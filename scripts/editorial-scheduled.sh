#!/usr/bin/env bash
# Scheduled editorial workflow (systemd timers, Europe/Zurich; see deploy/systemd).
#
#   generate  (06:00)  recover a saved raw edition of today, else run the worker once;
#                      stage the result only if it passes the automatic publication policy
#   publish   (07:00)  publish the staged edition with the automatic policy
#
# Safe to repeat: an already published edition is a no-op, publication is idempotent,
# and recovery never spends model tokens. The policy itself lives in
# prismunfold.editorial (config/config.json "editorial.auto_publish"), not here.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
umask 077
day=$(TZ=Europe/Zurich date +%F)
base="${XDG_STATE_HOME:-$HOME/.local/state}/prismunfold/editorial"
mkdir -p "$base"
exec 8>"$base/.scheduled.lock"
flock -w 120 8 || { echo "Another scheduled editorial run holds the lock" >&2; exit 1; }
ready="$base/$day.ready"

editorial() { docker compose run --rm --no-deps -T "${extra[@]}" --entrypoint python3 pipeline -m prismunfold.editorial "$@"; }
extra=()

if editorial status "$day" </dev/null >/dev/null 2>&1; then
  echo "Today's edition is already published"
  exit 0
fi

stage() {  # $1 = raw edition; stages it if the automatic policy accepts it
  local report=$1 preview
  preview="$(dirname "$report")/preview.json"
  editorial validate "$day" --check-policy < "$report" > "$preview"
  python3 - "$preview" <<'PY'
import json, sys
e = json.load(open(sys.argv[1]))
if not e.get("auto_publishable"):
    sys.exit("Automatic publication refused: " + e.get("policy_reason", "") + "; manual review required")
PY
  printf '%s\n' "$report" > "$ready.tmp"
  mv "$ready.tmp" "$ready"
}

case "${1:-}" in
  generate)
    if [[ -s $ready ]]; then
      echo "Today's staged edition already exists"
      exit 0
    fi
    # Recover a saved raw edition before spending any model tokens. The choice is
    # deterministic (most usable articles, then magazine, then newest), see select_candidate.
    extra=(-v "$base:/editorial:ro")
    candidate=$(editorial select-candidate "$day" /editorial </dev/null || true)
    extra=()
    if [[ -n $candidate ]]; then
      report="$base/${candidate#/editorial/}"
      [[ $report == "$base/$day."*/edition*.json && -s $report ]]
      stage "$report"
      echo "Recovered staged edition: $report"
      exit 0
    fi
    pointer=$(mktemp "$base/.pointer.XXXXXX")
    trap 'rm -f "$pointer"' EXIT
    EDITORIAL_READY_POINTER="$pointer" bash scripts/editorial.sh --dry-run
    IFS= read -r report < "$pointer"
    [[ $report == "$base/$day."*/edition.json && -s $report ]]
    stage "$report"
    echo "Validated edition staged for publication: $day"
    ;;
  publish)
    [[ -s $ready ]] || { echo "No validated edition for $day; previous issue retained" >&2; exit 1; }
    IFS= read -r report < "$ready"
    [[ $report == "$base/$day."*/edition*.json && -s $report ]]
    EDITORIAL_AUTO=1 bash scripts/editorial.sh --publish-existing "$report"
    ;;
  *) echo "Usage: $0 generate|publish" >&2; exit 2 ;;
esac
