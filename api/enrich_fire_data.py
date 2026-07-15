"""
enrich_fire_data.py
Pre-computes spatial joins for FDNY datasets using DuckDB and updates PostgreSQL.
"""
import asyncio
import os
import sys

import asyncpg
import duckdb

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
try:
    from config import Config
except ImportError:
    # Handle standalone mode or when run outside of api directory
    class Config:
        db = {}
        @classmethod
        def load(cls, file):
            pass

async def enrich(apply: bool = False):
    Config.load(file='env.yaml')
    db_user = os.environ.get('POSTGRES_USER', Config.db.get('user', 'postgres'))
    db_pass = os.environ.get('POSTGRES_PASSWORD', Config.db.get('pwd', 'password'))
    db_host = os.environ.get('POSTGRES_HOST', Config.db.get('host', '127.0.0.1'))
    db_name = os.environ.get('POSTGRES_DB', Config.db.get('dbname', 'databook'))
    
    dsn = f"postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}"

    conn = await asyncpg.connect(dsn)
    
    try:
        print("Verifying schema / ensuring target columns exist...")
        # Create columns if they don't exist
        for tbl in ['fdny_inspections', 'fdny_violations', 'fire_causes']:
            await conn.execute(f"""
                ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS battalion_id TEXT;
                CREATE INDEX IF NOT EXISTS idx_{tbl}_battalion ON {tbl}(battalion_id);
            """)
        
        await conn.execute("""
            ALTER TABLE fire_incident_dispatch ADD COLUMN IF NOT EXISTS battalion_ids TEXT[];
            CREATE INDEX IF NOT EXISTS idx_fire_incident_dispatch_battalions ON fire_incident_dispatch USING GIN(battalion_ids);
        """)
    except asyncpg.exceptions.UndefinedTableError as e:
        print(f"Note: Some tables might not exist yet: {e}")
        # Proceed anyway to test duckdb logic
    except Exception as e:
        print(f"Schema update error: {e}")
    
    print("\nInitializing DuckDB...")
    db = duckdb.connect()
    db.execute("PRAGMA memory_limit='1GB'")
    db.execute("PRAGMA temp_directory='/tmp'")
    
    print("Installing/Loading DuckDB extensions...")
    db.execute("INSTALL spatial;")
    db.execute("LOAD spatial;")
    db.execute("INSTALL postgres;")
    db.execute("LOAD postgres;")
    
    print("Attaching to PostgreSQL...")
    db.execute(f"CALL postgres_attach('{dsn}', source_schema='public');")

    print("\nLoading GeoJSON geometries from map.databook.nyc...")
    # Load Fire Battalions and Police Precincts
    db.execute("""
        CREATE TEMPORARY TABLE fb AS 
        SELECT nameCol AS fb_id, geom 
        FROM st_read('https://map.databook.nyc/data/fb.geojson')
    """)
    fb_count = db.execute("SELECT COUNT(*) FROM fb").fetchone()[0]
    print(f"Loaded {fb_count} Fire Battalions")
    
    db.execute("""
        CREATE TEMPORARY TABLE pp AS 
        SELECT nameCol AS pp_id, geom 
        FROM st_read('https://map.databook.nyc/data/pp.geojson')
    """)
    pp_count = db.execute("SELECT COUNT(*) FROM pp").fetchone()[0]
    print(f"Loaded {pp_count} Police Precincts")

    if not apply:
        print("\n⚠️ DRY RUN - Exiting before updating PostgreSQL rows.")
        await conn.close()
        return

    print("\n--- Applying Spatial Joins ---")

    # Update Inspections & Violations (ST_Within)
    for table in ['fdny_inspections', 'fdny_violations']:
        try:
            print(f"Enriching {table}...")
            # We select rows where battalion_id IS NULL and latitude/longitude are present
            query = f"""
                SELECT p.id, fb.fb_id
                FROM {db_name}.{table} p
                JOIN fb ON ST_Within(
                    ST_Point(CAST(p.longitude AS DOUBLE), CAST(p.latitude AS DOUBLE)), 
                    fb.geom
                )
                WHERE p.battalion_id IS NULL 
                  AND p.latitude IS NOT NULL 
                  AND p.longitude IS NOT NULL
            """
            updates = db.execute(query).fetchall()
            if updates:
                await conn.executemany(
                    f"UPDATE {table} SET battalion_id = $1 WHERE id = $2",
                    [(row[1], row[0]) for row in updates]
                )
                print(f"✅ Updated {len(updates)} rows in {table}")
            else:
                print(f"No new rows to update in {table}")
        except duckdb.BinderException:
            print(f"Skipping {table} (table likely not ingested yet).")
        except Exception as e:
            print(f"Error enriching {table}: {e}")

    # Update Fire Causes
    try:
        print(f"\nEnriching fire_causes...")
        result = await conn.execute("""
            UPDATE fire_causes 
            SET battalion_id = "Battalion" 
            WHERE battalion_id IS NULL AND "Battalion" IS NOT NULL
        """)
        updated = int(result.split()[-1])
        print(f"✅ fire_causes updated: {updated} rows.")
    except asyncpg.exceptions.UndefinedTableError:
        print("Skipping fire_causes (table likely not ingested yet).")
    except Exception as e:
        print(f"Error updating fire_causes: {e}")

    # Update Fire Incident Dispatch (ST_Intersects PP to FB crosswalk)
    try:
        print("\nBuilding Dispatch Crosswalk (Police Precinct to Fire Battalions)...")
        # Crosswalk mapping policeprecinct to array of battalion_ids
        crosswalk_query = """
            SELECT pp.pp_id, list(fb.fb_id) AS fb_list
            FROM pp
            JOIN fb ON ST_Intersects(pp.geom, fb.geom)
            GROUP BY pp.pp_id
        """
        crosswalk_rows = db.execute(crosswalk_query).fetchall()
        crosswalk_dict = {str(row[0]): row[1] for row in crosswalk_rows}
        print(f"Built crosswalk for {len(crosswalk_dict)} Police Precincts")
        
        print("Enriching fire_incident_dispatch...")
        # Get rows to update
        dispatch_rows = await conn.fetch("""
            SELECT id, policeprecinct 
            FROM fire_incident_dispatch 
            WHERE battalion_ids IS NULL AND policeprecinct IS NOT NULL
        """)
        
        dispatch_updates = []
        for r in dispatch_rows:
            # Socrata returns floats as strings, e.g. "78" or "78.0". Safe conversion:
            try:
                pp = str(int(float(r['policeprecinct'])))
            except (ValueError, TypeError):
                pp = str(r['policeprecinct']).strip()
                
            if pp in crosswalk_dict:
                dispatch_updates.append((crosswalk_dict[pp], r['id']))
                
        if dispatch_updates:
            await conn.executemany(
                "UPDATE fire_incident_dispatch SET battalion_ids = $1 WHERE id = $2",
                dispatch_updates
            )
            print(f"✅ Updated {len(dispatch_updates)} rows in fire_incident_dispatch")
        else:
            print("No new rows to update in fire_incident_dispatch")
    except asyncpg.exceptions.UndefinedTableError:
        print("Skipping fire_incident_dispatch (table likely not ingested yet).")
    except duckdb.BinderException:
        pass
    except Exception as e:
        print(f"Error enriching fire_incident_dispatch: {e}")

    await conn.close()


# =============================================================================
# Post-Ingest Hooks (called by data_scheduler.py)
# =============================================================================
# These match the POST_INGEST_HOOKS signature: async fn(conn: asyncpg.Connection)

def _get_dsn() -> str:
    """Build a PostgreSQL DSN from environment/config for DuckDB's postgres scanner."""
    db_cfg = getattr(Config, 'db', {}) or {}
    db_user = os.environ.get('POSTGRES_USER', db_cfg.get('user', 'postgres'))
    db_pass = os.environ.get('POSTGRES_PASSWORD', db_cfg.get('pwd', ''))
    db_host = os.environ.get('POSTGRES_HOST', db_cfg.get('host', '127.0.0.1'))
    db_name = os.environ.get('POSTGRES_DB', db_cfg.get('dbname', 'databook'))
    return f"postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}"


def _init_duckdb_spatial():
    """Create a memory-capped DuckDB connection with spatial + postgres extensions."""
    db = duckdb.connect()
    db.execute("PRAGMA memory_limit='1GB'")
    db.execute("PRAGMA temp_directory='/tmp'")
    db.execute("INSTALL spatial; LOAD spatial;")
    db.execute("INSTALL postgres; LOAD postgres;")
    return db


def _load_fb_geojson(db):
    """Load Fire Battalion polygons into a temporary DuckDB table.

    Why nameCol directly: DuckDB's st_read flattens GeoJSON properties into
    top-level columns, so 'nameCol' is a direct column, not nested under
    'properties'.
    """
    db.execute("""
        CREATE OR REPLACE TEMPORARY TABLE fb AS
        SELECT nameCol AS fb_id, geom
        FROM st_read('https://map.databook.nyc/data/fb.geojson')
    """)
    return db.execute("SELECT COUNT(*) FROM fb").fetchone()[0]


async def enrich_fire_causes_hook(conn) -> None:
    """Post-ingest hook for fire_causes: copy the existing battalion column."""
    print("[fire_hook] Enriching fire_causes...")
    try:
        await conn.execute(
            "ALTER TABLE fire_causes ADD COLUMN IF NOT EXISTS battalion_id TEXT")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fire_causes_battalion ON fire_causes(battalion_id)")
        result = await conn.execute("""
            UPDATE fire_causes
            SET battalion_id = "Battalion"
            WHERE battalion_id IS NULL AND "Battalion" IS NOT NULL
        """)
        updated = int(result.split()[-1])
        print(f"[fire_hook] ✅ fire_causes: {updated} rows enriched")
    except Exception as e:
        print(f"[fire_hook] ✗ fire_causes: {e}")


async def enrich_inspections_hook(conn) -> None:
    """Post-ingest hook for fdny_inspections: ST_Within spatial join."""
    await _enrich_point_table(conn, 'fdny_inspections')


async def enrich_violations_hook(conn) -> None:
    """Post-ingest hook for fdny_violations: ST_Within spatial join."""
    await _enrich_point_table(conn, 'fdny_violations')


async def _enrich_point_table(conn, table_name: str) -> None:
    """Shared logic for tables with LATITUDE/LONGITUDE → battalion_id.

    Uses Shapely STRtree (R-tree spatial index) for O(log n) point-in-polygon
    lookups instead of DuckDB's brute-force O(n×m) ST_Within.
    """
    import requests as _requests
    from shapely.geometry import shape as _shape, Point as _Point
    from shapely import STRtree as _STRtree

    print(f"[fire_hook] Enriching {table_name}...")
    try:
        await conn.execute(
            f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS battalion_id TEXT')
        await conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{table_name}_battalion ON "{table_name}"(battalion_id)')

        # Determine the unique key column for UPDATE targeting
        key_col_map = {
            'fdny_inspections': 'ACCT_ID',
            'fdny_violations': 'VIO_ID',
        }
        key_col = key_col_map.get(table_name)
        if not key_col:
            first = await conn.fetchval(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = $1 ORDER BY ordinal_position LIMIT 1",
                table_name)
            key_col = first

        # Load Fire Battalion polygons into STRtree
        resp = _requests.get('https://map.databook.nyc/data/fb.geojson', timeout=30)
        gj = resp.json()
        polys = []
        fb_ids = []
        for f in gj['features']:
            polys.append(_shape(f['geometry']))
            fb_ids.append(f['properties']['nameCol'])
        tree = _STRtree(polys)
        print(f"[fire_hook]   Built STRtree with {len(polys)} Fire Battalions")

        # Read un-enriched rows with coordinates from Postgres
        rows = await conn.fetch(f'''
            SELECT "{key_col}", "LATITUDE", "LONGITUDE"
            FROM "{table_name}"
            WHERE battalion_id IS NULL
              AND "LATITUDE" IS NOT NULL AND "LATITUDE" != ''
              AND "LONGITUDE" IS NOT NULL AND "LONGITUDE" != ''
        ''')
        print(f"[fire_hook]   {len(rows)} rows to spatially join")
        if not rows:
            print(f"[fire_hook]   {table_name}: no rows to enrich")
            return

        # Point-in-polygon via STRtree
        updates = []
        skipped = []
        for i, r in enumerate(rows):
            try:
                pt = _Point(float(r['LONGITUDE']), float(r['LATITUDE']))
            except (ValueError, TypeError):
                skipped.append(str(r[key_col]))
                continue

            idx = tree.nearest(pt)
            if polys[idx].contains(pt):
                updates.append((fb_ids[idx], str(r[key_col])))
            else:
                found = False
                for j in tree.query(pt):
                    if polys[j].contains(pt):
                        updates.append((fb_ids[j], str(r[key_col])))
                        found = True
                        break
                if not found:
                    skipped.append(str(r[key_col]))

            if (i + 1) % 50000 == 0:
                print(f"[fire_hook]     Processed {i+1}/{len(rows)}", flush=True)

        print(f"[fire_hook]   Spatial join: {len(updates)} matched, "
              f"{len(skipped)} unmatched")

        # Batch write matched rows
        BATCH = 10000
        if updates:
            for i in range(0, len(updates), BATCH):
                await conn.executemany(
                    f'UPDATE "{table_name}" SET battalion_id = $1 WHERE "{key_col}" = $2',
                    updates[i:i+BATCH])
            print(f"[fire_hook] ✅ {table_name}: {len(updates)} rows enriched")

        # Mark unmatched so they're skipped on next run
        if skipped:
            for i in range(0, len(skipped), BATCH):
                await conn.executemany(
                    f'UPDATE "{table_name}" SET battalion_id = $1 WHERE "{key_col}" = $2',
                    [('', k) for k in skipped[i:i+BATCH]])
    except Exception as e:
        print(f"[fire_hook] ✗ {table_name}: {e}")


async def enrich_dispatch_hook(conn) -> None:
    """Post-ingest hook for fire_incident_dispatch: PP→FB crosswalk via pre-computed table.

    Why a crosswalk table: dispatch records have no lat/lon — only a
    policeprecinct column. The pp_fb_crosswalk table maps each precinct
    to its overlapping fire battalion(s). This was pre-computed from
    GeoJSON polygon intersections and stored as a tiny 77-row table.
    """
    print("[fire_hook] Enriching fire_incident_dispatch...")
    try:
        await conn.execute(
            "ALTER TABLE fire_incident_dispatch ADD COLUMN IF NOT EXISTS battalion_ids TEXT[]")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fire_incident_dispatch_battalions
            ON fire_incident_dispatch USING GIN(battalion_ids)
        """)

        # Ensure crosswalk table exists
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'pp_fb_crosswalk')")
        if not exists:
            print("[fire_hook] ✗ pp_fb_crosswalk table missing — run crosswalk.sql first")
            return

        result = await conn.execute("""
            UPDATE fire_incident_dispatch d
            SET battalion_ids = c.fb_ids
            FROM pp_fb_crosswalk c
            WHERE d.policeprecinct = c.pp_id
              AND d.battalion_ids IS NULL
        """)
        updated = int(result.split()[-1])
        print(f"[fire_hook] ✅ fire_incident_dispatch: {updated} rows enriched via crosswalk")
    except Exception as e:
        print(f"[fire_hook] ✗ fire_incident_dispatch: {e}")


if __name__ == "__main__":
    apply_flag = "--apply" in sys.argv
    asyncio.run(enrich(apply=apply_flag))
