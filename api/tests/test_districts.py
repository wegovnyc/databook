"""Tests for the District subdataset endpoint.

Validates the generic /get/districts/{type}/{id}/{tbl} endpoint returns
correct results using the DISTRICT_COLUMNS mapping for 4 tables:
councilstatcases, nyccouncildiscretionaryfunding, budgetrequestsregister,
and facilitydb.
"""

import pytest
from unittest.mock import AsyncMock, patch


MOCK_ROWS = {
    "rows": [
        {"id": 1, "name": "Test Facility", "cd": "101"},
        {"id": 2, "name": "Test Facility 2", "cd": "101"},
    ]
}


@pytest.mark.asyncio
async def test_district_facilitydb_cd(client):
    """GET /get/districts/cd/101/facilitydb should filter on 'cd' column."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get("/get/districts/cd/101/facilitydb")

    assert resp.status_code == 200
    # Verify the SQL used the correct column from DISTRICT_COLUMNS
    sql = mock_sel.call_args[0][0]
    assert '"cd"' in sql
    assert "facilitydb" in sql


@pytest.mark.asyncio
async def test_district_facilitydb_cc(client):
    """GET /get/districts/cc/1/facilitydb should filter on 'council' column."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get("/get/districts/cc/1/facilitydb")

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert '"council"' in sql


@pytest.mark.asyncio
async def test_district_facilitydb_nta(client):
    """GET /get/districts/nta/BK09/facilitydb should filter on 'nta2020' column."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get("/get/districts/nta/BK09/facilitydb")

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert '"nta2020"' in sql


@pytest.mark.asyncio
async def test_district_councilstatcases_cd(client):
    """GET /get/districts/cd/101/councilstatcases should filter on 'COMMUNITY_BOARD'."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get("/get/districts/cd/101/councilstatcases")

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert '"Community Board"' in sql


@pytest.mark.asyncio
async def test_district_councilstatcases_cc(client):
    """GET /get/districts/cc/1/councilstatcases should filter on 'COUNCIL_DIST'."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get("/get/districts/cc/1/councilstatcases")

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert '"Council District"' in sql


@pytest.mark.asyncio
async def test_district_budgetrequestsregister_cc(client):
    """GET /get/districts/cc/1/budgetrequestsregister should use typo'd column name."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get("/get/districts/cc/1/budgetrequestsregister")

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert '"Council District"' in sql


@pytest.mark.asyncio
async def test_district_nyccouncildiscretionaryfunding_cd(client):
    """GET /get/districts/cd/101/nyccouncildiscretionaryfunding should filter on 'Community Board'."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get("/get/districts/cd/101/nyccouncildiscretionaryfunding")

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert '"Community Board"' in sql


@pytest.mark.asyncio
async def test_district_fallback_to_f_param(client):
    """Tables not in DISTRICT_COLUMNS should fall back to the `f` query param."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get(
            "/get/districts/cd/101/sometable",
            params={"f": "my_column", "sort": "col1,col2"}
        )

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert '"my_column"' in sql


@pytest.mark.asyncio
async def test_district_no_mapping_no_f_returns_error(client):
    """Tables not in DISTRICT_COLUMNS and no `f` should return empty rows with error."""
    resp = await client.get("/get/districts/cd/101/unknowntable")

    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"] == []
    assert "error" in data


@pytest.mark.asyncio
async def test_district_with_sort(client):
    """Sort param should generate ORDER BY clause."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get(
            "/get/districts/cd/101/facilitydb",
            params={"sort": "facname,facdomain"}
        )

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert "ORDER BY" in sql
    assert "facname" in sql


@pytest.mark.asyncio
async def test_district_without_sort(client):
    """No sort param should omit ORDER BY clause."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get("/get/districts/cd/101/facilitydb")

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert "ORDER BY" not in sql


@pytest.mark.asyncio
async def test_district_with_limit(client):
    """Limit param should generate LIMIT clause."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get(
            "/get/districts/cd/101/facilitydb",
            params={"limit": 50}
        )

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert "LIMIT 50" in sql


@pytest.mark.asyncio
async def test_district_with_limit_and_offset(client):
    """Limit + offset should generate both clauses."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get(
            "/get/districts/cd/101/facilitydb",
            params={"limit": 10, "offset": 20}
        )

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert "LIMIT 10" in sql
    assert "OFFSET 20" in sql


@pytest.mark.asyncio
async def test_district_without_limit(client):
    """No limit param should omit LIMIT clause (backward compat)."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ROWS) as mock_sel:
        resp = await client.get("/get/districts/cd/101/facilitydb")

    assert resp.status_code == 200
    sql = mock_sel.call_args[0][0]
    assert "LIMIT" not in sql
