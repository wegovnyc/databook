"""Crosswalk the org register to PASSPort vendors — Track B.

    docker compose exec -T api python build_org_vendor_crosswalk.py            # report
    docker compose exec -T api python build_org_vendor_crosswalk.py --apply    # write

WHAT THIS IS FOR, AND WHAT IT IS DELIBERATELY NOT
=================================================
Some civic actors in the org register also hold City contracts: MoMA, Carnegie
Hall, Central Park Conservancy, the BIDs, the political consultancies. Measured
2026-07-31 — **52 of 1,248 live orgs** match a PASSPort vendor, and **29 of them
hold at least one contract**, including Chinese-American Planning Council (192
contracts / $101.8M) and Central Park Conservancy ($248.8M). That is worth
surfacing on both profiles.

⚠ **Vendors are NOT merged into the directory** — a decision already taken, not
revisited here. 52 of 1,248 orgs is 4% of the directory and 0.14% of the 36,374
vendors; merging would swamp a curated register 30:1 across two identity schemes
with different editorial standards. The register's working definition is *civic
actors in NYC governance*: vendors as a class do not belong, while the ones that
are civic actors already do. These 52 overlaps are that intersection working.
So: a crosswalk, joined at read time. Nothing here writes to `wegov_orgs`.

THE SHAPE, AND WHY IT IS THIS SHAPE
===================================
⚠ **An unreviewed candidate NEVER goes in the link column.** `passport_supplier_id`
holds only a link we stand behind; a match awaiting review sits in
`candidate_supplier_id` with the link column NULL. The NYCHA crosswalk put
unreviewed candidates in the real id column and depended on every consumer
filtering out the tier — one missed filter publishes an unreviewed match (#146).
Here a join on `passport_supplier_id` cannot go wrong.

⚠ **A rebuild DELETEs every non-curated row first**, then re-inserts. The NYCHA
generator was upsert-only, so corrected false positives survived and were
re-written on the next run (#149).

⚠ **Curated rows are never overwritten**, and a curated row may deliberately be a
NO-MATCH (id `-`), which both prevents auto-linking and stops the pair returning
to the review queue forever (#155).

THE TIERS
=========
    exact          identical after punctuation-only normalization -> LINKS
    exact-suffix   identical after also stripping INC/LLC/CORP/THE/... -> LINKS
                   only when the matched variant has >= 2 significant tokens
    suffix-review  the same, but a single-token key -> DOES NOT LINK
    fuzzy          token-blocked ratio >= 0.96 with a distinctive shared token
                   (build_nycha_vendor_crosswalk._fuzzy_matches) -> LINKS
    fuzzy-review   0.86-0.96 -> DOES NOT LINK
    curated        a human said so -> LINKS (unless the no-match marker)
    rejected       a human said not this -> DOES NOT LINK

⚠ **THE SINGLE-TOKEN RULE EARNS ITS KEEP.** Measured on prod: suffix stripping
reduces both `The Nation` (the magazine) and `NATION GROUP INC` (an unrelated
firm) to the single token `NATION`. Requiring two significant tokens holds that
for review while still auto-linking `Central Park Conservancy` ->
`CENTRAL PARK CONSERVANCY INC` and `Prospect Park Alliance` ->
`PROSPECT PARK ALLIANCE INC`.

⚠ **The suffix list is the imported one, and it is NARROWER than it looks** —
`CORP` is stripped, `CORPORATION` is not. Measured consequence: exactly one
legitimate match is missed, `Carnegie Hall` -> `THE CARNEGIE HALL CORPORATION`,
which is therefore a curated row. Widening the list was considered and rejected:
adding CORPORATION/ASSOCIATION/TRUST/FUND would collapse `X Trust`, `X Fund` and
`X Association` all onto `X` and invent collisions, which is a poor trade for one
match that one CSV line already fixes.

⚠ It is computed on the **variant that actually matched**, not on the org's
primary name. `NYC & Company` normalizes to the single token `NYC` — but it
matched through its `display_name` (`New York City Tourism + Conventions`, four
tokens), which is the key that must be judged. Judging the wrong string would
have held a correct link.

⚠ **Many orgs may share one vendor, legitimately.** `United Federation of
Teachers` exists three times in the register (the union and two bargaining
units) and all three match supplier 1713785. One row per ORG, so this is
representable; a vendor-side lookup returns all of them and the consumer decides.
"""

import argparse
import asyncio
import collections
import csv
import os
import re
import sys

import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

try:
    import dbcreds
except ImportError:
    from modules import dbcreds

# Inherit the fuzzy matcher WHOLESALE rather than re-implementing it: it carries
# the #147 apostrophe fix, the #148 distinctive-token gate and the 0.96 floor,
# each of which exists because of a real false positive. A second copy would
# drift. (Same reasoning as enrich_doing_business.py.)
from build_nycha_vendor_crosswalk import _fuzzy_matches, _tokens
from build_nycha_vendor_crosswalk import norm as suffix_norm

DATA = os.environ.get("DATA_LAKE_PATH", "/data")
# ⚠ Defaults to the VERSION-CONTROLLED seed in this repo, not to /data. The
# NYCHA curated CSV lives only on the box, so 212 reviewed decisions exist in
# exactly one place and vanish with a rebuild. Overridable for a scratch file.
CURATED_CSV = os.environ.get(
    "ORG_VENDOR_CURATED_CSV",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "seed", "org_vendor_curated.csv"))

# Tiers whose row carries a real link. Everything else is a candidate or a
# rejection. ⚠ The TIER is the predicate, never the `curated` boolean — a human
# REJECTION is also curated (see build_nyc_org_crosswalk.py's note).
LINK_TIERS = ("exact", "exact-suffix", "fuzzy", "curated")

# Minimum significant tokens for a suffix-normalized match to auto-link.
MIN_SUFFIX_TOKENS = 2

# Org types that are never vendors in any meaningful sense — excluded so the
# fuzzy pass does not spend candidates on them or invent links for chart
# scaffolding. (`Classification`/`Official` are chart nodes, not bodies.)
EXCLUDED_TYPES = ("Classification", "Official", "Public Figure")

_NO_MATCH = {"-", "", "none", "null", "no", "nomatch", "no-match", "x"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS org_vendor_crosswalk (
    org_id                integer     NOT NULL,
    org_name              text,
    matched_variant       text,
    passport_supplier_id  text,
    candidate_supplier_id text,
    vendor_name           text,
    match_tier            text        NOT NULL,
    match_score           double precision,
    curated               boolean     NOT NULL DEFAULT false,
    curated_note          text,
    derived_at            timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id)
);
CREATE INDEX IF NOT EXISTS idx_org_vendor_xwalk_supplier
    ON org_vendor_crosswalk (passport_supplier_id);
CREATE INDEX IF NOT EXISTS idx_org_vendor_xwalk_tier
    ON org_vendor_crosswalk (match_tier);
"""


def strict_norm(s: str) -> str:
    """Punctuation-only normalization — NO suffix stripping.

    Deliberately separate from `suffix_norm`: dropping INC/LLC/CORP is what makes
    `MERCURY ENTERPRISES INC` collide with `Mercury`, so the two passes are
    tiered rather than merged.
    """
    s = (s or "").upper()
    s = re.sub(r"[‘’ʼ'`´]", "", s)
    return re.sub(r"[^A-Z0-9]", "", s)


def variants(org) -> list:
    """The org name spellings worth matching on, most authoritative first."""
    out, seen = [], set()
    for v in (org["name"], org["display_name"], org["alternate_name"]):
        v = (v or "").strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def _load_curated() -> list:
    """Curated seed CSV: org_id,passport_supplier_id[,note].

    ⚠ Must be REAL quoted CSV — org names contain commas, and hand-splitting on
    commas is how 47 of 212 rows were mangled in the NYCHA review (#155).
    """
    if not os.path.exists(CURATED_CSV):
        return []
    rows = []
    with open(CURATED_CSV, newline="", encoding="utf-8") as fh:
        for r in csv.reader(fh):
            if not r or not (r[0] or "").strip() or r[0].lstrip().startswith("#"):
                continue
            try:
                oid = int((r[0] or "").strip())
            except ValueError:
                continue                     # header line or junk
            sid = (r[1] if len(r) > 1 else "").strip()
            note = (r[2] if len(r) > 2 else "").strip()
            rows.append((oid, sid, note))
    return rows


async def build(conn, plan, apply):
    orgs = [dict(r) for r in await conn.fetch(
        'SELECT id, name, alternate_name, display_name, "type" FROM wegov_orgs '
        "WHERE retired_at IS NULL AND \"type\" <> ALL($1::text[])",
        list(EXCLUDED_TYPES))]
    vendors = [dict(r) for r in await conn.fetch(
        'SELECT "PASSPort Supplier-ID" AS sid, "Vendor Name" AS nm FROM vendors '
        'WHERE COALESCE("Vendor Name",\'\') <> \'\'')]
    plan.append(f"{len(orgs)} live orgs (excluding {list(EXCLUDED_TYPES)}), "
                f"{len(vendors)} PASSPort vendors")

    v_strict, v_suffix = collections.defaultdict(list), collections.defaultdict(list)
    for v in vendors:
        v_strict[strict_norm(v["nm"])].append(v)
        v_suffix[suffix_norm(v["nm"])].append(v)

    curated = _load_curated()
    curated_ids = {oid for oid, _sid, _n in curated}
    plan.append(f"curated seed rows: {len(curated)} (from {CURATED_CSV})")

    rows = []          # dicts ready to insert
    unresolved = []    # orgs with no exact/suffix hit -> the fuzzy pass
    counts = collections.Counter()

    for o in orgs:
        if o["id"] in curated_ids:
            continue                          # a human already decided this org
        hit = None
        for var in variants(o):
            ks = strict_norm(var)
            if ks and len(ks) >= 6 and ks in v_strict:
                hit = (var, v_strict[ks][0], "exact", 1.0)
                break
        if not hit:
            for var in variants(o):
                kn = suffix_norm(var)
                if not kn or len(kn) < 6 or kn not in v_suffix:
                    continue
                # ⚠ Judged on the variant that MATCHED, not on o["name"].
                toks = len(_tokens(kn))
                tier = ("exact-suffix" if toks >= MIN_SUFFIX_TOKENS
                        else "suffix-review")
                hit = (var, v_suffix[kn][0], tier, 1.0)
                break
        if hit:
            var, v, tier, score = hit
            counts[tier] += 1
            links = tier in LINK_TIERS
            rows.append(dict(
                org_id=o["id"], org_name=o["name"], matched_variant=var,
                passport_supplier_id=(v["sid"] if links else None),
                candidate_supplier_id=(None if links else v["sid"]),
                vendor_name=v["nm"], match_tier=tier, match_score=score,
                curated=False, curated_note=None))
        else:
            unresolved.append(o)

    # ── fuzzy pass over what is left ────────────────────────────────────────
    pv_entries = [(suffix_norm(v["nm"]), v["sid"], v["nm"]) for v in vendors]
    var_to_org, fuzz_input = {}, []
    for o in unresolved:
        for var in variants(o):
            # First variant wins if two variants of one org both match; the
            # primary name is the most authoritative spelling.
            var_to_org.setdefault(var, o)
            fuzz_input.append(var)
    high, review = _fuzzy_matches(fuzz_input, pv_entries)
    plan.append(f"fuzzy: {len(high)} at/above the auto-link floor, "
                f"{len(review)} held for review")

    seen_orgs = {r["org_id"] for r in rows}
    for bucket, tier in ((high, "fuzzy"), (review, "fuzzy-review")):
        for var, sid, vname, score in bucket:
            o = var_to_org.get(var)
            if not o or o["id"] in seen_orgs or o["id"] in curated_ids:
                continue
            seen_orgs.add(o["id"])
            counts[tier] += 1
            links = tier in LINK_TIERS
            rows.append(dict(
                org_id=o["id"], org_name=o["name"], matched_variant=var,
                passport_supplier_id=(sid if links else None),
                candidate_supplier_id=(None if links else sid),
                vendor_name=vname, match_tier=tier, match_score=score,
                curated=False, curated_note=None))

    # ── curated rows last, and they win ─────────────────────────────────────
    vendor_by_sid = {v["sid"]: v["nm"] for v in vendors}
    org_by_id = {o["id"]: o for o in orgs}
    curated_rows = []
    for oid, sid, note in curated:
        o = org_by_id.get(oid)
        if not o:
            plan.append(f"    curated: SKIP org {oid} — not a live org")
            continue
        if sid.lower() in _NO_MATCH:
            counts["rejected"] += 1
            curated_rows.append(dict(
                org_id=oid, org_name=o["name"], matched_variant=None,
                passport_supplier_id=None, candidate_supplier_id=None,
                vendor_name=None, match_tier="rejected", match_score=None,
                curated=True, curated_note=note or "reviewed: not this vendor"))
            continue
        counts["curated"] += 1
        curated_rows.append(dict(
            org_id=oid, org_name=o["name"], matched_variant=None,
            passport_supplier_id=sid, candidate_supplier_id=None,
            vendor_name=vendor_by_sid.get(sid), match_tier="curated",
            match_score=None, curated=True, curated_note=note or None))

    for tier in ("exact", "exact-suffix", "fuzzy", "curated",
                 "suffix-review", "fuzzy-review", "rejected"):
        if counts[tier]:
            mark = "LINKS " if tier in LINK_TIERS else "held  "
            plan.append(f"    {mark} {tier:<14} {counts[tier]}")

    linked = sum(counts[t] for t in LINK_TIERS)
    plan.append(f"total rows {len(rows) + len(curated_rows)}, of which "
                f"{linked} carry a link")

    # ⚠ A shrinking crosswalk is the signature of a bad upstream read. `vendors`
    # is re-ingested daily and a truncated response would silently empty this.
    if apply:
        before = await conn.fetchval(
            "SELECT count(*) FROM org_vendor_crosswalk "
            "WHERE match_tier = ANY($1::text[])", list(LINK_TIERS)) or 0
        if before and linked < before * 0.6:
            raise SystemExit(
                f"[org-vendor] ABORT: links would fall {before} -> {linked} "
                f"(>40% drop). Refusing to rebuild from what looks like a bad read.")

        async with conn.transaction():
            removed = await conn.execute(
                "DELETE FROM org_vendor_crosswalk WHERE curated = false")
            plan.append(f"cleared non-curated rows: {removed}")
            for r in rows + curated_rows:
                await conn.execute("""
                    INSERT INTO org_vendor_crosswalk
                        (org_id, org_name, matched_variant, passport_supplier_id,
                         candidate_supplier_id, vendor_name, match_tier,
                         match_score, curated, curated_note, derived_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10, now())
                    ON CONFLICT (org_id) DO UPDATE SET
                        org_name = EXCLUDED.org_name,
                        matched_variant = EXCLUDED.matched_variant,
                        passport_supplier_id = EXCLUDED.passport_supplier_id,
                        candidate_supplier_id = EXCLUDED.candidate_supplier_id,
                        vendor_name = EXCLUDED.vendor_name,
                        match_tier = EXCLUDED.match_tier,
                        match_score = EXCLUDED.match_score,
                        curated_note = EXCLUDED.curated_note,
                        derived_at = now()
                    WHERE org_vendor_crosswalk.curated = false
                       OR EXCLUDED.curated = true
                """, r["org_id"], r["org_name"], r["matched_variant"],
                    r["passport_supplier_id"], r["candidate_supplier_id"],
                    r["vendor_name"], r["match_tier"], r["match_score"],
                    r["curated"], r["curated_note"])
    return rows + curated_rows, counts


async def verify(conn):
    print("\n=== verification ===")
    # The invariant that #146 is about: no row may hold BOTH a live link and an
    # unreviewed candidate, and no held tier may carry a link.
    bad = await conn.fetchval(
        "SELECT count(*) FROM org_vendor_crosswalk "
        "WHERE passport_supplier_id IS NOT NULL AND candidate_supplier_id IS NOT NULL")
    print(f"rows with both a link and a candidate: {bad}  (must be 0)")
    leak = await conn.fetchval(
        "SELECT count(*) FROM org_vendor_crosswalk "
        "WHERE match_tier <> ALL($1::text[]) AND passport_supplier_id IS NOT NULL",
        list(LINK_TIERS))
    print(f"held/rejected rows carrying a link: {leak}  (must be 0)")
    nolink = await conn.fetchval(
        "SELECT count(*) FROM org_vendor_crosswalk "
        "WHERE match_tier = ANY($1::text[]) AND match_tier <> 'rejected' "
        "  AND passport_supplier_id IS NULL", list(LINK_TIERS))
    print(f"link tiers missing an id: {nolink}  (must be 0)")
    orphan = await conn.fetchval(
        "SELECT count(*) FROM org_vendor_crosswalk x "
        "LEFT JOIN wegov_orgs w ON w.id = x.org_id "
        "WHERE w.id IS NULL OR w.retired_at IS NOT NULL")
    print(f"rows pointing at a missing/retired org: {orphan}  (must be 0)")
    rows = await conn.fetch(
        "SELECT match_tier, count(*) AS n FROM org_vendor_crosswalk "
        "GROUP BY 1 ORDER BY 2 DESC")
    for r in rows:
        print(f"    {r['match_tier']:<14} {r['n']}")


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the crosswalk (default is a report)")
    ap.add_argument("--show", action="store_true",
                    help="list every row, so a human can review the held ones")
    args = ap.parse_args()

    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=dbcreds.password(),
        database=os.environ.get("POSTGRES_DB", "databook"))
    try:
        print(f"[org-vendor] mode: "
              f"{'APPLY' if args.apply else 'REPORT (pass --apply)'}\n")
        if args.apply:
            for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
                await conn.execute(stmt)
        plan = []
        rows, counts = await build(conn, plan, args.apply)
        for line in plan:
            print(f"[org-vendor] {line}")
        if args.show:
            print("\n=== every row ===")
            for r in sorted(rows, key=lambda x: (x["match_tier"], x["org_name"] or "")):
                link = r["passport_supplier_id"] or f"({r['candidate_supplier_id']})"
                print(f"  {r['match_tier']:<14} {str(r['org_name'])[:38]:<38} "
                      f"-> {link:<12} {str(r['vendor_name'])[:34]}")
        if args.apply:
            await verify(conn)
        else:
            print("\n[org-vendor] nothing written. Re-run with --apply.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())


async def derive_org_vendor_hook(conn):
    """Rebuild the crosswalk after a `vendors` ingest.

    Registered on `vendors` in data_scheduler.POST_INGEST_HOOKS for the same
    reason the Doing Business crosswalk is: this is name-matched against the
    vendor list, so it must be rebuilt whenever that list changes. Orgs move on
    a weekly cadence (`scripts/org-registry-refresh.sh`), and running here picks
    those up within a day too, so one registration covers both sides.

    ⚠ Guarded end to end. This is additive enrichment — an org profile and a
    vendor profile must both render without it, so a failure logs and returns
    rather than failing the ingest that triggered it.
    """
    try:
        for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
            await conn.execute(stmt)
        plan = []
        _rows, counts = await build(conn, plan, apply=True)
        linked = sum(counts[t] for t in LINK_TIERS)
        held = sum(counts[t] for t in ("suffix-review", "fuzzy-review"))
        print(f"[org-vendor] rebuilt: {linked} linked, {held} awaiting review")
    except Exception as exc:  # noqa: BLE001
        print(f"[org-vendor] hook failed (non-fatal): {exc}")
