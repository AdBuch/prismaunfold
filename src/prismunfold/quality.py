"""Editorial gate: decides whether an article may enter an edition. Pure function, easy to test."""

from __future__ import annotations

from datetime import datetime, timedelta

from .models import Article, Source
from .normalize import title_key

FUTURE_TOLERANCE = timedelta(hours=1)


def rejection_reason(
    article: Article,
    source: Source,
    now: datetime,
    max_age: timedelta,
    seen_urls: set[str],
    seen_titles: set[str],
) -> str | None:
    """Return why the article must be dropped, or None if it may be kept."""
    if source.ai_policy == "exclude" and article.ai_disclosed:
        return "ai-disclosed (source excludes AI content)"
    if article.published_at > now + FUTURE_TOLERANCE:
        return "published in the future"
    if now - article.published_at > max_age:
        return "older than max age"
    if article.canonical_url in seen_urls:
        return "duplicate url"
    if title_key(article.title) in seen_titles:
        return "duplicate title (syndicated copy)"
    return None
