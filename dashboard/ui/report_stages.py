"""A staged progress overview for the Attack Simulation page's PDF export.

Replaces the single progress bar: the export runs several distinct phases
(threat decay baseline, session restoration, the per-pattern battery, the
threat-increase scenario, then rendering), and a bare bar gives no sense of
which one is underway or how many remain. This shows every phase as a row
that goes pending -> active -> done, with the active row carrying the live
message and its own sub-bar. The phase boundaries come from
core/report_progress.py (Qt-free, tested)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from core.report_progress import STAGES, stage_fraction, stage_index_for_fraction
from ui import theme


class _StageRow(QWidget):
    """One phase: a status glyph + title line, and -- only while it is the
    active phase -- a thin sub-bar and the live detail message beneath it."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._base_title = title
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 1, 0, 1)
        outer.setSpacing(1)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        self.glyph = QLabel("○")
        self.glyph.setFixedWidth(16)
        self.glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel(title)
        head.addWidget(self.glyph)
        head.addWidget(self.title)
        head.addStretch(1)
        outer.addLayout(head)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setMaximumHeight(4)
        self.bar.setTextVisible(False)
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        outer.addWidget(self.bar)
        outer.addWidget(self.detail)
        self.set_state("pending")

    def set_title_suffix(self, suffix: str) -> None:
        self.title.setText(self._base_title + suffix)

    def set_state(self, state: str, detail: str = "") -> None:
        """state is 'pending' | 'active' | 'done'."""
        c = theme.scheme_colors()
        active = state == "active"
        self.bar.setVisible(active)
        self.detail.setVisible(active and bool(detail))
        if detail:
            self.detail.setText(detail)
            self.detail.setStyleSheet(f"color: {c['fg_muted']}; font-size: 11px; padding-left: 22px;")
        if state == "done":
            self.glyph.setText("✓")
            color, weight = c["success"], "600"
        elif active:
            self.glyph.setText("▸")
            color, weight = c["accent"], "600"
        else:
            self.glyph.setText("○")
            color, weight = c["fg_muted"], "400"
        self.glyph.setStyleSheet(f"color: {color};")
        self.title.setStyleSheet(f"color: {color}; font-weight: {weight};")

    def set_sub_progress(self, fraction: float) -> None:
        self.bar.setValue(int(max(0.0, min(1.0, fraction)) * 1000))


class ReportStagesWidget(QWidget):
    """The column of phase rows. Driven by update(fraction, message) from the
    export worker's progress signal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._rows: list[_StageRow] = []
        for stage in STAGES:
            row = _StageRow(stage.title)
            self._rows.append(row)
            layout.addWidget(row)

    def reset(self, n_patterns: int) -> None:
        """Start a fresh export: every phase pending, the pattern phase's
        title annotated with how many patterns the battery covers."""
        for row in self._rows:
            row.set_state("pending")
        patterns = _index("patterns")
        if patterns is not None:
            self._rows[patterns].set_title_suffix(f" ({n_patterns})")

    def update(self, fraction: float, message: str) -> None:
        idx = stage_index_for_fraction(fraction)
        for i, row in enumerate(self._rows):
            if i < idx:
                row.set_state("done")
            elif i == idx:
                row.set_state("active", detail=message)
                row.set_sub_progress(stage_fraction(fraction, i))
            else:
                row.set_state("pending")

    def mark_all_done(self) -> None:
        for row in self._rows:
            row.set_state("done")


def _index(key: str) -> int | None:
    for i, s in enumerate(STAGES):
        if s.key == key:
            return i
    return None
