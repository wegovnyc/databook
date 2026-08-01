"""Give `wegov_orgs` a real parent FK, and retire the Airtable string join.

Phase 3 of docs/ORG-DIRECTORY-OF-RECORD-PLAN.md.

    python add_parent_org_id.py                     # dry run of the additive step
    python add_parent_org_id.py --apply             # add the column + backfill
    python add_parent_org_id.py --drop-dead-columns # SEPARATE, run after deploy

WHAT AND WHY
============
`child_of` holds an Airtable `rec...` id as TEXT -- sometimes JSON-wrapped
(`["recABC"]`) -- joined to `airtable_id` by string equality after stripping
brackets. Consequences, all measured:

  * 63 orgs had a parent that resolved to NOTHING (repaired by hand in Phase 1;
    nothing stopped them coming back);
  * importing an org required minting a synthetic `recOTI.../recEXTRA...`
    `airtable_id` (137 exist) purely so children could reference it;
  * the join silently truncates OTI's 5 multi-parent records to their first
    parent, because equality needs exactly one id.

`parent_org_id INTEGER REFERENCES wegov_orgs(id)` makes a dangling parent
structurally impossible -- the database refuses it -- instead of something a
weekly script asserts after the fact.

⚠ TWO STEPS, ON PURPOSE, AND THE ORDER IS LOAD-BEARING
======================================================
`--apply` is purely ADDITIVE: it adds a nullable column, backfills it, and adds
the FK constraint. Nothing breaks if the running code has not been deployed yet.

`--drop-dead-columns` is DESTRUCTIVE and must run only AFTER the new code is
deployed, because `mcp_server.py` used to select `parent_name` straight off the
table. Dropping it under the old code would 500 both MCP org tools.

The three columns it drops -- `parent_id`, `parent_name`, `parent_type` -- are
**0 of 1,250 populated** (measured 2026-07-31) AND are shadowed by aliases of
the same name computed in `main.py`'s profile query. So `org.parent_id` is NULL
when read from the table and non-NULL when read from the API, depending which
path you came through. That ambiguity is not a cosmetic problem: it is exactly
how the MCP bug hid -- `mcp_server.py` queried the table, got the dead column,
and reported every organization as having no parent, for as long as the tools
have existed.

⚠ `child_of` / `child_of_name` are RETAINED by this script, deliberately. They
stay for one release as provenance and as the rollback path (`orgfilter`'s probe
falls back to the legacy join whenever `parent_org_id` is absent). Writers keep
both in step meanwhile -- see `adopt_nyc_orgs.py::wire_parents`.

⚠ A scalar FK inherits today's ONE PARENT ONLY limit. Borough Boards genuinely
reports to all five Borough Presidents, and OTI's multi-parent rows were
already truncated before this change. Recording that here rather than fixing
it: a real fix is a join table, which is a different piece of work.

⚠⚠ `wegov_orgs` HAD NO PRIMARY KEY -- discovered when the FK was first applied
against prod and Postgres refused it: "there is no unique constraint matching
given keys for referenced table". Measured 2026-07-31: **zero** rows in
`pg_constraint` for this table -- no primary key, no unique constraint, no
checks -- and `id` was a NULLABLE integer carrying only a plain, non-unique
btree index. So for the entire life of the directory nothing prevented two orgs
sharing an id, or an org having no id at all. They happen to be clean (1,250
rows, 1,250 non-null, 1,250 distinct), which is luck rather than design: the
table is `source_type='internal'` and was created outside any migration, so no
key was ever declared.

This script therefore declares `PRIMARY KEY (id)` before adding the FK. That is
a prerequisite discovered mid-flight, not scope creep -- an FK is meaningless
without a unique key to reference, and the plan assumed one existed. The PK also
sets `id NOT NULL`, which is the correct shape for a register keyed by id.
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

DEAD_COLUMNS = ("parent_id", "parent_name", "parent_type")

# The legacy resolution, kept in exactly one place here so the backfill and the
# drift check cannot disagree about what `child_of` meant.
LEGACY_JOIN = r"""
    LEFT JOIN wegov_orgs p
           ON p.airtable_id = regexp_replace(o.child_of, '[\[\]"]', '', 'g')
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


async def apply(apply_it: bool) -> int:
    conn = await _connect()
    try:
        print(f"[parent-fk] mode: {'APPLY' if apply_it else 'DRY RUN (pass --apply)'}")

        total = await conn.fetchval("SELECT count(*) FROM wegov_orgs")
        populated = await conn.fetchval(
            "SELECT count(*) FROM wegov_orgs "
            "WHERE COALESCE(btrim(child_of), '') NOT IN ('', '[]')")
        resolvable = await conn.fetchval(f"""
            SELECT count(*) FROM wegov_orgs o {LEGACY_JOIN}
            WHERE COALESCE(btrim(o.child_of), '') NOT IN ('', '[]')
              AND p.id IS NOT NULL""")
        print(f"[parent-fk] {total} org rows, {populated} with a child_of, "
              f"{resolvable} of those resolve to a real org")

        # ⚠ Refuse to proceed if any populated child_of does NOT resolve. The FK
        # would reject those rows anyway; failing here says WHICH, instead of
        # surfacing as an opaque constraint violation mid-transaction.
        if populated != resolvable:
            rows = await conn.fetch(f"""
                SELECT o.id, o.name, o.child_of FROM wegov_orgs o {LEGACY_JOIN}
                WHERE COALESCE(btrim(o.child_of), '') NOT IN ('', '[]')
                  AND p.id IS NULL ORDER BY o.name LIMIT 20""")
            print(f"[parent-fk] ABORT: {populated - resolvable} orgs have a "
                  f"child_of that resolves to nothing. Fix these first "
                  f"(restore_org_chart_nodes.py did this in Phase 1):")
            for r in rows:
                print(f"[parent-fk]     {r['id']} {r['name']!r} -> {r['child_of']!r}")
            return 1

        have = await _col_exists(conn, "parent_org_id")
        print(f"[parent-fk] parent_org_id already present: {have}")

        # ⚠ The FK needs a unique key to reference, and this table has never had
        # one. Verify the data can carry a PK before claiming we will add it --
        # a duplicate or NULL id is a real data problem, not something to force.
        has_pk = bool(await conn.fetchval(
            "SELECT 1 FROM pg_constraint "
            "WHERE conrelid = 'wegov_orgs'::regclass AND contype = 'p'"))
        nulls = await conn.fetchval("SELECT count(*) FROM wegov_orgs WHERE id IS NULL")
        distinct = await conn.fetchval("SELECT count(DISTINCT id) FROM wegov_orgs")
        print(f"[parent-fk] primary key on wegov_orgs.id: {has_pk} "
              f"({total} rows, {distinct} distinct ids, {nulls} NULL)")
        if not has_pk and (nulls or distinct != total):
            dupes = await conn.fetch(
                "SELECT id, count(*) AS n FROM wegov_orgs GROUP BY id "
                "HAVING count(*) > 1 ORDER BY n DESC LIMIT 10")
            print(f"[parent-fk] ABORT: cannot add a primary key — "
                  f"{nulls} NULL ids, {total - distinct} duplicated:")
            for d in dupes:
                print(f"[parent-fk]     id {d['id']} appears {d['n']} times")
            return 1

        if not apply_it:
            if not has_pk:
                print("[parent-fk] would ADD PRIMARY KEY (id) — the table has "
                      "none, so the FK cannot be created without it")
            print(f"[parent-fk] would ADD parent_org_id, backfill {resolvable} "
                  f"rows, add the FK constraint + index")
            for c in DEAD_COLUMNS:
                if await _col_exists(conn, c):
                    n = await conn.fetchval(f'SELECT count("{c}") FROM wegov_orgs')
                    print(f"[parent-fk] dead column {c}: {n} of {total} populated "
                          f"(drop with --drop-dead-columns AFTER deploying)")
            return 0

        # One transaction: a half-applied schema change is the thing to avoid.
        async with conn.transaction():
            if not has_pk:
                # Declares id NOT NULL as a side effect, which is the correct
                # shape for a register keyed by id. Instant at 1,250 rows.
                await conn.execute("ALTER TABLE wegov_orgs ADD PRIMARY KEY (id)")
                print("[parent-fk] PRIMARY KEY (id) added — the table had none")
            await conn.execute(
                "ALTER TABLE wegov_orgs ADD COLUMN IF NOT EXISTS parent_org_id INTEGER")
            updated = await conn.execute(f"""
                UPDATE wegov_orgs o SET parent_org_id = sub.pid
                FROM (SELECT o2.id AS oid, p.id AS pid
                        FROM wegov_orgs o2
                        LEFT JOIN wegov_orgs p
                               ON p.airtable_id = regexp_replace(
                                      o2.child_of, '[\\[\\]"]', '', 'g')
                       WHERE COALESCE(btrim(o2.child_of), '') NOT IN ('', '[]')
                         AND p.id IS NOT NULL) sub
                WHERE o.id = sub.oid
                  AND o.parent_org_id IS DISTINCT FROM sub.pid""")
            print(f"[parent-fk] backfill: {updated}")

            # ⚠ Self-referencing FK. NOT VALID would let existing bad rows
            # through; the pre-flight above already proved there are none, so
            # validate immediately and let a surprise fail the transaction.
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_constraint WHERE conname = 'wegov_orgs_parent_fk'")
            if not exists:
                await conn.execute("""
                    ALTER TABLE wegov_orgs
                      ADD CONSTRAINT wegov_orgs_parent_fk
                      FOREIGN KEY (parent_org_id) REFERENCES wegov_orgs(id)
                      ON DELETE SET NULL""")
                print("[parent-fk] FK constraint added (ON DELETE SET NULL)")
            await conn.execute("CREATE INDEX IF NOT EXISTS wegov_orgs_parent_org_id_idx "
                               "ON wegov_orgs (parent_org_id)")

        wired = await conn.fetchval(
            "SELECT count(*) FROM wegov_orgs WHERE parent_org_id IS NOT NULL")
        print(f"[parent-fk] parent_org_id populated: {wired} (expected {resolvable})")
        if wired != resolvable:
            print("[parent-fk] ⚠ MISMATCH — investigate before deploying")
            return 1
        return 0
    finally:
        await conn.close()


async def drop_dead_columns(apply_it: bool) -> int:
    """Drop parent_id / parent_name / parent_type. Run AFTER deploying.

    They are 0% populated and shadowed by same-named computed aliases, which is
    how the MCP null-parent bug stayed invisible.
    """
    conn = await _connect()
    try:
        print(f"[parent-fk] drop-dead-columns: "
              f"{'APPLY' if apply_it else 'DRY RUN (pass --apply too)'}")
        if not await _col_exists(conn, "parent_org_id"):
            print("[parent-fk] ABORT: run --apply first; parent_org_id is absent")
            return 1

        for c in DEAD_COLUMNS:
            if not await _col_exists(conn, c):
                print(f"[parent-fk] {c}: already gone")
                continue
            n = await conn.fetchval(f'SELECT count("{c}") FROM wegov_orgs')
            # ⚠ Never drop a column that turns out to hold data. The premise of
            # this step is that they are empty; verify per column rather than
            # trusting the measurement taken on another day.
            if n:
                print(f"[parent-fk] REFUSING to drop {c}: {n} rows are populated")
                return 1
            print(f"[parent-fk] {'dropping' if apply_it else 'would drop'} {c} "
                  f"({n} populated)")
            if apply_it:
                await conn.execute(f'ALTER TABLE wegov_orgs DROP COLUMN "{c}"')
        return 0
    finally:
        await conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the changes (default is a dry run)")
    ap.add_argument("--drop-dead-columns", action="store_true",
                    help="drop parent_id/parent_name/parent_type — AFTER deploying")
    args = ap.parse_args()
    if args.drop_dead_columns:
        sys.exit(asyncio.run(drop_dead_columns(args.apply)))
    sys.exit(asyncio.run(apply(args.apply)))


if __name__ == "__main__":
    main()
