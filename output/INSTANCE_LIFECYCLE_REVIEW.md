# Generated assets, modeling commands and input ownership

This is a follow-up to the application-wide UX review, on **2026-10-17**.
The earlier fresh-settings 28-suite acceptance is a historical source snapshot.
Eight production files changed in this round; that earlier acceptance must not
be presented as a test of this newer source. **PASS: 15/15 affected native suites,
1,046 checks**, generated **06:42:40Z**. The authoritative current-source record is
[instance_lifecycle_acceptance.json](instance_lifecycle_acceptance.json), with
timestamped evidence in `instance-lifecycle/20261017T063553Z/`.
The first frozen **14/14** matrix passed **1,040 checks**. A subsequent actual
Layers GoZ probe found one redundant boundary; the current **15-suite** run
includes its fix and regression and passes on final frozen source. The first matrix retains its separate snapshot
in `instance_lifecycle_14_acceptance.json` and timestamped evidence.

## Problems found and repaired

| Observed behavior | Resulting behavior |
|---|---|
| ArrayMesh offsets and NanoMesh placements drift when the object or its parent moves, rotates or scales. All ten original native data checks failed. | Generated helpers use native parenting and the asset's local coordinates. Rename retains helper identity; frozen placements also travel with their asset. |
| Copied SubTools and recovery/clipboard snapshots can share mutable generated helpers. | Copies receive independent helper objects, placement meshes and Geometry Nodes groups where needed. Linked Model instances share the authored mesh while retaining independent placement helpers. |
| Changing array settings removes the assigned Curve path. | Cleanup only retires numbered Array stages. New stages precede owned post-processing modifiers; existing artist modifier interleaving is preserved. |
| Old, unparented helpers are not repaired by ordinary Sculpt entry. | Entry adopts legacy Array/Nano helpers. The regression moves the object before entry and verifies its authored local geometry afterward. |
| Edit Duplicate advertises Ctrl+D, but the Maya profile has no corresponding binding and the menu starts Blender's move modal. | Studio Duplicate copies in place, selects the copy, and leaves W available to move it. Menu, native Maya Ctrl+D and Qt Ctrl+D use one native operator. |
| Duplicate can inherit the last Instance setting. | Ordinary Duplicate explicitly requests independent mesh data; Instance explicitly shares it. The linked flag is not saved as an implicit next-command default. |
| Qt/menu Repeat Last lacks the native Undo owner supplied by viewport G. | These routes explicitly invoke the existing native Undo-capable Repeat operator. Each tested repeat removes in one Undo. |
| An unhandled shortcut starts in a numeric input, then propagates to a generic Qt parent with no global focusWidget and activates a scene command. | The existing input filter retains the originating widget/key through its ancestor chain until release or interruption. It retains no native QKeyEvent. Text handling remains local; the next button shortcut works. |
| After actual GoZ Return, the first modeling transform Undo reopens Sculpt and its tray. | Return records an explicit native modeling-mode boundary. Undoing the transform stays in Modeling. Undo/Redo across the boundary itself restores the appropriate mode and retains generated geometry. |
| Layers GoZ to Shape Editor records both that boundary and an outer command snapshot, requiring an empty Undo before returning to Sculpt. | Both return buttons share one native boundary owner; other layer edits retain their normal Undo. |

No alternate scene history, Qt application, shortcut owner or scene dispatcher
was introduced. Native strokes, the artist's base mesh and existing topology
protection remain in place.

## Evidence and fixture corrections

- Original data baseline: `instance_transform_data_baseline.json`, **0/10**.
  Transform drift reached 10.77 local units in the translation fixture.
- Preservation diagnostic: **19/20**, with the legacy Nano migration failure
  retained. Ordinary-entry migration correction: `instance_transform_data_migrated.json`,
  **20/20**.
- Initial GUI native keys were consumed by its factory first-launch splash.
  Disabling/resetting the splash at fixture startup made native Undo/Redo run.
  Sidebar Redo initially targeted a non-focusable frame while a DenseSpin owned
  text focus; focusing the actual live button corrected that fixture route.
  These were test corrections, not production history fixes.
- Actual Return-button baseline: `instance_transform_gui_actual_return.json`,
  **25 pass / 2 fail**; both failures reopen Sculpt on the first modeling Undo.
  Fixed boundary diagnostic: `instance_transform_gui_mode_boundary.json`, **33/33**.
- `model_duplicate_gui_text_trace.json` preserves the real input propagation
  failure. Per-event Python attributes and wrapper identity were insufficient;
  those rejected experiments remain in their diagnostic files.
- `model_duplicate_gui_key_owner.json`, **45/45**, exercises actual Qt menu
  clicks, native Maya Ctrl+D/G, Qt Ctrl+D/G, menu Repeat, Undo/Redo, text-key
  ownership, UV/shape-key/skin-weight preservation, linked mesh semantics,
  generated-helper independence and Sculpt Ctrl+D Divide.
- Layers GoZ actual-button baseline: `layer_goz_boundary_probe_visible.json`,
  **5 pass / 1 fail**. The first Undo stays identically in Object mode; the
  second reaches Sculpt. Fixed `layer_goz_history_gui_single_owner.json`, **6/6**,
  verifies one Undo restores the actual Sculpt tray, Redo restores the exact
  Shape Editor target, and the next model edit undoes while staying in Modeling.
  Basis/layer arrays remain exact. The first probe never expanded the collapsed
  Layers section and is retained as an invalid click-fixture diagnostic.

The final source-frozen matrix supersedes these diagnostics for acceptance.
All **140 manifest hashes** match before/after testing. Every process exits with code 0
with a fresh complete result and passes traceback/access-violation gates.
Logs are not warning-free. Eleven Studio GUI processes verify actual live
Switchboard INI ownership; three background processes verify local guarded
Qt stores. The separate native numerical control imports no Studio/Qt.
Fixed-name older results are preserved; every run has a timestamped evidence copy.

| Native final-source suite | Checks |
|---|---:|
| Generated asset data / actual GUI lifecycle | 20 / 33 |
| Model Duplicate, Repeat and text-key ownership | 45 |
| Actual layer GoZ history and exact target | 6 |
| Inspector history | 100 |
| Application UI, three window sizes | 229 |
| Modeling controls / sculpt controls | 71 / 93 |
| Integrated workflows / continuous artist session | 78 / 48 |
| Native Multires precision control | 10 |
| Workspace / reference GUI | 63 / 56 |
| Sculpt data / reference data | 77 / 117 |

GUI suites reporting DPR verify **1.25**; the application sweep includes
1280×720, 1920×1080 and 2560×1440. Current panel captures were visually inspected.
The older 28-suite baseline covers 100%, 125% and 150% on its historical source;
this affected matrix does not relabel it as a final-source three-scale run.
Launcher preflight also passes Blender 5.2.2 with local dependencies, without installs
or downloads: `instance_lifecycle_launcher_preflight.json`.

Reproduce from the workspace with:

```powershell
& ./Blend/scripts/check_instance_lifecycle.ps1
```

The [independent read-only review](instance_lifecycle_independent_review.md)
rates the tested Studio workflows **8/10, integrated and worthwhile**, with no
material blocker in those routes. The raw native duplicate bypass remains open;
that score does not certify the broader replacement goal.

## Boundaries

The fixed duplicate routes are Studio's Edit Duplicate/Instance, Maya Ctrl+D,
Qt Ctrl+D and the tested Repeat routes. Native Blender Shift+D/F3 duplicates
are isolated afterwards by a depsgraph pre-handler (later follow-up: 196/196 in
`test_native_duplicate_gui.py`). Helper resource retirement after deleting source assets
has not been certified.

This pass does not certify a physical pen/driver, the friend's clean machine,
whole-window GPU capture, successful external Maya conversion, a redistributable
installer, or exact proprietary Maya/ZBrush algorithms. The broad replacement
goal remains active.
