"""Agent selection, budgets and job status. Standard library only."""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path

from prismunfold.plan import Job, assign, available_agents, job_status, load_topics, read_plan, write_plan
from prismunfold.storage import Store

AGENTS = ["codex", "claude", "vibe", "goose"]


def jobs(n: int) -> list[Job]:
    return [Job(f"en-topic-{i}", "en", f"Topic {i}") for i in range(n)]


class AssignTest(unittest.TestCase):
    def test_not_every_agent_writes_about_every_topic(self):
        assigned = assign(jobs(6), "2026-11-12T18", AGENTS, per_topic=2, budget=6)
        self.assertTrue(all(len(j.agents) == 2 for j in assigned))
        self.assertTrue(all(len(set(j.agents)) == 2 for j in assigned))

    def test_work_is_spread_evenly_and_the_budget_holds(self):
        assigned = assign(jobs(8), "2026-11-12T18", AGENTS, per_topic=2, budget=4)
        load = Counter(a for j in assigned for a in j.agents)
        self.assertEqual(set(load.values()), {4})  # 16 slots over 4 agents
        tight = assign(jobs(8), "2026-11-12T18", AGENTS, per_topic=2, budget=1)
        self.assertEqual(max(Counter(a for j in tight for a in j.agents).values()), 1)
        self.assertEqual(sum(len(j.agents) for j in tight), 4)  # budget exhausted: later topics get nobody

    def test_pairing_rotates_between_editions(self):
        first = [j.agents for j in assign(jobs(4), "2026-11-12T18", AGENTS, 2, 6)]
        second = [j.agents for j in assign(jobs(4), "2026-11-13T00", AGENTS, 2, 6)]
        self.assertNotEqual(first, second)
        self.assertEqual(first, [j.agents for j in assign(jobs(4), "2026-11-12T18", AGENTS, 2, 6)])

    def test_explicit_agents_are_respected_and_count_against_the_budget(self):
        fixed = Job("en-fixed", "en", "Fixed", ("goose",))
        assigned = assign([fixed, *jobs(2)], "2026-11-12T18", AGENTS, per_topic=1, budget=1)
        self.assertEqual(assigned[0].agents, ("goose",))
        self.assertNotIn("goose", [a for j in assigned[1:] for a in j.agents])

    def test_no_available_agent_leaves_topics_unassigned(self):
        self.assertEqual([j.agents for j in assign(jobs(2), "e", [], 2, 6)], [(), ()])


class AvailabilityTest(unittest.TestCase):
    def test_only_agents_with_a_fresh_heartbeat_are_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = time.time()
            self.assertEqual(available_agents(tmp, AGENTS, 600, now), AGENTS)  # nobody announced yet
            beats = Path(tmp) / "_agents"
            beats.mkdir()
            (beats / "claude.ready").write_text("x")
            (beats / "codex.ready").write_text("x")
            os.utime(beats / "codex.ready", (now - 3600, now - 3600))
            (beats / "mallory.ready").write_text("x")
            self.assertEqual(available_agents(tmp, AGENTS, 600, now), ["claude"])
        self.assertEqual(available_agents(None, AGENTS, 600, 0), AGENTS)


class WritePlanTest(unittest.TestCase):
    def test_assignments_stay_fixed_within_an_edition_and_new_topics_are_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(f"{tmp}/db.sqlite3")
            cfg = {"enabled": AGENTS, "per_topic": 2, "max_topics_per_agent": 6}
            path = write_plan(store, jobs(2), "2026-11-12T18", f"{tmp}/shared", cfg)
            edition, first = read_plan(path)
            self.assertEqual(edition, "2026-11-12T18")

            # Later the pool shrinks to one agent; planned topics keep their writers.
            beats = Path(tmp) / "out" / "_agents"
            beats.mkdir(parents=True)
            (beats / "goose.ready").write_text("x")
            write_plan(store, jobs(3), "2026-11-12T18", f"{tmp}/shared", cfg, f"{tmp}/out")
            _, second = read_plan(path)
            self.assertEqual(second["en-topic-0"], first["en-topic-0"])
            self.assertEqual(second["en-topic-1"], first["en-topic-1"])
            self.assertEqual(second["en-topic-2"].agents, ("goose",))

            # A new edition is planned from scratch.
            write_plan(store, jobs(1), "2026-11-13T00", f"{tmp}/shared", cfg, f"{tmp}/out")
            edition, third = read_plan(path)
            self.assertEqual(edition, "2026-11-13T00")
            self.assertEqual(third["en-topic-0"].agents, ("goose",))
            store.close()

    def test_topics_file_may_name_agents_and_rejects_unknown_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topics.txt"
            path.write_text("en|Energy|claude, codex\nde|Verkehr\n", encoding="utf-8")
            loaded = load_topics(path)
            self.assertEqual(loaded[0].agents, ("claude", "codex"))
            self.assertEqual(loaded[1].agents, ())
            path.write_text("en|Energy|mallory\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown agent"):
                load_topics(path)
            path.write_text("en|a|b|c\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "topics.txt:1"):
                load_topics(path)

    def test_unreadable_plan_file_is_treated_as_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.tsv"
            self.assertEqual(read_plan(path), (None, {}))
            path.write_text("garbage\n", encoding="utf-8")
            self.assertEqual(read_plan(path), (None, {}))


class JobStatusTest(unittest.TestCase):
    def test_status_files_are_summarised_and_never_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "2026-11-12T18"
            for agent in ("claude", "codex", "mallory"):
                (base / agent).mkdir(parents=True)
            ok = {"agent": "claude", "state": "done", "attempts": 1, "seconds": 40}
            (base / "claude" / "a.status").write_text(json.dumps(ok))
            (base / "claude" / "b.status").write_text(json.dumps({"state": "failed", "attempts": 3, "seconds": 90}))
            (base / "codex" / "a.status").write_text(json.dumps({"state": "retrying", "attempts": 1, "seconds": 5}))
            (base / "codex" / "weird.status").write_text(json.dumps({"state": "<script>", "attempts": "many"}))
            (base / "codex" / "broken.status").write_text("{nope")
            (base / "codex" / "huge.status").write_text("x" * 100_000)
            (base / "codex" / "list.status").write_text("[1,2]")
            (base / "mallory" / "a.status").write_text(json.dumps(ok))

            summary = job_status(tmp, "2026-11-12T18")
            self.assertEqual(summary["agents"]["claude"], {"done": 1, "retrying": 0, "failed": 1, "unknown": 0, "attempts": 4, "seconds": 130})
            self.assertEqual(summary["agents"]["codex"]["retrying"], 1)
            self.assertEqual(summary["agents"]["codex"]["unknown"], 1)
            self.assertNotIn("mallory", summary["agents"])
            self.assertNotIn("<script>", json.dumps(summary))
            self.assertEqual(job_status(tmp, "../..")["jobs"], [])


if __name__ == "__main__":
    unittest.main()
