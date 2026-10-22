"""Repeat-command and Make Live regressions; native cases also run in Blender.

Standalone Python exercises result handling and invalid-target safety. Blender's
Python additionally exercises real mesh creation, welding, retopology and BVHs.
"""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_source(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCommandResults(unittest.TestCase):
    def setUp(self):
        self.registry = load_source("ux_registry", "landfall_studio/commands/registry.py")

    def test_failed_execution_does_not_replace_repeat_history(self):
        self.registry.record_command("valid", callable_fn=lambda: {"ok": True})
        for failed in ({"CANCELLED"}, {"ok": False, "error": "No selection"}, False):
            self.registry.register_command("failed", lambda value=failed: value)
            self.registry.execute_command("failed")
            self.assertEqual(self.registry.get_last_command()["id"], "valid")

    def test_cancelled_repeat_is_not_reported_as_success(self):
        for result in ({"CANCELLED"}, {"ok": False, "error": "No selection"}, False):
            self.registry.record_command("failed", callable_fn=lambda value=result: value)
            before = self.registry.get_last_command()["timestamp"]
            repeated = self.registry.repeat_last_command()
            self.assertFalse(repeated["ok"])
            self.assertIn("error", repeated)
            self.assertEqual(self.registry.get_last_command()["timestamp"], before)

    def test_repeat_exception_returns_actionable_failure(self):
        def failing(**kwargs):
            raise RuntimeError("Target object was removed")
        self.registry.record_command("missing", callable_fn=failing)
        repeated = self.registry.repeat_last_command()
        self.assertFalse(repeated["ok"])
        self.assertEqual(repeated["error"], "Target object was removed")

    def test_repeat_preserves_exact_arguments(self):
        observed = []
        self.registry.record_command("primitive", kwargs={"primitive_type": "CUBE", "width": 7.25},
            callable_fn=lambda **values: observed.append(values) or {"ok": True})
        self.assertTrue(self.registry.repeat_last_command()["ok"])
        self.assertEqual(observed, [{"primitive_type": "CUBE", "width": 7.25}])


class FakeObject(dict):
    def __init__(self, name, object_type):
        super().__init__()
        self.name, self.type = name, object_type
        self.data = types.SimpleNamespace()
        self.hide_select = self.show_wire = self.show_all_edges = False
        self.color = (1, 1, 1, 1)


class TestInvalidLiveTarget(unittest.TestCase):
    def test_camera_is_not_locked_and_existing_live_target_is_preserved(self):
        live = load_source("ux_live", "landfall_studio/modeling/live_surface.py")
        camera, mesh = FakeObject("Camera", "CAMERA"), FakeObject("Live", "MESH")
        scene = {"landfall_live_surface": mesh.name}
        fake_bpy = types.SimpleNamespace(
            context=types.SimpleNamespace(scene=scene,
                view_layer=types.SimpleNamespace(objects=types.SimpleNamespace(active=camera))),
            data=types.SimpleNamespace(objects={camera.name: camera, mesh.name: mesh}))
        with patch.dict(sys.modules, {"bpy": fake_bpy}):
            result = live.set_live_surface(toggle=True)
        self.assertFalse(result["ok"])
        self.assertFalse(camera.hide_select)
        self.assertNotIn("_landfall_live_prev_state", camera)
        self.assertEqual(scene["landfall_live_surface"], mesh.name)


try:
    import bpy
except ImportError:
    bpy = None


@unittest.skipUnless(bpy is not None, "Real mesh regressions require Blender Python")
class TestNativeCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import landfall_studio
        landfall_studio.register()

    @classmethod
    def tearDownClass(cls):
        import landfall_studio
        landfall_studio.unregister()

    def setUp(self):
        from landfall_studio import commands, modeling
        modeling.clear_modeling_state()
        commands.clear_state()
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

    def test_primitive_shelf_repeat_retains_options(self):
        from landfall_studio import commands
        from landfall_studio.ui import shelf, tool_settings
        previous = dict(tool_settings._option_box_state)
        try:
            tool_settings._option_box_state.update(prim_width=7.25, prim_height=3.0, prim_depth=1.5)
            self.assertTrue(shelf.execute_shelf_item("poly_cube")["ok"])
            dimensions = tuple(bpy.context.active_object.dimensions)
            self.assertTrue(commands.repeat_last_command()["ok"])
            self.assertEqual(len([o for o in bpy.context.scene.objects if o.type == "MESH"]), 2)
            self.assertEqual(tuple(bpy.context.active_object.dimensions), dimensions)
        finally:
            tool_settings._option_box_state.clear()
            tool_settings._option_box_state.update(previous)

    def test_target_weld_repeat_accepts_recorded_kwargs(self):
        from landfall_studio import commands, modeling
        bpy.ops.mesh.primitive_plane_add()
        result = modeling.weld_vertices_target_weld(0, 1, merge_to_center=False)
        self.assertTrue(result["ok"])
        self.assertTrue(commands.repeat_last_command()["ok"])

    def test_quad_fill_repeat_accepts_recorded_kwargs(self):
        from landfall_studio import commands, modeling
        modeling.clear_quad_draw_dots()
        for point in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)):
            modeling.plot_quad_draw_dot(point, project_to_live=False)
        self.assertTrue(modeling.fill_quad_from_dots()["ok"])
        self.assertTrue(commands.repeat_last_command()["ok"])
        self.assertEqual(len(bpy.context.active_object.data.polygons), 1)

    def test_same_topology_deformation_invalidates_live_bvh(self):
        from landfall_studio.modeling import live_surface
        bpy.ops.mesh.primitive_plane_add(size=4)
        obj = bpy.context.active_object
        self.assertTrue(live_surface.set_live_surface(obj)["ok"])
        before = live_surface.project_point_to_live_surface((0, 0, 3))
        for vertex in obj.data.vertices:
            vertex.co.z = 2
        obj.data.update()
        graph = types.SimpleNamespace(updates=[types.SimpleNamespace(id=obj.data, is_updated_geometry=True)])
        live_surface.invalidate_live_surface_cache(graph)
        after = live_surface.project_point_to_live_surface((0, 0, 3))
        self.assertAlmostEqual(before["location"][2], 0)
        self.assertAlmostEqual(after["location"][2], 2)

    def test_border_shelf_changes_actual_overlay_flag(self):
        from landfall_studio.ui import shelf
        initial = bool(bpy.context.scene.landfall_border_show)
        self.assertTrue(shelf.execute_shelf_item("border_edges")["ok"])
        self.assertEqual(bool(bpy.context.scene.landfall_border_show), not initial)

    def test_caddy_requires_selected_components_without_mutating_mesh(self):
        from landfall_studio import modeling
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.active_object
        for face in obj.data.polygons:
            face.select = False
        for edge in obj.data.edges:
            edge.select = False
        for vertex in obj.data.vertices:
            vertex.select = False
        original = tuple(tuple(v.co) for v in obj.data.vertices)
        for tool in ("EXTRUDE", "BEVEL", "BRIDGE", "CONNECT"):
            result = modeling.invoke_modeling_caddy(tool)
            self.assertFalse(result["ok"], tool)
            self.assertEqual(tuple(tuple(v.co) for v in obj.data.vertices), original)
            self.assertEqual(len(obj.data.polygons), 6)

    def test_caddy_blocks_shape_keys_and_shared_data(self):
        from landfall_studio import modeling
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.active_object
        obj.shape_key_add(name="Basis")
        self.assertFalse(modeling.invoke_modeling_caddy("BEVEL")["ok"])
        self.assertEqual(len(obj.data.vertices), 8)
        obj.shape_key_clear()
        instance = obj.copy()
        bpy.context.collection.objects.link(instance)
        self.assertFalse(modeling.invoke_modeling_caddy("BEVEL")["ok"])
        self.assertEqual(len(obj.data.vertices), 8)
        self.assertIs(obj.data, instance.data)

    def test_caddy_cancel_and_parameter_preserve_subsequent_mesh_edits(self):
        from landfall_studio import modeling
        from landfall_studio.modeling import caddy
        for action in (lambda: caddy.cancel_caddy(), lambda: modeling.set_caddy_parameter("width", .2)):
            bpy.ops.mesh.primitive_cube_add()
            obj = bpy.context.active_object
            self.assertTrue(modeling.invoke_modeling_caddy("BEVEL")["ok"])
            obj.data.vertices[0].co.z += 3.25
            obj.data.update()
            changed = tuple(tuple(v.co) for v in obj.data.vertices)
            result = action()
            self.assertFalse(result["ok"])
            self.assertTrue(result.get("guarded"))
            self.assertFalse(modeling.get_active_caddy_state()["open"])
            self.assertEqual(tuple(tuple(v.co) for v in obj.data.vertices), changed)

    def test_caddy_cancel_preserves_subsequent_uv_edits(self):
        from landfall_studio import modeling
        from landfall_studio.modeling import caddy
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.active_object
        self.assertTrue(modeling.invoke_modeling_caddy("BEVEL")["ok"])
        obj.data.uv_layers.active.data[0].uv = (.123, .456)
        obj.data.update()
        changed = tuple(obj.data.uv_layers.active.data[0].uv)
        self.assertFalse(caddy.cancel_caddy()["ok"])
        self.assertEqual(tuple(obj.data.uv_layers.active.data[0].uv), changed)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("FULL_UX_COMMANDS_RESULT:" + json.dumps({"ok": result.wasSuccessful(),
        "tests_run": result.testsRun, "skipped": len(result.skipped),
        "failures": len(result.failures), "errors": len(result.errors)}))
    sys.exit(0 if result.wasSuccessful() else 1)
