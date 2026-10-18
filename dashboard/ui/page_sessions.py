"""Sessions page: per-session / per-attacker drill-down. Lists every proxy
session (session:* in session_store) with its IP, risk score, request count,
verdict and honeypot pool, and for the selected one shows a plain-language
summary, the IP's reputation entry and a timeline of the suspicious requests
that built its score. Data comes from one redis round-trip
(core/redis_inspect.list_sessions) interpreted by core/session_view.py."""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import session_view
from core.colors import GREEN, GREY, ORANGE, RED
from core.docker_ctl import targets_for
from core.redis_inspect import RedisInspectError, list_sessions
from core.state import AppState
from ui.common import ErrorBanner, TargetSelector, set_status

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

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Target:"))
        self.target_combo = TargetSelector(lambda: targets_for("edge", self.state))
        bar.addWidget(self.target_combo)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by IP, session id or user agent…")
        self.search.setClearButtonEnabled(True)
        bar.addWidget(self.search, stretch=1)
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

        self.refresh_btn.clicked.connect(self.refresh)
        self.search.textChanged.connect(self._render)
        self.target_combo.currentIndexChanged.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self._on_select)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def rebuild_targets(self) -> None:
        self.target_combo.rebuild()

    def refresh(self) -> None:
        try:
            self._sessions = session_view.parse_snapshot(list_sessions(self.target_combo.current_remote()))
            error = None
        except RedisInspectError as e:
            self._sessions, error = [], str(e)
        self.error_banner.set_error(error, prefix="⚠ session_store (Redis) unreachable: ")
        self._render()

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
        if not self.table.selectionModel().selectedRows():
            self.story.clear()
            self.timeline.setRowCount(0)

    def _selected_id(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if rows and rows[0].row() < len(self._shown):
            return self._shown[rows[0].row()].session_id
        return None

    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self._shown):
            return
        s = self._shown[rows[0].row()]
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
