# Landfall Studio — fresh-settings native UX acceptance

Historical source snapshot: eight production files changed in the later
generated-asset/command round. See
[INSTANCE_LIFECYCLE_REVIEW.md](INSTANCE_LIFECYCLE_REVIEW.md) for its separate
current-source validation. This 28-suite record retains its original provenance.

Accepted **2026-10-17**, Blender **5.2.2 LTS**, native **PySide6** on Windows.
The application-wide polish is implemented. This round strengthens its evidence
without changing production code or ordinary preference ownership.

The authoritative [final aggregate](fresh_ui_final_acceptance.json) accepts
**28/28 suites**. It combines the unchanged-source
[28-suite matrix](fresh_ui_acceptance.json), generated at **05:38:59Z**, with one
affected-only preference-test recheck, generated at **05:39:59Z**. It is not one
untouched all-source run. Original results, source hashes and the correction are
preserved under `fresh-ui-regressions/`.

| Scenario | Accepted evidence |
|---|---|
| Application UI | 228/228 at actual Qt DPR 1.00; 229/229 at 1.25 and 1.50. Each covers 1280×720, 1920×1080 and 2560×1440, 91-button inventory, actual operator availability, Qt menus and guarded Windows mouse clicks. Inventory does not mean every command/topology combination was executed. |
| Inspector history | 100/100 at each scale; native Undo/Redo, exact cancellation, retained typed input, shader presets and stale-target recovery. |
| Workspace lifecycle | 63/63 at each scale; repeated focus and model/sculpt transitions, original layout return and normal teardown. |
| Modeling input | Controls 71/71, Channel stability 13/13, native scrub/typed inputs 69/69. |
| Sculpt input | Synthetic pen 47/47; sculpt controls 93/93; reference palettes 56/56; cursor/grid/zoom feedback 13/13. |
| Files/integration | File lifecycle 16/16; rotation/sculpt/save-reopen/GoZ integration 78/78. |
| Continuous artist session | 48/48, all twenty critical stages; actual base/detail paint, Smooth, mask/clear, SubTool rows, subdivision, save/reopen and exact Shape Editor return. |
| Native numerical control | Separate Blender-only process, no Studio/Qt bootstrap. Four no-stroke rebuilds exact; ten history cycles within the documented evaluated-surface bounds; complete Basis/layer buffers exact. |
| Dense sculpt | 252,216 triangles; live silhouette redraws and native brush restored. |
| Scene/data | Controls 122/122, panels 15/15, sculpt 77/77, fresh brush memory 12/12, reference features 117/117; character assertions and six Hypershade tests pass. |

All accepted processes exit **0**, results are fresh, and logs pass the Python
traceback/access-violation gates. Some logs contain deprecation, deliberate
nonuniform-scale, brush-append or small shutdown-allocation diagnostics. This
is not a warning-free claim.

## Fresh stores and the persistence correction

`tests/bootstrap_native_ui.py` activates the existing upstream UITK TestSandbox
before Studio construction. Each of the **27 Studio suites** verifies a local
INI QSettings round trip and local settings/preset roots. All **20 Studio GUI
suites** additionally verify the actual live Switchboard backend. The one
Blender-only numerical control deliberately does not import Studio or Qt.
Production tool-window preferences remain per Windows user.

Some existing sculpt fixtures override the bootstrap path with test-owned
preference files. The matrix therefore establishes fresh Blender/UITK stores
and test-owned sculpt preferences, not absence-before-load for every overridden
sculpt file. Workspace GUI tests explicitly check the approved initial favorites
and default Geometry/Masking state before changing them.

Independent review found a concrete persistence-test confound: the old fixed
`ux2_preferences.json` already held the asserted SH-first end state. Its pre-run
contents/hash/timestamps are preserved in
`fresh-ui-regressions/20261017T052635Z/brush_memory_legacy_preferences_observation.json`.
The data fixture now uses the bootstrap's unique path, or a UUID path standalone.
It asserts the file is absent and the approved eight favorites are initially in
order before changing, saving and reloading them. All original ten assertions
remain; the affected recheck passes **12/12**, with the actual path and absent
starting state recorded. No unrelated GUI retest was required for this test-only
correction. The final aggregate records its old/new hashes and superseding result.

## Independent review and use

Fresh read-only review: **8/10, integrated and worthwhile**. All four prior
directives are landed; no remaining material blocker was found in the reviewed
workflows. The reviewer verified all 136 current manifest hashes and the recheck
script hash. Its [full verdict](fresh_ui_independent_review.md) distinguishes
the accepted inputs from physical feel and exhaustive functionality.

Run `scripts/check_inspector_history.ps1` for a new complete matrix. The separate
`scripts/recheck_fresh_brush_memory.ps1` reproduces this one-fixture follow-up
against the preserved matrix; it requires exactly that fixture's hash to differ.
Fixed-name raw files may contain earlier evidence: use each aggregate's
timestamped `runs[].result`, `log` and `isolation_report` paths.

See [FULL_UX_REVIEW.md](FULL_UX_REVIEW.md) for the implemented repairs and
[FRIEND_QUICK_START.md](FRIEND_QUICK_START.md) for using the workspace.
The [local handoff rehearsal](LOCAL_HANDOFF_REHEARSAL.md) separately verifies a
physically copied Unicode-path runtime and relative external texture through
fresh-process reopen.

The checked workspace supports a controlled friend trial. Physical pen/driver
feel, the friend's machine, whole-window GPU capture, dependency/license
packaging and successful external Maya conversion remain separate gates.
The [Maya diagnosis](MAYA_RUNTIME_DIAGNOSIS.md) records a native standalone-import
crash without Studio; no repair or successful conversion is claimed. Exact
Maya/ZBrush algorithm parity and exhaustive product certification are not claimed.
