"""Pool Scaling page: a standing view of the honeypot pool registry, so the
scaling behaviour is visible without running a full Segmentation Validation
test or reading raw redis keys. Shows pool count and state, the resource
budget in use (memory / CPU / pool cap), why growth stopped, each pool's
sessions and idle time, and pool_manager's recent build / hand-off /
scale-down events. Refreshes every few seconds while the page is visible,
off the GUI thread. Data: core/redis_inspect.pool_snapshot() interpreted by
core/pool_view.py."""
from __future__ import annotations

import time

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QListWidget, QProgressBar, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from core import pool_view
from core.colors import GREEN, GREY, ORANGE, RED
from core.docker_ctl import targets_for
from core.redis_inspect import pool_snapshot
from core.state import AppState
from ui.common import ErrorBanner, Job, TargetSelector
from ui.flow_layout import FlowLayout
from ui.page_overview import StatCard

REFRESH_MS = 5000
_STATE_COLOR = {"steady": GREEN, "scaling up": ORANGE, "sessions waiting": ORANGE,
                "capped": RED, "manager offline": GREY}


def _bar(label: QLabel, bar: QProgressBar) -> QWidget:
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    label.setMinimumWidth(110)
    h.addWidget(label)
    h.addWidget(bar, stretch=1)
    return row


class PoolScalingPage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._busy = False
        self._jobs: set[Job] = set()

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Target:"))
        self.target_combo = TargetSelector(lambda: targets_for("edge", self.state))
        bar.addWidget(self.target_combo)
        self.refresh_btn = QPushButton("Refresh")
        bar.addWidget(self.refresh_btn)
        self.updated = QLabel("")
        bar.addWidget(self.updated, stretch=1)
        layout.addLayout(bar)
        self.error_banner = ErrorBanner()
        layout.addWidget(self.error_banner)

        cards_host = QWidget()
        cards = FlowLayout(cards_host, margin=0, h_spacing=10, v_spacing=10)
        self.card_state = StatCard("Scaling state")
        self.card_pools = StatCard("Pools")
        self.card_waiting = StatCard("Sessions waiting")
        self.card_building = StatCard("Building now")
        for c in (self.card_state, self.card_pools, self.card_waiting, self.card_building):
            cards.addWidget(c)
        layout.addWidget(cards_host)

        self.mem_label, self.mem_bar = QLabel("Memory budget"), QProgressBar()
        self.cpu_label, self.cpu_bar = QLabel("CPU budget"), QProgressBar()
        self.cap_label, self.cap_bar = QLabel("Pool cap"), QProgressBar()
        for lbl, pb in ((self.mem_label, self.mem_bar), (self.cpu_label, self.cpu_bar),
                        (self.cap_label, self.cap_bar)):
            layout.addWidget(_bar(lbl, pb))
        self.reason = QLabel("")
        self.reason.setWordWrap(True)
        layout.addWidget(self.reason)

        split = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(split, stretch=1)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Pool", "Kind", "Sessions", "Idle", "Database"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        split.addWidget(self.table)
        self.events = QListWidget()
        self.events.setWordWrap(True)
        split.addWidget(self.events)
        split.setSizes([480, 520])

        self.timer = QTimer(self)
        self.timer.setInterval(REFRESH_MS)
        self.timer.timeout.connect(self.refresh)
        self.refresh_btn.clicked.connect(self.refresh)
        self.target_combo.currentIndexChanged.connect(self.refresh)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()
        self.timer.start()

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def rebuild_targets(self) -> None:
        self.target_combo.rebuild()

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        remote = self.target_combo.current_remote()
        job = Job(lambda: pool_snapshot(remote), self)
        self._jobs.add(job)

        def finished(text, error):
            self._busy = False
            self._jobs.discard(job)
            job.deleteLater()
            if error or text is None:
                self.error_banner.set_error(error or "no data", prefix="⚠ session_store (Redis) unreachable: ")
                return
            self.error_banner.set_error(None)
            self._render(pool_view.parse_snapshot(text))
        job.done.connect(finished)
        job.start()

    def _render(self, o: pool_view.PoolOverview) -> None:
        self.updated.setText(f"updated {time.strftime('%H:%M:%S')}")
        self.card_state.set_value(o.state, "pool_manager " + ("running" if o.manager_alive else "not reporting"),
                                  _STATE_COLOR.get(o.state, GREY))
        self.card_pools.set_value(str(o.pools), f"{o.ready} ready · {o.free} free",
                                  GREEN if o.ready else GREY)
        self.card_waiting.set_value(str(o.waiting), "borrowing a shared pool" if o.waiting else "none",
                                    ORANGE if o.waiting else GREY)
        self.card_building.set_value(str(len(o.building)),
                                     ", ".join(f"pool {n}" for n in o.building) or "idle",
                                     ORANGE if o.building else GREY)
        self._set_bar(self.mem_bar, o.mem_used_mb, o.mem_max_mb, f"{o.mem_used_mb} / {o.mem_max_mb} MB")
        self._set_bar(self.cpu_bar, o.cpu_used, o.cpu_max, f"{o.cpu_used:g} / {o.cpu_max:g} CPUs")
        self._set_bar(self.cap_bar, o.pools, o.max_pools, f"{o.pools} / {o.max_pools} pools")
        if o.capped_reason:
            self.reason.setText(f"⚠ Growth stopped: {o.capped_reason}. New sessions now reuse existing pools round-robin.")
        elif o.scaledown_pending:
            self.reason.setText("A forced scale-down is in progress.")
        else:
            idle = f" Idle pools are removed after {o.idle_timeout // 60} min." if o.idle_timeout else ""
            self.reason.setText(f"Room for {o.room} more pool(s).{idle}" if o.manager_alive else
                                "pool_manager is not reporting -- start the edge stack on the Workloads page.")

        self.table.setRowCount(len(o.rows))
        for r, row in enumerate(o.rows):
            idle = "—" if row.idle_seconds is None else (
                f"{row.idle_seconds}s" if row.idle_seconds < 120 else f"{row.idle_seconds // 60}m")
            db = "—" if row.healthy is None else ("healthy" if row.healthy else "unhealthy")
            kind = ("static" if row.static else "runtime") + (" · free" if row.free else "")
            for c, text in enumerate((f"pool {row.number}", kind, str(row.owners), idle, db)):
                item = QTableWidgetItem(text)
                if c == 4 and row.healthy is False:
                    item.setForeground(QColor(RED))
                self.table.setItem(r, c, item)

        self.events.clear()
        for ts, text in reversed(o.events):
            self.events.addItem(f"{time.strftime('%H:%M:%S', time.localtime(ts))}   {text}")

    @staticmethod
    def _set_bar(bar: QProgressBar, used: float, maximum: float, text: str) -> None:
        bar.setRange(0, 1000)
        bar.setValue(int(min(1.0, used / maximum) * 1000) if maximum else 0)
        bar.setFormat(text if maximum else "no limit reported")
