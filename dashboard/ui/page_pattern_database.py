"""Pattern Database page.

A browsable, filterable view of every pattern the edge stack knows about:
the Lua CVE patterns, generic Layer 1/2 signatures, header and upload rules,
the Attack Simulation presets and the Suricata SIDs.  Selecting a row opens a
side panel with the trigger, source provenance, score path and the attack
lesson.

The catalogue is deliberately read from ``patterns/patterns.json`` (generated
by ``tools/generate_pattern_catalog.py``) rather than rebuilt from the Lua
source in the GUI: the same file feeds the documentation site, so both views
cannot drift apart.  On top of that read-only catalogue the page applies the
*pattern-plugin registry* (``core.pattern_registry`` / ``patterns/registry.
json``), the one mutable layer: each row's checkbox enables or disables a
pattern, and per-pattern and bulk actions add, edit, duplicate, remove, revert
and export.  Disabling a pattern here removes it from the Attack Simulation
battery and the Segmentation Validation run through the ``registry_changed``
signal, so "off in the database" means off everywhere it runs.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ui import theme
from core.colors import BLUE, GREY, ORANGE, RED
from core.pattern_catalog import PatternCatalog
from core.pattern_registry import PatternRegistry, load_catalog
from ui.common import ErrorBanner, badge_css, confirm
from ui.pattern_edit_dialog import PatternEditDialog
from ui.responsive import ResponsiveSplitter

_SEVERITY_COLOR = {
    "critical": RED,
    "high": ORANGE,
    "medium": BLUE,
    "low": GREY,
    "info": GREY,
}

_ROLE_ID = Qt.ItemDataRole.UserRole
_ZWSP = "\u200b"


def _fmt(value) -> str:
    return "" if value is None else str(value)


def _wrap_anywhere(label: QLabel, run: int = 14) -> None:
    """Insert zero-width break points into long unbroken tokens.

    QLabel wraps at whitespace only; a percent-encoded URI or an underscore
    identifier therefore keeps its full intrinsic width and forces the whole
    page into a horizontal scrollbar. This changes only what the label
    displays, never the catalogue data or the JSON copied from it.
    """
    text = label.text()
    out: list[str] = []
    since = 0
    for ch in text:
        out.append(ch)
        if ch.isspace() or ch in "/&?=,|_.%":
            since = 0
        else:
            since += 1
            if since >= run:
                out.append(_ZWSP)
                since = 0
    label.setText("".join(out))


def _score_text(pattern: dict) -> str:
    score = pattern.get("score")
    return "no fixed score" if score is None else f"+{score}"


def _source_labels(catalog: PatternCatalog, pattern: dict, limit: int = 3) -> str:
    keys = []
    for source in pattern.get("sources", []):
        key = source.get("key", "")
        if key and key not in keys:
            keys.append(key)
    labels = [catalog.sources.get(key, {}).get("label", key) for key in keys]
    text = ", ".join(labels[:limit])
    if len(labels) > limit:
        text += f" +{len(labels) - limit}"
    return text


class PatternDatabasePage(QWidget):
    # Emitted after any registry change (enable/disable, add, edit, remove) so
    # the main window can refresh the pages that run patterns -- Attack
    # Simulation and Segmentation Validation -- without re-reading the file on
    # their own.
    registry_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog = PatternCatalog(patterns=[], by_id={}, sources={}, kinds={},
                                      categories={}, counts={})
        self.registry = PatternRegistry.load()
        self._filtered: list[dict] = []
        self._selected_id = ""
        self._loading = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # ---- header / summary -------------------------------------------
        summary_row = QHBoxLayout()
        self.summary = QLabel("")
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setWordWrap(True)
        summary_row.addWidget(self.summary, stretch=1)
        self.plugin_badge = QLabel("PLUGINS LIVE")
        self.plugin_badge.setToolTip(
            "Each pattern is a plugin: tick a row to enable/disable it, or use "
            "the per-pattern and bulk actions to add, edit, remove or export. "
            "Changes live in patterns/registry.json and reach the Attack "
            "Simulation and Segmentation Validation pages immediately.")
        summary_row.addWidget(self.plugin_badge, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addLayout(summary_row)

        self.hint = QLabel(
            "One catalogue for both the dashboard and the docs. Filter by category, "
            "source or severity, then select a pattern to inspect its detection path.")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #888888;")
        outer.addWidget(self.hint)

        self.error_banner = ErrorBanner()
        outer.addWidget(self.error_banner)

        # ---- filters ----------------------------------------------------
        filters = QFrame()
        filters_layout = QVBoxLayout(filters)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(6)

        row1 = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name, ID, CVE, WSTG, source, Suricata SID…")
        self.search.setClearButtonEnabled(True)
        row1.addWidget(self.search, stretch=1)
        self.kind_combo = self._make_combo("All types")
        self.category_combo = self._make_combo("All categories")
        self.severity_combo = self._make_combo("All severities")
        row1.addWidget(self.kind_combo)
        row1.addWidget(self.category_combo)
        row1.addWidget(self.severity_combo)
        filters_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.source_combo = self._make_combo("All sources")
        self.component_combo = self._make_combo("All components")
        self.surface_combo = self._make_combo("All surfaces")
        row2.addWidget(self.source_combo)
        row2.addWidget(self.component_combo)
        row2.addWidget(self.surface_combo)
        self.reset_btn = QPushButton("Reset filters")
        row2.addWidget(self.reset_btn)
        row2.addStretch(1)
        filters_layout.addLayout(row2)

        # Actions get their own row: keeping five buttons on the filter row
        # made the page's minimum width ~1170px, which forced a horizontal
        # scrollbar on a 1024px laptop. The catalogue itself and the actions
        # are independent, so a third row is the cheap responsive fix.
        row3 = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #888888;")
        row3.addWidget(self.count_label)
        row3.addStretch(1)
        self.reload_btn = QPushButton("Reload catalogue")
        self.reload_btn.setToolTip("Re-read patterns/patterns.json and the registry from disk")
        row3.addWidget(self.reload_btn)
        self.export_btn = QPushButton("Export filtered…")
        self.export_btn.setToolTip("Save the currently filtered catalogue as JSON")
        row3.addWidget(self.export_btn)
        self.add_btn = QPushButton("Add pattern")
        self.add_btn.setToolTip("Author a new custom pattern (stored in patterns/registry.json)")
        row3.addWidget(self.add_btn)
        self.import_btn = QPushButton("Import…")
        self.import_btn.setToolTip("Import patterns from a honeypot-ids export file")
        row3.addWidget(self.import_btn)
        filters_layout.addLayout(row3)

        # Bulk actions operate on the ticked/selected rows, falling back to the
        # whole filtered set when nothing is selected -- so "disable everything
        # I'm currently looking at" is one click, and the enable/disable
        # decision reaches the Attack Simulation and Segmentation pages at once.
        row4 = QHBoxLayout()
        self.selection_label = QLabel("")
        self.selection_label.setStyleSheet(f"color: {theme.scheme_colors()['fg_muted']};")
        row4.addWidget(self.selection_label)
        row4.addStretch(1)
        self.bulk_enable_btn = QPushButton("Enable")
        self.bulk_enable_btn.setToolTip("Enable the selected patterns (or every filtered pattern)")
        self.bulk_disable_btn = QPushButton("Disable")
        self.bulk_disable_btn.setToolTip("Disable the selected patterns (or every filtered pattern)")
        self.bulk_default_btn = QPushButton("Reset to defaults")
        self.bulk_default_btn.setToolTip(
            "Return the selected patterns (or every filtered pattern) to their default state: "
            "generic attacks and detection signals on, CVE patterns off")
        self.bulk_export_btn = QPushButton("Export selected…")
        self.bulk_remove_btn = QPushButton("Remove…")
        self.bulk_remove_btn.setToolTip("Delete custom patterns / revert edited ones")
        for btn in (self.bulk_enable_btn, self.bulk_disable_btn, self.bulk_default_btn,
                    self.bulk_export_btn, self.bulk_remove_btn):
            row4.addWidget(btn)
        filters_layout.addLayout(row4)
        outer.addWidget(filters)

        # ---- table + detail side panel ----------------------------------
        self.split = ResponsiveSplitter(880)
        self.split.setChildrenCollapsible(False)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Pattern", "Type", "Category", "Severity", "Sources"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(60)
        for column, width in ((1, 104), (2, 124), (3, 86), (4, 150)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(column, width)
        header.setStretchLastSection(False)
        self.table.setMinimumWidth(0)
        self.table.setMinimumHeight(330)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.table.itemChanged.connect(self._on_item_changed)
        self.split.addWidget(self.table)

        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_host = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_host)
        self.detail_layout.setContentsMargins(14, 12, 14, 12)
        self.detail_layout.setSpacing(9)
        self.detail_scroll.setWidget(self.detail_host)
        self.detail_scroll.setMinimumWidth(300)
        self.split.addWidget(self.detail_scroll)
        self.split.setSizes([650, 420])
        outer.addWidget(self.split, stretch=1)

        self.search.textChanged.connect(self._refresh)
        for combo in (self.kind_combo, self.category_combo, self.severity_combo,
                      self.source_combo, self.component_combo, self.surface_combo):
            combo.currentIndexChanged.connect(self._refresh)
        self.reset_btn.clicked.connect(self._reset_filters)
        self.reload_btn.clicked.connect(self.reload)
        self.export_btn.clicked.connect(self._export_filtered)
        self.add_btn.clicked.connect(self._add_pattern)
        self.import_btn.clicked.connect(self._import_patterns)
        self.bulk_enable_btn.clicked.connect(lambda: self._bulk_set_enabled(True))
        self.bulk_disable_btn.clicked.connect(lambda: self._bulk_set_enabled(False))
        self.bulk_default_btn.clicked.connect(self._bulk_reset_enabled)
        self.bulk_export_btn.clicked.connect(self._export_selected)
        self.bulk_remove_btn.clicked.connect(self._bulk_remove)

        theme.on_change(self._theme_changed)
        self._apply_static_theme()
        self.reload()

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------
    def _make_combo(self, first_label: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem(first_label, "")
        combo.setMinimumContentsLength(12)
        return combo

    def _apply_static_theme(self) -> None:
        c = theme.scheme_colors()
        self.plugin_badge.setStyleSheet(
            f"QLabel {{ color: {c['accent']}; border: 1px solid {c['accent']}; "
            f"padding: 3px 8px; font-weight: 700; letter-spacing: 1px; font-size: 8pt; }}")
        self.detail_scroll.setStyleSheet(
            f"QScrollArea {{ background: {c['bg_alt']}; "
            f"border: 1px solid {c['border']}; }}")
        self.hint.setStyleSheet(f"color: {c['fg_muted']};")
        self.count_label.setStyleSheet(f"color: {c['fg_muted']};")
        self.reload_btn.setToolTip("Re-read patterns/patterns.json from disk")

    def _theme_changed(self) -> None:
        self._apply_static_theme()
        self._refresh_summary()
        self._show_detail(self._selected_id)

    # ------------------------------------------------------------------
    # catalogue / filters
    # ------------------------------------------------------------------
    def reload(self) -> None:
        """Load (or re-load) the generated catalogue and rebuild the view."""
        if self._loading:
            return
        self._loading = True
        try:
            self.registry = PatternRegistry.load()
            self.catalog = load_catalog(self.registry)
            self.error_banner.set_error(None)
        except Exception as exc:  # noqa: BLE001 -- a missing/stale file must not kill the page
            self.catalog = PatternCatalog(patterns=[], by_id={}, sources={}, kinds={},
                                          categories={}, counts={})
            self.error_banner.set_error(str(exc), prefix="Cannot load pattern catalogue: ")
        finally:
            self._loading = False
        self._fill_combos()
        self._refresh_summary()
        self._refresh()

    def _fill_combos(self) -> None:
        """Repopulate every filter combo while preserving the current choice."""
        choices = {
            self.kind_combo: self.catalog.option_labels("kind"),
            self.category_combo: self.catalog.option_labels("category"),
            self.severity_combo: [(v, v.title()) for v in
                                  ("critical", "high", "medium", "low", "info")
                                  if v in self.catalog.option_values("severity")],
            self.source_combo: self.catalog.source_options(),
            self.component_combo: [(v, v.replace("-", " ").title())
                                   for v in self.catalog.option_values("component")],
            self.surface_combo: [(v, v.replace("-", " ").title())
                                 for v in self.catalog.option_values("surface")],
        }
        first_labels = {
            self.kind_combo: "All types",
            self.category_combo: "All categories",
            self.severity_combo: "All severities",
            self.source_combo: "All sources",
            self.component_combo: "All components",
            self.surface_combo: "All surfaces",
        }
        for combo, options in choices.items():
            previous = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(first_labels[combo], "")
            for value, label in options:
                combo.addItem(label, value)
            index = combo.findData(previous)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def _refresh_summary(self) -> None:
        c = self.catalog.summary()
        accent = theme.scheme_colors()["accent"]
        muted = theme.scheme_colors()["fg_muted"]
        if not self.catalog.patterns:
            self.summary.setText(f"<span style='color:{muted}'>No pattern catalogue loaded.</span>")
            return
        total = c.get("total", len(self.catalog.patterns))
        disabled = c.get("disabled", sum(1 for p in self.catalog.patterns
                                         if not p.get("enabled", True)))
        custom = c.get("custom", 0)
        sids = c.get("suricata_sids", 0)
        sources = len(self.catalog.source_options())
        generated = self.catalog.generated or "unknown date"
        disabled_txt = (f"<span style='color:{muted}'> · </span>"
                        f"<b style='color:{ORANGE}'>{disabled}</b> "
                        f"<span style='color:{muted}'>disabled</span>") if disabled else ""
        custom_txt = (f"<span style='color:{muted}'> · </span>"
                      f"<b>{custom}</b> <span style='color:{muted}'>custom</span>") if custom else ""
        self.summary.setText(
            f"<span style='font-size:15pt;font-weight:700;color:{accent}'>{total}</span> "
            f"<span style='color:{muted}'>patterns</span>"
            f"{disabled_txt}{custom_txt}"
            f"<span style='color:{muted}'> · </span>"
            f"<b>{sids}</b> <span style='color:{muted}'>Suricata SIDs</span>"
            f"<span style='color:{muted}'> · </span>"
            f"<b>{sources}</b> <span style='color:{muted}'>rule sources</span>"
            f"<span style='color:{muted}'> · generated {html.escape(generated)}</span>")

    def _reset_filters(self) -> None:
        for combo in (self.kind_combo, self.category_combo, self.severity_combo,
                      self.source_combo, self.component_combo, self.surface_combo):
            combo.setCurrentIndex(0)
        self.search.clear()

    def _refresh(self) -> None:
        if self._loading:
            return
        self._filtered = self.catalog.filter(
            query=self.search.text(),
            kind=self.kind_combo.currentData() or "",
            category=self.category_combo.currentData() or "",
            severity=self.severity_combo.currentData() or "",
            source=self.source_combo.currentData() or "",
            component=self.component_combo.currentData() or "",
            surface=self.surface_combo.currentData() or "",
        )
        self._fill_table()
        total = len(self.catalog.patterns)
        shown = len(self._filtered)
        self.count_label.setText(f"{shown} of {total} shown")
        self.export_btn.setEnabled(bool(self._filtered))
        self._update_selection_label()

    def _fill_table(self) -> None:
        previous = self._selected_id
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        muted = QColor(theme.scheme_colors()["fg_muted"])
        accent = QColor(theme.scheme_colors()["accent"])
        for pattern in self._filtered:
            pattern_id = pattern.get("id", "")
            enabled = bool(pattern.get("enabled", True))
            is_custom = self.registry.is_custom(pattern_id)
            is_edited = self.registry.is_edited(pattern_id)
            row = self.table.rowCount()
            self.table.insertRow(row)

            name = pattern.get("name", pattern_id)
            if is_custom:
                name = "✎ " + name
            elif is_edited:
                name = "• " + name
            name_item = QTableWidgetItem(name)
            name_item.setData(_ROLE_ID, pattern_id)
            # The row's checkbox IS the enable/disable control.
            name_item.setFlags((name_item.flags() | Qt.ItemFlag.ItemIsUserCheckable))
            name_item.setCheckState(
                Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            tip = [pattern_id, pattern.get("description", "")]
            if is_custom:
                tip.append("Custom pattern (stored in patterns/registry.json).")
            elif is_edited:
                tip.append("Edited — overlay stored in patterns/registry.json.")
            if not enabled:
                tip.append("Disabled — excluded from Attack Simulation and "
                           "Segmentation Validation.")
            name_item.setToolTip("\n".join(t for t in tip if t))
            font = name_item.font()
            font.setBold(True)
            name_item.setFont(font)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(pattern.get("kind_label", "")))
            self.table.setItem(row, 2, QTableWidgetItem(pattern.get("category_label", "")))
            severity_item = QTableWidgetItem(pattern.get("severity", "").upper())
            severity_item.setForeground(QColor(_SEVERITY_COLOR.get(pattern.get("severity", ""), GREY)))
            severity_font = severity_item.font()
            severity_font.setBold(True)
            severity_item.setFont(severity_font)
            self.table.setItem(row, 3, severity_item)
            sources_item = QTableWidgetItem(_source_labels(self.catalog, pattern))
            sources_item.setToolTip("\n".join(
                f"{s.get('label', s.get('key', ''))} — {s.get('detail', '')}"
                for s in pattern.get("sources", [])))
            self.table.setItem(row, 4, sources_item)

            # A disabled pattern reads muted across the whole row; a custom one
            # keeps its name in the accent colour so authored entries stand out.
            for col in range(5):
                item = self.table.item(row, col)
                if item is None:
                    continue
                if not enabled and col != 3:
                    item.setForeground(muted)
                elif col == 0 and is_custom and enabled:
                    item.setForeground(accent)
        self.table.blockSignals(False)

        target_row = -1
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(_ROLE_ID) == previous:
                target_row = row
                break
        if target_row < 0 and self.table.rowCount():
            target_row = 0
        if target_row >= 0:
            self.table.blockSignals(True)
            self.table.setCurrentCell(target_row, 0)
            self.table.blockSignals(False)
            self._on_select()
        else:
            self._selected_id = ""
            self._show_detail("")

    # ------------------------------------------------------------------
    # side panel
    # ------------------------------------------------------------------
    def _on_select(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            self._selected_id = ""
            self._show_detail("")
            self._update_selection_label()
            return
        item = self.table.item(row, 0)
        pattern_id = item.data(_ROLE_ID) if item is not None else ""
        self._selected_id = pattern_id or ""
        self._show_detail(self._selected_id)
        self._update_selection_label()

    # ------------------------------------------------------------------
    # enable / disable, selection, bulk and plugin actions
    # ------------------------------------------------------------------
    def _selected_ids(self) -> list[str]:
        """IDs of the highlighted rows (the bulk-action target)."""
        ids = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), 0)
            if item is not None:
                pid = item.data(_ROLE_ID)
                if pid:
                    ids.append(pid)
        return ids

    def _bulk_target_ids(self) -> list[str]:
        """What the bulk buttons act on: the selected rows, or every filtered
        pattern when nothing is selected."""
        selected = self._selected_ids()
        if selected:
            return selected
        return [p.get("id", "") for p in self._filtered if p.get("id")]

    def _update_selection_label(self) -> None:
        selected = self._selected_ids()
        n = len(selected)
        if n:
            self.selection_label.setText(f"{n} selected — bulk actions apply to these")
        else:
            self.selection_label.setText("No rows selected — bulk actions apply to all shown")
        removable = any(self.registry.is_custom(i) or self.registry.is_edited(i)
                        for i in (selected or self._bulk_target_ids()))
        self.bulk_remove_btn.setEnabled(removable)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """A row checkbox was toggled: persist the enable/disable and let the
        rest of the dashboard follow."""
        if self._loading or item.column() != 0:
            return
        pattern_id = item.data(_ROLE_ID)
        if not pattern_id:
            return
        enabled = item.checkState() == Qt.CheckState.Checked
        if bool(self.catalog.by_id.get(pattern_id, {}).get("enabled", True)) == enabled:
            return
        self.registry.set_enabled(pattern_id, enabled, self._default_enabled(pattern_id))
        self._commit("enabled" if enabled else "disabled", pattern_id)

    def _default_enabled(self, pattern_id: str) -> bool:
        return bool(self.catalog.by_id.get(pattern_id, {}).get("default_enabled", True))

    def _bulk_set_enabled(self, enabled: bool) -> None:
        ids = self._bulk_target_ids()
        if not ids:
            return
        self.registry.set_many_enabled(ids, enabled, {i: self._default_enabled(i) for i in ids})
        self._commit(f"{'enabled' if enabled else 'disabled'} {len(ids)} pattern(s)")

    def _bulk_reset_enabled(self) -> None:
        ids = self._bulk_target_ids()
        if not ids:
            return
        self.registry.reset_enabled(ids)
        self._commit(f"reset {len(ids)} pattern(s) to their default state")

    def _bulk_remove(self) -> None:
        ids = [i for i in self._bulk_target_ids()
               if self.registry.is_custom(i) or self.registry.is_edited(i)]
        if not ids:
            QMessageBox.information(
                self, "Remove patterns",
                "Nothing to remove: only custom patterns can be deleted and only "
                "edited patterns can be reverted. Generated patterns return on "
                "reload — disable them instead.")
            return
        custom = [i for i in ids if self.registry.is_custom(i)]
        edited = [i for i in ids if not self.registry.is_custom(i)]
        parts = []
        if custom:
            parts.append(f"delete {len(custom)} custom pattern(s)")
        if edited:
            parts.append(f"revert {len(edited)} edited pattern(s) to the catalogue")
        if not confirm(self, "Remove patterns", "This will " + " and ".join(parts) + "."):
            return
        for pattern_id in ids:
            self.registry.remove(pattern_id)
        self._commit(f"removed {len(ids)} pattern(s)")

    def _add_pattern(self) -> None:
        dialog = PatternEditDialog(self)
        if dialog.exec() != PatternEditDialog.DialogCode.Accepted:
            return
        record = self.registry.add_custom(dialog.values())
        self._selected_id = record["id"]
        self._commit(f"added {record['id']}", record["id"])

    def _edit_pattern(self, pattern: dict) -> None:
        pattern_id = pattern.get("id", "")
        generated = not self.registry.is_custom(pattern_id)
        dialog = PatternEditDialog(self, pattern=pattern, generated=generated)
        if dialog.exec() != PatternEditDialog.DialogCode.Accepted:
            return
        self.registry.override(pattern_id, dialog.values())
        self._selected_id = pattern_id
        self._commit(f"edited {pattern_id}", pattern_id)

    def _duplicate_pattern(self, pattern: dict) -> None:
        clone = {k: pattern.get(k) for k in (
            "name", "kind", "kind_label", "category", "category_label",
            "severity", "component", "surface", "description", "trigger",
            "trigger_type", "notes", "tags", "wstg", "owasp", "mitre",
            "attack_vector", "detection", "score", "score_note")}
        clone["id"] = ""  # force a fresh slug
        clone["name"] = (pattern.get("name", "pattern") + " (copy)")
        record = self.registry.add_custom(clone)
        self._selected_id = record["id"]
        self._commit(f"duplicated as {record['id']}", record["id"])

    def _remove_pattern(self, pattern: dict) -> None:
        pattern_id = pattern.get("id", "")
        is_custom = self.registry.is_custom(pattern_id)
        if not is_custom and not self.registry.is_edited(pattern_id):
            QMessageBox.information(
                self, "Remove pattern",
                "This is a generated pattern with no local edits — it would "
                "return on the next reload. Disable it instead.")
            return
        verb = "Delete this custom pattern?" if is_custom else \
            "Revert this pattern to its catalogue values?"
        if not confirm(self, "Remove pattern", verb):
            return
        self.registry.remove(pattern_id)
        self._commit(f"removed {pattern_id}")

    def _revert_pattern(self, pattern_id: str) -> None:
        if not confirm(self, "Revert pattern",
                       "Discard local edits and restore the catalogue values?"):
            return
        self.registry.clear_override(pattern_id)
        self._selected_id = pattern_id
        self._commit(f"reverted {pattern_id}", pattern_id)

    def _import_patterns(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import patterns", str(Path.home()),
            "JSON files (*.json);;All files (*)")
        if not filename:
            return
        try:
            raw = json.loads(Path(filename).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Import patterns", f"Could not read {filename}:\n{exc}")
            return
        records = raw.get("patterns", raw) if isinstance(raw, dict) else raw
        if not isinstance(records, list):
            QMessageBox.critical(self, "Import patterns",
                                 "Unrecognised file: expected a pattern export with a "
                                 "'patterns' list.")
            return
        added = 0
        for record in records:
            if isinstance(record, dict) and record.get("name"):
                self.registry.add_custom({**record, "id": ""})
                added += 1
        if not added:
            QMessageBox.information(self, "Import patterns", "No patterns found to import.")
            return
        self._commit(f"imported {added} pattern(s)")

    def _show_context_menu(self, pos) -> None:
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        id_item = self.table.item(row, 0)
        pattern_id = id_item.data(_ROLE_ID) if id_item is not None else ""
        pattern = self.catalog.by_id.get(pattern_id)
        if not pattern:
            return
        menu = QMenu(self)
        enabled = bool(pattern.get("enabled", True))
        toggle = menu.addAction("Disable" if enabled else "Enable")
        toggle.triggered.connect(lambda: self._toggle_one(pattern_id, not enabled))
        menu.addAction("Edit…", lambda: self._edit_pattern(pattern))
        menu.addAction("Duplicate…", lambda: self._duplicate_pattern(pattern))
        menu.addAction("Export…",
                       lambda: self._export_patterns([pattern], "selected pattern"))
        if self.registry.is_custom(pattern_id):
            menu.addAction("Delete…", lambda: self._remove_pattern(pattern))
        elif self.registry.is_edited(pattern_id):
            menu.addAction("Revert edits…", lambda: self._revert_pattern(pattern_id))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _toggle_one(self, pattern_id: str, enabled: bool) -> None:
        self.registry.set_enabled(pattern_id, enabled, self._default_enabled(pattern_id))
        self._commit("enabled" if enabled else "disabled", pattern_id)

    def _commit(self, what: str, keep_id: str = "") -> None:
        """Save the registry, rebuild the view from the merged catalogue and
        tell the rest of the dashboard a pattern's state changed."""
        try:
            self.registry.save()
        except OSError as exc:
            QMessageBox.critical(self, "Pattern registry",
                                 f"Could not write the pattern registry:\n{exc}")
            return
        if keep_id:
            self._selected_id = keep_id
        self.reload()
        self.count_label.setText(f"Registry {what}")
        self.registry_changed.emit()

    def _new_detail_host(self) -> None:
        """Swap in a fresh scroll-area body instead of deleteLater()ing the
        old labels: a deferred delete lets the previous detail paint for one
        frame and makes fast row changes look like overlapping sections."""
        host = QWidget()
        host.setObjectName("PatternDetailBody")
        host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        host.setStyleSheet(
            f"#PatternDetailBody {{ background: {theme.scheme_colors()['bg_alt']}; }}")
        host.setMinimumWidth(0)
        host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)
        self.detail_scroll.setWidget(host)
        self.detail_host = host
        self.detail_layout = layout

    def _show_detail(self, pattern_id: str) -> None:
        self._new_detail_host()
        pattern = self.catalog.by_id.get(pattern_id)
        if not pattern:
            empty = QLabel("Select a pattern to inspect its trigger, sources, detection path and lesson.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignTop)
            empty.setStyleSheet(f"color: {theme.scheme_colors()['fg_muted']}; padding: 12px;")
            self.detail_layout.addWidget(empty)
            self.detail_layout.addStretch(1)
            return

        c = theme.scheme_colors()
        title = QLabel(pattern.get("name", pattern["id"]))
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title.setStyleSheet(f"color: {c['fg']}; font-size: 14pt; font-weight: 700;")
        self.detail_layout.addWidget(title)

        id_label = QLabel(pattern["id"])
        id_label.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        id_label.setStyleSheet(f"color: {c['fg_muted']};")
        self.detail_layout.addWidget(id_label)

        self.detail_layout.addWidget(self._badge_row(pattern))
        self.detail_layout.addWidget(self._body_label(
            pattern.get("description", ""), color=c["fg"], size=9.5))

        actions = QHBoxLayout()
        copy_btn = QPushButton("Copy JSON")
        copy_btn.setToolTip("Copy this pattern's full catalogue entry")
        copy_btn.clicked.connect(lambda: self._copy_pattern(pattern))
        actions.addWidget(copy_btn)
        export_btn = QPushButton("Export selected…")
        export_btn.setToolTip("Export just this pattern as JSON")
        export_btn.clicked.connect(lambda: self._export_patterns([pattern], "selected pattern"))
        actions.addWidget(export_btn)
        actions.addStretch(1)
        self.detail_layout.addLayout(actions)

        # Trigger
        trigger = pattern.get("trigger", "")
        if trigger:
            body = QLabel(trigger)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            body.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            body.setStyleSheet(f"color: {c['accent']};")
            body.setMinimumWidth(0)
            body.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            _wrap_anywhere(body)
            self.detail_layout.addWidget(self._section("Trigger", body,
                                                       subtitle=pattern.get("trigger_type", "")))
        else:
            self.detail_layout.addWidget(self._section(
                "Trigger", self._body_label("No single trigger string; this entry is behavioural or source-only.",
                                             color=c["fg_muted"])))

        # Detection path
        detection = pattern.get("detection", [])
        text = "\n".join(f"• {line}" for line in detection) if detection else "No direct detection path recorded."
        self.detail_layout.addWidget(self._section(
            "Detection path", self._body_label(text, color=c["fg"], size=9)))

        # Score
        score = pattern.get("score")
        if score is not None or pattern.get("score_note"):
            score_text = _score_text(pattern)
            note = pattern.get("score_note", "")
            body = self._body_label(
                f"{score_text}\n{note}" if note else score_text,
                color=c["fg"], size=9)
            self.detail_layout.addWidget(self._section("Score contribution", body))

        # Sources
        sources = pattern.get("sources", [])
        if sources:
            lines = []
            for source in sources:
                label = source.get("label", source.get("key", ""))
                module = source.get("module", "")
                detail = source.get("detail", "")
                lines.append(f"• {label} — {module}\n  {detail}")
            self.detail_layout.addWidget(self._section(
                "Sources", self._body_label("\n".join(lines), color=c["fg"], size=9)))

        # Signatures
        signatures = pattern.get("signatures", [])
        if signatures:
            lines = []
            for sig in signatures:
                layer = sig.get("layer", "")
                score = sig.get("score")
                name = sig.get("name", "")
                match = sig.get("match", "")
                suffix = f" · +{score}" if score is not None else ""
                label = f"{layer}{(' · ' + name) if name else ''}{suffix}"
                lines.append(f"• {label}\n  {match}")
            self.detail_layout.addWidget(self._section(
                "Signatures", self._body_label("\n".join(lines), color=c["fg"], size=8.5, mono=True)))

        # Suricata
        suricata = pattern.get("suricata", [])
        if suricata:
            lines = []
            for rule in suricata:
                lines.append(f"• SID {rule.get('sid')} (rev {rule.get('rev', 1)}) — "
                             f"{rule.get('message', '')}\n  {rule.get('classtype', '')}")
            self.detail_layout.addWidget(self._section(
                "Suricata evidence", self._body_label("\n".join(lines), color=c["fg"], size=9)))

        # Attack lesson
        lesson = pattern.get("lesson")
        if lesson:
            lines = [
                f"Attack class: {lesson.get('attack_class', '')}",
                f"OWASP: {lesson.get('owasp', '')}",
                f"ATT&CK: {lesson.get('attack', '')}",
                "",
                "How it works",
                lesson.get("how_it_works", ""),
                "",
                "Defence",
                lesson.get("defence", ""),
            ]
            self.detail_layout.addWidget(self._section(
                "Attack lesson", self._body_label("\n".join(lines), color=c["fg"], size=9)))

        # Preset / simulation
        preset = pattern.get("preset")
        if preset:
            lines = [f"{preset.get('method', 'GET')} {preset.get('path', '')}"]
            headers = preset.get("headers") or {}
            if headers:
                lines.append("")
                lines.append("Headers")
                lines.extend(f"{k}: {v}" for k, v in headers.items())
            body = preset.get("body") or ""
            if body:
                lines.append("")
                lines.append("Body")
                lines.append(body)
            sequence = preset.get("sequence") or []
            if sequence:
                lines.append("")
                lines.append("Follow-up requests")
                lines.extend(sequence)
            coverage = preset.get("coverage_note") or ""
            if coverage:
                lines.append("")
                lines.append(f"DB isolation: {'yes' if preset.get('db_isolated', True) else 'no'}")
                lines.append(coverage)
            self.detail_layout.addWidget(self._section(
                "Simulation preset", self._body_label("\n".join(lines), color=c["fg"],
                                                      size=8.5, mono=True)))

        # Notes / coverage
        notes = pattern.get("notes") or ""
        if notes:
            self.detail_layout.addWidget(self._section(
                "Notes", self._body_label(notes, color=c["fg"], size=9)))

        # Plugin controls -- the working enable/disable + edit/remove surface.
        pattern_id = pattern["id"]
        is_custom = self.registry.is_custom(pattern_id)
        is_edited = self.registry.is_edited(pattern_id)
        scaffold = QWidget()
        scaffold_layout = QVBoxLayout(scaffold)
        scaffold_layout.setContentsMargins(0, 0, 0, 0)
        scaffold_layout.setSpacing(5)
        enabled = QCheckBox("Enabled")
        enabled.setChecked(bool(pattern.get("enabled", True)))
        enabled.setToolTip("When off, this pattern is excluded from Attack "
                           "Simulation and Segmentation Validation.")
        enabled.toggled.connect(lambda state, pid=pattern_id: self._toggle_one(pid, state))
        scaffold_layout.addWidget(enabled)
        controls = QHBoxLayout()
        edit_btn = QPushButton("Edit…")
        edit_btn.clicked.connect(lambda: self._edit_pattern(pattern))
        controls.addWidget(edit_btn)
        dup_btn = QPushButton("Duplicate…")
        dup_btn.clicked.connect(lambda: self._duplicate_pattern(pattern))
        controls.addWidget(dup_btn)
        if is_custom:
            remove_btn = QPushButton("Delete…")
            remove_btn.clicked.connect(lambda: self._remove_pattern(pattern))
            controls.addWidget(remove_btn)
        elif is_edited:
            revert_btn = QPushButton("Revert…")
            revert_btn.clicked.connect(lambda pid=pattern_id: self._revert_pattern(pid))
            controls.addWidget(revert_btn)
        controls.addStretch(1)
        scaffold_layout.addLayout(controls)
        if is_custom:
            origin = "Custom pattern — authored here, stored in patterns/registry.json."
        elif is_edited:
            origin = "Edited — your changes overlay the generated catalogue entry."
        else:
            origin = ("Generated from a rule source. Disable it to switch it off, "
                      "or edit to overlay changes; deletes return on the next reload.")
        note = QLabel(origin)
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {c['fg_muted']}; font-size: 8.5pt;")
        scaffold_layout.addWidget(note)
        self.detail_layout.addWidget(self._section("Plugin controls", scaffold))

        # Raw JSON
        raw = QPlainTextEdit()
        raw.setReadOnly(True)
        raw.setMaximumHeight(170)
        raw.setMinimumWidth(0)
        raw.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        raw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        raw.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        raw.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        raw.setPlainText(json.dumps(pattern, indent=2, ensure_ascii=False))
        self.detail_layout.addWidget(self._section("Raw catalogue entry", raw))

        self.detail_layout.addStretch(1)

    def _badge_row(self, pattern: dict) -> QWidget:
        c = theme.scheme_colors()
        row = QWidget()
        row.setMinimumWidth(0)
        row.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        chips = [
            (pattern.get("kind_label", ""), c["accent"], c["accent_text"]),
            (pattern.get("category_label", ""), c["bg_alt"], c["fg"]),
            (pattern.get("severity", "").upper(), _SEVERITY_COLOR.get(pattern.get("severity", ""), GREY), "#111111"),
            (pattern.get("surface", "").title(), c["bg_alt"], c["fg_muted"]),
        ]
        # Component/plugin lives in the facts block: its full name is long
        # enough to push the badge row past the panel edge on narrower
        # windows, and a clipped chip is worse than no chip.
        for text, bg, fg in chips:
            if not text:
                continue
            chip = QLabel(text)
            chip.setStyleSheet(badge_css(bg, fg) + " QLabel { font-size: 8pt; }")
            layout.addWidget(chip)
        layout.addStretch(1)
        return row

    def _body_label(self, text: str, *, color: str, size: float = 9,
                    mono: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        style = f"color: {color}; font-size: {size}pt;"
        if mono:
            style += " font-family: monospace;"
        label.setStyleSheet(style)
        _wrap_anywhere(label)
        return label

    def _section(self, title: str, body: QWidget, subtitle: str = "") -> QFrame:
        c = theme.scheme_colors()
        frame = QFrame()
        frame.setMinimumWidth(0)
        frame.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        frame.setStyleSheet(
            f"QFrame {{ background: {c['bg_alt']}; border: 1px solid {c['border']}; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(9, 7, 11, 8)
        layout.setSpacing(3)
        heading = QLabel(title + (f"  ·  {subtitle}" if subtitle else ""))
        heading.setStyleSheet(
            f"color: {c['accent']}; font-size: 8pt; font-weight: 700; letter-spacing: 1px;")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(body)
        return frame

    # ------------------------------------------------------------------
    # export / clipboard
    # ------------------------------------------------------------------
    def _copy_pattern(self, pattern: dict) -> None:
        QGuiApplication.clipboard().setText(json.dumps(pattern, indent=2, ensure_ascii=False))
        self.count_label.setText(f"Copied {pattern.get('id', 'pattern')} to the clipboard")

    def _export_patterns(self, patterns: list[dict], what: str) -> None:
        if not patterns:
            QMessageBox.information(self, "Export patterns", "There is nothing to export.")
            return
        default = Path.home() / f"honeypot-patterns-{what.replace(' ', '-')}-{datetime.now():%Y%m%d}.json"
        filename, _filter = QFileDialog.getSaveFileName(
            self, f"Export {what}", str(default), "JSON files (*.json);;All files (*)")
        if not filename:
            return
        try:
            payload = self.catalog.export_payload(patterns)
            Path(filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Export patterns", f"Could not write {filename}:\n{exc}")
            return
        self.count_label.setText(f"Exported {len(patterns)} pattern(s) to {filename}")

    def _export_filtered(self) -> None:
        self._export_patterns(self._filtered, "filtered catalogue")

    def _export_selected(self) -> None:
        """Bulk export: the selected rows, or the whole filtered set when
        nothing is selected (same target the other bulk actions use)."""
        ids = self._bulk_target_ids()
        patterns = [self.catalog.by_id[i] for i in ids if i in self.catalog.by_id]
        what = "selected patterns" if self._selected_ids() else "filtered catalogue"
        self._export_patterns(patterns, what)
