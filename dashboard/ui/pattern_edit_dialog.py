"""Add / edit dialog for pattern plugins.

Covers the human-meaningful, editable fields of a pattern record (see
``core.pattern_registry.EDITABLE_FIELDS``). Everything a generator owns
(sources, signatures, Suricata SIDs, detection path) is shown read-only as
context but never edited here -- those come back from the sources on the next
``generate_pattern_catalog.py`` run, so editing them in the GUI would silently
be lost.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QPlainTextEdit, QVBoxLayout,
)

from ui import theme

_SEVERITIES = ("critical", "high", "medium", "low", "info")
_KINDS = (("cve", "CVE pattern"), ("generic", "Generic attack"),
          ("header", "Header rule"), ("upload", "Upload rule"), ("custom", "Custom"))
_SURFACES = (("frontend", "Frontend"), ("backend", "Backend"))
_COMPONENTS = (("core", "WordPress core"), ("plugin", "Plugin / theme"),
               ("custom", "Custom"))


class PatternEditDialog(QDialog):
    """Returns a dict of edited fields via :meth:`values` when accepted.

    ``pattern`` None means *add*; a dict means *edit* and pre-fills the form.
    ``generated`` True marks a generator-sourced pattern: its id is fixed and
    a banner explains that edits are stored as an overlay.
    """

    def __init__(self, parent=None, pattern: dict | None = None,
                 generated: bool = False):
        super().__init__(parent)
        self._pattern = pattern or {}
        self._generated = generated
        self.setWindowTitle("Edit pattern" if pattern else "Add pattern")
        self.setMinimumWidth(460)

        outer = QVBoxLayout(self)

        if generated:
            banner = QLabel(
                "This pattern comes from a rule source. Your edits are saved as "
                "an overlay in patterns/registry.json and can be reverted; the "
                "sources and detection path stay read-only.")
            banner.setWordWrap(True)
            banner.setStyleSheet(f"color: {theme.scheme_colors()['fg_muted']}; "
                                 f"font-size: 8.5pt;")
            outer.addWidget(banner)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.name_edit = QLineEdit(self._pattern.get("name", ""))
        form.addRow("Name", self.name_edit)

        self.id_edit = QLineEdit(self._pattern.get("id", ""))
        if pattern:
            self.id_edit.setReadOnly(True)
            self.id_edit.setToolTip("IDs are stable: deep links, exports and the "
                                    "enable/disable state all key on them.")
        else:
            self.id_edit.setPlaceholderText("auto from name if left blank")
        form.addRow("ID", self.id_edit)

        self.severity_combo = self._combo([(s, s.title()) for s in _SEVERITIES],
                                          self._pattern.get("severity", "medium"))
        form.addRow("Severity", self.severity_combo)
        self.kind_combo = self._combo(_KINDS, self._pattern.get("kind", "custom"),
                                      editable_key=True)
        form.addRow("Type", self.kind_combo)
        self.category_edit = QLineEdit(self._pattern.get("category", "custom"))
        form.addRow("Category", self.category_edit)
        self.component_combo = self._combo(_COMPONENTS,
                                           self._pattern.get("component", "custom"),
                                           editable_key=True)
        form.addRow("Component", self.component_combo)
        self.surface_combo = self._combo(_SURFACES,
                                         self._pattern.get("surface", "backend"))
        form.addRow("Surface", self.surface_combo)

        self.trigger_edit = QLineEdit(self._pattern.get("trigger", ""))
        self.trigger_edit.setPlaceholderText("the request string / signature that fires it")
        form.addRow("Trigger", self.trigger_edit)

        self.description_edit = QPlainTextEdit(self._pattern.get("description", ""))
        self.description_edit.setFixedHeight(70)
        form.addRow("Description", self.description_edit)

        self.notes_edit = QPlainTextEdit(self._pattern.get("notes", ""))
        self.notes_edit.setFixedHeight(54)
        form.addRow("Notes", self.notes_edit)

        outer.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _combo(self, options, current: str, editable_key: bool = False) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(editable_key)
        values = [v for v, _ in options]
        for value, label in options:
            combo.addItem(label, value)
        if current in values:
            combo.setCurrentIndex(values.index(current))
        elif editable_key and current:
            combo.setEditText(current)
        return combo

    def _combo_value(self, combo: QComboBox) -> str:
        if combo.isEditable() and combo.currentText() and \
                combo.currentText() != combo.currentData():
            data = combo.currentData()
            text = combo.currentText().strip()
            # An edited free-text entry wins only when it differs from the
            # selected row's label, so picking a listed option still works.
            label = combo.itemText(combo.currentIndex())
            return data if text == label else (text or data or "")
        return combo.currentData() or ""

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return
        self.accept()

    def values(self) -> dict:
        """The edited fields; id/name trimmed, blank id left for the registry
        to slug from the name."""
        return {
            "id": self.id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "severity": self.severity_combo.currentData() or "medium",
            "kind": self._combo_value(self.kind_combo) or "custom",
            "category": self.category_edit.text().strip() or "custom",
            "component": self._combo_value(self.component_combo) or "custom",
            "surface": self.surface_combo.currentData() or "backend",
            "trigger": self.trigger_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }
