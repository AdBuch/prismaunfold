"""Compose one daily edition from the stories of a day.

The edition is the same for every reader. Personal preferences are applied on the
device, on top of this shared selection (see the frontend), so the server never
learns a reader's profile and no reader gets an edition made only of what they like.

Selection is greedy. Each round takes the story with the highest value, where

    value = base score
            - a penalty for every already chosen story from the same section,
              the same primary region, the same language, or the same publishers
            + a bonus for a story that would otherwise be the only voice from its
              region or section (underreported)

Base score rewards independent sourcing, novelty and a clean verification state.
Nothing here measures clicks or engagement; there are none to measure.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass

from .models import Story
from .verification import DISPUTED, REVIEW_REQUIRED, SUPPORTED, UNVERIFIED, publisher_key

MAX_PLACED = 14
MAX_BRIEFS = 8
SECONDARY_SLOTS = 3

WEIGHT_BREADTH = 0.45
WEIGHT_NOVELTY = 0.25
WEIGHT_TRUST = 0.30
PENALTY_SECTION = 0.12
PENALTY_REGION = 0.08
PENALTY_LANGUAGE = 0.04
PENALTY_PUBLISHER = 0.10
BONUS_UNDERREPORTED = 0.10

TRUST = {SUPPORTED: 1.0, UNVERIFIED: 0.7, DISPUTED: 0.6, REVIEW_REQUIRED: 0.5}
MOTIFS = ("alpine", "sea", "terraces", "night", "trees", "city", "seed", "library", "market", "grid")
ART_CREDIT = "PrismUnfold procedural artwork, not a photograph"


def state_of(story: Story) -> str:
    return (story.verification or {}).get("state", UNVERIFIED)


def publishers_of(story: Story) -> frozenset[str]:
    return frozenset(publisher_key(s.url) for s in story.sources)


def base_score(story: Story, day: str) -> float:
    breadth = min(len(publishers_of(story)), 5) / 5.0
    novelty = 1.0 if story.day == day else 0.6  # first report today, or an update of an older one
    return round(
        WEIGHT_BREADTH * breadth + WEIGHT_NOVELTY * novelty + WEIGHT_TRUST * TRUST[state_of(story)], 4
    )


def image_for(story: Story) -> dict:
    """Deterministic abstract artwork. Real photographs need rights we do not have yet."""
    digest = hashlib.sha1(story.topic_slug.encode("utf-8")).digest()
    return {
        "motif": MOTIFS[digest[0] % len(MOTIFS)],
        "seed": int(story.id[:6], 16) % 1000,
        "alt": "Abstract illustration",
        "caption": f"Illustration: {story.topic}",
        "credit": ART_CREDIT,
    }


@dataclass(frozen=True)
class Pick:
    story: Story
    value: float
    underreported: bool


def select(stories: list[Story], day: str, limit: int) -> list[Pick]:
    """Order stories for the edition; see the module docstring for the rule."""
    region_total = Counter(r for s in stories for r in s.regions[:1])
    section_total = Counter(s.topic_slug for s in stories)
    remaining = sorted(stories, key=lambda s: s.id)
    picks: list[Pick] = []
    sections: Counter[str] = Counter()
    regions: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    used_publishers: Counter[str] = Counter()

    while remaining and len(picks) < limit:
        best: Pick | None = None
        for story in remaining:
            region = story.regions[0] if story.regions else ""
            lone_voice = section_total[story.topic_slug] == 1 or (region and region_total[region] == 1)
            underreported = bool(lone_voice) and len(publishers_of(story)) <= 1
            overlap = sum(1 for p in publishers_of(story) if used_publishers[p])
            value = (
                base_score(story, day)
                - PENALTY_SECTION * sections[story.topic_slug]
                - PENALTY_REGION * (regions[region] if region else 0)
                - PENALTY_LANGUAGE * languages[story.language]
                - PENALTY_PUBLISHER * min(overlap, 2)
                + (BONUS_UNDERREPORTED if underreported else 0.0)
            )
            if best is None or value > best.value:
                best = Pick(story, round(value, 4), underreported)
        assert best is not None
        picks.append(best)
        remaining.remove(best.story)
        sections[best.story.topic_slug] += 1
        if best.story.regions:
            regions[best.story.regions[0]] += 1
        languages[best.story.language] += 1
        used_publishers.update(publishers_of(best.story))
    return picks


def teaser(story: Story) -> str:
    return story.sentences[0].text if story.sentences else ""


def compose_edition(stories: list[Story], day: str, number: int) -> dict:
    """The edition of one day in the frontend's `Edition` shape."""
    usable = [s for s in stories if s.sentences and not s.nothing_new]
    picks = select(usable, day, MAX_PLACED + MAX_BRIEFS)
    placed, brief_picks = picks[:MAX_PLACED], picks[MAX_PLACED:]

    placements = []
    for order, pick in enumerate(placed, start=1):
        story = pick.story
        slot = "lead" if order == 1 else "secondary" if order <= 1 + SECONDARY_SLOTS else "standard"
        placements.append(
            {
                "storySlug": story.slug,
                "section": story.topic_slug,
                "slot": slot,
                "order": order,
                "snapshot": {
                    "headline": story.headline,
                    "teaser": teaser(story),
                    "image": image_for(story),
                },
                "language": story.language,
                "regions": list(story.regions),
                "verificationState": state_of(story),
                "underreported": pick.underreported,
                "isUpdate": story.day != day,
            }
        )
    briefs = [
        {
            "id": f"brief-{pick.story.id[:10]}",
            "section": pick.story.topic_slug,
            "text": pick.story.headline,
            "storySlug": pick.story.slug,
            "language": pick.story.language,
            "regions": list(pick.story.regions),
        }
        for pick in brief_picks
    ]

    all_publishers = {p for pick in picks for p in publishers_of(pick.story)}
    thin = sum(1 for pick in picks if len(publishers_of(pick.story)) <= 1)
    note = (
        f"{len(picks)} stories drawing on {len(all_publishers)} publishers. "
        f"{thin} rest on a single publisher and are marked. "
        "Selected and ordered automatically; no human editor has reviewed this edition."
    )
    return {
        "id": f"edition-{day}",
        "date": day,
        "number": number,
        "editorsNote": note,
        "placements": placements,
        "briefs": briefs,
        "magazineTeaser": "",
        "demo": False,
    }
