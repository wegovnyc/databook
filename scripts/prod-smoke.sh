#!/usr/bin/env bash
# Read-only smoke check against PRODUCTION (https://databook.nyc).
#
# Prod deploys are a manual `git pull && docker compose up -d --build` on the
# CPX41. Run this right after a deploy to confirm prod is serving. Read-only —
# GET requests only, nothing is modified.
#
# (The same check runs in CI via the manually-dispatched `prod-smoke` job, which
# additionally runs the Playwright browser journeys.)
set -uo pipefail

UA="Mozilla/5.0 (compatible; databook-smoke)"   # api 403s non-browser UAs (Cloudflare)
fail=0
check() {  # name url expect_substr(optional)
  local name="$1" url="$2" want="${3:-}"
  local body code
  body=$(curl -s -A "$UA" --max-time 25 -w '\n%{http_code}' "$url")
  code=$(printf '%s' "$body" | tail -1)
  if [ "$code" != "200" ]; then echo "  ✗ $name -> $code"; fail=1; return; fi
  if [ -n "$want" ] && ! printf '%s' "$body" | grep -q "$want"; then
    echo "  ✗ $name -> 200 but missing '$want'"; fail=1; return; fi
  echo "  ✓ $name -> 200"
}

echo "Prod read-only smoke (https://databook.nyc):"
check "frontend home"   "https://databook.nyc/"
check "api orgs"        "https://api.databook.nyc/get/orgs/bycd/101" "rows"
check "api docs"        "https://api.databook.nyc/docs"
check "map home"        "https://map.databook.nyc/"
check "map building"    "https://map.databook.nyc/building/3191412"
check "api2 nycdb"      "https://api2.databook.nyc/" "ok"
check "normalize"       "https://normalize.databook.nyc/"

[ "$fail" = 0 ] && echo "PROD SMOKE: all green" || { echo "PROD SMOKE: FAILURES above"; exit 1; }
