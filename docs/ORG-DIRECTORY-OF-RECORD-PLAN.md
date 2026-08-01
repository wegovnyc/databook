# Executable plan: give the org directory a system of record

**Status:** approved in outline 2026-07-30, nothing built. Every figure was
measured against production on that date; none is estimated. Phases are ordered
to be executed in sequence unless marked independent.

---

## What we are building toward

`wegov_orgs` in Postgres becomes the **register** — one row per organization,
keyed by id, editable, audited. The normalizer's `core_entities['orgs']` stays
the **matching dictionary** and is *derived* from the register instead of
hand-maintained. Airtable stops being an identity scheme. The org chart is built
from a real parent link and a real on-chart flag rather than from a string join
and a bucket.

## Ground truth (measured 2026-07-30)

| | |
|---|---:|
| live orgs in `wegov_orgs` | 1,238 |
| …with any parent at all | 360 |
| …whose parent resolves to nothing | **63** |
| …carrying a synthetic `airtable_id` minted during the OTI adoption | 137 |
| normalizer core entities | 545 |
| org match rows | 3,701 |
| …of which `manual` (human-curated) | **2,588** |
| distinct core names those rows reference | 530 |
| orgs that are also PASSPort vendors (strict match) | 25 |
| rows of type `Classification` / `Official` / `Public Figure` | **0** |

**The constraint every phase must respect:** removing a core entity orphans
every match row pointing at it. 2,588 of those rows are human work. No phase
below rewrites any of them.

---

## Phase 0 — close the normalizer admin exposure ✅ DONE 2026-07-30

**Shipped in #176.** Two things found during execution meant the planned control
would not have worked, so the record below is what was actually required.

⚠ **Cloudflare Access alone would NOT have closed this.** The origin answers
`Host: normalize.databook.nyc` on its **bare IP** — verified, HTTP 200 — so any
Cloudflare-layer policy is bypassable by anyone who knows the address, and the
address is in the private repo and in certificate-transparency logs. The control
has to live at the origin.

⚠ **The INTERNAL proxy path was reachable from the public internet.**
`curl -H 'Host: databook-nginx' http://<origin>/normalizer/datasets` returned
200 and 52 KB of dataset config, bypassing Cloudflare *and* the public vhost.
That path exists only for container-to-container traffic and had no restriction
at all. The plan did not anticipate this; it was found by testing the origin
directly rather than reasoning about the topology.

**What shipped:** basic auth on the public vhost, an allowlist restricting the
internal vhost to `172.19.0.0/16`, `/health` left open as a liveness probe, and
`prod-smoke.sh` moved onto `/health`. Credential via
`scripts/normalizer-auth-setup.sh` into `/etc/letsencrypt/normalizer.htpasswd`
— outside the git tree but inside a path already mounted into nginx, so no
compose change and no container recreate.

**Verified after reload:** external `/`, `/core/orgs`, `/admin/core/orgs`,
`/datasets` → **401**; direct-to-origin `:443` → **401**; direct-to-origin `:80`
with `Host: databook-nginx` → **403**; the api container → **200** on all
paths, including a live `aiohttp` round-trip on `/tasks`, `/queue`, `/logs`
using the same client the scheduler uses; `prod-smoke` all green.

**Still open, deliberately out of scope here:** the origin accepting direct
connections at all. That affects every site on the box, not just the
normalizer; restricting 80/443 to Cloudflare's ranges at the firewall is the
general fix and is too broad to bundle with this.

---

### Original plan, kept for the record

**Independent of everything else. Do this first regardless of the rest.**

`https://normalize.databook.nyc/admin/core/orgs` serves 983 KB to anyone, and
the write endpoints have **no authentication of any kind** — no `Depends()`, no
middleware, no nginx gate. Verified from outside the box:

```
/core/orgs         HTTP 200   660,731 bytes
/admin/core/orgs   HTTP 200   983,037 bytes
/datasets          HTTP 200    52,330 bytes
```

`POST /core/{name}/entity`, `DELETE /core/{name}/entity/{key}` and
`PUT /matches/{id}/{core}` are all reachable unauthenticated. Those endpoints
mutate the dictionary that stamps `wegov-org-id` onto every ingested table —
the same mechanism that put 10,005 unresolvable ids into 18 tables when it was
edited carelessly *by us*.

**Steps**
1. Check the normalizer's access logs for any *legitimate* external consumer
   before gating — the databook api uses the internal path, but a human may
   have bookmarked the admin, and anything else found should be inventoried,
   not broken silently.
2. Put a Cloudflare Access policy in front of `normalize.databook.nyc` — the
   whole host, not selected paths, since `/core/*` and `/matches/*` are as
   sensitive as `/admin/*`.
3. ⚠ Exempt nothing by path. The databook api reaches the normalizer over the
   **internal** Docker network (`NORMALIZER_BASE_URL=http://databook-nginx/normalizer`),
   so it does not traverse Cloudflare and is unaffected. Confirm that before
   enabling, then confirm again after.
4. Re-test the three URLs from outside; all should challenge.

**Verify:** `data_scheduler` still dispatches `/process/{id}/async` (watch one
sweep); the three URLs above no longer return 200 unauthenticated.

**Rollback:** disable the Access policy.

**Size:** small, and it is the highest risk-per-effort item in this document.

---

## Phase 1 — restore the lost chart scaffolding ✅ DONE 2026-07-31

**Shipped in #179.** `api/restore_org_chart_nodes.py`, idempotent, dry-run by
default. Outcome: **dangling parents 63 → 0**, directory (429) and all-orgs
(1,238) counts unchanged, 10 nodes restored, 3 children re-wired, 32 orgs moved
onto the flag, 35 rows snapshotted to `wegov_orgs_chart_restore_backup`.

⭐ **It also closed an item nobody had connected to it.** The five "core
entities whose numeric id resolves to nothing" — reported as open since the OTI
adoption — turned out to BE these lost nodes: `District Attorneys` 170020021
`Classification`, and `Chief of Staff` 170100017, `Chief Climate Officer`
170100240, `Chief Technology Officer` 170100034, `Deputy Mayor for Economic and
Workforce Development` 170100230, all `Official`. The core had preserved both
the id and the type the whole time. Restoring them with those ids took the
normalizer's dangling count to **0**, which also resolves **Phase 2's
pre-step** — that pre-step no longer exists.

**Two chart views (#180), Databook as default.** The static `orgChart.json`
is gone: it was manual, last written **2 March**, and written to a path inside
the `app` container that nginx never served and a rebuild destroyed.
`App\Custom\OrgChart` builds the tree per request instead, so the two views are
two filters over one payload.

| view | excludes | nodes |
|---|---|---:|
| **Databook** (default) | only what WE mark off-chart | **225** |
| NYC official | additionally what OTI marks off-chart | **212** |

⚠ This needed the two opinions SEPARATED: `wegov_orgs.in_org_chart` is ours
(32), `nyc_org_enrichment.in_org_chart` stays OTI's (161). The first pass wrote
both into one column, which made the second view impossible.

**Goal (original):** 63 dangling parents → 0, without inventing anything.

The org chart has two node kinds beyond organizations, and the code still knows
about both — `/get/orgs/chart` includes types `Classification` and `Official`,
`/get/orgs/all` excludes them — but **zero rows of either type exist.** They
were lost. The normalizer core still remembers two of them outright:

```
District Attorneys   -> id 170020021   type 'Classification'
Chief of Staff       -> id 170100017   type 'Official'
```

And **every missing parent's original Airtable id is recorded in its children's
`child_of`**, so restoration is exact and no child row needs editing.

| missing parent | original `airtable_id` | children | action |
|---|---|---:|---|
| Additional Mayoral Agencies (Not on Chart) | `recTZLn26klvFYOxj` | 32 | **flag, not a parent** — see below |
| Elected County Officials | `reckRTIpmsRKae8IU` | 6 | restore as `Classification` |
| Chief of Staff | `recIXPDD84xmPdV2s` | 5 | restore as `Official`, id 170100017 |
| Deputy Mayor for Strategic Policy Initiatives | `recdlyYOduxWVUWKh` | 5 | restore as `Official` |
| District Attorneys | `recTJbjZQCIIagGse` | 5 | restore as `Classification`, id 170020021 |
| The People of the City of New York | `rechr1BnnpiKGguXH` | 5 | restore as `Classification` |
| First Deputy Mayor | `recwvZRSkXdZ0hHzd` | 2 | **re-wire** — now org 170100307 |
| Chief Housing Officer | `recewLJXBWPvcKx4S` | 1 | restore as `Official` |
| Director of Communications | `recIQ8u44qEuQy6dZ` | 1 | restore as `Official` |
| Deputy Mayor for Operations | `recKWc8i7FSHUhikz` | 1 | **re-wire** — now org 170100303 |

### The "Not on Chart" bucket becomes a flag (decided)

Using it as a parent encodes "absent from the chart" as a *position in* the
chart. A flag says it properly — and NYC already publishes exactly that field.

**Measured corroboration:** of the 32 orgs parented to this bucket, **24 are
linked to an OTI record, and OTI reports `in_org_chart = false` for all 24 —
24 of 24 agreement — while giving none of them a `reports_to`.** The City's own
registry expresses this as a flag with no parent, which is the shape we are
moving to.

**Steps**
1. `ALTER TABLE wegov_orgs ADD COLUMN in_org_chart BOOLEAN` (nullable: unknown
   is a real state).
2. Backfill from `nyc_org_enrichment.in_org_chart` for the 306 registry orgs.
3. For the 32: set `in_org_chart = false`, clear `child_of`. The 8 not covered
   by OTI inherit our own categorization, which is what the bucket meant.
4. Restore the 6 scaffolding records with their original `airtable_id`, and
   their original id where the core remembers it. Type them `Classification`
   (a node that is not an organization) or `Official` (a person-role node) per
   the table above.
5. Re-wire the 3 children whose parent is now a real imported org.
6. Point `/get/orgs/chart` at `in_org_chart` where it is set, keeping the type
   filter for rows where it is NULL.

**Traps**
- ⚠ Restored records must **not** be typed into `DIRECTORY_TYPES`
  (`modules/orgfilter.py`) — `Classification` and `Official` belong in the chart
  and must stay out of `/get/orgs/directory` and `/get/orgs/all`.
- ⚠ They must not enter the matching dictionary either (Phase 2 excludes them).
  "District Attorneys" as a match target would swallow the five real DA offices.

**Side effect worth recording:** restoring `District Attorneys` (170020021) and
`Chief of Staff` (170100017) with their original ids also repairs **2 of the 5
core entities whose numeric id resolves to nothing** — and both ARE referenced
by curated match rows (ds 1 maps payroll's `District Attorney` to the former),
so this is not cosmetic. The remaining 3 are handled in Phase 2.

**Verify:** dangling parents = 0; `/get/orgs/directory` count unchanged;
`/get/orgs/all` count unchanged; org chart renders with ≥ today's node count.

**Rollback:** ⚠ step 3 **clears `child_of` on 32 rows — that is destructive**,
and "delete the 6 restored rows" does not undo it. Snapshot
`(id, child_of, child_of_name)` for the 32 into the backup dir first, per the
existing `/root/oti-*` practice. The restores themselves are plain inserts and
the flag column is additive.

**Size:** small. Mostly data, no new machinery.

---

## Phase 2 — derive the matching dictionary from the register ✅ DONE 2026-07-31

**Shipped in #182 (databook) + normalizer-py#13. Switched on prod the same
day: `POST /core/orgs/refresh` reloaded the dictionary 545 → 1,656 entities,
0 keys lost, 0 id changes except one deliberate fix (below).**

What was built, versus what was planned:

- `GET /get/orgs/core` (assembly in **`api/modules/orgcore.py`**, pure and
  unit-tested) emits the variants + retired-successor aliases + exclusions as
  planned. It returns a **bare JSON list** — every other endpoint wraps rows
  as `{"rows": ...}`, which the normalizer's `url:` loader would have read as
  two garbage records (its `_download_url` now also unwraps that envelope,
  belt and braces). `?report=1` returns the assembly diagnostics instead.
- **The union-in and the collision incumbents became one mechanism**: a
  Postgres table **`org_core_aliases`** (name → org_id, NULL = deliberate
  id-less stub), seeded by `api/seed_org_core_aliases.py` with **16 measured
  rows** — the 12 match-referenced names the register cannot derive (5 chart
  scaffolding names, 2 hand aliases, the UPPERCASE duplicate key, 4 id-less
  stubs) + the 4 collision incumbents (`District Council 37, AFSCME`,
  `Organization of Staff Analysts`, `SEIU Local 1199`, `United Federation of
  Teachers` — the only colliding variants today's core had resolved). The
  seed is HARDCODED and insert-only: a snapshot of human curation, reviewable
  in the diff, never clobbering a later table edit. Durable curation now goes
  in the register or this table — hand edits to the core do not survive a
  refresh.
- **Measured before the switch: today's core agreed with the derived feed on
  every single-org key — 0 id disagreements.** The one "change" shipped on
  purpose: `Hudson River Park Trust` was hand-typed as id `061546019`;
  `wegov_orgs.id` is the integer `61546019`. The zero form is stamped on 48
  ingested rows (crol 46, facilitydb 1, ds 328 1) and **joins to no org page
  today** — the org-section query compares id text equality. Their next
  ingest repairs them.
- The pre-flight lives in `seed_org_core_aliases.py --check`: all
  match-referenced core names (529 across 45 datasets) present in the feed,
  plus a feed floor (default 1,200) so a truncated feed is refused BEFORE the
  delete-and-reload, not discovered after.
- `sync_normalizer_org_core.py` reduced to its dataset-328 half as planned.
  ⚠ One behavioural fix found by the first prod dry run: the token-set
  similarity guard must be checked only on actual REWRITES — 12 legitimate
  order-inversion links (`Office of the Borough President of Queens` ↔
  `Queens Borough President`) score 0.48–0.65 forever, and holding an
  already-correct match every weekly run is noise that trains people to
  ignore holds.
- The 19 collision variants with no incumbent (`DC37`, `UFT`, `ATU`, …) are
  omitted and reported; none was a core key before, so nothing regressed.
- Observed during the switch, no action needed: OTI had *removed* a record
  (`NYC_GOID_000117`, `Mayor's Community Affairs Unit`) from the live feed
  while ds 328's ingested copy still carried it — the feed is Active-only, so
  records disappear as well as appear. The sync leaves such rows alone and
  the pre-flight still passed.

Verification (all on prod): every one of the 545 pre-switch keys survives
with its id; `NYC Districting Commission` → 170100330; both Cyber Command
spellings → 170100033; `Commission on Gender Equality` → 170011004; `DC37`
absent; a second refresh returned the identical 1,656. Snapshot for rollback:
`/root/org-core-switch-20260731-161536/` (core + ds-328 matches).

---

### Original plan, kept for the record

**Goal:** the core stops being a frozen hand-maintained snapshot.

`CORE_RECIPES["orgs"]` points at `file:data/core/orgs.json`, which exists
**nowhere** — not the repo, not the host, not the container — so
`POST /core/orgs/refresh` fails and the 545 entities can only be edited by hand.
`core_datasets.py:80` already implements a `url:` source, so this is one
endpoint plus one config line.

**Pre-step — resolve the 3 core entities whose id resolves to nothing.**
`Chief Climate Officer` → 170100240, `Chief Technology Officer` → 170100034 and
`Deputy Mayor for Economic and Workforce Development` → 170100230 name
`wegov_orgs` ids that do not exist, so they **cannot be derived from the
register**, and all three ARE referenced by match rows (6 rows, incl. `manual`:
ds 64/285 map MOCTO variants to `Chief Technology Officer`; ds 308 maps
`Deputy Mayor for Housing and Economic Development`). The pre-flight below
makes this unskippable — deliberately. For each: either remap the match rows to
a real org (likely right: MOCTO was folded into OTI in 2022; `Chief Climate
Officer` plausibly → Mayor's Office of Climate & Environmental Justice) or
create the org. Human curation either way; small.

**Steps**
1. Add `GET /get/orgs/core` to the databook api, emitting **one row per NAME
   VARIANT, not per org**: for each live org, its `name`, plus its
   `alternate_name`, plus its `display_name` — each a separate row carrying the
   same `id` and `name`. Rows can be slim: the recipe's `output_fields` are
   `wegov-org-name` + `wegov-org-id` only (`core_datasets.py:213`) — the 40
   fields in today's entities are ballast used only by the admin UI display.
2. **Also emit each RETIRED org's name as an alias of its `merged_into`
   successor.** The core today holds `Commission on Gender Equality` →
   170011004 precisely so data still arriving under the old name resolves; a
   live-orgs-only feed silently drops that on first refresh.
3. Exclude `Classification`, `Official`, `Public Figure` from the general
   emission (see Phase 1 traps) — the union-in below still carries the
   specific scaffolding names that curated match rows reference.
4. **Union in every name currently referenced by a match row**, whatever its
   type or retirement state. This is the safety net, not an optimisation.
5. Run the pre-flight check below. Only then repoint the recipe to
   `url:https://api.databook.nyc/get/orgs/core`.
6. Reduce `sync_normalizer_org_core.py` to its dataset-328 half.

**Collision policy — required, not optional.** Measured: **23 variant strings
map to more than one org**, worst case `DC37`, an `alternate_name` shared by
**19** distinct bargaining units (they are legitimately distinct — the known
DC 37 ×19 name collisions). The core is keyed by name, so a naive feed emits 19
rows with the same key and last-write-wins picks an arbitrary local — and the
auto-matcher would then link every payroll `DC37` to it. Policy:

> a variant that maps to >1 org is emitted ONLY if today's core already
> resolved that exact key — in which case keep the incumbent id (preserve
> curation, never re-roll it) — otherwise emit nothing for that key and list it
> in the endpoint's `collisions` report field.

**Pre-flight check — must gate the switch, and belongs in CI afterwards**

> every distinct `matches.core_text` where `core_dataset = 'orgs'` (530 values,
> less the `__SKIP__` sentinel) must appear in the endpoint's output

**Traps**
- ⚠ **If the endpoint emits one row per org, the first refresh deletes the alias
  entities** and the Districting Commission regresses to unmapped across the 12
  datasets that map it by hand. Five ids are deliberately claimed by two
  entities each (`NYC Cyber Command` + `Cyber Command` → 170100033); that is the
  dictionary working correctly and must survive.
- ⚠ A refresh is a delete-and-reload. Nothing in the core is curated-flagged, so
  anything a human typed there and did not put in Postgres is lost on first
  refresh. Snapshot `/core/orgs` before the switch.
- Scope note: feeding all 1,238 live orgs is *consistent with today*, not an
  expansion of kind — the current 545 already spans Unions (21), Bargaining
  Units (29), BIDs (11) and political organizations, so no type is newly
  admitted to matching. The growth is in coverage, and `save_matches` never
  lets `auto` overwrite `manual`. Re-read `/pipeline/unmapped` after the first
  post-switch sweep all the same.

**Verify:** refresh returns ≥545 entities; pre-flight passes with zero missing;
`/pipeline/unmapped` unchanged after a full sweep; `NYC Districting Commission`
still resolves to 170100330.

**Rollback:** repoint the recipe to `file:` and restore the snapshot via
`POST /core/orgs/entity`.

**Size:** small.

---

## Phase 3 — parent links stop going through Airtable ids ✅ DONE 2026-07-31

**Shipped in #185 (+ two follow-up fixes on main). Live on prod: 338 parent
edges migrated to `parent_org_id`, checksum byte-identical to the legacy
resolution, chart and profile render unchanged, three dead columns dropped.**

⚠⚠ **`wegov_orgs` HAD NO PRIMARY KEY.** Postgres refused the FK outright —
*"there is no unique constraint matching given keys for referenced table"* —
and the transaction rolled back cleanly. Measured: **zero** rows in
`pg_constraint` for this table (no PK, no unique constraint, no checks), with
`id` a **nullable** integer carrying only a plain non-unique btree index. So for
the entire life of the directory nothing prevented two orgs sharing an id, or an
org having no id at all. They happen to be clean (1,250 rows / 1,250 non-null /
1,250 distinct) — luck, not design, because the table is `source_type='internal'`
and was created outside any migration. `add_parent_org_id.py` now declares
`PRIMARY KEY (id)` first, after proving the data can carry one.

**Three live bugs fixed, each measured before the change:**
1. ⭐ **Both MCP org tools reported every organization as parentless** — they
   selected `parent_name` off the table, a **0-of-1,250-populated** dead column
   shadowed by a computed alias of the same name in `main.py`'s profile query.
   The website showed a parent; MCP showed none, for as long as the tools have
   existed. ⚠ **And it had a SECOND layer**: `get_organization_profile` also
   never *rendered* the parent it selected, so fixing the query alone changed
   nothing. Found only by calling the tool on prod after deploying the first
   fix. **Selecting a value proves nothing about surfacing it** — the guard now
   asserts both tools render it.
2. `chatbot.py` rendered `child_of` raw: `**Parent**: ["recIXPDD84xmPdV2s"]`.
3. `ChartUpdateJson.php` resolved parents through `child_of`, was on no
   schedule, and wrote to a path inside the `app` container nginx never serves.
   Deleted — `App\Custom\OrgChart` had already replaced it.

**Design notes worth keeping:**
- `modules/orgfilter.py` owns resolution (`parent_join`, `parent_id_projection`),
  probed and cached like `retired_at`/`in_org_chart`. The API guarantees a
  `parent_org_id` key on every chart row either way, so the **PHP builder has
  one code path** — a conditional there is invisible to `php -l` and only a
  rendered page would catch it.
- **Two migration steps, order load-bearing.** `--apply` is additive and safe
  before deploy; `--drop-dead-columns` is destructive and must follow it,
  because the *old* `mcp_server.py` selected `parent_name` off the table. It
  refuses to drop a column that turns out to hold data, and refuses to backfill
  if any `child_of` would not resolve.
- Deploying the code **before** the column existed was deliberate and proved
  the fallback path renders identically (151/144 chart links, unchanged).
- ⚠ `child_of`/`child_of_name` are **retained one release** as provenance and
  rollback; writers keep both in step and the weekly post-check now measures
  **drift** between them rather than dangling parents. Verified: a full weekly
  run reported `parent drift: 0` and `123 already agreed, 0 REPLACED` — i.e.
  the "already correct" comparison keys on the FK, so it does not rewrite 123
  rows every week.
- ⚠ A scalar FK inherits the **one-parent-only** limit. Borough Boards
  genuinely reports to all five Borough Presidents; OTI's multi-parent rows
  were already truncated. Recorded, not fixed — that needs a join table.

**Remaining for Phase 6:** drop `child_of`/`child_of_name` and decide whether
`airtable_id` stays as provenance.

---

### Original plan, kept for the record

**Goal:** a dangling parent becomes structurally impossible.

`child_of` holds an Airtable `rec…` id, joined on `airtable_id` by string
equality after stripping brackets (`main.py:331`). That is why 63 dangled, and
why the adoption had to mint 137 synthetic `recOTI…`/`recEXTRA…` ids: `child_of`
has no other way to reference a new org.

**Steps**
1. `ALTER TABLE wegov_orgs ADD COLUMN parent_org_id INTEGER REFERENCES
   wegov_orgs(id)`.
2. Backfill from the existing `child_of` → `airtable_id` join. After Phase 1
   this resolves for every populated `child_of`.
3. Migrate the two readers: the profile query (`main.py:330-331`) and
   `app/app/Console/Commands/ChartUpdateJson.php`.
4. Drop or populate the dead `parent_id` / `parent_name` / `parent_type`
   columns — they are **0% populated** today and shadowed by aliases of the same
   name computed in the profile query, so `org.parent_id` is NULL from the table
   and non-NULL from the API. That should not survive the phase.
5. Stop writing `child_of`; keep it as provenance for one release, then drop.

**Traps**
- ⚠ The FK is scalar, so it inherits today's **one parent only** limit — which
  is why OTI's 5 multi-parent records were truncated to their first parent
  during the adoption. Borough Boards genuinely reports to all five Borough
  Presidents. If that matters, it needs a join table; I would note it and not
  build it now.
- ⚠ `adopt_nyc_orgs.py::wire_parents` writes `child_of`; it must switch in the
  same change or the next adoption run reintroduces the string form.

**Verify:** FK guarantees no dangling; chart node count ≥ today's; org profile
parent renders identically for a sample across all node kinds.

**Rollback:** `child_of` is retained through the phase; revert the readers.

**Size:** medium — mechanical, but it touches the chart builder.

---

## Phase 4 — schedule the adoption

**Goal:** the directory stops drifting from a maintained daily source.

None of `build_nyc_org_crosswalk.py`, `adopt_nyc_orgs.py`, or
`sync_normalizer_org_core.py` is scheduled — all three ran once, by hand. All
are idempotent and dry-run-by-default (a re-run today reports `0 to create /
repointed 0 / nothing to do`), and a crosswalk rebuild cannot disturb the
adoption because imported and rejected rows are `curated = true`.

**Split in two, because half of it need not wait.** The dependency on Phase 2
applies only to `sync_normalizer_org_core.py` (it writes core entities
directly, and those writes become transient once the core is derived). The
crosswalk and the adoption write **Postgres only** and are idempotent — nothing
stops them being scheduled today.

### ✅ Phase 4a DONE 2026-07-31 (#181)

`scripts/org-registry-refresh.sh`, cron **Sun 04:00 UTC**, crontab backed up to
`/home/ubuntu/crontab.before-org-registry.bak`. Verified idempotent across three
runs and under a minimal `env -i` cron environment.

⚠ **Two hazards had to be fixed before it was safe unattended:**
1. The crosswalk rebuild `DELETE`d every non-curated row with **no row-count
   guard and no transaction** — a short Socrata response would have replaced the
   crosswalk with nothing. Socrata does return 200 with a truncated body under
   load (#117). Now refuses below 250 orgs, transactional, and the guard was
   tested by forcing it to trip.
2. `REJECTED_LINKS` was keyed on `nyc_record_id` alone, so a rejection rejected
   EVERY row for that record — including the `imported` link to the org created
   FOR it. The first run cut `Community Services Board` off from its own OTI
   record and coverage fell 306 → 305. Now keyed on the pair, with
   `relink_imported_orgs()` to repair and a verify-block invariant.

**The post-checks caught (2)** — the run reported `links 306 -> 305`. Exit 0
would have said nothing, which is why the script measures outcomes.

⚠ **`HC_URL_ORG_REGISTRY` is still unset**, so missed-run detection is not live;
Sentry covers "ran and failed". The healthchecks.io API key is **no longer on
the box**, which also blocks managing the other five checks.

**Phase 4a — schedule now, independent of everything:**
1. A `scripts/org-registry-refresh.sh` following `dos-crosswalk-refresh.sh`:
   crosswalk → adopt `--apply`, with a healthchecks.io check and `tail`-of-log
   in the ping body.
2. Weekly. The content is stable; daily buys nothing.
3. Fail the run if OTI returns < 250 records (already guarded in the script).

### ✅ Phase 4b DONE 2026-07-31 (#182, same PR as Phase 2)

`org-registry-refresh.sh` gained steps 3–5: ds-328 sync → **pre-flight** →
`POST /core/orgs/refresh` + measured post-checks (entity floor 1,200, and the
two canary keys: the Districting hand-alias and the Cyber Command
two-keys-one-id pair). ⚠ **The order is load-bearing**: the sync writes match
rows whose core_text is the register name; the pre-flight then checks EVERY
match row — including the just-written ones — against the feed; only then is
the dictionary reloaded. A failed pre-flight refuses the refresh and keeps
the previous dictionary, which is the safe state. Validated end-to-end with a
manual run on the switch day.

**Phase 4b — original: after Phase 2**, append to the same script: the
reduced ds-328 sync, then `POST /core/orgs/refresh` so the dictionary picks
up whatever the adoption changed.

**Traps**
- ⚠ **`rowsUpdatedAt` is not a usable change signal for `t3jq-9nkf`.** It moved
  to 2026-07-30 20:15 UTC — after the adoption ran — while a field-by-field diff
  of all 306 records showed **zero** changes. OTI republishes daily as a no-op.
  Do not gate on it; just run and let idempotency absorb it.
- ⚠ Between Phases 4a and 4b there is a window where the adoption can import an
  org the frozen core does not know. That is today's status quo, not a
  regression — but it is why 4b exists.

**Verify:** two consecutive scheduled runs report no changes; healthchecks shows
both.

**Size:** small.

---

## Phase 5 — the editing surface ✅ DONE 2026-07-31 (#186 API, #187 UI)

**Both halves shipped and live. `api/routers/org_admin.py` + the UI at
`/admin/orgs`. THE PLAN IS COMPLETE.**

**The UI is a pure consumer** (`app/app/Http/Controllers/OrgAdmin.php`,
`app/resources/views/admin/orgs/`). No invariant is re-implemented there: two
copies of a rule can disagree, and the API's copy is the one that also governs
curl and bulk scripts. When the API answers 409, the page renders the server's
reasoning *and the live contract count* and offers the confirmation — it does
not decide for itself whether a rename is safe. Verified end-to-end on prod
through the Laravel proxy: a `display_name` edit applied, an unconfirmed rename
came back 409 with its `why` and `impact` intact, and both edits landed in the
audit trail attributed to **devin**.

⚠⚠ **THE GATE IS THE LOAD-BEARING PART.** The Laravel app has **no user
system** — everything under `/about/*` is public by design, and there is no
session, guard or middleware to hang an editor role on. Without a gate,
`/admin/orgs` is an **unauthenticated write surface onto the register** — the
exact exposure Phase 0 found on the normalizer. So `/admin/` is gated by
**nginx basic auth at the origin** (`scripts/org-admin-auth-setup.sh`, htpasswd
outside the git tree in a path already mounted into nginx). Origin, not
Cloudflare, for the Phase 0 reason: the origin answers direct connections
(`dda13bf3`). A test pins the nginx block and was verified by **deleting it and
watching the test fail**.

⚠ **The API credential never reaches the browser.** It is a long-lived
write-scoped bearer token already in the app's `.env` (which is also how the
pre-existing write endpoints are reachable at all — see `e235ba85`), so the page
posts to Laravel and Laravel calls the API. `DatabookAPI::adminReq()` returns the
**status** as well as the body, unlike `req()`, which collapses everything to
`false` and would turn every deliberate refusal into a generic failure. A test
asserts no view references the key, a key header, or the API host.

Verified by **rendering**, not lint — `php -l` cannot validate Blade. Both pages
render (1,238 orgs listed; the edit form's three selects all preselected from
stored values), 0 exceptions, and the public chart / org profile / about pages
are unaffected by the shared-vhost change.

Endpoints under `/admin/orgs`: `GET /vocabulary`, `GET /{id}` (record + parent +
audit + rename impact), `POST` create, `PATCH /{id}`, `POST /{id}/retire`,
`POST /{id}/unretire`, and `DELETE /{id}` answering **405 with an explanation**.

The five invariants as built, each traceable to a failure in this repo:

| invariant | why |
|---|---|
| `type` ∈ the `orgfilter` vocabulary | free text broke 4 filters (#173) and rendered 28 of 270 agencies (#177) — silently, both times |
| renaming `name` needs `confirm_rename`, and the 409 quotes the blast radius | it is a join key into `contracts.agency`; a rename zeroes that profile's procurement figures. `display_name` is the free field |
| a parent may not be self, retired, or cyclic | `OrgChart::packnode` recurses with **no depth guard** — a cycle 500s the whole chart rather than looking wrong |
| retirement, never deletion; `merged_into` required; `unretire` exists | 3,700 match rows + every ingested `wegov-org-id` must keep resolving, and reversibility is only real if it is reachable |
| unknown fields are a 400 | silently dropping a field is how this codebase shipped changes that "succeeded" and did nothing |

⚠ **Types present in the data stay selectable.** A validator that rejected the
~930 Unions / Political Clubs / BIDs it is editing would be worse than none —
you could not save an existing row without retyping it.

⚠⚠ **THE PLAN'S AUTH LINE WAS WRONG.** It said "Cloudflare Access from Phase 0
covers it." Phase 0 put **nginx basic auth on the NORMALIZER's vhost** — a
different host — and task `dda13bf3` records that the origin answers direct
connections, so a Cloudflare-layer policy is bypassable regardless. These routes
therefore carry their own origin-level control: a valid JWT whose `users` row has
an editor `scope`, or the internal `api_key` for scripted use. Phase 0's real
lesson stands — the control must live at the origin, and application auth is at
the origin.

⚠ `Security(manager, scopes=['write'])` is deliberately NOT used, despite four
other endpoints using it: **`/login` mints `scopes=['read']` hardcoded**, so no
token it issues can satisfy a write-scoped dependency, and those four endpoints
are effectively unreachable by any human login. Authorising on the user row's
`scope` works today and widens nothing. Separate finding, filed as Hub
`e235ba85` — deliberately NOT fixed here, because granting scopes from
`users.scope` would make `delete_dataset_in_database` reachable with a login
token as a side effect of an unrelated phase.

**Not deployed yet** — these are write endpoints, so exposure waits on review or
on the UI landing.

**What remains:** the UI (a consumer of the above; copy the normalizer's
`core_detail.html` pattern — 478 lines of vanilla JS on the same no-build-step
stack), plus deciding where it is mounted and how the human authenticates to it.

---

### Original plan, kept for the record

## Phase 5 — the editing surface

**Goal:** the register becomes editable by a human, which it has never been.

This is the only substantial build, and it is late on purpose: written earlier
it would encode the model Phases 1–3 remove.

**Copy what already works.** The normalizer's `core_detail.html` is 478 lines of
vanilla JS on the same no-build-step stack — searchable list, per-entity field
panel, save/delete against JSON endpoints. Differences for a register:

- keyed by **id**, one row per org, so renaming is safe;
- a **parent picker** writing `parent_org_id`, and an `in_org_chart` toggle;
- `type` constrained to the vocabulary in `modules/orgfilter.py` — free text is
  precisely how a mixed vocabulary silently broke four filters in #173;
- `display_name` freely editable; **`name` edited behind a warning**, because it
  is a join key into `contracts.agency` (`oce.py::_resolve_org_id`, and the org
  page passes it to `/oce/agency/summary?name=`). Renaming it silently zeroes
  the procurement figures on that profile. The editor must surface this, not
  hide it;
- an audit trail — no store has one today.

**Auth:** Cloudflare Access from Phase 0 covers it. Revisit per-user accounts
only if more than a couple of people edit.

**Build API-first, UI second.** Ship the CRUD endpoints
(`POST/PUT/DELETE /admin/orgs/...`) with tests as their own PR, then the UI as
a pure consumer of them. The endpoints are where the invariants live — type
vocabulary, rename warning, audit write, retirement-not-deletion — and they
must hold for *any* client, not just the screen. It also means the audit trail
and a scripted bulk edit exist before a single pixel does.

**Verify:** create, rename, re-parent and retire a throwaway org end to end;
confirm a rename does not change its `/o/{id}-{slug}` URL or its procurement
figures; confirm the next `POST /core/orgs/refresh` reflects the edits.

**Size:** the real work.

---

## Phase 6 — retire Airtable ✅ DONE 2026-07-31

**Shipped with Phase 5's API half. `api/retire_airtable.py` snapshots every
row's `(id, name, airtable_id, child_of, child_of_name, parent_org_id)` into
`wegov_orgs_airtable_provenance`, then drops `child_of` / `child_of_name`.**

What Phase 6 actually was: Airtable had left the read path long ago, but
survived as an **identity scheme** — `child_of` stored an Airtable `rec…` id as
TEXT and was how one org referenced another, so every NEW org had to be minted a
synthetic `airtable_id` (**140 of 1,250 rows**: `recOTI…`, `recEXTRA…`,
`recNODE…`, `recEDIT…`) purely to be referenceable. Phase 3 replaced the
reference with an FK; this removed the scheme. `airtable_id` remains, meaning
only what it says: provenance for the **1,110** rows that really came from
Airtable.

⚠ **Why a snapshot rather than just a DROP.** `child_of` was Phase 3's rollback
path, and Phase 3 shipped *hours* — not a release — earlier. Keeping it live
would mean a decaying duplicate every writer must remember to update; deleting it
outright would destroy the provenance. So it moves to a table, insert-only, and
the drop is refused if the snapshot comes back short.

**Hard gates before dropping:** the primary key and the parent FK must both
exist, and **no row may have a `child_of` that disagrees with `parent_org_id`** —
a `child_of` that still knew something the FK did not would be destroyed here, so
it aborts and names the rows.

**Writers stopped writing both.** `adopt_nyc_orgs.py`,
`restore_org_chart_nodes.py` and the Phase 5 editor no longer set `child_of` or
mint synthetic ids. Two consequences worth naming:
- ⚠ `adopt_nyc_orgs`'s parent lookups **required** an `airtable_id` (because a
  parent was written as `child_of = [airtable_id]`), which would have silently
  excluded every org created through the editor. Removed.
- ⚠ `restore_org_chart_nodes`'s finder queries now read the **provenance table**.
  Left alone they would raise `UndefinedColumnError` — a script that reads as
  active and cannot run, the exact pattern this codebase keeps paying for.

**The weekly invariant changed with the schema.** `child_of` drift is gone, so
the post-check now measures what the FK does *not* give us: a live org whose
parent **exists but is retired**, which drops its whole branch off the chart
(measured in Phase 1 — one such node cost 135 of 256 nodes). Prod: **0**.

---

### Original plan, kept for the record

Airtable is already out of the read path; nothing loads from it and the
directory is near-static (almost everything last touched 2021-22, 26 records in
2024-06, nothing since). Once Phase 3 lands, `airtable_id` stops being how orgs
reference each other and can be kept as provenance or dropped. **Blocked until
then** — it is load-bearing for both the parent join and the chart builder.

**Size:** trivial, once unblocked.

---

## Track B — org ↔ vendor crosswalk ✅ DONE 2026-07-31 (#188)

**Shipped and live. `api/build_org_vendor_crosswalk.py` → `org_vendor_crosswalk`,
surfaced on both profiles.** Measured on prod: **53 of 1,238 live orgs link to a
PASSPort vendor and 29 hold at least one City contract** — Chinese-American
Planning Council (192 contracts / $101.8M), Central Park Conservancy ($248.8M),
Catskill Watershed ($54.2M), Carnegie Hall, Prospect Park Alliance.

| tier | rows | links |
|---|---:|---|
| `exact` | 25 | ✅ |
| `exact-suffix` | 24 | ✅ |
| `fuzzy` | 3 | ✅ |
| `curated` | 1 | ✅ |
| `suffix-review` / `fuzzy-review` | 19 | ⏸ held |

⚠ **An unreviewed candidate never enters the link column.** It sits in
`candidate_supplier_id` with `passport_supplier_id` NULL, so a join on the link
column *cannot* publish it — the #146 lesson made structural rather than left to
every consumer to remember.

**Audited the auto-links before applying.** All 3 fuzzy links are right
(`MoMA PS1` → P.S. 1 Contemporary Art Center; an *of/for* difference; a vendor
name with a typo'd space). Of the 19 held, ~6 look right — so auto-linking that
tier would have published ~13 false claims that an org holds City contracts.
Queue and how to record a decision: `docs/org-vendor-crosswalk-review.md`;
decisions live in the version-controlled `api/seed/org_vendor_curated.csv`
(the NYCHA equivalent exists only on the box).

⚠ **Two claims I published and then corrected**, both found by testing rather
than reasoning:
1. `Carnegie Hall` → `THE CARNEGIE HALL CORPORATION` does **not** match
   automatically. The imported suffix list strips `CORP` but **not**
   `CORPORATION`. Measured across every skipped org, it is the *only* legitimate
   match affected, so it is a curated row — widening the list would collapse
   `X Trust`, `X Fund` and `X Association` onto `X` and invent collisions.
2. The `Mercury` → `MERCURY ENTERPRISES INC` example for the single-token rule
   was wrong (that pair does not collide under the real list). The genuine save
   is `The Nation` → `NATION GROUP INC`, where both reduce to `NATION`.
   The example came from my own measurement script, which used a **wider** suffix
   list than the code — a reminder that a measurement harness must share the
   code's definitions or it measures a different system.

⚠ **A vendor may legitimately be several orgs.** `United Federation of Teachers`
is three register rows (the union plus two bargaining units), all supplier
1713785 — so the vendor page renders a **list** ("Civic Records"), verified
rendering all three with their correct types.

⚠ Surfacing is `GET /oce/org/vendor-activity`, deliberately its **own** endpoint:
joining this onto `/get/orgs/profile/{id}` would put the Greenbook enrichment
behind the same try/except and silently strip agency heads from every org page if
the table were missing. Contracts are counted by `vendor_name` **exact** equality
— the same predicate `get_vendor` uses — or the two pages would disagree with no
way to tell which was right.

⚠ Found by rendering: the vendor block was first inserted **inside**
`@if(!empty($nycha))`, so it only appeared for vendors that also had NYCHA
activity. The nav link rendered, which made it look half-working. `php -l` passes
either way — rendering is the test.

Auto-refreshes via `POST_INGEST_HOOKS["vendors"]`, guarded end to end.

---

### Original scope decision, kept for the record

## Track B — org ↔ vendor crosswalk (independent, any time)

**Scope decision: vendors are not merged into the directory.** Measured: **25 of
1,238 orgs** are also PASSPort vendors — 2% of the directory, 0.07% of the
36,357 vendors — and they fall exactly where expected (11 Nonprofit
Organization, 3 Public Benefit, 3 BID, 3 Political Consultants). Merging would
swamp a curated 1,238-row directory 30:1 for a 2% overlap, across two different
identity schemes and editorial standards.

**What the directory is for.** It is already not government-only: 186 Unions,
137 Political Clubs, 76 BIDs, 75 Political Consultants, 21 Publications. The
working definition is *civic actors in NYC governance* — bodies that shape,
contest, or deliver city government. Under it, vendors **as a class** do not
belong (a firm selling office furniture is not a civic actor), while the vendors
that *are* civic actors — service-delivery nonprofits, BIDs, cultural
institutions — already belong and are already there. The 25 overlaps are the
intersection working, not a scoping error.

**Build:** `org_vendor_crosswalk`, same shape as `nycha_vendor_crosswalk` and
the Doing Business one — tiered (`exact` / `fuzzy` / `fuzzy-review` /
`curated` / `rejected`), curated rows never overwritten, rebuild deletes
non-curated first (#149). Then an org profile can show "holds City contracts"
and a vendor profile can link back to the civic record. 25 is a floor; the NYCHA
experience says fuzzy adds meaningfully at the cost of needing review.

---

## Still blocked on NYC

12 dangling parents name real offices neither we nor OTI hold (`Chief of Staff`
5 — restored as a node in Phase 1 but not as an organization,
`Deputy Mayor for Strategic Policy Initiatives` 5, `Director of Communications`
1, `Chief Housing Officer` 1). See
`docs/open-data-agency-registry-reports-to-report.md`. Phase 1 restores them as
chart nodes, which resolves the *structural* problem; whether they are
organizations in their own right is NYC's answer to give.

## Standing invariants — the definition of done

Each phase has its own verification, but verification that runs once is how
this system got here — *a check reporting zero problems is indistinguishable
from a check that never ran*. These become CI tests (where they need only the
seed/code) or a daily assertion in `dataset-staleness.sh` (where they need
prod data), and they are the durable deliverable:

| invariant | held by | from |
|---|---|---|
| no org's parent references a nonexistent org | FK `wegov_orgs_parent_fk`, structural | ✅ Phase 3 |
| `wegov_orgs.id` is unique and NOT NULL | PK `wegov_orgs_pkey`, structural | ✅ Phase 3 |
| `child_of` never disagrees with `parent_org_id` | weekly post-check (drift) | ✅ Phase 3 |
| every `matches.core_text` (orgs) appears in `/get/orgs/core` | weekly pre-flight (`seed_org_core_aliases.py --check`, gates the refresh) + CI unit tests on the assembly | ✅ Phase 2 |
| `POST /core/orgs/refresh` succeeds and entity count ≥ match-referenced count | scheduled run (floor 1,200 + canary keys) | ✅ Phase 4b |
| no `wegov_orgs.type` outside the vocabulary in `modules/orgfilter.py` | CI (exists, extend) | Phase 1 |
| `/get/orgs/directory` and `/get/orgs/all` counts within an expected band | daily assertion | Phase 1 |
| re-running the adoption on unchanged OTI data is a no-op | scheduled run output | Phase 4a |
| retired orgs appear in no serving endpoint | CI | done (#172) |

## Order

**~~0~~ → ~~1~~ → ~~4a~~ → ~~2~~ → ~~3~~ → ~~4b~~ → ~~5~~ → ~~6~~ → ~~Track B~~
— EVERYTHING IN THIS PLAN IS SHIPPED.**
0 (#176) · 1 (#179/#180) · 4a (#181) · 2 + 4b (#182 + normalizer-py#13) ·
3 (#185) · 5 API + 6 (#186) · 5 UI (#187).

**What the register has now that it had none of on 2026-07-30:** a declared
primary key, an FK parent that makes a dangling reference impossible, a matching
dictionary derived from it rather than hand-maintained, a weekly refresh with
measured post-checks, a CRUD path with five enforced invariants, an audit trail,
and an editing UI behind an origin-level gate. Airtable is no longer an identity
scheme.

**The register now has what it never had**: a declared primary key, an FK
parent, a derived matching dictionary, a CRUD path with enforced invariants, and
an audit trail.

Phase 0 first because the exposure is live and unrelated to the rest. 4a comes
forward because it is pure insurance and waits on nothing. Phases 1–3 are each
small-to-medium, independently verifiable, and each leaves the system better
than it found it. Phase 5 is the only one that should wait for a settled model.
