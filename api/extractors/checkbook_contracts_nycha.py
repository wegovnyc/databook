from __future__ import annotations

"""
Checkbook NYC — NYCHA Contracts extractor (type_of_data=Contracts_NYCHA).

NYCHA's own contracts/agreements, published by CheckbookNYC as a parallel
`_NYCHA` feed. The feed is LINE/RELEASE-granular (~2M rows/FY; multiple rows per
contract), so we keep only the contract-level columns and let the API aggregate
to contract grain at query time (GROUP BY contract_id — see routers/nycha.py),
mirroring how the Revenue feed's denormalization is handled.

Criterion is `fiscal_year` (verified live 2026-07). The response does NOT echo the
year back, so we inject the queried fiscal_year per row (like the NYCHA Budget
feed). A contract active across several FYs appears in each year's pull; the
query-time GROUP BY collapses those to one row per contract (MAX of the constant
contract-level amounts), so the union is safe.
"""

import csv
import os
import time
import xml.etree.ElementTree as ET

import requests

from extractors import checkbook_post, clean_text, get_current_fiscal_year, upload_to_s3

API_URL = "https://www.checkbooknyc.com/api"
FILE_NAME = "nycha_contracts_data.csv"
MAX_RECORDS_PER_REQUEST = 20000

# Contract-level columns kept for the contracts explorer (the feed also returns
# line_*/release_*/item_* detail, dropped here — a v1 explorer is contract-grain).
# `fiscal_year` is injected from the request. Verified against the live feed 2026-07.
COLUMNS = [
    "fiscal_year", "contract_id", "vendor", "purpose", "location",
    "contract_type", "record_type", "purchase_order_type", "award_method",
    "industry", "funding_source", "responsibility_center", "pin", "program",
    "project", "expenditure_type", "grant_name",
    "start_date", "end_date", "approved_date", "number_of_releases",
    "contract_original_amount", "contract_current_amount", "contract_invoiced_amount",
]


def download_contracts_nycha(year: str = None, dry_run: bool = False) -> tuple[str | None, int]:
    """Download NYCHA contracts (line-grain) for a fiscal year. Returns (csv_path|None, count)."""
    if year is None:
        year = str(get_current_fiscal_year())
    print(f"[nycha-contracts] Starting download (FY {year})...")

    output_file = f"/tmp/{FILE_NAME}"
    offset = 1
    total = 0
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        while True:
            payload = f"""<request>
    <type_of_data>Contracts_NYCHA</type_of_data>
    <records_from>{offset}</records_from>
    <max_records>{MAX_RECORDS_PER_REQUEST}</max_records>
    <search_criteria>
        <criteria><name>fiscal_year</name><type>value</type><value>{year}</value></criteria>
    </search_criteria>
</request>"""
            try:
                resp = checkbook_post(payload, label="nycha-contracts")
                root = ET.fromstring(resp.content)
            except (requests.exceptions.RequestException, ET.ParseError) as e:
                print(f"[nycha-contracts] error at offset {offset}: {e}")
                break

            txns = root.findall(".//transaction")
            if not txns:
                break
            for txn in txns:
                row = {c: "" for c in COLUMNS}
                row["fiscal_year"] = year
                for child in txn:
                    if child.tag in row and child.tag != "fiscal_year":
                        row[child.tag] = clean_text(child.text)
                writer.writerow(row)
                total += 1

            if dry_run or len(txns) < MAX_RECORDS_PER_REQUEST:
                break
            offset += MAX_RECORDS_PER_REQUEST
            time.sleep(1)

    print(f"[nycha-contracts] Download complete: {total} records")
    return (output_file, total) if total else (None, 0)


async def run(dry_run: bool = False) -> dict:
    """Scheduler entrypoint — download current FY, upload to S3."""
    year = str(get_current_fiscal_year())
    csv_path, count = download_contracts_nycha(year=year, dry_run=dry_run)
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
    ap = argparse.ArgumentParser(description="Download Checkbook NYC NYCHA Contracts")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--year", type=str, default=None)
    args = ap.parse_args()
    download_contracts_nycha(year=args.year, dry_run=args.dry_run)
