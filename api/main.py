import json
import logging
import os
from modules import autoload
import uvicorn
from fastapi import Depends, FastAPI, Security, Query, Request, Path, HTTPException
import asyncpg
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Set
from fastapi_login import LoginManager
from fastapi_login.exceptions import InvalidCredentialsException
from fastapi.security import OAuth2PasswordRequestForm
import datetime
from config import Config
from user import User
from postgrex import CsvDataset
#from reqs import select
#from pydantic import BaseModel
from postgrex import PostgresModelAsync
from modules import duckpool
from subprocess import Popen
from routers.oce import router as oce_router
from routers.budget_revenue import router as budget_revenue_router
from routers.payroll import router as payroll_router
from routers.nycha import router as nycha_router
from routers.data_pipeline import router as pipeline_router
from routers.public_v1 import router as public_v1_router
from routers.search import router as search_router

# Error tracking: enabled only when SENTRY_DSN is set in the environment,
# so local dev and tests run without a Sentry account configured.
if os.getenv('SENTRY_DSN'):
    import sentry_sdk

    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        environment=os.getenv('SENTRY_ENVIRONMENT', 'production'),
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
    )

app = FastAPI(
    title = 'WeGovNYC Databook API',
    description = 'Access all normalized Databook data using our API documented below.',
    version="0.0.1",
    contact={
        'name': 'WeGovNYC Databook',
        'url': 'https://databook.wegov.nyc/',
        'email': 'dp@databook.wegov.nyc',
    },
)
'''license_info={
    'name': 'Apache 2.0',
    'url': 'https://www.apache.org/licenses/LICENSE-2.0.html',
},'''

origins = [
    'http://localhost:8000',
    'http://localhost:5539',
    'http://localhost:8580',       # Local dev (docker-compose.local.yml)
    'http://localhost:8080',       # Alternative local dev
    'http://18.191.137.137:5539',
    'http://devinbalkind',
    'http://52.14.103.188',
    'http://databook.wegov.nyc',
    'https://databook.wegov.nyc',
    'http://databook.nyc',
    'https://databook.nyc',
    'http://www.databook.nyc',
    'https://www.databook.nyc',
    'http://staging.databook.nyc',
    'https://staging.databook.nyc',
]

# Allow additional origins via environment variable (comma-separated).
# This avoids hardcoding staging/preview domains in source code.
_extra_origins = os.getenv('CORS_EXTRA_ORIGINS', '')
if _extra_origins:
    origins.extend([o.strip() for o in _extra_origins.split(',') if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

manager = LoginManager(Config.fastapi['key'], '/login')
user = User()
select = PostgresModelAsync.select

import re
_VALID_TABLE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def _safe_table(tbl: str) -> str:
    """Reject anything that isn't a plain SQL identifier, so a table name from
    a URL path can't be used for SQL injection when interpolated into a query.
    """
    if not _VALID_TABLE.match(tbl):
        raise HTTPException(status_code=404, detail="Unknown table")
    return tbl

# Register routers
app.include_router(public_v1_router)
app.include_router(search_router)
app.include_router(oce_router)
app.include_router(budget_revenue_router)
app.include_router(payroll_router)
app.include_router(nycha_router)
app.include_router(pipeline_router)


@app.on_event("startup")
async def start_data_scheduler():
    """Launch the background data scheduler if enabled via environment variable."""
    import asyncio
    if os.environ.get('DATA_SCHEDULER_ENABLED', '').strip() == '1':
        from data_scheduler import scheduler_loop
        asyncio.create_task(scheduler_loop())
        print("[startup] Data scheduler enabled — background task started.")
    else:
        print("[startup] Data scheduler disabled. Set DATA_SCHEDULER_ENABLED=1 to enable.")

@manager.user_loader()
async def query_user(user_id: str):
    """Load user from database using async connection to avoid sync connection corruption."""
    try:
        user_id_int = int(user_id)  # Cast string to int for asyncpg (id column is integer)
    except (ValueError, TypeError):
        return None
    result = await PostgresModelAsync.select(
        "SELECT id, email, pwdhash, scope FROM users WHERE id=$1", (user_id_int,)
    )
    if result.get('rows'):
        return result['rows'][0]
    return None

@app.on_event("startup")
async def startup():
    # Fully opens the pool (min_size == max_size) BEFORE traffic, so the request
    # path never calls getaddrinfo; see modules/postgrex/asyncmodel.py.
    await PostgresModelAsync.connect()
    print(f"[startup] Postgres pool warm: {PostgresModelAsync.pool_status()}", flush=True)
    # DuckDB gets its OWN executor so Parquet scans can never starve DNS
    # resolution for new Postgres connections; see modules/duckpool.py.
    print(f"[startup] DuckDB executor: {duckpool.pool_status()}", flush=True)
    await ensure_people_indexes()
    
    # Pre-warm heavy caches in the background so first user hits are instant.
    # IMPORTANT: run them SEQUENTIALLY in a single task, not as concurrent
    # create_task() fan-out. Each warm scans large Parquet/Postgres data; run
    # concurrently their peak allocations stacked and blew the container memory
    # limit -> OOM mid-warm -> restart -> re-warm, a perpetual crash-loop. Serial
    # keeps peak memory to one task at a time while staying off the startup
    # critical path (uvicorn is already accepting requests).
    import asyncio
    from routers.oce import refresh_dashboard_cache, refresh_digital_reform_cache, prewarm_transactions_metadata
    from routers.data_pipeline import _build_briefing

    async def _sequential_prewarm():
        warms = [
            ("dashboard", refresh_dashboard_cache),
            ("digital-reform", refresh_digital_reform_cache),
            ("transactions", prewarm_transactions_metadata),
            ("briefing", _build_briefing),
            ("projects-map", _load_projects_map_cache),
        ]
        for label, fn in warms:
            try:
                await fn()
                print(f"[startup] pre-warm done: {label}", flush=True)
            except Exception as e:
                print(f"[startup] pre-warm failed ({label}): {e}", flush=True)
        print("[startup] Sequential cache pre-warm complete.", flush=True)
    asyncio.create_task(_sequential_prewarm())
    print("[startup] Sequential cache pre-warm started (dashboard -> digital-reform -> transactions -> briefing -> projects-map).")

    # Briefing rebuilds every 6h thereafter (the initial build runs in the
    # sequential pre-warm above; this loop sleeps FIRST so it never collides
    # with startup warm).
    async def _briefing_rebuild_loop():
        while True:
            await asyncio.sleep(6 * 3600)  # 6 hours
            try:
                await _build_briefing()
            except Exception as e:
                print(f"[briefing] Cache rebuild failed: {e}", flush=True)
    asyncio.create_task(_briefing_rebuild_loop())
    print("[startup] Briefing 6h rebuild loop started.")


async def ensure_people_indexes():
    """Create pg_trgm extension, trigram indexes, and B-tree indexes for performance.

    Trigram indexes enable fast ILIKE people search (~1-2s instead of minutes).
    B-tree indexes on wegov-org-id enable fast org section filtering on large tables.
    All statements are idempotent (IF NOT EXISTS).
    """
    execute = PostgresModelAsync.execute
    try:
        await execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        # Trigram indexes for people search
        await execute('CREATE INDEX IF NOT EXISTS idx_civillist_name_trgm ON civillist USING gin ("EMPLOYEE NAME" gin_trgm_ops)')
        await execute("""CREATE INDEX IF NOT EXISTS idx_payrolldata_name_trgm ON payrolldata USING gin (("First Name" || ' ' || "Last Name") gin_trgm_ops)""")
        await execute("""CREATE INDEX IF NOT EXISTS idx_cla_name_trgm ON civillistactive USING gin (("First Name" || ' ' || "Last Name") gin_trgm_ops)""")
        # B-tree indexes for org section filtering (critical for payrolldata 6.8M, civillist 3.2M)
        await execute('CREATE INDEX IF NOT EXISTS idx_payrolldata_orgid ON payrolldata ("wegov-org-id")')
        await execute('CREATE INDEX IF NOT EXISTS idx_civillist_orgid ON civillist ("wegov-org-id")')
        await execute('CREATE INDEX IF NOT EXISTS idx_civillist_titlecode ON civillist ("TITLE CODE")')
        await execute('CREATE INDEX IF NOT EXISTS idx_civillistactive_orgid ON civillistactive ("wegov-org-id")')
        print("[startup] People search + org section indexes ensured.")
    except Exception as e:
        # Non-fatal: tables may not exist yet (first boot before data import)
        print(f"[startup] Skipped people indexes: {e}")


@app.on_event("shutdown")
async def shutdown():
    await PostgresModelAsync.disconnect()
    duckpool.shutdown()


@app.get('/health', tags=['Operations'], summary='Health check for deployment verification')
async def health_check():
    """Validate all critical dependencies are reachable."""
    checks = {}
    # Postgres
    try:
        result = await select('SELECT 1 AS ok')
        checks['postgres'] = 'ok' if result.get('rows') else 'no_rows'
    except Exception as e:
        checks['postgres'] = f'fail: {e}'
    # Table count
    try:
        result = await select("SELECT count(*) AS cnt FROM pg_tables WHERE schemaname='public'")
        checks['tables'] = result['rows'][0]['cnt'] if result.get('rows') else 0
    except Exception as e:
        checks['tables'] = f'fail: {e}'
    # CORS origins
    checks['cors_origins'] = len(origins)
    overall = 'ok' if checks.get('postgres') == 'ok' and isinstance(checks.get('tables'), int) and checks['tables'] > 0 else 'degraded'
    return {'status': overall, 'checks': checks}


    
# ================ datasets ================

@app.get('/get/datasets/all', tags=['Datasets'], summary="Get all dataset profiles")
async def get_all_datasets_profiles():
    """Return dataset metadata from dataset_registry.

    Aliases columns to match the legacy data_sources field names
    expected by PHP consumers (stats_data_sources, About page, etc.).
    """
    return await select("""
        SELECT display_name AS "Name",
               citation_url AS "Citation URL",
               source AS "Source",
               section AS "Section",
               description AS "Descripton",
               CASE WHEN is_active THEN 'Active' ELSE 'Develop' END AS "Status",
               to_char(last_ingested_at, 'MM/DD/YYYY HH24:MI') AS "Last Updated",
               to_char(last_checked_at, 'MM/DD/YYYY HH24:MI') AS "Last Modified",
               source_url AS "Data URL",
               table_name || '.csv' AS "Output Path",
               table_name AS "Label",
               category AS "Core Dataset(s)",
               id AS "_uid"
        FROM dataset_registry
        WHERE display_name IS NOT NULL
        ORDER BY display_name
    """)


@app.get('/get/datasets/profile/{name}', tags=['Datasets'], summary="Get dataset profile by name")
async def get_dataset_profile_by_name(name:str):
    """Get dataset profile from dataset_registry.

    Aliases columns to match the legacy data_sources field names
    expected by blade template citations.
    """
    return await select("""
        SELECT display_name AS "Name",
               citation_url AS "Citation URL",
               source AS "Source",
               section AS "Section",
               description AS "Descripton",
               CASE WHEN is_active THEN 'Active' ELSE 'Develop' END AS "Status",
               to_char(last_ingested_at, 'MM/DD/YYYY HH24:MI') AS "Last Updated",
               to_char(last_checked_at, 'MM/DD/YYYY HH24:MI') AS "Last Modified",
               source_url AS "Data URL",
               table_name || '.csv' AS "Output Path",
               table_name AS "Label",
               id AS "_uid"
        FROM dataset_registry
        WHERE display_name LIKE $1
    """, (name,))


# ================ orgs ================

@app.get('/get/orgs/chart', tags=['Organizations'])
async def get_organizations_for_building_chart():
    return await select('SELECT * FROM wegov_orgs WHERE "type" IN (\'City Agency\', \'Elected Office\', \'Boards and Comissions\', \'Classification\', \'Community Board\', \'Official\') ORDER BY name')

@app.get('/get/orgs/directory', tags=['Organizations'])
async def get_organizations_directory():
    return await select('SELECT * FROM wegov_orgs WHERE "type" IN (\'City Agency\', \'City Fund\', \'Community Board\', \'Economic Development Organization\', \'Elected Office\', \'State Agency\') ORDER BY name')

@app.get('/get/orgs/all', tags=['Organizations'])
async def get_organizations_full_list():
    return await select('SELECT * FROM wegov_orgs WHERE "type" NOT IN (\'Classification\', \'Official\', \'Public Figure\') ORDER BY name')

@app.get('/get/orgs/profile/{id}', tags=['Organizations'])
async def get_organization_profile(id: int):
    _base = "SELECT org.*, p.id AS parent_id, p.name AS parent_name, p.type AS parent_type"
    _joins = r""" FROM wegov_orgs org LEFT JOIN wegov_orgs p ON p.airtable_id = regexp_replace(org.child_of, '[\[\]"]', '', 'g')"""
    # Greenbook-derived agency head + fallback address (see api/enrich_agency.py).
    # Guarded so environments that haven't built the enrichment tables yet fall
    # back to the plain profile instead of 500ing every org page.
    try:
        return await select(
            _base
            + ", ahe.head_name AS derived_head_name, ahe.head_title AS derived_head_title"
            + ", ahe.confidence AS derived_head_confidence"
            + ", ace.address AS derived_address, ace.address_rows AS derived_address_rows"
            + _joins
            + " LEFT JOIN agency_head_enrichment ahe ON ahe.org_id = org.id"
            + " LEFT JOIN agency_contact_enrichment ace ON ace.org_id = org.id"
            + " WHERE org.id = $1", (id,))
    except asyncpg.exceptions.UndefinedTableError:
        return await select(_base + _joins + " WHERE org.id = $1", (id,))

@app.get('/get/orgs/section/{id}/{tbl}', tags=['Organizations'])
async def get_subdataset_related_to_organization(id: str, tbl: str):
    # Cap rows: large agencies map to hundreds of thousands of civillist /
    # payrolldata rows (payrolldata is ~6.8M total). SELECT * with no LIMIT
    # materialized the whole set into a Python list of dicts (~660 MB for the
    # worst title equivalent) — concurrent hits OOM-killed the container. Twin of
    # the /get/titles/{id}/{tbl} cap. The client-side DataTable can't render that
    # many rows anyway; org stats/charts use the separate aggregated endpoints.
    _ROW_CAP = 10000
    # civillist's employee-name column is already trimmed to "EMPLOYEE NAME"
    if tbl == 'civillist':
        return await select('SELECT * FROM civillist WHERE "wegov-org-id"=$1 LIMIT {}'.format(_ROW_CAP), (id,))
    # Some tables (e.g. ll18payanddemo, civillistactive) lack the wegov-org-id
    # mapping column — return empty rather than 500 (resilient fallback).
    try:
        return await select("SELECT * FROM {} WHERE \"wegov-org-id\"=$1 LIMIT {}".format(_safe_table(tbl), _ROW_CAP), (id,))
    except (asyncpg.exceptions.UndefinedColumnError, asyncpg.exceptions.UndefinedTableError):
        return []

@app.get('/get/orgs/ccmember/{id}', tags=['Organizations'])
async def get_city_council_member_related_to_organization(id: str):
    return await select("SELECT * FROM ccmembers WHERE \"wegov-org-id\"=$1", (id,))


# ---- stats --------
@app.get('/get/orgs/stats-reg/{id}/{tbl}', tags=['Organizations'])
async def organization_subdataset_number_stats(id: str, tbl: str):
    # Tables without the wegov-org-id column → count 0 rather than 500.
    try:
        return await select("SELECT count(*) FROM {} WHERE \"wegov-org-id\"=$1".format(_safe_table(tbl)), (id,))
    except (asyncpg.exceptions.UndefinedColumnError, asyncpg.exceptions.UndefinedTableError):
        return [{"count": 0}]

@app.get('/get/orgs/stats-notices/{id}/{crolsection}', tags=['Organizations'])
async def organization_notices_number_stats(id: str, crolsection: str):
    return await select("SELECT count(*) FROM crol WHERE \"wegov-org-id\"=$1 AND \"SectionName\"=$2", (id, crolsection))

@app.get('/get/orgs/stats-events/{id}', tags=['Organizations'])
async def organization_events_number_stats(id: str):
    return await select("SELECT count(*) FROM crol WHERE \"wegov-org-id\"=$1 AND NOT \"EventDate\" = ''", (id,))

@app.get('/get/orgs/stats-headcount/{id}/{fyear}', tags=['Organizations'])
async def organization_headcount_number_stats(id: str, fyear: str):
    return await select("SELECT sum(\"HEADCOUNT\"::numeric) FROM headcountactualsfunding WHERE \"wegov-org-id\"=$1 AND \"FISCAL YEAR\"=$2", (id, fyear))

@app.get('/get/orgs/stats-as/{id}/{fyear}', tags=['Organizations'])
async def organization_actual_spending_stats(id: str, fyear: str):
    return await select("SELECT sum(\"AMOUNT\"::numeric * 1000) FROM expenseactualsfunding WHERE \"wegov-org-id\"=$1 AND \"FISCAL YEAR\"=$2", (id, fyear))

@app.get('/get/orgs/stats-ac/{id}/{fyear}', tags=['Organizations'])
async def organization_additional_cost_stats(id: str, fyear: str):
    return await select("SELECT sum(\"TOTAL AMOUNT\"::numeric * 1000) FROM additionalcostsallocation WHERE \"wegov-org-id\"=$1 AND \"FISCAL YEAR\"=$2", (id, fyear))


@app.get('/get/orgs/pstats-projects_no/{id}/{pubdate}', tags=['Organizations'])
async def organization_projects_number_stats(id: str, pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\" = $1 AND \"PUB_DATE\"=$2", (id, pubdate))

@app.get('/get/orgs/pstats-orig_cost/{id}/{pubdate}', tags=['Organizations'])
async def organization_projects_original_cost_stats(id: str, pubdate: str):
    return await select("SELECT sum(\"BUDG_ORIG\") RES FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\" = $1 AND \"PUB_DATE\"=$2", (id, pubdate))

@app.get('/get/orgs/pstats-curr_cost/{id}/{pubdate}', tags=['Organizations'])
async def organization_projects_current_cost_stats(id: str, pubdate: str):
    return await select("SELECT sum(cast(REPLACE(\"BUDG_CURR\", ',', '.') as decimal)) RES FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\" = $1 AND \"PUB_DATE\"=$2", (id, pubdate))

@app.get('/get/orgs/pstats-over_budg_am/{id}/{pubdate}', tags=['Organizations'])
async def organization_projects_over_budgets_amount_stats(id: str, pubdate: str):
    return await select("SELECT -sum(cast(\"BUDG_DIFF\" as decimal)) RES FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\" = $1 AND \"PUB_DATE\"=$2", (id, pubdate))

@app.get('/get/orgs/pstats-long_no/{id}/{pubdate}', tags=['Organizations'])
async def organization_delayed_projects_number_stats(id: str, pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\" = $1 AND \"PUB_DATE\"=$2 AND \"DURATION_DIFF\" <> '-' AND cast(\"DURATION_DIFF\" as decimal) < 0", (id, pubdate))

@app.get('/get/orgs/pstats-over_budg_no/{id}/{pubdate}', tags=['Organizations'])
async def organization_over_budgeted_projects_number_stats(id: str, pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\" = $1 AND \"PUB_DATE\"=$2 AND cast(\"BUDG_DIFF\" as decimal) < 0", (id, pubdate))

@app.get('/get/orgs/pstats-late_start_no/{id}/{pubdate}', tags=['Organizations'])
async def organization_late_started_projects_number_stats(id: str, pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\" = $1 AND \"PUB_DATE\"=$2 AND \"START_DIFF\" <> '-' AND cast(REPLACE(\"START_DIFF\", ',', '.') as decimal) < 0", (id, pubdate))

@app.get('/get/orgs/pstats-late_end_no/{id}/{pubdate}', tags=['Organizations'])
async def organization_late_ended_projects_number_stats(id: str, pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\" = $1 AND \"PUB_DATE\"=$2 AND \"END_DIFF\" <> '-' AND cast(REPLACE(\"END_DIFF\", ',', '.') as decimal) < 0", (id, pubdate))

# ---- time-series stats for organization profile --------

@app.get('/get/orgs/stats-headcount/{id}', tags=['Organizations'])
async def organization_headcount_timeseries(id: str):
    return await select("SELECT \"FISCAL YEAR\" as year, sum(\"HEADCOUNT\"::numeric) as v FROM headcountactualsfunding WHERE \"wegov-org-id\"=$1 GROUP BY \"FISCAL YEAR\" ORDER BY \"FISCAL YEAR\"", (id,))

@app.get('/get/orgs/stats-pastheadcount/{id}', tags=['Organizations'])
async def organization_past_headcount_timeseries(id: str):
    return await select("SELECT \"CALENDAR YEAR\" as year, count(*) as v FROM civillist WHERE \"wegov-org-id\"=$1 GROUP BY \"CALENDAR YEAR\" ORDER BY \"CALENDAR YEAR\"", (id,))

@app.get('/get/orgs/stats-as/{id}', tags=['Organizations'])
async def organization_actual_spending_timeseries(id: str):
    return await select("SELECT \"FISCAL YEAR\" as year, sum(\"AMOUNT\"::numeric * 1000) as v FROM expenseactualsfunding WHERE \"wegov-org-id\"=$1 GROUP BY \"FISCAL YEAR\" ORDER BY \"FISCAL YEAR\"", (id,))

@app.get('/get/orgs/stats-ac/{id}', tags=['Organizations'])
async def organization_additional_cost_timeseries(id: str):
    return await select("SELECT \"FISCAL YEAR\" as year, sum(\"TOTAL AMOUNT\"::numeric * 1000) as v FROM additionalcostsallocation WHERE \"wegov-org-id\"=$1 GROUP BY \"FISCAL YEAR\" ORDER BY \"FISCAL YEAR\"", (id,))

@app.get('/get/orgs/stats-prj/{id}', tags=['Organizations'])
async def organization_project_stats_timeseries(id: str):
    return await select("SELECT \"PUB_DATE\" as pub_date, sum(cast(REPLACE(\"BUDG_CURR\", ',', '.') as decimal)) as budg_curr, -sum(cast(REPLACE(\"BUDG_DIFF\", ',', '.') as decimal)) as budg_diff FROM capitalprojectsdollarscomp WHERE \"wegov-org-id\"=$1 GROUP BY \"PUB_DATE\" ORDER BY \"PUB_DATE\"", (id,))

@app.get('/get/orgs/stats-civillist-aggregated/{id}', tags=['Organizations'])
async def organization_civillist_aggregated(id: str):
    # civillist has ~3.2M rows with text SALARY RATE (e.g. "$ 81,184.00") — needs
    # regexp_replace + SUM which exceeds the 15s global statement_timeout.
    sql = 'SELECT "TITLE CODE" as title, SUM(cast(regexp_replace("SALARY RATE", \'[$,]\', \'\', \'g\') as numeric)) as sum FROM civillist WHERE "wegov-org-id"=$1 GROUP BY "TITLE CODE" ORDER BY sum DESC LIMIT 10'
    rr = await PostgresModelAsync.select_safe_with_timeout(sql, [id], timeout_seconds=60)
    return {'rows': json.loads(PostgresModelAsync.jsonsafe(rr))}

# ---- notices --------

@app.get('/get/orgs/frontnews/{id}', tags=['Organizations'])
async def organization_future_news(id: str):
    return await select("SELECT \"StartDate\", \"EndDate\", \"SectionName\", \"ShortTitle\", \"RequestID\", \"TypeOfNoticeDescription\", \"wegov-org-name\", \"wegov-org-id\" FROM crol WHERE \"wegov-org-id\" = $1 AND \"EventDate\" = '' ORDER BY \"StartDate\" DESC LIMIT 9", (id,))
            
@app.get('/get/orgs/frontevents/{id}', tags=['Organizations'])
async def organization_future_events(id: str):
    return await select("SELECT \"StartDate\", \"EndDate\", \"SectionName\", \"ShortTitle\", \"RequestID\" FROM crol WHERE \"wegov-org-id\" = $1 AND \"EventDate\" <> '' ORDER BY \"EventDate\" DESC LIMIT 9", (id,))

@app.get('/get/orgs/notices/{id}', tags=['Organizations'])
async def organization_all_notices(id: str):
    return await select("SELECT * FROM crol WHERE \"wegov-org-id\"=$1 ORDER BY date(\"StartDate\")", (id,))
            
@app.get('/get/orgs/changeofpersonnel/{id}', tags=['Organizations'])
async def organization_change_of_personnel_notices(id: str):
    return await select("SELECT * FROM crol WHERE \"wegov-org-id\"=$1 AND \"SectionName\"='Changes in Personnel' ORDER BY date(\"StartDate\")", (id,))
            
@app.get('/get/orgs/publichearings/{id}', tags=['Organizations'])
async def organization_public_hearings_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Public Hearings and Meetings\'', (id,))
            
@app.get('/get/orgs/contractawards/{id}', tags=['Organizations'])
async def organization_contract_awards_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Contract Award Hearings\'', (id,))
            
@app.get('/get/orgs/specialmaterials/{id}', tags=['Organizations'])
async def organization_special_materials_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Special Materials\'', (id,))
            
@app.get('/get/orgs/agencyrules/{id}', tags=['Organizations'])
async def organization_agency_rules_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Agency Rules\'', (id,))
            
@app.get('/get/orgs/propertydisposition/{id}', tags=['Organizations'])
async def organization_property_disposition_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Property Disposition\'', (id,))
            
@app.get('/get/orgs/courtnotices/{id}', tags=['Organizations'])
async def organization_court_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Court Notices\'', (id,))
            
@app.get('/get/orgs/procurement/{id}', tags=['Organizations'])
async def organization_procurement_notices(id: str):
    return await select('SELECT "RequestID", "StartDate", "wegov-org-name", "TypeOfNoticeDescription", "CategoryDescription", "ShortTitle", "SelectionMethodDescription", "AdditionalDescription1", "SpecialCaseReasonDescription", "PIN", "DueDate", "EndDate", "AddressToRequest", "ContactName", "ContactPhone", "Email", "ContractAmount", "ContactFax", "OtherInfo1", "VendorName", "VendorAddress", "Printout1", "DocumentLinks", "EventBuildingName", "EventStreetAddress1" FROM crol WHERE "wegov-org-id"=$1 AND "SectionName" = \'Procurement\'', (id,))
            
@app.get('/get/orgs/events/{id}', tags=['Organizations'])
async def organization_events_notices(id: str):
    return await select('SELECT * FROM crol WHERE "wegov-org-id"=$1 AND NOT "EventDate" = \'\' ORDER BY date("EventDate") DESC', (id,))

@app.get('/get/orgs/icalevents/{id}', tags=['Event Feeds'])
async def organization_ical_events_feed(id: str):
    return await select("SELECT * FROM crol WHERE \"wegov-org-id\"=$1 AND NOT \"EventDate\" = '' AND DATE(\"EventDate\") >= DATE(NOW() - INTERVAL '1 week') ORDER BY date(\"EventDate\") DESC", (id,))

@app.get('/get/orgs/rssnews/{id}', tags=['Event Feeds'])
async def organization_rss_news_feed(id: str):
    return await select("SELECT c.* FROM crol c WHERE \"wegov-org-id\"=$1 AND \"EventDate\" = '' AND DATE(\"StartDate\") >= DATE(NOW() - INTERVAL '1 week') ORDER BY date(\"StartDate\") DESC", (id,))



# ================ capital projects ================

@app.get('/get/capitalprojects/all/{pubdate}', tags=['Capital Projects'])
async def get_capital_projects_by_year(pubdate: str):
    return await select("SELECT * FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\" = $1", (pubdate, ))

@app.get('/get/capitalprojects/profile/{prjid}', tags=['Capital Projects'])
async def get_capital_project_profile(prjid: str):
    return await select("SELECT * FROM capitalprojectsdollarscomp WHERE \"PROJECT_ID\" = $1 order by \"PUB_DATE\" DESC, \"PROJECT_ID\"", (prjid, ))

@app.get('/get/capitalprojects/milestones/{prjid}', tags=['Capital Projects'])
async def get_capital_project_milestones(prjid: str):
    return await select("SELECT * FROM capitalprojectsmilestones WHERE \"PROJECT_ID\" = $1 order by \"PUB_DATE\" DESC", (prjid, ))

@app.get('/get/capitalprojects/dates', tags=['Capital Projects'])
async def get_capital_projects_years_list():
    return await select("SELECT DISTINCT \"PUB_DATE\" FROM capitalprojectsdollarscomp ORDER BY \"PUB_DATE\" DESC")

@app.get('/get/capitalprojects/geojson', tags=['Capital Projects'])
async def get_capital_project_all_geodata():
    return await select('SELECT "GEO_JSON", "wegov-org-id" FROM capitalprojectsdollarscomp WHERE "PUB_DATE" = (SELECT DISTINCT "PUB_DATE" pd FROM capitalprojectsdollarscomp ORDER BY pd DESC LIMIT 1) AND "GEO_JSON" != \'\'')

@app.get('/get/capitalprojects/core/{prjid}', tags=['Capital Projects'])
async def get_capital_project_core(prjid: str):
    """Fetch a single capital project profile by ID.

    Why: Map popup links use maprojid format (e.g. '826WI-298-B') but the DB
    stores PROJECT_ID without the 3-digit agency prefix ('WI-298-B'). Try the
    exact ID first, then fall back to stripping the prefix.
    """
    result = await select("SELECT t1.*, t2.* FROM capitalprojectsdollarscomp t1 LEFT JOIN capitalprojectslist t2 ON t1.\"PROJECT_ID\" = t2.\"projectid\" WHERE t1.\"PROJECT_ID\" = $1 order by t1.\"PUB_DATE\" DESC LIMIT 1", (prjid, ))
    if not result.get('rows'):
        # Try stripping 3-digit managing agency prefix (maprojid → projectid)
        stripped = prjid[3:] if len(prjid) > 3 and prjid[:3].isdigit() else prjid
        if stripped != prjid:
            result = await select("SELECT t1.*, t2.* FROM capitalprojectsdollarscomp t1 LEFT JOIN capitalprojectslist t2 ON t1.\"PROJECT_ID\" = t2.\"projectid\" WHERE t1.\"PROJECT_ID\" = $1 order by t1.\"PUB_DATE\" DESC LIMIT 1", (stripped, ))
    if not result.get('rows'):
        # Fallback: ~6.3K projects live in capitalprojectslist but have no row in
        # the capital-commitment-plan *dollars* dataset (unbudgeted / planning-stage).
        # Return the list row tagged _source='list' so the frontend renders the
        # reduced project page (no dollars/schedule time-series) instead of 404ing.
        result = await select("SELECT *, 'list' AS _source FROM capitalprojectslist WHERE \"maprojid\" = $1 OR \"projectid\" = $1 LIMIT 1", (prjid, ))
    return result

@app.get('/get/capitalprojects/commitments/{prjid}', tags=['Capital Projects'])
async def get_capital_project_commitments(prjid: str):
    # Match either id form: callers pass maprojid (e.g. 858DOIT5MYSM) or the
    # prefix-stripped projectid (DOIT5MYSM); the table carries both columns.
    return await select("SELECT * FROM capitalprojectscommitments WHERE \"projectid\" = $1 OR \"maprojid\" = $1", (prjid, ))

@app.get('/get/capitalprojects/budgetandspend/{prjid}', tags=['Capital Projects'])
async def get_capital_project_budget_and_spend(prjid: str):
    return await select("SELECT * FROM capprojectsbudgetandspend WHERE \"FMS ID\" = $1", (prjid, ))

@app.get('/get/capitalprojects/budgetspendhistory/{prjid}', tags=['Capital Projects'])
async def get_capital_project_budget_spend_history(prjid: str):
    return await select("SELECT * FROM capprojectsbudgetspendhistory WHERE \"FMS ID\" = $1", (prjid, ))

@app.get('/get/capitalprojects/budgetsandschedule/{prjid}', tags=['Capital Projects'])
async def get_capital_project_budgets_and_schedule(prjid: str):
    return await select("SELECT * FROM capprojectsbudgetsandschedule WHERE \"FMS ID\" = $1", (prjid, ))

@app.get('/get/capitalprojects/schedulehistory/{agcy_cd}', tags=['Capital Projects'])
async def get_capital_project_schedule_history(agcy_cd: str):
    return await select("SELECT * FROM capprojectsschedulehistory WHERE \"Managing Agency\" = $1", (agcy_cd, ))

_projects_map_cache: dict = None
_projects_map_cache_time: float = 0.0

_PROJECTS_MAP_SQL = '''
    SELECT
        t1."PROJECT_ID",
        t1."PROJECT_DESCR",
        t1."GEO_JSON",
        t1."LAT" AS lat,
        t1."LNG" AS lng,
        t1."BUDG_CURR" AS "PLANNEDCOST",
        t1."START_ORIG",
        t1."END_CURR",
        t1."BORO",
        t1."TYP_CATEGORY_NAME" AS "CATEGORY",
        t1."wegov-project-type-names" AS "wegov-prjtype-name",
        t1."wegov-project-category" AS "wegov-prj-color",
        t1."wegov-org-name",
        t1."wegov-org-id",
        t2.description AS "description",
        t2.projectid,
        t2.typecategory
    FROM capitalprojectsdollarscomp t1
    LEFT JOIN capitalprojectslist t2 ON t1."PROJECT_ID" = t2.projectid
    WHERE t1."PUB_DATE" = (SELECT max("PUB_DATE") FROM capitalprojectsdollarscomp)
'''

async def _load_projects_map_cache():
    """Load (or refresh) the projects map cache. Runs at startup and every 6 hours.

    Why: capitalprojectsdollarscomp has 5k rows with large GEO_JSON TOAST values
    that take >15s to read, exceeding Postgres statement_timeout. Caching at app-level
    sidesteps the timeout entirely and makes map loads instant for all users.
    """
    import time
    global _projects_map_cache, _projects_map_cache_time
    try:
        rows = await PostgresModelAsync.select_safe_with_timeout(_PROJECTS_MAP_SQL, [], timeout_seconds=120)
        _projects_map_cache = {'rows': rows}
        _projects_map_cache_time = time.time()
        print(f"[projects cache] Loaded {len(rows)} projects into map cache.")
    except Exception as e:
        print(f"[projects cache] Failed to load: {e}")

@app.get('/get/capitalprojects/projectsnew', tags=['Capital Projects'])
async def get_capital_projects_new():
    """Serve projects map data from in-memory cache (built at startup, refreshed every 6h).
    
    Why cached: The underlying query reads ~10MB of GEO_JSON TOAST data across 5k rows,
    which consistently exceeds the 15s Postgres statement_timeout.
    """
    import time
    if _projects_map_cache is None:
        return JSONResponse(status_code=503, content={'error': 'Cache loading, please retry in 60s'})
    # Refresh stale cache in background (don't block the response)
    if time.time() - _projects_map_cache_time > 21600:
        import asyncio
        asyncio.create_task(_load_projects_map_cache())
    return _projects_map_cache

@app.get('/get/capitalprojects/mcore/{id}', tags=['Capital Projects'])
async def get_minor_capital_project_core(id: str):
    return await select('SELECT * FROM capitalprojectslist WHERE "maprojid"=$1', (id,))

# ---- stats --------


@app.get('/get/pstats-projects_no/{pubdate}', tags=['Capital Projects'])
async def get_capital_projects_number_by_publication_date(pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\"=$1", (pubdate,))

@app.get('/get/pstats-orig_cost/{pubdate}', tags=['Capital Projects'])
async def get_capital_projects_original_cost_by_publication_date(pubdate: str):
    return await select("SELECT sum(\"BUDG_ORIG\") RES FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\"=$1", (pubdate,))

@app.get('/get/pstats-curr_cost/{pubdate}', tags=['Capital Projects'])
async def get_capital_projects_current_cost_by_publication_date(pubdate: str):
    return await select("SELECT sum(cast(REPLACE(\"BUDG_CURR\", ',', '.') as decimal)) RES FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\"=$1", (pubdate,))

@app.get('/get/pstats-over_budg_am/{pubdate}', tags=['Capital Projects'])
async def get_capital_projects_over_budget_amount_by_publication_date(pubdate: str):
    return await select("SELECT -sum(cast(\"BUDG_DIFF\" as decimal)) RES FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\"=$1", (pubdate,))

@app.get('/get/pstats-long_no/{pubdate}', tags=['Capital Projects'])
async def get_delayed_capital_projects_number_by_publication_date(pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\"=$1 AND \"DURATION_DIFF\" <> '-' AND cast(\"DURATION_DIFF\" as decimal) < 0", (pubdate,))

@app.get('/get/pstats-over_budg_no/{pubdate}', tags=['Capital Projects'])
async def get_over_budget_capital_projects_number_by_publication_date(pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\"=$1 AND cast(\"BUDG_DIFF\" as decimal) < 0", (pubdate,))

@app.get('/get/pstats-late_start_no/{pubdate}', tags=['Capital Projects'])
async def get_number_of_capital_projects_with_late_start_by_publication_date(pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\"=$1 AND \"START_DIFF\" <> '-' AND cast(REPLACE(\"START_DIFF\", ',', '.') as decimal) < 0", (pubdate,))

@app.get('/get/pstats-late_end_no/{pubdate}', tags=['Capital Projects'])
async def get_number_of_capital_projects_with_late_end_by_publication_date(pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp WHERE \"PUB_DATE\"=$1 AND \"END_DIFF\" <> '-' AND cast(REPLACE(\"END_DIFF\", ',', '.') as decimal) < 0", (pubdate,))


# ================ Titles =======================

@app.get('/get/titles', tags=['Titles'])
async def get_all_civil_titles():
    return await select('SELECT * FROM nyccivilservicetitles ORDER BY "Title Code"', [])

@app.get('/get/titles/{id}', tags=['Titles'])
async def get_civil_title_profile(id: str):
    return await select("SELECT * FROM nyccivilservicetitles WHERE \"Title Code\" = $1 ORDER BY \"Assignment Level\"", (id, ))

@app.get('/get/titles/{id}/stats-civillist_salaries_by_year', tags=['Titles'])
async def get_salaries_by_year_stats_from_civillist(id: str):
    """Aggregate salary stats by year for the Employees & Salaries chart.

    Why: The titleheader.blade.php chart expects {year, salary, employees} fields.
    """
    return await select("""
        SELECT "CALENDAR YEAR" AS year,
               CAST(SUM(CAST(REGEXP_REPLACE("SALARY RATE", '[$\\s,]', '', 'g') AS REAL)) AS INT) AS salary,
               COUNT(*) AS employees
        FROM civillist
        WHERE "TITLE CODE" = $1
        GROUP BY "CALENDAR YEAR"
        ORDER BY "CALENDAR YEAR"
    """, (id,))

@app.get('/get/titles/{id}/stats-positionschedule_positions_by_agency', tags=['Titles'])
async def get_positions_by_agency_stats(id: str):
    """Aggregate position counts by agency for a given title code."""
    return await select('SELECT "AGENCY NAME" as agency, SUM(CAST("POSITIONS" AS INT)) as positions FROM positionschedule WHERE "TITLE CODE"=$1 AND "PUBLICATION DATE" = (SELECT MAX("PUBLICATION DATE") FROM positionschedule) GROUP BY "AGENCY NAME" ORDER BY positions DESC', (id,))

@app.get('/get/titles/{id}/{tbl}', tags=['Titles'])
async def get_subdataset_related_to_civil_title(id: str, tbl: str):
    # Map table names to their title ID column
    col_map = {
        'positionschedule': 'TITLE CODE',
        'civillist': 'TITLE CODE',
        'nycjobs': 'wegov-service-title-id',
        'civillistactive': 'wegov-service-title-id',
    }
    col = col_map.get(tbl, 'wegov-service-title-id')
    # positionschedule and civillistactive don't have wegov-org-id
    order_map = {
        'positionschedule': '"AGENCY NAME"',
        'nycjobs': '"wegov-org-id"',
        'civillist': '"wegov-org-id"',
        'civillistactive': '1',
    }
    order_col = order_map.get(tbl, '1')
    # Cap rows. A few title codes map to hundreds of thousands of civillist rows
    # (e.g. 70210 ≈ 262k). SELECT * with no LIMIT materialized the entire set into
    # a Python list of dicts — ~660 MB for a single call, so a few concurrent
    # requests OOM-killed the container (this was THE api crash-loop driver). It
    # also swamps the client-side DataTable. Cap to a browsable window; the title
    # charts use the separate aggregated /stats-* endpoints, so totals are
    # unaffected by this cap.
    _ROW_CAP = 10000
    if tbl == 'civillist':
        return await select(
            'SELECT * FROM civillist WHERE "TITLE CODE"=$1 ORDER BY "wegov-org-id" LIMIT {}'.format(_ROW_CAP),
            (id,))
    return await select('SELECT * FROM {} WHERE "{}"=$1 ORDER BY {} LIMIT {}'.format(tbl, col, order_col, _ROW_CAP), (id,))


# ================ Jobs =======================

_jobs_cache = {"data": None, "ts": 0}

@app.get('/get/jobs/all', tags=['Jobs'], summary="Get all current NYC job postings")
async def get_all_nyc_jobs():
    """Return job postings with only the columns needed for the Jobs page cards.

    Why: SELECT * returns 35+ columns including multi-KB text fields (Job Description,
    Minimum Qual Requirements, Preferred Skills) which bloats the response from ~15MB
    to ~1.6MB and slows client-side parsing. Only card-relevant fields are selected.

    Caching: 15-minute in-memory cache since nycjobs updates daily.
    """
    import time
    now = time.time()
    if _jobs_cache["data"] and (now - _jobs_cache["ts"]) < 900:  # 15 min
        from starlette.responses import JSONResponse
        return JSONResponse(
            content=_jobs_cache["data"],
            headers={"Cache-Control": "public, max-age=300"}
        )

    # Try full query with org enrichment columns first; fall back to base columns
    # if wegov-org-name / wegov-org-id haven't been added to nycjobs yet (e.g. staging).
    try:
        result = await select("""
            SELECT "Job ID", "Business Title", "Civil Service Title", "Agency",
                   "wegov-org-name", "wegov-org-id", "Salary Range From", "Salary Range To",
                   "Salary Frequency", "Posting Type", "Career Level", "Title Code No",
                   "Posting Date", "Post Until", "Full-Time/Part-Time indicator",
                   "Job Category", "Title Classification", "Work Location",
                   "# Of Positions", "Level"
            FROM nycjobs ORDER BY "Posting Date" DESC
        """, [])
    except Exception:
        # Org-enrichment columns missing — return base columns with NULL stubs
        result = await select("""
            SELECT "Job ID", "Business Title", "Civil Service Title", "Agency",
                   NULL AS "wegov-org-name", NULL AS "wegov-org-id",
                   "Salary Range From", "Salary Range To",
                   "Salary Frequency", "Posting Type", "Career Level", "Title Code No",
                   "Posting Date", "Post Until", "Full-Time/Part-Time indicator",
                   "Job Category", "Title Classification", "Work Location",
                   "# Of Positions", "Level"
            FROM nycjobs ORDER BY "Posting Date" DESC
        """, [])

    _jobs_cache["data"] = result
    _jobs_cache["ts"] = now

    from starlette.responses import JSONResponse
    return JSONResponse(
        content=result,
        headers={"Cache-Control": "public, max-age=300"}
    )




# ================ Districts =======================


@app.get('/get/orgs/bycd/{cd}', tags=['Organizations'])
async def get_organization_profile_associated_to_community_district(cd: str):
    #return await select('SELECT "id", "url" FROM wegov_orgs WHERE "communityDistrictId" LIKE $1', (cd,))
    return await select('SELECT * FROM wegov_orgs WHERE "communityDistrictId" = $1', ('["{}"]'.format(cd),))

@app.get('/get/orgs/bycc/{cc}', tags=['Organizations'])
async def get_organization_profile_associated_to_city_council_district(cc: str):
    #return await select('SELECT "id", "url" FROM wegov_orgs WHERE "cityCouncilDistrictId" LIKE $1', (cc,))
    return await select('SELECT * FROM wegov_orgs WHERE "cityCouncilDistrictId" = $1', ('["{}"]'.format(cc),))

# ---- fire battalions (spatial) --------
# These MUST be declared before the generic /{type}/{id}/{tbl} route below,
# otherwise FastAPI matches the wildcard first.

@app.get('/get/districts/fb/{id}/fire_causes', tags=['Districts'])
async def get_fire_causes_by_battalion(id: str, limit: int=Query(None, ge=1, le=10000), offset: int=Query(0, ge=0)):
    page_clause = f" LIMIT {int(limit)}" if limit else ""
    page_clause += f" OFFSET {int(offset)}" if offset else ""
    return await select(f'SELECT * FROM fire_causes WHERE "battalion_id" = $1{page_clause}', (id,))

@app.get('/get/districts/fb/{id}/fire_inspections', tags=['Districts'])
async def get_fire_inspections_by_battalion(id: str, limit: int=Query(None, ge=1, le=10000), offset: int=Query(0, ge=0)):
    page_clause = f" LIMIT {int(limit)}" if limit else ""
    page_clause += f" OFFSET {int(offset)}" if offset else ""
    return await select(f'SELECT * FROM fdny_inspections WHERE "battalion_id" = $1{page_clause}', (id,))

@app.get('/get/districts/fb/{id}/fire_violations', tags=['Districts'])
async def get_fire_violations_by_battalion(id: str, limit: int=Query(None, ge=1, le=10000), offset: int=Query(0, ge=0)):
    page_clause = f" LIMIT {int(limit)}" if limit else ""
    page_clause += f" OFFSET {int(offset)}" if offset else ""
    return await select(f'SELECT * FROM fdny_violations WHERE "battalion_id" = $1{page_clause}', (id,))

@app.get('/get/districts/fb/{id}/fire_dispatch', tags=['Districts'])
async def get_fire_dispatch_by_battalion(id: str, limit: int=Query(200, ge=1, le=10000), offset: int=Query(0, ge=0)):
    """Query dispatch records by battalion using array containment.

    Why: battalion_ids is a TEXT[] array because one Police Precinct can
    overlap with multiple Fire Battalions (many-to-many crosswalk).
    Default limit=200 to prevent full-table scans (~35s) on this 600k+ row table.
    """
    page_clause = f" LIMIT {int(limit)}"
    page_clause += f" OFFSET {int(offset)}" if offset else ""
    try:
        return await select(f'SELECT * FROM fire_incident_dispatch WHERE $1 = ANY("battalion_ids"){page_clause}', (id,))
    except Exception:
        return {"rows": [], "note": "fire_incident_dispatch not yet ingested"}


@app.get('/get/districts/{type}/{id}/capitalprojects', tags=['Districts'])
async def get_capital_projects_by_administrative_district(type: str, id: str):
    # `type` is interpolated into the crosswalk table name (capitalprojects_<type>_idx),
    # so guard it to a safe charset to keep the interpolation injection-proof. Crosswalk
    # tables exist for cd/cc/sd; nta has none (2010↔2020 NTA boundaries don't crosswalk —
    # the frontend hides capital projects for nta districts), so a missing table must
    # return empty rather than 500. _district_select tolerates the missing relation.
    if not re.fullmatch(r"[a-z]{2,4}", type):
        return {"rows": []}
    return await _district_select("SELECT pp.*, i.\"DIST\" FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1".format(type), (id,))

# Column mapping: which column stores the district identifier for each table + district type.
# Used by the generic district subdataset endpoint to filter rows by district.
# Keys are district types (cd, cc, nta); values map table names to their filter column.
# Lists are used when column names differ between environments (e.g. staging vs production).
DISTRICT_COLUMNS = {
    "cd": {
        "councilstatcases": ["Community Board", "COMMUNITY_BOARD"],
        "nyccouncildiscretionaryfunding": ["Community Board"],
        "budgetrequestsregister": ["Community Board"],
        "facilitydb": ["cd"],
    },
    "cc": {
        "councilstatcases": ["Council District", "COUNCIL_DIST"],
        "nyccouncildiscretionaryfunding": ["Council District"],
        "budgetrequestsregister": ["Council District"],
        "facilitydb": ["council"],
    },
    "nta": {
        # nyccouncildiscretionaryfunding intentionally absent: its NTA column is
        # 2010-vintage (stores 2010 NTA *names*), incompatible with the 2020 NTAs
        # the district pages use. 2010 and 2020 NTAs differ in actual boundaries,
        # not just naming, so there is no valid crosswalk — the section is hidden
        # for the nta district type (see app DistDatasets). Don't re-add without a
        # genuine 2020-vintage NTA column on this table.
        "budgetrequestsregister": ["Neighborhood Tabulation Area (NTA) (2020)"],
        "facilitydb": ["nta2020"],
        # councilstatcases has no NTA column
    },
}

# Borough digit to name mapping for parsing cd IDs (e.g. 101 = Manhattan district 01)
_CD_BOROUGH_NAMES = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}

# Tables where 'Community Board' stores "01 Manhattan" format instead of "101"
_CD_BOROUGH_FORMAT_TABLES = {"councilstatcases"}

# Tables where 'Community Board' stores just the board number ("01" or "1")
_CD_BOARD_ONLY_TABLES = {"budgetrequestsregister"}

# Tables where 'Council District' stores "NYCC001" prefix format
_CC_NYCC_PREFIX_TABLES = {"councilstatcases"}

# Cache resolved column names to avoid repeated schema queries
_resolved_columns: dict = {}

async def _resolve_district_column(tbl: str, candidates: list) -> str:
    """Find the actual column name from a list of candidates by checking the DB schema.

    Why: Column names differ between environments (e.g. 'Community Board' vs 'COMMUNITY_BOARD').
    Caches results so the schema is queried only once per table+candidates combination.
    """
    cache_key = f"{tbl}:{','.join(candidates)}"
    if cache_key in _resolved_columns:
        return _resolved_columns[cache_key]

    if len(candidates) == 1:
        _resolved_columns[cache_key] = candidates[0]
        return candidates[0]

    # Query the DB schema to find which candidate column actually exists
    try:
        result = await select(
            "SELECT column_name FROM information_schema.columns WHERE table_name = $1 AND column_name = ANY($2) LIMIT 1",
            (tbl, candidates))
        if result and "rows" in result and result["rows"]:
            col = result["rows"][0]["column_name"]
            _resolved_columns[cache_key] = col
            return col
    except Exception:
        pass

    # Fallback to first candidate
    _resolved_columns[cache_key] = candidates[0]
    return candidates[0]

async def _district_select(query: str, params: tuple = ()):
    """select() that tolerates the brief window during a table re-import (the
    scheduler's staging-swap drops/renames the table), returning empty instead
    of a 500 if the table/column momentarily isn't there."""
    try:
        return await select(query, params)
    except (asyncpg.exceptions.UndefinedColumnError, asyncpg.exceptions.UndefinedTableError):
        return {"rows": []}

@app.get('/get/districts/{type}/{id}/{tbl}', tags=['Districts'])
async def get_subdataset_by_administrative_district(type: str, tbl: str, id: str, sort: str=Query(None), f: str=Query(None), limit: int=Query(None, ge=1, le=10000), offset: int=Query(0, ge=0)):
    """Get rows from a table filtered by district type and id.

    Why: The filter column varies per table. DISTRICT_COLUMNS provides the
    mapping; the `f` query param is a legacy fallback for tables not in the map.
    Value formats also differ: facilitydb stores cd as '101', councilstatcases
    stores '01 Manhattan', budgetrequestsregister stores '01'.
    """
    # Determine which column to filter on
    candidates = DISTRICT_COLUMNS.get(type, {}).get(tbl)
    if not candidates:
        if not f:
            return {"rows": [], "error": f"No column mapping for table '{tbl}' with district type '{type}'"}
        col = f
    else:
        col = await _resolve_district_column(tbl, candidates)

    # Build ORDER BY clause (optional)
    order_clause = ""
    if sort and ',' in sort:
        s1, s2 = sort.split(',', 1)
        order_clause = ' ORDER BY "{}", "{}"'.format(s1.strip().strip('"'), s2.strip().strip('"'))

    # Build pagination clause
    page_clause = ""
    if limit is not None:
        page_clause = f" LIMIT {int(limit)}"
    if offset:
        page_clause += f" OFFSET {int(offset)}"

    # Handle cd value format differences
    if type == "cd" and len(id) == 3 and tbl in _CD_BOROUGH_FORMAT_TABLES:
        # Convert 101 → "01 Manhattan" (LIKE match for leading-zero/no-leading-zero variants)
        boro_digit = id[0]
        district_num = id[1:]  # "01"
        boro_name = _CD_BOROUGH_NAMES.get(boro_digit, "")
        # Match both "01 Manhattan" and "1 Manhattan" variants
        district_int = str(int(district_num))  # strip leading zero: "01" → "1"
        like_pattern = f"%{boro_name}"
        return await _district_select(
            'SELECT * FROM {} WHERE "{}" LIKE $1 AND (SPLIT_PART("{}", \' \', 1) = $2 OR SPLIT_PART("{}", \' \', 1) = $3){}{}'.format(
                tbl, col, col, col, order_clause, page_clause),
            (like_pattern, district_num, district_int))

    if type == "cd" and len(id) == 3 and tbl in _CD_BOARD_ONLY_TABLES:
        # Convert 101 → match "01" or "1" (board number only, no borough)
        district_num = id[1:]  # "01"
        district_int = str(int(district_num))  # "1"
        return await _district_select(
            'SELECT * FROM {} WHERE "{}" = $1 OR "{}" = $2{}{}'.format(tbl, col, col, order_clause, page_clause),
            (district_num, district_int))

    # Handle cc value format differences
    if type == "cc" and tbl in _CC_NYCC_PREFIX_TABLES:
        # councilstatcases stores council district as "NYCC001", "NYCC01", "NYCC1"
        # Try all zero-padded variants: NYCC001, NYCC01, NYCC1
        padded3 = id.zfill(3)   # "001"
        padded2 = id.zfill(2)   # "01"
        raw = str(int(id)) if id.isdigit() else id  # "1"
        return await _district_select(
            'SELECT * FROM {} WHERE "{}" IN ($1, $2, $3){}{}'.format(tbl, col, order_clause, page_clause),
            (f"NYCC{padded3}", f"NYCC{padded2}", f"NYCC{raw}"))

    return await _district_select('SELECT * FROM {} WHERE "{}"=$1{}{}'.format(tbl, col, order_clause, page_clause), (id,))


# ---- stats --------

@app.get('/get/districts/pstats-projects_no/{type}/{id}/{pubdate}', tags=['Districts'])
async def get_capital_projects_number_by_administrative_district_and_publication_date(type: str, id: str, pubdate: str):
    return await select("SELECT count(pp.*) RES FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1 AND \"PUB_DATE\"=$2".format(type), (id, pubdate))

@app.get('/get/districts/pstats-orig_cost/{type}/{id}/{pubdate}', tags=['Districts'])
async def get_capital_projects_original_cost_by_administrative_district_and_publication_date(type: str, id: str, pubdate: str):
    return await select("SELECT sum(\"BUDG_ORIG\") RES FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1 AND \"PUB_DATE\"=$2".format(type), (id, pubdate))

@app.get('/get/districts/pstats-curr_cost/{type}/{id}/{pubdate}', tags=['Districts'])
async def get_capital_projects_current_cost_by_administrative_district_and_publication_date(type: str, id: str, pubdate: str):
    return await select("SELECT sum(cast(REPLACE(\"BUDG_CURR\", ',', '.') as decimal)) RES FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1 AND \"PUB_DATE\"=$2".format(type), (id, pubdate))

@app.get('/get/districts/pstats-over_budg_am/{type}/{id}/{pubdate}', tags=['Districts'])
async def get_capital_projects_overbudget_amount_by_administrative_district_and_publication_date(type: str, id: str, pubdate: str):
    return await select("SELECT -sum(cast(\"BUDG_DIFF\" as decimal)) RES FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1 AND \"PUB_DATE\"=$2 AND cast(\"BUDG_DIFF\" as decimal) < 0".format(type), (id, pubdate))

@app.get('/get/districts/pstats-long_no/{type}/{id}/{pubdate}', tags=['Districts'])
async def get_delayed_capital_projects_number_by_administrative_district_and_publication_date(type: str, id: str, pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1 AND \"PUB_DATE\"=$2 AND \"DURATION_DIFF\" <> '-' AND cast(\"DURATION_DIFF\" as decimal) < 0".format(type), (id, pubdate))

@app.get('/get/districts/pstats-over_budg_no/{type}/{id}/{pubdate}', tags=['Districts'])
async def get_number_of_overbudgeted_capital_projects_by_administrative_district_and_publication_date(type: str, id: str, pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1 AND \"PUB_DATE\"=$2 AND cast(\"BUDG_DIFF\" as decimal) < 0".format(type), (id, pubdate))

@app.get('/get/districts/pstats-late_start_no/{type}/{id}/{pubdate}', tags=['Districts'])
async def get_number_of_capital_projects_with_late_start_by_administrative_district_and_publication_date(type: str, id: str, pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1 AND \"PUB_DATE\"=$2 AND \"START_DIFF\" <> '-' AND cast(REPLACE(\"START_DIFF\", ',', '.') as decimal) < 0".format(type), (id, pubdate))

@app.get('/get/districts/pstats-late_end_no/{type}/{id}/{pubdate}', tags=['Districts'])
async def get_number_of_capital_projects_with_late_end_by_administrative_district_and_publication_date(type: str, id: str, pubdate: str):
    return await select("SELECT count(*) RES FROM capitalprojectsdollarscomp pp INNER JOIN capitalprojects_{}_idx i ON pp.\"PROJECT_ID\"=i.\"PROJECT_ID\" WHERE i.\"DIST\" = $1 AND \"PUB_DATE\"=$2 AND \"END_DIFF\" <> '-' AND cast(REPLACE(\"END_DIFF\", ',', '.') as decimal) < 0".format(type), (id, pubdate))




# ================ notices =======================

@app.get('/get/notices/frontnews', tags=['Notices'])
async def get_all_future_news():
    return await select("SELECT \"StartDate\", \"EndDate\", \"SectionName\", \"ShortTitle\", \"RequestID\" , \"TypeOfNoticeDescription\", \"wegov-org-name\", \"wegov-org-id\" FROM crol WHERE \"EventDate\" = '' AND start_date_parsed::date >= current_date - INTERVAL '7 days' order by start_date_parsed DESC LIMIT 9", [])

@app.get('/get/notices/frontevents', tags=['Notices'])
async def get_all_future_events():
    return await select("""SELECT "StartDate", "EndDate", "SectionName", "ShortTitle", "RequestID", "EventDate", "TypeOfNoticeDescription", "wegov-org-name", "wegov-org-id" FROM crol WHERE event_date_parsed IS NOT NULL AND event_date_parsed >= current_date ORDER BY event_date_parsed LIMIT 9""", [])

@app.get('/get/notices/last30daysstats', tags=['Notices'])
async def get_last30days_stats():
    return await select("""
        SELECT "SectionName", start_date_parsed as "StartDate", COUNT(*) as count FROM crol 
        WHERE "EventDate" = '' AND start_date_parsed::date >= current_date - INTERVAL '30 days'
        GROUP BY "SectionName", start_date_parsed
        ORDER BY start_date_parsed
    """, [])

@app.get('/get/notices/years', tags=['Notices'])
async def get_list_of_notices_year():
    return await select('SELECT DISTINCT(SUBSTRING(\"StartDate\" from 7 for 4)) yy FROM crol ORDER BY yy DESC', [])
            

@app.get('/get/notices/all/{year}', tags=['Notices'])
async def get_all_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "EventDate" = \'\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/changeofpersonnel/{year}', tags=['Notices'])
async def get_change_of_personnel_notices_by_year(year: int):
    return await select('SELECT "AdditionalDescription1", "StartDate", "wegov-org-id", "wegov-org-name" FROM crol WHERE "SectionName" = \'Changes in Personnel\' AND NOT "AdditionalDescription1" = \'\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/publichearings/{year}', tags=['Notices'])
async def get_public_hearings_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Public Hearings and Meetings\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])

@app.get('/get/notices/meetings/{year}', tags=['Notices'])
async def get_meetings_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Public Hearings and Meetings\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/contractawards/{year}', tags=['Notices'])
async def get_contract_awards_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Contract Award Hearings\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/specialmaterials/{year}', tags=['Notices'])
async def get_special_materials_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Special Materials\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/agencyrules/{year}', tags=['Notices'])
async def get_agency_rules_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Agency Rules\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/propertydisposition/{year}', tags=['Notices'])
async def get_property_disposition_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Property Disposition\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/courtnotices/{year}', tags=['Notices'])
async def get_court_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE "SectionName" = \'Court Notices\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/procurement/{year}', tags=['Notices'])
async def get_procurement_notices_by_year(year: int):
    # resolved_ctr_id / resolved_epin: forward links from procurement notices to the
    # awarded contract (PIN = contracts.epin, exact) or the solicitation (PIN[:10] = EPIN).
    return await select('SELECT "RequestID", "StartDate", "wegov-org-name", "wegov-org-id", "TypeOfNoticeDescription", "CategoryDescription", "ShortTitle", "SelectionMethodDescription", "AdditionalDescription1", "SpecialCaseReasonDescription", "PIN", "DueDate", "EndDate", "AddressToRequest", "ContactName", "ContactPhone", "Email", "ContractAmount", "ContactFax", "OtherInfo1", "VendorName", "VendorAddress", "Printout1", "DocumentLinks", "EventBuildingName", "EventStreetAddress1", ct.ctr_id AS resolved_ctr_id, s."EPIN" AS resolved_epin FROM crol c LEFT JOIN LATERAL (SELECT ctr_id FROM contracts WHERE epin = trim(c."PIN") LIMIT 1) ct ON true LEFT JOIN LATERAL (SELECT "EPIN" FROM solicitations WHERE "EPIN" = left(trim(c."PIN"),10) LIMIT 1) s ON true WHERE "SectionName" = \'Procurement\' AND SUBSTRING("StartDate" from 7 for 4) = \'{}\''.format(year), [])
            
@app.get('/get/notices/events/{year}', tags=['Notices'])
async def get_event_notices_by_year(year: int):
    return await select('SELECT * FROM crol WHERE NOT "EventDate" = \'\' AND SUBSTRING("EventDate" from 7 for 4) = \'{}\''.format(year), [])

@app.get('/get/notices/icalevents', tags=['Notices'])
async def get_events_ical_feed():
    return await select('SELECT * FROM crol WHERE event_date_parsed IS NOT NULL AND event_date_parsed >= current_date - INTERVAL \'1 week\' ORDER BY event_date_parsed DESC', [])

@app.get('/get/notices/rssnews', tags=['Notices'])
async def get_news_rss_feed():
    return await select('SELECT c.* FROM crol c WHERE event_date_parsed IS NULL AND start_date_parsed IS NOT NULL AND start_date_parsed >= current_date - INTERVAL \'1 week\' ORDER BY start_date_parsed DESC', [])

@app.get('/get/notices/lastupdated', tags=['Notices'])
async def get_crol_last_updated():
    """Get the date when CROL data was last ingested into our database."""
    # Try ingestion_log first (most accurate)
    result = await select(
        "SELECT ingested_at FROM ingestion_log WHERE table_name = 'crol' AND status = 'success' ORDER BY ingested_at DESC LIMIT 1"
    )
    if result.get('rows') and result['rows'][0].get('ingested_at'):
        return {'rows': [{'last_updated': result['rows'][0]['ingested_at']}]}
    
    # Fallback: use most recent StartDate from crol table
    result = await select("SELECT MAX(start_date_parsed) as last_updated FROM crol")
    return result


# ---- stats --------
            
@app.get('/get/notices/stats/publichearings/{days}', tags=['Notices'])
async def get_public_hearings_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Public Hearings and Meetings\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/contractawards/{days}', tags=['Notices'])
async def get_contract_awards_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Contract Award Hearings\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/specialmaterials/{days}', tags=['Notices'])
async def get_special_materials_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Special Materials\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/agencyrules/{days}', tags=['Notices'])
async def get_agency_rules_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Agency Rules\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/propertydisposition/{days}', tags=['Notices'])
async def get_property_disposition_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Property Disposition\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/courtnotices/{days}', tags=['Notices'])
async def get_court_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Court Notices\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/procurement/{days}', tags=['Notices'])
async def get_procurement_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Procurement\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])

@app.get('/get/notices/stats/changeofpersonnel/{days}', tags=['Notices'])
async def get_change_of_personnel_notices_number_in_last_n_days(days: int):
    return await select('SELECT COUNT(*) RES FROM crol WHERE NOT "StartDate" = \'\' AND "SectionName" = \'Changes in Personnel\' AND NOT "AdditionalDescription1" = \'\' AND DATE("StartDate") >= DATE(NOW() - INTERVAL \'{} days\')'.format(days), [])



# ================ auctions =======================

@app.get('/get/auctions', tags=['Auctions'])
async def get_all_auctions():
    return await select('SELECT * FROM auctions WHERE date("Auction Ends") >= date(now()) ORDER BY "Auction Ends"', [])

@app.get('/get/frontauctions', tags=['Auctions'])
async def get_future_auctions():
    return await select('SELECT * FROM auctions WHERE date("Auction Ends") > date(now()) ORDER BY "Auction Ends" LIMIT 3', [])




# ================ srv routes ================

@app.post('/login', tags=['Auth'], summary="Authentication entry point", 
        responses={200: {
            'description': 'Access token',
            'content': {'application/json': {'example': {'access_token': 'xxxxxxxxxxxxxxxxxxxxxx', 'token_type': 'bearer'}}}
        }})
def auth(data: OAuth2PasswordRequestForm = Depends()):
    """
    Get authentication token
    """
    email = data.username
    password = data.password

    #user = query_user(email)
    usr = user.get_user(email=email)
    if not usr:
        raise InvalidCredentialsException
    elif User.pwd_hash(password) != usr['pwdhash']:
        raise InvalidCredentialsException

    access_token = manager.create_access_token(
        data={'sub': usr['id']}
        ,expires=datetime.timedelta(hours=24)
        ,scopes=['read']
    )
    return {'access_token': access_token, 'token_type': 'bearer'}


    
@app.post('/upload', tags=['Datasets'], summary="Upload CSV dataset", 
        responses={200: {'description': 'Success', 'content': {'application/json': {'example': {'result': 'OK'}}}},
                   503: {'description': 'Failed', 'content': {'application/json': {'example': {'result': 'Fail'}}}}}
         )
async def upload_csv_dataset(
    url: str = '',
    idxs: str = '',
    api_key: str = None,
    request: Request = None,
    user=Security(manager, scopes=['write'], use_cache=False)
):
    """
    Upload CSV dataset basically hosted at AWS S3:

    - **url**: CSV file url
    - **idxs**: comma separated fields list for adding database indexes
    - **api_key**: Optional API key for machine-to-machine auth
    """
    # Allow API key auth for internal automation
    if not api_key or api_key != Config.fastapi.get('key', ''):
        if not user:
            return JSONResponse(
                status_code=401,
                content={'error': 'Invalid credentials - provide api_key or Bearer token'}
            )
    if not url:
        return {'error': 'malformed request'}
    
    tbl = CsvDataset.url2fn(url)
    
    # Route CROL to async import (too large for sync driver)
    if tbl == 'crol':
        return await import_crol_async(url)
    
    ds = CsvDataset()
    
    if not ds.download(url):
        # Log failed download
        await log_ingestion(tbl, url, 'fail', error_message='Download failed')
        return {'result': 'fail'}
    
    extraidxs = {
        'crol': '',
        'wegov_orgs': 'type,communityDistrictId,cityCouncilDistrictId',
        '': '',

    }.get(tbl, '')
    req = ds.import_csv(tbl, tbl, ','.join(set([el for el in idxs.split(',') + extraidxs.split(',') if el])))
    
    if not req:
        await log_ingestion(tbl, url, 'fail', error_message='Import failed')
        return JSONResponse(status_code=503, content={'result': 'Fail'})
    
    # Get row count and log success
    try:
        row_count_result = await select(f"SELECT COUNT(*) as cnt FROM {tbl}")
        row_count = row_count_result['rows'][0]['cnt'] if row_count_result.get('rows') else None
    except:
        row_count = None
    
    await log_ingestion(tbl, url, 'success', row_count=row_count)
    
    return {'result': 'OK', 'table': tbl, 'rows': row_count}


async def import_crol_async(url: str):
    """
    Async import for CROL dataset - streams to disk then uses psql COPY.
    Bypasses the sync driver which saturates on large datasets.
    """
    import aiohttp
    import csv
    import asyncpg
    
    try:
        # Stream download to file (avoids loading 600MB into memory)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await log_ingestion('crol', url, 'fail', error_message=f'Download failed: HTTP {response.status}')
                    return JSONResponse(status_code=400, content={'result': 'Fail', 'error': f'Download failed: HTTP {response.status}'})
                
                with open('/tmp/crol_import.csv', 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
        
        # Read header
        with open('/tmp/crol_import.csv', 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
        
        # Dedupe columns
        seen = {}
        clean_cols = []
        for col in header:
            if col in seen:
                seen[col] += 1
                clean_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                clean_cols.append(col)
        
        # Connect to database
        db = await asyncpg.connect(
            user=Config.db['user'],
            password=Config.db['pwd'],
            database=Config.db['dbname'],
            host=Config.db['host']
        )
        
        try:
            # Drop and recreate table
            await db.execute('DROP TABLE IF EXISTS crol')
            col_defs = ', '.join([f'"{col}" TEXT' for col in clean_cols])
            await db.execute(f'CREATE TABLE crol ({col_defs})')
            
            # Stream import in batches
            batch_size = 10000
            batch = []
            total = 0
            
            with open('/tmp/crol_import.csv', 'r') as f:
                reader = csv.reader(f)
                next(reader)  # skip header
                for row in reader:
                    batch.append(tuple(row))
                    if len(batch) >= batch_size:
                        await db.copy_records_to_table('crol', records=batch, columns=clean_cols)
                        total += len(batch)
                        batch = []
                if batch:
                    await db.copy_records_to_table('crol', records=batch, columns=clean_cols)
                    total += len(batch)
            
            # Convert date columns (only if they exist in the CSV)
            for date_col in ['start_date_parsed', 'event_date_parsed']:
                if date_col in clean_cols:
                    try:
                        await db.execute(f"""
                            ALTER TABLE crol 
                            ALTER COLUMN {date_col} TYPE DATE USING CASE 
                                WHEN {date_col} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' THEN {date_col}::DATE 
                                ELSE NULL 
                            END
                        """)
                    except Exception:
                        pass  # Column may have unexpected values
            
            # If event_date_parsed not in CSV, create it from EventDate
            # EventDate format: "MM/DD/YYYY HH:MM:SS AM/PM"
            if 'event_date_parsed' not in clean_cols and 'EventDate' in clean_cols:
                await db.execute('ALTER TABLE crol ADD COLUMN event_date_parsed DATE')
                await db.execute("""
                    UPDATE crol SET event_date_parsed = 
                        TO_DATE(SUBSTRING("EventDate" FROM 1 FOR 10), 'MM/DD/YYYY')
                    WHERE "EventDate" != '' AND length("EventDate") >= 10
                """)

            # Create indexes (only for columns that exist)
            if 'start_date_parsed' in clean_cols:
                await db.execute('CREATE INDEX idx_crol_start_date ON crol(start_date_parsed)')
            # Always create event_date_parsed partial index (only rows with dates)
            # Partial index avoids seq scan on 1M rows when only 16K have event dates
            await db.execute('CREATE INDEX IF NOT EXISTS idx_crol_event_date ON crol(event_date_parsed) WHERE event_date_parsed IS NOT NULL')
            for idx_col, idx_name in [
                ('SectionName', 'idx_crol_section'),
                ('wegov-org-id', 'idx_crol_wegov_org_id'),
            ]:
                if idx_col in clean_cols:
                    await db.execute(f'CREATE INDEX {idx_name} ON crol("{idx_col}")')
            await db.execute('ANALYZE crol')
            
        finally:
            await db.close()
        
        # Cleanup temp file
        import os
        os.remove('/tmp/crol_import.csv')
        
        await log_ingestion('crol', url, 'success', row_count=total)
        return {'result': 'OK', 'table': 'crol', 'rows': total}
        
    except Exception as e:
        await log_ingestion('crol', url, 'fail', error_message=str(e))
        return JSONResponse(status_code=500, content={'result': 'Fail', 'error': str(e)})


async def log_ingestion(table_name: str, s3_url: str, status: str, row_count: int = None, error_message: str = None):
    """Log dataset ingestion to ingestion_log table."""
    try:
        await PostgresModelAsync.execute("""
            INSERT INTO ingestion_log (table_name, s3_url, status, row_count, error_message)
            VALUES ($1, $2, $3, $4, $5)
        """, (table_name, s3_url, status, row_count, error_message))
    except Exception as e:
        print(f"Failed to log ingestion: {e}")


async def update_registry_status(table_name: str, status: str,
                                 row_count: int = None,
                                 error_message: str = None):
    """Reflect an import outcome onto the dataset_registry row.

    Why: /pipeline/dataset-counts (homepage totals + "latest update") and the
    per-row fields in /pipeline/health read last_ingested_at / estimated_rows
    / last_error straight from dataset_registry. The scheduler's socrata and
    extractor paths call update_registry(), but the normalizer→/import-csv
    path never did — so normalizer-driven datasets showed stale counts and
    lingering errors even after a successful refresh. Matches by table_name
    (already lowercased to match the registry); a no-op for tables that
    aren't registered.
    """
    try:
        if status == 'success':
            await PostgresModelAsync.execute(
                """UPDATE dataset_registry
                   SET last_ingested_at = NOW(),
                       estimated_rows = COALESCE($2, estimated_rows),
                       last_error = NULL
                   WHERE table_name = $1""",
                (table_name, row_count))
        else:
            await PostgresModelAsync.execute(
                """UPDATE dataset_registry
                   SET last_error = $2
                   WHERE table_name = $1""",
                (table_name, (error_message or '')[:500]))
    except Exception as e:
        print(f"Failed to update registry status for {table_name}: {e}")


@app.post('/log-ingestion', tags=['Datasets'], summary="Log dataset ingestion (for normalizers)")
async def post_log_ingestion(
    table_name: str,
    status: str = 'success',
    row_count: int = None,
    s3_url: str = None,
    error_message: str = None,
    user=Security(manager, scopes=['write'])
):
    """
    Log a dataset ingestion event. Called by normalizers after successful data import.
    
    - **table_name**: Name of the table that was ingested (e.g., 'crol')
    - **status**: 'success' or 'fail'
    - **row_count**: Number of rows ingested (optional)
    - **s3_url**: Source URL if applicable (optional)
    - **error_message**: Error details if status is 'fail' (optional)
    """
    try:
        await PostgresModelAsync.execute("""
            INSERT INTO ingestion_log (table_name, s3_url, status, row_count, error_message)
            VALUES ($1, $2, $3, $4, $5)
        """, (table_name, s3_url or '', status, row_count, error_message))
        return {'result': 'OK', 'table_name': table_name, 'status': status, 'row_count': row_count}
    except Exception as e:
        return JSONResponse(status_code=500, content={'result': 'Fail', 'error': str(e)})


# Global-search recall/ranking indexes, as (index_name, table, "USING ..." body).
# Single source of truth: /import-csv recreates these after a re-import (tables are
# DROP+CREATEd, which silently wipes every index), and scripts/search_fts_indexes.sql
# backfills the same set once on prod. The to_tsvector('english', col) expressions
# MUST stay byte-identical to the ones in api/routers/search.py so the planner uses
# the GIN index. trgm = substring/typo recall for ILIKE; fts = word-order + stemming.
SEARCH_INDEXES = [
    ("idx_orgs_name_trgm",        "wegov_orgs",            'gin ("name" gin_trgm_ops)'),
    ("idx_orgs_altname_trgm",     "wegov_orgs",            'gin ("alternate_name" gin_trgm_ops)'),
    ("idx_orgs_name_fts",         "wegov_orgs",            "gin (to_tsvector('english', name))"),
    ("idx_orgs_altname_fts",      "wegov_orgs",            "gin (to_tsvector('english', \"alternate_name\"))"),
    ("idx_titles_descr_trgm",     "nyccivilservicetitles", 'gin ("Title Description" gin_trgm_ops)'),
    ("idx_titles_descr_fts",      "nyccivilservicetitles", "gin (to_tsvector('english', \"Title Description\"))"),
    ("idx_contracts_title_trgm",  "contracts",             'gin (contract_title gin_trgm_ops)'),
    ("idx_contracts_vendor_trgm", "contracts",             'gin (vendor_name gin_trgm_ops)'),
    ("idx_contracts_title_fts",   "contracts",             "gin (to_tsvector('english', contract_title))"),
    ("idx_solic_name_trgm",       "solicitations",         'gin ("Procurement Name" gin_trgm_ops)'),
    ("idx_solic_name_fts",        "solicitations",         "gin (to_tsvector('english', \"Procurement Name\"))"),
    ("idx_capproj_desc_trgm",     "capitalprojectslist",   'gin (description gin_trgm_ops)'),
    ("idx_capproj_desc_fts",      "capitalprojectslist",   "gin (to_tsvector('english', description))"),
    ("idx_crol_shorttitle_trgm",  "crol",                  'gin ("ShortTitle" gin_trgm_ops)'),
    ("idx_crol_shorttitle_fts",   "crol",                  "gin (to_tsvector('english', \"ShortTitle\"))"),
    ("idx_schools_name_trgm",     "schoollocations",       'gin (location_name gin_trgm_ops)'),
    ("idx_schools_name_fts",      "schoollocations",       "gin (to_tsvector('english', location_name))"),
    ("idx_cla_name_trgm",         "civillistactive",       'gin ((("First Name" || \' \' || "Last Name")) gin_trgm_ops)'),
    ("idx_gb_name_trgm",          "nycgreenbook",          'gin ((("First Name" || \' \' || "Last Name")) gin_trgm_ops)'),
]


async def _ensure_search_indexes(db, table_name: str):
    """Recreate the global-search GIN indexes for a freshly (re)imported table.

    /import-csv does DROP TABLE + CREATE + COPY, which drops all indexes — without
    this, search silently degrades to seq-scans (e.g. crol's index was missing on
    prod because CROL re-imports daily). Best-effort: a failing index (missing
    column, pg_trgm absent) is logged, never fatal to the import."""
    try:
        await db.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception as exc:  # noqa: BLE001
        logging.warning(f"[import] pg_trgm ensure failed: {exc}")
    for name, tbl, body in SEARCH_INDEXES:
        if tbl != table_name:
            continue
        try:
            await db.execute(f'CREATE INDEX IF NOT EXISTS {name} ON "{tbl}" USING {body}')
        except Exception as exc:  # noqa: BLE001
            logging.warning(f"[import] search index {name} on {tbl} failed: {exc}")


@app.post('/import-csv', tags=['Datasets'], summary="Import CSV dataset (streaming)")
async def import_csv_async(
    url: str,
    table_name: str,
    api_key: str = None,
    request: Request = None
):
    # Allow API key auth for internal automation OR JWT auth
    if api_key and api_key == Config.fastapi['key']:
        pass  # Authorized via API key
    else:
        # Try JWT auth
        try:
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not token:
                return JSONResponse(status_code=401, content={'result': 'Fail', 'error': 'Invalid credentials - provide api_key or Bearer token'})
            user = await manager.get_current_user(token)
            if not user:
                return JSONResponse(status_code=401, content={'result': 'Fail', 'error': 'Invalid credentials'})
        except Exception:
            return JSONResponse(status_code=401, content={'result': 'Fail', 'error': 'Invalid credentials - provide api_key or Bearer token'})

    # Normalise to lowercase so the imported table matches the unquoted
    # names the API uses in SELECT queries (Postgres lowercases unquoted
    # identifiers, but double-quoted names are case-sensitive).
    table_name = table_name.lower()
    """
    Import a CSV file from S3 into a PostgreSQL table using streaming.
    Downloads to disk first, then batch-inserts via COPY to avoid OOM
    on large datasets (1M+ rows like Expense Budget and CROL).
    """
    import aiohttp
    import csv
    import sys
    import os
    csv.field_size_limit(sys.maxsize)
    import asyncpg
    
    tmp_path = f'/tmp/import_{table_name}.csv'
    
    try:
        # Stream download to disk (avoids loading entire CSV into memory)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f'Download failed: HTTP {response.status}'
                    await log_ingestion(table_name, url, 'fail', error_message=err)
                    await update_registry_status(table_name, 'fail', error_message=err)
                    return JSONResponse(status_code=400, content={'result': 'Fail', 'error': f'Failed to download CSV: HTTP {response.status}'})

                with open(tmp_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)

        # Check file is non-empty
        if os.path.getsize(tmp_path) == 0:
            os.remove(tmp_path)
            err = f'S3 file is empty: {url}'
            await log_ingestion(table_name, url, 'fail', error_message=err)
            await update_registry_status(table_name, 'fail', error_message=err)
            return JSONResponse(status_code=400, content={'result': 'Fail', 'error': err})
        
        # Read header and dedupe columns
        with open(tmp_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
        
        seen = {}
        clean_cols = []
        for col in header:
            if col in seen:
                seen[col] += 1
                clean_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                clean_cols.append(col)
        
        # Connect to database
        db = await asyncpg.connect(
            user=Config.db['user'],
            password=Config.db['pwd'],
            database=Config.db['dbname'],
            host=Config.db['host']
        )
        
        try:
            # Drop and recreate table
            await db.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            col_defs = ', '.join([f'"{col}" TEXT' for col in clean_cols])
            await db.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
            
            # Stream import in batches
            batch_size = 10000
            batch = []
            total = 0
            
            with open(tmp_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader)  # skip header
                for row in reader:
                    batch.append(tuple(row))
                    if len(batch) >= batch_size:
                        await db.copy_records_to_table(
                            table_name, records=batch, columns=clean_cols)
                        total += len(batch)
                        batch = []
                if batch:
                    await db.copy_records_to_table(
                        table_name, records=batch, columns=clean_cols)
                    total += len(batch)
            
            # CROL-specific post-processing: date columns and indexes
            if table_name == 'crol':
                for date_col in ['start_date_parsed', 'event_date_parsed']:
                    if date_col in clean_cols:
                        try:
                            await db.execute(f"""
                                ALTER TABLE crol 
                                ALTER COLUMN {date_col} TYPE DATE USING CASE 
                                    WHEN {date_col} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' THEN {date_col}::DATE 
                                    ELSE NULL 
                                END
                            """)
                        except Exception:
                            pass

                if 'event_date_parsed' not in clean_cols and 'EventDate' in clean_cols:
                    await db.execute('ALTER TABLE crol ADD COLUMN event_date_parsed DATE')
                    await db.execute("""
                        UPDATE crol SET event_date_parsed = 
                            TO_DATE(SUBSTRING("EventDate" FROM 1 FOR 10), 'MM/DD/YYYY')
                        WHERE "EventDate" != '' AND length("EventDate") >= 10
                    """)

                if 'start_date_parsed' in clean_cols:
                    await db.execute('CREATE INDEX idx_crol_start_date ON crol(start_date_parsed)')
                await db.execute('CREATE INDEX IF NOT EXISTS idx_crol_event_date ON crol(event_date_parsed) WHERE event_date_parsed IS NOT NULL')
                for idx_col, idx_name in [
                    ('SectionName', 'idx_crol_section'),
                    ('wegov-org-id', 'idx_crol_wegov_org_id'),
                ]:
                    if idx_col in clean_cols:
                        await db.execute(f'CREATE INDEX {idx_name} ON crol("{idx_col}")')
                await db.execute('ANALYZE crol')

            # Refresh planner stats so pg_class.reltuples is accurate
            # immediately. The health dashboard reads reltuples (an estimate)
            # for row counts; after a DROP+CREATE+COPY it is 0 until
            # autoanalyze runs, which briefly flags a freshly-loaded table as
            # "Empty". Running ANALYZE here makes the count correct at once.
            await db.execute(f'ANALYZE "{table_name}"')

            # Rebuild this table's global-search GIN indexes — DROP+CREATE above
            # wiped them. Without this, search degrades to seq-scans after every
            # re-import (no-op for non-searchable tables).
            await _ensure_search_indexes(db, table_name)

            # Log ingestion
            await db.execute("""
                INSERT INTO ingestion_log (table_name, s3_url, status, row_count, error_message)
                VALUES ($1, $2, $3, $4, $5)
            """, table_name, url, 'success', total, None)
            
        finally:
            await db.close()
        
        # Cleanup temp file
        os.remove(tmp_path)
        
        await log_ingestion(table_name, url, 'success', row_count=total)
        await update_registry_status(table_name, 'success', row_count=total)
        return {'result': 'OK', 'table_name': table_name, 'rows': total, 's3_url': url}

    except Exception as e:
        await log_ingestion(table_name, url, 'fail', error_message=str(e))
        await update_registry_status(table_name, 'fail', error_message=str(e))
        # Cleanup on error
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return JSONResponse(status_code=500, content={'result': 'Fail', 'error': str(e)})


@app.get('/ingestion-log', tags=['Datasets'], summary="Get ingestion log")
async def get_ingestion_log(
    table_name: str = None,
    limit: int = 100,
    
):
    """Get ingestion history, optionally filtered by table name."""
    if table_name:
        return await select(
            "SELECT * FROM ingestion_log WHERE table_name = $1 ORDER BY ingested_at DESC LIMIT $2",
            (table_name, limit)
        )
    return await select(
        "SELECT * FROM ingestion_log ORDER BY ingested_at DESC LIMIT $1",
        (limit,)
    )


@app.get('/table-stats', tags=['Datasets'], summary="Get all database table statistics")
async def get_table_stats(
    
):
    """
    Get comprehensive statistics for all database tables including:
    - Row counts (estimated from pg_stat)
    - Table sizes
    - Last ingestion timestamps
    """
    # Get table sizes and estimated row counts using pg_class for better estimates
    table_info = await select("""
        SELECT 
            c.relname as table_name,
            c.reltuples::bigint as estimated_rows,
            pg_size_pretty(pg_total_relation_size(quote_ident(c.relname)::regclass)) as size,
            pg_total_relation_size(quote_ident(c.relname)::regclass) as size_bytes
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' 
          AND c.relkind = 'r'
        ORDER BY pg_total_relation_size(quote_ident(c.relname)::regclass) DESC
    """)
    
    # Get latest ingestion timestamps for each table
    ingestion_info = await select("""
        SELECT DISTINCT ON (table_name) 
            table_name,
            ingested_at,
            row_count as actual_rows,
            status,
            s3_url
        FROM ingestion_log 
        ORDER BY table_name, ingested_at DESC
    """)
    
    # Create lookup for ingestion info
    ingestion_map = {row['table_name']: row for row in ingestion_info.get('rows', [])}
    
    # Merge the data
    result = []
    for table in table_info.get('rows', []):
        table_name = table['table_name']
        ingestion = ingestion_map.get(table_name, {})
        
        # Use actual row count from ingestion if available and recent
        actual_rows = ingestion.get('actual_rows')
        estimated_rows = table.get('estimated_rows', 0)
        
        result.append({
            'table_name': table_name,
            'row_count': actual_rows if actual_rows else estimated_rows,
            'estimated_rows': estimated_rows,
            'size': table.get('size', 'Unknown'),
            'size_bytes': table.get('size_bytes', 0),
            'last_ingested': ingestion.get('ingested_at'),
            'ingestion_status': ingestion.get('status'),
            'source_url': ingestion.get('s3_url'),
        })
    
    return {'rows': result, 'total_tables': len(result)}

# ---- Schools --------

@app.get('/get/schools/sdstats/all', tags=['Schools'])
async def get_schools_global_stats():
    schools_no = await select('SELECT count(*) as res FROM schoollocations')
    students_no = await select('SELECT sum(cast("Org Enroll" as decimal)) as res FROM scaenrollmentcapacity WHERE "Org Enroll" ~ \'^[0-9\\.]+\' AND "Data As Of" = (SELECT max("Data As Of") FROM scaenrollmentcapacity)')
    prj_no = await select('SELECT count(*) as res FROM scaactiveprojects')
    prj_budget = await select('SELECT sum(cast("Project Budget Amount" as decimal)) as res FROM scacapitalprojectschedules WHERE "Project Budget Amount" ~ \'^[0-9\\.]+\'')
    prj_costs = await select('SELECT sum(cast("Total Phase Actual Spending Amount" as decimal)) as res FROM scacapitalprojectschedules WHERE "Total Phase Actual Spending Amount" ~ \'^[0-9\\.]+\'')
    
    s_no = students_no['rows'][0]['res'] or 1
    p_costs = prj_costs['rows'][0]['res'] or 0
    
    return {'rows': [{
        'schools_no': schools_no['rows'][0]['res'],
        'students_no': s_no,
        'prj_no': prj_no['rows'][0]['res'],
        'prj_budget': prj_budget['rows'][0]['res'],
        'prj_costs': p_costs,
        'pcosts_per_student': p_costs / s_no
    }]}

@app.get('/get/schools/all', tags=['Schools'])
async def get_all_schools():
    return await select('SELECT * FROM schoollocations')

@app.get('/get/schools/sdstats/{id}', tags=['Schools'])
async def get_school_district_stats(id: str):
    schools_no = await select('SELECT count(*) as res FROM schoollocations WHERE "Geographical_District_code" = $1', (id,))
    students_no = await select('SELECT sum(cast("Org Enroll" as decimal)) as res FROM scaenrollmentcapacity t1 JOIN schoollocations t2 ON t1."Bldg ID" = t2."location_code" WHERE t2."Geographical_District_code" = $1 AND "Org Enroll" ~ \'^[0-9\\.]+\' AND "Data As Of" = (SELECT max("Data As Of") FROM scaenrollmentcapacity)', (id,))
    prj_no = await select('SELECT count(*) as res FROM scaactiveprojects t1 JOIN schoollocations t2 ON t1."Building ID" = t2."location_code" WHERE t2."Geographical_District_code" = $1', (id,))
    prj_budget = await select('SELECT sum(cast("Project Budget Amount" as decimal)) as res FROM scacapitalprojectschedules t1 JOIN schoollocations t2 ON t1."Project Building Identifier" = t2."location_code" WHERE t2."Geographical_District_code" = $1 AND "Project Budget Amount" ~ \'^[0-9\\.]+\'', (id,))
    prj_costs = await select('SELECT sum(cast("Total Phase Actual Spending Amount" as decimal)) as res FROM scacapitalprojectschedules t1 JOIN schoollocations t2 ON t1."Project Building Identifier" = t2."location_code" WHERE t2."Geographical_District_code" = $1 AND "Total Phase Actual Spending Amount" ~ \'^[0-9\\.]+\'', (id,))
    
    s_no = students_no['rows'][0]['res'] or 1
    p_costs = prj_costs['rows'][0]['res'] or 0
    
    return {'rows': [{
        'schools_no': schools_no['rows'][0]['res'],
        'students_no': s_no,
        'prj_no': prj_no['rows'][0]['res'],
        'prj_budget': prj_budget['rows'][0]['res'],
        'prj_costs': p_costs,
        'pcosts_per_student': p_costs / s_no
    }]}

@app.get('/get/globstats', tags=['General'])
async def get_global_stats():
    total_datasets_no = await select(
        "SELECT count(*) as res FROM dataset_registry WHERE display_name IS NOT NULL")
    total_records_no = await select(
        'SELECT sum(n_live_tup) as res FROM pg_stat_user_tables')
    latest_update = await select(
        "SELECT to_char(max(last_ingested_at), 'MM/DD/YYYY HH24:MI') as res FROM dataset_registry")
    
    return {'rows': [{
        'total_datasets_no': total_datasets_no['rows'][0]['res'],
        'total_records_no': total_records_no['rows'][0]['res'],
        'latest_update': latest_update['rows'][0]['res']
    }]}

@app.get('/get/schools/{id}', tags=['Schools'])
async def get_school_details(id: str):
    return await select('SELECT * FROM schoollocations WHERE "location_code" = $1', (id,))

@app.get('/get/schools/section/{id}/{tbl}', tags=['Schools'])
async def get_school_section(id: str, tbl: str):
    # Map table names to their ID columns
    col_map = {
        'demographics': 'DBN',
        'attendance': 'DBN',
        'scaenrollmentcapacity': 'Bldg ID',
        'temphousing': 'DBN',
        'guidancecounsellors': 'DBN',
        'dohmhinspections': 'BBL',
        'scaactiveprojects': 'Building ID',
        'scacapitalprojectschedules': 'Project Building Identifier',
        'scaschoolprograms': 'Building ID',
        'scacurrentplan': 'Building ID',
        'scaaddedprojects': 'Bldg ID'
    }
    
    if tbl not in col_map:
        raise HTTPException(status_code=404, detail="Table not found or not authorized")
        
    col = col_map[tbl]
    return await select(f'SELECT * FROM {tbl} WHERE "{col}" = $1', (id,))

@app.get('/get/schools/schoolStats/{id}', tags=['Schools'])
async def get_school_stats(id: str):
    # Get system_code for demographics
    school = await select('SELECT "system_code" FROM schoollocations WHERE "location_code" = $1', (id,))
    if not school['rows']:
        return {'rows': []}
    system_code = school['rows'][0]['system_code']

    students_no = await select('SELECT sum(cast("Org Enroll" as decimal)) as res FROM scaenrollmentcapacity WHERE "Bldg ID" = $1 AND "Org Enroll" ~ \'^[0-9\\.]+\' AND "Data As Of" = (SELECT max("Data As Of") FROM scaenrollmentcapacity)', (id,))
    prj_no = await select('SELECT count(*) as res FROM scacapitalprojectschedules WHERE "Project Building Identifier" = $1', (id,))
    prj_budget = await select('SELECT sum(cast("Project Budget Amount" as decimal)) as res FROM scacapitalprojectschedules WHERE "Project Building Identifier" = $1 AND "Project Budget Amount" ~ \'^[0-9\\.]+\'', (id,))
    prj_costs = await select('SELECT sum(cast("Total Phase Actual Spending Amount" as decimal)) as res FROM scacapitalprojectschedules WHERE "Project Building Identifier" = $1 AND "Total Phase Actual Spending Amount" ~ \'^[0-9\\.]+\'', (id,))
    
    # Get latest poverty percentage
    povetry_perc = await select('SELECT "% Poverty" as res FROM demographics WHERE "DBN" = $1 ORDER BY "Year" DESC LIMIT 1', (system_code,))

    s_no = students_no['rows'][0]['res'] or 0
    p_costs = prj_costs['rows'][0]['res'] or 0
    
    return {'rows': [{
        'students_no': s_no,
        'prj_no': prj_no['rows'][0]['res'],
        'prj_budget': prj_budget['rows'][0]['res'],
        'prj_costs': p_costs,
        'pcosts_per_student': p_costs / s_no if s_no > 0 else 0,
        'povetry_perc': povetry_perc['rows'][0]['res'] if povetry_perc['rows'] else 'N/A'
    }]}


# ================ Budget Lines & Capital Projects Extras ================

@app.get('/get/pstats-categories/all', tags=['Capital Projects'])
async def get_pstats_categories_all():
    """Aggregate category stats across all published dates.

    Why: categoriesA.blade.php renders a DataTable expecting pubdate,
    category, fundingsource, year1amount, year10total, prjnum,
    plannedcost, and currcost per row.  Strategy data comes from
    capitalstrategy; project counts and costs come from
    capitalprojectsdollarscomp using the LATEST PUB_DATE, joined
    by category only (STRATEGY_PUB_DATE is too sparse to match).
    """
    return await select("""
        SELECT
            s."Published Date"                          AS pubdate,
            s."Ten-Year Plan Category"                  AS category,
            s."Funding Type"                            AS fundingsource,
            SUM(NULLIF(s."Fiscal Year 1 Amount", '')::BIGINT) AS year1amount,
            SUM(NULLIF(s."Ten-Year Total", '')::BIGINT)       AS year10total,
            COALESCE(p.prjnum, 0)                       AS prjnum,
            COALESCE(p.plannedcost, 0)                  AS plannedcost,
            COALESCE(p.currcost, 0)                     AS currcost
        FROM capitalstrategy s
        LEFT JOIN (
            SELECT
                UPPER("wegov-project-category")         AS cat_upper,
                COUNT(DISTINCT "PROJECT_ID")             AS prjnum,
                COALESCE(SUM("BUDG_ORIG"), 0)::BIGINT AS plannedcost,
                SUM(CASE WHEN "BUDG_CURR" ~ '^-?[0-9.]+$' THEN "BUDG_CURR"::NUMERIC ELSE 0 END)::BIGINT AS currcost
            FROM capitalprojectsdollarscomp
            WHERE "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp WHERE "PUB_DATE" < 20260000)
            GROUP BY UPPER("wegov-project-category")
        ) p ON p.cat_upper = UPPER(s."Ten-Year Plan Category")
        GROUP BY s."Published Date",
                 s."Ten-Year Plan Category",
                 s."Funding Type",
                 p.prjnum, p.plannedcost, p.currcost
        ORDER BY s."Published Date" DESC, s."Ten-Year Plan Category"
    """)

@app.get('/get/pstats-categories/recent', tags=['Capital Projects'])
async def get_pstats_categories_recent():
    """Get pstats-categories for the most recent published date.

    Why: Avoids hardcoding dates in the frontend.
    """
    date_result = await select('SELECT MAX("Published Date") as d FROM capitalstrategy')
    if not date_result.get('rows') or not date_result['rows'][0].get('d'):
        return {'rows': []}
    date = date_result['rows'][0]['d']
    return await get_pstats_categories(date)

@app.get('/get/pstats-categories/{date}', tags=['Capital Projects'])
async def get_pstats_categories(date: str):
    """Same as /all but filtered by published date."""
    return await select("""
        SELECT
            s."Published Date"                          AS pubdate,
            s."Ten-Year Plan Category"                  AS category,
            s."Funding Type"                            AS fundingsource,
            SUM(NULLIF(s."Fiscal Year 1 Amount", '')::BIGINT) AS year1amount,
            SUM(NULLIF(s."Ten-Year Total", '')::BIGINT)       AS year10total,
            COALESCE(p.prjnum, 0)                       AS prjnum,
            COALESCE(p.plannedcost, 0)                  AS plannedcost,
            COALESCE(p.currcost, 0)                     AS currcost
        FROM capitalstrategy s
        LEFT JOIN (
            SELECT
                "STRATEGY_PUB_DATE"                     AS pub_date,
                UPPER("wegov-project-category")         AS cat_upper,
                COUNT(DISTINCT "PROJECT_ID")             AS prjnum,
                SUM("BUDG_ORIG"::BIGINT)                 AS plannedcost,
                SUM(TRIM(REPLACE(NULLIF("BUDG_CURR", ''), ',', '.'))::NUMERIC::BIGINT) AS currcost
            FROM capitalprojectsdollarscomp
            WHERE "STRATEGY_PUB_DATE" = $1
            GROUP BY "STRATEGY_PUB_DATE", UPPER("wegov-project-category")
        ) p ON p.pub_date = s."Published Date"
            AND p.cat_upper = UPPER(s."Ten-Year Plan Category")
        WHERE s."Published Date" = $1
        GROUP BY s."Published Date",
                 s."Ten-Year Plan Category",
                 s."Funding Type",
                 p.prjnum, p.plannedcost, p.currcost
        ORDER BY s."Ten-Year Plan Category"
    """, (date,))

@app.get('/get/capitalbudget/bydate/recent', tags=['Capital Projects'])
async def get_capital_budget_by_date_recent():
    """Get capitalbudget data for the most recent publication date.

    Why: Avoids hardcoding dates in the frontend. Returns all rows
    matching the latest 'Published Date' in the table.
    """
    return await select("""
        SELECT * FROM capitalbudget
        WHERE "Published Date" = (
            SELECT MAX("Published Date") FROM capitalbudget
        )
    """)

@app.get('/get/capitalbudget/bydate/{date}', tags=['Capital Projects'])
async def get_capital_budget_by_date(date: str):
    return await select('SELECT * FROM capitalbudget WHERE "Published Date" = $1', (date,))

@app.get('/get/capitalbudget/{blcode}', tags=['Capital Projects'])
async def get_capital_budget_by_code(blcode: str):
    """Get budget line detail, falling back to capitalcommitmentplan if capitalbudget is empty.

    Why: capitalbudget is a dated dataset that may lack rows for newer budget lines.
    capitalcommitmentplan has current data and similar columns.
    Budget line formats vary: 'AG 0001' (capitalbudget), 'AG-0001'
    (commitments), 'AG0001' (no separator). We normalize and try all.
    """
    import re
    # Generate all format variants from whatever input we get
    stripped = blcode.replace(' ', '').replace('-', '')  # AG0001
    # Insert space after alpha prefix: AG 0001
    spaced = re.sub(r'^([A-Za-z]+)(\w)', r'\1 \2', stripped)
    # Insert dash after alpha prefix: AG-0001
    dashed = re.sub(r'^([A-Za-z]+)(\w)', r'\1-\2', stripped)
    variants = list(dict.fromkeys([blcode, stripped, spaced, dashed]))

    # Try capitalbudget first with all variants
    for v in variants:
        result = await select(
            'SELECT * FROM capitalbudget WHERE "Budget Line" = $1', (v,))
        if result.get('rows'):
            return result

    # Fallback: capitalcommitmentplan with all variants
    for v in variants:
        result = await select("""
            SELECT DISTINCT "Budget Line",
                   "Budget Line Description" AS "Budget Line Title",
                   "Funding Type",
                   "Project Type",
                   "Project Type Description",
                   "Project Type Description" AS "wegov-prjtype-name",
                   "Published Date"
            FROM capitalcommitmentplan
            WHERE "Budget Line" = $1
            ORDER BY "Published Date" DESC
        """, (v,))
        if result.get('rows'):
            return result

    return {"rows": []}

@app.get('/get/budglines_by_prjtype/{tslug}', tags=['Capital Projects'])
async def get_budglines_by_prjtype(tslug: str):
    """Budget lines for a project type, aliased for the blTable DataTable.

    Why: capitalstrategy uses compound codes like 'BR and HB' while
    capitalbudget uses individual codes like 'HB'. We split the compound
    code and match any part.
    """
    return await select("""
        SELECT
            b."Published Date"       AS pubdate,
            b."Budget Line"          AS budgline,
            b."Budget Line Title"    AS budglinename,
            b."Funding Type"         AS ftype,
            b."First Fiscal Year"    AS year1,
            NULLIF(b."Fiscal Year 1 Amount", '')::BIGINT AS year1amount,
            (COALESCE(NULLIF(b."Fiscal Year 1 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(b."Fiscal Year 2 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(b."Fiscal Year 3 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(b."Fiscal Year 4 Amount",'')::BIGINT,0)) AS totalbudgetvalue
        FROM capitalbudget b
        WHERE b."Project Type" IN (
            SELECT TRIM(regexp_split_to_table(
                CASE WHEN LENGTH(s."Project Type") <= 10 THEN s."Project Type"
                     ELSE s."Project Type Description" END,
                ' and '))
            FROM capitalstrategy s
            WHERE LOWER(REGEXP_REPLACE(REPLACE(s."Project Type Description", ' ', '-'), '-+', '-', 'g')) = $1
               OR LOWER(REGEXP_REPLACE(REPLACE(s."Project Type", ' ', '-'), '-+', '-', 'g')) = $1
            GROUP BY s."Project Type", s."Project Type Description"
        )
        ORDER BY b."Published Date" DESC, b."Budget Line"
    """, (tslug,))

@app.get('/get/commitments_by_prjtype/{tslug}', tags=['Capital Projects'])
async def get_commitments_by_prjtype(tslug: str):
    """Commitments for a project type, aliased for the commTable DataTable."""
    return await select("""
        SELECT
            c."Published Date"       AS pubdate,
            c."Budget Line"          AS budgline,
            c."Budget Line Description" AS budglinedesc,
            c."Funding Type"         AS ftype,
            (COALESCE(NULLIF(c."Fiscal Year 1 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(c."Fiscal Year 2 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(c."Fiscal Year 3 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(c."Fiscal Year 4 Amount",'')::BIGINT,0)
           + COALESCE(NULLIF(c."Fiscal Year 5 Amount",'')::BIGINT,0)) AS totalcommvalue,
            c."First Fiscal Year"    AS year1,
            NULLIF(c."Fiscal Year 1 Amount", '')::BIGINT AS year1amount,
            NULLIF(c."Fiscal Year 2 Amount", '')::BIGINT AS year2amount,
            NULLIF(c."Fiscal Year 3 Amount", '')::BIGINT AS year3amount,
            NULLIF(c."Fiscal Year 4 Amount", '')::BIGINT AS year4amount,
            NULLIF(c."Fiscal Year 5 Amount", '')::BIGINT AS year5amount
        FROM capitalcommitmentplan c
        WHERE c."Project Type" IN (
            SELECT TRIM(regexp_split_to_table(
                CASE WHEN LENGTH(s."Project Type") <= 10 THEN s."Project Type"
                     ELSE s."Project Type Description" END,
                ' and '))
            FROM capitalstrategy s
            WHERE LOWER(REGEXP_REPLACE(REPLACE(s."Project Type Description", ' ', '-'), '-+', '-', 'g')) = $1
               OR LOWER(REGEXP_REPLACE(REPLACE(s."Project Type", ' ', '-'), '-+', '-', 'g')) = $1
            GROUP BY s."Project Type", s."Project Type Description"
        )
        ORDER BY c."Published Date" DESC, c."Budget Line"
    """, (tslug,))

@app.get('/get/pstats-records_no-by_prjtype/tblname/{tslug}', tags=['Capital Projects'])
async def get_pstats_records_no_by_prjtype(tslug: str):
    return {'rows': [{'res': 0}]}

@app.get('/get/pstats-records_no-by_prjtype/{tblname}/{tslug}', tags=['Capital Projects'])
async def get_pstats_records_no_by_prjtype_real(tblname: str, tslug: str):
    """Count records for a project type in a specific capital projects table.

    Why: Each table uses a different column for project type. Project type names
    are slugified, so we match by slugifying the column values.
    """
    col_map = {
        'capitalbudget': ('"Project Type Name"', 'slug'),
        'capitalcommitmentplan': ('"Project Type Description"', 'slug'),
        'capitalprojectscommitments': ('projecttype', 'slug'),
        'capitalprojectsdollarscomp': ('"wegov-project-types"', 'ilike'),
        'capitalstrategy': ('"Project Type Description"', 'slug'),
    }
    entry = col_map.get(tblname.lower())
    if not entry:
        return {'rows': [{'res': 0}]}
    col, match_type = entry
    if match_type == 'ilike':
        query = f'SELECT COUNT(*) as res FROM {tblname} WHERE {col} ILIKE $1'
        result = await select(query, (f'%{tslug}%',))
    else:
        query = f"SELECT COUNT(*) as res FROM {tblname} WHERE LOWER(REGEXP_REPLACE(REPLACE({col}, ' ', '-'), '-+', '-', 'g')) = $1"
        result = await select(query, (tslug.lower(),))
    if result.get('rows') and result['rows'][0].get('res', 0) > 0:
        return result
    return {'rows': [{'res': 0}]}

@app.get('/get/capitalprojects/stratcategory/{cslug}', tags=['Capital Projects'])
async def get_capital_projects_stratcategory(cslug: str):
    """Get capital strategy data filtered by category slug."""
    cslug_clean = cslug.replace('-', ' ')
    return await select(
        'SELECT * FROM capitalstrategy '
        'WHERE LOWER(REPLACE("Ten-Year Plan Category", \' \', \'-\')) = $1 '
        'OR LOWER("Ten-Year Plan Category") ILIKE $2',
        (cslug, f'%{cslug_clean}%')
    )

@app.get('/get/capitalprojects/by_category/{cslug}', tags=['Capital Projects'])
async def get_capital_projects_by_category(cslug: str):
    """Get projects for a category from capitalprojectsdollarscomp.

    Why: The category pages need to show all projects in a category,
    not just 10. Matches by the slugified category column.
    """
    return await select(
        'SELECT * FROM capitalprojectsdollarscomp '
        'WHERE LOWER(REPLACE("wegov-project-category", \' \', \'-\')) = $1',
        (cslug.lower(),)
    )

@app.get('/get/pstats-records_no-by_category/tblname/{cslug}', tags=['Capital Projects'])
async def get_pstats_records_no_by_category(cslug: str):
    return {'rows': [{'res': 0}]}

@app.get('/get/pstats-records_no-by_category/{tblname}/{cslug}', tags=['Capital Projects'])
async def get_pstats_records_no_by_category_real(tblname: str, cslug: str):
    """Count records for a category in a specific capital projects table.

    Why: Each table uses a different column for category. Category names
    are slugified, so we match by slugifying column values.
    """
    col_map = {
        'capitalbudget': ('"Ten-Year Plan Category"', 'slug'),
        'capitalcommitmentplan': None,
        'capitalprojectscommitments': None,
        'capitalprojectsdollarscomp': ('"wegov-project-category-slug"', 'exact'),
        'capitalstrategy': ('"Ten-Year Plan Category"', 'slug'),
    }
    entry = col_map.get(tblname.lower())
    if not entry:
        return {'rows': [{'res': 0}]}
    col, match_type = entry
    if match_type == 'exact':
        query = f'SELECT COUNT(*) as res FROM {tblname} WHERE {col} = $1'
        result = await select(query, (cslug,))
    else:
        query = f"SELECT COUNT(*) as res FROM {tblname} WHERE LOWER(REGEXP_REPLACE(REPLACE({col}, ' ', '-'), '-+', '-', 'g')) = $1"
        result = await select(query, (cslug.lower(),))
    if result.get('rows') and result['rows'][0].get('res', 0) > 0:
        return result
    return {'rows': [{'res': 0}]}

@app.get('/get/capitalprojects/by_budgetline/{blcode}', tags=['Capital Projects'])
async def get_capital_projects_by_budgetline(blcode: str):
    """Get projects for a budget line from capitalprojectsdollarscomp.

    Why: capitalbudget uses spaces (AG 0001), capitalprojectsdollarscomp uses
    dashes (AG-0001). We try all format variants to ensure a match.
    """
    import re
    query = 'SELECT * FROM capitalprojectsdollarscomp WHERE "BUDGET_LINE" = $1'
    stripped = blcode.replace(' ', '').replace('-', '')
    spaced = re.sub(r'^([A-Za-z]+)(\w)', r'\1 \2', stripped)
    dashed = re.sub(r'^([A-Za-z]+)(\w)', r'\1-\2', stripped)
    for v in dict.fromkeys([blcode, stripped, spaced, dashed]):
        result = await select(query, (v,))
        if result.get('rows'):
            return result
    return {"rows": []}

@app.get('/get/capitalcommitments/stats_by_budgetline/{blcode}', tags=['Capital Projects'])
async def get_capital_commitments_stats_by_budgetline(blcode: str):
    """Aggregate commitment plan data by Published Date + Funding Type for the OMB chart.

    Why: The budgetLineA template expects grouped stats with comm_no (count) and
    yr1amount-yr5amount (sums). Budget line formats vary across tables (spaces, dashes,
    none), so we try all variants.
    """
    import re
    query = """
        SELECT "Published Date", "Funding Type",
               COUNT(*) as comm_no,
               MIN("First Fiscal Year") as "First Fiscal Year",
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 1 Amount", ''), '0') AS NUMERIC)) as yr1amount,
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 2 Amount", ''), '0') AS NUMERIC)) as yr2amount,
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 3 Amount", ''), '0') AS NUMERIC)) as yr3amount,
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 4 Amount", ''), '0') AS NUMERIC)) as yr4amount,
               SUM(CAST(COALESCE(NULLIF("Fiscal Year 5 Amount", ''), '0') AS NUMERIC)) as yr5amount
        FROM capitalcommitmentplan
        WHERE "Budget Line" = $1
        GROUP BY "Published Date", "Funding Type"
        ORDER BY "Published Date" DESC, "Funding Type"
    """
    stripped = blcode.replace(' ', '').replace('-', '')
    spaced = re.sub(r'^([A-Za-z]+)(\w)', r'\1 \2', stripped)
    dashed = re.sub(r'^([A-Za-z]+)(\w)', r'\1-\2', stripped)
    for v in dict.fromkeys([blcode, stripped, spaced, dashed]):
        result = await select(query, (v,))
        if result.get('rows'):
            return result
    return {"rows": []}

@app.get('/get/commitments/by_budgetline/{blcode}', tags=['Capital Projects'])
async def get_commitments_by_budgetline(blcode: str):
    """Get commitments for a budget line from capitalprojectscommitments.

    Why: The commDatatable in budgetLineA.blade.php expects columns from
    capitalprojectscommitments (maprojid, projectdescription, plancommdate,
    typcname, wegov-org-id, etc.). Adds SQL aliases for normalizer columns
    that the DataTable expects but don't exist in the raw table.
    """
    import re
    query = """SELECT *, typcname AS "wegov-prjtype-name"
               FROM capitalprojectscommitments WHERE budgetline = $1"""
    # Generate all format variants
    stripped = blcode.replace(' ', '').replace('-', '')
    spaced = re.sub(r'^([A-Za-z]+)(\w)', r'\1 \2', stripped)
    dashed = re.sub(r'^([A-Za-z]+)(\w)', r'\1-\2', stripped)
    for v in dict.fromkeys([blcode, stripped, spaced, dashed]):
        result = await select(query, (v,))
        if result.get('rows'):
            return result
    return {"rows": []}

@app.get('/get/pstats-records_no-by_budgetline/tblname/{blcode}', tags=['Capital Projects'])
async def get_pstats_records_no_by_budgetline(blcode: str):
    return [{'res': 0}]

@app.get('/get/pstats-records_no-by_budgetline/{tblname}/{blcode}', tags=['Capital Projects'])
async def get_pstats_records_no_by_budgetline_real(tblname: str, blcode: str):
    """Count records for a budget line in a specific capital projects table.

    Why: Each table uses a different column name for budget line and a different
    format (spaces, dashes, no separator). We map table→column and try all variants.
    """
    import re
    # Map table name to its budget line column
    col_map = {
        'capitalbudget': '"Budget Line"',
        'capitalcommitmentplan': '"Budget Line"',
        'capitalprojectscommitments': 'budgetline',
        'capitalprojectsdollarscomp': '"BUDGET_LINE"',
        'capprojectsbudgetsandschedule': '"BUDGET_LINE"',
        'capprojectsbudgetandspend': '"BUDGET_LINE"',
        'capprojectsbudgetspendhistory': '"BUDGET_LINE"',
        'capprojectsschedulehistory': '"BUDGET_LINE"',
    }
    col = col_map.get(tblname.lower())
    if not col:
        return {'rows': [{'res': 0}]}

    stripped = blcode.replace(' ', '').replace('-', '')
    spaced = re.sub(r'^([A-Za-z]+)(\w)', r'\1 \2', stripped)
    dashed = re.sub(r'^([A-Za-z]+)(\w)', r'\1-\2', stripped)
    for v in dict.fromkeys([blcode, stripped, spaced, dashed]):
        query = f'SELECT COUNT(*) as res FROM {tblname} WHERE {col} = $1'
        result = await select(query, (v,))
        if result.get('rows') and result['rows'][0].get('res', 0) > 0:
            return result
    return {'rows': [{'res': 0}]}

@app.get('/get/capitalcommitmentplan/all', tags=['Capital Projects'])
async def get_capital_commitment_plan_all():
    """Return commitment plan records for the 3 most recent publication dates.

    Why: prjCommitmentsA.blade.php DataTable expects a dataset with
    client-side filtering by Published Date and First Fiscal Year.
    Returning all 57K rows times out, so limit to 3 most recent dates.
    """
    return await select("""
        SELECT * FROM capitalcommitmentplan
        WHERE TRIM("Published Date") IN (
            SELECT DISTINCT TRIM("Published Date")
            FROM capitalcommitmentplan
            ORDER BY TRIM("Published Date") DESC
            LIMIT 3
        )
        ORDER BY "Published Date" DESC, "Budget Line"
    """)

@app.get('/get/capitalcommitmentplan/bydate/recent', tags=['Capital Projects'])
async def get_capital_commitment_plan_recent():
    return await select('SELECT DISTINCT "Published Date" FROM capitalcommitmentplan ORDER BY "Published Date" DESC LIMIT 5')

@app.get('/get/capitalcommitmentplan/bydate/{date}', tags=['Capital Projects'])
async def get_capital_commitment_plan_by_date(date: str):
    return await select('SELECT * FROM capitalcommitmentplan WHERE TRIM("Published Date") = $1', (date,))

@app.get('/get/capitalprojects/taxonomy/all', tags=['Capital Projects'])
async def get_capital_projects_taxonomy_all():
    """Aggregate project types from the Ten-Year Capital Strategy.

    Why: prjTypesA.blade.php DataTable expects pubdate, ptype_name, catnum,
    yr10_total, yr1_amt, plus budget/project columns (blnum, bl_yr4_total,
    cnum, pnum, budg_cost, curr_cost). Strategy data is the primary value;
    budget crossovers are zeroed until a proper ETL join is built.
    """
    return await select("""
        SELECT
            s."Published Date" as pubdate,
            CASE WHEN LENGTH(s."Project Type Description") > LENGTH(s."Project Type")
                 THEN s."Project Type Description"
                 ELSE s."Project Type" END as ptype_name,
            COUNT(DISTINCT s."Ten-Year Plan Category") as catnum,
            CAST(SUM(CAST(NULLIF(s."Ten-Year Total", '') AS NUMERIC)) AS NUMERIC) as yr10_total,
            CAST(SUM(CAST(NULLIF(s."Fiscal Year 1 Amount", '') AS NUMERIC)) AS NUMERIC) as yr1_amt,
            COALESCE(MAX(bl.blnum), 0) as blnum,
            COALESCE(MAX(bl.bl_yr4_total), 0) as bl_yr4_total,
            COALESCE(MAX(cm.cnum), 0) as cnum,
            COALESCE(MAX(p.prjnum), 0) as pnum,
            COALESCE(MAX(p.plannedcost), 0) as budg_cost,
            COALESCE(MAX(p.currcost), 0) as curr_cost
        FROM capitalstrategy s
        LEFT JOIN (
            SELECT
                UNNEST(STRING_TO_ARRAY("wegov-project-type-names", '; ')) AS ptype_name,
                COUNT(DISTINCT "PROJECT_ID") AS prjnum,
                SUM("BUDG_ORIG") AS plannedcost,
                SUM(TRIM(REPLACE(NULLIF("BUDG_CURR", ''), ',', '.'))::NUMERIC) AS currcost
            FROM capitalprojectsdollarscomp
            WHERE "PUB_DATE" = (
                SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp
                WHERE "STRATEGY_PUB_DATE" IS NOT NULL AND "STRATEGY_PUB_DATE" != ''
            )
            GROUP BY ptype_name
        ) p ON p.ptype_name = CASE WHEN LENGTH(s."Project Type Description") > LENGTH(s."Project Type")
                                    THEN s."Project Type Description"
                                    ELSE s."Project Type" END
        LEFT JOIN (
            SELECT
                "Project Type" AS ptype_code,
                COUNT(DISTINCT "Budget Line") AS blnum,
                SUM(
                    COALESCE(NULLIF("Fiscal Year 1 Amount", '')::NUMERIC, 0) +
                    COALESCE(NULLIF("Fiscal Year 2 Amount", '')::NUMERIC, 0) +
                    COALESCE(NULLIF("Fiscal Year 3 Amount", '')::NUMERIC, 0) +
                    COALESCE(NULLIF("Fiscal Year 4 Amount", '')::NUMERIC, 0)
                ) AS bl_yr4_total
            FROM capitalbudget
            WHERE "Published Date" = (SELECT MAX("Published Date") FROM capitalbudget)
            GROUP BY "Project Type"
        ) bl ON bl.ptype_code = CASE WHEN LENGTH(s."Project Type Description") < LENGTH(s."Project Type")
                                     THEN s."Project Type Description"
                                     ELSE s."Project Type" END
        LEFT JOIN (
            SELECT
                "Project Type" AS ptype_code,
                COUNT(*) AS cnum
            FROM capitalcommitmentplan
            WHERE "Published Date" = (SELECT MAX("Published Date") FROM capitalcommitmentplan)
            GROUP BY "Project Type"
        ) cm ON cm.ptype_code = CASE WHEN LENGTH(s."Project Type Description") < LENGTH(s."Project Type")
                                     THEN s."Project Type Description"
                                     ELSE s."Project Type" END
        GROUP BY s."Published Date",
                 CASE WHEN LENGTH(s."Project Type Description") > LENGTH(s."Project Type")
                      THEN s."Project Type Description"
                      ELSE s."Project Type" END
        ORDER BY s."Published Date" DESC, ptype_name
    """)

@app.get('/get/capitalprojects/taxonomy/{date}', tags=['Capital Projects'])
async def get_capital_projects_taxonomy(date: str):
    return await select('SELECT DISTINCT "Project Type" as type, count(*) as count FROM capitalprojectsdollarscomp WHERE "PUB_DATE" = $1 GROUP BY "Project Type" ORDER BY "Project Type"', (date,))

@app.get('/get/pstats-categories_by_type/{tslug}', tags=['Capital Projects'])
async def get_pstats_categories_by_type(tslug: str):
    """Aggregate categories by project type for prjType_a view.

    Why: prjTypeA.blade.php expects pubdate, prjtype, prjtypename, category,
    fundingsource, year1amount, year10total, prjnum, plannedcost, currcost.
    We compute these from capitalstrategy LEFT JOINed to capitalprojectsdollarscomp,
    filtered by project type slug.
    """
    return await select("""
        SELECT
            CASE WHEN LENGTH(s."Project Type") <= 10 THEN s."Project Type"
                 ELSE s."Project Type Description" END AS prjtype,
            CASE WHEN LENGTH(s."Project Type Description") > 10 THEN s."Project Type Description"
                 ELSE s."Project Type" END               AS prjtypename,
            s."Published Date"                          AS pubdate,
            s."Ten-Year Plan Category"                  AS category,
            s."Funding Type"                            AS fundingsource,
            SUM(NULLIF(s."Fiscal Year 1 Amount", '')::BIGINT) AS year1amount,
            SUM(NULLIF(s."Ten-Year Total", '')::BIGINT)       AS year10total,
            COALESCE(p.prjnum, 0)                       AS prjnum,
            COALESCE(p.plannedcost, 0)                  AS plannedcost,
            COALESCE(p.currcost, 0)                     AS currcost
        FROM capitalstrategy s
        LEFT JOIN (
            SELECT
                "STRATEGY_PUB_DATE"                     AS pub_date,
                UPPER("wegov-project-category")         AS cat_upper,
                COUNT(DISTINCT "PROJECT_ID")             AS prjnum,
                SUM("BUDG_ORIG"::BIGINT)                 AS plannedcost,
                SUM(TRIM(REPLACE(NULLIF("BUDG_CURR", ''), ',', '.'))::NUMERIC::BIGINT) AS currcost
            FROM capitalprojectsdollarscomp
            GROUP BY "STRATEGY_PUB_DATE", UPPER("wegov-project-category")
        ) p ON p.pub_date = s."Published Date"
            AND p.cat_upper = UPPER(s."Ten-Year Plan Category")
        WHERE LOWER(REGEXP_REPLACE(REPLACE(s."Project Type Description", ' ', '-'), '-+', '-', 'g')) = $1
           OR LOWER(REGEXP_REPLACE(REPLACE(s."Project Type", ' ', '-'), '-+', '-', 'g')) = $1
        GROUP BY s."Project Type",
                 s."Project Type Description",
                 s."Published Date",
                 s."Ten-Year Plan Category",
                 s."Funding Type",
                 p.prjnum, p.plannedcost, p.currcost
        ORDER BY s."Published Date" DESC, s."Ten-Year Plan Category"
    """, (tslug,))


@app.get('/delete/{tbl}', tags=['Datasets'], summary="Delete dataset", 
        responses={200: {'description': 'Success', 'content': {'application/json': {'example': {'result': 'OK'}}}},
                   404: {'description': 'Failed', 'content': {'application/json': {'example': {'result': 'Not found'}}}}}
         )
def delete_dataset_in_database(tbl:str, user=Security(manager, scopes=['write'])):
    """
    Delete dataset table in database:

    - **tbl**: Table name same as dataset name to delete
    """
    ds = CsvDataset()
    if ds.delete(tbl):
        return {'result': 'OK'}
    else:
        return JSONResponse(status_code=404, content={'result': 'Not found'})

# ================ People Search ================

@app.get('/search/people/{req}/{tbl}', tags=['People'])
async def search_people(req: str, tbl: str):
    """Search for people across multiple datasets.

    Why: The Laravel peoplesearchresults blade expects rows with fullname,
    date, wegov-org-id, wegov-org-name, tbl, and perm-id fields.
    The perm-id must use table prefix + numeric hash (e.g. cl12345)
    because the person controller parses the prefix to determine the table.
    Perm-id is computed in Python to avoid slow SQL MD5 on every row.
    """
    import hashlib
    import re as _re

    search_term = _re.sub(r'\s+', ' ', req.replace('+', ' ')).strip()
    pattern = f'%{search_term}%'

    queries = {
        'civillist': """
            SELECT
                TRIM("EMPLOYEE NAME") AS fullname,
                "CALENDAR YEAR" AS date,
                COALESCE("wegov-org-id", '') AS "wegov-org-id",
                COALESCE("wegov-org-name", '') AS "wegov-org-name",
                'civillist' AS tbl
            FROM civillist
            WHERE "EMPLOYEE NAME" ILIKE $1
            LIMIT 200
        """,
        'civillistactive': """
            SELECT
                TRIM("First Name" || ' ' || "Last Name") AS fullname,
                "Published Date" AS date,
                COALESCE("List Agency Code", '') AS "wegov-org-id",
                COALESCE("List Agency Desc", '') AS "wegov-org-name",
                'civillistactive' AS tbl
            FROM civillistactive
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 200
        """,
        'nycgreenbook': """
            SELECT
                TRIM("First Name" || ' ' || "Last Name") AS fullname,
                '' AS date,
                COALESCE("wegov-org-id", '') AS "wegov-org-id",
                COALESCE("wegov-org-name", '') AS "wegov-org-name",
                'nycgreenbook' AS tbl
            FROM nycgreenbook
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 200
        """,
        'payrolldata': """
            SELECT
                TRIM("First Name" || ' ' || "Last Name") AS fullname,
                COALESCE("Agency Start Date", '') AS date,
                COALESCE("wegov-org-id", '') AS "wegov-org-id",
                COALESCE("wegov-org-name", '') AS "wegov-org-name",
                'payrolldata' AS tbl
            FROM payrolldata
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 200
        """,
    }

    prefixes = {'civillist': 'cl', 'civillistactive': 'cla',
                'nycgreenbook': 'gb', 'payrolldata': 'pr'}

    if tbl == 'all':
        parts = list(queries.values())
    elif tbl in queries:
        parts = [queries[tbl]]
    else:
        return {'rows': []}

    full_query = ' UNION ALL '.join(f'({q})' for q in parts)
    result = await select(full_query, (pattern,))
    rows = result.get('rows', result) if isinstance(result, dict) else result

    # Add perm-id in Python (fast) instead of SQL (slow)
    for row in rows:
        key = f"{row['fullname']}|{row['date']}|{row['wegov-org-name']}|{row['tbl']}"
        h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
        row['perm-id'] = prefixes.get(row['tbl'], 'xx') + str(h)

    return {'rows': rows}


@app.get('/get/people/{pid}', tags=['People'])
async def get_person(pid: str, name: str = ''):
    """Look up a person by their perm-id (prefix + numeric hash).

    Why: The person controller parses the prefix (cl, cla, gb, pr) to
    determine the source table. We use an optional name query param to
    narrow the search, then match the hash for the exact record.
    If no name param, we fall back to scanning more broadly.
    """
    import re
    import hashlib
    m = re.match(r'^(cla|cl|gb|pr)(\d+)$', pid)
    if not m:
        return []
    prefix, uid = m.group(1), m.group(2)

    table_map = {'cl': 'civillist', 'cla': 'civillistactive',
                 'gb': 'nycgreenbook', 'pr': 'payrolldata'}
    tbl = table_map[prefix]

    # Search by name within the specific table (fast ILIKE)
    # If no name provided, we try to extract from referrer or scan broadly
    if name:
        search_name = name.replace('-', ' ').replace('+', ' ').strip()
        pattern = f'%{search_name}%'
    else:
        pattern = '%'  # fallback: broad scan (limited)

    name_queries = {
        'cl': """
            SELECT *
            FROM civillist
            WHERE "EMPLOYEE NAME" ILIKE $1
            LIMIT 500
        """,
        'cla': """
            SELECT *, '' AS "wegov-org-id", "List Agency Desc" AS "wegov-org-name"
            FROM civillistactive
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 500
        """,
        'gb': """
            SELECT * FROM nycgreenbook
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 500
        """,
        'pr': """
            SELECT * FROM payrolldata
            WHERE ("First Name" || ' ' || "Last Name") ILIKE $1
            LIMIT 500
        """,
    }

    result = await select(name_queries[prefix], (pattern,))
    rows = result.get('rows', result) if isinstance(result, dict) else result

    for row in rows:
        if tbl == 'civillist':
            rname = (row.get('EMPLOYEE NAME   ', row.get('EMPLOYEE NAME', ''))).strip()
            key = f"{rname}|{row.get('CALENDAR YEAR', '')}||{tbl}"
        elif tbl == 'civillistactive':
            rname = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
            key = f"{rname}|{row.get('Published Date', '')}|{row.get('List Agency Desc', '')}|{tbl}"
        elif tbl == 'nycgreenbook':
            rname = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
            key = f"{rname}||{row.get('wegov-org-name', '')}|{tbl}"
        else:  # payrolldata
            rname = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
            key = f"{rname}|{row.get('Agency Start Date', '')}|{row.get('wegov-org-name', '')}|{tbl}"

        h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
        if str(h) == uid:
            if tbl == 'civillist':
                row['EMPLOYEE NAME'] = rname
            return {'rows': [row]}

    # Fallback: return first match if hash not found
    if rows:
        row = rows[0]
        if tbl == 'civillist':
            row['EMPLOYEE NAME'] = (row.get('EMPLOYEE NAME   ', row.get('EMPLOYEE NAME', ''))).strip()
        return {'rows': [row]}

    return {'rows': []}


# ================ Chatbot ================

from pydantic import BaseModel
from typing import List, Dict

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

@app.post('/api/chat', tags=['Chatbot'], summary="Chat with AI assistant")
async def chat_with_assistant(request: ChatRequest):
    """
    Chat with the Databook AI assistant.
    The assistant can search organizations, capital projects, contracts, and more.
    
    - **message**: User's message
    - **history**: Optional conversation history
    """
    try:
        from chatbot import chat
        
        # Convert history to the format expected by chatbot
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
        
        # Call the async chat function
        response = await chat(request.message, history)
        
        return {"response": response}
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Chat error: {error_msg}")
        traceback.print_exc()
        
        # Check for rate limit errors and return friendly message
        if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
            return {"response": "I'm temporarily unavailable due to high usage. Try again later or connect the DatabookNYC MCP server to your own AI assistant by following instructions at <a href='https://databook.nyc/mcp' target='_blank'>databook.nyc/mcp</a>."}
        elif "INVALID_ARGUMENT" in error_msg:
            return {"response": "I had trouble processing that request. Please try rephrasing your question."}
        else:
            return {"response": "I encountered an error. Please try again."}


# ================ Newsletter Admin ================

@app.get('/admin/newsletter/preview', tags=['Newsletter'], summary="Preview newsletter HTML")
async def preview_newsletter():
    """
    Generate and preview the weekly newsletter.
    Returns the full HTML that would be sent to subscribers.
    """
    from fastapi.responses import HTMLResponse
    try:
        from newsletter_generator import generate_newsletter
        html = await generate_newsletter()
        return HTMLResponse(content=html)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.post('/admin/newsletter/send', tags=['Newsletter'], summary="Send newsletter")
async def send_newsletter_now(
    test_email: Optional[str] = None,
    user=Security(manager, scopes=['write'])
):
    """
    Send the weekly newsletter.
    
    - **test_email**: If provided, send only to this email (test mode)
    - Without test_email, sends to all subscribers from AirTable
    
    Requires write scope (admin access).
    """
    try:
        from newsletter_generator import generate_newsletter
        from newsletter_sender import send_newsletter
        
        html = await generate_newsletter()
        
        if test_email:
            result = await send_newsletter(html, test_only=True, test_email=test_email)
        else:
            result = await send_newsletter(html)
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.get('/admin/newsletter/validate', tags=['Newsletter'], summary="Validate newsletter links")
async def validate_newsletter_links_endpoint():
    """
    Generate the newsletter and test all links.
    Returns an HTML report showing link status.
    """
    from fastapi.responses import HTMLResponse
    try:
        from newsletter_generator import generate_newsletter
        from newsletter_link_validator import validate_newsletter_links
        
        # Generate newsletter
        html = await generate_newsletter()
        
        # Validate all links
        result = await validate_newsletter_links(html)
        
        return HTMLResponse(content=result["report_html"])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


if __name__ == '__main__':
    Popen(['python', '-m', 'https_redirect'])
    uvicorn.run(
        'main:app', port=443, host='0.0.0.0',
        reload=True, workers=4,
        ssl_keyfile='/etc/letsencrypt/live/databook-api.wegov.nyc/privkey.pem',
        ssl_certfile='/etc/letsencrypt/live/databook-api.wegov.nyc/fullchain.pem')