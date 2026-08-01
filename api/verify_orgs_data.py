
import asyncio
from modules import autoload
from config import Config
from postgrex import PostgresModelAsync

async def main():
    await PostgresModelAsync.connect()
    print("Connected to database.")
    
    # The vocabulary is mixed since the OTI adoption; orgfilter owns it.
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
    from modules import orgfilter
    query = ('SELECT count(*) as count FROM wegov_orgs WHERE "type" IN ('
             + orgfilter.sql_type_list(orgfilter.DIRECTORY_TYPES) + ')')
    print(f"Running query: {query}")
    
    try:
        result = await PostgresModelAsync.select(query)
        count = result['rows'][0]['count']
        print(f"Count of organizations found: {count}")
        
        if count == 0:
            print("WARNING: No organizations found matching the criteria.")
            # Let's check if there are ANY organizations
            all_count = await PostgresModelAsync.select('SELECT count(*) as count FROM wegov_orgs')
            print(f"Total rows in wegov_orgs: {all_count['rows'][0]['count']}")
            
            # Let's check available types
            types = await PostgresModelAsync.select('SELECT DISTINCT "type" FROM wegov_orgs')
            print("Available types in wegov_orgs:")
            for row in types['rows']:
                print(f"- {row['type']}")
                
    except Exception as e:
        print(f"Error executing query: {e}")
        
    await PostgresModelAsync.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
