# Collectors

Four Docker images, one per agent CLI. Each runs once, researches one topic on the
web, writes one evidence-linked report as JSON and exits.

| Image | Agent | Credentials |
| --- | --- | --- |
| `prismunfold/collector-codex` | OpenAI Codex CLI | `OPENAI_API_KEY` |
| `prismunfold/collector-claude` | Claude Code | `ANTHROPIC_API_KEY` |
| `prismunfold/collector-vibe` | Mistral Vibe | `MISTRAL_API_KEY` |
| `prismunfold/collector-goose` | goose | `GOOSE_PROVIDER`, `GOOSE_MODEL`, provider key |

All four share `common/collect.sh`, the assignment in `common/assignment.md` and the
output contract in `common/report.schema.json`. Only the CLI call differs.

## Run

```sh
cd collectors
cp .env.example .env        # fill in keys and TOPIC
mkdir -p out && chmod 777 out
docker compose run --rm claude
```

Output: `out/<edition>/<agent>/report.json` and `agent.log`. Exit code 0 means a
report file exists; it does not mean the report is valid.

Scheduled on one host, from the host's crontab (not cron inside the container):

```
5 */6 * * * cd /srv/prismunfold/collectors && TOPIC="..." docker compose up
```

On Kubernetes, use one CronJob per agent with the same image, env from a Secret
and a volume (or object storage) mounted at `/out`.

## Status and known gaps

These files are a first draft and have **not been built or run yet**.

- **Web search per agent is unverified.** Claude Code is given its web tools
  explicitly. Whether Codex, Vibe and goose can search the web out of the box, or
  need a flag, config or an MCP search extension, must be checked on first run.
  `AGENT_ARGS` passes extra flags through.
- **Sandboxing:** Codex's own sandbox may not work inside a container; it may need
  a different sandbox flag via `AGENT_ARGS`.
- **Validation is not in the image.** The pipeline must validate each report
  against the schema and reject sentences without a source before anything is
  published.
- **Versions are not pinned.** Set the build args (`CODEX_VERSION`,
  `CLAUDE_CODE_VERSION`, `VIBE_VERSION`, `GOOSE_TAG`) once a working set is known.
- **Cost limits** exist only as `MAX_TURNS` (Claude, Vibe). Set spending limits
  on the provider side as well.
