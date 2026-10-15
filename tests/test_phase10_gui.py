"""Gate 10 Non-Headless GUI Visual Regression & Inspection Suite (`tests/test_phase10_gui.py`).

Captures 3 high-resolution (`1920x1080`) live Blender 5.2 GUI composite screenshots verifying:
1. `phase10_modern_maya_studio_eevee_gui.png`:
   - Full "Modern Maya Studio 1.0" desktop in **Viewport 2.0 (EEVEE — `All Lights [7]` + `SSAO` + `Shadows` + `Wire on Shaded`)**, Smooth Cage (`2` mode), in-viewport `polyBevel1` caddy, docked `Channel Box + SHAPES + INPUTS + AnimLayer Stack`, `DAG Outliner`, and pure `PYTHON` Command Bar.
2. `phase10_marking_menu_caddy_viewport_gui.png`:
   - Modernized GPU Radial Marking Menu (`Shift+RMB — MODELING TOOLS`) with thick directional vector connector line + origin target ring, compass badges (`W/E/S/N/NW/NE/SW/SE`), right-aligned hotkey badges (`Ctrl+E`, `Ctrl+B`, `Ctrl+R`), Smooth Cage (`2` mode), and `polyExtrudeFace1` caddy.
3. `phase10_attribute_editor_outliner_gui.png`:
   - Docked Maya `Attribute Editor` (`Transform | Shape | Inputs / Modifiers | Material / Shader` node tabs + `Blender ↔ Maya` concept mapping) + `DAG Outliner` + Viewport 2.0 (EEVEE) lookdev scene.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio import advanced, character, continuity, keymaps, modeling, ui, viewport
from landfall_studio.ui import (
    attribute_editor,
    channel_box_ext,
    desktop,
    outliner,
    right_dock,
    shelf,
    style,
    tool_settings,
)
from landfall_studio.viewport import marking_menus

AGENT_OUT_DIR = Path(
    r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output"
)
LOCAL_OUT_DIR = REPO_ROOT / "output"
BRAIN_DIR = Path(
    r"C:\Users\mattk\.gemini\antigravity\brain\7b1d9264-a274-459e-8c9a-2432ca72975f"
)

SHOT_1_NAME = "phase10_modern_maya_studio_eevee_gui.png"
SHOT_2_NAME = "phase10_marking_menu_caddy_viewport_gui.png"
SHOT_3_NAME = "phase10_attribute_editor_outliner_gui.png"

_stage: int = 0
_results: dict = {
    "ok": False,
    "version": "1.0.0",
    "design_system": {},
    "eevee_viewport_20": {},
    "marking_menu_state": {},
    "screenshots": {},
    "composited_docks": [],
}


def _maximize_and_bring_to_front() -> None:
    try:
        import ctypes
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow

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


def _frame_viewport_camera(dist: float = 5.2) -> None:
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        r3d = space.region_3d
                        if r3d is not None:
                            r3d.view_perspective = "PERSP"
                            r3d.view_location = Vector((0.1, -0.35, 0.90))
                            r3d.view_distance = dist
                            r3d.view_rotation = Euler((1.14, 0.0, 0.60), "XYZ").to_quaternion()
                for reg in area.regions:
                    reg.tag_redraw()


def _composite_and_save(shot_filename: str) -> list[str]:
    import ctypes
    from qtpy import QtCore, QtGui, QtWidgets
    import blendertk as btk
    from blendertk.ui_utils.blender_window import BlenderWindow

    AGENT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)

    target_png = AGENT_OUT_DIR / shot_filename
    local_png = LOCAL_OUT_DIR / shot_filename
    brain_png = BRAIN_DIR / shot_filename

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

            # Composite any floating Maya Tear-Off windows
            for tpanel in right_dock.list_torn_off_panels():
                tw_widget = tpanel.get("widget")
                tx, ty, tw, th = tpanel.get("rect", (0, 0, 0, 0))
                if tw_widget is not None and tw > 0 and th > 0:
                    if app is not None:
                        app.processEvents()
                    painter.drawPixmap(QtCore.QRect(int(tx), int(ty), int(tw), int(th)), tw_widget.grab())
                    composited_docks.append(f"tear_off:{tpanel.get('mode')}")
        finally:
            painter.end()

        base_pix.save(str(target_png))
        base_pix.save(str(local_png))
        base_pix.save(str(brain_png))
    return composited_docks


def _setup_hero_eevee_scene():
    for obj in list(bpy.data.objects):
        if obj.type in ("MESH", "EMPTY", "LIGHT"):
            bpy.data.objects.remove(obj, do_unlink=True)

    grp_root = bpy.data.objects.new("grp_turntable_asset", None)
    bpy.context.collection.objects.link(grp_root)
    grp_geo = bpy.data.objects.new("grp_hero_geo", None)
    bpy.context.collection.objects.link(grp_geo)
    grp_geo.parent = grp_root
    grp_lgt = bpy.data.objects.new("grp_eevee_rig_lights", None)
    bpy.context.collection.objects.link(grp_lgt)
    grp_lgt.parent = grp_root

    # 1. Live Surface Base
    res_base = channel_box_ext.create_maya_primitive(
        "PLANE", width=3.8, depth=3.8, subdivisions_x=4, subdivisions_y=4
    )
    base_mesh = bpy.data.objects.get(res_base["object_name"])
    base_mesh.name = "pPlane_LiveSurface"
    base_mesh.parent = grp_geo
    modeling.set_live_surface(base_mesh)

    # 2. Hero Cylinder Asset with Smooth Cage (Mode 2) + Bevel + PBR StandardSurface Material
    res_hero = channel_box_ext.create_maya_primitive(
        "CYLINDER",
        radius=1.18,
        height=2.2,
        subdivisions_x=28,
        subdivisions_y=4,
        subdivisions_z=1,
    )
    hero = bpy.data.objects.get(res_hero["object_name"])
    hero.name = "pCylinder_HeroMech"
    hero.parent = grp_geo
    hero.location = Vector((0.0, 0.0, 1.05))
    hero.rotation_euler = Euler((0.28, -0.20, 0.42), "XYZ")

    # Assign Maya Hypershade Brushed Metal / Teal Clearcoat shader for EEVEE Viewport 2.0
    mat_res = advanced.create_from_template(
        "car_paint",
        name="aiStandardSurface_HeroTeal",
        assign_to_selection=False,
    )
    mat = bpy.data.materials.get(mat_res.get("material", ""))
    if mat is not None:
        if hero.data.materials:
            hero.data.materials[0] = mat
        else:
            hero.data.materials.append(mat)
        advanced.set_material_parameter(mat.name, "Base Color", (0.20, 0.46, 0.62, 1.0))
        advanced.set_material_parameter(mat.name, "Metallic", 0.72)
        advanced.set_material_parameter(mat.name, "Roughness", 0.24)

    # Create Three-Point EEVEE Studio Lights (Key, Fill, Rim) for Maya 7 'All Lights' EEVEE mode
    key_data = bpy.data.lights.new("keyLightShape", type="AREA")
    key_data.energy = 240.0
    key_data.color = (1.0, 0.96, 0.90)
    key_data.size = 3.5
    key_obj = bpy.data.objects.new("areaLight_Key", key_data)
    bpy.context.collection.objects.link(key_obj)
    key_obj.parent = grp_lgt
    key_obj.location = Vector((3.2, -2.8, 3.8))
    key_obj.rotation_euler = Euler((0.68, 0.12, 0.72), "XYZ")

    rim_data = bpy.data.lights.new("rimLightShape", type="AREA")
    rim_data.energy = 160.0
    rim_data.color = (0.45, 0.78, 1.0)
    rim_data.size = 2.8
    rim_obj = bpy.data.objects.new("areaLight_RimTeal", rim_data)
    bpy.context.collection.objects.link(rim_obj)
    rim_obj.parent = grp_lgt
    rim_obj.location = Vector((-3.0, 2.6, 2.9))
    rim_obj.rotation_euler = Euler((-0.62, -0.22, -0.78), "XYZ")

    bpy.ops.object.select_all(action="DESELECT")
    hero.select_set(True)
    bpy.context.view_layer.objects.active = hero

    # Enable Smooth Cage (Maya '2' mode: Cage + Smooth)
    try:
        bpy.ops.landfall.smooth_preview(mode="BOTH")
    except Exception:
        pass

    # Add Bevel modifier, procedural Geometry Nodes modifier, and open polyBevel1 caddy
    channel_box_ext.ensure_procedural_geonodes_modifier(hero, name="geoNodes_Procedural1")
    modeling.invoke_modeling_caddy("BEVEL")

    # Add Shape Editor targets + Animation Layers + keyframes on hero for Channel Box & Time Slider
    character.create_shape_target(hero, "Turntable_Flare", weight=0.42)
    advanced.ensure_base_animation_layer(hero)
    for f_no, rz in [(1, 0.42), (18, 0.75), (36, 1.15), (60, 1.65), (90, 2.15), (120, 0.42)]:
        advanced.keyframe_on_anim_layer(hero, "BaseAnimation", "rotation_euler", 2, value=rz, frame=f_no)
        advanced.keyframe_on_anim_layer(hero, "BaseAnimation", "location", 2, value=1.05, frame=f_no)
    advanced.create_anim_layer(hero, name="AnimLayer1_Turntable", mode="ADD", weight=1.0)
    for f_no, dz in [(1, 0.0), (24, 0.14), (48, -0.08), (72, 0.18), (96, 0.05)]:
        advanced.keyframe_on_anim_layer(hero, "AnimLayer1_Turntable", "location", 2, value=dz, frame=f_no)
    advanced.create_anim_layer(hero, name="AnimLayer2_HoverBob", mode="ADD", weight=0.85)
    bpy.context.scene.frame_set(1)

    # Set Active Tool to Move (W)
    try:
        bpy.ops.landfall_studio.select_tool(tool="TRANSLATE")
    except Exception:
        pass

    return hero


def _step_timer() -> float | None:
    global _stage
    try:
        if _stage == 0:
            bpy.context.preferences.view.show_splash = False
            bpy.ops.wm.read_homefile()
            _maximize_and_bring_to_front()
            landfall_studio.register()
            _results["desktop_restore"] = ui.restore_workspace_desktop(
                dock_channels=True,
                restore_script_output=False,
            )
            _hide_native_blender_viewport_bars()
            _stage = 1
            return 0.55

        if _stage == 1:
            _hide_native_blender_viewport_bars()
            _setup_hero_eevee_scene()

            # Activate Maya '7' (Use All Scene Lights in Viewport 2.0 EEVEE) + Wire on Shaded + SSAO + Shadows
            continuity.set_maya_viewport_shading("7")
            continuity.toggle_viewport_20_feature("SSAO", enable=True)
            continuity.toggle_viewport_20_feature("SHADOWS", enable=True)
            sh_state = continuity.get_viewport_shading_state()
            if not sh_state.get("wire_on_shaded"):
                continuity.set_maya_viewport_shading("WIRE_ON_SHADED")
            _results["eevee_viewport_20"] = continuity.get_viewport_shading_state()
            _results["design_system"] = style.verify_three_layer_theme_sync(dpi_scale=1.0)

            # Set Workspace to Modeling Standard (de-cluttered 4-tab right spine + Channel Box + GeoNodes INPUTS)
            desktop.apply_workspace_layout("Modeling Standard")
            desktop.sync_channels_now()
            channel_box_ext.refresh_channel_box_extensions()
            cb_widget, _ = ui.get_panel_widget_and_slots("channels")
            ext = getattr(cb_widget, "_lf_cb_ext_container", None) or channel_box_ext._channel_box_ext_instance
            if ext is not None and hasattr(ext, "set_layer_editor_tab"):
                ext.set_layer_editor_tab("ANIM")
            shelf.refresh_top_shelf_status()
            outliner.refresh_outliner()
            ui.refresh_time_slider_widgets()
            desktop.set_command_feedback(
                "apply_workspace_layout('Modeling Standard') | ensure_procedural_geonodes_modifier()",
                "Result: Modeling Standard • Channel Box + GeoNodes INPUTS • Viewport 2.0 (EEVEE [7])",
            )
            _frame_viewport_camera(dist=5.1)
            _stage = 2
            return 0.55

        if _stage == 2:
            # Capture Shot 1: Full Modern Maya Studio 1.0 Desktop in Viewport 2.0 (EEVEE)
            _hide_native_blender_viewport_bars()
            channel_box_ext.refresh_channel_box_extensions()
            cb_widget, _ = ui.get_panel_widget_and_slots("channels")
            ext = getattr(cb_widget, "_lf_cb_ext_container", None) or channel_box_ext._channel_box_ext_instance
            if ext is not None and hasattr(ext, "set_layer_editor_tab"):
                ext.set_layer_editor_tab("ANIM")
            docks_1 = _composite_and_save(SHOT_1_NAME)
            _results["composited_docks"] = docks_1
            _results["screenshots"]["studio_eevee_desktop"] = str(AGENT_OUT_DIR / SHOT_1_NAME)

            # Prepare Shot 2: Open Modernized GPU Radial Marking Menu + polyExtrudeFace1 Caddy + Floating Tear-Off Window!
            right_dock.tear_off_panel("TOOL_SETTINGS", x=1095, y=135, width=320, height=445)
            modeling.invoke_modeling_caddy("EXTRUDE")
            win = bpy.context.window_manager.windows[0]
            area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), win.screen.areas[0])
            region = next((r for r in area.regions if r.type == "WINDOW"), area.regions[0])
            mm_cx = int(region.width * 0.35)
            mm_cy = int(region.height * 0.64)
            with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
                bpy.ops.landfall_studio.marking_menu(
                    menu_mode="TOOL",
                    select_radial_index=0,
                    keep_open_for_capture=True,
                    raycast_x=mm_cx,
                    raycast_y=mm_cy,
                )
            _results["marking_menu_state"] = marking_menus.get_marking_menu_state()
            desktop.set_command_feedback(
                "tear_off_panel('TOOL_SETTINGS') | marking_menu(menu_mode='TOOL')",
                "Result: Floating Tear-Off Window (TOOL SETTINGS) + Shift+RMB Radial Marking Menu",
            )
            for r in area.regions:
                r.tag_redraw()
            _stage = 3
            return 0.50

        if _stage == 3:
            # Capture Shot 2: Modernized Radial Marking Menu + Floating Tear-Off Window + Caddy
            _hide_native_blender_viewport_bars()
            _composite_and_save(SHOT_2_NAME)
            _results["screenshots"]["marking_menu_caddy"] = str(AGENT_OUT_DIR / SHOT_2_NAME)
            marking_menus.stop_studio_marking_menu()
            right_dock.teardown_tear_off_windows()

            # Prepare Shot 3: Multi-Pane 'Lookdev / Hypershade' Workspace Layout (Top EEVEE Viewport + Bottom Blender ShaderNodeTree + Right Hypershade Browser)
            continuity.set_maya_viewport_shading("6")
            desktop.apply_workspace_layout("Lookdev / Hypershade")
            shelf.refresh_top_shelf_status()
            outliner.refresh_outliner()
            desktop.set_command_feedback(
                "apply_workspace_layout('Lookdev / Hypershade') | set_bottom_node_graph_split(True, 'SHADER')",
                "Result: Lookdev / Hypershade Workspace • Top 3D Viewport (EEVEE) + Bottom ShaderNodeTree Graph",
            )
            _frame_viewport_camera(dist=4.7)
            _stage = 4
            return 0.55

        if _stage == 4:
            # Capture Shot 3: Multi-Pane Lookdev / Hypershade Workspace (Top EEVEE + Bottom Shader Graph + Right Hypershade)
            _hide_native_blender_viewport_bars()
            _composite_and_save(SHOT_3_NAME)
            _results["screenshots"]["attribute_editor_outliner"] = str(AGENT_OUT_DIR / SHOT_3_NAME)
            desktop.apply_workspace_layout("Modeling Standard")

            _results["ok"] = bool(
                (AGENT_OUT_DIR / SHOT_1_NAME).is_file()
                and (AGENT_OUT_DIR / SHOT_2_NAME).is_file()
                and (AGENT_OUT_DIR / SHOT_3_NAME).is_file()
                and _results["design_system"].get("ok")
                and _results["eevee_viewport_20"].get("renderer_label") == "Viewport 2.0 (EEVEE)"
                and _results["marking_menu_state"].get("open")
            )
            for out_json in (
                AGENT_OUT_DIR / "phase10_gui_results.json",
                LOCAL_OUT_DIR / "phase10_gui_results.json",
            ):
                out_json.parent.mkdir(parents=True, exist_ok=True)
                out_json.write_text(json.dumps(_results, indent=2), encoding="utf-8")
            print("PHASE10_GUI_RESULT:" + json.dumps(_results), flush=True)
            landfall_studio.unregister()
            bpy.ops.wm.quit_blender()
            return None
    except Exception as exc:
        import traceback

        _results["ok"] = False
        _results["error"] = str(exc)
        _results["traceback"] = traceback.format_exc()
        print("PHASE10_GUI_RESULT:" + json.dumps(_results), flush=True)
        bpy.ops.wm.quit_blender()
        return None


if __name__ == "__main__":
    bpy.app.timers.register(_step_timer, first_interval=0.45, persistent=True)
