"""The feed desk: turns a clustered event from the RSS feeds into a `Story`.

Feed events and agent reports thereby share one model, one archive, one verification
path and one export. A desk story is extractive: each sentence is taken from the
title or excerpt of the article it cites, and the publisher is always named.

An event keeps its identity while it grows. The story id hangs on the earliest
article of the cluster, so a second outlet reporting the same event updates the
existing story instead of publishing it again. `updated_at` moves only when a new
article joined, which is what counts as a development here.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from .edition import agent_edition
from .models import Article, Event, Source, Story, StorySentence, StorySource, Summary
from .normalize import sha1_id
from .reports import slugify
from .verification import ExtractiveSupport, verify_story

GENERAL_TOPIC = "general"


def story_id_for(articles: list[Article]) -> str:
    """Stable id: the earliest article anchors the event (articles sorted oldest first)."""
    return sha1_id("desk", articles[0].id)


def story_from_event(
    event: Event,
    summary: Summary,
    articles: list[Article],
    sources: dict[str, Source],
    now: datetime,
    previous: Story | None = None,
) -> Story:
    """Build the desk story for an event. `articles` must be sorted oldest first."""
    by_id = {a.id: a for a in articles}
    story_sources = tuple(
        StorySource(
            url=a.canonical_url,
            title=a.title,
            publisher=sources[a.source_id].name if a.source_id in sources else a.source_id,
            published_at=a.published_at.isoformat(),
            language=a.language,
        )
        for a in articles
    )
    sentences = tuple(
        StorySentence(s.text, tuple(by_id[i].canonical_url for i in s.article_ids if i in by_id))
        for s in summary.sentences
    )
    sentences = tuple(s for s in sentences if s.source_urls)
    cited = {u for s in sentences for u in s.source_urls}
    topic = event.topics[0] if event.topics else GENERAL_TOPIC
    regions = tuple(
        dict.fromkeys(r for a in articles if a.source_id in sources for r in sources[a.source_id].regions)
    )
    story_id = story_id_for(articles)

    grew = previous is not None and {s.url for s in story_sources} - {s.url for s in previous.sources}
    story = Story(
        id=story_id,
        slug=previous.slug if previous else f"{slugify(event.title)}-{story_id[:8]}",
        agent="desk",
        model=summary.generator,
        topic=topic,
        topic_slug=slugify(topic),
        language=event.language,
        edition=previous.edition if previous else agent_edition(now),
        created_at=previous.created_at if previous else now,
        headline=event.title,
        sentences=sentences,
        sources=tuple(s for s in story_sources if s.url in cited),
        regions=regions,
        updated_at=now if grew else (previous.updated_at if previous else None),
    )
    return dataclasses.replace(story, verification=verify_story(story, None, ExtractiveSupport()))


def changed(story: Story, previous: Story | None) -> bool:
    """True when the story is new or says something different from the stored version."""
    if previous is None:
        return True
    return (story.sentences, story.sources, story.headline) != (
        previous.sentences,
        previous.sources,
        previous.headline,
    )
