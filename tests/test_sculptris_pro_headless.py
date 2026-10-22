"""Sculptris Pro on Blender dynamic topology: toggle, adaptive detail, guards."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio.sculpt import ops


class TestSculptrisProHeadless(unittest.TestCase):
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
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_uv_sphere_add()
        self.obj = bpy.context.active_object

    def sculpt(self):
        bpy.ops.object.mode_set(mode="SCULPT")

    def test_toggle_on_off_with_brush_adaptive_detail(self):
        self.sculpt()
        res = ops.dispatch("SCULPTRIS_PRO")
        self.assertTrue(res["sculptris_pro"])
        self.assertTrue(self.obj.use_dynamic_topology_sculpting)
        sculpt = bpy.context.scene.tool_settings.sculpt
        self.assertEqual(sculpt.detail_type_method, "BRUSH")
        self.assertAlmostEqual(sculpt.detail_percent, 25.0)
        self.assertFalse(ops.dispatch("SCULPTRIS_PRO")["sculptris_pro"])
        self.assertFalse(self.obj.use_dynamic_topology_sculpting)

    def test_explicit_enable_is_idempotent(self):
        self.sculpt()
        ops.dispatch("SCULPTRIS_PRO", enable=True)
        self.assertTrue(ops.dispatch("SCULPTRIS_PRO", enable=True)["sculptris_pro"])
        self.assertFalse(ops.dispatch("SCULPTRIS_PRO", enable=False)["sculptris_pro"])

    def test_refuses_subdivision_levels(self):
        mod = self.obj.modifiers.new("Multires", "MULTIRES")
        bpy.ops.object.multires_subdivide(modifier=mod.name, mode="CATMULL_CLARK")
        self.sculpt()
        with self.assertRaises(RuntimeError) as err:
            ops.dispatch("SCULPTRIS_PRO")
        self.assertIn("subdivision levels", str(err.exception))
        self.assertFalse(self.obj.use_dynamic_topology_sculpting)

    def test_refuses_layers(self):
        self.obj.shape_key_add(name="Basis")
        self.obj.shape_key_add(name="Layer 1")
        self.sculpt()
        with self.assertRaises(RuntimeError):
            ops.dispatch("SCULPTRIS_PRO")
        self.assertFalse(self.obj.use_dynamic_topology_sculpting)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSculptrisProHeadless)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("SCULPTRIS_PRO_HEADLESS_RESULT:" + json.dumps({
        "ok": result.wasSuccessful(), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors)}))
    sys.exit(0 if result.wasSuccessful() else 1)
