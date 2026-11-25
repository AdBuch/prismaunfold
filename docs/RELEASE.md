# Releases and production deployment

Production (server `unfold`, checkout `/opt/unfold`, user `adrian`) runs only
**releases**: a tag `vX.Y.Z` on a commit of `main` for which the GitHub Actions
workflow `CI` succeeded. A merge to `main` is not a deployment.

| Piece | Role |
| --- | --- |
| `.github/workflows/ci.yml` | Tests on every push (backend SQLite + PostgreSQL, frontend, browser, images, stack) |
| `.github/workflows/release.yml` | On a tag: checks "on main" and "CI green", publishes the GitHub release from `CHANGELOG.md` |
| `scripts/deploy-release.sh` | On the server: gate, backup, deploy, checks, automatic rollback |
| `deploy/unfold-update` | `~/bin/unfold-update`: runs the deploy script *of the release being deployed* |

## Making a release (maintainer)

1. Merge the reviewed pull request into `main`; wait for CI on `main` to be green.
2. Add the `## X.Y.Z` section to `CHANGELOG.md` in that pull request (the release
   workflow refuses a tag without it) and bump `pyproject.toml`.
3. Tag the merge commit and push the tag:

   ```bash
   git fetch origin && git tag -a vX.Y.Z -m "PrismUnfold X.Y.Z" origin/main && git push origin vX.Y.Z
   ```

4. The release workflow publishes the GitHub release once CI is green.

## What a deployment does

`unfold-update [vX.Y.Z]` (default: newest release on `main`):

1. **Gate** – refuses a non-release ref, a tag not on `origin/main`, a commit without a
   successful `CI` run, a checkout with locally modified tracked files, and runs while
   an editorial systemd job is active. Holds `~/.unfold-update.lock` (shared with
   `scripts/editorial.sh`, so no generation or publication overlaps a deployment).
2. **Backup** to `~/backups/prismunfold/<UTC>-<previous>-to-<tag>/` (mode 0700/0600):
   `db.dump` (`pg_dump -Fc`, checked with `pg_restore --list`, SHA-256 in `SHA256SUMS`),
   `site.tar.gz` (exported JSON), `config/` (`.env`, compose overrides, `config/topics.txt`),
   `manifest` (previous commit, image ids), `editions.count`.
3. **Images** – current `prismunfold/pipeline` and `prismunfold/web` are tagged
   `:rollback`.
4. **Switch** – `git checkout --detach <tag>`, `docker compose build pipeline web`,
   `docker compose up -d --no-deps pipeline web`. The database container keeps running;
   the additive schema upgrade runs when the pipeline starts.
5. **Checks** – web `/healthz` and app shell; containers `db`, `pipeline`, `web` running;
   database schema version ≥ 2; number of stored editions not smaller than before; a
   pipeline cycle after the switch; `api/v1/editorial/morgenbriefing.json` and
   `api/v1/daily/index.json` valid JSON; prism-data importer run (if configured);
   editorial timers enabled and identical to `deploy/systemd`; Codex login volume present.
6. **Rollback** – if a hard check fails, the previous commit and the `:rollback`
   images are restored automatically and checked again. Warnings (importer, timers,
   Codex volume) do not roll back but are reported.

Never touched: Docker volumes (`pgdata`, `site`, `shared`, `reports`,
`unfold_codex_auth`), `.env`, overrides, secrets, `~/.local/state/prismunfold/editorial`
(raw editions). `docker compose down` is never run.

Local configuration belongs in untracked files (`.env`, `docker-compose.override.yml`,
`config/topics.txt`). If `.env` sets `COMPOSE_FILE` (prism-data overlay), list the
override there too, otherwise Compose ignores it; the deploy script warns about this:
`COMPOSE_FILE=docker-compose.yml:deploy/compose.prism-data.yml:docker-compose.override.yml`.

## First production deployment of v0.2.0 (from `integration/mvp`)

Run on the server as `adrian`. Steps 1–3 change nothing.

```bash
# 1. Look at the current state (paste the output if anything is unexpected)
cd /opt/unfold
git status --short && git log --oneline -1 && git branch --show-current
cat ~/bin/unfold-update
docker compose ps
systemctl list-timers 'unfold-editorial-*' --no-pager
ls -la ~/.local/state/prismunfold/editorial/

# 2. Tracked files must be unchanged. If `git status --short` lists modified files (M),
#    save them and move local changes into an override instead of editing tracked files:
git diff > ~/unfold-local-changes-$(date +%F).patch

# 3. Install the new update command; the old one is kept
cp -p ~/bin/unfold-update ~/bin/unfold-update.legacy-$(date +%F)
git fetch --tags origin
git show v0.2.0:deploy/unfold-update > ~/bin/unfold-update && chmod 755 ~/bin/unfold-update

# 4. Deploy (backup, switch, checks, automatic rollback on failure)
unfold-update v0.2.0

# 5. Timers: the deploy output says whether the units differ from the installed ones
sudo bash /opt/unfold/scripts/install-editorial-timers.sh   # only if reported

# 6. Status of the deployment
unfold-update status
```

Not between 05:45 and 07:15 (the editorial jobs would be blocked by the lock).

### Enable the prism-data importer (independent of the AI workers)

```bash
install -d -m 700 ~/.config/prismunfold
( umask 077; read -rsp 'prism-data token: ' t && printf '%s' "$t" > ~/.config/prismunfold/prism-data.token; echo )
# the container user (UID 1000) must be able to read it; adrian is normally UID 1000:
id -u
# .env: add or extend (keep an existing override in the list)
#   COMPOSE_FILE=docker-compose.yml:deploy/compose.prism-data.yml
#   PRISM_DATA_SECRET_PATH=/home/adrian/.config/prismunfold/prism-data.token
docker compose up -d pipeline
docker compose run --rm pipeline import-bulletin --date 2026-11-25    # stores, does not publish (test_import_unverified)
docker compose logs --tail 50 pipeline | grep '"component": "bulletin"'
```

### Recover the editions of 24 and 25 November without a model call

```bash
cd /opt/unfold
E=~/.local/state/prismunfold/editorial
bash scripts/editorial.sh --status 2026-11-24; bash scripts/editorial.sh --status 2026-11-25

# 25 November (the AP-403 edition): inspect, preview, publish
bash scripts/editorial.sh --inspect $E/2026-11-25.7IyLAC/edition.json
bash scripts/editorial.sh --recover $E/2026-11-25.7IyLAC/edition.json
EDITORIAL_AUTO=1 bash scripts/editorial.sh --publish-existing $E/2026-11-25.7IyLAC/edition.json

# 24 November: two saved files; let the selector choose or name the file explicitly
PYTHONPATH=src python3 -m prismunfold.editorial select-candidate 2026-11-24 "$E"
bash scripts/editorial.sh --recover $E/2026-11-24.zIa6G9/edition.repaired.json
EDITORIAL_AUTO=1 bash scripts/editorial.sh --publish-existing $E/2026-11-24.zIa6G9/edition.repaired.json
#   already published with other content -> add --replace (old version stays as superseded)
#   too few publishable articles -> review, then: ... --publish-existing FILE --allow-partial --reviewer adrian

bash scripts/editorial.sh --status 2026-11-25    # withheld articles with reasons; approve single ones:
bash scripts/editorial.sh --approve 2026-11-25 <article_id> adrian "Quelle manuell geprüft"
```

Raw files are never modified; previews go to `recovery-<UTC>/` next to them.

### Verify after the deployment

```bash
unfold-update verify                                   # the same checks as during deploy
curl -fsS http://localhost:8080/api/v1/daily/index.json | python3 -m json.tool | head -30
docker compose logs --since 15m pipeline | grep -E 'cycle start|"event"' | tail -20
systemctl list-timers 'unfold-editorial-*' --no-pager
journalctl -u unfold-editorial-generate.service -u unfold-editorial-publish.service --since today --no-pager
```

The next morning: 06:00 generate (or recover), 07:00 publish, prism-data import from
07:00 in the pipeline log.

## Rollback

```bash
unfold-update rollback          # previous commit + :rollback images, then checks
```

The database stays as it is: 0.2 only added tables, which older code ignores. Only if
data itself must be reset:

```bash
unfold-update status            # shows the backup of the last deployment
unfold-update restore-db ~/backups/prismunfold/<dir> --yes
```

Manual fallback without the script: `git checkout --detach <previous commit from the
backup manifest>`, `docker image tag prismunfold/pipeline:rollback prismunfold/pipeline:latest`
(same for `web`), `docker compose up -d --no-deps pipeline web`. The legacy update
command is still available as `~/bin/unfold-update.legacy-<date>`.

## Recommended next step

Protect `main` on GitHub (require the CI checks and a pull request) so the rule
"only reviewed, tested code becomes a release" is enforced by GitHub as well.
