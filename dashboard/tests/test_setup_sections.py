"""Setup coverage: every setup step is in the first-run wizard AND under
Settings (same widgets, ui/setup_sections.py), the edge policy reaches a
fresh edge on its own, and the export bundle carries the deployment
choices. Only dummy values; nothing is written outside pfwtest_ temp dirs
(state.save and the policy path are patched)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from core import edge_policy, honeypot_layer  # noqa: E402
from core.env_file import EnvFile  # noqa: E402
from core.paths import EDGE_ENV_EXAMPLE  # noqa: E402
from core.state import AppState  # noqa: E402

_app = QApplication.instance() or QApplication([])


class _TmpPolicy:
    """Points EdgePolicySettings at a temp file for the duration."""

    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory(prefix="pfwtest_setup_")
        self.path = Path(self.dir.name) / "edge_policy.json"
        orig = edge_policy.EdgePolicySettings.load.__func__
        self.patches = [
            mock.patch.object(edge_policy.EdgePolicySettings, "load",
                              classmethod(lambda cls, path=self.path: orig(cls, path))),
            mock.patch.object(edge_policy, "POLICY_PATH", self.path),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()
        self.dir.cleanup()


def _state() -> AppState:
    state = AppState()
    state.save = mock.Mock()
    return state


class WizardCoverageTests(unittest.TestCase):
    def setUp(self):
        self.layer = honeypot_layer.active().id

    def tearDown(self):
        honeypot_layer.set_active(self.layer)

    def test_every_setup_step_is_a_page_in_order(self):
        from ui import wizard
        with _TmpPolicy():
            w = wizard.SetupWizard(_state())
            self.assertEqual(tuple(w.pageIds()), tuple(sorted(wizard._STEP_ORDER)))
            self.assertEqual([label for _pid, label in wizard.visible_steps()],
                             ["Welcome", "Remote/Local", "Edge .env", "SIEM .env", "Deployment",
                              "Alerts", "Certificates", "Done"])
            self.assertIsNotNone(w.page(wizard.PAGE_EDGE_ENV).secret_tools)
            self.assertTrue(w.page(wizard.PAGE_EDGE_ENV).secret_tools.generates)
            self.assertFalse(w.page(wizard.PAGE_SIEM_ENV).secret_tools.generates)
            self.assertIsNotNone(w.page(wizard.PAGE_DEPLOYMENT).host_checks)
            self.assertTrue(w.start_stacks)   # default on
            w.page(wizard.PAGE_FINISH).start_check.setChecked(False)
            self.assertFalse(w.start_stacks)
            w.deleteLater()

    def test_finish_page_lists_what_is_unfinished(self):
        from ui import wizard
        with _TmpPolicy(), mock.patch.object(wizard, "setup_summary",
                                             return_value=["ids .env: WP_ADMIN_EMAIL is a placeholder"]):
            page = wizard.FinishPage(_state())
            page.initializePage()
            self.assertIn("WP_ADMIN_EMAIL", page.summary.text())
        with _TmpPolicy(), mock.patch.object(wizard, "setup_summary", return_value=[]):
            page.initializePage()
            self.assertIn("complete", page.summary.text())
        page.deleteLater()


class SettingsCoverageTests(unittest.TestCase):
    def test_settings_has_a_tab_for_every_wizard_step(self):
        from ui.page_settings import SettingsPage
        with _TmpPolicy():
            page = SettingsPage(_state(), lambda: None, edge_running=lambda: True)
            tabs = [page.tabs.tabText(i) for i in range(page.tabs.count())]
            for name in ("ids remote (SSH)", "siem remote (SSH)", "ids .env", "siem .env",
                         "Deployment", "Host checks", "Alerts", "Certificates"):
                self.assertIn(name, tabs)
            # The layer can't change under a running ids stack.
            self.assertFalse(page.deployment.layer_combo.isEnabled())
            page.deleteLater()


class DeploymentSectionTests(unittest.TestCase):
    def setUp(self):
        self.layer = honeypot_layer.active().id

    def tearDown(self):
        honeypot_layer.set_active(self.layer)

    def test_saves_routing_to_the_policy_file(self):
        from ui.setup_sections import DeploymentSection
        with _TmpPolicy() as tmp:
            section = DeploymentSection(_state())
            self.assertTrue(section.layer_combo.isEnabled())
            section.score_radio.setChecked(True)
            section.target_score.setValue(35)
            section.unlisted_score.setValue(7)
            section.save()
            saved = json.loads(tmp.path.read_text())
            self.assertEqual(saved["targets"], {"mode": "score", "target_score": 35})
            self.assertEqual(saved["whitelist"]["unlisted_score"], 7)
            section.direct_radio.setChecked(True)
            self.assertFalse(section.target_score.isEnabled())
            section.save()
            self.assertEqual(edge_policy.EdgePolicySettings.load().mode, "direct")
            section.deleteLater()

    def test_layer_change_updates_state_and_notifies(self):
        from ui.setup_sections import DeploymentSection
        with _TmpPolicy():
            state = _state()
            state.honeypot_layer = "reverse_proxy"
            section = DeploymentSection(state)
            seen = []
            section.layer_changed.connect(seen.append)
            section.layer_combo.setCurrentIndex(section.layer_combo.findData("database"))
            section.save()
            self.assertEqual(state.honeypot_layer, "database")
            self.assertEqual(honeypot_layer.active().id, "database")
            self.assertEqual(seen, ["database"])
            section.save()                     # no change: no second signal
            self.assertEqual(seen, ["database"])
            section.deleteLater()


class AlertsSectionTests(unittest.TestCase):
    def test_changes_save_to_state(self):
        from ui.setup_sections import AlertsSection
        state = _state()
        section = AlertsSection(state)
        section.alert_score.setValue(55)
        section.alert_webhook.setText("https://hooks.invalid/x")
        section.alert_webhook.editingFinished.emit()
        self.assertEqual(state.alert_policy["score_threshold"], 55)
        self.assertEqual(state.alert_policy["webhook_url"], "https://hooks.invalid/x")
        self.assertTrue(state.save.called)
        section.deleteLater()


class ConfirmWeakTests(unittest.TestCase):
    def setUp(self):
        from tests.test_env_secrets import strong_env_text
        from ui import setup_sections
        self.mod = setup_sections
        self.env = EnvFile.from_text(strong_env_text(), Path("/nonexistent/.env"))
        self.env.set("REDIS_PASSWORD", "short-dummy")
        self.rebuilt = 0

        def rebuild():
            self.rebuilt += 1
        self.tools = setup_sections.SecretTools(
            "edge", Path("/nonexistent/.env"), EDGE_ENV_EXAMPLE, lambda: self.env,
            lambda: None, rebuild, lambda: None)

    def tearDown(self):
        self.tools.deleteLater()

    def _answer(self, button):
        box = mock.patch.object(self.mod, "QMessageBox")
        m = box.start()
        self.addCleanup(box.stop)
        m.StandardButton = QMessageBox.StandardButton
        m.question.return_value = button
        return m

    def test_cancel_stays_on_the_page(self):
        self._answer(QMessageBox.StandardButton.Cancel)
        self.assertFalse(self.tools.confirm_weak())
        self.assertEqual(self.env.get("REDIS_PASSWORD"), "short-dummy")

    def test_no_continues_unchanged(self):
        self._answer(QMessageBox.StandardButton.No)
        self.assertTrue(self.tools.confirm_weak())
        self.assertEqual(self.env.get("REDIS_PASSWORD"), "short-dummy")

    def test_yes_generates_then_continues(self):
        self._answer(QMessageBox.StandardButton.Yes)
        self.assertTrue(self.tools.confirm_weak())
        self.assertTrue(len(self.env.get("REDIS_PASSWORD")) == 64, "REDIS_PASSWORD not regenerated")
        self.assertEqual(self.rebuilt, 1)

    def test_strong_file_asks_nothing(self):
        self.env.set("REDIS_PASSWORD", "b" * 64)
        m = self._answer(QMessageBox.StandardButton.Cancel)
        self.assertTrue(self.tools.confirm_weak())
        m.question.assert_not_called()


class SummaryTests(unittest.TestCase):
    def test_reports_env_warnings_by_key_only(self):
        from tests.test_env_secrets import strong_env_text
        from ui import setup_sections
        env = EnvFile.from_text(strong_env_text(), Path("/nonexistent/.env"))
        env.set("REDIS_PASSWORD", "tiny-dummy")
        with mock.patch("core.env_upload.load_project_env", return_value=env):
            out = "\n".join(setup_sections.setup_summary(_state()))
        self.assertIn("REDIS_PASSWORD", out)
        self.assertNotIn("tiny-dummy", out)


class SeedPolicyTests(unittest.TestCase):
    def setUp(self):
        from core import redis_inspect
        from ui import edge_policy_bar
        self.ri = redis_inspect
        self.seed = edge_policy_bar.seed_if_missing

    def test_existing_policy_is_left_alone(self):
        with mock.patch.object(self.ri, "get_edge_policy", return_value="{}"), \
                mock.patch.object(self.ri, "set_edge_policy") as set_:
            self.assertFalse(self.seed(None, lambda: "{\"x\":1}", sleep=lambda _s: None))
        set_.assert_not_called()

    def test_missing_policy_is_applied_after_redis_comes_up(self):
        err = self.ri.RedisInspectError("not up yet")
        with mock.patch.object(self.ri, "get_edge_policy", side_effect=[err, err, None]), \
                mock.patch.object(self.ri, "set_edge_policy") as set_:
            self.assertTrue(self.seed(None, lambda: "{\"x\":1}", sleep=lambda _s: None))
        set_.assert_called_once_with(None, "{\"x\":1}")

    def test_gives_up_with_the_last_error(self):
        err = self.ri.RedisInspectError("down")
        with mock.patch.object(self.ri, "get_edge_policy", side_effect=err):
            with self.assertRaises(self.ri.RedisInspectError):
                self.seed(None, lambda: "{}", attempts=3, sleep=lambda _s: None)

    def test_edge_up_triggers_the_seed(self):
        from core.docker_ctl import Target
        from ui import page_services
        panel = page_services.TargetPanel(Target(project="edge"))
        with mock.patch.object(panel, "_seed_edge_policy") as seed, \
                mock.patch.object(panel, "_remove_finished_containers"), \
                mock.patch.object(panel, "_run"):
            panel._mutating_action, panel._last_mutating_args = True, ("up", "-d")
            panel._on_log_finished(0)
            seed.assert_called_once()
            panel._mutating_action, panel._last_mutating_args = True, ("down",)
            panel._on_log_finished(0)
            seed.assert_called_once()
        panel.log_panel.stop()
        panel.deleteLater()


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.layer = honeypot_layer.active().id

    def tearDown(self):
        honeypot_layer.set_active(self.layer)

    def test_deployment_choices_round_trip(self):
        from core import settings_bundle
        with _TmpPolicy() as tmp:
            settings = edge_policy.EdgePolicySettings.load()
            settings.mode, settings.unlisted_score = "score", 9
            settings.save()
            state = _state()
            state.honeypot_layer = "database"
            state.alert_policy = {"enabled": True, "score_threshold": 42}
            bundle = settings_bundle.export_bundle(state)
            for key in ("edge_env", "siem_env"):   # never touch the real .env files
                bundle.pop(key)
            tmp.path.unlink()

            fresh = _state()
            settings_bundle.apply_bundle(bundle, fresh)
            self.assertEqual(fresh.honeypot_layer, "database")
            self.assertEqual(fresh.alert_policy["score_threshold"], 42)
            loaded = edge_policy.EdgePolicySettings.load()
            self.assertEqual((loaded.mode, loaded.unlisted_score), ("score", 9))

    def test_old_bundle_without_the_sections_still_imports(self):
        from core import settings_bundle
        with _TmpPolicy() as tmp:
            fresh = _state()
            notes = settings_bundle.apply_bundle({"dashboard_export_version": 1}, fresh)
            self.assertEqual(fresh.honeypot_layer, "reverse_proxy")
            self.assertFalse(tmp.path.exists())
            self.assertTrue(notes)


if __name__ == "__main__":
    unittest.main()
