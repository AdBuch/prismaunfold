# Interface for the editorial pipeline (milestone 0.3)

What the reader experience needs from the editorial intelligence and research
pipeline, maintained in parallel. The frontend already reads every field below when
present and shows nothing when absent. All changes are additive to
`prismunfold.daily-edition/1` (docs/API.md); a breaking change needs a new
`schemaVersion`. Fixtures: `frontend/src/content/daily-fixtures.ts`.

## 1. Article fields (priority order)

| Field | Type | Used for | Today |
| --- | --- | --- | --- |
| `summary` | string, ≤ 2 sentences | Layer 1 “What happened”, teasers | Missing; the lead is shown |
| `whyItMatters` | string | Layer 1 and the front-page lead | Missing; nothing is shown |
| `regions` | ISO 3166 codes, `EU`, `GLOBAL` | Personal composition, the World | Derived from section names (interim) |
| `interests` | interest keys (READER_PROFILE.md) | Personal composition | Derived from section names (interim) |
| `importance` | 0..1, editorial | Global guarantee, ranking | Derived from editorial order (interim) |
| `topic` | stable slug | Dossiers, follows, repetition limits | Codex sets it; prism-data does not |
| `authors[]` | `{name, slug?, publisher?, verified}` | Voices pages, follows | Missing; contributor shown instead |
| `sources[].author` | string | Evidence layer | Missing |
| `corrections[]` | `{date, text}` | Correction box, “Updated since publication” | Missing |
| `updatedAt` | ISO time | Updates since publication | Missing |
| `language` | BCP 47 | `lang` attribute, language selection | Missing |
| `perspectives[].label/attribution` | strings | Layer 4 | prism-data assessments only |

Rules: never invent a field to fill the layout; `verified` on an author only for an
account the journalist controls; `whyItMatters` is editorial explanation, not a claim
without sources.

## 2. Indexes (replace browser-side assembly)

| File | Content |
| --- | --- |
| `api/v1/topics/index.json` | `[{slug, title, summary, firstDate, lastDate, articleCount, sections}]` |
| `api/v1/topics/{slug}.json` | Extend the 0.2 timeline with `articleIds[]`, `background[]` (deduplicated), `openQuestions[]`, `corrections[]` |
| `api/v1/magazine/index.json` | `[{articleId, date, headline, lead, topic, image}]`, newest first |
| `api/v1/authors/{slug}.json` | `{name, verified, publishers[], articleIds[]}`; only from reliable metadata |
| `api/v1/world.json` | Ranked current events: `[{articleId, date, importance, topic}]` |

## 3. Magazine from research

A research report may become the basis of a magazine article only after it passes
the editorial workflow (validation, review). Raw research output is never published;
the magazine reads only `kind: magazine` articles in a daily edition or the magazine
index.

## 4. Editions per profile and language

`daily/{date}.{profile}.{language}.json` with `editionProfile` and `language`,
referencing shared article ids (READER_PROFILE.md). Until then there is one public
edition per date.

## 5. Signals from readers (planned)

Aggregated, anonymous coverage-gap counts (READER_PROFILE.md). Workers receive topic
demand, never profiles, histories or identifiers. Commercial or partnership data must
never enter ranking or editorial assessment.

## 6. Shared models

The frontend does not change the database. `contributions`, `editions` and the
export in `src/prismunfold/daily.py` remain owned by the pipeline; schema changes are
coordinated through docs/API.md.
