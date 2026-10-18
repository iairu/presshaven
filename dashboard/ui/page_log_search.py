"""Global log search: grep-style search across every configured target's
containers at once (both projects, local + remote), instead of only ever
being able to tail one service's log at a time on the Workloads page.

Runs `docker compose logs --tail=<N>` (no -f, no specific service -- every
container in that target's project, with --ansi always) per selected
target, filters the captured output by the search string, and shows
matching lines prefixed with which target they came from -- in real color,
via the same ANSI rendering ui/process_runner.LogPanel uses (ui/
ansi_render.py): docker compose colors each service's own prefix
differently when tailing multiple services combined, which is genuinely
useful for telling matches from different containers apart at a glance,
on top of whatever coloring the underlying app's own log lines carry.
Matching itself still runs against the ANSI-stripped text (so escape codes
can't hide/split a search term), only DISPLAY keeps the original codes.

Beyond plain substring search: a Regex toggle, a time range (docker's
--since), a history completer, named saved searches and export of the full
result set to text / JSON lines -- query logic is in core/log_query.py.

Runs in a background QThread (mirroring ui/status_poller.StatusPoller's own
reasoning) so a slow/unreachable remote target never freezes the UI.
"""
from __future__ import annotations

import re
import subprocess

from PyQt6.QtCore import QStringListModel, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QCompleter, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from core import log_query
from core.docker_ctl import Target, all_targets
from core.state import AppState
from ui import ansi_render, theme

MAX_DISPLAYED_MATCHES = 500

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class LogSearchWorker(QThread):
    results_ready = pyqtSignal(list, list)  # matching lines, errors

    def __init__(self, targets: list[Target], matcher, tail: int, since: str | None = None,
                 parent=None):
        super().__init__(parent)
        self._targets = targets
        self._matcher = matcher        # line -> bool, from core.log_query.compile_matcher
        self._tail = tail
        self._since = since

    def run(self) -> None:
        matches: list[str] = []
        errors: list[str] = []

        for target in self._targets:
            argv, cwd = target.build("logs", f"--tail={self._tail}", *log_query.since_args(self._since))
            try:
                result = subprocess.run(
                    argv, cwd=cwd, capture_output=True, text=True, timeout=30,
                )
            except (subprocess.TimeoutExpired, OSError) as e:
                errors.append(f"{target.label}: {e}")
                continue
            if result.returncode != 0 and not result.stdout:
                errors.append(f"{target.label}: {result.stderr.strip()[:200] or 'command failed'}")
                continue

            for line in result.stdout.splitlines():
                # Matching runs against the ANSI-stripped text so escape
                # codes can't hide/split the search term; the ORIGINAL line
                # (codes intact) is kept for display.
                if self._matcher(_ANSI_RE.sub("", line)):
                    matches.append(f"[{target.label}] {line}")
                    if len(matches) >= MAX_DISPLAYED_MATCHES:
                        self.results_ready.emit(matches, errors)
                        return

        self.results_ready.emit(matches, errors)


class LogSearchPage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._worker: LogSearchWorker | None = None
        self._target_checks: dict[str, QCheckBox] = {}
        # The last search's raw results, kept around so toggling
        # collapse_check re-renders instantly instead of re-running the
        # (possibly slow/remote) search.
        self._last_matches: list[str] = []
        self._last_errors: list[str] = []

        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Text to search for across every selected target's containers...")
        self.search_box.returnPressed.connect(self.run_search)
        search_row.addWidget(self.search_box, stretch=1)

        self.case_check = QCheckBox("Case sensitive")
        search_row.addWidget(self.case_check)
        self.regex_check = QCheckBox("Regex")
        self.regex_check.setToolTip("Treat the search as a regular expression (Python syntax)")
        search_row.addWidget(self.regex_check)
        self._history_model = QStringListModel(list(self.state.log_search_history))
        completer = QCompleter(self._history_model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_box.setCompleter(completer)

        # On by default -- a burst of the same repeated message (a crash-
        # looping container, a periodic job failing every cycle) is exactly
        # the "wall of identical lines burying everything else" problem
        # this page exists to cut through. Re-renders the already-fetched
        # results on toggle (see _render_results) rather than re-running
        # the search, so flipping it is instant.
        self.collapse_check = QCheckBox("Collapse repeated lines")
        self.collapse_check.setChecked(True)
        self.collapse_check.toggled.connect(self._render_results)
        search_row.addWidget(self.collapse_check)

        search_row.addWidget(QLabel("Lines/container:"))
        self.tail_spin = QSpinBox()
        self.tail_spin.setRange(100, 20000)
        self.tail_spin.setSingleStep(500)
        self.tail_spin.setValue(2000)
        search_row.addWidget(self.tail_spin)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.run_search)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("Time range:"))
        self.range_combo = QComboBox()
        for label, since in log_query.TIME_RANGES:
            self.range_combo.addItem(label, since)
        options_row.addWidget(self.range_combo)
        options_row.addSpacing(16)
        options_row.addWidget(QLabel("Saved:"))
        self.saved_combo = QComboBox()
        self.saved_combo.setMinimumWidth(180)
        self.saved_combo.activated.connect(self._load_saved)
        options_row.addWidget(self.saved_combo)
        self.save_btn = QPushButton("Save search…")
        self.save_btn.clicked.connect(self._save_current)
        options_row.addWidget(self.save_btn)
        self.delete_saved_btn = QPushButton("Delete")
        self.delete_saved_btn.clicked.connect(self._delete_saved)
        options_row.addWidget(self.delete_saved_btn)
        options_row.addStretch()
        self.export_btn = QPushButton("Export results…")
        self.export_btn.clicked.connect(self._export)
        options_row.addWidget(self.export_btn)
        layout.addLayout(options_row)
        self._refresh_saved()

        targets_row = QHBoxLayout()
        targets_row.addWidget(QLabel("Targets:"))
        self._targets_container = targets_row
        layout.addLayout(targets_row)
        self.rebuild_targets()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888888;")
        layout.addWidget(self.status_label)

        self.results = QPlainTextEdit(readOnly=True)
        self.results.setPlaceholderText("Results will appear here.")
        layout.addWidget(self.results, stretch=1)
        self._apply_theme_colors()
        theme.on_change(self._apply_theme_colors)

    def showEvent(self, event) -> None:
        """Retries the last search, but ONLY if it actually errored (e.g. a
        target was unreachable) -- if results are already showing cleanly,
        re-running an arbitrary `--tail=<N>` grep across every selected
        target (potentially over SSH) just because the user switched tabs
        would be wasted work at best and would blow away their current
        results/scroll position at worst. Only fires if there's still a
        query typed in and at least one target checked (both already
        implied by _last_errors being non-empty from a real prior search,
        but guarded explicitly in case targets were deselected since)."""
        super().showEvent(event)
        if self._last_errors and self.search_box.text().strip() and self._selected_targets():
            self.run_search()

    def rebuild_targets(self) -> None:
        """Call when remote settings change -- rebuilds the target
        checkbox list without losing which ones were already checked, for
        any target key that still exists after the change."""
        previously_checked = {key for key, cb in self._target_checks.items() if cb.isChecked()}

        while self._targets_container.count() > 1:  # keep the "Targets:" label
            item = self._targets_container.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self._target_checks.clear()

        for target in all_targets(self.state):
            cb = QCheckBox(target.label)
            cb.setChecked(target.key in previously_checked or not previously_checked)
            self._targets_container.addWidget(cb)
            self._target_checks[target.key] = cb
        self._targets_container.addStretch()

    def _apply_theme_colors(self) -> None:
        self.results.setStyleSheet(ansi_render.panel_stylesheet())

    def focus_search_box(self) -> None:
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _selected_targets(self) -> list[Target]:
        all_t = all_targets(self.state)
        return [t for t in all_t if self._target_checks.get(t.key) and self._target_checks[t.key].isChecked()]

    def run_search(self) -> None:
        query = self.search_box.text().strip()
        if not query:
            return
        try:
            matcher = log_query.compile_matcher(query, self.regex_check.isChecked(),
                                                self.case_check.isChecked())
        except log_query.QueryError as e:
            self.status_label.setText(str(e))
            return
        targets = self._selected_targets()
        if not targets:
            self.status_label.setText("No targets selected.")
            return

        if self._worker is not None and self._worker.isRunning():
            return  # a search is already in flight

        self.state.log_search_history = log_query.push_history(self.state.log_search_history, query)
        self._history_model.setStringList(self.state.log_search_history)
        self.state.save()

        self.search_btn.setEnabled(False)
        self.status_label.setText(f"Searching {len(targets)} target(s)...")
        self.results.clear()

        self._worker = LogSearchWorker(targets, matcher, self.tail_spin.value(),
                                       self.range_combo.currentData())
        self._worker.results_ready.connect(self._on_results)
        self._worker.start()

    # ---- saved searches / export ----

    def _refresh_saved(self) -> None:
        self.saved_combo.clear()
        self.saved_combo.addItem("— saved searches —")
        for entry in self.state.log_saved_searches:
            self.saved_combo.addItem(entry.get("name", "?"), entry)
        self.delete_saved_btn.setEnabled(bool(self.state.log_saved_searches))

    def _save_current(self) -> None:
        query = self.search_box.text().strip()
        name, ok = QInputDialog.getText(self, "Save search", "Name for this search:", text=query[:40])
        if not ok:
            return
        try:
            self.state.log_saved_searches = log_query.save_search(
                self.state.log_saved_searches, name, query, self.regex_check.isChecked(),
                self.case_check.isChecked(), self.range_combo.currentData())
        except log_query.QueryError as e:
            QMessageBox.warning(self, "Save search", str(e))
            return
        self.state.save()
        self._refresh_saved()
        self.saved_combo.setCurrentIndex(1)

    def _load_saved(self, index: int) -> None:
        entry = self.saved_combo.itemData(index)
        if not isinstance(entry, dict):
            return
        self.search_box.setText(entry.get("query", ""))
        self.regex_check.setChecked(bool(entry.get("regex")))
        self.case_check.setChecked(bool(entry.get("case")))
        idx = self.range_combo.findData(entry.get("since"))
        self.range_combo.setCurrentIndex(max(0, idx))
        self.run_search()

    def _delete_saved(self) -> None:
        entry = self.saved_combo.currentData()
        if not isinstance(entry, dict):
            return
        self.state.log_saved_searches = log_query.delete_search(self.state.log_saved_searches, entry["name"])
        self.state.save()
        self._refresh_saved()

    def _export(self) -> None:
        if not self._last_matches:
            QMessageBox.information(self, "Export", "Run a search with results first.")
            return
        path, chosen = QFileDialog.getSaveFileName(
            self, "Export search results", "log_search.txt",
            "Text (*.txt);;JSON lines (*.jsonl)")
        if not path:
            return
        as_json = path.endswith(".jsonl") or "jsonl" in chosen
        lines = self._last_matches          # every match, not just the collapsed view
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(log_query.export_jsonl(lines) if as_json else log_query.export_text(lines))
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self.status_label.setText(f"Exported {len(lines)} line(s) to {path}")

    def _on_results(self, matches: list[str], errors: list[str]) -> None:
        self.search_btn.setEnabled(True)
        self._last_matches = matches
        self._last_errors = errors
        self._render_results()

    @staticmethod
    def _collapse_repeated(lines: list[str]) -> list[str]:
        """Collapses RUNS of consecutive, identical lines into one, with a
        "(×N)" suffix -- classic `uniq -c` semantics, not a global/fuzzy
        dedup: two identical lines with other lines between them are left
        alone (that's a real recurrence pattern worth seeing, not noise),
        and lines are only ever equal here if they're byte-identical
        (target-label prefix included), so the same message from two
        different services never collapses together.
        """
        collapsed: list[str] = []
        prev: str | None = None
        run_len = 0
        for line in lines:
            if line == prev:
                run_len += 1
                continue
            if prev is not None:
                collapsed.append(prev if run_len == 1 else f"{prev}  (×{run_len})")
            prev = line
            run_len = 1
        if prev is not None:
            collapsed.append(prev if run_len == 1 else f"{prev}  (×{run_len})")
        return collapsed

    def _render_results(self) -> None:
        self.results.clear()
        matches = self._last_matches
        errors = self._last_errors

        display_lines = self._collapse_repeated(matches) if self.collapse_check.isChecked() else matches

        if not matches:
            self.results.setPlainText("(no matches)")
        else:
            default_color = ansi_render.panel_colors()[1]
            for line in display_lines:
                # Fresh parser per line, not one shared across the whole
                # result set -- each match is an independent line from
                # (possibly) a different container/point in time, so SGR
                # state from one match's colors must not bleed into the
                # next the way it correctly would within one continuous
                # live tail (ui/process_runner.LogPanel's own use case).
                ansi_render.append(self.results, ansi_render.make_parser(), line + "\n", default_color)

        status = f"{len(matches)} match(es)"
        if len(display_lines) != len(matches):
            status += f" ({len(display_lines)} shown, repeats collapsed)"
        if len(matches) >= MAX_DISPLAYED_MATCHES:
            status += f" (capped at {MAX_DISPLAYED_MATCHES}, refine your search)"
        if errors:
            status += " -- " + "; ".join(errors)
        self.status_label.setText(status)
