"""Guards for the token scope model and the /delete hardening (task e235ba85).

The headline vulnerability — the JWT signing secret being the published default
`supersecretkey` — cannot be tested from CI (it is prod env). What CAN be pinned
is everything that must be true FOR the rotation to matter: the scope tiers, the
destructive-endpoint gate, and the SQL-injection fix.
"""

import importlib.util
import os
import pathlib
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'modules'))

import main  # noqa: E402


# ── scopes_for: login stops being vestigially read-only, WITHOUT widening ────

def test_scopes_for_maps_the_three_tiers():
    assert main.scopes_for('full') == ['read', 'write', 'admin']
    assert main.scopes_for('admin') == ['read', 'write', 'admin']
    assert main.scopes_for('write') == ['read', 'write']
    assert main.scopes_for('read') == ['read']


def test_a_write_user_never_gets_admin():
    """⚠ THE DECISION THE EXPOSURE FORCED. Wiring users.scope -> token scopes was
    the naive fix, and it would have made a `write` data operator able to DROP
    tables, because /delete only required `write`. A write user must get write
    and NOT admin."""
    assert 'admin' not in main.scopes_for('write')
    assert 'write' in main.scopes_for('write')


def test_unknown_or_missing_scope_defaults_to_read_only():
    for s in (None, '', 'guest', 'nonsense'):
        assert main.scopes_for(s) == ['read']


def test_login_no_longer_hardcodes_read_only():
    """It minted scopes=['read'] literally until 2026-08-01, so no login token
    could reach any write endpoint — safe but vestigial."""
    src = inspect_source(main.auth)
    assert "scopes_for(" in src
    assert "scopes=['read']" not in src and 'scopes=["read"]' not in src


# ── the destructive endpoint requires `admin`, not merely `write` ────────────

def test_delete_endpoint_requires_admin_scope():
    """⚠ A `write` service token (the app's own) must not be able to DROP a
    table. Only `admin` — which only a `full` user gets — reaches /delete."""
    src = open(os.path.join(os.path.dirname(__file__), '..', 'main.py'),
               encoding="utf-8").read()
    m = re.search(r"def delete_dataset_in_database\([^)]*\)", src, re.S)
    assert m, "the delete endpoint moved or was renamed"
    sig = m.group(0)
    assert "scopes=['admin']" in sig or 'scopes=["admin"]' in sig, \
        "delete must require the admin scope"
    assert "scopes=['write']" not in sig


# ── the SQL-injection sink is closed ─────────────────────────────────────────

class _FakeDB:
    def __init__(self, tables):
        self._tables = tables
        self.dropped = []

    def tables(self):
        return self._tables

    def q(self, sql):
        self.dropped.append(sql)


def _load_csvdataset():
    """Load the real csvdataset module in isolation.

    conftest stubs `config` and `postgrex`; `datax` is stubbed here so the
    module's top-level imports resolve without a database. Same file-load
    pattern conftest uses for the other pure modules.
    """
    import importlib.util
    from unittest.mock import MagicMock
    sys.modules.setdefault("datax", MagicMock())
    path = os.path.join(os.path.dirname(__file__), '..', 'modules', 'postgrex',
                        'csvdataset.py')
    spec = importlib.util.spec_from_file_location("_csvdataset_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CsvDataset


def _dataset(tables):
    CsvDataset = _load_csvdataset()
    ds = CsvDataset.__new__(CsvDataset)      # skip __init__ (it opens a real DB)
    ds.db = _FakeDB(tables)
    ds.datadir = "/tmp"
    ds.fn = None
    return ds


def test_delete_rejects_a_non_identifier():
    """⚠ `tbl` reached `DROP TABLE {}`.format(tbl) raw. A name that is not a
    plain identifier must be refused before any SQL runs."""
    ds = _dataset(["vendors"])
    for evil in ('vendors; DROP TABLE contracts', 'a" ; DELETE FROM x --',
                 'x OR 1=1', ''):
        assert ds.delete(evil) is False
    assert ds.db.dropped == [], "no DROP should have been issued"


def test_delete_rejects_a_nonexistent_table():
    """Even a clean identifier must exist before it is dropped — this also stops
    a valid-looking name for a table in another schema."""
    ds = _dataset(["vendors", "contracts"])
    assert ds.delete("not_a_real_table") is False
    assert ds.db.dropped == []


def test_delete_quotes_the_identifier_and_does_not_swallow():
    ds = _dataset(["vendors"])
    # delete_file returns False (no file), but the DROP must have run, quoted.
    ds.delete("vendors")
    assert ds.db.dropped == ['DROP TABLE "vendors"']
    # ⚠ strip comments first — the fix documents the old `except: pass` it
    # removed, and a naive scan fires on that explanation.
    code = "\n".join(ln for ln in inspect_source(type(ds).delete).split("\n")
                     if not ln.lstrip().startswith("#"))
    assert "except Exception:" not in code, \
        "the delete must not swallow errors any more"


# ── the startup guard that makes a weak secret impossible to ignore ──────────

def test_a_weak_signing_key_is_flagged():
    assert 'supersecretkey' in main._WEAK_SIGNING_KEYS
    assert 'secret' in main._WEAK_SIGNING_KEYS
    src = inspect_source(main.warn_on_weak_signing_key)
    assert "SECURITY" in src
    assert "rotate-fastapi-key.sh" in src


# ── the rotation script's safety properties ──────────────────────────────────

def test_rotation_script_moves_all_three_and_rolls_back():
    p = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts',
                     'rotate-fastapi-key.sh')
    src = open(p, encoding="utf-8").read()
    # all three locations of the shared secret
    assert "env.yaml" in src and "FAPI_KEY" in src and "DATABOOK_API_KEY" in src
    # it re-mints the app token rather than reusing the old signature
    assert "jwt.encode" in src
    # it proves the fix: an old-secret forged token must be rejected
    assert "forged" in src.lower() and "401" in src
    # and it reverts on failure
    assert "rollback" in src


def inspect_source(obj):
    import inspect
    return inspect.getsource(obj)


# ── the shared ingest key travels in a header, not the query string ───────────
#
# Found 2026-08-03 by reading the api access log during a normalizer sweep: the
# 64-hex DATABOOK_API_KEY appeared in plaintext in 11 request lines in 20
# minutes, because it was passed as `?api_key=`. uvicorn logs the full request
# line, so the query form publishes the credential to anyone with `docker logs`.

# Loaded straight off disk, and pinned onto `main` below, so these assertions
# depend on the real resolver rather than on conftest's mocking policy.
#
# conftest.py replaces the whole `modules` package with a MagicMock (so the suite
# never touches a real database) and now explicitly hangs the REAL apikey off it,
# for the reason recorded there: a MagicMock's `.ok()` is truthy, so mocking it
# authorises everybody. Before that fix these tests failed as
# `assert <MagicMock ...> is False`, and two org_admin auth tests FAILED OPEN.
_apikey_spec = importlib.util.spec_from_file_location(
    "apikey_under_test",
    pathlib.Path(__file__).resolve().parents[1] / "modules" / "apikey.py",
)
real_apikey = importlib.util.module_from_spec(_apikey_spec)
_apikey_spec.loader.exec_module(real_apikey)


@pytest.fixture
def _configured_key(monkeypatch):
    """Pin a known configured key, and the REAL resolver, on `main`."""
    monkeypatch.setattr(main.Config, 'fastapi', {'key': 'k' * 64}, raising=False)
    monkeypatch.setattr(main, 'apikey', real_apikey)
    return 'k' * 64


def test_the_header_authenticates(_configured_key):
    assert main._api_key_ok(_configured_key, None) is True


def test_the_query_parameter_still_authenticates_but_warns(_configured_key, caplog):
    """Kept working ON PURPOSE, so the api can deploy before the normalizer.

    A flag day would have 401'd every ingest in the window between the two
    deploys. The warning is what makes the remaining callers findable instead of
    the compatibility shim becoming permanent by accident.
    """
    with caplog.at_level('WARNING'):
        assert main._api_key_ok(None, _configured_key) is True
    assert 'QUERY PARAMETER' in caplog.text
    # The warning must not leak the thing it is complaining about.
    assert _configured_key not in caplog.text


def test_a_wrong_or_missing_key_is_refused_by_either_route(_configured_key):
    for header, query in ((None, None), ('', ''), ('wrong', None), (None, 'wrong'),
                          ('k' * 63, None)):
        assert main._api_key_ok(header, query) is False


def test_an_unconfigured_key_never_authenticates(monkeypatch):
    """⚠ Fail closed. `Config.fastapi` with no key must not turn into a state
    where an empty api_key matches an empty configured value and authorizes."""
    monkeypatch.setattr(main.Config, 'fastapi', {}, raising=False)
    monkeypatch.setattr(main, 'apikey', real_apikey)
    for header, query in ((None, None), ('', ''), ('anything', None)):
        assert main._api_key_ok(header, query) is False


def test_the_comparison_is_constant_time():
    """`==` on a str short circuits at the first differing byte. This is a
    secret, so the comparison must not be a timing oracle.

    Follows the logic into modules/apikey.py rather than inspecting the thin
    wrapper — a source check that reads a delegating function proves nothing.
    """
    src = inspect_source(real_apikey.ok)
    assert 'compare_digest' in src
    assert '== configured' not in src and 'configured ==' not in src


def test_org_admin_uses_the_shared_resolver_and_prefers_the_header():
    """⚠ The site the first pass MISSED.

    `org_admin.require_editor` had its own copy of this check that read the
    QUERY PARAMETER FIRST and compared with `==` — so the org-admin write API
    kept the log-leak path after #192 closed it on /import-csv and /upload. It
    was found by cross-checking the docs, not by the #192 guard, whose regex
    targets senders (`?api_key=`) and cannot see a reader.

    Pinned on the SOURCE because require_editor needs a live Request and a
    configured key; what must not regress is the shape.
    """
    path = os.path.join(os.path.dirname(__file__), '..', 'routers', 'org_admin.py')
    src = open(path, encoding='utf-8').read()
    body = src[src.index('async def require_editor'):]
    body = body[:body.index('\nasync def ', 1)] if '\nasync def ' in body[1:] else body

    assert 'apikey.ok(' in body, "must go through the shared resolver"
    assert 'api_key == configured' not in body, "must not compare the secret with =="
    # The header argument must come before the query one, or a caller sending
    # both would still be authorised by the logged copy.
    hdr = body.index('request.headers.get("X-API-Key")')
    qry = body.index('request.query_params.get("api_key")')
    assert hdr < qry, "header must be checked before the query parameter"


def test_no_source_sends_the_key_as_a_query_parameter():
    """Fail the build if any caller reverts to `?api_key=`.

    The direction that matters: asserting the api ACCEPTS a header cannot see a
    caller that still sends a query parameter — and the caller is what puts the
    secret in the log. So scan the callers. Covers the normalizer submodule and
    the ops scripts, which is where all three real callers lived.
    """
    # ⚠ realpath, and skip on path COMPONENTS rather than a substring. The first
    # draft of this guard used the un-normalized `<...>/api/tests/../..` as its
    # root, so EVERY dirpath contained the substring "test", the skip matched
    # everything, and the guard scanned 0 files while passing — vacuous, and
    # indistinguishable from a clean tree. Same class as the checks in this repo
    # that reported zero problems because they never ran.
    root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
    banned = re.compile(r"""[?&]api_key=|["']api_key["']\s*:""")
    offenders = []
    scanned = 0
    for sub in ('api', 'scripts', os.path.join('normalizer-py', 'app')):
        base = os.path.join(root, sub)
        for dirpath, _dirs, files in os.walk(base):
            parts = set(os.path.relpath(dirpath, root).split(os.sep))
            if parts & {'tests', '__pycache__', '.pytest_cache'}:
                continue
            for fn in files:
                if not fn.endswith(('.py', '.sh')):
                    continue
                path = os.path.join(dirpath, fn)
                scanned += 1
                with open(path, encoding='utf-8', errors='replace') as fh:
                    # ⚠ Skip comments AND docstrings. Several of these files now
                    # EXPLAIN the banned form in prose, and a guard that fires on
                    # its own documentation gets deleted rather than obeyed —
                    # this one flagged org_admin.py's module docstring on the
                    # first run. Stripping `#` was not enough.
                    in_doc = False
                    for n, line in enumerate(fh, 1):
                        code = line.split('#', 1)[0]
                        ticks = code.count('"""') + code.count("'''")
                        if ticks:
                            # A delimiter line is prose either way; toggle on an
                            # odd count so a one-line """doc""" does not flip it.
                            if ticks % 2:
                                in_doc = not in_doc
                            continue
                        if in_doc:
                            continue
                        if banned.search(code):
                            rel = os.path.relpath(path, root)
                            offenders.append(f"{rel}:{n}: {line.strip()}")

    # The guard must prove it looked. Without this, any future change that breaks
    # the walk turns this test back into a silent pass.
    assert scanned > 40, f"guard scanned only {scanned} files — the walk is broken"
    assert not offenders, (
        "These send the shared key as a query parameter, which writes it to the "
        "access log in plaintext. Use the X-API-Key header:\n  "
        + "\n  ".join(offenders))
