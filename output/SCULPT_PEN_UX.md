# Sculpt Studio pen interaction pass

The approved layout is preserved. This pass changes contact handling, feedback,
scrolling and interruption recovery in the native PySide6 controls.

| Input | Behavior |
|---|---|
| Pen tip on a command, toggle, favorite or well | Immediate pressed feedback; one action on a completed tap. Light contact is sufficient. |
| Vertical drag on a tray button, palette title or empty area | Grab the tray and move it with the tip. A drag cancels the pending button action. Stops at content bounds; no inertia. |
| Horizontal drag in an overflowing horizontal shelf | Move the shelf; retain the same button-versus-drag distinction. |
| Palette title tap | The full title width opens/closes the palette; Shift retains additional palettes. |
| Slider tap | Go directly to the touched value. The groove is visually compact with an 18–22 px hit target. |
| Slider drag | Own the drag through release, including outside the slider. Apply tray actions on release; brush Quick controls remain live. |
| Slider arrows / Ctrl+wheel | Update the actual underlying setting. Integer fields step by one. |
| Wheel over a value or picker | Scroll the tray without changing the parameter or SubTool source. |
| Numeric field tap | Native text focus; type a value and commit with Enter. |
| Dropdown tap | Open immediately, without the opening animation; the existing native combo owns its value and signals. Background refresh leaves open pickers alone. |
| Quick Menu toggle | Apply the setting and retain the popup for further changes. |
| Pen barrel on a brush | Open its existing context menu. |
| Escape / focus loss | Cancel pending contact, clear pressed/grab state and restore an uncommitted slider. The silhouette resizer also restores its starting scale. |
| Outside popup tap | Consume dismissal contact so it cannot become a canvas stroke. |

Favorite widgets remain in place when brush selection or recents change. The
collapsed tool drawer, brush shelves, header, canvas buttons, silhouette, pickers
and sculpt dialogs share the pen adapter. A faint warm pressed state provides
contact feedback without changing the approved visual arrangement.

## Ownership and native boundaries

The adapter runs inside the existing QApplication input filter. The existing
dock focus owner defers while a pen interaction owns the pointer; teardown
restores its original predicate. Handled tablet events are accepted once and
translated into native widget input. Synthesized mouse echoes are suppressed;
an actual mouse continues to work immediately after a pen.

Coordinates remain Qt logical coordinates. The adapter does not warp the pen or
replace Blender's native stroke, pressure, navigation, topology or Undo engines.
Windows press-and-hold/flick interpretation is disabled only on the adapter's
existing native UI handles and restored on teardown. No global tablet-driver or
Windows preference is changed. The combo animation preference is restored in the
same callback after opening the native popup.

## Validation

The focused native suite uses synthetic `QTabletEvent` input and real Qt widgets
in disposable Blender scenes. It verifies actual masks, brush settings, sources,
navigation state and widget/gesture ownership; these are not physical-device
latency or tablet-feel measurements.

Final scale/regression results are recorded in `sculpt_pen_acceptance.json`.
A fresh untitled demo also passed startup verification with PySide6, Sculpt
Studio active and the pen adapter installed (`sculpt_pen_demo_startup.json`).
The focused suite passes **47/47 at actual Qt DPR 1.00, 1.25 and 1.50**.
Fresh existing regressions pass: sculpt **93/93**, workspace **44/44**, Maya
controls **71/71**, Channel Box **13/13**, cursor/grid/zoom **13/13**, and
reference sidebar **56/56**. The reference sidebar suite also measures native
1280×720, 1920×1080 and 2560×1440 windows after the larger slider targets.
The independent read-only code review reported no actionable findings. Physical
tablet/driver delivery, mixed physical input devices and subjective pen feel
remain unverified. Native dialog/submenu coverage is limited to the controls
explicitly exercised; the shared adapter covers their marked sculpt parents.

Earlier diagnostics are retained. The popup investigation found a 150 ms native
combo animation and refresh interference; both were corrected. At DPR 1.00 the
first scrolling fixture requested 90 px with only 83 px remaining. The final
fixture tests a 40 px movement within bounds and separately verifies clamping.

## References

ZBrush documents sliding trays and a double-arrow cursor in
[Preferences > Interface](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/preferences/interface/interface.html).
This inspired direct tray grabbing and the drag cursor.

Qt documents that unhandled tablet input can become mouse input in
[QTabletEvent](https://doc.qt.io/qt-6/qtabletevent.html). The adapter accepts handled
contacts to avoid duplicate actions. Qt's
[native combo implementation](https://github.com/qt/qtbase/blob/dev/src/widgets/widgets/qcombobox.cpp)
also contains an opening animation and release guard; native combo APIs retain
selection ownership while the sculpt pen path bypasses that opening delay.
