"""Unit tests for core.report_progress (Qt-free)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import report_progress as rp  # noqa: E402


class StageMappingTests(unittest.TestCase):
    def test_boundaries_select_expected_stage(self):
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(0.0)].key, "decay")
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(0.19)].key, "decay")
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(0.20)].key, "restore")
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(0.27)].key, "restore")
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(0.28)].key, "patterns")
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(0.87)].key, "patterns")
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(0.88)].key, "increase")
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(0.98)].key, "increase")
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(0.99)].key, "finalize")
        self.assertEqual(rp.STAGES[rp.stage_index_for_fraction(1.0)].key, "finalize")

    def test_clamps_out_of_range(self):
        self.assertEqual(rp.stage_index_for_fraction(-1.0), 0)
        self.assertEqual(rp.stage_index_for_fraction(2.0), len(rp.STAGES) - 1)

    def test_stage_fraction_spans_slice(self):
        patterns = next(i for i, s in enumerate(rp.STAGES) if s.key == "patterns")
        self.assertAlmostEqual(rp.stage_fraction(0.28, patterns), 0.0, places=6)
        self.assertAlmostEqual(rp.stage_fraction(0.58, patterns), 0.5, places=6)
        self.assertAlmostEqual(rp.stage_fraction(0.88, patterns), 1.0, places=6)

    def test_stage_fraction_clamps(self):
        self.assertEqual(rp.stage_fraction(0.0, 2), 0.0)   # before this stage
        self.assertEqual(rp.stage_fraction(1.0, 2), 1.0)   # after it


if __name__ == "__main__":
    unittest.main()
