"""Unit tests for core.alert_policy (Qt-free; webhook tested against a local server)."""
from __future__ import annotations

import http.server
import json
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import alert_policy as ap  # noqa: E402
from core.pattern_log_parser import COLOR_HIGH, COLOR_LOW, COLOR_MED  # noqa: E402


class PolicyTests(unittest.TestCase):
    def test_defaults_and_sanitising(self):
        p = ap.AlertPolicy.from_dict({"min_severity": "bogus", "score_threshold": 500, "extra": 1})
        self.assertEqual((p.min_severity, p.score_threshold), ("high", 100))
        self.assertEqual(ap.AlertPolicy.from_dict(None), ap.AlertPolicy())
        self.assertEqual(ap.AlertPolicy.from_dict(p.to_dict()), p)

    def test_severity_threshold(self):
        p, sent = ap.AlertPolicy(on_diversion=False), {}
        self.assertFalse(ap.should_alert(p, "signal", "a", COLOR_MED, None, sent, 0))
        self.assertTrue(ap.should_alert(p, "signal", "b", COLOR_HIGH, None, sent, 0))
        p.min_severity = "medium"
        self.assertTrue(ap.should_alert(p, "signal", "c", COLOR_MED, None, sent, 0))
        self.assertFalse(ap.should_alert(p, "signal", "d", COLOR_LOW, None, sent, 0))

    def test_diversion_and_score_override_severity(self):
        p, sent = ap.AlertPolicy(min_severity="high", score_threshold=70), {}
        self.assertTrue(ap.should_alert(p, "outcome", "Routed to HONEYPOT", COLOR_LOW, 10, sent, 0))
        self.assertTrue(ap.should_alert(p, "signal", "scored", COLOR_LOW, 75, sent, 0))
        self.assertFalse(ap.should_alert(p, "signal", "quiet", COLOR_LOW, 20, sent, 0))

    def test_cooldown_per_label(self):
        p, sent = ap.AlertPolicy(cooldown_seconds=60), {}
        self.assertTrue(ap.should_alert(p, "signal", "x", COLOR_HIGH, None, sent, 100))
        self.assertFalse(ap.should_alert(p, "signal", "x", COLOR_HIGH, None, sent, 150))
        self.assertTrue(ap.should_alert(p, "signal", "y", COLOR_HIGH, None, sent, 150))
        self.assertTrue(ap.should_alert(p, "signal", "x", COLOR_HIGH, None, sent, 161))

    def test_disabled(self):
        self.assertFalse(ap.should_alert(ap.AlertPolicy(enabled=False), "outcome", "HONEYPOT",
                                         COLOR_HIGH, 99, {}, 0))


class WebhookTests(unittest.TestCase):
    def test_rejects_non_http(self):
        self.assertIn("http", ap.send_webhook("file:///etc/passwd", {}))

    def test_posts_json(self):
        got = {}

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                got["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.handle_request, daemon=True).start()
        payload = ap.webhook_payload("Routed to HONEYPOT", "Score: 90", "high", 90, 1)
        self.assertEqual(ap.send_webhook(f"http://127.0.0.1:{srv.server_port}/", payload), "")
        srv.server_close()
        self.assertIn("HIGH", got["body"]["text"])
        self.assertEqual(got["body"]["score"], 90)

    def test_unreachable_returns_error(self):
        self.assertTrue(ap.send_webhook("http://127.0.0.1:1/", {}, timeout=1))


if __name__ == "__main__":
    unittest.main()
