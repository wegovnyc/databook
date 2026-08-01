"""Post-ingest hook: load the five PASSPort vendor sub-tables from S3.

The `vendors` table carries only what fits on one row per supplier — name, FMS
code, certification, corporate structure. MOCS publishes five companion exports
that PASSPort itself shows and Databook has never surfaced:

    vendor_principals        who runs the company (officers + principal owners)
    vendor_evaluations       MOCS agency performance ratings, per contract
    vendor_entity_summary    address, phone, for-profit, gross revenue, DUNS
    vendor_related_entities  parent / subsidiary / affiliate graph
    vendor_other_names       DBA / trade-name / abbreviation history

The DDL for these has sat in setup_oce_postgres.py since the original port with
its loader commented out, so the tables were never created. This module is the
loader, wired to the `vendors` daily ingest.

Join key
--------
The exports carry NO supplier id — they key on `Vendor Name`, free text with
inconsistent leading/trailing whitespace. But they come out of the same MOCS
system as vendor_data.csv, so the name is effectively a natural key: stripping
to [A-Za-z0-9] (the same normalization `oce.py::_sbs_profile` uses) matches
99.4-99.6% of principals / other_names / related_entities rows and 89% of
entity_summary. We store that key as `vendor_name_norm` and index it, so the
API joins on it directly instead of normalizing 36k names per request.

Measured 2026-07-27 against the live exports:

    table                rows     rows matching a PASSPort vendor
    entity_summary     38,543     34,300 (89.0%)  -> 94.4% of vendors covered
    principals         67,286     66,907 (99.4%)  -> 94.3% of vendors covered
    evaluations       145,940    116,186 (79.6%)  -> 13.5% of vendors covered
    other_names         5,549      5,524 (99.5%)  -> 10.5% of vendors covered
    related_entities   41,478     41,109 (99.1%)  -> 22.4% of vendors covered

evaluations matches fewest DISTINCT names (49%) because MOCS evaluates bodies
that are not PASSPort suppliers at all (NYCEDC, Con Edison, ...). Those rows
are loaded but simply never join — we do not try to invent a vendor for them.

Staleness
---------
⚠ vendor_data.csv is refreshed DAILY on S3, but these five exports are frozen
at 2026-02-03. We therefore record each file's Last-Modified in
`vendor_enrichment_meta` and surface it as an "as of" date, rather than letting
a page imply the ownership data is as fresh as the vendor list. The ETag is
stored too so the daily hook re-downloads ~85 MB only when a file actually
changes.
"""

import csv
import io
import os
import re
from datetime import datetime, timezone

import aiohttp
import asyncpg

# Credential resolution lives in one place — see modules/dbcreds.py.
try:
    import dbcreds
except ImportError:  # when imported as part of the modules package
    from modules import dbcreds


S3_BASE = os.environ.get(
    "PASSPORT_SUBTABLE_BASE",
    "https://databook2.s3.amazonaws.com/pre-processed",
)

# Rows per executemany batch. These files are small enough to stream whole
# (the largest is ~27 MB) but the api container is memory-capped at 3 GB and
# shares it with DuckDB, so we never hold more than a batch of tuples.
BATCH = 2000


def norm_name(value) -> str:
    """Strip a vendor name to its [A-Z0-9] skeleton — the cross-source join key.

    Identical to oce.py::_sbs_profile's normalization on purpose: one key shape
    for every name-matched vendor source. Suffixes (INC/LLC/CORP) are NOT
    stripped — tested both ways, and stripping them roughly doubles the number
    of distinct names colliding onto multiple supplier ids (70 -> 167) while
    adding no matches, because both sides come from the same MOCS export.
    """
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", value.upper())


# --- Table definitions -------------------------------------------------------
# Each entry: (table, s3 filename, DDL, [(csv header, column), ...]).
#
# ⚠ The CSV headers are reproduced EXACTLY as MOCS publishes them, including
# 'Address  Line 2' and 'Contract  ID' (double space) and 'To Date ' (trailing
# space). We match headers after stripping whitespace, so these are written
# here in tidy form and normalized on read — see _header_index.

_TABLES = [
    (
        "vendor_entity_summary",
        "passport_entity_summary.csv",
        """
        CREATE TABLE IF NOT EXISTS vendor_entity_summary (
            vendor_name      text,
            vendor_name_norm text,
            address1         text,
            address2         text,
            city             text,
            state            text,
            zip              text,
            country          text,
            telephone        text,
            symbol           text,
            for_profit       text,
            duns             text,
            revenue          text
        )
        """,
        [("Vendor Name", "vendor_name"),
         ("Address Line 1", "address1"),
         ("Address Line 2", "address2"),
         ("City", "city"),
         ("State", "state"),
         ("Zip Code", "zip"),
         ("Country", "country"),
         ("Telephone", "telephone"),
         ("Stock Exchange Symbol", "symbol"),
         ("For Profit", "for_profit"),
         ("DUNS number", "duns"),
         ("Gross Revenue", "revenue")],
    ),
    (
        "vendor_principals",
        "passport_principals.csv",
        """
        CREATE TABLE IF NOT EXISTS vendor_principals (
            vendor_name      text,
            vendor_name_norm text,
            principal_name   text,
            title            text,
            ownership_type   text
        )
        """,
        [("Vendor Name", "vendor_name"),
         ("Principal Name", "principal_name"),
         ("Current Title", "title"),
         ("Principal Ownership Type", "ownership_type")],
    ),
    (
        "vendor_evaluations",
        "passport_performance_evaluation.csv",
        """
        CREATE TABLE IF NOT EXISTS vendor_evaluations (
            vendor_name      text,
            vendor_name_norm text,
            agency           text,
            contract_id      text,
            contract_id_norm text,
            purpose          text,
            eval_date        text,
            start_date       text,
            end_date         text,
            rating           text
        )
        """,
        [("Vendor Name", "vendor_name"),
         ("Agency", "agency"),
         ("Contract ID", "contract_id"),
         ("Purpose", "purpose"),
         ("Evaluation Date", "eval_date"),
         ("Evaluation Period Start Date", "start_date"),
         ("Evaluation Period End Date", "end_date"),
         ("Overall Rating", "rating")],
    ),
    (
        "vendor_other_names",
        "passport_other_names.csv",
        """
        CREATE TABLE IF NOT EXISTS vendor_other_names (
            vendor_name      text,
            vendor_name_norm text,
            type             text,
            other_name       text,
            from_date        text,
            to_date          text
        )
        """,
        [("Vendor Name", "vendor_name"),
         ("Other Name Type", "type"),
         ("Other Name", "other_name"),
         ("From Date", "from_date"),
         ("To Date", "to_date")],
    ),
    (
        "vendor_related_entities",
        "passport_related_entities.csv",
        """
        CREATE TABLE IF NOT EXISTS vendor_related_entities (
            vendor_name         text,
            vendor_name_norm    text,
            related_entity_name text,
            address1            text,
            address2            text,
            city                text,
            state               text,
            zip                 text,
            country             text,
            telephone           text,
            relationship        text
        )
        """,
        [("Vendor Name", "vendor_name"),
         ("Related Entity Name", "related_entity_name"),
         ("Address Line 1", "address1"),
         ("Address Line 2", "address2"),
         ("City", "city"),
         ("State", "state"),
         ("Zip Code", "zip"),
         ("Country", "country"),
         ("Telephone", "telephone"),
         ("Relationship to Vendor", "relationship")],
    ),
]

_META_DDL = """
CREATE TABLE IF NOT EXISTS vendor_enrichment_meta (
    table_name    text PRIMARY KEY,
    source_file   text,
    etag          text,
    last_modified text,
    row_count     integer,
    refreshed_at  timestamptz DEFAULT now()
)
"""

# vendor_name_norm on every table; contract_id_norm additionally on evaluations
# (they carry a contract id at 100%, and 27.7% of our contracts have one).
_INDEXES = {
    t[0]: [(f"idx_{t[0]}_norm", "vendor_name_norm")] for t in _TABLES
}
_INDEXES["vendor_evaluations"].append(
    ("idx_vendor_evaluations_ctr", "contract_id_norm"))


def _header_index(header: list, wanted: list) -> dict:
    """Map our tidy header names to their column position in the CSV.

    Whitespace is collapsed on both sides so 'Contract  ID' (MOCS ships a
    double space) and 'To Date ' (trailing space) resolve to our tidy names.
    Returns {tidy name: index}; a header we asked for and did not find is
    simply absent, and its column loads as NULL rather than failing the run.
    """
    def key(s):
        return re.sub(r"\s+", " ", (s or "").strip().lstrip("﻿")).lower()

    pos = {key(h): i for i, h in enumerate(header)}
    return {w: pos[key(w)] for w in wanted if key(w) in pos}


async def _load_table(conn: asyncpg.Connection, session: aiohttp.ClientSession,
                      table: str, filename: str, ddl: str,
                      mapping: list) -> dict:
    """Download one export and replace `table` with it. Returns a status dict.

    Load is staged: we build `_staging_<table>`, fill it, and only then swap it
    over the live table inside a transaction. A truncate-then-fill would leave
    the vendor profile with no ownership panel for the duration of the load,
    and would lose the old data entirely if the download died halfway.
    """
    url = f"{S3_BASE}/{filename}"
    await conn.execute(ddl)

    prev = await conn.fetchrow(
        "SELECT etag, last_modified, row_count FROM vendor_enrichment_meta "
        "WHERE table_name = $1", table)

    # HEAD first: these five exports change a few times a year while this hook
    # runs daily, so re-downloading ~85 MB every night is pure waste.
    etag = last_modified = None
    try:
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status == 200:
                etag = r.headers.get("ETag")
                last_modified = r.headers.get("Last-Modified")
    except Exception:
        pass  # HEAD is an optimization only — fall through to a full load.

    # Prefer the ETag (S3 always sends one); fall back to Last-Modified so the
    # skip still works against a plain file server. If neither is available we
    # reload — better to spend the bandwidth than to serve stale ownership data.
    live = await conn.fetchval(f"SELECT count(*) FROM {table}")
    if live > 0 and prev:
        if (etag and prev["etag"] == etag) or \
           (not etag and last_modified and prev["last_modified"] == last_modified):
            return {"status": "unchanged", "rows": live,
                    "last_modified": prev["last_modified"]}

    staging = f"_staging_{table}"
    await conn.execute(f"DROP TABLE IF EXISTS {staging}")
    await conn.execute(ddl.replace(
        f"CREATE TABLE IF NOT EXISTS {table}",
        f"CREATE TABLE {staging}", 1))

    headers = [h for h, _ in mapping]
    columns = [c for _, c in mapping]
    # vendor_name_norm is derived here, not in SQL, so the join key is written
    # by exactly one function (norm_name) shared with the API's lookup path.
    insert_cols = columns + ["vendor_name_norm"]
    if table == "vendor_evaluations":
        insert_cols.append("contract_id_norm")

    total = 0
    timeout = aiohttp.ClientTimeout(total=1800, sock_read=300)
    async with session.get(url, timeout=timeout) as resp:
        if resp.status != 200:
            await conn.execute(f"DROP TABLE IF EXISTS {staging}")
            return {"status": "fail", "error": f"HTTP {resp.status}"}

        body = (await resp.read()).decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(body))
        try:
            header = next(reader)
        except StopIteration:
            await conn.execute(f"DROP TABLE IF EXISTS {staging}")
            return {"status": "fail", "error": "empty file"}

        idx = _header_index(header, headers)
        missing = [h for h in headers if h not in idx]
        if "Vendor Name" in missing:
            await conn.execute(f"DROP TABLE IF EXISTS {staging}")
            return {"status": "fail",
                    "error": f"no Vendor Name column in {header[:6]}"}

        batch = []
        for row in reader:
            vals = []
            for h in headers:
                i = idx.get(h)
                v = row[i].strip() if (i is not None and i < len(row)) else None
                vals.append(v or None)
            name = vals[headers.index("Vendor Name")]
            vals.append(norm_name(name) or None)
            if table == "vendor_evaluations":
                cid = vals[headers.index("Contract ID")]
                vals.append(re.sub(r"[^A-Za-z0-9]", "", cid.upper()) if cid else None)
            batch.append(tuple(vals))

            if len(batch) >= BATCH:
                await conn.copy_records_to_table(
                    staging, records=batch, columns=insert_cols)
                total += len(batch)
                batch = []

        if batch:
            await conn.copy_records_to_table(
                staging, records=batch, columns=insert_cols)
            total += len(batch)

    if total == 0:
        await conn.execute(f"DROP TABLE IF EXISTS {staging}")
        return {"status": "fail", "error": "parsed 0 rows"}

    # Data-safety guard, same spirit as the lake refreshes: a source that
    # suddenly halves is far more likely to be a broken export than real news.
    if live > 0 and total < live * 0.5:
        await conn.execute(f"DROP TABLE IF EXISTS {staging}")
        return {"status": "fail",
                "error": f"refusing swap: {total} rows vs {live} live (>50% drop)"}

    async with conn.transaction():
        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        await conn.execute(f"ALTER TABLE {staging} RENAME TO {table}")
        for idx_name, col in _INDEXES.get(table, []):
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({col})")
        await conn.execute(
            """INSERT INTO vendor_enrichment_meta
                   (table_name, source_file, etag, last_modified, row_count, refreshed_at)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (table_name) DO UPDATE SET
                   source_file = EXCLUDED.source_file,
                   etag = EXCLUDED.etag,
                   last_modified = EXCLUDED.last_modified,
                   row_count = EXCLUDED.row_count,
                   refreshed_at = EXCLUDED.refreshed_at""",
            table, filename, etag, last_modified, total,
            datetime.now(timezone.utc))
    await conn.execute(f"ANALYZE {table}")

    return {"status": "success", "rows": total, "last_modified": last_modified}


async def derive_vendor_enrichment_hook(conn: asyncpg.Connection):
    """Load the five PASSPort vendor sub-tables. Registered on `vendors`.

    Each table is independent: one failing export (bad HTTP, changed header)
    leaves the other four loaded and the previous copy of the failed one in
    place. A vendor profile must never 500 because an enrichment source moved.
    """
    await conn.execute(_META_DDL)
    async with aiohttp.ClientSession() as session:
        for table, filename, ddl, mapping in _TABLES:
            try:
                r = await _load_table(conn, session, table, filename, ddl, mapping)
            except Exception as e:  # noqa: BLE001 — never break the vendors ingest
                print(f"[enrich_vendor] ✗ {table} failed: {e}")
                continue
            if r["status"] == "success":
                print(f"[enrich_vendor] ✓ {table}: {r['rows']} rows "
                      f"(source {r.get('last_modified') or 'unknown'})")
            elif r["status"] == "unchanged":
                print(f"[enrich_vendor] · {table}: unchanged, {r['rows']} rows")
            else:
                print(f"[enrich_vendor] ✗ {table}: {r.get('error')}")


if __name__ == "__main__":
    # Manual / first run, from the api container:
    #   docker compose exec -T api python enrich_vendor.py
    # The daily `vendors` ingest calls derive_vendor_enrichment_hook itself, so
    # this entrypoint is only needed to load the tables ahead of that cycle.
    import asyncio

    async def _main():
        conn = await asyncpg.connect(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=dbcreds.password(),
            database=os.environ.get("POSTGRES_DB", "databook"),
        )
        try:
            await derive_vendor_enrichment_hook(conn)
        finally:
            await conn.close()

    asyncio.run(_main())
