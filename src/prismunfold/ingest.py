"""Feed fetching (robots-aware) and parsing of RSS 2.0 and Atom into Article objects."""

from __future__ import annotations

import datetime as dt
import email.utils
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from typing import Any

from .models import Article, Source
from .normalize import canonical_url, sha1_id, strip_html

AGENT_NAME = "PrismUnfold-MVP"
USER_AGENT = f"{AGENT_NAME}/0.1 (feed reader; respects robots.txt)"
TIMEOUT_SECONDS = 15
MAX_FEED_BYTES = 5_000_000
EXCERPT_CHARS = 600
AI_CATEGORIES = frozenset({"ai-generated", "ai-assisted", "ki-generiert", "ki-unterstuetzt"})

ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"

_robots: dict[str, Any] = {}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        data = resp.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError(f"response larger than {MAX_FEED_BYTES} bytes: {url}")
    return data


def allowed_by_robots(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in _robots:
        parser = urllib.robotparser.RobotFileParser()
        try:
            parser.parse(_get(origin + "/robots.txt").decode("utf-8", "replace").splitlines())
            _robots[origin] = parser
        except urllib.error.HTTPError as exc:
            # No robots.txt means no restrictions; any other HTTP error is treated as "not allowed".
            _robots[origin] = None if exc.code == 404 else False
        except Exception:
            _robots[origin] = False
    parser = _robots[origin]
    if parser is None:
        return True
    if parser is False:
        return False
    return parser.can_fetch(AGENT_NAME, url)


def fetch_feed(source: Source) -> bytes:
    if not allowed_by_robots(source.feed_url):
        raise PermissionError(f"robots.txt disallows {source.feed_url}")
    return _get(source.feed_url)


def parse_date(value: str | None) -> dt.datetime | None:
    if not value or not value.strip():
        return None
    value = value.strip()
    try:
        parsed: dt.datetime | None = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is None:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _make_article(
    source: Source,
    url: str,
    title: str | None,
    published: dt.datetime | None,
    description: str | None,
    body: str | None,
    image_url: str | None,
    image_credit: str | None,
    categories: list[str],
) -> Article | None:
    title_text = strip_html(title)
    if not title_text or published is None or not url.startswith(("http://", "https://")):
        return None
    image_ok = bool(image_url and image_url.startswith(("http://", "https://")))
    canon = canonical_url(url)
    excerpt = "" if source.rights == "link_only" else strip_html(description)[:EXCERPT_CHARS]
    body_text = strip_html(body) if (body and source.rights == "full_text") else None
    ai = bool({c.strip().lower() for c in categories} & AI_CATEGORIES)
    return Article(
        id=sha1_id(canon),
        source_id=source.id,
        url=url,
        canonical_url=canon,
        title=title_text,
        published_at=published,
        language=source.language,
        excerpt=excerpt,
        body_text=body_text,
        image_url=image_url if image_ok else None,
        # Provenance: the image is credited to the article page it came from.
        image_source_url=url if image_ok else None,
        image_credit=(image_credit or source.name) if image_ok else None,
        ai_disclosed=ai,
        topics=tuple(source.topics),
    )


def _rss_item(item: ET.Element, source: Source) -> Article | None:
    image_url = None
    image_credit = None
    for enc in item.findall("enclosure"):
        if (enc.get("type") or "").startswith("image/"):
            image_url = enc.get("url")
            break
    if image_url is None:
        for media in item.findall(MEDIA + "content"):
            if media.get("medium") == "image" or (media.get("type") or "").startswith("image/"):
                image_url = media.get("url")
                credit_el = media.find(MEDIA + "credit")
                image_credit = credit_el.text if credit_el is not None else None
                break
    return _make_article(
        source,
        (item.findtext("link") or "").strip(),
        item.findtext("title"),
        parse_date(item.findtext("pubDate") or item.findtext(DC + "date")),
        item.findtext("description"),
        item.findtext(CONTENT + "encoded"),
        image_url,
        image_credit,
        [c.text or "" for c in item.findall("category")],
    )


def _atom_entry(entry: ET.Element, source: Source) -> Article | None:
    url = ""
    for link in entry.findall(ATOM + "link"):
        if link.get("rel", "alternate") == "alternate" and link.get("href"):
            url = link.get("href", "")
            break
    return _make_article(
        source,
        url.strip(),
        entry.findtext(ATOM + "title"),
        parse_date(entry.findtext(ATOM + "published") or entry.findtext(ATOM + "updated")),
        entry.findtext(ATOM + "summary"),
        entry.findtext(ATOM + "content"),
        None,
        None,
        [c.get("term", "") for c in entry.findall(ATOM + "category")],
    )


def parse_feed(data: bytes, source: Source) -> list[Article]:
    """Parse RSS or Atom bytes. Items without a title, link or valid date are skipped."""
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("feed declares a DTD or entities; refused")
    root = ET.fromstring(data)
    if root.tag.endswith("feed"):
        articles = [_atom_entry(e, source) for e in root.iter(ATOM + "entry")]
    else:
        articles = [_rss_item(e, source) for e in root.iter("item")]
    return [a for a in articles if a is not None]
