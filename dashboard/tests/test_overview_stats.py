"""Unit tests for core.overview_stats -- the Overview page's summary math.

Stdlib unittest only (no PyQt6), run with the rest:

    cd dashboard && python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASHBOARD_DIR))

from core import overview_stats  # noqa: E402
from core.colors import GREEN, GREY, ORANGE, RED  # noqa: E402
from core.overview_stats import DEGRADED, OFFLINE, OPERATIONAL, STARTING_UP, STOPPED  # noqa: E402


def _c(service, state="running", health="healthy", exit_code="0"):
    return {"Service": service, "State": state, "Health": health, "ExitCode": exit_code}


def _exited(service, code="0"):
    return {"Service": service, "State": "exited", "ExitCode": code}


class ProjectHealthTests(unittest.TestCase):
    def test_project_containers_spans_local_and_remote(self):
        results = {
            "edge-local": [_c("proxy"), _c("redis")],
            "edge-remote": [_c("proxy")],
            "siem-local": [_c("es01")],
        }
        self.assertEqual(len(overview_stats.project_containers(results, "edge")), 3)
        self.assertEqual(len(overview_stats.project_containers(results, "siem")), 1)

    def test_all_up_is_operational(self):
        h = overview_stats.project_health({"edge-local": [_c("proxy"), _c("redis")]}, "edge")
        self.assertEqual((h.state, h.running, h.total, h.color, h.up), (OPERATIONAL, 2, 2, GREEN, True))

    def test_unhealthy_is_degraded(self):
        h = overview_stats.project_health({"edge-local": [_c("proxy", health="unhealthy"), _c("redis")]}, "edge")
        self.assertEqual((h.state, h.color), (DEGRADED, RED))

    def test_no_containers_is_offline(self):
        h = overview_stats.project_health({"edge-local": []}, "edge")
        self.assertEqual((h.state, h.total, h.up), (OFFLINE, 0, False))

    def test_all_exited_is_stopped_not_up(self):
        # The regression the user hit: a stopped stack of exited-0 services
        # must not read as "up" just because the exit code was clean.
        h = overview_stats.project_health({"edge-local": [_exited("proxy"), _exited("redis")]}, "edge")
        self.assertEqual((h.state, h.running, h.up), (STOPPED, 0, False))
        self.assertEqual(h.color, ORANGE)

    def test_running_plus_finished_oneshot_is_operational(self):
        h = overview_stats.project_health(
            {"edge-local": [_c("proxy"), _exited("init_setup")]}, "edge")
        self.assertEqual(h.state, OPERATIONAL)

    def test_starting(self):
        h = overview_stats.project_health({"siem-local": [_c("es01", health="starting")]}, "siem")
        self.assertEqual((h.state, h.color), (STARTING_UP, ORANGE))


class SystemSummaryTests(unittest.TestCase):
    def _edge(self, state):
        return overview_stats.ProjectHealth("edge", "Edge (IDS honeypot)", state, 1, 1)

    def _siem(self, state):
        return overview_stats.ProjectHealth("siem", "SIEM (ELK)", state, 1, 1)

    def test_both_up_operational(self):
        label, color, _cap = overview_stats.system_summary([self._edge(OPERATIONAL), self._siem(OPERATIONAL)])
        self.assertEqual((label, color), ("Operational", GREEN))

    def test_edge_down_siem_up_is_not_operational(self):
        # The exact reported bug.
        label, color, caption = overview_stats.system_summary([self._edge(STOPPED), self._siem(OPERATIONAL)])
        self.assertNotEqual(label, "Operational")
        self.assertEqual(color, RED)   # the honeypot being down is serious
        self.assertIn("Edge", label)
        self.assertIn("edge stopped", caption)

    def test_siem_down_edge_up_is_amber(self):
        label, color, _cap = overview_stats.system_summary([self._edge(OPERATIONAL), self._siem(OFFLINE)])
        self.assertEqual((label, color), ("SIEM down", ORANGE))

    def test_degraded_wins(self):
        label, color, _c = overview_stats.system_summary([self._edge(DEGRADED), self._siem(OPERATIONAL)])
        self.assertEqual((label, color), ("Degraded", RED))

    def test_both_down_offline(self):
        label, color, _c = overview_stats.system_summary([self._edge(OFFLINE), self._siem(OFFLINE)])
        self.assertEqual((label, color), ("Offline", GREY))

    def test_empty(self):
        self.assertEqual(overview_stats.system_summary([])[0], "Idle")


class EventCountTests(unittest.TestCase):
    def _events(self, now):
        return [
            {"timestamp": now - 10, "label": "Final decision: HONEYPOT"},
            {"timestamp": now - 20, "label": "SQL injection pattern (+40)"},
            {"timestamp": now - 7200, "label": "Routed to HONEYPOT"},  # old
        ]

    def test_is_diversion(self):
        self.assertTrue(overview_stats.is_diversion({"label": "Routed to HONEYPOT"}))
        self.assertFalse(overview_stats.is_diversion({"label": "SQL injection (+40)"}))
        self.assertFalse(overview_stats.is_diversion({}))

    def test_window_counts(self):
        now = 1_000_000.0
        counts = overview_stats.event_window_counts(self._events(now), window_seconds=3600, now=now)
        self.assertEqual(counts["window_total"], 2)
        self.assertEqual(counts["window_diversions"], 1)
        self.assertEqual(counts["total"], 3)
        self.assertEqual(counts["total_diversions"], 2)
        self.assertEqual(counts["last_timestamp"], now - 10)

    def test_empty_history(self):
        counts = overview_stats.event_window_counts([], now=1_000_000.0)
        self.assertEqual(counts["window_total"], 0)
        self.assertIsNone(counts["last_timestamp"])


if __name__ == "__main__":
    unittest.main()
