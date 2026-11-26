# PrismUnfold – vision, roadmap and status

This is the single roadmap. Architecture: [architecture.md](architecture.md).
Editorial target: [EDITORIAL_SPEC.md](EDITORIAL_SPEC.md). Workflow and labels:
[EDITORIAL_WORKFLOW.md](EDITORIAL_WORKFLOW.md). Operations: [OPERATIONS.md](OPERATIONS.md).

## Product vision

PrismUnfold is a personalised digital newspaper, not a news aggregator and not a set
of separate AI publications. Four experiences:

- **Today's Edition** – one coherent daily newspaper per date.
- **Magazine** – long-form reports, investigations and thematic deep dives.
- **Archive** – historical daily editions and their articles.
- **My PrismUnfold** – interests, followed topics, curated collections.

RSS publishers, ChatGPT (prism-data bulletin), Codex, Claude, Mistral and other workers
*contribute* to the same newspaper. The Morgenbriefing is an editorial contribution to
the daily edition, not a newspaper of its own; long-form contributions move into the
Magazine. AI involvement, sources and uncertainty are disclosed; nothing is labelled
verified because a link exists.

## Roadmap

| Milestone | Content | Status |
| --- | --- | --- |
| 0.1 Repository and architecture consolidation | Branches reconciled, one canonical implementation, coherent docs, CI gates | **Implemented** on `feature/consolidation-0.1-0.2`; PR to `main` pending review |
| 0.2 Reliable editorial and ingestion pipeline | prism-data import, provenance, source classification, granular states, recovery, scheduling, unified daily API, image rights | **Implemented and tested in CI fixtures; not yet verified on the production VM** |
| 0.3 One newspaper, one daily edition, one Magazine | Today's Edition unifies Morgenbriefing and feed edition; article layers; The World, Magazine, Topics, Voices, My PrismUnfold; reader profile and deterministic composer | **Implemented on `feature/0.3-unified-newspaper`** (PR pending); product architecture: [PRODUCT.md](PRODUCT.md) |
| 0.4 Accounts, personalisation and social | Accounts and synchronised settings, publisher follows, collections and shareable mixes, verified journalist profiles, interface languages | Planned |
| 0.5 Release engineering | Release automation, visual regression, production CD | Partly: release gate, gated deployment with backup and rollback (v0.2.0); visual regression and CD planned |

## Status by capability

**Implemented** – feed desk (RSS ingest, clustering, extractive stories); agent report
desk with hostile-input checks; PostgreSQL/SQLite stores; static JSON API; Codex
editorial edition with structured output; per-article states and publication policy;
source accessibility classification with retries, cache and SSRF pinning; prism-data
import with revisions, review and backfill; contributions with provenance; deterministic
dedupe; image rights; unified daily edition JSON; AI-free recovery commands;
structured logs; systemd timers and in-container loop.

**Experimental** – research/writing split for Codex (`EDITORIAL_STAGES=split`);
subscription logins for Claude Code and Codex collectors.

**Implemented in 0.3** – one reader-facing newspaper over canonical articles; layered article page; device-local reader profile, onboarding and deterministic personal edition with coverage gaps; dossiers; Voices records; rights-based image rendering; page metadata; 0.2 URL redirects.

**Planned** – accounts and synchronisation; pipeline indexes for topics, magazine, authors and the World (PIPELINE_INTERFACE.md); aggregated coverage-gap signals; server-side rendering for crawlers; claim-level checker that reads cited pages; Claude/Mistral as edition
writers; short news briefs; editor UI for approvals; travel preferences from private
config; continental rotation; translation EN/ES/DE; Angular port and Go write API
(decided, not started).

**Deprecated** – `scripts/bulletin.sh` (sentence-list Codex bulletin via the report
desk), superseded by `scripts/editorial.sh`.

## Infrastructure (reported 2026-11-24)

- Proxmox VM 107, Debian, 4 GB RAM, 32 GB disk; internal LAN only.
- PostgreSQL 16, pipeline and web containers; checkout `/opt/unfold`; deploying user `adrian`.
- Codex CLI subscription login persists in the `unfold_codex_auth` volume.
- Open: Claude Code / Mistral Vibe authentication; WireGuard/jump host, Caddy,
  `unfold.krokero.ch` DNS/TLS – no public exposure until approved.

## Acceptance still to observe on the VM

1. Deploy the consolidation branch, check schema version 2 and `api/v1/daily/index.json`.
2. Enable the prism-data token; observe `import_waiting` before and `import_completed` after the push.
3. Recover the 24 and 25 November raw editions without a model call (OPERATIONS.md).
4. Let the 06:00/07:00 timers run one day; check `journalctl` and the published edition.
5. Compare edition quality with the ChatGPT bulletin.

## Decision log

- 2026-11-23: One VM, Docker Compose, 4 GB RAM; fresh installation.
- 2026-11-24: Codex subscription CLI reused; dedicated editorial edition with full prose
  and magazine instead of sentence lists. Publication 07:00 Europe/Zurich by timer.
- 2026-11-25 (0.1/0.2): `integration/mvp` is the consolidation baseline; `main` becomes
  authoritative after the consolidation PR. Validation is granular: a 403 never rejects
  an edition; a failed magazine makes the edition partial. Contributions keep provenance
  in an additive `contributions` table instead of per-provider newspaper models.
  prism-data staged statuses are never rewritten; approval is explicit and bound to the
  content hash. Publication no longer stops the pipeline; a database lock serialises it.
  One model run per day by default. Details: [BRANCH_RECONCILIATION.md](BRANCH_RECONCILIATION.md).

## Historical notes

- 2026-11-24 deployment regression (EACCES importing `editorial.py`, missing CSS):
  image file modes normalised; deploy as the normal user with umask 022.
- The audit of 14 November 2026 ([audit.md](audit.md)) is kept as a record; its
  backlog is superseded by this roadmap.
