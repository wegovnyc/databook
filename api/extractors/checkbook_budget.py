from __future__ import annotations

"""
Checkbook NYC Budget Extractor — downloads the expense budget via the XML API.

Budget is the City's expense budget by agency / department / expense-category /
budget-code: adopted vs modified vs committed, plus the expenditure breakdown
(pre-encumbered / encumbered / cash / accrued / post-adjustment). Budget-code-level
aggregates, so it lands as a single Parquet (no chunking). Mirrors
checkbook_spending.py, but the Budget record nests two amount groups
(<budget_amounts>, <expenditure_amounts>) which this flattens into one CSV row.

NOTE: the Budget domain's search criterion is `year` (NOT `fiscal_year`).
"""

import csv
import os
import time
import xml.etree.ElementTree as ET

import requests

from extractors import checkbook_post, clean_text, get_current_fiscal_year, upload_to_s3
from modules.errfmt import exc_str

API_URL = "https://www.checkbooknyc.com/api"
FILE_NAME = "budget_data.csv"
MAX_RECORDS_PER_REQUEST = 20000

# Flat CSV schema. First the flat tags, then the flattened nested amount groups
# (verified against the live API 2026-07).
FLAT_COLS = ["agency", "year", "department", "expense_category", "budget_code", "budget_name"]
BUDGET_AMOUNT_COLS = ["adopted", "modified", "committed"]
EXPENDITURE_COLS = ["pre_encumbered", "encumbered", "cash_expense", "post_adjustment", "accrued_expense"]
COLUMNS = FLAT_COLS + BUDGET_AMOUNT_COLS + EXPENDITURE_COLS


def _row_from(txn: ET.Element) -> dict:
    """Flatten one <transaction>, descending into the two nested amount groups."""
    row = {c: "" for c in COLUMNS}
    for child in txn:
        if child.tag in ("budget_amounts", "expenditure_amounts"):
            for amt in child:
                if amt.tag in row:
                    row[amt.tag] = clean_text(amt.text)
        elif child.tag in row:
            row[child.tag] = clean_text(child.text)
    return row


def download_budget(year: str = None, dry_run: bool = False) -> tuple[str | None, int]:
    """Download Checkbook NYC budget for a year. Returns (csv_path|None, count)."""
    if year is None:
        year = str(get_current_fiscal_year())
    print(f"[budget] Starting download (FY {year})...")

    output_file = f"/tmp/{FILE_NAME}"
    offset = 1
    total = 0
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        while True:
            payload = f"""<request>
    <type_of_data>Budget</type_of_data>
    <records_from>{offset}</records_from>
    <max_records>{MAX_RECORDS_PER_REQUEST}</max_records>
    <search_criteria>
        <criteria><name>year</name><type>value</type><value>{year}</value></criteria>
    </search_criteria>
</request>"""
            try:
                resp = checkbook_post(payload, label="budget")
                root = ET.fromstring(resp.content)
            except (requests.exceptions.RequestException, ET.ParseError) as e:
                print(f"[budget] error at offset {offset}: {exc_str(e)}")
                break

            txns = root.findall(".//transaction")
            if not txns:
                break
            for txn in txns:
                writer.writerow(_row_from(txn))
                total += 1

            if dry_run or len(txns) < MAX_RECORDS_PER_REQUEST:
                break
            offset += MAX_RECORDS_PER_REQUEST
            time.sleep(1)

    print(f"[budget] Download complete: {total} records")
    return (output_file, total) if total else (None, 0)


async def run(dry_run: bool = False) -> dict:
    """Scheduler entrypoint — download current FY, upload to S3."""
    year = str(get_current_fiscal_year())
    csv_path, count = download_budget(year=year, dry_run=dry_run)
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
    ap = argparse.ArgumentParser(description="Download Checkbook NYC Budget")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--year", type=str, default=None)
    args = ap.parse_args()
    download_budget(year=args.year, dry_run=args.dry_run)
