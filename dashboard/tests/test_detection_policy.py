"""Unit tests for core.detection_policy (Qt-free)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

DASH = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASH))

from core import detection_policy as dp  # noqa: E402
from core.env_file import EnvFile  # noqa: E402


def _env(text="THREAT_DECAY_ENABLED=true\n# keep me\nSCORE_DECAY_HALF_LIFE_SECONDS=300\nOTHER=1\n"):
    return EnvFile.from_text(text, Path("/nonexistent/.env"))


class ValueTests(unittest.TestCase):
    def test_normalise(self):
        bool_knob = dp.KNOB_BY_KEY["THREAT_DECAY_ENABLED"]
        self.assertEqual(dp.normalise(bool_knob, ' "TRUE" '), "true")
        self.assertEqual(dp.normalise(bool_knob, "off"), "false")
        self.assertIsNone(dp.normalise(bool_knob, "maybe"))
        int_knob = dp.KNOB_BY_KEY["IP_REPUTATION_CAP"]
        self.assertEqual(dp.normalise(int_knob, "25"), "25")
        self.assertIsNone(dp.normalise(int_knob, "101"))
        self.assertIsNone(dp.normalise(int_knob, "abc"))

    def test_read_values_defaults_and_bad_values(self):
        vals = dp.read_values(_env("SCORE_DECAY_HALF_LIFE_SECONDS=banana\nIP_REPUTATION_CAP=30\n"))
        self.assertEqual(vals["SCORE_DECAY_HALF_LIFE_SECONDS"], "300")   # falls back to default
        self.assertEqual(vals["IP_REPUTATION_CAP"], "30")
        self.assertEqual(vals["THREAT_DECAY_ENABLED"], "true")

    def test_validate(self):
        errs = dp.validate({"SHARED_IP_SESSIONS": "0", "NOPE": "1", "SHARED_IP_WINDOW": "120"})
        self.assertEqual(set(errs), {"SHARED_IP_SESSIONS", "NOPE"})


class ApplyTests(unittest.TestCase):
    def test_apply_changes_only_what_differs_and_keeps_comments(self):
        env = _env()
        diff = dp.apply_to(env, {"SCORE_DECAY_HALF_LIFE_SECONDS": "600", "THREAT_DECAY_ENABLED": "TRUE"})
        self.assertEqual(diff, {"SCORE_DECAY_HALF_LIFE_SECONDS": "600"})
        text = env.render()
        self.assertIn("SCORE_DECAY_HALF_LIFE_SECONDS=600", text)
        self.assertIn("# keep me", text)
        self.assertIn("OTHER=1", text)

    def test_apply_invalid_raises_and_changes_nothing(self):
        env = _env()
        before = env.render()
        with self.assertRaises(ValueError):
            dp.apply_to(env, {"SCORE_DECAY_HALF_LIFE_SECONDS": "1"})
        self.assertEqual(env.render(), before)

    def test_adds_a_key_missing_from_the_file(self):
        env = _env("OTHER=1\n")
        dp.apply_to(env, {"IP_REPUTATION_CAP": "20"})
        self.assertEqual(env.get("IP_REPUTATION_CAP"), "20")

    def test_real_template_has_every_knob(self):
        env = EnvFile.load(DASH.parent / "ids" / ".env.example")
        for knob in dp.KNOBS:
            self.assertIn(knob.key, env.keys(), knob.key)
            self.assertIsNotNone(dp.normalise(knob, env.get(knob.key)), knob.key)


class DecayTests(unittest.TestCase):
    def test_half_life_math(self):
        self.assertAlmostEqual(dp.decayed(100, 300, 300), 50)
        self.assertAlmostEqual(dp.seconds_to_fall_below(300), 300 * 0.32193, places=2)
        self.assertEqual(dp.seconds_to_fall_below(300, peak=70), 0.0)

    def test_summary(self):
        self.assertIn("never falls", dp.decay_summary(False, 300))
        self.assertIn("300s half-life", dp.decay_summary(True, 300))


if __name__ == "__main__":
    unittest.main()
