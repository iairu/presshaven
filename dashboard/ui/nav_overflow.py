"""Drag-and-drop navigation widgets.

The rail's category "⋮" used to open a native QMenu. A menu closes itself as
soon as a drag leaves it, so it cannot be a useful drop target. This module
replaces it with a small persistent side panel -- visually a menu, but a real
QWidget -- plus the two QListWidget subclasses that carry page drags between
the panel and the rail.

Drags stay inside one category. PAGE_GROUP (and therefore the breadcrumb)
treats a page's category as fixed; moving a page across sections would make
those mappings lie. Reordering and moving between a category's rail rows and
its overflow panel are both supported.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QMimeData, QModelIndex, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QDrag, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QToolButton,
    QVBoxLayout, QWidget,
)

PAGE_MIME = "application/x-honeypot-nav-page"

# Item data roles. The header rows in the rail carry GROUP_ROLE but no
# PAGE_ROLE, which is how drop handling tells a section label from a page.
PAGE_ROLE = Qt.ItemDataRole.UserRole
GROUP_ROLE = Qt.ItemDataRole.UserRole + 1

_DRAG_ICON_SIZE = 24


def make_page_item(page_id: str, label: str, group: str, icon: QIcon | None = None,
                   tooltip: str = "", row_height: int = 30) -> QListWidgetItem:
    item = QListWidgetItem(label)
    item.setData(PAGE_ROLE, page_id)
    item.setData(GROUP_ROLE, group)
    item.setSizeHint(QSize(0, row_height))
    if icon is not None and not icon.isNull():
        item.setIcon(icon)
    if tooltip:
        item.setToolTip(tooltip)
    return item


def payload_from_mime(mime: QMimeData) -> tuple[str, str] | None:
    """Return (source group, page id) from one of our page drags."""
    if not mime.hasFormat(PAGE_MIME):
        return None
    try:
        raw = bytes(mime.data(PAGE_MIME)).decode("utf-8")
        group, page_id = raw.split("\n", 1)
    except (UnicodeDecodeError, ValueError):
        return None
    return (group, page_id) if group and page_id else None


class NavGroupHeader(QWidget):
    """A category label plus its "⋮" button, and a drop target for the
    section's empty/header row.

    Without accepting drops here, a section whose pages have all moved to
    overflow would have no page row left to drop a page back onto -- the
    header is then the only visible target.
    """

    moreClicked = pyqtSignal()
    pageDropped = pyqtSignal(str, str, str, str, int)

    def __init__(self, group: str, parent=None):
        super().__init__(parent)
        self.group = group
        self.setObjectName("NavGroupHeader")
        self.setAcceptDrops(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 8, 0)
        layout.setSpacing(4)
        label = QLabel(group.upper())
        label.setObjectName("NavGroupTitle")
        # The label never needs mouse input; letting events through makes
        # the whole header row a reliable drop target.
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addStretch(1)
        self.more = QToolButton()
        self.more.setObjectName("NavMore")
        self.more.setText("⋮")
        self.more.setToolTip(f"More {group} pages")
        self.more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more.setAutoRaise(True)
        self.more.setFixedSize(22, 22)
        self.more.clicked.connect(lambda _checked=False: self.moreClicked.emit())
        layout.addWidget(self.more, alignment=Qt.AlignmentFlag.AlignBottom)

    def dragEnterEvent(self, event) -> None:
        if payload_from_mime(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        payload = payload_from_mime(event.mimeData())
        if payload is not None and payload[0] == self.group:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        payload = payload_from_mime(event.mimeData())
        if payload is None or payload[0] != self.group:
            event.ignore()
            return
        source_group, page_id = payload
        # The header means "top of this section's visible rows".
        self.pageDropped.emit(page_id, source_group, self.group, "visible", 0)
        event.acceptProposedAction()


class _PageDragList(QListWidget):
    """Shared drag source/drop target behaviour for rail and panel lists."""

    pageDropped = pyqtSignal(str, str, str, str, int)
    # page_id, source group, target group, target list ("visible"/"overflow"), index

    def __init__(self, source: str, parent=None):
        super().__init__(parent)
        self._source = source
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setIconSize(QSize(18, 18))
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._drag_start_item: QListWidgetItem | None = None
        self._drag_start_recorded = False

    # -- drag source -------------------------------------------------

    def mousePressEvent(self, event) -> None:
        # Remember the row the drag actually started on. currentItem() can
        # point at the previously selected page when the press lands on a
        # non-selectable section header.
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_item = self.itemAt(event.position().toPoint())
            self._drag_start_recorded = True
        else:
            self._drag_start_item = None
            self._drag_start_recorded = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start_item = None
        self._drag_start_recorded = False
        super().mouseReleaseEvent(event)

    def startDrag(self, supported_actions) -> None:
        if self._drag_start_recorded:
            item = self._drag_start_item
        else:
            item = self.itemAt(self.viewport().mapFromGlobal(QCursor.pos()))
        self._drag_start_item = None
        self._drag_start_recorded = False
        if item is None:
            return
        page_id = item.data(PAGE_ROLE)
        group = item.data(GROUP_ROLE)
        if not page_id or not group:
            return
        mime = QMimeData()
        mime.setData(PAGE_MIME, f"{group}\n{page_id}".encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        icon = item.icon()
        if not icon.isNull():
            drag.setPixmap(icon.pixmap(_DRAG_ICON_SIZE, _DRAG_ICON_SIZE))
            drag.setHotSpot(QPoint(_DRAG_ICON_SIZE // 2, _DRAG_ICON_SIZE // 2))
        drag.exec(Qt.DropAction.MoveAction)

    # -- drop target -------------------------------------------------

    def _payload(self, mime: QMimeData) -> tuple[str, str] | None:
        return payload_from_mime(mime)

    def _drop_target(self, pos: QPoint) -> tuple[str, int] | None:
        raise NotImplementedError

    def _valid_drop(self, event) -> tuple[str, str, str, int] | None:
        payload = self._payload(event.mimeData())
        if payload is None:
            return None
        source_group, page_id = payload
        target = self._drop_target(event.position().toPoint())
        if target is None:
            return None
        target_group, index = target
        if source_group != target_group:
            return None
        return source_group, page_id, target_group, index

    def dragEnterEvent(self, event) -> None:
        if self._payload(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._payload(event.mimeData()) is not None:
            if self._valid_drop(event) is not None:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        valid = self._valid_drop(event)
        if valid is None:
            event.ignore()
            return
        source_group, page_id, target_group, index = valid
        self.pageDropped.emit(page_id, source_group, target_group, self._source, index)
        event.acceptProposedAction()


class NavSidebarList(_PageDragList):
    """The rail's page list. Drop rows are resolved against the page items
    visible in each category, skipping the non-selectable section headers."""

    def __init__(self, parent=None):
        super().__init__("visible", parent)
        self.setObjectName("NavList")

    def focusInEvent(self, event) -> None:
        """Don't let merely focusing the rail select a page.

        When a page is opened from a category's overflow panel the rail is
        deliberately left with no current row (that page has no rail row).
        Closing the panel then returns focus to this list, and Qt's default
        focus-in behaviour selects the first selectable row -- which is
        "Overview" -- firing currentItemChanged and navigating away from the
        page the user just picked. Suppress that auto-selection so the rail
        keeps its "nothing selected" state instead.
        """
        if self.currentIndex().isValid():
            super().focusInEvent(event)
            return
        self.blockSignals(True)
        try:
            super().focusInEvent(event)
            self.setCurrentIndex(QModelIndex())
        finally:
            self.blockSignals(False)

    def _page_items(self, group: str) -> list[QListWidgetItem]:
        return [
            self.item(row) for row in range(self.count())
            if self.item(row).data(GROUP_ROLE) == group
            and self.item(row).data(PAGE_ROLE) is not None
            and not self.item(row).isHidden()
        ]

    def _drop_target(self, pos: QPoint) -> tuple[str, int] | None:
        item = self.itemAt(pos)
        if item is None:
            # Dropping in the blank space under the last section appends to
            # that section. It cannot silently move a page between groups:
            # the payload's source group is checked before the drop is
            # accepted.
            if self.count() == 0:
                return None
            group = self.item(self.count() - 1).data(GROUP_ROLE)
            if not group:
                return None
            return group, len(self._page_items(group))

        group = item.data(GROUP_ROLE)
        if not group:
            return None
        if item.data(PAGE_ROLE) is None:
            # A section header means "insert at the top of this section".
            return group, 0
        pages = self._page_items(group)
        try:
            index = pages.index(item)
        except ValueError:
            return group, len(pages)
        if pos.y() > self.visualItemRect(item).center().y():
            index += 1
        return group, index


class NavOverflowList(_PageDragList):
    """The overflow panel's page list, for one category."""

    def __init__(self, parent=None):
        super().__init__("overflow", parent)
        self.setObjectName("NavOverflowList")
        self._group = ""

    def set_group(self, group: str) -> None:
        self._group = group

    def _drop_target(self, pos: QPoint) -> tuple[str, int] | None:
        if not self._group:
            return None
        item = self.itemAt(pos)
        if item is None:
            return self._group, self.count()
        index = self.row(item)
        if pos.y() > self.visualItemRect(item).center().y():
            index += 1
        return self._group, index


class NavOverflowPanel(QFrame):
    """A persistent side panel showing one category's hidden pages.

    Deliberately not a Qt.Popup: a popup closes when the pointer leaves it,
    which would cancel the very drag (panel -> rail) it needs to support.
    Instead it stays open until Esc, its close button, a page is opened, or
    the user clicks outside the rail/panel.
    """

    pageActivated = pyqtSignal(str)
    pageDropped = pyqtSignal(str, str, str, str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group = ""
        self._rail: QWidget | None = None
        self._keep_open_widgets: list[QWidget] = []
        self.setObjectName("NavOverflowPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedWidth(248)
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        self.title = QLabel()
        self.title.setObjectName("NavOverflowTitle")
        close = QToolButton()
        close.setObjectName("NavOverflowClose")
        close.setText("×")
        close.setToolTip("Close")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setFixedSize(22, 22)
        close.setAutoRaise(True)
        close.clicked.connect(self.hide)
        header.addWidget(self.title, stretch=1)
        header.addWidget(close)
        layout.addLayout(header)

        self.list = NavOverflowList(self)
        self.list.pageDropped.connect(self.pageDropped)
        self.list.itemClicked.connect(self._activate)
        self.list.itemActivated.connect(self._activate)
        layout.addWidget(self.list, stretch=1)

        self.hint = QLabel()
        self.hint.setObjectName("NavOverflowHint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 135))
        self.setGraphicsEffect(shadow)

        escape = QShortcut(QKeySequence("Esc"), self)
        escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape.activated.connect(self.hide)

    @property
    def group(self) -> str:
        return self._group

    def keep_open_when_clicking(self, widget: QWidget) -> None:
        """Allow clicks/drags that start in ``widget`` without closing the
        panel -- the rail is the source of the other half of every drag."""
        if widget not in self._keep_open_widgets:
            self._keep_open_widgets.append(widget)

    def set_rail(self, rail: QWidget) -> None:
        """The rail to sit beside. Kept separate from the "⋮" anchor so the
        panel starts at the rail's right edge instead of overlapping the
        button's own row."""
        self._rail = rail

    def set_pages(self, group: str, entries: list[tuple[str, str, QIcon, str]],
                  current_page: str = "") -> None:
        same_group = self._group == group
        scroll = self.list.verticalScrollBar().value() if same_group else 0
        self._group = group
        self.title.setText(group.upper())
        self.list.set_group(group)
        self.list.clear()
        current_item = None
        for page_id, label, icon, tooltip in entries:
            item = make_page_item(page_id, label, group, icon, tooltip, row_height=30)
            self.list.addItem(item)
            if page_id == current_page:
                current_item = item
        if current_item is not None:
            self.list.setCurrentItem(current_item)
        self.list.verticalScrollBar().setValue(scroll)

        if entries:
            self.hint.setText("Click to open · drag to reorder or back to the sidebar")
        else:
            self.hint.setText("No hidden pages here. Drag one in from the sidebar.")
        rows = max(1, len(entries))
        self.setFixedHeight(88 + max(48, rows * 30))

    def show_at(self, anchor: QWidget) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        anchor_pos = anchor.mapTo(parent, QPoint(0, -4))
        if self._rail is not None:
            x = self._rail.mapTo(parent, QPoint(self._rail.width() + 6, 0)).x()
        else:
            x = anchor.mapTo(parent, QPoint(anchor.width() + 6, 0)).x()
        pos = QPoint(x, anchor_pos.y())
        max_x = max(8, parent.width() - self.width() - 8)
        max_y = max(8, parent.height() - self.height() - 8)
        pos.setX(min(max(8, pos.x()), max_x))
        pos.setY(min(max(8, pos.y()), max_y))
        self.move(pos)
        self.show()
        self.keep_on_screen()
        self.raise_()
        self.list.setFocus(Qt.FocusReason.PopupFocusReason)

    def keep_on_screen(self) -> None:
        """Clamp after a refresh changes the panel's height (e.g. a drop
        adds rows), so it never grows off the bottom of the window."""
        parent = self.parentWidget()
        if parent is None:
            return
        max_height = max(120, parent.height() - 16)
        if self.height() > max_height:
            self.setFixedHeight(max_height)
        x = max(8, min(self.x(), parent.width() - self.width() - 8))
        y = max(8, min(self.y(), parent.height() - self.height() - 8))
        self.move(x, y)

    def _activate(self, item: QListWidgetItem) -> None:
        page_id = item.data(PAGE_ROLE)
        if page_id and self.isVisible():
            self.pageActivated.emit(page_id)

    # -- lifecycle ---------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def hideEvent(self, event) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        super().hideEvent(event)

    def _contains_widget(self, widget: QWidget) -> bool:
        if widget is self or self.isAncestorOf(widget):
            return True
        return any(
            widget is keep or keep.isAncestorOf(widget)
            for keep in self._keep_open_widgets
        )

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and self.isVisible():
            if isinstance(obj, QWidget) and not self._contains_widget(obj):
                self.hide()
        return super().eventFilter(obj, event)
