# PrismUnfold

**Independent journalism. Many perspectives. One clearer view of the world.**

PrismUnfold is a long-term vision for a global, trustworthy and personalized news ecosystem. It combines the concise, curated experience of a daily news bulletin with Spotify-style discovery and subscriptions, and eventually Netflix-style original journalism.

## Mission

**More money for good journalism. More truth and transparency. Less misinformation, hidden bias and overlooked stories.**

PrismUnfold aims to strengthen independent journalism and its role as a watchdog of power, making reliable information accessible to everyone. The platform should **inform, not steer**: no political or social agenda, no paid influence over editorial judgments, and no engagement-driven outrage incentives.

We recognize that no system can promise absolute neutrality or certainty. We strive for **verifiable facts, transparent uncertainties, evidence-based assessments, diversity of sources, clear distinctions between reporting and opinion, and visible corrections**. Different perspectives deserve consideration, but unsupported claims must not be treated as equally credible as established evidence.

## Product vision

- **Less noise:** cluster hundreds of reports about one event into a coherent story, avoid duplicate coverage, and update only for meaningful developments.
- **More confidence:** compare independent sources, preserve provenance and links, surface disagreements, mark unverified claims and corrections.
- **Personal relevance without filter bubbles:** tune topics, regions, languages and detail levels, while preserving globally important and underreported stories.
- **Worldwide reach:** multilingual ingestion, local and international reporting, geographic and viewpoint diversity.
- **Read or listen:** concise daily briefings, thematic feeds, audio editions, playlists, saved stories and deep dives.
- **Support the creators:** fairly license third-party journalism and distribute subscription revenue transparently to participating publishers and, later, investigative projects.

## Product evolution

| Phase | Scope | Success looks like |
| --- | --- | --- |
| **1. Personal news assistant (MVP)** | One user's curated, fact-conscious daily bulletin; eventually family and friends | Reliable, useful, configurable daily briefing with traceable sources |
| **2. Public personalized news portal** | Accounts, individual news mixes, discovery, audio, multi-language support | A compelling scalable product with a free tier and paid subscriptions |
| **3. Open news platform** | Publishers, editors and users create and share bulletins, channels and playlists | Diverse independent content and transparent creator/publisher remuneration |
| **4. PrismUnfold Originals** | Employ journalists and correspondents to publish original reporting, investigations, interviews and documentaries | A sustainable editorial organization with strong independence and public-interest impact |

These phases represent strategic direction, not committed release dates.

## Business model

Start with **Spotify-like subscription tiers**. Depending on the subscription, users get increasing access to **licensed external premium articles, investigations and deeper research**, plus advanced news experiences. A useful free offering must remain available; truthfulness and basic verification must never depend on payment.

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

Focus on the **news intelligence core**, not a sprawling portal:

1. Ingest a curated set of multilingual RSS/news sources with timestamps, canonical URLs, attribution and usage rights.
2. Normalize and deduplicate articles; cluster them into real-world events and track meaningful updates.
3. Generate short, neutral German-language summaries of each event, preserving linked source evidence and expressing uncertainty.
4. Prioritize a mix of **personal interests + general world importance + discovery beyond the user's bubble**, with explicit, user-adjustable weights.
5. Assemble a compact daily news bulletin with regional sections, international coverage and optional deeper explanations.
6. Provide a simple responsive web UI for reading, source inspection, feedback, bookmarks and preference controls.
7. Add quality controls: citation coverage, source diversity, hallucination checks, editorial review flags and correction history.
8. Evaluate on a small real-user group before expanding to personalized audio, licensing/payment and community publishing.

### MVP non-goals

- Building a full social network or publisher marketplace.
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
    -> Daily bulletin / personalized feeds / audio later
    -> Web application and user feedback
```

Keep **News Intelligence**, **Media Marketplace** and **Editorial / Originals** logically separate, with clear interfaces and governance so that subscriptions and commercial partnerships never silently control factual assessments.

## Next steps for development

1. Inspect the repository and propose a minimal, maintainable architecture without assuming a technology stack has already been selected.
2. Write concise requirements and architecture decisions, including provenance and quality evaluation.
3. Deliver a vertical slice: ingest sources -> cluster stories -> evidence-linked summary -> daily bulletin -> web UI.
4. Add automated tests, observable processing and human review workflows before scale.
5. Iterate in small, reviewable commits, documenting limitations and open questions.

---

**North star:** *Help people understand the world, not tell them what to think, while making independent journalism economically sustainable.*

---

## Run the newspaper

Everything runs in containers. You need Docker with Compose.

```bash
cp .env.example .env                              # credentials for the agents (optional, see below)
cp config/topics.example.txt config/topics.txt    # topics for the agents (optional)
python3 scripts/activate-sources.py srf-news bbc-world guardian-world   # feeds to read; see catalog/README.md
docker compose up --build -d
```

Open <http://localhost:8080>. The first edition appears after the pipeline's first
cycle, usually within a minute; until then the paper says that nothing has been
published yet.

You get real news from the feeds alone. The agents are optional: an agent without
credentials in `.env` stays idle.

| Container | Job |
| --- | --- |
| `pipeline` | Every 10 minutes: reads the feeds, plans the agents' topics, checks their reports, keeps the archive, composes the daily edition, exports JSON |
| `codex`, `claude`, `vibe`, `goose` | One writer each. Works through the topics assigned to it |
| `db` | PostgreSQL. Reachable only by the pipeline |
| `web` | The newspaper frontend and the exported JSON, on port 8080 |
| `volumes-init` | Sets volume permissions once, then exits |

The containers talk only through volumes. No container starts another one and none
needs the Docker socket. They run as unprivileged users with dropped capabilities
and resource limits; pipeline and web have a read-only file system.

Useful commands:

```bash
docker compose logs -f pipeline                      # what is happening
docker compose run --rm pipeline status --reports-dir /out   # how the agents' jobs went
docker compose run --rm pipeline reports --reports-dir /out --force   # re-check all reports
python3 scripts/activate-sources.py --reset          # stop reading all feeds
docker compose down                                  # stop; add -v to delete all data
```

Before the first start, set `POSTGRES_PASSWORD` in `.env`.

### Sources are your decision

`catalog/sources.json` ships with six candidate feeds, all `pending_review`, so a fresh
checkout reads nothing. Activating one is an editorial and legal decision: read
`catalog/README.md` first. The candidates keep only the headline and the link.

### The agents

- Two agents are chosen per topic, in rotation, within a budget per agent. Change this
  under `agents` in `config/config.json`, or name the writers per topic in `topics.txt`.
- A failed job is retried twice with growing pauses, then given up for that edition.
- Credentials: an API key, or for Claude Code and Codex a subscription login (see
  `.env.example`). Check your provider's terms before running a subscription unattended.
- **No real agent has run yet.** The collector images are tested with a stand-in. Start
  with one agent and one topic, and set a spending limit with your provider.

### What the labels on a story mean

| Label | Meaning |
| --- | --- |
| Backed by its sources (`supported`) | A check confirmed the cited source says this. Today only feed-desk stories reach it, because their sentences are taken from the cited article |
| Cited, not yet checked (`unverified`) | Every sentence names a source; nobody checked that the source says so |
| Thinly sourced (`review_required`) | A single publisher, an unreachable source, or sentences removed for lack of a source |
| Sources disagree (`disputed`) | Sources contradict each other; the story says where |

No story is ever called verified. See `src/prismunfold/verification.py`.

### Develop without Docker

```bash
# Pipeline (Python 3.11+, standard library only; SQLite file as the store)
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m prismunfold run            # reads active feeds, writes site/api/v1

# Frontend (Node 22)
cd frontend && npm install
npm start          # real content: serves ../site/api/v1 next to the app on :4200
npm run start:demo # fictional fixtures, clearly labelled
npm run typecheck && npm test
```

### What is tested

Every push runs, in GitHub Actions: the pipeline tests on SQLite and PostgreSQL
(including hostile agent reports), frontend type check and unit tests, browser tests
on the demo build, ShellCheck, and a full stack run in which a browser reads a story
that went through the collector container, the report check and the database.

The "Live feeds" workflow runs the whole chain on real feeds. It runs when the catalog
changes or on demand, never as a gate, because it depends on the network.

### Where things are

- `docs/audit.md`: what was found, what is fixed, the backlog and the open risks
- `docs/architecture.md`: how the parts fit together
- `collectors/README.md`: the agent images
- `catalog/README.md`: the source catalog and how to review a source
- `frontend/README.md`: the frontend prototype's original notes
