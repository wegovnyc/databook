#!/bin/bash
# Data-staleness check for the NYC Open Data (Socrata) ingest path.
#
# WHY THIS EXISTS
# ---------------
# scripts/lake-staleness.sh does this job for the Checkbook Parquet lakes. The
# Socrata path — 60 datasets, the bulk of what we publish — had no equivalent, and
# on 2026-07-27 that cost us:
#
#   NYC Open Data dataset jvk9-k4re (DOT street reconstruction projects) was
#   republished EMPTY on 2026-07-01: a full 27-column schema with zero data rows.
#   Our ingest correctly refused it (the row-drop guard) and kept serving the last
#   good 12,056 rows. But every check we had asked "did the script run?" — and a
#   script can run perfectly and ingest nothing. Nobody noticed for 26 DAYS.
#
# So this check asks the two questions the job-level checks cannot:
#
#   A. Are we BEHIND THE SOURCE?  The source published something newer than our last
#      successful ingest, and has stayed ahead for longer than the tolerance. This is
#      the general case — it catches a broken ingest whatever the cause.
#
#   B. Has the SOURCE GONE EMPTY?  The City's own Local Law 251 asset inventory
#      publishes a per-dataset `Row Count`, daily and automatically. We already
#      ingest that inventory (table `locallaw251`), so we can simply read it and
#      flag any dataset we depend on that the City itself reports as having zero
#      rows. This is the check we argued the City should run portal-wide; there is
#      no excuse for not running it over our own dependencies first.
#
# Note what is deliberately NOT an alarm: a source that has not been updated in
# years. Plenty of City datasets are legitimately finished (we ingest several last
# touched in 2019). Staleness AT SOURCE is the City's business. Falling behind a
# source that HAS moved is ours.
#
# Reports through both paths, same rationale as lake-staleness.sh:
#   * healthchecks.io — success/fail so "check down" means "our copy is behind" and
#     Healthchecks emails on the state CHANGE, not once a day.
#   * Sentry error event — carries the detail, fingerprinted per dataset so repeat
#     days group into one issue instead of spawning a new one daily.
#
# Reads Postgres directly rather than the api's /pipeline/health, so its verdict
# holds even when the api container is down.
#
# Cron (root, prod CPX41) — daily, an hour after lake-staleness so the two alarms
# do not arrive interleaved:
#   0 13 * * * /home/ubuntu/databook/scripts/dataset-staleness.sh >> /home/ubuntu/databook/scripts/dataset-staleness.cron.log 2>&1
set -uo pipefail

ROOT=${DATABOOK_ROOT:-/home/ubuntu/databook}
LOG="$ROOT/scripts/dataset-staleness.log"

log(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
[ -f "$ROOT/.env" ] && . "$ROOT/.env"    # SENTRY_DSN + HC_URL_* (gitignored)

# Days a dataset may sit behind its source before we call it stale. The Socrata
# sweep runs daily, so 5 days means four consecutive missed opportunities — well
# clear of a single slow run, well short of a month.
BEHIND_MAX=${DATASET_BEHIND_MAX_DAYS:-5}

psql_q(){   # $1 = SQL -> tab-separated rows on stdout
  docker compose -f "$ROOT/docker-compose.yml" exec -T postgres \
    psql -U postgres -d databook -tAF$'\t' -c "$1" 2>/dev/null
}

# --- healthchecks.io ping --------------------------------------------------------
HC_URL="${HC_URL_DATASET_STALENESS:-}"
hc_ping(){   # $1 = success | fail
  [ -n "$HC_URL" ] || return 0
  local u="$HC_URL"
  [ "$1" = fail ] && u="$u/fail"
  tail -n 40 "$LOG" 2>/dev/null | curl -fsS -m 20 -o /dev/null --data-binary @- "$u" 2>/dev/null || true
}

# --- Sentry error event (independent of cron monitors) ---------------------------
sentry_event(){   # $1 = message  $2 = fingerprint suffix
  [ -n "${SENTRY_DSN:-}" ] || return 0
  local key host proj body
  key=$(echo "$SENTRY_DSN"  | sed -E "s|https://([^@]+)@.*|\1|")
  host=$(echo "$SENTRY_DSN" | sed -E "s|https://[^@]+@([^/]+)/.*|\1|")
  proj=$(echo "$SENTRY_DSN" | sed -E "s|.*/([0-9]+)$|\1|")
  body=$(python3 - "$1" "$2" <<'PYEOF'
import datetime, json, sys, uuid
msg, fp = sys.argv[1], sys.argv[2]
print(json.dumps({
    "event_id": uuid.uuid4().hex,
    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "platform": "other",
    "level": "warning",
    "logger": "dataset-staleness",
    "environment": "production",
    "server_name": "databook-prod",
    "transaction": "scripts/dataset-staleness.sh",
    "fingerprint": [f"dataset-staleness-{fp}"],
    "message": {"formatted": msg},
    "tags": {"job": "dataset-staleness", "dataset": fp, "alert_source": "staleness-check"},
}))
PYEOF
) || return 0
  curl -s -m 20 -o /dev/null -X POST "https://$host/api/$proj/store/" \
    -H "Content-Type: application/json" \
    -H "X-Sentry-Auth: Sentry sentry_version=7, sentry_client=databook-staleness/1.0, sentry_key=$key" \
    -d "$body" 2>/dev/null || true
}

log "=== dataset staleness check start (tolerance ${BEHIND_MAX}d) ==="
PROBLEMS=0

# ── A. Datasets we have fallen behind on ─────────────────────────────────────────
# last_source_updated_at is ahead of last_ingested_at, and has been for > tolerance.
# Never-ingested active datasets are caught by the second OR branch.
BEHIND_SQL="
SELECT table_name,
       COALESCE(socrata_id, '-'),
       COALESCE(to_char(last_ingested_at,      'YYYY-MM-DD'), 'never'),
       COALESCE(to_char(last_source_updated_at,'YYYY-MM-DD'), '-'),
       FLOOR(EXTRACT(EPOCH FROM (NOW() - last_source_updated_at)) / 86400)::int
FROM dataset_registry
WHERE is_active = TRUE
  AND source_type <> 'internal'
  AND last_source_updated_at IS NOT NULL
  AND (last_ingested_at IS NULL OR last_ingested_at < last_source_updated_at)
  AND last_source_updated_at < NOW() - INTERVAL '${BEHIND_MAX} days'
ORDER BY last_source_updated_at;"

BEHIND=$(psql_q "$BEHIND_SQL")
if [ -z "$BEHIND" ]; then
  log "  ok       no dataset is more than ${BEHIND_MAX}d behind its source"
else
  while IFS=$'\t' read -r tbl sid ingested src days; do
    [ -n "$tbl" ] || continue
    log "  BEHIND   $tbl ($sid) — source moved $src, our last ingest $ingested (${days}d behind)"
    sentry_event "dataset-staleness: $tbl ($sid) is ${days} days behind its source — source updated $src, last ingested $ingested" "$tbl"
    PROBLEMS=$(( PROBLEMS + 1 ))
  done <<< "$BEHIND"
fi

# ── B. Sources the City itself reports as empty ──────────────────────────────────
# Read the Local Law 251 inventory we already ingest. Column names arrive raw from
# the City's CSV ("UID", "Row Count"), so discover them rather than hardcoding — if
# the shape changes, skip the check with a notice instead of failing the run.
UID_COL=$(psql_q "SELECT column_name FROM information_schema.columns
                  WHERE table_name = 'locallaw251'
                    AND lower(replace(column_name, ' ', '_')) = 'uid' LIMIT 1")
ROW_COL=$(psql_q "SELECT column_name FROM information_schema.columns
                  WHERE table_name = 'locallaw251'
                    AND lower(replace(column_name, ' ', '_')) = 'row_count' LIMIT 1")

if [ -z "$UID_COL" ] || [ -z "$ROW_COL" ]; then
  log "  notice   locallaw251 inventory not available (uid='${UID_COL:-?}' row_count='${ROW_COL:-?}') — skipping empty-source check"
else
  EMPTY_SQL="
  SELECT r.table_name,
         r.socrata_id,
         COALESCE(r.estimated_rows, 0)
  FROM dataset_registry r
  JOIN locallaw251 l ON l.\"$UID_COL\" = r.socrata_id
  WHERE r.is_active = TRUE
    AND r.socrata_id IS NOT NULL
    AND NULLIF(regexp_replace(COALESCE(l.\"$ROW_COL\", ''), '[^0-9]', '', 'g'), '')::bigint = 0
  ORDER BY r.table_name;"

  EMPTY=$(psql_q "$EMPTY_SQL")
  if [ -z "$EMPTY" ]; then
    log "  ok       no ingested dataset is reported empty by the City's LL251 inventory"
  else
    while IFS=$'\t' read -r tbl sid ours; do
      [ -n "$tbl" ] || continue
      log "  EMPTY@SRC $tbl ($sid) — City inventory reports 0 rows at source; we still serve $ours"
      sentry_event "dataset-staleness: source for $tbl ($sid) reports 0 rows in the City's LL251 inventory — we are still serving $ours rows from the last good ingest" "$tbl-empty-source"
      PROBLEMS=$(( PROBLEMS + 1 ))
    done <<< "$EMPTY"
  fi
fi

if [ "$PROBLEMS" -eq 0 ]; then
  log "=== all ingested datasets are current with their sources ==="
  hc_ping success
  exit 0
fi
log "=== $PROBLEMS dataset problem(s) — see above ==="
hc_ping fail
exit 1
