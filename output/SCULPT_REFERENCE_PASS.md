# Sculpt Studio — supplied reference pass

The native PySide6 right tray now follows the ten supplied ZBrush palettes:
SubTool, Geometry, ArrayMesh, NanoMesh, Layers, Deformation, Masking, PolyGroups,
Morph Target and Polypaint. Red-crossed sections were excluded; grey controls
were audited rather than treated as exclusions.

Review [the clickable comparison gallery](sculpt-reference-gallery.html),
[the full feature map](SCULPT_FEATURE_MAP.md),
[spacing/color/responsive specifications](SCULPT_TRAY_LAYOUT.md) and the editable native source at
`landfall_studio/ui/sculpt_tray.py`. The gallery compares the supplied screenshots
with actual QWidget captures. It does not simulate a connected sculpt engine.

## Native implementation

Compact paired controls, slate backgrounds, amber states, embedded value sliders,
nested palettes and the permanent SubTool list follow the reference arrangement.
Geometry starts expanded; Shift-click retains additional palettes. Workspace
preferences retain the chosen arrangement. The existing Qt application, dock
lifecycle, command dispatcher and keymap owner remain in use.

Blender supplies Multires, Subsurf, Face Sets, mask filters, native sculpt filters,
Boolean, Shrinkwrap, Array, Geometry Nodes and mesh color attributes. Additional
adapters provide stored visibility sets and poses, indexed masked deformations,
rest-target snapshots, deterministic surface instances and fixed-topology MDD
import/export. Source meshes with protected keys, rigs or Multires are staged
before topology edits. Array helper ownership and node-group copying isolate
duplicated SubTools.

Custom position, mask and color edits capture native Sculpt undo nodes. Generated
modifiers use native global history checkpoints. One Undo reverses the modifier
command; continuing farther through history may encounter an unchanged checkpoint.
Brushes, native strokes and physical tablet processing keep their existing engine.

## Validation

Tests run in disposable factory Blender scenes with isolated test preferences.
No artist scene or personal Blender profile was saved or replaced.

| Check | Result / evidence |
|---|---|
| Reference data operations | **117 passed, 0 failed** — `sculpt_reference_data_results.json`; geometry, masks, all deformation commands, layers, arrays, multi-index NanoMesh, helper isolation, protected sources, MDD retiming, save/reopen |
| Native sidebar actions and layout matrix | **55/55 at DPR 1.00; 56/56 at 1.25; 56/56 at 1.50** — `sculpt_reference_gui_scale100.json`, `sculpt_reference_gui_scale125.json`, `sculpt_reference_gui_scale150.json`; each verifies 1280×720, 1920×1080 and 2560×1440. Includes real Qt clicks/sliders, rejected NanoMesh enable, source selection, mask/group/color/Morph Undo, Array/NanoMesh Undo, modifier Redo, layer creation and GoZ return. The extra check at higher DPR verifies the narrow-window drawer. |
| Existing sculpt data | **77 passed, 0 failed** — `zbrush_sculpt_results.json` |
| Brush memory / save-reopen | **10 passed, 0 failed** — `sculpt_ux2_data_results.json` |
| Existing sculpt GUI | **93 passed, 0 failed** — `zbrush_sculpt_gui_results.json` |
| Existing workspace interactions | **44 passed, 0 failed** — `sculpt_ux2_gui_results_reference_final.json` |
| Maya controls | **71 passed, 0 failed** — `controls_gui_results.json` |
| Channel Box live-transform stability | **13 passed, 0 failed** — `channel_stability_gui_results.json` |
| Cursor / grid / zoom feedback | **13 passed, 0 failed** — `sculpt_feedback_gui_results.json` |
| Dense Multires silhouette | **PASS**, 252,216 triangles, 4 verified redraws; last capture 16.04 ms, maximum 25.96 ms — `zbrush_density_results.json` |
| Comparison viewer | **11 passed, no browser errors** — `sculpt_reference_gallery_results.json`; ten tab/image pairs and narrow viewer layout |
| Fresh interactive launch | **PASS** — untitled creature demo, native process responding, PySide6/Tentacle active, Sculpt Studio dock and three SubTools verified after 20 seconds; `interactive_startup.json`, PID 45772 |

Consolidated evidence and final source hashes: `sculpt_reference_acceptance.json`.
Actual opened tray width is 290 logical pixels at all nine size/scale combinations;
the existing edge strip uses the remaining dock width. Each requested native
window size was confirmed with its actual Windows rectangle.

The earlier headless fixture crashed in native Face Set initialization without an
initialized undo stack. The disposable test harness now establishes its baseline
before invoking that operator; the final 117-check run exits normally. Earlier
diagnostic logs remain available. An initially failing array Undo test is retained
in the diagnostic logs; the final native checkpoint fix passed the same gate.
The window-size matrix also caught proportional tray shrinkage; the dock lifecycle
now restores its intended logical width after resize. The final checks measure
the opened tray and the narrow-window drawer rather than assuming a hidden tray
must remain visible. Unset NanoMesh sources show an explicit choice and rejected
enable attempts restore the previous option state.

## Remaining acceptance boundaries

This is an implementation of useful native equivalents, not a certification of
every uncrossed ZBrush feature or proprietary algorithm. The feature map records
the differences per palette. BPR conversion, subdivision-time ReUV, NanoMesh
per-face clipping, independent layer color/mask recording and several advanced
array stage/profile and PolyGroup options remain unavailable. Disabled controls
explain the boundary; some advanced options are documented without a control.

Native QWidget palette images are verified. Full-window GPU visual acceptance
remains **BLOCKED** by the previously reproduced blank/stale desktop capture issue
in factory Blender. Do not treat those diagnostic whole-window images as approved
visual comparisons. Physical tablet feel, exact ZBrush algorithms and the external
Maya runtime remain separate validation boundaries.

## Research

The [feature map](SCULPT_FEATURE_MAP.md) links all ten Maxon Tool/Polymesh reference
pages and Blender Face Sets documentation. Installed Blender 5.2 RNA was probed
directly (`sculpt_native_capabilities.json`) before wiring commands. Native history
behavior was also checked in isolated GUI probes. Blender's
[undo architecture](https://developer.blender.org/docs/features/core/undo/)
distinguishes the mode-specific and global data histories used here.
