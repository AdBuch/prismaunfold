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

## Run everything with Docker

Every component runs in its own container.

```bash
cp .env.example .env                              # add at least one agent's API key
cp config/topics.example.txt config/topics.txt    # one line per topic: <language>|<topic>
docker compose up --build -d
curl http://localhost:8080/api/v1/index.json
```

| Container | Job |
| --- | --- |
| `pipeline` | Every 10 minutes: plans the current 6-hour edition, checks the agents' reports, keeps the archive, exports JSON |
| `codex`, `claude`, `vibe`, `goose` | One writer each. Reads the job list, writes one report per topic. Idle without credentials |
| `web` | Serves the exported JSON on port 8080 |
| `volumes-init` | Sets volume permissions once, then exits |

The containers talk only through volumes: the pipeline writes the job list and our
prior coverage of each topic, the collectors write reports, the pipeline checks them
and exports JSON, the web container serves it. No container starts another one and
none needs the Docker socket.

Useful commands:

```bash
docker compose logs -f pipeline claude        # what is happening
docker compose run --rm pipeline reports --reports-dir /out --force   # re-check all reports
docker compose down                           # stop; add -v to delete all data
```

Status: CI builds all images and runs the stack with a stand-in agent
(`.github/workflows/ci.yml`). A run with real agents and API keys has not happened
yet; see `collectors/README.md` for the open points. The frontend is not part of
this setup yet, and storage is SQLite on a volume, not PostgreSQL.

## MVP (Phase 1) quickstart

The pipeline uses only the Python standard library (3.11+). It has two inputs: RSS/Atom feeds, and reports written by collector agents (see `collectors/`). Its only output is JSON for the frontend.

```bash
# Tests
PYTHONPATH=src python3 -m unittest discover -s tests -v

# Check, store, index and export the collector agents' reports
PYTHONPATH=src python3 -m prismunfold reports --reports-dir collectors/out

# Write our earlier coverage of a topic, for the agents to build on
PYTHONPATH=src python3 -m prismunfold context --topic "Swiss energy policy" --out collectors/context/prior.md

# Build an edition offline from the demo fixtures
PYTHONPATH=src python3 -m prismunfold run \
  --catalog tests/fixtures/catalog.json --fixtures tests/fixtures \
  --now 2026-11-06T06:30:00+01:00

# Build from live sources (only entries with status "active" in catalog/sources.json are fetched)
PYTHONPATH=src python3 -m prismunfold run
```

Output lands in `site/api/v1/` as static JSON; the pipeline renders no HTML. The SQLite store is `data/prismunfold.sqlite3`. Both directories are git-ignored.

| File | Content |
| --- | --- |
| `index.json` | Editions with agent-written stories, newest first |
| `editions/<edition>.json` | Stories of one edition, grouped by topic; several writers per topic |
| `stories/<slug>.json` | One story: sentences with source ids, sources, byline, AI disclosure |
| `briefings/<lang>/latest.json` | Feed-based events of the current edition window |

### Agent reports and the archive

- A report is untrusted input. A sentence without a well-formed http(s) source URL is dropped; a report with no sourced sentence, an unknown agent or a mismatching edition is rejected, and `reports` exits with code 1.
- With `--check-links`, every cited URL is opened; sources that do not answer are removed and sentences left without a source are dropped. Only public hosts are contacted. This catches invented links, not a real page that fails to support the sentence.
- Every accepted story is added to a search index (SQLite FTS5, keyword ranking). `context` retrieves earlier stories on a topic and the collectors append them to the agent prompt. Embeddings can replace the keyword search later.
- A story is never labelled as verified: confidence is `reported`, or `disputed` when uncertainties are listed.

### What the MVP does

- Reads RSS 2.0 and Atom feeds, respects robots.txt, refuses DTDs and entities.
- Drops articles that are stale, future-dated, AI-disclosed (if the source excludes AI), or syndicated copies. Each drop is logged with its reason.
- Enforces source rights: `excerpt_only` drops the body, `link_only` drops the excerpt too.
- Groups articles about the same event (title similarity within 36 hours, same language).
- Writes an extractive summary. Each sentence cites its articles. Uncited sentences are removed.
- Selects up to 25 events per edition, at most 5 per primary topic.
- Builds editions at 00/06/12/18 local time for the configured time zone (IANA rules, DST-safe).

### Not in the MVP yet

- LLM summaries and translations (`NoTranslator` marks them as pending in the JSON).
- Personal ranking and feed keys (designed for the device, see the decision log).
- Topic requests, a review queue for new sources, and a running scheduler.
- Images are linked from the source, not stored locally.
- Clustering works within one language only.
