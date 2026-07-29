#!/bin/bash
# Data-staleness check for the OCE/Checkbook Parquet lakes.
#
# WHY THIS EXISTS
# ---------------
# Every other alarm we have watches a PROCESS ("did the refresh script run? did it
# exit non-zero?"). None of them watches the OUTCOME users actually experience:
# whether the data on the site is current. Those are different failures:
#
#   * A refresh can fail loudly for weeks and — as happened 2026-07-26, when
#     CheckbookNYC's WAF IP-blocked the box — reach nobody, because the Sentry cron
#     monitors were disabled and silently discarded check-ins.
#   * Worse, the Checkbook-dependent crons are now deliberately PAUSED (2026-07-27)
#     until NYC allowlists us, so there is no failing job left to alert on at all.
#     The lake just quietly ages.
#
# This check reads the lake's own mtimes on disk, so it is true regardless of what
# any script did or didn't do — and it needs neither the api container nor Checkbook
# to be reachable.
#
# It reports through BOTH paths, for the reasons each exists:
#   * healthchecks.io: pings success when everything is fresh, /fail when anything is
#     stale. So "check down" literally means "the published data is out of date", and
#     Healthchecks emails on the state CHANGE rather than once a day.
#   * Sentry error event: carries the detail (which domain, how many days) and does
#     not depend on cron monitors. Fingerprinted per domain so repeat days group into
#     one issue instead of spawning a new one daily.
#
# Thresholds sit just above each domain's refresh cadence, so one skipped run is
# tolerated and two are not.
#
# Cron (root, prod CPX41) — daily, mid-day UTC so a failed weekend refresh surfaces
# on Monday rather than mid-run:
#   0 12 * * * /home/ubuntu/databook/scripts/lake-staleness.sh >> /home/ubuntu/databook/scripts/lake-staleness.cron.log 2>&1
#
# Scope note: this measures how fresh OUR COPY is (mtime), not whether the upstream
# source published anything new. A refresh that succeeds but pulls an unchanged
# fiscal year still counts as fresh — correctly, since nothing is broken on our side.
set -uo pipefail

ROOT=/home/ubuntu/databook
DATA=/home/ubuntu/databook-data
LOG="$ROOT/scripts/lake-staleness.log"

log(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
[ -f "$ROOT/.env" ] && . "$ROOT/.env"    # SENTRY_DSN + HC_URL_* (gitignored)

# --- domains: label | path (newest partition for partitioned lakes) | max age days
# Weekly-refreshed lakes get 10 days (7 + slack for one missed Sunday).
# Payroll refreshes monthly, so 40 days (31 + slack).
WEEKLY_MAX=${LAKE_STALE_WEEKLY_DAYS:-10}
MONTHLY_MAX=${LAKE_STALE_MONTHLY_DAYS:-40}

newest_partition(){ ls -td "$1"/fiscal_year=* 2>/dev/null | head -1; }

# --- healthchecks.io ping (see scripts/oce-refresh.sh for the full rationale) -----
HC_URL="${HC_URL_LAKE_STALENESS:-}"
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
    "logger": "lake-staleness",
    "environment": "production",
    "server_name": "databook-prod",
    "transaction": "scripts/lake-staleness.sh",
    "fingerprint": [f"lake-staleness-{fp}"],
    "message": {"formatted": msg},
    "tags": {"job": "lake-staleness", "domain": fp, "alert_source": "staleness-check"},
}))
PYEOF
) || return 0
  curl -s -m 20 -o /dev/null -X POST "https://$host/api/$proj/store/" \
    -H "Content-Type: application/json" \
    -H "X-Sentry-Auth: Sentry sentry_version=7, sentry_client=databook-staleness/1.0, sentry_key=$key" \
    -d "$body" 2>/dev/null || true
}

# Returns 0 when fresh, 1 when stale or missing. Deliberately signals via the EXIT
# CODE rather than stdout: the caller used to capture stdout with $(...), which
# swallowed every per-domain log line so a firing check printed no detail about WHY.
check_one(){   # $1 = label  $2 = path  $3 = max age days
  local label="$1" path="$2" max="$3" mtime age
  if [ -z "$path" ] || [ ! -e "$path" ]; then
    log "  MISSING  $label  (expected at ${path:-<none>})"
    sentry_event "lake-staleness: $label artifact is MISSING (expected ${path:-<none>})" "$label"
    return 1
  fi
  mtime=$(stat -c %Y "$path" 2>/dev/null || echo 0)
  age=$(( ( $(date +%s) - mtime ) / 86400 ))
  if [ "$age" -ge "$max" ]; then
    log "  STALE    $label  ${age}d old (limit ${max}d) — last refreshed $(date -u -d "@$mtime" +%Y-%m-%d)"
    sentry_event "lake-staleness: $label is ${age} days old (limit ${max}) — last refreshed $(date -u -d "@$mtime" +%Y-%m-%d)" "$label"
    return 1
  fi
  log "  ok       $label  ${age}d old (limit ${max}d)"
  return 0
}

log "=== lake staleness check start ==="
STALE=0
for spec in \
  "spending|$(newest_partition "$DATA/spending")|$WEEKLY_MAX" \
  "budget|$DATA/budget/budget.parquet|$WEEKLY_MAX" \
  "revenue|$DATA/revenue/revenue.parquet|$WEEKLY_MAX" \
  "nycha_spending|$(newest_partition "$DATA/nycha_spending")|$WEEKLY_MAX" \
  "nycha_budget|$DATA/nycha_budget/nycha_budget.parquet|$WEEKLY_MAX" \
  "nycha_revenue|$DATA/nycha_revenue/nycha_revenue.parquet|$WEEKLY_MAX" \
  "nycha_contracts|$DATA/nycha_contracts/nycha_contracts.parquet|$WEEKLY_MAX" \
  "payroll|$DATA/payroll/payroll.parquet|$MONTHLY_MAX" \
; do
  IFS='|' read -r label path max <<<"$spec"
  check_one "$label" "$path" "$max" || STALE=$(( STALE + 1 ))
done

if [ "$STALE" -eq 0 ]; then
  log "=== all lakes fresh ==="
  hc_ping success
  exit 0
fi
log "=== $STALE lake(s) STALE or MISSING — data on the site is out of date ==="
hc_ping fail
exit 1
