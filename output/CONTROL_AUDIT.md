# Studio controls and UI audit — October 16, 2026

The core interaction audit passes. The entire product is **not fully certified**: the installed Maya 2024 runtime fails to initialize, so native Maya interchange remains blocked.

## Verified results

- **71 GUI behavior checks passed**, with no failures. These deliver events through Blender's real GUI event queue and PySide6 QtTest in a disposable scene. They do not constitute physical-device or full Maya parity certification.
- **121 data and dispatch checks passed**: all 109 menu operator entries have valid operator/property contracts; all 56 unique shelf IDs have dispatch implementations. Semantic checks cover selected Boolean operands, distinct Union/Difference results, material assignment, constraint targets, source mesh preservation, and navigation preference restoration.
- Existing regression suites **02, 03, 04, 05, 06, 08, 09, 10, and 11 passed**. Initial temporary-directory permission failures were rerun using workspace-local temporary storage; they were not counted as passes.
- Suite **07 does not pass**. `mayapy.exe` crashes with `0xC0000005` while initializing its standalone runtime, including outside the sandbox. A direct invocation also fails to import `maya.standalone` with a DLL initialization error. Runtime discovery alone is not a working conversion test.

## Corrected behavior

- The interactive launcher closes the startup splash before adding Studio panels. An obscured splash was consuming viewport clicks and keys.
- Q/W/E/R activate actual Select/Move/Rotate/Scale tools and synchronize the manipulator. Native LMB Move/Scale handle drags and MMB transform drags are tested.
- Click replaces selection; Shift-click toggles; Ctrl-click removes; Ctrl+Shift-click adds. Marquee selection works from all four tools. Shift marquee adds/preserves, Ctrl marquee removes, and Ctrl+Shift marquee adds.
- Alt+LMB tumbles, Alt+MMB tracks, and Alt+RMB uses horizontal dolly. Dragging right and scrolling up move closer. Input preferences restore when Studio is disabled.
- F8/F9/F10/F11 switch object/vertex/edge/face modes. S sets transform keys; Z and Shift+Z undo and redo. Text editing keeps its own keys.
- Viewport menus and 4/5/6/7, Wire, X-Ray, SSAO, and Shadows are real PySide6 widgets. State reads back from Blender. SSAO uses Blender 5.2's fast-GI ambient-occlusion path instead of the removed `use_gtao` setting. X-Ray enters a supported shading mode.
- RMB marking menus have actual PySide6 buttons and retain the radial action definitions, branches, cursor targeting, and native modal gesture dispatch. Tentacle's actual Qt hotbox/tool windows remain in use.
- Modeling caddies use editable PySide6 controls; changing a parameter updates geometry and Cancel restores the captured mesh.
- The eight right-side panels open; Lasso activates the native lasso tool. Outliner clearing clears Blender selection. Sample display-layer rows were removed; authored mini-layer visibility/mode controls are wired.
- Playback range grips and the Python command button perform their advertised actions.
- Isolate and Joint shelf buttons execute real actions. Unknown shelf actions report an error. Send Maya no longer silently performs only a dry run when clicked.
- Boolean Union/Difference use the correct operation and operand; Assign New Material assigns its material; constraint actions set a selected driver.
- Upstream keymap repair no longer treats Studio-owned shortcuts as its own or replaces all Studio bindings during a repair.

## Scope and remaining limits

Custom controls share **PySide6 6.12.0** through one QApplication; qtpy is pinned to PySide6. Blender renders native editor canvases, transform gizmos, and spatial selection guides. Read-only GPU HUD overlays are not buttons.

This audit does not prove every command on every possible rig/asset, every OS focus/DPI transition, every Maya interaction, or live delivery into interactive Maya. Native `.ma`/`.mb` conversion and Send Maya require a healthy Maya runtime. No source assets were overwritten and no global add-on installation or dependency download was performed.

## Evidence and use

- `controls_gui_results.json`, `controls_gui.log`, `controls_data_results.json`, `controls_data.log`
- `audit_phase02.log` through `audit_phase11.log` (suite 07 failed as described above)
- `controls_viewport_bar.png`, `controls_caddy_qt.png`, and `controls_radial_qt.png` capture running Qt widgets. `controls_native_frame.png` is Blender's framebuffer; foreign Qt surfaces are excluded from that framebuffer.
- Open **Open Landfall Studio.cmd** in the workspace to launch a session that stays open. Screenshot test scripts intentionally close Blender when finished.

References: Autodesk's [selection modifiers](https://help.autodesk.com/cloudhelp/2027/ENU/Maya-Basics/files/GUID-98CCC417-B06A-4E19-A3C6-19EF75295EEA.htm), [camera navigation](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Basics/files/GUID-941480C1-9BDA-4DB3-8EA8-113A0D6FAF1F.htm), and [hotkey reference](https://help.autodesk.com/cloudhelp/2025/ENU/Maya-KeyboardShortcuts/files/GUID-30CACC9D-8FBE-4B85-8A8F-C5ADF32DDD4E.htm).
