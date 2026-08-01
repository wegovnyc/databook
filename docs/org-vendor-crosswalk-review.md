# Org ↔ vendor crosswalk — review queue

**Generated 2026-07-31 from `org_vendor_crosswalk` (Track B,
`api/build_org_vendor_crosswalk.py`).** Regenerate the figures with
`docker compose exec -T api python build_org_vendor_crosswalk.py --show`.

## Where things stand

| tier | rows | links? |
|---|---:|---|
| `exact` | 25 | ✅ |
| `exact-suffix` | 24 | ✅ |
| `fuzzy` | 3 | ✅ |
| `curated` | 1 | ✅ |
| `suffix-review` | 2 | ⏸ held |
| `fuzzy-review` | 17 | ⏸ held |
| **linked** | **53** | |

**52 of 1,238 live orgs are linked to a PASSPort vendor, and 29 of them hold at
least one City contract** — Chinese-American Planning Council (192 contracts /
$101.8M), Central Park Conservancy ($248.8M), Catskill Watershed ($54.2M),
Carnegie Hall, Brooklyn Children's Museum, Prospect Park Alliance.

⏸ **Held rows do NOT link.** Their id sits in `candidate_supplier_id` with
`passport_supplier_id` NULL, so no serving query can publish them. Nothing below
is live; reviewing it only *adds* links.

## What needs a human — 19 rows

Approving one is a line in the curated CSV; so is rejecting it, and a rejection
sticks (it never returns to this queue). My reading is in the last column and is
**a suggestion, not a decision** — several are genuinely ambiguous.

| org id | org | candidate vendor | score | looks |
|---|---|---|---:|---|
| 170019006 | NYC & Company | NEW YORK CITY TOURISM AND CONVENTIONS INC | 0.943 | ✅ **right** — renamed 2023; `display_name` already carries the new name |
| 170100334 | New York City School Bus Umbrella Services, Inc. | NYC SCHOOL BUS UMBRELLA SERVICES INC | 0.865 | ✅ **right** — NYC/New York City only |
| 170020072 | NYS Unified Court System OCA | State of New York (Unified Court System, Office of Court Administration) | 0.871 | ✅ **right** — same body, parenthesised |
| 170100081 | Fulton Mall Improvement Association | FULTON MALL IMP ASSOCIATION | 0.871 | ✅ **right** — `IMP` = Improvement |
| 170013214 | New York Communities for Change | NEW YORK CITY COMMUNITIES FOR CHANGE | 0.925 | ⚠ **probably right** — one stray "CITY"; confirm it is not a distinct affiliate |
| 170013103 | El Diario | EL DIARIO LLC | 1.000 | ⚠ **probably right** — held only because the key is one token |
| 170013323 | The Nation | NATION GROUP INC | 1.000 | ❌ **probably wrong** — the magazine vs a firm called Nation Group |
| 170010998 | Economic Development Corporation | QUEENS ECONOMIC DEVELOPMENT CORPORATION | 0.901 | ❌ **wrong** — NYCEDC ≠ Queens EDC |
| 170019025 | Empire State Development Corporation | Empire State Certified Development Corporation | 0.878 | ❌ **wrong** — different bodies |
| 170013219 | New York State Nurses Association | NEW YORK STATE DEFENDERS ASSOCIATION INC | 0.870 | ❌ **wrong** — Nurses vs Defenders |
| 170011044 | New York City Water Board | NEW YORK CITY WATER WORKS LLC | 0.880 | ❌ **wrong** — Board vs an LLC |
| 170100297 | Convention Center Development Corporation | THE HOPE CENTER DEVELOPMENT CORPORATION | 0.868 | ❌ **wrong** |
| 170100319 | Land Development Corporation | MDB DEVELOPMENT CORPORATION | 0.909 | ❌ **wrong** |
| 170100152 | 4C Partners | GC PARTNERS LLC | 0.909 | ❌ **wrong** — one character apart, different firms |
| 170013120 | Gmi Software Inc | GT SOFTWARE INC | 0.870 | ❌ **wrong** |
| 170100092 | Lincoln Square | 16 LINCOLN SQUARE LLC | 0.903 | ❌ **wrong** — the BID vs an address-named LLC |
| 170100061 | Madison Avenue | J & C Madison Avenue Corp | 0.875 | ❌ **wrong** — the BID vs a firm |
| 170100134 | RJF Communications | J&L Communications | 0.889 | ❌ **wrong** |
| 170013378 | World Trade Federation | WORLD ROMA FEDERATION INC | 0.884 | ❌ **wrong** |

**Roughly 6 of 19 look right.** That ratio is the argument for the gate: auto-
linking this tier would have published about thirteen wrong claims that an org
holds City contracts.

## How to apply a decision

Edit **`api/seed/org_vendor_curated.csv`** (version-controlled) —
`org_id,passport_supplier_id[,note]`:

```csv
# approve
170019006,1633750,renamed 2023 — same organization
170100334,1950951,NYC = New York City
# reject: "-" means reviewed and NOT a match. It never returns to this queue.
170010998,-,NYCEDC is not Queens EDC
170013219,-,Nurses Association is not Defenders Association
```

Then rebuild:

```bash
docker compose exec -T api python build_org_vendor_crosswalk.py --apply
```

⚠ **Real quoted CSV, not hand-split lines** — org names contain commas, and that
is how 47 of 212 rows were mangled during the NYCHA review (#155).

⚠ Curated rows are never overwritten by a rebuild, and the rebuild deletes only
non-curated rows (#149), so a decision survives every future run.

## Notes worth keeping

- ⚠ **`United Federation of Teachers` is three register rows** — the union plus
  two bargaining units — all matching supplier 1713785. That is correct, not a
  duplicate: the crosswalk is one row per org, and the vendor page lists all
  three under "Civic Records".
- ⚠ **The single-token rule earned its keep on `The Nation`.** Suffix stripping
  reduces both the magazine and the unrelated `NATION GROUP INC` to `NATION`, so
  without the rule that would have auto-linked. It costs one false hold
  (`El Diario`), which is one CSV line away — the right trade.
- ⚠ **The suffix list is narrower than it looks**: it strips `CORP` but not
  `CORPORATION`. Measured consequence — exactly ONE legitimate match is missed,
  `Carnegie Hall` → `THE CARNEGIE HALL CORPORATION`, and it does not even appear
  in the queue below because the automatic passes produce no row at all (the
  residual scores under the fuzzy floor). It is therefore a **curated** row in
  `api/seed/org_vendor_curated.csv`. Widening the list was considered and
  rejected: adding CORPORATION/ASSOCIATION/TRUST/FUND collapses `X Trust`,
  `X Fund` and `X Association` all onto `X` and invents collisions.
- Curated decisions live in **`api/seed/org_vendor_curated.csv`**, in the repo —
  the NYCHA equivalent lives only on the box, so 212 reviewed decisions sit in
  one place and would vanish with a rebuild.
- The crosswalk rebuilds automatically after each `vendors` ingest
  (`POST_INGEST_HOOKS`), so it tracks both sides without a separate schedule.
