#!/bin/bash
# CROL Import Script - runs on databook.nyc server
# Downloads CROL from S3 and imports to PostgreSQL

echo "Downloading CROL from S3..."
curl -s "https://databook2.s3.amazonaws.com/crol" -o /tmp/crol.csv
echo "Download complete: $(ls -lh /tmp/crol.csv | awk '{print $5}')"

echo "Copying to postgres container..."
sudo docker cp /tmp/crol.csv databook-postgres:/tmp/crol.csv

echo "Dropping and recreating CROL table..."
sudo docker exec databook-postgres psql -U postgres -d databook -c "DROP TABLE IF EXISTS crol"

# Create table from header
sudo docker exec databook-postgres psql -U postgres -d databook -c "
CREATE TABLE crol (
    \"RequestID\" TEXT,
    \"StartDate\" TEXT,
    \"EndDate\" TEXT,
    \"AgencyName\" TEXT,
    \"TypeOfNoticeDescription\" TEXT,
    \"CategoryDescription\" TEXT,
    \"ShortTitle\" TEXT,
    \"SelectionMethodDescription\" TEXT,
    \"SectionName\" TEXT,
    \"SpecialCaseReasonDescription\" TEXT,
    \"PIN\" TEXT,
    \"DueDate\" TEXT,
    \"AddressToRequest\" TEXT,
    \"ContactName\" TEXT,
    \"ContactPhone\" TEXT,
    \"Email\" TEXT,
    \"ContractAmount\" TEXT,
    \"ContactFax\" TEXT,
    \"AdditionalDescription1\" TEXT,
    \"AdditionalDesctription2\" TEXT,
    \"AdditionalDescription3\" TEXT,
    \"OtherInfo1\" TEXT,
    \"OtherInfo2\" TEXT,
    \"OtherInfo3\" TEXT,
    \"VendorName\" TEXT,
    \"VendorAddress\" TEXT,
    \"Printout1\" TEXT,
    \"Printout2\" TEXT,
    \"Printout3\" TEXT,
    \"DocumentLinks\" TEXT,
    \"EventDate\" TEXT,
    \"EventBuildingName\" TEXT,
    \"EventStreetAddress1\" TEXT,
    \"EventStreetAddress2\" TEXT,
    \"EventCity\" TEXT,
    \"EventStateCode\" TEXT,
    \"EventZipCode\" TEXT,
    \"wegov-org-name\" TEXT,
    \"wegov-org-id\" TEXT,
    start_date_parsed TEXT,
    event_date_parsed TEXT
)"

echo "Importing data via COPY..."
sudo docker exec databook-postgres psql -U postgres -d databook -c "COPY crol FROM '/tmp/crol.csv' WITH (FORMAT csv, HEADER true)"

echo "Converting date columns to DATE type..."
sudo docker exec databook-postgres psql -U postgres -d databook -c "
ALTER TABLE crol 
ALTER COLUMN start_date_parsed TYPE DATE USING CASE 
    WHEN start_date_parsed ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN start_date_parsed::DATE 
    ELSE NULL 
END;
ALTER TABLE crol 
ALTER COLUMN event_date_parsed TYPE DATE USING CASE 
    WHEN event_date_parsed ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN event_date_parsed::DATE 
    ELSE NULL 
END;
"

echo "Creating indexes..."
sudo docker exec databook-postgres psql -U postgres -d databook -c "
CREATE INDEX idx_crol_start_date ON crol(start_date_parsed);
CREATE INDEX idx_crol_event_date ON crol(event_date_parsed);
CREATE INDEX idx_crol_section ON crol(\"SectionName\");
CREATE INDEX idx_crol_wegov_org_id ON crol(\"wegov-org-id\");
ANALYZE crol;
"

echo "Done! Row count:"
sudo docker exec databook-postgres psql -U postgres -d databook -c "SELECT COUNT(*) as rows FROM crol"

# Cleanup
rm -f /tmp/crol.csv
sudo docker exec databook-postgres rm -f /tmp/crol.csv
echo "CROL import complete!"
