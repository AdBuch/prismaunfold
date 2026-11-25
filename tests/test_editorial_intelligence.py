"""Deterministic Editorial Intelligence tests. No network, model keys or paid calls."""
from __future__ import annotations

import os
import tempfile
import unittest
from uuid import uuid4
from datetime import timedelta
from pathlib import Path

from prismunfold.ei_store import utcnow
from prismunfold.intelligence import EditorialIntelligence, validate_document
from prismunfold.storage import Store


EVENT_KEY = "2026-11-25|ch|solar-vote"


def document(source, language, original_work, *, source_type="journalism",
             relation="supports", event_key=EVENT_KEY):
    return {
        "event_key": event_key, "source_id": source, "url": f"https://{source}.example.org/solar",
        "headline": "Decision about solar subsidies" if language == "en" else
                    ("Beschluss zur Solarförderung" if language == "de" else
                     "Decisión sobre ayudas solares"),
        "language": language, "source_type": source_type,
        "origin_type": "original_publisher", "original_work_id": original_work,
        "published_at": "2026-11-25T12:00:00+01:00",
        "rights": {"ai_processing": True, "store_excerpt": False,
                   "display_excerpt": False},
        "excerpt": "This publisher's copyrighted copy must not be retained.",
        "topics": ["energy", "politics"], "regions": ["CH"],
        "claims": [{
            "key": "vote", "statement": "The legislature adopted the measure.",
            "kind": "fact", "relation": relation, "locator": "paragraph 2 / vote roll"
        }],
    }


def writer(dossier, language):
    return {
        "headline": {"de": "Parlament entscheidet über Solarförderung",
                     "es": "El Parlamento decide sobre los incentivos solares"}[language],
        "lead": {"de": "Der Entscheid wurde bekanntgegeben.",
                 "es": "Se anunció la decisión."}[language],
        "paragraphs": [{
            "text": {"de": "Die Vorlage wurde angenommen.",
                     "es": "La propuesta fue aprobada."}[language],
            "claim_keys": ["vote"],
        }],
        "article_variant": "standard_article",
    }


class EditorialIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "test.sqlite")
        self.addCleanup(self.store.close)
        self.ei = EditorialIntelligence(self.store)
        self.docs = [
            document("publisher-de", "de", "wire-copy-a"),
            document("publisher-es", "es", "wire-copy-a"),
        ]
        self.event_id = self.ei.ingest(self.docs)[0]

    def test_multilingual_same_event_and_syndication_not_independent(self):
        dossier = self.ei.dossier(self.event_id)
        self.assertEqual(dossier["languages"], ["de", "es"])
        self.assertEqual(len(dossier["documents"]), 2)
        self.assertEqual(dossier["independent_original_works"], 1)
        self.assertIn("independent_reporting", dossier["gaps"])
        self.assertIn("original_primary_document", dossier["gaps"])
        self.assertEqual(dossier["claims"][0]["verification"], "requires_independent_review")
        self.assertEqual(dossier["documents"][0]["excerpt"], "")
        self.assertEqual(self.ei.ingest(self.docs), [self.event_id])
        self.assertEqual(len(self.ei.dossier(self.event_id)["documents"]), 2)

    def test_targeted_research_persists_retries_and_fills_gaps(self):
        job = self.ei.plan_research(self.event_id)
        self.assertEqual(job["state"], "pending")
        self.assertFalse(self.ei.repo.enqueue(job))
        first = self.ei.repo.lease(job["id"], worker="test")
        self.assertEqual(first["state"], "leased")
        self.assertIsNone(self.ei.repo.lease(job["id"], worker="other"))
        second = self.ei.repo.lease(job["id"], worker="other",
                                    now=utcnow() + timedelta(minutes=6))
        self.assertNotEqual(first["lease_id"], second["lease_id"])
        with self.assertRaisesRegex(ValueError, "no longer valid"):
            self.ei.repo.finish(job["id"], first["lease_id"], success=True)
        self.ei.repo.finish(job["id"], second["lease_id"], success=False,
                            error_type="ResearchUnavailable")
        self.assertEqual(self.ei.repo.get(f"job|{job['id']}")["state"], "pending")

        official = document("official", "de", "official-roll-call",
                            source_type="official_document")
        dossier = self.ei.run_research(job["id"], lambda requested_job, old: [official])
        self.assertEqual(dossier["independent_original_works"], 2)
        self.assertEqual(dossier["gaps"], [])
        self.assertEqual(self.ei.repo.get(f"job|{job['id']}")["state"], "completed")
        self.assertIsNone(self.ei.plan_research(self.event_id))
        self.assertIsNone(self.ei.run_research(job["id"], lambda j, d: []))

    def test_invalid_research_never_publishes_and_job_is_retryable(self):
        job = self.ei.plan_research(self.event_id)
        invalid = document("different", "de", "other", event_key="different-event")
        with self.assertRaisesRegex(ValueError, "event identity"):
            self.ei.run_research(job["id"], lambda j, d: [invalid])
        self.assertEqual(self.ei.repo.get(f"job|{job['id']}")["state"], "pending")
        self.assertEqual(len(self.ei.dossier(self.event_id)["documents"]), 2)
        self.assertEqual(self.ei.content_pool()["articles"], [])

    def test_provenance_claim_links_review_translations_and_two_readers(self):
        official = document("official", "de", "official-roll-call",
                            source_type="official_document")
        self.ei.ingest([official])
        doc_id = validate_document(official)["document_id"]
        german = self.ei.draft(self.event_id, "de", writer)
        self.assertEqual(german["publication_status"], "draft_needs_review")
        self.assertEqual(self.ei.content_pool()["articles"], [])
        with self.assertRaisesRegex(ValueError, "draft changed since review"):
            self.ei.approve(self.event_id, "de", reviewer="Editor",
                            expected_draft_digest="0" * 64,
                            checked_claim_sources={"vote": [doc_id]})
        with self.assertRaisesRegex(ValueError, "every published claim"):
            self.ei.approve(self.event_id, "de", reviewer="Editor", expected_draft_digest=german["draft_digest"],
                            checked_claim_sources={})
        with self.assertRaisesRegex(ValueError, "human reviewer"):
            self.ei.approve(self.event_id, "de", reviewer="AI", expected_draft_digest=german["draft_digest"],
                            checked_claim_sources={"vote": [doc_id]})
        article = self.ei.approve(self.event_id, "de", reviewer="Editor", expected_draft_digest=german["draft_digest"],
                                  checked_claim_sources={"vote": [doc_id]})
        self.assertEqual(article["revision"], 1)
        same = self.ei.approve(self.event_id, "de", reviewer="Editor", expected_draft_digest=german["draft_digest"],
                                checked_claim_sources={"vote": [doc_id]})
        self.assertEqual(same["approval"], article["approval"])
        spanish = self.ei.draft(self.event_id, "es", writer)
        self.ei.approve(self.event_id, "es", reviewer="Editor", expected_draft_digest=spanish["draft_digest"],
                        checked_claim_sources={"vote": [doc_id]})
        pool = self.ei.content_pool()
        self.assertEqual(pool["schema_version"], "prismunfold.content-pool/1")
        self.assertEqual(len(pool["articles"]), 2)
        self.assertNotIn("reviewer", str(pool))
        self.assertTrue(all(a["claim_references"] for a in pool["articles"]))
        de = self.ei.reader_edition({"languages": ["de"], "topics": ["energy"]})
        es = self.ei.reader_edition({"languages": ["es"], "topics": ["energy"],
                                     "reading_depth": "brief"})
        self.assertEqual(len(de), 1)
        self.assertEqual(len(es), 1)
        self.assertEqual(de[0]["language"], "de")
        self.assertEqual(es[0]["language"], "es")
        self.assertEqual(de[0]["claim_references"], es[0]["claim_references"])
        self.assertEqual(es[0]["paragraphs"], [])
        self.assertEqual(self.ei.reader_edition({"topics": ["sports"]}), [])
        path = Path(self.ei.export_pool(self.tmp.name))
        self.assertTrue(path.is_file())
        self.assertIn("editorial-intelligence", path.as_posix())

    def test_revisions_are_immutable_and_draft_requires_all_claim_links(self):
        official = document("official", "de", "official-roll-call",
                            source_type="official_document")
        self.ei.ingest([official])
        doc_id = validate_document(official)["document_id"]
        initial = self.ei.draft(self.event_id, "de", writer)
        self.ei.approve(self.event_id, "de", reviewer="Editor",
                        expected_draft_digest=initial["draft_digest"],
                        checked_claim_sources={"vote": [doc_id]})
        def revised(dossier, language):
            raw = writer(dossier, language)
            raw["paragraphs"][0]["text"] = "Die Vorlage erhielt eine Mehrheit."
            return raw
        revised_draft = self.ei.draft(self.event_id, "de", revised)
        latest = self.ei.approve(self.event_id, "de", reviewer="Editor",
                                 expected_draft_digest=revised_draft["draft_digest"],
                                 checked_claim_sources={"vote": [doc_id]})
        self.assertEqual(latest["revision"], 2)
        self.assertIsNotNone(self.ei.repo.get(f"revision|{latest['article_id']}|1"))
        self.assertIsNotNone(self.ei.repo.get(f"revision|{latest['article_id']}|2"))
        with self.assertRaisesRegex(ValueError, "claim references"):
            self.ei.draft(self.event_id, "en", lambda d, l:
                          dict(headline="x", lead="y",
                               paragraphs=[dict(text="Unsourced claim",
                                                claim_keys=["not-present"])]))

    def test_rights_untrusted_inputs_and_conflicts(self):
        unauthorized = document("blocked", "en", "blocked")
        unauthorized["rights"]["ai_processing"] = "unknown"
        with self.assertRaisesRegex(ValueError, "permission"):
            self.ei.ingest([unauthorized])
        self.assertEqual(len(self.ei.dossier(self.event_id)["documents"]), 2)
        contradicted = document("third", "en", "independent", relation="contradicts")
        self.ei.ingest([contradicted])
        evidence = self.ei.dossier(self.event_id)["claims"][0]["evidence"]
        self.assertIn("contradicts", [e["relation"] for e in evidence])
        self.assertEqual(self.ei.content_pool()["articles"], [])
        first_draft = self.ei.draft(self.event_id, "de", writer)
        supportive_id = validate_document(self.docs[0])["document_id"]
        contrary_id = validate_document(contradicted)["document_id"]
        with self.assertRaisesRegex(ValueError, "disputed claims"):
            self.ei.approve(self.event_id, "de", reviewer="Editor",
                            expected_draft_digest=first_draft["draft_digest"],
                            checked_claim_sources={"vote": [supportive_id]})
        def with_disclosure(dossier, language):
            article = writer(dossier, language)
            article["uncertainties"] = ["Eine weitere Quelle widerspricht dieser Darstellung."]
            return article
        disclosed = self.ei.draft(self.event_id, "de", with_disclosure)
        published = self.ei.approve(
            self.event_id, "de", reviewer="Editor",
            expected_draft_digest=disclosed["draft_digest"],
            checked_claim_sources={"vote": [supportive_id, contrary_id]})
        self.assertEqual(published["claim_status"]["vote"], "disputed_with_disclosure")
        self.assertEqual(len(self.ei.content_pool()["articles"][0]["source_references"]), 2)
        secondary = document("secondary", "en", "ai-bulletin")
        secondary["origin_type"] = "ai_secondary"
        self.ei.ingest([secondary])
        self.assertEqual(self.ei.dossier(self.event_id)["independent_original_works"], 2)
        self.assertEqual(self.ei.content_pool()["articles"], [])  # new evidence invalidates old approval


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not set")
class PostgresEditorialIntelligenceTests(unittest.TestCase):
    """Runs against PostgreSQL 16 in the existing CI matrix; never needs secrets."""

    def test_schema_jobs_and_published_pool(self):
        from prismunfold.storage_pg import PostgresStore
        store = PostgresStore(os.environ["TEST_DATABASE_URL"])
        try:
            ei = EditorialIntelligence(store)
            doc = document("pg-fixture", "de", "pg-work-" + uuid4().hex,
                           event_key="ei-pg-test-" + uuid4().hex)
            event_id = ei.ingest([doc])[0]
            self.assertGreaterEqual(store.schema_version(), 3)
            self.assertEqual(ei.dossier(event_id)["independent_original_works"], 1)
            job = ei.plan_research(event_id)
            leased = ei.repo.lease(job["id"], worker="pg-test")
            self.assertEqual(leased["state"], "leased")
            self.assertIsNone(ei.repo.lease(job["id"], worker="second"))
            ei.repo.finish(job["id"], leased["lease_id"], success=True)
            self.assertEqual(ei.repo.get(f"job|{job['id']}")["state"], "completed")
            self.assertEqual(ei.content_pool()["articles"], [])
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
