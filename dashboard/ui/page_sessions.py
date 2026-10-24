"""Sessions page: per-session / per-adversary drill-down. Lists every proxy
session (session:* in session_store) with its IP, risk score, request count,
verdict and honeypot pool, and for the selected one shows a plain-language
summary, the IP's reputation entry and a timeline of the suspicious requests
that built its score. Data comes from one redis round-trip
(core/redis_inspect.list_sessions) interpreted by core/session_view.py."""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import session_view
from core.colors import GREEN, GREY, ORANGE, RED
from core.docker_ctl import targets_for
from core.redis_inspect import RedisInspectError, delete_session, list_sessions
from core.state import AppState
from ui.common import ErrorBanner, Job, TargetSelector, confirm, set_status

REFRESH_MS = 6000

_VERDICT_COLOR = {"benign": GREEN, "suspicious": ORANGE, "over threshold": RED,
                  "diverted": RED, "compromised": RED}
_COLUMNS = ["Session", "IP", "Score", "Requests", "Verdict", "Pool", "Last seen"]


def _clock(ts: int) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "—"


class SessionsPage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._sessions: list[session_view.SessionSummary] = []
        self._shown: list[session_view.SessionSummary] = []
        self._busy = False
        self._jobs: set[Job] = set()

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Target:"))
        self.target_combo = TargetSelector(lambda: targets_for("edge", self.state))
        bar.addWidget(self.target_combo)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by IP, session id or user agent…")
        self.search.setClearButtonEnabled(True)
        bar.addWidget(self.search, stretch=1)
        self.auto_check = QCheckBox("Live")
        self.auto_check.setChecked(True)
        self.auto_check.setToolTip("Refresh the session list every few seconds")
        bar.addWidget(self.auto_check)
        self.reset_btn = QPushButton("Reset session")
        self.reset_btn.setToolTip("Drop the selected session's state so its next request is scored fresh")
        self.reset_btn.setEnabled(False)
        bar.addWidget(self.reset_btn)
        self.refresh_btn = QPushButton("Refresh")
        bar.addWidget(self.refresh_btn)
        self.count_label = QLabel("")
        bar.addWidget(self.count_label)
        layout.addLayout(bar)

        self.error_banner = ErrorBanner()
        layout.addWidget(self.error_banner)

        split = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(split, stretch=1)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        split.addWidget(self.table)

        detail = QSplitter(Qt.Orientation.Horizontal)
        self.story = QPlainTextEdit(readOnly=True)
        self.story.setPlaceholderText("Select a session to see its story.")
        detail.addWidget(self.story)
        self.timeline = QTableWidget(0, 4)
        self.timeline.setHorizontalHeaderLabels(["Time", "Score", "Request", "Patterns"])
        self.timeline.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.timeline.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.timeline.verticalHeader().setVisible(False)
        detail.addWidget(self.timeline)
        detail.setSizes([420, 580])
        split.addWidget(detail)
        split.setSizes([300, 260])

        self.timer = QTimer(self)
        self.timer.setInterval(REFRESH_MS)
        self.timer.timeout.connect(self._tick)
        self.refresh_btn.clicked.connect(self.refresh)
        self.reset_btn.clicked.connect(self._reset_selected)
        self.search.textChanged.connect(self._render)
        self.target_combo.currentIndexChanged.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.auto_check.toggled.connect(self._tick)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()
        self.timer.start()

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def rebuild_targets(self) -> None:
        self.target_combo.rebuild()

    def _tick(self) -> None:
        if self.auto_check.isChecked():
            self.refresh()

    def refresh(self) -> None:
        """Fetch off the GUI thread -- list_sessions can be slow over SSH."""
        if self._busy:
            return
        self._busy = True
        remote = self.target_combo.current_remote()
        job = Job(lambda: list_sessions(remote), self)
        self._jobs.add(job)

        def finished(text, error):
            self._busy = False
            self._jobs.discard(job)
            job.deleteLater()
            if error or text is None:
                self._sessions = []
                self.error_banner.set_error(error or "no data",
                                            prefix="⚠ session_store (Redis) unreachable: ")
            else:
                self._sessions = session_view.parse_snapshot(text)
                self.error_banner.set_error(None)
            self._render()
        job.done.connect(finished)
        job.start()

    def _reset_selected(self) -> None:
        s = self._selected_session()
        if s is None:
            return
        if not confirm(self, "Reset session",
                       f"Drop all stored state for session {s.session_id[:12]} (from {s.ip or 'unknown IP'})? "
                       "Its risk score, honeypot pool binding and fingerprint recovery are cleared, so its "
                       "next request is scored from scratch."):
            return
        try:
            delete_session(self.target_combo.current_remote(), s.session_id)
        except RedisInspectError as e:
            QMessageBox.warning(self, "Reset failed", str(e))
            return
        self.refresh()

    def _render(self) -> None:
        needle = self.search.text().strip().lower()
        self._shown = [s for s in self._sessions
                       if not needle or needle in f"{s.session_id} {s.ip} {s.user_agent}".lower()]
        keep = self._selected_id()
        self.table.setRowCount(len(self._shown))
        for row, s in enumerate(self._shown):
            cells = [s.session_id[:12], s.ip, str(s.risk_score), str(s.request_count),
                     s.verdict, s.pool or "—", _clock(s.last_activity)]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 4:
                    item.setForeground(QColor(_VERDICT_COLOR.get(s.verdict, GREY)))
                self.table.setItem(row, col, item)
            if s.session_id == keep:
                self.table.selectRow(row)
        set_status(self.count_label, f"{len(self._shown)} of {len(self._sessions)} sessions")
        selected = bool(self.table.selectionModel().selectedRows())
        self.reset_btn.setEnabled(selected)
        if not selected:
            self.story.clear()
            self.timeline.setRowCount(0)
            if not self._sessions:
                self.story.setPlaceholderText(
                    "No sessions yet. Bring the edge stack up and run a pattern on the Attack "
                    "Simulation page, then select the session here to read its story.")

    def _selected_id(self) -> str | None:
        s = self._selected_session()
        return s.session_id if s else None

    def _selected_session(self) -> session_view.SessionSummary | None:
        rows = self.table.selectionModel().selectedRows()
        if rows and rows[0].row() < len(self._shown):
            return self._shown[rows[0].row()]
        return None

    def _on_select(self) -> None:
        s = self._selected_session()
        self.reset_btn.setEnabled(s is not None)
        if s is None:
            return
        lines = [session_view.narrative(s), "", f"User agent: {s.user_agent or '—'}",
                 f"First request: {s.first_uri or '—'}",
                 f"Created: {_clock(s.created_at)}   Last activity: {_clock(s.last_activity)}"]
        if s.ip_reputation:
            lines += ["", "IP reputation (threat_ips):"] + [f"  {k}: {v}" for k, v in s.ip_reputation.items()]
        self.story.setPlainText("\n".join(lines))
        self.timeline.setRowCount(len(s.timeline))
        for row, e in enumerate(s.timeline):
            for col, text in enumerate((_clock(e.timestamp), "" if e.score is None else str(e.score),
                                        e.uri, e.detail)):
                self.timeline.setItem(row, col, QTableWidgetItem(text))
