"""Build the licence-product <-> City Record notice crosswalk.

    docker compose exec -T api python build_notice_product_links.py            # REPORT
    docker compose exec -T api python build_notice_product_links.py --apply    # write

Which City Record notices name a product the City licenses. Feeds the "City
Record notices mentioning this product" panel on each licence family page.

Why a batch job rather than a live join
---------------------------------------
Ranking is what makes notice-body search expensive, not matching. GIN cannot
return ordered results, so `ORDER BY rank LIMIT 8` cannot stop early — Postgres
fetches every matching row to sort it. Measured on prod: the term "construction"
goes from 150ms/7,893 rows (title only, today) to 831ms/15,321 rows once bodies
are searchable, and that is a LOWER bound. Computed offline none of that exists:
the whole batch is 0.79s and the request path does no ranking at all.

The yield is the other half of the argument, and it is why this is a PANEL and
not a search feature. Across all 1,101,601 notices the City's TOP licence
families appear in single digits to low double digits — Salesforce 24, DocuSign
18, LexisNexis 14, Citrix 12, ArcGIS 10, Elasticsearch 7, SolarWinds 5 — with
Microsoft the lone outlier at 1,219. The City Record publishes PROCEDURAL
notices (solicitations, awards, hearings) whose bodies describe process, not
product. Final measured result: 3,777 links across 430 families, and the great
majority of those families land under 10 notices.

⚠ SO THIS IS NOT EVIDENCE OF PROCUREMENT ACTIVITY. A notice naming a product is
not a notice ABOUT that product. The EPIN crosswalk (oce._notices_for_epins) is
the accurate id-based link and is a different panel. The page must say so.

Matching
--------
`to_tsvector('simple', body) @@ phraseto_tsquery('simple', family)`, against
`idx_crol_body_fts`.

⚠⚠ `simple`, NOT `english`, and this is the single most important line here. The
English snowball stemmer collapses BRAND NAMES onto ordinary stems, so a
perfectly distinctive product name can match notices that never contain it:
`Feedly` stems to 'feed' and matched 121 notices about data FEEDS; `Mobilize`
stems to 'mobil' and matched 2,388 notices, almost all of them saying "mobile".
Measured on prod, english -> simple: Feedly 121 -> 0, Mobilize 2,388 -> 11,
Reflections 349 -> 2, Precisely 58 -> 10 — while genuinely distinctive names do
not move at all (Oracle 363 -> 363, Gartner 48 -> 48, DocuSign 18 -> 18).
Stemming is right for prose search and wrong for proper nouns. The index and the
query must use the SAME configuration or the index cannot serve the query; a
guard pins that.

⭐ FTS TOKENISATION GIVES WORD BOUNDARIES FOR FREE, which is what makes this
safe without a regex. `Quest` as a naive substring matches 21,702 notices,
because "re-QUEST" contains it and City Record notices are made of that word.
Measured three ways: naive ILIKE 21,702 / word-bounded regex 30 /
phraseto_tsquery 29. Same for SAS (1,469 / 27 / 27).

⚠ IT DOES NOT FIX EVERYTHING, and the residue is why the seed exists. `Box`
goes 2,831 -> 2,479 -> 2,068 and `Zoom` 1,563 -> 1,557 -> 1,429, because "P.O.
Box" and "join via Zoom" are SEMANTIC failures. No matcher fixes those.

Two eligibility rules, both deliberately visible in the run output
------------------------------------------------------------------
1. `api/seed/license_family_notice_exclusions.csv` — a curated list, never a
   threshold. No hit count separates Microsoft's legitimate 1,219 from
   Streetscape's 139 of pure noise, so a ceiling would drop the first and keep
   the second.
2. MIN_NAME_LEN — names shorter than this carry too little information to be
   distinctive. ⚠ This IS a threshold, so it is named, explained, and the run
   REPORTS how many families it skipped, rather than silently shrinking the
   catalogue. Every short name actually measured (Box 3, Zoom 4, SAS 3) was
   noise; the other ~36 are unmeasured, which is the honest reason to skip them.

⚠ `license_family.is_generic` does NOT do this job — it is true for 16 rows and
was built for another purpose. Do not lean on it.
"""
import argparse
import asyncio
import csv
import io
import os

import asyncpg

try:
    from modules import dbcreds
except ImportError:  # pragma: no cover - path differs between run styles
    import dbcreds

# Below this, a family name is not distinctive enough to match on. Reported.
MIN_NAME_LEN = 5
# Never matched: the catalogue's own "we could not identify this" bucket.
UNIDENTIFIED = "(unidentified)"
# Refuse to publish a rebuild that loses more than this share of the links.
MAX_DROP = 0.50

# ⚠ ONE column list, used for the real table AND the staging table. The staging
# DDL used to be `LIKE notice_product_links`, which quietly made a DRY RUN depend
# on the real table existing — so the dry run had to create it, and "dry" wrote.
COLUMNS = """
    family      text NOT NULL,
    request_id  text NOT NULL,
    title       text,
    agency      text,
    notice_type text,
    start_date  date,
    built_at    timestamptz NOT NULL DEFAULT now()
"""

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS notice_product_links ({COLUMNS},
    PRIMARY KEY (family, request_id)
);
CREATE INDEX IF NOT EXISTS idx_npl_family ON notice_product_links (family);
"""


def _seed_path(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed", name)


def load_exclusions():
    """Families excluded from notice matching. Comment lines start with '#'.

    ⚠ Returns the reasons too, so a caller can print WHY a family is absent. An
    exclusion with no stated reason is indistinguishable from a typo.
    """
    path = _seed_path("license_family_notice_exclusions.csv")
    out = {}
    try:
        with io.open(path, encoding="utf-8") as fh:
            for row in csv.DictReader(l for l in fh if not l.startswith("#")):
                fam = (row.get("family") or "").strip()
                reason = (row.get("reason") or "").strip()
                if fam:
                    out[fam] = reason
    except FileNotFoundError:
        # Degrade loudly rather than silently matching everything: an absent
        # seed must not quietly publish Streetscape's 144 false notices.
        print("[notice-links] ⚠ exclusion seed MISSING — refusing to match")
        return None
    return out


async def eligible_families(conn, exclusions):
    """The families we will match on, plus the two skip counts, measured."""
    rows = await conn.fetch(
        "SELECT DISTINCT family FROM license_family WHERE family <> '' ")
    all_fams = sorted({r["family"] for r in rows if r["family"]})
    too_short = [f for f in all_fams if len(f) < MIN_NAME_LEN]
    excluded = [f for f in all_fams if f in exclusions]
    keep = [f for f in all_fams
            if len(f) >= MIN_NAME_LEN and f not in exclusions and f != UNIDENTIFIED]
    return all_fams, keep, too_short, excluded


async def unqueryable(conn, families):
    """Families whose name produces an EMPTY tsquery, so they can never match.

    ⚠ This exists because an unmatchable family and a family with no notices are
    byte-identical downstream — both render an absent panel. Counting them is the
    difference between "nobody mentions ArcGIS" and "we never asked".
    """
    if not families:
        return []
    rows = await conn.fetch(
        "SELECT f AS family FROM unnest($1::text[]) f "
        "WHERE phraseto_tsquery('simple', f) = ''::tsquery", families)
    return [r["family"] for r in rows]


async def build(conn, families, apply: bool):
    """Match and (optionally) swap. Returns (pairs, families_hit)."""
    await conn.execute("DROP TABLE IF EXISTS _staging_notice_product_links")
    await conn.execute(
        f"CREATE TABLE _staging_notice_product_links ({COLUMNS})")
    # ⚠ The tsvector expression must be textually what searchindexes.py declares,
    # or the planner cannot use idx_crol_body_fts and this becomes 774 sequential
    # scans of a 464 MB heap.
    await conn.execute(
        """
        INSERT INTO _staging_notice_product_links
              (family, request_id, title, agency, notice_type, start_date)
        SELECT f.family, c."RequestID", c."ShortTitle", c."AgencyName",
               c."TypeOfNoticeDescription", c.start_date_parsed
        FROM unnest($1::text[]) AS f(family)
        JOIN crol c
          ON to_tsvector('simple', coalesce(c."AdditionalDescription1", ''))
             @@ phraseto_tsquery('simple', f.family)
        ON CONFLICT DO NOTHING
        """,
        families,
    )
    pairs = await conn.fetchval("SELECT count(*) FROM _staging_notice_product_links")
    fams_hit = await conn.fetchval(
        "SELECT count(DISTINCT family) FROM _staging_notice_product_links")

    if not apply:
        await conn.execute("DROP TABLE IF EXISTS _staging_notice_product_links")
        return pairs, fams_hit

    previous = await conn.fetchval(
        "SELECT count(*) FROM notice_product_links "
        "WHERE to_regclass('public.notice_product_links') IS NOT NULL")
    # ⚠ Guard the SWAP, not the build. A truncated crol ingest or a half-loaded
    # catalogue would otherwise empty this panel across every family page at once,
    # and an empty panel reads exactly like "this product is in no notices".
    if previous and pairs < previous * (1 - MAX_DROP):
        await conn.execute("DROP TABLE IF EXISTS _staging_notice_product_links")
        raise RuntimeError(
            f"refusing swap: {pairs} links vs {previous} previously "
            f"(>{int(MAX_DROP * 100)}% drop)")

    async with conn.transaction():
        await conn.execute("DROP TABLE IF EXISTS notice_product_links")
        await conn.execute(
            "ALTER TABLE _staging_notice_product_links "
            "RENAME TO notice_product_links")
        await conn.execute(
            "ALTER TABLE notice_product_links "
            "ADD PRIMARY KEY (family, request_id)")
        await conn.execute(
            "CREATE INDEX idx_npl_family ON notice_product_links (family)")
    return pairs, fams_hit


async def run(conn, apply: bool, verbose: bool = True):
    exclusions = load_exclusions()
    if exclusions is None:
        return None
    # ⚠ Only when applying. A dry run must not create the table it is pretending
    # to write — `--apply` is the only mode that touches anything durable.
    if apply:
        for stmt in [x.strip() for x in SCHEMA.split(";") if x.strip()]:
            await conn.execute(stmt)

    all_fams, keep, too_short, excluded = await eligible_families(conn, exclusions)

    # ⚠ A RUN THAT CONSIDERED NOTHING MUST NOT LOOK LIKE A RUN THAT FOUND NOTHING.
    # This is the permanently-red-monitor / zero-files-scanned class: the
    # classifier that printed "Done. 0 classified" and exited 0 is the same bug.
    if len(all_fams) < 700:
        raise RuntimeError(
            f"only {len(all_fams)} families in license_family — catalogue looks "
            "unbuilt; refusing to rebuild the notice crosswalk from it")

    dead = await unqueryable(conn, keep)
    if dead:
        keep = [f for f in keep if f not in set(dead)]

    pairs, fams_hit = await build(conn, keep, apply)

    if verbose:
        print(f"[notice-links] catalogue: {len(all_fams)} families")
        print(f"[notice-links]   skipped, shorter than {MIN_NAME_LEN} chars: "
              f"{len(too_short)}")
        print(f"[notice-links]   skipped, curated exclusions: {len(excluded)}")
        if dead:
            print(f"[notice-links]   skipped, name yields an empty tsquery: "
                  f"{len(dead)} -> {', '.join(dead)}")
        print(f"[notice-links]   matched on: {len(keep)}")
        print(f"[notice-links] result: {pairs} links across {fams_hit} families")
        if excluded:
            print("[notice-links] excluded families and why:")
            for f in excluded:
                print(f"    {f:<28} {exclusions[f]}")
    return pairs, fams_hit


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the table (default is a dry run)")
    args = ap.parse_args()
    conn = await asyncpg.connect(**dbcreds.settings({}))
    try:
        print(f"[notice-links] mode: "
              f"{'APPLY' if args.apply else 'REPORT (pass --apply)'}\n")
        await run(conn, args.apply)
        if not args.apply:
            print("\n[notice-links] nothing written. Re-run with --apply.")
    finally:
        await conn.close()


async def derive_notice_product_links_hook(conn):
    """Rebuild the crosswalk after a `crol` ingest.

    Registered on `crol` in data_scheduler.POST_INGEST_HOOKS. ⚠ APPENDED, not
    inserted at 0: the index hook must run FIRST so this matches against
    idx_crol_body_fts rather than seq-scanning a 464 MB heap 774 times. That is
    the opposite of the `vendors` registration, where the index goes first for
    the same reason but the enrichment hooks were already in the dict.

    ⚠ It depends on TWO tables with different cadences. `crol` reloads on source
    change (observed lagging up to 5 days — NOT daily); `license_family` is
    rebuilt monthly by license-analysis-refresh.sh. Registering on crol is right
    because crol is the side that moves, but a family added by the monthly run
    gets no notices until the next crol ingest. `built_at` carries that vintage
    rather than a second trigger racing this one.

    ⚠ Guarded: this is additive enrichment, so a failure logs and returns rather
    than failing the ingest that triggered it.
    """
    try:
        await run(conn, apply=True, verbose=False)
        n = await conn.fetchval("SELECT count(*) FROM notice_product_links")
        f = await conn.fetchval(
            "SELECT count(DISTINCT family) FROM notice_product_links")
        print(f"[notice-links] rebuilt: {n} links across {f} families")
    except Exception as exc:  # noqa: BLE001
        print(f"[notice-links] hook failed (non-fatal): {exc}")


if __name__ == "__main__":
    asyncio.run(main())
