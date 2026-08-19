from __future__ import annotations

"""
Checkbook NYC Payroll extractor (type_of_data=Payroll, criterion=fiscal_year).

The Payroll feed is ~10M detail rows per fiscal year (one row per payment record;
NO employee names — aggregated at agency/title/pay-date grain, so there is ZERO
PII). Downloading 10M raw rows to CSV would be 1-2 GB per FY, so this
STREAM-AGGREGATES as it paginates into an ANNUAL ROLLUP at
(agency, title, payroll_type) grain and writes a small rollup CSV per FY.

Amounts: gross_pay / base_pay / overtime_payments / other_payments are per-row and
ADDITIVE -> summed. gross_pay_ytd is cumulative (NOT additive) -> dropped.
annual_salary is a rate, not an amount, and is 0/blank for many titles (e.g. DOE
pedagogues) -> tracked as sum+count+min+max over the POSITIVE values only, so the
API can report a headcount-free average annual salary for salaried positions.
`records` = number of payment rows (NOT a distinct-employee headcount — the feed
carries no employee id, so a true headcount isn't derivable).

Mirrors checkbook_budget.py (single-file domain, criterion differs). Built into a
Parquet by build_budget_revenue_parquet.py (domain "payroll"); served by
routers/payroll.py.
"""

import csv
import os
import time
import xml.etree.ElementTree as ET

import requests

from extractors import checkbook_post, clean_text, get_current_fiscal_year, upload_to_s3
from modules.errfmt import exc_str

FILE_NAME = "payroll_data.csv"
MAX_RECORDS_PER_REQUEST = 20000

# Rollup CSV schema (annual grain). Mirrors the build "payroll" domain spec.
COLUMNS = ["fiscal_year", "agency", "title", "payroll_type",
           "gross", "base", "overtime", "other", "records",
           "salary_sum", "salary_count", "salary_min", "salary_max"]


def _num(text: str | None) -> float:
    try:
        return float((text or "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def download_payroll(year: str = None, dry_run: bool = False) -> tuple[str | None, int]:
    """Download + roll up Checkbook NYC payroll for a fiscal year. Returns
    (rollup_csv_path|None, rollup_row_count)."""
    if year is None:
        year = str(get_current_fiscal_year())
    print(f"[payroll] Starting download (FY {year})...")

    # (agency, title, payroll_type) -> aggregate dict
    agg: dict[tuple, dict] = {}
    offset = 1
    rows_in = 0
    while True:
        payload = f"""<request>
    <type_of_data>Payroll</type_of_data>
    <records_from>{offset}</records_from>
    <max_records>{MAX_RECORDS_PER_REQUEST}</max_records>
    <search_criteria>
        <criteria><name>fiscal_year</name><type>value</type><value>{year}</value></criteria>
    </search_criteria>
</request>"""
        try:
            resp = checkbook_post(payload, label="payroll")
            root = ET.fromstring(resp.content)
        except (requests.exceptions.RequestException, ET.ParseError) as e:
            print(f"[payroll] error at offset {offset}: {exc_str(e)}")
            break

        txns = root.findall(".//transaction")
        if not txns:
            break
        for txn in txns:
            d = {c.tag: c.text for c in txn}
            key = (clean_text(d.get("agency")), clean_text(d.get("title")),
                   clean_text(d.get("payroll_type")))
            a = agg.get(key)
            if a is None:
                a = agg[key] = {"gross": 0.0, "base": 0.0, "overtime": 0.0, "other": 0.0,
                                "records": 0, "salary_sum": 0.0, "salary_count": 0,
                                "salary_min": None, "salary_max": None}
            a["gross"] += _num(d.get("gross_pay"))
            a["base"] += _num(d.get("base_pay"))
            a["overtime"] += _num(d.get("overtime_payments"))
            a["other"] += _num(d.get("other_payments"))
            a["records"] += 1
            sal = _num(d.get("annual_salary"))
            if sal > 0:
                a["salary_sum"] += sal
                a["salary_count"] += 1
                a["salary_min"] = sal if a["salary_min"] is None else min(a["salary_min"], sal)
                a["salary_max"] = sal if a["salary_max"] is None else max(a["salary_max"], sal)
            rows_in += 1

        if rows_in % 200000 < MAX_RECORDS_PER_REQUEST:
            print(f"[payroll] FY{year}: {rows_in:,} rows read, {len(agg):,} groups so far")
        if dry_run or len(txns) < MAX_RECORDS_PER_REQUEST:
            break
        offset += MAX_RECORDS_PER_REQUEST
        time.sleep(1)

    if not agg:
        print(f"[payroll] FY{year}: no records")
        return None, 0

    output_file = f"/tmp/{FILE_NAME}"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for (agency, title, ptype), a in agg.items():
            w.writerow({
                "fiscal_year": year, "agency": agency, "title": title, "payroll_type": ptype,
                "gross": round(a["gross"], 2), "base": round(a["base"], 2),
                "overtime": round(a["overtime"], 2), "other": round(a["other"], 2),
                "records": a["records"], "salary_sum": round(a["salary_sum"], 2),
                "salary_count": a["salary_count"],
                "salary_min": "" if a["salary_min"] is None else a["salary_min"],
                "salary_max": "" if a["salary_max"] is None else a["salary_max"],
            })
    print(f"[payroll] FY{year}: {rows_in:,} detail rows -> {len(agg):,} rollup rows -> {output_file}")
    return output_file, len(agg)


async def run(dry_run: bool = False) -> dict:
    """Scheduler entrypoint — download current FY, upload rollup CSV to S3."""
    year = str(get_current_fiscal_year())
    csv_path, count = download_payroll(year=year, dry_run=dry_run)
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
    ap = argparse.ArgumentParser(description="Download + roll up Checkbook NYC Payroll")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--year", type=str, default=None)
    args = ap.parse_args()
    download_payroll(year=args.year, dry_run=args.dry_run)
