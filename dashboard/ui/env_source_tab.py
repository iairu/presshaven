"""Connectors & Config page tab for one project's .env: a Local/Remote toggle that
swaps the SOURCE of the same EnvEditorWidget between the real local file
and the one fetched live from the configured remote host over SSH. Save
writes back to whichever source is currently selected. Companion to the
wizard's RemoteAwareEnvPage (same underlying core.env_upload functions),
but reachable anytime afterward rather than only during first-run setup,
and switchable back and forth without leaving the page.

For the ids project it also covers secret hygiene (core/env_secrets.py):
"Generate weak secrets" fills every placeholder/weak secret in the form,
"Restore backup…" puts a .env.bak.* back, a local Save that changes a secret
backs the file up first, and a warning line lists what is still a placeholder.
"""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from core import env_secrets

from core.docker_ctl import Target
from core.env_file import EnvFile, merge_example_keys, seed_from_example
from core.env_upload import EnvUploadError, download_env_text, upload_env_text
from core.state import RemoteConfig
from ui.env_editor import EnvEditorWidget, looks_like_secret

_SOURCE_LOCAL = "local"
_SOURCE_REMOTE = "remote"


class EnvSourceTab(QWidget):
    def __init__(
        self, project: str, local_path: Path, local_example: Path,
        get_remote_config, parent=None,
    ):
        super().__init__(parent)
        self.project = project
        self.local_path = local_path
        self.local_example = local_example
        self._get_remote_config = get_remote_config  # callable -> RemoteConfig, read fresh each time

        self.env_file: EnvFile | None = None
        self.editor: EnvEditorWidget | None = None
        self._source_is_remote = False

        layout = QVBoxLayout(self)

        toggle_row = QHBoxLayout()
        toggle_row.addWidget(QLabel("Editing:"))
        self.source_combo = QComboBox()
        self.source_combo.addItem("Local .env", _SOURCE_LOCAL)
        self.source_combo.addItem("Remote .env (fetched live via SSH)", _SOURCE_REMOTE)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        toggle_row.addWidget(self.source_combo)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Re-fetch from the current source, discarding unsaved edits here.")
        self.refresh_btn.clicked.connect(self._reload_current_source)
        toggle_row.addWidget(self.refresh_btn)
        toggle_row.addStretch()

        # The generation rules know the ids stack's secrets only.
        self._secret_tools = project == "edge"
        self.generate_btn = QPushButton("Generate weak secrets")
        self.generate_btn.setToolTip(
            "Fill every secret that is missing, a placeholder, the .env.example value "
            "or too short with a strong random value (database passwords, Redis, salts, "
            "signing keys, admin passwords, GDPR key). Values stay hidden; press Save to "
            "write them, then Redeploy on the Workloads page.")
        self.generate_btn.clicked.connect(self._generate_weak_secrets)
        self.generate_btn.setVisible(self._secret_tools)
        toggle_row.addWidget(self.generate_btn)
        self.restore_btn = QPushButton("Restore backup…")
        self.restore_btn.setToolTip(
            "Put a .env.bak.* backup back as the local .env (the current file is "
            "backed up first).")
        self.restore_btn.clicked.connect(self._restore_backup)
        toggle_row.addWidget(self.restore_btn)
        layout.addLayout(toggle_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #888888;")
        layout.addWidget(self.status_label)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #e0a800;")
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

        self._editor_slot = QVBoxLayout()
        layout.addLayout(self._editor_slot, stretch=1)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn)

        self._load_local()
        self.refresh_remote_availability()

    def refresh_remote_availability(self) -> None:
        """Call after remote settings change elsewhere (Settings' own
        remote tabs) so the Remote option's availability -- and the
        currently-shown content, if it's already on Remote -- stays
        correct without needing to reopen this tab."""
        remote = self._get_remote_config()
        configured = remote.is_configured()

        model = self.source_combo.model()
        remote_item = model.item(1)
        if remote_item:
            remote_item.setEnabled(configured)

        if not configured and self.source_combo.currentData() == _SOURCE_REMOTE:
            self.source_combo.setCurrentIndex(0)  # falls back to Local via the signal

    def _clear_editor(self) -> None:
        while self._editor_slot.count():
            item = self._editor_slot.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_source_changed(self, _index: int) -> None:
        if self.source_combo.currentData() == _SOURCE_REMOTE:
            self._load_remote()
        else:
            self._load_local()

    def _reload_current_source(self) -> None:
        if self.source_combo.currentData() == _SOURCE_REMOTE:
            self._load_remote()
        else:
            self._load_local()

    def _show_editor(self) -> None:
        self._clear_editor()
        self.editor = EnvEditorWidget(self.env_file)
        self._editor_slot.addWidget(self.editor)
        self.restore_btn.setEnabled(not self._source_is_remote)
        self._update_warnings()

    def _update_warnings(self) -> None:
        """Placeholder/weak settings in the file as loaded or last saved."""
        warnings = (env_secrets.config_warnings(self.env_file, self.local_example)
                    if self._secret_tools and self.env_file is not None else [])
        self.warning_label.setText("\n".join(f"⚠ {w}" for w in warnings))
        self.warning_label.setVisible(bool(warnings))

    def _load_local(self) -> None:
        self._source_is_remote = False
        self.env_file = seed_from_example(self.local_path, self.local_example)
        self._show_editor()
        self.status_label.setText(
            f"Editing local file: {self.local_path}" + self._added_keys_note()
        )
        self.status_label.setStyleSheet("color: #888888;")

    def _added_keys_note(self) -> str:
        """Suffix for the status line naming keys that .env.example has
        but the loaded file doesn't (they're in the form with template
        defaults, and get written on Save)."""
        added = self.env_file.added_keys if self.env_file else []
        if not added:
            return ""
        return (
            f"\nNot in this file yet, added from .env.example (saved on Save): "
            + ", ".join(added)
        )

    def _load_remote(self) -> None:
        remote = self._get_remote_config()
        if not remote.is_configured():
            QMessageBox.warning(
                self, "Remote not configured",
                "Configure and test this project's remote connection "
                "first (Settings → remote tab, or the wizard).",
            )
            self.source_combo.blockSignals(True)
            self.source_combo.setCurrentIndex(0)
            self.source_combo.blockSignals(False)
            self._load_local()
            return

        self._clear_editor()
        remote_env_path = Target(project=self.project, remote=remote).remote_env_path()
        self.status_label.setText(f"Fetching {remote_env_path} from {remote.user}@{remote.host}…")
        self.status_label.setStyleSheet("color: #888888;")
        self.repaint()

        try:
            text = download_env_text(self.project, remote)
        except EnvUploadError as e:
            QMessageBox.warning(self, "Fetch failed", str(e))
            self.source_combo.blockSignals(True)
            self.source_combo.setCurrentIndex(0)
            self.source_combo.blockSignals(False)
            self._load_local()
            return

        self._source_is_remote = True
        display_path = Path(f"{remote.user}@{remote.host}:{remote_env_path}")
        self.env_file = EnvFile.from_text(text, display_path)
        # The template is part of this repo, so it describes what the
        # remote deployment of the same code needs too -- an empty remote
        # file becomes the full template, an old one gains new keys.
        self.env_file.added_keys = merge_example_keys(self.env_file, self.local_example)
        self._show_editor()

        if text:
            self.status_label.setText(
                f"Editing REMOTE file: {remote.user}@{remote.host}:{remote_env_path}"
                + self._added_keys_note()
            )
        else:
            self.status_label.setText(
                f"No .env found yet at {remote.user}@{remote.host}:"
                f"{remote_env_path} -- starting from the .env.example "
                "template; Save will create it there."
            )
        self.status_label.setStyleSheet("color: #5cb85c;")

    def _generate_weak_secrets(self) -> None:
        """Replace every weak secret in the form (not on disk until Save).
        Reports key names only; the values stay masked in their fields."""
        self.editor.apply_to_env_file()
        try:
            plan = env_secrets.secret_plan(self.env_file, self.local_example)
        except Exception as e:  # noqa: BLE001 -- e.g. openssl missing for the GDPR key
            QMessageBox.warning(self, "Generate weak secrets", f"Could not generate secrets: {e}")
            return
        if not plan:
            QMessageBox.information(self, "Generate weak secrets",
                                    "Every secret is already strong -- nothing to change.")
            return
        for key, value in plan.items():
            self.env_file.set(key, value)
        self._show_editor()
        generated = [k for k, v in plan.items() if v]
        cleared = [k for k, v in plan.items() if not v]
        text = ""
        if generated:
            text += "Generated: " + ", ".join(generated) + "\n\n"
        if cleared:
            text += ("Cleared (placeholder external credential, that integration is "
                     "now off until you enter a real one): " + ", ".join(cleared) + "\n\n")
        QMessageBox.information(
            self, "Generate weak secrets",
            text + "Not written yet: press Save (the current file is backed up first). "
            "Then use Redeploy on the Workloads page so every container -- databases "
            "included -- switches to the new values. Everyone gets logged out.")

    def _restore_backup(self) -> None:
        backups = env_secrets.list_backups(self.local_path)
        if not backups:
            QMessageBox.information(self, "Restore backup",
                                    f"No .env.bak.* backups next to {self.local_path}.")
            return
        name, ok = QInputDialog.getItem(
            self, "Restore backup",
            f"Replace {self.local_path} with (newest first):",
            [b.name for b in backups], 0, False)
        if not ok:
            return
        chosen = self.local_path.parent / name
        try:
            previous = env_secrets.restore(self.local_path, chosen)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Restore backup", f"Restore failed: {e}")
            return
        self._load_local()
        QMessageBox.information(
            self, "Restore backup",
            f"Restored {name}."
            + (f" The file it replaced was saved as {previous.name}." if previous else "")
            + "\n\nRunning containers still use whatever they were started with: "
              "Redeploy on the Workloads page to apply it.")

    def _changed_secrets_on_disk(self) -> list[str]:
        """Secret keys whose value in the form differs from the local file."""
        if not self.local_path.exists():
            return []
        disk = EnvFile.load(self.local_path)
        return [k for k in self.env_file.keys()
                if looks_like_secret(k) and k in disk.keys() and disk.get(k) != self.env_file.get(k)]

    def _save(self) -> None:
        self.editor.apply_to_env_file()
        if self._source_is_remote:
            remote = self._get_remote_config()
            try:
                upload_env_text(self.env_file.render(), self.project, remote)
            except EnvUploadError as e:
                QMessageBox.warning(self, "Save to remote failed", str(e))
                return
            remote_env_path = Target(project=self.project, remote=remote).remote_env_path()
            QMessageBox.information(
                self, "Saved",
                f"Saved to {remote.user}@{remote.host}:{remote_env_path}",
            )
        else:
            changed = self._changed_secrets_on_disk()
            note = ""
            if changed:
                try:
                    note = f"\n\nPrevious file backed up as {env_secrets.backup(self.local_path).name}."
                except OSError as e:
                    if not confirm_unbacked(self, e):
                        return
                note += (f"\nChanged secrets: {', '.join(changed)}. Redeploy on the Workloads "
                         "page to apply them (databases switch their passwords on that restart).")
            self.env_file.save()
            os.chmod(self.local_path, 0o600)   # it holds every credential of the stack
            QMessageBox.information(self, "Saved", f"Saved {self.local_path}" + note)
        self._update_warnings()


def confirm_unbacked(parent, error: Exception) -> bool:
    return QMessageBox.question(
        parent, "Backup failed",
        f"Could not back up the current .env ({error}). Save anyway?",
    ) == QMessageBox.StandardButton.Yes
