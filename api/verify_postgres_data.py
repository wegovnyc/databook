import asyncio
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from postgrex.asyncmodel import PostgresModelAsync
from config import Config

async def main():
    try:
        table_names = ['vendors', 'contracts', 'solicitations']
        print(f"Checking row counts for: {table_names}")
        
        for table in table_names:
            try:
                res = await PostgresModelAsync.select_safe(f"SELECT count(*) as count FROM {table}")
                count = res[0]['count'] if res else "Error"
                print(f"{table}: {count}")
            except Exception as e:
                print(f"{table}: Error querying - {e}")
                
    except Exception as emain:
        print(f"Main error: {emain}")
    finally:
        await PostgresModelAsync.disconnect()

if __name__ == '__main__':
    # Load config manually if needed or rely on defaults
    Config.load(file='env.yaml')
    asyncio.run(main())
