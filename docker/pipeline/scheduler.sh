#!/bin/sh
# Pipeline loop. Every PIPELINE_INTERVAL seconds:
#   1. plan     write the job list and prior coverage for the current 6-hour edition
#   2. reports  check what the collectors wrote for this and the previous edition
#               (a report may arrive after the edition changed), store, index, export
#   3. run      build the feed-based briefing from the source catalog
# Every step is safe to repeat. A failing step is logged and the loop carries on.
#
# With arguments, run the prismunfold CLI once instead:  docker compose run --rm pipeline plan
set -u

# DATABASE_URL (postgresql://...) selects PostgreSQL; without it a SQLite file is used.
DB="${DATABASE_URL:-${DB_PATH:-/data/prismunfold.sqlite3}}"
SITE="${SITE_DIR:-/site}"
cli() { command="$1"; shift; python3 -m prismunfold "$command" --db "$DB" --site "$SITE" "$@"; }

if [ "$#" -gt 0 ]; then
  cli "$@"
  exit $?
fi

# CHECK_LINKS=0 turns the link check off (for example without internet access).
LINK_FLAG="--check-links"
[ "${CHECK_LINKS:-1}" = "0" ] && LINK_FLAG=""

while :; do
  echo "pipeline: cycle start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cli plan --topics "${TOPICS_FILE:-/app/config/topics.txt}" --shared-dir /shared --reports-dir /out \
    || echo "pipeline: plan failed" >&2
  cli status --reports-dir /out || true
  # Exit code 1 means some report was rejected; the details are in the log above.
  cli reports --reports-dir /out --edition recent $LINK_FLAG \
    || echo "pipeline: at least one report was rejected" >&2
  if [ "${FEEDS:-1}" = "1" ]; then
    cli run || echo "pipeline: feed run failed" >&2
  fi
  sleep "${PIPELINE_INTERVAL:-600}"
done
