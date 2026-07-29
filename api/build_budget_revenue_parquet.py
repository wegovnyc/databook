#!/usr/bin/env python3
"""
Build the single-file Parquet for the Budget and Revenue domains from the
extractor CSVs (checkbook_budget.py / checkbook_revenue.py).

Budget and Revenue are small (agency/budget-code/revenue-source aggregates, not
per-payment rows), so each domain is one Parquet — no Hive partitioning, no
chunking. The API reads it whole via DuckDB (see routers/budget_revenue.py).

Numeric amount columns are TRY_CAST to DOUBLE and the year to INTEGER so the API
can aggregate without per-query casts; text is TRIMmed.

Usage (local, from downloaded CSVs — safe, no S3):
    python build_budget_revenue_parquet.py --domain revenue --csv /tmp/revenue_2025.csv /tmp/revenue_2024.csv --out ./br_out
    python build_budget_revenue_parquet.py --domain budget  --csv /tmp/budget_*.csv --out ./br_out

Usage (on the prod box, upload to S3):
    python build_budget_revenue_parquet.py --domain revenue --csv /tmp/revenue_*.csv --upload

Pass every fiscal year's CSV in one call — they're unioned into one Parquet.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import duckdb

S3_BUCKET = os.environ.get("SPENDING_S3_BUCKET", "nyc-databook-spending")

DOMAINS = {
    "budget": {
        "out_key": "budget/budget.parquet",
        "year_col": "year",
        "text": ["agency", "department", "expense_category", "budget_code", "budget_name"],
        "nums": ["adopted", "modified", "committed", "pre_encumbered", "encumbered",
                 "cash_expense", "post_adjustment", "accrued_expense"],
    },
    "revenue": {
        "out_key": "revenue/revenue.parquet",
        "year_col": "fiscal_year",
        "text": ["agency", "revenue_category", "revenue_source", "fund_class",
                 "funding_class", "revenue_class", "budget_fiscal_year",
                 "closing_classification_name"],
        "nums": ["adopted", "modified", "recognized"],
    },
    # NYCHA (Housing Authority) parallel feeds — no `agency` dimension; org axes are
    # responsibility_center / funding_source / budget_type (see extractors/
    # checkbook_{budget,revenue}_nycha.py). Consumed by routers/nycha.py.
    "nycha_budget": {
        "out_key": "nycha_budget/nycha_budget.parquet",
        "year_col": "year",
        "text": ["budget_type", "budget_name", "expense_category", "funding_source",
                 "responsibility_center", "program", "project"],
        "nums": ["adopted", "modified", "remaining", "committed", "encumbered",
                 "actual_amount"],
    },
    "nycha_revenue": {
        "out_key": "nycha_revenue/nycha_revenue.parquet",
        "year_col": "budget_fiscal_year",
        "text": ["budget_name", "budget_type", "closing_classification_name",
                 "revenue_expense_category", "funding_source", "program", "project",
                 "responsibility_center", "revenue_category", "revenue_class"],
        "nums": ["adopted", "modified", "recognized", "remaining"],
    },
    # Payroll — annual rollup (agency/title/payroll_type grain) produced by the
    # extractor, which pre-sums the additive pay amounts. Single-file per the
    # assessment (~150 MB); served by routers/payroll.py. `records` = payment-row
    # count; salary_sum/count give a headcount-free average annual salary.
    "payroll": {
        "out_key": "payroll/payroll.parquet",
        "year_col": "fiscal_year",
        "text": ["agency", "title", "payroll_type"],
        "nums": ["gross", "base", "overtime", "other", "records",
                 "salary_sum", "salary_count", "salary_min", "salary_max"],
    },
    # NYCHA contracts — stored line-grain (contract-level columns only); the API
    # aggregates to one row per contract_id at query time (routers/nycha.py).
    "nycha_contracts": {
        "out_key": "nycha_contracts/nycha_contracts.parquet",
        "year_col": "fiscal_year",
        "text": ["contract_id", "vendor", "purpose", "location", "contract_type",
                 "record_type", "purchase_order_type", "award_method", "industry",
                 "funding_source", "responsibility_center", "pin", "program", "project",
                 "expenditure_type", "grant_name", "start_date", "end_date", "approved_date"],
        "nums": ["number_of_releases", "contract_original_amount",
                 "contract_current_amount", "contract_invoiced_amount"],
    },
}


def _select_expr(spec: dict, available: set) -> str:
    parts = [f"TRY_CAST({spec['year_col']} AS INTEGER) AS {spec['year_col']}"]
    for c in spec["text"]:
        if c == spec["year_col"]:
            continue
        parts.append(f"NULLIF(TRIM(CAST({c} AS VARCHAR)), '') AS {c}" if c in available
                     else f"CAST(NULL AS VARCHAR) AS {c}")
    for c in spec["nums"]:
        parts.append(f"TRY_CAST({c} AS DOUBLE) AS {c}" if c in available
                     else f"CAST(NULL AS DOUBLE) AS {c}")
    return ", ".join(parts)


def build(domain: str, csvs: list[str], out_dir: str, merge_existing: str | None = None) -> str:
    spec = DOMAINS[domain]
    year_col = spec["year_col"]
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")

    files = [f for pat in csvs for f in glob.glob(pat)]
    if not files:
        print(f"[build] no CSVs matched {csvs}"); sys.exit(1)
    quoted = ", ".join(f"'{f}'" for f in files)
    src = f"read_csv_auto([{quoted}], header=true, all_varchar=true, ignore_errors=true, union_by_name=true)"
    available = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}

    out_path = os.path.join(out_dir, os.path.basename(spec["out_key"]))
    os.makedirs(out_dir, exist_ok=True)

    fresh_select = f"SELECT {_select_expr(spec, available)} FROM {src}"

    # --merge: refresh only the fiscal years present in the new CSVs, and retain
    # every other year from an existing Parquet. Lets the scheduled refresh
    # re-pull just recent FYs (budget/revenue restate only recent years) instead
    # of re-downloading all history each run, while keeping the single-file layout.
    # Same-converter output on both sides → UNION ALL BY NAME is schema-safe.
    if merge_existing and os.path.exists(merge_existing):
        fresh_years = sorted(
            r[0] for r in con.execute(
                f"SELECT DISTINCT TRY_CAST({year_col} AS INTEGER) AS y FROM {src} "
                f"WHERE {year_col} IS NOT NULL"
            ).fetchall() if r[0] is not None
        )
        if not fresh_years:
            print(f"[build] {domain}: --merge given but CSVs have no usable {year_col}; aborting")
            sys.exit(1)
        yrs = ", ".join(str(y) for y in fresh_years)
        select_sql = (
            f"WITH fresh AS ({fresh_select}) SELECT * FROM fresh "
            f"UNION ALL BY NAME "
            f"SELECT * FROM read_parquet('{merge_existing}') WHERE {year_col} NOT IN ({yrs})"
        )
        print(f"[build] {domain}: merge — refreshing FYs {fresh_years}, retaining "
              f"other years from {merge_existing}")
    else:
        if merge_existing:
            print(f"[build] {domain}: --merge target {merge_existing} absent — full build from CSVs")
        select_sql = fresh_select

    con.execute(f"COPY ({select_sql}) TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_path}')").fetchone()[0]
    print(f"[build] {domain}: {n:,} rows from {len(files)} CSV(s) -> {out_path}")
    return out_path


def upload(out_path: str, out_key: str) -> None:
    import boto3
    s3 = boto3.client("s3")
    print(f"[upload] {out_path} -> s3://{S3_BUCKET}/{out_key}")
    s3.upload_file(out_path, S3_BUCKET, out_key)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build Budget/Revenue Parquet")
    ap.add_argument("--domain", required=True, choices=list(DOMAINS))
    ap.add_argument("--csv", nargs="+", required=True, help="CSV path(s)/glob(s) — all fiscal years")
    ap.add_argument("--out", default="./br_out", help="Local output directory")
    ap.add_argument("--merge", default=None,
                    help="Existing Parquet to merge with: refresh only the FYs in --csv, "
                         "retain all other years from this file (recent-FYs-only refresh)")
    ap.add_argument("--upload", action="store_true", help="Upload to S3 (needs AWS creds)")
    args = ap.parse_args()

    path = build(args.domain, args.csv, args.out, merge_existing=args.merge)
    if args.upload:
        upload(path, DOMAINS[args.domain]["out_key"])
