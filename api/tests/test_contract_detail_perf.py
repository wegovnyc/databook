"""Guards the contract-detail query shape (api/routers/oce.py).

`/oce/contract/{id}` took 1.7-9.2s for any contract with payments (one 21.5s
outlier) because `_query_contract_detail` filtered on
`regexp_replace(upper(contract_id), ...) = ?`. A predicate that wraps the
column in a function cannot use Parquet row-group statistics, so DuckDB decoded
and re-normalized every row of every scanned fiscal-year partition. Measured on
prod 2026-07-27: 8.69s -> 0.79s by filtering the raw column and materializing
one scan instead of two.

That regression is invisible — the endpoint keeps returning correct data, just
slowly — so these tests build a small Parquet lake and pin the behaviour that
makes it fast, plus the correctness caveat that makes it safe.
"""

import os

import duckdb
import pytest

from routers import oce


@pytest.fixture
def lake(tmp_path, monkeypatch):
    """A two-fiscal-year Parquet lake shaped like the spending lake."""
    con = duckdb.connect()
    rows = [
        # (contract_id, issue_date, check_amount, payee, sub_vendor, prime, fy)
        ("CT100120241425458", "2023-08-15", 100.0, "ACME CORP", "No", "N/A", 2024),
        ("CT100120241425458", "2023-09-20", 250.0, "ACME CORP", "No", "N/A", 2024),
        ("CT100120241425458", "2024-09-10", 400.0, "SUBCO LLC", "Yes", "ACME CORP", 2025),
        # A different contract that must never leak into the rollup.
        ("CT999920241425458", "2024-09-11", 999.0, "OTHER INC", "No", "N/A", 2025),
        # A dashed raw id — the 0.05% case that plain equality would miss.
        ("PON1126MJH10-01", "2024-10-01", 77.0, "MUSEUM", "No", "N/A", 2025),
    ]
    for fy in (2024, 2025):
        d = tmp_path / f"fiscal_year={fy}"
        d.mkdir()
        vals = ", ".join(
            "('%s', '%s', %s, '%s', '%s', '%s')" % r[:6] for r in rows if r[6] == fy)
        con.execute(
            f"COPY (SELECT * FROM (VALUES {vals}) "
            f"AS t(contract_id, issue_date, check_amount, payee_name, sub_vendor, "
            f"associated_prime_vendor)) TO '{d}/chunk_0001.parquet' (FORMAT PARQUET)")
    con.close()

    monkeypatch.setattr(oce, "SPENDING_DATA_BASE", str(tmp_path))
    monkeypatch.setattr(oce, "_persistent_spending_connection", duckdb.connect)
    return tmp_path


def test_rolls_up_only_the_requested_contract(lake):
    d = oce._query_contract_detail("CT100120241425458", "2023-08-15", "2024-09-10")
    assert d["timeline"]["labels"] == ["2023-08", "2023-09", "2024-09"]
    assert d["timeline"]["values"] == [100.0, 250.0, 400.0]
    payees = {v["payee"]: v for v in d["vendors"]}
    assert set(payees) == {"ACME CORP", "SUBCO LLC"}, "another contract leaked in"
    assert payees["ACME CORP"]["spent"] == 350.0
    assert payees["ACME CORP"]["payments"] == 2
    assert payees["SUBCO LLC"]["is_sub_vendor"] is True
    assert payees["SUBCO LLC"]["prime_vendor"] == "ACME CORP"
    # 'N/A' is the source's null marker and must not be shown as a prime vendor.
    assert payees["ACME CORP"]["prime_vendor"] is None


def test_raw_variants_are_included_in_the_filter(lake):
    """Dashed raw ids only match when passed as variants — the safety valve.

    `_query_contract_spend_map` collects these per contract. If that plumbing is
    ever dropped, the fast path would silently under-report those payments.
    """
    norm = "PON1126MJH1001"
    without = oce._query_contract_detail(norm, "2024-10-01", "2024-10-01")
    assert without["timeline"]["labels"] == [], \
        "normalized id should not match the dashed raw id on its own"

    with_variant = oce._query_contract_detail(
        norm, "2024-10-01", "2024-10-01", ["PON1126MJH10-01"])
    assert with_variant["timeline"]["values"] == [77.0]
    assert with_variant["vendors"][0]["payee"] == "MUSEUM"


def test_scans_only_the_contracts_fiscal_years(lake, monkeypatch):
    """FY pruning must survive: a one-FY contract must not open both years."""
    seen = []
    real = oce.get_spending_files

    def spy(fiscal_year=None, all_years=False):
        seen.append(fiscal_year if fiscal_year else ("all" if all_years else "recent"))
        return real(fiscal_year=fiscal_year, all_years=all_years)

    monkeypatch.setattr(oce, "get_spending_files", spy)
    oce._query_contract_detail("CT999920241425458", "2024-09-11", "2024-09-11")
    assert seen == [2025], f"expected only FY2025 to be scanned, got {seen}"
    assert "all" not in seen, "fell back to an all-years scan"


def test_predicate_does_not_wrap_the_contract_id_column(lake, monkeypatch):
    """The actual performance invariant: filter the RAW column.

    Wrapping contract_id in regexp_replace/upper defeats Parquet row-group
    pruning and is what made this endpoint take up to 9.2s. Correctness tests
    above would still pass if someone reintroduced it, so pin the SQL shape.
    """
    captured = []

    class Spy:
        """Records SQL. `.cursor()` returns the spy so the real code path
        (`_persistent_spending_connection().cursor()`) stays observed."""

        def __init__(self, inner):
            self._inner = inner

        def cursor(self):
            return self

        def execute(self, sql, params=None):
            captured.append(sql)
            return self._inner.execute(sql, params) if params else self._inner.execute(sql)

        def close(self):
            pass  # the underlying connection is reused across the assertions

        def __getattr__(self, name):
            return getattr(self._inner, name)

    monkeypatch.setattr(oce, "_persistent_spending_connection",
                        lambda: Spy(duckdb.connect()))
    oce._query_contract_detail("CT100120241425458", "2023-08-15", "2024-09-10")

    assert captured, "no SQL captured — the spy was bypassed"
    sql = " ".join(captured).lower()
    # Isolate the filter on the parquet scan: everything after the last
    # read_parquet(...) up to the closing paren of the CTE.
    predicate = sql.split("read_parquet", 1)[1].split("where", 1)[1][:120]
    assert "regexp_replace" not in predicate and "upper(contract_id" not in predicate, (
        f"contract_id is wrapped in a function again ({predicate!r}) — this "
        f"disables Parquet row-group pruning and makes the endpoint many times slower")
    assert "contract_id in (" in predicate, f"unexpected predicate: {predicate!r}"

    # One materialized scan feeding both aggregates, not two scans.
    assert sql.count("read_parquet") == 1, "reverted to scanning the lake twice"
    assert "materialized" in sql
