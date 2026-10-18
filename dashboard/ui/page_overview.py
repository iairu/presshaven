"""Overview page: the dashboard's landing screen -- a security-operations
summary assembled from data the app already collects but never showed in
one place before.

Two live sources feed it, with no new background work of its own:
  - the shared StatusPoller's per-target `docker compose ps` results
    (pushed in via apply_status(), exactly like Workloads/Global
    Visualization), aggregated per project into one health line each; and
  - the app-lifetime SecurityEventFeed (ui/security_feed.py), whose
    `score_changed`/`event_added` signals and persisted
    `recent_events()` history drive the current risk score and the live
    "recent security events" list. That feed used to power nothing (its
    own docstring referenced an Overview page that did not exist) -- this
    page is finally its consumer.

Pure presentation: all the counting lives in core/overview_stats.py
(Qt-free, unit-tested). Clicking a quick-action jumps to the relevant page
via open_page_requested, the same mechanism the Knowledge Base page uses.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QWidget,
)

from core import overview_stats, pool_view, session_view
from core.colors import GREEN, GREY, ORANGE, RED
from core.docker_ctl import target_for
from core.pattern_log_parser import COLOR_HIGH, PatternEvent
from core.redis_inspect import list_sessions, pool_snapshot
from core.state import AppState
from ui import theme
from ui.common import Job
from ui.flow_layout import FlowLayout
from ui.security_feed import SecurityEventFeed

# How often the landing-page stats refresh while the page is visible, so the
# decayed score, the "(1h)" windows and the live redis-backed cards don't go
# stale just because the user is sitting on the page. Kept brisk (3s) so the
# decaying risk score visibly ticks down; the redis-backed cards self-
# throttle via _redis_busy if a fetch is slower than one interval.
REFRESH_MS = 3000

# Risk-score colour bands -- the honeypot routing threshold is 80 (see the
# Knowledge Base glossary / init.lua), so a score at or above it is the
# danger colour, an elevated score the warning colour.
_HONEYPOT_THRESHOLD = 80
_ELEVATED = 40


def _score_color(score: int | None) -> str:
    if score is None:
        return GREY
    if score >= _HONEYPOT_THRESHOLD:
        return RED
    if score >= _ELEVATED:
        return ORANGE
    return GREEN


def _ago(ts: float | None) -> str:
    if not ts:
        return "never"
    delta = max(0, int(time.time() - ts))
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    return f"{delta // 86400}d ago"


class StatCard(QFrame):
    """A titled value tile -- big value, small caption, accent bar in a
    status colour. Recoloured on theme change via set_value()'s cached
    args, so it follows light/dark like the rest of the app."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setMinimumWidth(190)
        self._value = "—"
        self._accent = GREY
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("StatCardTitle")
        self.value_label = QLabel(self._value)
        self.value_label.setObjectName("StatCardValue")
        self.caption_label = QLabel("")
        self.caption_label.setObjectName("StatCardCaption")
        self.caption_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.caption_label)
        theme.on_change(self._restyle)
        self._restyle()

    def set_value(self, value: str, caption: str = "", accent: str | None = None) -> None:
        self._value = value
        if accent is not None:
            self._accent = accent
        self.value_label.setText(value)
        self.caption_label.setText(caption)
        self.caption_label.setVisible(bool(caption))
        self._restyle()

    def _restyle(self) -> None:
        c = theme.scheme_colors()
        self.setStyleSheet(
            f"#StatCard {{ background: {c['surface']}; border: 1px solid {c['border']};"
            f" border-left: 4px solid {self._accent}; border-radius: 8px; }}"
            f"#StatCardTitle {{ color: {c['fg_muted']}; font-size: 8pt; font-weight: 700;"
            " letter-spacing: 1px; }"
            f"#StatCardValue {{ color: {self._accent}; font-size: 22pt; font-weight: 800; }}"
            f"#StatCardCaption {{ color: {c['fg_muted']}; font-size: 8pt; }}")


class OverviewPage(QWidget):
    open_page_requested = pyqtSignal(str)
    lifecycle_requested = pyqtSignal(str)   # "start" | "stop" | "restart", for both stacks

    def __init__(self, state: AppState, security_feed: SecurityEventFeed, parent=None):
        super().__init__(parent)
        self.state = state
        self.feed = security_feed
        self._last_results: dict = {}
        self._redis_busy = False
        self._jobs: set[Job] = set()

        root = QVBoxLayout(self)
        root.setSpacing(12)

        # ---- stat cards ----
        cards_host = QWidget()
        self._cards = FlowLayout(cards_host, margin=0, h_spacing=10, v_spacing=10)
        self.card_score = StatCard("Current risk score")
        self.card_health = StatCard("System health")
        self.card_diverted = StatCard("Attackers diverted")
        self.card_pools = StatCard("Honeypot pools")
        self.card_events = StatCard("Notable events (1h)")
        for card in (self.card_score, self.card_health, self.card_diverted,
                     self.card_pools, self.card_events):
            self._cards.addWidget(card)
        root.addWidget(cards_host)

        # ---- per-stack health lines + lifecycle controls ----
        stacks_row = QHBoxLayout()
        self.stacks_label = QLabel("Bring the stacks up to see live health.")
        self.stacks_label.setWordWrap(True)
        self.stacks_label.setStyleSheet(f"color: {GREY};")
        stacks_row.addWidget(self.stacks_label, stretch=1)
        self.start_btn = QPushButton("▶ Start all")
        self.start_btn.setToolTip("docker compose up -d on the ids and siem stacks (every configured target)")
        self.start_btn.clicked.connect(lambda: self.lifecycle_requested.emit("start"))
        self.restart_all_btn = QPushButton("⟳ Restart all")
        self.restart_all_btn.clicked.connect(lambda: self.lifecycle_requested.emit("restart"))
        self.stop_btn = QPushButton("■ Stop all")
        self.stop_btn.setToolTip("docker compose stop on the ids and siem stacks")
        self.stop_btn.clicked.connect(lambda: self.lifecycle_requested.emit("stop"))
        for b in (self.start_btn, self.restart_all_btn, self.stop_btn):
            stacks_row.addWidget(b)
        root.addLayout(stacks_row)

        # ---- quick actions ----
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for label, page in [
            ("Run an attack →", "patterns"),
            ("Open SIEM analytics →", "kibana"),
            ("Search logs →", "log_search"),
            ("Inspect state store →", "redis"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _c, p=page: self.open_page_requested.emit(p))
            actions.addWidget(btn)
        actions.addStretch()
        root.addLayout(actions)

        # ---- recent security events ----
        header = QHBoxLayout()
        title = QLabel("Recent security events")
        title.setStyleSheet("font-weight: 700; font-size: 11pt;")
        header.addWidget(title)
        header.addStretch()
        self.events_hint = QLabel("honeypot diversions, CVE / high-severity signals")
        self.events_hint.setStyleSheet(f"color: {GREY}; font-size: 8pt;")
        header.addWidget(self.events_hint)
        root.addLayout(header)

        self.events_list = QListWidget()
        self.events_list.setWordWrap(True)
        root.addWidget(self.events_list, stretch=1)

        # Seed from persisted history (previous sessions + this one), then
        # subscribe to live additions.
        for event, ts in self.feed.recent_events():
            self._add_event_item(event, ts)
        self._scroll_events_to_bottom()
        self._refresh_score()
        self._refresh_counts()
        self.card_diverted.set_value("—", "bring the edge stack up", GREY)
        self.card_pools.set_value("—", "bring the edge stack up", GREY)

        self.feed.event_added.connect(self._on_event_added)
        self.feed.score_changed.connect(self._on_score_changed)

        # Auto-refresh while visible: time-based cards and the decayed score
        # recomputed locally, the diverted-attacker and pool cards re-fetched
        # from the session store off the GUI thread.
        self.timer = QTimer(self)
        self.timer.setInterval(REFRESH_MS)
        self.timer.timeout.connect(self._tick)

    # ---- live updates ----

    def apply_status(self, results: dict) -> None:
        """Called from MainWindow on every poll tick with the same results
        dict the other pages get."""
        self._last_results = results
        healths = [overview_stats.project_health(results, "edge", "Edge (IDS honeypot)"),
                   overview_stats.project_health(results, "siem", "SIEM (ELK)")]
        lines = [f"<b>{h.label}:</b> <span style='color:{h.color};'>{h.text}</span>" for h in healths]
        self.stacks_label.setText("&nbsp;&nbsp;·&nbsp;&nbsp;".join(lines))
        self.stacks_label.setTextFormat(Qt.TextFormat.RichText)
        headline, color, caption = overview_stats.system_summary(healths)
        self.card_health.set_value(headline, caption, color)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Time-based captions ("3m ago", last-hour counts) and the decayed
        # risk score drift while the page is hidden -- recompute on re-entry,
        # then keep them fresh on a timer.
        self._tick()
        self.timer.start()

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def _tick(self) -> None:
        self._refresh_counts()
        self._refresh_score()
        if self._last_results:
            self.apply_status(self._last_results)
        self._fetch_redis()

    def _fetch_redis(self) -> None:
        """One off-thread round-trip to the edge session store for the two
        live cards (attackers diverted, pool state). Silently leaves the
        cards on their last value if the store is unreachable -- the page is
        a glanceable summary, not a place to surface redis errors."""
        if self._redis_busy:
            return
        self._redis_busy = True
        remote = target_for("edge", self.state).remote

        def work():
            return list_sessions(remote), pool_snapshot(remote)

        job = Job(work, self)
        self._jobs.add(job)

        def done(result, error):
            self._redis_busy = False
            self._jobs.discard(job)
            job.deleteLater()
            if error or result is None:
                self.card_diverted.set_value("—", "session store unreachable", GREY)
                self.card_pools.set_value("—", "session store unreachable", GREY)
                return
            sessions_text, pools_text = result
            self._render_diverted(session_view.parse_snapshot(sessions_text))
            self._render_pools(pool_view.parse_snapshot(pools_text))
        job.done.connect(done)
        job.start()

    def _render_diverted(self, sessions) -> None:
        n = overview_stats.unique_diverted_ips(sessions)
        self.card_diverted.set_value(
            str(n), f"{len(sessions)} active session(s)", RED if n else GREEN)

    def _render_pools(self, o: pool_view.PoolOverview) -> None:
        used = max(0, o.ready - o.free)
        preparing = len(o.building)
        self.card_pools.set_value(
            str(used), f"{o.free} available · {preparing} preparing",
            ORANGE if (used or preparing) else GREEN)

    def _on_event_added(self, event: PatternEvent, ts: int) -> None:
        self._add_event_item(event, ts)
        self._scroll_events_to_bottom()
        self._refresh_counts()
        self._refresh_score()

    def _on_score_changed(self, _score) -> None:
        # A fresh per-request score just landed; recompute the decayed
        # posture (which now includes it via the persisted history).
        self._refresh_score()

    def _refresh_score(self) -> None:
        """The headline risk is a decayed aggregate of recent notable
        activity (core/overview_stats.posture_score), not just the last
        request's raw score -- so it fades as attacks stop and climbs again
        when they resume. The latest raw request score is the caption."""
        score = overview_stats.posture_score(self.state.security_events)
        latest = self.feed.latest_score
        if score is None:
            caption = f"latest request: {latest}" if latest is not None else "no requests scored yet"
            self.card_score.set_value("—", caption, GREY)
            return
        band = ("honeypot threshold reached" if score >= _HONEYPOT_THRESHOLD
                else "elevated" if score >= _ELEVATED else "benign")
        caption = f"{band} · decayed from recent activity"
        if latest is not None:
            caption = f"{band} · latest request {latest}"
        self.card_score.set_value(str(score), caption, _score_color(score))

    def _refresh_counts(self) -> None:
        counts = overview_stats.event_window_counts(self.state.security_events)
        self.card_events.set_value(
            str(counts["window_total"]),
            f"last event {_ago(counts['last_timestamp'])}",
            ORANGE if counts["window_total"] else GREY)

    def _add_event_item(self, event: PatternEvent, ts: int) -> None:
        when = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "--:--:--"
        detail = f" — {event.detail}" if event.detail else ""
        item = QListWidgetItem(f"{when}   {event.label}{detail}")
        item.setForeground(_qcolor(event.color))
        self.events_list.addItem(item)
        # Keep the widget bounded the same way the feed caps its history.
        while self.events_list.count() > 200:
            self.events_list.takeItem(0)

    def _scroll_events_to_bottom(self) -> None:
        self.events_list.scrollToBottom()


def _qcolor(hex_color: str):
    from PyQt6.QtGui import QColor
    return QColor(hex_color or COLOR_HIGH)
