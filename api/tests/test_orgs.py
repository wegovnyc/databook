"""Tests for the Organizations endpoints.

Validates public org endpoints (directory, all, profile) return correct
response structure without requiring authentication.
"""

import pytest
from unittest.mock import AsyncMock, patch


MOCK_ORGS = {
    "rows": [
        {"id": 170010040, "name": "Department of Education", "type": "City Agency"},
        {"id": 170020040, "name": "Department of Health", "type": "City Agency"},
    ]
}


@pytest.mark.asyncio
async def test_orgs_directory_returns_rows(client):
    """GET /get/orgs/directory should return rows without auth."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ORGS):
        resp = await client.get("/get/orgs/directory")

    assert resp.status_code == 200
    data = resp.json()
    assert "rows" in data
    assert len(data["rows"]) == 2
    assert data["rows"][0]["name"] == "Department of Education"


@pytest.mark.asyncio
async def test_orgs_all_returns_rows(client):
    """GET /get/orgs/all should return rows without auth."""
    with patch("main.select", new_callable=AsyncMock, return_value=MOCK_ORGS):
        resp = await client.get("/get/orgs/all")

    assert resp.status_code == 200
    data = resp.json()
    assert "rows" in data
    assert len(data["rows"]) >= 1


@pytest.mark.asyncio
async def test_orgs_profile_returns_single_org(client):
    """GET /get/orgs/profile/{id} should return profile data."""
    mock_profile = {
        "rows": [
            {
                "id": 170010040,
                "name": "Department of Education",
                "parent_id": None,
                "parent_name": None,
            }
        ]
    }
    with patch("main.select", new_callable=AsyncMock, return_value=mock_profile):
        resp = await client.get("/get/orgs/profile/170010040")

    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"][0]["id"] == 170010040
