"""Tests for core/services_report.py helpers.

    cd dashboard && python3 -m unittest discover -s tests -v

Needs PyQt6, so it is skipped where PyQt6 isn't installed, like the Qt-free
CI job.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from core import services_report
except ImportError:  # PyQt6 missing
    services_report = None


@unittest.skipIf(services_report is None, "PyQt6 not installed")
class EventKeyTests(unittest.TestCase):
    def test_a_marker_lists_its_events_in_order(self):
        # Marker 5 of a start: the seeds' "started" came before their "finished".
        text = services_report._summarize_events([
            "honeypot_db_migration finished", "seed_1 started", "seed_2 started",
            "seed_1 finished", "seed_2 finished", "production_db_seed finished"])
        self.assertEqual(text, "finished: honeypot_db_migration; started: seed_1, seed_2; "
                               "finished: seed_1, seed_2, production_db_seed")

    def test_pending_then_healthy_in_one_marker_is_healthy(self):
        text = services_report._summarize_events([
            "db healthy", "session_store running, health pending", "pool_manager started",
            "session_store healthy"])
        self.assertEqual(text, "healthy: db, session_store; started: pool_manager")


if __name__ == "__main__":
    unittest.main()
