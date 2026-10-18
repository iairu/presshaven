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


class BackfillTests(unittest.TestCase):
    def test_rfc3339_to_epoch(self):
        import calendar
        self.assertEqual(live_events.rfc3339_to_epoch("2026-10-17T07:22:59.885Z"),
                         calendar.timegm((2026, 10, 17, 7, 22, 59, 0, 0, 0)))
        self.assertEqual(live_events.rfc3339_to_epoch(None), 0)
        self.assertEqual(live_events.rfc3339_to_epoch("nonsense"), 0)

    def test_parse_backfill_uses_log_timestamps_and_skips_noise(self):
        text = (
            "reverse_proxy-1  | 2026-10-17T07:22:59.100Z [LOCATION / HEADER] route_decision='honeypot' risk_score='90'\n"
            "reverse_proxy-1  | 2026-10-17T07:23:00.000Z SESSION DEBUG nothing to see\n"
        )
        rows = live_events.parse_backfill(text)
        self.assertEqual(len(rows), 1)
        ts, event = rows[0]
        self.assertEqual(ts, live_events.rfc3339_to_epoch("2026-10-17T07:22:59Z"))
        self.assertEqual(event.kind, "outcome")

    def test_parse_backfill_empty(self):
        self.assertEqual(live_events.parse_backfill(""), [])


class CsvTests(unittest.TestCase):
    def test_csv_round_trip(self):
        text = live_events.to_csv([(0, "high", "outcome", "Routed, to HONEYPOT", 'a "b"')])
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[0], ["time", "severity", "kind", "label", "detail"])
        self.assertEqual(rows[1], ["", "high", "outcome", "Routed, to HONEYPOT", 'a "b"'])


if __name__ == "__main__":
    unittest.main()
