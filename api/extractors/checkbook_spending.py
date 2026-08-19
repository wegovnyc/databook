from __future__ import annotations

"""
Checkbook NYC Spending Extractor — downloads spending transactions via XML API.

Consolidated from Databook Pipeline's download_spending.py with improvements:
- Dynamic fiscal year (no more hardcoded 2025)
- S3 credentials via environment (no hardcoded keys)
- Can be called programmatically from the data scheduler
"""

import csv
import os
import time
import xml.etree.ElementTree as ET

import requests

from extractors import (
    S3_BUCKET, S3_PREFIX, checkbook_post, clean_text,
    get_current_fiscal_year, upload_to_s3,
)
from modules.errfmt import exc_str

# Checkbook NYC XML API
API_URL = "https://www.checkbooknyc.com/api"
FILE_NAME = "spending_data.csv"
# Checkbook honours up to 20,000 rows/request for Spending (50,000 is rejected).
# Larger pages cut request count ~10x, which slashes both the per-request rate-limit
# sleeps AND Checkbook's offset re-scan cost (server re-scans from row 1 each request,
# so total work scales as rows^2/batch) — a ~7x end-to-end speedup vs the old 2,000.
# Env-overridable so ops can dial it back if Checkbook ever tightens the cap.
MAX_RECORDS_PER_REQUEST = int(os.environ.get("CHECKBOOK_MAX_RECORDS", "20000"))

# Explicitly request every spending column we depend on, so the CSV schema is
# stable regardless of Checkbook's default response set. Includes the M/WBE
# (mwbe_category / woman_owned_business / emerging_business) and document-level
# fields that build_spending_parquet.py keeps for the v2 Parquet. Verified against
# the live API 2026-07 — these are the tags a Spending <transaction> returns.
RESPONSE_COLUMNS = [
    "agency", "payee_name", "check_amount", "fiscal_year", "issue_date",
    "industry", "spending_category", "contract_id", "department",
    "expense_category", "budget_code", "sub_vendor", "associated_prime_vendor",
    "mwbe_category", "woman_owned_business", "emerging_business",
    "capital_project", "mocs_registered", "contract_purpose",
    "document_id", "sub_contract_reference_id",
]

_RESPONSE_COLUMNS_XML = (
    "<response_columns>"
    + "".join(f"<column>{c}</column>" for c in RESPONSE_COLUMNS)
    + "</response_columns>"
)


def download_spending(year: str = None, dry_run: bool = False) -> tuple[str | None, int]:
    """
    Download Checkbook NYC spending transactions for a given fiscal year.

    Args:
        year: Fiscal year to download. Defaults to current NYC fiscal year.
        dry_run: If True, download only one batch and skip S3 upload.

    Returns:
        Tuple of (local CSV path or None, record count).
    """
    if year is None:
        year = str(get_current_fiscal_year())

    print(f"[spending] Starting download (FY {year})...")

    output_file = f"/tmp/{FILE_NAME}"
    offset = 1
    total_records = 0

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = None

        while True:
            payload = f"""<request>
    <type_of_data>Spending</type_of_data>
    <records_from>{offset}</records_from>
    <max_records>{MAX_RECORDS_PER_REQUEST}</max_records>
    <search_criteria>
        <criteria>
            <name>fiscal_year</name>
            <type>value</type>
            <value>{year}</value>
        </criteria>
    </search_criteria>
    {_RESPONSE_COLUMNS_XML}
</request>"""

            try:
                response = checkbook_post(payload, timeout=60, label="spending")
            except requests.exceptions.RequestException as e:
                print(f"[spending] API error at offset {offset}: {exc_str(e)}")
                break

            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                print(f"[spending] XML parse error: {exc_str(e)}")
                break

            transactions = root.findall(".//transaction")

            if not transactions:
                print(f"[spending] No more transactions at offset {offset}")
                break

            if writer is None:
                headers = [child.tag for child in transactions[0]]
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()

            for txn in transactions:
                row = {child.tag: clean_text(child.text) for child in txn}
                writer.writerow(row)
                total_records += 1

            if dry_run:
                print("[spending] Dry run — stopping after first batch")
                break

            if len(transactions) < MAX_RECORDS_PER_REQUEST:
                break

            offset += MAX_RECORDS_PER_REQUEST
            time.sleep(1)  # Rate limiting

    print(f"[spending] Download complete: {total_records} records")

    if total_records == 0:
        return None, 0

    return output_file, total_records


async def run(dry_run: bool = False) -> dict:
    """
    Entry point for the data scheduler.

    Downloads spending data, uploads to S3, returns result dict.
    """
    year = str(get_current_fiscal_year())
    csv_path, count = download_spending(year=year, dry_run=dry_run)

    if not csv_path or count == 0:
        return {"status": "fail", "error": "No records downloaded", "rows": 0}

    if dry_run:
        return {"status": "success", "rows": count, "dry_run": True}

    url = upload_to_s3(csv_path, FILE_NAME)

    # Clean up temp file
    if os.path.exists(csv_path):
        os.remove(csv_path)

    if url:
        return {"status": "success", "rows": count, "s3_url": url}
    return {"status": "fail", "error": "S3 upload failed", "rows": count}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download Checkbook NYC Spending")
    parser.add_argument("--dry-run", action="store_true",
                        help="Download one batch only, skip S3")
    parser.add_argument("--year", type=str, default=None,
                        help=f"Fiscal year (default: {get_current_fiscal_year()})")
    args = parser.parse_args()

    download_spending(year=args.year, dry_run=args.dry_run)
