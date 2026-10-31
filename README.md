# ChromeOS Frameless for FreeCAD

On a Chromebook, Linux apps run inside ChromeOS's Linux environment (Crostini),
and ChromeOS adds its own tall, light-grey title bar to every X11 window.
This FreeCAD add-on removes that bar from FreeCAD's main window and dialogs,
and puts the window controls on FreeCAD's menu bar instead:

- **Move:** drag the empty space on the menu bar (to the right of *Help*).
- **Maximise / restore:** double-click that empty space, or use the □ button.
- **Resize:** press and drag within 8 px of any window edge.
- **Minimise / maximise / close:** buttons at the right end of the menu bar.
  Their icons follow your theme: light on dark themes, dark on light ones.
- **Dialogs:** Preferences, the Addon Manager, message boxes and other dialogs
  open without the bar too. Drag any empty area of a dialog to move it, or drag
  its edges to resize. Close them with their own buttons or **Esc**.
- **Shelf icon:** if you run FreeCAD from an **AppImage**, ChromeOS shows a
  generic Linux penguin in the shelf, because an AppImage doesn't register a
  launcher or icon. The add-on installs FreeCAD's icon and a launcher the first
  time it runs, so FreeCAD gets its own icon from the next start onwards.

ChromeOS keyboard shortcuts keep working: **Alt+=** maximises, **Alt+[** and
**Alt+]** snap the window to the left or right half of the screen.

<!-- Screenshot: add docs/screenshot.png and uncomment
![FreeCAD without the ChromeOS title bar](docs/screenshot.png)
-->

## Requirements

- FreeCAD 1.0 or newer (tested with 1.1.4, Qt 6), running under ChromeOS Linux.
- `xprop`, which is preinstalled on ChromeOS Linux. If it's missing, install it with
  `sudo apt install x11-utils`.

Outside ChromeOS, or when FreeCAD runs natively on Wayland, the add-on does
nothing.

## Install

**Addon Manager:** in FreeCAD, open *Tools → Addon manager*, search for
*ChromeOS Frameless*, install, and restart FreeCAD. If it isn't in the list
yet, add `https://github.com/jflmng/FreeCAD-ChromeOS-Frameless` as a custom
repository in the Addon Manager's preferences.

**Manually:**

```bash
git clone https://github.com/jflmng/FreeCAD-ChromeOS-Frameless \
    ~/.local/share/FreeCAD/v1-1/Mod/ChromeOSFrameless
```

Use the `Mod` folder for your FreeCAD version (`v1-0`, `v1-1`, …). Then restart
FreeCAD.

## The AppImage launcher

The add-on writes `~/.local/share/applications/org.freecad.FreeCAD.desktop`
and FreeCAD's icon under `~/.local/share/icons/hicolor/`. The launcher includes
`StartupWMClass=FreeCAD`, which is how ChromeOS matches the running window to
its icon. It also:

- does nothing if you already have a FreeCAD launcher (any `.desktop` file with
  `StartupWMClass=FreeCAD`), or if FreeCAD was installed from a distro package
- updates the launcher's path if you move or replace the AppImage
- never overwrites a launcher it didn't create

## Turning it off

- For one session: start FreeCAD with `FREECAD_FRAMED=1`.
- Permanently: disable or uninstall it in the Addon Manager, or delete the folder
  from `Mod`. The AppImage launcher stays; delete
  `~/.local/share/applications/org.freecad.FreeCAD.desktop` if you don't want it.

## Known limitations

- The cursor doesn't change shape over the resize edges, so you have to aim.
- The splash screen keeps its title bar. It appears before FreeCAD loads
  add-ons. You can turn it off in *Edit → Preferences → General*.
- Frameless dialogs don't show their title text (for example "Preferences").

## How it works

ChromeOS's X11 bridge (*sommelier*) honours the standard `_MOTIF_WM_HINTS`
property. The add-on uses it to ask for "no decorations". Moving and resizing go
through Qt's `startSystemMove()` / `startSystemResize()`, which use the
`_NET_WM_MOVERESIZE` protocol that sommelier supports.

## License

LGPL-2.1-or-later, the same as FreeCAD. See [LICENSE](LICENSE).
