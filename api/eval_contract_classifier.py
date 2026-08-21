#!/usr/bin/env python3
"""Measure classifier ACCURACY against labels, not agreement between models.

⚠⚠ WHY THIS EXISTS. The choice between `gemini-3.5-flash` ($130 to classify all
36,421 contracts) and `gemini-3.1-flash-lite` ($8) was being argued from a single
number: "agreement between them on 40 contracts: tech_relevant 98%, is_license
92%, build_vs_buy 75%". That number is AGREEMENT, not accuracy. Neither model is
ground truth, so it says the two disagree on 1 row in 12 — it does NOT say which
one is right, and it cannot rank them. Choosing a model from it is choosing from
a measurement that does not measure the thing.

⚠ AND THE SAMPLE WAS BIASED FOR THIS DECISION. Those 40 came from the
already-classified digital set: contracts from vendors whose NAMES look
technical, which is where the boundary calls are hardest. The 33,000 contracts a
full run would add are mostly obvious non-tech, and the recall problem lives in
the untagged population — neither is represented in that sample at all.

So: a stratified sample across the WHOLE contract population, labels stored in a
version-controlled CSV, and per-field accuracy for each model against those
labels.

⚠⚠ THE LABELS ARE AI-ADJUDICATED, NOT HUMAN GROUND TRUTH, and that limit is
real: the adjudicator is also a language model and may share failure modes with
the models under test. Two things make it usable anyway — the adjudicator is a
different family and a much larger model, and it labels from the same evidence
the page shows a reader, so every label is checkable. Each row carries a
`confidence`, and scoring reports high-confidence rows separately. Correct any
label in the CSV and re-score; that is the intended workflow, and the file is a
diff so a correction is reviewable.

⚠ SHARES PRODUCTION'S DEFINITIONS. It imports CONTRACT_SELECT, attach_notices and
_classify_batch from classify_digital_contracts rather than rebuilding them. A
harness that rebuilds the query and the prompt measures a different system and
reports its accuracy as the real one's — the org-crosswalk measurement script
did exactly that with a wider suffix list and put two wrong examples into a
docstring.

    # 1. draw the sample (writes seed/eval_contract_sample.csv, labels blank)
    docker compose exec -T api python eval_contract_classifier.py --build-sample
    # 2. label it (edit the CSV; see LABELLING below)
    # 3. run each model over the sample
    docker compose exec -T api python eval_contract_classifier.py --run --model gemini-3.5-flash
    docker compose exec -T api python eval_contract_classifier.py --run --model gemini-3.1-flash-lite
    # 4. score every model that has been run
    docker compose exec -T api python eval_contract_classifier.py --score

LABELLING (the only two fields that decide this question):
  tech_relevant  1/0 — is this genuinely a digital/IT/software/data product or
                 service? Physical-world work mis-tagged as tech is 0.
  is_license     1/0 — is this PRIMARILY a software licence or subscription, as
                 opposed to custom development, staffing, consulting or hardware?
  confidence     high/low — `low` means the evidence genuinely does not settle
                 it. Scoring reports both the full set and high-confidence only,
                 because a model should not be penalised for a call a careful
                 reader could not make either.
"""
import argparse
import asyncio
import csv
import json
import os
import sys

from modules import autoload  # noqa: F401,E402
from postgrex import PostgresModelAsync  # noqa: E402

import classify_digital_contracts as clf  # noqa: E402

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")
SAMPLE = os.path.join(SEED_DIR, "eval_contract_sample.csv")
RESULTS = os.path.join(SEED_DIR, "eval_contract_results.json")

# ⚠ STRATIFIED, WITH THE STRATUM SIZES RECORDED, because the population is
# overwhelmingly non-tech: a uniform sample of 120 would be ~110 obvious
# negatives and would measure almost nothing about the decision. Each stratum is
# sampled separately and scored separately; a population estimate weights by the
# real stratum size, which is why `population` is stored with the sample.
#
#   untagged_plain  the bulk. Confirms the sieve rejects the obvious.
#   untagged_signal where the RECALL problem lives — software bought from vendors
#                   whose names look nothing like technology firms (Elasticsearch
#                   from "RAJ SOMAS", LegalStratus from "ARBOLA INC").
#   tagged          today's universe. Where the PRECISION problem lives: 444 of
#                   2,993 classified rows here are not tech at all.
STRATA = {
    "untagged_plain": {
        "n": 40,
        "where": """c.contract_id IS NOT NULL
            AND c.vendor_name NOT IN (SELECT vendor_name FROM vendor_tags WHERE tag='digital_services')
            AND c.contract_title !~* '(software|licen[cs]|subscription|saas|platform|application|cloud|hosting|system|data|digital|IT )'""",
    },
    "untagged_signal": {
        "n": 40,
        "where": """c.contract_id IS NOT NULL
            AND c.vendor_name NOT IN (SELECT vendor_name FROM vendor_tags WHERE tag='digital_services')
            AND c.contract_title ~* '(software|licen[cs]|subscription|saas|platform|application|cloud|hosting|system|data|digital|IT )'""",
    },
    "tagged": {
        "n": 40,
        "where": """c.contract_id IS NOT NULL
            AND c.vendor_name IN (SELECT vendor_name FROM vendor_tags WHERE tag='digital_services')""",
    },
}

# ⚠ A FIXED SEED. Re-drawing the sample must reproduce the same rows, or a
# re-run silently scores different contracts and the numbers stop comparing.
SAMPLE_SEED = 20260811

FIELDS = ["contract_id", "stratum", "tech_relevant", "is_license", "confidence",
          "note", "contract_title", "vendor_name", "agency", "award_amount",
          "contract_purpose", "main_commodity", "notice_description"]


async def build_sample():
    """Draw the stratified sample and write it with blank label columns."""
    if os.path.exists(SAMPLE):
        print(f"REFUSING: {SAMPLE} exists — labels would be destroyed.\n"
              f"  Delete it deliberately if you really mean to re-draw.")
        return 1
    rows_out, population = [], {}
    for name, spec in STRATA.items():
        total = await PostgresModelAsync.select_safe(
            f"SELECT count(DISTINCT c.contract_id) AS n FROM contracts c WHERE {spec['where']}")
        population[name] = int(total[0]["n"]) if total else 0
        # ⚠ setseed makes the draw reproducible; ORDER BY random() alone does not.
        await PostgresModelAsync.select_safe(f"SELECT setseed({(SAMPLE_SEED % 1000) / 1000.0})")
        picked = await PostgresModelAsync.select_safe(
            clf.CONTRACT_SELECT.format(where=spec["where"])
            + f" ORDER BY random() LIMIT {spec['n'] * 3}")
        picked = clf._dedup(picked)[: spec["n"]]
        await clf.attach_notices(picked)
        for c in picked:
            rows_out.append({
                "contract_id": c["contract_id"], "stratum": name,
                "tech_relevant": "", "is_license": "", "confidence": "", "note": "",
                "contract_title": (c.get("contract_title") or "").replace("\n", " "),
                "vendor_name": c.get("vendor_name") or "",
                "agency": c.get("agency") or "",
                "award_amount": c.get("award_amount") or 0,
                "contract_purpose": (c.get("contract_purpose") or "").replace("\n", " ")[:300],
                "main_commodity": c.get("main_commodity") or "",
                "notice_description": (c.get("notice_description") or "").replace("\n", " ")[:300],
            })
        print(f"  {name}: sampled {len([r for r in rows_out if r['stratum']==name])} "
              f"of {population[name]:,}")
    with open(SAMPLE, "w", newline="", encoding="utf-8") as fh:
        fh.write("# EVALUATION SAMPLE. Labels are AI-adjudicated pending human review;\n"
                 "# correct any row and re-score. Population sizes for weighting:\n")
        for k, v in population.items():
            fh.write(f"#   {k}: {v}\n")
        w = csv.DictWriter(fh, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows_out)
    print(f"wrote {len(rows_out)} rows to {SAMPLE} — label tech_relevant/is_license next")
    return 0


def read_sample():
    if not os.path.exists(SAMPLE):
        raise SystemExit(f"no sample at {SAMPLE} — run --build-sample first")
    with open(SAMPLE, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


async def run_model(model):
    """Classify the sample with `model`, through production's own code path."""
    sample = read_sample()
    ids = [r["contract_id"] for r in sample]
    rows = await PostgresModelAsync.select_safe(
        clf.CONTRACT_SELECT.format(where="c.contract_id = ANY($1)"), [ids])
    contracts = clf._dedup(rows)
    await clf.attach_notices(contracts)
    # ⚠ _classify_batch reads the module-level MODEL, exactly as production does.
    clf.MODEL = model
    clf.USAGE.clear()
    got = {}
    batches = [contracts[i:i + clf.BATCH_SIZE]
               for i in range(0, len(contracts), clf.BATCH_SIZE)]
    print(f"{model}: {len(contracts)} contracts in {len(batches)} batches…")
    for i, b in enumerate(batches):
        for res in await asyncio.to_thread(clf._classify_batch, b):
            got[res["id"]] = res
        print(f"  batch {i + 1}/{len(batches)}", flush=True)
    store = json.load(open(RESULTS)) if os.path.exists(RESULTS) else {}
    store[model] = {
        "results": got,
        "usage": [list(u) for u in clf.USAGE],
    }
    json.dump(store, open(RESULTS, "w"), indent=1)
    clf._report_spend(len(contracts))
    print(f"stored {len(got)} results for {model}")
    return 0


def _metrics(pairs):
    """(label, predicted) booleans -> accuracy plus the confusion counts.

    ⚠ Accuracy alone is useless on a population that is ~92% negative: a model
    that answers "no" to everything scores 92%. Precision and recall on the
    POSITIVE class are what decide whether a sieve is usable."""
    tp = sum(1 for a, b in pairs if a and b)
    tn = sum(1 for a, b in pairs if not a and not b)
    fp = sum(1 for a, b in pairs if not a and b)
    fn = sum(1 for a, b in pairs if a and not b)
    n = len(pairs)
    return {
        "n": n,
        "accuracy": (tp + tn) / n if n else 0,
        "precision": tp / (tp + fp) if (tp + fp) else None,
        "recall": tp / (tp + fn) if (tp + fn) else None,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
    }


def _fmt(m):
    p = f"{m['precision']:.0%}" if m["precision"] is not None else " n/a"
    r = f"{m['recall']:.0%}" if m["recall"] is not None else " n/a"
    return (f"acc {m['accuracy']:6.1%}  prec {p:>4}  rec {r:>4}   "
            f"(tp {m['tp']:>3} tn {m['tn']:>3} fp {m['fp']:>3} fn {m['fn']:>3})")


def score():
    sample = read_sample()
    if not os.path.exists(RESULTS):
        raise SystemExit("no results — run --run --model X first")
    store = json.load(open(RESULTS))
    labelled = [r for r in sample if r["tech_relevant"] in ("0", "1")]
    print(f"labelled: {len(labelled)} of {len(sample)}")
    if not labelled:
        raise SystemExit("nothing labelled yet")

    for model, blob in sorted(store.items()):
        res = blob["results"]
        print(f"\n=== {model} ===")
        for field in ("tech_relevant", "is_license"):
            for scope, rows in (("all", labelled),
                                ("high-confidence only",
                                 [r for r in labelled if r["confidence"] == "high"])):
                pairs = [(r[field] == "1", bool(res[r["contract_id"]].get(field)))
                         for r in rows if r["contract_id"] in res]
                if pairs:
                    print(f"  {field:14} {scope:22} {_fmt(_metrics(pairs))}")
            # Per stratum: the sieve's job differs completely between them.
            for st in STRATA:
                pairs = [(r[field] == "1", bool(res[r["contract_id"]].get(field)))
                         for r in labelled
                         if r["stratum"] == st and r["contract_id"] in res]
                if pairs:
                    print(f"    {'':12} {st:22} {_fmt(_metrics(pairs))}")
        u = blob.get("usage") or []
        if u:
            pin, vis, think = (sum(x[i] for x in u) for i in range(3))
            price = clf.PRICES.get(model)
            cost = (pin / 1e6 * price[0] + (vis + think) / 1e6 * price[1]) if price else None
            per = f"${cost / len(res):.5f}/contract" if cost and res else "n/a"
            print(f"  tokens: in {pin:,} out {vis:,}+{think:,} thinking"
                  + (f" · {per} · ${cost:.4f} for this run" if cost else ""))

    # ⚠ The disagreements are the product. A percentage tells you how often two
    # models differ; the rows tell you WHICH judgements are at stake.
    models = sorted(store)
    if len(models) == 2:
        a, b = (store[m]["results"] for m in models)
        print(f"\n=== where {models[0]} and {models[1]} disagree ===")
        by_id = {r["contract_id"]: r for r in sample}
        for cid in sorted(set(a) & set(b)):
            for field in ("tech_relevant", "is_license"):
                if bool(a[cid].get(field)) != bool(b[cid].get(field)):
                    row = by_id.get(cid, {})
                    lab = row.get(field, "?")
                    winner = models[0] if (a[cid].get(field) is True) == (lab == "1") else models[1]
                    print(f"  {cid} {field}: {models[0]}={bool(a[cid].get(field))} "
                          f"{models[1]}={bool(b[cid].get(field))} label={lab} "
                          f"-> {winner if lab in ('0','1') else 'UNLABELLED'}")
                    print(f"      {row.get('contract_title','')[:76]}")
    return 0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-sample", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--model", default="gemini-3.5-flash")
    args = ap.parse_args()
    if args.build_sample:
        return await build_sample()
    if args.run:
        return await run_model(args.model)
    if args.score:
        return score()
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
