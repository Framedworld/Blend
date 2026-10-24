"""Maya modeling menu parity: the Maya-named entries perform real edits.

Each entry is read from the actual menu data (operator path and arguments),
then executed on a fresh mesh with the selection Maya's command expects.
View-dependent projections (Planar, Cylindrical, Spherical) and interactive
tools need a 3D viewport and are covered by the GUI availability suite.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import bmesh
import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio.ui import menus


def _entry(menu_title, label):
    for title, entries in menus.MENU_SETS["Modeling"]:
        if title != menu_title:
            continue
        for e in entries:
            if e[0] == "OP" and e[1] == label:
                return e[2], dict(e[4])
    raise KeyError(menu_title + " / " + label)


def _run(menu_title, label):
    path, props = _entry(menu_title, label)
    module, name = path.split(".")
    return getattr(getattr(bpy.ops, module), name)("EXEC_DEFAULT", **props)


def _counts(obj):
    obj.update_from_editmode()
    me = obj.data
    return len(me.vertices), len(me.edges), len(me.polygons)


class TestMayaMenusHeadless(unittest.TestCase):
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
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        self.obj = bpy.context.view_layer.objects.active
        bpy.ops.object.mode_set(mode="EDIT")

    def select(self, mode, picker):
        bpy.ops.mesh.select_mode(type=mode)
        bpy.ops.mesh.select_all(action="DESELECT")
        bm = bmesh.from_edit_mesh(self.obj.data)
        seq = {"VERT": bm.verts, "EDGE": bm.edges, "FACE": bm.faces}[mode]
        seq.ensure_lookup_table()
        for element in picker(list(seq)):
            element.select_set(True)
        bm.select_flush_mode()
        bmesh.update_edit_mesh(self.obj.data)

    def top_face(self, faces):
        return [max(faces, key=lambda f: f.calc_center_median().z)]

    def test_extract_makes_new_object(self):
        self.select("FACE", self.top_face)
        self.assertIn("FINISHED", _run("Mesh", "Extract"))
        self.assertEqual(len([o for o in bpy.data.objects if o.type == "MESH"]), 2)
        self.assertEqual(_counts(self.obj)[2], 5)

    def test_triangulate_then_quadrangulate(self):
        bpy.ops.mesh.select_all(action="SELECT")
        self.assertIn("FINISHED", _run("Mesh", "Triangulate"))
        self.assertEqual(_counts(self.obj)[2], 12)
        bpy.ops.mesh.select_all(action="SELECT")
        self.assertIn("FINISHED", _run("Mesh", "Quadrangulate"))
        self.assertEqual(_counts(self.obj)[2], 6)

    def test_fill_hole(self):
        self.select("FACE", self.top_face)
        bpy.ops.mesh.delete(type="FACE")
        bpy.ops.mesh.select_all(action="SELECT")
        self.assertIn("FINISHED", _run("Mesh", "Fill Hole"))
        self.assertEqual(_counts(self.obj)[2], 6)

    def test_add_divisions(self):
        self.select("FACE", self.top_face)
        self.assertIn("FINISHED", _run("Edit Mesh", "Add Divisions"))
        self.assertEqual(_counts(self.obj)[2], 9)

    def test_collapse_edge(self):
        self.select("EDGE", lambda edges: edges[:1])
        self.assertIn("FINISHED", _run("Edit Mesh", "Collapse"))
        self.assertEqual(_counts(self.obj)[0], 7)

    def test_merge_to_center(self):
        self.select("FACE", self.top_face)
        self.assertIn("FINISHED", _run("Edit Mesh", "Merge to Center"))
        self.assertEqual(_counts(self.obj)[0], 5)

    def test_merge_coincident(self):
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.duplicate()
        bpy.ops.mesh.select_all(action="SELECT")
        self.assertIn("FINISHED", _run("Edit Mesh", "Merge"))
        self.assertEqual(_counts(self.obj)[0], 8)

    def test_detach_vertex(self):
        self.select("VERT", lambda verts: verts[:1])
        self.assertIn("FINISHED", _run("Edit Mesh", "Detach"))
        self.assertGreater(_counts(self.obj)[0], 8)

    def test_average_vertices_moves_corner(self):
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.subdivide(number_cuts=2)
        self.select("VERT", lambda verts: [max(verts, key=lambda v: v.co.length)])
        self.obj.update_from_editmode()
        index = next(v.index for v in self.obj.data.vertices if v.select)
        before = self.obj.data.vertices[index].co.length
        self.assertIn("FINISHED", _run("Edit Mesh", "Average Vertices"))
        self.obj.update_from_editmode()
        self.assertLess(self.obj.data.vertices[index].co.length, before - 1e-3)

    def test_poke_face(self):
        self.select("FACE", self.top_face)
        self.assertIn("FINISHED", _run("Edit Mesh", "Poke Face"))
        self.assertEqual(_counts(self.obj)[2], 9)

    def test_spin_edges(self):
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.quads_convert_to_tris()
        self.select("EDGE", lambda edges: [e for e in edges if len(e.link_faces) == 2
                                            and all(len(f.verts) == 3 for f in e.link_faces)
                                            and abs(e.link_faces[0].normal.dot(e.link_faces[1].normal) - 1) < 1e-4][:1])
        before = sorted(tuple(sorted(e.vertices)) for e in self.obj.data.edges)
        self.assertIn("FINISHED", _run("Edit Mesh", "Flip Triangle Edge"))
        self.obj.update_from_editmode()
        self.assertNotEqual(before, sorted(tuple(sorted(e.vertices)) for e in self.obj.data.edges))
        self.assertIn("FINISHED", _run("Edit Mesh", "Spin Edge Backward"))

    def test_append_to_polygon(self):
        self.select("FACE", self.top_face)
        bpy.ops.mesh.delete(type="FACE")
        bm = bmesh.from_edit_mesh(self.obj.data)
        for v in bm.verts:
            v.select_set(v.co.z > 0.5)
        bm.select_flush_mode()
        bmesh.update_edit_mesh(self.obj.data)
        self.assertIn("FINISHED", _run("Mesh Tools", "Append to Polygon"))
        self.assertEqual(_counts(self.obj)[2], 6)

    def test_cut_and_sew_uv_edges(self):
        self.select("EDGE", lambda edges: edges[:2])
        self.assertIn("FINISHED", _run("UV", "Cut UV Edges"))
        self.obj.update_from_editmode()
        self.assertEqual(sum(e.use_seam for e in self.obj.data.edges), 2)
        self.assertIn("FINISHED", _run("UV", "Sew UV Edges"))
        self.obj.update_from_editmode()
        self.assertEqual(sum(e.use_seam for e in self.obj.data.edges), 0)

    def test_unfold_and_layout(self):
        bpy.ops.mesh.select_all(action="SELECT")
        self.assertIn("FINISHED", _run("UV", "Unfold"))
        self.assertIn("FINISHED", _run("UV", "Layout"))
        self.obj.update_from_editmode()
        uv = self.obj.data.uv_layers.active.data
        self.assertTrue(all(-1e-4 <= c <= 1.0001 for loop in uv for c in loop.uv))

    def test_in_window_menu_commands_start_in_the_viewport(self):
        class Region: x, y, width, height = 100, 50, 800, 600
        class Window:
            warped = None
            def cursor_warp(self, x, y): Window.warped = (x, y)
        override = {"window": Window(), "region": Region()}
        self.assertTrue(menus._bring_cursor_to_viewport(override, "ed.undo_history"))
        self.assertEqual(Window.warped, (500, 350))
        Window.warped = None
        for path in ("import_scene.fbx", "wm.obj_export", "landfall.project_open", "landfall_studio.import_maya_ascii",
                     "screen.userpref_show", "render.render"):
            self.assertFalse(menus._bring_cursor_to_viewport(override, path), path)
        self.assertIsNone(Window.warped)
        self.assertFalse(menus._bring_cursor_to_viewport({}, "ed.undo_history"))

    def test_symmetrize_and_retopology_entries_exist(self):
        for title, label in (("Mesh", "Symmetrize"), ("Mesh", "Retopologize (QuadriFlow)"),
                             ("Edit Mesh", "Chamfer Vertex"), ("Mesh Tools", "Crease")):
            path, _ = _entry(title, label)
            module, name = path.split(".")
            self.assertIsNotNone(getattr(getattr(bpy.ops, module), name).get_rna_type())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestMayaMenusHeadless)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("MAYA_MENUS_HEADLESS_RESULT:" + json.dumps({
        "ok": result.wasSuccessful(), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors)}))
    sys.exit(0 if result.wasSuccessful() else 1)
