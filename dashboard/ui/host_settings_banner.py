"""Banner for host settings a stack needs but the stack can't set itself
(core/host_settings.py): Redis' vm.overcommit_memory on the edge host,
Elasticsearch's vm.max_map_count on the SIEM host. Checked for every target
in use -- this machine and any remote server -- off the GUI thread (a remote
check goes over SSH), and shown above every page like DependencyBanner, with
the commands that fix it.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core import host_settings
from core.docker_ctl import Target, all_targets
from core.state import AppState
from ui import theme
from ui.common import clear_layout

# Re-check this often while the app runs (a server may be rebooted without
# its settings persisted).
RECHECK_MS = 15 * 60 * 1000


def targets_to_check(state: AppState) -> list[Target]:
    """Remote targets always; a local one when its project has no remote
    configured (so this machine is where that stack runs) or when the local
    stack has containers. Avoids warning about this machine's SIEM settings
    when the SIEM only ever runs on a remote server."""
    out = []
    targets = all_targets(state)
    remote_projects = {t.project for t in targets if t.is_remote}
    for t in targets:
        if t.is_remote or t.project not in remote_projects or t.ps(timeout=8.0):
            out.append(t)
    return out


class _CheckJob(QThread):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.result: list[tuple[Target, list[host_settings.Problem]]] = []

    def run(self) -> None:
        for t in targets_to_check(self._state):
            found = host_settings.target_problems(t)
            if found:   # None (unreachable) is the status poller's business
                self.result.append((t, found))


class HostSettingsBanner(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self._job: _CheckJob | None = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 10, 14, 10)
        self._layout.setSpacing(4)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setVisible(False)
        self._compact = False
        self._details: QWidget | None = None
        self._details_btn: QPushButton | None = None
        theme.on_change(self._apply_style)
        self._timer = QTimer(self)
        self._timer.setInterval(RECHECK_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        QTimer.singleShot(2000, self.refresh)   # after the window is up

    def _apply_style(self) -> None:
        if not self.isVisible():
            self.setStyleSheet("")
            return
        c = theme.scheme_colors()
        edge = c["warning"]
        self.setStyleSheet(
            f"HostSettingsBanner {{ background-color: {c['bg_alt']}; border: 1px solid {c['border']}; "
            f"border-left: 4px solid {edge}; }} "
            f"QLabel {{ color: {c['fg']}; background: transparent; }} "
            f"QLabel#BannerHeader {{ color: {edge}; font-weight: 700; }} "
            f"QLabel#BannerCommand {{ font-family: {theme.MONO_STACK}; background-color: {c['bg']}; "
            f"border: 1px solid {c['border']}; border-radius: 4px; padding: 6px; }}")

    def refresh(self) -> None:
        """Start a background check (no-op while one is running)."""
        if self._job is not None:
            return
        job = _CheckJob(self._state, self)
        self._job = job

        def done() -> None:
            self._job = None
            self._show(job.result)
            job.deleteLater()
        job.finished.connect(done)
        job.start()

    def _show(self, result: list[tuple[Target, list[host_settings.Problem]]]) -> None:
        clear_layout(self._layout)
        self._details = self._details_btn = None
        if not result:
            self.setVisible(False)
            self._apply_style()
            return
        self.setVisible(True)
        self._apply_style()

        hosts = ", ".join(t.label for t, _ in result)
        header_row = QHBoxLayout()
        header = QLabel(f"⚠ Host settings missing on {hosts} -- the stack runs, but these "
                        "kernel settings must be set on that machine itself:")
        header.setObjectName("BannerHeader")
        header.setWordWrap(True)
        header.setMinimumWidth(1)
        header_row.addWidget(header, stretch=1)
        self._details_btn = QPushButton()
        self._details_btn.clicked.connect(lambda: self.set_compact(not self._compact))
        header_row.addWidget(self._details_btn, alignment=Qt.AlignmentFlag.AlignTop)
        recheck = QPushButton("Recheck")
        recheck.clicked.connect(self.refresh)
        header_row.addWidget(recheck, alignment=Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(header_row)

        self._details = QWidget()
        details = QVBoxLayout(self._details)
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(4)
        for target, found in result:
            for p in found:
                line = QLabel(f"  •  {target.label}: {p.text()}")
                line.setWordWrap(True)
                details.addWidget(line)
            where = (f"on {target.remote.host} (over SSH)" if target.is_remote
                     else "on this machine")
            cmd = QLabel(f"Fix {where}, now and after reboots:\n"
                         + host_settings.fix_commands(found))
            cmd.setWordWrap(True)
            cmd.setObjectName("BannerCommand")
            cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            details.addWidget(cmd)
        self._layout.addWidget(self._details)
        self.set_compact(self._compact)

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        if self._details is not None:
            self._details.setVisible(not compact)
            self._details_btn.setText("Details" if compact else "Hide details")
