# PrismUnfold

**Independent journalism. Many perspectives. One clearer view of the world.**

PrismUnfold is a **beautiful digital newspaper for everyone**, powered by the concise, carefully sourced and personally curated experience of our existing daily morning news bulletin. The editorial experience comes first: a recognizable front page, clear sections, high-quality concise writing and deeper reporting. The **Spotify analogy applies primarily to social discovery, sharing stories with friends and accessing journalism from multiple participating publishers through one subscription**. In the long term, PrismUnfold will also create original journalism.

## Mission

**More money for good journalism. More truth and transparency. Less misinformation, hidden bias and overlooked stories.**

PrismUnfold aims to strengthen independent journalism and its role as a watchdog of power, making reliable information accessible to everyone. The platform should **inform, not steer**: no political or social agenda, no paid influence over editorial judgments, and no engagement-driven outrage incentives.

We recognize that no system can promise absolute neutrality or certainty. We strive for **verifiable facts, transparent uncertainties, evidence-based assessments, diversity of sources, clear distinctions between reporting and opinion, and visible corrections**. Different perspectives deserve consideration, but unsupported claims must not be treated as equally credible as established evidence.

## Core experience: a newspaper, not a generic feed

The existing personalized daily world briefing is the product reference, translated into an elegant, responsive newspaper interface. An edition should feel like a coherent publication rather than an endless stream of unrelated cards.

- **Front page:** masthead, lead story, editorial hierarchy, section navigation, compelling typography and a deliberate reading experience across mobile and desktop.
- **Daily edition:** a bounded morning paper with compact, high-information-density reporting, appropriate context and a deeper magazine-style feature, rather than an infinite scroll.
- **Editorial range:** Switzerland (including rotating regional coverage), Peru, global affairs, conflicts, society, good news and discoveries, with wide geographical and source diversity.
- **Article pages:** clear source references, confidence/uncertainty, relevant perspectives, chronology of significant updates and links to original reporting.
- **Personal editions:** users can shape sections, languages, depth and topics without eliminating globally significant stories.
- **Social reading:** share an article or an edition with friends, follow recommendations and build collections or reading lists. Sharing must work via public links and should not require the recipient to join just to see a free story.
- **Multi-publisher access:** when licensed, users can open participating publishers' full articles and investigations with a PrismUnfold subscription, with access varying by tier.

**Not the goal:** make Spotify's music-player interface for text, build another outrage-driven social media feed, or gate the basic facts behind payment.

## Product vision

- **Less noise:** cluster hundreds of reports about one event into a coherent story, avoid duplicate coverage, and update only for meaningful developments.
- **More confidence:** compare independent sources, preserve provenance and links, surface disagreements, mark unverified claims and corrections.
- **Personal relevance without filter bubbles:** tune topics, regions, languages and detail levels, while preserving globally important and underreported stories.
- **Worldwide reach:** multilingual ingestion, local and international reporting, geographic and viewpoint diversity.
- **Read first, optionally listen:** a newspaper-first web reading experience, concise daily editions, saved stories and deep dives. Audio is a later optional format.
- **Support the creators:** fairly license third-party journalism and distribute subscription revenue transparently to participating publishers and, later, investigative projects.

## Product evolution

| Phase | Scope | Success looks like |
| --- | --- | --- |
| **1. Digital daily newspaper (MVP)** | Transform the existing personalized morning bulletin into a beautiful, shareable newspaper-style web experience; test with family and friends | A coherent daily edition, readable public stories, trustworthy source links, personal preferences |
| **2. Public newspaper + social reading** | Individual editions, public share links, friend recommendations, followable collections, multi-language support and publisher licensing pilots | Readers return for their edition, share stories with friends, and can access licensed premium reporting |
| **3. Open news platform** | Publishers, editors and users create and share bulletins, channels and playlists | Diverse independent content and transparent creator/publisher remuneration |
| **4. PrismUnfold Originals** | Employ journalists and correspondents to publish original reporting, investigations, interviews and documentaries | A sustainable editorial organization with strong independence and public-interest impact |

These phases represent strategic direction, not committed release dates.

## Business model

Build toward **Spotify-like subscription tiers for access to multiple publishers**, alongside Spotify-like sharing and friend discovery. Depending on the subscription, users get increasing access to **licensed external premium articles, investigations and deeper research**, plus advanced news experiences. A useful free offering must remain available; truthfulness and basic verification must never depend on payment.

Any access to paywalled external content **requires publisher agreements and appropriate licensing**. No bypassing paywalls, copying entire articles without rights, or implying partnerships where none exist.

Over time, expand into publisher partnerships, creator payouts and original journalism. The revenue model should invest meaningfully in reporting rather than optimize purely for clicks, time-on-site or sensational content.

## Editorial and platform principles

1. **Accuracy before speed:** check and corroborate, and show what remains unknown.
2. **Editorial independence:** separate commercial incentives, ranking systems and editorial decisions; disclose conflicts of interest.
3. **Transparency and accountability:** cite original sources, explain editorial/AI involvement, preserve corrections and audit trails.
4. **Evidence over false balance:** show competing interpretations fairly without equating proven facts with misinformation.
5. **Discovery beyond preferences:** guarantee space for world relevance, underreported communities and uncomfortable-but-important news.
6. **Journalism as public infrastructure:** protect independent scrutiny of institutions and make quality information widely accessible.
7. **Human accountability:** AI assists with ingestion and synthesis; consequential editorial judgment and original reporting remain accountable to people.

## Proposed initial MVP

Build the **daily newspaper experience and its news intelligence core together**, without attempting a full publisher marketplace at launch:

1. Ingest a curated set of multilingual RSS/news sources with timestamps, canonical URLs, attribution and usage rights.
2. Normalize and deduplicate articles; cluster them into real-world events and track meaningful updates.
3. Generate short, neutral German-language summaries of each event, preserving linked source evidence and expressing uncertainty.
4. Prioritize a mix of **personal interests + general world importance + discovery beyond the user's bubble**, with explicit, user-adjustable weights.
5. Assemble a compact daily news bulletin with regional sections, international coverage and optional deeper explanations.
6. Provide an editorially designed, responsive newspaper UI: front page, clear sections, lead stories, article pages, source inspection, bookmarks and preference controls.
7. Enable sharing individual free stories and editions by durable public URLs; start with simple social sharing, not a full social graph. Add quality controls: citation coverage, source diversity, hallucination checks, editorial review flags and correction history.
8. Evaluate with family and friends before expanding to friend feeds, licensed publisher article access, payments, audio and community publishing.

### MVP non-goals

- Building a full social network or publisher marketplace; simple public story sharing **is** in scope.
- Implementing paywall access without contractual rights.
- Claiming that AI summaries are independently fact-checked merely because multiple articles were aggregated.
- Launching a newsroom or commissioning original journalism in phase 1.

## Conceptual architecture

```text
Sources / feeds
    -> Ingestion + provenance
    -> Normalization / event clustering
    -> Evidence comparison + validation signals
    -> Neutral event summaries + editorial review flags
    -> Global relevance + personal mix + discovery
    -> Daily edition composer + newspaper layout
    -> Public front page, article pages, shareable links
    -> Preferences, bookmarks, friend discovery later
    -> Licensed multi-publisher access later
```

Keep **News Intelligence**, **Media Marketplace** and **Editorial / Originals** logically separate, with clear interfaces and governance so that subscriptions and commercial partnerships never silently control factual assessments.

## Next steps for development

1. Inspect the repository and propose a minimal, maintainable architecture without assuming a technology stack has already been selected.
2. Write concise requirements and architecture decisions, including provenance and quality evaluation.
3. Deliver a vertical slice: ingest sources -> cluster stories -> evidence-linked summary -> daily newspaper front page -> story page -> shareable public URL.
4. Add automated tests, observable processing and human review workflows before scale.
5. Iterate in small, reviewable commits, documenting limitations and open questions.

---

**North star:** *Help people understand the world, not tell them what to think, while making independent journalism economically sustainable.*


## Status of this document

The sections below describe the original Phase 2 prototype, which ran on fictional
fixtures only. Since the integration the default build reads real stories from the
pipeline's JSON API; the fixtures remain as the demo build (`npm run start:demo`) and
for tests. Current instructions are in the README at the repository root.

## Phase 2 frontend prototype

A runnable newspaper prototype lives in `src/`. **All content is fictional demo material**: no real events, publishers or sources, and nothing is verified. Source links use reserved `example.org` addresses.

### Run it

Requires Node.js 22 or newer.

```bash
npm install
npm start          # builds, then serves http://localhost:4200
```

Other commands:

```bash
npm run dev        # rebuilds on change while serving
npm run typecheck  # strict TypeScript check
npm test           # unit tests (node:test, no browser needed)
npm run test:e2e   # browser navigation tests; needs a running server and Playwright browsers
```

For the browser tests run `npx playwright install chromium` once, start `npm start`, then `npm run test:e2e` in a second terminal.

### Screens

| Route | Screen |
| --- | --- |
| `/` or `/edition/today` | Today's edition: masthead, lead, front-page columns, sections, in brief, magazine feature, clear end |
| `/edition/:date` | Archived edition with previous/next and a date selector. Placements keep a snapshot of their original wording |
| `/archive` | List of editions and a date picker with validation |
| `/story/:slug` | Reader: sources, corrections, confidence note, story-so-far, related stories, share |
| `/topic/:slug` | Topic timeline: milestones, reports, updates, corrections; filter and sort |
| `/magazine/:slug` | Long-form template: hero, drop cap, pull quotes, sidebars, chronology, glossary, related reading |
| `/magazine`, `/about` | Feature index and an explanation of the demo |

### Architecture

- `src/models.ts`: typed domain models (Edition, EditionStoryPlacement, Story, Topic, TimelineEvent, SourceReference, MagazineFeature).
- `src/content/content-service.ts`: the `ContentService` interface. Views depend only on this. `fixture-service.ts` implements it with local fixtures, so a real API client can replace it later.
- `src/content/*.ts`: fixtures (3 editions, 12 stories, 2 magazine features, 2 timelines).
- `src/components/`: reusable editorial pieces. `src/views/`: one module per screen. `src/lib/`: router, escaping, procedural artwork.
- Zero runtime dependencies. Build uses esbuild; types are checked with `tsc`.

The artwork is procedurally generated and stands in for credited photography. Every image carries a `credit` field for real photo credits later.

### Known limitations

- Not Angular: the prototype uses plain TypeScript. The models and `ContentService` boundary carry over unchanged if the project later moves to Angular.
- No preferences drawer, no real images, no backend, authentication or payments (all out of scope for Phase 2).
- Fixtures are in English only.
