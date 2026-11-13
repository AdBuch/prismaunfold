# PrismUnfold: Phase 2 MVP Frontend Prototype Brief

Status: product direction and implementation handoff (9 November 2026).

## Core experience

PrismUnfold is **a beautiful, finite daily digital newspaper**, not a Spotify player, a generic infinite-scroll feed or a news dashboard. The existing highly curated daily ChatGPT world-news bulletin is the editorial reference. Readers arrive at **Today's Edition**, with a recognizable masthead, main headline, supporting stories, sections and a deliberate beginning and end.

The default front page has an editorial hierarchy shared by everyone; personalization can adjust relevance, section prominence and language without erasing globally important news. **A daily edition is a published snapshot**. Readers may revisit previous editions by date. When a story changes, append meaningful updates to a **living topic timeline**, rather than silently rewriting historical editions. Corrections must be explicit and traceable.

## Writing styles

Two distinct reading experiences:

- **News:** concise, elegant, high information density, accurate, source-linked; readable in 30 seconds to 3 minutes. Distinguish facts, disputed claims and uncertainty. No exaggerated headlines or fabricated confidence scores.
- **Background / Magazine:** more alternative, exploratory and atmospheric in *presentation* and narration, with thoughtful context, narrative structure, sidebars, explanatory graphics, maps, chronology and multiple relevant perspectives. Longer, engaging reading that explains *why* an event matters. This does **not** mean alternative facts or lower verification standards. Editorial voice stays independent, intellectually curious and grounded.

Deep dives should be discoverable from news stories and also collected in their own magazine section.

## Prototype routes and interactions

- `/` or `/edition/today`: a newspaper-like daily front page with issue date, lead story, front-page columns, section headings, concise teasers, "In brief" and a magazine feature.
- `/edition/:date`: browse a dated edition; previous/next buttons and an accessible date selector. The displayed historical issue remains stable.
- `/story/:slug`: readable article with title, lead, byline/AI disclosure where appropriate, publication and update times, section, source references, original publisher links, related stories and an interactive story timeline.
- `/topic/:slug`: chronological topic history showing dated milestones and links to relevant stories/editions.
- `/magazine/:slug` (or magazine story template): long-form typography, contextual pullouts, related reading, distinct but cohesive visual language.
- Optional simple preferences drawer: language, region/topic interests, density. Do not make a complex personalization engine for the prototype.

Interactions that must actually work: click article, return to edition, select an archived date, traverse timeline and related stories, switch to magazine feature, share/copy a canonical URL. Responsive for mobile and desktop, with keyboard-accessible navigation.

## Visual direction

Contemporary newspaper meets thoughtful literary magazine. Strong typographic hierarchy, refined serif display headlines and readable body text, restrained neutral palette, generous whitespace, subtle rules, carefully composed grid, tasteful imagery with captions and credit fields. The magazine pages can use more editorial experimentation, art direction and longer-form visual sections. Avoid cookie-cutter card grids, dashboard chrome, giant gradients, gimmicky badges and Spotify imitation.

The daily front page should look convincingly like a publication, not a wireframe.

## Prototype data and publishing model

For the first frontend-only demonstration, use **typed fixtures/local mock JSON** with at least:
- 3 dated editions, each with curated sections and varied story formats;
- 8-12 stories spanning Switzerland, Peru, international affairs, society/science and underreported regions;
- 2 magazine-style features;
- 2 evolving topics with multi-date timelines.

Illustrative content must be explicitly marked as **demo/fictional**, or use genuine externally sourced articles with attributable sources and verified dates. Never invent real quotations, news events, publisher partnerships, licenses or source links. Do not imitate a real premium article's full text.

Model at minimum: Edition, Section, Story, Topic, TimelineEvent, SourceReference, MagazineFeature, EditionStoryPlacement (edition ordering and display snapshot), with stable IDs and dates. The same Story/Topic can appear in multiple editions, but publication snapshots must remain stable. Structure UI behind a content repository/service abstraction so later API data can replace fixtures without rewriting views.

## Spotify-inspired future (not Phase 2 build scope)

The Spotify analogy is about **sharing what you read with friends**, discovering stories through trusted connections, building reading collections/playlists, and a **single subscription tier granting legally licensed access** to content from participating external publishers. Sharing a link must not purport to unlock a publisher paywall. Eventually publishers receive transparent, fair remuneration. The free edition remains useful and factually complete.

## Editorial guardrails

Strengthen independent journalism's watchdog role: more resources for quality reporting, less misinformation and structural bias, more transparency, less neglected coverage and no political/social steering. Show uncertainty and sources rather than claiming perfect objectivity. Commercial access and algorithms must not influence conclusions.

## Phase 2 definition of done

- A runnable, attractive and responsive browser prototype focused on daily editions.
- Working edition archive by date, newspaper story reader, topic timelines and magazine long-form template.
- Realistic fixture data, no nonfunctional controls or dead links.
- Clean component architecture with typed content models and explicit API boundary.
- Basic automated coverage of navigation and edition/timeline behavior, plus README commands to run it.
- No backend, authentication, payments, real feeds, social graph or paywall integration unless already implemented and needed for compatibility.
- Small, reviewable commits on a feature branch; report what works and known gaps.

## Next engineering action

Inspect repository first. At the time of writing it only has README.md; verify current contents independently. Choose a maintainable frontend stack consistent with what is present; if still empty, Angular + TypeScript is a reasonable option but confirm in your plan. Implement the vertical slice as a visually polished prototype rather than expanding scope into unrelated systems.
