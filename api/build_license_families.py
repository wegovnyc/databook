#!/usr/bin/env python3
"""Derive the `license_family` mapping that groups AI-detected license products.

WHY THIS EXISTS. `digital_contract_enrichment.license_product` is free text the
classifier produced, and it fragments badly: measured 2026-08-10, **525 distinct
strings for 948 license contracts**. Left ungrouped, the Licenses page tells
lies of omission -- `ShotSpotter` ($21.9M) and `SoundThinking` ($22.0M) read as
two products when SoundThinking IS the renamed ShotSpotter, and `ArcGIS` (12
contracts) and `ESRI ArcGIS` (8) split Esri's footprint in half.

TWO LAYERS, because they fail differently:
  * AUTO -- norm() folds case and punctuation, so `Solarwinds`/`SolarWinds` and
    `Accellion/Kiteworks`/`Accellion Kiteworks` merge with no human judgement.
    Mechanical, safe, needs no review.
  * CURATED -- seed/license_family_curated.csv, version-controlled, for merges
    that require knowing something about the world: that Checkpoint is Check
    Point, that Micro Focus and Microfocus are one vendor, that Precisely used to
    be Pitney Bowes. A wrong merge here is a reviewable diff, which is the whole
    point -- the ILIKE rules this replaces lived inside a query where nobody
    could see or correct them.

⚠ GENERIC VALUES ARE NOT PRODUCTS. The classifier emits `Various`, `Unknown`,
`Engineering Software`, `Project Management Software`, `EHR System` and friends
when it cannot identify a product. Those are marked is_generic and must be
presented as "unidentified", never ranked as if they were software. Curating
them into a real family would manufacture a product that does not exist.

Idempotent; rebuild after any classifier run:
    docker compose exec -T api python build_license_families.py
"""
import asyncio
import csv
import os
import re
import sys
from collections import Counter, defaultdict

from modules import autoload  # noqa: F401
from modules import dbcreds
from config import Config
import asyncpg

SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "seed", "license_family_curated.csv")

# ⚠ Refuse to publish a mapping built from suspiciously few products -- the same
# argument as the org crosswalk's row-count guard. A truncated read that rebuilt
# the table with 12 rows would silently collapse the whole page's grouping.
MIN_PRODUCTS = 200

DDL = """
CREATE TABLE IF NOT EXISTS license_family (
    product_raw  text PRIMARY KEY,
    product_norm text NOT NULL,
    family       text NOT NULL,
    slug         text NOT NULL DEFAULT '',
    curated      boolean NOT NULL DEFAULT false,
    is_generic   boolean NOT NULL DEFAULT false,
    contracts    integer NOT NULL DEFAULT 0,
    built_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE license_family ADD COLUMN IF NOT EXISTS slug text NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_license_family_family ON license_family (family);
CREATE INDEX IF NOT EXISTS idx_license_family_norm   ON license_family (product_norm);
CREATE INDEX IF NOT EXISTS idx_license_family_slug   ON license_family (slug);
"""


def slugify(name: str) -> str:
    """Family name -> URL segment. `SoundThinking (ShotSpotter)` ->
    `soundthinking-shotspotter`."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "unnamed"


def assign_slugs(families):
    """Deterministic, collision-free slugs.

    ⚠ STABILITY IS THE REQUIREMENT, because these become public URLs. Families
    are sorted before numbering, so a rebuild cannot silently swap which family
    owns `microsoft` and which owns `microsoft-2` — that would repoint a live
    link at a different product. Collisions get a numeric suffix rather than
    being merged: two families that slugify the same are still two families.
    """
    out, seen = {}, {}
    for fam in sorted(families):
        base = slugify(fam)
        n = seen.get(base, 0) + 1
        seen[base] = n
        out[fam] = base if n == 1 else f"{base}-{n}"
    return out


def norm(s: str) -> str:
    """Fold case and punctuation. `Accellion/Kiteworks` -> `ACCELLION KITEWORKS`.

    ⚠ Deliberately does NOT strip corporate suffixes (INC/CORP/LLC). The org
    work already paid for that lesson: widening a normalizer collapses
    `X Trust` / `X Fund` / `X Association` onto `X`. Here it would merge
    `Quest` with `Quest Toad` and `Quest Spotlight`, which are different
    products from one vendor -- a judgement that belongs in the curated file.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", s or "")).strip().upper()


def load_curated():
    """product_norm -> (family, is_generic). Keyed on the NORMALIZED form so a
    curator can type the product however it appears and still match."""
    if not os.path.exists(SEED):
        print(f"⚠ no curated seed at {SEED} — auto layer only")
        return {}
    out = {}
    with open(SEED, newline="", encoding="utf-8") as fh:
        # ⚠ Strip comment lines BEFORE the CSV parser sees them. A `#` line
        # containing a comma ("# different purchases, prefer leaving them
        # separate") parses as product="# different purchases" with a non-empty
        # family and would install itself as a real curated rule.
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
        for row in csv.DictReader(lines):
            raw = (row.get("product") or "").strip()
            fam = (row.get("family") or "").strip()
            if not raw or not fam:
                continue
            out[norm(raw)] = (fam, (row.get("generic") or "").strip().lower()
                              in ("1", "true", "yes", "y"))
    return out


async def main():
    curated = load_curated()
    conn = await asyncpg.connect(**dbcreds.settings(Config.db))
    try:
        rows = await conn.fetch("""
            SELECT license_product AS p, count(*) AS n
            FROM digital_contract_enrichment
            WHERE is_license AND coalesce(trim(license_product),'') <> ''
            GROUP BY license_product
        """)
        if len(rows) < MIN_PRODUCTS:
            print(f"REFUSING: only {len(rows)} distinct products found "
                  f"(floor {MIN_PRODUCTS}). Has the classifier run?")
            return 1

        # Group raw spellings by normalized key, so the auto layer merges them.
        by_norm = defaultdict(list)
        for r in rows:
            by_norm[norm(r["p"])].append((r["p"], r["n"]))

        records, families = [], Counter()
        matched_curated = set()
        for nkey, spellings in by_norm.items():
            if nkey in curated:
                family, generic = curated[nkey]
                matched_curated.add(nkey)
                is_cur = True
            else:
                # Display name = the most-used raw spelling, so the label is the
                # one a reader is most likely to recognise. Alphabetical tiebreak
                # keeps rebuilds deterministic.
                family = sorted(spellings, key=lambda s: (-s[1], s[0]))[0][0]
                generic, is_cur = False, False
            for raw, n in spellings:
                records.append([raw, nkey, family, is_cur, generic, n])
                families[family] += n

        # Slugs last, over the FINAL family set, so numbering is stable.
        slugs = assign_slugs({r[2] for r in records})
        assert len(set(slugs.values())) == len(slugs), "slug collision survived"
        for r in records:
            r.append(slugs[r[2]])

        async with conn.transaction():
            for stmt in DDL.strip().split(";"):
                if stmt.strip():
                    await conn.execute(stmt)
            await conn.execute("TRUNCATE license_family")
            await conn.executemany(
                """INSERT INTO license_family
                   (product_raw, product_norm, family, curated, is_generic,
                    contracts, slug)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""", [tuple(r) for r in records])

        merged = sum(1 for k, v in by_norm.items() if len(v) > 1)
        print(f"license_family rebuilt: {len(records)} product spellings -> "
              f"{len(families)} families")
        print(f"  auto-merged by case/punctuation: {merged} normalized keys held "
              f">1 raw spelling")
        print(f"  curated rules applied: {len(matched_curated)} of {len(curated)}")
        print(f"  generic (unidentified, NOT a product): "
              f"{sum(1 for r in records if r[4])} spellings")
        dupes = len(slugs) - len(set(assign_slugs(set(slugs)).values()))
        print(f"  slugs: {len(set(slugs.values()))} unique for {len(slugs)} families"
              + (f" (⚠ {dupes} needed a numeric suffix)" if dupes else ""))

        # ⚠ A curated rule that matches nothing is silently dead weight -- the
        # product may have been renamed by a reclassification, or the rule may
        # have a typo. Report it; do not fail, because a rule can legitimately
        # pre-empt a product that is not in the data yet.
        stale = sorted(set(curated) - matched_curated)
        if stale:
            print(f"  ⚠ {len(stale)} curated rule(s) matched NO product "
                  f"(typo, or the product is gone):")
            for s in stale[:15]:
                print(f"      {s} -> {curated[s][0]}")

        top = ", ".join(f"{f} ({n})" for f, n in families.most_common(6))
        print(f"  largest families by contract count: {top}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
