"""Opt-in, additive persistence for the Editorial Intelligence vertical slice.

This is deliberately separate from the live newspaper tables. It reuses the
existing Store/PostgresStore connections and their cross-process advisory locks.
No existing edition or publication is changed by enabling this module.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


class IntelligenceStore:
    """Versioned JSON artifacts and recoverable research jobs, SQLite/Postgres."""

    def __init__(self, store):
        self.store = store
        self.pg = not hasattr(store, "path")
        self.param = "%s" if self.pg else "?"
        self.store.db.execute(
            """CREATE TABLE IF NOT EXISTS ei_records (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                event_id TEXT,
                updated_at TEXT NOT NULL,
                data TEXT NOT NULL
            )"""
        )
        self.store.db.execute(
            "CREATE INDEX IF NOT EXISTS ei_records_kind_event ON ei_records (kind, event_id)"
        )
        if self.pg:
            self.store.db.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (3, now()) "
                "ON CONFLICT DO NOTHING"
            )
        else:
            self.store.db.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) "
                "VALUES (3, datetime('now'))"
            )
        self.store.commit()

    def get(self, key: str) -> dict | None:
        row = self.store.db.execute(
            f"SELECT data FROM ei_records WHERE id = {self.param}", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind: str, event_id: str | None = None) -> list[dict]:
        p = self.param
        if event_id is None:
            query = f"SELECT data FROM ei_records WHERE kind = {p} ORDER BY id"
            args = (kind,)
        else:
            query = f"SELECT data FROM ei_records WHERE kind = {p} AND event_id = {p} ORDER BY id"
            args = (kind, event_id)
        rows = self.store.db.execute(query, args).fetchall()
        return [json.loads(row[0]) for row in rows]

    def put(self, key: str, kind: str, event_id: str | None, payload: dict) -> bool:
        """Idempotent atomic replacement. Returns False for unchanged content."""
        p = self.param
        with self.store.lock("editorial-intelligence"):
            if self.get(key) == payload:
                return False
            self.store.db.execute(
                f"INSERT INTO ei_records (id, kind, event_id, updated_at, data) "
                f"VALUES ({p}, {p}, {p}, {p}, {p}) "
                "ON CONFLICT(id) DO UPDATE SET "
                "kind = excluded.kind, event_id = excluded.event_id, "
                "updated_at = excluded.updated_at, data = excluded.data",
                (key, kind, event_id, timestamp(utcnow()),
                 json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            )
            self.store.commit()
            return True

    def enqueue(self, job: dict) -> bool:
        """Enqueue once, never reset a completed job on repeated demand analysis."""
        key = f"job|{job['id']}"
        with self.store.lock("editorial-intelligence"):
            if self.get(key) is not None:
                return False
            return self.put(key, "job", job["event_id"], {
                **job, "state": "pending", "attempts": 0, "lease_id": None,
                "leased_until": None, "last_error_type": None,
            })

    def lease(self, job_id: str, *, worker: str, seconds: int = 300,
              max_attempts: int = 3, now: datetime | None = None) -> dict | None:
        """At most one live lease; expired work may be claimed again."""
        if not 1 <= seconds <= 3600:
            raise ValueError("lease duration out of bounds")
        now = now or utcnow()
        key = f"job|{job_id}"
        with self.store.lock("editorial-intelligence"):
            job = self.get(key)
            if job is None or job["state"] in ("completed", "dead_letter"):
                return None
            until = job.get("leased_until")
            if job["state"] == "leased" and until and datetime.fromisoformat(until) > now:
                return None
            if job["attempts"] >= max_attempts:
                job.update(state="dead_letter", lease_id=None, leased_until=None)
                self.put(key, "job", job["event_id"], job)
                return None
            job.update(state="leased", attempts=job["attempts"] + 1,
                       lease_id=uuid4().hex, worker=worker,
                       leased_until=timestamp(now + timedelta(seconds=seconds)))
            self.put(key, "job", job["event_id"], job)
            return job

    def finish(self, job_id: str, lease_id: str, *, success: bool,
               error_type: str | None = None, max_attempts: int = 3) -> dict:
        """Reject stale results from a timed-out or replaced worker."""
        key = f"job|{job_id}"
        with self.store.lock("editorial-intelligence"):
            job = self.get(key)
            if not job or job["state"] != "leased" or job.get("lease_id") != lease_id:
                raise ValueError("job lease no longer valid")
            job.update(state="completed" if success else
                       ("dead_letter" if job["attempts"] >= max_attempts else "pending"),
                       lease_id=None, leased_until=None,
                       last_error_type=None if success else (error_type or "ResearchFailure")[:80])
            self.put(key, "job", job["event_id"], job)
            return job
