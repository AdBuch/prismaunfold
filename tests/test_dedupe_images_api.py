"""Deduplication, provenance counting, image rights, logging redaction and the daily API contract."""
import json
import tempfile
import unittest
from pathlib import Path

from prismunfold.contributions import independent_publishers
from prismunfold.daily import SCHEMA, compose, export_daily
from prismunfold.dedupe import add_coverage, match_score
from prismunfold.images import AI_LABEL, image_metadata
from prismunfold.oplog import record


def item(headline, urls=(), lead="", paragraphs=("Text.",), day="2026-11-25", origin="prism-data"):
    return dict(headline=headline, lead=lead, date=day, origin=origin, section="International",
                sources=[dict(id=str(i), url=u) for i, u in enumerate(urls)],
                paragraphs=[dict(text=p, source_ids=[]) for p in paragraphs])


class DedupeTests(unittest.TestCase):
    def test_identical_articles_match(self):
        a = item("Bundesrat beschliesst neue Regeln für Solarförderung")
        b = item("Bundesrat beschliesst neue Regeln für Solarförderung!")
        self.assertEqual(match_score(a, b), 2.0)

    def test_related_reporting_matches_on_shared_original_url(self):
        a = item("Parlament verabschiedet Solarförderung", ["https://www.admin.ch/solar?utm_source=x"])
        b = item("Solarförderung im Parlament verabschiedet: was sich ändert", ["https://admin.ch/solar/".replace("admin", "www.admin")])
        self.assertGreater(match_score(a, b), 1.0)

    def test_unrelated_events_mentioning_the_same_country_stay_separate(self):
        a = item("Peru: Regierung kündigt Wasserschutz im Amazonas an")
        b = item("Peru: Regierung verliert Vertrauensabstimmung im Kongress")
        self.assertEqual(match_score(a, b), 0.0)

    def test_outside_time_window_never_matches(self):
        a = item("Bundesrat beschliesst neue Regeln für Solarförderung", day="2026-11-25")
        b = item("Bundesrat beschliesst neue Regeln für Solarförderung", day="2026-11-10")
        self.assertEqual(match_score(a, b), 0.0)

    def test_conflicting_perspectives_are_kept_and_repeated_paragraphs_dropped(self):
        target = item("Waffenruhe in Region X hält vorerst", paragraphs=("Die Waffenruhe hält.",), origin="prismunfold")
        candidate = item("Waffenruhe in Region X hält vorerst", paragraphs=("Die Waffenruhe hält.", "Beobachter melden Verstösse."))
        candidate["uncertainties"] = ["Angaben der Konfliktparteien widersprechen sich."]
        self.assertTrue(add_coverage(candidate, [target]))
        attached = target["coverage"][0]
        self.assertEqual([p["text"] for p in attached["paragraphs"]], ["Beobachter melden Verstösse."])
        self.assertEqual(attached["uncertainties"], ["Angaben der Konfliktparteien widersprechen sich."])
        self.assertEqual(target["paragraphs"][0]["text"], "Die Waffenruhe hält.")

    def test_ambiguous_match_is_not_merged(self):
        candidate = item("Bundesrat beschliesst neue Regeln für Solarförderung")
        targets = [item("Bundesrat beschliesst neue Regeln für Solarförderung"),
                   item("Bundesrat beschliesst neue Regeln für Solarförderung")]
        self.assertFalse(add_coverage(candidate, targets))

    def test_same_original_cited_by_several_agents_counts_once(self):
        ap = "https://apnews.com/article/abc?utm_campaign=x"
        self.assertEqual(independent_publishers([[{"url": ap}], [{"url": "https://www.apnews.com/article/abc"}],
                                                 [ap]]), {"apnews.com"})
        self.assertEqual(len(independent_publishers([[{"url": ap}], [{"url": "https://www.admin.ch/x"}]])), 2)


class ImageTests(unittest.TestCase):
    def test_rights_are_required_before_display(self):
        base = dict(url="https://upload.wikimedia.org/a.jpg", credit="Foto: Jane Doe")
        self.assertTrue(image_metadata(dict(base, license="CC BY-SA 4.0"))["display"])
        self.assertEqual(image_metadata(base)["display_reason"], "missing_rights")
        self.assertEqual(image_metadata(dict(url=base["url"], license="CC0"))["display_reason"], "missing_credit")
        self.assertEqual(image_metadata(dict(base, display_allowed=False, license="CC0"))["display_reason"], "rights_blocked")
        self.assertEqual(image_metadata(dict(base, url="http://x.example.org/a.jpg", display_allowed=True))["display_reason"], "not_https")
        kept = image_metadata(dict(base, caption="Ohne Freigabe", rights_note="Anfrage läuft"))
        self.assertEqual((kept["caption"], kept["rights_note"], kept["display"]), ("Ohne Freigabe", "Anfrage läuft", False))

    def test_ai_illustrations_need_explicit_grant_and_are_labelled(self):
        img = dict(url="https://cdn.example.org/i.png", credit="PrismUnfold", origin="ai_illustration", license="CC0")
        self.assertEqual(image_metadata(img)["display_reason"], "ai_illustration_needs_explicit_grant")
        shown = image_metadata(dict(img, display_allowed=True))
        self.assertTrue(shown["display"])
        self.assertIn(AI_LABEL, shown["caption"])

    def test_unsafe_image_url_is_rejected(self):
        with self.assertRaises(ValueError):
            image_metadata(dict(url="javascript:alert(1)"))


class LoggingTests(unittest.TestCase):
    def test_secrets_never_reach_the_log(self):
        rec = record("bulletin", "import_failed", token="ghp_abcdefghijklmnopqrstuvwxyz0123",
                     authorization="Bearer x", reason="failed with github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ and Bearer abc",
                     edition_date="2026-11-25", nested={"api_key": "sk-1", "ok": 1})
        text = json.dumps(rec)
        self.assertNotIn("ghp_", text)
        self.assertNotIn("github_pat_", text)
        self.assertNotIn("Bearer abc", text)
        self.assertNotIn("api_key", text)
        self.assertEqual(rec["edition_date"], "2026-11-25")
        self.assertEqual({"timestamp", "component", "event", "run_id"} - rec.keys(), set())


class DailyContractTests(unittest.TestCase):
    """API contract for the unified daily edition (docs/API.md)."""

    def edition(self):
        article = dict(article_id="ed-1", section="Schweiz Politik", headline="H1", lead="L", kind="news", state="published",
                       paragraphs=[dict(text="P", source_ids=["a"])], provider="codex",
                       sources=[dict(id="a", url="https://www.admin.ch/a", title="A", publisher="Bund", link_status="reachable")],
                       images=[dict(url="https://x.example.org/no-rights.jpg", credit="", display=False, origin="unknown")],
                       coverage=[dict(headline="H1b", paragraphs=[], sources=[], origin="prism-data",
                                      provenance=dict(provider="prism-data", origin_type="ai_secondary",
                                                      publication_basis="upstream_published", citation_level="item"))])
        good = dict(article, article_id="ed-2", section="Good News", headline="G", coverage=[], images=[])
        return dict(date="2026-11-25", articles=[article, good], magazine=None, additional_articles=[], additional_magazines=[],
                    warnings=["Magazin zurückgestellt"], disclosure="KI", completeness="partial",
                    lagebild=[dict(category="Wichtig", text="T", sources=[], state="validated")],
                    bulletin=dict(lead="Intro", outlook=[dict(text="O", label="Beobachten", sources=[])], disclosure="D",
                                  note="N", random_article=None, publication_basis="upstream_published"))

    def test_contract_shape(self):
        doc = compose(self.edition())
        self.assertEqual(doc["schemaVersion"], SCHEMA)
        self.assertEqual(set(doc), {"schemaVersion", "date", "timezone", "title", "mainHeadline", "introduction", "rubrics",
                                    "articles", "briefs", "magazine", "goodNews", "randomFacts", "assessments",
                                    "contributors", "transparency", "revision"})
        self.assertEqual(doc["mainHeadline"], {"articleId": "ed-1", "headline": "H1"})
        self.assertEqual(doc["rubrics"], [{"name": "Schweiz Politik", "articleIds": ["ed-1"]}])
        self.assertEqual([a["articleId"] for a in doc["goodNews"]], ["ed-2"])
        art = doc["articles"][0]
        self.assertNotIn("url", art["images"][0])  # no display rights -> no embeddable URL
        self.assertEqual(art["verification"]["factual"], "not_independently_verified")
        self.assertEqual(art["coverage"][0]["provenance"]["citationLevel"], "item")
        self.assertEqual([c["provider"] for c in doc["contributors"]], ["codex", "prism-data"])
        self.assertEqual(doc["transparency"]["completeness"], "partial")
        self.assertEqual(len(doc["assessments"]), 2)

    def test_export_is_atomic_and_indexed(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_daily([self.edition()], tmp)
            files = sorted(p.name for p in (Path(tmp) / "api/v1/daily").iterdir())
            self.assertEqual(files, ["2026-11-25.json", "index.json"])  # no temp files left behind
            index = json.loads((Path(tmp) / "api/v1/daily/index.json").read_text())
            self.assertEqual(index[0]["href"], "/api/v1/daily/2026-11-25.json")

    def test_failed_export_keeps_the_previous_file(self):
        from unittest.mock import patch

        from prismunfold.export import _write
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "api/v1/x.json"
            _write(path, {"version": 1})
            with patch("prismunfold.export.json.dump", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    _write(path, {"version": 2})
            self.assertEqual(json.loads(path.read_text()), {"version": 1})
            self.assertEqual([p.name for p in path.parent.iterdir()], ["x.json"])


if __name__ == "__main__":
    unittest.main()
