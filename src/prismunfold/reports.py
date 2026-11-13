"""Read and check the reports written by collector agents.

A report is untrusted input. An agent may ignore the schema, write the wrong types,
invent fields, produce megabytes of text or try to steer the pipeline through file
names. This module turns a report into a `Story` or rejects it; it never raises
anything but `ReportError` for bad content, and one bad report never stops the others.

What it guarantees is structural only: every sentence that survives carries at least
one well-formed public http(s) URL. Whether that URL exists, and whether the page
supports the sentence, are separate questions answered in `linkcheck` and
`verification`.
"""

from __future__ import annotations

import ipaddress
import json
import re
import stat
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .models import Story, StorySentence, StorySource
from .normalize import canonical_url, sha1_id, strip_html, title_key

SCHEMA_VERSION = 1
COLLECTOR_AGENTS = {
    "codex": "Codex",
    "claude": "Claude Code",
    "vibe": "Mistral Vibe",
    "goose": "goose",
}
# "desk" is the pipeline's own feed desk. It never arrives as a report file.
AGENT_NAMES = {**COLLECTOR_AGENTS, "desk": "PrismUnfold feed desk"}

MAX_REPORT_BYTES = 256 * 1024
MAX_SENTENCES = 40
MAX_SOURCES = 60
MAX_URLS_PER_SENTENCE = 8
MAX_NOTES = 12
MAX_TEXT = 600
MAX_URL = 2000
MAX_AGE = timedelta(days=7)
MAX_FUTURE = timedelta(minutes=15)
EDITION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z_-]{0,39}$")
FILE_STEM_RE = re.compile(r"^[\w-]{1,80}$")
LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8})?$")


class ReportError(ValueError):
    """The report cannot be used at all."""


def slugify(text: str, limit: int = 60) -> str:
    return title_key(text).replace(" ", "-")[:limit].strip("-") or "untitled"


def clean_text(value: object, limit: int = MAX_TEXT) -> str:
    """Plain text from an untrusted value: no markup, no control characters, bounded length.

    Returns "" for anything that is not a string.
    """
    if not isinstance(value, str):
        return ""
    text = "".join(" " if unicodedata.category(ch)[0] == "C" else ch for ch in value[: limit * 4])
    return strip_html(text)[:limit].strip()


def _required_text(raw: dict, key: str, limit: int = MAX_TEXT) -> str:
    text = clean_text(raw.get(key), limit)
    if not text:
        raise ReportError(f"field {key!r} is missing, empty or not a string")
    return text


def _list(raw: dict, key: str, problems: list[str], required: bool = False) -> list:
    value = raw.get(key)
    if isinstance(value, list):
        return value
    if required:
        raise ReportError(f"field {key!r} must be a list")
    if value is not None:
        problems.append(f"field {key!r} is not a list, ignored")
    return []


def public_url(value: object) -> str | None:
    """Canonical form of a usable public http(s) URL, else None.

    Rejects other schemes, credentials in the URL, bare IP addresses, hosts without a
    dot, whitespace and control characters, and overlong URLs.
    """
    if not isinstance(value, str) or not 0 < len(value) <= MAX_URL:
        return None
    value = value.strip()
    if any(ch.isspace() or unicodedata.category(ch)[0] == "C" for ch in value):
        return None
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        _ = parts.port  # raises ValueError for a malformed port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or parts.username or parts.password:
        return None
    if "." not in host or host.endswith("."):
        return None
    try:
        ipaddress.ip_address(host)
        return None  # a real publisher has a name; literal addresses are not sources
    except ValueError:
        pass
    return canonical_url(value)


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ReportError(f"{field} must be an ISO date-time string")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReportError(f"{field} is not an ISO date-time: {value[:40]!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _source_date(value: object, now: datetime | None) -> str | None:
    """A source's publication date as given, or None if absent, unparsable or in the future."""
    if not isinstance(value, str):
        return None
    try:
        parsed = _timestamp(value, "published_at")
    except ReportError:
        return None
    if now is not None and parsed > now + timedelta(days=1):
        return None
    return parsed.isoformat()


def parse_report(
    raw: object,
    expected_agent: str | None = None,
    expected_edition: str | None = None,
    now: datetime | None = None,
) -> tuple[Story, list[str]]:
    """Turn one raw report into a Story. Return the story and a list of problems found.

    `now` enables the age check: a report dated in the future or older than a week is
    rejected. Raises ReportError when nothing usable is left.
    """
    if not isinstance(raw, dict):
        raise ReportError("report is not a JSON object")
    version = raw.get("schema_version")
    if isinstance(version, bool) or version != SCHEMA_VERSION:
        raise ReportError(f"unsupported schema_version {str(version)[:20]!r}")
    agent = raw.get("agent")
    if not isinstance(agent, str) or agent not in COLLECTOR_AGENTS:
        raise ReportError(f"unknown agent {str(agent)[:20]!r}")
    if expected_agent and agent != expected_agent:
        raise ReportError(f"report claims agent {agent!r} but was written by {expected_agent!r}")

    problems: list[str] = []
    topic = _required_text(raw, "topic", 200)
    language = _required_text(raw, "language", 12).lower()
    if not LANGUAGE_RE.match(language):
        raise ReportError(f"language {language!r} is not a language tag")
    edition = _required_text(raw, "edition", 40)
    if not EDITION_RE.match(edition):  # the edition becomes a file name
        raise ReportError(f"edition {edition!r} is not a plain identifier")
    if expected_edition and edition != expected_edition:
        raise ReportError(f"report claims edition {edition!r} but lies in {expected_edition!r}")
    headline = _required_text(raw, "headline", 200)
    created_at = _timestamp(raw.get("created_at"), "created_at")
    if now is not None:
        if created_at > now + MAX_FUTURE:
            raise ReportError("created_at lies in the future")
        if created_at < now - MAX_AGE:
            raise ReportError("created_at is more than a week old")
    model = clean_text(raw.get("model"), 80) or "unknown"

    sources: dict[str, StorySource] = {}
    raw_sources = _list(raw, "sources", problems)
    if len(raw_sources) > MAX_SOURCES:
        problems.append(f"report lists {len(raw_sources)} sources, kept the first {MAX_SOURCES}")
    for item in raw_sources[:MAX_SOURCES]:
        url = public_url(item.get("url")) if isinstance(item, dict) else None
        if url is None:
            problems.append("dropped a source without a usable URL")
            continue
        language_tag = clean_text(item.get("language"), 12).lower()
        sources[url] = StorySource(
            url=url,
            title=clean_text(item.get("title"), 300),
            publisher=clean_text(item.get("publisher"), 120) or urlsplit(url).hostname or "",
            published_at=_source_date(item.get("published_at"), now),
            language=language_tag if LANGUAGE_RE.match(language_tag) else None,
        )

    sentences: list[StorySentence] = []
    raw_sentences = _list(raw, "sentences", problems, required=True)
    if len(raw_sentences) > MAX_SENTENCES:
        problems.append(f"report has {len(raw_sentences)} sentences, kept the first {MAX_SENTENCES}")
    for position, item in enumerate(raw_sentences[:MAX_SENTENCES], start=1):
        if not isinstance(item, dict):
            problems.append(f"sentence {position}: not an object, dropped")
            continue
        text = clean_text(item.get("text"))
        cited = item.get("source_urls")
        cited = cited[:MAX_URLS_PER_SENTENCE] if isinstance(cited, list) else []
        urls = list(dict.fromkeys(u for u in map(public_url, cited) if u))
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
        sentences.append(StorySentence(text, tuple(urls)))

    nothing_new = raw.get("nothing_new") is True
    if not sentences and not nothing_new:
        raise ReportError("no sentence with a usable source is left")

    def notes(key: str) -> tuple[str, ...]:
        items = (clean_text(n) for n in _list(raw, key, problems)[:MAX_NOTES])
        return tuple(n for n in items if n)

    cited_urls = {u for s in sentences for u in s.source_urls}
    topic_slug = slugify(topic)
    story_id = sha1_id(agent, topic_slug, language, edition)
    story = Story(
        id=story_id,
        slug=f"{slugify(headline)}-{story_id[:8]}",
        agent=agent,
        model=model,
        topic=topic,
        topic_slug=topic_slug,
        language=language,
        edition=edition,
        created_at=created_at,
        headline=headline,
        sentences=tuple(sentences),
        sources=tuple(s for u, s in sources.items() if u in cited_urls),
        uncertainties=notes("uncertainties"),
        nothing_new=nothing_new,
        disputes=notes("disputes"),
    )
    return story, problems


def _reject_constant(name: str) -> float:
    raise ValueError(f"non-finite number {name} is not valid JSON")


def read_report_file(path: Path) -> object:
    """Load one report file defensively. Raises ReportError for anything unsafe or unreadable."""
    if not FILE_STEM_RE.match(path.stem):
        raise ReportError("file name is not a plain identifier")
    try:
        info = path.lstat()
    except OSError as exc:
        raise ReportError(f"cannot read file: {exc.strerror}") from exc
    if not stat.S_ISREG(info.st_mode):  # no symlinks, devices or directories
        raise ReportError("not a regular file")
    if info.st_size > MAX_REPORT_BYTES:
        raise ReportError(f"file is larger than {MAX_REPORT_BYTES} bytes")
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_REPORT_BYTES + 1)
        if len(data) > MAX_REPORT_BYTES:
            raise ReportError(f"file is larger than {MAX_REPORT_BYTES} bytes")
        return json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ReportError("JSON is nested too deeply") from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ReportError(f"not readable as UTF-8 JSON: {str(exc)[:120]}") from exc


def load_reports(
    out_dir: str | Path, edition: str | None = None, now: datetime | None = None
) -> list[tuple[Path, Story | None, list[str]]]:
    """Read out_dir/<edition>/<agent>/<topic>.json. A report that fails has story None.

    The edition and agent are taken from the directory names, which the pipeline and
    the container setup control, and must match what the report claims.
    """
    root = Path(out_dir)
    if edition is not None and not EDITION_RE.match(edition):
        return []
    pattern = f"{edition}/*/*.json" if edition else "*/*/*.json"
    results: list[tuple[Path, Story | None, list[str]]] = []
    for path in sorted(root.glob(pattern)):
        try:
            raw = read_report_file(path)
            story, problems = parse_report(
                raw,
                expected_agent=path.parent.name,
                expected_edition=path.parent.parent.name,
                now=now,
            )
        except ReportError as exc:
            results.append((path, None, [f"rejected: {exc}"]))
        except Exception as exc:  # a parser bug must not take the other reports down with it
            results.append((path, None, [f"rejected: unexpected {type(exc).__name__}"]))
        else:
            results.append((path, story, problems))
    return results
