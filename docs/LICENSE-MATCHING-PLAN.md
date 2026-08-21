# License Matching Improvement Plan

> ## ✅ ALL SEVEN PHASES SHIPPED 2026-08-13 (PRs #222-#230).
> This document is kept as the RECORD OF WHY, not as outstanding work. Read
> `CLAUDE.md` → "Current status (2026-08-13)" for the current state.
>
> **Two phases changed shape during the build**, and the reasons matter more than
> the plan did:
> - **Phase 3 (catalogue snapshot) collapsed to a fetch.** The catalogue shipped a
>   JSON API mid-build (`/v1/entries.json`, `/by-product.json`, `/meta.json`), so
>   the browser harvest fallback was never needed — and the API corrected data I
>   had already published (2,121 entries was really 1,995 after a dedup).
> - **Phase 4 (detectors) became two GETs**, and querying the precomputed index
>   found **$19.06M of strong software matches against ~$2M found by hand** —
>   including `Esri ArcGIS $13.3M → QGIS`, which the replaceability rating had
>   hidden on `low`.
>
> **What the plan did not anticipate, and turned out to matter most:** classifying
> WHAT KIND OF PURCHASE each family is. Phase 1 was written as a display rule; it
> became the finding — only 25% of licence spend is an open-source question at
> all, and $6.80M of AWS had been invisible.
>
> ⚠ Still open, and both are decisions rather than work: the **publish/gate/unlink**
> call on pages that are unlisted yet linked from public vendor profiles, and the
> **curation pass** (`curated = 0` on `is_license`; top 10 families = 79% of value).



> Six workstreams to make the licence → open-source matching honest, mechanical
> and priced. Written 2026-08-13 from the measured state below. Companion to the
> Licenses analysis (`/research/digital-reform/licenses`, unlisted) and the two
> seeds in PR #222 (`license_replacement_candidates.csv`,
> `license_family_class.csv`).

## The measured starting point (do not re-derive)

- **948 licence contracts, $1,370.4M current value**, 431 product families.
- `build_vs_buy = high` covers **102 contracts / $10.13M — 0.7% of licence
  spend**. `medium` adds $85.98M.
- ⚠⚠ **The rating hides money.** "Could the City build this itself?" is the
  wrong question for infrastructure, so it lands on `low` and vanishes from
  every replaceability view: **AWS $6.80M** (two-thirds the size of the entire
  `high` set), Rocket Software $4.22M, SolarWinds $1.22M, Nerdio $1.12M,
  Socrata $828K, Box $656K.
- ⚠ **The rating is the weakest field on the site**: 75% cross-model agreement
  (vs 98% for `tech_relevant`), self-inconsistent on 64 of 435 families, and
  ~$1.5M of its `high` set are category errors (content subscriptions, managed
  hosting, instructor-led training).
- **Catalogue**: govoss-catalog.vercel.app — 2,121 entries / 1,881 repos /
  19 categories / 1,056 with publiccode.yml. ⚠ **No machine access yet**; a
  feature-request prompt asking for `/entries.json` + a `replaces` field has
  been handed to the owner (who built the site). Everything below has a
  fallback that does not depend on it.
- **Known AI costs** (measured, thinking-token-aware): classification
  $0.00025/contract, summaries $0.00006/family on `gemini-3.1-flash-lite`.
  Every run in this plan totals **under $1**.
- Existing plumbing to reuse: `license_family` (slugs, TRUNCATE-rebuilt),
  `license_family_description` (curated flag, never overwritten), the
  comment-stripping seed-loader pattern, and the guard conventions
  (assert-it-looked, verify-by-reintroducing-the-bug).

## The invariant every phase respects

⚠⚠ **An unreviewed match never renders as a claim.** The NYCHA crosswalk lesson
(#146) is structural here: auto-generated candidates go to a *review* surface,
and only curated rows reach the public-facing pages. Classifying a line as
hosting is likewise **never a defence of the spend** — hosting rows must carry a
price-facing lever, and a test enforces it.

---

## Phase 0 — Wire the two seeds (prerequisite; PR #222 must land first)

**What:** `build_license_classes.py` loads both CSVs into
`license_family_class` and `license_replacement_candidates` tables (comment-
stripping loader, row-count floor, stale-rule report — clone the
`build_license_families.py` shape). Family pages gain two sections:
*"What kind of purchase is this"* (class + lever) and *"Possible open-source
replacements"* (curated candidates, confidence-labelled, catalogue-linked).
`none-found` renders as *"No known open-source alternative (searched
2026-08-11)"* — absence displayed, not omitted.

**Verify:** render `/licenses/wp-engine` (hosting lever, no OSS pretence),
`/licenses/surveymonkey` (LimeSurvey, 18 adopters), `/licenses/hootsuite`
(explicit negative). Guards: candidates table absent ⇒ section degrades,
never 500s; seed vocabularies pinned (already in PR #222's tests).

**Effort:** 1 PR. No AI spend.

## Phase 1 — Classify the purchase BEFORE rating replaceability

**What:** a per-family `purchase_class` (the 7-class vocabulary from the seed),
auto-derived by a Gemini pass over each family's recorded purposes (~435
families, pennies) with the curated CSV as overrides — curated always wins.
Then the display rule that motivates everything: **only `software-licence`
families show a build-vs-buy rating.** Every other class shows its lever
instead (price-and-rightsizing, benchmark-then-self-host, is-the-paid-tier-
needed, …).

⚠ Do **not** re-run the classifier with `--force` to add this — that would
rewrite settled `build_vs_buy` values and visibly move the Build-your-own
headline (documented hazard). A separate pass writes only the class.

**Verify (acceptance is a page state, not a diff):** AWS renders under
*cloud-infrastructure* with a price lever — the $6.80M that was invisible
becomes the largest line in a new "hosting & infrastructure" view. Guard: no
family with class ≠ software-licence appears in any replaceability-ranked list.

**Effort:** 1 PR. ~$0.05 AI.

## Phase 2 — Match on capability, not product name

**What:** a controlled vocabulary of ~30 capability tags (`survey-collection`,
`helpdesk-ticketing`, `remote-access`, `lms-platform`, `file-sharing`, …), each
mapped to one of the catalogue's 19 categories. A grounded Gemini pass tags
each software-licence family from its recorded purposes. Tags become the match
key (Phase 4) and a page filter.

⚠ The vocabulary is a version-controlled seed with the category mapping in it;
a guard fails on a tag that maps to no catalogue category. This is what removes
"I happened to know what SurveyMonkey does" from the loop.

**Effort:** 1 PR. ~$0.05 AI.

## Phase 3 — Get the catalogue machine-readable

**Preferred:** the catalogue owner ships `/entries.json` + `/meta.json` (the
feature request is already sent; items are build-step changes to a static
site). **Fallback, so this plan is never blocked:** a one-time browser harvest
of all 2,121 entries into `api/seed/govoss_catalog_snapshot.json` —
`{name, description, category, licence, adopters, country, source, repo_url,
status, link_dead, generated_at}`.

⚠ Guards: the loader **asserts ≥2,000 entries** (a truncated harvest must
refuse, not quietly shrink the match pool) and every consumer surfaces
`generated_at` — a snapshot that looks live is the stale-`repos.json` failure.
Dedup on repo URL (2,121 entries / 1,881 repos ⇒ ~240 duplicates measured).

**Effort:** ½ PR if `/entries.json` lands; 1 PR for the harvest.

## Phase 4 — Mechanical matching, two independent detectors

**Detector A — already-open-source (highest confidence, zero judgement):**
normalized name match between family names and catalogue entries. A hit means
the substitute *is the same product* and the spend is a paid tier — the class
of finding worth ~$385K today (NGINX Plus, GeoServer, Anaconda, DBeaver, Shiny
Server Pro). ⚠ Reuse the existing `norm()`; do **not** strip corporate
suffixes (measured lesson: it doubles collisions and adds nothing).

**Detector B — capability match, ranked by evidence:** for each software-
licence family, catalogue entries sharing its capability tag, ranked by
**government adopter count desc**, licence shown, `link_dead` excluded. Ranking
by adoption+licence replaces text similarity entirely — `LimeSurvey, 18
adopters, GPL-3.0` is the argument a buyer needs; a similarity score is not.

**Both write tier `auto` rows to `license_replacement_candidates` — and the
page renders ONLY curated rows.** Auto output lands in
`docs/license-replacement-review.md` (regenerable), reviewed like the
org-vendor crosswalk; accepted rows are promoted into the CSV where each is a
diff. Guard: an `auto`-tier row rendering on any page fails the build —
verified by promoting one without curation and watching it fail.

**Effort:** 1 PR. No AI spend (both detectors are deterministic).

## Phase 5 — Price context, within honest limits

⚠ **No seat or unit counts exist anywhere in this data** (already stated on the
page). So per-seat comparisons are impossible and must not be faked. What *is*
derivable:

- **Cost per contract-year** — term dates exist on ~all licence contracts;
  `value / term_years` on every family page and in the CSV export.
- **A curated rate-card seed** (`license_rate_cards.csv`): public list prices
  for the hosting/benchmarkable class — WP Engine, Pantheon, Box, Akamai — each
  row carrying `source_url` + `as_of`. ⚠ A price without a date reads like a
  measurement; the guard rejects rows missing either. The page shows the rate
  card **beside** the spend and asks the question; it never computes
  "N× overpriced" without a unit count to divide by.
- **AWS/cloud gets lever text only** (committed-use coverage, rightsizing) —
  benchmarking metered consumption needs usage data we do not hold, and
  pretending otherwise would be the same category error in the other direction.

**Effort:** 1 PR. No AI spend.

## Phase 6 — Durable negatives and a re-match loop

**What:** `searched_at` on every candidate row; the licenses index gains a
*"Gaps in the open-source commons"* section (Hootsuite $902K, Voicecast $900K,
Fulcrum $278K, Spectrio $86K, service-desk chatbot $476K — the two largest
"replaceable" lines are negatives, which is a finding about the commons, not
about the search). When the catalogue snapshot refreshes, the Phase 4 matcher
re-runs and **diffs**: a new candidate for a previously-`none` family is the
headline of the run report. The gap list is also a deliverable back to the
catalogue's owner — you built it; this is its demand signal.

**Effort:** ½ PR, folded into Phase 4's matcher.

## Phase 7 (cross-cutting) — Schedule the pipeline, with its thresholds

Nothing runs any of this today; the classifier sat six weeks untouched. One
monthly host cron: classify new contracts → rebuild families → describe →
classify purchases → re-match → report. ⚠ The lessons that must ship *with*
the cron, not after it: a healthchecks check created in the same change (a
check without its pinger manufactures a red monitor), a cron expression that
matches the check exactly, **not at 04:00 UTC** (the api-restart collision),
detached execution, and `exc_str` on every error path. Post-check measures the
outcome (`max(classified_at)` moved), not the log's last line.

**Effort:** 1 PR.

---

## Order and dependencies

```
PR #222 ──> Phase 0 ──> Phase 1 ──┐
                        Phase 2 ──┼──> Phase 4 ──> Phase 6
            Phase 3 (or fallback)─┘        │
                        Phase 5 (independent after Phase 0)
                        Phase 7 (after Phase 4)
```

Phases 1, 2, 3 are mutually independent and can run in any order after
Phase 0. Total: ~6 PRs, well under $1 of AI spend, no schema changes to any
pipeline-loaded table.

## Risks, stated rather than managed away

- **Curation is the bottleneck, and it is already behind**: `curated = 0` on
  the underlying classifications. Phases 1–2 add more AI judgements. The
  mitigations are structural (auto never renders; review docs; seeds as
  diffs), but the review time is real and human.
- **The catalogue may never ship machine access.** The harvest fallback works
  but freezes; `generated_at` display is the honesty mechanism, not a fix.
- **The unlisted/public tension is unresolved.** Vendor profiles (public)
  already link into the licence pages (unlisted, uncurated). Each phase makes
  those pages more consequential; the publish/basic-auth/unlink decision from
  the earlier session is still open and gets more urgent, not less.
- **Rate cards drift.** The `as_of` field makes staleness visible; it does not
  prevent it. A lapsed rate card should be treated like the ACKNOWLEDGED
  pattern in `dataset-staleness.sh` — dated, and loud once expired.
