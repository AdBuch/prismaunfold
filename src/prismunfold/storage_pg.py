"""PostgreSQL persistence. Same methods as the SQLite `Store`, selected by a postgres:// URL.

Needs the `psycopg` package (version 3), which the pipeline image installs. Records are
JSONB documents next to indexed columns. The archive search uses a tsvector column:
keyword search, any query word may match, headline and topic weigh more than the text.
Text is folded (lower case, no diacritics) on the way in and in the query, so
"Zürich" finds "Zurich"; this matches the SQLite index and needs no extension.
"""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from datetime import datetime

import psycopg
from psycopg.types.json import Jsonb

from .models import Article, Story, article_from_dict, story_from_dict, to_jsonable
from .normalize import fold

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS articles (
        id TEXT PRIMARY KEY,
        canonical_url TEXT NOT NULL UNIQUE,
        published_at TIMESTAMPTZ NOT NULL,
        data JSONB NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS articles_published ON articles (published_at)",
    """
    CREATE TABLE IF NOT EXISTS editions (
        id TEXT PRIMARY KEY,
        language TEXT NOT NULL,
        built_at TIMESTAMPTZ NOT NULL,
        data JSONB NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stories (
        id TEXT PRIMARY KEY,
        topic_slug TEXT NOT NULL,
        language TEXT NOT NULL,
        agent TEXT NOT NULL,
        edition TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        data JSONB NOT NULL,
        search TSVECTOR NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS stories_topic ON stories (topic_slug, created_at)",
    "CREATE INDEX IF NOT EXISTS stories_search ON stories USING GIN (search)",
    # Schema version 2 (milestone 0.2): additive only.
    """
    CREATE TABLE IF NOT EXISTS contributions (
        id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        source_key TEXT NOT NULL,
        edition_date DATE NOT NULL,
        content_hash TEXT NOT NULL,
        generated_at TIMESTAMPTZ,
        received_at TIMESTAMPTZ NOT NULL,
        state TEXT NOT NULL,
        data JSONB NOT NULL,
        UNIQUE (source_key, content_hash)
    )
    """,
    "CREATE INDEX IF NOT EXISTS contributions_date ON contributions (edition_date, provider)",
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL
    )
    """,
    "INSERT INTO schema_migrations (version, applied_at) VALUES (1, 'epoch') ON CONFLICT DO NOTHING",
    "INSERT INTO schema_migrations (version, applied_at) VALUES (2, now()) ON CONFLICT DO NOTHING",
)

SCHEMA_VERSION = 2

WORD_RE = re.compile(r"\w+")


def is_postgres_url(target: str) -> bool:
    return str(target).startswith(("postgres://", "postgresql://"))


class PostgresStore:
    def __init__(self, url: str, connect_attempts: int = 10) -> None:
        last_error: Exception | None = None
        for attempt in range(connect_attempts):
            try:
                self.db = psycopg.connect(url)
                break
            except psycopg.OperationalError as exc:  # database still starting
                last_error = exc
                time.sleep(min(2 + attempt, 5))
        else:
            raise RuntimeError(f"could not connect to PostgreSQL: {last_error}")
        for statement in SCHEMA:
            self.db.execute(statement)
        self.db.commit()

    @contextmanager
    def lock(self, name: str, timeout: float = 120):
        """Session-level advisory lock shared by every pipeline process on this database.

        Re-entrant within one connection (as PostgreSQL advisory locks are).
        """
        held = self.__dict__.setdefault("_held", {})
        if held.get(name):
            held[name] += 1
            try:
                yield
            finally:
                held[name] -= 1
            return
        deadline = time.monotonic() + timeout
        while not self.db.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (name,)).fetchone()[0]:
            if time.monotonic() > deadline:
                from .storage import LockTimeout
                raise LockTimeout(f"lock {name} is held by another process")
            time.sleep(0.5)
        held[name] = 1
        try:
            yield
        finally:
            held[name] = 0
            # Advisory unlock is not transactional; the caller decides commit or rollback.
            self.db.execute("SELECT pg_advisory_unlock(hashtext(%s))", (name,))

    def close(self) -> None:
        self.db.commit()
        self.db.close()

    def commit(self) -> None:
        self.db.commit()

    # --- Feed articles and editions ---

    def save_article(self, article: Article) -> None:
        self.db.execute(
            "INSERT INTO articles (id, canonical_url, published_at, data) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (article.id, article.canonical_url, article.published_at, Jsonb(to_jsonable(article))),
        )

    def articles_since(self, since: datetime) -> list[Article]:
        rows = self.db.execute("SELECT data FROM articles WHERE published_at >= %s", (since,)).fetchall()
        return [article_from_dict(row[0]) for row in rows]

    def save_edition(self, edition_id: str, language: str, built_at: datetime, payload: dict) -> None:
        self.db.execute(
            "INSERT INTO editions (id, language, built_at, data) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET language = EXCLUDED.language, "
            "built_at = EXCLUDED.built_at, data = EXCLUDED.data",
            (edition_id, language, built_at, Jsonb(payload)),
        )

    def get_edition(self, edition_id: str) -> dict | None:
        row = self.db.execute("SELECT data FROM editions WHERE id = %s", (edition_id,)).fetchone()
        return row[0] if row else None

    def save_edition_revision(self, edition_id: str, language: str, revised_at: datetime, payload: dict) -> bool:
        result = self.db.execute(
            "INSERT INTO editions (id, language, built_at, data) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET language = EXCLUDED.language, "
            "built_at = EXCLUDED.built_at, data = EXCLUDED.data "
            "WHERE EXCLUDED.built_at >= editions.built_at AND EXCLUDED.data <> editions.data",
            (edition_id, language, revised_at, Jsonb(payload)),
        )
        return result.rowcount == 1

    def schema_version(self) -> int:
        return self.db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]

    # --- Editorial contributions (provenance, revisions, states); see contributions.py ---

    def save_contribution(self, c: dict) -> bool:
        """Insert a received revision. False if the same content was already recorded."""
        result = self.db.execute(
            "INSERT INTO contributions (id, provider, source_key, edition_date, content_hash, generated_at, "
            "received_at, state, data) VALUES (%s, %s, %s, %s::date, %s, %s::timestamptz, %s::timestamptz, %s, %s) "
            "ON CONFLICT (source_key, content_hash) DO NOTHING",
            (c["id"], c["provider"], c["source_key"], c["edition_date"], c["content_hash"],
             c.get("generated_at"), c["received_at"], c["state"], Jsonb(c)),
        )
        return result.rowcount == 1

    def update_contribution(self, c: dict) -> None:
        self.db.execute("UPDATE contributions SET state = %s, data = %s WHERE id = %s",
                        (c["state"], Jsonb(c), c["id"]))

    def get_contribution(self, contribution_id: str) -> dict | None:
        row = self.db.execute("SELECT data FROM contributions WHERE id = %s", (contribution_id,)).fetchone()
        return row[0] if row else None

    def list_contributions(self, source_key: str | None = None, edition_date: str | None = None,
                           provider: str | None = None) -> list[dict]:
        rows = self.db.execute(
            "SELECT data FROM contributions WHERE (%s::text IS NULL OR source_key = %s::text) "
            "AND (%s::date IS NULL OR edition_date = %s::date) AND (%s::text IS NULL OR provider = %s::text) "
            "ORDER BY edition_date, generated_at NULLS FIRST, received_at",
            (source_key, source_key, edition_date, edition_date, provider, provider),
        ).fetchall()
        return [row[0] for row in rows]

    # --- Stories written by collector agents, plus the archive index over them ---

    def save_story(self, story: Story) -> None:
        """Insert or replace a story together with its search vector."""
        self.db.execute(
            "INSERT INTO stories (id, topic_slug, language, agent, edition, created_at, data, search) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, "
            "setweight(to_tsvector('simple', %s::text), 'A') || "
            "setweight(to_tsvector('simple', %s::text), 'B')) "
            "ON CONFLICT (id) DO UPDATE SET topic_slug = EXCLUDED.topic_slug, "
            "language = EXCLUDED.language, agent = EXCLUDED.agent, edition = EXCLUDED.edition, "
            "created_at = EXCLUDED.created_at, data = EXCLUDED.data, search = EXCLUDED.search",
            (
                story.id,
                story.topic_slug,
                story.language,
                story.agent,
                story.edition,
                story.created_at,
                Jsonb(to_jsonable(story)),
                fold(f"{story.topic} {story.headline}"),
                fold(" ".join(s.text for s in story.sentences)),
            ),
        )

    def daily_editions(self) -> dict[str, dict]:
        """Stored daily editions by date (YYYY-MM-DD)."""
        rows = self.db.execute("SELECT id, data FROM editions WHERE id LIKE 'daily|%%'").fetchall()
        return {row[0].split("|", 1)[1]: row[1] for row in rows}

    def get_story(self, story_id: str) -> Story | None:
        row = self.db.execute("SELECT data FROM stories WHERE id = %s", (story_id,)).fetchone()
        return story_from_dict(row[0]) if row else None

    def has_story(self, story_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM stories WHERE id = %s", (story_id,)).fetchone() is not None

    def all_stories(self) -> list[Story]:
        rows = self.db.execute("SELECT data FROM stories ORDER BY created_at").fetchall()
        return [story_from_dict(row[0]) for row in rows]

    def stories_for_topic(self, topic_slug: str, language: str | None = None, limit: int = 5) -> list[Story]:
        rows = self.db.execute(
            "SELECT data FROM stories WHERE topic_slug = %s "
            "AND (%s::text IS NULL OR language = %s::text) ORDER BY created_at DESC LIMIT %s",
            (topic_slug, language, language, limit),
        ).fetchall()
        return [story_from_dict(row[0]) for row in rows]

    def search_stories(self, query: str, language: str | None = None, limit: int = 5) -> list[Story]:
        """Keyword search over the archive, best match first. Any query word may match."""
        # Only word characters reach the tsquery, so query syntax cannot be injected.
        words = [w for w in WORD_RE.findall(fold(query)) if len(w) >= 3]
        if not words:
            return []
        tsquery = " | ".join(words)
        rows = self.db.execute(
            "SELECT data FROM stories WHERE search @@ to_tsquery('simple', %s::text) "
            "AND (%s::text IS NULL OR language = %s::text) "
            "ORDER BY ts_rank(search, to_tsquery('simple', %s::text)) DESC, created_at DESC LIMIT %s",
            (tsquery, language, language, tsquery, limit),
        ).fetchall()
        return [story_from_dict(row[0]) for row in rows]
