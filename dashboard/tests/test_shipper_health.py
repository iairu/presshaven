"""Unit tests for core.shipper_health (Qt-free)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import shipper_health as sh  # noqa: E402

OK = "vector_outbound-1  | 2026-10-17T08:00:01.100Z  INFO vector::topology::builder: Healthcheck passed.\n"
RETRY = ("vector_outbound-1  | 2026-10-17T08:05:00.000Z  WARN sink{component_id=siem}:request{request_id=1}: "
         "vector::sinks::util::retries: Retrying after error. error=Request failed: tls handshake eof "
         "internal_log_rate_limit=true\n")
NOISE = "vector_outbound-1  | 2026-10-17T08:00:00Z INFO vector: Vector has started.\n"


class AnalyseTests(unittest.TestCase):
    def test_healthy(self):
        h = sh.analyse_logs(NOISE + OK)
        self.assertEqual(h.verdict, sh.DELIVERING)
        self.assertEqual(h.last_ok, "2026-10-17T08:00:01.100Z")
        self.assertEqual(h.error_count, 0)

    def test_failing_after_ok(self):
        h = sh.analyse_logs(OK + RETRY)
        self.assertEqual(h.verdict, sh.FAILING)
        self.assertEqual(h.error_count, 1)
        self.assertIn("tls handshake eof", h.last_error_text)
        self.assertNotIn("internal_log_rate_limit", h.last_error_text)

    def test_recovered(self):
        h = sh.analyse_logs(RETRY + OK)
        self.assertEqual(h.verdict, sh.DELIVERING)
        self.assertIn("1 earlier error", h.detail)

    def test_unconfirmed_with_no_signal(self):
        self.assertEqual(sh.analyse_logs(NOISE).verdict, sh.UNCONFIRMED)
        self.assertEqual(sh.analyse_logs("").verdict, sh.UNCONFIRMED)

    def test_ansi_and_prefix_stripped(self):
        h = sh.analyse_logs("\x1b[36mvector_outbound-1  |\x1b[0m 2026-10-17T08:00:01Z Healthcheck passed.\n")
        self.assertEqual(h.verdict, sh.DELIVERING)

    def test_evidence_capped_newest_last(self):
        h = sh.analyse_logs(RETRY * 30 + OK)
        self.assertEqual(len(h.evidence), 12)
        self.assertTrue(h.evidence[-1].ok)


class CombineTests(unittest.TestCase):
    def test_disabled_wins(self):
        h = sh.combine(False, "ELK_ENABLED is not true", None, OK)
        self.assertEqual(h.verdict, sh.DISABLED)
        self.assertIn("ELK_ENABLED", h.detail)

    def test_container_down(self):
        self.assertEqual(sh.combine(True, "", None, OK).verdict, sh.STOPPED)
        exited = {"State": "exited", "ExitCode": "1"}
        self.assertEqual(sh.combine(True, "", exited, OK).verdict, sh.STOPPED)

    def test_running_uses_logs(self):
        running = {"State": "running", "Health": ""}
        self.assertEqual(sh.combine(True, "", running, OK + RETRY).verdict, sh.FAILING)

    def test_index_stats(self):
        text = ('[{"index":"honeypot-nginx_access-2026.10.17","docs.count":"166","store.size":"1mb"},'
                '{"index":"honeypot-suricata-2026.10.17","docs.count":"41","store.size":"300kb"}]')
        stats = sh.parse_index_stats(text)
        self.assertEqual(stats["total_docs"], 207)
        self.assertEqual(stats["index_count"], 2)
        self.assertEqual(stats["indices"][0][0], "honeypot-nginx_access-2026.10.17")

    def test_index_stats_bad_input(self):
        self.assertIsNone(sh.parse_index_stats("missing authentication credentials"))
        self.assertIsNone(sh.parse_index_stats('{"error":"x"}'))
        self.assertEqual(sh.parse_index_stats("[]")["total_docs"], 0)

    def test_aggregator_state(self):
        self.assertEqual(sh.aggregator_state([{"Service": "vector_inbound", "State": "running", "Health": "healthy"}]),
                         "healthy")
        self.assertEqual(sh.aggregator_state([{"Service": "es01", "State": "running"}]), "unknown")
        self.assertEqual(sh.aggregator_state([]), "unknown")


if __name__ == "__main__":
    unittest.main()
