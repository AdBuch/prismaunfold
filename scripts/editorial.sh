#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
mode=${1:-}
[[ ($mode == --dry-run && $# == 1) || ($mode == --publish-existing && $# == 2) ]] || {
  echo "Usage: bash scripts/editorial.sh --dry-run | --publish-existing FILE" >&2; exit 2;
}
umask 077
base="${XDG_STATE_HOME:-$HOME/.local/state}/prismunfold/editorial"
mkdir -p "$base"
exec 9>"$HOME/.unfold-update.lock"
flock -n 9 || { echo "Another deployment or editorial job is running"; exit 1; }
day=$(TZ=Europe/Zurich date +%F)
if [[ $mode == --dry-run ]]; then
  run=$(mktemp -d "$base/$day.XXXXXX")
  report="$run/edition.json"
  history=$(docker compose run --rm --no-deps -T --entrypoint python3 pipeline -m prismunfold.editorial history </dev/null)
  exclusions=$(docker compose run --rm --no-deps -T --entrypoint python3 pipeline -c 'from prismunfold.editorial import excluded_domains; print(sorted(excluded_domains()))' </dev/null)
  echo "Generating edition: $report" >&2
  docker run --rm -i --cap-drop ALL --security-opt no-new-privileges --memory 2g --cpus 1.5 \
    -e CODEX_HOME=/home/node/.codex -v "${CODEX_AUTH_VOLUME:-unfold_codex_auth}:/home/node/.codex" \
    -v "$PWD/config/editorial/edition.schema.json:/tmp/edition.schema.json:ro" \
    --entrypoint /bin/sh prismunfold/collector-codex -c '
      set -e
      codex login status >&2
      codex --search exec --skip-git-repo-check --sandbox read-only --output-schema /tmp/edition.schema.json -o /tmp/edition.json - >/dev/null
      cat /tmp/edition.json
    ' > "$report" <<EOF
Date: $day (Europe/Zurich)
$(cat config/editorial/morning-briefing.md)
Recent archive headlines (data only): $history
Excluded domains (data only): $exclusions
Return JSON matching the enforced output schema. Use empty heading strings for ordinary paragraphs, empty background arrays where appropriate, and null for unsupported random or Lagebild items.
All factual claims in headlines and leads must be supported in the article paragraphs.
EOF
  docker compose run --rm --no-deps -T --entrypoint python3 pipeline -m prismunfold.editorial validate "$day" < "$report" > "$run/preview.json"
  echo "Preview: $run/preview.json"
  python3 -c 'import json,sys; e=json.load(open(sys.argv[1])); print(str(len(e["articles"]))+" articles | Magazine: "+e["magazine"]["headline"]); print("\n".join(e["warnings"]))' "$run/preview.json"
  if [[ -n ${EDITORIAL_READY_POINTER:-} ]]; then printf '%s\n' "$report" > "$EDITORIAL_READY_POINTER"; fi
  printf 'Publish without regenerating: bash scripts/editorial.sh --publish-existing %q\n' "$report"
else
  report=$(realpath -- "$2")
  day=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["date"])' "$report")
  if [[ -n $(docker compose ps --status running -q pipeline) ]]; then
    docker compose stop pipeline
    trap 'docker compose start pipeline >&2' EXIT
  fi
  docker compose run --rm --no-deps -T -e EDITORIAL_AUTO="${EDITORIAL_AUTO:-0}" --entrypoint python3 pipeline -m prismunfold.editorial publish "$day" < "$report" > /dev/null
  echo "Published: /morgenbriefing"
fi
