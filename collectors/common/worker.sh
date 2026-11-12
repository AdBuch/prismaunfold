#!/bin/sh
# Work through the job list the pipeline wrote, one topic at a time.
#
# Reads /shared/jobs/current.tsv (first line "#edition <id>", then
# <topic id> TAB <language> TAB <topic>) and calls collect.sh for every topic this
# agent has not reported on yet in that edition.
#
# WORKER_INTERVAL unset: go through the list once and exit (Kubernetes CronJob).
# WORKER_INTERVAL=N:     repeat every N seconds (docker compose).
#
# A topic that failed is marked and not retried in the same edition, so a broken
# setup cannot burn API budget in a loop. Delete the .failed file to retry.
set -eu

: "${AGENT:?AGENT is required}"
JOBS="${JOBS_FILE:-/shared/jobs/current.tsv}"
TAB="$(printf '\t')"

has_credentials() {
  case "$AGENT" in
    codex) [ -n "${OPENAI_API_KEY:-}" ] ;;
    claude) [ -n "${ANTHROPIC_API_KEY:-}" ] ;;
    vibe) [ -n "${MISTRAL_API_KEY:-}" ] ;;
    goose) [ -n "${GOOSE_PROVIDER:-}" ] && [ -n "${GOOSE_MODEL:-}" ] ;;
    *) return 1 ;;
  esac
}

run_once() {
  if [ ! -s "$JOBS" ]; then
    echo "worker[$AGENT]: no job list yet at $JOBS" >&2
    return 0
  fi
  edition="$(sed -n '1s/^#edition //p' "$JOBS")"
  if [ -z "$edition" ]; then
    echo "worker[$AGENT]: job list has no edition line" >&2
    return 0
  fi
  out="/out/$edition/$AGENT"
  # Read the list on fd 3 so the agent CLI cannot consume it through stdin.
  while IFS="$TAB" read -r topic_id language topic <&3; do
    case "$topic_id" in '' | \#*) continue ;; esac
    [ -e "$out/$topic_id.json" ] && continue
    [ -e "$out/$topic_id.failed" ] && continue
    if EDITION="$edition" TOPIC_ID="$topic_id" LANGUAGE="$language" TOPIC="$topic" \
      CONTEXT_FILE="/shared/context/$edition/$topic_id.md" \
      /opt/collector/collect.sh < /dev/null; then
      :
    else
      mkdir -p "$out"
      date -u +%Y-%m-%dT%H:%M:%SZ > "$out/$topic_id.failed"
      echo "worker[$AGENT]: '$topic' failed; not retried in edition $edition" >&2
    fi
  done 3< "$JOBS"
}

if ! has_credentials; then
  echo "worker[$AGENT]: no credentials configured, this agent stays idle" >&2
  exit 0
fi

if [ -z "${WORKER_INTERVAL:-}" ]; then
  run_once
  exit 0
fi
while :; do
  run_once
  sleep "$WORKER_INTERVAL"
done
