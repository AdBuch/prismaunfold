import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from prismunfold.editorial import (apply_policy, editions, export_editorial, problems, public_view, publish,
                                   review_article, select_candidate, validate)
from prismunfold.storage import open_store

FIXTURES = Path(__file__).parent / "fixtures" / "editorial"


def sample():
    sections = ["Schweiz Politik", "Schweiz Regional", "Peru Politik", "Krisen- und Konfliktgebiete", "International", "Good News"]
    def paragraphs(n, words):
        return [{"text": " ".join(["Beispiel"] * words), "source_ids": ["a", "b"]} for _ in range(n)]
    return {"publication": "morgenbriefing", "provider": "codex", "date": "2026-11-24",
            "sources": [{"id": "a", "url": "https://www.admin.ch/a", "publisher": "Bund", "title": "A"},
                        {"id": "b", "url": "https://www.un.org/b", "publisher": "UN", "title": "B"}],
            "articles": [{"section": s, "headline": s, "lead": "Vorspann", "paragraphs": paragraphs(2, 40)} for s in sections],
            "magazine": {"headline": "Magazin", "lead": "Vorspann", "paragraphs": paragraphs(5, 80)}}


def ap_probe(url):
    """The 25 November 2026 incident: AP answers 403 to HEAD and GET."""
    return "restricted" if "apnews.com" in url else "reachable"


class EditorialValidationTests(unittest.TestCase):
    def test_complete_edition_and_archive(self):
        payload = validate(sample(), lambda url: True, excluded=set())
        self.assertEqual(len(payload["articles"]), 6)
        self.assertTrue(all(a["state"] == "validated" for a in payload["articles"]))
        self.assertEqual(len(payload["magazine"]["paragraphs"]), 5)
        with TemporaryDirectory() as tmp:
            store = open_store(Path(tmp) / "test.db")
            try:
                outcome, stored = publish(store, sample(), payload, auto=True, site_dir=tmp)
                self.assertEqual(outcome, "published")
                self.assertEqual(editions(store)[0]["date"], "2026-11-24")
                self.assertEqual(store.daily_editions(), {})
                exported = json.loads((Path(tmp) / "api/v1/editorial/morgenbriefing.json").read_text())
                self.assertNotIn("withheld", exported[0])
                self.assertTrue((Path(tmp) / "api/v1/daily/2026-11-24.json").exists())
            finally:
                store.close()

    def test_background_and_topic(self):
        raw = sample()
        raw["articles"][0]["topic"] = "swiss-politics"
        raw["articles"][0]["background"] = [{"heading": "Kontext", "text": "Hintergrund", "source_ids": ["a"]}]
        result = validate(raw, lambda url: True, excluded=set())
        self.assertEqual(result["articles"][0]["topic"], "swiss-politics")
        self.assertEqual(result["articles"][0]["background"][0]["heading"], "Kontext")

    def test_extra_sections(self):
        raw = sample()
        raw["random"] = {"text": "Belegter Fakt", "source_ids": ["a"]}
        raw["lagebild"] = {"Wichtig": {"text": "Analyse", "source_ids": ["b"]}}
        result = validate(raw, lambda url: True, excluded=set())
        self.assertEqual(result["random"]["text"], "Belegter Fakt")
        self.assertEqual(result["lagebild"][0]["category"], "Wichtig")
        self.assertEqual(result["lagebild"][0]["sources"][0]["id"], "b")

    def test_one_failed_paragraph_marks_only_that_article(self):
        raw = sample()
        raw["articles"][0]["paragraphs"][0]["source_ids"] = ["b"]
        payload = validate(raw, lambda url: "admin.ch" in url, excluded=set())
        self.assertEqual(len(payload["articles"]), 6)
        first = next(a for a in payload["articles"] if a["headline"] == "Schweiz Politik")
        self.assertEqual(first["state"], "review_required")
        self.assertEqual(first["review_reasons"][0]["paragraph"], 1)
        self.assertEqual(first["review_reasons"][0]["reason"], "only_missing_sources")
        self.assertEqual(sum(a["state"] == "validated" for a in payload["articles"]), 5)
        found = problems(payload)
        self.assertEqual(found[0]["sources"][0]["url"], "https://www.un.org/b")

    def test_malformed_article_is_listed_not_fatal(self):
        raw = sample()
        raw["articles"][1]["section"] = "Unbekannt"
        payload = validate(raw, lambda url: True, excluded=set())
        self.assertEqual(len(payload["articles"]), 5)
        self.assertEqual(payload["invalid"][0]["reason"], "Unknown section")

    def test_failed_magazine_keeps_the_edition_publishable(self):
        raw = sample()
        raw["magazine"]["paragraphs"][0]["source_ids"] = ["missing"]
        payload = validate(raw, lambda url: True, excluded=set())
        self.assertIsNone(payload["magazine"])
        self.assertEqual(payload["invalid"][0]["kind"], "magazine")
        result = apply_policy(payload, auto=True)
        self.assertEqual(len(result["articles"]), 6)
        self.assertEqual(result["completeness"], "partial")

    def test_paywalled_only_paragraph_needs_review(self):
        raw = sample()
        raw["sources"][1]["access"] = "paywalled"
        self.assertTrue(all(a["state"] == "validated"
                            for a in validate(raw, lambda url: "admin.ch" in url, excluded=set())["articles"]))
        raw["magazine"]["paragraphs"][0]["source_ids"] = ["b"]
        payload = validate(raw, lambda url: True, excluded=set())
        self.assertEqual(payload["magazine"]["state"], "review_required")
        self.assertEqual(payload["magazine"]["review_reasons"][0]["reason"], "only_restricted_sources")

    def test_excluded_source_is_removed_and_flagged_not_edition_fatal(self):
        raw = sample()
        raw["sources"][0]["url"] = "https://example.com/article"
        payload = validate(raw, lambda url: True, excluded={"example.com"})
        self.assertTrue(all(a["state"] == "review_required" for a in payload["articles"]))
        self.assertNotIn("a", payload["articles"][0]["paragraphs"][0]["source_ids"])
        raw["articles"][0]["paragraphs"][0]["source_ids"] = ["a"]
        payload = validate(raw, lambda url: True, excluded={"example.com"})
        self.assertEqual(payload["articles"][0]["state"], "rejected")

    def test_unsafe_source_rejects_only_dependent_article(self):
        raw = sample()
        raw["sources"].append({"id": "c", "url": "https://intranet.example.net/x", "publisher": "X", "title": "X"})
        raw["articles"][2]["paragraphs"][0]["source_ids"] = ["c"]
        payload = validate(raw, lambda url: "unsafe" if "intranet" in url else "reachable", excluded=set())
        states = sorted(a["state"] for a in payload["articles"])
        self.assertEqual(states.count("rejected"), 1)
        self.assertEqual(states.count("validated"), 5)
        result = apply_policy(payload, auto=True)
        self.assertEqual(len(result["articles"]), 5)
        self.assertEqual(result["withheld"][0]["state"], "rejected")

    def test_transient_source_state_is_distinct(self):
        raw = sample()
        payload = validate(raw, lambda url: "timeout", excluded=set())
        self.assertEqual(payload["articles"][0]["review_reasons"][0]["reason"], "sources_temporarily_unreachable")

    def test_legacy_combined_status_is_read_as_unsafe(self):
        payload = validate(sample(), lambda url: "unsafe_or_unresolved", excluded=set())
        self.assertTrue(all(a["state"] == "rejected" for a in payload["articles"]))

    def test_rejected_short_items_and_unchecked_background_are_never_published(self):
        raw = sample()
        raw["sources"].append({"id": "c", "url": "https://intranet.example.net/x", "publisher": "X", "title": "X"})
        raw["sources"].append({"id": "d", "url": "https://apnews.com/x", "publisher": "AP", "title": "AP"})
        raw["random"] = {"text": "Fakt", "source_ids": ["c"]}
        raw["articles"][0]["background"] = [{"heading": "H", "text": "Nur AP", "source_ids": ["d"]}]
        probe = lambda u: "unsafe" if "intranet" in u else "restricted" if "apnews" in u else "reachable"
        payload = validate(raw, probe, excluded=set())
        manual = apply_policy(payload, auto=False, approve_review_required=True)
        self.assertNotIn("random", manual)
        auto = apply_policy(payload, auto=True)
        first = next(a for a in auto["articles"] if a["headline"] == "Schweiz Politik")
        self.assertEqual(first["background"], [])

    def test_untrusted_generated_at_is_normalised(self):
        from prismunfold.editorial import _timestamp
        self.assertIsNone(_timestamp({"x": 1}))
        self.assertIsNone(_timestamp("yesterday"))
        self.assertIsNone(_timestamp("2026-11-25T06:00:00"))
        self.assertEqual(_timestamp("2026-11-25T06:00:00Z"), "2026-11-25T06:00:00+00:00")

    def test_partial_edition_policy(self):
        raw = sample()
        payload = validate(raw, lambda url: "admin.ch" not in url and "un.org" not in url, excluded=set())
        with self.assertRaisesRegex(ValueError, "Publication refused"):
            apply_policy(payload, auto=True)
        manual = apply_policy(payload, auto=False, approve_review_required=True, allow_partial=True, reviewer="ed")
        self.assertEqual(len(manual["articles"]), 6)
        self.assertTrue(all(a["approval"]["by"] == "ed" for a in manual["articles"]))


class AP403RegressionTest(unittest.TestCase):
    """25 Nov 2026: one AP URL answered 403 and the whole Codex edition failed."""

    def setUp(self):
        self.raw = json.loads((FIXTURES / "2026-11-25-ap403.json").read_text(encoding="utf-8"))

    def test_403_no_longer_rejects_the_edition(self):
        payload = validate(self.raw, ap_probe, excluded=set())
        self.assertEqual(len(payload["articles"]), 10)
        crisis = next(a for a in payload["articles"] if a["section"] == "Krisen- und Konfliktgebiete")
        self.assertEqual(crisis["state"], "validated")  # AP is supplementary next to UN
        ap = next(s for s in crisis["sources"] if s["id"] == "ap")
        self.assertEqual(ap["link_status"], "restricted")
        self.assertEqual(payload["magazine"]["state"], "review_required")
        result = apply_policy(payload, auto=True)
        self.assertEqual(len(result["articles"]), 10)
        self.assertIsNone(result["magazine"])
        self.assertEqual(result["withheld"][0]["kind"], "magazine")
        self.assertEqual(result["completeness"], "partial")

    def test_withheld_magazine_can_be_approved_later_without_regeneration(self):
        payload = validate(self.raw, ap_probe, excluded=set())
        with TemporaryDirectory() as tmp:
            store = open_store(Path(tmp) / "db")
            try:
                publish(store, self.raw, payload, auto=True, site_dir=tmp)
                magazine_id = payload["magazine"]["article_id"]
                edition = review_article(store, "2026-11-25", magazine_id, "approve", "Adrian", "AP checked by hand",
                                         site_dir=tmp)
                self.assertEqual(edition["magazine"]["approval"]["by"], "Adrian")
                self.assertTrue(edition["magazine"]["review_required"])
                exported = json.loads((Path(tmp) / "api/v1/editorial/morgenbriefing.json").read_text())
                self.assertEqual(exported[0]["magazine"]["headline"], payload["magazine"]["headline"])
                edition = review_article(store, "2026-11-25", magazine_id, "reject", "Adrian", site_dir=tmp)
                self.assertEqual(edition["withheld"][-1]["state"], "withdrawn")
                # A reviewer's reject can be reversed; an unsafe-source rejection cannot.
                edition = review_article(store, "2026-11-25", magazine_id, "approve", "Adrian", site_dir=tmp)
                self.assertTrue(edition["magazine"]["review_required"])
            finally:
                store.close()


class RecoveryTests(unittest.TestCase):
    def test_publish_is_idempotent_and_refuses_silent_overwrite(self):
        raw = sample()
        payload = validate(raw, lambda url: True, excluded=set())
        with TemporaryDirectory() as tmp:
            store = open_store(Path(tmp) / "db")
            try:
                self.assertEqual(publish(store, raw, payload, auto=True, site_dir=tmp)[0], "published")
                # A retry after a failed export (same content) only re-exports.
                (Path(tmp) / "api/v1/editorial/morgenbriefing.json").unlink()
                self.assertEqual(publish(store, raw, payload, auto=True, site_dir=tmp)[0], "already_published")
                self.assertTrue((Path(tmp) / "api/v1/editorial/morgenbriefing.json").exists())
                changed = sample()
                changed["articles"][0]["lead"] = "Korrigierter Vorspann"
                changed_payload = validate(changed, lambda url: True, excluded=set())
                with self.assertRaisesRegex(ValueError, "--replace"):
                    publish(store, changed, changed_payload, auto=True, site_dir=tmp)
                self.assertEqual(publish(store, changed, changed_payload, auto=False, replace=True, site_dir=tmp)[0], "published")
                states = [c["state"] for c in store.list_contributions(edition_date="2026-11-24")]
                self.assertEqual(sorted(states), ["published", "superseded"])
                record = store.list_contributions(edition_date="2026-11-24")[0]
                self.assertEqual(record["raw"]["date"], "2026-11-24")  # raw document preserved
            finally:
                store.close()

    def test_select_candidate_is_deterministic_and_never_modifies_raw_files(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            good, partial, broken = base / "2026-11-24.zIa6G9", base / "2026-11-24.aaaaaa", base / "2026-11-24.bbbbbb"
            for d in (good, partial, broken):
                d.mkdir()
            raw = sample()
            (good / "edition.json").write_text(json.dumps(raw))
            repaired = dict(raw, articles=raw["articles"][:4])
            (partial / "edition.json").write_text(json.dumps(repaired))
            (broken / "edition.json").write_text("{not json")
            before = {p: p.read_bytes() for p in base.glob("*/edition.json")}
            os.utime(partial / "edition.json", (time.time() + 60, time.time() + 60))
            self.assertEqual(select_candidate(base, "2026-11-24"), good / "edition.json")
            self.assertEqual({p: p.read_bytes() for p in base.glob("*/edition.json")}, before)
            self.assertIsNone(select_candidate(base, "2026-11-23"))

    def test_concurrent_publication_is_serialised(self):
        from prismunfold.storage import LockTimeout
        with TemporaryDirectory() as tmp:
            first, second = open_store(Path(tmp) / "db"), open_store(Path(tmp) / "db")
            try:
                with first.lock("edition-publication"):
                    with self.assertRaises(LockTimeout):
                        with second.lock("edition-publication", timeout=0.3):
                            pass
                with second.lock("edition-publication", timeout=0.3):
                    with second.lock("edition-publication", timeout=0.3):  # re-entrant
                        pass
            finally:
                first.close()
                second.close()

    def test_public_view_hides_withheld_and_internal_fields(self):
        payload = apply_policy(validate(sample(), lambda url: True, excluded=set()), auto=True)
        view = public_view(dict(payload, raw_hash="x", contribution_id="y"))
        self.assertNotIn("withheld", view)
        self.assertNotIn("raw_hash", view)
        self.assertNotIn("invalid", view)


class ResearchStageTests(unittest.TestCase):
    def test_research_keeps_only_citable_notes(self):
        from prismunfold.editorial import prepare_research
        sections = ["Schweiz Politik", "Schweiz Regional", "Peru Politik", "International", "Reisen", "Good News"]
        raw = {"sources": [{"id": "a", "url": "https://www.admin.ch/a", "title": "A", "publisher": "Bund"},
                           {"id": "b", "url": "https://www.un.org/b", "title": "B", "publisher": "UN"},
                           {"id": "p", "url": "https://apnews.com/x", "title": "P", "publisher": "AP"}],
               "dossiers": [{"section": s, "subject": s, "notes": [{"text": "Befund", "source_ids": ["a"]},
                                                                    {"text": "Nur AP", "source_ids": ["p"]}]} for s in sections]
                           + [{"section": "Magazin", "subject": "M", "notes": [{"text": "x", "source_ids": ["a", "b"]}]}]}
        result = prepare_research(raw, ap_probe, excluded=set())
        self.assertEqual({s["id"] for s in result["sources"]}, {"a", "b"})
        self.assertTrue(all(len(d["notes"]) == 1 for d in result["dossiers"] if d["section"] != "Magazin"))
        raw["dossiers"] = raw["dossiers"][:3]
        with self.assertRaisesRegex(ValueError, "six sourced"):
            prepare_research(raw, ap_probe, excluded=set())


class EditorialCliTests(unittest.TestCase):
    def test_validate_and_inspect_need_no_database_or_ai(self):
        import subprocess, sys
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1] / "src"), EDITORIAL_CATALOG=str(Path(__file__).parents[1] / "catalog/sources.json"))
        raw = json.dumps(sample()).encode()
        # Links are not reachable in CI; inspect must still report, not crash.
        env["SOURCE_CHECK_CACHE"] = ""
        code = ("import sys, prismunfold.editorial as e; e.http_status = lambda u: 'restricted';"
                "e.SourceCheckCache.probe = lambda self, check=None: (lambda u: 'restricted'); sys.exit(e.main(sys.argv[1:]))")
        out = subprocess.run([sys.executable, "-c", code, "inspect", "2026-11-24"], input=raw, env=env,
                             capture_output=True, check=True)
        found = json.loads(out.stdout)
        self.assertTrue(found and all(p["reason"] == "only_restricted_sources" for p in found))


if __name__ == "__main__":
    unittest.main()
