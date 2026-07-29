#!/usr/bin/env bash
# Rebuild the PASSPort vendor -> NY DOS legal-entity crosswalk.
#
# Runs api/build_dos_crosswalk.py in an ISOLATED container, because the registry
# lives in the nycdb service's 9 GB DuckDB file which the databook api container
# does not mount (and should not — see the module docstring). DuckDB is opened
# read-only, which is safe alongside a running nycdb-api.
#
# Cadence: nycdb refreshes the registry monthly (cron: 1st, 08:30 UTC), so this
# is scheduled a few hours later on the 1st. It cannot be a post-ingest hook on
# `vendors` like the other enrichments, for the mount reason above.
#
# Install (root's crontab):
#   0 12 1 * * /home/ubuntu/databook/scripts/dos-crosswalk-refresh.sh \
#     >> /home/ubuntu/databook/scripts/dos-crosswalk-refresh.log 2>&1
set -euo pipefail

REPO="${REPO:-/home/ubuntu/databook}"
NYCDB_DIR="${NYCDB_DIR:-/opt/nycdb/db}"
NETWORK="${NETWORK:-databook_databook-network}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

if [ ! -f "$NYCDB_DIR/nycdb.duckdb" ]; then
  log "FAIL: $NYCDB_DIR/nycdb.duckdb not found — is the nycdb service installed?"
  exit 1
fi

# Read the DB credentials from the running api container rather than duplicating
# them here; they live in the box's gitignored .env.
eval "$(docker inspect databook-api --format '{{range .Config.Env}}{{println .}}{{end}}' \
        | grep -E '^POSTGRES_(USER|PASSWORD|DB|HOST)=' | sed 's/^/export /')"

log "rebuilding DOS crosswalk"
docker run --rm -m 4g --network "$NETWORK" \
  -v "$NYCDB_DIR:/nycdb:ro" \
  -v "$REPO/api/build_dos_crosswalk.py:/app/build_dos_crosswalk.py:ro" \
  -w /app \
  -e POSTGRES_HOST -e POSTGRES_USER -e POSTGRES_PASSWORD -e POSTGRES_DB \
  databook-api python build_dos_crosswalk.py

# Post-check: the builder swaps in a transaction, so a crash leaves the previous
# table intact — but a run that produced almost nothing is still worth shouting
# about, since the panel would silently empty out across the site.
LINKED=$(docker compose -f "$REPO/docker-compose.yml" exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At \
  -c "SELECT count(*) FROM dos_entity_enrichment WHERE dos_id IS NOT NULL" 2>/dev/null | tr -d '\r')

if [ -z "${LINKED:-}" ] || [ "$LINKED" -lt 10000 ]; then
  log "FAIL: only ${LINKED:-0} linked rows (expected ~15,600)"
  exit 1
fi
log "OK: $LINKED vendors linked to a DOS entity"
