# Product architecture (milestone 0.3)

PrismUnfold is a digital newspaper, a multilingual knowledge platform and, later, an
open journalistic ecosystem. Principle: **personalise access to reality, not reality
itself.** Personalisation changes selection, order, language and depth; it never
changes what an article says. The product is useful to a single reader without any
community, network effects or engagement optimisation.

Related: [READER_PROFILE.md](READER_PROFILE.md) (profile and composition contract),
[PIPELINE_INTERFACE.md](PIPELINE_INTERFACE.md) (what the editorial pipeline must
deliver), [API.md](API.md) (JSON contracts), [PROJECT.md](PROJECT.md) (roadmap).

Status words: **implemented** (in code, covered by tests), **interim** (implemented in
the frontend until the pipeline provides it), **planned**.

## One publication, many contributors

RSS publishers, the prism-data bulletin (ChatGPT), Codex, Claude, Mistral, local
models, research agents and, later, journalists and human editors are internal
contributors. Their contributions become **canonical articles** with provenance
(docs/EDITORIAL_WORKFLOW.md). Readers see one newspaper; a contributor is shown under
“Evidence and transparency” and on its Voices page, never as a separate paper in the
navigation. Matching reports of one event are shown once, with the others as
“Other contributors on the same event”.

## Compositions over canonical articles

Every reader-facing collection references canonical articles by id and never copies
their content:

| Composition | Built from | Status |
| --- | --- | --- |
| Public daily edition | `api/v1/daily/{date}.json` (editorial order) + the feed desk's edition of that date | Implemented |
| Personal daily edition | The public edition's articles, recomposed on the device (lib/composer.ts) | Implemented |
| Historical edition | The published daily edition of a past date, unchanged | Implemented |
| The World | Newest article per event from recent editions, ranked by importance | Implemented (interim: assembled in the browser) |
| Magazine | `kind: magazine` articles of all editions + earlier long-form features | Implemented (interim) |
| Dossier | Articles with the same `topic` + the topic timeline | Implemented (interim) |
| Voices page | Articles naming the author or contributor | Implemented (interim) |
| Thematic collection, shareable mix | References to articles, saved by a reader | Planned (saved articles exist on the device) |

One canonical daily edition exists per date today. The contract reserves
`editionProfile` and `language` for “one edition per date, profile and language”.

## Navigation

Six destinations, chosen so that content types do not each need a menu entry:

| Destination | Purpose |
| --- | --- |
| **Today** | The landing page: the finite daily newspaper (public or personal) |
| **The World** | The public, continuously updated newspaper of significant events; not personalised |
| **Magazine** | Slower, deeper journalism: features, reports, explanations |
| **Topics** | Dossiers that evolve over time |
| **Archive** | Every edition by date |
| **My PrismUnfold** | Preferences, follows, saved articles, history, privacy controls |

Articles, dossiers and Voices pages are reached from these; About and the privacy
note live in the footer.

## Routes

| Path | View | Notes |
| --- | --- | --- |
| `/` | Today | Personal edition when a profile exists; `?edition=public` shows the public one |
| `/edition/{date}` | Today for a date | Canonical URL of an edition; `/edition/today` = `/` |
| `/article/{articleId}` | Article with layers | Canonical URL of an article; magazine articles use the magazine style |
| `/world` | The World | |
| `/magazine`, `/magazine/{slug}` | Magazine index, earlier long-form features | |
| `/topics`, `/topic/{slug}` | Dossier index, dossier | Topic timelines from 0.2 are part of the dossier |
| `/author/{slug}` | Voices page | Contributors (`/author/codex`) and named authors |
| `/archive` | Archive | |
| `/story/{slug}` | Feed-desk and agent stories | Unchanged since 0.2 |
| `/me` | My PrismUnfold | `noindex` |
| `/about` | How this paper is made | |
| `/morgenbriefing` → `/` · `/morgenbriefing/{date}` → `/edition/{date}` · `/morgenbriefing/{date}/artikel/{n}` → `/article/{id}` · `/preferences` → `/me` | Compatibility | Client-side replace, no history entry |

## Today's Edition

Masthead and date · edition bar with previous/next and date selector · onboarding
invitation (until the reader sets up or skips) · introduction · front page (lead,
secondary stories, In brief) · updated since publication (corrections) · sections ·
more reporting (feed desk, without stories already attached to an article) · magazine
feature · Good News · discoveries · editorial outlook · how this edition was made ·
end of edition. A date with only a feed edition renders as before.

In the personal edition each item says why it is there (important for everyone, your
interest, a follow, discovery beyond your interests) and interests without content are
listed under “Not covered today”.

## Article layers (progressive unfolding)

| Layer | Content | Shown when |
| --- | --- | --- |
| 1 Overview | Headline, lead; “What happened” and “Why it matters” | Lead always; the two fields only when the pipeline provides them |
| 2 Article | Paragraphs with numbered source references; paragraphs without an openly reachable source are marked; images with rights; corrections | Always |
| 3 Context | Background, other contributors on the event, earlier reporting on the topic, dossier link | When any exists |
| 4 Perspectives | Attributed positions, open questions | When the reporting contains them; none are added for balance |
| 5 Evidence | Sources with publisher, author, date and access status; what was checked; contributor and AI involvement; limitations; images not shown | Always |

Layers 3 to 5 are folded `<details>` elements, keyboard operable.

## Visual identity

The 0.2 design system stays: serif display and text faces, masthead with prism mark,
rules instead of cards, restrained palette, a dark magazine panel, generous measure.
0.3 adds a dateline, text-led lead layout when no image is cleared, quiet notices for
onboarding and coverage gaps, folded layers and a magazine article style. Screenshots:
CI artifact `screenshots-demo` and [screenshots/0.3](screenshots/0.3).

## Images

Rendering follows the rights metadata (docs/EDITORIAL_WORKFLOW.md, “Images”): an
image appears only with a display grant, HTTPS and a credit; AI illustrations carry a
visible label; images without rights are listed under Evidence. An article without an
image uses the text-led layout. No image generation is part of the pipeline.

## Sharing and discoverability

Stable URLs for editions, articles, magazine features, dossiers and Voices pages.
Every page sets title, description, canonical link and Open Graph tags. Personal
pages (`/me`, the personal edition, unverified author records) are `noindex`; the
personal edition's canonical link is the public edition. Pages are rendered in the
browser; server-side rendering for crawlers is planned.

## Privacy and trust

Preferences, follows, saved articles and history are stored on the device only, are
editable and removable, and the exact stored data is shown. Reading history and
behavioural personalisation are off by default. No profile is sent to PrismUnfold or
to AI workers; aggregated topic demand is the planned interface
(READER_PROFILE.md). Recommendation weights are relevance signals and are kept apart
from editorial assessments; there are no commercial partnerships in the ranking.

## Limitations of 0.3

- No accounts: settings do not synchronise between devices; publisher follows have no UI yet.
- World, Magazine, Topics and Voices are assembled from the last 14 (Magazine: 60)
  editions in the browser until the pipeline exports indexes.
- Interest and region signals are derived from section names until articles carry
  `regions` and interest keys; importance is derived from the editorial order.
- “What happened”, “Why it matters”, author names and corrections appear only when the
  pipeline supplies them; today's Codex and prism-data editions do not.
- The interface is in English; content keeps its own language. Interface languages are planned.
- Short news briefs, curated collections and shareable mixes are reserved in the
  contract but not produced.
