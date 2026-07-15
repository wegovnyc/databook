"""
Enrich capitalprojectsdollarscomp with GEO_JSON from CPDB geometry datasets.

Downloads CPDB Projects (Points) and (Polygons) from NYC Open Data Socrata API,
converts geometry to the GEO_JSON format expected by the projects map, and updates
the capitalprojectsdollarscomp table.

Usage:
    python enrich_geo_json.py              # Dry run (print stats only)
    python enrich_geo_json.py --apply      # Apply updates to database
"""

import asyncio
import json
import os
import sys
from typing import Dict, Optional
from urllib.request import urlopen, Request

import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from config import Config

# CPDB Socrata GeoJSON endpoints
POINTS_ID = "h2ic-zdws"
POLYGONS_ID = "9jkp-n57r"
SOCRATA_LIMIT = 50000  # Max rows per request

# Color palette for project categories
CATEGORY_COLORS = {
    "Fixed Asset": "#3b82f6",
    "Lump Sum": "#f59e0b",
    "ITT, Vehicles and Equipment": "#10b981",
}
DEFAULT_COLOR = "#53777a"


def fetch_geojson(dataset_id: str) -> list:
    """Fetch all GeoJSON features from a Socrata dataset."""
    url = f"https://data.cityofnewyork.us/resource/{dataset_id}.geojson?$limit={SOCRATA_LIMIT}"
    req = Request(url, headers={"Accept": "application/geo+json"})
    with urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    return data.get("features", [])


def compute_bounds(geometry: dict) -> dict:
    """Compute bounding box (W, S, E, N) from a GeoJSON geometry."""
    coords = []

    def extract_coords(obj):
        if isinstance(obj, list):
            if obj and isinstance(obj[0], (int, float)):
                coords.append(obj)
            else:
                for item in obj:
                    extract_coords(item)

    extract_coords(geometry.get("coordinates", []))

    if not coords:
        return {"W": 0, "S": 0, "E": 0, "N": 0}

    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return {
        "W": min(lons),
        "S": min(lats),
        "E": max(lons),
        "N": max(lats),
    }


def build_geo_json(feature: dict) -> Optional[str]:
    """Convert a Socrata GeoJSON feature to the map's expected GEO_JSON format.

    Why: The projects map reads GEO_JSON from each DataTable row and expects:
    - type: Feature
    - geometry: {type, coordinates}
    - properties: {custom_color, PRJ_ID, NAME, AGENCY, CATEGORY, PLANNEDCOST,
                    START_CURR, END_CURR, W, S, E, N}
    """
    geom = feature.get("geometry")
    props = feature.get("properties", {})

    if not geom or not geom.get("coordinates"):
        return None

    # Convert MultiPoint to Point (use first point)
    if geom["type"] == "MultiPoint":
        coords = geom["coordinates"]
        if not coords:
            return None
        geom = {"type": "Point", "coordinates": coords[0]}

    bounds = compute_bounds(geom)
    if bounds["W"] == 0 and bounds["S"] == 0:
        return None

    category = props.get("typecategory", props.get("typecat", ""))
    color = CATEGORY_COLORS.get(category, DEFAULT_COLOR)

    # Build the planned cost string
    planned_total = props.get("plannedcommit_total", props.get("pctotal", ""))
    if planned_total:
        try:
            planned_total = f"{float(planned_total):,.0f}"
        except (ValueError, TypeError):
            planned_total = str(planned_total)

    geo_json_obj = {
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "custom_color": color,
            "PRJ_ID": props.get("maprojid", ""),
            "NAME": props.get("description", props.get("descript", "")),
            "AGENCY": props.get("magencyname", props.get("magenname", "")),
            "CATEGORY": category,
            "PLANNEDCOST": planned_total,
            "START_CURR": props.get("mindate", ""),
            "END_CURR": props.get("maxdate", ""),
            **bounds,
        },
    }

    return json.dumps(geo_json_obj, separators=(",", ":"))


def _build_geo_lookup() -> Dict[str, str]:
    """Download CPDB geometry and build projectid/maprojid → GEO_JSON lookup."""
    print("[geo_enrich] Fetching CPDB Polygons...")
    polygons = fetch_geojson(POLYGONS_ID)
    print(f"[geo_enrich]   → {len(polygons)} polygon features")

    print("[geo_enrich] Fetching CPDB Points...")
    points = fetch_geojson(POINTS_ID)
    print(f"[geo_enrich]   → {len(points)} point features")

    # Build lookup: both maprojid and projectid → GEO_JSON string
    # This covers both old format (projectid) and new format (maprojid)
    geo_lookup: Dict[str, str] = {}

    for feat in points:
        props = feat.get("properties", {})
        geo_str = build_geo_json(feat)
        if not geo_str:
            continue
        projectid = props.get("projectid")
        maprojid = props.get("maprojid")
        if projectid:
            geo_lookup[projectid] = geo_str
        if maprojid:
            geo_lookup[maprojid] = geo_str

    # Overwrite with polygons (higher priority)
    poly_count = 0
    for feat in polygons:
        props = feat.get("properties", {})
        geo_str = build_geo_json(feat)
        if not geo_str:
            continue
        projectid = props.get("projectid")
        maprojid = props.get("maprojid")
        if projectid:
            geo_lookup[projectid] = geo_str
        if maprojid:
            geo_lookup[maprojid] = geo_str
            poly_count += 1

    print(f"[geo_enrich] Lookup built: {len(geo_lookup)} keys "
          f"({len(points)} points, {poly_count} polygons)")
    return geo_lookup


async def enrich_geo_json_hook(conn) -> None:
    """Post-ingest hook: enrich capitalprojectsdollarscomp with CPDB geometry.

    Why: The capitalprojectsdollarscomp table has a GEO_JSON column for the
    projects map, but new data ingested from Socrata doesn't include geometry.
    This hook downloads CPDB Points and Polygons from NYC Open Data and fills
    in GEO_JSON for any rows where it's missing.

    Matches the POST_INGEST_HOOKS signature: async fn(conn: asyncpg.Connection)
    """
    geo_lookup = _build_geo_lookup()

    # Get distinct PROJECT_IDs with empty GEO_JSON
    rows = await conn.fetch(
        """SELECT DISTINCT TRIM("PROJECT_ID") as pid
           FROM capitalprojectsdollarscomp
           WHERE "GEO_JSON" IS NULL OR "GEO_JSON" = ''"""
    )
    empty_ids = {r["pid"] for r in rows}
    print(f"[geo_enrich] {len(empty_ids)} distinct PROJECT_IDs with empty GEO_JSON")

    # Match
    matched = {pid: geo_lookup[pid] for pid in empty_ids if pid in geo_lookup}
    print(f"[geo_enrich] Matched {len(matched)} / {len(empty_ids)} with geometry")

    if not matched:
        print("[geo_enrich] Nothing to update")
        return

    # Apply updates
    updated = 0
    for pid, geo_str in matched.items():
        result = await conn.execute(
            'UPDATE capitalprojectsdollarscomp SET "GEO_JSON" = $1 '
            'WHERE TRIM("PROJECT_ID") = $2 AND ("GEO_JSON" IS NULL OR "GEO_JSON" = \'\')',
            geo_str, pid,
        )
        count = int(result.split()[-1])
        updated += count

    print(f"[geo_enrich] ✅ Updated {updated} rows across {len(matched)} projects")


async def enrich(apply: bool = False):
    """Standalone entry point: downloads CPDB geometry and updates the DB."""
    geo_lookup = _build_geo_lookup()

    # Connect to database
    Config.load(file='env.yaml')
    db_user = os.environ.get('POSTGRES_USER', Config.db.get('user', 'postgres'))
    db_pass = os.environ.get('POSTGRES_PASSWORD', Config.db.get('pwd', 'password'))
    db_host = os.environ.get('POSTGRES_HOST', Config.db.get('host', '127.0.0.1'))
    db_name = os.environ.get('POSTGRES_DB', Config.db.get('dbname', 'databook'))
    dsn = f"postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}"

    conn = await asyncpg.connect(dsn)

    try:
        # Get all PROJECT_IDs from the table (strip whitespace)
        rows = await conn.fetch(
            'SELECT DISTINCT TRIM("PROJECT_ID") as pid FROM capitalprojectsdollarscomp'
        )
        project_ids = {r["pid"] for r in rows}
        print(f"\nProject IDs in DB: {len(project_ids)}")

        # Match
        matched = {pid: geo_lookup[pid] for pid in project_ids if pid in geo_lookup}
        print(f"Matched with geometry: {len(matched)}")
        print(f"Unmatched: {len(project_ids) - len(matched)}")

        if not apply:
            print("\n⚠️  DRY RUN — pass --apply to update the database")
            return

        # Apply updates
        print(f"\nUpdating {len(matched)} project GEO_JSON values...")
        updated = 0
        for pid, geo_str in matched.items():
            result = await conn.execute(
                'UPDATE capitalprojectsdollarscomp SET "GEO_JSON" = $1 WHERE TRIM("PROJECT_ID") = $2',
                geo_str, pid,
            )
            count = int(result.split()[-1])
            updated += count

        print(f"✅ Updated {updated} rows across {len(matched)} projects")

        # Verify
        filled = await conn.fetchval(
            """SELECT count(*) FROM capitalprojectsdollarscomp
               WHERE "GEO_JSON" IS NOT NULL AND "GEO_JSON" != ''"""
        )
        total = await conn.fetchval(
            "SELECT count(*) FROM capitalprojectsdollarscomp"
        )
        print(f"\nVerification: {filled}/{total} rows have GEO_JSON ({filled*100//total}%)")

    finally:
        await conn.close()


if __name__ == "__main__":
    apply_flag = "--apply" in sys.argv
    asyncio.run(enrich(apply=apply_flag))

