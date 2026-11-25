"""Deterministic matching of contributions that report the same event.

No model call: canonical source URLs, normalised headlines, token overlap, shared
named entities and a publication-date window decide. The bar is deliberately high:
two stories that merely mention the same country, politician or organisation stay
separate, and an ambiguous match (two equally good targets) is not merged.

When a candidate matches, it is attached to the target as `coverage` (with its own
attribution, sources, perspectives and uncertainties); paragraphs that repeat text
already shown are dropped from the attached copy. The target keeps its own headline,
text and sources. Contradictions and uncertainties are kept, never resolved here.
"""
from __future__ import annotations

import re
from datetime import date

from .normalize import canonical_url, fold, title_key, tokens

ENTITY = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-ZÄÖÜ][\w\-]{2,})")
GENERIC = frozenset(fold(w) for w in """
    Schweiz Peru Deutschland Europa USA China Russland Ukraine Bund Regierung Parlament
    Bundesrat Präsident Minister Switzerland Germany Europe Government President
""".split())
WINDOW_DAYS = 2


def _entities(item: dict) -> frozenset[str]:
    text = f"{item.get('headline', '')}. {item.get('lead', '')}"
    return frozenset(fold(m) for m in ENTITY.findall(text)) - GENERIC


def _urls(item: dict) -> set[str]:
    return {canonical_url(s["url"]) for s in item.get("sources", []) if s.get("url")}


def _day(item: dict) -> date | None:
    value = item.get("date") or item.get("edition_date")
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def match_score(candidate: dict, target: dict) -> float:
    """0 = different events; higher = more certainly the same event."""
    left, right = _day(candidate), _day(target)
    if left and right and abs((left - right).days) > WINDOW_DAYS:
        return 0.0
    a, b = tokens(candidate["headline"]), tokens(target["headline"])
    common = len(a & b)
    overlap = common / max(1, len(a | b))
    shared_urls = _urls(candidate) & _urls(target)
    entities = len(_entities(candidate) & _entities(target))
    if common >= 2 and title_key(candidate["headline"]) == title_key(target["headline"]):
        return 2.0
    if shared_urls and common >= 2 and overlap >= 0.28:
        return 1.0 + overlap
    if common >= 4 and overlap >= 0.65:
        return overlap
    if common >= 3 and overlap >= 0.45 and entities >= 2:
        return overlap
    return 0.0


def _paragraph_keys(item: dict) -> set[str]:
    return {title_key(p["text"]) for p in item.get("paragraphs", []) if p.get("text")}


def add_coverage(candidate: dict, targets: list[dict]) -> bool:
    """Attach `candidate` to its single best match among `targets`; False if none or ambiguous."""
    ranked = sorted(((match_score(candidate, t), i) for i, t in enumerate(targets)), reverse=True)
    if not ranked or ranked[0][0] == 0 or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
        return False
    target = targets[ranked[0][1]]
    seen = _paragraph_keys(target)
    for existing in target.get("coverage", []):
        seen |= _paragraph_keys(existing)
    attached = dict(candidate)
    attached["paragraphs"] = [p for p in candidate.get("paragraphs", []) if title_key(p.get("text", "")) not in seen]
    attached["duplicate_paragraphs_omitted"] = len(candidate.get("paragraphs", [])) - len(attached["paragraphs"])
    target.setdefault("coverage", []).append(attached)
    return True
