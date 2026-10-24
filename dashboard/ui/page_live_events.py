"""Live Events page: an in-app, always-available stream of everything the
reverse proxy's pattern analyzer decides, independent of Kibana and the
SIEM stack. Subscribes to SecurityEventFeed.event_parsed (the existing
app-lifetime log tail -- no second process) and, on first open, backfills
recent history with one `docker compose logs` read so the table is not
blank until the next request arrives.

Rather than one table row per raw log line, related lines are collapsed into
one row per request: a request logs a burst of scoring signals, routing
steps and a final score, terminated by a single "outcome" line, and that
burst becomes one entry showing the outcome, the final score, the signals
that fired, and a per-request latency (the span from the first to the last
log line of the burst). Grouping, latency and filtering live in
core/live_events.py (Qt-free, tested)."""
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

# Table columns. One row = one request (a collapsed burst of related events).
COL_TIME, COL_SEV, COL_REQUEST, COL_SCORE, COL_SIGNALS, COL_LATENCY = range(6)


class LiveEventsPage(QWidget):
    def __init__(self, feed: SecurityEventFeed, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._events: list[tuple[int, PatternEvent]] = []   # newest last, all kept up to MAX_ROWS
        self._paused = False
        self._buffered: list[tuple[int, PatternEvent]] = []
        self._backfilled = False
        self._backfill_job: Job | None = None
        # The trailing request whose outcome line hasn't arrived yet, and the
        # table row showing it (so a growing request updates one row in place
        # instead of forcing a full rebuild on every line). Reset whenever an
        # outcome closes the group, and recomputed on _rebuild().
        self._open_group: list[tuple[int, PatternEvent]] = []
        self._open_row: int | None = None

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

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Time", "Severity", "Request", "Score", "Signals", "Latency"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(COL_REQUEST, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(COL_SIGNALS, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setToolTip(
            "Latency: the span from a request's first analyzer line to its routing "
            "outcome, measured from the log timestamps.")
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

    def _gvisible(self, group: live_events.EventGroup) -> bool:
        return (live_events.group_matches(self.filter_combo.currentData(), group)
                and live_events.text_matches(self.search.text(), group.search_text))

    # -- live input -------------------------------------------------------

    def _on_event(self, event: PatternEvent, ts: int) -> None:
        if self._paused:
            self._buffered.append((ts, event))
            self._update_status()
            return
        self._append(ts, event)

    def _append(self, ts: int, event: PatternEvent) -> None:
        self._events.append((ts, event))
        if len(self._events) > MAX_ROWS:
            del self._events[:-MAX_ROWS]
        # Extend the in-flight request (the open group) and reflect it in its
        # row. The newest events are never the ones trimmed above, so the open
        # group stays intact.
        self._open_group.append((ts, event))
        group = live_events.summarize_group(self._open_group)
        if self._gvisible(group):
            if self._open_row is None:
                self._open_row = self.table.rowCount()
                self.table.insertRow(self._open_row)
            self._fill_row(self._open_row, group)
            self._cap_rows()
            if self.autoscroll.isChecked():
                self.table.scrollToBottom()
        if event.kind == "outcome":
            # Request finished -> freeze this row and start a fresh group.
            self._open_group = []
            self._open_row = None
        self._update_status()

    def _cap_rows(self) -> None:
        while self.table.rowCount() > MAX_ROWS:
            self.table.removeRow(0)
            if self._open_row is not None:
                self._open_row -= 1

    # -- rendering --------------------------------------------------------

    def _fill_row(self, row: int, group: live_events.EventGroup) -> None:
        sev = live_events.severity(group.color)
        score = "" if group.score is None else str(group.score)
        latency = "—" if group.latency_ms is None else f"{group.latency_ms} ms"
        cells = {
            COL_TIME: live_events.format_time(group.ts),
            COL_SEV: sev.upper(),
            COL_REQUEST: group.title,
            COL_SCORE: score,
            COL_SIGNALS: group.signals,
            COL_LATENCY: latency,
        }
        for col, text in cells.items():
            item = QTableWidgetItem(text)
            if col == COL_SEV:
                item.setForeground(QColor(group.color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            elif col in (COL_SCORE, COL_LATENCY):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if group.detail:
                item.setToolTip(group.detail)
            self.table.setItem(row, col, item)

    def _groups(self) -> list[live_events.EventGroup]:
        return live_events.group_events(self._events)

    def _rebuild(self) -> None:
        self.table.setRowCount(0)
        for group in self._groups():
            if self._gvisible(group):
                row = self.table.rowCount()
                self.table.insertRow(row)
                self._fill_row(row, group)
        # Re-establish the open-group tracking so live appends keep updating
        # one row in place: the trailing events after the last outcome.
        self._open_group = self._trailing_open()
        if self._open_group and self._gvisible(live_events.summarize_group(self._open_group)):
            self._open_row = self.table.rowCount() - 1
        else:
            self._open_row = None
        if self.autoscroll.isChecked():
            self.table.scrollToBottom()
        self._update_status()

    def _trailing_open(self) -> list[tuple[int, PatternEvent]]:
        """The events of the still-in-flight request: everything after the
        most recent outcome line (empty if the newest event was an outcome)."""
        tail: list[tuple[int, PatternEvent]] = []
        for ts, e in reversed(self._events):
            if e.kind == "outcome":
                break
            tail.append((ts, e))
        tail.reverse()
        return tail

    # -- controls ---------------------------------------------------------

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
        self._open_group = []
        self._open_row = None
        self.table.setRowCount(0)
        self._update_status()

    def _export(self) -> None:
        visible = [g for g in self._groups() if self._gvisible(g)]
        if not visible:
            QMessageBox.information(self, "Export", "No events to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export events", "live_events.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                fh.write(live_events.groups_to_csv(visible))
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def _update_status(self) -> None:
        text = f"{self.table.rowCount()} requests shown of {len(self._events)} events received"
        if self._paused:
            text += f" · paused, {len(self._buffered)} buffered"
        self.status.setText(text)
        self._update_counts()

    def _update_counts(self) -> None:
        tally = {"high": 0, "medium": 0, "low": 0, "info": 0}
        for group in self._groups():
            tally[live_events.severity(group.color)] += 1
        parts = [f"<b style='color:{_SEV_COLOR[sev]}'>{tally[sev]}</b> {sev}"
                 for sev in ("high", "medium", "low", "info")]
        self.counts.setText(" &nbsp; ".join(parts))
