"""prism-data import: real-shape fixture, errors, revisions, review, backfill, scheduling."""
import copy
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from prismunfold import bulletin
from prismunfold.bulletin import (BulletinError, due, fetch, import_day, import_document, import_range,
                                  merge_editions, publication_basis, review_bulletin, validate)
from prismunfold.editorial import export_editorial
from prismunfold.storage import open_store

FIXTURE = Path(__file__).parent / "fixtures" / "prism-data" / "2026-11-25.json"
DAY = "2026-11-25"
AFTER_SEVEN = datetime.fromisoformat(DAY + "T07:05:00+01:00")


def document(**changes):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw.update(changes)
    return raw


class Env:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.store = open_store(self.dir / "db")
        self.secret = self.dir / "token"
        self.secret.write_text("github_pat_fixture_0123456789")

    def close(self):
        self.store.close()
        self.tmp.cleanup()


class FixtureTests(unittest.TestCase):
    """The real 25 November test export: schema 1.1, test_import_unverified, null fields."""

    def test_real_shape_is_accepted_and_metadata_preserved(self):
        entry = validate(document(), DAY)
        self.assertEqual(entry["status"], "test_import_unverified")
        self.assertEqual(entry["schema_version"], "1.1")
        self.assertEqual(entry["editorial_cutoff"], "")
        self.assertEqual(len(entry["rubrics"]), 9)
        self.assertEqual(len(entry["articles"]), 10)  # nine rubric items + Good News
        self.assertEqual(entry["magazine"]["sources"][0]["publisher"], "EUR-Lex")
        self.assertEqual(entry["magazine"]["sources"][0]["published_at"], "")  # null stays empty, never invented
        self.assertEqual(entry["random_article"]["kind"], "random")
        self.assertEqual(len(entry["outlook"]), 4)
        self.assertTrue(all(a["limitations"] == ["no_original_sources"] for a in entry["articles"]))
        self.assertTrue(entry["articles"][0]["uncertainties"])
        self.assertIn("Testexport", entry["note"])

    def test_unverified_bulletin_is_stored_but_not_published(self):
        env = Env()
        try:
            outcome = import_document(env.store, DAY, FIXTURE.read_bytes())
            self.assertEqual(outcome, "imported")
            exported = json.loads(Path(export_editorial(env.store, env.dir)).read_text())
            self.assertEqual(exported, [])
            stored = env.store.get_edition(bulletin.EDITION_PREFIX + DAY)
            self.assertEqual(stored["status"], "test_import_unverified")  # never rewritten
            record, = env.store.list_contributions(source_key=bulletin.SOURCE_KEY + DAY)
            self.assertEqual(record["state"], "review_required")
            self.assertEqual(record["raw"]["publication_status"], "test_import_unverified")
            self.assertEqual(record["origin_type"], "ai_secondary")
        finally:
            env.close()

    def test_explicit_approval_is_bound_to_content_and_labelled(self):
        env = Env()
        try:
            import_document(env.store, DAY, FIXTURE.read_bytes())
            with self.assertRaises(ValueError):
                review_bulletin(env.store, DAY, "approved", "  ")
            review_bulletin(env.store, DAY, "approved", "Adrian", "Testlauf für die Darstellung")
            exported = json.loads(Path(export_editorial(env.store, env.dir)).read_text())
            self.assertEqual(exported[0]["bulletin"]["publication_basis"], "manually_approved")
            self.assertEqual(exported[0]["bulletin"]["upstream_status"], "test_import_unverified")
            self.assertIn("Manuell", exported[0]["disclosure"])
            self.assertEqual(exported[0]["articles"][0]["provenance"]["publication_basis"], "manually_approved")
            daily = json.loads((env.dir / "api/v1/daily" / f"{DAY}.json").read_text())
            self.assertEqual(daily["contributors"], [{"provider": "prism-data", "originType": "ai_secondary"}])
            # A corrected revision needs a new approval.
            revised = document(generated_at="2026-11-25T07:30:00+01:00")
            self.assertEqual(import_document(env.store, DAY, json.dumps(revised).encode()), "imported")
            self.assertIsNone(publication_basis(env.store.get_edition(bulletin.EDITION_PREFIX + DAY)))
        finally:
            env.close()

    def test_rejection_withholds_an_upstream_published_bulletin(self):
        env = Env()
        try:
            import_document(env.store, DAY, json.dumps(document(publication_status="published")).encode())
            self.assertEqual(len(json.loads(Path(export_editorial(env.store, env.dir)).read_text())), 1)
            review_bulletin(env.store, DAY, "rejected", "Adrian")
            self.assertEqual(json.loads(Path(export_editorial(env.store, env.dir)).read_text()), [])
        finally:
            env.close()


class StatusTests(unittest.TestCase):
    def test_publication_statuses(self):
        for status, public in (("published", True), ("final", True), ("draft", False),
                               ("unverified", False), ("test_import_unverified", False)):
            entry = dict(validate(document(publication_status=status), DAY), digest="x")
            self.assertEqual(bool(publication_basis(entry)), public, status)
        with self.assertRaisesRegex(BulletinError, "unknown bulletin publication_status"):
            validate(document(publication_status="live"), DAY)


class ErrorTests(unittest.TestCase):
    def setUp(self):
        self.env = Env()

    def tearDown(self):
        self.env.close()

    def run_import(self, fetcher):
        return import_day(self.env.store, self.env.secret, AFTER_SEVEN, fetcher=fetcher)

    def test_missing_bulletin_waits(self):
        self.assertEqual(self.run_import(lambda d, t: None), "waiting")

    def test_not_due_before_seven_zurich_including_dst(self):
        self.assertEqual(import_day(self.env.store, self.env.secret, datetime.fromisoformat(DAY + "T05:59:00+00:00"),
                                    fetcher=lambda *a: self.fail("fetched too early")), "not_due")
        # Summer time: 07:00 CEST = 05:00 UTC.
        self.assertTrue(due(datetime.fromisoformat("2026-07-01T05:00:00+00:00"))[0])
        self.assertFalse(due(datetime.fromisoformat("2026-07-01T04:59:00+00:00"))[0])
        # Winter time: 07:00 CET = 06:00 UTC; the DST switch day (29 March 2026) too.
        self.assertFalse(due(datetime.fromisoformat("2026-11-25T05:59:00+00:00"))[0])
        self.assertTrue(due(datetime.fromisoformat("2026-03-29T05:00:00+00:00"))[0])
        self.assertEqual(due(datetime.fromisoformat("2026-11-25T23:30:00+00:00"))[1], "2026-11-26")

    def test_malformed_json(self):
        with self.assertRaises(BulletinError) as ctx:
            self.run_import(lambda d, t: b'{"schema_version": ')
        self.assertEqual(ctx.exception.code, "invalid_json")

    def test_unsupported_schema(self):
        with self.assertRaises(BulletinError) as ctx:
            self.run_import(lambda d, t: json.dumps(document(schema_version="2.0")).encode())
        self.assertEqual(ctx.exception.code, "unsupported_schema")

    def test_size_limit(self):
        with self.assertRaises(BulletinError) as ctx:
            self.run_import(lambda d, t: b" " * (bulletin.MAX_BYTES + 1))
        self.assertEqual(ctx.exception.code, "too_large")

    def test_unreadable_secret(self):
        self.env.secret.write_text("bad token with spaces")
        with self.assertRaises(BulletinError) as ctx:
            self.run_import(lambda d, t: None)
        self.assertEqual(ctx.exception.code, "secret_unreadable")

    def test_auth_failure_and_outage_are_classified(self):
        def http(code):
            return HTTPError("https://api.github.com/", code, "", {}, BytesIO())
        cases = [([http(401)], "auth_failed"), ([http(404), http(404)], "auth_failed"),
                 ([http(503)], "github_unavailable"), ([http(302)], "github_unavailable"),
                 ([URLError("down")], "github_unavailable")]
        for effects, code in cases:
            with patch("prismunfold.bulletin.build_opener") as factory:
                factory.return_value.open = Mock(side_effect=effects)
                with self.assertRaises(BulletinError) as ctx:
                    fetch(DAY, "token_value")
                self.assertEqual(ctx.exception.code, code)
                self.assertNotIn("token_value", str(ctx.exception))

    def test_failure_does_not_touch_existing_publication(self):
        import_document(self.env.store, DAY, json.dumps(document(publication_status="published")).encode())
        with self.assertRaises(BulletinError):
            self.run_import(lambda d, t: b"{")
        self.assertEqual(self.env.store.get_edition(bulletin.EDITION_PREFIX + DAY)["status"], "published")


class RevisionTests(unittest.TestCase):
    def test_repeat_correction_older_and_interrupted(self):
        env = Env()
        try:
            first = json.dumps(document(publication_status="published")).encode()
            self.assertEqual(import_document(env.store, DAY, first), "imported")
            self.assertEqual(import_document(env.store, DAY, first), "unchanged")
            corrected = document(publication_status="published", generated_at="2026-11-25T08:00:00+01:00", lead="Korrektur.")
            self.assertEqual(import_document(env.store, DAY, json.dumps(corrected).encode()), "imported")
            older = document(publication_status="published", generated_at="2026-11-25T06:00:00+01:00", lead="Alt.")
            self.assertEqual(import_document(env.store, DAY, json.dumps(older).encode()), "older_revision")
            self.assertEqual(env.store.get_edition(bulletin.EDITION_PREFIX + DAY)["lead"], "Korrektur.")
            states = [c["state"] for c in env.store.list_contributions(source_key=bulletin.SOURCE_KEY + DAY)]
            self.assertEqual(sorted(states), ["superseded", "superseded", "validated"])

            # Interrupted import: the process dies after writing but before commit. The
            # transaction is rolled back, so the next run imports the revision again.
            newest = document(publication_status="published", generated_at="2026-11-25T09:00:00+01:00", lead="Neu.")
            data = json.dumps(newest).encode()
            env.store.db.commit()
            with patch.object(env.store, "commit", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    import_document(env.store, DAY, data)
            env.store.db.rollback()
            self.assertEqual(env.store.get_edition(bulletin.EDITION_PREFIX + DAY)["lead"], "Korrektur.")
            self.assertEqual(import_document(env.store, DAY, data), "imported")
        finally:
            env.close()

    def test_backfill_continues_after_a_failing_day(self):
        env = Env()
        try:
            def fetcher(day, token):
                if day == "2026-11-24":
                    raise BulletinError("github_unavailable", "down")
                if day == "2026-11-23":
                    return None
                return json.dumps(document(publication_status="published")).encode()
            results = import_range(env.store, env.secret, "2026-11-23", "2026-11-25", fetcher)
            self.assertEqual(results, {"2026-11-23": "waiting", "2026-11-24": "failed:github_unavailable",
                                       "2026-11-25": "imported"})
            with self.assertRaises(BulletinError):
                import_range(env.store, env.secret, "2026-11-25", "2026-11-01", fetcher)
        finally:
            env.close()

    def test_cli_import_from_local_file(self):
        from prismunfold.cli import main
        env = Env()
        try:
            env.store.close()
            code = main(["import-bulletin", "--db", str(env.dir / "db"), "--site", str(env.dir / "site"),
                         "--date", DAY, "--file", str(FIXTURE)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((env.dir / "site/api/v1/editorial/morgenbriefing.json").read_text()), [])
            code = main(["import-bulletin", "--db", str(env.dir / "db"), "--site", str(env.dir / "site"),
                         "--date", DAY, "--review", "approved", "--reviewer", "Adrian"])
            self.assertEqual(code, 0)
            self.assertEqual(len(json.loads((env.dir / "site/api/v1/editorial/morgenbriefing.json").read_text())), 1)
            env.store = open_store(env.dir / "db")
        finally:
            env.close()


class MigrationTests(unittest.TestCase):
    def test_existing_database_from_before_0_2_is_upgraded_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.sqlite3"
            old = sqlite3.connect(path)
            old.executescript("""
                CREATE TABLE editions (id TEXT PRIMARY KEY, language TEXT NOT NULL, built_at TEXT NOT NULL, data TEXT NOT NULL);
                INSERT INTO editions VALUES ('editorial|morgenbriefing|2026-11-24', 'de', '2026-11-24T06:00:00+00:00',
                  '{"date": "2026-11-24", "articles": [], "magazine": null, "warnings": [], "disclosure": "x"}');
            """)
            old.commit()
            old.close()
            store = open_store(path)
            try:
                self.assertEqual(store.schema_version(), 2)
                self.assertEqual(store.list_contributions(), [])
                self.assertEqual(store.get_edition("editorial|morgenbriefing|2026-11-24")["date"], "2026-11-24")
                exported = json.loads(Path(export_editorial(store, tmp)).read_text())
                self.assertEqual(exported[0]["date"], "2026-11-24")
            finally:
                store.close()
            store = open_store(path)  # reopening is a no-op
            store.close()


class MergeTests(unittest.TestCase):
    def test_bulletin_merges_into_authored_edition_with_provenance(self):
        incoming = dict(validate(document(publication_status="published"), DAY), digest="abc")
        authored = {"date": DAY, "articles": [copy.deepcopy(incoming["articles"][0]) | {"origin": "prismunfold"}],
                    "magazine": None, "warnings": [], "disclosure": "x"}
        edition, = merge_editions([authored], [incoming], [])
        self.assertEqual(edition["articles"][0]["coverage"][0]["provenance"]["provider"], "prism-data")
        self.assertEqual(edition["articles"][0]["coverage"][0]["duplicate_paragraphs_omitted"], 2)
        self.assertEqual(edition["magazine"]["origin"], "prism-data")


if __name__ == "__main__":
    unittest.main()
