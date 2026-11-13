"""Persistence. `open_store` picks the backend from the target:

    postgresql://user:pass@host/db   PostgreSQL (storage_pg.PostgresStore, needs psycopg)
    anything else                    a SQLite file (stdlib only; tests and local runs)

Both backends offer the same methods. Records are JSON documents next to indexed columns.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Article, Story, article_from_dict, story_from_dict, to_jsonable

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL UNIQUE,
    published_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS articles_published ON articles (published_at);
CREATE TABLE IF NOT EXISTS editions (
    id TEXT PRIMARY KEY,
    language TEXT NOT NULL,
    built_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stories (
    id TEXT PRIMARY KEY,
    topic_slug TEXT NOT NULL,
    language TEXT NOT NULL,
    agent TEXT NOT NULL,
    edition TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS stories_topic ON stories (topic_slug, created_at);
CREATE VIRTUAL TABLE IF NOT EXISTS story_index USING fts5(
    story_id UNINDEXED,
    language UNINDEXED,
    topic,
    headline,
    body,
    tokenize = "unicode61 remove_diacritics 2"
);
"""

WORD_RE = re.compile(r"\w+")


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def open_store(target: str | Path):
    """Return a PostgresStore for a postgres URL, else a SQLite Store for the path."""
    if str(target).startswith(("postgres://", "postgresql://")):
        from .storage_pg import PostgresStore  # imported late: psycopg is optional

        return PostgresStore(str(target))
    return Store(target)


class Store:
    def __init__(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.commit()
        self.db.close()

    def commit(self) -> None:
        self.db.commit()

    def save_article(self, article: Article) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO articles (id, canonical_url, published_at, data) VALUES (?, ?, ?, ?)",
            (
                article.id,
                article.canonical_url,
                _utc_iso(article.published_at),
                json.dumps(to_jsonable(article), ensure_ascii=False),
            ),
        )

    def articles_since(self, since: datetime) -> list[Article]:
        rows = self.db.execute(
            "SELECT data FROM articles WHERE published_at >= ?", (_utc_iso(since),)
        ).fetchall()
        return [article_from_dict(json.loads(row[0])) for row in rows]

    def save_edition(self, edition_id: str, language: str, built_at: datetime, payload: dict) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO editions (id, language, built_at, data) VALUES (?, ?, ?, ?)",
            (edition_id, language, _utc_iso(built_at), json.dumps(payload, ensure_ascii=False)),
        )

    # --- Stories written by collector agents, plus the archive index over them ---

    def save_story(self, story: Story) -> None:
        """Insert or replace a story and keep the search index in step."""
        self.db.execute(
            "INSERT OR REPLACE INTO stories (id, topic_slug, language, agent, edition, created_at, data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                story.id,
                story.topic_slug,
                story.language,
                story.agent,
                story.edition,
                _utc_iso(story.created_at),
                json.dumps(to_jsonable(story), ensure_ascii=False),
            ),
        )
        self.db.execute("DELETE FROM story_index WHERE story_id = ?", (story.id,))
        self.db.execute(
            "INSERT INTO story_index (story_id, language, topic, headline, body) VALUES (?, ?, ?, ?, ?)",
            (
                story.id,
                story.language,
                story.topic,
                story.headline,
                " ".join(s.text for s in story.sentences),
            ),
        )

    def daily_editions(self) -> dict[str, dict]:
        """Stored daily editions by date (YYYY-MM-DD)."""
        rows = self.db.execute("SELECT id, data FROM editions WHERE id LIKE 'daily|%'").fetchall()
        return {row[0].split("|", 1)[1]: json.loads(row[1]) for row in rows}

    def get_story(self, story_id: str) -> Story | None:
        row = self.db.execute("SELECT data FROM stories WHERE id = ?", (story_id,)).fetchone()
        return story_from_dict(json.loads(row[0])) if row else None

    def has_story(self, story_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM stories WHERE id = ?", (story_id,)).fetchone() is not None

    def all_stories(self) -> list[Story]:
        rows = self.db.execute("SELECT data FROM stories ORDER BY created_at").fetchall()
        return [story_from_dict(json.loads(row[0])) for row in rows]

    def stories_for_topic(self, topic_slug: str, language: str | None = None, limit: int = 5) -> list[Story]:
        rows = self.db.execute(
            "SELECT data FROM stories WHERE topic_slug = ? AND (? IS NULL OR language = ?) "
            "ORDER BY created_at DESC LIMIT ?",
            (topic_slug, language, language, limit),
        ).fetchall()
        return [story_from_dict(json.loads(row[0])) for row in rows]

    def search_stories(self, query: str, language: str | None = None, limit: int = 5) -> list[Story]:
        """Keyword search over the archive, best match first. Any query word may match."""
        words = [w for w in WORD_RE.findall(query) if len(w) >= 3]
        if not words:
            return []
        match = " OR ".join(f'"{w}"' for w in words)
        rows = self.db.execute(
            "SELECT s.data FROM story_index JOIN stories s ON s.id = story_index.story_id "
            "WHERE story_index MATCH ? AND (? IS NULL OR story_index.language = ?) "
            "ORDER BY bm25(story_index) LIMIT ?",
            (match, language, language, limit),
        ).fetchall()
        return [story_from_dict(json.loads(row[0])) for row in rows]
