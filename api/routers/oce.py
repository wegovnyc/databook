from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from typing import Optional, List, Dict, Any
import asyncio
import duckdb
import os
import math
import json
import re
import time
import csv
import io
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from modules.postgrex.asyncmodel import PostgresModelAsync
from modules.duckpool import to_duckdb_thread
from modules.errfmt import exc_str
# ⚠ The ONE owner of what "digital" means. Seven call sites used to interpolate
# their own vendor_tags IN-lists; the scope (and the tag->derived migration
# gate) now lives in modules/digitalscope.py. Do not query vendor_tags here.
from modules import digitalscope
# ⚠ The ONE owner of whether a contract's amount is committed money or a CEILING
# an agency may buy against. Three surfaces used to make that judgement
# separately (the queue headline, the vendor profile's contract list, and the
# lock-in denominator) and none of them made it at all — so 43% of the queue's
# headline was ceiling money captioned as spend. Do not re-derive the MA/MMA
# rule here; `startswith("MA")` silently misses MMA, which is $23.4B.
from modules import contractkind
# ⚠ Purchase-class resolution (product grain, family fallback). The Renewal Queue
# and the Licenses page MUST resolve a contract's class through the same module or
# they can disagree about which question a contract deserves — which is how $6.8M
# of AWS ended up rated "low replaceability" and invisible.
from modules import licenseclass
# ⚠ The shared "expiring" window. Both pages used to type the horizon themselves.
from modules import licensewindow
# ⚠ Vendor-name -> supplier id as a MAP, never a join. See the module docstring:
# 48 names hold >1 row in `vendors`, and the join duplicated a contract.
from modules import vendorids
# ⚠ The Overview's headline lens. The segment axis and the drill-down predicate live
# in ONE module so the bar and the filtered table cannot disagree about what a
# segment contains — see its docstring for why "licences" is not a function.
from modules import techsegments
# ⚠ Unregistered purchasing vehicles. Section-level, `ceiling` never `value`, and
# never merged into a total.
from modules import pipelinevehicles

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/oce",
    tags=["Procurement (OCE)"],
    responses={404: {"description": "Not found"}},
)

# Spending data lake location. Historically AWS S3 (public-read, queried over
# HTTPS); set SPENDING_DATA_BASE to a local directory to serve the Parquet off
# local disk instead (Hetzner-local, no AWS creds, faster, and DuckDB can glob so
# the per-year chunk map is unused). The value is a base under which the tree is
# `fiscal_year=<FY>/*.parquet`. A "http(s)://" value = S3 mode; anything else =
# local-directory mode. Reversible: flip the env back to the S3 URL.
S3_HTTPS_BASE = "https://nyc-databook-spending.s3.amazonaws.com"
SPENDING_DATA_BASE = os.environ.get("SPENDING_DATA_BASE", S3_HTTPS_BASE).rstrip("/")


def _spending_base_is_local() -> bool:
    return not SPENDING_DATA_BASE.startswith(("http://", "https://"))

# In-memory cache for dashboard stats (expensive S3 Parquet + multi-query aggregation)
# Refreshed explicitly after each daily scheduler cycle; TTL is a safety net.
_dashboard_cache: Dict[str, Any] = {'data': None, 'timestamp': 0}
DASHBOARD_CACHE_TTL = 90000  # 25 hours — just over 1 scheduler cycle as safety net

# In-memory LRU cache for the digital-reform combined endpoint (also used by the
# agency-procurement profile). BOUNDED on purpose: the cache key includes the
# request's page/sort/filter params, so a scraper hammering the endpoint with
# randomized params (e.g. negative page numbers) produces a distinct key per hit.
# With an unbounded dict those keys accumulated forever, growing memory until the
# container hit its cgroup limit and got OOM-killed. The size cap + LRU eviction
# make that impossible; param normalization (see get_digital_reform_all) also
# collapses functionally-identical requests onto one key so the cache stays useful.
_digital_reform_cache: "OrderedDict[str, Any]" = OrderedDict()
DIGITAL_REFORM_CACHE_TTL = 86400  # 24 hours — data refreshes daily
DIGITAL_REFORM_CACHE_MAX = 256    # hard cap on distinct cached param combinations


def _dr_cache_get(key: str):
    """Bounded-LRU read: return fresh cached data, or None (dropping expired)."""
    entry = _digital_reform_cache.get(key)
    if entry is None:
        return None
    if (time.time() - entry['ts']) >= DIGITAL_REFORM_CACHE_TTL:
        _digital_reform_cache.pop(key, None)
        return None
    _digital_reform_cache.move_to_end(key)
    return entry['data']


def _dr_cache_set(key: str, data) -> None:
    """Bounded-LRU write: store, mark most-recently-used, and evict oldest beyond
    the cap so unbounded distinct keys can't grow memory without limit."""
    _digital_reform_cache[key] = {'data': data, 'ts': time.time()}
    _digital_reform_cache.move_to_end(key)
    while len(_digital_reform_cache) > DIGITAL_REFORM_CACHE_MAX:
        _digital_reform_cache.popitem(last=False)

# Cache for the digital-contract spend map (one expensive Checkbook Parquet scan,
# shared across all page-filter combinations so a filter click never re-scans S3).
_digital_spend_cache: Dict[str, Any] = {'data': None, 'ts': 0}
_spend_populating: bool = False  # guards against concurrent background scans

# In-memory cache for the /transactions endpoint, keyed by query params.
# The underlying query scans many S3 Parquet files; data refreshes daily.
_transactions_cache: Dict[str, Any] = {}
TRANSACTIONS_CACHE_TTL = 86400  # 24 hours
_TRANSACTIONS_CACHE_MAX = 500   # cap entries (agency × params combinations)

# Facet lists (distinct agencies / categories / industries + counts) and dashboard
# top-N widgets. Both scan the S3 Parquet, so cache per fiscal-year for 24h.
_spending_facets_cache: Dict[str, Any] = {}
_spending_top_cache: Dict[str, Any] = {}
_subvendor_cache: Dict[str, Any] = {}
_mwbe_cache: Dict[str, Any] = {}
SPENDING_AGG_CACHE_TTL = 86400  # 24 hours — spending data refreshes daily

# Contract spend map — SUM(check_amount) per contract from the spending Parquet,
# keyed by normalized_contract_id (the #20 crosswalk). One full-history scan, cached
# 24h (ideally scheduler-precomputed). Powers spent-to-date / utilization on contracts.
_contract_spend_cache: Dict[str, Any] = {'data': None, 'ts': 0}
CONTRACT_SPEND_CACHE_TTL = 86400  # 24 hours

# Persistent DuckDB connection for spending/transactions queries. Reused across
# requests so DuckDB's HTTP metadata + object cache stay warm — re-reading the
# S3 Parquet footers on every request is the dominant cost. Per-query work uses
# .cursor() so it's safe under to_duckdb_thread.
_spending_con = None

def _persistent_spending_connection():
    global _spending_con
    if _spending_con is None:
        con = duckdb.connect()
        con.execute("INSTALL httpfs; LOAD httpfs;")
        # Cap DuckDB memory to fit the container cgroup. By default DuckDB sizes
        # its budget to ~80% of HOST RAM (~12 GB here) with no knowledge of the
        # container's 3 GB limit, so a heavy Parquet scan could allocate past the
        # cap mid-query and get OOM-killed. 2 GB (not 1) for this shared workhorse
        # connection: it serves the dashboard's heavy scans (Top-N/facets), and
        # 1 GB forced heavy spilling that pushed cold spending/top to ~16s. 2 GB +
        # ~0.25 GB Python stays well under the 3 GB cap; it spills beyond that.
        con.execute("SET memory_limit='2GB'; SET threads=2;")
        # Keep S3 file metadata/footers cached between requests. Wrapped defensively
        # since setting names vary across DuckDB versions.
        for pragma in ("SET enable_http_metadata_cache=true;", "SET enable_object_cache=true;"):
            try:
                con.execute(pragma)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[spending] could not apply pragma {pragma!r}: {exc}")
        _spending_con = con
    return _spending_con


# The fiscal year the /procurement/transactions dashboard defaults to. Kept in
# sync with ProcurementController@transactions (currently 2026); the dashboard's
# client-side widgets request this FY, so we pre-warm exactly these response
# caches to avoid the ~15s cold-scan blank-widget window after a restart.
_DASHBOARD_PREWARM_FY = 2026


async def prewarm_transactions_metadata():
    """Warm DuckDB's Parquet metadata cache AND the spending-dashboard response
    caches so the first visitor to /procurement/transactions after a restart
    doesn't hit the cold ~15s scans and see blank Top-N / totals.

    Runs inside the sequential startup pre-warm, so these heavy scans execute one
    at a time (bounded memory), not concurrently on a cold cache.
    """
    def _warm_meta():
        con = _persistent_spending_connection().cursor()
        files = get_spending_files(None)  # default 5 recent years — reads footers only
        con.execute(f"SELECT COUNT(*) FROM read_parquet({files})").fetchone()
        con.close()

    try:
        logger.info("[cache] Pre-warming transactions metadata + dashboard...")
        await to_duckdb_thread(_warm_meta)
        # Warm the dashboard's actual endpoint response caches for the default FY,
        # in the same order the page loads them. Each is guarded so one slow/failed
        # scan can't abort the rest.
        fy = _DASHBOARD_PREWARM_FY
        warmers = [
            ("spending/top", get_spending_top(fiscal_year=fy, limit=5)),
            ("transactions/facets", get_transactions_facets(fiscal_year=fy)),
            ("spending/subvendors", get_subvendors(fiscal_year=fy, limit=8)),
            ("transactions summary", list_transactions(fiscal_year=fy, limit=1)),
            ("transactions/charts", get_transactions_charts()),
            ("spending/capital-by-year", get_capital_spending_by_year(years=10)),
        ]
        for label, coro in warmers:
            try:
                await coro
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[cache] dashboard warm '{label}' failed: {exc}")
        logger.info("[cache] Transactions metadata + dashboard warmed.")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[cache] transactions pre-warm failed: {exc}")

# ============================================================================
# Helpers
# ============================================================================

def get_spending_connection():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    # Bound DuckDB memory to the container budget (spills instead of OOM-killing
    # the container); DuckDB otherwise targets ~80% of host RAM. See the note in
    # _persistent_spending_connection.
    con.execute("SET memory_limit='1GB'; SET threads=2;")
    return con

# Per-year chunk counts — only needed in S3 mode (HTTPS can't list a bucket, so the
# chunk files must be enumerated by name). In local mode DuckDB globs the directory,
# so this map is irrelevant and never consulted. Verified via S3 HEAD (2026-02-13).
_CHUNKS_PER_YEAR = {
    2026: 8, 2025: 14, 2024: 17, 2023: 16, 2022: 16,
    2021: 13, 2020: 8, 2019: 16, 2018: 15, 2017: 15,
    2016: 15, 2015: 14, 2014: 14, 2013: 12, 2012: 12,
    2011: 13, 2010: 7,
}


def _local_spending_years() -> list:
    """Local-lake year-set derived by globbing `fiscal_year=*` dirs on disk, so the
    scheduled refresh (scripts/oce-refresh.sh) picking up a brand-new FY needs no code
    change. Returns [] if the base isn't a readable local directory."""
    base = SPENDING_DATA_BASE
    out = []
    try:
        for name in os.listdir(base):
            if name.startswith("fiscal_year=") and os.path.isdir(os.path.join(base, name)):
                try:
                    out.append(int(name.split("=", 1)[1]))
                except ValueError:
                    pass
    except OSError:
        return []
    return sorted(out, reverse=True)


def get_spending_files(fiscal_year: int = None, all_years: bool = False) -> str:
    """Return a DuckDB read_parquet() file argument (a `[...]` list literal) for the
    requested fiscal year(s). S3 mode enumerates chunk files; local mode globs each
    year's directory (and skips years not present, so a partial local backfill works)."""
    if fiscal_year:
        years = [fiscal_year]
    elif all_years:
        # Full history — used for contract spent-to-date (cumulative over a contract's life).
        # Local mode derives the year-set from disk (so a newly-ingested FY is included
        # automatically); S3 mode falls back to the static chunk map.
        years = (_local_spending_years() if _spending_base_is_local() else []) \
            or sorted(_CHUNKS_PER_YEAR.keys(), reverse=True)
    else:
        # Default to recent 5 years for performance.
        years = [2026, 2025, 2024, 2023, 2022]

    base = SPENDING_DATA_BASE
    if _spending_base_is_local():
        # Local disk: DuckDB globs a directory — no chunk enumeration needed.
        pats = [f"'{base}/fiscal_year={fy}/*.parquet'"
                for fy in years if os.path.isdir(f"{base}/fiscal_year={fy}")]
        if not pats:  # requested years not migrated yet — glob them anyway (errors clearly)
            pats = [f"'{base}/fiscal_year={fy}/*.parquet'" for fy in years]
        return "[" + ", ".join(pats) + "]"

    # S3 over HTTPS: enumerate chunk files (no bucket listing available).
    urls = []
    for fy in years:
        for chunk in range(1, _CHUNKS_PER_YEAR.get(fy, 10) + 1):
            urls.append(f"'{base}/fiscal_year={fy}/chunk_{chunk:04d}.parquet'")
    return "[" + ", ".join(urls) + "]"

def format_currency(amount):
    if amount is None:
        return "N/A"
    try:
        return f"${float(amount):,.2f}"
    except (ValueError, TypeError):
        return "N/A"

def _get_checkbook_summary() -> dict:
    """Query Parquet spending for total and yearly breakdown across all FYs.
    
    Returns dict with 'total', 'transactions', and 'by_year' keys.
    Runs synchronously — call via to_duckdb_thread.
    """
    con = get_spending_connection()
    # 5 most recent years for the dashboard summary (the get_spending_files default).
    files = get_spending_files(None)
    try:
        total_row = con.execute(
            f"SELECT SUM(TRY_CAST(check_amount AS DOUBLE)) as t, COUNT(*) as c "
            f"FROM read_parquet({files})"
        ).fetchone()
        yearly = con.execute(
            f"SELECT fiscal_year, SUM(TRY_CAST(check_amount AS DOUBLE)) as t, COUNT(*) as c "
            f"FROM read_parquet({files}) GROUP BY fiscal_year ORDER BY fiscal_year"
        ).fetchall()
        return {
            'total': total_row[0] if total_row else 0,
            'transactions': total_row[1] if total_row else 0,
            'by_year': [
                {'year': int(r[0]), 'total': r[1], 'count': r[2]}
                for r in yearly
            ]
        }
    except Exception as e:
        print(f"Checkbook summary error: {exc_str(e)}")
        return {'total': 0, 'transactions': 0, 'by_year': []}
    finally:
        con.close()

# ============================================================================
# Endpoints
# ============================================================================

@router.get("/dashboard/stats")
async def get_dashboard_stats():
    # Serve from cache if fresh (avoids expensive re-computation)
    if _dashboard_cache['data'] and (time.time() - _dashboard_cache['timestamp']) < DASHBOARD_CACHE_TTL:
        age = int(time.time() - _dashboard_cache['timestamp'])
        logger.info(f"Serving dashboard stats from cache (age: {age}s)")
        return _dashboard_cache['data']
    
    logger.info("Dashboard stats cache miss — running full query from oce.db")
    stats = {}
    
    # Query contracts/solicitations/vendors from Postgres
    try:
        async def _query_oce_stats():
            stats_local = {}
            r = await PostgresModelAsync.select_safe("SELECT count(*) as c FROM contracts")
            stats_local['contracts'] = r[0]['c'] if r else 0
            r = await PostgresModelAsync.select_safe("SELECT count(*) as c FROM solicitations")
            stats_local['solicitations'] = r[0]['c'] if r else 0
            r = await PostgresModelAsync.select_safe("SELECT count(*) as c FROM vendors")
            stats_local['vendors'] = r[0]['c'] if r else 0
            r = await PostgresModelAsync.select_safe("SELECT count(DISTINCT agency) as c FROM contracts WHERE agency IS NOT NULL AND agency != ''")
            ag1 = r[0]['c'] if r else 0
            r = await PostgresModelAsync.select_safe("SELECT count(DISTINCT \"Agency\") as c FROM solicitations WHERE \"Agency\" IS NOT NULL AND \"Agency\" != ''")
            ag2 = r[0]['c'] if r else 0
            stats_local['agencies'] = max(ag1, ag2)

            r = await PostgresModelAsync.select_safe("SELECT COALESCE(SUM(award_amount), 0) as total FROM contracts")
            stats_local['awarded'] = float(r[0]['total']) if r else 0

            # Top agencies by spending
            rows = await PostgresModelAsync.select_safe("""
                SELECT agency, SUM(award_amount) as total
                FROM contracts
                WHERE agency IS NOT NULL AND agency != ''
                GROUP BY agency ORDER BY total DESC LIMIT 8
            """)
            stats_local['agencies_chart'] = [{'label': r['agency'][:30], 'value': float(r['total'] or 0)} for r in (rows or [])]

            # Top vendors by spending
            rows = await PostgresModelAsync.select_safe("""
                SELECT vendor_name, SUM(award_amount) as total
                FROM contracts
                WHERE vendor_name IS NOT NULL AND vendor_name != ''
                GROUP BY vendor_name ORDER BY total DESC LIMIT 8
            """)
            stats_local['vendors_chart'] = [{'label': r['vendor_name'][:30], 'value': float(r['total'] or 0)} for r in (rows or [])]

            # Industries by spending
            rows = await PostgresModelAsync.select_safe("""
                SELECT industry, COUNT(*) as count, SUM(award_amount) as total
                FROM contracts
                WHERE industry IS NOT NULL AND industry != ''
                GROUP BY industry ORDER BY total DESC LIMIT 10
            """)
            stats_local['industries_chart'] = [{'label': r['industry'][:30], 'value': float(r['total'] or 0)} for r in (rows or [])]

            # Procurement methods by spending
            rows = await PostgresModelAsync.select_safe("""
                SELECT procurement_method, COUNT(*) as count, SUM(award_amount) as total
                FROM contracts
                WHERE procurement_method IS NOT NULL AND procurement_method != ''
                GROUP BY procurement_method ORDER BY total DESC LIMIT 10
            """)
            stats_local['methods_chart'] = [{'label': r['procurement_method'][:30], 'value': float(r['total'] or 0)} for r in (rows or [])]

            return stats_local

        oce_stats = await _query_oce_stats()
        stats['contracts'] = oce_stats['contracts']
        stats['vendors'] = oce_stats['vendors']
        stats['solicitations'] = oce_stats['solicitations']
        stats['agencies'] = oce_stats['agencies']
        stats['awarded'] = oce_stats['awarded']
    except Exception as e:
        logger.error(f"OCE stats query failed: {exc_str(e)}")
        stats = {'contracts': 0, 'vendors': 0, 'solicitations': 0, 'agencies': 0, 'awarded': 0}
        oce_stats = {}
    
    # Total Spending (from Checkbook S3 Parquet - actual payments)
    try:
        checkbook = await to_duckdb_thread(_get_checkbook_summary)
        stats['spending'] = checkbook['total']
        stats['transactions'] = checkbook['transactions']
    except Exception:
        checkbook = {'total': 0, 'transactions': 0, 'by_year': []}
        stats['spending'] = stats.get('awarded', 0)
        stats['transactions'] = 0
    
    # Spending Over Time (Checkbook)
    time_data = {'labels': [], 'values': []}
    for yr in checkbook.get('by_year', []):
        time_data['labels'].append(f"FY{yr['year']}")
        time_data['values'].append(yr['total'])
    
    # Charts from oce.db
    agencies_data = {'labels': [r['label'] for r in oce_stats.get('agencies_chart', [])],
                     'values': [r['value'] for r in oce_stats.get('agencies_chart', [])]}
    vendors_data = {'labels': [r['label'] for r in oce_stats.get('vendors_chart', [])],
                    'values': [r['value'] for r in oce_stats.get('vendors_chart', [])]}
    industries_data = {'labels': [r['label'] for r in oce_stats.get('industries_chart', [])],
                       'values': [r['value'] for r in oce_stats.get('industries_chart', [])]}
    methods_data = {'labels': [r['label'] for r in oce_stats.get('methods_chart', [])],
                    'values': [r['value'] for r in oce_stats.get('methods_chart', [])]}

    stats['charts'] = {
        'time': time_data,
        'agencies': agencies_data,
        'vendors': vendors_data,
        'industries': industries_data,
        'methods': methods_data
    }
    
    # Cache the result
    _dashboard_cache['data'] = stats
    _dashboard_cache['timestamp'] = time.time()
    logger.info("Dashboard stats cached successfully")
    
    return stats


async def refresh_dashboard_cache():
    """Force-refresh the dashboard stats cache.
    
    Called by the data scheduler after the daily ingestion cycle completes,
    and at API startup to pre-warm the cache so users never hit a cold query.
    """
    logger.info("[cache] Refreshing procurement dashboard stats...")
    # Invalidate so get_dashboard_stats() runs the full query
    _dashboard_cache['data'] = None
    _dashboard_cache['timestamp'] = 0
    try:
        await get_dashboard_stats()
        logger.info("[cache] Dashboard stats cache refreshed successfully")
    except Exception as e:
        logger.error(f"[cache] Failed to refresh dashboard stats: {exc_str(e)}")


async def refresh_digital_reform_cache():
    """Pre-warm the digital reform combined endpoint cache.
    
    Called at API startup and after the daily data pipeline cycle,
    following the same pattern as refresh_dashboard_cache.
    """
    logger.info("[cache] Pre-warming digital reform cache...")
    _digital_reform_cache.clear()
    try:
        await get_digital_reform_all()  # default params = page 1 for all sections
        logger.info("[cache] Digital reform cache warmed successfully")
    except Exception as e:
        logger.error(f"[cache] Failed to warm digital reform cache: {exc_str(e)}")

@router.get("/vendors")
async def list_vendors(
    page: int = 1, 
    limit: int = 50, 
    q: Optional[str] = None,
    sort: str = 'name',
    order: str = 'asc',
    category: Optional[str] = None,
    mwbe: Optional[str] = None,
    # Data missing for these but kept for API compatibility potential
    filter: Optional[str] = None, 
    tag: Optional[str] = None
):
    offset = (max(page, 1) - 1) * limit
    
    where_clauses = []
    params = []
    param_idx = 1
    
    if q:
        # Postgres ILIKE is better for case insensitive search
        where_clauses.append(f"(\"Vendor Name\" ILIKE ${param_idx} OR \"PASSPort Supplier-ID\" ILIKE ${param_idx+1})")
        params.extend([f"%{q}%", f"%{q}%"])
        param_idx += 2
        
    if category:
        where_clauses.append(f"\"Business Category\" = ${param_idx}")
        params.append(category)
        param_idx += 1
        
    if mwbe:
        if mwbe == 'Any MWBE':
            where_clauses.append(f"(\"Certification Type\" IS NOT NULL AND \"Certification Type\" != '' AND \"Certification Type\" != 'Non-MWBE')")
        elif mwbe == 'MBE':
             where_clauses.append(f"\"Certification Type\" LIKE ${param_idx}")
             params.append('%MBE%')
             param_idx += 1
        elif mwbe == 'WBE':
             where_clauses.append(f"\"Certification Type\" LIKE ${param_idx}")
             params.append('%WBE%')
             param_idx += 1
        elif mwbe == 'Non-MWBE':
             where_clauses.append(f"\"Certification Type\" = 'Non-MWBE'")
        
    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Sort mapping
    valid_sorts = {
        'name': 'v."Vendor Name"',
        'contracts': 'contract_count',
        'amount': 'total_awarded'
    }
    sql_sort = valid_sorts.get(sort, '"Vendor Name"')
    sql_order = 'DESC' if order == 'desc' else 'ASC'
    
    # Use CTE for O(n+m) performance instead of O(n*m) correlated subqueries
    data_sql = f"""
        WITH vendor_stats AS (
            SELECT vendor_name, COUNT(*) as contract_count, COALESCE(SUM(award_amount), 0) as total_awarded
            FROM contracts WHERE vendor_name IS NOT NULL GROUP BY vendor_name
        )
        SELECT v.*, COALESCE(vs.contract_count, 0) as contract_count, COALESCE(vs.total_awarded, 0) as total_awarded
        FROM vendors v
        LEFT JOIN vendor_stats vs ON vs.vendor_name = v."Vendor Name"
        {where_str}
        ORDER BY {sql_sort} {sql_order}
        LIMIT ${param_idx} OFFSET ${param_idx+1}
    """
    
    count_sql = f"SELECT count(*) as c FROM vendors {where_str}"
    
    rows = await PostgresModelAsync.select_safe(data_sql, params + [limit, offset])
    total_res = await PostgresModelAsync.select_safe(count_sql, params)
    total = total_res[0]['c'] if total_res else 0
    
    # Metadata for Sidebar
    # Ideally distinct queries, but hardcoded for speed/legacy match
    categories = [
        "Commercial Services", "Construction", "Distribution", 
        "Human Services", "Manufacturing", "Nonprofit", 
        "Professional Services", "Retail"
    ]
    mwbe_options = ["Any MWBE", "MBE", "WBE", "Non-MWBE"]
    
    return {
        "data": rows,
        "total": total,
        "page": page,
        "pages": math.ceil(total / limit),
        "categories": categories,
        "mwbe_options": mwbe_options
    }

async def _notices_for_epins(epins: list) -> list:
    """City Record notices whose PIN exactly matches any of these contract EPINs
    (the accurate id-based link). Live indexed join; guarded against blank/short
    EPINs (which would match the ~5M empty-PIN notices)."""
    clean = list({e.strip() for e in epins if e and len(str(e).strip()) >= 6})
    if not clean:
        return []
    try:
        rows = await PostgresModelAsync.select_safe(
            """
            SELECT "RequestID" AS rid, "ShortTitle" AS title, "AgencyName" AS agency,
                   "TypeOfNoticeDescription" AS type, "StartDate" AS date
            FROM crol
            WHERE trim("PIN") = ANY($1)
            ORDER BY start_date_parsed DESC NULLS LAST
            LIMIT 25
            """,
            [clean],
        )
        return [{
            "title": n.get("title") or "Notice",
            "type": n.get("type") or "",
            "agency": n.get("agency") or "",
            "date": (n.get("date") or "")[:10],
            "url": f"https://a856-cityrecord.nyc.gov/RequestDetail/{n['rid']}",
        } for n in (rows or [])]
    except Exception as exc:  # noqa: BLE001
        # ALERTS: the City Record notices panel on solicitation/contract/vendor pages, gone for everyone.
        logger.error(f"[oce] notices-for-epins query failed: {exc}")
        return []


# --- SBS certified-business enrichment ---------------------------------------
# `sbscertifiedbiz` is the Dept of Small Business Services directory of certified
# M/WBE / EBE / LBE firms. It carries what PASSPort does NOT: what the firm
# actually DOES (NAICS sector + free-text description), website/phone, year
# established, bonding capacity, union-signatory status, and up to three
# self-reported past-performance jobs. ~11.5k rows, of which ~6.3k (54%) match a
# PASSPort vendor by normalized name.
#
# Matched LIVE on a normalized name rather than through a stored crosswalk: there
# is no shared identifier between SBS and PASSPort, and the table is small enough
# that the scan is trivial next to the request's other work. Also tries the DBA
# name, since firms are certified under a formal name but contract under a trade
# name. Guarded — a missing table or bad row must never break the vendor profile.
_SBS_JOB_FIELDS = (
    # (client, value, date, description) — note job 1's value column is named
    # inconsistently in the source dataset (`Largest_Value_of_Contract`).
    ("Name_of_Client_Job_Exp_1", "Largest_Value_of_Contract",
     "Date_of_Work_Job_Exp_1", "Description_of_Work_Job_Exp_1"),
    ("Name_of_Client_Job_Exp_2", "Value_of_Contract_Job_Exp_2",
     "Date_of_Work_Job_Exp_2", "Description_of_Work_Job_Exp_2"),
    ("Name_of_Client_Job_Exp_3", "Value_of_Contract_Job_Exp_3",
     "Date_of_Work_Job_Exp_3", "Description_of_Work_Job_Exp_3"),
)

_SBS_SQL = """
    SELECT "Account_Number", "Vendor_Formal_Name", "Vendor_DBA", "Business_Description",
           "Certification", "Certification_Renewal_Date", "Website", "telephone",
           "Date_Of_Establishment", "Aggregate_Bonding_Limit",
           "Signatory_To_Union_Contracts", "NAICS_Title", "NAICS_Sector",
           "NAICS_Subsector", "ID6_digit_NAICS_code",
           "Types_of_Construction_Projects_Performed", "Capacity_Building_Programs",
           "Enrolled_in_PASSPort", "Borough", "City", "State",
           "Name_of_Client_Job_Exp_1", "Largest_Value_of_Contract",
           "Date_of_Work_Job_Exp_1", "Description_of_Work_Job_Exp_1",
           "Name_of_Client_Job_Exp_2", "Value_of_Contract_Job_Exp_2",
           "Date_of_Work_Job_Exp_2", "Description_of_Work_Job_Exp_2",
           "Name_of_Client_Job_Exp_3", "Value_of_Contract_Job_Exp_3",
           "Date_of_Work_Job_Exp_3", "Description_of_Work_Job_Exp_3"
    FROM sbscertifiedbiz
    WHERE upper(regexp_replace("Vendor_Formal_Name", '[^A-Za-z0-9]', '', 'g')) = $1
       OR upper(regexp_replace("Vendor_DBA", '[^A-Za-z0-9]', '', 'g')) = $1
    LIMIT 1
"""


def _s(row: dict, key: str) -> str:
    """Trimmed string cell ('' when absent/blank) — the SBS table is all text."""
    return (row.get(key) or "").strip()


async def _sbs_profile(vendor_name: str) -> Optional[dict]:
    """SBS certified-business record for a vendor name, or None."""
    key = re.sub(r"[^A-Za-z0-9]", "", (vendor_name or "").upper())
    if not key:
        return None
    try:
        rows = await PostgresModelAsync.select_safe(_SBS_SQL, [key])
    except Exception as exc:  # noqa: BLE001 — best-effort enrichment
        logger.warning(f"[oce] SBS lookup failed for {vendor_name!r}: {exc}")
        return None
    if not rows:
        return None
    r = rows[0]
    jobs = []
    for client_f, value_f, date_f, desc_f in _SBS_JOB_FIELDS:
        client = _s(r, client_f)
        if not client:
            continue
        jobs.append({"client": client, "value": _s(r, value_f),
                     "date": _s(r, date_f), "description": _s(r, desc_f)})
    return {
        "account_number": _s(r, "Account_Number"),
        "formal_name": _s(r, "Vendor_Formal_Name"),
        "dba": _s(r, "Vendor_DBA"),
        "description": _s(r, "Business_Description"),
        "certification": _s(r, "Certification"),
        "certification_renewal": _s(r, "Certification_Renewal_Date")[:10],
        "website": _s(r, "Website"),
        "telephone": _s(r, "telephone"),
        "established": _s(r, "Date_Of_Establishment")[:10],
        "bonding_limit": _s(r, "Aggregate_Bonding_Limit"),
        "union_signatory": _s(r, "Signatory_To_Union_Contracts"),
        "naics_title": _s(r, "NAICS_Title"),
        "naics_sector": _s(r, "NAICS_Sector"),
        "naics_subsector": _s(r, "NAICS_Subsector"),
        "naics_code": _s(r, "ID6_digit_NAICS_code"),
        "construction_types": _s(r, "Types_of_Construction_Projects_Performed"),
        "capacity_programs": _s(r, "Capacity_Building_Programs"),
        "enrolled_in_passport": _s(r, "Enrolled_in_PASSPort"),
        "borough": _s(r, "Borough"),
        "city": _s(r, "City"),
        "state": _s(r, "State"),
        "jobs": jobs,
    }


# --- PASSPort vendor sub-tables ----------------------------------------------
# MOCS publishes five companion exports to the vendor list that PASSPort itself
# displays and Databook never has: who runs the company (vendor_principals),
# agency performance ratings (vendor_evaluations), the registered entity record
# incl. the only populated DUNS we have (vendor_entity_summary), the corporate
# family (vendor_related_entities) and DBA history (vendor_other_names).
# Loaded by api/enrich_vendor.py on the daily `vendors` ingest.
#
# All five key on `vendor_name_norm`, the [A-Z0-9] skeleton of the vendor name
# — the same key shape _sbs_profile uses. They come from the same MOCS system
# as `vendors`, so this is effectively a foreign key: 99.4-99.6% of principals /
# other-names / related-entity rows match, and 94% of vendors get a principals
# and entity-summary panel. Joined live; no crosswalk table, no human review.
#
# Caps: a single vendor can carry 1,141 evaluations and 384 related entities, so
# those two are rolled up with a bounded detail list rather than returned whole.
_EVAL_DETAIL_LIMIT = 25
_RELATED_LIMIT = 50
_OTHER_NAMES_LIMIT = 25

# Rating vocabulary, best to worst. Used to order the summary consistently and
# to decide what counts as adverse — the source has exactly these five values.
_RATING_ORDER = ["Excellent", "Good", "Satisfactory", "Poor", "Unsatisfactory"]
_ADVERSE_RATINGS = {"Poor", "Unsatisfactory"}


async def _passport_profile(vendor_name: str) -> Optional[dict]:
    """The five PASSPort sub-table panels for a vendor name, or None.

    Every query is individually guarded: on a fresh environment none of these
    tables exist yet, and a vendor profile must render fine without them.
    """
    key = re.sub(r"[^A-Za-z0-9]", "", (vendor_name or "").upper())
    if not key:
        return None

    # One catalog probe before the eight lookups. "Not loaded yet" is a normal
    # state — a fresh environment, or prod between a deploy and the first
    # enrich_vendor run — and it should cost one cheap query and log nothing,
    # not eight failed lookups and eight warnings on every vendor page view.
    try:
        probe = await PostgresModelAsync.select_safe(
            "SELECT to_regclass('public.vendor_principals') IS NOT NULL "
            "OR to_regclass('public.vendor_entity_summary') IS NOT NULL "
            "AS installed")
        if not (probe and probe[0].get("installed")):
            return None
    except Exception as exc:  # noqa: BLE001
        # ALERTS: this probe gates the WHOLE PASSPort block (principals, ratings, entity) for every vendor.
        logger.error(f"[oce] PASSPort sub-table probe failed: {exc}")
        return None

    async def q(sql: str, params: list) -> list:
        try:
            return await PostgresModelAsync.select_safe(sql, params) or []
        except Exception as exc:  # noqa: BLE001 — best-effort enrichment
            logger.warning(f"[oce] PASSPort sub-table query failed for "
                           f"{vendor_name!r}: {exc}")
            return []

    # ⚠ 80 vendors have two entity_summary rows (duplicate MOCS registrations).
    # Prefer the more complete one rather than an arbitrary LIMIT 1.
    entity_rows = await q(
        """SELECT address1, address2, city, state, zip, country, telephone,
                  symbol, for_profit, duns, revenue
           FROM vendor_entity_summary WHERE vendor_name_norm = $1
           ORDER BY (duns IS NOT NULL) DESC, (telephone IS NOT NULL) DESC,
                    (address1 IS NOT NULL) DESC
           LIMIT 1""", [key])

    principals = await q(
        """SELECT principal_name, title, ownership_type
           FROM vendor_principals WHERE vendor_name_norm = $1
             AND principal_name IS NOT NULL
           ORDER BY (ownership_type = 'Principal Owner') DESC,
                    principal_name""", [key])

    eval_summary = await q(
        """SELECT rating, count(*) AS n,
                  count(DISTINCT agency) AS agencies,
                  max(eval_date) AS latest
           FROM vendor_evaluations WHERE vendor_name_norm = $1
           GROUP BY rating""", [key])

    eval_rows = await q(
        f"""SELECT agency, contract_id, purpose, eval_date, start_date,
                   end_date, rating
            FROM vendor_evaluations WHERE vendor_name_norm = $1
            ORDER BY eval_date DESC NULLS LAST
            LIMIT {_EVAL_DETAIL_LIMIT}""", [key])

    related = await q(
        f"""SELECT related_entity_name, relationship, city, state, country
            FROM vendor_related_entities WHERE vendor_name_norm = $1
              AND related_entity_name IS NOT NULL
            ORDER BY relationship, related_entity_name
            LIMIT {_RELATED_LIMIT}""", [key])
    related_total = await q(
        "SELECT count(*) AS n FROM vendor_related_entities "
        "WHERE vendor_name_norm = $1", [key])

    other_names = await q(
        f"""SELECT type, other_name, from_date, to_date
            FROM vendor_other_names WHERE vendor_name_norm = $1
              AND other_name IS NOT NULL
            ORDER BY (to_date = 'Present') DESC, type, other_name
            LIMIT {_OTHER_NAMES_LIMIT}""", [key])

    if not (entity_rows or principals or eval_summary or related or other_names):
        return None

    # Evaluations rollup. `ratings` keeps source order so a profile always reads
    # Excellent -> Unsatisfactory, and `adverse` is called out because a Poor or
    # Unsatisfactory MOCS rating is the single most newsworthy fact here.
    counts = {r["rating"]: int(r["n"] or 0) for r in eval_summary if r.get("rating")}
    total_evals = sum(counts.values())
    evaluations = None
    if total_evals:
        evaluations = {
            "total": total_evals,
            "ratings": [{"rating": r, "count": counts[r]}
                        for r in _RATING_ORDER if counts.get(r)]
                       + [{"rating": r, "count": n}
                          for r, n in sorted(counts.items())
                          if r not in _RATING_ORDER],
            "adverse": sum(n for r, n in counts.items() if r in _ADVERSE_RATINGS),
            "agencies": max((int(r["agencies"] or 0) for r in eval_summary),
                            default=0),
            "latest": max((r["latest"] or "" for r in eval_summary),
                          default="")[:10],
            "showing": len(eval_rows),
            "recent": [{
                "agency": (r.get("agency") or "").strip(),
                "contract_id": (r.get("contract_id") or "").strip(),
                "purpose": (r.get("purpose") or "").strip(),
                "date": (r.get("eval_date") or "")[:10],
                "period_start": (r.get("start_date") or "")[:10],
                "period_end": (r.get("end_date") or "")[:10],
                "rating": (r.get("rating") or "").strip(),
            } for r in eval_rows],
        }

    entity = None
    if entity_rows:
        e = entity_rows[0]
        street = ", ".join(p for p in [_s(e, "address1"), _s(e, "address2")] if p)
        # City and state are separate columns with inconsistent casing
        # ('NEW YORK' / 'New York'); comma-separate them so the two do not run
        # together, and collapse the stray double spaces the source ships.
        locality = ", ".join(p for p in [_s(e, "city"), _s(e, "state")] if p)
        if _s(e, "zip"):
            locality = f"{locality} {_s(e, 'zip')}".strip()
        entity = {
            "address": re.sub(r"\s{2,}", " ",
                              ", ".join(p for p in [street, locality] if p)),
            "country": _s(e, "country"),
            "telephone": _s(e, "telephone"),
            "for_profit": _s(e, "for_profit"),
            # The only populated DUNS we hold — vendors."DUNS Number" is 0% filled.
            # Formatting is inconsistent at source ('008964249' vs '10-150-1608');
            # shown verbatim rather than guessing a canonical form.
            "duns": _s(e, "duns"),
            "revenue": _s(e, "revenue"),
            "symbol": _s(e, "symbol"),
        }
        if not any(entity.values()):
            entity = None

    return {
        "entity": entity,
        "principals": [{
            "name": (p.get("principal_name") or "").strip(),
            "title": (p.get("title") or "").strip(),
            "ownership_type": (p.get("ownership_type") or "").strip(),
        } for p in principals],
        "evaluations": evaluations,
        "related": {
            "total": int(related_total[0]["n"]) if related_total else len(related),
            "showing": len(related),
            "rows": [{
                "name": (r.get("related_entity_name") or "").strip(),
                "relationship": (r.get("relationship") or "").strip(),
                "location": " ".join(p for p in [_s(r, "city"), _s(r, "state")] if p),
            } for r in related],
        } if related else None,
        "other_names": [{
            "type": (n.get("type") or "").strip(),
            "name": (n.get("other_name") or "").strip(),
            "from": (n.get("from_date") or "")[:10],
            "to": (n.get("to_date") or "").strip(),
        } for n in other_names],
    }


# --- NY DOS legal-entity record -----------------------------------------------
# The NY Department of State corporate registry, materialized into
# `dos_entity_enrichment` by api/build_dos_crosswalk.py (a batch job — the
# registry is a 9 GB DuckDB file owned by the nycdb service, so it cannot be
# joined at request time). This is the only source here for how OLD a business
# is, and the only one describing its legal form rather than its procurement
# behaviour.
#
# ⚠ Three limits the UI must state, all inherent to the source:
#   * nycdb filters the registry to the FIVE NYC COUNTIES, so a legitimate
#     out-of-state vendor simply will not match;
#   * it is ACTIVE-only — dissolved entities are absent;
#   * matching is by normalized name (no shared id), 43% of vendors.
_DOS_SQL = """
    SELECT dos_id, entity_name, entity_type, jurisdiction, county,
           initial_filing_date, registered_agent, process_name, process_address
    FROM dos_entity_enrichment
    WHERE passport_supplier_id = $1 AND dos_id IS NOT NULL
    LIMIT 1
"""


async def _dos_profile(supplier_id: str) -> Optional[dict]:
    """NY DOS registration record for a vendor, or None when unmatched."""
    if not supplier_id:
        return None
    try:
        rows = await PostgresModelAsync.select_safe(_DOS_SQL, [supplier_id])
    except Exception as exc:  # noqa: BLE001 — table absent until the job runs
        logger.warning(f"[oce] DOS lookup failed for {supplier_id}: {exc}")
        return None
    if not rows:
        return None
    r = rows[0]

    filed = r.get("initial_filing_date")
    filed_iso = filed.isoformat() if hasattr(filed, "isoformat") else (filed or "")
    years = None
    if filed is not None and hasattr(filed, "year"):
        # Whole years since registration — the "business age" the procurement
        # data cannot give us. Guarded against a future-dated filing.
        today = datetime.now(timezone.utc).date()
        years = today.year - filed.year - ((today.month, today.day) < (filed.month, filed.day))
        if years < 0:
            years = None

    etype = (r.get("entity_type") or "").strip()
    return {
        "dos_id": (r.get("dos_id") or "").strip(),
        "entity_name": (r.get("entity_name") or "").strip(),
        # Registry values are SHOUTED ('DOMESTIC LIMITED LIABILITY COMPANY');
        # title-case them for display but leave the wording untouched.
        "entity_type": etype.title() if etype.isupper() else etype,
        "jurisdiction": (r.get("jurisdiction") or "").strip(),
        "county": (r.get("county") or "").strip(),
        "registered": filed_iso,
        "age_years": years,
        "registered_agent": (r.get("registered_agent") or "").strip(),
        "process_name": (r.get("process_name") or "").strip(),
        "process_address": (r.get("process_address") or "").strip(),
        "lookup_url": "https://apps.dos.ny.gov/publicInquiry/",
    }


# --- Doing Business Database (MOCS / Local Law 34) ----------------------------
# A second, independently maintained view of who runs a company — collected to
# enforce LL34's campaign-contribution limits rather than self-disclosed at
# vendor registration. Adds registered LOBBYISTS, which PASSPort has not got.
# Loaded by api/enrich_doing_business.py.
#
# ⚠ Joined ONLY through `doing_business_crosswalk.passport_supplier_id`, which
# the generator populates for exact and exact-DBA name matches only. Unreviewed
# near-misses live in `candidate_supplier_id` and therefore cannot leak into a
# profile through this join.
_DB_PEOPLE_LIMIT = 60


async def _doing_business_profile(supplier_id: str) -> Optional[dict]:
    """Doing Business principals for a PASSPort vendor, or None."""
    if not supplier_id:
        return None
    try:
        rows = await PostgresModelAsync.select_safe(
            """SELECT p.full_name, p.role_code, p.role_label, p.role_group,
                      p.is_organization, p.start_date, p.end_date,
                      x.organization_name, x.confidence
               FROM doing_business_crosswalk x
               JOIN doing_business_people p ON p.org_name_norm = x.org_name_norm
               WHERE x.passport_supplier_id = $1
               ORDER BY p.is_organization,
                        CASE p.role_group WHEN 'Principal officer' THEN 0
                                          WHEN 'Owner' THEN 1
                                          WHEN 'Senior manager' THEN 2
                                          WHEN 'Lobbyist' THEN 3 ELSE 4 END,
                        p.full_name""", [supplier_id])
    except Exception as exc:  # noqa: BLE001 — absent on a fresh env
        logger.warning(f"[oce] Doing Business lookup failed for {supplier_id}: {exc}")
        return None
    if not rows:
        return None

    entity = None
    try:
        erows = await PostgresModelAsync.select_safe(
            """SELECT e.ownership_structure_code, e.ownership_structure,
                      e.organization_phone, e.start_date
               FROM doing_business_crosswalk x
               JOIN doing_business_entities e ON e.org_name_norm = x.org_name_norm
               WHERE x.passport_supplier_id = $1 LIMIT 1""", [supplier_id])
        if erows:
            e = erows[0]
            entity = {
                # Falls back to the raw code when MOCS's own data dictionary does
                # not document it (it omits IND/JNT/GOV, and calls JNT "JV").
                "ownership_structure": _s(e, "ownership_structure")
                                       or _s(e, "ownership_structure_code"),
                "phone": _s(e, "organization_phone"),
                # Repaired at load time — every source date is missing its century.
                "doing_business_since": _s(e, "start_date"),
            }
            if not any(entity.values()):
                entity = None
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[oce] Doing Business entity lookup failed: {exc}")

    people, orgs = [], []
    for r in rows[:_DB_PEOPLE_LIMIT]:
        item = {
            "name": (r.get("full_name") or "").strip(),
            # Empty when MOCS publishes no public definition for the code; the
            # frontend then shows the bare code rather than inventing a meaning.
            "role": (r.get("role_label") or "").strip(),
            "role_code": (r.get("role_code") or "").strip(),
            "group": (r.get("role_group") or "").strip(),
            "since": (r.get("start_date") or "")[:10],
            "until": (r.get("end_date") or "")[:10],
        }
        if not item["name"]:
            continue
        # EWN rows are ORGANISATIONS that own >=10%, not people (99.9% have no
        # first name; the surname field holds names like GOLDMAN SACHS). Kept in
        # a separate list so the UI never labels a company as a person.
        (orgs if r.get("is_organization") else people).append(item)

    return {
        "organization_name": (rows[0].get("organization_name") or "").strip(),
        "match": (rows[0].get("confidence") or "").strip(),
        "entity": entity,
        "people": people,
        "organizations": orgs,
        "total": len(rows),
        "showing": min(len(rows), _DB_PEOPLE_LIMIT),
        "lobbyists": sum(1 for r in rows if r.get("role_group") == "Lobbyist"),
    }


async def _doing_business_as_of() -> str:
    """Vintage of the Doing Business feed ('' if unknown).

    ⚠ Always label this. The dataset advertises monthly automated updates but
    `rowsUpdatedAt` has read 2025-11-21 for at least eight months.
    """
    try:
        rows = await PostgresModelAsync.select_safe(
            "SELECT last_modified FROM vendor_enrichment_meta "
            "WHERE table_name = 'doing_business_people'")
    except Exception:  # noqa: BLE001
        return ""
    return ((rows[0].get("last_modified") if rows else "") or "")[:10]


async def _passport_as_of() -> str:
    """Publication date of the PASSPort sub-table exports ('' if unknown).

    ⚠ These five exports are refreshed only a few times a year while the vendor
    list itself is daily, so the pages that show them must say "as of" — an
    ownership panel that looks as fresh as the contract list would be a lie.
    """
    try:
        rows = await PostgresModelAsync.select_safe(
            "SELECT max(last_modified) AS lm FROM vendor_enrichment_meta")
    except Exception:  # noqa: BLE001 — table absent on a fresh env
        return ""
    lm = (rows[0].get("lm") if rows else None) or ""
    try:
        # HTTP date ('Tue, 03 Feb 2026 07:00:52 GMT') -> ISO day.
        return datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


@router.get("/vendor/{id}")
async def get_vendor(id: str, response: Response):
    """Get a single vendor profile with their contracts.

    Why: The Blade template (vendor_profile.blade.php) uses simplified field
    names like 'name', 'passport_supplier_id', etc. — not the raw DB column
    names. We transform the response to match.
    """
    vendor_res = await PostgresModelAsync.select_safe("SELECT * FROM vendors WHERE \"PASSPort Supplier-ID\" = $1", [id])
    if not vendor_res:
        raise HTTPException(status_code=404, detail="Vendor not found")
    v = vendor_res[0]

    vendor = {
        'name': v.get('Vendor Name', ''),
        'passport_supplier_id': v.get('PASSPort Supplier-ID', ''),
        'status': v.get('PASSPort Vendor Status', ''),
        'fms_vendor_code': v.get('FMS Vendor Code', ''),
        'duns_number': v.get('DUNS Number', ''),
        'certification_type': v.get('Certification Type', ''),
        'ethnicity': v.get('Ethnicity', ''),
        'business_category': v.get('Business Category', ''),
        'corporate_structure': v.get('Corporate Structure', ''),
    }

    # ⚠⚠ ONE ROW PER CONTRACT, NOT PER AMENDMENT. `contracts` carries a row per
    # amendment / change order — 53,260 rows for 36,421 distinct contract_ids,
    # 32% duplicates — and the Checkbook spend map is keyed on contract_id. So
    # listing every row attributed the SAME paid figure to each amendment and then
    # summed them: ACCENTURE's CT1-057-20228806565 appears 4 times, each carrying
    # the whole $13.3M, which is how the profile reported paying 197.9% of what it
    # awarded. Both `paid` and `awarded` were inflated by amendment count.
    #
    # Keeps the row with the largest current value, which is the contract's current
    # state — amendments RESTATE the total, they do not add to it (verified on the
    # Ivalua contract, whose amendment rows run 2.3 / 3.1 / 3.9 / 6.5 / 17.8 / 37.9
    # where 37.9 is the whole agreement, not the sum).
    #
    # ⚠ Keyed on `coalesce(contract_id, ctid)`, NEVER on contract_id alone: 2,546
    # rows across 1,866 vendors have NO contract_id (the unregistered rows keyed on
    # EPIN), and a bare DISTINCT ON would collapse all of one vendor's into a single
    # row — INFOPEOPLE CORPORATION has 11, so ten real contracts would vanish from
    # the page. Verified: all 11 survive.
    contracts = await PostgresModelAsync.select_safe(
        "SELECT * FROM ("
        "  SELECT DISTINCT ON (coalesce(contract_id, 'row:' || ctid::text)) * "
        "  FROM contracts WHERE vendor_name = $1 "
        "  ORDER BY coalesce(contract_id, 'row:' || ctid::text), "
        "           current_amount DESC NULLS LAST, award_amount DESC NULLS LAST"
        ") x ORDER BY award_amount DESC NULLS LAST", [v['Vendor Name']])

    # Checkbook ACTUALS for this vendor's contracts, via the #20 normalized-id
    # crosswalk — the same in-process map /oce/contracts already uses. The vendor
    # profile previously showed award amounts only: no paid-to-date anywhere, even
    # though contracts, agencies and NYCHA all show it.
    spend_map = await _get_contract_spend_map()
    _spend_cache_headers(response, spend_map)
    awarded = paid = 0.0
    # ⚠ Master-agreement ceilings, kept SEPARATE from awarded money. A master
    # carries no payments under its own id (measured: 0 of 57 on the renewal
    # queue, against 88% of ordinary contracts), so counting its ceiling in the
    # denominator of `pct_used` understates utilisation for every vendor holding
    # one — ACCENTURE's book alone carries $52.5M of it. See modules/contractkind.
    ceiling = 0.0
    ceiling_count = 0
    payments = 0
    for c in (contracts or []):
        key = _normalize_contract_id(c.get('normalized_contract_id') or c.get('contract_id'))
        _add_contract_spend(c, spend_map.get(key) if key else None)
        paid += c.get('spent_to_date') or 0.0
        payments += c.get('payment_count') or 0
        # Per-row, so the Contracts list can label a ceiling instead of rendering
        # it identically to committed money.
        is_ceiling = contractkind.is_master(c.get('contract_id'))
        c['amount_kind'] = 'ceiling' if is_ceiling else 'committed'
        try:
            amt = float(c.get('award_amount') or 0)
        except (TypeError, ValueError):
            amt = 0.0
        if is_ceiling:
            ceiling += amt
            ceiling_count += 1
        else:
            awarded += amt
    spend = {
        # `available` is honest about a cold map: _get_contract_spend_map() returns
        # {} on the first call while it populates in the background, and rendering
        # a $0 "paid" tile for a vendor with real payments would be worse than
        # rendering nothing. The frontend gates on this.
        "available": bool(spend_map),
        # ⚠ `awarded` is now COMMITTED money only, and `pct_used` divides by it.
        # Including master ceilings in that denominator understated utilisation
        # for every vendor holding one, because a master's draws are filed under
        # the purchase orders agencies raise against it, never under its own id.
        "awarded": awarded, "paid": paid, "payments": payments,
        "pct_used": round(paid / awarded * 100, 1) if awarded > 0 else None,
        # Reported beside it, never added into it — the Overview's pipeline block
        # established this convention: name the key `ceiling` so it resists
        # being summed with money.
        "ceiling": ceiling, "ceiling_count": ceiling_count,
    }

    # SBS certified-business profile (what the firm does, contact, capacity, past
    # performance). Guarded inside the helper.
    sbs = await _sbs_profile(v.get('Vendor Name', ''))

    # PASSPort sub-tables: ownership, MOCS performance ratings, registered
    # entity record, corporate family, DBA history. Guarded inside the helper.
    # NY DOS legal-entity record (age, entity type, county, registered agent).
    dos = await _dos_profile(id)

    passport = await _passport_profile(v.get('Vendor Name', ''))
    if passport:
        passport["as_of"] = await _passport_as_of()

    # Doing Business (LL34): a second custodian's view of the same company, plus
    # registered lobbyists. Linked on exact name only — see _doing_business_profile.
    doing_business = await _doing_business_profile(id)
    if doing_business:
        doing_business["as_of"] = await _doing_business_as_of()

    # Related City Record notices via this vendor's contract EPINs (id-based, not name).
    related_notices = await _notices_for_epins([c.get('epin', '') for c in (contracts or [])])

    # NYCHA activity (crosswalked vendors only): reverse-lookup this PASSPort id
    # in nycha_vendor_crosswalk (built by build_nycha_vendor_crosswalk.py), then
    # aggregate the NYCHA DuckDB lake for the matched raw name(s). Guarded — the
    # crosswalk table and the NYCHA lake are optional (fresh envs), and a hiccup
    # here must never break the vendor profile.
    nycha = None
    try:
        xw = await PostgresModelAsync.select_safe(
            "SELECT nycha_vendor_name, confidence, match_score FROM nycha_vendor_crosswalk "
            "WHERE passport_supplier_id = $1", [id])
        names = [r['nycha_vendor_name'] for r in (xw or []) if r.get('nycha_vendor_name')]
        if names:
            from routers.nycha import vendor_activity_for_names
            act = await to_duckdb_thread(vendor_activity_for_names, names)
            if act:
                # Surface HOW the link was made (curated / exact / fuzzy + score) so
                # a name-matched join is auditable rather than presented as fact.
                best = (xw or [])[0]
                nycha = {"names": names,
                         "match": {"confidence": best.get("confidence") or "",
                                   "score": float(best["match_score"]) if best.get("match_score") is not None else None},
                         **act}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[oce] NYCHA vendor activity lookup failed for {id}: {exc}")

    # Is this vendor also a civic actor in the org register? (Track B.) Measured
    # 2026-07-31: 52 of 1,248 orgs are also PASSPort vendors — cultural
    # institutions, BIDs, service-delivery nonprofits, political consultancies.
    #
    # ⚠ Joined on `passport_supplier_id`, which by construction holds ONLY links
    # we stand behind; unreviewed candidates live in `candidate_supplier_id` and
    # therefore cannot leak through this query. That is the #146 lesson made
    # structural rather than left to every consumer to remember.
    #
    # ⚠ MULTIPLE orgs may legitimately share one vendor — `United Federation of
    # Teachers` is three register rows (the union plus two bargaining units), all
    # supplier 1713785 — so this is a LIST, not a single value.
    civic = []
    try:
        civic = await PostgresModelAsync.select_safe(
            "SELECT x.org_id, x.org_name, x.match_tier, x.match_score, "
            "       w.type AS org_type, w.display_name "
            "FROM org_vendor_crosswalk x "
            "JOIN wegov_orgs w ON w.id = x.org_id "
            "WHERE x.passport_supplier_id = $1 AND w.retired_at IS NULL "
            "ORDER BY x.org_name", [id]) or []
    except Exception as exc:  # noqa: BLE001
        # The crosswalk is optional (fresh envs) and a hiccup must never break
        # the vendor profile.
        logger.warning(f"[oce] org crosswalk lookup failed for {id}: {exc}")

    # Software product families this vendor supplies, for the "Software
    # Products" section. Optional and independently guarded: the licence tables
    # are derived, so a fresh environment simply has none and the section
    # does not render.
    # ⚠ Scoped to THIS vendor's own contracts by contract_id, not by name --
    # the name join already happened upstream when the profile was resolved,
    # and re-matching on the name here would risk a different answer.
    software = []
    try:
        software = await PostgresModelAsync.select_safe("""
            WITH mine AS (
                SELECT DISTINCT c.contract_id
                FROM contracts c
                WHERE lower(trim(c.vendor_name)) = (
                    SELECT lower(trim("Vendor Name")) FROM vendors
                    WHERE "PASSPort Supplier-ID" = $1 LIMIT 1)
                  AND c.contract_id IS NOT NULL
            )
            SELECT lf.family, lf.slug,
                   count(DISTINCT e.contract_id)      AS contracts,
                   max(d.summary)                     AS summary
            FROM digital_contract_enrichment e
            JOIN mine m       ON m.contract_id = e.contract_id
            JOIN license_family lf ON lf.product_raw = e.license_product
            LEFT JOIN license_family_description d ON d.family = lf.family
            WHERE e.is_license AND NOT lf.is_generic
            GROUP BY lf.family, lf.slug
            ORDER BY count(DISTINCT e.contract_id) DESC, lf.family
        """, [id]) or []
    except Exception as exc:  # noqa: BLE001
        logger.info(f"[oce] licence families unavailable for {id}: {exc_str(exc)}")

    return {
        "vendor": vendor,
        "contracts": contracts or [],
        "spend": spend,
        "sbs": sbs,
        "passport": passport,
        "doing_business": doing_business,
        "dos": dos,
        "related_notices": related_notices,
        "nycha": nycha,
        "civic_orgs": civic,
        "software": software,
    }


@router.get("/filter-options")
async def get_filter_options():
    """Get distinct values for filter dropdowns."""
    # Get contract statuses
    statuses_res = await PostgresModelAsync.select_safe(
        "SELECT DISTINCT status FROM contracts WHERE status IS NOT NULL ORDER BY status"
    )
    statuses = [r['status'] for r in statuses_res] if statuses_res else []
    
    # Get procurement methods
    methods_res = await PostgresModelAsync.select_safe(
        "SELECT DISTINCT procurement_method FROM contracts WHERE procurement_method IS NOT NULL ORDER BY procurement_method"
    )
    methods = [r['procurement_method'] for r in methods_res] if methods_res else []
    
    # Get industries
    industries_res = await PostgresModelAsync.select_safe(
        "SELECT DISTINCT industry FROM contracts WHERE industry IS NOT NULL ORDER BY industry"
    )
    industries = [r['industry'] for r in industries_res] if industries_res else []

    # Checkbook expense categories (Phase D — checkbook_contract_meta). Guarded so a
    # missing/empty table never breaks the (shared) filter-options endpoint.
    expense_categories = []
    try:
        ec_res = await PostgresModelAsync.select_safe(
            "SELECT DISTINCT expense_category FROM checkbook_contract_meta "
            "WHERE expense_category IS NOT NULL AND expense_category != '' ORDER BY expense_category"
        )
        expense_categories = [r['expense_category'] for r in (ec_res or [])]
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[filter-options] expense_category list failed: {exc}")

    # Get solicitation statuses
    sol_statuses_res = await PostgresModelAsync.select_safe(
        "SELECT DISTINCT \"RFx Status\" as rfx_status FROM solicitations WHERE \"RFx Status\" IS NOT NULL ORDER BY \"RFx Status\""
    )
    sol_statuses = [r['rfx_status'] for r in sol_statuses_res] if sol_statuses_res else []
    
    # Get solicitation methods
    sol_methods_res = await PostgresModelAsync.select_safe(
        "SELECT DISTINCT \"Procurement Method\" as procurement_method FROM solicitations WHERE \"Procurement Method\" IS NOT NULL ORDER BY \"Procurement Method\""
    )
    sol_methods = [r['procurement_method'] for r in sol_methods_res] if sol_methods_res else []
    
    # Get solicitation industries
    sol_industries_res = await PostgresModelAsync.select_safe(
        "SELECT DISTINCT \"Industry\" as industry FROM solicitations WHERE \"Industry\" IS NOT NULL ORDER BY \"Industry\""
    )
    sol_industries = [r['industry'] for r in sol_industries_res] if sol_industries_res else []
    
    return {
        "contracts": {
            "statuses": statuses,
            "methods": methods,
            "industries": industries,
            "expense_categories": expense_categories
        },
        "solicitations": {
            "statuses": sol_statuses,
            "methods": sol_methods,
            "industries": sol_industries
        }
    }

# ----------------------------------------------------------------------------
# Contract spend map — spent-to-date / utilization / timeline from the spending
# Parquet, joined onto the Postgres `contracts` via normalized_contract_id (#20).
# ----------------------------------------------------------------------------

def _normalize_contract_id(v: Optional[str]) -> Optional[str]:
    """Alnum-uppercase form — matches contracts.normalized_contract_id."""
    return re.sub(r"[^A-Z0-9]", "", (v or "").upper()) or None


def _fy_of(date_str: Optional[str]) -> Optional[int]:
    """NYC fiscal year (Jul 1–Jun 30) for an ISO date string; FY labelled by end year."""
    m = re.match(r"(\d{4})-(\d{2})", date_str or "")
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return y + 1 if mo >= 7 else y


def _query_contract_spend_map(target_keys) -> dict:
    """Full-history scan of spent / payments / first & last payment per contract,
    keyed by normalized_contract_id — but ONLY for `target_keys` (the normalized
    ids present in the contracts table).

    Why scoped: NYC spending has ~8M distinct raw contract_ids (POs/documents), so
    an unfiltered GROUP BY materialized an ~8M-entry dict (~5.5 GB) that OOM-killed
    the container — yet every caller only .get()s a real contract's key, so >99%
    was dead weight. Restricting to the ~30k real contracts gives identical
    per-contract values (verified) at ~75 MB. Normalization + grouping run in SQL,
    matching _normalize_contract_id exactly (upper, strip non-alnum), so two raw
    ids that normalize together are merged by GROUP BY. Must run under
    to_duckdb_thread."""
    if not target_keys:
        return {}
    con = _persistent_spending_connection().cursor()
    files = get_spending_files(all_years=True)
    rows = con.execute(
        f"SELECT nkey, SUM(TRY_CAST(check_amount AS DOUBLE)) AS spent, COUNT(*) AS n, "
        f"MIN(issue_date) AS first_date, MAX(issue_date) AS last_date, "
        # Raw ids that do NOT already equal their normalized form. This is what
        # lets _query_contract_detail filter on the raw column (which the Parquet
        # row-group statistics can prune) instead of re-normalizing every row.
        # Free here: this scan already computes nkey and is already grouped.
        f"ARRAY_AGG(DISTINCT contract_id) FILTER (WHERE contract_id <> nkey) AS variants "
        f"FROM ("
        f"  SELECT REGEXP_REPLACE(UPPER(contract_id), '[^A-Z0-9]', '', 'g') AS nkey, "
        f"         contract_id, check_amount, issue_date "
        f"  FROM read_parquet({files}) WHERE contract_id IS NOT NULL AND contract_id != ''"
        f") WHERE nkey IN (SELECT unnest(?::VARCHAR[])) GROUP BY nkey",
        [list(target_keys)],
    ).fetchall()
    con.close()
    out: Dict[str, dict] = {}
    for nkey, spent, n, first_date, last_date, variants in rows:
        if not nkey:
            continue
        out[nkey] = {"spent_to_date": float(spent or 0), "payment_count": int(n or 0),
                     "first_payment": first_date, "last_payment": last_date,
                     "raw_variants": list(variants or [])}
    return out


# A program is a handful of contracts; 4,721 is a calendar. Co-termination is
# only shown for groups at or under this size.
_COTERM_MAX_GROUP = 10


async def _related_contracts(ctr_id: str, vendor: str, agency: str,
                             end_date: str) -> dict:
    """Other contracts a reader of THIS contract should see, in two clearly
    separate kinds. Never merged, because they carry different evidential weight.

    `same_vendor` is a FACT: the same vendor holds these at the same agency. The
    renewal queue already computes vendor concentration ("this vendor holds $189M
    citywide") but publishes it as a NUMBER on a different page, so the claim was
    never traversable from the contract it is made about.

    `co_terminating` is CIRCUMSTANTIAL and labelled as such. Contracts ending on
    the same day at the same agency are often one program — MOCS's PASSPort is
    5 contracts / $78.1M all ending 04/27/2027, of which the queue previously
    showed one row with no indication a $37.9M platform licence expires with it.
    ⚠ But it is NOT evidence of a shared program, and the page must not say it
    is: see the standing rule against asserting a product identity from
    co-termination plus a shared agency.

    ⚠⚠ TWO RULES MAKE THE SECOND SIGNAL USABLE AT ALL, and without them it is
    almost pure noise. Measured across all 56,806 contracts:
      * 46,607 contracts co-terminate with a different vendor at the same agency;
      * the largest group is **4,721 contracts** (DYCD, 06/30/2023), then 1,873,
        1,835, 1,751 — and EVERY oversized group lands on **06/30**, the NYC
        fiscal-year boundary, where a shared end date carries no information.
    So: groups larger than _COTERM_MAX_GROUP are dropped, and 06/30 is excluded
    outright. That leaves 3,488 groups / 12,007 contracts — and PASSPort, at 5,
    survives. Both rules are stated on the page, because a threshold the reader
    cannot see is indistinguishable from an opinion.
    """
    out = {"same_vendor": [], "co_terminating": [],
           "coterm_max_group": _COTERM_MAX_GROUP}
    cols = ("ctr_id, contract_id, contract_title, vendor_name, agency, "
            "current_amount, award_amount, start_date, end_date")
    try:
        if vendor and agency:
            out["same_vendor"] = [dict(r) for r in (await PostgresModelAsync.select_safe(
                f"SELECT DISTINCT ON (ctr_id) {cols} FROM contracts "
                "WHERE vendor_name = $1 AND agency = $2 AND ctr_id <> $3 "
                "ORDER BY ctr_id, current_amount DESC NULLS LAST LIMIT 25",
                [vendor, agency, ctr_id]) or [])]
        # ⚠ `NOT LIKE '06/30/%'` is the fiscal-boundary exclusion; the HAVING is the
        # size cap. Dropping either re-admits the 4,721-contract group.
        if agency and end_date and not str(end_date).startswith("06/30"):
            peers = await PostgresModelAsync.select_safe(
                f"SELECT DISTINCT ON (ctr_id) {cols} FROM contracts "
                "WHERE agency = $1 AND end_date = $2 "
                "ORDER BY ctr_id, current_amount DESC NULLS LAST",
                [agency, end_date]) or []
            if 1 < len(peers) <= _COTERM_MAX_GROUP:
                out["co_terminating"] = [dict(r) for r in peers
                                         if str(r.get("ctr_id")) != str(ctr_id)]
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[contract {ctr_id}] related-contracts lookup failed: {exc_str(exc)}")
    return out


async def _precomputed_spend_map() -> Optional[dict]:
    """The spend map from `contract_spend`, built offline by
    build_contract_timeline.py. Returns None when the table is absent or empty, so
    the caller falls back to the live DuckDB scan.

    ⚠ THIS IS WHAT REMOVES THE ~60s COLD WINDOW. `_populate_contract_spend` scans
    the whole lake in the background and returns {} meanwhile, so for about a
    minute after EVERY api restart — including the daily 04:00 cron — every
    contract page rendered an empty spend section and `/oce/contracts/export` sent
    `no-store`. A Postgres read of ~31.6k rows is fast enough to do inline, so the
    map is populated before the first request instead of a minute after it.
    """
    try:
        rows = await PostgresModelAsync.select_safe(
            "SELECT nkey, spent_to_date, payment_count, first_payment, last_payment, "
            "raw_variants FROM contract_spend")
    except Exception as exc:  # noqa: BLE001
        # WARNING, not ERROR: an absent table is the legitimate state before the
        # first build, and the DuckDB path still serves the page.
        logger.warning(f"[contracts] precomputed spend map unavailable: {exc_str(exc)}")
        return None
    if not rows:
        return None
    return {r["nkey"]: {"spent_to_date": float(r["spent_to_date"] or 0),
                        "payment_count": int(r["payment_count"] or 0),
                        "first_payment": r["first_payment"],
                        "last_payment": r["last_payment"],
                        "raw_variants": list(r["raw_variants"] or [])}
            for r in rows if r["nkey"]}


async def _precomputed_contract_detail(key: str) -> Optional[dict]:
    """One contract's timeline + payee rollup from Postgres, or None to fall back.

    ⚠ Returns None — not an empty detail — when the contract has no precomputed
    rows, because those two states are different and only one of them should
    trigger the Parquet scan. A contract registered since the last lake refresh
    genuinely has no rows here and must still render.
    """
    try:
        tl = await PostgresModelAsync.select_safe(
            "SELECT month, total FROM contract_timeline WHERE nkey = $1 ORDER BY month",
            [key])
        pv = await PostgresModelAsync.select_safe(
            "SELECT payee_name, sub_vendor, prime, spent, n FROM contract_payees "
            "WHERE nkey = $1 ORDER BY rank", [key])
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[contract] precomputed detail unavailable: {exc_str(exc)}")
        return None
    if not tl and not pv:
        return None
    return {
        "timeline": {"labels": [r["month"] for r in tl],
                     "values": [float(r["total"] or 0) for r in tl]},
        "vendors": [{"payee": r["payee_name"], "sub_vendor": r["sub_vendor"],
                     "prime_vendor": r["prime"], "spent": float(r["spent"] or 0),
                     "payments": int(r["n"] or 0)} for r in pv],
    }


_contract_spend_populating = False  # guards against concurrent background scans


async def _populate_contract_spend() -> None:
    """Background: the full-history scan, cached. Never on the request path (the
    all-years scan can take >60s cold). Scoped to the contract ids that exist in
    the contracts table so the in-memory map stays bounded (see
    _query_contract_spend_map) — derives the key set exactly as the lookups do."""
    global _contract_spend_populating
    try:
        crows = await PostgresModelAsync.select_safe(
            "SELECT normalized_contract_id, contract_id FROM contracts"
        )
        targets = set()
        for r in (crows or []):
            k = _normalize_contract_id(r.get('normalized_contract_id') or r.get('contract_id'))
            if k:
                targets.add(k)
        m = await to_duckdb_thread(_query_contract_spend_map, targets)
        _contract_spend_cache['data'] = m
        _contract_spend_cache['ts'] = time.time()
        logger.info(f"[contracts] spend map ready ({len(m)} contracts, {len(targets)} targets)")
    except Exception as exc:  # noqa: BLE001
        # ALERTS: no spend/utilization on any contract, and "no spend" looks identical to "$0 spent".
        logger.error(f"[contracts] spend-map build failed: {exc}")
    finally:
        _contract_spend_populating = False


async def _get_contract_spend_map() -> dict:
    """Non-blocking accessor. Returns the cached map when fresh; otherwise kicks off
    a one-shot background scan and returns whatever's on hand ({} the first time) so
    /oce/contracts never blocks on the S3 read. (Ideally scheduler-precomputed.)"""
    global _contract_spend_populating
    c = _contract_spend_cache
    if c['data'] is not None and (time.time() - c['ts']) < CONTRACT_SPEND_CACHE_TTL:
        return c['data']
    # ⚠ PRECOMPUTE FIRST, DuckDB only as a fallback. Reading ~31.6k rows from
    # Postgres is fast enough to do inline, which is what closes the cold window;
    # the background scan stays for a fresh environment where the builder has not
    # run yet, and is deliberately NOT deleted (see build_contract_timeline.py).
    pre = await _precomputed_spend_map()
    if pre:
        c['data'] = pre
        c['ts'] = time.time()
        return pre
    if not _contract_spend_populating:
        _contract_spend_populating = True
        asyncio.create_task(_populate_contract_spend())
    return c['data'] or {}


def _spend_cache_headers(response: Response, spend_map: dict) -> None:
    """Mark a response built from the contract spend map as cacheable, or not.

    ⚠ THE MAP IS EMPTY FOR ~1 MINUTE AFTER EVERY api RESTART, including the daily
    04:00 cron. `_get_contract_spend_map()` is deliberately non-blocking: it kicks
    off a background scan and returns `{}` meanwhile, and callers render nothing
    rather than a false $0. That is correct for a live request and WRONG to cache —
    Cloudflare's edge TTL would pin an empty spend section for the whole TTL, so a
    routine restart could blank the figures on every contract page for 10 minutes.
    Measured 2026-08-04: `/oce/contract/{id}` went 0.580s -> 0.044s once cached, so
    the cache is worth keeping; this is what makes it safe.

    A cold map is the one state where the response is correct but INCOMPLETE, and
    incomplete is exactly what must not be stored. `no-store` (not `no-cache`)
    because we want it neither kept nor revalidated — the next request should build
    a fresh response, by which point the scan has almost certainly finished.

    ⚠ Has no effect until the Cloudflare Cache Rule uses `respect_origin`; under
    `override_origin` the edge ignores every header we send here. See the ordering
    note in api/main.py — the api ships first, the rule flips second.
    """
    response.headers["Cache-Control"] = (
        f"public, max-age={_EDGE_MAX_AGE}" if spend_map else "no-store"
    )


_EDGE_MAX_AGE = int(os.getenv("API_EDGE_MAX_AGE", "600"))


def _add_contract_spend(contract: dict, spend: Optional[dict]) -> dict:
    """Attach spent_to_date / payment_count / pct_used to a contract row."""
    award = contract.get("award_amount") or 0
    try:
        award = float(award)
    except (TypeError, ValueError):
        award = 0.0
    spent = float(spend["spent_to_date"]) if spend else 0.0
    contract["spent_to_date"] = spent
    contract["payment_count"] = spend["payment_count"] if spend else 0
    contract["first_payment"] = spend["first_payment"] if spend else None
    contract["last_payment"] = spend["last_payment"] if spend else None
    contract["pct_used"] = round(spent / award * 100, 1) if award > 0 else None
    return contract


def _query_contract_detail(normalized_id: str, first_date: Optional[str],
                           last_date: Optional[str],
                           raw_variants: Optional[list] = None) -> dict:
    """Timeline (by month) + top payee/sub-vendor rollup for one contract. Scans only
    the fiscal years the contract has payments in (from the spend map) to bound cost.

    Two things keep this cheap, both measured on prod 2026-07-27 against contract
    CT182620151425458 (1,592 payments spanning FY2015-FY2026, the worst case found):

    1. **Filter the RAW column, never a function of it.** This used to test
       `regexp_replace(upper(contract_id), ...) = ?`, which forces DuckDB to
       decode and re-normalize every row of every scanned partition — no
       row-group pruning is possible against a computed expression. The lake
       already stores contract_id un-dashed and uppercase, so plain equality
       returns byte-identical results while letting the Parquet statistics skip
       whole row groups: 4.53s -> 0.82s on the timeline query alone.

       Correctness is not assumed: 13,783 of 26.3M rows (0.05%) DO carry a raw
       id that normalization would change (dashed `PON...` purchase orders,
       1,131 distinct). `_query_contract_spend_map` collects those per contract
       as `raw_variants` — free, since it already computes nkey — and they are
       added to the IN list here. Today that set is empty for every one of the
       36,421 real contracts, but a future Checkbook refresh introducing one
       will be picked up automatically rather than silently dropping payments.

    2. **One scan, not two.** The timeline and payee rollups need exactly the
       same filtered rows, so they are materialized once and aggregated twice:
       1.59s -> 0.79s. Total for the worst case: 8.69s -> 0.79s (~11x).

    Must run under to_duckdb_thread.
    """
    fys = sorted({fy for fy in (_fy_of(first_date), _fy_of(last_date)) if fy})
    if fys:
        years = list(range(min(fys), max(fys) + 1))
        urls = []
        for fy in years:
            urls.append(get_spending_files(fiscal_year=fy)[1:-1])  # strip the [ ]
        files = "[" + ", ".join(u for u in urls if u) + "]"
    else:
        files = get_spending_files(all_years=True)

    ids = [normalized_id] + [v for v in (raw_variants or []) if v and v != normalized_id]
    ph = ", ".join("?" for _ in ids)
    con = _persistent_spending_connection().cursor()
    row = con.execute(
        f"WITH payments AS MATERIALIZED ("
        f"  SELECT issue_date, check_amount, payee_name, sub_vendor, associated_prime_vendor "
        f"  FROM read_parquet({files}) WHERE contract_id IN ({ph})"
        f"), tl AS ("
        f"  SELECT strftime(TRY_CAST(issue_date AS DATE), '%Y-%m') AS m, "
        f"         COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) AS t "
        f"  FROM payments WHERE issue_date IS NOT NULL GROUP BY m"
        f"), vn AS ("
        f"  SELECT payee_name, sub_vendor, associated_prime_vendor, "
        f"         COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) AS spent, COUNT(*) AS n "
        f"  FROM payments GROUP BY 1, 2, 3 ORDER BY spent DESC LIMIT 25"
        f") SELECT "
        f"  (SELECT list({{'m': m, 't': t}} ORDER BY m) FROM tl), "
        f"  (SELECT list({{'p': payee_name, 'sv': sub_vendor, 'pv': associated_prime_vendor, "
        f"                 's': spent, 'n': n}} ORDER BY spent DESC) FROM vn)",
        ids
    ).fetchone()
    con.close()

    timeline = (row[0] if row else None) or []
    vendors = (row[1] if row else None) or []
    return {
        "timeline": {"labels": [r["m"] for r in timeline],
                     "values": [float(r["t"]) for r in timeline]},
        "vendors": [
            {"payee": v["p"], "is_sub_vendor": (v["sv"] == "Yes"),
             "prime_vendor": (v["pv"] if v["pv"] and v["pv"] != "N/A" else None),
             "spent": float(v["s"]), "payments": int(v["n"])}
            for v in vendors
        ],
    }


def _contracts_where(q, agency, status, method, industry, min_amount, max_amount, expense_category=None):
    """Parametrized WHERE for the Postgres `contracts` table. Returns
    (where_sql, params, next_param_index)."""
    clauses, params, i = [], [], 1
    if q:
        clauses.append(f"(contract_title ILIKE ${i} OR contract_id ILIKE ${i+1} OR vendor_name ILIKE ${i+2})")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]; i += 3
    if agency:
        clauses.append(f"agency ILIKE ${i}"); params.append(f"%{agency}%"); i += 1
    if status:
        clauses.append(f"status = ${i}"); params.append(status); i += 1
    if method:
        clauses.append(f"procurement_method = ${i}"); params.append(method); i += 1
    if industry:
        clauses.append(f"industry = ${i}"); params.append(industry); i += 1
    if expense_category:
        # expense_category lives in checkbook_contract_meta (Phase D) — filter via the id crosswalk.
        clauses.append(f"normalized_contract_id IN (SELECT normalized_contract_id FROM checkbook_contract_meta WHERE expense_category = ${i})")
        params.append(expense_category); i += 1
    if min_amount not in (None, ""):
        clauses.append(f"award_amount >= ${i}"); params.append(float(min_amount)); i += 1
    if max_amount not in (None, ""):
        clauses.append(f"award_amount <= ${i}"); params.append(float(max_amount)); i += 1
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return where, params, i


async def _attach_contract_meta(rows: list) -> None:
    """Merge purpose / expense_category / award_method (Checkbook, checkbook_contract_meta)
    onto contract rows by normalized_contract_id. Missing → None (falls back to title)."""
    keys = sorted({k for c in (rows or [])
                   if (k := _normalize_contract_id(c.get('normalized_contract_id') or c.get('contract_id')))})
    if not keys:
        return
    ph = ",".join(f"${i+1}" for i in range(len(keys)))
    try:
        meta = await PostgresModelAsync.select_safe(
            f"SELECT normalized_contract_id AS n, purpose, expense_category, award_method "
            f"FROM checkbook_contract_meta WHERE normalized_contract_id IN ({ph})", keys)
    except Exception as exc:  # noqa: BLE001
        # ALERTS: purpose + expense_category silently blank on every contract row.
        logger.error(f"[contracts] meta join failed: {exc}")
        meta = []
    mmap = {m['n']: m for m in (meta or [])}
    for c in (rows or []):
        m = mmap.get(_normalize_contract_id(c.get('normalized_contract_id') or c.get('contract_id')))
        c['purpose'] = m['purpose'] if m else None
        c['expense_category'] = m['expense_category'] if m else None
        c['award_method'] = m['award_method'] if m else None


@router.get("/contracts")
async def list_contracts(
    response: Response,
    page: int = 1,
    limit: int = 50,
    q: Optional[str] = None,
    agency: Optional[str] = None,
    status: Optional[str] = None,
    method: Optional[str] = None,
    industry: Optional[str] = None,
    expense_category: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    sort: str = 'amount',
    order: str = 'desc'
):
    offset = (max(page, 1) - 1) * limit
    where_str, params, param_idx = _contracts_where(q, agency, status, method, industry, min_amount, max_amount, expense_category)

    valid_sorts = {
        'amount': 'award_amount',
        'date': 'start_date',
        'vendor': 'vendor_name',
        'agency': 'agency'
    }
    sql_sort = valid_sorts.get(sort, 'award_amount')
    sql_order = 'ASC' if order == 'asc' else 'DESC'
    
    data_sql = f"""
        SELECT * FROM contracts
        {where_str}
        ORDER BY {sql_sort} {sql_order}
        LIMIT ${param_idx} OFFSET ${param_idx+1}
    """
    
    count_sql = f"SELECT count(*) as c FROM contracts {where_str}"
    
    rows = await PostgresModelAsync.select_safe(data_sql, params + [limit, offset])
    total_res = await PostgresModelAsync.select_safe(count_sql, params)
    total = total_res[0]['c'] if total_res else 0

    # Join spent-to-date / utilization from the spending Parquet.
    spend_map = await _get_contract_spend_map()
    _spend_cache_headers(response, spend_map)
    for c in (rows or []):
        key = _normalize_contract_id(c.get('normalized_contract_id') or c.get('contract_id'))
        _add_contract_spend(c, spend_map.get(key) if key else None)
    # Join purpose / expense_category / award_method (Checkbook meta, Phase D).
    await _attach_contract_meta(rows or [])

    return {
        "data": rows,
        "total": total,
        "page": page,
        "pages": math.ceil(total / limit)
    }


@router.get("/contracts/export")
async def export_contracts(
    q: Optional[str] = None, agency: Optional[str] = None, status: Optional[str] = None,
    method: Optional[str] = None, industry: Optional[str] = None,
    expense_category: Optional[str] = None,
    min_amount: Optional[float] = None, max_amount: Optional[float] = None,
    sort: str = 'amount', order: str = 'desc',
):
    """Download the current contract filter set as CSV (with spent-to-date, capped 50k)."""
    where_str, params, _ = _contracts_where(q, agency, status, method, industry, min_amount, max_amount, expense_category)
    sql_sort = {'amount': 'award_amount', 'date': 'start_date', 'vendor': 'vendor_name', 'agency': 'agency'}.get(sort, 'award_amount')
    sql_order = 'ASC' if order == 'asc' else 'DESC'
    rows = await PostgresModelAsync.select_safe(
        f"SELECT contract_id, contract_title, agency, vendor_name, award_amount, status, "
        f"start_date, end_date, procurement_method, industry, normalized_contract_id "
        f"FROM contracts {where_str} ORDER BY {sql_sort} {sql_order} NULLS LAST LIMIT 50000",
        params,
    ) or []
    spend_map = await _get_contract_spend_map()
    cols = ["contract_id", "title", "agency", "vendor", "award_amount", "spent_to_date",
            "pct_used", "status", "start_date", "end_date", "method", "industry"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for c in rows:
        key = _normalize_contract_id(c.get('normalized_contract_id') or c.get('contract_id'))
        sp = spend_map.get(key) if key else None
        try:
            award = float(c.get('award_amount') or 0)
        except (TypeError, ValueError):
            award = 0.0
        spent = float(sp['spent_to_date']) if sp else 0.0
        pct = round(spent / award * 100, 1) if award > 0 else ''
        w.writerow([c.get('contract_id', ''), c.get('contract_title', ''), c.get('agency', ''),
                    c.get('vendor_name', ''), award, spent, pct, c.get('status', ''),
                    c.get('start_date', ''), c.get('end_date', ''),
                    c.get('procurement_method', ''), c.get('industry', '')])
    resp = Response(content=buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="databook-contracts.csv"',
        "X-Row-Count": str(len(rows)),
    })
    # ⚠ Set on the RETURNED Response, not an injected one: when a handler returns
    # its own Response, FastAPI does not merge the injected `response` object's
    # headers, so the usual pattern would silently do nothing here. Same rule as
    # the JSON endpoints — a CSV built from a cold spend map must not be stored.
    _spend_cache_headers(resp, spend_map)
    return resp

@router.get("/solicitations")
async def list_solicitations(
    page: int = 1,
    limit: int = 50,
    q: Optional[str] = None,
    agency: Optional[str] = None,
    status: Optional[str] = None,
    method: Optional[str] = None,
    industry: Optional[str] = None,
    sort: str = 'due_date',
    order: str = 'desc'
):
    offset = (max(page, 1) - 1) * limit
    
    where_clauses = []
    params = []
    param_idx = 1
    
    if q:
        where_clauses.append(f"(\"Procurement Name\" ILIKE ${param_idx} OR \"EPIN\" ILIKE ${param_idx+1} OR \"Agency\" ILIKE ${param_idx+2})")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        param_idx += 3
        
    if agency:
        where_clauses.append(f"\"Agency\" ILIKE ${param_idx}")
        params.append(f"%{agency}%")
        param_idx += 1
        
    if status:
        where_clauses.append(f"\"RFx Status\" = ${param_idx}")
        params.append(status)
        param_idx += 1
        
    if method:
        where_clauses.append(f"\"Procurement Method\" = ${param_idx}")
        params.append(method)
        param_idx += 1
        
    if industry:
        where_clauses.append(f"\"Industry\" = ${param_idx}")
        params.append(industry)
        param_idx += 1
        
    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    valid_sorts = {
        'release_date': 'TO_DATE(NULLIF("Release Date", \'\'), \'MM/DD/YYYY\')',
        'due_date': 'TO_DATE(NULLIF("Due Date", \'\'), \'MM/DD/YYYY\')',
        'agency': '"Agency"',
        'name': '"Procurement Name"'
    }
    sql_sort = valid_sorts.get(sort, 'TO_DATE(NULLIF("Due Date", \'\'), \'MM/DD/YYYY\')')
    sql_order = 'ASC' if order == 'asc' else 'DESC'
    
    data_sql = f"""
        SELECT * FROM solicitations
        {where_str}
        ORDER BY {sql_sort} {sql_order} NULLS LAST
        LIMIT ${param_idx} OFFSET ${param_idx+1}
    """
    
    count_sql = f"SELECT count(*) as c FROM solicitations {where_str}"
    
    rows = await PostgresModelAsync.select_safe(data_sql, params + [limit, offset])
    total_res = await PostgresModelAsync.select_safe(count_sql, params)
    total = total_res[0]['c'] if total_res else 0
    
    return {
        "data": rows,
        "total": total,
        "page": page,
        "pages": math.ceil(total / limit)
    }

@router.get("/contract/{id}")
async def get_contract(id: str, response: Response):
    """Get a single contract by CTR-ID or Contract ID with linked vendor and solicitation."""
    # Try looking up by ctr_id first, then by contract_id
    contract_res = await PostgresModelAsync.select_safe(
        "SELECT * FROM contracts WHERE ctr_id = $1", [id]
    )
    if not contract_res:
        # Try by contract_id (e.g., CT1-846-20268804478)
        contract_res = await PostgresModelAsync.select_safe(
            "SELECT * FROM contracts WHERE contract_id = $1", [id]
        )
    if not contract_res:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    contract = contract_res[0]
    
    # Get linked vendor if vendor_name exists
    vendor = None
    if contract.get('vendor_name'):
        vendor_res = await PostgresModelAsync.select_safe(
            "SELECT * FROM vendors WHERE \"Vendor Name\" = $1", [contract['vendor_name']]
        )
        if vendor_res:
            vendor = vendor_res[0]
    
    # Get linked solicitation via EPIN
    solicitation = None
    if contract.get('epin'):
        sol_res = await PostgresModelAsync.select_safe(
            "SELECT * FROM solicitations WHERE \"EPIN\" = $1", [contract['epin']]
        )
        if sol_res:
            solicitation = sol_res[0]

    # Checkbook meta (purpose / expense_category / award_method) + spend rollup + timeline.
    await _attach_contract_meta([contract])
    key = _normalize_contract_id(contract.get('normalized_contract_id') or contract.get('contract_id'))
    spend_map = await _get_contract_spend_map()
    _spend_cache_headers(response, spend_map)
    _add_contract_spend(contract, spend_map.get(key) if key else None)
    detail = {"timeline": {"labels": [], "values": []}, "vendors": []}
    if key and spend_map.get(key):
        # ⚠ PRECOMPUTED FIRST. The live DuckDB scan is only 53ms on its own, but
        # under concurrency it starves the event loop and inflates UNRELATED
        # Postgres spans 2.3x (measured 2026-08-18 with a control endpoint). The
        # fix is removing it from the request path, not speeding it up.
        pre = await _precomputed_contract_detail(key)
        if pre is not None:
            detail = pre
        else:
            try:
                e = spend_map[key]
                detail = await to_duckdb_thread(
                    _query_contract_detail, key, e.get("first_payment"), e.get("last_payment"),
                    e.get("raw_variants")
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[contract {id}] detail query failed: {exc}")

    # MOCS performance evaluations for THIS contract. The evaluations export
    # carries a contract id on every row, and 27.7% of our contracts have at
    # least one — the agency's own end-of-period assessment of how the work
    # went, which nothing else on this page reports. Joined on the normalized
    # id (the export uses the same 'CT1-068-20248800127' shape we do).
    evaluations = []
    if key:
        try:
            rows = await PostgresModelAsync.select_safe(
                """SELECT agency, purpose, eval_date, start_date, end_date, rating
                   FROM vendor_evaluations WHERE contract_id_norm = $1
                   ORDER BY eval_date DESC NULLS LAST LIMIT 25""", [key])
            evaluations = [{
                "agency": (r.get("agency") or "").strip(),
                "purpose": (r.get("purpose") or "").strip(),
                "date": (r.get("eval_date") or "")[:10],
                "period_start": (r.get("start_date") or "")[:10],
                "period_end": (r.get("end_date") or "")[:10],
                "rating": (r.get("rating") or "").strip(),
            } for r in (rows or [])]
        except Exception as exc:  # noqa: BLE001 — table absent on a fresh env
            logger.warning(f"[contract {id}] evaluations lookup failed: {exc}")

    return {
        "contract": contract,
        "vendor": vendor,
        "solicitation": solicitation,
        "spend_timeline": detail["timeline"],
        "spend_vendors": detail["vendors"],
        "evaluations": evaluations,
        "evaluations_as_of": await _passport_as_of() if evaluations else "",
        "related_notices": await _notices_for_epins([contract.get('epin', '')]),
        # Other contracts a reader of this one should see. Two clearly separate
        # kinds — a fact and a circumstantial signal — never merged. See
        # _related_contracts for the two rules that make the second usable.
        "related_contracts": await _related_contracts(
            str(contract.get('ctr_id') or id), contract.get('vendor_name') or '',
            contract.get('agency') or '', contract.get('end_date') or ''),
    }

@router.get("/solicitation/{epin}")
async def get_solicitation(epin: str):
    """Get a single solicitation by EPIN with resulting contracts.

    Why: solicitation_profile.blade.php uses lowercase keys (epin, procurement_name,
    rfx_status etc.) — not the raw DB column names. We transform the response.
    """
    sol_res = await PostgresModelAsync.select_safe(
        "SELECT * FROM solicitations WHERE \"EPIN\" = $1", [epin]
    )
    if not sol_res:
        raise HTTPException(status_code=404, detail="Solicitation not found")
    
    s = sol_res[0]
    solicitation = {
        'epin': s.get('EPIN', ''),
        'procurement_name': s.get('Procurement Name', ''),
        'agency': s.get('Agency', ''),
        'rfx_status': s.get('RFx Status', ''),
        'release_date': s.get('Release Date', ''),
        'due_date': s.get('Due Date', ''),
        'industry': s.get('Industry', ''),
        'procurement_method': s.get('Procurement Method', ''),
        'main_commodity': s.get('Main Commodity', ''),
        'program': s.get('Program', ''),
    }
    
    # Get resulting contracts
    contracts = await PostgresModelAsync.select_safe(
        "SELECT * FROM contracts WHERE epin = $1 ORDER BY award_amount DESC", [epin]
    )
    
    # Calculate stats
    total_awarded = sum(c.get('award_amount', 0) or 0 for c in contracts)

    # Related City Record notices — the notice PIN prefixes this 10-char EPIN.
    # Live join (no stored crosswalk: CROL refreshes daily). Guarded so a missing
    # crol table or query failure never breaks the solicitation page.
    related_notices = []
    # Guard: a blank/too-short EPIN would match the ~5M empty-PIN notices.
    if epin and len(epin.strip()) >= 6:
        try:
            notice_rows = await PostgresModelAsync.select_safe(
                """
                SELECT "RequestID" AS rid, "ShortTitle" AS title, "AgencyName" AS agency,
                       "TypeOfNoticeDescription" AS type, "StartDate" AS date
                FROM crol
                WHERE left(trim("PIN"), 10) = $1
                ORDER BY start_date_parsed DESC NULLS LAST
                LIMIT 25
                """,
                [epin.strip()],
            )
            for n in (notice_rows or []):
                related_notices.append({
                    "title": n.get("title") or "Notice",
                    "type": n.get("type") or "",
                    "agency": n.get("agency") or "",
                    "date": (n.get("date") or "")[:10],
                    "url": f"https://a856-cityrecord.nyc.gov/RequestDetail/{n['rid']}",
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[oce] related-notices query failed for {epin}: {exc}")

    return {
        "solicitation": solicitation,
        "contracts": contracts or [],
        "related_notices": related_notices,
        "stats": {
            "contract_count": len(contracts),
            "total_awarded": total_awarded
        }
    }

# ============================================================================
# Digital Service Reform — renewal-review signals (editorial heuristics)
# ============================================================================
# These constants drive the "Renewal Review Queue": a systematic way to triage
# the digital contracts expiring before 2030 and surface which ones the city
# should scrutinize before renewing. The flags are transparent (each carries a
# human-readable reason) rather than an opaque score, so reviewers see *why* a
# contract surfaced. The keyword/method lists are intentionally easy to tune.

# Procurement methods that involved genuine competition. Everything else
# (renewals, amendments, sole-source, MWBE non-competitive, GSA/OGS piggybacks,
# micropurchases, subscriptions…) extends or awards without a fresh bid and is
# flagged "non-competitive" — the dominant pattern in this dataset.
COMPETITIVE_PROCUREMENT_METHODS = {
    "competitive sealed bid",
    "competitive sealed proposal",
}

# Methods that extend/renew an existing engagement rather than start a fresh one.
RENEWAL_PROCUREMENT_METHODS = {
    "renewal",
    "amendment",
    "negotiated acquisition extension",
}


def _scan_contract_spend(normed_ids: list) -> dict:
    """SUM(check_amount) per contract over recent-FY Checkbook Parquet, keyed by
    the normalized (upper, alnum-only) contract id so it joins to
    contracts.normalized_contract_id. Blocking DuckDB S3 scan — call via
    to_duckdb_thread. Returns {} on any failure (best-effort enrichment)."""
    if not normed_ids:
        return {}
    con = _persistent_spending_connection().cursor()
    files = get_spending_files(None)  # 5 recent fiscal years
    # ids are already alnum-only uppercase (normalized_contract_id). Checkbook
    # contract_ids are un-dashed (e.g. "CT107120268802839"), so a direct
    # upper(contract_id) match joins them without a costly per-row regex.
    in_list = ",".join("'" + str(i).replace("'", "") + "'" for i in normed_ids)
    sql = ("SELECT upper(contract_id) AS n, SUM(TRY_CAST(check_amount AS DOUBLE)) AS s "
           f"FROM read_parquet({files}) "
           f"WHERE contract_id IS NOT NULL AND upper(contract_id) IN ({in_list}) "
           "GROUP BY 1")
    try:
        return {row[0]: float(row[1] or 0) for row in con.execute(sql).fetchall()}
    finally:
        con.close()


async def _populate_digital_spend(*scopes) -> None:
    """Background: run the expensive Checkbook Parquet scan and cache the result,
    then clear the digital-reform page cache so the next load includes spend.
    Never runs on the request path (the scan can take >60s cold).

    ⚠ THE UNION OF EVERY SCOPE THAT READS THE MAP. There is one cache, shared by
    the dashboard and the Renewal Queue, and those now run in different scopes —
    so building it from one of them would leave the other's contracts with
    `spent = None`, which silently disables the `underused` (shelfware) flag on
    exactly the rows it exists for. A missing spend figure looks identical to a
    contract with no spend.
    """
    global _spend_populating
    try:
        ids = set()
        for sc in scopes:
            idrows = await PostgresModelAsync.select_safe(
                f"""SELECT DISTINCT c.normalized_contract_id AS n FROM {sc.table()} c
                    WHERE {sc.where('c')} AND c.normalized_contract_id IS NOT NULL""")
            ids.update(str(r['n']).upper() for r in (idrows or []) if r.get('n'))
        ids = sorted(ids)
        spend = await to_duckdb_thread(_scan_contract_spend, ids)
        _digital_spend_cache['data'] = spend
        _digital_spend_cache['ts'] = time.time()
        _digital_reform_cache.clear()  # force recompute so spend/utilization show
        logger.info(f"[oce] digital spend map ready ({len(spend)} contracts)")
    except Exception as exc:  # noqa: BLE001
        # ALERTS: disables the `underused` flag queue-wide; a missing spend figure looks like a real one.
        logger.error(f"[oce] digital spend scan failed: {exc}")
    finally:
        _spend_populating = False


async def _get_digital_spend_map(*scopes) -> dict:
    """Non-blocking accessor for the digital-contract spend map. Returns the
    cached map when fresh; otherwise kicks off a one-shot background scan and
    returns whatever is on hand ({} the first time) so the page never blocks on
    the S3 Parquet read. Shared across all page-filter combinations — and across
    scopes, hence the *scopes union in _populate_digital_spend."""
    global _spend_populating
    c = _digital_spend_cache
    fresh = c['data'] is not None and (time.time() - c['ts']) < DIGITAL_REFORM_CACHE_TTL
    if fresh:
        return c['data']
    if not _spend_populating:
        _spend_populating = True
        asyncio.create_task(_populate_digital_spend(*scopes))
    return c['data'] or {}

# "Build-your-own candidate" heuristic: services the city could plausibly stand
# up itself with modern open-source + AI tooling, rather than renew a vendor
# contract. Matched (case-insensitively) against contract_title + program +
# industry. Each bucket maps a set of keywords to the reason shown to reviewers.
# This is a SUGGESTION to investigate, explicitly labeled as heuristic in the UI.
BUILD_YOUR_OWN_KEYWORDS = {
    "Website / CMS / portal": ["website", "web design", "web develop", "web site",
                               "portal", "content management", "drupal", "wordpress", "cms"],
    "Chatbot / virtual assistant": ["chatbot", "chat bot", "virtual assistant",
                                     "conversational", " 311"],
    "Forms / workflow / case mgmt": ["online form", "eform", "e-form", "workflow",
                                      "case management", "permitting"],
    "Document processing / OCR / translation": ["document management", "scanning",
                                                 "digitization", "ocr", "translation",
                                                 "transcription"],
    "Data / dashboard / analytics": ["dashboard", "analytics", "data visualization",
                                      "business intelligence", "reporting tool"],
    "Scheduling / notifications": ["scheduling", "appointment", "notification system"],
    "Survey / feedback": ["survey", "questionnaire"],
}


def _build_your_own_reason(text: str) -> Optional[str]:
    """Return the matching build-your-own bucket label for a contract's text, or None."""
    t = (text or "").lower()
    for label, kws in BUILD_YOUR_OWN_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return label
    return None


# ⚠⚠ THE QUESTION "COULD THE CITY BUILD THIS?" ONLY MAKES SENSE FOR ONE KIND OF
# PURCHASE. Asked of hosting, cloud, support tiers or content subscriptions it
# answers "no" and ends the conversation — which is precisely how Amazon Web
# Services sat at $6.80M rated `low` and appeared in no replaceability view on the
# Licenses page, against a `high` set totalling $10.13M. The Licenses page fixed
# that by hiding the rating outside `software-licence` and giving every other class
# its own lever. The queue was still asking every row the same question.
#
# So: where a contract HAS a resolved purchase class and that class is not
# `software-licence`, the build-your-own flag is withdrawn and the class's own
# lever is flagged instead. The labels are the question a reviewer should actually
# ask, keyed by licenseclass.LEVER_FOR.
CLASS_LEVER_LABELS = {
    "benchmark-then-self-host": "Benchmark the price",
    "price-and-rightsizing": "Benchmark the price",
    "is-the-paid-tier-needed": "Is the paid tier needed?",
    "is-the-content-needed": "Is the content needed?",
    "scope-and-rate-review": "Scope and rate review",
}

# The one class where the substitution question is the right question. A row with
# NO resolved class (every non-licence contract in the queue — staffing, hardware,
# telecom) keeps the existing behaviour: "could we build this instead of buying a
# website" is a fair question about a service, and gating those out would delete
# the flag exactly where the heuristic is most apt.
SUBSTITUTION_CLASS = "software-licence"


_ASCII_MAP = {
    "—": "-", "–": "-", "‒": "-", "−": "-",   # dashes
    "“": '"', "”": '"', "‘": "'", "’": "'",   # smart quotes
    "…": "...", "×": "x", "≤": "<=", "≥": ">=",
    "→": "->", "←": "<-", "·": "-", "•": "-",
    " ": " ", " ": " ", " ": " ",                   # nbsp/thin spaces
}


def _ascii(s):
    """Normalize smart punctuation (em-dash, curly quotes, x, ...) to plain ASCII.
    Applied to AI-/data-derived text rendered into HTML so it never depends on the
    page charset being interpreted correctly downstream (copy-paste, print, etc.)."""
    if not s:
        return s
    for k, v in _ASCII_MAP.items():
        s = s.replace(k, v)
    return s


def _review_flags(row: dict, days_to_expiry: Optional[int], has_rebid: bool,
                  vendor_stats: Optional[dict] = None, va_stats: Optional[dict] = None,
                  spent: Optional[float] = None, days_since_start: Optional[int] = None,
                  enrich: Optional[dict] = None, purchase_class: Optional[dict] = None) -> List[dict]:
    """Compute transparent renewal-review flags for one expiring contract.

    Each flag is {key, label, reason, severity}. severity drives badge colour
    in the UI (high=warn/red, med=amber, info=neutral).
    - vendor_stats: this vendor's footprint across ALL digital contracts
      {cnt, agencies, total} — lock-in signal.
    - va_stats: this vendor+agency relationship {cnt, since, total} — renewal chain.
    - spent: total Checkbook spend on this contract (recent FYs) — utilization.
    - purchase_class: modules/licenseclass.resolve() output, or None/{} for a
      contract with no licence family (every non-licence row). Gates flag 1.
    """
    flags: List[dict] = []
    award = float(row.get("award_amount") or 0)
    current = float(row.get("current_amount") or 0)
    method = (row.get("procurement_method") or "").strip()

    # 1. Build-your-own candidate (top-priority editorial signal). Prefer the AI
    #    enrichment's build_vs_buy rating (with its rationale); fall back to the
    #    keyword heuristic for any contract not yet classified.
    #    ⚠ CLASS-GATED — see CLASS_LEVER_LABELS. The reason is computed first and
    #    the class decides which flag carries it, so a withdrawn build-your-own is
    #    replaced by the right question rather than by silence.
    boyo_reason = None
    if enrich and enrich.get("build_vs_buy"):
        if enrich["build_vs_buy"] == "high":
            boyo_reason = ((enrich.get("rationale") or "Likely replaceable with open-source/AI tooling.")
                           + " (AI assessment — verify.)")
    else:
        boyo = _build_your_own_reason(
            f"{row.get('contract_title','')} {row.get('program','')} {row.get('industry','')}")
        if boyo:
            boyo_reason = (f"Looks like {boyo} — potentially replaceable with "
                           "open-source/AI tooling. Heuristic; verify.")

    if boyo_reason:
        pc = purchase_class or {}
        cls = (pc.get("class") or "").strip()
        lever = (pc.get("lever") or "").strip()
        if cls and cls != SUBSTITUTION_CLASS:
            flags.append({
                "key": "class_lever",
                "label": CLASS_LEVER_LABELS.get(lever, "Wrong question asked"),
                "reason": (f"Rated replaceable, but this is a {cls.replace('-', ' ')} "
                           f"purchase — “could the City build this?” is the wrong "
                           f"question for it. The lever is: {lever or 'unclassified'}. "
                           + boyo_reason),
                "severity": "med"})
        else:
            flags.append({"key": "build_your_own", "label": "Build-your-own candidate",
                          "reason": boyo_reason, "severity": "high"})

    # 2. Non-competitive award (renewal/amendment/sole-source/piggyback/etc).
    if method and method.lower() not in COMPETITIVE_PROCUREMENT_METHODS:
        flags.append({"key": "non_competitive", "label": "Non-competitive",
                      "reason": f"Awarded via “{method}” — not competitively bid.",
                      "severity": "med"})

    # 3. No open/forthcoming solicitation posted in the City Record for this PIN
    #    (a bare original "Award" notice does not count — see the rebid lookup).
    if not has_rebid:
        flags.append({"key": "no_rebid", "label": "No open solicitation",
                      "reason": "No Solicitation, Intent-to-Award or Vendor-List notice posted for this PIN — no replacement competition is visibly in motion, so any renewal would happen by default.",
                      "severity": "med"})

    # 4. Scope grew materially over the original award.
    if award > 0 and current > award * 1.25:
        flags.append({"key": "scope_growth", "label": f"Scope grew {current/award:.1f}×",
                      "reason": f"Current value ${current:,.0f} vs original award ${award:,.0f}.",
                      "severity": "info"})

    # 5. High value expiring in the near term (≤12 months).
    if award >= 1_000_000 and days_to_expiry is not None and 0 <= days_to_expiry <= 365:
        flags.append({"key": "high_value_near_term", "label": "High value, near-term",
                      "reason": f"${award:,.0f} contract expiring in {days_to_expiry} days.",
                      "severity": "high"})

    # 6. Vendor lock-in: this vendor's footprint across all digital contracts is
    #    large enough that renewing extends a concentrated dependency.
    vs = vendor_stats or {}
    vcnt = int(vs.get("cnt") or 0)
    vagencies = int(vs.get("agencies") or 0)
    # ⚠ The threshold tests COMMITTED money, not ceilings. A vendor whose book is
    # mostly master-agreement headroom has not been paid that money and should
    # not trip a concentration test on it. Falls back to `total` when the split
    # is absent (an older cached payload) so the flag degrades to its previous
    # behaviour rather than silently vanishing.
    vtotal = float(vs.get("total") or 0)
    vcommitted = float(vs.get("committed_total") if vs.get("committed_total") is not None
                       else vtotal)
    vceiling = float(vs.get("ceiling_total") or 0)
    if vagencies >= 6 or vcommitted >= 150_000_000 or vcnt >= 25:
        bits = []
        if vcnt >= 25: bits.append(f"{vcnt} digital contracts")
        if vagencies >= 6: bits.append(f"{vagencies} agencies")
        if vcommitted >= 150_000_000:
            bits.append(f"${vcommitted/1_000_000:.0f}M in committed contracts")
        # Stated, never added: a ceiling is headroom to buy against, so folding it
        # into the same figure is the defect this whole change exists to end.
        if vceiling >= 10_000_000:
            bits.append(f"a further ${vceiling/1_000_000:.0f}M of master-agreement "
                        f"ceilings")
        flags.append({"key": "vendor_lock_in", "label": "Vendor lock-in",
                      "reason": "Concentrated dependency — this vendor holds " + ", ".join(bits) + " citywide.",
                      "severity": "info"})

    # 7. Underused / shelfware: a sizable contract, in force long enough to have
    #    been drawn down, with almost no Checkbook spend against it → candidate to
    #    cancel. Guarded to the spend window (started ≥2022) so we don't false-flag
    #    contracts whose spend predates the scanned fiscal years.
    syear = str(row.get("start_year") or "")
    if (spent is not None and award >= 1_000_000 and days_since_start is not None
            and days_since_start >= 540 and syear >= "2022" and spent < award * 0.10):
        flags.append({"key": "underused", "label": "Underused",
                      "reason": f"Only ${spent:,.0f} of ${award:,.0f} awarded has been spent "
                                f"({(spent/award*100):.0f}%) despite being active ~{days_since_start//30} months — possible shelfware.",
                      "severity": "high"})

    # 8. Renewal chain: this award extends an existing engagement, or the same
    #    vendor+agency pairing recurs across many contracts → the city has been
    #    with this vendor for this function a long time, often without recompeting.
    va = va_stats or {}
    va_cnt = int(va.get("cnt") or 0)
    since = va.get("since")
    va_total = float(va.get("total") or 0)
    agency = row.get("agency") or "this agency"
    if method.lower() in RENEWAL_PROCUREMENT_METHODS or va_cnt >= 4:
        parts = []
        if method.lower() in RENEWAL_PROCUREMENT_METHODS:
            parts.append(f"this award is a “{method}”")
        if va_cnt >= 2:
            tail = f" with {agency}" + (f" since {since}" if since else "")
            tail += f" (${va_total/1_000_000:.0f}M total)" if va_total >= 1_000_000 else ""
            parts.append(f"{va_cnt} contracts{tail}")
        flags.append({"key": "renewal_chain", "label": "Renewal chain",
                      "reason": "Long-running engagement — " + "; ".join(parts) + ".",
                      "severity": "med"})

    # ASCII-normalize all surfaced text (handles em-dashes etc. baked into the
    # literal reasons above and any smart punctuation in AI rationales).
    for f in flags:
        f["label"] = _ascii(f["label"])
        f["reason"] = _ascii(f["reason"])
    return flags


@router.get("/digital-reform/stats")
async def get_digital_reform_stats():
    """Get summary stats for Digital Service Reform dashboard.

    ⚠ Legacy standalone endpoint — the live page reads /digital-reform/all.
    Kept on the shared scope so it can never disagree with the page; that adds
    the confirmed-non-tech exclusion it historically lacked."""
    sc = await digitalscope.load(PostgresModelAsync, logger)
    if sc.empty:
        return {"count": 0, "total": 0, "vendor_count": 0}

    stats_query = f"""
        SELECT COUNT(*) as count, COALESCE(SUM({sc.value('c')}), 0) as total
        FROM {sc.table()} c
        WHERE {sc.where('c')}{sc.exclude_nontech('c')}
    """
    stats_rows = await PostgresModelAsync.select_safe(stats_query)

    return {
        "count": stats_rows[0]['count'] if stats_rows else 0,
        "total": float(stats_rows[0]['total']) if stats_rows and stats_rows[0]['total'] else 0,
        "vendor_count": sc.vendor_count
    }

@router.get("/digital-reform/vendors")
async def get_digital_vendors(
    page: int = 1,
    limit: int = 25,
    sort: str = 'amount',
    order: str = 'desc'
):
    """Get paginated list of digital service vendors with contract counts.

    ⚠ Legacy standalone endpoint — the live page reads /digital-reform/all."""
    offset = (max(page, 1) - 1) * limit

    sc = await digitalscope.load(PostgresModelAsync, logger)
    if sc.empty:
        return {"vendors": [], "total": 0, "page": page, "total_pages": 0}

    # Get aggregated vendor stats with sorting
    sort_col = 'total' if sort == 'amount' else ('cnt' if sort == 'contracts' else 'vendor_name')
    order_dir = 'DESC' if order == 'desc' else 'ASC'

    query = f"""
        SELECT c.vendor_name, COUNT(*) as cnt, COALESCE(SUM({sc.value('c')}), 0) as total,
               v."PASSPort Supplier-ID" as vendor_id
        FROM {sc.table()} c
        LEFT JOIN vendors v ON LOWER(c.vendor_name) = LOWER(v."Vendor Name")
        WHERE {sc.where('c')}
        GROUP BY c.vendor_name, v."PASSPort Supplier-ID"
        ORDER BY {sort_col} {order_dir}
        LIMIT {limit} OFFSET {offset}
    """
    rows = await PostgresModelAsync.select_safe(query)

    # Get total count
    count_query = f"""
        SELECT COUNT(DISTINCT c.vendor_name) as c FROM {sc.table()} c WHERE {sc.where('c')}
    """
    count_rows = await PostgresModelAsync.select_safe(count_query)
    total = count_rows[0]['c'] if count_rows else 0

    vendors = []
    for r in rows:
        tag_info = sc.meta_for(r['vendor_name'])
        vendors.append({
            'vendor_id': r.get('vendor_id'),
            'vendor_name': r['vendor_name'],
            'classification': tag_info.get('classification', 'Digital'),
            'description': tag_info.get('description', ''),
            'contract_count': r['cnt'],
            'total_awarded': float(r['total'] or 0)
        })
    
    return {
        "vendors": vendors,
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit if total > 0 else 0
    }

@router.get("/digital-reform/contracts")
async def get_digital_contracts(
    page: int = 1,
    limit: int = 25,
    sort: str = 'date',
    order: str = 'desc'
):
    """Get paginated list of digital service contracts.

    ⚠ Legacy standalone endpoint — the live page reads /digital-reform/all."""
    offset = (max(page, 1) - 1) * limit

    sc = await digitalscope.load(PostgresModelAsync, logger)
    if sc.empty:
        return {"contracts": [], "total": 0, "page": page, "total_pages": 0}

    # Map sort column
    sort_map = {'date': 'start_date', 'amount': 'award_amount', 'vendor': 'vendor_name', 'end_date': 'end_date'}
    sort_col = sort_map.get(sort, 'start_date')
    order_dir = 'DESC' if order == 'desc' else 'ASC'

    query = f"""
        SELECT c.contract_id, c.ctr_id, c.contract_title, c.vendor_name, c.agency, c.start_date, c.end_date, c.award_amount,
               v."PASSPort Supplier-ID" as vendor_id
        FROM {sc.table()} c
        LEFT JOIN vendors v ON LOWER(c.vendor_name) = LOWER(v."Vendor Name")
        WHERE {sc.where('c')}
        ORDER BY c.{sort_col} {order_dir} NULLS LAST
        LIMIT {limit} OFFSET {offset}
    """
    rows = await PostgresModelAsync.select_safe(query)

    # Get total count
    count_query = f"SELECT COUNT(*) as c FROM {sc.table()} c WHERE {sc.where('c')}"
    count_rows = await PostgresModelAsync.select_safe(count_query)
    total = count_rows[0]['c'] if count_rows else 0

    contracts = []
    for r in rows:
        contracts.append({
            'contract_id': r['contract_id'],
            'ctr_id': r.get('ctr_id'),
            'contract_title': _ascii(r.get('contract_title', '')),
            'vendor_id': r.get('vendor_id'),
            'vendor_name': r['vendor_name'],
            'agency': r['agency'],
            'start_date': r['start_date'],
            'end_date': r['end_date'],
            'award_amount': float(r['award_amount'] or 0),
            'classification': sc.meta_for(r['vendor_name']).get('classification') or 'Digital'
        })

    return {
        "contracts": contracts,
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit if total > 0 else 0
    }

@router.get("/digital-reform/expiring")
async def get_expiring_digital_contracts(
    page: int = 1,
    limit: int = 25,
    sort: str = 'date',
    order: str = 'asc'
):
    """Get digital service contracts expiring in the next 5 years.

    ⚠ Legacy standalone endpoint — the live page reads /digital-reform/all.
    ⚠ On the QUEUE's scope, not the dashboard's: an expiring-contracts endpoint
    that disagreed with the Renewal Queue would be a second answer to the same
    question, which is the whole defect this change is closing. Its own window
    (5 years) is left alone — it is not the queue's window and never was.
    """
    offset = (max(page, 1) - 1) * limit

    sc = await digitalscope.load(PostgresModelAsync, logger,
                                 mode_override=digitalscope.queue_mode())
    if sc.empty:
        return {"contracts": [], "total": 0, "page": page, "total_pages": 0}

    # Date filter: today to 5 years from now
    # end_date is stored as MM/DD/YYYY format, so we need to convert for comparison
    order_dir = 'ASC' if order == 'asc' else 'DESC'
    # Only the text end_date column may be parsed with TO_DATE; award_amount is
    # numeric (double precision) and must be sorted raw, else to_date() errors.
    order_expr = "TO_DATE(c.end_date, 'MM/DD/YYYY')" if sort == 'date' else "c.award_amount"

    # ⚠⚠ NO `LEFT JOIN vendors` — and this one is a correction to #244, which put
    # this endpoint on the queue's scope precisely so it could not be "a second
    # answer to the same question", then left the duplicating join in place. With
    # the join, one row of this PAGINATED result was a duplicate while `count_query`
    # below (which has no join) reported the undeduplicated total — so the endpoint
    # disagreed both with the page and with its own `total`.
    query = f"""
        SELECT c.contract_id, c.ctr_id, c.contract_title, c.vendor_name, c.agency, c.start_date, c.end_date, c.award_amount
        FROM {sc.table()} c
        WHERE {sc.where('c')}
          AND c.end_date IS NOT NULL
          AND LENGTH(c.end_date) = 10
          AND TO_DATE(c.end_date, 'MM/DD/YYYY') >= CURRENT_DATE
          AND TO_DATE(c.end_date, 'MM/DD/YYYY') <= CURRENT_DATE + INTERVAL '5 years'
        ORDER BY {order_expr} {order_dir} NULLS LAST, c.contract_id ASC
        LIMIT {limit} OFFSET {offset}
    """
    rows = await PostgresModelAsync.select_safe(query)
    # ⚠ A tiebreak, because this endpoint is PAGINATED with OFFSET: without it, two
    # contracts sharing an end_date can swap between page 1 and page 2 and a reader
    # sees one twice. Same reasoning as the queue's.
    legacy_vendor_ids = await vendorids.unique_map(PostgresModelAsync, logger)

    count_query = f"""
        SELECT COUNT(*) as c FROM {sc.table()} c
        WHERE {sc.where('c')}
          AND c.end_date IS NOT NULL
          AND LENGTH(c.end_date) = 10
          AND TO_DATE(c.end_date, 'MM/DD/YYYY') >= CURRENT_DATE
          AND TO_DATE(c.end_date, 'MM/DD/YYYY') <= CURRENT_DATE + INTERVAL '5 years'
    """
    count_rows = await PostgresModelAsync.select_safe(count_query)
    total = count_rows[0]['c'] if count_rows else 0

    contracts = []
    for r in rows:
        contracts.append({
            'contract_id': r['contract_id'],
            'ctr_id': r.get('ctr_id'),
            'contract_title': _ascii(r.get('contract_title', '')),
            'vendor_id': legacy_vendor_ids.get(vendorids.key(r.get('vendor_name'))),
            'vendor_name': r['vendor_name'],
            'agency': r['agency'],
            'start_date': r['start_date'],
            'end_date': r['end_date'],
            'award_amount': float(r['award_amount'] or 0),
            'classification': sc.meta_for(r['vendor_name']).get('classification') or 'Digital'
        })
    
    return {
        "contracts": contracts,
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit if total > 0 else 0
    }

@router.get("/digital-reform/charts")
async def get_digital_charts():
    """Get chart data for Digital Service Reform dashboard."""
    
    sc = await digitalscope.load(PostgresModelAsync, logger)
    if sc.empty:
        return {"trend": {"labels": [], "values": []}, "agencies": {"labels": [], "values": []}}

    # Spending trend by year
    trend_query = f"""
        SELECT substr(c.start_date, 7, 4) as year, SUM({sc.value('c')}) as total
        FROM {sc.table()} c
        WHERE {sc.where('c')}
          AND length(c.start_date) = 10
        GROUP BY year
        ORDER BY year
    """
    trend_rows = await PostgresModelAsync.select_safe(trend_query)
    
    trend = {"labels": [], "values": []}
    for r in trend_rows:
        try:
            y = int(r['year'])
            if 2018 <= y <= 2030:
                trend['labels'].append(str(y))
                trend['values'].append(float(r['total'] or 0))
        except:
            pass
    
    # Top agencies by digital spending
    agency_query = f"""
        SELECT c.agency, SUM({sc.value('c')}) as total
        FROM {sc.table()} c
        WHERE {sc.where('c')}
          AND c.agency IS NOT NULL AND c.agency != ''
        GROUP BY c.agency
        ORDER BY total DESC
        LIMIT 8
    """
    agency_rows = await PostgresModelAsync.select_safe(agency_query)
    
    agencies = {"labels": [], "values": []}
    for r in agency_rows:
        agencies['labels'].append(r['agency'][:40])
        agencies['values'].append(float(r['total'] or 0))
    
    # Expiring contracts by year (next 5 years)
    # end_date is stored as MM/DD/YYYY format
    expiring_query = f"""
        SELECT substr(c.end_date, 7, 4) as year, SUM({sc.value('c')}) as total
        FROM {sc.table()} c
        WHERE {sc.where('c')}
          AND c.end_date IS NOT NULL
          AND LENGTH(c.end_date) = 10
          AND TO_DATE(c.end_date, 'MM/DD/YYYY') >= CURRENT_DATE
          AND TO_DATE(c.end_date, 'MM/DD/YYYY') <= CURRENT_DATE + INTERVAL '5 years'
        GROUP BY year
        ORDER BY year
    """
    expiring_rows = await PostgresModelAsync.select_safe(expiring_query)
    
    expiring = {"labels": [], "values": []}
    for r in expiring_rows:
        expiring['labels'].append(r['year'])
        expiring['values'].append(float(r['total'] or 0))
    
    # Expiring contracts by agency (next 5 years)
    expiring_agencies_query = f"""
        SELECT c.agency, SUM({sc.value('c')}) as total
        FROM {sc.table()} c
        WHERE {sc.where('c')}
          AND c.end_date IS NOT NULL
          AND LENGTH(c.end_date) = 10
          AND TO_DATE(c.end_date, 'MM/DD/YYYY') >= CURRENT_DATE
          AND TO_DATE(c.end_date, 'MM/DD/YYYY') <= CURRENT_DATE + INTERVAL '5 years'
          AND c.agency IS NOT NULL AND c.agency != ''
        GROUP BY c.agency
        ORDER BY total DESC
        LIMIT 8
    """
    expiring_agencies_rows = await PostgresModelAsync.select_safe(expiring_agencies_query)
    
    expiring_agencies = {"labels": [], "values": []}
    for r in expiring_agencies_rows:
        expiring_agencies['labels'].append(r['agency'][:40])
        expiring_agencies['values'].append(float(r['total'] or 0))
    
    return {
        "trend": trend,
        "agencies": agencies,
        "expiring": expiring,
        "expiring_agencies": expiring_agencies
    }


@router.get("/digital-reform/all")
async def get_digital_reform_all(
    vendor_page: int = 1, vendor_limit: int = 25,
    vendor_sort: str = 'amount', vendor_order: str = 'desc',
    vendor_q: str = '',
    contract_page: int = 1, contract_limit: int = 25,
    contract_sort: str = 'date', contract_order: str = 'desc',
    contract_q: str = '', contract_method: str = '',
    expiring_page: int = 1, expiring_limit: int = 25,
    expiring_sort: str = 'date', expiring_order: str = 'asc',
    expiring_year: str = '', expiring_agency: str = '',
    expiring_method: str = '', expiring_min: float = 0,
    expiring_flag: str = '', expiring_category: str = '',
    expiring_license: str = '', expiring_buildbuy: str = '',
    expiring_shownontech: str = '', expiring_product: str = '',
    # The composition bar's drill-down: a segment slug from modules/techsegments.
    contract_segment: str = ''
):
    """Combined digital reform endpoint — fetches vendor tags once, runs all
    queries concurrently. Replaces 5 serial PHP→API calls with 1.
    Results are cached (see TTL). Supports search/filtering on the vendor and
    contract tables, plus a "Renewal Review Queue" over contracts expiring
    before 2030 (triage filters + transparent review flags + City Record links).
    """
    # Normalize params BEFORE building the cache key. The query logic below
    # already clamps pages (max(page,1)) and maps sorts via allow-lists, so
    # results were always correct — but the cache KEY used the raw params, so
    # e.g. vendor_page=-17 and vendor_page=-5 keyed two entries for the same
    # page-1 result. Canonicalizing here collapses those onto one key (a huge
    # reduction in the key space a scraper can generate) without changing any
    # legitimate response. Values map to the same canonical form the queries use.
    vendor_page = max(1, vendor_page)
    contract_page = max(1, contract_page)
    expiring_page = max(1, expiring_page)
    vendor_limit = min(max(1, vendor_limit), 100)
    contract_limit = min(max(1, contract_limit), 100)
    expiring_limit = min(max(1, expiring_limit), 100)
    vendor_sort = vendor_sort if vendor_sort in ('amount', 'contracts') else 'name'
    contract_sort = contract_sort if contract_sort in ('date', 'amount', 'vendor', 'end_date') else 'date'
    expiring_sort = expiring_sort if expiring_sort in ('amount', 'priority') else 'date'
    vendor_order = 'desc' if vendor_order == 'desc' else 'asc'
    contract_order = 'desc' if contract_order == 'desc' else 'asc'
    expiring_order = 'desc' if expiring_order == 'desc' else 'asc'

    # Build cache key from all params. ⚠ The scope mode leads it: the mode only
    # changes with a restart (which clears this in-memory cache anyway), but a
    # key that names its scope can never serve tag-mode numbers as derived ones.
    cache_key = (
        f"{digitalscope.mode()}:{digitalscope.queue_mode()}:"
        f"{vendor_page}:{vendor_limit}:{vendor_sort}:{vendor_order}:{vendor_q}:"
        f"{contract_page}:{contract_limit}:{contract_sort}:{contract_order}:{contract_q}:{contract_method}:{contract_segment}:"
        f"{expiring_page}:{expiring_limit}:{expiring_sort}:{expiring_order}:"
        f"{expiring_year}:{expiring_agency}:{expiring_method}:{expiring_min}:{expiring_flag}:"
        f"{expiring_category}:{expiring_license}:{expiring_buildbuy}:{expiring_shownontech}:"
        f"{expiring_product}"
    )
    cached = _dr_cache_get(cache_key)
    if cached is not None:
        return cached

    # ⚠ TWO scope resolutions, on purpose and temporarily. modules/digitalscope.py
    # owns what "digital" means; the Renewal Queue is already on the derived scope
    # while the Overview sections wait for their rebuild, so `sc` serves the
    # dashboard and `qsc` serves the queue (and the two EXPIRING charts, which
    # render only on the queue page — a table and the chart above it disagreeing
    # would be worse than either scope).
    sc = await digitalscope.load(PostgresModelAsync, logger)
    qsc = (sc if digitalscope.queue_mode() == sc.mode
           else await digitalscope.load(PostgresModelAsync, logger,
                                        mode_override=digitalscope.queue_mode()))
    # ⚠ BOTH must be empty for the zero-shell. It used to key on the dashboard
    # scope alone, which would now serve an empty queue whenever `vendor_tags` is
    # missing — a table the queue's own scope can populate perfectly well.
    if sc.empty and qsc.empty:
        return {
            "stats": {"count": 0, "total": 0, "vendor_count": 0,
                      "active_count": 0, "active_total": 0,
                      "ended_count": 0, "ended_total": 0},
            "charts": {"trend": {"labels": [], "values": []}, "agencies": {"labels": [], "values": []},
                       "expiring": {"labels": [], "values": []}, "expiring_agencies": {"labels": [], "values": []}},
            "vendors": {"vendors": [], "total": 0, "page": 1, "total_pages": 0},
            "contracts": {"contracts": [], "total": 0, "page": 1, "total_pages": 0,
                          "segment": "", "segment_slug": ""},
            "composition": {"available": False, "segments": [], "bar": [], "totals": {},
                            "reason": "no contracts in scope"},
            "pipeline": {"rows": [], "count": 0, "ceiling": 0, "masters": 0,
                         "floor": pipelinevehicles.DISPLAY_FLOOR, "vendors": 0},
            "scope": {"mode": digitalscope.mode(), "positive": False, "vendor_count": 0},
            "expiring": {"contracts": [], "total": 0, "page": 1, "total_pages": 0,
                         "summary": {"count": 0, "total_value": 0, "build_your_own": 0,
                                     "class_lever": 0,
                                     "non_competitive": 0, "no_rebid": 0, "scope_growth": 0,
                                     "high_value_near_term": 0, "vendor_lock_in": 0,
                                     "underused": 0, "renewal_chain": 0,
                                     "licenses": 0, "licenses_value": 0,
                                     "nontech_excluded": 0},
                         "scope": {"mode": digitalscope.queue_mode(), "positive": False},
                         "options": {"years": [], "agencies": [], "methods": [], "categories": []}},
            "contract_options": {"methods": []},
        }

    nondigital_exclude = sc.exclude_nontech
    is_digital_expr = sc.is_digital

    # --- Define concurrent query coroutines ---

    async def _stats():
        # ⚠ ACTIVE vs ENDED, because the headline is otherwise read as current
        # exposure and it is not: measured on the derived scope, 3,653 of 4,397
        # contracts have ALREADY ENDED — 83% by count, 45% by value. The licences
        # page learned this the hard way (72% of its inventory had ended with
        # nothing on the page saying so).
        # ⚠ "Ended" is a positive test on a usable end_date, so a contract with no
        # parseable date counts as ACTIVE and the page's label says "not known to
        # have ended". Guessing the other way would quietly shrink the live figure.
        ended = ("(c.end_date IS NOT NULL AND LENGTH(c.end_date) = 10 "
                 "AND TO_DATE(c.end_date, 'MM/DD/YYYY') < CURRENT_DATE)")
        q = (f"SELECT COUNT(*) as count, COALESCE(SUM({sc.value('c')}), 0) as total, "
             f"COUNT(*) FILTER (WHERE {ended}) as ended_count, "
             f"COALESCE(SUM({sc.value('c')}) FILTER (WHERE {ended}), 0) as ended_total "
             f"FROM {sc.table()} c WHERE {sc.where('c')}" + nondigital_exclude("c"))
        rows = await PostgresModelAsync.select_safe(q)
        r = rows[0] if rows else {}
        count = r.get('count') or 0
        total = float(r.get('total') or 0)
        ended_count = r.get('ended_count') or 0
        ended_total = float(r.get('ended_total') or 0)
        return {
            "count": count,
            "total": total,
            "vendor_count": sc.vendor_count,
            "ended_count": ended_count,
            "ended_total": ended_total,
            # ⚠ Derived by SUBTRACTION from the same query, never a second predicate.
            # Two independent definitions of "active" on one page is how the two
            # expiring figures on the licences page came to disagree.
            "active_count": count - ended_count,
            "active_total": total - ended_total,
        }

    async def _composition():
        """The Overview's headline: how the technology universe divides up.

        ⚠ ONE ROW PER CONTRACT, one segment per contract — see
        modules/techsegments. The whole set is pulled once (4,397 rows) and
        rolled up in Python, so the bar, the table and the segment totals are the
        same arithmetic rather than three GROUP BYs that can drift apart.
        """
        # ⚠ DERIVED SCOPE ONLY, and it says so rather than approximating. Tag mode is
        # amendment-ROW grain, so a contract with three amendments would be counted
        # three times in its segment and the bar would not be a partition of
        # anything. A page that hides the lens on a rollback is honest; one that
        # shows a triple-counted bar is not.
        if not sc.enr_exists or sc.mode != "derived":
            return {"available": False, "segments": [], "bar": [], "totals": {},
                    "reason": ("the enrichment table is missing" if not sc.enr_exists
                               else f"composition needs one row per contract; scope is '{sc.mode}'")}
        q = f"""
            SELECT {sc.value('c')} AS value, e.is_license, e.function_category,
                   (c.end_date IS NOT NULL AND LENGTH(c.end_date) = 10
                    AND TO_DATE(c.end_date, 'MM/DD/YYYY') < CURRENT_DATE) AS ended
            FROM {sc.table()} c
            JOIN digital_contract_enrichment e ON e.contract_id = c.contract_id
            WHERE {sc.where('c')}{nondigital_exclude("c")}
        """
        try:
            rows = await PostgresModelAsync.select_safe(q) or []
        except Exception as exc:  # noqa: BLE001
            # ALERTS: the Overview's whole composition bar; `available: False` renders as nothing.
            logger.error(f"[oce] composition unavailable: {exc_str(exc)}")
            return {"available": False, "segments": [], "bar": [], "totals": {}}
        segments, bar = techsegments.rollup([dict(r) for r in rows])
        return {
            "available": bool(segments),
            "segments": segments,
            "bar": bar,
            # ⚠ The partition's own closure, in the payload, so the page can be
            # checked against itself and a guard can assert it adds up.
            # ⚠⚠ `value` WILL NOT EQUAL `stats.total` TO THE DOLLAR, and that is
            # arithmetic rather than a gap: `award_amount`/`current_amount` are
            # Postgres `real` (float32), so the tile's SUM() is accumulated in float32
            # by Postgres while these segments are summed in float64 by Python over
            # the very same rows. Measured: $10,610,503,478 here against
            # $10,610,510,848 there — $7,370 apart on $10.6B, 7e-7 relative, and
            # invisible at the $0.1M the page prints. The CONTRACT COUNTS match
            # exactly, which is the check that would actually catch a lost segment.
            "totals": {
                "contracts": sum(a["contracts"] for a in segments),
                "value": sum(a["value"] for a in segments),
                "segments": len(segments),
                "in_bar": len([b for b in bar if b.get("slug")]),
                "bar_floor_share": techsegments.BAR_MIN_SHARE,
            },
        }

    async def _charts():
        # Spending trend
        trend_q = f"""
            SELECT substr(c.start_date, 7, 4) as year, SUM({sc.value('c')}) as total
            FROM {sc.table()} c WHERE {sc.where('c')} AND length(c.start_date) = 10
              {nondigital_exclude("c")}
            GROUP BY year ORDER BY year
        """
        trend_rows = await PostgresModelAsync.select_safe(trend_q)
        trend = {"labels": [], "values": []}
        for r in (trend_rows or []):
            try:
                y = int(r['year'])
                if 2018 <= y <= 2030:
                    trend['labels'].append(str(y))
                    trend['values'].append(float(r['total'] or 0))
            except: pass

        # Top agencies
        ag_q = f"""
            SELECT c.agency, SUM({sc.value('c')}) as total FROM {sc.table()} c
            WHERE {sc.where('c')} AND c.agency IS NOT NULL AND c.agency != ''
              {nondigital_exclude("c")}
            GROUP BY c.agency ORDER BY total DESC LIMIT 8
        """
        ag_rows = await PostgresModelAsync.select_safe(ag_q)
        agencies = {"labels": [r['agency'][:40] for r in (ag_rows or [])],
                    "values": [float(r['total'] or 0) for r in (ag_rows or [])]}

        # Expiring by year.
        # ⚠ THE TWO EXPIRING CHARTS USE THE QUEUE'S SCOPE (`qsc`), not the
        # dashboard's — they render only on the Renewal Queue page, directly above
        # the table they describe. The window comes from modules/licensewindow so
        # the chart cannot cover a different span from the table.
        exp_q = f"""
            SELECT substr(c.end_date, 7, 4) as year, SUM({qsc.value('c')}) as total
            FROM {qsc.table()} c WHERE {qsc.where('c')}
              AND {licensewindow.sql_clause('c')}
              {qsc.exclude_nontech("c")}
            GROUP BY year ORDER BY year
        """
        exp_rows = await PostgresModelAsync.select_safe(exp_q)
        expiring_chart = {"labels": [r['year'] for r in (exp_rows or [])],
                          "values": [float(r['total'] or 0) for r in (exp_rows or [])]}

        # Expiring by agency (queue scope — see above).
        exp_ag_q = f"""
            SELECT c.agency, SUM({qsc.value('c')}) as total FROM {qsc.table()} c
            WHERE {qsc.where('c')}
              AND {licensewindow.sql_clause('c')}
              AND c.agency IS NOT NULL AND c.agency != ''
              {qsc.exclude_nontech("c")}
            GROUP BY c.agency ORDER BY total DESC LIMIT 8
        """
        exp_ag_rows = await PostgresModelAsync.select_safe(exp_ag_q)
        exp_agencies = {"labels": [r['agency'][:40] for r in (exp_ag_rows or [])],
                        "values": [float(r['total'] or 0) for r in (exp_ag_rows or [])]}

        return {"trend": trend, "agencies": agencies, "expiring": expiring_chart, "expiring_agencies": exp_agencies}

    async def _vendors():
        """Who the City buys technology from.

        ⚠⚠ "DIGITAL SHARE" IS GONE, and its removal is the point of this rebuild.
        The column divided a vendor's tagged-digital spend by their TOTAL City
        spend, which made Inter-Con SECURITY SYSTEMS — a physical-guard company —
        rank 5th at "100% digital share". Under a scope that admits a contract
        because the classifier confirmed it is technology, the honest columns are
        the confirmed ones: how many tech contracts, worth how much. A ratio
        against unrelated spend answered no question anyone had.

        ⚠ NO `LEFT JOIN vendors` — 48 names hold more than one row there, which
        listed a vendor twice (measured 183rd in this very table). Ids come from
        vendorids.unique_map.
        """
        v_offset = (max(vendor_page, 1) - 1) * vendor_limit
        sort_col = ('tech_total' if vendor_sort == 'amount'
                    else ('tech_cnt' if vendor_sort == 'contracts' else 'vendor_name'))
        order_dir = 'DESC' if vendor_order == 'desc' else 'ASC'
        dig = is_digital_expr('c')
        # Optional name search (parameterized — $1 used in both the page + count query).
        params = []
        search_clause = ""
        if vendor_q.strip():
            params.append(f"%{vendor_q.strip().lower()}%")
            search_clause = " AND LOWER(c.vendor_name) LIKE $1"
        q = f"""
            SELECT c.vendor_name,
                   COUNT(*) FILTER (WHERE {dig}) AS tech_cnt,
                   COALESCE(SUM({sc.value('c')}) FILTER (WHERE {dig}), 0) AS tech_total,
                   COUNT(DISTINCT c.agency) FILTER (WHERE {dig}) AS agencies
            FROM {sc.table()} c
            WHERE {sc.where('c')}{search_clause}
            GROUP BY c.vendor_name
            ORDER BY {sort_col} {order_dir} NULLS LAST, c.vendor_name ASC
            LIMIT {vendor_limit} OFFSET {v_offset}
        """
        rows = await PostgresModelAsync.select_safe(q, params)
        cnt_q = f"SELECT COUNT(DISTINCT c.vendor_name) as c FROM {sc.table()} c WHERE {sc.where('c')}{search_clause}"
        cnt_rows = await PostgresModelAsync.select_safe(cnt_q, params)
        total = cnt_rows[0]['c'] if cnt_rows else 0

        page_names = [r['vendor_name'] for r in (rows or []) if r.get('vendor_name')]
        vendor_ids = await vendorids.unique_map(PostgresModelAsync, logger)
        # ⚠ WHAT A VENDOR SELLS, DERIVED — not a hand-written reseller seed. The plan
        # asked for reseller annotations "where curation knows them"; the licence
        # inventory already knows them, and computing it means the annotation cannot
        # go stale. Measured: DELL MARKETING LP resolves to 18 licence families
        # (Microsoft, Red Hat, McAfee, SolarWinds…), which is what makes it visibly a
        # reseller, while American Traffic Solutions resolves to none.
        sells = {}
        if page_names:
            try:
                srows = await PostgresModelAsync.select_safe(f"""
                    SELECT c.vendor_name,
                           coalesce(lf.family, e.license_product) AS family,
                           SUM({sc.value('c')}) AS val
                    FROM {sc.table()} c
                    JOIN digital_contract_enrichment e ON e.contract_id = c.contract_id
                    LEFT JOIN license_family lf ON lf.product_raw = e.license_product
                    WHERE c.vendor_name = ANY($1) AND e.is_license
                      AND coalesce(lf.family, e.license_product, '') <> ''
                    GROUP BY 1, 2
                """, [page_names]) or []
                for r in srows:
                    sells.setdefault(r['vendor_name'], []).append(
                        (r['family'], float(r['val'] or 0)))
            except Exception as exc:  # noqa: BLE001
                logger.info(f"[oce] vendor licence families unavailable: {exc_str(exc)}")

        vendors_out = []
        for r in (rows or []):
            fams = sorted(sells.get(r['vendor_name'], []), key=lambda a: -a[1])
            vendors_out.append({
                'vendor_id': vendor_ids.get(vendorids.key(r['vendor_name'])),
                'vendor_name': r['vendor_name'],
                # ⚠ Named `tech_*`: these count only contracts the classification
                # confirmed, which is the whole claim the page is making.
                'contract_count': r['tech_cnt'],
                'total_awarded': float(r['tech_total'] or 0),
                'agencies': r['agencies'],
                # ⚠ CAPPED AT 4, WITH THE FULL COUNT BESIDE IT. Dell resolves to 18;
                # printing 18 names in a table cell is not an annotation, and
                # printing 4 without saying "of 18" is the count-before-you-cap
                # defect this codebase has paid for twice.
                'sells': [f for f, _ in fams[:4]],
                'sells_total': len(fams),
            })
        return {"vendors": vendors_out, "total": total, "page": vendor_page,
                "total_pages": (total + vendor_limit - 1) // vendor_limit if total > 0 else 0}

    async def _contracts():
        c_offset = (max(contract_page, 1) - 1) * contract_limit
        sort_map = {'date': 'start_date', 'amount': 'award_amount', 'vendor': 'vendor_name', 'end_date': 'end_date'}
        sort_col = sort_map.get(contract_sort, 'start_date')
        order_dir = 'DESC' if contract_order == 'desc' else 'ASC'
        # Optional keyword search (vendor/title/agency/id) + procurement-method filter.
        params = []
        filt = ""
        if contract_q.strip():
            params.append(f"%{contract_q.strip().lower()}%")
            i = len(params)
            filt += (f" AND (LOWER(c.vendor_name) LIKE ${i} OR LOWER(c.contract_title) LIKE ${i}"
                     f" OR LOWER(c.agency) LIKE ${i} OR LOWER(c.contract_id) LIKE ${i})")
        if contract_method.strip():
            params.append(contract_method.strip())
            filt += f" AND c.procurement_method = ${len(params)}"
        # ⚠ THE COMPOSITION BAR'S DRILL-DOWN. Resolved through modules/techsegments,
        # never re-derived here: the bar and this filter must be the same definition
        # or a segment's table will not add up to the segment it was reached from.
        # An unknown slug resolves to "" and filters nothing, rather than emptying
        # the table and looking like "no such contracts".
        seg_name = techsegments.resolve_slug(contract_segment, composition_segments)
        if seg_name:
            pred = techsegments.sql_predicate(seg_name, len(params) + 1)
            if pred:
                sql_frag, seg_params = pred
                params.extend(seg_params)
                filt += (" AND EXISTS (SELECT 1 FROM digital_contract_enrichment e "
                         f"WHERE e.contract_id = c.contract_id AND {sql_frag})")
        filt += nondigital_exclude("c")  # digital-relevant contracts only
        # ⚠ NO `LEFT JOIN vendors` — see _vendors. It also made `total` (computed
        # below without the join) disagree with the rows on this very table.
        # ⚠ A LEFT JOIN on the enrichment is safe here and ONLY here because
        # `digital_contract_enrichment` has `PRIMARY KEY (contract_id)` — verified on
        # prod: 36,413 rows, 36,413 distinct ids, 0 duplicates. That is the property
        # the `vendors` join never had, and the reason to state it rather than assume
        # it. It gives each row its composition segment, which replaces a
        # `classification` badge that read the constant "Digital" on every row.
        q = f"""
            SELECT c.contract_id, c.ctr_id, c.contract_title, c.vendor_name, c.agency,
                   c.procurement_method, c.start_date, c.end_date, c.award_amount,
                   e.is_license, e.function_category
            FROM {sc.table()} c
            LEFT JOIN digital_contract_enrichment e ON e.contract_id = c.contract_id
            WHERE {sc.where('c')}{filt}
            ORDER BY c.{sort_col} {order_dir} NULLS LAST, c.contract_id ASC
            LIMIT {contract_limit} OFFSET {c_offset}
        """
        rows = await PostgresModelAsync.select_safe(q, params)
        cnt_q = f"SELECT COUNT(*) as c FROM {sc.table()} c WHERE {sc.where('c')}{filt}"
        cnt_rows = await PostgresModelAsync.select_safe(cnt_q, params)
        total = cnt_rows[0]['c'] if cnt_rows else 0
        vendor_ids = await vendorids.unique_map(PostgresModelAsync, logger)
        contracts_out = []
        for r in (rows or []):
            contracts_out.append({
                'contract_id': r['contract_id'], 'ctr_id': r.get('ctr_id'),
                'contract_title': _ascii(r.get('contract_title', '')),
                'vendor_id': vendor_ids.get(vendorids.key(r.get('vendor_name'))),
                'vendor_name': r['vendor_name'],
                'agency': r['agency'], 'procurement_method': r.get('procurement_method', ''),
                'start_date': r['start_date'], 'end_date': r['end_date'],
                'award_amount': float(r['award_amount'] or 0),
                # Which composition segment this row is in — resolved through the
                # same module as the bar, so a row can never show a segment the bar
                # would have counted elsewhere.
                'segment': techsegments.segment_of(r.get('is_license'),
                                                   r.get('function_category')),
                'is_license': bool(r.get('is_license')),
            })
        return {"contracts": contracts_out, "total": total, "page": contract_page,
                "total_pages": (total + contract_limit - 1) // contract_limit if total > 0 else 0,
                # What the table is currently scoped to, so the page can show a
                # clearable chip instead of silently displaying a subset.
                "segment": seg_name, "segment_slug": techsegments.slug(seg_name) if seg_name else ""}

    async def _expiring():
        """Renewal Review Queue: every digital contract expiring before the shared
        horizon, enriched with review flags + City Record links, filtered/sorted/paged.

        The full set is small (≤~800 rows), so we pull it once and do flag
        computation, filtering, summary aggregation and pagination in Python —
        this keeps the transparent flags and the flag-based filter consistent
        with the summary counts, and needs only one row scan + two crol lookups.

        ⚠ SCOPED BY `qsc`, NOT `sc`. This page is on the derived scope
        (classification-confirmed technology, one row per contract) ahead of the
        Overview rebuild; see modules/digitalscope.QUEUE_MODE_ENV.
        """
        # 1. Full set: all digital contracts expiring between today and the horizon.
        # ⚠⚠ NO `LEFT JOIN vendors`. It used to resolve the supplier id here, and
        # 48 vendor names hold more than one row in that table, so the join
        # DUPLICATED a contract — CT1-017-20248805602 (Absorb Software LMS, two
        # supplier ids) is why this page reported 243 expiring licences where the
        # Licenses page reported 242. Ids now come from vendorids.unique_map below,
        # which cannot duplicate a row and refuses to guess between two companies.
        base_q = f"""
            SELECT c.contract_id, c.ctr_id, c.epin, c.normalized_contract_id, c.contract_title,
                   c.vendor_name, c.agency, c.procurement_method, c.program, c.industry,
                   c.start_date, c.end_date, c.award_amount, c.current_amount,
                   (TO_DATE(c.end_date, 'MM/DD/YYYY') - CURRENT_DATE) AS days_to_expiry,
                   CASE WHEN LENGTH(c.start_date) = 10
                        THEN (CURRENT_DATE - TO_DATE(c.start_date, 'MM/DD/YYYY')) END AS days_since_start,
                   substr(c.end_date, 7, 4) AS exp_year,
                   substr(c.start_date, 7, 4) AS start_year
            FROM {qsc.table()} c
            WHERE {qsc.where('c')}
              AND {licensewindow.sql_clause('c')}
            ORDER BY TO_DATE(c.end_date, 'MM/DD/YYYY') ASC, c.contract_id ASC
        """
        # ⚠ `c.contract_id` is a TIEBREAK, not decoration. 693 contracts share ~500
        # distinct end dates, so ordering on the date alone left tied rows in
        # whatever order the plan produced — and removing the vendors join changed
        # the plan, which is how a deep-diff of this payload turned up two rows
        # simply swapped. On a paginated table an unstable order can show one row
        # twice and hide another across two page loads.
        rows = await PostgresModelAsync.select_safe(base_q) or []
        vendor_ids = await vendorids.unique_map(PostgresModelAsync, logger)

        # 2. Which of these PINs have a *live or forthcoming procurement* posted in
        #    the City Record (= a replacement is visibly in motion)? Only Solicitation
        #    / Intent to Award / Vendor List notices count — a bare "Award" notice is
        #    just the ORIGINAL award and must NOT clear the "no re-bid" flag (the
        #    common case here: PINs carry only their old Award notice).
        all_epins = list({(r.get('epin') or '').strip() for r in rows
                          if r.get('epin') and len(str(r.get('epin')).strip()) >= 6})
        rebid_epins = set()
        if all_epins:
            try:
                m = await PostgresModelAsync.select_safe(
                    """SELECT DISTINCT trim("PIN") AS pin FROM crol
                       WHERE trim("PIN") = ANY($1)
                         AND "TypeOfNoticeDescription" IN ('Solicitation','Intent to Award','Vendor List')""",
                    [all_epins])
                rebid_epins = {row['pin'] for row in (m or [])}
            except Exception as exc:  # noqa: BLE001
                # ALERTS: queue-wide signal: every row silently loses its no-open-solicitation flag.
                logger.error(f"[oce] expiring re-bid lookup failed: {exc}")

        # 2b. Vendor footprint across ALL digital contracts (lock-in signal).
        # ⚠ Measured over the QUEUE's universe. Both this and 2c genuinely weaken
        # as the universe widens (lock-in 357 -> 301, renewal chain 391 -> 367):
        # a vendor's concentration is a share of the technology the City buys, so a
        # truer denominator means fewer vendors look concentrated. That is the
        # flags becoming more honest, not fewer problems existing.
        vendor_stats = {}
        try:
            vrows = await PostgresModelAsync.select_safe(
                # ⚠ `total` drives a PUBLISHED claim about a named vendor — the
                # lock-in flag reads "this vendor holds $189M total citywide" —
                # so it must not silently include ceilings the vendor has never
                # been paid against. Split here rather than at the flag, because
                # the flag's THRESHOLD is what the split changes: a vendor whose
                # book is mostly master ceilings should not trip a concentration
                # test on money nobody has spent. `sql_is_master` is the same
                # rule as `contractkind.is_master`, guard-pinned to agree.
                f"""SELECT c.vendor_name, COUNT(*) AS cnt, COUNT(DISTINCT c.agency) AS agencies,
                           COALESCE(SUM({qsc.value('c')}),0) AS total,
                           COALESCE(SUM({qsc.value('c')}) FILTER (
                               WHERE NOT ({contractkind.sql_is_master('c.contract_id')})),0)
                             AS committed_total,
                           COALESCE(SUM({qsc.value('c')}) FILTER (
                               WHERE {contractkind.sql_is_master('c.contract_id')}),0)
                             AS ceiling_total
                    FROM {qsc.table()} c WHERE {qsc.where('c')}
                    GROUP BY c.vendor_name""")
            vendor_stats = {r['vendor_name']: r for r in (vrows or [])}
        except Exception as exc:  # noqa: BLE001
            # ALERTS: queue-wide signal: every row silently loses its lock-in flag.
            logger.error(f"[oce] vendor concentration lookup failed: {exc}")

        # 2c. Vendor+agency relationship (renewal-chain signal).
        va_stats = {}
        try:
            varows = await PostgresModelAsync.select_safe(
                f"""SELECT c.vendor_name, c.agency, COUNT(*) AS cnt,
                           MIN(substr(c.start_date, 7, 4)) AS since,
                           COALESCE(SUM({qsc.value('c')}),0) AS total
                    FROM {qsc.table()} c WHERE {qsc.where('c')}
                      AND c.agency IS NOT NULL AND c.agency <> ''
                    GROUP BY c.vendor_name, c.agency""")
            va_stats = {(r['vendor_name'], r['agency']): r for r in (varows or [])}
        except Exception as exc:  # noqa: BLE001
            # ALERTS: queue-wide signal: every row silently loses its renewal-chain flag.
            logger.error(f"[oce] vendor+agency lookup failed: {exc}")

        # 2d. Checkbook spend per contract (cached daily; best-effort).
        spend_map = await _get_digital_spend_map(sc, qsc)

        # 2e. AI enrichment (build-vs-buy, license, function category, tech flag).
        enr_map = {}
        try:
            cids = [r['contract_id'] for r in rows if r.get('contract_id')]
            if cids:
                erows = await PostgresModelAsync.select_safe(
                    """SELECT contract_id, tech_relevant, is_license, license_product,
                              license_purpose, function_category, build_vs_buy, rationale
                       FROM digital_contract_enrichment WHERE contract_id = ANY($1)""", [cids])
                enr_map = {e['contract_id']: e for e in (erows or [])}
        except Exception as exc:  # noqa: BLE001
            # ALERTS: EVERY AI flag on the page. Sentry runs only where that table exists, so firing here means broken, not fresh.
            logger.error(f"[oce] enrichment lookup failed (table missing?): {exc}")

        # 2f. Product -> family (+ slug, + is_generic), for the Licenses page's deep
        # links. ⚠ SEPARATELY guarded on purpose. Folding this join into the query
        # above would mean a missing license_family table takes the whole `try` with
        # it and silently disables EVERY AI flag on this page -- a much larger
        # failure than losing one filter. Absent table => family falls back to
        # the raw product, and the page is merely ungrouped and unlinked.
        # ⚠ The SLUG is what makes a licence row link to its family page. Linking by
        # display name would break the moment a curated merge renamed a family;
        # licenses.py resolves /family/{slug} by slug for exactly that reason.
        family_map = {}
        try:
            frows = await PostgresModelAsync.select_safe(
                "SELECT product_raw, family, slug, is_generic FROM license_family")
            family_map = {f['product_raw']: f for f in (frows or [])}
        except Exception as exc:  # noqa: BLE001
            logger.info(f"[oce] license_family unavailable, using raw products: {exc_str(exc)}")

        # 2g. Purchase class, resolved through modules/licenseclass at PRODUCT grain
        # with a FAMILY fallback -- the SAME resolver the Licenses page uses, so the
        # two pages cannot disagree about what kind of purchase a contract is.
        # ⚠ Separately guarded, same reasoning as 2f: absent tables mean no class,
        # which restores the pre-gate behaviour (every row asked the build-your-own
        # question) rather than emptying the queue.
        fam_classes, prod_classes = {}, {}
        try:
            crows = await PostgresModelAsync.select_safe(
                "SELECT family, class, lever, why, tier FROM license_family_class")
            fam_classes = {c['family']: dict(c) for c in (crows or [])}
        except Exception as exc:  # noqa: BLE001
            logger.info(f"[oce] license_family_class unavailable: {exc_str(exc)}")
        try:
            prows = await PostgresModelAsync.select_safe(
                "SELECT product_norm, class, lever, why, tier FROM license_product_class")
            prod_classes = {p['product_norm']: dict(p) for p in (prows or [])}
        except Exception as exc:  # noqa: BLE001
            logger.info(f"[oce] license_product_class unavailable: {exc_str(exc)}")

        # 3. Enrich each row with flags + tidy fields.
        enriched = []
        for r in rows:
            epin = (r.get('epin') or '').strip()
            days = r.get('days_to_expiry')
            days = int(days) if days is not None else None
            dss = r.get('days_since_start')
            dss = int(dss) if dss is not None else None
            has_rebid = epin in rebid_epins
            ncid = (r.get('normalized_contract_id') or '').upper()
            spent = spend_map.get(ncid) if ncid else None
            award_amt = float(r.get('award_amount') or 0)
            enr = enr_map.get(r['contract_id']) or {}
            product = enr.get('license_product') or ''
            fam_row = family_map.get(product) or {}
            family = fam_row.get('family') or product
            # ⚠ Resolved for EVERY row, licence or not: a non-licence contract has
            # no family, so resolve() returns an empty class and the row keeps the
            # unclassified behaviour. That is the intended asymmetry — the gate
            # exists to stop asking "could we build this?" of hosting and support,
            # not to stop asking it of a website-development service.
            pclass = licenseclass.resolve(product, family, prod_classes, fam_classes)
            flags = _review_flags(r, days, has_rebid, vendor_stats.get(r['vendor_name']),
                                   va_stats.get((r['vendor_name'], r.get('agency'))), spent, dss, enr,
                                   pclass)
            enriched.append({
                'contract_id': r['contract_id'], 'ctr_id': r.get('ctr_id'), 'epin': epin,
                'contract_title': _ascii(r.get('contract_title', '')),
                'vendor_id': vendor_ids.get(vendorids.key(r.get('vendor_name'))),
                'vendor_name': r['vendor_name'],
                'agency': r.get('agency', ''), 'procurement_method': r.get('procurement_method', ''),
                'program': r.get('program', ''), 'industry': r.get('industry', ''),
                'start_date': r.get('start_date'), 'end_date': r.get('end_date'),
                'days_to_expiry': days, 'exp_year': r.get('exp_year'),
                'award_amount': award_amt,
                'current_amount': float(r.get('current_amount') or 0),
                'spent': spent,
                'utilization': (spent / award_amt) if (spent is not None and award_amt > 0) else None,
                'has_rebid': has_rebid,
                'tech_relevant': enr.get('tech_relevant'),
                'is_license': enr.get('is_license'),
                'license_product': _ascii(product),
                'license_family': _ascii(family),
                # ⚠ Empty for a generic family ("Various", "Unknown"): those are not
                # products, so their family page would tell a reader nothing and the
                # Licenses page itself refuses to rank them. No slug => no link.
                'license_family_slug': ('' if fam_row.get('is_generic')
                                        else (fam_row.get('slug') or '')),
                'license_purpose': _ascii(enr.get('license_purpose') or ''),
                'function_category': _ascii(enr.get('function_category') or ''),
                'build_vs_buy': enr.get('build_vs_buy') or '',
                'ai_rationale': _ascii(enr.get('rationale') or ''),
                # The purchase class, so the page can show which question this
                # contract deserves instead of assuming it is the substitution one.
                'purchase_class': pclass.get('class') or '',
                'purchase_class_lever': pclass.get('lever') or '',
                'purchase_class_source': pclass.get('source') or '',
                'purchase_class_tier': pclass.get('tier') or '',
                'flags': flags, 'flag_keys': [f['key'] for f in flags],
                # ⚠ Whether this row's money is COMMITTED or a CEILING to buy
                # against. A master agreement carries no payments under its own
                # id — measured 0 of 57 on this queue, against 88% of ordinary
                # contracts — so a $50.0M master rendered like a $50.0M contract
                # reads as spend about to renew. Served per row so the page can
                # label it rather than re-deriving the rule in Blade.
                'amount_kind': 'ceiling' if contractkind.is_master(
                    r['contract_id']) else 'committed',
                'contract_kind': contractkind.kind(r['contract_id']),
                # ⚠ `classification` REMOVED (#247). It came from vendor_tags, which the
                # derived scope does not read — so after the flip it returned the
                # constant 'Digital' for every row: a key that looks like data and says
                # nothing. Nothing rendered it (checked across the views, the public API
                # and the MCP server), and a payload deep-diff against prod showed these
                # 17 rows as the ONLY difference in the queue, which is how it surfaced.
            })

        # 4. Filter options derived from the full set (so the dropdowns are stable).
        options = {
            'years': sorted({e['exp_year'] for e in enriched if e['exp_year']}),
            'agencies': sorted({e['agency'] for e in enriched if e['agency']}),
            'methods': sorted({e['procurement_method'] for e in enriched if e['procurement_method']}),
            'categories': sorted({e['function_category'] for e in enriched
                                  if e['function_category'] and e['function_category'] != 'Non-tech'}),
        }

        # Likely-non-tech contracts (AI tech_relevant=False) are excluded by default.
        # ⚠⚠ THIS IS A TAG-SCOPE DEVICE AND IT IS RETIRED ON THE DERIVED SCOPE.
        # Under the vendor-name tag, "digital" admitted pest control and ship repair,
        # so the page had to hide 105 confirmed non-tech contracts and disclose that
        # it was hiding them. The derived scope is a POSITIVE condition — a contract
        # is here because the classification confirmed it is technology — so nothing
        # can be admitted and then hidden, and `nontech_excluded` is 0 by
        # construction. Kept computed rather than deleted so the number stays
        # MEASURED: if it is ever non-zero on the derived scope, that is a defect in
        # the scope, not a filter to re-expose.
        # ⚠ `expiring_shownontech` is therefore inert on the derived scope. The UI
        # control is gone; the parameter is still accepted so an old bookmark or the
        # Overview's forwarded query string cannot 422.
        nontech_total = sum(1 for e in enriched if e['tech_relevant'] is False)
        show_nontech = expiring_shownontech in ('1', 'true', 'yes')

        # 5. Apply triage filters.
        def _keep(e):
            if not show_nontech and e['tech_relevant'] is False: return False
            if expiring_year and e['exp_year'] != expiring_year: return False
            if expiring_agency and e['agency'] != expiring_agency: return False
            if expiring_method and e['procurement_method'] != expiring_method: return False
            if expiring_min and e['award_amount'] < expiring_min: return False
            if expiring_flag and expiring_flag not in e['flag_keys']: return False
            if expiring_category and e['function_category'] != expiring_category: return False
            if expiring_buildbuy and e['build_vs_buy'] != expiring_buildbuy: return False
            if expiring_license in ('1', 'true', 'yes') and not e['is_license']: return False
            # Matches a FAMILY or a raw product name, so a Licenses-page link
            # works whether or not the family mapping table is present.
            if expiring_product and expiring_product not in (
                    e['license_family'], e['license_product']): return False
            return True
        filtered = [e for e in enriched if _keep(e)]

        # 6. Summary over the filtered set (drives the headline strip).
        # ⚠⚠ COMMITTED MONEY AND CEILINGS ARE NOT THE SAME NUMBER, so the summary
        # reports both and never only their sum. 57 of these rows are master
        # agreements carrying $1,623.9M of ceiling that no agency has drawn
        # against — 0% of masters have a payment under their own id, against 88%
        # of ordinary contracts. See modules/contractkind. `total_value` is kept
        # (it is what the existing tile renders and consumers read) but is now
        # accompanied by the split, so a page can stop captioning it as spend.
        _committed, _ceiling, _n_committed, _n_ceiling = contractkind.split_amounts(
            filtered, amount=lambda e: e['award_amount'])
        summary = {
            'count': len(filtered),
            'total_value': sum(e['award_amount'] for e in filtered),
            'committed_value': _committed,
            'ceiling_value': _ceiling,
            'committed_count': _n_committed,
            'ceiling_count': _n_ceiling,
            'build_your_own': sum(1 for e in filtered if 'build_your_own' in e['flag_keys']),
            # Rows where the substitution question was withdrawn because the
            # purchase class implies a different lever. See CLASS_LEVER_LABELS.
            'class_lever': sum(1 for e in filtered if 'class_lever' in e['flag_keys']),
            'non_competitive': sum(1 for e in filtered if 'non_competitive' in e['flag_keys']),
            'no_rebid': sum(1 for e in filtered if 'no_rebid' in e['flag_keys']),
            'scope_growth': sum(1 for e in filtered if 'scope_growth' in e['flag_keys']),
            'high_value_near_term': sum(1 for e in filtered if 'high_value_near_term' in e['flag_keys']),
            'vendor_lock_in': sum(1 for e in filtered if 'vendor_lock_in' in e['flag_keys']),
            'underused': sum(1 for e in filtered if 'underused' in e['flag_keys']),
            'renewal_chain': sum(1 for e in filtered if 'renewal_chain' in e['flag_keys']),
            'licenses': sum(1 for e in filtered if e['is_license']),
            # ⚠ current-else-award, the LICENCES-PAGE money rule, so the two pages'
            # expiring-licence value is comparable figure-for-figure. `total_value`
            # above stays award_amount because the tile beside it says "Total
            # awarded"; mixing the two rules under one label is how a page ends up
            # with two numbers for one thing.
            'licenses_value': sum((e['current_amount'] or e['award_amount'])
                                  for e in filtered if e['is_license']),
            'nontech_excluded': 0 if show_nontech else nontech_total,
        }

        # 7. Sort. 'priority' = most flags first (then value); else date / amount.
        rev = (expiring_order == 'desc')
        if expiring_sort == 'amount':
            filtered.sort(key=lambda e: e['award_amount'], reverse=rev)
        elif expiring_sort == 'priority':
            filtered.sort(key=lambda e: (len(e['flags']), e['award_amount']), reverse=True)
        else:  # date
            filtered.sort(key=lambda e: (e['days_to_expiry'] is None, e['days_to_expiry'] or 0), reverse=rev)

        # 8. Paginate.
        total = len(filtered)
        e_offset = (max(expiring_page, 1) - 1) * expiring_limit
        page_rows = filtered[e_offset:e_offset + expiring_limit]

        # 9. Attach City Record notice details for the visible page only.
        page_epins = list({e['epin'] for e in page_rows if e['epin'] and len(e['epin']) >= 6})
        notices_by_epin: Dict[str, list] = {}
        if page_epins:
            try:
                nrows = await PostgresModelAsync.select_safe(
                    """
                    SELECT trim("PIN") AS pin, "ShortTitle" AS title,
                           "TypeOfNoticeDescription" AS type, "StartDate" AS date, "RequestID" AS rid
                    FROM crol WHERE trim("PIN") = ANY($1)
                    ORDER BY start_date_parsed DESC NULLS LAST
                    """,
                    [page_epins])
                for n in (nrows or []):
                    notices_by_epin.setdefault(n['pin'], []).append({
                        'title': _ascii(n.get('title') or 'Notice'),
                        'type': _ascii(n.get('type') or ''),
                        'date': (n.get('date') or '')[:10],
                        'url': f"https://a856-cityrecord.nyc.gov/RequestDetail/{n['rid']}",
                    })
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[oce] expiring notices lookup failed: {exc}")
        for e in page_rows:
            e['notices'] = notices_by_epin.get(e['epin'], [])[:5]

        return {"contracts": page_rows, "total": total, "page": expiring_page,
                "total_pages": (total + expiring_limit - 1) // expiring_limit if total > 0 else 0,
                "summary": summary, "options": options,
                # ⚠ The page states which scope it is on, from the payload, never
                # from copy. While the Overview and the queue run in different
                # scopes, a reader comparing two pages must be able to see that.
                "scope": {"mode": qsc.mode,
                          "positive": qsc.mode == "derived",
                          "horizon": licensewindow.HORIZON,
                          "one_row_per_contract": qsc.mode == "derived"}}

    async def _pipeline():
        """Citywide vehicles that have not reached registration — the section-level
        blind spot, and this page is its canonical home (the Licenses page points
        here rather than computing a second, narrower figure).

        ⚠ Scoped by the DERIVED tech vendor set, computed in SQL from the same
        predicate the page displays — never from the old vendor-name tag, which
        admits janitorial services and ship repair onto a technology page.
        ⚠ The literal table name is deliberately not written here: the ban guard in
        test_digitalscope.py strips `#` comments but cannot strip docstrings, because
        triple-quoted strings are also where SQL lives. Wording around it keeps the
        guard maximally strict, which is the right trade.
        ⚠ Tag mode returns the block empty rather than a tag-scoped version: the
        whole point of the move is one figure for the section.
        """
        if sc.mode != "derived":
            return {"rows": [], "count": 0, "ceiling": 0.0, "masters": 0,
                    "floor": pipelinevehicles.DISPLAY_FLOOR, "vendors": 0,
                    "unavailable_reason": f"scope is '{sc.mode}'"}
        try:
            vrows = await PostgresModelAsync.select_safe(
                f"""SELECT DISTINCT c.vendor_name FROM {sc.table()} c
                    WHERE {sc.where('c')} AND coalesce(c.vendor_name, '') <> ''""") or []
        except Exception as exc:  # noqa: BLE001
            # ALERTS: the whole pipeline block returns an empty shell that reads as "no vehicles".
            logger.error(f"[oce] pipeline vendor set unavailable: {exc_str(exc)}")
            return {"rows": [], "count": 0, "ceiling": 0.0, "masters": 0,
                    "floor": pipelinevehicles.DISPLAY_FLOOR, "vendors": 0}
        return await pipelinevehicles.load(
            PostgresModelAsync, [r["vendor_name"] for r in vrows], logger)

    async def _contract_options():
        """Distinct procurement methods across all digital contracts — feeds the
        contracts-table method filter dropdown."""
        rows = await PostgresModelAsync.select_safe(
            f"""SELECT DISTINCT c.procurement_method AS m FROM {sc.table()} c
                WHERE {sc.where('c')}
                  AND c.procurement_method IS NOT NULL AND c.procurement_method <> ''
                ORDER BY 1""")
        return {"methods": [r['m'] for r in (rows or [])]}

    # Run all query groups concurrently
    # ⚠ Composition runs FIRST, not in the gather: _contracts resolves its segment
    # filter against the segments this computes, so the bar and its drill-down are
    # provably the same partition. One query over ~4,400 rows.
    composition = await _composition()
    composition_segments = composition.get("segments") or []

    stats, charts, vendors, contracts, expiring_data, contract_options, pipeline = await asyncio.gather(
        _stats(), _charts(), _vendors(), _contracts(), _expiring(), _contract_options(), _pipeline()
    )

    result = {
        "stats": stats, "charts": charts, "vendors": vendors,
        "contracts": contracts, "expiring": expiring_data,
        "contract_options": contract_options,
        "composition": composition,
        # ⚠⚠ NEVER MERGED INTO A TOTAL — `ceiling`, not `value`. See
        # modules/pipelinevehicles. A test pins the separation on both pages.
        "pipeline": pipeline,
        # What "digital" means for this payload, so the page states its scope from
        # the data rather than from copy.
        "scope": {"mode": sc.mode, "positive": sc.mode == "derived",
                  "vendor_count": sc.vendor_count},
    }

    # Cache result
    _dr_cache_set(cache_key, result)

    return result

# ============================================================================
# Agencies Endpoints
# ============================================================================

async def _live_orgs(prefix: str = "AND", alias: str = "") -> str:
    """`AND retired_at IS NULL` for org lookups — see modules/orgfilter.py.

    Without it, `contracts.agency` could resolve to a retired duplicate: both
    `Public Design Commission` rows share a name, and only the id ordering kept
    the live one winning. That is luck, not logic.
    """
    from modules import orgfilter
    return await orgfilter.live_clause(
        lambda sql: PostgresModelAsync.select_safe(sql, []), prefix, alias)


async def _resolve_org_id(agency_name: Optional[str]):
    """Resolve a contracts.agency name to a wegov_orgs id via an EXACT normalized
    (upper/trim) match on name or alternate_name. Deliberately conservative — a
    fuzzy match could deep-link an agency to the wrong org profile, so unmatched
    agencies return None and keep the standalone procurement page. Returns int|None.
    """
    if not agency_name:
        return None
    rows = await PostgresModelAsync.select_safe(
        """
        SELECT id FROM wegov_orgs
        WHERE (UPPER(TRIM(name)) = UPPER(TRIM($1))
           OR UPPER(TRIM(COALESCE("alternate_name", ''))) = UPPER(TRIM($1))){live}
        ORDER BY id
        LIMIT 1
        """.format(live=await _live_orgs()),
        [agency_name],
    )
    return rows[0]["id"] if rows else None


@router.get("/agencies")
async def list_agencies(
    page: int = 1,
    limit: int = 50,
    q: Optional[str] = None,
    sort: str = 'amount',
    order: str = 'desc'
):
    """Get paginated list of agencies with contract counts, total spending, and top vendor."""
    offset = (max(page, 1) - 1) * limit

    # Base query to aggregate agencies from contracts. org_id is resolved by an
    # exact normalized name match to wegov_orgs so the listing can deep-link an
    # agency straight to its org profile (NULL → standalone procurement page).
    base_query = """
        SELECT
            c.agency as name,
            COUNT(DISTINCT c.ctr_id) as contract_count,
            COALESCE(SUM(c.award_amount), 0) as total_value,
            (SELECT o.id FROM wegov_orgs o
              WHERE (UPPER(TRIM(o.name)) = UPPER(TRIM(c.agency))
                 OR UPPER(TRIM(COALESCE(o."alternate_name", ''))) = UPPER(TRIM(c.agency)))
                 {live_o}
              ORDER BY o.id LIMIT 1) as org_id
        FROM contracts c
        WHERE c.agency IS NOT NULL AND c.agency != ''
    """.replace("{live_o}", await _live_orgs(alias="o"))

    if q:
        base_query += f" AND LOWER(c.agency) LIKE '%{q.lower()}%'"
    
    base_query += " GROUP BY c.agency"
    
    # Sorting
    sort_map = {
        'name': 'name',
        'count': 'contract_count',
        'amount': 'total_value'
    }
    sort_col = sort_map.get(sort, 'total_value')
    order_dir = 'DESC' if order.lower() == 'desc' else 'ASC'
    
    # Count query
    count_query = f"SELECT COUNT(*) as c FROM ({base_query}) as sub"
    count_result = await PostgresModelAsync.select_safe(count_query)
    total = count_result[0]['c'] if count_result else 0
    
    # Main query with pagination
    query = f"""
        {base_query}
        ORDER BY {sort_col} {order_dir}
        LIMIT {limit} OFFSET {offset}
    """
    
    rows = await PostgresModelAsync.select_safe(query)

    # Enrich each agency with its top vendor by total spend
    if rows:
        agency_names = [r['name'] for r in rows]
        placeholders = ', '.join(f'${i+1}' for i in range(len(agency_names)))
        top_vendor_query = f"""
            SELECT DISTINCT ON (agency) agency, vendor_name, total
            FROM (
                SELECT agency, vendor_name, SUM(award_amount) as total
                FROM contracts
                WHERE agency IN ({placeholders})
                  AND vendor_name IS NOT NULL AND vendor_name != ''
                GROUP BY agency, vendor_name
            ) sub
            ORDER BY agency, total DESC
        """
        top_vendors = await PostgresModelAsync.select_safe(top_vendor_query, agency_names)
        vendor_map = {r['agency']: r for r in (top_vendors or [])}
        for row in rows:
            tv = vendor_map.get(row['name'])
            row['top_vendor'] = tv['vendor_name'] if tv else None
            row['top_vendor_amount'] = float(tv['total']) if tv else 0
    
    return {
        "agencies": rows or [],
        "total": total,
        "page": page,
        "pages": math.ceil(total / limit) if limit else 1
    }




@router.get("/org/vendor-activity")
async def get_org_vendor_activity(org_id: int = Query(..., description="wegov_orgs.id")):
    """Does this org also hold City contracts, as a PASSPort vendor? (Track B.)

    Deliberately a SEPARATE endpoint rather than extra joins on
    /get/orgs/profile/{id}: that query already carries the Greenbook enrichment
    behind one try/except, so a missing table here would drop THAT too and
    silently strip agency heads and addresses from every org page. Small blast
    radius beats a tidy single query.

    ⚠ Contracts are counted by `vendor_name` EXACT equality — the same predicate
    `get_vendor` uses (`WHERE vendor_name = $1`). If this normalized instead, the
    figures on the org page and the vendor page would disagree, and there would
    be no way to tell which was right.

    ⚠ Only `passport_supplier_id` is read, never `candidate_supplier_id`: an
    unreviewed match must not be able to publish itself as fact.
    """
    try:
        link = await PostgresModelAsync.select_safe(
            "SELECT passport_supplier_id, vendor_name, match_tier, match_score, "
            "       matched_variant "
            "FROM org_vendor_crosswalk "
            "WHERE org_id = $1 AND passport_supplier_id IS NOT NULL", [org_id])
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[oce] org vendor-activity lookup failed for {org_id}: {exc}")
        return {"available": False, "linked": False}
    if not link:
        return {"available": True, "linked": False}

    row = link[0]
    stats = await PostgresModelAsync.select_safe(
        "SELECT count(*) AS n, "
        "       sum(COALESCE(award_amount, 0)) AS awarded, "
        "       sum(COALESCE(current_amount, 0)) AS current_total, "
        "       max(end_date) AS latest_end "
        "FROM contracts WHERE vendor_name = $1", [row["vendor_name"]])
    st = (stats or [{}])[0]
    return {
        "available": True,
        "linked": True,
        "supplier_id": row["passport_supplier_id"],
        "vendor_name": row["vendor_name"],
        # Surface HOW the link was made, so a name-based join is auditable
        # rather than presented as fact — the same discipline as the NYCHA block.
        "match": {"tier": row["match_tier"],
                  "score": float(row["match_score"]) if row["match_score"] is not None else None,
                  "matched_on": row["matched_variant"]},
        "contracts": int(st.get("n") or 0),
        "awarded": float(st.get("awarded") or 0),
        "current_amount": float(st.get("current_total") or 0),
        "latest_end": st.get("latest_end"),
    }


@router.get("/agency/summary")
async def get_agency_summary(name: str = Query(..., description="Agency name")):
    """Get lightweight procurement summary stats for an agency by name."""
    
    agency_name = name
    
    # Contracts stats — parameterized ($1) so agency names with apostrophes
    # (e.g. "Administration for Children's Services") don't break the SQL.
    contracts_query = """
        SELECT
            COUNT(*) as contracts_count,
            COALESCE(SUM(award_amount), 0) as total_awarded,
            COUNT(CASE WHEN LOWER(status) LIKE '%progress%' OR LOWER(status) LIKE '%active%' THEN 1 END) as active_contracts
        FROM contracts WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))
    """
    contracts_stats = await PostgresModelAsync.select_safe(contracts_query, [agency_name])

    # Solicitations count
    solicitations_query = """
        SELECT COUNT(*) as solicitations_count
        FROM solicitations WHERE LOWER(TRIM("Agency")) = LOWER(TRIM($1))
    """
    solicitations_stats = await PostgresModelAsync.select_safe(solicitations_query, [agency_name])
    
    c = contracts_stats[0] if contracts_stats else {}
    s = solicitations_stats[0] if solicitations_stats else {}
    
    return {
        "agency_name": agency_name,
        "contracts_count": c.get('contracts_count', 0),
        "total_awarded": float(c.get('total_awarded', 0) or 0),
        "active_contracts": c.get('active_contracts', 0),
        "solicitations_count": s.get('solicitations_count', 0)
    }


@router.get("/agency/procurement")
async def get_agency_procurement(name: str = Query(..., description="Agency name")):
    """Get procurement profile for an agency by name. Cached 24h."""

    # Check cache first
    cache_key = f"agency_procurement:{name.lower().strip()}"
    cached = _dr_cache_get(cache_key)
    if cached is not None:
        return cached
    
    agency_name = name
    
    # Check if agency exists in contracts (parameterized)
    check_query = "SELECT COUNT(*) as c FROM contracts WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))"
    check_result = await PostgresModelAsync.select_safe(check_query, [agency_name])
    if not check_result or check_result[0]['c'] == 0:
        raise HTTPException(status_code=404, detail="Agency not found")
    
    # Stats (parameterized)
    contracts_query = """
        SELECT COUNT(*) as count, COALESCE(SUM(award_amount), 0) as total
        FROM contracts WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))
    """
    contracts_stats = await PostgresModelAsync.select_safe(contracts_query, [agency_name])
    
    solicitations_query = """
        SELECT COUNT(*) as count FROM solicitations 
        WHERE LOWER(TRIM("Agency")) = LOWER(TRIM($1))
    """
    solicitations_stats = await PostgresModelAsync.select_safe(solicitations_query, [agency_name])
    
    vendors_query = """
        SELECT COUNT(DISTINCT vendor_name) as count FROM contracts 
        WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))
        AND vendor_name IS NOT NULL AND vendor_name != ''
    """
    vendors_stats = await PostgresModelAsync.select_safe(vendors_query, [agency_name])
    
    stats = {
        "contracts": contracts_stats[0]['count'] if contracts_stats else 0,
        "total_value": float(contracts_stats[0]['total']) if contracts_stats and contracts_stats[0]['total'] else 0,
        "solicitations": solicitations_stats[0]['count'] if solicitations_stats else 0,
        "vendors": vendors_stats[0]['count'] if vendors_stats else 0
    }
    
    # Monthly activity - contracts by month (last 24 months)
    monthly_activity_query = """
        SELECT 
            TO_CHAR(TO_DATE(start_date, 'MM/DD/YYYY'), 'YYYY-MM') as month,
            COUNT(*) as contract_count,
            COALESCE(SUM(award_amount), 0) as total_value
        FROM contracts 
        WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))
        AND start_date IS NOT NULL AND start_date != ''
        GROUP BY TO_CHAR(TO_DATE(start_date, 'MM/DD/YYYY'), 'YYYY-MM')
        ORDER BY month DESC
        LIMIT 24
    """
    try:
        monthly_activity = await PostgresModelAsync.select_safe(monthly_activity_query, [agency_name])
        monthly_activity = list(reversed(monthly_activity)) if monthly_activity else []
    except:
        monthly_activity = []
    
    # Spending by year
    yearly_spending_query = """
        SELECT 
            EXTRACT(YEAR FROM TO_DATE(start_date, 'MM/DD/YYYY'))::INTEGER as year,
            COALESCE(SUM(award_amount), 0) as total_value,
            COUNT(*) as contract_count
        FROM contracts 
        WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))
        AND start_date IS NOT NULL AND start_date != ''
        GROUP BY EXTRACT(YEAR FROM TO_DATE(start_date, 'MM/DD/YYYY'))
        ORDER BY year DESC
        LIMIT 10
    """
    try:
        yearly_spending = await PostgresModelAsync.select_safe(yearly_spending_query, [agency_name])
        yearly_spending = list(reversed(yearly_spending)) if yearly_spending else []
    except:
        yearly_spending = []
    
    # All contracts for table (client-side pagination)
    contracts_list_query = """
        SELECT 
            ctr_id, contract_id, vendor_name as vendor, award_amount, start_date, end_date, status
        FROM contracts 
        WHERE LOWER(TRIM(agency)) = LOWER(TRIM($1))
        ORDER BY start_date DESC
    """
    contracts = await PostgresModelAsync.select_safe(contracts_list_query, [agency_name])
    
    # All solicitations for table (client-side pagination)
    solicitations_list_query = """
        SELECT "EPIN" as epin, "Procurement Name" as title, "Release Date" as release_date, "Due Date" as due_date, "RFx Status" as status, "Procurement Method" as method
        FROM solicitations 
        WHERE LOWER(TRIM("Agency")) = LOWER(TRIM($1))
        ORDER BY "Release Date" DESC
    """
    solicitations = await PostgresModelAsync.select_safe(solicitations_list_query, [agency_name])
    
    # All vendors for table (client-side pagination).
    # ⚠⚠ NO `LEFT JOIN vendors`, AND THIS IS WHY. Resolving the supplier id here
    # with `ON LOWER(TRIM(c.vendor_name)) = LOWER(TRIM(v."Vendor Name"))` and then
    # grouping by that id LISTED A VENDOR TWICE, because 48 vendor names hold more
    # than one row in `vendors` — PASSPort duplicate-registrations, 42 of them with
    # a distinct FMS vendor code per record (ABSORB SOFTWARE INC is 1871820 /
    # FNR0000088 and 2073456 / FNR0000453, identical in every other field).
    #
    # Measured on prod 2026-08-12, before this fix: 20 duplicated rows across 12
    # agencies — Department for the Aging listed ALLEN AME CHURCH twice at
    # $16,126,468 each, and 2 more besides. The two copies each linked to a
    # DIFFERENT vendor profile for the same company.
    #
    # ⚠ The sharpest symptom was a page disagreeing with itself: `stats.vendors` is
    # COUNT(DISTINCT vendor_name) and was right, while the Vendors tab badge counts
    # these rows and read 1-3 higher on those 12 agencies. Two vendor counts on one
    # page, and no way for a reader to tell which was the measurement.
    #
    # ⚠ NOT a money error: the join multiplies rows evenly, so each duplicate
    # carried the CORRECT contract count and total. Nothing was overstated — one
    # relationship was simply presented as two.
    #
    # Ids now come from modules/vendorids.unique_map, which accepts a name only
    # where it resolves to exactly ONE supplier id. A map cannot duplicate a row,
    # and an ambiguous name stays unlinked rather than sending a reader to an
    # arbitrary one of two companies. The table's JS already renders an unlinked
    # name when `vendor_id` is absent, so no template change is needed.
    vendors_list_query = """
        SELECT
            c.vendor_name as name,
            COUNT(*) as contract_count,
            COALESCE(SUM(c.award_amount), 0) as total_value
        FROM contracts c
        WHERE LOWER(TRIM(c.agency)) = LOWER(TRIM($1))
        AND c.vendor_name IS NOT NULL AND c.vendor_name != ''
        GROUP BY c.vendor_name
        ORDER BY total_value DESC, c.vendor_name ASC
    """
    # ⚠ `c.vendor_name` is a TIEBREAK, and the ties here are large: at DYCD 115
    # vendors share a total of $18,750, 69 share $0 and 66 share $5,000, in a
    # client-paginated 2,010-row table. Ordering on the value alone leaves those
    # groups in whatever order the plan produces, which can show one vendor twice
    # across two page loads and never show another.
    # ⚠ Stated precisely, because I could not reproduce it: two runs returned an
    # IDENTICAL order, so today it is incidentally repeatable, not guaranteed. What
    # is measured is that the order is unspecified by the query and that changing the
    # query reorders tied rows — the Renewal Queue's tied end_date rows did exactly
    # that when this same join was removed there. The tiebreak is free; relying on
    # the planner is not.
    vendor_rows = await PostgresModelAsync.select_safe(vendors_list_query, [agency_name])
    agency_vendor_ids = await vendorids.unique_map(PostgresModelAsync, logger)
    vendors = [{**dict(r), "vendor_id": agency_vendor_ids.get(vendorids.key(r["name"]))}
               for r in (vendor_rows or [])]
    
    # Resolve the org profile this agency maps to (if any) so callers can deep-link
    # / redirect into the unified org profile instead of the standalone page.
    org_id = await _resolve_org_id(agency_name)

    result = {
        "agency": {
            "name": agency_name,
            "org_id": org_id
        },
        "stats": stats,
        "monthly_activity": monthly_activity or [],
        "yearly_spending": yearly_spending or [],
        "contracts": contracts or [],
        "solicitations": solicitations or [],
        "vendors": vendors or []
    }

    # Cache result
    _dr_cache_set(cache_key, result)

    return result


# ============================================================================
# Transactions / Spending Endpoints (DuckDB + S3 Parquet)
# ============================================================================

# Columns returned per transaction row. The first six are the legacy shape the
# existing UI reads; the rest power the explorer's expandable-row detail panel.
# All exist in the S3 Parquet (verified 2026 schema).
_TRANSACTION_COLS = [
    "payee_name", "agency", "check_amount", "issue_date", "spending_category", "contract_id",
    "expense_category", "department", "industry", "budget_code",
    "sub_vendor", "associated_prime_vendor",
]

# Facetable dimensions: which categorical columns the explorer filters/facets on.
_FACET_DIMS = ["agency", "spending_category", "expense_category", "industry"]

# ----------------------------------------------------------------------------
# Optional (v2) columns — M/WBE + document-level. NOT in the legacy 13-col
# Parquet; added by the v2 re-ingest (api/build_spending_parquet.py, which keeps
# every Checkbook response column instead of the old 13-col narrowing). The API
# references these only when a schema probe confirms they're present, so it stays
# error-free before any backfill and lights up automatically once one lands.
# Reads that touch them use union_by_name=true, so years not yet re-ingested
# simply return NULL for the new columns instead of erroring on a mixed schema.
# ----------------------------------------------------------------------------
_MWBE_COLS = ["mwbe_category", "woman_owned_business", "emerging_business"]

_spending_schema_cache: Dict[str, Any] = {"cols": None, "ts": 0.0}
_SPENDING_SCHEMA_TTL = 3600  # re-probe hourly so a backfill is picked up within the hour


def _spending_columns() -> set:
    """Column names present in the spending Parquet (cached ~1h).

    Probes the newest chunk — the re-ingest lands newest-FY-first — so a partial
    backfill is detected as soon as any recent year carries the new columns.
    """
    now = time.time()
    c = _spending_schema_cache
    if c["cols"] is not None and (now - c["ts"]) < _SPENDING_SCHEMA_TTL:
        return c["cols"]
    cols = set(_TRANSACTION_COLS) | {"fiscal_year"}
    try:
        con = _persistent_spending_connection().cursor()
        newest = get_spending_files(2026).strip("[]").split(",")[0].strip()
        rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet({newest})").fetchall()
        cols = {r[0] for r in rows}
        con.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[spending] schema probe failed; assuming base columns: {exc}")
    c["cols"], c["ts"] = cols, now
    return cols


def _mwbe_enabled() -> bool:
    """True once the re-ingest has added M/WBE columns to the Parquet."""
    return "mwbe_category" in _spending_columns()


def _spending_source(files: str) -> str:
    """FROM-source for a spending read. Uses union_by_name=true when M/WBE is
    enabled so a mix of re-ingested (v2) and legacy (13-col) chunks reads cleanly
    (missing columns → NULL). Falls back to a plain read when M/WBE is absent."""
    return f"read_parquet({files}, union_by_name=true)" if _mwbe_enabled() else f"read_parquet({files})"


def _spending_where(filters: dict) -> tuple:
    """Build a parametrized WHERE clause + params list for the spending Parquet.

    Returns (where_sql, params). Text filters (agency/vendor/q) are ILIKE substring;
    categorical facets are exact equality; amount/date are ranges. Parametrized with
    `?` placeholders so no user input is interpolated into SQL.
    """
    clauses: List[str] = []
    params: List[Any] = []
    if filters.get("agency"):
        clauses.append("agency ILIKE ?"); params.append(f"%{filters['agency']}%")
    if filters.get("vendor"):
        clauses.append("payee_name ILIKE ?"); params.append(f"%{filters['vendor']}%")
    if filters.get("q"):
        like = f"%{filters['q']}%"
        clauses.append(
            "(payee_name ILIKE ? OR agency ILIKE ? OR spending_category ILIKE ? "
            "OR expense_category ILIKE ?)"
        )
        params += [like, like, like, like]
    if filters.get("expense_category"):
        clauses.append("expense_category = ?"); params.append(filters["expense_category"])
    if filters.get("spending_category"):
        clauses.append("spending_category = ?"); params.append(filters["spending_category"])
    if filters.get("industry"):
        clauses.append("industry = ?"); params.append(filters["industry"])
    if filters.get("sub_vendor"):
        clauses.append("sub_vendor = ?"); params.append(filters["sub_vendor"])
    # M/WBE filters — only wired in when the v2 columns are present (otherwise the
    # clause would reference a non-existent column and fail the whole query).
    if _mwbe_enabled():
        if filters.get("mwbe_category"):
            clauses.append("mwbe_category = ?"); params.append(filters["mwbe_category"])
        if filters.get("woman_owned") in ("Yes", "No"):
            clauses.append("woman_owned_business = ?"); params.append(filters["woman_owned"])
        if filters.get("emerging") in ("Yes", "No"):
            clauses.append("emerging_business = ?"); params.append(filters["emerging"])
    if filters.get("min_amount") is not None:
        clauses.append("TRY_CAST(check_amount AS DOUBLE) >= ?"); params.append(filters["min_amount"])
    if filters.get("max_amount") is not None:
        clauses.append("TRY_CAST(check_amount AS DOUBLE) <= ?"); params.append(filters["max_amount"])
    if filters.get("date_from"):
        clauses.append("TRY_CAST(issue_date AS DATE) >= ?"); params.append(filters["date_from"])
    if filters.get("date_to"):
        clauses.append("TRY_CAST(issue_date AS DATE) <= ?"); params.append(filters["date_to"])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _query_transactions(filters: dict, sort: str, order: str, limit: int, offset: int) -> dict:
    """Run a synchronous DuckDB query against S3 Parquet spending data.

    Must be called via to_duckdb_thread to avoid blocking the event loop.
    """
    # Reuse the persistent connection (warm S3 metadata cache) via an independent
    # cursor so it's safe to run inside to_duckdb_thread.
    con = _persistent_spending_connection().cursor()
    files = get_spending_files(filters.get("fiscal_year"))
    where_str, params = _spending_where(filters)

    sort_map = {
        "amount": "TRY_CAST(check_amount AS DOUBLE)",
        "date": "TRY_CAST(issue_date AS DATE)",
        "agency": "agency",
        "vendor": "payee_name",
    }
    sql_sort = sort_map.get(sort, "TRY_CAST(check_amount AS DOUBLE)")
    sql_order = "ASC" if order == "asc" else "DESC"

    source = _spending_source(files)

    # Combined count + sum — one scan over the Parquet files instead of two
    # (they share the same WHERE).
    agg_sql = (
        f"SELECT COUNT(*) AS c, "
        f"COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) AS total_amount "
        f"FROM {source} {where_str}"
    )
    agg = con.execute(agg_sql, params).fetchone()
    total = agg[0] if agg else 0
    total_amount = float(agg[1]) if agg else 0.0

    # Data — append M/WBE columns to the row shape once the v2 re-ingest has them.
    cols = list(_TRANSACTION_COLS)
    if _mwbe_enabled():
        cols += [c for c in _MWBE_COLS if c in _spending_columns()]
    data_sql = (
        f"SELECT {', '.join(cols)} "
        f"FROM {source} {where_str} "
        f"ORDER BY {sql_sort} {sql_order} NULLS LAST "
        f"LIMIT {int(limit)} OFFSET {int(offset)}"
    )
    raw = con.execute(data_sql, params).fetchall()
    rows = [{cols[i]: (str(v) if v is not None else None) for i, v in enumerate(row)} for row in raw]

    # Cursor is disposable; the underlying persistent connection stays open.
    con.close()

    return {
        "data": rows,
        "total": total,
        "total_amount": total_amount,
        "page": (offset // limit) + 1,
        "pages": math.ceil(total / limit) if total > 0 else 0,
    }


@router.get("/transactions")
async def list_transactions(
    page: int = 1,
    limit: int = 50,
    fiscal_year: Optional[int] = None,
    agency: Optional[str] = None,
    vendor: Optional[str] = None,
    q: Optional[str] = None,
    expense_category: Optional[str] = None,
    spending_category: Optional[str] = None,
    industry: Optional[str] = None,
    sub_vendor: Optional[str] = None,
    mwbe_category: Optional[str] = None,
    woman_owned: Optional[str] = None,
    emerging: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort: str = "amount",
    order: str = "desc",
):
    """Query Checkbook NYC spending data from S3 Parquet via DuckDB."""
    if limit > 100:
        limit = 100
    offset = (max(page, 1) - 1) * limit
    fy = fiscal_year  # None = all recent years (2022-2026)
    filters = {
        "fiscal_year": fy, "agency": agency, "vendor": vendor, "q": q,
        "expense_category": expense_category, "spending_category": spending_category,
        "industry": industry, "sub_vendor": sub_vendor,
        "mwbe_category": mwbe_category, "woman_owned": woman_owned, "emerging": emerging,
        "min_amount": min_amount, "max_amount": max_amount,
        "date_from": date_from, "date_to": date_to,
    }

    # Serve from cache when fresh — the S3 Parquet scan is expensive and the data
    # only changes daily.
    cache_key = "|".join(str(filters[k]) for k in sorted(filters)) + f"|{sort}|{order}|{limit}|{offset}"
    cached = _transactions_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < TRANSACTIONS_CACHE_TTL:
        return cached["data"]

    try:
        result = await to_duckdb_thread(
            _query_transactions, filters, sort, order, limit, offset
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Spending query failed: {exc}")

    # Available fiscal years for the filter dropdown
    result["fiscal_years"] = list(range(2026, 2009, -1))
    result["fiscal_year"] = fy
    # Tell the UI whether the M/WBE facet/columns are live yet (v2 re-ingest).
    result["mwbe_available"] = _mwbe_enabled()

    # Resolve vendor profile ids (PASSPort Supplier-ID) for the page's payees so the
    # UI can deep-link to vendor profiles. Checkbook payee names exact-match PASSPort
    # vendor names where possible; unmatched payees get vendor_id=None (no link).
    rows = result.get("data") or []
    payees = sorted({(r.get("payee_name") or "").strip() for r in rows if r.get("payee_name")})
    if payees:
        placeholders = ",".join(f"${i+1}" for i in range(len(payees)))
        try:
            vrows = await PostgresModelAsync.select_safe(
                f'SELECT "Vendor Name" AS name, "PASSPort Supplier-ID" AS vid '
                f'FROM vendors WHERE "Vendor Name" IN ({placeholders})',
                payees,
            )
            vmap = {r["name"]: r["vid"] for r in (vrows or []) if r.get("vid")}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[transactions] vendor id resolution failed: {exc}")
            vmap = {}
        for r in rows:
            r["vendor_id"] = vmap.get((r.get("payee_name") or "").strip())

    # Resolve PASSPort contract identity for the page's Checkbook contract_ids so
    # the UI can deep-link to contract profiles. Checkbook ids are un-dashed
    # (e.g. "CT107120268802839"); PASSPort stores a dashed contract_id
    # ("CT1-071-...") plus a normalized_contract_id (dashes stripped). We match on
    # the normalized form (normalized_contract_id is 1:1 with contract_id). Most
    # rows are non-contract document types (DO/PO/PON purchase & delivery orders)
    # that aren't registered PASSPort contracts — those get ctr_id=None (no link).
    def _norm_cid(v: Optional[str]) -> Optional[str]:
        return re.sub(r"[^A-Z0-9]", "", (v or "").upper()) or None

    normed_cids = sorted({
        n for r in rows
        if (n := _norm_cid(r.get("contract_id")))
    })
    if normed_cids:
        placeholders = ",".join(f"${i+1}" for i in range(len(normed_cids)))
        try:
            crows = await PostgresModelAsync.select_safe(
                f"SELECT normalized_contract_id AS n, ctr_id, contract_id "
                f"FROM contracts WHERE normalized_contract_id IN ({placeholders})",
                normed_cids,
            )
            cmap = {r["n"]: r for r in (crows or []) if r.get("n")}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[transactions] contract id resolution failed: {exc}")
            cmap = {}
        for r in rows:
            match = cmap.get(_norm_cid(r.get("contract_id")))
            r["ctr_id"] = match["ctr_id"] if match else None
            r["passport_contract_id"] = match["contract_id"] if match else None

    # Cache (with a simple size cap to bound memory)
    if len(_transactions_cache) >= _TRANSACTIONS_CACHE_MAX:
        oldest = min(_transactions_cache, key=lambda k: _transactions_cache[k]["ts"])
        del _transactions_cache[oldest]
    _transactions_cache[cache_key] = {"data": result, "ts": time.time()}
    return result


def _query_spending_charts() -> dict:
    """Build spending-by-year and last-12-months chart data via DuckDB."""
    con = get_spending_connection()

    # Spending by fiscal year (all years)
    all_files = get_spending_files(None)
    by_year_sql = (
        f"SELECT fiscal_year, "
        f"COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) as total "
        f"FROM read_parquet({all_files}, hive_partitioning=true) "
        f"GROUP BY fiscal_year ORDER BY fiscal_year"
    )
    by_year_raw = con.execute(by_year_sql).fetchall()
    by_year = {
        "labels": [str(r[0]) for r in by_year_raw],
        "values": [float(r[1]) for r in by_year_raw],
    }

    # Spending by month (last 12 months from the most recent 2 fiscal years)
    recent_files = get_spending_files(None)  # uses default 5 recent years
    by_month_sql = (
        f"SELECT strftime(TRY_CAST(issue_date AS DATE), '%Y-%m') as month, "
        f"COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) as total "
        f"FROM read_parquet({recent_files}, hive_partitioning=true) "
        f"WHERE issue_date IS NOT NULL "
        f"AND TRY_CAST(issue_date AS DATE) >= CURRENT_DATE - INTERVAL '12 months' "
        f"GROUP BY month ORDER BY month"
    )
    by_month_raw = con.execute(by_month_sql).fetchall()
    by_month = {
        "labels": [r[0] for r in by_month_raw if r[0]],
        "values": [float(r[1]) for r in by_month_raw if r[0]],
    }

    con.close()
    return {"by_year": by_year, "by_month": by_month}


@router.get("/transactions/charts")
async def get_transactions_charts():
    """Get spending chart data: by fiscal year and last 12 months.

    Why: Precomputed to /app/shared/spending_charts.json by the scheduler.
    Falls back to live DuckDB query if the cache file doesn't exist.
    """
    cache_path = "/app/shared/spending_charts.json"
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return json.load(f)

    # Cache miss — compute live and trigger async regeneration
    try:
        result = await to_duckdb_thread(_query_spending_charts)
        # Write cache for next request
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(result, f, separators=(",", ":"))
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chart query failed: {exc}")


# ----------------------------------------------------------------------------
# Facets — distinct filterable values + counts for the explorer's filter rail.
# ----------------------------------------------------------------------------

# Per-dimension cap on how many facet options to return (spending_category is tiny;
# agency ~150; expense_category ~231; industry can be long — cap it).
_FACET_CAPS = {"agency": 400, "spending_category": 20, "expense_category": 400, "industry": 200, "mwbe_category": 30}


def _query_spending_facets(filters: dict) -> dict:
    """Distinct values + count + total per facet dimension — CONTEXTUAL.

    Each dimension's options are computed against every OTHER active filter but not
    its own (so the agency list narrows when you pick an expense category, yet the
    expense-category dropdown still shows all of its options). One scan per dimension
    (4 total); results are cached per filter-set for 24h at the endpoint.
    """
    con = _persistent_spending_connection().cursor()
    files = get_spending_files(filters.get("fiscal_year"))
    source = _spending_source(files)
    dims = list(_FACET_DIMS)
    if _mwbe_enabled():
        dims.append("mwbe_category")
    out: Dict[str, list] = {}
    for dim in dims:
        # Apply all active filters except this dimension's own selection.
        sub = {k: v for k, v in filters.items() if k != dim}
        where_str, params = _spending_where(sub)
        sql = (
            f"SELECT {dim} AS v, COUNT(*) AS c, "
            f"COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) AS amt "
            f"FROM {source} {where_str} GROUP BY {dim}"
        )
        rows = con.execute(sql, params).fetchall()
        items = [
            {"value": str(v), "count": c, "amount": float(a)}
            for (v, c, a) in rows if v is not None and v != ""
        ]
        items.sort(key=lambda r: r["amount"], reverse=True)
        out[dim] = items[: _FACET_CAPS.get(dim, 200)]
    con.close()
    return out


@router.get("/transactions/facets")
async def get_transactions_facets(
    fiscal_year: Optional[int] = None,
    q: Optional[str] = None,
    vendor: Optional[str] = None,
    agency: Optional[str] = None,
    expense_category: Optional[str] = None,
    spending_category: Optional[str] = None,
    industry: Optional[str] = None,
    sub_vendor: Optional[str] = None,
    mwbe_category: Optional[str] = None,
    woman_owned: Optional[str] = None,
    emerging: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Filter-rail options: distinct agencies / spending & expense categories /
    industries (+ M/WBE category once re-ingested) with counts and totals,
    contextual to the other active filters."""
    filters = {
        "fiscal_year": fiscal_year, "q": q, "vendor": vendor,
        "agency": agency, "expense_category": expense_category,
        "spending_category": spending_category, "industry": industry,
        "sub_vendor": sub_vendor,
        "mwbe_category": mwbe_category, "woman_owned": woman_owned, "emerging": emerging,
        "min_amount": min_amount, "max_amount": max_amount,
        "date_from": date_from, "date_to": date_to,
    }
    cache_key = "|".join(str(filters[k]) for k in sorted(filters))
    cached = _spending_facets_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < SPENDING_AGG_CACHE_TTL:
        return cached["data"]
    try:
        result = await to_duckdb_thread(_query_spending_facets, filters)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Facet query failed: {exc}")
    if len(_spending_facets_cache) >= 200:
        oldest = min(_spending_facets_cache, key=lambda k: _spending_facets_cache[k]["ts"])
        del _spending_facets_cache[oldest]
    _spending_facets_cache[cache_key] = {"data": result, "ts": time.time()}
    return result


# ----------------------------------------------------------------------------
# Top-N widgets — Checkbook-style "Top agencies / payees / categories / contracts"
# for the spending dashboard, in one Parquet scan.
# ----------------------------------------------------------------------------

def _query_spending_top(fiscal_year: Optional[int], limit: int) -> dict:
    """Top-N by total spend across four dimensions, one GROUPING SETS scan."""
    con = _persistent_spending_connection().cursor()
    files = get_spending_files(fiscal_year)
    dims = ["agency", "payee_name", "expense_category", "contract_id"]
    sets = ",".join(f"({d})" for d in dims)
    sql = (
        f"SELECT {', '.join(dims)}, COUNT(*) AS c, "
        f"COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) AS amt "
        f"FROM read_parquet({files}) "
        f"GROUP BY GROUPING SETS ({sets})"
    )
    raw = con.execute(sql).fetchall()
    con.close()

    buckets: Dict[str, list] = {d: [] for d in dims}
    for row in raw:
        vals = row[: len(dims)]
        count, amt = row[-2], float(row[-1])
        for i, d in enumerate(dims):
            v = vals[i]
            if v is not None and v != "" and v != "N/A":
                buckets[d].append({"value": str(v), "count": count, "amount": amt})
                break
    for d in dims:
        buckets[d].sort(key=lambda r: r["amount"], reverse=True)
        buckets[d] = buckets[d][:limit]
    return {
        "agencies": buckets["agency"],
        "payees": buckets["payee_name"],
        "expense_categories": buckets["expense_category"],
        "contracts": buckets["contract_id"],
    }


@router.get("/spending/top")
async def get_spending_top(fiscal_year: Optional[int] = None, limit: int = 5):
    """Dashboard 'Top N' lists: agencies, payees, expense categories, contracts."""
    limit = max(1, min(limit, 25))
    cache_key = f"{fiscal_year}|{limit}"
    cached = _spending_top_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < SPENDING_AGG_CACHE_TTL:
        return cached["data"]
    try:
        result = await to_duckdb_thread(_query_spending_top, fiscal_year, limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Top-N query failed: {exc}")

    # Resolve profile ids so the dashboard can deep-link the ranked lists:
    # payee_name → vendor_id (PASSPort Supplier-ID), contract_id → ctr_id. Same
    # matching as list_transactions. Failures are non-fatal — the UI falls back to
    # an explorer-filtered link when an id is absent.
    payees = result.get("payees") or []
    names = sorted({(p.get("value") or "").strip() for p in payees if p.get("value")})
    if names:
        placeholders = ",".join(f"${i+1}" for i in range(len(names)))
        try:
            vrows = await PostgresModelAsync.select_safe(
                f'SELECT "Vendor Name" AS name, "PASSPort Supplier-ID" AS vid '
                f'FROM vendors WHERE "Vendor Name" IN ({placeholders})', names,
            )
            vmap = {r["name"]: r["vid"] for r in (vrows or []) if r.get("vid")}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[spending/top] vendor id resolution failed: {exc}")
            vmap = {}
        for p in payees:
            p["vendor_id"] = vmap.get((p.get("value") or "").strip())

    def _norm_cid(v: Optional[str]) -> Optional[str]:
        return re.sub(r"[^A-Z0-9]", "", (v or "").upper()) or None

    contracts = result.get("contracts") or []
    normed = sorted({n for c in contracts if (n := _norm_cid(c.get("value")))})
    if normed:
        placeholders = ",".join(f"${i+1}" for i in range(len(normed)))
        try:
            crows = await PostgresModelAsync.select_safe(
                f"SELECT normalized_contract_id AS n, ctr_id, contract_id "
                f"FROM contracts WHERE normalized_contract_id IN ({placeholders})", normed,
            )
            cmap = {r["n"]: r for r in (crows or []) if r.get("n")}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[spending/top] contract id resolution failed: {exc}")
            cmap = {}
        for c in contracts:
            m = cmap.get(_norm_cid(c.get("value")))
            c["ctr_id"] = m["ctr_id"] if m else None
            c["passport_contract_id"] = m["contract_id"] if m else None

    _spending_top_cache[cache_key] = {"data": result, "ts": time.time()}
    return result


# ----------------------------------------------------------------------------
# Sub-vendor lens — payments the City made to sub-vendors (sub_vendor='Yes'),
# with their prime, plus the primes routing the most sub-vendor spend.
# ----------------------------------------------------------------------------

def _query_subvendors(fiscal_year: Optional[int], limit: int, agency: Optional[str] = None) -> dict:
    con = _persistent_spending_connection().cursor()
    files = get_spending_files(fiscal_year)
    # Optional agency scope — case-insensitive ILIKE, matching how /transactions
    # scopes by agency (Checkbook's proper-case names vs MOCS uppercase).
    ag = " AND agency ILIKE ?" if agency else ""
    p = [f"%{agency}%"] if agency else []
    total = con.execute(
        f"SELECT COUNT(*) AS n, COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) AS amt, "
        f"COUNT(DISTINCT payee_name) AS subs, COUNT(DISTINCT associated_prime_vendor) AS primes "
        f"FROM read_parquet({files}) WHERE sub_vendor = 'Yes'{ag}", p
    ).fetchone()
    top_subs = con.execute(
        f"SELECT payee_name, ANY_VALUE(associated_prime_vendor) AS prime, "
        f"COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) AS amt, COUNT(*) AS n "
        f"FROM read_parquet({files}) WHERE sub_vendor = 'Yes'{ag} "
        f"GROUP BY payee_name ORDER BY amt DESC LIMIT {int(limit)}", p
    ).fetchall()
    top_primes = con.execute(
        f"SELECT associated_prime_vendor, COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) AS amt, COUNT(*) AS n "
        f"FROM read_parquet({files}) WHERE sub_vendor = 'Yes'{ag} "
        f"AND associated_prime_vendor IS NOT NULL AND associated_prime_vendor NOT IN ('', 'N/A') "
        f"GROUP BY associated_prime_vendor ORDER BY amt DESC LIMIT {int(limit)}", p
    ).fetchall()
    con.close()
    return {
        "total_amount": float(total[1]) if total else 0.0,
        "payment_count": int(total[0]) if total else 0,
        "subvendor_count": int(total[2]) if total else 0,
        "prime_count": int(total[3]) if total else 0,
        "top_subvendors": [
            {"payee": r[0], "prime": (r[1] if r[1] and r[1] != "N/A" else None),
             "amount": float(r[2]), "payments": int(r[3])} for r in top_subs
        ],
        "top_primes": [
            {"prime": r[0], "amount": float(r[1]), "payments": int(r[2])} for r in top_primes
        ],
    }


@router.get("/spending/subvendors")
async def get_subvendors(fiscal_year: Optional[int] = None, limit: int = 8, agency: Optional[str] = None):
    """Sub-vendor lens: total sub-vendor spend + top sub-vendors + top primes.
    Pass `agency` to scope to a single agency (used by the agency profile)."""
    limit = max(1, min(limit, 25))
    cache_key = f"{fiscal_year}|{limit}|{agency or ''}"
    cached = _subvendor_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < SPENDING_AGG_CACHE_TTL:
        return cached["data"]
    try:
        result = await to_duckdb_thread(_query_subvendors, fiscal_year, limit, agency)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sub-vendor query failed: {exc}")

    # Resolve vendor profile ids for the sub-vendor payees + primes so the UI can
    # deep-link them (same matching as list_transactions). Best-effort: unmatched
    # names carry no id and render as plain text.
    subs = result.get("top_subvendors") or []
    primes = result.get("top_primes") or []
    names = sorted({
        (x.get(k) or "").strip()
        for lst, k in ((subs, "payee"), (subs, "prime"), (primes, "prime"))
        for x in lst if (x.get(k) or "").strip()
    })
    if names:
        placeholders = ",".join(f"${i+1}" for i in range(len(names)))
        try:
            vrows = await PostgresModelAsync.select_safe(
                f'SELECT "Vendor Name" AS name, "PASSPort Supplier-ID" AS vid '
                f'FROM vendors WHERE "Vendor Name" IN ({placeholders})', names,
            )
            vmap = {r["name"]: r["vid"] for r in (vrows or []) if r.get("vid")}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[subvendors] vendor id resolution failed: {exc}")
            vmap = {}
        for s in subs:
            s["vendor_id"] = vmap.get((s.get("payee") or "").strip())
            s["prime_id"] = vmap.get((s.get("prime") or "").strip())
        for p in primes:
            p["vendor_id"] = vmap.get((p.get("prime") or "").strip())

    _subvendor_cache[cache_key] = {"data": result, "ts": time.time()}
    return result


# ----------------------------------------------------------------------------
# M/WBE lens — Checkbook classifies every payment by minority/women-owned business
# category, plus woman-owned and emerging (EBE) flags. Dashboard cut: spend split
# by M/WBE category + woman-owned / emerging totals. Requires the v2 re-ingest
# (see build_spending_parquet.py); dormant + `available:false` until then.
# ----------------------------------------------------------------------------

# Categories Checkbook uses for spend NOT attributable to a certified M/WBE. Used
# to derive a "certified M/WBE" rollup vs. the rest.
_MWBE_NONCERTIFIED = {"Non-M/WBE", "Individuals and Others", "", "N/A"}


def _query_mwbe(fiscal_year: Optional[int], limit: int, agency: Optional[str] = None) -> dict:
    con = _persistent_spending_connection().cursor()
    files = get_spending_files(fiscal_year)
    src = _spending_source(files)
    # Optional agency scope (case-insensitive ILIKE, as in /transactions).
    ag = " AND agency ILIKE ?" if agency else ""
    p = [f"%{agency}%"] if agency else []
    by_cat = con.execute(
        f"SELECT mwbe_category AS v, COUNT(*) AS n, "
        f"COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) AS amt "
        f"FROM {src} WHERE mwbe_category IS NOT NULL AND mwbe_category <> ''{ag} "
        f"GROUP BY mwbe_category ORDER BY amt DESC LIMIT {int(limit)}", p
    ).fetchall()
    wo = con.execute(
        f"SELECT COUNT(*), COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) "
        f"FROM {src} WHERE woman_owned_business = 'Yes'{ag}", p
    ).fetchone()
    eb = con.execute(
        f"SELECT COUNT(*), COALESCE(SUM(TRY_CAST(check_amount AS DOUBLE)), 0) "
        f"FROM {src} WHERE emerging_business = 'Yes'{ag}", p
    ).fetchone()
    con.close()

    cats = [
        {"category": str(v), "payment_count": int(n), "total_amount": float(a)}
        for (v, n, a) in by_cat
    ]
    certified = sum(
        c["total_amount"] for c in cats if c["category"] not in _MWBE_NONCERTIFIED
    )
    certified_n = sum(
        c["payment_count"] for c in cats if c["category"] not in _MWBE_NONCERTIFIED
    )
    return {
        "available": True,
        "by_category": cats,
        "certified_mwbe": {"payment_count": certified_n, "total_amount": certified},
        "woman_owned": {"payment_count": int(wo[0]), "total_amount": float(wo[1])},
        "emerging": {"payment_count": int(eb[0]), "total_amount": float(eb[1])},
    }


_capital_year_cache = {'data': None, 'ts': 0}


@router.get("/spending/capital-by-year")
async def get_capital_spending_by_year(years: int = 10):
    """Actual capital spending — Checkbook 'Capital Contracts' payments — by fiscal
    year, the last N COMPLETE fiscal years (the current FY is partial, so it's
    dropped to avoid a misleading dip). Distinct from CPDB budget/commitment data:
    this is cash the City actually paid out on capital work. Cached 24h."""
    years = max(1, min(years, 17))
    now = time.time()
    c = _capital_year_cache
    if c['data'] is not None and (now - c['ts']) < SPENDING_AGG_CACHE_TTL:
        return c['data']

    def _q():
        con = _persistent_spending_connection().cursor()
        files = get_spending_files(all_years=True)
        rows = con.execute(
            f"SELECT TRY_CAST(fiscal_year AS INT) AS fy, "
            f"SUM(TRY_CAST(check_amount AS DOUBLE)) AS amt "
            f"FROM read_parquet({files}) "
            f"WHERE spending_category = 'Capital Contracts' AND fiscal_year IS NOT NULL "
            f"GROUP BY 1 ORDER BY 1"
        ).fetchall()
        con.close()
        return rows

    rows = await to_duckdb_thread(_q)
    series = [(int(fy), float(a or 0)) for fy, a in rows if fy is not None]
    if series:
        cur = max(fy for fy, _ in series)  # current FY is partial — exclude it
        series = [(fy, a) for fy, a in series if fy < cur][-years:]
    result = {"labels": [f"FY{fy}" for fy, _ in series],
              "values": [a for _, a in series], "category": "Capital Contracts"}
    c['data'] = result
    c['ts'] = now
    return result


@router.get("/spending/mwbe")
async def get_spending_mwbe(fiscal_year: Optional[int] = None, limit: int = 15, agency: Optional[str] = None):
    """M/WBE lens: spend by minority/women-owned business category + woman-owned /
    emerging totals. Pass `agency` to scope to a single agency (agency profile).
    Returns `available:false` (empty) until the v2 re-ingest lands the M/WBE
    columns, so callers hide the section gracefully."""
    if not _mwbe_enabled():
        return {
            "available": False, "by_category": [],
            "certified_mwbe": {"payment_count": 0, "total_amount": 0.0},
            "woman_owned": {"payment_count": 0, "total_amount": 0.0},
            "emerging": {"payment_count": 0, "total_amount": 0.0},
        }
    limit = max(1, min(limit, 40))
    cache_key = f"{fiscal_year}|{limit}|{agency or ''}"
    cached = _mwbe_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < SPENDING_AGG_CACHE_TTL:
        return cached["data"]
    try:
        result = await to_duckdb_thread(_query_mwbe, fiscal_year, limit, agency)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"M/WBE query failed: {exc}")
    _mwbe_cache[cache_key] = {"data": result, "ts": time.time()}
    return result


# ----------------------------------------------------------------------------
# CSV export — the current filter set, capped, streamed as a download.
# ----------------------------------------------------------------------------

_EXPORT_ROW_CAP = 50000  # bound memory / response size; UI warns when truncated


def _query_transactions_export(filters: dict, sort: str, order: str) -> tuple:
    """Fetch up to _EXPORT_ROW_CAP filtered rows and render CSV. Returns (csv, n)."""
    con = _persistent_spending_connection().cursor()
    files = get_spending_files(filters.get("fiscal_year"))
    where_str, params = _spending_where(filters)
    sort_map = {
        "amount": "TRY_CAST(check_amount AS DOUBLE)", "date": "TRY_CAST(issue_date AS DATE)",
        "agency": "agency", "vendor": "payee_name",
    }
    sql_sort = sort_map.get(sort, "TRY_CAST(check_amount AS DOUBLE)")
    sql_order = "ASC" if order == "asc" else "DESC"
    cols = list(_TRANSACTION_COLS)
    if _mwbe_enabled():
        cols += [c for c in _MWBE_COLS if c in _spending_columns()]
    sql = (
        f"SELECT {', '.join(cols)} FROM {_spending_source(files)} {where_str} "
        f"ORDER BY {sql_sort} {sql_order} NULLS LAST LIMIT {_EXPORT_ROW_CAP}"
    )
    raw = con.execute(sql, params).fetchall()
    con.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    for row in raw:
        writer.writerow(["" if v is None else v for v in row])
    return buf.getvalue(), len(raw)


@router.get("/transactions/export")
async def export_transactions(
    fiscal_year: Optional[int] = None,
    agency: Optional[str] = None,
    vendor: Optional[str] = None,
    q: Optional[str] = None,
    expense_category: Optional[str] = None,
    spending_category: Optional[str] = None,
    industry: Optional[str] = None,
    sub_vendor: Optional[str] = None,
    mwbe_category: Optional[str] = None,
    woman_owned: Optional[str] = None,
    emerging: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort: str = "amount",
    order: str = "desc",
):
    """Download the current filtered transaction set as CSV (capped at 50k rows)."""
    filters = {
        "fiscal_year": fiscal_year, "agency": agency, "vendor": vendor, "q": q,
        "expense_category": expense_category, "spending_category": spending_category,
        "industry": industry, "sub_vendor": sub_vendor,
        "mwbe_category": mwbe_category, "woman_owned": woman_owned, "emerging": emerging,
        "min_amount": min_amount, "max_amount": max_amount,
        "date_from": date_from, "date_to": date_to,
    }
    try:
        csv_text, n = await to_duckdb_thread(_query_transactions_export, filters, sort, order)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")
    fy_label = fiscal_year or "recent"
    headers = {
        "Content-Disposition": f'attachment; filename="databook-spending-fy{fy_label}.csv"',
        "X-Row-Count": str(n),
        "X-Row-Cap": str(_EXPORT_ROW_CAP),
    }
    return Response(content=csv_text, media_type="text/csv", headers=headers)

