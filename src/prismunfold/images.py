"""Image metadata and display rights.

An image is embedded only when its rights are documented, never merely because a
worker returned an image URL. Metadata of images that may not be shown is kept, so
an editor can clear them later. An article without a usable image stays publishable.

Canonical fields (docs/EDITORIAL_WORKFLOW.md, "Images"):

    url, source_url, alt, caption, credit, license, license_url, rights, rights_note,
    display_allowed (upstream claim), origin, display (our decision), display_reason

`origin` is one of: publisher, wikimedia_commons, official, licensed_photo, chart,
ai_illustration, unknown. AI illustrations are shown only with an explicit grant and
are always labelled; they never count as photographs of real events.
"""
from __future__ import annotations

import re

from .reports import public_url

ORIGINS = ("publisher", "wikimedia_commons", "official", "licensed_photo", "chart",
           "ai_illustration", "unknown")
OPEN_LICENSE = re.compile(r"(?:CC[- ]BY(?:[- ]SA)?[- ]?[234](?:\.0)?|CC0(?:[- ]?1\.0)?|public[ -]domain)", re.I)
GRANTED = ("approved", "licensed", "public_domain")
BLOCKED = ("denied", "restricted", "unknown", "unlicensed")
AI_LABEL = "KI-generierte Illustration – kein Foto eines realen Ereignisses"


def _text(value, limit):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("invalid image text field")
    return value.strip()


def _link(value):
    if not value:
        return ""
    url = public_url(value)
    if not url or "\\" in url:
        raise ValueError("invalid HTTP(S) image URL")
    return url


def image_metadata(raw) -> dict:
    """Normalise one image record and decide whether it may be displayed."""
    if not isinstance(raw, dict):
        raise ValueError("image must be an object")
    url = raw.get("url") or raw.get("image_url")
    _link(url)
    url = url.strip()  # keep signed image URLs byte-for-byte
    rights = raw.get("rights")
    details = rights if isinstance(rights, dict) else {}
    license_name = _text(raw.get("license") or details.get("license"), 250)
    credit = _text(raw.get("credit") or raw.get("attribution") or details.get("credit"), 400)
    allowed = raw.get("display_allowed", details.get("display_allowed"))
    rights_status = _text(details.get("status") if isinstance(rights, dict) else rights, 250)
    origin = _text(raw.get("origin"), 40) or "unknown"
    if origin not in ORIGINS:
        origin = "unknown"
    explicit = allowed is True or rights_status in GRANTED
    blocked = allowed is False or rights_status in BLOCKED
    open_license = bool(license_name and OPEN_LICENSE.fullmatch(license_name))

    reason = "ok"
    if not url.startswith("https://"):
        reason = "not_https"
    elif not credit:
        reason = "missing_credit"
    elif blocked:
        reason = "rights_blocked"
    elif origin == "ai_illustration" and not explicit:
        reason = "ai_illustration_needs_explicit_grant"
    elif not (explicit or open_license):
        reason = "missing_rights"
    caption = _text(raw.get("caption"), 700)
    if origin == "ai_illustration" and AI_LABEL not in caption:
        caption = f"{caption} · {AI_LABEL}" if caption else AI_LABEL
    return dict(url=url, alt=_text(raw.get("alt"), 500), caption=caption,
                credit=credit, license=license_name, rights=rights_status,
                rights_note=_text(raw.get("rights_note") or details.get("note"), 700),
                source_url=_link(raw.get("source_url")), license_url=_link(raw.get("license_url")),
                display_allowed=allowed if isinstance(allowed, bool) else None,
                origin=origin, display=reason == "ok", display_reason=reason)
