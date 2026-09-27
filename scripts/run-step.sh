#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
PROJECT_DIR=${OPPORTUNITY_RADAR_PROJECT_DIR:-"$(pwd)"}
STATE_DIR=${OPPORTUNITY_RADAR_STATE_DIR:-"$PROJECT_DIR/.opportunity-radar"}

usage() {
  cat <<'EOF'
Usage:
  run-step.sh discover [--query TEXT] [--days DAYS] [--limit COUNT] [--sources PROFILE_OR_IDS]

Source profiles and IDs are defined in references/source-registry.json.
The command writes raw evidence JSON only. The calling agent turns it into a ranked opportunity shortlist.
EOF
}

fail() {
  printf '%s\n' "Error: $*" >&2
  exit 1
}

[ "${1:-}" = "discover" ] || { usage; exit 1; }
shift
query=""
days=30
limit=5
sources="balanced"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --query) [ "$#" -ge 2 ] || fail "--query requires text."; query=$2; shift 2 ;;
    --days) [ "$#" -ge 2 ] || fail "--days requires a positive integer."; days=$2; shift 2 ;;
    --limit) [ "$#" -ge 2 ] || fail "--limit requires a positive integer."; limit=$2; shift 2 ;;
    --sources) [ "$#" -ge 2 ] || fail "--sources requires a profile name or comma-separated source IDs."; sources=$2; shift 2 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

mkdir -p "$STATE_DIR/runs"
stamp=$(date '+%Y-%m-%d-%H%M%S')
json_output="$STATE_DIR/runs/$stamp-evidence.json"
[ ! -e "$json_output" ] || fail "Output already exists: $json_output"
python_command=${PYTHON:-python3}
command -v "$python_command" >/dev/null 2>&1 || fail "Python 3 is required. Set PYTHON to its executable path."
"$python_command" "$ROOT_DIR/scripts/collect_discovery.py" \
  --registry "$ROOT_DIR/references/source-registry.json" \
  --output-json "$json_output" \
  --query "$query" \
  --days "$days" \
  --limit "$limit" \
  --sources "$sources"
