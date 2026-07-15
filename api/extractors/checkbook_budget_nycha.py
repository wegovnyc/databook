from __future__ import annotations

"""
Checkbook NYC — NYCHA Budget extractor (type_of_data=Budget_NYCHA).

NYCHA (NYC Housing Authority) is a separate public-benefit corporation with its
own budget, published by CheckbookNYC as a parallel `_NYCHA` feed. Unlike the
City expense budget there is NO `agency`/`department`/`budget_code` dimension —
NYCHA's org axes are `responsibility_center` (developments + functional units),
`program`, `funding_source`, and `budget_type`. Aggregate grain (small: ~37k
rows/FY), so it lands as a single Parquet (no chunking). Mirrors
checkbook_budget.py, including the two nested amount groups.

NOTE: the criterion is `year` (like the City Budget, NOT `fiscal_year`), and the
response does NOT echo the year back — so we inject the queried year per row.
"""

import csv
import os
import time
import xml.etree.ElementTree as ET

import requests

from extractors import checkbook_post, clean_text, get_current_fiscal_year, upload_to_s3

API_URL = "https://www.checkbooknyc.com/api"
FILE_NAME = "nycha_budget_data.csv"
MAX_RECORDS_PER_REQUEST = 20000

# Flat CSV schema. `year` is injected from the request (the feed omits it). Then
# the flat dimension tags, then the flattened nested amount groups (verified live
# 2026-07: budget_amounts -> adopted/modified/remaining;
# expenditure_amounts -> committed/encumbered/actual_amount).
FLAT_COLS = ["year", "budget_type", "budget_name", "expense_category",
             "funding_source", "responsibility_center", "program", "project"]
BUDGET_AMOUNT_COLS = ["adopted", "modified", "remaining"]
EXPENDITURE_COLS = ["committed", "encumbered", "actual_amount"]
COLUMNS = FLAT_COLS + BUDGET_AMOUNT_COLS + EXPENDITURE_COLS


def _row_from(txn: ET.Element, year: str) -> dict:
    """Flatten one <transaction>, descending into the two nested amount groups.
    Injects `year` (the feed doesn't return it)."""
    row = {c: "" for c in COLUMNS}
    row["year"] = year
    for child in txn:
        if child.tag in ("budget_amounts", "expenditure_amounts"):
            for amt in child:
                if amt.tag in row:
                    row[amt.tag] = clean_text(amt.text)
        elif child.tag in row:
            row[child.tag] = clean_text(child.text)
    return row


def download_budget_nycha(year: str = None, dry_run: bool = False) -> tuple[str | None, int]:
    """Download NYCHA budget for a year. Returns (csv_path|None, count)."""
    if year is None:
        year = str(get_current_fiscal_year())
    print(f"[nycha-budget] Starting download (FY {year})...")

    output_file = f"/tmp/{FILE_NAME}"
    offset = 1
    total = 0
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        while True:
            payload = f"""<request>
    <type_of_data>Budget_NYCHA</type_of_data>
    <records_from>{offset}</records_from>
    <max_records>{MAX_RECORDS_PER_REQUEST}</max_records>
    <search_criteria>
        <criteria><name>year</name><type>value</type><value>{year}</value></criteria>
    </search_criteria>
</request>"""
            try:
                resp = checkbook_post(payload, label="nycha-budget")
                root = ET.fromstring(resp.content)
            except (requests.exceptions.RequestException, ET.ParseError) as e:
                print(f"[nycha-budget] error at offset {offset}: {e}")
                break

            txns = root.findall(".//transaction")
            if not txns:
                break
            for txn in txns:
                writer.writerow(_row_from(txn, year))
                total += 1

            if dry_run or len(txns) < MAX_RECORDS_PER_REQUEST:
                break
            offset += MAX_RECORDS_PER_REQUEST
            time.sleep(1)

    print(f"[nycha-budget] Download complete: {total} records")
    return (output_file, total) if total else (None, 0)


async def run(dry_run: bool = False) -> dict:
    """Scheduler entrypoint — download current FY, upload to S3."""
    year = str(get_current_fiscal_year())
    csv_path, count = download_budget_nycha(year=year, dry_run=dry_run)
    if not csv_path or count == 0:
        return {"status": "fail", "error": "No records downloaded", "rows": 0}
    if dry_run:
        return {"status": "success", "rows": count, "dry_run": True}
    url = upload_to_s3(csv_path, FILE_NAME)
    if os.path.exists(csv_path):
        os.remove(csv_path)
    return {"status": "success", "rows": count, "s3_url": url} if url \
        else {"status": "fail", "error": "S3 upload failed", "rows": count}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Download Checkbook NYC NYCHA Budget")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--year", type=str, default=None)
    args = ap.parse_args()
    download_budget_nycha(year=args.year, dry_run=args.dry_run)
