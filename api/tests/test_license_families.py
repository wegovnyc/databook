"""Guards for the licence-family mapping and the Licenses page.

The mapping is what stops the page telling lies of omission: ungrouped,
`ShotSpotter` and `SoundThinking` read as two products when they are one company
before and after a rename, and `ArcGIS`/`ESRI ArcGIST` split Esri in half.
"""
import csv
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SEED = os.path.join(ROOT, 'api/seed/license_family_curated.csv')


def _norm(s):
    """Must stay identical to build_license_families.norm()."""
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", s or "")).strip().upper()


def _rules():
    with open(SEED, newline='', encoding='utf-8') as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith('#')]
    out = {}
    for row in csv.DictReader(lines):
        raw = (row.get('product') or '').strip()
        fam = (row.get('family') or '').strip()
        if raw and fam:
            out[_norm(raw)] = (fam, (row.get('generic') or '').strip().lower()
                               in ('1', 'true', 'yes', 'y'))
    return out


def test_norm_matches_the_builders_definition():
    """⚠ A harness that reimplements the code's definitions measures a DIFFERENT
    system. This caught a real error once already: a measurement script used a
    wider suffix list than the code and put two wrong examples into a docstring.
    So pin _norm here against the builder's actual source.
    """
    src = open(os.path.join(ROOT, 'api/build_license_families.py'), encoding='utf-8').read()
    body = re.search(r'def norm\(s: str\) -> str:.*?return (.+?)\n', src, re.DOTALL)
    assert body, "build_license_families.norm() not found — did it get renamed?"
    expr = body.group(1)
    assert '[^A-Za-z0-9]+' in expr and '.strip().upper()' in expr, expr


def test_comment_lines_never_become_curated_rules():
    """⚠ THE BUG THIS EXISTS FOR. csv.DictReader does not know about `#`
    comments, and a comment containing a comma ("# different purchases, prefer
    leaving them separate") parses as product="# different purchases" with a
    NON-EMPTY family — installing itself as a real merge rule. The loader strips
    comments first; this proves it stayed stripped.
    """
    rules = _rules()
    assert rules, "no rules parsed at all — the seed or the parser is broken"
    for key, (fam, _generic) in rules.items():
        assert not key.startswith('#'), f"comment leaked into a rule: {key}"
        assert not fam.startswith('#'), f"comment leaked into a family: {fam}"
        # A real product key is short; prose is not.
        assert len(key) < 70, f"suspiciously long key, likely prose: {key!r}"


def test_the_measured_fragmentation_cases_are_covered():
    """The specific splits measured on prod 2026-08-10. Each of these was a real
    misreading on the page before it was curated, so each stays pinned."""
    rules = _rules()
    def fam(p):
        return rules.get(_norm(p), (None, None))[0]

    # A rename a string match cannot possibly see.
    assert fam('ShotSpotter') == fam('SoundThinking') is not None
    # Vendor name present vs absent halved Esri's footprint (12 vs 8 contracts).
    assert fam('ArcGIS') == fam('ESRI ArcGIS') == fam('Esri ArcGIS') is not None
    # One word vs two.
    assert fam('Check Point') == fam('Checkpoint') is not None
    assert fam('Micro Focus') == fam('Microfocus') is not None
    # Acronym vs full name.
    assert fam('AWS') == fam('Amazon Web Services') is not None
    # Concentration depends on this one: 47% of licence value is Microsoft.
    for p in ('Microsoft ELA', 'Microsoft Premier Support', 'Microsoft Unified Support'):
        assert fam(p) == 'Microsoft', p


def test_case_and_punctuation_variants_need_no_rule():
    """The auto layer must handle these, or the curated file becomes a
    never-ending list of spellings and the real merges get lost in it."""
    assert _norm('Solarwinds') == _norm('SolarWinds')
    assert _norm('Accellion/Kiteworks') == _norm('Accellion Kiteworks')
    assert _norm('CommVault') == _norm('Commvault')
    assert _norm('ARCHIBUS') == _norm('Archibus')
    assert _norm('E-builder') == _norm('e-Builder')
    # ...and must NOT collapse genuinely different tokens.
    assert _norm('Check Point') != _norm('Checkpoint')
    assert _norm('Quest') != _norm('Quest Toad')


def test_generic_values_are_flagged_and_never_given_a_product_family():
    """⚠ `Various`/`Unknown`/`EHR System` are what the classifier emits when it
    CANNOT identify a product. Presenting them as software would invent products
    that do not exist, so they must carry generic=1 and a family that reads as
    unidentified — never a plausible-looking vendor name.
    """
    rules = _rules()
    for p in ('Various', 'Unknown', 'Engineering Software', 'EHR System',
              'Project Management Software'):
        got = rules.get(_norm(p))
        assert got, f"{p} has no rule — it would be ranked as a real product"
        fam, generic = got
        assert generic is True, f"{p} must be flagged generic"
        assert 'unidentified' in fam.lower(), f"{p} mapped to a product-like family: {fam}"

    # And nothing NON-generic may claim the unidentified family, or real products
    # would be hidden inside the bucket.
    for key, (fam, generic) in rules.items():
        if 'unidentified' in fam.lower():
            assert generic is True, f"{key} uses the unidentified family but is not generic"


def test_builder_refuses_to_publish_a_suspiciously_small_mapping():
    """A truncated read that rebuilt the table with a handful of rows would
    silently collapse the page's grouping. Same argument as the org crosswalk's
    row-count guard, which caught exactly this."""
    src = open(os.path.join(ROOT, 'api/build_license_families.py'), encoding='utf-8').read()
    assert 'MIN_PRODUCTS' in src
    m = re.search(r'MIN_PRODUCTS\s*=\s*(\d+)', src)
    assert m and int(m.group(1)) >= 100, "floor too low to catch a truncated read"
    assert 'REFUSING' in src, "the floor must abort, not warn"


def test_licenses_router_never_joins_contracts_without_deduping():
    """⚠ THE MEASUREMENT BUG THIS EXISTS FOR. `contracts` holds several rows per
    contract_id, so a plain join returned 1,109 rows for 950 licence contracts —
    inflating value ~6% and the expiring count ~18%. Every read must go through
    the DISTINCT ON (contract_id) CTE.

    ⚠ ONE deliberate exception exists: the ambiguity probe must join raw,
    because counting the duplicate rows is its whole purpose. It is allowed only
    by an explicit `RAW-CONTRACTS-JOIN-OK` marker within the preceding few
    lines, so the exception is a reviewable annotation rather than a hole. This
    guard fired on that probe when it was written, which is what the marker is
    for -- do not widen the rule to make a new join pass.
    """
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert 'DISTINCT ON (contract_id)' in src
    lines = src.split('\n')
    # The dedup CTE's own `FROM contracts` is the one legitimate unmarked use.
    cte_line = next((i for i, ln in enumerate(lines)
                     if ln.strip() == 'FROM contracts'), None)
    assert cte_line is not None, "the dedup CTE lost its FROM contracts"

    offenders = []
    for i, ln in enumerate(lines):
        if not re.search(r'(?:FROM|JOIN)\s+contracts\b', ln):
            continue
        if i == cte_line:
            continue
        window = '\n'.join(lines[max(0, i - 6):i])
        if 'RAW-CONTRACTS-JOIN-OK' in window:
            continue
        offenders.append(f"line {i + 1}: {ln.strip()}")
    assert not offenders, (
        "raw contracts join outside the dedup CTE (inflates totals ~6%); "
        "if it is deliberate, annotate it RAW-CONTRACTS-JOIN-OK:\n  "
        + "\n  ".join(offenders))

    # ⚠ And the exception must not become the rule.
    assert src.count('RAW-CONTRACTS-JOIN-OK') <= 2, (
        "more than one annotated raw join — each is a place totals can inflate, "
        "so adding another should be a deliberate, argued change")


def test_licenses_page_is_published_and_still_states_its_limits():
    """⚠ PUBLISHED 2026-08-11. This guard used to assert the OPPOSITE — noindex plus
    absence from the nav — because every judgement on the page was unreviewed AI
    output. The top 20 families (88.0% of value) have now been reviewed and accepted,
    so the page is in the nav and indexable.

    ⚠ The guard is INVERTED rather than deleted, for two reasons. Publishing is a
    decision, so reverting it should also be a decision and not a silent edit. And
    what makes publishing defensible is not the review alone but the caveats the page
    carries — so those are pinned here, in the same test that allows publication.
    """
    view = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php')
    body = open(view, encoding='utf-8').read()
    assert not re.search(r'name=["\']robots["\']\s+content=["\'][^"\']*noindex', body), \
        "the page is back to noindex — if unpublishing is intended, invert this guard"

    menubar = os.path.join(ROOT, 'app/resources/views/sub/menubar.blade.php')
    nav = open(menubar, encoding='utf-8').read()
    assert 'digital-reform.licenses' in nav, \
        "the Licenses page is no longer reachable from the nav, so publishing it " \
        "left it as unfindable as it was before"

    # ⚠ The price of publication: the reader must still be told what this is.
    assert 'db-analysis-badge' in body, \
        "the Analysis badge is gone from a now-public AI-derived analysis"
    low = body.lower()
    assert 'unreviewed' in low or 'uncurated' in low, \
        "the page no longer tells a public reader that the tail is unreviewed"

    # ⚠⚠ A PAGE MUST NOT DESCRIBE ITSELF AS UNLISTED WHILE BEING IN THE NAV.
    # Removing the meta tag was not enough: this page kept RENDERING the sentence
    # "This page is not linked from the site navigation and is marked noindex",
    # which was simply false once it shipped. Caught on prod by grepping the
    # rendered HTML for "noindex" and finding it in the body text, not a tag.
    rendered = re.sub(r'\{\{--.*?--\}\}', '', body, flags=re.DOTALL)
    for claim in ('unlisted', 'not linked from the site navigation',
                  'reachable-but-unpublished'):
        assert claim not in rendered.lower(), \
            f"the page still tells readers it is {claim!r} while it is in the nav"

    # ⚠ AND NO SIBLING MAY BE LEFT BEHIND. The function view is linked straight
    # from every family page, so leaving it noindex while its parents publish
    # recreates the reachable-but-unindexed state publishing was meant to end.
    for sibling in ('digital-reform-license-family', 'digital-reform-license-capability'):
        sib = open(os.path.join(
            ROOT, f'app/resources/views/procurement/{sibling}.blade.php'),
            encoding='utf-8').read()
        assert not re.search(r'name=["\']robots["\']\s+content=["\'][^"\']*noindex', sib), \
            f"{sibling} is still noindex while its parent page is published"


def test_licenses_page_states_the_limits_it_cannot_measure():
    """The page must keep saying what it cannot tell you. Unit prices are not
    derivable (no seat counts) and utilisation covers only ~19% of these
    contracts — both are questions a reader will otherwise assume it answered.
    """
    view = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php')
    body = open(view, encoding='utf-8').read().lower()
    assert 'seat' in body, "the page no longer says unit prices are unknowable"
    assert '19%' in body or 'utilis' in body or 'utiliz' in body, \
        "the page no longer states the utilisation coverage limit"
    assert '92%' in body, "the page no longer states the is_license agreement rate"


def test_slugs_are_deterministic_and_collision_free():
    """⚠ THESE BECOME PUBLIC URLS. Two properties matter, and the second is the
    subtle one: slugs must be unique, AND the numbering must be stable across
    rebuilds. If assignment depended on dict order, a rebuild could swap which
    family owns `microsoft` and which owns `microsoft-2`, silently repointing a
    live link at a different product.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "blf", os.path.join(ROOT, 'api/build_license_families.py'))
    src = open(spec.origin, encoding='utf-8').read()

    # ⚠ ONE namespace used as globals for both, or assign_slugs cannot see
    # slugify at call time — a function's globals come from the globals dict,
    # not the locals one.
    import re as _re
    ns = {'re': _re}
    for fn in ('def slugify', 'def assign_slugs'):
        m = _re.search(fn + r'\(.*?\n(?=\n\ndef |\Z)', src, _re.DOTALL)
        assert m, f"{fn} not found in the builder — renamed?"
        exec(compile(m.group(0), '<x>', 'exec'), ns)
    slugify, assign = ns['slugify'], ns['assign_slugs']

    assert slugify('SoundThinking (ShotSpotter)') == 'soundthinking-shotspotter'
    assert slugify('Broadcom (CA)') == 'broadcom-ca'
    assert slugify('(unidentified)') == 'unidentified'
    assert slugify('') == 'unnamed', "an empty family must still get a usable slug"

    # Collisions get suffixed, never merged: two families are still two families.
    got = assign({'Check Point', 'Check-Point', 'Microsoft'})
    assert len(set(got.values())) == 3, got

    # ⚠ Stability: the same input set in any order yields the same assignment.
    a = assign({'A B', 'A-B', 'A_B'})
    b = assign(list(reversed(sorted({'A B', 'A-B', 'A_B'}))))
    assert a == b, f"slug assignment is order-dependent: {a} vs {b}"


def test_vendor_links_require_an_unambiguous_supplier_id():
    """⚠ A vendor name that matches TWO PASSPort supplier ids must not be
    linked. Measured on this set: 86 of 88 names resolve uniquely, but
    ABSORB SOFTWARE INC matches two — linking it would send a reader to an
    arbitrary one of two companies. Same rule as the DOS crosswalk, which
    stores NULL for ambiguous rather than guessing.

    ⚠ The RULE has not changed; its OWNER moved. The lookup lives in
    modules/vendorids.py as of #244, because the Renewal Queue was resolving ids
    with a `LEFT JOIN vendors` instead — and 48 vendor names hold more than one row
    in that table, so the join DUPLICATED the Absorb contract and the queue reported
    one more expiring licence than this page. This guard follows the code rather
    than passing because the string it looked for happened to be gone.
    """
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert 'vendorids.unique_map(' in src, \
        "the Licenses page resolves supplier ids some other way than the shared map"
    mod = open(os.path.join(ROOT, 'api/modules/vendorids.py'), encoding='utf-8').read()
    assert 'HAVING count(DISTINCT "PASSPort Supplier-ID") = 1' in mod, \
        "the vendor id lookup no longer requires a UNIQUE match"

    # And the views must not link a row that has no id.
    for view in ('digital-reform-licenses', 'digital-reform-license-family'):
        body = open(os.path.join(
            ROOT, f'app/resources/views/procurement/{view}.blade.php'),
            encoding='utf-8').read()
        if "route('procurement.vendor'" not in body:
            continue
        assert "empty($v['vendor_id'])" in body or "empty($r['vendor_id'])" in body, \
            f"{view} links a vendor without checking an id resolved"


def test_family_pages_are_published_with_their_provenance_markers():
    """⚠ Published with the parent 2026-08-11 (was: asserted noindex). A family page
    is only as reviewed as the family it describes — the top 20 were reviewed, the
    ~410-family tail was not — so the markers that let a reader tell the difference
    are what this guard protects."""
    body = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php'),
        encoding='utf-8').read()
    assert not re.search(r'name=["\']robots["\']\s+content=["\'][^"\']*noindex', body), \
        "family pages are back to noindex — invert this guard if that is intended"
    assert 'db-analysis-badge' in body, "the Analysis badge is gone from a public page"
    assert 'summary_curated' in body, \
        "the curated-vs-auto marker on the summary is gone, so a public reader " \
        "cannot tell a reviewed product description from a generated one"
    assert '92%' in body, \
        "the family page no longer states the is_license agreement rate"


def test_summaries_are_grounded_in_our_data_not_model_knowledge():
    """⚠ A product summary generated from the model's world knowledge is an
    unverifiable claim on a page whose whole premise is that claims are
    checkable — and it can describe a product the City is not actually buying.
    The prompt must summarise the purposes WE recorded, and must be allowed to
    return nothing when those say nothing useful.
    """
    src = open(os.path.join(ROOT, 'api/describe_license_families.py'),
               encoding='utf-8').read()
    low = src.lower()
    assert 'recorded_purposes' in src, "the prompt no longer passes our own recorded purposes"
    assert 'do not add capabilities' in low or 'own knowledge' in low, \
        "the prompt no longer forbids drawing on outside knowledge"
    assert 'return the empty string' in low, \
        "the model must be allowed to decline rather than invent a purpose"
    # And a declined summary must not be stored as filler.
    assert 'skipped[0] += 1' in src, "blank summaries are no longer skipped"


def test_replaceability_is_shown_as_a_distribution_not_a_verdict():
    """⚠ build_vs_buy is the WEAKEST field: 75% cross-model agreement (vs 98%
    for tech_relevant), and 64 of 435 families are rated inconsistently by the
    classifier across their own contracts. The page must show the spread and
    both caveats — a lone confident rating would hide them.
    """
    view = os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php')
    body = open(view, encoding='utf-8').read()
    assert '75%' in body, "the page no longer states the build_vs_buy agreement rate"
    assert 'inconsistently' in body, \
        "the page no longer warns when a product's own contracts disagree"
    assert "$repSpread" in body, "the rating distribution is no longer rendered"

    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert '"mixed":' in api, "the API no longer reports whether ratings conflict"


def test_vendor_software_section_links_to_family_pages():
    """The section exists to connect a vendor to what it actually sells. It also
    links a PUBLIC page into the unlisted licence section, so it must carry the
    unreviewed caveat rather than presenting the list as a record."""
    view = os.path.join(ROOT, 'app/resources/views/procurement/vendor_profile.blade.php')
    body = open(view, encoding='utf-8').read()
    if 'section-software' not in body:
        return  # section removed deliberately; nothing to enforce
    assert "route('research.digital-reform.license-family'" in body, \
        "the software section no longer links to family pages"
    assert 'not yet reviewed' in body, \
        "the software section lost its uncurated caveat on a PUBLIC page"


def test_curated_summaries_live_in_a_version_controlled_seed():
    """⚠ A hand-written summary typed straight into the database exists only on
    that box: invisible in review, lost on a fresh environment, unreproducible.
    That is the "one-time script that doesn't stick" trap this codebase has paid
    for repeatedly. Curated summaries go in the seed, and the describer applies
    them; the database is the derived copy, never the source.
    """
    seed = os.path.join(ROOT, 'api/seed/license_family_summaries_curated.csv')
    assert os.path.exists(seed), "the curated-summary seed is gone"

    with open(seed, newline='', encoding='utf-8') as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith('#')]
    rows = {(_r.get('family') or '').strip(): (_r.get('summary') or '').strip()
            for _r in csv.DictReader(lines)}
    rows = {k: v for k, v in rows.items() if k and v}
    assert rows, "the seed parses to nothing"
    for fam, summ in rows.items():
        assert not fam.startswith('#'), f"comment leaked into the seed: {fam}"
        assert all(ord(c) < 128 for c in summ), f"non-ASCII in {fam}'s summary"
        assert len(summ) < 400, f"{fam}'s summary is too long to render"

    src = open(os.path.join(ROOT, 'api/describe_license_families.py'),
               encoding='utf-8').read()
    assert 'load_curated_summaries' in src, "the describer no longer applies the seed"
    assert "curated = true" in src, "seeded summaries are no longer marked curated"


def test_the_page_does_not_claim_a_curated_summary_was_human_written():
    """⚠ `curated` means held-fixed-and-reviewable, NOT necessarily authored by a
    person. A page whose whole premise is checkable claims must not make an
    unverifiable claim about its own provenance.
    """
    body = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php'),
        encoding='utf-8').read()
    assert 'Written by a person' not in body, \
        "the page claims a curated summary was human-written, which it cannot verify"


def _seed(name):
    """Read a curated seed, stripping comments before the CSV parser sees them."""
    path = os.path.join(ROOT, 'api/seed', name)
    with open(path, newline='', encoding='utf-8') as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith('#')]
    return [r for r in csv.DictReader(lines) if any((v or '').strip() for v in r.values())]


def test_replacement_candidates_seed_is_well_formed():
    """⚠ Every row here is a JUDGEMENT presented on a public-facing analysis page, so
    the file has to be self-policing: no invented confidence levels, no candidate
    asserted without a reason, and 'searched and found nothing' recorded explicitly
    rather than omitted. An omitted negative is indistinguishable from an unsearched
    one, which is how the same dead-end gets researched twice.
    """
    rows = _seed('license_replacement_candidates.csv')
    assert len(rows) > 20, f"only {len(rows)} candidate rows — did the seed get truncated?"

    kinds = {'oss-replacement', 'oss-same-product', 'hosting-alt', 'none-found'}
    confs = {'strong', 'partial', 'adjacent', 'none'}
    none_found = 0
    for r in rows:
        fam = (r.get('family') or '').strip()
        assert fam, f"row with no family: {r}"
        assert (r.get('candidate_kind') or '').strip() in kinds, \
            f"{fam}: bad candidate_kind {r.get('candidate_kind')!r}"
        assert (r.get('confidence') or '').strip() in confs, \
            f"{fam}: bad confidence {r.get('confidence')!r}"
        assert (r.get('why') or '').strip(), f"{fam}: a candidate with no reason is not reviewable"
        if (r.get('candidate_kind') or '').strip() in ('none-found', 'hosting-alt'):
            none_found += 1
            continue
        assert (r.get('candidate') or '').strip(), f"{fam}: kind implies a candidate but none given"
        # A strong claim must point somewhere a reader can check.
        if (r.get('confidence') or '').strip() == 'strong':
            assert (r.get('url') or '').strip().startswith('http'), \
                f"{fam}: 'strong' confidence with no URL to verify it against"

    # ⚠ The negative results are the part most likely to be quietly dropped.
    assert none_found >= 5, \
        "the 'searched and found nothing' rows are gone — absence is a finding and " \
        "must stay recorded (Hootsuite and Voicecast are the two largest lines)"
    fams = {(r.get('family') or '').strip() for r in rows}
    for expected in ('Hootsuite', 'Voicecast', 'Amazon Web Services', 'WP Engine'):
        assert expected in fams, f"{expected} dropped out of the candidates seed"


def test_procurement_class_seed_does_not_excuse_hosting_spend():
    """⚠ THE REASON THIS FILE EXISTS. build_vs_buy asks "could we build it?", which is
    the wrong question for infrastructure — so AWS ($6.80M) sits on `low` and vanishes
    from every replaceability view, while the entire `high` set is $10.13M.

    Classifying a line as hosting must never read as clearing it. Hosting is the class
    where a public rate card makes overcharging PROVABLE, so each hosting row must
    carry a price-facing lever, not a shrug.
    """
    rows = _seed('license_family_class.csv')
    assert len(rows) > 15, f"only {len(rows)} class rows"

    classes = {'software-licence', 'managed-hosting', 'cloud-infrastructure',
               'oss-support-tier', 'content-subscription', 'professional-services',
               'support-maintenance'}
    by_fam = {}
    for r in rows:
        fam = (r.get('family') or '').strip()
        cls = (r.get('class') or '').strip()
        assert fam and cls, f"incomplete row: {r}"
        assert cls in classes, f"{fam}: unknown class {cls!r}"
        assert (r.get('why') or '').strip(), f"{fam}: a classification with no reason"
        by_fam[fam] = (cls, (r.get('lever') or '').strip(), (r.get('why') or ''))

    # Hosting and infrastructure must name a price-facing lever.
    price_levers = {'benchmark-then-self-host', 'price-and-rightsizing'}
    for fam, (cls, lever, _why) in by_fam.items():
        if cls in ('managed-hosting', 'cloud-infrastructure'):
            assert lever in price_levers, (
                f"{fam} is {cls} but its lever is {lever!r} — hosting must point at a "
                f"price review, or the classification becomes an excuse")

    # The specific lines that motivated the file.
    assert by_fam.get('Amazon Web Services', ('',))[0] == 'cloud-infrastructure', \
        "AWS — the largest hosting-class line at $6.80M — lost its classification"
    assert by_fam.get('WP Engine', ('',))[0] == 'managed-hosting'
    # ⚠ And the category errors in the replaceability rating must stay documented.
    for fam in ('LinkedIn Learning', 'Pluralsight', 'GO1'):
        assert by_fam.get(fam, ('',))[0] == 'content-subscription', \
            f"{fam} is a content library, not software — Moodle cannot replace it"


def test_only_curated_candidates_can_reach_a_page():
    """⚠⚠ THE #146 LESSON, MADE STRUCTURAL. The NYCHA crosswalk put unreviewed
    candidates in the live id column and depended on every consumer remembering
    to filter the tier — one missed filter published an unreviewed match. Here the
    API's query itself is scoped to tier='curated', so an auto match cannot reach
    a page by omission.
    """
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    m = re.search(r'FROM license_replacement_candidate(.*?)"""', src, re.DOTALL)
    assert m, "the candidates query is gone"
    assert "tier = 'curated'" in m.group(1), \
        "the candidates query no longer restricts to curated — an unreviewed " \
        "auto match could now render as a claim"

    # And the builder must keep the two tiers separable.
    b = open(os.path.join(ROOT, 'api/build_license_procurement.py'), encoding='utf-8').read()
    assert "tier='auto'" in b or 'tier="auto"' in b or "'auto'" in b
    assert 'MIN_ENTRIES' in b and 'REFUSING' in b, \
        "the catalogue fetch lost its truncation floor"


def test_build_vs_buy_is_hidden_for_non_software_classes():
    """⚠ Showing a build-vs-buy rating on hosting is how $6.80M of AWS became
    invisible: the rating answers "could we build this?" with a correct `low` and
    ends the conversation, when the real lever is price. Only software-licence
    families may show a rating; everything else shows its lever instead.
    """
    body = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php'),
        encoding='utf-8').read()
    assert "$showRating" in body, "the class gate on the rating is gone"
    assert "'software-licence'" in body, "the gate no longer keys on software-licence"
    m = re.search(r"\$showRating\s*=\s*\((.*?)\);", body)
    assert m and 'software-licence' in m.group(1), \
        f"showRating no longer restricts to software-licence: {m and m.group(1)}"


def test_catalogue_provenance_is_surfaced_not_implied_live():
    """⚠ The catalogue's JSON is regenerated Mondays but redeployed manually, so
    `generated_at` is the honest freshness signal. A snapshot that looks live is
    the stale-repos.json failure; the pages must show the date."""
    for view in ('digital-reform-licenses', 'digital-reform-license-family'):
        body = open(os.path.join(
            ROOT, f'app/resources/views/procurement/{view}.blade.php'),
            encoding='utf-8').read()
        if 'catMeta' not in body:
            continue
        assert "generated_at" in body, f"{view} does not show catalogue generated_at"


def test_product_alias_seed_allows_a_deliberate_non_match():
    """⚠ A blank target means "do not attempt a match" — different from "no match
    found". Learning Tree is instructor-led training; auto-matching it to Moodle
    would repeat the category error the class file exists to prevent.
    """
    rows = _seed('license_product_aliases.csv')
    assert rows, "the alias seed parses to nothing"
    blanks = [r for r in rows if not (r.get('catalogue_product') or '').strip()]
    assert blanks, "the deliberate-non-match rows are gone"
    for r in blanks:
        assert 'DELIBERATELY BLANK' in (r.get('why') or ''), \
            f"{r.get('family')}: a blank target must say it is intentional"
    # The alias that motivated the file.
    esri = next((r for r in rows if r['family'] == 'Esri ArcGIS'), None)
    assert esri and esri['catalogue_product'] == 'ArcGIS Desktop', \
        "the Esri ArcGIS alias is gone — this is the $13.3M match a name join misses"


def test_capability_vocabulary_maps_to_real_catalogue_categories():
    """⚠ A capability tag whose category is not one the catalogue actually uses
    cannot match anything — and it would look like a covered family that simply
    has no options. The category values are the catalogue's KEYS
    (`web-content`), not its display labels ("Content & Web Publishing"); this
    guard caught exactly that mistake before it shipped.
    """
    rows = _seed('license_capability_vocab.csv')
    assert len(rows) >= 20, f"only {len(rows)} capability tags — too coarse to match on"
    # The 19 category KEYS the catalogue publishes in /meta.json, pinned as read
    # 2026-08-11. ⚠ If the catalogue renames a category this test fails, which is
    # the point: a tag pointing at a key that no longer exists silently matches
    # nothing. Re-read /meta.json before editing this set.
    keys = {'case-workflow', 'citizen-services', 'collaboration', 'crm-service',
            'data-analytics', 'dev-tools', 'documents', 'environment-transport',
            'finance-procurement', 'geospatial', 'health-social', 'hr-workforce',
            'identity-security', 'infrastructure', 'integration',
            'learning-knowledge', 'office', 'registers', 'web-content'}
    assert len(keys) == 19, "the catalogue publishes 19 categories"
    bad = [(r['capability'], r['catalogue_category']) for r in rows
           if (r.get('catalogue_category') or '').strip() not in keys]
    assert not bad, f"capability tags with an unknown catalogue category key: {bad}"
    # ⚠ The distinction that keeps Moodle from being offered for a course library.
    caps = {r['capability'] for r in rows}
    assert 'lms-platform' in caps and 'training-content' in caps, \
        "the platform/content split is gone — this is the category error that " \
        "put LinkedIn Learning on a replaceability list"


def test_purchase_classifier_abstains_rather_than_guessing():
    """⚠ Defaulting an unclear purchase to software-licence would silently
    recreate the category error the class layer exists to prevent. And an empty
    string is not a legal enum member for the API (400 INVALID_ARGUMENT), so
    abstention needs an explicit sentinel."""
    src = open(os.path.join(ROOT, 'api/classify_license_purchases.py'),
               encoding='utf-8').read()
    assert '"unclear"' in src, "the abstention sentinel is gone"
    assert 'abstained' in src, "abstentions are no longer counted"
    assert "cls == \"unclear\"" in src or "cls == 'unclear'" in src, \
        "the sentinel is no longer treated as an abstention"
    # Curated classifications must survive every re-run.
    assert "tier <> 'curated'" in src, \
        "the AI pass can now overwrite hand-classified families"


def test_rate_card_seed_requires_a_source_and_a_date():
    """⚠ A price without a date reads like a measurement. Vendor pricing changes
    quietly, so an undated figure on a public page is a claim we cannot defend."""
    rows = _seed('license_rate_cards.csv')
    assert rows, "the rate-card seed parses to nothing"
    for r in rows:
        fam = (r.get('family') or '').strip()
        assert fam, f"row with no family: {r}"
        assert (r.get('source_url') or '').strip().startswith('http'), \
            f"{fam}: a list price with no source URL is not checkable"
        assert re.match(r'^\d{4}-\d{2}-\d{2}$', (r.get('as_of') or '').strip()), \
            f"{fam}: a list price with no as_of date reads like a measurement"
        assert (r.get('unit') or '').strip(), f"{fam}: a price with no unit is meaningless"


def test_per_seat_cost_is_never_computed():
    """⚠⚠ THE LINE BETWEEN PRICE CONTEXT AND INVENTION. There are no seat, site or
    unit counts anywhere in the contract data, so a per-seat or per-site figure
    would require inventing the denominator. Cost per contract-YEAR is derivable
    from the term dates and is the only division allowed.

    _term_years must also return None rather than defaulting, or a 5-year
    contract silently becomes a 5x-inflated annual cost.
    """
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert '_term_years' in src and 'per_year' in src
    assert 'per_seat' not in src and 'per_site' not in src, \
        "a per-seat/per-site figure is being computed, but no unit count exists"
    m = re.search(r'def _term_years.*?(?=\ndef )', src, re.DOTALL)
    assert m and 'return None' in m.group(0), \
        "_term_years no longer abstains on an unusable term"


def test_capability_vocabulary_does_not_conflate_unlike_functions():
    """⚠ THE DEFECT THIS EXISTS FOR. A single `asset-facilities` tag grouped
    Lansweeper (IT/licence discovery), AssetWorks AiM and Archibus (buildings),
    Trapeze (fleet) and Vision CAMA (property tax assessment — not asset
    management at all). "12 agencies buy asset management" was true of the tag and
    false of the world.

    A function tag that groups unlike things is WORSE than no tag, because the
    cross-agency view is exactly what it feeds — it manufactures a consolidation
    opportunity that does not exist.
    """
    rows = _seed('license_capability_vocab.csv')
    caps = {r['capability'] for r in rows}
    for required in ('it-asset-management', 'facilities-asset', 'fleet-management'):
        assert required in caps, f"{required} is gone — the conflated tag is back"
    assert 'asset-facilities' not in caps, \
        "the conflated asset-facilities tag was reintroduced"


def test_generic_products_still_get_a_function():
    """⚠ `is_generic` means the PRODUCT could not be named, not that the FUNCTION is
    unknown. Excluding generics from the capability pass hid $3.76M of UMS/InVision
    software-asset-management services from the cross-agency function view that
    exists to surface precisely that kind of duplication.

    Suppress the product identity; keep the capability.
    """
    src = open(os.path.join(ROOT, 'api/classify_license_purchases.py'),
               encoding='utf-8').read()
    m = re.search(r'SELECT lf\.family.*?GROUP BY lf\.family', src, re.DOTALL)
    assert m, "the family query is gone"
    assert 'NOT lf.is_generic' not in m.group(0), \
        "generic families are excluded from the capability pass again — this hides " \
        "the spend whose product is unnamed but whose function is obvious"

    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert '_capability_rollup' in api, "the cross-agency function rollup is gone"


def _balanced(src, start):
    """The parenthesised expression beginning at `start`, across line breaks.

    ⚠ A `re.search(r'... = (.+)')` stops at the first newline, so a condition
    wrapped over two lines is only half-read — which is how this very guard came
    to pass while seeing only `a["products"] >= _FRAG_MIN_PRODUCTS`."""
    i = src.index('(', start)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == '(':
            depth += 1
        elif src[j] == ')':
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    raise AssertionError('unbalanced parentheses in the fragmentation expression')


def test_fragmentation_needs_many_products_not_just_many_agencies():
    """⚠ Agency count alone is the wrong signal. office-productivity spans 18
    agencies on 2 products — that is a citywide Microsoft agreement working as
    intended, not fragmentation. network-security spans 18 agencies on 32 products,
    which is the actual finding. The flag must require both.

    ⚠⚠ AND IT MUST STAY SCARCE. With only the product/agency floors this badge
    landed on 26 of 46 rows — more than half the table, which is wallpaper, not a
    signal. A value floor and a top-N cap keep it meaning "look at this one".

    ⚠ `other` must never carry it: that bucket is the classifier's abstention, and
    you cannot consolidate the functions you failed to identify. It was both
    flagged AND sorted first, so the loudest row on the table was the one row
    that means "we do not know".
    """
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    at = src.find('a["fragmented"] =')
    assert at != -1, "the fragmentation flag is gone"
    expr = _balanced(src, at)
    assert 'products' in expr and 'agencies' in expr, \
        f"fragmentation must consider BOTH product count and agency count: {expr}"
    assert '_FRAG_MIN_VALUE' in expr, \
        "the value floor is gone — the badge spreads back across half the table"
    assert '_OTHER_CAPABILITY' in expr, \
        "the abstention bucket can be flagged 'worth consolidating' again"
    # The cap that keeps the badge scarce, and the pin that keeps `other` last.
    assert '_FRAG_MAX_BADGED' in src, "the top-N cap on the badge is gone"
    assert re.search(r'sorted\(out,\s*key=lambda a: \(a\["key"\] == _OTHER_CAPABILITY',
                     src), \
        "`other` is no longer pinned to the end of the function table"

    # ⚠ And the rule must be STATED where the badge is rendered. A threshold the
    # reader cannot see is indistinguishable from an opinion.
    view = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php'),
        encoding='utf-8').read()
    assert 'worth consolidating' in view.lower(), "the badge is gone from the page"
    assert re.search(r'at least 5 distinct', view), \
        "the page no longer states what 'worth consolidating?' actually requires"


def test_the_rate_card_seed_is_actually_consumed():
    """⚠⚠ THE FAILURE THIS EXISTS FOR, AND I COMMITTED IT. license_rate_cards.csv
    was written, given a validating test, and read by NOTHING for two commits. The
    test passed the whole time, because validating a file's shape says nothing
    about whether any code opens it — the two failures are indistinguishable from
    the test output. Exactly the never-called register_untracked_tables() class.

    A seed with no consumer is decoration. Assert the consumer exists.
    """
    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert 'license_rate_cards.csv' in api, \
        "nothing in the API reads the rate-card seed — it is inert again"
    assert 'rate_card' in api, "the rate card is not exposed on any endpoint"

    view = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php'),
        encoding='utf-8').read()
    assert 'rateCard' in view, "the rate card is loaded but never rendered"
    # ⚠ And it must stay a comparison, never a division.
    assert 'not divided into it' in view, \
        "the page no longer says the list price is shown beside the spend rather " \
        "than divided into it — with no seat count, dividing invents the denominator"


def test_the_function_view_is_navigable():
    """⚠ Naming a function as fragmented and then dead-ending is worse than not
    naming it: a reader cannot act on "32 network-security products" without
    seeing which 32. The index rows must link, and family pages must say which
    function they belong to."""
    idx = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php'),
        encoding='utf-8').read()
    assert "license-capability" in idx, "the function rows are not clickable"

    fam = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php'),
        encoding='utf-8').read()
    assert "license-capability" in fam, "a family page does not show its function"

    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert '/capability/{cap}' in api, "the function drill-down endpoint is gone"


def _rendered_copy(view):
    """Just the prose a reader sees: no comments, no code, no CSS.

    ⚠⚠ EVERY GUARD IN THIS FILE THAT SCANS A TEMPLATE NEEDS THIS, and the first
    draft of the two below proved it by failing on themselves. The percentage
    scanner matched `style="width: 40%"` (a CSS length) and `'<0.1%'` (a
    formatting sentinel inside @php); the label scanner matched the string
    `$capWords` inside the comment that explains why $capWords must not exist.

    Same family as the org-type guard that "must strip comments first, or it
    fires on its own explanation" — and as the guard that scanned zero files and
    passed. A scanner that reads code as copy reports problems that are not
    there; one that reads nothing reports none. Both are unusable.
    """
    body = re.sub(r'\{\{--.*?--\}\}', '', view, flags=re.DOTALL)   # Blade comments
    body = re.sub(r'@php\b.*?@endphp', '', body, flags=re.DOTALL)  # PHP blocks
    body = re.sub(r'<style\b.*?</style>', '', body, flags=re.DOTALL)
    body = re.sub(r'<script\b.*?</script>', '', body, flags=re.DOTALL)
    body = re.sub(r'style="[^"]*"', '', body)                      # inline CSS
    body = re.sub(r'//[^\n]*', '', body)                           # stray PHP comments
    return body


def _php_code(view):
    """The template's CODE, with only comments removed.

    ⚠ The counterpart to _rendered_copy, and both are needed. _rendered_copy
    strips @php blocks — correct when scanning prose, and USELESS for finding a
    reintroduced `$capWords` map, which lives inside exactly those blocks.
    Verified the hard way: the label guard passed while a freshly injected map sat
    in the @php block it could not see. A scanner blind to the region the defect
    lives in is the zero-files scanner wearing a different hat.
    """
    body = re.sub(r'\{\{--.*?--\}\}', '', view, flags=re.DOTALL)   # Blade comments
    body = re.sub(r'(?m)^\s*//[^\n]*$', '', body)                  # whole-line PHP comments
    return body


def test_the_reviewed_share_is_computed_never_typed():
    """⚠⚠ THE DEFECT THIS EXISTS FOR, FOUND ON THE LIVE PAGE. The review note read
    "the largest 20 product families — 88.0% of the value on this page — have been
    reviewed by hand" as literal template text, while the page's OWN concentration
    strip, computed from the same payload, read 87.7% for the top 20 and the class
    seed had grown to 38 curated rows. Two more literals had drifted the same way:
    "138" GSA contracts (live value 149) and "37 families are hand-classified".

    Three stale numbers in one document, each stated with the same confidence as
    the computed ones beside them. A documented rollup is a SNAPSHOT, not a
    measurement, and this page's whole claim on a reader is that it measures.

    The predicate is now `tier='curated'` on the class row — the thing a
    version-controlled seed can actually evidence — computed by _reviewed().
    """
    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert 'def _reviewed(' in api, "the computed review share is gone"
    assert '"reviewed": _reviewed(' in api, "the review share is no longer served"
    assert '"intergov_contracts"' in api, \
        "the intergovernmental count is no longer computed — it was a typed 138"

    view = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php'),
        encoding='utf-8').read()
    assert "$reviewed['share']" in view or '$reviewed["share"]' in view, \
        "the page no longer renders the computed review share"
    body = _rendered_copy(view)

    # ⚠ THE BANNED PATTERN: a hardcoded percentage in rendered copy. Every real
    # figure on this page comes from the payload, so a literal `NN.N%` or `NN%` in
    # the body is by definition a number that cannot track its own data.
    # Thresholds stated as RULES are the deliberate exception and are listed.
    allowed = {'92%',    # cross-model agreement on a fixed 40-contract sample
               '19%',    # Checkbook spend-metadata coverage, a stated limit
               '100%',   # the rhetorical "would read 100%" in the routes note
               '6%'}     # the dedup inflation constant, measured once
    literals = set(re.findall(r'\b\d{1,3}(?:\.\d)?%', body)) - allowed
    assert not literals, (
        f"hardcoded percentages in rendered copy: {sorted(literals)} — these drift "
        "silently. Compute them in the API and render the payload key instead.")


def test_the_calendar_discloses_the_contracts_it_drops():
    """⚠⚠ ~72% OF THIS INVENTORY HAD ALREADY ENDED AND THE PAGE NEVER SAID SO.
    `_by_year` skips any contract whose end year is past, so the renewal calendar
    summed to 262 contracts while the headline tile above it read 948 — and the
    $1.37B beside that tile is what a reader quotes as current exposure.

    Only `no_end_date` was disclosed, which made the omission look complete.

    The buckets must also RECONCILE: year rows + ended + no_end_date == the
    contract count. Without that, a future filter can drop rows into a gap again
    and every visible total will still look plausible.
    """
    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert '"ended"' in api, "the calendar no longer reports contracts that ended"
    assert '"active_contracts"' in api and '"active_value"' in api, \
        "the summary no longer distinguishes running contracts from historical ones"
    # ⚠ Derived by subtraction from the calendar's own bucket, deliberately: two
    # independent definitions of "active" is how the two expiring figures on this
    # page came to disagree in the first place.
    assert 'by_year["ended"]["contracts"]' in api, \
        "active count is computed independently of the calendar again"

    view = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php'),
        encoding='utf-8').read()
    assert 'had already ended' in view, \
        "the page no longer tells the reader the calendar omits ended contracts"
    assert 'historical' in view.lower(), \
        "the page no longer says this analysis is largely historical"

    # The reconciliation, on synthetic rows so it tests the arithmetic and not
    # whatever prod happens to hold today.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        '_lic_by_year', os.path.join(ROOT, 'api/routers/licenses.py'))
    # ⚠ Loading the module by path would import fastapi/postgrex; the function is
    # pure, so exec just its source instead.
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    m = re.search(r'\ndef _by_year\(rows\):.*?\n(?=\n@|\ndef |\Z)', src, re.DOTALL)
    assert m, "_by_year is gone"
    ns = {'time': __import__('time')}
    exec(m.group(0), ns)                                        # noqa: S102
    this_year = ns['time'].strftime('%Y')
    rows = [
        {'end_year': '1999', 'value': 10.0, 'expiring': False, 'family': 'Old'},
        {'end_year': '1998', 'value': 5.0, 'expiring': False, 'family': 'Old'},
        {'end_year': this_year, 'value': 100.0, 'expiring': True, 'family': 'Big'},
        {'end_year': this_year, 'value': 1.0, 'expiring': True, 'family': 'Small'},
        {'end_year': '', 'value': 7.0, 'expiring': False, 'family': 'NoDate'},
    ]
    out = ns['_by_year'](rows)
    counted = (sum(y['contracts'] for y in out['years'])
               + out['ended']['contracts'] + out['no_end_date'])
    assert counted == len(rows), \
        f"the calendar buckets lose rows: {counted} accounted for of {len(rows)}"
    assert out['ended'] == {'contracts': 2, 'value': 15.0}
    # And each year names its own largest line, so a row dominated by one
    # agreement cannot read as a broad-based cliff.
    assert out['years'][0]['top_family'] == 'Big'


def test_capped_lists_carry_their_full_length():
    """⚠ Every truncated list on this page presented itself as complete. "By
    vendor" showed 25 of 88 under the heading "Who the City buys licenses from";
    "Product families by value" showed 60 of 434. A reader cannot tell a short
    list from a short table, so the denominator has to travel with the slice.

    This is the same rule as _agg's product_count — count before you cap — applied
    to the payload rather than to one helper.
    """
    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    m = re.search(r'"totals": \{(.*?)\}', api, re.DOTALL)
    assert m, "the payload no longer reports the full length of its capped lists"
    for key in ('families', 'fragmented', 'by_method', 'by_agency', 'by_vendor'):
        assert f'"{key}"' in m.group(1), f"{key} has no denominator in `totals`"

    # ⚠ The totals must be measured on the UNSLICED lists. Reading len() off the
    # capped list is the defect this guards, and it looks identical in output.
    for name in ('frag_all', 'methods_all', 'agency_all', 'vendor_all'):
        assert re.search(rf'\b{name}\b\s*=\s*sorted\(', api), \
            f"{name} is no longer built in full before slicing"
        assert f'len({name})' in api, f"`totals` no longer measures {name} unsliced"

    view = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php'),
        encoding='utf-8').read()
    assert view.count('Showing the top') >= 2, \
        "the capped agency/vendor tables no longer state that they are capped"


def test_capability_labels_live_in_the_seed_not_in_a_view():
    """⚠⚠ 18 OF THE 46 FUNCTION TAGS IN USE RENDERED AS RAW KEBAB-CASE KEYS on a
    published page — `project-tracking`, `hr-workforce`, `statistics-analysis` —
    sitting beside properly labelled rows like "Network security".

    The cause was structural, not a typo: the label map lived in THREE Blade
    templates, each holding its own partial copy of a 47-tag vocabulary. Adding a
    tag to the seed could not label it without editing three views nobody thought
    to open, so nobody ever did.

    The label now lives with the vocabulary and is served by the API. This guard
    fails if a view grows its own copy again.
    """
    rows = _seed('license_capability_vocab.csv')
    missing = [r['capability'] for r in rows if not (r.get('label') or '').strip()]
    assert not missing, f"capability tags with no display label: {missing}"
    # ⚠ A label equal to its key is the bug wearing a label column.
    same = [r['capability'] for r in rows if (r.get('label') or '').strip() == r['capability']]
    assert not same, f"these labels are just the raw key: {same}"

    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert 'license_capability_vocab.csv' in api, \
        "the API no longer reads the label seed — the labels are inert again"
    assert '"label"' in api, "the capability rollup no longer serves a label"

    # ⚠ THE BANNED PATTERN. Any view reconstructing the mapping locally.
    scanned = 0
    for name in ('digital-reform-licenses', 'digital-reform-license-capability',
                 'digital-reform-license-family'):
        path = os.path.join(ROOT, f'app/resources/views/procurement/{name}.blade.php')
        # ⚠ _php_code, NOT _rendered_copy: the map would live inside an @php
        # block, which _rendered_copy strips — so scanning the copy cannot see the
        # defect at all. Comments still go, because each of these files explains
        # in a comment that $capWords must not exist here, and a raw scan fires on
        # its own warning.
        body = _php_code(open(path, encoding='utf-8').read())
        scanned += 1
        assert '$capWords' not in body, \
            f"{name} grew its own capability label map again"
        # Two or more kebab-case vocabulary keys mapped to strings is the shape.
        pairs = re.findall(r"'[a-z]+(?:-[a-z]+)+'\s*=>\s*'[^']+'", body)
        caps = {r['capability'] for r in rows}
        local = [p for p in pairs if p.split("'")[1] in caps]
        assert len(local) < 2, f"{name} maps capability keys to labels inline: {local}"
    assert scanned == 3, "the guard did not scan all three license views"


def test_curated_reasoning_never_restates_the_familys_own_scope():
    """⚠⚠ THE SAME DRIFT DEFECT, REINTRODUCED IN THE SEED — I wrote it myself.

    After spending a whole change removing typed percentages from the page, I
    wrote 60 curated `why` rows that opened with the family's own scope: "$112.5M
    over 7 contracts, led by NYPD…". Those strings render on the family page,
    directly beneath the same value and contract count computed live from the
    database. When the full-population classification landed, the inventory grew
    from 948 contracts to 1,601 and **28 of the 61 rows were instantly wrong** —
    Salesforce's said $3.1M over 2 contracts against a live $16.1M over 4, and
    Elasticsearch's said $65K against $2.1M, a 32x error.

    The rule: `why` carries the REASONING. The page carries the numbers. A figure
    the page already renders must not be retyped beside it.

    ⚠ Figures the page CANNOT derive are still allowed and wanted — an internal
    breakdown (Microsoft's $573.8M ELA within the family), a published list price,
    another city's contract. Those carry their own context and do not track this
    family's total. What is banned is the self-describing opener and the
    "over N contracts" scope clause.
    """
    rows = _seed('license_family_class.csv')
    assert len(rows) > 40, f"only {len(rows)} class rows — did the seed shrink?"

    lead = re.compile(r'^\s*\$[\d,]+\.?\d*[MK]?\b')
    scope = re.compile(r'\b(?:over|on|across)\s+\d+\s+contracts?\b', re.I)
    offenders = []
    for r in rows:
        fam, why = (r.get('family') or '').strip(), (r.get('why') or '')
        if lead.match(why):
            offenders.append(f"{fam}: opens with its own value — {why[:44]!r}")
        m = scope.search(why)
        if m:
            offenders.append(f"{fam}: restates its own contract count — {m.group(0)!r}")
    assert not offenders, (
        "curated reasoning restates figures the family page already renders live, "
        "so it goes stale the moment the inventory changes:\n  "
        + "\n  ".join(offenders))


def test_pipeline_agreements_never_enter_a_total():
    """⚠⚠ THE WHOLE RISK OF SURFACING THEM. Unregistered agreements carry no
    contract_id, so `_CONTRACTS` (and therefore every aggregate on this page)
    excludes them — correctly, because they are CEILINGS on unsigned paper, not
    spend. The hazard is that a row leaks into `rows` and silently adds a $1.2B
    purchasing ceiling to the licence total, or that a reader adds it themselves.

    ⚠ REWRITTEN 2026-08-13 (#247). The block's canonical home is now the section
    OVERVIEW, and the query lives in modules/pipelinevehicles so there is one
    definition: scoped to licence vendors it was 121 agreements / $1.61B, while the
    section-level figure over the whole technology universe is 257 / $3.22B. Two
    pages publishing two figures for one question is the defect this section spent a
    week removing. This page keeps the ROWS (its family pages title-match against
    them, which the Overview cannot do) and publishes no aggregate of its own.
    """
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()

    # One query, in the shared module, and this page uses it rather than its own.
    assert 'pipelinevehicles.load(' in src, \
        "the Licenses page no longer loads the pipeline through the shared module"
    assert 'contract_id IS NULL' not in src, \
        "the Licenses page has grown its own pipeline query back — one definition"

    mod = open(os.path.join(ROOT, 'api/modules/pipelinevehicles.py'), encoding='utf-8').read()
    assert 'contract_id IS NULL' in mod, \
        "the shared query no longer restricts to unregistered contracts — it can now " \
        "return rows that are ALSO in the main set, double-counting them"
    assert 'DISTINCT ON (epin)' in mod, "pipeline rows are no longer one-per-EPIN"
    assert 'vendor_name = ANY($1)' in mod, \
        "the pipeline is no longer scoped to a vendor set at all"
    assert "tag='digital_services'" not in mod, \
        "the pipeline is scoped by the noisy vendor tag again"
    # ⚠ The vendor set is computed from the licence rows already in hand, so it is
    # provably the vendors this page displays, and it avoids a second raw join into
    # `contracts` whose duplicate rows are the documented inflation hazard.
    assert re.search(r'lic_vendors = sorted\(\{.*?for r in rows', src, re.DOTALL), \
        "the pipeline vendor set is no longer derived from the licence rows"

    # It must never be merged into a total on this page.
    for total in ('"total_value"', '"contracts": len(rows)', '"active_value"'):
        seg = src[src.index(total):src.index(total) + 160]
        assert 'pipe' not in seg, f"a pipeline value reached {total}"

    # `ceiling`, not `value`, at the boundary — in the module now.
    assert '"ceiling"' in mod and 'd["ceiling"]' in mod, \
        "the combined figure is no longer called a ceiling"
    # ⚠ And the retired key must FAIL LOUDLY for an old consumer rather than serve a
    # narrower number under the same name.
    assert '"moved_to"' in src, \
        "the licences payload still publishes its own pipeline aggregate"

    # The page points at the Overview instead of restating the block.
    view = _rendered_copy(open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php'),
        encoding='utf-8').read())
    assert 'still in the pipeline' in view, \
        "the pointer to the pipeline block is gone from the Licenses page"
    assert 'Only registered contracts are counted' in view, \
        "the limits note no longer discloses the registration blind spot"


def test_pipeline_family_link_is_a_title_match_and_says_so():
    """⚠ These rows were never classified — no contract_id means the classifier
    never saw them — so they carry no product field at all. The family link is a
    TITLE match, which is weak; showing the matched title is what makes it
    checkable instead of asserted."""
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert 'def _pipeline_for_family(' in src, "the family-level pipeline link is gone"
    assert '"pipeline_vehicles": _pipeline_for_family(' in src, \
        "the family payload no longer carries its pipeline vehicles"

    fam = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php'),
        encoding='utf-8').read()
    assert '$pipeVehicles' in fam, "the family page does not render pipeline vehicles"
    body = _rendered_copy(fam)
    assert "title names this product" in body, \
        "the family page no longer discloses that the link is a title match"
    assert 'not counted above' in body, \
        "the family page no longer says the ceiling is excluded from its totals"


def test_views_read_api_keys_with_their_stored_spelling():
    """⚠⚠ THE US-SPELLING PASS BROKE A DATA KEY AND NOTHING NOTICED. The
    replacement-candidates table has a `licence` column (the OSS licence, e.g.
    GPL-2.0), the API serves it under that key, and a blanket licence→license
    rewrite of the family view renamed the SUBSCRIPT too — so the License column
    rendered empty for every candidate on prod, and `?? ''` made the breakage
    silent. The API said GPL-2.0-or-later; the page said nothing.

    Spelling passes may touch PROSE only. Keys are storage, and their spelling is
    fixed by the schema, not by style. This pins every stored-spelling key the
    licence views read.
    """
    fam = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php'),
        encoding='utf-8').read()
    assert "$cd['licence']" in fam, \
        "the candidates licence column is read under the wrong key — the cell " \
        "renders empty while the API serves the value"
    assert "$cd['license']" not in fam, \
        "a US-spelled subscript is back; the API key is 'licence'"
    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert re.search(r'SELECT family, candidate, candidate_kind, confidence, licence',
                     api), "the API no longer serves the candidates' licence column"


def test_the_class_view_is_navigable():
    """⚠ The purchase class is this page's HEADLINE lens — it is the view that
    surfaced $6.80M of AWS the replaceability rating hid — and it was the one
    table with no drill-down. Families clicked through to a family page and
    functions to a function page; classes dead-ended, so "Managed hosting
    $265.5M" could not be opened.

    ⚠ The filter resolves through modules/licenseclass at product grain, the same
    resolver the rollup uses. Re-deriving the class in the endpoint (or in SQL)
    would let the drill-down disagree with the table it was reached from, which
    is the entire reason that module exists.
    """
    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    m = re.search(r'if purchase_class:(.*?)\n    if expiring', api, re.DOTALL)
    assert m, "the contracts endpoint no longer filters by purchase class"
    assert 'licenseclass.resolve(' in m.group(1), \
        "the class filter re-derives the class instead of using the shared resolver"

    view = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php'),
        encoding='utf-8').read()
    assert '?class=' in view, "the class rows are not clickable"

    ctrl = open(os.path.join(
        ROOT, 'app/app/Http/Controllers/ProcurementController.php'), encoding='utf-8').read()
    assert "input('class'" in ctrl, "the controller drops the class parameter"
    assert "class=' . urlencode($class)" in ctrl, \
        "the class filter never reaches the API"


def test_the_function_view_is_exportable():
    """⚠ The cross-agency function view is the most novel table here — "how many
    different products do we buy to do one job, in how many agencies" is the
    consolidation question, and it is the one nobody else publishes. Only the
    contract-level export existed, so the one view worth taking away was the one
    view you could not download."""
    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert '/capabilities/export' in api, "the function view has no CSV export"
    view = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php'),
        encoding='utf-8').read()
    assert 'capabilities/export' in view, "the function export is not linked"


def test_capped_display_lists_never_become_counts():
    """⚠ _agg truncates its product list for display. Reading len() off the capped
    list undercounts any agency with more than 12 products — a wrong number that
    looks like a measurement. The count is taken before the cap."""
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    m = re.search(r'a\["product_count"\]\s*=\s*len\(a\["products"\]\)\s*\n\s*a\["products"\]\s*=\s*sorted', src)
    assert m, "product_count is no longer computed BEFORE the display cap"


def test_identity_verification_requires_citations_and_the_right_model():
    """⚠⚠ TWO MEASURED FACTS THIS PINS, both learned the expensive way.

    1. `gemini-3.1-flash-lite` returns NO grounding metadata when handed a
       google_search tool — it silently answers from recall. Its answer about
       Carahsoft was CORRECT, which is exactly the danger: an ungrounded right
       answer is indistinguishable from an ungrounded wrong one. The verifier
       must not be moved to the lite model to save money; the citations are the
       product.
    2. Appending "Return ONLY a JSON object" to a grounded request DISABLES the
       search. The identical query grounds with 13-16 sources as prose and
       returns ZERO the moment structured output is demanded. Hence two steps:
       search in prose, extract afterwards.

    And the gate itself: a finding with no sources is discarded, however
    plausible it reads.
    """
    src = open(os.path.join(ROOT, 'api/verify_license_identities.py'),
               encoding='utf-8').read()
    m = re.search(r'^MODEL = "(.+?)"', src, re.M)
    assert m and 'lite' not in m.group(1), \
        f"the verifier's search model is {m and m.group(1)!r} — a lite model does " \
        f"not ground, and would produce uncited claims that look identical to cited ones"

    assert 'if not chunks:' in src and 'return None, []' in src, \
        "the no-sources gate is gone — ungrounded findings could now be written"
    assert 'grounding_chunks' in src, "sources are no longer read from the response"

    # The two-step split must survive: a schema on the SEARCH call kills grounding.
    search_call = src[src.index('def _verify'):src.index('def report_spend')]
    grounded = search_call[:search_call.index('EXTRACT_MODEL')] if 'EXTRACT_MODEL' in search_call else search_call
    assert 'response_schema' not in grounded, \
        "a response_schema is back on the grounded call — that silently disables " \
        "search, and every finding will be discarded for having no sources"

    # Output is a review queue, never a page.
    assert 'license-identity-review.md' in src
    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert 'identity' not in api.lower() or 'license-identity' not in api, \
        "identity findings are being served to a page; they are a review queue"


# ---------------------------------------------------------------------------
# PRODUCT-GRAIN purchase class. ⚠ These guard the fix for the defect that one
# class per FAMILY could not represent two kinds of purchase: $68.9M of Microsoft
# vendor support sat inside a `software-licence` family and was asked whether an
# open-source substitute existed. See modules/licenseclass.py.
# ---------------------------------------------------------------------------

def _licenseclass():
    """⚠ Loaded BY PATH, not `from modules import ...`: conftest.py replaces the
    whole `modules` package with a MagicMock, so a plain import silently yields a
    mock whose `CLASSES` contains everything and asserts nothing. That is the
    vacuous-guard trap — the first draft of these tests "passed" against a mock.
    licenseclass.py imports only `re`, which is what makes this safe."""
    import importlib.util
    path = os.path.join(ROOT, 'api/modules/licenseclass.py')
    spec = importlib.util.spec_from_file_location('licenseclass_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_product_class_seed_is_well_formed():
    """Same rules as the family seed, applied one grain down — including the one
    that matters most: hosting and cloud must name a PRICE-facing lever, or
    classifying a line as infrastructure becomes a way of excusing it."""
    licenseclass = _licenseclass()

    rows = _seed('license_product_class.csv')
    assert rows, "the product-class seed is empty"
    seen = set()
    for r in rows:
        prod = (r.get('product') or '').strip()
        cls = (r.get('class') or '').strip()
        assert prod and cls, f"incomplete row: {r}"
        assert cls in licenseclass.CLASSES, f"{prod}: unknown class {cls!r}"
        assert (r.get('why') or '').strip(), f"{prod}: an override with no reason"
        lever = (r.get('lever') or '').strip()
        if cls in ('managed-hosting', 'cloud-infrastructure'):
            assert lever in licenseclass.PRICE_LEVERS, (
                f"{prod} is {cls} but its lever is {lever!r} — hosting must point at "
                f"a price review, or the classification becomes an excuse")
        # ⚠ Keys are normalised, so two rows differing only in punctuation would
        # silently collide and one would win at random.
        key = licenseclass.norm(prod)
        assert key not in seen, f"{prod}: duplicate override after normalisation"
        seen.add(key)


def test_the_microsoft_support_split_is_pinned():
    """⚠ THE MEASURED DEFECT THIS LAYER EXISTS FOR. The Microsoft family is
    $643.5M and correctly `software-licence` (89.2% of it is the ELA), but $68.9M
    of it is vendor support. If these overrides vanish, that money silently
    returns to the substitution question and the class rollup overstates
    `software-licence` by ~5% of the entire page."""
    licenseclass = _licenseclass()

    rows = {licenseclass.norm(r['product']): r for r in _seed('license_product_class.csv')}
    for prod, expected in (('Microsoft Unified Support', 'support-maintenance'),
                           ('Microsoft Premier Support', 'support-maintenance'),
                           ('Microsoft Premier Services', 'professional-services')):
        r = rows.get(licenseclass.norm(prod))
        assert r, f"{prod} lost its product-grain class — $68.9M is back in software-licence"
        assert r['class'] == expected, f"{prod} is now {r['class']!r}, expected {expected!r}"

    # ⚠ And the FAMILY must stay software-licence: the ELA is 89.2% of it, so
    # reclassifying the family would be the opposite error.
    fam = {r['family'].strip(): r for r in _seed('license_family_class.csv')}
    assert fam.get('Microsoft', {}).get('class') == 'software-licence', \
        "the Microsoft family is no longer software-licence, but the ELA is 89.2% of it"


def test_product_class_overrides_actually_reach_the_rollup():
    """⚠ VERIFY IN THE DIRECTION THAT CAN FAIL. A correct resolver wired to
    nothing is the inert-seed trap: the seed would validate, the tests would pass
    and the page would still show the family answer. So this asserts the VALUE
    MOVES, and that the router actually passes product classes in."""
    licenseclass = _licenseclass()

    fam = {'Microsoft': {'class': 'software-licence',
                         'lever': 'open-source-substitute', 'why': 'the ELA'}}
    prod = {licenseclass.norm('Microsoft Unified Support'):
            {'class': 'support-maintenance', 'lever': 'is-the-paid-tier-needed', 'why': 'x'}}
    rows = [
        {'product': 'Microsoft ELA', 'family': 'Microsoft', 'value': 573.8},
        {'product': 'Microsoft Unified Support', 'family': 'Microsoft', 'value': 57.0},
        # ⚠ A different raw spelling of the SAME product must inherit the override,
        # or every variant would need its own row and most would be missed.
        {'product': 'MICROSOFT  UNIFIED  SUPPORT', 'family': 'Microsoft', 'value': 1.0},
    ]

    mix, dominant = licenseclass.mix(rows, prod, fam)
    by = {a['key']: a for a in mix}
    assert set(by) == {'software-licence', 'support-maintenance'}, \
        f"the family did not split across classes: {sorted(by)}"
    assert round(by['support-maintenance']['value'], 1) == 58.0, \
        "the support products did not move out of software-licence"
    assert round(by['software-licence']['value'], 1) == 573.8
    # Dominance is by VALUE. Counting contracts would hand the headline to the
    # 2-row support tail over the 1-row ELA.
    assert dominant == 'software-licence'
    assert by['support-maintenance']['lever'] == 'is-the-paid-tier-needed'

    # Without the override, everything collapses back to one class — this is the
    # bug, reproduced, so the assertion above cannot pass for the wrong reason.
    mix_noop, _ = licenseclass.mix(rows, {}, fam)
    assert [a['key'] for a in mix_noop] == ['software-licence'], \
        "the no-override path should behave exactly as the old family-grain code"

    # And the router must actually hand them over.
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    assert 'license_product_class' in src, "the router never reads the override table"

    # ⚠ Read the CALL SITES, not the file. The first version of this assertion was
    # a regex for `_class_rollup(rows, ... product_classes`, which matched the
    # function's own DEFINITION — so deleting the argument from the real call left
    # the test green. Verified by doing exactly that.
    calls = []
    for m in re.finditer(r'(?<!def )\b_class_rollup\(', src):
        i = m.end()
        depth, start = 1, i
        while i < len(src) and depth:
            depth += (src[i] == '(') - (src[i] == ')')
            i += 1
        calls.append(src[start:i - 1])
    assert calls, "_class_rollup is never called"
    for args in calls:
        assert 'product_classes' in args, (
            f"_class_rollup is called without product classes, so the override "
            f"layer is inert: _class_rollup({' '.join(args.split())})")

    assert 'licenseclass.resolve(' in src, \
        "per-contract class resolution is gone from the family endpoint"


def test_product_class_seed_is_actually_consumed():
    """⚠ A seed nothing reads is indistinguishable from one that works — the rate
    card file was inert for two commits with a passing shape test. Assert the
    LOADER opens this one, and that an override naming a nonexistent product is
    reported rather than silently doing nothing."""
    src = open(os.path.join(ROOT, 'api/build_license_procurement.py'),
               encoding='utf-8').read()
    assert 'license_product_class.csv' in src, "nothing loads the product-class seed"
    assert 'CREATE TABLE IF NOT EXISTS license_product_class' in src, \
        "the product-class table is never created"
    assert 'MATCH NO PRODUCT' in src, \
        "the loader no longer reports inert overrides, so a typo would be silent"
    # ⚠ Must not wipe a future AI-written tier, the way a TRUNCATE once wiped 392
    # AI capabilities.
    assert "DELETE FROM license_product_class WHERE tier='curated'" in src, \
        "the loader deletes more than the curated rows it owns"


def test_class_vocabulary_does_not_drift_from_the_classifier():
    """⚠ The vocabulary now lives in modules/licenseclass so the router, loader,
    seeds and classifier cannot disagree. The classifier keeps its own literal
    (it must run standalone), so pin them to each other — a class the AI can emit
    but the resolver does not know would be dropped on the floor."""
    licenseclass = _licenseclass()

    src = open(os.path.join(ROOT, 'api/classify_license_purchases.py'),
               encoding='utf-8').read()
    m = re.search(r'CLASSES\s*=\s*\[(.*?)\]', src, re.DOTALL)
    assert m, "cannot find CLASSES in the classifier"
    theirs = set(re.findall(r'"([a-z-]+)"', m.group(1)))
    assert theirs == set(licenseclass.CLASSES), (
        f"class vocabulary has drifted: classifier={sorted(theirs)} "
        f"module={sorted(licenseclass.CLASSES)}")

    lev = re.search(r'LEVER_FOR\s*=\s*\{(.*?)\}', src, re.DOTALL)
    assert lev, "cannot find LEVER_FOR in the classifier"
    theirs_lev = dict(re.findall(r'"([a-z-]+)":\s*"([a-z-]+)"', lev.group(1)))
    assert theirs_lev == dict(licenseclass.LEVER_FOR), \
        "the lever mapping has drifted between the classifier and the module"


def test_product_grain_norm_matches_the_builder():
    """⚠ An override is keyed on norm(product). If this definition drifts from
    build_license_families.norm the keys stop matching and every override becomes
    inert — silently, because an unmatched override is not an error."""
    licenseclass = _licenseclass()

    src = open(os.path.join(ROOT, 'api/build_license_families.py'), encoding='utf-8').read()
    m = re.search(r'def norm\(s: str\) -> str:.*?return (.*?)\n', src, re.DOTALL)
    assert m, "cannot find the builder's norm()"
    for probe in ('Microsoft Unified Support', 'MICROSOFT  UNIFIED  SUPPORT',
                  'Accellion/Kiteworks', 'Esri ArcGIS', "Adam's European"):
        assert licenseclass.norm(probe) == _norm(probe), \
            f"norm() disagrees with the builder on {probe!r}"


def test_the_family_page_states_a_mixed_class_instead_of_absorbing_it():
    """⚠ The whole point of the product grain is visible on the page. If the mix
    block goes, a family's dominant class silently speaks for its minority
    purchases again — which is the AWS failure at family scale."""
    body = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php'),
        encoding='utf-8').read()
    assert "class_mix" in body, "the family page no longer renders its class mix"
    assert "class_mixed" in body, "the mixed-class flag is not consulted"
    assert 'not all one kind of purchase' in body, \
        "the page no longer tells the reader the family holds several purchase kinds"
    # ⚠ A Blade directive glued to a word character is not compiled; every
    # conditional phrase here must be precomputed in @php.
    assert '@php' in body


def test_ibm_is_split_by_product_and_citrix_is_not():
    """⚠ THE RULE THIS PAIR ENCODES: group at vendor level when the products do the
    SAME job; split when they do different jobs, because a family carries exactly
    ONE function tag and ONE lever.

    IBM was one family with the function `database-platform` covering statistical
    analysis, document imaging and database security — wrong for two thirds of the
    value, and unfixable at that grain. Citrix stays merged because its products
    are all desktop/access virtualisation.
    """
    rules = _rules()
    def fam(p):
        return rules.get(_norm(p), (None, None))[0]

    assert fam('IBM SPSS') == fam('SPSS') == 'IBM SPSS', \
        "SPSS is back inside a catch-all IBM family"
    assert fam('IBM Guardium') == 'IBM Guardium'
    assert fam('FileNet') == 'IBM FileNet'
    # ⚠ Three different jobs must not share a family again.
    assert len({fam('IBM SPSS'), fam('IBM Guardium'), fam('FileNet')}) == 3, \
        "the IBM products have been re-merged, so one function tag speaks for all"
    # The unattributable string keeps the vendor-level residual.
    assert fam('IBM Software') == 'IBM', \
        "`IBM Software` names no product and must stay the vendor-level residual"
    # Same-job products stay grouped — the control for the rule above.
    assert fam('Citrix') == fam('Citrix ShareFile') == fam('Citrix Netscaler') == 'Citrix'

    # ⚠ A SPLIT MUST NOT COST COVERAGE. New families the AI pass has never seen
    # fall into `(unclassified)`, so each needs a curated class or the split reads
    # as a regression on the page.
    classed = {r['family'].strip(): r for r in _seed('license_family_class.csv')}
    for f in ('IBM SPSS', 'IBM Guardium', 'IBM FileNet', 'IBM'):
        assert f in classed, f"{f} has no class, so the split moved value to unclassified"
        assert (classed[f].get('why') or '').strip(), f"{f} classified with no reason"
    # And the function tags must actually differ — the whole point of splitting.
    caps = {classed[f].get('capability') for f in ('IBM SPSS', 'IBM Guardium', 'IBM FileNet')}
    assert len(caps) == 3, f"the split families share a function tag: {caps}"


def test_the_class_tier_is_surfaced_so_a_reader_can_tell_reviewed_from_auto():
    """⚠ THE GAP PUBLISHING CREATED. The summary block has always shown whether it
    was curated; the purchase CLASS did not — so on a public page a reader could not
    tell a hand-held classification from an automatic one, while the paragraph
    directly above it disclosed exactly that. Only 44 of 434 families are curated,
    so for most of the page the honest answer is "not reviewed".

    ⚠ The tier must travel the WHOLE way: SQL -> resolve() -> the endpoint -> the
    template. A break anywhere silently degrades to "auto", which reads as a
    deliberate disclosure rather than a bug — so each hop is asserted separately.
    """
    licenseclass = _licenseclass()

    # 1. resolve() carries it, and defaults to the SAFE direction.
    fam = {'F': {'class': 'software-licence', 'lever': 'open-source-substitute',
                 'tier': 'curated'}}
    assert licenseclass.resolve('p', 'F', {}, fam)['tier'] == 'curated'
    # ⚠ A row with no tier must NOT read as reviewed. Claiming review is the
    # harmful error; an unlabelled row is not evidence of it.
    assert licenseclass.resolve('p', 'F', {}, {'F': {'class': 'x'}})['tier'] == 'auto'
    assert licenseclass.resolve('p', 'nope', {}, fam)['tier'] == ''

    # 2. A bucket aggregating both tiers reports 'mixed', never the flattering one.
    prod = {licenseclass.norm('q'): {'class': 'software-licence', 'tier': 'curated'}}
    mix, _ = licenseclass.mix(
        [{'product': 'p', 'family': 'F', 'value': 1.0},
         {'product': 'q', 'family': 'F', 'value': 1.0}],
        prod, {'F': {'class': 'software-licence', 'tier': 'auto'}})
    assert len(mix) == 1 and mix[0]['tier'] == 'mixed', \
        f"a part-reviewed bucket reports {mix[0]['tier']!r} instead of 'mixed'"

    # 3. The SQL actually selects it — the hop most likely to be forgotten, and the
    # one that fails silently because every tier would then default to 'auto'.
    src = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    for table in ('license_family_class', 'license_product_class'):
        m = re.search(r'"SELECT ([^"]*) FROM ' + table + r'"', src)
        assert m, f"cannot find the {table} query"
        assert 'tier' in m.group(1), \
            f"the {table} query no longer selects tier, so every class reads as auto"
    assert '"class_tier"' in src, "the family endpoint no longer returns class_tier"

    # ⚠ And the column must exist wherever that query runs. The fetch is wrapped in
    # a try/except that leaves `classes` EMPTY on error, so a missing column would
    # blank the whole purchase-class view rather than raise.
    loader = open(os.path.join(ROOT, 'api/build_license_procurement.py'),
                  encoding='utf-8').read()
    assert 'ADD COLUMN IF NOT EXISTS tier' in loader, \
        "the loader no longer guarantees the tier column it is now SELECTed on"

    # 4. The template renders it, and does not overclaim.
    body = open(os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-license-family.blade.php'),
        encoding='utf-8').read()
    assert "class_tier" in body, "the family page does not read the class tier"
    rendered = re.sub(r'\{\{--.*?--\}\}', '', body, flags=re.DOTALL)
    assert 'not yet reviewed by a person' in rendered, \
        "the page no longer tells a reader when a classification is unreviewed"
    # ⚠ Same discipline as the summary block: curated means held fixed and
    # reviewable, NOT human-authored. Do not let the page claim authorship.
    assert 'written by a person' not in rendered, \
        "the class tier now claims human authorship, which curated does not mean"


def test_the_family_table_is_one_table_and_every_column_sorts():
    """⚠⚠ TWO TABLES, ONE DATASET. "One product, many separate contracts" was a
    filtered, re-sorted subset of "Product families by value" — same rows, same
    numbers, ranked by agencies instead of value — and nothing on the page said so.
    Measured before the merge: all 8 rows of the shortlist appeared in the family
    table with identical agencies/contracts/value, while the two visible lists
    overlapped in exactly ONE row, so they read as unrelated findings.

    They are now one table. The threshold survives as a per-row flag, a count and a
    filter; the ranking survives as a column you can sort.

    ⚠⚠ WHY EVERY NUMERIC CELL CARRIES `data-order`, STATED CORRECTLY. The first
    version of this guard said `Expiring` and `Non-competitive` had been sorting as
    TEXT because they rendered "-" with no sort key. **That was an inference and it
    was wrong** — measured afterwards in a browser, a column of `12 / 9 / - / 4`
    detects as `num` and sorts correctly (DataTables treats "-" as a null-like), and
    `1,205 / 255 / 83` detects as `num-fmt` and sorts correctly too.

    What actually breaks is a MIXED-UNIT column: `$79.8M / $100K / $644.1M / $9K`
    detects as `string` and sorts `$9K, $79.8M, $644.1M, $100K`, because the visible
    text is not monotonic in the underlying value. So the rule is: **a cell whose
    text is not monotonic in its value needs `data-order`** — money and shares here.
    The keys on the count columns are defensive rather than corrective: an explicit
    key does not depend on type-detection heuristics or on the data staying
    dash-free. This assertion covers all of them because a uniform rule is cheaper
    to keep than a per-column judgement, and it is the only one that survives a new
    column being added.
    """
    view_path = os.path.join(
        ROOT, 'app/resources/views/procurement/digital-reform-licenses.blade.php')
    view = open(view_path, encoding='utf-8').read()

    # One table: the shortlist's loop and heading are gone.
    assert '@foreach($frag as' not in view, \
        "the separate fragmented table is back — it is a subset of the family table"
    body = _rendered_copy(view)
    assert 'One product, many separate contracts' not in body, \
        "the merged-away heading is back in the rendered copy"
    # …but its anchor still resolves, so old links do not die.
    assert 'id="fragmented"' in view, \
        "the #fragmented anchor is gone; links to the merged-away table now land nowhere"

    # The finding survives, stated from the payload rather than typed.
    assert '$fragCount' in view and "$totals['fragmented']" in view, \
        "the consolidation count is no longer rendered from the payload"
    assert '$fragRule' in view and "consolidation_rule" in view, \
        "the threshold is no longer read from the payload — it must not be typed"
    assert re.search(r"\$fragRule\['min_agencies'\]", view), \
        "the rule's numbers are not rendered, so the badge is an unexplained opinion"
    # ⚠ $totals must be assigned BEFORE it is read. Written the other way round
    # first, the count silently rendered 0 — a wrong number that looks measured.
    assert view.index("$totals = $lic['totals']") < view.index("$fragCount ="), \
        "$fragCount reads $totals before it is assigned; it will render 0"

    # Sortability: every numeric cell in the family table carries a sort key.
    i = view.index('id="licFamilyTable"')
    table = view[i:view.index('</table>', i)]
    numeric = re.findall(r'<td class="lic-num[^"]*"([^>]*)>', table)
    assert numeric, "the family table has no numeric cells — this guard is scanning nothing"
    missing = [c for c in numeric if 'data-order=' not in c]
    assert not missing, (
        f"{len(missing)} numeric cells in the family table have no `data-order`. "
        "DataTables then sorts the column as TEXT, which is how a formatted number "
        "or a '-' placeholder makes 9 sort after 12.")

    # A merge is exactly where a column count drifts, so pin the shape.
    head = view[i:view.index('</thead>', i)]
    n_head = len(re.findall(r'<th[ >]', head))
    fam_row = table[table.index('@foreach($fams'):table.index('@if($generic')]
    gen_row = table[table.index('@if($generic'):]
    assert n_head == len(re.findall(r'<td[ >]', fam_row)) == len(re.findall(r'<td[ >]', gen_row)), (
        f"column count mismatch: {n_head} headers, "
        f"{len(re.findall(r'<td[ >]', fam_row))} family cells, "
        f"{len(re.findall(r'<td[ >]', gen_row))} unidentified-row cells")

    # The filter must read the API's flag, never re-derive the threshold client-side.
    assert 'data-frag=' in view and 'licFragOnly' in view, \
        "the consolidation filter is gone"
    js = view[view.index('licFragOnly'):]
    assert not re.search(r'agencies\s*>=\s*3|>=\s*3\s*&&', js), \
        "the filter re-derives the threshold in JavaScript — it must read the flag " \
        "the API computed, or the badge and the filter can disagree"


def test_the_consolidation_flag_and_its_count_come_from_one_rule():
    """The badge, the count and the filter are three surfaces of one predicate. They
    used to be one inline expression feeding one table; with three consumers, the
    predicate needs a name and the count needs to be derived from the flags."""
    api = open(os.path.join(ROOT, 'api/routers/licenses.py'), encoding='utf-8').read()
    for const in ('_FAMILY_FRAG_MIN_AGENCIES', '_FAMILY_FRAG_MIN_CONTRACTS'):
        assert f'{const} = ' in api, f"{const} is gone — the threshold is inline again"
    assert re.search(r'f\["consolidation_candidate"\] = \(\s*\n?\s*f\["agencies"\] >= _FAMILY_FRAG_MIN_AGENCIES',
                     api), "the per-row flag no longer uses the named threshold"
    # ⚠ The count must come from the FLAGS, not from a second copy of the predicate.
    assert 'frag_all = sorted([f for f in real if f["consolidation_candidate"]]' in api, \
        "the shortlist count is derived from its own expression again — it can now " \
        "disagree with the badge on the row beside it"
    assert '"consolidation_rule": {"min_agencies": _FAMILY_FRAG_MIN_AGENCIES' in api, \
        "the rule is no longer served, so the page has to hardcode it"
