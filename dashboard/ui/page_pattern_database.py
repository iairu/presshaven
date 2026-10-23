"""Pattern Database page.

A browsable, filterable view of every pattern the edge stack knows about:
the Lua CVE patterns, generic Layer 1/2 signatures, header and upload rules,
the Attack Simulation presets and the Suricata SIDs.  Selecting a row opens a
side panel with the trigger, source provenance, score path and the attack
lesson.

The catalogue is deliberately read from ``patterns/patterns.json`` (generated
by ``tools/generate_pattern_catalog.py``) rather than rebuilt from the Lua
source in the GUI: the same file feeds the documentation site, so both views
cannot drift apart.  The page is also the scaffold for the upcoming
"patterns as plugins" workflow -- stable IDs, per-entry metadata, and export
already exist; the add/edit/remove/enable controls are visible but disabled
until the engine-side registry lands.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from ui import theme
from core.colors import BLUE, GREY, ORANGE, RED
from core.pattern_catalog import PatternCatalog
from ui.common import ErrorBanner, badge_css, clear_layout
from ui.responsive import ResponsiveSplitter

_SEVERITY_COLOR = {
    "critical": RED,
    "high": ORANGE,
    "medium": BLUE,
    "low": GREY,
    "info": GREY,
}

_ROLE_ID = Qt.ItemDataRole.UserRole


def _fmt(value) -> str:
    return "" if value is None else str(value)


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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog = PatternCatalog(patterns=[], by_id={}, sources={}, kinds={},
                                      categories={}, counts={})
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
        self.plugin_badge = QLabel("PLUGIN-READY")
        self.plugin_badge.setToolTip(
            "Every entry has a stable ID, provenance and export shape. "
            "Add / edit / remove / enable controls will use these IDs when the "
            "pattern-plugin registry lands.")
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
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #888888;")
        row2.addWidget(self.count_label)

        self.reload_btn = QPushButton("Reload catalogue")
        self.reload_btn.setToolTip("Re-read patterns/patterns.json from disk")
        row2.addWidget(self.reload_btn)
        self.export_btn = QPushButton("Export filtered…")
        self.export_btn.setToolTip("Save the currently filtered catalogue as JSON")
        row2.addWidget(self.export_btn)
        self.add_btn = QPushButton("Add pattern…")
        self.add_btn.setEnabled(False)
        self.add_btn.setToolTip("Scaffolded for the upcoming pattern-plugin registry")
        row2.addWidget(self.add_btn)
        self.import_btn = QPushButton("Import…")
        self.import_btn.setEnabled(False)
        self.import_btn.setToolTip("Scaffolded for the upcoming pattern-plugin registry")
        row2.addWidget(self.import_btn)
        filters_layout.addLayout(row2)
        outer.addWidget(filters)

        # ---- table + detail side panel ----------------------------------
        self.split = ResponsiveSplitter(880)
        self.split.setChildrenCollapsible(False)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Pattern", "Type", "Category", "Severity", "Sources", "ID"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        self.table.setMinimumHeight(330)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.split.addWidget(self.table)

        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
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
            self.catalog = PatternCatalog.load()
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
        cves = c.get("cves", 0)
        sids = c.get("suricata_sids", 0)
        sources = len(self.catalog.source_options())
        generated = self.catalog.generated or "unknown date"
        self.summary.setText(
            f"<span style='font-size:15pt;font-weight:700;color:{accent}'>{total}</span> "
            f"<span style='color:{muted}'>patterns</span>"
            f"<span style='color:{muted}'> · </span>"
            f"<b>{cves}</b> <span style='color:{muted}'>CVEs</span>"
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

    def _fill_table(self) -> None:
        previous = self._selected_id
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for pattern in self._filtered:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(pattern.get("name", pattern.get("id", "")))
            name_item.setData(_ROLE_ID, pattern.get("id", ""))
            name_item.setToolTip(pattern.get("description", ""))
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
            id_item = QTableWidgetItem(pattern.get("id", ""))
            id_item.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            self.table.setItem(row, 5, id_item)
        self.table.blockSignals(False)

        target_row = -1
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(_ROLE_ID) == previous:
                target_row = row
                break
        if target_row < 0 and self.table.rowCount():
            target_row = 0
        if target_row >= 0:
            self.table.setCurrentCell(target_row, 0)
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
            return
        item = self.table.item(row, 0)
        pattern_id = item.data(_ROLE_ID) if item is not None else ""
        self._selected_id = pattern_id or ""
        self._show_detail(self._selected_id)

    def _show_detail(self, pattern_id: str) -> None:
        clear_layout(self.detail_layout)
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

        # Plugin scaffold
        scaffold = QWidget()
        scaffold_layout = QVBoxLayout(scaffold)
        scaffold_layout.setContentsMargins(0, 0, 0, 0)
        scaffold_layout.setSpacing(5)
        enabled = QCheckBox("Enabled")
        enabled.setChecked(bool(pattern.get("enabled", True)))
        enabled.setEnabled(False)
        enabled.setToolTip("Read-only preview: toggles will use this stable ID once the pattern-plugin registry lands.")
        scaffold_layout.addWidget(enabled)
        controls = QHBoxLayout()
        for label in ("Edit…", "Duplicate…", "Remove…"):
            button = QPushButton(label)
            button.setEnabled(False)
            button.setToolTip("Scaffolded for the upcoming pattern-plugin registry")
            controls.addWidget(button)
        controls.addStretch(1)
        scaffold_layout.addLayout(controls)
        note = QLabel("Pattern plugins are next: the catalogue already provides the contract "
                      "(stable ID, provenance, export payload, enabled state).")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {c['fg_muted']}; font-size: 8.5pt;")
        scaffold_layout.addWidget(note)
        self.detail_layout.addWidget(self._section("Plugin controls", scaffold))

        # Raw JSON
        raw = QPlainTextEdit()
        raw.setReadOnly(True)
        raw.setMaximumHeight(170)
        raw.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        raw.setPlainText(json.dumps(pattern, indent=2, ensure_ascii=False))
        self.detail_layout.addWidget(self._section("Raw catalogue entry", raw))

        self.detail_layout.addStretch(1)

    def _badge_row(self, pattern: dict) -> QWidget:
        c = theme.scheme_colors()
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        chips = [
            (pattern.get("kind_label", ""), c["accent"], c["accent_text"]),
            (pattern.get("category_label", ""), c["bg_alt"], c["fg"]),
            (pattern.get("severity", "").upper(), _SEVERITY_COLOR.get(pattern.get("severity", ""), GREY), "#111111"),
            (pattern.get("surface", "").title(), c["bg_alt"], c["fg_muted"]),
        ]
        component = pattern.get("component", "")
        if pattern.get("plugin"):
            chips.append((f"{component}: {pattern['plugin']}", c["bg_alt"], c["fg"]))
        elif component:
            chips.append((component.title(), c["bg_alt"], c["fg"]))
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
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        style = f"color: {color}; font-size: {size}pt;"
        if mono:
            style += " font-family: monospace;"
        label.setStyleSheet(style)
        return label

    def _section(self, title: str, body: QWidget, subtitle: str = "") -> QFrame:
        c = theme.scheme_colors()
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {c['bg_alt']}; border: 1px solid {c['border']}; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(9, 7, 9, 8)
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
