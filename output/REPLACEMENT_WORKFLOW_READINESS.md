# Landfall Studio workflow readiness

The user goal remains a dependable Maya-style modeling workspace and a
ZBrush-style sculpt workspace, with convenient access to Blender's native
features. A button inventory or a successful small demo does not prove that
replacement workflow. This ledger supplements the full UX review.

Current round repairs asset-local Array/Nano helpers, independent snapshots,
consistent Model Duplicate/Repeat, text-key propagation and the explicit GoZ
history boundary, including the redundant Layers GoZ step. Its final frozen
matrix passes **15/15 suites, 1,046 checks**, with normal exits and fresh/store/
log/hash gates. Independent review: **8/10 for tested Studio workflows**.
Native Blender Shift+D/F3 duplication is now covered: a depsgraph pre-handler gives each native copy its own generated helpers; `test_native_duplicate_gui.py` passes 196/196 (hidden-desktop run, 2026-10-22). See
[INSTANCE_LIFECYCLE_REVIEW.md](INSTANCE_LIFECYCLE_REVIEW.md).

Previous native evidence: **28/28 accepted suites**, fresh Blender/UITK test stores,
and an affected-only **12/12** fresh-file favorites/brush-memory recheck on unchanged
production code. See [FRESH_SETTINGS_UX_REVIEW.md](FRESH_SETTINGS_UX_REVIEW.md) and
[fresh_ui_final_acceptance.json](fresh_ui_final_acceptance.json). The original
matrix and the one-fixture correction retain separate hashes/results. Physical
input, the friend's machine, whole-window GPU capture, external Maya and release
packaging remain separate gates.

## Current repair: native inspector history

Implemented and verified in the 100-scenario native inspector run
(`scene_edit_history_gui_presets.json`). Current acceptance is recorded in
`inspector_history_final_acceptance.json`: **23/23 suites**, unchanged production
source across the frozen matrix and two documented fixture-only rechecks.
History passes 100/100 at each actual DPR 1.00/1.25/1.50; full UX passes
228/228, 229/229 and 229/229; workspace/focus passes 63/63 at all three scales.

- Typed Attribute Editor and Channel Box values participate in native Undo/Redo.
- Modifier cards, INPUTS tree and Geometry Nodes window share the same history.
- Shape/material slider previews commit one complete gesture. Escape, focus
  loss, selection changes, deletion and file replacement retire their owners.
- Stationary material handle taps preserve authored precision and history.
- All eight visible shader preset buttons create and assign real shader graphs,
  with native Undo/Redo. Chrome, Gold, Car Paint and Subsurface Skin previously
  referenced absent upstream template names; Studio now supplies their native
  Principled preset settings through the existing material engine.
- Creating Pivot options no longer adds a scene-history step or clears Redo.
- Native highlighted-channel viewport MMB shares native Undo/Redo with Qt edits.
  Custom properties, modifiers, Geometry Nodes and primitive INPUTS now capture
  exact values at gesture start. Escape/RMB restores them; integer movement
  accumulates from that start rather than rounding every event to zero.
- Menu labels use Qt's normal activation/popup lifecycle. Manual foreign-parent
  activation could open then dismiss a File menu on its next native message.
- Shape/Skin now scrolls through the existing pointer owner and uses readable
  two-column actions and a shared compact weight editor. Long production names
  elide with full tooltips without imposing their width on the shared stack.
- A first-window-resize race could accept old area fractions before Blender
  reflowed them, leaving a narrow inspector. The existing resize queue now
  retains the intended minimum width until live geometry reaches it. The 125%
  1280/1920/2560 preflight passes 211 checks and preserves 429 DIP of sidebar width.

## Integrated workflow repairs — 2026-10-17

The independent workflow audit's two confirmed P1s now have native GUI repair
evidence in `history-regressions/replacement_workflows_recheck.json`: **78/78**.
The scoped native application UX gate is accepted. The independent final review
rates it 8/10 with no remaining material blocker in these bounded workflows;
see `FINAL_UX_VERDICT.md`.

| Priority | Observable gap | Next acceptance scenario |
|---|---|---|
| Repaired P1 | Layer/Divide could lose the exact Shape Editor target. Recording state is now owned by each mesh, restored on entry and retained while shared Multires detail uses Basis. Return changes the active key after leaving native Sculpt. | Named base delta, native high-detail stroke, Undo/Redo, save/reopen, actual GoZ button, repeated return and two meshes with colliding layer names pass. Deleted remembered targets do not select a different layer. |
| Repaired P1 | Non-Euler objects displayed/edited unused Euler storage. AE now edits actual orientation while preserving representation; Channel Box exposes native Quaternion W/X/Y/Z or Angle/Axis X/Y/Z for correct keys and locks. Native viewport rotation and cancellation preserve all raw representations. | Both modes pass real Qt edit, one-click channel, native Undo/Redo, key/indicator, four-component lock, identity reset, viewport MMB commit/Escape and mode-change orientation checks. Mixed modes cannot cross-wire component indices. |
| Repaired P1 | A GoZ tray click after reopening a file dereferenced a saved Window from the previous file and crashed Blender. | Sculpt provenance now stores pointer IDs and resolves only current Window/Area/Region owners. Popups resolve their originating live context; file load retires the saved origin. The same saved-file/button sequence now exits normally. |
| Verified integration | The initial duplicate-preview finding was disproved by the existing Multires-aware bridge. | The native workflow now covers mixed Multires/ordinary selections through 1/2/3, repeated GoZ and actual Modifier Delete/Undo recovery of the grids and detail. |

The unit-radius Multires fixture changes by about **0.0835 local units** under
native paint. Native float32 grid flush/rebuild introduces measured differences
up to **3.58e-7**; evaluated-surface comparisons use **1e-6 local units**. Shape-key
base and target data checks remain exact. The base-layer delta in this integration
fixture is seeded; native base brush recording has separate coverage in the
93-case sculpt GUI suite. The suite requires a native paint
modal and a surface change above 1e-4 before testing history or persistence.
Earlier failed diagnostics remain preserved and are not accepted results.

The later [continuous artist session](CONTINUOUS_ARTIST_SESSION.md) closes that
seeded-base gap: **48/48 native GUI checks at DPR 1.25** on the same production
source. Native strokes author both the base layer and high detail; Smooth,
mask/clear, real SubTool row switches, Divide, B-D-S, Undo/Redo, save/reopen and
the actual GoZ button preserve the complete work and exact target. Its separate
Blender-only control reproduces the tiny native grid-Undo error. The documented
evaluated-Undo allowance is 2e-6 maximum / 5e-8 RMS local units for this fixture;
Basis and layer buffers remain exact. This is separate acceptance evidence, not
an untouched expansion of the earlier frozen matrix.

Repeated mode stress also exposed a Qt style teardown access violation from
restyling an already cached Tentacle panel on every retrieval. Default styling
now initializes once per live Switchboard widget; explicit theme changes retain
their existing path. Final transition suites pass 63/63 at 100%, 125% and 150%
and exit normally, with that repair included.

## External and physical boundaries

The [local handoff rehearsal](LOCAL_HANDOFF_REHEARSAL.md) now passes **24/24
modeling and 27/27 sculpt/fresh-process checks at DPR 1.25**, from 5,665 physically
copied runtime files under a spaces/Unicode path. Actual module origins, copied
launcher preflight, native controls, fresh Blender/Qt test stores and a real
unpacked relative texture through save/reopen are verified. Both processes exit
normally and original source hashes remain unchanged. This adds relocation
evidence, while a friend's actual clean machine remains unverified.

The latest recorded Maya 2024 standalone initialization failed with
`0xC0000005`; successful external Maya interchange is blocked by that runtime.
The [three-environment diagnosis](MAYA_RUNTIME_DIAGNOSIS.md) now reproduces the
fault during standalone import before initialization or Studio execution;
Windows identifies `mayaLib0.dll` at offset `0x1067`. No runtime repair is claimed.
Synthetic native input checks do not certify physical tablet/driver feel or
mixed-monitor pen behavior. Whole-window GPU capture remains separately blocked
by the previously reproduced factory-Blender presentation problem; native Qt
widget captures remain usable. Clean-machine installation and redistributable
packaging have not been certified.

The full replacement objective remains **active**. Existing source artist files
and working Blender sessions are not the regression fixtures.

Current follow-up gate: scoped native UX acceptance **PASS**, with the composite
provenance recorded above. Independent review also identified unsupported GN
socket types and custom boolean dragging. Numeric
INPUTS now accepts finite scalar socket types; other sockets remain visible with
a native-editor hint. Custom toggles do not enter continuous numeric dragging.
The new 69-scenario native test exercises actual typed sockets and all three
field presentations. Earlier failed and
interrupted matrices are diagnostic evidence, not final acceptance.

Native baseline evidence for the two repaired workflow P1s:
`non_euler_rotation_baseline.json` (AE/Channels/MMB changed Euler storage with
zero orientation change in both quaternion and axis-angle modes) and
`sculpt_return_workflow_baseline.json` (Divide remembered the recorded layer,
but layer GoZ rejected Basis and direct Shape Editor return retained Basis).
