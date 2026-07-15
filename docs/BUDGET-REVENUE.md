# Budget & Revenue domains — build & ingest runbook

Two CheckbookNYC-parity domains built on the proven spending recipe (extractor →
Parquet → schema-tolerant DuckDB API → design-system pages). **Code is complete
and deploy-safe; the pages stay dormant (`available:false`, "not yet available")
until the Parquet is ingested — the one ops step below.**

## What's built

- **Extractors:** `api/extractors/checkbook_budget.py`, `checkbook_revenue.py`
  (mirror `checkbook_spending.py`). Budget flattens the two nested amount groups
  (`budget_amounts`, `expenditure_amounts`); Budget's criterion is `year`, Revenue's
  is `fiscal_year`.
- **Converter:** `api/build_budget_revenue_parquet.py` — unions per-year CSVs into
  one typed Parquet per domain (amounts→DOUBLE, year→INT), written to the local data
  lake via `--out /data/{budget,revenue}` (a legacy `--upload` S3 path still exists
  but is unused — the lake is local now).
- **API:** `api/routers/budget_revenue.py` (`/oce/budget/{summary,agencies}`,
  `/oce/revenue/{summary,agencies}`) — DuckDB over a single Parquet per domain in the
  local lake (`BUDGET_REVENUE_BASE=/data`), cached daily, `available:false` until the
  file exists.
- **Frontend:** `/procurement/budget`, `/procurement/revenue`
  (`BudgetRevenueController` + `procurement/{budget,revenue}.blade.php`), Budget/
  Revenue submenu items.

## ⚠ Revenue aggregation — a real modeling gotcha (validate at ingest)

The **Budget** feed is at budget-code grain (a clean partition) — `SUM` is correct;
FY25 totals validated ~ $125B modified, in line with the City's expense budget.

The **Revenue** feed is **denormalized**: `adopted`/`modified` are budget figures
**repeated across every detail row** of a revenue line, and `recognized` carries
multiple snapshots per line. A naive `SUM` over-counts ~460× ($49.5T vs the real
~$110B). So the API first collapses to the revenue-line grain
(`agency, revenue_category, revenue_source, revenue_class, fund_class,
funding_class`) taking `MAX()` of each amount, then aggregates — see
`_revenue_lines()`. Validated on an FY25 sample: adopted ~$114.7B / modified
~$129.4B. **Re-validate against the full ingested dataset** — if totals look off,
the line-grain columns are the thing to revisit.

## Ingest (ops step — LOCAL data lake, no AWS creds)

**✅ DONE 2026-07-13 — Budget + Revenue are live** (`/procurement/budget`,
`/procurement/revenue`), validated on the full dataset (Budget modified ~$123.8B;
Revenue adopted ~$115.5B / modified ~$130.3B). Steps below are the reference for
re-running / a fresh box.

The lake is local disk (`BUDGET_REVENUE_BASE=/data`, mounted from
`/home/ubuntu/databook-data`; see `data-lake-local` memory). Write to `/data` —
**no S3, no creds.** Budget/Revenue are additive (brand-new files; nothing live
depends on them), so this is low-risk.

⚠ **Run in an ISOLATED `docker run` container, NOT `docker compose exec api`** —
the api container is memory-capped (3 GB) and a bulk extract can OOM it, taking
down the live api. Run the whole per-domain sequence inside ONE isolated container
so the per-FY `/tmp` CSVs persist through the final build:

```bash
cd /home/ubuntu/databook
# Budget (criterion: year) — one isolated container, extractors + build together
docker run --rm -m 6g --dns 8.8.8.8 -v /home/ubuntu/databook-data:/data -w /app databook-api sh -c '
  for FY in $(seq 2025 -1 2010); do python -m extractors.checkbook_budget --year $FY && cp /tmp/budget_data.csv /tmp/budget_$FY.csv; done
  python build_budget_revenue_parquet.py --domain budget --csv "/tmp/budget_2*.csv" --out /data/budget'
# Revenue (criterion: fiscal_year)
docker run --rm -m 6g --dns 8.8.8.8 -v /home/ubuntu/databook-data:/data -w /app databook-api sh -c '
  for FY in $(seq 2025 -1 2010); do python -m extractors.checkbook_revenue --year $FY && cp /tmp/revenue_data.csv /tmp/revenue_$FY.csv; done
  python build_budget_revenue_parquet.py --domain revenue --csv "/tmp/revenue_2*.csv" --out /data/revenue'
```

(`--out /data/budget` lands `/data/budget/budget.parquet`, which is exactly where
`BUDGET_REVENUE_BASE=/data` expects it; same for revenue. Note the `_2*.csv` glob
excludes the leftover `budget_data.csv`, avoiding a duplicated final FY.)

The API picks the files up automatically (availability re-checked every ~5 min);
no redeploy needed. Then `/procurement/budget` and `/procurement/revenue` populate.

## Verify

```bash
curl -s 'https://api.databook.nyc/oce/budget/summary'  | head   # available:true, sane totals (~$115-125B modified)
curl -s 'https://api.databook.nyc/oce/revenue/summary' | head   # adopted ~$110B — NOT tens of trillions
```

Load both pages; confirm the stat tiles, by-year chart, category ranking, and the
by-agency utilization/realization table.

## Weekly refresh (automated)

✅ **DONE — the whole OCE lake (spending + budget + revenue) now refreshes weekly**
via `scripts/oce-refresh.sh` (host orchestrator, modeled on NYCDB's
`/opt/nycdb/app/refresh.sh`). Cron on the prod box:

```
0 2 * * 0 /home/ubuntu/databook/scripts/oce-refresh.sh weekly >> /home/ubuntu/databook/scripts/oce-refresh.cron.log 2>&1
```

Each run: builds in **isolated `docker run` containers** (never `compose exec api`
— OOM lesson), re-pulls only the years that can still change — the **current +
prior FY** of spending (per-FY partition swap) and the **current + 2 prior FYs** of
budget/revenue (via `build_budget_revenue_parquet.py --merge`, which refreshes just
those FYs and retains all older years from the live single-file Parquet) — then
**validates (>50% row-count guard) → atomic swap → api restart → live-check (incl.
the revenue de-duped $-total sanity band) → rollback on failure**.

> **Deep restatements of old years:** old-year budget/revenue is frozen at the last
> full build. If CheckbookNYC ever restates a year older than the refresh window,
> re-run a one-off **full** build (drop `--merge`, pass all FYs) to recapture it.
Fails safe: any bad download/validation/post-swap check keeps the current data.
Monitored in Sentry Crons (monitor slug `oce-refresh-weekly`). See the script
header for details.

## NYCHA weekly refresh (companion)

The four NYCHA domains (budget / revenue / contracts / spending) refresh weekly via
**`scripts/oce-refresh-nycha.sh`** — a separate companion to `oce-refresh.sh` (kept
apart so a bug in one can't break the other). Same fail-safe pattern (isolated
builds → >50% guard → atomic swap → api restart → live-check → rollback → Sentry
`oce-refresh-nycha-weekly`). Single-file domains re-pull current+2-prior FYs and
`--merge` older; spending rebuilds the current+prior FY partitions. Cron:

```
0 5 * * 0 /home/ubuntu/databook/scripts/oce-refresh-nycha.sh weekly >> /home/ubuntu/databook/scripts/oce-refresh-nycha.cron.log 2>&1
```

⚠ NYCHA spending re-pulls ~5–6M rows/run (the heavy part). If weekly load is
undesirable, move THIS cron to monthly — the City `oce-refresh` stays weekly.

## Follow-ups

- Consider agency-scoped budget/revenue on the agency profile (a `?agency=` param,
  mirroring the spending lenses) as a later enrichment.
- As new domains land (NYCHA, Payroll), fold them into `scripts/oce-refresh.sh`
  (current+prior FY for large feeds; full rebuild for small ones).
