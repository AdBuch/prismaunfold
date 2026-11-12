"""Command line.

    prismunfold run      build one feed-based edition (ingest, cluster, summarise, export JSON)
    prismunfold context  write the archive's prior coverage of a topic for the collector agents
    prismunfold reports  check the collector agents' reports, store, index and export them
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .archive import prior_coverage
from .export import export_stories
from .ingest import fetch_feed
from .models import Source
from .pipeline import load_catalog, load_config, run
from .reports import load_reports
from .storage import Store


def _parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _fixture_fetcher(directory: str):
    def fetch(source: Source) -> bytes:
        return (Path(directory) / f"{source.id}.xml").read_bytes()

    return fetch


def _run(args: argparse.Namespace, cfg: dict) -> int:
    catalog = load_catalog(args.catalog or cfg["catalog_path"])
    fetch = _fixture_fetcher(args.fixtures) if args.fixtures else fetch_feed
    store = Store(args.db or cfg["db_path"])
    try:
        report = run(cfg, catalog, _parse_now(args.now), fetch, store, args.site or cfg["site_dir"])
    finally:
        store.close()

    print(
        f"fetched={report.fetched} kept={report.kept} events={report.events} "
        f"dropped_sentences={report.dropped_sentences} editions={','.join(report.editions) or 'none'}"
    )
    for title, reason in report.dropped:
        print(f"  dropped: {title!r} ({reason})")
    for error in report.errors:
        print(f"  error: {error}")
    return 0


def _context(args: argparse.Namespace, cfg: dict) -> int:
    store = Store(args.db or cfg["db_path"])
    try:
        text = prior_coverage(store, args.topic, args.language, args.limit)
    finally:
        store.close()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"context: {'no prior coverage' if not text else f'{len(text)} characters'} -> {out}")
    return 0


def _reports(args: argparse.Namespace, cfg: dict) -> int:
    """Exit code 1 when at least one report was rejected, so a scheduler notices."""
    results = load_reports(args.reports_dir, args.edition)
    store = Store(args.db or cfg["db_path"])
    accepted = rejected = 0
    try:
        for path, story, problems in results:
            if story is None:
                rejected += 1
            else:
                accepted += 1
                store.save_story(story)
            for problem in problems:
                print(f"  {path}: {problem}")
        store.commit()
        written = export_stories(store, args.site or cfg["site_dir"])
    finally:
        store.close()
    print(f"reports: accepted={accepted} rejected={rejected} files_written={len(written)}")
    return 1 if rejected else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prismunfold", description="Build PrismUnfold editions.")
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default="config/config.json")
    common.add_argument("--db", help="override db_path from the config")
    common.add_argument("--site", help="override site_dir from the config")

    run_cmd = sub.add_parser("run", parents=[common], help="ingest feeds and export one edition")
    run_cmd.add_argument("--catalog", help="override catalog_path from the config")
    run_cmd.add_argument("--fixtures", help="read DIR/<source-id>.xml instead of the network")
    run_cmd.add_argument("--now", help="ISO 8601 time to build for (default: current time)")

    ctx_cmd = sub.add_parser("context", parents=[common], help="write prior coverage of a topic")
    ctx_cmd.add_argument("--topic", required=True)
    ctx_cmd.add_argument("--language")
    ctx_cmd.add_argument("--limit", type=int, default=5)
    ctx_cmd.add_argument("--out", required=True, help="markdown file to write (empty if nothing found)")

    rep_cmd = sub.add_parser("reports", parents=[common], help="check, store and export agent reports")
    rep_cmd.add_argument("--reports-dir", default="collectors/out")
    rep_cmd.add_argument("--edition", help="only this edition (default: all found)")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    return {"run": _run, "context": _context, "reports": _reports}[args.command](args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
