# ChromeOS Frameless for FreeCAD

On a Chromebook, Linux apps run inside ChromeOS's Linux environment (Crostini),
and ChromeOS adds its own tall, light-grey title bar to every X11 window.
This FreeCAD add-on removes that bar from FreeCAD's main window and puts the
window controls on FreeCAD's menu bar instead:

- **Move:** drag the empty space on the menu bar (to the right of *Help*).
- **Maximise / restore:** double-click that empty space, or use the □ button.
- **Resize:** press and drag within 8 px of any window edge.
- **Minimise / maximise / close:** buttons at the right end of the menu bar.
  Their icons follow your theme: light on dark themes, dark on light ones.

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

## Turning it off

- For one session: start FreeCAD with `FREECAD_FRAMED=1`.
- Permanently: disable or uninstall it in the Addon Manager, or delete the folder
  from `Mod`.

## Known limitations

- The cursor doesn't change shape over the resize edges, so you have to aim.
- The splash screen keeps its title bar. It appears before FreeCAD loads
  add-ons. You can turn it off in *Edit → Preferences → General*.
- Only FreeCAD's main window is affected. Separate dialogs keep the ChromeOS bar.

## How it works

ChromeOS's X11 bridge (*sommelier*) honours the standard `_MOTIF_WM_HINTS`
property. The add-on uses it to ask for "no decorations". Moving and resizing go
through Qt's `startSystemMove()` / `startSystemResize()`, which use the
`_NET_WM_MOVERESIZE` protocol that sommelier supports.

## License

LGPL-2.1-or-later, the same as FreeCAD. See [LICENSE](LICENSE).
