"""Unit tests for core.eta (Qt-free)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import eta  # noqa: E402


class RemainingSecondsTests(unittest.TestCase):
    def test_half_done_mirrors_elapsed(self):
        self.assertAlmostEqual(eta.remaining_seconds(60.0, 0.5), 60.0)

    def test_quarter_done(self):
        self.assertAlmostEqual(eta.remaining_seconds(30.0, 0.25), 90.0)

    def test_complete_is_zero(self):
        self.assertEqual(eta.remaining_seconds(100.0, 1.0), 0.0)

    def test_not_estimable_yet(self):
        self.assertIsNone(eta.remaining_seconds(0.0, 0.5))
        self.assertIsNone(eta.remaining_seconds(10.0, 0.0))


class FormatEtaTests(unittest.TestCase):
    def test_none_reads_as_estimating(self):
        self.assertEqual(eta.format_eta(None), "estimating…")

    def test_minutes_seconds(self):
        self.assertEqual(eta.format_eta(150), "~2:30")

    def test_sub_minute(self):
        self.assertEqual(eta.format_eta(5), "~0:05")

    def test_hours(self):
        self.assertEqual(eta.format_eta(3665), "~1:01:05")

    def test_negative_floored(self):
        self.assertEqual(eta.format_eta(-10), "~0:00")


class EtaTrackerTests(unittest.TestCase):
    def test_counts_down_between_updates(self):
        t = eta.EtaTracker()
        t.update(60.0, 0.5)             # 60 s left, anchored at t=60
        self.assertAlmostEqual(t.remaining_at(60.0), 60.0)
        self.assertAlmostEqual(t.remaining_at(75.0), 45.0)   # 15 s elapsed since anchor
        self.assertAlmostEqual(t.remaining_at(120.0), 0.0)   # floored, not negative

    def test_reanchors_on_update(self):
        t = eta.EtaTracker()
        t.update(10.0, 0.5)
        self.assertAlmostEqual(t.remaining_at(10.0), 10.0)
        t.update(30.0, 0.75)            # 30 s took 0.75 -> 10 s remain
        self.assertAlmostEqual(t.remaining_at(30.0), 10.0)

    def test_none_until_first_estimable_update(self):
        t = eta.EtaTracker()
        self.assertIsNone(t.remaining_at(5.0))
        t.update(10.0, 0.0)             # still not estimable
        self.assertIsNone(t.remaining_at(12.0))

    def test_reset_clears(self):
        t = eta.EtaTracker()
        t.update(10.0, 0.5)
        t.reset()
        self.assertIsNone(t.remaining_at(10.0))


if __name__ == "__main__":
    unittest.main()
