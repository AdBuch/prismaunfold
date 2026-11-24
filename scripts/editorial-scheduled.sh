#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
umask 077
day=$(TZ=Europe/Zurich date +%F)
base="${XDG_STATE_HOME:-$HOME/.local/state}/prismunfold/editorial"
mkdir -p "$base"
exec 8>"$base/.scheduled.lock"
flock -w 120 8
ready="$base/$day.ready"
# Query the database first; manual publication and timer retries are idempotent.
published() {
  local history
  history=$(docker compose run --rm --no-deps -T --entrypoint python3 pipeline -m prismunfold.editorial history </dev/null)
  python3 -c 'import json,sys; print("yes" if any(e["date"] == sys.argv[1] for e in json.load(sys.stdin)) else "no")' "$day" <<< "$history"
}
quality_gate() {
  python3 - "$1" "$day" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    e = json.load(f)
sections = {a["section"] for a in e["articles"]}
required = {"Schweiz Politik", "Peru Politik", "International", "Good News"}
if not (e["date"] == sys.argv[2] and len(e["articles"]) >= 8 and len(sections) >= 7
        and required <= sections and e.get("magazine") and e.get("random")
        and {x["category"] for x in e.get("lagebild", [])}
        == {"Wichtig", "Überschätzt", "Unterberichtet", "Beobachten"}):
    sys.exit("Automatic publication refused: incomplete edition; manual review required")
PY
}
status=$(published)
if [[ $status == yes ]]; then
  echo "Today's edition is already published"
  exit 0
fi
case "${1:-}" in
  generate)
    if [[ -s $ready ]]; then
      echo "Today's staged edition already exists"
      exit 0
    fi
    # Runner emits a pointer only after successful validation. No eval of its output.
    pointer=$(mktemp "$base/.pointer.XXXXXX")
    trap 'rm -f "$pointer"' EXIT
    EDITORIAL_READY_POINTER="$pointer" bash scripts/editorial.sh --dry-run
    IFS= read -r report < "$pointer"
    [[ $report == "$base/$day."*/edition.json && -s $report ]]
    quality_gate "$(dirname "$report")/preview.json"
    printf '%s\n' "$report" > "$ready.tmp"
    mv "$ready.tmp" "$ready"
    echo "Validated edition staged for publication: $day"
    ;;
  publish)
    [[ -s $ready ]] || { echo "No validated edition for $day; previous issue retained" >&2; exit 1; }
    IFS= read -r report < "$ready"
    [[ $report == "$base/$day."*/edition.json && -s $report ]]
    quality_gate "$(dirname "$report")/preview.json"
    EDITORIAL_AUTO=1 bash scripts/editorial.sh --publish-existing "$report"
    ;;
  *) echo "Usage: $0 generate|publish" >&2; exit 2 ;;
esac
