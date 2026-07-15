"""Tests for the Budget & Revenue endpoints (routers/budget_revenue.py).

These verify routing + the schema-tolerant dormant shape (available:false before
ingestion) without needing the Parquet. The revenue-grain dedup logic is checked
as a SQL-shape unit test.
"""

import pytest


@pytest.mark.asyncio
async def test_budget_summary_routable(client):
    resp = await client.get("/oce/budget/summary")
    assert resp.status_code != 404, "budget/summary endpoint is missing"
    assert resp.status_code != 422


@pytest.mark.asyncio
async def test_budget_agencies_routable(client):
    resp = await client.get("/oce/budget/agencies", params={"fiscal_year": 2025, "sort": "utilization"})
    assert resp.status_code != 404, "budget/agencies endpoint is missing"
    assert resp.status_code != 422


@pytest.mark.asyncio
async def test_revenue_summary_routable(client):
    resp = await client.get("/oce/revenue/summary")
    assert resp.status_code != 404, "revenue/summary endpoint is missing"
    assert resp.status_code != 422


@pytest.mark.asyncio
async def test_revenue_agencies_routable(client):
    resp = await client.get("/oce/revenue/agencies", params={"fiscal_year": 2025})
    assert resp.status_code != 404, "revenue/agencies endpoint is missing"
    assert resp.status_code != 422


@pytest.mark.asyncio
async def test_dormant_shape_when_no_parquet(client):
    """Before ingestion the Parquet 404s → endpoints must return available:false
    with the empty shape, never a 500."""
    from routers import budget_revenue as br
    br._avail_cache = {"ts": 0.0, "val": {}}  # force a fresh availability probe
    for path in ("/oce/budget/summary", "/oce/revenue/summary"):
        resp = await client.get(path)
        assert resp.status_code == 200, f"{path} should not error when dormant: {resp.text[:200]}"
        body = resp.json()
        assert "available" in body


def test_revenue_grain_dedup_sql_shape():
    """adopted/modified are repeated BUDGET snapshots — collapse to the line grain
    with MAX (a naive SUM over-counts ~460x). recognized is ADDITIVE actual cash
    (one row per receipt) — it must be SUM()med over the 'Collected Revenue' rows,
    NOT MAX()ed (MAX kept only the largest receipt -> ~31% of modified)."""
    from routers import budget_revenue as br
    lines = br._revenue_lines("read_parquet('x')")
    assert "MAX(adopted)" in lines and "MAX(modified)" in lines
    assert "MAX(recognized)" not in lines
    assert "SUM(CASE WHEN closing_classification_name = 'Collected Revenue'" in lines
    assert "THEN recognized" in lines
    assert "GROUP BY" in lines and "revenue_source" in lines


def test_latest_full_fy_defaults_to_closed_year():
    """Dashboards default to the latest fully-closed FY, never the in-progress or
    just-ended (still-settling) year — and never a year with no data."""
    import datetime
    from routers.budget_revenue import _latest_full_fy
    assert _latest_full_fy(None) is None
    # a year far in the past always clamps to itself (never overshoots the data)
    assert _latest_full_fy(2000) == 2000
    # with abundant data the default is a fully-closed FY: this calendar year
    # (once its FY books close ~Oct) or last year — never the in-progress one
    y = datetime.date.today().year
    assert _latest_full_fy(9999) in (y - 1, y)
