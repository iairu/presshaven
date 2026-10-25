"""Minimize / maximize for the frameless main window on hosts whose window
manager can't do it.

Qt's showMinimized()/showMaximized() are requests to the window manager.
VcXsrv (and similar Windows X servers used from WSL) run without an EWMH
window manager: confirmed live, they ignore both the WM_CHANGE_STATE /
_NET_WM_STATE requests Qt sends and the _NET_WM_STATE property itself --
even for decorated windows, whose working min/max buttons are native
Windows frame controls that never go through X. A frameless window there
has no way to minimize or maximize through X at all.

So on such an "unmanaged" X server:
  * maximize is done by hand -- the window is resized to the work area of
    the monitor it is on (taken from Windows, so the taskbar stays visible;
    falls back to Qt's available screen geometry);
  * minimize asks Windows directly (user32 ShowWindow on the X server's
    window, found by its title) through one long-lived powershell.exe
    helper via WSL interop; restoring is then native (taskbar click).
Everywhere else (a real X11 window manager, Wayland, Windows) the native Qt
calls are used unchanged."""
from __future__ import annotations

import base64
import ctypes
import ctypes.util
import os
import shutil
from collections import deque
from typing import Callable

from PyQt6.QtCore import QObject, QProcess, QRect, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QWidget

_SW_MINIMIZE = 6
_POWERSHELL_FALLBACK = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
# How long to wait for the helper's work-area answer before maximizing to
# Qt's own screen geometry instead.
_WORKAREA_TIMEOUT_MS = 600
# VcXsrv drops the first configure request on a window that fills the work
# area (confirmed live: one setGeometry() from maximized does nothing, a
# second one lands), so by-hand geometry changes are checked and re-sent.
_GEOMETRY_RETRY_MS = 60
_GEOMETRY_RETRIES = 4

# Reads one command per line from stdin, answers one line per command.
#   show <nCmdShow> <base64 title>  -> "ok <hwnd>"
#   work <base64 title>             -> "work l t r b vx vy vw vh"  (monitor work
#                                       area of that window + virtual screen)
_HELPER_SCRIPT = r'''
Add-Type -TypeDefinition @"
using System; using System.Text; using System.Runtime.InteropServices;
public static class PhWin {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] struct MONITORINFO { public int cbSize; public RECT rcMonitor; public RECT rcWork; public uint dwFlags; }
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] static extern IntPtr MonitorFromWindow(IntPtr h, uint f);
  [DllImport("user32.dll")] static extern bool GetMonitorInfo(IntPtr m, ref MONITORINFO i);
  [DllImport("user32.dll")] static extern int GetSystemMetrics(int i);
  public static IntPtr Find(string title) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { var t = new StringBuilder(512); GetWindowText(h, t, 512);
      if (t.ToString() == title) { found = h; return false; } return true; }, IntPtr.Zero);
    return found;
  }
  public static IntPtr Show(string title, int cmd) {
    IntPtr h = Find(title); if (h != IntPtr.Zero) ShowWindow(h, cmd); return h;
  }
  public static string Work(string title) {
    IntPtr h = Find(title); if (h == IntPtr.Zero) return "none";
    var i = new MONITORINFO(); i.cbSize = Marshal.SizeOf(i);
    if (!GetMonitorInfo(MonitorFromWindow(h, 2), ref i)) return "none";
    return string.Format("{0} {1} {2} {3} {4} {5} {6} {7}", i.rcWork.L, i.rcWork.T, i.rcWork.R, i.rcWork.B,
      GetSystemMetrics(76), GetSystemMetrics(77), GetSystemMetrics(78), GetSystemMetrics(79));
  }
}
"@
[Console]::Out.WriteLine("ready"); [Console]::Out.Flush()
while (($line = [Console]::In.ReadLine()) -ne $null) {
  $p = $line.Split(' ')
  try {
    if ($p[0] -eq 'show') {
      $t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p[2]))
      $out = "ok " + [PhWin]::Show($t, [int]$p[1])
    } elseif ($p[0] -eq 'work') {
      $t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p[1]))
      $out = "work " + [PhWin]::Work($t)
    } else { $out = "err" }
  } catch { $out = "err" }
  [Console]::Out.WriteLine($out); [Console]::Out.Flush()
}
'''


def _x11_has_window_manager() -> bool:
    """Whether the X server runs an EWMH window manager (one that sets
    _NET_SUPPORTING_WM_CHECK on the root window). Anything that goes wrong
    while asking counts as "yes", so the native Qt calls stay the default."""
    lib_path = ctypes.util.find_library("X11") or "libX11.so.6"
    try:
        x11 = ctypes.cdll.LoadLibrary(lib_path)
    except OSError:
        return True
    c_ulong, c_void_p = ctypes.c_ulong, ctypes.c_void_p
    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XInternAtom.restype = c_ulong
    x11.XInternAtom.argtypes = [c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XGetWindowProperty.argtypes = [
        c_void_p, c_ulong, c_ulong, ctypes.c_long, ctypes.c_long, ctypes.c_int, c_ulong,
        ctypes.POINTER(c_ulong), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(c_ulong),
        ctypes.POINTER(c_ulong), ctypes.POINTER(c_void_p),
    ]
    x11.XFree.argtypes = [c_void_p]
    x11.XCloseDisplay.argtypes = [c_void_p]

    display = x11.XOpenDisplay(None)
    if not display:
        return True
    try:
        atom = x11.XInternAtom(display, b"_NET_SUPPORTING_WM_CHECK", 1)
        if not atom:
            return False
        actual_type, actual_format = c_ulong(), ctypes.c_int()
        nitems, after, prop = c_ulong(), c_ulong(), c_void_p()
        status = x11.XGetWindowProperty(
            display, x11.XDefaultRootWindow(display), atom, 0, 1, 0, 0,
            ctypes.byref(actual_type), ctypes.byref(actual_format), ctypes.byref(nitems),
            ctypes.byref(after), ctypes.byref(prop))
        if prop.value:
            x11.XFree(prop)
        return status != 0 or (actual_type.value != 0 and nitems.value > 0)
    finally:
        x11.XCloseDisplay(display)


def _powershell() -> str | None:
    found = shutil.which("powershell.exe")
    if found:
        return found
    return _POWERSHELL_FALLBACK if os.path.exists(_POWERSHELL_FALLBACK) else None


class _WindowsHelper(QObject):
    """One powershell.exe kept running for the app's lifetime (starting it
    costs ~1 s; a request to a running one is near-instant). Requests are
    answered in order, so replies are matched to callbacks FIFO."""

    def __init__(self, program: str, parent: QObject):
        super().__init__(parent)
        self._program = program
        self._process: QProcess | None = None
        self._pending: deque[Callable[[str], None] | None] = deque()
        self._buffer = b""
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    def start(self) -> None:
        if self._process is not None:
            return
        process = QProcess(self)
        process.readyReadStandardOutput.connect(self._on_output)
        process.finished.connect(self._on_finished)
        encoded = base64.b64encode(_HELPER_SCRIPT.encode("utf-16-le")).decode("ascii")
        process.start(self._program, ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                      "-EncodedCommand", encoded])
        self._process = process
        self._pending.append(None)   # the "ready" line

    def request(self, line: str, callback: Callable[[str], None] | None = None) -> None:
        self.start()
        self._pending.append(callback)
        self._process.write((line + "\n").encode("ascii"))

    def stop(self) -> None:
        if self._process is None:
            return
        process, self._process = self._process, None
        process.closeWriteChannel()
        if not process.waitForFinished(1000):
            process.kill()
            process.waitForFinished(500)

    def _on_output(self) -> None:
        if self._process is None:
            return
        self._buffer += bytes(self._process.readAllStandardOutput())
        while b"\n" in self._buffer:
            raw, self._buffer = self._buffer.split(b"\n", 1)
            callback = self._pending.popleft() if self._pending else None
            if callback is not None:
                callback(raw.decode("utf-8", "replace").strip())

    def _on_finished(self, *_args) -> None:
        # Fail whatever was still waiting; the next request restarts it.
        pending, self._pending = self._pending, deque()
        self._process = None
        self._buffer = b""
        for callback in pending:
            if callback is not None:
                callback("err")


class WindowHost(QObject):
    """minimize() / toggle_maximized() / is_maximized() for a frameless
    top-level window, native where the window manager supports it and done
    by hand (see module docstring) where it doesn't."""

    def __init__(self, window: QWidget, on_state_changed: Callable[[], None]):
        super().__init__(window)
        self._window = window
        self._on_state_changed = on_state_changed
        # Normal geometry while maximized by hand; None otherwise.
        self._restore_geometry: QRect | None = None
        # Bumped per by-hand geometry change, so a pending retry of an
        # older one stands down.
        self._generation = 0
        self._manual = (QGuiApplication.platformName() == "xcb"
                        and not _x11_has_window_manager())
        program = _powershell() if self._manual else None
        self._helper = _WindowsHelper(program, self) if program else None
        if self._helper is not None:
            # Warm it up now so the first click doesn't wait for startup.
            QTimer.singleShot(0, self._helper.start)

    @property
    def manual(self) -> bool:
        return self._manual

    def is_maximized(self) -> bool:
        return self._restore_geometry is not None or self._window.isMaximized()

    def minimize(self) -> None:
        if self._manual and self._helper is not None:
            self._helper.request(f"show {_SW_MINIMIZE} {self._title_b64()}")
        else:
            self._window.showMinimized()

    def toggle_maximized(self) -> None:
        if self.is_maximized():
            self.restore()
        elif not self._manual:
            self._window.showMaximized()
        elif self._helper is not None:
            self._maximize_from_windows()
        else:
            self._maximize_to(self._qt_work_area())

    def restore(self) -> None:
        """Back to the normal geometry. Safe to call when not maximized."""
        if self._restore_geometry is not None:
            geometry, self._restore_geometry = self._restore_geometry, None
            self._set_geometry(geometry)
            self._on_state_changed()
        elif self._window.isMaximized():
            self._window.showNormal()

    def normal_geometry(self) -> QRect:
        """The geometry to persist: the pre-maximize one while maximized by
        hand, so the next launch doesn't open at full-screen size."""
        return QRect(self._restore_geometry) if self._restore_geometry else self._window.geometry()

    # ---- manual maximize ----

    def _title_b64(self) -> str:
        return base64.b64encode(self._window.windowTitle().encode("utf-8")).decode("ascii")

    def _qt_work_area(self) -> QRect:
        screen = self._window.screen() or QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def _maximize_from_windows(self) -> None:
        state = {"done": False}

        def apply(area: QRect) -> None:
            if not state["done"]:
                state["done"] = True
                self._maximize_to(area)

        def on_reply(reply: str) -> None:
            apply(self._map_work_area(reply) or self._qt_work_area())

        self._helper.request(f"work {self._title_b64()}", on_reply)
        QTimer.singleShot(_WORKAREA_TIMEOUT_MS, lambda: apply(self._qt_work_area()))

    def _map_work_area(self, reply: str) -> QRect | None:
        """Windows coordinates -> X root coordinates. VcXsrv's root window
        spans the Windows virtual screen, possibly scaled (DPI); anything
        that doesn't map to a sane rect inside it is rejected."""
        parts = reply.split()
        if len(parts) != 9 or parts[0] != "work":
            return None
        try:
            left, top, right, bottom, vx, vy, vw, vh = (int(p) for p in parts[1:])
        except ValueError:
            return None
        if vw <= 0 or vh <= 0:
            return None
        virtual = QGuiApplication.primaryScreen().virtualGeometry()
        sx, sy = virtual.width() / vw, virtual.height() / vh
        area = QRect(virtual.x() + round((left - vx) * sx), virtual.y() + round((top - vy) * sy),
                     round((right - left) * sx), round((bottom - top) * sy))
        if area.width() < 200 or area.height() < 150 or not virtual.contains(area):
            return None
        return area

    def _maximize_to(self, area: QRect) -> None:
        if self._restore_geometry is None:
            self._restore_geometry = self._window.geometry()
        self._set_geometry(area)
        self._on_state_changed()

    def _set_geometry(self, target: QRect, tries: int = _GEOMETRY_RETRIES) -> None:
        self._window.setGeometry(target)
        self._generation += 1
        generation = self._generation

        def check(left: int) -> None:
            # Only the size is checked: a drag that restores the window
            # moves it straight away, and that move must not be undone.
            if generation != self._generation or self._window.size() == target.size():
                return
            self._window.setGeometry(target)
            if left > 1:
                QTimer.singleShot(_GEOMETRY_RETRY_MS, lambda: check(left - 1))

        QTimer.singleShot(_GEOMETRY_RETRY_MS, lambda: check(tries))
