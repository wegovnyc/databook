"""
Data Pipeline API routes — registry CRUD, health dashboard, manual triggers.

Mounted as a FastAPI router at the /pipeline prefix.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Security, Query
from fastapi.responses import JSONResponse

from postgrex import PostgresModelAsync


router = APIRouter(prefix="/pipeline", tags=["Data Pipeline"])


# =============================================================================
# Helpers
# =============================================================================

async def _select(query: str, params: tuple = ()):
    """Run a SELECT and return rows as list of dicts."""
    from main import select
    return await select(query, params)


# =============================================================================
# Dataset Registry CRUD
# =============================================================================

@router.get("/registry", summary="List all datasets in the registry")
async def list_registry(
    source_type: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = True,
):
    """
    Get all datasets in the dataset_registry.

    Optionally filter by source_type (socrata, extractor, manual),
    category, or active status.
    """
    conditions = []
    params = []
    idx = 1

    if active_only:
        conditions.append(f"is_active = ${idx}")
        params.append(True)
        idx += 1

    if source_type:
        conditions.append(f"source_type = ${idx}")
        params.append(source_type)
        idx += 1

    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    return await _select(
        f"SELECT * FROM dataset_registry {where} ORDER BY category, table_name",
        tuple(params)
    )


@router.get("/registry/{table_name}", summary="Get a single dataset entry")
async def get_registry_entry(table_name: str):
    """Get detailed information about a specific dataset."""
    result = await _select(
        "SELECT * FROM dataset_registry WHERE table_name = $1",
        (table_name,)
    )
    rows = result.get('rows', [])
    if not rows:
        return JSONResponse(status_code=404,
                            content={"error": f"Dataset '{table_name}' not found"})
    return {"dataset": rows[0]}


@router.patch("/registry/{table_name}", summary="Update a dataset entry")
async def update_registry_entry(
    table_name: str,
    is_active: Optional[bool] = None,
    ingestion_mode: Optional[str] = None,
    natural_key: Optional[str] = None,
    needs_normalization: Optional[bool] = None,
    refresh_strategy: Optional[str] = None,
):
    """Update fields on a dataset registry entry."""
    updates = {}
    if is_active is not None:
        updates['is_active'] = is_active
    if ingestion_mode is not None:
        updates['ingestion_mode'] = ingestion_mode
    if natural_key is not None:
        updates['natural_key'] = natural_key
    if needs_normalization is not None:
        updates['needs_normalization'] = needs_normalization

    if not updates:
        return JSONResponse(status_code=400,
                            content={"error": "No fields to update"})

    sets = []
    vals = [table_name]
    for i, (k, v) in enumerate(updates.items(), 2):
        sets.append(f"{k} = ${i}")
        vals.append(v)

    await PostgresModelAsync.execute(
        f"UPDATE dataset_registry SET {', '.join(sets)} WHERE table_name = $1",
        tuple(vals)
    )
    return {"result": "OK", "updated": list(updates.keys())}


# =============================================================================
# Cached Homepage Stats
# =============================================================================

@router.get("/globstats", summary="Cached homepage statistics")
async def get_cached_glob_stats():
    """Return pre-computed homepage stats from the cached_stats table.

    Rebuilt daily by the scheduler after each data check cycle.
    """
    result = await _select(
        "SELECT stats, computed_at FROM cached_stats WHERE id = 1")
    rows = result.get("rows", []) if isinstance(result, dict) else result
    if not rows:
        return {"error": "Stats not yet computed", "stats": {}}
    import json as _json
    row = rows[0]
    stats = _json.loads(row['stats']) if isinstance(row['stats'], str) else row['stats']
    stats['_computed_at'] = row.get('computed_at', '')
    return stats


@router.get("/dataset-counts", summary="Live dataset/record counts from the registry")
async def get_dataset_counts():
    """Return live dataset count, total records, and latest update timestamp.

    Uses a direct DB connection (not the shared pool) to avoid contention
    during startup when the briefing cache rebuild saturates the pool.
    """
    import asyncpg
    from config import Config
    try:
        conn = await asyncpg.connect(
            user=Config.db['user'], password=Config.db['pwd'],
            database=Config.db['dbname'], host=Config.db['host'],
            timeout=10, statement_cache_size=0)
        try:
            row = await conn.fetchrow(
                """SELECT count(*) as total_datasets_no,
                          COALESCE(SUM(estimated_rows), 0)::bigint as total_records_no,
                          MAX(last_ingested_at) as latest_update
                   FROM dataset_registry
                   WHERE estimated_rows > 0""")
            return {
                "total_datasets_no": row['total_datasets_no'],
                "total_records_no": row['total_records_no'],
                "latest_update": row['latest_update'].isoformat() if row['latest_update'] else None
            }
        finally:
            await conn.close()
    except Exception as e:
        return {"total_datasets_no": 0, "total_records_no": 0, "latest_update": None, "error": str(e)}


# =============================================================================
# Data Health Dashboard
# =============================================================================

@router.get("/health", summary="Data health dashboard")
async def data_health():
    """
    Comprehensive data health view combining registry, ingestion log,
    and unmapped entity counts.

    Returns each dataset with status indicators:
    - 🟢 Active: our dataset was updated after source was last updated
    - 🟡 Update Needed: source has newer data than our last ingestion
    - 🔴 Error: last check failed, dataset is empty, or never ingested
    """
    # Get registry with latest ingestion info + actual Postgres row counts
    registry = await _select("""
        SELECT
            r.*,
            (SELECT COUNT(*) FROM unmapped_entities u
             WHERE u.table_name = r.table_name
               AND u.resolved_at IS NULL) as unmapped_count,
            (SELECT MAX(ingested_at) FROM ingestion_log l
             WHERE l.table_name = r.table_name
               AND l.status = 'success') as log_last_ingested,
            (SELECT status FROM ingestion_log l
             WHERE l.table_name = r.table_name
             ORDER BY l.ingested_at DESC LIMIT 1) as last_status,
            (SELECT c.reltuples::bigint FROM pg_class c
             JOIN pg_namespace n ON c.relnamespace = n.oid
             WHERE c.relname = r.table_name AND n.nspname = 'public') as actual_row_count,
            (SELECT pg_size_pretty(pg_total_relation_size(c.oid))
             FROM pg_class c
             JOIN pg_namespace n ON c.relnamespace = n.oid
             WHERE c.relname = r.table_name AND n.nspname = 'public') as actual_table_size
        FROM dataset_registry r
        WHERE r.is_active = TRUE AND r.source_type != 'internal'
        ORDER BY r.category, r.table_name
    """)

    rows = registry.get('rows', [])
    now = datetime.now(timezone.utc)

    def _parse_ts(ts):
        """Parse a timestamp string or datetime into a tz-aware datetime."""
        if not ts:
            return None
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except ValueError:
                return None
        if not getattr(ts, 'tzinfo', None):
            ts = ts.replace(tzinfo=timezone.utc)
        return ts

    def _format_age(ts, now):
        """Format a timestamp as a human-readable relative label."""
        if not ts:
            return '—'
        days = (now - ts).days
        if days <= 0:
            return 'Today'
        elif days == 1:
            return '1d ago'
        else:
            return f'{days}d ago'

    for row in rows:
        # Build S3 URL from s3_key
        s3_key = row.get('s3_key')
        row['s3_url'] = (
            f"https://databook2.s3.amazonaws.com/{s3_key}" if s3_key else None
        )

        # Parse timestamps
        last_ingested = _parse_ts(row.get('last_ingested_at'))
        log_ingested = _parse_ts(row.get('log_last_ingested'))
        last_updated = max(filter(None, [last_ingested, log_ingested]), default=None)
        last_checked = _parse_ts(row.get('last_checked_at'))
        source_updated = _parse_ts(row.get('last_source_updated_at'))
        actual_rows = row.get('actual_row_count') or 0
        last_status = row.get('last_status', '')
        last_error = row.get('last_error', '')
        source_type = row.get('source_type', '')

        # Human-readable labels
        row['last_checked_label'] = _format_age(last_checked, now)
        row['last_updated_label'] = _format_age(last_updated, now)
        row['source_updated_label'] = _format_age(source_updated, now)

        # ── Status logic ──────────────────────────────────────────
        # Ignore stale/false-positive errors:
        #   - "HTTP 200" stored as error is not a real error
        #   - If data was successfully ingested AFTER the error, treat as resolved
        real_error = last_error and last_error.strip().upper() != 'HTTP 200'
        if real_error and last_updated:
            # Error happened but data was ingested — stale error, ignore
            real_error = False

        # Internal datasets have no external source — skip status
        if source_type == 'internal':
            row['status'] = 'none'
            row['status_label'] = '—'
        # Never ingested
        elif not last_updated:
            if real_error:
                row['status'] = 'error'
                row['status_label'] = 'Potential Issue'
            else:
                row['status'] = 'error'
                row['status_label'] = 'Never ingested'
        # Has error and no successful ingestion
        elif real_error:
            row['status'] = 'error'
            row['status_label'] = 'Potential Issue'
        elif actual_rows == 0:
            row['status'] = 'error'
            row['status_label'] = 'Empty'
        # Update Needed: source was updated after our last ingestion
        elif source_updated and last_updated < source_updated:
            row['status'] = 'update_needed'
            row['status_label'] = 'Update Needed'
        # Active: our data is current (or no source timestamp to compare)
        else:
            row['status'] = 'active'
            row['status_label'] = 'Active'

    # Map table_name → site sections (derived from dataset config files)
    # Source: OrgsDatasets.php, TitlesDatasets.php, ProjectsDatasets.php,
    #         DistDatasets.php, SchoolDatasets.php, CROLDatasets.php,
    #         AuctionsDatasets.php, UnDatasets.php, ProcurementController.php
    SECTION_MAP = {
        # ── Organizations (OrgsDatasets.php) ──────────────────────
        'expensebudgetonnycopendata': ['Organizations'],
        'capitalprojectsdollarscomp': ['Organizations', 'Projects', 'Districts'],
        'benefitsapi': ['Organizations'],
        'nycgreenbook': ['Organizations', 'People'],
        'agencypmi': ['Organizations'],
        'budgetrequestsregister': ['Organizations', 'Districts'],
        'nycjobs': ['Organizations', 'Titles'],
        'facilitydb': ['Organizations', 'Districts'],
        'onenycindicators': ['Organizations'],
        'fy2021mmragencyperformance': ['Organizations'],
        'fy2021mmragencyresources': ['Organizations'],
        'locallaw251': ['Organizations'],
        'nyccouncildiscretionaryfunding': ['Organizations', 'Districts'],
        'opendatareleasetracker': ['Organizations'],
        'expenseplan': ['Organizations'],
        'headcountactualsfunding': ['Organizations'],
        'expenseactualsfunding': ['Organizations'],
        'additionalcostsallocation': ['Organizations'],
        'govpublist': ['Organizations'],
        'govpubrequired': ['Organizations'],
        'fteheadcount': ['Organizations'],
        'positionschedule': ['Organizations', 'Titles'],
        'll18payanddemo': ['Organizations'],
        'civillist': ['Organizations', 'People', 'Titles'],
        'civillistactive': ['Organizations', 'People', 'Titles'],
        'publishedwebsitedata': ['Organizations'],
        'payrolldata': ['Organizations', 'People'],
        'resourcesmmr': ['Organizations'],
        'crol': ['Organizations', 'Notices'],
        # ── Titles (TitlesDatasets.php) ───────────────────────────
        # positionschedule, nycjobs, civillist, civillistactive already above
        'nyccivilservicetitles': ['Titles'],
        # ── People (People.php controller) ────────────────────────
        # civillist, civillistactive, payrolldata, nycgreenbook already above
        # ── Projects (ProjectsDatasets.php, Projects.php) ─────────
        'capitalprojectslist': ['Projects'],
        'capitalprojectsdollars': ['Projects'],
        'capitalprojectscommitments': ['Projects'],
        'capitalprojectsmilestones': ['Projects'],
        'capitalstrategy': ['Projects'],
        'capitalbudget': ['Projects'],
        'capitalcommitmentplan': ['Projects'],
        'capprojectsbudgetandspend': ['Projects'],
        'capprojectsbudgetsandschedule': ['Projects'],
        'capprojectsbudgetspendhistory': ['Projects'],
        'capprojectsschedulehistory': ['Projects'],
        'ceqrprojectlocation': ['Projects'],
        'ceqrprojectmilestones': ['Projects'],
        # ── Districts (DistDatasets.php) ──────────────────────────
        # budgetrequestsregister, facilitydb, nyccouncildiscretionaryfunding,
        # capitalprojectsdollarscomp, schoollocations, scacapitalprojectschedules
        # already above
        'scademostats': ['Districts'],
        'demographics': ['Districts', 'Schools'],
        'councilstatcases': ['Districts'],
        'ccmembers': ['Districts'],
        'nyccommunityboards': ['Districts'],
        # ── Schools (SchoolDatasets.php) ──────────────────────────
        'schoollocations': ['Schools', 'Districts'],
        'attendance': ['Schools'],
        'scaenrollmentcapacity': ['Schools'],
        'temphousing': ['Schools'],
        'guidancecounsellors': ['Schools'],
        'dohmhinspections': ['Schools'],
        'scaactiveprojects': ['Schools'],
        'scacapitalprojectschedules': ['Schools', 'Districts'],
        'scaschoolprograms': ['Schools'],
        'scacurrentplan': ['Schools'],
        'scaaddedprojects': ['Schools'],
        'schoolcampus': ['Schools'],
        # ── Notices (CROLDatasets.php) ────────────────────────────
        # crol already above
        # ── Procurement (ProcurementController.php) ───────────────
        'contracts': ['Procurement'],
        'solicitations': ['Procurement'],
        'vendors': ['Procurement'],
        'passport': ['Procurement'],
        'passport_contracts': ['Procurement'],
        'passport_solicitations': ['Procurement'],
        # ── Other ─────────────────────────────────────────────────
        'auctions': ['Notices'],
        'ft_fte_staff_levels': ['Organizations'],
        'll18payanddemoreport': ['Organizations'],
        'expenseactualsfundingtest': ['Organizations'],
        'streetandhighwayblock': ['Districts'],
        'streetandhighwayintersection': ['Districts'],
        'websitedata': ['Organizations'],
    }

    # Fetch normalizer task/alert count per dataset
    normalizer_alerts = {}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://normalize.databook.nyc/tasks"
            )
            if resp.status_code == 200:
                tasks = resp.json()
                for t in tasks:
                    ds_id = t.get('dataset_id')
                    if ds_id and not t.get('resolved'):
                        normalizer_alerts[ds_id] = (
                            normalizer_alerts.get(ds_id, 0) + 1
                        )
    except Exception:
        pass  # Normalizer may be down

    for row in rows:
        tn = row.get('table_name', '')
        row['sections'] = SECTION_MAP.get(tn, [])
        nid = row.get('normalizer_dataset_id')
        row['alert_count'] = normalizer_alerts.get(nid, 0) if nid else 0

    # Summary stats
    active = sum(1 for r in rows if r.get('status') == 'active')
    update_needed = sum(1 for r in rows if r.get('status') == 'update_needed')
    error = sum(1 for r in rows if r.get('status') == 'error')
    total_alerts = sum(r.get('alert_count', 0) for r in rows)

    # Flag rows where estimated vs actual row count diverges
    mismatched = 0
    for row in rows:
        est = row.get('estimated_rows') or 0
        actual = row.get('actual_row_count') or 0
        if est > 0 and actual == 0:
            row['sync_status'] = 'not_imported'
        elif est > 0 and abs(est - actual) > max(est * 0.05, 10):
            row['sync_status'] = 'mismatch'
            mismatched += 1
        else:
            row['sync_status'] = 'ok'

    return {
        "summary": {
            "total_datasets": len(rows),
            "active": active,
            "update_needed": update_needed,
            "error": error,
            "total_alerts": total_alerts,
            "row_count_mismatches": mismatched,
            "checked_at": now.isoformat(),
        },
        "datasets": rows,
    }


@router.get("/verify", summary="Verify S3 ↔ Postgres sync")
async def verify_sync():
    """Compare estimated row counts against actual Postgres rows.

    Why: Detects silent import failures where data reached S3 but
    wasn't fully loaded into Postgres (e.g., 502 timeouts).
    """
    result = await _select("""
        SELECT
            r.table_name,
            r.display_name,
            r.estimated_rows,
            r.s3_key,
            CASE WHEN EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE c.relname = r.table_name AND n.nspname = 'public'
            ) THEN TRUE ELSE FALSE END as table_exists,
            COALESCE(
                (SELECT c.reltuples::bigint FROM pg_class c
                 JOIN pg_namespace n ON c.relnamespace = n.oid
                 WHERE c.relname = r.table_name AND n.nspname = 'public'),
                0
            ) as actual_rows,
            pg_size_pretty(CASE WHEN EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE c.relname = r.table_name AND n.nspname = 'public'
            ) THEN pg_total_relation_size(r.table_name::regclass)
            ELSE 0 END) as table_size
        FROM dataset_registry r
        WHERE r.is_active = TRUE
        ORDER BY r.table_name
    """)

    rows = result.get('rows', [])
    issues = []
    for row in rows:
        est = row.get('estimated_rows') or 0
        actual = row.get('actual_rows') or 0
        s3 = row.get('s3_key')

        if not row.get('table_exists'):
            row['issue'] = 'table_missing'
            issues.append(row)
        elif s3 and est > 0 and actual == 0:
            row['issue'] = 'empty_table'
            issues.append(row)
        elif est > 0 and abs(est - actual) > max(est * 0.05, 10):
            row['issue'] = 'row_count_mismatch'
            row['difference'] = est - actual
            issues.append(row)
        else:
            row['issue'] = None

    return {
        "total_datasets": len(rows),
        "issues_found": len(issues),
        "issues": issues,
        "all_datasets": rows,
    }



# =============================================================================
# Registry ↔ Normalizer Sync Check
# =============================================================================

@router.get("/sync-check", summary="Check registry ↔ normalizer config sync")
async def sync_check():
    """Detect orphaned normalizer_dataset_ids or S3 file issues.

    Why: Datasets in the registry may reference normalizer IDs that
    don't exist in the normalizer's config, or have empty S3 files.
    This detects the mismatch before it causes silent import failures.
    """
    import aiohttp
    import os

    normalizer_url = os.environ.get(
        "NORMALIZER_URL", "http://3.208.92.214:8090")

    # Get all registry entries with normalizer IDs
    registry = await _select("""
        SELECT id, table_name, normalizer_dataset_id, s3_key
        FROM dataset_registry
        WHERE is_active = TRUE AND normalizer_dataset_id IS NOT NULL
        ORDER BY table_name
    """)
    reg_rows = registry.get('rows', [])

    # Fetch normalizer dataset list
    normalizer_ids = set()
    normalizer_error = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{normalizer_url}/datasets",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    normalizer_ids = {
                        d['id'] for d in data.get('datasets', data)
                        if isinstance(d, dict) and 'id' in d
                    }
                else:
                    normalizer_error = f"HTTP {resp.status}"
    except Exception as e:
        normalizer_error = str(e)

    # Check S3 file sizes for datasets with S3 keys
    S3_BUCKET = "https://databook2.s3.amazonaws.com/"
    issues = []
    for row in reg_rows:
        nid = row.get('normalizer_dataset_id')
        table = row.get('table_name')
        s3_key = row.get('s3_key')
        s3_url = f"{S3_BUCKET}{s3_key}" if s3_key else None

        # Check normalizer config
        if normalizer_ids and nid not in normalizer_ids:
            issues.append({
                'table_name': table,
                'normalizer_dataset_id': nid,
                'issue': 'orphaned_normalizer_id',
                'detail': f'ID {nid} not found in normalizer config',
            })

        # Check S3 file
        if s3_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.head(
                        s3_url,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        size = int(resp.headers.get('Content-Length', 0))
                        if resp.status != 200 or size == 0:
                            issues.append({
                                'table_name': table,
                                'normalizer_dataset_id': nid,
                                'issue': 'empty_s3_file',
                                'detail': f'S3 file is {size} bytes',
                                's3_url': s3_url,
                            })
            except Exception:
                pass

    return {
        "total_checked": len(reg_rows),
        "issues_found": len(issues),
        "normalizer_reachable": normalizer_error is None,
        "normalizer_error": normalizer_error,
        "normalizer_datasets_found": len(normalizer_ids),
        "issues": issues,
    }


@router.post("/auto-populate", summary="Auto-populate missing normalizer configs")
async def auto_populate():
    """Find registry datasets with no normalizer config and create them.

    Why: Some datasets in the registry reference normalizer_dataset_ids
    that don't exist. This creates the basic config (data_url, output_path)
    and generates a review task for src_txt_flds in the normalizer.
    """
    import aiohttp
    import os
    import re

    normalizer_url = os.environ.get(
        "NORMALIZER_URL", "http://3.208.92.214:8090")

    # Get registry entries with normalizer IDs
    registry = await _select("""
        SELECT table_name, display_name, normalizer_dataset_id,
               socrata_id, source_type
        FROM dataset_registry
        WHERE is_active = TRUE AND normalizer_dataset_id IS NOT NULL
        ORDER BY table_name
    """)
    reg_rows = registry.get('rows', [])

    # Get existing normalizer dataset IDs
    normalizer_ids = set()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{normalizer_url}/datasets",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    dsets = data.get('datasets', data)
                    if isinstance(dsets, list):
                        normalizer_ids = {
                            d['id'] for d in dsets
                            if isinstance(d, dict) and 'id' in d
                        }
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Cannot reach normalizer: {e}"})

    # Find orphaned entries
    orphans = []
    for row in reg_rows:
        nid = row.get('normalizer_dataset_id')
        if nid and nid not in normalizer_ids:
            sid = row.get('socrata_id', '')
            table = row.get('table_name', '')

            # Derive data_url from socrata_id
            data_url = ""
            if sid:
                data_url = (
                    f"https://data.cityofnewyork.us/api/views/"
                    f"{sid}/rows.csv?accessType=DOWNLOAD"
                )

            # Derive output_path from table_name (CamelCase + .csv)
            parts = re.split(r'[_\-]', table)
            camel = ''.join(p.capitalize() for p in parts)
            output_path = f"{camel}.csv"

            orphans.append({
                "id": nid,
                "name": row.get('display_name') or table,
                "data_url": data_url,
                "output_path": output_path,
                "socrata_id": sid,
            })

    if not orphans:
        return {
            "created": 0,
            "message": "All normalizer configs exist — nothing to populate",
        }

    # Send to normalizer's /auto-populate
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{normalizer_url}/auto-populate",
                json=orphans,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                result = await resp.json()
                return {
                    "created": result.get("created", 0),
                    "datasets": result.get("datasets", []),
                    "orphans_found": len(orphans),
                }
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"Normalizer /auto-populate failed: {e}"})


# =============================================================================
# Unmapped Entities
# =============================================================================

@router.get("/unmapped", summary="List unmapped entities")
async def list_unmapped(
    table_name: Optional[str] = None,
    resolved: bool = False,
    limit: int = 100,
):
    """
    Get unmapped entities, optionally filtered by dataset.

    By default returns only unresolved entities.
    """
    conditions = []
    params = []
    idx = 1

    if table_name:
        conditions.append(f"table_name = ${idx}")
        params.append(table_name)
        idx += 1

    if not resolved:
        conditions.append("resolved_at IS NULL")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    return await _select(
        f"""SELECT * FROM unmapped_entities {where}
            ORDER BY first_seen_at DESC LIMIT ${idx}""",
        tuple(params) + (limit,)
    )


@router.post("/unmapped/{entity_id}/resolve", summary="Mark entity as resolved")
async def resolve_unmapped(entity_id: int, notes: str = ""):
    """Mark an unmapped entity as resolved after manual mapping."""
    await PostgresModelAsync.execute("""
        UPDATE unmapped_entities
        SET resolved_at = NOW(), resolution_notes = $2
        WHERE id = $1
    """, (entity_id, notes))
    return {"result": "OK", "entity_id": entity_id}


# =============================================================================
# City Briefing Feed
# =============================================================================

# In-memory briefing cache — rebuilt every 6 hours via background task.
_briefing_cache = {"data": [], "computed_at": None}


async def _build_briefing():
    """Build the briefing data by querying all sections.

    Called by the background scheduler — never by the endpoint directly.
    """
    import asyncpg
    from config import Config
    from datetime import datetime

    print("[briefing] Building briefing cache...", flush=True)

    conn = await asyncpg.connect(
        user=Config.db['user'],
        password=Config.db['pwd'],
        database=Config.db['dbname'],
        host=Config.db['host'],
    )
    await conn.execute("SET statement_timeout = '60s'")

    items = []

    async def _bq(sql):
        """Run a briefing query with the dedicated connection."""
        rows = await conn.fetch(sql)
        result = []
        for r in rows:
            try:
                result.append({k: v.strip() if isinstance(v, str) else v for k, v in dict(r).items()})
            except Exception:
                pass
        return result

    try:
        # ── 1. Public Hearings & Meetings (CROL events) ──
        try:
            rows = await _bq(
                """SELECT "EventDate", "SectionName", "ShortTitle", "RequestID",
                          "wegov-org-name"
                   FROM crol
                   WHERE "SectionName" = 'Public Hearings and Meetings'
                     AND "EventDate" <> ''
                     AND "EventDate" ~ '^[0-9]{1,2}/'
                     AND TO_DATE(SPLIT_PART("EventDate", ' ', 1), 'MM/DD/YYYY')
                         >= current_date - interval '7 days'
                     AND TO_DATE(SPLIT_PART("EventDate", ' ', 1), 'MM/DD/YYYY')
                         <= current_date + interval '7 days'
                   ORDER BY TO_DATE(SPLIT_PART("EventDate", ' ', 1), 'MM/DD/YYYY')
                   LIMIT 15"""
            )
            for r in rows:
                dt_raw = r.get("EventDate", "")
                try:
                    from datetime import datetime as _dt
                    iso = _dt.strptime(dt_raw.split(" ")[0], "%m/%d/%Y").strftime("%Y-%m-%d") if dt_raw else None
                except Exception:
                    iso = None
                items.append({
                    "s": "hearing",
                    "title": (r.get("ShortTitle") or "Untitled")[:120],
                    "agency": _agency_abbr(r.get("wegov-org-name")),
                    "date": iso,
                    "time": dt_raw,
                    "context": f"City Record #{r.get('RequestID', '')}",
                    "amount": None,
                    "url": f"https://a856-cityrecord.nyc.gov/RequestDetail/{r.get('RequestID', '')}"
                })
        except Exception as e:
            print(f"[briefing] hearings error: {e}", flush=True)

        # ── 2. Rules & Regulations (CROL Agency Rules) ──
        try:
            rows = await _bq(
                """SELECT "StartDate", "ShortTitle", "RequestID",
                          "wegov-org-name", "TypeOfNoticeDescription"
                   FROM crol
                   WHERE "SectionName" = 'Agency Rules'
                     AND "StartDate" <> ''
                     AND "StartDate" ~ '^[0-9]{1,2}/'
                     AND TO_DATE(SPLIT_PART("StartDate", ' ', 1), 'MM/DD/YYYY')
                         >= current_date - interval '7 days'
                   ORDER BY TO_DATE(SPLIT_PART("StartDate", ' ', 1), 'MM/DD/YYYY') DESC
                   LIMIT 15"""
            )
            for r in rows:
                sd = r.get("StartDate", "")
                try:
                    from datetime import datetime as _dt
                    iso = _dt.strptime(sd.split(" ")[0], "%m/%d/%Y").strftime("%Y-%m-%d") if sd else None
                except Exception:
                    iso = None
                notice_type = r.get("TypeOfNoticeDescription", "")
                prefix = "Adopted: " if "adopt" in notice_type.lower() else "Proposed: " if "propos" in notice_type.lower() else ""
                items.append({
                    "s": "rules",
                    "title": f"{prefix}{(r.get('ShortTitle') or 'Untitled')[:110]}",
                    "agency": _agency_abbr(r.get("wegov-org-name")),
                    "date": iso,
                    "time": None,
                    "context": notice_type[:80] if notice_type else None,
                    "amount": None,
                    "url": f"https://a856-cityrecord.nyc.gov/RequestDetail/{r.get('RequestID', '')}"
                })
        except Exception as e:
            print(f"[briefing] rules error: {e}", flush=True)

        # ── 3. Contracts (recently started or ending) ──
        try:
            rows = await _bq(
                """SELECT contract_id, ctr_id, contract_title, vendor_name, agency,
                          award_amount, status, start_date, end_date
                   FROM contracts
                   WHERE (
                       start_date ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
                       AND TO_DATE(start_date, 'MM/DD/YYYY')
                           BETWEEN current_date - interval '7 days'
                               AND current_date + interval '7 days'
                   ) OR (
                       end_date ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
                       AND TO_DATE(end_date, 'MM/DD/YYYY')
                           BETWEEN current_date
                               AND current_date + interval '7 days'
                   )
                   ORDER BY ABS(TO_DATE(start_date, 'MM/DD/YYYY') - current_date),
                          award_amount DESC NULLS LAST
                   LIMIT 15"""
            )
            for r in rows:
                sd = r.get("start_date", "")
                ed = r.get("end_date", "")
                try:
                    from datetime import datetime as _dt
                    dt_str = _dt.strptime(sd, "%m/%d/%Y").strftime("%Y-%m-%d") if sd and '/' in sd else None
                except Exception:
                    dt_str = None
                if not dt_str:
                    try:
                        dt_str = _dt.strptime(ed, "%m/%d/%Y").strftime("%Y-%m-%d") if ed and '/' in ed else None
                    except Exception:
                        dt_str = None
                amt = r.get("award_amount")
                amt_str = _format_amount(amt) if amt else None
                ctr_id = r.get("ctr_id") or r.get("contract_id")
                items.append({
                    "s": "contracts",
                    "title": (r.get("contract_title") or "Untitled")[:120],
                    "agency": _agency_abbr(r.get("agency")),
                    "date": dt_str,
                    "time": None,
                    "context": f"Vendor: {(r.get('vendor_name') or 'N/A')[:40]} · {r.get('status', '')}",
                    "amount": amt_str,
                    "url": f"/procurement/contract/{ctr_id}" if ctr_id else "/procurement/contracts"
                })
        except Exception as e:
            print(f"[briefing] contracts error: {e}", flush=True)

        # ── 4. Solicitations (due within ±7 days) ──
        try:
            rows = await _bq(
                """SELECT "EPIN", "Procurement Name", "Agency", "Due Date",
                          "RFx Status", "Procurement Method"
                   FROM solicitations
                   WHERE "Due Date" IS NOT NULL AND "Due Date" != ''
                     AND TO_DATE(SPLIT_PART("Due Date", ' ', 1), 'MM/DD/YYYY')
                         BETWEEN current_date - interval '7 days'
                             AND current_date + interval '7 days'
                   ORDER BY "Due Date" ASC
                   LIMIT 20"""
            )
            for r in rows:
                due_raw = r.get("Due Date", "")
                try:
                    from datetime import datetime as _dt
                    dt_str = _dt.strptime(due_raw.split(' ')[0], "%m/%d/%Y").strftime("%Y-%m-%d")
                except Exception:
                    dt_str = None
                items.append({
                    "s": "solicitations",
                    "title": f"{r.get('Procurement Method', 'RFP')}: {(r.get('Procurement Name') or 'Untitled')[:100]}",
                    "agency": _agency_abbr(r.get("Agency")),
                    "date": dt_str,
                    "time": due_raw.split(' ', 1)[1] if ' ' in due_raw else None,
                    "context": f"Due: {due_raw} · {r.get('RFx Status', '')}",
                    "amount": None,
                    "url": f"/procurement/solicitation/{r.get('EPIN', '')}" if r.get('EPIN') else "/procurement/solicitations"
                })
        except Exception as e:
            print(f"[briefing] solicitations error: {e}", flush=True)

        # ── 5. Jobs (recently posted) ──
        try:
            rows = await _bq(
                """SELECT "Job ID", "Agency", "Business Title", "Salary Range From",
                          "Salary Range To", "Salary Frequency", "Posting Date", "Job Category"
                   FROM nycjobs
                   WHERE "Posting Date" IS NOT NULL
                     AND "Posting Date"::date >= current_date - interval '7 days'
                   ORDER BY "Posting Date" DESC
                   LIMIT 15"""
            )
            for r in rows:
                dt = r.get("Posting Date")
                try:
                    from datetime import datetime as _dt
                    dt_iso = _dt.strptime(str(dt).split(' ')[0], "%m/%d/%Y").strftime("%Y-%m-%d") if dt else None
                except Exception:
                    dt_iso = dt.strftime("%Y-%m-%d") if hasattr(dt, 'strftime') else str(dt)[:10] if dt else None
                sal_lo = r.get("Salary Range From")
                sal_hi = r.get("Salary Range To")
                sal_str = None
                try:
                    if sal_lo and sal_hi:
                        sal_str = f"${int(float(sal_lo)):,}-${int(float(sal_hi)):,}"
                    elif sal_lo:
                        sal_str = f"${int(float(sal_lo)):,}+"
                except (ValueError, TypeError):
                    pass
                items.append({
                    "s": "jobs",
                    "title": (r.get("Business Title") or "Untitled")[:120],
                    "agency": _agency_abbr(r.get("Agency")),
                    "date": dt_iso,
                    "time": None,
                    "context": f"Salary: {sal_str or 'N/A'} · {r.get('Job Category', '')[:30]}",
                    "amount": None,
                    "url": f"https://cityjobs.nyc.gov/jobs?q={r.get('Job ID', '')}"
                })
        except Exception as e:
            print(f"[briefing] jobs error: {e}", flush=True)

        # ── 6. Personnel Changes (CROL) ──
        try:
            rows = await _bq(
                """SELECT "StartDate", "ShortTitle", "RequestID", "wegov-org-name"
                   FROM crol
                   WHERE "SectionName" = 'Changes in Personnel'
                     AND "StartDate" <> ''
                     AND "StartDate" ~ '^[0-9]{1,2}/'
                     AND TO_DATE(SPLIT_PART("StartDate", ' ', 1), 'MM/DD/YYYY')
                         >= current_date - interval '7 days'
                   ORDER BY TO_DATE(SPLIT_PART("StartDate", ' ', 1), 'MM/DD/YYYY') DESC
                   LIMIT 10"""
            )
            for r in rows:
                sd = r.get("StartDate", "")
                try:
                    from datetime import datetime as _dt
                    iso = _dt.strptime(sd.split(" ")[0], "%m/%d/%Y").strftime("%Y-%m-%d") if sd else None
                except Exception:
                    iso = None
                items.append({
                    "s": "personnel",
                    "title": (r.get("ShortTitle") or "Untitled")[:120],
                    "agency": _agency_abbr(r.get("wegov-org-name")),
                    "date": iso,
                    "time": None,
                    "context": f"City Record #{r.get('RequestID', '')}",
                    "amount": None,
                    "url": f"https://a856-cityrecord.nyc.gov/RequestDetail/{r.get('RequestID', '')}"
                })
        except Exception as e:
            print(f"[briefing] personnel error: {e}", flush=True)

        # ── 7. New Vendors (first-time contract appearance) ──
        try:
            rows = await _bq(
                """SELECT v.vendor_name, v.agency, v.contract_title,
                          v.award_amount, v.start_date, v.ctr_id, v.contract_id,
                          vp."PASSPort Supplier-ID" as passport_id
                   FROM contracts v
                   LEFT JOIN vendors vp ON UPPER(vp."Vendor Name") = UPPER(v.vendor_name)
                   WHERE v.start_date ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
                     AND TO_DATE(v.start_date, 'MM/DD/YYYY')
                         BETWEEN current_date - interval '7 days'
                             AND current_date + interval '7 days'
                     AND NOT EXISTS (
                         SELECT 1 FROM contracts older
                         WHERE older.vendor_name = v.vendor_name
                           AND older.start_date ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
                           AND TO_DATE(older.start_date, 'MM/DD/YYYY')
                               < current_date - interval '7 days'
                     )
                   ORDER BY v.award_amount DESC NULLS LAST
                   LIMIT 10"""
            )
            for r in rows:
                sd = r.get("start_date", "")
                try:
                    from datetime import datetime as _dt
                    dt_str = _dt.strptime(sd, "%m/%d/%Y").strftime("%Y-%m-%d")
                except Exception:
                    dt_str = None
                amt = r.get("award_amount")
                ctr_id = r.get("ctr_id") or r.get("contract_id")
                passport_id = r.get("passport_id")
                if passport_id:
                    url = f"/procurement/vendor/{passport_id}"
                elif ctr_id:
                    url = f"/procurement/contract/{ctr_id}"
                else:
                    url = "/procurement/vendors"
                items.append({
                    "s": "vendors",
                    "title": f"New vendor: {(r.get('vendor_name') or 'Unknown')[:80]}",
                    "agency": _agency_abbr(r.get("agency")),
                    "date": dt_str,
                    "time": None,
                    "context": (r.get("contract_title") or "")[:60],
                    "amount": _format_amount(amt) if amt else None,
                    "url": url
                })
        except Exception as e:
            print(f"[briefing] vendors error: {e}", flush=True)

        # ── 8. Capital Project Milestones ──
        try:
            rows = await _bq(
                """SELECT "PROJECT_ID", "TASK_DESCRIPTION", "TASK_END_DATE",
                          "ORIG_END_DATE"
                   FROM capitalprojectsmilestones
                   WHERE "TASK_END_DATE" IS NOT NULL
                     AND "TASK_END_DATE" != ''
                     AND "TASK_END_DATE" ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
                     AND TO_DATE(SPLIT_PART("TASK_END_DATE", ' ', 1), 'MM/DD/YYYY')
                         BETWEEN current_date - interval '7 days'
                             AND current_date + interval '7 days'
                   ORDER BY "TASK_END_DATE"
                   LIMIT 15"""
            )
            for r in rows:
                ted = (r.get("TASK_END_DATE") or "").replace(" 12:00:00 AM", "")
                try:
                    from datetime import datetime as _dt
                    dt_str = _dt.strptime(ted, "%m/%d/%Y").strftime("%Y-%m-%d") if ted else None
                except Exception:
                    dt_str = None
                prj_id = r.get("PROJECT_ID", "")
                items.append({
                    "s": "capital",
                    "title": (r.get("TASK_DESCRIPTION") or "Milestone")[:120],
                    "agency": "",
                    "date": dt_str,
                    "time": None,
                    "context": f"Project {prj_id}",
                    "amount": None,
                    "url": f"/projects/capital?prj={prj_id}" if prj_id else "/projects/capital"
                })
        except Exception as e:
            print(f"[briefing] capital milestones error: {e}", flush=True)

        # ── 9. Council Hearings (jehiah/nyc_legislation events) ──
        try:
            import aiohttp
            from datetime import timedelta

            now_dt = datetime.utcnow()
            current_year = now_dt.year
            window_start = now_dt - timedelta(days=7)
            window_end = now_dt + timedelta(days=7)

            events_url = f"https://api.github.com/repos/jehiah/nyc_legislation/contents/events/{current_year}"
            headers = {"User-Agent": "DatabookNYC-Briefing/1.0"}

            async with aiohttp.ClientSession() as session:
                async with session.get(events_url, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        entries = await resp.json()
                    else:
                        entries = []

            for entry in entries:
                fname = entry.get("name", "")
                if not fname.endswith(".json"):
                    continue
                parts = fname.replace(".json", "").split("_")
                if len(parts) < 4:
                    continue
                try:
                    ev_date = datetime.strptime(parts[0], "%Y-%m-%d")
                except ValueError:
                    continue
                if not (window_start <= ev_date <= window_end):
                    continue

                ev_time = f"{parts[1]}:{parts[2]}" if len(parts) > 2 else ""
                ev_id = parts[-1] if parts[-1].isdigit() else ""
                committee_slug = "-".join(parts[3:-1]) if len(parts) > 4 else parts[3] if len(parts) > 3 else ""
                committee_name = committee_slug.replace("-", " ").title()

                # Fetch event JSON for agenda count and committee name
                try:
                    raw_url = f"https://raw.githubusercontent.com/jehiah/nyc_legislation/master/events/{current_year}/{fname}"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(raw_url, headers=headers,
                                               timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                ev_data = await resp.json(content_type=None)
                                committee_name = ev_data.get("BodyName", committee_name)
                                agenda_count = sum(1 for it in ev_data.get("Items", [])
                                                   if it.get("MatterFile") and it.get("AgendaSequence", 0) > 0)
                            else:
                                agenda_count = 0
                except Exception:
                    agenda_count = 0

                iso_date = ev_date.strftime("%Y-%m-%d")
                context = f"Council Hearing · {agenda_count} agenda item(s)" if agenda_count else "Council Hearing"
                legistar_url = f"https://legistar.council.nyc.gov/MeetingDetail.aspx?LEGID={ev_id}&GID=61" if ev_id else ""

                items.append({
                    "s": "council",
                    "title": f"Committee on {committee_name}" if not committee_name.startswith("Committee") else committee_name,
                    "agency": "City Council",
                    "date": iso_date,
                    "time": ev_time,
                    "context": context,
                    "amount": None,
                    "url": legistar_url
                })
        except Exception as e:
            print(f"[briefing] council hearings error: {e}", flush=True)

        # Filter out items with no date
        items = [i for i in items if i["date"]]

        # Write to cache
        _briefing_cache["data"] = items
        _briefing_cache["computed_at"] = datetime.utcnow().isoformat() + "Z"
        print(f"[briefing] Cache rebuilt: {len(items)} items", flush=True)
        return items
    finally:
        await conn.close()


@router.get("/briefing", summary="Get City Briefing feed items")
async def get_briefing():
    """Return cached briefing feed items.

    Data is rebuilt every 6 hours in the background.
    If cache is empty, triggers an on-demand build.
    """
    if not _briefing_cache["data"]:
        # First request before cache is warm — build on demand
        await _build_briefing()
    return _briefing_cache["data"]


@router.get("/briefing/meta", summary="Get briefing cache metadata")
async def get_briefing_meta():
    """Return cache metadata (item count, last computed time)."""
    return {
        "items": len(_briefing_cache["data"]),
        "computed_at": _briefing_cache["computed_at"]
    }


@router.post("/briefing/refresh", summary="Force-refresh briefing cache")
async def refresh_briefing():
    """Manually trigger a briefing cache rebuild."""
    import asyncio
    asyncio.create_task(_build_briefing())
    return {"result": "OK", "message": "Briefing cache rebuild started"}


@router.get("/hearings", summary="Get NYC Council hearing calendar")
async def get_hearings(days_ahead: int = 30, days_behind: int = 14):
    """Fetch upcoming and recent NYC Council hearings from jehiah/nyc_legislation.

    Returns structured JSON for the hearing calendar frontend page.
    """
    import aiohttp
    from datetime import timedelta

    now = datetime.utcnow()
    window_start = now - timedelta(days=days_behind)
    window_end = now + timedelta(days=days_ahead)
    current_year = now.year

    years_to_check = [current_year]
    if window_start.year < current_year:
        years_to_check.insert(0, window_start.year)
    if window_end.year > current_year:
        years_to_check.append(window_end.year)

    headers = {"User-Agent": "DatabookNYC-Hearings/1.0"}
    events = []

    for year in years_to_check:
        url = f"https://api.github.com/repos/jehiah/nyc_legislation/contents/events/{year}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    entries = await resp.json() if resp.status == 200 else []
        except Exception:
            entries = []

        for entry in entries:
            fname = entry.get("name", "")
            if not fname.endswith(".json"):
                continue
            parts = fname.replace(".json", "").split("_")
            if len(parts) < 4:
                continue
            try:
                ev_date = datetime.strptime(parts[0], "%Y-%m-%d")
            except ValueError:
                continue
            if not (window_start <= ev_date <= window_end):
                continue

            ev_time = f"{parts[1]}:{parts[2]}" if len(parts) > 2 else ""
            ev_id = parts[-1] if parts[-1].isdigit() else ""
            committee_slug = "-".join(parts[3:-1]) if len(parts) > 4 else parts[3] if len(parts) > 3 else ""
            committee_name = committee_slug.replace("-", " ").title()

            # Fetch event JSON for full details
            try:
                raw_url = f"https://raw.githubusercontent.com/jehiah/nyc_legislation/master/events/{year}/{fname}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(raw_url, headers=headers,
                                           timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            ev_data = await resp.json(content_type=None)
                            committee_name = ev_data.get("BodyName", committee_name)
                            location = ev_data.get("Location", "")
                            agenda_status = ev_data.get("AgendaStatusName", "")
                            agenda_file = ev_data.get("AgendaFile", "")
                            video_path = ev_data.get("VideoPath", "")
                            legistar_url = ev_data.get("InSiteURL", "")
                            items = []
                            for it in ev_data.get("Items", []):
                                if it.get("MatterFile") and it.get("AgendaSequence", 0) > 0:
                                    intro_link = ""
                                    mf = it.get("MatterFile", "")
                                    if mf.startswith("Int "):
                                        intro_link = f"https://intro.nyc/{mf.replace('Int ', '')}"
                                    items.append({
                                        "matter_file": mf,
                                        "matter_name": (it.get("MatterName") or it.get("Title") or "")[:120],
                                        "matter_type": it.get("MatterType", ""),
                                        "intro_link": intro_link,
                                    })
                        else:
                            location = ""
                            agenda_status = ""
                            agenda_file = ""
                            video_path = ""
                            legistar_url = ""
                            items = []
            except Exception:
                location = ""
                agenda_status = ""
                agenda_file = ""
                video_path = ""
                legistar_url = ""
                items = []

            if not legistar_url and ev_id:
                legistar_url = f"https://legistar.council.nyc.gov/MeetingDetail.aspx?LEGID={ev_id}&GID=61"

            events.append({
                "date": ev_date.strftime("%Y-%m-%d"),
                "time": ev_time,
                "committee": committee_name,
                "location": location,
                "event_id": ev_id,
                "agenda_status": agenda_status,
                "agenda_items": items,
                "agenda_count": len(items),
                "legistar_url": legistar_url,
                "agenda_file": agenda_file,
                "video_path": video_path,
                "is_past": ev_date < now,
            })

    events.sort(key=lambda x: x["date"])

    return {
        "events": events,
        "window": {
            "start": window_start.strftime("%Y-%m-%d"),
            "end": window_end.strftime("%Y-%m-%d"),
        },
        "total": len(events),
    }


# Theme-to-agency mapping for cross-referencing hearing topics with Databook
_HEARING_THEME_MAP = {
    "transportation": {"agencies": ["%transportation%", "%DOT%"], "label": "Transportation & Infrastructure"},
    "street": {"agencies": ["%transportation%", "%DOT%"], "label": "Street Safety & Infrastructure"},
    "traffic": {"agencies": ["%transportation%", "%DOT%"], "label": "Traffic & Street Safety"},
    "sanitation": {"agencies": ["%sanitation%"], "label": "Sanitation & Waste Management"},
    "waste": {"agencies": ["%sanitation%"], "label": "Sanitation & Waste Management"},
    "housing": {"agencies": ["%housing%", "%HPD%", "%NYCHA%"], "label": "Housing & Development"},
    "homeless": {"agencies": ["%homeless%", "%DHS%"], "label": "Homelessness Services"},
    "education": {"agencies": ["%education%", "%DOE%"], "label": "Education"},
    "school": {"agencies": ["%education%", "%DOE%", "%school construction%"], "label": "Schools & Education"},
    "police": {"agencies": ["%police%", "%NYPD%"], "label": "Public Safety & Policing"},
    "fire": {"agencies": ["%fire%", "%FDNY%"], "label": "Fire & Emergency Services"},
    "health": {"agencies": ["%health%", "%DOHMH%"], "label": "Public Health"},
    "parks": {"agencies": ["%parks%", "%DPR%"], "label": "Parks & Recreation"},
    "environment": {"agencies": ["%environment%", "%DEP%"], "label": "Environmental Protection"},
    "water": {"agencies": ["%environment%", "%DEP%"], "label": "Water & Environmental"},
    "buildings": {"agencies": ["%buildings%", "%DOB%"], "label": "Buildings & Construction"},
    "construction": {"agencies": ["%buildings%", "%DOB%", "%design and construction%", "%DDC%"], "label": "Construction & Infrastructure"},
    "budget": {"agencies": ["%budget%", "%OMB%"], "label": "Budget & Finance"},
    "technology": {"agencies": ["%technology%", "%OTI%", "%DoITT%"], "label": "Technology & Innovation"},
    "consumer": {"agencies": ["%consumer%", "%DCWP%"], "label": "Consumer Protection"},
    "correction": {"agencies": ["%correction%", "%DOC%"], "label": "Criminal Justice & Corrections"},
    "youth": {"agencies": ["%youth%", "%DYCD%"], "label": "Youth & Community Development"},
    "child": {"agencies": ["%child%", "%ACS%"], "label": "Children & Family Services"},
    "planning": {"agencies": ["%planning%", "%DCP%"], "label": "City Planning & Land Use"},
    "zoning": {"agencies": ["%planning%", "%DCP%"], "label": "Zoning & Land Use"},
}


@router.get("/hearing-briefing/{event_id}", summary="Generate data briefing for a hearing")
async def get_hearing_briefing_api(event_id: str, year: int = 2026):
    """Cross-reference a hearing's agenda with Databook data (contracts, budget,
    capital projects, CROL notices, jobs) and return a structured briefing."""
    import aiohttp

    headers = {"User-Agent": "DatabookNYC-Briefing/1.0"}

    # 1. Find the event file
    dir_url = f"https://api.github.com/repos/jehiah/nyc_legislation/contents/events/{year}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(dir_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                entries = await resp.json() if resp.status == 200 else []
    except Exception:
        return JSONResponse({"error": "Could not reach GitHub API"}, status_code=502)

    target_file = None
    for e in entries:
        if e.get("name", "").endswith(f"_{event_id}.json"):
            target_file = e["name"]
            break
    if not target_file:
        return JSONResponse({"error": f"Event {event_id} not found in {year}"}, status_code=404)

    # 2. Fetch event data
    raw_url = f"https://raw.githubusercontent.com/jehiah/nyc_legislation/master/events/{year}/{target_file}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(raw_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                event = await resp.json(content_type=None) if resp.status == 200 else None
    except Exception:
        event = None
    if not event:
        return JSONResponse({"error": "Could not fetch event data"}, status_code=502)

    committee = event.get("BodyName", "Unknown Committee")
    event_date = (event.get("Date") or "")[:10]

    # 3. Collect bills and extract themes
    bills = []
    bill_titles = []
    for item in event.get("Items", []):
        matter_name = item.get("MatterName") or item.get("Title") or ""
        matter_file = item.get("MatterFile", "")
        if matter_name and not item.get("RollCallFlag"):
            bill_titles.append(matter_name)
            intro_link = ""
            if matter_file.startswith("Int "):
                intro_link = f"https://intro.nyc/{matter_file.replace('Int ', '')}"
            bills.append({
                "matter_file": matter_file,
                "matter_name": matter_name[:120],
                "intro_link": intro_link,
            })

    # Extract themes
    found_themes = {}
    for text in bill_titles + [committee]:
        lower = text.lower()
        for keyword, theme in _HEARING_THEME_MAP.items():
            if keyword in lower and theme["label"] not in found_themes:
                found_themes[theme["label"]] = theme
    themes = list(found_themes.values())

    # 4. Query Databook for each theme
    theme_data = []
    for theme_info in themes[:5]:
        label = theme_info["label"]
        agency_patterns = theme_info["agencies"]
        theme_result = {"label": label, "contracts": [], "budget": [], "capital_projects": [], "crol": [], "open_jobs": 0}

        # Contracts
        try:
            conditions = " OR ".join(f"agency ILIKE ${i+1}" for i in range(len(agency_patterns)))
            params = tuple(agency_patterns) + (5,)
            result = await _select(f"""
                SELECT contract_title, vendor_name, agency, award_amount, ctr_id
                FROM contracts
                WHERE ({conditions})
                ORDER BY award_amount DESC NULLS LAST
                LIMIT ${len(agency_patterns)+1}
            """, params)
            rows = result.get("rows", []) if isinstance(result, dict) else result
            for r in rows:
                theme_result["contracts"].append({
                    "title": (r.get("contract_title") or "Untitled")[:60],
                    "vendor": (r.get("vendor_name") or "N/A")[:40],
                    "amount": float(r["award_amount"]) if r.get("award_amount") else None,
                    "ctr_id": r.get("ctr_id", ""),
                })
        except Exception as e:
            print(f"[hearing-brief] contracts error: {e}", flush=True)

        # Budget
        try:
            conditions = " OR ".join(f""""Agency Name" ILIKE ${i+1}""" for i in range(len(agency_patterns)))
            result = await _select(f"""
                SELECT "Agency Name",
                       SUM(CAST(NULLIF("Current Modified Budget Amount", '') AS NUMERIC)) as total_budget,
                       "Fiscal Year"
                FROM expensebudgetonnycopendata
                WHERE ({conditions})
                  AND "Fiscal Year" = (SELECT MAX("Fiscal Year") FROM expensebudgetonnycopendata)
                GROUP BY "Agency Name", "Fiscal Year"
                ORDER BY total_budget DESC LIMIT 3
            """, tuple(agency_patterns))
            rows = result.get("rows", []) if isinstance(result, dict) else result
            for r in rows:
                theme_result["budget"].append({
                    "agency": r.get("Agency Name", ""),
                    "total": float(r["total_budget"]) if r.get("total_budget") else 0,
                    "fy": r.get("Fiscal Year"),
                })
        except Exception as e:
            print(f"[hearing-brief] budget error: {e}", flush=True)

        # Capital projects
        try:
            conditions = " OR ".join(f"man_agency_name ILIKE ${i+1}" for i in range(len(agency_patterns)))
            params = tuple(agency_patterns) + (3,)
            result = await _select(f"""
                SELECT project_id, short_description, total_plan_commtmts as budget, man_agency_name
                FROM capitalprojectslist
                WHERE ({conditions})
                ORDER BY total_plan_commtmts DESC NULLS LAST
                LIMIT ${len(agency_patterns)+1}
            """, params)
            rows = result.get("rows", []) if isinstance(result, dict) else result
            for r in rows:
                theme_result["capital_projects"].append({
                    "project_id": r.get("project_id", ""),
                    "description": (r.get("short_description") or "N/A")[:60],
                    "budget": float(r["budget"]) if r.get("budget") else None,
                })
        except Exception as e:
            print(f"[hearing-brief] capital error: {e}", flush=True)

        # CROL notices
        try:
            conditions = " OR ".join(f""""wegov-org-name" ILIKE ${i+1}""" for i in range(len(agency_patterns)))
            params = tuple(agency_patterns) + (3,)
            result = await _select(f"""
                SELECT "ShortTitle", "SectionName", "RequestID"
                FROM crol
                WHERE ({conditions})
                  AND "StartDate" <> ''
                  AND "StartDate" ~ '^[0-9]{{1,2}}/'
                  AND TO_DATE(SPLIT_PART("StartDate", ' ', 1), 'MM/DD/YYYY') >= current_date - interval '90 days'
                ORDER BY TO_DATE(SPLIT_PART("StartDate", ' ', 1), 'MM/DD/YYYY') DESC
                LIMIT ${len(agency_patterns)+1}
            """, params)
            rows = result.get("rows", []) if isinstance(result, dict) else result
            for r in rows:
                theme_result["crol"].append({
                    "title": (r.get("ShortTitle") or "N/A")[:60],
                    "section": r.get("SectionName", ""),
                    "request_id": r.get("RequestID", ""),
                })
        except Exception as e:
            print(f"[hearing-brief] crol error: {e}", flush=True)

        # Jobs count
        try:
            conditions = " OR ".join(f""""Agency" ILIKE ${i+1}""" for i in range(len(agency_patterns)))
            result = await _select(f"""
                SELECT COUNT(*) as cnt FROM nycjobs WHERE ({conditions})
            """, tuple(agency_patterns))
            rows = result.get("rows", []) if isinstance(result, dict) else result
            if rows:
                theme_result["open_jobs"] = rows[0].get("cnt", 0)
        except Exception as e:
            print(f"[hearing-brief] jobs error: {e}", flush=True)

        theme_data.append(theme_result)

    return {
        "committee": committee,
        "date": event_date,
        "event_id": event_id,
        "bills": bills,
        "themes": theme_data,
        "theme_count": len(theme_data),
    }


def _agency_abbr(name: str) -> str:
    """Extract a short agency abbreviation from a full name."""
    if not name:
        return "NYC"
    # Common abbreviations
    abbrs = {
        "department of transportation": "DOT",
        "department of sanitation": "DSNY",
        "department of buildings": "DOB",
        "department of education": "DOE",
        "department of environmental protection": "DEP",
        "department of city planning": "DCP",
        "department of parks and recreation": "DPR",
        "department of health": "DOHMH",
        "fire department": "FDNY",
        "police department": "NYPD",
        "department of correction": "DOC",
        "department of homeless services": "DHS",
        "department of information technology": "DoITT",
        "department of consumer": "DCWP",
        "department of housing preservation": "HPD",
        "department of design and construction": "DDC",
        "department of youth": "DYCD",
        "department of citywide administrative": "DCAS",
        "economic development": "EDC",
        "school construction authority": "SCA",
        "nyc housing authority": "NYCHA",
        "mayor": "Mayor's Office",
        "office of technology": "OTI",
    }
    lower = name.lower()
    for key, abbr in abbrs.items():
        if key in lower:
            return abbr
    # Fallback: first 8 chars
    return name[:8]


def _format_amount(val) -> str:
    """Format a numeric value as a short dollar string."""
    if val is None:
        return None
    try:
        v = float(val)
    except (ValueError, TypeError):
        return str(val)
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:,.0f}"


# =============================================================================
# Manual Triggers
# =============================================================================

@router.post("/check", summary="Trigger a full data check")
async def trigger_data_check():
    """
    Manually trigger a data check cycle.

    Polls all active datasets for changes and ingests any that have been
    updated at their source. Runs asynchronously — returns immediately.
    """
    import asyncio
    from data_scheduler import run_data_check

    asyncio.create_task(run_data_check())
    return {
        "result": "OK",
        "message": "Data check started in background. "
                   "Monitor via /pipeline/health"
    }


@router.post("/rebuild-stats", summary="Rebuild homepage statistics")
async def trigger_rebuild_stats():
    """Manually recompute cached homepage statistics.

    Why: Stats are normally rebuilt at the end of each scheduler cycle,
    but if the cycle fails mid-way (e.g. normalizer timeout), stats
    go stale. This endpoint allows manual refresh.
    Runs asynchronously to avoid HTTP timeout / OOM on large queries.
    """
    import asyncio
    from data_scheduler import get_db_connection, rebuild_glob_stats

    async def _rebuild():
        conn = await get_db_connection()
        try:
            await rebuild_glob_stats(conn)
        except Exception as e:
            print(f"[stats] Background rebuild failed: {e}", flush=True)
        finally:
            await conn.close()

    asyncio.create_task(_rebuild())
    return {"result": "OK", "message": "Stats rebuild started in background"}

@router.post("/check/{table_name}", summary="Check a single dataset")
async def trigger_single_check(
    table_name: str,
    skip_normalizer: bool = False
):
    """
    Manually trigger a check and potential refresh for a single dataset.

    Args:
        skip_normalizer: If true, bypass the normalizer and import raw CSV
                         from Socrata directly. Useful for restoring datasets
                         wiped by failed normalizer runs.

    Runs asynchronously — returns immediately while processing continues
    in the background. Monitor results via /pipeline/registry.
    """
    from data_scheduler import get_db_connection
    import asyncio

    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM dataset_registry WHERE table_name = $1",
            table_name
        )
        if not row:
            await conn.close()
            return JSONResponse(status_code=404,
                                content={"error": f"'{table_name}' not in registry"})

        async def _process_single(table: str, raw_import: bool):
            """Background task: process a single dataset."""
            from data_scheduler import (
                get_db_connection as get_conn,
                process_socrata_dataset,
                process_extractor_dataset,
                process_normalized_dataset,
                full_replace_import,
                update_registry,
            )
            import aiohttp
            from datetime import datetime, timezone

            bg_conn = await get_conn()
            try:
                r = await bg_conn.fetchrow(
                    "SELECT * FROM dataset_registry WHERE table_name = $1",
                    table
                )
                if not r:
                    return
                ds = dict(r)
                async with aiohttp.ClientSession() as session:
                    if raw_import and ds.get('socrata_id'):
                        # Bypass normalizer: import raw CSV from Socrata
                        print(f"[single-check] {table}: raw import "
                              f"(skip_normalizer=true)")
                        result = await full_replace_import(
                            bg_conn, ds, session)
                        now = datetime.now(timezone.utc)
                        if result['status'] == 'success':
                            await update_registry(
                                bg_conn, ds['id'],
                                last_ingested_at=now,
                                estimated_rows=result.get('rows'),
                                last_error=None)
                            print(f"[single-check] {table}: raw import "
                                  f"success — {result.get('rows'):,} rows")
                        else:
                            await update_registry(
                                bg_conn, ds['id'],
                                last_error=result.get('error'))
                            print(f"[single-check] {table}: raw import "
                                  f"failed — {result.get('error')}")
                    elif (ds.get('normalizer_dataset_id')
                          and ds.get('needs_normalization', True)):
                        nid = ds['normalizer_dataset_id']
                        import os
                        base = os.environ.get(
                            "NORMALIZER_BASE_URL",
                            "https://normalize.databook.nyc")
                        async with session.post(
                            f"{base}/process/{nid}/async",
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            body = await resp.json()
                            print(f"[single-check] {table}: "
                                  f"queued → {body.get('status')}")
                    elif ds['source_type'] == 'socrata':
                        await process_socrata_dataset(
                            bg_conn, ds, session)
                    elif ds['source_type'] == 'extractor':
                        # force=True: a manual single-check should re-ingest now,
                        # bypassing the once-daily guard.
                        await process_extractor_dataset(
                            bg_conn, ds, session, force=True)
            except Exception as e:
                print(f"[single-check] Error processing {table}: {e}")
            finally:
                await bg_conn.close()

        asyncio.create_task(_process_single(table_name, skip_normalizer))
        return {
            "result": "OK",
            "message": f"Processing '{table_name}' in background. "
                       "Monitor via /pipeline/registry"
        }
    finally:
        await conn.close()

