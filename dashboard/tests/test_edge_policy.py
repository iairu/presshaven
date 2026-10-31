import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import edge_policy as ep  # noqa: E402
from core.pattern_registry import PatternRegistry, load_catalog  # noqa: E402


class NormalisePathTests(unittest.TestCase):
    def test_canonical_form(self):
        self.assertEqual(ep.normalise_path("/Shop/"), "/shop/")
        self.assertEqual(ep.normalise_path("//wp%2Dlogin.php"), "/wp-login.php")
        self.assertEqual(ep.normalise_path("/a/./b/../c"), "/a/c")
        self.assertEqual(ep.normalise_path("/"), "/")

    def test_rejects_unmatchable_paths(self):
        for bad in ("shop/", "/a?b=1", "/a#x", "/a b", "/../etc", "/" + "a" * 600):
            with self.assertRaises(ValueError, msg=bad):
                ep.normalise_path(bad)


class WhitelistSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "edge_policy.json"

    def test_defaults(self):
        s = ep.EdgePolicySettings.load(self.tmp)
        self.assertEqual((s.mode, s.target_score, s.unlisted_score), ("direct", 40, 10))
        by_id = {e.id: e for e in s.whitelist_entries()}
        self.assertTrue(by_id["home"].enabled)
        self.assertFalse(by_id["xmlrpc"].enabled)
        self.assertIn("page-about", by_id)  # seeded shop page
        self.assertNotIn("page-home", by_id)  # the front page is "/"

    def test_target_plugin_dirs_are_not_whitelisted(self):
        paths = [e.path for e in ep.default_whitelist()]
        for plugin_dir in set(ep.plugin_dirs_by_cve().values()):
            self.assertFalse(any(p.startswith(f"/wp-content/plugins/{plugin_dir}/") for p in paths))

    def test_toggle_records_only_deviations(self):
        s = ep.EdgePolicySettings.load(self.tmp)
        s.set_whitelist_enabled("home", False)
        s.set_whitelist_enabled("xmlrpc", False)  # already the default
        self.assertEqual(s.whitelist_overrides, {"home": False})
        s.set_whitelist_enabled("home", True)
        self.assertEqual(s.whitelist_overrides, {})

    def test_custom_entries_round_trip(self):
        s = ep.EdgePolicySettings.load(self.tmp)
        s.mode, s.target_score, s.unlisted_score = "score", 25, 0
        rec = s.add_custom("/Wishlist/", "prefix", "Wishlist")
        s.save()
        again = ep.EdgePolicySettings.load(self.tmp)
        self.assertEqual((again.mode, again.target_score, again.unlisted_score), ("score", 25, 0))
        custom = [e for e in again.whitelist_entries() if e.custom]
        self.assertEqual([(c.id, c.path, c.match) for c in custom], [(rec["id"], "/wishlist/", "prefix")])
        self.assertTrue(again.remove_custom(rec["id"]))
        self.assertEqual([e for e in again.whitelist_entries() if e.custom], [])

    def test_duplicate_and_bad_custom_rejected(self):
        s = ep.EdgePolicySettings.load(self.tmp)
        with self.assertRaises(ValueError):
            s.add_custom("/shop/", "prefix")
        with self.assertRaises(ValueError):
            s.add_custom("/x", "regex")

    def test_unparseable_file_gives_defaults(self):
        self.tmp.write_text("{nope", encoding="utf-8")
        self.assertEqual(ep.EdgePolicySettings.load(self.tmp).mode, "direct")
        self.tmp.write_text(json.dumps({"targets": {"mode": "yolo", "target_score": 900}}), encoding="utf-8")
        s = ep.EdgePolicySettings.load(self.tmp)
        self.assertEqual((s.mode, s.target_score), ("direct", 100))


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.registry = PatternRegistry(path=Path(tempfile.mkdtemp()) / "registry.json")

    def targets(self):
        return ep.honeypot_targets(load_catalog(self.registry))

    def enable_all(self):
        for t in self.targets():
            self.registry.set_enabled(t.pattern_id, True, default=False)

    def test_every_target_starts_disabled(self):
        targets = self.targets()
        self.assertTrue(targets)
        self.assertFalse(any(t.enabled for t in targets))
        payload = ep.build_payload(ep.EdgePolicySettings(path=Path(tempfile.mkdtemp()) / "p.json"), targets)
        self.assertEqual(payload["targets"]["disabled_cves"], sorted(t.cve for t in targets))

    def test_every_cve_pattern_is_a_target(self):
        targets = self.targets()
        self.assertEqual(len(targets), load_catalog(self.registry).counts["cves"])
        by_cve = {t.cve: t for t in targets}
        # catalogue says woocommerce-abandoned-cart; the edge matches the init.lua dir
        self.assertEqual(by_cve["CVE-2023-2986"].plugin_dir, "abandoned-cart-lite")
        self.assertFalse(by_cve["CVE-2017-1001000"].edge_enforced)
        self.assertTrue(by_cve["CVE-2024-25600"].edge_enforced)

    def test_plugin_dir_disabled_only_when_all_its_cves_are(self):
        self.enable_all()
        self.registry.set_enabled("cve-2024-8425", False, default=False)
        self.assertEqual(ep.disabled_plugin_dirs(self.targets()), [])
        self.registry.set_enabled("cve-2025-47577", False, default=False)
        self.assertEqual(ep.disabled_plugin_dirs(self.targets()), ["gift-voucher"])

    def test_payload(self):
        self.enable_all()
        self.registry.set_enabled("cve-2024-25600", False, default=False)
        settings = ep.EdgePolicySettings(path=Path(tempfile.mkdtemp()) / "p.json")
        settings.set_whitelist_enabled("home", False)
        payload = ep.build_payload(settings, self.targets())
        self.assertEqual(payload["targets"]["disabled_cves"], ["CVE-2024-25600"])
        self.assertEqual(payload["targets"]["disabled_plugins"], ["bricks"])
        self.assertEqual(payload["targets"]["mode"], "direct")
        ids = [e["id"] for e in payload["whitelist"]["entries"]]
        self.assertNotIn("home", ids)
        self.assertNotIn("xmlrpc", ids)
        self.assertIn("shop", ids)
        self.assertEqual(json.loads(ep.encode_payload(payload)), payload)


if __name__ == "__main__":
    unittest.main()
