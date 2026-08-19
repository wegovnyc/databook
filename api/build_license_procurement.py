#!/usr/bin/env python3
"""Build the procurement-analysis layer over licence families.

Three things, in one idempotent pass, because they are one logical refresh:

  1. PURCHASE CLASS  -- what kind of thing each family is (seed:
     license_family_class.csv). ⚠⚠ This exists because the replaceability rating
     HIDES MONEY: "could the City build this itself?" is the wrong question for
     infrastructure, so AWS ($6.80M) sits on `low` and drops out of every
     replaceability view, while the whole `high` set is $10.13M. Classifying the
     purchase is what lets the right question get asked of each line.

  2. CURATED CANDIDATES -- hand-reviewed replacement suggestions (seed:
     license_replacement_candidates.csv), tier `curated`.

  3. AUTO CANDIDATES -- mechanical matches against the catalogue's precomputed
     inverted index, tier `auto`.

⚠⚠ ONLY `curated` ROWS EVER RENDER. Auto rows land in
docs/license-replacement-review.md for review; promoting one means adding it to
the seed, where it is a diff. This is the #146 lesson made structural: an
unreviewed candidate must not be able to reach a public page by accident.

⚠ AN EMPTY MATCH MEANS "NOT MAPPED", NOT "NO ALTERNATIVE EXISTS". The
catalogue's `replaces` index covers 95 proprietary products out of 1,995
entries. The only absences safe to report as real gaps are the four the
catalogue itself asserts in /meta.json -> known_gaps.

    docker compose exec -T api python build_license_procurement.py
    docker compose exec -T api python build_license_procurement.py --offline
"""
import argparse
import asyncio
import csv
import json
import os
import re
import sys
import urllib.request
from collections import Counter

from modules import autoload  # noqa: F401,E402
from modules import dbcreds  # noqa: E402
from modules import licenseclass  # noqa: E402
from modules.errfmt import exc_str  # noqa: E402
from config import Config  # noqa: E402
import asyncpg  # noqa: E402

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")
BASE = "https://govoss-catalog.vercel.app"
# ⚠ Pin the VERSIONED alias. The unversioned path is free to change shape; this
# one is the catalogue's own promise not to break consumers.
ENTRIES_URL = f"{BASE}/v1/entries.json"
BYPRODUCT_URL = f"{BASE}/by-product.json"
META_URL = f"{BASE}/meta.json"
SNAPSHOT = os.path.join(SEED_DIR, "govoss_catalog_snapshot.json")

# ⚠ Floors, not warnings. A truncated fetch that silently shrank the match pool
# would look like "the catalogue has fewer options now" -- the same class as the
# org crosswalk's row-count guard, which caught exactly this.
MIN_ENTRIES = 1500
MIN_MAPPED_PRODUCTS = 50

DDL = """
CREATE TABLE IF NOT EXISTS license_family_class (
    family     text PRIMARY KEY,
    class      text NOT NULL,
    lever      text NOT NULL DEFAULT '',
    why        text NOT NULL DEFAULT '',
    built_at   timestamptz NOT NULL DEFAULT now()
);
-- ⚠ `capability` and `tier` are declared HERE as well as in
-- classify_license_purchases.py, because routers/licenses.py SELECTs both and its
-- fetch is wrapped in a try/except that logs and leaves `classes` EMPTY on error.
-- So on a database where only this script had ever run, a missing column would
-- silently empty the entire purchase-class view rather than raise -- the #146
-- failure shape. Idempotent, so declaring it twice costs nothing.
ALTER TABLE license_family_class ADD COLUMN IF NOT EXISTS capability text NOT NULL DEFAULT '';
ALTER TABLE license_family_class ADD COLUMN IF NOT EXISTS tier text NOT NULL DEFAULT 'auto';
-- ⚠ PRODUCT-grain class, an OVERRIDE of the family's. A family is a merge of
-- product spellings, so one class per family could not hold two answers: $68.9M
-- of Microsoft support sat inside a `software-licence` family being asked about
-- open-source substitutes. `product_norm` is norm(product_raw), so one row
-- covers every spelling. See modules/licenseclass.py.
CREATE TABLE IF NOT EXISTS license_product_class (
    product_norm text PRIMARY KEY,
    product      text NOT NULL DEFAULT '',
    class        text NOT NULL,
    lever        text NOT NULL DEFAULT '',
    why          text NOT NULL DEFAULT '',
    tier         text NOT NULL DEFAULT 'curated',
    built_at     timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS license_replacement_candidate (
    family         text NOT NULL,
    candidate      text NOT NULL DEFAULT '',
    candidate_kind text NOT NULL,
    confidence     text NOT NULL,
    licence        text NOT NULL DEFAULT '',
    gov_adopters   integer,
    url            text NOT NULL DEFAULT '',
    why            text NOT NULL DEFAULT '',
    tier           text NOT NULL DEFAULT 'auto',
    searched_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (family, candidate, tier)
);
CREATE INDEX IF NOT EXISTS idx_lrc_family ON license_replacement_candidate (family);
CREATE INDEX IF NOT EXISTS idx_lrc_tier   ON license_replacement_candidate (tier);
CREATE TABLE IF NOT EXISTS license_catalogue_meta (
    id           integer PRIMARY KEY DEFAULT 1,
    generated_at text NOT NULL DEFAULT '',
    entries      integer NOT NULL DEFAULT 0,
    mapped_products integer NOT NULL DEFAULT 0,
    known_gaps   jsonb,
    fetched_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT license_catalogue_meta_single CHECK (id = 1)
);
"""


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def read_seed(name):
    """⚠ Strip comment lines BEFORE the CSV parser. A `#` line containing a comma
    parses as a real row otherwise -- a bug already paid for in this codebase."""
    path = os.path.join(SEED_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return [r for r in csv.DictReader(lines)
            if any((v or "").strip() for v in r.values())]


def fetch_catalogue(offline):
    """Live fetch, snapshotted. --offline replays the snapshot so a build is
    reproducible and CI never depends on a third-party host."""
    if offline:
        if not os.path.exists(SNAPSHOT):
            print(f"REFUSING: --offline but no snapshot at {SNAPSHOT}")
            return None
        data = json.load(open(SNAPSHOT, encoding="utf-8"))
        print(f"offline: replaying snapshot fetched {data.get('fetched_at')}")
        return data

    out = {}
    for key, url in (("meta", META_URL), ("by_product", BYPRODUCT_URL),
                     ("entries", ENTRIES_URL)):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                out[key] = json.loads(r.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"REFUSING: could not fetch {url}: {exc_str(exc)}")
            return None

    entries = out["entries"] if isinstance(out["entries"], list) \
        else out["entries"].get("entries", [])
    if len(entries) < MIN_ENTRIES:
        print(f"REFUSING: only {len(entries)} catalogue entries "
              f"(floor {MIN_ENTRIES}) -- treating as a truncated fetch")
        return None
    if len(out["by_product"]) < MIN_MAPPED_PRODUCTS:
        print(f"REFUSING: only {len(out['by_product'])} mapped products "
              f"(floor {MIN_MAPPED_PRODUCTS})")
        return None

    data = {
        "fetched_at": None,   # stamped by the caller; scripts avoid clock calls
        "generated_at": out["meta"].get("generated_at", ""),
        "counts": out["meta"].get("counts", {}),
        "known_gaps": out["meta"].get("known_gaps", {}),
        "by_product": out["by_product"],
        # ⚠ Keep only what the matcher needs. The full entries file is 2.9 MB and
        # committing it would put a third party's dataset in our history.
        "entry_names": sorted({(e.get("name") or "") for e in entries
                               if e.get("name") and not e.get("link_dead")}),
        "entries": len(entries),
    }
    return data


_CONF_ORDER = {"strong": 0, "partial": 1, "adjacent": 2}


def best_alt(alts):
    """Strongest confidence first, then most government adopters.

    ⚠ Ranking by ADOPTION, not text similarity. `LimeSurvey, 18 adopters,
    GPL-3.0` is the argument a public-sector buyer needs; a similarity score is
    not. Adoption is also the one field here that is a fact rather than a
    judgement."""
    return sorted(alts, key=lambda a: (_CONF_ORDER.get(a.get("confidence"), 3),
                                       -(a.get("adopters") or 0)))[0]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="replay the committed snapshot instead of fetching")
    ap.add_argument("--report", default="docs/license-replacement-review.md")
    args = ap.parse_args()

    cat = fetch_catalogue(args.offline)
    if cat is None:
        return 1

    by_product = cat["by_product"]
    bp_idx = {norm(k): (k, v) for k, v in by_product.items()}
    aliases = {r["family"].strip(): (r.get("catalogue_product") or "").strip()
               for r in read_seed("license_product_aliases.csv") if r.get("family")}

    conn = await asyncpg.connect(**dbcreds.settings(Config.db))
    try:
        for stmt in DDL.strip().split(";"):
            if stmt.strip():
                await conn.execute(stmt)

        # --- our families -------------------------------------------------
        fams = await conn.fetch("""
            WITH c AS (
                SELECT DISTINCT ON (contract_id) contract_id, current_amount, award_amount
                FROM contracts WHERE contract_id IS NOT NULL
                ORDER BY contract_id, coalesce(current_amount,0) DESC
            )
            SELECT lf.family,
                   count(*)                                          AS contracts,
                   sum(coalesce(c.current_amount, c.award_amount, 0)) AS value
            FROM digital_contract_enrichment e
            JOIN c ON c.contract_id = e.contract_id
            JOIN license_family lf ON lf.product_raw = e.license_product
            WHERE e.is_license AND NOT lf.is_generic
            GROUP BY lf.family
        """)
        if not fams:
            print("REFUSING: no licence families found -- has the classifier run?")
            return 1
        fam_value = {f["family"]: float(f["value"] or 0) for f in fams}

        # --- 1. purchase class (curated seed only; no AI in this script) ---
        cls_rows = read_seed("license_family_class.csv")
        async with conn.transaction():
            # ⚠ NO TRUNCATE. It would wipe the 392 AI-assigned capabilities every
            # time this loader ran, and the next page render would show a
            # half-empty function view with nothing reporting why.
            await conn.execute("UPDATE license_family_class SET tier='auto' "
                               "WHERE tier='curated'")
            for r in cls_rows:
                # ⚠ tier='curated' and a non-empty capability must both stick:
                # the AI pass writes only where tier <> 'curated', so a hand-set
                # function survives every refresh. A blank capability here leaves
                # the AI's value alone rather than erasing it.
                cap = (r.get("capability") or "").strip()
                await conn.execute(
                    """INSERT INTO license_family_class
                           (family, class, lever, why, capability, tier)
                       VALUES ($1,$2,$3,$4,$5,'curated')
                       ON CONFLICT (family) DO UPDATE
                       SET class=EXCLUDED.class, lever=EXCLUDED.lever,
                           why=EXCLUDED.why, tier='curated',
                           capability = CASE WHEN EXCLUDED.capability <> ''
                                             THEN EXCLUDED.capability
                                             ELSE license_family_class.capability END""",
                    r["family"].strip(), r["class"].strip(),
                    (r.get("lever") or "").strip(), (r.get("why") or "").strip(), cap)
        unknown_cls = [r["family"] for r in cls_rows if r["family"].strip() not in fam_value]
        print(f"purchase classes: {len(cls_rows)} loaded"
              + (f"  ⚠ {len(unknown_cls)} name no live family: {unknown_cls[:5]}"
                 if unknown_cls else ""))

        # --- 1b. PRODUCT-grain class overrides ----------------------------
        # ⚠ Why a second table rather than more rows in the one above: the family
        # class is the DEFAULT and is mostly AI-assigned, while these are
        # exceptions where the purchase kind inside a family genuinely differs.
        # Keeping them apart is what lets an absent product mean "the family
        # answer is fine" instead of "unclassified".
        prod_rows = read_seed("license_product_class.csv")
        known_products = {r["product_raw"]: r["product_norm"] for r in (
            await conn.fetch("SELECT product_raw, product_norm FROM license_family"))}
        known_norms = set(known_products.values())
        async with conn.transaction():
            # ⚠ Deletes only `curated`, not the whole table. Nothing writes `auto`
            # here today, but a future product-grain AI pass would — and a blanket
            # delete is exactly how the 392 AI capabilities were wiped once.
            await conn.execute("DELETE FROM license_product_class WHERE tier='curated'")
            for r in prod_rows:
                raw = (r.get("product") or "").strip()
                cls = (r.get("class") or "").strip()
                if not raw or not cls:
                    continue
                await conn.execute(
                    """INSERT INTO license_product_class
                           (product_norm, product, class, lever, why, tier)
                       VALUES ($1,$2,$3,$4,$5,'curated')
                       ON CONFLICT (product_norm) DO UPDATE
                       SET product=EXCLUDED.product, class=EXCLUDED.class,
                           lever=EXCLUDED.lever, why=EXCLUDED.why, tier='curated'""",
                    licenseclass.norm(raw), raw, cls,
                    (r.get("lever") or "").strip() or licenseclass.LEVER_FOR.get(cls, ""),
                    (r.get("why") or "").strip())
        # ⚠ AN OVERRIDE FOR A PRODUCT THAT DOES NOT EXIST IS INERT, and silence
        # would make it indistinguishable from one that worked. Name them.
        inert = [r["product"] for r in prod_rows
                 if (r.get("product") or "").strip()
                 and licenseclass.norm(r["product"]) not in known_norms]
        print(f"product-class overrides: {len(prod_rows)} loaded"
              + (f"  ⚠ {len(inert)} MATCH NO PRODUCT and change nothing: {inert}"
                 if inert else "  (all match a live product)"))

        # --- 2. curated candidates ----------------------------------------
        cand_rows = read_seed("license_replacement_candidates.csv")
        async with conn.transaction():
            await conn.execute("DELETE FROM license_replacement_candidate WHERE tier='curated'")
            for r in cand_rows:
                adopters = (r.get("gov_adopters") or "").strip()
                await conn.execute(
                    """INSERT INTO license_replacement_candidate
                       (family, candidate, candidate_kind, confidence, licence,
                        gov_adopters, url, why, tier)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'curated')
                       ON CONFLICT (family, candidate, tier) DO UPDATE
                       SET candidate_kind=EXCLUDED.candidate_kind,
                           confidence=EXCLUDED.confidence, licence=EXCLUDED.licence,
                           gov_adopters=EXCLUDED.gov_adopters, url=EXCLUDED.url,
                           why=EXCLUDED.why""",
                    r["family"].strip(), (r.get("candidate") or "").strip(),
                    r["candidate_kind"].strip(), r["confidence"].strip(),
                    (r.get("licence") or "").strip(),
                    int(adopters) if adopters.isdigit() else None,
                    (r.get("url") or "").strip(), (r.get("why") or "").strip())
        print(f"curated candidates: {len(cand_rows)} loaded")

        # --- 3. auto matches ----------------------------------------------
        # Detector A: the family name IS a catalogue entry name -> the product is
        # already open source and the spend is a paid tier. Highest-confidence
        # class of finding, and it needs no judgement at all.
        entry_names = {norm(n): n for n in cat["entry_names"]}
        # Detector B: the alias/name/substring chain into the replaces index.
        auto, matched, unmapped = [], 0, []
        for fam in sorted(fam_value):
            alias = aliases.get(fam)
            if fam in aliases and not alias:
                continue          # deliberately blank: do not attempt a match
            hit = None
            if alias:
                hit = (alias, by_product.get(alias, []))
            if not hit or not hit[1]:
                hit = bp_idx.get(norm(fam))
            if not hit:
                k = norm(fam)
                for nk, pair in bp_idx.items():
                    if len(nk) > 5 and (nk in k or k in nk):
                        hit = pair
                        break
            if not hit or not hit[1]:
                if norm(fam) in entry_names:
                    auto.append((fam, entry_names[norm(fam)], "oss-same-product",
                                 "strong", "", None, "",
                                 "Family name matches a catalogue entry exactly: the "
                                 "product is already open source, so the spend is a "
                                 "paid tier or support contract."))
                    matched += 1
                else:
                    unmapped.append(fam)
                continue
            product, alts = hit
            b = best_alt(alts)
            kind = {"software": "oss-replacement", "paid-tier": "oss-same-product",
                    "service": "hosting-alt"}.get(b.get("kind"), "oss-replacement")
            auto.append((fam, b.get("name", ""), kind, b.get("confidence", "adjacent"),
                         b.get("licence") or b.get("licence_spdx") or "",
                         b.get("adopters"), b.get("url") or b.get("repo_url") or "",
                         f"Auto-matched via /by-product.json key '{product}' "
                         f"(kind={b.get('kind')}, {b.get('adopters') or 0} adopters)."))
            matched += 1

        async with conn.transaction():
            await conn.execute("DELETE FROM license_replacement_candidate WHERE tier='auto'")
            for row in auto:
                await conn.execute(
                    """INSERT INTO license_replacement_candidate
                       (family, candidate, candidate_kind, confidence, licence,
                        gov_adopters, url, why, tier)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'auto')
                       ON CONFLICT (family, candidate, tier) DO NOTHING""", *row)

        await conn.execute("""
            INSERT INTO license_catalogue_meta
                (id, generated_at, entries, mapped_products, known_gaps, fetched_at)
            VALUES (1,$1,$2,$3,$4, now())
            ON CONFLICT (id) DO UPDATE SET generated_at=EXCLUDED.generated_at,
                entries=EXCLUDED.entries, mapped_products=EXCLUDED.mapped_products,
                known_gaps=EXCLUDED.known_gaps, fetched_at=now()
        """, cat["generated_at"], cat["entries"], len(by_product),
            json.dumps(cat["known_gaps"]))

        # --- report --------------------------------------------------------
        curated_fams = {r["family"].strip() for r in cand_rows}
        pending = [a for a in auto if a[0] not in curated_fams]
        by_conf = Counter(a[3] for a in auto)
        print(f"auto matches: {matched} of {len(fam_value)} families "
              f"({dict(by_conf)});  {len(unmapped)} unmapped")
        print(f"  ⚠ unmapped means NOT MAPPED, not 'no alternative exists' -- the "
              f"index covers {len(by_product)} products")
        print(f"  {len(pending)} auto matches await review (not rendered)")
        print(f"catalogue: {cat['entries']} entries, generated_at {cat['generated_at']}")

        report = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", args.report)
        os.makedirs(os.path.dirname(report), exist_ok=True)
        with open(report, "w", encoding="utf-8") as fh:
            fh.write("# Licence replacement review queue\n\n")
            fh.write("Auto-generated by `api/build_license_procurement.py`. "
                     "**Nothing here renders on any page.**\n"
                     "To publish a row, add it to "
                     "`api/seed/license_replacement_candidates.csv`, where it "
                     "becomes a reviewable diff.\n\n")
            fh.write(f"- Catalogue `generated_at`: **{cat['generated_at']}**\n")
            fh.write(f"- Catalogue entries: {cat['entries']}; "
                     f"proprietary products mapped: {len(by_product)}\n")
            fh.write(f"- Our families: {len(fam_value)}; auto-matched: {matched}; "
                     f"unmapped: {len(unmapped)}\n")
            fh.write("- ⚠ An unmapped family means **not mapped**, not "
                     "\"no alternative exists\".\n\n")
            fh.write("## Awaiting review, by value\n\n")
            fh.write("| $ | family | candidate | confidence | kind | adopters |\n")
            fh.write("|---:|---|---|---|---|---:|\n")
            for a in sorted(pending, key=lambda x: -fam_value.get(x[0], 0)):
                fh.write(f"| {fam_value.get(a[0],0)/1e3:,.0f}K | {a[0]} | {a[1]} | "
                         f"{a[3]} | {a[2]} | {a[5] or ''} |\n")
            gaps = (cat["known_gaps"] or {}).get("no_results_observed_for") or []
            if gaps:
                fh.write("\n## Gaps the catalogue itself asserts\n\n")
                fh.write("These are real absences, corroborated by the catalogue's "
                         "own `known_gaps`, not just an empty search:\n\n")
                for g in gaps:
                    fh.write(f"- {g}\n")
            fh.write("\n## Unmapped families by value (top 40)\n\n")
            for fam in sorted(unmapped, key=lambda f: -fam_value.get(f, 0))[:40]:
                fh.write(f"- {fam_value.get(fam,0)/1e3:,.0f}K — {fam}\n")
        print(f"wrote {args.report}")

        if not args.offline:
            cat_out = dict(cat)
            cat_out["fetched_at"] = cat["generated_at"]
            json.dump(cat_out, open(SNAPSHOT, "w", encoding="utf-8"), indent=1)
            print(f"snapshot written to seed/{os.path.basename(SNAPSHOT)}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
