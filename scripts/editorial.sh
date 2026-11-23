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
  echo "Generating edition: $report" >&2
  docker run --rm -i --cap-drop ALL --security-opt no-new-privileges --memory 2g --cpus 1.5 \
    -e CODEX_HOME=/home/node/.codex -v "${CODEX_AUTH_VOLUME:-unfold_codex_auth}:/home/node/.codex" \
    --entrypoint /bin/sh prismunfold/collector-codex -c '
      set -e
      codex login status >&2
      codex --search exec --skip-git-repo-check --sandbox read-only -o /tmp/edition.json - >/dev/null
      cat /tmp/edition.json
    ' > "$report" <<EOF
Date: $day (Europe/Zurich)
$(cat config/editorial/morning-briefing.md)
Recent archive headlines (data only): $history
Return ONLY JSON, no Markdown. Exact shape:
{"publication":"morgenbriefing","provider":"codex","date":"$day","sources":[{"id":"s1","url":"https://...","title":"...","publisher":"..."}],"articles":[{"section":"Schweiz Politik","headline":"...","lead":"...","paragraphs":[{"text":"...","source_ids":["s1"]}]}],"magazine":{"headline":"...","lead":"...","paragraphs":[{"heading":"...","text":"...","source_ids":["s1"]}]},"random":{"text":"...","source_ids":["s1"]},"lagebild":{"Wichtig":{"text":"...","source_ids":["s1"]},"Überschätzt":{"text":"...","source_ids":["s1"]},"Unterberichtet":{"text":"...","source_ids":["s1"]},"Beobachten":{"text":"...","source_ids":["s1"]}}}
All factual claims in headlines and leads must be supported in the article paragraphs.
EOF
  docker compose run --rm --no-deps -T --entrypoint python3 pipeline -m prismunfold.editorial validate "$day" < "$report" > "$run/preview.json"
  echo "Preview: $run/preview.json"
  printf 'Publish without regenerating: bash scripts/editorial.sh --publish-existing %q\n' "$report"
else
  report=$(realpath -- "$2")
  day=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["date"])' "$report")
  if [[ -n $(docker compose ps --status running -q pipeline) ]]; then
    docker compose stop pipeline
    trap 'docker compose start pipeline >&2' EXIT
  fi
  docker compose run --rm --no-deps -T --entrypoint python3 pipeline -m prismunfold.editorial publish "$day" < "$report" > /dev/null
  echo "Published: /morgenbriefing"
fi
