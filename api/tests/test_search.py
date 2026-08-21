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


# ---- durable search-index recreation (modules/searchindexes.py) --------------
# ⚠ THESE MOVED. They used to read `main.SEARCH_INDEXES` and call
# `main._ensure_search_indexes`, and they failed when the declarations moved into
# modules/searchindexes.py — correctly, because that IS the change. The list lived in
# main.py where only /import-csv could apply it, so `contracts` and `solicitations`
# (extractor path, DROP+RENAME) lost their indexes at every ingest: 5 of 19 were
# missing on prod. They are repointed here rather than deleted, because what they
# check — well-formed bodies, one table at a time, survives a failure — still matters.
# ⚠ Loaded BY PATH: conftest replaces the `modules` package with a MagicMock, so
# `from modules import searchindexes` inside a test yields a mock that satisfies
# almost any assertion.


def _searchindexes():
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "modules", "searchindexes.py")
    spec = importlib.util.spec_from_file_location("_si_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_search_indexes_unique_and_well_formed():
    si = _searchindexes()
    names = [n for n, _, _ in si.INDEXES]
    assert len(names) == len(set(names)), "duplicate index names"
    for _, _, body in si.INDEXES:
        assert body.startswith("gin ("), body
    # An FTS index must use the same text-search configuration as the queries
    # that read it, or the planner cannot use it — silently, with no error.
    #
    # ⚠ ONE index is deliberately `simple`, and the exception is named rather than
    # the rule relaxed: `idx_crol_body_fts` is read by
    # build_notice_product_links.py, which matches PRODUCT NAMES, and the english
    # snowball stemmer collapses brand names onto ordinary stems — `Feedly` stems
    # to 'feed' and matched 121 notices about data feeds, `Mobilize` to 'mobil'
    # and matched 2,388 saying "mobile". Everything else here is read by
    # routers/search.py, which searches PROSE and wants stemming.
    #
    # Listing the exception keeps this guard sharp: a NEW index that picks the
    # wrong configuration still fails, which a blanket "any config" would not.
    SIMPLE_BY_DESIGN = {"idx_crol_body_fts"}
    fts = [(n, b) for n, _, b in si.INDEXES if "to_tsvector" in b]
    assert fts, "no FTS indexes are declared at all"
    for name, body in fts:
        want = "simple" if name in SIMPLE_BY_DESIGN else "english"
        assert f"to_tsvector('{want}'," in body, (
            f"{name} should use the '{want}' configuration; body is {body}")
    # And the exception must still exist — if it is renamed away, this set goes
    # stale and silently stops guarding anything (the ALLOWED_NAME_JOINS lesson).
    assert SIMPLE_BY_DESIGN <= {n for n, _ in fts}, \
        f"stale entry in SIMPLE_BY_DESIGN: {SIMPLE_BY_DESIGN - {n for n, _ in fts}}"


@pytest.mark.asyncio
async def test_ensure_search_indexes_targets_only_its_table():
    si = _searchindexes()

    calls = []

    class FakeDB:
        async def execute(self, sql):
            calls.append(sql)

    await si.ensure(FakeDB(), "crol")
    idx = [c for c in calls if "CREATE INDEX" in c]
    assert idx, "expected crol index creation"
    assert all('ON "crol"' in c for c in idx), "must only touch the given table"
    assert any("gin_trgm_ops" in c for c in idx) and any("to_tsvector" in c for c in idx)
    # A non-searchable table creates no indexes — and does not even ensure pg_trgm,
    # because it returns before touching the connection.
    calls.clear()
    await si.ensure(FakeDB(), "some_random_table")
    assert not [c for c in calls if "CREATE INDEX" in c]


@pytest.mark.asyncio
async def test_ensure_search_indexes_survives_a_failing_index():
    """One bad index (e.g. missing column) must not abort the import — but it must
    be reported, or a missing index is invisible for months (which is what happened)."""
    si = _searchindexes()
    logged = []

    class FlakyDB:
        def __init__(self):
            self.n = 0

        async def execute(self, sql):
            self.n += 1
            if "CREATE INDEX" in sql and self.n % 2 == 0:
                raise Exception("boom")

    made = await si.ensure(FlakyDB(), "wegov_orgs", log=logged.append)  # must not raise
    assert made < len(si.for_table("wegov_orgs")), "the failures were not counted"
    assert logged and any("wegov_orgs" in m for m in logged), \
        "a failing index must name itself in the log"


@pytest.mark.asyncio
async def test_nycha_vendors_group_links(client, mock_db, monkeypatch):
    """NYCHA vendor search: matched → City profile, unmatched → NYCHA-native profile."""
    def fake(term, limit=8):
        return [
            {"vendor": "ADAMS EUROPEAN CONTRACTING INC.", "contracts": 10, "current": 1.0, "vendor_id": None},
            {"vendor": "MICROSOFT CORP", "contracts": 2, "current": 2.0, "vendor_id": "1632138"},
        ]
    monkeypatch.setattr("routers.nycha.search_vendors", fake)
    r = await client.get("/get/search?q=contract&type=nycha_vendors")
    grp = [g for g in r.json()["groups"] if g["type"] == "nycha_vendors"]
    assert grp, "nycha_vendors group missing"
    res = grp[0]["results"]
    adams = next(x for x in res if x["title"].startswith("ADAMS"))
    assert "/procurement-nycha-vendor?name=" in adams["url"] and "ADAMS" in adams["url"]
    assert "10 contracts" in adams["meta"]
    ms = next(x for x in res if x["title"].startswith("MICROSOFT"))
    assert ms["url"] == "/procurement/vendor/1632138"
