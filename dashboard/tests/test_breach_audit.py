"""Tests for core.breach_audit -- the attacker-perspective hardening audit.

These exercise the pure logic (result classification, pool discovery, the
headline verdict, probe command shapes, the fail-closed secret handling) with
the docker/HTTP boundaries mocked. No container, no network, no secret value is
ever touched.
"""
from __future__ import annotations

import unittest
from unittest import mock

from core import breach_audit as ba


class DiscoverPoolsTests(unittest.TestCase):
    def test_compose_and_runtime_names(self):
        names = [
            "honeypot-ids-system-v1-honeypot_eshop_2-1",
            "honeypot-ids-system-v1-honeypot_database-1",   # pool 1 of db layer
            "honeypot_eshop_5",                             # runtime pool
            "honeypot_database_5",
            "production_eshop",
            "reverse_proxy",
        ]
        pools = ba.discover_pools(names)
        self.assertIn(2, pools)
        self.assertIn(5, pools)
        self.assertEqual(pools[5]["eshop"], "honeypot_eshop_5")
        self.assertEqual(pools[5]["database"], "honeypot_database_5")

    def test_ignores_non_pool_containers(self):
        pools = ba.discover_pools(["reverse_proxy", "session_store", "pool_manager"])
        self.assertEqual(pools, {})


class ReachResultTests(unittest.TestCase):
    def _d(self, **kw):
        return ba._Reach("dest", "1.2.3.4", 80, **kw)

    def test_blocked_is_pass(self):
        r = ba._reach_result(ba.CAT_BREAKOUT, "hp1", self._d(), 7, "BLOCKED")
        self.assertEqual(r.outcome, ba.PASS)

    def test_open_is_fail(self):
        r = ba._reach_result(ba.CAT_BREAKOUT, "hp1", self._d(), 0, "OPEN")
        self.assertEqual(r.outcome, ba.FAIL)

    def test_probe_unavailable_is_error(self):
        r = ba._reach_result(ba.CAT_BREAKOUT, "hp1", self._d(), 0, "PROBE_UNAVAILABLE")
        self.assertEqual(r.outcome, ba.ERROR)

    def test_udp_label(self):
        r = ba._reach_result(ba.CAT_BREAKOUT, "hp1", self._d(udp=True), 0, "BLOCKED")
        self.assertTrue(r.probe.startswith("UDP"))


class HeadlineTests(unittest.TestCase):
    def _data(self, *outcomes_sev):
        d = ba.BreachAuditData("t", "l", "u", "reverse_proxy", ba.ALL_CATEGORIES)
        for outcome, sev in outcomes_sev:
            d.results.append(ba.ProbeResult(ba.CAT_BREAKOUT, "p", "e", outcome, "", sev))
        return d

    def test_breach_when_any_fail(self):
        d = self._data((ba.PASS, ba.HIGH), (ba.FAIL, ba.CRITICAL))
        status, _ = d.headline()
        self.assertEqual(status, "BREACH")

    def test_breach_reports_worst_severity(self):
        d = self._data((ba.FAIL, ba.MEDIUM), (ba.FAIL, ba.CRITICAL))
        _, summary = d.headline()
        self.assertIn("critical", summary)

    def test_warnings_without_fail(self):
        d = self._data((ba.PASS, ba.HIGH), (ba.WARN, ba.MEDIUM))
        status, _ = d.headline()
        self.assertTrue(status.startswith("HARDENED"))
        self.assertIn("warning", status.lower())

    def test_all_pass(self):
        d = self._data((ba.PASS, ba.HIGH), (ba.PASS, ba.HIGH))
        status, _ = d.headline()
        self.assertEqual(status, "HARDENED")

    def test_nothing_ran(self):
        d = self._data()
        status, _ = d.headline()
        self.assertEqual(status, "INCONCLUSIVE")

    def test_counts(self):
        d = self._data((ba.PASS, ba.HIGH), (ba.FAIL, ba.HIGH), (ba.WARN, ba.MEDIUM))
        c = d.counts()
        self.assertEqual(c[ba.PASS], 1)
        self.assertEqual(c[ba.FAIL], 1)
        self.assertEqual(c[ba.WARN], 1)


class ProbeCommandTests(unittest.TestCase):
    def test_tcp_probe_reports_open_or_blocked(self):
        cmd = ba._tcp_probe_cmd("production_database", 3306)
        self.assertIn("fsockopen", cmd)
        self.assertIn("OPEN", cmd)
        self.assertIn("BLOCKED", cmd)
        self.assertIn("3306", cmd)

    def test_breakout_destinations_cover_production_and_internet(self):
        names = ["production_eshop", "production_database", "honeypot_eshop_1"]
        dests = ba._breakout_destinations(names, 1)
        labels = " ".join(d.label for d in dests)
        self.assertIn("production database", labels)
        self.assertIn("internet", labels)
        self.assertIn("metadata", labels)
        self.assertIn("Docker daemon", labels)

    def test_breakout_includes_peer_pools_not_self(self):
        names = ["honeypot_eshop_1", "honeypot_eshop_2", "honeypot_database_2"]
        dests = ba._breakout_destinations(names, 1)
        hosts = [d.host for d in dests]
        self.assertIn("honeypot_eshop_2", hosts)
        self.assertNotIn("honeypot_eshop_1", hosts)  # never probe ourselves


class SecretHandlingTests(unittest.TestCase):
    def test_whitelist_skips_without_secret(self):
        results = ba.run_whitelist("https://localhost", "", log=lambda s: None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].outcome, ba.SKIP)

    def test_db_password_probe_compares_only_hashes(self):
        # Two different passwords -> different hashes -> PASS, and the probe
        # must never surface either value.
        def fake_exec(target, container, command, timeout=20.0):
            # command hashes $MYSQL_ROOT_PASSWORD; return a hash per container.
            h = "a" * 64 if "prod" in container else "b" * 64
            return 0, h
        with mock.patch.object(ba, "_docker_exec", side_effect=fake_exec):
            r = ba._db_password_shared_probe(
                mock.Mock(), ba.CAT_BREAKOUT, "honeypot_database_1", "production_database")
        self.assertEqual(r.outcome, ba.PASS)
        self.assertNotIn("a" * 64, r.evidence)
        self.assertNotIn("b" * 64, r.evidence)

    def test_db_password_probe_flags_shared(self):
        def fake_exec(target, container, command, timeout=20.0):
            return 0, "c" * 64  # same hash both sides == shared password
        with mock.patch.object(ba, "_docker_exec", side_effect=fake_exec):
            r = ba._db_password_shared_probe(
                mock.Mock(), ba.CAT_BREAKOUT, "honeypot_database_1", "production_database")
        self.assertEqual(r.outcome, ba.FAIL)
        self.assertEqual(r.severity, ba.CRITICAL)


class RoutingProbeTests(unittest.TestCase):
    def test_routes_to_honeypot(self):
        self.assertTrue(ba._routes_to_honeypot(ba._HttpResult(200, "honeypot", "80")))
        self.assertFalse(ba._routes_to_honeypot(ba._HttpResult(200, "production", "0")))

    def test_obfuscation_fail_when_served_production_unscored(self):
        # A crafted request that reaches production with score 0 is a real hole.
        def fake_req(base_url, path, secret, **kw):
            if path == ba._TARGET_PLUGIN:
                return ba._HttpResult(200, "honeypot", "80")       # baseline
            return ba._HttpResult(200, "production", "0")          # bypassed
        with mock.patch.object(ba, "_edge_request", side_effect=fake_req):
            results = ba.run_whitelist("https://localhost", "secret", log=lambda s: None)
        fails = [r for r in results if r.outcome == ba.FAIL]
        self.assertTrue(fails, "expected at least one bypass to be flagged FAIL")

    def test_obfuscation_pass_when_still_diverted(self):
        def fake_req(base_url, path, secret, **kw):
            return ba._HttpResult(200, "honeypot", "80")
        with mock.patch.object(ba, "_edge_request", side_effect=fake_req):
            results = ba.run_whitelist("https://localhost", "secret", log=lambda s: None)
        self.assertFalse([r for r in results if r.outcome == ba.FAIL])

    def test_edge_exposure_flags_leaked_header(self):
        # A wrong secret that still yields a routing header is a leak.
        def fake_req(base_url, path, secret, **kw):
            return ba._HttpResult(200, "honeypot", "80")
        with mock.patch.object(ba, "_edge_request", side_effect=fake_req):
            results = ba.run_edge_exposure("https://localhost", "secret", log=lambda s: None)
        leak = [r for r in results if "gated" in r.probe and r.outcome == ba.FAIL]
        self.assertTrue(leak)

    def test_edge_exposure_pass_when_header_withheld(self):
        def fake_req(base_url, path, secret, **kw):
            # No routing header for anyone, smuggling gets a 400.
            if kw.get("method") == "POST":
                return ba._HttpResult(400, None, None)
            return ba._HttpResult(200, None, None)
        with mock.patch.object(ba, "_edge_request", side_effect=fake_req):
            results = ba.run_edge_exposure("https://localhost", "secret", log=lambda s: None)
        self.assertFalse([r for r in results if r.outcome == ba.FAIL])


class PrivilegeProbeTests(unittest.TestCase):
    def test_privileged_container_fails(self):
        def fake_inspect(target, container, fmt, timeout=15.0):
            if "Privileged" in fmt:
                return "true"
            return ""
        with mock.patch.object(ba, "_inspect", side_effect=fake_inspect):
            results = ba._privilege_probes(mock.Mock(), ba.CAT_BREAKOUT, "honeypot_eshop_1")
        priv = [r for r in results if "privileged" in r.probe]
        self.assertEqual(priv[0].outcome, ba.FAIL)

    def test_docker_sock_mount_fails(self):
        def fake_inspect(target, container, fmt, timeout=15.0):
            if ".Mounts" in fmt and "Source" in fmt:
                return "/var/run/docker.sock->/var/run/docker.sock"
            return ""
        with mock.patch.object(ba, "_inspect", side_effect=fake_inspect):
            results = ba._privilege_probes(mock.Mock(), ba.CAT_BREAKOUT, "honeypot_eshop_1")
        sock = [r for r in results if "Docker socket" in r.probe]
        self.assertEqual(sock[0].outcome, ba.FAIL)

    def test_clean_container_passes(self):
        def fake_inspect(target, container, fmt, timeout=15.0):
            if "SecurityOpt" in fmt:
                return "no-new-privileges:true"
            if "Privileged" in fmt:
                return "false"
            return ""
        with mock.patch.object(ba, "_inspect", side_effect=fake_inspect):
            results = ba._privilege_probes(mock.Mock(), ba.CAT_BREAKOUT, "honeypot_eshop_1")
        self.assertFalse([r for r in results if r.outcome == ba.FAIL])


if __name__ == "__main__":
    unittest.main()
