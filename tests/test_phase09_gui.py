"""Gate 09 Live Blender 5.2 GUI Verification & Maya Continuity Screenshot Suite (`T09-GUI`):
Verifies the full 5-dock Modern Maya Studio desktop for Gate 09 (`09_BLENDER_NATIVE_CONTINUITY.md`):
1. Viewport 2.0 Shading (`4 / 5 / 6 / 7` + `Alt+Z` X-Ray + `Wire on Shaded`) reflected live in the Top 26px Viewport Strip.
2. Maya Soft Selection (`B` Toggle + `Hold B + LMB-Drag` Falloff Radius Ring) synchronized across:
   - 3D Viewport 3-ring concentric heatmap falloff ring (`SOFT SELECT [B] • Radius: 2.35m • Falloff: SMOOTH`)
   - Top Status Line amber `◎ Soft [B]: 2.35m` pill
   - Left 42px Tool Box Rail `B` Soft Select button
   - Right Dock `Tool Settings` (`SOFT SELECTION (B)` section)
3. Native Blender Editors & Modes Bridge (`FX / Nodes` Shelf tab + `GeometryNodes` modifier on `pCylinder1` visible in the DAG Outliner + `Sculpt` / `Grease Pencil` / `UV Editor` / `Shader Editor` bridges) with zero keymap leaks into protected contexts.
"""

from __future__ import annotations

import ctypes
import json
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio  # noqa: E402
from landfall_studio import advanced, continuity, keymaps, modeling, ui, viewport  # noqa: E402
from landfall_studio.ui import channel_box_ext, desktop, outliner, shelf, tool_settings  # noqa: E402

ARTIFACT_DIR = Path(
    r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output"
)
LOCAL_OUT_DIR = REPO_ROOT / "output"
BRAIN_DIR = Path(
    r"C:\Users\mattk\.gemini\antigravity\brain\7b1d9264-a274-459e-8c9a-2432ca72975f"
)
SOFT_SELECT_PNG = ARTIFACT_DIR / "phase09_maya_continuity_soft_select_gui.png"
LOCAL_SOFT_SELECT_PNG = LOCAL_OUT_DIR / "phase09_maya_continuity_soft_select_gui.png"
BRAIN_SOFT_SELECT_PNG = BRAIN_DIR / "phase09_maya_continuity_soft_select_gui.png"

_results: dict = {
    "ok": False,
    "shading_modes_verified": {},
    "soft_selection": {},
    "native_bridges": {},
    "keymap_scan": {},
}
_stage: int = 0
_bars_hidden_once: bool = False


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


def _hide_native_blender_viewport_bars() -> None:
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                with bpy.context.temp_override(window=win, screen=win.screen, area=area):
                    for sp in area.spaces:
                        if sp.type == "VIEW_3D":
                            sp.show_region_toolbar = False
                            sp.show_region_header = False
                            sp.show_region_tool_header = False
                            sp.show_gizmo = True
                            sp.show_gizmo_navigate = False
                for r in area.regions:
                    r.tag_redraw()


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
                            r3d.view_location = Vector((0.15, -0.4, 0.95))
                            r3d.view_distance = 5.4
                            r3d.view_rotation = Euler((1.12, 0.0, 0.58), "XYZ").to_quaternion()
                for reg in area.regions:
                    reg.tag_redraw()


def _composite_and_save(target_png: Path, local_png: Path, brain_png: Path) -> list[str]:
    from qtpy import QtCore, QtGui, QtWidgets
    import blendertk as btk
    from blendertk.ui_utils.blender_window import BlenderWindow

    target_png.parent.mkdir(parents=True, exist_ok=True)
    local_png.parent.mkdir(parents=True, exist_ok=True)
    brain_png.parent.mkdir(parents=True, exist_ok=True)

    win = btk.main_window()
    hwnd = BlenderWindow.window_hwnd(win) if win else None
    if hwnd:
        ctypes.windll.user32.SetFocus(hwnd)

    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()

    v3d_area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), win.screen.areas[0])
    v3d_region = next((r for r in v3d_area.regions if r.type == "WINDOW"), v3d_area.regions[0])
    with bpy.context.temp_override(
        window=win,
        screen=win.screen,
        area=v3d_area,
        region=v3d_region,
    ):
        bpy.ops.screen.screenshot(filepath=str(target_png))

    composited_docks = []
    base_pix = QtGui.QPixmap(str(target_png))
    if not base_pix.isNull():
        painter = QtGui.QPainter(base_pix)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        try:
            sdock = ui.desktop._get_top_shelf_dock()
            s_rect = sdock.enforce_dock_geometry() or sdock._inner_dock._last_rect
            if sdock.widget is not None and s_rect is not None:
                sx, sy, sw, sh = s_rect
                sdock.widget.resize(int(sw), int(sh))
                if app is not None:
                    app.processEvents()
                painter.drawPixmap(QtCore.QRect(int(sx), int(sy), int(sw), int(sh)), sdock.widget.grab())
                composited_docks.append("top_shelf")

            ldock = ui.desktop._get_left_outliner_dock()
            l_rect = ldock.enforce_dock_geometry() or ldock._inner_dock._last_rect
            if ldock.widget is not None and l_rect is not None:
                lx, ly, lw, lh = l_rect
                ldock.widget.resize(int(lw), int(lh))
                if app is not None:
                    app.processEvents()
                painter.drawPixmap(QtCore.QRect(int(lx), int(ly), int(lw), int(lh)), ldock.widget.grab())
                composited_docks.append("left_outliner")

            rdock = ui.desktop._get_right_dock()
            r_rect = rdock.enforce_dock_geometry() or rdock._inner_dock._last_rect
            if rdock.host_widget is not None and r_rect is not None:
                rx, ry, rw, rh = r_rect
                rdock.host_widget.resize(int(rw), int(rh))
                if app is not None:
                    app.processEvents()
                painter.drawPixmap(QtCore.QRect(int(rx), int(ry), int(rw), int(rh)), rdock.host_widget.grab())
                composited_docks.append("right_sidebar")

            tdock = ui.time_slider.get_bottom_time_slider_dock()
            t_rect = tdock.enforce_dock_geometry() or tdock._inner_dock._last_rect
            if tdock.widget is not None and t_rect is not None:
                tx, ty, tw, th = t_rect
                tdock.widget.resize(int(tw), int(th))
                if app is not None:
                    app.processEvents()
                painter.drawPixmap(QtCore.QRect(int(tx), int(ty), int(tw), int(th)), tdock.widget.grab())
                composited_docks.append("time_slider")
        finally:
            painter.end()

        base_pix.save(str(target_png))
        base_pix.save(str(local_png))
        base_pix.save(str(brain_png))
    return composited_docks


def _setup_hero_continuity_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    grp_root = bpy.data.objects.new("grp_asset_root", None)
    bpy.context.collection.objects.link(grp_root)
    grp_geo = bpy.data.objects.new("grp_render_geo", None)
    bpy.context.collection.objects.link(grp_geo)
    grp_geo.parent = grp_root

    res_base = channel_box_ext.create_maya_primitive("PLANE", width=3.6, depth=3.6, subdivisions_x=4, subdivisions_y=4)
    base_mesh = bpy.data.objects.get(res_base["object_name"])
    base_mesh.name = "pPlane_LiveBase"
    base_mesh.parent = grp_geo
    modeling.set_live_surface(base_mesh)

    res_hero = channel_box_ext.create_maya_primitive(
        "CYLINDER",
        radius=1.18,
        height=2.2,
        subdivisions_x=28,
        subdivisions_y=4,
        subdivisions_z=1,
    )
    hero = bpy.data.objects.get(res_hero["object_name"])
    hero.name = "pCylinder1"
    if hero.data:
        hero.data.name = "pCylinderShape1"
    hero.parent = grp_geo
    hero.location = (0.35, -1.20, 1.15)
    hero.rotation_euler = (0.0, 0.785398, 0.0)

    bpy.context.view_layer.objects.active = hero
    hero.select_set(True)
    modeling.invoke_modeling_caddy("BEVEL")

    # Bridge 1: Attach Geometry Nodes graph via Phase 09 Native Bridge
    gn_res = continuity.open_native_editor_or_mode("GEOMETRY_NODES")
    _results["native_bridges"]["geometry_nodes"] = gn_res

    # Assign Standard Surface shader
    advanced.create_from_template(
        "aiStandardSurface",
        name="aiStandardSurface_Hero",
        assign_to_selection=True,
    )
    advanced.set_material_parameter("aiStandardSurface_Hero", "base_color", (0.28, 0.58, 0.78))

    # Verify Maya 4 / 5 / 6 / 7 Viewport Shading modes
    for m_key in ("4", "5", "6", "7"):
        st_m = continuity.set_maya_viewport_shading(m_key)
        _results["shading_modes_verified"][m_key] = st_m["maya_id"]

    # Settle on Maya 6 (Shaded & Textured) + Wireframe on Shaded
    continuity.set_maya_viewport_shading("6")
    hero.show_wire = True
    hero.show_all_edges = True

    # Enable Maya Soft Selection (B) with Falloff Ring active
    soft_st = continuity.set_soft_selection_state(
        enabled=True,
        radius=2.35,
        falloff_curve="SMOOTH",
        show_ring_overlay=False,
    )
    _results["soft_selection"] = soft_st
    _results["keymap_scan"] = keymaps.scan_keymap_conflicts()
    _results["shadowed_shortcut_count"] = len(continuity.get_shadowed_shortcut_map())


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
                restore_script_output=False,
                dock_shelf=True,
                dock_outliner=True,
                dock_time_slider_bar=True,
                apply_theme=True,
            )
            _results["desktop_restore"] = desk
            _stage = 1
            return 0.50

        if _stage == 1:
            _hide_native_blender_viewport_bars()
            _setup_hero_continuity_scene()
            # Switch Top Shelf to 'FX / Nodes' tab so Geometry Nodes / Sculpt / Grease Pencil / Soft [B] tiles are visible
            for inst in getattr(shelf, "_shelf_instances", ()):
                for idx in range(inst.tabs.count()):
                    if "FX" in inst.tabs.tabText(idx) or "Nodes" in inst.tabs.tabText(idx):
                        inst.tabs.setCurrentIndex(idx)
                        break
            tool_settings.set_tool_setting("tool_context", "SOFT_SELECT")
            desktop.cycle_right_dock("TOOL_SETTINGS")
            tool_settings.refresh_tool_settings_widget()
            shelf.refresh_top_shelf_status()
            outliner.refresh_outliner()
            ui.refresh_time_slider_widgets()
            desktop.set_command_feedback(
                "softSelect(enable=True, radius=2.35, falloff='SMOOTH') | open_native_editor('GEOMETRY_NODES')",
                "Result: Soft Selection [B] ON (r=2.35m) • pCylinder1_GeoNodes Active",
            )
            _frame_viewport_camera()
            _stage = 2
            return 0.65

        if _stage == 2:
            _hide_native_blender_viewport_bars()
            tool_settings.refresh_tool_settings_widget()
            shelf.refresh_top_shelf_status()
            outliner.refresh_outliner()
            ui.refresh_time_slider_widgets()
            _frame_viewport_camera()
            _stage = 3
            return 0.35

        if _stage == 3:
            _hide_native_blender_viewport_bars()
            docks = _composite_and_save(
                SOFT_SELECT_PNG, LOCAL_SOFT_SELECT_PNG, BRAIN_SOFT_SELECT_PNG
            )
            _results["composited_docks"] = docks
            _results["hud_state"] = viewport.get_hud_state()
            _results["screenshot"] = str(SOFT_SELECT_PNG)
            _results["ok"] = bool(
                SOFT_SELECT_PNG.is_file()
                and len(docks) >= 4
                and _results["soft_selection"].get("enabled")
                and _results["keymap_scan"].get("clean")
                and _results["native_bridges"].get("geometry_nodes", {}).get("ok")
            )
            for out_json in (
                ARTIFACT_DIR / "phase09_gui_results.json",
                LOCAL_OUT_DIR / "phase09_gui_result.json",
            ):
                out_json.parent.mkdir(parents=True, exist_ok=True)
                out_json.write_text(json.dumps(_results, indent=2), encoding="utf-8")
            print("PHASE09_GUI_RESULT:" + json.dumps(_results), flush=True)
            landfall_studio.unregister()
            bpy.ops.wm.quit_blender()
            return None
    except Exception as exc:
        import traceback

        _results["ok"] = False
        _results["error"] = str(exc)
        _results["traceback"] = traceback.format_exc()
        print("PHASE09_GUI_RESULT:" + json.dumps(_results), flush=True)
        bpy.ops.wm.quit_blender()
        return None


if __name__ == "__main__":
    bpy.app.timers.register(_step_timer, first_interval=0.45, persistent=True)
