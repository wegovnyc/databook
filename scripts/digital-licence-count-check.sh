#!/usr/bin/env bash
# Do the Renewal Queue and the Software Licenses page agree about how many licence
# contracts are expiring? Read-only; two GETs.
#
# ⚠⚠ WHY THIS IS A SCRIPT AND NOT A UNIT TEST. The two figures are counted over two
# different row sets, and those row sets only exist against a real database. A unit
# test can prove neither page defines the expiring window itself (it does — see
# api/tests/test_queue_rescope.py) and that the queue resolves vendor ids by map
# rather than by a duplicating join. It cannot prove the counts came out equal.
# This is the check that can.
#
# The disagreement it exists for: the queue LEFT JOINed `vendors` on the vendor
# name, 48 names hold more than one row there, and the join duplicated
# CT1-017-20248805602 (Absorb Software LMS, two supplier ids) — so the queue said
# 243 where the Licenses page said 242.
#
# ⚠ AN AGREEMENT OF 0 == 0 IS NOT AN AGREEMENT. On an empty database (the CI
# ephemeral smoke, a fresh local stack) both figures are zero and a naive equality
# check passes having measured nothing — the same vacuous pass as the guard that
# scanned zero files. This script reports SKIP and exits 0 in that case, loudly, and
# never prints OK.
#
# Usage:  bash scripts/digital-licence-count-check.sh [API_BASE]
#         API_BASE defaults to https://api.databook.nyc
set -uo pipefail

BASE="${1:-${DATABOOK_API_BASE:-https://api.databook.nyc}}"
UA="Mozilla/5.0 (compatible; databook-licence-check)"   # the api 403s non-browser UAs at the edge

get() { curl -sS -A "$UA" --max-time 60 "$1"; }

QUEUE_JSON=$(get "${BASE}/oce/digital-reform/all?expiring_limit=1")
LIC_JSON=$(get "${BASE}/oce/licenses")

read -r Q_N Q_V Q_MODE < <(printf '%s' "$QUEUE_JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    print("ERR ERR ERR"); sys.exit()
e = (d.get("expiring") or {})
s = (e.get("summary") or {})
print(s.get("licenses", "ERR"), round(float(s.get("licenses_value") or 0), 2),
      (e.get("scope") or {}).get("mode", "?"))
')

read -r L_N L_V < <(printf '%s' "$LIC_JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    print("ERR ERR"); sys.exit()
s = (d.get("summary") or {})
print(s.get("expiring", "ERR"), round(float(s.get("expiring_value") or 0), 2))
')

echo "Renewal Queue   : ${Q_N} expiring licences, \$${Q_V}  (scope: ${Q_MODE})"
echo "Licenses page   : ${L_N} expiring licences, \$${L_V}"

if [ "$Q_N" = "ERR" ] || [ "$L_N" = "ERR" ]; then
  echo "LICENCE COUNT CHECK: could not read both payloads from ${BASE}"
  exit 1
fi

# ⚠ The queue on the vendor-name scope holds a SUBSET of the licence inventory, so
# the two figures are not comparable there and equality would be the wrong
# assertion. Say which state we are in rather than failing on a scope we know about.
if [ "$Q_MODE" != "derived" ]; then
  echo "LICENCE COUNT CHECK: SKIP — the queue is on the '${Q_MODE}' scope, which"
  echo "  covers only vendors matched by name, so its licence set is a subset of the"
  echo "  Licenses page's by design. Nothing measured."
  exit 0
fi

if [ "$Q_N" = "0" ] && [ "$L_N" = "0" ]; then
  echo "LICENCE COUNT CHECK: SKIP — both figures are 0, so nothing was measured."
  echo "  (Empty database? 0 == 0 is not an agreement.)"
  exit 0
fi

rc=0
[ "$Q_N" = "$L_N" ] || { echo "  ✗ counts disagree: ${Q_N} vs ${L_N}"; rc=1; }
[ "$Q_V" = "$L_V" ] || { echo "  ✗ values disagree: \$${Q_V} vs \$${L_V}"; rc=1; }

if [ "$rc" = 0 ]; then
  echo "LICENCE COUNT CHECK: OK — both pages report ${Q_N} expiring licences worth \$${Q_V}"
else
  echo "LICENCE COUNT CHECK: DISAGREEMENT — the two pages are counting different sets."
  echo "  Most likely causes, in order: a join reintroduced into the queue's row query"
  echo "  (see modules/vendorids.py), a change to one page's expiring window (see"
  echo "  modules/licensewindow.py), or a genuine scope difference — an is_license row"
  echo "  whose tech_relevant is false is on the Licenses page and cannot enter the"
  echo "  queue. Three such rows exist (public-radio subscriptions); none expire in"
  echo "  the window today, and if one starts to, THAT is the reconciliation to state."
fi
exit "$rc"
