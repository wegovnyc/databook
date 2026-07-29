"""Tests for the OCE (procurement) endpoints.

Route existence tests — verify the endpoints are mounted correctly.
They may return 500 in test when DB data is missing, but should never
return 404 (which would mean the route is not registered).
"""

import pytest


@pytest.mark.asyncio
async def test_oce_dashboard_stats_endpoint_exists(client):
    """GET /oce/dashboard/stats should be routable."""
    resp = await client.get("/oce/dashboard/stats")
    assert resp.status_code != 404, "OCE dashboard stats endpoint is missing"


@pytest.mark.asyncio
async def test_oce_vendors_endpoint_exists(client):
    """GET /oce/vendors should be routable."""
    resp = await client.get("/oce/vendors")
    assert resp.status_code != 404, "OCE vendors endpoint is missing"


@pytest.mark.asyncio
async def test_oce_contracts_endpoint_exists(client):
    """GET /oce/contracts should be routable."""
    resp = await client.get("/oce/contracts")
    assert resp.status_code != 404, "OCE contracts endpoint is missing"


def test_contract_spend_helpers():
    """Pure helpers behind the contract spend map (normalization + NYC fiscal year)."""
    from routers.oce import _normalize_contract_id, _fy_of
    # normalized_contract_id = alnum-uppercase (the #20 crosswalk key)
    assert _normalize_contract_id("CT1-071-20268804478") == "CT107120268804478"
    assert _normalize_contract_id("pon1069mmis0002026") == "PON1069MMIS0002026"
    assert _normalize_contract_id("") is None and _normalize_contract_id(None) is None
    # NYC fiscal year runs Jul 1–Jun 30, labelled by the end year
    assert _fy_of("2025-10-31") == 2026  # Oct 2025 -> FY2026
    assert _fy_of("2026-03-14") == 2026  # Mar 2026 -> FY2026
    assert _fy_of("2025-06-30") == 2025  # Jun 2025 -> FY2025
    assert _fy_of(None) is None


def test_get_spending_files_local_globs_years(tmp_path, monkeypatch):
    """Local mode derives the all_years set from on-disk fiscal_year=* dirs, so a
    newly-ingested FY (via scripts/oce-refresh.sh) is picked up with no code change.
    Per-FY and default-recent requests keep globbing a single directory."""
    from routers import oce
    for fy in (2024, 2025, 2026):
        (tmp_path / f"fiscal_year={fy}").mkdir()
    monkeypatch.setattr(oce, "SPENDING_DATA_BASE", str(tmp_path))
    assert oce._spending_base_is_local()
    assert oce._local_spending_years() == [2026, 2025, 2024]

    allf = oce.get_spending_files(all_years=True)
    assert "fiscal_year=2026/*.parquet" in allf
    assert "fiscal_year=2024/*.parquet" in allf

    # a brand-new FY dir is reflected immediately, no code edit
    (tmp_path / "fiscal_year=2027").mkdir()
    assert oce._local_spending_years()[0] == 2027
    assert "fiscal_year=2027/*.parquet" in oce.get_spending_files(all_years=True)

    # single-FY request unchanged (globs just that year's directory)
    assert oce.get_spending_files(fiscal_year=2026) == \
        f"['{tmp_path}/fiscal_year=2026/*.parquet']"


@pytest.mark.asyncio
async def test_oce_contracts_accepts_amount_filter(client):
    """The explorer's amount-range + expense-category (Phase D) filters should be accepted."""
    resp = await client.get("/oce/contracts", params={
        "min_amount": 1000, "max_amount": 5_000_000, "expense_category": "Contractual Services",
    })
    assert resp.status_code != 404 and resp.status_code != 422, resp.text[:200]


@pytest.mark.asyncio
async def test_oce_contracts_export_endpoint_exists(client):
    """GET /oce/contracts/export should be routable and CSV-typed on success."""
    resp = await client.get("/oce/contracts/export", params={"status": "Registered"})
    assert resp.status_code != 404, "OCE contracts/export endpoint is missing"
    assert resp.status_code != 422, f"export params rejected: {resp.text[:200]}"
    if resp.status_code == 200:
        assert "text/csv" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_oce_solicitations_endpoint_exists(client):
    """GET /oce/solicitations should be routable."""
    resp = await client.get("/oce/solicitations")
    assert resp.status_code != 404, "OCE solicitations endpoint is missing"


@pytest.mark.asyncio
async def test_oce_filter_options_endpoint_exists(client):
    """GET /oce/filter-options should be routable."""
    resp = await client.get("/oce/filter-options")
    assert resp.status_code != 404, "OCE filter-options endpoint is missing"


@pytest.mark.asyncio
async def test_oce_agencies_endpoint_exists(client):
    """GET /oce/agencies should be routable."""
    resp = await client.get("/oce/agencies")
    assert resp.status_code != 404, "OCE agencies endpoint is missing"


@pytest.mark.asyncio
async def test_oce_transactions_endpoint_exists(client):
    """GET /oce/transactions should be routable."""
    resp = await client.get("/oce/transactions")
    assert resp.status_code != 404, "OCE transactions endpoint is missing"


@pytest.mark.asyncio
async def test_oce_transactions_accepts_new_filters(client):
    """The explorer filters (category / amount / date) should be accepted, not 422."""
    resp = await client.get(
        "/oce/transactions",
        params={
            "fiscal_year": 2026, "spending_category": "Contracts",
            "expense_category": "Payroll Summary", "industry": "N/A",
            "sub_vendor": "Yes",
            "min_amount": 1000, "max_amount": 5_000_000,
            "date_from": "2025-07-01", "date_to": "2026-06-30",
            "sort": "date", "order": "asc",
        },
    )
    assert resp.status_code != 404, "transactions endpoint is missing"
    assert resp.status_code != 422, f"new filter params rejected: {resp.text[:200]}"


@pytest.mark.asyncio
async def test_oce_transactions_facets_endpoint_exists(client):
    """GET /oce/transactions/facets should be routable and accept contextual filters."""
    resp = await client.get("/oce/transactions/facets", params={
        "fiscal_year": 2026, "spending_category": "Payroll", "sub_vendor": "Yes",
    })
    assert resp.status_code != 404, "OCE transactions/facets endpoint is missing"
    assert resp.status_code != 422, f"facet filter params rejected: {resp.text[:200]}"


@pytest.mark.asyncio
async def test_oce_spending_top_endpoint_exists(client):
    """GET /oce/spending/top should be routable."""
    resp = await client.get("/oce/spending/top", params={"fiscal_year": 2026, "limit": 5})
    assert resp.status_code != 404, "OCE spending/top endpoint is missing"


@pytest.mark.asyncio
async def test_oce_spending_subvendors_endpoint_exists(client):
    """GET /oce/spending/subvendors (sub-vendor lens) should be routable."""
    resp = await client.get("/oce/spending/subvendors", params={"fiscal_year": 2026})
    assert resp.status_code != 404, "OCE spending/subvendors endpoint is missing"
    assert resp.status_code != 422, f"subvendors params rejected: {resp.text[:200]}"


@pytest.mark.asyncio
async def test_oce_spending_lenses_accept_agency(client):
    """The sub-vendor + M/WBE lenses must accept an `agency` scope (agency profile)."""
    for path in ("/oce/spending/subvendors", "/oce/spending/mwbe"):
        resp = await client.get(path, params={"agency": "DEPARTMENT OF EXAMPLE"})
        assert resp.status_code != 404, f"{path} is missing"
        assert resp.status_code != 422, f"{path} rejected agency param: {resp.text[:200]}"


@pytest.mark.asyncio
async def test_oce_transactions_export_endpoint_exists(client):
    """GET /oce/transactions/export should be routable and CSV-typed when it succeeds."""
    resp = await client.get("/oce/transactions/export", params={"fiscal_year": 2026})
    assert resp.status_code != 404, "OCE transactions/export endpoint is missing"
    assert resp.status_code != 422, f"export params rejected: {resp.text[:200]}"
    if resp.status_code == 200:
        assert "text/csv" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_oce_spending_mwbe_endpoint_exists(client):
    """GET /oce/spending/mwbe (M/WBE lens) should be routable."""
    resp = await client.get("/oce/spending/mwbe", params={"fiscal_year": 2026})
    assert resp.status_code != 404, "OCE spending/mwbe endpoint is missing"
    assert resp.status_code != 422, f"mwbe params rejected: {resp.text[:200]}"


@pytest.mark.asyncio
async def test_oce_transactions_accepts_mwbe_filters(client):
    """The M/WBE filters should be accepted (not 422) whether or not the columns
    are present yet — they're simply ignored until the v2 re-ingest lands."""
    resp = await client.get("/oce/transactions", params={
        "fiscal_year": 2026, "mwbe_category": "Women",
        "woman_owned": "Yes", "emerging": "No",
    })
    assert resp.status_code != 404
    assert resp.status_code != 422, f"M/WBE filter params rejected: {resp.text[:200]}"


# ---------------------------------------------------------------------------
# M/WBE schema-tolerance — the API must reference the v2 M/WBE columns ONLY when
# the Parquet actually has them, so it stays error-free before the re-ingest and
# lights up automatically after. These unit tests exercise that gate without S3.
# ---------------------------------------------------------------------------

def _set_schema(has_mwbe: bool):
    """Force the spending schema probe cache on/off for M/WBE."""
    from routers import oce
    base = set(oce._TRANSACTION_COLS) | {"fiscal_year"}
    cols = base | set(oce._MWBE_COLS) if has_mwbe else base
    oce._spending_schema_cache.update({"cols": cols, "ts": float("inf")})


def test_mwbe_filters_ignored_when_absent():
    """With no M/WBE columns, an M/WBE filter must NOT enter the WHERE clause
    (referencing a missing column would fail the whole Parquet query)."""
    from routers import oce
    _set_schema(has_mwbe=False)
    try:
        where, params = oce._spending_where({"mwbe_category": "Women", "woman_owned": "Yes"})
        assert "mwbe_category" not in where
        assert "woman_owned_business" not in where
        assert params == []
        assert oce._mwbe_enabled() is False
        assert oce._spending_source("[x]") == "read_parquet([x])"
    finally:
        oce._spending_schema_cache.update({"cols": None, "ts": 0.0})


def test_mwbe_filters_applied_when_present():
    """With M/WBE columns present, filters enter the WHERE (parametrized) and the
    read switches to union_by_name so mixed legacy/v2 chunks read cleanly."""
    from routers import oce
    _set_schema(has_mwbe=True)
    try:
        where, params = oce._spending_where(
            {"mwbe_category": "Women", "woman_owned": "Yes", "emerging": "No"}
        )
        assert "mwbe_category = ?" in where
        assert "woman_owned_business = ?" in where
        assert "emerging_business = ?" in where
        assert params == ["Women", "Yes", "No"]
        assert oce._mwbe_enabled() is True
        assert "union_by_name=true" in oce._spending_source("[x]")
    finally:
        oce._spending_schema_cache.update({"cols": None, "ts": 0.0})


def test_digital_reform_cache_is_bounded():
    """A scraper sending randomized query params (each a distinct cache key) must
    NOT grow the digital-reform cache without limit — that was the OOM root cause.
    _dr_cache_set enforces a hard cap with oldest-first (LRU) eviction."""
    from routers import oce
    oce._digital_reform_cache.clear()
    try:
        # 10x the cap in distinct keys, as a param-fuzzing scraper would produce.
        for i in range(oce.DIGITAL_REFORM_CACHE_MAX * 10):
            oce._dr_cache_set(f"key-{i}", {"i": i})
        assert len(oce._digital_reform_cache) == oce.DIGITAL_REFORM_CACHE_MAX
        assert oce._dr_cache_get("key-0") is None  # oldest evicted
        newest = oce.DIGITAL_REFORM_CACHE_MAX * 10 - 1
        assert oce._dr_cache_get(f"key-{newest}") == {"i": newest}  # newest kept
    finally:
        oce._digital_reform_cache.clear()


def test_digital_reform_cache_lru_and_ttl():
    """Reads refresh LRU recency (a touched key survives eviction); entries past
    the TTL read as None and are dropped."""
    from routers import oce
    import time as _t
    oce._digital_reform_cache.clear()
    try:
        for i in range(oce.DIGITAL_REFORM_CACHE_MAX):
            oce._dr_cache_set(f"k{i}", i)
        assert oce._dr_cache_get("k0") == 0        # touch -> most-recently-used
        oce._dr_cache_set("overflow", -1)          # forces one eviction
        assert oce._dr_cache_get("k0") == 0        # spared by the touch
        assert oce._dr_cache_get("k1") is None     # evicted instead
        # TTL expiry: a stale entry reads as None and is removed.
        oce._digital_reform_cache["stale"] = {
            "data": "x", "ts": _t.time() - oce.DIGITAL_REFORM_CACHE_TTL - 1,
        }
        assert oce._dr_cache_get("stale") is None
        assert "stale" not in oce._digital_reform_cache
    finally:
        oce._digital_reform_cache.clear()


# --- vendor profile enrichment (SBS + Checkbook actuals) ----------------------

@pytest.mark.asyncio
async def test_sbs_profile_shapes_jobs_and_handles_job1_naming(monkeypatch):
    """SBS enrichment: builds the past-performance list, tolerates the source's
    inconsistent job-1 value column (`Largest_Value_of_Contract`), and skips
    job slots with no client."""
    from unittest.mock import AsyncMock
    from modules.postgrex.asyncmodel import PostgresModelAsync
    from routers import oce
    row = {
        "Account_Number": "12345", "Vendor_Formal_Name": "ACME BUILDERS, INC.",
        "Vendor_DBA": "ACME", "Business_Description": "General construction",
        "Certification": "MBE", "Certification_Renewal_Date": "2027-03-01T00:00:00",
        "Website": "acme.example", "telephone": "2125550000",
        "Date_Of_Establishment": "1998-05-04T00:00:00", "Aggregate_Bonding_Limit": "5000000",
        "Signatory_To_Union_Contracts": "Yes", "NAICS_Title": "Commercial Building Construction",
        "NAICS_Sector": "Construction", "NAICS_Subsector": "Buildings",
        "ID6_digit_NAICS_code": "236220", "Types_of_Construction_Projects_Performed": "Schools",
        "Capacity_Building_Programs": "", "Enrolled_in_PASSPort": "Yes", "Borough": "Bronx",
        "City": "Bronx", "State": "NY",
        # job 1 present (note the oddly-named value column), job 2 blank, job 3 present
        "Name_of_Client_Job_Exp_1": "SCA", "Largest_Value_of_Contract": "2000000",
        "Date_of_Work_Job_Exp_1": "2023", "Description_of_Work_Job_Exp_1": "PS 1 roof",
        "Name_of_Client_Job_Exp_2": "  ", "Value_of_Contract_Job_Exp_2": "999",
        "Date_of_Work_Job_Exp_2": "", "Description_of_Work_Job_Exp_2": "",
        "Name_of_Client_Job_Exp_3": "DDC", "Value_of_Contract_Job_Exp_3": "750000",
        "Date_of_Work_Job_Exp_3": "2021", "Description_of_Work_Job_Exp_3": "Library",
    }
    monkeypatch.setattr(PostgresModelAsync, "select_safe", AsyncMock(return_value=[row]))
    out = await oce._sbs_profile("Acme Builders Inc")
    assert out["certification"] == "MBE"
    assert out["naics_title"] == "Commercial Building Construction"
    assert out["established"] == "1998-05-04"        # trimmed to a date
    assert out["certification_renewal"] == "2027-03-01"
    assert [j["client"] for j in out["jobs"]] == ["SCA", "DDC"]   # blank slot skipped
    assert out["jobs"][0]["value"] == "2000000"      # job-1 quirk column read
    assert out["jobs"][1]["value"] == "750000"


@pytest.mark.asyncio
async def test_sbs_profile_returns_none_when_absent(monkeypatch):
    """No SBS row (or a failing/missing table) yields None, never an exception."""
    from unittest.mock import AsyncMock
    from modules.postgrex.asyncmodel import PostgresModelAsync
    from routers import oce
    monkeypatch.setattr(PostgresModelAsync, "select_safe", AsyncMock(return_value=[]))
    assert await oce._sbs_profile("Nobody Ltd") is None
    monkeypatch.setattr(PostgresModelAsync, "select_safe",
                        AsyncMock(side_effect=Exception('relation "sbscertifiedbiz" does not exist')))
    assert await oce._sbs_profile("Nobody Ltd") is None
    assert await oce._sbs_profile("") is None        # empty name short-circuits


def test_add_contract_spend_exposes_payment_window():
    """first_payment/last_payment are attached (they were computed and dropped
    before) so the profile can show the real payment window vs the contract term."""
    from routers.oce import _add_contract_spend
    c = _add_contract_spend({"award_amount": "1000"}, {
        "spent_to_date": 250.0, "payment_count": 4,
        "first_payment": "2024-01-05", "last_payment": "2025-06-30"})
    assert c["spent_to_date"] == 250.0 and c["payment_count"] == 4
    assert c["first_payment"] == "2024-01-05" and c["last_payment"] == "2025-06-30"
    assert c["pct_used"] == 25.0
    # no spend row -> zeros, not None, and no pct for a $0 award
    c2 = _add_contract_spend({"award_amount": 0}, None)
    assert c2["spent_to_date"] == 0.0 and c2["pct_used"] is None
