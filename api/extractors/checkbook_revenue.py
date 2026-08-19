from __future__ import annotations

"""
Checkbook NYC Revenue Extractor — downloads revenue records via the XML API.

Revenue is the City's recognized/collected revenue by agency, revenue class, and
source (adopted vs modified vs recognized). Far smaller than Spending — agency ×
revenue-source aggregates, not per-payment rows — so it lands as a single Parquet
(no chunking). Mirrors checkbook_spending.py.
"""

import csv
import os
import time
import xml.etree.ElementTree as ET

import requests

from extractors import checkbook_post, clean_text, get_current_fiscal_year, upload_to_s3
from modules.errfmt import exc_str

API_URL = "https://www.checkbooknyc.com/api"
FILE_NAME = "revenue_data.csv"
MAX_RECORDS_PER_REQUEST = 20000  # revenue is small; big pages keep it to one/few calls

# Columns the Revenue domain returns (verified against the live API 2026-07).
COLUMNS = [
    "agency", "revenue_category", "revenue_source", "fund_class", "funding_class",
    "revenue_class", "budget_fiscal_year", "fiscal_year",
    "adopted", "modified", "recognized", "closing_classification_name",
]


def download_revenue(year: str = None, dry_run: bool = False) -> tuple[str | None, int]:
    """Download Checkbook NYC revenue for a fiscal year. Returns (csv_path|None, count)."""
    if year is None:
        year = str(get_current_fiscal_year())
    print(f"[revenue] Starting download (FY {year})...")

    output_file = f"/tmp/{FILE_NAME}"
    offset = 1
    total = 0
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        while True:
            payload = f"""<request>
    <type_of_data>Revenue</type_of_data>
    <records_from>{offset}</records_from>
    <max_records>{MAX_RECORDS_PER_REQUEST}</max_records>
    <search_criteria>
        <criteria><name>fiscal_year</name><type>value</type><value>{year}</value></criteria>
    </search_criteria>
</request>"""
            try:
                resp = checkbook_post(payload, label="revenue")
                root = ET.fromstring(resp.content)
            except (requests.exceptions.RequestException, ET.ParseError) as e:
                print(f"[revenue] error at offset {offset}: {exc_str(e)}")
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

    print(f"[revenue] Download complete: {total} records")
    return (output_file, total) if total else (None, 0)


async def run(dry_run: bool = False) -> dict:
    """Scheduler entrypoint — download current FY, upload to S3."""
    year = str(get_current_fiscal_year())
    csv_path, count = download_revenue(year=year, dry_run=dry_run)
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
    ap = argparse.ArgumentParser(description="Download Checkbook NYC Revenue")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--year", type=str, default=None)
    args = ap.parse_args()
    download_revenue(year=args.year, dry_run=args.dry_run)
