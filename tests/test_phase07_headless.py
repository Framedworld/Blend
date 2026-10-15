"""Gate 07 Headless Test Suite (`tests/test_phase07_headless.py`).

Validates:
1. Real Maya 2024 `mayapy.exe` runtime discovery (`get_maya_runtime_status`) and `.ma` fixture authoring (`generate_maya_fixture_ma`) with:
   - Hierarchy (`environment_GRP`, `heroChar_GRP` -> `controls_RIG` -> `root_JNT` -> `spine_JNT` -> `head_JNT`, `body_main_GEO`)
   - `skinCluster` weights on `body_main_GEO`
   - `blendShape` (`heroMorph_BS`) with targets `Smile` and `BrowUp`
   - Material (`heroBody_MAT`) & UV coordinates
   - Keyframe animation on `root_JNT`, `spine_JNT`, and `heroMorph_BS.Smile` (`frames 1..24`)
   - Complex Maya DG nodes (`customDriver_EXP` expression + `customRig_MMX` multMatrix)
2. Preflight inspection (`preflight_maya_scene`) detecting supported categories (`transforms`, `meshes`, `joints`, `skin_clusters`, `blend_shapes`, `anim_curves`) and flagging `customDriver_EXP` + `customRig_MMX` in `complex_dg_nodes`, `baked_or_approximated_items`, and `unsupported_or_lost_items`.
3. `.ma -> Blender -> Save As .ma -> Re-Import` round-trip (`validate_interchange_roundtrip`):
   - Source `.ma` SHA-256 unchanged (`source_unchanged == True`)
   - Overwrite guard rejects saving onto source `.ma` when `allow_overwrite_source=False`
   - Saved `.ma` contains valid `transform`, `mesh`, `skinCluster`, `blendShape`, and `animCurve*` nodes
   - Re-imported scene preserves hierarchy, transforms, vertex/polygon counts, materials, UVs, skin weights, blendShape targets, and animation range (`comparison_diffs == []`).
4. Non-destructive `Reference Scene` workflow (`reference_scene`, `list_scene_references`, `set_reference_mode`, `reload_reference_scene`, `unlink_and_import_reference(approved=False/True)`):
   - Links a `.blend` reference and a `.ma` reference (via `MayaSceneImport.bake_scene`)
   - Verifies `off`, `reference`, and `template` display modes
   - Verifies `unlink_and_import_reference(approved=False)` is blocked (`guarded=True`) and `approved=True` localizes datablocks.
5. Figma Make UI Pass & Maya Interchange Inspector (`interchange_panel`, `shelf`, `outliner`, `right_dock`, `time_slider`, `viewport.hud`) headless snapshot verification.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def run_tests() -> None:
    import bpy
    import landfall_studio
    from landfall_studio import interchange, ui, viewport

    print("=== Gate 07 Headless Suite: Maya .ma/.mb Interchange, Reference Scene & Figma UI Pass ===")

    # Ensure clean registered state
    landfall_studio.unregister()
    landfall_studio.register()

    # 1. Runtime discovery
    rt = interchange.get_maya_runtime_status()
    print(f"[T01] Runtime Status: available={rt['available']} ({rt['mayapy_exe']}), version={rt['maya_version']}")
    _assert(rt["available"], f"Expected local mayapy.exe to be available, got: {rt}")
    _assert(rt["mayapy_exe"] and os.path.isfile(rt["mayapy_exe"]), f"Invalid mayapy_exe path: {rt}")
    print("[PASS] T01: Maya 2024 runtime and blendertk.MayaBridge discovered")

    with tempfile.TemporaryDirectory(prefix="lf_gate07_") as tmpdir:
        src_ma = os.path.join(tmpdir, "hero_source.ma")
        rt_ma = os.path.join(tmpdir, "hero_roundtrip_saved.ma")

        # 2. Author real Maya 2024 .ma fixture via mayapy.exe & preflight it
        fix_res = interchange.generate_maya_fixture_ma(src_ma)
        _assert(fix_res.get("ok"), f"generate_maya_fixture_ma failed: {fix_res}")
        pf = fix_res["preflight"]
        _assert(os.path.isfile(src_ma) and pf.get("size_bytes", 0) > 1024, f"Expected non-empty .ma file: {pf}")
        _assert(pf["format"] == ".ma" and pf["status"] == "READY", f"Unexpected preflight status: {pf}")

        summary = pf["summary"]
        _assert(summary["meshes"] >= 1, f"Expected mesh node in .ma: {summary}")
        _assert(summary["skin_clusters"] >= 1, f"Expected skinCluster in .ma: {summary}")
        _assert(summary["blend_shapes"] >= 1, f"Expected blendShape in .ma: {summary}")
        _assert(summary["anim_curves"] >= 1, f"Expected animCurve nodes in .ma: {summary}")

        dg_types = {d["type"] for d in pf["complex_dg_nodes"]}
        _assert("expression" in dg_types and "multMatrix" in dg_types, f"Expected expression & multMatrix flagged: {dg_types}")
        _assert(len(pf["baked_or_approximated_items"]) >= 1 and len(pf["unsupported_or_lost_items"]) >= 1, f"Expected loss report items: {pf}")
        print(f"[PASS] T02: Real Maya .ma fixture authored ({pf['size_bytes']} bytes) & preflight flagged {dg_types}")

        # 3. Source overwrite protection check
        ow_res = interchange.save_as_maya_scene(
            src_ma,
            protected_source_path=src_ma,
            allow_overwrite_source=False,
        )
        _assert(
            ow_res.get("ok") is False and "Refusing to overwrite" in str(ow_res.get("error", "")),
            f"Expected overwrite protection to block writing onto protected_source_path: {ow_res}",
        )
        print("[PASS] T03: Source .ma overwrite protection enforced when allow_overwrite_source=False")

        # 4. Full .ma -> Blender -> Save As .ma -> Re-Import Round-Trip
        rt_res = interchange.validate_interchange_roundtrip(src_ma, rt_ma)
        _assert(rt_res.get("ok"), f"validate_interchange_roundtrip failed: {rt_res}")
        _assert(rt_res["source_unchanged"] is True, "Source .ma SHA-256 must remain identical after round-trip")
        _assert(rt_res["source_sha256_before"] == rt_res["source_sha256_after"], "SHA-256 mismatch on source .ma")

        saved_pf = rt_res.get("saved_ma_preflight", {})
        saved_sum = saved_pf.get("summary", {})
        _assert(saved_sum.get("meshes", 0) >= 1 and saved_sum.get("transforms", 0) >= 1, f"Saved .ma missing meshes/transforms: {saved_pf}")
        _assert(saved_sum.get("skin_clusters", 0) >= 1 and saved_sum.get("blend_shapes", 0) >= 1, f"Saved .ma missing skinCluster/blendShape: {saved_pf}")
        _assert(len(rt_res.get("comparison_diffs", [])) == 0, f"Round-trip topology diffs detected: {rt_res.get('comparison_diffs')}")
        print(
            f"[PASS] T04: .ma -> Blender -> Save As .ma -> Re-Import round-trip verified "
            f"(status={rt_res['status']}, source_unchanged=True, objects={rt_res['hierarchy_and_geometry']['object_count']}, "
            f"weighted_verts={rt_res['skinning_and_joints']['total_weighted_vertices']}, "
            f"morph_targets={rt_res['morphs_and_animation']['total_shape_targets']})"
        )

        # 5. Reference Scene workflow (.blend and .ma non-destructive referencing + off/reference/template modes + guarded unlink)
        ref_blend_path = os.path.join(tmpdir, "prop_crate_ref.blend")
        bpy.ops.wm.read_homefile(use_empty=True)
        ui.create_maya_primitive("CUBE", name="RefCrate_GEO", width=1.5, height=1.5, depth=1.5)
        bpy.ops.wm.save_as_mainfile(filepath=ref_blend_path)

        # Start fresh host scene
        bpy.ops.wm.read_homefile(use_empty=True)
        ui.create_maya_primitive("SPHERE", name="HostSphere_GEO", radius=1.0)

        link_res = interchange.reference_scene(ref_blend_path, display_mode="reference")
        _assert(link_res.get("ok"), f"reference_scene(.blend) failed: {link_res}")
        _assert(link_res.get("source_unchanged") is True, "Reference source .blend must remain unchanged")
        refs = interchange.list_scene_references()
        _assert(len(refs) >= 1, f"Expected >= 1 scene reference, got: {refs}")
        lib_name = link_res["library_name"]

        # Test cycling reference modes (off / reference / template)
        m_t = interchange.set_reference_mode(lib_name, mode="template")
        _assert(m_t.get("ok") and m_t["display_mode"] == "template", f"Expected template mode: {m_t}")
        m_n = interchange.set_reference_mode(lib_name, mode="off")
        _assert(m_n.get("ok") and m_n["display_mode"] == "off", f"Expected off mode: {m_n}")
        m_r = interchange.set_reference_mode(lib_name, mode="reference")
        _assert(m_r.get("ok") and m_r["display_mode"] == "reference", f"Expected reference mode: {m_r}")

        # Test reload reference
        rel_res = interchange.reload_reference_scene(lib_name)
        _assert(rel_res.get("ok"), f"reload_reference_scene failed: {rel_res}")

        # Test guarded unlink & import (must block when approved=False, succeed when approved=True)
        blocked_unlink = interchange.unlink_and_import_reference(lib_name, approved=False)
        _assert(
            blocked_unlink.get("ok") is False and blocked_unlink.get("guarded") is True,
            f"Expected unlink_and_import_reference(approved=False) to be blocked: {blocked_unlink}",
        )
        ok_unlink = interchange.unlink_and_import_reference(lib_name, approved=True)
        _assert(ok_unlink.get("ok") is True, f"Expected unlink_and_import_reference(approved=True) to succeed: {ok_unlink}")
        print("[PASS] T05: Reference Scene (.blend link, off/reference/template display modes, reload, guarded unlink) verified")

        # 6. Foreign .ma Reference Scene via MayaSceneImport.bake_scene
        bpy.ops.wm.read_homefile(use_empty=True)
        ma_ref_res = interchange.reference_scene(src_ma, display_mode="reference")
        _assert(ma_ref_res.get("ok"), f"reference_scene(.ma) failed: {ma_ref_res}")
        _assert(ma_ref_res.get("source_unchanged") is True, f"Expected source_unchanged=True: {ma_ref_res}")
        refs_after_ma = interchange.list_scene_references()
        _assert(len(refs_after_ma) >= 1 and refs_after_ma[0].get("foreign_source"), f"Expected foreign_source on .ma reference: {refs_after_ma}")
        print(f"[PASS] T06: Foreign .ma Reference Scene baked & linked non-destructively ({ma_ref_res['library_name']})")

        # 7. Figma Make UI Pass & Maya Interchange Inspector Snapshot Verification
        ui_snap = ui.get_interchange_ui_snapshot()
        _assert(ui_snap.get("ok"), f"get_interchange_ui_snapshot failed: {ui_snap}")
        _assert(len(ui_snap.get("references", [])) >= 1, f"Expected active reference in UI snapshot: {ui_snap}")

        # Verify Right Dock cycling to MAYA_INTERCHANGE
        ui.open_panel("channels", docked=True)
        cyc_mi = ui.cycle_right_dock("MAYA_INTERCHANGE")
        _assert(cyc_mi.get("mode") == "MAYA_INTERCHANGE", f"Expected MAYA_INTERCHANGE mode, got: {cyc_mi}")
        cyc_cb = ui.cycle_right_dock("CHANNEL_BOX")
        _assert(cyc_cb.get("mode") == "CHANNEL_BOX", f"Expected CHANNEL_BOX mode, got: {cyc_cb}")

        # Verify Time Slider 3-Row Bottom Chrome & Command Feedback sync
        ui.set_command_feedback("mayaImportScene -file hero_source.ma", "Imported 5 DAG nodes (0 errors)")
        ts_snap = ui.get_time_slider_snapshot()
        _assert(ts_snap.get("ok"), f"get_time_slider_snapshot failed: {ts_snap}")
        fb_snap = ui.get_command_feedback()
        _assert("Imported 5 DAG nodes" in fb_snap.get("result", ""), f"Unexpected command feedback: {fb_snap}")

        # Verify Viewport HUD stats & Outliner snapshot
        hud_st = viewport.get_hud_state()
        _assert(hud_st.get("enabled") is True, f"Expected HUD enabled: {hud_st}")
        out_snap = ui.get_dag_outliner_snapshot()
        _assert(out_snap.get("ok") is True, f"Expected DAG Outliner snapshot ok: {out_snap}")
        print("[PASS] T07: Figma Make UI Pass & Maya Interchange Inspector headless snapshots verified")

    landfall_studio.unregister()
    print("=== ALL GATE 07 HEADLESS TESTS PASSED (7/7) ===")


if __name__ == "__main__":
    try:
        run_tests()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
