"""
Databook Data Scheduler — Automated dataset freshness checking and ingestion.

Runs as a background async task within the Databook2 API. On each daily cycle:
1. Polls Socrata metadata API for change detection on SODA datasets
2. Triggers extractors for non-Socrata datasets (Checkbook, PASSPort)
3. Downloads/imports data using full-replace or incremental-append mode
4. Scans for unmapped entities and sends alert emails
"""

import asyncio
import csv
import json
import io
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import asyncpg

from config import Config

# ⚠ getLogger ONLY — never basicConfig here. modules/applog.py owns the api's
# logging configuration, and a second config in a module the api imports would
# double every line in prod (#249). This module is not under `routers.*` or
# `modules.*`, so it inherits root at WARNING: logger.warning and logger.error
# are emitted (and .error becomes a Sentry event via LoggingIntegration's
# EventHandler), while logger.info would be dropped — so nothing here uses info.
logger = logging.getLogger(__name__)
from generate_dashboard import generate as generate_titles_dashboard

try:
    import orgfilter
except ImportError:
    from modules import orgfilter
# ⚠ ONE owner for the GIN/global-search declarations, shared with main.py's
# /import-csv path — see the module docstring for why two copies existed and what
# that cost.
# ⚠⚠ THE SAME try/except AS orgfilter ABOVE, AND IT IS LOAD-BEARING, NOT STYLE.
# `conftest.py` replaces the whole `modules` package with a MagicMock, whose
# `tables()` returns a mock that `sorted()` reads as EMPTY — so `from modules
# import searchindexes` alone made the hook-registration loop below register
# NOTHING under test, silently. Two guards caught it; the direct import keeps the
# real module in both environments.
try:
    import searchindexes
except ImportError:
    from modules import searchindexes
from enrich_geo_json import enrich_geo_json_hook
from enrich_fire_data import (
    enrich_fire_causes_hook,
    enrich_inspections_hook,
    enrich_violations_hook,
    enrich_dispatch_hook,
)
from enrich_agency import derive_agency_enrichment_hook
from enrich_vendor import derive_vendor_enrichment_hook
from enrich_doing_business import derive_doing_business_hook
from build_org_vendor_crosswalk import derive_org_vendor_hook
from build_notice_product_links import derive_notice_product_links_hook
from modules.errfmt import exc_str

# Credential resolution lives in one place — see modules/dbcreds.py.
try:
    import dbcreds
except ImportError:  # when imported as part of the modules package
    from modules import dbcreds



def dedupe_columns(columns: list) -> list:
    """Return column names with duplicates suffixed (_1, _2, ...).

    Why: some source CSVs repeat a header name — e.g. mocs-contracts.csv
    carries "wegov-org-name"/"wegov-org-id" twice from a double-enriched
    upstream export. A raw CREATE TABLE built from such a header raises
    Postgres `column "x" specified more than once`. Mirrors the dedupe
    already used by full_replace_import() and the /import-csv endpoint so
    every import path is consistent.
    """
    seen: dict = {}
    clean: list = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            clean.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            clean.append(col)
    return clean


def conform_row(row: list, ncols: int):
    """Coerce a CSV row to exactly ncols fields, or None to skip it.

    Why: some source CSVs are ragged — e.g. mocs-contracts.csv declares a
    26-column header (two spurious trailing wegov-org-* duplicates) but its
    data rows carry only 24 fields. The old strict `len(row) != ncols`
    skip then dropped every row, yielding a bogus "Empty CSV". Padding short
    rows with '' and truncating long ones keeps the data aligned to the
    leading columns (the real schema) instead of losing it. Returns None for
    genuinely blank lines so they aren't inserted.
    """
    if not row:
        return None
    if len(row) < ncols:
        return tuple(row) + ('',) * (ncols - len(row))
    if len(row) > ncols:
        return tuple(row[:ncols])
    return tuple(row)


# =============================================================================
# Constants
# =============================================================================

SOCRATA_BASE = "https://data.cityofnewyork.us"
SOCRATA_META_URL = f"{SOCRATA_BASE}/api/views/{{socrata_id}}.json"
SOCRATA_RESOURCE_URL = f"{SOCRATA_BASE}/resource/{{socrata_id}}.csv"

# Run cycle: 24 hours
SCHEDULER_INTERVAL_SECONDS = 86400
# ⚠ A CYCLE THAT DIES OUTRIGHT USED TO COST A FULL DAY. Every dataset inside
# `run_data_check` is already individually guarded, so the only way to reach the
# loop's own handler is a failure OUTSIDE those guards — in practice the
# `get_db_connection()` at the top of the cycle. Measured on prod 2026-08-18: an
# asyncpg connect TimeoutError under crawler-induced executor starvation (DuckDB
# Parquet scans share the default executor with getaddrinfo) killed the cycle
# before a single dataset was polled, and the loop then slept 86400s. That is a
# routine trigger — ~190 such timeouts per 24h are documented — so a short retry
# is worth far more than it costs.
#
# Deliberately NOT classifying transient-vs-permanent: that judgement is the trap
# (cf. api_exec deciding infra-vs-logic by probing health). A genuine logic error
# simply fails every attempt and costs SCHEDULER_MAX_RETRIES * the delay before
# alerting — a few minutes — which is a price worth paying to avoid guessing.
SCHEDULER_RETRY_DELAY_SECONDS = 120
SCHEDULER_MAX_RETRIES = 3


# =============================================================================
# Dead-man's switch for the scheduler loop
# =============================================================================
# ⚠⚠ WHAT A GREEN CHECK HERE DOES AND DOES NOT MEAN. It means the LOOP RAN a
# cycle to completion. It does NOT mean the data is fresh: individual datasets are
# guarded inside `run_data_check`, so a cycle can complete with several of them
# failing and still ping success. Dataset freshness is `scripts/dataset-staleness.sh`
# (daily) and `dataset_registry.last_error`. Conflating the two would be a green
# monitor that means less than it looks like — the permanently-red monitor's
# cousin, and the more dangerous of the pair.
#
# This exists because NOTHING watched this loop. All 8 healthchecks checks watch
# HOST crons; this runs inside the api process, and the failure line was a bare
# `print` invisible to Sentry. On 2026-08-18 the loop died at 14:15 and the only
# thing that would ever have noticed was dataset-staleness.sh, up to 5 days later
# and only if a source moved.
#
# ⚠ Read from the environment AT PING TIME, not at import: the value arrives from
# the box's gitignored `.env` via compose, so it is baked at container CREATE.
# Changing it needs a recreate, not a restart — the documented trap.
_HC_ENV_VAR = "HC_URL_API_SCHEDULER"


async def _hc_ping(kind: str, body: str = "") -> None:
    """Ping the healthchecks.io check for this loop. No-op when unconfigured.

    ⚠ NO-OP WHEN UNSET IS LOAD-BEARING, and it is what makes the rollout safe:
    the code ships first and does nothing, then the check is created, then the env
    var is set. Creating a check before anything can ping it manufactures a red
    monitor on its first missed schedule — that is why the DOS crosswalk check and
    its `hc_ping` had to ship together.

    ⚠ Never raises. A monitoring call that can break the thing it monitors is
    worse than no monitoring.
    """
    url = (os.environ.get(_HC_ENV_VAR) or "").strip()
    if not url:
        return
    if kind == "start":
        url = f"{url}/start"
    elif kind == "fail":
        url = f"{url}/fail"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # healthchecks RETAINS the body, so the alert email carries the
            # reason instead of just "went down".
            await session.post(url, data=(body or "")[:10000])
    except Exception as exc:  # noqa: BLE001 — monitoring must never be fatal
        logger.warning("[scheduler] healthchecks ping (%s) failed: %s",
                       kind, exc_str(exc))

# Normalizer API (Python/FastAPI on Lightsail)
NORMALIZER_BASE_URL = os.environ.get(
    "NORMALIZER_BASE_URL",
    "https://normalize.databook.nyc"
)
# Timeout for normalizer processing — streaming makes two passes over the
# CSV, and a single-worker normalizer queues concurrent requests.
NORMALIZER_TIMEOUT_SECONDS = int(os.environ.get("NORMALIZER_TIMEOUT", "1800"))

# Alert sender (uses al@sarapis.org integration)
ALERT_FROM = os.environ.get("PIPELINE_ALERT_FROM", "al@sarapis.org")
ALERT_TO = os.environ.get("PIPELINE_ALERT_TO", "devinbalkind@gmail.com")


# =============================================================================
# Post-Ingest Hooks
# =============================================================================
# Maps table names to async callables that should run after successful ingestion.
# Why: Derived analytics (dashboard_data.json, aggregation tables, etc.) must
# be rebuilt when their source datasets are updated.

POST_INGEST_HOOKS = {
    "nyccivilservicetitles": [generate_titles_dashboard],
    "positionschedule": [generate_titles_dashboard],
    "capitalprojectsdollarscomp": [enrich_geo_json_hook],
    # FDNY spatial enrichment: assign battalion_id(s) after Socrata import
    "fire_causes": [enrich_fire_causes_hook],
    "fdny_inspections": [enrich_inspections_hook],
    "fdny_violations": [enrich_violations_hook],
    "fire_incident_dispatch": [enrich_dispatch_hook],
    # Greenbook drives derived agency leadership + address tables (agency heads
    # aren't in any NYC dataset; wegov_orgs addresses are a thin static seed).
    "nycgreenbook": [derive_agency_enrichment_hook],
    # The five PASSPort vendor sub-tables (principals, evaluations, entity
    # summary, related entities, other names) join to `vendors` on normalized
    # name, so they are reloaded whenever the vendor list is. The hook HEADs
    # each export first and skips unchanged ones, so most days it is a no-op.
    # Doing Business (LL34) is name-matched against the vendor list, so its
    # crosswalk must be rebuilt whenever that list changes — even on the days
    # the MOCS feed itself is unchanged (it has not moved since 2025-11-21).
    # Track B: which orgs in the civic register are also PASSPort vendors. Name-
    # matched against the vendor list, so it is rebuilt whenever that list
    # changes — which also picks up register changes within a day.
    "vendors": [derive_vendor_enrichment_hook, derive_doing_business_hook,
                derive_org_vendor_hook],
    # Which City Record notices name a product the City licenses, for the panel
    # on each licence family page. Matched against the notice BODY via
    # idx_crol_body_fts, so it belongs to the table that carries that index.
    #
    # ⚠ REGISTERED HERE SO IT LANDS *AFTER* THE INDEX HOOK, and that is
    # load-bearing rather than tidy. The loop below does `insert(0, ...)` for the
    # index lambda on every table in TABLE_INDEXES | searchindexes.tables(), and
    # `crol` is in both — so naming it here leaves the order [indexes, this].
    # Reversed, the 774 product probes become 774 sequential scans of a 464 MB
    # heap instead of 774 bitmap index scans (2.4s measured, with the index).
    #
    # ⚠ crol reloads on SOURCE CHANGE, not daily — observed lagging up to five
    # days (2026-08-06 -> 08-10). The links are therefore as fresh as the last
    # crol ingest, which `notice_product_links.built_at` records.
    "crol": [derive_notice_product_links_hook],
}


# Performance indexes that must be recreated after pipeline drops/recreates tables.
# Map of table_name -> list of (index_name, column_expression) tuples.
TABLE_INDEXES = {
    # ⚠⚠ THESE NAMES LOOK OFF-CONVENTION ON PURPOSE. `civillist`, `payrolldata` and
    # `civillistactive` were indexed by a SECOND mechanism — CREATE INDEX statements
    # inside `main.py::ensure_people_indexes()`, run at api STARTUP — under different
    # names from the ones declared here. Measured 2026-08-13: the startup names were
    # the ones that existed on prod (`idx_civillist_orgid` 97MB / 2,803 scans,
    # `idx_payrolldata_orgid` 204MB) and the declared `*_wegov_org_id` names existed
    # nowhere. Adopting the LIVE names costs nothing; renaming would have meant
    # building ~300MB of duplicate index and dropping the originals for tidiness.
    # ⚠ And it was not merely redundant. Startup is a WEAK mechanism for a
    # pipeline-loaded table: /import-csv drops the table on every ingest and restores
    # only the GIN half, so these B-trees were absent from each ingest until the next
    # api restart — `idx_civillist_titlecode`, the most-used index on that table
    # (6,528 scans), was declared NOWHERE ELSE. Declared here, the post-ingest hook
    # restores them immediately.
    "civillist": [("idx_civillist_orgid", '"wegov-org-id"'),
                  ("idx_civillist_titlecode", '"TITLE CODE"')],
    "civillistactive": [("idx_civillistactive_orgid", '"wegov-org-id"')],
    # ⚠⚠ CORRECTED 2026-08-13: this comment used to say `crol` KEEPS its indexes
    # across the daily ingest, so the entries below were "durability insurance
    # rather than because the ingest destroys them". **That is wrong, and the
    # declaration is the only thing that saves them.** `main.py::import_crol_async`
    # does `DROP TABLE IF EXISTS crol` + CREATE on every import (crol is routed
    # away from the generic /import-csv path), then recreates four indexes from its
    # own inline list. Anything outside that list dies daily — which is exactly
    # what happened: `idx_crol_pin` / `idx_crol_pin10` were created by hand on
    # 2026-08-11 and were ALREADY GONE by 08-13, destroyed by the 16:18 ingest.
    # Measured, not inferred: pg_class oids show the importer's four created
    # together, the search-index pair next, and these two only when the hook was
    # run. They survive now because the scheduler calls run_post_ingest_hooks()
    # after the import and this list is what that hook applies.
    # The absence made the related-notices lookup on /oce/contract/{id} a seq scan
    # over all 1.1M rows: 106.8ms and 59,388 buffers, against 0.102ms and 9
    # once indexed (Sentry DATABOOK-API-16).
    "crol": [
        ("idx_crol_wegov_org_id", '"wegov-org-id"'),
        # ⚠ These four were created INLINE by main.py::import_crol_async — and by a
        # verbatim SECOND copy of the same block in import_csv_async. Three
        # declaration sites for one table, with `idx_crol_wegov_org_id` in two of
        # them. Declared here so the importer can call the shared hook instead.
        ("idx_crol_start_date", "start_date_parsed"),
        ("idx_crol_event_date", "event_date_parsed", "event_date_parsed IS NOT NULL"),
        ("idx_crol_section", '"SectionName"'),
        # oce.py related_notices — `WHERE trim("PIN") = ANY($1)`.
        ("idx_crol_pin", 'trim("PIN")'),
        # The notice<->solicitation prefix join: the 10-char EPIN prefixes the PIN.
        ("idx_crol_pin10", 'left(trim("PIN"), 10)'),
    ],
    "expensebudgetonnycopendata": [("idx_expensebudget_wegov_org_id", '"wegov-org-id"')],
    "capitalprojectsmilestones": [("idx_capitalprojectsmilestones_wegov_org_id", '"wegov-org-id"')],
    # Live name, per the note at the top of this map.
    "payrolldata": [("idx_payrolldata_orgid", '"wegov-org-id"')],
    # The three PASSPort tables had ZERO indexes — measured on prod 2026-08-04,
    # `pg_indexes` returned no rows for any of them, so every point lookup on
    # the procurement pages was a sequential scan. `SELECT * FROM contracts
    # WHERE ctr_id = $1` (the first thing /oce/contract/{id} does) planned as
    # `Seq Scan ... Rows Removed by Filter: 55805`, 10.7ms warm / 2,477 shared
    # buffers, and the handler runs a second one against contract_id whenever
    # the first misses. Each index below backs a measured equality predicate:
    "contracts": [
        # /oce/contract/{id} — primary lookup, then the contract_id fallback.
        ("idx_contracts_ctr_id", "ctr_id"),
        ("idx_contracts_contract_id", "contract_id"),
        # /oce/solicitation/{epin} resulting-contracts, and the notice<->procurement
        # crosswalk in main.py, which runs `LEFT JOIN LATERAL (SELECT ctr_id FROM
        # contracts WHERE epin = trim(c."PIN") LIMIT 1)` once PER crol ROW for a
        # whole year — the largest single win here.
        ("idx_contracts_epin", "epin"),
        # Vendor profile contract list (oce.get_vendor, mcp get_vendor_profile).
        ("idx_contracts_vendor_name", "vendor_name"),
    ],
    "vendors": [
        ("idx_vendors_supplier_id", '"PASSPort Supplier-ID"'),
        ("idx_vendors_vendor_name", '"Vendor Name"'),
    ],
    "solicitations": [("idx_solicitations_epin", '"EPIN"')],
}


async def recreate_table_indexes(conn: asyncpg.Connection, table_name: str):
    """Recreate performance indexes after pipeline drops/recreates a table.

    Why: The data pipeline does DROP TABLE + CREATE TABLE on every import,
    which destroys manually-created indexes. This hook ensures critical
    indexes (e.g. wegov-org-id for org profile queries) survive data updates.

    ⚠ The extractor path is DROP + RENAME, not TRUNCATE: rows are COPYed into
    `_staging_<table>`, the real table is dropped and the staging one renamed
    over it. The staging table carries no indexes, so the renamed table has
    none either — which is why a hand-run CREATE INDEX cannot survive here and
    this hook is the only durable place to declare one.
    """
    indexes = TABLE_INDEXES.get(table_name, [])
    search = searchindexes.for_table(table_name)
    if not indexes and not search:
        return
    created = 0
    for entry in indexes:
        # ⚠ A third element is an optional PARTIAL-index predicate. crol's
        # event-date index is `WHERE event_date_parsed IS NOT NULL` (16K of 1.1M
        # rows carry a date), and without this the declaration could not express it
        # — which is why that one lived inline in the importer instead.
        idx_name, col_expr = entry[0], entry[1]
        where = f' WHERE {entry[2]}' if len(entry) > 2 else ''
        try:
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS {idx_name} ON "{table_name}"({col_expr}){where}'
            )
            created += 1
            # ⚠ "ensured", not "Created": CREATE INDEX IF NOT EXISTS succeeds as a
            # no-op, so this line said "Created" for indexes that already existed —
            # which reads as evidence of work that did not happen. It matters now
            # that the log is actually readable (#249).
            print(f"[indexes] ✓ ensured {idx_name} on {table_name}")
        except Exception as e:
            print(f"[indexes] ✗ Failed to create {idx_name} on {table_name}: {exc_str(e)}")
    # ⚠ THE GIN HALF, and it had no durable home at all until now. TABLE_INDEXES
    # renders `CREATE INDEX ... ON tbl(expr)`, which cannot express
    # `USING gin (col gin_trgm_ops)`, so the global-search indexes were declared in
    # main.py and applied ONLY by /import-csv — a path `contracts` and
    # `solicitations` never take. Measured 2026-08-13: 5 of the 19 were missing on
    # prod, all 5 on those two tables, and contract search was a seq scan of 55,806
    # rows on every keystroke-completed query. Same module now serves both callers.
    if search:
        created += await searchindexes.ensure(
            conn, table_name,
            log=lambda m: print(f"[indexes] {m}"))
    # A freshly renamed table has no statistics until autovacuum gets to it, and
    # the planner will ignore a brand-new index while it thinks the table is
    # empty. ANALYZE makes the index take effect on the next query rather than
    # whenever autovacuum happens to run — otherwise this hook can report
    # success while every lookup still seq-scans.
    if created:
        try:
            await conn.execute(f'ANALYZE "{table_name}"')
            print(f"[indexes] ✓ ANALYZE {table_name}")
        except Exception as e:
            print(f"[indexes] ✗ ANALYZE {table_name} failed: {exc_str(e)}")


# Register index recreation as post-ingest hooks for affected tables.
# Inserted at position 0, not appended: `vendors` already carries three
# enrichment hooks that themselves query the table by name (vendor sub-tables,
# Doing Business, org<->vendor crosswalk), so rebuilding the indexes first
# means those hooks run against an indexed table instead of seq-scanning it.
# ⚠ THE UNION of both index families, not just TABLE_INDEXES. Registering only the
# btree tables is what left `contracts` and `solicitations` — which carry search
# indexes and nothing else — with no hook to restore their GIN indexes after the
# extractor dropped their tables.
for _tbl in sorted(set(TABLE_INDEXES) | searchindexes.tables()):
    if _tbl not in POST_INGEST_HOOKS:
        POST_INGEST_HOOKS[_tbl] = []
    POST_INGEST_HOOKS[_tbl].insert(
        0, lambda conn, t=_tbl: recreate_table_indexes(conn, t)
    )


async def run_post_ingest_hooks(table_name: str,
                                conn: asyncpg.Connection):
    """Run registered post-ingest hooks for a successfully updated table.

    Why: When source data changes, any derived analytics must be regenerated.
    Each hook receives the DB connection so it can query fresh data.
    """
    hooks = POST_INGEST_HOOKS.get(table_name, [])
    if not hooks:
        return

    print(f"[hooks] Running {len(hooks)} post-ingest hook(s) for {table_name}")
    for hook_fn in hooks:
        try:
            await hook_fn(conn)
            print(f"[hooks] ✓ {hook_fn.__module__}.{hook_fn.__name__}")
        except Exception as e:
            print(f"[hooks] ✗ {hook_fn.__module__}.{hook_fn.__name__}: {exc_str(e)}")



# =============================================================================
# Database Helpers
# =============================================================================

async def get_db_connection() -> asyncpg.Connection:
    """Create a standalone asyncpg connection for scheduler operations."""
    db_cfg = getattr(Config, 'db', {}) or {}
    db_user = os.environ.get('POSTGRES_USER', db_cfg.get('user', 'postgres'))
    db_pass = dbcreds.password(db_cfg.get('pwd', ''))
    db_host = os.environ.get('POSTGRES_HOST', db_cfg.get('host', '127.0.0.1'))
    db_name = os.environ.get('POSTGRES_DB', db_cfg.get('dbname', 'databook'))
    return await asyncpg.connect(
        user=db_user, password=db_pass, host=db_host, database=db_name
    )


async def get_active_datasets(conn: asyncpg.Connection) -> list[dict]:
    """Fetch all active datasets from the registry."""
    rows = await conn.fetch(
        "SELECT * FROM dataset_registry WHERE is_active = TRUE ORDER BY id"
    )
    return [dict(r) for r in rows]


async def update_registry(conn: asyncpg.Connection, dataset_id: int, **kwargs):
    """Update specific fields in the dataset registry."""
    sets = []
    vals = []
    for i, (k, v) in enumerate(kwargs.items(), 1):
        sets.append(f"{k} = ${i + 1}")
        vals.append(v)
    vals.insert(0, dataset_id)
    await conn.execute(
        f"UPDATE dataset_registry SET {', '.join(sets)} WHERE id = $1",
        *vals
    )


async def log_ingestion(conn: asyncpg.Connection, table_name: str,
                        s3_url: str, status: str, row_count: int = None,
                        error_message: str = None):
    """Record an ingestion event in the ingestion_log table."""
    try:
        await conn.execute("""
            INSERT INTO ingestion_log (table_name, s3_url, status, row_count, error_message)
            VALUES ($1, $2, $3, $4, $5)
        """, table_name, s3_url or '', status, row_count, error_message)
    except Exception as e:
        print(f"[scheduler] Failed to log ingestion for {table_name}: {exc_str(e)}")


# =============================================================================
# Socrata Metadata Polling
# =============================================================================

async def check_socrata_metadata(socrata_id: str,
                                 session: aiohttp.ClientSession
                                 ) -> Optional[datetime]:
    """
    Poll the Socrata metadata API to get the last data update timestamp.

    Why: Socrata returns `rowsUpdatedAt` as a Unix timestamp (always present)
    and `dataUpdatedAt` which is often null. We prefer `rowsUpdatedAt` for
    reliable change detection.
    """
    url = SOCRATA_META_URL.format(socrata_id=socrata_id)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"[scheduler] Socrata meta {socrata_id}: HTTP {resp.status}")
                return None
            meta = await resp.json()

            # Prefer rowsUpdatedAt (Unix int), fall back to dataUpdatedAt
            ts = meta.get('rowsUpdatedAt') or meta.get('dataUpdatedAt')
            if ts is None:
                return None

            # Unix timestamp (int/float)
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts, tz=timezone.utc)

            # ISO string fallback
            if isinstance(ts, str):
                return datetime.fromisoformat(
                    ts.replace('Z', '+00:00')
                )
    except Exception as e:
        print(f"[scheduler] Socrata meta {socrata_id} error: {exc_str(e)}")
    return None


# =============================================================================
# Ingestion: Full Replace
# =============================================================================

async def full_replace_import(conn: asyncpg.Connection, ds: dict,
                              session: aiohttp.ClientSession) -> dict:
    """
    Download full CSV from Socrata and replace the table contents.

    Uses TRUNCATE + COPY for atomicity.
    """
    socrata_id = ds['socrata_id']
    table_name = ds['table_name']
    url = f"{SOCRATA_BASE}/api/views/{socrata_id}/rows.csv?accessType=DOWNLOAD"

    print(f"[scheduler] Full replace: {table_name} from {socrata_id}")

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            if resp.status != 200:
                return {"status": "fail", "error": f"HTTP {resp.status}"}
            csv_text = await resp.text()

        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        if not rows:
            # Distinguish the two zero-row cases in the error we store on the
            # registry, because they need different responses. A header with no
            # data rows means the SOURCE is publishing an empty dataset (NYC Open
            # Data jvk9-k4re did exactly this on 2026-07-01) — nothing to retry,
            # and scripts/dataset-staleness.sh will report it against the City's
            # own LL251 row count. No header at all means a truncated or broken
            # response, which is worth investigating on our side.
            if reader.fieldnames:
                return {"status": "fail",
                        "error": f"Source published {len(reader.fieldnames)} "
                                 f"columns and 0 data rows (empty at source)"}
            return {"status": "fail", "error": "Empty CSV (no header in response)"}

        columns = list(rows[0].keys())

        # Deduplicate column names
        clean_cols = dedupe_columns(columns)

        # Atomic swap: create staging → swap
        staging = f"_staging_{table_name}"
        col_defs = ', '.join([f'"{c}" TEXT' for c in clean_cols])

        await conn.execute(f'DROP TABLE IF EXISTS "{staging}"')
        await conn.execute(f'CREATE TABLE "{staging}" ({col_defs})')

        # Batch insert
        batch_size = 5000
        total = 0
        for i in range(0, len(rows), batch_size):
            batch = [tuple(row.get(col, '') for col in columns)
                     for row in rows[i:i + batch_size]]
            await conn.copy_records_to_table(
                staging, records=batch, columns=clean_cols
            )
            total += len(batch)

        # Safety check: compare staging row count against existing table
        # to prevent data loss from truncated imports
        try:
            existing = await conn.fetchval(
                f'SELECT count(*) FROM "{table_name}"')
            if existing and existing > 0 and total < existing * 0.5:
                msg = (f"Safety check: staging has {total:,} "
                       f"rows vs existing {existing:,} "
                       f"({total/existing:.0%}). Aborting swap.")
                print(f"[SAFETY] ⚠️  {table_name}: {msg}", flush=True)
                await conn.execute(
                    f'DROP TABLE IF EXISTS "{staging}"')
                return {"status": "fail", "error": msg}
        except Exception:
            pass  # Table may not exist yet (first import)

        # Atomic swap: DROP old + RENAME staging in ONE transaction. The DDL holds
        # an ACCESS EXCLUSIVE lock, so concurrent readers block until commit and
        # then see the new table — instead of hitting a window where the table is
        # briefly absent (the source of transient UndefinedTable/UndefinedColumn 500s).
        async with conn.transaction():
            await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            await conn.execute(
                f'ALTER TABLE "{staging}" RENAME TO "{table_name}"'
            )

        return {"status": "success", "rows": total}

    except Exception as e:
        return {"status": "fail", "error": str(e)}


# =============================================================================
# Ingestion: Incremental Append
# =============================================================================

async def incremental_append(conn: asyncpg.Connection, ds: dict,
                             session: aiohttp.ClientSession) -> dict:
    """
    Fetch only rows updated since the last ingestion using Socrata's
    :updated_at system field, then UPSERT using the natural key.

    Why: The SODA resource API returns lowercase column names (e.g. request_id)
    but existing DB tables may have CamelCase columns (e.g. RequestID) from
    prior CSV imports. We build a case-insensitive column mapping to bridge
    this gap.
    """
    socrata_id = ds['socrata_id']
    table_name = ds['table_name']
    natural_key = ds.get('natural_key')
    last_ingested = ds.get('last_ingested_at')

    if not natural_key:
        # Fall back to full replace if no natural key defined
        print(f"[scheduler] No natural key for {table_name}, falling back to full replace")
        return await full_replace_import(conn, ds, session)

    print(f"[scheduler] Incremental append: {table_name} (key={natural_key})")

    # Build the SODA query with :updated_at filter
    params = {"$limit": "50000", "$order": ":updated_at ASC"}
    if last_ingested:
        since = last_ingested.strftime("%Y-%m-%dT%H:%M:%S")
        params["$where"] = f":updated_at > '{since}'"

    url = SOCRATA_RESOURCE_URL.format(socrata_id=socrata_id)

    try:
        async with session.get(url, params=params,
                               timeout=aiohttp.ClientTimeout(total=300)) as resp:
            if resp.status != 200:
                return {"status": "fail", "error": f"HTTP {resp.status}"}
            csv_text = await resp.text()

        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)

        if not rows:
            print(f"[scheduler] No new rows for {table_name}")
            return {"status": "success", "rows": 0}

        csv_columns = list(rows[0].keys())

        # Check if table exists; if not, create it with CSV column names
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = $1 AND table_schema = 'public'
            )
        """, table_name)

        if not table_exists:
            col_defs = ', '.join([f'"{c}" TEXT' for c in csv_columns])
            await conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
            # No mapping needed — columns match CSV
            db_columns = csv_columns
            nk_db = natural_key
        else:
            # Build case-insensitive mapping: csv_col (lowercase) → db_col (actual)
            db_cols_result = await conn.fetch("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = $1 AND table_schema = 'public'
            """, table_name)
            db_col_names = [r['column_name'] for r in db_cols_result]
            db_col_lower_map = {c.lower(): c for c in db_col_names}

            # Map CSV columns → DB columns (skip CSV cols not in DB)
            db_columns = []
            csv_to_db = {}
            for cc in csv_columns:
                db_name = db_col_lower_map.get(cc.lower())
                if db_name:
                    db_columns.append(db_name)
                    csv_to_db[cc] = db_name

            if not db_columns:
                return {"status": "fail",
                        "error": "No matching columns between CSV and DB"}

            # Map the natural key to its DB column name
            nk_db = db_col_lower_map.get(natural_key.lower(), natural_key)
            csv_columns = [cc for cc in csv_columns if cc in csv_to_db]

        # Use a staging table for the UPSERT (with DB column names)
        staging = f"_delta_{table_name}"
        col_defs = ', '.join([f'"{c}" TEXT' for c in db_columns])

        await conn.execute(f'DROP TABLE IF EXISTS "{staging}"')
        await conn.execute(f'CREATE TABLE "{staging}" ({col_defs})')

        # Insert delta rows into staging
        batch_size = 5000
        total = 0
        for i in range(0, len(rows), batch_size):
            batch = [tuple(row.get(col, '') for col in csv_columns)
                     for row in rows[i:i + batch_size]]
            await conn.copy_records_to_table(
                staging, records=batch, columns=db_columns
            )
            total += len(batch)

        # UPSERT from staging into main table
        # First ensure the natural key has a unique constraint
        constraint_name = f"uq_{table_name}_{nk_db.replace(' ', '_').lower()}"
        try:
            await conn.execute(f"""
                ALTER TABLE "{table_name}"
                ADD CONSTRAINT "{constraint_name}"
                UNIQUE ("{nk_db}")
            """)
        except Exception as e:
            # Constraint or backing index may already exist
            if 'already exists' in str(e):
                pass
            else:
                raise

        # Build UPSERT
        insert_cols = ', '.join([f'"{c}"' for c in db_columns])
        update_sets = ', '.join([
            f'"{c}" = EXCLUDED."{c}"'
            for c in db_columns if c != nk_db
        ])

        await conn.execute(f"""
            INSERT INTO "{table_name}" ({insert_cols})
            SELECT {insert_cols} FROM "{staging}"
            ON CONFLICT ("{nk_db}") DO UPDATE SET {update_sets}
        """)

        # Clean up staging
        await conn.execute(f'DROP TABLE IF EXISTS "{staging}"')

        # Post-processing: backfill normalized columns and parse dates
        if ds.get('entity_column') and ds.get('canonical_id_column'):
            await post_normalize(
                conn, table_name,
                ds['entity_column'], ds['canonical_id_column'])
        await post_parse_dates(conn, table_name)

        return {"status": "success", "rows": total}

    except Exception as e:
        # Clean up staging on error
        try:
            await conn.execute(f'DROP TABLE IF EXISTS "_delta_{table_name}"')
        except Exception:
            pass
        return {"status": "fail", "error": str(e)}


async def post_normalize(conn: asyncpg.Connection, table_name: str,
                         entity_col: str, canonical_id_col: str):
    """Backfill entity mappings for newly inserted rows using existing data.

    Why: When rows are UPSERTed directly from Socrata (bypassing the
    normalizer), they lack canonical entity IDs (wegov-org-id, etc.).
    This function fills them via self-join on the entity column, using
    known mappings from previously normalized rows in the same table.
    """
    try:
        # Check if columns exist
        cols = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = $1 AND table_schema = 'public'
        """, table_name)
        col_names = {r['column_name'] for r in cols}

        if entity_col not in col_names or canonical_id_col not in col_names:
            print(f"[post_normalize] {table_name}: columns missing "
                  f"({entity_col}, {canonical_id_col})")
            return

        # Build mapping from existing rows
        updated = await conn.fetchval(f"""
            WITH mappings AS (
                SELECT DISTINCT "{entity_col}" as entity,
                       "{canonical_id_col}" as canonical_id
                FROM "{table_name}"
                WHERE "{canonical_id_col}" IS NOT NULL
                  AND "{canonical_id_col}" != ''
            )
            UPDATE "{table_name}" t
            SET "{canonical_id_col}" = m.canonical_id
            FROM mappings m
            WHERE t."{entity_col}" = m.entity
              AND (t."{canonical_id_col}" IS NULL OR t."{canonical_id_col}" = '')
            RETURNING 1
        """)

        # Also backfill wegov-org-name if it exists
        if 'wegov-org-name' in col_names and canonical_id_col == 'wegov-org-id':
            await conn.execute(f"""
                WITH mappings AS (
                    SELECT DISTINCT "{entity_col}" as entity,
                           "wegov-org-name" as org_name
                    FROM "{table_name}"
                    WHERE "wegov-org-name" IS NOT NULL
                      AND "wegov-org-name" != ''
                )
                UPDATE "{table_name}" t
                SET "wegov-org-name" = m.org_name
                FROM mappings m
                WHERE t."{entity_col}" = m.entity
                  AND (t."wegov-org-name" IS NULL OR t."wegov-org-name" = '')
            """)

        print(f"[post_normalize] {table_name}: backfilled entity mappings")

    except Exception as e:
        print(f"[post_normalize] {table_name}: error — {exc_str(e)}")


async def post_parse_dates(conn: asyncpg.Connection, table_name: str):
    """Fill *_parsed date columns from their raw counterparts.

    Why: The normalizer adds parsed DATE columns (event_date_parsed,
    start_date_parsed) for efficient queries. When rows arrive directly
    from Socrata, these columns are NULL. This parses the raw text dates.
    """
    # Map of parsed column → raw source column
    date_pairs = {
        'event_date_parsed': 'EventDate',
        'start_date_parsed': 'StartDate',
    }

    try:
        cols = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = $1 AND table_schema = 'public'
        """, table_name)
        col_names = {r['column_name'] for r in cols}

        for parsed_col, raw_col in date_pairs.items():
            if parsed_col not in col_names or raw_col not in col_names:
                continue

            # Parse MM/DD/YYYY from the first 10 chars of the raw column
            updated = await conn.execute(f"""
                UPDATE "{table_name}"
                SET "{parsed_col}" = TO_DATE(
                    SUBSTRING("{raw_col}" FROM 1 FOR 10), 'MM/DD/YYYY')
                WHERE "{parsed_col}" IS NULL
                  AND "{raw_col}" IS NOT NULL
                  AND "{raw_col}" != ''
                  AND length("{raw_col}") >= 10
            """)
            print(f"[post_parse_dates] {table_name}: filled {parsed_col}")

            # Recreate partial index if needed
            idx_name = f"idx_{table_name}_{parsed_col.replace('_parsed', '')}"
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS "{idx_name}"
                ON "{table_name}" ("{parsed_col}")
                WHERE "{parsed_col}" IS NOT NULL
            """)

    except Exception as e:
        print(f"[post_parse_dates] {table_name}: error — {exc_str(e)}")


async def needs_full_refresh(conn: asyncpg.Connection, ds: dict) -> bool:
    """Check if an incremental dataset needs a full normalizer refresh.

    Why: Incremental Socrata-direct imports bypass the normalizer, so new
    entity names won't get canonical mappings. A full normalizer refresh
    every 30 days catches any drift and ensures complete normalization.
    """
    table_name = ds['table_name']
    try:
        last_full = await conn.fetchval("""
            SELECT MAX(ingested_at) FROM ingestion_log
            WHERE table_name = $1
              AND status = 'success'
              AND s3_url LIKE '%s3%'
        """, table_name)
        if not last_full:
            return True
        return (datetime.now(timezone.utc) - last_full).days >= 30
    except Exception:
        return True


# =============================================================================
# Unmapped Entity Scanner
# =============================================================================

async def scan_unmapped_entities(conn: asyncpg.Connection,
                                ds: dict) -> list[str]:
    """
    After ingestion, check for rows missing canonical entity IDs.

    Returns a list of newly discovered unmapped entity values.
    """
    if not ds.get('needs_normalization') or not ds.get('entity_column'):
        return []

    table_name = ds['table_name']
    entity_col = ds['entity_column']
    id_col = ds.get('canonical_id_column', 'wegov-org-id')

    # Check if both columns exist in the table
    try:
        cols = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = $1 AND table_schema = 'public'
        """, table_name)
        col_names = {r['column_name'] for r in cols}
        if entity_col not in col_names or id_col not in col_names:
            print(f"[scanner] Columns missing in {table_name}: "
                  f"need {entity_col}, {id_col}")
            return []
    except Exception:
        return []

    # Find entity values with no canonical ID
    try:
        unmapped_rows = await conn.fetch(f"""
            SELECT DISTINCT "{entity_col}" as entity_value
            FROM "{table_name}"
            WHERE ("{id_col}" IS NULL OR "{id_col}" = '')
              AND "{entity_col}" IS NOT NULL
              AND TRIM("{entity_col}") != ''
        """)
    except Exception as e:
        print(f"[scanner] Query failed for {table_name}: {exc_str(e)}")
        return []

    new_unmapped = []
    for row in unmapped_rows:
        val = row['entity_value'].strip()
        if not val:
            continue

        # Check if this is a NEW unmapped entity
        existing = await conn.fetchval("""
            SELECT 1 FROM unmapped_entities
            WHERE table_name = $1 AND entity_column = $2 AND entity_value = $3
        """, table_name, entity_col, val)

        if not existing:
            await conn.execute("""
                INSERT INTO unmapped_entities
                    (table_name, entity_column, entity_value, core_dataset)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """, table_name, entity_col, val, 'orgs')
            new_unmapped.append(val)

    if new_unmapped:
        print(f"[scanner] {len(new_unmapped)} new unmapped entities "
              f"in {table_name}.{entity_col}")

    return new_unmapped


# =============================================================================
# Alert Emails
# =============================================================================

async def send_unmapped_alert(table_name: str, entity_col: str,
                              new_entities: list[str],
                              normalizer_id: int = None):
    """Send an alert email when new unmapped entities are discovered."""
    try:
        import boto3
        ses = boto3.client('ses', region_name='us-east-1')

        entity_list = '\n'.join([f"  • {e}" for e in new_entities[:20]])
        extra = (f"\n  ... and {len(new_entities) - 20} more"
                 if len(new_entities) > 20 else "")

        normalizer_url = ""
        if normalizer_id:
            normalizer_url = (f"\nMap these entities in the normalizer:\n"
                              f"{NORMALIZER_BASE_URL}/admin/matches"
                              f"/{normalizer_id}\n")

        body = (
            f"{len(new_entities)} new unmapped {entity_col} value(s) appeared "
            f"in the {table_name} dataset that aren't mapped to canonical "
            f"Databook organizations:\n\n{entity_list}{extra}\n"
            f"{normalizer_url}\n"
            f"Action required: Manual mapping needed in the normalizer.\n\n"
            f"Dataset: {table_name} | Column: {entity_col} | "
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )

        ses.send_email(
            Source=f"Databook Pipeline <{ALERT_FROM}>",
            Destination={"ToAddresses": [ALERT_TO]},
            Message={
                "Subject": {
                    "Data": f"⚠️ Databook: {len(new_entities)} new unmapped "
                            f"entities in {table_name}",
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {"Data": body, "Charset": "UTF-8"},
                },
            },
        )
        print(f"[alert] Unmapped entity alert sent for {table_name}")
    except Exception as e:
        # SES is not reachable from prod: the AWS credentials were removed when
        # the data lake moved off S3 (2026-07-11), so boto3 finds none and every
        # send fails here. Printing alone meant the signal died in a container
        # log. Fall back to Sentry, which IS wired, so the finding still lands
        # somewhere a human looks. The rows are in unmapped_entities regardless,
        # and /pipeline/unmapped + the admin Data Health page read them.
        print(f"[alert] Failed to send alert email: {exc_str(e)}")
        try:
            import sentry_sdk
            sentry_sdk.capture_message(
                f"{len(new_entities)} new unmapped {entity_col} value(s) in "
                f"{table_name} (email alert unavailable: {e}). "
                f"Sample: {', '.join(new_entities[:10])}",
                level="warning",
            )
        except Exception as se:
            print(f"[alert] Sentry fallback also failed: {se}")


async def send_staleness_alert(stale_datasets: list[dict]):
    """Send an alert when datasets haven't been updated within expected window."""
    if not stale_datasets:
        return

    try:
        import boto3
        ses = boto3.client('ses', region_name='us-east-1')

        items = '\n'.join([
            f"  • {ds['table_name']} — last ingested: "
            f"{ds['last_ingested_at'] or 'never'}"
            for ds in stale_datasets
        ])

        ses.send_email(
            Source=f"Databook Pipeline <{ALERT_FROM}>",
            Destination={"ToAddresses": [ALERT_TO]},
            Message={
                "Subject": {
                    "Data": f"⚠️ Databook: {len(stale_datasets)} stale datasets",
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {
                        "Data": f"The following datasets haven't been updated "
                                f"recently:\n\n{items}\n\n"
                                f"Check the data health dashboard for details:\n"
                                f"https://databook.nyc/admin/data-health",
                        "Charset": "UTF-8",
                    },
                },
            },
        )
        print(f"[alert] Staleness alert sent for {len(stale_datasets)} datasets")
    except Exception as e:
        print(f"[alert] Failed to send staleness alert: {exc_str(e)}")


# =============================================================================
# Normalizer Integration
# =============================================================================

async def process_normalized_dataset(conn: asyncpg.Connection, ds: dict,
                                     session: aiohttp.ClientSession,
                                     force: bool = False):
    """Process a dataset through the normalizer API using async + polling.

    Why: The normalizer runs a single uvicorn worker. Synchronous HTTP calls
    block for the entire processing duration (up to 30min for large datasets),
    causing queue contention, nginx 502s, and scheduler timeouts. Async mode
    queues the work and returns immediately; we poll /logs for completion.

    Flow: Socrata change detection → async normalizer trigger → poll for
    completion → S3 import.
    """
    table_name = ds['table_name']
    socrata_id = ds.get('socrata_id')
    normalizer_id = ds['normalizer_dataset_id']
    now = datetime.now(timezone.utc)

    # 1. Change detection (if Socrata dataset)
    if socrata_id:
        source_updated = await check_socrata_metadata(socrata_id, session)
        await update_registry(conn, ds['id'],
                              last_checked_at=now,
                              last_source_updated_at=source_updated)

        if not source_updated:
            print(f"[scheduler] {table_name}: couldn't get source timestamp")
            return

        last_ingested = ds.get('last_ingested_at')
        if not force and last_ingested and source_updated <= last_ingested:
            print(f"[scheduler] {table_name}: up to date "
                  f"(source={source_updated}, ingested={last_ingested})")
            return

        print(f"[scheduler] {table_name}: source changed! "
              f"Triggering normalizer (ID {normalizer_id})...")
    else:
        print(f"[scheduler] {table_name}: triggering normalizer "
              f"(ID {normalizer_id}, no Socrata change detection)...")

    # 2. Trigger normalizer via async HTTP API
    async_url = f"{NORMALIZER_BASE_URL}/process/{normalizer_id}/async"
    sync_url = f"{NORMALIZER_BASE_URL}/process/{normalizer_id}"
    logs_url = f"{NORMALIZER_BASE_URL}/logs"

    try:
        # Try async endpoint first (returns immediately)
        timeout = aiohttp.ClientTimeout(total=30)
        try:
            async with session.post(async_url, timeout=timeout) as resp:
                body = await resp.text()
                if resp.status == 200:
                    print(f"[scheduler] {table_name}: normalizer accepted "
                          f"(async mode)")
                    use_polling = True
                elif resp.status == 404:
                    # Async endpoint not available, fall back to sync
                    use_polling = False
                else:
                    error_msg = (f"Normalizer async HTTP {resp.status}: "
                                 f"{body[:100]}")
                    print(f"[scheduler] {table_name}: {error_msg}")
                    await update_registry(conn, ds['id'],
                                          last_error=error_msg)
                    return
        except Exception:
            # Connection error — fall back to sync
            use_polling = False

        result = None

        if use_polling:
            # 2a. Poll for completion via /logs endpoint
            poll_interval = 15  # seconds
            max_polls = NORMALIZER_TIMEOUT_SECONDS // poll_interval
            print(f"[scheduler] {table_name}: polling for completion "
                  f"(max {max_polls * poll_interval}s)...")

            for i in range(max_polls):
                await asyncio.sleep(poll_interval)

                try:
                    async with session.get(
                        logs_url,
                        params={"dataset_id": normalizer_id, "limit": 1},
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if resp.status != 200:
                            continue
                        log_data = await resp.json()
                        logs = log_data.get("logs", [])
                        if not logs:
                            continue

                        latest = logs[0]
                        started = latest.get("started_at", "")
                        status = latest.get("status", "")

                        # Check if this log entry is recent (started after
                        # our trigger)
                        if status in ("success", "error"):
                            result = latest
                            break

                        if (i + 1) % 4 == 0:
                            elapsed = (i + 1) * poll_interval
                            print(f"[scheduler] {table_name}: still "
                                  f"processing ({elapsed}s)...")
                except Exception:
                    continue

            if result is None:
                error_msg = (f"Normalizer timed out after "
                             f"{NORMALIZER_TIMEOUT_SECONDS}s (polling)")
                print(f"[scheduler] {table_name}: {error_msg}")
                await log_ingestion(conn, table_name, async_url, 'fail',
                                    error_message=error_msg)
                await update_registry(conn, ds['id'], last_error=error_msg)
                return

            status = result.get("status", "")
            if status == "error":
                error_msg = result.get("error", "Unknown normalizer error")
                print(f"[scheduler] {table_name}: normalizer failed — "
                      f"{error_msg}")
                await log_ingestion(conn, table_name, async_url, 'fail',
                                    error_message=error_msg)
                await update_registry(conn, ds['id'], last_error=error_msg)
                return

            s3_url = result.get("s3_url", "")
            unmatched = result.get("unmatched_count", 0)
            suffix = ''
            if unmatched:
                suffix = f' ({unmatched} unmatched)'
            print(f"[scheduler] {table_name}: normalizer {status} → "
                  f"{s3_url}{suffix}")

        else:
            # 2b. Fallback: synchronous call (original behaviour)
            print(f"[scheduler] {table_name}: using synchronous mode "
                  f"(async endpoint unavailable)")
            timeout = aiohttp.ClientTimeout(
                total=NORMALIZER_TIMEOUT_SECONDS)
            async with session.post(sync_url, timeout=timeout) as resp:
                body = await resp.text()

                if not body or not body.strip():
                    error_msg = (
                        f"Normalizer returned empty body "
                        f"(HTTP {resp.status})."
                    )
                    print(f"[scheduler] {table_name}: {error_msg}")
                    await log_ingestion(conn, table_name,
                                        sync_url, 'fail',
                                        error_message=error_msg)
                    await update_registry(conn, ds['id'],
                                          last_error=error_msg)
                    return

                try:
                    result = json.loads(body)
                except json.JSONDecodeError as je:
                    error_msg = (
                        f"Normalizer returned invalid JSON "
                        f"(HTTP {resp.status}): "
                        f"{str(je)[:50]}. Body: {body[:100]}"
                    )
                    print(f"[scheduler] {table_name}: {error_msg}")
                    await log_ingestion(conn, table_name,
                                        sync_url, 'fail',
                                        error_message=error_msg)
                    await update_registry(conn, ds['id'],
                                          last_error=error_msg)
                    return

                status = result.get('status', '')
                if resp.status != 200 or status == 'error':
                    error_msg = result.get('error',
                                           f"HTTP {resp.status}")
                    print(f"[scheduler] {table_name}: normalizer "
                          f"failed — {error_msg}")
                    await log_ingestion(conn, table_name,
                                        sync_url, 'fail',
                                        error_message=error_msg)
                    await update_registry(conn, ds['id'],
                                          last_error=error_msg)
                    return

                s3_url = result.get('s3_url', '')
                unmatched = result.get('unmatched_count', 0)
                suffix = ''
                if unmatched:
                    suffix = f' ({unmatched} unmatched)'
                print(f"[scheduler] {table_name}: normalizer "
                      f"{status} → {s3_url}{suffix}")

    except asyncio.TimeoutError:
        error_msg = (f"Normalizer timed out after "
                     f"{NORMALIZER_TIMEOUT_SECONDS}s")
        print(f"[scheduler] {table_name}: {error_msg}")
        await log_ingestion(conn, table_name, sync_url, 'fail',
                            error_message=error_msg)
        await update_registry(conn, ds['id'], last_error=error_msg)
        return
    except Exception as e:
        error_msg = f"Normalizer request failed: {e}"
        print(f"[scheduler] {table_name}: {error_msg}")
        await log_ingestion(conn, table_name, sync_url, 'fail',
                            error_message=error_msg)
        await update_registry(conn, ds['id'], last_error=error_msg)
        return

    # 3. Import normalized data from S3 into PostgreSQL
    if s3_url:
        import_result = await _import_from_url(conn, table_name,
                                               s3_url, session)
        await log_ingestion(conn, table_name, s3_url,
                            import_result['status'],
                            row_count=import_result.get('rows'),
                            error_message=import_result.get('error'))

        if import_result['status'] == 'success':
            await update_registry(conn, ds['id'],
                                  last_ingested_at=now,
                                  estimated_rows=import_result.get('rows'),
                                  last_error=None)
            print(f"[scheduler] {table_name}: imported "
                  f"{import_result.get('rows'):,} rows")

            # Run post-ingest hooks (e.g. rebuild dashboard)
            await run_post_ingest_hooks(table_name, conn)

            # Post-ingestion: scan for unmapped entities
            new_unmapped = await scan_unmapped_entities(conn, ds)
            if new_unmapped:
                await send_unmapped_alert(
                    table_name, ds.get('entity_column', ''),
                    new_unmapped, normalizer_id
                )
        else:
            await update_registry(conn, ds['id'],
                                  last_error=import_result.get('error'))
            print(f"[scheduler] {table_name}: DB import failed — "
                  f"{import_result.get('error')}")


# =============================================================================
# Homepage Stats Cache
# =============================================================================

async def _safe_val(conn, query, default=0):
    """Run a single-value query, returning default on error."""
    try:
        val = await conn.fetchval(query)
        return val if val is not None else default
    except Exception as e:
        print(f"[stats] Query failed: {exc_str(e)}", flush=True)
        return default


def _clean_stats(stats):
    """Convert Decimal/date types to JSON-safe Python types.

    Why: json.dumps(default=str) converts Decimals to strings like
    '396117566000.0'. The frontend JS (toFinShortK, commaThousands)
    expects numeric values, not strings. This converts Decimals to
    float/int before serialization.
    """
    from decimal import Decimal
    cleaned = {}
    for k, v in stats.items():
        if isinstance(v, Decimal):
            cleaned[k] = float(v)
        elif isinstance(v, list):
            cleaned[k] = [
                {kk: float(vv) if isinstance(vv, Decimal) else vv
                 for kk, vv in item.items()}
                if isinstance(item, dict) else item
                for item in v
            ]
        else:
            cleaned[k] = v
    return cleaned


async def _notice_count(conn, section, days):
    """Count CROL notices for a section in the last N days."""
    if section == 'all':
        return await _safe_val(conn, f"""
            SELECT COUNT(*) FROM crol
            WHERE "StartDate" != ''
              AND start_date_parsed::date >= current_date - INTERVAL '{days} days'
        """)
    elif section == 'changeofpersonnel':
        return await _safe_val(conn, f"""
            SELECT COUNT(*) FROM crol
            WHERE "StartDate" != ''
              AND "SectionName" = 'Changes in Personnel'
              AND "AdditionalDescription1" != ''
              AND start_date_parsed::date >= current_date - INTERVAL '{days} days'
        """)
    else:
        section_map = {
            'publichearings': 'Public Hearings and Meetings',
            'contractawards': 'Contract Award Hearings',
            'specialmaterials': 'Special Materials',
            'agencyrules': 'Agency Rules',
            'propertydisposition': 'Property Disposition',
            'courtnotices': 'Court Notices',
            'procurement': 'Procurement',
        }
        name = section_map.get(section, section)
        return await _safe_val(conn, f"""
            SELECT COUNT(*) FROM crol
            WHERE "StartDate" != ''
              AND "SectionName" = '{name}'
              AND start_date_parsed::date >= current_date - INTERVAL '{days} days'
        """)


async def rebuild_glob_stats(conn: asyncpg.Connection):
    """Recompute all homepage statistics and cache in DB.

    Called at the end of date_check cycle so stats reflect
    the latest ingested data. The result is a single JSON row
    in cached_stats, served by GET /pipeline/globstats.
    """
    print("[stats] Rebuilding homepage statistics...")
    stats = {}

    try:
        # Increase statement timeout for heavy aggregate queries
        await conn.execute("SET statement_timeout = '300s'")

        # ── About the Data ─────────────────────────────────────
        stats['total_datasets_no'] = await _safe_val(
            conn, "SELECT count(*) FROM dataset_registry WHERE display_name IS NOT NULL")
        stats['total_records_no'] = await _safe_val(
            conn, "SELECT sum(n_live_tup)::bigint FROM pg_stat_user_tables")
        latest = await conn.fetchval(
            'SELECT max(last_ingested_at) FROM dataset_registry')
        stats['latest_update'] = (
            latest.isoformat() if hasattr(latest, 'isoformat')
            else latest)

        # ── Organizations ──────────────────────────────────────
        # ⚠ `type = 'City Agency'` alone is wrong since the OTI adoption: 240
        # orgs were retyped onto OTI's vocabulary, taking City Agency from 167
        # to 27, and this tile sits on the very page that broke. The vocabulary
        # lives in modules/orgfilter.py — nowhere else.
        stats['agencies_no'] = await _safe_val(
            conn, "SELECT count(*) FROM wegov_orgs WHERE type IN ("
                  + orgfilter.sql_type_list(orgfilter.CITY_AGENCY_TYPES)
                  + ") AND retired_at IS NULL")
        # Retired rows are merged-away duplicates; they are not organizations
        # the site serves, so they must not be counted as such.
        stats['orgs_no'] = await _safe_val(
            conn, "SELECT count(*) FROM wegov_orgs WHERE retired_at IS NULL")
        stats['orgs_datasets_no'] = await _safe_val(
            conn,
            "SELECT count(*) FROM dataset_registry WHERE is_active = true AND display_name IS NOT NULL")

        # ── People ─────────────────────────────────────────────
        # Filter by latest full year to avoid double-counting
        # employees across multiple years in the historical table
        latest_year = await conn.fetchval(
            'SELECT max("CALENDAR YEAR") FROM civillist')
        year_filter = f"""AND "CALENDAR YEAR" = '{latest_year}'""" if latest_year else ""
        stats['salary'] = float(await _safe_val(conn, f"""
            SELECT SUM(CAST(REGEXP_REPLACE("SALARY RATE", '[$,\\s]', '', 'g')
                   AS NUMERIC))
            FROM civillist
            WHERE "SALARY RATE" ~ '^[\\$0-9,.\\s]+'
              {year_filter}
        """, 0))
        stats['employees_no'] = await _safe_val(
            conn, f"""SELECT count(*) FROM civillist WHERE 1=1 {year_filter}""")
        stats['contacts_no'] = await _safe_val(
            conn, "SELECT count(*) FROM nycgreenbook")

        # ── Titles ─────────────────────────────────────────────
        stats['titles_no'] = await _safe_val(conn, """
            SELECT count(DISTINCT "Title Code")
            FROM nyccivilservicetitles""")
        stats['positions_no'] = await _safe_val(
            conn, "SELECT count(*) FROM positionschedule")
        stats['jobs_no'] = await _safe_val(
            conn, "SELECT count(*) FROM nycjobs")

        # ── Capital Projects ───────────────────────────────────
        # Exclude bogus future PUB_DATEs (e.g. 20260101 from Socrata)
        import datetime
        max_valid_date = datetime.date.today().strftime('%Y%m%d')
        pubdate = await conn.fetchval(
            f"""SELECT max("PUB_DATE") FROM capitalprojectsdollarscomp
                WHERE "PUB_DATE" <= '{max_valid_date}'""")
        if pubdate:
            stats['projects_no'] = await _safe_val(conn, f"""
                SELECT count(*) FROM capitalprojectsdollarscomp
                WHERE "PUB_DATE" = '{pubdate}'""")
            stats['orig_cost'] = float(await _safe_val(conn, f"""
                SELECT sum("BUDG_ORIG") FROM capitalprojectsdollarscomp
                WHERE "PUB_DATE" = '{pubdate}'""", 0))
            stats['curr_cost'] = float(await _safe_val(conn, f"""
                SELECT sum(cast(REPLACE("BUDG_CURR", ',', '.') as decimal))
                FROM capitalprojectsdollarscomp
                WHERE "PUB_DATE" = '{pubdate}'""", 0))
            stats['over_budg_am'] = float(await _safe_val(conn, f"""
                SELECT -sum(cast("BUDG_DIFF" as decimal))
                FROM capitalprojectsdollarscomp
                WHERE "PUB_DATE" = '{pubdate}'""", 0))

            # Top-10 lists
            for list_name, order_col, extra_where in [
                ('most_expensive_list', '"BUDG_CURR" DESC', ''),
                ('longest_running_list', '"DURATION_CURR" DESC',
                 'AND "DURATION_CURR" ~ \'^[0-9.]+$\''),
                ('most_over_budget_list', 'cast("BUDG_DIFF" as decimal) DESC',
                 'AND "BUDG_DIFF" ~ \'^-?[0-9.]+$\''),
                ('latest_list', '"DURATION_DIFF" DESC',
                 'AND "DURATION_DIFF" ~ \'^-?[0-9.]+$\''),
            ]:
                try:
                    rows = await conn.fetch(f"""
                        SELECT "PROJECT_DESCR", "PROJECT_ID",
                               "BUDG_CURR", "BUDG_ORIG", "BUDG_DIFF",
                               "DURATION_CURR", "DURATION_DIFF", "END_DIFF"
                        FROM capitalprojectsdollarscomp
                        WHERE "PUB_DATE" = '{pubdate}' {extra_where}
                        ORDER BY {order_col}
                        LIMIT 10
                    """)
                    stats[list_name] = [dict(r) for r in rows]
                except Exception:
                    stats[list_name] = []
        else:
            stats['projects_no'] = 0
            stats['orig_cost'] = 0
            stats['curr_cost'] = 0
            stats['over_budg_am'] = 0

        # ── Notices ────────────────────────────────────────────
        sections = [
            'all', 'publichearings', 'contractawards', 'specialmaterials',
            'agencyrules', 'propertydisposition', 'courtnotices',
            'procurement', 'changeofpersonnel'
        ]
        for sec in sections:
            for days in [1, 7, 30]:
                key = f"notices_{sec}_{days}"
                stats[key] = await _notice_count(conn, sec, days)

        # ── Schools ────────────────────────────────────────────
        stats['schools_no'] = await _safe_val(
            conn, "SELECT count(*) FROM schoollocations")
        stats['students_no'] = float(await _safe_val(conn, """
            SELECT sum(cast("Org Enroll" as decimal))
            FROM scaenrollmentcapacity
            WHERE "Org Enroll" ~ '^[0-9.]+'
              AND "Data As Of" = (
                  SELECT max("Data As Of") FROM scaenrollmentcapacity)
        """, 0))
        stats['prj_no'] = await _safe_val(
            conn, "SELECT count(*) FROM scaactiveprojects")

        prj_budget = float(await _safe_val(conn, """
            SELECT sum(cast("Project Budget Amount" as decimal))
            FROM scacapitalprojectschedules
            WHERE "Project Budget Amount" ~ '^[0-9.]+'
        """, 0))
        prj_costs = float(await _safe_val(conn, """
            SELECT sum(cast("Total Phase Actual Spending Amount" as decimal))
            FROM scacapitalprojectschedules
            WHERE "Total Phase Actual Spending Amount" ~ '^[0-9.]+'
        """, 0))
        stats['prj_budget'] = prj_budget
        stats['prj_costs'] = prj_costs
        s_no = stats['students_no'] or 1
        stats['pcosts_per_student'] = prj_costs / s_no

        # ── Districts ──────────────────────────────────────────
        stats['dist_cd'] = await _safe_val(conn, """
            SELECT count(*)
            FROM nyccommunityboards""")
        stats['dist_cc'] = 51  # Fixed — NYC Council districts
        stats['dist_nta'] = await _safe_val(conn, """
            SELECT count(DISTINCT nta_name)
            FROM demographics""", 195)  # fallback: known NYC NTA count
        stats['dist_sd'] = 33  # Fixed — NYC School districts

        # ── Procurement ────────────────────────────────────────
        stats['procurement_contracts'] = await _safe_val(
            conn, "SELECT count(*) FROM contracts")
        stats['procurement_vendors'] = await _safe_val(
            conn, "SELECT count(*) FROM vendors")
        stats['procurement_solicitations'] = await _safe_val(
            conn, "SELECT count(*) FROM solicitations")

        # Clean Decimal/date types for JSON serialization
        stats = _clean_stats(stats)

        # ── Store in DB ────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_stats (
                id INTEGER PRIMARY KEY DEFAULT 1,
                stats JSONB NOT NULL,
                computed_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            INSERT INTO cached_stats (id, stats, computed_at)
            VALUES (1, $1::jsonb, NOW())
            ON CONFLICT (id) DO UPDATE
            SET stats = $1::jsonb, computed_at = NOW()
        """, json.dumps(stats, default=str))

        print(f"[stats] Cached {len(stats)} stats successfully.")

        # Also update the static JSON fallback file
        static_path = os.path.join(
            os.path.dirname(__file__), '..', 'app', 'public', 'data', 'globStats.json')
        try:
            with open(static_path, 'w') as f:
                json.dump(stats, f, default=str)
            print(f"[stats] Updated static fallback: {static_path}")
        except Exception as ef:
            print(f"[stats] Could not update static file: {ef}")


    except Exception as e:
        print(f"[stats] Failed to rebuild stats: {exc_str(e)}")
        import traceback
        traceback.print_exc()


# =============================================================================
# Main Scheduler Loop
# =============================================================================

async def run_data_check(conn: asyncpg.Connection = None):
    """
    Run a single data check cycle: poll all datasets, import changed ones.

    Can be called directly for manual triggers or by the background loop.
    """
    own_conn = conn is None
    if own_conn:
        conn = await get_db_connection()

    try:
        datasets = await get_active_datasets(conn)
        print(f"[scheduler] Checking {len(datasets)} active datasets...")

        # Retry previously failed datasets first
        failed = await conn.fetch("""
            SELECT DISTINCT ON (l.table_name) l.table_name, l.error_message
            FROM ingestion_log l
            JOIN dataset_registry r ON r.table_name = l.table_name
            WHERE r.is_active = TRUE
            ORDER BY l.table_name, l.ingested_at DESC
        """)
        retry_tables = {
            row['table_name'] for row in failed
            if row.get('error_message')
        }
        if retry_tables:
            print(f"[scheduler] Retrying {len(retry_tables)} previously failed: "
                  f"{', '.join(sorted(retry_tables))}")

        async with aiohttp.ClientSession() as session:
            # ─── Pass 1: Non-normalizer Socrata + extractor datasets ──────
            # These only need a metadata poll + optional CSV import.
            non_norm = [d for d in datasets
                        if not d.get('normalizer_dataset_id')]
            norm = [d for d in datasets
                    if d.get('normalizer_dataset_id')]

            for ds in non_norm:
                table_name = ds['table_name']
                source_type = ds['source_type']
                force = table_name in retry_tables

                try:
                    if source_type == 'socrata':
                        await process_socrata_dataset(
                            conn, ds, session, force=force)
                    elif source_type == 'extractor':
                        await process_extractor_dataset(
                            conn, ds, session, force=force)
                    else:
                        print(f"[scheduler] Skipping {table_name} "
                              f"(source_type={source_type})")
                except Exception as e:
                    print(f"[scheduler] Error processing {table_name}: {exc_str(e)}")
                    await update_registry(conn, ds['id'],
                                          last_error=str(e),
                                          last_checked_at=datetime.now(timezone.utc))

            print(f"[scheduler] Pass 1 complete: {len(non_norm)} "
                  f"non-normalizer datasets checked.")

            # ─── Pass 2: Normalizer datasets ───────────────────────────────
            # Step 2a: Quick metadata check for ALL normalizer datasets
            changed_incremental = []  # append-mode with natural key
            changed_full = []         # replace-mode or needs 30d refresh
            for ds in norm:
                table_name = ds['table_name']
                socrata_id = ds.get('socrata_id')
                now = datetime.now(timezone.utc)
                try:
                    if socrata_id:
                        source_updated = await check_socrata_metadata(
                            socrata_id, session)
                        await update_registry(
                            conn, ds['id'],
                            last_checked_at=now,
                            last_source_updated_at=source_updated)

                        last_ingested = ds.get('last_ingested_at')
                        force = table_name in retry_tables
                        if force or not last_ingested or (
                                source_updated and source_updated > last_ingested):
                            # Route: incremental vs full
                            if (ds.get('ingestion_mode') == 'append'
                                    and ds.get('natural_key')
                                    and socrata_id):
                                # Check if 30-day full refresh needed
                                if await needs_full_refresh(conn, ds):
                                    print(f"[scheduler] {table_name}: "
                                          f"30-day full refresh needed")
                                    changed_full.append(ds)
                                else:
                                    changed_incremental.append(ds)
                            else:
                                changed_full.append(ds)
                    else:
                        await update_registry(
                            conn, ds['id'], last_checked_at=now)
                except Exception as e:
                    print(f"[scheduler] Error checking {table_name}: {exc_str(e)}")
                    await update_registry(conn, ds['id'],
                                          last_error=str(e),
                                          last_checked_at=now)

            print(f"[scheduler] Pass 2a complete: {len(norm)} normalizer "
                  f"datasets checked. {len(changed_incremental)} incremental, "
                  f"{len(changed_full)} full replace.")

            # Step 2b: Process incremental datasets via Socrata-direct
            for ds in changed_incremental:
                table_name = ds['table_name']
                now = datetime.now(timezone.utc)
                try:
                    print(f"[scheduler] {table_name}: incremental "
                          f"Socrata-direct update")
                    result = await incremental_append(conn, ds, session)
                    await log_ingestion(
                        conn, table_name,
                        f"socrata-direct:{ds.get('socrata_id', '')}",
                        result['status'],
                        row_count=result.get('rows'),
                        error_message=result.get('error'))

                    if result['status'] == 'success':
                        await update_registry(
                            conn, ds['id'],
                            last_ingested_at=now,
                            estimated_rows=result.get('rows'),
                            last_error=None)
                        print(f"[scheduler] {table_name}: incremental "
                              f"done — {result.get('rows', 0)} rows")
                        await run_post_ingest_hooks(table_name, conn)
                        new_unmapped = await scan_unmapped_entities(conn, ds)
                        if new_unmapped:
                            await send_unmapped_alert(
                                table_name,
                                ds.get('entity_column', ''),
                                new_unmapped,
                                ds.get('normalizer_dataset_id'))
                    else:
                        await update_registry(
                            conn, ds['id'],
                            last_error=result.get('error'))
                        print(f"[scheduler] {table_name}: incremental "
                              f"failed — {result.get('error')}")
                except Exception as e:
                    print(f"[scheduler] Error incremental "
                          f"{table_name}: {e}")
                    await update_registry(
                        conn, ds['id'], last_error=str(e))

            # Step 2c: Fire-and-forget to normalizer queue
            # The normalizer manages its own sequential queue —
            # we just POST /process/{id}/async for each changed dataset.
            if changed_full:
                normalizer_ok = False
                try:
                    async with session.get(
                        f"{NORMALIZER_BASE_URL}/health",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        normalizer_ok = resp.status == 200
                except Exception:
                    pass

                if normalizer_ok:
                    print(f"[scheduler] Normalizer reachable — queuing "
                          f"{len(changed_full)} datasets.")
                    queued = 0
                    for ds in changed_full:
                        table_name = ds['table_name']
                        nid = ds.get('normalizer_dataset_id')
                        if not nid:
                            print(f"[scheduler] {table_name}: no "
                                  f"normalizer_dataset_id, skipping")
                            continue
                        try:
                            async with session.post(
                                f"{NORMALIZER_BASE_URL}/process"
                                f"/{nid}/async",
                                timeout=aiohttp.ClientTimeout(total=30)
                            ) as resp:
                                body = await resp.json()
                                status = body.get("status", "?")
                                print(f"[scheduler] {table_name}: "
                                      f"queued → {status}")
                                queued += 1
                        except Exception as e:
                            print(f"[scheduler] {table_name}: "
                                  f"queue error — {e}")
                            await update_registry(
                                conn, ds['id'], last_error=str(e))
                    print(f"[scheduler] Queued {queued}/"
                          f"{len(changed_full)} datasets to normalizer.")
                else:
                    print(f"[scheduler] Normalizer unreachable — skipping "
                          f"normalization for {len(changed_full)} datasets.")

        print("[scheduler] Data check cycle complete.")

        # End-to-end health check: compare Socrata counts vs Postgres
        await _run_completeness_check(conn, session)

        # Unmapped-entity sweep, independent of what was ingested this cycle
        await _run_unmapped_scan(conn)

        # Rebuild cached homepage stats
        await rebuild_glob_stats(conn)

        # Pre-compute procurement dashboard stats so users never hit cold query
        from routers.oce import refresh_dashboard_cache, refresh_digital_reform_cache
        await refresh_dashboard_cache()
        await refresh_digital_reform_cache()

        # Pre-compute spending charts (DuckDB/S3 → JSON file)
        from generate_spending_charts import generate_spending_charts
        await generate_spending_charts()

    finally:
        if own_conn:
            await conn.close()


async def _run_unmapped_scan(conn):
    """Scan every scannable dataset for entity values with no canonical id.

    Why this is its own end-of-cycle pass, like _run_completeness_check:

    scan_unmapped_entities() was only ever called as a post-step inside the
    ingest functions, and in production it therefore never ran at all:

      * Normalizer-driven datasets — most of them, and precisely the ones with
        entity columns — are ingested by the NORMALIZER's own daily sweep, which
        pushes to this api's /import-csv. That endpoint does not scan.
      * The api scheduler then reaches the same dataset, sees
        `source_updated <= last_ingested` (already stamped by /import-csv),
        prints "up to date" and returns — before its scan call.

    So the scan was starved by the success of the other path. Measured on prod
    2026-07-29: 18 unmapped values existed across 9 scannable datasets while
    unmapped_entities held 0 rows, and /pipeline/health reported
    "total_alerts: 0" — a clean bill of health from a check that had never run.

    Running it as a sweep decouples it from ingest outcomes entirely: it does not
    matter which scheduler moved the data, or whether anything moved at all.
    Idempotent — scan_unmapped_entities only records values it has not seen.
    """
    datasets = await get_active_datasets(conn)
    scanned = 0
    total_new = 0

    for ds in datasets:
        if not ds.get('needs_normalization') or not ds.get('entity_column'):
            continue
        table_name = ds['table_name']
        try:
            new_unmapped = await scan_unmapped_entities(conn, ds)
            scanned += 1
            if new_unmapped:
                total_new += len(new_unmapped)
                await send_unmapped_alert(
                    table_name,
                    ds.get('entity_column', ''),
                    new_unmapped,
                    ds.get('normalizer_dataset_id'),
                )
        except Exception as e:
            # One bad table must not abort the sweep.
            print(f"[unmapped-scan] {table_name}: failed — {exc_str(e)}")

    print(f"[unmapped-scan] Scanned {scanned} datasets, "
          f"{total_new} new unmapped entities")


async def _run_completeness_check(conn, session):
    """Compare Socrata source row counts against our Postgres tables.

    Why: Detects silent data loss anywhere in the pipeline —
    normalizer failures, empty S3 uploads, import timeouts, etc.
    Runs at the end of each daily scheduler cycle.
    """
    datasets = await get_active_datasets(conn)
    issues = []

    for ds in datasets:
        socrata_id = ds.get('socrata_id')
        table_name = ds['table_name']
        if not socrata_id:
            continue

        # Get our actual Postgres row count
        try:
            row = await conn.fetchrow(
                "SELECT reltuples::bigint as cnt FROM pg_class c "
                "JOIN pg_namespace n ON c.relnamespace = n.oid "
                "WHERE c.relname = $1 AND n.nspname = 'public'",
                table_name
            )
            our_count = row['cnt'] if row else 0
        except Exception:
            our_count = 0

        # Get Socrata source count
        try:
            count_url = (
                f"https://data.cityofnewyork.us/resource/{socrata_id}"
                f".json?$select=count(*)%20as%20cnt&$limit=1"
            )
            async with session.get(count_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    source_count = int(data[0]['cnt']) if data else 0
                else:
                    continue
        except Exception:
            continue

        if source_count == 0:
            continue

        ratio = our_count / source_count if source_count > 0 else 0

        if our_count == 0:
            issues.append({
                'table_name': table_name,
                'socrata_id': socrata_id,
                'our_count': our_count,
                'source_count': source_count,
                'issue': 'empty_table',
                'pct': 0,
            })
        elif ratio < 0.95:
            issues.append({
                'table_name': table_name,
                'socrata_id': socrata_id,
                'our_count': our_count,
                'source_count': source_count,
                'issue': 'incomplete',
                'pct': round(ratio * 100, 1),
            })

    if issues:
        print(f"[scheduler] Completeness check: {len(issues)} issues found")
        await _send_completeness_alert(issues)
    else:
        print("[scheduler] Completeness check: all datasets OK")


async def _send_completeness_alert(issues: list[dict]):
    """Send an email when datasets have significant row count deltas."""
    try:
        import boto3
        ses = boto3.client('ses', region_name='us-east-1')

        items = '\n'.join([
            f"  • {i['table_name']}: {i['our_count']:,} / "
            f"{i['source_count']:,} ({i['pct']}%) — {i['issue']}"
            for i in issues
        ])

        ses.send_email(
            Source=f"Databook Pipeline <{ALERT_FROM}>",
            Destination={"ToAddresses": [ALERT_TO]},
            Message={
                "Subject": {
                    "Data": f"⚠️ Databook: {len(issues)} datasets "
                            f"with incomplete data",
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {
                        "Data": f"The following datasets have fewer rows "
                                f"than their Socrata source:\n\n{items}"
                                f"\n\nCheck the data health dashboard:\n"
                                f"https://databook.nyc/admin/data-health",
                        "Charset": "UTF-8",
                    },
                },
            },
        )
        print(f"[alert] Completeness alert sent for {len(issues)} datasets")
    except Exception as e:
        print(f"[alert] Failed to send completeness alert: {exc_str(e)}")


async def process_socrata_dataset(conn: asyncpg.Connection, ds: dict,
                                  session: aiohttp.ClientSession,
                                  force: bool = False):
    """Check a Socrata dataset for updates and ingest if changed."""
    table_name = ds['table_name']
    socrata_id = ds['socrata_id']

    if not socrata_id:
        print(f"[scheduler] {table_name}: no Socrata ID, skipping")
        return

    # Poll metadata
    source_updated = await check_socrata_metadata(socrata_id, session)
    now = datetime.now(timezone.utc)

    await update_registry(conn, ds['id'],
                          last_checked_at=now,
                          last_source_updated_at=source_updated)

    if not source_updated:
        print(f"[scheduler] {table_name}: couldn't get source timestamp")
        return

    # Compare with last ingestion
    last_ingested = ds.get('last_ingested_at')
    if not force and last_ingested and source_updated <= last_ingested:
        print(f"[scheduler] {table_name}: up to date "
              f"(source={source_updated}, ingested={last_ingested})")
        return

    print(f"[scheduler] {table_name}: source changed! "
          f"(source={source_updated}, ingested={last_ingested})")

    # Ingest
    if ds.get('ingestion_mode') == 'append':
        result = await incremental_append(conn, ds, session)
    else:
        result = await full_replace_import(conn, ds, session)

    # Log and update registry
    await log_ingestion(conn, table_name, ds.get('source_url', ''),
                        result['status'],
                        row_count=result.get('rows'),
                        error_message=result.get('error'))

    if result['status'] == 'success':
        await update_registry(conn, ds['id'],
                              last_ingested_at=now,
                              estimated_rows=result.get('rows'),
                              last_error=None)

        # Run post-ingest hooks (e.g. rebuild dashboard)
        await run_post_ingest_hooks(table_name, conn)

        # Post-ingestion: scan for unmapped entities
        new_unmapped = await scan_unmapped_entities(conn, ds)
        if new_unmapped:
            await send_unmapped_alert(
                table_name, ds.get('entity_column', ''),
                new_unmapped, ds.get('normalizer_dataset_id')
            )
    else:
        await update_registry(conn, ds['id'],
                              last_error=result.get('error'))
        print(f"[scheduler] {table_name}: ingestion failed — "
              f"{result.get('error')}")


async def process_extractor_dataset(conn: asyncpg.Connection, ds: dict,
                                    session: aiohttp.ClientSession,
                                    force: bool = False):
    """
    Process an extractor-based dataset (Checkbook, PASSPort).

    These run daily regardless of source change detection. Pass force=True
    (e.g. from a manual /pipeline/check trigger) to bypass the once-daily
    guard and re-ingest immediately.
    """
    table_name = ds['table_name']
    now = datetime.now(timezone.utc)

    # Check if already ingested today
    last_ingested = ds.get('last_ingested_at')
    if not force and last_ingested and (now - last_ingested).days < 1:
        print(f"[scheduler] {table_name}: already ingested today")
        await update_registry(conn, ds['id'], last_checked_at=now)
        return

    print(f"[scheduler] {table_name}: daily extractor run")

    # For extractor datasets, download from their S3 location
    source_url = ds.get('source_url')
    if not source_url:
        print(f"[scheduler] {table_name}: no source_url configured")
        return

    # Use full replace import from S3.
    # `contracts` needs a column transform (raw PASSPort CSV → snake_case schema
    # that oce.py queries); the generic raw loader would clobber it with raw
    # column names and break every /oce/contracts query. See
    # _import_contracts_transformed for details.
    if table_name == 'contracts':
        result = await _import_contracts_transformed(
            conn, table_name, source_url, session)
    else:
        result = await _import_from_url(conn, table_name, source_url, session)

    await log_ingestion(conn, table_name, source_url, result['status'],
                        row_count=result.get('rows'),
                        error_message=result.get('error'))

    if result['status'] == 'success':
        await update_registry(conn, ds['id'],
                              last_ingested_at=now,
                              last_checked_at=now,
                              estimated_rows=result.get('rows'),
                              last_error=None)

        # The Socrata and normalizer paths both do this; the extractor path
        # never did, so a hook registered on `vendors`/`contracts` would have
        # been silently dead. Registering a hook that never fires is worse
        # than having no hook, because the data looks maintained.
        await run_post_ingest_hooks(table_name, conn)

        new_unmapped = await scan_unmapped_entities(conn, ds)
        if new_unmapped:
            await send_unmapped_alert(
                table_name, ds.get('entity_column', ''),
                new_unmapped, ds.get('normalizer_dataset_id')
            )
    else:
        await update_registry(conn, ds['id'],
                              last_checked_at=now,
                              last_error=result.get('error'))


async def _import_from_url(conn: asyncpg.Connection, table_name: str,
                           url: str, session: aiohttp.ClientSession) -> dict:
    """Stream-download CSV from URL and replace table contents.

    Why: The previous implementation loaded the entire CSV into memory twice
    (once as raw text, once as list[dict]), causing OOM for datasets >500K
    rows on a 512MB container. This version streams in 64KB chunks and
    batch-inserts 2000 rows at a time, keeping memory at ~20MB.
    """
    batch_size = 2000

    try:
        timeout = aiohttp.ClientTimeout(total=1200, sock_read=300)
        async with session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                return {"status": "fail", "error": f"HTTP {resp.status}"}

            columns = None
            staging = f"_staging_{table_name}"
            batch = []
            total = 0
            adjusted = 0  # rows padded/truncated to the column count
            buf = b""

            async for chunk in resp.content.iter_chunked(64 * 1024):
                buf += chunk

                # Parse CSV header from the first newline
                if columns is None:
                    newline_pos = buf.find(b"\n")
                    if newline_pos == -1:
                        continue

                    header_line = buf[:newline_pos].decode(
                        "utf-8", errors="replace")
                    reader = csv.reader(io.StringIO(header_line))
                    # Dedupe before building the schema so a source with
                    # repeated headers (e.g. mocs-contracts.csv duplicates
                    # wegov-org-name/-id) doesn't raise Postgres
                    # `column "..." specified more than once`. Length is
                    # preserved, so the per-row `len(row) != len(columns)`
                    # guard below still aligns.
                    columns = dedupe_columns(next(reader))
                    col_defs = ', '.join(
                        [f'"{c}" TEXT' for c in columns])

                    await conn.execute(
                        f'DROP TABLE IF EXISTS "{staging}"')
                    await conn.execute(
                        f'CREATE TABLE "{staging}" ({col_defs})')

                    remaining = buf[newline_pos + 1:]
                    buf = b""
                    text = remaining.decode(
                        "utf-8", errors="replace")
                else:
                    text = buf.decode("utf-8", errors="replace")
                    buf = b""

                # Keep any incomplete trailing line for next chunk
                last_nl = text.rfind("\n")
                if last_nl == -1:
                    buf = text.encode("utf-8")
                    continue
                complete = text[:last_nl]
                remainder = text[last_nl + 1:]
                if remainder:
                    buf = remainder.encode("utf-8")

                reader = csv.reader(io.StringIO(complete))
                for row in reader:
                    conformed = conform_row(row, len(columns))
                    if conformed is None:
                        continue
                    if len(row) != len(columns):
                        adjusted += 1
                    batch.append(conformed)
                    if len(batch) >= batch_size:
                        await conn.copy_records_to_table(
                            staging, records=batch,
                            columns=columns)
                        total += len(batch)
                        batch = []
                        if total % 50000 == 0:
                            print(f"[scheduler] {table_name}: "
                                  f"imported {total:,} rows...")

            # Flush remaining buffer
            if buf and columns:
                text = buf.decode("utf-8", errors="replace")
                reader = csv.reader(io.StringIO(text))
                for row in reader:
                    conformed = conform_row(row, len(columns))
                    if conformed is None:
                        continue
                    if len(row) != len(columns):
                        adjusted += 1
                    batch.append(conformed)

            # Flush last batch
            if batch and columns:
                await conn.copy_records_to_table(
                    staging, records=batch, columns=columns)
                total += len(batch)

        if total == 0:
            await conn.execute(f'DROP TABLE IF EXISTS "{staging}"')
            return {"status": "fail", "error": "Empty CSV"}

        if adjusted:
            print(f"[scheduler] {table_name}: conformed {adjusted:,} "
                  f"ragged rows to {len(columns)} columns", flush=True)

        # Safety check: compare staging row count against existing table
        # to prevent data loss from truncated imports
        try:
            existing = await conn.fetchval(
                f'SELECT count(*) FROM "{table_name}"')
            if existing and existing > 0 and total < existing * 0.5:
                msg = (f"Safety check: staging has {total:,} "
                       f"rows vs existing {existing:,} "
                       f"({total/existing:.0%}). Aborting swap.")
                print(f"[SAFETY] ⚠️  {table_name}: {msg}", flush=True)
                await conn.execute(
                    f'DROP TABLE IF EXISTS "{staging}"')
                return {"status": "fail", "error": msg}
        except Exception:
            pass  # Table may not exist yet (first import)

        # Atomic swap: DROP old + RENAME staging in ONE transaction. The DDL holds
        # an ACCESS EXCLUSIVE lock, so concurrent readers block until commit and
        # then see the new table — instead of hitting a window where the table is
        # briefly absent (the source of transient UndefinedTable/UndefinedColumn 500s).
        async with conn.transaction():
            await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            await conn.execute(
                f'ALTER TABLE "{staging}" RENAME TO "{table_name}"'
            )

        return {"status": "success", "rows": total}

    except Exception as e:
        # Clean up staging table on error
        try:
            await conn.execute(
                f'DROP TABLE IF EXISTS "_staging_{table_name}"')
        except Exception:
            pass
        return {"status": "fail", "error": str(e)}


# --- contracts: transformed import (raw PASSPort CSV → snake_case schema) -----

# Target schema for the `contracts` table. This MUST match the columns oce.py
# queries (ctr_id, contract_id, award_amount, agency, vendor_name, ...) and the
# bootstrap schema in setup_oce_postgres.py. The generic raw loader would import
# the PASSPort column names verbatim ("CTR-ID", "Award Amount", ...) and break
# every /oce/contracts query, so contracts is imported via the transform below.
_CONTRACTS_DDL = """
    ctr_id TEXT, epin TEXT, contract_id TEXT, contract_title TEXT,
    agency TEXT, agency_id TEXT, vendor_name TEXT, program TEXT,
    procurement_method TEXT, contract_type TEXT, status TEXT,
    award_amount REAL, current_amount REAL, start_date TEXT, end_date TEXT,
    industry TEXT, normalized_contract_id TEXT, normalized_epin TEXT
"""
_CONTRACTS_COLS = [
    'ctr_id', 'epin', 'contract_id', 'contract_title', 'agency', 'agency_id',
    'vendor_name', 'program', 'procurement_method', 'contract_type', 'status',
    'award_amount', 'current_amount', 'start_date', 'end_date', 'industry',
    'normalized_contract_id', 'normalized_epin',
]


def _clean_money(val):
    """Parse a money string like '$586,840,920.00' to a float (0.0 if blank)."""
    if val is None or val == '':
        return 0.0
    cleaned = re.sub(r'[^0-9.]', '', str(val))
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _normalize_id(value):
    """Uppercase + strip non-alphanumerics, for cross-system id matching."""
    if not value:
        return None
    norm = re.sub(r'[^A-Z0-9]', '', str(value).upper())
    return norm or None


async def _import_contracts_transformed(conn: asyncpg.Connection,
                                        table_name: str, url: str,
                                        session: aiohttp.ClientSession) -> dict:
    """Import mocs-contracts.csv into the snake_case schema oce.py expects.

    Why this exists instead of the generic _import_from_url:
      1. The raw CSV uses PASSPort headers ("CTR-ID", "Contract ID",
         "Award Amount", "wegov-org-id", ...). oce.py queries snake_case
         (ctr_id, contract_id, award_amount, agency_id, ...), so a raw dump
         breaks every contracts endpoint with UndefinedColumnError.
      2. The source header is currently malformed: wegov-org-name / wegov-org-id
         appear TWICE (26 header cols) while data rows have 24 cols. A raw
         CREATE TABLE fails with 'column "wegov-org-name" specified more than
         once'. We dedupe by keeping each column's FIRST occurrence, which is
         the one aligned with the data (the duplicate pair is appended at the
         end of the header only).

    Mirrors setup_oce_postgres.py's transform_contracts, using stdlib csv only
    (pandas is not installed in the API image).
    """
    try:
        timeout = aiohttp.ClientTimeout(total=1200, sock_read=300)
        async with session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                return {"status": "fail", "error": f"HTTP {resp.status}"}
            text = await resp.text()

        reader = csv.reader(io.StringIO(text))
        try:
            header = next(reader)
        except StopIteration:
            return {"status": "fail", "error": "Empty CSV"}

        # Map column name → first column index (strip BOM/whitespace). Keeping
        # the first occurrence drops the duplicated trailing wegov-org-* pair.
        col_idx: dict[str, int] = {}
        for i, name in enumerate(header):
            key = name.lstrip('﻿').strip()
            if key not in col_idx:
                col_idx[key] = i

        def g(row: list, name: str):
            i = col_idx.get(name)
            if i is None or i >= len(row):
                return None
            val = row[i].lstrip('﻿').strip()
            return val or None

        rows = []
        for row in reader:
            if not row:
                continue
            cid = g(row, 'Contract ID')
            epin = g(row, 'EPIN')
            rows.append((
                g(row, 'CTR-ID'),
                epin,
                cid,
                g(row, 'Contract Title'),
                g(row, 'Agency'),
                g(row, 'wegov-org-id'),
                g(row, 'Vendor'),
                g(row, 'Program'),
                g(row, 'Procurement Method'),
                g(row, 'Contract Type'),
                g(row, 'Status'),
                _clean_money(g(row, 'Award Amount')),
                _clean_money(g(row, 'Current Contract Amount')),
                g(row, 'Contract Start Date'),
                g(row, 'Contract End Date'),
                g(row, 'Industry'),
                _normalize_id(cid),
                _normalize_id(epin),
            ))

        total = len(rows)
        if total == 0:
            return {"status": "fail", "error": "Empty CSV"}

        staging = f"_staging_{table_name}"
        await conn.execute(f'DROP TABLE IF EXISTS "{staging}"')
        await conn.execute(f'CREATE TABLE "{staging}" ({_CONTRACTS_DDL})')
        await conn.copy_records_to_table(
            staging, records=rows, columns=_CONTRACTS_COLS)

        # Safety check: don't swap in a table that lost >50% of its rows.
        try:
            existing = await conn.fetchval(
                f'SELECT count(*) FROM "{table_name}"')
            if existing and existing > 0 and total < existing * 0.5:
                msg = (f"Safety check: staging has {total:,} rows vs existing "
                       f"{existing:,} ({total/existing:.0%}). Aborting swap.")
                print(f"[SAFETY] ⚠️  {table_name}: {msg}", flush=True)
                await conn.execute(f'DROP TABLE IF EXISTS "{staging}"')
                return {"status": "fail", "error": msg}
        except Exception:
            pass  # Table may not exist yet (first import)

        async with conn.transaction():
            await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            await conn.execute(
                f'ALTER TABLE "{staging}" RENAME TO "{table_name}"')

        return {"status": "success", "rows": total}

    except Exception as e:
        try:
            await conn.execute(f'DROP TABLE IF EXISTS "_staging_{table_name}"')
        except Exception:
            pass
        return {"status": "fail", "error": str(e)}


# =============================================================================
# Background Task (started on API boot)
# =============================================================================

async def scheduler_loop():
    """
    Background loop that runs the data check cycle daily.

    Designed to be started via asyncio.create_task during API startup.
    """
    print("[scheduler] Data scheduler started. First check in 60 seconds...")
    await asyncio.sleep(60)  # Initial delay to let API fully boot

    while True:
        # Retry a cycle that died outright, before falling back to the daily
        # interval. See SCHEDULER_RETRY_DELAY_SECONDS for why this exists and why
        # it does not try to tell a transient failure from a permanent one.
        completed = False
        last_error = ""
        for attempt in range(1, SCHEDULER_MAX_RETRIES + 2):
            try:
                await _hc_ping("start")
                print(f"[scheduler] Starting daily data check at "
                      f"{datetime.now(timezone.utc).isoformat()}"
                      + (f" (attempt {attempt})" if attempt > 1 else ""))
                await run_data_check()
                completed = True
                break
            except Exception as e:  # noqa: BLE001 — the loop must never die
                import traceback
                if attempt > SCHEDULER_MAX_RETRIES:
                    # ⚠⚠ ERROR, NOT print — THIS IS THE ALERTING FIX. The old
                    # line here was a bare `print`, so a scheduler that had died
                    # was invisible to Sentry: LoggingIntegration raises events
                    # from the LOGGING module at ERROR and never sees a print,
                    # and no healthchecks check covers this loop (all 8 watch
                    # HOST crons; this runs inside the api). The only compensating
                    # control was dataset-staleness.sh, up to 5 days later and
                    # only if the source moved.
                    last_error = exc_str(e)
                    logger.error(
                        "[scheduler] cycle failed %d times, giving up until the "
                        "next interval: %s", attempt, last_error)
                    traceback.print_exc()
                    break
                # WARNING while retries remain: visible in the log (#249) but not
                # an alert, because a blip that self-heals should not page anyone.
                logger.warning(
                    "[scheduler] cycle failed (attempt %d/%d), retrying in %ds: %s",
                    attempt, SCHEDULER_MAX_RETRIES + 1,
                    SCHEDULER_RETRY_DELAY_SECONDS, exc_str(e))
                traceback.print_exc()
                await asyncio.sleep(SCHEDULER_RETRY_DELAY_SECONDS)

        # ⚠ The ping reports whether the LOOP completed a cycle, not whether every
        # dataset ingested — see the note on _hc_ping. It is sent outside the retry
        # loop so exactly one success-or-fail lands per interval.
        if completed:
            await _hc_ping("success", "scheduler cycle completed")
        else:
            await _hc_ping(
                "fail",
                f"scheduler cycle failed {SCHEDULER_MAX_RETRIES + 1} times, "
                f"last error: {last_error}")

        print(f"[scheduler] Next check in {SCHEDULER_INTERVAL_SECONDS}s")
        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)
