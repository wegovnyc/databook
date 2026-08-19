"""Guards for the global-search GIN indexes.

The defect these exist to prevent has already happened once: the declarations lived
in a `.sql` script and in a literal list inside `main.py` that only `/import-csv`
applied, while `contracts` and `solicitations` are loaded by the EXTRACTOR path,
which drops and renames their tables. Measured on prod 2026-08-13 — **5 of the 19
declared search indexes did not exist**, all 5 on those two tables, and contract
search was a sequential scan of all 55,806 rows.

The three ways it can silently come back:

1. a second copy of the declarations appears (a list in a router, a new .sql), so the
   two drift and nobody can tell which is live,
2. a table carrying search indexes has no post-ingest hook, so nothing reapplies them
   after its ingest drops the table,
3. a search query gains an OR branch with no index — which does not merely leave that
   branch slow, it makes Postgres abandon the BitmapOr and seq-scan through ALL the
   other indexes (measured: 393.9ms with three of four branches indexed, 1.8ms with
   four).

⚠ modules/ is a MagicMock under conftest.py, so the module is loaded BY PATH.
"""
import importlib.util
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
MAIN = os.path.join(ROOT, 'api/main.py')
SCHEDULER = os.path.join(ROOT, 'api/data_scheduler.py')
SEARCH_ROUTER = os.path.join(ROOT, 'api/routers/search.py')


def _load():
    spec = importlib.util.spec_from_file_location(
        '_searchindexes', os.path.join(ROOT, 'api/modules/searchindexes.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(src):
    """Python comments, so a guard does not fire on its own explanation."""
    src = re.sub(r'(?s)""".*?"""', '', src)
    return re.sub(r'(?m)#[^\n]*$', '', src)


# ------------------------------------------------- 1. one owner, no second copy


def test_the_declarations_live_in_exactly_one_module():
    """⚠ Two copies is the original defect. `main.py` held a literal list that only
    /import-csv applied; the scheduler could not see it, so the extractor tables lost
    their indexes silently."""
    si = _load()
    assert len(si.INDEXES) > 15, "the declaration list looks truncated"
    main = _strip_comments(_read(MAIN))
    # ⚠ Scoped to EACH call site. `'searchindexes.ensure(' in main` was satisfied by
    # the people-index caller alone, so deleting the /import-csv delegation left this
    # green — one loose substring covering two independent seams.
    wrapper = main[main.index('async def _ensure_search_indexes'):]
    wrapper = wrapper[:wrapper.index('@app.')]
    assert 'searchindexes.ensure(' in wrapper, \
        "the /import-csv path no longer delegates to the shared module"
    # ⚠ Startup used to call `searchindexes.ensure` directly; it now goes through
    # `recreate_table_indexes`, which applies BOTH index families from their
    # declarations. That seam is asserted by test_main_declares_no_indexes_of_its_own,
    # so this guard stays on the /import-csv wrapper only.
    # No file outside the module may hold its own gin_trgm_ops list.
    for path in (MAIN, SCHEDULER, SEARCH_ROUTER):
        body = _strip_comments(_read(path))
        assert 'gin_trgm_ops' not in body, \
            f"{os.path.basename(path)} declares its own trigram indexes again"
    # ⚠ The .sql scripts stay (they are how a brand-new database is bootstrapped),
    # but they must not be the only home for anything.
    sql = os.path.join(ROOT, 'scripts/search_indexes.sql')
    if os.path.exists(sql):
        declared = set(re.findall(r'CREATE INDEX[^;]*?IF NOT EXISTS\s+(\w+)', _read(sql)))
        known = {n for n, _, _ in si.INDEXES}
        # Anything the script declares on a pipeline-loaded table must also be in
        # the module, or it dies at the next ingest with nothing to restore it.
        missing = {n for n in declared if n.startswith(('idx_contracts', 'idx_solic', 'idx_crol'))} - known
        assert not missing, f"declared only in the .sql script, so not durable: {missing}"


# --------------------------------------------- 2. every table has a hook


def test_every_table_with_search_indexes_gets_a_post_ingest_hook():
    """⚠ THE ACTUAL BUG. The registration loop iterated TABLE_INDEXES only, so
    `contracts` and `solicitations` — which carry search indexes and no btree ones —
    had no hook at all, and nothing recreated their GIN indexes after the extractor
    dropped their tables."""
    src = _read(SCHEDULER)
    assert 'set(TABLE_INDEXES) | searchindexes.tables()' in src, \
        "hook registration no longer covers the tables that only have search indexes"
    # And the hook body must actually apply them.
    body = src[src.index('async def recreate_table_indexes'):]
    body = body[:body.index('\n# ')]
    assert 'searchindexes.ensure(' in body, \
        "recreate_table_indexes no longer applies the search indexes"
    assert 'if not indexes and not search:' in body, \
        "the early return ignores search-only tables again"


def test_the_index_hook_still_runs_before_the_enrichment_hooks():
    """`vendors` carries enrichment hooks that query the table by name; the index
    rebuild must precede them. insert(0), never append."""
    src = _read(SCHEDULER)
    assert 'POST_INGEST_HOOKS[_tbl].insert(' in src and '.append(' not in \
        src[src.index('for _tbl in sorted(set(TABLE_INDEXES)'):][:400], \
        "the index hook is no longer inserted at the front"


def test_analyze_follows_index_creation():
    """A freshly renamed table has no statistics, and the planner ignores a brand-new
    index while it thinks the table is empty — so the hook can print ✓ while every
    lookup still seq-scans."""
    src = _read(SCHEDULER)
    body = src[src.index('async def recreate_table_indexes'):]
    body = body[:body.index('\n# ')]
    # ⚠ Match the STATEMENT, not the word. The first draft asserted `'ANALYZE' in
    # body` and passed with the statement deleted, because the ✓ print line beside
    # it also says ANALYZE — a guard reading its own log text.
    assert re.search(r'execute\(\s*f?[\'"]ANALYZE', body), \
        "ANALYZE is no longer EXECUTED after index creation"


# ------------------------------------- 3. every OR branch in a search is indexed


def test_every_column_a_search_query_filters_has_an_index():
    """⚠⚠ THE NON-OBVIOUS ONE. Postgres can only build a BitmapOr when EVERY branch
    of the OR is indexable. `contract_id ILIKE` had no index, so the planner ignored
    the three that existed and seq-scanned: 393.9ms. With all four, 1.8ms.

    So an unindexed branch does not cost you that branch — it costs you the whole
    query. This walks the real search functions and checks each ILIKE'd column.
    """
    si = _load()
    src = _read(SEARCH_ROUTER)
    by_table = {}
    for name, tbl, body in si.INDEXES:
        by_table.setdefault(tbl, []).append(body)

    checked = 0
    for fn, table in (('_contracts', 'contracts'), ('_solicitations', 'solicitations')):
        m = re.search(r'async def %s\(.*?(?=\nasync def |\Z)' % fn, src, re.S)
        assert m, f"{fn}() is gone -- the guard cannot check what it cannot find"
        body = m.group(0)
        # Columns compared with ILIKE, quoted ("Procurement Name") or bare.
        cols = re.findall(r'(?:"([^"]+)"|(\w+))\s+ILIKE', body)
        cols = {a or b for a, b in cols}
        assert cols, f"{fn}() has no ILIKE predicates -- has the query changed shape?"
        bodies = " ".join(by_table.get(table, []))
        for col in cols:
            checked += 1
            assert col in bodies, (
                f"{fn}() filters {table}.{col} with ILIKE and no trigram index "
                f"declares it. One unindexed OR branch disables the BitmapOr for "
                f"ALL of them -- declare it in modules/searchindexes.py.")
    assert checked >= 5, f"the scan only checked {checked} columns -- it is vacuous"


def test_the_two_id_indexes_are_present_and_explained():
    """These exist only to make the OTHER indexes reachable, which is unusual enough
    that removing them would look like a cleanup."""
    si = _load()
    names = {n for n, _, _ in si.INDEXES}
    assert 'idx_contracts_id_trgm' in names
    assert 'idx_solic_epin_trgm' in names
    doc = _read(os.path.join(ROOT, 'api/modules/searchindexes.py'))
    assert 'BitmapOr' in doc, "the reason the id indexes exist is no longer recorded"
    # ⚠ A btree on the same column is NOT a substitute and must not be confused for one.
    assert 'cannot serve `ILIKE' in doc


def test_a_failed_index_is_logged_not_swallowed():
    """`recreate_table_indexes` prints ✗ and moves on, which is right for an ingest —
    but a failure that logs nothing is how five missing indexes went unnoticed."""
    si = _load()
    src = _read(os.path.join(ROOT, 'api/modules/searchindexes.py'))
    body = src[src.index('async def ensure'):]
    # ⚠ Strip the docstring first: it contains the very ✗ this asserts on, so the
    # check passed against its own explanation while the log line was gone.
    body = re.sub(r'(?s)""".*?"""', '', body, count=1)
    fail_branch = body[body.rindex('except Exception'):]
    assert 'if log:' in fail_branch and '✗' in fail_branch, \
        "a failing index no longer names itself in the log"
    assert 'return made' in body, "ensure() no longer reports how many it created"


def test_index_bodies_are_well_formed():
    """Every body must start with an index method — the hook interpolates it after
    `USING`, so a malformed one fails at ingest time, not here."""
    si = _load()
    for name, tbl, body in si.INDEXES:
        assert body.startswith(('gin ', 'gist ', 'btree ')), f"{name}: bad body {body!r}"
        assert body.count('(') == body.count(')'), f"{name}: unbalanced parens"
        assert name.startswith('idx_'), f"{name}: unexpected index name"
    assert len({n for n, _, _ in si.INDEXES}) == len(si.INDEXES), "duplicate index name"


# --------------------------- 4. one declaration per column, one owner


def _table_indexes():
    """`data_scheduler.TABLE_INDEXES` without importing the module (it pulls in the
    whole enrichment stack). Parsed from source, then evaluated as a literal."""
    import ast
    src = _read(SCHEDULER)
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'TABLE_INDEXES':
            return ast.literal_eval(node.value)
    raise AssertionError("TABLE_INDEXES is gone -- the guard cannot check it")


def _norm_col(expr):
    return expr.replace('"', '').replace(' ', '').lower()


def test_no_column_is_declared_by_two_different_indexes():
    """⚠⚠ THE DUPLICATE-NAME DEFECT. `civillist."wegov-org-id"` was declared twice —
    `idx_civillist_orgid` by a CREATE INDEX inside main.py's startup path, and
    `idx_civillist_wegov_org_id` in TABLE_INDEXES. Only the startup one existed, so
    the moment the hook ran for that table it would have built a SECOND ~97MB index
    doing the identical job (and ~204MB for payrolldata).

    The invariant is about COLUMNS, not names: two names covering one column is the
    bug, whatever they are called.
    """
    si = _load()
    seen = {}
    for tbl, entries in _table_indexes().items():
        for entry in entries:
            # ⚠ A third element is an optional partial-index predicate; it is part of
            # the identity, because `col WHERE x` and `col WHERE y` are genuinely
            # different indexes rather than a duplicate.
            name, expr = entry[0], entry[1]
            where = _norm_col(entry[2]) if len(entry) > 2 else ''
            key = (tbl, _norm_col(expr), where)
            assert key not in seen, (
                f"{tbl}.{expr} is declared by BOTH {seen[key]} and {name} — "
                f"one column, two indexes, ~100-200MB of duplicate work")
            seen[key] = name
    # GIN bodies are a different access method, so a btree and a trigram index on the
    # same column are legitimate (measured: both are needed, `ILIKE '%x%'` cannot use
    # a btree). Only duplicates WITHIN a family are the defect.
    gin = {}
    for name, tbl, body in si.INDEXES:
        key = (tbl, _norm_col(body))
        assert key not in gin, f"{tbl} {body} declared by both {gin[key]} and {name}"
        gin[key] = name


def test_main_declares_no_indexes_of_its_own():
    """One owner. main.py may APPLY indexes; it may not DECIDE what they are."""
    main = _strip_comments(_read(MAIN))
    assert 'CREATE INDEX' not in main, \
        "main.py issues its own CREATE INDEX again — declare it in data_scheduler " \
        "TABLE_INDEXES or modules/searchindexes.py instead"
    # …and the startup path must go through the same function the hook uses, or the
    # two mechanisms drift again.
    people = main[main.index('async def ensure_people_indexes'):]
    people = people[:people.index('\n\n\n')]
    assert 'recreate_table_indexes(' in people, \
        "startup no longer applies indexes through the shared function"


def test_the_indexes_that_only_startup_used_to_create_are_now_declared():
    """⚠ Deleting the startup CREATE statements without declaring these would have
    LOST them at the next ingest. `idx_civillist_titlecode` in particular was the
    most-scanned index on that table and lived in no other declaration."""
    declared = {e[0] for entries in _table_indexes().values() for e in entries}
    for name in ("idx_civillist_orgid", "idx_civillist_titlecode",
                 "idx_payrolldata_orgid", "idx_civillistactive_orgid"):
        assert name in declared, (
            f"{name} was created by main.py's startup path and is not declared in "
            f"TABLE_INDEXES — it will vanish at the next ingest")


def test_the_partial_index_predicate_is_applied():
    """⚠ crol's event-date index is PARTIAL — `WHERE event_date_parsed IS NOT NULL`,
    16K of 1.1M rows. If the optional third element stopped being rendered, the hook
    would build a FULL index over every row instead: same name, silently ~70x the
    rows, and nothing would fail. That is why it lived inline in the importer until
    the declaration learned to express it.

    Behavioural, not a source scan: run the real function and read the SQL it emits.
    """
    import asyncio
    import sys
    sys.path.insert(0, os.path.join(ROOT, 'api'))
    from data_scheduler import recreate_table_indexes

    emitted = []

    class _Conn:
        async def execute(self, sql, *_a):
            emitted.append(" ".join(sql.split()))
            return "CREATE INDEX"

    asyncio.run(recreate_table_indexes(_Conn(), "crol"))
    partial = [s for s in emitted if "idx_crol_event_date" in s]
    assert partial, "the partial index is no longer declared for crol"
    assert "WHERE event_date_parsed IS NOT NULL" in partial[0], (
        f"the partial-index predicate was dropped — this would build a FULL index "
        f"over all 1.1M rows: {partial[0]}")
    # …and an entry without a predicate must NOT gain a stray WHERE.
    plain = [s for s in emitted if "idx_crol_section" in s]
    assert plain and "WHERE" not in plain[0], plain
