"""Guards for the Renewal Queue re-scope (docs/DIGITAL-SERVICES-SECTION-PLAN.md §2 Page 2).

Four defects are pinned here, each verified by reintroducing it:

1. the `LEFT JOIN vendors` that DUPLICATED a contract (queue 243 licences vs the
   Licenses page's 242),
2. two independent definitions of the expiring window,
3. the build-your-own flag asked of purchases where it is the wrong question,
4. the queue silently falling back to the old vendor-name scope.

⚠ modules/ is replaced by a MagicMock in conftest.py, so modules under test are
loaded BY PATH — `from modules import licenseclass` in a test yields a mock whose
`CLASSES` contains everything and asserts nothing.

⚠ WHAT THESE GUARDS CANNOT DO: prove the two pages' licence counts actually agree.
That needs both row sets, which exist only against a real database, so it is
checked at runtime by scripts/digital-licence-count-check.sh. What is provable
here is that neither page can define the window itself, and that the queue cannot
resolve vendor ids by a join again — which is the mechanism that made them
disagree in the first place.
"""
import importlib.util
import os
import re
import sys
import types

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
OCE = os.path.join(ROOT, 'api/routers/oce.py')
LICENSES = os.path.join(ROOT, 'api/routers/licenses.py')


def _load(name):
    """Load api/modules/<name>.py by path, with a real errfmt stand-in."""
    errfmt = types.ModuleType('modules.errfmt')
    errfmt.exc_str = lambda e: f"{type(e).__name__}: {e}"
    sys.modules.setdefault('modules.errfmt', errfmt)
    path = os.path.join(ROOT, 'api', 'modules', f'{name}.py')
    spec = importlib.util.spec_from_file_location(f'_{name}', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _strip_comments(src):
    """Python comments only. A guard that reads its own explanation as code fires
    on the prose that documents the ban."""
    return re.sub(r'(?m)^\s*#.*$', '', src)


def _function_body(src, name):
    """The source of one `def`/`async def`, by indentation — so a ban can be scoped
    to the function that must not do a thing while its siblings still do.

    ⚠ Returns None if the def is gone, and every caller asserts on that: a scope
    that matches nothing is the zero-files scanner all over again.
    """
    # ⚠ `[ \t]*`, NOT `\s*`: `\s` matches newlines, so `^(\s*)def` anchored on an
    # earlier blank line, made the first extracted line EMPTY and the indent one too
    # deep. The extraction returned '' and every ban below would have been vacuous —
    # caught only because the caller asserts the block is non-empty and long.
    m = re.search(rf'(?m)^([ \t]*)(?:async\s+)?def\s+{re.escape(name)}\s*\(', src)
    if not m:
        return None
    indent = len(m.group(1))
    lines = src[m.start():].split('\n')
    body = [lines[0]]
    for line in lines[1:]:
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        body.append(line)
    return '\n'.join(body)


# ---------------------------------------------------------------- 1. the join


def test_the_queue_resolves_vendor_ids_by_map_never_by_join():
    """⚠⚠ THE DEFECT: `LEFT JOIN vendors v ON LOWER(c.vendor_name) = LOWER(v."Vendor
    Name")` in the Renewal Queue's row query. 48 vendor names hold more than one row
    in `vendors`, so the join returned a matching contract TWICE — measured, it
    inflated exactly one row (CT1-017-20248805602, Absorb Software's LMS, supplier
    ids 1871820 and 2073456), which is why the queue reported 243 expiring licences
    where the Licenses page reported 242.

    The ban is scoped to `_expiring` on purpose. `_vendors` and `_contracts` serve
    the OLD tag-scope dashboard, whose only job is to keep publishing exactly what
    it published until it is rebuilt; fixing their join would move a published
    number by one row for no reader's benefit. That is a measured decision, not an
    oversight — see the PR.
    """
    src = open(OCE, encoding='utf-8').read()
    body = _function_body(src, '_expiring')
    assert body, "_expiring is gone — this guard is scanning nothing"
    assert len(body.split('\n')) > 100, \
        f"_expiring extracted as only {len(body.split(chr(10)))} lines — the " \
        "indentation walk broke and the ban below is vacuous"

    code = _strip_comments(body)
    assert 'JOIN vendors' not in code, \
        "the Renewal Queue joins `vendors` by name again — that duplicates every " \
        "contract whose vendor name holds more than one supplier id. Use " \
        "modules/vendorids.unique_map()."
    assert 'vendorids.unique_map(' in code, \
        "the queue no longer resolves supplier ids through modules/vendorids"


def test_the_vendor_id_map_refuses_to_guess_between_two_companies():
    """The map's whole value is the uniqueness condition. Without it, an ambiguous
    name resolves to `min(id)` — sending a reader to an arbitrary one of two
    companies, which is worse than an unlinked name (the DOS-crosswalk rule:
    ambiguous -> NULL, never a guess)."""
    src = open(os.path.join(ROOT, 'api/modules/vendorids.py'), encoding='utf-8').read()
    code = _strip_comments(src)
    assert re.search(r'HAVING\s+count\(DISTINCT\s+"PASSPort Supplier-ID"\)\s*=\s*1', code), \
        "vendorids lost its uniqueness condition — the map now guesses"

    vi = _load('vendorids')
    # Folding must be identical on both sides or the map resolves nothing.
    assert vi.key('  Absorb Software Inc ') == 'absorb software inc'
    assert vi.key(None) == ''


def test_the_agency_vendor_table_counts_a_vendor_once():
    """⚠⚠ THE SAME JOIN, ON A PUBLISHED PAGE OUTSIDE THIS SECTION. The agency
    profile's vendors table resolved supplier ids with `LEFT JOIN vendors ON
    LOWER(TRIM(vendor_name))` and then GROUPED BY that id, so a duplicate-registered
    vendor was listed twice. Measured on prod 2026-08-12: 20 duplicated rows across
    12 agencies — Department for the Aging listed ALLEN AME CHURCH twice at
    $16,126,468 each.

    ⚠ The symptom worth pinning is a page disagreeing with itself: `stats.vendors` is
    COUNT(DISTINCT vendor_name) and was right, while the Vendors badge counted these
    rows and read 1-3 higher. Two vendor counts on one page.

    ⚠ And the GROUP BY is the load-bearing half. Dropping the join while leaving
    `GROUP BY c.vendor_name, v."PASSPort Supplier-ID"` would not compile; keeping the
    join while grouping by name alone would silently pick an arbitrary id. Both are
    banned by requiring the name-only grouping AND the map.
    """
    src = open(OCE, encoding='utf-8').read()
    body = _function_body(src, 'get_agency_procurement')
    assert body, "get_agency_procurement is gone — this guard is scanning nothing"
    assert len(body.split('\n')) > 80, \
        "the extracted endpoint is too short — the indentation walk broke"
    code = _strip_comments(body)
    assert 'JOIN vendors' not in code, \
        "the agency vendors table joins `vendors` by name again — that lists a " \
        "duplicate-registered vendor twice. Use modules/vendorids.unique_map()."
    assert 'vendorids.unique_map(' in code, \
        "the agency vendors table no longer resolves ids through the shared map"
    assert 'GROUP BY c.vendor_name\n' in code, \
        "the vendor rollup groups by something other than the name alone"
    # A vendor is one row per name, so the payload count must be able to equal
    # stats.vendors, which is COUNT(DISTINCT vendor_name).
    assert 'COUNT(DISTINCT vendor_name) as count' in code, \
        "stats.vendors no longer counts distinct names — the two figures on the " \
        "page can disagree again"


def test_both_pages_resolve_vendor_ids_through_the_same_module():
    """The Licenses page had this right and the queue did not; the fix is one owner,
    not two correct copies."""
    for path in (OCE, LICENSES):
        code = _strip_comments(open(path, encoding='utf-8').read())
        assert 'vendorids.unique_map(' in code, \
            f"{os.path.basename(path)} resolves supplier ids some other way again"
    lic = _strip_comments(open(LICENSES, encoding='utf-8').read())
    assert 'HAVING count(DISTINCT' not in lic, \
        "the Licenses page grew its own copy of the vendor-id query back"


# ------------------------------------------------------- 2. the shared window


def test_neither_page_defines_the_expiring_window_itself():
    """⚠ The horizon was typed as a literal in BOTH files. They agreed by
    coincidence; nothing would have caught an edit to one of them, and the two
    figures drifting apart is silent by construction."""
    lw = _load('licensewindow')
    assert lw.HORIZON == '2030-01-01'

    for path in (OCE, LICENSES):
        code = _strip_comments(open(path, encoding='utf-8').read())
        assert lw.HORIZON not in code, (
            f"{os.path.basename(path)} types the expiring horizon itself — it must "
            "come from modules/licensewindow.HORIZON, or the two pages can drift")
        assert 'licensewindow.' in code, \
            f"{os.path.basename(path)} no longer uses the shared window"

    # The SQL form must be built FROM the constant, not beside it.
    src = open(os.path.join(ROOT, 'api/modules/licensewindow.py'), encoding='utf-8').read()
    assert "{HORIZON}" in src, \
        "licensewindow's SQL clause hardcodes a date instead of interpolating HORIZON"


def test_the_window_is_the_same_window_in_both_directions():
    """Boundaries, because an inclusive/exclusive slip is exactly the kind of
    difference that shows up as one page reading one contract higher."""
    lw = _load('licensewindow')
    today = '2026-08-12'
    assert lw.is_expiring('12/31/2029', today) is True          # inside
    assert lw.is_expiring('01/01/2030', today) is False         # exclusive upper
    assert lw.is_expiring('08/12/2026', today) is True          # inclusive lower
    assert lw.is_expiring('08/11/2026', today) is False         # already ended
    # Unusable dates are refused rather than parsed into an invented one — the SQL
    # side refuses the same rows with its LENGTH check.
    assert lw.is_expiring('', today) is False
    assert lw.is_expiring(None, today) is False
    assert lw.is_expiring('2029-12-31', today) is False         # wrong format
    assert lw.is_expiring('1/1/2029', today) is False           # not 10 chars

    clause = lw.sql_clause('c')
    assert 'LENGTH(c.end_date) = 10' in clause
    assert ">= CURRENT_DATE" in clause and f"< DATE '{lw.HORIZON}'" in clause


# -------------------------------------------------- 3. the class-gated flag


def _flags(**kw):
    from routers.oce import _review_flags
    row = {"procurement_method": "Competitive Sealed Bid", "award_amount": 5000,
           "contract_title": kw.pop("title", "")}
    return {f["key"]: f for f in _review_flags(
        row, 900, True, None, None, None, None,
        kw.pop("enrich", None), kw.pop("purchase_class", None))}


def test_build_your_own_is_withdrawn_outside_the_software_licence_class():
    """⚠⚠ THE LESSON THIS ENCODES. `build_vs_buy` asks "could the City build this?".
    For infrastructure that is the WRONG QUESTION, so it answers `low` and ends the
    conversation — which is how Amazon Web Services sat at $6.80M rated `low` and
    appeared in no replaceability view at all, against a `high` set of $10.13M. The
    Licenses page fixed it by hiding the rating outside `software-licence`. The queue
    was still asking every row.
    """
    high = {"build_vs_buy": "high", "rationale": "Commodity ticketing tool."}

    # No class at all (every non-licence contract) -> unchanged behaviour. Gating
    # these out would delete the flag where the heuristic is most apt.
    assert 'build_your_own' in _flags(enrich=high)
    assert 'build_your_own' in _flags(enrich=high, purchase_class={})

    # software-licence -> the substitution question is the right one.
    assert 'build_your_own' in _flags(
        enrich=high, purchase_class={"class": "software-licence",
                                     "lever": "open-source-substitute"})

    # Every other class -> withdrawn, and REPLACED, not silently dropped.
    for cls, lever, label in (
            ("managed-hosting", "benchmark-then-self-host", "Benchmark the price"),
            ("cloud-infrastructure", "price-and-rightsizing", "Benchmark the price"),
            ("support-maintenance", "is-the-paid-tier-needed", "Is the paid tier needed?"),
            ("content-subscription", "is-the-content-needed", "Is the content needed?"),
            ("professional-services", "scope-and-rate-review", "Scope and rate review"),
    ):
        got = _flags(enrich=high, purchase_class={"class": cls, "lever": lever})
        assert 'build_your_own' not in got, f"{cls} is still asked the build question"
        assert 'class_lever' in got, f"{cls} lost its own lever instead of gaining one"
        assert got['class_lever']['label'] == label
        # The reason must name the class AND carry the original rationale, or the
        # withdrawal is unauditable.
        assert cls.replace('-', ' ') in got['class_lever']['reason']
        assert 'Commodity ticketing tool.' in got['class_lever']['reason']

    # The KEYWORD path is gated too — it is the same question by another route.
    got = _flags(title="Citywide WEBSITE and portal",
                 purchase_class={"class": "managed-hosting",
                                 "lever": "benchmark-then-self-host"})
    assert 'build_your_own' not in got and 'class_lever' in got

    # A rating of medium/low produces NEITHER flag: the gate must not invent a
    # lever flag for a contract nobody flagged.
    for rating in ("medium", "low"):
        got = _flags(enrich={"build_vs_buy": rating, "rationale": "x"},
                     purchase_class={"class": "managed-hosting",
                                     "lever": "benchmark-then-self-host"})
        assert 'build_your_own' not in got and 'class_lever' not in got


def test_every_class_has_a_lever_label_and_the_labels_come_from_licenseclass():
    """A class whose lever has no label would render "Wrong question asked", which
    tells a reviewer nothing. Every lever in licenseclass except the substitution
    one must be labelled."""
    from routers.oce import CLASS_LEVER_LABELS, SUBSTITUTION_CLASS
    lc = _load('licenseclass')
    assert SUBSTITUTION_CLASS in lc.CLASSES
    missing = [c for c in lc.CLASSES if c != SUBSTITUTION_CLASS
               and lc.LEVER_FOR[c] not in CLASS_LEVER_LABELS]
    assert not missing, f"no lever label for {missing} — those rows lose their question"
    # ⚠ Hosting and cloud must point at a PRICE review; classifying a line as
    # infrastructure is not a defence of it.
    for c in ("managed-hosting", "cloud-infrastructure"):
        assert 'price' in CLASS_LEVER_LABELS[lc.LEVER_FOR[c]].lower() \
            or 'benchmark' in CLASS_LEVER_LABELS[lc.LEVER_FOR[c]].lower()


def test_the_queue_resolves_class_through_licenseclass_at_product_grain():
    """Both pages must resolve a contract's class through the SAME resolver, or they
    can disagree about which question a contract deserves. Product grain matters:
    the family answer covered all 23 Microsoft contracts and filed $68.9M of support
    as a licence."""
    body = _function_body(open(OCE, encoding='utf-8').read(), '_expiring')
    code = _strip_comments(body)
    assert 'licenseclass.resolve(' in code, \
        "the queue derives a purchase class some other way"
    assert 'license_product_class' in code, \
        "the queue reads only family classes — product overrides are the fix for " \
        "Microsoft's support tail and must be consulted"
    assert re.search(r'licenseclass\.resolve\(\s*product,\s*family,\s*prod_classes,\s*fam_classes\s*\)', code), \
        "resolve() is no longer given both layers in the documented order"


def test_the_view_hides_the_replaceability_rating_outside_software_licence():
    """The API withdrawing the flag is half of it; the dossier still rendering
    "High replaceability" would contradict the withdrawn flag on the same row."""
    view = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-expiring.blade.php')
    src = open(view, encoding='utf-8').read()
    assert re.search(r"\$showBvb\s*=.*software-licence", src, re.S), \
        "the view no longer gates the build-vs-buy block on the purchase class"
    assert '@if($showBvb)' in src, "the build-vs-buy block is no longer gated"


# ------------------------------------------------------------- 4. the scope


def test_the_queue_cannot_silently_fall_back_to_the_vendor_name_scope():
    """⚠ The queue is on the derived scope AHEAD of the dashboard, so it must not
    read DIGITAL_SCOPE. If it did, the global gate saying `tag` — which it does
    today — would put this page back on the 85.2%-precision vendor-name scope, and
    its licence count back to disagreeing with the Licenses page."""
    ds = _load('digitalscope')
    for env in (ds.MODE_ENV, ds.QUEUE_MODE_ENV):
        os.environ.pop(env, None)
    try:
        assert ds.queue_mode() == 'derived', "the queue no longer defaults to the derived scope"
        # ⚠ This used to assert the GLOBAL gate still defaulted to `tag`. It no longer
        # does — the Overview rebuild flipped it 2026-08-13 (#247), and that claim now
        # belongs to test_overview_rebuild.py, which owns the flip. Left as a note
        # rather than deleted silently: the guard was right to fail here.
        assert ds.mode() in ds.MODES

        # The global gate must NOT drag the queue back, in EITHER direction.
        os.environ[ds.MODE_ENV] = 'tag'
        assert ds.queue_mode() == 'derived', \
            "DIGITAL_SCOPE=tag silently rolled the queue back to the vendor-name scope"

        # An explicit, page-named lever exists for a real rollback.
        os.environ[ds.QUEUE_MODE_ENV] = 'tag'
        assert ds.queue_mode() == 'tag'
        # …and a typo in it must not change what the page measures.
        os.environ[ds.QUEUE_MODE_ENV] = 'derived-ish'
        assert ds.queue_mode() == 'derived'
    finally:
        for env in (ds.MODE_ENV, ds.QUEUE_MODE_ENV):
            os.environ.pop(env, None)

    # A section-level override is what lets one payload hold two scopes while the
    # Overview waits for its rebuild.
    src = open(os.path.join(ROOT, 'api/modules/digitalscope.py'), encoding='utf-8').read()
    assert 'mode_override' in src, "load() lost its per-section override"


def test_the_payload_states_its_scope_and_the_page_reads_it_from_there():
    """The page must not claim a scope in copy. Two pages on two scopes is
    temporary and deliberate; a reader comparing them has to be able to see it, and
    a template literal would keep saying "derived" after a rollback."""
    code = _strip_comments(open(OCE, encoding='utf-8').read())
    body = _function_body(code, '_expiring')
    assert '"scope"' in body and 'qsc.mode' in body, \
        "the queue payload no longer reports which scope produced it"

    view = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-expiring.blade.php')
    src = open(view, encoding='utf-8').read()
    assert "$expiring['scope']" in src, "the view no longer reads the scope from the payload"
    assert '$expPositiveScope' in src, "the scope-dependent copy is gone"


def test_the_retired_nontech_disclosure_is_replaced_not_deleted():
    """⚠ `nontech_excluded` goes to 0 on a positive scope, so the old "105 likely
    non-tech contracts are hidden — show them" note stops rendering. Losing an
    honesty device silently is not the same as retiring it: the page must state that
    nothing is filtered out, and must still SHOUT if the measured number is ever
    non-zero on the positive scope, because that would mean the scope is broken."""
    view = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-expiring.blade.php')
    src = open(view, encoding='utf-8').read()
    assert 'Nothing is filtered out of this queue' in src, \
        "the replacement scope statement is gone — the disclosure was dropped, not retired"
    # The measured value is still consulted, so a broken scope cannot hide.
    scope_block = src[src.index('Nothing is filtered out of this queue'):]
    assert "nontech_excluded" in scope_block[:1200], \
        "the positive-scope copy no longer checks the measured non-tech count"

    # And the API must keep MEASURING it rather than hardcoding zero.
    code = _strip_comments(open(OCE, encoding='utf-8').read())
    assert "sum(1 for e in enriched if e['tech_relevant'] is False)" in code, \
        "nontech_excluded is no longer measured — a zero that cannot be wrong is " \
        "indistinguishable from a check that never ran"


def test_licence_rows_link_to_their_family_page():
    """The queue dead-ended exactly where the section's richest context lives.
    ⚠ By SLUG, not display name: /oce/licenses/family/{slug} resolves by slug so a
    curated merge renaming a family cannot break every link."""
    code = _strip_comments(open(OCE, encoding='utf-8').read())
    assert "'license_family_slug'" in code, "the payload carries no family slug"
    assert 'slug, is_generic FROM license_family' in code, \
        "the family lookup no longer selects the slug (and the generic flag)"

    view = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-expiring.blade.php')
    src = open(view, encoding='utf-8').read()
    assert "research.digital-reform.license-family" in src, \
        "licence rows no longer link to their family page"
    assert "license_family_slug" in src, "the link is built from something other than the slug"
