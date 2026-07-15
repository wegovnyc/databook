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
import time
import math
import datetime
from typing import Optional

import duckdb
from fastapi import APIRouter, HTTPException

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


# ---------------------------------------------------------------------------
# NYCHA Revenue  (recognized = collected; realization = recognized/modified)
# ---------------------------------------------------------------------------

# Defensive line-grain dedup, mirroring routers/budget_revenue.py: the City Revenue
# feed repeats adopted/modified across detail rows (~460x over-count on naive SUM).
# NYCHA's feed is smaller and looks line-grain already, but we collapse to the
# revenue-line grain with MAX() before aggregating to be safe against the same trap.
# ⚠ RE-VALIDATE at ingest: if totals look implausible (NYCHA revenue is ~$4-5B/yr,
# Section 8 subsidy ~$1.6B), revisit this grain.
_REV_GRAIN = ("budget_fiscal_year, budget_name, budget_type, revenue_expense_category, "
              "funding_source, responsibility_center, revenue_category, revenue_class")


def _revenue_lines(src: str) -> str:
    return (
        f"SELECT budget_fiscal_year AS year, revenue_category, funding_source, "
        f"MAX(adopted) AS adopted, MAX(modified) AS modified, "
        f"MAX(recognized) AS recognized, MAX(remaining) AS remaining "
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
    full = f"WITH c AS ({_contracts_grain(fy_src)}) SELECT * FROM c {outer_where}"
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
