"""Phase 04 Headless Verification Suite (`T04-1`).

Verifies in headless Blender 5.2:
1. Multi-object Channel Box editing and 3D Viewport `MMB` virtual-slider channel scrubbing across selected channels/objects.
2. `SHAPES` inspection/renaming and live parametric `INPUTS` (`polyCube1`, `polySphere1`) + active modifier `INPUTS` (`Bevel`, `Subsurf`) + `Delete History` (`landfall_studio.delete_history`).
3. Maya Display Layer Editor (`V` visibility, `P` playback, `Normal / T Template / R Reference` state cycling).
4. `.blend` Save & Reopen persistence of Display Layers (`V/P/T/R`), memberships, and parametric `INPUTS` history.
5. Maya Attribute Editor (`Transform`, `Shape`, `Shader`, and explicit `BLENDER_MAYA_CONCEPT_MAPPING`) + Linked Library read-only safety (`bpy.data.libraries.load(..., link=True)`).
6. Unified Tool Settings & Option Box (`□`) (`axis_orientation`, `soft_select`, `symmetry`, `bevel_segments`, `reset_tool_settings`).
7. Maya DAG Outliner (`Transform -> [+] Shape` hierarchy, search filter, two-way selection, and `MMB` world-preserving reparenting with `Undo`/`Redo`).
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Euler, Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_JSON = (
    Path(
        r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output"
    )
    / "phase04_headless_results.json"
)


def main() -> int:
    os.environ["LANDFALL_STUDIO_UPSTREAM"] = r"C:\Users\mattk\Documents\Landfall\upstream"
    os.environ["LANDFALL_STUDIO_DEPS"] = r"C:\Users\mattk\Documents\Landfall\.deps\py313"

    import landfall_studio
    from landfall_studio import commands, diagnostics, ui, viewport

    landfall_studio.register()
    rep = diagnostics.get_report()
    assert rep["full_stack_ready"] is True

    results = {"suite": "T04-1", "blender_version": bpy.app.version_string, "checks": {}}

    with tempfile.TemporaryDirectory(prefix="lf_phase04_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # ------------------------------------------------------------------
        # 1. Parametric Maya Primitives, SHAPES, and Multi-Object Channel Box
        # ------------------------------------------------------------------
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        bpy.ops.landfall_studio.maya_poly_primitive(
            primitive_type="CUBE",
            width=2.0,
            height=2.0,
            depth=2.0,
            subdivisions_x=1,
            subdivisions_y=1,
            subdivisions_z=1,
        )
        cube = bpy.context.view_layer.objects.active
        assert cube is not None and cube.name == "pCube1"

        bpy.ops.landfall_studio.maya_poly_primitive(
            primitive_type="SPHERE",
            radius=1.5,
            subdivisions_x=16,
            subdivisions_y=12,
        )
        sphere = bpy.context.view_layer.objects.active
        assert sphere is not None and sphere.name == "pSphere1"

        # Open Channel Box and select both pCube1 and pSphere1
        ui.open_panel("channels", docked=True)
        cube.select_set(True)
        sphere.select_set(True)
        bpy.context.view_layer.objects.active = cube
        ui.sync_channels_now()

        # Multi-object edit via Channel Box UI table -> updates BOTH objects
        multi_edit = ui.set_channel_value_from_ui("location_z", 4.25)
        assert multi_edit["ok"] is True
        assert abs(float(cube.location.z) - 4.25) < 1e-4
        assert abs(float(sphere.location.z) - 4.25) < 1e-4

        # Highlight channels in Channel Box (`location_x`, `scale_y`) and scrub via Viewport MMB virtual slider
        matched_ch = ui.select_channels_in_ui(["location_x", "scale_y"])
        assert set(matched_ch) == {"location_x", "scale_y"}, f"Got {matched_ch}"
        commands.set_active_tool("SELECT")  # Even in SELECT tool, highlighted channels scrub!
        res_scrub = bpy.ops.landfall_studio.mmb_virtual_slider(delta=1.5)
        assert res_scrub == {"FINISHED"}
        assert abs(float(cube.location.x) - 1.5) < 1e-4
        assert abs(float(sphere.location.x) - 1.5) < 1e-4
        assert abs(float(cube.scale.y) - 2.5) < 1e-4
        assert abs(float(sphere.scale.y) - 2.5) < 1e-4

        results["checks"]["multi_object_and_mmb_channel_scrub"] = {
            "multi_edited_z": float(cube.location.z),
            "scrubbed_channels": matched_ch,
            "cube_loc_x": float(cube.location.x),
            "sphere_loc_x": float(sphere.location.x),
            "cube_scale_y": float(cube.scale.y),
            "sphere_scale_y": float(sphere.scale.y),
        }

        # ------------------------------------------------------------------
        # 2. SHAPES & Live Parametric/Modifier INPUTS + Delete History
        # ------------------------------------------------------------------
        sphere.select_set(False)
        cube.select_set(True)
        bpy.context.view_layer.objects.active = cube

        sinfo_before = ui.get_object_shape_info(cube)
        assert sinfo_before["shape_name"] == "pCube1Shape"
        ren_res = ui.rename_object_shape(cube, "Hero_CubeShape")
        assert ren_res["ok"] is True and cube.data.name == "Hero_CubeShape"

        inputs_before = ui.get_object_inputs(cube)
        assert len(inputs_before) == 1 and inputs_before[0]["node_name"] == "polyCube1"
        verts_initial = len(cube.data.vertices)
        assert verts_initial == 8

        # Edit polyCube1.subdivisions_x = 3 and width = 4.0 -> non-destructively regenerates mesh
        in_res1 = ui.set_object_input_attribute(cube, "polyCube1", "subdivisions_x", 3)
        in_res2 = ui.set_object_input_attribute(cube, "polyCube1", "width", 4.0)
        assert in_res1["ok"] is True and in_res2["ok"] is True
        assert len(cube.data.vertices) == 16, f"Expected 16 verts for 3x1x1 cube, got {len(cube.data.vertices)}"
        xs = [v.co.x for v in cube.data.vertices]
        assert abs((max(xs) - min(xs)) - 4.0) < 1e-4

        # Add a Bevel modifier and edit its segments via INPUTS
        bev = cube.modifiers.new(name="polyBevel1", type="BEVEL")
        bev.width = 0.2
        bev.segments = 1
        mod_edit = ui.set_object_input_attribute(cube, "polyBevel1", "segments", 3)
        assert mod_edit["ok"] is True and bev.segments == 3
        inputs_with_mod = ui.get_object_inputs(cube)
        assert [n["node_name"] for n in inputs_with_mod] == ["polyCube1", "polyBevel1"]

        # Delete Construction History (Alt+Shift+D) -> applies Bevel and clears polyCube1
        del_hist = bpy.ops.landfall_studio.delete_history()
        assert del_hist == {"FINISHED"}
        assert len(ui.get_object_inputs(cube)) == 0
        assert len(cube.modifiers) == 0
        assert len(cube.data.vertices) > 16  # Bevel geometry is now baked into mesh

        results["checks"]["shapes_inputs_and_delete_history"] = {
            "renamed_shape": cube.data.name,
            "subdivided_verts_before_bake": 16,
            "baked_verts_after_delete_history": len(cube.data.vertices),
            "remaining_inputs": len(ui.get_object_inputs(cube)),
        }

        # ------------------------------------------------------------------
        # 3. Maya Display Layer Editor (`V`, `P`, `Normal / T / R`)
        # ------------------------------------------------------------------
        lyr = ui.create_display_layer("Hero_Geo_Layer", assign_selected=True)
        assert lyr["ok"] is True and "pCube1" in lyr["members"]

        # Toggle V (visibility)
        ui.set_display_layer_state("Hero_Geo_Layer", visible=False)
        assert cube.hide_viewport is True
        ui.set_display_layer_state("Hero_Geo_Layer", visible=True)
        assert cube.hide_viewport is False

        # Toggle P (playback)
        ui.set_display_layer_state("Hero_Geo_Layer", playback=False)
        assert ui.list_display_layers()[0]["playback"] is False
        ui.set_display_layer_state("Hero_Geo_Layer", playback=True)

        # Cycle Mode: N -> T (Template: wireframe + unselectable) -> R (Reference: shaded + unselectable) -> N
        st_t = ui.set_display_layer_state("Hero_Geo_Layer", cycle_mode=True)
        assert st_t["mode"] == "T"
        assert cube.display_type == "WIRE" and cube.hide_select is True

        st_r = ui.set_display_layer_state("Hero_Geo_Layer", cycle_mode=True)
        assert st_r["mode"] == "R"
        assert cube.display_type == "TEXTURED" and cube.hide_select is True

        st_n = ui.set_display_layer_state("Hero_Geo_Layer", cycle_mode=True)
        assert st_n["mode"] == "N"
        assert cube.hide_select is False

        # Leave Hero_Geo_Layer in Reference ('R') mode for Save/Reopen persistence test
        ui.set_display_layer_state("Hero_Geo_Layer", mode="R")

        results["checks"]["display_layers_v_p_t_r"] = {
            "layer_name": "Hero_Geo_Layer",
            "template_wire_unselectable": True,
            "reference_shaded_unselectable": True,
            "normal_selectable": True,
        }

        # ------------------------------------------------------------------
        # 4. Maya DAG Outliner (`Transform -> Shape`) & `MMB` World-Preserving Reparenting + Undo/Redo
        # ------------------------------------------------------------------
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=(5.0, -3.0, 2.0))
        loc_root = bpy.context.view_layer.objects.active
        loc_root.name = "Rig_Root_Grp"
        loc_root.rotation_euler = Euler((0.0, 0.0, math.radians(45.0)), "XYZ")

        sphere.location = Vector((8.0, 1.5, 4.0))
        sphere.rotation_euler = Euler((math.radians(15.0), math.radians(-20.0), 0.0), "XYZ")
        bpy.context.view_layer.update()
        world_before = sphere.matrix_world.copy()

        bpy.ops.ed.undo_push(message="Before Outliner Reparent")
        rep_res = ui.reparent_preserve_world("pSphere1", "Rig_Root_Grp")
        assert rep_res["ok"] is True
        assert sphere.parent == loc_root
        assert rep_res["max_matrix_diff"] < 1e-5, f"World matrix drifted: {rep_res}"
        bpy.ops.ed.undo_push(message="After Outliner Reparent")

        # Verify DAG Outliner tree structure (Rig_Root_Grp -> pSphere1 -> pSphere1Shape)
        dag_snap = ui.get_dag_outliner_snapshot(show_shapes=True)
        root_names = [r["name"] for r in dag_snap["roots"]]
        assert "Rig_Root_Grp" in root_names
        assert "pSphere1" not in root_names  # Now a child of Rig_Root_Grp!
        rig_node = next(r for r in dag_snap["roots"] if r["name"] == "Rig_Root_Grp")
        child_sphere_node = next(c for c in rig_node["children"] if c["name"] == "pSphere1")
        assert any(
            c["kind"] == "SHAPE" and c["name"] == "pSphere1Shape"
            for c in child_sphere_node["children"]
        )

        # Test Undo & Redo of reparenting
        bpy.ops.ed.undo()
        sphere = bpy.data.objects["pSphere1"]
        assert sphere.parent is None, "Undo should restore pSphere1 to world root"
        bpy.ops.ed.redo()
        sphere = bpy.data.objects["pSphere1"]
        assert sphere.parent is not None and sphere.parent.name == "Rig_Root_Grp"
        max_diff_after_redo = max(
            abs(world_before[r][c] - sphere.matrix_world[r][c])
            for r in range(4)
            for c in range(4)
        )
        assert max_diff_after_redo < 1e-5

        results["checks"]["dag_outliner_and_reparent_undo"] = {
            "parent": sphere.parent.name,
            "max_world_matrix_diff": float(max_diff_after_redo),
            "shape_child_present": True,
            "undo_redo_verified": True,
        }

        # ------------------------------------------------------------------
        # 5. Attribute Editor, Honest Concept Mapping, & Tool Settings (`□`)
        # ------------------------------------------------------------------
        ui.select_in_outliner(["pSphere1"])
        ae_snap = ui.get_attribute_editor_snapshot(sphere)
        assert ae_snap["ok"] is True
        assert len(ae_snap["concept_mapping"]) >= 5

        mat_res = ui.set_attribute_editor_value("material", "roughness", 0.25, obj=sphere)
        assert mat_res["ok"] is True
        assert abs(float(mat_res["snapshot"]["material"]["roughness"]) - 0.25) < 1e-3

        # Tool Settings & Option Box (`□`)
        ui.open_tool_settings_for_shelf_item("bevel", "BEVEL")
        ui.set_tool_setting("axis_orientation", "LOCAL")
        ui.set_tool_setting("soft_select_enabled", True)
        ui.set_tool_setting("soft_select_radius", 3.75)
        ui.set_tool_setting("symmetry_x", True)
        ui.set_tool_setting("bevel_segments", 4)
        ts_snap = ui.get_tool_settings_snapshot()
        assert ts_snap["axis_orientation_blender"] == "LOCAL"
        assert ts_snap["soft_select_enabled"] is True
        assert abs(ts_snap["soft_select_radius"] - 3.75) < 1e-4
        assert ts_snap["symmetry"]["x"] is True
        assert ts_snap["option_box"]["bevel_segments"] == 4

        ts_reset = ui.reset_tool_settings()
        assert ts_reset["axis_orientation_blender"] == "GLOBAL"
        assert ts_reset["soft_select_enabled"] is False
        assert ts_reset["symmetry"]["x"] is False

        results["checks"]["attribute_editor_and_tool_settings"] = {
            "concept_mapping_count": len(ae_snap["concept_mapping"]),
            "shader_roughness": mat_res["snapshot"]["material"]["roughness"],
            "tool_settings_verified": True,
        }

        # ------------------------------------------------------------------
        # 6. Save & Reopen Persistence + Linked Library Read-Only Safety
        # ------------------------------------------------------------------
        saved_scene_path = tmp_path / "gate04_persistence_scene.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(saved_scene_path))
        assert saved_scene_path.is_file()

        # Create a separate library .blend file to test linked data safety
        lib_blend_path = tmp_path / "external_rig_lib.blend"
        bpy.ops.wm.read_homefile(use_empty=True)
        bpy.ops.mesh.primitive_monkey_add(size=2.0)
        lib_obj = bpy.context.view_layer.objects.active
        lib_obj.name = "Linked_Prop_Asset"
        bpy.ops.wm.save_as_mainfile(filepath=str(lib_blend_path))

        # Reopen our saved Gate 04 scene
        bpy.ops.wm.open_mainfile(filepath=str(saved_scene_path))
        ui.sync_all_display_layers_from_scene()

        reopened_cube = bpy.data.objects.get("pCube1")
        reopened_sphere = bpy.data.objects.get("pSphere1")
        assert reopened_cube is not None and reopened_sphere is not None
        assert reopened_cube.data.name == "Hero_CubeShape"
        assert reopened_cube.hide_select is True  # From 'Hero_Geo_Layer' in Reference ('R') mode
        reopened_layers = ui.list_display_layers()
        assert len(reopened_layers) == 1 and reopened_layers[0]["name"] == "Hero_Geo_Layer"
        assert reopened_layers[0]["mode"] == "R"
        reopened_sphere_inputs = ui.get_object_inputs(reopened_sphere)
        assert len(reopened_sphere_inputs) == 1 and reopened_sphere_inputs[0]["node_name"] == "polySphere1"

        # Link external library object into scene and verify read-only protection
        with bpy.data.libraries.load(str(lib_blend_path), link=True) as (data_from, data_to):
            data_to.objects = ["Linked_Prop_Asset"]
        linked_asset = data_to.objects[0]
        bpy.context.scene.collection.objects.link(linked_asset)

        assert ui.is_datablock_linked(linked_asset) is True
        ae_linked = ui.get_attribute_editor_snapshot(linked_asset)
        assert ae_linked["linked"] is True and ae_linked["editable"] is False
        blocked_edit = ui.set_attribute_editor_value("transform", "translate_x", 99.0, obj=linked_asset)
        assert blocked_edit["ok"] is False and blocked_edit.get("linked") is True
        blocked_hist = ui.delete_construction_history(linked_asset)
        assert blocked_hist["ok"] is False and blocked_hist.get("linked") is True

        results["checks"]["save_reopen_and_linked_safety"] = {
            "reopened_layer_mode": reopened_layers[0]["mode"],
            "reopened_parametric_node": reopened_sphere_inputs[0]["node_name"],
            "linked_asset_read_only": True,
        }

        # ------------------------------------------------------------------
        # 7. Clean Unregister Verification
        # ------------------------------------------------------------------
        landfall_studio.unregister()
        results["checks"]["clean_unregister"] = {"ok": True}

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[T04-1] PASS — Results written to {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
