#!/usr/bin/env python3
"""Apply contract-grain enrichment corrections from the curated seed.

⚠⚠ THIS IS THE MECHANISM THE $929M HOTEL CONTRACT FORCED. The classifier filed
"Hotel Management Svcs for DHS Emergency Programs" — hotel rooms for homeless
services — as tech_relevant, function "Data/analytics". Family-grain curation
cannot reach it (services have no licence family), so contract-grain judgements
need their own version-controlled home: api/seed/contract_enrichment_curated.csv.

Rows here are applied to digital_contract_enrichment with curated = true, which
the classifier NEVER overwrites (its UPDATE carries WHERE curated = false), so a
decision survives every re-run — the same guarantee the licence seeds have.

⚠ BLANK MEANS KEEP. A row correcting only tech_relevant leaves the AI's
function_category standing, and vice versa — the Microsoft-capability precedent.

    docker compose exec -T api python seed_contract_enrichment.py          # dry run
    docker compose exec -T api python seed_contract_enrichment.py --apply
"""
import argparse
import asyncio
import csv
import os
import sys

from modules import autoload  # noqa: F401,E402
from postgrex import PostgresModelAsync  # noqa: E402

SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "seed", "contract_enrichment_curated.csv")


def read_seed():
    with open(SEED, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    rows = []
    for r in csv.DictReader(lines):
        cid = (r.get("contract_id") or "").strip()
        if not cid:
            continue
        assert None not in r, f"malformed CSV row (unquoted comma?): {r}"
        rows.append(r)
    return rows


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write; default is dry run")
    args = ap.parse_args()

    rows = read_seed()
    if not rows:
        print("seed is empty — nothing to do")
        return 0

    applied, missing = 0, []
    for r in rows:
        cid = r["contract_id"].strip()
        exists = await PostgresModelAsync.select_safe(
            "SELECT curated FROM digital_contract_enrichment WHERE contract_id = $1", [cid])
        if not exists:
            # ⚠ Report, never invent: a correction for a row the classifier has
            # not produced would fabricate an enrichment record from thin air.
            missing.append(cid)
            continue

        sets, params = ["curated = true"], []
        # ⚠ `shown` carries the VALUES for the log. Printing the SQL fragment
        # instead ("tech_relevant = $1") tells a reader which column moved but
        # not what it moved to — a log that looks informative and is not.
        shown = []
        tr = (r.get("tech_relevant") or "").strip()
        if tr in ("0", "1"):
            params.append(tr == "1")
            sets.append(f"tech_relevant = ${len(params)}")
            shown.append(f"tech_relevant -> {tr == '1'}")
        fc = (r.get("function_category") or "").strip()
        if fc:
            params.append(fc)
            sets.append(f"function_category = ${len(params)}")
            shown.append(f"function_category -> {fc!r}")
        params.append(cid)
        q = (f"UPDATE digital_contract_enrichment SET {', '.join(sets)} "
             f"WHERE contract_id = ${len(params)}")
        if args.apply:
            await PostgresModelAsync.select_safe(q, params)
        applied += 1
        print(f"  {'applied' if args.apply else 'would apply'}  {cid}: "
              + ", ".join(shown or ["(curated flag only)"])
              + (f"  -- {r.get('note','')[:60]}" if r.get("note") else ""))

    if missing:
        print(f"  ⚠ {len(missing)} seed rows match NO enrichment record (skipped): {missing}")
    print(f"{'applied' if args.apply else 'dry run:'} {applied} corrections"
          + ("" if args.apply else " — re-run with --apply"))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
