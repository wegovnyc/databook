"""Tests for the /health endpoint.

Validates the health check returns correct structure and degrades
gracefully when Postgres is unreachable.
"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_health_returns_ok_when_db_healthy(client):
    """Health check should return status=ok when Postgres is reachable."""
    mock_rows = {"rows": [{"ok": 1}]}
    mock_tables = {"rows": [{"cnt": 42}]}

    with patch("main.select", new_callable=AsyncMock) as mock_sel:
        mock_sel.side_effect = [mock_rows, mock_tables]
        resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "checks" in data
    assert data["checks"]["postgres"] == "ok"
    assert data["checks"]["tables"] == 42


@pytest.mark.asyncio
async def test_health_returns_degraded_when_db_fails(client):
    """Health check should return status=degraded when Postgres is down."""
    with patch("main.select", new_callable=AsyncMock) as mock_sel:
        mock_sel.side_effect = Exception("connection refused")
        resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert "fail" in data["checks"]["postgres"]
