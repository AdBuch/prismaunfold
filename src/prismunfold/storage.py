"""Persistence. `open_store` picks the backend from the target:

    postgresql://user:pass@host/db   PostgreSQL (storage_pg.PostgresStore, needs psycopg)
    anything else                    a SQLite file (stdlib only; tests and local runs)

Both backends offer the same methods. Records are JSON documents next to indexed columns.
"""

from __future__ import annotations

import fcntl
import json
import re
import sqlite3
import time
from contextlib import contextmanager
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
-- Added in schema version 2 (milestone 0.2). Additive only: older databases gain
-- these tables on the next start; nothing existing is changed.
CREATE TABLE IF NOT EXISTS contributions (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    source_key TEXT NOT NULL,
    edition_date TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    generated_at TEXT,
    received_at TEXT NOT NULL,
    state TEXT NOT NULL,
    data TEXT NOT NULL,
    UNIQUE (source_key, content_hash)
);
CREATE INDEX IF NOT EXISTS contributions_date ON contributions (edition_date, provider);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (1, '1970-01-01T00:00:00+00:00');
INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (2, datetime('now'));
"""

SCHEMA_VERSION = 2

WORD_RE = re.compile(r"\w+")


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def open_store(target: str | Path):
    """Return a PostgresStore for a postgres URL, else a SQLite Store for the path."""
    if str(target).startswith(("postgres://", "postgresql://")):
        from .storage_pg import PostgresStore  # imported late: psycopg is optional

        return PostgresStore(str(target))
    return Store(target)


class LockTimeout(RuntimeError):
    pass


class Store:
    def __init__(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = Path(path)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    @contextmanager
    def lock(self, name: str, timeout: float = 120):
        """Exclusive lock shared by every process using this database (publication, export).

        Re-entrant within one Store, so publication can export while holding it.
        """
        held = self.__dict__.setdefault("_held", {})
        if held.get(name):
            held[name] += 1
            try:
                yield
            finally:
                held[name] -= 1
            return
        safe = re.sub(r"[^a-z0-9_-]", "_", name.lower())
        with open(self.path.with_name(f"{self.path.name}.{safe}.lock"), "a") as handle:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > deadline:
                        raise LockTimeout(f"lock {name} is held by another process") from None
                    time.sleep(0.2)
            held[name] = 1
            try:
                yield
            finally:
                held[name] = 0
                fcntl.flock(handle, fcntl.LOCK_UN)

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

    def get_edition(self, edition_id: str) -> dict | None:
        row = self.db.execute("SELECT data FROM editions WHERE id = ?", (edition_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_edition_revision(self, edition_id: str, language: str, revised_at: datetime, payload: dict) -> bool:
        timestamp = revised_at.astimezone(timezone.utc).isoformat(timespec="microseconds")
        result = self.db.execute(
            "INSERT INTO editions (id, language, built_at, data) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET language = excluded.language, "
            "built_at = excluded.built_at, data = excluded.data "
            "WHERE excluded.built_at >= editions.built_at AND excluded.data <> editions.data",
            (edition_id, language, timestamp, json.dumps(payload, ensure_ascii=False)),
        )
        return result.rowcount == 1

    def schema_version(self) -> int:
        return self.db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]

    # --- Editorial contributions (provenance, revisions, states); see contributions.py ---

    def save_contribution(self, c: dict) -> bool:
        """Insert a received revision. False if the same content was already recorded."""
        result = self.db.execute(
            "INSERT INTO contributions (id, provider, source_key, edition_date, content_hash, generated_at, "
            "received_at, state, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(source_key, content_hash) DO NOTHING",
            (c["id"], c["provider"], c["source_key"], c["edition_date"], c["content_hash"],
             c.get("generated_at"), c["received_at"], c["state"], json.dumps(c, ensure_ascii=False)),
        )
        return result.rowcount == 1

    def update_contribution(self, c: dict) -> None:
        self.db.execute("UPDATE contributions SET state = ?, data = ? WHERE id = ?",
                        (c["state"], json.dumps(c, ensure_ascii=False), c["id"]))

    def get_contribution(self, contribution_id: str) -> dict | None:
        row = self.db.execute("SELECT data FROM contributions WHERE id = ?", (contribution_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_contributions(self, source_key: str | None = None, edition_date: str | None = None,
                           provider: str | None = None) -> list[dict]:
        rows = self.db.execute(
            "SELECT data FROM contributions WHERE (? IS NULL OR source_key = ?) "
            "AND (? IS NULL OR edition_date = ?) AND (? IS NULL OR provider = ?) "
            "ORDER BY edition_date, COALESCE(generated_at, ''), received_at",
            (source_key, source_key, edition_date, edition_date, provider, provider),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

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
