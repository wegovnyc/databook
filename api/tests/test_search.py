"""Tests for the federated search router — grouped /get/search and the
navbar typeahead /get/search/suggest. The DB is mocked: select_safe returns
one canned row per table so we exercise shaping/interleaving, not Postgres.
"""
from unittest.mock import AsyncMock, patch

import pytest


def _fake_rows(sql, params):
    """Return one shaped row keyed by the table the query targets, so every
    per-type builder produces exactly one result."""
    s = sql.lower()
    if "wegov_orgs" in s:
        return [{"id": "170010214", "name": "Department of Health", "type": "City Agency"}]
    if "nyccivilservicetitles" in s:
        return [{"code": "1006C", "descr": "Health Services Manager", "minr": 1, "maxr": 2}]
    if "from contracts" in s:
        return [{"ctr_id": "5485382", "contract_id": "C1", "contract_title": "Health svc",
                 "vendor_name": "Acme", "agency": "DOH"}]
    if "from solicitations" in s:
        return [{"name": "Health RFP", "epin": "E1", "agency": "DOH", "status": "Open"}]
    if "schoollocations" in s:
        return [{"code": "M015", "name": "Health HS", "typ": "High school"}]
    if "capitalprojectslist" in s:
        return [{"maprojid": "HBX1086", "description": "Health Center", "magencyname": "DOH"}]
    if "crol" in s:
        return [{"rid": "99", "title": "Health Notice", "agency": "DOH", "typ": "Award"}]
    if "civillistactive" in s:  # people UNION
        return [{"fullname": "Jane Health", "org": "DOH", "dt": "2026", "tbl": "civillistactive"}]
    return []


@pytest.fixture
def mock_db():
    with patch("routers.search.PostgresModelAsync.select_safe",
               new_callable=AsyncMock) as m:
        m.side_effect = _fake_rows
        yield m


@pytest.mark.asyncio
async def test_grouped_search_returns_all_types(client, mock_db):
    r = await client.get("/get/search?q=health")
    assert r.status_code == 200
    data = r.json()
    assert data["query"] == "health"
    types = {g["type"] for g in data["groups"]}
    # All 8 federated types present (each builder returned a row).
    assert types == {"organizations", "people", "titles", "contracts",
                     "solicitations", "projects", "schools", "notices"}
    assert data["total"] == len(data["groups"])


@pytest.mark.asyncio
async def test_grouped_search_type_filter(client, mock_db):
    r = await client.get("/get/search?q=health&type=organizations")
    data = r.json()
    assert [g["type"] for g in data["groups"]] == ["organizations"]


@pytest.mark.asyncio
async def test_suggest_is_flat_and_navigable(client, mock_db):
    r = await client.get("/get/search/suggest?q=health")
    assert r.status_code == 200
    data = r.json()
    sugg = data["suggestions"]
    assert sugg, "expected suggestions"
    # Flat list, each tagged with a type + on-site URL.
    for s in sugg:
        assert s["url"].startswith("/")
        assert s["type"] and s["title"]
    # Typeahead excludes list-only / external types.
    assert {"solicitations", "notices"}.isdisjoint({s["type"] for s in sugg})
    # Capped at the dropdown limit.
    assert len(sugg) <= 8


@pytest.mark.asyncio
async def test_suggest_interleaves_types(client, mock_db):
    """First rows should span multiple types (round-robin), not dump one type."""
    r = await client.get("/get/search/suggest?q=health")
    sugg = r.json()["suggestions"]
    assert len({s["type"] for s in sugg[:4]}) > 1


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/get/search", "/get/search/suggest"])
async def test_short_query_returns_empty(client, mock_db, path):
    r = await client.get(path + "?q=h")
    data = r.json()
    assert data.get("groups", []) == [] and data.get("suggestions", []) == []
    mock_db.assert_not_called()  # too-short: no DB round-trips


# ---- durable search-index recreation (main.py) -------------------------------

def test_search_indexes_unique_and_well_formed():
    import main
    names = [n for n, _, _ in main.SEARCH_INDEXES]
    assert len(names) == len(set(names)), "duplicate index names"
    for _, _, body in main.SEARCH_INDEXES:
        assert body.startswith("gin ("), body
    # Every FTS index must use the exact to_tsvector('english', ...) form the
    # search.py queries use, or the planner won't pick it up.
    fts = [b for _, _, b in main.SEARCH_INDEXES if "to_tsvector" in b]
    assert fts and all("to_tsvector('english'," in b for b in fts)


@pytest.mark.asyncio
async def test_ensure_search_indexes_targets_only_its_table():
    import main

    calls = []

    class FakeDB:
        async def execute(self, sql):
            calls.append(sql)

    await main._ensure_search_indexes(FakeDB(), "crol")
    idx = [c for c in calls if "CREATE INDEX" in c]
    assert idx, "expected crol index creation"
    assert all('ON "crol"' in c for c in idx), "must only touch the given table"
    assert any("gin_trgm_ops" in c for c in idx) and any("to_tsvector" in c for c in idx)
    # A non-searchable table creates no indexes (still ensures pg_trgm only).
    calls.clear()
    await main._ensure_search_indexes(FakeDB(), "some_random_table")
    assert not [c for c in calls if "CREATE INDEX" in c]


@pytest.mark.asyncio
async def test_ensure_search_indexes_survives_a_failing_index():
    """One bad index (e.g. missing column) must not abort the import."""
    import main

    class FlakyDB:
        def __init__(self):
            self.n = 0

        async def execute(self, sql):
            self.n += 1
            if "CREATE INDEX" in sql and self.n % 2 == 0:
                raise Exception("boom")

    await main._ensure_search_indexes(FlakyDB(), "wegov_orgs")  # must not raise
