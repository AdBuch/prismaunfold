"""Editorial editions written by AI editorial workers (Codex today; Claude, Mistral, ...).

Validation is granular, never all-or-nothing:

* Every article, the magazine and every short item is judged on its own. A problem
  in one of them never rejects the whole edition; the original contribution is kept.
* Source accessibility (`linkcheck`) is recorded per source and paragraph. It is not
  factual verification: a reachable page does not prove a claim, and a refusal
  (HTTP 403, paywall) does not prove a source invented.
* Each article gets an editorial state: `validated` (every paragraph has an openly
  reachable source), `review_required` (some paragraph rests only on restricted,
  missing or temporarily unreachable sources), or `rejected` (some paragraph rests
  only on unsafe or catalogue-excluded sources). Malformed articles are listed as
  `invalid` with the reason.

Publication applies an explicit policy (docs/EDITORIAL_WORKFLOW.md):

* automatic: `validated` articles are published; `review_required` and `rejected`
  ones are withheld for review; the edition is published when at least
  `min_articles` articles in `min_sections` sections survive. A missing or failed
  magazine, Random or Lagebild makes the edition *partial*, not invalid.
* manual: the same, plus optional explicit approval of review-required articles
  (they stay labelled "prüfbedürftig") and of partial editions.
* `approve` / `reject` change one article later, without regenerating anything.

Raw editions are never modified; recovery re-validates saved JSON without an AI call.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import contributions as contrib
from .linkcheck import (DNS_FAILURE, LEGACY, MISSING, RATE_LIMITED, REACHABLE, RESTRICTED, TIMEOUT_STATUS,
                        UNAVAILABLE, UNKNOWN, UNSAFE, SourceCheckCache, http_status)
from .normalize import sha1_id
from .oplog import event
from .reports import public_url
from .storage import open_store

PUBLICATION = "morgenbriefing"
WORKERS = ("codex", "claude", "mistral", "goose", "chatgpt", "other")
ACCESS = ("open", "excerpt", "paywalled", "unknown")
SECTIONS = ("Schweiz Politik", "Schweiz Gesellschaft", "Schweiz Regional",
            "Peru Politik", "Peru Gesellschaft", "Krisen- und Konfliktgebiete", "Reisen",
            "International", "Wirtschaft, Technologie & Wissenschaft", "Good News")
ASSESSMENTS = ("Wichtig", "Überschätzt", "Unterberichtet", "Beobachten")
MAX_BYTES = 512 * 1024
EDITION_PREFIX = "editorial|morgenbriefing|"
COMPONENT = "editorial"
DEFAULT_POLICY = dict(min_articles=5, min_sections=3)
DISCLOSURE = ("KI-redaktionell erstellt. Quellenzugriff geprüft, nicht die Richtigkeit der Aussagen. "
              "Beiträge mit unzugänglichen Belegen werden zurückgehalten oder als prüfbedürftig markiert.")
# Paragraph evidence -> reason shown to editors.
REASONS = {
    RESTRICTED: "only_restricted_sources",      # 401/402/403/451 or declared paywall
    MISSING: "only_missing_sources",            # 404/410: possibly wrong or invented link
    "transient": "sources_temporarily_unreachable",
    UNSAFE: "only_unsafe_sources",
    "excluded": "only_excluded_sources",
    UNKNOWN: "sources_not_checked",
}
TRANSIENT_STATES = {RATE_LIMITED, UNAVAILABLE, TIMEOUT_STATUS, DNS_FAILURE}


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


def article_id(day: str, section: str, headline: str) -> str:
    return f"ed-{day}-{sha1_id(section, headline)[:10]}"


def _evidence(statuses: list[tuple[dict, str]]) -> tuple[str, list[str]]:
    """Paragraph evidence from (source, status) pairs -> (evidence, usable source ids)."""
    usable = [(s, st) for s, st in statuses if st != UNSAFE and s.get("policy") != "excluded"]
    if not usable:
        return ("excluded" if any(s.get("policy") == "excluded" for s, _ in statuses) else UNSAFE), []
    if any(st == REACHABLE and s["access"] != "paywalled" for s, st in usable):
        return REACHABLE, [s["id"] for s, _ in usable]
    states = {RESTRICTED if s["access"] == "paywalled" and st == REACHABLE else st for s, st in usable}
    if states & TRANSIENT_STATES:
        evidence = "transient"
    elif RESTRICTED in states:
        evidence = RESTRICTED
    elif UNKNOWN in states:
        evidence = UNKNOWN
    else:
        evidence = MISSING
    return evidence, [s["id"] for s, _ in usable]


def validate(raw, probe=http_status, excluded=None):
    """Normalise and judge an edition. Raises only for an unusable document as a whole."""
    excluded = excluded_domains() if excluded is None else excluded
    require(isinstance(raw, dict) and raw.get("publication") == PUBLICATION, "Wrong publication")
    provider = raw.get("provider")
    require(provider in WORKERS, "Unknown editorial provider")
    day = string(raw.get("date"), 10)
    require(date.fromisoformat(day).isoformat() == day, "Invalid edition date")
    sources = raw.get("sources")
    require(isinstance(sources, list) and 1 <= len(sources) <= 80, "Invalid sources")
    source_map, warnings, invalid = {}, [], []
    for index, item in enumerate(sources):
        try:
            require(isinstance(item, dict), "Invalid source")
            sid = string(item.get("id"), 60)
            url = public_url(item.get("url"))
            require(url is not None, "Invalid source URL")
            require(sid not in source_map, "Duplicate source id")
            host = urlsplit(url).hostname or ""
            access = item.get("access", "unknown")
            require(access in ACCESS, "Invalid access status")
            source = dict(id=sid, url=url, title=string(item.get("title"), 300),
                          publisher=string(item.get("publisher"), 120), access=access,
                          link_status=UNKNOWN)
            if any(host == d or host.endswith("." + d) for d in excluded):
                source["policy"] = "excluded"
            source_map[sid] = source
        except ValueError as exc:
            # A broken source entry only affects paragraphs citing it (as unknown id).
            invalid.append(dict(kind="source", index=index, reason=str(exc)))
    cache = {}

    def status(sid):
        source = source_map[sid]
        if source.get("policy") == "excluded":
            return source["link_status"]
        url = source["url"]
        if url not in cache:
            value = probe(url)
            if isinstance(value, bool):
                value = REACHABLE if value else MISSING
            cache[url] = LEGACY.get(value, value)
        source["link_status"] = cache[url]
        return cache[url]

    def refs(ids):
        require(isinstance(ids, list) and 1 <= len(ids) <= 10 and all(isinstance(s, str) for s in ids),
                "Invalid source list")
        unique = list(dict.fromkeys(ids))
        unknown = [s for s in unique if s not in source_map]
        require(len(unknown) < len(unique), "Unknown paragraph source")
        known = [s for s in unique if s in source_map]
        return _evidence([(source_map[s], status(s)) for s in known])

    def article(item, magazine=False):
        require(isinstance(item, dict), "Invalid article")
        section = "Magazin" if magazine else item.get("section")
        require(magazine or section in SECTIONS, "Unknown section")
        paragraphs = item.get("paragraphs")
        require(isinstance(paragraphs, list) and (4 if magazine else 2) <= len(paragraphs) <= 16,
                "Invalid paragraph count")
        headline = string(item.get("headline"), 200)
        result, used, reasons = [], set(), []
        state = "validated"
        for position, para in enumerate(paragraphs, start=1):
            require(isinstance(para, dict), "Invalid paragraph")
            body = string(para.get("text"), 4000)
            evidence, kept = refs(para.get("source_ids"))
            used.update(kept)
            p = dict(text=body, source_ids=kept, evidence=evidence, review_required=evidence != REACHABLE)
            if para.get("heading"):
                p["heading"] = string(para["heading"], 160)
            if evidence != REACHABLE:
                reasons.append(dict(paragraph=position, reason=REASONS[evidence],
                                    sources=[dict(id=s, url=source_map[s]["url"], status=source_map[s]["link_status"])
                                             for s in para.get("source_ids", []) if s in source_map]))
                if evidence in (UNSAFE, "excluded"):
                    state = "rejected"
                elif state == "validated":
                    state = "review_required"
            dropped = [s for s in para.get("source_ids", []) if s in source_map and s not in kept]
            if dropped and evidence == REACHABLE:
                reasons.append(dict(paragraph=position, reason="unsafe_or_excluded_source_removed",
                                    sources=[dict(id=s, url=source_map[s]["url"]) for s in dropped]))
                if state == "validated":
                    state = "review_required"
            result.append(p)
        words = sum(len(p["text"].split()) for p in result)
        require((350 if magazine else 65) <= words <= (1000 if magazine else 250), "Article length outside limits")
        out = dict(article_id=article_id(day, section, headline), section=section, headline=headline,
                   lead=string(item.get("lead"), 600), paragraphs=result,
                   sources=[source_map[s] for s in sorted(used)], state=state,
                   review_required=state != "validated", review_reasons=reasons,
                   kind="magazine" if magazine else "news", origin="prismunfold", provider=provider)
        topic = item.get('topic', '')
        if isinstance(topic, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', topic):
            out['topic'] = topic
        background = item.get("background", [])
        out["background"] = []
        if isinstance(background, list):
            for entry in background[:5]:
                try:
                    extra = short_item(entry)
                    if extra["state"] == "rejected":
                        continue
                    extra["heading"] = string(entry.get("heading"), 120)
                    out["background"].append(extra)
                except ValueError:
                    continue
        return out

    def short_item(item):
        require(isinstance(item, dict), "Invalid short item")
        evidence, kept = refs(item.get("source_ids"))
        state = "validated" if evidence == REACHABLE else "rejected" if evidence in (UNSAFE, "excluded") else "review_required"
        return dict(text=string(item.get("text"), 900), sources=[source_map[s] for s in kept],
                    review_required=state != "validated", state=state, evidence=evidence)

    articles = raw.get("articles")
    require(isinstance(articles, list) and 1 <= len(articles) <= 16, "Need 1–16 news articles")
    judged = []
    for idx, item in enumerate(articles):
        try:
            judged.append(article(item))
        except ValueError as exc:
            invalid.append(dict(kind="article", index=idx + 1,
                                headline=item.get("headline", "") if isinstance(item, dict) else "", reason=str(exc)))
    ids = [a["article_id"] for a in judged]
    require(len(ids) == len(set(ids)), "Duplicate article headline in one section")
    magazine = None
    if raw.get("magazine") is not None:
        try:
            magazine = article(raw.get("magazine"), True)
        except ValueError as exc:
            invalid.append(dict(kind="magazine", index=0, reason=str(exc)))
    extras = {}
    if raw.get("random") is not None:
        try:
            extras["random"] = short_item(raw["random"])
        except ValueError as exc:
            invalid.append(dict(kind="random", index=0, reason=str(exc)))
    assessments = raw.get("lagebild") or {}
    extras["lagebild"] = []
    if isinstance(assessments, dict):
        for category in ASSESSMENTS:
            if assessments.get(category) is not None:
                try:
                    extras["lagebild"].append(dict(category=category, **short_item(assessments[category])))
                except ValueError as exc:
                    invalid.append(dict(kind="lagebild", index=category, reason=str(exc)))
    judged.sort(key=lambda a: SECTIONS.index(a["section"]))
    payload = dict(publication=PUBLICATION, provider=provider, date=day, **extras, title="Morgenbriefing",
                   articles=judged, magazine=magazine, invalid=invalid, disclosure=DISCLOSURE)
    payload["warnings"] = warnings + _warnings(payload)
    return payload


def _warnings(payload) -> list[str]:
    out = []
    for item in payload.get("invalid", []):
        label = item.get("headline") or f"{item['kind']} {item['index']}"
        out.append(f"Nicht verwendbar ({item['kind']}): {label}: {item['reason']}")
    for a in payload["articles"] + ([payload["magazine"]] if payload.get("magazine") else []):
        if a["state"] == "review_required":
            out.append("Prüfbedürftig: " + a["headline"])
        elif a["state"] == "rejected":
            out.append("Zurückgewiesen (unsichere oder ausgeschlossene Quelle): " + a["headline"])
    covered = {a["section"] for a in payload["articles"] if a["state"] in ("validated", "approved", "published")}
    missing = [section for section in SECTIONS if section not in covered]
    if missing:
        out.append("Keine veröffentlichte Meldung: " + ", ".join(missing))
    if not payload.get("magazine") or payload["magazine"]["state"] not in ("validated", "approved", "published"):
        out.append("Magazin zurückgestellt oder nicht vorhanden")
    if not payload.get("random") or payload["random"]["state"] != "validated":
        out.append("Random des Tages fehlt oder ist prüfbedürftig")
    if len([x for x in payload.get("lagebild", []) if x["state"] == "validated"]) != len(ASSESSMENTS):
        out.append("Lagebild ist unvollständig")
    return out


def load_policy(config_path: str | None = None) -> dict:
    policy = dict(DEFAULT_POLICY)
    path = Path(config_path or os.environ.get("PRISMUNFOLD_CONFIG", "config/config.json"))
    try:
        policy.update(json.loads(path.read_text(encoding="utf-8")).get("editorial", {}).get("auto_publish", {}))
    except (OSError, ValueError):
        pass
    return policy


def apply_policy(payload: dict, *, auto: bool, approve_review_required: bool = False,
                 allow_partial: bool = False, policy: dict | None = None, reviewer: str = "") -> dict:
    """Split a validated edition into what is published now and what is withheld."""
    policy = policy or DEFAULT_POLICY
    stamp = contrib.now_iso()
    publish, withheld = [], []
    for a in payload["articles"]:
        a = dict(a)
        if a["state"] == "validated" or (a["state"] == "review_required" and approve_review_required and not auto):
            if a["state"] == "review_required":
                a["approval"] = dict(by=reviewer or "operator", at=stamp, note="published with review label")
            a["state"] = "published"
            publish.append(a)
        else:
            withheld.append(a)
    sections = {a["section"] for a in publish}
    complete = len(publish) >= policy["min_articles"] and len(sections) >= policy["min_sections"]
    if not complete and (auto or not allow_partial):
        raise ValueError(f"Publication refused: {len(publish)} publishable articles in {len(sections)} sections; "
                         f"policy needs {policy['min_articles']} in {policy['min_sections']}")
    out = dict(payload, articles=publish, withheld=withheld)
    magazine = payload.get("magazine")
    if magazine and (magazine["state"] == "validated" or
                     (magazine["state"] == "review_required" and approve_review_required and not auto)):
        out["magazine"] = dict(magazine, state="published")
    else:
        out["magazine"] = None
        if magazine:
            withheld.append(magazine)
    for key in ("random",):
        if out.get(key) and out[key]["state"] != "validated" and (auto or not approve_review_required):
            out.pop(key)
    out["lagebild"] = [x for x in payload.get("lagebild", [])
                       if x["state"] == "validated" or (x["state"] == "review_required" and approve_review_required and not auto)]
    out["completeness"] = "complete" if out["magazine"] and out.get("random") and len(out["lagebild"]) == len(ASSESSMENTS) else "partial"
    out["publication"] = PUBLICATION
    out["published_at"] = stamp
    out["publication_mode"] = "automatic" if auto else "manual"
    out["warnings"] = _warnings(dict(payload, articles=payload["articles"]))
    return out


def public_view(edition: dict) -> dict:
    """What readers and the API see: no withheld items, no internal validation detail."""
    out = {k: v for k, v in edition.items() if k not in ("withheld", "invalid", "raw_hash", "contribution_id")}
    return out


def editions(store):
    rows = store.db.execute("SELECT data FROM editions WHERE id LIKE 'editorial|morgenbriefing|%' ORDER BY id DESC").fetchall()
    return [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in rows]


def export_editorial(store, site_dir, stories=None):
    from .bulletin import imports, merge_editions
    from .daily import export_daily
    from .export import _write

    authored = [public_view(e) for e in editions(store)]
    bulletins = imports(store)
    if bulletins:
        authored = merge_editions(authored, bulletins, store.all_stories() if stories is None else stories)
    path = _write(Path(site_dir) / "api/v1/editorial/morgenbriefing.json", authored)
    export_daily(authored, site_dir)
    event(COMPONENT, "export_completed", editions=len(authored))
    return path


def _store():
    return open_store(os.environ.get("DATABASE_URL") or os.environ.get("DB_PATH") or "data/prismunfold.sqlite3")


def _site():
    return os.environ.get("SITE_DIR", "/site")


def publish(store, raw: dict, payload: dict, *, auto: bool, approve_review_required=False, allow_partial=False,
            replace=False, policy=None, reviewer="", site_dir=None) -> tuple[str, dict]:
    """Store and export an edition. Safe to retry: identical content only re-exports."""
    day = payload["date"]
    digest = contrib.content_hash(raw)
    source_key = f"{payload['provider']}/{PUBLICATION}/{day}"
    with store.lock("edition-publication"):
        current = store.get_edition(EDITION_PREFIX + day)
        if current and current.get("raw_hash") == digest:
            outcome = "already_published"
            result = current
        else:
            if current and not replace:
                raise ValueError("Edition already published with different content; use --replace to supersede it")
            result = apply_policy(payload, auto=auto, approve_review_required=approve_review_required,
                                  allow_partial=allow_partial, policy=policy, reviewer=reviewer)
            record = contrib.new(payload["provider"], source_key, day, digest,
                                 generated_at=raw.get("generated_at"), kind="edition", raw=raw,
                                 normalised=None, state="validated")
            if not store.save_contribution(record):
                record = next(c for c in store.list_contributions(source_key=source_key) if c["content_hash"] == digest)
            contrib.transition(record, "published", by=reviewer or ("scheduler" if auto else "operator"))
            store.update_contribution(record)
            for previous in store.list_contributions(source_key=source_key):
                if previous["id"] != record["id"] and previous["state"] == "published":
                    store.update_contribution(contrib.transition(previous, "superseded", note=f"replaced by {record['id']}"))
            result = dict(result, raw_hash=digest, contribution_id=record["id"])
            store.save_edition(EDITION_PREFIX + day, "de", datetime.now(timezone.utc), result)
            store.commit()
            outcome = "published"
        export_editorial(store, site_dir or _site())
    event(COMPONENT, "edition_published" if outcome == "published" else "edition_recovered",
          provider=payload["provider"], edition_date=day, status=outcome,
          articles=len(result["articles"]), withheld=len(result.get("withheld", [])),
          completeness=result.get("completeness"))
    return outcome, result


def review_article(store, day: str, article_ref: str, decision: str, reviewer: str, note: str = "",
                   site_dir=None) -> dict:
    """Approve a withheld article (or magazine) or reject a published one; no regeneration."""
    require(decision in ("approve", "reject"), "decision must be approve or reject")
    require(bool(reviewer.strip()), "reviewer is required")
    with store.lock("edition-publication"):
        edition = store.get_edition(EDITION_PREFIX + day)
        require(edition is not None, f"No published edition for {day}")
        stamp = contrib.now_iso()
        withheld = edition.setdefault("withheld", [])
        if decision == "approve":
            match = next((a for a in withheld if a["article_id"] == article_ref), None)
            require(match is not None, "Article is not withheld")
            require(match["state"] != "rejected", "Rejected articles (unsafe or excluded sources) cannot be approved")
            withheld.remove(match)
            match = dict(match, state="published", review_required=match["state"] == "review_required",
                         approval=dict(by=reviewer, at=stamp, note=note))
            if match["kind"] == "magazine":
                require(not edition.get("magazine"), "Edition already has a magazine")
                edition["magazine"] = match
            else:
                edition["articles"].append(match)
                edition["articles"].sort(key=lambda a: SECTIONS.index(a["section"]))
        else:
            pool = edition["articles"] + ([edition["magazine"]] if edition.get("magazine") else [])
            match = next((a for a in pool if a["article_id"] == article_ref), None)
            require(match is not None, "Article is not published")
            if match is edition.get("magazine"):
                edition["magazine"] = None
            else:
                edition["articles"].remove(match)
            withheld.append(dict(match, state="rejected", rejection=dict(by=reviewer, at=stamp, note=note)))
        store.save_edition(EDITION_PREFIX + day, "de", datetime.now(timezone.utc), edition)
        store.commit()
        export_editorial(store, site_dir or _site())
    event(COMPONENT, "article_approved" if decision == "approve" else "article_rejected",
          edition_date=day, article_id=article_ref, status=decision)
    return edition


def problems(payload: dict) -> list[dict]:
    """Flat list of validation findings for operators (inspect, logs)."""
    out = [dict(edition_date=payload["date"], kind=i["kind"], article_id="", paragraph=None,
                reason=i["reason"], sources=[], headline=i.get("headline", "")) for i in payload.get("invalid", [])]
    for a in payload["articles"] + ([payload["magazine"]] if payload.get("magazine") else []):
        for r in a.get("review_reasons", []):
            out.append(dict(edition_date=payload["date"], kind=a["kind"], article_id=a["article_id"],
                            headline=a["headline"], state=a["state"], paragraph=r["paragraph"],
                            reason=r["reason"], sources=r["sources"]))
    return out


def _log_problems(payload):
    for p in problems(payload):
        event(COMPONENT, "validation_failed" if p.get("state") != "review_required" else "article_review_required",
              level=30, edition_date=p["edition_date"], article_id=p["article_id"], paragraph=p["paragraph"],
              error_code=p["reason"], sources=[f"{s['id']} {s.get('status', '')} {s['url']}" for s in p["sources"]])


def _read_stdin():
    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "Edition too large")
    return json.loads(data)


def _probe():
    cache = SourceCheckCache(os.environ.get("SOURCE_CHECK_CACHE") or None)
    return cache, cache.probe()


def candidates(base: Path, day: str) -> list[Path]:
    return sorted(p for p in base.glob(f"{day}.*/edition*.json")
                  if p.is_file() and re.fullmatch(r"edition(\.repaired)?\.json", p.name))


def select_candidate(base: Path, day: str) -> Path | None:
    """Deterministic choice among saved raw editions for `day`, without network access.

    Rank: structurally valid > more usable articles > has magazine > newer mtime > path.
    """
    ranked = []
    for path in candidates(base, day):
        try:
            raw = json.loads(path.read_bytes()[:MAX_BYTES + 1])
            payload = validate(raw, probe=lambda url: UNKNOWN, excluded=set())
            if payload["date"] != day:
                continue
        except (OSError, ValueError):
            continue
        ranked.append(((len(payload["articles"]), payload["magazine"] is not None, path.stat().st_mtime, str(path)), path))
    return max(ranked)[1] if ranked else None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m prismunfold.editorial")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("history")
    p = sub.add_parser("bulletin-context"); p.add_argument("date")
    for name in ("validate", "inspect"):
        p = sub.add_parser(name, help="read a raw edition on stdin; no AI call"); p.add_argument("date")
    sub.choices["validate"].add_argument("--check-policy", action="store_true",
                                         help="add auto_publishable/policy_reason to the preview")
    p = sub.add_parser("publish", help="publish a raw edition from stdin; idempotent")
    p.add_argument("date")
    p.add_argument("--auto", action="store_true", help="scheduler policy (also EDITORIAL_AUTO=1)")
    p.add_argument("--approve-review-required", action="store_true")
    p.add_argument("--allow-partial", action="store_true")
    p.add_argument("--replace", action="store_true")
    p.add_argument("--reviewer", default="")
    for name in ("approve", "reject"):
        p = sub.add_parser(name); p.add_argument("date"); p.add_argument("article_id")
        p.add_argument("--reviewer", required=True); p.add_argument("--note", default="")
    p = sub.add_parser("revalidate", help="re-check the stored raw edition's sources; no AI call")
    p.add_argument("date")
    p = sub.add_parser("select-candidate"); p.add_argument("date"); p.add_argument("base")
    sub.add_parser("export")
    p = sub.add_parser("status"); p.add_argument("date")
    args = parser.parse_args(argv)

    if args.mode == "select-candidate":
        chosen = select_candidate(Path(args.base), args.date)
        if not chosen:
            return 1
        print(chosen)
        return 0
    if args.mode in ("validate", "inspect"):
        raw = _read_stdin()
        cache, probe = _probe()
        payload = validate(raw, probe)
        cache.save()
        require(payload["date"] == args.date, "Edition date mismatch")
        _log_problems(payload)
        if args.mode == "inspect":
            print(json.dumps(problems(payload), ensure_ascii=False, indent=2))
        else:
            if args.check_policy:
                try:
                    apply_policy(payload, auto=True, policy=load_policy())
                    payload.update(auto_publishable=True, policy_reason="")
                except ValueError as exc:
                    payload.update(auto_publishable=False, policy_reason=str(exc))
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    store = _store()
    try:
        if args.mode == "history":
            print(json.dumps([{"date": e["date"], "headlines": [{"section": a["section"], "headline": a["headline"], "topic": a.get("topic", "")} for a in e["articles"]],
                               "magazine": (e.get("magazine") or {}).get("headline", "")} for e in editions(store)[:7]], ensure_ascii=False))
        elif args.mode == "bulletin-context":
            from .bulletin import editorial_context
            print(json.dumps(editorial_context(store, args.date), ensure_ascii=False))
        elif args.mode == "publish":
            raw = _read_stdin()
            cache, probe = _probe()
            payload = validate(raw, probe)
            cache.save()
            require(payload["date"] == args.date, "Edition date mismatch")
            _log_problems(payload)
            auto = args.auto or os.environ.get("EDITORIAL_AUTO") == "1"
            outcome, result = publish(store, raw, payload, auto=auto, approve_review_required=args.approve_review_required,
                                      allow_partial=args.allow_partial, replace=args.replace,
                                      policy=load_policy(), reviewer=args.reviewer)
            print(json.dumps(dict(outcome=outcome, date=args.date, articles=len(result["articles"]),
                                  withheld=[dict(article_id=a["article_id"], state=a["state"], headline=a["headline"])
                                            for a in result.get("withheld", [])],
                                  completeness=result.get("completeness")), ensure_ascii=False, indent=2))
        elif args.mode in ("approve", "reject"):
            review_article(store, args.date, args.article_id, args.mode, args.reviewer, args.note)
            print(f"{args.mode}d {args.article_id}")
        elif args.mode == "revalidate":
            edition = store.get_edition(EDITION_PREFIX + args.date)
            require(edition is not None, "No published edition for this date")
            record = store.get_contribution(edition.get("contribution_id", ""))
            require(record is not None and record.get("raw"), "Stored raw edition not found")
            cache, probe = _probe()
            payload = validate(record["raw"], probe)
            cache.save()
            _log_problems(payload)
            now_ok = {a["article_id"] for a in payload["articles"] if a["state"] == "validated"}
            promotable = [a["article_id"] for a in edition.get("withheld", [])
                          if a["article_id"] in now_ok and a["state"] == "review_required"]
            for ref in promotable:
                review_article(store, args.date, ref, "approve", "revalidation", "sources reachable on re-check")
            print(json.dumps(dict(date=args.date, promoted=promotable), ensure_ascii=False))
        elif args.mode == "export":
            print(export_editorial(store, _site()))
        elif args.mode == "status":
            edition = store.get_edition(EDITION_PREFIX + args.date)
            if not edition:
                print(json.dumps(dict(date=args.date, published=False)))
                return 1
            print(json.dumps(dict(date=args.date, published=True, completeness=edition.get("completeness"),
                                  articles=[dict(article_id=a.get("article_id"), state=a.get("state"), headline=a["headline"])
                                            for a in edition["articles"]],
                                  magazine=(edition.get("magazine") or {}).get("headline"),
                                  withheld=[dict(article_id=a["article_id"], state=a["state"], headline=a["headline"],
                                                 reasons=[r["reason"] for r in a.get("review_reasons", [])])
                                            for a in edition.get("withheld", [])]), ensure_ascii=False, indent=2))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as exc:
        print(f"editorial: {exc}", file=sys.stderr)
        sys.exit(1)
