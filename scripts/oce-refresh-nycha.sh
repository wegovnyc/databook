#!/bin/bash
# NYCHA lake refresh — weekly companion to oce-refresh.sh (kept separate so a bug
# here can never break the City refresh, and vice-versa). Same fail-safe pattern:
# build in ISOLATED docker-run containers -> validate (>50% guard) -> atomic swap
# -> api restart -> live-check -> rollback on failure -> Sentry Crons check-in.
#
# Refreshes the 4 NYCHA domains (data starts FY2018):
#   budget / revenue / contracts — single-file domains: re-pull current + 2 prior
#     FYs and --merge older years from the live Parquet (build_budget_revenue_parquet).
#   spending — partitioned lake: rebuild the current + prior FY partitions
#     (build_nycha_spending_parquet), like the City spending lake.
#
# ⚠ NYCHA spending re-pulls ~5-6M rows/run — this is the heavy part. If the weekly
# load is undesirable, move THIS cron to monthly (the City oce-refresh stays weekly).
#
# Cron (root, prod CPX41):
#   0 5 * * 0 /home/ubuntu/databook/scripts/oce-refresh-nycha.sh weekly >> /home/ubuntu/databook/scripts/oce-refresh-nycha.cron.log 2>&1
set -uo pipefail

MODE="${1:-weekly}"
ROOT=/home/ubuntu/databook
DATA=/home/ubuntu/databook-data
BUILD="$DATA/_refresh_build_nycha"
IMG=databook-api
LOG="$ROOT/scripts/oce-refresh-nycha.log"
HOSTHDR="api.databook.nyc"
MIN_RATIO=50

log(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
[ -f "$ROOT/.env" ] && . "$ROOT/.env"

sentry_checkin(){   # $1 = in_progress|ok|error
  [ -n "${SENTRY_DSN:-}" ] && [ -n "${CHECKIN:-}" ] || return 0
  local key host proj mon sched body
  key=$(echo "$SENTRY_DSN"  | sed -E "s|https://([^@]+)@.*|\1|")
  host=$(echo "$SENTRY_DSN" | sed -E "s|https://[^@]+@([^/]+)/.*|\1|")
  proj=$(echo "$SENTRY_DSN" | sed -E "s|.*/([0-9]+)$|\1|")
  mon="oce-refresh-nycha-$MODE"; sched="0 5 * * 0"
  if [ "$1" = in_progress ]; then
    body="{\"check_in_id\":\"$CHECKIN\",\"status\":\"in_progress\",\"environment\":\"production\",\"monitor_config\":{\"schedule\":{\"type\":\"crontab\",\"value\":\"$sched\"},\"checkin_margin\":30,\"max_runtime\":300,\"timezone\":\"UTC\"}}"
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
  body=$(python3 - "oce-refresh-nycha" "${MODE:-}" "$1" <<'PYEOF'
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
HC_URL="${HC_URL_NYCHA_REFRESH:-}"
hc_ping(){   # $1 = start | success | fail
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

case "$MODE" in weekly) ;; *) fail "usage: oce-refresh-nycha.sh weekly" ;; esac
command -v docker >/dev/null || fail "docker not found"
[ -d "$DATA/nycha_spending" ] || log "note: nycha_spending lake absent — spending step will full-build the target FYs"

CHECKIN=$(python3 -c "import uuid;print(uuid.uuid4().hex)" 2>/dev/null || echo "")
sentry_checkin in_progress
hc_ping start

# --- target fiscal years -------------------------------------------------------
read CLOCK_FY NEWEST <<EOF
$(python3 - "$DATA" <<'PY'
import os, sys, datetime, re
data = sys.argv[1]
now = datetime.datetime.utcnow()
clock_fy = now.year + 1 if now.month >= 7 else now.year
years = []
sd = os.path.join(data, "nycha_spending")
if os.path.isdir(sd):
    for d in os.listdir(sd):
        m = re.match(r"fiscal_year=(\d{4})$", d)
        if m and os.path.isdir(os.path.join(sd, d)):
            years.append(int(m.group(1)))
newest = max(years) if years else clock_fy
print(clock_fy, newest)
PY
)
EOF
[ -n "${CLOCK_FY:-}" ] && [ -n "${NEWEST:-}" ] || fail "could not determine fiscal years"
TOP=$(( CLOCK_FY > NEWEST ? CLOCK_FY : NEWEST ))
BR_FROM=$(( TOP - 2 ))
SPEND_FYS="$TOP $(( TOP - 1 ))"

log "=== NYCHA refresh start ($MODE); clock_fy=$CLOCK_FY newest_spending=$NEWEST -> single-file FYs $TOP..$BR_FROM (merge); spending FYs $SPEND_FYS ==="

rm -rf "$BUILD"
mkdir -p "$BUILD/nycha_budget" "$BUILD/nycha_revenue" "$BUILD/nycha_contracts" "$BUILD/nycha_spending" || fail "mkdir staging"

# --- 1) single-file domains (budget/revenue/contracts): recent FYs + merge ------
# args: <domain> <module> <year-flag-name> <csv-prefix> <live-parquet>
build_single() {
  local domain="$1" module="$2" prefix="$3"
  log "building $domain (FYs $TOP..$BR_FROM + merge) ..."
  docker run --rm -m 6g --dns 8.8.8.8 -v "$DATA":/data -w /app "$IMG" sh -c '
    for FY in $(seq '"$TOP"' -1 '"$BR_FROM"'); do
      python -m extractors.'"$module"' --year "$FY" || true
      if [ -s /tmp/'"$prefix"'_data.csv ] && [ "$(wc -l < /tmp/'"$prefix"'_data.csv)" -gt 1 ]; then
        cp /tmp/'"$prefix"'_data.csv "/tmp/'"$prefix"'_$FY.csv"
      fi
    done
    ls /tmp/'"$prefix"'_2*.csv >/dev/null 2>&1 || { echo "no '"$domain"' CSVs"; exit 1; }
    python build_budget_revenue_parquet.py --domain '"$domain"' --csv "/tmp/'"$prefix"'_2*.csv" \
      --out /data/_refresh_build_nycha/'"$domain"' --merge /data/'"$domain"'/'"$domain"'.parquet
  ' >>"$LOG" 2>&1 || fail "$domain build"
  [ -f "$BUILD/$domain/$domain.parquet" ] || fail "$domain.parquet not built"
}
build_single nycha_budget    checkbook_budget_nycha    nycha_budget
build_single nycha_revenue   checkbook_revenue_nycha   nycha_revenue
build_single nycha_contracts checkbook_contracts_nycha nycha_contracts

# --- 2) spending (partitioned): rebuild current + prior FY partitions ------------
BUILT_SPEND=""
for FY in $SPEND_FYS; do
  log "building nycha_spending FY$FY ..."
  docker run --rm -m 6g --dns 8.8.8.8 -v "$DATA":/data -w /app "$IMG" \
    python build_nycha_spending_parquet.py --fiscal-year "$FY" --download \
    --out /data/_refresh_build_nycha/nycha_spending >>"$LOG" 2>&1
  if [ -d "$BUILD/nycha_spending/fiscal_year=$FY" ]; then
    BUILT_SPEND="$BUILT_SPEND $FY"
  else
    log "  nycha_spending FY$FY produced no output — skipping (e.g. not-yet-open FY)"
  fi
done

# --- 3) validate (>50% row-count guard) BEFORE swap -----------------------------
count_rows(){ docker run --rm -v "$DATA":/data -w /app "$IMG" python -c "
import duckdb,sys
try: print(duckdb.sql(\"SELECT count(*) FROM read_parquet('/data/$1')\").fetchone()[0])
except Exception: print(0)" 2>/dev/null | tail -1; }
guard(){ # $1=new $2=old $3=label
  [ "${1:-0}" -gt 0 ] || fail "$3 built 0 rows"
  if [ "${2:-0}" -gt 0 ] && [ "$(( $1 * 100 / $2 ))" -lt "$MIN_RATIO" ]; then
    fail "$3 dropped >50% ($1 < ${MIN_RATIO}% of $2) — keeping live data"
  fi
}
for D in nycha_budget nycha_revenue nycha_contracts; do
  new=$(count_rows "_refresh_build_nycha/$D/$D.parquet"); old=$(count_rows "$D/$D.parquet")
  log "  $D: new=$new live=$old"; guard "$new" "$old" "$D"
done
for FY in $BUILT_SPEND; do
  new=$(count_rows "_refresh_build_nycha/nycha_spending/fiscal_year=$FY/*.parquet")
  old=$(count_rows "nycha_spending/fiscal_year=$FY/*.parquet")
  log "  nycha_spending FY$FY: new=$new live=$old"; guard "$new" "$old" "nycha_spending FY$FY"
done

# --- 4) swap (api stopped briefly so no query sees a half-swapped tree) ----------
log "validation OK — swapping ..."
cd "$ROOT" || fail "cd $ROOT"
docker compose stop api >/dev/null 2>&1
for D in nycha_budget nycha_revenue nycha_contracts; do
  live="$DATA/$D/$D.parquet"
  [ -f "$live" ] && mv "$live" "$live.bak"
  mkdir -p "$DATA/$D"; mv "$BUILD/$D/$D.parquet" "$live" || log "swap $D failed"
done
# Rollback copies of spending partitions MUST live OUTSIDE the partitioned tree:
# a sibling "fiscal_year=$FY.bak" dir matches the reader's fiscal_year=* glob and
# hive-partitioning then parses "2026.bak" as the partition value — the summary
# endpoint 500s on it and the post-swap check rolls back GOOD data (bit both
# 2026-07-15 runs; only spending is read via a directory glob, so only it failed).
RBK="$DATA/_rollback_nycha_spending"
rm -rf "$RBK"; mkdir -p "$RBK"
for FY in $BUILT_SPEND; do
  live="$DATA/nycha_spending/fiscal_year=$FY"
  [ -d "$live" ] && mv "$live" "$RBK/fiscal_year=$FY"
  mv "$BUILD/nycha_spending/fiscal_year=$FY" "$live" || log "swap spending FY$FY failed"
done
docker compose up -d api >/dev/null 2>&1

# --- 5) post-swap live-check + rollback -----------------------------------------
# The swap recreates the api container, clearing its response cache, so EVERY
# endpoint is served cold and the heavy ones (contracts aggregates ~16.5M rows)
# take a while to warm. Retry each endpoint with backoff until it reports
# available:true — a single cold/slow/warming response must NOT trigger a false
# rollback (row-count validation already passed above). ~2 min budget/endpoint.
check_available(){  # $1 = endpoint path; returns 0 once available:true, else 1
  local ep="$1" i
  for i in $(seq 1 40); do
    curl -sf -m 30 -H "Host: $HOSTHDR" "http://localhost/$ep" 2>/dev/null | grep -q '"available": *true' && return 0
    sleep 3
  done
  return 1
}
ok=1
for ep in "oce/nycha/budget/summary" "oce/nycha/revenue/summary" "oce/nycha/contracts/summary" "oce/nycha/spending/summary"; do
  check_available "$ep" || { ok=0; log "post-swap check: $ep never reported available:true after retries"; }
done

if [ "$ok" = "1" ]; then
  for D in nycha_budget nycha_revenue nycha_contracts; do rm -f "$DATA/$D/$D.parquet.bak"; done
  rm -rf "$RBK"
  rm -rf "$BUILD"
  # Rebuild the NYCHA→PASSPort vendor crosswalk from the just-swapped lake so it
  # tracks vendor churn. Must run in the api container (needs BOTH the DuckDB
  # /data lake AND Postgres — an isolated docker run isn't on the compose
  # network). Guarded: a crosswalk hiccup must never fail the lake refresh.
  log "refreshing NYCHA vendor crosswalk ..."
  if docker compose exec -T api python build_nycha_vendor_crosswalk.py >>"$LOG" 2>&1; then
    log "vendor crosswalk refreshed"
  else
    log "WARN: vendor crosswalk refresh failed (lake refresh unaffected) — rerun manually: docker compose exec -T api python build_nycha_vendor_crosswalk.py"
  fi
  sentry_checkin ok
  hc_ping success
  log "=== NYCHA refresh OK ($MODE); budget/revenue/contracts + spending FYs:$BUILT_SPEND ==="
else
  log "post-swap live-check FAILED — rolling back"
  docker compose stop api >/dev/null 2>&1
  for D in nycha_budget nycha_revenue nycha_contracts; do
    [ -f "$DATA/$D/$D.parquet.bak" ] && { rm -f "$DATA/$D/$D.parquet"; mv "$DATA/$D/$D.parquet.bak" "$DATA/$D/$D.parquet"; }
  done
  for FY in $BUILT_SPEND; do
    live="$DATA/nycha_spending/fiscal_year=$FY"
    [ -d "$RBK/fiscal_year=$FY" ] && { rm -rf "$live"; mv "$RBK/fiscal_year=$FY" "$live"; }
  done
  rm -rf "$RBK"
  docker compose up -d api >/dev/null 2>&1
  fail "post-swap check (rolled back)"
fi
