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


def _c(service, state="running", health="healthy", exit_code="0"):
    return {"Service": service, "State": state, "Health": health, "ExitCode": exit_code}


class ProjectAggregationTests(unittest.TestCase):
    def test_project_containers_spans_local_and_remote(self):
        results = {
            "edge-local": [_c("proxy"), _c("redis")],
            "edge-remote": [_c("proxy")],
            "siem-local": [_c("es01")],
        }
        self.assertEqual(len(overview_stats.project_containers(results, "edge")), 3)
        self.assertEqual(len(overview_stats.project_containers(results, "siem")), 1)

    def test_project_summary_all_up(self):
        results = {"edge-local": [_c("proxy"), _c("redis")]}
        text, color, up, total = overview_stats.project_summary(results, "edge")
        self.assertEqual((up, total), (2, 2))
        self.assertEqual(color, GREEN)

    def test_project_summary_flags_unhealthy(self):
        results = {"edge-local": [_c("proxy", health="unhealthy"), _c("redis")]}
        _text, color, up, total = overview_stats.project_summary(results, "edge")
        self.assertEqual((up, total), (2, 2))  # unhealthy still counts as "up/running"
        self.assertEqual(color, RED)

    def test_empty_project(self):
        text, color, up, total = overview_stats.project_summary({}, "edge")
        self.assertEqual((up, total), (0, 0))
        self.assertEqual(color, GREY)


class OverallColorTests(unittest.TestCase):
    def test_worst_wins(self):
        self.assertEqual(overview_stats.overall_color([GREEN, ORANGE, GREEN]), ORANGE)
        self.assertEqual(overview_stats.overall_color([GREEN, RED, ORANGE]), RED)
        self.assertEqual(overview_stats.overall_color([GREEN, GREEN]), GREEN)

    def test_empty_is_grey(self):
        self.assertEqual(overview_stats.overall_color([]), GREY)


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
