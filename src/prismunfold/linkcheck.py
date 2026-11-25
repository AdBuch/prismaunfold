"""Source accessibility checks for cited URLs.

This answers one question only: can the cited document currently be retrieved? It
catches invented or dead links. It does NOT show that the page supports the sentence
citing it (see `verification`), and a refusal (HTTP 403, paywall, anti-bot page)
does not show that a source is fabricated.

Results (see docs/EDITORIAL_WORKFLOW.md, "Source accessibility"):

    reachable        2xx response
    restricted       401/402/403/407/451: authentication, payment or access policy
    missing          404/410
    rate_limited     429                                   (transient, retried)
    unavailable      5xx, connection or TLS errors         (5xx retried)
    timeout          the request did not complete in time  (transient, retried)
    dns_failure      the host could not be resolved now   (transient, retried)
    unsafe           scheme, host or a redirect target violates the security policy
    unknown          not checked (yet)

Security: the URLs come from AI workers and are untrusted. Only http(s) URLs whose
host resolves exclusively to public (global) addresses are contacted. The connection
is pinned to the vetted address, so the HTTP client cannot resolve the name a second
time to an internal address (DNS rebinding). Every redirect target is re-validated
and resolved the same way; at most MAX_REDIRECTS are followed. No cookies, no
credentials, no proxy, no paywall or anti-bot circumvention: a refusal is recorded
as `restricted` and left alone.
"""

from __future__ import annotations

import dataclasses
import http.client
import ipaddress
import json
import os
import socket
import ssl
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit

from .models import Story

USER_AGENT = "PrismUnfoldLinkCheck/0.2 (+source accessibility check; no content reuse)"
TIMEOUT = 10
MAX_REDIRECTS = 5
ATTEMPTS = 3
BACKOFF = 1.0
MAX_BACKOFF = 8.0

REACHABLE, RESTRICTED, MISSING = "reachable", "restricted", "missing"
RATE_LIMITED, UNAVAILABLE, TIMEOUT_STATUS = "rate_limited", "unavailable", "timeout"
DNS_FAILURE, UNSAFE, UNKNOWN = "dns_failure", "unsafe", "unknown"
STATUSES = (REACHABLE, RESTRICTED, MISSING, RATE_LIMITED, UNAVAILABLE, TIMEOUT_STATUS,
            DNS_FAILURE, UNSAFE, UNKNOWN)
TRANSIENT = frozenset({RATE_LIMITED, UNAVAILABLE, TIMEOUT_STATUS, DNS_FAILURE})
# Older stored editions used one combined value; read it as "unsafe".
LEGACY = {"unsafe_or_unresolved": UNSAFE}

# Returns True when the URL answers with a page. Injected in tests.
Probe = Callable[[str], bool]


class Unsafe(Exception):
    pass


class DNSFailure(Exception):
    pass


def resolve_public(host: str, resolver=socket.getaddrinfo) -> list[str]:
    """All addresses of `host`, which must all be public. Raises DNSFailure / Unsafe."""
    if not host:
        raise Unsafe("missing host")
    try:
        ipaddress.ip_address(host)
        raise Unsafe("literal IP address")
    except ValueError:
        pass
    try:
        infos = resolver(host, None, proto=socket.IPPROTO_TCP)
    except UnicodeError:
        raise Unsafe("invalid host name") from None
    except OSError as exc:
        raise DNSFailure(str(exc)) from None
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not addresses:
        raise DNSFailure("no addresses")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global or ip.is_multicast:
            raise Unsafe("host resolves to a non-public address")
    return addresses


def is_public_host(host: str) -> bool:
    """True only if every address the host resolves to is a public one."""
    try:
        resolve_public(host)
        return True
    except (Unsafe, DNSFailure):
        return False


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, address, **kw):
        super().__init__(host, **kw)
        self._address = address

    def connect(self):
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, **kw):
        super().__init__(host, context=ssl.create_default_context(), **kw)
        self._address = address

    def connect(self):
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _request(method: str, url: str, address: str, timeout: float) -> tuple[int, str]:
    """One request to the pinned address. Returns (status code, Location header)."""
    parts = urlsplit(url)
    cls = _PinnedHTTPSConnection if parts.scheme == "https" else _PinnedHTTPConnection
    conn = cls(parts.hostname, address, port=parts.port, timeout=timeout)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    try:
        conn.request(method, path, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        response = conn.getresponse()
        if method == "GET":
            response.read(65536)  # enough to complete the exchange; content is not used
        return response.status, response.getheader("Location") or ""
    finally:
        conn.close()


@dataclasses.dataclass(frozen=True)
class SourceCheck:
    url: str
    status: str
    http_status: int | None = None
    attempts: int = 1
    final_url: str = ""
    detail: str = ""

    @property
    def transient(self) -> bool:
        return self.status in TRANSIENT


def _classify(code: int) -> str:
    if 200 <= code < 300:
        return REACHABLE
    if code in (401, 402, 403, 407, 451):
        return RESTRICTED
    if code in (404, 410):
        return MISSING
    if code == 429:
        return RATE_LIMITED
    return UNAVAILABLE


def _once(url: str, transport, resolver, timeout: float) -> SourceCheck:
    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        parts = urlsplit(current)
        if parts.scheme not in ("http", "https") or parts.username or parts.password:
            return SourceCheck(url, UNSAFE, final_url=current, detail="scheme or credentials")
        try:
            address = resolve_public(parts.hostname or "", resolver)[0]
        except Unsafe as exc:
            return SourceCheck(url, UNSAFE, final_url=current, detail=str(exc))
        except DNSFailure:
            return SourceCheck(url, DNS_FAILURE, final_url=current, detail="name not resolved")
        code = None
        for method in ("HEAD", "GET"):
            try:
                code, location = transport(method, current, address, timeout)
            except (socket.timeout, TimeoutError):
                return SourceCheck(url, TIMEOUT_STATUS, final_url=current)
            except (OSError, http.client.HTTPException, ValueError) as exc:
                return SourceCheck(url, UNAVAILABLE, final_url=current, detail=type(exc).__name__)
            # Many publishers refuse HEAD but answer GET; a 403 on HEAD is not final.
            if method == "HEAD" and code in (400, 403, 405, 501):
                continue
            break
        if code in (301, 302, 303, 307, 308) and location:
            current = urljoin(current, location)
            continue
        return SourceCheck(url, _classify(code), http_status=code, final_url=current)
    return SourceCheck(url, UNSAFE, final_url=current, detail="too many redirects")


def check_source(url: str, *, transport=_request, resolver=socket.getaddrinfo, sleep=time.sleep,
                 attempts: int = ATTEMPTS, backoff: float = BACKOFF, timeout: float = TIMEOUT) -> SourceCheck:
    """Check one URL with bounded retries and exponential backoff for transient results."""
    result = SourceCheck(url, UNKNOWN)
    for attempt in range(1, max(1, attempts) + 1):
        result = dataclasses.replace(_once(url, transport, resolver, timeout), attempts=attempt)
        # 5xx and timeouts may clear; other "unavailable" causes (TLS, 4xx) are retried too,
        # because the budget is small and a single blip should not decide publication.
        if not result.transient or attempt == attempts:
            return result
        sleep(min(MAX_BACKOFF, backoff * 2 ** (attempt - 1)))
    return result


class SourceCheckCache:
    """Remembers results during an editorial cycle; optionally persisted as JSON.

    Definitive answers are kept for `ttl` seconds, transient ones for `transient_ttl`,
    so a publisher that was down is asked again in the next cycle, not in the same one.
    """

    def __init__(self, path: str | Path | None = None, ttl: int = 6 * 3600, transient_ttl: int = 900,
                 clock=time.time) -> None:
        self.path = Path(path) if path else None
        self.ttl, self.transient_ttl, self.clock = ttl, transient_ttl, clock
        self.entries: dict[str, dict] = {}
        if self.path and self.path.exists():
            try:
                self.entries = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.entries = {}

    def get(self, url: str) -> SourceCheck | None:
        entry = self.entries.get(url)
        if not entry:
            return None
        ttl = self.transient_ttl if entry["status"] in TRANSIENT else self.ttl
        if self.clock() - entry["checked_at"] > ttl:
            return None
        return SourceCheck(url, entry["status"], entry.get("http_status"), entry.get("attempts", 1),
                           entry.get("final_url", ""), entry.get("detail", ""))

    def put(self, result: SourceCheck) -> None:
        self.entries[result.url] = dict(status=result.status, http_status=result.http_status,
                                        attempts=result.attempts, final_url=result.final_url,
                                        detail=result.detail, checked_at=self.clock())

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(self.entries, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def probe(self, check=check_source) -> Callable[[str], str]:
        """A `url -> status` function that consults and fills the cache."""
        def status(url: str) -> str:
            hit = self.get(url)
            if hit is None:
                hit = check(url)
                self.put(hit)
            return hit.status
        return status


def http_status(url: str) -> str:
    """Status string for one URL (accessibility, not truth)."""
    return check_source(url).status


def http_probe(url: str) -> bool:
    """Compatibility for the agent-report desk: True only for a reachable page."""
    return http_status(url) == REACHABLE


@dataclasses.dataclass(frozen=True)
class LinkCheck:
    story: Story | None  # None when no sentence kept a reachable source
    reachable: dict[str, bool]  # every URL the story cited, before pruning
    dropped_sentences: int
    problems: list[str]


def check_story(story: Story, probe: Probe = http_probe) -> LinkCheck:
    """Remove dead source URLs and drop sentences left without a source."""
    urls = list(dict.fromkeys(u for s in story.sentences for u in s.source_urls))
    reachable = {u: bool(probe(u)) for u in urls}
    problems = [f"source does not answer, removed: {u}" for u in urls if not reachable[u]]

    sentences = []
    dropped = 0
    for position, sentence in enumerate(story.sentences, start=1):
        kept = tuple(u for u in sentence.source_urls if reachable[u])
        if kept:
            sentences.append(dataclasses.replace(sentence, source_urls=kept))
        else:
            dropped += 1
            problems.append(f"sentence {position}: no reachable source, dropped")

    if not sentences and not story.nothing_new:
        problems.append("rejected: no sentence with a reachable source is left")
        return LinkCheck(None, reachable, dropped, problems)
    checked = dataclasses.replace(
        story,
        sentences=tuple(sentences),
        sources=tuple(s for s in story.sources if reachable.get(s.url)),
    )
    return LinkCheck(checked, reachable, dropped, problems)
