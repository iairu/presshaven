"""Tests for core/host_settings.py -- host kernel settings the stacks need.

    cd dashboard && python3 -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import host_settings as hs  # noqa: E402


class HostSettingsTests(unittest.TestCase):
    def test_parse_and_problems_per_project(self):
        v = hs.parse_values("vm.overcommit_memory=0\nvm.max_map_count=65530\nnoise\n")
        self.assertEqual(v, {"vm.overcommit_memory": 0, "vm.max_map_count": 65530})
        self.assertEqual([p.setting.key for p in hs.problems("edge", v)], ["vm.overcommit_memory"])
        self.assertEqual([p.setting.key for p in hs.problems("siem", v)], ["vm.max_map_count"])
        ok = {"vm.overcommit_memory": 1, "vm.max_map_count": 1048576}
        self.assertEqual(hs.problems("edge", ok) + hs.problems("siem", ok), [])

    def test_unreadable_value_is_a_problem(self):
        v = hs.parse_values("vm.overcommit_memory=\nvm.max_map_count=262144\n")
        (p,) = hs.problems("edge", v)
        self.assertIsNone(p.value)
        self.assertIn("unreadable", p.text())

    def test_read_command_runs_in_a_plain_shell(self):
        out = subprocess.run(["sh", "-c", hs.read_command()], capture_output=True, text=True).stdout
        self.assertEqual(set(hs.parse_values(out)), {s.key for s in hs.SETTINGS})

    def test_fix_commands_set_now_and_persist(self):
        found = hs.problems("edge", {"vm.overcommit_memory": 0})
        cmds = hs.fix_commands(found)
        self.assertIn("sudo sysctl -w vm.overcommit_memory=1", cmds)
        self.assertIn(hs.SYSCTL_FILE, cmds)
        persisted = subprocess.run(["sh", "-c", cmds.splitlines()[-1].split(" | ")[0]],
                                   capture_output=True, text=True).stdout
        self.assertEqual(persisted, "vm.overcommit_memory = 1\n")
        self.assertEqual(hs.fix_commands([]), "")


if __name__ == "__main__":
    unittest.main()
