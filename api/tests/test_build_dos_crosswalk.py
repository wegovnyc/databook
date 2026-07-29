"""Guards the NY DOS crosswalk builder (api/build_dos_crosswalk.py).

The registry stores filing dates as MM/DD/YYYY text spanning 1806-2025, and
that date is the whole point of the panel — it is the only place Databook can
say how old a business is. A misparse would render a confident wrong year
rather than failing, so the parser is pinned here, including the ambiguity that
matters most: 03/11/2020 is 11 March, not 3 November.
"""

from datetime import date

import pytest

from build_dos_crosswalk import _address, parse_filing_date


@pytest.mark.parametrize("raw,expected", [
    ("03/11/2020", date(2020, 3, 11)),   # MM/DD, not DD/MM
    ("12/23/1998", date(1998, 12, 23)),
    ("01/01/1806", date(1806, 1, 1)),    # earliest in the registry
    ("12/31/2025", date(2025, 12, 31)),  # latest in the registry
    ("  04/28/1971  ", date(1971, 4, 28)),
])
def test_parses_the_registry_date_format(raw, expected):
    assert parse_filing_date(raw) == expected


def test_month_and_day_are_not_transposed():
    """A DD/MM reading would silently shift a business's age by months."""
    d = parse_filing_date("03/11/2020")
    assert (d.month, d.day) == (3, 11)


@pytest.mark.parametrize("bad", [
    "", None, "   ", "2020-03-11", "not a date", "13/45/2020", "03/11/20xx",
])
def test_returns_none_rather_than_a_wrong_date(bad):
    assert parse_filing_date(bad) is None


@pytest.mark.parametrize("bad", ["01/01/1200", "01/01/3000"])
def test_rejects_years_outside_the_registrys_range(bad):
    """Out-of-range years are corrupt data, not history — better absent."""
    assert parse_filing_date(bad) is None


def test_address_joins_and_collapses_source_whitespace():
    assert _address("123  MAIN ST", "BROOKLYN", "NY", "11201") == \
        "123 MAIN ST, BROOKLYN, NY, 11201"


def test_address_skips_blank_fragments():
    """dos_process_address_1 is 98.3% populated; the rest are sparser."""
    assert _address("", None, "NY", "  ") == "NY"
    assert _address(None, None) == ""
