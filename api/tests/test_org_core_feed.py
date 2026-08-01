"""Guards for the derived org matching dictionary (Phase 2).

`GET /get/orgs/core` + `modules/orgcore.py` + `api/seed_org_core_aliases.py`.
The normalizer's `POST /core/orgs/refresh` delete-and-reloads the dictionary
from this feed, so a wrong emission here silently orphans manual match rows on
the next refresh — these tests pin every rule that protects them.
"""

import importlib
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'modules'))

import orgcore  # noqa: E402

seedmod = importlib.import_module("seed_org_core_aliases")


def org(id, name, alt=None, disp=None, type="City Agency",
        retired_at=None, merged_into=None):
    return {"id": id, "name": name, "alternate_name": alt,
            "display_name": disp, "type": type,
            "retired_at": retired_at, "merged_into": merged_into}


def as_map(feed):
    return {r["name"]: r["id"] for r in feed}


# ── one row per NAME VARIANT ─────────────────────────────────────────────────

def test_emits_every_name_variant_with_the_same_id():
    """⚠ THE BIG TRAP: one row per ORG would delete the alias entities on first
    refresh — five ids are deliberately claimed by two entities each
    (`NYC Cyber Command` + `Cyber Command` -> 170100033)."""
    feed, _ = orgcore.build_core_feed(
        [org(170100033, "NYC Cyber Command", alt="Cyber Command")], [])
    assert as_map(feed) == {"NYC Cyber Command": "170100033",
                            "Cyber Command": "170100033"}


def test_display_name_is_a_variant_too():
    feed, _ = orgcore.build_core_feed(
        [org(1, "Fire Department",
             disp="Fire Department of the City of New York")], [])
    assert as_map(feed) == {"Fire Department": "1",
                            "Fire Department of the City of New York": "1"}


def test_ids_are_strings_and_feed_is_sorted():
    """Today's hand-maintained core stores string ids; the stamped
    `wegov-org-id` must stay byte-identical across the switch. Sorted output
    makes refresh diffs stable."""
    feed, _ = orgcore.build_core_feed([org(2, "B"), org(1, "A")], [])
    assert [r["name"] for r in feed] == ["A", "B"]
    assert all(isinstance(r["id"], str) for r in feed)


def test_blank_and_duplicate_variants_collapse():
    feed, _ = orgcore.build_core_feed(
        [org(1, "Same Name", alt="  ", disp="Same Name")], [])
    assert as_map(feed) == {"Same Name": "1"}


# ── scaffolding exclusion ────────────────────────────────────────────────────

def test_classification_official_public_figure_are_excluded():
    """`District Attorneys` as a general match target would swallow the five
    real DA offices. Chart scaffolding stays out of the dictionary unless an
    alias row admits a specific name."""
    rows = [org(170020021, "District Attorneys", type="Classification"),
            org(170100017, "Chief of Staff", type="Official"),
            org(3, "Some Person", type="Public Figure"),
            org(4, "Real Agency")]
    feed, _ = orgcore.build_core_feed(rows, [])
    assert as_map(feed) == {"Real Agency": "4"}
    assert orgcore.EXCLUDED_TYPES == ("Classification", "Official", "Public Figure")


def test_alias_row_admits_a_match_referenced_scaffolding_name():
    """ds 1 maps payroll's `District Attorney` to the `District Attorneys`
    Classification node — the alias row is what keeps that resolving."""
    rows = [org(170020021, "District Attorneys", type="Classification")]
    feed, _ = orgcore.build_core_feed(
        rows, [{"name": "District Attorneys", "org_id": 170020021}])
    assert as_map(feed) == {"District Attorneys": "170020021"}


# ── retirement handling ──────────────────────────────────────────────────────

def test_retired_org_names_resolve_to_the_merged_into_successor():
    """The core deliberately holds `Commission on Gender Equality` ->
    170011004 (the surviving Gender Equity record); a live-orgs-only feed
    silently drops it on first refresh."""
    rows = [org(170011004, "Commission on Gender Equity"),
            org(170100011, "Commission on Gender Equality",
                retired_at="2026-07-30", merged_into=170011004)]
    feed, _ = orgcore.build_core_feed(rows, [])
    assert as_map(feed) == {"Commission on Gender Equity": "170011004",
                            "Commission on Gender Equality": "170011004"}


def test_retirement_chains_are_followed():
    rows = [org(3, "Survivor"),
            org(2, "Middle", retired_at="x", merged_into=3),
            org(1, "Oldest", retired_at="x", merged_into=2)]
    feed, _ = orgcore.build_core_feed(rows, [])
    assert as_map(feed)["Oldest"] == "3"


def test_retired_without_successor_is_reported_not_guessed():
    rows = [org(1, "Gone", retired_at="x", merged_into=None)]
    feed, rep = orgcore.build_core_feed(rows, [])
    assert feed == []
    assert rep["retired_unresolved"] == ["Gone"]


def test_alias_target_is_followed_through_retirement():
    """A later merge must not leave an alias stamping a retired id."""
    rows = [org(9, "New Home"),
            org(5, "Old Home", retired_at="x", merged_into=9)]
    feed, _ = orgcore.build_core_feed(rows, [{"name": "Hand Alias", "org_id": 5}])
    assert as_map(feed)["Hand Alias"] == "9"


# ── the collision policy ─────────────────────────────────────────────────────

def test_colliding_variant_is_omitted_without_an_alias():
    """⚠ `DC37` is an alternate_name shared by 19 distinct bargaining units.
    The core is keyed by name, so a naive feed would last-write-wins onto an
    arbitrary local and the auto-matcher would link every payroll `DC37` to
    it. No alias -> no emission, and the omission is REPORTED."""
    rows = [org(17001473, "Local 1549", alt="DC37"),
            org(17001475, "Local 372", alt="DC37")]
    feed, rep = orgcore.build_core_feed(rows, [])
    assert "DC37" not in as_map(feed)
    assert rep["collisions_omitted"] == [
        {"name": "DC37", "org_ids": [17001473, 17001475]}]


def test_alias_row_keeps_the_collision_incumbent():
    """`United Federation of Teachers` names both the union and bargaining
    units; the hand-maintained core resolved it to 17001498 and the alias row
    preserves that id verbatim — never re-rolled."""
    rows = [org(17001482, "Local 2", alt="United Federation of Teachers"),
            org(17001498, "UFT", alt="United Federation of Teachers")]
    feed, rep = orgcore.build_core_feed(
        rows, [{"name": "United Federation of Teachers", "org_id": 17001498}])
    assert as_map(feed)["United Federation of Teachers"] == "17001498"
    assert rep["collisions_omitted"] == []


def test_alias_wins_over_a_single_derived_id():
    """Alias rows are the curated layer; a register variant never overrides
    one. The disagreement is reported, not silently resolved."""
    rows = [org(1, "Agency", alt="Shared Key"), org(2, "Keeper")]
    feed, rep = orgcore.build_core_feed(
        rows, [{"name": "Shared Key", "org_id": 2}])
    assert as_map(feed)["Shared Key"] == "2"
    assert rep["alias_overrides"]


# ── id-less stubs ────────────────────────────────────────────────────────────

def test_null_alias_id_emits_an_empty_id_stub():
    """4 match-referenced stubs have no org to point at (`NYS Department of
    Public Service`...). They must stay in the dictionary — with an empty id,
    exactly like the hand-maintained stub — so their match rows keep
    resolving instead of orphaning."""
    feed, _ = orgcore.build_core_feed(
        [], [{"name": "NYS Department of Public Service", "org_id": None}])
    assert as_map(feed) == {"NYS Department of Public Service": ""}


# ── the seed ─────────────────────────────────────────────────────────────────

def test_seed_pins_the_measured_incumbents_and_stubs():
    """The 16 rows are a snapshot of human curation measured out of the live
    core on 2026-07-31. A re-measure that disagrees means the core changed —
    re-measure, do not just edit the test."""
    seed = {name: org_id for name, org_id, _ in seedmod.SEED}
    assert len(seed) == len(seedmod.SEED) == 16, "seed names must be unique"
    # the headline fix of the adoption: 12 datasets map this by hand
    assert seed["NYC Districting Commission"] == 170100330
    assert seed["District Attorneys"] == 170020021
    # the four collision incumbents, ids read from the live core
    assert seed["District Council 37, AFSCME"] == 17001496
    assert seed["Organization of Staff Analysts"] == 17001478
    assert seed["Service Employees' International Union, Local 1199"] == 17001480
    assert seed["United Federation of Teachers"] == 17001498
    # the four deliberate id-less stubs
    assert [n for n, i in seed.items() if i is None] == [
        "NYS Department of Public Service", "Upper Manhattan Empowerment Zone",
        "Pavers & Road Builders DC", "Industrial Business Zone Boundary Commission"]
    assert all(note for _, _, note in seedmod.SEED), "every alias must say why"


def test_seed_is_insert_only():
    """A re-run must never clobber a later human edit to the table."""
    import inspect
    src = inspect.getsource(seedmod.seed)
    assert "ON CONFLICT (name) DO NOTHING" in src
    assert "UPDATE" not in src and "DELETE" not in src


# ── the endpoint ─────────────────────────────────────────────────────────────

ORG_COLS = [{"column_name": c} for c in
            ("id", "name", "alternate_name", "display_name", "type",
             "retired_at", "merged_into")]


def _select_safe(rows_by_call):
    calls = {"n": 0}

    async def fake(sql, *a, **kw):
        out = rows_by_call[min(calls["n"], len(rows_by_call) - 1)]
        calls["n"] += 1
        return out
    return fake


@pytest.mark.asyncio
async def test_endpoint_returns_a_bare_json_list(client):
    """The consumer is the normalizer's `url:` source, which expects a bare
    list — NOT the {'rows': ...} wrapper every other endpoint uses. Wrapping
    it would make the refresh load a dictionary of two garbage entities."""
    fake = _select_safe([ORG_COLS,
                         [org(170010002, "Office of the Mayor")],
                         [{"name": "Hand Alias", "org_id": 170010002}]])
    with patch("main.PostgresModelAsync.select_safe", new=AsyncMock(side_effect=fake)):
        resp = await client.get("/get/orgs/core")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert {r["name"]: r["id"] for r in data} == {
        "Office of the Mayor": "170010002", "Hand Alias": "170010002"}


@pytest.mark.asyncio
async def test_endpoint_report_mode_returns_diagnostics(client):
    fake = _select_safe([ORG_COLS, [org(1, "A", alt="X"), org(2, "B", alt="X")], []])
    with patch("main.PostgresModelAsync.select_safe", new=AsyncMock(side_effect=fake)):
        resp = await client.get("/get/orgs/core?report=1")
    diag = resp.json()
    assert diag["count"] == 2       # A and B; X omitted as a collision
    assert diag["collisions_omitted"] == [{"name": "X", "org_ids": [1, 2]}]
