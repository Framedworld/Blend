# Native inspector history and interaction review

2026-10-16–17. This is the second workflow review after the full Studio UX pass.
The full Maya/ZBrush replacement objective remains active; see
[REPLACEMENT_WORKFLOW_READINESS.md](REPLACEMENT_WORKFLOW_READINESS.md) for open
integrated workflow findings.

## Demonstrated defects and repairs

The baseline native probe typed X=7.5 after a native move to X=2. Undo jumped to
X=0 and Redo recovered only X=2. Direct Qt property edits were missing from
Blender's history. The repaired native probe restores X=2, then redoes X=7.5.

Studio now commits inspector changes through one internal native Undo operator,
using the existing viewport context helper. Callback tokens exist only for the
synchronous call; Redo restores Blender's history rather than replaying a
closure against old scene objects. There is no second scene Undo stack or new
application event filter.

Affected interfaces: Attribute Editor, Channel Box, SHAPES/INPUTS, Modifier
Stack, Geometry Nodes Group Inputs, Shape/Skin actions and Hypershade. Shape,
material and Channel Box slider drags preview live and commit once. Escape,
focus loss, selection changes, a different scene edit, deletion, file reload
and unregister retire preview ownership. Native viewport operations retain
their existing modal history owner.

Additional defects exposed by actual inputs:

- An upstream Pivot options initializer was decorated as a scene edit. Merely
  initializing that menu could clear Redo. The decorator now belongs to the
  actual Transfer Pivot action.
- Native slider press ordering could add an initial small shape-weight change
  before starting a drag. Shape/material sliders now share the existing direct
  tip slider with explicit press ownership. Handle grabs retain their offset;
  track taps still move to the touched value.
- Geometry Nodes 5.2 socket values were absent from the history comparison.
  Exact native socket values now participate, including values hidden by display
  rounding.
- Pending Channel Box text could resolve a new selection when committed. The
  controller validates displayed/live targets before mutation; selection changes
  discard typing and restore original scrub previews. Open editors survive
  ordinary refresh even during native focus handoff.
- The Channel Box INPUTS extension could retain freed object RNA after Undo.
  Refresh now rebinds live references and rejects obsolete selection callbacks.
- A stationary material-handle tap could quantize an authored value to the
  displayed hundredth. Untouched gestures preserve exact native precision and
  create no history entry.
- Chrome, Gold, Car Paint and Subsurface Skin buttons referenced names missing
  from the upstream shader catalog. Studio now extends the existing native
  material engine with their editable Principled settings. All eight visible
  presets are exercised through creation, assignment, Undo and Redo.
- Native viewport MMB cancellation restored transforms but left custom
  properties and modifier/GN inputs changed. One captured channel session now
  retains exact raw values, original targets and cumulative integer motion.
  Escape/RMB restores complete baselines; native history still owns the drag.
- String, Object, Collection, Material and Vector sockets could be presented as
  editable zero-valued floats. They now show read-only typed values and point to
  the native editor. Channel Box, Modifier Stack and Group Inputs use the same
  editability contract. Nonnumeric/nonfinite input is rejected before mutation;
  custom booleans do not enter continuous numeric dragging.
- Custom menu activation could open then dismiss File on its next native focus
  message. QMenuBar now owns its normal activation and popup lifecycle. Real
  label clicks/Escape replace menu-availability-only evidence for this path.
- Shape/Skin's cramped weight editor and clipped action labels are repaired.
  The panel scrolls through the existing pen owner, uses two-column actions and
  shares the compact numeric editor with Attribute Editor. Long names elide
  with complete tooltips; the morph status badge retains its own space.
- The 125% matrix exposed a wider shared-stack and first-resize race. Dynamic
  AE/Channel/Modifier/material labels now share elision. Window extent changes
  queue sizing until Blender's area reflow completes, and native FINISHED no
  longer retires an intent before its actual target dimension is reached.
  The targeted 125% run passes 211 checks, with a 429 DIP sidebar at 1280/1920/2560.

## Acceptance evidence

The complete focused native suite passes **100/100** in
`scene_edit_history_gui_presets.json`. Its source is
`tests/test_scene_edit_history_gui.py`. It uses real Qt control events and native
simulated viewport Z/Shift-Z against a disposable Blender scene. It verifies
actual Blender values, modifier/node presence, shader assignments, exact
baselines, one-step grouping, independent preceding history, interruption,
file-replacement cleanup and adapter reinstall.

The final source-stable matrix is generated by
`scripts/check_inspector_history.ps1` into
`inspector_history_acceptance.json`, with separate results under
`history-regressions/`. The script checks process exit, fresh complete JSON,
minimum scenario counts, actual Qt DPR, clean callback logs and unchanged source
hashes across the matrix. Old frozen acceptance JSON is preserved; earlier
diagnostic failures are not promoted to PASS.

**Final acceptance: 23/23 suites PASS**, recorded in
`inspector_history_final_acceptance.json`. Inspector history passes 100/100,
full UX passes 228/228, 229/229 and 229/229, and workspace/focus passes 63/63 at
actual DPR 1.00/1.25/1.50 respectively. Native channel coverage passes 69/69.
All accepted runs exit normally with fresh results and clean callback/crash logs.

Production source is unchanged across the frozen matrix and two affected-only
fixture rechecks. The original matrix retains 21 passes and two failures;
`scripts/recheck_ux_fixtures.ps1` verifies that only the Channel stability and
integrated-workflow test fixtures changed, records both hashes and writes the
separate final aggregate. The former waits for pending startup layout before
observation (all 13 original checks retained). The latter avoids reactivating
the native parent while typing into its existing delegate and adds a 300 ms
idle check for both rotation modes (76 original checks plus two). This is a
documented composite acceptance, not one untouched all-source run. Use the final
aggregate's `runs[].result` paths; fixed-name raw results may be historical.

The native viewport probe passed
11/11; actual custom/INPUTS cancellation fixes passed28/28, then typed sockets,
boolean channels, integer motion and independent preceding history passed59/59.
The expanded presentation suite passed69/69. A new display matrix checks actual
menu clicks, field readability, child bounds, long names, bottom action reach,
light pen taps and pen scrolling. Earlier diagnostic/interrupted matrices are
retained separately and do not certify the final source.

The integrated follow-up now passes **78/78** native GUI scenarios for native
quaternion/axis-angle rotations, shared Multires detail, exact layer return,
two-object ownership, saved-file tray context and modifier removal recovery.
See `REPLACEMENT_WORKFLOW_READINESS.md` for its measured surface tolerance and
the preserved failure baselines. The final matrix includes this workflow plus
sculpt, brush persistence and reference-feature data regressions.

A later stress run exposed a Qt style teardown access violation when ordinary
panel retrieval fully reapplied the theme to the cached Tentacle panel. Studio
now uses the same Switchboard lookup and initializes default styling once per
live widget. Explicit theme changes remain with their existing owner. The
final workspace runs pass 63/63 at 100%, 125% and 150%, with no repeated theme
applications during the final handoffs; the accepted matrix includes this repair.

## Limits and reproduction

The installed Blender 5.2.2 material API always creates a node tree and ignores
`use_nodes=False`. The test records that capability and verifies exact native
default graph/value restoration. It does not claim to exercise the older
non-node-material branch on this build.

Physical pen/driver feel, external Maya conversion, full GPU-window image
acceptance and clean-machine distribution remain separate gates. Native
Sculpt/Divide/GoZ, non-Euler rotation and shared smooth preview now have the
accepted integrated and regression evidence above. The independent final review
found no remaining material blocker within this scope; see `FINAL_UX_VERDICT.md`.

Keep the required local upstream repairs when reproducing this checkout:
`upstream/blendertk/blendertk/ui_utils/qt_dock.py` (live Area resolution) and
`upstream/tentacle/tentacle/slots/blender/pivot.py` (Undo belongs to the action),
plus `upstream/blendertk/blendertk/node_utils/attributes/channels/_channels.py`
(native rotation paths, values, animation, locks and defaults).
No source artist scene or working Blender session is used as a fixture.
