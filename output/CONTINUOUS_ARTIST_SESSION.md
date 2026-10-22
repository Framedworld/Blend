# Continuous modeling-to-sculpt session

**2026-10-17: 48/48 native GUI checks PASS**, actual Qt DPR **1.25**.
[Acceptance and source hashes](continuous_artist_session_acceptance.json).
Both the artist session and its separate Blender-only control exit normally,
produce fresh complete evidence and have clean callback/crash logs. Production
hashes match the earlier accepted 23-suite UX source. This follow-up adds tests
and evidence; no product behavior was changed.

Fresh independent read-only review: **8/10, integrated and worthwhile**, no
remaining material blocker in this bounded workflow. It verified all 48 checks,
twenty required stages, native control, logs and all 91 manifest hashes; all 88
product/upstream hashes match the earlier accepted source.

## What was exercised

The previous integrated suite seeded its base-layer delta. This session instead
authors the base form with native brush input and follows that work through the
rest of the application:

1. Type a real Attribute Editor scale, then use native Undo and Redo.
2. Click the shelf's Sculpt tile and the tray's New Layer button.
3. Select the Standard favorite and draw a native base stroke. Require an actual
   `SCULPT_OT_brush_stroke` modal and a meaningful layer delta; compare every
   Basis vertex exactly. Undo restores the complete empty layer and Redo restores
   every brush-authored layer vertex.
4. Hold Shift and draw Smooth; release restores the chosen-brush presentation.
5. Ctrl-drag a native mask, verify actual protection, then click Clear.
6. Select another SubTool through its real tree row, then select the form again.
   Recording and the exact layer data survive.
7. Click Divide, verify native Multires and retained base target, select
   DamStandard with B → D → S, and make a native high-detail stroke.
8. Undo/Redo detail, save/reopen, and click GoZ to Shape Editor. Verify the actual
   returned mesh, active layer, editor selection, complete Basis/layer data and
   evaluated high-detail surface.

The disposable fixture has **1,490 base vertices** and **6,050 evaluated vertices**.
Measured base, Smooth and detail changes are recorded in the result JSON;
none of those deformations is seeded through direct coordinate assignment.

Initial mesh creation, palette expansion, brush size/intensity setup and
`sculpt.enter()` after reopen are direct fixture actions. The typed model edit,
major action buttons, favorite, SubTool rows, browser mnemonics, native strokes,
Undo/Redo and final GoZ use real synthetic Qt/Blender input. This is a continuous
native workflow, not physical-tablet validation or external Maya interchange.

## Native Undo precision control

The first complete session was **not accepted**: 47 checks passed and the
evaluated detail-Undo comparison exceeded the earlier fixture's borrowed
`1e-6` limit. Actual error was `1.3113021850585938e-6` local units, while the
complete Basis/layer buffers remained exact. Failed runs are preserved under
`continuous-artist-session/`.

A separate process loads the exact saved pre-detail mesh **without importing
Studio**. It uses the stock native brush modal and Ctrl+Z/Shift+Ctrl+Z. Four
consecutive no-stroke Sculpt flush/rebuild snapshots are exact. Over ten native
Undo/Redo cycles, the Undo residual plateaus after cycle 2 at maximum
`1.3113e-6` and RMS approximately `2.537e-8`. The worst pole component differs
by 22 float32 ULPs. Native Redo grows from approximately `2.98e-8` to `1.666e-7`
by cycle 10, remaining below the retained `1e-6` limit. Complete Basis and layer
arrays remain exact. This identifies a native Undo/evaluated-grid numerical
boundary; the initial flush-only explanation was not confirmed.

For this unit-radius fixture, **evaluated grid Undo alone** permits maximum
`2e-6` and RMS `5e-8` local units. Both bounds must pass. Exact Basis/layer checks
and other `1e-6` surface checks remain unchanged; actual detail deformation must
exceed `1e-4`. The runner repeats the native control on each acceptance run and
requires its bounds, exact shape buffers, all ten cycles, normal exit and clean
logs. This is a documented numerical allowance, not a product-code workaround.

The final aggregate points to timestamped session/control results and logs.
The first numerical control is retained in
`native_multires_undo_precision_first.json`; repeated-cycle and per-run copies
contain RMS, signed components, ULPs and baseline/source hashes.

## Reproduce and interpret

Run from the workspace root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Blend\scripts\check_continuous_artist_session.ps1
```

The runner requires exactly **48 checks**, twenty named critical stages, no
failed checks, fresh results, stable source hashes, normal exits and clean logs.
It uses isolated local resources and disposable `.test_env` files. Earlier
diagnostics are retained rather than promoted to PASS.

This new continuous test ran at DPR 1.25. The earlier 100%/125%/150% UX matrix
remains separate evidence on the same production source. Physical pen feel,
mixed monitors, clean-machine delivery, external Maya conversion and full GPU
window capture retain the limits in [FINAL_UX_VERDICT.md](FINAL_UX_VERDICT.md).
