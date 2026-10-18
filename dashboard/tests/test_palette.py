"""Unit tests for core.palette (Qt-free)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.palette import Command, rank, score  # noqa: E402

CMDS = [
    Command("page:health", "Global Visualization", "Monitor", "Topology map of every workload"),
    Command("page:log_search", "Forensics Analysis", "Monitor", "Forensic search across raw logs"),
    Command("page:redis", "Pool State Store", "Threat Operations", "Inspect the proxy's live state"),
    Command("page:patterns", "Attack Simulation", "Threat Operations", "Replay CVE patterns"),
    Command("action:wizard", "Re-run setup wizard…", "Actions"),
]


class ScoreTests(unittest.TestCase):
    def test_ordering_of_match_kinds(self):
        self.assertEqual(score("attack", "attack"), 100)
        self.assertGreater(score("att", "Attack Simulation"), score("sim", "Attack Simulation"))
        self.assertGreater(score("sim", "Attack Simulation"), score("ack", "Attack Simulation"))
        self.assertGreater(score("ack", "Attack Simulation"), score("asm", "Attack Simulation"))
        self.assertIsNone(score("zzz", "Attack Simulation"))

    def test_empty_query_scores_zero(self):
        self.assertEqual(score("", "anything"), 0)


class RankTests(unittest.TestCase):
    def test_empty_returns_all_in_order(self):
        self.assertEqual([c.id for c in rank("", CMDS)], [c.id for c in CMDS])

    def test_title_prefix_first(self):
        self.assertEqual(rank("for", CMDS)[0].id, "page:log_search")

    def test_matches_keywords_and_group(self):
        self.assertEqual([c.id for c in rank("cve", CMDS)], ["page:patterns"])
        self.assertEqual({c.id for c in rank("threat", CMDS)}, {"page:redis", "page:patterns"})

    def test_title_beats_keyword_only(self):
        cmds = [Command("a", "Logs", "", "forensic"), Command("b", "Forensics", "", "")]
        self.assertEqual(rank("for", cmds)[0].id, "b")

    def test_fuzzy_subsequence(self):
        self.assertEqual(rank("gvz", CMDS)[0].id, "page:health")

    def test_no_match(self):
        self.assertEqual(rank("qqqq", CMDS), [])


if __name__ == "__main__":
    unittest.main()
