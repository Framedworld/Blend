# GoZ Sculpt Studio

Latest interaction polish: [pen taps, tray dragging, sliders and popup recovery](SCULPT_PEN_UX.md).

Latest: [supplied palette reference implementation](SCULPT_REFERENCE_PASS.md),
[native/reference comparison gallery](sculpt-reference-gallery.html), and
[feature map with adapted/unsupported boundaries](SCULPT_FEATURE_MAP.md).

The second UX pass is implemented. See [the current implementation and acceptance
report](SCULPT_UX_PASS2.md) and [the clickable UI prototype](sculpt-design/index.html).
Native behavior/data checks pass; full-window visual approval is currently
BLOCKED by blank/stale GPU presentation reproduced before Studio loads.

Implemented in the workspace's Landfall Studio source for Blender 5.2.2 LTS.
The sculpt desktop uses the existing Tentacle QApplication and PySide6 6.12.
The native Blender viewport, transform gizmos and sculpt engine remain the
rendering and geometry foundation. No second Qt runtime or startup installer
was added.

## Open and use

- `Open Landfall Studio.cmd` opens the normal Maya Studio desktop. Enter Sculpt
  through the workspace selector, native mode controls, shelf or other mode
  switches to engage the sculpt desktop automatically.
- `Open Landfall Sculpt Studio.cmd` opens a fresh, disposable creature example
  directly in Sculpt Studio. It leaves Blender running.
- The teal **GoZ: Return to Maya** control restores the previous Maya workspace,
  inspector page and shelf. A mesh entered from Edit Mode can return to Edit Mode.
- **GoZ to Shape Editor** selects the same real shape-key target in Studio's
  Shape Editor. This is an internal Studio handoff.

The compact header keeps Size, Intensity and Focal visible; secondary settings
use overflow. Brush/Stroke/Alpha/Material wells live on the left, stable favorites
replace the timeline, and SubTools stay above a single-open tool accordion.
Shift-click retains additional sections. On narrow windows recents disappear
and the right tray becomes a drawer. GoZ restores the original dock widgets and
dimensions. Favorites/tray choices are saved locally to the workspace.

## Controls

| Input | Result |
|---|---|
| Q / W / E / R | Draw / Move / Scale / Rotate in Sculpt mode |
| Blank LMB drag | Orbit |
| Shift during orbit | Nearest principal orthographic view |
| Alt + blank LMB drag | Pan |
| Release Alt while continuing that drag | Pull away to zoom in; push toward the model to zoom out |
| Mesh LMB / Alt LMB / Shift LMB | Native sculpt / inverse / smooth |
| Alt click another visible mesh | Transfer Sculpt mode to that SubTool |
| Ctrl mesh drag / Ctrl Alt mesh drag | Paint / erase mask |
| Ctrl mesh click / Ctrl Alt mesh click | Blur / sharpen mask |
| Ctrl blank click | Invert mask |
| Ctrl blank drag | Box/lasso mask on overlap; clear on empty canvas |
| Ctrl Alt blank drag | Erase on overlap; fill on empty canvas |
| Ctrl blank drag with DynaMesh on and empty mask | Voxel remesh |
| Ctrl Shift drag / add Alt | Hide outside / inside box |
| Ctrl Shift blank click / empty drag | Show all / invert visibility |
| Ctrl Shift mesh click | Isolate the clicked face set |
| Ctrl numpad +/- | Grow / shrink mask |
| Ctrl Up / Down | Increase / decrease mask contrast |
| B, then two brush letters | Actual Qt brush palette |
| Space hold / release / Escape | Quick controls preview / commit / rollback |
| Plain RMB | Persistent quick controls; native cancel during a stroke |
| Tab | Native canvas focus mode; press again to restore |
| S / U / O | Draw Size / Z Intensity / Focal Shift slider (ZBrush defaults; I also opens Intensity) |
| X / L / Shift F / K or ? | X symmetry / LazyMouse / polyframe / help |
| Ctrl D / Shift D / D | Divide / lower / higher subdivision |
| Ctrl W | Group masked faces |

Maya Alt MMB/RMB navigation remains available. Transform tools own their drags;
the brush fallback is enabled only for Draw. Native strokes are invoked directly
by Blender's keymap, preserving its tablet input and undo path.

Sculpt starts with the grid and axes off. Floor remains an optional display
control; GoZ restores the exact preceding Maya grid state. Hover shows the brush
rings and a small center crosshair. During a native stroke the rings disappear
and the crosshair follows the live pen tip; release restores the rings. Focused
validation and native viewport images: [feedback pass](SCULPT_FEEDBACK_PASS.md).

Brush mnemonics: ST Standard, CB ClayBuildup, CL Clay, CR Crease, MV Move,
MT Move Topological, DS DamStandard, TD TrimDynamic, HP hPolish, IN Inflate,
PI Pinch, SH SnakeHook, SM Smooth, MP MaskPen, IM IMM Primitives.

The stroke and alpha wells change actual brush settings/resources. Color opens
a nonblocking Qt picker. Rgb selects the native sculpt color brush. M paints face
material assignments; right-click M to choose or create the paint material.
Rgb and M are now in the header overflow. Draw Size stays shared; intensity,
focal shift, stroke, alpha, LazyMouse and direction are retained per brush and
save with the scene. Fresh DamStandard/Crease subtract. Right-click favorites
to pin, unpin, reorder or Reset Current Brush. Temporary modifier indicators
restore the selected-brush presentation on release.

## Scene operations and continuity

| Area | Implementation |
|---|---|
| SubTools | Same scene mesh objects and parent paths as the Maya DAG; visibility, append, duplicate, delete, split, extract, merge and selection synchronize |
| Masked extraction | Native sculpt extraction of the current surface, with an editable Solidify thickness |
| Subdivision | Actual Multires levels; Maya 1/2/3 shares the same modifier |
| Delete lower | Stages a new base and reconstructs remaining levels, then validates the upper surface before switching |
| DynaMesh | Native volume-preserving voxel remesh; resolution is normalized to local mesh extent |
| ZRemesher | Native QuadriFlow, target face count, feature/boundary preservation and attribute transfer |
| PolyGroups | Actual sculpt face-set attributes, including connected islands and normal groups |
| Deformations | Mask-weighted base coordinate edits and native sculpt mesh filters on high Multires levels; selected base shape layers retain their topology |
| Layers | Real base-resolution shape keys, active recording target, strength, baking and Shape Editor focus |
| Canvas | Actual Qt buttons; native perspective, grid, local view, symmetry, frame, navigation, wire, x-ray, ghost, Solo and Xpose |
| Silhouette | GPU flat silhouette; live viewport depth for Multires grids, which evaluated mesh access omits in Sculpt mode |
| Points | Exact subdivision topology counts, with current active resolution and highest-resolution SubTool totals |

Topology-changing operations stage an evaluated sculpt copy for meshes carrying
shape keys, skin groups, armature modifiers or linked-object data. Ordinary
topology edits retain hidden in-memory recovery snapshots. **Recovery snapshots…**
restores an independent editable copy. Recovery objects are excluded from the
working SubTool list and Maya DAG. Original source asset files are never saved
by these commands.

Native sculpt bindings, shared transform tool maps, viewport shading and Qt pages
are restored on mode exit. Sculpt controls can be disabled without altering the
saved Maya/Hybrid profile. Popups retain native keyboard focus, and editable Qt
fields keep their text-entry keys.

## Verification

Latest machine-readable results:

- `sculpt_ux2_qa_summary.json`: 44 second-pass native GUI checks at each actual
  Qt DPR 1.00/1.25/1.50, including all three requested window sizes; 10 additional
  per-brush/save-reopen data checks. See the current report for visual limitations.

- `zbrush_sculpt_results.json`: **77 passed, 0 failed** native scene semantics
  and geometry checks, including high-resolution deformation and the base-layer
  recording policy.
- `zbrush_sculpt_gui_results.json`: **93 passed, 0 failed** native event queue
  and real Qt widget checks, including native strokes, undo/redo, transforms,
  masking, visibility, RGB/material painting and Shape Editor return.
- `zbrush_density_results.json`: Multires viewport/depth rendering with 252,216
  surface triangles and native Q/W/E/R events. The measured thumbnail capture
  timings are machine-specific and recorded in the result JSON; this is not a
  general frame-rate claim.
- `controls_gui_results.json` and `controls_data_results.json`: **71 GUI and
  121 dispatch/data checks passed**, rerun after the sculpt integration.
- `sculpt_phase02_regression.log` through the applicable phase 11 logs:
  existing integration suites, excluding the separately blocked Maya runtime.

Full-window captures include the actual embedded Qt desktop:
`zbrush_window_capture.png`, `zbrush_dense_window.png`, and the launch demo's
`zbrush_demo_window.png`. Separate live widget captures are also retained.

The GUI harness uses Blender event simulation and PySide6 QtTest, with native
popup focus checks. It does not replace a physical tablet acceptance test.

The final interactive launch was saved as `zbrush_sculpt_demo.blend` and left
open. `interactive_startup.json` confirms active PySide6/Tentacle, the
`ZBRUSH_STUDIO` dock and all three SubTools. A separate desktop process check
confirmed the saved Blender window was still running and responding after
startup; `zbrush_demo_window.png` captures that actual window.

## Practical boundaries

- Brush feel, falloff, voxel reconstruction and quad remeshing use Blender's
  algorithms and configured equivalents. Exact ZBrush algorithm parity is not
  certified.
- Ghost shows other SubTools as wire ghosts; Transp is a separate viewport x-ray
  control. Local symmetry uses the SubTool's native object-local axes.
- Keep Groups preserves QuadriFlow features and transfers face-set attributes;
  it is subject to QuadriFlow's topology behavior. Adapt uses smoothed normals.
- M paints native face material slots, and Rgb paints Blender color attributes.
  This does not implement ZBrush's material system.
- Shape keys record base vertices. New Layer/REC returns to base resolution;
  raising subdivision stops layer recording. Multires detail remains shared
  sculpt displacement. Unify Scale also requires base resolution.
- Physical pen pressure curves, eraser/barrel buttons, multiple monitors and
  every DPI/workspace arrangement still need device testing. Current GUI
  verification ran on Windows at the available display scale.
- External Maya interchange remains blocked by the Maya runtime failure recorded
  in `CONTROL_AUDIT.md`; the internal GoZ handoff does not depend on that runtime.

Reference inspected: [AIGODLIKE/Bbrush](https://github.com/AIGODLIKE/Bbrush),
manifest version 1.5.1, GPL-3.0-or-later. Its tablet interaction and silhouette
concepts informed the requested behavior. No Bbrush source was vendored.

