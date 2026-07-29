"""Guards the Doing Business (LL34) loader — api/enrich_doing_business.py.

Three things here fail silently rather than loudly, so they are pinned:

1. **Every source date is missing its century** (`0017-07-01`). A naive parse
   yields year 17 and sorts/renders as nonsense; repair_year must add 2000 and
   only 2000.
2. **MOCS publishes no dictionary for `relationship_type_code`.** The mapping
   must therefore stay minimal and honest: label only what MOCS documents or
   what the data itself demonstrates, and never invent a title for a named
   individual. A future contributor "helpfully" filling in MCT/MRP/MPI is the
   regression this catches.
3. **EWN rows are organizations, not people** (GOLDMAN SACHS, KRM 2021
   IRREVOCABLE TRUST). Rendering one as a person would attribute a company's
   ownership stake to an individual.
"""

import pytest

from enrich_doing_business import (
    _ROLES,
    _SENIOR_MANAGER_CODES,
    norm_name,
    ownership_label,
    repair_year,
    role_of,
)


@pytest.mark.parametrize("raw,expected", [
    ("0017-07-01T00:00:00.000", "2017-07-01"),   # the standard corrupt shape
    ("0008-01-15T00:00:00.000", "2008-01-15"),   # earliest observed year
    ("0024-01-30T00:00:00.000", "2024-01-30"),   # latest observed year
    ("0025-06-30", "2025-06-30"),                # no time component
    ("2019-05-04T00:00:00.000", "2019-05-04"),   # already sane — untouched
])
def test_repair_year_restores_the_missing_century(raw, expected):
    assert repair_year(raw) == expected


@pytest.mark.parametrize("bad", ["", None, "   ", "not-a-date", "garbage"])
def test_repair_year_returns_none_rather_than_inventing_a_date(bad):
    assert repair_year(bad) is None


def test_repair_year_rejects_implausible_years():
    """A repaired date must land in a sane range, not silently pass through."""
    assert repair_year("9999-01-01") is None


def test_repaired_dates_land_in_the_local_law_34_era():
    """LL34 took effect in 2007, so every repaired year must be >= 2007.

    This is what makes +2000 (rather than +1900) demonstrably right.
    """
    for y in range(8, 25):
        out = repair_year(f"{y:04d}-06-15T00:00:00.000")
        assert out is not None
        assert 2007 <= int(out[:4]) <= 2026, out


def test_only_documented_or_demonstrated_roles_carry_a_label():
    """The honesty invariant: no invented titles for undocumented codes.

    MOCS documents CEO/CFO/COO (LL34 Q&A), OWN ("Owner", attached data
    dictionary) and LOB (lobbyist). EWN is demonstrated by the data itself.
    Everything else must come back with an EMPTY label.
    """
    assert set(_ROLES) == {"CEO", "CFO", "COO", "OWN", "LOB", "EWN"}, (
        "a role label was added — it must be backed by a MOCS document or by "
        "evidence in the data, see the module docstring")
    for code in _SENIOR_MANAGER_CODES | {"POL", "ZZZ", "MCT"}:
        label, group, _ = role_of(code)
        assert label == "", f"{code} must not be given an invented label"


def test_senior_manager_codes_are_grouped_but_not_named():
    """Grouping is supported by LL34 ('at least one Senior Manager'); the
    per-code meaning is not documented, so it must not be asserted."""
    for code in ("MCT", "MRP", "MPI", "MED", "MLU", "MFC", "MGR"):
        label, group, is_org = role_of(code)
        assert group == "Senior manager"
        assert label == ""
        assert is_org is False


def test_unknown_codes_fall_through_to_other():
    label, group, is_org = role_of("POL")
    assert (label, group, is_org) == ("", "Other", False)
    assert role_of(None)[1] == "Other"


def test_ewn_is_flagged_as_an_organization_not_a_person():
    """EWN = an entity owning >=10%. Must never render in a people list."""
    label, group, is_org = role_of("EWN")
    assert is_org is True
    assert group == "Owner"
    assert "organization" in label.lower()
    # Every other documented role is a natural person.
    for code in ("CEO", "CFO", "COO", "OWN", "LOB"):
        assert role_of(code)[2] is False


def test_role_lookup_is_case_and_whitespace_insensitive():
    assert role_of(" ceo ") == role_of("CEO")


def test_ownership_label_handles_the_feeds_case_duplicates():
    """The feed ships both 'cor'/'COR' and 'llc'/'LLC'."""
    assert ownership_label("cor") == ownership_label("COR") == "Business Corporation"
    assert ownership_label("llc") == "Limited Liability Company"


def test_ownership_label_is_empty_for_codes_the_dictionary_omits():
    """⚠ The published dictionary lists Joint Venture as 'JV' but the feed sends
    'JNT', and never mentions IND or GOV. Undocumented codes pass through raw
    (the API falls back to the code) rather than being guessed."""
    for code in ("JNT", "IND", "GOV"):
        assert ownership_label(code) == ""


def test_norm_name_matches_the_other_vendor_join_keys():
    """Must equal enrich_vendor.norm_name so all name joins share one key shape."""
    from enrich_vendor import norm_name as vendor_norm
    for n in ["MAKE THE ROAD NEW YORK", "Sheppard Mullin Richter & Hampton LLP",
              "  O'BRIEN & SONS, INC. "]:
        assert norm_name(n) == vendor_norm(n)
