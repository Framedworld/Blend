# Sculpt Studio — second UX pass

Latest artist corrections: [zoom, grid, cursor and Channel Box feedback pass](SCULPT_FEEDBACK_PASS.md).

The editable design artifact and native PySide6 implementation are delivered.
Behavior and data tests pass. **Full native visual acceptance is BLOCKED**:
desktop captures show blank/stale GPU content even in a factory Blender window
before Studio or Qt loads. This is not a fully signed-off ZBrush conversion.

## Review the design

Open [the standalone prototype](sculpt-design/index.html) in a desktop browser,
or unpack [the editable ZIP](sculpt-studio-design-prototype.zip). No server,
account or installation is required. Its explicit UI PROTOTYPE label separates
interface demonstrations from native geometry operations.

- [1920×1080 reference](sculpt-design/sculpt-reference-1920.png), with additional
  1280×720 and 2560×1440 references in the same directory.
- [Brush browser](sculpt-design/brush-browser-reference.png),
  [quick controls](sculpt-design/quick-controls-reference.png), and
  [modeling return](sculpt-design/modeling-reference.png).
- [Compact layout reference](sculpt-design/layout-reference.png), editable
  `layout-reference.html`, and [layout measurements](sculpt-design/LAYOUT.md).

The artifact uses the existing creature demo and 15 original SVG brush thumbnails
shared with native Qt. Try Modeling/Sculpt, B C B, hold Space, release/Escape, RMB,
Tab, favorites, accordion sections and GoZ Return. Geometry buttons are previews.

## Native workspace

Run `Open Landfall Sculpt Studio.cmd` from the project root for a disposable
creature scene. The existing application, dispatcher and keymap owner remain in
control; no second Qt runtime was introduced.

The original second-pass startup confirmed active PySide6/Tentacle, Sculpt Studio
and three SubTools (PID 30432). The latest feedback revision opens a fresh demo;
see `interactive_startup.json` and [the feedback report](SCULPT_FEEDBACK_PASS.md)
for current session evidence. Startup/behavior evidence does not approve the
blocked full-window visual gate.

The previous Outliner and timeline widgets are retained by their existing dock
owners and replaced temporarily with a left brush shelf and bottom favorites.
The compact header gives room to the viewport. GoZ restores the original widgets,
pane widths, shelf height and exact Shape Editor target. Maya DAG exposes the
original scene tree in a temporary dialog.

The left shelf contains live Brush, Stroke, Alpha and Material previews plus two
color controls. SubTools stay above the right accordion. Geometry starts open;
Shift-click retains additional sections. The right tray becomes a drawer below
1100 logical pixels; recents disappear before primary settings. Size, Intensity
and Focal stay visible without horizontal scrolling. Secondary controls use
overflow. Maya viewport functions are available from Display.

Favorites default to **Standard, ClayBuildup, Move, DamStandard, TrimDynamic,
hPolish, Inflate, Pinch**. Right-click pins/unpins and moves favorites left/right.
Recents cannot reorder favorites. Tiles have original thumbnails, names, mnemonic
badges and purpose tooltips. B opens a stationary catalog; search and mnemonic
filtering never rearrange its tiles.

Draw Size is shared. Each brush retains intensity, focal shift, stroke, alpha,
LazyMouse and direction. Fresh DamStandard and Crease presets subtract. Reset
Current Brush rebuilds the configured preset while preserving the prior asset.
All indicators share actual active-brush state. Shift/Ctrl/Ctrl+Shift temporarily
show Smooth/Mask/Visibility.

Space previews pointer-relative quick controls; release commits, Escape rolls
back. RMB opens persistent controls and routes an active paint stroke through
Blender's native cancellation path. S/U/I use the same parameters. Focus loss
cancels previews. Popups retain the invoking viewport, clamp to the screen,
consume dismissal input and never warp the pointer. Tab reversibly expands the
native canvas.

## State and lifecycle

- `sculpt/preferences.py`: workspace-local `.landfall_studio/sculpt_ui.json`,
  version 1, for favorites, accordion choices and tray override. Tests redirect
  this path into disposable files; global Blender preferences are untouched.
- `sculpt/state.py`: scene-owned `BrushMemory` serializes per-brush settings into
  the saved `.blend`. Actual local native brush assets remain the sculpt source.
- `ui/sculpt_widgets.py` owns shared brush presentation, cursor controls and
  viewport provenance; `sculpt/layout.py` uses existing dock ownership throughout.
- Scoped reconciliation repairs native paint fallback rows lost during asset/mode
  transitions, then removes repairs by signature. RMB's native modal cancellation
  map is restored exactly. No nested paint modal was introduced.
- Conflicting Tentacle activation is suspended only while Sculpt owns inputs;
  the user's chosen activation key is never rebound or persisted.
- Native resizing waits for safe input state. A public maximize/restore round trip
  retires stale screen hover before area resizing, preserving overlays, finite
  grid state and OS pointer position.
- Compact spin fields explicitly lay out their editors: the inherited theme
  otherwise reduced NoButtons editors to one pixel. Thumbnail drawing restores
  the caller's GPU viewport, scissor, depth and blend state.
- Native menus establish their OS/transient owner before showing and avoid
  queued activation of the embedded parent after a popup takes focus.
- Popup dismissal sets Qt's documented `WA_NoMouseReplay` on the dismissal
  press itself, preventing replay into the sculpt canvas. The GUI sequence
  verifies an outside press closes the popup without changing the shape layer.

Native strokes/undo, Multires, topology recovery and base-resolution layer
recording remain intact. Layer creation/selection/recording refreshes the native
sculpt session against the selected shape-key buffer. Raising Multires stops
base-layer REC; high-resolution grids remain shared displacement.

## Verification

Blender 5.2.2 LTS / Python 3.13 / PySide6 6.12 on Windows, isolated factory scenes,
workspace-local profiles and synthetic native/Qt input:

| Evidence | Result | Scope |
|---|---|---|
| `sculpt-design/verification.json` | 10 passed; no page errors | Clickable prototype and three desktop sizes |
| `sculpt_ux2_gui_results_scale{100,125,150}.json` | 44 passed per scale; 0 failed | Actual Qt DPR 1.00 / 1.25 / 1.50; all three native window sizes |
| `zbrush_sculpt_gui_results.json` | 93 passed; 0 failed | Strokes, undo/redo, masks, SubTools, subdivision, layers, exact return |
| `zbrush_sculpt_results.json` | 77 passed; 0 failed | Native geometry, topology recovery, high-resolution deformation, base-layer REC |
| `sculpt_ux2_data_results.json` | 10 passed; 0 failed | Brush state, reset, favorites/recents, save/reopen |
| `controls_gui_results.json` | 71 passed; 0 failed | Maya control/UI regressions |
| `controls_data_results.json` | 121 passed; 0 failed | Existing controls data/dispatch baseline from this task |
| `zbrush_density_results.json` | PASS | Live Multires silhouette at 252,216 triangles and native Q/W/E/R |
| Full native window comparison | **BLOCKED** | Blank/stale desktop GPU presentation prevents visual approval |

Run `scripts/check_sculpt_design.mjs` and `scripts/check_sculpt_ux2.ps1`.
`sculpt_ux2_qa_summary.json` records process exit, result freshness, actual DPR
and assertion counts. Passing behavior assertions does not override the visual
gate. The new GUI sequence checks the first stroke into the selected shape layer
after popup dismissal, RMB geometry cancellation, second-viewport provenance,
focus loss, Tab with pen controls disabled, exact modal-map restoration, restored
dock dimensions and three repeated handoffs. The original sculpt suite supplies
mask/SubTool/subdivision/layer/undo/return session coverage.

## Remaining acceptance boundaries

The presentation probe reproduces the blank GPU window in factory Blender
**before registering Studio**, on OpenGL and Vulkan. Qt surfaces and state keep
updating. Blender's internal screenshot contains the correctly rendered creature.
This evidence cannot establish that a full native window is visually correct on
this host. Reproduce with `scripts/diagnose_sculpt_presentation.py`; inspect
`presentation_opengl_0_bare.png`, `presentation_vulkan_0_bare.png`,
`ux2_blender_pixels.png` and probe logs. No driver, Windows graphics setting or
global Blender preference was changed. The nine native window captures are
diagnostic evidence, not approved references.

Physical tablet pressure/eraser/barrel buttons, real multi-monitor mixed-DPI moves,
and exact ZBrush algorithms/physical feel remain separate validation boundaries.
External Maya interchange remains **BLOCKED** by the previously established Maya
2024 initialization failure (`0xC0000005`). GoZ is the internal Studio Object/Edit/
Shape Editor handoff; external Maya transfer is not claimed.

Reference direction: [Maxon's shelf and tray layout](https://help.maxon.net/zbr/en-us/Content/html/getting-started/finding-your-way-around/finding-your-way-around.html).
Brush algorithms remain configured Blender equivalents. The artwork is original.
Popup semantics: [Qt widget attributes](https://doc.qt.io/qt-6.12/qt.html).

