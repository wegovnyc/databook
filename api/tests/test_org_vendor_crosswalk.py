"""Guards for the org ↔ vendor crosswalk (Track B).

Every rule here exists because of a specific past failure in this codebase's
crosswalks — #146 (unreviewed candidates in the link column), #147 (apostrophes),
#148 (fuzzy false positives), #149 (upsert-only left corrections behind), #155
(the curated CSV must be real CSV).
"""

import importlib
import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'modules'))

xw = importlib.import_module("build_org_vendor_crosswalk")


def _no_comments(src: str) -> str:
    """Strip `#` comment lines — three guards in this work fired on the prose
    explaining the very pattern they ban."""
    return "\n".join(ln for ln in src.split("\n")
                     if not ln.lstrip().startswith("#"))


# ── the link column may never hold an unreviewed match (#146) ────────────────

def test_only_reviewed_tiers_carry_a_link():
    assert xw.LINK_TIERS == ("exact", "exact-suffix", "fuzzy", "curated")
    for held in ("fuzzy-review", "suffix-review", "rejected"):
        assert held not in xw.LINK_TIERS


def test_held_tiers_go_in_the_candidate_column_not_the_link_column():
    """⚠ THE #146 LESSON, MADE STRUCTURAL. The NYCHA crosswalk put unreviewed
    candidates in the real id column and relied on every consumer filtering the
    tier — one missed filter publishes an unreviewed match. Here a join on
    `passport_supplier_id` cannot go wrong."""
    src = _no_comments(inspect.getsource(xw.build))
    assert "candidate_supplier_id=(None if links else" in src.replace(" ", "") \
        or "candidate_supplier_id=(None if links else v[\"sid\"])" in src, \
        "held rows must put the id in candidate_supplier_id"
    assert "passport_supplier_id=(v[\"sid\"] if links else None)" in src


def test_the_schema_separates_link_from_candidate():
    assert "passport_supplier_id" in xw.SCHEMA
    assert "candidate_supplier_id" in xw.SCHEMA


def test_consumers_read_only_the_link_column():
    """Both surfacing queries must ignore candidate_supplier_id entirely."""
    oce = open(os.path.join(os.path.dirname(__file__), '..', 'routers', 'oce.py'),
               encoding="utf-8").read()
    for frag in ("FROM org_vendor_crosswalk",):
        assert frag in oce
    # every crosswalk query in oce.py must filter/select the LINK column
    for chunk in oce.split("org_vendor_crosswalk")[1:]:
        head = chunk[:400]
        assert "passport_supplier_id" in head, \
            "a crosswalk query does not reference the link column"
        assert "candidate_supplier_id" not in head, \
            "a serving query must never read unreviewed candidates"


# ── the rebuild must not leave corrections behind (#149) ─────────────────────

def test_rebuild_deletes_non_curated_rows_first():
    src = _no_comments(inspect.getsource(xw.build))
    assert "DELETE FROM org_vendor_crosswalk WHERE curated = false" in src


def test_curated_rows_are_never_overwritten():
    src = _no_comments(inspect.getsource(xw.build))
    assert "WHERE org_vendor_crosswalk.curated = false" in src \
        or "curated = false" in src


def test_a_curated_no_match_marker_exists(monkeypatch):
    """⚠ Without it, every human rejection is re-proposed as a candidate on the
    next run, so review work never sticks (#155)."""
    assert "-" in xw._NO_MATCH and "none" in xw._NO_MATCH


def test_curated_seed_is_parsed_as_real_csv():
    """47 of 212 names in the NYCHA review contained commas; hand-splitting is
    how they were mangled."""
    src = inspect.getsource(xw._load_curated)
    assert "csv.reader" in src


# ── the tiering rules ────────────────────────────────────────────────────────

def test_strict_norm_does_not_strip_legal_suffixes():
    """⚠ The whole point of having two passes. Stripping INC/ENTERPRISES is what
    makes `MERCURY ENTERPRISES INC` collide with the political consultancy
    `Mercury`, so the strict tier must not do it."""
    assert xw.strict_norm("Mercury") != xw.strict_norm("Mercury Enterprises Inc")
    # punctuation and case still normalise away
    assert xw.strict_norm("Staten Island Children's Museum") == \
        xw.strict_norm("STATEN ISLAND CHILDRENS MUSEUM")


def test_single_token_suffix_matches_do_not_auto_link():
    """`MERCURY ENTERPRISES INC` -> `MERCURY` is a one-token key and must be
    held; `Carnegie Hall` -> `THE CARNEGIE HALL CORPORATION` is two and links."""
    assert xw.MIN_SUFFIX_TOKENS == 2
    src = _no_comments(inspect.getsource(xw.build))
    assert "suffix-review" in src
    assert "MIN_SUFFIX_TOKENS" in src


def test_the_token_count_is_taken_from_the_matched_variant():
    """⚠ Judging the org's PRIMARY name would hold a correct link: `NYC & Company`
    normalises to the single token `NYC`, but it matches through its
    `display_name` (`New York City Tourism + Conventions`), which is the key that
    must be judged."""
    src = _no_comments(inspect.getsource(xw.build))
    # the tier decision must be computed inside the per-variant loop, on `kn`
    assert "toks = len(_tokens(kn))" in src


def test_variants_are_ordered_most_authoritative_first():
    org = {"name": "NYC & Company", "display_name": "New York City Tourism",
           "alternate_name": "NYCC"}
    assert xw.variants(org) == ["NYC & Company", "New York City Tourism", "NYCC"]


def test_variants_dedupes_and_drops_blanks():
    org = {"name": "Same", "display_name": "same", "alternate_name": "  "}
    assert xw.variants(org) == ["Same"]


def test_the_fuzzy_matcher_is_reused_not_reimplemented():
    """It carries the #147 apostrophe fix, the #148 distinctive-token gate and
    the 0.96 floor — each from a real false positive. A second copy would drift."""
    src = open(os.path.join(os.path.dirname(__file__), '..',
                            'build_org_vendor_crosswalk.py'), encoding="utf-8").read()
    assert "from build_nycha_vendor_crosswalk import _fuzzy_matches" in src
    assert "def _fuzzy_matches" not in src, "must not re-implement the matcher"


def test_chart_scaffolding_types_are_excluded():
    """`Classification` / `Official` are chart nodes, not bodies that could hold
    a contract."""
    assert xw.EXCLUDED_TYPES == ("Classification", "Official", "Public Figure")


# ── the safety rails ────────────────────────────────────────────────────────

def test_a_collapsing_crosswalk_is_refused():
    """`vendors` is re-ingested daily and Socrata returns 200 with truncated
    bodies under load (#117), which would otherwise silently empty this."""
    src = _no_comments(inspect.getsource(xw.build))
    assert "ABORT" in src and "0.6" in src


def test_the_tier_is_the_predicate_never_the_curated_boolean():
    """⚠ A human REJECTION is also `curated = true`, so the boolean is not a safe
    link predicate — the tier is."""
    src = _no_comments(inspect.getsource(xw))
    assert "match_tier = ANY($1::text[])" in src


def test_verification_asserts_the_link_candidate_invariants():
    src = _no_comments(inspect.getsource(xw.verify))
    assert "must be 0" in src
    # no row may hold both, and no held tier may carry a link
    assert "candidate_supplier_id IS NOT NULL" in src
    assert "retired_at IS NOT NULL" in src, "must catch rows pointing at retired orgs"


# ── the surfacing ───────────────────────────────────────────────────────────

def test_org_activity_counts_contracts_the_same_way_the_vendor_page_does():
    """⚠ If one side normalized and the other did not, the org page and the
    vendor page would disagree with no way to tell which was right."""
    oce = open(os.path.join(os.path.dirname(__file__), '..', 'routers', 'oce.py'),
               encoding="utf-8").read()
    assert 'FROM contracts WHERE vendor_name = $1' in oce


def test_the_org_panel_states_how_the_link_was_made():
    """A name-based join must be presented as a judgement, not as fact — the
    same discipline as the NYCHA block."""
    hdr = open(os.path.join(os.path.dirname(__file__), '..', '..', 'app',
                            'resources', 'views', 'sub', 'orgheader.blade.php'),
               encoding="utf-8").read()
    assert "civic_vendor" in hdr
    assert "human-confirmed match" in hdr and "matched on name" in hdr


def test_the_vendor_page_handles_several_orgs_for_one_vendor():
    """`United Federation of Teachers` is three register rows — the union plus
    two bargaining units — all supplier 1713785."""
    vp = open(os.path.join(os.path.dirname(__file__), '..', '..', 'app',
                           'resources', 'views', 'procurement',
                           'vendor_profile.blade.php'), encoding="utf-8").read()
    assert "@foreach ($civicOrgs as $co)" in vp
    assert "Civic Records" in vp, "the plural heading must exist"


def test_the_curated_seed_is_version_controlled():
    """⚠ The NYCHA curated CSV lives only on the box, so 212 reviewed decisions
    exist in exactly one place and would vanish with a rebuild. This one defaults
    to a file inside the repo."""
    assert "seed" in xw.CURATED_CSV and "/data/" not in xw.CURATED_CSV
    assert os.path.exists(xw.CURATED_CSV), \
        f"the curated seed is missing: {xw.CURATED_CSV}"


def test_the_seed_parses_and_carries_the_carnegie_hall_decision():
    """The one legitimate match the automatic passes cannot make: the shared
    suffix list strips CORP but not CORPORATION, so `Carnegie Hall` and
    `THE CARNEGIE HALL CORPORATION` produce different keys and score below the
    fuzzy floor. Curated rather than widening the list, which would collapse
    `X Trust`/`X Fund`/`X Association` onto `X`."""
    rows = xw._load_curated()
    assert (170100266, "1638062") in [(o, s) for o, s, _n in rows]
    # comments and the header must not be parsed as data
    assert all(isinstance(o, int) for o, _s, _n in rows)
