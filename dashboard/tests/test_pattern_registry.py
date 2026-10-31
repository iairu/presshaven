import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.pattern_catalog import PatternCatalog  # noqa: E402
from core.pattern_registry import (  # noqa: E402
    PatternRegistry, active_presets, disabled_preset_cves, load_catalog,
    normalise_custom, slugify,
)
from core.patterns import PATTERN_PRESETS, default_enabled  # noqa: E402


class RegistryPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "registry.json"

    def test_missing_file_is_empty_registry(self):
        reg = PatternRegistry.load(self.tmp)
        self.assertEqual(reg.overrides, {})
        self.assertEqual(reg.custom, [])

    def test_disable_persists_and_reloads(self):
        reg = PatternRegistry.load(self.tmp)
        reg.set_enabled("cve-2024-25600", False)
        reg.save()
        again = PatternRegistry.load(self.tmp)
        self.assertFalse(again.is_enabled("cve-2024-25600"))
        self.assertTrue(again.is_enabled("something-else"))  # default on

    def test_enabling_again_prunes_the_override(self):
        reg = PatternRegistry.load(self.tmp)
        reg.set_enabled("cve-2024-25600", False)
        reg.set_enabled("cve-2024-25600", True)
        self.assertEqual(reg.overrides, {})  # back to default, nothing stored

    def test_override_merges_without_dropping_enabled(self):
        reg = PatternRegistry.load(self.tmp)
        reg.set_enabled("cve-2024-25600", False)
        reg.override("cve-2024-25600", {"severity": "low", "ignored_field": "x"})
        self.assertEqual(reg.overrides["cve-2024-25600"],
                         {"enabled": False, "severity": "low"})

    def test_corrupt_file_falls_back_to_empty(self):
        self.tmp.write_text("{ not json", encoding="utf-8")
        reg = PatternRegistry.load(self.tmp)
        self.assertEqual(reg.custom, [])


class CustomPatternTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("My Nasty Pattern!"), "my-nasty-pattern")
        self.assertEqual(slugify(""), "pattern")

    def test_normalise_fills_catalogue_shape(self):
        rec = normalise_custom({"name": "Weird Probe", "severity": "BOGUS"})
        self.assertEqual(rec["id"], "weird-probe")
        self.assertEqual(rec["severity"], "medium")  # bogus -> default
        self.assertTrue(rec["enabled"])
        self.assertTrue(rec["sources"])  # always has provenance
        for key in ("id", "name", "kind", "category", "severity", "surface"):
            self.assertIn(key, rec)

    def test_unique_id_assignment(self):
        reg = PatternRegistry()
        a = reg.add_custom({"name": "Dup"})
        b = reg.add_custom({"name": "Dup"})
        self.assertNotEqual(a["id"], b["id"])

    def test_remove_custom_and_revert_generated(self):
        reg = PatternRegistry()
        rec = reg.add_custom({"name": "Temp"})
        self.assertTrue(reg.remove(rec["id"]))
        self.assertFalse(reg.is_custom(rec["id"]))
        reg.set_enabled("cve-2024-25600", False)
        self.assertTrue(reg.remove("cve-2024-25600"))  # drops the override
        self.assertTrue(reg.is_enabled("cve-2024-25600"))


class EffectiveCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = PatternCatalog.load()

    def test_only_generic_and_detection_patterns_start_enabled(self):
        cat = load_catalog(PatternRegistry(), base=self.base)
        for p in cat.patterns:
            self.assertEqual(p["enabled"], p["kind"] != "cve", p["id"])
            self.assertEqual(p["default_enabled"], p["enabled"], p["id"])
        self.assertEqual(cat.counts["disabled"], cat.counts["cves"])
        self.assertTrue(cat.by_id["cmd-system"]["enabled"])
        self.assertTrue(cat.by_id["tool-acunetix"]["enabled"])
        self.assertFalse(cat.by_id["cve-2024-25600"]["enabled"])

    def test_generated_catalogue_follows_the_default_rule(self):
        # patterns.json is regenerated from default_enabled(); a stale file fails here.
        for p in self.base.patterns:
            self.assertEqual(p["enabled"], default_enabled(p["kind"]), p["id"])

    def test_disable_reflected_in_catalog_and_counts(self):
        reg = PatternRegistry()
        reg.set_enabled("cmd-system", False)
        cat = load_catalog(reg, base=self.base)
        self.assertFalse(cat.by_id["cmd-system"]["enabled"])
        self.assertTrue(cat.by_id["cmd-system"]["default_enabled"])
        self.assertEqual(cat.counts["disabled"], cat.counts["cves"] + 1)
        self.assertEqual(cat.counts["total"], len(self.base.patterns))

    def test_enabling_a_cve_is_recorded_and_disabling_it_prunes(self):
        reg = PatternRegistry()
        reg.set_enabled("cve-2024-25600", True, default=False)
        self.assertEqual(reg.overrides, {"cve-2024-25600": {"enabled": True}})
        self.assertTrue(load_catalog(reg, base=self.base).by_id["cve-2024-25600"]["enabled"])
        reg.set_enabled("cve-2024-25600", False, default=False)
        self.assertEqual(reg.overrides, {})

    def test_saved_choices_win_over_the_defaults(self):
        reg = PatternRegistry(overrides={"cve-2024-25600": {"enabled": True},
                                         "cmd-system": {"enabled": False}})
        cat = load_catalog(reg, base=self.base)
        self.assertTrue(cat.by_id["cve-2024-25600"]["enabled"])
        self.assertFalse(cat.by_id["cmd-system"]["enabled"])

    def test_reset_enabled_keeps_edits_and_custom_patterns(self):
        reg = PatternRegistry(overrides={"cve-2024-25600": {"enabled": True, "name": "Renamed"},
                                         "cve-2022-0739": {"enabled": True},
                                         "cmd-system": {"enabled": False}})
        custom = reg.add_custom({"name": "Mine", "enabled": False})
        reg.reset_enabled(["cve-2022-0739"])
        self.assertNotIn("cve-2022-0739", reg.overrides)
        self.assertIn("cmd-system", reg.overrides)
        reg.reset_enabled()
        self.assertEqual(reg.overrides, {"cve-2024-25600": {"name": "Renamed"}})
        self.assertFalse(reg.is_enabled(custom["id"]))

    def test_export_leaves_out_merge_bookkeeping(self):
        cat = load_catalog(PatternRegistry(), base=self.base)
        payload = cat.export_payload(cat.patterns[:2])
        self.assertFalse(any("default_enabled" in p for p in payload["patterns"]))

    def test_custom_pattern_appears_in_catalog(self):
        reg = PatternRegistry()
        reg.add_custom({"name": "Injected Probe", "category": "custom"})
        cat = load_catalog(reg, base=self.base)
        self.assertEqual(cat.counts["total"], len(self.base.patterns) + 1)
        self.assertIn("injected-probe", cat.by_id)
        self.assertIn("custom", cat.categories)

    def test_override_edits_name(self):
        reg = PatternRegistry()
        reg.override("cve-2024-25600", {"name": "Renamed"})
        cat = load_catalog(reg, base=self.base)
        self.assertEqual(cat.by_id["cve-2024-25600"]["name"], "Renamed")

    def test_base_catalog_is_not_mutated(self):
        reg = PatternRegistry()
        reg.override("cve-2024-25600", {"name": "Renamed"})
        load_catalog(reg, base=self.base)
        self.assertNotEqual(self.base.by_id["cve-2024-25600"]["name"], "Renamed")


class PresetFilteringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = PatternCatalog.load()

    def test_disabling_a_cve_drops_its_preset(self):
        reg = PatternRegistry()
        for p in self.base.patterns:
            if p["kind"] == "cve":
                reg.set_enabled(p["id"], True, default=False)
        reg.set_enabled("cve-2024-25600", False, default=False)
        cat = load_catalog(reg, base=self.base)
        disabled = disabled_preset_cves(catalog=cat)
        self.assertIn("CVE-2024-25600", disabled)
        kept = active_presets(PATTERN_PRESETS, catalog=cat)
        self.assertTrue(all(p.cve != "CVE-2024-25600" for p in kept))
        self.assertEqual(len(kept), len(PATTERN_PRESETS) - 1)

    def test_defaults_keep_generic_presets_and_drop_cve_ones(self):
        cat = load_catalog(PatternRegistry(), base=self.base)
        catalogued = {p["cve"] for p in cat.patterns if p["kind"] == "cve"}
        kept = active_presets(PATTERN_PRESETS, catalog=cat)
        self.assertTrue(any(p.kind == "generic" for p in kept))
        self.assertFalse(any(p.cve in catalogued for p in kept))
        self.assertEqual(len(kept), sum(1 for p in PATTERN_PRESETS if p.cve not in catalogued))


if __name__ == "__main__":
    unittest.main()
