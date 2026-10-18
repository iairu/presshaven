"""Detection Policy page: the knobs that decide who gets diverted to the
honeypot, as a labelled form instead of raw .env text. Reads the edge
stack's .env (local, or fetched over SSH for a remote target), validates
each value (core/detection_policy.py), writes only the changed keys back
with every comment preserved, and can restart reverse_proxy so they take
effect (nginx reads these environment variables at startup).

A live sentence under the form explains what the current decay settings
mean for a maxed-out score, so the effect of a change is visible before
saving."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox, QFormLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from core import detection_policy as dp
from core.docker_ctl import targets_for
from core.env_upload import EnvUploadError, load_project_env, upload_env_text
from core.state import AppState
from ui.common import ErrorBanner, TargetSelector, confirm, muted_label, set_status
from ui.process_runner import LogPanel


class DetectionPage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._env = None
        self._widgets: dict[str, QCheckBox | QSpinBox] = {}

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Target:"))
        self.target_combo = TargetSelector(lambda: targets_for("edge", self.state))
        bar.addWidget(self.target_combo)
        self.reload_btn = QPushButton("Reload")
        bar.addWidget(self.reload_btn)
        bar.addStretch()
        layout.addLayout(bar)
        self.error_banner = ErrorBanner()
        layout.addWidget(self.error_banner)

        form_host = QWidget()
        form = QFormLayout(form_host)
        for knob in dp.KNOBS:
            if knob.kind == "bool":
                w = QCheckBox("enabled")
                w.toggled.connect(self._on_edited)
            else:
                w = QSpinBox()
                w.setRange(knob.minimum, knob.maximum)
                if knob.unit:
                    w.setSuffix(f" {knob.unit}")
                w.valueChanged.connect(self._on_edited)
            self._widgets[knob.key] = w
            form.addRow(f"{knob.label}:", w)
            form.addRow("", muted_label(f"{knob.help}  ({knob.key}, default {knob.default})"))
        layout.addWidget(form_host)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        layout.addWidget(muted_label(
            f"The honeypot threshold itself ({dp.HONEYPOT_THRESHOLD}) is fixed in the proxy's code, not a setting. "
            "Changes take effect when reverse_proxy restarts."))

        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_restart_btn = QPushButton("Save && restart reverse_proxy")
        self.defaults_btn = QPushButton("Restore defaults")
        self.defaults_btn.setToolTip("Set every field to its documented default (not saved until you Save)")
        self.status = QLabel("")
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.save_restart_btn)
        buttons.addWidget(self.defaults_btn)
        buttons.addWidget(self.status, stretch=1)
        layout.addLayout(buttons)

        self.restart_log = LogPanel(show_stop_button=False)
        self.restart_log.setMaximumHeight(120)
        layout.addWidget(self.restart_log)
        layout.addStretch()

        self.reload_btn.clicked.connect(lambda: self.reload(force=True))
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)
        self.save_btn.clicked.connect(lambda: self._save(restart=False))
        self.save_restart_btn.clicked.connect(lambda: self._save(restart=True))
        self.defaults_btn.clicked.connect(self._restore_defaults)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Don't wipe unsaved edits just because the user switched tabs and
        # came back -- only (re)load when there's nothing in progress.
        if self._env is None or not self._has_unsaved():
            self.reload()

    def _has_unsaved(self) -> bool:
        return self._env is not None and bool(dp.changes(self._env, self._form_values()))

    def _on_target_changed(self) -> None:
        if self._has_unsaved() and not confirm(
                self, "Discard changes?",
                "You have unsaved detection-policy changes. Switch target and discard them?"):
            return
        self.reload(force=True)

    def _restore_defaults(self) -> None:
        for key, w in self._widgets.items():
            knob = dp.KNOB_BY_KEY[key]
            w.blockSignals(True)
            if isinstance(w, QCheckBox):
                w.setChecked(knob.default == "true")
            else:
                w.setValue(int(knob.default))
            w.blockSignals(False)
        self._on_edited()

    def rebuild_targets(self) -> None:
        self.target_combo.rebuild()

    def _form_values(self) -> dict[str, str]:
        out = {}
        for key, w in self._widgets.items():
            out[key] = ("true" if w.isChecked() else "false") if isinstance(w, QCheckBox) else str(w.value())
        return out

    def reload(self, force: bool = False) -> None:
        if not force and self._has_unsaved():
            return
        remote = self.target_combo.current_remote()
        try:
            self._env = load_project_env("edge", remote)
            self.error_banner.set_error(None)
        except EnvUploadError as e:
            self._env = None
            self.error_banner.set_error(str(e), prefix="⚠ Could not read the edge .env: ")
            return
        values = dp.read_values(self._env)
        for key, w in self._widgets.items():
            w.blockSignals(True)
            if isinstance(w, QCheckBox):
                w.setChecked(values[key] == "true")
            else:
                w.setValue(int(values[key]))
            w.blockSignals(False)
        self._on_edited()
        set_status(self.status, "")

    def _on_edited(self, *_args) -> None:
        v = self._form_values()
        self.summary.setText(dp.decay_summary(v["THREAT_DECAY_ENABLED"] == "true",
                                              int(v["SCORE_DECAY_HALF_LIFE_SECONDS"])))
        if self._env is not None:
            n = len(dp.changes(self._env, v))
            set_status(self.status, f"{n} unsaved change(s)" if n else "")

    def _save(self, restart: bool) -> None:
        if self._env is None:
            self.reload()
            if self._env is None:
                return
        target = self.target_combo.current_target()
        try:
            diff = dp.apply_to(self._env, self._form_values())
            if diff:
                if target.is_remote:
                    upload_env_text(self._env.render(), "edge", target.remote)
                else:
                    self._env.save()
        except (ValueError, EnvUploadError, OSError) as e:
            QMessageBox.warning(self, "Save failed", str(e))
            return
        set_status(self.status, f"saved {len(diff)} change(s)" if diff else "nothing to save")
        if restart:
            argv, cwd = target.build("up", "-d", "--force-recreate", "reverse_proxy") \
                if diff else target.build("restart", "reverse_proxy")
            self.restart_log.run(argv, cwd)
