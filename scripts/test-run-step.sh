#!/bin/sh
set -eu
ROOT_DIR=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
STATE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/opportunity-radar-cloud-test.XXXXXX")
export OPPORTUNITY_RADAR_STATE_DIR="$STATE_DIR"
"$ROOT_DIR/scripts/run-step.sh" discover --query "AI" --days 30 --limit 2 --sources developer >/dev/null
plan=$(find "$STATE_DIR/runs" -name '*-plan.json' -type f | head -n 1)
[ -n "$plan" ] || { echo "Plan JSON was not created" >&2; exit 1; }
python3 - "$plan" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
assert p['runtime']=='cloud-native-web-search'
assert p['tasks']
assert all(t['queries'] for t in p['tasks'])
assert all(t['result_limit']==2 for t in p['tasks'])
print('Cloud-native query-plan check passed')
PY
cat > "$STATE_DIR/evidence.json" <<'JSON'
{"collected_at":"2026-09-26T00:00:00+00:00","results":[{"source_id":"test","records":[{"title":"Example","url":"https://example.com/item","summary":"Example evidence","evidence_type":"test"}]}]}
JSON
python3 "$ROOT_DIR/scripts/validate-evidence.py" "$STATE_DIR/evidence.json" >/dev/null
printf 'Cloud-native skill checks passed. State kept at: %s\n' "$STATE_DIR"
