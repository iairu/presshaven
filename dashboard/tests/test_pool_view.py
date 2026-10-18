"""Unit tests for core.pool_view (Qt-free)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import pool_view  # noqa: E402

NOW = 10_000


def _snap(**over):
    status = {"at": NOW, "pools": 5, "ready": 4, "free": 1, "waiting": 2, "room": 0, "spares": 1,
              "building": {"6": NOW - 5}, "max_pools": 10, "max_memory_mb": 8192, "max_cpus": 8.0,
              "mem_per_pool": 1536, "cpus_per_pool": 1.5, "idle_timeout": 1800, "capped": ""}
    snap = {"ready": ["1", "2", "3", "4"], "free": ["4"], "owners": {"1": 2, "2": 0, "3": 1, "4": 0},
            "capped": "", "waiting": 2, "status": json.dumps(status),
            "last_seen": ["1", str(NOW - 30), "4", str(NOW - 900)],
            "health": ["1", json.dumps({"healthy": True}), "2", json.dumps({"healthy": False})],
            "events": [json.dumps({"type": "build", "pool": 4, "at": NOW - 60, "seconds": 41.2}),
                       json.dumps({"type": "pool_health", "pool": 2, "healthy": False, "at": NOW - 50}),
                       json.dumps({"type": "capped", "reason": "memory budget", "at": NOW - 10}),
                       "not json"],
            "scaledown": 0, "now": NOW}
    snap.update(over)
    return json.dumps(snap)


class OverviewTests(unittest.TestCase):
    def test_headline_numbers(self):
        o = pool_view.parse_snapshot(_snap())
        self.assertTrue(o.manager_alive)
        self.assertEqual((o.pools, o.ready, o.free, o.waiting), (5, 4, 1, 2))
        self.assertEqual(o.building, [6])
        self.assertEqual((o.mem_used_mb, o.mem_max_mb), (7680, 8192))
        self.assertAlmostEqual(o.mem_fraction, 7680 / 8192)
        self.assertEqual(o.cpu_used, 7.5)

    def test_rows(self):
        rows = {r.number: r for r in pool_view.parse_snapshot(_snap()).rows}
        self.assertEqual((rows[1].owners, rows[1].idle_seconds, rows[1].static, rows[1].healthy), (2, 30, True, True))
        self.assertTrue(rows[4].free)
        self.assertFalse(rows[4].static)
        self.assertEqual(rows[4].idle_seconds, 900)
        self.assertIsNone(rows[3].idle_seconds)
        self.assertIs(rows[2].healthy, False)

    def test_events_readable_and_health_blips_hidden(self):
        texts = [t for _ts, t in pool_view.parse_snapshot(_snap()).events]
        self.assertEqual(texts, ["pool 4 built in 41s", "resource limit reached: memory budget"])

    def test_state_words(self):
        self.assertEqual(pool_view.parse_snapshot(_snap()).state, "scaling up")
        capped = json.loads(_snap())
        capped["status"] = json.dumps({**json.loads(capped["status"]), "capped": "memory budget"})
        self.assertEqual(pool_view.parse_snapshot(json.dumps(capped)).state, "capped")
        self.assertEqual(pool_view.parse_snapshot(_snap(status="")).state, "manager offline")

    def test_empty_lua_tables_and_garbage(self):
        o = pool_view.parse_snapshot(_snap(ready={}, free={}, owners={}, events={}, last_seen={}, health={}))
        self.assertEqual((o.rows, o.events), ([], []))
        self.assertFalse(pool_view.parse_snapshot("junk").manager_alive)
        self.assertEqual(pool_view.parse_snapshot("[]").pools, 0)


if __name__ == "__main__":
    unittest.main()
