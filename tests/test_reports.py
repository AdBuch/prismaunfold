"""Tests for collector reports, the archive and the JSON export. Standard library only."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from prismunfold.archive import prior_coverage, related_stories
from prismunfold.cli import main
from prismunfold.export import export_stories
from prismunfold.edition import agent_edition
from prismunfold.linkcheck import check_story, http_probe, is_public_host
from prismunfold.plan import load_topics
from prismunfold.reports import ReportError, load_reports, parse_report
from prismunfold.storage import Store

REPORT = {
    "schema_version": 1,
    "agent": "claude",
    "model": "demo-model",
    "topic": "Swiss energy policy",
    "language": "en",
    "edition": "2026-11-12T18",
    "created_at": "2026-11-12T18:20:00Z",
    "headline": "Parliament debates <b>solar</b> subsidies",
    "sentences": [
        {
            "text": "The National Council debated a solar subsidy bill.",
            "source_urls": ["https://news.example.org/solar?utm_source=x#top"],
        },
        {"text": "A vote is expected next week.", "source_urls": ["https://other.example.com/vote"]},
        {"text": "Experts are thrilled.", "source_urls": []},
        {"text": "Prices will surely fall.", "source_urls": ["javascript:alert(1)", "not a url"]},
    ],
    "sources": [
        {"url": "https://news.example.org/solar", "title": "Solar bill", "publisher": "Example News",
         "published_at": "2026-11-12T10:00:00Z"},
        {"url": "https://other.example.com/vote", "title": "Vote planned", "publisher": "Other Daily"},
        {"url": "ftp://bad.example.org/x", "title": "x", "publisher": "x"},
    ],
    "uncertainties": [],
}


def report(**changes):
    return {**copy.deepcopy(REPORT), **changes}


class ParseReportTest(unittest.TestCase):
    def test_unsourced_sentences_are_dropped(self):
        story, problems = parse_report(REPORT)
        self.assertEqual(len(story.sentences), 2)
        self.assertEqual(sum("no usable source URL" in p for p in problems), 2)

    def test_urls_are_canonical_and_markup_is_removed(self):
        story, _ = parse_report(REPORT)
        self.assertEqual(story.sentences[0].source_urls, ("https://news.example.org/solar",))
        self.assertEqual(story.headline, "Parliament debates solar subsidies")
        self.assertEqual({s.publisher for s in story.sources}, {"Example News", "Other Daily"})

    def test_report_without_any_sourced_sentence_is_rejected(self):
        with self.assertRaises(ReportError):
            parse_report(report(sentences=[{"text": "Trust me.", "source_urls": []}]))

    def test_nothing_new_report_is_accepted_empty(self):
        story, _ = parse_report(report(sentences=[], nothing_new=True))
        self.assertTrue(story.nothing_new)

    def test_wrong_agent_schema_and_edition_are_rejected(self):
        for bad in (
            report(agent="mallory"),
            report(schema_version=2),
            report(edition="../../etc"),
            report(created_at="yesterday"),
            "not an object",
        ):
            with self.assertRaises(ReportError):
                parse_report(bad)
        with self.assertRaises(ReportError):
            parse_report(REPORT, expected_agent="codex")
        with self.assertRaises(ReportError):
            parse_report(REPORT, expected_edition="2026-11-13T00")

    def test_cited_url_missing_from_source_list_is_kept_and_flagged(self):
        story, problems = parse_report(report(sources=[]))
        self.assertEqual(len(story.sources), 2)
        self.assertTrue(any("not in the source list" in p for p in problems))

    def test_single_publisher_is_named_as_uncertainty(self):
        one = report(sentences=REPORT["sentences"][:1])
        story, _ = parse_report(one)
        self.assertTrue(any("single publisher" in u for u in story.uncertainties))


class LinkCheckTest(unittest.TestCase):
    def test_dead_sources_are_removed_and_their_sentences_dropped(self):
        story, _ = parse_report(REPORT)
        checked, problems = check_story(story, probe=lambda url: "news.example.org" in url)
        self.assertEqual([s.text for s in checked.sentences], [story.sentences[0].text])
        self.assertEqual([s.url for s in checked.sources], ["https://news.example.org/solar"])
        self.assertTrue(any("no reachable source" in p for p in problems))

    def test_story_with_only_dead_sources_is_rejected(self):
        story, _ = parse_report(REPORT)
        checked, problems = check_story(story, probe=lambda url: False)
        self.assertIsNone(checked)
        self.assertTrue(problems[-1].startswith("rejected"))

    def test_private_and_loopback_targets_are_never_contacted(self):
        for host in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "::1", "no-such-host.invalid"):
            self.assertFalse(is_public_host(host), host)
        self.assertFalse(http_probe("http://127.0.0.1:8080/admin"))
        self.assertFalse(http_probe("file:///etc/passwd"))


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(f"{self.tmp.name}/db.sqlite3")
        self.first, _ = parse_report(REPORT)
        self.store.save_story(self.first)
        other = report(
            agent="codex",
            topic="Alpine tourism",
            headline="Ski season opens early",
            sentences=[{"text": "Lifts opened after heavy snowfall and a solar outage.",
                        "source_urls": ["https://news.example.org/ski"]}],
        )
        self.second, _ = parse_report(other)
        self.store.save_story(self.second)
        self.store.commit()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_same_topic_is_found(self):
        found = related_stories(self.store, "Swiss energy policy", "en")
        self.assertEqual(found[0].id, self.first.id)

    def test_keyword_search_finds_related_story_under_another_topic(self):
        found = related_stories(self.store, "solar power", "en")
        self.assertEqual({s.id for s in found}, {self.first.id, self.second.id})

    def test_language_filter_and_empty_result(self):
        self.assertEqual(related_stories(self.store, "Swiss energy policy", "de"), [])
        self.assertEqual(prior_coverage(self.store, "quantum computing", "en"), "")

    def test_saving_again_does_not_duplicate_index_rows(self):
        self.store.save_story(self.first)
        self.assertEqual(len(self.store.search_stories("subsidy", "en")), 1)

    def test_prior_coverage_lists_sentences_with_sources(self):
        text = prior_coverage(self.store, "Swiss energy policy", "en")
        self.assertIn("Parliament debates solar subsidies", text)
        self.assertIn("https://news.example.org/solar", text)
        self.assertIn("Never cite PrismUnfold itself", text)

    def test_query_syntax_cannot_break_the_search(self):
        self.assertEqual(self.store.search_stories('"; DROP TABLE stories; -- NEAR(', "en"), [])
        self.assertEqual(len(self.store.all_stories()), 2)


class ExportAndCliTest(unittest.TestCase):
    def write_reports(self, root: Path) -> None:
        files = {
            "claude": REPORT,
            "codex": report(agent="codex", headline="Solar bill reaches parliament"),
            "goose": report(agent="goose", sentences=[]),  # rejected: nothing sourced
        }
        for agent, payload in files.items():
            path = root / "2026-11-12T18" / agent / "swiss-energy-policy.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
        (root / "2026-11-12T18" / "vibe").mkdir()
        (root / "2026-11-12T18" / "vibe" / "broken.json").write_text("{not json", encoding="utf-8")

    def test_load_reports_marks_rejected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_reports(Path(tmp))
            results = load_reports(tmp, "2026-11-12T18")
            self.assertEqual(sum(story is not None for _, story, _ in results), 2)
            self.assertEqual(sum(story is None for _, story, _ in results), 2)

    def test_cli_reports_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_reports(Path(tmp) / "out")
            args = ["--config", "", "--db", f"{tmp}/db.sqlite3", "--site", f"{tmp}/site"]
            code = main(["reports", *args, "--reports-dir", f"{tmp}/out"])
            self.assertEqual(code, 1)  # two rejected reports must be visible to the scheduler

            api = Path(tmp) / "site" / "api" / "v1"
            index = json.loads((api / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["editions"][0]["storyCount"], 2)
            edition = json.loads((api / "editions" / "2026-11-12T18.json").read_text(encoding="utf-8"))
            stories = edition["topics"][0]["stories"]
            self.assertEqual({s["agent"] for s in stories}, {"claude", "codex"})

            story = json.loads((api / "stories" / f"{stories[0]['slug']}.json").read_text(encoding="utf-8"))
            self.assertEqual(story["relatedSlugs"], [stories[1]["slug"]])
            self.assertIn(story["confidence"], ("reported", "disputed"))
            self.assertIn("AI agent", story["aiDisclosure"])
            source_ids = {s["id"] for s in story["sources"]}
            for sentence in story["sentences"]:
                self.assertTrue(sentence["sourceIds"])
                self.assertTrue(set(sentence["sourceIds"]) <= source_ids)

            out = Path(tmp) / "prior.md"
            self.assertEqual(main(["context", *args, "--topic", "Swiss energy policy", "--out", str(out)]), 0)
            self.assertIn("Solar bill reaches parliament", out.read_text(encoding="utf-8"))

    def test_second_run_skips_known_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_reports(Path(tmp) / "out")
            args = ["reports", "--config", "", "--db", f"{tmp}/db.sqlite3", "--site", f"{tmp}/site",
                    "--reports-dir", f"{tmp}/out"]
            main(args)
            store = Store(f"{tmp}/db.sqlite3")
            self.assertEqual(len(store.all_stories()), 2)
            store.close()
            self.assertEqual(main(args), 1)  # rejected reports stay visible on every run

    def test_plan_writes_jobs_and_context_for_the_collectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_reports(Path(tmp) / "out")
            base = ["--config", "", "--db", f"{tmp}/db.sqlite3", "--site", f"{tmp}/site"]
            main(["reports", *base, "--reports-dir", f"{tmp}/out"])
            topics = Path(tmp) / "topics.txt"
            topics.write_text("# comment\n\nen|Swiss  energy policy\nde|Energiepolitik in Zürich\n"
                              "en|Swiss energy policy\n", encoding="utf-8")
            code = main(["plan", *base, "--topics", str(topics), "--shared-dir", f"{tmp}/shared",
                         "--now", "2026-11-13T07:59:00+01:00"])
            self.assertEqual(code, 0)
            lines = (Path(tmp) / "shared/jobs/current.tsv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "#edition 2026-11-13T06")
            self.assertEqual(lines[1:], [
                "en-swiss-energy-policy\ten\tSwiss energy policy",
                "de-energiepolitik-in-zurich\tde\tEnergiepolitik in Zürich",
            ])
            context = Path(tmp) / "shared/context/2026-11-13T06"
            self.assertIn("Solar bill", (context / "en-swiss-energy-policy.md").read_text(encoding="utf-8"))
            self.assertEqual((context / "de-energiepolitik-in-zurich.md").read_text(encoding="utf-8"), "")
            self.assertEqual(list(Path(tmp).rglob("*.tmp")), [])

    def test_plan_without_topics_file_is_not_an_error(self):
        self.assertEqual(main(["plan", "--config", "", "--topics", "/nonexistent/topics.txt"]), 0)

    def test_bad_topic_line_is_reported_with_its_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topics.txt"
            path.write_text("en|ok\njust a topic\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "topics.txt:2"):
                load_topics(path)

    def test_agent_edition_is_a_six_hour_utc_block(self):
        self.assertEqual(agent_edition(datetime(2026, 11, 12, 23, 59, tzinfo=timezone.utc)), "2026-11-12T18")
        self.assertEqual(agent_edition(datetime.fromisoformat("2026-11-13T00:30:00+01:00")), "2026-11-12T18")
        self.assertEqual(agent_edition(datetime(2026, 11, 13, 0, 0, tzinfo=timezone.utc)), "2026-11-13T00")

    def test_export_skips_nothing_new_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(f"{tmp}/db.sqlite3")
            story, _ = parse_report(report(sentences=[], nothing_new=True))
            store.save_story(story)
            export_stories(store, f"{tmp}/site")
            store.close()
            index = json.loads((Path(tmp) / "site/api/v1/index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["editions"], [])


if __name__ == "__main__":
    unittest.main()
