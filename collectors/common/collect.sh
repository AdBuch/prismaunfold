#!/bin/sh
# Shared entrypoint for all PrismUnfold collector images.
# Runs one agent CLI once, headless, and expects a report file as the result.
#
# Required env: AGENT (codex|claude|vibe|goose), TOPIC
# Optional env: LANGUAGE (default en), EDITION (default: current UTC date and hour),
#               TOPIC_ID (file name of the report; default: derived from TOPIC),
#               MAX_TURNS (default 40),
#               CODEX_ARGS, CLAUDE_ARGS, VIBE_ARGS, GOOSE_ARGS (extra flags for that CLI),
#               AGENT_ARGS (extra flags for whichever CLI this image runs)
#               CONTEXT_FILE (default /context/prior.md): earlier PrismUnfold coverage
#               of the topic, written by the pipeline; appended to the prompt when present.
set -eu

: "${AGENT:?AGENT is required}"
: "${TOPIC:?TOPIC is required}"
LANGUAGE="${LANGUAGE:-en}"
EDITION="${EDITION:-$(date -u +%Y-%m-%dT%H)}"
MAX_TURNS="${MAX_TURNS:-40}"
AGENT_ARGS="${AGENT_ARGS:-}"
CONTEXT_FILE="${CONTEXT_FILE:-/context/prior.md}"

TOPIC_ID="${TOPIC_ID:-$(printf '%s' "$TOPIC" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//; s/-$//' | cut -c1-60)}"
TOPIC_ID="${TOPIC_ID:-topic}"

OUT_DIR="/out/${EDITION}/${AGENT}"
REPORT="${OUT_DIR}/${TOPIC_ID}.json"
LOG="${OUT_DIR}/${TOPIC_ID}.log"
PROMPT_FILE="/tmp/prompt.md"
(umask 000 && mkdir -p "/out/${EDITION}" && chmod 1777 "/out/${EDITION}" 2>/dev/null) || true
mkdir -p "$OUT_DIR"
cd /work

{
  printf 'Agent name: %s\n' "$AGENT"
  printf 'Topic: %s\n' "$TOPIC"
  printf 'Report language: %s\n' "$LANGUAGE"
  printf 'Edition: %s\n' "$EDITION"
  printf 'Write the report to this exact path: %s\n\n' "$REPORT"
  cat /opt/collector/assignment.md
  printf '\n\n## JSON schema of the report\n\n'
  cat /opt/collector/report.schema.json
  if [ -s "$CONTEXT_FILE" ]; then
    printf '\n\n'
    cat "$CONTEXT_FILE"
  fi
} > "$PROMPT_FILE"

echo "collector: agent=$AGENT topic=$TOPIC language=$LANGUAGE edition=$EDITION" >&2

# AGENT_ARGS is split on purpose so several flags can be passed.
# shellcheck disable=SC2086
case "$AGENT" in
  codex)
    if [ -n "${OPENAI_API_KEY:-}" ]; then
      codex login --api-key "$OPENAI_API_KEY" >/dev/null
    elif [ ! -s "${CODEX_HOME:-$HOME/.codex}/auth.json" ]; then
      echo "collector: codex needs OPENAI_API_KEY or a mounted auth.json" >&2
      exit 2
    fi
    codex exec --skip-git-repo-check $AGENT_ARGS ${CODEX_ARGS:-} - < "$PROMPT_FILE" > "$LOG" 2>&1
    ;;
  claude)
    if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
      echo "collector: claude needs ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN" >&2
      exit 2
    fi
    claude -p "$(cat "$PROMPT_FILE")" \
      --allowedTools "WebSearch,WebFetch,Read,Write" \
      --max-turns "$MAX_TURNS" $AGENT_ARGS ${CLAUDE_ARGS:-} > "$LOG" 2>&1
    ;;
  vibe)
    : "${MISTRAL_API_KEY:?MISTRAL_API_KEY is required}"
    vibe --prompt "$(cat "$PROMPT_FILE")" --trust \
      --max-turns "$MAX_TURNS" --output text $AGENT_ARGS ${VIBE_ARGS:-} > "$LOG" 2>&1
    ;;
  goose)
    : "${GOOSE_PROVIDER:?GOOSE_PROVIDER is required}"
    : "${GOOSE_MODEL:?GOOSE_MODEL is required}"
    GOOSE_MODE=auto goose run --no-session -i "$PROMPT_FILE" $AGENT_ARGS ${GOOSE_ARGS:-} > "$LOG" 2>&1
    ;;
  *)
    echo "collector: unknown AGENT '$AGENT'" >&2
    exit 2
    ;;
esac

if [ ! -s "$REPORT" ]; then
  echo "collector: agent finished but wrote no report at $REPORT (see $LOG)" >&2
  exit 1
fi
echo "collector: report written to $REPORT" >&2
