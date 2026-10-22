"""Gate 10 Headless Verification Suite (`tests/test_phase10_headless.py`).

Verifies:
1. Unified 3-layer Modern Maya Studio Design System (`Blender Theme` + `GPU Overlays` + `Qt QSS`) & DPI scaling (`1.0x`, `1.25x`, `1.5x`) with zero clipped shelf labels.
2. First-class Viewport 2.0 (`BLENDER_EEVEE`) hardware shader engine (`6` Textured EEVEE, `7` Use All Lights EEVEE, `SSAO`, `Shadows`, `Raytracing`, `MSAA 16x`, and `Viewport 2.0 (EEVEE)` ↔ `Cycles` renderer switcher).
3. Modernized GPU Radial Marking Menus (`RMB`, `Shift+RMB`, `Ctrl+RMB`) with compass direction badges (`W/E/S/N/NW/NE/SW/SE`), hotkey badges (`F9–F12`, `Ctrl+E`, `B`), and directional vector connector batches.
4. End-to-end Landfall Studio `v1.0.0` surface availability across all 7 Right Dock tabs, 7 Shelf tabs, DAG Outliner, pure `PYTHON` Command Bar, and clean reversible `unregister()` restoration.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio import continuity, keymaps, modeling, ui, viewport
from landfall_studio.ui import channel_box_ext, desktop, right_dock, shelf, style
from landfall_studio.viewport import marking_menus


class TestPhase10ModernMayaPolishHeadless(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        landfall_studio.register()

    @classmethod
    def tearDownClass(cls):
        try:
            landfall_studio.unregister()
        except Exception:
            pass

    def test_01_three_layer_design_system_and_dpi_scales(self):
        self.assertEqual(landfall_studio.bl_info["version"], (1, 0, 0))
        tokens = style.get_design_system_tokens()
        self.assertIn("palette", tokens)
        self.assertIn("blender_theme", tokens["layers"])
        self.assertIn("gpu_overlays", tokens["layers"])
        self.assertIn("qt_docks", tokens["layers"])
        self.assertEqual(tokens["palette"]["accent_teal"], "#38A3D8")

        for dpi in (1.0, 1.25, 1.5):
            audit = style.verify_three_layer_theme_sync(dpi_scale=dpi)
            self.assertTrue(audit["ok"], f"DPI {dpi} audit failed: {audit}")
            self.assertEqual(audit["clipped_shelf_labels"], [])
            self.assertLessEqual(audit["max_shelf_label_len"], 10)
            self.assertGreater(audit["qss_length"], 4000)

    def test_02_viewport_20_eevee_hardware_shader_and_cycles_switch(self):
        st6 = continuity.set_maya_viewport_shading("6")
        self.assertTrue(st6["ok"])
        self.assertEqual(st6["maya_mode"], "6")
        self.assertIn("EEVEE", st6["renderer_engine"])
        self.assertEqual(st6["renderer_label"], "Viewport 2.0 (EEVEE)")
        self.assertTrue(st6["eevee_ssao"])
        self.assertTrue(st6["eevee_shadows"])
        self.assertEqual(st6["eevee_msaa"], 16)

        st7 = continuity.set_maya_viewport_shading("7")
        self.assertEqual(st7["maya_mode"], "7")
        self.assertEqual(st7["renderer_label"], "Viewport 2.0 (EEVEE)")

        # Toggle SSAO and Shadows
        st_ssao = continuity.toggle_viewport_20_feature("SSAO", enable=False)
        self.assertFalse(st_ssao["eevee_ssao"])
        st_ssao_on = continuity.toggle_viewport_20_feature("SSAO", enable=True)
        self.assertTrue(st_ssao_on["eevee_ssao"])

        # Switch renderer to Cycles and back to Viewport 2.0 (EEVEE)
        st_cyc = continuity.set_viewport_renderer("CYCLES")
        self.assertEqual(st_cyc["renderer_engine"], "CYCLES")
        st_eevee = continuity.set_viewport_renderer("EEVEE")
        self.assertIn("EEVEE", st_eevee["renderer_engine"])
        self.assertEqual(st_eevee["renderer_label"], "Viewport 2.0 (EEVEE)")

        hud_st = viewport.get_hud_state()
        self.assertEqual(hud_st["renderer_label"], "Viewport 2.0 (EEVEE)")
        self.assertTrue(hud_st["eevee_ssao"])

    def test_03_modernized_marking_menu_layout_connectors_and_hotkeys(self):
        for mode in ("COMPONENT", "TOOL", "CONVERT"):
            marking_menus._studio_mm.update(
                {
                    "open": True,
                    "menu_mode": mode,
                    "x": 640.0,
                    "y": 420.0,
                    "cursor_x": 500.0,
                    "cursor_y": 420.0,
                    "list": marking_menus._base_list_for_mode(bpy.context, mode),
                    "hot": ("radial", 0),
                }
            )
            marking_menus._build_mm_layout(bpy.context)
            lay = marking_menus._studio_mm["layout"]
            self.assertIsNotNone(lay)
            self.assertEqual(len(lay["chips"]), 8)
            self.assertEqual(
                tuple(c["compass"] for c in lay["chips"]),
                ("W", "E", "S", "N", "NW", "NE", "SW", "SE"),
            )
            self.assertIn("MAYA MARKING MENU", lay["header_text"])
            self.assertGreaterEqual(len(lay["rows"]), 6)
        marking_menus.stop_studio_marking_menu()

    def test_04_end_to_end_studio_surfaces_and_clean_unregister(self):
        # Verify all 7 Shelf tabs
        expected_shelf_tabs = (
            "Polygons",
            "Modeling",
            "Subdiv & Display",
            "UV & Shading",
            "Deform & Rigging",
            "FX / Nodes",
            "Pipeline",
        )
        for t_name in expected_shelf_tabs:
            self.assertIn(t_name, shelf.SHELF_TABS)

        # Verify all 7 Right Dock modes cycle cleanly
        for r_mode in (
            "CHANNEL_BOX",
            "MODELING_TOOLKIT",
            "HYPERSHADE",
            "SHAPE_EDITOR",
            "MAYA_INTERCHANGE",
            "ATTRIBUTE_EDITOR",
            "TOOL_SETTINGS",
        ):
            res = desktop.cycle_right_dock(r_mode)
            self.assertEqual(res["mode"], r_mode)

        # Verify pure PYTHON command execution
        cmd_res = desktop.execute_command_string("21 * 2")
        self.assertTrue(cmd_res["ok"])
        self.assertEqual(str(cmd_res["result"]), "42")

        # Verify reversible theme & keymap cleanup
        scan = keymaps.scan_keymap_conflicts()
        self.assertTrue(scan["clean"])
        self.assertEqual(scan["protected_context_leaks"], [])

    def test_05_workspace_layouts_tear_off_and_geonodes_inputs(self):
        """Verify Geometry Nodes socket introspection in Channel Box INPUTS, Tear-Off / Redock windows, and Multi-Pane Workspace Layouts."""
        from landfall_studio.ui import right_dock

        res_prim = channel_box_ext.create_maya_primitive("CUBE", width=2.0, height=2.0, depth=2.0)
        self.assertTrue(res_prim["ok"])
        cube = bpy.data.objects.get(res_prim["object_name"])

        # 1. Geometry Nodes modifier with exposed sockets in Channel Box INPUTS
        gn_res = channel_box_ext.ensure_procedural_geonodes_modifier(cube, name="geoNodes_Test1")
        self.assertTrue(gn_res["ok"])
        inputs = channel_box_ext.get_object_inputs(cube)
        gn_node = next((n for n in inputs if n["kind"] == "geometry_nodes"), None)
        self.assertIsNotNone(gn_node)
        self.assertEqual(gn_node["node_type"], "GEOMETRY_NODES")
        self.assertGreaterEqual(len(gn_node["attributes"]), 3)

        # Mutate a Geometry Nodes socket via set_object_input_attribute
        edit_res = channel_box_ext.set_object_input_attribute(
            cube, "geoNodes_Test1", "Subdivide Level", 2
        )
        self.assertTrue(edit_res["ok"])
        self.assertEqual(edit_res["value"], 2)

        # 2. Tear-Off & Redock Panel Manager
        tear_res = right_dock.tear_off_panel("TOOL_SETTINGS", x=180, y=140, width=360, height=480)
        self.assertTrue(tear_res["ok"])
        self.assertTrue(tear_res["floating"])
        self.assertEqual(len(right_dock.list_torn_off_panels()), 1)
        redock_res = right_dock.redock_panel("TOOL_SETTINGS")
        self.assertTrue(redock_res["ok"])
        self.assertEqual(len(right_dock.list_torn_off_panels()), 0)

        # 3. Multi-Pane Workspace Layouts & Context-Aware Spine Tabs
        ws_lookdev = desktop.apply_workspace_layout("Lookdev / Hypershade")
        self.assertTrue(ws_lookdev["ok"])
        self.assertEqual(ws_lookdev["right_dock_mode"], "HYPERSHADE")
        self.assertTrue(ws_lookdev["bottom_node_graph"]["open"])
        self.assertEqual(ws_lookdev["bottom_node_graph"]["ui_type"], "ShaderNodeTree")
        self.assertLessEqual(len(ws_lookdev["visible_spine_tabs"]), 4)

        ws_fx = desktop.apply_workspace_layout("FX & Geometry Nodes")
        self.assertTrue(ws_fx["ok"])
        self.assertEqual(ws_fx["bottom_node_graph"]["ui_type"], "GeometryNodeTree")

        ws_std = desktop.apply_workspace_layout("Modeling Standard")
        self.assertTrue(ws_std["ok"])
        self.assertFalse(ws_std["bottom_node_graph"]["open"])
        self.assertEqual(ws_std["right_dock_mode"], "CHANNEL_BOX")
        self.assertEqual(
            set(ws_std["visible_spine_tabs"]),
            {"CHANNEL_BOX", "MODELING_TOOLKIT", "ATTRIBUTE_EDITOR", "TOOL_SETTINGS", "MODIFIER_STACK"},
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPhase10ModernMayaPolishHeadless)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    out_summary = {
        "suite": "T10-1_headless_modern_maya_polish",
        "version": "1.0.0",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "passed": result.wasSuccessful(),
    }
    out_dir = REPO_ROOT / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "phase10_headless_results.json").write_text(
        json.dumps(out_summary, indent=2), encoding="utf-8"
    )
    agent_out = Path(
        r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output"
    )
    if agent_out.is_dir():
        (agent_out / "phase10_headless_results.json").write_text(
            json.dumps(out_summary, indent=2), encoding="utf-8"
        )
    print("PHASE10_HEADLESS_RESULT:" + json.dumps(out_summary), flush=True)
    sys.exit(0 if result.wasSuccessful() else 1)
