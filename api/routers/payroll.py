"""
Payroll domain (CheckbookNYC parity) — DuckDB over a single Parquet, the annual
rollup built by build_budget_revenue_parquet.py (domain "payroll") from
extractors/checkbook_payroll.py.

Grain: (fiscal_year, agency, title, payroll_type). Amounts are pre-summed
(gross/base/overtime/other are additive); `records` = payment-row count (NOT a
distinct-employee headcount — the feed has no employee id); avg annual salary is
derived from salary_sum/salary_count over positive-salary rows only.

Schema-tolerant like budget_revenue: every endpoint returns `available: false`
with an empty shape until the Parquet is ingested. Cached daily; DuckDB memory
bounded; defaults to the latest fully-closed FY.
"""
from __future__ import annotations

import os
import io
import csv
import time
import math
import asyncio
import datetime
from typing import Optional

import duckdb
from fastapi import APIRouter, HTTPException, Response

from modules.duckpool import to_duckdb_thread

router = APIRouter(prefix="/oce/payroll", tags=["payroll"])

_BASE = os.environ.get("BUDGET_REVENUE_BASE", "https://nyc-databook-spending.s3.amazonaws.com")
_FILE = "payroll/payroll.parquet"

_CACHE: dict = {}
_CACHE_TTL = 86400
_avail_cache: dict = {"ts": 0.0, "val": None}

# avg annual salary (headcount-free): total reported salary / rows that reported one.
_AVGSAL = "CASE WHEN SUM(salary_count) > 0 THEN SUM(salary_sum)/SUM(salary_count) ELSE 0 END"


def _src() -> str:
    return f"read_parquet('{_BASE.rstrip('/')}/{_FILE}')"


def _con():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET memory_limit='1GB'; SET threads=2;")
    return con


def _available() -> bool:
    now = time.time()
    if now - _avail_cache["ts"] < 300 and _avail_cache["val"] is not None:
        return _avail_cache["val"]
    ok = False
    try:
        con = _con()
        con.execute(f"SELECT 1 FROM {_src()} LIMIT 1").fetchone()
        con.close()
        ok = True
    except Exception:
        ok = False
    _avail_cache["val"] = ok
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
    if max_year is None:
        return None
    today = datetime.date.today()
    settled = today.year if today.month >= 10 else today.year - 1
    return min(settled, int(max_year))


_EMPTY = {"available": False, "latest_year": None, "totals": {}, "by_year": [],
          "by_agency": [], "by_title": [], "by_payroll_type": []}


def _query_summary() -> dict:
    con = _con()
    src = _src()
    latest = _latest_full_fy(con.execute(f"SELECT MAX(fiscal_year) FROM {src}").fetchone()[0])
    g, b, ot, oth, rec, avgsal = con.execute(
        f"SELECT COALESCE(SUM(gross),0), COALESCE(SUM(base),0), COALESCE(SUM(overtime),0), "
        f"COALESCE(SUM(other),0), COALESCE(SUM(records),0), {_AVGSAL} FROM {src} WHERE fiscal_year = ?",
        [latest]
    ).fetchone()
    by_year = con.execute(
        f"SELECT fiscal_year, COALESCE(SUM(gross),0), COALESCE(SUM(overtime),0) "
        f"FROM {src} GROUP BY fiscal_year ORDER BY fiscal_year"
    ).fetchall()
    by_agency = con.execute(
        f"SELECT agency, COALESCE(SUM(gross),0) g, COALESCE(SUM(overtime),0) ot, "
        f"COALESCE(SUM(records),0) r FROM {src} WHERE fiscal_year = ? AND agency IS NOT NULL "
        f"GROUP BY agency ORDER BY g DESC LIMIT 15", [latest]
    ).fetchall()
    by_title = con.execute(
        f"SELECT title, COALESCE(SUM(gross),0) g, {_AVGSAL} a FROM {src} "
        f"WHERE fiscal_year = ? AND title IS NOT NULL GROUP BY title ORDER BY g DESC LIMIT 15", [latest]
    ).fetchall()
    by_ptype = con.execute(
        f"SELECT COALESCE(payroll_type,'(unspecified)'), COALESCE(SUM(gross),0) g, COALESCE(SUM(overtime),0) ot "
        f"FROM {src} WHERE fiscal_year = ? GROUP BY payroll_type ORDER BY g DESC", [latest]
    ).fetchall()
    con.close()
    return {
        "available": True,
        "latest_year": int(latest) if latest else None,
        "totals": {"gross": float(g), "base": float(b), "overtime": float(ot),
                   "other": float(oth), "records": int(rec), "avg_salary": float(avgsal),
                   "ot_share": (float(ot) / float(g)) if g else 0.0},
        "by_year": [{"year": int(y), "gross": float(gg), "overtime": float(oo)}
                    for (y, gg, oo) in by_year if y is not None],
        "by_agency": [{"agency": a, "gross": float(gg), "overtime": float(oo), "records": int(r)}
                      for (a, gg, oo, r) in by_agency],
        "by_title": [{"title": t, "gross": float(gg), "avg_salary": float(a)} for (t, gg, a) in by_title],
        "by_payroll_type": [{"payroll_type": p, "gross": float(gg), "overtime": float(oo)}
                            for (p, gg, oo) in by_ptype],
    }


@router.get("/summary")
async def payroll_summary():
    if not _available():
        return _EMPTY
    try:
        return await _cached("payroll:summary", _query_summary)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Payroll summary failed: {exc}")


_AGENCY_SORTS = {"gross": "gross", "overtime": "overtime", "records": "records",
                 "avg_salary": "avg_salary", "agency": "agency"}


def _query_agencies(fiscal_year, sort, order, page, limit) -> dict:
    con = _con()
    src = _src()
    fy = fiscal_year or _latest_full_fy(con.execute(f"SELECT MAX(fiscal_year) FROM {src}").fetchone()[0])
    col = _AGENCY_SORTS.get(sort, "gross")
    order_sql = "ASC" if order == "asc" else "DESC"
    base = (
        f"SELECT agency, COALESCE(SUM(gross),0) gross, COALESCE(SUM(base),0) base, "
        f"COALESCE(SUM(overtime),0) overtime, COALESCE(SUM(other),0) other, "
        f"COALESCE(SUM(records),0) records, {_AVGSAL} avg_salary "
        f"FROM {src} WHERE fiscal_year = ? AND agency IS NOT NULL GROUP BY agency"
    )
    total = con.execute(f"SELECT COUNT(*) FROM ({base}) t", [fy]).fetchone()[0]
    rows = con.execute(
        f"{base} ORDER BY {col} {order_sql} NULLS LAST LIMIT ? OFFSET ?",
        [fy, int(limit), (max(page, 1) - 1) * int(limit)]
    ).fetchall()
    cols = [d[0] for d in con.description]
    con.close()
    data = [dict(zip(cols, r)) for r in rows]
    for d in data:
        for k in ("gross", "base", "overtime", "other", "avg_salary"):
            d[k] = float(d[k] or 0)
        d["records"] = int(d["records"] or 0)
    return {"available": True, "fiscal_year": int(fy), "data": data, "total": total,
            "page": page, "pages": math.ceil(total / limit) if limit else 1}


@router.get("/agencies")
async def payroll_agencies(fiscal_year: Optional[int] = None, sort: str = "gross",
                           order: str = "desc", page: int = 1, limit: int = 50):
    if not _available():
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"payroll:agencies:{fiscal_year}:{sort}:{order}:{page}:{limit}"
    try:
        return await _cached(key, lambda: _query_agencies(fiscal_year, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Payroll agencies failed: {exc}")


# --- record explorer: the rollup rows (agency / title / payroll_type) -----------
_REC_SORTS = {"gross": "gross", "overtime": "overtime", "base": "base", "records": "records",
              "avg_salary": "avg_salary", "title": "title", "agency": "agency"}


def _query_records(fiscal_year, q, agency, payroll_type, sort, order, page, limit) -> dict:
    con = _con()
    src = _src()
    fy = fiscal_year or _latest_full_fy(con.execute(f"SELECT MAX(fiscal_year) FROM {src}").fetchone()[0])
    where = ["fiscal_year = ?"]
    params: list = [fy]
    if agency:
        where.append("agency = ?"); params.append(agency)
    if payroll_type:
        where.append("payroll_type = ?"); params.append(payroll_type)
    if q:
        where.append("(title ILIKE ? OR agency ILIKE ?)")
        like = f"%{q}%"; params += [like, like]
    where_sql = "WHERE " + " AND ".join(where)
    # avg_salary is per-row here (salary_sum/salary_count) since the rollup grain
    # is already agency/title/payroll_type.
    sel = ("agency, title, payroll_type, gross, base, overtime, other, records, "
           "CASE WHEN salary_count > 0 THEN salary_sum/salary_count ELSE 0 END AS avg_salary, "
           "salary_min, salary_max")
    col = _REC_SORTS.get(sort, "gross")
    order_sql = "ASC" if order == "asc" else "DESC"
    total = con.execute(f"SELECT COUNT(*) FROM {src} {where_sql}", params).fetchone()[0]
    rows = con.execute(
        f"SELECT {sel} FROM {src} {where_sql} ORDER BY {col} {order_sql} NULLS LAST LIMIT ? OFFSET ?",
        params + [int(limit), (max(page, 1) - 1) * int(limit)]
    ).fetchall()
    cols = [d[0] for d in con.description]
    con.close()
    data = []
    for r in rows:
        d = dict(zip(cols, r))
        for k in ("gross", "base", "overtime", "other", "avg_salary", "salary_min", "salary_max"):
            d[k] = float(d[k]) if d.get(k) is not None else 0.0
        d["records"] = int(d["records"] or 0)
        data.append(d)
    return {"available": True, "fiscal_year": int(fy), "data": data, "total": total,
            "page": page, "pages": math.ceil(total / limit) if limit else 1}


@router.get("/records")
async def payroll_records(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                          agency: Optional[str] = None, payroll_type: Optional[str] = None,
                          sort: str = "gross", order: str = "desc", page: int = 1, limit: int = 25):
    if not _available():
        return {"available": False, "data": [], "total": 0, "page": 1, "pages": 1}
    limit = max(1, min(limit, 200))
    key = f"payroll:rec:{fiscal_year}:{q}:{agency}:{payroll_type}:{sort}:{order}:{page}:{limit}"
    try:
        return await _cached(key, lambda: _query_records(fiscal_year, q, agency, payroll_type, sort, order, page, limit))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Payroll records failed: {exc}")


_EXPORT_CAP = 50000
_EXPORT_COLS = ["fiscal_year", "agency", "title", "payroll_type", "gross", "base",
                "overtime", "other", "records", "avg_salary", "salary_min", "salary_max"]


@router.get("/records/export")
async def payroll_records_export(fiscal_year: Optional[int] = None, q: Optional[str] = None,
                                 agency: Optional[str] = None, payroll_type: Optional[str] = None,
                                 sort: str = "gross", order: str = "desc"):
    if not _available():
        raise HTTPException(status_code=404, detail="Payroll not available")
    try:
        d = await to_duckdb_thread(
            _query_records, fiscal_year, q, agency, payroll_type, sort, order, 1,
            _EXPORT_CAP)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Payroll export failed: {exc}")
    fy = d.get("fiscal_year")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_EXPORT_COLS)
    for row in d.get("data", []):
        row = {**row, "fiscal_year": fy}
        w.writerow(["" if row.get(c) is None else row.get(c) for c in _EXPORT_COLS])
    return Response(content=buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="nyc-payroll-fy{fy or "latest"}.csv"',
        "X-Row-Count": str(len(d.get("data", []))), "X-Row-Cap": str(_EXPORT_CAP),
    })
