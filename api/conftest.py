"""Shared pytest fixtures for Databook API tests.

Uses httpx.AsyncClient with FastAPI's ASGI transport to test endpoints
without starting a real server or connecting to a database.

Strategy: We need to import main.py which has deep dependency chains
(postgrex -> config -> env.yaml, etc.). Rather than fighting those
imports, we install the API's dependencies and run from the api/ dir.
"""

import os
import sys
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure api/ is on sys.path so local modules resolve.
_api_dir = os.path.dirname(os.path.abspath(__file__))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

# Stub out problematic modules that require external state (database,
# config files) before any app code is imported.
# This lets us test routes without env.yaml or a running Postgres.

# Create a mock Config module
_mock_config = MagicMock()
_mock_config.Config.fastapi = {"key": "test-secret-key"}
_mock_config.Config.db = {
    "user": "test",
    "pwd": "test",
    "dbname": "test",
    "host": "localhost",
}
sys.modules.setdefault("config", _mock_config)

# Create mock User module
_mock_user_mod = MagicMock()
sys.modules.setdefault("user", _mock_user_mod)

# Create mock autoload
_mock_autoload = MagicMock()
sys.modules.setdefault("modules", _mock_autoload)
sys.modules.setdefault("modules.autoload", _mock_autoload)

# Create mock postgrex with async model
_mock_postgrex = MagicMock()
_mock_postgrex.PostgresModelAsync.connect = AsyncMock()
_mock_postgrex.PostgresModelAsync.disconnect = AsyncMock()
_mock_postgrex.PostgresModelAsync.select = AsyncMock(return_value={"rows": []})
_mock_postgrex.PostgresModelAsync.select_safe = AsyncMock(return_value=[{"c": 0}])
_mock_postgrex.CsvDataset = MagicMock()
sys.modules.setdefault("postgrex", _mock_postgrex)
sys.modules.setdefault("modules.postgrex", _mock_postgrex)
sys.modules.setdefault("modules.postgrex.asyncmodel", _mock_postgrex)

# Now import the app — all dependency chains are short-circuited.
from main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    """Yield an async HTTP client wired to the FastAPI app."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_select():
    """Patch PostgresModelAsync.select to return controlled data.

    Usage in tests:
        def test_example(mock_select):
            mock_select.return_value = {"rows": [{"id": 1}]}
    """
    with patch("main.select", new_callable=AsyncMock) as mocked:
        yield mocked
