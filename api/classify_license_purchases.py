#!/usr/bin/env python3
"""Classify every licence family: what KIND of purchase, and what CAPABILITY.

⚠⚠ WHY THE CLASS COMES FIRST. `build_vs_buy` asks "could the City build this
itself?". For infrastructure that is the wrong question, so it answers `low` and
ends the conversation -- which is how Amazon Web Services ($6.80M) stayed
invisible while the entire `high` set was $10.13M. Only a `software-licence` gets
a build-vs-buy rating on the page; every other class gets its own lever. Before
this ran, 98% of licence value ($1,347.89M) was unclassified.

⚠ CURATED ALWAYS WINS. license_family_class.csv is hand-reviewed; this script
never overwrites a family it names. The AI fills the long tail only.

⚠ GENERIC FAMILIES ARE INCLUDED HERE ON PURPOSE. `is_generic` means the
classifier could not name the PRODUCT ("Software Asset Management Solution" is a
description, not a product). But the FUNCTION is still knowable from the contract
text, and excluding generics hid the largest software-asset-management spend
($3.76M of UMS/InVision services) from the cross-agency function view that exists
to surface exactly that. Suppress the product identity, not the capability.

⚠ CAPABILITY TAGS ARE A CLOSED VOCABULARY mapped to the catalogue's own 19
categories (seed: license_capability_vocab.csv). A free-text tag would be
unmatchable, which is the whole failure this replaces: every earlier match
depended on a human guessing the right search word.

    docker compose exec -T api python classify_license_purchases.py
    docker compose exec -T api python classify_license_purchases.py --force
"""
import argparse
import asyncio
import csv
import json
import os
import sys
from collections import Counter

from google import genai
from google.genai import types

from modules import autoload  # noqa: F401,E402
from modules import dbcreds  # noqa: E402
from modules.errfmt import exc_str  # noqa: E402
from config import Config  # noqa: E402
import asyncpg  # noqa: E402

MODEL = "gemini-3.1-flash-lite"
BATCH_SIZE = 25
CONCURRENCY = 4
USAGE = []
SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")

PRICES = {
    "gemini-3.5-flash": (1.50, 9.00), "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50), "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}

CLASSES = ["software-licence", "managed-hosting", "cloud-infrastructure",
           "oss-support-tier", "content-subscription", "professional-services",
           "support-maintenance"]

LEVER_FOR = {
    "software-licence": "open-source-substitute",
    "managed-hosting": "benchmark-then-self-host",
    "cloud-infrastructure": "price-and-rightsizing",
    "oss-support-tier": "is-the-paid-tier-needed",
    "content-subscription": "is-the-content-needed",
    "professional-services": "scope-and-rate-review",
    "support-maintenance": "is-the-paid-tier-needed",
}

DDL = """
ALTER TABLE license_family_class ADD COLUMN IF NOT EXISTS capability text NOT NULL DEFAULT '';
ALTER TABLE license_family_class ADD COLUMN IF NOT EXISTS tier text NOT NULL DEFAULT 'auto';
"""

INSTRUCTION = """You classify New York City government software purchases for a public
transparency site. For each product family you get the product name and the descriptions
the City recorded on its own contracts.

Return TWO things per family.

1. `purchase_class` — WHAT KIND OF THING IS BEING BOUGHT. This matters more than any
other judgement, because each class implies a completely different question:
  - "software-licence": a licence to run or use software. Ask: is there an open-source
    substitute?
  - "managed-hosting": someone else runs the software for you (managed WordPress, a
    hosted portal, cloud file storage priced per seat). The software may itself be free;
    what is bought is hosting and operations. Ask: is the price right?
  - "cloud-infrastructure": metered consumption of compute, storage, CDN or network
    (AWS, Azure, a CDN, container monitoring priced per node). Ask: is it right-sized?
  - "oss-support-tier": a commercial edition or support contract for software that is
    ALREADY open source (NGINX Plus, GeoServer support, DBeaver PRO, Red Hat).
    Ask: does the paid tier earn its price?
  - "content-subscription": a library of content, not software — training courses,
    video libraries, data feeds. No software substitutes for content.
  - "professional-services": people. Instructor-led training delivery, consulting,
    staff augmentation.
  - "support-maintenance": vendor support or maintenance on PROPRIETARY software.

⚠ Getting this wrong in a specific way is the error to avoid: do NOT call training
content or managed hosting a "software-licence" just because software is involved. A
course library is content. Managed WordPress hosting is hosting, even though WordPress
is software.

2. `capability` — ONE tag from the supplied list saying what the thing DOES. Use
"other" only if nothing fits. Choose on function, not on vendor.

Return "unclear" for purchase_class only if the recorded descriptions genuinely do not
say enough to tell. Guessing is worse than abstaining."""


def schema(caps):
    return {
        "type": "object",
        "properties": {"results": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "family": {"type": "string"},
                # ⚠ An empty string is not a legal enum member for this API (400
                # INVALID_ARGUMENT). Abstention needs an explicit sentinel.
                "purchase_class": {"type": "string", "enum": CLASSES + ["unclear"]},
                "capability": {"type": "string", "enum": caps + ["other"]},
                "why": {"type": "string"},
            },
            "required": ["family", "purchase_class", "capability"],
        }}},
        "required": ["results"],
    }


def read_seed(name):
    path = os.path.join(SEED_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return [r for r in csv.DictReader(lines)
            if any((v or "").strip() for v in r.values())]


def _batch(batch, caps):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY not set")
    cli = genai.Client(api_key=key)
    payload = [{"family": b["family"], "recorded_purposes": b["purposes"][:10],
                "contract_count": b["n"]} for b in batch]
    resp = cli.models.generate_content(
        model=MODEL,
        contents=("Allowed capability tags: " + ", ".join(caps)
                  + "\n\nClassify these purchases:\n" + json.dumps(payload)),
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCTION, response_mime_type="application/json",
            response_schema=schema(caps), temperature=0),
    )
    u = getattr(resp, "usage_metadata", None)
    if u is not None:
        USAGE.append((getattr(u, "prompt_token_count", 0) or 0,
                      getattr(u, "candidates_token_count", 0) or 0,
                      getattr(u, "thoughts_token_count", 0) or 0))
    return json.loads(resp.text).get("results", [])


def report_spend(n):
    if not USAGE:
        print("No usage metadata returned — spend UNKNOWN (do not assume cheap).")
        return
    pin = sum(u[0] for u in USAGE); vis = sum(u[1] for u in USAGE)
    think = sum(u[2] for u in USAGE)
    print(f"Tokens over {len(USAGE)} batches: input {pin:,} · output {vis:,} visible "
          f"+ {think:,} thinking = {vis + think:,} billed")
    pr = PRICES.get(MODEL)
    if not pr:
        print(f"  ⚠ no list price on file for {MODEL} — cost NOT computed")
        return
    cost = pin / 1e6 * pr[0] + (vis + think) / 1e6 * pr[1]
    print(f"  cost ${cost:.4f} at {MODEL} list price "
          f"({f'${cost / n:.5f}/family' if n else 'n/a'})")


async def main():
    global MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="redo families that already have an auto classification")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()
    MODEL = args.model

    vocab = read_seed("license_capability_vocab.csv")
    caps = [r["capability"].strip() for r in vocab if r.get("capability")]
    if len(caps) < 10:
        print(f"REFUSING: capability vocabulary has only {len(caps)} tags")
        return 1

    conn = await asyncpg.connect(**dbcreds.settings(Config.db))
    try:
        for stmt in DDL.strip().split(";"):
            if stmt.strip():
                await conn.execute(stmt)

        # ⚠ Curated families are excluded outright, not merely overwritten later:
        # the hand-written class and its reasoning must survive every re-run.
        curated = {r["family"].strip() for r in read_seed("license_family_class.csv")}
        await conn.execute(
            "UPDATE license_family_class SET tier='curated' WHERE family = ANY($1)",
            list(curated))

        rows = await conn.fetch("""
            SELECT lf.family, count(*) AS n,
                   array_agg(DISTINCT e.license_purpose) AS purposes
            FROM digital_contract_enrichment e
            JOIN license_family lf ON lf.product_raw = e.license_product
            WHERE e.is_license
            GROUP BY lf.family
        """)
        fams = [{"family": r["family"], "n": r["n"],
                 "purposes": [p for p in (r["purposes"] or []) if p]}
                for r in rows if r["family"] not in curated]
        if not args.force:
            done = {r["family"] for r in await conn.fetch(
                "SELECT family FROM license_family_class WHERE tier='auto'")}
            fams = [f for f in fams if f["family"] not in done]
        if args.limit:
            fams = fams[:args.limit]
        if not fams:
            print("Nothing to classify (all done? use --force).")
            return 0

        batches = [fams[i:i + BATCH_SIZE] for i in range(0, len(fams), BATCH_SIZE)]
        print(f"Classifying {len(fams)} families in {len(batches)} batches "
              f"(model={MODEL}, {len(caps)} capability tags, "
              f"{len(curated)} curated families skipped)…")

        sem = asyncio.Semaphore(CONCURRENCY)
        # ⚠ One asyncpg connection cannot serve concurrent operations. The model
        # calls run in parallel; the writes are serialised behind this lock.
        db_lock = asyncio.Lock()
        wrote, abstained, seen_class, seen_cap = [0], [0], Counter(), Counter()
        failed = [0]

        async def run(idx, batch):
            async with sem:
                try:
                    results = await asyncio.to_thread(_batch, batch, caps)
                except Exception as exc:  # noqa: BLE001
                    failed[0] += 1
                    print(f"  batch {idx}: ERROR {exc_str(exc)}", flush=True)
                    return
                for r in results:
                    fam = (r.get("family") or "").strip()
                    cls = (r.get("purchase_class") or "").strip()
                    cap = (r.get("capability") or "").strip()
                    if not fam or fam in curated:
                        continue
                    if not cls or cls == "unclear":
                        # The prompt allows abstention; honour it rather than
                        # defaulting to software-licence, which would silently
                        # re-create the category error this exists to prevent.
                        abstained[0] += 1
                        continue
                    if cls not in CLASSES:
                        continue
                    seen_class[cls] += 1
                    seen_cap[cap] += 1
                    async with db_lock:
                        await conn.execute("""
                            INSERT INTO license_family_class
                                (family, class, lever, why, capability, tier)
                            VALUES ($1,$2,$3,$4,$5,'auto')
                            ON CONFLICT (family) DO UPDATE
                              SET class=EXCLUDED.class, lever=EXCLUDED.lever,
                                  why=EXCLUDED.why, capability=EXCLUDED.capability
                              WHERE license_family_class.tier <> 'curated'
                        """, fam, cls, LEVER_FOR.get(cls, ""),
                            (r.get("why") or "")[:400], cap)
                    wrote[0] += 1
                print(f"  …{wrote[0]} classified", flush=True)

        await asyncio.gather(*(run(i, b) for i, b in enumerate(batches)))
        # ⚠⚠ A RUN THAT ACCOMPLISHED NOTHING MUST NOT REPORT SUCCESS. Measured
        # 2026-08-11: the Gemini account's prepayment credits ran out mid-run,
        # every batch returned 429 RESOURCE_EXHAUSTED, and this printed
        # "Done. 0 classified" and exited 0 — so `license-analysis-refresh.sh`
        # (monthly cron, healthchecks-monitored) would have pinged SUCCESS having
        # classified nothing at all. That is the permanently-green monitor this
        # codebase has paid for twice: a check reporting no problems is
        # indistinguishable from one that never ran.
        if failed[0]:
            print(f"  ⚠ {failed[0]} of {len(batches)} batches FAILED")
        if batches and failed[0] == len(batches):
            print(f"FAIL: every one of {len(batches)} batches errored — "
                  f"nothing was classified. Check API credit and quota first.")
            return 1
        print(f"Done. {wrote[0]} classified, {abstained[0]} abstained "
              f"(descriptions too vague — left unclassified on purpose).")
        print(f"  classes: {dict(seen_class)}")
        print(f"  top capabilities: {dict(seen_cap.most_common(8))}")
        report_spend(len(fams))
        return 1 if failed[0] else 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
