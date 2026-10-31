"""Honeypot Targets page: the URLs that exist only to catch attackers.

One row per CVE pattern of the pattern registry (the catalogue's ``cve``
patterns) with the vulnerable plugin directory the honeypots ship it in. The
row checkbox is the registry's own enabled flag -- the same switch as on the
Pattern Database page -- so a disabled target stops matching at the edge AND
drops out of Attack Simulation / Segmentation Validation. A plugin directory
stops being a target once every CVE it hosts is disabled. Every target starts
disabled (core.patterns.DEFAULT_DISABLED_KINDS): CVE targets are opt-in.

The routing mode decides what a hit does:
  * auto-send -- divert to a honeypot at once, scoring bypassed;
  * score     -- add the target score and let the honeypot threshold decide.

"Apply to edge" pushes the policy (targets AND whitelist) to the selected
edge's Redis, see ui/edge_policy_bar.py."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QRadioButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import edge_policy
from core.detection_policy import HONEYPOT_THRESHOLD
from core.pattern_registry import PatternRegistry, load_catalog
from core.state import AppState
from ui import theme
from ui.common import muted_label, set_status
from ui.edge_policy_bar import EdgePolicyBar, current_document

_ROLE_ID = Qt.ItemDataRole.UserRole


class HoneypotTargetsPage(QWidget):
    # A target was enabled/disabled: the registry changed, so the pages that
    # run patterns (and the Pattern Database page) re-read it.
    registry_changed = pyqtSignal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.settings = edge_policy.EdgePolicySettings.load()
        self.registry = PatternRegistry.load()
        self.catalog = None

        layout = QVBoxLayout(self)
        self.bar = EdgePolicyBar(state, current_document)
        layout.addWidget(self.bar)
        layout.addWidget(self.bar.error_banner)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("When a request hits a target:"))
        self.direct_radio = QRadioButton("Auto-send to honeypot (scoring bypassed)")
        self.score_radio = QRadioButton("Score it first, divert at the threshold")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.direct_radio)
        self.mode_group.addButton(self.score_radio)
        mode_row.addWidget(self.direct_radio)
        mode_row.addWidget(self.score_radio)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        score_row = QHBoxLayout()
        score_row.addWidget(QLabel("Target score:"))
        self.score_spin = QSpinBox()
        self.score_spin.setRange(0, edge_policy.MAX_SCORE)
        self.score_spin.setSuffix(" pts")
        score_row.addWidget(self.score_spin)
        self.mode_hint = muted_label("")
        score_row.addWidget(self.mode_hint, stretch=1)
        layout.addLayout(score_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Target", "Name", "Severity", "Plugin path", "Edge trigger", "Sample request"])
        header = self.table.horizontalHeader()
        for col in range(5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        buttons = QHBoxLayout()
        self.enable_all_btn = QPushButton("Enable all")
        self.reset_btn = QPushButton("Reset to defaults")
        self.reset_btn.setToolTip("Every CVE target back to its default state (off until you enable it)")
        self.status = QLabel("")
        self.count_label = QLabel("")
        buttons.addWidget(self.enable_all_btn)
        buttons.addWidget(self.reset_btn)
        buttons.addWidget(self.status, stretch=1)
        buttons.addWidget(self.count_label)
        layout.addLayout(buttons)
        layout.addWidget(muted_label(
            "Targets start disabled; enable the CVEs you want caught. "
            "Enable/disable is shared with the Pattern Database page: a disabled target no longer "
            "matches at the edge and is skipped by Attack Simulation. A plugin directory stays a "
            "target while any of its CVEs is enabled."))

        self.table.itemChanged.connect(self._on_item_changed)
        self.direct_radio.toggled.connect(self._on_mode_changed)
        self.score_spin.valueChanged.connect(self._on_score_changed)
        self.enable_all_btn.clicked.connect(self._enable_all)
        self.reset_btn.clicked.connect(self._reset_defaults)

        self.reload()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reload()
        self.bar.check()

    def rebuild_targets(self) -> None:
        self.bar.rebuild_targets()

    def reload(self) -> None:
        self.settings = edge_policy.EdgePolicySettings.load()
        self.registry = PatternRegistry.load()
        for w in (self.direct_radio, self.score_spin):
            w.blockSignals(True)
        self.direct_radio.setChecked(self.settings.mode == "direct")
        self.score_radio.setChecked(self.settings.mode == "score")
        self.score_spin.setValue(self.settings.target_score)
        for w in (self.direct_radio, self.score_spin):
            w.blockSignals(False)
        self._update_mode_hint()
        self._fill()

    def _fill(self) -> None:
        try:
            self.catalog = load_catalog(self.registry)
            targets = edge_policy.honeypot_targets(self.catalog)
            self.bar.error_banner.set_error(None)
        except Exception as e:  # noqa: BLE001 -- a stale catalogue must not kill the page
            self.catalog = None
            targets = []
            self.bar.error_banner.set_error(str(e), prefix="Cannot load pattern catalogue: ")
        muted = QColor(theme.scheme_colors()["fg_muted"])
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for t in targets:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cve_item = QTableWidgetItem(t.cve)
            cve_item.setData(_ROLE_ID, t.pattern_id)
            cve_item.setFlags(cve_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            cve_item.setCheckState(Qt.CheckState.Checked if t.enabled else Qt.CheckState.Unchecked)
            plugin = f"/wp-content/plugins/{t.plugin_dir}/" if t.plugin_dir else "—"
            trigger = t.trigger if t.edge_enforced else "— (simulation preset only)"
            cells = [cve_item, QTableWidgetItem(t.name), QTableWidgetItem(t.severity.upper()),
                     QTableWidgetItem(plugin), QTableWidgetItem(trigger),
                     QTableWidgetItem(t.sample_request)]
            if not t.edge_enforced:
                cve_item.setToolTip("No edge trigger: this CVE only exists as an Attack Simulation "
                                    "preset, so the switch only affects the simulation.")
            for col, item in enumerate(cells):
                if not t.enabled:
                    item.setForeground(muted)
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        enabled = sum(1 for t in targets if t.enabled)
        disabled_dirs = edge_policy.disabled_plugin_dirs(targets)
        text = f"{enabled} of {len(targets)} targets enabled"
        if disabled_dirs:
            text += f" · plugin paths off: {', '.join(disabled_dirs)}"
        self.count_label.setText(text)

    def _update_mode_hint(self) -> None:
        direct = self.direct_radio.isChecked()
        self.score_spin.setEnabled(not direct)
        if direct:
            self.mode_hint.setText("A target hit goes straight to a honeypot pool, whatever its score.")
        else:
            self.mode_hint.setText(
                f"Each CVE match and each plugin-path hit adds this score; the request is diverted "
                f"once its total reaches the honeypot threshold ({HONEYPOT_THRESHOLD}).")

    def _save_settings(self, what: str) -> None:
        try:
            self.settings.save()
        except OSError as e:
            QMessageBox.critical(self, "Honeypot targets", f"Could not write {self.settings.path}:\n{e}")
            return
        set_status(self.status, f"{what} (saved; apply to edge to enforce)")
        self.bar.refresh_sync()

    def _save_registry(self, what: str) -> None:
        try:
            self.registry.save()
        except OSError as e:
            QMessageBox.critical(self, "Honeypot targets", f"Could not write the pattern registry:\n{e}")
            return
        self._fill()
        set_status(self.status, f"{what} (saved; apply to edge to enforce)")
        self.bar.refresh_sync()
        self.registry_changed.emit()

    def _on_mode_changed(self, _checked: bool) -> None:
        self.settings.mode = "direct" if self.direct_radio.isChecked() else "score"
        self._update_mode_hint()
        self._save_settings("auto-send mode" if self.settings.mode == "direct" else "score-first mode")

    def _on_score_changed(self, value: int) -> None:
        self.settings.target_score = value
        self._save_settings(f"target score set to {value}")

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        enabled = item.checkState() == Qt.CheckState.Checked
        pattern_id = item.data(_ROLE_ID)
        self.registry.set_enabled(pattern_id, enabled, self._default_enabled(pattern_id))
        self._save_registry(f"{item.text()} {'enabled' if enabled else 'disabled'}")

    def _default_enabled(self, pattern_id: str) -> bool:
        pattern = self.catalog.by_id.get(pattern_id, {}) if self.catalog else {}
        return bool(pattern.get("default_enabled", True))

    def _row_ids(self) -> list[str]:
        return [self.table.item(row, 0).data(_ROLE_ID) for row in range(self.table.rowCount())]

    def _enable_all(self) -> None:
        for pattern_id in self._row_ids():
            self.registry.set_enabled(pattern_id, True, self._default_enabled(pattern_id))
        self._save_registry("all targets enabled")

    def _reset_defaults(self) -> None:
        self.registry.reset_enabled(self._row_ids())
        self._save_registry("targets reset to their defaults")
