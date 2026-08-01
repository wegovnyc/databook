"""Adopt NYC's official agency registry (`t3jq-9nkf`) into our org directory.

`build_nyc_org_crosswalk.py` established the JOIN (173 of 306 OTI orgs linked to
`wegov_orgs`). This script is the ADOPTION: it imports the OTI orgs we do not
have, brings OTI's attributes across additively, and applies the three data
fixes the registry unblocked. It never lets OTI overwrite a field we already
hold -- disagreements are recorded for review instead.

Run (dry run is the default; nothing is written without --apply):

    docker compose exec -T api python adopt_nyc_orgs.py
    docker compose exec -T api python adopt_nyc_orgs.py --apply

WHY THIS IS MORE THAN AN IMPORT -- the measured state, 2026-07-30
================================================================
Two independent OTI -> `wegov_orgs` mappings already existed, and they disagree:

  A) `nyc_org_crosswalk`   173 links, one-to-one enforced, false positives
                           actively designed out (see that script's four rules).
  B) the normalizer's own enrichment on the ingested OTI table (dataset 328),
                           305 of 307 rows "mapped" but onto only 262 distinct
                           orgs -- because it is a loose fuzzy matcher with no
                           one-to-one constraint.

(B) is wrong in bulk. Measured collisions: **35 different Mayoral offices all
collapsed onto `170010002` Office of the Mayor**; Districting Commission ->
*Tax* Commission; Museum of the City of New York -> *City University* of New
York; NYCHA *Board* -> NYCHA; NYC *Ballet* -> NYC *Center*; Fund for Public
Schools -> NYC Public Schools; Lower Manhattan Development Corp -> EDC. Those
are corrected by `sync_normalizer_org_core.py`, not here.

WHY THE IMPORT REPAIRS PRODUCTION DATA
--------------------------------------
Someone had already begun importing OTI orgs into the NORMALIZER's `orgs` core
by hand. That core holds 515 entities:

    400  real numeric `wegov_orgs.id`
    108  SYNTHETIC hex ids (`693e48a482c22`) that exist in NO `wegov_orgs` row
      7  no id at all (a bare `{"name": ...}` stub)

Those synthetic ids are not inert -- the normalizer stamps them into
`wegov-org-id` during ingest, so **10,005 rows across 18 production tables now
carry an org id that resolves to nothing**: `facilitydb` 5,383 (Community
Action Board at DYCD), `nyccouncildiscretionaryfunding` 3,281 (Board of
Health), `crol` 654 (12 distinct), and 15 more. `wegov_orgs.id` is an
`integer`, so a 13-char hex id can never be stored there -- the repair is to
mint a real id here and repoint the core entity, which
`sync_normalizer_org_core.py` does.

The 7 id-less stubs are the same story one step earlier: `NYC Districting
Commission` is a stub that **12 datasets already map to by hand** (`manual`
match rows in ds 2, 31, 64, 65, 68, 74, 92, 191, 195, 202, 203). It was never
"unmappable" -- humans mapped it correctly to an entity that had no id to give.
Creating the org fixes all 12 at once with no re-mapping.

SCOPE: 133 imported, not 126
----------------------------
The review doc counts "126 no match" plus "7 rejected" separately. All 133 are
import candidates: tier `rejected` means *this OTI record is not that wegov
org*, which is not the same as *this org should not exist*. Every one of the 7
is a real distinct body we lack -- Community Action Board at DYCD (NOT DYCD),
Deputy Mayor for Community Safety (NOT for Public Safety), Deputy Mayor for
Operations (NOT Mayor's Office of Operations), NYC HER Future (matched against
*NJ* Future), NYCHA Board, Workforce Development Board, Workforce Development
Council. The first of those is the 5,383-row dangling cluster.

Their `rejected` crosswalk rows are LEFT IN PLACE: they must keep suppressing
the bad match suggestion. The new import gets its own `imported` row.

WHAT OTI NOW OWNS, AND WHAT STAYS OURS (owner decisions, 2026-07-30)
--------------------------------------------------------------------
  type        OTI's `organization_type`, **verbatim**. No mapping. Our own
              `Nonprofit` is renamed to OTI's `Nonprofit Organization`
              throughout, including the 13 rows OTI does not cover, so one
              concept has one name.
  parent      OTI's `reports_to` **when it resolves cleanly**; ours is kept
              when it does not. This overwrites an existing parent.
  name        **OURS stays.** OTI's official name goes in `display_name` and is
              what the site shows. `name` is a JOIN KEY -- see the SCHEMA
              comment on `display_name` for why renaming would silently zero
              the procurement figures on ~83 profiles.
  everything  additive, in `nyc_org_enrichment`.
  else

⚠ `wegov_orgs.type` is therefore a MIXED vocabulary -- OTI's for the 306, ours
for the ~930 it does not cover. `modules/orgfilter.py` owns the vocabulary and
names the four filters that would otherwise silently drop ~117 agencies.

`Nonprofit Organization` is deliberately absent from `/get/orgs/directory`'s
type filter, so the 49 Cultural Institutions Group nonprofits hold records --
repairing the dangling references -- WITHOUT appearing in a directory of
government. The government-typed rows DO enter `/get/orgs/{chart,directory,all}`
and search: intended, but a visible product change, not just a data change.

TRAPS
-----
- `wegov_orgs.child_of` stores **Airtable `rec...` ids**, joined on
  `airtable_id` (`main.py:320`), and that join strips brackets/quotes and
  compares for EQUALITY -- so `child_of` must hold exactly ONE id. OTI's
  `reports_to` has 5 multi-parent rows (`;`-separated); we take the first and
  record the full list in `nyc_org_enrichment.reports_to`.
- New orgs therefore need a synthetic `airtable_id`. Ours is
  `recOTI<record_id suffix>` -- deterministic, so a re-run is idempotent, and
  visibly not a real Airtable id.
- Retirement is **additive** (`retired_at`, `merged_into`), never a DELETE, so
  it is reversible and history survives. Serving queries must filter it.
"""

import argparse
import asyncio
import collections
import datetime
import json
import os
import re
import sys

import aiohttp
import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

try:
    import dbcreds
except ImportError:
    from modules import dbcreds


SOCRATA_ID = "t3jq-9nkf"
SOURCE_URL = f"https://data.cityofnewyork.us/resource/{SOCRATA_ID}.json?$limit=5000"

LINK_TIERS = ('exact/alias', 'token-set', 'curated', 'imported')

# ⚠ **OTI's `organization_type` is used VERBATIM** for every org in the registry
# (decision 2026-07-30). There is no longer a mapping into our own vocabulary.
#
# The previous version derived one by majority vote over the 173 linked orgs, and
# the measurement is why using OTI's directly is better: our types collapse real
# distinctions OTI preserves. 43 `Mayoral Office` + 32 `Mayoral Agency` + 16
# `Division` + 26 `Advisory or Regulatory Organization` were ALL just
# `City Agency` to us, and two OTI types were genuinely ambiguous in our data
# (`Public Benefit or Development Organization` split 10 City Agency / 5
# Nonprofit / 4 EDO / 2 State Agency). Adopting OTI's vocabulary drops the
# guessing entirely -- so there is no `type_confidence='low'` any more.
#
# ⚠ `wegov_orgs.type` is now MIXED: OTI's vocabulary for the 306, ours for the
# ~930 OTI does not cover. Every type filter must accept both -- see
# `modules/orgfilter.py`, which owns the vocabulary and lists the four places
# that would otherwise have silently dropped ~117 agencies.

# Our `Nonprofit` is renamed to OTI's `Nonprofit Organization` **throughout**,
# including the 13 non-OTI rows that carry it, so one concept has one name.
TYPE_RENAMES = {"Nonprofit": "Nonprofit Organization"}

# OTI links we have judged WRONG. Recorded as tier `rejected` (curated, so a
# rebuild never re-suggests them) which also frees the OTI record to be imported
# as its own org.
#   NYC_GOID_000119  Community Services Board -- a DOHMH body. The token-set pass
#   linked it to our `Manhattan Community Board # 1` (sim 0.59); confirmed by the
#   owner 2026-07-30 as having no association with that community board.
# ⚠ Keyed on the PAIR (record_id, wrong org id), not on record_id alone.
# Keyed on record_id it rejected EVERY row for that record — including the
# `imported` link to the org created FOR it. Measured on the first scheduled
# run: NYC_GOID_000119 ended up with two rejected rows, one of them cutting
# `Community Services Board` (170100385) off from its own OTI record, and OTI
# coverage fell 306 -> 305. A rejection says "this record is not THAT org"; it
# must never be read as "this record belongs to no org".
REJECTED_LINKS = {
    ("NYC_GOID_000119", 170010341):
        "Community Services Board has no association with "
        "Manhattan Community Board # 1 (owner, 2026-07-30)",
}

# Bodies that production data references through the normalizer core but which
# OTI does not publish, so the import cannot reach them. OTI is **Active-only**,
# which is why a dissolved corporation is absent. Without these three rows, 195
# ingested rows keep a `wegov-org-id` that resolves to nothing:
#
#   Off Track Betting Corp.                             184 rows
#   Commission to Strengthen Local Democracy             10 rows
#   Commission on Public Information and Communication     1 row
#
# Ids continue the same `1701` series; they carry NO `nyc_record_id` because
# they are not OTI records, and the reason each exists is recorded in
# `internal_notes` (a field nothing renders -- verified).
EXTRA_ORGS = [
    {"name": "New York City Off-Track Betting Corporation",
     "type": "Other", "code": "OTB",
     "alternate_name": "Off Track Betting Corp.",
     "note": "Public benefit corporation, dissolved 2010. Absent from OTI "
             "t3jq-9nkf because that feed is Active-only. Created because 184 "
             "ingested rows reference it via the normalizer orgs core."},
    {"name": "Commission to Strengthen Local Democracy",
     "type": "City Agency", "code": "",
     "alternate_name": "",
     "note": "Charter commission, work concluded. Absent from OTI t3jq-9nkf "
             "(Active-only). Created because 10 ingested rows reference it."},
    {"name": "Commission on Public Information and Communication",
     "type": "City Agency", "code": "COPIC",
     "alternate_name": "",
     "note": "Charter-mandated body (NYC Charter ch. 47). Absent from OTI "
             "t3jq-9nkf. Created because 1 ingested row references it."},
]

# The `1701` id series runs 170100002..170100248 with no gaps above it, so new
# records continue it. Bounded so a bug cannot wander into another series.
ID_BLOCK_LO = 170100000
ID_BLOCK_HI = 170199999

# ⚠ OTI's `reports_to` is FREE TEXT that does not reliably reference OTI's own
# `name` field. Measured: of 35 distinct values, 11 match no OTI org name --
# `Mayor` (the org is `Office of the Mayor`), `City Council` (`New York City
# Council`), `Bronx County District Attorney's Office` (`Bronx District
# Attorney's Office`), and so on.
#
# Only unambiguous rewrites go here -- each resolves to exactly ONE org.
# Deliberately absent, because guessing a parent is worse than leaving it empty:
#   'Deputy Mayor for Administration and Chief of Staff'  no such org
#   'Deputy Mayor for Communications'                     no such org
#   "Mayor's Community Affairs Unit"                      no such org
#   'Deputy Mayor of Housing Economic and Workforce Development'  a typo'd
#       variant that could mean either of two real Deputy Mayors
# Their full `reports_to` string is preserved in `nyc_org_enrichment` either way.
#
# ⚠ NOT aliased: `Deputy Mayor for Public Safety` -> `Deputy Mayor for Community
# Safety`. A human explicitly REJECTED that pair in the crosswalk review (they
# are different offices), and this map must not quietly reinstate it.
REPORTS_TO_ALIASES = {
    "Mayor": "Office of the Mayor",
    "Chief of Staff": "Chief of Staff to the Mayor",
    "City Council": "New York City Council",
    "Bronx County District Attorney's Office": "Bronx District Attorney's Office",
    # Richmond County IS Staten Island -- the same borough/county equivalence
    # build_nyc_org_crosswalk.py encodes for the DAs.
    "Office of the District Attorney Richmond County":
        "Staten Island District Attorney's Office",
    "Deputy Mayor for Strategic Initiatives":
        "Deputy Mayor for Strategic Policy Initiatives",
}

SCHEMA = """
ALTER TABLE wegov_orgs ADD COLUMN IF NOT EXISTS nyc_record_id TEXT;
ALTER TABLE wegov_orgs ADD COLUMN IF NOT EXISTS retired_at    TIMESTAMPTZ;
ALTER TABLE wegov_orgs ADD COLUMN IF NOT EXISTS merged_into   INTEGER;
-- ⚠ `display_name` exists so we can show NYC's official name WITHOUT renaming
-- `name`. `name` is a JOIN KEY, not just a label: `oce.py::_resolve_org_id`
-- matches `contracts.agency` against it by exact normalized equality, and the
-- org page passes it to `/oce/agency/summary?name=`. Renaming `Fire Department`
-- to `Fire Department of the City of New York` would therefore match ZERO
-- contracts and silently zero the procurement figures on ~83 profiles. It also
-- keeps every existing URL byte-identical, since `/o/{id}-{slug}` is built from
-- `name` (the slug is decorative -- lookup is by id -- but canonical links and
-- newly generated hrefs would otherwise change).
ALTER TABLE wegov_orgs ADD COLUMN IF NOT EXISTS display_name  TEXT;
-- Phase 3's parent FK. Ensured here (column only, no constraint) so this script
-- never fails on a database that has not run add_parent_org_id.py -- that script
-- owns the backfill, the FK constraint and the index, and is idempotent, so the
-- two cannot conflict.
ALTER TABLE wegov_orgs ADD COLUMN IF NOT EXISTS parent_org_id INTEGER;
CREATE UNIQUE INDEX IF NOT EXISTS idx_orgs_nyc_record_id
    ON wegov_orgs(nyc_record_id) WHERE nyc_record_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orgs_retired_at ON wegov_orgs(retired_at);

-- OTI's attributes, additively. Never merged into wegov_orgs: where OTI and we
-- disagree on a field we already hold, the disagreement is recorded (see the
-- `oti_*` vs `ours_*` pairs) so a human decides, per the agreed approach.
CREATE TABLE IF NOT EXISTS nyc_org_enrichment (
    org_id                       INTEGER NOT NULL,
    nyc_record_id                TEXT    NOT NULL,
    oti_name                     TEXT,
    oti_organization_type        TEXT,
    our_type                     TEXT,
    type_confidence              TEXT,
    acronym                      TEXT,
    alternate_or_former_names    TEXT,
    alternate_or_former_acronyms TEXT,
    principal_officer_full_name  TEXT,
    principal_officer_title      TEXT,
    principal_officer_contact    TEXT,
    reports_to                   TEXT,
    operational_status           TEXT,
    url                          TEXT,
    in_org_chart                 TEXT,
    listed_in_nyc_gov_agency     TEXT,
    origin                       TEXT,     -- 'imported' | 'linked'
    name_disagrees               BOOLEAN DEFAULT FALSE,
    type_disagrees               BOOLEAN DEFAULT FALSE,
    parent_disagrees             BOOLEAN DEFAULT FALSE,
    ours_name                    TEXT,
    ours_parent_name             TEXT,
    curated                      BOOLEAN NOT NULL DEFAULT FALSE,
    curated_note                 TEXT,
    refreshed_at                 TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (org_id, nyc_record_id)
);
CREATE INDEX IF NOT EXISTS idx_nyc_org_enr_record ON nyc_org_enrichment(nyc_record_id);
"""


# ── helpers ──────────────────────────────────────────────────────────────────

def scalar(v) -> str:
    """Flatten a Socrata field to text.

    ⚠ Not every column in this feed is a string, and the ones that are not will
    fail an asyncpg text bind rather than coerce:
      * `url` (278 rows) and `principal_officer_contact` (147) are Socrata URL
        objects -- `{"url": "https://..."}`.
      * `in_org_chart` and `listed_in_nyc_gov_agency` are real booleans.
    `build_nyc_org_crosswalk.py` never hit this because it reads only `name`,
    `alternate_or_former_names`, `acronym` and `record_id`.
    """
    if v is None:
        return ""
    if isinstance(v, dict):
        return str(v.get("url") or v.get("address") or "")
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def norm(s: str) -> str:
    """Loose comparison key for detecting name/parent disagreement.

    ⚠ Apostrophes are DROPPED, not spaced. Replacing them with a space turns
    `Mayor's` into `MAYOR S`, so `Mayor's Office of X` reads as different from
    `Mayors Office of X` -- which would both invent false name disagreements and
    stop `reports_to` from resolving. This is the #147 lesson (`ADAM'S` ->
    `ADAMS`) applied here.
    """
    s = (s or "").upper().replace("&", " AND ").replace("’", "'").replace("'", "")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# `synthetic_airtable_id()` lived here until Phase 6. It minted `recOTI000314`
# from `NYC_GOID_000314` so an imported org could be referenced by `child_of`,
# which only ever addressed an org by `airtable_id`. The parent is
# `parent_org_id` now and an org's identity is its `id`, so nothing needs a
# synthetic Airtable id — and minting one would falsely claim Airtable
# provenance for a row that never came from there.


def first_parent(reports_to: str) -> str:
    """OTI ships `;`-separated multi-parents (5 rows). `child_of` is joined by
    EQUALITY after stripping brackets/quotes (`main.py:320`), so it must hold a
    single id -- the rest is preserved in `nyc_org_enrichment.reports_to`."""
    return next((p.strip() for p in (reports_to or "").split(";") if p.strip()), "")


def first_alt(names: str) -> str:
    return next((p.strip() for p in (names or "").split(";") if p.strip()), "")


async def fetch_oti(session) -> list:
    async with session.get(SOURCE_URL, timeout=aiohttp.ClientTimeout(total=120)) as r:
        r.raise_for_status()
        return await r.json()


# ── the three data fixes ─────────────────────────────────────────────────────
#
# Each was confirmed against OTI's authoritative record AND measured against
# production before being written here.

async def apply_data_fixes(conn, oti_by_id, plan, apply):
    """PDC merge, Gender Equality retirement, and the Districting Commission.

    Measured reference counts across all 45 tables carrying `wegov-org-id`:
        170020048  Public Design Commission (typed 'State Agency')   647 rows / 7 tables
        170011008  Public Design Commission (typed 'City Agency')      0 rows
        170011004  Commission on Gender Equity                        45 rows / 4 tables
        170100011  Commission on Gender Equality                       0 rows
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    # ── fix 1: Public Design Commission -- migrate onto the correctly-typed row.
    # 170020048 is typed 'State Agency' (no NYS body of that name exists; the
    # State analogue is OGS Design & Construction) but holds all 647 rows and is
    # the only one in the normalizer core. 170011008 is typed correctly and holds
    # nothing. Decision: the CORRECTLY TYPED record survives, and the data moves
    # to it -- so the surviving row needs no type edit at all, and the wrong type
    # leaves the directory entirely.
    #
    # Its parent still needs fixing: 170011008 says 'Deputy Mayor for Economic
    # and Workforce Development'; OTI says PDC reports to **Deputy Mayor for
    # Housing and Planning**. (Curiously the retiring row had the better parent,
    # 'Chief Housing Officer' -- each record held one right answer.)
    pdc_survivor, pdc_retire = 170011008, 170020048
    pdc = await conn.fetchrow(
        "SELECT id, name, type, alternate_name, description, logo, logo_file, "
        "code, main_phone, main_address, contact_page, charter "
        "FROM wegov_orgs WHERE id = $1", pdc_retire)
    surv = await conn.fetchrow("SELECT id, type FROM wegov_orgs WHERE id = $1", pdc_survivor)
    if pdc and surv:
        # Carry the retiring row's substance across, but only into fields the
        # survivor leaves empty -- never overwrite.
        carry = {k: pdc[k] for k in
                 ("alternate_name", "description", "logo", "logo_file", "code",
                  "main_phone", "main_address", "contact_page", "charter")
                 if pdc[k] not in (None, "")}
        plan.append(f"fix/pdc: carry {sorted(carry)} from {pdc_retire} into empty "
                    f"fields of {pdc_survivor}")
        if apply and carry:
            sets = ", ".join(
                f'"{k}" = COALESCE(NULLIF("{k}", \'\'), ${i + 2})'
                for i, k in enumerate(carry))
            await conn.execute(
                f"UPDATE wegov_orgs SET {sets} WHERE id = $1",
                pdc_survivor, *[carry[k] for k in carry])

        parent = await resolve_parent_ref(conn, "Deputy Mayor for Housing and Planning")
        if parent:
            plan.append(f"fix/pdc: reparent {pdc_survivor} -> "
                        f"Deputy Mayor for Housing and Planning ({parent['id']}) per OTI")
            if apply:
                await conn.execute(
                    'UPDATE wegov_orgs SET parent_org_id = $2 WHERE id = $1',
                    pdc_survivor, int(parent["id"]))
        else:
            plan.append("fix/pdc: WARNING 'Deputy Mayor for Housing and Planning' not "
                        "found in wegov_orgs -- parent left unchanged")

        moved = await repoint_org_id(conn, pdc_retire, pdc_survivor,
                                     "Public Design Commission", plan, apply)
        plan.append(f"fix/pdc: repointed {moved} ingested rows {pdc_retire} -> {pdc_survivor}")
        plan.append(f"fix/pdc: retire {pdc_retire} (merged_into {pdc_survivor})")
        if apply:
            await conn.execute(
                "UPDATE wegov_orgs SET retired_at = $2, merged_into = $3 WHERE id = $1",
                pdc_retire, now, pdc_survivor)
            # The crosswalk must follow the survivor, or the OTI record still
            # points at a retired org.
            # ⚠ `nyc_org_crosswalk.wegov_org_id` is BIGINT while `wegov_orgs.id`
            # is INTEGER, so one placeholder used in both contexts makes
            # asyncpg raise AmbiguousParameterError -- cast at each use.
            await conn.execute(
                "UPDATE nyc_org_crosswalk SET wegov_org_id = $1::bigint, wegov_name = "
                "(SELECT name FROM wegov_orgs WHERE id = $1::int) "
                "WHERE nyc_record_id = 'NYC_GOID_000397'", pdc_survivor)
    else:
        plan.append("fix/pdc: SKIPPED -- one of 170011008/170020048 is absent "
                    "(already applied?)")

    # ── fix 2: Commission on Gender Equality (170100011) is a duplicate of
    # Commission on Gender Equity (170011004) -- same URL, same body (LL 45 of
    # 2020). OTI knows only 'Commission on Gender Equity'. Measured: the
    # duplicate has ZERO rows in all 45 tables and ZERO normalizer match rows
    # point at it, so retiring it orphans nothing.
    #
    # The duplicate did hold the better parent (Office of Equity); the survivor
    # says 'Additional Mayoral Agencies (Not on Chart)'. Move it across.
    ge_survivor, ge_retire = 170011004, 170100011
    if await conn.fetchval("SELECT 1 FROM wegov_orgs WHERE id = $1 AND retired_at IS NULL",
                           ge_retire):
        parent = await resolve_parent_ref(conn, "Office of Equity")
        if parent:
            plan.append(f"fix/gender-equity: reparent {ge_survivor} -> "
                        f"Office of Equity ({parent['id']}), inherited from the duplicate")
            if apply:
                await conn.execute(
                    'UPDATE wegov_orgs SET parent_org_id = $2 WHERE id = $1',
                    ge_survivor, int(parent["id"]))
        plan.append(f"fix/gender-equity: retire {ge_retire} (merged_into {ge_survivor})")
        if apply:
            await conn.execute(
                "UPDATE wegov_orgs SET retired_at = $2, merged_into = $3 WHERE id = $1",
                ge_retire, now, ge_survivor)
    else:
        plan.append("fix/gender-equity: SKIPPED -- 170100011 already retired/absent")

    # ── fix 3: the Districting Commission is created by the ordinary import
    # path (it is one of the 133). Nothing special is needed HERE -- the fix
    # that matters is giving the normalizer's id-less `NYC Districting
    # Commission` stub this new id, which `sync_normalizer_org_core.py` does,
    # and which repairs all 12 datasets that already map to it by hand.
    dc = oti_by_id.get("NYC_GOID_000314")
    plan.append("fix/districting: created via the import path"
                if dc else
                "fix/districting: WARNING NYC_GOID_000314 absent from the live OTI feed")


async def resolve_parent_ref(conn, name: str):
    """Find a live org to parent onto, by exact then normalized name."""
    # ⚠ No longer requires an `airtable_id`. Until Phase 6 both queries did,
    # because a parent was written as `child_of = [airtable_id]` — so an org
    # without one could not be a parent, which would have silently excluded
    # every org created through the Phase 5 editor. The parent is an id now.
    row = await conn.fetchrow(
        "SELECT id, name FROM wegov_orgs "
        "WHERE name = $1 AND retired_at IS NULL ORDER BY id LIMIT 1", name)
    if row:
        return row
    rows = await conn.fetch(
        "SELECT id, name FROM wegov_orgs WHERE retired_at IS NULL")
    target = norm(name)
    for r in rows:
        if norm(r["name"]) == target:
            return r
    return None


async def repoint_org_id(conn, old, new, new_name, plan, apply):
    """Repoint `wegov-org-id` across every table that carries one.

    The durable fix is always the normalizer core (the next ingest rewrites
    these columns); this makes the already-ingested data correct NOW rather
    than after the next sweep.
    """
    tables = [r["table_name"] for r in await conn.fetch(
        "SELECT table_name FROM information_schema.columns "
        "WHERE column_name = 'wegov-org-id' ORDER BY table_name")]
    total = 0
    for t in tables:
        n = await conn.fetchval(
            f'SELECT count(*) FROM "{t}" WHERE "wegov-org-id"::text = $1', str(old))
        if not n:
            continue
        total += n
        plan.append(f"    repoint {n:>6} rows in {t}")
        if apply:
            # Some of these columns are `numeric`, most are `text`; the cast on
            # the read side plus a plain assignment keeps both working.
            await conn.execute(
                f'UPDATE "{t}" SET "wegov-org-id" = $1, "wegov-org-name" = $2 '
                f'WHERE "wegov-org-id"::text = $3', str(new), new_name, str(old))
    return total


# ── import ───────────────────────────────────────────────────────────────────

async def apply_rejected_links(conn, plan, apply):
    """Record owner-refused OTI links so they stop being links.

    Written as tier `rejected` with `curated = true`, which the crosswalk
    rebuild preserves and never re-suggests (the #149 lesson). Demoting the row
    also makes the OTI record unlinked, so the ordinary import path gives it its
    own org on this same run.
    """
    for (rec, wrong_org_id), why in REJECTED_LINKS.items():
        row = await conn.fetchrow(
            "SELECT wegov_org_id, wegov_name, match_tier FROM nyc_org_crosswalk "
            "WHERE nyc_record_id = $1 AND wegov_org_id = $2", rec, wrong_org_id)
        if not row:
            plan.append(f"reject: {rec} -> {wrong_org_id} has no crosswalk row "
                        f"(already gone)")
            continue
        if row["match_tier"] == "rejected":
            plan.append(f"reject: {rec} -> {wrong_org_id} already rejected")
            continue
        plan.append(f"reject: {rec} -/-> {row['wegov_org_id']} "
                    f"{row['wegov_name']!r} ({why})")
        if apply:
            # Scoped to the one wrong pair. Anything else for this record —
            # notably the `imported` link to the org created for it — stands.
            await conn.execute(
                "UPDATE nyc_org_crosswalk SET match_tier = 'rejected', "
                "curated = TRUE WHERE nyc_record_id = $1 AND wegov_org_id = $2",
                rec, wrong_org_id)


async def apply_type_renames(conn, plan, apply):
    """Rename our type values onto OTI's vocabulary, across ALL rows."""
    for old, new in TYPE_RENAMES.items():
        n = await conn.fetchval(
            'SELECT count(*) FROM wegov_orgs WHERE "type" = $1', old)
        plan.append(f"types: rename {old!r} -> {new!r} on {n} rows "
                    f"(all rows, not just OTI-linked)")
        if apply and n:
            await conn.execute(
                'UPDATE wegov_orgs SET "type" = $2 WHERE "type" = $1', old, new)


async def apply_oti_types(conn, oti, plan, apply):
    """Set `type` to OTI's `organization_type` for every org in the registry."""
    oti_type = {r["record_id"]: (r.get("organization_type") or "").strip()
                for r in oti}
    rows = await conn.fetch(
        "SELECT x.nyc_record_id, w.id, w.name, w.type FROM nyc_org_crosswalk x "
        "JOIN wegov_orgs w ON w.id = x.wegov_org_id "
        "WHERE x.match_tier = ANY($1::text[]) AND w.retired_at IS NULL",
        list(LINK_TIERS))
    changes = collections.Counter()
    n = 0
    for r in rows:
        want = oti_type.get(r["nyc_record_id"])
        if not want or want == (r["type"] or ""):
            continue
        n += 1
        changes[f"{r['type']!r} -> {want!r}"] += 1
        if apply:
            await conn.execute('UPDATE wegov_orgs SET "type" = $2 WHERE id = $1',
                               r["id"], want)
    plan.append(f"types: adopted OTI organization_type on {n} orgs")
    for k, c in changes.most_common():
        plan.append(f"    {c:>4}  {k}")


async def apply_display_names(conn, oti, plan, apply):
    """Set `display_name` to OTI's name wherever it differs from ours.

    `name` is deliberately left alone -- it is a join key into `contracts.agency`
    and the source of every `/o/{id}-{slug}` URL. See the SCHEMA comment.
    """
    oti_name = {r["record_id"]: (r.get("name") or "").strip() for r in oti}
    rows = await conn.fetch(
        "SELECT x.nyc_record_id, w.id, w.name, w.display_name "
        "FROM nyc_org_crosswalk x JOIN wegov_orgs w ON w.id = x.wegov_org_id "
        "WHERE x.match_tier = ANY($1::text[]) AND w.retired_at IS NULL",
        list(LINK_TIERS))
    set_n = cleared = 0
    for r in rows:
        want = oti_name.get(r["nyc_record_id"]) or ""
        # Only a genuine difference earns a display_name; an identical one would
        # be noise that later drifts out of sync.
        if want and norm(want) != norm(r["name"]):
            if (r["display_name"] or "") != want:
                set_n += 1
                if apply:
                    await conn.execute(
                        "UPDATE wegov_orgs SET display_name = $2 WHERE id = $1",
                        r["id"], want)
        elif r["display_name"]:
            cleared += 1
            if apply:
                await conn.execute(
                    "UPDATE wegov_orgs SET display_name = NULL WHERE id = $1",
                    r["id"])
    plan.append(f"display names: set {set_n} to OTI's official name, cleared "
                f"{cleared} that no longer differ (URLs + `name` untouched)")


async def relink_imported_orgs(conn, plan, apply):
    """Every imported org must be linked to the OTI record it was created from.

    ⚠ Repairs the record-id-scoped rejection bug above. An imported org carries
    its source `nyc_record_id`, so a missing `imported` crosswalk row is
    unambiguous damage rather than a judgement call — the org exists BECAUSE of
    that record. Left unrepaired the org is orphaned from its own source, its
    `nyc_org_enrichment` row is deleted as stale, and OTI coverage silently
    drops.
    """
    broken = await conn.fetch(
        "SELECT w.id, w.name, w.nyc_record_id FROM wegov_orgs w "
        "WHERE w.nyc_record_id IS NOT NULL AND w.retired_at IS NULL "
        "  AND NOT EXISTS (SELECT 1 FROM nyc_org_crosswalk x "
        "                  WHERE x.nyc_record_id = w.nyc_record_id "
        "                    AND x.wegov_org_id = w.id "
        "                    AND x.match_tier = ANY($1::text[]))",
        list(LINK_TIERS))
    plan.append(f"relink: {len(broken)} imported orgs missing their own OTI link")
    for r in broken:
        plan.append(f"    relink {r['name'][:44]!r} ({r['id']}) -> "
                    f"{r['nyc_record_id']}")
        if apply:
            await conn.execute(
                "INSERT INTO nyc_org_crosswalk (wegov_org_id, nyc_record_id, "
                "  nyc_name, wegov_name, match_tier, match_score, curated) "
                "VALUES ($1,$2,$3,$4,'imported',1.0,TRUE) "
                "ON CONFLICT (wegov_org_id, nyc_record_id) DO UPDATE "
                "  SET match_tier = 'imported', curated = TRUE",
                r["id"], r["nyc_record_id"], r["name"], r["name"])


async def import_missing(conn, oti, plan, apply):
    """Create a `wegov_orgs` row for every OTI org we do not already link to."""
    linked = {r["nyc_record_id"] for r in await conn.fetch(
        "SELECT nyc_record_id FROM nyc_org_crosswalk WHERE match_tier = ANY($1::text[])",
        list(LINK_TIERS))}
    already = {r["nyc_record_id"]: r["id"] for r in await conn.fetch(
        "SELECT id, nyc_record_id FROM wegov_orgs WHERE nyc_record_id IS NOT NULL")}

    todo = [r for r in oti
            if r["record_id"] not in linked and r["record_id"] not in already]
    plan.append(f"import: {len(oti)} OTI orgs, {len(linked)} already linked, "
                f"{len(already)} already imported -> {len(todo)} to create")
    if not todo:
        return {}

    next_id = (await conn.fetchval(
        "SELECT max(id) FROM wegov_orgs WHERE id BETWEEN $1 AND $2",
        ID_BLOCK_LO, ID_BLOCK_HI) or ID_BLOCK_LO) + 1

    created = {}
    by_type = collections.Counter()
    # Deterministic order so a partial run resumes predictably.
    for r in sorted(todo, key=lambda x: x["record_id"]):
        oid = next_id
        next_id += 1
        if next_id > ID_BLOCK_HI:
            raise RuntimeError("exhausted the 1701 id block")
        # OTI's type verbatim -- no mapping, nothing to guess.
        our_type = (r.get("organization_type") or "").strip() or "Other"
        by_type[our_type] += 1
        created[r["record_id"]] = {
            "id": oid, "name": r.get("name") or "", "type": our_type,
        }
        if apply:
            # ⚠ NO airtable_id. Phase 6 retired Airtable as an identity scheme:
            # a synthetic `recOTI…` existed only so children could reference this
            # row through `child_of`, and the parent is `parent_org_id` now. The
            # org's identity is its `id` — the primary key declared in Phase 3.
            await conn.execute(
                'INSERT INTO wegov_orgs (id, name, "type", url, '
                ' alternate_name, code, last_updated, nyc_record_id) '
                'VALUES ($1,$2,$3,$4,$5,$6,$7,$8)',
                oid, r.get("name") or "", our_type, scalar(r.get("url")),
                first_alt(r.get("alternate_or_former_names")),
                scalar(r.get("acronym")),
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
                r["record_id"])
            await conn.execute(
                "INSERT INTO nyc_org_crosswalk (wegov_org_id, nyc_record_id, nyc_name, "
                " wegov_name, match_tier, match_score, curated) "
                "VALUES ($1,$2,$3,$4,'imported',1.0,TRUE) "
                "ON CONFLICT (wegov_org_id, nyc_record_id) DO NOTHING",
                oid, r["record_id"], r.get("name"), r.get("name"))

    for k, n in by_type.most_common():
        plan.append(f"    {n:>3}  {k}")

    # Non-OTI bodies that production data references (see EXTRA_ORGS).
    for spec in EXTRA_ORGS:
        exists = await conn.fetchval(
            "SELECT id FROM wegov_orgs WHERE name = $1", spec["name"])
        if exists:
            plan.append(f"    extra: {spec['name']!r} already present ({exists})")
            continue
        oid = next_id
        next_id += 1
        plan.append(f"    extra: create {spec['name']!r} as {oid} ({spec['type']})")
        if apply:
            await conn.execute(
                'INSERT INTO wegov_orgs (id, name, "type", code, '
                ' alternate_name, internal_notes, last_updated) '
                'VALUES ($1,$2,$3,$4,$5,$6,$7)',
                oid, spec["name"], spec["type"], spec["code"],
                spec["alternate_name"], spec["note"],
                datetime.datetime.now(datetime.timezone.utc).isoformat())
    return created


async def wire_parents(conn, oti, plan, apply):
    """Resolve OTI `reports_to` -> the org's parent link.

    ⚠ Since Phase 3 the authoritative parent is **`parent_org_id`**, an FK to
    `wegov_orgs(id)`. `child_of` / `child_of_name` are written in step for one
    release, as provenance and as the rollback path (`orgfilter.parent_join`
    falls back to the legacy string join wherever the FK column is absent). When
    `child_of` is dropped, delete those two assignments and the `airtable_id`
    lookup that feeds them — nothing else here changes, because the decision of
    WHICH org is the parent never depended on the Airtable id.

    Only ever fills a parent that is EMPTY. An existing parent is a value we
    already hold, so a disagreement with OTI is recorded, not overwritten.

    ⚠ A `reports_to` value is an OTI NAME, and an OTI name frequently belongs to
    an org we hold under a DIFFERENT name -- `Office of the Mayor` is linked to
    our `170010002`, `Office of the Borough President of The Bronx` to our
    `Bronx Borough President`. So resolve through the crosswalk FIRST (OTI name
    -> record_id -> linked org) and only fall back to matching our own names.
    Name-matching alone left 14 parents unwired that we plainly have.

    ⚠ POLICY (owner, 2026-07-30): **OTI's parent WINS when it resolves cleanly,
    and ours is kept when it does not.** So this now overwrites an existing
    `child_of`, where an earlier version only filled empty ones. "Cleanly" means
    the `reports_to` value resolves to exactly one live org via the crosswalk or
    an exact name match -- no fuzzy matching, and `REPORTS_TO_ALIASES` covers
    only unambiguous rewrites. When it does not resolve, ours is left untouched
    rather than blanked, which is the whole point of the fallback.

    This applies to EVERY org in the registry, not just imported ones: OTI is
    the maintained source for the reporting line.
    """
    # Every org in the registry, not only the imported ones.
    rows = await conn.fetch(
        "SELECT x.nyc_record_id, w.id, w.name, w.parent_org_id "
        "FROM nyc_org_crosswalk x JOIN wegov_orgs w ON w.id = x.wegov_org_id "
        "WHERE x.match_tier = ANY($1::text[]) AND w.retired_at IS NULL",
        list(LINK_TIERS))
    by_record = {r["nyc_record_id"]: r for r in rows}
    oti_by_id = {r["record_id"]: r for r in oti}
    # Our current parent's NAME for the swap report. Phase 6 dropped
    # child_of_name, which is what used to supply it.
    name_by_id = {int(r["id"]): r["name"] for r in await conn.fetch(
        "SELECT id, name FROM wegov_orgs")}

    # OTI name -> the live org that OTI record resolves to, via the crosswalk.
    linked = await conn.fetch(
        "SELECT x.nyc_record_id, w.id, w.name "
        "FROM nyc_org_crosswalk x JOIN wegov_orgs w ON w.id = x.wegov_org_id "
        "WHERE x.match_tier = ANY($1::text[]) AND w.retired_at IS NULL",
        list(LINK_TIERS))
    org_for_record = {r["nyc_record_id"]: r for r in linked}
    org_for_oti_name = {}
    for r in oti:
        o = org_for_record.get(r["record_id"])
        if o:
            org_for_oti_name.setdefault(norm(r.get("name")), o)

    filled = replaced = unchanged = unresolved = 0
    misses, swaps = [], []
    # Records where OTI named a parent we could not resolve, so ours stands.
    # This is the ONLY meaningful "parent disagreement" once OTI wins whenever it
    # resolves -- comparing the raw `reports_to` string against our parent's name
    # just reports naming-form differences (OTI's `Office of the Mayor` vs our
    # `Mayor's Office`) and made 37 rows look unresolved when they were fine.
    kept_ours = set()
    for rec, row in by_record.items():
        parent_name = first_parent((oti_by_id.get(rec) or {}).get("reports_to"))
        if not parent_name:
            continue
        parent_name = REPORTS_TO_ALIASES.get(parent_name, parent_name)
        # crosswalk first (OTI name -> linked org), then our own names
        parent = org_for_oti_name.get(norm(parent_name)) \
            or await resolve_parent_ref(conn, parent_name)
        if not parent:
            # OTI's value does not resolve -> KEEP OURS.
            unresolved += 1
            kept_ours.add(rec)
            misses.append(f"{row['name'][:34]!r} reports_to {parent_name!r} "
                          f"(kept ours)")
            continue

        # "Already correct" is decided on parent_org_id, the authoritative
        # column. Phase 6 removed the child_of string it used to be compared
        # against as well.
        was_empty = row["parent_org_id"] is None
        if row["parent_org_id"] == int(parent["id"]):
            unchanged += 1
            continue
        if was_empty:
            filled += 1
        else:
            replaced += 1
            ours = name_by_id.get(row["parent_org_id"], "") or ""
            swaps.append(f"{row['name'][:32]!r}: {ours[:30]!r} -> "
                         f"{parent['name'][:30]!r}")
        if apply:
            await conn.execute(
                "UPDATE wegov_orgs SET parent_org_id = $2 WHERE id = $1",
                row["id"], int(parent["id"]))

    plan.append(f"parents: OTI applied where clear -- {filled} filled, {replaced} "
                f"REPLACED ours, {unchanged} already agreed, {unresolved} kept ours "
                f"(OTI's value did not resolve)")
    for s in swaps:
        plan.append(f"    replaced  {s}")
    for m in misses:
        plan.append(f"    kept      {m}")
    return kept_ours


# ── enrichment (additive) + disagreement report ──────────────────────────────

async def refresh_enrichment(conn, oti, plan, apply, kept_ours=frozenset()):
    """Upsert every OTI attribute into `nyc_org_enrichment`, and record what is
    still different after adoption."""
    # A record that stopped being a link (e.g. an owner rejection) must not leave
    # a stale enrichment row behind, or its old disagreement flags keep being
    # counted -- which is exactly how the verify block reported 83 name / 1 type
    # while the live pass computed 82 / 0.
    stale = await conn.execute(
        "DELETE FROM nyc_org_enrichment e WHERE NOT EXISTS ("
        "  SELECT 1 FROM nyc_org_crosswalk x WHERE x.nyc_record_id = e.nyc_record_id"
        "    AND x.wegov_org_id = e.org_id AND x.match_tier = ANY($1::text[]))",
        list(LINK_TIERS))
    plan.append(f"enrichment: cleared rows that are no longer links ({stale})")

    links = await conn.fetch(
        "SELECT x.nyc_record_id, x.wegov_org_id, x.match_tier, w.name AS ours_name, "
        "       w.type AS ours_type, par.name AS ours_parent, w.nyc_record_id "
        "         AS imported_from "
        "FROM nyc_org_crosswalk x JOIN wegov_orgs w ON w.id = x.wegov_org_id "
        "LEFT JOIN wegov_orgs par ON par.id = w.parent_org_id "
        "WHERE x.match_tier = ANY($1::text[]) AND w.retired_at IS NULL",
        list(LINK_TIERS))
    oti_by_id = {r["record_id"]: r for r in oti}

    n = dis_name = dis_type = dis_parent = 0
    for l in links:
        r = oti_by_id.get(l["nyc_record_id"])
        if not r:
            continue
        oti_type = (r.get("organization_type") or "").strip()
        ours_parent = ""
        try:
            p = json.loads(l["ours_parent"] or "[]")
            ours_parent = (p[0] if p else "") or ""
        except (ValueError, TypeError):
            ours_parent = (l["ours_parent"] or "").strip('[]"')

        # These now record what is still DIFFERENT after adoption, which is a
        # much smaller set than before:
        #   name_bad   -- expected and permanent. `name` stays as the join key
        #                 into contracts.agency; `display_name` carries OTI's.
        #   type_bad   -- should be 0: we take OTI's type verbatim.
        #   parent_bad -- only where OTI's reports_to did not resolve, so we
        #                 kept ours. Computed from what wire_parents actually
        #                 did, NOT by string-comparing `reports_to` against our
        #                 parent's name -- those differ in naming form even when
        #                 they are the same body.
        name_bad = norm(r.get("name")) != norm(l["ours_name"])
        type_bad = bool(oti_type) and oti_type != (l["ours_type"] or "")
        parent_bad = l["nyc_record_id"] in kept_ours
        dis_name += name_bad
        dis_type += type_bad
        dis_parent += parent_bad
        n += 1
        if not apply:
            continue
        await conn.execute(
            """INSERT INTO nyc_org_enrichment
                 (org_id, nyc_record_id, oti_name, oti_organization_type, our_type,
                  type_confidence, acronym, alternate_or_former_names,
                  alternate_or_former_acronyms, principal_officer_full_name,
                  principal_officer_title, principal_officer_contact, reports_to,
                  operational_status, url, in_org_chart, listed_in_nyc_gov_agency,
                  origin, name_disagrees, type_disagrees, parent_disagrees,
                  ours_name, ours_parent_name, refreshed_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,
                       $18,$19,$20,$21,$22,$23,NOW())
               ON CONFLICT (org_id, nyc_record_id) DO UPDATE SET
                 oti_name = EXCLUDED.oti_name,
                 oti_organization_type = EXCLUDED.oti_organization_type,
                 our_type = EXCLUDED.our_type,
                 type_confidence = EXCLUDED.type_confidence,
                 acronym = EXCLUDED.acronym,
                 alternate_or_former_names = EXCLUDED.alternate_or_former_names,
                 alternate_or_former_acronyms = EXCLUDED.alternate_or_former_acronyms,
                 principal_officer_full_name = EXCLUDED.principal_officer_full_name,
                 principal_officer_title = EXCLUDED.principal_officer_title,
                 principal_officer_contact = EXCLUDED.principal_officer_contact,
                 reports_to = EXCLUDED.reports_to,
                 operational_status = EXCLUDED.operational_status,
                 url = EXCLUDED.url,
                 in_org_chart = EXCLUDED.in_org_chart,
                 listed_in_nyc_gov_agency = EXCLUDED.listed_in_nyc_gov_agency,
                 origin = EXCLUDED.origin,
                 name_disagrees = EXCLUDED.name_disagrees,
                 type_disagrees = EXCLUDED.type_disagrees,
                 parent_disagrees = EXCLUDED.parent_disagrees,
                 ours_name = EXCLUDED.ours_name,
                 ours_parent_name = EXCLUDED.ours_parent_name,
                 refreshed_at = NOW()
               WHERE nyc_org_enrichment.curated = false""",
            l["wegov_org_id"], l["nyc_record_id"], r.get("name"), oti_type,
            # `our_type` is now OTI's own value, adopted verbatim, so there is
            # nothing to be confident or unconfident about.
            oti_type, "oti",
            scalar(r.get("acronym")), scalar(r.get("alternate_or_former_names")),
            scalar(r.get("alternate_or_former_acronyms")),
            scalar(r.get("principal_officer_full_name")),
            scalar(r.get("principal_officer_title")),
            scalar(r.get("principal_officer_contact")), scalar(r.get("reports_to")),
            scalar(r.get("operational_status")), scalar(r.get("url")),
            scalar(r.get("in_org_chart")), scalar(r.get("listed_in_nyc_gov_agency")),
            "imported" if l["imported_from"] else "linked",
            name_bad, type_bad, parent_bad, l["ours_name"], ours_parent)

    plan.append(f"enrichment: {n} orgs; disagreements -> name {dis_name}, "
                f"type {dis_type}, parent {dis_parent} (recorded, NOT applied)")


# ── verify ───────────────────────────────────────────────────────────────────

async def verify(conn, oti):
    print("\n=== verification ===")
    total = await conn.fetchval("SELECT count(*) FROM wegov_orgs")
    live = await conn.fetchval("SELECT count(*) FROM wegov_orgs WHERE retired_at IS NULL")
    imported = await conn.fetchval(
        "SELECT count(*) FROM wegov_orgs WHERE nyc_record_id IS NOT NULL")
    retired = await conn.fetchval(
        "SELECT count(*) FROM wegov_orgs WHERE retired_at IS NOT NULL")
    print(f"wegov_orgs: {total} total, {live} live, {retired} retired, "
          f"{imported} carrying an OTI record_id")

    linked = await conn.fetchval(
        "SELECT count(DISTINCT nyc_record_id) FROM nyc_org_crosswalk "
        "WHERE match_tier = ANY($1::text[])", list(LINK_TIERS))
    print(f"OTI coverage: {linked}/{len(oti)} record_ids resolve to a live org")

    dupe = await conn.fetch(
        "SELECT nyc_record_id, count(*) FROM wegov_orgs "
        "WHERE nyc_record_id IS NOT NULL GROUP BY 1 HAVING count(*) > 1")
    print(f"duplicate record_id rows: {len(dupe)} (must be 0)")

    unlinked = await conn.fetchval(
        "SELECT count(*) FROM wegov_orgs w WHERE w.nyc_record_id IS NOT NULL "
        "  AND w.retired_at IS NULL AND NOT EXISTS ("
        "    SELECT 1 FROM nyc_org_crosswalk x "
        "    WHERE x.nyc_record_id = w.nyc_record_id AND x.wegov_org_id = w.id "
        "      AND x.match_tier = ANY($1::text[]))", list(LINK_TIERS))
    print(f"imported orgs not linked to their own OTI record: {unlinked} (must be 0)")

    orphan = await conn.fetchval(
        "SELECT count(*) FROM nyc_org_crosswalk x LEFT JOIN wegov_orgs w "
        "ON w.id = x.wegov_org_id WHERE x.match_tier = ANY($1::text[]) "
        "AND (w.id IS NULL OR w.retired_at IS NOT NULL)", list(LINK_TIERS))
    print(f"crosswalk links pointing at a missing/retired org: {orphan} (must be 0)")

    # The FK guarantees the parent EXISTS. It does not guarantee the parent is
    # LIVE — retirement is additive, so a live org can end up pointing at a
    # retired parent, which drops its whole branch off the org chart (the
    # generator skips parentless orgs). That is the invariant left to measure
    # now that child_of is gone.
    stale_parent = await conn.fetchval(
        "SELECT count(*) FROM wegov_orgs o JOIN wegov_orgs p ON p.id = o.parent_org_id "
        "WHERE o.retired_at IS NULL AND p.retired_at IS NOT NULL")
    print(f"live orgs whose parent is RETIRED: {stale_parent} (must be 0)")

    dis = await conn.fetchrow(
        "SELECT count(*) FILTER (WHERE name_disagrees) AS n, "
        "       count(*) FILTER (WHERE type_disagrees) AS t, "
        "       count(*) FILTER (WHERE parent_disagrees) AS p, "
        "       count(*) FILTER (WHERE type_confidence = 'low') AS low "
        "FROM nyc_org_enrichment")
    if dis:
        print(f"awaiting review: name {dis['n']}, type {dis['t']}, parent {dis['p']}, "
              f"low-confidence type {dis['low']}")


REPORT_HEADER = """# OTI agency registry (`t3jq-9nkf`) -- adoption review

What the adoption brought across, and every disagreement it recorded instead of
applying. Regenerate with:

    docker compose exec -T api python adopt_nyc_orgs.py --report > \\
        docs/nyc-org-adoption-review.md

OTI's attributes are additive: they live in `nyc_org_enrichment`, and
`wegov_orgs` keeps its own `name`, `type` and parent. Where the two disagree the
row below is the decision waiting to be made -- nothing here has been applied to
`wegov_orgs`.
"""


async def report(conn):
    """Emit the review markdown from the live enrichment table."""
    s = await conn.fetchrow(
        "SELECT (SELECT count(*) FROM wegov_orgs) AS orgs, "
        "  (SELECT count(*) FROM wegov_orgs WHERE retired_at IS NULL) AS live, "
        "  (SELECT count(*) FROM wegov_orgs WHERE nyc_record_id IS NOT NULL) AS imported, "
        "  count(*) AS enriched, "
        "  count(*) FILTER (WHERE name_disagrees)   AS dname, "
        "  count(*) FILTER (WHERE type_disagrees)   AS dtype, "
        "  count(*) FILTER (WHERE parent_disagrees) AS dparent, "
        "  count(*) FILTER (WHERE type_confidence = 'low') AS lowconf "
        "FROM nyc_org_enrichment")

    out = [REPORT_HEADER]
    out.append(f"""
## Where things stand

| | |
|---|---:|
| `wegov_orgs` rows | {s['orgs']} |
| live (not retired) | {s['live']} |
| created from an OTI record | {s['imported']} |
| OTI records with an enrichment row | {s['enriched']} |
| **name disagreements** | **{s['dname']}** |
| **type disagreements** | **{s['dtype']}** |
| **parent disagreements** | **{s['dparent']}** |
| imported with a low-confidence type | {s['lowconf']} |
""")

    attrs = await conn.fetchrow(
        "SELECT count(*) FILTER (WHERE COALESCE(acronym,'') <> '') AS acronym, "
        "  count(*) FILTER (WHERE COALESCE(alternate_or_former_names,'') <> '') AS alt, "
        "  count(*) FILTER (WHERE COALESCE(principal_officer_full_name,'') <> '') AS po, "
        "  count(*) FILTER (WHERE COALESCE(principal_officer_title,'') <> '') AS pot, "
        "  count(*) FILTER (WHERE COALESCE(principal_officer_contact,'') <> '') AS poc, "
        "  count(*) FILTER (WHERE COALESCE(reports_to,'') <> '') AS rt, "
        "  count(*) FILTER (WHERE in_org_chart = 'true') AS chart "
        "FROM nyc_org_enrichment")
    out.append(f"""## New attributes now held (additively, in `nyc_org_enrichment`)

| attribute | populated |
|---|---:|
| `acronym` | {attrs['acronym']} |
| `alternate_or_former_names` | {attrs['alt']} |
| `principal_officer_full_name` | {attrs['po']} |
| `principal_officer_title` | {attrs['pot']} |
| `principal_officer_contact` | {attrs['poc']} |
| `reports_to` | {attrs['rt']} |
| `in_org_chart = true` | {attrs['chart']} |
""")

    retired = await conn.fetch(
        "SELECT w.id, w.name, w.type, w.merged_into, "
        "  (SELECT name FROM wegov_orgs s WHERE s.id = w.merged_into) AS into_name "
        "FROM wegov_orgs w WHERE w.retired_at IS NOT NULL ORDER BY w.id")
    if retired:
        out.append("## Retired duplicates\n\n"
                   "Additive, never deleted -- `retired_at` + `merged_into`, so the "
                   "merge is reversible.\n\n"
                   "| id | name | was typed | merged into |\n|---|---|---|---|")
        for r in retired:
            out.append(f"| `{r['id']}` | {r['name']} | {r['type']} | "
                       f"`{r['merged_into']}` {r['into_name']} |")
        out.append("")

    types = await conn.fetch(
        "SELECT w.type, count(*) AS n, "
        "       count(*) FILTER (WHERE w.nyc_record_id IS NOT NULL) AS imported "
        "FROM nyc_org_crosswalk x JOIN wegov_orgs w ON w.id = x.wegov_org_id "
        "WHERE x.match_tier = ANY($1::text[]) AND w.retired_at IS NULL "
        "GROUP BY 1 ORDER BY 2 DESC", list(LINK_TIERS))
    out.append("## Types, taken from OTI verbatim\n\n"
               "OTI's `organization_type` is adopted as-is -- no mapping, nothing "
               "guessed. Our own `Nonprofit` was renamed to OTI's `Nonprofit "
               "Organization` throughout, including rows OTI does not cover.\n\n"
               "⚠ `Nonprofit Organization` is deliberately absent from "
               "`/get/orgs/directory`'s type filter, so those rows exist without "
               "entering a directory of government.\n\n"
               "| type | orgs in the registry | of which imported |\n|---|---:|---:|")
    for r in types:
        out.append(f"| {r['type']} | {r['n']} | {r['imported']} |")
    out.append("")

    dn = await conn.fetch(
        "SELECT id, name, display_name FROM wegov_orgs "
        "WHERE display_name IS NOT NULL AND retired_at IS NULL ORDER BY display_name")
    out.append(f"## Displayed names -- {len(dn)}\n\n"
               "The site shows OTI's official name; `name` is unchanged, so every "
               "`/o/{id}-{slug}` URL stays byte-identical and the "
               "`contracts.agency` join keeps working.\n\n"
               "| id | shown (OTI) | stored `name` (URL + join key) |\n|---|---|---|")
    for r in dn:
        out.append(f"| `{r['id']}` | {r['display_name']} | {r['name']} |")
    out.append("")

    for title, where, cols, head, note in [
        ("Type disagreements", "type_disagrees",
         ("org_id", "nyc_record_id", "oti_name", "oti_organization_type",
          "our_type", "ours_name"),
         "| our id | OTI record | OTI name | OTI type | type that implies | our name |",
         "OTI's `organization_type` maps to a different `wegov_orgs.type` than the "
         "one we hold. Ours is unchanged."),
        ("Parent disagreements", "parent_disagrees",
         ("org_id", "oti_name", "reports_to", "ours_parent_name"),
         "| our id | OTI name | OTI reports_to | our parent |",
         "⚠ OTI's `reports_to` is free text that does not always match OTI's own "
         "`name` field, so some of these are source noise rather than a real "
         "disagreement."),
        ("Name disagreements", "name_disagrees",
         ("org_id", "nyc_record_id", "oti_name", "ours_name"),
         "| our id | OTI record | OTI name | our name |",
         "Mostly OTI's longer official forms (`New York City X` vs our `X`). "
         "Adopting a name changes URLs, so none were applied."),
    ]:
        rows = await conn.fetch(
            f"SELECT {', '.join(cols)} FROM nyc_org_enrichment "
            f"WHERE {where} AND origin = 'linked' ORDER BY oti_name")
        out.append(f"## {title} -- {len(rows)}\n\n{note}\n\n{head}\n"
                   f"|{'---|' * len(cols)}")
        for r in rows:
            cells = []
            for c in cols:
                v = r[c] or ""
                cells.append(f"`{v}`" if c in ("org_id", "nyc_record_id") else str(v))
            out.append("| " + " | ".join(cells) + " |")
        out.append("")

    print("\n".join(out))


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the changes (default is a dry run)")
    ap.add_argument("--report", action="store_true",
                    help="print the review markdown from nyc_org_enrichment and exit")
    args = ap.parse_args()

    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=dbcreds.password(),
        database=os.environ.get("POSTGRES_DB", "databook"),
    )
    try:
        if args.report:
            await report(conn)
            return

        async with aiohttp.ClientSession() as session:
            oti = await fetch_oti(session)
        print(f"[adopt] OTI orgs: {len(oti)}")
        if len(oti) < 250:
            raise RuntimeError(f"refusing to run: OTI returned only {len(oti)} rows")
        oti_by_id = {r["record_id"]: r for r in oti}

        mode = "APPLY" if args.apply else "DRY RUN (rolled back; pass --apply)"
        print(f"[adopt] mode: {mode}\n")

        # Everything runs inside ONE transaction, committed only with --apply.
        # A dry run therefore exercises the REAL code path -- schema included --
        # and reports exact counts, instead of guessing at what it would do.
        # (This works because asyncpg holds one session; the trap noted in
        # CLAUDE.md was `psql -c`, which autocommits so a later ROLLBACK lands
        # in a different session and does nothing.)
        plan = []
        tx = conn.transaction()
        await tx.start()
        try:
            for stmt in SCHEMA.strip().split(";"):
                if stmt.strip():
                    await conn.execute(stmt)
            plan.append("schema: nyc_record_id / retired_at / merged_into + "
                        "nyc_org_enrichment ready")

            # Order matters: create the orgs first, so the data fixes and the
            # parent wiring have something to point at.
            #
            # NOTE the phases below are passed `apply=True` unconditionally --
            # inside this transaction the writes are real, and the transaction
            # is what decides whether they survive. Passing the flag down would
            # mean the dry run measured a different code path than the one that
            # eventually runs.
            # Rejections FIRST: demoting a link frees that OTI record to be
            # imported as its own org on this same run.
            await apply_rejected_links(conn, plan, True)
            await import_missing(conn, oti, plan, True)
            await relink_imported_orgs(conn, plan, True)
            await apply_data_fixes(conn, oti_by_id, plan, True)
            await apply_type_renames(conn, plan, True)
            await apply_oti_types(conn, oti, plan, True)
            await apply_display_names(conn, oti, plan, True)
            kept_ours = await wire_parents(conn, oti, plan, True)
            await refresh_enrichment(conn, oti, plan, True, kept_ours)

            for line in plan:
                print(f"[adopt] {line}")
            await verify(conn, oti)

            if args.apply:
                await tx.commit()
                print("\n[adopt] COMMITTED")
            else:
                await tx.rollback()
                print("\n[adopt] ROLLED BACK -- nothing was written. "
                      "Re-run with --apply to keep it.")
        except Exception:
            await tx.rollback()
            print("\n[adopt] ROLLED BACK on error -- nothing was written.")
            raise

        print("\n[adopt] normalizer core is a SEPARATE store -- run "
              "sync_normalizer_org_core.py next, or the 10,005 dangling hex-id "
              "rows come straight back on the next ingest.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
