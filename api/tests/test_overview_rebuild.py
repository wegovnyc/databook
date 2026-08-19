"""Guards for the Overview rebuild (docs/DIGITAL-SERVICES-SECTION-PLAN.md §2 Page 1).

The Overview was the last page on the vendor-name scope. Flipping it publishes
3,343 -> 4,397 contracts and $6.5B -> $10.6B, and replaces the page's headline with
a composition partition. What can go wrong is specific:

1. the partition stops being a partition (a segment lost, or one contract in two),
2. the bar and its drill-down drift apart, so a segment's table does not add up to
   the segment it was reached from,
3. "Digital Share" or the tagged-vendor tile comes back — the two figures that
   made a physical-guard company rank fifth on a technology page,
4. the pipeline's ceilings get added to a total,
5. the three pages start explaining their scope three different ways again.

⚠ modules/ is a MagicMock under conftest.py, so modules are loaded BY PATH.
"""
import importlib.util
import os
import re
import sys
import types

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
OCE = os.path.join(ROOT, 'api/routers/oce.py')
VIEWS = os.path.join(ROOT, 'app/resources/views')
OVERVIEW = os.path.join(VIEWS, 'procurement/digital-reform.blade.php')
LICENSES = os.path.join(VIEWS, 'procurement/digital-reform-licenses.blade.php')
EXPIRING = os.path.join(VIEWS, 'procurement/digital-reform-expiring.blade.php')
SCOPE_NOTE = os.path.join(VIEWS, 'sub/digital-scope-note.blade.php')


def _load(name):
    errfmt = types.ModuleType('modules.errfmt')
    errfmt.exc_str = lambda e: f"{type(e).__name__}: {e}"
    sys.modules.setdefault('modules.errfmt', errfmt)
    spec = importlib.util.spec_from_file_location(
        f'_{name}', os.path.join(ROOT, 'api', 'modules', f'{name}.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _strip_php_comments(src):
    """Blade/PHP comments, so a guard does not read its own explanation as copy."""
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?m)//[^\n]*$', '', src)


# --------------------------------------------------------- 1. the partition


def test_the_composition_is_a_partition_and_it_closes():
    """⚠⚠ ONE BUCKET PER CONTRACT. `licences` is a FLAG that cuts across every
    function — measured, 400 of 584 Data/analytics contracts are licences — so a bar
    with "licences" beside "hardware" either double-counts or silently drops. The
    partition is: bought as a licence -> licence; otherwise named by function.

    This is the `_by_year` lesson at a different grain: that calendar quietly summed
    to 262 contracts under a tile reading 948, because rows fell into a gap nothing
    reconciled.
    """
    ts = _load('techsegments')
    rows = [
        {"is_license": True,  "function_category": "Data/analytics", "value": 100.0, "ended": False},
        {"is_license": True,  "function_category": "Office productivity", "value": 50.0, "ended": True},
        {"is_license": False, "function_category": "Data/analytics", "value": 25.0, "ended": False},
        {"is_license": False, "function_category": "Staffing/consulting", "value": 10.0, "ended": True},
        {"is_license": False, "function_category": "", "value": 5.0, "ended": False},
        {"is_license": False, "function_category": None, "value": 1.0, "ended": False},
    ]
    segments, bar = ts.rollup(rows)
    assert sum(a["contracts"] for a in segments) == len(rows), "the partition lost rows"
    assert abs(sum(a["value"] for a in segments) - sum(r["value"] for r in rows)) < 1e-9
    # Every row lands in exactly one segment, so no segment may double-count.
    assert len({a["segment"] for a in segments}) == len(segments)

    by = {a["segment"]: a for a in segments}
    # Both licences are in the licence segment, whatever their function.
    assert by[ts.LICENCE_SEGMENT]["contracts"] == 2
    # …and the non-licence Data/analytics contract is NOT counted there.
    assert by["Data/analytics"]["contracts"] == 1
    # ⚠ THE CROSS-CUT: the function segment must say how many of its job's contracts
    # went to the licence segment, or the partition hides the page's own argument.
    assert by["Data/analytics"]["licence_siblings"] == 1
    assert by["Staffing/consulting"]["licence_siblings"] == 0
    # A per-segment "licences" count would be vacuous (all or nothing) and is gone.
    assert "licences" not in by["Data/analytics"]
    # The unclassified sentinel is its own segment, never folded into a real one.
    assert by[ts.UNCLASSIFIED_SEGMENT]["contracts"] == 2

    # active is by subtraction from the same rows, never a second predicate
    assert by["Data/analytics"]["active_contracts"] == 1
    assert by["Staffing/consulting"]["active_contracts"] == 0

    # The bar is capped and the fold is DISCLOSED with its count.
    assert sum(b["contracts"] for b in bar) == len(rows), "the bar dropped rows"
    other = [b for b in bar if b["segment"] == ts.OTHER_SEGMENT]
    if other:
        assert other[0]["folded"] >= 1 and other[0]["segments"], \
            "the folded band does not say what it folded"
        assert not other[0]["slug"], "the folded band must not pretend to be drillable"


def test_the_api_serves_the_partitions_own_closure():
    src = open(OCE, encoding='utf-8').read()
    assert 'async def _composition()' in src, "the composition section is gone"
    assert '"composition": composition' in src, "composition is not in the payload"
    for key in ('"contracts": sum(a["contracts"] for a in segments)',
                '"bar_floor_share": techsegments.BAR_MIN_SHARE'):
        assert key in src, f"the payload no longer carries {key} — the page cannot be checked"
    # ⚠ Composition must REFUSE tag mode rather than approximate it: amendment-row
    # grain would count a contract once per amendment and the bar would add up to
    # nothing real.
    assert 'sc.mode != "derived"' in src, \
        "composition no longer refuses the amendment-grain scope"


# ------------------------------------------------- 2. the bar and its drill-down


def test_the_drill_down_uses_the_same_definition_as_the_bar():
    """A segment's contract table must be the segment the bar counted. The predicate
    lives in techsegments and the router resolves the slug against the segments it
    just computed — not by reversing the slug, which is lossy on free text."""
    ts = _load('techsegments')
    segs, _ = ts.rollup([
        {"is_license": False, "function_category": "Telecom/network", "value": 1.0, "ended": False},
        {"is_license": True, "function_category": "x", "value": 1.0, "ended": False},
    ])
    assert ts.resolve_slug("telecom-network", segs) == "Telecom/network"
    assert ts.resolve_slug("no-such-segment", segs) == "", \
        "an unknown slug must filter nothing, not empty the table"
    assert ts.resolve_slug("", segs) == ""

    # ⚠ The `NOT is_license` half: without it a function drill-down returns the
    # licence contracts the bar counted elsewhere.
    sql, params = ts.sql_predicate("Telecom/network", 3)
    assert "NOT e.is_license" in sql and "$3" in sql and params == ["Telecom/network"], sql
    lic_sql, lic_params = ts.sql_predicate(ts.LICENCE_SEGMENT, 3)
    assert lic_sql == "e.is_license" and lic_params == []
    # Free text is BOUND, never interpolated.
    assert "Telecom" not in sql

    src = open(OCE, encoding='utf-8').read()
    assert 'techsegments.resolve_slug(contract_segment, composition_segments)' in src, \
        "the drill-down no longer resolves against the computed segments"
    assert 'composition = await _composition()' in src, \
        "composition must run before the gather, or the drill-down has nothing to " \
        "resolve against"
    # And the page must say what it is filtered to.
    view = _strip_php_comments(open(OVERVIEW, encoding='utf-8').read())
    assert '$segSel' in view and 'contract_segment' in view, \
        "the page no longer shows a clearable chip for the segment filter"


# --------------------------------------------- 3. the two retired figures


def test_digital_share_and_the_tagged_vendor_tile_are_gone_for_good():
    """⚠⚠ THE FIGURES THIS REBUILD EXISTS TO DELETE. "Digital Share" divided a
    vendor's tagged spend by their TOTAL City spend, so Inter-Con SECURITY SYSTEMS —
    physical guards — ranked 5th at "100% digital share". The "Digital Vendors: 200"
    tile counted a hand-kept name list and called it a measurement.
    """
    src = open(OCE, encoding='utf-8').read()
    assert 'digital_share' not in src, \
        "digital_share is back in the API — it is a ratio against unrelated spend"
    # ⚠ COMMENT-STRIPPED, or this fires on the Blade comment that documents the
    # retirement — the scanner-reads-its-own-explanation trap, which this file hit on
    # its first run. The API check above can use raw source because `digital_share` is
    # a key name no prose needs.
    body = _strip_php_comments(open(OVERVIEW, encoding='utf-8').read())
    assert 'Digital Share' not in body and 'digital_share' not in body, \
        "the Digital Share column is back on the page"
    assert 'Tagged in Database' not in body, "the tagged-vendor tile is back"
    assert 'Digital Service Reform' not in body, \
        "the retired h1 is back — the page is 'Digital Services Analysis: Overview'"
    assert 'Digital Services Analysis: Overview' in body, "the h1 is missing"
    # The honest replacements must be present, not merely the old ones absent.
    for want in ('Technology contracts', 'Technology value', 'not known to have ended'):
        assert want in body, f"the rebuilt page lost '{want}'"


def test_the_vendor_table_counts_only_confirmed_technology():
    src = open(OCE, encoding='utf-8').read()
    i = src.index('async def _vendors()')
    j = src.index('async def _contracts()')
    body = src[i:j]
    assert 'FILTER (WHERE {dig})' in body, \
        "the vendor table no longer restricts its counts to confirmed-tech contracts"
    assert 'total_award_all' not in body and 'total_contract_count' not in body, \
        "the whole-book columns are back; they only ever fed digital_share"
    # ⚠ `sells` is capped, and the cap is disclosed — Dell resolves to 18 families.
    assert "'sells': [f for f, _ in fams[:4]]" in body and "'sells_total': len(fams)" in body, \
        "the reseller annotation lost its cap or its full count"


# ------------------------------------------------------ 4. the pipeline


def test_the_pipeline_is_a_ceiling_and_lives_in_exactly_one_place():
    """⚠⚠ NEVER MERGED INTO A TOTAL. One leaked row adds a $1.2B ceiling to a page
    whose headline is smaller than that. The value key is `ceiling`, so summing it
    into `value` requires renaming it first.

    ⚠ And exactly ONE page computes it. Scoped to licence vendors it was 121
    agreements / $1.61B; scoped to the technology universe it is 257 / $3.22B. Two
    pages publishing two figures for one question is the defect this section spent a
    week removing.
    """
    pv = _load('pipelinevehicles')
    assert 'contract_id IS NULL' in pv._SQL, "the pipeline no longer selects UNREGISTERED rows"
    assert 'DISTINCT ON (epin)' in pv._SQL, "the pipeline is no longer deduped on epin"

    src = open(OCE, encoding='utf-8').read()
    assert 'pipelinevehicles.load(' in src, "the Overview no longer serves the pipeline"
    assert '"pipeline": pipeline' in src, "the pipeline is not in the payload"

    lic = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert 'contract_id IS NULL' not in lic, \
        "the Licenses page computes its own pipeline again — there must be one figure"

    # The licence VIEW keeps a pointer, not a second table.
    licview = _strip_php_comments(open(LICENSES, encoding='utf-8').read())
    assert 'research.digital-reform' in licview and 'pipeline' in licview, \
        "the Licenses page lost its pointer to the pipeline block"
    assert '$pipeRows' not in licview, "the Licenses page still renders pipeline rows"

    # The Overview must call it a ceiling in the copy a reader sees, not just in the key.
    ov = _strip_php_comments(open(OVERVIEW, encoding='utf-8').read())
    assert 'ceiling' in ov.lower() and 'not spend' in ov.lower(), \
        "the never-add-this framing is gone from the pipeline block"
    assert "$pipe['ceiling']" in ov, "the block no longer renders the ceiling key"
    # ⚠ And it must not be added to anything: no arithmetic mixing the two.
    assert not re.search(r"stats\['total'\][^\n]*pipe\[", ov), \
        "a total is being combined with a pipeline ceiling"


# --------------------------------------------------- 5. one scope note


def test_all_three_pages_share_one_scope_note():
    """⚠ Three pages explaining their scope three different ways is how the section
    ended up with two universes and no way for a reader to notice."""
    assert os.path.exists(SCOPE_NOTE), "the shared scope note is gone"
    note = open(SCOPE_NOTE, encoding='utf-8').read()
    for page in (OVERVIEW, LICENSES, EXPIRING):
        src = open(page, encoding='utf-8').read()
        assert "@include('sub.digital-scope-note'" in src, \
            f"{os.path.basename(page)} no longer includes the shared scope note"
    # It must state the blind spot and the accuracy, and read its mode from the payload.
    body = _strip_php_comments(note)
    assert 'registration' in body, "the note no longer states the registration blind spot"
    assert '95.8%' in body and '97.5%' in body, \
        "the measured classifier accuracy is gone from the note"
    assert '$scope' in note, "the note asserts a scope instead of reading it from the payload"
    # ⚠ Typed percentages are allowed HERE and only here, because the page cannot
    # compute an offline eval — but they must carry the sample they came from, or they
    # are a claim rather than a measurement.
    assert '120-contract sample' in body, \
        "the accuracy figures no longer say what they were measured on"


def test_the_scope_note_percentages_are_the_only_typed_ones_in_the_overview():
    """The licences page already bans hardcoded percentages in its copy; the Overview
    now makes the same promise. Its figures all come from the payload."""
    body = _strip_php_comments(open(OVERVIEW, encoding='utf-8').read())
    # Strip Blade expressions — a computed `{{ number_format(...) }}%` is the CORRECT
    # way to print a percentage and must not be mistaken for a literal.
    body = re.sub(r'\{\{.*?\}\}', '', body, flags=re.S)
    body = re.sub(r'@php.*?@endphp', '', body, flags=re.S)
    # …and CSS/style attributes, where a width percentage is layout, not a claim,
    # plus <script>, where `cutout: '60%'` is a chart option. ⚠ A scanner that reads
    # CODE as COPY reports problems that are not there — the mirror of the guard that
    # scanned zero files, and this assertion caught itself doing it.
    body = re.sub(r'style="[^"]*"', '', body)
    body = re.sub(r'<style>.*?</style>', '', body, flags=re.S)
    body = re.sub(r'<script.*?</script>', '', body, flags=re.S)
    literals = set(re.findall(r'\b\d{1,3}(?:\.\d)?%', body))
    assert not literals, (
        f"hardcoded percentages in the Overview's copy: {sorted(literals)} — compute "
        "them in the API and render the payload key")


def test_the_scope_gate_now_defaults_to_the_measured_scope():
    """⚠ The flip itself, in code where it is reviewable — not an env var on one box
    that no history records. `DIGITAL_SCOPE=tag` must still roll it back."""
    ds = _load('digitalscope')
    for env in (ds.MODE_ENV, ds.QUEUE_MODE_ENV):
        os.environ.pop(env, None)
    try:
        assert ds.mode() == 'derived', "the scope gate no longer defaults to derived"
        os.environ[ds.MODE_ENV] = 'tag'
        assert ds.mode() == 'tag', "the rollback lever is gone"
        os.environ[ds.MODE_ENV] = 'nonsense'
        assert ds.mode() == 'derived', "an invalid mode must fall back to the default"
    finally:
        os.environ.pop(ds.MODE_ENV, None)
    # The tag path must still EXIST — deleting it should be a deliberate retirement.
    src = open(os.path.join(ROOT, 'api/modules/digitalscope.py'), encoding='utf-8').read()
    assert "FROM vendor_tags" in src, \
        "the tag mode is gone entirely; that is a retirement, not a default change"


def test_the_controller_passes_every_payload_key_the_overview_reads():
    """⚠⚠ THE BUG NO SOURCE-SCANNING GUARD IN THIS FILE CAUGHT, and the reason to
    render a page before believing it works.

    The API served `composition`, `pipeline` and `scope`; the Blade read them; every
    guard here passed — and the page rendered with **no composition bar and no
    pipeline block at all**, because ProcurementController's view-data array never
    passed them through. `$composition ?? []` degraded politely, so there was no
    error, no warning and no visible failure. Only fetching the page found it.

    Same shape as the org chart, which selected a parent it never rendered: the API
    having a value proves nothing about the page receiving it. The seam between them
    needs its own assertion.
    """
    ctrl = open(os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php'),
                encoding='utf-8').read()
    view = _strip_php_comments(open(OVERVIEW, encoding='utf-8').read())

    # Payload-backed variables the rebuilt Overview reads. ⚠ Each must be handed over
    # by the controller; a key that only exists in the API is invisible to the page.
    for var, key in (('$composition', 'composition'),
                     ('$pipeline', 'pipeline'),
                     ('$scope', 'scope'),
                     ('$stats', 'stats'),
                     ('$contracts', 'contracts'),
                     ('$vendors', 'vendors'),
                     ('$expiring', 'expiring')):
        assert var in view, f"the Overview no longer reads {var} — update this list"
        assert re.search(rf"'{key}'\s*=>", ctrl), \
            (f"ProcurementController does not pass '{key}' to the view, so the page "
             f"reads {var} as empty and renders that section as nothing — silently")

    # And the drill-down parameter must reach the API, or clicking a segment does
    # nothing at all.
    assert "'contract_segment' => $contractSegment" in ctrl, \
        "the segment drill-down is not forwarded to the API"
    assert "input('contract_segment'" in ctrl, \
        "the controller never reads the segment parameter from the request"
