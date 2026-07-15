#!/usr/bin/env python3
"""
Build the partitioned spending Parquet consumed by api/routers/oce.py.

This is the CSV -> Parquet conversion step that previously lived nowhere in the
repo (it was a one-off DuckDB job). It reads the Checkbook Spending CSV produced
by extractors/checkbook_spending.py (which captures EVERY response column) and
writes it out as `fiscal_year=<FY>/chunk_<NNNN>.parquet`, the layout the API
reader enumerates.

The important difference from the legacy build: it KEEPS the M/WBE and
document-level columns (mwbe_category, woman_owned_business, emerging_business,
capital_project, mocs_registered, contract_purpose, document_id,
sub_contract_reference_id) instead of narrowing to the old 13. The API surfaces
those columns automatically once they're present (see `_spending_columns()` /
`_mwbe_enabled()` in routers/oce.py) — no schema change needed there.

Re-ingest is newest-FY-first: the API's schema probe reads the newest chunk, so a
partial backfill lights the M/WBE features up as soon as the first recent year
lands. Years not yet rebuilt keep their legacy 13-col chunks; the reader mixes
them with `union_by_name=true` (missing columns read as NULL).

Usage (local, from a downloaded CSV — safe, no S3):
    python build_spending_parquet.py --csv /tmp/spending_data.csv --out ./spend_out

Usage (produce + upload one fiscal year to S3, on the prod box with creds):
    python build_spending_parquet.py --fiscal-year 2026 --upload

After a run it PRINTS the per-FY chunk counts as a ready-to-paste CHUNKS_PER_YEAR
fragment — update that map in routers/oce.py:get_spending_files() for any FY whose
chunk count changed.
"""
from __future__ import annotations

import argparse
import os
import sys

import duckdb

# Column order written to Parquet. The legacy 13 come first (stable shape for the
# existing reader), then the v2 additions. Every name matches a Checkbook Spending
# response tag verified 2026-07 (see extractors/checkbook_spending.py RESPONSE_COLUMNS).
LEGACY_COLS = [
    "agency", "payee_name", "check_amount", "fiscal_year", "issue_date",
    "industry", "spending_category", "contract_id", "department",
    "expense_category", "budget_code", "sub_vendor", "associated_prime_vendor",
]
V2_COLS = [
    "mwbe_category", "woman_owned_business", "emerging_business",
    "capital_project", "mocs_registered", "contract_purpose",
    "document_id", "sub_contract_reference_id",
]
ALL_COLS = LEGACY_COLS + V2_COLS

# Rows per Parquet chunk. ~200k keeps each file a comfortable size for HTTP range
# reads while matching the existing multi-chunk-per-year layout.
CHUNK_ROWS = 200_000

S3_BUCKET = os.environ.get("SPENDING_S3_BUCKET", "nyc-databook-spending")


def _select_expr(available: set) -> str:
    """SELECT list: TRIM every kept column; emit NULL for any the CSV lacks so the
    output schema is always the full ALL_COLS set regardless of source vintage."""
    parts = []
    for c in ALL_COLS:
        if c == "fiscal_year":
            parts.append("TRY_CAST(fiscal_year AS INTEGER) AS fiscal_year")
        elif c in available:
            parts.append(f"NULLIF(TRIM(CAST({c} AS VARCHAR)), '') AS {c}")
        else:
            parts.append(f"CAST(NULL AS VARCHAR) AS {c}")
    return ", ".join(parts)


def build(csv_path: str, out_dir: str, only_fy: int | None = None) -> dict:
    """Convert `csv_path` to partitioned Parquet under `out_dir`. Returns
    {fiscal_year: chunk_count}."""
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")

    # Read all-as-VARCHAR so ragged Checkbook exports never fail type inference.
    src = (
        f"read_csv_auto('{csv_path}', header=true, all_varchar=true, "
        f"ignore_errors=true)"
    )
    available = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}
    missing = [c for c in ALL_COLS if c not in available and c != "fiscal_year"]
    if missing:
        print(f"[build] NOTE: source CSV missing {missing} — emitting NULL for them")

    con.execute(f"CREATE VIEW rows AS SELECT {_select_expr(available)} FROM {src}")

    fys = con.execute(
        "SELECT DISTINCT fiscal_year FROM rows WHERE fiscal_year IS NOT NULL ORDER BY 1"
    ).fetchall()
    fys = [r[0] for r in fys if only_fy is None or r[0] == only_fy]
    if not fys:
        print(f"[build] no rows for fiscal_year={only_fy}" if only_fy else "[build] no rows")
        return {}

    counts: dict[int, int] = {}
    for fy in fys:
        n = con.execute("SELECT COUNT(*) FROM rows WHERE fiscal_year = ?", [fy]).fetchone()[0]
        nchunks = max(1, -(-n // CHUNK_ROWS))  # ceil
        fy_dir = os.path.join(out_dir, f"fiscal_year={fy}")
        os.makedirs(fy_dir, exist_ok=True)
        for i in range(nchunks):
            path = os.path.join(fy_dir, f"chunk_{i + 1:04d}.parquet")
            con.execute(
                f"COPY (SELECT * EXCLUDE (fiscal_year) FROM rows WHERE fiscal_year = ? "
                f"ORDER BY payee_name LIMIT {CHUNK_ROWS} OFFSET {i * CHUNK_ROWS}) "
                f"TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)",
                [fy],
            )
        counts[fy] = nchunks
        print(f"[build] FY{fy}: {n:,} rows -> {nchunks} chunk(s)")
    return counts


def upload(out_dir: str) -> None:
    """Upload the local partitioned tree to s3://<bucket>/fiscal_year=*/chunk_*.parquet."""
    import boto3

    s3 = boto3.client("s3")
    for root, _dirs, fnames in os.walk(out_dir):
        for fn in fnames:
            if not fn.endswith(".parquet"):
                continue
            local = os.path.join(root, fn)
            key = os.path.relpath(local, out_dir).replace(os.sep, "/")
            print(f"[upload] {local} -> s3://{S3_BUCKET}/{key}")
            s3.upload_file(local, S3_BUCKET, key)


def _print_chunks_fragment(counts: dict) -> None:
    if not counts:
        return
    print("\n# Paste into routers/oce.py:get_spending_files() CHUNKS_PER_YEAR for changed FYs:")
    for fy in sorted(counts, reverse=True):
        print(f"    {fy}: {counts[fy]},")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build partitioned spending Parquet")
    ap.add_argument("--csv", default="/tmp/spending_data.csv",
                    help="Source Checkbook spending CSV (default: /tmp/spending_data.csv)")
    ap.add_argument("--out", default="./spend_out", help="Local output directory")
    ap.add_argument("--fiscal-year", type=int, default=None,
                    help="Build only this fiscal year (default: every FY in the CSV)")
    ap.add_argument("--download", action="store_true",
                    help="Download the FY from Checkbook first (needs --fiscal-year)")
    ap.add_argument("--upload", action="store_true",
                    help="Upload the built tree to S3 (needs AWS creds)")
    args = ap.parse_args()

    csv_path = args.csv
    if args.download:
        if not args.fiscal_year:
            print("--download requires --fiscal-year"); sys.exit(2)
        from extractors.checkbook_spending import download_spending
        csv_path, n = download_spending(year=str(args.fiscal_year))
        if not csv_path:
            print("download produced no rows"); sys.exit(1)

    counts = build(csv_path, args.out, only_fy=args.fiscal_year)
    if args.upload:
        upload(args.out)
    _print_chunks_fragment(counts)
