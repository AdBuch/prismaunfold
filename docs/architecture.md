# Architecture

```
publisher feeds ──► feed desk ─────────────┐
(catalog, active only)   cluster, extract  │
                                           ▼
topics.txt ──► plan ──► collectors ──► report check ──► Story ──► verification ──► store
               (who writes what)  (agents)   (untrusted input)                  (PostgreSQL)
                    ▲                                                               │
                    └──────────── archive: earlier stories on the topic ◄───────────┤
                                                                                    ▼
                                             browser ◄── web (nginx) ◄── JSON ◄── compose edition
```

## One story model

Everything publishable is a `Story` (`src/prismunfold/models.py`): a headline and
sentences, each with the URLs of the sources backing it. Two producers write stories:

- **The feed desk** (`desk.py`) turns a cluster of feed articles into a story whose
  sentences are taken from the articles' own titles and excerpts.
- **Collector agents** (`collectors/`) research a topic and file a JSON report, which
  `reports.py` checks as untrusted input and turns into a story, or rejects.

One model means one archive, one verification path and one export.

## Verification

`verification.py` answers four questions separately: is there a well-formed citation,
does the URL answer, does the page support the sentence, do two independent
publishers support it. The result is one of `unverified`, `supported`, `disputed`,
`review_required`, per sentence and per story. Support is decided by a
`SupportChecker`; the only real one today is the extractive checker for feed-desk
stories. A checker that reads the cited page is the main missing piece.

## Editions

`compose.py` builds one edition per day, the same for every reader, and freezes it
once the day is over. Reader preferences are applied in the browser and stored only
there (`frontend/src/lib/prefs.ts`).

## The contract between pipeline and frontend

`export.py` writes static JSON under `site/api/v1/` in the shapes of
`frontend/src/models.ts`. The frontend's `ApiContentService` fetches and shape-checks
it. There is no application server in the read path; nginx serves files.

## Containers and trust boundaries

| Boundary | Rule |
| --- | --- |
| Agent to pipeline | Reports and status files are untrusted: size-limited, type-checked, never executed. The pipeline mounts them read-only |
| Pipeline to agent | Job list and prior coverage, mounted read-only into the collectors |
| Pipeline to web | Exported JSON, mounted read-only into nginx |
| Pipeline to internet | Feed fetches honour robots.txt; the link check refuses private addresses |
| Browser | Strict Content-Security-Policy; no third-party requests; all text escaped by the `html` template helper |

## Decisions and their reasons

- **Static JSON instead of an API server.** Reading is the hot path at scale and files
  behind a CDN are the cheapest way to serve it. A Go API is planned for writes.
- **Files on volumes between containers.** No queue, no Docker socket; a collector is
  a run-to-completion job that also fits a Kubernetes CronJob.
- **Frontend moved to `frontend/`**, so it no longer shares `src/` and `tests/` with Python.
- **The frontend stayed framework-free TypeScript** for this step, to connect what
  exists instead of rewriting it. The Angular port decided earlier is still open.
- **Sources stay `pending_review` in the repository.** Activating a publisher's feed
  is a rights decision for a person.
