"""Unit tests for core.log_query (Qt-free)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import log_query as lq  # noqa: E402


class MatcherTests(unittest.TestCase):
    def test_plain_case_insensitive_by_default(self):
        m = lq.compile_matcher("sql")
        self.assertTrue(m("an SQL injection"))
        self.assertFalse(m("nothing"))

    def test_plain_case_sensitive(self):
        self.assertFalse(lq.compile_matcher("sql", case_sensitive=True)("SQL"))
        self.assertTrue(lq.compile_matcher("SQL", case_sensitive=True)("an SQL"))

    def test_regex(self):
        m = lq.compile_matcher(r"CVE-\d{4}-\d+", regex=True)
        self.assertTrue(m("hit cve-2024-27956 here"))
        self.assertFalse(m("CVE-abc"))
        self.assertFalse(lq.compile_matcher("^a", regex=True, case_sensitive=True)("A"))

    def test_regex_chars_are_literal_in_plain_mode(self):
        self.assertTrue(lq.compile_matcher("a.b")("xa.by"))
        self.assertFalse(lq.compile_matcher("a.b")("axb"))

    def test_errors(self):
        with self.assertRaises(lq.QueryError):
            lq.compile_matcher("")
        with self.assertRaises(lq.QueryError):
            lq.compile_matcher("(unclosed", regex=True)


class SinceTests(unittest.TestCase):
    def test_since_args(self):
        self.assertEqual(lq.since_args("1h"), ["--since", "1h"])
        self.assertEqual(lq.since_args(None), [])

    def test_ranges_have_unique_labels(self):
        labels = [l for l, _ in lq.TIME_RANGES]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertIsNone(lq.TIME_RANGES[0][1])


class HistoryAndSavedTests(unittest.TestCase):
    def test_history_dedupes_and_caps(self):
        h = lq.push_history(["a", "b"], "b")
        self.assertEqual(h, ["b", "a"])
        self.assertEqual(lq.push_history(h, "  "), h)
        many = []
        for i in range(30):
            many = lq.push_history(many, f"q{i}")
        self.assertEqual((len(many), many[0]), (lq.HISTORY_LIMIT, "q29"))

    def test_save_replaces_same_name_and_delete(self):
        s = lq.save_search([], "sqli", "union select", False, False, "1h")
        s = lq.save_search(s, "xss", "<script", False, True, None)
        s = lq.save_search(s, "sqli", "union.*select", True, False, "6h")
        self.assertEqual([x["name"] for x in s], ["sqli", "xss"])
        self.assertEqual(s[0]["query"], "union.*select")
        self.assertEqual([x["name"] for x in lq.delete_search(s, "sqli")], ["xss"])
        with self.assertRaises(lq.QueryError):
            lq.save_search([], "", "q", False, False, None)


class ExportTests(unittest.TestCase):
    LINES = ["[Edge (local)] \x1b[36mproxy-1 |\x1b[0m GET /wp-admin", "plain"]

    def test_text_strips_ansi(self):
        text = lq.export_text(self.LINES)
        self.assertNotIn("\x1b", text)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(lq.export_text([]), "")

    def test_jsonl_splits_target(self):
        rows = [json.loads(l) for l in lq.export_jsonl(self.LINES).splitlines()]
        self.assertEqual(rows[0]["target"], "Edge (local)")
        self.assertIn("GET /wp-admin", rows[0]["line"])
        self.assertEqual(rows[1], {"target": "", "line": "plain"})


if __name__ == "__main__":
    unittest.main()
