#!/usr/bin/env python3
"""Generate spending_charts.json for the Spending landing page.

Why: The /procurement/transactions page shows two charts (spending by fiscal
year _ spending last 12 months). Querying DuckDB + S3 Parquet on every page
load takes 10-30s. This pre-computes the data to a JSON file, refreshed
daily by the scheduler loop or on-demand via CLI.

Output: /app/shared/spending_charts.json
"""
import asyncio
import json
import os

OUTPUT_PATH = os.environ.get(
    "SPENDING_CHARTS_OUTPUT",
    "/app/shared/spending_charts.json",
)


async def generate_spending_charts(conn=None):
    """Generate spending chart data from DuckDB/S3 and write to JSON file.

    Why: Follows the same pattern as generate_dashboard.py — precompute
    expensive analytics to a static JSON file served by the API.
    The conn parameter is accepted for API compatibility but not used
    (spending data comes from DuckDB, not Postgres).
    """
    from routers.oce import _query_spending_charts

    print("[spending_charts] Generating spending charts...")

    try:
        data = _query_spending_charts()
    except Exception as e:
        print(f"[spending_charts] ✗ DuckDB query failed: {e}")
        return None

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    by_year_count = len(data.get("by_year", {}).get("labels", []))
    by_month_count = len(data.get("by_month", {}).get("labels", []))
    print(f"[spending_charts] ✓ Generated {OUTPUT_PATH}")
    print(f"[spending_charts]   {by_year_count} fiscal years, "
          f"{by_month_count} monthly data points")

    return data


if __name__ == "__main__":
    asyncio.run(generate_spending_charts())
