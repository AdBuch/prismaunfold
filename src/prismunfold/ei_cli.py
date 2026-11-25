"""Opt-in operator CLI for Editorial Intelligence; never part of live scheduling.

Example:
  PYTHONPATH=src python -m prismunfold.ei_cli --db /tmp/ei.sqlite ingest --file docs.json
  PYTHONPATH=src python -m prismunfold.ei_cli --db /tmp/ei.sqlite dossier --event evt-...
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .intelligence import EditorialIntelligence
from .storage import open_store


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in editorial-intelligence operator commands")
    parser.add_argument("--db", default=os.getenv("DATABASE_URL", "data/prismunfold.sqlite3"))
    sub = parser.add_subparsers(dest="action", required=True)

    ingest = sub.add_parser("ingest", help="import permission-reviewed structured source documents")
    ingest.add_argument("--file", required=True, help="JSON array of structured source documents")
    dossier = sub.add_parser("dossier", help="inspect the internal event evidence dossier")
    dossier.add_argument("--event", required=True)
    research = sub.add_parser("plan-research", help="persist one targeted research job")
    research.add_argument("--event", required=True)
    run = sub.add_parser("run-research", help="consume a provided provider result; no network calls")
    run.add_argument("--job", required=True)
    run.add_argument("--file", required=True, help="JSON array of research source documents")
    jobs = sub.add_parser("jobs", help="display persistent job states")
    jobs.add_argument("--event", help="optional event ID")
    draft = sub.add_parser("draft", help="validate structured writer result")
    draft.add_argument("--event", required=True)
    draft.add_argument("--language", required=True)
    draft.add_argument("--file", required=True, help="JSON writer result")
    approve = sub.add_parser("approve", help="sign off exact draft claim-to-document links")
    approve.add_argument("--event", required=True)
    approve.add_argument("--language", required=True)
    approve.add_argument("--reviewer", required=True, help="named human editor")
    approve.add_argument("--draft-digest", required=True,
                         help="SHA-256 draft_digest shown to and inspected by the editor")
    approve.add_argument("--checked-file", required=True,
                         help="JSON object claim_key -> original source document IDs reviewed")
    export = sub.add_parser("export", help="write the published content-pool contract")
    export.add_argument("--site", default="site")
    edition = sub.add_parser("edition", help="compose a cached profile-specific article selection")
    edition.add_argument("--profile", required=True,
                         help="JSON object with languages, topics, reading_depth")

    args = parser.parse_args(argv)
    store = open_store(args.db)
    try:
        ei = EditorialIntelligence(store)
        if args.action == "ingest":
            value = ei.ingest(load_json(args.file))
        elif args.action == "dossier":
            value = ei.dossier(args.event)
        elif args.action == "plan-research":
            value = ei.plan_research(args.event)
        elif args.action == "run-research":
            documents = load_json(args.file)
            value = ei.run_research(args.job, lambda job, dossier: documents)
        elif args.action == "jobs":
            value = ei.repo.list("job", args.event)
        elif args.action == "draft":
            result = load_json(args.file)
            value = ei.draft(args.event, args.language, lambda dossier, language: result)
        elif args.action == "approve":
            value = ei.approve(args.event, args.language, reviewer=args.reviewer,
                               expected_draft_digest=args.draft_digest,
                               checked_claim_sources=load_json(args.checked_file))
        elif args.action == "export":
            value = {"written": ei.export_pool(args.site)}
        elif args.action == "edition":
            value = ei.reader_edition(load_json(args.profile))
        else:
            parser.error("unknown action")
        print(json.dumps(value, indent=2, ensure_ascii=False))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
