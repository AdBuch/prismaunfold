"""Summaries with mandatory source citations, plus the translation boundary.

ExtractiveSummarizer needs no LLM: it takes headlines and lead sentences from the sources.
Every sentence carries the ids of the articles it comes from; validate_summary drops any
sentence that cites nothing or cites an article outside the event (Q-1, FR-5).
An LLM summariser and translator plug in behind the same interfaces later.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Protocol

from .models import Article, Event, Sentence, Summary
from .normalize import strip_html, title_key

PROMPT_VERSION = "extractive-0.1"
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
MAX_SENTENCE_CHARS = 280


class NotConfigured(RuntimeError):
    """Raised by a backend that is not set up yet (for example the LLM translator)."""


def first_sentence(text: str) -> str:
    if not text:
        return ""
    return SENTENCE_SPLIT.split(text.strip(), maxsplit=1)[0][:MAX_SENTENCE_CHARS]


class ExtractiveSummarizer:
    name = "extractive"

    def __init__(self, max_sentences: int = 3) -> None:
        self.max_sentences = max_sentences

    def summarize(self, event: Event, articles: list[Article]) -> Summary:
        """Articles must be sorted oldest first, so the original report leads."""
        merged: dict[str, tuple[str, list[str]]] = {}
        order: list[str] = []
        for article in articles:
            lead_source = article.excerpt or strip_html(article.body_text)[:600]
            for text in (article.title, first_sentence(lead_source)):
                key = title_key(text)
                if not key:
                    continue
                if key not in merged:
                    merged[key] = (text, [])
                    order.append(key)
                ids = merged[key][1]
                if article.id not in ids:
                    ids.append(article.id)
        sentences = tuple(
            Sentence(text=merged[k][0], article_ids=tuple(merged[k][1]))
            for k in order[: self.max_sentences]
        )
        return Summary(
            event_id=event.id,
            language=event.language,
            sentences=sentences,
            generator=self.name,
            prompt_version=PROMPT_VERSION,
        )


def validate_summary(summary: Summary, event: Event) -> tuple[Summary, int]:
    """Keep only sentences whose citations all belong to the event. Return (summary, dropped)."""
    allowed = set(event.article_ids)
    kept = tuple(s for s in summary.sentences if s.article_ids and set(s.article_ids) <= allowed)
    dropped = len(summary.sentences) - len(kept)
    return dataclasses.replace(summary, sentences=kept), dropped


class Translator(Protocol):
    def translate(self, summary: Summary, target_language: str) -> Summary: ...


class NoTranslator:
    """Placeholder until the LLM translation adapter is configured."""

    def translate(self, summary: Summary, target_language: str) -> Summary:
        raise NotConfigured("no translation backend configured yet")
