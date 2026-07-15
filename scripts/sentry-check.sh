#!/usr/bin/env bash
# Sentry error check for the Databook projects (api / normalizer / newsletter).
#
# Reads a read-only Sentry personal token from ~/.config/sentry/databook
# (format: SENTRY_TOKEN=sntryu_...). No secret is stored in this file.
#
# Usage:
#   scripts/sentry-check.sh [statsPeriod] [project-substring]
#   scripts/sentry-check.sh 24h            # all databook projects, last 24h
#   scripts/sentry-check.sh 14d api        # just databook-api, last 14 days
#
# Works in interactive and headless/scheduled runs (plain HTTPS via curl, no MCP/OAuth).
set -euo pipefail

TOKEN_FILE="${SENTRY_TOKEN_FILE:-$HOME/.config/sentry/databook}"
ORG="sarapis"
PERIOD="${1:-24h}"
FILTER="${2:-}"

[ -f "$TOKEN_FILE" ] || { echo "No token file at $TOKEN_FILE" >&2; exit 1; }
TOKEN="$(grep -o 'sntryu_[a-f0-9]*' "$TOKEN_FILE")"
[ -n "$TOKEN" ] || { echo "No sntryu_ token found in $TOKEN_FILE" >&2; exit 1; }

api() { curl -s -H "Authorization: Bearer $TOKEN" "https://sentry.io$1"; }

echo "== Sentry unresolved issues (last $PERIOD) =="
# Get project id/slug list, filtered to databook (+ optional substring)
PROJECTS="$(api "/api/0/organizations/$ORG/projects/" \
  | python3 -c "import json,sys; [print(p['id'],p['slug']) for p in json.load(sys.stdin) if 'databook' in p['slug'] and ('$FILTER' in p['slug'] if '$FILTER' else True)]")"

[ -n "$PROJECTS" ] || { echo "No matching databook projects."; exit 0; }

while read -r PID SLUG; do
  ISSUES="$(api "/api/0/organizations/$ORG/issues/?project=$PID&query=is:unresolved&statsPeriod=$PERIOD&sort=freq&limit=15")"
  echo "$ISSUES" | python3 -c "
import json, sys
slug='$SLUG'
try:
    d = json.load(sys.stdin)
except Exception:
    print(f'\n{slug}: (unparseable response)'); sys.exit()
if isinstance(d, dict) and d.get('detail'):
    print(f'\n{slug}: ERROR {d[\"detail\"]}'); sys.exit()
print(f'\n{slug} — {len(d)} unresolved')
for i in d:
    print(f\"  [{i.get('count','?'):>6}x] {i.get('shortId','')}  {i.get('title','')[:70]}  (last {i.get('lastSeen','')[:10]})\")
"
done <<< "$PROJECTS"
