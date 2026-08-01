"""Guards for the org parent FK (Phase 3).

`wegov_orgs.parent_org_id` replaces the `child_of` -> `airtable_id` STRING join.
These pin the behaviours that were bugs, plus the compatibility shim that lets
the same code serve a database on either side of the migration.
"""

import importlib
import os
import re
import sys

import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'modules'))

import orgfilter  # noqa: E402

parentfk = importlib.import_module("add_parent_org_id")


def _runner(has_column: bool):
    async def run(sql):
        return [{"ok": 1}] if has_column else []
    return run


# ── the probe + the two SQL shapes ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_parent_join_uses_the_fk_when_the_column_exists():
    orgfilter.reset_cache()
    sql = await orgfilter.parent_join(_runner(True))
    assert "p.id = org.parent_org_id" in sql
    assert "airtable_id" not in sql, "must not fall back once the FK exists"
    assert "child_of" not in sql
    orgfilter.reset_cache()


@pytest.mark.asyncio
async def test_parent_join_falls_back_to_the_legacy_string_join():
    """⚠ `wegov_orgs` has NO DDL in this repo (source_type='internal'), so a
    local or CI database may predate the column. Referencing it unconditionally
    would 500 every org profile — and in routers/search.py, which swallows
    exceptions, it would make a search group silently EMPTY instead."""
    orgfilter.reset_cache()
    sql = await orgfilter.parent_join(_runner(False))
    assert "airtable_id" in sql and "child_of" in sql
    assert "parent_org_id" not in sql
    orgfilter.reset_cache()


@pytest.mark.asyncio
async def test_parent_join_honours_table_aliases():
    orgfilter.reset_cache()
    sql = await orgfilter.parent_join(_runner(True), child="o", parent="par")
    assert "par.id = o.parent_org_id" in sql
    orgfilter.reset_cache()


@pytest.mark.asyncio
async def test_parent_id_projection_is_empty_once_the_fk_exists():
    """`SELECT org.*` already carries parent_org_id, so adding an alias would
    duplicate the key. Before the FK, the legacy join supplies it under the
    SAME name — the consumer must have exactly one code path."""
    orgfilter.reset_cache()
    assert await orgfilter.parent_id_projection(_runner(True)) == ("", "")
    orgfilter.reset_cache()
    sel, join = await orgfilter.parent_id_projection(_runner(False))
    assert "AS parent_org_id" in sel and "child_of" in join
    orgfilter.reset_cache()


@pytest.mark.asyncio
async def test_probe_failure_degrades_to_the_legacy_join():
    """A probe that raises must not take the org endpoints down with it."""
    orgfilter.reset_cache()

    async def boom(sql):
        raise RuntimeError("no such database")

    sql = await orgfilter.parent_join(boom)
    assert "airtable_id" in sql
    orgfilter.reset_cache()


# ── the readers that were BROKEN ─────────────────────────────────────────────

def test_no_source_file_reads_child_of_to_resolve_a_parent():
    """⚠ THE REGRESSION CLASS THIS EXISTS FOR.

    `child_of` is GONE (Phase 6) and nothing may resolve a parent through it —
    that is orgfilter's job, which is why the drop touched one file. The
    legacy fallback survives there for databases that predate the FK (and which
    therefore still have the column). The scan is for the banned pattern rather
    than for an approved list, because a test asserting `orgfilter` merely
    *contains* the right helper could not see a file that ignores it (which is
    exactly how the #177 agencies regression hid).

    Writers and the migration/provenance machinery are exempt by name.
    """
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    allowed = {
        # orgfilter owns the fallback; the two migration scripts read child_of in
        # order to migrate and then destroy it.
        "api/modules/orgfilter.py",
        "api/add_parent_org_id.py", "api/retire_airtable.py",
    }
    # a parent resolved by matching child_of against airtable_id
    rx = re.compile(r"airtable_id\s*=\s*regexp_replace\s*\(\s*\w*\.?child_of")
    offenders = []
    for sub in ("api", "app/app", "app/resources/views", "scripts"):
        base = os.path.normpath(os.path.join(root, sub))
        for dirpath, _dirs, files in os.walk(base):
            if any(p in dirpath for p in ("vendor", "node_modules", "__pycache__",
                                          os.sep + "tests")):
                continue
            for fn in files:
                if not fn.endswith((".py", ".php", ".sh")):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, root)
                if rel.replace(os.sep, "/") in allowed:
                    continue
                src = open(path, encoding="utf-8", errors="replace").read()
                if rx.search(src):
                    offenders.append(rel)
    assert not offenders, (
        "these resolve a parent through the legacy child_of string join instead "
        "of orgfilter.parent_join:\n  " + "\n  ".join(offenders))


def _sql_literals(path):
    """Every string literal in a module that looks like an org SQL query.

    ⚠ Parsed with `ast`, NOT grepped. A text scan of this file's own docstrings
    fires on the prose describing the banned pattern — the trap that is already
    documented for the org-type guard. Docstrings are skipped structurally, and
    the SQL lives in triple-quoted literals so they cannot simply be stripped.
    """
    import ast
    tree = ast.parse(open(path, encoding="utf-8").read())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            v = node.value
            if "SELECT" in v.upper() and "wegov_orgs" in v:
                out.append(v)
    return out


def test_mcp_org_tools_do_not_select_parent_name_off_the_table():
    """⚠ THE LIVE BUG PHASE 3 FIXED. Both MCP org tools selected `parent_name`
    straight off `wegov_orgs`, where it is a 0%-populated dead column shadowed
    by a computed alias of the same name in main.py's profile query. So the
    website showed a parent and the MCP tools reported none, for as long as they
    have existed. Measured 2026-07-31: get_organization_profile(170100340)
    returned no parent for `Office of Community Hiring`, whose parent is
    `Office of Workforce Development`."""
    path = os.path.join(os.path.dirname(__file__), '..', 'mcp_server.py')
    for sql in _sql_literals(path):
        if "parent_name" not in sql:
            continue
        assert "par.name AS parent_name" in sql, (
            "an org query reads parent_name without joining the parent row:\n"
            + sql)
    src = open(path, encoding="utf-8").read()
    assert "_parent_join()" in src, \
        "the org queries must resolve the parent via orgfilter"
    # ⚠ SECOND LAYER, found on prod after the query was fixed: the profile
    # SELECTed parent_name and its output template never printed it, so the
    # parent stayed invisible either way. Fixing the query alone was not enough.
    assert "- Part of:" in src, \
        "get_organization_profile must actually RENDER the parent it selects"
    assert src.count("- Part of:") >= 2, \
        "both org tools (search + profile) must render the parent"


def test_chatbot_does_not_render_child_of_as_the_parent():
    """It used to answer `**Parent**: ["recIXPDD84xmPdV2s"]` — an Airtable
    record id, JSON brackets and all."""
    src = open(os.path.join(os.path.dirname(__file__), '..', 'chatbot.py'),
               encoding="utf-8").read()
    assert "org.get('child_of'" not in src and 'org.get("child_of"' not in src
    assert "parent_name" in src


def test_org_chart_builder_keys_the_tree_by_org_id():
    """The PHP builder used to key `$mm` by `airtable_id` and parse the parent
    out of `child_of`. Keying by id is what makes an imported org referenceable
    without minting a synthetic `recOTI…` Airtable id."""
    src = open(os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'app',
                            'Custom', 'OrgChart.php'), encoding="utf-8").read()
    assert "$mm[$key]" in src, "the node map must be keyed by the org id"
    assert "parent_org_id" in src
    assert "json_decode" not in src, "no more JSON-wrapped Airtable parent ids"
    assert "$mm[$org['airtable_id']]" not in src


def test_the_superseded_chart_command_is_gone():
    """`chart:updatejson` wrote the static orgChart.json to a path inside the
    app container that nginx never served, was registered on no schedule, and
    resolved parents through child_of. App\\Custom\\OrgChart replaced it."""
    assert not os.path.exists(os.path.join(
        os.path.dirname(__file__), '..', '..', 'app', 'app', 'Console',
        'Commands', 'ChartUpdateJson.php'))


# ── the migration script ─────────────────────────────────────────────────────

def test_migration_is_two_steps_and_the_destructive_one_is_separate():
    """Adding the column is additive and safe before deploy; dropping the dead
    columns would 500 the OLD mcp_server.py, which selected parent_name off the
    table. So they must not share a flag."""
    import inspect
    assert parentfk.DEAD_COLUMNS == ("parent_id", "parent_name", "parent_type")
    src = inspect.getsource(parentfk)
    assert "--drop-dead-columns" in src
    drop = inspect.getsource(parentfk.drop_dead_columns)
    # it must refuse to drop a column that turns out to hold data
    assert "REFUSING to drop" in drop
    # and refuse to run before the replacement exists
    assert "parent_org_id" in drop


def test_migration_refuses_when_a_child_of_would_not_resolve():
    """The FK would reject those rows anyway; aborting first says WHICH,
    instead of surfacing as an opaque constraint violation."""
    import inspect
    src = inspect.getsource(parentfk.apply)
    assert "ABORT" in src
    assert "populated != resolvable" in src


def _no_comments(src: str) -> str:
    """Drop `#` comment lines. Same reason as the ast parsing above: without it
    this fires on the comment that EXPLAINS the banned pattern."""
    return "\n".join(ln for ln in src.split("\n")
                     if not ln.lstrip().startswith("#"))


def test_migration_declares_the_missing_primary_key():
    """⚠ `wegov_orgs` HAD NO PRIMARY KEY — zero rows in pg_constraint, and `id`
    was a nullable integer with only a plain non-unique index. Postgres refused
    the FK on the first prod apply: "there is no unique constraint matching
    given keys". So nothing ever prevented two orgs sharing an id. The migration
    declares PRIMARY KEY (id), but only after proving the data can carry one."""
    import inspect
    src = _no_comments(inspect.getsource(parentfk.apply))
    assert "ADD PRIMARY KEY (id)" in src
    # it must verify first, not force it
    assert "count(DISTINCT id)" in src and "id IS NULL" in src
    assert "ABORT: cannot add a primary key" in src


def test_migration_adds_a_real_foreign_key():
    """An FK is the whole point — it makes a dangling parent structurally
    impossible rather than something a weekly script asserts afterwards."""
    import inspect
    src = _no_comments(inspect.getsource(parentfk.apply))
    assert "REFERENCES wegov_orgs(id)" in src
    assert "NOT VALID" not in src, "validate immediately; the pre-flight proved it clean"


# ── the endpoint keeps its contract ──────────────────────────────────────────

ORG_ROW = {"rows": [{"id": 170100340, "name": "Office of Community Hiring",
                     "parent_id": 170100310, "parent_name": "Office of Workforce Development",
                     "parent_type": "Mayoral Office"}]}


@pytest.mark.asyncio
async def test_profile_still_exposes_parent_id_name_and_type(client):
    """⚠ These three alias names are load-bearing in sub/orgheader.blade.php:
    it renders $org['parent_name'], links via $org['parent_id'], and greys the
    label when $org['parent_type'] is Classification/Official. The TABLE columns
    of those names are dropped; the aliases must survive."""
    orgfilter.reset_cache()
    with patch("main.select", new_callable=AsyncMock, return_value=ORG_ROW):
        resp = await client.get("/get/orgs/profile/170100340")
    assert resp.status_code == 200
    row = resp.json()["rows"][0]
    assert row["parent_name"] == "Office of Workforce Development"
    assert row["parent_id"] == 170100310
    assert row["parent_type"] == "Mayoral Office"
    orgfilter.reset_cache()


# ── Phase 6: Airtable retired as an identity scheme ──────────────────────────

def test_no_writer_sets_child_of_any_more():
    """⚠ Phase 6 dropped `child_of`/`child_of_name`. A writer still setting them
    would raise UndefinedColumnError on prod — and the weekly refresh runs
    unattended, so it would fail on a schedule rather than in front of someone.

    Comments are stripped first: three guards in this session fired on the prose
    explaining the very pattern they ban.
    """
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    rx = re.compile(r"SET[^\"']*child_of|child_of\s*=\s*\$|INSERT[^)]*\bchild_of\b")
    offenders = []
    for sub in ("api", "app/app", "scripts"):
        base = os.path.normpath(os.path.join(root, sub))
        for dirpath, _dirs, files in os.walk(base):
            if any(p in dirpath for p in ("vendor", "node_modules", "__pycache__",
                                          os.sep + "tests")):
                continue
            for fn in files:
                if not fn.endswith((".py", ".php", ".sh")):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                # retire_airtable.py reads them to snapshot them; the Phase 1
                # backup table legitimately still HAS columns of that name.
                if rel in ("api/retire_airtable.py", "api/add_parent_org_id.py"):
                    continue
                src = "\n".join(
                    ln for ln in open(path, encoding="utf-8",
                                      errors="replace").read().split("\n")
                    if not ln.lstrip().startswith(("#", "--", "*", "//")))
                if rx.search(src):
                    offenders.append(rel)
    assert not offenders, (
        "these still WRITE child_of, which no longer exists:\n  "
        + "\n  ".join(offenders))


def test_phase6_snapshots_before_dropping():
    """`child_of` was Phase 3's rollback path and Phase 3 shipped hours, not a
    release, earlier. The provenance is preserved as a table rather than kept as
    a decaying duplicate writers must remember to update."""
    import importlib
    p6 = importlib.import_module("retire_airtable")
    src = _no_comments(inspect_source(p6))
    assert "wegov_orgs_airtable_provenance" in src
    assert "ON CONFLICT (id) DO NOTHING" in src, "a re-run must not overwrite it"
    # and it must refuse to drop if the snapshot came back short
    assert "refusing to drop" in src
    assert p6.DROP_COLUMNS == ("child_of", "child_of_name")


def test_phase6_gates_on_drift_and_the_fk():
    """A `child_of` that still knows something `parent_org_id` does not would be
    destroyed by the drop, so it is a hard gate, not a warning."""
    import importlib
    src = _no_comments(inspect_source(importlib.import_module("retire_airtable")))
    assert "wegov_orgs_parent_fk" in src and "contype='p'" in src
    assert "ABORT" in src
    assert "IS DISTINCT FROM p.id" in src


def inspect_source(mod):
    import inspect as _i
    return _i.getsource(mod)
