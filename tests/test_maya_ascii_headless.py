"""Native Maya ASCII interchange: Maya-written meshes in, Maya-readable meshes out."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio.interchange import maya_ascii

# The layout Maya writes for a history-free polyCube (unit cube, 1 cm up).
POLY_CUBE = '''//Maya ASCII 2024 scene
//Name: cube.ma
requires maya "2024";
currentUnit -l centimeter -a degree -t film;
fileInfo "application" "maya";
createNode transform -n "pCube1";
	rename -uid "6C1A0F00-4D0B-7A5E-3C2D-0A9B8C7D6E5F";
	setAttr ".t" -type "double3" 0 1 0 ;
createNode mesh -n "pCubeShape1" -p "pCube1";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr -s 14 ".uvst[0].uvsp[0:13]" -type "float2" 0.375 0 0.625 0 0.375 0.25 0.625 0.25
		 0.375 0.5 0.625 0.5 0.375 0.75 0.625 0.75 0.375 1 0.625 1 0.875 0 0.875 0.25 0.125 0 0.125 0.25;
	setAttr ".cuvs" -type "string" "map1";
	setAttr -s 8 ".vt[0:7]"  -0.5 -0.5 0.5 0.5 -0.5 0.5 -0.5 0.5 0.5 0.5 0.5 0.5
		 -0.5 0.5 -0.5 0.5 0.5 -0.5 -0.5 -0.5 -0.5 0.5 -0.5 -0.5;
	setAttr -s 12 ".ed[0:11]"  0 1 0 2 3 0 4 5 0 6 7 0 0 2 0 1 3 0 2 4 0 3 5 0 4 6 0
		 5 7 0 6 0 0 7 1 0;
	setAttr -s 6 -ch 24 ".fc[0:5]" -type "polyFaces"
		f 4 0 5 -2 -5
		mu 0 4 0 1 3 2
		f 4 1 7 -3 -7
		mu 0 4 2 3 5 4
		f 4 2 9 -4 -9
		mu 0 4 4 5 7 6
		f 4 3 11 -1 -11
		mu 0 4 6 7 9 8
		f 4 -12 -10 -8 -6
		mu 0 4 1 10 11 3
		f 4 10 4 6 8
		mu 0 4 12 0 2 13;
	setAttr ".cd" -type "dataPolyComponent" Index_Data Edge 0 ;
// End of cube.ma
'''

HISTORY = '''//Maya ASCII 2024 scene
requires maya "2024";
currentUnit -l centimeter -a degree -t film;
createNode transform -n "pSphere1";
createNode mesh -n "pSphereShape1" -p "pSphere1";
	setAttr -k off ".v";
createNode polySphere -n "polySphere1";
connectAttr "polySphere1.out" "pSphereShape1.i";
'''

HIERARCHY = '''//Maya ASCII 2024 scene
requires maya "2024";
currentUnit -l meter -a degree -t film;
createNode transform -n "grp";
	setAttr ".t" -type "double3" 1 0 0 ;
	setAttr ".r" -type "double3" 0 90 0 ;
createNode transform -n "tri" -p "grp";
	setAttr ".t" -type "double3" 0 2 0 ;
	setAttr ".s" -type "double3" 2 2 2 ;
	setAttr ".ro" 5;
createNode mesh -n "triShape" -p "|grp|tri";
	setAttr -s 3 ".vt[0:1]" 0 0 0 1 0 0;
	setAttr ".vt[2]" 0 0 -1;
	setAttr -s 3 ".pt[2:2]" -type "float3" 0 0 -1;
	setAttr -s 3 ".ed[0:2]" 0 1 1 1 2 1 2 0 1;
	setAttr -s 1 -ch 3 ".fc[0]" -type "polyFaces" f 3 0 1 2;
createNode transform -n "hidden";
	setAttr ".v" no;
'''


def _write(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".ma", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()
    return handle.name


def _world_verts(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


class TestMayaAsciiHeadless(unittest.TestCase):
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

    def test_maya_poly_cube_imports_with_outward_faces_uvs_and_hard_edges(self):
        res = maya_ascii.import_maya_ascii(_write(POLY_CUBE))
        self.assertTrue(res["ok"], res)
        obj = bpy.data.objects["pCube1"]
        me = obj.data
        self.assertEqual((len(me.vertices), len(me.polygons)), (8, 6))
        self.assertTrue(all(len(p.vertices) == 4 for p in me.polygons))
        # 1 cm along Maya Y is 0.01 m along Blender Z.
        self.assertAlmostEqual(obj.location.z, 0.01, places=6)
        self.assertAlmostEqual(obj.location.y, 0.0, places=6)
        for poly in me.polygons:
            self.assertGreater(poly.normal.dot(poly.center), 0.0)
        self.assertAlmostEqual(max(v.co.z for v in me.vertices), 0.005, places=6)
        self.assertEqual(me.uv_layers.active.name, "map1")
        uvs = {tuple(round(c, 3) for c in l.uv) for l in me.uv_layers.active.data}
        self.assertIn((0.375, 0.0), uvs)
        self.assertIn((0.875, 0.25), uvs)
        sharp = me.attributes["sharp_edge"]
        self.assertTrue(all(sharp.data[i].value for i in range(len(me.edges))))

    def test_history_only_mesh_is_reported_not_imported_empty(self):
        res = maya_ascii.import_maya_ascii(_write(HISTORY))
        self.assertTrue(res["ok"])
        self.assertEqual(res["mesh_count"], 0)
        self.assertEqual(res["skipped"][0]["node"], "pSphereShape1")
        self.assertIn("construction history", res["skipped"][0]["reason"])

    def test_hierarchy_chunks_tweaks_rotate_order_and_visibility(self):
        res = maya_ascii.import_maya_ascii(_write(HIERARCHY))
        self.assertTrue(res["ok"], res)
        grp, tri, hidden = (bpy.data.objects[n] for n in ("grp", "tri", "hidden"))
        self.assertIs(tri.parent, grp)
        self.assertTrue(hidden.hide_get())
        bpy.context.view_layer.update()
        world = sorted(tuple(round(c, 4) for c in p) for p in _world_verts(tri))
        # Maya: grp at x=1 rotated 90 deg about Y; tri 2 up and scaled 2.
        # Local vertex (0,0,-2) -> scaled (0,0,-4) -> rotY90 (-4,0,0) -> +grp -> (-3,2,0).
        expected = sorted(tuple(round(c, 4) for c in maya_ascii._maya_to_blender_point(p, 1.0))
                          for p in ((1, 2, 0), (1, 2, -2), (-3, 2, 0)))
        self.assertEqual(world, expected)

    def test_round_trip_preserves_world_shape_hierarchy_and_uvs(self):
        bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3), rotation=(0.3, 0.2, 0.1))
        cube = bpy.context.active_object
        cube.name = "Hero Body"
        cube.scale = (1, 2, 0.5)
        # Smooth-shaded, so only the one marked edge is hard (flat faces export all-hard).
        bpy.ops.object.shade_smooth()
        bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(cube.data)
        bm.edges.ensure_lookup_table()
        bm.edges[0].smooth = False
        bmesh.update_edit_mesh(cube.data)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.mesh.primitive_ico_sphere_add(radius=0.5, location=(4, 0, 0))
        ball = bpy.context.active_object
        ball.name = "Ball"
        ball.parent = cube
        ball.matrix_parent_inverse = cube.matrix_world.inverted()
        bpy.context.view_layer.update()
        before = {o.name: sorted(tuple(round(c, 4) for c in p) for p in _world_verts(o)) for o in (cube, ball)}
        uv_before = sorted(tuple(round(c, 4) for c in l.uv) for l in cube.data.uv_layers.active.data)
        path = tempfile.NamedTemporaryFile(suffix=".ma", delete=False).name
        out = maya_ascii.export_maya_ascii(path, [cube, ball])
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["meshes"], 2)
        text = Path(path).read_text(encoding="utf-8")
        self.assertIn('createNode transform -n "Hero_Body";', text)
        self.assertIn('createNode transform -n "Ball" -p "Hero_Body";', text)
        self.assertIn("currentUnit -l centimeter", text)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        res = maya_ascii.import_maya_ascii(path)
        self.assertTrue(res["ok"], res)
        bpy.context.view_layer.update()
        cube2, ball2 = bpy.data.objects["Hero_Body"], bpy.data.objects["Ball"]
        self.assertIs(ball2.parent, cube2)
        self.assertEqual(sorted(tuple(round(c, 4) for c in p) for p in _world_verts(cube2)), before["Hero Body"])
        self.assertEqual(sorted(tuple(round(c, 4) for c in p) for p in _world_verts(ball2)), before["Ball"])
        uv_after = sorted(tuple(round(c, 4) for c in l.uv) for l in cube2.data.uv_layers.active.data)
        self.assertEqual(uv_after, uv_before)
        self.assertEqual(sum(cube2.data.attributes["sharp_edge"].data[i].value for i in range(12)), 1)
        for poly in cube2.data.polygons:
            self.assertGreater(poly.normal.dot(poly.center), 0.0)

    def test_flat_shading_exports_hard_edges(self):
        bpy.ops.mesh.primitive_cube_add()
        path = tempfile.NamedTemporaryFile(suffix=".ma", delete=False).name
        maya_ascii.export_maya_ascii(path, [bpy.context.active_object])
        edge_line = next(l for l in Path(path).read_text(encoding="utf-8").splitlines() if '".ed[' in l)
        flags = edge_line.split('"', 2)[2].strip().rstrip(";").split()[2::3]
        self.assertEqual(set(flags), {"0"})

    def test_operators_import_and_export(self):
        src = _write(POLY_CUBE)
        self.assertIn("FINISHED", bpy.ops.landfall_studio.import_maya_ascii(filepath=src))
        self.assertIn("pCube1", bpy.data.objects)
        out = tempfile.NamedTemporaryFile(suffix=".ma", delete=False).name
        self.assertIn("FINISHED", bpy.ops.landfall_studio.export_maya_ascii(filepath=out))
        self.assertIn('createNode mesh -n "pCube1Shape" -p "pCube1";', Path(out).read_text(encoding="utf-8"))

    def test_bridge_uses_native_route_only_without_maya_runtime(self):
        from unittest import mock
        from landfall_studio.interchange import maya_bridge, preflight_report
        missing = {"available": False, "error": "Local mayapy executable not found; Maya interchange is BLOCKED."}
        with mock.patch.object(preflight_report, "get_maya_runtime_status", return_value=missing):
            report = maya_bridge.import_maya_scene(_write(POLY_CUBE))
            self.assertEqual(report["route"], "native_ascii")
            self.assertIn("pCube1", report["imported_objects"])
            self.assertIn("pCube1", bpy.data.objects)
            dst = Path(tempfile.mkdtemp()) / "saved.ma"
            saved = maya_bridge.save_as_maya_scene(str(dst))
            self.assertEqual(saved["route"], "native_ascii")
            self.assertTrue(dst.is_file())

    def test_rejects_binary_and_non_maya_files(self):
        self.assertFalse(maya_ascii.import_maya_ascii("scene.mb")["ok"])
        self.assertFalse(maya_ascii.import_maya_ascii(_write("hello"))["ok"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestMayaAsciiHeadless)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("MAYA_ASCII_HEADLESS_RESULT:" + json.dumps({
        "ok": result.wasSuccessful(), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors)}))
    sys.exit(0 if result.wasSuccessful() else 1)
