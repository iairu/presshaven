"""Ctrl+K command palette: a small frameless-style dialog with a search box
and a result list. Type to filter every page (and a few actions), Up/Down
to move, Enter to run, Esc to close. Ranking is core/palette.py; the
caller supplies the commands and a callback that executes the chosen one."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from core import palette


class CommandPalette(QDialog):
    def __init__(self, commands: list[palette.Command], on_run: Callable[[palette.Command], None],
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Command palette")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setModal(True)
        self.resize(520, 380)
        self._commands = commands
        self._on_run = on_run

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Go to a page or run an action…")
        self.search.textChanged.connect(self._refilter)
        self.search.returnPressed.connect(self._run_current)
        layout.addWidget(self.search)
        self.results = QListWidget()
        self.results.itemActivated.connect(lambda _item: self._run_current())
        layout.addWidget(self.results, stretch=1)
        hint = QLabel("↑↓ move · Enter open · Esc close")
        hint.setStyleSheet("color: #888888; font-size: 8pt;")
        layout.addWidget(hint)
        self.search.installEventFilter(self)
        self._refilter()

    def eventFilter(self, obj, event) -> bool:
        """Up/Down in the search box move the list selection."""
        from PyQt6.QtCore import QEvent
        if obj is self.search and event.type() == QEvent.Type.KeyPress:
            step = {Qt.Key.Key_Down: 1, Qt.Key.Key_Up: -1}.get(event.key())
            if step:
                row = self.results.currentRow() + step
                self.results.setCurrentRow(max(0, min(self.results.count() - 1, row)))
                return True
        return super().eventFilter(obj, event)

    def _refilter(self) -> None:
        self.results.clear()
        for c in palette.rank(self.search.text(), self._commands):
            item = QListWidgetItem(f"{c.title}    —    {c.group}" if c.group else c.title)
            item.setData(Qt.ItemDataRole.UserRole, c)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def _run_current(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        command = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        self._on_run(command)
