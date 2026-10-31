"""Target selector + "Apply to edge" strip shared by the URL Whitelist and
Honeypot Targets pages.

Both pages edit halves of ONE document (core/edge_policy.py build_payload),
so applying from either page pushes the whole current policy -- whitelist
and targets -- to the selected edge's Redis. The strip also shows whether
the edge is running what the dashboard has saved, with no policy at all
(the built-in defaults), or something else (edited elsewhere, or changes
here not applied yet)."""
from __future__ import annotations

import json
import time
from typing import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from core import edge_policy, redis_inspect
from core.docker_ctl import targets_for
from ui import theme
from ui.common import ErrorBanner, Job, TargetSelector, set_status


class EdgePolicyBar(QWidget):
    """``build_document`` returns the JSON text the edge should be running."""
    applied = pyqtSignal()

    def __init__(self, state, build_document: Callable[[], str], parent=None):
        super().__init__(parent)
        self._build_document = build_document
        self._jobs: set[Job] = set()
        self._edge_document: str | None = None
        self._edge_known = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(QLabel("Edge:"))
        self.target_combo = TargetSelector(lambda: targets_for("edge", state))
        outer.addWidget(self.target_combo)
        self.check_btn = QPushButton("Check edge")
        self.check_btn.setToolTip("Read the policy the selected edge is running")
        outer.addWidget(self.check_btn)
        self.apply_btn = QPushButton("Apply to edge")
        self.apply_btn.setToolTip(
            "Push the saved whitelist AND honeypot targets to the edge's Redis. "
            "Workers pick it up within ~5 s; no restart needed.")
        outer.addWidget(self.apply_btn)
        self.status = QLabel("")
        outer.addWidget(self.status, stretch=1)

        self.error_banner = ErrorBanner()

        self.check_btn.clicked.connect(self.check)
        self.apply_btn.clicked.connect(self.apply)
        self.target_combo.currentIndexChanged.connect(self.check)

    def rebuild_targets(self) -> None:
        self.target_combo.rebuild()

    def _run(self, fn, on_done) -> None:
        job = Job(fn, self)
        self._jobs.add(job)

        def finished(result, error):
            self._jobs.discard(job)
            on_done(result, error)
        job.done.connect(finished)
        job.start()

    def check(self) -> None:
        remote = self.target_combo.current_remote()
        set_status(self.status, "checking edge…")
        self._run(lambda: redis_inspect.get_edge_policy(remote), self._on_checked)

    def _on_checked(self, document, error: str) -> None:
        if error:
            self._edge_known = False
            self.error_banner.set_error(error, prefix="⚠ Could not read the edge policy: ")
            set_status(self.status, "")
            return
        self.error_banner.set_error(None)
        self._edge_document, self._edge_known = document, True
        self.refresh_sync()

    def refresh_sync(self) -> None:
        """Re-evaluate the in-sync label after a local edit (no edge round trip)."""
        if not self._edge_known:
            return
        if self._edge_document is None:
            set_status(self.status, "edge is running the built-in defaults (nothing applied yet)",
                       color=theme.scheme_colors()["warning"])
            return
        try:
            same = json.loads(self._edge_document) == json.loads(self._build_document())
        except (ValueError, TypeError):
            same = False
        if same:
            set_status(self.status, "edge is running this policy", color=theme.scheme_colors()["success"])
        else:
            set_status(self.status, "edge differs from this policy (not applied yet)", color=theme.scheme_colors()["warning"])

    def apply(self) -> None:
        remote = self.target_combo.current_remote()
        try:
            document = self._build_document()
        except Exception as e:  # noqa: BLE001 -- shown, never fatal
            set_status(self.status, f"could not build policy: {e}", color=theme.scheme_colors()["danger"])
            return
        set_status(self.status, "applying…")

        def work():
            redis_inspect.set_edge_policy(remote, document)
            return document

        def done(result, error):
            if error:
                self.error_banner.set_error(error, prefix="⚠ Could not apply the edge policy: ")
                set_status(self.status, "")
                return
            self.error_banner.set_error(None)
            self._edge_document, self._edge_known = result, True
            self.refresh_sync()
            self.applied.emit()
        self._run(work, done)


def seed_if_missing(remote, build_document: Callable[[], str] | None = None,
                    attempts: int = 10, delay: float = 3.0, sleep=time.sleep) -> bool:
    """After an edge start: push the saved policy when the edge's Redis has
    none yet (a fresh deploy or a purge), so it runs what the dashboard
    shows instead of the Lua built-in defaults. A policy already there is
    left alone -- it may have been applied on purpose. Retries while Redis
    is still coming up. True when it applied one."""
    build_document = build_document or current_document
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            if redis_inspect.get_edge_policy(remote) is not None:
                return False
            redis_inspect.set_edge_policy(remote, build_document())
            return True
        except redis_inspect.RedisInspectError as e:
            last = e
            if attempt < attempts - 1:
                sleep(delay)
    raise last


def current_document() -> str:
    """The policy document from the saved settings and the pattern registry."""
    return edge_policy.encode_payload(
        edge_policy.build_payload(edge_policy.EdgePolicySettings.load()))
