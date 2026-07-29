#!/bin/bash
# Payroll lake refresh / backfill — kept SEPARATE from oce-refresh.sh because the
# Payroll feed re-pulls ~10M rows/FY (~2 hr each; deep-offset Checkbook pagination),
# far heavier than budget/revenue. Single-file annual-rollup lake
# (/data/payroll/payroll.parquet), built by build_budget_revenue_parquet.py
# (domain "payroll") from extractors/checkbook_payroll.py, which stream-aggregates
# to (agency,title,payroll_type) grain. Fail-safe: build per-FY CSVs, rebuild the
# merged parquet to a temp dir, sanity-check, atomic-swap, restart api, post-check,
# rollback on failure.
#
# Modes:
#   payroll-refresh.sh current                 re-pull current + prior FY, merge (monthly cron)
#   payroll-refresh.sh backfill <START> <END>  pull each FY START..END (inclusive), merge
#
# Cron (root, prod CPX41) — MONTHLY (payroll is heavy + barely restates):
#   0 6 1 * * /home/ubuntu/databook/scripts/payroll-refresh.sh current >> /home/ubuntu/databook/scripts/payroll-refresh.cron.log 2>&1
#
# Backfill (one-time, DETACHED so an SSH drop can't kill it):
#   cd /home/ubuntu/databook && setsid nohup scripts/payroll-refresh.sh backfill 2016 2024 >/dev/null 2>&1 &
set -uo pipefail

MODE="${1:-current}"
ROOT=/home/ubuntu/databook
DATA=/home/ubuntu/databook-data
BUILD="$DATA/_payroll_build"          # per-FY rollup CSVs (retained across runs -> cheap merges)
TMP="$DATA/_payroll_tmp"
LIVE="$DATA/payroll/payroll.parquet"
IMG=databook-api
LOG="$ROOT/scripts/payroll-refresh.log"
HOSTHDR="api.databook.nyc"

log(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
[ -f "$ROOT/.env" ] && . "$ROOT/.env"

# --- Sentry Crons check-in (mirrors oce-refresh{,-nycha}.sh) --------------------
# Without this the monthly cron fails SILENTLY. Only the scheduled `current` mode
# checks in: a manual `backfill` is not the cron job and (at ~3 hr/FY) would blow
# max_runtime and pollute the monitor's history.
# ⚠ Sentry's monitor_config times are MINUTES: max_runtime=720 (12 h) because a
# `current` run re-pulls 2 FYs at ~3 hr each (deep-offset Checkbook pagination),
# vastly longer than the City/NYCHA refreshes.
sentry_checkin(){   # $1 = in_progress|ok|error
  [ "$MODE" = current ] || return 0
  [ -n "${SENTRY_DSN:-}" ] && [ -n "${CHECKIN:-}" ] || return 0
  local key host proj mon sched body
  key=$(echo "$SENTRY_DSN"  | sed -E "s|https://([^@]+)@.*|\1|")
  host=$(echo "$SENTRY_DSN" | sed -E "s|https://[^@]+@([^/]+)/.*|\1|")
  proj=$(echo "$SENTRY_DSN" | sed -E "s|.*/([0-9]+)$|\1|")
  mon="payroll-refresh-monthly"; sched="0 6 1 * *"
  if [ "$1" = in_progress ]; then
    body="{\"check_in_id\":\"$CHECKIN\",\"status\":\"in_progress\",\"environment\":\"production\",\"monitor_config\":{\"schedule\":{\"type\":\"crontab\",\"value\":\"$sched\"},\"checkin_margin\":60,\"max_runtime\":720,\"timezone\":\"UTC\"}}"
  else
    body="{\"check_in_id\":\"$CHECKIN\",\"status\":\"$1\"}"
  fi
  curl -s -m 20 -o /dev/null -X POST "https://$host/api/$proj/cron/$mon/$key/" \
    -H "Content-Type: application/json" -d "$body" 2>/dev/null || true
}
# --- Sentry ERROR EVENT — belt-and-braces alerting ------------------------------
# WHY THIS EXISTS (measured 2026-07-27): the cron check-in above can be silently
# DISCARDED. Sentry accepts the POST and returns success, but if the monitor is
# `disabled` (org cron-monitor quota) the check-in is never recorded. Verified:
# monitors `oce-refresh-weekly`, `oce-refresh-nycha-weekly` and
# `payroll-refresh-selftest` all existed with the correct upserted config yet had
# status=disabled and ZERO recorded check-ins — so when BOTH weekly refreshes
# failed on 2026-07-26 (CheckbookNYC WAF-blocked the box), nothing alerted.
#
# An ordinary error EVENT does not depend on cron monitors at all: it uses the
# error quota, lands in the databook-api issue stream, and therefore shows up in
# the daily Sentry digest. Fixed fingerprint so repeat failures group into one
# issue instead of spamming a new one each week.
sentry_event(){   # $1 = message
  [ -n "${SENTRY_DSN:-}" ] || return 0
  local key host proj body
  key=$(echo "$SENTRY_DSN"  | sed -E "s|https://([^@]+)@.*|\1|")
  host=$(echo "$SENTRY_DSN" | sed -E "s|https://[^@]+@([^/]+)/.*|\1|")
  proj=$(echo "$SENTRY_DSN" | sed -E "s|.*/([0-9]+)$|\1|")
  body=$(python3 - "payroll-refresh" "${MODE:-}" "$1" <<'PYEOF'
import datetime, json, sys, uuid
job, mode, msg = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({
    "event_id": uuid.uuid4().hex,
    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "platform": "other",
    "level": "error",
    "logger": job,
    "environment": "production",
    "server_name": "databook-prod",
    "transaction": f"scripts/{job}.sh",
    "fingerprint": [f"{job}-failure"],
    "message": {"formatted": f"{job} ({mode}) FAILED: {msg}"},
    "tags": {"job": job, "mode": mode, "alert_source": "refresh-script"},
}))
PYEOF
) || return 0
  curl -s -m 20 -o /dev/null -X POST "https://$host/api/$proj/store/" \
    -H "Content-Type: application/json" \
    -H "X-Sentry-Auth: Sentry sentry_version=7, sentry_client=databook-refresh/1.0, sentry_key=$key" \
    -d "$body" 2>/dev/null || true
}
# --- healthchecks.io dead-man's-switch -----------------------------------------
# WHY, on top of Sentry: Sentry Crons monitors sit DISABLED at the org's cron quota
# and a disabled monitor SILENTLY DISCARDS check-ins (measured 2026-07-27: 0
# check-ins ever recorded across 4 monitors, despite every POST returning 202). So
# "this job never ran at all" was detected by nothing. Healthchecks covers exactly
# that on its free tier, and unlike Sentry Crons it retains the ping BODY — so we
# send the tail of this log and the alert arrives WITH the reason. Sentry keeps the
# error-event path (sentry_event) for the "ran and failed" case.
# URL comes from $ROOT/.env (gitignored); unset -> silently skipped.
# ⚠ Gated to `current` for the same reason as sentry_checkin: a manual `backfill`
# is NOT the scheduled monthly job. Pinging this check during a multi-day backfill
# would mark the monthly job healthy out of schedule and (via /start) skew its
# measured duration.
HC_URL="${HC_URL_PAYROLL_REFRESH:-}"
hc_ping(){   # $1 = start | success | fail
  [ "$MODE" = current ] || return 0
  [ -n "$HC_URL" ] || return 0
  local u="$HC_URL"
  case "$1" in start) u="$u/start" ;; fail) u="$u/fail" ;; esac
  if [ "$1" = start ]; then
    curl -fsS -m 15 -o /dev/null "$u" 2>/dev/null || true
  else
    tail -n 40 "$LOG" 2>/dev/null | curl -fsS -m 20 -o /dev/null --data-binary @- "$u" 2>/dev/null || true
  fi
}
fail(){ log "FAILED ($MODE): $*"; sentry_checkin error; sentry_event "$*"; hc_ping fail; exit 1; }
command -v docker >/dev/null || fail "docker not found"

CHECKIN=$(python3 -c "import uuid;print(uuid.uuid4().hex)" 2>/dev/null || echo "")
sentry_checkin in_progress
hc_ping start

# --- determine target FYs ------------------------------------------------------
CLOCK_FY=$(python3 -c "import datetime as d;n=d.datetime.utcnow();print(n.year+1 if n.month>=7 else n.year)")
case "$MODE" in
  current)  FYS="$CLOCK_FY $(( CLOCK_FY - 1 ))" ;;
  backfill) START="${2:-}"; END="${3:-}"; [ -n "$START" ] && [ -n "$END" ] || fail "usage: backfill <start> <end>"
            FYS=$(seq "$END" -1 "$START") ;;
  *) fail "usage: payroll-refresh.sh current | backfill <start> <end>" ;;
esac
mkdir -p "$BUILD" "$DATA/payroll" || fail "mkdir"
log "=== payroll refresh start ($MODE); FYs: $(echo $FYS | tr '\n' ' ')==="

# --- 1) download + roll up each target FY (isolated container) ------------------
SWAPPED=0   # FYs that passed sanity and went live — drives the Sentry outcome
for FY in $FYS; do
  log "downloading + rolling up FY$FY (~10M rows, slow) ..."
  docker run --rm -m 6g --dns 8.8.8.8 -v "$DATA":/data -w /app "$IMG" sh -c "
    python -m extractors.checkbook_payroll --year $FY &&
    [ -s /tmp/payroll_data.csv ] && [ \$(wc -l < /tmp/payroll_data.csv) -gt 1 ] &&
    cp /tmp/payroll_data.csv /data/_payroll_build/payroll_$FY.csv
  " >>"$LOG" 2>&1 && log "  FY$FY rollup CSV written" || log "  FY$FY download FAILED — keeping prior CSV if any"

  # --- 2) rebuild merged parquet from ALL per-FY CSVs -> temp, then atomic swap --
  ls "$BUILD"/payroll_2*.csv >/dev/null 2>&1 || { log "  no payroll CSVs yet — skipping build"; continue; }
  rm -rf "$TMP"; mkdir -p "$TMP"
  docker run --rm -m 6g -v "$DATA":/data -w /app "$IMG" \
    python build_budget_revenue_parquet.py --domain payroll \
    --csv "/data/_payroll_build/payroll_*.csv" --out /data/_payroll_tmp >>"$LOG" 2>&1 \
    || { log "  FY$FY build FAILED — live parquet untouched"; continue; }

  # sanity: temp parquet has rows and a plausible latest-FY total (NYC ~$20-45B/yr)
  ok=$(docker run --rm -v "$DATA":/data -w /app "$IMG" python -c "
import duckdb
try:
    s=\"read_parquet('/data/_payroll_tmp/payroll.parquet')\"
    c=duckdb.connect(); n=c.execute(f'SELECT COUNT(*) FROM {s}').fetchone()[0]
    fy=c.execute(f'SELECT MAX(fiscal_year) FROM {s}').fetchone()[0]
    g=c.execute(f'SELECT COALESCE(SUM(gross),0) FROM {s} WHERE fiscal_year={fy}').fetchone()[0]
    print('ok' if n>0 and 20e9 <= g <= 45e9 else 'bad')
except Exception as e:
    print('bad')
" 2>/dev/null | tail -1)
  if [ "$ok" != "ok" ]; then log "  FY$FY sanity check failed ($ok) — NOT swapping"; continue; fi
  mv "$LIVE" "$LIVE.bak" 2>/dev/null
  mv "$TMP/payroll.parquet" "$LIVE" || { log "  swap FAILED"; [ -f "$LIVE.bak" ] && mv "$LIVE.bak" "$LIVE"; continue; }
  rm -f "$LIVE.bak"
  SWAPPED=$(( SWAPPED + 1 ))
  log "  FY$FY merged + swapped live"
done
rm -rf "$TMP"

# --- 3) restart api so the daily cache picks up the new years, post-check --------
cd "$ROOT" || fail "cd $ROOT"
docker compose restart api >/dev/null 2>&1
# Retry with backoff: the restart clears the api's caches, so the first cold
# /oce/payroll/summary can be slow (mirrors the oce-refresh post-swap checks).
POST_OK=0
for i in $(seq 1 40); do
  curl -sf -m 30 -H "Host: $HOSTHDR" "http://localhost/oce/payroll/summary" 2>/dev/null | grep -q '"available": *true' && { POST_OK=1; log "post-swap check OK"; break; }
  sleep 3
done
[ "$POST_OK" = 1 ] || log "post-swap check FAILED — /oce/payroll/summary never reported available:true"

# Outcome -> Sentry (scheduled `current` runs only). A run that swapped nothing, or
# whose post-check never passed, is an ERROR: the data silently did not advance.
if [ "$SWAPPED" -gt 0 ] && [ "$POST_OK" = 1 ]; then
  sentry_checkin ok
  hc_ping success
  log "=== payroll refresh OK ($MODE); FYs swapped: $SWAPPED ==="
else
  sentry_checkin error
  hc_ping fail
  log "=== payroll refresh FINISHED WITH ERRORS ($MODE); FYs swapped: $SWAPPED, post_ok: $POST_OK ==="
  exit 1
fi
