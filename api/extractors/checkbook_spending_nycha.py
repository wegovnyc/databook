from __future__ import annotations

"""
Checkbook NYC — NYCHA Spending extractor (type_of_data=Spending_NYCHA).

NYCHA's own payment transactions, published by CheckbookNYC as a parallel
`_NYCHA` feed. Per-payment grain (~2.85M rows/FY, ~41.7M all-time), per-FY
filterable via `fiscal_year`, so it lands as a PARTITIONED Parquet lake
(fiscal_year=<FY>/chunk_*.parquet) like the City spending lake — see
build_nycha_spending_parquet.py + routers/nycha.py.

NYCHA spending has no `agency`/`department`; its axes are `responsibility_center`
(developments + functional units), `funding_source` (federal Section 8 vs City vs
capital), `spending_category`, and the `section_8` flag. The response includes the
fiscal year in the `year` tag.
"""

import csv
import os
import xml.etree.ElementTree as ET

import requests  # noqa: F401  (kept for the RequestException type in callers)

from extractors import checkbook_post, clean_text, get_current_fiscal_year, upload_to_s3
from modules.errfmt import exc_str

API_URL = "https://www.checkbooknyc.com/api"
FILE_NAME = "nycha_spending_data.csv"
MAX_RECORDS_PER_REQUEST = 20000

# Every response column we keep (verified against the live Spending_NYCHA feed
# 2026-07). Requested explicitly so the CSV schema is stable.
RESPONSE_COLUMNS = [
    "year", "issue_date", "document_id", "section_8", "purchase_order_type",
    "contract_id", "release_number", "invoice_number", "check_status",
    "check_amount", "amount_spent", "vendor", "purpose", "spending_category",
    "industry", "funding_source", "responsibility_center", "expense_category",
    "program", "project",
]
_RESPONSE_COLUMNS_XML = (
    "<response_columns>"
    + "".join(f"<column>{c}</column>" for c in RESPONSE_COLUMNS)
    + "</response_columns>"
)


def download_spending_nycha(year: str = None, dry_run: bool = False) -> tuple[str | None, int]:
    """Download NYCHA spending transactions for a fiscal year. Returns (csv_path|None, count)."""
    if year is None:
        year = str(get_current_fiscal_year())
    print(f"[nycha-spending] Starting download (FY {year})...")

    output_file = f"/tmp/{FILE_NAME}"
    offset = 1
    total = 0
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = None
        while True:
            payload = f"""<request>
    <type_of_data>Spending_NYCHA</type_of_data>
    <records_from>{offset}</records_from>
    <max_records>{MAX_RECORDS_PER_REQUEST}</max_records>
    <search_criteria>
        <criteria><name>fiscal_year</name><type>value</type><value>{year}</value></criteria>
    </search_criteria>
    {_RESPONSE_COLUMNS_XML}
</request>"""
            try:
                resp = checkbook_post(payload, label="nycha-spending")
                root = ET.fromstring(resp.content)
            except (requests.exceptions.RequestException, ET.ParseError) as e:
                print(f"[nycha-spending] error at offset {offset}: {exc_str(e)}")
                break

            txns = root.findall(".//transaction")
            if not txns:
                break
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=RESPONSE_COLUMNS)
                writer.writeheader()
            for txn in txns:
                row = {c: "" for c in RESPONSE_COLUMNS}
                for child in txn:
                    if child.tag in row:
                        row[child.tag] = clean_text(child.text)
                writer.writerow(row)
                total += 1

            if dry_run or len(txns) < MAX_RECORDS_PER_REQUEST:
                break
            offset += MAX_RECORDS_PER_REQUEST

    print(f"[nycha-spending] Download complete: {total} records")
    return (output_file, total) if total else (None, 0)


async def run(dry_run: bool = False) -> dict:
    """Scheduler entrypoint — download current FY, upload to S3."""
    year = str(get_current_fiscal_year())
    csv_path, count = download_spending_nycha(year=year, dry_run=dry_run)
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
    ap = argparse.ArgumentParser(description="Download Checkbook NYC NYCHA Spending")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--year", type=str, default=None)
    args = ap.parse_args()
    download_spending_nycha(year=args.year, dry_run=args.dry_run)
