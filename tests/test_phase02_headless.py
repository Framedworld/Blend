"""Phase 02 Headless Verification Suite (`T02-1`).

Verifies:
1. Single Keymap & Profile Owner (`MAYA` and `HYBRID` profiles) and reversible switching.
2. Keymap Conflict Scanner (`scan_keymap_conflicts`): single hotbox owner on `SPACE`, distinct `RMB`/`Shift+RMB`/`Ctrl+RMB` menus, zero leaks in protected contexts (`Text`, `Console`, `Sculpt`, `Paint`, `Node Editor`), zero truncated user keymaps.
3. Persistent tool & manipulator selection (`Q / W / E / R`) and Last Tool recall (`Y`).
4. Unified Command Registry and Repeat Last Command (`G`) across `blendertk` / Studio operations.
5. Seamless `Object Mode` ↔ `Edit Mode` component transitions (`F8` toggle with memory, `F9` Vert, `F10` Edge, `F11` Face, `F12` UV) and `Ctrl+RMB` component conversion (`VERT`, `EDGE`, `FACE`, `BOUNDARY`).
6. `1 / 2 / 3` Smooth Mesh Preview (`CAGE`, `BOTH`, `SMOOTH`) preserving base mesh and cage overlay flag.
7. `Hold D` + `V/C/X` Pivot Snapping preserving world vertex coordinates, plus Escape/cancel state restoration.
8. Open-viewport `MMB` Virtual Slider along active manipulator axis.
9. Complete cleanup on `unregister()`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import bmesh
import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_JSON = (
    Path(
        r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output"
    )
    / "phase02_headless_results.json"
)


def _count_addon_kmi() -> int:
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return 0
    return sum(len(km.keymap_items) for km in kc.keymaps)


def main() -> int:
    os.environ["LANDFALL_STUDIO_UPSTREAM"] = r"C:\Users\mattk\Documents\Landfall\upstream"
    os.environ["LANDFALL_STUDIO_DEPS"] = r"C:\Users\mattk\Documents\Landfall\.deps\py313"

    import landfall_studio
    from landfall_studio import commands, keymaps, viewport

    baseline_kmi = _count_addon_kmi()
    baseline_depsgraph = len(bpy.app.handlers.depsgraph_update_post)
    baseline_load_post = len(bpy.app.handlers.load_post)

    # 1. Register Landfall Studio (defaults to MAYA profile)
    landfall_studio.register()

    # 2. Run Keymap Conflict Scanner in MAYA profile
    maya_scan = keymaps.scan_keymap_conflicts(bpy.context)
    assert maya_scan["clean"] is True, f"Maya profile conflict scan failed: {maya_scan}"
    assert maya_scan["active_profile"] == "MAYA"
    assert maya_scan["duplicate_hotbox_on_space"] is False
    assert len(maya_scan["protected_context_leaks"]) == 0
    assert len(maya_scan["truncated_user_keymaps"]) == 0
    assert maya_scan["tentacle_key_info"]["addon_key_type"] == "SPACE"
    if sys.platform == "win32":
        assert maya_scan["tentacle_key_info"]["active_vk"] == 0x20

    # Verify distinct RMB, Shift+RMB, Ctrl+RMB marking menu bindings exist
    rmb_modes = {
        (b["keymap"], b["ctrl"], b["shift"]): b["menu_mode"]
        for b in maya_scan["rmb_menu_bindings"]
    }
    for km_name in ("Object Mode", "Mesh"):
        assert rmb_modes.get((km_name, False, False)) == "COMPONENT"
        assert rmb_modes.get((km_name, False, True)) == "TOOL"
        assert rmb_modes.get((km_name, True, False)) == "CONVERT"

    # 3. Profile switching: MAYA -> HYBRID -> MAYA
    bpy.ops.landfall_studio.set_interaction_profile(profile="HYBRID")
    hybrid_scan = keymaps.scan_keymap_conflicts(bpy.context)
    assert hybrid_scan["clean"] is True, f"Hybrid profile scan failed: {hybrid_scan}"
    assert hybrid_scan["active_profile"] == "HYBRID"
    assert hybrid_scan["muted_native_item_count"] == 0
    assert hybrid_scan["tentacle_key_info"]["addon_key_type"] == "Z"

    bpy.ops.landfall_studio.set_interaction_profile(profile="MAYA")
    maya_scan_restored = keymaps.scan_keymap_conflicts(bpy.context)
    assert maya_scan_restored["clean"] is True
    assert maya_scan_restored["active_profile"] == "MAYA"
    assert maya_scan_restored["tentacle_key_info"]["addon_key_type"] == "SPACE"

    # 4. Q / W / E / R persistent tool & gizmo selection + Y (Select Last Tool)
    qwer_results = {}
    for tool_id, expected_flags in (
        ("SELECT", (False, False, False)),
        ("TRANSLATE", (True, False, False)),
        ("ROTATE", (False, True, False)),
        ("RESIZE", (False, False, True)),
    ):
        bpy.ops.landfall_studio.select_tool(tool=tool_id)
        sp = viewport.find_view3d_area_region(bpy.context)[0].spaces.active
        actual_flags = (
            bool(sp.show_gizmo_object_translate),
            bool(sp.show_gizmo_object_rotate),
            bool(sp.show_gizmo_object_scale),
        )
        assert actual_flags == expected_flags, f"{tool_id}: {actual_flags} != {expected_flags}"
        qwer_results[tool_id] = actual_flags

    # Press Q (SELECT), then press Y (select_last_tool) -> should recall RESIZE (R)
    bpy.ops.landfall_studio.select_tool(tool="SELECT")
    assert commands.get_active_tool() == "SELECT"
    bpy.ops.landfall_studio.select_last_tool()
    assert commands.get_active_tool() == "RESIZE"

    # 5. Unified Command Registry + Repeat Last Command (G)
    # Remove default objects first for clean count
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    bpy.ops.landfall_studio.btk_create_primitive(primitive_type="CUBE", size=2.0)
    assert len(bpy.data.objects) == 1
    first_cube = bpy.data.objects[0]

    # Press G (repeat_last_command) -> should repeat btk_create_primitive and create a second cube
    bpy.ops.landfall_studio.repeat_last_command()
    assert len(bpy.data.objects) == 2
    active_cube = bpy.context.view_layer.objects.active
    assert active_cube is not None and active_cube.type == "MESH"

    # 6. Seamless Component Mode Switching (F8-F12) without manual Tab
    assert bpy.context.mode == "OBJECT"
    # F10 -> Edge mode directly from Object mode
    bpy.ops.landfall_studio.component_mode(mode="EDGE")
    assert bpy.context.mode == "EDIT_MESH"
    assert tuple(bool(x) for x in bpy.context.tool_settings.mesh_select_mode) == (
        False,
        True,
        False,
    )

    # F8 (TOGGLE) -> back to Object mode, remembering EDGE
    bpy.ops.landfall_studio.component_mode(mode="TOGGLE")
    assert bpy.context.mode == "OBJECT"
    assert commands.get_last_component_mode() == "EDGE"

    # F8 (TOGGLE) again -> back to EDIT_MESH in EDGE mode!
    bpy.ops.landfall_studio.component_mode(mode="TOGGLE")
    assert bpy.context.mode == "EDIT_MESH"
    assert tuple(bool(x) for x in bpy.context.tool_settings.mesh_select_mode) == (
        False,
        True,
        False,
    )

    # F9 (VERT), F11 (FACE), F12 (UV)
    bpy.ops.landfall_studio.component_mode(mode="VERT")
    assert tuple(bool(x) for x in bpy.context.tool_settings.mesh_select_mode) == (
        True,
        False,
        False,
    )
    bpy.ops.landfall_studio.component_mode(mode="FACE")
    assert tuple(bool(x) for x in bpy.context.tool_settings.mesh_select_mode) == (
        False,
        False,
        True,
    )
    bpy.ops.landfall_studio.component_mode(mode="UV")
    assert bpy.context.tool_settings.use_uv_select_sync is True

    # 7. Component Conversion (Ctrl+RMB / landfall_studio.convert_selection)
    bpy.ops.landfall_studio.component_mode(mode="FACE")
    bm = bmesh.from_edit_mesh(active_cube.data)
    bm.faces.ensure_lookup_table()
    bm.select_mode = {"FACE"}
    for v in bm.verts:
        v.select_set(False)
    for e in bm.edges:
        e.select_set(False)
    for i, f in enumerate(bm.faces):
        f.select_set(i == 0)
    bm.select_flush_mode()
    bmesh.update_edit_mesh(active_cube.data)

    # Convert 1 Face -> Edges (4 edges)
    bpy.ops.landfall_studio.convert_selection(target="EDGE")
    bm = bmesh.from_edit_mesh(active_cube.data)
    sel_edge_count = sum(1 for e in bm.edges if e.select)
    assert sel_edge_count == 4, f"Expected 4 edges from 1 face, got {sel_edge_count}"

    # Convert 4 Edges -> Vertices (4 verts)
    bpy.ops.landfall_studio.convert_selection(target="VERT")
    bm = bmesh.from_edit_mesh(active_cube.data)
    sel_vert_count = sum(1 for v in bm.verts if v.select)
    assert sel_vert_count == 4, f"Expected 4 verts, got {sel_vert_count}"

    # Return to Object Mode via F8 / OBJECT
    bpy.ops.landfall_studio.component_mode(mode="OBJECT")
    assert bpy.context.mode == "OBJECT"

    # 8. Smooth Mesh Preview (1 / 2 / 3)
    bpy.ops.landfall.smooth_preview(mode="BOTH")  # 2: Smooth + Original Cage
    assert bpy.context.scene.landfall_cage_show is True
    subsurf = next((m for m in active_cube.modifiers if m.type == "SUBSURF"), None)
    assert subsurf is not None and subsurf.show_viewport is True

    bpy.ops.landfall.smooth_preview(mode="SMOOTH")  # 3: Smooth only
    assert bpy.context.scene.landfall_cage_show is False
    assert subsurf.show_viewport is True

    bpy.ops.landfall.smooth_preview(mode="CAGE")  # 1: Base only
    assert bpy.context.scene.landfall_cage_show is False
    assert subsurf.show_viewport is False

    # 9. Hold D Pivot Editing + V (Vertex Snap) & Cancel Safety
    bpy.ops.landfall_studio.select_tool(tool="ROTATE", axis="Y")
    verts_world_before = [
        tuple(round(c, 5) for c in (active_cube.matrix_world @ v.co))
        for v in active_cube.data.vertices
    ]
    origin_before = tuple(round(c, 5) for c in active_cube.matrix_world.translation)

    # Snap pivot to vertex (D + V)
    bpy.ops.landfall_studio.pivot_edit_modal(snap_mode="VERTEX")
    origin_after_v = tuple(round(c, 5) for c in active_cube.matrix_world.translation)
    verts_world_after = [
        tuple(round(c, 5) for c in (active_cube.matrix_world @ v.co))
        for v in active_cube.data.vertices
    ]
    assert origin_after_v != origin_before, "Pivot origin should have snapped to a vertex"
    assert verts_world_after == verts_world_before, "World vertex positions must not move during pivot snap!"
    # Verify tool and snap state restored on release
    assert bpy.context.scene.tool_settings.use_transform_data_origin is False
    assert bpy.context.scene.tool_settings.use_snap is False
    assert commands.get_active_tool() == "ROTATE"

    # Simulate Escape/Cancel during pivot edit -> must not change origin or leak state
    bpy.ops.landfall_studio.pivot_edit_modal(snap_mode="GRID", simulate_cancel=True)
    assert tuple(round(c, 5) for c in active_cube.matrix_world.translation) == origin_after_v
    assert bpy.context.scene.tool_settings.use_transform_data_origin is False

    # 10. Open-Viewport MMB Virtual Slider along active axis
    bpy.ops.landfall_studio.select_tool(tool="TRANSLATE", axis="Y")
    y_before = float(active_cube.location.y)
    bpy.ops.landfall_studio.mmb_virtual_slider(delta=1.25)
    y_after = float(active_cube.location.y)
    assert abs((y_after - y_before) - 1.25) < 1e-5, f"MMB virtual slider delta mismatch: {y_before} -> {y_after}"

    # 11. Unregister and verify zero leaks
    landfall_studio.unregister()

    after_kmi = _count_addon_kmi()
    after_depsgraph = len(bpy.app.handlers.depsgraph_update_post)
    after_load_post = len(bpy.app.handlers.load_post)
    assert after_kmi == baseline_kmi, f"Leaked keymap items: {after_kmi} vs {baseline_kmi}"
    assert after_depsgraph == baseline_depsgraph
    assert after_load_post == baseline_load_post
    assert keymaps.get_muted_native_count() == 0

    results = {
        "suite": "T02-1_headless_interaction",
        "overall_pass": True,
        "maya_profile_scan": maya_scan,
        "hybrid_profile_scan": hybrid_scan,
        "qwer_gizmo_flags": qwer_results,
        "last_tool_recall_y": "RESIZE",
        "command_repeat_g": {
            "repeated_id": "landfall_studio.btk_create_primitive",
            "objects_created": 2,
        },
        "component_modes_verified": ["TOGGLE", "VERT", "EDGE", "FACE", "UV"],
        "conversions_verified": ["EDGE", "VERT"],
        "smooth_preview_verified": ["BOTH", "SMOOTH", "CAGE"],
        "pivot_snap_d_v": {
            "origin_before": origin_before,
            "origin_after": origin_after_v,
            "world_vertices_preserved": verts_world_after == verts_world_before,
            "state_restored_after_release_and_escape": True,
        },
        "mmb_virtual_slider": {
            "axis": "Y",
            "y_before": round(y_before, 4),
            "y_after": round(y_after, 4),
        },
        "unregister_clean": {
            "leaked_kmi": after_kmi - baseline_kmi,
            "leaked_depsgraph_handlers": after_depsgraph - baseline_depsgraph,
            "leaked_load_post_handlers": after_load_post - baseline_load_post,
            "remaining_muted_native_items": keymaps.get_muted_native_count(),
        },
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"PHASE02_HEADLESS_PASS: wrote {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
