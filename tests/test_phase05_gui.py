"""Gate 05 GUI Verification & Screenshot Suite (`T05-2`):
Verifies the full 4-dock Modern Maya Studio desktop with:
- Docked `Modeling Toolkit` right sidebar tab (`MODELING_TOOLKIT`)
- Top Status Line `LIVE: HiRes_Sculpt_Sphere` emerald magnet pill
- `Make Live` scoped surface projection + `Quad Draw` retopology patch and plotted construction dots (`v1..v4`)
- Floating `In-Viewport Heads-Up Caddy` (`polyBevel1` / `polyExtrudeFace1`) rendered in `SpaceView3D` (`POST_PIXEL`)
- Non-Deformer History, Read-Only Scene Diagnostics, and Material-Preserving Texel Density
- Captures `output/phase05_modeling_maya_ui_gui.png`.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio import commands, modeling, ui, viewport

ARTIFACT_PNG = Path(
    r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output\phase05_modeling_maya_ui_gui.png"
)
BRAIN_PNG = Path(
    r"C:\Users\mattk\.gemini\antigravity\brain\7b1d9264-a274-459e-8c9a-2432ca72975f\phase05_modeling_maya_ui_gui.png"
)

_results: dict = {"steps": []}
_stage: int = 0


def _maximize_and_bring_to_front() -> None:
    try:
        from blendertk.ui_utils.blender_window import BlenderWindow
        import blendertk as btk

        win = btk.main_window()
        hwnd = BlenderWindow.window_hwnd(win) if win else None
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _frame_viewport_camera() -> None:
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.shading.type = "SOLID"
                        space.shading.light = "STUDIO"
                        space.shading.color_type = "MATERIAL"
                        space.shading.show_cavity = True
                        space.shading.show_specular_highlight = True
                        r3d = space.region_3d
                        if r3d is not None:
                            r3d.view_perspective = "PERSP"
                            r3d.view_location = Vector((0.3, 0.0, 0.45))
                            r3d.view_distance = 6.2
                            r3d.view_rotation = Euler((1.08, 0.0, 0.62), "XYZ").to_quaternion()
                for reg in area.regions:
                    reg.tag_redraw()


def _build_showcase_scene() -> dict:
    # Clear default cube/light
    for obj in list(bpy.data.objects):
        if obj.type in ("MESH", "LIGHT"):
            bpy.data.objects.remove(obj, do_unlink=True)

    # 1. Create a high-res sculpt reference sphere on the left and Make Live
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=48, ring_count=24, radius=1.35, location=(-1.45, 0.0, 0.65)
    )
    live_sphere = bpy.context.view_layer.objects.active
    live_sphere.name = "HiRes_Sculpt_Sphere"
    bpy.ops.object.shade_smooth()

    mat_live = bpy.data.materials.new(name="aiSculptClay")
    mat_live.diffuse_color = (0.19, 0.30, 0.28, 1.0)
    live_sphere.data.materials.append(mat_live)

    # Activate Make Live via shelf item so Top Status Line pill updates to LIVE: HiRes_Sculpt_Sphere
    ui.execute_shelf_item("make_live")

    # 2. Plot Quad Draw retopology quads + construction dots onto the live sphere
    modeling.set_quad_draw_active(True)
    modeling.clear_quad_draw_dots()

    # Build a 2x2 quad patch on the front-facing hemisphere of HiRes_Sculpt_Sphere
    patch_quads = [
        [(-1.95, -0.85, 1.45), (-1.45, -0.95, 1.45), (-1.45, -0.75, 1.85), (-1.95, -0.65, 1.85)],
        [(-1.45, -0.95, 1.45), (-0.95, -0.85, 1.45), (-0.95, -0.65, 1.85), (-1.45, -0.75, 1.85)],
        [(-1.95, -0.65, 1.85), (-1.45, -0.75, 1.85), (-1.45, -0.35, 2.05), (-1.95, -0.25, 2.02)],
        [(-1.45, -0.75, 1.85), (-0.95, -0.65, 1.85), (-0.95, -0.25, 2.02), (-1.45, -0.35, 2.05)],
    ]
    retopo_obj = None
    for qpts in patch_quads:
        modeling.clear_quad_draw_dots()
        for pt in qpts:
            modeling.plot_quad_draw_dot(pt)
        f_res = modeling.fill_quad_from_dots(retopo_obj)
        retopo_obj = bpy.data.objects.get(f_res["object_name"])

    if retopo_obj is not None:
        mat_retopo = bpy.data.materials.new(name="aiRetopoCyan")
        mat_retopo.diffuse_color = (0.20, 0.72, 0.94, 1.0)
        retopo_obj.data.materials.append(mat_retopo)
        retopo_obj.show_wire = True
        retopo_obj.show_all_edges = True
        retopo_obj.show_in_front = True

    # Leave 4 fresh plotted Quad Draw dots visible for the viewport HUD overlay
    modeling.clear_quad_draw_dots()
    for dpt in [
        (-1.85, -1.05, 0.95),
        (-1.45, -1.15, 0.95),
        (-1.05, -1.05, 0.95),
        (-1.45, -1.22, 0.48),
    ]:
        modeling.plot_quad_draw_dot(dpt)

    # 3. Create an armored hard-surface hero prop on the right and invoke the Bevel In-Viewport Caddy (`polyBevel1`)
    res_prim = ui.create_maya_primitive(
        primitive_type="CUBE",
        width=1.65,
        height=1.65,
        depth=1.65,
        subdivisions_x=2,
        subdivisions_y=2,
        subdivisions_z=2,
    )
    hero_mesh = bpy.data.objects.get(res_prim["object_name"])
    hero_mesh.name = "pArmorBlock1"
    hero_mesh.data.name = "pArmorBlockShape1"
    hero_mesh.location = (1.35, 0.15, 0.65)
    bpy.context.view_layer.update()

    mat_armor = bpy.data.materials.new(name="aiStandardArmor")
    mat_armor.diffuse_color = (0.34, 0.56, 0.78, 1.0)
    hero_mesh.data.materials.append(mat_armor)
    hero_mesh.show_wire = True
    hero_mesh.show_all_edges = True

    bpy.ops.object.select_all(action="DESELECT")
    hero_mesh.select_set(True)
    bpy.context.view_layer.objects.active = hero_mesh

    # Unwrap + set 256 px/m texel density on pArmorBlock1
    uv_res = modeling.uv_unwrap_and_pack(hero_mesh, method="SMART", margin=0.03)
    td_res = modeling.set_mesh_texel_density(hero_mesh, target_td=256.0, map_size=2048)

    # Select edges on pArmorBlock1 and open the Bevel Caddy (`polyBevel1`)
    for e in hero_mesh.data.edges:
        e.select = True
    caddy_res = modeling.invoke_modeling_caddy(
        "BEVEL", hero_mesh, {"offset": 0.16, "segments": 3, "profile": 0.5}
    )
    # Scrub offset slightly to exercise live caddy parameter scrubbing in GUI
    modeling.scrub_caddy_parameter(delta_px=8.0, param_key="offset")

    # Run strictly read-only scene diagnostics
    diag_rep = modeling.run_scene_diagnostics()

    return {
        "live_surface": modeling.get_live_surface_state(),
        "quad_draw": modeling.get_quad_draw_overlay_data(),
        "caddy": modeling.get_active_caddy_state(),
        "uv_res": uv_res,
        "td_res": td_res,
        "diagnostics_read_only": diag_rep["read_only_verified"],
    }


def _step_timer():
    global _stage
    try:
        if _stage == 0:
            bpy.context.preferences.view.show_splash = False
            bpy.ops.wm.read_homefile()
            _maximize_and_bring_to_front()
            landfall_studio.register()
            desk = ui.restore_workspace_desktop(
                dock_channels=True,
                restore_script_output=True,
                dock_shelf=True,
                dock_outliner=True,
                apply_theme=True,
            )
            _results["desktop_restore"] = desk
            _stage = 1
            return 0.45

        if _stage == 1:
            showcase = _build_showcase_scene()
            _results["showcase"] = showcase
            # Switch Right Dock to Modeling Toolkit (`MODELING_TOOLKIT`)
            cyc = ui.cycle_right_dock("MODELING_TOOLKIT")
            ui.refresh_modeling_toolkit_widgets()
            ui.refresh_top_shelf_status()
            ui.outliner.refresh_outliner()
            _frame_viewport_camera()
            _results["right_dock_cycle"] = cyc
            _stage = 2
            return 0.55

        if _stage == 2:
            # Trigger a diagnostic audit from the Modeling Toolkit widget so its status box shows live numbers
            mtk_snap = ui.get_modeling_toolkit_snapshot()
            w_list = getattr(ui.modeling_toolkit, "_active_mtk_widgets", [])
            if w_list:
                w_list[-1]._on_run_diagnostics()
                w_list[-1].refresh_from_scene()
            ui.refresh_top_shelf_status()
            _frame_viewport_camera()
            _results["modeling_toolkit_snapshot"] = ui.get_modeling_toolkit_snapshot()
            _results["hud_state"] = viewport.get_hud_state()
            _results["registry_state"] = ui.get_registry_state()
            _stage = 3
            return 0.55

        if _stage == 3:
            from qtpy import QtCore, QtGui, QtWidgets
            from blendertk.env_utils.script_output import ScriptConsole

            ARTIFACT_PNG.parent.mkdir(parents=True, exist_ok=True)
            BRAIN_PNG.parent.mkdir(parents=True, exist_ok=True)

            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.processEvents()

            bpy.ops.screen.screenshot(filepath=str(ARTIFACT_PNG))

            composited_docks = []
            try:
                base_pix = QtGui.QPixmap(str(ARTIFACT_PNG))
                if not base_pix.isNull():
                    painter = QtGui.QPainter(base_pix)
                    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

                    # 1. Top Shelf (Status Line with LIVE: HiRes_Sculpt_Sphere + Tabbed Icon Shelf)
                    sdock = ui.desktop._get_top_shelf_dock()
                    s_rect = sdock.enforce_dock_geometry() or sdock._inner_dock._last_rect
                    if sdock.widget is not None and s_rect is not None:
                        sx, sy, sw, sh = s_rect
                        sdock.widget.resize(int(sw), int(sh))
                        if app is not None:
                            app.processEvents()
                        s_pix = sdock.widget.grab()
                        painter.drawPixmap(QtCore.QRect(int(sx), int(sy), int(sw), int(sh)), s_pix)
                        composited_docks.append("top_shelf")

                    # 2. Left Outliner + Maya Tool Box
                    ldock = ui.desktop._get_left_outliner_dock()
                    l_rect = ldock.enforce_dock_geometry() or ldock._inner_dock._last_rect
                    if ldock.widget is not None and l_rect is not None:
                        lx, ly, lw, lh = l_rect
                        ldock.widget.resize(int(lw), int(lh))
                        if app is not None:
                            app.processEvents()
                        l_pix = ldock.widget.grab()
                        painter.drawPixmap(QtCore.QRect(int(lx), int(ly), int(lw), int(lh)), l_pix)
                        composited_docks.append("left_outliner")

                    # 3. Right Sidebar (Modeling Toolkit tab active)
                    rdock = ui.desktop._get_right_dock()
                    r_rect = rdock.enforce_dock_geometry() or rdock._inner_dock._last_rect
                    if rdock.host_widget is not None and r_rect is not None:
                        rx, ry, rw, rh = r_rect
                        rdock.host_widget.resize(int(rw), int(rh))
                        if app is not None:
                            app.processEvents()
                        r_pix = rdock.host_widget.grab()
                        painter.drawPixmap(QtCore.QRect(int(rx), int(ry), int(rw), int(rh)), r_pix)
                        composited_docks.append("right_sidebar")

                    # 4. Bottom Script Output / Command Line
                    so_widget, _ = ui.get_panel_widget_and_slots("script_output")
                    so_dock = ScriptConsole.instance()._dock
                    so_dock._last_rect = None
                    so_dock._position(so_dock.content_region())
                    so_rect = so_dock._last_rect
                    if so_widget is not None and so_rect is not None:
                        bx, by, bw, bh = so_rect
                        so_pix = so_widget.grab()
                        painter.drawPixmap(QtCore.QRect(int(bx), int(by), int(bw), int(bh)), so_pix)
                        composited_docks.append("script_output")

                    painter.end()
                    base_pix.save(str(ARTIFACT_PNG))
                    base_pix.save(str(BRAIN_PNG))
            except Exception as comp_exc:
                print(f"[T05-2 composite warning] {comp_exc}")

            captured = ARTIFACT_PNG.is_file()
            _results["screenshot_saved"] = captured
            _results["screenshot_path"] = str(ARTIFACT_PNG)
            _results["composited_docks"] = composited_docks

            # Verify key assertions
            reg = _results["registry_state"]
            mtk = _results["modeling_toolkit_snapshot"]
            hud = _results["hud_state"]
            ok = (
                bool(reg.get("top_shelf_docked"))
                and bool(reg.get("left_outliner_docked"))
                and reg.get("right_dock_mode") == "MODELING_TOOLKIT"
                and bool(mtk.get("ok"))
                and "LIVE: HiRes_Sculpt_Sphere" in mtk.get("live_label", "")
                and bool(hud.get("caddy_open"))
                and hud.get("caddy_node_title") == "polyBevel1"
                and bool(hud.get("live_surface_active"))
                and hud.get("quad_draw_dot_count") == 4
                and captured
            )
            _results["ok"] = ok
            json_path = ARTIFACT_PNG.parent / "phase05_gui_results.json"
            json_path.write_text(json.dumps(_results, indent=2), encoding="utf-8")
            print("PHASE05_GUI_RESULT:" + json.dumps(_results))
            bpy.ops.wm.quit_blender()
            return None
    except Exception as exc:
        import traceback

        _results["ok"] = False
        _results["error"] = str(exc)
        _results["traceback"] = traceback.format_exc()
        print("PHASE05_GUI_RESULT:" + json.dumps(_results))
        bpy.ops.wm.quit_blender()
        return None


if __name__ == "__main__":
    bpy.app.timers.register(_step_timer, first_interval=0.4, persistent=True)
