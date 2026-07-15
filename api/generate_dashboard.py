#!/usr/bin/env python3
"""Generate dashboard_data.json for the Civil Service Titles page.

Why: The /titles Blade view reads pre-computed analytics from this JSON
file. It contains aggregated metrics, chart data, and curated lists
that would be too expensive to compute on every page load.

Data sources:
  - nyccivilservicetitles table (Socrata nzjr-3966): Title codes, descriptions,
    salary rates, assignment levels, union info
  - positionschedule table (Socrata f4wx-5ve6): Positions per title per agency
    — FILTERED TO LATEST PUBLICATION DATE ONLY to avoid historical duplicates
  - titles_analysis.csv (enrichment): Full Description flag, Effective Date

This script is called:
  1. Manually: docker exec databook-api python3 api/generate_dashboard.py
  2. Automatically: via post-ingest hook when nyccivilservicetitles or
     positionschedule are updated by the data scheduler
"""
import asyncio
import csv
import json
import os
from datetime import datetime

import asyncpg


# Path to enrichment CSV — check multiple possible locations
# (repo root during local dev, or /app/ inside Docker container)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CANDIDATES = [
    os.path.join(_SCRIPT_DIR, "..", "titles_analysis.csv"),   # api/ → repo root
    os.path.join(_SCRIPT_DIR, "titles_analysis.csv"),         # same dir (Docker /app/)
    "/app/titles_analysis.csv",                                # explicit Docker path
]
ENRICHMENT_CSV = os.environ.get("TITLES_ENRICHMENT_CSV", "")
if not ENRICHMENT_CSV:
    for candidate in _CANDIDATES:
        if os.path.exists(candidate):
            ENRICHMENT_CSV = candidate
            break
    else:
        ENRICHMENT_CSV = _CANDIDATES[0]  # fallback for warning message

OUTPUT_PATH = os.environ.get(
    "DASHBOARD_OUTPUT",
    "/app/shared/dashboard_data.json",
)

# SQL fragment: filter positionschedule to latest publication date only.
# Why: The table stores multiple historical snapshots. Without this filter,
# SUM(POSITIONS) counts the same title across every snapshot, inflating totals.
PS_LATEST = (
    'positionschedule WHERE "PUBLICATION DATE" = '
    '(SELECT MAX("PUBLICATION DATE") FROM positionschedule)'
)


def load_enrichment():
    """Load titles_analysis.csv into a dict keyed by Title Code.

    Why: This CSV contains pre-computed flags (Full Description Yes/No,
    Effective Date) that aren't in the Socrata source dataset. It was
    generated from a separate analysis pipeline.
    """
    enrichment = {}
    path = ENRICHMENT_CSV
    if not os.path.exists(path):
        print(f"  Warning: enrichment CSV not found at {path}")
        return enrichment

    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row.get("Title Code", "").strip()
            if code:
                enrichment[code] = {
                    "full_desc": row.get("Full Description", "").strip(),
                    "effective_date": row.get("Effective Date", "").strip(),
                }
    print(f"  Loaded enrichment for {len(enrichment)} titles")
    return enrichment


async def generate(conn=None):
    """Generate dashboard_data.json from DB + enrichment CSV.

    Can be called directly or imported by data_scheduler.py.
    """
    own_conn = conn is None
    if own_conn:
        conn = await asyncpg.connect(
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "secret"),
            database=os.getenv("DB_NAME", "databook"),
            host=os.getenv("DB_HOST", "postgres"),
        )

    enrichment = load_enrichment()

    data = {"metrics": {}, "charts": {}, "top_lists": {}, "lists": {}}

    # Get latest publication date for logging
    latest_pub = await conn.fetchval(
        'SELECT MAX("PUBLICATION DATE") FROM positionschedule'
    )
    print(f"  Using PUBLICATION DATE = {latest_pub}")

    # --- Metrics ---
    total_rows = await conn.fetchval(
        'SELECT COUNT(DISTINCT "Title Code") FROM nyccivilservicetitles'
    )
    data["metrics"]["total_rows"] = total_rows

    try:
        cnt_titles_pos = await conn.fetchval(
            f'SELECT COUNT(DISTINCT "TITLE CODE") FROM {PS_LATEST} '
            'AND CAST("POSITIONS" AS INTEGER) > 0'
        )
    except Exception:
        cnt_titles_pos = 0
    data["metrics"]["cnt_titles_pos"] = cnt_titles_pos

    try:
        total_positions = await conn.fetchval(
            f'SELECT SUM(CAST("POSITIONS" AS INTEGER)) FROM {PS_LATEST}'
        )
    except Exception:
        total_positions = 0
    data["metrics"]["total_positions"] = total_positions or 0

    # Individual positions = same as total_positions (sum of all positions
    # in the latest publication date snapshot)
    data["metrics"]["individual_positions"] = total_positions or 0

    data["metrics"]["pct_titles_pos"] = (
        round(cnt_titles_pos / total_rows * 100, 1) if total_rows else 0
    )

    # Full description stats from enrichment CSV
    has_desc = sum(1 for v in enrichment.values() if v["full_desc"] == "Yes")
    data["metrics"]["cnt_full_desc"] = has_desc
    data["metrics"]["pct_full_desc"] = (
        round(has_desc / total_rows * 100, 1) if total_rows else 0
    )

    # Positions with full descriptions
    try:
        title_codes_with_desc = [
            k for k, v in enrichment.items() if v["full_desc"] == "Yes"
        ]
        if title_codes_with_desc:
            placeholders = ", ".join(
                f"${i+1}" for i in range(len(title_codes_with_desc))
            )
            cnt_pos_desc = await conn.fetchval(
                f'SELECT COALESCE(SUM(CAST("POSITIONS" AS INTEGER)), 0) '
                f'FROM {PS_LATEST} AND "TITLE CODE" IN ({placeholders})',
                *title_codes_with_desc,
            )
        else:
            cnt_pos_desc = 0
    except Exception:
        cnt_pos_desc = 0
    data["metrics"]["cnt_positions_full_desc"] = cnt_pos_desc or 0
    data["metrics"]["pct_positions_full_desc"] = (
        round((cnt_pos_desc or 0) / max(total_positions or 1, 1) * 100, 1)
    )

    # Title ages from enrichment CSV
    ages = []
    for code, info in enrichment.items():
        if info["effective_date"]:
            try:
                dt = datetime.strptime(info["effective_date"], "%m/%d/%Y")
                age = (datetime.now() - dt).days / 365.25
                ages.append((code, info, age))
            except ValueError:
                pass

    if ages:
        ages.sort(key=lambda x: x[2], reverse=True)
        data["metrics"]["oldest_title_age"] = round(ages[0][2], 1)
        oldest_code = ages[0][0]
        oldest_desc = await conn.fetchval(
            'SELECT "Title Description" FROM nyccivilservicetitles '
            'WHERE "Title Code" = $1 LIMIT 1',
            oldest_code,
        )
        data["metrics"]["oldest_title_name"] = oldest_desc or oldest_code
        age_vals = [a[2] for a in ages]
        data["metrics"]["avg_age"] = round(sum(age_vals) / len(age_vals), 1)
        sorted_ages = sorted(age_vals)
        mid = len(sorted_ages) // 2
        data["metrics"]["median_age"] = (
            round(sorted_ages[mid], 1)
            if len(sorted_ages) % 2
            else round((sorted_ages[mid - 1] + sorted_ages[mid]) / 2, 1)
        )
    else:
        data["metrics"]["oldest_title_age"] = 0
        data["metrics"]["oldest_title_name"] = "N/A"
        data["metrics"]["avg_age"] = 0
        data["metrics"]["median_age"] = 0

    # --- Charts ---
    # Timeline chart (titles by effective date year)
    year_counts = {}
    for _, info, _ in ages:
        try:
            year = info["effective_date"].split("/")[-1]
            year_counts[year] = year_counts.get(year, 0) + 1
        except (IndexError, ValueError):
            pass
    sorted_years = sorted(year_counts.items())
    data["charts"]["timeline"] = {
        "years": [y for y, _ in sorted_years],
        "counts": [c for _, c in sorted_years],
    }

    # Bucket chart (distribution of positions per title — latest pub date only)
    try:
        buckets_raw = await conn.fetch(
            f'SELECT "TITLE CODE", SUM(CAST("POSITIONS" AS INTEGER)) as pos '
            f'FROM {PS_LATEST} GROUP BY "TITLE CODE"'
        )
        bucket_map = {
            "0": 0, "1-5": 0, "6-20": 0, "21-50": 0,
            "51-100": 0, "101-500": 0, "500+": 0,
        }
        for r in buckets_raw:
            p = r["pos"]
            if p == 0: bucket_map["0"] += 1
            elif p <= 5: bucket_map["1-5"] += 1
            elif p <= 20: bucket_map["6-20"] += 1
            elif p <= 50: bucket_map["21-50"] += 1
            elif p <= 100: bucket_map["51-100"] += 1
            elif p <= 500: bucket_map["101-500"] += 1
            else: bucket_map["500+"] += 1
        data["charts"]["buckets"] = {
            "labels": list(bucket_map.keys()),
            "values": list(bucket_map.values()),
        }
    except Exception as e:
        print(f"  Bucket chart warning: {e}")
        data["charts"]["buckets"] = {"labels": [], "values": []}

    # Agency pie chart — titles missing descriptions by agency
    try:
        codes_no_desc = [
            k for k, v in enrichment.items() if v["full_desc"] != "Yes"
        ]
        if codes_no_desc:
            placeholders = ", ".join(
                f"${i+1}" for i in range(len(codes_no_desc))
            )
            agency_no_desc = await conn.fetch(
                f'SELECT "AGENCY NAME" as "Agency Name", '
                f'SUM(CAST("POSITIONS" AS INTEGER)) as "Scheduled Positions" '
                f'FROM {PS_LATEST} AND "TITLE CODE" IN ({placeholders}) '
                f'AND "AGENCY NAME" IS NOT NULL '
                f'GROUP BY "AGENCY NAME" '
                f'ORDER BY "Scheduled Positions" DESC',
                *codes_no_desc,
            )
            data["charts"]["agency_no_desc"] = [dict(r) for r in agency_no_desc]
        else:
            data["charts"]["agency_no_desc"] = []
    except Exception as e:
        print(f"  Agency pie chart warning: {e}")
        data["charts"]["agency_no_desc"] = []

    # --- Top Lists ---
    # Popular titles (top 8 by positions — latest pub date only)
    # Why: Use subqueries to aggregate positions per title code first,
    # then join to titles with DISTINCT ON to avoid duplicates from
    # multiple assignment levels with different salary rates.
    try:
        top_titles = await conn.fetch(
            'SELECT DISTINCT ON (pos_agg."Title Code") '
            'pos_agg."Title Code", t."Title Description", '
            'CAST(t."Minimum Salary Rate" AS NUMERIC) as "Minimum Salary", '
            'CAST(t."Maximum Salary Rate" AS NUMERIC) as "Maximum Salary", '
            'pos_agg.total_pos as "Total Positions using this Title" '
            'FROM ('
            '  SELECT "TITLE CODE" as "Title Code", '
            '  SUM(CAST("POSITIONS" AS INTEGER)) as total_pos '
            f'  FROM {PS_LATEST} '
            '  GROUP BY "TITLE CODE"'
            ') pos_agg '
            'JOIN nyccivilservicetitles t ON t."Title Code" = pos_agg."Title Code" '
            'ORDER BY pos_agg."Title Code", t."Assignment Level" '
        )
        # Sort by positions descending and take top 8
        top_list = sorted(
            [dict(r) for r in top_titles],
            key=lambda x: x["Total Positions using this Title"],
            reverse=True,
        )[:8]
        data["top_lists"]["agencies"] = top_list
    except Exception as e:
        print(f"  Popular titles warning: {e}")
        data["top_lists"]["agencies"] = []

    # Top 10 for chart
    try:
        top10 = await conn.fetch(
            'SELECT DISTINCT ON (pos_agg."Title Code") '
            'pos_agg."Title Code", t."Title Description", '
            'pos_agg.total_pos as "Total Positions using this Title" '
            'FROM ('
            '  SELECT "TITLE CODE" as "Title Code", '
            '  SUM(CAST("POSITIONS" AS INTEGER)) as total_pos '
            f'  FROM {PS_LATEST} '
            '  GROUP BY "TITLE CODE"'
            ') pos_agg '
            'JOIN nyccivilservicetitles t ON t."Title Code" = pos_agg."Title Code" '
            'ORDER BY pos_agg."Title Code", t."Assignment Level" '
        )
        top10_sorted = sorted(
            [dict(r) for r in top10],
            key=lambda x: x["Total Positions using this Title"],
            reverse=True,
        )[:10]
        data["top_lists"]["total"] = top10_sorted
    except Exception as e:
        print(f"  Top 10 warning: {e}")
        data["top_lists"]["total"] = []

    # Oldest titles (from enrichment dates)
    if ages:
        oldest_rows = []
        for code, info, age in ages:
            desc = await conn.fetchval(
                'SELECT "Title Description" FROM nyccivilservicetitles '
                'WHERE "Title Code" = $1 LIMIT 1',
                code,
            )
            pos = await conn.fetchval(
                f'SELECT COALESCE(SUM(CAST("POSITIONS" AS INTEGER)), 0) '
                f'FROM {PS_LATEST} AND "TITLE CODE" = $1',
                code,
            )
            oldest_rows.append({
                "Title Code": code,
                "Title Description": desc or code,
                "Effective Date": info["effective_date"],
                "Total Positions using this Title": pos or 0,
            })
        data["top_lists"]["oldest"] = oldest_rows
    else:
        data["top_lists"]["oldest"] = []

    # --- Lists ---
    # Master list for DataTable — one row per unique Title Code
    # Why: Use a LEFT JOIN with pre-aggregated stats instead of correlated
    # subqueries. The old approach ran 2 subqueries per title row against
    # positionschedule, causing statement timeouts on production.
    try:
        master = await conn.fetch(
            'WITH pos_stats AS ('
            '  SELECT "TITLE CODE" as tc, '
            '    SUM(CAST("POSITIONS" AS INTEGER)) as total_pos, '
            '    COUNT(DISTINCT "AGENCY NAME") as agency_cnt '
            f'  FROM {PS_LATEST} '
            '  GROUP BY "TITLE CODE"'
            ') '
            'SELECT DISTINCT ON (t."Title Code") '
            't."Title Code", t."Title Description", '
            'CAST(t."Minimum Salary Rate" AS NUMERIC) as "Minimum Salary", '
            'CAST(t."Maximum Salary Rate" AS NUMERIC) as "Maximum Salary", '
            'COALESCE(ps.total_pos, 0) as "Scheduled Positions", '
            'COALESCE(ps.agency_cnt, 0) as "Agencies" '
            'FROM nyccivilservicetitles t '
            'LEFT JOIN pos_stats ps ON ps.tc = t."Title Code" '
            'ORDER BY t."Title Code", t."Assignment Level"'
        )
        master_list = []
        for r in master:
            row = dict(r)
            code = row["Title Code"]
            info = enrichment.get(code, {})
            row["Full Description"] = info.get("full_desc", "") or ""
            master_list.append(row)
        # Sort by Scheduled Positions descending
        master_list.sort(
            key=lambda x: x["Scheduled Positions"], reverse=True
        )
        data["lists"]["master_list"] = master_list
    except Exception as e:
        print(f"  Master list warning: {e}")
        data["lists"]["master_list"] = []

    # Titles missing descriptions — all of them, sorted by positions
    try:
        codes_no_desc_sorted = [
            (k, v) for k, v in enrichment.items() if v["full_desc"] != "Yes"
        ]
        no_desc_rows = []
        for code, info in codes_no_desc_sorted:
            desc = await conn.fetchval(
                'SELECT "Title Description" FROM nyccivilservicetitles '
                'WHERE "Title Code" = $1 LIMIT 1',
                code,
            )
            pos = await conn.fetchval(
                f'SELECT COALESCE(SUM(CAST("POSITIONS" AS INTEGER)), 0) '
                f'FROM {PS_LATEST} AND "TITLE CODE" = $1',
                code,
            )
            no_desc_rows.append({
                "Title Code": code,
                "Title Description": desc or code,
                "Total Positions using this Title": pos or 0,
            })
        no_desc_rows.sort(
            key=lambda x: x["Total Positions using this Title"], reverse=True
        )
        data["lists"]["no_desc"] = no_desc_rows
    except Exception as e:
        print(f"  No-desc list warning: {e}")
        data["lists"]["no_desc"] = []

    if own_conn:
        await conn.close()

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    def decimal_default(obj):
        """Handle Decimal and other non-serializable types."""
        if hasattr(obj, "__float__"):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2, default=decimal_default)

    print(f"  Generated {OUTPUT_PATH}")
    print(f"    Titles: {data['metrics']['total_rows']}")
    print(f"    Positions: {data['metrics']['total_positions']:,}")
    print(f"    Full descriptions: {data['metrics']['cnt_full_desc']}")
    print(f"    With effective dates: {len(ages)}")
    print(f"    Master list: {len(data['lists']['master_list'])} rows")
    print(f"    No-desc titles: {len(data['lists']['no_desc'])}")
    print(f"    Popular titles: {len(data['top_lists']['agencies'])}")

    return data


if __name__ == "__main__":
    asyncio.run(generate())
