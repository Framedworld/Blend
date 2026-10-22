# Landfall Studio — friend quick start

This is the working Windows Studio workspace, with Blender modeling and the
ZBrush-inspired Sculpt Studio in one application. Save your own work as a new
`.blend` file. The included creature is a disposable example.

## Start

1. Use Blender **5.2 LTS**. This workspace was tested with **5.2.2**, Python
   **3.13**, and its local PySide6 dependencies. Another Blender/Python version
   needs separate verification.
2. Keep `Blend`, `upstream`, `.deps`, and the two `Open Landfall … .cmd` files
   together. Windows may hide `.deps`; include it when copying the workspace.
3. Double-click **Open Landfall Studio.cmd** for modeling, or **Open Landfall
   Sculpt Studio.cmd** for the creature demo. These open a fresh Blender process.
   Blender preferences and Sculpt Studio favorites use `.landfall_studio`,
   without installing an add-on into your regular Blender profile. Some tool-window
   settings are saved per Windows user and do not travel with this folder.

For a fresh copy, leave `.test_env` and `.landfall_studio` behind; they contain
local test fixtures and local session resources rather than application source.

The launcher checks the Blender version and required local files before opening.
If Blender is installed elsewhere, set `LANDFALL_BLENDER_EXE` to the full path to
your Blender 5.2 `blender.exe`. To check the workspace without launching, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Blend\scripts\launch_studio.ps1 -CheckOnly
```

## Get moving

| Task | Modeling controls |
|---|---|
| Select / Move / Rotate / Scale | Q / W / E / R |
| Selection | Click replaces; Shift toggles; Ctrl removes |
| Orbit / Pan / Zoom | Alt + left / middle / right drag |
| Frame selected / all | F / A |
| Smooth preview | 1 / 2 / 3 |
| Wire / Solid / Textured / Lit | 4 / 5 / 6 / 7 |
| Object/components; vertices / edges / faces / UV | F8; F9 / F10 / F11 / F12 |
| Undo / Redo | Z / Shift+Z (Edit menu also available) |
| Repeat command / recall tool | G / Y |
| Duplicate in place; move the selected copy | Ctrl+D; W |
| Set animation keys | S |
| Hotbox / marking menus | Hold Space / right-click |
| Save / Save As | Ctrl+S / Ctrl+Shift+S |
| Open / New | Ctrl+O / Ctrl+N |

**Help → Studio Controls…** shows these controls inside the application. Tooltips
describe button actions. Some commands need a mesh, selected components, a
material, or another context; menu availability follows Blender's actual poll.

## Panels that stay out of your way

- Plain wheel scrolls the panel, including when the pointer is over a numeric
  field. Hold **Ctrl** to intentionally adjust a value with the wheel.
- Click a number, type, then press **Enter** to commit. Idle panel updates retain
  unfinished input. A focused button keeps normal Space/Enter activation, and
  dialogs keep their keyboard input.
- Inspector edits participate in **Z / Shift+Z** Undo/Redo. A parameter drag
  commits once; **Escape** restores its starting value. Changing selection or
  replacing the file retires unfinished edits.
- **Edit → Duplicate Instance** shares the original mesh. Ordinary **Ctrl+D**
  makes independent mesh data. Both retain their own generated placement
  helpers. Native Blender Shift+D/F3 duplication also gives each copy its own
  generated helpers.
- Shape/Skin scrolls when space is short. Grab its background with the pen to
  scroll; a light tap activates a button. Hover an abbreviated production name
  to read the complete name.
- Nonnumeric Geometry Nodes sockets show their actual value read-only. Use the
  modifier's **Graph ↗** control for the native typed editor.
- Attribute Editor rotation uses degrees and preserves the object's native
  mode. Quaternion and axis-angle objects expose their native four components
  in Channel Box, so values, animation keys and locks address the same channels.
- **File → Import / Export → Maya ASCII (.ma, native)** opens and writes Maya
  geometry (hierarchy, meshes, UVs, hard edges) without Maya installed. Delete
  construction history in Maya first; `.mb`, shaders and rigs need Maya itself.
- Use the right-side tabs for Channels, Attribute Editor, Tool Settings,
  Modeling, Modifiers, Shape/Skin, Hypershade and Maya interchange.
- Floating editors move by their header and resize from their lower corner.
- **Ctrl+E** (and Edit Mesh → Extrude, the shelf and the Modeling Toolkit)
  extrudes faces in place and shows the Move manipulator along the face normal,
  as in Maya. Drag it to set Thickness; scale it to set Offset; or type values
  into the polyExtrudeFace1 caddy. Edges and vertices use the drag-extrude.
- Bevel/Extrude options operate the same modeling caddy. Commit or cancel before
  moving on. Moving or scaling the extruded faces is read back into the caddy;
  any other geometry change retires the caddy rather than overwriting that work.
- Parametric primitive INPUTS stop regenerating once the mesh has custom data
  that regeneration would destroy. Shape-key/shared/linked topology needs an
  independent modeling copy; keep the original for recovery.

## Sculpt Studio

Enter Sculpt mode from Studio; **GoZ Return** restores the modeling arrangement.
The Layers section's **GoZ to Shape Editor** returns to the remembered base
layer target. These are internal Studio handoffs.
It records a native mode boundary: undoing the next modeling edit stays in
Modeling; undoing the Return step itself reopens Sculpt.

- Favorites select with one click. **B → two letters** selects a brush.
- Hold **Space** for quick controls; release commits, Escape restores. Right-click
  opens the persistent version while idle; during a stroke it keeps cancellation.
- **Tab** hides/restores shelves and trays. **Shift** smooths, **Ctrl** masks,
  **Ctrl+Shift** changes visibility.
- Drag a right-tray title, button or empty space vertically with the pen to
  scroll. A drag cancels the pending button tap. Sliders keep their own gestures.
- The floor/grid starts off. Enable it from sculpt Display when desired.
- For Alt-click-release zoom, pulling away from the model zooms in and pushing
  toward it zooms out. A stroke hides the outer brush ring; the center crosshair
  tracks the tip.
- Shape-layer recording uses base vertices. Higher subdivision stops recording;
  Multires detail is shared displacement rather than independent shape-key data.
  The layer's GoZ button remembers the base target through Divide and save/reopen;
  each mesh retains its own target when switching from Modeling.

## Save and recover

Save a new `.blend` early, then use Ctrl+S regularly. Save As preserves a second
version. For a handoff, collect referenced textures and use **File → Make External
Paths Relative**; **Find Missing Files…** helps repair paths on another computer.
Keep original source assets and an earlier saved version before topology edits.

If the layout needs restoring, choose **Workspace → Modeling Standard** from the
top-right workspace selector. Reopening a saved file rebuilds the existing Qt
desktop owners. If startup fails, read the
launcher error first; it names the missing executable or workspace file. Keep
the error and `Blend/output/interactive_startup.json` when reporting a problem.

## Current boundaries

The current [workflow readiness ledger](REPLACEMENT_WORKFLOW_READINESS.md) records
the repaired inspector, rotation and sculpt-return workflows with native test
evidence. The latest frozen affected acceptance passes **15/15 suites, 1,046
checks**, including three window sizes at the current 125% scale, fresh local
test stores, native Undo/Redo, generated-asset copies and both GoZ return routes.
See the [current follow-up](INSTANCE_LIFECYCLE_REVIEW.md) and
[accepted evidence](instance_lifecycle_acceptance.json).
The earlier [fresh-settings review](FRESH_SETTINGS_UX_REVIEW.md) covers 28 suites
at 100%, 125% and 150% on its historical source snapshot, including a verified
fresh-file favorites/save-reload check. The native
[continuous artist session](CONTINUOUS_ARTIST_SESSION.md) also passes
48 checks with actual brush-authored base and detail work through save/reopen
and exact Shape Editor return.

The full UX report is [FULL_UX_REVIEW.md](FULL_UX_REVIEW.md), with actual test
evidence and limits. Mouse/keyboard and synthetic pen events were checked in
native Blender/Qt; physical pen-driver feel still needs hands-on testing.
Whole-window GPU screenshot acceptance remains blocked on this machine despite
working native widget captures. **External Maya interchange is not ready for a
friend's production files:** installed Maya 2024 standalone crashes during
initialization. Bridge failure handling is tested, but successful Maya conversion
requires a healthy Maya runtime and a separate round trip. Blender features are
adaptations; exact Maya/ZBrush algorithm parity is not certified.

This guide covers running the checked workspace. A redistributed installer or
public package still needs dependency/license packaging and a clean-machine
acceptance run.

The historical [local handoff rehearsal](LOCAL_HANDOFF_REHEARSAL.md) verifies relocation to
a spaces/Unicode path, fresh test settings, actual controls and relative external
textures through save/reopen. It uses the copied production entry point with a
test observer; your friend's own machine still needs its first launch check.
