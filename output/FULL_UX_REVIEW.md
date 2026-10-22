# Landfall Studio — full UX review and polish

Reviewed and repaired on **2026-10-16–17**, across the Studio application, beyond
Sculpt mode. Target: Windows, Blender **5.2.2 LTS**, Python **3.13**, native
**PySide6**. The existing Qt application, command dispatcher, keymap and dock
lifecycle remain the owners of their respective behavior.

**Current follow-up:** generated-asset lifecycle, Model Duplicate/Repeat,
text-key ownership and the GoZ-to-modeling Undo boundary have further repairs.
Eight production files changed. Their final frozen affected matrix passes
**15/15 suites, 1,046 checks**, all normal exits with fresh/local-store/log/hash gates.
The fresh independent review rates the tested Studio workflows **8/10**.
The application sweep covers three window sizes at actual DPR 1.25;
see [INSTANCE_LIFECYCLE_REVIEW.md](INSTANCE_LIFECYCLE_REVIEW.md). The 28-suite
snapshot below predates these changes and is not current-source certification.

**Previous acceptance: 28/28 native suites**, with fresh Blender/UITK test stores
and one explicitly documented fresh-file preference recheck (**12/12**).
All accepted processes exit normally, logs pass traceback/access-violation gates,
and production source is unchanged. See
[FRESH_SETTINGS_UX_REVIEW.md](FRESH_SETTINGS_UX_REVIEW.md) and the authoritative
[fresh_ui_final_acceptance.json](fresh_ui_final_acceptance.json). This supplements
the earlier accepted matrices below and retains their original provenance.

**Workflow follow-up:** the native inspector history review now repairs missing
Undo/Redo steps, cancelled-gesture ownership, stale INPUTS references and four
broken shader preset mappings. See [INSPECTOR_HISTORY_REVIEW.md](INSPECTOR_HISTORY_REVIEW.md)
and its separate source-stable regression evidence. The broader replacement
objective is still active: [REPLACEMENT_WORKFLOW_READINESS.md](REPLACEMENT_WORKFLOW_READINESS.md)
records the later sculpt/Multires return, rotation, saved-viewport lifecycle and
Shape/Skin readability repairs. The final integrated workflow passes **78/78**
native GUI checks and the application acceptance is **23/23 suites**.
The earlier acceptance below is a dated baseline, not certification of every
replacement workflow or of later source changes.

**Baseline result:** the scoped automated UX acceptance is recorded in
[full_ux_acceptance.json](full_ux_acceptance.json). This is a reviewed working
workspace, not a claim of exhaustive product certification. A friend's first
session should start with [FRIEND_QUICK_START.md](FRIEND_QUICK_START.md).

## Prior composite acceptance — 2026-10-17

**PASS for the scoped native UX review.** The result for this earlier snapshot is
[inspector_history_final_acceptance.json](inspector_history_final_acceptance.json).
The independent [final verdict](FINAL_UX_VERDICT.md) rates this pass **8/10** and
finds no remaining material blocker in the reviewed workflows. This supports a
friend's controlled trial of the checked workspace; exhaustive product or
Maya/ZBrush replacement certification is not claimed.

| Current check | Accepted result |
|---|---|
| Full application UX | **228/228 at 100%, 229/229 at 125%, 229/229 at 150% actual Qt scaling**; each covers 1280×720, 1920×1080 and 2560×1440, 91 sidebar buttons, native Qt menu clicks and foreground/target-guarded Windows mouse clicks. |
| Native inspector Undo/Redo | **100/100 at each scale**; actual data, gesture cancellation, no-op precision, shader presets and stale-target recovery. |
| Workspace/focus/GoZ | **63/63 at each scale**; repeated focus and mode transitions, original layout return and the repaired Qt restyling crash. |
| Modeling / Channels | Controls **71/71**, Channel stability **13/13**, native channel scrub and typed GN inputs **69/69**. |
| Sculpt and integrated return | Pen **47/47**, sculpt controls **93/93**, rotation/sculpt/save-reopen/GoZ integration **78/78**. |
| Continuous artist session follow-up | **48/48 at DPR 1.25**, real brush-authored base → Smooth/mask → SubTools → Divide/detail → save/reopen → exact Shape Editor return; separate Blender-only precision control also passes. See [CONTINUOUS_ARTIST_SESSION.md](CONTINUOUS_ARTIST_SESSION.md). |
| Local handoff follow-up | **24/24 modeling + 27/27 sculpt/fresh-process checks at DPR 1.25**, physically relocated runtime, fresh Blender/Qt test stores, real relative external texture and native save/reopen. See [LOCAL_HANDOFF_REHEARSAL.md](LOCAL_HANDOFF_REHEARSAL.md). |
| Files and data | File lifecycle **16/16**; controls **122/122**, panels **15/15**, sculpt **77/77**, brush memory **10/10**, reference features **117/117**; character and Hypershade suites pass. |
| Launch | Windows launcher preflight **PASS** on Blender 5.2.2 LTS; no installation or download. |

All 23 accepted suites exit normally with fresh complete results and clean
callback/access-violation logs. Production source hashes are unchanged across
all runs. Acceptance combines the frozen 23-suite matrix with affected-only
rechecks of **two test fixtures**; it is not one untouched all-source run.
The original matrix's two failures and old/new fixture hashes remain preserved.
Channel stability now waits for pending startup resize work before observing
motion. The rotation fixture types into its existing click-opened editor without
reactivating the native parent, and adds a 300 ms idle-editor check in both modes.
The behavioral assertions remain intact. Reproduction and provenance are in
`scripts/check_inspector_history.ps1`, `scripts/recheck_ux_fixtures.ps1` and the
final aggregate's `runs` entries. Fixed-name raw result files may be historical;
use the accepted `history-regressions/` paths recorded by that aggregate.

The additional continuous session has its own acceptance aggregate and does not
replace or relabel the 23-suite matrix. Production hashes match that matrix;
the follow-up adds native end-to-end evidence without product-code changes.

## Coverage

Launch/preflight; file New/Open/Save/Save As and project paths; menu and shelf
actions; mouse/keyboard focus; viewport menus; selection and transform panels;
Outliner; Channels and primitive INPUTS; Attribute Editor; Tool Settings;
modeling caddies and Quad Draw; modifiers/Geometry Nodes inputs; Shape/Skin;
Hypershade; animation/time/command controls; Maya bridge failure handling;
floating windows; repeated workspace and sculpt transitions; teardown; common
window sizes and display scaling.

The new GUI suite inventories **91 buttons** across eight right-dock pages and
checks every operator-backed menu action against its real Blender availability.
Inventory and availability checks are distinct from executing every command.
Native interactions exercise the affected critical paths against actual Blender
data, including intentional invalid actions. Independent reviewers audited
commands, panels and handoff; a final fresh read-only review found no remaining
P1/P2 in the repaired file-lifecycle and cross-file-state paths.

## Defects repaired

Priority describes the defect before this pass. All rows below are implemented;
remaining acceptance boundaries are listed separately.

| Priority / area | Finding and resulting behavior |
|---|---|
| P1 — File loading | Opening/newing files could dereference freed Blender Area/Window memory and crash. Dock, menu and viewport owners now resolve live references. One persistent recovery callback restores the existing desktop after load, including rapid repeated loads. |
| P1 — Cross-file state | Old sculpt Xpose/visibility/return caches could survive a new file and affect a same-named loaded object. Every load clears temporary scene references, even while a recovery callback is pending. Loaded object positions and the exact Shape Editor return are preserved. |
| P1 — Repeated handoff | A later stress run crashed Qt while the same cached Tentacle panel was fully restyled on Sculpt re-entry. Studio now resolves that existing Switchboard panel and initializes its default style once per live widget; explicit theme changes remain available. The final 63-case transition suites pass at 100%, 125% and 150%, including normal exit and no redundant theme applications during repeated handoffs. |
| P1 — Canvas focus | An extra final baseline exposed an intermittent native crash in `ED_screen_areas_iter_next` on focus exit. Fullscreen restore frees its temporary screen, so native Tab now queues one coalesced focus request on the application timer after area event handling. The existing Sculpt keymap owner remains authoritative. File load, GoZ and teardown cancel pending requests. Pen-disabled access, non-viewport fall-through and repeated transitions are checked. |
| P1 — Destructive editing | Primitive INPUTS, topology caddies and stale caddy cancellation could replace shape-key/custom/shared data or overwrite later edits. Regeneration now requires a pristine construction mesh; unsupported data is guarded. Caddies validate their source/result, preserve real UV/weight data and retire safely after unrelated changes. |
| P1 — Inspector history | Direct Qt changes could disappear from native Undo/Redo or undo unrelated work. Inspector edits now share Blender's history; drags commit once, cancellation restores exact values and stale selection/file references cannot receive edits. |
| P1 — Native rotation | Quaternion/axis-angle controls changed unused Euler storage. AE now edits actual orientation while preserving the mode; Channel Box keys, locks, values and defaults use native components. Viewport rotation/cancellation preserves all representations. |
| P1 — Sculpt layer return | Divide/detail/save-reopen could lose the exact Shape Editor target. Each mesh now owns its remembered base target; native Multires detail remains shared, and GoZ restores the exact layer after leaving Sculpt. Saved tray/popup contexts resolve live owners, avoiding another reopened-file crash. |
| P1 — Maya/file failure contracts | A missing bridge result or stale output could appear successful; clear-existing import could destroy originals before import succeeded. Results/artifacts are validated, exceptions reported, imports staged, and cross-scene deletion refused. Destination overwrites require a concrete native dialog; defaults preserve files. |
| P2 — Keyboard focus | Viewport shortcuts could escape modal dialogs, numeric editors and pickers. Dialogs retain input; focused buttons keep Space/Enter; combos keep typeahead. File shortcuts use canonical commands; loading bypasses a context override that would be freed by that operation. |
| P2 — Wheel safety | Merely scrolling over numbers changed values. Plain wheel now scrolls the nearest panel or is consumed; Ctrl+wheel explicitly adjusts. Open picker behavior remains native. Sculpt pen routing remains in the existing filter. |
| P2 — Exactly one action | Command-bar clicks had duplicate signal connections. A click now executes once. Failed/cancelled commands do not populate Repeat Last or report success. Primitive repeat retains its actual arguments. |
| P2 — Availability and feedback | Menu actions could advertise unavailable operators or hide errors. Menus recalculate actual poll state when opening; failures surface in shared feedback. Viewport checkmarks reflect scene state. Render no longer advertises the F12 key owned by Studio UV selection. Help now contains actual Studio controls. |
| P2 — Editing/refresh | Idle refresh could overwrite typed input, drag the wrong object/material/key, rebuild lists or leave stale inspectors. Controllers bind edits to the displayed item, preserve unfinished fields, synchronize floating/docked panels and retain list selection/scroll. External modifier, material and topology changes invalidate the appropriate presentation. |
| P2 — Numeric fields | Negative/zero scales and actual key ranges were restricted. Attribute and shape editors use real ranges/read-only state. Transform text that collapsed to a one-pixel internal Qt editor is repaired. Invalid modifier edits report and restore canonical values. |
| P2 — Responsive layout | At 1280 width, Blender area ratios compressed the inspector until fields were cropped. The existing resize owner now maintains useful modeling pane sizes while retaining a canvas. New sizing requests supersede older queued requests even when applied immediately; cancelled native moves retain the latest request for retry. Retry records resolve live windows/areas, discard obsolete references and recover a stopped timer; old callback results cannot erase a newer request. This prevents stale Sculpt sizes from undoing GoZ's restored modeling dimensions. Modifier cards are explicitly shown, pending editors protected and the footer wraps into two rows. Toolkit labels fit and tooltips explain them. |
| P2 — Panel/action mismatch | Channel tear-off opened Tool Settings, Object toggled unpredictably, UV did not open a real editor, Quad Draw entry paths did not invoke the modal. These now perform their named action. Floating headers drag, corners resize and placement is monitor-clamped. |
| P2 — Selection/tool state | Nested Outliner selection was wrong; a transform selection retained a prior INPUTS scrub target; unsupported Make Live targets could disturb a valid target. Selection and owners now match the displayed data. Live BVH geometry invalidation uses the existing depsgraph handler. |
| P2 — Modeling fidelity | Weld/fill repeat argument mismatches and arbitrary Quad Draw edge choice were corrected. Ctrl-click uses the nearest projected edge; unsupported gesture claims were removed. Bevel/Extrude option boxes share the real caddy. Soft-select reset includes object mode. |
| P2 — Timeline/preferences | Idle time refresh could replace unfinished frame input; profile teardown dirtied preferences incorrectly. Frame controls commit deliberately and incoming dirty state is restored exactly. |
| P2 — Local handoff | Hard-coded startup assumptions failed silently. Both Windows entry points share a preflight launcher, with explicit Blender/version/dependency errors, no auto-installs and a workspace-local resource directory. |

## Historical baseline validation — 2026-10-16

This section records the earlier accepted baseline. The 2026-10-17 acceptance
above supersedes it for the changed production source.

The final aggregate records source SHA-256 values, process exits, fresh-result
checks, individual failures and report paths. Earlier `full_ux_*` / `full_review_*`
diagnostics remain available and are not substituted for final acceptance.

| Final check | Result |
|---|---|
| New full-app native UX suite | **180/180 at each actual Qt DPR 1.00, 1.25 and 1.50**, including 1280×720, 1920×1080 and 2560×1440 client sizes; 91 sidebar buttons inventoried per run. |
| Strengthened workspace/focus suite | **63/63 at each DPR 1.00/1.25/1.50**; includes 12 focus stress cycles per run, deferred native focus entry/exit, non-viewport Tab, split-view popup provenance, GoZ from fullscreen, pending-request cancellation and original pane dimensions. |
| Native file lifecycle | **16/16**; fresh final run exits normally. |
| Existing native GUI regressions | Modeling controls **71/71**, sculpt **93/93**, pen **47/47**, Channel Box **13/13**, cursor/grid/zoom **13/13**, reference palettes **56/56**. |
| Dense native Multires | **PASS**, **252,216 triangles**, live silhouette redraw and native Draw tool restored. |
| New command/panel/failure tests | Commands **14/14** (0 skips); panels **15/15**; bridge failure contracts **18/18** using ordinary Python mocks/fixtures. |
| Existing scene/data regressions | Controls **122/122**, sculpt **77/77**, brush save/reopen **10/10**, reference features **117/117**, code audit **26/26**. |
| Phase regressions | **01–06 and 08–11 PASS**. Phase 07 remains **BLOCKED** by Maya initialization. |
| Launch | Normal Windows launcher preflight **PASS**; fresh interactive startup verification is included in the aggregate. |

All final native GUI logs are checked for Python tracebacks and access violations,
in addition to fresh result files and normal process exits. Current widget
captures were reinspected after the final resize repair. The aggregate separates
earlier failed diagnostics from accepted runs.

Tests use **factory scenes and isolated local Blender resources**. QtTest clicks,
keyboard/wheel/tablet events and Blender event simulation reach production
widgets/operators and actual scene data. They are synthetic input in the native
application. Maya failure-contract tests use mocks and controlled fixtures;
they do not demonstrate a successful Maya conversion.

The strengthened responsive check verifies both the internal text-editor width
and the field's containment inside the actual inspector. An earlier geometry
check passed while the panel itself was clipped; that weaker result was not
accepted. Native Attribute Editor captures at 100%/150% and modifier/toolkit
captures at 125% were inspected after the repair.

The final result audit also caught an exit-code trap: a native workspace test
quit normally with one failed assertion (43/44), because older deferred Sculpt
sizes reapplied after GoZ return. That result is retained as
`sculpt_ux2_gui_full_layout_failure.json`; it was not accepted. Latest-intent
coalescing and cancelled-move retries repair that defect. The focused independent
review found no actionable findings after both repairs. The aggregate requires
fresh JSON behavior results as well as normal process exits.

A further baseline caught the focus crash after 27 checks. Its native stack and
partial JSON remain in `full_ux_focus_native_crash.txt` and
`sculpt_ux2_gui_full_focus_crash.json`. Blender's
[handler dispatch source](https://raw.githubusercontent.com/blender/blender/main/source/blender/windowmanager/intern/wm_event_system.cc)
shows that application timers execute after event handlers. This is current upstream source,
not the installed binary's exact commit; the lifetime hazard is consistent with
the installed crash stack. The repaired native suite adds 12 repeated focus
cycles, non-viewport Tab, deferred focus entry/exit, queued-entry cancellation
on GoZ, scoped binding removal and GoZ from focus.
The later accepted matrix above includes this repair.

Representative native captures:

- [1280 Attribute Editor at 100%](full-ux_scale100/ATTRIBUTE_EDITOR_1280.png)
- [1280 Attribute Editor at 150%](full-ux_scale150/ATTRIBUTE_EDITOR_1280.png)
- [1280 Modifier Stack at 125%](full-ux_scale125/MODIFIER_STACK_1280.png)
- [Modeling Toolkit](full-ux_scale125/MODELING_TOOLKIT.png)

The file-lifecycle suite performs real saves and loads, Qt Ctrl+S, UV window
creation, saved sculpt reopen, GoZ return, same-name cross-file position checks
and rapid repeated New operations. Early runs reproduced native crashes; the
final suite must complete all checks and quit normally. Some Blender GUI test
shutdowns still print a few tiny unfreed-block diagnostics; that is recorded,
not treated as proof of perfect memory cleanup.

## Remaining boundaries for a friend handoff

| Gate | Status and impact |
|---|---|
| External Maya runtime | **BLOCKED.** Detected Maya 2024 `mayapy.exe` fails standalone fixture initialization with `3221225477` (`0xC0000005`). See [full_review_phase07_headless.log](full_review_phase07_headless.log). Bridge failures now report honestly, but successful import/export and Maya round-trip acceptance remain unavailable. |
| Physical input | **UNVERIFIED.** Actual tablet driver/contact feel, barrel-button delivery, mixed physical mouse/pen use and monitor-to-monitor operation need a hands-on session. Synthetic checks cannot certify these. |
| Whole-window GPU visuals | **BLOCKED on this machine.** The earlier blank/stale desktop GPU capture reproduces in factory Blender before Studio on OpenGL/Vulkan. Widget captures are usable; internal sculpt silhouette checks are separate. See [SCULPT_UX_PASS2.md](SCULPT_UX_PASS2.md). No driver/global preference workaround was applied. |
| Exhaustive functionality/parity | **NOT CLAIMED.** 91 sidebar buttons were inventoried and operator menu availability was reviewed; not every command against every scene/topology combination was executed. Blender adaptations are not exact Maya/ZBrush algorithms. |
| Redistribution | **NOT PERFORMED.** No installer/public package was built. Copying this workspace must retain its local dependencies and pinned upstreams. Clean-machine and license-packaging review are separate release work. |

## Source and reproduction notes

The later [Maya isolation diagnosis](MAYA_RUNTIME_DIAGNOSIS.md) narrows the failure
to importing standalone, before initialization: ordinary, isolated and minimal
environments all fault in `mayaLib0.dll` at offset `0x1067`, without Studio.
The local handoff rehearsal proves path relocation with fresh Qt test stores;
it does not replace the remaining clean-machine gate or retrospectively change
the environment used by earlier suites.

New/expanded tests: `test_full_ux_gui.py`, `test_full_ux_file_gui.py`,
`test_full_ux_commands_data.py`, `test_full_ux_panels_data.py`,
`test_full_ux_handoff_data.py`. Existing phase09/audit26 expectations now test the
real contract: a headless process cannot create a native UV window; shape-key
topology is protected and successful caddy editing uses an independent mesh.
Static source-string assertions were replaced with real command payload checks.

Required upstream repairs:
`upstream/blendertk/blendertk/ui_utils/qt_dock.py` now resolves a live Area before
accessing its regions or undocking. The pinned checkout remains at
`d55d1ca61d5568582bbffe8ec0af458d1e8aa8b6` with this local patch; preserve the
patch when reproducing or updating upstream. The follow-up also moves the
`@btk.undoable` decorator in `upstream/tentacle/tentacle/slots/blender/pivot.py`
from the Transfer Pivot options initializer to the actual action. Retain this
local patch on the pinned Tentacle checkout. The follow-up also repairs native
rotation paths, values, keys, locks and defaults in
`upstream/blendertk/blendertk/node_utils/attributes/channels/_channels.py`.
Retain all three local upstream patches. Each acceptance aggregate records
its own source snapshot. Existing unrelated workspace changes were retained.

The full-window/phase data checks use the installed Blender executable with
`--factory-startup`, `--enable-event-simulate` for GUI tests and
`--python-exit-code 1`. Each process has its own `BLENDER_USER_RESOURCES` under
`.test_env`. Final scale runs use `QT_SCALE_FACTOR=0.8/1/1.2` on this 125% Windows
display and assert **actual Qt DPR 1.00/1.25/1.50**. No artist process or authored
asset was closed or used as the test fixture. No global install was performed.

For Qt behavior reference, the implementation follows native
[modal focus](https://doc.qt.io/qt-6/qapplication.html#activeModalWidget),
[deferred spin-box commits](https://doc.qt.io/qt-6/qabstractspinbox.html#keyboardTracking-prop)
and [action availability](https://doc.qt.io/qt-6/qaction.html#enabled-prop).
