# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2026 James Fleming
"""Hide the ChromeOS title bar on FreeCAD's main window (Crostini, X11).

- Drag empty space on the menu bar to move the window.
- Double-click empty menu bar space to maximise / restore.
- Press within a few pixels of the window edge and drag to resize.
- Minimise / maximise / close buttons at the right end of the menu bar.

Disable: launch with FREECAD_FRAMED=1, or uninstall the add-on.
"""
import os
import shutil
import subprocess

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

EDGE = 8  # px band at the window border that starts a resize


def _wanted():
    if not (os.path.isdir("/opt/google/cros-containers")
            and os.environ.get("FREECAD_FRAMED") != "1"
            and QtGui.QGuiApplication.platformName() == "xcb"):
        return False
    if shutil.which("xprop") is None:
        App.Console.PrintWarning(
            "ChromeOS Frameless: 'xprop' not found; install it with "
            "'sudo apt install x11-utils'. Leaving the title bar alone.\n")
        return False
    return True


def _edges_at(win, gpos):
    """Qt.Edges for a global point near the border of win, or None."""
    if win.isMaximized() or win.isFullScreen():
        return None
    p = win.mapFromGlobal(gpos)
    r = win.rect()
    edges = QtCore.Qt.Edges()
    if p.x() < EDGE:
        edges |= QtCore.Qt.LeftEdge
    elif p.x() > r.width() - EDGE:
        edges |= QtCore.Qt.RightEdge
    if p.y() < EDGE:
        edges |= QtCore.Qt.TopEdge
    elif p.y() > r.height() - EDGE:
        edges |= QtCore.Qt.BottomEdge
    return edges if edges != QtCore.Qt.Edges() else None


def _glyph(kind, color):
    """16 px line icon for a window button, drawn in the given colour."""
    ratio = QtWidgets.QApplication.instance().devicePixelRatio()
    pm = QtGui.QPixmap(int(16 * ratio), int(16 * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    pen = QtGui.QPen(color, 1.2)
    p.setPen(pen)
    if kind == "min":
        p.drawLine(QtCore.QPointF(3.5, 8.5), QtCore.QPointF(12.5, 8.5))
    elif kind == "max":
        p.drawRect(QtCore.QRectF(3.5, 3.5, 9, 9))
    elif kind == "restore":
        p.drawRect(QtCore.QRectF(3.5, 5.5, 7, 7))
        p.drawPolyline([QtCore.QPointF(5.5, 5.5), QtCore.QPointF(5.5, 3.5),
                        QtCore.QPointF(12.5, 3.5), QtCore.QPointF(12.5, 10.5),
                        QtCore.QPointF(10.5, 10.5)])
    elif kind == "close":
        p.drawLine(QtCore.QPointF(3.5, 3.5), QtCore.QPointF(12.5, 12.5))
        p.drawLine(QtCore.QPointF(12.5, 3.5), QtCore.QPointF(3.5, 12.5))
    p.end()
    return QtGui.QIcon(pm)


class _TitleButtons(QtWidgets.QWidget):
    STYLE = """
        QToolButton { border: none; padding: 3px 10px; background: transparent; }
        QToolButton:hover { background: rgba(128, 128, 128, 70); }
        QToolButton#close:hover { background: #c42b1c; }
    """

    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        self.setStyleSheet(self.STYLE)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.min_btn = self._button("Minimise", mw.showMinimized)
        self.max_btn = self._button("Maximise", self._toggle_max)
        self.close_btn = self._button("Close", mw.close)
        self.close_btn.setObjectName("close")
        for b in (self.min_btn, self.max_btn, self.close_btn):
            lay.addWidget(b)
        self.update_icons()

    def _button(self, tip, slot):
        b = QtWidgets.QToolButton(self)
        b.setToolTip(tip)
        b.setFocusPolicy(QtCore.Qt.NoFocus)
        b.clicked.connect(slot)
        return b

    def _toggle_max(self):
        if self.mw.isMaximized():
            self.mw.showNormal()
        else:
            self.mw.showMaximized()

    def _icon_color(self):
        """Contrast with the menu bar as actually drawn: FreeCAD's themes are
        stylesheets, so the palette's text colour can't be trusted."""
        bar = self.parentWidget()
        if not isinstance(bar, QtWidgets.QMenuBar) or bar.width() <= self.width():
            return self.palette().color(QtGui.QPalette.WindowText)
        img = bar.grab().toImage()
        ratio = img.width() / bar.width()
        x = int((bar.width() - self.width() - 10) * ratio)
        bg = img.pixelColor(x, int(2 * ratio))
        return QtGui.QColor(225, 225, 225) if bg.lightness() < 128 else QtGui.QColor(30, 30, 30)

    def update_icons(self):
        color = self._icon_color()
        maxed = self.mw.isMaximized()
        self.min_btn.setIcon(_glyph("min", color))
        self.max_btn.setIcon(_glyph("restore" if maxed else "max", color))
        self.max_btn.setToolTip("Restore" if maxed else "Maximise")
        self.close_btn.setIcon(_glyph("close", color))


def _place_buttons(bar, buttons):
    buttons.adjustSize()
    buttons.setFixedHeight(bar.height())
    buttons.move(bar.width() - buttons.width(), 0)
    buttons.raise_()


class _WindowControls(QtCore.QObject):
    BAR_EVENTS = (QtCore.QEvent.Resize, QtCore.QEvent.LayoutRequest)
    WINDOW_EVENTS = (QtCore.QEvent.WindowStateChange, QtCore.QEvent.PaletteChange,
                     QtCore.QEvent.StyleChange)
    MOUSE_EVENTS = (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick)
    EVENTS = BAR_EVENTS + WINDOW_EVENTS + MOUSE_EVENTS

    def __init__(self, mw, buttons):
        super().__init__(mw)
        self.mw = mw
        self.bar = mw.menuBar()
        self.buttons = buttons
        # The app-wide filter must be gone before the main window is torn
        # down; touching a half-destroyed QMainWindow segfaults on exit.
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.uninstall)

    def uninstall(self):
        QtWidgets.QApplication.instance().removeEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() not in self.EVENTS:
            return False
        try:
            return self._filter(obj, ev)
        except RuntimeError:  # a widget we track was destroyed; stand down
            self.uninstall()
            return False

    def _filter(self, obj, ev):
        t = ev.type()
        if obj is self.bar and t in self.BAR_EVENTS:
            _place_buttons(obj, self.buttons)
            return False
        if obj is self.mw and t in self.WINDOW_EVENTS:
            self.buttons.update_icons()
            return False
        if t not in self.MOUSE_EVENTS:
            return False
        if ev.button() != QtCore.Qt.LeftButton or not isinstance(obj, QtWidgets.QWidget):
            return False
        if obj.window() is not self.mw:
            return False
        if obj is self.buttons or self.buttons.isAncestorOf(obj):
            return False  # let the buttons work even inside the resize band

        handle = self.mw.windowHandle()
        if t == QtCore.QEvent.MouseButtonPress:
            edges = _edges_at(self.mw, ev.globalPosition().toPoint())
            if edges is not None:
                handle.startSystemResize(edges)
                return True

        if obj is self.bar and self.bar.actionAt(ev.position().toPoint()) is None:
            if t == QtCore.QEvent.MouseButtonDblClick:
                if self.mw.isMaximized():
                    self.mw.showNormal()
                else:
                    self.mw.showMaximized()
            else:
                handle.startSystemMove()
            return True
        return False


def _undecorate(widget):
    # _MOTIF_WM_HINTS = flags (2: "decorations field is set"), functions,
    # decorations (0: none), input mode, status. ChromeOS's X11 bridge
    # (sommelier) drops its title bar for windows that ask for no decorations.
    subprocess.run(["xprop", "-id", str(int(widget.winId())),
                    "-f", "_MOTIF_WM_HINTS", "32c",
                    "-set", "_MOTIF_WM_HINTS", "2, 0, 0, 0, 0"], check=False)


def _apply():
    mw = Gui.getMainWindow()
    _undecorate(mw)

    # Overlay on the menu bar rather than its corner widget: FreeCAD replaces
    # (and deletes) the corner widget when it sets up the workbench selector.
    bar = mw.menuBar()
    buttons = _TitleButtons(mw)
    buttons.setParent(bar)
    buttons.show()
    _place_buttons(bar, buttons)
    buttons.update_icons()  # now that the bar's real background is known

    mw._window_controls = _WindowControls(mw, buttons)
    QtWidgets.QApplication.instance().installEventFilter(mw._window_controls)


def install():
    if _wanted():
        QtCore.QTimer.singleShot(1000, _apply)
