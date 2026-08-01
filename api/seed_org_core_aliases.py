"""Seed `org_core_aliases` and pre-flight the derived matching dictionary.

Phase 2 of docs/ORG-DIRECTORY-OF-RECORD-PLAN.md. Two jobs, one file, because
they share every measurement:

    python seed_org_core_aliases.py            # dry run of the seeding
    python seed_org_core_aliases.py --apply    # create + seed the alias table
    python seed_org_core_aliases.py --check    # pre-flight: exit 1 unless every
                                               # match-referenced core name is
                                               # in /get/orgs/core

WHY THE TABLE EXISTS
====================
`GET /get/orgs/core` derives the normalizer's matching dictionary from
`wegov_orgs`. Measured against prod 2026-07-31, the register's name variants
reproduce today's 545 hand-maintained core entities with the SAME id in every
case but sixteen, and those sixteen are exactly what this table carries:

  * 12 match-referenced names the register cannot derive — the five chart
    scaffolding names (`Classification`/`Official` rows are excluded from the
    general feed: `District Attorneys` as a match target would swallow the
    five real DA offices, yet a manual payroll match row references it), two
    hand aliases (`NYC Districting Commission`, `Housing and Community
    Renewal`), an UPPERCASE duplicate key, and the 4 id-less stubs that a
    match row references but no org backs;
  * 4 collision incumbents — variant strings the register maps to MORE THAN
    ONE org (`United Federation of Teachers` names both the union and its
    bargaining units). The feed omits colliding variants unless this table
    names the incumbent, and these four are the only colliding variants the
    hand-maintained core had resolved. Their ids preserve that resolution
    verbatim — never re-rolled.

The seed is HARDCODED, not derived at run time, deliberately: it is a snapshot
of human curation as of the switch, reviewable in this diff, and idempotent
(`ON CONFLICT DO NOTHING` — a re-run never clobbers a later human edit).
Future additions are plain INSERTs into the table; the --check below is what
tells you one is needed.

THE PRE-FLIGHT (--check)
========================
    every distinct matches.core_text where core_dataset='orgs' (excluding the
    __SKIP__ sentinel) must appear in /get/orgs/core

Run before every `POST /core/orgs/refresh` — the refresh is a delete-and-
reload, so a name missing from the feed silently orphans every match row
pointing at it. Wired into scripts/org-registry-refresh.sh (Phase 4b), where a
non-zero exit stops the refresh and leaves the previous dictionary in place.
"""

import argparse
import asyncio
import os
import sys

import aiohttp
import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

try:
    import dbcreds
except ImportError:
    from modules import dbcreds

NORMALIZER_BASE_URL = os.environ.get(
    "NORMALIZER_BASE_URL", "https://normalize.databook.nyc").rstrip("/")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")

DDL = """
CREATE TABLE IF NOT EXISTS org_core_aliases (
    name       TEXT PRIMARY KEY,
    org_id     INTEGER,
    note       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

# (name, org_id, note). org_id None = a known id-less stub: the feed emits it
# with an empty id so the match rows referencing it keep resolving, exactly as
# the hand-maintained stub did. Every id below was read out of the live core
# on 2026-07-31, not invented here.
SEED = [
    # ── match-referenced names the register cannot derive ────────────────────
    ("COMMISSION ON RACIAL EQUITY", 170100295,
     "uppercase duplicate key; 14 match rows reference this exact casing"),
    ("Chief Climate Officer", 170100240,
     "Official-typed chart node, excluded from the general feed; match-referenced"),
    ("Chief Technology Officer", 170100034,
     "Official-typed chart node, excluded from the general feed; match-referenced"),
    ("Chief of Staff", 170100017,
     "Official-typed chart node, excluded from the general feed; match-referenced"),
    ("Deputy Mayor for Economic and Workforce Development", 170100230,
     "Official-typed chart node, excluded from the general feed; match-referenced"),
    ("District Attorneys", 170020021,
     "Classification chart node; ds 1 maps payroll's 'District Attorney' here"),
    ("Housing and Community Renewal", 170020033,
     "hand alias for NYS Homes & Community Renewal"),
    ("NYC Districting Commission", 170100330,
     "12 datasets map this by hand; the org's name is OTI's longer form"),
    ("NYS Department of Public Service", None,
     "id-less stub, match-referenced; no org backs it yet"),
    ("Upper Manhattan Empowerment Zone", None,
     "id-less stub, match-referenced; no org backs it yet"),
    ("Pavers & Road Builders DC", None,
     "id-less stub, match-referenced; no org backs it yet"),
    ("Industrial Business Zone Boundary Commission", None,
     "id-less stub, match-referenced; no org backs it yet"),
    # ── collision incumbents (variant names >1 org; keep the curated id) ─────
    ("District Council 37, AFSCME", 17001496,
     "collision incumbent: alternate_name of 19 bargaining units"),
    ("Organization of Staff Analysts", 17001478,
     "collision incumbent: union vs bargaining-unit name"),
    ("Service Employees' International Union, Local 1199", 17001480,
     "collision incumbent: union vs bargaining-unit name"),
    ("United Federation of Teachers", 17001498,
     "collision incumbent: union vs bargaining-unit name"),
]


async def _connect():
    return await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=dbcreds.password(),
        database=os.environ.get("POSTGRES_DB", "databook"))


async def seed(apply: bool) -> int:
    conn = await _connect()
    try:
        print(f"[seed] mode: {'APPLY' if apply else 'DRY RUN (pass --apply)'}")
        # Every seeded id must exist in the register — a typo here would stamp
        # an unresolvable id onto ingested rows, the exact defect Phase 2 ends.
        ids = [oid for _, oid, _ in SEED if oid is not None]
        found = {r["id"] for r in await conn.fetch(
            "SELECT id FROM wegov_orgs WHERE id = ANY($1::int[])", ids)}
        missing = [oid for oid in ids if oid not in found]
        if missing:
            raise SystemExit(f"[seed] ABORT: seeded ids absent from wegov_orgs: {missing}")

        if not apply:
            existing = set()
        else:
            await conn.execute(DDL)
            existing = {r["name"] for r in await conn.fetch(
                "SELECT name FROM org_core_aliases")}
        inserted = 0
        for name, org_id, note in SEED:
            if name in existing:
                print(f"[seed] keep  {name!r} (already present, not touched)")
                continue
            inserted += 1
            print(f"[seed] {'insert' if apply else 'would insert'}  "
                  f"{name!r} -> {org_id}")
            if apply:
                await conn.execute(
                    "INSERT INTO org_core_aliases (name, org_id, note) "
                    "VALUES ($1, $2, $3) ON CONFLICT (name) DO NOTHING",
                    name, org_id, note)
        print(f"[seed] {inserted} of {len(SEED)} rows "
              f"{'inserted' if apply else 'to insert'}")
        return 0
    finally:
        await conn.close()


async def check() -> int:
    """Every match-referenced core name must appear in the feed. Exit 1 if not."""
    async with aiohttp.ClientSession() as s:
        async def get(url):
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=180)) as r:
                r.raise_for_status()
                return await r.json()

        feed = await get(API_BASE_URL + "/get/orgs/core")
        names = {row["name"] for row in feed}
        print(f"[check] feed: {len(feed)} rows from {API_BASE_URL}/get/orgs/core")

        # A truncated feed must be refused BEFORE the delete-and-reload, not
        # discovered after — the refresh would happily load 10 rows. The live
        # feed measured ~1,650 at the switch; the register only grows (orgs
        # are retired, never deleted), so a real drop below this is a fault.
        floor = int(os.environ.get("ORG_CORE_FEED_FLOOR", "1200"))
        if len(feed) < floor:
            print(f"[check] FAIL: feed has {len(feed)} rows, below the floor "
                  f"of {floor} — refusing to bless a refresh from it")
            return 1

        datasets = await get(NORMALIZER_BASE_URL + "/datasets")
        if isinstance(datasets, dict):
            datasets = datasets.get("datasets") or list(datasets.values())
        ds_ids = [d["id"] for d in datasets if "orgs" in (d.get("core_datasets") or [])]
        core_texts = {}
        for did in ds_ids:
            m = await get(f"{NORMALIZER_BASE_URL}/matches/{did}/orgs")
            for row in m.get("matches", []):
                ct = row.get("core_text")
                if ct and ct != "__SKIP__":
                    core_texts.setdefault(ct, set()).add(did)
        print(f"[check] {len(core_texts)} distinct match-referenced core names "
              f"across {len(ds_ids)} datasets")

        missing = sorted(set(core_texts) - names)
        if missing:
            print(f"[check] FAIL: {len(missing)} match-referenced names are NOT "
                  f"in the feed — refreshing now would orphan their match rows:")
            for name in missing:
                print(f"[check]     {name!r} (datasets {sorted(core_texts[name])})")
            print("[check] fix: INSERT the name into org_core_aliases with the "
                  "org id it should resolve to (NULL for a deliberate stub).")
            return 1
        print("[check] OK: every match-referenced core name is in the feed")
        return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="create the table and insert missing seed rows")
    ap.add_argument("--check", action="store_true",
                    help="pre-flight the feed against the normalizer's match rows")
    args = ap.parse_args()
    if args.check:
        sys.exit(asyncio.run(check()))
    sys.exit(asyncio.run(seed(args.apply)))


if __name__ == "__main__":
    main()
