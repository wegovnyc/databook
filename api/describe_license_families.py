#!/usr/bin/env python3
"""Write a one-line product summary for each licence family.

⚠⚠ GROUNDED IN OUR OWN DATA, NOT IN THE MODEL'S WORLD KNOWLEDGE. The prompt is
given only the product name plus the purposes and contract titles WE recorded,
and is told to summarise those. Asking a model "what is Ivalua?" invites a
confident description of a product the City may not actually be buying -- and
an unverifiable claim on a page whose whole point is that claims are checkable.
Every summary can be checked against the purposes shown beneath it on the page.

⚠ SEPARATE TABLE ON PURPOSE. build_license_families.py TRUNCATEs license_family
on every rebuild, so a description column there would be destroyed each time the
mapping is regenerated. Keyed by family NAME: rename a family in the curated CSV
and it simply loses its summary until this is re-run, which is the safe
direction (a stale summary attached to a renamed product would be worse).

    docker compose exec -T api python describe_license_families.py
    docker compose exec -T api python describe_license_families.py --force
    docker compose exec -T api python describe_license_families.py --limit 20
"""
import argparse
import asyncio
import json
import os
import sys

from google import genai
from google.genai import types

from modules import autoload  # noqa: F401,E402
from modules import dbcreds  # noqa: E402
from config import Config  # noqa: E402
import asyncpg  # noqa: E402

MODEL = "gemini-3.1-flash-lite"
BATCH_SIZE = 25
CONCURRENCY = 4
USAGE = []

# Same table as the classifier -- keep in step if that one changes.
PRICES = {
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}

CURATED_SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "seed", "license_family_summaries_curated.csv")

DDL = """
CREATE TABLE IF NOT EXISTS license_family_description (
    family       text PRIMARY KEY,
    summary      text NOT NULL,
    model        text NOT NULL DEFAULT '',
    curated      boolean NOT NULL DEFAULT false,
    generated_at timestamptz NOT NULL DEFAULT now()
);
"""

INSTRUCTION = """You write one-sentence summaries of software products for a public
transparency site about New York City government contracts.

You are given a product name and the descriptions New York City recorded on its own
contracts for that product. SUMMARISE WHAT THOSE DESCRIPTIONS SAY. Do not add
capabilities, history, pricing, company facts or opinions from your own knowledge --
if the recorded descriptions only say "learning management", the summary says that
and no more.

Rules:
- ONE sentence, plain English, at most 25 words.
- Say what the software DOES, in the way a non-technical reader would understand.
- No marketing language, no adjectives like "powerful" or "leading", no vendor praise.
- Do not repeat the product name if it would be redundant; start with the function.
- If the recorded descriptions are too vague to say anything useful (for example just
  "software" or "licensing"), return the empty string rather than inventing a purpose.
- ASCII only: no em-dashes, curly quotes or other non-ASCII characters."""

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "family": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["family", "summary"],
            },
        }
    },
    "required": ["results"],
}


def _describe_batch(batch):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY not set")
    cli = genai.Client(api_key=key)
    payload = [{
        "family": b["family"],
        "recorded_purposes": b["purposes"][:12],
        "example_contract_titles": b["titles"][:5],
        "contract_count": b["n"],
    } for b in batch]
    resp = cli.models.generate_content(
        model=MODEL,
        contents="Summarise each product:\n" + json.dumps(payload),
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCTION,
            response_mime_type="application/json",
            response_schema=SCHEMA,
            temperature=0,
        ),
    )
    u = getattr(resp, "usage_metadata", None)
    if u is not None:
        USAGE.append((getattr(u, "prompt_token_count", 0) or 0,
                      getattr(u, "candidates_token_count", 0) or 0,
                      getattr(u, "thoughts_token_count", 0) or 0))
    return json.loads(resp.text).get("results", [])


def _report_spend(n):
    if not USAGE:
        print("No usage metadata returned — spend UNKNOWN.")
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
    print(f"  cost ${cost:.4f} at {MODEL} list price "
          f"({f'${cost / n:.5f}/family' if n else 'n/a'})")


def load_curated_summaries():
    """Hand-written summaries from the version-controlled seed.

    ⚠ Comment lines are stripped BEFORE the CSV parser sees them -- a `#` line
    containing a comma parses as a real row otherwise. Same bug the family
    mapping loader already had to fix.
    """
    if not os.path.exists(CURATED_SEED):
        return {}
    import csv as _csv
    with open(CURATED_SEED, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    out = {}
    for row in _csv.DictReader(lines):
        fam = (row.get("family") or "").strip()
        summ = (row.get("summary") or "").strip()
        if fam and summ:
            out[fam] = summ
    return out


async def main():
    global MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="redo families that already have one")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=MODEL, help=f"default {MODEL}")
    args = ap.parse_args()
    MODEL = args.model

    conn = await asyncpg.connect(**dbcreds.settings(Config.db))
    try:
        for stmt in DDL.strip().split(";"):
            if stmt.strip():
                await conn.execute(stmt)

        # Apply the hand-written seed FIRST, so those families are already
        # curated and the generator skips them below.
        hand = load_curated_summaries()
        for fam, summ in hand.items():
            await conn.execute("""
                INSERT INTO license_family_description
                    (family, summary, model, curated, generated_at)
                VALUES ($1, $2, 'hand-written', true, now())
                ON CONFLICT (family) DO UPDATE
                  SET summary = EXCLUDED.summary, model = 'hand-written',
                      curated = true, generated_at = now()
            """, fam, summ[:400])
        if hand:
            print(f"Applied {len(hand)} hand-written summaries from the seed.")

        rows = await conn.fetch("""
            SELECT lf.family,
                   count(*)                                        AS n,
                   array_agg(DISTINCT e.license_purpose)           AS purposes,
                   array_agg(DISTINCT c.contract_title)            AS titles
            FROM digital_contract_enrichment e
            JOIN license_family lf ON lf.product_raw = e.license_product
            JOIN (SELECT DISTINCT ON (contract_id) contract_id, contract_title
                  FROM contracts WHERE contract_id IS NOT NULL
                  ORDER BY contract_id) c ON c.contract_id = e.contract_id
            WHERE e.is_license AND NOT lf.is_generic
            GROUP BY lf.family
        """)
        fams = [{"family": r["family"], "n": r["n"],
                 "purposes": [p for p in (r["purposes"] or []) if p],
                 "titles": [t for t in (r["titles"] or []) if t]} for r in rows]

        if not args.force:
            done = {r["family"] for r in await conn.fetch(
                "SELECT family FROM license_family_description")}
            fams = [f for f in fams if f["family"] not in done]
        # ⚠ Never overwrite a human-written summary, whatever --force says.
        curated = {r["family"] for r in await conn.fetch(
            "SELECT family FROM license_family_description WHERE curated")}
        fams = [f for f in fams if f["family"] not in curated]

        if args.limit:
            fams = fams[:args.limit]
        if not fams:
            print("Nothing to describe (all done? use --force).")
            return 0

        batches = [fams[i:i + BATCH_SIZE] for i in range(0, len(fams), BATCH_SIZE)]
        print(f"Describing {len(fams)} families in {len(batches)} batches "
              f"(model={MODEL}, concurrency={CONCURRENCY})…")

        sem = asyncio.Semaphore(CONCURRENCY)
        # ⚠ ONE asyncpg connection CANNOT serve concurrent operations -- it
        # raises "another operation is in progress". The Gemini calls run
        # concurrently (they are the slow part); the writes are serialised
        # behind this lock. Same class as the normalizer's shared-DuckDB-cursor
        # bug: the connection is the shared resource, not the work.
        db_lock = asyncio.Lock()
        written = [0]
        skipped = [0]

        async def run(idx, batch):
            async with sem:
                try:
                    results = await asyncio.to_thread(_describe_batch, batch)
                except Exception as exc:  # noqa: BLE001
                    print(f"  batch {idx}: ERROR {exc!r}", flush=True)
                    return
                for r in results:
                    fam = (r.get("family") or "").strip()
                    summ = (r.get("summary") or "").strip()
                    if not fam:
                        continue
                    if not summ:
                        # The model was told to return "" when the recorded
                        # descriptions say nothing useful. Honour that rather
                        # than storing a filler sentence.
                        skipped[0] += 1
                        continue
                    async with db_lock:
                        await conn.execute("""
                            INSERT INTO license_family_description
                                (family, summary, model, generated_at)
                            VALUES ($1,$2,$3, now())
                            ON CONFLICT (family) DO UPDATE
                              SET summary = EXCLUDED.summary, model = EXCLUDED.model,
                                  generated_at = now()
                              WHERE license_family_description.curated = false
                        """, fam, summ[:400], MODEL)
                    written[0] += 1
                print(f"  …{written[0]} written", flush=True)

        await asyncio.gather(*(run(i, b) for i, b in enumerate(batches)))
        print(f"Done. {written[0]} summaries written, {skipped[0]} left blank "
              f"(recorded descriptions too vague).")
        _report_spend(len(fams))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
