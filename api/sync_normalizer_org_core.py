"""Keep dataset 328's org matches aligned with the OTI crosswalk.

    docker compose exec -T api python sync_normalizer_org_core.py
    docker compose exec -T api python sync_normalizer_org_core.py --apply

REDUCED IN PHASE 2 (2026-07-31) — this used to also write core entities
(repointing hex ids, creating entities for imported orgs, following
retirements). All of that became transient the moment the core turned into a
derived artifact: `GET /get/orgs/core` now assembles the matching dictionary
from `wegov_orgs` (see api/modules/orgcore.py) and `POST /core/orgs/refresh`
delete-and-reloads it, so writing entities here would last exactly one
refresh. The one-time repairs the old version performed (10,004 ingested rows,
108 hex ids) are done and stay done in Postgres. What remains is the half the
refresh CANNOT derive: dataset 328's match rows.

WHY DATASET 328 IS DIFFERENT
============================
`nyc-agencies-and-governance-organizations` (ds 328) ingests OTI's registry
itself, and its org matches were originally produced by the loose fuzzy
matcher with no one-to-one constraint — 305 of 307 rows "matched" onto only
262 distinct orgs (35 Mayoral offices all collapsed onto Office of the Mayor).
For 328 the correct mapping is knowable EXACTLY: its `source_text` IS an OTI
name, and `nyc_org_crosswalk` already says which org that record belongs to.
So this is a lookup, not re-matching — and it must re-run whenever the weekly
adoption imports or relinks an org, which is why it sits in
scripts/org-registry-refresh.sh (Phase 4b) right after the adoption.

⚠ Only dataset 328. Every other dataset's org matches are years of human
curation over agency names in someone else's spelling.

⚠ The target core key is the linked org's `name` — the register name that
`/get/orgs/core` is guaranteed to emit. Do not target `display_name` or an
OTI spelling: a match row pointing at a name the feed does not carry is an
orphan after the next refresh.

⚠ SIMILARITY GUARD, kept from the original: a `token-set` crosswalk link is
second-guessed before being written into match rows, because that pass is
order-insensitive and produced the one known false positive (OTI's `Community
Services Board`, a DOHMH body, -> our `Manhattan Community Board # 1`, sim
0.59). The other tiers are NOT guarded — the tier records HOW a link was made,
which beats string similarity: `exact/alias` legitimately links `NYC & Company`
-> `New York City Tourism + Conventions` at sim 0.25 (renamed 2023), and a
blanket guard held that correct link on the first run ever taken.
"""

import argparse
import asyncio
import os
import sys
from difflib import SequenceMatcher

import aiohttp
import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

try:
    import dbcreds
except ImportError:
    from modules import dbcreds


NORMALIZER_BASE_URL = os.environ.get(
    "NORMALIZER_BASE_URL", "https://normalize.databook.nyc").rstrip("/")
OTI_DATASET_ID = 328
LINK_TIERS = ('exact/alias', 'token-set', 'curated', 'imported')

# Below this, a `token-set` link is held rather than written. Tuned to admit
# real naming variance ("NYC Cyber Command" vs "Cyber Command") while rejecting
# the known bad link ("Community Services Board" vs "Manhattan Community
# Board # 1", which scores 0.59).
NAME_SIM_MIN = 0.66

# Only this tier gets similarity-checked -- see the docstring.
GUARDED_TIERS = ("token-set",)


def norm(s: str) -> str:
    """Kept byte-identical to adopt_nyc_orgs.norm -- apostrophes DROPPED, not
    spaced (#147), so the two scripts agree on whether two names are the same."""
    import re
    s = (s or "").upper().replace("&", " AND ").replace("’", "'").replace("'", "")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sim(a: str, b: str) -> float:
    """Similarity that is not fooled by one name being a clean superset of the
    other -- `Cyber Command` vs `NYC Cyber Command` should read as the same
    body, and plain ratio already handles that; containment makes it explicit."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


class Normalizer:
    def __init__(self, session, apply):
        self.s, self.apply = session, apply

    async def get(self, path):
        async with self.s.get(NORMALIZER_BASE_URL + path,
                              timeout=aiohttp.ClientTimeout(total=180)) as r:
            r.raise_for_status()
            return await r.json()

    async def put_matches(self, dataset_id, entries):
        if not self.apply:
            return
        async with self.s.put(
                f"{NORMALIZER_BASE_URL}/matches/{dataset_id}/orgs",
                json={"core_dataset": "orgs", "matches": entries},
                timeout=aiohttp.ClientTimeout(total=180)) as r:
            r.raise_for_status()
            return await r.json()


async def linked_orgs(conn):
    """OTI record_id -> the live org it is linked to (with the link's tier)."""
    rows = await conn.fetch(
        "SELECT x.nyc_record_id, x.match_tier, w.id, w.name "
        "FROM nyc_org_crosswalk x JOIN wegov_orgs w ON w.id = x.wegov_org_id "
        "WHERE x.match_tier = ANY($1::text[]) AND w.retired_at IS NULL",
        list(LINK_TIERS))
    return {r["nyc_record_id"]: dict(r) for r in rows}


async def oti_name_to_record(conn):
    """OTI org name -> record_id, from the ingested copy of the registry."""
    rows = await conn.fetch(
        'SELECT record_id, name FROM "nyc-agencies-and-governance-organizations" '
        "WHERE COALESCE(record_id,'') <> ''")
    return {r["name"]: r["record_id"] for r in rows}


async def fix_oti_dataset_matches(conn, nz, plan):
    """Rewrite dataset 328's org matches from the crosswalk, not from fuzz."""
    by_record = await linked_orgs(conn)
    oti_names = await oti_name_to_record(conn)

    cur = await nz.get(f"/matches/{OTI_DATASET_ID}/orgs")
    current = {m["source_text"]: m.get("core_text") for m in cur.get("matches", [])}
    plan.append(f"ds {OTI_DATASET_ID}: {len(current)} existing org matches")

    entries, changed, same, unlinked, skipped = [], [], 0, 0, []
    for name, rec in sorted(oti_names.items()):
        org = by_record.get(rec)
        if not org:
            unlinked += 1
            continue
        want = org["name"]           # the register name the feed always emits
        if current.get(name) == want:
            # Already pointing where the crosswalk says. The guard below is
            # checked only on actual REWRITES — a legitimate token-set link
            # can score badly forever (order inversions like `Office of the
            # Borough President of Queens` <-> `Queens Borough President` sit
            # at 0.48-0.65), and flagging a stable, already-correct match
            # every weekly run is noise that trains people to ignore holds.
            same += 1
            continue
        tier, s = org.get("match_tier") or "", sim(name, org["name"])
        if tier in GUARDED_TIERS and s < NAME_SIM_MIN:
            skipped.append(f"{name!r} -> {org['id']} {org['name']!r} "
                           f"(tier {tier}, sim {s:.2f})")
            continue
        changed.append((name, current.get(name), want))
        entries.append({"source_text": name, "core_text": want,
                        "matched_by": "manual"})

    plan.append(f"ds {OTI_DATASET_ID}: {same} already correct, {len(changed)} to "
                f"rewrite, {unlinked} OTI records with no crosswalk link, "
                f"{len(skipped)} held by the token-set similarity guard")
    for s in skipped:
        plan.append(f"    HELD  {s} -- crosswalk link needs human review")
    for name, was, now in changed[:25]:
        plan.append(f"    {name[:44]:<44} {str(was)[:30]:<30} -> {now[:34]}")
    if len(changed) > 25:
        plan.append(f"    ... and {len(changed) - 25} more")
    if entries:
        await nz.put_matches(OTI_DATASET_ID, entries)
    return len(changed)


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
        print(f"[sync] normalizer: {NORMALIZER_BASE_URL}")
        print(f"[sync] mode: {'APPLY' if args.apply else 'DRY RUN (pass --apply)'}\n")
        plan = []
        async with aiohttp.ClientSession() as session:
            nz = Normalizer(session, args.apply)
            await fix_oti_dataset_matches(conn, nz, plan)
        for line in plan:
            print(f"[sync] {line}")
        print("\n[sync] ⚠ the normalizer re-processes a dataset whenever the live "
              "ETag differs from the stored one, so corrected matches take effect "
              "on the table's next ingest.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
