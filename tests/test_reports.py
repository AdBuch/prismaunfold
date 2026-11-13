"""Contract tests for collector reports: what is accepted, what is rejected, and that
hostile input cannot hurt the pipeline. Standard library only."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from prismunfold.archive import prior_coverage, related_stories
from prismunfold.cli import main
from prismunfold.edition import agent_edition
from prismunfold.linkcheck import check_story, http_probe, is_public_host
from prismunfold.plan import load_topics
from prismunfold.reports import (
    MAX_REPORT_BYTES,
    MAX_SENTENCES,
    ReportError,
    load_reports,
    parse_report,
    public_url,
)
from prismunfold.storage import Store, open_store

NOW = "2026-11-12T19:00:00+00:00"
NOW_DT = datetime.fromisoformat(NOW)

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
            report(agent="desk"),  # the pipeline's own desk can never arrive as a report
            report(schema_version=2),
            report(schema_version=True),
            report(edition="../../etc"),
            report(created_at="yesterday"),
            report(language="en; DROP"),
            "not an object",
            ["a", "list"],
            None,
        ):
            with self.assertRaises(ReportError, msg=repr(bad)[:60]):
                parse_report(bad)
        with self.assertRaises(ReportError):
            parse_report(REPORT, expected_agent="codex")
        with self.assertRaises(ReportError):
            parse_report(REPORT, expected_edition="2026-11-13T00")

    def test_cited_url_missing_from_source_list_is_kept_and_flagged(self):
        story, problems = parse_report(report(sources=[]))
        self.assertEqual(len(story.sources), 2)
        self.assertTrue(any("not in the source list" in p for p in problems))

    def test_disputes_and_uncertainties_are_kept_apart(self):
        story, _ = parse_report(report(uncertainties=["Turnout is not known."],
                                       disputes=["Outlets give different vote counts."]))
        self.assertEqual(story.uncertainties, ("Turnout is not known.",))
        self.assertEqual(story.disputes, ("Outlets give different vote counts.",))


class AdversarialReportTest(unittest.TestCase):
    """Every field with the wrong type. Nothing may raise anything but ReportError."""

    WRONG = (None, 0, 1.5, True, "text", [], ["x"], {}, {"a": 1}, [[]], [None], [{"text": 1}])

    def test_wrong_types_never_crash(self):
        for field in REPORT:
            for value in self.WRONG:
                try:
                    story, _ = parse_report(report(**{field: value}))
                except ReportError:
                    continue
                self.assertTrue(story.sentences or story.nothing_new, f"{field}={value!r}")
                for sentence in story.sentences:
                    self.assertTrue(sentence.text)
                    self.assertTrue(sentence.source_urls)

    def test_wrong_types_inside_sentences_and_sources_never_crash(self):
        for value in self.WRONG:
            sentences = [{"text": value, "source_urls": ["https://a.example.org/1"]},
                         {"text": "Kept.", "source_urls": value},
                         value,
                         {"text": "Good.", "source_urls": ["https://a.example.org/1", value]}]
            sources = [value, {"url": value, "title": value, "publisher": value,
                               "published_at": value, "language": value}]
            story, _ = parse_report(report(sentences=sentences, sources=sources, uncertainties=[value]))
            # A plain string is a legitimate sentence text; every other type is dropped.
            expected = (["text"] if value == "text" else []) + ["Good."]
            self.assertEqual([s.text for s in story.sentences], expected, repr(value))

    def test_unsafe_urls_are_never_accepted(self):
        for url in (
            "javascript:alert(1)", "file:///etc/passwd", "data:text/html,x", "ftp://example.org/x",
            "http://localhost/admin", "http://127.0.0.1/", "http://[::1]/", "http://169.254.169.254/latest",
            "http://10.0.0.8/x", "https://user:secret@example.org/", "https://example.org:99999/x",
            "https://exa mple.org/", "https://example.org/\npath", "https://intranet/", "https://example./",
            "//example.org/x", "", " ", "https://" + "a" * 3000 + ".org/",
        ):
            self.assertIsNone(public_url(url), url)
        self.assertEqual(public_url("HTTPS://Example.org/a?utm_source=x"), "https://example.org/a")

    def test_oversized_report_is_cut_down_not_trusted(self):
        many = [{"text": f"Sentence {i} " + "x" * 5000, "source_urls": ["https://a.example.org/1"] * 50}
                for i in range(500)]
        story, problems = parse_report(report(sentences=many, sources=[{"url": f"https://s{i}.example.org/"}
                                                                       for i in range(500)]))
        self.assertEqual(len(story.sentences), MAX_SENTENCES)
        self.assertTrue(all(len(s.text) <= 600 for s in story.sentences))
        self.assertTrue(any("kept the first" in p for p in problems))

    def test_control_characters_and_markup_are_removed_from_text(self):
        story, _ = parse_report(report(headline="Break\x00ing\x1b[31m <script>alert(1)</script>‮news"))
        self.assertNotIn("\x00", story.headline)
        self.assertNotIn("\x1b", story.headline)
        self.assertNotIn("‮", story.headline)
        self.assertNotIn("<", story.headline)

    def test_timestamps_are_checked_against_now(self):
        parse_report(REPORT, now=NOW_DT)
        for created in ("2026-11-12T20:00:00Z", "2031-01-01T00:00:00Z", "2026-11-01T00:00:00Z"):
            with self.assertRaises(ReportError, msg=created):
                parse_report(report(created_at=created), now=NOW_DT)
        future_source = report(sources=[{"url": "https://news.example.org/solar", "published_at": "2030-01-01"},
                                        {"url": "https://other.example.com/vote", "published_at": "soon"}])
        story, _ = parse_report(future_source, now=NOW_DT)
        self.assertEqual([s.published_at for s in story.sources], [None, None])

    def test_slug_and_ids_are_safe_file_names(self):
        story, _ = parse_report(report(headline="../../../etc/passwd \\ ..", topic="a/b\\c:d*e?"))
        for value in (story.slug, story.topic_slug, story.id):
            self.assertRegex(value, r"^[\w-]+$")


class LoadReportsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "2026-11-12T18" / "claude"
        self.dir.mkdir(parents=True)
        (self.dir / "good.json").write_text(json.dumps(REPORT), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def outcome(self) -> dict[str, str]:
        return {p.name: ("ok" if s else problems[-1])
                for p, s, problems in load_reports(self.tmp.name, "2026-11-12T18", NOW_DT)}

    def test_one_bad_file_does_not_stop_the_others(self):
        (self.dir / "broken.json").write_text("{not json", encoding="utf-8")
        (self.dir / "binary.json").write_bytes(b"\xff\xfe\x00\x01")
        (self.dir / "empty.json").write_text("", encoding="utf-8")
        (self.dir / "nan.json").write_text('{"schema_version": NaN}', encoding="utf-8")
        (self.dir / "deep.json").write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
        (self.dir / "huge.json").write_text(" " * (MAX_REPORT_BYTES + 1) + "{}", encoding="utf-8")
        result = self.outcome()
        self.assertEqual(result["good.json"], "ok")
        self.assertEqual(sum(v == "ok" for v in result.values()), 1)
        self.assertEqual(len(result), 7)
        self.assertIn("larger than", result["huge.json"])
        self.assertIn("nested too deeply", result["deep.json"])

    def test_symlinks_and_odd_file_names_are_refused(self):
        secret = Path(self.tmp.name) / "secret.json"
        secret.write_text(json.dumps(REPORT), encoding="utf-8")
        os.symlink(secret, self.dir / "link.json")
        (self.dir / "odd name;rm.json").write_text(json.dumps(REPORT), encoding="utf-8")
        result = self.outcome()
        self.assertIn("not a regular file", result["link.json"])
        self.assertIn("plain identifier", result["odd name;rm.json"])

    def test_agent_and_edition_must_match_the_directory(self):
        other = Path(self.tmp.name) / "2026-11-12T18" / "codex"
        other.mkdir()
        (other / "spoof.json").write_text(json.dumps(REPORT), encoding="utf-8")  # says "claude"
        result = self.outcome()
        self.assertIn("was written by 'codex'", result["spoof.json"])

    def test_edition_argument_cannot_leave_the_reports_directory(self):
        self.assertEqual(load_reports(self.tmp.name, "../.."), [])
        self.assertEqual(load_reports(self.tmp.name, "*"), [])


class LinkCheckTest(unittest.TestCase):
    def test_dead_sources_are_removed_and_their_sentences_dropped(self):
        story, _ = parse_report(REPORT)
        check = check_story(story, probe=lambda url: "news.example.org" in url)
        self.assertEqual([s.text for s in check.story.sentences], [story.sentences[0].text])
        self.assertEqual([s.url for s in check.story.sources], ["https://news.example.org/solar"])
        self.assertEqual(check.dropped_sentences, 1)
        self.assertEqual(check.reachable, {"https://news.example.org/solar": True,
                                           "https://other.example.com/vote": False})

    def test_story_with_only_dead_sources_is_rejected(self):
        story, _ = parse_report(REPORT)
        check = check_story(story, probe=lambda url: False)
        self.assertIsNone(check.story)
        self.assertTrue(check.problems[-1].startswith("rejected"))

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

    def test_story_lookup_by_id(self):
        self.assertEqual(self.store.get_story(self.first.id), self.first)
        self.assertIsNone(self.store.get_story("missing"))


class CliTest(unittest.TestCase):
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

    def args(self, tmp: str) -> list[str]:
        return ["--config", "", "--db", f"{tmp}/db.sqlite3", "--site", f"{tmp}/site"]

    def test_reports_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_reports(Path(tmp) / "out")
            code = main(["reports", *self.args(tmp), "--reports-dir", f"{tmp}/out", "--now", NOW])
            self.assertEqual(code, 1)  # two rejected reports must be visible to the scheduler

            api = Path(tmp) / "site" / "api" / "v1"
            index = json.loads((api / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["latest"], "2026-11-12")
            self.assertEqual(index["storyCount"], 2)
            self.assertEqual(index["sections"], [{"id": "swiss-energy-policy", "label": "Swiss energy policy"}])
            editions = json.loads((api / "editions.json").read_text(encoding="utf-8"))
            placements = editions[0]["placements"]
            self.assertEqual([p["slot"] for p in placements], ["lead", "secondary"])

            story = json.loads((api / "stories" / f"{placements[0]['storySlug']}.json").read_text(encoding="utf-8"))
            self.assertEqual(story["relatedSlugs"], [placements[1]["storySlug"]])
            self.assertEqual(story["confidence"], "reported")
            self.assertIn("AI agent", story["aiDisclosure"])
            # Two sentences were dropped for lack of a source, so the story needs review.
            self.assertEqual(story["verification"]["state"], "review_required")
            self.assertFalse(story["verification"]["links_checked"])
            source_ids = {s["id"] for s in story["sources"]}
            for sentence in story["sentences"]:
                self.assertTrue(sentence["sourceIds"])
                self.assertTrue(set(sentence["sourceIds"]) <= source_ids)
                self.assertEqual(sentence["verification"]["support"], "not_checked")

            topic = json.loads((api / "topics" / "swiss-energy-policy.json").read_text(encoding="utf-8"))
            self.assertEqual(len(topic["events"]), 2)
            self.assertEqual(json.loads((api / "magazines.json").read_text(encoding="utf-8")), [])
            self.assertEqual(list(api.rglob("*.tmp")), [])

            out = Path(tmp) / "prior.md"
            self.assertEqual(main(["context", *self.args(tmp), "--topic", "Swiss energy policy", "--out", str(out)]), 0)
            self.assertIn("Solar bill reaches parliament", out.read_text(encoding="utf-8"))

    def test_second_run_skips_known_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_reports(Path(tmp) / "out")
            args = ["reports", *self.args(tmp), "--reports-dir", f"{tmp}/out", "--now", NOW]
            main(args)
            store = open_store(f"{tmp}/db.sqlite3")
            self.assertEqual(len(store.all_stories()), 2)
            store.close()
            self.assertEqual(main(args), 1)  # rejected reports stay visible on every run

    def test_stale_reports_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_reports(Path(tmp) / "out")
            code = main(["reports", *self.args(tmp), "--reports-dir", f"{tmp}/out", "--now", "2026-12-24T00:00:00Z"])
            self.assertEqual(code, 1)
            index = json.loads((Path(tmp) / "site/api/v1/index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["storyCount"], 0)
            self.assertIsNone(index["latest"])

    def test_plan_writes_jobs_and_context_for_the_collectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_reports(Path(tmp) / "out")
            main(["reports", *self.args(tmp), "--reports-dir", f"{tmp}/out", "--now", NOW])
            topics = Path(tmp) / "topics.txt"
            topics.write_text("# comment\n\nen|Swiss  energy policy\nde|Energiepolitik in Zürich\n"
                              "en|Swiss energy policy\n", encoding="utf-8")
            code = main(["plan", *self.args(tmp), "--topics", str(topics), "--shared-dir", f"{tmp}/shared",
                         "--now", "2026-11-13T07:59:00+01:00"])
            self.assertEqual(code, 0)
            lines = (Path(tmp) / "shared/jobs/current.tsv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "#edition 2026-11-13T06")
            self.assertEqual([line.split("\t")[:3] for line in lines[1:]], [
                ["en-swiss-energy-policy", "en", "Swiss energy policy"],
                ["de-energiepolitik-in-zurich", "de", "Energiepolitik in Zürich"],
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


if __name__ == "__main__":
    unittest.main()
