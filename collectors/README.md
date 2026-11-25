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

The normal way is the stack in the repository root (`docker compose up`, see the
main README): there each collector runs `common/worker.sh`, which works through
the pipeline's job list. The commands below run a single agent on a single topic
by hand, which is useful for trying out an agent.

```sh
cd collectors
cp .env.example .env        # fill in keys and TOPIC
mkdir -p out && chmod 777 out
docker compose run --rm claude
```

Output: `out/<edition>/<agent>/<topic>.json` and `<topic>.log`. Exit code 0 means a
report file exists; it does not mean the report is valid.

A whole edition, all agents on all topics, including checking and export:

```sh
cp ../config/topics.example.txt ../config/topics.txt   # one line per topic: <language>|<topic>
./run-edition.sh
```

`run-edition.sh` first asks the pipeline for our earlier coverage of each topic
(`context/prior.md`), which the agents get appended to their prompt, and finally
runs `prismunfold reports` to check, store, index and export what they wrote.

Scheduled on one host, from the host's crontab (not cron inside the container):

```
5 */6 * * * /srv/prismunfold/collectors/run-edition.sh
```

On Kubernetes, use one CronJob per agent with the same image, env from a Secret
and a volume (or object storage) mounted at `/out`.

## Status and known gaps

The images have **not been built or run yet**. The entrypoint script was run once
outside Docker with a stand-in agent, and its report passed through the pipeline.

- **Web search per agent is unverified.** Claude Code is given its web tools
  explicitly. Whether Codex, Vibe and goose can search the web out of the box, or
  need a flag, config or an MCP search extension, must be checked on first run.
  `AGENT_ARGS` passes extra flags through.
- **Sandboxing:** Codex's own sandbox may not work inside a container; it may need
  a different sandbox flag via `AGENT_ARGS`.
- **Validation is not in the image.** `prismunfold reports` checks structure and
  drops sentences without a source URL. `--check-links` also opens the cited
  URLs; that code is tested with stand-in responses only, not against the live web.
- **Agents run one after another** per topic. Running them in parallel is a
  later optimisation.
- **Versions are not pinned.** Set the build args (`CODEX_VERSION`,
  `CLAUDE_CODE_VERSION`, `VIBE_VERSION`, `GOOSE_TAG`) once a working set is known.
- **Cost limits** exist only as `MAX_TURNS` (Claude, Vibe). Set spending limits
  on the provider side as well.
