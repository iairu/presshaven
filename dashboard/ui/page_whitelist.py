"""URL Whitelist page: the inventory of legitimate shop URLs.

Every legitimate WordPress / WooCommerce endpoint is one row with its own
enable checkbox (core/edge_policy.py). A request to a path that is NOT on the
enabled whitelist earns the edge's ``unlisted_endpoint`` signal -- the
"unlisted path score" below, 0 = inventory only. The whitelist never lowers a
score or skips a check, so a payload on a whitelisted path is still caught.

Edits save to patterns/edge_policy.json at once; "Apply to edge" pushes the
policy to the selected edge (see ui/edge_policy_bar.py)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import edge_policy
from core.state import AppState
from ui import theme
from ui.common import confirm, muted_label, set_status
from ui.edge_policy_bar import EdgePolicyBar, current_document

_ROLE_ID = Qt.ItemDataRole.UserRole


class WhitelistPage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.settings = edge_policy.EdgePolicySettings.load()

        layout = QVBoxLayout(self)
        self.bar = EdgePolicyBar(state, current_document)
        layout.addWidget(self.bar)
        layout.addWidget(self.bar.error_banner)
        layout.addWidget(muted_label(
            "Every legitimate shop URL, each switchable on its own. A request to a path that is not on "
            "the enabled whitelist adds the unlisted-path score to its risk score. The whitelist only "
            "ever adds evidence: an attack payload on a whitelisted path is still detected."))

        score_row = QHBoxLayout()
        score_row.addWidget(QLabel("Unlisted path score:"))
        self.unlisted_spin = QSpinBox()
        self.unlisted_spin.setRange(0, edge_policy.MAX_SCORE)
        self.unlisted_spin.setSuffix(" pts")
        self.unlisted_spin.setToolTip(
            "Added to a request whose path is not on the enabled whitelist. 0 keeps the whitelist as "
            f"an inventory only. Default {edge_policy.DEFAULT_UNLISTED_SCORE}: on its own it never reaches "
            "the honeypot threshold, but it adds up with other evidence.")
        score_row.addWidget(self.unlisted_spin)
        score_row.addStretch()
        self.count_label = QLabel("")
        score_row.addWidget(self.count_label)
        layout.addLayout(score_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Path", "Match", "Group", "Description"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Add path:"))
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/wishlist/")
        add_row.addWidget(self.path_edit, stretch=1)
        self.match_combo = QComboBox()
        self.match_combo.addItem("exact", "exact")
        self.match_combo.addItem("prefix (and everything below)", "prefix")
        add_row.addWidget(self.match_combo)
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("description (optional)")
        add_row.addWidget(self.label_edit, stretch=1)
        self.add_btn = QPushButton("Add")
        add_row.addWidget(self.add_btn)
        layout.addLayout(add_row)

        buttons = QHBoxLayout()
        self.enable_all_btn = QPushButton("Enable all")
        self.remove_btn = QPushButton("Remove custom path")
        self.reset_btn = QPushButton("Reset to defaults")
        self.reset_btn.setToolTip("Restore each built-in entry's default on/off state (custom paths are kept)")
        self.status = QLabel("")
        buttons.addWidget(self.enable_all_btn)
        buttons.addWidget(self.remove_btn)
        buttons.addWidget(self.reset_btn)
        buttons.addWidget(self.status, stretch=1)
        layout.addLayout(buttons)

        self.table.itemChanged.connect(self._on_item_changed)
        self.unlisted_spin.valueChanged.connect(self._on_score_changed)
        self.add_btn.clicked.connect(self._add)
        self.path_edit.returnPressed.connect(self._add)
        self.enable_all_btn.clicked.connect(self._enable_all)
        self.remove_btn.clicked.connect(self._remove)
        self.reset_btn.clicked.connect(self._reset)

        self.reload()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reload()
        self.bar.check()

    def rebuild_targets(self) -> None:
        self.bar.rebuild_targets()

    def reload(self) -> None:
        self.settings = edge_policy.EdgePolicySettings.load()
        self.unlisted_spin.blockSignals(True)
        self.unlisted_spin.setValue(self.settings.unlisted_score)
        self.unlisted_spin.blockSignals(False)
        self._fill()

    def _fill(self) -> None:
        entries = self.settings.whitelist_entries()
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for e in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            path_item = QTableWidgetItem(e.path)
            path_item.setData(_ROLE_ID, e.id)
            # The row's checkbox IS the enable/disable control.
            path_item.setFlags(path_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            path_item.setCheckState(Qt.CheckState.Checked if e.enabled else Qt.CheckState.Unchecked)
            path_item.setToolTip(e.id + (" (custom)" if e.custom else ""))
            self.table.setItem(row, 0, path_item)
            self.table.setItem(row, 1, QTableWidgetItem(e.match))
            self.table.setItem(row, 2, QTableWidgetItem(e.group))
            self.table.setItem(row, 3, QTableWidgetItem(e.label))
        self.table.blockSignals(False)
        enabled = sum(1 for e in entries if e.enabled)
        self.count_label.setText(f"{enabled} of {len(entries)} paths enabled")

    def _save(self, what: str) -> None:
        try:
            self.settings.save()
        except OSError as e:
            QMessageBox.critical(self, "URL whitelist", f"Could not write {self.settings.path}:\n{e}")
            return
        self._fill()
        set_status(self.status, f"{what} (saved; apply to edge to enforce)")
        self.bar.refresh_sync()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        entry_id = item.data(_ROLE_ID)
        enabled = item.checkState() == Qt.CheckState.Checked
        self.settings.set_whitelist_enabled(entry_id, enabled)
        self._save(f"{item.text()} {'enabled' if enabled else 'disabled'}")

    def _on_score_changed(self, value: int) -> None:
        self.settings.unlisted_score = value
        self._save(f"unlisted path score set to {value}")

    def _add(self) -> None:
        try:
            record = self.settings.add_custom(
                self.path_edit.text(), self.match_combo.currentData(), self.label_edit.text())
        except ValueError as e:
            set_status(self.status, str(e), color=theme.scheme_colors()["danger"])
            return
        self.path_edit.clear()
        self.label_edit.clear()
        self._save(f"added {record['path']}")

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(_ROLE_ID) if item else None

    def _remove(self) -> None:
        entry_id = self._selected_id()
        if not entry_id or not self.settings.remove_custom(entry_id):
            set_status(self.status, "select a custom path to remove (built-in paths can only be disabled)")
            return
        self._save("custom path removed")

    def _enable_all(self) -> None:
        for e in self.settings.whitelist_entries():
            self.settings.set_whitelist_enabled(e.id, True)
        self._save("all paths enabled")

    def _reset(self) -> None:
        if not confirm(self, "Reset whitelist",
                       "Restore every built-in path to its default on/off state? Custom paths are kept."):
            return
        self.settings.reset_whitelist()
        self._save("built-in paths reset")
