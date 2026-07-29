"""Build the PASSPort vendor -> NY DOS legal-entity crosswalk.

The NY Department of State corporate registry (`ny_active_corporations`,
2,097,741 rows) is already on this box, inside the **nycdb** service's DuckDB
file. It has been used only for landlord/building enrichment; nothing has ever
joined it to vendors. It answers questions no procurement source can:

    entity_type              LLC / business corp / not-for-profit / professional
    initial_dos_filing_date  => how OLD the business actually is
    county, jurisdiction     where it is registered, domestic vs foreign
    registered_agent_name    who accepts service of process
    dos_process_*            the service-of-process address

Why a batch job and not a request-time join
-------------------------------------------
Cross-store: the registry is a 9.1 GB DuckDB file owned by `nycdb-api`, while
`vendors` is Postgres inside the databook stack, and the databook api container
does not (and should not) mount 9 GB of someone else's database. So this
resolves the join OFFLINE and materializes a compact
`dos_entity_enrichment` table (~15.6k rows) that the API reads from Postgres
like any other enrichment. DuckDB is opened READ-ONLY, which is safe to run
concurrently with nycdb-api (verified).

Run it in an isolated container — the api image already has duckdb + asyncpg:

    docker run --rm -m 4g --network databook_databook-network \
      -v /opt/nycdb/db:/nycdb:ro -w /app \
      -e POSTGRES_HOST -e POSTGRES_USER -e POSTGRES_PASSWORD -e POSTGRES_DB \
      databook-api python build_dos_crosswalk.py

(pass the POSTGRES_* values through from the environment rather than typing
them on the command line; scripts/dos-crosswalk-refresh.sh reads them from the
running api container.)

Cadence: nycdb refreshes the registry monthly (cron, 1st at 08:30 UTC), so this
is scheduled just after it. It is NOT a post-ingest hook on `vendors`, because
the api container cannot reach the DuckDB file.

Matching
--------
The registry ships a pre-computed `entity_name_norm`, built by nycdb's
persisted `norm_name()` DuckDB macro, so the join must use that same macro on
the vendor side. Measured 2026-07-27: **15,618 of 36,335 vendors (43%)** match
unambiguously.

⚠ `norm_name()` is nycdb's ADDRESS normalizer, not a company-name one: it
expands single letters and street words, so `ADAM'S EUROPEAN CONTRACTING` comes
out as `ADAM SOUTH EUROPEAN CONTRACTING` (the "'S" becomes "SOUTH"). That is
tolerable here only because it is applied symmetrically to both sides, so the
distortion cancels. It was checked rather than assumed: of the 15,618 matches,
**14,936 (95.6%) are byte-identical** after plain [A-Z0-9] normalization, and
every one of the lowest-similarity pairs is a legitimate INC/INCORPORATED or
CORP/CORPORATION variant that the macro correctly canonicalises. The rare
collision risk it introduces (a standalone "S" colliding with "SOUTH") is
covered by the ambiguity rule below.

⚠ **Vendors matching more than one DOS entity are skipped, not guessed** (5 of
them, typically a domestic and a foreign registration of the same trade name).
They are recorded with confidence 'ambiguous' and a NULL dos_id so they can be
curated later and never silently show the wrong company's incorporation date.

Three limits worth stating in the UI
------------------------------------
1. The nycdb table is filtered to the **five NYC counties** at load, so a
   perfectly legitimate out-of-state vendor simply will not match.
2. It is **ACTIVE-only** — dissolved entities are absent (dataset 63wc-4exh
   carries full filing/status history if that ever matters).
3. `registered_agent_name` is 19.6% populated and `ceo_name` only 10.8%, so
   those are rendered only when present.

Do NOT reintroduce OpenCorporates for this: it resells the same NY DOS data we
already hold, and its token is committed in the legacy `oce` repo.
"""

import asyncio
import os
import re
from datetime import datetime, timezone

import asyncpg
import duckdb

NYCDB_PATH = os.environ.get("NYCDB_PATH", "/nycdb/nycdb.duckdb")

_DDL = """
CREATE TABLE IF NOT EXISTS dos_entity_enrichment (
    passport_supplier_id text PRIMARY KEY,
    vendor_name          text,
    dos_id               text,
    entity_name          text,
    entity_type          text,
    jurisdiction         text,
    county               text,
    initial_filing_date  date,
    registered_agent     text,
    process_name         text,
    process_address      text,
    match_key            text,
    confidence           text,
    source               text DEFAULT 'ny_dos_active_corporations',
    derived_at           timestamptz DEFAULT now(),
    curated              boolean DEFAULT false,
    curated_note         text
)
"""


def parse_filing_date(value):
    """'03/11/2020' -> date(2020, 3, 11); None when unusable.

    The registry stores dates as MM/DD/YYYY text spanning 01/01/1806 to
    12/31/2025. Parsed here so the API can compute a business age without
    re-parsing per request, and so a malformed value fails at build time
    rather than rendering as a bogus year.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        d = datetime.strptime(value.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None
    # The registry's own range; anything outside it is corrupt, not historic.
    if not (1800 <= d.year <= datetime.now(timezone.utc).year + 1):
        return None
    return d


def _address(*parts) -> str:
    """Join address fragments, collapsing the source's stray double spaces."""
    joined = ", ".join(p.strip() for p in parts if p and p.strip())
    return re.sub(r"\s{2,}", " ", joined)


async def main():
    con = duckdb.connect(NYCDB_PATH, read_only=True)

    pg = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        database=os.environ.get("POSTGRES_DB", "databook"),
    )
    try:
        await pg.execute(_DDL)
        vendors = await pg.fetch(
            'SELECT "PASSPort Supplier-ID" AS id, "Vendor Name" AS n FROM vendors '
            'WHERE "Vendor Name" IS NOT NULL AND "Vendor Name" <> \'\'')
        print(f"[dos] {len(vendors)} vendors to match")

        con.execute("CREATE TEMP TABLE v(id VARCHAR, name VARCHAR)")
        con.executemany("INSERT INTO v VALUES (?, ?)",
                        [(r["id"], r["n"]) for r in vendors])

        # QUALIFY keeps only vendors resolving to exactly ONE registry entity;
        # the ambiguous ones are collected separately below rather than picked
        # arbitrarily. norm_name() is nycdb's macro — see the module docstring.
        rows = con.execute("""
            SELECT v.id, v.name, d.dos_id, d.current_entity_name, d.entity_type,
                   d.jurisdiction, d.county, d.initial_dos_filing_date,
                   d.registered_agent_name, d.dos_process_name,
                   d.dos_process_address_1, d.dos_process_city,
                   d.dos_process_state, d.dos_process_zip,
                   norm_name(v.name) AS k
            FROM v
            JOIN ny_active_corporations d ON d.entity_name_norm = norm_name(v.name)
            QUALIFY count(*) OVER (PARTITION BY v.id) = 1
        """).fetchall()

        ambiguous = con.execute("""
            SELECT v.id, v.name, norm_name(v.name) AS k, count(*) AS n
            FROM v
            JOIN ny_active_corporations d ON d.entity_name_norm = norm_name(v.name)
            GROUP BY 1, 2, 3 HAVING count(*) > 1
        """).fetchall()

        records = []
        undated = 0
        for (vid, vname, dos_id, ename, etype, juris, county, filed,
             agent, pname, a1, city, state, zipc, key) in rows:
            d = parse_filing_date(filed)
            if filed and d is None:
                undated += 1
            records.append((
                vid, vname, dos_id, ename, etype, juris, county, d,
                (agent or "").strip() or None,
                (pname or "").strip() or None,
                _address(a1, city, state, zipc) or None,
                key, "exact-norm"))
        for vid, vname, key, n in ambiguous:
            # Recorded so the ambiguity is visible and curatable — never linked.
            records.append((vid, vname, None, None, None, None, None, None,
                            None, None, None, key, "ambiguous"))

        # Rebuild from scratch except curated rows: an upsert-only generator
        # silently preserves corrected false positives (the #149 lesson).
        async with pg.transaction():
            await pg.execute("DELETE FROM dos_entity_enrichment WHERE curated = false")
            await pg.executemany("""
                INSERT INTO dos_entity_enrichment
                    (passport_supplier_id, vendor_name, dos_id, entity_name,
                     entity_type, jurisdiction, county, initial_filing_date,
                     registered_agent, process_name, process_address,
                     match_key, confidence, derived_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13, now())
                ON CONFLICT (passport_supplier_id) DO NOTHING
            """, records)
        await pg.execute(
            "CREATE INDEX IF NOT EXISTS idx_dos_enrichment_conf "
            "ON dos_entity_enrichment(confidence)")
        await pg.execute("ANALYZE dos_entity_enrichment")

        linked = await pg.fetchval(
            "SELECT count(*) FROM dos_entity_enrichment WHERE dos_id IS NOT NULL")
        total = await pg.fetchval("SELECT count(*) FROM dos_entity_enrichment")
        print(f"[dos] ✓ {linked} linked / {total} rows "
              f"({len(ambiguous)} ambiguous, skipped; {undated} unparseable dates)")
        if vendors:
            print(f"[dos]   coverage: {100 * linked / len(vendors):.1f}% of vendors")
    finally:
        await pg.close()
        con.close()


if __name__ == "__main__":
    asyncio.run(main())
