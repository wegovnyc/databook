"""Guards for the federated search's SQL, and for the LEVEL its failures log at.

The defect these exist to prevent is a group that silently stops returning
results. `global_search` appends a group only `if res`, so a builder returning
[] is **omitted from the payload entirely** and the response is still 200 —
there is no shape difference between "nothing matched" and "this query has been
failing since June". That is not a hypothetical: `_people` capped each arm of a
`UNION ALL` with a bare `LIMIT`, which is a Postgres syntax error, and the
people group returned [] on every search from 2026-06-19 to 2026-08-14.
`q=garcia` served `total: 0` while the database held ten matching people.

Two independent guards, because either alone leaves the hole open:

* the STATIC one pins the exact shape that broke, across the whole tree — it
  would have failed the moment `0e9a614` was written;
* the BEHAVIOURAL one pins that a malformed query is reported at ERROR, which
  is what makes any FUTURE instance of this class alert instead of hiding.
  (`logger.warning` reaches Sentry as a breadcrumb only, and a breadcrumb is
  discarded unless an ERROR follows in the same request scope — which never
  happens on a path that returns 200.)

⚠ The behavioural half must not be satisfied by the docstring or the comment
explaining it, so it runs the real function and reads the emitted record.
"""

import ast
import logging
import os
import re
import warnings

import pytest

_API_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Files whose SQL the static scan covers. Excludes the test tree so the guard
# cannot be satisfied (or broken) by its own fixtures.
_SKIP_DIR_PARTS = {"tests", "__pycache__", "node_modules", ".git", "venv"}


def _python_sources():
    """Every non-test .py file under api/, as (relpath, text).

    ⚠ Path COMPONENTS, never a substring: an earlier guard in this repo
    computed its root un-normalised, so every dirpath contained "/tests/", it
    skipped everything, scanned zero files and passed unconditionally.
    """
    out = []
    for dirpath, dirnames, filenames in os.walk(_API_DIR):
        parts = set(os.path.relpath(dirpath, _API_DIR).split(os.sep))
        if parts & _SKIP_DIR_PARTS:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_PARTS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    out.append((os.path.relpath(path, _API_DIR), fh.read()))
            except (OSError, UnicodeDecodeError):
                continue
    return out


# `LIMIT <something>` followed directly by UNION/EXCEPT/INTERSECT with no
# closing paren in between. In Postgres a bare LIMIT binds to the WHOLE set
# operation, so this is a syntax error, not a per-arm cap. The `[^\s)]+` stops
# at a `)`, which is exactly what makes the parenthesised (correct) form pass.
_UNPARENTHESISED_LIMITED_ARM = re.compile(
    r"LIMIT\s+[^\s)]+\s+(?:UNION|EXCEPT|INTERSECT)\b", re.IGNORECASE
)

_SET_OP = re.compile(r"\b(?:UNION|EXCEPT|INTERSECT)\b", re.IGNORECASE)


def _sql_literals(text):
    """Yield (lineno, value) for every string literal that is NOT a docstring.

    ⚠⚠ SCANNING THE RAW TEXT DOES NOT WORK HERE, and the first draft of this
    guard proved it by failing on the comment in `search.py` that EXPLAINS the
    bug — a comment quoting `SELECT ... LIMIT $2 UNION ALL` is prose, not SQL.
    A scanner that reads an explanation as code reports problems that are not
    there, the mirror of the guard that scanned zero files.

    Parsing with `ast` removes `#` comments for free and lets docstrings be
    excluded by identity, while keeping ordinary string literals — which is
    exactly where SQL lives.
    """
    # Compiling arbitrary sources raises SyntaxWarning for things like an
    # `invalid escape sequence` in a regex literal elsewhere in the tree. Those
    # are real but they belong to their own file, not to this guard — letting
    # them through makes the suite output look like this test found something.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(text)
    doc_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                doc_ids.add(id(first.value))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in doc_ids):
            yield getattr(node, "lineno", 0), node.value


def test_no_set_operation_arm_is_capped_by_an_unparenthesised_limit():
    """`SELECT ... LIMIT n UNION ALL SELECT ...` is a syntax error (42601).

    To cap each arm the arm must be parenthesised. This is the exact shape that
    took out the people group for eight weeks.
    """
    sources = _python_sources()
    # ⚠ Assert the scan LOOKED. A guard that walks the tree and finds nothing is
    # indistinguishable from one that never ran.
    assert len(sources) > 40, f"only scanned {len(sources)} files -- scan is vacuous"

    offenders, files_with_set_ops = [], 0
    for rel, text in sources:
        try:
            literals = list(_sql_literals(text))
        except SyntaxError:
            continue  # not importable anyway; the build fails elsewhere
        if any(_SET_OP.search(v) for _, v in literals):
            files_with_set_ops += 1
        for lineno, value in literals:
            for m in _UNPARENTHESISED_LIMITED_ARM.finditer(value):
                offenders.append(f"{rel}:{lineno}: {m.group(0)!r}")

    # A second vacuity check, on the thing actually being inspected: if no SQL
    # literal anywhere contains a set operation, the regex above is checking
    # nothing and would pass however broken the tree got.
    assert files_with_set_ops > 0, (
        "no SQL literal in api/ contains UNION/EXCEPT/INTERSECT -- the scan "
        "found nothing to check, so its success is meaningless"
    )

    assert not offenders, (
        "a LIMIT directly precedes a set operation with no closing paren -- in "
        "Postgres that is a syntax error, and the failing group degrades to [] "
        "invisibly:\n  " + "\n  ".join(offenders)
    )


def test_the_people_query_parenthesises_both_arms():
    """Narrower than the scan above, and deliberately kept beside it.

    The tree-wide guard could be weakened by a future refactor of its regex
    without anyone noticing which real query it protected; this one names the
    query and fails if its arms lose their parentheses.
    """
    path = os.path.join(_API_DIR, "routers", "search.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == "_people"), None)
    assert fn is not None, "routers/search.py no longer defines _people"

    sql = [c.value for c in ast.walk(fn)
           if isinstance(c, ast.Constant) and isinstance(c.value, str)
           and _SET_OP.search(c.value)]
    assert sql, "_people's SQL no longer contains a set operation -- update this guard"

    for q in sql:
        assert q.count("(SELECT") >= 2, "_people's UNION arms are not parenthesised"
        assert not _UNPARENTHESISED_LIMITED_ARM.search(q), (
            "_people has an unparenthesised LIMIT before its UNION -- the "
            "regression that emptied the people group 2026-06-19 to 2026-08-14"
        )


# ---------------------------------------------------------------------------
# The failure LEVEL. Runs the real `_rows`, reads the real emitted record.
# ---------------------------------------------------------------------------

def _load_search_module():
    from routers import search  # noqa: PLC0415 — deferred; conftest stubs deps first
    return search


def _raise(exc):
    async def _boom(*a, **kw):
        raise exc
    return _boom


@pytest.mark.asyncio
async def test_a_malformed_query_is_reported_as_an_error(monkeypatch, caplog):
    """A syntax error is ALWAYS a code defect -- never transient, never
    environmental -- so it must reach Sentry as an event, which means ERROR."""
    search = _load_search_module()
    asyncpg_exc = pytest.importorskip("asyncpg.exceptions")

    monkeypatch.setattr(
        search.PostgresModelAsync, "select_safe",
        _raise(asyncpg_exc.PostgresSyntaxError('syntax error at or near "UNION"')),
        raising=False,
    )

    with caplog.at_level(logging.DEBUG, logger=search.logger.name):
        out = await search._rows("SELECT 1 LIMIT 1 UNION ALL SELECT 2", [])

    assert out == [], "a failed group must still degrade to [] rather than 500"
    levels = {r.levelno for r in caplog.records}
    assert logging.ERROR in levels, (
        "a malformed query logged at "
        f"{sorted(logging.getLevelName(l) for l in levels)} -- at WARNING it is a "
        "Sentry breadcrumb only, and a breadcrumb attached to no error is never sent"
    )


@pytest.mark.asyncio
async def test_a_missing_table_stays_a_warning(monkeypatch, caplog):
    """The counter-direction, and the reason the `except` is narrow.

    Derived tables legitimately do not exist until their job has run, and this
    repo treats that as a normal fresh-environment state. Promoting it would
    raise a Sentry event per absent table and the alert would be ignored within
    a week -- so the guard pins that it is NOT promoted.
    """
    search = _load_search_module()
    asyncpg_exc = pytest.importorskip("asyncpg.exceptions")

    monkeypatch.setattr(
        search.PostgresModelAsync, "select_safe",
        _raise(asyncpg_exc.UndefinedTableError('relation "license_family" does not exist')),
        raising=False,
    )

    with caplog.at_level(logging.DEBUG, logger=search.logger.name):
        out = await search._rows("SELECT * FROM license_family", [])

    assert out == []
    levels = {r.levelno for r in caplog.records}
    assert logging.ERROR not in levels, (
        "a missing table was promoted to ERROR -- that is the widening trap: "
        "UndefinedTableError shares its SQLSTATE-class-42 parent with "
        "PostgresSyntaxError, so catching the parent alerts on every fresh env"
    )
    assert logging.WARNING in levels, "a missing table should still be visible at WARNING"


def test_the_syntax_error_tuple_does_not_include_the_class_42_parent():
    """Pins the narrowness itself, so a future 'simplification' to the parent
    class fails here rather than in production alert volume."""
    search = _load_search_module()
    asyncpg_exc = pytest.importorskip("asyncpg.exceptions")

    assert search._SYNTAX_ERRORS, (
        "_SYNTAX_ERRORS is empty, so the ERROR branch is unreachable and every "
        "malformed query silently degrades to WARNING again"
    )
    # `SyntaxOrAccessError` is the VERIFIED immediate base of all three: 42601
    # (syntax), 42P01 (undefined table) and 42703 (undefined column). Catching
    # it would sweep the two fresh-env conditions into Sentry alongside the real
    # defect, so each is named here rather than trusting the base class alone.
    for banned in ("UndefinedTableError", "UndefinedColumnError",
                   "SyntaxOrAccessError"):
        cls = getattr(asyncpg_exc, banned, None)
        assert cls is not None, (
            f"asyncpg.exceptions.{banned} no longer exists -- this guard is "
            "silently checking nothing; re-derive the hierarchy"
        )
        assert not issubclass(cls, tuple(search._SYNTAX_ERRORS)), (
            f"{banned} is caught by _SYNTAX_ERRORS -- too wide; match 42601 only"
        )
