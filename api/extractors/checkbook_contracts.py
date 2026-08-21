from __future__ import annotations

"""
Checkbook NYC Contracts Extractor — downloads contract data via XML API.

Consolidated from Databook Pipeline's download_contracts.py with improvements:
- Dynamic fiscal year
- S3 credentials via environment
- Async run() entry point for the data scheduler
"""

import csv
import os
import time
import xml.etree.ElementTree as ET

import requests

from extractors import (
    S3_BUCKET, S3_PREFIX, clean_text,
    get_current_fiscal_year, upload_to_s3,
)
from modules.errfmt import exc_str

# Checkbook NYC XML API
API_URL = "https://www.checkbooknyc.com/api"
FILE_NAME = "contracts_data.csv"
MAX_RECORDS_PER_REQUEST = 2000
STATUSES = ['active', 'registered']


def download_contracts(year: str = None, dry_run: bool = False) -> tuple[str | None, int]:
    """
    Download Checkbook NYC contracts for a given fiscal year.

    Iterates over 'active' and 'registered' statuses, combining results.

    Args:
        year: Fiscal year to download. Defaults to current NYC fiscal year.
        dry_run: If True, stop after first batch per status.

    Returns:
        Tuple of (local CSV path or None, record count).
    """
    if year is None:
        year = str(get_current_fiscal_year())

    print(f"[contracts] Starting download (FY {year})...")

    output_file = f"/tmp/{FILE_NAME}"
    total_records = 0
    writer = None
    fieldnames = []

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        for status in STATUSES:
            print(f"[contracts] Fetching status: {status}")
            offset = 1

            while True:
                payload = f"""<request>
    <type_of_data>Contracts</type_of_data>
    <records_from>{offset}</records_from>
    <max_records>{MAX_RECORDS_PER_REQUEST}</max_records>
    <search_criteria>
        <criteria>
            <name>fiscal_year</name>
            <type>value</type>
            <value>{year}</value>
        </criteria>
        <criteria>
            <name>status</name>
            <type>value</type>
            <value>{status}</value>
        </criteria>
        <criteria>
            <name>category</name>
            <type>value</type>
            <value>all</value>
        </criteria>
    </search_criteria>
</request>"""

                try:
                    response = requests.post(API_URL, data=payload, timeout=60)
                    response.raise_for_status()

                    try:
                        root = ET.fromstring(response.content)
                    except ET.ParseError:
                        print("[contracts] XML parse error, skipping batch")
                        break

                    # Check for API-level error
                    status_node = root.find('status')
                    if status_node is not None:
                        result = status_node.find('result')
                        if result is not None and result.text == 'failure':
                            print(f"[contracts] API error for {status}")
                            break

                    records = root.findall(".//contract")
                    if not records:
                        records = root.findall(".//transaction")

                    if not records:
                        print(f"[contracts] No records at offset {offset} "
                              f"for {status}")
                        break

                    if writer is None and records:
                        fieldnames = [elem.tag for elem in records[0]]
                        fieldnames.append('extraction_status_filter')
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()

                    for record in records:
                        row = {child.tag: clean_text(child.text)
                               for child in record}
                        row['extraction_status_filter'] = status
                        csv_row = {k: row.get(k, '') for k in fieldnames}
                        writer.writerow(csv_row)

                    total_records += len(records)
                    offset += len(records)

                    if len(records) < MAX_RECORDS_PER_REQUEST:
                        break

                    if dry_run:
                        print("[contracts] Dry run — stopping per status")
                        break

                    time.sleep(1)

                except Exception as e:
                    print(f"[contracts] Error: {exc_str(e)}")
                    break

    print(f"[contracts] Download complete: {total_records} records")

    if total_records == 0:
        return None, 0

    return output_file, total_records


async def run(dry_run: bool = False) -> dict:
    """Entry point for the data scheduler."""
    year = str(get_current_fiscal_year())
    csv_path, count = download_contracts(year=year, dry_run=dry_run)

    if not csv_path or count == 0:
        return {"status": "fail", "error": "No records downloaded", "rows": 0}

    if dry_run:
        return {"status": "success", "rows": count, "dry_run": True}

    url = upload_to_s3(csv_path, FILE_NAME)

    if os.path.exists(csv_path):
        os.remove(csv_path)

    if url:
        return {"status": "success", "rows": count, "s3_url": url}
    return {"status": "fail", "error": "S3 upload failed", "rows": count}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download Checkbook NYC Contracts"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--year", type=str, default=None,
                        help=f"Fiscal year (default: {get_current_fiscal_year()})")
    args = parser.parse_args()

    download_contracts(year=args.year, dry_run=args.dry_run)
