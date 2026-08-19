"""Guards for the licences page's annual SPENDING chart.

This is the first block on that page that reports CASH rather than awarded value,
and the ways it can go wrong are specific:

1. the year series stops closing -- a fiscal year silently dropped between the
   scan and the payload, which is exactly what `_by_year` on this same page did
   when 72% of the inventory fell into an undisclosed `ended` gap,
2. the fiscal year IN PROGRESS gets drawn as a bar, so the newest year reads as a
   collapse, or gets dropped without being reported,
3. the coverage caveat goes missing, and a $864.6M floor is read as the licence
   bill -- 161 contracts carrying $749.3M have no payment at all, led by a
   $573.8M citywide master that is genuinely paid under other contract ids,
4. someone "corrects" the sum by deduplicating rows, which measurement says is
   WRONG here (see test_the_plain_sum_is_deliberate) and would also make this
   chart disagree with the contract page, the vendor profile and the queue,
5. the query wraps `contract_id` in a function, disabling Parquet row-group
   pruning -- the #160 defect, worth 10-34x.

⚠ modules/ is a MagicMock under conftest.py, so anything loaded here is loaded
BY PATH. The router itself is scanned as source, never imported: importing it
pulls in postgrex and the whole oce module.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
LICENSES = os.path.join(ROOT, 'api/routers/licenses.py')
VIEW = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php')


def _src():
    with open(LICENSES, encoding='utf-8') as fh:
        return fh.read()


def _view():
    with open(VIEW, encoding='utf-8') as fh:
        return fh.read()


def _function_body(src, name):
    """The source of one function, from its `def` to the next top-level `def`.

    ⚠ `[ \t]*` NOT `\\s*`: `\\s` matches newlines, so the anchored form matched a
    BLANK LINE and every ban built on it passed vacuously. Caught only because the
    caller asserts the body is non-empty.
    """
    m = re.search(r'(?m)^[ \t]*(?:async )?def %s\(' % re.escape(name), src)
    assert m, f"{name}() is gone -- the guard cannot check what it cannot find"
    rest = src[m.start():]
    nxt = re.search(r'(?m)^(?:async )?def |^@router', rest[1:])
    body = rest[:nxt.start() + 1] if nxt else rest
    assert len(body.splitlines()) > 5, f"{name}() body looks empty -- guard is vacuous"
    return body


# ------------------------------------------------------- 1. the series closes


def test_the_paid_series_accounts_for_everything_scanned():
    """`years` + `partial` + `dropped` == `total_all`, computed in the payload rather
    than asserted in prose. A fiscal year that matched no bucket would vanish while
    every visible figure still looked plausible.

    ⚠ This guard changed shape when the shared 10-year window landed: `dropped` is a
    third bucket now, so a two-way closure would no longer be the whole story. It
    fired on that change, which is the guard working.
    """
    body = _function_body(_src(), '_build_spend_by_year')
    assert '"total_all"' in body, "total_all is gone -- nothing pins the closure"
    assert '_window(buckets, cur_fy)' in body, \
        "the paid series no longer goes through the shared window helper"
    assert '"total": sum(y["paid"] for y in years)' in body
    # ⚠ SCOPED TO THE `total_all` EXPRESSION ITSELF. A body-wide substring search
    # passed while total_all had been cut back to two buckets, because
    # `sum(... for y in dropped)` also appears in the `dropped` block a few lines
    # down. Found by reintroducing the bug; a loose scan is a vacuous scan.
    expr = body.split('"total_all":')[1].split('"dropped"')[0]
    for bucket in ('years', 'partial', 'dropped'):
        assert f'for y in {bucket}' in expr, \
            f"total_all no longer includes `{bucket}`, so the closure cannot be checked"


# ------------------------------------------- 2. the fiscal year in progress


def test_the_current_fiscal_year_is_excluded_from_the_bars_and_still_reported():
    src = _src()
    body = _function_body(src, '_build_spend_by_year')
    # ⚠ Derived from the CLOCK, not from max(fiscal_year) in the lake. The lake
    # carries future-dated rows (measured: the FY2027 partition runs to
    # 2027-03-27), so a max()-based rule can mark a year complete that is not.
    assert '_fy_of(time.strftime("%Y-%m-%d"))' in body, \
        "the current fiscal year is no longer taken from the clock"
    assert 'max(' not in body.split('cur_fy')[0].split('\n')[-1], \
        "the current fiscal year looks derived from the data again"
    view = _view()
    assert '$spendPart' in view, "the partial year is no longer rendered"
    assert 'is in progress and is not drawn' in view, \
        "the page no longer says why the newest year has no bar"


def test_the_fiscal_year_helper_is_imported_not_reimplemented():
    """One definition of the NYC fiscal year. A second copy is how a harness comes
    to measure a different system than the code it is checking."""
    src = _src()
    assert '_fy_of' in src and 'from routers.oce import' in src
    assert not re.search(r'def _fy_of', src), \
        "licenses.py has grown its own fiscal-year function"
    # And it must be the July boundary, wherever it lives.
    oce = open(os.path.join(ROOT, 'api/routers/oce.py'), encoding='utf-8').read()
    fy = _function_body(oce, '_fy_of')
    assert 'mo >= 7' in fy, "the fiscal-year boundary moved off July"


# --------------------------------------------------- 3. the coverage caveat


def test_the_payload_carries_the_coverage_caveat_and_names_the_largest_gap():
    body = _function_body(_src(), '_build_spend_by_year')
    for key in ('"contracts_paid"', '"unmatched_contracts"', '"unmatched_value"',
                '"largest_unmatched"'):
        assert key in body, f"coverage no longer carries {key}"
    assert 'max(unmatched, key=lambda k: value_of[k])' in body, \
        "the largest unmatched contract is no longer identified"


def test_the_page_states_that_the_paid_series_is_a_floor():
    """⚠ THE SUBSTANTIVE RISK. $844.8M looks like the licence bill and is not: it is
    payments filed under these contract ids, and a master agreement is paid against
    on agency purchase orders. A reader who quotes the chart without that sentence is
    quoting a floor as a total."""
    view = _view()
    assert 'treat paid as a\n                    floor' in view or 'treat paid as a floor' in view, \
        "the floor disclosure is gone from the page"
    assert 'The largest with none is' in view, \
        "the page no longer names the largest contract with no payments"
    assert 'matches Checkbook\'s own per-contract' in view, \
        "the page no longer says the matched contracts agree with Checkbook itself"


# ------------------------------------------------------ 4. the sum is plain


def test_the_plain_sum_is_deliberate_and_documented():
    """⚠ DO NOT DEDUPLICATE. 666 of 8,273 rows are exact duplicates and an earlier
    draft "corrected" for that. Scored against `checkbook_contract_meta.spent_to_date`
    -- CheckbookNYC's OWN per-contract figure -- the plain sum matches 159 of 183
    contracts and every dedup rule tried scored worse (155, 152, 104). It is also
    what the contract page, the vendor profile and the queue already publish."""
    body = _function_body(_src(), '_scan_spend_by_year')
    assert 'SUM(amt)' in body, "the sum changed shape"
    for banned in ('DISTINCT ON', 'any_value(', 'GROUP BY document_id'):
        assert banned not in body, \
            f"a dedup ({banned}) was introduced -- measurement says the plain sum " \
            f"matches Checkbook's own figure better"
    doc = _function_body(_src(), '_build_spend_by_year')
    assert 'spent_to_date' in doc, \
        "the reason the sum is not deduplicated is no longer recorded"


# ---------------------------------------------------- 5. the scan stays fast


def test_the_scan_filters_the_raw_column_and_scans_once():
    """#160: wrapping a Parquet column in a function makes the predicate opaque to
    row-group statistics. Measured on this set, `upper(contract_id)` and the full
    normalizing regex return identical totals ($885.2M / 8,273 rows) -- so the
    regex buys nothing and costs the pruning."""
    body = _function_body(_src(), '_scan_spend_by_year')
    assert 'upper(contract_id) IN' in body, "the id predicate changed"
    assert 'REGEXP_REPLACE(UPPER(contract_id)' not in body, \
        "the scan re-normalizes contract_id, which disables row-group pruning"
    assert body.count('read_parquet(') == 1, \
        "the lake is scanned more than once; materialize and aggregate instead"
    assert 'MATERIALIZED' in body, "the single scan is no longer materialized"
    # Blocking DuckDB work must go through the dedicated pool, never the default
    # executor (it is shared with getaddrinfo -- CI enforces this repo-wide).
    caller = _function_body(_src(), '_build_spend_by_year')
    assert 'to_duckdb_thread(_scan_spend_by_year' in caller


def test_a_failed_scan_hides_the_section_instead_of_publishing_a_wrong_series():
    body = _function_body(_src(), '_populate_spend_by_year')
    assert 'logger.warning' in body, "a failed scan would now be silent"
    assert 'if out.get("available")' in body, \
        "an empty result would be cached for a day"
    view = _view()
    assert '$spendOK' in view, "the page renders the chart without checking availability"


def test_the_lake_scan_is_never_on_the_request_path():
    """⚠⚠ THE ONE THAT BIT ME. With the scan awaited inside the payload, cold
    `/oce/licenses` went 1.9s -> **17.8s** over HTTP — past the 15s timeout in
    ProcurementController, so the ENTIRE page fell back to "not available" on the
    first load after every restart, including the 04:00 cron. The in-process
    measurement was 4.9s and could not see it.

    So: the accessor returns `pending` and starts a background task, and a pending
    payload is NOT cached (a 6h cache on a 20s condition would hide the chart for the
    rest of the day)."""
    src = _src()
    acc = _function_body(src, '_spend_by_year')
    assert 'asyncio.create_task(_populate_spend_by_year' in acc, \
        "the scan is no longer started in the background"
    assert '"pending": True' in acc, "a cold series no longer reports itself as pending"
    assert 'await _build_spend_by_year' not in acc, \
        "the accessor awaits the scan again -- that is the 17.8s cold page"
    # And the endpoint must not freeze that state into the 6h payload cache.
    ep = src.split('async def licenses()')[1]
    assert 'if not (payload.get("spend_by_year") or {}).get("pending"):' in ep, \
        "a pending payload is cached again, so the chart would stay missing for 6h"
    # The page has to say it, or a missing chart looks like a broken feature.
    view = _view()
    assert '$spendPending' in view and 'still loading' in view, \
        "the page no longer distinguishes 'loading' from 'unavailable'"


def test_the_chart_canvas_sits_in_a_bounded_wrapper():
    """#61: a maintainAspectRatio:false canvas with no fixed-height parent grows
    without limit, which took a whole page down once."""
    view = _view()
    m = re.search(r'<div class="db-chart-body"[^>]*height:\s*\d+px[^>]*>\s*'
                  r'<canvas id="licSpendChart">', view)
    assert m, "the spend canvas is no longer inside a fixed-height wrapper"
    assert 'maintainAspectRatio: false' in view


def test_the_chart_reads_the_served_series_and_derives_nothing():
    """The buckets, the exclusion of the partial year and the counts are all the
    API's. A chart that recomputed any of them could disagree with the caption
    printed directly beneath it."""
    view = _view()
    assert '@json($spendYears)' in view, "the chart no longer reads the served series"
    assert '@json($awardYears)' in view, "the award chart no longer reads the served series"
    js = view.split('licAwardChart')[-1]
    for banned in ('getFullYear', 'new Date', '.filter(', '.reduce('):
        assert banned not in js, f"a chart script derives its own data ({banned})"


# ------------------------------------- 6. awarded and paid, side by side


def test_awarded_and_paid_are_separate_series_and_never_added():
    """⚠⚠ A COMMITMENT AND A PAYMENT ARE NOT THE SAME UNIT. Awarded value is a
    multi-year ceiling — 2025 reads $794.1M almost entirely because of one $573.8M
    Microsoft renewal — while paid is cash in that year. Summing or differencing them
    produces a number that means nothing, which is the same error as the composition
    bar that mixed two axes."""
    src = _src()
    assert '"award_by_year": award_by_year' in src and '"spend_by_year": spend_by_year' in src, \
        "the two series are no longer served separately"
    # No arithmetic across the two anywhere in the router or the view.
    for text, where in ((src, 'the router'), (_view(), 'the page')):
        for banned in ('award_by_year"]["total"] -', 'value"] - $spend', "value'] - \\$spend"):
            assert banned not in text, f"{where} subtracts one series from the other"
    view = _view()
    assert 'Awarded is a commitment, not cash' in view, \
        "the page no longer distinguishes a commitment from a payment"


def test_both_series_share_one_window_and_disclose_what_it_dropped():
    """⚠ Two charts on one page reading back different distances is a defect a reader
    cannot see. One constant, one helper, and both report the tail they cut — the
    `by_vendor` lesson (25 of 88 rows under a heading implying all of them)."""
    src = _src()
    assert '_WINDOW_YEARS = 10' in src, "the window constant is gone or renamed"
    assert src.count('_window(buckets, ') == 2, \
        "the two series no longer go through the same window helper"
    for fn in ('_award_by_year', '_build_spend_by_year'):
        body = _function_body(src, fn)
        assert '"dropped"' in body, f"{fn} no longer reports what the window dropped"
    view = _view()
    assert 'outside the window' in view, "the page no longer says the window cut a tail"
    # ⚠ The window is measured from the clock in both, not from the data.
    assert 'int(time.strftime("%Y"))' in _function_body(src, '_award_by_year')


def test_the_award_series_closes_over_every_row():
    """years + partial + dropped + no_date == total_all. A contract with an unparseable
    start date must be reported, not dropped: `_by_year` on this page summed to 262
    contracts under a tile reading 948 for exactly that reason."""
    body = _function_body(_src(), '_award_by_year')
    for key in ('"total_all"', '"no_date"', '"dropped"'):
        assert key in body, f"the award series no longer carries {key}"
    assert 'sum(b["value"] for b in buckets.values()) + no_date_v' in body, \
        "total_all no longer includes the undated rows, so the closure is not checkable"


def test_the_window_helper_is_exhaustive():
    """Every bucket lands in exactly one of the three lists — proved on synthetic
    buckets, so a fourth silent branch cannot appear.

    ⚠ THE CONSTANT IS READ FROM THE SOURCE, NOT RESTATED. The first draft prepended
    its own `_WINDOW_YEARS = 10` before exec-ing the helper, so changing the real
    constant to 15 left this test green — it was measuring a window the code does not
    use. Same defect as a harness that rebuilds the query it is meant to check.
    """
    src = _src()
    body = _function_body(src, '_window')
    assert 'else:' in body and body.count('append(') == 3, \
        "the window helper is no longer a three-way exhaustive split"
    m = re.search(r'(?m)^_WINDOW_YEARS\s*=\s*(\d+)$', src)
    assert m, "_WINDOW_YEARS is gone -- the window is no longer declared in one place"
    n = int(m.group(1))
    ns = {}
    exec(compile(f'_WINDOW_YEARS = {n}\n' + body, '<w>', 'exec'), ns)
    cur = 2027
    buckets = {y: {"year": y, "v": 1} for y in range(cur - n - 7, cur + 1)}
    inside, partial, dropped = ns['_window'](buckets, cur)
    assert len(inside) + len(partial) + len(dropped) == len(buckets), \
        "a bucket fell through all three branches"
    assert [b["year"] for b in partial] == [cur]
    assert [b["year"] for b in inside] == list(range(cur - n, cur)), \
        f"the window is not the last {n} complete years"
    assert len(inside) == n
    assert [b["year"] for b in dropped] == list(range(cur - n - 7, cur - n))


def test_the_page_explains_the_gap_as_master_agreements_not_a_matching_failure():
    """⚠⚠ THE QUESTION A READER WILL ASK. Measured: all 29 MA/MMA agreements have
    zero payments under their own id ($727.4M of awarded value) while 1,440 of 1,572
    ordinary contracts have them. That is what a master agreement IS — agencies buy
    against it on their own purchase orders — so the honest statement is "filed
    elsewhere", not "unmatched". Every figure is served."""
    src = _src()
    assert '_MASTER_PREFIXES' in src and 'def _is_master' in src, \
        "the master/contract split is gone"
    body = _function_body(src, '_build_spend_by_year')
    assert '"by_kind"' in body, "the coverage block no longer carries the id-kind split"
    view = _view()
    assert 'Why the two do not reconcile' in view, \
        "the page no longer explains the gap"
    assert '$spendMaster[\'contracts\']' in view and '$spendPlain[\'paid_contracts\']' in view, \
        "the explanation no longer renders the measured counts"
    assert 'not under the agreement' in view, \
        "the page no longer says where the missing spending actually is"
    # Same discipline as the floor sentence: no typed money in the explanation.
    para = view.split('Why the two do not reconcile')[1][:2000]
    assert not re.search(r'\$\s?\d[\d,.]*\s?[MB]\b', para), \
        "a money figure is typed into the reconciliation sentence — serve it instead"


def test_both_canvases_sit_in_bounded_wrappers():
    view = _view()
    for canvas in ('licAwardChart', 'licSpendChart'):
        m = re.search(r'<div class="db-chart-body"[^>]*height:\s*\d+px[^>]*>\s*'
                      r'<canvas id="%s">' % canvas, view)
        assert m, f"{canvas} is no longer inside a fixed-height wrapper (#61)"
