from __future__ import annotations

"""
Setup script for the Databook data pipeline tables.

Creates the dataset_registry and unmapped_entities tables required
for automated data ingestion, change detection, and monitoring.

Usage:
    python setup_data_pipeline.py               # Setup tables only
    python setup_data_pipeline.py --populate     # Setup + populate from datasets.json
"""

import asyncio
import json
import os
import re
import sys

import asyncpg

# Adjust path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from config import Config


# =============================================================================
# Table Schemas
# =============================================================================

SCHEMAS = {
    "dataset_registry": """
        CREATE TABLE IF NOT EXISTS dataset_registry (
            id SERIAL PRIMARY KEY,
            table_name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            socrata_id TEXT,
            source_url TEXT,
            s3_key TEXT,
            ingestion_mode TEXT DEFAULT 'replace',
            natural_key TEXT,
            needs_normalization BOOLEAN DEFAULT FALSE,
            normalizer_dataset_id INT,
            extractor_script TEXT,
            entity_column TEXT,
            canonical_id_column TEXT,
            category TEXT,
            citation_url TEXT,
            source TEXT,
            section TEXT,
            description TEXT,
            last_source_updated_at TIMESTAMPTZ,
            last_checked_at TIMESTAMPTZ,
            last_ingested_at TIMESTAMPTZ,
            estimated_rows BIGINT,
            table_size TEXT,
            last_error TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """,
    "unmapped_entities": """
        CREATE TABLE IF NOT EXISTS unmapped_entities (
            id SERIAL PRIMARY KEY,
            table_name TEXT NOT NULL,
            entity_column TEXT NOT NULL,
            entity_value TEXT NOT NULL,
            core_dataset TEXT,
            first_seen_at TIMESTAMPTZ DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            resolution_notes TEXT,
            UNIQUE(table_name, entity_column, entity_value)
        );
    """,
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_registry_source_type ON dataset_registry(source_type);",
    "CREATE INDEX IF NOT EXISTS idx_registry_active ON dataset_registry(is_active);",
    "CREATE INDEX IF NOT EXISTS idx_registry_category ON dataset_registry(category);",
    "CREATE INDEX IF NOT EXISTS idx_unmapped_table ON unmapped_entities(table_name);",
    "CREATE INDEX IF NOT EXISTS idx_unmapped_resolved ON unmapped_entities(resolved_at);",
]


# =============================================================================
# Socrata ID Extraction
# =============================================================================

SOCRATA_URL_PATTERN = re.compile(
    r'data\.cityofnewyork\.us/api/views/([a-z0-9]{4}-[a-z0-9]{4})/'
)


def extract_socrata_id(data_url: str) -> str | None:
    """Extract the 4x4 Socrata dataset ID from a data download URL."""
    if not data_url:
        return None
    match = SOCRATA_URL_PATTERN.search(data_url)
    return match.group(1) if match else None


# =============================================================================
# Dataset Classification
# =============================================================================

# Map normalizer output_path to PostgreSQL table name
OUTPUT_PATH_TO_TABLE = {
    "NYCGreenbook.csv": "nycgreenbook",
    "ExpenseBudgetOnNYCOpenData.csv": "expensebudgetonnycopendata",
    "BenefitsAPI.csv": "benefitsapi",
    "AgencyPMI.csv": "agencypmi",
    "NYCJobs.csv": "nycjobs",
    "BudgetRequestsRegister.csv": "budgetrequestsregister",
    "NYCCouncilDiscretionaryFunding.csv": "nyccouncildiscretionaryfunding",
    "facilitydb.csv": "facilitydb",
    "ExpensePlan.csv": "expenseplan",
    "govpublist": "govpublist",
    "govpubrequired": "govpubrequired",
    "locallaw251": "locallaw251",
    "opendatareleasetracker": "opendatareleasetracker",
    "PayrollData.csv": "payrolldata",
    "onenycindicators": "onenycindicators",
    "FTEHeadcount.csv": "fteheadcount",
    "LL18PayandDemo.csv": "ll18payanddemoreport",
    "ft_fte_staff_levels.csv": "ft_fte_staff_levels",
    "schoolLocations.csv": "schoollocations",
    "scaActiveProjects.csv": "scaactiveprojects",
    "crol": "crol",
    "ccmembers": "ccmembers",
    "CapitalProjects.csv": "capitalprojects",
}

# Datasets that grow by appending rows (use incremental mode)
APPEND_DATASETS = {
    "crol": "RequestID",
    "nycjobs": "Job ID",
    "payrolldata": None,  # composite key, use full replace for now
}

# Datasets that need normalizer entity matching
NORMALIZED_DATASETS = {
    "nycgreenbook": {"entity_col": "Agency Name", "id_col": "wegov-org-id"},
    "nycjobs": {"entity_col": "Agency", "id_col": "wegov-org-id"},
    "payrolldata": {"entity_col": "Agency Name", "id_col": "wegov-org-id"},
    "crol": {"entity_col": "AgencyName", "id_col": "wegov-org-id"},
    "expensebudgetonnycopendata": {"entity_col": "Agency Name", "id_col": "wegov-org-id"},
    "facilitydb": {"entity_col": "overagency", "id_col": "wegov-org-id"},
    "budgetrequestsregister": {"entity_col": "Responsible Agency", "id_col": "wegov-org-id"},
    "agencypmi": {"entity_col": "Agency", "id_col": "wegov-org-id"},
    "expenseplan": {"entity_col": "Agency Name", "id_col": "wegov-org-id"},
    # Capital / CPDB datasets
    "capitalprojectscommitments": {"entity_col": "sagencyname", "id_col": "wegov-org-id"},
    "cpdb_projects": {"entity_col": "magencyname", "id_col": "wegov-org-id"},
    "cpdb_commitments": {"entity_col": "sagencyname", "id_col": "wegov-org-id"},
    "capitalcommitmentactuals": {"entity_col": "AGENCY", "id_col": "wegov-org-id"},
    # HR datasets that were missing org enrichment (Sentry: "wegov-org-id" 500s).
    # Names need the normalizer's fuzzy matching — exact joins only cover ~50%.
    "civillistactive": {"entity_col": "List Agency Desc", "id_col": "wegov-org-id"},
    "ll18payanddemo": {"entity_col": "Agency Name", "id_col": "wegov-org-id"},
}

# Category classification based on normalizer tabs
TAB_TO_CATEGORY = {
    "People": "HR/Payroll",
    "Finances": "Budget/Finance",
    "Jobs": "Employment",
    "Services": "Services",
    "Indicators": "Performance",
    "Records and Data": "Records",
    "Education": "Schools",
    "Facilities": "Facilities",
    "Districts": "Districts",
    "Requests": "Community Boards",
    "Organizations": "Reference",
    "Notices": "CROL/Notices",
}


def classify_category(tabs) -> str:
    """Derive a category from the normalizer tab field."""
    if isinstance(tabs, list) and tabs:
        return TAB_TO_CATEGORY.get(tabs[0], "Other")
    if isinstance(tabs, str) and tabs:
        return TAB_TO_CATEGORY.get(tabs, "Other")
    return "Other"


# =============================================================================
# Populate Registry from datasets.json
# =============================================================================

async def populate_from_datasets_json(conn, datasets_json_path: str):
    """
    Parse normalizer datasets.json and insert Socrata datasets into the registry.

    Derives table names, Socrata IDs, categories, normalization requirements,
    and ingestion modes from the existing dataset definitions.
    """
    with open(datasets_json_path, 'r') as f:
        datasets = json.load(f)

    inserted = 0
    skipped = 0

    for ds_id, ds in datasets.items():
        data_url = ds.get('data_url', '')
        socrata_id = extract_socrata_id(data_url)
        output_path = ds.get('output_path', '')
        name = ds.get('name', f'Dataset {ds_id}')

        # Skip datasets without a Socrata URL or output path
        if not socrata_id or not output_path:
            skipped += 1
            continue

        # Derive table name from output path
        table_name = OUTPUT_PATH_TO_TABLE.get(
            output_path,
            output_path.replace('.csv', '').lower()
        )

        # Determine ingestion mode and natural key
        if table_name in APPEND_DATASETS:
            ingestion_mode = 'append'
            natural_key = APPEND_DATASETS[table_name]
        else:
            ingestion_mode = 'replace'
            natural_key = None

        # Determine normalization requirements
        needs_norm = table_name in NORMALIZED_DATASETS
        entity_col = NORMALIZED_DATASETS.get(table_name, {}).get('entity_col')
        id_col = NORMALIZED_DATASETS.get(table_name, {}).get('id_col')

        # Determine S3 key from output_url
        output_url = ds.get('output_url', '')
        s3_key = None
        if 'databook2.s3' in output_url:
            s3_key = output_url.split('databook2.s3.amazonaws.com/')[-1]
        elif 'wegov-research-api.s3' in output_url:
            # Old bucket — will be migrated
            s3_key = output_url.split('wegov-research-api.s3.amazonaws.com/')[-1]

        category = classify_category(ds.get('tab'))

        try:
            await conn.execute("""
                INSERT INTO dataset_registry (
                    table_name, display_name, source_type, socrata_id,
                    source_url, s3_key, ingestion_mode, natural_key,
                    needs_normalization, normalizer_dataset_id,
                    entity_column, canonical_id_column, category, is_active
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                ) ON CONFLICT (table_name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    socrata_id = EXCLUDED.socrata_id,
                    source_url = EXCLUDED.source_url,
                    s3_key = EXCLUDED.s3_key,
                    normalizer_dataset_id = EXCLUDED.normalizer_dataset_id,
                    category = EXCLUDED.category
            """,
                table_name, name, 'socrata', socrata_id,
                data_url, s3_key, ingestion_mode, natural_key,
                needs_norm, int(ds_id),
                entity_col, id_col, category, True
            )
            inserted += 1
            print(f"  ✓ {table_name} ({socrata_id}) — {name}")
        except Exception as e:
            print(f"  ✗ {table_name}: {e}")

    # Add extractor-based datasets manually
    extractor_datasets = [
        ("contracts", "MOCS Contracts", "extractor", None,
         "https://databook2.s3.amazonaws.com/mocs-contracts.csv",
         "mocs-contracts.csv", "append", "contract_id", True,
         None, "download_contracts.py", "Agency", "agency_id",
         "Procurement", True),
        ("solicitations", "MOCS Solicitations", "extractor", None,
         "https://databook2.s3.amazonaws.com/MOCS_solicitations",
         "MOCS_solicitations", "append", "epin", True,
         None, "extract_passport_data.py", "Agency", "agency_id",
         "Procurement", True),
        ("vendors", "PASSPort Vendors", "extractor", None,
         "https://databook2.s3.amazonaws.com/pre-processed/vendor_data.csv",
         "pre-processed/vendor_data.csv", "replace", "passport_supplier_id",
         False, None, "extract_passport_data.py", None, None,
         "Procurement", True),
    ]

    for ds in extractor_datasets:
        try:
            await conn.execute("""
                INSERT INTO dataset_registry (
                    table_name, display_name, source_type, socrata_id,
                    source_url, s3_key, ingestion_mode, natural_key,
                    needs_normalization, normalizer_dataset_id,
                    extractor_script, entity_column, canonical_id_column,
                    category, is_active
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15
                ) ON CONFLICT (table_name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    source_url = EXCLUDED.source_url,
                    extractor_script = EXCLUDED.extractor_script
            """, *ds)
            inserted += 1
            print(f"  ✓ {ds[0]} (extractor) — {ds[1]}")
        except Exception as e:
            print(f"  ✗ {ds[0]}: {e}")

    # Add previously unregistered tables that exist in the database
    await register_untracked_tables(conn)

    print(f"\nPopulated: {inserted} datasets, skipped: {skipped}")


# Table-name → (display_name, source_type, category) for known unregistered tables
UNTRACKED_TABLES = {
    # Internal / system tables
    "users":              ("Users",                    "internal", "System"),
    "wegov_orgs":         ("WeGov Organizations",      "internal", "Reference"),
    "vendor_tags":        ("Vendor Tags",              "internal", "Reference"),
    "data_sources":       ("Data Sources (metadata)",  "internal", "System"),
    # Socrata datasets with known IDs (active)
    "publishedwebsitedata": ("NYC Open Data Plan: Website Data", "socrata", "Reference"),
    "attendance":         ("School Attendance & Chronic Absenteeism", "socrata", "Schools"),
    "ll18payanddemo":     ("LL18 Pay & Demographics",  "socrata",  "HR/Payroll"),
    "positionschedule":   ("Position Schedule",        "socrata",  "HR/Payroll"),
    "capitalstrategy":    ("Ten-Year Capital Strategy", "socrata",  "Budget/Finance"),
    "capitalprojectslist": ("Capital Projects (CPDB)",  "socrata",  "Budget/Finance"),
    "capitalcommitmentplan": ("Capital Commitment Plan", "socrata", "Budget/Finance"),
    "capitalcommitmentactuals": ("Capital Commitment Actuals", "socrata", "Budget/Finance"),
    "cpdb_projects":      ("CPDB Projects (Raw)",      "socrata",  "Budget/Finance"),
    "cpdb_commitments":   ("CPDB Commitments (Raw)",   "socrata",  "Budget/Finance"),
    # External / one-time downloads
    "schoolcampus":       ("School Campus Data",       "extractor", "Schools"),
    "auctions":           ("City Auctions",            "external",  "Procurement"),
    # Dated/retired datasets (will be deactivated below)
    "capitalbudget":      ("Capital Budget",           "socrata",  "Budget/Finance"),
    "capitalprojectsdollarscomp": ("Capital Projects Dollars Comparison", "socrata", "Budget/Finance"),
    "capitalprojectsdollars": ("Capital Project Detail Data - Dollars", "socrata", "Budget/Finance"),
    "capitalprojectsmilestones": ("Capital Projects Milestones", "socrata", "Budget/Finance"),
    "fy2021mmragencyperformance": ("MMR Agency Performance (FY2021)", "socrata", "Performance"),
    "fy2021mmragencyresources":   ("MMR Agency Resources (FY2021)",   "socrata", "Performance"),
    # FDNY Public Safety
    "fire_causes":                ("Fire Causes",                     "socrata", "Public Safety"),
    "fdny_inspections":           ("FDNY Inspections",                "socrata", "Public Safety"),
    "fdny_violations":            ("FDNY Violations",                 "socrata", "Public Safety"),
    "fire_incident_dispatch":     ("Fire Incident Dispatch",          "socrata", "Public Safety"),
}

# Socrata IDs and source URLs for datasets that were missing them
METADATA_CORRECTIONS = {
    "publishedwebsitedata": {"socrata_id": "duz4-2gn9",
        "source_url": "https://data.cityofnewyork.us/api/views/duz4-2gn9/rows.csv?accessType=DOWNLOAD"},
    "positionschedule":     {"socrata_id": "f4wx-5ve6",
        "source_url": "https://data.cityofnewyork.us/api/views/f4wx-5ve6/rows.csv?accessType=DOWNLOAD"},
    "ll18payanddemo":       {"socrata_id": "423i-ukqr",
        "source_url": "https://data.cityofnewyork.us/api/views/423i-ukqr/rows.csv?accessType=DOWNLOAD"},
    "attendance":           {"socrata_id": "gqq2-hgxd",
        "source_url": "https://data.cityofnewyork.us/api/views/gqq2-hgxd/rows.csv?accessType=DOWNLOAD"},
    "capitalstrategy":      {"socrata_id": "b37a-3faw",
        "source_url": "https://data.cityofnewyork.us/api/views/b37a-3faw/rows.csv?accessType=DOWNLOAD"},
    "capitalprojectslist":  {"socrata_id": "fi59-268w",
        "source_url": "https://data.cityofnewyork.us/api/views/fi59-268w/rows.csv?accessType=DOWNLOAD"},
    "capitalbudget":        {"socrata_id": "46m8-77gv",
        "source_url": "https://data.cityofnewyork.us/api/views/46m8-77gv/rows.csv?accessType=DOWNLOAD"},
    "capitalcommitmentplan": {"socrata_id": "2cmn-uidm",
        "source_url": "https://data.cityofnewyork.us/api/views/2cmn-uidm/rows.csv?accessType=DOWNLOAD"},
    "capitalcommitmentactuals": {"socrata_id": "8u85-k342",
        "source_url": "https://data.cityofnewyork.us/api/views/8u85-k342/rows.csv?accessType=DOWNLOAD"},
    "cpdb_projects": {"socrata_id": "fi59-268w",
        "source_url": "https://data.cityofnewyork.us/api/views/fi59-268w/rows.csv?accessType=DOWNLOAD"},
    "cpdb_commitments": {"socrata_id": "djxg-kcfi",
        "source_url": "https://data.cityofnewyork.us/api/views/djxg-kcfi/rows.csv?accessType=DOWNLOAD"},
    "fire_causes": {"socrata_id": "ii3r-svjz",
        "source_url": "https://data.cityofnewyork.us/api/views/ii3r-svjz/rows.csv?accessType=DOWNLOAD"},
    "fdny_inspections": {"socrata_id": "ssq6-fkht",
        "source_url": "https://data.cityofnewyork.us/api/views/ssq6-fkht/rows.csv?accessType=DOWNLOAD"},
    "fdny_violations": {"socrata_id": "bi53-yph3",
        "source_url": "https://data.cityofnewyork.us/api/views/bi53-yph3/rows.csv?accessType=DOWNLOAD"},
    "fire_incident_dispatch": {"socrata_id": "8m42-w767",
        "source_url": "https://data.cityofnewyork.us/api/views/8m42-w767/rows.csv?accessType=DOWNLOAD"},
}

# Datasets that are dated/static and should not be checked for updates
DATED_DATASETS = [
    "capitalbudget",
    "capitalprojectsdollarscomp",
    "capitalprojectsdollars",      # Retired by NYC Oct 2023 (wa2y-rh4b)
    "capitalprojectsmilestones",   # Retired by NYC Oct 2023 (s7yh-frbm)
    "fy2021mmragencyperformance",
    "fy2021mmragencyresources",
    "auctions",
    "websitedata",  # Superseded by publishedwebsitedata
]

# Maps DB table_name → normalizer dataset ID from datasets.json.
# Why: The scheduler uses this to route datasets through the normalizer API.
# Only datasets with entity matching (orgs, districts, etc.) are listed.
NORMALIZER_DATASET_IDS = {
    # Budget / Finance
    "expensebudgetonnycopendata": 2,
    "expenseplan":               31,
    "capitalprojects":           25,
    "capitalprojectsdollars":    196,
    "capitalprojectscommitments": 240,
    "capitalprojectslist":       241,
    "capitalbudget":             213,
    "capitalcommitmentplan":     212,
    "additionalcostsallocation": 195,
    "expenseactualsfunding":     194,
    "headcountactualsfunding":   193,
    # HR / Payroll
    "payrolldata":               68,
    "civillist":                 202,
    "civillistactive":           206,
    "positionschedule":          203,
    "nyccivilservicetitles":     201,
    "ll18payanddemo":            88,
    "fteheadcount":              74,
    "ft_fte_staff_levels":       92,
    "nycjobs":                   5,
    # Performance
    "agencypmi":                 4,
    "resourcesmmr":              289,
    "onenycindicators":          69,
    # Legislative / Government
    "nycgreenbook":              1,
    "ccmembers":                 192,
    "nyccouncildiscretionaryfunding": 7,
    "budgetrequestsregister":    6,
    "councilstatcases":          287,
    "citymeetings":              291,
    # Reference / Open Data
    "benefitsapi":               3,
    "govpublist":                64,
    "govpubrequired":            65,
    "locallaw251":               66,
    "opendatareleasetracker":    67,
    "publishedwebsitedata":      324,
    "websitedata":               285,
    "nyc-agencies-and-governance-organizations": 328,
    # Notices
    "crol":                      191,
    # Facilities / Geography
    "facilitydb":                16,
    "streetandhighwayblock":     198,
    "streetandhighwayintersection": 197,
    # Schools
    "dohmhinspections":          251,
    "demographics":              253,
}


async def register_untracked_tables(conn):
    """Register tables that exist in the DB but aren't in the dataset registry."""
    count = 0
    for table_name, (display_name, source_type, category) in UNTRACKED_TABLES.items():
        try:
            await conn.execute("""
                INSERT INTO dataset_registry (
                    table_name, display_name, source_type, category,
                    ingestion_mode, is_active
                ) VALUES ($1, $2, $3, $4, 'replace', TRUE)
                ON CONFLICT (table_name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    source_type = EXCLUDED.source_type,
                    category = EXCLUDED.category
            """, table_name, display_name, source_type, category)
            count += 1
            print(f"  ✓ {table_name} ({source_type}) — {display_name}")
        except Exception as e:
            print(f"  ✗ {table_name}: {e}")
    print(f"  Registered {count} previously untracked tables")

    # Apply metadata corrections (socrata IDs, source URLs)
    for table_name, corrections in METADATA_CORRECTIONS.items():
        try:
            await conn.execute("""
                UPDATE dataset_registry
                SET socrata_id = $2, source_url = $3
                WHERE table_name = $1
            """, table_name, corrections['socrata_id'], corrections['source_url'])
            print(f"  ✓ {table_name} → socrata_id={corrections['socrata_id']}")
        except Exception as e:
            print(f"  ✗ {table_name} metadata: {e}")

    # Datasets that should bypass the external normalizer and import
    # directly from Socrata (with post_normalize self-join backfill).
    # Why: The normalizer at normalize.databook.nyc is behind Cloudflare,
    # which blocks API requests. These datasets use the direct Socrata
    # import path instead, with entity mapping via self-join.
    DIRECT_SOCRATA_OVERRIDE = {
        'nycjobs', 'fire_causes', 'fdny_inspections', 'fdny_violations', 'fire_incident_dispatch'
    }

    # Populate normalizer_dataset_id for datasets requiring normalization
    norm_count = 0
    for table_name, norm_id in NORMALIZER_DATASET_IDS.items():
        try:
            needs_norm = table_name not in DIRECT_SOCRATA_OVERRIDE
            result = await conn.execute("""
                UPDATE dataset_registry
                SET normalizer_dataset_id = $2, needs_normalization = $3
                WHERE table_name = $1
            """, table_name, norm_id, needs_norm)
            if "UPDATE 1" in result:
                norm_count += 1
                if not needs_norm:
                    print(f"  ⚡ {table_name}: direct Socrata (normalizer bypassed)")
        except Exception as e:
            print(f"  ✗ {table_name} normalizer_id: {e}")
    print(f"  Set normalizer_dataset_id for {norm_count} datasets")

    # Deactivate duplicate raw passport tables (superseded by extractor entries)
    dupes = ['passport', 'passport_contracts', 'passport_solicitations']
    await conn.execute("""
        UPDATE dataset_registry SET is_active = FALSE
        WHERE table_name = ANY($1::text[])
    """, dupes)
    print(f"  Deactivated {len(dupes)} duplicate passport tables")

    # Deactivate dated/static datasets
    await conn.execute("""
        UPDATE dataset_registry SET is_active = FALSE
        WHERE table_name = ANY($1::text[])
    """, DATED_DATASETS)
    print(f"  Deactivated {len(DATED_DATASETS)} dated/static datasets")

    # Ensure the PP→FB crosswalk table exists.
    # Why: The dispatch enrichment hook (enrich_dispatch_hook) needs this
    # pre-computed mapping to assign battalion_ids to dispatch records.
    # The crosswalk is derived from polygon intersections between
    # pp.geojson and fb.geojson — it only changes if district boundaries
    # are redrawn, so it's safe to create once and leave.
    crosswalk_exists = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'pp_fb_crosswalk')")
    if crosswalk_exists:
        print("  ✓ pp_fb_crosswalk table already exists")
    else:
        print("  ⚠️  pp_fb_crosswalk missing — creating from GeoJSON...")
        try:
            import requests as _req
            from shapely.geometry import shape as _shape
            from shapely import STRtree as _STRtree

            fb_gj = _req.get('https://map.databook.nyc/data/fb.geojson',
                             timeout=30).json()
            pp_gj = _req.get('https://map.databook.nyc/data/pp.geojson',
                             timeout=30).json()

            fb_polys = [_shape(f['geometry']) for f in fb_gj['features']]
            fb_ids = [f['properties']['nameCol'] for f in fb_gj['features']]
            tree = _STRtree(fb_polys)

            await conn.execute(
                "CREATE TABLE pp_fb_crosswalk "
                "(pp_id TEXT PRIMARY KEY, fb_ids TEXT[])")
            for feat in pp_gj['features']:
                pp_id = feat['properties']['nameCol']
                pp_geom = _shape(feat['geometry'])
                hits = tree.query(pp_geom)
                matching = [fb_ids[i] for i in hits
                            if fb_polys[i].intersects(pp_geom)]
                if matching:
                    await conn.execute(
                        "INSERT INTO pp_fb_crosswalk VALUES ($1, $2)",
                        pp_id, sorted(matching))
            cnt = await conn.fetchval(
                "SELECT count(*) FROM pp_fb_crosswalk")
            print(f"  ✓ Created pp_fb_crosswalk with {cnt} rows")
        except Exception as e:
            print(f"  ✗ pp_fb_crosswalk creation failed: {e}")


async def sync_table_stats(conn):
    """
    Pull live row counts and table sizes from PostgreSQL into the registry.

    Why: Keeps the registry in sync with actual DB state without requiring
    a separate table-stats query. Runs as a maintenance task.
    """
    print("\nSyncing table stats from PostgreSQL...")
    updated = 0
    rows = await conn.fetch("""
        SELECT r.table_name
        FROM dataset_registry r
        JOIN information_schema.tables t
          ON t.table_name = r.table_name AND t.table_schema = 'public'
    """)
    for row in rows:
        tn = row['table_name']
        try:
            stats = await conn.fetchrow("""
                SELECT pg_size_pretty(pg_total_relation_size(quote_ident($1))) as size,
                       (SELECT reltuples::bigint FROM pg_class WHERE relname = $1) as rows
            """, tn)
            if stats:
                await conn.execute("""
                    UPDATE dataset_registry
                    SET estimated_rows = $2, table_size = $3
                    WHERE table_name = $1
                """, tn, stats['rows'], stats['size'])
                updated += 1
        except Exception as e:
            print(f"  ✗ {tn}: {e}")
    print(f"  Updated stats for {updated} tables")


# =============================================================================
# Main
# =============================================================================

async def get_db_connection():
    """Connect to PostgreSQL using project config."""
    Config.load(file='env.yaml')
    db_user = os.environ.get('POSTGRES_USER', Config.db.get('user', 'postgres'))
    db_pass = os.environ.get('POSTGRES_PASSWORD', Config.db.get('pwd', 'password'))
    db_host = os.environ.get('POSTGRES_HOST', Config.db.get('host', '127.0.0.1'))
    db_name = os.environ.get('POSTGRES_DB', Config.db.get('dbname', 'databook'))

    auth = f"{db_user}:{db_pass}" if db_pass else db_user
    dsn = f"postgresql://{auth}@{db_host}:5432/{db_name}"
    return await asyncpg.connect(dsn)


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Set up Databook data pipeline tables"
    )
    parser.add_argument(
        '--populate', action='store_true',
        help='Populate registry from normalizer datasets.json'
    )
    parser.add_argument(
        '--sync-stats', action='store_true',
        help='Sync row counts and table sizes from PostgreSQL'
    )
    parser.add_argument(
        '--datasets-json',
        default=os.path.expanduser(
            '~/Antigravity/Databook Pipeline/normalizer/data/datasets.json'
        ),
        help='Path to normalizer datasets.json'
    )
    args = parser.parse_args()

    print("Connecting to PostgreSQL...")
    conn = await get_db_connection()

    try:
        print("Creating tables...")
        for name, schema in SCHEMAS.items():
            await conn.execute(schema)
            print(f"  ✓ {name}")

        # Ensure new columns exist (migration for existing installs)
        for col in ['table_size TEXT', 'citation_url TEXT', 'source TEXT',
                     'section TEXT', 'description TEXT']:
            try:
                await conn.execute(
                    f"ALTER TABLE dataset_registry ADD COLUMN IF NOT EXISTS {col}")
            except Exception:
                pass

        print("Creating indexes...")
        for idx_sql in INDEXES:
            await conn.execute(idx_sql)
        print("  ✓ All indexes created")

        if args.populate:
            if not os.path.exists(args.datasets_json):
                print(f"Error: {args.datasets_json} not found")
                return
            print(f"\nPopulating registry from {args.datasets_json}...")
            await populate_from_datasets_json(conn, args.datasets_json)

        if args.sync_stats or args.populate:
            await sync_table_stats(conn)

    finally:
        await conn.close()

    print("\nDone.")


if __name__ == '__main__':
    asyncio.run(main())
