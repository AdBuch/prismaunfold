"""One feed run: ingest -> editorial gate -> cluster -> summarise -> rank -> desk stories -> export."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .cluster import cluster_articles
from .desk import changed, story_from_event, story_id_for
from .edition import edition_window
from .ingest import fetch_feed, parse_feed
from .models import Article, Event, Source, Summary
from .normalize import sha1_id, title_key
from .quality import rejection_reason
from .rank import score, select
from .export import export_site
from .storage import Store
from .summarize import ExtractiveSummarizer, NoTranslator, NotConfigured, validate_summary

DEFAULTS: dict = {
    "edition_timezone": "Europe/Zurich",
    "edition_hours": [0, 6, 12, 18],
    "languages": ["de", "en", "es"],
    "max_age_hours": 36,
    "cluster_threshold": 0.2,
    "cluster_window_hours": 36,
    "max_sentences": 3,
    "max_events_per_edition": 25,
    "max_events_per_topic": 5,
    "catalog_path": "catalog/sources.json",
    "db_path": "data/prismunfold.sqlite3",
    "site_dir": "site",
    # Which collector agents may be assigned topics, how many write about each topic,
    # and how many topics one agent may get per edition. See plan.py.
    "agents": {"enabled": ["codex", "claude", "vibe", "goose"], "per_topic": 2, "max_topics_per_agent": 6},
}

FetchFn = Callable[[Source], bytes]
LOOKBACK = timedelta(days=7)


@dataclass
class RunReport:
    fetched: int = 0
    kept: int = 0
    events: int = 0
    dropped: list[tuple[str, str]] = field(default_factory=list)
    dropped_sentences: int = 0
    stories: int = 0
    errors: list[str] = field(default_factory=list)
    editions: list[str] = field(default_factory=list)


def load_config(path: str | Path | None) -> dict:
    cfg = dict(DEFAULTS)
    if path and Path(path).exists():
        cfg.update(json.loads(Path(path).read_text(encoding="utf-8")))
    return cfg


def load_catalog(path: str | Path) -> list[Source]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Source(
            **{
                **d,
                "languages": tuple(d["languages"]),
                "regions": tuple(d.get("regions", [])),
                "topics": tuple(d.get("topics", [])),
            }
        )
        for d in raw
    ]


def apply_rights(article: Article, source: Source) -> Article:
    """Store only what the source's rights allow (Q-5)."""
    if source.rights == "link_only":
        return dataclasses.replace(article, excerpt="", body_text=None)
    if source.rights == "excerpt_only":
        return dataclasses.replace(article, body_text=None)
    return article


def build_event(group: list[Article]) -> Event:
    """group must be sorted oldest first."""
    ids = tuple(a.id for a in group)
    sources = tuple(dict.fromkeys(a.source_id for a in group))
    topics = tuple(dict.fromkeys(t for a in group for t in a.topics))
    return Event(
        id=sha1_id(*sorted(ids)),
        language=group[0].language,
        title=group[0].title,
        article_ids=ids,
        source_ids=sources,
        topics=topics,
        first_published=group[0].published_at,
        last_published=group[-1].published_at,
        single_source=len(sources) == 1,
    )


def run(
    cfg: dict,
    catalog: list[Source],
    now: datetime,
    fetch: FetchFn,
    store: Store,
    site_dir: str | Path,
) -> RunReport:
    report = RunReport()
    now = now.astimezone(timezone.utc)
    max_age = timedelta(hours=cfg["max_age_hours"])
    sources = {s.id: s for s in catalog}
    names = {s.id: s.name for s in catalog}

    # 1. Ingest: only sources with status "active" are fetched.
    fresh: list[Article] = []
    for src in (s for s in catalog if s.status == "active"):
        try:
            items = parse_feed(fetch(src), src)
        except Exception as exc:  # one broken feed must not stop the edition
            report.errors.append(f"{src.id}: {exc}")
            continue
        report.fetched += len(items)
        fresh.extend(apply_rights(a, src) for a in items)
    for article in fresh:
        store.save_article(article)
    store.commit()

    # 2. Editorial gate. The earliest report wins, so later syndicated copies are dropped.
    # Look back further than max_age so that stale articles are reported (FR-11), not silently ignored.
    candidates = sorted(store.articles_since(now - LOOKBACK), key=lambda a: a.published_at)
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    kept: list[Article] = []
    for article in candidates:
        src = sources.get(article.source_id)
        if src is None or src.status != "active":
            continue
        reason = rejection_reason(article, src, now, max_age, seen_urls, seen_titles)
        if reason:
            report.dropped.append((article.title, reason))
            continue
        seen_urls.add(article.canonical_url)
        seen_titles.add(title_key(article.title))
        kept.append(article)
    report.kept = len(kept)

    # 3. Cluster, summarise (with citations), translate.
    summarizer = ExtractiveSummarizer(cfg["max_sentences"])
    translator = NoTranslator()
    articles_by_id = {a.id: a for a in kept}
    clusters = cluster_articles(
        kept, cfg["cluster_threshold"], timedelta(hours=cfg["cluster_window_hours"])
    )
    events: list[Event] = []
    summaries: dict[str, Summary] = {}
    for group in clusters:
        event = build_event(group)
        base, dropped = validate_summary(summarizer.summarize(event, group), event)
        report.dropped_sentences += dropped
        if not base.sentences:  # Q-1: no sourced sentence, no event
            continue
        pending: list[str] = []
        for lang in cfg["languages"]:
            if lang == event.language:
                continue
            try:
                translator.translate(base, lang)  # result is stored once the adapter exists
            except NotConfigured:
                pending.append(lang)
        summaries[event.id] = dataclasses.replace(base, translations_pending=tuple(pending))
        events.append(event)

    # 4. Rank and select for the edition window.
    tz_name = cfg["edition_timezone"]
    start, end = edition_window(now, tz_name, tuple(cfg["edition_hours"]))
    scored = [
        dataclasses.replace(e, score=score(e, now), new=e.first_published >= start) for e in events
    ]
    chosen = select(scored, cfg["max_events_per_edition"], cfg["max_events_per_topic"])
    report.events = len(chosen)

    # 5. Each chosen event becomes (or updates) a desk story in the shared story model.
    for event in chosen:
        group = [articles_by_id[i] for i in event.article_ids]
        previous = store.get_story(story_id_for(group))
        story = story_from_event(event, summaries[event.id], group, sources, now, previous)
        if story.sentences and changed(story, previous):
            store.save_story(story)
            report.stories += 1
    store.commit()

    # 6. Export JSON for the frontend: feed stories and agent stories together.
    export_site(store, Path(site_dir), now)
    report.editions = sorted({e.language for e in chosen})
    return report
