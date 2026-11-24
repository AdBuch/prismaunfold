import unittest
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from pathlib import Path

from prismunfold.editorial import validate, editions, export_editorial
from prismunfold.storage import open_store


def sample():
    sections = ["Schweiz Politik", "Schweiz Regional", "Peru Politik", "Krisen- und Konfliktgebiete", "International", "Good News"]
    def paragraphs(n, words):
        return [{"text": " ".join(["Beispiel"] * words), "source_ids": ["a", "b"]} for _ in range(n)]
    return {"publication": "morgenbriefing", "provider": "codex", "date": "2026-11-24",
            "sources": [{"id": "a", "url": "https://www.admin.ch/a", "publisher": "Bund", "title": "A"},
                        {"id": "b", "url": "https://www.un.org/b", "publisher": "UN", "title": "B"}],
            "articles": [{"section": s, "headline": s, "lead": "Vorspann", "paragraphs": paragraphs(2, 40)} for s in sections],
            "magazine": {"headline": "Magazin", "lead": "Vorspann", "paragraphs": paragraphs(5, 80)}}


class EditorialTests(unittest.TestCase):
    def test_complete_edition_and_archive(self):
        payload = validate(sample(), lambda url: True)
        self.assertEqual(len(payload["articles"]), 6)
        self.assertEqual(len(payload["magazine"]["paragraphs"]), 5)
        with TemporaryDirectory() as tmp:
            store = open_store(Path(tmp) / "test.db")
            try:
                store.save_edition("editorial|morgenbriefing|2026-11-24", "de", datetime.now(timezone.utc), payload)
                store.commit()
                self.assertEqual(editions(store), [payload])
                self.assertEqual(store.daily_editions(), {})
                self.assertTrue(Path(export_editorial(store, tmp)).exists())
            finally:
                store.close()

    def test_background_and_topic(self):
        raw = sample()
        raw["articles"][0]["topic"] = "swiss-politics"
        raw["articles"][0]["background"] = [{"heading": "Kontext", "text": "Hintergrund", "source_ids": ["a"]}]
        result = validate(raw, lambda url: True)
        self.assertEqual(result["articles"][0]["topic"], "swiss-politics")
        self.assertEqual(result["articles"][0]["background"][0]["heading"], "Kontext")

    def test_extra_sections(self):
        raw = sample()
        raw["random"] = {"text": "Belegter Fakt", "source_ids": ["a"]}
        raw["lagebild"] = {"Wichtig": {"text": "Analyse", "source_ids": ["b"]}}
        result = validate(raw, lambda url: True)
        self.assertEqual(result["random"]["text"], "Belegter Fakt")
        self.assertEqual(result["lagebild"][0]["category"], "Wichtig")
        self.assertEqual(result["lagebild"][0]["sources"][0]["id"], "b")

    def test_missing_source_omits_whole_article(self):
        raw = sample()
        raw["articles"][0]["paragraphs"][0]["source_ids"] = ["b"]
        payload = validate(raw, lambda url: "admin.ch" in url)
        self.assertEqual(len(payload["articles"]), 5)
        self.assertTrue(payload["warnings"])

    def test_bad_magazine_rejects_edition(self):
        raw = sample()
        raw["magazine"]["paragraphs"][0]["source_ids"] = ["missing"]
        with self.assertRaises(ValueError):
            validate(raw, lambda url: True)

    def test_excluded_source_rejected(self):
        raw = sample()
        raw["sources"][0]["url"] = "https://example.com/article"
        with self.assertRaises(ValueError):
            validate(raw, lambda url: True, excluded={"example.com"})

    def test_paywall_requires_other_support(self):
        raw = sample()
        raw["sources"][1]["access"] = "paywalled"
        self.assertEqual(len(validate(raw, lambda url: "admin.ch" in url, excluded=set())["articles"]), 6)
        raw["magazine"]["paragraphs"][0]["source_ids"] = ["b"]
        with self.assertRaises(ValueError):
            validate(raw, lambda url: True, excluded=set())
