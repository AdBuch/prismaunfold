"""SQLite persistence (stdlib only). Records are stored as JSON documents next to indexed columns."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Article, article_from_dict, to_jsonable

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
"""


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


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
