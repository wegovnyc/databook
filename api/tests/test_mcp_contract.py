"""Contract tests for the MCP server.

The MCP server runs as a separate Docker service (port 8082) and is
NOT mounted on the main FastAPI app. These tests verify critical
routes on the main API that the MCP server depends on.
"""

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_main_app_has_health_endpoint(client):
    """The main API should always have /health, which MCP deps also rely on."""
    with patch("main.select", new_callable=AsyncMock) as mock_sel:
        mock_sel.return_value = {"rows": [{"ok": 1}]}
        resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_oce_router_is_mounted(client):
    """The OCE router should be mounted at /oce prefix."""
    resp = await client.get("/oce/dashboard/stats")
    # 200 or 500 (missing DuckDB) — but NOT 404 (unmounted).
    assert resp.status_code != 404, "OCE router is not mounted"


@pytest.mark.asyncio
async def test_public_notices_endpoint(client):
    """GET /get/notices/frontnews — public endpoint that MCP uses."""
    with patch("main.select", new_callable=AsyncMock) as mock_sel:
        mock_sel.return_value = {"rows": []}
        resp = await client.get("/get/notices/frontnews")
    assert resp.status_code == 200
