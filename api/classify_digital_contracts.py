#!/usr/bin/env python3
"""Classify digital-service contracts with Gemini 3.5 Flash to power the Renewal
Review Queue (/research/digital-reform): license detection, build-vs-buy
replaceability, function-category clustering, and tech-vs-non-tech cleanup.

Results are upserted into digital_contract_enrichment (see
scripts/digital_reform_enrichment.sql). Idempotent and re-runnable: already
classified contracts are skipped unless --force, and rows marked curated=true
(human-edited) are never overwritten.

Run inside the api container (has GEMINI_API_KEY + DB access):
    docker compose exec -T api python classify_digital_contracts.py            # expiring-before-2030 set
    docker compose exec -T api python classify_digital_contracts.py --all      # every digital contract
    docker compose exec -T api python classify_digital_contracts.py --force    # reclassify
    docker compose exec -T api python classify_digital_contracts.py --limit 40 # smoke test
"""
import argparse
import asyncio
import json
import os

from google import genai
from google.genai import types

# Bootstraps sys.path (adds modules/) and loads env.yaml config — same as main.py.
from modules import autoload  # noqa: F401,E402
from postgrex import PostgresModelAsync  # noqa: E402

MODEL = "gemini-3.5-flash"
BATCH_SIZE = 20
CONCURRENCY = 5

INSTRUCTION = """You classify New York City government technology contracts to help the city decide which EXPIRING contracts it should NOT renew.

Each contract comes with several fields — weigh them in roughly this priority when
they are present and non-empty: contract_purpose and expense_category (from
Checkbook NYC, the most authoritative description of what the contract buys),
then scope_description and notice_category (from the City Record notice), then
commodity and solicitation_name (from the originating solicitation), then
contract_title, program and industry. The title alone is often vague; always
prefer the richer contract_purpose / scope_description / commodity when available.
contract_type, term, award_amount vs current_amount, status, procurement_method,
selection_method and special_case_reason are context for the renewal judgment.

For each contract, judge:

- tech_relevant: Is this genuinely a digital / IT / software / data service or product? Return false for physical-world work mis-tagged as tech: pest control, painting, ship/drydock repair, physical security guards, fuel, waste hauling, generators/power equipment, office furniture/filing, medical supplies, building/HVAC systems, courier/delivery.
- is_license: Is this primarily the purchase of a SOFTWARE LICENSE or subscription (vs. custom development, staffing, consulting, hardware)?
- license_product: If is_license, the product/platform name (e.g. "Microsoft Office 365", "ArcGIS", "Salesforce"); else "".
- license_purpose: If is_license, what the software is used for, one short phrase; else "".
- function_category: A 2-4 word capability bucket. Prefer reusing common buckets: "Website/CMS", "GIS/mapping", "ERP/financials", "Case management", "Cybersecurity", "Data/analytics", "Office productivity", "Staffing/consulting", "Hardware/infrastructure", "Telecom/network", "Identity/access", "Payments", "Document management", "Non-tech". Use the commodity field as a strong hint when present.
- build_vs_buy: How plausibly could the city replace this by building its own solution with open-source software + modern AI tooling? "high" = simple, commoditized software a small team could now stand up (basic websites, forms, simple dashboards, chatbots); "medium" = feasible but real effort/integration; "low" = specialized/regulated/hardware/deeply-integrated platforms or non-tech.
- rationale: One sentence justifying the build_vs_buy rating, citing the scope/commodity evidence you relied on.

Base your judgment on the evidence provided; do not invent capabilities not implied by the fields. Return one result object per contract, preserving the given id."""

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "tech_relevant": {"type": "boolean"},
                    "is_license": {"type": "boolean"},
                    "license_product": {"type": "string"},
                    "license_purpose": {"type": "string"},
                    "function_category": {"type": "string"},
                    "build_vs_buy": {"type": "string", "enum": ["high", "medium", "low"]},
                    "rationale": {"type": "string"},
                },
                "required": ["id", "tech_relevant", "is_license", "function_category",
                             "build_vs_buy", "rationale"],
            },
        }
    },
    "required": ["results"],
}

def _classify_batch(batch: list) -> list:
    """Blocking Gemini call for one batch of contracts. Returns list of result dicts.
    Builds its own client — these run in separate threads, and a shared genai
    httpx client is not safe to reuse across them."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY not set")
    cli = genai.Client(api_key=key)
    payload = [{
        "id": c["contract_id"],
        "contract_title": c.get("contract_title") or "",
        # Tier 3: Checkbook contract purpose (richest scope) + expense category
        "contract_purpose": c.get("contract_purpose") or "",
        "expense_category": c.get("expense_category") or "",
        # Tier 2: originating solicitation
        "solicitation_name": c.get("solicitation_name") or "",
        "commodity": c.get("main_commodity") or "",
        # Tier 1: City Record notice text for this PIN
        "scope_description": c.get("notice_description") or "",
        "notice_category": c.get("notice_category") or "",
        "selection_method": c.get("notice_selection_method") or "",
        "special_case_reason": c.get("notice_special_case") or "",
        # PASSPort metadata
        "program": c.get("program") or "",
        "industry": c.get("industry") or "",
        "vendor_name": c.get("vendor_name") or "",
        "agency": c.get("agency") or "",
        "contract_type": c.get("contract_type") or "",
        "status": c.get("status") or "",
        "award_amount": c.get("award_amount") or 0,
        "current_amount": c.get("current_amount") or 0,
        "term": f"{c.get('start_date') or '?'} to {c.get('end_date') or '?'}",
        "procurement_method": c.get("procurement_method") or "",
    } for c in batch]
    resp = cli.models.generate_content(
        model=MODEL,
        contents="Classify these contracts:\n" + json.dumps(payload),
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCTION,
            response_mime_type="application/json",
            response_schema=SCHEMA,
            temperature=0,
        ),
    )
    return json.loads(resp.text).get("results", [])


UPSERT = """
INSERT INTO digital_contract_enrichment
    (contract_id, tech_relevant, is_license, license_product, license_purpose,
     function_category, build_vs_buy, rationale, model, classified_at)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9, now())
ON CONFLICT (contract_id) DO UPDATE SET
    tech_relevant     = EXCLUDED.tech_relevant,
    is_license        = EXCLUDED.is_license,
    license_product   = EXCLUDED.license_product,
    license_purpose   = EXCLUDED.license_purpose,
    function_category = EXCLUDED.function_category,
    build_vs_buy      = EXCLUDED.build_vs_buy,
    rationale         = EXCLUDED.rationale,
    model             = EXCLUDED.model,
    classified_at     = now()
WHERE digital_contract_enrichment.curated = false
"""


async def _save(result: dict):
    await PostgresModelAsync.execute(UPSERT, [
        result["id"], result.get("tech_relevant"), result.get("is_license"),
        (result.get("license_product") or "")[:300], (result.get("license_purpose") or "")[:500],
        (result.get("function_category") or "")[:120], result.get("build_vs_buy"),
        (result.get("rationale") or "")[:1000], MODEL,
    ])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="classify all digital contracts, not just expiring<2030")
    ap.add_argument("--force", action="store_true", help="reclassify already-classified contracts")
    ap.add_argument("--limit", type=int, default=0, help="cap number of contracts (smoke test)")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    window = "" if args.all else (
        " AND c.end_date IS NOT NULL AND LENGTH(c.end_date)=10"
        " AND TO_DATE(c.end_date,'MM/DD/YYYY') >= CURRENT_DATE"
        " AND TO_DATE(c.end_date,'MM/DD/YYYY') < DATE '2030-01-01'")
    # Enrich each contract with richer context than the bare title (Tiers 1 & 2):
    #  - Tier 1: the City Record notice for the PIN (longest description wins) +
    #    PASSPort fields we already hold (contract_type, current vs award, status, term).
    #  - Tier 2: the originating solicitation's Main Commodity + Procurement Name (via
    #    the EPIN-prefix crosswalk) — a government-assigned category + fuller name.
    rows = await PostgresModelAsync.select_safe(f"""
        SELECT c.contract_id, c.epin, c.contract_title, c.program, c.industry,
               c.vendor_name, c.agency, c.award_amount, c.procurement_method,
               c.contract_type, c.current_amount, c.status, c.start_date, c.end_date,
               s."Procurement Name"  AS solicitation_name,
               s."Main Commodity"    AS main_commodity,
               m.purpose          AS contract_purpose,
               m.expense_category AS expense_category
        FROM contracts c
        LEFT JOIN solicitations s
          ON length(trim(c.epin)) >= 10 AND s."EPIN" = left(trim(c.epin), 10)
        LEFT JOIN checkbook_contract_meta m
          ON m.normalized_contract_id = c.normalized_contract_id
        WHERE c.vendor_name IN (SELECT vendor_name FROM vendor_tags WHERE tag='digital_services')
          AND c.contract_id IS NOT NULL{window}
    """)
    # De-dup by contract_id (one row per contract).
    seen, contracts = set(), []
    for r in (rows or []):
        cid = r["contract_id"]
        if cid and cid not in seen:
            seen.add(cid)
            contracts.append(r)

    if not args.force:
        done = await PostgresModelAsync.select_safe("SELECT contract_id FROM digital_contract_enrichment")
        done_ids = {r["contract_id"] for r in (done or [])}
        contracts = [c for c in contracts if c["contract_id"] not in done_ids]

    if args.limit:
        contracts = contracts[:args.limit]

    # Tier 1: attach the richest City Record notice per PIN (indexed ANY lookup;
    # pick the longest AdditionalDescription1 per PIN in Python — far cheaper than
    # a per-row LATERAL over the ~5M-row crol table).
    epins = list({(c.get("epin") or "").strip() for c in contracts
                  if c.get("epin") and len(str(c.get("epin")).strip()) >= 6})
    notice_by_pin = {}
    for i in range(0, len(epins), 1000):
        chunk = epins[i:i + 1000]
        nrows = await PostgresModelAsync.select_safe(
            """SELECT trim("PIN") AS pin, "CategoryDescription" AS cat,
                      "AdditionalDescription1" AS descr,
                      "SelectionMethodDescription" AS sel,
                      "SpecialCaseReasonDescription" AS special
               FROM crol WHERE trim("PIN") = ANY($1)""", [chunk]) or []
        for n in nrows:
            pin = n["pin"]
            cur = notice_by_pin.get(pin)
            if cur is None or len(n.get("descr") or "") > len(cur.get("descr") or ""):
                notice_by_pin[pin] = n
    for c in contracts:
        n = notice_by_pin.get((c.get("epin") or "").strip(), {})
        c["notice_category"] = n.get("cat")
        c["notice_description"] = n.get("descr")
        c["notice_selection_method"] = n.get("sel")
        c["notice_special_case"] = n.get("special")

    if not contracts:
        print("Nothing to classify (all done? use --force to redo).")
        return

    batches = [contracts[i:i + args.batch_size] for i in range(0, len(contracts), args.batch_size)]
    print(f"Classifying {len(contracts)} contracts in {len(batches)} batches "
          f"(model={MODEL}, concurrency={CONCURRENCY})…")

    sem = asyncio.Semaphore(CONCURRENCY)
    done_count = [0]

    async def run_batch(idx, batch):
        async with sem:
            try:
                results = await asyncio.to_thread(_classify_batch, batch)
            except Exception as exc:  # noqa: BLE001
                print(f"  batch {idx}: ERROR {exc!r}", flush=True)
                return
            for res in results:
                try:
                    await _save(res)
                except Exception as exc:  # noqa: BLE001
                    print(f"  save {res.get('id')}: ERROR {exc!r}", flush=True)
            done_count[0] += len(batch)
            print(f"  …{done_count[0]}/{len(contracts)}", flush=True)

    await asyncio.gather(*(run_batch(i, b) for i, b in enumerate(batches)))
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
