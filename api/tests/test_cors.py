"""Tests for CORS configuration.

Validates that the correct origins are allowed and that CORS headers
are present in responses from public endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch


ALLOWED_ORIGINS = [
    "https://databook.nyc",
    "http://databook.nyc",
    "https://databook.wegov.nyc",
]

DISALLOWED_ORIGINS = [
    "https://evil.example.com",
    "https://phishing-databook.nyc",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
async def test_cors_allows_known_origins(client, origin):
    """Requests from allowed origins should get CORS headers back."""
    with patch("main.select", new_callable=AsyncMock, return_value={"rows": []}):
        resp = await client.get(
            "/get/orgs/directory",
            headers={"Origin": origin},
        )

    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
async def test_cors_blocks_unknown_origins(client, origin):
    """Requests from unknown origins should NOT get CORS headers."""
    with patch("main.select", new_callable=AsyncMock, return_value={"rows": []}):
        resp = await client.get(
            "/get/orgs/directory",
            headers={"Origin": origin},
        )

    assert resp.status_code == 200
    # CORS middleware should not echo back an unknown origin.
    acao = resp.headers.get("access-control-allow-origin")
    assert acao is None or acao != origin
