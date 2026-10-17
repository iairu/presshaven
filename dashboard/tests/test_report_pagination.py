"""Tests for core/report_pagination.py: page breaks in the PDF reports.

    cd dashboard && python3 -m unittest discover -s tests -v

Needs PyQt6, so it is skipped where PyQt6 isn't installed, like the Qt-free
CI job.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QSizeF
    from PyQt6.QtGui import QTextDocument
    from PyQt6.QtWidgets import QApplication
    from core import report_pagination, vector_figures
except ImportError:  # PyQt6 missing
    report_pagination = None

PAGE = 1000.0


def _figure_rect(doc):
    lay = doc.documentLayout()
    b = doc.begin()
    while b.isValid():
        if b.text().strip() == "\ufffc":
            return lay.blockBoundingRect(b)
        b = b.next()
    return None


@unittest.skipIf(report_pagination is None, "PyQt6 not installed")
class FitFiguresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _doc(self, words: int, fig_h: int) -> "QTextDocument":
        doc = QTextDocument()
        doc.setPageSize(QSizeF(600, PAGE))
        fig, p = vector_figures.new_figure(600, fig_h)
        p.end()
        vector_figures.add_figure(doc, "f://1", fig)
        doc.setHtml("<p>" + "line of text " * words + "</p><p><img src='f://1' width='600'/></p>"
                    "<p>Figure 2. A caption.</p>")
        vector_figures.embed_figures(doc)
        return doc

    def test_figure_across_the_break_is_shrunk_to_fit_the_page(self):
        doc = self._doc(300, 500)                       # text ~55% of the page, figure 50%
        self.assertEqual(report_pagination._fit_figures(doc, PAGE), 1)
        r = _figure_rect(doc)
        self.assertLess(r.bottom(), PAGE)               # now ends on the first page
        self.assertGreaterEqual(r.height(), 500 * report_pagination._MIN_FIGURE_SCALE)

    def test_figure_that_would_shrink_too_much_is_left_alone(self):
        doc = self._doc(300, 900)                       # would need well under 70%
        self.assertEqual(report_pagination._fit_figures(doc, PAGE), 0)
        self.assertEqual(round(_figure_rect(doc).height()), 900)


if __name__ == "__main__":
    unittest.main()
