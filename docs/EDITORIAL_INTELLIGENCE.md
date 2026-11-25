# Editorial Intelligence Foundation (EI-01)

**Status:** isolated opt-in vertical slice on feature/editorial-intelligence-foundation.
**Production:** disabled. The consolidated 0.1/0.2 ingestion, prism-data importer, daily publication and milestone 0.3 frontend are unchanged.

## Purpose and architecture

The existing platform has same-language RSS clustering, limited citation checking, contributor provenance, and a shared daily API. Those foundations do not establish whether a claim is genuinely supported by a source, nor do they provide continuous, reusable event dossiers.

The first EI slice adds:

    Permission-reviewed structured documents (DE / ES / EN ...)
      -> explicit stable event identity + source lineage
      -> claim/evidence references and gap analysis
      -> durable targeted research jobs
      -> reusable internal event dossier
      -> structured article drafts
      -> named human claim-link review
      -> multilingual prepared articles in shared content pool
      -> cached selection for different readers

This module is not a competing newspaper, a web crawler, or a new default model worker. It does not make external model or search calls.

## Delivered components

| Responsibility | Code | Status |
| --- | --- | --- |
| Processing rights and structured source ingestion | intelligence.py validate_document(), ingest() | Working with approved structured inputs |
| Stable events and source lineage | intelligence.py dossier() | Explicit event keys; original_work_id for syndication |
| Claim/evidence references | dossier() | Structured claims and locators; evidence NOT automatically verified |
| Research jobs | ei_store.py, plan_research(), run_research() | Persistent leases, retries, expiry and dead-letter state |
| Replaceable providers | Callback signatures for researcher and writer | Mocked/configurable, no live adapter yet |
| Human editorial review | approve() | Every published claim linked to a checked original document |
| Revision history | ei_records snapshots | Immutable publication revisions |
| Multilingual shared pool | content_pool(), export_pool() | Only approved variants; shared claim IDs |
| Reader composition | reader_edition(profile) | Selects cached variants, never regenerates facts |

The root of a news item is an event, not a source article. Two language-specific documents can share one event only if assigned the same explicit event_key; semantic multilingual matching is planned, NOT implemented here. Different event keys are never merged on superficial topical similarity.

## Input contract

A source document must contain: event_key, source_id, headline, URL, language, timezone-aware published_at, source_type, original_work_id, rights, and a claims array. A claim needs key, statement, kind (fact, attributed, analysis, forecast or opinion), relation (supports or contradicts), and a specific evidence locator. Optional metadata: excerpt, topics, regions, origin_type. Rights.ai_processing must explicitly be true. Rights.store_excerpt must explicitly be true to retain any excerpt. Unknown permissions are rejected.

Example of illustrative, NOT real-world evidence:

    {
      "event_key": "fictional-event-2026-11-25",
      "source_id": "illustrative-source",
      "url": "https://example.org/vote",
      "headline": "Example parliamentary record",
      "language": "en",
      "source_type": "official_document",
      "origin_type": "original_publisher",
      "original_work_id": "imaginary-record",
      "published_at": "2026-11-25T12:00:00+01:00",
      "rights": {"ai_processing": true, "store_excerpt": false},
      "topics": ["politics"],
      "regions": ["CH"],
      "claims": [{"key": "vote", "statement": "A fictional proposal passed.",
                  "kind": "fact", "relation": "supports",
                  "locator": "Example record item 4"}]
    }

A supporting relation is a proposed evidence relationship, NOT automatic proof of factual truth. A government document proves an official statement was made, not necessarily that the reported statement is true. A research provider cannot mark its own findings verified. AI-curated secondary material does not count as an independent original source. Distinct original_work_id values are potential, not guaranteed, independence.

Dossiers remain internal and explicitly identify coverage gaps and contradictory relations.

## Durable jobs and database schema

The module reuses the existing SQLite/PostgreSQL connections and advisory locks. On first explicit EI use it creates an additive ei_records table with id, kind, event_id, updated_at and data (JSON text), plus an index. It marks optional schema migration 3. It does not alter the original tables.

Record prefixes: document, dossier, job, draft, published and revision. Jobs have immutable IDs per gap set, bounded lease expiry, retry count and dead-letter state. Stale results from replaced worker leases are rejected; failures persist for retry. No large external queue, Kafka or Kubernetes is added.

## Operator CLI

The commands below require permission-reviewed local JSON files. They do not perform scraping or network research. Run only in a trusted operator environment.

    export PYTHONPATH=src
    python -m prismunfold.ei_cli --db /tmp/ei.sqlite ingest --file documents.json
    python -m prismunfold.ei_cli --db /tmp/ei.sqlite dossier --event evt-...
    python -m prismunfold.ei_cli --db /tmp/ei.sqlite plan-research --event evt-...
    python -m prismunfold.ei_cli --db /tmp/ei.sqlite jobs
    python -m prismunfold.ei_cli --db /tmp/ei.sqlite run-research --job research-... --file research.json
    python -m prismunfold.ei_cli --db /tmp/ei.sqlite draft --event evt-... --language de --file writer.de.json
    python -m prismunfold.ei_cli --db /tmp/ei.sqlite approve --event evt-... --language de --reviewer "Named Editor" --checked-file checked.json
    python -m prismunfold.ei_cli --db /tmp/ei.sqlite export --site /tmp/ei-preview
    python -m prismunfold.ei_cli --db /tmp/ei.sqlite edition --profile profile.json

Writer JSON contains headline, lead, paragraphs[]; each paragraph has text and an array of claim_keys present in the dossier. The checked JSON object maps all used claim keys to arrays of original source document IDs whose passage locators a named human editor actually inspected. Approval includes the exact language variant. The CLI does NOT authenticate the entered reviewer name, so this is not yet a production-ready review service.

## Output and 0.3 integration

The static, atomic preview path is:

    api/v1/editorial-intelligence/content-pool.json

The versioned schema is prismunfold.content-pool/1. It contains only approved articles with event_id, article_id, language, article_variant, headline, lead, paragraphs with claim_keys, claim_references, topics, regions, revision, review status, and reviewer-checked original source references. Internal dossiers and reviewer identity are not exported.

Milestone 0.3 should add a versioned adapter into the canonical article/edition contract when the teams agree on mapping, corrections and publication gate semantics. This new endpoint is a shared content pool only, never a second newspaper. Existing daily JSON endpoints and old frontend remain unchanged. Reader preferences select prepared content by topic, language and reading depth without additional model calls; a minimum public-interest coverage policy is still future work.

## Tests

    PYTHONPATH=src python3 -m unittest tests.test_editorial_intelligence -v
    PYTHONPATH=src python3 -m unittest discover -s tests

Deterministic tests exercise multilingual event association, syndication, AI-secondary source lineage, restricted rights, research gaps, persistent retries and lease expiry, malformed research, draft validation, human review gating, immutable revisions, content-pool export and two reader profiles. They need neither secrets nor paid calls.

No production deployment or real external research is claimed. A real-provider smoke test must be separately enabled on an approved source catalogue, not required in CI.

## Next phases and current limitations

**EI-01B:** connect approved RSS documents and staged prism-data bulletin contributions, source discovery candidate review, cross-language event matching with ambiguity detection.
**EI-01C:** actual source passage checks, retrieval and claim support analysis, model capability routing and resource usage budgets.
**EI-01D:** provider-backed editorial writing and translation, independent reviewing, magazine artifacts, correction propagation.
**EI-01E:** aggregate reader demand mapping, public-interest minimum coverage and a versioned 0.3 composition adapter.

Current limitations are important: this slice relies on structured upstream claim candidates and explicit event keys; it cannot independently verify content, ownership-based independence, full-text copyrights, translated semantic equivalence or claims added by prose generators. The human review is explicit but only text-identified, not authenticated. PostgreSQL and VM deployment need live validation before any production flag is enabled. No images are copied or rendered without separate rights review.
