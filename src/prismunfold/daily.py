"""Unified daily edition API (backend foundation for milestone 0.3).

One logical edition per publication date, composed from every public contribution
of that date (AI editorial workers, the prism-data bulletin, matched agent reports),
written to

    site/api/v1/daily/index.json          newest first: date, main headline, counts
    site/api/v1/daily/YYYY-MM-DD.json     the edition (contract: docs/API.md)

The existing endpoints (api/v1/editorial/morgenbriefing.json, editions.json, ...)
stay unchanged; the frontend can move to this contract in 0.3 without another
backend rewrite. Only published or approved items are included; withheld items and
internal validation detail never reach this file. Images without display rights keep
their metadata but lose the embeddable URL.
"""
from __future__ import annotations

from pathlib import Path

SCHEMA = "prismunfold.daily-edition/1"
ZONE = "Europe/Zurich"


def _source(s: dict) -> dict:
    return {k: v for k, v in dict(
        id=s.get("id"), url=s.get("url"), title=s.get("title"), publisher=s.get("publisher"),
        publishedAt=s.get("published_at") or None, sourceType=s.get("source_type") or None,
        access=s.get("access") or None, linkStatus=s.get("link_status") or None).items() if v is not None}


def _image(i: dict) -> dict:
    out = dict(alt=i.get("alt", ""), caption=i.get("caption", ""), credit=i.get("credit", ""),
               license=i.get("license", ""), licenseUrl=i.get("license_url", ""), rights=i.get("rights", ""),
               rightsNote=i.get("rights_note", ""), sourceUrl=i.get("source_url", ""),
               origin=i.get("origin", "unknown"), display=bool(i.get("display")))
    if out["display"]:
        out["url"] = i["url"]
    return out


def _provenance(a: dict) -> dict:
    p = a.get("provenance") or {}
    provider = p.get("provider") or a.get("provider") or ("prism-data" if a.get("origin") == "prism-data" else "prismunfold")
    return dict(provider=provider, originType=p.get("origin_type", "ai_secondary"),
                publicationBasis=p.get("publication_basis") or ("approved" if a.get("approval") else "validated"),
                citationLevel=p.get("citation_level") or a.get("citation_level") or "paragraph",
                generatedAt=p.get("generated_at"), upstreamStatus=p.get("upstream_status"))


def _article(a: dict, fallback_id: str) -> dict:
    ids = {s.get("id"): s for s in a.get("sources", [])}
    access = sorted({s.get("link_status") for s in ids.values() if s.get("link_status")})
    out = dict(
        articleId=a.get("article_id") or fallback_id, kind=a.get("kind", "news"), section=a.get("section", ""),
        headline=a["headline"], lead=a.get("lead", ""), topic=a.get("topic") or None,
        paragraphs=[dict(text=p["text"], heading=p.get("heading") or None, sourceIds=p.get("source_ids", []),
                         reviewRequired=bool(p.get("review_required"))) for p in a.get("paragraphs", [])],
        sources=[_source(s) for s in a.get("sources", [])],
        images=[_image(i) for i in a.get("images", [])],
        perspectives=[dict(text=x["text"], label=x.get("label") or None, attribution=x.get("attribution") or None,
                           sources=[_source(s) for s in x.get("sources", [])]) for x in a.get("perspectives", [])],
        uncertainties=list(a.get("uncertainties", [])),
        background=[dict(heading=b.get("heading"), text=b["text"], reviewRequired=bool(b.get("review_required")),
                         sources=[_source(s) for s in b.get("sources", [])])
                    for b in a.get("background", [])],
        reviewRequired=bool(a.get("review_required")),
        limitations=list(a.get("limitations", [])),
        verification=dict(sourceAccess=access or ["unknown"], factual="not_independently_verified"),
        provenance=_provenance(a),
        coverage=[_article(c, f"{fallback_id}-c{n}") for n, c in enumerate(a.get("coverage", []))],
    )
    if a.get("story_slug"):
        out["storySlug"] = a["story_slug"]
    return {k: v for k, v in out.items() if v is not None}


def _short(item: dict, label: str | None = None) -> dict:
    return dict(label=label or item.get("label") or item.get("category"), text=item["text"],
                attribution=item.get("attribution") or None, reviewRequired=bool(item.get("review_required")),
                sources=[_source(s) for s in item.get("sources", [])])


def compose(edition: dict) -> dict:
    """The daily-edition document for one merged editorial edition."""
    day = edition["date"]
    news = [_article(a, f"{day}-{n}") for n, a in enumerate(edition.get("articles", []))]
    news += [_article(a, f"{day}-x{n}") for n, a in enumerate(edition.get("additional_articles", []))]
    magazines = [m for m in [edition.get("magazine"), *edition.get("additional_magazines", [])] if m]
    features = [_article(m, f"{day}-m{n}") for n, m in enumerate(magazines)]
    good = [a for a in news if a["section"] == "Good News"]
    regular = [a for a in news if a["section"] != "Good News"]
    bulletin = edition.get("bulletin") or {}
    rubrics: dict[str, list[str]] = {}
    for a in regular:
        rubrics.setdefault(a["section"], []).append(a["articleId"])
    contributors = {}
    for a in news + features:
        for item in [a, *a["coverage"]]:
            p = item["provenance"]
            contributors[p["provider"]] = dict(provider=p["provider"], originType=p["originType"])
    random = []
    if edition.get("random"):
        random.append(_short(edition["random"], "Random des Tages"))
    if bulletin.get("random_article"):
        r = bulletin["random_article"]
        random.append(dict(label=r["headline"], text="\n\n".join(p["text"] for p in r["paragraphs"]),
                           attribution="prism-data", reviewRequired=False,
                           sources=[_source(s) for s in r.get("sources", [])]))
    lead = regular[0] if regular else (news[0] if news else None)
    return dict(
        schemaVersion=SCHEMA, date=day, timezone=ZONE, title="PrismUnfold · Tagesausgabe",
        mainHeadline=dict(articleId=lead["articleId"], headline=lead["headline"]) if lead else None,
        introduction=dict(text=bulletin["lead"], provider="prism-data", originType="ai_secondary")
        if bulletin.get("lead") else None,
        rubrics=[dict(name=name, articleIds=ids) for name, ids in rubrics.items()],
        articles=regular,
        briefs=[],  # short news briefs: contract slot for 0.3; no contributor provides them yet
        magazine=features,
        goodNews=good,
        randomFacts=random,
        assessments=[_short(x) for x in edition.get("lagebild", [])] +
                    [_short(x, x.get("label") or "Ausblick") for x in bulletin.get("outlook", [])],
        contributors=sorted(contributors.values(), key=lambda c: c["provider"]),
        transparency=dict(
            disclosures=[d for d in [edition.get("disclosure"), bulletin.get("disclosure")] if d],
            warnings=list(edition.get("warnings", [])),
            editorialNote=bulletin.get("note") or None,
            completeness=edition.get("completeness", "unknown"),
            independentVerification="AI contributions and source-access checks are not independent factual verification.",
        ),
        revision=dict(publishedAt=edition.get("published_at"), publicationMode=edition.get("publication_mode"),
                      bulletinGeneratedAt=bulletin.get("generated_at"), bulletinBasis=bulletin.get("publication_basis")),
    )


def export_daily(merged_editions: list[dict], site_dir) -> list[str]:
    from .export import _write

    base = Path(site_dir) / "api/v1/daily"
    written, index = [], []
    for edition in merged_editions:
        doc = compose(edition)
        written.append(_write(base / f"{doc['date']}.json", doc))
        index.append(dict(date=doc["date"], mainHeadline=doc["mainHeadline"], articleCount=len(doc["articles"]),
                          magazineCount=len(doc["magazine"]), completeness=doc["transparency"]["completeness"],
                          contributors=[c["provider"] for c in doc["contributors"]], href=f"/api/v1/daily/{doc['date']}.json"))
    written.append(_write(base / "index.json", sorted(index, key=lambda x: x["date"], reverse=True)))
    return written
