"""Import daily ChatGPT Morgenbriefing JSON as an additional PrismUnfold source.

Usage: python3 tools/import_morgenbriefing.py data/morgenbriefing/2026-11-26.json
Writes normalized JSON to stdout. Does not overwrite other feeds or claim verification.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


def normalize(payload):
    day = payload.get("date")
    date.fromisoformat(day)
    if not isinstance(payload.get("sections"), list):
        raise ValueError("sections must be an array")
    edition_id = f"morgenbriefing:{day}"
    stories = []
    for section_index, section in enumerate(payload["sections"]):
        if not isinstance(section, dict):
            raise ValueError("section must be an object")
        for item_index, item in enumerate(section.get("items", [])):
            if not isinstance(item, dict):
                raise ValueError("section item must be an object")
            urls = item.get("source_urls", [])
            if not isinstance(urls, list):
                raise ValueError("source_urls must be an array")
            for url in urls:
                if not isinstance(url, str) or urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
                    raise ValueError(f"invalid source URL: {url!r}")
            stories.append({
                "id": f"{edition_id}:{section_index}:{item_index}",
                "title": item.get("title") or item.get("headline") or "Ohne Titel",
                "body": item.get("body") or item.get("text") or item.get("summary") or "",
                "section": section.get("title", "Unsortiert"),
                "source_urls": urls,
                "source_type": "ai_curated_secondary",
                "origin": "chatgpt_morgenbriefing",
                "requires_independent_verification": True,
                "edition_date": day,
            })
    return {
        "id": edition_id,
        "date": day,
        "lead": payload.get("lead", ""),
        "stories": stories,
        "deep_dive": payload.get("deep_dive"),
        "good_news": payload.get("good_news"),
        "random_fact": payload.get("random_fact"),
        "outlook": payload.get("outlook"),
        "provenance": {
            "origin": "chatgpt_morgenbriefing",
            "source_type": "ai_curated_secondary",
            "generated_at": payload.get("generated_at"),
            "timezone": payload.get("timezone", "Europe/Zurich"),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        print(json.dumps(normalize(payload), ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
