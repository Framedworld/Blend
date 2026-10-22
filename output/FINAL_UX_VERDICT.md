# Landfall Studio — final independent UX verdict

Reviewed **2026-10-17**, after the application-wide review and polish.

Current generated-asset/command/input follow-up changes eight production files;
its frozen affected matrix passes **15/15 suites, 1,046 checks**. The fresh
[independent follow-up](instance_lifecycle_independent_review.md) rates the
tested Studio workflows **8/10**, with no material blocker in those routes.
Native Blender Shift+D/F3 duplication is now covered: a depsgraph pre-handler gives each native copy its own generated helpers; `test_native_duplicate_gui.py` passes 196/196 (hidden-desktop run, 2026-10-22). See
[INSTANCE_LIFECYCLE_REVIEW.md](INSTANCE_LIFECYCLE_REVIEW.md). The verdict and
28-suite evidence below apply to the earlier frozen production snapshot.

Previous fresh-settings follow-up: **28/28 accepted native suites** and an affected
fresh-file persistence recheck (**12/12**) on unchanged production code.
Fresh independent verdict: **8/10, integrated and worthwhile**, all prior
directives landed and no remaining material blocker in the reviewed workflows.
See [FRESH_SETTINGS_UX_REVIEW.md](FRESH_SETTINGS_UX_REVIEW.md), the
[raw review](fresh_ui_independent_review.md) and
[current aggregate](fresh_ui_final_acceptance.json). The earlier evidence below
retains its own snapshot and composite provenance.

> Independent verdict: 8/10. Highest completed gate: integrated and worthwhile.

The fresh read-only reviewer found **no remaining material blocker within the
reviewed native workflows**. Prior menu, layout, history, rotation, sculpt-return
and repeated-restyling directives are landed. Native captures support readable
controls and reachable actions. The checked workspace is suitable for a friend's
controlled trial. This review does not certify the entire product or exhaustive
Maya/ZBrush parity.

## Evidence verified by the reviewer

- **23/23 accepted suites**, normal process exits and clean callback/crash logs.
- Inspector history **100/100 at 100%, 125% and 150% actual Qt scaling**.
- Full application UX **228/228, 229/229 and 229/229**, respectively; includes
  three window sizes, Qt menu clicks and guarded Windows mouse clicks.
- Workspace/focus/GoZ **63/63 at each scale**, Channel stability **13/13**,
  native channel scrub/typed input **69/69**, integrated workflows **78/78**.
- Production source unchanged across the original matrix and rechecks; accepted
  product hashes match. Later test-fixture changes are recorded separately.

The [final aggregate](inspector_history_final_acceptance.json) is a composite:
a frozen 23-suite matrix plus two affected-only fixture rechecks. It is **not
one untouched all-source run**. Both original failures, old/new test hashes and
superseding results are retained. Startup layout settling was corrected before
Channel stability observation; integrated rotation typing now retains its
click-opened delegate and verifies that it survives a 300 ms pause in both modes.
The existing behavioral assertions remain, with two additional idle checks.
The reviewer independently inspected this provenance and the actual results.

## Remaining handoff checks

1. Run a physical pen/mouse session through base strokes, masks, subdivision,
   popups, panel scrolling, exact GoZ return and monitor changes. Synthetic native
   events do not certify tablet-driver delivery or physical feel.
2. Test startup, asset paths and save/reopen on the friend's clean machine.
   Redistributable installer and dependency/license packaging are separate work.
3. Repair the installed Maya 2024 runtime and demonstrate an external round trip
   before using production Maya files. Its standalone initialization currently
   fails with `0xC0000005`; failure handling is verified, successful conversion
   is not.

Whole-window GPU capture remains blocked by the recorded factory-Blender
presentation issue. Native Qt widget captures and native sculpt silhouette
checks provide separate, usable evidence.

See the [full review](FULL_UX_REVIEW.md),
[workflow readiness ledger](REPLACEMENT_WORKFLOW_READINESS.md) and
[friend quick start](FRIEND_QUICK_START.md).

## Later continuous-session evidence

The [continuous artist session](CONTINUOUS_ARTIST_SESSION.md) adds 48 passing
native GUI checks at DPR 1.25 on unchanged production source, including actual
base strokes followed by Smooth, mask, SubTools, Divide/detail, save/reopen and
exact-layer GoZ. A separate Blender-only numerical control explains the tiny
evaluated-grid Undo allowance while complete Basis/layer data remains exact.
Fresh independent review rates this bounded session 8/10, integrated and
worthwhile. This adds evidence without certifying the remaining physical,
external or distribution boundaries above.

## Later local handoff evidence

The [local handoff rehearsal](LOCAL_HANDOFF_REHEARSAL.md) passes **24/24 modeling
and 27/27 sculpt/fresh-process checks at DPR 1.25** from a physically copied
runtime under a spaces/Unicode path. Actual module origins, fresh Blender/Qt
test stores, native buttons/history and a real relative external texture are
verified. This supports local relocation; a clean machine remains separate.
Fresh independent review rates this bounded result 8/10, integrated and
worthwhile. Ordinary production tool-window settings remain per Windows user;
the fresh local Qt stores belong to this test harness.
The earlier 22/25 result used shared Qt stores and is superseded for freshness
claims. The [Maya diagnosis](MAYA_RUNTIME_DIAGNOSIS.md) narrows its separate
blocker to native standalone import, without identifying a repair.
