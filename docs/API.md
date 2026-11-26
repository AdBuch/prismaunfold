# JSON API

Static files written by the pipeline under `site/api/v1/` and served by nginx.
There is no application server in the read path.

| Endpoint | Status | Shape |
| --- | --- | --- |
| `index.json`, `editions.json`, `stories/{slug}.json`, `topics/{slug}.json`, … | Implemented (feed desk and agent stories) | `frontend/src/models.ts` |
| `editorial/morgenbriefing.json` | Implemented; used by `/morgenbriefing` | List of editorial editions, newest first; see below |
| `daily/index.json`, `daily/{date}.json` | Implemented in 0.2; read by the frontend since 0.3 (Today, articles, World, Magazine, Topics, Voices) | Unified daily edition, below |

All writes are atomic (temporary file + rename); a failed export leaves the previous
file in place. Only published or approved content is exported.

## `editorial/morgenbriefing.json` (compatible extension)

Unchanged fields: `date`, `title`, `articles[]`, `magazine`, `random`, `lagebild[]`,
`warnings[]`, `disclosure`, and for imported bulletins `additional_articles[]`,
`additional_magazines[]`, `bulletin{}`.

Optional fields added in 0.2 (older editions lack them; clients must tolerate absence):
`completeness` (`complete`|`partial`), `published_at`, `publication_mode`; per article
`article_id`, `state`, `review_required`, `review_reasons[]`, `approval{by,at,note}`,
`kind`, `provider`, `provenance{provider, origin_type, publication_basis,
upstream_status, generated_at, content_hash, citation_level}`; per source
`link_status`, `policy`; per bulletin `bulletin.publication_basis`,
`bulletin.upstream_status`, `bulletin.rubrics`, `bulletin.editorial_cutoff`.

## `daily/{date}.json` (schema `prismunfold.daily-edition/1`)

One logical edition per publication date (Europe/Zurich), composed from all public
contributions of that date.

```jsonc
{
  "schemaVersion": "prismunfold.daily-edition/1",
  "date": "2026-11-25", "timezone": "Europe/Zurich", "title": "PrismUnfold · Tagesausgabe",
  "mainHeadline": {"articleId": "ed-2026-11-25-…", "headline": "…"} | null,
  "introduction": {"text": "…", "provider": "prism-data", "originType": "ai_secondary"} | null,
  "rubrics": [{"name": "Schweiz Politik", "articleIds": ["…"]}],
  "articles": [Article],          // news, rubric order
  "briefs": [],                   // short news briefs: reserved for 0.3
  "magazine": [Article],          // kind "magazine"; first is the feature of the day
  "goodNews": [Article],
  "randomFacts": [{"label", "text", "attribution", "reviewRequired", "sources": [Source]}],
  "assessments": [{"label", "text", "attribution", "reviewRequired", "sources": [Source]}],
  "contributors": [{"provider": "codex", "originType": "ai_secondary"}],
  "transparency": {"disclosures": [], "warnings": [], "editorialNote": "…" | null,
                   "completeness": "complete|partial|unknown", "independentVerification": "…"},
  "revision": {"publishedAt", "publicationMode", "bulletinGeneratedAt", "bulletinBasis"}
}
```

`Article`:

```jsonc
{
  "articleId": "ed-…" | "pd-…", "kind": "news|magazine|good_news|random", "section": "…",
  "headline": "…", "lead": "…", "topic": "slug" /* optional */,
  "paragraphs": [{"text", "heading" /* optional */, "sourceIds": [], "reviewRequired": false}],
  "sources": [Source], "images": [Image], "perspectives": [...], "uncertainties": ["…"],
  "background": [{"heading", "text", "sources": [Source]}],
  "reviewRequired": false, "limitations": ["no_original_sources"],
  "verification": {"sourceAccess": ["reachable", "restricted"], "factual": "not_independently_verified"},
  "provenance": {"provider", "originType", "publicationBasis", "citationLevel", "generatedAt", "upstreamStatus"},
  "coverage": [Article],          // matched contributions from other providers
  "storySlug": "…"                // optional link to an agent/feed story
}
```

`Source`: `id`, `url`, `title`, `publisher`, optional `publishedAt`, `sourceType`,
`access`, `linkStatus`. `Image`: `alt`, `caption`, `credit`, `license`, `licenseUrl`,
`rights`, `rightsNote`, `sourceUrl`, `origin`, `display`, and `url` **only when
`display` is true**.

`daily/index.json`: `[{date, mainHeadline, articleCount, magazineCount, completeness,
contributors[], href}]`, newest first.

The contract is checked by `tests/test_dedupe_images_api.py::DailyContractTests` (export)
and `frontend/tests/newspaper.test.ts` (reader). Changing it requires a new `schemaVersion`.

Optional article fields the frontend already reads when present (pipeline backlog:
[PIPELINE_INTERFACE.md](PIPELINE_INTERFACE.md)): `summary`, `whyItMatters`, `regions`,
`interests`, `importance`, `authors[]`, `corrections[]`, `updatedAt`, `language`,
`sources[].author`; per edition `editionProfile`, `language`.

## Compatibility notes (0.3)

- `editorial/morgenbriefing.json` is still exported for compatibility; the frontend
  no longer reads it. The `/morgenbriefing…` URLs redirect to editions and articles.
- `editions.json`, `stories/…`, `topics/…`, `magazines.json` are unchanged and still read.
- Article ids are canonical URLs (`/article/{articleId}`); their date prefix must stay.
