from __future__ import annotations

"""
PASSPort / MOCS Data Extractor — scrapes vendor, contract, and solicitation data.

Consolidated from Databook Pipeline's extract_passport_data.py with improvements:
- No hardcoded AWS keys
- Async run() entry point for the data scheduler
- Shared S3 upload utility
"""

import csv
import json
import os
import re
import time
from urllib.parse import urljoin

import requests

from extractors import S3_BUCKET, S3_PREFIX, upload_to_s3

# PASSPort Public Data Sources
DATASETS = [
    {
        "name": "PASSPort Vendors",
        "url": "https://a0333-passportpublic.nyc.gov/vendor.html",
        "variable": "public_vend_data",
        "file_name": "vendor_data.csv",
        "script_pattern": r"vendorData\.js",
    },
    {
        "name": "PASSPort Contracts",
        "url": "https://a0333-passportpublic.nyc.gov/contracts.html",
        "variable": "public_ctr_data",
        "file_name": "contracts_data.csv",
        "script_pattern": r"contractData\.js",
    },
    {
        "name": "PASSPort Solicitations (RFx)",
        "url": "https://a0333-passportpublic.nyc.gov/rfx.html",
        "variable": "public_rfx_data",
        "file_name": "solicitations_data.csv",
        "script_pattern": r"rfxData\.js",
    },
]

# Column mappings verified against PASSPort data shape
HEADERS_MAPPING = {
    "PASSPort Vendors": [
        "PASSPort Supplier-ID", "Vendor Name", "PASSPort Vendor Status",
        "FMS Vendor Code", "DUNS Number", "OLD Certification Type",
        "Ethnicity", "Certification Type", "Business Category",
        "Corporate Structure", "Worker Coop check",
    ],
    "PASSPort Solicitations (RFx)": [
        "RFP-ID", "BPM-ID", "Program", "Industry", "EPIN",
        "Procurement Name", "Agency", "RFx Status", "Release Date",
        "Due Date", "Main Commodity", "Procurement Method",
    ],
    "PASSPort Contracts": [
        "CTR-ID", "EPIN", "Contract ID", "Contract Title", "Agency",
        "Vendor", "Program", "Procurement Method", "Contract Type", "Status",
        "Award Amount", "Current Contract Amount", "Total Encumbered Amount",
        "Total Paid Amount", "Contract Start Date", "Contract End Date",
        "Contract Registration Date", "Industry", "Unknown_18",
        "Certification Type", "Corporate Structure", "Ethnicity",
    ],
}


def _extract_json_from_text(text: str, variable_name: str):
    """Parse a JS variable assignment to extract JSON data."""
    pattern = re.compile(
        rf"(?:var|let|const)\s+{variable_name}\s*=\s*", re.IGNORECASE
    )
    match = pattern.search(text)
    if not match:
        return None

    start_index = match.end()
    current_index = start_index
    while current_index < len(text) and text[current_index].isspace():
        current_index += 1

    if current_index >= len(text):
        return None

    first_char = text[current_index]
    open_chars = {'{': '}', '[': ']'}
    if first_char not in open_chars:
        return None

    last_char_index = text.rfind(open_chars[first_char])
    if last_char_index <= current_index:
        return None

    json_str = text[current_index:last_char_index + 1]

    # Sanitize invalid escapes
    sanitize_pattern = r'\\(?![\\"/bfnrtu]|u[0-9a-fA-F]{4})'
    json_str_clean = re.sub(sanitize_pattern, r'\\\\', json_str)

    # Sanitize control chars inside strings
    string_regex = r'"([^"\\]*(?:\\.[^"\\]*)*)"'

    def sanitize_match(m):
        content = m.group(1)
        if '\n' in content or '\r' in content or '\t' in content:
            content = (content.replace('\n', '\\n')
                       .replace('\r', '\\r')
                       .replace('\t', '\\t'))
            return f'"{content}"'
        return m.group(0)

    json_str_clean = re.sub(string_regex, sanitize_match, json_str_clean)

    try:
        return json.loads(json_str_clean)
    except json.JSONDecodeError:
        try:
            import json5
            return json5.loads(json_str)
        except Exception:
            return None


def _extract_headers(html_content: str) -> list[str] | None:
    """Extract column headers from HTML <thead>."""
    thead_match = re.search(
        r'<thead[^>]*>(.*?)</thead>', html_content,
        re.IGNORECASE | re.DOTALL
    )
    if not thead_match:
        return None

    headers = re.findall(
        r'<th[^>]*>(.*?)</th>', thead_match.group(1),
        re.IGNORECASE | re.DOTALL
    )
    return [re.sub(r'<[^>]+>', '', h).strip() for h in headers]


def fetch_dataset(dataset: dict, dry_run: bool = False) -> tuple[str | None, int]:
    """
    Fetch and extract a single PASSPort dataset.

    Tries inline JS first, then looks for external script files.
    """
    print(f"[passport] Processing {dataset['name']}...")

    try:
        response = requests.get(dataset['url'], timeout=60)
        response.raise_for_status()
        html_content = response.text
    except Exception as e:
        print(f"[passport] Failed to fetch {dataset['url']}: {e}")
        return None, 0

    # Try extracting data from inline JS
    data = _extract_json_from_text(html_content, dataset['variable'])

    if data is None:
        # Look for external script
        soup_scripts = re.findall(
            r'<script[^>]+src=["\']([^"\']+)["\']', html_content
        )
        target_url = None
        for script_src in soup_scripts:
            if re.search(dataset.get('script_pattern', ''),
                         script_src, re.IGNORECASE):
                target_url = urljoin(dataset['url'], script_src)
                break

        if target_url:
            print(f"[passport] Fetching script: {target_url}")
            try:
                script_resp = requests.get(target_url, timeout=120)
                script_resp.raise_for_status()
                data = _extract_json_from_text(
                    script_resp.text, dataset['variable']
                )
            except Exception as e:
                print(f"[passport] Script fetch error: {e}")

    if not data or not isinstance(data, list):
        print(f"[passport] No data extracted for {dataset['name']}")
        return None, 0

    print(f"[passport] Extracted {len(data)} records")

    if dry_run:
        return None, len(data)

    # Write to CSV
    output_file = f"/tmp/{dataset['file_name']}"

    if not data:
        return None, 0

    first_item = data[0]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        if isinstance(first_item, dict):
            headers = _extract_headers(html_content)
            if not headers:
                headers = sorted(set().union(*(d.keys() for d in data)))
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)
        elif isinstance(first_item, list):
            writer = csv.writer(f)
            headers = _extract_headers(html_content)
            if not headers:
                headers = HEADERS_MAPPING.get(dataset['name'])
            if headers:
                # Pad/trim to match data width
                data_width = len(first_item)
                if len(headers) < data_width:
                    headers += [f"col_{i}" for i in range(len(headers), data_width)]
                elif len(headers) > data_width:
                    headers = headers[:data_width]
                writer.writerow(headers)
            else:
                writer.writerow([f"col_{i}" for i in range(len(first_item))])
            writer.writerows(data)

    return output_file, len(data)


async def run(dry_run: bool = False) -> dict:
    """
    Entry point for the data scheduler.

    Downloads all PASSPort datasets, uploads to S3.
    """
    results = {}

    for ds in DATASETS:
        csv_path, count = fetch_dataset(ds, dry_run=dry_run)

        if csv_path and count > 0:
            url = upload_to_s3(csv_path, ds['file_name'])
            if os.path.exists(csv_path):
                os.remove(csv_path)
            results[ds['name']] = {
                "status": "success", "rows": count, "s3_url": url
            }
        elif count > 0 and dry_run:
            results[ds['name']] = {
                "status": "success", "rows": count, "dry_run": True
            }
        else:
            results[ds['name']] = {
                "status": "fail", "rows": 0, "error": "No data extracted"
            }

    total = sum(r.get('rows', 0) for r in results.values())
    all_ok = all(r['status'] == 'success' for r in results.values())

    return {
        "status": "success" if all_ok else "partial",
        "rows": total,
        "datasets": results,
    }


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Extract PASSPort/MOCS Data"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(run(dry_run=args.dry_run))
