# M/WBE Spending — Re-ingest Runbook

The M/WBE domain (minority/women-owned business reporting on spending) is fully
built in code, but dormant until the spending Parquet carries the M/WBE columns.
This is the one ops step that lands them. It rewrites the live spending lake (now
local disk on the box) and takes hours, so it is deliberately NOT automated in the
refresh cycle yet.

## Why a re-ingest is needed

CheckbookNYC's Spending feed already returns `mwbe_category`,
`woman_owned_business`, and `emerging_business` (verified 2026-07 — 21 columns).
The extractor captured them all along, but the legacy CSV→Parquet build narrowed
the output to 13 columns and dropped them. `api/build_spending_parquet.py` is the
version-controlled build step that keeps every column; running it regenerates the
Parquet with M/WBE included.

## How the code reacts (no deploy needed after ingest)

`api/routers/oce.py` probes the newest Parquet chunk hourly (`_spending_columns`).
The moment a re-ingested chunk carries `mwbe_category`, `_mwbe_enabled()` flips true
and the API lights up:

- M/WBE filters (`mwbe_category` / `woman_owned` / `emerging`) on `/oce/transactions`,
  `/transactions/facets`, `/transactions/export`
- `mwbe_category` contextual facet; M/WBE columns in the row shape + CSV
- `/oce/spending/mwbe` dashboard lens (returns `available:false` until then)

Reads switch to `union_by_name=true`, so years not yet re-ingested keep their
legacy 13-col chunks and simply read NULL for the new columns. **You can backfill
one FY at a time.** The frontend (dashboard "M/WBE spending" section + explorer
facet) is gated on the same signal and appears automatically.

## Run it (on the prod box — LOCAL data lake, no AWS creds)

The spending lake is now local disk (`SPENDING_DATA_BASE=/data/spending`, mounted
from `/home/ubuntu/databook-data`; see `data-lake-local` memory / the "Local data
lake" note in the root CLAUDE.md). The build writes to `/data` — **no S3, no creds.**

⚠ **Run the build in an ISOLATED `docker run` container, NOT `docker compose exec
api`.** The api container is memory-capped (3 GB) and a spending download+build
OOMs it, taking down the live api (learned the hard way 2026-07-13). An isolated
`docker run` off the same image gets its own memory and mounts the same `/data`.

M/WBE **replaces the live spending lake**, so build to a STAGING dir, validate, then
swap. Newest-FY-first so recent data lights up first (this is slow — deep-offset
Checkbook pagination makes big FYs ~20–40 min each, so budget several hours):

```bash
cd /home/ubuntu/databook
# 1. Build a fresh v2 tree next to the live one, ONE isolated container per FY
#    (each FY downloads then writes fiscal_year=<FY>/chunk_<NNNN>.parquet).
for FY in 2026 2025 2024 2023 2022 2021 2020 2019 2018 2017 2016 2015 2014 2013 2012 2011 2010; do
  docker run --rm -m 6g --dns 8.8.8.8 -v /home/ubuntu/databook-data:/data -w /app \
    databook-api python build_spending_parquet.py --fiscal-year "$FY" --download --out /data/spending_v2
done
# (In practice: run the loop under nohup in a script so it survives disconnects.)
# 2. Validate /data/spending_v2 (row counts sane, mwbe_category present + non-null):
docker run --rm -v /home/ubuntu/databook-data:/data -w /app databook-api python -c "import duckdb;print(duckdb.connect().execute(\"SELECT COUNT(*), COUNT(mwbe_category) FROM read_parquet('/data/spending_v2/fiscal_year=2025/*.parquet')\").fetchone())"
#    Also compare total row counts v2 vs the live /data/spending (guard >50% drop).
# 3. Atomic-ish swap, keeping the old tree as a rollback (quick; ok in the api container):
docker compose exec -T api sh -c 'mv /data/spending /data/spending_v1_backup && mv /data/spending_v2 /data/spending'
# 4. Force the schema re-probe (else it caches ~1h): restart the api.
docker compose restart api
```

Each FY downloads the Checkbook feed and writes `fiscal_year=<FY>/chunk_<NNNN>.parquet`
locally. Expect millions of rows total; **several hours** full history. Rollback =
swap `spending_v1_backup` back.

**No `CHUNKS_PER_YEAR` step anymore** — in local mode `get_spending_files()` globs
the directory, so chunk counts don't matter. (That manual follow-up only existed for
the old S3-HTTPS mode, which couldn't list a bucket.)

## Verify

```bash
curl -s 'https://api.databook.nyc/oce/spending/mwbe?fiscal_year=2026' | head
# expect {"available": true, "by_category": [...], "woman_owned": {...}, ...}
```

Then load `/procurement/transactions` — the "M/WBE spending" section should render
— and `/procurement/transactions/search` — the M/WBE category facet + woman-owned /
emerging toggles should appear.

## Notes

- The extractor now pins an explicit `<response_columns>` set, so the CSV schema
  is stable regardless of Checkbook's default response.
- Once validated, fold `build_spending_parquet.py` into the scheduled spending
  refresh so new data keeps the M/WBE columns automatically.
- M/WBE is per-transaction as Checkbook attributes it; treat category totals as the
  Comptroller's attribution, not an independent certification lookup.
