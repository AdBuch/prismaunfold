"""MVP tests, standard library only.

Run from the repository root:
    PYTHONPATH=src python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from prismunfold.cluster import cluster_articles
from prismunfold.edition import edition_window
from prismunfold.ingest import parse_feed
from prismunfold.models import Article, Event, Sentence, Summary
from prismunfold.normalize import canonical_url
from prismunfold.pipeline import DEFAULTS, load_catalog, run
from prismunfold.quality import rejection_reason
from prismunfold.storage import Store
from prismunfold.summarize import validate_summary

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime.fromisoformat("2026-11-06T06:30:00+01:00")
UTC = timezone.utc


def fetch_fixture(source):
    return (FIXTURES / f"{source.id}.xml").read_bytes()


def make_article(aid, title, published, language="de", source_id="s", **extra):
    return Article(
        id=aid,
        source_id=source_id,
        url=f"https://example.org/{aid}",
        canonical_url=f"https://example.org/{aid}",
        title=title,
        published_at=published,
        language=language,
        **extra,
    )


def utc(*args):
    return datetime(*args, tzinfo=UTC)


class CanonicalUrlTest(unittest.TestCase):
    def test_strips_tracking_and_fragment(self):
        self.assertEqual(
            canonical_url("https://Example.org/News/?utm_source=x&id=5#frag"),
            "https://example.org/News?id=5",
        )


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.catalog = {s.id: s for s in load_catalog(FIXTURES / "catalog.json")}

    def test_rss_parses_all_items_and_flags_ai(self):
        articles = parse_feed(fetch_fixture(self.catalog["demo-rss"]), self.catalog["demo-rss"])
        self.assertEqual(len(articles), 4)
        ai = [a for a in articles if a.ai_disclosed]
        self.assertEqual([a.title for a in ai], ["Automatisch erzeugter Kurzbericht zur Börse"])

    def test_excerpt_only_source_keeps_no_body(self):
        src = self.catalog["demo-rss"]
        articles = parse_feed(fetch_fixture(src), src)
        self.assertTrue(all(a.body_text is None for a in articles))

    def test_full_text_source_keeps_body(self):
        src = self.catalog["demo-atom"]
        articles = parse_feed(fetch_fixture(src), src)
        followup = next(a for a in articles if a.title.startswith("Neues Klimapaket"))
        self.assertIn("Engpässen", followup.body_text)

    def test_image_requires_source_provenance(self):
        src = self.catalog["demo-rss"]
        with_image = next(
            a for a in parse_feed(fetch_fixture(src), src) if a.image_url is not None
        )
        self.assertEqual(with_image.image_source_url, with_image.url)
        self.assertEqual(with_image.image_credit, "Demo-Fotografin")

    def test_doctype_is_refused(self):
        src = self.catalog["demo-rss"]
        with self.assertRaises(ValueError):
            parse_feed(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><rss/>', src)


class QualityTest(unittest.TestCase):
    def setUp(self):
        self.src = load_catalog(FIXTURES / "catalog.json")[0]
        self.max_age = timedelta(hours=36)

    def check(self, article, seen_urls=frozenset(), seen_titles=frozenset()):
        return rejection_reason(article, self.src, NOW.astimezone(UTC), self.max_age, set(seen_urls), set(seen_titles))

    def test_ai_disclosed_is_dropped_when_excluded(self):
        art = make_article("x", "Titel", utc(2026, 11, 6, 5), ai_disclosed=True)
        self.assertIn("ai-disclosed", self.check(art))

    def test_stale_and_future_are_dropped(self):
        self.assertIn("older", self.check(make_article("x", "Titel", utc(2026, 11, 2, 9))))
        self.assertIn("future", self.check(make_article("y", "Titel", utc(2026, 11, 7, 9))))

    def test_duplicates_are_dropped(self):
        art = make_article("x", "Titel", utc(2026, 11, 6, 5))
        self.assertIn("duplicate title", self.check(art, seen_titles={"titel"}))


class ClusterTest(unittest.TestCase):
    def test_groups_related_titles_within_language(self):
        a = make_article("a", "Bundesrat beschliesst neues Klimapaket", utc(2026, 11, 6, 4, 10))
        b = make_article("b", "Neues Klimapaket: Kantone kritisieren Umsetzungsfristen", utc(2026, 11, 6, 4, 40))
        c = make_article("c", "Zürcher Kantonsrat debattiert Velowege", utc(2026, 11, 6, 5, 20))
        groups = cluster_articles([a, b, c], 0.2, timedelta(hours=36))
        self.assertEqual(sorted(len(g) for g in groups), [1, 2])


class SummaryTest(unittest.TestCase):
    def test_sentences_without_valid_citation_are_dropped(self):
        event = Event(
            id="e", language="de", title="t", article_ids=("a",), source_ids=("s",),
            topics=(), first_published=utc(2026, 11, 6), last_published=utc(2026, 11, 6),
        )
        summary = Summary(
            event_id="e", language="de", generator="test", prompt_version="t",
            sentences=(
                Sentence("ok", ("a",)),
                Sentence("bad", ("zzz",)),
                Sentence("uncited", ()),
            ),
        )
        cleaned, dropped = validate_summary(summary, event)
        self.assertEqual([s.text for s in cleaned.sentences], ["ok"])
        self.assertEqual(dropped, 2)


class EditionWindowTest(unittest.TestCase):
    def test_zurich_standard_time(self):
        start, end = edition_window(utc(2026, 11, 6, 5, 30), "Europe/Zurich")
        self.assertEqual(start, utc(2026, 11, 6, 5, 0))
        self.assertEqual(end, utc(2026, 11, 6, 11, 0))

    def test_zurich_across_dst_switch(self):
        # 2026-03-29: clocks go forward; 06:00 local is then 04:00 UTC.
        start, end = edition_window(utc(2026, 3, 29, 5, 0), "Europe/Zurich")
        self.assertEqual(start, utc(2026, 3, 29, 4, 0))
        self.assertEqual(end, utc(2026, 3, 29, 10, 0))

    def test_odd_offset_zone(self):
        # Asia/Kathmandu is UTC+05:45. 2026-11-06 19:00 UTC is 00:45 on 2026-11-07 local time.
        start, end = edition_window(utc(2026, 11, 6, 19, 0), "Asia/Kathmandu")
        self.assertEqual(start, utc(2026, 11, 6, 18, 15))
        self.assertEqual(end, utc(2026, 11, 7, 0, 15))
        self.assertEqual(start.astimezone(ZoneInfo("Asia/Kathmandu")).hour, 0)


class PipelineTest(unittest.TestCase):
    def test_end_to_end_from_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {**DEFAULTS, "db_path": f"{tmp}/db.sqlite3", "site_dir": f"{tmp}/site"}
            store = Store(cfg["db_path"])
            report = run(cfg, load_catalog(FIXTURES / "catalog.json"), NOW, fetch_fixture, store, cfg["site_dir"])
            store.close()

            self.assertEqual(report.errors, [])
            self.assertEqual(report.kept, 3)
            self.assertEqual(report.events, 2)
            reasons = [reason for _, reason in report.dropped]
            self.assertTrue(any("ai-disclosed" in r for r in reasons))
            self.assertTrue(any("older" in r for r in reasons))
            self.assertTrue(any("duplicate title" in r for r in reasons))

            site = Path(tmp) / "site"
            data = json.loads((site / "api/v1/briefings/de/latest.json").read_text(encoding="utf-8"))
            titles = [item["event"]["title"] for item in data["events"]]
            self.assertIn("Zürcher Kantonsrat debattiert Velowege", titles)
            self.assertTrue(any(item["event"]["single_source"] for item in data["events"]))
            self.assertTrue(all(item["summary"]["translations_pending"] for item in data["events"]))
            self.assertEqual(list(site.rglob("*.html")), [])  # the pipeline renders no HTML

    def test_blocked_source_is_not_fetched(self):
        calls = []

        def spy(source):
            calls.append(source.id)
            return fetch_fixture(source)

        with tempfile.TemporaryDirectory() as tmp:
            cfg = {**DEFAULTS, "db_path": f"{tmp}/db.sqlite3", "site_dir": f"{tmp}/site"}
            store = Store(cfg["db_path"])
            run(cfg, load_catalog(FIXTURES / "catalog.json"), NOW, spy, store, cfg["site_dir"])
            store.close()
        self.assertNotIn("demo-blocked", calls)


if __name__ == "__main__":
    unittest.main()
