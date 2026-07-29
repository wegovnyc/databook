"""Guards on the dataset_registry seed (api/setup_data_pipeline.py).

Why this file exists
--------------------
The seed defines two "(Raw)" entries — cpdb_projects and cpdb_commitments — that
point at the SAME Socrata datasets as the canonical capitalprojectslist and
capitalprojectscommitments. Someone deactivated the first and missed the second,
and the duplicate then spent five months (2026-02-27 → 2026-07-28) POSTing
/process/240/async on every scheduler sweep and failing with an HTML 502, because
a duplicate can never ingest and therefore never satisfies the scheduler's
"already up to date" skip.

Nothing caught it. The registry happily holds two active rows for one source, and
the failure is invisible unless someone reads the error column. These tests make
that shape a build failure instead.
"""

import setup_data_pipeline as seed


def _socrata_ids_by_table():
    """table_name -> socrata_id for every seeded Socrata dataset."""
    out = {}
    for table, meta in seed.METADATA_CORRECTIONS.items():
        sid = (meta or {}).get("socrata_id")
        if sid:
            out[table] = sid
    return out


def _is_suppressed(table):
    return table in seed.DUPLICATE_DATASETS or table in seed.DATED_DATASETS


class TestNoActiveDuplicateSources:
    def test_no_two_active_entries_share_a_socrata_id(self):
        """The exact bug: two ACTIVE registry rows for one Socrata dataset.

        A duplicate is allowed to exist in the seed (the table may still hold
        historical data), but it must be listed in DUPLICATE_DATASETS so setup
        deactivates it and the scheduler leaves it alone.
        """
        by_id = {}
        for table, sid in _socrata_ids_by_table().items():
            if _is_suppressed(table):
                continue
            by_id.setdefault(sid, []).append(table)

        clashes = {sid: tables for sid, tables in by_id.items() if len(tables) > 1}
        assert not clashes, (
            "Two or more ACTIVE registry entries share a Socrata id: "
            f"{clashes}. A duplicate never ingests and re-triggers the "
            "normalizer on every sweep — add the non-canonical table to "
            "DUPLICATE_DATASETS in setup_data_pipeline.py."
        )

    def test_no_two_active_entries_share_a_normalizer_dataset(self):
        """Same failure via the other route: one normalizer dataset, two owners.

        This is what actually caused the 502 — both entries POSTing
        /process/240/async, against a normalizer running --workers 1.
        """
        by_nid = {}
        for table, nid in seed.NORMALIZER_DATASET_IDS.items():
            if _is_suppressed(table):
                continue
            by_nid.setdefault(nid, []).append(table)

        clashes = {nid: tables for nid, tables in by_nid.items() if len(tables) > 1}
        assert not clashes, (
            "Two or more ACTIVE registry entries drive the same normalizer "
            f"dataset: {clashes}. The normalizer runs --workers 1, so the "
            "second concurrent /process call times out at nginx and returns "
            "an HTML 502."
        )


class TestKnownDuplicatesStayListed:
    """Pin the specific entries, so removing one is a deliberate act."""

    def test_cpdb_raw_pair_is_deactivated(self):
        for table in ("cpdb_projects", "cpdb_commitments"):
            assert table in seed.DUPLICATE_DATASETS, (
                f"{table} duplicates a canonical CPDB entry and must stay in "
                "DUPLICATE_DATASETS — it was left active once already and "
                "failed silently for five months."
            )

    def test_raw_passport_tables_stay_deactivated(self):
        for table in ("passport", "passport_contracts", "passport_solicitations"):
            assert table in seed.DUPLICATE_DATASETS

    def test_duplicates_do_not_shadow_a_canonical_entry(self):
        """Every duplicate must have a canonical sibling that is NOT suppressed.

        Guards the opposite mistake: deactivating the entry the site reads from.
        """
        ids = _socrata_ids_by_table()
        for dupe in seed.DUPLICATE_DATASETS:
            sid = ids.get(dupe)
            if not sid:
                continue  # no seeded socrata_id (e.g. the passport tables)
            siblings = [
                t for t, s in ids.items()
                if s == sid and t != dupe and not _is_suppressed(t)
            ]
            assert siblings, (
                f"{dupe} is marked a duplicate but no ACTIVE entry owns "
                f"socrata_id {sid} — deactivating it would orphan the source."
            )


class TestDeactivationsActuallyRun:
    """A declaration nothing applies is worse than no declaration.

    DUPLICATE_DATASETS and DATED_DATASETS were enforced only inside
    register_untracked_tables, which is called only from
    populate_from_datasets_json, which returns early unless a datasets.json
    exists at a local dev path. On prod it does not, so `--populate` bailed
    before reaching it and a bare run never called it — the lists read as
    authoritative while being dead code in production for months.

    These tests pin the wiring so that cannot recur.
    """

    def _main_src(self):
        import inspect
        return inspect.getsource(seed.main)

    def test_main_calls_the_deactivations(self):
        assert "apply_registry_deactivations(conn)" in self._main_src(), (
            "main() must call apply_registry_deactivations — otherwise nothing "
            "enforces DUPLICATE_DATASETS/DATED_DATASETS in production."
        )

    def test_deactivations_are_not_gated_on_populate(self):
        """The exact regression: reachable only via --populate.

        --populate needs a datasets.json absent from prod, so any gating on it
        makes the call dead code there.
        """
        src = self._main_src()
        after_populate_branch = src.split("if args.populate:")[-1]
        call_line = [
            ln for ln in after_populate_branch.splitlines()
            if "apply_registry_deactivations(conn)" in ln
        ]
        assert call_line, "expected the call after the --populate branch"
        # must sit at the function's top level (8 spaces), not nested inside it
        indent = len(call_line[0]) - len(call_line[0].lstrip())
        assert indent == 8, (
            f"apply_registry_deactivations is indented {indent} spaces — it "
            "looks nested inside a conditional. It must run unconditionally."
        )

    def test_deactivations_apply_both_lists(self):
        import inspect
        src = inspect.getsource(seed.apply_registry_deactivations)
        for name in ("DUPLICATE_DATASETS", "DATED_DATASETS"):
            assert name in src, f"{name} is no longer applied"
        assert src.count("is_active = FALSE") == 2

    def test_deactivations_are_not_also_run_from_populate(self):
        """Kept out of register_untracked_tables so they run once, everywhere."""
        import inspect
        src = inspect.getsource(seed.register_untracked_tables)
        assert "DUPLICATE_DATASETS" not in src and "DATED_DATASETS" not in src, (
            "the deactivations moved to apply_registry_deactivations; leaving a "
            "copy here re-creates the populate-only path that caused the bug."
        )

    def test_risky_maintenance_stays_off_the_default_path(self):
        """Measured drift: do NOT let these run unconditionally.

        Against prod on 2026-07-28, applying NORMALIZER_DATASET_IDS would flip
        needs_normalization on 27 datasets and UNTRACKED_TABLES would register
        4 new ones — real ingest-behaviour changes. They belong on --populate
        until that drift is reconciled deliberately.
        """
        src = self._main_src()
        assert "register_untracked_tables" not in src, (
            "register_untracked_tables must not be called from main(): it "
            "rewrites needs_normalization for 27 prod datasets and registers "
            "4 new ones. Reconcile the drift before promoting it."
        )


class TestNeedsNormalizationHasOneOwner:
    """needs_normalization must be computed in exactly one place.

    It was written by two code paths using different rules:

        populate_from_datasets_json : table_name in NORMALIZED_DATASETS
        register_untracked_tables   : table_name not in DIRECT_SOCRATA_OVERRIDE

    The second has nothing to do with whether a dataset has an entity to
    normalize. Measured against prod on 2026-07-28, it would have flipped 28
    rows — every one of them away from the first rule, which prod follows on 77
    of 80 rows. It never did damage only because the function was unreachable in
    production.

    The column gates the post-ingest unmapped-entity scan. It does NOT select
    the ingest path — routing keys on normalizer_dataset_id.
    """

    def test_normalizer_id_loop_does_not_write_needs_normalization(self):
        import inspect
        src = inspect.getsource(seed.register_untracked_tables)
        loop = src.split("NORMALIZER_DATASET_IDS.items()")[-1]
        assert "needs_normalization" not in loop, (
            "The NORMALIZER_DATASET_IDS loop must set normalizer_dataset_id "
            "only. Writing needs_normalization here re-creates a second, "
            "conflicting owner for that column — it would flip 28 prod rows."
        )

    def test_direct_socrata_override_is_gone(self):
        """Checks the definition, not the word — the comment explains why."""
        import inspect, re
        src = inspect.getsource(seed.register_untracked_tables)
        code = "\n".join(
            ln for ln in src.splitlines() if not ln.lstrip().startswith("#")
        )
        assert not re.search(r"DIRECT_SOCRATA_OVERRIDE\s*=", code), (
            "DIRECT_SOCRATA_OVERRIDE never bypassed the normalizer — bypass "
            "means having no normalizer_dataset_id, and the loop set one "
            "anyway. Leave a dataset out of NORMALIZER_DATASET_IDS instead."
        )
        assert "DIRECT_SOCRATA_OVERRIDE" not in code, (
            "DIRECT_SOCRATA_OVERRIDE is referenced in code again"
        )

    def test_populate_remains_the_single_owner(self):
        import inspect
        src = inspect.getsource(seed.populate_from_datasets_json)
        assert "needs_norm = table_name in NORMALIZED_DATASETS" in src, (
            "populate_from_datasets_json owns needs_normalization via "
            "NORMALIZED_DATASETS membership; that rule must stay put."
        )


class TestOutputPathTableMapping:
    """OUTPUT_PATH_TO_TABLE must agree with how the normalizer picks a table.

    The normalizer derives the target from the S3 filename —
    PurePosixPath(s3_url).stem, lowercased by /import-csv — so
    "LL18PayandDemo.csv" lands in `ll18payanddemo`. The seed claimed
    `ll18payanddemoreport`, a different and orphaned table.

    That disagreement was the blind spot in the duplicate guards above: they
    read NORMALIZER_DATASET_IDS from this file, and `ll18payanddemoreport` got
    its normalizer id from datasets.json instead — so two active registry rows
    shared dataset 88 and nothing caught it. This checks the seed's own two
    sources of truth against each other, which is the part a static test CAN
    see.
    """

    def test_output_path_stem_matches_declared_table(self):
        from pathlib import PurePosixPath
        mismatches = {}
        for csv_name, table in seed.OUTPUT_PATH_TO_TABLE.items():
            stem = PurePosixPath(csv_name).stem.lower()
            if stem != table and table not in seed.DUPLICATE_DATASETS:
                mismatches[csv_name] = (stem, table)
        assert not mismatches, (
            "OUTPUT_PATH_TO_TABLE disagrees with the table the normalizer will "
            f"actually write to (S3 stem, lowercased): {mismatches}. The "
            "normalizer wins — /import-csv is handed the stem — so a mismatch "
            "means the seed describes a table that never receives the data."
        )

    def test_ll18_report_orphan_stays_deactivated(self):
        assert 'll18payanddemoreport' in seed.DUPLICATE_DATASETS, (
            "ll18payanddemoreport shares normalizer dataset 88 with "
            "ll18payanddemo, which is the table the normalizer writes to and "
            "the app reads. Leaving it active makes the scheduler re-trigger "
            "dataset 88 every sweep for a table nothing reads."
        )

    def test_no_two_outputs_target_one_table(self):
        seen = {}
        for csv_name, table in seed.OUTPUT_PATH_TO_TABLE.items():
            seen.setdefault(table, []).append(csv_name)
        clashes = {t: c for t, c in seen.items() if len(c) > 1}
        assert not clashes, f"Multiple outputs target one table: {clashes}"
