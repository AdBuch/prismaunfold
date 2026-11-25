"""Retrieval over everything already published, so new reports build on old ones.

MVP: keyword retrieval (SQLite FTS5, BM25 ranking) over headline and text. This is the
"R" of RAG without embeddings; a vector index (pgvector) can replace `Store.search_stories`
later behind the same function.
"""

from __future__ import annotations

from .models import Story
from .reports import AGENT_NAMES, slugify
from .storage import Store

INTRO = """# Prior PrismUnfold coverage of this topic

These are earlier reports from our own archive. Use them to avoid repeating what
readers already know and to report what has changed since.

- Treat them as background, not as a source. Never cite PrismUnfold itself.
- A claim from an earlier report may be reused only if you reopen its source now.
- If an earlier report turns out to be wrong, say so in `uncertainties`.
"""


def related_stories(store: Store, topic: str, language: str | None = None, limit: int = 5) -> list[Story]:
    """Earlier stories on the same topic first, then other archive hits for the topic words."""
    found: dict[str, Story] = {}
    for story in store.stories_for_topic(slugify(topic), language, limit):
        found[story.id] = story
    for story in store.search_stories(topic, language, limit):
        found.setdefault(story.id, story)
    ordered = sorted(found.values(), key=lambda s: s.created_at, reverse=True)
    return [s for s in ordered if not s.nothing_new][:limit]


def prior_coverage(store: Store, topic: str, language: str | None = None, limit: int = 5) -> str:
    """Markdown block for the agent prompt. Empty string when the archive has nothing."""
    stories = related_stories(store, topic, language, limit)
    if not stories:
        return ""
    parts = [INTRO]
    for story in stories:
        parts.append(
            f"\n## {story.headline}\n\n"
            f"Edition {story.edition}, written by {AGENT_NAMES.get(story.agent, story.agent)}, "
            f"language {story.language}.\n"
        )
        for sentence in story.sentences:
            parts.append(f"- {sentence.text} (sources: {', '.join(sentence.source_urls)})")
        for note in story.uncertainties:
            parts.append(f"- Uncertain: {note}")
    return "\n".join(parts) + "\n"
