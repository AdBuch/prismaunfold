r"""Provider-independent editorial contributions and their provenance.

A *contribution* is anything an editorial contributor hands to the newspaper: an
imported prism-data bulletin, a Codex edition, a Claude or Mistral report, an RSS
item. Contributions are stored as received (raw document, content hash, revision)
next to their normalised form and an editorial state. They are never themselves the
published newspaper: the daily edition is composed from them (see `daily`).

Provenance answers: where did it come from (provider, source_key, external_id), when
was it generated / received, which original sources does it cite and at which level
(paragraph or item), what are its known limitations, which revision was published,
and which review happened (state_history).

Editorial states (docs/EDITORIAL_WORKFLOW.md):

    received -> normalised -> validated -> approved -> published
                           \-> review_required -> approved | rejected
    any revision replaced by a newer one -> superseded

Source accessibility (`linkcheck`) and factual verification (`verification`) are
separate fields; an editorial state never implies either.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

PROVIDERS = ("rss", "prism-data", "chatgpt", "codex", "claude", "mistral", "goose", "other")
STATES = ("received", "normalised", "validated", "review_required", "approved", "published",
          "rejected", "superseded")
PUBLIC_STATES = frozenset({"approved", "published"})
# How a contribution relates to the facts it reports.
ORIGIN_TYPES = ("original_publisher", "ai_secondary", "editorial_synthesis")
PROVIDER_ORIGIN = {"rss": "original_publisher", "prism-data": "ai_secondary", "chatgpt": "ai_secondary",
                   "codex": "ai_secondary", "claude": "ai_secondary", "mistral": "ai_secondary",
                   "goose": "ai_secondary", "other": "ai_secondary"}


def content_hash(data: bytes | str | dict) -> str:
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new(provider: str, source_key: str, edition_date: str, digest: str, *, generated_at: str | None,
        upstream_status: str = "", kind: str = "edition", raw=None, normalised=None,
        state: str = "received", limitations: list[str] | None = None, received_at: str | None = None) -> dict:
    if provider not in PROVIDERS:
        provider = "other"
    if state not in STATES:
        raise ValueError(f"unknown editorial state: {state}")
    received_at = received_at or now_iso()
    return {
        "id": f"{provider}|{source_key}|{digest[:16]}",
        "provider": provider,
        "kind": kind,
        "source_key": source_key,
        "edition_date": edition_date,
        "content_hash": digest,
        "generated_at": generated_at,
        "received_at": received_at,
        "origin_type": PROVIDER_ORIGIN.get(provider, "ai_secondary"),
        "upstream_status": upstream_status,
        "state": state,
        "state_history": [dict(state=state, at=received_at, by="system", note="")],
        "limitations": list(limitations or []),
        "raw": raw,
        "normalised": normalised,
    }


def transition(contribution: dict, state: str, by: str = "system", note: str = "") -> dict:
    if state not in STATES:
        raise ValueError(f"unknown editorial state: {state}")
    contribution["state"] = state
    contribution.setdefault("state_history", []).append(dict(state=state, at=now_iso(), by=by, note=note))
    return contribution


def independent_publishers(source_lists) -> set[str]:
    """Distinct original publishers behind a set of contributions.

    Several AI contributions citing the same original article are one confirmation,
    not several: we count canonical original URLs' hosts, never contributors.
    """
    from urllib.parse import urlsplit

    from .normalize import canonical_url

    hosts = set()
    for sources in source_lists:
        for source in sources or []:
            url = source.get("url") if isinstance(source, dict) else source
            if url:
                host = (urlsplit(canonical_url(url)).hostname or "").removeprefix("www.")
                if host:
                    hosts.add(host)
    return hosts
