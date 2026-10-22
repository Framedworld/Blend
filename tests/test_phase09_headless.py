"""Phase 09 Headless Test Suite — Blender Native Feature Continuity & Bridge (`landfall_studio.continuity`).

Run via:
    blender -b --factory-startup -P tests/test_phase09_headless.py
"""

from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import bpy  # noqa: E402
import landfall_studio  # noqa: E402
from landfall_studio import continuity, keymaps, ui, viewport  # noqa: E402


class TestPhase09Headless(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        landfall_studio.register()

    @classmethod
    def tearDownClass(cls):
        landfall_studio.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        keymaps.apply_profile(bpy.context, profile="MAYA")

    def test_01_maya_4_5_6_7_viewport_shading_continuity(self):
        """Verify Maya 4 (Wireframe), 5 (Smooth Shaded), 6 (Textured), 7 (Use All Lights), X-Ray, and Wire on Shaded."""
        res_prim = ui.create_maya_primitive("SPHERE", radius=1.5)
        self.assertTrue(res_prim["ok"])

        for mode_key, expected_id in (
            ("4", "WIREFRAME"),
            ("5", "SMOOTH_SHADED"),
            ("6", "TEXTURED"),
            ("7", "ALL_LIGHTS"),
        ):
            r = bpy.ops.landfall_studio.viewport_shading(mode=mode_key)
            self.assertEqual(r, {"FINISHED"})
            st = continuity.get_viewport_shading_state()
            self.assertTrue(st["ok"])
            self.assertEqual(st["maya_mode"], mode_key)
            self.assertEqual(st["maya_id"], expected_id)

        # Toggle Wireframe on Shaded and X-Ray
        st_before = continuity.get_viewport_shading_state()
        st_wire = continuity.set_maya_viewport_shading("WIRE_ON_SHADED")
        self.assertNotEqual(st_wire["wire_on_shaded"], st_before["wire_on_shaded"])

        st_xray = continuity.set_maya_viewport_shading("XRAY")
        self.assertTrue(st_xray["ok"])

    def test_02_soft_selection_b_key_and_proportional_editing_sync(self):
        """Verify Soft Selection (B) toggles and synchronizes two-way with Blender Proportional Editing (O) & Tool Settings."""
        ts = bpy.context.scene.tool_settings
        ts.use_proportional_edit = False
        ts.use_proportional_edit_objects = False

        # 1. Toggle Soft Selection ON via operator (B tap)
        r1 = bpy.ops.landfall_studio.soft_selection(action="TOGGLE")
        self.assertEqual(r1, {"FINISHED"})
        st1 = continuity.get_soft_selection_state()
        self.assertTrue(st1["enabled"])
        self.assertTrue(st1["object_mode_enabled"])
        self.assertTrue(ts.use_proportional_edit)

        # 2. Set radius and falloff curve via operator (Hold B + LMB drag equivalent)
        r2 = bpy.ops.landfall_studio.soft_selection(
            action="SET",
            enabled=True,
            radius=2.75,
            falloff_curve="SPHERE",
        )
        self.assertEqual(r2, {"FINISHED"})
        self.assertAlmostEqual(ts.proportional_size, 2.75, places=3)
        self.assertEqual(ts.proportional_edit_falloff, "SPHERE")

        # Verify Tool Settings snapshot reflects exact Soft Selection state
        ts_snap = ui.get_tool_settings_snapshot()
        self.assertTrue(ts_snap["soft_select_enabled"])
        self.assertAlmostEqual(ts_snap["soft_select_radius"], 2.75, places=3)
        self.assertEqual(ts_snap["soft_select_falloff"], "SPHERE")

        # 3. Mutate via Tool Settings -> verify continuity state matches
        ui.set_tool_setting("soft_select_radius", 1.35)
        ui.set_tool_setting("soft_select_falloff", "SMOOTH")
        st3 = continuity.get_soft_selection_state()
        self.assertAlmostEqual(st3["radius"], 1.35, places=3)
        self.assertEqual(st3["falloff_curve"], "SMOOTH")

        # 4. Toggle OFF via B
        bpy.ops.landfall_studio.soft_selection(action="TOGGLE")
        self.assertFalse(ts.use_proportional_edit)
        self.assertFalse(ts.use_proportional_edit_objects)

    def test_03_shadowed_shortcuts_rehomed_and_verified(self):
        """Verify all shadowed Blender shortcuts have bound, working fallback chords (Ctrl+Shift+A, DEL/BackSpace, Shift+F, Alt+V, Ctrl+Shift+Q)."""
        smap = continuity.get_shadowed_shortcut_map()
        self.assertGreaterEqual(len(smap), 10)
        for row in smap:
            self.assertTrue(
                row["fallback_bound"],
                f"Fallback operator {row['fallback_operator']} not bound for {row['maya_key']}",
            )

        # Create two cubes and test Ctrl+Shift+A (select_all_toggle) and DEL (smart_delete)
        ui.create_maya_primitive("CUBE", width=1.0)
        ui.create_maya_primitive("SPHERE", radius=1.0)
        self.assertEqual(len(bpy.data.objects), 2)

        bpy.ops.landfall_studio.select_all_toggle(action="DESELECT")
        self.assertEqual(len(bpy.context.selected_objects), 0)

        bpy.ops.landfall_studio.select_all_toggle(action="SELECT")
        self.assertEqual(len(bpy.context.selected_objects), 2)

        # Delete one selected object via smart_delete
        bpy.ops.landfall_studio.select_all_toggle(action="DESELECT")
        first_obj = bpy.data.objects[0]
        first_obj.select_set(True)
        bpy.context.view_layer.objects.active = first_obj
        bpy.ops.landfall_studio.smart_delete()
        self.assertEqual(len(bpy.data.objects), 1)

    def test_04_native_editors_and_modes_bridge(self):
        """Verify Geometry Nodes, Shader Editor, UV Editor, Sculpt Mode, and Grease Pencil bridges work deterministically."""
        res_prim = ui.create_maya_primitive("CUBE", width=2.0)
        cube = bpy.data.objects[res_prim["object_name"]]
        bpy.context.view_layer.objects.active = cube

        # 1. Geometry Nodes bridge
        gn = continuity.open_native_editor_or_mode("GEOMETRY_NODES")
        self.assertTrue(gn["ok"])
        self.assertIn("geometry_nodes", gn)
        self.assertGreaterEqual(gn["geometry_nodes"]["node_count"], 2)
        self.assertTrue(any(m.type == "NODES" for m in cube.modifiers))

        # 2. Sculpt Mode bridge & return to Object Mode
        sc = continuity.open_native_editor_or_mode("SCULPT_MODE")
        self.assertTrue(sc["ok"])
        self.assertEqual(sc["mode_after"], "SCULPT")

        ob = continuity.open_native_editor_or_mode("OBJECT_MODE")
        self.assertTrue(ob["ok"])
        self.assertEqual(ob["mode_after"], "OBJECT")

        # 3. UV Editor bridge & return to Object Mode
        bpy.context.view_layer.objects.active = cube
        uv = continuity.open_native_editor_or_mode("UV_EDITOR")
        # A real UV window cannot open headlessly. Require the component-mode
        # contract here; the native full UX file suite verifies the actual window.
        self.assertFalse(uv["ok"])
        self.assertFalse(uv.get('editor_opened',False))
        self.assertTrue(uv.get('error'))
        self.assertEqual(uv["mode_after"], "EDIT_MESH")
        continuity.open_native_editor_or_mode("OBJECT_MODE")

        # 4. Grease Pencil bridge
        gp = continuity.open_native_editor_or_mode("GREASE_PENCIL")
        self.assertTrue(gp["ok"])
        self.assertTrue(gp.get("grease_pencil_object"))

    def test_05_protected_context_keymap_integrity(self):
        """Verify zero Studio keymap leaks into Sculpt, Grease Pencil, Paint, Node Editor, Text, or Console."""
        rep = keymaps.scan_keymap_conflicts()
        self.assertTrue(rep["clean"], f"Keymap conflict scan failed: {rep}")
        self.assertEqual(len(rep["protected_context_leaks"]), 0)
        self.assertEqual(len(rep["duplicate_studio_bindings"]), 0)
        self.assertFalse(rep["duplicate_hotbox_on_space"])

    def test_06_shelf_and_hud_continuity_integration(self):
        """Verify FX / Nodes shelf items and HUD continuity snapshot."""
        ui.create_maya_primitive("CUBE", width=2.0)
        r_gn = ui.execute_shelf_item("geometry_nodes")
        self.assertTrue(r_gn["ok"])

        r_soft = ui.execute_shelf_item("soft_select")
        self.assertTrue(r_soft["ok"])

        hud_st = viewport.get_hud_state()
        self.assertTrue(hud_st["soft_select_enabled"])
        self.assertIn("maya_shading_mode", hud_st)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPhase09Headless)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
