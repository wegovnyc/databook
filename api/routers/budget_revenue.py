"""
Budget & Revenue domains (CheckbookNYC parity) — DuckDB over a single S3 Parquet
per domain (built by build_budget_revenue_parquet.py from the checkbook_budget /
checkbook_revenue extractors).

Schema-tolerant like the M/WBE lens: every endpoint returns `available: false`
with an empty shape until the Parquet has been ingested, so the frontend pages
render a "not yet available" state instead of erroring. Small datasets
(agency/budget-code/revenue-source aggregates), so each is one whole-file read.
"""
from __future__ import annotations

import os
import time
import asyncio
import datetime
from typing import Optional

import duckdb
from fastapi import APIRouter, HTTPException

from modules.duckpool import to_duckdb_thread

router = APIRouter(prefix="/oce", tags=["budget-revenue"])

# Public HTTPS base for the spending bucket (same bucket as spending). Overridable
# for local testing (point at a directory of fixture parquets).
_BASE = os.environ.get("BUDGET_REVENUE_BASE", "https://nyc-databook-spending.s3.amazonaws.com")
_FILES = {"budget": "budget/budget.parquet", "revenue": "revenue/revenue.parquet"}

_YEAR_COL = {"budget": "year", "revenue": "fiscal_year"}

_CACHE: dict = {}
_CACHE_TTL = 86400  # daily-refreshed data
_avail_cache: dict = {"ts": 0.0, "val": {}}


def _file(domain: str) -> str:
    """Parquet location for a domain (single quoted literal for read_parquet)."""
    return f"'{_BASE.rstrip('/')}/{_FILES[domain]}'"


def _con():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    # Bound DuckDB memory to the container budget so a scan spills to disk rather
    # than allocating past the cgroup limit and OOM-killing the container (DuckDB
    # defaults to ~80% of host RAM). Mirrors routers/oce.py.
    con.execute("SET memory_limit='1GB'; SET threads=2;")
    return con


def _available(domain: str) -> bool:
    """Whether the domain's Parquet exists + reads (cached ~5min). Keeps the
    endpoints error-free before ingestion."""
    now = time.time()
    if now - _avail_cache["ts"] < 300 and domain in _avail_cache["val"]:
        return _avail_cache["val"][domain]
    ok = False
    try:
        con = _con()
        con.execute(f"SELECT 1 FROM read_parquet({_file(domain)}) LIMIT 1").fetchone()
        con.close()
        ok = True
    except Exception:
        ok = False
    _avail_cache["val"][domain] = ok
    _avail_cache["ts"] = now
    return ok


async def _cached(key: str, fn):
    """Cache wrapper; a MISS is offloaded to the dedicated DuckDB executor.

    ⚠ This used to call fn() inline, which meant a cold DuckDB scan ran ON THE
    EVENT LOOP and stalled every other request in the process for its duration —
    including asyncpg's socket reads and timers, which is one of the ways the
    2026-07-27 connect TimeoutError bursts were produced. The api restarts daily
    at 04:00 UTC (cron), so the cache is cold every morning and the first visitor
    to each endpoint paid that stall. See modules/duckpool.py.
    """
    hit = _CACHE.get(key)
    if hit and (time.time() - hit["ts"]) < _CACHE_TTL:
        return hit["data"]
    data = await to_duckdb_thread(fn)
    _CACHE[key] = {"data": data, "ts": time.time()}
    return data


def _latest_full_fy(max_year):
    """The fiscal year dashboards default to: the latest fully-CLOSED NYC FY.

    NYC FY ends June 30 (labelled by end-year) and its books take months to
    finalize, so we default to neither the in-progress FY nor the just-ended one
    (whose figures are still settling) — a FY is treated as "full" once its books
    have closed (~October). Clamped to the years actually present in the data.
    e.g. mid-July 2026 -> FY2025 (FY2026 just ended; FY2027 in progress). The
    default advances automatically each autumn. Callers still accept an explicit
    ?fiscal_year= to view any year, including the current partial one."""
    if max_year is None:
        return None
    today = datetime.date.today()
    settled = today.year if today.month >= 10 else today.year - 1
    return min(settled, int(max_year))


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

_BUDGET_EMPTY = {"available": False, "latest_year": None, "totals": {}, "by_year": [], "by_category": []}


def _query_budget_summary() -> dict:
    con = _con()
    src = f"read_parquet({_file('budget')})"
    latest = _latest_full_fy(con.execute(f"SELECT MAX(year) FROM {src}").fetchone()[0])
    totals_row = con.execute(
        f"SELECT COALESCE(SUM(adopted),0), COALESCE(SUM(modified),0), "
        f"COALESCE(SUM(committed),0), COALESCE(SUM(cash_expense),0) "
        f"FROM {src} WHERE year = ?", [latest]
    ).fetchone()
    by_year = con.execute(
        f"SELECT year, COALESCE(SUM(adopted),0), COALESCE(SUM(modified),0), "
        f"COALESCE(SUM(cash_expense),0) FROM {src} GROUP BY year ORDER BY year"
    ).fetchall()
    by_cat = con.execute(
        f"SELECT expense_category, COALESCE(SUM(modified),0) m, COALESCE(SUM(cash_expense),0) sp "
        f"FROM {src} WHERE year = ? AND expense_category IS NOT NULL "
        f"GROUP BY expense_category ORDER BY m DESC LIMIT 15", [latest]
    ).fetchall()
    con.close()
    a, m, c, sp = totals_row
    return {
        "available": True,
        "latest_year": int(latest) if latest else None,
        "totals": {"adopted": float(a), "modified": float(m), "committed": float(c),
                   "spent": float(sp), "utilization": (float(sp) / float(m)) if m else 0.0},
        "by_year": [{"year": int(y), "adopted": float(ad), "modified": float(mo), "spent": float(s)}
                    for (y, ad, mo, s) in by_year],
        "by_category": [{"category": cat, "modified": float(mm), "spent": float(ss),
                         "utilization": (float(ss) / float(mm)) if mm else 0.0}
                        for (cat, mm, ss) in by_cat],
    }


_BUDGET_SORTS = {"modified": "modified", "adopted": "adopted", "spent": "spent",
                 "agency": "agency", "utilization": "util"}


def _query_budget_agencies(fiscal_year: Optional[int], sort: str, order: str,
                           page: int, limit: int) -> dict:
    con = _con()
    src = f"read_parquet({_file('budget')})"
    fy = fiscal_year or _latest_full_fy(con.execute(f"SELECT MAX(year) FROM {src}").fetchone()[0])
    col = _BUDGET_SORTS.get(sort, "modified")
    order_sql = "ASC" if order == "asc" else "DESC"
    base = (
        f"SELECT agency, COALESCE(SUM(adopted),0) AS adopted, COALESCE(SUM(modified),0) AS modified, "
        f'COALESCE(SUM(committed),0) AS "committed", COALESCE(SUM(cash_expense),0) AS spent, '
        f"CASE WHEN SUM(modified) > 0 THEN SUM(cash_expense)/SUM(modified) ELSE 0 END AS util "
        f"FROM {src} WHERE year = ? AND agency IS NOT NULL GROUP BY agency"
    )
    total = con.execute(f"SELECT COUNT(*) FROM ({base}) t", [fy]).fetchone()[0]
    rows = con.execute(
        f"{base} ORDER BY {col} {order_sql} LIMIT ? OFFSET ?",
        [fy, int(limit), (max(page, 1) - 1) * int(limit)]
    ).fetchall()
    con.close()
    import math
    return {
        "available": True, "fiscal_year": int(fy),
        "data": [{"agency": r[0], "adopted": float(r[1]), "modified": float(r[2]),
                  "committed": float(r[3]), "spent": float(r[4]), "utilization": float(r[5])}
                 for r in rows],
        "total": total, "page": page, "pages": math.ceil(total / limit) if limit else 1,
    }


@router.get("/budget/summary")
async def budget_summary():
    if not _available("budget"):
        return _BUDGET_EMPTY
    try:
        return await _cached("budget:summary", _query_budget_summary)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Budget summary failed: {exc}")


@router.get("/budget/agencies")
async def budget_agencies(fiscal_year: Optional[int] = None, sort: str = "modified",
                          order: str = "desc", page: int = 1, limit: int = 50):
    if not _available("budget"):
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"budget:agencies:{fiscal_year}:{sort}:{order}:{page}:{limit}"
    try:
        return await _cached(
            key, lambda: _query_budget_agencies(fiscal_year, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Budget agencies failed: {exc}")


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------

# The Revenue feed is denormalized, but adopted/modified and recognized are
# denormalized DIFFERENTLY:
#   * adopted/modified are BUDGET snapshots REPEATED across every detail row of a
#     revenue line — so we collapse to the revenue-line grain and MAX() picks the
#     (headline) figure. A naive SUM over-counts these ~460x.
#   * recognized is ACTUAL cash and is ADDITIVE at the raw-row grain — each row is
#     a distinct receipt (many byte-identical, e.g. standardized PVB fines: a
#     single amount can recur 30k+ times), so recognized must be SUM()med, not
#     MAX()ed. MAX() kept only the largest single receipt per line, which read
#     ~31% of modified (FY24 $38B); SUM() of the 'Collected Revenue' rows reads
#     ~92% of modified (FY24 $115B), matching NYC's published actuals. We scope to
#     closing_classification_name='Collected Revenue' (actual collections) and
#     exclude Billed/Roll/Unbilled accrual adjustments. SUM is associative, so the
#     per-grain SUM re-aggregates correctly by year/category/agency downstream.
# Validated on FY22-25: adopted/modified match NYC's budget, recognized 90-96% of
# modified. (Fixed 2026-07-15; prior code MAX()ed recognized.)
_REVENUE_GRAIN = "fiscal_year, agency, revenue_category, revenue_source, revenue_class, fund_class, funding_class"
_RECOGNIZED_SUM = ("SUM(CASE WHEN closing_classification_name = 'Collected Revenue' "
                   "THEN recognized ELSE 0 END)")


def _revenue_lines(src: str) -> str:
    return (
        f"SELECT fiscal_year, agency, revenue_category, "
        f"MAX(adopted) AS adopted, MAX(modified) AS modified, "
        f"{_RECOGNIZED_SUM} AS recognized "
        f"FROM {src} GROUP BY {_REVENUE_GRAIN}"
    )


def _query_revenue_summary() -> dict:
    con = _con()
    src = f"read_parquet({_file('revenue')})"
    lines = f"WITH lines AS ({_revenue_lines(src)})"
    latest = _latest_full_fy(con.execute(f"SELECT MAX(fiscal_year) FROM {src}").fetchone()[0])
    totals = con.execute(
        f"{lines} SELECT COALESCE(SUM(adopted),0), COALESCE(SUM(modified),0), COALESCE(SUM(recognized),0) "
        f"FROM lines WHERE fiscal_year = ?", [latest]
    ).fetchone()
    by_year = con.execute(
        f"{lines} SELECT fiscal_year, COALESCE(SUM(adopted),0), COALESCE(SUM(modified),0), "
        f"COALESCE(SUM(recognized),0) FROM lines GROUP BY fiscal_year ORDER BY fiscal_year"
    ).fetchall()
    by_cat = con.execute(
        f"{lines} SELECT revenue_category, COALESCE(SUM(modified),0) m, COALESCE(SUM(recognized),0) rec "
        f"FROM lines WHERE fiscal_year = ? AND revenue_category IS NOT NULL "
        f"GROUP BY revenue_category ORDER BY rec DESC LIMIT 15", [latest]
    ).fetchall()
    con.close()
    a, m, rec = totals
    return {
        "available": True,
        "latest_year": int(latest) if latest else None,
        "totals": {"adopted": float(a), "modified": float(m), "recognized": float(rec),
                   "realization": (float(rec) / float(m)) if m else 0.0},
        "by_year": [{"year": int(y), "adopted": float(ad), "modified": float(mo), "recognized": float(r)}
                    for (y, ad, mo, r) in by_year],
        "by_category": [{"category": cat, "modified": float(mm), "recognized": float(rr),
                         "realization": (float(rr) / float(mm)) if mm else 0.0}
                        for (cat, mm, rr) in by_cat],
    }


_REVENUE_SORTS = {"recognized": "recognized", "modified": "modified",
                  "adopted": "adopted", "agency": "agency"}


def _query_revenue_agencies(fiscal_year: Optional[int], sort: str, order: str,
                            page: int, limit: int) -> dict:
    con = _con()
    src = f"read_parquet({_file('revenue')})"
    fy = fiscal_year or _latest_full_fy(con.execute(f"SELECT MAX(fiscal_year) FROM {src}").fetchone()[0])
    col = _REVENUE_SORTS.get(sort, "recognized")
    order_sql = "ASC" if order == "asc" else "DESC"
    # Aggregate over the deduped revenue lines (see _revenue_lines) so adopted/
    # modified aren't multiplied by their detail-row repetition.
    base = (
        f"WITH lines AS ({_revenue_lines(src)}) "
        f"SELECT agency, COALESCE(SUM(adopted),0) adopted, COALESCE(SUM(modified),0) modified, "
        f"COALESCE(SUM(recognized),0) recognized "
        f"FROM lines WHERE fiscal_year = ? AND agency IS NOT NULL GROUP BY agency"
    )
    total = con.execute(f"SELECT COUNT(*) FROM ({base}) t", [fy]).fetchone()[0]
    rows = con.execute(
        f"{base} ORDER BY {col} {order_sql} LIMIT ? OFFSET ?",
        [fy, int(limit), (max(page, 1) - 1) * int(limit)]
    ).fetchall()
    con.close()
    import math
    return {
        "available": True, "fiscal_year": int(fy),
        "data": [{"agency": r[0], "adopted": float(r[1]), "modified": float(r[2]),
                  "recognized": float(r[3]),
                  "realization": (float(r[3]) / float(r[2])) if r[2] else 0.0} for r in rows],
        "total": total, "page": page, "pages": math.ceil(total / limit) if limit else 1,
    }


@router.get("/revenue/summary")
async def revenue_summary():
    if not _available("revenue"):
        return {"available": False, "latest_year": None, "totals": {}, "by_year": [], "by_category": []}
    try:
        return await _cached("revenue:summary", _query_revenue_summary)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Revenue summary failed: {exc}")


@router.get("/revenue/agencies")
async def revenue_agencies(fiscal_year: Optional[int] = None, sort: str = "recognized",
                           order: str = "desc", page: int = 1, limit: int = 50):
    if not _available("revenue"):
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"revenue:agencies:{fiscal_year}:{sort}:{order}:{page}:{limit}"
    try:
        return await _cached(
            key, lambda: _query_revenue_agencies(fiscal_year, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Revenue agencies failed: {exc}")
