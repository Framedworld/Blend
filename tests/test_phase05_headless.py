"""Gate 05 Headless Verification Suite (`T05-1`):
Modeling Caddies, Target Weld, Scoped Make Live, Quad Draw, Non-Deformer History,
Read-Only Scene Diagnostics, and Material-Preserving UV / Texel Density.
"""

from __future__ import annotations

import json
import math
import os
import sys
import unittest
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio import commands, modeling


def _reset_clean_scene() -> None:
    modeling.clear_modeling_state()
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _scene_mutation_signature(scene) -> tuple:
    """Capture an immutable signature of every mesh's counts, vertex coords, modifiers, materials, and transforms."""
    items = []
    for obj in sorted(scene.objects, key=lambda o: o.name):
        mat_tuple = tuple(round(v, 5) for row in obj.matrix_world for v in row)
        mods = tuple((m.name, m.type) for m in obj.modifiers)
        if obj.type == "MESH" and obj.data is not None:
            me = obj.data
            v_coords = tuple(
                (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
                for v in me.vertices
            )
            p_mats = tuple(int(p.material_index) for p in me.polygons)
            items.append(
                (
                    obj.name,
                    mat_tuple,
                    mods,
                    len(me.vertices),
                    len(me.edges),
                    len(me.polygons),
                    v_coords,
                    p_mats,
                )
            )
        else:
            items.append((obj.name, obj.type, mat_tuple, mods))
    return tuple(items)


class TestPhase05ModelingUVDiagnosticsHeadless(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        landfall_studio.register()

    @classmethod
    def tearDownClass(cls):
        try:
            landfall_studio.unregister()
        except Exception:
            pass

    def setUp(self):
        _reset_clean_scene()

    def test_01_target_weld_and_in_viewport_caddies_with_repeat(self):
        """Verify Target Weld (point-to-point & midpoint) and Extrude/Bevel/Bridge/Connect caddies + G repeat."""
        # 1. Target Weld point-to-point (snap to target)
        bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0.0, 0.0, 0.0))
        plane = bpy.context.view_layer.objects.active
        plane.name = "WeldPlane"
        target_co = Vector(plane.data.vertices[1].co)

        weld_res = modeling.weld_vertices_target_weld(
            plane, source_vert_index=0, target_vert_index=1, merge_to_center=False
        )
        self.assertTrue(weld_res["ok"], f"TargetWeld failed: {weld_res}")
        self.assertEqual(weld_res["verts_before"], 4)
        self.assertEqual(weld_res["verts_after"], 3)
        self.assertAlmostEqual(
            (Vector(weld_res["welded_co"]) - target_co).length, 0.0, places=4
        )

        # 2. Extrude Caddy (`polyExtrudeFace1`) with non-destructive scrubbing + G repeat
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(4.0, 0.0, 0.0))
        cube = bpy.context.view_layer.objects.active
        cube.name = "CaddyCube"
        for p in cube.data.polygons:
            p.select = False
        cube.data.polygons[0].select = True

        ext_res = modeling.invoke_modeling_caddy("EXTRUDE", cube, {"thickness": 0.25, "offset": 0.0, "divisions": 1})
        self.assertTrue(ext_res["ok"])
        verts_after_first_extrude = len(cube.data.vertices)
        self.assertGreater(verts_after_first_extrude, 8)

        # Scrubbing thickness and offset must NOT stack duplicate extrusions!
        scrub1 = modeling.scrub_caddy_parameter(delta_px=20.0, param_key="thickness")
        self.assertTrue(scrub1["ok"])
        self.assertEqual(
            len(cube.data.vertices),
            verts_after_first_extrude,
            "Caddy scrub stacked duplicate extrusion geometry instead of re-evaluating from baseline!",
        )
        scrub2 = modeling.set_caddy_parameter("offset", 0.12)
        self.assertTrue(scrub2["ok"])
        self.assertEqual(len(cube.data.vertices), verts_after_first_extrude)
        modeling.commit_caddy()

        # Repeat Last (`G`) should repeat the extrusion on current selection
        rep_res = commands.repeat_last_command()
        self.assertTrue(rep_res["ok"])
        self.assertGreater(len(cube.data.vertices), verts_after_first_extrude)

        # 3. Bevel Caddy (`polyBevel1`) with multi-segment scrubbing
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(8.0, 0.0, 0.0))
        bev_cube = bpy.context.view_layer.objects.active
        bev_cube.name = "BevelCube"
        for e in bev_cube.data.edges:
            e.select = True
        bev_res = modeling.invoke_modeling_caddy("BEVEL", bev_cube, {"offset": 0.15, "segments": 1})
        self.assertTrue(bev_res["ok"])
        v_seg1 = len(bev_cube.data.vertices)
        bev_seg3 = modeling.set_caddy_parameter("segments", 3)
        self.assertTrue(bev_seg3["ok"])
        self.assertGreater(len(bev_cube.data.vertices), v_seg1)
        modeling.commit_caddy()

        # 4. Connect Caddy (`polyConnectComponents1`)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(12.0, 0.0, 0.0))
        con_cube = bpy.context.view_layer.objects.active
        con_cube.name = "ConnectCube"
        for e in con_cube.data.edges:
            e.select = True
        con_res = modeling.invoke_modeling_caddy("CONNECT", con_cube, {"cuts": 2, "slide": 0.15, "pinch": 0.0})
        self.assertTrue(con_res["ok"])
        self.assertGreater(len(con_cube.data.vertices), 8)
        modeling.commit_caddy()

    def test_02_scoped_make_live_and_quad_draw_retopology(self):
        """Verify Make Live locks only the target surface and Quad Draw projects strictly to the live mesh."""
        bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, location=(0.0, 0.0, 0.0))
        sphere = bpy.context.view_layer.objects.active
        sphere.name = "HiRes_Sculpt_Sphere"

        # Place a bystander cube closer to query point (0, 0, 3.2) than the sphere (radius 2.0)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 3.0))
        bystander = bpy.context.view_layer.objects.active
        bystander.name = "Bystander_Cube"

        live_res = modeling.set_live_surface("HiRes_Sculpt_Sphere")
        self.assertTrue(live_res["ok"])
        self.assertTrue(live_res["active"])
        self.assertEqual(live_res["object_name"], "HiRes_Sculpt_Sphere")
        self.assertTrue(sphere.hide_select, "Live surface must be locked against accidental selection")
        self.assertFalse(bystander.hide_select, "Bystander mesh must remain selectable")

        # Project point from (0, 0, 3.2): even though Bystander_Cube is right at Z=2.5..3.5,
        # scoped Make Live projection must land strictly on HiRes_Sculpt_Sphere (radius ~ 2.0)!
        proj = modeling.project_point_to_live_surface((0.0, 0.0, 3.2))
        self.assertIsNotNone(proj)
        self.assertEqual(proj["live_object"], "HiRes_Sculpt_Sphere")
        hit_loc = Vector(proj["location"])
        self.assertAlmostEqual(hit_loc.length, 2.0, delta=0.08)

        # Quad Draw: plot 4 dots on the upper hemisphere, fill quad, extrude strip, loop cut, and relax
        modeling.clear_quad_draw_dots()
        pts = [
            (-0.6, -0.6, 2.5),
            (0.6, -0.6, 2.5),
            (0.6, 0.6, 2.5),
            (-0.6, 0.6, 2.5),
        ]
        for pt in pts:
            d_res = modeling.plot_quad_draw_dot(pt)
            self.assertTrue(d_res["ok"])
            self.assertTrue(d_res["projected"])

        fill_res = modeling.fill_quad_from_dots()
        self.assertTrue(fill_res["ok"], f"Quad Draw fill failed: {fill_res}")
        self.assertEqual(fill_res["faces"], 1)

        retopo_obj = bpy.data.objects.get(fill_res["object_name"])
        self.assertIsNotNone(retopo_obj)
        # Verify face normal points outward (+Z) matching the sphere hemisphere
        poly_normal = retopo_obj.data.polygons[0].normal
        self.assertGreater(poly_normal.z, 0.5, f"Quad normal should align with live surface normal, got {poly_normal}")

        # Tab-drag extrude boundary edge strip
        ext_strip = modeling.extrude_quad_draw_strip(
            retopo_obj, edge_index=0, delta_world=(0.0, -0.7, 0.0)
        )
        self.assertTrue(ext_strip["ok"])
        self.assertEqual(ext_strip["faces"], 2)

        # Ctrl-click loop cut
        loop_res = modeling.insert_quad_draw_loop(retopo_obj, edge_index=0,cuts=1)
        self.assertTrue(loop_res["ok"])
        self.assertGreaterEqual(loop_res["faces"], 3)

        # Shift-drag relax projected onto live sphere
        relax_res = modeling.relax_quad_draw_verts(retopo_obj, iterations=2, strength=0.5)
        self.assertTrue(relax_res["ok"])
        for v in retopo_obj.data.vertices:
            w_co = retopo_obj.matrix_world @ v.co
            self.assertAlmostEqual(
                w_co.length,
                2.0,
                delta=0.1,
                msg="Relaxed Quad Draw vertex drifted off the Make Live sphere!",
            )

        # Clear Make Live and verify hide_select restoration
        clear_res = modeling.clear_live_surface()
        self.assertFalse(clear_res["active"])
        self.assertFalse(sphere.hide_select)

    def test_03_non_deformer_history_and_guarded_transforms(self):
        """Verify Delete Non-Deformer History preserves Armature + weights, guards Shape Keys, and guards child transforms."""
        # 1. Rigged mesh with Armature deformer + vertex weights + Bevel & Subsurf modeling modifiers
        bpy.ops.object.armature_add(location=(0.0, 0.0, 0.0))
        arm_obj = bpy.context.view_layer.objects.active
        arm_obj.name = "Hero_Rig"

        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
        rig_mesh = bpy.context.view_layer.objects.active
        rig_mesh.name = "Hero_Body"

        vg = rig_mesh.vertex_groups.new(name="Bone_Root")
        vg.add(list(range(len(rig_mesh.data.vertices))), 0.85, "REPLACE")

        mod_bev = rig_mesh.modifiers.new(name="polyBevel1", type="BEVEL")
        mod_bev.width = 0.12
        mod_sub = rig_mesh.modifiers.new(name="polySubd1", type="SUBSURF")
        mod_sub.levels = 1
        mod_arm = rig_mesh.modifiers.new(name="skinCluster1", type="ARMATURE")
        mod_arm.object = arm_obj

        hist_before = modeling.inspect_construction_history(rig_mesh)
        self.assertEqual(hist_before["modeling_count"], 2)
        self.assertEqual(hist_before["deformer_count"], 1)

        nd_res = modeling.delete_non_deformer_history(rig_mesh)
        self.assertTrue(nd_res["ok"], f"Non-deformer history bake failed: {nd_res}")
        self.assertEqual(nd_res["applied_modeling_modifiers"], ["polyBevel1", "polySubd1"])
        self.assertEqual(nd_res["preserved_deformer_modifiers"], ["skinCluster1"])
        self.assertEqual([m.name for m in rig_mesh.modifiers], ["skinCluster1"])
        self.assertGreater(len(rig_mesh.data.vertices), 8, "Modeling modifiers were not baked into mesh topology")
        self.assertIn("Bone_Root", [g.name for g in rig_mesh.vertex_groups])

        # 2. Shape Keys + topology-changing modifier must be guarded
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(5.0, 0.0, 0.0))
        morph_mesh = bpy.context.view_layer.objects.active
        morph_mesh.name = "Morph_Head"
        morph_mesh.shape_key_add(name="Basis")
        sk_smile = morph_mesh.shape_key_add(name="Smile")
        sk_smile.data[0].co.z += 0.5
        morph_mesh.modifiers.new(name="SubsurfHazard", type="SUBSURF")

        guard_res = modeling.delete_non_deformer_history(morph_mesh)
        self.assertFalse(guard_res["ok"])
        self.assertTrue(guard_res["guarded"])
        self.assertTrue(guard_res["guarded_shape_keys"])
        self.assertEqual(len(morph_mesh.data.shape_keys.key_blocks), 2)
        self.assertEqual(len(morph_mesh.modifiers), 1)

        # 3. Parent-Child hierarchy: Freeze Transformations & Center Pivot must preserve child world-space geometry
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(2.0, 3.0, 1.0))
        parent_obj = bpy.context.view_layer.objects.active
        parent_obj.name = "Parent_Hull"
        parent_obj.rotation_euler = (0.2, -0.3, 0.4)
        parent_obj.scale = (1.5, 1.2, 0.8)

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(4.0, 5.0, 2.0))
        child_obj = bpy.context.view_layer.objects.active
        child_obj.name = "Child_Turret"
        child_obj.parent = parent_obj
        bpy.context.view_layer.update()
        child_obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
        bpy.context.view_layer.update()

        child_world_verts_before = [child_obj.matrix_world @ Vector(v.co) for v in child_obj.data.vertices]

        fz_res = modeling.freeze_transformations_guarded(parent_obj)
        self.assertTrue(fz_res["ok"], f"Guarded Freeze Transforms failed: {fz_res}")
        self.assertLess(fz_res["max_child_matrix_diff"], 1e-4)

        cp_res = modeling.center_or_bake_pivot_guarded(parent_obj, mode="CENTER")
        self.assertTrue(cp_res["ok"], f"Guarded Center Pivot failed: {cp_res}")
        self.assertLess(cp_res["max_child_matrix_diff"], 1e-4)

        bpy.context.view_layer.update()
        child_world_verts_after = [child_obj.matrix_world @ Vector(v.co) for v in child_obj.data.vertices]
        max_v_drift = max(
            (a - b).length for a, b in zip(child_world_verts_before, child_world_verts_after)
        )
        self.assertLess(max_v_drift, 1e-4, f"Child world vertices drifted by {max_v_drift} after parent freeze/pivot!")

    def test_04_read_only_scene_diagnostics_and_uv_material_preservation(self):
        """Verify run_scene_diagnostics is 100% read-only and UV/Texel Density ops preserve multi-material assignments."""
        # Build a mesh with deliberate N-gon, non-manifold wire edge, zero-area face, and non-planar quad
        bm = bmesh.new()
        # 5-gon (N-gon)
        v0 = bm.verts.new((0.0, 0.0, 0.0))
        v1 = bm.verts.new((1.0, 0.0, 0.0))
        v2 = bm.verts.new((1.4, 1.0, 0.0))
        v3 = bm.verts.new((0.5, 1.6, 0.0))
        v4 = bm.verts.new((-0.4, 1.0, 0.0))
        bm.faces.new((v0, v1, v2, v3, v4))

        # Non-planar quad
        q0 = bm.verts.new((2.0, 0.0, 0.0))
        q1 = bm.verts.new((3.0, 0.0, 0.0))
        q2 = bm.verts.new((3.0, 1.0, 0.85))  # lifted corner
        q3 = bm.verts.new((2.0, 1.0, 0.0))
        bm.faces.new((q0, q1, q2, q3))

        # Zero-area degenerate triangle (collinear points)
        z0 = bm.verts.new((4.0, 0.0, 0.0))
        z1 = bm.verts.new((4.0, 0.0, 0.0))
        z2 = bm.verts.new((5.0, 0.0, 0.0))
        bm.faces.new((z0, z1, z2))

        # Loose wire edge (non-manifold)
        w0 = bm.verts.new((6.0, 0.0, 0.0))
        w1 = bm.verts.new((7.0, 0.0, 0.0))
        bm.edges.new((w0, w1))

        me_defect = bpy.data.meshes.new("DefectMeshShape")
        bm.to_mesh(me_defect)
        bm.free()
        obj_defect = bpy.data.objects.new("DefectMesh", me_defect)
        bpy.context.collection.objects.link(obj_defect)

        # Create a non-uniformly scaled parent + rotated child to induce transform shear
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-3.0, 0.0, 0.0))
        shear_p = bpy.context.view_layer.objects.active
        shear_p.name = "ShearParent"
        shear_p.scale = (3.0, 0.4, 1.0)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-3.0, 1.0, 0.0))
        shear_c = bpy.context.view_layer.objects.active
        shear_c.name = "ShearChild"
        shear_c.parent = shear_p
        shear_c.rotation_euler = (0.6, 0.5, 0.3)
        bpy.context.view_layer.update()

        sig_before = _scene_mutation_signature(bpy.context.scene)
        diag = modeling.run_scene_diagnostics(bpy.context.scene)
        sig_after = _scene_mutation_signature(bpy.context.scene)

        self.assertEqual(
            sig_before,
            sig_after,
            "run_scene_diagnostics() mutated scene state instead of being strictly read-only!",
        )
        self.assertTrue(diag["read_only_verified"])
        issues = diag["mesh_issues"]
        self.assertGreaterEqual(issues["ngons"], 1)
        self.assertGreaterEqual(issues["nonmanifold"], 1)
        self.assertGreaterEqual(issues["nonplanar"], 1)
        self.assertGreaterEqual(issues["zero_area_faces"], 1)
        self.assertGreaterEqual(diag["transform_issues"]["sheared_transforms"], 1)

        # UV & Texel Density + Material Preservation
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 6.0, 0.0))
        uv_cube = bpy.context.view_layer.objects.active
        uv_cube.name = "Asset_Crate"
        mat_a = bpy.data.materials.new(name="Mat_Hull")
        mat_b = bpy.data.materials.new(name="Mat_Trim")
        uv_cube.data.materials.append(mat_a)
        uv_cube.data.materials.append(mat_b)
        for idx, p in enumerate(uv_cube.data.polygons):
            p.material_index = idx % 2

        uv_cube.data.uv_layers.new(name="temp_trash_uv")
        mat_snap_before = modeling.snapshot_material_assignments(uv_cube)

        unwrap_res = modeling.uv_unwrap_and_pack(uv_cube, method="SMART", margin=0.03)
        self.assertTrue(unwrap_res["ok"])
        self.assertTrue(unwrap_res["materials_preserved"])

        td_set = modeling.set_mesh_texel_density(uv_cube, target_td=256.0, map_size=2048)
        self.assertTrue(td_set["ok"])
        self.assertTrue(td_set["materials_preserved"])
        self.assertAlmostEqual(td_set["new_td"], 256.0, delta=1.5)

        clean_res = modeling.uv_cleanup_sets_guarded(uv_cube, keep_names=[uv_cube.data.uv_layers[0].name])
        self.assertTrue(clean_res["ok"])
        self.assertIn("temp_trash_uv", clean_res["removed_uv_sets"])
        self.assertTrue(clean_res["materials_preserved"])

        mat_snap_after = modeling.snapshot_material_assignments(uv_cube)
        self.assertEqual(mat_snap_before, mat_snap_after)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TestPhase05ModelingUVDiagnosticsHeadless
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(
        "PHASE05_HEADLESS_RESULT:"
        + json.dumps(
            {
                "ok": result.wasSuccessful(),
                "tests_run": result.testsRun,
                "failures": len(result.failures),
                "errors": len(result.errors),
            }
        )
    )
    sys.exit(0 if result.wasSuccessful() else 1)
