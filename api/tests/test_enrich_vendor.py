"""Guards the PASSPort vendor sub-table loader (api/enrich_vendor.py).

The loader's whole job is turning five MOCS exports into tables the vendor
profile can join on. Two things about those exports break naive readers, and
both are pinned here because neither fails loudly — a mis-read header silently
loads a column of NULLs, and a drifting normalization silently stops matching:

1. The published headers are irregular: 'Address  Line 2' and 'Contract  ID'
   carry a DOUBLE space, 'To Date ' has a trailing space, and the files are
   UTF-8 with a BOM.
2. `vendor_name_norm` is the join key for every one of these tables, and it
   must stay byte-identical to the normalization oce.py uses to look them up.
"""

import re

from enrich_vendor import _TABLES, _header_index, norm_name


def test_norm_name_matches_the_api_lookup_key():
    """The key written at load time must equal the key the API queries with.

    oce.py::_passport_profile and _sbs_profile both compute
    re.sub(r"[^A-Za-z0-9]", "", name.upper()). If norm_name ever diverges,
    every panel silently returns empty rather than erroring.
    """
    for name in ["ADAM'S EUROPEAN CONTRACTING", "  Congregation Azras Inc ",
                 "J & N Construction Group, LLC", "1 Empire Group LLC",
                 "St. Nick's Alliance Corp.", "34 1/2 E 12TH ST CORP"]:
        assert norm_name(name) == re.sub(r"[^A-Za-z0-9]", "", name.upper())


def test_norm_name_is_whitespace_and_punctuation_insensitive():
    """Leading/trailing space is endemic in these exports ('  Ideal Supply  ')."""
    assert norm_name("  Ideal Supply Company  ") == "IDEALSUPPLYCOMPANY"
    assert norm_name("ADAM'S EUROPEAN") == norm_name("ADAMS EUROPEAN")
    assert norm_name(None) == ""
    assert norm_name("") == ""
    assert norm_name("!!!") == ""


def test_header_index_tolerates_the_published_header_irregularities():
    """Double spaces, trailing space and a BOM must all still resolve."""
    header = ["﻿Vendor Name", "Agency", "Contract  ID", "Purpose",
              "Evaluation Date", "Evaluation Period Start Date",
              "Evaluation Period End Date", "Overall Rating"]
    wanted = ["Vendor Name", "Contract ID", "Overall Rating"]
    idx = _header_index(header, wanted)
    assert idx["Vendor Name"] == 0
    assert idx["Contract ID"] == 2, "double-space 'Contract  ID' must resolve"
    assert idx["Overall Rating"] == 7

    # Trailing space, as shipped in passport_other_names.csv.
    assert _header_index(["Vendor Name", "To Date "], ["To Date"])["To Date"] == 1


def test_header_index_omits_columns_that_are_absent():
    """A dropped upstream column loads as NULL instead of failing the run."""
    idx = _header_index(["Vendor Name"], ["Vendor Name", "Gross Revenue"])
    assert "Gross Revenue" not in idx
    assert idx["Vendor Name"] == 0


def test_every_table_declares_vendor_name_and_a_norm_column():
    """Vendor Name is the join source; vendor_name_norm is the join key.

    A table missing either would load fine and then join to nothing.
    """
    for table, filename, ddl, mapping in _TABLES:
        headers = [h for h, _ in mapping]
        columns = [c for _, c in mapping]
        assert "Vendor Name" in headers, f"{table} cannot be joined to vendors"
        assert "vendor_name" in columns
        assert "vendor_name_norm" in ddl, f"{table} DDL lacks the join key"
        assert filename.endswith(".csv")


def test_evaluations_carries_a_normalized_contract_id():
    """Evaluations also join to `contracts` — 27.7% of contracts have one."""
    ddl = next(d for t, _, d, _ in _TABLES if t == "vendor_evaluations")
    assert "contract_id_norm" in ddl
