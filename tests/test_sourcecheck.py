"""Source accessibility checks: classification, retries, cache and SSRF rules (no network)."""
import socket
import unittest

from prismunfold import linkcheck
from prismunfold.linkcheck import SourceCheckCache, check_source


def resolver(table):
    def resolve(host, port, proto=0):
        if host not in table:
            raise socket.gaierror("Name or service not known")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0)) for address in table[host]]
    return resolve


PUBLIC = resolver({"apnews.com": ["104.18.1.1"], "www.admin.ch": ["162.23.1.1"],
                   "evil.example.com": ["93.184.216.34"], "internal.example.com": ["10.0.0.5"],
                   "mixed.example.com": ["93.184.216.34", "127.0.0.1"]})


def transport(responses):
    """responses: {(method, url): (code, location) | Exception}; records calls."""
    calls = []

    def send(method, url, address, timeout):
        calls.append((method, url, address))
        result = responses.get((method, url), responses.get(("*", url)))
        if isinstance(result, BaseException):
            raise result
        return result
    send.calls = calls
    return send


def check(url, responses, **kw):
    send = transport(responses)
    kw.setdefault("sleep", lambda s: None)
    return check_source(url, transport=send, resolver=PUBLIC, **kw), send.calls


class ClassificationTests(unittest.TestCase):
    def test_http_200(self):
        result, calls = check("https://www.admin.ch/a", {("HEAD", "https://www.admin.ch/a"): (200, "")})
        self.assertEqual(result.status, "reachable")
        self.assertEqual(calls[0][2], "162.23.1.1")  # connection pinned to the vetted address

    def test_http_403_on_head_and_get_is_restricted_not_missing(self):
        # The AP News case of 25 November 2026.
        url = "https://apnews.com/article/x"
        result, calls = check(url, {("*", url): (403, "")})
        self.assertEqual(result.status, "restricted")
        self.assertEqual([c[0] for c in calls], ["HEAD", "GET"])
        self.assertFalse(result.transient)

    def test_head_refused_but_get_ok(self):
        url = "https://apnews.com/article/y"
        result, _ = check(url, {("HEAD", url): (405, ""), ("GET", url): (200, "")})
        self.assertEqual(result.status, "reachable")

    def test_http_404_and_410_are_missing(self):
        for code in (404, 410):
            url = f"https://www.admin.ch/{code}"
            self.assertEqual(check(url, {("*", url): (code, "")})[0].status, "missing")

    def test_http_429_is_rate_limited_and_retried_with_backoff(self):
        url = "https://www.admin.ch/busy"
        sleeps = []
        result, calls = check(url, {("*", url): (429, "")}, sleep=sleeps.append, attempts=3, backoff=1.0)
        self.assertEqual(result.status, "rate_limited")
        self.assertEqual(result.attempts, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_http_500_is_unavailable_and_recovers_on_retry(self):
        url = "https://www.admin.ch/flaky"
        state = {"n": 0}

        def send(method, u, address, timeout):
            state["n"] += 1
            return (500, "") if state["n"] <= 1 else (200, "")
        result = check_source(url, transport=send, resolver=PUBLIC, sleep=lambda s: None)
        self.assertEqual(result.status, "reachable")
        self.assertEqual(result.attempts, 2)

    def test_timeout(self):
        url = "https://www.admin.ch/slow"
        result, _ = check(url, {("*", url): socket.timeout("timed out")}, attempts=2)
        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.attempts, 2)

    def test_dns_failure_is_not_unsafe(self):
        result, calls = check("https://no-such-host.example.org/x", {}, attempts=1)
        self.assertEqual(result.status, "dns_failure")
        self.assertEqual(calls, [])

    def test_private_address_is_unsafe_and_never_contacted(self):
        for url in ("https://internal.example.com/x", "https://mixed.example.com/x", "http://127.0.0.1/admin",
                    "file:///etc/passwd", "https://user:pw@www.admin.ch/"):
            result, calls = check(url, {}, attempts=1)
            self.assertEqual(result.status, "unsafe", url)
            self.assertEqual(calls, [], url)

    def test_unsafe_redirect_target_is_not_followed(self):
        url = "https://evil.example.com/r"
        result, calls = check(url, {("*", url): (302, "http://internal.example.com/secret")})
        self.assertEqual(result.status, "unsafe")
        self.assertEqual({c[1] for c in calls}, {url})

    def test_public_redirect_is_followed_and_revalidated(self):
        url = "https://evil.example.com/r"
        result, calls = check(url, {("*", url): (301, "https://www.admin.ch/final"),
                                    ("HEAD", "https://www.admin.ch/final"): (200, "")})
        self.assertEqual(result.status, "reachable")
        self.assertEqual(result.final_url, "https://www.admin.ch/final")
        self.assertEqual(calls[-1][2], "162.23.1.1")

    def test_redirect_loop_is_bounded(self):
        url = "https://evil.example.com/loop"
        result, calls = check(url, {("*", url): (302, url)}, attempts=1)
        self.assertEqual(result.status, "unsafe")
        self.assertLessEqual(len(calls), linkcheck.MAX_REDIRECTS + 1)

    def test_legacy_probe_helpers(self):
        self.assertFalse(linkcheck.http_probe("http://127.0.0.1:8080/admin"))
        self.assertFalse(linkcheck.is_public_host("localhost"))


class CacheTests(unittest.TestCase):
    def test_cache_avoids_repeated_requests_and_expires_transient_results_sooner(self):
        now = [1000.0]
        cache = SourceCheckCache(clock=lambda: now[0], ttl=3600, transient_ttl=60)
        hits = []

        def fake(url):
            hits.append(url)
            return linkcheck.SourceCheck(url, "timeout" if "slow" in url else "restricted")
        probe = cache.probe(fake)
        for _ in range(3):
            self.assertEqual(probe("https://apnews.com/x"), "restricted")
            self.assertEqual(probe("https://slow.example.org/"), "timeout")
        self.assertEqual(len(hits), 2)
        now[0] += 120
        probe("https://apnews.com/x"), probe("https://slow.example.org/")
        self.assertEqual(hits.count("https://slow.example.org/"), 2)
        self.assertEqual(hits.count("https://apnews.com/x"), 1)

    def test_cache_persists_atomically(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checks.json"
            cache = SourceCheckCache(path)
            cache.put(linkcheck.SourceCheck("https://a.example.org/", "reachable", 200))
            cache.save()
            self.assertEqual(SourceCheckCache(path).get("https://a.example.org/").status, "reachable")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["checks.json"])


if __name__ == "__main__":
    unittest.main()
