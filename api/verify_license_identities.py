#!/usr/bin/env python3
"""Web-verify what each licence family actually IS, with citations.

⚠⚠ THIS ANSWERS A QUESTION THE CONTRACT TEXT STRUCTURALLY CANNOT. Our grounded
summaries say what NYC recorded buying; they cannot say that "Carahsoft" names a
distributor rather than a product, or that "Casebuilder" is SoundThinking's
police platform and therefore belongs beside the same vendor's $43.9M of gunshot
detection. Both were found by searching, and the second corrected a wrong
function tag on a $46.1M family.

⚠⚠ NO SOURCES, NO ROW. Every finding must carry grounding citations or it is
discarded and counted as a refusal. This is enforceable here in a way it is not
for a hand-written note, and it is the only thing separating this from a
confident guess.

⚠⚠ AND THE MODEL CHOICE IS LOAD-BEARING. Measured 2026-08-13: given the same
google_search tool, `gemini-3.1-flash-lite` returns NO grounding metadata -- it
silently answers from recall. Its answer about Carahsoft was correct, which is
precisely the danger: an ungrounded right answer is indistinguishable from an
ungrounded wrong one. `gemini-3.5-flash` grounds and returns sources. Do not
"save money" by moving this to the lite model; the citations are the product.

⚠ OUTPUT IS A REVIEW QUEUE, NEVER A PAGE. Findings land in
docs/license-identity-review.md. Acting on one means editing a curated seed,
where it becomes a diff -- the same rule as the replacement candidates.

    docker compose exec -T api python verify_license_identities.py --top 40
"""
import argparse
import asyncio
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

# ⚠ Not the lite model. See the docstring: lite does not ground.
MODEL = "gemini-3.5-flash"
EXTRACT_MODEL = "gemini-3.1-flash-lite"  # parsing only; no search involved
CONCURRENCY = 3
USAGE = []
EXTRACT_USAGE = []
PRICES = {"gemini-3.5-flash": (1.50, 9.00), "gemini-3-flash-preview": (0.50, 3.00),
          "gemini-3.1-flash-lite": (0.25, 1.50)}

PROMPT = """You are verifying what a piece of software actually is, for a public
transparency site about New York City government contracts.

You will be given: the name New York City uses, the vendor it buys from, the agency,
and the purposes recorded on the contracts.

USE WEB SEARCH. Then answer only what the search supports. If search does not settle a
question, say so rather than filling it in from memory.

Report:
- entity_type: "product" (a specific piece of software), "vendor-or-reseller" (the name
  is a company that resells or distributes other people's software, not a product),
  "service" (consulting, managed service, staffing), or "unclear".
- what_it_does: one plain sentence. No marketing language.
- same_vendor_as: if this product is made by a company that clearly also sells ANOTHER
  named product, name the company. This is how a single vendor relationship split across
  differently-named contracts gets spotted.
- renamed_from: any former product or company name (acquisitions, rebrands). This is the
  single hardest thing for a string match to see.
- flag: the one thing a reviewer should know, or "" if nothing. Say it plainly, e.g.
  "this is a reseller, not a product" or "the recorded purpose suggests a legal system
  but this is a law-enforcement product".

⚠ If the recorded purposes contradict what you find, SAY SO in flag. That contradiction
is the most valuable thing you can report."""

SCHEMA = {
    "type": "object",
    "properties": {
        "entity_type": {"type": "string",
                        "enum": ["product", "vendor-or-reseller", "service", "unclear"]},
        "what_it_does": {"type": "string"},
        "same_vendor_as": {"type": "string"},
        "renamed_from": {"type": "string"},
        "flag": {"type": "string"},
    },
    "required": ["entity_type", "what_it_does", "flag"],
}


def _verify(fam):
    """Two steps, because they fight each other in one call.

    ⚠⚠ ASKING FOR JSON-ONLY OUTPUT SILENTLY DISABLES SEARCH. Measured
    2026-08-13: the identical request grounds with 13-16 sources as prose, and
    returns ZERO sources the moment "Return ONLY a JSON object" is appended --
    the model switches from searching to reasoning and answers from recall. The
    first version of this script discarded all 12 families for exactly that
    reason, which is the gate working, but it produced nothing.

    So: step 1 searches and answers in prose (grounded, cited). Step 2 extracts
    fields from that prose with a cheap model and a schema -- no search needed,
    because it is only parsing text step 1 already produced.
    """
    cli = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    q = (f"Product name as used by New York City: {fam['family']}\n"
         f"Vendor on the contracts: {fam['vendor']}\n"
         f"Buying agency: {fam['agency']}\n"
         f"Purposes recorded on the contracts: {fam['purposes'][:400]}\n\n"
         f"What is this, really? Is it a specific software product, or is the name "
         f"a reseller/distributor, or a service? Who makes it? Was it renamed or "
         f"acquired? Does that company also sell other named products? And does "
         f"anything you find CONTRADICT the recorded purposes above?")
    resp = cli.models.generate_content(
        model=MODEL, contents=q,
        config=types.GenerateContentConfig(
            system_instruction=PROMPT,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0),
    )
    u = getattr(resp, "usage_metadata", None)
    if u is not None:
        USAGE.append((getattr(u, "prompt_token_count", 0) or 0,
                      getattr(u, "candidates_token_count", 0) or 0,
                      getattr(u, "thoughts_token_count", 0) or 0))

    # ⚠ THE GATE. No grounding chunks means the model answered from recall, and
    # the finding is discarded however plausible it reads.
    gm = getattr(resp.candidates[0], "grounding_metadata", None)
    chunks = (getattr(gm, "grounding_chunks", None) or []) if gm else []
    if not chunks:
        return None, []
    sources, seen = [], set()
    for c in chunks[:8]:
        web = getattr(c, "web", None)
        if web:
            uri = getattr(web, "uri", "") or ""
            title = getattr(web, "title", "") or ""
            if title and title not in seen:
                seen.add(title)
                sources.append({"title": title, "uri": uri})

    prose = (resp.text or "").strip()
    if not prose:
        return None, sources

    # Step 2: pure extraction from step 1's grounded prose. No search, so a
    # schema is safe here -- there is nothing left for it to suppress.
    ex = cli.models.generate_content(
        model=EXTRACT_MODEL,
        contents=("Extract the fields from this research note. Use only what it "
                  "says; leave a field empty rather than inferring.\n\n" + prose[:6000]),
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=SCHEMA,
            temperature=0),
    )
    u2 = getattr(ex, "usage_metadata", None)
    if u2 is not None:
        EXTRACT_USAGE.append((getattr(u2, "prompt_token_count", 0) or 0,
                              getattr(u2, "candidates_token_count", 0) or 0,
                              getattr(u2, "thoughts_token_count", 0) or 0))
    try:
        return json.loads(ex.text), sources
    except (ValueError, TypeError):
        return None, sources


def report_spend(n):
    if not USAGE:
        print("No usage metadata — spend UNKNOWN.")
        return
    pin = sum(u[0] for u in USAGE); vis = sum(u[1] for u in USAGE)
    think = sum(u[2] for u in USAGE)
    print(f"Tokens: input {pin:,} · output {vis:,} visible + {think:,} thinking")
    pr = PRICES.get(MODEL)
    cost = 0.0
    if pr:
        cost = pin / 1e6 * pr[0] + (vis + think) / 1e6 * pr[1]
    if EXTRACT_USAGE:
        ep = PRICES.get(EXTRACT_MODEL, (0.25, 1.50))
        ein = sum(u[0] for u in EXTRACT_USAGE)
        eout = sum(u[1] + u[2] for u in EXTRACT_USAGE)
        cost += ein / 1e6 * ep[0] + eout / 1e6 * ep[1]
        print(f"  extraction step: input {ein:,} output {eout:,}")
    print(f"  cost ${cost:.4f} ({f'${cost/n:.4f}/family' if n else 'n/a'})")


async def main():
    # ⚠ Must precede every mention of MODEL in this scope, including the
    # --model default below. Compile-time SyntaxError that ast.parse hides;
    # this is the second time in one session, hence the comment.
    global MODEL

    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--model", default=MODEL)
    # ⚠ Verify NAMED families instead of the top slice. Added because a question
    # about one family ("is Ivalua the platform behind PASSPort?") otherwise
    # costs a run over every family above it by value -- ~200 grounded searches
    # to answer one question. Repeatable: `--family Ivalua --family Salesforce`.
    ap.add_argument("--family", action="append", default=None,
                    help="verify these families by exact name (repeatable); "
                         "overrides --top")
    args = ap.parse_args()
    MODEL = args.model

    conn = await asyncpg.connect(**dbcreds.settings(Config.db))
    try:
        rows = await conn.fetch("""
            WITH c AS (
                SELECT DISTINCT ON (contract_id) contract_id, current_amount,
                       award_amount, agency, vendor_name
                FROM contracts WHERE contract_id IS NOT NULL
                ORDER BY contract_id, coalesce(current_amount,0) DESC
            )
            SELECT lf.family, max(lf.slug) AS slug,
                   sum(coalesce(c.current_amount,c.award_amount,0)) AS value,
                   count(*) AS contracts,
                   (array_agg(c.vendor_name ORDER BY coalesce(c.current_amount,0) DESC))[1] AS vendor,
                   (array_agg(c.agency ORDER BY coalesce(c.current_amount,0) DESC))[1] AS agency,
                   string_agg(DISTINCT e.license_purpose, ' | ') AS purposes,
                   max(k.capability) AS capability, max(k.class) AS class
            FROM digital_contract_enrichment e
            JOIN c ON c.contract_id = e.contract_id
            JOIN license_family lf ON lf.product_raw = e.license_product
            LEFT JOIN license_family_class k ON k.family = lf.family
            WHERE e.is_license AND NOT lf.is_generic
              AND ($2::text[] IS NULL OR lf.family = ANY($2::text[]))
            GROUP BY lf.family
            ORDER BY sum(coalesce(c.current_amount,c.award_amount,0)) DESC
            LIMIT $1
        """, (len(args.family) if args.family else args.top), args.family)

        # ⚠ A named family that matched nothing must be LOUD, not silently
        # absent -- an empty run is otherwise indistinguishable from "verified
        # and found nothing", which is this repo's oldest defect shape.
        if args.family:
            missing = sorted(set(args.family) - {r["family"] for r in rows})
            if missing:
                print(f"⚠ no such licence family (check spelling/case): {missing}")
                print("   families are derived from license_product on LICENCE "
                      "contracts; a system bought as a service has none.")
        fams = [{"family": r["family"], "slug": r["slug"], "value": float(r["value"] or 0),
                 "contracts": r["contracts"], "vendor": r["vendor"] or "",
                 "agency": r["agency"] or "", "purposes": r["purposes"] or "",
                 "capability": r["capability"] or "", "class": r["class"] or ""}
                for r in rows]
        print(f"Verifying {len(fams)} families (model={MODEL}, sources required)…")

        sem = asyncio.Semaphore(CONCURRENCY)
        out, ungrounded, unparsed = [], [], []

        async def run(f):
            async with sem:
                try:
                    res, sources = await asyncio.to_thread(_verify, f)
                except Exception as exc:  # noqa: BLE001
                    print(f"  {f['family']}: ERROR {exc_str(exc)}", flush=True)
                    return
                if not sources:
                    ungrounded.append(f["family"])
                    return
                if not res:
                    unparsed.append(f["family"])
                    return
                out.append({**f, **res, "sources": sources})
                print(f"  {f['family']}: {res.get('entity_type')}"
                      f"{' ⚑' if res.get('flag') else ''}", flush=True)

        await asyncio.gather(*(run(f) for f in fams))

        # Findings worth a human's time, most valuable first.
        def rank(r):
            score = 0
            if r.get("entity_type") in ("vendor-or-reseller", "service"): score -= 3
            if r.get("flag"): score -= 2
            if r.get("renamed_from"): score -= 1
            if r.get("same_vendor_as"): score -= 1
            return (score, -r["value"])

        out.sort(key=rank)
        path = os.path.join(os.getcwd(), "docs", "license-identity-review.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# Licence family identity review\n\n")
            fh.write("Web-verified with citations. **Nothing here renders on any "
                     "page.** Acting on a finding means editing a curated seed, "
                     "where it becomes a reviewable diff.\n\n")
            fh.write(f"- Verified: **{len(out)}** of {len(fams)} families\n")
            fh.write(f"- ⚠ Discarded for having NO SOURCES: **{len(ungrounded)}** "
                     f"— an ungrounded answer is discarded however plausible it "
                     f"reads{': ' + ', '.join(ungrounded[:6]) if ungrounded else ''}\n")
            if unparsed:
                fh.write(f"- Unparseable response: {len(unparsed)} "
                         f"({', '.join(unparsed[:6])})\n")
            fh.write(f"- Model: `{MODEL}` — ⚠ the lite model returns no grounding "
                     f"metadata at all, so it must not be used here\n\n")
            types_seen = Counter(r.get("entity_type") for r in out)
            fh.write(f"- Entity types found: {dict(types_seen)}\n\n")
            fh.write("## Findings\n\n")
            for r in out:
                flagged = "⚑ " if (r.get("flag") or r.get("entity_type") != "product") else ""
                fh.write(f"### {flagged}{r['family']} — ${r['value']/1e6:,.2f}M\n\n")
                fh.write(f"- **Is:** `{r.get('entity_type')}` — {r.get('what_it_does','')}\n")
                fh.write(f"- Our tags: class `{r['class'] or '—'}`, "
                         f"function `{r['capability'] or '—'}`\n")
                fh.write(f"- Vendor on contracts: {r['vendor']} ({r['agency']})\n")
                if r.get("same_vendor_as"):
                    fh.write(f"- **Same vendor as:** {r['same_vendor_as']}\n")
                if r.get("renamed_from"):
                    fh.write(f"- **Renamed from:** {r['renamed_from']}\n")
                if r.get("flag"):
                    fh.write(f"- ⚠ **{r['flag']}**\n")
                fh.write(f"- Recorded purposes: {r['purposes'][:200]}\n")
                fh.write("- Sources: "
                         + "; ".join(f"[{s['title'] or 'source'}]({s['uri']})"
                                     for s in r["sources"][:4]) + "\n\n")
        print(f"\nwrote docs/license-identity-review.md "
              f"({len(out)} verified, {len(ungrounded)} discarded for no sources)")
        report_spend(len(out))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
