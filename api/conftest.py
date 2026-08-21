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

# modules.duckpool is deliberately NOT mocked. It is pure stdlib (a dedicated
# ThreadPoolExecutor for DuckDB work — see modules/duckpool.py) with no external
# state, and tests/test_duckpool.py asserts its real thread behaviour, which is what
# keeps blocking Parquet scans off the executor asyncpg needs for DNS. The "modules"
# MagicMock above would otherwise swallow the import.
import importlib.util as _ilu  # noqa: E402

_duckpool_spec = _ilu.spec_from_file_location(
    "modules.duckpool", os.path.join(_api_dir, "modules", "duckpool.py")
)
_duckpool = _ilu.module_from_spec(_duckpool_spec)
_duckpool_spec.loader.exec_module(_duckpool)
sys.modules.setdefault("modules.duckpool", _duckpool)
# ...and hang it off the mocked "modules" package too, so `from modules import
# duckpool` resolves to the real module instead of a MagicMock attribute.
_mock_autoload.duckpool = _duckpool

# modules.orgfilter is NOT mocked either, for the same reason: pure stdlib
# (logging only — see modules/orgfilter.py) and its real behaviour IS the thing
# under test. It decides whether `AND retired_at IS NULL` is appended to every
# org query; get that wrong and org search silently returns nothing instead of
# erroring, so a MagicMock standing in for it would hide the very bug the tests
# exist to catch.
_orgfilter_spec = _ilu.spec_from_file_location(
    "modules.orgfilter", os.path.join(_api_dir, "modules", "orgfilter.py")
)
_orgfilter = _ilu.module_from_spec(_orgfilter_spec)
_orgfilter_spec.loader.exec_module(_orgfilter)
sys.modules.setdefault("modules.orgfilter", _orgfilter)
_mock_autoload.orgfilter = _orgfilter

# modules.orgcore is NOT mocked either: pure stdlib (collections only) and its
# real behaviour is under test — it assembles the normalizer's matching
# dictionary, where a MagicMock would happily "emit" a feed that orphans 2,588
# manual match rows.
_orgcore_spec = _ilu.spec_from_file_location(
    "modules.orgcore", os.path.join(_api_dir, "modules", "orgcore.py")
)
_orgcore = _ilu.module_from_spec(_orgcore_spec)
_orgcore_spec.loader.exec_module(_orgcore)
sys.modules.setdefault("modules.orgcore", _orgcore)
_mock_autoload.orgcore = _orgcore

# modules.errfmt is NOT mocked either: pure stdlib and its real behaviour is
# exactly what is under test. It exists because `print(f"...error: {e}")` logged
# an EMPTY message for every timeout (str(TimeoutError()) == ''), so a MagicMock —
# whose str() is a cheerful non-empty repr — would make the empty-message bug
# untestable by papering over the one property that matters.
_errfmt_spec = _ilu.spec_from_file_location(
    "modules.errfmt", os.path.join(_api_dir, "modules", "errfmt.py")
)
_errfmt = _ilu.module_from_spec(_errfmt_spec)
_errfmt_spec.loader.exec_module(_errfmt)
sys.modules.setdefault("modules.errfmt", _errfmt)
_mock_autoload.errfmt = _errfmt

# ⚠ modules.apikey MUST NOT be mocked, and this is the strongest case of the
# three. It is pure stdlib (secrets + logging) and it decides AUTHENTICATION: a
# MagicMock's `.ok()` returns a truthy Mock, so every caller is authorised, and
# `require_editor` waves through an unauthenticated request. That is not a
# hypothetical — mocking it turned test_org_admin's
# `test_every_write_route_is_gated` green-adjacent (400 instead of 401, i.e. past
# auth and into validation) and made `test_a_reader_scope_may_not_edit` stop
# raising. A stub that FAILS OPEN in an auth test is worse than no test.
_apikey_spec = _ilu.spec_from_file_location(
    "modules.apikey", os.path.join(_api_dir, "modules", "apikey.py")
)
_apikey = _ilu.module_from_spec(_apikey_spec)
_apikey_spec.loader.exec_module(_apikey)
sys.modules.setdefault("modules.apikey", _apikey)
_mock_autoload.apikey = _apikey

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
