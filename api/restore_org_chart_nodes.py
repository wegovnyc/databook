"""Phase 1: restore the org chart's lost scaffolding, and make "on the chart" a flag.

Run (dry run is the default; nothing is written without --apply):

    docker compose exec -T api python restore_org_chart_nodes.py
    docker compose exec -T api python restore_org_chart_nodes.py --apply

WHAT WAS BROKEN
===============
The org chart has two node kinds that are NOT organizations, and the code still
knows about both -- `/get/orgs/chart` includes types `Classification` and
`Official`, `/get/orgs/all` excludes them. But **zero rows of either type
exist**: the records were lost at some point, leaving 63 orgs whose `child_of`
pointed at nothing.

This is a RESTORATION, not an invention, because both stores remembered them:

  * every missing parent's original `airtable_id` is still sitting in its
    children's `child_of`, so recreating the row with that id makes all its
    children resolve with **no edit to any child**;
  * the normalizer core still holds five of them with their original id AND
    type -- `District Attorneys` 170020021 `Classification`, `Chief of Staff`
    170100017 `Official`, plus `Chief Climate Officer` 170100240, `Chief
    Technology Officer` 170100034 and `Deputy Mayor for Economic and Workforce
    Development` 170100230, all `Official`.

⭐ Those five are exactly the "core entities whose numeric id resolves to
nothing" that have been reported as an open item since the OTI adoption. They
were never a separate problem — they are these same lost nodes, and restoring
them here closes that item too, including the pre-step Phase 2 was blocked on.

"NOT ON CHART" BECOMES A FLAG (owner decision)
==============================================
32 orgs were parented to a bucket called `Additional Mayoral Agencies (Not on
Chart)`. That encodes "absent from the chart" as a *position in* the chart. NYC
publishes the right shape: an `in_org_chart` boolean.

⚠ Measured corroboration before doing it: of those 32, **24 are linked to an
OTI record, and OTI reports `in_org_chart = false` for all 24 — 24 of 24 — while
giving none of them a `reports_to`.** The City's own registry says these are
off-chart with no parent, which is precisely what we are moving to. The other 8
are not in OTI and keep our own categorisation, which is what the bucket meant.

⚠ THE DESTRUCTIVE STEP
Clearing `child_of` on those 32 rows cannot be undone by deleting a restored
row. This script snapshots `(id, child_of, child_of_name)` for every row it
touches into `wegov_orgs_chart_restore_backup` BEFORE writing, in the same
transaction.

TRAPS
-----
- Restored nodes must NOT be typed into `DIRECTORY_TYPES` — `Classification`
  and `Official` belong in the chart and must stay out of
  `/get/orgs/directory` and `/get/orgs/all`. Both already exclude them; the
  verify block asserts the counts did not move.
- They must not become match targets either. `District Attorneys` as a
  matchable name would swallow the five real DA offices. Phase 2's endpoint
  excludes these types; until then the core is frozen, so nothing changes.
"""

import argparse
import asyncio
import datetime
import json
import os
import sys

import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

try:
    import dbcreds
except ImportError:
    from modules import dbcreds


# The lost chart nodes. `airtable_id` is the ORIGINAL, recovered from the
# `child_of` of the orgs that still point at it — which is what makes this a
# restoration rather than a re-parenting exercise. `org_id` is the original id
# where the normalizer core still remembers it, else None to mint a new one.
#
# type: 'Classification' = a grouping node that is not an organization
#       'Official'       = a person-role node (a post, not a body)
CHART_NODES = [
    # -- still referenced as a parent by live orgs -------------------------
    {"name": "Elected County Officials",
     "airtable_id": "reckRTIpmsRKae8IU", "org_id": None, "type": "Classification",
     "parent": "The People of the City of New York"},
    {"name": "Chief of Staff",
     "airtable_id": "recIXPDD84xmPdV2s", "org_id": 170100017, "type": "Official",
     "parent": "Mayor's Office"},
    {"name": "Deputy Mayor for Strategic Policy Initiatives",
     "airtable_id": "recdlyYOduxWVUWKh", "org_id": None, "type": "Official",
     "parent": "First Deputy Mayor"},
    {"name": "District Attorneys",
     "airtable_id": "recTJbjZQCIIagGse", "org_id": 170020021, "type": "Classification",
     "parent": "Elected County Officials"},
    # ⚠ id 170000000 is NOT arbitrary — it is THE ROOT OF THE ORG CHART.
    # `ChartUpdateJson.php:59` hardcodes `$org['id'] == '170000000'` to find the
    # root, and the March 2026 snapshot of `public/data/orgChart.json` opens
    # with `<a>The People of the City of New York</a>` at `className: node_def`
    # (the greyed, unlinked Classification treatment). Restore it under any
    # other id and the generator finds no root and emits a broken chart.
    {"name": "The People of the City of New York",
     "airtable_id": "rechr1BnnpiKGguXH", "org_id": 170000000, "type": "Classification",
     "parent": None},
    {"name": "Chief Housing Officer",
     "airtable_id": "recewLJXBWPvcKx4S", "org_id": None, "type": "Official",
     "parent": "First Deputy Mayor"},
    {"name": "Director of Communications",
     "airtable_id": "recIQ8u44qEuQy6dZ", "org_id": None, "type": "Official",
     "parent": "Mayor's Office"},
    # -- referenced only by the normalizer core, which kept their ids ------
    # No live org parents to these, but curated match rows point at them
    # (ds 69 OER/ORR -> Chief Climate Officer; ds 64/285 MOCTO -> Chief
    # Technology Officer; ds 308 -> Deputy Mayor for Economic and Workforce
    # Development), so the ids must exist for those to resolve.
    {"name": "Chief Climate Officer",
     "airtable_id": None, "org_id": 170100240, "type": "Official",
     "parent": "Deputy Mayor for Operations"},
    {"name": "Chief Technology Officer",
     "airtable_id": None, "org_id": 170100034, "type": "Official",
     "parent": "First Deputy Mayor"},
    {"name": "Deputy Mayor for Economic and Workforce Development",
     "airtable_id": None, "org_id": 170100230, "type": "Official",
     "parent": "First Deputy Mayor"},
]

# The bucket that becomes a flag. Not restored as a row.
NOT_ON_CHART_AIRTABLE_ID = "recTZLn26klvFYOxj"

# Parents that are now real imported orgs — their children just re-wire.
REWIRE = {
    "recwvZRSkXdZ0hHzd": 170100307,   # First Deputy Mayor
    "recKWc8i7FSHUhikz": 170100303,   # Deputy Mayor for Operations
}

ID_BLOCK_LO, ID_BLOCK_HI = 170100000, 170199999

SCHEMA = """
-- Nullable on purpose: NULL means "not stated", which is different from false.
ALTER TABLE wegov_orgs ADD COLUMN IF NOT EXISTS in_org_chart BOOLEAN;
ALTER TABLE wegov_orgs ADD COLUMN IF NOT EXISTS is_chart_node BOOLEAN;

-- Snapshot of every row this script rewrites, so the destructive step is
-- reversible. Written before any UPDATE, inside the same transaction.
CREATE TABLE IF NOT EXISTS wegov_orgs_chart_restore_backup (
    id            INTEGER,
    child_of      TEXT,
    child_of_name TEXT,
    parent_org_id INTEGER,
    in_org_chart  BOOLEAN,
    reason        TEXT,
    backed_up_at  TIMESTAMPTZ DEFAULT NOW()
);
-- ⚠ child_of / child_of_name are kept as COLUMNS here because the 35 rows this
-- table already holds were captured while they existed (Phase 1). Phase 6
-- dropped them from wegov_orgs, so new snapshots leave them NULL and record
-- parent_org_id instead. Do not drop the old columns: that would discard the
-- pre-Phase-1 provenance this table exists to preserve.
"""


def stripped(v: str) -> str:
    """`["recABC"]` -> `recABC` — the same unwrapping main.py:345 does."""
    return (v or "").strip().strip("[]").strip('"').strip()


async def snapshot(conn, ids, reason, plan, apply):
    if not ids:
        return
    plan.append(f"    snapshot {len(ids)} rows ({reason}) -> "
                f"wegov_orgs_chart_restore_backup")
    if apply:
        await conn.execute(
            "INSERT INTO wegov_orgs_chart_restore_backup "
            "  (id, parent_org_id, in_org_chart, reason) "
            "SELECT id, parent_org_id, in_org_chart, $2 "
            "FROM wegov_orgs WHERE id = ANY($1::int[])", list(ids), reason)


async def keep_our_flag_ours(conn, plan, apply):
    """`wegov_orgs.in_org_chart` records OUR editorial opinion, and only ours.

    ⚠ An earlier pass copied OTI's `in_org_chart` into this column, which
    CONFLATED two different opinions in one field and made the two chart views
    impossible to build. Measured after that pass: 169 rows false — 32 ours,
    161 OTI's, overlapping on 24.

    The separation:
      * `wegov_orgs.in_org_chart`      OURS. false for the 32 that used to hang
                                       off the `Additional Mayoral Agencies
                                       (Not on Chart)` bucket, true for the
                                       restored scaffolding nodes, NULL
                                       everywhere else (no opinion).
      * `nyc_org_enrichment.in_org_chart`  OTI's. Already there, untouched,
                                       and read directly by the OTI chart view.

    Keeping OTI's opinion out of this column is what lets the default chart show
    what we have always shown while the OTI view stays available alongside it.
    """
    ours_false = [r["id"] for r in await conn.fetch(
        "SELECT DISTINCT id FROM wegov_orgs_chart_restore_backup "
        "WHERE reason = 'not-on-chart bucket'")]
    node_names = [s["name"] for s in CHART_NODES]

    reset = await conn.fetchval(
        "SELECT count(*) FROM wegov_orgs WHERE in_org_chart IS NOT NULL "
        "  AND NOT (id = ANY($1::int[])) AND NOT (name = ANY($2::text[]))",
        ours_false, node_names)
    plan.append(f"flag: ours = {len(ours_false)} off-chart + "
                f"{len(node_names)} chart nodes on-chart; clearing {reset} rows "
                f"that only carried OTI's opinion (it stays in "
                f"nyc_org_enrichment)")
    if apply:
        await conn.execute(
            "UPDATE wegov_orgs SET in_org_chart = NULL "
            "WHERE in_org_chart IS NOT NULL "
            "  AND NOT (id = ANY($1::int[])) AND NOT (name = ANY($2::text[]))",
            ours_false, node_names)
        if ours_false:
            await conn.execute(
                "UPDATE wegov_orgs SET in_org_chart = FALSE WHERE id = ANY($1::int[])",
                ours_false)
        await conn.execute(
            "UPDATE wegov_orgs SET in_org_chart = TRUE WHERE name = ANY($1::text[])",
            node_names)


async def bucket_to_flag(conn, plan, apply):
    """`Additional Mayoral Agencies (Not on Chart)` stops being a parent."""
    # ⚠ Reads the PROVENANCE table, not wegov_orgs. Phase 6 dropped child_of;
    # `wegov_orgs_airtable_provenance` is where the Airtable parent strings this
    # script was written to interpret now live. Without this the query raises
    # UndefinedColumnError and the script becomes one that cannot run.
    kids = await conn.fetch(
        r"""SELECT o.id, o.name FROM wegov_orgs o
            JOIN wegov_orgs_airtable_provenance v ON v.id = o.id
            WHERE o.retired_at IS NULL
              AND regexp_replace(v.child_of,'[\[\]"]','','g') = $1""",
        NOT_ON_CHART_AIRTABLE_ID)
    plan.append(f"flag: {len(kids)} orgs parented to the 'Not on Chart' bucket "
                f"-> in_org_chart = false, parent cleared")
    if not kids:
        return
    await snapshot(conn, [r["id"] for r in kids], "not-on-chart bucket", plan, apply)
    if apply:
        await conn.execute(
            "UPDATE wegov_orgs SET in_org_chart = FALSE, parent_org_id = NULL "
            "WHERE id = ANY($1::int[])",
            [r["id"] for r in kids])


async def rewire(conn, plan, apply):
    """Children whose parent is now a real imported org."""
    total = 0
    for aid, org_id in REWIRE.items():
        target = await conn.fetchrow(
            "SELECT id, name, airtable_id FROM wegov_orgs "
            "WHERE id = $1 AND retired_at IS NULL", org_id)
        if not target:
            plan.append(f"    rewire: SKIP — org {org_id} not found")
            continue
        kids = await conn.fetch(
            r"""SELECT o.id FROM wegov_orgs o
                JOIN wegov_orgs_airtable_provenance v ON v.id = o.id
                WHERE o.retired_at IS NULL
                  AND regexp_replace(v.child_of,'[\[\]"]','','g') = $1""", aid)
        if not kids:
            continue
        total += len(kids)
        plan.append(f"    rewire {len(kids)} children onto {target['name']!r} "
                    f"({org_id})")
        await snapshot(conn, [r["id"] for r in kids], f"rewire->{org_id}",
                       plan, apply)
        if apply:
            # ⚠ parent_org_id is authoritative since Phase 3; child_of is
            # written in step for one release as provenance/rollback. Updating
            # only one of the two is exactly the drift adopt_nyc_orgs verifies.
            await conn.execute(
                "UPDATE wegov_orgs SET parent_org_id = $2 "
                "WHERE id = ANY($1::int[])",
                [r["id"] for r in kids], int(target["id"]))
    plan.append(f"rewire: {total} children moved onto real orgs")


async def restore_nodes(conn, plan, apply):
    """Recreate the lost Classification / Official nodes."""
    next_id = (await conn.fetchval(
        "SELECT max(id) FROM wegov_orgs WHERE id BETWEEN $1 AND $2",
        ID_BLOCK_LO, ID_BLOCK_HI) or ID_BLOCK_LO) + 1

    created = kept = fixed = 0
    for spec in CHART_NODES:
        existing = await conn.fetchrow(
            "SELECT id FROM wegov_orgs WHERE name = $1", spec["name"])
        if existing:
            # Self-heal a node restored under the wrong id. This matters for
            # the root: an earlier run minted a fresh id for `The People of the
            # City of New York` before we knew the chart generator hardcodes
            # 170000000, which would have left the chart rootless.
            # ⚠ Since Phase 3 children reference a parent by ID, so changing an
            # id DOES move its children — the FK follows it. This counts them.
            if spec["org_id"] and existing["id"] != spec["org_id"]:
                clash = await conn.fetchval(
                    "SELECT 1 FROM wegov_orgs WHERE id = $1", spec["org_id"])
                refs = await conn.fetchval(
                    "SELECT count(*) FROM wegov_orgs WHERE parent_org_id = $1",
                    int(existing["id"]))
                if clash:
                    plan.append(f"    ⚠ {spec['name']!r} wants id "
                                f"{spec['org_id']} but it is taken — left at "
                                f"{existing['id']}")
                elif refs:
                    plan.append(f"    ⚠ {spec['name']!r} id {existing['id']} is "
                                f"referenced {refs}x — not renumbering")
                else:
                    fixed += 1
                    plan.append(f"    renumber {spec['name']!r} "
                                f"{existing['id']} -> {spec['org_id']}")
                    if apply:
                        await conn.execute(
                            "UPDATE wegov_orgs SET id = $2 WHERE id = $1",
                            existing["id"], spec["org_id"])
                continue
            kept += 1
            plan.append(f"    exists  {spec['name']!r} ({existing['id']})")
            continue
        oid = spec["org_id"]
        if oid is None:
            oid = next_id
            next_id += 1
        # A node nothing points at still needs an airtable_id, because
        # `child_of` can only reference an org that way (main.py:345).
        aid = spec["airtable_id"] or f"recNODE{oid}"
        created += 1
        plan.append(f"    restore {spec['type']:<15} {spec['name'][:44]:<44} "
                    f"id={oid} airtable_id={aid}")
        if apply:
            await conn.execute(
                'INSERT INTO wegov_orgs (id, name, "type", airtable_id, '
                ' is_chart_node, in_org_chart, internal_notes, last_updated) '
                'VALUES ($1,$2,$3,$4,TRUE,TRUE,$5,$6)',
                oid, spec["name"], spec["type"], aid,
                "Org-chart node restored 2026-07-30 (Phase 1). Not an "
                "organization: 'Classification' is a grouping node, 'Official' "
                "a person-role node. Original airtable_id recovered from the "
                "child_of of orgs still pointing at it; original id from the "
                "normalizer core where it remembered one.",
                datetime.datetime.now(datetime.timezone.utc).isoformat())
    plan.append(f"restore: {created} created, {kept} already present, {fixed} renumbered")


async def wire_node_parents(conn, plan, apply):
    """Give the restored nodes their OWN parent.

    ⚠ Restoring a node is not enough to put it back on the chart.
    `ChartUpdateJson.php` skips any org without a parent (`if (!$parent_id)
    continue;`), so a node with children but no parent takes its whole branch
    out of the tree. Measured: after the first pass the regenerated chart had
    **121 nodes against March's 256**, having lost `Elected County Officials`
    and all 72 of its descendants.

    The hierarchy comes from `public/data/orgChart.json` as generated on
    2026-03-02 — a record of the tree while these nodes still existed, which
    makes this recovered rather than invented, exactly like the ids.

    Only fills an EMPTY parent. Where OTI has since given a real org a parent
    (`First Deputy Mayor` and `Deputy Mayor for Operations` now sit under
    `Mayor's Office`), OTI wins — that is the round-2 policy and this must not
    quietly revert it.
    """
    wired = skipped = unresolved = 0
    for spec in CHART_NODES:
        if not spec.get("parent"):
            continue
        row = await conn.fetchrow(
            "SELECT id, child_of FROM wegov_orgs WHERE name = $1", spec["name"])
        if not row:
            continue
        if (row["child_of"] or "").strip() not in ("", "[]"):
            skipped += 1
            continue
        parent = await conn.fetchrow(
            "SELECT id, name, airtable_id FROM wegov_orgs "
            "WHERE name = $1 AND retired_at IS NULL "
            "  AND COALESCE(airtable_id,'') <> '' ORDER BY id LIMIT 1",
            spec["parent"])
        if not parent:
            unresolved += 1
            plan.append(f"    ⚠ {spec['name']!r} wants parent "
                        f"{spec['parent']!r} — not found")
            continue
        wired += 1
        plan.append(f"    parent  {spec['name'][:44]:<44} -> {parent['name']}")
        if apply:
            await conn.execute(
                "UPDATE wegov_orgs SET parent_org_id = $2 WHERE id = $1",
                row["id"], int(parent["id"]))
    plan.append(f"node parents: {wired} wired, {skipped} already had one, "
                f"{unresolved} unresolved")


async def verify(conn):
    print("\n=== verification ===")
    # Since Phase 3 a MISSING parent is impossible by FK. What remains
    # measurable is a parent that exists but is RETIRED, which still drops the
    # org's whole branch off the chart.
    dangling = await conn.fetchval(
        "SELECT count(*) FROM wegov_orgs o JOIN wegov_orgs p "
        "  ON p.id = o.parent_org_id "
        "WHERE o.retired_at IS NULL AND p.retired_at IS NOT NULL")
    print(f"live orgs whose parent is RETIRED: {dangling}  (target 0)")

    for label, sql in [
        ("directory", "SELECT count(*) FROM wegov_orgs WHERE \"type\" IN "
                      "('City Agency','City Fund','Community Board',"
                      "'Economic Development Organization','Elected Office',"
                      "'State Agency','Advisory or Regulatory Organization',"
                      "'Division','Mayoral Agency','Mayoral Office','Pension Fund',"
                      "'Public Benefit or Development Organization',"
                      "'State Government Agency') AND retired_at IS NULL"),
        ("all", "SELECT count(*) FROM wegov_orgs WHERE \"type\" NOT IN "
                "('Classification','Official','Public Figure') AND retired_at IS NULL"),
        ("chart nodes", "SELECT count(*) FROM wegov_orgs WHERE \"type\" IN "
                        "('Classification','Official') AND retired_at IS NULL"),
        ("off-chart flagged", "SELECT count(*) FROM wegov_orgs "
                              "WHERE in_org_chart = FALSE AND retired_at IS NULL"),
    ]:
        print(f"{label:<20} {await conn.fetchval(sql)}")

    print(f"backup rows: "
          f"{await conn.fetchval('SELECT count(*) FROM wegov_orgs_chart_restore_backup')}")


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the changes (default is a dry run)")
    args = ap.parse_args()

    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=dbcreds.password(),
        database=os.environ.get("POSTGRES_DB", "databook"),
    )
    try:
        print(f"[chart] mode: "
              f"{'APPLY' if args.apply else 'DRY RUN (rolled back; pass --apply)'}\n")
        plan = []
        tx = conn.transaction()
        await tx.start()
        try:
            for stmt in SCHEMA.strip().split(";"):
                if stmt.strip():
                    await conn.execute(stmt)
            plan.append("schema: in_org_chart / is_chart_node + backup table ready")

            # Order matters: restore the nodes first so the re-wire and the
            # dangling check have targets, and snapshot before any UPDATE.
            await restore_nodes(conn, plan, True)
            await wire_node_parents(conn, plan, True)
            await rewire(conn, plan, True)
            await bucket_to_flag(conn, plan, True)
            await keep_our_flag_ours(conn, plan, True)

            for line in plan:
                print(f"[chart] {line}")
            await verify(conn)

            if args.apply:
                await tx.commit()
                print("\n[chart] COMMITTED")
            else:
                await tx.rollback()
                print("\n[chart] ROLLED BACK — nothing written. Re-run with --apply.")
        except Exception:
            await tx.rollback()
            print("\n[chart] ROLLED BACK on error — nothing written.")
            raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
