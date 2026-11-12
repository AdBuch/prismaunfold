"""Check that the URLs an agent cites actually exist.

This catches invented links. It does not prove that a page supports the sentence
citing it; that needs reading the page and is a separate step.

The URLs come from an agent, so they are untrusted: only public http(s) hosts are
contacted, never loopback, private or link-local addresses. The host is resolved
once for the check and again by the HTTP client, so run this where internal
services are not reachable anyway (its own container or network policy).
"""

from __future__ import annotations

import dataclasses
import ipaddress
import socket
import urllib.error
import urllib.request
from typing import Callable
from urllib.parse import urlsplit

from .models import Story

USER_AGENT = "PrismUnfoldLinkCheck/0.1 (+source verification)"
TIMEOUT = 10

# Returns True when the URL answers with a page. Injected in tests.
Probe = Callable[[str], bool]


def is_public_host(host: str) -> bool:
    """True only if every address the host resolves to is a public one."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)


class _NoRedirectToPrivate(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if parts.scheme not in ("http", "https") or not is_public_host(parts.hostname or ""):
            raise urllib.error.URLError(f"redirect to non-public target {newurl!r}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_probe(url: str) -> bool:
    """HEAD first, GET if the server refuses HEAD. Any 2xx counts as existing."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not is_public_host(parts.hostname or ""):
        return False
    opener = urllib.request.build_opener(_NoRedirectToPrivate)
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with opener.open(request, timeout=TIMEOUT) as response:
                return 200 <= response.status < 300
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue  # some servers do not answer HEAD
            return False
        except (urllib.error.URLError, OSError, ValueError):
            return False
    return False


def check_story(story: Story, probe: Probe = http_probe) -> tuple[Story | None, list[str]]:
    """Remove dead source URLs; drop sentences left without a source.

    Returns (None, problems) when no sentence survives.
    """
    urls = list(dict.fromkeys(u for s in story.sentences for u in s.source_urls))
    alive = {u for u in urls if probe(u)}
    problems = [f"source does not answer, removed: {u}" for u in urls if u not in alive]

    sentences = []
    for position, sentence in enumerate(story.sentences, start=1):
        kept = tuple(u for u in sentence.source_urls if u in alive)
        if kept:
            sentences.append(dataclasses.replace(sentence, source_urls=kept))
        else:
            problems.append(f"sentence {position}: no reachable source, dropped")

    if not sentences and not story.nothing_new:
        return None, problems + ["rejected: no sentence with a reachable source is left"]
    checked = dataclasses.replace(
        story,
        sentences=tuple(sentences),
        sources=tuple(s for s in story.sources if s.url in alive),
    )
    return checked, problems
