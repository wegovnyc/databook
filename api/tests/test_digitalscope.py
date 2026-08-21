"""Guards for the Digital Services scope migration (docs/DIGITAL-SERVICES-SECTION-PLAN.md).

⚠ modules/ is replaced by a MagicMock in conftest.py, so digitalscope is loaded
BY PATH here — `from modules import digitalscope` in a test yields a mock that
satisfies any assertion (the licenseclass lesson).
"""
import csv
import importlib.util
import os
import re
import sys
import types

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _load_digitalscope():
    path = os.path.join(ROOT, 'api', 'modules', 'digitalscope.py')
    # digitalscope imports modules.errfmt; give the loader a real stand-in so the
    # module under test is genuine even while the package is mocked.
    errfmt = types.ModuleType('modules.errfmt')
    errfmt.exc_str = lambda e: f"{type(e).__name__}: {e}"
    sys.modules.setdefault('modules.errfmt', errfmt)
    spec = importlib.util.spec_from_file_location('_digitalscope', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scope_lives_in_one_module_and_oce_never_reads_vendor_tags():
    """⚠⚠ THE DEFECT THIS MIGRATION FIXES: seven call sites each interpolated
    their own vendor_tags IN-list, so "digital" meant seven copies of a frozen
    200-name keyword list — 85.2% precision, 200 of 6,964 vendors, Inter-Con
    SECURITY SYSTEMS at "100% digital share" on the public page.

    After the refactor the scope has ONE owner. A vendor_tags read reappearing
    in oce.py is the old world growing back.
    """
    src = open(os.path.join(ROOT, 'api/routers/oce.py'), encoding='utf-8').read()
    code = re.sub(r'(?m)^\s*#.*$', '', src)          # comments may explain the ban
    assert 'vendor_tags' not in code, \
        "oce.py queries vendor_tags directly again — the scope has one owner, " \
        "modules/digitalscope.py"
    assert 'vendor_list' not in code, \
        "an interpolated vendor IN-list is back in oce.py"
    assert src.count('digitalscope.load(') >= 6, \
        "the endpoints no longer resolve their scope through digitalscope"

    # The scan is only meaningful if the string lives where it should.
    scope_src = open(os.path.join(ROOT, 'api/modules/digitalscope.py'), encoding='utf-8').read()
    assert "FROM vendor_tags" in scope_src, \
        "vendor_tags left digitalscope too — the tag mode is gone entirely, " \
        "which should be a deliberate retirement, not a side effect"


def test_tag_mode_preserves_the_old_numbers_and_derived_fixes_them():
    """⚠ The gate's contract, in both directions. Tag mode must keep serving
    exactly what the page published (amendment-ROW grain, award_amount, the
    vendor IN-list) so the refactor alone changes nothing. Derived mode must be
    the licences discipline (one row per contract, current-else-award, positive
    tech_relevant scope) so the flip is the fix and not a third thing.
    """
    ds = _load_digitalscope()

    # tag: byte-familiar shapes
    assert ds.table_sql('tag') == 'contracts'
    assert ds.where_sql('tag', 'c', "'A','B'") == "c.vendor_name IN ('A','B')"
    assert ds.value_sql('tag', 'c') == 'c.award_amount'

    # derived: dedup + positive scope + current-else-award
    t = ds.table_sql('derived')
    assert 'DISTINCT ON (contract_id)' in t and 'current_amount' in t, \
        "derived mode lost the one-row-per-contract dedup"
    w = ds.where_sql('derived', 'c', "IGNORED")
    assert 'tech_relevant' in w and w.startswith('EXISTS'), \
        "derived scope is no longer a positive tech_relevant condition"
    assert 'IGNORED' not in w, "derived mode must not depend on any vendor list"
    assert ds.value_sql('derived', 'c') == 'coalesce(c.current_amount, c.award_amount)'

    # the compensating non-tech exclusion belongs to tag mode only
    assert ds.exclude_confirmed_nontech_sql('derived', 'c', True) == ''
    assert 'tech_relevant = false' in ds.exclude_confirmed_nontech_sql('tag', 'c', True)

    # ⚠ THE DEFAULT FLIPPED TO `derived` 2026-08-13 (#247), with the Overview rebuild
    # — the last page that still published the old numbers. This assertion used to
    # read `== 'tag'` and failing here is how the flip announced itself; the claim now
    # lives in test_overview_rebuild.py, which owns the decision. What this still
    # pins, and what matters either way, is that the ROLLBACK works and an invalid
    # value never guesses.
    os.environ.pop(ds.MODE_ENV, None)
    assert ds.mode() == ds.DEFAULT_MODE
    os.environ[ds.MODE_ENV] = 'tag'
    try:
        assert ds.mode() == 'tag', "DIGITAL_SCOPE=tag no longer rolls the scope back"
        os.environ[ds.MODE_ENV] = 'garbage'
        assert ds.mode() == ds.DEFAULT_MODE, \
            "an invalid mode must fall back to the default, not crash or guess"
    finally:
        os.environ.pop(ds.MODE_ENV, None)


def test_contract_grain_corrections_have_a_seed_and_a_consumer():
    """⚠ A seed with no consumer is decoration (the rate-card lesson), and a
    correction mechanism matters here because family-grain curation cannot reach
    services: the $929M hotel contract had no licence family to fix it through.
    """
    seed_path = os.path.join(ROOT, 'api/seed/contract_enrichment_curated.csv')
    with open(seed_path, newline='', encoding='utf-8') as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith('#')]
    rows = [r for r in csv.DictReader(lines) if (r.get('contract_id') or '').strip()]
    assert rows, "the seed is empty — the hotel correction is gone"
    bad = [r for r in rows if None in r]
    assert not bad, f"unquoted commas truncated {len(bad)} rows (the vocab-seed defect)"
    for r in rows:
        assert (r.get('note') or '').strip(), \
            f"{r['contract_id']}: a correction with no stated reason"
        tr = (r.get('tech_relevant') or '').strip()
        assert tr in ('', '0', '1'), f"{r['contract_id']}: tech_relevant must be blank/0/1"

    loader = open(os.path.join(ROOT, 'api/seed_contract_enrichment.py'), encoding='utf-8').read()
    assert 'contract_enrichment_curated.csv' in loader, "the loader lost its seed"
    # ⚠ Match the CODE, not the docstring — the docstring also says "curated =
    # true", and the first draft of this assertion passed against a loader whose
    # UPDATE no longer set the flag at all. The scanner-matches-its-own-
    # documentation trap, again.
    assert '["curated = true"]' in loader, \
        "the UPDATE no longer starts from the curated flag — corrections would " \
        "be silently reclassified at the next AI run"
    # ⚠ Blank-means-keep: the UPDATE must be built per-field, never overwrite both.
    assert "if tr in (\"0\", \"1\")" in loader and 'if fc:' in loader, \
        "the loader no longer respects blank-means-keep"

    # And the flag it relies on must still protect: the classifier's writes must
    # be gated on curated = false, or a re-run silently undoes every correction.
    clf = open(os.path.join(ROOT, 'api/classify_digital_contracts.py'), encoding='utf-8').read()
    assert 'curated = false' in clf, \
        "classify_digital_contracts no longer respects the curated flag — every " \
        "contract-grain correction dies at the next run"


def test_worksheet_is_the_gate_and_preserves_decisions():
    """The composition bar publishes only after the top rows are reviewed; the
    worksheet is that gate, and re-running it must never blank a verdict."""
    src = open(os.path.join(ROOT, 'api/build_contract_review_worksheet.py'), encoding='utf-8').read()
    assert 'NOT e.is_license' in src, \
        "the worksheet includes licence contracts — those are reviewed at family grain"
    assert 'e.tech_relevant' in src, "the worksheet lost its tech scope"
    assert 'def read_existing' in src and 'prior.get("verdict"' in src, \
        "re-running the worksheet discards decisions"
    assert 'CONTRACT_SELECT' in src and 'attach_notices' in src, \
        "the worksheet rebuilds the evidence query instead of sharing production's"
