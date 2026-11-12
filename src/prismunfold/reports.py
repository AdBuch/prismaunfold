"""Read and check the reports written by collector agents.

A report is untrusted input: an agent may ignore the schema, invent fields or leave
out sources. Nothing here opens a cited URL; that check is a separate, later step.
What this module guarantees is structural: every sentence that survives carries at
least one well-formed http(s) source URL (Q-1, FR-5).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .models import Story, StorySentence, StorySource
from .normalize import canonical_url, sha1_id, strip_html, title_key

SCHEMA_VERSION = 1
AGENT_NAMES = {
    "codex": "Codex",
    "claude": "Claude Code",
    "vibe": "Mistral Vibe",
    "goose": "goose",
}
MAX_SENTENCES = 40
MAX_TEXT = 600
EDITION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z_-]{0,39}$")


class ReportError(ValueError):
    """The report cannot be used at all."""


def slugify(text: str, limit: int = 60) -> str:
    return title_key(text).replace(" ", "-")[:limit].strip("-") or "untitled"


def _text(raw: dict, key: str, limit: int = MAX_TEXT) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReportError(f"missing or empty field {key!r}")
    return strip_html(value)[:limit]


def _url(value: object) -> str | None:
    """Return the canonical form of a usable http(s) URL, else None."""
    if not isinstance(value, str):
        return None
    parts = urlsplit(value.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname or "." not in parts.hostname:
        return None
    return canonical_url(value)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ReportError("created_at must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReportError(f"created_at is not an ISO date-time: {value!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_report(
    raw: object, expected_agent: str | None = None, expected_edition: str | None = None
) -> tuple[Story, list[str]]:
    """Turn one raw report into a Story. Return the story and a list of problems found.

    Raises ReportError when nothing usable is left.
    """
    if not isinstance(raw, dict):
        raise ReportError("report is not a JSON object")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ReportError(f"unsupported schema_version {raw.get('schema_version')!r}")
    agent = raw.get("agent")
    if agent not in AGENT_NAMES:
        raise ReportError(f"unknown agent {agent!r}")
    if expected_agent and agent != expected_agent:
        raise ReportError(f"report claims agent {agent!r} but was written by {expected_agent!r}")

    problems: list[str] = []
    topic = _text(raw, "topic", 200)
    language = _text(raw, "language", 12).lower()
    edition = _text(raw, "edition", 40)
    if not EDITION_RE.match(edition):  # the edition becomes a file name
        raise ReportError(f"edition {edition!r} is not a plain identifier")
    if expected_edition and edition != expected_edition:
        raise ReportError(f"report claims edition {edition!r} but lies in {expected_edition!r}")
    headline = _text(raw, "headline", 200)
    created_at = _timestamp(raw.get("created_at"))
    model = raw.get("model") if isinstance(raw.get("model"), str) and raw["model"].strip() else "unknown"

    sources: dict[str, StorySource] = {}
    for item in raw.get("sources") or []:
        url = _url(item.get("url")) if isinstance(item, dict) else None
        if url is None:
            problems.append("dropped a source without a usable URL")
            continue
        published = item.get("published_at")
        sources[url] = StorySource(
            url=url,
            title=strip_html(str(item.get("title") or ""))[:300],
            publisher=strip_html(str(item.get("publisher") or ""))[:120] or urlsplit(url).hostname or "",
            published_at=published if isinstance(published, str) else None,
            language=item.get("language") if isinstance(item.get("language"), str) else None,
        )

    sentences: list[StorySentence] = []
    raw_sentences = raw.get("sentences")
    if not isinstance(raw_sentences, list):
        raise ReportError("sentences must be a list")
    if len(raw_sentences) > MAX_SENTENCES:
        problems.append(f"report has {len(raw_sentences)} sentences, kept the first {MAX_SENTENCES}")
    for position, item in enumerate(raw_sentences[:MAX_SENTENCES], start=1):
        text = strip_html(item.get("text")) if isinstance(item, dict) and isinstance(item.get("text"), str) else ""
        urls = [u for u in map(_url, item.get("source_urls") or [])] if isinstance(item, dict) else []
        urls = list(dict.fromkeys(u for u in urls if u))
        if not text:
            problems.append(f"sentence {position}: empty, dropped")
            continue
        if not urls:
            problems.append(f"sentence {position}: no usable source URL, dropped")
            continue
        for url in urls:  # a cited URL missing from the source list still has to be shown
            if url not in sources:
                sources[url] = StorySource(url=url, title="", publisher=urlsplit(url).hostname or "")
                problems.append(f"sentence {position}: cites {url}, which is not in the source list")
        sentences.append(StorySentence(text[:MAX_TEXT], tuple(urls)))

    nothing_new = raw.get("nothing_new") is True
    if not sentences and not nothing_new:
        raise ReportError("no sentence with a usable source is left")

    cited = {u for s in sentences for u in s.source_urls}
    uncertainties = tuple(
        strip_html(u)[:MAX_TEXT] for u in raw.get("uncertainties") or [] if isinstance(u, str) and u.strip()
    )
    publishers = {sources[u].publisher for u in cited}
    if sentences and len(publishers) == 1:
        uncertainties += ("All sentences rest on a single publisher.",)

    topic_slug = slugify(topic)
    story_id = sha1_id(agent, topic_slug, language, edition)
    story = Story(
        id=story_id,
        slug=f"{slugify(headline)}-{story_id[:8]}",
        agent=agent,
        model=model.strip()[:80],
        topic=topic,
        topic_slug=topic_slug,
        language=language,
        edition=edition,
        created_at=created_at,
        headline=headline,
        sentences=tuple(sentences),
        sources=tuple(s for u, s in sources.items() if u in cited),
        uncertainties=uncertainties,
        nothing_new=nothing_new,
    )
    return story, problems


def load_reports(out_dir: str | Path, edition: str | None = None) -> list[tuple[Path, Story | None, list[str]]]:
    """Read out_dir/<edition>/<agent>/<topic>.json. A report that fails has story None."""
    root = Path(out_dir)
    pattern = f"{edition}/*/*.json" if edition else "*/*/*.json"
    results: list[tuple[Path, Story | None, list[str]]] = []
    for path in sorted(root.glob(pattern)):
        agent_dir = path.parent.name
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            story, problems = parse_report(
                raw, expected_agent=agent_dir, expected_edition=path.parent.parent.name
            )
        except (ReportError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            results.append((path, None, [f"rejected: {exc}"]))
            continue
        results.append((path, story, problems))
    return results
