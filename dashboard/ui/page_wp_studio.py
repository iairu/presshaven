"""WordPress Studio -- edit the real shop, push changes to every honeypot.

Embeds the production wp-admin panel and, on demand, fans the editor's changes
out to every honeypot pool with a staged progress bar. The point of the page:
a single place to manage the WordPress + WooCommerce shop so that pages, posts,
products and safe settings stay identical between production and the decoys an
adversary lands in -- without ever copying user accounts, orders or any secret
(API keys, passwords, payment-gateway config).

Two moving parts keep the editing session safe:

  * The embedded browser injects X-Studio-Backend + the internal-test secret on
    every request, so nginx force-routes wp-admin to production and never
    diverts a live edit into a honeypot (see core.wp_studio.studio_headers and
    router_rules.is_studio_passthrough).
  * Propagation reuses the honeypot_content_sync service's replication script
    in `--once N` mode, so the dashboard runs the exact same allow-listed sync
    the periodic loop runs -- the "what is safe to copy" policy lives in one
    place (the script), not duplicated here.

Qt-free logic (which pools, the sync command, the URL/headers, the policy
text) lives in core.wp_studio and is unit-tested; this module is the thin Qt
adapter around it.
"""
from __future__ import annotations

import subprocess
import time

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QProgressBar,
                             QPushButton, QVBoxLayout, QWidget)

from core import wp_studio
from core.docker_ctl import target_for
from core.env_upload import EnvUploadError, load_project_env
from core.eta import EtaTracker, format_eta
from core.state import AppState
from ui import theme
from ui.browser_widget import BrowserWidget
from ui.common import ErrorBanner, muted_label

# A pool sync is a single scoped mysqldump+apply; generous ceiling so a slow
# disk or SSH link doesn't cut a legitimate sync short, but it never hangs the
# worker thread forever.
_SYNC_TIMEOUT_S = 180


def _edge_host(state: AppState) -> str:
    return state.remote_edge.host if state.remote_edge.is_configured() else "localhost"


class _StudioInterceptor(QWebEngineUrlRequestInterceptor):
    """Injects the studio passthrough headers on every request from the
    embedded admin browser, so nginx keeps it pinned to production. The secret
    can be refreshed (set_secret) once the edge .env has been read."""

    def __init__(self, secret: str, parent=None):
        super().__init__(parent)
        self._secret = secret or ""

    def set_secret(self, secret: str) -> None:
        self._secret = secret or ""

    def interceptRequest(self, info) -> None:  # noqa: N802 (Qt override)
        for name, value in wp_studio.studio_headers(self._secret).items():
            info.setHttpHeader(name.encode(), value.encode())


class _PoolRow(QWidget):
    """One pool's propagation status: a glyph + label, with an optional detail
    line (error text) when it fails. States: pending | active | done | failed."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 1, 0, 1)
        outer.setSpacing(1)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        self.glyph = QLabel("○")
        self.glyph.setFixedWidth(16)
        self.glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel(label)
        head.addWidget(self.glyph)
        head.addWidget(self.label)
        head.addStretch(1)
        outer.addLayout(head)
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        self.detail.setVisible(False)
        outer.addWidget(self.detail)
        self.set_state("pending")

    def set_state(self, state: str, detail: str = "") -> None:
        c = theme.scheme_colors()
        if state == "done":
            self.glyph.setText("✓")
            color, weight = c["success"], "600"
        elif state == "failed":
            self.glyph.setText("✗")
            color, weight = c["danger"], "600"
        elif state == "active":
            self.glyph.setText("▸")
            color, weight = c["accent"], "600"
        else:
            self.glyph.setText("○")
            color, weight = c["fg_muted"], "400"
        self.glyph.setStyleSheet(f"color: {color};")
        self.label.setStyleSheet(f"color: {color}; font-weight: {weight};")
        self.detail.setVisible(bool(detail))
        if detail:
            self.detail.setText(detail)
            self.detail.setStyleSheet(f"color: {c['fg_muted']}; font-size: 11px; padding-left: 22px;")


class _PropagationJob(QThread):
    """Runs the per-pool sync sequentially off the GUI thread. Emits a signal
    as each pool starts and finishes, plus one when the whole run is done, so
    the page can advance the progress bar and the per-pool rows live."""

    pool_started = pyqtSignal(int, int, int)       # pool, index (0-based), total
    pool_finished = pyqtSignal(int, int, bool, str)  # pool, index, ok, detail
    run_finished = pyqtSignal(int, int)            # succeeded, total

    def __init__(self, target, steps, parent=None):
        super().__init__(parent)
        self._target = target
        self._steps = steps

    def run(self) -> None:
        total = len(self._steps)
        succeeded = 0
        for i, step in enumerate(self._steps):
            self.pool_started.emit(step.pool, i, total)
            ok, detail = self._sync_one(step.pool)
            if ok:
                succeeded += 1
            self.pool_finished.emit(step.pool, i, ok, detail)
        self.run_finished.emit(succeeded, total)

    def _sync_one(self, pool: int) -> tuple[bool, str]:
        argv, cwd = wp_studio.sync_argv(self._target, pool)
        try:
            proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                  timeout=_SYNC_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return False, f"timed out after {_SYNC_TIMEOUT_S}s"
        except Exception as e:  # noqa: BLE001 -- surfaced to the GUI as text
            return False, str(e)
        if proc.returncode == 0:
            return True, ""
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, (detail[-1] if detail else f"exit {proc.returncode}")


class WpStudioPage(QWidget):
    """The WordPress Studio page: embedded production wp-admin + propagate."""

    # Ask MainWindow to trigger an immediate status poll once a run finishes.
    refresh_requested = pyqtSignal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._job: _PropagationJob | None = None
        self._propagating = False
        self._pool_rows: list[_PoolRow] = []
        self._run_t0 = 0.0
        self._eta = EtaTracker()
        self._secret_cache: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("WordPress Studio")
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        root.addWidget(title)
        root.addWidget(muted_label(
            "Edit the real shop below. Changes land in production; press "
            "“Propagate to honeypot pools” to mirror them into every decoy at "
            "once, so adversaries always see the same catalog your customers do."))

        self.error_banner = ErrorBanner()
        root.addWidget(self.error_banner)

        root.addWidget(self._build_policy_panel())

        # Toolbar: propagate button + status.
        bar = QHBoxLayout()
        self.propagate_btn = QPushButton("Propagate to honeypot pools")
        self.propagate_btn.setToolTip(
            "Mirror production's pages, posts, products and safe settings into "
            "every ready honeypot pool, right now.")
        self.propagate_btn.clicked.connect(self._start_propagation)
        bar.addWidget(self.propagate_btn)
        self.status_label = muted_label("")
        bar.addWidget(self.status_label, stretch=1)
        self.eta_label = muted_label("")
        bar.addWidget(self.eta_label)
        root.addLayout(bar)

        # Progress area (hidden until a run). Overall bar + per-pool rows.
        self.progress_box = QFrame()
        self.progress_box.setObjectName("studioProgress")
        pbl = QVBoxLayout(self.progress_box)
        pbl.setContentsMargins(8, 6, 8, 6)
        pbl.setSpacing(2)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        pbl.addWidget(self.progress_bar)
        self.pool_rows_box = QVBoxLayout()
        self.pool_rows_box.setContentsMargins(0, 0, 0, 0)
        self.pool_rows_box.setSpacing(0)
        pbl.addLayout(self.pool_rows_box)
        self.progress_box.setVisible(False)
        root.addWidget(self.progress_box)

        # The embedded admin browser, pinned to production via header injection.
        self._interceptor = _StudioInterceptor(self._internal_secret())
        self.browser = BrowserWidget(wp_studio.studio_url(_edge_host(self.state)),
                                     profile_name="wp-studio")
        self.browser.profile.setUrlRequestInterceptor(self._interceptor)
        root.addWidget(self.browser, stretch=1)

        if not self._internal_secret():
            self.error_banner.show_message(
                "INTERNAL_TEST_SECRET is not set on the edge stack, so the admin "
                "panel cannot be pinned to production and may be diverted into a "
                "honeypot while editing. Propagation still works.")

        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(1000)
        self._eta_timer.timeout.connect(self._tick_eta)

    # ---- helpers ----

    def _target(self):
        return target_for("edge", self.state)

    def _internal_secret(self) -> str:
        """The edge INTERNAL_TEST_SECRET (cached). Empty string if unreadable --
        the page degrades to an un-pinned admin panel and warns."""
        if self._secret_cache is not None:
            return self._secret_cache
        secret = ""
        try:
            env = load_project_env("edge", self._target().remote)
            secret = env.get("INTERNAL_TEST_SECRET", "").strip()
        except EnvUploadError:
            secret = ""
        self._secret_cache = secret
        return secret

    def _build_policy_panel(self) -> QWidget:
        """Two columns: what an edit carries to every pool, and what never
        leaves production. Mirrors core.wp_studio's allow/deny constants."""
        frame = QFrame()
        frame.setObjectName("studioPolicy")
        cols = QHBoxLayout(frame)
        cols.setContentsMargins(8, 6, 8, 6)
        cols.setSpacing(16)
        c = theme.scheme_colors()

        def column(heading: str, items, color: str) -> QWidget:
            box = QWidget()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(1)
            head = QLabel(heading)
            head.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 12px;")
            lay.addWidget(head)
            for it in items:
                row = QLabel(f"•  {it}")
                row.setWordWrap(True)
                row.setStyleSheet(f"color: {c['fg_muted']}; font-size: 12px;")
                lay.addWidget(row)
            lay.addStretch(1)
            return box

        cols.addWidget(column("Propagates to production + all pools",
                              wp_studio.PROPAGATES, c["success"]), stretch=1)
        cols.addWidget(column("Never leaves production",
                              wp_studio.NEVER_PROPAGATES, c["danger"]), stretch=1)
        return frame

    # ---- propagation ----

    def _start_propagation(self) -> None:
        if self._propagating:
            return
        self.error_banner.hide()
        pools = wp_studio.ready_pools(self._target().remote)
        steps = wp_studio.propagation_steps(pools)
        if not steps:
            self.error_banner.show_message("No honeypot pools to propagate to.")
            return

        # Build the per-pool rows fresh.
        for row in self._pool_rows:
            row.setParent(None)
        self._pool_rows = []
        for step in steps:
            row = _PoolRow(step.label)
            self._pool_rows.append(row)
            self.pool_rows_box.addWidget(row)

        self._propagating = True
        self.propagate_btn.setEnabled(False)
        self.progress_box.setVisible(True)
        self.progress_bar.setRange(0, len(steps))
        self.progress_bar.setValue(0)
        self.browser.set_dimmed(True, "Propagating to honeypot pools…")
        self.status_label.setText(f"Propagating to {len(steps)} pool(s)…")
        self._run_t0 = time.monotonic()
        self._eta.reset()
        self._eta_timer.start()

        self._job = _PropagationJob(self._target(), steps, self)
        self._job.pool_started.connect(self._on_pool_started)
        self._job.pool_finished.connect(self._on_pool_finished)
        self._job.run_finished.connect(self._on_run_finished)
        self._job.start()

    def _on_pool_started(self, pool: int, index: int, total: int) -> None:
        if 0 <= index < len(self._pool_rows):
            self._pool_rows[index].set_state("active")
        self.status_label.setText(f"Syncing honeypot pool {pool} ({index + 1} of {total})…")

    def _on_pool_finished(self, pool: int, index: int, ok: bool, detail: str) -> None:
        if 0 <= index < len(self._pool_rows):
            self._pool_rows[index].set_state("done" if ok else "failed", detail)
        done = index + 1
        self.progress_bar.setValue(done)
        total = self.progress_bar.maximum() or 1
        self._eta.update(time.monotonic() - self._run_t0, done / total)
        self._tick_eta()

    def _on_run_finished(self, succeeded: int, total: int) -> None:
        self._propagating = False
        self._eta_timer.stop()
        self.eta_label.setText("")
        self.propagate_btn.setEnabled(True)
        self.browser.set_dimmed(False)
        failed = total - succeeded
        if failed:
            self.status_label.setText(f"Propagated to {succeeded} of {total} pool(s) — {failed} failed.")
            self.error_banner.show_message(
                f"{failed} pool(s) did not sync. See the rows above for details.")
        else:
            self.status_label.setText(f"Propagated to all {total} pool(s).")
        self.refresh_requested.emit()

    def _tick_eta(self) -> None:
        if not self._propagating:
            return
        remaining = self._eta.remaining_at(time.monotonic() - self._run_t0)
        self.eta_label.setText(f"~ {format_eta(remaining)} left")
