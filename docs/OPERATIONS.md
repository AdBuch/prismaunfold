# Operations

Local development, tests, deployment on the Proxmox VM, scheduling, secrets,
logging, recovery and rollback. Workflow semantics: [EDITORIAL_WORKFLOW.md](EDITORIAL_WORKFLOW.md).

## Local development and tests

```bash
# Pipeline: Python 3.11+, standard library only, SQLite file as the store
PYTHONPATH=src python3 -m unittest discover -s tests
# Same tests against PostgreSQL (needs psycopg 3)
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres PYTHONPATH=src python3 -m unittest discover -s tests

# Frontend: Node 22
cd frontend && npm install && npm run typecheck && npm test && npm run build
```

Tests use fixtures and mocks only: no network, no credentials, no AI calls, no
access to `prism-data`. CI (`.github/workflows/ci.yml`) runs them on every push,
plus PostgreSQL, frontend type check/unit/browser tests, image builds, ShellCheck,
compose validation and a full stack test.

## Environment on the server

Proxmox VM (Debian, ~4 GB RAM), Docker Compose, checkout in `/opt/unfold`, deploying
user `adrian`. Services: `db` (PostgreSQL 16), `pipeline` (loop every 10 min), `web`
(nginx, port 8080); collector containers optional. Persistent volumes: `pgdata`,
`site`, `shared`, `reports`, and the Codex auth volume `unfold_codex_auth`.
Editorial run state: `~/.local/state/prismunfold/editorial/`.

## Configuration and secrets

| Setting | Where | Notes |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | `.env` | Fixed once the volume exists |
| `COMPOSE_FILE=docker-compose.yml:deploy/compose.prism-data.yml` | `.env` | Enables the prism-data import |
| `PRISM_DATA_SECRET_PATH=/home/adrian/.config/prismunfold/prism-data.token` | `.env` | Absolute path to the token file, outside the checkout |
| `editorial.auto_publish` | `config/config.json` | `min_articles`, `min_sections` |
| `EDITORIAL_TIMEOUT_SECONDS` (2400), `EDITORIAL_MAX_GENERATIONS` (1), `EDITORIAL_FORCE_GENERATE`, `EDITORIAL_STAGES` (`single`/`split`), `EDITORIAL_RESEARCH_FROM`, `CODEX_AUTH_VOLUME` | environment of `scripts/editorial.sh` | |
| `SOURCE_CHECK_CACHE` | environment | Optional JSON cache file for source checks |

**prism-data token.** Fine-grained GitHub personal access token, *Only select
repositories: `AdBuch/prism-data`*, permission *Contents: Read-only*, nothing else,
expiry ≤ 90 days.

```bash
install -d -m 700 ~/.config/prismunfold
( umask 077; printf '%s' 'github_pat_…' > ~/.config/prismunfold/prism-data.token )
# readable by the pipeline user (UID 1000 in the container); on rootless Docker map the UID
```

The token reaches only the pipeline container, as the Compose secret
`/run/secrets/prism_data_token`. It is never in Git, in logs (the logger redacts
token-like values), in prompts, in frontend configuration, or in the Codex/collector
containers. Requests go only to `api.github.com`; redirects are not followed, so the
`Authorization` header never reaches another host.

**Rotation:** create the new token, overwrite the file, run
`docker compose up -d pipeline` (secrets are read per import, a restart is only
needed if the file path changes), check one `import_completed`/`import_waiting`
event, then revoke the old token on GitHub.

## Deploy

```bash
cd /opt/unfold
# 0. Backup (always)
mkdir -p ~/backups && docker compose exec -T db pg_dump -U prismunfold -Fc prismunfold > ~/backups/prismunfold-$(date +%F-%H%M).dump
git rev-parse HEAD > ~/backups/deployed-before-$(date +%F-%H%M).txt
# 1. Code (normal deploying user, umask 022; or the existing update script)
git fetch origin
git switch feature/consolidation-0.1-0.2   # after the PR is merged: git switch main && git pull --ff-only
# 2. Images and services (the schema upgrade is additive and runs on pipeline start)
docker compose build pipeline web
docker compose up -d db pipeline web
# 3. Checks
docker compose logs --tail 50 pipeline
docker compose run --rm --no-deps -T --entrypoint python3 pipeline -c \
  'from prismunfold.storage import open_store; import os; s=open_store(os.environ["DATABASE_URL"]); print("schema", s.schema_version())'
curl -fsS http://localhost:8080/api/v1/daily/index.json | head -c 300
# 4. Timers (only when the files under deploy/systemd changed)
sudo bash scripts/install-editorial-timers.sh
```

## Scheduling

One scheduler per task, all in Europe/Zurich (systemd handles DST via `OnCalendar … Europe/Zurich`;
the importer converts with `zoneinfo`).

| When | What | Scheduler |
| --- | --- | --- |
| 06:00 | `editorial-scheduled.sh generate`: recover a saved run of today, else one Codex run; stage it if the automatic policy accepts it | `unfold-editorial-generate.timer` |
| 07:00 | `editorial-scheduled.sh publish`: publish the staged edition (automatic policy) | `unfold-editorial-publish.timer` |
| from 07:00, every cycle (10 min) | `import-bulletin`: today's prism-data file; waits if missing, skips unchanged, applies corrections, keeps older revisions out | pipeline container loop |
| every cycle | feeds, agent reports, export | pipeline container loop |

Both timers are `Persistent=true`, so a run missed during a reboot is caught up.
Publication no longer stops the pipeline container; writers are serialised by a
database lock (`flock` for SQLite, PostgreSQL advisory lock). The scheduled script
holds its own lock; `editorial.sh` shares `~/.unfold-update.lock` with the
deployment update script, so generation and publication never overlap a deploy.

The newspaper stays readable when Codex, Claude, Mistral or GitHub are down, the
bulletin is late, a source answers 403 or 429, the magazine fails, PostgreSQL
restarts (connections are retried), a worker is interrupted, or the server reboots:
every step is repeatable and the previous edition stays published until a new one
passes.

## Logging

Pipeline components write one JSON object per line (`src/prismunfold/oplog.py`):
`timestamp`, `component`, `event`, `run_id`, and where relevant `provider`,
`edition_date`, `article_id`, `contribution_id`, `status`, `duration_ms`,
`attempt`, `error_code`, `paragraph`, `sources`.

Events: `import_started`, `import_completed`, `import_unchanged`, `import_waiting`,
`import_failed`, `validation_failed`, `article_review_required`, `article_approved`,
`article_rejected`, `edition_published`, `edition_recovered`, `export_completed`.
Worker runs write `run.json` (exit code, duration, token use if reported) and
`worker.log` next to the raw edition.

```bash
docker compose logs pipeline | grep '"component": "bulletin"' | tail
journalctl -u unfold-editorial-generate.service -u unfold-editorial-publish.service --since today
```

Never logged: tokens, authorization headers, complete prompts or model responses,
document content of the bulletin.

## Recovery of existing editions (no AI call)

Raw editions are never modified; recovery writes previews into a new
`recovery-<UTC>` directory next to the raw file.

```bash
cd /opt/unfold
E=~/.local/state/prismunfold/editorial

# Inspect: every problem with article, paragraph, source id, URL and reason
bash scripts/editorial.sh --inspect $E/2026-11-25.7IyLAC/edition.json

# Preview with the current validation (writes recovery-*/preview.json and problems.json)
bash scripts/editorial.sh --recover $E/2026-11-25.7IyLAC/edition.json

# Publish it (automatic policy) – idempotent, safe to retry after a failed export
EDITORIAL_AUTO=1 bash scripts/editorial.sh --publish-existing $E/2026-11-25.7IyLAC/edition.json

# Or as operator: also publish review-required articles with a visible label, accept a partial edition
bash scripts/editorial.sh --publish-existing $E/2026-11-25.7IyLAC/edition.json \
  --approve-review-required --allow-partial --reviewer adrian

# 24 Nov: two candidates; choose explicitly, or let the selector choose deterministically
PYTHONPATH=src python3 -m prismunfold.editorial select-candidate 2026-11-24 "$E"   # host Python 3.11+, stdlib only
bash scripts/editorial.sh --publish-existing $E/2026-11-24.zIa6G9/edition.repaired.json
#   (if 24 Nov is already published with other content: add --replace; the old version is kept as superseded)

# After publication
bash scripts/editorial.sh --status 2026-11-25                      # published and withheld articles with reasons
bash scripts/editorial.sh --approve 2026-11-25 ed-2026-11-25-xxxx adrian "AP-Artikel manuell geprüft"
bash scripts/editorial.sh --reject  2026-11-25 ed-2026-11-25-xxxx adrian "Aussage nicht belegt"
bash scripts/editorial.sh --revalidate 2026-11-25                  # re-check sources, promote what now passes
bash scripts/editorial.sh --reexport                               # rewrite JSON from the database

# prism-data
docker compose run --rm pipeline import-bulletin --date 2026-11-25            # manual import
docker compose run --rm pipeline import-bulletin --from 2026-11-01 --to 2026-11-25   # backfill
docker compose run --rm pipeline import-bulletin --date 2026-11-25 --review approved --reviewer adrian --note "Testlauf"
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `import_failed` `auth_failed` | Token expired, wrong repository scope, or file unreadable for UID 1000 |
| `import_failed` `github_unavailable` | GitHub outage or rate limit; next cycle retries |
| `import_waiting` after 07:00 | Bulletin not pushed yet; retried every cycle |
| `import_failed` `invalid_document` / `unsupported_schema` | Upstream file; fix it there, the corrected revision is picked up automatically |
| Bulletin imported but not visible | Upstream status is staged (`draft`, `unverified`, `test_import_unverified`): approve explicitly or publish upstream |
| "Publication refused: N publishable articles" | `--inspect` the raw edition; approve single articles or publish manually with `--allow-partial` |
| "Generation budget used" | Recover the saved run; `EDITORIAL_FORCE_GENERATE=1` only deliberately |
| "Edition already published with different content" | Intended protection; `--replace` if the new version should supersede |
| Many `restricted` sources | Publisher blocks automated requests; not an error, articles need another reachable source or review |
| `LockTimeout` | Another publication/import is running; it is retried by the next run |

## Rollback

The 0.2 schema change is additive; code from `integration/mvp` ignores the new
tables, so rolling back code needs no database change.

```bash
cd /opt/unfold
git switch integration/mvp          # or: git checkout "$(cat ~/backups/deployed-before-….txt)"
docker compose build pipeline web && docker compose up -d pipeline web
# old publication scripts stop the pipeline container during publish again; that is expected
# only if data must be restored:
docker compose stop pipeline
docker compose exec -T db pg_restore -U prismunfold -d prismunfold --clean --if-exists < ~/backups/prismunfold-….dump
docker compose start pipeline
```

Editions published by 0.2 carry extra fields; the old frontend ignores them. Items
withheld by 0.2 stay withheld after a rollback (they are not in the exported JSON).
