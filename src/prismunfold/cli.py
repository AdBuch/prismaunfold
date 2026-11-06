"""Command line: `prismunfold run [--fixtures DIR] [--now ISO]`."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .ingest import fetch_feed
from .models import Source
from .pipeline import load_catalog, load_config, run
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prismunfold", description="Build one news edition.")
    sub = parser.add_subparsers(dest="command", required=True)
    run_cmd = sub.add_parser("run", help="ingest, build and render one edition")
    run_cmd.add_argument("--config", default="config/config.json")
    run_cmd.add_argument("--catalog", help="override catalog_path from the config")
    run_cmd.add_argument("--fixtures", help="read DIR/<source-id>.xml instead of the network")
    run_cmd.add_argument("--now", help="ISO 8601 time to build for (default: current time)")
    run_cmd.add_argument("--db", help="override db_path from the config")
    run_cmd.add_argument("--site", help="override site_dir from the config")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
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


if __name__ == "__main__":
    raise SystemExit(main())
