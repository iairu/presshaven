"""Unit tests for core.live_events (Qt-free)."""
from __future__ import annotations

import csv
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import live_events  # noqa: E402
from core.pattern_log_parser import COLOR_HIGH, COLOR_INFO, COLOR_LOW, COLOR_MED  # noqa: E402


class SeverityTests(unittest.TestCase):
    def test_colour_mapping(self):
        self.assertEqual(live_events.severity(COLOR_HIGH), "high")
        self.assertEqual(live_events.severity(COLOR_MED), "medium")
        self.assertEqual(live_events.severity(COLOR_LOW), "low")
        self.assertEqual(live_events.severity(COLOR_INFO), "info")
        self.assertEqual(live_events.severity("#123456"), "info")

    def test_rank_orders_severities(self):
        self.assertLess(live_events.severity_rank(COLOR_LOW), live_events.severity_rank(COLOR_HIGH))


class FilterTests(unittest.TestCase):
    def test_all_passes_everything(self):
        self.assertTrue(live_events.matches("all", "signal", "x", COLOR_INFO))

    def test_medium_and_high(self):
        self.assertFalse(live_events.matches("medium", "signal", "x", COLOR_LOW))
        self.assertTrue(live_events.matches("medium", "signal", "x", COLOR_MED))
        self.assertTrue(live_events.matches("medium", "signal", "x", COLOR_HIGH))
        self.assertFalse(live_events.matches("high", "signal", "x", COLOR_MED))

    def test_diversions_and_outcomes(self):
        self.assertTrue(live_events.matches("diversions", "outcome", "Routed to HONEYPOT", COLOR_HIGH))
        self.assertFalse(live_events.matches("diversions", "outcome", "Routed to PRODUCTION", COLOR_LOW))
        self.assertTrue(live_events.matches("outcomes", "outcome", "x", COLOR_LOW))
        self.assertFalse(live_events.matches("outcomes", "signal", "x", COLOR_LOW))

    def test_text_match(self):
        self.assertTrue(live_events.text_matches("", "anything"))
        self.assertTrue(live_events.text_matches("SQL", "sql injection", "d"))
        self.assertFalse(live_events.text_matches("xss", "sql injection", "d"))


class CsvTests(unittest.TestCase):
    def test_csv_round_trip(self):
        text = live_events.to_csv([(0, "high", "outcome", "Routed, to HONEYPOT", 'a "b"')])
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[0], ["time", "severity", "kind", "label", "detail"])
        self.assertEqual(rows[1], ["", "high", "outcome", "Routed, to HONEYPOT", 'a "b"'])


if __name__ == "__main__":
    unittest.main()
