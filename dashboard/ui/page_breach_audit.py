"""Breach Validation page: run the attacker-perspective hardening audit
(core.breach_audit) against the live stack and export a PDF.

Where Attack Simulation (page_patterns) proves exploit traffic is diverted and
Segmentation Validation (page_pool_test) proves diverted sessions are isolated,
this page assumes the attacker has already won and tries to break the
containment: climb out of a honeypot container onto the production network,
reach production from the wrong side, or smuggle a honeypot target past the
whitelist onto production. Every probe is read-only; a blocked attempt is a
PASS.

The run happens off the GUI thread (docker exec / HTTP can be slow, especially
over SSH); results stream into a table as the categories complete, and the
"Export report (PDF)" button renders the same data through
core.breach_audit_pdf.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core import breach_audit
from core.breach_audit import (CATEGORY_LABELS, ERROR, FAIL, PASS, SKIP, WARN,
                               BreachAuditData, ProbeResult)
from core.docker_ctl import target_for
from core.state import AppState

_OUTCOME_COLOR = {
    PASS: "#2e7d32", FAIL: "#c62828", WARN: "#e08a00", SKIP: "#888888", ERROR: "#888888",
}
_OUTCOME_TEXT = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN", SKIP: "SKIP", ERROR: "ERROR"}


class _AuditJob(QThread):
    """Runs the (blocking) audit off the GUI thread, emitting progress lines as
    it goes and the finished BreachAuditData (or an error) at the end."""
    progress = pyqtSignal(str)
    done = pyqtSignal(object, str)

    def __init__(self, target, state, categories, parent=None):
        super().__init__(parent)
        self._target = target
        self._state = state
        self._categories = categories

    def run(self) -> None:
        try:
            data = breach_audit.run_audit(
                self._target, self._state, self._categories,
                log=lambda s: self.progress.emit(s))
            self.done.emit(data, "")
        except Exception as e:  # noqa: BLE001 -- surfaced to the GUI as text
            self.done.emit(None, str(e))


class BreachAuditPage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._job: _AuditJob | None = None
        self._data: BreachAuditData | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(
            "<b>Breach Validation.</b> Attacker's-eye scan of the hardening this "
            "platform ships. It assumes a honeypot container is already owned and "
            "tries to pivot out of it to production, the other pools, the Docker "
            "daemon and the internet, and it tries to smuggle a honeypot target "
            "past the edge whitelist onto production. Every probe is read-only &ndash; "
            "a blocked attempt is a <span style='color:#2e7d32;'>PASS</span>."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        cat_box = QGroupBox("Categories to scan")
        cat_layout = QVBoxLayout(cat_box)
        self._cat_checks: dict[str, QCheckBox] = {}
        for cat in breach_audit.ALL_CATEGORIES:
            cb = QCheckBox(CATEGORY_LABELS[cat])
            cb.setChecked(True)
            self._cat_checks[cat] = cb
            cat_layout.addWidget(cb)
        layout.addWidget(cat_box)

        controls = QHBoxLayout()
        self.run_btn = QPushButton("Run breach validation")
        self.run_btn.clicked.connect(self._run)
        controls.addWidget(self.run_btn)

        self.export_btn = QPushButton("Export report (PDF)")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export)
        controls.addWidget(self.export_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)   # busy indicator
        self.progress.hide()
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Result", "Category", "Probe", "Expected", "Evidence"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

    # -- target -------------------------------------------------------------

    def rebuild_targets(self) -> None:
        """Called when the remote settings change; the page always uses the
        single edge target (local, or the configured remote), so there is
        nothing to rebuild, but main_window calls this on every page."""

    def _target(self):
        return target_for("edge", self.state)

    # -- run ----------------------------------------------------------------

    def _run(self) -> None:
        if self._job is not None:
            return
        categories = [c for c, cb in self._cat_checks.items() if cb.isChecked()]
        if not categories:
            QMessageBox.information(self, "Nothing selected",
                                    "Select at least one category to scan.")
            return

        self.table.setRowCount(0)
        self._data = None
        self.export_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.progress.show()
        self.status_label.setText("Starting breach validation …")
        self.status_label.setStyleSheet("color: #888888;")

        self._job = _AuditJob(self._target(), self.state, categories, self)
        self._job.progress.connect(self._on_progress)
        self._job.done.connect(self._on_done)
        self._job.start()

    def _on_progress(self, line: str) -> None:
        self.status_label.setText(line)

    def _on_done(self, data, error: str) -> None:
        self.progress.hide()
        self.run_btn.setEnabled(True)
        self._job = None
        if error or data is None:
            self.status_label.setText(f"✗ Breach validation failed: {error}")
            self.status_label.setStyleSheet("color: #c62828;")
            return

        self._data = data
        self._fill_table(data)
        self.export_btn.setEnabled(True)
        status, summary = data.headline()
        color = "#c62828" if status.startswith("BREACH") else (
            "#e08a00" if "warning" in status.lower() else "#2e7d32")
        self.status_label.setText(f"{status}: {summary}")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _fill_table(self, data: BreachAuditData) -> None:
        # Failures first, then warnings, then the rest, so the eye lands on
        # anything that broke.
        order = {FAIL: 0, WARN: 1, ERROR: 2, SKIP: 3, PASS: 4}
        results = sorted(data.results, key=lambda r: order.get(r.outcome, 9))
        self.table.setRowCount(len(results))
        for row, r in enumerate(results):
            self._set(row, 0, _OUTCOME_TEXT.get(r.outcome, r.outcome.upper()),
                      _OUTCOME_COLOR.get(r.outcome))
            self._set(row, 1, CATEGORY_LABELS.get(r.category, r.category))
            probe = r.probe + (f"\n(from {r.source})" if r.source else "")
            self._set(row, 2, probe)
            self._set(row, 3, r.expectation)
            self._set(row, 4, r.evidence)
        self.table.resizeRowsToContents()

    def _set(self, row: int, col: int, text: str, color: str | None = None) -> None:
        item = QTableWidgetItem(text)
        if color:
            from PyQt6.QtGui import QColor
            item.setForeground(QColor(color))
            if col == 0:
                f = item.font()
                f.setBold(True)
                item.setFont(f)
        self.table.setItem(row, col, item)

    # -- export -------------------------------------------------------------

    def _export(self) -> None:
        if self._data is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save breach validation report", "breach_validation_report.pdf",
            "PDF files (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            from core.breach_audit_pdf import render_pdf
            render_pdf(self._data, path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(e))
            return
        QMessageBox.information(self, "Exported", f"Saved {path}")
