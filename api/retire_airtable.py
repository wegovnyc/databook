"""Retire Airtable as an identity scheme — Phase 6.

    python retire_airtable.py            # dry run
    python retire_airtable.py --apply    # snapshot, then drop child_of/child_of_name

WHAT PHASE 6 ACTUALLY IS
========================
Airtable left the READ path long ago; nothing loads from it and the directory is
near-static (almost everything last touched 2021-22, 26 records in 2024-06,
nothing since). What survived was Airtable as an **identity scheme**:

  * `child_of` stored an Airtable `rec...` id as TEXT and was how one org
    referenced another — replaced by the `parent_org_id` FK in Phase 3;
  * so a NEW org had to be given a synthetic `airtable_id` (`recOTI…`,
    `recEXTRA…`, `recNODE…`, `recEDIT…`) purely to be referenceable at all.
    Measured 2026-07-31: **140 of 1,250** rows carry a synthetic id.

This drops `child_of` / `child_of_name` and stops minting synthetic ids. After
it, an org's identity is its `id` — the primary key declared in Phase 3 — and
`airtable_id` is nothing but historical provenance for the 1,110 rows that came
from Airtable.

⚠ WHY THE COLUMNS ARE SNAPSHOTTED, NOT JUST DROPPED
===================================================
`child_of` was the rollback path for Phase 3: `orgfilter.parent_join` falls back
to the legacy string join wherever `parent_org_id` is absent. Dropping the column
removes that path, and Phase 3 shipped HOURS earlier, not a release earlier.

So the provenance is preserved properly instead of being kept as a decaying
duplicate that writers must remember to update: every row's
`(id, name, airtable_id, child_of, child_of_name, parent_org_id)` goes into
`wegov_orgs_airtable_provenance` first. That table is the record of what Airtable
said, and it is what a reconstruction would read. Following the
`wegov_orgs_chart_restore_backup` precedent from Phase 1.

⚠ VERIFY BEFORE DROPPING — the script refuses unless:
  * `parent_org_id` is populated for every row that has a `child_of`, and
  * the two agree on every row (no drift), and
  * the FK constraint and the primary key both exist.
A `child_of` that still knows something `parent_org_id` does not would be
destroyed by this, so it is a hard gate rather than a warning.
"""

import argparse
import asyncio
import os
import sys

import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

try:
    import dbcreds
except ImportError:
    from modules import dbcreds

DROP_COLUMNS = ("child_of", "child_of_name")

SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS wegov_orgs_airtable_provenance (
    id            INTEGER PRIMARY KEY,
    name          TEXT,
    airtable_id   TEXT,
    child_of      TEXT,
    child_of_name TEXT,
    parent_org_id INTEGER,
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


async def _connect():
    return await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=dbcreds.password(),
        database=os.environ.get("POSTGRES_DB", "databook"))


async def _col_exists(conn, name) -> bool:
    return bool(await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'wegov_orgs' AND column_name = $1", name))


async def main_async(apply: bool) -> int:
    conn = await _connect()
    try:
        print(f"[phase6] mode: {'APPLY' if apply else 'DRY RUN (pass --apply)'}")

        have_child_of = await _col_exists(conn, "child_of")
        if not have_child_of:
            print("[phase6] child_of is already gone — nothing to do")
            return 0

        # ── the gates ────────────────────────────────────────────────────────
        pk = await conn.fetchval(
            "SELECT 1 FROM pg_constraint WHERE conrelid='wegov_orgs'::regclass "
            "AND contype='p'")
        fk = await conn.fetchval(
            "SELECT 1 FROM pg_constraint WHERE conname='wegov_orgs_parent_fk'")
        print(f"[phase6] primary key: {bool(pk)}   parent FK: {bool(fk)}")
        if not (pk and fk):
            print("[phase6] ABORT: run add_parent_org_id.py --apply first — "
                  "dropping child_of without the FK in place would leave orgs "
                  "with no parent mechanism at all")
            return 1

        total = await conn.fetchval("SELECT count(*) FROM wegov_orgs")
        with_child = await conn.fetchval(
            "SELECT count(*) FROM wegov_orgs "
            "WHERE COALESCE(btrim(child_of),'') NOT IN ('','[]')")
        with_fk = await conn.fetchval(
            "SELECT count(*) FROM wegov_orgs WHERE parent_org_id IS NOT NULL")
        drift = await conn.fetch(r"""
            SELECT o.id, o.name, o.child_of, o.parent_org_id, p.id AS legacy_id
            FROM wegov_orgs o
            LEFT JOIN wegov_orgs p
                   ON p.airtable_id = regexp_replace(o.child_of,'[\[\]"]','','g')
            WHERE COALESCE(btrim(o.child_of),'') NOT IN ('','[]')
              AND o.parent_org_id IS DISTINCT FROM p.id
            ORDER BY o.name LIMIT 20""")
        print(f"[phase6] {total} rows: {with_child} with child_of, {with_fk} with "
              f"parent_org_id, {len(drift)} disagreeing")
        if drift:
            print("[phase6] ABORT: child_of still knows something parent_org_id "
                  "does not — dropping it would destroy that:")
            for d in drift:
                print(f"[phase6]     {d['id']} {d['name']!r} child_of->{d['legacy_id']} "
                      f"fk->{d['parent_org_id']}")
            return 1

        synth = await conn.fetchval(
            "SELECT count(*) FROM wegov_orgs WHERE airtable_id LIKE 'recOTI%' "
            "OR airtable_id LIKE 'recEXTRA%' OR airtable_id LIKE 'recNODE%' "
            "OR airtable_id LIKE 'recEDIT%'")
        real = await conn.fetchval(
            "SELECT count(*) FROM wegov_orgs "
            "WHERE COALESCE(btrim(airtable_id),'') <> ''") - synth
        print(f"[phase6] airtable_id: {real} genuine, {synth} synthetic "
              f"(kept as provenance; no new ones are minted after this)")

        if not apply:
            print(f"[phase6] would snapshot {total} rows into "
                  f"wegov_orgs_airtable_provenance, then DROP "
                  f"{', '.join(DROP_COLUMNS)}")
            return 0

        async with conn.transaction():
            await conn.execute(SNAPSHOT_DDL)
            # Insert-only: a re-run must not overwrite the original capture.
            n = await conn.execute("""
                INSERT INTO wegov_orgs_airtable_provenance
                    (id, name, airtable_id, child_of, child_of_name, parent_org_id)
                SELECT id, name, airtable_id, child_of, child_of_name, parent_org_id
                FROM wegov_orgs
                ON CONFLICT (id) DO NOTHING""")
            print(f"[phase6] snapshot: {n}")
            kept = await conn.fetchval(
                "SELECT count(*) FROM wegov_orgs_airtable_provenance")
            if kept < total:
                raise RuntimeError(
                    f"snapshot holds {kept} of {total} rows — refusing to drop")
            for c in DROP_COLUMNS:
                if await _col_exists(conn, c):
                    await conn.execute(f'ALTER TABLE wegov_orgs DROP COLUMN "{c}"')
                    print(f"[phase6] dropped {c}")

        print("\n=== verification ===")
        for c in DROP_COLUMNS:
            print(f"{c} present: {await _col_exists(conn, c)}  (want False)")
        print(f"provenance rows: "
              f"{await conn.fetchval('SELECT count(*) FROM wegov_orgs_airtable_provenance')}"
              f"  (want {total})")
        print(f"parent_org_id populated: "
              f"{await conn.fetchval('SELECT count(*) FROM wegov_orgs WHERE parent_org_id IS NOT NULL')}"
              f"  (want {with_fk})")
        # The invariant the FK does NOT give us: existence is guaranteed,
        # liveness is not. A live org may still point at a retired parent.
        stale = await conn.fetchval(
            "SELECT count(*) FROM wegov_orgs o JOIN wegov_orgs p ON p.id = o.parent_org_id "
            "WHERE o.retired_at IS NULL AND p.retired_at IS NOT NULL")
        print(f"live orgs whose parent is RETIRED: {stale}  (want 0)")
        return 0
    finally:
        await conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the changes (default is a dry run)")
    args = ap.parse_args()
    sys.exit(asyncio.run(main_async(args.apply)))


if __name__ == "__main__":
    main()
