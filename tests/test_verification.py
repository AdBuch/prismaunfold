"""Verification states and the edition composer. Standard library only."""

from __future__ import annotations

import dataclasses
import unittest

from prismunfold.compose import compose_edition, select
from prismunfold.reports import parse_report
from prismunfold.verification import (
    CONTRADICTED,
    DISPUTED,
    NOT_SUPPORTED,
    REVIEW_REQUIRED,
    SUPPORTED,
    UNVERIFIED,
    ExtractiveSupport,
    publisher_key,
    verify_story,
)

from test_reports import report

TWO_PUBLISHERS = [
    {"text": "The council debated the bill.",
     "source_urls": ["https://news.example.org/a", "https://www.other.example.com/b"]},
    {"text": "A vote follows next week.", "source_urls": ["https://other.example.com/c"]},
]


class Fixed:
    """A support checker that answers from a table keyed by URL."""

    name = "fixed"

    def __init__(self, table: dict[str, str], default: str = SUPPORTED) -> None:
        self.table, self.default = table, default

    def check(self, sentence, source) -> str:
        return self.table.get(source.url, self.default)


def story(**changes):
    return parse_report(report(sentences=TWO_PUBLISHERS, sources=[], **changes))[0]


class VerifyStoryTest(unittest.TestCase):
    def test_a_citation_alone_is_never_called_supported(self):
        record = verify_story(story())
        self.assertEqual(record["state"], UNVERIFIED)
        self.assertEqual({c["support"] for c in record["sentences"]}, {"not_checked"})
        self.assertEqual({c["citation"] for c in record["sentences"]}, {"structural"})
        self.assertFalse(record["links_checked"])
        self.assertEqual(record["corroborated_sentences"], 0)

    def test_reachable_links_alone_do_not_make_it_supported(self):
        s = story()
        reachable = {u: True for x in s.sentences for u in x.source_urls}
        record = verify_story(s, reachable)
        self.assertEqual(record["state"], UNVERIFIED)
        self.assertTrue(record["links_checked"])
        self.assertTrue(all(c["sources_reachable"] for c in record["sentences"]))

    def test_supported_needs_a_checker_and_corroboration_needs_two_publishers(self):
        record = verify_story(story(), checker=Fixed({}))
        self.assertEqual(record["state"], SUPPORTED)
        first, second = record["sentences"]
        self.assertTrue(first["corroborated"])  # two independent publishers support it
        self.assertFalse(second["corroborated"])  # one publisher only
        self.assertEqual(record["corroborated_sentences"], 1)
        self.assertEqual(record["independent_publishers"], 2)

    def test_www_prefix_does_not_create_a_second_publisher(self):
        self.assertEqual(publisher_key("https://www.other.example.com/b"), publisher_key("https://other.example.com/c"))

    def test_contradiction_makes_the_story_disputed(self):
        record = verify_story(story(), checker=Fixed({"https://other.example.com/c": CONTRADICTED}))
        self.assertEqual(record["state"], DISPUTED)
        self.assertEqual(record["sentences"][1]["state"], DISPUTED)

    def test_writer_reported_dispute_makes_the_story_disputed(self):
        record = verify_story(story(disputes=["Outlets give different vote counts."]))
        self.assertEqual(record["state"], DISPUTED)

    def test_uncertainty_is_not_a_dispute(self):
        self.assertEqual(verify_story(story(uncertainties=["Turnout is unknown."]))["state"], UNVERIFIED)

    def test_unsupported_sentence_needs_review(self):
        record = verify_story(story(), checker=Fixed({"https://other.example.com/c": NOT_SUPPORTED}))
        self.assertEqual(record["state"], REVIEW_REQUIRED)
        self.assertEqual(record["sentences"][1]["support"], NOT_SUPPORTED)

    def test_thin_or_damaged_stories_need_review(self):
        single = parse_report(report(sentences=TWO_PUBLISHERS[1:], sources=[]))[0]
        self.assertEqual(verify_story(single, checker=Fixed({}))["state"], REVIEW_REQUIRED)
        self.assertEqual(verify_story(story(), dropped_sentences=1)["state"], REVIEW_REQUIRED)
        self.assertEqual(verify_story(story(), dead_sources=1)["state"], REVIEW_REQUIRED)
        unreachable = {u: False for x in story().sentences for u in x.source_urls}
        self.assertEqual(verify_story(story(), unreachable)["state"], REVIEW_REQUIRED)

    def test_checker_must_return_a_known_result(self):
        with self.assertRaises(ValueError):
            verify_story(story(), checker=Fixed({}, default="verified"))

    def test_extractive_desk_stories_are_supported_by_their_own_source(self):
        self.assertEqual(verify_story(story(), checker=ExtractiveSupport())["state"], SUPPORTED)


def make(agent: str, topic: str, urls: list[str], state: str = UNVERIFIED, region: str = "", language: str = "en"):
    s = parse_report(
        report(agent=agent, topic=topic, language=language, headline=f"{topic} by {agent}", sources=[],
               sentences=[{"text": f"Sentence on {topic}.", "source_urls": urls}])
    )[0]
    return dataclasses.replace(s, verification={"state": state}, regions=(region,) if region else ())


class ComposeTest(unittest.TestCase):
    def setUp(self):
        many = [f"https://p{i}.example.org/x" for i in range(4)]
        self.stories = [
            make("claude", "Energy", many, SUPPORTED, "ch"),
            make("codex", "Energy", many[:3], UNVERIFIED, "ch"),
            make("vibe", "Energy", many[:2], UNVERIFIED, "ch"),
            make("goose", "Rural clinics", ["https://local.example.net/clinic"], REVIEW_REQUIRED, "pe", "es"),
            make("claude", "Trade", ["https://p9.example.org/t", "https://p8.example.org/t"], UNVERIFIED, "eu"),
        ]

    def test_best_sourced_supported_story_leads(self):
        picks = select(self.stories, "2026-11-12", 10)
        self.assertEqual(picks[0].story.agent, "claude")
        self.assertEqual(picks[0].story.topic, "Energy")

    def test_one_section_cannot_fill_the_top(self):
        picks = select(self.stories, "2026-11-12", 10)
        self.assertGreater(len({p.story.topic for p in picks[:3]}), 1)

    def test_lone_single_source_voice_is_marked_underreported_and_placed(self):
        picks = select(self.stories, "2026-11-12", 10)
        clinic = next(p for p in picks if p.story.topic == "Rural clinics")
        self.assertTrue(clinic.underreported)
        self.assertLess(picks.index(clinic), 4)  # ahead of the third report on the same subject

    def test_selection_is_deterministic(self):
        first = [p.story.id for p in select(self.stories, "2026-11-12", 10)]
        second = [p.story.id for p in select(list(reversed(self.stories)), "2026-11-12", 10)]
        self.assertEqual(first, second)

    def test_edition_has_one_lead_and_frontend_fields(self):
        edition = compose_edition(self.stories, "2026-11-12", 7)
        slots = [p["slot"] for p in edition["placements"]]
        self.assertEqual(slots, ["lead", "secondary", "secondary", "secondary", "standard"])
        self.assertEqual(edition["date"], "2026-11-12")
        self.assertEqual(edition["number"], 7)
        self.assertFalse(edition["demo"])
        self.assertIn("no human editor", edition["editorsNote"])
        for placement in edition["placements"]:
            self.assertTrue(placement["snapshot"]["headline"])
            self.assertIn("not a photograph", placement["snapshot"]["image"]["credit"])
            self.assertIn(placement["verificationState"], (UNVERIFIED, SUPPORTED, DISPUTED, REVIEW_REQUIRED))

    def test_empty_and_nothing_new_stories_are_left_out(self):
        empty = dataclasses.replace(self.stories[0], sentences=())
        self.assertEqual(compose_edition([empty], "2026-11-12", 1)["placements"], [])


if __name__ == "__main__":
    unittest.main()
