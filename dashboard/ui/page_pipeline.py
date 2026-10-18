"""Log Pipeline page: is the edge's Vector shipper actually delivering logs
to the SIEM? The Global Visualization shows vector_outbound as a green box
whenever its container runs, even when the mTLS channel to the aggregator is
failing -- the exact situation ARCHITECTURE.md documents twice. This page
combines four checks: shipping configured (ELK_ENABLED / VECTOR_HOST), the
shipper container running, its log tail (delivery errors vs. the last
healthcheck pass, core/shipper_health.py) and the SIEM-side vector_inbound
container. Refreshed every 15 s while visible, off the GUI thread."""
from __future__ import annotations

import subprocess
import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)
from PyQt6.QtGui import QColor

from core import shipper_health as sh
from core.colors import GREEN, GREY, ORANGE, RED
from core.docker_ctl import Target, targets_for
from core.state import AppState
from ui.common import ErrorBanner, Job, TargetSelector
from ui.flow_layout import FlowLayout
from ui.page_overview import StatCard

REFRESH_MS = 15000
_VERDICT_COLOR = {sh.DELIVERING: GREEN, sh.UNCONFIRMED: ORANGE, sh.FAILING: RED,
                  sh.STOPPED: RED, sh.DISABLED: GREY}
_AGG_COLOR = {"healthy": GREEN, "running": GREEN, "unhealthy": RED, "exited_bad": RED, "down": RED,
              "starting": ORANGE, "created": ORANGE, "unknown": GREY}


def _check(edge: Target, siem_targets: list[Target]):
    """(ShipperHealth, aggregator state) -- runs docker/ssh, so off-thread."""
    enabled, why = edge.siem_shipping()
    shipper = next((c for c in edge.ps() if c.get("Service") == sh.SHIPPER_SERVICE), None)
    logs = ""
    if enabled and shipper is not None:
        argv, cwd = edge.build("logs", "--tail=300", "--timestamps", sh.SHIPPER_SERVICE)
        try:
            logs = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=30).stdout
        except (subprocess.TimeoutExpired, OSError):
            logs = ""
    agg = "unknown"
    for t in siem_targets:
        agg = sh.aggregator_state(t.ps())
        if agg != "unknown":
            break
    return sh.combine(enabled, why, shipper, logs), agg


class PipelinePage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._busy = False
        self._jobs: set[Job] = set()

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Edge target:"))
        self.target_combo = TargetSelector(lambda: targets_for("edge", self.state))
        bar.addWidget(self.target_combo)
        self.refresh_btn = QPushButton("Check now")
        bar.addWidget(self.refresh_btn)
        self.updated = QLabel("")
        bar.addWidget(self.updated, stretch=1)
        layout.addLayout(bar)
        self.error_banner = ErrorBanner()
        layout.addWidget(self.error_banner)

        cards_host = QWidget()
        cards = FlowLayout(cards_host, margin=0, h_spacing=10, v_spacing=10)
        self.card_verdict = StatCard("Edge → SIEM delivery")
        self.card_agg = StatCard("SIEM aggregator")
        self.card_errors = StatCard("Delivery errors (log tail)")
        self.card_ok = StatCard("Last healthcheck pass")
        for c in (self.card_verdict, self.card_agg, self.card_errors, self.card_ok):
            cards.addWidget(c)
        layout.addWidget(cards_host)

        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        note = QLabel("Vector does not log every successful batch, so “delivering” means: the healthcheck passed and "
                      "no delivery error (retry, TLS, DNS, refused connection) has been logged since. To confirm "
                      "end to end, check that honeypot-* indices keep growing on the SIEM.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {GREY}; font-size: 8pt;")
        layout.addWidget(note)

        layout.addWidget(QLabel("<b>Relevant shipper log lines</b>"))
        self.evidence = QListWidget()
        self.evidence.setWordWrap(True)
        layout.addWidget(self.evidence, stretch=1)

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
        edge = self.target_combo.current_target()
        if self._busy or edge is None:
            return
        self._busy = True
        siem = targets_for("siem", self.state)
        job = Job(lambda: _check(edge, siem), self)
        self._jobs.add(job)

        def finished(result, error):
            self._busy = False
            self._jobs.discard(job)
            job.deleteLater()
            if error or result is None:
                self.error_banner.set_error(error or "no data", prefix="⚠ Pipeline check failed: ")
                return
            self.error_banner.set_error(None)
            self._render(*result)
        job.done.connect(finished)
        job.start()

    def _render(self, h: sh.ShipperHealth, agg: str) -> None:
        self.updated.setText(f"checked {time.strftime('%H:%M:%S')}")
        self.card_verdict.set_value(h.verdict, accent=_VERDICT_COLOR.get(h.verdict, GREY))
        self.card_agg.set_value(agg.replace("_", " "), "vector_inbound", _AGG_COLOR.get(agg, GREY))
        self.card_errors.set_value(str(h.error_count), "none in the tail" if not h.error_count else
                                   f"latest {h.last_error or 'unknown time'}", RED if h.error_count else GREEN)
        self.card_ok.set_value(h.last_ok[11:19] if h.last_ok else "—",
                               h.last_ok[:10] if h.last_ok else "none in the tail", GREEN if h.last_ok else GREY)
        self.detail.setText(h.detail)
        self.evidence.clear()
        for e in h.evidence:
            item = QListWidgetItem(("✓ " if e.ok else "✗ ") + e.text)
            item.setForeground(QColor(GREEN if e.ok else RED))
            self.evidence.addItem(item)
