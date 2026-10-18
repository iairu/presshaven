"""Live Events page: an in-app, always-available stream of everything the
reverse proxy's pattern analyzer decides, independent of Kibana and the
SIEM stack. Subscribes to SecurityEventFeed.event_parsed (the existing
app-lifetime log tail -- no second process) and, on first open, backfills
recent history with one `docker compose logs` read so the table is not
blank until the next request arrives. Keeps a bounded table of the most
recent events, with severity/kind filters, free-text search, a per-severity
count summary, pause, clear and CSV export. Filtering, backfill parsing and
export are in core/live_events.py (Qt-free, tested)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import live_events
from core.colors import GREEN, GREY, ORANGE, RED
from core.docker_ctl import target_for
from core.pattern_log_parser import PatternEvent
from core.state import AppState
from ui.common import Job
from ui.security_feed import SecurityEventFeed

MAX_ROWS = 1000
BACKFILL_LINES = 500
_SEV_COLOR = {"high": RED, "medium": ORANGE, "low": GREEN, "info": GREY}


class LiveEventsPage(QWidget):
    def __init__(self, feed: SecurityEventFeed, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._events: list[tuple[int, PatternEvent]] = []   # newest last, all kept up to MAX_ROWS
        self._paused = False
        self._buffered: list[tuple[int, PatternEvent]] = []
        self._backfilled = False
        self._backfill_job: Job | None = None

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

        self.counts = QLabel("")
        self.counts.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.counts)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Time", "Severity", "Kind", "Event", "Detail"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._backfill()

    def _backfill(self) -> None:
        """One-shot read of recent reverse_proxy history, off-thread, so the
        feed is populated the moment the page is first opened instead of
        only from the next live request onward."""
        if self._backfilled or self._backfill_job is not None:
            return
        self._backfilled = True
        self.status.setText("loading recent history…")
        target = target_for("edge", self.state)

        def fetch():
            import subprocess
            argv, cwd = target.build("logs", f"--tail={BACKFILL_LINES}", "--timestamps", "reverse_proxy")
            return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=30).stdout

        self._backfill_job = Job(fetch, self)

        def done(text, _error):
            self._backfill_job = None
            if text:
                existing = {(ts, e.label, e.detail) for ts, e in self._events}
                rows = [(ts, e) for ts, e in live_events.parse_backfill(text)
                        if (ts, e.label, e.detail) not in existing]
                self._events = (rows + self._events)[-MAX_ROWS:]
                self._rebuild()
            else:
                self._update_status()
        self._backfill_job.done.connect(done)
        self._backfill_job.start()

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
        for col, text in enumerate((live_events.format_time(ts), sev.upper(), event.kind,
                                    event.label, event.detail)):
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
        self._update_counts()

    def _update_counts(self) -> None:
        tally = {"high": 0, "medium": 0, "low": 0, "info": 0}
        for _ts, e in self._events:
            tally[live_events.severity(e.color)] += 1
        parts = [f"<b style='color:{_SEV_COLOR[sev]}'>{tally[sev]}</b> {sev}"
                 for sev in ("high", "medium", "low", "info")]
        self.counts.setText(" &nbsp; ".join(parts))
