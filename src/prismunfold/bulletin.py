"""Import the private morning bulletin and reconcile it with existing coverage."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from .normalize import sha1_id, title_key, tokens
from .reports import public_url

LOG = logging.getLogger(__name__)
API = "https://api.github.com/repos/AdBuch/prism-data"
ZONE = ZoneInfo("Europe/Zurich")
MAX_BYTES = 2 * 1024 * 1024
PUBLIC_STATUSES = {"published", "final"}
STAGED_STATUSES = {"draft", "test_import_unverified", "unverified"}
DISCLOSURE = "KI-kuratierte Sekundärquelle. Verweise und Einschätzungen wurden durch den Import nicht verifiziert."
LICENSE = re.compile(r"(?:CC[- ]BY(?:[- ]SA)?[- ]?[234](?:\.0)?|CC0(?:[- ]?1\.0)?|public[ -]domain)", re.I)


def obj(value):
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value


def items(value, limit=200):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError("invalid array")
    return value


def text(value, limit=16000, required=False):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError("invalid text field")
    return value.strip()


def link(value):
    url = public_url(value)
    if not url or "\\" in url:
        raise ValueError("invalid HTTP(S) URL")
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
        refs.setdefault(url, dict(id=sha1_id(url), url=url, title=url, publisher=urlsplit(url).hostname))
    return list(refs.values())


def perspectives(values):
    result = []
    for raw in items(values, 50):
        if isinstance(raw, str):
            result.append(dict(text=text(raw, required=True), label="", sources=[]))
        else:
            raw = obj(raw)
            result.append(dict(text=text(raw.get("text") or raw.get("body") or raw.get("assessment"), required=True),
                               label=text(raw.get("perspective") or raw.get("label") or raw.get("category") or raw.get("title"), 250),
                               attribution=text(raw.get("attribution") or raw.get("author"), 250),
                               sources=source_refs(raw)))
    return result


def image_metadata(raw):
    raw = obj(raw)
    url = raw.get("url") or raw.get("image_url")
    link(url)
    url = url.strip()  # Preserve signed image URLs byte-for-byte.
    rights = raw.get("rights")
    details = rights if isinstance(rights, dict) else {}
    license_name = text(raw.get("license") or details.get("license"), 250)
    credit = text(raw.get("credit") or raw.get("attribution") or details.get("credit"), 400)
    allowed = raw.get("display_allowed", details.get("display_allowed"))
    rights_status = text(details.get("status") if isinstance(rights, dict) else rights, 250)
    explicit = allowed is True or rights_status in ("approved", "licensed", "public_domain")
    blocked = allowed is False or rights_status in ("denied", "restricted", "unknown", "unlicensed")
    qualified = bool(license_name and LICENSE.fullmatch(license_name))
    # A credit and an explicit grant or recognised licence are required before embedding.
    display = (url.startswith("https://") and bool(credit) and not blocked
               and (explicit or qualified))
    return dict(url=url, alt=text(raw.get("alt"), 500), caption=text(raw.get("caption"), 700),
                credit=credit, license=license_name,
                rights=rights_status,
                rights_note=text(raw.get("rights_note") or details.get("note"), 700),
                source_url=link(raw["source_url"]) if raw.get("source_url") else "",
                license_url=link(raw["license_url"]) if raw.get("license_url") else "",
                display=display)


def article(raw, section):
    raw = obj(raw)
    sources = source_refs(raw)
    body = text(raw.get("body"), 30000, required=True)
    return {
        "external_id": text(raw.get("id"), 180, required=True),
        "section": section,
        "headline": text(raw.get("title"), 350, required=True),
        "lead": text(raw.get("lead"), 3000),
        # The upstream citations are item-level. Never turn them into paragraph-level claims.
        "paragraphs": [dict(text=p.strip(), source_ids=[])
                       for p in re.split(r"\n\s*\n", body) if p.strip()],
        "sources": sources,
        "uncertainties": [text(x, 2500, required=True) for x in items(raw.get("uncertainties"), 50)],
        "perspectives": perspectives(raw.get("assessments")) + perspectives(raw.get("perspectives")),
        "images": [image_metadata(x) for x in items(raw.get("images"), 30)],
        "origin": "prism-data",
    }


def validate(raw, day):
    raw = obj(raw)
    if raw.get("schema_version") not in ("1.0", "1.1"):
        raise ValueError("unsupported bulletin schema_version")
    if raw.get("date") != day or date.fromisoformat(day).isoformat() != day:
        raise ValueError("bulletin path and edition date do not match")
    if raw.get("timezone") != ZONE.key:
        raise ValueError("unexpected edition timezone")
    try:
        generated = datetime.fromisoformat(text(raw.get("generated_at"), 65, required=True))
    except ValueError:
        raise ValueError("invalid generated_at") from None
    if generated.utcoffset() is None:
        raise ValueError("generated_at must include a timezone")
    status = text(raw.get("publication_status"), 65, required=True)
    if status not in PUBLIC_STATUSES | STAGED_STATUSES:
        raise ValueError("unknown bulletin publication_status")
    news = []
    for section in items(raw.get("sections"), 60):
        section = obj(section)
        name = text(section.get("title"), 160, required=True)
        news.extend(article(item, name) for item in items(section.get("items")))
        if len(news) > 200:
            raise ValueError("too many bulletin articles")
    if raw.get("good_news") is not None:
        news.append(article(raw["good_news"], "Good News"))
    if not news:
        raise ValueError("bulletin needs news articles")
    magazine = article(raw["deep_dive"], "Magazin") if raw.get("deep_dive") is not None else None
    random = article(raw["random_fact"], "Random des Tages") if raw.get("random_fact") is not None else None
    ids = [item["external_id"] for item in [*news, magazine, random] if item]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate bulletin item ID")
    return dict(date=day, generated_at=generated.isoformat(), status=status,
                lead=text(raw.get("lead"), 5000), articles=news, magazine=magazine, random_article=random,
                outlook=perspectives(raw.get("outlook")), note=text(raw.get("editorial_note"), 5000))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(day: str, token: str) -> bytes | None:
    opener = build_opener(NoRedirect())

    def request(path, media):
        req = Request(API + path, headers={"Authorization": "Bearer " + token, "Accept": media,
                                            "User-Agent": "PrismUnfold", "X-GitHub-Api-Version": "2022-11-28"})
        return opener.open(req, timeout=12)

    try:
        with request(f"/contents/data/morgenbriefing/{day}.json?ref=main", "application/vnd.github.raw+json") as response:
            data = response.read(MAX_BYTES + 1)
    except HTTPError as error:
        if error.code != 404:
            raise
        error.close()
        # GitHub also uses 404 for inaccessible private resources.
        with request("/contents?ref=main", "application/vnd.github+json"):
            return None
    if len(data) > MAX_BYTES:
        raise ValueError("bulletin exceeds size limit")
    return data


def imports(store):
    rows = store.db.execute("SELECT data FROM editions WHERE id LIKE 'bulletin|morgenbriefing|%' ORDER BY id DESC").fetchall()
    return [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in rows]


def import_daily(store, secret_path, now, day=None, fetcher=fetch):
    local = now.astimezone(ZONE)
    if day is None and local.hour < 7:
        return False
    day = day or local.date().isoformat()
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("invalid date")
    try:
        token = Path(secret_path).read_text(encoding="utf-8").strip()
        if not token or len(token) > 512 or not re.fullmatch(r"[A-Za-z0-9_\-]+", token):
            raise ValueError("invalid secret file")
        data = fetcher(day, token)
    except HTTPError as error:
        error.close()
        raise ValueError(f"GitHub API returned HTTP {error.code}") from None
    except OSError:
        raise ValueError("cannot read import secret or contact GitHub") from None
    if data is None:
        LOG.info("prism-data date=%s waiting for bulletin", day)
        return False
    if len(data) > MAX_BYTES:
        raise ValueError("bulletin exceeds size limit")
    digest = hashlib.sha256(data).hexdigest()
    edition_id = "bulletin|morgenbriefing|" + day
    existing = store.get_edition(edition_id)
    if existing and existing["digest"] == digest:
        LOG.info("prism-data date=%s unchanged", day)
        return False
    try:
        raw = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError):
        raise ValueError("invalid bulletin JSON") from None
    payload = validate(raw, day)
    if existing and datetime.fromisoformat(existing["generated_at"]) > datetime.fromisoformat(payload["generated_at"]):
        LOG.warning("prism-data date=%s older revision ignored", day)
        return False
    changed = store.save_edition_revision(edition_id, "de",
                                          datetime.fromisoformat(payload["generated_at"]), dict(payload, digest=digest))
    store.commit()
    if not changed:
        LOG.info("prism-data date=%s already handled by another run", day)
        return False
    LOG.info("prism-data date=%s status=%s articles=%s imported", day, payload["status"], len(payload["articles"]))
    return True


def match_score(candidate, target):
    left, right = tokens(candidate["headline"]), tokens(target["headline"])
    common = len(left & right)
    if common >= 2 and title_key(candidate["headline"]) == title_key(target["headline"]):
        return 2.0
    overlap = common / max(1, len(left | right))
    shared = {s["url"] for s in candidate["sources"]} & {s["url"] for s in target["sources"]}
    if (shared and common >= 2 and overlap >= 0.28) or (common >= 4 and overlap >= 0.65):
        return overlap + bool(shared)
    return 0.0


def add_coverage(candidate, targets):
    ranked = sorted(((match_score(candidate, target), index) for index, target in enumerate(targets)), reverse=True)
    if not ranked or ranked[0][0] == 0 or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
        return False
    targets[ranked[0][1]].setdefault("coverage", []).append(candidate)
    return True


def story_context(story):
    """Existing reports retain only their own claims, publisher links and labels."""
    # Carry only the related story's own scoped evidence. The synthetic bulletin
    # never enters the feed scoring, verification, or publisher-counting path.
    return dict(section=story.topic, headline=story.headline, lead="", origin="prismunfold",
                story_slug=story.slug, verification=(story.verification or {}).get("state"),
                paragraphs=[dict(text=s.text, source_ids=[sha1_id(url) for url in s.source_urls])
                            for s in story.sentences],
                sources=[dict(id=sha1_id(s.url), url=s.url, title=s.title, publisher=s.publisher,
                              published_at=s.published_at) for s in story.sources],
                uncertainties=list(story.uncertainties) + list(story.disputes))


def merge_editions(authored, bulletins, stories):
    by_day = {e["date"]: e for e in authored}
    supplemental = {e["date"]: e for e in bulletins if e["status"] in PUBLIC_STATUSES}
    story_days = {}
    for story in stories:
        if story.language == "de" and story.sentences and not story.nothing_new and story.day in supplemental:
            story_days.setdefault(story.day, []).append(story)

    for day, bulletin in supplemental.items():
        existing = by_day.get(day)
        targets = [dict(item) for item in existing["articles"]] if existing else []
        additional = []
        for item in bulletin["articles"]:
            if not add_coverage(item, targets + additional):
                additional.append(dict(item))
        magazine = dict(existing["magazine"]) if existing and existing.get("magazine") else None
        other_magazines = []
        if bulletin["magazine"]:
            if magazine is None:
                magazine = dict(bulletin["magazine"])
            elif not add_coverage(bulletin["magazine"], [magazine]):
                other_magazines.append(dict(bulletin["magazine"]))
        for story in story_days.get(day, []):
            add_coverage(story_context(story), targets + additional + ([magazine] if magazine else []) + other_magazines)
        by_day[day] = {
            **(existing or dict(date=day, title="Morgenbriefing", warnings=[], disclosure=DISCLOSURE)),
            "articles": targets if existing else additional,
            "additional_articles": additional if existing else [],
            "magazine": magazine,
            "additional_magazines": other_magazines,
            "bulletin": dict(lead=bulletin["lead"], note=bulletin["note"], outlook=bulletin["outlook"],
                             random_article=bulletin["random_article"], disclosure=DISCLOSURE),
        }
    return [by_day[day] for day in sorted(by_day, reverse=True)]


def editorial_context(store, day):
    previous = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    editions = (store.get_edition("bulletin|morgenbriefing|" + date) for date in (day, previous))
    match = next((e for e in editions if e and e["status"] in PUBLIC_STATUSES), None)
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
