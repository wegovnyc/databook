#!/usr/bin/env python3
"""Generate the human review worksheet for the licence analysis.

⚠⚠ WHY A WORKSHEET AND NOT THE SEED FILES. The curated CSVs are the right place
for a DECISION to live, but the wrong place to make one: they show the answer
without the evidence or the money. Reviewing there means editing blind. This puts
every judgement about one product, the evidence behind it, and the value at
stake, on one line.

⚠ ORDERED BY VALUE, WITH A RUNNING PERCENTAGE, so the reviewer can stop on
purpose rather than from exhaustion. Measured 2026-08-13: the top 10 families are
79.1% of all licence value, the top 20 are 88.0%. Reviewing 432 families is not
the task; reviewing 10 is.

⚠ RE-RUNNING NEVER DISCARDS A DECISION ALREADY MADE. Existing verdicts are read
back and preserved, and a row that has been decided is marked so. The whole point
of the exercise is destroyed if a refresh silently blanks it -- the same rule as
`curated` rows surviving every AI pass.

    docker compose exec -T api python build_review_worksheet.py
    docker compose exec -T api python build_review_worksheet.py --top 40
"""
import argparse
import asyncio
import csv
import os
import sys

from modules import autoload  # noqa: F401,E402
from modules import dbcreds  # noqa: E402
from config import Config  # noqa: E402
import asyncpg  # noqa: E402

# ⚠ `__file__` is "<stdin>" when this is piped to `python -`, and abspath then
# resolves ROOT to "/" -- the same un-normalized-root trap that once made a guard
# scan zero files and pass. Fall back to the working directory, which inside the
# api container is /app, and let the caller override.
_here = os.path.abspath(__file__) if os.path.exists(__file__) else os.path.abspath(os.getcwd() + "/x")
ROOT = os.environ.get("REVIEW_ROOT") or os.path.dirname(os.path.dirname(_here))
if not os.path.isdir(os.path.join(ROOT, "docs")):
    ROOT = os.path.dirname(_here)
SHEET = os.path.join(ROOT, "docs", "license-review-worksheet.csv")
NOTES = os.path.join(ROOT, "docs", "license-review-worksheet.md")

# What the reviewer can say. Deliberately small: a long vocabulary makes the
# worksheet a form to fill in rather than a judgement to make.
VERDICTS = ["", "ok", "not-a-licence", "wrong-class", "wrong-function",
            "wrong-summary", "wrong-product-grouping"]

DECISION_COLS = ["verdict", "correct_class", "correct_capability",
                 "correct_summary", "notes"]


def load_existing():
    """Decisions already made, keyed by family. ⚠ Never discarded on a re-run."""
    if not os.path.exists(SHEET):
        return {}
    out = {}
    with open(SHEET, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            fam = (r.get("family") or "").strip()
            if fam and any((r.get(c) or "").strip() for c in DECISION_COLS):
                out[fam] = {c: (r.get(c) or "").strip() for c in DECISION_COLS}
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20,
                    help="how many families to put in the sheet (default 20 = ~88%% of value)")
    args = ap.parse_args()

    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    print(f"writing under {ROOT}/docs")
    existing = load_existing()
    conn = await asyncpg.connect(**dbcreds.settings(Config.db))
    try:
        rows = await conn.fetch("""
            WITH c AS (
                SELECT DISTINCT ON (contract_id) contract_id, current_amount,
                       award_amount, agency, vendor_name, contract_title
                FROM contracts WHERE contract_id IS NOT NULL
                ORDER BY contract_id, coalesce(current_amount,0) DESC
            )
            SELECT lf.family,
                   max(lf.slug)                                   AS slug,
                   count(*)                                       AS contracts,
                   sum(coalesce(c.current_amount,c.award_amount,0)) AS value,
                   count(DISTINCT c.agency)                       AS agencies,
                   bool_or(lf.is_generic)                         AS is_generic,
                   max(k.class)                                   AS purchase_class,
                   max(k.capability)                              AS capability,
                   max(k.tier)                                    AS class_tier,
                   max(d.summary)                                 AS summary,
                   bool_or(d.curated)                             AS summary_curated,
                   string_agg(DISTINCT e.build_vs_buy, '/')       AS build_vs_buy,
                   string_agg(DISTINCT e.license_product, ' | ')  AS products,
                   string_agg(DISTINCT e.license_purpose, ' | ')  AS purposes,
                   string_agg(DISTINCT c.agency, ', ')            AS agency_list
            FROM digital_contract_enrichment e
            JOIN c ON c.contract_id = e.contract_id
            JOIN license_family lf ON lf.product_raw = e.license_product
            LEFT JOIN license_family_class k ON k.family = lf.family
            LEFT JOIN license_family_description d ON d.family = lf.family
            WHERE e.is_license
            GROUP BY lf.family
            ORDER BY sum(coalesce(c.current_amount,c.award_amount,0)) DESC
        """)
        if not rows:
            print("REFUSING: no licence families found")
            return 1

        total = sum(float(r["value"] or 0) for r in rows)
        top = rows[:args.top]

        cols = (["rank", "family", "value_usd", "pct_of_total", "cumulative_pct",
                 "contracts", "agencies", "ai_purchase_class", "ai_capability",
                 "ai_build_vs_buy", "ai_summary", "class_tier", "summary_curated",
                 "is_generic", "products_merged", "recorded_purposes", "page"]
                + DECISION_COLS)

        cum = 0.0
        with open(SHEET, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for i, r in enumerate(top, 1):
                v = float(r["value"] or 0)
                cum += v
                prior = existing.get(r["family"], {})
                w.writerow({
                    "rank": i, "family": r["family"],
                    "value_usd": int(v),
                    "pct_of_total": f"{100*v/total:.1f}",
                    "cumulative_pct": f"{100*cum/total:.1f}",
                    "contracts": r["contracts"], "agencies": r["agencies"],
                    "ai_purchase_class": r["purchase_class"] or "",
                    "ai_capability": r["capability"] or "",
                    "ai_build_vs_buy": r["build_vs_buy"] or "",
                    "ai_summary": r["summary"] or "",
                    "class_tier": r["class_tier"] or "",
                    "summary_curated": "yes" if r["summary_curated"] else "",
                    "is_generic": "yes" if r["is_generic"] else "",
                    "products_merged": (r["products"] or "")[:300],
                    "recorded_purposes": (r["purposes"] or "")[:400],
                    "page": f"https://databook.nyc/research/digital-reform/licenses/{r['slug'] or ''}",
                    **{c: prior.get(c, "") for c in DECISION_COLS},
                })

        decided = sum(1 for r in top if r["family"] in existing)
        covered = 100 * cum / total

        with open(NOTES, "w", encoding="utf-8") as fh:
            fh.write("# Licence analysis — review worksheet\n\n")
            fh.write(f"**Edit `docs/license-review-worksheet.csv`.** "
                     f"{len(top)} families, covering **{covered:.1f}%** of "
                     f"${total/1e6:,.0f}M in licence value. "
                     f"{decided} already decided.\n\n")
            fh.write("## How to do it\n\n")
            fh.write("Open the CSV in a spreadsheet. Each row is one product "
                     "family, ordered by money, with every AI judgement about it "
                     "and the evidence behind them. Fill in `verdict`; add the "
                     "correction columns only when the verdict says something is "
                     "wrong. `cumulative_pct` tells you how much of the money you "
                     "have covered, so you can stop deliberately.\n\n")
            fh.write("### verdict — one of\n\n")
            fh.write("| verdict | means |\n|---|---|\n")
            fh.write("| `ok` | everything on this row is right |\n")
            fh.write("| `not-a-licence` | ⚠ **the strongest one.** These contracts should not be in the analysis at all |\n")
            fh.write("| `wrong-class` | it is not that kind of purchase — put the right one in `correct_class` |\n")
            fh.write("| `wrong-function` | wrong capability tag — put the right one in `correct_capability` |\n")
            fh.write("| `wrong-summary` | the description is wrong — write the right one in `correct_summary` |\n")
            fh.write("| `wrong-product-grouping` | unlike products merged into one family, or one product split |\n\n")
            fh.write("You can put more than one, comma-separated.\n\n")
            fh.write("### What each column is, and how much to trust it\n\n")
            fh.write("| column | how it was made | measured reliability |\n|---|---|---|\n")
            fh.write("| `ai_purchase_class` | AI, from recorded purposes | 37 families hand-checked, the rest not. **Decides which question the page asks** |\n")
            fh.write("| `ai_build_vs_buy` | AI, per contract | ⚠ **weakest field**: 75% agreement between two models, and 64 families rated inconsistently against themselves |\n")
            fh.write("| `ai_capability` | AI, closed vocabulary | drives the cross-agency consolidation view |\n")
            fh.write("| `ai_summary` | AI, from the recorded purposes only | grounded in the evidence column beside it; check it against that, not against what you know about the product |\n")
            fh.write("| `is_licence` (inclusion) | AI | 92% agreement between two models — roughly 1 row in 12 |\n\n")
            fh.write("⚠ `class_tier = curated` and `summary_curated = yes` mean a "
                     "human already decided that cell; changing it is a "
                     "deliberate override, not a correction.\n\n")
            fh.write("### When you are done\n\n")
            fh.write("Hand the CSV back. Decisions are applied to the "
                     "version-controlled seeds (`license_family_class.csv`, "
                     "`license_family_summaries_curated.csv`, "
                     "`license_family_curated.csv`), where each becomes a "
                     "reviewable diff — and where **no later AI pass can "
                     "overwrite it**.\n\n")
            fh.write("⚠ Re-running the generator preserves anything already "
                     "filled in. It will not blank your work.\n\n")
            fh.write("## The rows\n\n")
            fh.write("| # | family | value | cum % | contracts | agencies | class | function |\n")
            fh.write("|---:|---|---:|---:|---:|---:|---|---|\n")
            run = 0.0
            for i, r in enumerate(top, 1):
                v = float(r["value"] or 0); run += v
                fh.write(f"| {i} | [{r['family']}](https://databook.nyc/research/"
                         f"digital-reform/licenses/{r['slug'] or ''}) | "
                         f"${v/1e6:,.1f}M | {100*run/total:.1f}% | {r['contracts']} | "
                         f"{r['agencies']} | {r['purchase_class'] or '—'} | "
                         f"{r['capability'] or '—'} |\n")

        print(f"wrote docs/license-review-worksheet.csv ({len(top)} families, "
              f"{covered:.1f}% of ${total/1e6:,.0f}M)")
        print(f"wrote docs/license-review-worksheet.md (how-to + the row list)")
        if decided:
            print(f"  preserved {decided} decisions already made")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
