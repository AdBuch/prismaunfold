"""Domain model for the MVP. Mirrors the domain model in the project document
'claude/mvp-architektur-vorschlag.md' (section 3), reduced to what Phase 1 needs."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any

RIGHTS = ("excerpt_only", "full_text", "link_only")
STATUSES = ("pending_review", "active", "blocked")
AI_POLICIES = ("exclude", "label")


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    feed_url: str
    languages: tuple[str, ...]
    rights: str = "excerpt_only"
    status: str = "pending_review"
    ai_policy: str = "exclude"
    regions: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.rights not in RIGHTS:
            raise ValueError(f"{self.id}: unknown rights {self.rights!r}")
        if self.status not in STATUSES:
            raise ValueError(f"{self.id}: unknown status {self.status!r}")
        if self.ai_policy not in AI_POLICIES:
            raise ValueError(f"{self.id}: unknown ai_policy {self.ai_policy!r}")
        if not self.languages:
            raise ValueError(f"{self.id}: at least one language required")

    @property
    def language(self) -> str:
        """MVP: the first listed language is the language of all its articles."""
        return self.languages[0]


@dataclass(frozen=True)
class Article:
    id: str
    source_id: str
    url: str
    canonical_url: str
    title: str
    published_at: datetime
    language: str
    excerpt: str = ""
    body_text: str | None = None
    image_url: str | None = None
    image_source_url: str | None = None
    image_credit: str | None = None
    ai_disclosed: bool = False
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class Event:
    id: str
    language: str
    title: str
    article_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    topics: tuple[str, ...]
    first_published: datetime
    last_published: datetime
    single_source: bool = False
    score: float = 0.0
    new: bool = False


@dataclass(frozen=True)
class Sentence:
    text: str
    article_ids: tuple[str, ...]


@dataclass(frozen=True)
class Summary:
    event_id: str
    language: str
    sentences: tuple[Sentence, ...]
    generator: str
    prompt_version: str
    machine_translated: bool = False
    translated_from: str | None = None
    translations_pending: tuple[str, ...] = ()


def to_jsonable(obj: Any) -> Any:
    """Convert dataclasses, datetimes and tuples into plain JSON-serialisable values."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj


def article_from_dict(d: dict[str, Any]) -> Article:
    return Article(
        **{
            **d,
            "published_at": datetime.fromisoformat(d["published_at"]),
            "topics": tuple(d.get("topics", ())),
        }
    )


# --- Stories written by collector agents -------------------------------------------------


@dataclass(frozen=True)
class StorySource:
    url: str
    title: str
    publisher: str
    published_at: str | None = None
    language: str | None = None


@dataclass(frozen=True)
class StorySentence:
    text: str
    source_urls: tuple[str, ...]


@dataclass(frozen=True)
class Story:
    """One publishable news story with a source for every sentence.

    Two producers share this model: a collector agent's report on a topic
    (agent = codex, claude, vibe, goose) and the feed desk's extractive summary of
    an event (agent = desk). Keeping one model means one archive, one verification
    path and one export for both.
    """

    id: str
    slug: str
    agent: str
    model: str
    topic: str
    topic_slug: str
    language: str
    edition: str
    created_at: datetime
    headline: str
    sentences: tuple[StorySentence, ...]
    sources: tuple[StorySource, ...]
    uncertainties: tuple[str, ...] = ()
    nothing_new: bool = False
    disputes: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    updated_at: datetime | None = None
    # Result of verification.verify_story, stored so an edition shows what was known then.
    verification: dict[str, Any] | None = None

    @property
    def day(self) -> str:
        """Calendar day (UTC) of first publication, YYYY-MM-DD. Edition ids start with it."""
        return self.edition[:10]


def story_from_dict(d: dict[str, Any]) -> Story:
    updated = d.get("updated_at")
    return Story(
        **{
            **d,
            "created_at": datetime.fromisoformat(d["created_at"]),
            "updated_at": datetime.fromisoformat(updated) if updated else None,
            "sentences": tuple(
                StorySentence(s["text"], tuple(s["source_urls"])) for s in d["sentences"]
            ),
            "sources": tuple(StorySource(**s) for s in d["sources"]),
            "uncertainties": tuple(d.get("uncertainties", ())),
            "disputes": tuple(d.get("disputes", ())),
            "regions": tuple(d.get("regions", ())),
        }
    )
