"""What do we actually know about a claim? Four separate questions, never merged.

1. Citation    The sentence names a well-formed source URL. (`reports` guarantees this.)
2. Reachable   The URL answers. (`linkcheck` checks this; None = not checked.)
3. Support     The page really says what the sentence says. (A `SupportChecker` decides.)
4. Corroborated  At least two independent publishers support it.

A source link existing proves 1, at most 2. It never proves 3 or 4, so a sentence is
only ever `supported` when a checker has confirmed it.

States, for a sentence and for a whole story:

    unverified        cited, nobody has checked the support yet
    supported         a checker confirmed the cited source supports it
    disputed          sources contradict each other, or a checker found a contradiction
    review_required   something is wrong or thin: a dead link, a source that does not
                      support the sentence, or a story resting on a single publisher
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from .models import Story, StorySentence, StorySource

UNVERIFIED = "unverified"
SUPPORTED = "supported"
DISPUTED = "disputed"
REVIEW_REQUIRED = "review_required"
STATES = (UNVERIFIED, SUPPORTED, DISPUTED, REVIEW_REQUIRED)

# Results a SupportChecker may return for one sentence and one source.
NOT_CHECKED = "not_checked"
NOT_SUPPORTED = "not_supported"
CONTRADICTED = "contradicted"
SUPPORT_RESULTS = (NOT_CHECKED, SUPPORTED, NOT_SUPPORTED, CONTRADICTED)


class SupportChecker(Protocol):
    """Decides whether a source supports a sentence. Implementations read the page."""

    name: str

    def check(self, sentence: StorySentence, source: StorySource) -> str:
        """Return one of SUPPORT_RESULTS."""
        ...


class NoSupportChecker:
    """Default: nobody has read the sources, so nothing is claimed about support."""

    name = "none"

    def check(self, sentence: StorySentence, source: StorySource) -> str:
        return NOT_CHECKED


class ExtractiveSupport:
    """For feed-desk stories only: each sentence is copied from the cited article's own
    title or excerpt, so that article supports it by construction."""

    name = "extractive"

    def check(self, sentence: StorySentence, source: StorySource) -> str:
        return SUPPORTED


def publisher_key(url: str) -> str:
    """Rough identity of a publisher: the host without a leading www.

    Two hosts of one media group still count as two; a syndicated agency text on two
    sites counts as two as well. Independence is therefore an upper bound.
    """
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


@dataclass(frozen=True)
class ClaimVerification:
    state: str
    citation: str  # always "structural": sentences without a source never get this far
    sources_reachable: bool | None
    support: str
    independent_publishers: int
    corroborated: bool


def verify_sentence(
    sentence: StorySentence,
    sources: dict[str, StorySource],
    reachable: dict[str, bool] | None,
    checker: SupportChecker,
) -> ClaimVerification:
    results = {
        url: checker.check(sentence, sources[url]) for url in sentence.source_urls if url in sources
    }
    for url, result in results.items():
        if result not in SUPPORT_RESULTS:
            raise ValueError(f"checker {checker.name!r} returned {result!r} for {url}")
    supporting = {publisher_key(u) for u, r in results.items() if r == SUPPORTED}
    all_reachable = (
        None if reachable is None else all(reachable.get(u, False) for u in sentence.source_urls)
    )

    if CONTRADICTED in results.values():
        state, support = DISPUTED, CONTRADICTED
    elif NOT_SUPPORTED in results.values() and not supporting:
        state, support = REVIEW_REQUIRED, NOT_SUPPORTED
    elif all_reachable is False:
        state, support = REVIEW_REQUIRED, SUPPORTED if supporting else NOT_CHECKED
    elif supporting:
        state, support = SUPPORTED, SUPPORTED
    else:
        state, support = UNVERIFIED, NOT_CHECKED

    return ClaimVerification(
        state=state,
        citation="structural",
        sources_reachable=all_reachable,
        support=support,
        independent_publishers=len({publisher_key(u) for u in sentence.source_urls}),
        corroborated=len(supporting) >= 2,
    )


def verify_story(
    story: Story,
    reachable: dict[str, bool] | None = None,
    checker: SupportChecker | None = None,
    dropped_sentences: int = 0,
    dead_sources: int = 0,
) -> dict:
    """Verification record for a story, as a plain dict ready to store and export.

    `reachable` maps each cited URL to the link check's result; None means no link
    check ran. `dropped_sentences` counts sentences removed earlier for lack of a
    usable or reachable source; any such loss sends the story to review.
    """
    checker = checker or NoSupportChecker()
    sources = {s.url: s for s in story.sources}
    claims = [verify_sentence(s, sources, reachable, checker) for s in story.sentences]
    publishers = {publisher_key(u) for s in story.sentences for u in s.source_urls}
    states = {c.state for c in claims}

    reasons: list[str] = []
    if story.disputes:
        reasons.append("The writer reports that sources contradict each other.")
    if DISPUTED in states:
        reasons.append("A source contradicts at least one sentence.")
    if any(c.support == NOT_SUPPORTED for c in claims):
        reasons.append("At least one cited source does not support its sentence.")
    if any(c.sources_reachable is False for c in claims):
        reasons.append("At least one cited source could not be opened.")
    if dead_sources:
        reasons.append(f"{dead_sources} cited source(s) could not be opened and were removed.")
    if dropped_sentences:
        reasons.append(f"{dropped_sentences} sentence(s) were removed for lack of a usable source.")
    if claims and len(publishers) == 1:
        reasons.append("Every sentence rests on a single publisher.")

    if story.disputes or DISPUTED in states:
        state = DISPUTED
    elif reasons:
        state = REVIEW_REQUIRED
    elif claims and states == {SUPPORTED}:
        state = SUPPORTED
    else:
        state = UNVERIFIED

    return {
        "state": state,
        "checker": checker.name,
        "links_checked": reachable is not None,
        "independent_publishers": len(publishers),
        "corroborated_sentences": sum(c.corroborated for c in claims),
        "reasons": reasons,
        "sentences": [dataclasses.asdict(c) for c in claims],
    }
