#!/bin/sh
set -eu
ROOT_DIR=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
PROJECT_DIR=${OPPORTUNITY_RADAR_PROJECT_DIR:-"$(pwd)"}
STATE_DIR=${OPPORTUNITY_RADAR_STATE_DIR:-"$PROJECT_DIR/.opportunity-radar"}

usage() {
  cat <<'TXT'
Usage:
  run-step.sh discover [--query TEXT] [--days DAYS] [--limit COUNT] [--sources PROFILE_OR_IDS]

Cloud-native behavior: this command performs NO network requests. It writes a web-search
plan JSON for the calling agent, which must execute the searches using its built-in web tools.
TXT
}
fail() { printf '%s\n' "Error: $*" >&2; exit 1; }
[ "${1:-}" = "discover" ] || { usage; exit 1; }
shift
query=""; days=30; limit=8; sources="balanced"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --query) [ "$#" -ge 2 ] || fail "--query requires text"; query=$2; shift 2 ;;
    --days) [ "$#" -ge 2 ] || fail "--days requires a positive integer"; days=$2; shift 2 ;;
    --limit) [ "$#" -ge 2 ] || fail "--limit requires a positive integer"; limit=$2; shift 2 ;;
    --sources) [ "$#" -ge 2 ] || fail "--sources requires a profile or source IDs"; sources=$2; shift 2 ;;
    *) fail "Unknown option: $1" ;;
  esac
done
mkdir -p "$STATE_DIR/runs"
stamp=$(date '+%Y-%m-%d-%H%M%S')
out="$STATE_DIR/runs/$stamp-plan.json"
[ ! -e "$out" ] || fail "Output already exists: $out"
python_command=${PYTHON:-python3}
command -v "$python_command" >/dev/null 2>&1 || fail "Python 3 is required"
"$python_command" "$ROOT_DIR/scripts/build-query-plan.py" \
  --registry "$ROOT_DIR/references/source-registry.json" \
  --output-json "$out" --query "$query" --days "$days" --limit "$limit" --sources "$sources"
