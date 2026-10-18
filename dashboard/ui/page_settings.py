"""Connectors & Config page: edit either project's real .env file, configure remote
(SSH) control for either project, and export/import the whole
configuration as one JSON bundle. This is the "adjust existing .env"
surface -- the wizard covers first-run creation; this covers anytime
changes."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from core import alert_policy

from core.paths import (
    EDGE_ENV_EXAMPLE, EDGE_ENV_FILE, SIEM_ENV_EXAMPLE, SIEM_ENV_FILE,
)
from core.settings_bundle import BundleError, apply_bundle, export_bundle, read_bundle, write_bundle
from core.state import AppState
from ui import theme
from ui.env_source_tab import EnvSourceTab
from ui.remote_config_widget import RemoteConfigWidget


class SettingsPage(QWidget):
    def __init__(self, state: AppState, on_state_changed, on_poll_interval_changed=None,
                 on_test_alert=None, parent=None):
        super().__init__(parent)
        self.state = state
        self._on_state_changed = on_state_changed
        self._on_poll_interval_changed = on_poll_interval_changed
        self._on_test_alert = on_test_alert

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_tabs()

    def _build_tabs(self) -> None:
        """(Re)builds every tab from scratch, reading .env files fresh
        from disk. Called from __init__ and again after a successful
        Import, since the previously-displayed editors/widgets would
        otherwise keep showing pre-import values."""
        self.tabs.clear()

        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_alerts_tab(), "Alerts")

        # Each .env tab has its own Local/Remote toggle (only enabled once
        # that project's remote connection is configured) -- get_remote_config
        # is a callable, not a snapshot, so it always reflects whatever the
        # remote tabs below currently hold, including after they're saved.
        self.edge_env_tab = EnvSourceTab(
            "edge", EDGE_ENV_FILE, EDGE_ENV_EXAMPLE, lambda: self.state.remote_edge,
        )
        self.tabs.addTab(self.edge_env_tab, "ids .env")

        self.siem_env_tab = EnvSourceTab(
            "siem", SIEM_ENV_FILE, SIEM_ENV_EXAMPLE, lambda: self.state.remote_siem,
        )
        self.tabs.addTab(self.siem_env_tab, "siem .env")

        self.edge_remote_widget = RemoteConfigWidget("edge", self.state.remote_edge)
        edge_remote_tab = self._wrap_with_save(self.edge_remote_widget, self._save_edge_remote)
        self.tabs.addTab(edge_remote_tab, "ids remote (SSH)")

        self.siem_remote_widget = RemoteConfigWidget("siem", self.state.remote_siem)
        siem_remote_tab = self._wrap_with_save(self.siem_remote_widget, self._save_siem_remote)
        self.tabs.addTab(siem_remote_tab, "siem remote (SSH)")

        self.tabs.addTab(self._build_export_import_tab(), "Export / Import")

    def _build_general_tab(self) -> QWidget:
        container = QWidget()
        form = QFormLayout(container)

        self.theme_combo = QComboBox()
        for value in theme.THEMES:
            self.theme_combo.addItem(theme.THEME_LABELS[value], value)
        self.theme_combo.setCurrentIndex(max(0, theme.THEMES.index(self.state.theme)))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
        form.addRow("Theme:", self.theme_combo)

        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 300)
        self.poll_interval_spin.setSuffix(" s")
        self.poll_interval_spin.setValue(max(1, round(self.state.poll_interval_ms / 1000)))
        self.poll_interval_spin.valueChanged.connect(self._on_poll_interval_spin_changed)
        form.addRow("Status refresh interval:", self.poll_interval_spin)

        self.tray_notif_check = QCheckBox("Notify when a container becomes unhealthy")
        self.tray_notif_check.setChecked(self.state.tray_notifications_enabled)
        self.tray_notif_check.toggled.connect(self._on_tray_notif_toggled)
        form.addRow("", self.tray_notif_check)

        note = QLabel(
            "Lower the refresh interval for a snappier topology map; "
            "raise it to reduce SSH round-trips against a remote target on "
            "a slow link. Takes effect immediately, no restart needed."
        )
        note.setWordWrap(True)
        form.addRow(note)

        return container

    def _build_alerts_tab(self) -> QWidget:
        policy = alert_policy.AlertPolicy.from_dict(self.state.alert_policy)
        container = QWidget()
        form = QFormLayout(container)

        self.alert_enabled = QCheckBox("Raise alerts for security events")
        self.alert_enabled.setChecked(policy.enabled)
        form.addRow("", self.alert_enabled)

        self.alert_severity = QComboBox()
        self.alert_severity.addItem("Medium and above", "medium")
        self.alert_severity.addItem("High only", "high")
        self.alert_severity.setCurrentIndex(alert_policy.MIN_SEVERITIES.index(policy.min_severity))
        form.addRow("Minimum severity:", self.alert_severity)

        self.alert_diversion = QCheckBox("Always alert when a session is diverted to the honeypot")
        self.alert_diversion.setChecked(policy.on_diversion)
        form.addRow("", self.alert_diversion)

        self.alert_score = QSpinBox()
        self.alert_score.setRange(0, 100)
        self.alert_score.setSpecialValueText("off")
        self.alert_score.setValue(policy.score_threshold)
        form.addRow("Alert at risk score ≥:", self.alert_score)

        self.alert_cooldown = QSpinBox()
        self.alert_cooldown.setRange(0, 3600)
        self.alert_cooldown.setSuffix(" s")
        self.alert_cooldown.setValue(policy.cooldown_seconds)
        form.addRow("Repeat suppression:", self.alert_cooldown)

        self.alert_desktop = QCheckBox("Desktop notification (system tray)")
        self.alert_desktop.setChecked(policy.desktop)
        form.addRow("", self.alert_desktop)

        self.alert_webhook = QLineEdit(policy.webhook_url)
        self.alert_webhook.setPlaceholderText("https://hooks.slack.com/… or any endpoint accepting a JSON POST")
        form.addRow("Webhook URL:", self.alert_webhook)

        test_btn = QPushButton("Send test alert")
        test_btn.clicked.connect(self._send_test_alert)
        form.addRow("", test_btn)

        note = QLabel("Container-health notifications are separate (General tab). Changes apply immediately.")
        note.setWordWrap(True)
        form.addRow(note)

        for widget, signal in ((self.alert_enabled, "toggled"), (self.alert_severity, "currentIndexChanged"),
                               (self.alert_diversion, "toggled"), (self.alert_score, "valueChanged"),
                               (self.alert_cooldown, "valueChanged"), (self.alert_desktop, "toggled"),
                               (self.alert_webhook, "editingFinished")):
            getattr(widget, signal).connect(self._save_alert_policy)
        return container

    def _save_alert_policy(self, *_args) -> None:
        self.state.alert_policy = alert_policy.AlertPolicy(
            enabled=self.alert_enabled.isChecked(), min_severity=self.alert_severity.currentData(),
            on_diversion=self.alert_diversion.isChecked(), score_threshold=self.alert_score.value(),
            cooldown_seconds=self.alert_cooldown.value(), desktop=self.alert_desktop.isChecked(),
            webhook_url=self.alert_webhook.text().strip()).to_dict()
        self.state.save()

    def _send_test_alert(self) -> None:
        self._save_alert_policy()
        if self._on_test_alert:
            self._on_test_alert()
        url = self.state.alert_policy.get("webhook_url", "")
        if url:
            error = alert_policy.send_webhook(
                url, alert_policy.webhook_payload("Test alert", "from the dashboard", "high", None, 0))
            QMessageBox.information(self, "Webhook test", "Webhook delivered." if not error
                                    else f"Webhook failed: {error}")

    def _on_poll_interval_spin_changed(self, seconds: int) -> None:
        interval_ms = seconds * 1000
        if self._on_poll_interval_changed:
            self._on_poll_interval_changed(interval_ms)
        else:
            self.state.poll_interval_ms = interval_ms
            self.state.save()

    def _on_tray_notif_toggled(self, checked: bool) -> None:
        self.state.tray_notifications_enabled = checked
        self.state.save()

    def _on_theme_combo_changed(self, index: int) -> None:
        value = self.theme_combo.itemData(index)
        self.state.theme = value
        self.state.save()
        theme.apply_theme(value)

    def _wrap_with_save(self, widget: QWidget, save_fn) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.addWidget(widget, stretch=1)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(save_fn)
        v.addWidget(save_btn)
        return container

    def _save_edge_remote(self) -> None:
        self.state.remote_edge = self.edge_remote_widget.to_config()
        self.state.save()
        self._on_state_changed()
        self.edge_env_tab.refresh_remote_availability()
        QMessageBox.information(self, "Saved", "Remote settings saved for ids.")

    def _save_siem_remote(self) -> None:
        self.state.remote_siem = self.siem_remote_widget.to_config()
        self.state.save()
        self._on_state_changed()
        self.siem_env_tab.refresh_remote_availability()
        QMessageBox.information(self, "Saved", "Remote settings saved for siem.")

    # ---- Export / Import ----

    def _build_export_import_tab(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)

        info = QLabel(
            "Back up or restore both projects' .env values and remote (SSH) "
            "target settings as a single JSON file -- useful before a "
            "risky change, or to move this setup to a fresh checkout of "
            "the repo instead of re-typing everything by hand.\n\n"
            "⚠ The exported file contains real secrets in plaintext "
            "(database/Redis passwords, API keys, the remote SSH key "
            "path -- not the key file's contents, just its path). Store "
            "it securely and never commit it to version control.\n\n"
            "Import only changes keys present in the file -- other "
            "existing .env keys and all comments are left exactly as "
            "they are (same comment-preserving editor this whole app "
            "uses). Remote (SSH) settings for each project present in "
            "the file are replaced entirely."
        )
        info.setWordWrap(True)
        v.addWidget(info)

        export_btn = QPushButton("Export settings…")
        export_btn.clicked.connect(self._export_settings)
        v.addWidget(export_btn)

        import_btn = QPushButton("Import settings…")
        import_btn.clicked.connect(self._import_settings)
        v.addWidget(import_btn)

        v.addStretch()
        return container

    def _export_settings(self) -> None:
        default_name = f"honeypot-dashboard-export-{datetime.now():%Y%m%d_%H%M%S}.json"
        path_str, _ = QFileDialog.getSaveFileName(self, "Export settings", default_name, "JSON files (*.json)")
        if not path_str:
            return

        try:
            bundle = export_bundle(self.state)
            write_bundle(Path(path_str), bundle)
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return

        QMessageBox.information(
            self, "Exported",
            f"Settings exported to:\n\n{path_str}\n\n"
            "Remember: this file contains real secrets in plaintext -- "
            "store it securely.",
        )

    def _import_settings(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(self, "Import settings", "", "JSON files (*.json)")
        if not path_str:
            return

        reply = QMessageBox.warning(
            self, "Confirm import",
            "This will overwrite matching keys in both projects' real "
            ".env files and replace both remote (SSH) settings entirely "
            "with whatever is in this file.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            bundle = read_bundle(Path(path_str))
            notes = apply_bundle(bundle, self.state)
        except BundleError as e:
            QMessageBox.warning(self, "Import failed", str(e))
            return

        self._on_state_changed()
        self._build_tabs()
        QMessageBox.information(self, "Imported", "\n".join(notes))
