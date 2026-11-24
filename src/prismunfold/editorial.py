"""Editorial editions are independent of the feed desk and topic reports."""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .reports import public_url
from .linkcheck import http_probe
from .storage import open_store

PUBLICATION = "morgenbriefing"
DOMAINS = ("admin.ch", "parlament.ch", "ch.ch", "gob.pe", "un.org", "who.int",
           "europa.eu", "imf.org", "worldbank.org")
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


def read_sources(sources):
    require(isinstance(sources, list) and 2 <= len(sources) <= 80, "Invalid sources")
    source_map = {}
    for item in sources:
        require(isinstance(item, dict), "Invalid source")
        sid = string(item.get("id"), 60)
        url = public_url(item.get("url"))
        require(url is not None and sid not in source_map, "Invalid or duplicate source")
        host = urlsplit(url).hostname or ""
        require(any(host == d or host.endswith("." + d) for d in DOMAINS), "Source outside allowlist")
        source_map[sid] = dict(id=sid, url=url, title=string(item.get("title"), 300),
                               publisher=string(item.get("publisher"), 120))
    require(len({source["url"] for source in source_map.values()}) == len(source_map), "Duplicate source URL")
    return source_map


def prepare_research(raw, probe=http_probe):
    """Keep only evidence that the writing pass can cite."""
    require(isinstance(raw, dict), "Invalid research")
    sources = read_sources(raw.get("sources"))
    dossiers = raw.get("dossiers")
    require(isinstance(dossiers, list) and len(dossiers) <= 30, "Invalid dossiers")
    reachable = {sid for sid, source in sources.items() if probe(source["url"])}
    kept = []
    used = set()
    for dossier in dossiers:
        require(isinstance(dossier, dict), "Invalid dossier")
        section = string(dossier.get("section"), 80)
        subject = string(dossier.get("subject"), 200)
        notes = dossier.get("notes")
        require(isinstance(notes, list) and 1 <= len(notes) <= 30, "Invalid research notes")
        usable = []
        for note in notes:
            require(isinstance(note, dict), "Invalid note")
            text = string(note.get("text"), 1800)
            ids = note.get("source_ids")
            require(isinstance(ids, list) and 1 <= len(ids) <= 10 and
                    all(isinstance(sid, str) and sid in sources for sid in ids), "Unknown research source")
            # A note can combine distinct claims from its cited documents.
            if set(ids) <= reachable:
                usable.append(dict(text=text, source_ids=ids))
                used.update(ids)
        if usable:
            kept.append(dict(section=section, subject=subject, notes=usable))
    require(sum(d["section"] in SECTIONS for d in kept) >= 6, "Research needs six sourced news dossiers")
    require(any(d["section"] == "Magazin" and len({sid for note in d["notes"]
                                                 for sid in note["source_ids"]}) >= 2 for d in kept),
            "Magazine research needs two reachable documents")
    return dict(sources=[sources[sid] for sid in sorted(used)], dossiers=kept)


def validate(raw, probe=http_probe):
    require(isinstance(raw, dict) and raw.get("publication") == PUBLICATION, "Wrong publication")
    require(raw.get("provider") == "codex", "Wrong provider")
    day = string(raw.get("date"), 10)
    require(date.fromisoformat(day).isoformat() == day, "Invalid edition date")
    source_map = read_sources(raw.get("sources"))
    cache = {}
    def reachable(sid):
        url = source_map[sid]["url"]
        if url not in cache:
            cache[url] = bool(probe(url))
        return cache[url]

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
            kept = list(dict.fromkeys(s for s in ids if reachable(s)))
            # Never silently remove paragraphs from coherent prose.
            require(bool(kept), "Paragraph has no reachable cited source")
            used.update(kept)
            p = dict(text=body, source_ids=kept)
            if para.get("heading"):
                p["heading"] = string(para["heading"], 160)
            result.append(p)
        words = sum(len(p["text"].split()) for p in result)
        require((350 if magazine else 65) <= words <= (1000 if magazine else 250), "Article length outside limits")
        out = dict(section=section, headline=string(item.get("headline"), 200),
                   lead=string(item.get("lead"), 600), paragraphs=result,
                   sources=[source_map[s] for s in sorted(used)])
        return out

    def short_item(item):
        require(isinstance(item, dict), "Invalid short item")
        ids = item.get("source_ids")
        require(isinstance(ids, list) and 1 <= len(ids) <= 10 and
                all(isinstance(s, str) and s in source_map for s in ids), "Unknown short-item source")
        kept = list(dict.fromkeys(s for s in ids if reachable(s)))
        require(bool(kept), "Short item has no reachable source")
        return dict(text=string(item.get("text"), 900), sources=[source_map[s] for s in kept])

    articles = raw.get("articles")
    require(isinstance(articles, list) and 6 <= len(articles) <= 12, "Need 6–12 news articles")
    good, warnings = [], []
    for idx, item in enumerate(articles):
        try:
            good.append(article(item))
        except ValueError as exc:
            warnings.append(f"Article {idx + 1} omitted: {exc}")
    require(len(good) >= 5 and len(good) * 2 >= len(articles), "Too few complete articles survived")
    magazine = article(raw.get("magazine"), True)
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
    return dict(publication=PUBLICATION, provider="codex", date=day, **extras,
                title="Morgenbriefing", articles=good, magazine=magazine, warnings=warnings,
                disclosure="KI-redaktionell erstellt. Quellenlinks geprüft; Aussagen nicht unabhängig verifiziert.")


def editions(store):
    # Existing editions table; independent namespace, no changes to feed editions.
    rows = store.db.execute("SELECT data FROM editions WHERE id LIKE 'editorial|morgenbriefing|%' ORDER BY id DESC").fetchall()
    return [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in rows]


def export_editorial(store, site_dir):
    from .export import _write
    return _write(Path(site_dir) / "api/v1/editorial/morgenbriefing.json", editions(store))


def main():
    mode = sys.argv[1]
    if mode == "history":
        store = open_store(os.environ["DATABASE_URL"])
        try:
            print(json.dumps([{"date": e["date"], "headlines": [{"section": a["section"], "headline": a["headline"]} for a in e["articles"]],
                               "magazine": e["magazine"]["headline"]} for e in editions(store)[:7]], ensure_ascii=False))
        finally:
            store.close()
        return
    require(mode in ("research", "validate", "publish"), "Unknown mode")
    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "Edition too large")
    raw = json.loads(data)
    if mode == "research":
        print(json.dumps(prepare_research(raw), ensure_ascii=False))
        return
    payload = validate(raw)
    require(payload["date"] == sys.argv[2], "Edition date mismatch")
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
