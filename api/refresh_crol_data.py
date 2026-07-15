import os
import sys
import re

# Ensure we can import modules
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'modules'))

from postgrex import PostgresModel
from postgrex.csvdataset import CsvDataset
from config import Config

def refresh_crol():
    env_path = os.path.join(os.getcwd(), 'env.yaml')
    Config.load(file=env_path)
    Config.env = 'mac'
    # Ensure correct DB config if needed (though Postgrex might handle it if env vars set)
    # Check if we need to force it like in generate_token
    
    print("Connecting to database...")
    db = PostgresModel()
    
    print("Cleaning old CROL data...")
    # Optional: Truncate table to ensure clean slate? Or CsvDataset.import_csv replaces?
    # CsvDataset.import_csv usually appends or fails if primary key conflict? 
    # Let's drop the table to be safe and let import recreate it, assuming schema is inferred from CSV.
    # Wait, if we drop, we lose indexes. 
    # Better to truncate if schema is good.
    # But CsvDataset usually creates table.
    try:
        db.q('DROP TABLE IF EXISTS crol')
        print("Dropped old crol table.")
    except Exception as e:
        print(f"Error dropping table: {e}")

    url = "https://databook2.s3.amazonaws.com/crol"
    print(f"Downloading crol from {url}...")
    
    ds = CsvDataset()
    try:
        ds.download(url)
        # S3 url ends in /crol, so filename is likely 'crol' without extension or with it depending on headers?
        # url2fn might return just 'crol'
        filename = CsvDataset.url2fn(url)
        print(f"Downloaded to {filename}")
        
        print("Importing to DB...")
        # idxs: SectionName,StartDate,EventDate based on our needs
        idxs = 'SectionName,StartDate,EventDate'
        ds.import_csv('crol', filename, idxs)
        print("Import complete.")
        
        ds.delete_file()
        
    except Exception as e:
        print(f"Error during import: {e}")

if __name__ == '__main__':
    refresh_crol()
