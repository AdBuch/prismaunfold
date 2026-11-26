# Changelog

Releases are tags `vX.Y.Z` on `main` whose CI succeeded (docs/RELEASE.md).
Only releases are deployed to production.

## Unreleased (0.3.0)

One newspaper (docs/PRODUCT.md).
- Today's Edition combines the editorial daily edition (Codex, prism-data) and the feed
  desk's edition; the Morgenbriefing is no longer a separate publication.
- Navigation: Today, The World, Magazine, Topics, Archive, My PrismUnfold.
- Article pages unfold in layers: overview, article, context, perspectives, evidence.
- Device-local reader profile with onboarding; deterministic personal edition that keeps
  the day's important news, limits repetition, keeps a discovery share and lists
  coverage gaps instead of inventing content (docs/READER_PROFILE.md).
- Dossiers, Voices pages (labelled as assembled records), unified Magazine, archive over
  all editions; images only with rights, AI illustrations labelled.
- Canonical links, Open Graph, `noindex` for personal pages; 0.2 URLs redirect.
- Interface contract for the editorial pipeline (docs/PIPELINE_INTERFACE.md).
- No backend or database change.

## 0.2.0

First production release from `main`. Consolidates the repository (milestone 0.1) and
makes the editorial and ingestion pipeline reliable (milestone 0.2). Pull requests #2
and #3.

### Consolidation (0.1)
- `main` is the authoritative branch; `integration/mvp`, `feature/prism-data-import`,
  `fix/editorial-quality` and `main` reconciled (docs/BRANCH_RECONCILIATION.md).
- One canonical path per concern; `scripts/bulletin.sh` deprecated, the standalone
  Morgenbriefing adapter removed.
- Canonical documentation: PROJECT, architecture, EDITORIAL_WORKFLOW, API,
  OPERATIONS, PRISM_DATA, RELEASE.

### Editorial and ingestion pipeline (0.2)
- prism-data import (`AdBuch/prism-data`): independent of the AI workers, from 07:00
  Europe/Zurich, idempotent, corrections and revision protection, backfill, explicit
  review for unverified bulletins, error codes.
- Contributions with provenance (`contributions` table, additive schema version 2).
- Source accessibility with nine statuses, retries, cache, SSRF-safe pinned connections,
  30 s limit per URL. HTTP 403 no longer rejects an edition.
- Per-article editorial states and explicit publication policy; failed magazine makes
  an edition partial instead of failing it; approve/reject/revalidate single articles.
- Recovery of saved editions without a model call; one generation per day by default.
- Publication without stopping the pipeline (database lock).
- Unified daily edition API `api/v1/daily` (foundation for 0.3); existing endpoints unchanged.
- Image rights handling; deterministic deduplication; structured JSON logs.

### Release and deployment
- `scripts/deploy-release.sh` and `deploy/unfold-update`: only CI-verified release tags
  on `main` are deployed; database, site and configuration backup before every
  deployment; post-deployment checks; automatic rollback of code and images.
- Release workflow publishes GitHub releases only for verified tags.

### Upgrade notes
- Database: additive (`contributions`, `schema_migrations`); created on pipeline start.
- `scripts/editorial.sh --publish-existing` no longer stops the pipeline container.
- Install the new `~/bin/unfold-update` (docs/RELEASE.md). The previous script is kept.

### Not verified in production at release time
- Everything above was tested in CI with fixtures; the first production deployment
  and the recovery of the 24/25 November editions are part of the deployment runbook.
