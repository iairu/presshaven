"""Unit tests for core.session_view (Qt-free)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import session_view  # noqa: E402


def _session(**over):
    base = {"id": "abc123def456", "created_at": 100, "last_activity": 160, "ip_address": "203.0.113.9",
            "user_agent": "curl/8", "route_preference": "production", "risk_score": 55, "request_count": 7,
            "honeypot_bound": False, "compromised": False, "metadata": {"first_uri": "/"},
            "suspicious_activities": [
                {"timestamp": 150, "uri": "/b", "risk_score": 55, "patterns": ["sqli"]},
                {"timestamp": 120, "uri": "/a", "risk_score": 30, "patterns": {"xss": 1}}]}
    base.update(over)
    return base


def _snapshot(rows, threat=None):
    return json.dumps({"sessions": rows, "threat_ips": json.dumps(threat or {})})


class ParseTests(unittest.TestCase):
    def test_parse_session_fields_and_timeline_order(self):
        s = session_view.parse_session(json.dumps(_session()), pool="2",
                                       threat_ips={"203.0.113.9": {"reason": "scanner"}})
        self.assertEqual((s.ip, s.risk_score, s.request_count, s.duration), ("203.0.113.9", 55, 7, 60))
        self.assertEqual([e.uri for e in s.timeline], ["/a", "/b"])
        self.assertEqual(s.timeline[0].detail, "xss")
        self.assertEqual(s.ip_reputation["reason"], "scanner")
        self.assertTrue(s.diverted)

    def test_garbage_is_none(self):
        self.assertIsNone(session_view.parse_session("not json"))
        self.assertIsNone(session_view.parse_session("[1]"))

    def test_malformed_activities_skipped(self):
        self.assertEqual(session_view.parse_timeline([1, "x", {"timestamp": 5, "uri": "/"}])[0].uri, "/")
        self.assertEqual(session_view.parse_timeline("nope"), [])


class VerdictTests(unittest.TestCase):
    def _v(self, **over):
        return session_view.parse_session(json.dumps(_session(suspicious_activities=[], **over))).verdict

    def test_verdicts(self):
        self.assertEqual(self._v(risk_score=0), "benign")
        self.assertEqual(self._v(risk_score=50), "suspicious")
        self.assertEqual(self._v(risk_score=85), "over threshold")
        self.assertEqual(self._v(risk_score=85, honeypot_bound=True), "diverted")
        self.assertEqual(self._v(compromised=True), "compromised")


class SnapshotTests(unittest.TestCase):
    def test_sorted_riskiest_first_and_pool_joined(self):
        rows = [{"id": "a", "session": json.dumps(_session(id="a", risk_score=10)), "pool": ""},
                {"id": "b", "session": json.dumps(_session(id="b", risk_score=90)), "pool": "3"},
                {"id": "c", "session": "garbage", "pool": ""}]
        out = session_view.parse_snapshot(_snapshot(rows))
        self.assertEqual([s.session_id for s in out], ["b", "a"])
        self.assertEqual(out[0].pool, "3")

    def test_empty_lua_table_encodes_as_object(self):
        self.assertEqual(session_view.parse_snapshot('{"sessions": {}, "threat_ips": "{}"}'), [])
        self.assertEqual(session_view.parse_snapshot("junk"), [])

    def test_narrative_mentions_pool_and_first_uri(self):
        s = session_view.parse_session(json.dumps(_session()), pool="2")
        text = session_view.narrative(s)
        self.assertIn("pool 2", text)
        self.assertIn("/a", text)


if __name__ == "__main__":
    unittest.main()
