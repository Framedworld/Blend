"""Gate 08 GUI Verification & Maya UI Polish Screenshot Suite (`T08-GUI`):
Verifies the full 5-dock Modern Maya Studio desktop after the Gate 08 Hypershade + Animation/Weight Layers + Maya UI Polish Pass:
- Clean 3D Viewport with Blender's native `Object Mode` header and left `T` toolbar hidden so only the Maya Viewport 2.0 chrome (`Panels  View  Shading  Lighting  Show  Renderer  Help`, `POLY COUNT` HUD, `● LIVE SURFACE`, `polyBevel1` caddy, and bottom-left `X/Y/Z` World Axis Tripod above `persp`) is visible
- Polished Maya Channel Box (`RightAreaQtDock`) with full `Translate X/Y/Z`, `Rotate X/Y/Z`, `Scale X/Y/Z`, `Visibility` labels, tight `218px` table height so `SHAPES` and `INPUTS` sit directly below `Scale Z`, and bottom `Display | Anim` Layer Editor tabs showing `BaseAnimation` + additive/override NLA layers
- Docked `HYPERSHADE` right-dock mode (`HypershadePanel`) with custom-painted 3D specular shader ball swatches, 1-click `aiStandardSurface` / Principled presets (`Metal`, `Brushed Metal`, `Rough Metal`, `Plastic`, `Rubber`, `Glass`, `Clearcoat`, `Emission`, `Skin (SSS)`), interactive parameter scrubbers, PBR texture auto-wiring, and `Graph Network (Shader Editor)` integration
- Pure `PYTHON` command bar badge at the bottom of the workspace (no MEL)
- Captures `output/phase08_maya_channel_box_anim_layers_gui.png` and `output/phase08_maya_hypershade_ui_gui.png`.
"""

from __future__ import annotations

import ctypes
import json
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Euler, Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio import advanced, character, interchange, modeling, ui, viewport

ARTIFACT_DIR = Path(
    r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output"
)
BRAIN_DIR = Path(
    r"C:\Users\mattk\.gemini\antigravity\brain\7b1d9264-a274-459e-8c9a-2432ca72975f"
)
CHANNEL_BOX_PNG = ARTIFACT_DIR / "phase08_maya_channel_box_anim_layers_gui.png"
BRAIN_CHANNEL_BOX_PNG = BRAIN_DIR / "phase08_maya_channel_box_anim_layers_gui.png"
HYPERSHADE_PNG = ARTIFACT_DIR / "phase08_maya_hypershade_ui_gui.png"
BRAIN_HYPERSHADE_PNG = BRAIN_DIR / "phase08_maya_hypershade_ui_gui.png"

_results: dict = {"steps": []}
_stage: int = 0
_temp_dir = Path(tempfile.mkdtemp(prefix="lf_phase08_gui_"))


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


_bars_hidden_once: bool = False


def _hide_native_blender_viewport_bars() -> None:
    """Safely hide Blender's native VIEW_3D header, tool header, and T-toolbar once after area_split completes."""
    global _bars_hidden_once
    if _bars_hidden_once:
        return
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
    _bars_hidden_once = True


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
                            r3d.view_location = Vector((0.0, 0.0, 0.68))
                            r3d.view_distance = 5.1
                            r3d.view_rotation = Euler((1.14, 0.0, 0.56), "XYZ").to_quaternion()
                for reg in area.regions:
                    reg.tag_redraw()


def _write_dummy_png(path: Path, rgba: tuple[float, float, float, float]) -> str:
    img = bpy.data.images.new(name=path.stem, width=16, height=16, alpha=True)
    img.pixels = list(rgba) * (16 * 16)
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return str(path)


def _build_reference_blend(ref_blend_path: Path) -> None:
    col = bpy.data.collections.new("Ref_Scan_Proxy_GRP")
    bpy.context.scene.collection.children.link(col)
    bpy.ops.mesh.primitive_torus_add(
        major_radius=1.85, minor_radius=0.05, major_segments=48, minor_segments=16, location=(0.0, 0.0, 0.05)
    )
    ring = bpy.context.view_layer.objects.active
    ring.name = "ref_turntable_ring_GEO"
    ring_mesh = ring.data
    for c in list(ring.users_collection):
        c.objects.unlink(ring)
    col.objects.link(ring)
    bpy.data.libraries.write(str(ref_blend_path), {col}, fake_user=True)
    bpy.data.objects.remove(ring, do_unlink=True)
    bpy.data.meshes.remove(ring_mesh, do_unlink=True)
    bpy.data.collections.remove(col)


def _build_phase08_showcase() -> dict:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mat in list(bpy.data.materials):
        if not getattr(mat, "is_grease_pencil", False):
            bpy.data.materials.remove(mat, do_unlink=True)

    ref_blend = _temp_dir / "ref_turntable_proxy.blend"
    _build_reference_blend(ref_blend)

    ma_path = _temp_dir / "chr_paladin_maya.ma"
    fix_res = interchange.generate_maya_fixture_ma(str(ma_path))
    authored_ma = bool(fix_res.get("ok"))

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120
    scene.frame_current = 1

    if authored_ma:
        interchange.import_maya_scene(str(ma_path), clear_existing=False, use_cache=True)

    body = bpy.data.objects.get("body_main_GEO")
    if body is None or body.type != "MESH":
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=32, ring_count=20, radius=1.22, location=(0.0, 0.0, 0.72)
        )
        body = bpy.context.view_layer.objects.active
        body.name = "body_main_GEO"
    body.data.name = "body_main_GEOShape"

    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=36, ring_count=24, radius=1.18, location=(0.0, 0.0, 0.78)
    )
    sculpt_hero = bpy.context.view_layer.objects.active
    sculpt_hero.name = "paladin_chest_armor_GEO"
    bpy.ops.object.shade_smooth()
    sculpt_hero.show_wire = True
    sculpt_hero.show_all_edges = True

    # Create rich Hypershade shader ball materials from presets
    m_armor = advanced.create_from_template("Metal", name="aiStd_Paladin_Armor", assign_to_selection=False)
    advanced.set_material_parameter("aiStd_Paladin_Armor", "base_color", (0.32, 0.56, 0.78))
    advanced.set_material_parameter("aiStd_Paladin_Armor", "roughness", 0.24)
    advanced.set_material_parameter("aiStd_Paladin_Armor", "metallic", 0.88)

    m_gold = advanced.create_from_template("Brushed Metal", name="aiStd_Gold_Trim", assign_to_selection=False)
    advanced.set_material_parameter("aiStd_Gold_Trim", "base_color", (0.86, 0.68, 0.26))
    advanced.set_material_parameter("aiStd_Gold_Trim", "roughness", 0.28)
    advanced.set_material_parameter("aiStd_Gold_Trim", "metallic", 0.95)

    m_visor = advanced.create_from_template("Glass", name="aiStd_Visor_Glass", assign_to_selection=False)
    advanced.set_material_parameter("aiStd_Visor_Glass", "base_color", (0.20, 0.78, 0.95))
    advanced.set_material_parameter("aiStd_Visor_Glass", "roughness", 0.06)

    m_rubber = advanced.create_from_template("Rubber", name="aiStd_UnderSuit_Rubber", assign_to_selection=False)
    m_skin = advanced.create_from_template("Skin (SSS)", name="aiStd_Skin_Subsurface", assign_to_selection=False)
    m_glow = advanced.create_from_template("Emission", name="aiStd_Core_Emissive", assign_to_selection=False)
    advanced.set_material_parameter("aiStd_Core_Emissive", "base_color", (0.22, 0.82, 1.0))

    # Auto-wire PBR texture maps onto aiStd_Paladin_Armor
    bc_png = _write_dummy_png(_temp_dir / "T_Paladin_BaseColor.png", (0.32, 0.56, 0.78, 1.0))
    r_png = _write_dummy_png(_temp_dir / "T_Paladin_Roughness.png", (0.24, 0.24, 0.24, 1.0))
    m_png = _write_dummy_png(_temp_dir / "T_Paladin_Metallic.png", (0.88, 0.88, 0.88, 1.0))
    n_png = _write_dummy_png(_temp_dir / "T_Paladin_Normal.png", (0.5, 0.5, 1.0, 1.0))
    pbr_res = advanced.auto_wire_pbr_textures(
        "aiStd_Paladin_Armor", [bc_png, r_png, m_png, n_png], create_if_missing=False
    )

    advanced.assign_material_to_selection("aiStd_Paladin_Armor", objects=[body, sculpt_hero])
    pauldron_l = bpy.data.objects.get("pauldron_L_GEO")
    pauldron_r = bpy.data.objects.get("pauldron_R_GEO")
    if pauldron_l and pauldron_r:
        advanced.assign_material_to_selection("aiStd_Gold_Trim", objects=[pauldron_l, pauldron_r])

    body.show_wire = True
    body.show_all_edges = True

    # Ensure polyBevel1 & polySmoothFace1 in INPUTS
    if "polyBevel1" not in body.modifiers:
        bev = body.modifiers.new(name="polyBevel1", type="BEVEL")
        bev.width = 0.15
        bev.segments = 4
        bev.profile = 0.5
    if "polySmoothFace1" not in body.modifiers:
        sub = body.modifiers.new(name="polySmoothFace1", type="SUBSURF")
        sub.levels = 1

    # Add Shape Editor targets + keyframes
    character.create_shape_target(body, "Armor_Expand", weight=0.35)
    character.create_shape_target(body, "Breathing_Chest", weight=0.20)
    for f_no, w_val in [(1, 0.0), (18, 0.4), (36, 0.85), (54, 0.5), (72, 1.0), (96, 0.25)]:
        character.keyframe_shape_target(body, "Armor_Expand", frame=f_no, weight=w_val)

    # Author Maya Animation Layers (`BaseAnimation` + `AnimLayer1_Recoil` + `AnimLayer2_Breathing` + `AnimLayer3_PoseFix`)
    advanced.ensure_base_animation_layer(body)
    for f_no, rz in [(1, 0.0), (14, 0.25), (28, -0.20), (45, 0.38), (62, 0.0), (84, 0.28), (105, 0.0)]:
        advanced.keyframe_on_anim_layer(body, "BaseAnimation", "rotation_euler", 2, value=rz, frame=f_no)
        advanced.keyframe_on_anim_layer(body, "BaseAnimation", "location", 2, value=0.72, frame=f_no)

    advanced.create_anim_layer(body, "AnimLayer1_Recoil", mode="ADD", weight=0.85)
    for f_no, dz in [(1, 0.0), (14, 0.12), (28, -0.05), (45, 0.18), (84, 0.08)]:
        advanced.keyframe_on_anim_layer(body, "AnimLayer1_Recoil", "location", 2, value=dz, frame=f_no)

    advanced.create_anim_layer(body, "AnimLayer2_Breathing", mode="ADD", weight=0.50)
    for f_no, sx in [(1, 0.0), (36, 0.06), (72, -0.04), (105, 0.0)]:
        advanced.keyframe_on_anim_layer(body, "AnimLayer2_Breathing", "scale", 0, value=sx, frame=f_no)

    advanced.create_anim_layer(body, "AnimLayer3_PoseFix", mode="OVERRIDE", weight=1.0)
    advanced.keyframe_on_anim_layer(body, "AnimLayer3_PoseFix", "location", 2, value=0.72, frame=1)
    advanced.set_anim_layer_state(body, "AnimLayer3_PoseFix", mute=True)

    # Author non-destructive Skin Weight Layers
    if "Root_Jnt" not in body.vertex_groups:
        body.vertex_groups.new(name="Root_Jnt")
    if "Chest_Jnt" not in body.vertex_groups:
        body.vertex_groups.new(name="Chest_Jnt")
    body.vertex_groups["Root_Jnt"].lock_weight = True
    advanced.ensure_base_weight_layer(body)
    advanced.create_weight_layer(body, "ShoulderFix_Layer", mode="OVERRIDE", weight=0.75)

    # Reference turntable proxy
    ref_res = interchange.reference_scene(str(ref_blend), display_mode="reference")

    # Add key light and camera
    light_data = bpy.data.lights.new(name="keyLight_area1Shape", type="AREA")
    light_obj = bpy.data.objects.new(name="keyLight_area1", object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.location = (2.8, -2.5, 3.4)

    cam_data = bpy.data.cameras.new(name="cam_render_shot01Shape")
    cam_obj = bpy.data.objects.new(name="cam_render_shot01", object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.5, 1.4)

    scene.frame_start = 1
    scene.frame_end = 120
    scene.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    sculpt_hero.select_set(True)
    bpy.context.view_layer.objects.active = body

    # Activate floating polyBevel1 in-viewport caddy
    modeling.invoke_modeling_caddy("BEVEL", apply_live=False)

    return {
        "authored_ma": authored_ma,
        "pbr_wired_ok": pbr_res.get("ok", False),
        "reference_result_ok": ref_res.get("ok", False),
        "active_object": body.name,
        "anim_layer_count": len(advanced.list_anim_layers(body)),
        "weight_layer_count": len(advanced.list_weight_layers(body)),
        "material_count": len(advanced.list_scene_materials()),
    }


def _composite_and_save(target_png: Path, brain_png: Path) -> list[str]:
    from qtpy import QtCore, QtGui, QtWidgets
    import blendertk as btk
    from blendertk.ui_utils.blender_window import BlenderWindow
    from blendertk.env_utils.script_output import ScriptConsole

    target_png.parent.mkdir(parents=True, exist_ok=True)
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

            so_dock = ScriptConsole.instance()._dock
            if so_dock.docked:
                so_widget, _ = ui.get_panel_widget_and_slots("script_output")
                so_dock._last_rect = None
                so_dock._position(so_dock.content_region())
                so_rect = so_dock._last_rect
                if so_widget is not None and so_rect is not None:
                    bx, by, bw, bh = so_rect
                    painter.drawPixmap(QtCore.QRect(int(bx), int(by), int(bw), int(bh)), so_widget.grab())
                    composited_docks.append("script_output")
        finally:
            painter.end()

        base_pix.save(str(target_png))
        base_pix.save(str(brain_png))
    return composited_docks


def _step_timer():
    global _stage
    try:
        if _stage == 0:
            print("[T08-GUI] Stage 0 start", flush=True)
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
            print("[T08-GUI] Stage 0 done", flush=True)
            _stage = 1
            return 0.50

        if _stage == 1:
            print("[T08-GUI] Stage 1 start (hide native viewport bars + build showcase)", flush=True)
            _hide_native_blender_viewport_bars()
            showcase = _build_phase08_showcase()
            _results["showcase"] = showcase
            ui.cycle_right_dock("CHANNEL_BOX")
            ui.channel_box_ext.refresh_channel_box_extensions()
            # Switch Layer Editor bottom tab to 'Anim' so the Maya AnimLayer stack is visible
            cb_widget, _ = ui.get_panel_widget_and_slots("channels")
            ext = getattr(cb_widget, "_lf_cb_ext_container", None) or ui.channel_box_ext._channel_box_ext_instance
            if ext is not None and hasattr(ext, "set_layer_editor_tab"):
                ext.set_layer_editor_tab("ANIM")
            ui.refresh_hypershade_widgets()
            ui.refresh_interchange_widgets()
            ui.refresh_time_slider_widgets()
            ui.refresh_top_shelf_status()
            ui.outliner.refresh_outliner()
            _frame_viewport_camera()
            print("[T08-GUI] Stage 1 done", flush=True)
            _stage = 2
            return 0.65

        if _stage == 2:
            print("[T08-GUI] Stage 2 capture Maya Channel Box + Anim Layers screenshot", flush=True)
            _hide_native_blender_viewport_bars()
            ui.channel_box_ext.refresh_channel_box_extensions()
            cb_widget, _ = ui.get_panel_widget_and_slots("channels")
            ext = getattr(cb_widget, "_lf_cb_ext_container", None) or ui.channel_box_ext._channel_box_ext_instance
            if ext is not None and hasattr(ext, "set_layer_editor_tab"):
                ext.set_layer_editor_tab("ANIM")
            ui.refresh_time_slider_widgets()
            ui.refresh_top_shelf_status()
            ui.outliner.refresh_outliner()
            _frame_viewport_camera()
            docks_cb = _composite_and_save(CHANNEL_BOX_PNG, BRAIN_CHANNEL_BOX_PNG)
            _results["channel_box_screenshot"] = str(CHANNEL_BOX_PNG)
            _results["channel_box_docks"] = docks_cb
            _results["channels_snapshot"] = ui.get_channels_snapshot()

            # Switch right dock to HYPERSHADE to verify & capture Gate 08 Hypershade panel
            ui.cycle_right_dock("HYPERSHADE")
            ui.refresh_hypershade_widgets()
            _frame_viewport_camera()
            _stage = 3
            return 0.55

        if _stage == 3:
            print("[T08-GUI] Stage 3 capture Hypershade screenshot & finish", flush=True)
            _hide_native_blender_viewport_bars()
            ui.refresh_hypershade_widgets()
            docks_hs = _composite_and_save(HYPERSHADE_PNG, BRAIN_HYPERSHADE_PNG)
            _results["hypershade_screenshot"] = str(HYPERSHADE_PNG)
            _results["hypershade_docks"] = docks_hs
            _results["hypershade_snapshot"] = ui.get_hypershade_ui_snapshot()
            _results["time_slider_snapshot"] = ui.get_time_slider_snapshot()
            _results["hud_state"] = viewport.get_hud_state()
            _results["registry_state"] = ui.get_registry_state()

            ok = (
                CHANNEL_BOX_PNG.is_file()
                and HYPERSHADE_PNG.is_file()
                and len(_results.get("channel_box_docks", [])) >= 4
                and len(docks_hs) >= 4
                and bool(_results["hypershade_snapshot"].get("ok"))
                and _results["hypershade_snapshot"].get("material_count", 0) >= 6
                and len(_results["channels_snapshot"].get("anim_layers", [])) >= 4
                and _results["hud_state"].get("caddy_open") is True
            )
            _results["ok"] = ok
            json_path = ARTIFACT_DIR / "phase08_gui_results.json"
            json_path.write_text(json.dumps(_results, indent=2), encoding="utf-8")
            print("PHASE08_GUI_RESULT:" + json.dumps(_results), flush=True)
            landfall_studio.unregister()
            bpy.ops.wm.quit_blender()
            return None
    except Exception as exc:
        import traceback

        _results["ok"] = False
        _results["error"] = str(exc)
        _results["traceback"] = traceback.format_exc()
        print("PHASE08_GUI_RESULT:" + json.dumps(_results), flush=True)
        bpy.ops.wm.quit_blender()
        return None


if __name__ == "__main__":
    bpy.app.timers.register(_step_timer, first_interval=0.45, persistent=True)
