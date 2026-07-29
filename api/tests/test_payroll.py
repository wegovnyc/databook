"""Tests for the Payroll domain router (DuckDB over the annual-rollup parquet)."""
import duckdb
import pytest


@pytest.fixture
def lake(tmp_path):
    d = tmp_path / "payroll"; d.mkdir()
    con = duckdb.connect()
    con.execute("""CREATE TABLE t AS SELECT * FROM (VALUES
      (2025,'Dept A','TITLE X','SALARIED',     1000.0,800.0,150.0,50.0,10,900000.0,10,80000.0,100000.0),
      (2025,'Dept A','TITLE Y','NON-SALARIED',  500.0,400.0, 50.0,50.0, 5,     0.0, 0,   NULL,    NULL),
      (2025,'Dept B','TITLE X','SALARIED',      2000.0,1900.0,50.0,50.0,20,1600000.0,20,70000.0,90000.0),
      (2024,'Dept A','TITLE X','SALARIED',       900.0,700.0,150.0,50.0, 9,810000.0, 9,80000.0,100000.0)
     ) AS v(fiscal_year,agency,title,payroll_type,gross,base,overtime,other,records,
            salary_sum,salary_count,salary_min,salary_max)""")
    con.execute(f"COPY t TO '{d}/payroll.parquet' (FORMAT PARQUET)")
    con.close()
    return str(tmp_path)


@pytest.fixture
def prt(lake, monkeypatch):
    import routers.payroll as p
    monkeypatch.setattr(p, "_BASE", lake)
    monkeypatch.setattr(p, "_CACHE", {})
    monkeypatch.setattr(p, "_avail_cache", {"ts": 0.0, "val": None})
    return p


def test_summary_totals_and_avg_salary(prt):
    s = prt._query_summary()
    assert s["latest_year"] == 2025
    assert s["totals"]["gross"] == 3500.0            # 1000+500+2000 (FY2025 only)
    assert s["totals"]["overtime"] == 250.0
    assert s["totals"]["records"] == 35
    # weighted avg salary = (900000+1600000)/(10+20) across FY2025 salaried rows
    assert abs(s["totals"]["avg_salary"] - (2500000/30)) < 0.5
    assert {x["payroll_type"] for x in s["by_payroll_type"]} == {"SALARIED", "NON-SALARIED"}
    assert [y["year"] for y in s["by_year"]] == [2024, 2025]


def test_agencies_sorted_and_scoped_to_fy(prt):
    a = prt._query_agencies(None, "gross", "desc", 1, 50)
    assert a["fiscal_year"] == 2025 and a["total"] == 2
    assert a["data"][0]["agency"] == "Dept B" and a["data"][0]["gross"] == 2000.0
    # Dept B avg salary = 1600000/20 = 80000
    assert abs(a["data"][0]["avg_salary"] - 80000.0) < 0.5


def test_records_filter_and_perrow_avg(prt):
    r = prt._query_records(2025, None, "Dept A", None, "gross", "desc", 1, 25)
    assert r["total"] == 2
    tx = next(x for x in r["data"] if x["title"] == "TITLE X")
    assert tx["gross"] == 1000.0 and abs(tx["avg_salary"] - 90000.0) < 0.5  # 900000/10
    ty = next(x for x in r["data"] if x["title"] == "TITLE Y")
    assert ty["avg_salary"] == 0.0  # no reported salary


@pytest.mark.asyncio
async def test_endpoints_routable(client):
    for ep in ("/oce/payroll/summary", "/oce/payroll/agencies", "/oce/payroll/records"):
        resp = await client.get(ep)
        assert resp.status_code != 404, f"{ep} missing"
        assert "available" in resp.json()
