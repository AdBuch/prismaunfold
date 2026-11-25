# Architecture

Status words: **implemented**, **experimental**, **planned** (see [PROJECT.md](PROJECT.md)).

## Data flow

```text
RSS / original publishers ──► feed desk (ingest, cluster, extract) ─────────┐
prism-data (ChatGPT bulletin) ──► bulletin importer ──────────────────────┐ │
Codex (/ Claude / Mistral) editorial worker ──► editorial validation ───┐ │ │
topic collectors (codex, claude, vibe, goose) ──► report desk ────────┐ │ │ │
                                                                      ▼ ▼ ▼ ▼
                                                   normalised contributions + provenance
                                                                      │
                                               dedupe / topic matching (deterministic)
                                                                      │
                                source accessibility + editorial states + policy
                                                                      │
                                                                 PostgreSQL
                                                                      │
                                                          edition composition
                                                                      │
                           static JSON: daily edition · Morgenbriefing · stories · archive
                                                                      │
                                                     nginx ──► browser (TypeScript)
```

## Components and responsibilities

| Component | Code | Responsibility | Status |
| --- | --- | --- | --- |
| Source ingestion | `ingest.py`, `normalize.py`, `pipeline.py`, `catalog/` | Read active feeds only, canonical URLs, robots.txt | Implemented |
| Topic clustering | `cluster.py`, `desk.py` | Feed articles → event clusters → extractive stories | Implemented |
| Agent report desk | `plan.py`, `reports.py`, `collectors/` | Assign topics, check untrusted agent reports, store stories | Implemented |
| External bulletin import | `bulletin.py` | prism-data fetch, schema validation, revisions, review, backfill | Implemented |
| AI editorial workers | `scripts/editorial.sh`, `config/editorial/` | Codex edition (single call; split stages experimental) | Implemented / experimental |
| Normalisation & provenance | `contributions.py` | Provider-independent contribution records, states, raw documents | Implemented |
| Deduplication | `dedupe.py` | Same-event matching without model calls; coverage attachment | Implemented |
| Editorial validation & policy | `editorial.py` | Per-article states, publication policy, approve/reject, recovery | Implemented |
| Evidence & source validation | `linkcheck.py`, `verification.py` | Accessibility (nine statuses, SSRF-safe); citation/support/corroboration for stories | Implemented; page-reading checker planned |
| Image metadata & rights | `images.py` | Display decision from rights, AI labelling | Implemented |
| Persistence | `storage.py`, `storage_pg.py` | Stores, additive schema, cross-process locks | Implemented |
| Daily edition composition | `compose.py` (feed edition), `bulletin.merge_editions` + `daily.py` (editorial) | One logical edition per date | Implemented (API); UI in 0.3 |
| Magazine | `magazine` items in editions, `daily.magazine` | Long-form features with provenance | Implemented in API; own model and UI in 0.3 |
| API export | `export.py`, `editorial.export_editorial`, `daily.py` | Atomic static JSON | Implemented |
| Frontend | `frontend/` | Renders edition, Morgenbriefing, stories, archive | Implemented; unified UI in 0.3 |
| Scheduling | `docker/pipeline/scheduler.sh`, `deploy/systemd/`, `scripts/editorial-scheduled.sh` | Loop every 10 min; 06:00/07:00 timers | Implemented |
| Monitoring | `oplog.py`, `run.json` | Structured JSON events | Implemented; metrics/alerts planned |

## Contributions versus published content

Every contribution is stored as received (`contributions` table, raw document, hash,
state history). Published content is a separate, composed view:

- `editions` row `editorial|morgenbriefing|{date}` – the published editorial edition
  (published articles plus a `withheld` list that is never exported).
- `editions` row `bulletin|morgenbriefing|{date}` – the current prism-data revision
  (plus an optional operator review bound to its hash).
- `editions` rows `daily|{date}` – the feed-desk daily edition (unchanged).
- Export merges editorial edition, bulletin and matching agent stories into
  `api/v1/editorial/morgenbriefing.json` and `api/v1/daily/{date}.json`.

There is no per-provider newspaper model; provider identity is provenance.

## Database model

| Table | Content | Since |
| --- | --- | --- |
| `articles` | Feed articles (canonical URL unique) | 0.0 |
| `stories` (+ `story_index`/tsvector) | Feed-desk and agent stories; archive search | 0.0 |
| `editions` | Frozen feed editions, editorial editions, bulletin revisions (JSON) | 0.0 |
| `contributions` | Every received contribution revision with provenance and state; unique per `(source_key, content_hash)` | 0.2 |
| `schema_migrations` | Applied schema versions (1, 2) | 0.2 |

Migrations are additive (`CREATE … IF NOT EXISTS`) and run when a store opens; there
is no destructive migration. Rolling back code needs no schema change.

## Trust boundaries

| Boundary | Rule |
| --- | --- |
| Agents / workers → pipeline | Untrusted input: size limits, type checks, never executed; reports mounted read-only |
| Codex editorial container | Own auth volume, read-only sandbox, no database, no Docker socket, no repository credentials |
| prism-data token | Only the pipeline container, as a Compose secret; requests only to `api.github.com`, no redirects |
| Pipeline → internet | Feeds honour robots.txt; source checks only to public addresses, connection pinned, redirects re-validated |
| Pipeline → web | Exported JSON, mounted read-only into nginx |
| Browser | Strict CSP; images only from HTTPS with display rights; text escaped by the `html` helper |

## Decisions

- **Static JSON instead of an API server** for reading; a Go write API is planned.
- **Files on volumes between containers**, no queue, no Docker socket.
- **Docker Compose on one small VM**; no Kubernetes/Kafka/Elasticsearch until a
  requirement is demonstrated.
- **Deterministic matching** before any model call; **granular states** instead of
  all-or-nothing validation; **idempotent, lock-protected publication**.
- **Frontend stays framework-free TypeScript** until 0.3; the Angular port is decided
  but not started.
- **Sources stay `pending_review`** in the repository; activation is a person's rights decision.
