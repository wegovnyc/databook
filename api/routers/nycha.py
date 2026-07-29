"""
NYCHA (NYC Housing Authority) Budget & Revenue domains — CheckbookNYC `_NYCHA`
feeds. DuckDB over a single Parquet per domain (built by
build_budget_revenue_parquet.py from checkbook_{budget,revenue}_nycha.py).

Mirrors routers/budget_revenue.py (schema-tolerant, `available:false` until the
Parquet is ingested, cached daily, DuckDB memory bounded), but NYCHA has NO
`agency` dimension — its org axes are `responsibility_center` (developments +
functional units), `funding_source` (federal Section 8 vs City vs capital),
`expense_category`/`revenue_category`, and `budget_type`. So the breakdowns group
on those instead.
"""
from __future__ import annotations

import os
import io
import csv
import time
import math
import logging
import datetime
from typing import Optional

import duckdb
from fastapi import APIRouter, HTTPException, Response

from modules.duckpool import to_duckdb_thread

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oce/nycha", tags=["nycha"])

_BASE = os.environ.get("BUDGET_REVENUE_BASE", "https://nyc-databook-spending.s3.amazonaws.com")
_FILES = {
    "nycha_budget": "nycha_budget/nycha_budget.parquet",
    "nycha_revenue": "nycha_revenue/nycha_revenue.parquet",
    "nycha_contracts": "nycha_contracts/nycha_contracts.parquet",
}

_CACHE: dict = {}
_CACHE_TTL = 86400  # daily-refreshed data
_avail_cache: dict = {"ts": 0.0, "val": {}}


def _file(domain: str) -> str:
    return f"'{_BASE.rstrip('/')}/{_FILES[domain]}'"


def _crosswalk_clause(alias: str):
    """(join_sql, select_sql) to LEFT JOIN the NYCHA→PASSPort vendor crosswalk and
    expose vendor_id — only when the crosswalk parquet exists (guards fresh envs /
    S3 base). `alias`.vendor is matched to the raw crosswalk key. Built by
    build_nycha_vendor_crosswalk.py."""
    path = f"{_BASE.rstrip('/')}/nycha_vendor_crosswalk.parquet"
    if _BASE.lower().startswith("http") or not os.path.exists(path):
        return "", ""
    return (f"LEFT JOIN read_parquet('{path}') xw ON {alias}.vendor = xw.nycha_vendor_name",
            ", xw.passport_supplier_id AS vendor_id")


def _con():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    # Bound memory to the container budget (DuckDB otherwise grabs ~80% of HOST
    # RAM, ignoring the cgroup). Mirrors routers/budget_revenue.py.
    con.execute("SET memory_limit='1GB'; SET threads=2;")
    return con


def _available(domain: str) -> bool:
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


def _cached(key: str, fn):
    hit = _CACHE.get(key)
    if hit and (time.time() - hit["ts"]) < _CACHE_TTL:
        return hit["data"]
    data = fn()
    _CACHE[key] = {"data": data, "ts": time.time()}
    return data


def _latest_full_fy(max_year):
    """Default fiscal year: the latest fully-CLOSED NYC FY (books close ~October;
    labelled by June-30 end-year). Not the in-progress FY nor the just-ended one
    whose figures are still settling; clamped to the years present. Mirrors
    routers/budget_revenue.py so NYCHA defaults consistently with the City pages.
    Callers still honor ?fiscal_year= to view any year."""
    if max_year is None:
        return None
    today = datetime.date.today()
    settled = today.year if today.month >= 10 else today.year - 1
    return min(settled, int(max_year))


# ---------------------------------------------------------------------------
# NYCHA Budget  (spent = actual_amount; utilization = actual/modified)
# ---------------------------------------------------------------------------

_BUDGET_EMPTY = {"available": False, "latest_year": None, "totals": {},
                 "by_year": [], "by_category": [], "by_funding_source": []}


def _query_budget_summary() -> dict:
    con = _con()
    src = f"read_parquet({_file('nycha_budget')})"
    latest = _latest_full_fy(con.execute(f"SELECT MAX(year) FROM {src}").fetchone()[0])
    # NYCHA's Checkbook budget feed publishes the appropriated budget
    # (adopted/modified) only for prior years; for current years it carries
    # committed + actual spending instead. So the page is committed/spending-
    # forward: the operative "budget basis" is modified when published, else
    # committed, and utilization is measured against that.
    a, m, cm, sp = con.execute(
        f"SELECT COALESCE(SUM(adopted),0), COALESCE(SUM(modified),0), "
        f"COALESCE(SUM(committed),0), COALESCE(SUM(actual_amount),0) "
        f"FROM {src} WHERE year = ?", [latest]
    ).fetchone()
    by_year = con.execute(
        f"SELECT year, COALESCE(SUM(modified),0), COALESCE(SUM(committed),0), "
        f"COALESCE(SUM(actual_amount),0) FROM {src} GROUP BY year ORDER BY year"
    ).fetchall()
    # rank on the budget basis (modified-or-committed) so recent years aren't blank
    basis = "CASE WHEN SUM(modified) > 0 THEN SUM(modified) ELSE SUM(committed) END"
    by_cat = con.execute(
        f"SELECT expense_category, {basis} AS b, COALESCE(SUM(actual_amount),0) sp "
        f"FROM {src} WHERE year = ? AND expense_category IS NOT NULL "
        f"GROUP BY expense_category ORDER BY b DESC LIMIT 15", [latest]
    ).fetchall()
    by_fund = con.execute(
        f"SELECT funding_source, {basis} AS b, COALESCE(SUM(actual_amount),0) sp "
        f"FROM {src} WHERE year = ? AND funding_source IS NOT NULL "
        f"GROUP BY funding_source ORDER BY b DESC LIMIT 15", [latest]
    ).fetchall()
    con.close()
    basis_total = float(m) if m else float(cm)
    return {
        "available": True,
        "latest_year": int(latest) if latest else None,
        "budget_basis": "modified" if m else "committed",
        "totals": {"adopted": float(a), "modified": float(m), "committed": float(cm),
                   "spent": float(sp), "basis": basis_total,
                   "utilization": (float(sp) / basis_total) if basis_total else 0.0},
        "by_year": [{"year": int(y), "modified": float(mo), "committed": float(co), "spent": float(s)}
                    for (y, mo, co, s) in by_year],
        "by_category": [{"category": c, "basis": float(bb), "spent": float(ss),
                         "utilization": (float(ss) / float(bb)) if bb else 0.0}
                        for (c, bb, ss) in by_cat],
        "by_funding_source": [{"funding_source": fs, "basis": float(bb), "spent": float(ss),
                               "utilization": (float(ss) / float(bb)) if bb else 0.0}
                              for (fs, bb, ss) in by_fund],
    }


_BUDGET_UNIT_SORTS = {"basis": "basis", "committed": "committed", "spent": "spent",
                      "unit": "unit", "utilization": "util"}
# budget basis = appropriated (modified) when published, else committed (see summary)
_BASIS = "CASE WHEN SUM(modified) > 0 THEN SUM(modified) ELSE SUM(committed) END"


def _query_budget_units(fiscal_year: Optional[int], sort: str, order: str,
                        page: int, limit: int) -> dict:
    """Budget by responsibility_center (NYCHA developments + functional units)."""
    con = _con()
    src = f"read_parquet({_file('nycha_budget')})"
    fy = fiscal_year or _latest_full_fy(con.execute(f"SELECT MAX(year) FROM {src}").fetchone()[0])
    col = _BUDGET_UNIT_SORTS.get(sort, "basis")
    order_sql = "ASC" if order == "asc" else "DESC"
    base = (
        f"SELECT responsibility_center AS unit, {_BASIS} AS basis, "
        f"COALESCE(SUM(committed),0) AS committed, COALESCE(SUM(actual_amount),0) AS spent, "
        f"CASE WHEN {_BASIS} > 0 THEN SUM(actual_amount)/({_BASIS}) ELSE 0 END AS util "
        f"FROM {src} WHERE year = ? AND responsibility_center IS NOT NULL GROUP BY responsibility_center"
    )
    total = con.execute(f"SELECT COUNT(*) FROM ({base}) t", [fy]).fetchone()[0]
    rows = con.execute(
        f"{base} ORDER BY {col} {order_sql} LIMIT ? OFFSET ?",
        [fy, int(limit), (max(page, 1) - 1) * int(limit)]
    ).fetchall()
    con.close()
    return {
        "available": True, "fiscal_year": int(fy),
        "data": [{"unit": r[0], "basis": float(r[1]), "committed": float(r[2]),
                  "spent": float(r[3]), "utilization": float(r[4])} for r in rows],
        "total": total, "page": page, "pages": math.ceil(total / limit) if limit else 1,
    }


@router.get("/budget/summary")
async def nycha_budget_summary():
    if not _available("nycha_budget"):
        return _BUDGET_EMPTY
    try:
        return _cached("nycha:budget:summary", _query_budget_summary)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA budget summary failed: {exc}")


@router.get("/budget/units")
async def nycha_budget_units(fiscal_year: Optional[int] = None, sort: str = "basis",
                             order: str = "desc", page: int = 1, limit: int = 50):
    if not _available("nycha_budget"):
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"nycha:budget:units:{fiscal_year}:{sort}:{order}:{page}:{limit}"
    try:
        return _cached(key, lambda: _query_budget_units(fiscal_year, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA budget units failed: {exc}")


# --- Budget line record explorer --------------------------------------------
# A record = one budget line, collapsed to the natural line grain (safe against
# any repeated snapshot rows; amounts MAX()ed).
_BUDGET_LINE_GRAIN = ("year, budget_type, budget_name, expense_category, funding_source, "
                      "responsibility_center, program, project")
_BUDGET_REC_SORTS = {"modified": "modified", "committed": "committed", "actual": "actual",
                     "adopted": "adopted", "unit": "responsibility_center"}
_BUDGET_REC_COLS = ["year", "responsibility_center", "expense_category", "funding_source",
                    "budget_type", "budget_name", "program", "project",
                    "adopted", "modified", "committed", "actual", "remaining"]


def _budget_lines(src: str) -> str:
    return (
        "SELECT year, responsibility_center, expense_category, funding_source, budget_type, "
        "budget_name, program, project, MAX(adopted) AS adopted, MAX(modified) AS modified, "
        'MAX(committed) AS "committed", MAX(actual_amount) AS actual, MAX(remaining) AS remaining '
        f"FROM {src} GROUP BY {_BUDGET_LINE_GRAIN}"
    )


def _query_budget_records(fiscal_year, q, sort, order, page, limit) -> dict:
    con = _con()
    src = f"read_parquet({_file('nycha_budget')})"
    if fiscal_year:
        src = f"(SELECT * FROM read_parquet({_file('nycha_budget')}) WHERE year = {int(fiscal_year)})"
    where, params = "", []
    if q:
        where = ("WHERE responsibility_center ILIKE ? OR expense_category ILIKE ? "
                 "OR budget_name ILIKE ? OR funding_source ILIKE ?")
        like = f"%{q}%"; params = [like, like, like, like]
    full = f"WITH b AS ({_budget_lines(src)}) SELECT * FROM b {where}"
    total = con.execute(f"SELECT COUNT(*) FROM ({full}) t", params).fetchone()[0]
    col = _BUDGET_REC_SORTS.get(sort, "modified")
    order_sql = "ASC" if order == "asc" else "DESC"
    rows = con.execute(f"{full} ORDER BY {col} {order_sql} NULLS LAST LIMIT ? OFFSET ?",
                       params + [int(limit), (max(page, 1) - 1) * int(limit)]).fetchall()
    cols = [d[0] for d in con.description]
    con.close()
    data = []
    for r in rows:
        d = dict(zip(cols, r))
        for k in ("adopted", "modified", "committed", "actual", "remaining"):
            d[k] = float(d[k]) if d.get(k) is not None else 0.0
        data.append(d)
    return {"available": True, "data": data, "total": total, "page": page,
            "pages": math.ceil(total / limit) if limit else 1}


@router.get("/budget/records")
async def nycha_budget_records(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                               sort: str = "modified", order: str = "desc",
                               page: int = 1, limit: int = 25):
    if not _available("nycha_budget"):
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"nycha:budget:rec:{fiscal_year}:{q}:{sort}:{order}:{page}:{limit}"
    try:
        return _cached(key, lambda: _query_budget_records(fiscal_year, q, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA budget records failed: {exc}")


@router.get("/budget/records/export")
async def nycha_budget_records_export(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                                      sort: str = "modified", order: str = "desc"):
    if not _available("nycha_budget"):
        raise HTTPException(status_code=404, detail="NYCHA budget not available")
    try:
        d = _query_budget_records(fiscal_year, q, sort, order, 1, 50000)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA budget export failed: {exc}")
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(_BUDGET_REC_COLS)
    for row in d.get("data", []):
        w.writerow(["" if row.get(c) is None else row.get(c) for c in _BUDGET_REC_COLS])
    return Response(content=buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="nycha-budget-fy{fiscal_year or "all"}.csv"',
        "X-Row-Count": str(len(d.get("data", []))),
    })


# ---------------------------------------------------------------------------
# NYCHA Revenue  (recognized = collected; realization = recognized/modified)
# ---------------------------------------------------------------------------

# adopted/modified vs recognized are denormalized DIFFERENTLY (mirrors
# routers/budget_revenue.py):
#   * adopted/modified are BUDGET snapshots repeated across a revenue line's detail
#     rows, so we collapse to the revenue-line grain and MAX() picks the headline.
#   * recognized is ACTUAL cash and is ADDITIVE — each row is a distinct receipt
#     (and some grains carry several rows + negative reversal adjustments), so
#     recognized must be SUM()med, not MAX()ed. Unlike the City feed (where MAX
#     read only ~31% of modified because a single amount recurred 30k+ times),
#     NYCHA's feed is already near line-grain so MAX was ~93% of modified — but it
#     still mis-nets multi-row/negative-adjustment grains (e.g. FY2025 MAX $4.81B
#     vs the correct SUM $4.74B). NYCHA's closing_classification_name is a single
#     value 'COLLECTED REVENUE' (uppercase; the City uses 'Collected Revenue'), so
#     we guard case-insensitively to stay correct if accrual rows ever appear.
#     `remaining` is derived as modified - recognized (its own column would pair
#     with the pre-fix MAX). (Fixed 2026-07-17; prior code MAX()ed recognized.)
# ⚠ RE-VALIDATE at ingest: NYCHA revenue is ~$4-5B/yr, Section 8 subsidy ~$1.6B.
_REV_GRAIN = ("budget_fiscal_year, budget_name, budget_type, revenue_expense_category, "
              "funding_source, responsibility_center, revenue_category, revenue_class")
_RECOGNIZED_SUM = ("SUM(CASE WHEN upper(closing_classification_name) = 'COLLECTED REVENUE' "
                   "THEN recognized ELSE 0 END)")


def _revenue_lines(src: str) -> str:
    return (
        f"SELECT budget_fiscal_year AS year, revenue_category, funding_source, "
        f"MAX(adopted) AS adopted, MAX(modified) AS modified, "
        f"{_RECOGNIZED_SUM} AS recognized, "
        f"(MAX(modified) - {_RECOGNIZED_SUM}) AS remaining "
        f"FROM {src} GROUP BY {_REV_GRAIN}"
    )


_REVENUE_EMPTY = {"available": False, "latest_year": None, "totals": {},
                  "by_year": [], "by_category": [], "by_funding_source": []}


def _query_revenue_summary() -> dict:
    con = _con()
    src = f"read_parquet({_file('nycha_revenue')})"
    lines = f"WITH lines AS ({_revenue_lines(src)})"
    latest = _latest_full_fy(con.execute(f"SELECT MAX(budget_fiscal_year) FROM {src}").fetchone()[0])
    a, m, rec, rem = con.execute(
        f"{lines} SELECT COALESCE(SUM(adopted),0), COALESCE(SUM(modified),0), "
        f"COALESCE(SUM(recognized),0), COALESCE(SUM(remaining),0) FROM lines WHERE year = ?", [latest]
    ).fetchone()
    by_year = con.execute(
        f"{lines} SELECT year, COALESCE(SUM(adopted),0), COALESCE(SUM(modified),0), "
        f"COALESCE(SUM(recognized),0) FROM lines GROUP BY year ORDER BY year"
    ).fetchall()
    by_cat = con.execute(
        f"{lines} SELECT revenue_category, COALESCE(SUM(modified),0) m, COALESCE(SUM(recognized),0) rec "
        f"FROM lines WHERE year = ? AND revenue_category IS NOT NULL "
        f"GROUP BY revenue_category ORDER BY rec DESC LIMIT 15", [latest]
    ).fetchall()
    by_fund = con.execute(
        f"{lines} SELECT funding_source, COALESCE(SUM(recognized),0) rec "
        f"FROM lines WHERE year = ? AND funding_source IS NOT NULL "
        f"GROUP BY funding_source ORDER BY rec DESC LIMIT 15", [latest]
    ).fetchall()
    con.close()
    return {
        "available": True,
        "latest_year": int(latest) if latest else None,
        "totals": {"adopted": float(a), "modified": float(m), "recognized": float(rec),
                   "remaining": float(rem),
                   "realization": (float(rec) / float(m)) if m else 0.0},
        "by_year": [{"year": int(y), "adopted": float(ad), "modified": float(mo), "recognized": float(r)}
                    for (y, ad, mo, r) in by_year],
        "by_category": [{"category": c, "modified": float(mm), "recognized": float(rr),
                         "realization": (float(rr) / float(mm)) if mm else 0.0}
                        for (c, mm, rr) in by_cat],
        "by_funding_source": [{"funding_source": fs, "recognized": float(rr)}
                              for (fs, rr) in by_fund],
    }


_REVENUE_SOURCE_SORTS = {"recognized": "recognized", "modified": "modified",
                         "adopted": "adopted", "source": "source"}


def _query_revenue_sources(fiscal_year: Optional[int], sort: str, order: str,
                           page: int, limit: int) -> dict:
    """Revenue by funding_source (federal Section 8 vs City vs capital, etc.)."""
    con = _con()
    src = f"read_parquet({_file('nycha_revenue')})"
    fy = fiscal_year or _latest_full_fy(con.execute(f"SELECT MAX(budget_fiscal_year) FROM {src}").fetchone()[0])
    col = _REVENUE_SOURCE_SORTS.get(sort, "recognized")
    order_sql = "ASC" if order == "asc" else "DESC"
    base = (
        f"WITH lines AS ({_revenue_lines(src)}) "
        f"SELECT funding_source AS source, COALESCE(SUM(adopted),0) adopted, "
        f"COALESCE(SUM(modified),0) modified, COALESCE(SUM(recognized),0) recognized "
        f"FROM lines WHERE year = ? AND funding_source IS NOT NULL GROUP BY funding_source"
    )
    total = con.execute(f"SELECT COUNT(*) FROM ({base}) t", [fy]).fetchone()[0]
    rows = con.execute(
        f"{base} ORDER BY {col} {order_sql} LIMIT ? OFFSET ?",
        [fy, int(limit), (max(page, 1) - 1) * int(limit)]
    ).fetchall()
    con.close()
    return {
        "available": True, "fiscal_year": int(fy),
        "data": [{"source": r[0], "adopted": float(r[1]), "modified": float(r[2]),
                  "recognized": float(r[3]),
                  "realization": (float(r[3]) / float(r[2])) if r[2] else 0.0} for r in rows],
        "total": total, "page": page, "pages": math.ceil(total / limit) if limit else 1,
    }


@router.get("/revenue/summary")
async def nycha_revenue_summary():
    if not _available("nycha_revenue"):
        return _REVENUE_EMPTY
    try:
        return _cached("nycha:revenue:summary", _query_revenue_summary)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA revenue summary failed: {exc}")


@router.get("/revenue/sources")
async def nycha_revenue_sources(fiscal_year: Optional[int] = None, sort: str = "recognized",
                                order: str = "desc", page: int = 1, limit: int = 50):
    if not _available("nycha_revenue"):
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"nycha:revenue:sources:{fiscal_year}:{sort}:{order}:{page}:{limit}"
    try:
        return _cached(key, lambda: _query_revenue_sources(fiscal_year, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA revenue sources failed: {exc}")


# --- Revenue line record explorer -------------------------------------------
# A record = one revenue line (deduped line grain). recognized is SUM()med (actual
# additive cash, see _revenue_lines) while adopted/modified are MAX()ed (repeated
# budget snapshots); remaining is derived modified - recognized. Kept consistent
# with the rollup.
_REV_REC_GRAIN = ("budget_fiscal_year, revenue_category, revenue_class, funding_source, "
                  "budget_name, budget_type, revenue_expense_category, responsibility_center")
_REV_REC_SORTS = {"recognized": "recognized", "modified": "modified", "adopted": "adopted",
                  "category": "revenue_category"}
_REV_REC_COLS = ["year", "revenue_category", "revenue_class", "funding_source", "budget_name",
                 "budget_type", "revenue_expense_category", "responsibility_center",
                 "adopted", "modified", "recognized", "remaining"]


def _revenue_record_lines(src: str) -> str:
    return (
        "SELECT budget_fiscal_year AS year, revenue_category, revenue_class, funding_source, "
        "budget_name, budget_type, revenue_expense_category, responsibility_center, "
        f"MAX(adopted) adopted, MAX(modified) modified, {_RECOGNIZED_SUM} recognized, "
        f"(MAX(modified) - {_RECOGNIZED_SUM}) remaining "
        f"FROM {src} GROUP BY {_REV_REC_GRAIN}"
    )


def _query_revenue_records(fiscal_year, q, sort, order, page, limit) -> dict:
    con = _con()
    src = f"read_parquet({_file('nycha_revenue')})"
    if fiscal_year:
        src = f"(SELECT * FROM read_parquet({_file('nycha_revenue')}) WHERE budget_fiscal_year = {int(fiscal_year)})"
    where, params = "", []
    if q:
        where = ("WHERE revenue_category ILIKE ? OR funding_source ILIKE ? "
                 "OR budget_name ILIKE ? OR revenue_class ILIKE ?")
        like = f"%{q}%"; params = [like, like, like, like]
    full = f"WITH r AS ({_revenue_record_lines(src)}) SELECT * FROM r {where}"
    total = con.execute(f"SELECT COUNT(*) FROM ({full}) t", params).fetchone()[0]
    col = _REV_REC_SORTS.get(sort, "recognized")
    order_sql = "ASC" if order == "asc" else "DESC"
    rows = con.execute(f"{full} ORDER BY {col} {order_sql} NULLS LAST LIMIT ? OFFSET ?",
                       params + [int(limit), (max(page, 1) - 1) * int(limit)]).fetchall()
    cols = [d[0] for d in con.description]
    con.close()
    data = []
    for r in rows:
        d = dict(zip(cols, r))
        for k in ("adopted", "modified", "recognized", "remaining"):
            d[k] = float(d[k]) if d.get(k) is not None else 0.0
        data.append(d)
    return {"available": True, "data": data, "total": total, "page": page,
            "pages": math.ceil(total / limit) if limit else 1}


@router.get("/revenue/records")
async def nycha_revenue_records(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                                sort: str = "recognized", order: str = "desc",
                                page: int = 1, limit: int = 25):
    if not _available("nycha_revenue"):
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"nycha:revenue:rec:{fiscal_year}:{q}:{sort}:{order}:{page}:{limit}"
    try:
        return _cached(key, lambda: _query_revenue_records(fiscal_year, q, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA revenue records failed: {exc}")


@router.get("/revenue/records/export")
async def nycha_revenue_records_export(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                                       sort: str = "recognized", order: str = "desc"):
    if not _available("nycha_revenue"):
        raise HTTPException(status_code=404, detail="NYCHA revenue not available")
    try:
        d = _query_revenue_records(fiscal_year, q, sort, order, 1, 50000)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA revenue export failed: {exc}")
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(_REV_REC_COLS)
    for row in d.get("data", []):
        w.writerow(["" if row.get(c) is None else row.get(c) for c in _REV_REC_COLS])
    return Response(content=buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="nycha-revenue-fy{fiscal_year or "all"}.csv"',
        "X-Row-Count": str(len(d.get("data", []))),
    })


# ---------------------------------------------------------------------------
# NYCHA Contracts  (line/release-grain feed -> aggregated to contract grain)
# ---------------------------------------------------------------------------

def _contracts_grain(src: str) -> str:
    """One row per contract_id. Contract-level fields are constant across the
    feed's line/release rows (and across the per-FY pulls a multi-year contract
    appears in), so MAX() collapses them safely. `current` is aliased current_amt
    (avoids the SQL keyword)."""
    return (
        f"SELECT contract_id, MAX(vendor) vendor, MAX(purpose) purpose, "
        f"MAX(responsibility_center) responsibility_center, MAX(award_method) award_method, "
        f"MAX(contract_type) contract_type, MAX(industry) industry, "
        f"MAX(funding_source) funding_source, MAX(pin) pin, "
        f"MAX(start_date) start_date, MAX(end_date) end_date, "
        f"MAX(number_of_releases) releases, MAX(contract_original_amount) original, "
        f"MAX(contract_current_amount) current_amt, MAX(contract_invoiced_amount) invoiced, "
        f"MAX(TRY_CAST(fiscal_year AS INTEGER)) fiscal_year "
        f"FROM {src} WHERE contract_id IS NOT NULL GROUP BY contract_id"
    )


_CONTRACTS_EMPTY = {"available": False, "totals": {}, "by_year": [], "top_vendors": []}


def _query_contracts_summary() -> dict:
    con = _con()
    src = f"read_parquet({_file('nycha_contracts')})"
    g = f"WITH c AS ({_contracts_grain(src)})"
    n, cur, inv = con.execute(
        f"{g} SELECT count(*), COALESCE(SUM(current_amt),0), COALESCE(SUM(invoiced),0) FROM c"
    ).fetchone()
    by_year = con.execute(
        f"SELECT TRY_CAST(fiscal_year AS INTEGER) y, COUNT(DISTINCT contract_id) "
        f"FROM {src} WHERE contract_id IS NOT NULL GROUP BY y ORDER BY y"
    ).fetchall()
    top_v = con.execute(
        f"{g} SELECT vendor, COUNT(*) n, COALESCE(SUM(current_amt),0) v FROM c "
        f"WHERE vendor IS NOT NULL GROUP BY vendor ORDER BY v DESC LIMIT 15"
    ).fetchall()
    con.close()
    return {
        "available": True,
        "totals": {"contracts": int(n), "current": float(cur), "invoiced": float(inv),
                   "utilization": (float(inv) / float(cur)) if cur else 0.0},
        "by_year": [{"year": int(y), "contracts": int(c)} for (y, c) in by_year if y is not None],
        "top_vendors": [{"vendor": v, "contracts": int(cn), "current": float(cv)}
                        for (v, cn, cv) in top_v],
    }


_CONTRACT_SORTS = {"current": "current_amt", "invoiced": "invoiced", "original": "original",
                   "vendor": "vendor", "end_date": "end_date", "releases": "releases"}


def _query_contracts_list(fiscal_year, q, sort, order, page, limit) -> dict:
    con = _con()
    src = f"read_parquet({_file('nycha_contracts')})"
    # optional FY filter: restrict to contracts appearing in that fiscal year
    fy_src = src
    if fiscal_year:
        fy_src = f"(SELECT * FROM {src} WHERE TRY_CAST(fiscal_year AS INTEGER) = {int(fiscal_year)})"
    outer_where, params = "", []
    if q:
        outer_where = "WHERE vendor ILIKE ? OR purpose ILIKE ? OR contract_id ILIKE ?"
        like = f"%{q}%"; params = [like, like, like]
    col = _CONTRACT_SORTS.get(sort, "current_amt")
    order_sql = "ASC" if order == "asc" else "DESC"
    xj, xsel = _crosswalk_clause("c")
    full = f"WITH c AS ({_contracts_grain(fy_src)}) SELECT c.*{xsel} FROM c {xj} {outer_where}"
    total = con.execute(f"SELECT COUNT(*) FROM ({full}) t", params).fetchone()[0]
    rows = con.execute(
        f"{full} ORDER BY {col} {order_sql} NULLS LAST LIMIT ? OFFSET ?",
        params + [int(limit), (max(page, 1) - 1) * int(limit)]
    ).fetchall()
    cols = [d[0] for d in con.description]
    con.close()
    data = []
    for r in rows:
        d = dict(zip(cols, r))
        for k in ("original", "current_amt", "invoiced", "releases"):
            d[k] = float(d[k]) if d.get(k) is not None else 0.0
        data.append(d)
    import math
    return {"available": True, "data": data, "total": total, "page": page,
            "pages": math.ceil(total / limit) if limit else 1}


@router.get("/contracts/summary")
async def nycha_contracts_summary():
    if not _available("nycha_contracts"):
        return _CONTRACTS_EMPTY
    try:
        return _cached("nycha:contracts:summary", _query_contracts_summary)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA contracts summary failed: {exc}")


@router.get("/contracts")
async def nycha_contracts(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                          sort: str = "current", order: str = "desc",
                          page: int = 1, limit: int = 50):
    if not _available("nycha_contracts"):
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"nycha:contracts:{fiscal_year}:{q}:{sort}:{order}:{page}:{limit}"
    try:
        return _cached(key, lambda: _query_contracts_list(fiscal_year, q, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA contracts failed: {exc}")


_CONTRACT_EXPORT_CAP = 50000
_CONTRACT_EXPORT_COLS = ["contract_id", "vendor", "purpose", "responsibility_center",
                         "award_method", "contract_type", "industry", "funding_source",
                         "pin", "start_date", "end_date", "fiscal_year",
                         "original", "current_amt", "invoiced", "releases"]


def _query_contracts_export(fiscal_year, q, sort, order) -> tuple:
    """CSV of the filtered contract set (contract grain), capped. Returns (csv, n)."""
    con = _con()
    src = f"read_parquet({_file('nycha_contracts')})"
    fy_src = src
    if fiscal_year:
        fy_src = f"(SELECT * FROM {src} WHERE TRY_CAST(fiscal_year AS INTEGER) = {int(fiscal_year)})"
    outer_where, params = "", []
    if q:
        outer_where = "WHERE vendor ILIKE ? OR purpose ILIKE ? OR contract_id ILIKE ?"
        like = f"%{q}%"; params = [like, like, like]
    col = _CONTRACT_SORTS.get(sort, "current_amt")
    order_sql = "ASC" if order == "asc" else "DESC"
    cols = ", ".join(_CONTRACT_EXPORT_COLS)
    rows = con.execute(
        f"WITH c AS ({_contracts_grain(fy_src)}) SELECT {cols} FROM c {outer_where} "
        f"ORDER BY {col} {order_sql} NULLS LAST LIMIT {_CONTRACT_EXPORT_CAP}", params
    ).fetchall()
    con.close()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_CONTRACT_EXPORT_COLS)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue(), len(rows)


@router.get("/contracts/export")
async def nycha_contracts_export(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                                 sort: str = "current", order: str = "desc"):
    """Download the current filtered NYCHA contract set as CSV (capped at 50k)."""
    if not _available("nycha_contracts"):
        raise HTTPException(status_code=404, detail="NYCHA contracts not available")
    try:
        csv_text, n = _query_contracts_export(fiscal_year, q, sort, order)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA contracts export failed: {exc}")
    return Response(content=csv_text, media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="nycha-contracts-fy{fiscal_year or "all"}.csv"',
        "X-Row-Count": str(n), "X-Row-Cap": str(_CONTRACT_EXPORT_CAP),
    })


# ---------------------------------------------------------------------------
# NYCHA Spending  (per-payment transactions -> partitioned lake, aggregated here)
# ---------------------------------------------------------------------------

# NOTE: aggregate `amount_spent`, NOT `check_amount`. The feed explodes each
# payment (document_id) into thousands of rows — one per development ×
# expense-category — and REPEATS the full check_amount on every row (SUM(check_amount)
# over-counts ~377x, e.g. $1.9T vs the real ~$5B). `amount_spent` is the per-row
# allocated share, so it sums correctly at every grain (category/funding/development).
def _spending_glob(fiscal_year=None) -> str:
    """read_parquet arg for the partitioned NYCHA spending lake (hive-partitioned
    on fiscal_year). One FY, or all FYs."""
    base = _BASE.rstrip("/")
    fy = f"fiscal_year={int(fiscal_year)}" if fiscal_year else "fiscal_year=*"
    return f"'{base}/nycha_spending/{fy}/*.parquet'"


def _spending_available() -> bool:
    now = time.time()
    if now - _avail_cache["ts"] < 300 and "nycha_spending" in _avail_cache["val"]:
        return _avail_cache["val"]["nycha_spending"]
    ok = False
    try:
        con = _con()
        con.execute(f"SELECT 1 FROM read_parquet({_spending_glob()}, hive_partitioning=true) LIMIT 1").fetchone()
        con.close()
        ok = True
    except Exception:
        ok = False
    _avail_cache["val"]["nycha_spending"] = ok
    _avail_cache["ts"] = now
    return ok


_SPENDING_EMPTY = {"available": False, "latest_year": None, "totals": {}, "by_year": [],
                   "by_category": [], "by_funding_source": [], "section_8": {}}

# Per-row spend: `amount_spent` is the allocated share for the denormalized
# transaction categories (Section 8 / Contracts / Other), but is NULL for Payroll
# (which has no document_id and isn't row-exploded) — there the real value is in
# check_amount. Using check_amount for the denormalized categories over-counts ~377x;
# COALESCE would pull negative reversal checks. This expression is correct at every
# grain. FY2025 total ~= $6.9B (Section 8 $2.25B / Contracts $2.08B / Payroll $1.43B /
# Other $1.13B), consistent with NYCHA's scale.
_SPEND = ("(CASE WHEN amount_spent IS NOT NULL THEN amount_spent "
          "WHEN spending_category = 'Payroll' THEN check_amount ELSE 0 END)")


def _query_spending_summary() -> dict:
    con = _con()
    con.execute("SET memory_limit='2GB';")
    allsrc = f"read_parquet({_spending_glob()}, hive_partitioning=true)"
    latest = _latest_full_fy(con.execute(f"SELECT MAX(fiscal_year) FROM {allsrc}").fetchone()[0])
    src = f"read_parquet({_spending_glob(latest)}, hive_partitioning=true)"
    total = con.execute(f"SELECT COALESCE(SUM({_SPEND}),0) FROM {src}").fetchone()[0]
    by_year = con.execute(
        f"SELECT fiscal_year, COALESCE(SUM({_SPEND}),0) FROM {allsrc} "
        f"GROUP BY fiscal_year ORDER BY fiscal_year"
    ).fetchall()
    by_cat = con.execute(
        f"SELECT spending_category, COALESCE(SUM({_SPEND}),0) v FROM {src} "
        f"WHERE spending_category IS NOT NULL GROUP BY spending_category ORDER BY v DESC LIMIT 15"
    ).fetchall()
    by_fund = con.execute(
        f"SELECT funding_source, COALESCE(SUM({_SPEND}),0) v FROM {src} "
        f"WHERE funding_source IS NOT NULL GROUP BY funding_source ORDER BY v DESC LIMIT 15"
    ).fetchall()
    top_v = con.execute(
        f"SELECT vendor, COALESCE(SUM({_SPEND}),0) v FROM {src} "
        f"WHERE vendor IS NOT NULL AND vendor NOT IN ('N/A','') GROUP BY vendor ORDER BY v DESC LIMIT 15"
    ).fetchall()
    s8 = con.execute(
        f"SELECT CASE WHEN upper(section_8)='Y' THEN 'Section 8' ELSE 'Other' END grp, "
        f"COALESCE(SUM({_SPEND}),0) FROM {src} GROUP BY grp"
    ).fetchall()
    con.close()
    return {
        "available": True,
        "latest_year": int(latest) if latest else None,
        "totals": {"spending": float(total)},
        "by_year": [{"year": int(y), "spending": float(v)} for (y, v) in by_year if y is not None],
        "by_category": [{"category": c, "spending": float(v)} for (c, v) in by_cat],
        "by_funding_source": [{"funding_source": fs, "spending": float(v)} for (fs, v) in by_fund],
        "top_vendors": [{"vendor": v, "spending": float(a)} for (v, a) in top_v],
        "section_8": {grp: float(v) for (grp, v) in s8},
    }


_DEV_SORTS = {"spending": "spending", "development": "development", "payments": "payments"}


def _query_spending_by_development(fiscal_year, sort, order, page, limit) -> dict:
    con = _con()
    con.execute("SET memory_limit='2GB';")
    allsrc = f"read_parquet({_spending_glob()}, hive_partitioning=true)"
    fy = fiscal_year or _latest_full_fy(con.execute(f"SELECT MAX(fiscal_year) FROM {allsrc}").fetchone()[0])
    src = f"read_parquet({_spending_glob(fy)}, hive_partitioning=true)"
    col = _DEV_SORTS.get(sort, "spending")
    order_sql = "ASC" if order == "asc" else "DESC"
    base = (
        f"SELECT responsibility_center AS development, COALESCE(SUM({_SPEND}),0) AS spending, "
        f"COUNT(*) AS payments FROM {src} WHERE responsibility_center IS NOT NULL "
        f"GROUP BY responsibility_center"
    )
    total = con.execute(f"SELECT COUNT(*) FROM ({base}) t").fetchone()[0]
    rows = con.execute(
        f"{base} ORDER BY {col} {order_sql} LIMIT ? OFFSET ?",
        [int(limit), (max(page, 1) - 1) * int(limit)]
    ).fetchall()
    con.close()
    import math
    return {
        "available": True, "fiscal_year": int(fy),
        "data": [{"development": r[0], "spending": float(r[1]), "payments": int(r[2])} for r in rows],
        "total": total, "page": page, "pages": math.ceil(total / limit) if limit else 1,
    }


@router.get("/spending/summary")
async def nycha_spending_summary():
    if not _spending_available():
        return _SPENDING_EMPTY
    try:
        return _cached("nycha:spending:summary", _query_spending_summary)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA spending summary failed: {exc}")


@router.get("/spending/by-development")
async def nycha_spending_by_development(fiscal_year: Optional[int] = None, sort: str = "spending",
                                        order: str = "desc", page: int = 1, limit: int = 50):
    if not _spending_available():
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"nycha:spending:dev:{fiscal_year}:{sort}:{order}:{page}:{limit}"
    try:
        return _cached(key, lambda: _query_spending_by_development(fiscal_year, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA spending by-development failed: {exc}")


# --- Spending payment-grain record explorer ---------------------------------
# A "record" = one check-level payment (document_id). The feed explodes each
# payment into many rows (one per development x expense-category) repeating the
# full check_amount, so we collapse to document_id and take MAX(check_amount) as
# the payment total. document_id IS NOT NULL excludes Payroll (aggregate-only in
# the feed — no per-payment records). FY-scoped so each query prunes to one
# partition (~3M rows) instead of the full 22.56M-row lake.
_SPEND_REC_SORTS = {"amount": "amount", "date": "issue_date", "vendor": "vendor"}
_SPEND_REC_SELECT = (
    "SELECT document_id, MAX(vendor) vendor, MAX(issue_date) issue_date, "
    "MAX(check_status) check_status, MAX(contract_id) contract_id, MAX(purpose) purpose, "
    "MAX(purchase_order_type) po_type, MAX(section_8) section_8, MAX(industry) industry, "
    "MAX(spending_category) spending_category, MAX(funding_source) funding_source, "
    "MAX(responsibility_center) responsibility_center, MAX(expense_category) expense_category, "
    "MAX(TRY_CAST(check_amount AS DOUBLE)) amount, "
    "MAX(TRY_CAST(fiscal_year AS INTEGER)) fiscal_year"
)


def _spend_rec_where(fiscal_year, spending_category, section_8):
    where, params = ["document_id IS NOT NULL"], []
    if spending_category:
        where.append("spending_category = ?"); params.append(spending_category)
    if section_8 in ("Y", "N"):
        where.append("section_8 = ?"); params.append(section_8)
    return "WHERE " + " AND ".join(where), params


def _query_spending_records(fiscal_year, q, spending_category, section_8, sort, order, page, limit) -> dict:
    con = _con()
    src = f"read_parquet({_spending_glob(fiscal_year)}, hive_partitioning=true)"
    base_where, params = _spend_rec_where(fiscal_year, spending_category, section_8)
    pay = f"{_SPEND_REC_SELECT} FROM {src} {base_where} GROUP BY document_id"
    outer, oparams = "", []
    if q:
        outer = "WHERE vendor ILIKE ? OR purpose ILIKE ? OR document_id ILIKE ? OR contract_id ILIKE ?"
        like = f"%{q}%"; oparams = [like, like, like, like]
    xj, xsel = _crosswalk_clause("pay")
    full = f"WITH pay AS ({pay}) SELECT pay.*{xsel} FROM pay {xj} {outer}"
    total = con.execute(f"SELECT COUNT(*) FROM ({full}) t", params + oparams).fetchone()[0]
    col = _SPEND_REC_SORTS.get(sort, "amount")
    order_sql = "ASC" if order == "asc" else "DESC"
    rows = con.execute(f"{full} ORDER BY {col} {order_sql} NULLS LAST LIMIT ? OFFSET ?",
                       params + oparams + [int(limit), (max(page, 1) - 1) * int(limit)]).fetchall()
    cols = [d[0] for d in con.description]
    con.close()
    data = []
    for r in rows:
        d = dict(zip(cols, r))
        d["amount"] = float(d["amount"]) if d.get("amount") is not None else 0.0
        data.append(d)
    return {"available": True, "data": data, "total": total, "page": page,
            "pages": math.ceil(total / limit) if limit else 1}


@router.get("/spending/records")
async def nycha_spending_records(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                                 spending_category: Optional[str] = None, section_8: Optional[str] = None,
                                 sort: str = "amount", order: str = "desc",
                                 page: int = 1, limit: int = 25):
    if not _spending_available():
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"nycha:spend:rec:{fiscal_year}:{q}:{spending_category}:{section_8}:{sort}:{order}:{page}:{limit}"
    try:
        return _cached(key, lambda: _query_spending_records(fiscal_year, q, spending_category, section_8, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA spending records failed: {exc}")


_SPEND_EXPORT_CAP = 50000
_SPEND_EXPORT_COLS = ["document_id", "vendor", "issue_date", "check_status", "contract_id",
                      "spending_category", "funding_source", "responsibility_center",
                      "expense_category", "section_8", "po_type", "industry", "amount",
                      "fiscal_year", "purpose"]


@router.get("/spending/records/export")
async def nycha_spending_records_export(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                                        spending_category: Optional[str] = None, section_8: Optional[str] = None,
                                        sort: str = "amount", order: str = "desc"):
    if not _spending_available():
        raise HTTPException(status_code=404, detail="NYCHA spending not available")
    try:
        d = _query_spending_records(fiscal_year, q, spending_category, section_8, sort, order, 1, _SPEND_EXPORT_CAP)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA spending export failed: {exc}")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_SPEND_EXPORT_COLS)
    for row in d.get("data", []):
        w.writerow(["" if row.get(c) is None else row.get(c) for c in _SPEND_EXPORT_COLS])
    return Response(content=buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="nycha-payments-fy{fiscal_year or "recent"}.csv"',
        "X-Row-Count": str(len(d.get("data", []))), "X-Row-Cap": str(_SPEND_EXPORT_CAP),
    })


# ---------------------------------------------------------------------------
# NYCHA vendor activity — powers the NYCHA section on the City vendor profile
# (routers/oce.py::get_vendor, via the nycha_vendor_crosswalk reverse lookup).
# ---------------------------------------------------------------------------

def _query_vendor_activity(names: list) -> dict:
    """Aggregate NYCHA contract + spending activity for a set of raw NYCHA vendor
    names (one PASSPort vendor can match several name variants). Contracts at
    contract grain via _contracts_grain; spending as SUM(_SPEND) — the per-row
    allocated share, NOT raw check_amount (the feed repeats check_amount on every
    exploded row, see the _SPEND note) — plus distinct payments (document_id;
    Payroll has none, and vendors don't appear in Payroll anyway)."""
    ph = ", ".join("?" for _ in names)
    out = {"contracts": None, "spending": None}
    if _available("nycha_contracts"):
        con = _con()
        try:
            src = f"read_parquet({_file('nycha_contracts')})"
            n, cur, inv = con.execute(
                f"WITH c AS ({_contracts_grain(src)}) "
                f"SELECT COUNT(*), COALESCE(SUM(current_amt),0), COALESCE(SUM(invoiced),0) "
                f"FROM c WHERE vendor IN ({ph})", names
            ).fetchone()
            out["contracts"] = {"count": int(n), "current": float(cur), "invoiced": float(inv)}
        finally:
            con.close()
    if _spending_available():
        con = _con()
        try:
            con.execute("SET memory_limit='2GB';")
            src = f"read_parquet({_spending_glob()}, hive_partitioning=true)"
            total, pays, min_fy, max_fy = con.execute(
                f"SELECT COALESCE(SUM({_SPEND}),0), COUNT(DISTINCT document_id), "
                f"MIN(fiscal_year), MAX(fiscal_year) FROM {src} WHERE vendor IN ({ph})", names
            ).fetchone()
            out["spending"] = {"total": float(total), "payments": int(pays),
                               "min_year": int(min_fy) if min_fy is not None else None,
                               "max_year": int(max_fy) if max_fy is not None else None}
        finally:
            con.close()
    return out


def vendor_activity_for_names(names: list) -> Optional[dict]:
    """Sync (DuckDB) — call via to_duckdb_thread from async handlers. Returns
    None when the vendor has no NYCHA activity at all, so callers can omit the
    section entirely. Cached daily like the other NYCHA rollups."""
    names = sorted({(n or "").strip() for n in names} - {""})
    if not names:
        return None
    key = "nycha:vendor-activity:" + "|".join(names)
    act = _cached(key, lambda: _query_vendor_activity(names))
    c, s = act.get("contracts"), act.get("spending")
    if not (c and c["count"]) and not (s and (s["payments"] or s["total"])):
        return None
    return act


@router.get("/vendor-activity")
async def nycha_vendor_activity(name: str):
    """NYCHA activity rollup for one exact vendor name (as it appears in the
    NYCHA lake). The vendor profile uses the in-process helper; this endpoint
    exists for direct checks and other consumers."""
    try:
        act = await to_duckdb_thread(vendor_activity_for_names, [name])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA vendor activity failed: {exc}")
    return {"available": act is not None, **(act or {})}


# ---------------------------------------------------------------------------
# NYCHA vendor directory + NYCHA-native vendor profiles.
# NYCHA is a separate authority; a NYCHA vendor with no PASSPort record (~half of
# contract vendors) has no City vendor profile. This lists ALL NYCHA vendors
# (contracts ∪ spending) with their activity + crosswalk match, so matched
# vendors link to the City profile and unmatched vendors get a NYCHA-native one.
# ---------------------------------------------------------------------------

def _crosswalk_name_to_id() -> dict:
    """name → PASSPort id from the crosswalk parquet (empty when absent / S3 base)."""
    xpath = f"{_BASE.rstrip('/')}/nycha_vendor_crosswalk.parquet"
    if _BASE.lower().startswith("http") or not os.path.exists(xpath):
        return {}
    con = _con()
    try:
        rows = con.execute(
            f"SELECT nycha_vendor_name, passport_supplier_id FROM read_parquet('{xpath}')"
        ).fetchall()
    finally:
        con.close()
    return {n: pid for (n, pid) in rows if pid}


def _query_vendors_all() -> list:
    """Every NYCHA vendor (contracts ∪ spending) with contract count/current/
    invoiced (contract grain), spending total + payment count, and the crosswalk
    vendor_id. Aggregations run once and are merged in Python (~43k vendors); the
    spending GROUP BY scans the full lake (~10s cold) so this is cached daily and
    the endpoint paginates/searches the cached list per request."""
    cagg: dict = {}
    if _available("nycha_contracts"):
        con = _con()
        try:
            src = f"read_parquet({_file('nycha_contracts')})"
            for v, n, cur, inv in con.execute(
                f"WITH grain AS ({_contracts_grain(src)}) "
                f"SELECT vendor, COUNT(*), COALESCE(SUM(current_amt),0), COALESCE(SUM(invoiced),0) "
                f"FROM grain WHERE vendor IS NOT NULL AND vendor <> '' GROUP BY vendor"
            ).fetchall():
                cagg[v] = {"contracts": int(n), "current": float(cur), "invoiced": float(inv)}
        finally:
            con.close()
    sagg: dict = {}
    if _spending_available():
        con = _con()
        try:
            con.execute("SET memory_limit='2GB';")
            src = f"read_parquet({_spending_glob()}, hive_partitioning=true)"
            for v, sp, pay in con.execute(
                f"SELECT vendor, COALESCE(SUM({_SPEND}),0), COUNT(DISTINCT document_id) FROM {src} "
                f"WHERE vendor IS NOT NULL AND vendor NOT IN ('N/A','') GROUP BY vendor"
            ).fetchall():
                sagg[v] = {"spending": float(sp), "payments": int(pay)}
        finally:
            con.close()
    xw = _crosswalk_name_to_id()
    out = []
    for v in set(cagg) | set(sagg):
        c = cagg.get(v, {}); s = sagg.get(v, {})
        out.append({
            "vendor": v,
            "contracts": c.get("contracts", 0), "current": c.get("current", 0.0),
            "invoiced": c.get("invoiced", 0.0),
            "spending": s.get("spending", 0.0), "payments": s.get("payments", 0),
            "vendor_id": xw.get(v),
        })
    return out


_VEND_SORTS = {"spending", "current", "invoiced", "contracts", "payments", "vendor"}


def _vendors_page(q, sort, order, page, limit) -> dict:
    rows = _cached("nycha:vendors:all", _query_vendors_all)
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in (r["vendor"] or "").lower()]
    key = sort if sort in _VEND_SORTS else "spending"
    rev = order != "asc"
    if key == "vendor":
        rows = sorted(rows, key=lambda r: (r["vendor"] or "").lower(), reverse=rev)
    else:
        rows = sorted(rows, key=lambda r: r.get(key) or 0, reverse=rev)
    total = len(rows)
    start = (max(page, 1) - 1) * limit
    return {"available": True, "data": rows[start:start + limit], "total": total,
            "page": page, "pages": math.ceil(total / limit) if limit else 1}


@router.get("/vendors")
async def nycha_vendors(q: Optional[str] = None, sort: str = "spending", order: str = "desc",
                        page: int = 1, limit: int = 25):
    """Searchable/sortable/paginated directory of all NYCHA vendors."""
    if not (_available("nycha_contracts") or _spending_available()):
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(int(limit), 200))
    try:
        return await to_duckdb_thread(_vendors_page, q, sort, order, page, limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA vendors failed: {exc}")


_VEND_EXPORT_CAP = 50000
_VEND_EXPORT_COLS = ["vendor", "vendor_id", "contracts", "current", "invoiced", "spending", "payments"]


@router.get("/vendors/export")
async def nycha_vendors_export(q: Optional[str] = None, sort: str = "spending", order: str = "desc"):
    if not (_available("nycha_contracts") or _spending_available()):
        raise HTTPException(status_code=404, detail="NYCHA vendors not available")
    try:
        d = await to_duckdb_thread(_vendors_page, q, sort, order, 1, _VEND_EXPORT_CAP)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA vendors export failed: {exc}")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_VEND_EXPORT_COLS)
    for row in d.get("data", []):
        w.writerow(["" if row.get(c) is None else row.get(c) for c in _VEND_EXPORT_COLS])
    return Response(content=buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="nycha-vendors.csv"',
        "X-Row-Count": str(len(d.get("data", []))), "X-Row-Cap": str(_VEND_EXPORT_CAP),
    })


def _vendor_crosswalk_id(name: str) -> Optional[str]:
    xpath = f"{_BASE.rstrip('/')}/nycha_vendor_crosswalk.parquet"
    if _BASE.lower().startswith("http") or not os.path.exists(xpath):
        return None
    con = _con()
    try:
        r = con.execute(
            f"SELECT passport_supplier_id FROM read_parquet('{xpath}') "
            f"WHERE nycha_vendor_name = ? AND passport_supplier_id IS NOT NULL LIMIT 1", [name]
        ).fetchone()
    finally:
        con.close()
    return r[0] if r else None


def _query_vendor_contracts(name: str) -> list:
    """Contract-grain rows for one exact NYCHA vendor name (capped)."""
    if not _available("nycha_contracts"):
        return []
    con = _con()
    try:
        src = f"(SELECT * FROM read_parquet({_file('nycha_contracts')}) WHERE vendor = ?)"
        rows = con.execute(
            f"WITH c AS ({_contracts_grain(src)}) SELECT c.* FROM c "
            f"ORDER BY current_amt DESC NULLS LAST LIMIT 500", [name]
        ).fetchall()
        cols = [d[0] for d in con.description]
    finally:
        con.close()
    data = []
    for r in rows:
        d = dict(zip(cols, r))
        for k in ("original", "current_amt", "invoiced", "releases"):
            d[k] = float(d[k]) if d.get(k) is not None else 0.0
        data.append(d)
    return data


def _vendor_profile(name: str) -> dict:
    act = vendor_activity_for_names([name])
    return {
        "available": act is not None,
        "vendor": name,
        "vendor_id": _vendor_crosswalk_id(name),
        "contracts": (act or {}).get("contracts"),
        "spending": (act or {}).get("spending"),
        "contract_list": _query_vendor_contracts(name),
    }


@router.get("/vendor")
async def nycha_vendor(name: str):
    """NYCHA-native vendor profile (rollup + contract list) for one exact vendor
    name. `vendor_id` is set when the vendor IS crosswalked — the frontend then
    redirects to the richer City vendor profile instead of rendering this."""
    try:
        return await to_duckdb_thread(_vendor_profile, name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA vendor profile failed: {exc}")


# ---------------------------------------------------------------------------
# NYCHA individual contract profile — contract-grain detail + actual payments
# (the spending lake carries the same contract_id, and DuckDB prunes on it fast).
# ---------------------------------------------------------------------------

def _query_nycha_contract(cid: str) -> Optional[dict]:
    if not _available("nycha_contracts"):
        return None
    con = _con()
    try:
        src = f"(SELECT * FROM read_parquet({_file('nycha_contracts')}) WHERE contract_id = ?)"
        row = con.execute(f"WITH c AS ({_contracts_grain(src)}) SELECT c.* FROM c LIMIT 1", [cid]).fetchone()
        cols = [d[0] for d in con.description]
    finally:
        con.close()
    if not row:
        return None
    contract = dict(zip(cols, row))
    for k in ("original", "current_amt", "invoiced", "releases"):
        contract[k] = float(contract[k]) if contract.get(k) is not None else 0.0

    vid = _vendor_crosswalk_id(contract["vendor"]) if contract.get("vendor") else None

    payments = None
    if _spending_available():
        con = _con()
        try:
            con.execute("SET memory_limit='2GB';")
            src = f"read_parquet({_spending_glob()}, hive_partitioning=true)"
            total, cnt, mn, mx = con.execute(
                f"SELECT COALESCE(SUM({_SPEND}),0), COUNT(DISTINCT document_id), "
                f"MIN(fiscal_year), MAX(fiscal_year) FROM {src} WHERE contract_id = ?", [cid]
            ).fetchone()
            by_year = con.execute(
                f"SELECT fiscal_year, COALESCE(SUM({_SPEND}),0) FROM {src} "
                f"WHERE contract_id = ? GROUP BY fiscal_year ORDER BY fiscal_year", [cid]
            ).fetchall()
            plist = con.execute(
                f"WITH pay AS ({_SPEND_REC_SELECT} FROM {src} "
                f"WHERE contract_id = ? AND document_id IS NOT NULL GROUP BY document_id) "
                f"SELECT * FROM pay ORDER BY amount DESC NULLS LAST LIMIT 100", [cid]
            ).fetchall()
            pcols = [d[0] for d in con.description]
        finally:
            con.close()
        plist_out = []
        for r in plist:
            d = dict(zip(pcols, r))
            d["amount"] = float(d["amount"]) if d.get("amount") is not None else 0.0
            plist_out.append(d)
        payments = {
            "total": float(total), "count": int(cnt),
            "min_year": int(mn) if mn is not None else None,
            "max_year": int(mx) if mx is not None else None,
            "by_year": [{"year": int(y), "spending": float(v)} for (y, v) in by_year if y is not None],
            "list": plist_out,
        }
    return {"available": True, "contract": contract, "vendor_id": vid, "payments": payments}


def search_vendors(term: str, limit: int = 8) -> list:
    """Name search over NYCHA CONTRACT vendors for global-search federation.
    Scoped to the contracts parquet (small/fast, pruned by the ILIKE before the
    grain) rather than the full 43k contracts∪spending aggregate, so the navbar
    typeahead stays snappy — the meaningful NYCHA-only vendors (e.g. ADAMS
    EUROPEAN) are contract vendors. Attaches the crosswalk vendor_id so matched
    names can link to the City profile. Resilient: returns [] on any failure."""
    term = (term or "").strip()
    if not term or not _available("nycha_contracts"):
        return []
    try:
        con = _con()
        try:
            src = f"(SELECT * FROM read_parquet({_file('nycha_contracts')}) WHERE vendor ILIKE ?)"
            rows = con.execute(
                f"WITH c AS ({_contracts_grain(src)}) "
                f"SELECT vendor, COUNT(*) contracts, COALESCE(SUM(current_amt),0) cur "
                f"FROM c WHERE vendor IS NOT NULL AND vendor <> '' "
                f"GROUP BY vendor ORDER BY cur DESC LIMIT ?",  # `current` is a reserved word
                [f"%{term}%", int(limit)]
            ).fetchall()
        finally:
            con.close()
    except Exception as exc:  # resilient (must never break federated search) but not silent
        logger.warning(f"[nycha] search_vendors failed for {term!r}: {exc}")
        return []
    xw = _crosswalk_name_to_id()
    return [{"vendor": v, "contracts": int(n), "current": float(cur), "vendor_id": xw.get(v)}
            for (v, n, cur) in rows]


@router.get("/contract")
async def nycha_contract(id: str):
    """Individual NYCHA contract profile: contract-grain detail + actual payments
    (from the spending lake, matched on contract_id)."""
    try:
        data = await to_duckdb_thread(_query_nycha_contract, id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NYCHA contract profile failed: {exc}")
    if data is None:
        return {"available": False}
    return data
