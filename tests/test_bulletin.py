import copy
import json
import tempfile
import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from prismunfold.bulletin import editorial_context, fetch, import_daily, imports, merge_editions, validate
from prismunfold.editorial import export_editorial
from prismunfold.models import Story, StorySentence, StorySource
from prismunfold.storage import open_store

DAY = "2026-11-25"
URL = "https://www.admin.ch/example"


def bulletin():
    return {
        "schema_version": "1.1", "date": DAY, "timezone": "Europe/Zurich",
        "generated_at": DAY + "T07:00:00+01:00", "publication_status": "published",
        "lead": "Die Lage am Morgen.", "editorial_note": "Eine offene Frage bleibt.",
        "sections": [{"title": "Schweiz Politik", "items": [{
            "id": "energy", "title": "Parlament verabschiedet neue Regeln für Solarförderung",
            "body": "Der erste Absatz.\n\nEin zweiter Absatz zur Umsetzung.",
            "sources": [{"url": URL + "?utm_source=test", "publisher": "Bund", "title": "Beschluss",
                         "source_type": "primary", "published_at": DAY}],
            "source_urls": [URL], "uncertainties": ["Der Zeitpunkt der Umsetzung ist offen."],
            "assessments": [{"text": "Eine frühe Wirkung ist vorerst unwahrscheinlich.", "perspective": "Forschung",
                             "attribution": "Forschungsgruppe", "source_urls": ["https://www.example.org/advice"]}],
            "perspectives": ["Die Vollzugsbehörden sehen zusätzlichen Aufwand."],
            "images": [
                {"url": "https://www.example.org/solar.jpg?sig=P%2fQ", "license": "CC BY-SA 4.0",
                 "credit": "Bildautor", "source_url": "https://www.example.org/image"},
                {"url": "https://www.example.org/unlicensed.jpg", "credit": "Unbekannt"},
            ],
        }]}],
        "deep_dive": {"id": "feature", "title": "Die Stromnetze im Winter", "body": "Ausführliche Analyse."},
        "good_news": {"id": "good", "title": "Erholung der Fischbestände", "body": "Die Bestände erholen sich."},
        "random_fact": {"id": "random", "title": "Wussten Sie?", "body": "Überraschendes aus der Botanik."},
        "outlook": ["Umsetzung des Beschlusses beobachten.", {"text": "Datenlage prüfen.", "label": "Beobachten"}],
    }


class BulletinTests(unittest.TestCase):
    def test_preserves_evidence_and_display_rights_without_inventing_paragraph_citations(self):
        entry = validate(bulletin(), DAY)
        article = entry["articles"][0]
        self.assertEqual([s["url"] for s in article["sources"]], [URL])
        self.assertEqual(article["paragraphs"][0]["source_ids"], [])
        self.assertEqual(article["sources"][0]["source_type"], "primary")
        self.assertEqual(article["perspectives"][0]["attribution"], "Forschungsgruppe")
        self.assertEqual(len(article["perspectives"]), 2)
        self.assertEqual(article["images"][0]["url"], "https://www.example.org/solar.jpg?sig=P%2fQ")
        self.assertTrue(article["images"][0]["display"])
        self.assertFalse(article["images"][1]["display"])
        self.assertEqual(entry["magazine"]["headline"], "Die Stromnetze im Winter")
        self.assertEqual(entry["random_article"]["external_id"], "random")
        self.assertEqual(entry["articles"][1]["section"], "Good News")

    def test_import_clock_replay_recovery_and_staged_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = open_store(Path(tmp) / "db")
            try:
                secret = Path(tmp) / "token"
                secret.write_text("test_token")
                calls = []
                raw = bulletin()
                raw["publication_status"] = "test_import_unverified"

                def downloader(day, token):
                    calls.append((day, token))
                    return json.dumps(raw).encode()

                self.assertFalse(import_daily(store, secret, datetime.fromisoformat(DAY + "T05:59:00+00:00"), fetcher=downloader))
                self.assertFalse(calls)
                due = datetime.fromisoformat(DAY + "T06:00:00+00:00")
                self.assertTrue(import_daily(store, secret, due, fetcher=downloader))
                self.assertFalse(import_daily(store, secret, due, fetcher=downloader))
                self.assertEqual(calls[0], (DAY, "test_token"))
                self.assertEqual(editorial_context(store, DAY), {})
                self.assertEqual(json.loads(Path(export_editorial(store, tmp)).read_text()), [])
                raw["publication_status"] = "published"
                self.assertTrue(import_daily(store, secret, due, fetcher=downloader))
                self.assertEqual(len(imports(store)), 1)
                self.assertEqual(editorial_context(store, "2026-11-26")["date"], DAY)
                self.assertEqual(json.loads(Path(export_editorial(store, tmp)).read_text())[0]["date"], DAY)
                raw["generated_at"] = DAY + "T06:00:00+01:00"
                self.assertFalse(import_daily(store, secret, due, fetcher=downloader))
                with self.assertRaisesRegex(ValueError, "invalid bulletin JSON"):
                    import_daily(store, secret, due, fetcher=lambda *_: b"{")
                self.assertEqual(len(imports(store)), 1)
            finally:
                store.close()

    def test_merge_preserves_authored_text_sources_and_original_story_verification(self):
        incoming = validate(bulletin(), DAY)
        original = copy.deepcopy(incoming["articles"][0])
        original["paragraphs"] = [{"text": "Eigene Redaktion", "source_ids": []}]
        original.pop("origin")
        authored = {"date": DAY, "articles": [original], "magazine": {"section": "Magazin",
                    "headline": "Ein zweites Thema", "sources": []}}
        story = Story("123", "solar", "desk", "feeds", "Politik", "politik", "de", DAY,
                      datetime.fromisoformat(DAY), original["headline"],
                      (StorySentence("Eine weitere Quelle übersetzt den Beschluss.", (URL,)),),
                      (StorySource(URL, "Beschluss", "Bund"),), verification={"state": "supported"})
        edition, = merge_editions([authored], [incoming], [story])
        merged, = edition["articles"]
        self.assertEqual(merged["paragraphs"][0]["text"], "Eigene Redaktion")
        self.assertNotIn("coverage", original)
        self.assertEqual([c["origin"] for c in merged["coverage"]], ["prism-data", "prismunfold"])
        self.assertEqual(merged["coverage"][1]["verification"], "supported")
        self.assertEqual(edition["additional_articles"][0]["section"], "Good News")
        self.assertEqual(edition["additional_magazines"][0]["headline"], incoming["magazine"]["headline"])

    def test_github_auth_goes_only_to_api_and_404_checks_repository_access(self):
        with patch("prismunfold.bulletin.build_opener") as factory:
            opener = factory.return_value
            opener.open = Mock(side_effect=[HTTPError("https://api.github.com/", 404, "", {}, BytesIO()), BytesIO(b"[]")])
            self.assertIsNone(fetch(DAY, "test_token"))
            urls = [call.args[0].full_url for call in opener.open.call_args_list]
            self.assertTrue(all(url.startswith("https://api.github.com/repos/AdBuch/prism-data/") for url in urls))
            self.assertIn(f"/data/morgenbriefing/{DAY}.json?ref=main", urls[0])
            self.assertEqual(opener.open.call_args_list[0].args[0].get_header("Authorization"), "Bearer test_token")

    def test_rejects_invalid_date_and_unsafe_image_url(self):
        raw = bulletin()
        with self.assertRaisesRegex(ValueError, "date do not match"):
            validate(raw, "2026-11-24")
        raw["sections"][0]["items"][0]["images"][0]["url"] = "javascript:alert(1)"
        with self.assertRaisesRegex(ValueError, "invalid HTTP"):
            validate(raw, DAY)
