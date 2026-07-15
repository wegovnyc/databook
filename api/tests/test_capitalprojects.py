"""Capital-project core endpoint: list-only fallback (the /p/ 404 fix)."""
import asyncpg
import pytest


@pytest.mark.asyncio
async def test_core_falls_back_to_list_when_no_dollarscomp(client, mock_select):
    """When the commitment-plan dollars table has no matching row, core returns
    the capitalprojectslist row tagged _source='list' (→ reduced page)."""
    def fake(sql, params=None):
        if 'capitalprojectsdollarscomp' in sql:
            return {'rows': []}
        if 'capitalprojectslist' in sql:
            assert "'list' AS _source" in sql
            return {'rows': [{'maprojid': '858DOIT5MYSM', 'description': 'X', '_source': 'list'}]}
        return {'rows': []}
    mock_select.side_effect = fake
    r = await client.get('/get/capitalprojects/core/858DOIT5MYSM')
    assert r.status_code == 200
    assert r.json()['rows'][0]['_source'] == 'list'


@pytest.mark.asyncio
async def test_core_prefers_dollarscomp_when_present(client, mock_select):
    """A real commitment-plan project is returned untagged (→ full page)."""
    def fake(sql, params=None):
        if 'capitalprojectsdollarscomp' in sql:
            return {'rows': [{'PROJECT_ID': 'DOIT5MYSM', 'PROJECT_DESCR': 'X'}]}
        raise AssertionError('should not reach list fallback')
    mock_select.side_effect = fake
    r = await client.get('/get/capitalprojects/core/DOIT5MYSM')
    assert r.status_code == 200
    assert r.json()['rows'][0].get('_source') is None


@pytest.mark.asyncio
async def test_commitments_matches_either_id_form(client, mock_select):
    """Commitments lookup must match maprojid OR projectid (callers pass either)."""
    captured = {}
    def fake(sql, params=None):
        captured['sql'] = sql
        return {'rows': []}
    mock_select.side_effect = fake
    await client.get('/get/capitalprojects/commitments/858DOIT5MYSM')
    assert '"projectid" = $1 OR "maprojid" = $1' in captured['sql']


@pytest.mark.asyncio
async def test_district_capitalprojects_missing_crosswalk_is_empty_not_500(client, mock_select):
    """nta has no capitalprojects_nta_idx crosswalk (2010↔2020 NTAs don't map).
    The endpoint must return empty rows, not 500 — was flooding Sentry."""
    mock_select.side_effect = asyncpg.exceptions.UndefinedTableError(
        'relation "capitalprojects_nta_idx" does not exist')
    r = await client.get('/get/districts/nta/MN0101/capitalprojects')
    assert r.status_code == 200
    assert r.json() == {"rows": []}


@pytest.mark.asyncio
async def test_district_capitalprojects_rejects_unsafe_type(client, mock_select):
    """`type` is interpolated into the table name — an unsafe value must be
    rejected before any query runs (injection guard)."""
    r = await client.get('/get/districts/cd;DROP/101/capitalprojects')
    assert r.status_code == 200
    assert r.json() == {"rows": []}
    mock_select.assert_not_called()


@pytest.mark.asyncio
async def test_district_capitalprojects_valid_type_uses_crosswalk(client, mock_select):
    """A valid type (cd) joins the matching crosswalk table."""
    captured = {}
    def fake(sql, params=None):
        captured['sql'] = sql
        return {'rows': [{'PROJECT_ID': 'X', 'DIST': '101'}]}
    mock_select.side_effect = fake
    r = await client.get('/get/districts/cd/101/capitalprojects')
    assert r.status_code == 200
    assert 'capitalprojects_cd_idx' in captured['sql']
