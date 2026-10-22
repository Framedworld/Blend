"""Maya extrude parity: Ctrl+E caddy and manipulator absorption.

Maya's extrude manipulator edits the polyExtrudeFace node itself. In Studio the
native Move/Scale tool edits the cap, and the caddy must read that edit back as
Thickness / Offset / lateral translate instead of closing on the next change.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio import modeling
from landfall_studio.modeling import caddy


def _cap_world_z(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    return max(v.co.z for v in bm.verts if v.select)


def _cap_centre(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    selected = [v.co.copy() for v in bm.verts if v.select]
    return sum(selected, Vector()) / len(selected)


class TestMayaExtrudeHeadless(unittest.TestCase):
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
        modeling.clear_modeling_state()
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        self.obj = bpy.context.view_layer.objects.active
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.mesh.select_all(action="DESELECT")
        bm = bmesh.from_edit_mesh(self.obj.data)
        top = max(bm.faces, key=lambda f: f.calc_center_median().z)
        top.select_set(True)
        bmesh.update_edit_mesh(self.obj.data)

    def tearDown(self):
        caddy.commit_or_close_caddy()

    def test_01_ctrl_e_opens_zero_thickness_caddy(self):
        self.assertIn("FINISHED", bpy.ops.landfall_studio.maya_extrude())
        state = caddy.get_active_caddy_state()
        self.assertTrue(state["open"])
        self.assertEqual(state["tool"], "EXTRUDE")
        self.assertAlmostEqual(state["params"]["thickness"], 0.0)
        self.assertEqual(len(self.obj.data.vertices), 12)
        self.assertEqual(bpy.context.scene.transform_orientation_slots[0].type, "NORMAL")
        caddy.commit_or_close_caddy()
        self.assertEqual(bpy.context.scene.transform_orientation_slots[0].type, "GLOBAL")

    def test_02_manipulator_move_becomes_thickness(self):
        bpy.ops.landfall_studio.maya_extrude()
        bpy.ops.transform.translate(value=(0.0, 0.0, 0.6))
        state = caddy.get_active_caddy_state()
        self.assertTrue(state["open"])
        self.assertAlmostEqual(state["params"]["thickness"], 0.6, places=4)
        # Typing a new thickness keeps the caddy and replaces the dragged one.
        res = caddy.set_caddy_parameter("thickness", 0.9)
        self.assertTrue(res["ok"], res)
        self.assertAlmostEqual(_cap_world_z(self.obj), 1.9, places=4)
        self.assertEqual(len(self.obj.data.vertices), 12)

    def test_03_divisions_after_drag_keep_dragged_height(self):
        bpy.ops.landfall_studio.maya_extrude()
        bpy.ops.transform.translate(value=(0.0, 0.0, 0.5))
        res = caddy.set_caddy_parameter("divisions", 3)
        self.assertTrue(res["ok"], res)
        self.assertAlmostEqual(_cap_world_z(self.obj), 1.5, places=4)
        self.assertEqual(len(self.obj.data.vertices), 8 + 4 * 3)

    def test_04_lateral_move_and_uniform_scale_are_absorbed(self):
        bpy.ops.landfall_studio.maya_extrude()
        bpy.ops.transform.translate(value=(0.3, 0.0, 0.4))
        bpy.ops.transform.resize(value=(0.5, 0.5, 0.5))
        state = caddy.get_active_caddy_state()
        self.assertTrue(state["open"])
        self.assertAlmostEqual(state["params"]["thickness"], 0.4, places=4)
        self.assertAlmostEqual(state["params"]["offset"], 0.5, places=4)
        self.assertAlmostEqual(state["params"]["cap_shift"][0], 0.3, places=4)
        before = _cap_centre(self.obj)
        res = caddy.set_caddy_parameter("thickness", 0.4)
        self.assertTrue(res["ok"], res)
        self.assertLess((_cap_centre(self.obj) - before).length, 1e-4)

    def test_05_unrelated_edit_still_closes_caddy(self):
        bpy.ops.landfall_studio.maya_extrude()
        bm = bmesh.from_edit_mesh(self.obj.data)
        bm.verts.ensure_lookup_table()
        other = next(v for v in bm.verts if not v.select)
        other.co.x += 0.25
        bmesh.update_edit_mesh(self.obj.data)
        res = caddy.set_caddy_parameter("thickness", 0.5)
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("guarded"))
        bm = bmesh.from_edit_mesh(self.obj.data)
        self.assertTrue(any(abs(v.co.x - (other.co.x)) < 1e-6 for v in bm.verts))

    def test_06_rotation_is_not_misread(self):
        bpy.ops.landfall_studio.maya_extrude()
        bpy.ops.transform.translate(value=(0.0, 0.0, 0.5))
        bpy.ops.transform.rotate(value=0.5, orient_axis="X")
        res = caddy.set_caddy_parameter("thickness", 0.5)
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("guarded"))

    def test_07_edge_selection_falls_back(self):
        bpy.ops.mesh.select_mode(type="EDGE")
        bpy.ops.mesh.select_all(action="DESELECT")
        bm = bmesh.from_edit_mesh(self.obj.data)
        bm.edges.ensure_lookup_table()
        bm.edges[0].select_set(True)
        bmesh.update_edit_mesh(self.obj.data)
        result = bpy.ops.landfall_studio.maya_extrude()
        self.assertFalse(caddy.get_active_caddy_state()["open"])
        self.assertNotIn("FINISHED", result)

    def test_08_menu_route_matches_ctrl_e(self):
        from landfall_studio.ui import menus
        res = menus._caddy("EXTRUDE")()
        self.assertTrue(res["ok"], res)
        state = caddy.get_active_caddy_state()
        self.assertAlmostEqual(state["params"]["thickness"], 0.0)
        self.assertEqual(bpy.context.scene.transform_orientation_slots[0].type, "NORMAL")
        bpy.ops.transform.translate(value=(0.0, 0.0, 0.3))
        self.assertAlmostEqual(caddy.get_active_caddy_state()["params"]["thickness"], 0.3, places=4)

    def test_09_marking_menu_operator_matches_ctrl_e(self):
        self.assertIn("FINISHED", bpy.ops.landfall_studio.modeling_caddy(tool_type="EXTRUDE"))
        state = caddy.get_active_caddy_state()
        self.assertAlmostEqual(state["params"]["thickness"], 0.0)
        self.assertEqual(bpy.context.scene.transform_orientation_slots[0].type, "NORMAL")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestMayaExtrudeHeadless)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("MAYA_EXTRUDE_HEADLESS_RESULT:" + json.dumps({
        "ok": result.wasSuccessful(), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors)}))
    sys.exit(0 if result.wasSuccessful() else 1)
