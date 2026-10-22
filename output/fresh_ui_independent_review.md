# Independent review — fresh-settings native UX round

Fresh read-only reviewer, 2026-10-17. Report retained below; link target adapted
to this report directory. No product/test edits or Blender launches by reviewer.

Independent verdict: **8/10 — integrated and worthwhile** for this bounded native UX round. No remaining material blocker was found in the reviewed workflows. This does not certify the whole product or physical input feel.

Prior directives:

- **LANDED:** Activate the existing UITK sandbox before Studio construction, isolating QSettings and preset roots. All **20 Studio GUI processes** verify their actual live Switchboard uses a local INI backend; **7 background processes** verify the guarded settings probe.
- **LANDED:** Preserve meaningful behavior checks, process/log gates, actual DPI checks and source stability. The original **28-suite matrix passes**, with normal exits and fresh results.
- **LANDED:** Correct the demonstrated favorite-persistence confound. The original fixed preference file already contained the expected SH-first result. The affected-only recheck now starts with an absent file, verifies the approved default order, and passes **12/12**, retaining all original ten assertions.
- **LANDED:** Preserve production settings behavior and honest provenance. No production code changed during this round. The final aggregate explicitly identifies a frozen matrix plus one fixture recheck, rather than one untouched run.

Evidence reviewed in [fresh_ui_final_acceptance.json](fresh_ui_final_acceptance.json):

- **28/28 accepted suites**; all **136 current manifest hashes** and the recheck script hash match.
- Inspector history **100/100**, workspace/focus **63/63**, and application UX **228/229/229** at actual Qt DPR **1.0/1.25/1.5**. Button inventory and operator availability remain distinct from executing every command.
- Continuous artist session **48/48**, including every one of the twenty required stages: native base/Smooth/mask/detail strokes, SubTools, subdivision, save/reopen and exact Shape Editor return.
- Blender-only precision control confirms no Studio import, four exact no-stroke rebuilds and ten history cycles. Worst evaluated Undo displacement is **1.3113e-6**, RMS **2.5428e-8**; complete shape buffers remain exact. This supports the documented numerical allowance, not zero evaluated-grid drift.
- Dense silhouette check passes at **252,216 triangles**, with visible canvas/silhouette and native brush ownership.
- Logs are callback/crash-clean, **not warning-free**.

Remaining boundaries:

- Several GUI fixtures still use PID-named sculpt preference files. No actual contaminated GUI default was established; relevant workspace/default-palette assertions pass. This is weaker than explicit absent-before-load proof and should not be described as universally fresh sculpt preference storage.
- The sandbox verifies the exercised stores, not every possible filesystem path. UITK still contains legacy preset-migration paths outside the redirected root; no evidence showed those paths being accessed in this round.
- Physical pen/mouse delivery, friend-machine startup, whole-window GPU capture, successful external Maya conversion and redistribution packaging remain unverified.

Prioritized recommendations:

1. Preserve the original matrix and superseding fixture result with the explicit composite description.
2. When next changing affected GUI fixtures, retain the bootstrap's run-owned preference path instead of relying on PID filenames; no unrelated rerun is presently justified.
3. Perform the physical pen/mouse trial and clean-machine launcher/save/reopen trial before calling the friend handoff bulletproof.
4. Keep successful Maya interoperability blocked until native standalone startup and an actual external round trip succeed.
