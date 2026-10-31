# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2026 James Fleming
"""Hide the ChromeOS title bar on FreeCAD's main window (Crostini, X11).

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
import subprocess

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

EDGE = 8  # px band at the window border that starts a resize

APP_ID = "org.freecad.FreeCAD"  # FreeCAD's own desktop/icon id
GENERATED_KEY = "X-ChromeOS-Frameless-Generated"


def _on_chromeos():
    return os.path.isdir("/opt/google/cros-containers")


def _wanted():
    if not (_on_chromeos()
            and os.environ.get("FREECAD_FRAMED") != "1"
            and QtGui.QGuiApplication.platformName() == "xcb"):
        return False
    if shutil.which("xprop") is None:
        App.Console.PrintWarning(
            "ChromeOS Frameless: 'xprop' not found; install it with "
            "'sudo apt install x11-utils'. Leaving the title bar alone.\n")
        return False
    return True


# Widgets whose empty area can be dragged to move a frameless dialog. Matched
# on the C++ class name so FreeCAD's own QWidget subclasses don't count.
BACKGROUND_CLASSES = {"QWidget", "QFrame", "QLabel", "QGroupBox"}
TEXT_INTERACTIVE = (QtCore.Qt.TextSelectableByMouse
                    | QtCore.Qt.LinksAccessibleByMouse)


def _is_dialog(widget):
    return (isinstance(widget, QtWidgets.QDialog) and widget.isWindow()
            and widget.windowType() == QtCore.Qt.Dialog)


def _is_background(widget):
    if widget.isWindow():
        return True
    if widget.metaObject().className() not in BACKGROUND_CLASSES:
        return False
    if isinstance(widget, QtWidgets.QLabel):
        return not widget.textInteractionFlags() & TEXT_INTERACTIVE
    if isinstance(widget, QtWidgets.QGroupBox):
        return not widget.isCheckable()
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
    EVENTS = BAR_EVENTS + WINDOW_EVENTS + MOUSE_EVENTS + (QtCore.QEvent.Polish,)

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
        if t == QtCore.QEvent.Polish:
            # Sent once, before a widget is first shown: Qt then maps the
            # dialog already asking for no decorations, so no bar ever shows.
            if _is_dialog(obj):
                obj.setWindowFlag(QtCore.Qt.FramelessWindowHint, True)
            return False
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
        win = obj.window()
        if win is not self.mw:
            return self._dialog_mouse(win, obj, ev)
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

    def _dialog_mouse(self, win, obj, ev):
        if (ev.type() != QtCore.QEvent.MouseButtonPress or not _is_dialog(win)
                or not win.windowFlags() & QtCore.Qt.FramelessWindowHint):
            return False
        handle = win.windowHandle()
        edges = _edges_at(win, ev.globalPosition().toPoint())
        if edges is not None:
            handle.startSystemResize(edges)
            return True
        if _is_background(obj):
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

    for path in glob.glob(os.path.join(apps, "*.desktop")):
        if path == ours:
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            if "StartupWMClass=FreeCAD" in f.read():
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
        with open(ours, encoding="utf-8") as f:
            current = f.read()
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
    if _on_chromeos():
        QtCore.QTimer.singleShot(1500, _ensure_launcher_safely)
    if _wanted():
        QtCore.QTimer.singleShot(1000, _apply)
