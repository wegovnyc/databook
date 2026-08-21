"""Guards for the precomputed contract timeline / payees / spend map.

⚠⚠ THE FAILURE MODES ARE ALL SILENT. A precompute that keys differently, caps
differently, or is scoped wrongly still returns 200 with a plausible-looking
page — it just shows a DIFFERENT answer from the live scan it replaced, or an
empty one that reads as "this contract has no payments".

Four things this pins:
1. the normalization matches oce._normalize_contract_id (two implementations of
   one key is how a precompute stops matching);
2. the payee cap matches the LIMIT in _query_contract_detail, so the precomputed
   answer is the SAME answer;
3. the build is scoped to REGISTERED contracts — the lake holds 8.65M distinct
   contract_ids and grouping over all of them is the #103 OOM defect;
4. the live DuckDB path is still reachable as a fallback (owner decision).
"""
import importlib.util
import io
import os
import re

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
BUILDER = os.path.join(ROOT, 'api/build_contract_timeline.py')
OCE = os.path.join(ROOT, 'api/routers/oce.py')
REFRESH = os.path.join(ROOT, 'scripts/oce-refresh.sh')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _builder():
    spec = importlib.util.spec_from_file_location('_bct', BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------- 1. the key must not drift

def test_the_builders_normalization_matches_the_routers():
    """⚠ `oce._normalize_contract_id` is upper + strip non-alphanumeric. The
    builder expresses the same rule in SQL. If they diverge, the precompute is
    keyed on something the lookup never asks for and every page silently falls
    back (or worse, matches the wrong contract)."""
    mod = _builder()
    sql = mod.NKEY.upper().replace(' ', '')
    assert 'UPPER(CONTRACT_ID)' in sql, f"the builder no longer uppercases: {mod.NKEY}"
    assert "'[^A-Z0-9]'" in sql, f"the builder's strip pattern changed: {mod.NKEY}"
    # And the router's own rule must still be the one we matched.
    oce = _read(OCE)
    fn = oce[oce.index('def _normalize_contract_id'):]
    fn = fn[:fn.index('\ndef ', 5)]
    assert 'upper()' in fn.lower() or 'upper(' in fn.lower(), \
        "oce._normalize_contract_id no longer uppercases; the builder must follow"


def test_the_payee_cap_matches_the_live_query():
    """⚠ The precompute must be the SAME answer, not a similar one. If
    _query_contract_detail keeps 25 payees and the builder keeps 10, a contract
    page silently shows fewer rows than it did — with no error anywhere."""
    mod = _builder()
    oce = _read(OCE)
    fn = oce[oce.index('def _query_contract_detail'):]
    fn = fn[:fn.index('\ndef ', 5)]
    m = re.search(r'ORDER BY spent DESC LIMIT (\d+)', fn)
    assert m, "could not find the payee LIMIT in _query_contract_detail"
    assert int(m.group(1)) == mod.TOP_PAYEES, (
        f"live query keeps {m.group(1)} payees but the builder keeps "
        f"{mod.TOP_PAYEES} — the precomputed page would differ from the scanned one")


# --------------------------------------- 2. scoping, and the run that did nothing

class _StubConn:
    def __init__(self, keys):
        self._keys = keys
        self.executed = []

    async def execute(self, sql, *a):
        self.executed.append(sql)

    async def fetch(self, sql, *a):
        return [{'k': k} for k in self._keys]

    async def fetchval(self, sql, *a):
        return 0


@pytest.mark.asyncio
async def test_a_run_against_an_unloaded_contracts_table_raises(monkeypatch):
    """⚠ THE ZERO-SCANNED CLASS. Writing the result of a run that saw no
    registered contracts would blank every contract page's spend section, and an
    empty timeline is indistinguishable from a contract with no payments."""
    mod = _builder()
    monkeypatch.setattr(mod, 'build_duckdb',
                        lambda keys: pytest.fail("must not scan the lake"))
    conn = _StubConn(['CT1000000000001', 'CT1000000000002'])
    with pytest.raises(RuntimeError, match='refusing'):
        await mod.run(conn, apply=True, verbose=False)


def test_the_build_is_scoped_to_registered_keys():
    """⚠ THE #103 OOM, REBUILT. The lake holds 8,651,319 distinct contract_ids;
    grouping over all of them produced a ~5.5GB dict that crash-looped the api.
    The relevant slice is 2.4% of the lake."""
    src = _read(BUILDER)
    code = '\n'.join(l for l in src.splitlines() if not l.lstrip().startswith('#'))
    assert 'IN (SELECT k FROM keys)' in code, \
        "the lake scan is no longer restricted to the registered key set"
    assert 'MIN_KEYS' in code, "the minimum-keys guard is gone"


def test_the_swap_is_guarded_against_a_large_drop():
    src = _read(BUILDER)
    assert 'MAX_DROP' in src and '_staging_' in src, \
        "the stage-and-swap guard is gone; a truncated lake would blank every page"


# ------------------------------------------- 3. the read path and its fallback

def test_the_router_prefers_the_precompute_but_keeps_the_duckdb_fallback():
    """⚠ OWNER DECISION 2026-08-18: keep the fallback. A contract registered since
    the last lake refresh has no precomputed rows and must still render, and a
    fresh environment where the builder has never run must still work."""
    oce = _read(OCE)
    assert '_precomputed_spend_map' in oce and '_precomputed_contract_detail' in oce, \
        "the precomputed readers are gone"
    assert 'to_duckdb_thread(' in oce and '_query_contract_detail' in oce, \
        "the live DuckDB fallback was removed; that was explicitly kept"
    assert '_populate_contract_spend' in oce, \
        "the background spend-map scan was removed; it is the fresh-env fallback"


def test_absent_precomputed_detail_returns_None_not_an_empty_result():
    """⚠ None and an empty timeline are DIFFERENT states and only one should
    trigger the scan. Returning {} for a missing contract would mean a
    newly-registered contract silently shows no payments forever."""
    oce = _read(OCE)
    fn = oce[oce.index('async def _precomputed_contract_detail'):]
    fn = fn[:fn.index('\n\n\n')]
    assert 'if not tl and not pv:' in fn and 'return None' in fn, \
        "a contract with no precomputed rows no longer falls back to the live scan"


# ------------------------------------------------------ 4. where it is wired

def test_the_builder_runs_on_the_refresh_success_path_isolated_and_guarded():
    """⚠ Three separate requirements, each with its own failure:
    - on oce-refresh.sh's success path, because the lake only changes there and a
      separate cron would serve a timeline built from the previous lake;
    - in an ISOLATED container, because a full-lake DuckDB pass inside the api is
      the contention this removes (and the documented way to OOM it);
    - guarded, because a builder hiccup must not roll back a good lake refresh.
    """
    sh = _read(REFRESH)
    assert 'build_contract_timeline.py --apply' in sh, "the builder is not wired in"
    block = sh[sh.index('if [ "$check_ok" = "1" ]; then'):]
    block = block[:block.index('\nelse')]
    assert 'build_contract_timeline.py' in block, \
        "the builder is not on the success path — it could run against a rolled-back lake"
    assert 'docker run --rm' in block, \
        "the builder is no longer run in an isolated container"
    assert 'WARN' in block and 'fail ' not in block.split('build_contract_timeline.py')[1][:400], \
        "a builder failure now aborts the refresh; it must only warn"
