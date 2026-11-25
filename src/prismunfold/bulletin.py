"""Import the private prism-data morning bulletin and reconcile it with existing coverage.

Source: GitHub repository AdBuch/prism-data, branch main,
path data/morgenbriefing/YYYY-MM-DD.json, available daily from 07:00 Europe/Zurich.

The bulletin is an AI-curated *secondary* source. Importing it needs no model call,
never changes its upstream publication status, never counts as independent
confirmation of a claim, and never invents missing URLs, credits or dates. Its
citations are item-level; they are never turned into paragraph-level claims.

Publication: upstream `published`/`final` bulletins are composed into the daily
edition. `draft`, `unverified` and `test_import_unverified` are stored for review
only, unless an operator records an explicit approval bound to the exact content
hash (`review_bulletin`). A new revision needs a new approval.

Every received revision is kept as a contribution (raw document, content hash,
state). Identical content is a no-op; an older revision never replaces a newer one.
A missing bulletin, a bad document, an auth failure or a GitHub outage raises a
`BulletinError` with an error code; callers log it and the rest of the pipeline goes on.
"""
from __future__ import annotations

import json
import re
import socket
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from . import contributions as contrib
from .dedupe import add_coverage
from .images import image_metadata
from .normalize import sha1_id
from .oplog import event
from .reports import public_url

API = "https://api.github.com/repos/AdBuch/prism-data"
PATH = "data/morgenbriefing/{day}.json"
ZONE = ZoneInfo("Europe/Zurich")
AVAILABLE_FROM_HOUR = 7
MAX_BYTES = 2 * 1024 * 1024
SCHEMA_VERSIONS = ("1.0", "1.1")
PUBLIC_STATUSES = {"published", "final"}
STAGED_STATUSES = {"draft", "test_import_unverified", "unverified"}
EDITION_PREFIX = "bulletin|morgenbriefing|"
SOURCE_KEY = "prism-data/morgenbriefing/"
DISCLOSURE = "KI-kuratierte Sekundärquelle. Verweise und Einschätzungen wurden durch den Import nicht verifiziert."
COMPONENT = "bulletin"


class BulletinError(ValueError):
    """An import failure with a stable error code (see docs/PRISM_DATA.md)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def obj(value):
    if not isinstance(value, dict):
        raise BulletinError("invalid_document", "expected an object")
    return value


def items(value, limit=200):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise BulletinError("invalid_document", "invalid array")
    return value


def text(value, limit=16000, required=False):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise BulletinError("invalid_document", "invalid text field")
    return value.strip()


def link(value):
    url = public_url(value)
    if not url or "\\" in url:
        raise BulletinError("invalid_document", "invalid HTTP(S) URL")
    return url


def source_refs(item):
    refs = {}
    for raw in items(item.get("sources")):
        raw = obj(raw)
        url = link(raw.get("url"))
        refs[url] = dict(id=sha1_id(url), url=url, title=text(raw.get("title"), 700) or url,
                         publisher=text(raw.get("publisher"), 200) or urlsplit(url).hostname,
                         published_at=text(raw.get("published_at"), 80),
                         source_type=text(raw.get("source_type"), 100),
                         access=text(raw.get("access"), 80))
    for raw in items(item.get("source_urls")):
        url = link(raw)
        refs.setdefault(url, dict(id=sha1_id(url), url=url, title=url, publisher=urlsplit(url).hostname,
                                  published_at="", source_type="", access=""))
    return list(refs.values())


def perspectives(values):
    result = []
    for raw in items(values, 50):
        if isinstance(raw, str):
            result.append(dict(text=text(raw, required=True), label="", attribution="", sources=[]))
        else:
            raw = obj(raw)
            result.append(dict(text=text(raw.get("text") or raw.get("body") or raw.get("assessment"), required=True),
                               label=text(raw.get("perspective") or raw.get("label") or raw.get("category") or raw.get("title"), 250),
                               attribution=text(raw.get("attribution") or raw.get("author"), 250),
                               sources=source_refs(raw)))
    return result


def images_of(raw):
    try:
        return [image_metadata(x) for x in items(raw.get("images"), 30)]
    except ValueError as exc:
        raise BulletinError("invalid_document", f"invalid HTTP(S) URL or image field: {exc}") from None


def article(raw, section, day, kind="news"):
    raw = obj(raw)
    sources = source_refs(raw)
    body = text(raw.get("body"), 30000, required=True)
    external_id = text(raw.get("id"), 180, required=True)
    uncertainties = [text(x, 2500, required=True) for x in items(raw.get("uncertainties"), 50)]
    return {
        "article_id": f"pd-{day}-{sha1_id(external_id)[:10]}",
        "external_id": external_id,
        "kind": kind,
        "section": section,
        "headline": text(raw.get("title"), 350, required=True),
        "lead": text(raw.get("lead"), 3000),
        # Upstream citations are item-level. Never turn them into paragraph-level claims.
        "citation_level": "item",
        "paragraphs": [dict(text=p.strip(), source_ids=[])
                       for p in re.split(r"\n\s*\n", body) if p.strip()],
        "sources": sources,
        "uncertainties": uncertainties,
        "perspectives": perspectives(raw.get("assessments")) + perspectives(raw.get("perspectives")),
        "images": images_of(raw),
        "origin": "prism-data",
        "date": day,
        # Limitations the reader must see: no original sources means nothing to check against.
        "limitations": [] if sources else ["no_original_sources"],
    }


def validate(raw, day):
    """Normalise a bulletin document. Raises BulletinError for anything invalid."""
    raw = obj(raw)
    if raw.get("schema_version") not in SCHEMA_VERSIONS:
        raise BulletinError("unsupported_schema", "unsupported bulletin schema_version")
    try:
        valid_day = date.fromisoformat(day).isoformat() == day
    except (TypeError, ValueError):
        valid_day = False
    if raw.get("date") != day or not valid_day:
        raise BulletinError("invalid_document", "bulletin path and edition date do not match")
    if raw.get("timezone") != ZONE.key:
        raise BulletinError("invalid_document", "unexpected edition timezone")
    try:
        generated = datetime.fromisoformat(text(raw.get("generated_at"), 65, required=True))
    except ValueError:
        raise BulletinError("invalid_document", "invalid generated_at") from None
    if generated.utcoffset() is None:
        raise BulletinError("invalid_document", "generated_at must include a timezone")
    status = text(raw.get("publication_status"), 65, required=True)
    if status not in PUBLIC_STATUSES | STAGED_STATUSES:
        raise BulletinError("invalid_document", "unknown bulletin publication_status")
    news, rubrics = [], []
    for section in items(raw.get("sections"), 60):
        section = obj(section)
        name = text(section.get("title"), 160, required=True)
        rubrics.append(name)
        news.extend(article(item, name, day) for item in items(section.get("items")))
        if len(news) > 200:
            raise BulletinError("invalid_document", "too many bulletin articles")
    if raw.get("good_news") is not None:
        news.append(article(raw["good_news"], "Good News", day, kind="good_news"))
    if not news:
        raise BulletinError("invalid_document", "bulletin needs news articles")
    magazine = article(raw["deep_dive"], "Magazin", day, kind="magazine") if raw.get("deep_dive") is not None else None
    random = article(raw["random_fact"], "Random des Tages", day, kind="random") if raw.get("random_fact") is not None else None
    ids = [item["external_id"] for item in [*news, magazine, random] if item]
    if len(ids) != len(set(ids)):
        raise BulletinError("invalid_document", "duplicate bulletin item ID")
    cutoff = raw.get("editorial_cutoff")
    return dict(date=day, schema_version=raw["schema_version"], generated_at=generated.isoformat(),
                editorial_cutoff=text(cutoff, 65) if cutoff is not None else "",
                status=status, lead=text(raw.get("lead"), 5000), rubrics=rubrics, articles=news,
                magazine=magazine, random_article=random, outlook=perspectives(raw.get("outlook")),
                note=text(raw.get("editorial_note"), 5000))


class NoRedirect(HTTPRedirectHandler):
    """Never follow redirects: the Authorization header must not reach another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(day: str, token: str) -> bytes | None:
    """The bulletin bytes, or None when the file does not exist (yet). Raises BulletinError."""
    opener = build_opener(NoRedirect())

    def request(path, media):
        req = Request(API + path, headers={"Authorization": "Bearer " + token, "Accept": media,
                                            "User-Agent": "PrismUnfold", "X-GitHub-Api-Version": "2022-11-28"})
        return opener.open(req, timeout=12)

    try:
        try:
            with request(f"/contents/{PATH.format(day=day)}?ref=main", "application/vnd.github.raw+json") as response:
                data = response.read(MAX_BYTES + 1)
        except HTTPError as error:
            if error.code != 404:
                raise
            error.close()
            # GitHub also answers 404 for private resources the token may not read.
            with request("/contents?ref=main", "application/vnd.github+json"):
                return None
    except HTTPError as error:
        code = error.code
        error.close()
        if code in (401, 404):
            raise BulletinError("auth_failed", f"GitHub API returned HTTP {code}; check token scope and expiry") from None
        if code == 403 or code == 429:
            raise BulletinError("github_unavailable", f"GitHub API refused or rate-limited the request (HTTP {code})") from None
        if 300 <= code < 400:
            raise BulletinError("github_unavailable", f"GitHub API redirected (HTTP {code}); not followed") from None
        raise BulletinError("github_unavailable", f"GitHub API returned HTTP {code}") from None
    except (URLError, socket.timeout, TimeoutError, OSError):
        raise BulletinError("github_unavailable", "cannot contact GitHub") from None
    if len(data) > MAX_BYTES:
        raise BulletinError("too_large", "bulletin exceeds size limit")
    return data


def read_secret(secret_path) -> str:
    try:
        token = Path(secret_path).read_text(encoding="utf-8").strip()
    except OSError:
        raise BulletinError("secret_unreadable", "cannot read the prism-data token file") from None
    if not token or len(token) > 512 or not re.fullmatch(r"[A-Za-z0-9_\-]+", token):
        raise BulletinError("secret_unreadable", "invalid secret file")
    return token


def imports(store):
    rows = store.db.execute("SELECT data FROM editions WHERE id LIKE 'bulletin|morgenbriefing|%' ORDER BY id DESC").fetchall()
    return [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in rows]


def due(now: datetime, day: str | None = None) -> tuple[bool, str]:
    """(is the bulletin for `day` expected yet, the day). Default day: today in Zurich."""
    local = now.astimezone(ZONE)
    if day is None:
        return local.hour >= AVAILABLE_FROM_HOUR, local.date().isoformat()
    return True, day


def import_document(store, day: str, data: bytes, *, received_at: str | None = None) -> str:
    """Store one bulletin document. Returns imported | unchanged | older_revision | already_handled."""
    if len(data) > MAX_BYTES:
        raise BulletinError("too_large", "bulletin exceeds size limit")
    digest = contrib.content_hash(data)
    edition_id = EDITION_PREFIX + day
    existing = store.get_edition(edition_id)
    if existing and existing["digest"] == digest:
        return "unchanged"
    try:
        raw = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError, UnicodeDecodeError):
        raise BulletinError("invalid_json", "invalid bulletin JSON") from None
    payload = validate(raw, day)
    record = contrib.new("prism-data", SOURCE_KEY + day, day, digest, generated_at=payload["generated_at"],
                         upstream_status=payload["status"], kind="bulletin", raw=raw, normalised=None,
                         state="normalised", received_at=received_at,
                         limitations=["ai_curated_secondary", "item_level_citations"])
    older = bool(existing and datetime.fromisoformat(existing["generated_at"]) > datetime.fromisoformat(payload["generated_at"]))
    if older:
        # Keep the late, older revision for provenance; it never replaces the newer one.
        contrib.transition(record, "superseded", note="older than the stored revision")
        store.save_contribution(record)
        store.commit()
        return "older_revision"
    changed = store.save_edition_revision(edition_id, "de", datetime.fromisoformat(payload["generated_at"]),
                                          dict(payload, digest=digest, contribution_id=record["id"]))
    if not changed:
        store.commit()
        return "already_handled"
    contrib.transition(record, "validated" if payload["status"] in PUBLIC_STATUSES else "review_required",
                       note=f"upstream publication_status={payload['status']}")
    store.save_contribution(record)
    for previous in store.list_contributions(source_key=SOURCE_KEY + day):
        if previous["id"] != record["id"] and previous["state"] != "superseded":
            store.update_contribution(contrib.transition(previous, "superseded", note=f"replaced by {record['id']}"))
    store.commit()
    return "imported"


def import_day(store, secret_path, now: datetime, day: str | None = None, fetcher=fetch) -> str:
    """Fetch and import one day. Returns not_due | waiting | imported | unchanged | older_revision | already_handled."""
    is_due, day = due(now, day)
    if not is_due:
        return "not_due"
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError:
        raise BulletinError("invalid_date", "invalid date") from None
    started = time.monotonic()
    event(COMPONENT, "import_started", provider="prism-data", edition_date=day)
    try:
        data = fetcher(day, read_secret(secret_path))
        if data is None:
            outcome = "waiting"
        else:
            with store.lock("edition-publication"):
                outcome = import_document(store, day, data)
    except BulletinError as error:
        event(COMPONENT, "import_failed", level=40, provider="prism-data", edition_date=day,
              error_code=error.code, status="failed", reason=str(error),
              duration_ms=int((time.monotonic() - started) * 1000))
        raise
    names = {"waiting": "import_waiting", "imported": "import_completed"}
    current = store.get_edition(EDITION_PREFIX + day) or {}
    event(COMPONENT, names.get(outcome, "import_unchanged"), provider="prism-data", edition_date=day,
          status=outcome, upstream_status=current.get("status"),
          duration_ms=int((time.monotonic() - started) * 1000),
          articles=len(current.get("articles", [])) if outcome == "imported" else None)
    return outcome


def import_daily(store, secret_path, now, day=None, fetcher=fetch) -> bool:
    """Compatibility wrapper: True when a new revision was stored."""
    return import_day(store, secret_path, now, day, fetcher) == "imported"


def import_range(store, secret_path, start: str, end: str, fetcher=fetch) -> dict[str, str]:
    """Backfill [start, end]. One failing day is recorded and does not stop the others."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first or (last - first).days > 366:
        raise BulletinError("invalid_date", "backfill range must be 1–367 days, start before end")
    results = {}
    day = first
    while day <= last:
        try:
            results[day.isoformat()] = import_day(store, secret_path, datetime.now(ZONE), day.isoformat(), fetcher)
        except BulletinError as error:
            results[day.isoformat()] = f"failed:{error.code}"
        day += timedelta(days=1)
    return results


def review_bulletin(store, day: str, decision: str, reviewer: str, note: str = "") -> dict:
    """Record an operator decision on the stored revision; bound to its content hash.

    `approved` lets a staged bulletin (draft/unverified/test import) into the edition,
    labelled as manually approved; `rejected` withholds even an upstream-published one.
    The upstream publication_status itself is never changed.
    """
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be approved or rejected")
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    edition_id = EDITION_PREFIX + day
    with store.lock("edition-publication"):
        current = store.get_edition(edition_id)
        if not current:
            raise ValueError(f"no imported bulletin for {day}")
        current["review"] = dict(decision=decision, reviewer=reviewer.strip()[:120], note=note[:1000],
                                 digest=current["digest"], at=contrib.now_iso())
        store.save_edition(edition_id, "de", datetime.fromisoformat(current["generated_at"]), current)
        record = store.get_contribution(current.get("contribution_id", ""))
        if record:
            store.update_contribution(contrib.transition(record, decision, by=reviewer.strip()[:120], note=note[:300]))
        store.commit()
    event(COMPONENT, "article_approved" if decision == "approved" else "article_rejected", provider="prism-data",
          edition_date=day, status=decision, contribution_id=current.get("contribution_id"))
    return current


def publication_basis(bulletin: dict) -> str | None:
    """Why a stored bulletin may appear publicly, or None when it must stay internal."""
    review = bulletin.get("review") or {}
    current_review = review.get("digest") == bulletin.get("digest")
    if current_review and review.get("decision") == "rejected":
        return None
    if bulletin["status"] in PUBLIC_STATUSES:
        return "upstream_published"
    if current_review and review.get("decision") == "approved":
        return "manually_approved"
    return None


def story_context(story):
    """Existing reports retain only their own claims, publisher links and labels."""
    # Carry only the related story's own scoped evidence. The synthetic bulletin
    # never enters the feed scoring, verification, or publisher-counting path.
    return dict(section=story.topic, headline=story.headline, lead="", origin="prismunfold",
                story_slug=story.slug, verification=(story.verification or {}).get("state"),
                date=story.day,
                paragraphs=[dict(text=s.text, source_ids=[sha1_id(url) for url in s.source_urls])
                            for s in story.sentences],
                sources=[dict(id=sha1_id(s.url), url=s.url, title=s.title, publisher=s.publisher,
                              published_at=s.published_at) for s in story.sources],
                uncertainties=list(story.uncertainties) + list(story.disputes))


def _labelled(item: dict, basis: str, bulletin: dict) -> dict:
    out = dict(item)
    out["provenance"] = dict(provider="prism-data", origin_type="ai_secondary", publication_basis=basis,
                             upstream_status=bulletin["status"], generated_at=bulletin["generated_at"],
                             content_hash=bulletin.get("digest", ""), citation_level="item",
                             contribution_id=bulletin.get("contribution_id", ""))
    return out


def merge_editions(authored, bulletins, stories):
    by_day = {e["date"]: e for e in authored}
    supplemental = {}
    for bulletin in bulletins:
        basis = publication_basis(bulletin)
        if basis:
            supplemental[bulletin["date"]] = (bulletin, basis)
    story_days = {}
    for story in stories:
        if story.language == "de" and story.sentences and not story.nothing_new and story.day in supplemental:
            story_days.setdefault(story.day, []).append(story)

    for day, (bulletin, basis) in supplemental.items():
        existing = by_day.get(day)
        targets = [dict(item) for item in existing["articles"]] if existing else []
        additional = []
        for item in bulletin["articles"]:
            item = _labelled(item, basis, bulletin)
            if not add_coverage(item, targets + additional):
                additional.append(dict(item))
        magazine = dict(existing["magazine"]) if existing and existing.get("magazine") else None
        other_magazines = []
        if bulletin["magazine"]:
            feature = _labelled(bulletin["magazine"], basis, bulletin)
            if magazine is None:
                magazine = feature
            elif not add_coverage(feature, [magazine]):
                other_magazines.append(feature)
        for story in story_days.get(day, []):
            add_coverage(story_context(story), targets + additional + ([magazine] if magazine else []) + other_magazines)
        disclosure = DISCLOSURE + (" Manuell zur Veröffentlichung freigegeben; Upstream-Status: "
                                   + bulletin["status"] + "." if basis == "manually_approved" else "")
        by_day[day] = {
            **(existing or dict(date=day, title="Morgenbriefing", warnings=[], disclosure=disclosure)),
            "articles": targets if existing else additional,
            "additional_articles": additional if existing else [],
            "magazine": magazine,
            "additional_magazines": other_magazines,
            "bulletin": dict(lead=bulletin["lead"], note=bulletin["note"], outlook=bulletin["outlook"],
                             random_article=_labelled(bulletin["random_article"], basis, bulletin) if bulletin["random_article"] else None,
                             rubrics=bulletin.get("rubrics", []), editorial_cutoff=bulletin.get("editorial_cutoff", ""),
                             publication_basis=basis, upstream_status=bulletin["status"],
                             generated_at=bulletin["generated_at"], disclosure=disclosure),
        }
    return [by_day[day] for day in sorted(by_day, reverse=True)]


def editorial_context(store, day):
    previous = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    editions = (store.get_edition(EDITION_PREFIX + d) for d in (day, previous))
    match = next((e for e in editions if e and publication_basis(e)), None)
    if not match:
        return {}
    # Yesterday's bulletin is continuity context for the 06:00 edition. After
    # 07:00 the current edition becomes an additional source for manual runs.
    return {
        "role": "KI-kuratierte Sekundärquelle; keine unabhängige Bestätigung.",
        "date": match["date"],
        "items": [
            dict(section=a["section"], headline=a["headline"],
                 original_urls=[s["url"] for s in a["sources"]], uncertainties=a["uncertainties"])
            for a in [*match["articles"], match["magazine"]] if a
        ],
    }
