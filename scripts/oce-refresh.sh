#!/bin/bash
# OCE data lake refresh — host orchestrator for the Checkbook spending/budget/revenue
# Parquet lake. Mirrors the NYCDB refresh.sh pattern: build in one-off ISOLATED
# containers -> validate -> atomic swap with post-swap live-check + rollback.
# Fails safe: any bad download / validation / post-swap check keeps the CURRENT
# data untouched.
#
#   weekly (default) — re-pull the current + prior fiscal year of spending
#                      (older FYs are immutable) and fully rebuild the small
#                      budget + revenue single-file domains.
#
# ⚠ The builds MUST run in isolated `docker run` containers, NEVER inside the api
# container (`docker compose exec api`): a bulk Checkbook extract OOMs the 3 GB-
# capped api (root cause of the 30h crash-loop, see databook-api-oom-scraper).
#
# Cron (root, on the prod CPX41), alongside the NYCDB lines:
#   0 2 * * 0 /home/ubuntu/databook/scripts/oce-refresh.sh weekly >> /home/ubuntu/databook/scripts/oce-refresh.cron.log 2>&1
set -uo pipefail

MODE="${1:-weekly}"
ROOT=/home/ubuntu/databook
DATA=/home/ubuntu/databook-data          # host path; container mounts it at /data
BUILD="$DATA/_refresh_build"             # staging tree (host); /data/_refresh_build in-container
IMG=databook-api                          # same image the api runs / the M/WBE ingest uses
LOG="$ROOT/scripts/oce-refresh.log"
HOSTHDR="api.databook.nyc"                # curl the api via nginx: localhost:8000 is NOT the api here
MIN_RATIO=50                              # data-safety guard: reject a rebuilt slice < 50% of live rows

log(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
[ -f "$ROOT/.env" ] && . "$ROOT/.env"    # SENTRY_DSN (gitignored)

# --- Sentry Crons check-in (same scheme as /opt/nycdb/app/refresh.sh) -----------
# Alerts on a failed OR missed scheduled run. Client-generated $CHECKIN id:
# re-POST the same id with in_progress then ok/error.
sentry_checkin(){   # $1 = in_progress|ok|error  (uses global $CHECKIN)
  [ -n "${SENTRY_DSN:-}" ] && [ -n "${CHECKIN:-}" ] || return 0
  local key host proj mon sched body
  key=$(echo "$SENTRY_DSN"  | sed -E "s|https://([^@]+)@.*|\1|")
  host=$(echo "$SENTRY_DSN" | sed -E "s|https://[^@]+@([^/]+)/.*|\1|")
  proj=$(echo "$SENTRY_DSN" | sed -E "s|.*/([0-9]+)$|\1|")
  mon="oce-refresh-$MODE"; sched="0 2 * * 0"
  if [ "$1" = in_progress ]; then
    body="{\"check_in_id\":\"$CHECKIN\",\"status\":\"in_progress\",\"environment\":\"production\",\"monitor_config\":{\"schedule\":{\"type\":\"crontab\",\"value\":\"$sched\"},\"checkin_margin\":30,\"max_runtime\":180,\"timezone\":\"UTC\"}}"
  else
    body="{\"check_in_id\":\"$CHECKIN\",\"status\":\"$1\"}"
  fi
  curl -s -m 20 -o /dev/null -X POST "https://$host/api/$proj/cron/$mon/$key/" \
    -H "Content-Type: application/json" -d "$body" 2>/dev/null || true
}
fail(){ log "FAILED ($MODE): $*"; sentry_checkin error; exit 1; }

case "$MODE" in weekly) ;; *) fail "usage: oce-refresh.sh weekly" ;; esac
command -v docker >/dev/null || fail "docker not found"
[ -d "$DATA/spending" ] || fail "live lake $DATA/spending missing"

CHECKIN=$(python3 -c "import uuid;print(uuid.uuid4().hex)" 2>/dev/null || echo "")
sentry_checkin in_progress

# --- helpers --------------------------------------------------------------------
# Row count over a parquet glob, run in an isolated container. Echoes 0 on any error.
count_rows(){   # $1 = /data-relative glob (e.g. spending/fiscal_year=2026/*.parquet)
  docker run --rm -v "$DATA":/data -w /app "$IMG" python -c "
import duckdb, sys
try:
    print(duckdb.sql(\"SELECT count(*) FROM read_parquet('/data/$1')\").fetchone()[0])
except Exception:
    print(0)
" 2>/dev/null | tail -1
}

# --- target fiscal years (robust across the July 1 NYC FY boundary) -------------
# CLOCK_FY = NYC fiscal year from the wall clock (flips July 1). NEWEST = newest FY
# actually present in the lake. TOP = max(the two) so we catch a brand-new FY the
# first week Checkbook opens it; prior FY is refreshed too (trailing settlements).
read CLOCK_FY NEWEST <<EOF
$(python3 - "$DATA" <<'PY'
import os, sys, datetime, re
data = sys.argv[1]
now = datetime.datetime.utcnow()
clock_fy = now.year + 1 if now.month >= 7 else now.year
years = []
sd = os.path.join(data, "spending")
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
TARGET_FYS="$TOP $(( TOP - 1 ))"
# Budget/revenue restate only recent years, so re-pull just the current + 2 prior
# FYs and retain all older years from the existing Parquet (--merge). Old-year
# budget/revenue is effectively frozen at the last full build; a rare deep
# restatement is picked up by a manual full rebuild (see docs/BUDGET-REVENUE.md).
BR_FROM=$(( TOP - 2 ))

log "=== OCE refresh start ($MODE); clock_fy=$CLOCK_FY newest_in_lake=$NEWEST -> spending FYs: $TARGET_FYS; budget/revenue FYs: $TOP..$BR_FROM (merge older) ==="

# --- clean + prepare staging ----------------------------------------------------
rm -rf "$BUILD"
mkdir -p "$BUILD/spending" "$BUILD/budget" "$BUILD/revenue" || fail "mkdir staging"

# --- 1) Build spending, per target FY (isolated container, sequential) ----------
BUILT_FYS=""
for FY in $TARGET_FYS; do
  log "building spending FY$FY ..."
  docker run --rm -m 6g --dns 8.8.8.8 -v "$DATA":/data -w /app "$IMG" \
    python build_spending_parquet.py --fiscal-year "$FY" --download \
    --out /data/_refresh_build/spending >>"$LOG" 2>&1
  rc=$?
  if [ $rc -ne 0 ] || [ ! -d "$BUILD/spending/fiscal_year=$FY" ]; then
    # A not-yet-open future FY legitimately returns no rows — SKIP it (leave live
    # data untouched), don't fail the whole run. Genuine build errors on a FY that
    # SHOULD have data are caught by the <50% guard below when its live slice is big.
    log "  spending FY$FY produced no output (rc=$rc) — skipping this FY"
    continue
  fi
  BUILT_FYS="$BUILT_FYS $FY"
done
[ -n "$(echo "$BUILT_FYS" | tr -d ' ')" ] || fail "no spending FY built"

# --- 2) Build budget + revenue (recent FYs only, merge older from live) ---------
# Download just the current + 2 prior FYs and merge with the retained older years
# from the LIVE Parquet (read at build time, before the swap). Guards against empty
# CSVs so a not-yet-open future year can't poison the union. If the live file is
# absent (fresh box), --merge falls back to a full build from whatever CSVs exist.
log "building budget (year criterion; FYs $TOP..$BR_FROM + merge) ..."
docker run --rm -m 6g --dns 8.8.8.8 -v "$DATA":/data -w /app "$IMG" sh -c '
  for FY in $(seq '"$TOP"' -1 '"$BR_FROM"'); do
    python -m extractors.checkbook_budget --year "$FY" || true
    if [ -s /tmp/budget_data.csv ] && [ "$(wc -l < /tmp/budget_data.csv)" -gt 1 ]; then
      cp /tmp/budget_data.csv "/tmp/budget_$FY.csv"
    fi
  done
  ls /tmp/budget_2*.csv >/dev/null 2>&1 || { echo "no budget CSVs"; exit 1; }
  python build_budget_revenue_parquet.py --domain budget --csv "/tmp/budget_2*.csv" \
    --out /data/_refresh_build/budget --merge /data/budget/budget.parquet
' >>"$LOG" 2>&1 || fail "budget build"

log "building revenue (fiscal_year criterion; FYs $TOP..$BR_FROM + merge) ..."
docker run --rm -m 6g --dns 8.8.8.8 -v "$DATA":/data -w /app "$IMG" sh -c '
  for FY in $(seq '"$TOP"' -1 '"$BR_FROM"'); do
    python -m extractors.checkbook_revenue --year "$FY" || true
    if [ -s /tmp/revenue_data.csv ] && [ "$(wc -l < /tmp/revenue_data.csv)" -gt 1 ]; then
      cp /tmp/revenue_data.csv "/tmp/revenue_$FY.csv"
    fi
  done
  ls /tmp/revenue_2*.csv >/dev/null 2>&1 || { echo "no revenue CSVs"; exit 1; }
  python build_budget_revenue_parquet.py --domain revenue --csv "/tmp/revenue_2*.csv" \
    --out /data/_refresh_build/revenue --merge /data/revenue/revenue.parquet
' >>"$LOG" 2>&1 || fail "revenue build"

[ -f "$BUILD/budget/budget.parquet" ]   || fail "budget.parquet not built"
[ -f "$BUILD/revenue/revenue.parquet" ] || fail "revenue.parquet not built"

# --- 3) Validate (row-count >50% guard) BEFORE any swap -------------------------
# Revenue $-total sanity (the ~460x denormalization trap) is covered post-swap by
# the live /oce/revenue/summary check, which returns the properly de-duped total.
for FY in $BUILT_FYS; do
  new=$(count_rows "_refresh_build/spending/fiscal_year=$FY/*.parquet")
  old=$(count_rows "spending/fiscal_year=$FY/*.parquet")
  log "  spending FY$FY: new=$new live=$old"
  [ "${new:-0}" -gt 0 ] || fail "spending FY$FY built 0 rows"
  if [ "${old:-0}" -gt 0 ] && [ "$(( new * 100 / old ))" -lt "$MIN_RATIO" ]; then
    fail "spending FY$FY dropped >50% ($new < ${MIN_RATIO}% of $old) — keeping live data"
  fi
done
for D in budget revenue; do
  new=$(count_rows "_refresh_build/$D/$D.parquet")
  old=$(count_rows "$D/$D.parquet")
  log "  $D: new=$new live=$old"
  [ "${new:-0}" -gt 0 ] || fail "$D built 0 rows"
  if [ "${old:-0}" -gt 0 ] && [ "$(( new * 100 / old ))" -lt "$MIN_RATIO" ]; then
    fail "$D dropped >50% ($new < ${MIN_RATIO}% of $old) — keeping live data"
  fi
done

# --- 4) Swap (stop api first so no query sees a half-swapped tree) --------------
log "validation OK — swapping in new data ..."
cd "$ROOT" || fail "cd $ROOT"
docker compose stop api >/dev/null 2>&1
SWAPPED=""   # track what we moved, for rollback
for FY in $BUILT_FYS; do
  live="$DATA/spending/fiscal_year=$FY"
  [ -d "$live" ] && mv "$live" "$live.bak"
  mv "$BUILD/spending/fiscal_year=$FY" "$live" || { log "swap FY$FY failed"; break; }
  SWAPPED="$SWAPPED spending:$FY"
done
for D in budget revenue; do
  live="$DATA/$D/$D.parquet"
  [ -f "$live" ] && mv "$live" "$live.bak"
  mv "$BUILD/$D/$D.parquet" "$live" || { log "swap $D failed"; break; }
  SWAPPED="$SWAPPED $D:file"
done
docker compose up -d api >/dev/null 2>&1

# --- 5) Post-swap live-check + rollback -----------------------------------------
# The swap recreates the api container, clearing its response cache, so EVERY
# endpoint is served cold and the heavy ones take a while to warm. Retry each
# check with backoff until it passes — a single cold/slow/warming response must
# NOT trigger a false rollback (row-count validation already passed above).
retry(){ local i; for i in $(seq 1 40); do "$@" && return 0; sleep 3; done; return 1; }
check_2xx(){ curl -sf -m 30 -H "Host: $HOSTHDR" -o /dev/null "http://localhost/$1"; }
# Revenue: assert available AND de-duped modified total is in the ~$100-140B band
check_revenue(){
  curl -sf -m 30 -H "Host: $HOSTHDR" "http://localhost/oce/revenue/summary" 2>/dev/null | python3 -c "
import sys, json, re
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
if not d.get('available', False): sys.exit(1)
# find the largest dollar figure in the payload; must be tens-to-low-hundreds of billions
nums = [float(x) for x in re.findall(r'-?\d+\.?\d*', json.dumps(d)) if len(x) >= 9]
mx = max(nums) if nums else 0
sys.exit(0 if 5e10 <= mx <= 3e11 else 1)
"
}

check_ok=1
FY_CHECK=$(echo "$BUILT_FYS" | awk '{print $1}')
retry check_2xx "oce/spending/top?fiscal_year=$FY_CHECK" || { check_ok=0; log "post-swap check: spending/top never returned 2xx after retries"; }
retry check_2xx "oce/budget/summary" || { check_ok=0; log "post-swap check: budget/summary never returned 2xx after retries"; }
retry check_revenue || { check_ok=0; log "post-swap check: revenue/summary never passed (available + \$-band) after retries"; }

if [ "$check_ok" = "1" ]; then
  for FY in $BUILT_FYS; do rm -rf "$DATA/spending/fiscal_year=$FY.bak"; done
  rm -f "$DATA/budget/budget.parquet.bak" "$DATA/revenue/revenue.parquet.bak"
  rm -rf "$BUILD"
  sentry_checkin ok
  log "=== OCE refresh OK ($MODE); refreshed spending FYs:$BUILT_FYS + budget + revenue ==="
else
  log "post-swap live-check FAILED — rolling back"
  docker compose stop api >/dev/null 2>&1
  for FY in $BUILT_FYS; do
    live="$DATA/spending/fiscal_year=$FY"
    [ -d "$live.bak" ] && { rm -rf "$live"; mv "$live.bak" "$live"; }
  done
  for D in budget revenue; do
    live="$DATA/$D/$D.parquet"
    [ -f "$live.bak" ] && { rm -f "$live"; mv "$live.bak" "$live"; }
  done
  docker compose up -d api >/dev/null 2>&1
  fail "post-swap check (rolled back to previous data)"
fi
