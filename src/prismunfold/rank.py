"""Shared ranking for an edition. No personal data: personal weights are applied on the device later."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from .models import Event


def score(event: Event, now: datetime) -> float:
    """Recency (half-life about 6 hours) plus breadth (up to 5 sources)."""
    hours = max((now - event.last_published).total_seconds() / 3600.0, 0.0)
    recency = 1.0 / (1.0 + hours / 6.0)
    breadth = min(len(set(event.source_ids)), 5) / 5.0
    return round(0.6 * recency + 0.4 * breadth, 4)


def select(events: list[Event], max_events: int, max_per_topic: int) -> list[Event]:
    """Highest score first, with a cap per primary topic so one beat cannot flood the edition."""
    ranked = sorted(events, key=lambda e: (-e.score, e.id))
    chosen: list[Event] = []
    per_topic: Counter[str] = Counter()
    for event in ranked:
        if len(chosen) >= max_events:
            break
        primary = event.topics[0] if event.topics else "allgemein"
        if per_topic[primary] >= max_per_topic:
            continue
        chosen.append(event)
        per_topic[primary] += 1
    return chosen
