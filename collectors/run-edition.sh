#!/bin/sh
# Run one edition: for every topic, give the agents our prior coverage, let each agent
# write its own report, then check, store, index and export all reports.
#
# Usage:  collectors/run-edition.sh [topics-file]
# Env:    AGENTS  (default "codex claude vibe goose"), EDITION (default: UTC date and hour)
# Needs:  docker compose, python3 (for the prismunfold pipeline), collectors/.env
set -eu
cd "$(dirname "$0")"

TOPICS="${1:-topics.txt}"
AGENTS="${AGENTS:-codex claude vibe goose}"
EDITION="${EDITION:-$(date -u +%Y-%m-%dT%H)}"
export EDITION
mkdir -p out context

pipeline() { (cd .. && PYTHONPATH=src python3 -m prismunfold "$@"); }

# One topic per line: <language>|<topic>. Empty lines and lines starting with # are skipped.
while IFS='|' read -r LANGUAGE TOPIC; do
  case "$LANGUAGE" in '' | \#*) continue ;; esac
  export LANGUAGE TOPIC
  pipeline context --topic "$TOPIC" --language "$LANGUAGE" --out collectors/context/prior.md
  for agent in $AGENTS; do
    # stdin is redirected so the agent cannot swallow the rest of the topics file.
    docker compose run --rm -T "$agent" < /dev/null \
      || echo "run-edition: $agent failed for '$TOPIC'" >&2
  done
done < "$TOPICS"

pipeline reports --reports-dir collectors/out --edition "$EDITION" --check-links
