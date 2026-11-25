"""Evidence-first, opt-in Editorial Intelligence vertical slice (EI-01).

No scraping, model access, automatic approvals or changes to the daily publisher.
The input contract accepts permission-reviewed, structured source documents; an
agent's proposed evidence is never self-verifying. A human review is required
before a drafted article can enter the shared content pool.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from .ei_store import IntelligenceStore, timestamp, utcnow
from .normalize import canonical_url, sha1_id

CLAIM_KINDS = frozenset(("fact", "attributed", "analysis", "forecast", "opinion"))
RELATIONS = frozenset(("supports", "contradicts"))
PUBLIC_SCHEMA = "prismunfold.content-pool/1"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _require(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value.strip()


def _date(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("published_at must be timezone-aware ISO 8601") from exc


def validate_document(doc: dict) -> dict:
    """Reject unknown processing rights and ambiguous event identity."""
    if not isinstance(doc, dict):
        raise ValueError("document must be an object")
    rights = doc.get("rights") or {}
    if rights.get("ai_processing") is not True:
        raise ValueError("source has no explicit AI-processing permission")
    url = _require(doc.get("url"), "url")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("invalid source URL")
    event_key = _require(doc.get("event_key"), "event_key")
    language = _require(doc.get("language"), "language").lower()
    if len(language) not in (2, 3) or not language.isalpha():
        raise ValueError("language must be ISO 639 code")
    source_type = _require(doc.get("source_type"), "source_type")
    origin_type = doc.get("origin_type", "original_publisher")
    if origin_type not in ("original_publisher", "ai_secondary"):
        raise ValueError("unsupported origin_type")
    claims = []
    if not isinstance(doc.get("claims"), list):
        raise ValueError("claims must be a list")
    for claim in doc["claims"]:
        if not isinstance(claim, dict):
            raise ValueError("claim must be an object")
        kind = claim.get("kind")
        relation = claim.get("relation", "supports")
        if kind not in CLAIM_KINDS or relation not in RELATIONS:
            raise ValueError("invalid claim kind or relation")
        claims.append({
            "key": _require(claim.get("key"), "claim key"),
            "statement": _require(claim.get("statement"), "claim statement"),
            "kind": kind,
            "relation": relation,
            "locator": _require(claim.get("locator"), "evidence locator"),
        })
    clean = {
        "event_key": event_key,
        "headline": _require(doc.get("headline"), "headline"),
        "language": language, "source_id": _require(doc.get("source_id"), "source_id"),
        "url": canonical_url(url),
        "source_type": source_type,
        "origin_type": origin_type,
        "published_at": _date(doc.get("published_at")),
        "original_work_id": doc.get("original_work_id") or canonical_url(url),
        "claims": claims,
        "rights": {"ai_processing": True,
                   "store_excerpt": rights.get("store_excerpt") is True,
                   "display_excerpt": rights.get("display_excerpt") is True},
        "excerpt": doc.get("excerpt", "") if rights.get("store_excerpt") is True else "",
        "topics": sorted(set(doc.get("topics") or [])),
        "regions": sorted(set(doc.get("regions") or [])),
    }
    if not isinstance(clean["excerpt"], str):
        raise ValueError("excerpt must be text")
    if not all(isinstance(x, str) for x in clean["topics"] + clean["regions"]):
        raise ValueError("topics and regions must be text")
    clean["document_id"] = "doc-" + digest(clean)[:20]
    clean["event_id"] = "evt-" + sha1_id("editorial-intelligence", event_key)
    return clean


class EditorialIntelligence:
    def __init__(self, store):
        self.repo = IntelligenceStore(store)

    def ingest(self, documents: list[dict]) -> list[str]:
        """Persist structured evidence without publishing anything."""
        events = set()
        for raw in documents:
            doc = validate_document(raw)
            self.repo.put(f"document|{doc['document_id']}", "document", doc["event_id"], doc)
            events.add(doc["event_id"])
        for event_id in events:
            self.dossier(event_id)
        return sorted(events)

    def dossier(self, event_id: str) -> dict:
        docs = self.repo.list("document", event_id)
        if not docs:
            raise ValueError("event has no permitted source documents")
        if len({doc["event_key"] for doc in docs}) != 1:
            raise ValueError("event key collision")
        docs.sort(key=lambda d: (d["published_at"], d["document_id"]))
        claims: dict[str, dict] = {}
        for doc in docs:
            for row in doc["claims"]:
                claim = claims.setdefault(row["key"], {
                    "id": "claim-" + sha1_id(event_id, row["key"]),
                    "key": row["key"], "evidence": [],
                    "verification": "requires_independent_review",
                })
                claim["evidence"].append({
                    "document_id": doc["document_id"], "statement": row["statement"],
                    "kind": row["kind"], "relation": row["relation"],
                    "locator": row["locator"], "original_work_id": doc["original_work_id"],
                    "origin_type": doc["origin_type"],
                })
        # Same wire copy, repeated press release or AI citation is not confirmation.
        independent = {d["original_work_id"] for d in docs if
                       d["origin_type"] == "original_publisher"}
        gaps = []
        if not any(d["source_type"] == "official_document" for d in docs):
            gaps.append("original_primary_document")
        if len(independent) < 2:
            gaps.append("independent_reporting")
        if not claims:
            gaps.append("claim_evidence")
        dossier = {
            "schema_version": "prismunfold.event-dossier/1",
            "event_id": event_id, "event_key": docs[0]["event_key"],
            "headline": docs[0]["headline"], "documents": docs,
            "claims": [claims[key] for key in sorted(claims)],
            "gaps": gaps, "independent_original_works": len(independent),
            "lineage_limitation": "Distinct original_work_id values are only potential independence; "
                                  "ownership and undisclosed syndication require review.",
            "topics": sorted({t for d in docs for t in d["topics"]}),
            "regions": sorted({r for d in docs for r in d["regions"]}),
            "languages": sorted({d["language"] for d in docs}),
            "publication_status": "internal_dossier",
        }
        self.repo.put(f"dossier|{event_id}", "dossier", event_id, dossier)
        return dossier

    def plan_research(self, event_id: str, *, max_documents: int = 5) -> dict | None:
        dossier = self.dossier(event_id)
        if not dossier["gaps"]:
            return None
        if not 1 <= max_documents <= 20:
            raise ValueError("max_documents must be between 1 and 20")
        job = {
            "id": "research-" + sha1_id(event_id, ",".join(dossier["gaps"])),
            "event_id": event_id,
            "objective": "Find permitted original evidence for: " + ", ".join(dossier["gaps"]),
            "missing_evidence": dossier["gaps"],
            "budget": {"max_documents": max_documents, "max_attempts": 3,
                       "lease_seconds": 300},
            "provider": "configurable",
        }
        self.repo.enqueue(job)
        return self.repo.get(f"job|{job['id']}")

    def run_research(self, job_id: str, researcher: Callable[[dict, dict], list[dict]],
                     worker: str = "configured-researcher") -> dict | None:
        """Explicit provider call; network/model use is entirely the caller's choice."""
        job = self.repo.lease(job_id, worker=worker)
        if job is None:
            return None
        try:
            docs = researcher(job, self.dossier(job["event_id"]))
            if not isinstance(docs, list) or len(docs) > job["budget"]["max_documents"]:
                raise ValueError("research exceeded allowed document count")
            validated = [validate_document(d) for d in docs]
            if any(d["event_id"] != job["event_id"] for d in validated):
                raise ValueError("research changed event identity")
            # Only validated data enters persistence. A research provider cannot approve it.
            self.ingest(docs)
        except Exception as exc:
            self.repo.finish(job_id, job["lease_id"], success=False,
                             error_type=type(exc).__name__)
            raise
        self.repo.finish(job_id, job["lease_id"], success=True)
        return self.dossier(job["event_id"])

    def draft(self, event_id: str, language: str, writer: Callable[[dict, str], dict]) -> dict:
        """A replaceable writer returns typed prose with explicit claim keys."""
        dossier = self.dossier(event_id)
        raw = writer(dossier, language)
        if not isinstance(raw, dict) or not isinstance(raw.get("paragraphs"), list):
            raise ValueError("writer must return structured paragraphs")
        keys = {c["key"] for c in dossier["claims"]}
        if not raw["paragraphs"]:
            raise ValueError("empty draft")
        paragraphs = []
        for paragraph in raw["paragraphs"]:
            if not isinstance(paragraph, dict):
                raise ValueError("paragraph must be structured")
            used = paragraph.get("claim_keys", [])
            if not isinstance(used, list) or not used or any(k not in keys for k in used):
                raise ValueError("paragraph has missing or unrecognised claim references")
            paragraphs.append({"text": _require(paragraph.get("text"), "paragraph text"),
                               "claim_keys": sorted(set(used))})
        draft = {
            "event_id": event_id, "language": _require(language, "language"),
            "headline": _require(raw.get("headline"), "headline"),
            "lead": _require(raw.get("lead"), "lead"),
            "paragraphs": paragraphs, "topics": dossier["topics"],
            "regions": dossier["regions"], "article_variant": raw.get("article_variant", "standard_article"),
            "editorial_importance": raw.get("editorial_importance", "normal"),
            "source_document_ids": sorted({e["document_id"] for c in dossier["claims"]
                                          for e in c["evidence"]}),
            "publication_status": "draft_needs_review",
        }
        self.repo.put(f"draft|{event_id}|{language}", "draft", event_id, draft)
        return draft

    def approve(self, event_id: str, language: str, *, reviewer: str,
                checked_claim_sources: dict[str, list[str]]) -> dict:
        """Human approval of claim-to-source links and the exact language variant.

        The reviewer is responsible for checking that the referenced original passage
        supports the drafted sentence. This function cannot itself read or verify it.
        """
        reviewer = _require(reviewer, "reviewer")
        if reviewer.lower() in ("ai", "system", "bot", "anonymous"):
            raise ValueError("named human reviewer required")
        draft = self.repo.get(f"draft|{event_id}|{language}")
        if not draft:
            raise ValueError("no draft to review")
        dossier = self.dossier(event_id)
        claims = {c["key"]: c for c in dossier["claims"]}
        used = {k for p in draft["paragraphs"] for k in p["claim_keys"]}
        if set(checked_claim_sources) != used:
            raise ValueError("every published claim requires explicit review")
        for key, source_ids in checked_claim_sources.items():
            supporting = {e["document_id"] for e in claims[key]["evidence"]
                          if e["relation"] == "supports" and e["origin_type"] == "original_publisher"}
            if not source_ids or not set(source_ids) <= supporting:
                raise ValueError(f"{key}: checked sources must have original supporting locators")
        content = {**draft, "publication_status": "approved",
                   "approval": {"basis": "named_human_review", "reviewer": reviewer,
                                "checked_claim_sources": checked_claim_sources,
                                "approved_at": timestamp(utcnow())}}
        article_id = "ei-" + sha1_id(event_id, language)
        current = self.repo.get(f"published|{article_id}")
        comparable = {k: v for k, v in content.items() if k != "approval"}
        content_digest = digest(comparable)
        if current and current["content_digest"] == content_digest:
            return current   # idempotent; keep original sign-off and revision
        revision = 1 if current is None else current["revision"] + 1
        article = {**content, "article_id": article_id, "revision": revision,
                   "content_digest": content_digest, "claim_references":
                       [claims[k]["id"] for k in sorted(used)]}
        # Keep immutable revision snapshots for corrections and future audit.
        self.repo.put(f"revision|{article_id}|{revision}", "revision", event_id, article)
        self.repo.put(f"published|{article_id}", "published", event_id, article)
        return article

    def content_pool(self) -> dict:
        articles = self.repo.list("published")
        # Do not expose internal dossier text or reviewer identifiers to the reader.
        public = []
        for article in articles:
            filtered = {k: v for k, v in article.items()
                        if k not in ("approval", "content_digest", "source_document_ids")}
            filtered["review"] = {"status": "human_approved", "basis": "claim_evidence_review"}
            filtered["source_references"] = [
                {"document_id": doc["document_id"], "url": doc["url"],
                 "source_id": doc["source_id"], "language": doc["language"],
                 "source_type": doc["source_type"], "original_work_id": doc["original_work_id"]}
                for doc in self.dossier(article["event_id"])["documents"]
            ]
            public.append(filtered)
        return {"schema_version": PUBLIC_SCHEMA, "articles": public,
                "editorial_notice": "Human-approved synthesis; citations remain claim-linked. "
                                    "No automatic truth score or publisher independence guarantee."}

    def reader_edition(self, profile: dict) -> list[dict]:
        """Pure selection of cached articles. Never calls a writer per reader."""
        languages = profile.get("languages") or ["de", "en", "es"]
        interests = set(profile.get("topics") or [])
        by_event: dict[str, list[dict]] = {}
        for article in self.content_pool()["articles"]:
            if interests and not (set(article["topics"]) & interests):
                continue
            by_event.setdefault(article["event_id"], []).append(article)
        selected = []
        for candidates in by_event.values():
            chosen = min(candidates, key=lambda a: (
                languages.index(a["language"]) if a["language"] in languages else len(languages),
                a["article_id"]))
            if profile.get("reading_depth") == "brief":
                chosen = {**chosen, "paragraphs": [],
                          "display_variant": "brief", "claim_references": chosen["claim_references"]}
            selected.append(chosen)
        return sorted(selected, key=lambda a: a["article_id"])

    def export_pool(self, site_dir: str | Path) -> str:
        from .export import _write
        return _write(Path(site_dir) / "api/v1/editorial-intelligence/content-pool.json",
                      self.content_pool())
