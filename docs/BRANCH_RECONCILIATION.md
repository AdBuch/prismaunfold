# Branch reconciliation (milestone 0.1)

Audit date: 25 November 2026. All remote references were fetched again; the
statuses from the earlier audit were re-checked against the actual commits and
diffs, not commit messages. Pull requests could not be listed from the audit
session (no GitHub API access), so this report covers branches only.

Consolidation branch: `feature/consolidation-0.1-0.2`, created from
`integration/mvp` (`3265107`). Nothing was force-pushed, no history was rewritten,
no remote branch was deleted.

## Findings

| Branch | Tip | Ahead of `integration/mvp` | Behind | Verdict |
| --- | --- | --- | --- | --- |
| `integration/mvp` | `3265107` (25 Nov) | – | – | Baseline. Current deployment branch; has structured Codex output, resilient source validation, edition recovery |
| `main` | `e44cedd` (25 Nov) | 3 | 78 | Merged. Diverged at `956a5aa`; the 3 commits only add files |
| `feature/prism-data-import` | `f5cc143` (25 Nov) | 1 | 5 | Merged (one conflict), then hardened |
| `fix/editorial-quality` | `6c30885` (24 Nov) | 1 | 32 | Merged; research brief kept, code superseded, re-ported |
| `feature/collector-agents` | – | 0 | 72 | Fully contained. Nothing to do |
| `feature/editorial-morning-edition` | – | 0 | 37 | Fully contained. Nothing to do |
| `feature/phase-2-frontend` | – | 0 | 72 | Fully contained. Nothing to do |
| `mvp/phase-1` | – | 0 | 79 | Fully contained. Nothing to do |

No other remote branch exists.

## Per-branch decisions

### `main` (3 commits, 25 Nov)

| Change | Decision | Reason |
| --- | --- | --- |
| `config/morgenbriefing-editorial.json` | **Retained** | The upstream bulletin's editorial brief (rubrics, rotation, extras). Reference for comparing the Codex brief with the ChatGPT bulletin |
| `tools/import_morgenbriefing.py` | **Superseded, removed** | A second importer for the same file with a schema-less input shape, no persistence, no revision handling and no pipeline integration (its own doc said so). `bulletin.py` is the canonical importer |
| `docs/morgenbriefing-source.md` | **Superseded, removed** | Its rules (secondary source, no independent confirmation, continue without the file, never overwrite history silently, secrets only at runtime) are implemented and documented in `docs/PRISM_DATA.md` |

Merging `main` (rather than cherry-picking) means the consolidation branch contains
`main`'s history, so a pull request into `main` has no divergence.

### `feature/prism-data-import` (1 commit, 25 Nov)

Kept almost entirely: `bulletin.py`, the `import-bulletin` CLI, the compose overlay
with a file secret, the CSP change for rights-cleared images, the importer tests,
the frontend coverage/perspective/image rendering, atomic `_write`, and
`get_edition` / `save_edition_revision` in both stores.

- Conflict in `frontend/src/views/editorial.ts`: resolved by keeping the importer's
  structure and re-adding `integration/mvp`'s "Prüfbedürftig" and link-status markers.
- Adapted afterwards: error codes, contributions/provenance, operator review,
  backfill, local-file import, image rights moved to `images.py`, matching moved to
  `dedupe.py`, acceptance of the real schema 1.1 export (null fields, `editorial_cutoff`).

### `fix/editorial-quality` (1 commit, 24 Nov)

Based on an editorial version from before the structured-output and resilient-
validation work; its `editorial.py`/`editorial.sh` conflict with that work (old
domain allow-list, all-or-nothing validation, free-form JSON).

| Change | Decision | Reason |
| --- | --- | --- |
| `config/editorial/research.md` | **Retained** | Research-stage brief |
| Research/writing split (`prepare_research`, two Codex calls) | **Adapted** | Re-implemented on the new source classification as `EDITORIAL_STAGES=split` (experimental) with a reusable dossier; the single structured call stays default |
| Root route shows the Morgenbriefing; nav relabel | **Deferred to 0.3** | Reader-facing navigation belongs to "one newspaper, one daily edition"; current URLs stay |
| `EDITORIAL_SPEC.md` / `PROJECT.md` text | **Superseded** | Described the split as the default; docs rewritten |

## Overlapping implementations resolved

| Problem | Before | Canonical now |
| --- | --- | --- |
| Importing the prism-data bulletin | `tools/import_morgenbriefing.py` and `bulletin.py` | `bulletin.py` |
| Codex morning edition | `scripts/bulletin.sh` (sentence-list report via the agent-report desk) and `scripts/editorial.sh` (full edition) | `scripts/editorial.sh`; `bulletin.sh` deprecated, kept for saved runs |
| Source checks | `http_probe` (bool) and `http_status` (string) with a combined `unsafe_or_unresolved` | `linkcheck.check_source` with nine statuses; `http_probe` kept as a wrapper |
| Publication gate | Duplicated in `editorial.py` and `editorial-scheduled.sh` | `editorial.apply_policy`, configured in `config/config.json` |
| Recovery candidate | Last glob match in `editorial-scheduled.sh` | `editorial select-candidate` (deterministic) |
| Matching bulletin items to existing coverage | Inside `bulletin.py` | `dedupe.py`, shared |

## Database and API compatibility

- Additive only: tables `contributions` and `schema_migrations` (`CREATE IF NOT EXISTS`).
  Existing rows are read as before; editions stored before 0.2 (no `article_id`,
  no `state`, old `unsafe_or_unresolved` link status) still export and render.
- `api/v1/editorial/morgenbriefing.json` keeps its shape; items gain optional fields
  (`article_id`, `state`, `review_reasons`, `provenance`, `approval`). Withheld items
  never appear in it.
- New: `api/v1/daily/index.json` and `api/v1/daily/{date}.json` (docs/API.md).

## Path to `main` as the authoritative branch

1. Review and merge the pull request `feature/consolidation-0.1-0.2` → `main`
   (no divergence: `main` is already merged into it).
2. Deploy from `main`: on the server, `git fetch && git switch main` in `/opt/unfold`
   (docs/OPERATIONS.md, "Deploy"). Keep `integration/mvp` untouched as the rollback point.
3. After one week of stable operation, protect `main` (required CI checks, no direct
   pushes) and stop deploying `integration/mvp`. Deleting the merged feature
   branches is then optional and an owner decision.
