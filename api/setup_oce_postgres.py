import asyncio
import os
import sys
import pandas as pd
import io
import requests
import asyncpg
import re
from datetime import datetime

# Adjust path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from config import Config

# S3 Base URL
S3_BASE = "https://databook2.s3.amazonaws.com"

# SQL Schemas
SCHEMAS = {
    "vendors": """
        CREATE TABLE IF NOT EXISTS vendors (
            passport_supplier_id TEXT PRIMARY KEY,
            name TEXT,
            fms_vendor_code TEXT,
            duns_number TEXT,
            certification_type TEXT,
            ethnicity TEXT,
            business_category TEXT,
            corporate_structure TEXT
        );
    """,
    "contracts": """
        CREATE TABLE IF NOT EXISTS contracts (
            ctr_id TEXT,
            epin TEXT,
            contract_id TEXT,
            contract_title TEXT,
            agency TEXT,
            agency_id TEXT,
            vendor_name TEXT,
            program TEXT,
            procurement_method TEXT,
            contract_type TEXT,
            status TEXT,
            award_amount REAL,
            current_amount REAL,
            start_date TEXT,
            end_date TEXT,
            industry TEXT,
            normalized_contract_id TEXT,
            normalized_epin TEXT
        );
    """,
    "solicitations": """
        CREATE TABLE IF NOT EXISTS solicitations (
            rfp_id TEXT,
            bpm_id TEXT,
            program TEXT,
            industry TEXT,
            epin TEXT PRIMARY KEY,
            procurement_name TEXT,
            agency TEXT,
            agency_id TEXT,
            rfx_status TEXT,
            release_date TEXT,
            due_date TEXT,
            main_commodity TEXT,
            procurement_method TEXT,
            normalized_epin TEXT
        );
    """,
    "vendor_entity_summary": """
        CREATE TABLE IF NOT EXISTS vendor_entity_summary (
            vendor_name TEXT,
            address1 TEXT,
            address2 TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            country TEXT,
            telephone TEXT,
            symbol TEXT,
            for_profit TEXT,
            duns TEXT,
            revenue TEXT
        );
    """,
    "vendor_other_names": """
        CREATE TABLE IF NOT EXISTS vendor_other_names (
            vendor_name TEXT,
            type TEXT,
            other_name TEXT,
            from_date TEXT,
            to_date TEXT
        );
    """,
    "vendor_evaluations": """
        CREATE TABLE IF NOT EXISTS vendor_evaluations (
            vendor_name TEXT,
            agency TEXT,
            contract_id TEXT,
            purpose TEXT,
            eval_date TEXT,
            start_date TEXT,
            end_date TEXT,
            rating TEXT
        );
    """,
    "vendor_principals": """
        CREATE TABLE IF NOT EXISTS vendor_principals (
            vendor_name TEXT,
            principal_name TEXT,
            title TEXT,
            ownership_type TEXT
        );
    """,
    "vendor_related_entities": """
        CREATE TABLE IF NOT EXISTS vendor_related_entities (
            vendor_name TEXT,
            related_entity_name TEXT,
            address1 TEXT,
            address2 TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            country TEXT,
            telephone TEXT,
            relationship TEXT
        );
    """
}

# Helpers
def normalize_contract_id(cid):
    if not isinstance(cid, str) or not cid: return None
    return re.sub(r'[^A-Z0-9]', '', cid.upper())

def normalize_epin(epin):
    if not isinstance(epin, str) or not epin: return None
    return re.sub(r'[^A-Z0-9]', '', epin.upper())

def clean_money(val):
    if pd.isna(val) or val == '': return 0.0
    if isinstance(val, (int, float)): return float(val)
    cleaned = re.sub(r'[^0-9.]', '', str(val))
    if not cleaned: return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

async def get_db_connection():
    Config.load(file='env.yaml')
    db_user = os.environ.get('POSTGRES_USER', Config.db.get('user', 'postgres'))
    db_pass = os.environ.get('POSTGRES_PASSWORD', Config.db.get('pwd', 'password'))
    db_host = os.environ.get('POSTGRES_HOST', Config.db.get('host', '127.0.0.1'))
    db_name = os.environ.get('POSTGRES_DB', Config.db.get('dbname', 'databook'))
    
    auth = f"{db_user}:{db_pass}" if db_pass else db_user
    dsn = f"postgresql://{auth}@{db_host}:5432/{db_name}"
    return await asyncpg.connect(dsn)

async def import_data(conn, table_name, url, transform_func=None):
    print(f"Dataset {table_name}: Downloading {url}...")
    try:
        # Bypass SSL verification
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        
        # Read simple CSV first
        # Use python engine or skip bad lines to handle inconsistencies
        df = pd.read_csv(url, dtype=str, on_bad_lines='skip')
        print(f"DEBUG: {table_name} Columns: {list(df.columns)}")
        
        # Fill NaN with None (which becomes NULL in SQL)
        df = df.where(pd.notnull(df), None)
        
        rows = []
        
        if table_name == 'solicitations':
            # Deduplicate by EPIN (Primary Key)
            print(f"DEBUG: {table_name} - Deduplicating by EPIN...")
            df = df.drop_duplicates(subset=['EPIN'], keep='first')

        if transform_func:
            # Apply custom transformation
            for idx, row in df.iterrows():
                t_row = transform_func(row)
                if t_row is not None:
                    rows.append(t_row)
                
                if idx == 0:
                    print(f"DEBUG: {table_name} Sample Transformed: {t_row}")
        else:
            # Generic dump (columns must match schema)
            rows = [tuple(row) for row in df.to_numpy()]
            
        print(f"Dataset {table_name}: Inserting {len(rows)} rows...")
        
        # Determine columns from the schema definition or just rely on exact match
        # Since we use copy_records_to_table, we just need the rows tuple to match schema order
        await conn.copy_records_to_table(table_name, records=rows)
        print(f"Dataset {table_name}: Success.")
        
    except Exception as e:
        print(f"Dataset {table_name}: Failed - {e}")

# Transformers
def transform_vendors(row):
    return (
        row.get("PASSPort Supplier-ID"),
        row.get("Vendor Name"),
        row.get("FMS Vendor Code"),
        row.get("DUNS Number"),
        row.get("Certification Type"),
        row.get("Ethnicity"),
        row.get("Business Category"),
        row.get("Corporate Structure")
    )

def transform_contracts(row):
    cid = row.get("Contract ID")
    epin = row.get("EPIN")
    return (
        row.get("CTR-ID"),
        epin,
        cid,
        row.get("Contract Title"),
        row.get("Agency"), # Agency Name
        row.get("wegov-org-id"), # Agency ID
        row.get("Vendor"),
        row.get("Program"),
        row.get("Procurement Method"),
        row.get("Contract Type"),
        row.get("Status"),
        clean_money(row.get("Award Amount")),
        clean_money(row.get("Current Contract Amount")),
        row.get("Contract Start Date"),
        row.get("Contract End Date"),
        row.get("Industry"),
        normalize_contract_id(cid),
        normalize_epin(epin)
    )

def transform_solicitations(row):
    epin = row.get("EPIN")
    if not epin:
        return None
        
    return (
        row.get("RFP-ID"),
        row.get("BPM-ID"),
        row.get("Program"),
        row.get("Industry"),
        epin,
        row.get("Procurement Name"),
        row.get("Agency"),
        row.get("wegov-org-id"),
        row.get("RFx Status"),
        row.get("Release Date"),
        row.get("Due Date"),
        row.get("Main Commodity"),
        row.get("Procurement Method"),
        normalize_epin(epin)
    )

async def main():
    print("Connecting to Postgres...")
    conn = await get_db_connection()
    
    # 1. Vendors
    await conn.execute("DROP TABLE IF EXISTS vendors CASCADE")
    await conn.execute(SCHEMAS['vendors'])
    await import_data(conn, 'vendors', S3_BASE + "/pre-processed/vendor_data.csv", transform_vendors)
    
    # 2. Contracts (with wegov-org-id normalization)
    await conn.execute("DROP TABLE IF EXISTS contracts CASCADE")
    await conn.execute(SCHEMAS['contracts'])
    await import_data(conn, 'contracts', S3_BASE + "/mocs-contracts.csv", transform_contracts)
    
    # 3. Solicitations (with wegov-org-id normalization)
    await conn.execute("DROP TABLE IF EXISTS solicitations CASCADE")
    await conn.execute(SCHEMAS['solicitations'])
    await import_data(conn, 'solicitations', S3_BASE + "/MOCS_solicitations", transform_solicitations)
    
    # 4. Other tables (Generic/Bulk)
    others = {
        # "vendor_entity_summary": "/pre-processed/passport_entity_summary.csv",
        # "vendor_other_names": "/pre-processed/passport_other_names.csv",
        # "vendor_evaluations": "/pre-processed/passport_performance_evaluation.csv",
        # "vendor_principals": "/pre-processed/passport_principals.csv",
        # "vendor_related_entities": "/pre-processed/passport_related_entities.csv"
    }
    
    for tbl, path in others.items():
        await conn.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
        await conn.execute(SCHEMAS[tbl])
        await import_data(conn, tbl, S3_BASE + path) # Implicit mapping (risky but worked previously for these)

    await conn.close()
    print("Done.")

if __name__ == '__main__':
    asyncio.run(main())
