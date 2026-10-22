"""Bridge failure regressions; ordinary Python, no Blender/Maya process needed."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class FakeObject:
    def __init__(self, name):
        self.name = name
        self.users_scene = ()


class BridgeResultTests(unittest.TestCase):
    def setUp(self):
        test_root = (ROOT.parent / ".test_env" / "handoff_data").resolve()
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="landfall_handoff_", dir=test_root)
        self.assertTrue(Path(self.temp.name).resolve().is_relative_to(test_root))
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / "existing.ma"
        self.old_scene = b'// Existing artist scene\ncreateNode transform -n "Original";\n'
        self.destination.write_bytes(self.old_scene)
        self.bridge = types.SimpleNamespace(
            maya_path="test-maya.exe",
            save_as=mock.Mock(return_value=None),
            send=mock.Mock(return_value=None),
        )
        self.bridge_class = mock.Mock(return_value=self.bridge)
        self.preflight = types.ModuleType("_landfall_handoff_test.preflight_report")
        self.preflight.get_maya_runtime_status = mock.Mock(return_value={
            "available": True, "maya_exe": "test-maya.exe", "mayapy_exe": "test-mayapy.exe",
        })
        self.preflight.capture_blender_scene_signature = mock.Mock(return_value={"object_count": 1})
        self.preflight.preflight_maya_scene = mock.Mock(return_value={
            "ok": True, "status": "READY", "summary": {"transforms": 1, "meshes": 0},
            "source_path": str(self.destination),
        })
        self.preflight.build_interchange_report = mock.Mock(side_effect=lambda **kwargs: {
            "ok": not bool(kwargs.get("error")),
            "status": "FAIL" if kwargs.get("error") else "PASS",
            "error": kwargs.get("error"),
        })
        package = types.ModuleType("_landfall_handoff_test")
        package.__path__ = []
        fake_bpy = types.ModuleType("bpy")
        obj = FakeObject("ArtistMesh")
        self.original = obj
        self.other_scene_object = FakeObject("OtherSceneMesh")
        self.objects = [obj, self.other_scene_object]
        self.remove_object = mock.Mock(side_effect=lambda target, **kwargs: self.objects.remove(target))
        fake_bpy.context = types.SimpleNamespace(
            selected_objects=[obj], scene=types.SimpleNamespace(objects=[obj]),
        )
        obj.users_scene = (fake_bpy.context.scene,)
        fake_bpy.data = types.SimpleNamespace(objects=types.SimpleNamespace(remove=self.remove_object))
        self.fake_bpy = fake_bpy
        bridge_module = types.ModuleType("blendertk.env_utils.maya_bridge._maya_bridge")
        bridge_module.MayaBridge = self.bridge_class
        importer_module = types.ModuleType("blendertk.env_utils.maya_bridge._scene_import")
        self.importer = types.SimpleNamespace(import_scene=mock.Mock(return_value=[]))
        importer_module.MayaSceneImport = mock.Mock(return_value=self.importer)
        modules = {
            "_landfall_handoff_test": package,
            "_landfall_handoff_test.preflight_report": self.preflight,
            "bpy": fake_bpy,
            "blendertk": types.ModuleType("blendertk"),
            "blendertk.env_utils": types.ModuleType("blendertk.env_utils"),
            "blendertk.env_utils.maya_bridge": types.ModuleType("blendertk.env_utils.maya_bridge"),
            bridge_module.__name__: bridge_module,
            importer_module.__name__: importer_module,
        }
        self.module_patch = mock.patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        spec = importlib.util.spec_from_file_location(
            "_landfall_handoff_test.maya_bridge", ROOT / "landfall_studio/interchange/maya_bridge.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_failed_save_cannot_reuse_existing_scene_as_success(self):
        result = self.module.save_as_maya_scene(str(self.destination))
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("did not complete", result["error"])
        self.assertEqual(self.destination.read_bytes(), self.old_scene)
        self.preflight.preflight_maya_scene.assert_not_called()

    def test_explicit_failure_cannot_reuse_existing_scene(self):
        for response in ({}, {"ok": False}, {"success": False}, {"status": "CANCELLED"}, {"error": "Conversion failed"}):
            with self.subTest(response=response):
                self.bridge.save_as.return_value = response
                result = self.module.save_as_maya_scene(str(self.destination))
                self.assertFalse(result["ok"])
                self.assertEqual(self.destination.read_bytes(), self.old_scene)
        self.preflight.preflight_maya_scene.assert_not_called()

    def test_save_exception_reports_failure_and_preserves_existing_scene(self):
        self.bridge.save_as.side_effect = RuntimeError("conversion unavailable")
        result = self.module.save_as_maya_scene(str(self.destination))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "conversion unavailable")
        self.assertEqual(self.destination.read_bytes(), self.old_scene)

    def test_successful_save_uses_upstream_output_path(self):
        def save(path, **_kwargs):
            Path(path).write_text('createNode transform -n "NewExport";\n', encoding="utf-8")
            # Upstream judges the produced artifact and can retain a nonzero
            # diagnostic child exit code after a successful artifact write.
            return {"output": path, "returncode": -1073741819, "mode": "save_as"}
        self.bridge.save_as.side_effect = save
        result = self.module.save_as_maya_scene(str(self.destination))
        self.assertTrue(result["ok"])
        self.assertEqual(result["written_path"], str(self.destination))
        self.preflight.preflight_maya_scene.assert_called_once_with(str(self.destination))

    def test_success_result_still_requires_new_destination_artifact(self):
        target = self.destination.with_name("missing.ma")
        self.bridge.save_as.return_value = {"output": str(target), "mode": "save_as"}
        result = self.module.save_as_maya_scene(str(target))
        self.assertFalse(result["ok"])
        self.assertFalse(target.exists())

    def test_save_result_for_another_path_is_not_accepted(self):
        self.bridge.save_as.return_value = {"output": str(self.destination.with_name("different.ma"))}
        result = self.module.save_as_maya_scene(str(self.destination))
        self.assertFalse(result["ok"])
        self.assertIn("unexpected output path", result["error"])
        self.preflight.preflight_maya_scene.assert_not_called()

    def test_save_result_without_output_cannot_claim_existing_destination(self):
        self.bridge.save_as.return_value = {"mode": "save_as"}
        result = self.module.save_as_maya_scene(str(self.destination))
        self.assertFalse(result["ok"])
        self.assertIn("output artifact", result["error"])
        self.assertEqual(self.destination.read_bytes(), self.old_scene)
        self.preflight.preflight_maya_scene.assert_not_called()

    def test_original_import_source_is_protected_before_bridge_call(self):
        result = self.module.save_as_maya_scene(
            str(self.destination), protected_source_path=str(self.destination),
        )
        self.assertFalse(result["ok"])
        self.assertIn("Refusing to overwrite", result["error"])
        self.bridge.save_as.assert_not_called()
        self.assertEqual(self.destination.read_bytes(), self.old_scene)

    def test_failed_send_is_not_reported_as_sent(self):
        for response in (None, {}, {"ok": False}, {"error": "Export failed"}, {"status": "BLOCKED"}):
            with self.subTest(response=response):
                self.bridge.send.return_value = response
                result = self.module.send_to_maya()
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "FAIL")
                self.assertTrue(result["error"])

    def test_send_exception_is_a_reviewable_error(self):
        self.bridge.send.side_effect = RuntimeError("launch failed")
        result = self.module.send_to_maya()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["error"], "launch failed")

    def test_successful_send_retains_successful_bridge_contract(self):
        self.bridge.send.return_value = {"script": "staged/import.py", "payload": "staged/asset.fbx"}
        result = self.module.send_to_maya()
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "SENT")
        self.assertEqual(result["object_count"], 1)

    def test_failed_import_preserves_original_scene_and_source(self):
        self.importer.import_scene.side_effect = RuntimeError("mayapy conversion failed")
        result = self.module.import_maya_scene(str(self.destination), clear_existing=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "mayapy conversion failed")
        self.remove_object.assert_not_called()
        self.assertIn(self.original, self.objects)
        self.assertEqual(self.destination.read_bytes(), self.old_scene)
        self.assertIsNone(self.module._last_imported_source_path)
        self.preflight.capture_blender_scene_signature.assert_called_once_with([])

    def test_incomplete_import_does_not_clear_existing_scene(self):
        for response in (None, []):
            with self.subTest(response=response):
                self.importer.import_scene.return_value = response
                result = self.module.import_maya_scene(str(self.destination), clear_existing=True)
                self.assertFalse(result["ok"])
                self.assertIn(self.original, self.objects)
        self.remove_object.assert_not_called()

    def test_completed_import_clears_only_captured_original_scene_objects(self):
        imported = FakeObject(self.original.name)
        created_during_import = FakeObject("CreatedDuringImport")
        def import_scene(*_args, **_kwargs):
            self.objects.extend([imported, created_during_import])
            self.fake_bpy.context.scene.objects.extend([imported, created_during_import])
            return [imported]
        self.importer.import_scene.side_effect = import_scene
        result = self.module.import_maya_scene(str(self.destination), clear_existing=True)
        self.assertTrue(result["ok"])
        self.remove_object.assert_called_once_with(self.original, do_unlink=True)
        self.assertNotIn(self.original, self.objects)
        self.assertIn(imported, self.objects)
        self.assertIn(created_during_import, self.objects)
        self.assertIn(self.other_scene_object, self.objects)
        self.assertEqual(self.destination.read_bytes(), self.old_scene)
        self.assertTrue(self.importer.import_scene.call_args.kwargs["scene_settings"])

    def test_additive_import_keeps_original_scene(self):
        self.importer.import_scene.return_value = [FakeObject("ImportedMesh")]
        result = self.module.import_maya_scene(str(self.destination))
        self.assertTrue(result["ok"])
        self.remove_object.assert_not_called()
        self.assertIn(self.original, self.objects)

    def test_clear_existing_refuses_objects_shared_with_another_scene(self):
        other_scene = types.SimpleNamespace(name="OtherScene")
        self.original.users_scene = (self.fake_bpy.context.scene, other_scene)
        result = self.module.import_maya_scene(str(self.destination), clear_existing=True)
        self.assertFalse(result["ok"])
        self.assertIn("also belong to another scene", result["error"])
        self.assertIn(self.original.name, result["error"])
        self.assertEqual(result["imported_objects"], [])
        self.importer.import_scene.assert_not_called()
        self.remove_object.assert_not_called()
        self.assertIn(self.original, self.objects)
        self.assertIn(self.other_scene_object, self.objects)
        self.assertEqual(self.destination.read_bytes(), self.old_scene)
        self.assertIsNone(self.module._last_imported_source_path)

    def test_shared_original_does_not_block_additive_import(self):
        self.original.users_scene = (self.fake_bpy.context.scene, types.SimpleNamespace(name="OtherScene"))
        self.importer.import_scene.return_value = [FakeObject("ImportedMesh")]
        result = self.module.import_maya_scene(str(self.destination))
        self.assertTrue(result["ok"])
        self.importer.import_scene.assert_called_once()
        self.remove_object.assert_not_called()

    def test_valid_empty_source_can_replace_scene_after_completed_import(self):
        self.preflight.preflight_maya_scene.return_value["summary"] = {"transforms": 0, "meshes": 0}
        result = self.module.import_maya_scene(str(self.destination), clear_existing=True)
        self.assertTrue(result["ok"])
        self.remove_object.assert_called_once_with(self.original, do_unlink=True)
        self.preflight.capture_blender_scene_signature.assert_called_once_with([])


if __name__ == "__main__":
    unittest.main()
