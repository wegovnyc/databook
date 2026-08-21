#!/usr/bin/env python3
"""Generate the review worksheet for the largest non-licence tech contracts.

⚠⚠ WHY THIS EXISTS. The Overview redesign's composition bar segments come from
`digital_contract_enrichment.function_category` — the classifier's free-text
bucket, with NO curation layer. Measured 2026-08-12: the "Data/analytics"
segment read $2,137M, of which $1,927M — 90% — was TWO misfiled contracts (a
$998M camera-enforcement program, and $929M of hotel management for homeless
services that is not technology at all). If one segment's top rows can hide a
$1.93B error, every segment's top rows are suspect until a human looks.

The top ~30 non-licence tech contracts by value dominate every segment, so this
worksheet is the composition bar's publication gate — the same
top-N-by-value discipline as the licence review, one grain down.
Licence-classified contracts are excluded: they already have family-grain
review.

⚠ RE-RUNNING NEVER DISCARDS A DECISION. Existing verdicts are read back and
preserved, same rule as build_review_worksheet.py.

Decisions are applied via api/seed/contract_enrichment_curated.csv (see
seed_contract_enrichment.py) — the worksheet is where you DECIDE, the seed is
where the decision LIVES.

    docker compose exec -T api python build_contract_review_worksheet.py
    docker compose exec -T api python build_contract_review_worksheet.py --top 50
"""
import argparse
import asyncio
import csv
import os
import sys

from modules import autoload  # noqa: F401,E402
from postgrex import PostgresModelAsync  # noqa: E402

# ⚠ Shares production's query and enrichment — a harness that rebuilds them
# measures a different system (the org-crosswalk suffix-list lesson).
import classify_digital_contracts as clf  # noqa: E402

# ⚠ Same un-normalized-root trap note as build_review_worksheet.py: __file__ is
# "<stdin>" when piped; fall back to cwd (which is /app in the container).
_here = os.path.abspath(__file__) if os.path.exists(__file__) else os.path.abspath(os.getcwd() + "/x")
ROOT = os.environ.get("REVIEW_ROOT") or os.path.dirname(_here)
OUT = os.path.join(ROOT, "docs", "contract-review-worksheet.csv")

FIELDS = ["rank", "contract_id", "value_usd", "contract_title", "vendor_name",
          "agency", "start_date", "end_date", "procurement_method",
          "ai_function_category", "ai_rationale",
          "contract_purpose", "main_commodity", "notice_description",
          # ---- decision columns (yours) ----
          "verdict",             # ok | wrong-function | not-tech | unsure
          "correct_tech_relevant",   # 0/1, only when verdict says so
          "correct_function_category",
          "note"]


def read_existing():
    if not os.path.exists(OUT):
        return {}
    with open(OUT, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return {r["contract_id"]: r for r in csv.DictReader(lines)
            if (r.get("verdict") or "").strip()}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    decided = read_existing()

    # The candidates: tech, not a licence, one row per contract, by value.
    rows = await PostgresModelAsync.select_safe(f"""
        WITH c AS (SELECT DISTINCT ON (contract_id) contract_id,
                          coalesce(current_amount, award_amount) AS val
                   FROM contracts WHERE contract_id IS NOT NULL
                   ORDER BY contract_id, coalesce(current_amount,0) DESC,
                            coalesce(award_amount,0) DESC)
        SELECT c.contract_id, c.val, e.function_category, e.rationale
        FROM c JOIN digital_contract_enrichment e ON e.contract_id = c.contract_id
        WHERE e.tech_relevant AND NOT e.is_license
        ORDER BY c.val DESC NULLS LAST
        LIMIT {int(args.top)}
    """) or []
    ids = [r["contract_id"] for r in rows]
    meta = {r["contract_id"]: r for r in rows}

    # Evidence, through the classifier's own fetch path.
    contracts = clf._dedup(await PostgresModelAsync.select_safe(
        clf.CONTRACT_SELECT.format(where="c.contract_id = ANY($1)"), [ids]))
    await clf.attach_notices(contracts)
    by_id = {c["contract_id"]: c for c in contracts}

    kept = 0
    out = []
    for i, cid in enumerate(ids, 1):
        c = by_id.get(cid, {})
        m = meta[cid]
        prior = decided.get(cid, {})
        if prior:
            kept += 1
        out.append({
            "rank": i, "contract_id": cid,
            "value_usd": int(m["val"] or 0),
            "contract_title": (c.get("contract_title") or "").replace("\n", " "),
            "vendor_name": c.get("vendor_name") or "",
            "agency": c.get("agency") or "",
            "start_date": c.get("start_date") or "", "end_date": c.get("end_date") or "",
            "procurement_method": c.get("procurement_method") or "",
            "ai_function_category": m.get("function_category") or "",
            "ai_rationale": (m.get("rationale") or "").replace("\n", " ")[:300],
            "contract_purpose": (c.get("contract_purpose") or "").replace("\n", " ")[:300],
            "main_commodity": c.get("main_commodity") or "",
            "notice_description": (c.get("notice_description") or "").replace("\n", " ")[:300],
            "verdict": prior.get("verdict", ""),
            "correct_tech_relevant": prior.get("correct_tech_relevant", ""),
            "correct_function_category": prior.get("correct_function_category", ""),
            "note": prior.get("note", ""),
        })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        fh.write("# CONTRACT-GRAIN REVIEW WORKSHEET — the composition bar's publication gate.\n"
                 "# Fill `verdict` (ok | wrong-function | not-tech | unsure); add the\n"
                 "# correction columns only when the verdict says something is wrong.\n"
                 "# Apply decisions via api/seed/contract_enrichment_curated.csv.\n")
        w = csv.DictWriter(fh, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(out)
    print(f"wrote {OUT} ({len(out)} contracts, {kept} prior decisions preserved)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
