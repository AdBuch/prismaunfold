"""Editorial editions are independent of the feed desk and topic reports."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .reports import public_url
from .linkcheck import http_status
from .storage import open_store

PUBLICATION = "morgenbriefing"
ACCESS = ("open", "excerpt", "paywalled", "unknown")
SECTIONS = ("Schweiz Politik", "Schweiz Gesellschaft", "Schweiz Regional",
            "Peru Politik", "Peru Gesellschaft", "Krisen- und Konfliktgebiete", "Reisen",
            "International", "Wirtschaft, Technologie & Wissenschaft", "Good News")
ASSESSMENTS = ("Wichtig", "Überschätzt", "Unterberichtet", "Beobachten")
MAX_BYTES = 512 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def string(value, limit):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, "Invalid text")
    return value.strip()


def excluded_domains():
    catalog = json.loads(Path(os.environ.get("EDITORIAL_CATALOG", "catalog/sources.json")).read_text(encoding="utf-8"))
    domains = {(urlsplit(item["feed_url"]).hostname or "").removeprefix("www.").removeprefix("feeds.")
               for item in catalog if item.get("ai_policy") == "exclude" and item.get("feed_url")}
    if "bbci.co.uk" in domains:
        domains.update(("bbc.com", "bbc.co.uk"))
    return domains


def validate(raw, probe=http_status, excluded=None):
    excluded = excluded_domains() if excluded is None else excluded
    require(isinstance(raw, dict) and raw.get("publication") == PUBLICATION, "Wrong publication")
    require(raw.get("provider") == "codex", "Wrong provider")
    day = string(raw.get("date"), 10)
    require(date.fromisoformat(day).isoformat() == day, "Invalid edition date")
    sources = raw.get("sources")
    require(isinstance(sources, list) and 2 <= len(sources) <= 80, "Invalid sources")
    source_map = {}
    for item in sources:
        require(isinstance(item, dict), "Invalid source")
        sid = string(item.get("id"), 60)
        url = public_url(item.get("url"))
        require(url is not None and sid not in source_map, "Invalid or duplicate source")
        host = urlsplit(url).hostname or ""
        require(not any(host == d or host.endswith("." + d) for d in excluded), "Source excluded by catalogue")
        access = item.get("access", "unknown")
        require(access in ACCESS, "Invalid access status")
        source_map[sid] = dict(id=sid, url=url, title=string(item.get("title"), 300),
                               publisher=string(item.get("publisher"), 120), access=access)
    cache = {}
    warnings = []
    def status(sid):
        source = source_map[sid]
        url = source["url"]
        if url not in cache:
            value = probe(url)
            cache[url] = ("reachable" if value else "missing") if isinstance(value, bool) else value
        source["link_status"] = cache[url]
        return cache[url]

    def refs(ids):
        unique = list(dict.fromkeys(ids))
        for sid in unique:
            state = status(sid)
            require(state != "unsafe_or_unresolved", f"Unsafe or unresolved source: {sid}")
        supported = any(source_map[s]["access"] != "paywalled" and status(s) == "reachable" for s in unique)
        return unique, supported

    def article(item, magazine=False):
        require(isinstance(item, dict), "Invalid article")
        section = "Magazin" if magazine else item.get("section")
        require(magazine or section in SECTIONS, "Unknown section")
        paragraphs = item.get("paragraphs")
        require(isinstance(paragraphs, list) and (4 if magazine else 2) <= len(paragraphs) <= 16,
                "Invalid paragraph count")
        result = []
        used = set()
        for para in paragraphs:
            require(isinstance(para, dict), "Invalid paragraph")
            body = string(para.get("text"), 4000)
            ids = para.get("source_ids")
            require(isinstance(ids, list) and 1 <= len(ids) <= 10 and
                    all(isinstance(s, str) and s in source_map for s in ids), "Unknown paragraph source")
            kept, supported = refs(ids)
            used.update(kept)
            p = dict(text=body, source_ids=kept, review_required=not supported)
            if para.get("heading"):
                p["heading"] = string(para["heading"], 160)
            result.append(p)
        words = sum(len(p["text"].split()) for p in result)
        require((350 if magazine else 65) <= words <= (1000 if magazine else 250), "Article length outside limits")
        out = dict(section=section, headline=string(item.get("headline"), 200),
                   lead=string(item.get("lead"), 600), paragraphs=result,
                   sources=[source_map[s] for s in sorted(used)],
                   review_required=any(p["review_required"] for p in result))
        topic = item.get('topic', '')
        if isinstance(topic, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', topic):
            out['topic'] = topic
        background = item.get("background", [])
        require(isinstance(background, list) and len(background) <= 5, "Invalid background")
        out["background"] = []
        for entry in background:
            try:
                extra = short_item(entry)
                extra["heading"] = string(entry.get("heading"), 120)
                out["background"].append(extra)
            except ValueError:
                continue
        return out

    def short_item(item):
        require(isinstance(item, dict), "Invalid short item")
        ids = item.get("source_ids")
        require(isinstance(ids, list) and 1 <= len(ids) <= 10 and
                all(isinstance(s, str) and s in source_map for s in ids), "Unknown short-item source")
        kept, supported = refs(ids)
        return dict(text=string(item.get("text"), 900), sources=[source_map[s] for s in kept], review_required=not supported)

    articles = raw.get("articles")
    require(isinstance(articles, list) and 6 <= len(articles) <= 16, "Need 6–16 news articles")
    good = []
    for idx, item in enumerate(articles):
        try:
            good.append(article(item))
        except ValueError as exc:
            warnings.append(f"Article {idx + 1} omitted: {exc}")
    require(len(good) >= 5 and len(good) * 2 >= len(articles), "Too few complete articles survived")
    try:
        magazine = article(raw.get("magazine"), True)
    except ValueError as exc:
        magazine = None
        warnings.append(f"Magazin zurueckgestellt: {exc}")
    require(len({a["section"] for a in good}) >= 3, "Insufficient section diversity")
    extras = {}
    if raw.get("random") is not None:
        try:
            extras["random"] = short_item(raw["random"])
        except ValueError as exc:
            warnings.append(f"Random omitted: {exc}")
    assessments = raw.get("lagebild", {})
    require(isinstance(assessments, dict) and all(k in ASSESSMENTS for k in assessments), "Invalid Lagebild")
    extras["lagebild"] = []
    for category in ASSESSMENTS:
        if category in assessments:
            try:
                extras["lagebild"].append(dict(category=category, **short_item(assessments[category])))
            except ValueError as exc:
                warnings.append(f"Lagebild {category} omitted: {exc}")
    for a in good + ([magazine] if magazine else []):
        if a["review_required"]:
            warnings.append("Quellenzugriff unvollstaendig: " + a["headline"])
    good.sort(key=lambda a: SECTIONS.index(a["section"]))
    covered = {a["section"] for a in good}
    missing = [section for section in SECTIONS if section not in covered]
    if missing:
        warnings.append("Keine veröffentlichte Meldung: " + ", ".join(missing))
    if "random" not in extras:
        warnings.append("Random des Tages fehlt")
    if len(extras["lagebild"]) != len(ASSESSMENTS):
        warnings.append("Lagebild ist unvollständig")
    return dict(publication=PUBLICATION, provider="codex", date=day, **extras,
                title="Morgenbriefing", articles=good, magazine=magazine, warnings=warnings,
                disclosure="KI-redaktionell erstellt. Quellenzugriff geprüft, nicht die Richtigkeit der Aussagen. Beiträge mit unzugänglichen Belegen sind als prüfbedürftig markiert.")


def editions(store):
    # Existing editions table; independent namespace, no changes to feed editions.
    rows = store.db.execute("SELECT data FROM editions WHERE id LIKE 'editorial|morgenbriefing|%' ORDER BY id DESC").fetchall()
    return [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in rows]


def export_editorial(store, site_dir, stories=None):
    from .bulletin import imports, merge_editions
    from .export import _write

    authored = editions(store)
    bulletins = imports(store)
    if bulletins:
        authored = merge_editions(authored, bulletins, store.all_stories() if stories is None else stories)
    return _write(Path(site_dir) / "api/v1/editorial/morgenbriefing.json", authored)


def main():
    mode = sys.argv[1]
    if mode == "bulletin-context":
        from .bulletin import editorial_context

        store = open_store(os.environ["DATABASE_URL"])
        try:
            print(json.dumps(editorial_context(store, sys.argv[2]), ensure_ascii=False))
        finally:
            store.close()
        return
    if mode == "history":
        store = open_store(os.environ["DATABASE_URL"])
        try:
            print(json.dumps([{"date": e["date"], "headlines": [{"section": a["section"], "headline": a["headline"], "topic": a.get("topic", "")} for a in e["articles"]],
                               "magazine": (e.get("magazine") or {}).get("headline", "")} for e in editions(store)[:7]], ensure_ascii=False))
        finally:
            store.close()
        return
    require(mode in ("validate", "publish"), "Unknown mode")
    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "Edition too large")
    payload = validate(json.loads(data))
    require(payload["date"] == sys.argv[2], "Edition date mismatch")
    if mode == "publish" and os.environ.get("EDITORIAL_AUTO") == "1":
        sections = {a["section"] for a in payload["articles"] if not a.get("review_required")}
        require(sum(not a.get("review_required") for a in payload["articles"]) >= 5,
                "Automatic publication refused: too few articles with reachable evidence")
        require(len(payload["articles"]) >= 8 and len(sections) >= 7 and
                {"Schweiz Politik", "Peru Politik", "International", "Good News"} <= sections and
                payload.get("magazine") and payload.get("random") and
                {x["category"] for x in payload["lagebild"]} == set(ASSESSMENTS),
                "Automatic publication refused: incomplete edition")
    if mode == "publish":
        store = open_store(os.environ["DATABASE_URL"])
        try:
            require(not any(e["date"] == payload["date"] for e in editions(store)),
                    "Edition already published; refusing to overwrite")
            store.save_edition("editorial|morgenbriefing|" + payload["date"], "de",
                               datetime.now(timezone.utc), payload)
            store.commit()
            export_editorial(store, "/site")
        finally:
            store.close()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
