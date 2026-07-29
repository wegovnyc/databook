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


class _FakeConn:
    """Minimal asyncpg-shaped stub for the unmapped sweep."""

    def __init__(self, datasets):
        self._datasets = datasets

    async def fetch(self, *_a, **_k):
        return []

    async def fetchval(self, *_a, **_k):
        return None

    async def execute(self, *_a, **_k):
        return "INSERT 0 1"


class TestUnmappedScanSweep:
    """The sweep must run independently of what was ingested this cycle.

    scan_unmapped_entities used to be called only as a post-step inside the
    ingest functions, so in production it never ran: normalizer-driven datasets
    are ingested by the normalizer's own sweep via /import-csv (which does not
    scan), and the api scheduler then sees "up to date" and returns before its
    scan call. Measured on prod 2026-07-29: 18 unmapped values across 9
    scannable datasets, and unmapped_entities held 0 rows.
    """

    def _run(self, datasets, monkeypatch):
        import asyncio
        import data_scheduler as sched

        seen, alerts = [], []

        async def fake_scan(conn, ds):
            seen.append(ds['table_name'])
            return ds.get('_fake_new', [])

        async def fake_alert(table, col, new, nid):
            alerts.append((table, len(new)))

        async def fake_get_active(conn):
            return datasets

        monkeypatch.setattr(sched, "scan_unmapped_entities", fake_scan)
        monkeypatch.setattr(sched, "send_unmapped_alert", fake_alert)
        monkeypatch.setattr(sched, "get_active_datasets", fake_get_active)
        asyncio.run(sched._run_unmapped_scan(_FakeConn(datasets)))
        return seen, alerts

    def test_scans_without_any_ingest_having_happened(self, monkeypatch):
        """The whole point: no ingest occurred this cycle, scan anyway."""
        ds = [{"table_name": "crol", "needs_normalization": True,
               "entity_column": "AgencyName", "_fake_new": ["NEW AGENCY"]}]
        seen, alerts = self._run(ds, monkeypatch)
        assert seen == ["crol"]
        assert alerts == [("crol", 1)]

    def test_skips_datasets_that_cannot_be_scanned(self, monkeypatch):
        ds = [
            {"table_name": "flag_off", "needs_normalization": False,
             "entity_column": "Agency"},
            {"table_name": "no_entity_col", "needs_normalization": True,
             "entity_column": ""},
            {"table_name": "ok", "needs_normalization": True,
             "entity_column": "Agency"},
        ]
        seen, _ = self._run(ds, monkeypatch)
        assert seen == ["ok"]

    def test_no_alert_when_nothing_new(self, monkeypatch):
        ds = [{"table_name": "clean", "needs_normalization": True,
               "entity_column": "Agency", "_fake_new": []}]
        seen, alerts = self._run(ds, monkeypatch)
        assert seen == ["clean"]
        assert alerts == []

    def test_one_failing_table_does_not_abort_the_sweep(self, monkeypatch):
        import asyncio
        import data_scheduler as sched
        seen = []

        async def fake_scan(conn, ds):
            if ds['table_name'] == "boom":
                raise RuntimeError("column vanished")
            seen.append(ds['table_name'])
            return []

        async def fake_get_active(conn):
            return ds_list

        ds_list = [
            {"table_name": "boom", "needs_normalization": True,
             "entity_column": "Agency"},
            {"table_name": "after", "needs_normalization": True,
             "entity_column": "Agency"},
        ]
        monkeypatch.setattr(sched, "scan_unmapped_entities", fake_scan)
        monkeypatch.setattr(sched, "get_active_datasets", fake_get_active)
        asyncio.run(sched._run_unmapped_scan(_FakeConn(ds_list)))
        assert seen == ["after"], "sweep must continue past a failing table"


class TestUnmappedScanIsWiredIntoTheCycle:
    def test_cycle_calls_the_sweep(self):
        """Assert the CALL, not the substring — `async def _run_unmapped_scan(
        conn)` also contains the bare name, so a looser check passes even with
        the call deleted (which it did, first time round)."""
        import inspect
        import data_scheduler as sched
        src = inspect.getsource(sched)
        assert "await _run_unmapped_scan(conn)" in src, (
            "the scheduler cycle must call _run_unmapped_scan — otherwise the "
            "unmapped-entity check silently never runs, and /pipeline/health "
            "reports total_alerts: 0 from a check that never executed."
        )
