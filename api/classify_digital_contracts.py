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
    # FULL POPULATION -- drops the vendor-name gate. See --all-vendors below.
    docker compose exec -T api python classify_digital_contracts.py --all --all-vendors --model gemini-3.1-flash-lite

⚠⚠ MODEL CHOICE IS MEASURED, NOT ARGUED (2026-08-11). The earlier basis for
preferring gemini-3.5-flash was "agreement between the two models" -- which is
not accuracy, because neither is ground truth, and it cannot rank them.
`eval_contract_classifier.py` scores both against labels on a stratified
120-contract sample drawn from the WHOLE population:

                     tech_relevant        is_license        cost/contract
    flash-lite       95.8% (97.1% hc)   97.5% (100% hc)     $0.00023
    flash            97.5% (98.1% hc)   96.7% (100% hc)     $0.00378  (16.4x)

flash-lite is BETTER on is_license and 2 rows worse on tech_relevant out of 120
-- indistinguishable at that sample size. Both are 100% on high-confidence rows.
**Use flash-lite for bulk classification.** ⚠ The eval did NOT measure
build_vs_buy, whose cross-model agreement is only 75% and which drives the
Renewal Review Queue's headline flag -- so do NOT --force existing rows onto
another model without evaluating that field first.

Every run prints its own token count and list-price cost (see _report_spend).

⚠ COST IS DOMINATED BY THINKING TOKENS, WHICH ARE BILLED AS OUTPUT. Measured on
40 real contracts, 2026-08-10:
    gemini-3.5-flash        input 10,455 · visible out 5,028 · THINKING 9,606 (191%)
                            -> $0.00368/contract, i.e. ~$9.00 for the 2,442 unclassified
    gemini-3.1-flash-lite   input 11,517 · visible out 4,857 · THINKING 0
                            -> $0.00025/contract, ~$0.62 for the same set (14.5x cheaper)
Agreement between them on 40 already-classified contracts: tech_relevant 98%,
is_license 92%, build_vs_buy 75%.
⚠ That build_vs_buy spread is why --force on the existing rows is NOT a free
swap: build_vs_buy drives the "Build-your-own candidate" flag, the headline of
/research/digital-reform/expiring, so re-running settled rows on another model
visibly moves that number. tech_relevant -- the field the non-expiring contracts
are actually consumed for -- is the one that agrees.

⚠ Long runs: launch DETACHED (setsid nohup) and never within an hour of 04:00
UTC, when a cron does `docker compose restart api` and would kill the run.
"""
import argparse
import asyncio
import json
import os
import sys

from google import genai
from google.genai import types

# Bootstraps sys.path (adds modules/) and loads env.yaml config — same as main.py.
from modules import autoload  # noqa: F401,E402
from postgrex import PostgresModelAsync  # noqa: E402

MODEL = "gemini-3.5-flash"
BATCH_SIZE = 20
CONCURRENCY = 5

# Token accounting. `_classify_batch` runs in worker threads (asyncio.to_thread);
# list.append is atomic under the GIL, so this needs no lock.
USAGE = []

# Paid-tier USD per 1M tokens — ai.google.dev/gemini-api/docs/pricing, read 2026-08-10.
# ⚠ THE OUTPUT PRICE BILLS THINKING TOKENS, and they dominate here. Measured on
# 40 real contracts 2026-08-10: gemini-3.5-flash spent 9,606 thinking tokens
# against 5,028 visible ones (191%), so counting only the visible output
# understates this job's bill ~3.4x. gemini-3.1-flash-lite spent ZERO
# (prompt + candidates == total exactly) at 14.5x lower cost.
# ⚠ Keep this table current or delete it. A stale price is worse than no price,
# because it reads like a measurement -- which is how "~$6 for 3.9k contracts"
# sat in CLAUDE.md for six weeks while the real rate was ~$14.
PRICES = {
    "gemini-3.5-flash":      (1.50, 9.00),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-2.5-flash":      (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}

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

# ⚠ THE TIER 2/3 SELECT, EXTRACTED SO AN EVALUATION CAN SHARE IT VERBATIM.
# A harness that rebuilds this query measures a DIFFERENT SYSTEM than production
# and reports its accuracy as if it were the real one — the same defect as the
# org-crosswalk measurement script that used a wider suffix list than the code
# and put two wrong examples into the docstring. `{where}` is the only thing a
# caller may vary.
CONTRACT_SELECT = """
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
    WHERE {where}
"""


def _dedup(rows):
    """One row per contract_id. `contracts` holds amendment history."""
    seen, out = set(), []
    for r in (rows or []):
        cid = r["contract_id"]
        if cid and cid not in seen:
            seen.add(cid)
            out.append(r)
    return out


async def attach_notices(contracts: list) -> None:
    """Tier 1: the richest City Record notice per PIN, attached in place.

    Indexed ANY lookup, longest AdditionalDescription1 per PIN picked in Python —
    far cheaper than a per-row LATERAL over the ~5M-row crol table.

    ⚠ Shared with the evaluation harness for the same reason as CONTRACT_SELECT:
    the notice text is a classifier INPUT, so a harness that skipped it would be
    scoring the models on thinner evidence than production gives them."""
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
    u = getattr(resp, "usage_metadata", None)
    if u is not None:
        # ⚠ thoughts_token_count is None on models that do not think — coerce, or
        # the sum raises and takes the whole batch down over pure bookkeeping.
        USAGE.append((getattr(u, "prompt_token_count", 0) or 0,
                      getattr(u, "candidates_token_count", 0) or 0,
                      getattr(u, "thoughts_token_count", 0) or 0))
    return json.loads(resp.text).get("results", [])


def _report_spend(n_contracts: int) -> None:
    """Print what the run actually spent.

    ⚠ Without this, a run's cost is invisible and gets replaced by folklore: a
    "~$6" guess sat in the docs for six weeks, was never checked, and was wrong
    by ~2.4x in the expensive direction. The fix is that the job reports its own
    spend, so the next person reads a measurement instead of a guess.
    """
    if not USAGE:
        print("No usage metadata returned — spend UNKNOWN (do not assume cheap).")
        return
    pin = sum(u[0] for u in USAGE)
    vis = sum(u[1] for u in USAGE)
    think = sum(u[2] for u in USAGE)
    print(f"Tokens over {len(USAGE)} batches: input {pin:,} · output {vis:,} visible "
          f"+ {think:,} thinking = {vis + think:,} billed")
    price = PRICES.get(MODEL)
    if not price:
        print(f"  ⚠ no list price on file for {MODEL} — cost NOT computed")
        return
    cost = pin / 1e6 * price[0] + (vis + think) / 1e6 * price[1]
    per = f"${cost / n_contracts:.5f}/contract" if n_contracts else "n/a"
    print(f"  cost ${cost:.4f} at {MODEL} list price ({per})")


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
    # ⚠ Must precede every mention of MODEL in this scope, including the
    # `--model` default below — Python rejects a `global` that follows a use of
    # the name, and it is a COMPILE-time SyntaxError, so `ast.parse` will not
    # show it to you. Only `compile()` (or actually importing) does.
    global MODEL

    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="classify all digital contracts, not just expiring<2030")
    # ⚠⚠ DROPS THE VENDOR-NAME GATE. Everything else here starts from
    # vendor_tags.digital_services, which is an ILIKE heuristic over vendor NAMES
    # ('%SYSTEMS%', '%TECHNOLOGY%', ~15 named firms, $100K floor). Measured
    # 2026-08-11 it is wrong in both directions: 444 of 2,993 contracts it admits
    # are not tech at all (85.2% precision), and it covers only 200 of 6,964
    # vendors -- so an Elasticsearch licence renewal sold by "RAJ SOMAS" and a
    # LegalStratus licence sold by "ARBOLA INC" are invisible. A stratified,
    # labelled sample put the true licence population near 1,400 against the 948
    # the tag finds (see eval_contract_classifier.py).
    #
    # A FULL RUN IS `--all --all-vendors`: this flag drops the vendor gate, --all
    # drops the expiring-before-2030 window.
    ap.add_argument("--all-vendors", action="store_true",
                    help="classify EVERY contract, not only digital-tagged vendors "
                         "(the tag is a name heuristic; see the note in the source)")
    ap.add_argument("--force", action="store_true", help="reclassify already-classified contracts")
    ap.add_argument("--limit", type=int, default=0, help="cap number of contracts (smoke test)")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--model", default=MODEL,
                    help=f"model to classify with (default {MODEL}; priced: "
                         f"{', '.join(sorted(PRICES))})")
    args = ap.parse_args()

    # _classify_batch reads MODEL for the call and _save stores it in the `model`
    # column, so a mixed-model table stays attributable to what produced each row.
    MODEL = args.model

    window = "" if args.all else (
        " AND c.end_date IS NOT NULL AND LENGTH(c.end_date)=10"
        " AND TO_DATE(c.end_date,'MM/DD/YYYY') >= CURRENT_DATE"
        " AND TO_DATE(c.end_date,'MM/DD/YYYY') < DATE '2030-01-01'")
    # Enrich each contract with richer context than the bare title (Tiers 1 & 2):
    #  - Tier 1: the City Record notice for the PIN (longest description wins) +
    #    PASSPort fields we already hold (contract_type, current vs award, status, term).
    #  - Tier 2: the originating solicitation's Main Commodity + Procurement Name (via
    #    the EPIN-prefix crosswalk) — a government-assigned category + fuller name.
    vendor_gate = "" if args.all_vendors else (
        "c.vendor_name IN (SELECT vendor_name FROM vendor_tags WHERE tag='digital_services')\n"
        "      AND ")
    rows = await PostgresModelAsync.select_safe(CONTRACT_SELECT.format(
        where=f"{vendor_gate}c.contract_id IS NOT NULL{window}"))
    contracts = _dedup(rows)

    if not args.force:
        done = await PostgresModelAsync.select_safe("SELECT contract_id FROM digital_contract_enrichment")
        done_ids = {r["contract_id"] for r in (done or [])}
        contracts = [c for c in contracts if c["contract_id"] not in done_ids]

    if args.limit:
        contracts = contracts[:args.limit]

    # Tier 1: City Record notice text. See attach_notices().
    await attach_notices(contracts)

    if not contracts:
        print("Nothing to classify (all done? use --force to redo).")
        return

    batches = [contracts[i:i + args.batch_size] for i in range(0, len(contracts), args.batch_size)]
    print(f"Classifying {len(contracts)} contracts in {len(batches)} batches "
          f"(model={MODEL}, concurrency={CONCURRENCY})…")

    sem = asyncio.Semaphore(CONCURRENCY)
    done_count = [0]
    failed = [0]

    async def run_batch(idx, batch):
        async with sem:
            try:
                results = await asyncio.to_thread(_classify_batch, batch)
            except Exception as exc:  # noqa: BLE001
                failed[0] += 1
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
    # ⚠⚠ A RUN THAT ACCOMPLISHED NOTHING MUST NOT REPORT SUCCESS. Measured
    # 2026-08-11 on the sibling script: the Gemini account's prepayment credits
    # ran out, every batch returned 429 RESOURCE_EXHAUSTED, and it printed
    # "Done. 0 classified" and exited 0 — so the monthly refresh cron would have
    # pinged its healthcheck SUCCESS having classified nothing. Same class as the
    # permanently-red monitor and the guard that scanned zero files: an outcome of
    # zero is indistinguishable from never having run.
    if failed[0]:
        print(f"  ⚠ {failed[0]} of {len(batches)} batches FAILED")
    if batches and failed[0] == len(batches):
        print(f"FAIL: every one of {len(batches)} batches errored — nothing was "
              f"classified. Check API credit and quota first.")
        _report_spend(len(contracts))
        return 1
    print("Done.")
    _report_spend(len(contracts))
    return 1 if failed[0] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
