"""Tests for core/startup_events.py -- start-up events and warnings of the
Services report, and the docker_ctl gate on the SIEM log shipper.

    cd dashboard && python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.startup_events import (chart_groups, detect_events, dominant_series, event_markers,  # noqa: E402
                                  log_warnings, nice_axis, peak_context, split_at_gaps,
                                  start_warnings, stop_warnings)


def run(*snapshots, operation="start"):
    """Feed successive {service: state} snapshots, one per second."""
    events, prev = [], {}
    for t, cur in enumerate(snapshots):
        detect_events(prev, cur, float(t), events, operation)
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

    def test_stop_words_a_database_exiting_as_stopped_then_removed(self):
        labels = run({"db": "healthy"}, {"db": "exited_ok"}, {}, operation="stop")[1:]
        self.assertEqual(labels, ["db stopped", "db removed"])

    def test_stop_seen_only_as_gone_is_stopped_and_removed(self):
        self.assertEqual(run({"es01": "healthy"}, {}, operation="stop")[1:], ["es01 stopped and removed"])

    def test_stop_killed_container(self):
        labels = run({"web": "running"}, {"web": "exited_bad"}, operation="stop")[1:]
        self.assertEqual(labels, ["web stopped (non-zero exit)"])

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
        # WARN lines that only mention an error are not called error lines.
        self.assertTrue(w["vector_outbound"].startswith("2 WARN line(s) mentioning an error"))
        self.assertNotIn("kibana", w)          # an INFO line is not an error
        self.assertNotIn("ok", w)

    def test_clean_start_has_no_warnings(self):
        self.assertEqual(start_warnings([{"Service": "es01", "State": "running",
                                          "Health": "healthy", "ExitCode": 0}], "es01-1  | ready\n"), [])


    def test_kibana_warn_line_is_not_an_error_line(self):
        logs = ("kibana  | [2026-10-17T08:53:12.000+00:00][WARN ][plugins.alerting] "
                "Error executing alerting telemetry task\n")
        self.assertTrue(dict(log_warnings(logs))["kibana"].startswith("1 WARN line(s)"))

    def test_real_error_lines(self):
        logs = "seed-1  | ERROR 1062 (23000): Duplicate entry\n"
        self.assertTrue(dict(log_warnings(logs))["seed"].startswith("1 error line(s)"))

    def test_stop_warnings(self):
        w = dict(stop_warnings({"suricata_ids": 137, "web": 143, "ok": 0, "bad": 2}, ""))
        self.assertIn("killed", w["suricata_ids"])
        self.assertNotIn("web", w)          # 143: ended by SIGTERM, a clean stop
        self.assertIn("2", w["bad"])
        self.assertNotIn("ok", w)


class MarkerTests(unittest.TestCase):
    def test_markers_span_at_most_the_window(self):
        events = [(16.6, "a started"), (18.2, "b started"), (20.3, "c started"), (21.6, "d started"),
                  (23.2, "e healthy"), (24.8, "f started")]
        markers = event_markers(events)
        self.assertTrue(all(t1 - t0 <= 1.5 for _n, t0, t1, _l in markers))
        self.assertEqual([m[3] for m in markers],
                         [["a started"], ["b started"], ["c started", "d started"],
                          ["e healthy"], ["f started"]])

    def test_same_check_shares_a_marker(self):
        self.assertEqual(len(event_markers([(7.0, "a created"), (7.0, "b created"), (7.6, "a started")])), 1)

    def test_peak_context(self):
        markers = event_markers([(31.0, "x"), (49.0, "y"), (51.0, "z")])
        self.assertEqual(peak_context(46.0, markers), "between markers 1 and 2")
        self.assertEqual(peak_context(50.0, markers), "at marker 2")
        self.assertEqual(peak_context(3.0, markers, 3.0),
                         "before marker 1 (the first sample of the recording)")
        self.assertEqual(peak_context(60.0, markers), "9 s after marker 3")


class ChartMathTests(unittest.TestCase):
    def test_nice_axis(self):
        self.assertEqual(nice_axis(513), (600, 200))
        self.assertEqual(nice_axis(297, 4), (300, 100))
        self.assertEqual(nice_axis(91, 8), (100, 20))
        self.assertEqual(nice_axis(8, 5), (8, 2))
        self.assertEqual(nice_axis(2135, 4), (3000, 1000))

    def test_split_at_gaps(self):
        pts = [(0, 1), (0.25, 1), (0.5, 1), (5.0, 2), (5.25, 2)]
        self.assertEqual([len(s) for s in split_at_gaps(pts, 1.0)], [3, 2])

    def test_dominant_series(self):
        self.assertEqual(dominant_series({"init": 513, "seed1": 90, "seed2": 80, "mig": 20}), ["init"])
        self.assertEqual(dominant_series({"suri": 300, "vec": 290, "a": 12, "b": 5, "c": 1}), ["suri", "vec"])
        self.assertEqual(dominant_series({"a": 50, "b": 40, "c": 30}), [])
        self.assertEqual(dominant_series({"a": 50, "b": 0}), [])


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
