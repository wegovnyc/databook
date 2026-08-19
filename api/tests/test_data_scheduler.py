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


class TestProcurementTableIndexes:
    """The three PASSPort tables (`contracts`, `vendors`, `solicitations`) had
    ZERO indexes on prod — measured 2026-08-04, `pg_indexes` returned no rows
    for any of them, so /oce/contract/{id} opened with a seq scan over 55,806
    rows (`Rows Removed by Filter: 55805`).

    They cannot be fixed by hand: the extractor path COPYs into
    `_staging_<table>`, DROPs the real table and RENAMEs the staging one over
    it, and the staging table has no indexes — so any manually created index is
    destroyed on the next ingest. TABLE_INDEXES + the post-ingest hook is the
    only durable declaration point.
    """

    def test_contracts_indexes_are_declared(self):
        from data_scheduler import TABLE_INDEXES
        cols = {c for _n, c in TABLE_INDEXES.get("contracts", [])}
        # Each of these backs a measured equality predicate in the request path.
        assert {"ctr_id", "contract_id", "epin", "vendor_name"} <= cols

    def test_vendors_and_solicitations_indexes_are_declared(self):
        from data_scheduler import TABLE_INDEXES
        assert {c for _n, c in TABLE_INDEXES.get("vendors", [])} >= {
            '"PASSPort Supplier-ID"', '"Vendor Name"'}
        assert {c for _n, c in TABLE_INDEXES.get("solicitations", [])} == {
            '"EPIN"'}

    def test_declared_contracts_columns_exist_in_the_ddl(self):
        """The real failure mode. recreate_table_indexes SWALLOWS a failed
        CREATE INDEX (prints an x and moves on), so an index naming a column
        that does not exist would never be created and nothing would raise —
        the same 'declared but silently never runs' shape as the unreachable
        register_untracked_tables(). Pin the declared columns to the DDL the
        ingest actually creates.
        """
        from data_scheduler import TABLE_INDEXES, _CONTRACTS_COLS
        for idx_name, col in TABLE_INDEXES["contracts"]:
            assert col in _CONTRACTS_COLS, (
                f"{idx_name} indexes contracts.{col}, which is not in "
                f"_CONTRACTS_DDL — CREATE INDEX would fail and be swallowed"
            )

    def test_every_indexed_table_has_the_hook_registered(self):
        """An index declared for a table with no hook is never recreated."""
        from data_scheduler import TABLE_INDEXES, POST_INGEST_HOOKS
        for tbl in TABLE_INDEXES:
            assert POST_INGEST_HOOKS.get(tbl), f"{tbl} has no post-ingest hook"

    def test_index_hook_runs_before_the_other_hooks(self):
        """`vendors` carries three enrichment hooks that query it by name, so
        the index rebuild must come first or they seq-scan an unindexed table."""
        from data_scheduler import POST_INGEST_HOOKS
        first = POST_INGEST_HOOKS["vendors"][0]
        assert first.__name__ == "<lambda>", (
            "the index-recreation lambda must be first in vendors' hook list"
        )
        assert len(POST_INGEST_HOOKS["vendors"]) == 4

    def test_recreate_creates_each_index_then_analyzes(self):
        """A brand-new index on a just-renamed table is ignored by the planner
        until the table has statistics, so the ANALYZE is load-bearing: without
        it this hook can report success while every lookup still seq-scans."""
        import asyncio
        from data_scheduler import recreate_table_indexes

        run = []

        class _Conn:
            async def execute(self, sql, *_a):
                run.append(" ".join(sql.split()))
                return "CREATE INDEX"

        asyncio.run(recreate_table_indexes(_Conn(), "contracts"))
        # ⚠ COUNTED FROM THE DECLARATIONS, not pinned to a literal. This asserted
        # `== 4` and fired when the hook took on the GIN half — correctly, because
        # the count changed; but a magic number here just has to be re-guessed every
        # time an index is added. Both families, from their own sources.
        from data_scheduler import TABLE_INDEXES, searchindexes
        expected = len(TABLE_INDEXES["contracts"]) + len(searchindexes.for_table("contracts"))
        assert sum("CREATE INDEX" in s for s in run) == expected
        assert 'CREATE INDEX IF NOT EXISTS idx_contracts_ctr_id ON "contracts"(ctr_id)' in run
        # The GIN half must go through too — this is the half that was missing on
        # prod entirely, because nothing reapplied it after the extractor ingest.
        assert any("gin (contract_title gin_trgm_ops)" in s for s in run), \
            "the search indexes are no longer recreated by the hook"
        assert run[-1] == 'ANALYZE "contracts"', "ANALYZE must run after the indexes"

    def test_a_failed_index_does_not_abort_the_rest(self):
        """Fail-soft: one bad index must not cost the others, and must not take
        down the ingest that triggered the hook."""
        import asyncio
        from data_scheduler import recreate_table_indexes

        run = []

        class _Conn:
            async def execute(self, sql, *_a):
                if "idx_contracts_epin" in sql:
                    raise RuntimeError("boom")
                run.append(" ".join(sql.split()))
                return "CREATE INDEX"

        asyncio.run(recreate_table_indexes(_Conn(), "contracts"))
        from data_scheduler import TABLE_INDEXES, searchindexes
        _all = len(TABLE_INDEXES["contracts"]) + len(searchindexes.for_table("contracts"))
        assert sum("CREATE INDEX" in s for s in run) == _all - 1
        assert run[-1] == 'ANALYZE "contracts"'
