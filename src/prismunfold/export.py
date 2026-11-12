"""Write everything the frontend reads, as static JSON under site/api/v1/.

The pipeline renders no HTML. Field names are camelCase and follow the frontend's
typed models (Story, SourceReference) where the two overlap.

    api/v1/index.json                       list of editions, newest first
    api/v1/editions/<edition>.json          stories of one edition, grouped by topic
    api/v1/stories/<slug>.json              one story with per-sentence sources
    api/v1/briefings/<lang>/latest.json     feed-based events of the current edition window
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Article, Event, Story, Summary, to_jsonable
from .normalize import sha1_id
from .reports import AGENT_NAMES
from .storage import Store

API = "api/v1"
AI_DISCLOSURE = "Researched and written by an AI agent ({agent}, model {model}). Not reviewed by a human editor."


def _write(path: Path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def story_payload(story: Story, related: list[Story]) -> dict:
    source_ids = {s.url: sha1_id(s.url) for s in story.sources}
    disputed = bool(story.uncertainties)
    return {
        "id": story.id,
        "slug": story.slug,
        "language": story.language,
        "edition": story.edition,
        "topic": story.topic,
        "topicSlug": story.topic_slug,
        "headline": story.headline,
        "standfirst": story.sentences[0].text if story.sentences else "",
        "sentences": [
            {"text": s.text, "sourceIds": [source_ids[u] for u in s.source_urls]}
            for s in story.sentences
        ],
        "byline": AGENT_NAMES.get(story.agent, story.agent),
        "agent": story.agent,
        "model": story.model,
        "aiDisclosure": AI_DISCLOSURE.format(
            agent=AGENT_NAMES.get(story.agent, story.agent), model=story.model
        ),
        "publishedAt": story.created_at.isoformat(),
        "corrections": [],
        "sources": [
            {
                "id": source_ids[s.url],
                "name": s.publisher,
                "title": s.title,
                "url": s.url,
                "publishedAt": s.published_at,
            }
            for s in story.sources
        ],
        # Never "established": nothing here has been verified by a person (Q-4).
        "confidence": "disputed" if disputed else "reported",
        "confidenceNote": " ".join(story.uncertainties)
        or f"Summarised from {len(story.sources)} sources.",
        # Other writers' reports on the same topic in the same edition.
        "relatedSlugs": [r.slug for r in related if r.id != story.id],
        "image": None,
    }


def export_stories(store: Store, site_dir: str | Path, generated_at: datetime | None = None) -> list[str]:
    """Rebuild the story and edition files from the store. Return the written paths."""
    root = Path(site_dir) / API
    generated = (generated_at or datetime.now(timezone.utc)).isoformat()
    stories = [s for s in store.all_stories() if not s.nothing_new and s.sentences]
    written: list[str] = []

    by_edition: dict[str, list[Story]] = {}
    for story in stories:
        by_edition.setdefault(story.edition, []).append(story)

    for edition, items in by_edition.items():
        topics: dict[tuple[str, str], list[Story]] = {}
        for story in sorted(items, key=lambda s: (s.topic_slug, s.language, s.agent)):
            topics.setdefault((story.topic_slug, story.language), []).append(story)
        for group in topics.values():
            for story in group:
                written.append(_write(root / "stories" / f"{story.slug}.json", story_payload(story, group)))
        written.append(
            _write(
                root / "editions" / f"{edition}.json",
                {
                    "edition": edition,
                    "generatedAt": generated,
                    "topics": [
                        {
                            "topicSlug": slug,
                            "topic": group[0].topic,
                            "language": lang,
                            "stories": [
                                {
                                    "slug": s.slug,
                                    "headline": s.headline,
                                    "standfirst": s.sentences[0].text,
                                    "byline": AGENT_NAMES.get(s.agent, s.agent),
                                    "agent": s.agent,
                                    "sourceCount": len(s.sources),
                                    "confidence": "disputed" if s.uncertainties else "reported",
                                }
                                for s in group
                            ],
                        }
                        for (slug, lang), group in topics.items()
                    ],
                },
            )
        )

    written.append(
        _write(
            root / "index.json",
            {
                "generatedAt": generated,
                "editions": [
                    {"edition": e, "storyCount": len(by_edition[e]), "path": f"editions/{e}.json"}
                    for e in sorted(by_edition, reverse=True)
                ],
            },
        )
    )
    return written


def export_briefing(
    site_dir: str | Path,
    pages: dict[str, list[tuple[Event, Summary, list[Article]]]],
    label: str,
    start: datetime,
    end: datetime,
    generated_at: datetime,
    tz_name: str,
    names: dict[str, str],
) -> list[str]:
    """Write the feed-based events of one edition window, one file set per language."""
    root = Path(site_dir) / API / "briefings"
    stamp = start.strftime("%Y%m%dT%H%MZ")
    written: list[str] = []
    for lang, items in pages.items():
        payload = {
            "language": lang,
            "edition": label,
            "timezone": tz_name,
            "windowStart": start.isoformat(),
            "windowEnd": end.isoformat(),
            "generatedAt": generated_at.isoformat(),
            "sourceNames": {
                sid: names.get(sid, sid) for e, _, _ in items for sid in e.source_ids
            },
            "events": [
                {"event": to_jsonable(e), "summary": to_jsonable(s), "articles": to_jsonable(arts)}
                for e, s, arts in items
            ],
        }
        for name in (f"{stamp}.json", "latest.json"):
            written.append(_write(root / lang / name, payload))
    return written
