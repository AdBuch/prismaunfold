"""Write everything the frontend reads, as static JSON under site/api/v1/.

The pipeline renders no HTML. The files follow the frontend's typed models
(frontend/src/models.ts), so the frontend's API service is a thin fetch layer.

    api/v1/index.json            latest edition date, sections, languages, regions
    api/v1/editions.json         every daily edition, newest first (Edition[])
    api/v1/stories/<slug>.json   one story with per-sentence sources and verification
    api/v1/topics/<slug>.json    timeline of a topic (Topic)
    api/v1/magazines.json        deep dives (MagazineFeature[]); empty until one exists

An edition is frozen once its day is over: it is stored and served as published.
Story files always show the latest state of a story, including later verification.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .compose import compose_edition, image_for, state_of
from .models import Story
from .normalize import sha1_id
from .reports import AGENT_NAMES
from .verification import DISPUTED, REVIEW_REQUIRED, SUPPORTED

API = "api/v1"
DISCLOSURE_AGENT = (
    "Researched and written by an AI agent ({name}, model {model}). "
    "Not reviewed by a human editor."
)
DISCLOSURE_DESK = (
    "Assembled automatically from publisher feeds. Each sentence is taken from the title "
    "or excerpt of the article it cites. Not reviewed by a human editor."
)
STATE_NOTE = {
    SUPPORTED: "Each sentence is backed by the source it cites.",
    DISPUTED: "Sources contradict each other on at least one point.",
    REVIEW_REQUIRED: "Thinly sourced or not fully checked. Read with care.",
    "unverified": "Every sentence names a source, but nobody has checked that the sources say this.",
}


def _write(path: Path, payload: object) -> str:
    """Write atomically so the web server never serves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return str(path)


def story_payload(story: Story, related: list[Story]) -> dict:
    """One story in the frontend's `Story` shape."""
    source_ids = {s.url: sha1_id(s.url)[:12] for s in story.sources}
    verification = story.verification or {"state": "unverified", "reasons": [], "sentences": []}
    claims = verification.get("sentences") or []
    state = state_of(story)
    name = AGENT_NAMES.get(story.agent, story.agent)
    payload = {
        "id": story.id,
        "slug": story.slug,
        "section": story.topic_slug,
        "headline": story.headline,
        "standfirst": story.sentences[0].text if story.sentences else "",
        "body": [s.text for s in story.sentences],
        "sentences": [
            {
                "text": s.text,
                "sourceIds": [source_ids[u] for u in s.source_urls if u in source_ids],
                "verification": claims[i] if i < len(claims) else None,
            }
            for i, s in enumerate(story.sentences)
        ],
        "byline": name,
        "agent": story.agent,
        "model": story.model,
        "aiDisclosure": DISCLOSURE_DESK
        if story.agent == "desk"
        else DISCLOSURE_AGENT.format(name=name, model=story.model),
        "publishedAt": story.created_at.isoformat(),
        "corrections": [],
        "sources": [
            {
                "id": source_ids[s.url],
                "name": s.publisher,
                "title": s.title or s.url,
                "url": s.url,
                **({"publishedAt": s.published_at} if s.published_at else {}),
            }
            for s in story.sources
        ],
        # The legacy field never says "established": nothing was verified by a person (Q-4).
        "confidence": "disputed" if state == DISPUTED else "reported",
        "confidenceNote": STATE_NOTE[state],
        "verification": {k: v for k, v in verification.items() if k != "sentences"},
        "uncertainties": list(story.uncertainties),
        "disputes": list(story.disputes),
        "topicSlug": story.topic_slug,
        "relatedSlugs": [r.slug for r in related if r.id != story.id],
        "image": image_for(story),
        "language": story.language,
        "regions": list(story.regions),
        "demo": False,
    }
    if story.updated_at:
        payload["updatedAt"] = story.updated_at.isoformat()
    return payload


def topic_payload(stories: list[Story]) -> dict:
    """Timeline of one topic in the frontend's `Topic` shape. Stories sorted oldest first."""
    first = stories[0]
    events = []
    for story in stories:
        events.append(
            {
                "id": f"report-{story.id[:10]}",
                "date": story.day,
                "kind": "report",
                "title": story.headline,
                "summary": story.sentences[0].text,
                "storySlug": story.slug,
                "editionDate": story.day,
                "sources": [s.publisher for s in story.sources],
            }
        )
        if story.updated_at and story.updated_at.date().isoformat() != story.day:
            events.append(
                {
                    "id": f"update-{story.id[:10]}",
                    "date": story.updated_at.date().isoformat(),
                    "kind": "update",
                    "title": f"More sources on: {story.headline}",
                    "summary": f"The story now draws on {len(story.sources)} sources.",
                    "storySlug": story.slug,
                    "editionDate": story.updated_at.date().isoformat(),
                }
            )
    writers = sorted({AGENT_NAMES.get(s.agent, s.agent) for s in stories})
    return {
        "slug": first.topic_slug,
        "title": first.topic,
        "summary": f"{len(stories)} reports so far, written by {', '.join(writers)}.",
        "section": first.topic_slug,
        "events": sorted(events, key=lambda e: e["date"]),
        "image": image_for(first),
        "demo": False,
    }


def _days_of(story: Story) -> set[str]:
    """Days on which the story belongs in an edition: first report, and a later update."""
    days = {story.day}
    if story.updated_at:
        days.add(story.updated_at.astimezone(timezone.utc).date().isoformat())
    return days


def export_site(store, site_dir: str | Path, now: datetime | None = None) -> list[str]:
    """Rebuild the JSON API from the store. Return the written paths."""
    root = Path(site_dir) / API
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stories = [s for s in store.all_stories() if s.sentences and not s.nothing_new]
    written: list[str] = []

    # Stories, with the other writers' reports on the same topic and day as related.
    groups: dict[tuple[str, str, str], list[Story]] = {}
    for story in stories:
        groups.setdefault((story.topic_slug, story.language, story.day), []).append(story)
    for story in stories:
        related = groups[(story.topic_slug, story.language, story.day)] if story.agent != "desk" else []
        written.append(_write(root / "stories" / f"{story.slug}.json", story_payload(story, related)))

    # Topic timelines.
    by_topic: dict[str, list[Story]] = {}
    for story in sorted(stories, key=lambda s: s.created_at):
        by_topic.setdefault(story.topic_slug, []).append(story)
    for slug, items in by_topic.items():
        written.append(_write(root / "topics" / f"{slug}.json", topic_payload(items)))

    # Daily editions. Days before yesterday are frozen as stored.
    frozen_before = (now - timedelta(days=1)).date().isoformat()
    stored = store.daily_editions()
    by_day: dict[str, list[Story]] = {}
    for story in stories:
        for day in _days_of(story):
            by_day.setdefault(day, []).append(story)
    editions: dict[str, dict] = {d: e for d, e in stored.items() if d < frozen_before}
    for number, day in enumerate(sorted(set(by_day) | set(editions)), start=1):
        if day in editions:
            continue
        edition = compose_edition(by_day[day], day, number)
        if edition["placements"]:
            editions[day] = edition
            store.save_edition(f"daily|{day}", "*", now, edition)
    store.commit()
    ordered = [editions[d] for d in sorted(editions, reverse=True)]
    written.append(_write(root / "editions.json", ordered))
    written.append(_write(root / "magazines.json", []))

    sections: dict[str, str] = {}
    for story in stories:
        sections.setdefault(story.topic_slug, story.topic)
    written.append(
        _write(
            root / "index.json",
            {
                "generatedAt": now.isoformat(),
                "latest": ordered[0]["date"] if ordered else None,
                "editionCount": len(ordered),
                "storyCount": len(stories),
                "sections": [{"id": k, "label": v} for k, v in sorted(sections.items())],
                "languages": sorted({s.language for s in stories}),
                "regions": sorted({r for s in stories for r in s.regions}),
            },
        )
    )
    return written
