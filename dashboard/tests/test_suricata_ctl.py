"""Unit tests for core.suricata_ctl parsing (Qt-free, no docker)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

DASH = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASH))

from core import suricata_ctl as sc  # noqa: E402

RULES = (
    '# header comment\n'
    'alert http any any -> $HOME_NET $HTTP_PORTS (msg:"Admin Panel Discovery"; classtype:web-application-attack; sid:1000052; rev:2;)\n'
    '# alert http any any -> $HOME_NET any (msg:"Old; \\"quoted\\" rule"; sid:1000053; rev:1;)\n'
    '\n'
)


def _eve(**over):
    e = {"timestamp": "2026-10-17T07:22:59+0000", "event_type": "alert", "src_ip": "1.2.3.4", "src_port": 5,
         "dest_ip": "10.0.0.1", "dest_port": 80,
         "alert": {"signature": "S", "signature_id": 9, "category": "C", "severity": 1, "action": "allowed"},
         "http": {"url": "/x", "http_user_agent": "ua"}}
    e.update(over)
    return json.dumps(e)


class AlertTests(unittest.TestCase):
    def test_parses_alerts_and_skips_noise(self):
        text = "\n".join([_eve(), '{"event_type":"flow"}', "garbage", "", _eve(src_ip="9.9.9.9")])
        alerts = sc.parse_alerts(text)
        self.assertEqual([a.src_ip for a in alerts], ["1.2.3.4", "9.9.9.9"])
        self.assertEqual(alerts[0].severity_label, "critical")
        self.assertEqual(alerts[0].url, "/x")

    def test_alert_without_http(self):
        a = sc.parse_alerts(_eve(http=None))[0]
        self.assertEqual(a.url, "")

    def test_summarize(self):
        alerts = sc.parse_alerts("\n".join([_eve(), _eve(), _eve(src_ip="7.7.7.7")]))
        s = sc.summarize(alerts)
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["by_severity"], {"critical": 3})
        self.assertEqual(s["top_sources"][0], ("1.2.3.4", 2))


class RuleTests(unittest.TestCase):
    def test_parse_rules_enabled_and_disabled(self):
        rules = sc.parse_rules(RULES)
        self.assertEqual([(r.sid, r.enabled) for r in rules], [(1000052, True), (1000053, False)])
        self.assertEqual(rules[0].msg, "Admin Panel Discovery")
        self.assertEqual((rules[0].classtype, rules[0].rev), ("web-application-attack", 2))
        self.assertIn("quoted", rules[1].msg)

    def test_toggle_round_trip(self):
        off = sc.set_rule_enabled(RULES, 1000052, False)
        self.assertFalse({r.sid: r for r in sc.parse_rules(off)}[1000052].enabled)
        on = sc.set_rule_enabled(off, 1000052, True)
        self.assertEqual(on, RULES)

    def test_enable_commented_rule(self):
        on = sc.set_rule_enabled(RULES, 1000053, True)
        self.assertTrue({r.sid: r for r in sc.parse_rules(on)}[1000053].enabled)

    def test_unknown_sid(self):
        with self.assertRaises(sc.SuricataError):
            sc.set_rule_enabled(RULES, 42, False)

    def test_real_rules_file_parses(self):
        path = DASH.parent / "ids" / "suricata_rules" / "local.rules"
        if not path.exists():
            self.skipTest("no local.rules")
        rules = sc.parse_rules(path.read_text())
        self.assertGreater(len(rules), 10)
        self.assertEqual(len({r.sid for r in rules}), len(rules))


if __name__ == "__main__":
    unittest.main()
