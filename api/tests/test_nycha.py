"""Tests for the NYCHA Budget & Revenue endpoints + converter domains.

Route tests verify the endpoints are mounted (never 404). With no Parquet
ingested they return the schema-tolerant `available: false` shape (200, not 500).
"""
import csv
import importlib.util
import os

import pytest


@pytest.mark.asyncio
async def test_nycha_budget_summary_routable(client):
    resp = await client.get("/oce/nycha/budget/summary")
    assert resp.status_code != 404, "NYCHA budget summary endpoint missing"
    # schema-tolerant: available flag present regardless of ingest state
    assert "available" in resp.json()


@pytest.mark.asyncio
async def test_nycha_budget_units_routable(client):
    resp = await client.get("/oce/nycha/budget/units")
    assert resp.status_code != 404, "NYCHA budget units endpoint missing"
    assert "available" in resp.json()


@pytest.mark.asyncio
async def test_nycha_revenue_summary_routable(client):
    resp = await client.get("/oce/nycha/revenue/summary")
    assert resp.status_code != 404, "NYCHA revenue summary endpoint missing"
    assert "available" in resp.json()


@pytest.mark.asyncio
async def test_nycha_revenue_sources_routable(client):
    resp = await client.get("/oce/nycha/revenue/sources")
    assert resp.status_code != 404, "NYCHA revenue sources endpoint missing"
    assert "available" in resp.json()


def _load_builder():
    path = os.path.join(os.path.dirname(__file__), "..", "build_budget_revenue_parquet.py")
    spec = importlib.util.spec_from_file_location("bbr", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_nycha_domains_registered():
    bbr = _load_builder()
    assert "nycha_budget" in bbr.DOMAINS
    assert "nycha_revenue" in bbr.DOMAINS
    assert bbr.DOMAINS["nycha_budget"]["year_col"] == "year"
    assert bbr.DOMAINS["nycha_revenue"]["year_col"] == "budget_fiscal_year"


def test_nycha_converter_builds_parquet(tmp_path):
    """The converter turns NYCHA extractor CSVs into typed Parquet (amounts->DOUBLE,
    year->INT), tolerating the NYCHA-specific column sets."""
    duckdb = pytest.importorskip("duckdb")
    bbr = _load_builder()

    # nycha_budget fixture
    bcsv = tmp_path / "nb_2024.csv"
    with open(bcsv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "budget_type", "budget_name", "expense_category",
                    "funding_source", "responsibility_center", "program", "project",
                    "adopted", "modified", "remaining", "committed", "encumbered",
                    "actual_amount"])
        w.writerow(["2024", "P.S.", "FRINGE", "ANNUITY", "FED", "RES EMP SVCS",
                    "No Program", "No Project", "100", "120", "20", "5", "10", "90"])
        w.writerow(["2024", "OTPS", "SUPPLIES", "MATERIALS", "CITY", "QUEENSBRIDGE",
                    "P1", "J1", "200", "250", "50", "0", "0", "210"])
    out_b = tmp_path / "nycha_budget"
    bbr.build("nycha_budget", [str(bcsv)], str(out_b))
    n, m, sp = duckdb.sql(
        f"SELECT count(*), sum(modified), sum(actual_amount) "
        f"FROM read_parquet('{out_b}/nycha_budget.parquet')"
    ).fetchone()
    assert n == 2 and m == 370.0 and sp == 300.0

    # nycha_revenue fixture
    rcsv = tmp_path / "nr_2024.csv"
    with open(rcsv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["budget_fiscal_year", "budget_name", "budget_type",
                    "closing_classification_name", "revenue_expense_category",
                    "funding_source", "program", "project", "responsibility_center",
                    "revenue_category", "revenue_class", "adopted", "modified",
                    "recognized", "remaining"])
        w.writerow(["2024", "FED SUBSIDIES", "OTHER REV", "COLLECTED", "SUBSIDY",
                    "SECTION 8", "FY2024", "No Project", "CMA", "FEDERAL SEC8",
                    "Fed Sec 8", "0", "0", "1604387951.71", "-1604387951.71"])
    out_r = tmp_path / "nycha_revenue"
    bbr.build("nycha_revenue", [str(rcsv)], str(out_r))
    n, rec = duckdb.sql(
        f"SELECT count(*), sum(recognized) "
        f"FROM read_parquet('{out_r}/nycha_revenue.parquet')"
    ).fetchone()
    assert n == 1 and abs(rec - 1604387951.71) < 1


@pytest.mark.asyncio
async def test_nycha_contracts_summary_routable(client):
    resp = await client.get("/oce/nycha/contracts/summary")
    assert resp.status_code != 404, "NYCHA contracts summary endpoint missing"
    assert "available" in resp.json()


@pytest.mark.asyncio
async def test_nycha_contracts_list_routable(client):
    resp = await client.get("/oce/nycha/contracts")
    assert resp.status_code != 404, "NYCHA contracts list endpoint missing"
    assert "available" in resp.json()


def test_nycha_contracts_domain_registered():
    bbr = _load_builder()
    assert "nycha_contracts" in bbr.DOMAINS
    assert bbr.DOMAINS["nycha_contracts"]["year_col"] == "fiscal_year"


def test_nycha_contracts_grain_collapses_multi_fy(tmp_path):
    """A contract appearing in several FY pulls (line/release rows) must collapse
    to ONE row per contract_id, with MAX() picking the constant contract amounts."""
    duckdb = pytest.importorskip("duckdb")
    bbr = _load_builder()
    from routers.nycha import _contracts_grain

    csv = tmp_path / "nc.csv"
    cols = ["fiscal_year", "contract_id", "vendor", "purpose", "location", "contract_type",
            "record_type", "purchase_order_type", "award_method", "industry", "funding_source",
            "responsibility_center", "pin", "program", "project", "expenditure_type",
            "grant_name", "start_date", "end_date", "approved_date", "number_of_releases",
            "contract_original_amount", "contract_current_amount", "contract_invoiced_amount"]
    import csv as _csv
    with open(csv, "w", newline="") as f:
        w = _csv.writer(f); w.writerow(cols)
        # contract C1 appears in FY2023 and FY2024 (2 line rows); C2 once
        base = {c: "" for c in cols}
        for fy in ("2023", "2024"):
            r = dict(base, fiscal_year=fy, contract_id="C1", vendor="ACME",
                     contract_current_amount="1000000", contract_invoiced_amount="400000",
                     number_of_releases="3")
            w.writerow([r[c] for c in cols])
        r = dict(base, fiscal_year="2024", contract_id="C2", vendor="BETA",
                 contract_current_amount="500000", contract_invoiced_amount="500000")
        w.writerow([r[c] for c in cols])

    out = tmp_path / "nycha_contracts"
    bbr.build("nycha_contracts", [str(csv)], str(out))
    p = f"{out}/nycha_contracts.parquet"
    grain = _contracts_grain(f"read_parquet('{p}')")
    got = dict((r[0], r) for r in duckdb.sql(
        f"SELECT contract_id, current_amt, invoiced, fiscal_year FROM ({grain})").fetchall())
    assert len(got) == 2, "C1's two FY rows must collapse to one contract"
    assert got["C1"][1] == 1000000.0 and got["C1"][2] == 400000.0
    assert got["C1"][3] == 2024  # MAX(fiscal_year)
    assert got["C2"][1] == 500000.0


@pytest.mark.asyncio
async def test_nycha_spending_summary_routable(client):
    resp = await client.get("/oce/nycha/spending/summary")
    assert resp.status_code != 404, "NYCHA spending summary endpoint missing"
    assert "available" in resp.json()


@pytest.mark.asyncio
async def test_nycha_spending_by_development_routable(client):
    resp = await client.get("/oce/nycha/spending/by-development")
    assert resp.status_code != 404, "NYCHA spending by-development endpoint missing"
    assert "available" in resp.json()
