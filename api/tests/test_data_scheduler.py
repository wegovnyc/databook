"""Tests for the CSV import helpers in data_scheduler.

Regression coverage for the `contracts` ingest, whose source
(mocs-contracts.csv) ships a 26-column header with two spurious trailing
`wegov-org-name`/`wegov-org-id` duplicates while its data rows carry only 24
fields. That combination first crashed CREATE TABLE with Postgres
`column "wegov-org-name" specified more than once`, and once dedupe was added,
the strict row-length check dropped every row as "Empty CSV".
"""

from data_scheduler import dedupe_columns, conform_row


class TestDedupeColumns:
    def test_no_duplicates_unchanged(self):
        assert dedupe_columns(["a", "b", "c"]) == ["a", "b", "c"]

    def test_suffixes_duplicates(self):
        assert dedupe_columns(["x", "x", "x"]) == ["x", "x_1", "x_2"]

    def test_mocs_contracts_header(self):
        header = (
            ["c%d" % i for i in range(22)]
            + ["wegov-org-name", "wegov-org-id",
               "wegov-org-name", "wegov-org-id"]
        )
        out = dedupe_columns(header)
        assert len(out) == 26
        # First pair keeps the canonical names the API/frontend query.
        assert out[22] == "wegov-org-name"
        assert out[23] == "wegov-org-id"
        # Trailing duplicates get suffixed instead of colliding.
        assert out[24] == "wegov-org-name_1"
        assert out[25] == "wegov-org-id_1"


class TestConformRow:
    def test_exact_unchanged(self):
        assert conform_row(["x", "y"], 2) == ("x", "y")

    def test_pads_short_rows(self):
        assert conform_row(["a"], 3) == ("a", "", "")

    def test_truncates_long_rows(self):
        assert conform_row(["a", "b", "c"], 2) == ("a", "b")

    def test_blank_row_skipped(self):
        assert conform_row([], 5) is None

    def test_contracts_24_into_26(self):
        # 24 real fields align to the leading columns; the two spurious
        # duplicate columns are padded empty — no data loss.
        data = ["v%d" % i for i in range(24)]
        row = conform_row(data, 26)
        assert row == tuple(data) + ("", "")
        assert row[22] == "v22"  # wegov-org-name value preserved
