"""Plan one edition for the collector agents.

Writes two things into a directory shared with the collector containers:

    jobs/current.tsv              first line "#edition <id>", then one line per topic:
                                  <topic id> TAB <language> TAB <topic>
    context/<edition>/<id>.md     our earlier coverage of that topic (may be empty)

Collectors only read these files; the pipeline never starts a container itself.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .archive import prior_coverage
from .reports import slugify
from .storage import Store


@dataclass(frozen=True)
class Job:
    topic_id: str
    language: str
    topic: str


def load_topics(path: str | Path) -> list[Job]:
    """One topic per line: <language>|<topic>. Blank lines and # comments are skipped."""
    jobs: dict[str, Job] = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        language, sep, topic = line.partition("|")
        language, topic = language.strip().lower(), " ".join(topic.split())
        if not sep or not language or not topic:
            raise ValueError(f"{path}:{number}: expected '<language>|<topic>', got {line!r}")
        job = Job(f"{language}-{slugify(topic)}", language, topic)
        jobs.setdefault(job.topic_id, job)
    return list(jobs.values())


def _write_atomic(path: Path, text: str) -> None:
    """Readers in other containers must never see a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_plan(store: Store, jobs: list[Job], edition: str, shared_dir: str | Path) -> Path:
    shared = Path(shared_dir)
    for job in jobs:
        _write_atomic(
            shared / "context" / edition / f"{job.topic_id}.md",
            prior_coverage(store, job.topic, job.language),
        )
    lines = [f"#edition {edition}"] + [f"{j.topic_id}\t{j.language}\t{j.topic}" for j in jobs]
    jobs_path = shared / "jobs" / "current.tsv"
    _write_atomic(jobs_path, "\n".join(lines) + "\n")
    return jobs_path
