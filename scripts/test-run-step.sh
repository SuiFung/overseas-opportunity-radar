#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
STATE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/opportunity-radar-test.XXXXXX")
export OPPORTUNITY_RADAR_STATE_DIR="$STATE_DIR"

"$ROOT_DIR/scripts/run-step.sh" discover --query "AI" --days 30 --limit 2 --sources hacker-news,github >/dev/null
evidence_json=$(find "$STATE_DIR/runs" -name '*-evidence.json' -type f | head -n 1)
[ -n "$evidence_json" ] || { printf 'Evidence JSON was not created.\n' >&2; exit 1; }
python3 - "$evidence_json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
results = {result["source_id"]: result for result in payload["results"]}
assert set(results) == {"hacker-news", "github"}, results.keys()
assert all(result["status"] == "collected" for result in results.values()), results
assert all(result["records"] for result in results.values()), results
PY

printf 'Opportunity evidence collection check passed. State kept at: %s\n' "$STATE_DIR"
