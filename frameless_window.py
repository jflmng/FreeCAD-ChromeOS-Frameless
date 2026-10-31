# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2026 James Fleming
"""Hide the ChromeOS title bar on FreeCAD's windows (Crostini, X11).

- Drag empty space on the menu bar to move the window.
- Double-click empty menu bar space to maximise / restore.
- Press within a few pixels of the window edge and drag to resize.
- Minimise / maximise / close buttons at the right end of the menu bar.
- Dialogs open without a title bar too; drag their background to move them.
- When FreeCAD runs from an AppImage, adds a launcher so the ChromeOS shelf
  shows FreeCAD's icon instead of the generic Linux penguin.

Disable: launch with FREECAD_FRAMED=1, or uninstall the add-on.
"""
import glob
import os
import shutil

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

Qt, QEvent = QtCore.Qt, QtCore.QEvent

EDGE = 8  # px band at the window border that starts a resize

APP_ID = "org.freecad.FreeCAD"  # FreeCAD's own desktop/icon id
GENERATED_KEY = "X-ChromeOS-Frameless-Generated"

# Widgets whose empty area can be dragged to move a frameless dialog. Matched
# on the C++ class name so FreeCAD's own QWidget subclasses don't count.
BACKGROUND_CLASSES = {"QWidget", "QFrame", "QLabel", "QGroupBox"}

# Button icons as polylines on a 16 px grid.
GLYPHS = {
    "min": [[(3.5, 8.5), (12.5, 8.5)]],
    "max": [[(3.5, 3.5), (12.5, 3.5), (12.5, 12.5), (3.5, 12.5), (3.5, 3.5)]],
    "restore": [[(3.5, 5.5), (10.5, 5.5), (10.5, 12.5), (3.5, 12.5), (3.5, 5.5)],
                [(5.5, 5.5), (5.5, 3.5), (12.5, 3.5), (12.5, 10.5), (10.5, 10.5)]],
    "close": [[(3.5, 3.5), (12.5, 12.5)], [(12.5, 3.5), (3.5, 12.5)]],
}


def _on_chromeos():
    return os.path.isdir("/opt/google/cros-containers")


def _is_dialog(widget):
    return (isinstance(widget, QtWidgets.QDialog) and widget.isWindow()
            and widget.windowType() == Qt.Dialog)


def _make_frameless(win):
    """ChromeOS's X11 bridge (sommelier) drops its title bar for windows that
    ask for no decorations, but only reads that when the window is mapped,
    so call this before the window is first shown."""
    win.setWindowFlag(Qt.FramelessWindowHint, True)


def _is_background(widget):
    if widget.isWindow():
        return True
    if widget.metaObject().className() not in BACKGROUND_CLASSES:
        return False
    if isinstance(widget, QtWidgets.QLabel):
        return not widget.textInteractionFlags() & (
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
    if isinstance(widget, QtWidgets.QGroupBox):
        return not widget.isCheckable()
    return True


def _edges_at(win, gpos):
    """Qt.Edges for a global point near the border of win, or None."""
    if win.isMaximized() or win.isFullScreen():
        return None
    p, r = win.mapFromGlobal(gpos), win.rect()
    edges = Qt.Edges()
    if p.x() < EDGE:
        edges |= Qt.LeftEdge
    elif p.x() > r.width() - EDGE:
        edges |= Qt.RightEdge
    if p.y() < EDGE:
        edges |= Qt.TopEdge
    elif p.y() > r.height() - EDGE:
        edges |= Qt.BottomEdge
    return edges or None


# Cursor to show over each edge / corner of a frameless window.
EDGE_CURSORS = {
    Qt.LeftEdge: Qt.SizeHorCursor, Qt.RightEdge: Qt.SizeHorCursor,
    Qt.TopEdge: Qt.SizeVerCursor, Qt.BottomEdge: Qt.SizeVerCursor,
    Qt.TopEdge | Qt.LeftEdge: Qt.SizeFDiagCursor,
    Qt.BottomEdge | Qt.RightEdge: Qt.SizeFDiagCursor,
    Qt.TopEdge | Qt.RightEdge: Qt.SizeBDiagCursor,
    Qt.BottomEdge | Qt.LeftEdge: Qt.SizeBDiagCursor,
}


def _toggle_max(win):
    win.showNormal() if win.isMaximized() else win.showMaximized()


def _glyph(kind, color):
    """16 px line icon for a window button, drawn in the given colour."""
    ratio = QtWidgets.QApplication.instance().devicePixelRatio()
    pm = QtGui.QPixmap(int(16 * ratio), int(16 * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtGui.QPen(color, 1.2))
    for line in GLYPHS[kind]:
        p.drawPolyline([QtCore.QPointF(x, y) for x, y in line])
    p.end()
    return QtGui.QIcon(pm)


class _TitleButtons(QtWidgets.QWidget):
    """Minimise / maximise / close, overlaid on the right end of the menu bar.
    Not the bar's corner widget: FreeCAD replaces (and deletes) that when it
    sets up the workbench selector."""
    STYLE = """
        QToolButton { border: none; padding: 3px 10px; background: transparent; }
        QToolButton:hover { background: rgba(128, 128, 128, 70); }
        QToolButton#close:hover { background: #c42b1c; }
    """

    def __init__(self, mw):
        super().__init__(mw.menuBar())
        self.mw = mw
        self.setStyleSheet(self.STYLE)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.min_btn, self.max_btn, self.close_btn = (
            self._button(lay, slot) for slot in (
                mw.showMinimized, lambda: _toggle_max(mw), mw.close))
        self.min_btn.setToolTip("Minimise")
        self.close_btn.setToolTip("Close")
        self.close_btn.setObjectName("close")
        self.show()
        self.place()

    def _button(self, lay, slot):
        b = QtWidgets.QToolButton(self)
        b.setFocusPolicy(Qt.NoFocus)
        b.clicked.connect(slot)
        lay.addWidget(b)
        return b

    def place(self):
        bar = self.parentWidget()
        self.adjustSize()
        self.setFixedHeight(bar.height())
        self.move(bar.width() - self.width(), 0)
        self.raise_()
        self.update_icons()

    def _icon_color(self):
        """Contrast with the menu bar as actually drawn: FreeCAD's themes are
        stylesheets, so the palette's text colour can't be trusted."""
        bar = self.parentWidget()
        if bar.width() <= self.width():
            return self.palette().color(QtGui.QPalette.WindowText)
        img = bar.grab().toImage()
        ratio = img.width() / bar.width()
        bg = img.pixelColor(int((bar.width() - self.width() - 10) * ratio), int(2 * ratio))
        return QtGui.QColor(225, 225, 225) if bg.lightness() < 128 else QtGui.QColor(30, 30, 30)

    def update_icons(self):
        color = self._icon_color()
        maxed = self.mw.isMaximized()
        self.min_btn.setIcon(_glyph("min", color))
        self.max_btn.setIcon(_glyph("restore" if maxed else "max", color))
        self.max_btn.setToolTip("Restore" if maxed else "Maximise")
        self.close_btn.setIcon(_glyph("close", color))


class _WindowControls(QtCore.QObject):
    """App-wide event filter: frameless dialogs, button upkeep, and
    move / resize by mouse (with resize cursors at the edges) for the main
    window and dialogs."""
    BAR_EVENTS = {QEvent.Resize, QEvent.LayoutRequest}
    WINDOW_EVENTS = {QEvent.WindowStateChange, QEvent.PaletteChange, QEvent.StyleChange}
    MOUSE_EVENTS = {QEvent.MouseButtonPress, QEvent.MouseButtonDblClick}
    HOVER_EVENTS = {QEvent.MouseMove, QEvent.Leave}
    EVENTS = BAR_EVENTS | WINDOW_EVENTS | MOUSE_EVENTS | HOVER_EVENTS | {QEvent.Polish}

    def __init__(self, mw):
        super().__init__(mw)
        self.mw = mw
        self.bar = mw.menuBar()
        self.buttons = _TitleButtons(mw)
        self.cursor = None  # resize cursor currently overriding, if any
        app = QtWidgets.QApplication.instance()
        app.installEventFilter(self)
        # The filter must be gone before the main window is torn down;
        # touching a half-destroyed QMainWindow segfaults on exit.
        app.aboutToQuit.connect(self.uninstall)

    def uninstall(self):
        QtWidgets.QApplication.instance().removeEventFilter(self)
        self._set_cursor(None)

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
        if t == QEvent.Polish:  # sent once, before a widget is first shown
            if _is_dialog(obj):
                _make_frameless(obj)
        elif t in self.BAR_EVENTS:
            if obj is self.bar:
                self.buttons.place()
        elif t in self.WINDOW_EVENTS:
            if obj is self.mw:
                self.buttons.update_icons()
        elif t in self.HOVER_EVENTS:
            # Watch the QWindow, which gets every move; widgets only get
            # moves without a button held if they turn on mouse tracking.
            if isinstance(obj, QtGui.QWindow):
                self._hover(obj, ev)
        elif ev.button() == Qt.LeftButton and isinstance(obj, QtWidgets.QWidget):
            return self._mouse(obj, ev)
        return False

    def _ours(self, win):
        return ((win is self.mw or _is_dialog(win))
                and bool(win.windowFlags() & Qt.FramelessWindowHint))

    def _on_buttons(self, widget):
        return widget is self.buttons or self.buttons.isAncestorOf(widget)

    def _hover(self, qwindow, ev):
        if ev.type() == QEvent.MouseMove and ev.buttons() != Qt.NoButton:
            return  # mid-drag: leave the cursor alone
        shape = None
        widget = QtWidgets.QWidget.find(qwindow.winId())
        if ev.type() == QEvent.MouseMove and widget and self._ours(widget.window()):
            gpos = ev.globalPosition().toPoint()
            edges = _edges_at(widget.window(), gpos)
            under = QtWidgets.QApplication.widgetAt(gpos) if edges else None
            if edges and not (under and self._on_buttons(under)):
                shape = EDGE_CURSORS.get(edges)
        self._set_cursor(shape)

    def _set_cursor(self, shape):
        if shape == self.cursor:
            return
        if self.cursor is None:
            QtWidgets.QApplication.setOverrideCursor(shape)
        elif shape is None:
            QtWidgets.QApplication.restoreOverrideCursor()
        else:
            QtWidgets.QApplication.changeOverrideCursor(shape)
        self.cursor = shape

    def _mouse(self, obj, ev):
        win = obj.window()
        if not self._ours(win) or self._on_buttons(obj):
            return False  # buttons must work even inside the resize band
        press = ev.type() == QEvent.MouseButtonPress
        handle = win.windowHandle()
        if press and (edges := _edges_at(win, ev.globalPosition().toPoint())):
            handle.startSystemResize(edges)
            return True
        if win is self.mw:
            if obj is not self.bar or self.bar.actionAt(ev.position().toPoint()):
                return False
            handle.startSystemMove() if press else _toggle_max(win)
            return True
        if press and _is_background(obj):
            handle.startSystemMove()
            return True
        return False


def _launcher_text(appimage):
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=FreeCAD\n"
        "Comment=Parametric 3D CAD modeller\n"
        f'Exec="{appimage}" %F\n'
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "Categories=Science;Engineering;\n"
        "MimeType=application/x-extension-fcstd;\n"
        # ChromeOS matches running windows to launchers by WM_CLASS; without
        # this the shelf shows a penguin.
        "StartupWMClass=FreeCAD\n"
        f"{GENERATED_KEY}=true\n"
    )


def ensure_launcher(data_home=None):
    """Give an AppImage FreeCAD a launcher and icon so ChromeOS can show the
    right shelf icon. Leaves any launcher it didn't write untouched."""
    appimage, appdir = os.environ.get("APPIMAGE"), os.environ.get("APPDIR")
    if not appimage or not appdir:
        return  # distro packages ship their own launcher and icon
    data_home = data_home or os.environ.get(
        "XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    apps = os.path.join(data_home, "applications")
    ours = os.path.join(apps, APP_ID + ".desktop")

    def read(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    if any("StartupWMClass=FreeCAD" in read(p)
           for p in glob.glob(os.path.join(apps, "*.desktop")) if p != ours):
        return  # the user already has a FreeCAD launcher

    icons = os.path.join(data_home, "icons", "hicolor")
    svg = os.path.join(appdir, APP_ID + ".svg")
    svg_dest = os.path.join(icons, "scalable", "apps", APP_ID + ".svg")
    if os.path.isfile(svg) and not os.path.isfile(svg_dest):
        os.makedirs(os.path.dirname(svg_dest), exist_ok=True)
        shutil.copyfile(svg, svg_dest)
        # PNGs too: ChromeOS picks these up more reliably than SVG alone.
        icon = QtGui.QIcon(svg_dest)
        for size in (48, 64, 128, 256):
            png = os.path.join(icons, f"{size}x{size}", "apps", APP_ID + ".png")
            os.makedirs(os.path.dirname(png), exist_ok=True)
            # Explicit ratio 1: icon sizes are real pixels, not scaled.
            icon.pixmap(QtCore.QSize(size, size), 1.0).save(png)

    text = _launcher_text(appimage)
    if os.path.isfile(ours):
        current = read(ours)
        if GENERATED_KEY not in current or current == text:
            return  # someone else's file, or already up to date
    os.makedirs(apps, exist_ok=True)
    with open(ours, "w", encoding="utf-8") as f:
        f.write(text)
    App.Console.PrintMessage(
        "ChromeOS Frameless: added a FreeCAD launcher so the shelf shows "
        "FreeCAD's icon. Restart FreeCAD to see it.\n")


def _ensure_launcher_safely():
    try:
        ensure_launcher()
    except OSError as e:
        App.Console.PrintWarning(f"ChromeOS Frameless: couldn't add launcher: {e}\n")


def install():
    if not _on_chromeos():
        return
    QtCore.QTimer.singleShot(1500, _ensure_launcher_safely)
    if os.environ.get("FREECAD_FRAMED") == "1" \
            or QtGui.QGuiApplication.platformName() != "xcb":
        return
    # Add-ons load before FreeCAD shows its main window, so it gets mapped
    # frameless from the start.
    mw = Gui.getMainWindow()
    visible = mw.isVisible()
    _make_frameless(mw)
    if visible:  # changing flags hides a shown window
        mw.show()
    QtCore.QTimer.singleShot(0, lambda: setattr(mw, "_window_controls", _WindowControls(mw)))
