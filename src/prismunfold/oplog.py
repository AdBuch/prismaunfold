"""Structured operational logging.

Every pipeline component logs one JSON object per line through `event()`:

    {"timestamp": "...", "component": "bulletin", "event": "import_completed",
     "edition_date": "2026-11-25", "status": "test_import_unverified", ...}

Field names follow docs/OPERATIONS.md (run_id, provider, edition_date, article_id,
duration_ms, attempt, error_code, ...). Values that look like credentials are never
written: keys naming a secret are dropped and bearer/token-looking strings redacted.
Log validation reasons and identifiers, never complete model output or prompts.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone

SECRET_KEYS = re.compile(r"(token|secret|password|authorization|api[_-]?key|cookie)", re.I)
SECRET_VALUES = re.compile(r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|Bearer\s+\S+|sk-[A-Za-z0-9-]{16,})")
MAX_VALUE = 500

RUN_ID = os.environ.get("PRISMUNFOLD_RUN_ID") or uuid.uuid4().hex[:12]
_LOGGER = logging.getLogger("prismunfold.ops")


def _clean(value):
    if isinstance(value, str):
        value = SECRET_VALUES.sub("[redacted]", value)
        return value if len(value) <= MAX_VALUE else value[:MAX_VALUE] + "…"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in list(value)[:20]]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if not SECRET_KEYS.search(str(k))}
    return _clean(str(value))


def record(component: str, event_name: str, **fields) -> dict:
    """The log record as a dict (used by tests and by `event`)."""
    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "component": component,
        "event": event_name,
        "run_id": fields.pop("run_id", RUN_ID),
    }
    for key, value in fields.items():
        if value is None or SECRET_KEYS.search(key):
            continue
        out[key] = _clean(value)
    return out


def event(component: str, event_name: str, level: int = logging.INFO, **fields) -> dict:
    rec = record(component, event_name, **fields)
    if _LOGGER.handlers or logging.getLogger().handlers:
        _LOGGER.log(level, json.dumps(rec, ensure_ascii=False, sort_keys=False))
    else:
        print(json.dumps(rec, ensure_ascii=False), file=sys.stderr)
    return rec


def setup(level: int = logging.INFO) -> None:
    """One JSON object per line on stderr; idempotent."""
    if not _LOGGER.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        _LOGGER.addHandler(handler)
        _LOGGER.propagate = False
    _LOGGER.setLevel(level)


class Timer:
    """`with Timer() as t: ...; t.ms` gives the duration in milliseconds."""

    def __enter__(self):
        self._start = time.monotonic()
        self.ms = 0
        return self

    def __exit__(self, *exc):
        self.ms = int((time.monotonic() - self._start) * 1000)
        return False
