from __future__ import annotations

"""
Checkbook NYC — NYCHA Revenue extractor (type_of_data=Revenue_NYCHA).

NYCHA's own revenue (adopted / modified / recognized / remaining), dominated by
federal operating subsidies (Section 8 / vouchers) rather than City tax revenue.
No `agency` dimension — the axes are `revenue_category` / `revenue_class` /
`funding_source` / `responsibility_center` / `budget_type`. Small aggregate feed
(~19k rows/FY) → a single Parquet. Mirrors checkbook_revenue.py.

NOTE: the criterion is `budget_fiscal_year` (NOT `fiscal_year` or `year`); the
year IS returned in that column.
"""

import csv
import os
import time
import xml.etree.ElementTree as ET

import requests

from extractors import checkbook_post, clean_text, get_current_fiscal_year, upload_to_s3
from modules.errfmt import exc_str

API_URL = "https://www.checkbooknyc.com/api"
FILE_NAME = "nycha_revenue_data.csv"
MAX_RECORDS_PER_REQUEST = 20000  # revenue is small; big pages keep it to one/few calls

# Columns the Revenue_NYCHA feed returns (verified live 2026-07). All flat.
COLUMNS = [
    "budget_fiscal_year", "budget_name", "budget_type", "closing_classification_name",
    "revenue_expense_category", "funding_source", "program", "project",
    "responsibility_center", "revenue_category", "revenue_class",
    "adopted", "modified", "recognized", "remaining",
]


def download_revenue_nycha(year: str = None, dry_run: bool = False) -> tuple[str | None, int]:
    """Download NYCHA revenue for a fiscal year. Returns (csv_path|None, count)."""
    if year is None:
        year = str(get_current_fiscal_year())
    print(f"[nycha-revenue] Starting download (FY {year})...")

    output_file = f"/tmp/{FILE_NAME}"
    offset = 1
    total = 0
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        while True:
            payload = f"""<request>
    <type_of_data>Revenue_NYCHA</type_of_data>
    <records_from>{offset}</records_from>
    <max_records>{MAX_RECORDS_PER_REQUEST}</max_records>
    <search_criteria>
        <criteria><name>budget_fiscal_year</name><type>value</type><value>{year}</value></criteria>
    </search_criteria>
</request>"""
            try:
                resp = checkbook_post(payload, label="nycha-revenue")
                root = ET.fromstring(resp.content)
            except (requests.exceptions.RequestException, ET.ParseError) as e:
                print(f"[nycha-revenue] error at offset {offset}: {exc_str(e)}")
                break

            txns = root.findall(".//transaction")
            if not txns:
                break
            for txn in txns:
                row = {c: "" for c in COLUMNS}
                for child in txn:
                    if child.tag in row:
                        row[child.tag] = clean_text(child.text)
                writer.writerow(row)
                total += 1

            if dry_run or len(txns) < MAX_RECORDS_PER_REQUEST:
                break
            offset += MAX_RECORDS_PER_REQUEST
            time.sleep(1)

    print(f"[nycha-revenue] Download complete: {total} records")
    return (output_file, total) if total else (None, 0)


async def run(dry_run: bool = False) -> dict:
    """Scheduler entrypoint — download current FY, upload to S3."""
    year = str(get_current_fiscal_year())
    csv_path, count = download_revenue_nycha(year=year, dry_run=dry_run)
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
    ap = argparse.ArgumentParser(description="Download Checkbook NYC NYCHA Revenue")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--year", type=str, default=None)
    args = ap.parse_args()
    download_revenue_nycha(year=args.year, dry_run=args.dry_run)
