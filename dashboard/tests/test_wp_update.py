"""Unit tests for core.wp_update (Qt-free)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import wp_update  # noqa: E402


class _FakeTarget:
    """Records the compose args wp_update's builders forward to Target.build."""

    def __init__(self):
        self.calls: list[tuple] = []

    def build(self, *compose_args):
        self.calls.append(compose_args)
        return (["docker", "compose", *compose_args], "/edge")


class ParseCheckTests(unittest.TestCase):
    def test_parses_both_updates_available(self):
        out = (
            '{"ok":true,'
            '"wordpress":{"installed":"6.8.3","latest":"6.9.0","update_available":true},'
            '"woocommerce":{"installed":"10.2.2","latest":"10.3.0","update_available":true},'
            '"errors":""}'
        )
        r = wp_update.parse_check(out)
        self.assertTrue(r.ok)
        self.assertTrue(r.any_update_available)
        self.assertEqual(r.wordpress.installed, "6.8.3")
        self.assertEqual(r.wordpress.latest, "6.9.0")
        self.assertTrue(r.wordpress.update_available)
        self.assertEqual(r.woocommerce.latest, "10.3.0")
        self.assertEqual(r.errors, ())
        self.assertEqual([c.name for c in r.components], ["WordPress", "WooCommerce"])

    def test_up_to_date(self):
        out = (
            '{"ok":true,'
            '"wordpress":{"installed":"6.8.3","latest":"6.8.3","update_available":false},'
            '"woocommerce":{"installed":"10.2.2","latest":"10.2.2","update_available":false},'
            '"errors":""}'
        )
        r = wp_update.parse_check(out)
        self.assertTrue(r.ok)
        self.assertFalse(r.any_update_available)

    def test_only_woocommerce_update(self):
        out = (
            '{"ok":true,'
            '"wordpress":{"installed":"6.8.3","latest":"6.8.3","update_available":false},'
            '"woocommerce":{"installed":"10.2.2","latest":"10.3.0","update_available":true},'
            '"errors":""}'
        )
        r = wp_update.parse_check(out)
        self.assertTrue(r.any_update_available)
        self.assertFalse(r.wordpress.update_available)
        self.assertTrue(r.woocommerce.update_available)

    def test_not_ok_carries_error(self):
        r = wp_update.parse_check('{"ok":false,"error":"wordpress-not-installed"}')
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "wordpress-not-installed")
        self.assertFalse(r.any_update_available)

    def test_errors_field_split_on_semicolons(self):
        out = (
            '{"ok":true,'
            '"wordpress":{"installed":"6.8.3","latest":"6.8.3","update_available":false},'
            '"woocommerce":{"installed":"","latest":"","update_available":false},'
            '"errors":"could-not-read-core-version;woocommerce-not-found"}'
        )
        r = wp_update.parse_check(out)
        self.assertEqual(
            r.errors, ("could-not-read-core-version", "woocommerce-not-found"))

    def test_latest_defaults_to_installed_when_missing(self):
        out = '{"ok":true,"wordpress":{"installed":"6.8.3"},"woocommerce":{"installed":"10.2.2"},"errors":""}'
        r = wp_update.parse_check(out)
        self.assertEqual(r.wordpress.latest, "6.8.3")
        self.assertFalse(r.wordpress.update_available)

    def test_json_extracted_from_noisy_stdout(self):
        out = "some banner line\n{\"ok\":true,\"wordpress\":{\"installed\":\"6.8.3\",\"latest\":\"6.8.3\",\"update_available\":false},\"woocommerce\":{\"installed\":\"10.2.2\",\"latest\":\"10.2.2\",\"update_available\":false},\"errors\":\"\"}\n"
        r = wp_update.parse_check(out)
        self.assertTrue(r.ok)

    def test_empty_output_raises(self):
        with self.assertRaises(ValueError):
            wp_update.parse_check("   ")

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            wp_update.parse_check("not json at all\njust logs")


class ArgvBuilderTests(unittest.TestCase):
    def test_check_argv_defaults_to_production(self):
        t = _FakeTarget()
        argv, cwd = wp_update.check_argv(t)
        self.assertEqual(cwd, "/edge")
        self.assertEqual(
            t.calls[0],
            ("run", "--rm", "--no-deps", "production_db_seed", "sh",
             "/update_wordpress.sh", "--check"),
        )

    def test_check_argv_for_a_pool_service(self):
        t = _FakeTarget()
        wp_update.check_argv(t, wp_update.pool_seed_service(2))
        self.assertEqual(
            t.calls[0],
            ("run", "--rm", "--no-deps", "honeypot_db_seed_2", "sh",
             "/update_wordpress.sh", "--check"),
        )

    def test_apply_production_argv(self):
        t = _FakeTarget()
        wp_update.apply_production_argv(t)
        self.assertEqual(
            t.calls[0],
            ("run", "--rm", "--no-deps", "production_db_seed", "sh",
             "/update_wordpress.sh", "--apply"),
        )

    def test_resync_files_argv_runs_init_setup(self):
        t = _FakeTarget()
        wp_update.resync_files_argv(t)
        self.assertEqual(t.calls[0], ("run", "--rm", "--no-deps", "init_setup"))

    def test_pool_db_update_argv(self):
        t = _FakeTarget()
        wp_update.pool_db_update_argv(t, 3)
        self.assertEqual(
            t.calls[0],
            ("run", "--rm", "--no-deps", "honeypot_db_seed_3", "sh",
             "/update_wordpress.sh", "--apply-db-only"),
        )

    def test_pool_seed_service_name(self):
        self.assertEqual(wp_update.pool_seed_service(1), "honeypot_db_seed_1")


class PlanTests(unittest.TestCase):
    def test_updatable_pools_are_the_static_pools(self):
        self.assertEqual(wp_update.updatable_pools(), [1, 2, 3])

    def test_update_steps_bookended_by_maintenance(self):
        steps = wp_update.update_steps()
        keys = [s.key for s in steps]
        self.assertEqual(keys[0], "maintenance_on")
        self.assertEqual(keys[-1], "maintenance_off")
        self.assertIn("production", keys)
        self.assertIn("resync", keys)
        # one migrate step per static pool
        self.assertEqual([k for k in keys if k.startswith("pool_")],
                         ["pool_1", "pool_2", "pool_3"])

    def test_update_steps_respects_given_pools(self):
        steps = wp_update.update_steps([1])
        self.assertEqual([k for k in [s.key for s in steps] if k.startswith("pool_")], ["pool_1"])

    def test_production_step_is_weightiest(self):
        steps = {s.key: s for s in wp_update.update_steps()}
        self.assertGreater(steps["production"].weight, steps["pool_1"].weight)


class PolicyConstantTests(unittest.TestCase):
    def test_ttl_is_a_safe_cap(self):
        self.assertGreaterEqual(wp_update.MAINTENANCE_TTL, 300)
        self.assertGreater(wp_update.MAINTENANCE_GRACE_S, 5)  # above the 5s mirror interval

    def test_copy_mentions_downtime_and_pool_limitation(self):
        self.assertIn("maintenance", wp_update.DOWNTIME_NOTICE.lower())
        self.assertIn("dynamic pools", wp_update.POOL_LIMITATION.lower())
        self.assertTrue(wp_update.WHAT_UPDATES)


if __name__ == "__main__":
    unittest.main()
