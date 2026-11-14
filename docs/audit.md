# Repository audit and backlog

Audit of 14 November 2026, covering the branches `main`, `mvp/phase-1`,
`feature/collector-agents` and `feature/phase-2-frontend`. Work happened on
`integration/mvp`. Nothing was pushed to `main`.

Status words: **fixed** (done and covered by a test that runs in CI),
**partly** (done in part; the gap is named), **open**.

## What was there

| Branch | Content | State found |
| --- | --- | --- |
| `main` | Product README and the frontend brief | Documentation only |
| `mvp/phase-1` | Python feed pipeline: ingest, cluster, extractive summary, static HTML | Worked on fixtures; source catalog empty |
| `feature/collector-agents` | Collector images, report check, archive, PostgreSQL, Docker, CI | CI green with a stand-in agent; never run with a real agent |
| `feature/phase-2-frontend` | TypeScript newspaper prototype | Fictional fixtures only; never connected to the pipeline |

The two halves could not meet: the frontend lived at the repository root and shared
`src/` and `tests/` with the Python code, and the pipeline's JSON had a different
shape from the frontend's models.

## P0: blocks a working, trustworthy paper

| # | Finding | Status |
| --- | --- | --- |
| P0-1 | Frontend and pipeline were never connected; the frontend showed only fictional fixtures. | **fixed.** `ApiContentService` reads `site/api/v1`; the pipeline exports in the frontend's model shapes. The production bundle contains no fixture content (checked in CI). |
| P0-2 | Frontend and Python code collided in `src/` and `tests/`. | **fixed.** Frontend moved to `frontend/` in the merge. |
| P0-3 | `reports.py` crashed on wrong types. A report with `"sources": 5` or `"uncertainties": 3` raised `TypeError`, which `load_reports` did not catch, so one bad report stopped all others. | **fixed.** Every field is type-checked; any unexpected error rejects only that report. Adversarial tests feed every field every wrong type. |
| P0-4 | No size limit on report files; deep nesting, non-UTF-8 and `NaN` were not handled. | **fixed.** 256 KB limit, bounded reads, all rejected cleanly. |
| P0-5 | Report files were read through symlinks, and file names were not checked. | **fixed.** Regular files with plain names only. |
| P0-6 | Source URLs with embedded credentials, bare IP addresses, or control characters were accepted. | **fixed** in `public_url`. |
| P0-7 | Report timestamps were not checked; a report dated years ahead or behind was accepted. | **fixed.** Future-dated and week-old reports are rejected; implausible source dates are dropped. |
| P0-8 | The export labelled stories `reported` or `disputed` from one mixed list of "uncertainties". A single-publisher note alone made a story "disputed". Nothing separated "has a link" from "the link works" from "the source says so". | **fixed.** `verification.py` keeps citation, reachability, support and corroboration apart, with the states `unverified`, `supported`, `disputed`, `review_required`. A link alone never yields `supported`. |
| P0-9 | The frontend had no loading, empty or error state; an unreachable backend would have left a blank page. | **fixed.** All three exist; the browser test covers the empty and not-found paths. |
| P0-10 | CI reported a failing test as green (a pipe into `tee` hid the exit code). | **fixed** earlier on `feature/collector-agents`; every step now runs with `pipefail`. |

## P1: needed for the MVP to be useful

| # | Finding | Status |
| --- | --- | --- |
| P1-1 | Feed events and agent reports were two separate models with two exports. | **fixed.** Both are `Story`; one archive, one verification path, one export. |
| P1-2 | A feed event changed its id whenever another article joined, so the same event would be published again each time. | **fixed.** The id hangs on the earliest article; a growing event updates its story. |
| P1-3 | Every agent ran on every topic, with no budget. A failing topic was never retried. | **fixed.** Writers per topic are configurable and rotate; per-agent budget; three tries with growing pauses; job status files and `prismunfold status`. |
| P1-4 | No way to tell which agents are alive. | **fixed.** Workers write a heartbeat; only live agents get topics. |
| P1-5 | No edition composer; ranking was recency plus source count. | **partly.** `compose.py` balances sourcing, novelty, verification state, sections, regions, languages and publishers, and lifts lone thin voices. "Global importance" has no signal beyond the number of independent publishers. |
| P1-6 | No reader preferences. | **fixed.** Languages, regions, sections; stored in the browser only; the lead is never hidden and other stories stay reachable. |
| P1-7 | No real news source; the catalog was empty. | **partly.** Seven candidate feeds are in the catalog as `pending_review`. Activating them is left to a person, as the catalog rules require. See "Open risks". |
| P1-8 | Translation between German, English and Spanish. | **open.** Stories appear in the language they were written in. `NoTranslator` is still the only translator. |
| P1-9 | Checking that a source supports a sentence. | **open.** The `SupportChecker` interface exists; only the trivial extractive checker is implemented. Agent stories therefore never reach `supported`. |
| P1-10 | Cost reporting. | **partly.** Tries and seconds per job are reported. Token and money figures are not: the agent CLIs do not report them in a common form. |
| P1-11 | Local models. | **partly.** goose can be pointed at a local provider through `GOOSE_PROVIDER`; this has not been tried. There is no provider abstraction of our own. |
| P1-12 | Magazine and deep dives. | **partly.** The screen exists and shows an empty state; the pipeline does not write features yet. |

## P2: later

- No lockfile for the frontend; dependency versions float. Commit `package-lock.json`.
- Agent CLI versions are not pinned in the collector images.
- `editions.json` carries every edition in full; it needs paging before the archive grows.
- Old story files are never removed from `site/`.
- Corrections: the model and the screen support them, the pipeline never writes one.
- Clustering is title similarity within one language; the same event in German and English stays two stories.
- Collector containers are not read-only, because the agent CLIs write to their home directory.
- The Go API and an Angular port of the frontend, both decided earlier, are not started. The frontend is still framework-free TypeScript.
- Images are not published to a registry.

## Open risks

1. **No real agent has ever run.** Everything about the collectors is tested with a
   stand-in. Web search inside Codex, Vibe and goose, the Codex sandbox in a
   container, and the quality of real reports are unknown.
2. **Source rights are not cleared.** The candidate feeds are an engineer's guess at
   reasonable sources, kept to headline and link. Whether a public news site may
   show them is a question for each publisher's terms.
3. **`unverified` is the normal state of an agent story.** The paper says so on every
   story, but a reader may still take a cited sentence as checked.
4. **The link check has only run against stand-in responses.**
5. **Agent CLIs with web access run with their own permissions.** Capabilities are
   dropped and resources capped, but an agent can reach the internet by design.
