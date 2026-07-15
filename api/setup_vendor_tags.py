#!/usr/bin/env python3
"""
Setup vendor_tags table and populate with digital service vendors.
"""
import asyncio
import asyncpg
import os
import sys

sys.path.append('/app/modules')
from config import Config

async def setup():
    Config.load(file='env.yaml')
    db_user = os.environ.get('POSTGRES_USER', Config.db.get('user', 'postgres'))
    db_pass = os.environ.get('POSTGRES_PASSWORD', Config.db.get('pwd', 'password'))
    db_host = os.environ.get('POSTGRES_HOST', Config.db.get('host', '127.0.0.1'))
    db_name = os.environ.get('POSTGRES_DB', Config.db.get('dbname', 'databook'))
    auth = f'{db_user}:{db_pass}' if db_pass else db_user
    dsn = f'postgresql://{auth}@{db_host}:5432/{db_name}'
    
    conn = await asyncpg.connect(dsn)
    
    # Create vendor_tags table
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS vendor_tags (
            id SERIAL PRIMARY KEY,
            vendor_name TEXT NOT NULL,
            tag TEXT NOT NULL,
            classification TEXT,
            description TEXT,
            UNIQUE(vendor_name, tag)
        )
    ''')
    print('Created vendor_tags table')
    
    # Find vendors in contracts with tech-related industry or program
    results = await conn.fetch('''
        SELECT DISTINCT vendor_name, 
               SUM(award_amount) as total_amount,
               COUNT(*) as contract_count
        FROM contracts 
        WHERE (
            industry ILIKE '%technology%' OR 
            industry ILIKE '%information%' OR
            industry ILIKE '%software%' OR
            industry ILIKE '%computer%' OR
            program ILIKE '%technology%' OR
            program ILIKE '%DOITT%' OR
            vendor_name ILIKE '%TECHNOLOGY%' OR
            vendor_name ILIKE '%SOFTWARE%' OR
            vendor_name ILIKE '%SYSTEMS%' OR
            vendor_name ILIKE '%IBM%' OR
            vendor_name ILIKE '%MICROSOFT%' OR
            vendor_name ILIKE '%GOOGLE%' OR
            vendor_name ILIKE '%AMAZON%' OR
            vendor_name ILIKE '%ORACLE%' OR
            vendor_name ILIKE '%ACCENTURE%' OR
            vendor_name ILIKE '%DELOITTE%' OR
            vendor_name ILIKE '%INFOR%' OR
            vendor_name ILIKE '%CGI%' OR
            vendor_name ILIKE '%CISCO%' OR
            vendor_name ILIKE '%DELL%' OR
            vendor_name ILIKE '%SAP%'
        )
        AND vendor_name IS NOT NULL
        GROUP BY vendor_name
        HAVING SUM(award_amount) > 100000
        ORDER BY total_amount DESC
        LIMIT 200
    ''')
    
    print(f'Found {len(results)} tech vendors to add')
    
    # Insert vendors as digital_services
    inserted = 0
    for r in results:
        try:
            await conn.execute('''
                INSERT INTO vendor_tags (vendor_name, tag, classification, description)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (vendor_name, tag) DO NOTHING
            ''', r['vendor_name'], 'digital_services', 'Technology', 'Auto-detected from IT/Technology contracts')
            inserted += 1
        except Exception as e:
            print(f"Error: {e}")
    
    print(f'Inserted {inserted} vendor tags')
    
    count = await conn.fetchval("SELECT COUNT(*) FROM vendor_tags WHERE tag = 'digital_services'")
    print(f'Total digital_services vendors: {count}')
    
    await conn.close()
    print('Done.')

if __name__ == '__main__':
    asyncio.run(setup())
