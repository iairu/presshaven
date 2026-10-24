"""WordPress Update -- check for and apply core + WooCommerce upgrades.

Checks whether a newer WordPress / WooCommerce is available and, on demand,
upgrades every instance behind a site-wide maintenance page. The update model
(confirmed with the operator) is "update production, then re-sync to pools":

  1. turn the maintenance page ON (a TTL-guarded Redis flag the edge serves a
     503 for -- see core.redis_inspect.set_maintenance + lua/maintenance.lua),
  2. update production's files + database,
  3. re-sync the updated files into every pool volume (init_setup's rsync),
  4. migrate each static pool's database,
  5. turn the maintenance page OFF.

The maintenance flag is cleared in a `finally`, and is TTL-guarded in Redis, so
the site always comes back -- even if a step fails or the dashboard dies
mid-update. Qt-free logic (check-JSON parsing, the compose commands, the plan)
lives in core.wp_update and is unit-tested; this is the thin Qt adapter.
"""
from __future__ import annotations

import subprocess
import time

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QProgressBar, QPushButton, QVBoxLayout, QWidget)

from core import redis_inspect, wp_update
from core.docker_ctl import target_for
from core.eta import EtaTracker, format_eta
from core.state import AppState
from ui import theme
from ui.common import ErrorBanner, muted_label

# Per-stage subprocess ceilings. Production downloads core + WooCommerce from
# wordpress.org so it gets the most generous cap; the file rsync and per-pool
# DB migrations are local and bounded. None of these should ever be hit on a
# healthy run -- they exist so a hung network call or disk can't wedge the
# worker thread (and thus the maintenance window) forever.
_TIMEOUT_CHECK_S = 120
_TIMEOUT_PRODUCTION_S = 900
_TIMEOUT_RESYNC_S = 300
_TIMEOUT_POOL_S = 300


def _last_line(text: str, fallback: str) -> str:
    lines = (text or "").strip().splitlines()
    return lines[-1] if lines else fallback


class _CheckJob(QThread):
    """Runs `update_wordpress.sh --check` against production off the GUI thread
    and parses the JSON into a wp_update.CheckResult."""

    done = pyqtSignal(object, str)  # CheckResult | None, error_text

    def __init__(self, target, parent=None):
        super().__init__(parent)
        self._target = target

    def run(self) -> None:
        argv, cwd = wp_update.check_argv(self._target)
        try:
            proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                  timeout=_TIMEOUT_CHECK_S)
        except subprocess.TimeoutExpired:
            self.done.emit(None, f"Version check timed out after {_TIMEOUT_CHECK_S}s.")
            return
        except Exception as e:  # noqa: BLE001 -- surfaced to the GUI as text
            self.done.emit(None, str(e))
            return
        if proc.returncode != 0:
            self.done.emit(None, _last_line(
                proc.stderr or proc.stdout, f"check exited {proc.returncode}"))
            return
        try:
            result = wp_update.parse_check(proc.stdout)
        except ValueError as e:
            self.done.emit(None, f"Could not read version info: {e}")
            return
        self.done.emit(result, "")


class _StepRow(QWidget):
    """One plan step's status: glyph + label + optional detail line.
    States: pending | active | done | failed."""

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


class _UpdateJob(QThread):
    """Runs the whole staged update off the GUI thread.

    Executes wp_update.update_steps() in order. Maintenance is turned on first
    (and, crucially, cleared in a `finally` so the site recovers no matter how
    the run ends). If maintenance can't be turned on, the run aborts BEFORE
    touching production -- never upgrade a live store without the curtain down.
    After maintenance is on, a failed step does not abort the run: the remaining
    instances are still brought forward and maintenance is still lifted, with
    the failures reported per-row.
    """

    step_started = pyqtSignal(int, int, str)        # index, total, label
    step_finished = pyqtSignal(int, bool, str)      # index, ok, detail
    run_finished = pyqtSignal(int, int, bool)       # succeeded, total, aborted

    def __init__(self, target, remote, steps, pools, parent=None):
        super().__init__(parent)
        self._target = target
        self._remote = remote
        self._steps = steps
        self._pools = pools

    def run(self) -> None:
        total = len(self._steps)
        succeeded = 0
        aborted = False
        maintenance_on = False
        try:
            for i, step in enumerate(self._steps):
                self.step_started.emit(i, total, step.label)

                if step.key == "maintenance_on":
                    ok, detail = self._maintenance_on()
                    maintenance_on = ok
                    self.step_finished.emit(i, ok, detail)
                    if ok:
                        succeeded += 1
                    else:
                        # Could not raise the curtain -- abort before production.
                        aborted = True
                        break
                    continue

                if step.key == "maintenance_off":
                    ok, detail = self._maintenance_off()
                    maintenance_on = not ok  # cleared on success
                    if ok:
                        succeeded += 1
                    self.step_finished.emit(i, ok, detail)
                    continue

                ok, detail = self._run_argv(step)
                if ok:
                    succeeded += 1
                self.step_finished.emit(i, ok, detail)
        finally:
            # Fail-safe: whatever happened above, make sure the site comes back.
            if maintenance_on:
                try:
                    redis_inspect.clear_maintenance(self._remote)
                except Exception:  # noqa: BLE001 -- best effort; TTL still covers us
                    pass
        self.run_finished.emit(succeeded, total, aborted)

    def _maintenance_on(self) -> tuple[bool, str]:
        try:
            redis_inspect.set_maintenance(self._remote, wp_update.MAINTENANCE_TTL)
        except Exception as e:  # noqa: BLE001
            return False, f"could not enable maintenance: {e}"
        # The edge mirrors the flag on a 5s timer; wait out the window so the
        # first update requests are already being held before we touch anything.
        time.sleep(wp_update.MAINTENANCE_GRACE_S)
        return True, ""

    def _maintenance_off(self) -> tuple[bool, str]:
        try:
            redis_inspect.clear_maintenance(self._remote)
        except Exception as e:  # noqa: BLE001
            return False, (f"could not disable maintenance: {e} -- it will clear "
                           f"on its own within {wp_update.MAINTENANCE_TTL}s")
        return True, ""

    def _argv_for(self, step):
        if step.key == "production":
            return wp_update.apply_production_argv(self._target), _TIMEOUT_PRODUCTION_S
        if step.key == "resync":
            return wp_update.resync_files_argv(self._target), _TIMEOUT_RESYNC_S
        if step.key.startswith("pool_"):
            pool = int(step.key.split("_", 1)[1])
            return wp_update.pool_db_update_argv(self._target, pool), _TIMEOUT_POOL_S
        return None, 0

    def _run_argv(self, step) -> tuple[bool, str]:
        built, timeout = self._argv_for(step)
        if built is None:
            return False, f"unknown step {step.key}"
        argv, cwd = built
        try:
            proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                  timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, f"timed out after {timeout}s"
        except Exception as e:  # noqa: BLE001
            return False, str(e)
        if proc.returncode == 0:
            return True, ""
        return False, _last_line(proc.stderr or proc.stdout, f"exit {proc.returncode}")


class WpUpdatePage(QWidget):
    """The WordPress Update page: check versions, then upgrade everything."""

    refresh_requested = pyqtSignal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._check_job: _CheckJob | None = None
        self._update_job: _UpdateJob | None = None
        self._running = False
        self._last_check: wp_update.CheckResult | None = None
        self._step_rows: list[_StepRow] = []
        self._weights: list[float] = []
        self._total_weight = 1.0
        self._done_weight = 0.0
        self._run_t0 = 0.0
        self._eta = EtaTracker()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("WordPress Update")
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        root.addWidget(title)
        root.addWidget(muted_label(
            "Check for newer WordPress core and WooCommerce releases and apply "
            "them to production and every honeypot pool at once, behind a "
            "maintenance page."))

        self.error_banner = ErrorBanner()
        root.addWidget(self.error_banner)

        root.addWidget(self._build_version_panel())
        root.addWidget(self._build_notice_panel())

        # Toolbar: check + update buttons, status, ETA.
        bar = QHBoxLayout()
        self.check_btn = QPushButton("Check for updates")
        self.check_btn.setToolTip("Query wordpress.org for the newest WordPress "
                                  "core and WooCommerce versions.")
        self.check_btn.clicked.connect(self._start_check)
        bar.addWidget(self.check_btn)

        self.update_btn = QPushButton("Update all instances")
        self.update_btn.setToolTip("Take the site into maintenance, update "
                                   "production, re-sync pools, migrate databases.")
        self.update_btn.clicked.connect(self._start_update)
        self.update_btn.setEnabled(False)
        bar.addWidget(self.update_btn)

        self.status_label = muted_label("")
        bar.addWidget(self.status_label, stretch=1)
        self.eta_label = muted_label("")
        bar.addWidget(self.eta_label)
        root.addLayout(bar)

        # Progress area (hidden until an update runs).
        self.progress_box = QFrame()
        self.progress_box.setObjectName("updateProgress")
        pbl = QVBoxLayout(self.progress_box)
        pbl.setContentsMargins(8, 6, 8, 6)
        pbl.setSpacing(2)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        pbl.addWidget(self.progress_bar)
        self.step_rows_box = QVBoxLayout()
        self.step_rows_box.setContentsMargins(0, 0, 0, 0)
        self.step_rows_box.setSpacing(0)
        pbl.addLayout(self.step_rows_box)
        self.progress_box.setVisible(False)
        root.addWidget(self.progress_box)

        root.addStretch(1)

        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(1000)
        self._eta_timer.timeout.connect(self._tick_eta)

    # ---- helpers ----

    def _target(self):
        return target_for("edge", self.state)

    def _build_version_panel(self) -> QWidget:
        """A small grid: component | installed | latest | status, filled in by
        a check. Starts with a prompt to run one."""
        frame = QFrame()
        frame.setObjectName("updateVersions")
        grid = QGridLayout(frame)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(4)
        c = theme.scheme_colors()

        heads = ["Component", "Installed", "Latest", "Status"]
        for col, h in enumerate(heads):
            lab = QLabel(h)
            lab.setStyleSheet(f"color: {c['fg_muted']}; font-weight: 700; font-size: 11px;")
            grid.addWidget(lab, 0, col)

        # Two value rows we update in place.
        self._ver_cells: dict[str, list[QLabel]] = {}
        for r, name in enumerate(("WordPress", "WooCommerce"), start=1):
            cells = []
            for col in range(4):
                lab = QLabel(name if col == 0 else "—")
                lab.setStyleSheet("font-size: 12px;")
                grid.addWidget(lab, r, col)
                cells.append(lab)
            self._ver_cells[name] = cells

        self._ver_hint = QLabel("Run a check to see available updates.")
        self._ver_hint.setStyleSheet(f"color: {c['fg_muted']}; font-size: 11px;")
        grid.addWidget(self._ver_hint, 3, 0, 1, 4)
        return frame

    def _build_notice_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("updateNotice")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        c = theme.scheme_colors()

        head = QLabel("Expected downtime")
        head.setStyleSheet(f"color: {c['accent']}; font-weight: 700; font-size: 12px;")
        lay.addWidget(head)

        notice = QLabel(wp_update.DOWNTIME_NOTICE)
        notice.setWordWrap(True)
        notice.setStyleSheet(f"color: {c['fg_muted']}; font-size: 12px;")
        lay.addWidget(notice)

        for item in wp_update.WHAT_UPDATES:
            row = QLabel(f"•  {item}")
            row.setWordWrap(True)
            row.setStyleSheet(f"color: {c['fg_muted']}; font-size: 12px;")
            lay.addWidget(row)

        limit = QLabel(wp_update.POOL_LIMITATION)
        limit.setWordWrap(True)
        limit.setStyleSheet(f"color: {c['fg_muted']}; font-size: 11px; font-style: italic;")
        lay.addWidget(limit)
        return frame

    # ---- check ----

    def _start_check(self) -> None:
        if self._running:
            return
        self.error_banner.hide()
        self.check_btn.setEnabled(False)
        self.status_label.setText("Checking for updates…")
        self._check_job = _CheckJob(self._target(), self)
        self._check_job.done.connect(self._on_check_done)
        self._check_job.start()

    def _on_check_done(self, result, error: str) -> None:
        self.check_btn.setEnabled(True)
        if result is None:
            self.status_label.setText("")
            self.error_banner.show_message(f"Update check failed: {error}")
            return
        if not result.ok:
            self.status_label.setText("")
            self.error_banner.show_message(
                f"WordPress is not ready to update ({result.error}).")
            self.update_btn.setEnabled(False)
            return

        self._last_check = result
        c = theme.scheme_colors()
        for comp in result.components:
            cells = self._ver_cells.get(comp.name)
            if not cells:
                continue
            cells[1].setText(comp.installed or "—")
            cells[2].setText(comp.latest or "—")
            if comp.update_available:
                cells[3].setText(f"update → {comp.latest}")
                cells[3].setStyleSheet(f"color: {c['accent']}; font-weight: 700; font-size: 12px;")
            else:
                cells[3].setText("up to date")
                cells[3].setStyleSheet(f"color: {c['success']}; font-size: 12px;")

        if result.errors:
            self._ver_hint.setText(
                "Note: " + "; ".join(result.errors)
                + " (wordpress.org may be unreachable from the stack).")
        else:
            self._ver_hint.setText("")

        if result.any_update_available:
            self.status_label.setText("Updates available.")
            self.update_btn.setEnabled(True)
        else:
            self.status_label.setText("Everything is up to date.")
            self.update_btn.setEnabled(False)

    # ---- update ----

    def _start_update(self) -> None:
        if self._running:
            return
        self.error_banner.hide()
        pools = wp_update.updatable_pools()
        steps = wp_update.update_steps(pools)

        for row in self._step_rows:
            row.setParent(None)
        self._step_rows = []
        for step in steps:
            row = _StepRow(step.label)
            self._step_rows.append(row)
            self.step_rows_box.addWidget(row)

        self._weights = [max(0.01, s.weight) for s in steps]
        self._total_weight = sum(self._weights) or 1.0
        self._done_weight = 0.0

        self._running = True
        self.check_btn.setEnabled(False)
        self.update_btn.setEnabled(False)
        self.progress_box.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting update…")
        self._run_t0 = time.monotonic()
        self._eta.reset()
        self._eta_timer.start()

        self._update_job = _UpdateJob(
            self._target(), self._target().remote, steps, pools, self)
        self._update_job.step_started.connect(self._on_step_started)
        self._update_job.step_finished.connect(self._on_step_finished)
        self._update_job.run_finished.connect(self._on_run_finished)
        self._update_job.start()

    def _on_step_started(self, index: int, total: int, label: str) -> None:
        if 0 <= index < len(self._step_rows):
            self._step_rows[index].set_state("active")
        self.status_label.setText(f"{label} ({index + 1} of {total})…")

    def _on_step_finished(self, index: int, ok: bool, detail: str) -> None:
        if 0 <= index < len(self._step_rows):
            self._step_rows[index].set_state("done" if ok else "failed", detail)
        if 0 <= index < len(self._weights):
            self._done_weight += self._weights[index]
        frac = min(1.0, self._done_weight / self._total_weight)
        self.progress_bar.setValue(int(frac * 1000))
        self._eta.update(time.monotonic() - self._run_t0, frac)
        self._tick_eta()

    def _on_run_finished(self, succeeded: int, total: int, aborted: bool) -> None:
        self._running = False
        self._eta_timer.stop()
        self.eta_label.setText("")
        self.check_btn.setEnabled(True)
        failed = total - succeeded
        if aborted:
            self.status_label.setText("Update aborted before production was touched.")
            self.error_banner.show_message(
                "Could not enable the maintenance page, so the update was not "
                "started — production was left untouched. See the step above.")
        elif failed:
            self.status_label.setText(f"Update finished with {failed} problem(s).")
            self.error_banner.show_message(
                f"{failed} step(s) did not complete. See the rows above. The "
                "maintenance page has been lifted.")
        else:
            self.status_label.setText("Update complete. Maintenance lifted.")
            self.progress_bar.setValue(1000)
        # Re-check so the version panel reflects the new state.
        self.refresh_requested.emit()
        if not aborted:
            self._start_check()

    def _tick_eta(self) -> None:
        if not self._running:
            return
        remaining = self._eta.remaining_at(time.monotonic() - self._run_t0)
        self.eta_label.setText(f"~ {format_eta(remaining)} left")
