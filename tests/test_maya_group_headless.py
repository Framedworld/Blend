"""Maya Group / Ungroup and convert-selection hotkeys."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio.keymaps import profiles


def _close(a, b):
    return all(abs(x - y) < 1e-5 for ra, rb in zip(a, b) for x, y in zip(ra, rb))


class TestMayaGroupHeadless(unittest.TestCase):
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
        bpy.ops.mesh.primitive_cube_add(location=(2, 0, 0))
        self.a = bpy.context.active_object
        bpy.ops.mesh.primitive_cube_add(location=(-2, 0, 4), rotation=(0.3, 0, 0))
        self.b = bpy.context.active_object
        for obj in (self.a, self.b):
            obj.select_set(True)

    def test_group_keeps_world_and_centres_pivot(self):
        before = {o.name: o.matrix_world.copy() for o in (self.a, self.b)}
        self.assertIn("FINISHED", bpy.ops.landfall_studio.group_objects())
        group = bpy.context.active_object
        self.assertEqual(group.name, "group1")
        self.assertEqual(group.type, "EMPTY")
        self.assertEqual({self.a.parent, self.b.parent}, {group})
        bpy.context.view_layer.update()
        for o in (self.a, self.b):
            self.assertTrue(_close(o.matrix_world, before[o.name]), o.name)
        self.assertAlmostEqual(group.matrix_world.translation.x, 0.0, places=4)
        self.assertGreater(group.matrix_world.translation.z, 1.0)
        self.assertEqual([o for o in bpy.context.selected_objects], [group])

    def test_group_nests_under_common_parent_and_names_increment(self):
        bpy.ops.landfall_studio.group_objects()
        outer = bpy.context.active_object
        self.a.select_set(True)
        outer.select_set(False)
        bpy.context.view_layer.objects.active = self.a
        bpy.ops.landfall_studio.group_objects()
        inner = bpy.context.active_object
        self.assertEqual(inner.name, "group2")
        self.assertIs(inner.parent, outer)
        self.assertIs(self.a.parent, inner)

    def test_ungroup_restores_children_in_place(self):
        before = {o.name: o.matrix_world.copy() for o in (self.a, self.b)}
        bpy.ops.landfall_studio.group_objects()
        group = bpy.context.active_object
        group.location.x += 3
        bpy.context.view_layer.update()
        moved = {o.name: o.matrix_world.copy() for o in (self.a, self.b)}
        self.assertFalse(_close(moved[self.a.name], before[self.a.name]))
        self.assertIn("FINISHED", bpy.ops.landfall_studio.ungroup_objects())
        self.assertIsNone(bpy.data.objects.get("group1"))
        bpy.context.view_layer.update()
        for o in (self.a, self.b):
            self.assertIsNone(o.parent)
            self.assertTrue(_close(o.matrix_world, moved[o.name]), o.name)
            self.assertTrue(o.select_get())

    def test_maya_profile_binds_group_and_convert_keys(self):
        profiles.apply_profile(bpy.context, "MAYA")
        addon = bpy.context.window_manager.keyconfigs.addon
        found = set()
        for km in addon.keymaps:
            for item in km.keymap_items:
                if item.idname == "landfall_studio.group_objects" and item.type == "G" and item.ctrl and not item.shift:
                    found.add("group")
                if item.idname == "landfall_studio.ungroup_objects" and item.type == "G" and item.ctrl and item.shift:
                    found.add("ungroup")
                if item.idname == "landfall_studio.convert_selection" and item.ctrl and item.type in ("F9", "F10", "F11"):
                    found.add(item.type + ":" + item.properties.target)
        self.assertEqual(found, {"group", "ungroup", "F9:VERT", "F10:EDGE", "F11:FACE"})


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestMayaGroupHeadless)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("MAYA_GROUP_HEADLESS_RESULT:" + json.dumps({
        "ok": result.wasSuccessful(), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors)}))
    sys.exit(0 if result.wasSuccessful() else 1)
