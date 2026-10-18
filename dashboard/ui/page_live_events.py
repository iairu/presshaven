"""Live Events page: an in-app, always-available stream of everything the
reverse proxy's pattern analyzer decides, independent of Kibana and the
SIEM stack. Subscribes to SecurityEventFeed.event_parsed (the existing
app-lifetime log tail -- no second process), keeps a bounded table of the
most recent events, and offers severity/kind filters, free-text search,
pause, clear and CSV export. Filtering/export logic is in
core/live_events.py (Qt-free, tested)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import live_events
from core.pattern_log_parser import PatternEvent
from ui.security_feed import SecurityEventFeed

MAX_ROWS = 1000


class LiveEventsPage(QWidget):
    def __init__(self, feed: SecurityEventFeed, parent=None):
        super().__init__(parent)
        self._events: list[tuple[int, PatternEvent]] = []   # newest last, all kept up to MAX_ROWS
        self._paused = False
        self._buffered: list[tuple[int, PatternEvent]] = []

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.filter_combo = QComboBox()
        for fid, label in live_events.FILTERS.items():
            self.filter_combo.addItem(label, fid)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter text, e.g. SQL, CVE-2024, wp-admin…")
        self.search.setClearButtonEnabled(True)
        self.autoscroll = QCheckBox("Follow newest")
        self.autoscroll.setChecked(True)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.clear_btn = QPushButton("Clear")
        self.export_btn = QPushButton("Export CSV…")
        for w in (self.filter_combo, self.search):
            bar.addWidget(w, stretch=1 if w is self.search else 0)
        for w in (self.autoscroll, self.pause_btn, self.clear_btn, self.export_btn):
            bar.addWidget(w)
        layout.addLayout(bar)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Time", "Severity", "Event", "Detail"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        self.status = QLabel("")
        layout.addWidget(self.status)

        self.filter_combo.currentIndexChanged.connect(self._rebuild)
        self.search.textChanged.connect(self._rebuild)
        self.pause_btn.toggled.connect(self._on_pause)
        self.clear_btn.clicked.connect(self._clear)
        self.export_btn.clicked.connect(self._export)
        feed.event_parsed.connect(self._on_event)
        self._update_status()

    def _visible(self, event: PatternEvent) -> bool:
        return (live_events.matches(self.filter_combo.currentData(), event.kind, event.label, event.color)
                and live_events.text_matches(self.search.text(), event.label, event.detail))

    def _on_event(self, event: PatternEvent, ts: int) -> None:
        if self._paused:
            self._buffered.append((ts, event))
            self._update_status()
            return
        self._append(ts, event)

    def _append(self, ts: int, event: PatternEvent) -> None:
        self._events.append((ts, event))
        del self._events[:-MAX_ROWS]
        if self._visible(event):
            self._add_row(ts, event)
            while self.table.rowCount() > MAX_ROWS:
                self.table.removeRow(0)
            if self.autoscroll.isChecked():
                self.table.scrollToBottom()
        self._update_status()

    def _add_row(self, ts: int, event: PatternEvent) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        sev = live_events.severity(event.color)
        for col, text in enumerate((live_events.format_time(ts), sev.upper(), event.label, event.detail)):
            item = QTableWidgetItem(text)
            if col == 1:
                item.setForeground(QColor(event.color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, col, item)

    def _rebuild(self) -> None:
        self.table.setRowCount(0)
        for ts, event in self._events:
            if self._visible(event):
                self._add_row(ts, event)
        if self.autoscroll.isChecked():
            self.table.scrollToBottom()
        self._update_status()

    def _on_pause(self, paused: bool) -> None:
        self._paused = paused
        self.pause_btn.setText("Resume" if paused else "Pause")
        if not paused:
            pending, self._buffered = self._buffered, []
            for ts, event in pending:
                self._append(ts, event)
        self._update_status()

    def _clear(self) -> None:
        self._events.clear()
        self._buffered.clear()
        self.table.setRowCount(0)
        self._update_status()

    def _export(self) -> None:
        visible = [(ts, e) for ts, e in self._events if self._visible(e)]
        if not visible:
            QMessageBox.information(self, "Export", "No events to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export events", "live_events.csv", "CSV (*.csv)")
        if not path:
            return
        rows = [(ts, live_events.severity(e.color), e.kind, e.label, e.detail) for ts, e in visible]
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                fh.write(live_events.to_csv(rows))
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def _update_status(self) -> None:
        text = f"{self.table.rowCount()} shown of {len(self._events)} received"
        if self._paused:
            text += f" · paused, {len(self._buffered)} buffered"
        self.status.setText(text)
