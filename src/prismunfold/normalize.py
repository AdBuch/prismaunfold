"""Canonical URLs, text cleaning and title keys used for deduplication and clustering."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = re.compile(r"^(utm_[a-z_]+|fbclid|gclid|mc_cid|mc_eid)$", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^\w\s]")
STOPWORDS = frozenset(
    """
    alle auch aber dass dann dem den der des die das durch einen einer eines eine
    für ihre ihren mit nach nicht oder über und vom von wie wird werden bei aus
    auf als sind ist im in am an zum zur wurde wurden habe haben hat sich
    about after also been from have into more over that their they this with were
    """.split()
)


def canonical_url(url: str) -> str:
    """Lower-case scheme and host, drop fragments and tracking parameters, trim trailing slash."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.port:
        host = f"{host}:{parts.port}"
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not TRACKING_PARAMS.match(k)
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ""))


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    return WS_RE.sub(" ", unescape(TAG_RE.sub(" ", text))).strip()


def fold(text: str) -> str:
    """Lower case and remove diacritics, so 'Zürich' and 'Zurich' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def title_key(title: str) -> str:
    return WS_RE.sub(" ", PUNCT_RE.sub(" ", fold(title))).strip()


def tokens(title: str) -> frozenset[str]:
    return frozenset(w for w in title_key(title).split() if len(w) >= 4 and w not in STOPWORDS)


def sha1_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
