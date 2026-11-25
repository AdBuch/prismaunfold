#!/usr/bin/env bash
# Production deployment of PrismUnfold releases (server "unfold", checkout /opt/unfold).
#
#   deploy-release.sh deploy vX.Y.Z [--no-auto-rollback]   deploy a verified release tag
#   deploy-release.sh verify                               run the post-deployment checks only
#   deploy-release.sh rollback                             return to the previously deployed version
#   deploy-release.sh restore-db BACKUP_DIR --yes          restore the database dump of a backup
#   deploy-release.sh status                               current and previous deployment
#
# Only releases are deployed: an annotated or lightweight tag vX.Y.Z whose commit is
# on origin/main and for which the GitHub Actions workflow "CI" finished successfully.
# Before anything changes, the database (pg_dump), the exported site, local
# configuration (.env, compose overrides, topics) and the current image ids are backed
# up. Volumes, secrets, the Codex login volume and editorial run files are never
# touched; `docker compose down` is never called. If the post-deployment checks fail,
# the previous code and images are restored automatically (the 0.2 schema change is
# additive, so the database stays as it is; restore-db exists for the rare case).
#
# Environment (defaults in brackets): UNFOLD_DIR [/opt/unfold], UNFOLD_REPO
# [AdBuch/prismaunfold], BACKUP_DIR [~/backups/prismunfold], DEPLOY_STATE_DIR
# [~/.local/state/prismunfold/deploy], WEB_URL [http://localhost:$WEB_PORT or 8080],
# GITHUB_API [https://api.github.com], CI_WORKFLOW [CI], DB_USER/DB_NAME [prismunfold],
# CODEX_AUTH_VOLUME [unfold_codex_auth], VERIFY_TIMEOUT [240 s], LOCK_FILE [~/.unfold-update.lock].
set -Eeuo pipefail

# The checkout this script lives in is replaced during a deployment, and bash reads
# scripts incrementally: run from a private copy.
if [[ -z ${PRISMUNFOLD_DEPLOY_COPY:-} ]]; then
  copy=$(mktemp "${TMPDIR:-/tmp}/deploy-release.XXXXXX")
  cp -- "$0" "$copy"
  chmod 700 "$copy"
  PRISMUNFOLD_DEPLOY_COPY=$copy exec bash "$copy" "$@"
fi
trap 'rm -f -- "$PRISMUNFOLD_DEPLOY_COPY"' EXIT

UNFOLD_DIR=${UNFOLD_DIR:-/opt/unfold}
UNFOLD_REPO=${UNFOLD_REPO:-AdBuch/prismaunfold}
BACKUP_DIR=${BACKUP_DIR:-$HOME/backups/prismunfold}
STATE_DIR=${DEPLOY_STATE_DIR:-$HOME/.local/state/prismunfold/deploy}
GITHUB_API=${GITHUB_API:-https://api.github.com}
CI_WORKFLOW=${CI_WORKFLOW:-CI}
DB_USER=${DB_USER:-prismunfold}
DB_NAME=${DB_NAME:-prismunfold}
CODEX_AUTH_VOLUME=${CODEX_AUTH_VOLUME:-unfold_codex_auth}
VERIFY_TIMEOUT=${VERIFY_TIMEOUT:-240}
LOCK_FILE=${LOCK_FILE:-$HOME/.unfold-update.lock}
IMAGES=(pipeline web)

say() { printf '[deploy] %s\n' "$*" >&2; }
warn() { printf '[deploy] WARNING: %s\n' "$*" >&2; WARNINGS=$((WARNINGS + 1)); }
die() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }
WARNINGS=0

usage() { sed -n '2,8p' "$PRISMUNFOLD_DEPLOY_COPY" | sed 's/^# \{0,1\}//' >&2; exit 2; }

compose() { docker compose "$@"; }

web_url() {
  if [[ -n ${WEB_URL:-} ]]; then printf '%s' "$WEB_URL"; return; fi
  local port
  port=$(sed -n 's/^WEB_PORT=\([0-9]\{1,5\}\)$/\1/p' .env 2>/dev/null | tail -1)
  printf 'http://localhost:%s' "${port:-8080}"
}

lock() {
  exec 9>"$LOCK_FILE"
  flock -w 300 9 || die "another deployment or editorial job holds $LOCK_FILE"
}

state_write() {  # key value
  mkdir -p "$STATE_DIR"
  printf '%s\n' "$2" > "$STATE_DIR/$1.tmp"
  mv "$STATE_DIR/$1.tmp" "$STATE_DIR/$1"
}
state_read() { cat "$STATE_DIR/$1" 2>/dev/null || true; }

preflight() {
  cd "$UNFOLD_DIR" || die "$UNFOLD_DIR not found"
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "$UNFOLD_DIR is not a git checkout"
  local origin
  origin=$(git config --get remote.origin.url || true)
  [[ ${origin,,} == *"${UNFOLD_REPO,,}"* ]] || die "origin ($origin) is not $UNFOLD_REPO"
  if ! git diff --quiet || ! git diff --cached --quiet; then
    git status --short --untracked-files=no >&2
    die "tracked files were changed locally; commit them upstream or move them to an override (see docs/RELEASE.md)"
  fi
  docker compose version >/dev/null 2>&1 || die "docker compose is not available"
  if command -v systemctl >/dev/null 2>&1; then
    local unit
    for unit in unfold-editorial-generate.service unfold-editorial-publish.service; do
      if systemctl is-active --quiet "$unit" 2>/dev/null; then die "$unit is running; deploy after it finished"; fi
    done
  fi
  if [[ -f docker-compose.override.yml ]] && grep -q '^COMPOSE_FILE=' .env 2>/dev/null \
     && ! grep -q '^COMPOSE_FILE=.*docker-compose.override.yml' .env; then
    warn "COMPOSE_FILE in .env does not list docker-compose.override.yml, so the override is NOT applied"
  fi
}

ci_passed() {  # sha -> 0 if the CI workflow succeeded for this commit
  local sha=$1 body
  body=$(curl -fsS --max-time 20 -H 'Accept: application/vnd.github+json' \
    "$GITHUB_API/repos/$UNFOLD_REPO/actions/runs?head_sha=$sha&per_page=100") \
    || die "cannot query GitHub Actions for $sha"
  printf '%s' "$body" | python3 -c '
import json, sys
runs = [r for r in json.load(sys.stdin).get("workflow_runs", []) if r.get("name") == sys.argv[1]]
ok = [r for r in runs if r.get("status") == "completed" and r.get("conclusion") == "success"]
sys.exit(0 if ok else 1)
' "$CI_WORKFLOW"
}

resolve_release() {  # tag -> sha (verified)
  local tag=$1 sha
  [[ $tag =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "'$tag' is not a release tag (vX.Y.Z)"
  git fetch --quiet --force --tags origin main || die "git fetch failed"
  sha=$(git rev-parse --verify --quiet "refs/tags/$tag^{commit}") || die "tag $tag does not exist on origin"
  git merge-base --is-ancestor "$sha" origin/main || die "$tag ($sha) is not on origin/main"
  ci_passed "$sha" || die "workflow '$CI_WORKFLOW' has not succeeded for $tag ($sha); refusing to deploy"
  printf '%s' "$sha"
}

db_scalar() {  # SQL -> single value via the db container
  compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -At -c "$1"
}

backup() {  # label -> backup directory
  local dir
  dir="$BACKUP_DIR/$(date -u +%Y%m%dT%H%M%SZ)-$1"
  ( umask 077; mkdir -p "$dir" )
  say "backup to $dir"
  compose up -d db >/dev/null
  local i
  for i in $(seq 1 30); do compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 && break; sleep 2; done
  ( umask 077; compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$dir/db.dump" ) \
    || die "pg_dump failed; nothing was changed"
  [[ -s $dir/db.dump ]] || die "database dump is empty; nothing was changed"
  compose exec -T db pg_restore --list < "$dir/db.dump" > "$dir/db.list" || die "database dump is not readable; nothing was changed"
  db_scalar "SELECT count(*) FROM editions" > "$dir/editions.count" || die "cannot count editions"
  if [[ -n $(compose ps -q web 2>/dev/null) ]]; then
    ( umask 077; compose exec -T web tar czf - -C /site . > "$dir/site.tar.gz" ) || warn "site export not archived"
  fi
  local f
  for f in .env docker-compose.override.yml compose.override.yml config/topics.txt; do
    [[ -f $f ]] && install -D -m 600 "$f" "$dir/config/$f"
  done
  { echo "commit=$(git rev-parse HEAD)"; echo "describe=$(git describe --tags --always)"; echo "created=$(date -u +%FT%TZ)"
    for f in "${IMAGES[@]}"; do echo "image_$f=$(docker image inspect -f '{{.Id}}' "prismunfold/$f:latest" 2>/dev/null || echo none)"; done
  } > "$dir/manifest"
  (cd "$dir" && sha256sum db.dump > SHA256SUMS)
  printf '%s' "$dir"
}

keep_images() {  # tag current images so a rollback needs no rebuild
  local img
  for img in "${IMAGES[@]}"; do
    if docker image inspect "prismunfold/$img:latest" >/dev/null 2>&1; then
      docker image tag "prismunfold/$img:latest" "prismunfold/$img:rollback"
    fi
  done
}

install_timers_hint() {
  local unit
  for unit in deploy/systemd/*.service deploy/systemd/*.timer; do
    [[ -f $unit ]] || continue
    if ! cmp -s "$unit" "/etc/systemd/system/$(basename "$unit")"; then
      warn "systemd unit $(basename "$unit") differs from the installed one: run  sudo bash scripts/install-editorial-timers.sh"
      return
    fi
  done
}

verify() {  # post-deployment checks; returns non-zero on a hard failure
  local url fail=0 deadline since=${1:-} before=${2:-}
  url=$(web_url)
  say "verifying (web $url)"
  deadline=$((SECONDS + VERIFY_TIMEOUT))
  until curl -fsS --max-time 5 "$url/healthz" >/dev/null 2>&1; do
    ((SECONDS < deadline)) || { echo "  FAIL web /healthz"; fail=1; break; }
    sleep 3
  done
  if ((fail == 0)); then
    curl -fsS --max-time 10 "$url/" | grep -q '<div id="app">' && echo "  ok   frontend shell" || { echo "  FAIL frontend shell"; fail=1; }
  fi
  local state
  state=$(compose ps --format '{{.Service}} {{.State}}' 2>/dev/null || true)
  for svc in db pipeline web; do
    grep -q "^$svc running" <<<"$state" && echo "  ok   container $svc running" || { echo "  FAIL container $svc not running"; fail=1; }
  done
  local version
  version=$(compose exec -T pipeline python3 -c 'import os; from prismunfold.storage import open_store; s = open_store(os.environ["DATABASE_URL"]); print(s.schema_version()); s.close()' 2>/dev/null | tail -1 || true)
  [[ $version =~ ^[0-9]+$ && $version -ge 2 ]] && echo "  ok   database schema version $version" || { echo "  FAIL database schema version '$version'"; fail=1; }
  if [[ -n $before ]]; then
    local after
    after=$(db_scalar "SELECT count(*) FROM editions" 2>/dev/null || echo -1)
    ((after >= before)) && echo "  ok   editions preserved ($before -> $after)" || { echo "  FAIL editions $before -> $after"; fail=1; }
  fi
  # The pipeline loop exports every cycle; wait for a cycle started after the deployment.
  local seen=0
  while ((SECONDS < deadline)); do
    if compose logs --no-color ${since:+--since "$since"} pipeline 2>/dev/null | grep -q 'pipeline: cycle start'; then seen=1; break; fi
    sleep 5
  done
  ((seen)) && echo "  ok   pipeline cycle running" || { echo "  FAIL no pipeline cycle within ${VERIFY_TIMEOUT}s"; fail=1; }
  local api
  for api in api/v1/editorial/morgenbriefing.json api/v1/daily/index.json; do
    until curl -fsS --max-time 10 "$url/$api" 2>/dev/null | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; do
      ((SECONDS < deadline)) || { echo "  FAIL API $api"; fail=1; continue 2; }
      sleep 5
    done
    echo "  ok   API $api"
  done
  # Importer: independent of the AI workers; only checked when the overlay provides a token.
  if compose exec -T pipeline sh -c 'test -n "${PRISM_DATA_TOKEN_FILE:-}"' 2>/dev/null; then
    if compose exec -T pipeline /app/scheduler.sh import-bulletin >/dev/null 2>&1; then
      echo "  ok   prism-data importer ran (imported, unchanged, waiting or not yet due)"
    else
      warn "prism-data importer failed; see: docker compose logs pipeline | grep import_failed"
    fi
  else
    echo "  --   prism-data importer not configured (COMPOSE_FILE overlay without token)"
  fi
  if command -v systemctl >/dev/null 2>&1; then
    local timer
    for timer in unfold-editorial-generate.timer unfold-editorial-publish.timer; do
      systemctl is-enabled --quiet "$timer" 2>/dev/null && echo "  ok   $timer enabled" || warn "$timer is not enabled"
    done
    install_timers_hint
  fi
  docker volume inspect "$CODEX_AUTH_VOLUME" >/dev/null 2>&1 && echo "  ok   Codex login volume $CODEX_AUTH_VOLUME kept" \
    || warn "Codex login volume $CODEX_AUTH_VOLUME not found (editorial generation will need a login)"
  return "$fail"
}

switch_to() {  # sha [use-rollback-images]
  git -c advice.detachedHead=false checkout --quiet --detach "$1"
  local img
  local have=1
  for img in "${IMAGES[@]}"; do
    docker image inspect "prismunfold/$img:rollback" >/dev/null 2>&1 || have=0
  done
  if [[ ${2:-} == images && $have == 1 ]]; then
    for img in "${IMAGES[@]}"; do
      docker image tag "prismunfold/$img:rollback" "prismunfold/$img:latest"
    done
  else
    # No saved images (or a forward deployment): build from the checked-out code.
    compose build "${IMAGES[@]}"
  fi
  compose up -d db >/dev/null
  compose up -d --no-deps "${IMAGES[@]}"
}

do_rollback() {
  local target backup
  target=$(state_read previous)
  [[ -n $target ]] || die "no previous deployment recorded"
  backup=$(state_read previous_backup)
  say "rolling back to $target"
  switch_to "$target" images
  verify "$(date -u +%FT%TZ)" "" || warn "checks after rollback reported failures"
  state_write current "$target"
  state_write current_tag "$(git describe --tags --always)"
  printf '%s rollback to %s\n' "$(date -u +%FT%TZ)" "$target" >> "$STATE_DIR/history"
  say "rolled back. The database was not changed (0.2 schema change is additive)."
  [[ -n $backup ]] && say "database backup from before the failed deployment: $backup (restore-db $backup --yes)"
}

cmd=${1:-}
case $cmd in
  deploy)
    [[ $# -ge 2 ]] || usage
    tag=$2; auto_rollback=1
    [[ ${3:-} == --no-auto-rollback ]] && auto_rollback=0
    umask 022
    preflight
    lock
    sha=$(resolve_release "$tag")
    previous=$(git rev-parse HEAD)
    if [[ $previous == "$sha" && ${FORCE_REDEPLOY:-0} != 1 ]]; then
      say "$tag ($sha) is already checked out; running the checks only (FORCE_REDEPLOY=1 to rebuild)"
      verify || die "checks failed"
      exit 0
    fi
    say "deploying $tag ($sha), previous $(git describe --tags --always) ($previous)"
    label=$(git describe --tags --always)
    dir=$(backup "${label//[^A-Za-z0-9._-]/_}-to-$tag")
    editions_before=$(cat "$dir/editions.count")
    keep_images
    state_write previous "$previous"
    state_write previous_backup "$dir"
    started=$(date -u +%FT%TZ)
    if ! switch_to "$sha"; then
      warn "build or start failed"
      ((auto_rollback)) && { do_rollback; die "deployment of $tag failed and was rolled back"; }
      die "deployment of $tag failed; run: $0 rollback"
    fi
    if ! verify "$started" "$editions_before"; then
      ((auto_rollback)) && { do_rollback; die "checks failed for $tag; rolled back"; }
      die "checks failed for $tag; run: $0 rollback"
    fi
    state_write current "$sha"
    state_write current_tag "$tag"
    printf '%s deploy %s %s backup=%s warnings=%s\n' "$(date -u +%FT%TZ)" "$tag" "$sha" "$dir" "$WARNINGS" >> "$STATE_DIR/history"
    say "deployed $tag. Backup: $dir. Warnings: $WARNINGS"
    ;;
  verify)
    preflight
    verify "" "" || die "checks failed"
    say "checks passed. Warnings: $WARNINGS"
    ;;
  rollback)
    umask 022
    preflight
    lock
    do_rollback
    ;;
  restore-db)
    [[ $# -ge 3 && $3 == --yes && -s $2/db.dump ]] || die "usage: $0 restore-db BACKUP_DIR --yes (BACKUP_DIR must contain db.dump)"
    cd "$UNFOLD_DIR"
    lock
    (cd "$2" && sha256sum -c SHA256SUMS) || die "backup checksum mismatch"
    say "restoring $2/db.dump (pipeline stopped meanwhile)"
    compose stop pipeline
    compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --single-transaction < "$2/db.dump"
    compose start pipeline
    say "database restored"
    ;;
  status)
    echo "current:  $(state_read current_tag) $(state_read current)"
    echo "previous: $(state_read previous)  backup: $(state_read previous_backup)"
    tail -5 "$STATE_DIR/history" 2>/dev/null || true
    ;;
  *) usage ;;
esac
