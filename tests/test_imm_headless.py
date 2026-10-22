"""ZBrush-style Insert Multi Mesh: aligned, sized parts from a parts library."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import bpy
from mathutils import Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio.sculpt import ops, state


def _extent(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return max(max(c[a] for c in corners) - min(c[a] for c in corners) for a in range(3))


class TestImmHeadless(unittest.TestCase):
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0)
        self.body = bpy.context.active_object
        self.body.name = "Body"
        bpy.ops.object.mode_set(mode="SCULPT")

    def test_primitive_inserts_aligned_sized_and_keeps_active_subtool(self):
        normal = Vector((1, 1, 0)).normalized()
        res = ops.dispatch("IMM_INSERT", location=(0.7, 0.7, 0), normal=tuple(normal), size=0.4, part="CYLINDER")
        self.assertTrue(res["ok"], res)
        part = bpy.data.objects[res["subtool"]]
        self.assertTrue(part.name.startswith("SubTool · IMM Cylinder"))
        self.assertIs(bpy.context.view_layer.objects.active, self.body)
        self.assertEqual(bpy.context.mode, "SCULPT")
        axis = (part.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        self.assertGreater(axis.dot(normal), 0.9999)
        self.assertAlmostEqual(max(part.dimensions), 0.4, places=5)
        self.assertLess((part.matrix_world.translation - Vector((0.7, 0.7, 0))).length, 1e-6)
        self.assertIn(self.body.users_collection[0], part.users_collection)

    def test_largest_extent_matches_size(self):
        res = ops.dispatch("IMM_INSERT", location=(0, 0, 1), normal=(0, 0, 1), size=0.5, part="CUBE")
        part = bpy.data.objects[res["subtool"]]
        dims = sorted(part.dimensions)
        self.assertAlmostEqual(dims[-1], 0.5, places=5)

    def test_active_subtool_becomes_a_part_and_inserts(self):
        res = ops.dispatch("IMM_PART", part="__ACTIVE__")
        self.assertTrue(res["ok"])
        self.assertEqual(state.get().imm_part, res["part"])
        self.assertIn(res["part"], ops.imm_parts())
        coll = bpy.data.collections["IMM Parts"]
        self.assertTrue(coll.hide_viewport)
        inserted = ops.dispatch("IMM_INSERT", location=(0, 0, 1), normal=(0, 0, 1), size=0.2)
        part = bpy.data.objects[inserted["subtool"]]
        self.assertEqual(len(part.data.vertices), len(self.body.data.vertices))
        self.assertIsNot(part.data, self.body.data)
        self.assertAlmostEqual(max(part.dimensions), 0.2, places=4)

    def test_choosing_a_part_and_missing_part_error(self):
        ops.dispatch("IMM_PART", part="CUBE")
        self.assertEqual(state.get().imm_part, "CUBE")
        with self.assertRaises(RuntimeError):
            ops.dispatch("IMM_INSERT", location=(0, 0, 1), normal=(0, 0, 1), size=0.2, part="IMM Gone")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestImmHeadless)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("IMM_HEADLESS_RESULT:" + json.dumps({
        "ok": result.wasSuccessful(), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors)}))
    sys.exit(0 if result.wasSuccessful() else 1)
