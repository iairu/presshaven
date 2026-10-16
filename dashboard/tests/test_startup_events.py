"""Tests for core/startup_events.py -- start-up events and warnings of the
Services report, and the docker_ctl gate on the SIEM log shipper.

    cd dashboard && python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.startup_events import chart_groups, detect_events, start_warnings  # noqa: E402


def run(*snapshots):
    """Feed successive {service: state} snapshots, one per second."""
    events, prev = [], {}
    for t, cur in enumerate(snapshots):
        detect_events(prev, cur, float(t), events)
        prev = cur
    return [label for _t, label in events]


class EventTests(unittest.TestCase):
    def test_created_is_not_started(self):
        labels = run({"kibana": "created"}, {"kibana": "starting"}, {"kibana": "healthy"})
        self.assertEqual(labels, ["kibana created", "kibana running, health pending", "kibana healthy"])

    def test_one_shot_job_finishes_then_is_removed(self):
        labels = run({"init": "created"}, {"init": "running"}, {"init": "exited_ok"}, {})
        self.assertEqual(labels, ["init created", "init started", "init finished", "init removed"])

    def test_running_service_that_goes_away_is_stopped(self):
        self.assertEqual(run({"es01": "healthy"}, {})[-1], "es01 stopped")

    def test_failed_job(self):
        self.assertEqual(run({"job": "running"}, {"job": "exited_bad"})[-1], "job exited (error)")


class WarningTests(unittest.TestCase):
    def test_failed_unstarted_and_noisy_services_are_flagged(self):
        ps = [{"Service": "setup", "State": "exited", "ExitCode": 1},
              {"Service": "late", "State": "created", "ExitCode": 0},
              {"Service": "ok", "State": "running", "Health": "healthy", "ExitCode": 0}]
        logs = ("vector_outbound-1  | WARN Retrying after error. error=dns error\n"
                "vector_outbound-1  | WARN Retrying after error. error=dns error\n"
                "kibana-1  | [2026-10-16T06:54:22.603+00:00][INFO ][plugins.notifications] Email Service Error\n"
                "es01-1  | started\n")
        w = dict(start_warnings(ps, logs))
        self.assertEqual(w["setup"], "exited with code 1")
        self.assertEqual(w["late"], "created but never started")
        self.assertTrue(w["vector_outbound"].startswith("2 error line(s)"))
        self.assertNotIn("kibana", w)          # an INFO line is not an error
        self.assertNotIn("ok", w)

    def test_clean_start_has_no_warnings(self):
        self.assertEqual(start_warnings([{"Service": "es01", "State": "running",
                                          "Health": "healthy", "ExitCode": 0}], "es01-1  | ready\n"), [])


class ChartGroupTests(unittest.TestCase):
    def test_small_stack_is_one_chart(self):
        self.assertEqual(chart_groups(["kibana", "es01", "vector_inbound"]),
                         [("", ["es01", "kibana", "vector_inbound"])])

    def test_edge_stack_is_split_by_role_with_at_most_8_per_chart(self):
        edge = ["backup_service", "honeypot_content_sync", "honeypot_database_1", "honeypot_database_2",
                "honeypot_database_3", "honeypot_db_migration", "honeypot_db_seed_1", "honeypot_db_seed_2",
                "honeypot_db_seed_3", "honeypot_eshop_1", "honeypot_eshop_2", "honeypot_eshop_3", "init_setup",
                "log_capper", "pool_manager", "production_database", "production_db_seed", "production_eshop",
                "reverse_proxy", "session_store", "suricata_ids", "vector_outbound"]
        groups = dict(chart_groups(edge))
        self.assertEqual(sorted(s for m in groups.values() for s in m), sorted(edge))
        self.assertTrue(all(len(m) <= 8 for m in groups.values()))
        self.assertIn("init_setup", groups["One-shot jobs"])
        self.assertIn("production_database", groups["Databases"])
        self.assertEqual(groups["Shops"], ["honeypot_eshop_1", "honeypot_eshop_2", "honeypot_eshop_3",
                                           "production_eshop"])


class ShipperGateTests(unittest.TestCase):
    def test_siem_shipping(self):
        from core.docker_ctl import siem_shipping
        self.assertFalse(siem_shipping({"ELK_ENABLED": "false", "VECTOR_HOST": "10.0.0.5"})[0])
        self.assertFalse(siem_shipping({"ELK_ENABLED": "true", "VECTOR_HOST": "your-siem-vm.example.com"})[0])
        self.assertFalse(siem_shipping({"ELK_ENABLED": "true"})[0])
        self.assertTrue(siem_shipping({"ELK_ENABLED": "true", "VECTOR_HOST": "host.docker.internal"})[0])

    def test_whole_stack_up_scales_the_shipper_to_zero_when_disabled(self):
        from core.docker_ctl import Target
        t = Target("edge")
        t.siem_shipping = lambda: (False, "ELK_ENABLED is not true")
        self.assertIn("vector_outbound=0", t.build("up", "-d")[0])
        self.assertNotIn("vector_outbound=0", t.build("up", "-d", "--force-recreate", "reverse_proxy")[0])
        self.assertNotIn("vector_outbound=0", t.build("down")[0])
        t.siem_shipping = lambda: (True, "")
        self.assertNotIn("vector_outbound=0", t.build("up", "-d")[0])


if __name__ == "__main__":
    unittest.main()
