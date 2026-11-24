# PrismUnfold – vision, architecture & progress

## Mission
A personal news assistant that grows into an independent editorial portal and ultimately an open platform. Reduce information overload, disclose AI involvement and uncertainty, support independent journalism, compare perspectives, avoid fake news and make sources visible without turning the newspaper into a link directory.

## Product target
Classic Editorial + Modern Magazine + My PrismUnfold. Distinct editions from ChatGPT/Codex, Claude and Mistral, alongside the aggregated evidence-linked feed desk. A finite daily newspaper, a researched magazine feature, publication archives, reader preferences and transparent sourcing. Long-term: shareable mixes, original journalism, sustainable funding. These are goals, not delivered features.

## Current infrastructure (reported 2026-11-24)
- [x] Proxmox VM 107, Debian, 4 GB RAM, 32 GB disk; internal LAN.
- [x] PostgreSQL 16, pipeline and web Docker services running; fresh installation, previous laptop backup retained.
- [x] Git deploy key and manual update script; branch integration/mvp. Full update/rollback verification remains necessary.
- [x] Codex CLI subscription login persists in external auth volume; smoke inference confirmed.
- [x] First sentence-list bulletin generated; exposed editorial quality gap and link validation failures.
- [ ] Claude Code and Mistral Vibe authentication and dry runs; Goose optional.
- [ ] Jump-host/WireGuard route verification, Caddy forwarding, unfold.krokero.ch DNS/TLS; no public exposure until approved.

## Editorial milestone (this branch)
Canonical target: [Morgenbriefing Weltlage](EDITORIAL_SPEC.md), supplied 2026-11-24. The executable prompt v4 is derived from this specification.
- [x] Versioned German editorial instructions; coherent news articles plus standalone long-form magazine.
- [x] Separate editorial namespace in existing editions table, static JSON export and dedicated newspaper route.
- [x] Explicit dry-run / publish-existing workflow; no second model call, no auto-publication.
- [x] Recent headline history passed to writer; independent source links retained per paragraph.
- [ ] CI and end-to-end verification on Proxmox, editorial acceptance versus original ChatGPT briefing.
- [x] Exact editorial rubrics and optional source-linked Random des Tages / four-category Lagebild in edition model and UI.
- [ ] Travel personalisation from private configuration, target length calibrated against an original issue, reliable continental rotation.
- [ ] Stronger independent claim verification; link reachability is not truth. Source rights review and network egress restrictions.
- [ ] Separate research and writing stages, automated repetition controls, broader permitted sources.
- [ ] Independent provider adapters and publication selector; daily 07:00 Europe/Zurich scheduler only after acceptance.

## Architecture
Laptop / GitHub → manual deployment → Proxmox VM → Docker Compose. Existing feed pipeline and collectors use shared/reports/site volumes. Editorial Codex uses an isolated container with its own persistent auth volume; outputs a staged JSON edition. Python validates, stores an independent edition in PostgreSQL and exports a static JSON API. UI renders news as coherent articles with a separate magazine and date archive. No database access from the model container. Keep secrets outside Git. Restrict model network access and public routes before exposing service.

## Acceptance and operations
After merging and deploying, run `bash scripts/editorial.sh --dry-run`; read preview.json, compare content with the original morning briefing, check every major claim and the feature's coherence. Then use the printed publish-existing command and open /morgenbriefing. Verify the edition persists after a pipeline restart and a Git update; rerunning publish for the same date must refuse overwrite. Monitor memory, token allowance and runtime. Do not enable the other collectors automatically. The original scheduled ChatGPT briefing remains independent until replacement is accepted.

## Decision log
- 2026-11-23: One VM, Docker Compose, 4 GB initial RAM; fresh installation because laptop data only two days old.
- 2026-11-24: Existing Codex subscription CLI reused; first sentence-based output rejected as product direction. Dedicated editorial edition with full prose and magazine, not simply a report collector. Keep feed desk and existing reports separate.
- Next: record test results, commit/PR references and changes to acceptance criteria here. Never mark a runtime milestone complete until observed.

## Deployment regression 2026-11-24
The merged editorial build reported EACCES importing editorial.py, and the user reported missing UI styling. Verified original stylesheet remains byte-for-byte intact as prefix of current CSS. Docker image source/static artifact modes are now normalised; runtime confirmation pending. Deploy as the normal deployment user (not sudo), keep umask 022 for Git checkout, and verify CSS HTTP 200/text-css plus Python import before generating an edition. Configuration bind mounts retain host permissions; do not recursively expose secrets or authentication volumes.

## Editorial reading experience v4
Three levels: complete daily newspaper, internal thematic reading and edition history, external original reporting. Paywalled sources may be supplementary references; accessible evidence is required, explicit catalogue exclusions remain, no access circumvention. Broad research is subject to source rights. Codex remains the only configured editorial runner. No shell needed, sandbox unchanged. UI uses original PrismUnfold palette and typography. Runtime acceptance pending.
