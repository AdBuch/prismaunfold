"""Plan one edition for the collector agents, and report on how the jobs went.

The pipeline writes two things into a directory shared with the collector containers:

    jobs/current.tsv              first line "#edition <id>", then one line per topic:
                                  <topic id> TAB <language> TAB <topic> TAB <agents>
    context/<edition>/<id>.md     our earlier coverage of that topic (may be empty)

Collectors only read these files; the pipeline never starts a container itself.

Not every agent writes about every topic. Each topic gets `per_topic` writers, chosen
in rotation so the pairing changes from edition to edition, within a budget of
`max_topics_per_agent` per edition. Only agents that recently announced themselves
(a heartbeat file written by their worker) are considered, so a missing API key or a
stopped container shrinks the pool instead of leaving topics unwritten. A topic line
may name its agents explicitly: "<language>|<topic>|claude,codex".

Once an edition is planned, its assignments stay fixed; later runs only add new topics.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .archive import prior_coverage
from .reports import COLLECTOR_AGENTS, EDITION_RE, slugify

DEFAULT_AGENTS = {
    "enabled": list(COLLECTOR_AGENTS),
    "per_topic": 2,
    "max_topics_per_agent": 6,
    "heartbeat_seconds": 1800,
}
MAX_STATUS_BYTES = 16 * 1024


@dataclass(frozen=True)
class Job:
    topic_id: str
    language: str
    topic: str
    agents: tuple[str, ...] = field(default=())  # empty: let the planner choose


def load_topics(path: str | Path) -> list[Job]:
    """One topic per line: <language>|<topic>[|<agent>,<agent>]. Blank lines and # comments are skipped."""
    jobs: dict[str, Job] = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) not in (2, 3) or not parts[0] or not parts[1]:
            raise ValueError(f"{path}:{number}: expected '<language>|<topic>[|<agents>]', got {line!r}")
        agents = tuple(a.strip().lower() for a in parts[2].split(",") if a.strip()) if len(parts) == 3 else ()
        unknown = [a for a in agents if a not in COLLECTOR_AGENTS]
        if unknown:
            raise ValueError(f"{path}:{number}: unknown agent(s) {', '.join(unknown)}")
        language, topic = parts[0].lower(), " ".join(parts[1].split())
        job = Job(f"{language}-{slugify(topic)}", language, topic, agents)
        jobs.setdefault(job.topic_id, job)
    return list(jobs.values())


def available_agents(reports_dir: str | Path | None, enabled: list[str], max_age: int, now: float) -> list[str]:
    """Enabled agents whose worker announced itself recently.

    Before any worker has ever announced itself (first start, or no reports directory),
    every enabled agent counts as available.
    """
    if reports_dir is None:
        return list(enabled)
    beats = Path(reports_dir) / "_agents"
    seen = {p.stem: p.stat().st_mtime for p in beats.glob("*.ready")} if beats.is_dir() else {}
    if not seen:
        return list(enabled)
    return [a for a in enabled if now - seen.get(a, 0) <= max_age]


def assign(
    jobs: list[Job], edition: str, pool: list[str], per_topic: int, budget: int, load: Counter[str] | None = None
) -> list[Job]:
    """Give every job without explicit agents `per_topic` writers from the pool.

    The starting point rotates with topic and edition, and the least loaded agents go
    first, so work is spread evenly and no agent exceeds its budget. `load` carries
    the assignments already made in this edition.
    """
    load = Counter() if load is None else load
    for job in jobs:
        load.update(job.agents)
    result: list[Job] = []
    for job in jobs:
        if job.agents or not pool:
            result.append(job)
            continue
        offset = int(hashlib.sha1(f"{job.topic_id}|{edition}".encode()).hexdigest(), 16) % len(pool)
        rotated = pool[offset:] + pool[:offset]
        ranked = sorted(rotated, key=lambda a: load[a])  # stable: ties keep the rotation order
        chosen = tuple(a for a in ranked if load[a] < budget)[:per_topic]
        load.update(chosen)
        result.append(Job(job.topic_id, job.language, job.topic, chosen))
    return result


def read_plan(jobs_path: Path) -> tuple[str | None, dict[str, Job]]:
    """The edition and jobs of an existing plan file; (None, {}) if absent or unreadable."""
    try:
        lines = jobs_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, {}
    if not lines or not lines[0].startswith("#edition "):
        return None, {}
    jobs: dict[str, Job] = {}
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= 3:
            agents = tuple(a for a in parts[3].split(",") if a) if len(parts) > 3 else ()
            jobs[parts[0]] = Job(parts[0], parts[1], parts[2], agents)
    return lines[0].removeprefix("#edition "), jobs


def _write_atomic(path: Path, text: str) -> None:
    """Readers in other containers must never see a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_plan(
    store,
    jobs: list[Job],
    edition: str,
    shared_dir: str | Path,
    agents_cfg: dict | None = None,
    reports_dir: str | Path | None = None,
    now: float | None = None,
) -> Path:
    cfg = {**DEFAULT_AGENTS, **(agents_cfg or {})}
    shared = Path(shared_dir)
    jobs_path = shared / "jobs" / "current.tsv"

    planned_edition, planned = read_plan(jobs_path)
    kept = planned if planned_edition == edition else {}
    fixed = [kept[j.topic_id] for j in jobs if j.topic_id in kept]
    fresh = [j for j in jobs if j.topic_id not in kept]
    load: Counter[str] = Counter(a for j in fixed for a in j.agents)
    pool = available_agents(
        reports_dir, [a for a in cfg["enabled"] if a in COLLECTOR_AGENTS], cfg["heartbeat_seconds"],
        time.time() if now is None else now,
    )
    assigned = {j.topic_id: j for j in fixed + assign(fresh, edition, pool, cfg["per_topic"], cfg["max_topics_per_agent"], load)}
    ordered = [assigned[j.topic_id] for j in jobs]

    for job in ordered:
        _write_atomic(
            shared / "context" / edition / f"{job.topic_id}.md",
            prior_coverage(store, job.topic, job.language),
        )
    lines = [f"#edition {edition}"] + [
        f"{j.topic_id}\t{j.language}\t{j.topic}\t{','.join(j.agents)}" for j in ordered
    ]
    _write_atomic(jobs_path, "\n".join(lines) + "\n")
    return jobs_path


def job_status(reports_dir: str | Path, edition: str) -> dict:
    """Summary of the collectors' job status files for one edition.

    Status files are written by the workers and are untrusted like reports: they are
    size-limited, type-checked and only counted, never executed or echoed verbatim.
    """
    summary: dict = {"edition": edition, "agents": {}, "jobs": []}
    if not EDITION_RE.match(edition):
        return summary
    for path in sorted(Path(reports_dir).glob(f"{edition}/*/*.status")):
        agent = path.parent.name
        if agent not in COLLECTOR_AGENTS or path.is_symlink():
            continue
        try:
            if path.stat().st_size > MAX_STATUS_BYTES:
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        state = raw.get("state") if raw.get("state") in ("done", "retrying", "failed") else "unknown"
        attempts = raw.get("attempts") if isinstance(raw.get("attempts"), int) else 0
        seconds = raw.get("seconds") if isinstance(raw.get("seconds"), int) else 0
        bucket = summary["agents"].setdefault(
            agent, {"done": 0, "retrying": 0, "failed": 0, "unknown": 0, "attempts": 0, "seconds": 0}
        )
        bucket[state] += 1
        bucket["attempts"] += max(attempts, 0)
        bucket["seconds"] += max(seconds, 0)
        summary["jobs"].append(
            {"agent": agent, "topic_id": path.stem, "state": state, "attempts": attempts, "seconds": seconds}
        )
    return summary
