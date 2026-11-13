"""The PostgreSQL backend must behave like the SQLite one.

Skipped unless TEST_DATABASE_URL points at a disposable database, e.g.
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
All tables are emptied before every test.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from prismunfold.archive import prior_coverage, related_stories
from prismunfold.cli import main
from prismunfold.models import Article
from prismunfold.reports import parse_report
from prismunfold.storage import Store, open_store

from test_reports import NOW, REPORT, report

URL = os.environ.get("TEST_DATABASE_URL")


class OpenStoreTest(unittest.TestCase):
    def test_path_opens_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = open_store(f"{tmp}/db.sqlite3")
            self.assertIsInstance(store, Store)
            store.close()


@unittest.skipUnless(URL, "TEST_DATABASE_URL is not set")
class PostgresStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = open_store(URL)
        self.store.db.execute("TRUNCATE articles, editions, stories")
        self.store.commit()
        self.first, _ = parse_report(REPORT)
        self.second, _ = parse_report(
            report(
                agent="codex",
                topic="Alpine tourism",
                headline="Ski season opens early in Zürich region",
                sentences=[{"text": "Lifts opened after heavy snowfall and a solar outage.",
                            "source_urls": ["https://news.example.org/ski"]}],
            )
        )
        self.store.save_story(self.first)
        self.store.save_story(self.second)
        self.store.commit()

    def tearDown(self):
        self.store.close()

    def test_story_round_trip(self):
        stories = {s.id: s for s in self.store.all_stories()}
        self.assertEqual(stories[self.first.id], self.first)
        self.assertTrue(self.store.has_story(self.first.id))
        self.assertFalse(self.store.has_story("missing"))

    def test_saving_again_replaces_instead_of_duplicating(self):
        self.store.save_story(self.first)
        self.store.commit()
        self.assertEqual(len(self.store.all_stories()), 2)
        self.assertEqual(len(self.store.search_stories("subsidy", "en")), 1)

    def test_topic_lookup_and_language_filter(self):
        self.assertEqual(related_stories(self.store, "Swiss energy policy", "en")[0].id, self.first.id)
        self.assertEqual(related_stories(self.store, "Swiss energy policy", "de"), [])

    def test_keyword_search_matches_any_word_and_ignores_diacritics(self):
        found = {s.id for s in self.store.search_stories("solar power", "en")}
        self.assertEqual(found, {self.first.id, self.second.id})
        self.assertEqual([s.id for s in self.store.search_stories("zurich")], [self.second.id])
        self.assertEqual(self.store.search_stories("quantum computing"), [])

    def test_headline_match_ranks_above_body_match(self):
        self.assertEqual(self.store.search_stories("solar", "en")[0].id, self.first.id)

    def test_query_syntax_cannot_break_the_search(self):
        self.assertEqual(self.store.search_stories("\"; DROP TABLE stories; -- & | ! :* (", "en"), [])
        self.assertEqual(len(self.store.all_stories()), 2)

    def test_prior_coverage_reads_from_postgres(self):
        self.assertIn("Parliament debates solar subsidies", prior_coverage(self.store, "Swiss energy policy", "en"))

    def test_articles_and_editions(self):
        now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
        article = Article(
            id="a1", source_id="s", url="https://example.org/a1", canonical_url="https://example.org/a1",
            title="Titel", published_at=now, language="de", topics=("politik",),
        )
        self.store.save_article(article)
        self.store.save_article(article)  # same id and URL: ignored, not an error
        self.store.save_edition("de|x", "de", now, {"edition": "x"})
        self.store.save_edition("de|x", "de", now, {"edition": "y"})
        self.store.commit()
        self.assertEqual(self.store.articles_since(now - timedelta(hours=1)), [article])
        self.assertEqual(self.store.articles_since(now + timedelta(hours=1)), [])

    def test_cli_uses_database_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out" / "2026-11-12T18" / "goose" / "t.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(report(agent="goose", headline="Third voice")), encoding="utf-8")
            os.environ["DATABASE_URL"] = URL
            try:
                code = main(["reports", "--config", "", "--site", f"{tmp}/site",
                             "--reports-dir", f"{tmp}/out", "--now", NOW])
            finally:
                del os.environ["DATABASE_URL"]
            self.assertEqual(code, 0)
            self.assertEqual(len(self.store.all_stories()), 3)
            api = Path(tmp) / "site/api/v1"
            editions = json.loads((api / "editions.json").read_text(encoding="utf-8"))
            self.assertEqual([e["date"] for e in editions], ["2026-11-12"])
            self.assertEqual(len(editions[0]["placements"]), 3)
            self.assertEqual(self.store.daily_editions()["2026-11-12"]["date"], "2026-11-12")
            story = self.store.get_story(self.first.id)
            self.assertEqual(story, self.first)
            self.assertIsNone(self.store.get_story("missing"))

if __name__ == "__main__":
    unittest.main()
