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


# ---- the eight district stat tiles ------------------------------------------
# Same crosswalk, same two hazards, and they never inherited the guard above:
# one nta district page raised eight UndefinedTableErrors (Sentry DATABOOK-API-P,
# 8 events in one second) because all eight tiles load per page view.

PSTATS = [
    'projects_no', 'orig_cost', 'curr_cost', 'over_budg_am',
    'long_no', 'over_budg_no', 'late_start_no', 'late_end_no',
]


@pytest.mark.parametrize('stat', PSTATS)
@pytest.mark.asyncio
async def test_district_pstats_missing_crosswalk_is_null_not_500(client, mock_select, stat):
    """nta has no capitalprojects_nta_idx crosswalk, so every tile must degrade.

    A single null `res` — NOT empty rows: the frontend reads
    `resp['data'][0]['res'] ?? '-'`, which renders `-` on a null and throws a
    TypeError on an empty array. It is also the shape a valid crosswalk with no
    matching rows already returns.
    """
    mock_select.side_effect = asyncpg.exceptions.UndefinedTableError(
        'relation "capitalprojects_nta_idx" does not exist')
    r = await client.get(f'/get/districts/pstats-{stat}/nta/MN0101/20210805')
    assert r.status_code == 200
    assert r.json() == {'rows': [{'res': None}]}


@pytest.mark.parametrize('stat', PSTATS)
@pytest.mark.asyncio
async def test_district_pstats_rejects_unsafe_type(client, mock_select, stat):
    """`type` is interpolated into the table name — reject before any query."""
    r = await client.get(f'/get/districts/pstats-{stat}/cd;DROP/101/20210805')
    assert r.status_code == 200
    assert r.json() == {'rows': [{'res': None}]}
    mock_select.assert_not_called()


@pytest.mark.parametrize('stat', PSTATS)
@pytest.mark.asyncio
async def test_district_pstats_valid_type_uses_crosswalk(client, mock_select, stat):
    """A valid type (cd) still reaches the matching crosswalk table."""
    captured = {}
    def fake(sql, params=None):
        captured['sql'] = sql
        return {'rows': [{'res': 7}]}
    mock_select.side_effect = fake
    r = await client.get(f'/get/districts/pstats-{stat}/cd/101/20210805')
    assert r.status_code == 200
    assert r.json() == {'rows': [{'res': 7}]}
    assert 'capitalprojects_cd_idx' in captured['sql']
    assert '{}' not in captured['sql']  # the template was actually formatted


def test_no_handler_interpolates_the_crosswalk_without_the_guard():
    """The crosswalk table name may only be built inside a guarding helper.

    Checks the direction that catches the handler nobody has written yet: a new
    stat endpoint that does `.format(type)` itself and calls bare `select()` is
    exactly how these eight drifted away from the list endpoint's guard. Written
    against the literal `capitalprojects_{}_idx` template — prose refers to it as
    `capitalprojects_<type>_idx` so this cannot fire on its own explanation.
    """
    import os
    main_py = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'main.py')
    with open(main_py) as fh:
        lines = fh.read().splitlines()

    interpolations = [
        ln for ln in lines
        if 'capitalprojects_{}_idx' in ln and not ln.strip().startswith('#')
    ]
    # Assert the scan looked: a guard that matches nothing passes vacuously.
    assert len(interpolations) >= 9, (
        f'expected the 8 stat tiles + the list endpoint, found {len(interpolations)}')
    for ln in interpolations:
        assert '_pstats_select(' in ln or '_district_select(' in ln, (
            f'crosswalk interpolated outside a guarding helper: {ln.strip()}')
