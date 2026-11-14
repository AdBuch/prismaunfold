#!/bin/sh
# Work through the job list the pipeline wrote, one topic at a time.
#
# Reads /shared/jobs/current.tsv (first line "#edition <id>", then
# <topic id> TAB <language> TAB <topic> TAB <agents>) and calls collect.sh for every
# topic assigned to this agent that it has not reported on yet in that edition.
# A line without an agents column is meant for every agent.
#
# WORKER_INTERVAL unset: go through the list once and exit (Kubernetes CronJob).
# WORKER_INTERVAL=N:     repeat every N seconds (docker compose).
#
# Failures are retried a bounded number of times with growing pauses:
# MAX_ATTEMPTS tries (default 3), waiting RETRY_BASE_SECONDS * 2^(attempt-1)
# (default 120 s, then 240 s) before the next one. After that the topic is given
# up for this edition, so a broken setup cannot burn API budget in a loop.
# MAX_TOPICS_PER_EDITION caps how many topics this agent starts per edition.
#
# For every job a status file <topic id>.status (JSON) records state, attempts and
# seconds spent; the pipeline summarises them with `prismunfold status`.
set -eu

: "${AGENT:?AGENT is required}"
JOBS="${JOBS_FILE:-/shared/jobs/current.tsv}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
RETRY_BASE_SECONDS="${RETRY_BASE_SECONDS:-120}"
MAX_TOPICS_PER_EDITION="${MAX_TOPICS_PER_EDITION:-10}"
TAB="$(printf '\t')"

has_credentials() {
  case "$AGENT" in
    # An API key, or a subscription login: a mounted ~/.codex/auth.json for Codex,
    # a token from `claude setup-token` for Claude Code.
    codex) [ -n "${OPENAI_API_KEY:-}" ] || [ -s "${CODEX_HOME:-$HOME/.codex}/auth.json" ] ;;
    claude) [ -n "${ANTHROPIC_API_KEY:-}" ] || [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] ;;
    vibe) [ -n "${MISTRAL_API_KEY:-}" ] ;;
    goose) [ -n "${GOOSE_PROVIDER:-}" ] && [ -n "${GOOSE_MODEL:-}" ] ;;
    *) return 1 ;;
  esac
}

# Tell the pipeline this agent is alive and has credentials, so it gets topics assigned.
heartbeat() {
  mkdir -p /out/_agents 2>/dev/null || return 0
  date -u +%Y-%m-%dT%H:%M:%SZ > "/out/_agents/$AGENT.ready" 2>/dev/null || true
}

write_status() { # file state attempts seconds exit_code next_try_epoch
  printf '{"agent":"%s","state":"%s","attempts":%s,"seconds":%s,"exit_code":%s,"next_try":%s,"updated_at":"%s"}\n' \
    "$AGENT" "$2" "$3" "$4" "$5" "$6" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$1.tmp"
  mv "$1.tmp" "$1"
}

# Numeric field from a status file; 0 if the file or field is missing or not a number.
status_number() { # file field
  value="$(sed -n "s/.*\"$2\":\([0-9][0-9]*\).*/\1/p" "$1" 2>/dev/null | head -n 1)"
  printf '%s' "${value:-0}"
}

assigned_to_me() { # agents column; empty means everyone
  [ -z "$1" ] && return 0
  case ",$1," in *",$AGENT,"*) return 0 ;; esac
  return 1
}

run_once() {
  heartbeat
  if [ ! -s "$JOBS" ]; then
    echo "worker[$AGENT]: no job list yet at $JOBS" >&2
    return 0
  fi
  edition="$(sed -n '1s/^#edition //p' "$JOBS")"
  case "$edition" in
    '' | *[!0-9A-Za-z_-]*)
      echo "worker[$AGENT]: job list has no usable edition line" >&2
      return 0
      ;;
  esac
  out="/out/$edition/$AGENT"
  # The edition directory is shared by agents running under different users.
  (umask 000 && mkdir -p "/out/$edition" && chmod 1777 "/out/$edition" 2>/dev/null) || true
  mkdir -p "$out"
  # Read the list on fd 3 so the agent CLI cannot consume it through stdin.
  while IFS="$TAB" read -r topic_id language topic agents <&3; do
    case "$topic_id" in '' | \#* | *[!0-9A-Za-z_-]*) continue ;; esac
    assigned_to_me "${agents:-}" || continue
    [ -e "$out/$topic_id.json" ] && continue

    status="$out/$topic_id.status"
    attempts="$(status_number "$status" attempts)"
    [ "$attempts" -ge "$MAX_ATTEMPTS" ] && continue
    now="$(date +%s)"
    [ "$now" -lt "$(status_number "$status" next_try)" ] && continue
    started="$(find "$out" -name '*.status' | wc -l)"
    if [ "$attempts" -eq 0 ] && [ "$started" -ge "$MAX_TOPICS_PER_EDITION" ]; then
      echo "worker[$AGENT]: budget of $MAX_TOPICS_PER_EDITION topics reached, skipping '$topic'" >&2
      continue
    fi

    attempts=$((attempts + 1))
    code=0
    EDITION="$edition" TOPIC_ID="$topic_id" LANGUAGE="$language" TOPIC="$topic" \
      CONTEXT_FILE="/shared/context/$edition/$topic_id.md" \
      /opt/collector/collect.sh < /dev/null || code=$?
    seconds=$(( $(date +%s) - now + $(status_number "$status" seconds) ))

    if [ "$code" -eq 0 ]; then
      write_status "$status" done "$attempts" "$seconds" 0 0
    elif [ "$attempts" -ge "$MAX_ATTEMPTS" ]; then
      write_status "$status" failed "$attempts" "$seconds" "$code" 0
      echo "worker[$AGENT]: '$topic' failed $attempts times; given up for edition $edition" >&2
    else
      wait_seconds=$((RETRY_BASE_SECONDS * (1 << (attempts - 1))))
      write_status "$status" retrying "$attempts" "$seconds" "$code" $(( $(date +%s) + wait_seconds ))
      echo "worker[$AGENT]: '$topic' failed (attempt $attempts of $MAX_ATTEMPTS); next try in ${wait_seconds}s" >&2
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
