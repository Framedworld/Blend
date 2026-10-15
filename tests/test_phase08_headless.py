"""Phase 08 Headless Test Suite — Maya Hypershade Lookdev, Animation Layers, and Skin Weight Layers.

Run with:
    blender -b --factory-startup -P tests/test_phase08_headless.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import bpy
import landfall_studio
from landfall_studio import advanced, character, ui


class TestPhase08AdvancedHypershadeAndLayersHeadless(unittest.TestCase):
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
        bpy.ops.wm.read_homefile(use_empty=True)

    def test_01_hypershade_templates_assignment_and_select_by_material(self):
        """Verify Maya Hypershade shader templates, 1-click assignment, parameter scrubbing, and Select Objects With Material."""
        templates = advanced.get_shader_templates()
        self.assertGreaterEqual(len(templates), 4)
        self.assertIn("standard", templates)
        self.assertIn("Metal", templates)

        c1 = ui.create_maya_primitive("CUBE", name="pCubeA")["object"]
        c2 = ui.create_maya_primitive("SPHERE", name="pSphereB")["object"]
        for o in bpy.data.objects:
            o.select_set(False)
        c1.select_set(True)
        bpy.context.view_layer.objects.active = c1

        res = advanced.create_from_template(
            "metallic",
            name="aiHeroMetal_MAT",
            assign_to_selection=True,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["material"], "aiHeroMetal_MAT")
        self.assertIn(c1.name, res["assigned_objects"])

        # Scrub roughness parameter
        p_res = advanced.set_material_parameter("aiHeroMetal_MAT", "roughness", 0.18)
        self.assertTrue(p_res["ok"])
        self.assertAlmostEqual(p_res["properties"]["roughness"], 0.18, places=3)

        # Deselect all, then Select Objects With Material
        c1.select_set(False)
        sel_res = advanced.select_objects_with_material("aiHeroMetal_MAT")
        self.assertTrue(sel_res["ok"])
        self.assertEqual(sel_res["selected_objects"], [c1.name])
        self.assertNotIn(c2.name, sel_res["selected_objects"])

    def test_02_hypershade_pbr_texture_auto_wiring_and_colorspace_audit(self):
        """Verify pythontk.MapFactory + blendertk.MatUtils PBR texture auto-wiring and sRGB vs Non-Color fixing."""
        cube = ui.create_maya_primitive("CUBE", name="pLookdevCube")["object"]
        mat_res = advanced.create_from_template(
            "standard",
            name="aiProp_MAT",
            assign_to_selection=True,
        )
        self.assertTrue(mat_res["ok"])

        with tempfile.TemporaryDirectory() as tmpdir:
            tex_paths = []
            for map_suffix in ("HeroProp_BaseColor.png", "HeroProp_Roughness.png", "HeroProp_Normal.png"):
                img = bpy.data.images.new(map_suffix, width=8, height=8)
                img.pixels = [0.5, 0.5, 0.8, 1.0] * (8 * 8)
                fpath = os.path.join(tmpdir, map_suffix)
                img.filepath_raw = fpath
                img.file_format = "PNG"
                img.save()
                bpy.data.images.remove(img)
                tex_paths.append(fpath)

            wire_res = advanced.auto_wire_pbr_textures(
                "aiProp_MAT",
                texture_paths=tex_paths,
            )
            self.assertTrue(wire_res["ok"])
            self.assertGreaterEqual(len(wire_res["wired_sockets"]), 3)
            self.assertIn("Base Color", wire_res["wired_sockets"])
            self.assertIn("Roughness", wire_res["wired_sockets"])
            self.assertIn("Normal", wire_res["wired_sockets"])

            audit = advanced.audit_scene_textures()
            self.assertTrue(audit["ok"])
            self.assertGreaterEqual(audit["total_images"], 3)
            self.assertEqual(audit["missing_count"], 0)

    def test_03_hypershade_duplicate_and_unused_material_cleanup(self):
        """Verify blendertk.MatUtils duplicate material merging and unused material purge."""
        cube = ui.create_maya_primitive("CUBE", name="pCleanCube")["object"]
        m_used = bpy.data.materials.new("charSkin_MAT")
        m_unused = bpy.data.materials.new("orphanUnused_MAT")
        cube.data.materials.append(m_used)

        res = advanced.cleanup_scene_materials(merge_duplicates=True, delete_unused=True)
        self.assertTrue(res["ok"])
        self.assertIn("charSkin_MAT", res["remaining_materials"])
        self.assertIsNone(bpy.data.materials.get("orphanUnused_MAT"))

    def test_04_maya_animation_layers_add_override_mute_and_weight(self):
        """Verify NLA-backed Maya Animation Layers (BaseAnimation + Additive/Override layers with weight & mute)."""
        cube = ui.create_maya_primitive("CUBE", name="pAnimCube")["object"]
        base_res = advanced.ensure_base_animation_layer(cube)
        self.assertTrue(base_res["ok"])

        # Key BaseAnimation at frame 1 (location.z = 1.0) and frame 10 (location.z = 3.0)
        advanced.keyframe_on_anim_layer(
            cube,
            "BaseAnimation",
            "location",
            2,
            value=1.0,
            frame=1,
        )
        advanced.keyframe_on_anim_layer(
            cube,
            "BaseAnimation",
            "location",
            2,
            value=3.0,
            frame=10,
        )

        # Create Additive layer AnimLayer1_Recoil adding +2.0 to Z
        l_res = advanced.create_anim_layer(
            cube,
            "AnimLayer1_Recoil",
            mode="ADD",
            weight=1.0,
        )
        self.assertTrue(l_res["ok"])
        advanced.keyframe_on_anim_layer(
            cube,
            "AnimLayer1_Recoil",
            "location",
            2,
            value=2.0,
            frame=1,
        )
        advanced.keyframe_on_anim_layer(
            cube,
            "AnimLayer1_Recoil",
            "location",
            2,
            value=2.0,
            frame=10,
        )

        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        self.assertAlmostEqual(float(cube.location.z), 3.0, places=3)

        # Set AnimLayer1_Recoil weight to 0.5 -> Z should be 1.0 + 0.5 * 2.0 = 2.0
        advanced.set_anim_layer_state(cube, "AnimLayer1_Recoil", weight=0.5)
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        self.assertAlmostEqual(float(cube.location.z), 2.0, places=3)

        # Mute AnimLayer1_Recoil -> Z should return to BaseAnimation (1.0)
        advanced.set_anim_layer_state(cube, "AnimLayer1_Recoil", mute=True)
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        self.assertAlmostEqual(float(cube.location.z), 1.0, places=3)

    def test_05_non_destructive_skin_weight_layers_preserve_locked_influences(self):
        """Verify non-destructive Skin Weight Layers respect locked vertex groups (`vg.lock_weight`)."""
        cube = ui.create_maya_primitive("CUBE", name="pSkinnedMesh")["object"]
        vg_root = cube.vertex_groups.new(name="joint_root")
        vg_spine = cube.vertex_groups.new(name="joint_spine")
        vg_chest = cube.vertex_groups.new(name="joint_chest")

        n_verts = len(cube.data.vertices)
        for v_idx in range(n_verts):
            vg_root.add([v_idx], 0.4, "REPLACE")
            vg_spine.add([v_idx], 0.6, "REPLACE")
            vg_chest.add([v_idx], 0.0, "REPLACE")

        # Lock joint_root (0.4 must remain untouched!)
        vg_root.lock_weight = True

        base_w = advanced.ensure_base_weight_layer(cube)
        self.assertTrue(base_w["ok"])

        lyr_res = advanced.create_weight_layer(
            cube,
            "ShoulderFix_Layer",
            mode="OVERRIDE",
            weight=1.0,
        )
        self.assertTrue(lyr_res["ok"])

        # Attempting to author directly onto locked joint_root is blocked
        blocked_res = advanced.set_layer_vertex_weights(
            cube,
            "ShoulderFix_Layer",
            "joint_root",
            {0: 0.9},
        )
        self.assertFalse(blocked_res["ok"])
        self.assertEqual(blocked_res["status"], "BLOCKED")

        # Override joint_chest on vertex 0 to 0.6 (remaining unlocked budget is 1.0 - 0.4 = 0.6)
        w_res = advanced.set_layer_vertex_weights(
            cube,
            "ShoulderFix_Layer",
            "joint_chest",
            {0: 0.6},
            evaluate=True,
        )
        self.assertTrue(w_res["ok"])
        self.assertIn("joint_root", w_res["evaluation"]["locked_groups_preserved"])

        # Verify locked joint_root is still exactly 0.4 on vertex 0, and joint_chest received weight
        self.assertAlmostEqual(vg_root.weight(0), 0.4, places=4)
        self.assertGreater(vg_chest.weight(0), 0.25)
        self.assertAlmostEqual(
            vg_root.weight(0) + vg_spine.weight(0) + vg_chest.weight(0),
            1.0,
            places=4,
        )

        # Disable ShoulderFix_Layer -> vertex 0 returns to BaseWeights (root=0.4, spine=0.6, chest=0.0)
        advanced.set_weight_layer_state(cube, "ShoulderFix_Layer", enabled=False)
        self.assertAlmostEqual(vg_root.weight(0), 0.4, places=4)
        self.assertAlmostEqual(vg_spine.weight(0), 0.6, places=4)
        self.assertAlmostEqual(vg_chest.weight(0), 0.0, places=4)

    def test_06_hypershade_and_channel_box_ui_snapshots(self):
        """Verify Hypershade right-dock mode and Channel Box Animation Layer snapshot."""
        cube = ui.create_maya_primitive("CUBE", name="pUICube")["object"]
        advanced.create_from_template("car_paint", name="aiCarPaint_MAT", assign_to_selection=True)
        advanced.create_anim_layer(cube, "AnimLayer_UI", mode="ADD", weight=0.8)

        dock_res = ui.cycle_right_dock("HYPERSHADE")
        self.assertTrue(dock_res["ok"])
        self.assertEqual(dock_res["mode"], "HYPERSHADE")

        hs_snap = ui.get_hypershade_ui_snapshot()
        self.assertTrue(hs_snap["ok"])
        self.assertGreaterEqual(hs_snap["material_count"], 1)

        ui.cycle_right_dock("CHANNEL_BOX")
        cb_snap = ui.get_channels_snapshot()
        self.assertTrue(cb_snap["ok"])
        self.assertGreaterEqual(len(cb_snap["anim_layers"]), 2)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TestPhase08AdvancedHypershadeAndLayersHeadless
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
