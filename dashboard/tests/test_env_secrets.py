"""Dashboard side of the secret-hygiene workflow: bulk generation, backup /
restore, placeholder warnings, Redeploy and the scenario runner. Only dummy
values are used, and secret values are compared, never printed."""
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from core import env_secrets  # noqa: E402
from core.docker_ctl import RUNTIME_POOL_LABEL, Target  # noqa: E402
from core.env_file import EnvFile  # noqa: E402
from core.paths import EDGE_ENV_EXAMPLE  # noqa: E402

STRONG = "a" * 40


def env_from(text: str, path: Path = Path("/nonexistent/.env")) -> EnvFile:
    return EnvFile.from_text(text, path)


def strong_env_text() -> str:
    gen = env_secrets._generator()
    lines = [f"{k}={chr(97 + i % 26) * 10}{i:030d}" for i, k in enumerate(gen.HEX32)]
    lines += [f"{k}=Strong{i}PasswordValue1234" for i, k in enumerate(gen.ADMIN)]
    lines += ["GDPR_PRIVATE_KEY=" + "M" * 1200, "WP_ADMIN_EMAIL=ops@shop.test",
              "ELK_ENABLED=false"]
    return "\n".join(lines) + "\n"


class SecretPlanTests(unittest.TestCase):
    def test_example_file_is_all_weak(self):
        example = EnvFile.load(EDGE_ENV_EXAMPLE)
        with mock.patch.object(env_secrets._generator(), "gdpr_key", return_value="K" * 1600):
            plan = env_secrets.secret_plan(example, EDGE_ENV_EXAMPLE)
        for key in ("MYSQL_PASSWORD", "MYSQL_PASSWORD_POOL_1", "HONEYPOT_DB_PASSWORD",
                    "INTERNAL_TEST_SECRET", "REDIS_PASSWORD", "WORDPRESS_AUTH_KEY",
                    "GDPR_PRIVATE_KEY"):
            self.assertIn(key, plan)
            self.assertTrue(plan[key] and plan[key] != example.get(key), f"{key} not replaced")
        values = [v for v in plan.values() if v]
        self.assertTrue(len(values) == len(set(values)), "two generated secrets share a value")

    def test_strong_file_needs_nothing(self):
        env = env_from(strong_env_text())
        self.assertEqual(env_secrets.weak_secrets(env, EDGE_ENV_EXAMPLE), [])
        self.assertEqual(env_secrets.secret_plan(env, EDGE_ENV_EXAMPLE), {})

    def test_weak_names_match_the_plan(self):
        env = env_from(strong_env_text())
        env.set("REDIS_PASSWORD", "short")
        env.set("ABUSEIPDB_API_KEY", "your_abuseipdb_api_key")
        self.assertEqual(env_secrets.weak_secrets(env, EDGE_ENV_EXAMPLE),
                         ["REDIS_PASSWORD", "ABUSEIPDB_API_KEY"])
        plan = env_secrets.secret_plan(env, EDGE_ENV_EXAMPLE)
        self.assertEqual(sorted(plan), ["ABUSEIPDB_API_KEY", "REDIS_PASSWORD"])
        self.assertEqual(plan["ABUSEIPDB_API_KEY"], "")


class WarningTests(unittest.TestCase):
    def test_clean_file_has_no_warnings(self):
        self.assertEqual(env_secrets.config_warnings(env_from(strong_env_text()), EDGE_ENV_EXAMPLE), [])

    def test_elk_with_placeholder_hosts(self):
        env = env_from(strong_env_text())
        env.set("ELK_ENABLED", "true")
        env.set("VECTOR_HOST", "your-siem-vm.example.com")
        env.set("ELASTICSEARCH_HOST", "your-siem-vm.example.com")
        text = "\n".join(env_secrets.config_warnings(env, EDGE_ENV_EXAMPLE))
        self.assertIn("VECTOR_HOST", text)
        self.assertIn("ELASTICSEARCH_HOST", text)
        env.set("VECTOR_HOST", "siem.internal")
        env.set("ELASTICSEARCH_HOST", "siem.internal")
        self.assertEqual(env_secrets.config_warnings(env, EDGE_ENV_EXAMPLE), [])

    def test_placeholder_admin_email(self):
        env = env_from(strong_env_text())
        env.set("WP_ADMIN_EMAIL", "admin@example.com")
        warnings = env_secrets.config_warnings(env, EDGE_ENV_EXAMPLE)
        self.assertEqual(len(warnings), 1)
        self.assertIn("WP_ADMIN_EMAIL", warnings[0])

    def test_warnings_never_contain_values(self):
        env = env_from(strong_env_text())
        env.set("REDIS_PASSWORD", "tiny-dummy")
        self.assertNotIn("tiny-dummy", "\n".join(env_secrets.config_warnings(env, EDGE_ENV_EXAMPLE)))


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="pfwtest_env_"))
        self.env = self.dir / ".env"
        self.env.write_text("A=current\n")

    def tearDown(self):
        for p in self.dir.iterdir():
            p.unlink()
        self.dir.rmdir()

    def test_backup_is_private(self):
        b = env_secrets.backup(self.env)
        self.assertTrue(b.name.startswith(".env.bak."))
        self.assertEqual(stat.S_IMODE(b.stat().st_mode), 0o600)
        self.assertEqual(env_secrets.list_backups(self.env), [b])

    def test_restore_keeps_the_replaced_file(self):
        old = self.dir / ".env.bak.20260101000000"
        old.write_text("A=old\n")
        with mock.patch("time.strftime", return_value="20990101000000"):
            previous = env_secrets.restore(self.env, old)
        self.assertEqual(self.env.read_text(), "A=old\n")
        self.assertEqual(previous.read_text(), "A=current\n")
        self.assertEqual(stat.S_IMODE(self.env.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in env_secrets.list_backups(self.env)],
                         [previous.name, old.name])

    def test_restore_refuses_other_files(self):
        stray = self.dir / "notes.txt"
        stray.write_text("x")
        with self.assertRaises(ValueError):
            env_secrets.restore(self.env, stray)
        self.assertEqual(self.env.read_text(), "A=current\n")


class RedeployTests(unittest.TestCase):
    def test_edge_replaces_runtime_pools_then_recreates(self):
        with mock.patch.object(Target, "siem_shipping", return_value=(True, "")):
            argv, cwd = Target(project="edge").build_redeploy()
        cmd = argv[-1]
        self.assertEqual(argv[:2], ["sh", "-c"])
        order = [cmd.index("stop pool_manager"), cmd.index(f"--filter label={RUNTIME_POOL_LABEL}"),
                 cmd.index("down --remove-orphans"), cmd.index("up -d --build --remove-orphans")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("down -v", cmd)   # data volumes are kept
        self.assertIn("&&", cmd)           # no `up` after a failed `down`

    def test_edge_scales_out_the_shipper_when_unconfigured(self):
        with mock.patch.object(Target, "siem_shipping", return_value=(False, "x")):
            cmd = Target(project="edge").build_redeploy()[0][-1]
        self.assertIn("--scale vector_outbound=0", cmd)

    def test_siem_has_no_pool_step(self):
        cmd = Target(project="siem").build_redeploy()[0][-1]
        self.assertNotIn("pool_manager", cmd)
        self.assertIn("up -d --build", cmd)


class ScenarioRunnerTests(unittest.TestCase):
    def test_argv_has_no_secret_and_only_known_scripts(self):
        from ui import scenario_runner
        scripts = scenario_runner.scenario_scripts()
        self.assertIn("scenario_01_thm_woocommerce.sh", scripts)
        argv = scenario_runner.scenario_argv(scripts[0], " 10.0.0.5 ", "")
        self.assertEqual(argv[0], "bash")
        self.assertEqual(argv[2:], ["10.0.0.5", "80"])
        self.assertFalse(any("SECRET" in a for a in argv))
        with self.assertRaises(ValueError):
            scenario_runner.scenario_argv("../../evil.sh", "h", "1")

    def test_common_lib_reads_the_secret_from_env(self):
        from ui.scenario_runner import SCENARIO_DIR
        lib = (SCENARIO_DIR / "lib" / "scenario_common.sh").read_text()
        self.assertIn("^INTERNAL_TEST_SECRET=", lib)
        self.assertIn('if [ -z "${INTERNAL_TEST_SECRET:-}" ]', lib)


class EnvTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="pfwtest_envtab_"))
        self.env = self.dir / ".env"
        ef = env_from(strong_env_text(), self.env)
        ef.set("REDIS_PASSWORD", "short-dummy")
        ef.set("WP_ADMIN_EMAIL", "admin@example.com")
        ef.save()
        from core.state import RemoteConfig
        from ui import env_source_tab
        self.mod = env_source_tab
        self.box = mock.patch.object(env_source_tab, "QMessageBox")
        self.box.start()
        self.tab = env_source_tab.EnvSourceTab("edge", self.env, EDGE_ENV_EXAMPLE, lambda: RemoteConfig())

    def tearDown(self):
        self.box.stop()
        self.tab.deleteLater()
        for p in self.dir.iterdir():
            p.unlink()
        self.dir.rmdir()

    def test_warns_then_generates_saves_and_backs_up(self):
        self.assertTrue(self.tab.warning_label.isVisibleTo(self.tab))
        self.assertIn("WP_ADMIN_EMAIL", self.tab.warning_label.text())
        before = EnvFile.load(self.env).get("REDIS_PASSWORD")
        self.tab._generate_weak_secrets()
        self.assertEqual(EnvFile.load(self.env).get("REDIS_PASSWORD"), before)  # not saved yet
        self.tab._save()
        after = EnvFile.load(self.env).get("REDIS_PASSWORD")
        self.assertTrue(after != before and len(after) == 64, "REDIS_PASSWORD not regenerated")
        self.assertEqual(stat.S_IMODE(self.env.stat().st_mode), 0o600)
        backups = env_secrets.list_backups(self.env)
        self.assertEqual(len(backups), 1)
        self.assertTrue(EnvFile.load(backups[0]).get("REDIS_PASSWORD") == before)
        self.assertNotIn("Placeholder", self.tab.warning_label.text())
        self.assertIn("WP_ADMIN_EMAIL", self.tab.warning_label.text())

    def test_siem_tab_has_no_generator(self):
        from core.state import RemoteConfig
        tab = self.mod.EnvSourceTab("siem", self.env, EDGE_ENV_EXAMPLE, lambda: RemoteConfig())
        self.assertFalse(tab.generate_btn.isVisibleTo(tab))
        self.assertFalse(tab.warning_label.isVisibleTo(tab))
        tab.deleteLater()


if __name__ == "__main__":
    unittest.main()
