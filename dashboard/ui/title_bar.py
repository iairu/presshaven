"""Custom window title bar for the frameless main window: brand + menu bar
on the left, the command-palette search pinned to the exact horizontal
centre, and the presshaven.io link + minimize / maximize / close on the
right. Dragging any empty title-bar space (including the gaps around the
brand and beside the menus) moves the window and double-clicking it toggles
maximize. Moves go through the platform's window manager
(QWindow.startSystemMove) where it can, so snapping/tiling keep working on
Wayland, X11 and Windows; X servers whose window manager doesn't advertise
_NET_WM_MOVERESIZE (VcXsrv/X410 for WSL, confirmed live) refuse that, and
the window is then moved by hand instead.

A frameless window also loses its native resize border; WindowResizeGrips
puts thin invisible handles back along every edge and corner, with the same
system-first, by-hand-fallback approach (QWindow.startSystemResize), and
WindowBorder draws the thin gray outline a frameless window otherwise lacks.
Minimize / maximize go through ui.window_host.WindowHost, which does them
by hand on X servers without a window manager (VcXsrv), where Qt's own
requests are silently ignored."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenuBar, QPushButton, QSizePolicy, QToolButton,
    QWidget,
)

from ui import theme
from ui.window_host import WindowHost

SITE_URL = "https://presshaven.io"
TITLE_BAR_HEIGHT = 40
_SEARCH_WIDTH = 360
# Narrower than this and the search can't sit centred without overlapping
# the menus or window buttons, so it shrinks into the free space instead.
_SEARCH_MIN_WIDTH = 120


class TitleBar(QFrame):
    """The window's top strip. Owns the QMenuBar (MainWindow fills it) and
    the search button (MainWindow connects searchRequested)."""

    searchRequested = pyqtSignal()

    def __init__(self, window: QWidget, icon: QIcon | None = None):
        super().__init__(window)
        self._window = window
        self.host = WindowHost(window, self._on_window_state_changed)
        self.setObjectName("TitleBar")
        self.setFixedHeight(TITLE_BAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(8)

        self._left = QWidget()
        left = QHBoxLayout(self._left)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)
        # Widgets whose empty area counts as title bar for dragging (the
        # menu bar only where no menu title is under the cursor).
        self._drag_zones: list[QWidget] = [self._left]
        if icon is not None and not icon.isNull():
            logo = QLabel()
            logo.setObjectName("TitleLogo")
            logo.setPixmap(icon.pixmap(QSize(18, 18)))
            left.addWidget(logo)
            self._drag_zones.append(logo)
        brand = QLabel("PressHaven<span style='font-weight:400'>.io</span>")
        brand.setObjectName("TitleBrand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        left.addWidget(brand)
        divider = QFrame()
        divider.setObjectName("TitleDivider")
        divider.setFixedSize(1, 16)
        left.addWidget(divider)
        self.menu_bar = QMenuBar()
        self.menu_bar.setObjectName("TitleMenuBar")
        self.menu_bar.setNativeMenuBar(False)
        self.menu_bar.setFixedHeight(28)
        left.addWidget(self.menu_bar, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._left)
        self._drag_zones += [brand, divider, self.menu_bar]

        layout.addStretch(1)

        self._right = QWidget()
        right = QHBoxLayout(self._right)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self._link = QLabel()
        self._link.setObjectName("TitleLink")
        self._link.setTextFormat(Qt.TextFormat.RichText)
        self._link.setOpenExternalLinks(True)
        self._link.setToolTip(SITE_URL)
        self._link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._link.setContentsMargins(0, 0, 12, 0)
        right.addWidget(self._link)
        self.min_btn = self._window_button("—", "Minimize", self.host.minimize)
        self.max_btn = self._window_button("□", "Maximize", self._toggle_maximized)
        self.close_btn = self._window_button("✕", "Close", self._window.close)
        self.close_btn.setObjectName("TitleCloseButton")
        for button in (self.min_btn, self.max_btn, self.close_btn):
            right.addWidget(button)
        layout.addWidget(self._right)
        self._drag_zones.append(self._right)

        # Not in the layout: positioned by hand in resizeEvent() so it sits
        # on the window's true centre line whatever the side widths are.
        self.search_btn = QPushButton("⌕   Search pages and actions…", self)
        self.search_btn.setObjectName("TitleSearch")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setToolTip("Jump to any page or action (Ctrl+K)")
        self.search_btn.clicked.connect(self.searchRequested)
        self._shortcut_hint = QLabel("Ctrl+K", self.search_btn)
        self._shortcut_hint.setObjectName("TitleSearchHint")
        self._shortcut_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Offset of the cursor from the window's top-left during a by-hand
        # move; None when no such drag is in progress.
        self._drag_offset: QPoint | None = None
        for zone in self._drag_zones:
            zone.installEventFilter(self)
        window.installEventFilter(self)
        self._apply_theme()
        theme.on_change(self._apply_theme)

    def _apply_theme(self) -> None:
        """A rich-text link takes its color from the palette in effect when
        the text was set, so it is re-set (with the theme's color inline)
        on every theme change; the hint's size changes with the stylesheet."""
        c = theme.scheme_colors()
        color = c["accent"] if theme.effective_theme() == theme.THEME_DOCS else c["nav_fg"]
        self._link.setText(
            f'<a href="{SITE_URL}" style="color:{color}; text-decoration:none;">'
            'presshaven.io&nbsp;↗</a>')
        self._place_search()

    def _window_button(self, glyph: str, tip: str, slot) -> QToolButton:
        button = QToolButton()
        button.setObjectName("TitleWindowButton")
        button.setText(glyph)
        button.setToolTip(tip)
        button.setFixedSize(46, TITLE_BAR_HEIGHT)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(slot)
        return button

    def _toggle_maximized(self) -> None:
        self.host.toggle_maximized()

    def _on_window_state_changed(self) -> None:
        """A by-hand maximize/restore sends no WindowStateChange, so the
        host reports it here. (Grips and border follow via the resize it
        causes: the host flips its state before changing the geometry.)"""
        self._sync_max_button()

    def _sync_max_button(self) -> None:
        maximized = self.host.is_maximized()
        self.max_btn.setText("❐" if maximized else "□")
        self.max_btn.setToolTip("Restore" if maximized else "Maximize")

    def eventFilter(self, obj, event) -> bool:
        if obj is self._window and event.type() == QEvent.Type.WindowStateChange:
            self._sync_max_button()
        elif obj in self._drag_zones and self._is_drag_event(obj, event):
            return self._handle_drag(event)
        return super().eventFilter(obj, event)

    # ---- layout ----

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_search()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._place_search()

    def _place_search(self) -> None:
        height = 28
        width = min(_SEARCH_WIDTH, self.width() // 3)
        x = (self.width() - width) // 2
        # Keep clear of the brand/menus on the left and the link/buttons
        # on the right; give up centring before overlapping either.
        left_edge = self._left.geometry().right() + 12
        right_edge = self._right.geometry().left() - 12
        if x < left_edge or x + width > right_edge:
            width = max(_SEARCH_MIN_WIDTH, min(width, right_edge - left_edge))
            x = max(left_edge, min(x, right_edge - width))
        self.search_btn.setVisible(right_edge - left_edge >= _SEARCH_MIN_WIDTH)
        self.search_btn.setGeometry(x, (self.height() - height) // 2, width, height)
        hint = self._shortcut_hint
        hint.ensurePolished()
        hint.adjustSize()
        hint.move(width - hint.width() - 8, (height - hint.height()) // 2)
        hint.setVisible(width >= 220)

    # ---- dragging ----

    _MOUSE_EVENTS = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove,
                     QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick)

    def _is_drag_event(self, obj: QWidget, event) -> bool:
        if event.type() not in self._MOUSE_EVENTS:
            return False
        # A drag already under way owns every move/release, wherever the
        # cursor has wandered; otherwise a press over a menu title is the
        # menu bar's, not ours.
        if self._drag_offset is not None or obj is not self.menu_bar:
            return True
        return self.menu_bar.actionAt(event.position().toPoint()) is None

    def mousePressEvent(self, event) -> None:
        if not self._handle_drag(event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self._handle_drag(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if not self._handle_drag(event):
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if not self._handle_drag(event):
            super().mouseDoubleClickEvent(event)

    def _handle_drag(self, event) -> bool:
        """Move the window from a press on empty title-bar space. Returns
        whether the event was consumed."""
        kind = event.type()
        global_pos = event.globalPosition().toPoint()
        if kind == QEvent.Type.MouseButtonDblClick:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            self._drag_offset = None
            self._toggle_maximized()
            return True
        if kind == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            handle = self._window.windowHandle()
            if handle is not None and handle.startSystemMove():
                return True
            self._drag_offset = global_pos - self._window.frameGeometry().topLeft()
            return True
        if self._drag_offset is None:
            return False
        if kind == QEvent.Type.MouseButtonRelease:
            self._drag_offset = None
            return True
        if not event.buttons() & Qt.MouseButton.LeftButton:
            self._drag_offset = None
            return False
        if self.host.is_maximized():
            # Dragging a maximized window restores it under the cursor,
            # keeping the cursor at the same relative spot along the bar.
            ratio = self._drag_offset.x() / max(1, self._window.width())
            self.host.restore()
            self._drag_offset = QPoint(int(ratio * self._window.width()), self._drag_offset.y())
        self._window.move(global_pos - self._drag_offset)
        return True


class _ResizeGrip(QWidget):
    def __init__(self, parent: QWidget, edges: Qt.Edge, cursor: Qt.CursorShape):
        super().__init__(parent)
        self._edges = edges
        # (cursor, window geometry) at press time during a by-hand resize.
        self._start: tuple[QPoint, QRect] | None = None
        self.setCursor(cursor)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        window = self.window()
        handle = window.windowHandle()
        if handle is None or not handle.startSystemResize(self._edges):
            self._start = (event.globalPosition().toPoint(), window.geometry())
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._start is None:
            super().mouseMoveEvent(event)
            return
        origin, geometry = self._start
        delta = event.globalPosition().toPoint() - origin
        window = self.window()
        min_w = max(window.minimumSizeHint().width(), window.minimumWidth(), 200)
        min_h = max(window.minimumSizeHint().height(), window.minimumHeight(), 150)
        left, top = geometry.left(), geometry.top()
        right, bottom = geometry.right(), geometry.bottom()
        e = Qt.Edge
        if self._edges & e.LeftEdge:
            left = min(left + delta.x(), right - min_w + 1)
        if self._edges & e.RightEdge:
            right = max(right + delta.x(), left + min_w - 1)
        if self._edges & e.TopEdge:
            top = min(top + delta.y(), bottom - min_h + 1)
        if self._edges & e.BottomEdge:
            bottom = max(bottom + delta.y(), top + min_h - 1)
        window.setGeometry(QRect(QPoint(left, top), QPoint(right, bottom)))
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._start = None
        super().mouseReleaseEvent(event)


class WindowResizeGrips:
    """Invisible edge/corner handles laid over a frameless window. Call
    update_geometry() from the window's resizeEvent; they hide themselves
    while the window is maximized or full-screen."""

    THICKNESS = 5
    CORNER = 12

    def __init__(self, window: QWidget, is_maximized=None):
        self._window = window
        self._is_maximized = is_maximized or window.isMaximized
        e, C = Qt.Edge, Qt.CursorShape
        self._grips = {
            "top": _ResizeGrip(window, e.TopEdge, C.SizeVerCursor),
            "bottom": _ResizeGrip(window, e.BottomEdge, C.SizeVerCursor),
            "left": _ResizeGrip(window, e.LeftEdge, C.SizeHorCursor),
            "right": _ResizeGrip(window, e.RightEdge, C.SizeHorCursor),
            "top_left": _ResizeGrip(window, e.TopEdge | e.LeftEdge, C.SizeFDiagCursor),
            "bottom_right": _ResizeGrip(window, e.BottomEdge | e.RightEdge, C.SizeFDiagCursor),
            "top_right": _ResizeGrip(window, e.TopEdge | e.RightEdge, C.SizeBDiagCursor),
            "bottom_left": _ResizeGrip(window, e.BottomEdge | e.LeftEdge, C.SizeBDiagCursor),
        }

    def update_geometry(self) -> None:
        w, h = self._window.width(), self._window.height()
        t, c = self.THICKNESS, self.CORNER
        # The top corners stay edge-thin rather than square so they never
        # swallow clicks on the title bar's logo or close button.
        rects = {
            "top": QRect(c, 0, w - 2 * c, t),
            "bottom": QRect(c, h - t, w - 2 * c, t),
            "left": QRect(0, c, t, h - 2 * c),
            "right": QRect(w - t, c, t, h - 2 * c),
            "top_left": QRect(0, 0, c, t),
            "top_right": QRect(w - c, 0, c, t),
            "bottom_left": QRect(0, h - c, c, c),
            "bottom_right": QRect(w - c, h - c, c, c),
        }
        resizable = not (self._is_maximized() or self._window.isFullScreen())
        for name, grip in self._grips.items():
            grip.setGeometry(rects[name])
            grip.setVisible(resizable)
            grip.raise_()


class WindowBorder(QWidget):
    """1px gray outline around the whole frameless window, drawn on top of
    everything and transparent to the mouse (the resize grips under it
    still work). Hidden while maximized or full-screen, like a native
    frame. Call update_geometry() from the window's resizeEvent and on
    state changes."""

    def __init__(self, window: QWidget, is_maximized=None):
        super().__init__(window)
        self._window = window
        self._is_maximized = is_maximized or window.isMaximized
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        theme.on_change(self.update)

    def update_geometry(self) -> None:
        self.setGeometry(0, 0, self._window.width(), self._window.height())
        self.setVisible(not (self._is_maximized() or self._window.isFullScreen()))
        self.raise_()

    def paintEvent(self, event) -> None:
        # Neutral gray whatever the theme's own border hue: lighter than a
        # dark background, darker than a light one.
        dark = QColor(theme.scheme_colors()["bg"]).lightness() < 128
        painter = QPainter(self)
        painter.setPen(QColor("#4a4a4a" if dark else "#a3a3a3"))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
