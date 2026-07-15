#!/usr/bin/env python3
"""Tier 3 ingest: pull contract "purpose" (scope) + spend/category/award-method
from the Checkbook NYC Contracts XML API into checkbook_contract_meta, scoped to
the contracts our Digital Services pages care about (digital-tagged vendors).

The Checkbook API filters by fiscal_year + status, not vendor, so we page through
the requested FYs and keep only records whose normalized contract id OR PIN
matches one of our target contracts. Match key verified: our
contracts.normalized_contract_id == norm(prime_contract_id); PIN↔epin is a fallback.

Run inside the api container:
    docker compose exec -T api python import_checkbook_contract_meta.py                 # expiring-before-2030 set
    docker compose exec -T api python import_checkbook_contract_meta.py --all            # all digital-vendor contracts
    docker compose exec -T api python import_checkbook_contract_meta.py --fy 2023 2024 2025 2026
"""
import argparse
import asyncio
import re
import xml.etree.ElementTree as ET

import requests

from modules import autoload  # noqa: F401  (sys.path + config bootstrap)
from postgrex import PostgresModelAsync  # noqa: E402

API_URL = "https://www.checkbooknyc.com/api"
PAGE = 1000
STATUSES = ["registered", "pending"]


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _fetch_fy(year: int, targets_id, targets_pin, sink: dict):
    """Page through one fiscal year, keeping records that match our targets.
    targets_id=None (all-contracts / Phase D mode) keeps every contract."""
    for status in STATUSES:
        offset = 1
        while True:
            payload = (f"<request><type_of_data>Contracts</type_of_data>"
                       f"<records_from>{offset}</records_from><max_records>{PAGE}</max_records>"
                       f"<search_criteria>"
                       f"<criteria><name>fiscal_year</name><type>value</type><value>{year}</value></criteria>"
                       f"<criteria><name>status</name><type>value</type><value>{status}</value></criteria>"
                       f"<criteria><name>category</name><type>value</type><value>all</value></criteria>"
                       f"</search_criteria></request>")
            try:
                resp = requests.post(API_URL, data=payload, timeout=180)
                recs = ET.fromstring(resp.content).findall(".//transaction")
            except Exception as exc:  # noqa: BLE001
                print(f"  FY{year}/{status} offset {offset}: ERROR {exc!r}", flush=True)
                break
            if not recs:
                break
            for c in recs:
                d = {e.tag: (e.text or "") for e in c}
                nid = _norm(d.get("prime_contract_id"))
                pin = (d.get("prime_contract_pin") or "").strip()
                if not nid:
                    continue
                # targets_id is None in all-contracts mode → keep every contract.
                if targets_id is not None and not (nid in targets_id or (pin and pin in targets_pin)):
                    continue
                purpose = (d.get("prime_contract_purpose") or "").strip()
                if nid not in sink or (purpose and len(purpose) > len(sink[nid]["purpose"])):
                    sink[nid] = {
                        "nid": nid, "pin": pin, "purpose": purpose,
                        "spent": d.get("prime_vendor_spent_to_date") or None,
                        "expense": (d.get("prime_contract_expense_category") or "").strip()[:200],
                        "award": (d.get("prime_contract_award_method") or "").strip()[:200],
                        "fy": str(year),
                    }
            offset += len(recs)
            if len(recs) < PAGE:
                break
        print(f"  FY{year}/{status}: matched so far {len(sink)}", flush=True)


UPSERT = """
INSERT INTO checkbook_contract_meta
    (normalized_contract_id, pin, purpose, spent_to_date, expense_category, award_method, source_fy, updated_at)
VALUES ($1,$2,$3,$4,$5,$6,$7, now())
ON CONFLICT (normalized_contract_id) DO UPDATE SET
    pin=EXCLUDED.pin, purpose=EXCLUDED.purpose, spent_to_date=EXCLUDED.spent_to_date,
    expense_category=EXCLUDED.expense_category, award_method=EXCLUDED.award_method,
    source_fy=EXCLUDED.source_fy, updated_at=now()
"""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="target all digital-vendor contracts (not just expiring<2030)")
    ap.add_argument("--all-contracts", dest="all_contracts", action="store_true",
                    help="Phase D: keep EVERY Checkbook contract (purpose/category for the whole universe), "
                         "not just digital-tagged vendors. Larger ingest — pair with a wide --fy.")
    ap.add_argument("--fy", type=int, nargs="+", default=[2023, 2024, 2025, 2026])
    args = ap.parse_args()

    if args.all_contracts:
        # Phase D: no target set — _fetch_fy keeps every contract in the requested FYs.
        targets_id = None
        targets_pin = None
        print(f"ALL-CONTRACTS mode (Phase D): keeping every Checkbook contract. "
              f"Scanning FYs {args.fy}…", flush=True)
    else:
        window = "" if args.all else (
            " AND c.end_date IS NOT NULL AND LENGTH(c.end_date)=10"
            " AND TO_DATE(c.end_date,'MM/DD/YYYY') >= CURRENT_DATE"
            " AND TO_DATE(c.end_date,'MM/DD/YYYY') < DATE '2030-01-01'")
        rows = await PostgresModelAsync.select_safe(f"""
            SELECT DISTINCT c.normalized_contract_id AS nid, trim(c.epin) AS pin
            FROM contracts c
            WHERE c.vendor_name IN (SELECT vendor_name FROM vendor_tags WHERE tag='digital_services'){window}
        """)
        targets_id = {r["nid"] for r in (rows or []) if r.get("nid")}
        targets_pin = {r["pin"] for r in (rows or []) if r.get("pin") and len(r["pin"]) >= 6}
        print(f"Targets: {len(targets_id)} contract ids, {len(targets_pin)} pins. "
              f"Scanning Checkbook FYs {args.fy}…", flush=True)

    sink = {}
    for fy in args.fy:
        await asyncio.to_thread(_fetch_fy, fy, targets_id, targets_pin, sink)

    print(f"Matched {len(sink)} contracts with Checkbook purpose data. Saving…", flush=True)
    saved = 0
    for v in sink.values():
        try:
            spent = float(v["spent"]) if v["spent"] not in (None, "", "-") else None
        except ValueError:
            spent = None
        try:
            await PostgresModelAsync.execute(UPSERT, [
                v["nid"], v["pin"] or None, v["purpose"][:2000] or None,
                spent, v["expense"] or None, v["award"] or None, v["fy"]])
            saved += 1
            if saved % 5000 == 0:
                print(f"  …upserted {saved}/{len(sink)}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  save {v['nid']}: ERROR {exc!r}", flush=True)
    print(f"Done. Upserted {saved}.")


if __name__ == "__main__":
    asyncio.run(main())
