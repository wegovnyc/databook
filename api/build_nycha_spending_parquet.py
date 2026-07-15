#!/usr/bin/env python3
"""
Build the partitioned NYCHA spending Parquet lake consumed by routers/nycha.py.

Mirrors build_spending_parquet.py but for the Spending_NYCHA schema (no
agency/payee_name split; axes are responsibility_center / funding_source /
spending_category + the section_8 flag). Reads the CSV from
extractors/checkbook_spending_nycha.py and writes
`nycha_spending/fiscal_year=<FY>/chunk_<NNNN>.parquet` — the layout the API globs.

All columns read as VARCHAR (ragged Checkbook exports never fail type inference);
amounts TRY_CAST to DOUBLE, the year to INTEGER (kept only in the partition path).

Usage:
    # produce one fiscal year into the local lake (downloads first)
    python build_nycha_spending_parquet.py --fiscal-year 2024 --download --out /data/nycha_spending
    # or from an already-downloaded CSV
    python build_nycha_spending_parquet.py --csv /tmp/nycha_spending_data.csv --out ./out
"""
from __future__ import annotations

import argparse
import os
import sys

import duckdb

# Partition column (from the feed's `year` tag) — stored in the path, not the file.
YEAR_COL = "year"
TEXT_COLS = [
    "issue_date", "document_id", "section_8", "purchase_order_type", "contract_id",
    "release_number", "invoice_number", "check_status", "vendor", "purpose",
    "spending_category", "industry", "funding_source", "responsibility_center",
    "expense_category", "program", "project",
]
NUM_COLS = ["check_amount", "amount_spent"]
CHUNK_ROWS = 200_000


def _select_expr(available: set) -> str:
    parts = []
    for c in TEXT_COLS:
        parts.append(f"NULLIF(TRIM(CAST({c} AS VARCHAR)), '') AS {c}" if c in available
                     else f"CAST(NULL AS VARCHAR) AS {c}")
    for c in NUM_COLS:
        parts.append(f"TRY_CAST({c} AS DOUBLE) AS {c}" if c in available
                     else f"CAST(NULL AS DOUBLE) AS {c}")
    return ", ".join(parts)


def build(csv_path: str, out_dir: str, only_fy: int | None = None) -> dict:
    con = duckdb.connect()
    src = f"read_csv_auto('{csv_path}', header=true, all_varchar=true, ignore_errors=true)"
    available = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}
    con.execute(
        f"CREATE VIEW rows AS SELECT TRY_CAST({YEAR_COL} AS INTEGER) AS fiscal_year, "
        f"{_select_expr(available)} FROM {src}"
    )
    fys = [r[0] for r in con.execute(
        "SELECT DISTINCT fiscal_year FROM rows WHERE fiscal_year IS NOT NULL ORDER BY 1"
    ).fetchall() if only_fy is None or r[0] == only_fy]
    if not fys:
        print(f"[build] no rows for fiscal_year={only_fy}" if only_fy else "[build] no rows")
        return {}

    counts: dict[int, int] = {}
    for fy in fys:
        n = con.execute("SELECT COUNT(*) FROM rows WHERE fiscal_year = ?", [fy]).fetchone()[0]
        nchunks = max(1, -(-n // CHUNK_ROWS))
        fy_dir = os.path.join(out_dir, f"fiscal_year={fy}")
        os.makedirs(fy_dir, exist_ok=True)
        for i in range(nchunks):
            path = os.path.join(fy_dir, f"chunk_{i + 1:04d}.parquet")
            con.execute(
                f"COPY (SELECT * EXCLUDE (fiscal_year) FROM rows WHERE fiscal_year = ? "
                f"ORDER BY vendor LIMIT {CHUNK_ROWS} OFFSET {i * CHUNK_ROWS}) "
                f"TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)",
                [fy],
            )
        counts[fy] = nchunks
        print(f"[build] FY{fy}: {n:,} rows -> {nchunks} chunk(s)")
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build partitioned NYCHA spending Parquet")
    ap.add_argument("--csv", default="/tmp/nycha_spending_data.csv")
    ap.add_argument("--out", default="./nycha_spend_out")
    ap.add_argument("--fiscal-year", type=int, default=None)
    ap.add_argument("--download", action="store_true",
                    help="Download the FY from Checkbook first (needs --fiscal-year)")
    args = ap.parse_args()

    csv_path = args.csv
    if args.download:
        if not args.fiscal_year:
            print("--download requires --fiscal-year"); sys.exit(2)
        from extractors.checkbook_spending_nycha import download_spending_nycha
        csv_path, n = download_spending_nycha(year=str(args.fiscal_year))
        if not csv_path:
            print("download produced no rows"); sys.exit(1)

    build(csv_path, args.out, only_fy=args.fiscal_year)
