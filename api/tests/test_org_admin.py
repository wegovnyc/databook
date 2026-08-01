"""Guards for the org register's editing surface (Phase 5, API half).

The endpoints are where the invariants live — they must hold for a screen, a
curl and a bulk script alike — so these tests are the actual deliverable
alongside the router. Every invariant here comes from a real failure in this
codebase's history.
"""

import os
import sys

import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'modules'))

from routers import org_admin  # noqa: E402


EDITOR = {"id": 1, "email": "devin", "scope": "full"}

ORG = {"id": 170100340, "name": "Office of Community Hiring", "type": "Division",
       "display_name": None, "parent_org_id": 170100310, "retired_at": None,
       "merged_into": None, "in_org_chart": None, "alternate_name": None}


def _editor(monkeypatch=None):
    """Patch the auth dependency — auth itself is tested separately."""
    return patch.object(org_admin, "require_editor",
                        new=AsyncMock(return_value=EDITOR))


# ── auth ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_every_write_route_is_gated(client):
    """⚠ THE PHASE 0 LESSON. The normalizer's write endpoints had no auth of any
    kind — no Depends(), no middleware, no nginx gate — and that was the highest
    risk-per-effort item in the whole plan. These endpoints mutate the register
    that feeds the matching dictionary, the org chart and 3,700 match rows."""
    for method, path in (("post", "/admin/orgs"),
                         ("patch", "/admin/orgs/1"),
                         ("post", "/admin/orgs/1/retire"),
                         ("post", "/admin/orgs/1/unretire"),
                         ("get", "/admin/orgs/1"),
                         ("get", "/admin/orgs/vocabulary"),
                         ("delete", "/admin/orgs/1")):
        kw = {"json": {}} if method in ("post", "patch") else {}
        resp = await getattr(client, method)(path, **kw)
        assert resp.status_code in (401, 403), \
            f"{method.upper()} {path} answered {resp.status_code} unauthenticated"


@pytest.mark.asyncio
async def test_a_reader_scope_may_not_edit():
    """Authorising on the USER ROW's scope, not the token's — /login mints
    scopes=['read'] hardcoded, so a write-scoped dependency could never be
    satisfied by any token it issues."""
    from fastapi import HTTPException

    class Req:
        query_params = {}
        headers = {"Authorization": "Bearer t"}

    fake_mgr = type("M", (), {
        "get_current_user": AsyncMock(return_value={"id": 2, "email": "ro",
                                                    "scope": "read"})})()
    with patch.dict("sys.modules", {"main": type("m", (), {"manager": fake_mgr})}):
        with pytest.raises(HTTPException) as exc:
            await org_admin.require_editor(Req())
    assert exc.value.status_code == 403
    assert "read" in str(exc.value.detail)


def test_editor_scopes_are_explicit():
    assert org_admin.EDITOR_SCOPES == ("full", "write", "admin")
    assert "read" not in org_admin.EDITOR_SCOPES


# ── invariant 1: the type vocabulary ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_type_outside_the_vocabulary_is_rejected(client):
    """⚠ Free-text `type` is exactly how a mixed vocabulary silently broke four
    filters (#173) and rendered 28 of 270 agencies (#177). `orgfilter` owns the
    list; a value outside it makes rows vanish with no error."""
    with _editor(), \
         patch.object(org_admin, "_extra_types", new=AsyncMock(return_value=())), \
         patch.object(org_admin, "_one", new=AsyncMock(return_value=None)):
        resp = await client.post("/admin/orgs",
                                 json={"name": "X", "type": "Made Up Type"})
    assert resp.status_code == 400
    assert "orgfilter" in resp.text


@pytest.mark.asyncio
async def test_types_present_in_the_data_stay_selectable(client):
    """The register holds ~930 rows OTI does not cover (Unions, Political Clubs,
    BIDs…). A validator that rejects the data it is editing is worse than none —
    you could not save an existing row without retyping it."""
    with _editor(), \
         patch.object(org_admin, "_extra_types",
                      new=AsyncMock(return_value=("Union", "Political Club"))):
        resp = await client.get("/admin/orgs/vocabulary")
    assert resp.status_code == 200
    types = resp.json()["types"]
    assert "Union" in types and "Political Club" in types
    # and the canonical vocabulary is still reported separately
    assert "Mayoral Office" in resp.json()["canonical"]


# ── invariant 2: name is a join key ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_renaming_name_requires_explicit_confirmation(client):
    """⚠ `name` is a JOIN KEY: oce.py::_resolve_org_id matches contracts.agency
    against it by UPPER(TRIM()) equality. Renaming `Fire Department` silently
    zeroes that profile's procurement figures. The 409 must SAY so and quote the
    blast radius."""
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(return_value=dict(ORG))), \
         patch.object(org_admin, "_rename_impact",
                      new=AsyncMock(return_value={"contracts_matching_name": 412})):
        resp = await client.patch("/admin/orgs/170100340",
                                  json={"name": "A Different Name"})
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["impact"]["contracts_matching_name"] == 412
    assert "display_name" in body["why"], "must point the user at the safe field"
    assert "JOIN KEY" in body["why"]


@pytest.mark.asyncio
async def test_confirmed_rename_proceeds_and_warns(client):
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(return_value=dict(ORG))), \
         patch.object(org_admin, "_rename_impact",
                      new=AsyncMock(return_value={"contracts_matching_name": 7})), \
         patch.object(org_admin, "_audit", new=AsyncMock()), \
         patch("routers.org_admin.PostgresModelAsync.execute", new=AsyncMock()):
        resp = await client.patch("/admin/orgs/170100340",
                                 json={"name": "New Name", "confirm_rename": True})
    assert resp.status_code == 200
    assert resp.json()["changed"] == {"name": "New Name"}
    assert any("stop matching" in w for w in resp.json()["warnings"])


@pytest.mark.asyncio
async def test_display_name_needs_no_confirmation(client):
    """The whole point of display_name: show NYC's official name without
    touching the join key."""
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(return_value=dict(ORG))), \
         patch.object(org_admin, "_audit", new=AsyncMock()), \
         patch("routers.org_admin.PostgresModelAsync.execute", new=AsyncMock()):
        resp = await client.patch("/admin/orgs/170100340",
                                  json={"display_name": "Official Long Name"})
    assert resp.status_code == 200
    assert resp.json()["changed"] == {"display_name": "Official Long Name"}


@pytest.mark.asyncio
async def test_empty_name_is_rejected(client):
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(return_value=dict(ORG))):
        resp = await client.patch("/admin/orgs/170100340", json={"name": "   "})
    assert resp.status_code == 400
    assert "join key" in resp.text


# ── invariant 3: no parent cycles ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_self_parenting_is_rejected(client):
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(return_value=dict(ORG))):
        resp = await client.patch("/admin/orgs/170100340",
                                  json={"parent_org_id": 170100340})
    assert resp.status_code == 400
    assert "own parent" in resp.text


@pytest.mark.asyncio
async def test_a_parent_cycle_is_rejected(client):
    """⚠ Not cosmetic: OrgChart::packnode recurses through children with NO depth
    guard, so a cycle blows the stack and 500s the entire chart page."""
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(side_effect=[
             dict(ORG),                                    # current
             {"id": 999, "name": "Parent", "retired_at": None},   # parent exists
         ])), \
         patch.object(org_admin, "_would_cycle",
                      new=AsyncMock(return_value=[999, 170100340])):
        resp = await client.patch("/admin/orgs/170100340",
                                  json={"parent_org_id": 999})
    assert resp.status_code == 400
    assert "cycle" in resp.text


@pytest.mark.asyncio
async def test_would_cycle_detects_a_loop_and_terminates():
    """The walk must terminate even if the data already contains a loop
    elsewhere — otherwise the validator itself hangs."""
    chain = {1: 2, 2: 3, 3: 1}          # a pre-existing loop not involving 42

    async def fake_one(sql, params=()):
        return {"parent_org_id": chain.get(params[0])}

    with patch.object(org_admin, "_one", new=AsyncMock(side_effect=fake_one)):
        assert await org_admin._would_cycle(42, 1) is None      # terminates
        assert await org_admin._would_cycle(3, 1) == [1, 2, 3]  # real cycle found


@pytest.mark.asyncio
async def test_a_retired_org_cannot_be_a_parent(client):
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(side_effect=[
             dict(ORG),
             {"id": 999, "name": "Gone", "retired_at": "2026-07-30"},
         ])):
        resp = await client.patch("/admin/orgs/170100340",
                                  json={"parent_org_id": 999})
    assert resp.status_code == 400
    assert "retired" in resp.text


# ── invariant 4: retirement, never deletion ──────────────────────────────────

@pytest.mark.asyncio
async def test_delete_is_refused_with_an_explanation(client):
    """A DELETE would orphan 3,700 match rows and every ingested wegov-org-id —
    silently, because those are string references the database does not police."""
    with _editor():
        resp = await client.delete("/admin/orgs/170100340")
    assert resp.status_code == 405
    body = resp.json()
    assert "retired, not deleted" in body["error"]
    assert "/retire" in body["use"]


@pytest.mark.asyncio
async def test_retire_requires_a_successor(client):
    """`merged_into` is mandatory: match rows and ingested ids pointing here must
    keep resolving to something."""
    with _editor(), \
         patch.object(org_admin, "_one",
                      new=AsyncMock(return_value={"id": 1, "name": "X",
                                                  "retired_at": None})):
        resp = await client.post("/admin/orgs/1/retire", json={})
    assert resp.status_code == 400
    assert "merged_into is required" in resp.text


@pytest.mark.asyncio
async def test_retire_warns_about_orphaned_children(client):
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(side_effect=[
             {"id": 1, "name": "Parent", "retired_at": None},
             {"id": 2, "name": "Successor", "retired_at": None},
         ])), \
         patch.object(org_admin, "_audit", new=AsyncMock()), \
         patch("routers.org_admin.PostgresModelAsync.select_safe",
               new=AsyncMock(return_value=[{"id": 9, "name": "Kid"}])), \
         patch("routers.org_admin.PostgresModelAsync.execute", new=AsyncMock()):
        resp = await client.post("/admin/orgs/1/retire", json={"merged_into": 2})
    assert resp.status_code == 200
    assert any("parent" in w for w in resp.json()["warnings"])


@pytest.mark.asyncio
async def test_cannot_merge_into_a_retired_org(client):
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(side_effect=[
             {"id": 1, "name": "X", "retired_at": None},
             {"id": 2, "name": "AlsoGone", "retired_at": "2026-01-01"},
         ])):
        resp = await client.post("/admin/orgs/1/retire", json={"merged_into": 2})
    assert resp.status_code == 400
    assert "itself retired" in resp.text


def test_unretire_exists_so_reversibility_is_real():
    """Retirement is only safe because it is reversible; reversibility is only
    real if it is reachable."""
    paths = {r.path for r in org_admin.router.routes}
    assert "/admin/orgs/{org_id}/unretire" in paths


# ── invariant 5: unknown fields are rejected, not ignored ────────────────────

@pytest.mark.asyncio
async def test_unknown_fields_are_rejected(client):
    """Silently dropping an unrecognised field is how this codebase repeatedly
    shipped a change that 'succeeded' and did nothing."""
    with _editor(), \
         patch.object(org_admin, "_one", new=AsyncMock(return_value=dict(ORG))):
        resp = await client.patch("/admin/orgs/170100340",
                                  json={"nmae": "typo", "retired_at": "now"})
    assert resp.status_code == 400
    assert "unknown field" in resp.text
    # retirement must not be reachable as a plain field update
    assert "retired_at" in resp.text


def test_retirement_columns_are_not_directly_editable():
    for f in ("retired_at", "merged_into", "id", "airtable_id"):
        assert f not in org_admin.EDITABLE_FIELDS, \
            f"{f} must not be settable via PATCH"


# ── the id and the audit trail ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_may_not_choose_the_id(client):
    """`id` is the register's primary key (declared in Phase 3) and the value
    ingested data references."""
    with _editor():
        resp = await client.post("/admin/orgs",
                                 json={"id": 5, "name": "X", "type": "Division"})
    assert resp.status_code == 400
    assert "assigned by the server" in resp.text


@pytest.mark.asyncio
async def test_create_assigns_the_next_id_in_the_1701_series(client):
    calls = {}

    async def fake_one(sql, params=()):
        if "MAX(id)" in sql:
            # ⚠ The query MUST bound the series at both ends. The register holds
            # legacy ids far above it (811254850 New York City Fire Museum), so
            # `WHERE id >= MIN` mints 811254851 — measured on prod by creating
            # one. This mock previously hid that by returning the series max
            # regardless of the predicate.
            assert "BETWEEN" in sql, \
                "id series must be bounded at BOTH ends, not just >= MIN"
            return {"m": 170100390}
        return None                                  # no duplicate name

    async def fake_exec(sql, params=None):
        calls["sql"], calls["params"] = sql, params

    with _editor(), \
         patch.object(org_admin, "_extra_types", new=AsyncMock(return_value=())), \
         patch.object(org_admin, "_one", new=AsyncMock(side_effect=fake_one)), \
         patch.object(org_admin, "_audit", new=AsyncMock()), \
         patch("routers.org_admin.PostgresModelAsync.execute",
               new=AsyncMock(side_effect=fake_exec)):
        resp = await client.post("/admin/orgs",
                                 json={"name": "New Body", "type": "Division"})
    assert resp.status_code == 200
    assert resp.json()["id"] == 170100391
    assert org_admin.ID_SERIES_MIN == 170100000
    assert org_admin.ID_SERIES_MAX == 170199999
    # ⚠ Phase 6: NO synthetic airtable_id. One existed only so `child_of` could
    # address a new org, and the parent is parent_org_id now. Minting one would
    # falsely claim Airtable provenance for a row that never came from there.
    assert "airtable_id" not in calls["sql"]
    assert not any(str(v).startswith("rec") for v in calls["params"])


@pytest.mark.asyncio
async def test_every_mutation_is_audited(client):
    """No store in this system has ever had an audit trail."""
    seen = []

    async def fake_audit(org_id, action, actor, **kw):
        seen.append((org_id, action, actor["email"], kw.get("field")))

    with _editor(), \
         patch.object(org_admin, "_extra_types", new=AsyncMock(return_value=())), \
         patch.object(org_admin, "_one", new=AsyncMock(return_value=dict(ORG))), \
         patch.object(org_admin, "_audit", new=AsyncMock(side_effect=fake_audit)), \
         patch("routers.org_admin.PostgresModelAsync.execute", new=AsyncMock()):
        await client.patch("/admin/orgs/170100340", json={"type": "Mayoral Office"})
    assert seen == [(170100340, "update", "devin", "type")]


@pytest.mark.asyncio
async def test_a_no_op_update_says_so_rather_than_claiming_success(client):
    """Reporting 'updated' when nothing changed is the same class of lie as a
    check that never ran."""
    with _editor(), \
         patch.object(org_admin, "_extra_types", new=AsyncMock(return_value=())), \
         patch.object(org_admin, "_one", new=AsyncMock(return_value=dict(ORG))), \
         patch.object(org_admin, "_audit", new=AsyncMock()):
        resp = await client.patch("/admin/orgs/170100340",
                                  json={"type": "Division"})   # already Division
    assert resp.status_code == 200
    assert resp.json()["changed"] == {}
    assert "no field differed" in resp.json()["note"]


# ── the rename impact mirrors the real join ──────────────────────────────────

def test_rename_impact_mirrors_the_oce_resolution_sql():
    """The number quoted to the human must be the number that would stop
    matching, so the predicate has to be the one oce.py actually uses."""
    import inspect
    src = inspect.getsource(org_admin._rename_impact)
    assert "UPPER(TRIM(agency))" in src and "UPPER(TRIM($1))" in src
    oce = open(os.path.join(os.path.dirname(__file__), '..', 'routers', 'oce.py'),
               encoding="utf-8").read()
    assert "UPPER(TRIM(name)) = UPPER(TRIM($1))" in oce, \
        "oce.py's resolution changed — _rename_impact must follow it"


# ── the UI's origin gate ─────────────────────────────────────────────────────

def test_the_admin_ui_path_is_gated_at_the_origin():
    """⚠ THE ONLY THING AUTHENTICATING /admin/orgs IN THE BROWSER.

    The Laravel app has no user system, so the editing UI is gated by nginx basic
    auth on /admin/ — the Phase 0 control, at the origin, because task dda13bf3
    records that the origin answers direct connections and a Cloudflare-layer
    policy is therefore bypassable.

    Delete that block and the UI becomes an unauthenticated write surface onto
    the register — the exact exposure Phase 0 found on the normalizer. So it is
    pinned here rather than trusted to survive an nginx edit.
    """
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    conf = open(os.path.join(root, 'nginx', 'conf.d', 'ssl.conf'),
                encoding="utf-8").read()
    assert "location /admin/" in conf, "the /admin/ location block is gone"
    block = conf.split("location /admin/", 1)[1].split("location /", 1)[0]
    assert "auth_basic" in block, "/admin/ is no longer behind basic auth"
    assert "auth_basic_user_file" in block, "no htpasswd is configured for /admin/"
    # and the credential must live outside the tracked tree
    assert "/etc/letsencrypt/" in block


def test_the_ui_never_puts_the_api_credential_in_a_page():
    """The API credential is a long-lived write-scoped bearer token in the app's
    .env. Rendering it into a page would publish it to anyone with devtools, so
    the browser posts to Laravel and Laravel calls the API."""
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    views = os.path.join(root, 'app', 'resources', 'views', 'admin', 'orgs')
    for fn in os.listdir(views):
        src = open(os.path.join(views, fn), encoding="utf-8").read()
        assert "fapi_key" not in src, f"{fn} leaks the API credential"
        assert "X-Api-Key" not in src, f"{fn} leaks an API key header"
        # and it must not call the API host directly
        assert "api.databook.nyc" not in src, f"{fn} bypasses the server-side proxy"
