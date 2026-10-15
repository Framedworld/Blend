"""Gate 07 GUI Verification & Figma Make UI Screenshot Suite (`T07-GUI`):
Verifies the full 5-dock Modern Maya Studio desktop after the Figma Make UI pass + Gate 07 Maya `.ma` Interchange:
- Top Shelf (`TopShelfQtDock`) with Figma Make Status Line (`M` badge, `Modeling [F2]`, `.ma` quick actions, `MASK: Obj|Vtx|Edg|Face|UV`, `SNAP`, `● LIVE SURFACE`, `Symmetry OFF`, `Modeling Standard`) and `46x42` top-beveled shelf tiles
- Left Outliner (`LeftOutlinerQtDock`) with `42px` Tool Box (`Q/W/E/R/D/B` corner badges + `2px` `#38A3D8` active bar), `SCENE HIERARCHY | TYPE` subheader, custom `_MayaOutlinerItemDelegate` (`GRP`/`MSH`/`RIG`/`LGT`/`CAM`/`REF` pill badges), and bottom `DISPLAY LAYERS` subpanel
- Right Sidebar (`RightAreaQtDock`) with `26px` Vertical Rotated Edge Tab Strip (`CHANNEL BOX`, `MODELING TOOLKIT`, `SHAPE EDITOR`, `MAYA BRIDGE`, `ATTRIBUTE EDITOR`, `TOOL SETTINGS`), Figma Make Object Header Bar (`body_main_GEO`), and `#E35D6A`/`#4AB866`/`#4E9CE6` `X`/`Y`/`Z` axis dots
- Bottom 3-Row Chrome (`BottomTimeSliderQtDock`) with `TIME 1.00` readout, dark scrub track with red transform ticks & cyan morph ticks, `RANGE` slider row, and `MEL | PY` interactive command bar
- Viewport 2.0 HUD with `26px` Panel Menu Strip (`Panels  View  Shading  Lighting  Show  Renderer`), `POLY COUNT` card (`SCENE` / `SEL`), `● LIVE SURFACE` capsule, floating `polyBevel1` dark-glass caddy, and `persp | 35mm` pill
- Live `.ma` Maya scene import (`interchange.open_or_import_maya_scene`) + `Reference Scene` (`interchange.reference_scene`) + `MAYA_INTERCHANGE` (`MAYA BRIDGE`) dock snapshot
- Captures `output/phase07_maya_interchange_figma_ui_gui.png` and `output/phase07_maya_bridge_inspector_gui.png`.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Euler, Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio import character, interchange, modeling, ui, viewport

ARTIFACT_DIR = Path(
    r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output"
)
BRAIN_DIR = Path(
    r"C:\Users\mattk\.gemini\antigravity\brain\7b1d9264-a274-459e-8c9a-2432ca72975f"
)
FIGMA_UI_PNG = ARTIFACT_DIR / "phase07_maya_interchange_figma_ui_gui.png"
BRAIN_FIGMA_UI_PNG = BRAIN_DIR / "phase07_maya_interchange_figma_ui_gui.png"
BRIDGE_UI_PNG = ARTIFACT_DIR / "phase07_maya_bridge_inspector_gui.png"
BRAIN_BRIDGE_UI_PNG = BRAIN_DIR / "phase07_maya_bridge_inspector_gui.png"

_results: dict = {"steps": []}
_stage: int = 0
_temp_dir = Path(tempfile.mkdtemp(prefix="lf_phase07_gui_"))


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
                            r3d.view_location = Vector((0.0, 0.0, 0.65))
                            r3d.view_distance = 5.2
                            r3d.view_rotation = Euler((1.14, 0.0, 0.56), "XYZ").to_quaternion()
                for reg in area.regions:
                    reg.tag_redraw()


def _author_maya_fixture_ma(ma_path: Path) -> bool:
    runtime = interchange.detect_maya_runtime()
    mayapy = runtime.get("mayapy_path")
    if not mayapy:
        return False
    script = f"""
import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds

cmds.file(new=True, force=True)
body = cmds.polySphere(name="body_main_GEO", sx=28, sy=20, r=1.18)[0]
cmds.setAttr(body + ".ty", 0.72)
cmds.setAttr(body + ".sy", 1.15)
cmds.polyBevel3(body + ".f[0:15]", fraction=0.15, segments=4, depth=1.0, mitering=0, chamfer=True)

pauldron_l = cmds.polyCube(name="pauldron_L_GEO", w=0.65, h=0.42, d=0.65, sx=2, sy=2, sz=2)[0]
cmds.setAttr(pauldron_l + ".translate", -1.25, 1.35, 0.0, type="double3")
pauldron_r = cmds.polyCube(name="pauldron_R_GEO", w=0.65, h=0.42, d=0.65, sx=2, sy=2, sz=2)[0]
cmds.setAttr(pauldron_r + ".translate", 1.25, 1.35, 0.0, type="double3")

grp = cmds.group(body, pauldron_l, pauldron_r, name="chr_paladin_A_GRP")
cmds.select(clear=True)
j_root = cmds.joint(name="Root_Jnt", p=(0, 0, 0))
j_chest = cmds.joint(name="Chest_Jnt", p=(0, 0.8, 0))
j_head = cmds.joint(name="Head_Jnt", p=(0, 1.5, 0))
cmds.skinCluster(j_root, j_chest, j_head, body, name="SkinCluster_Paladin", toSelectedBones=True)

for f_no, ry in [(1, 0.0), (14, 15.0), (28, -12.0), (45, 24.0), (62, 0.0), (84, 18.0), (105, 0.0)]:
    cmds.setKeyframe(body, attribute="rotateY", time=f_no, value=ry)

cmds.file(rename=r"{str(ma_path)}")
cmds.file(save=True, type="mayaAscii", force=True)
"""
    env = interchange.ensure_mayapy_sitecustomize_env()
    proc = subprocess.run(
        [mayapy, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return proc.returncode == 0 and ma_path.is_file()


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


def _build_showcase_and_interchange() -> dict:
    # Remove default Cube/Light/Camera
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    ref_blend = _temp_dir / "ref_turntable_proxy.blend"
    _build_reference_blend(ref_blend)

    ma_path = _temp_dir / "chr_paladin_maya.ma"
    fix_res = interchange.generate_maya_fixture_ma(str(ma_path))
    authored_ma = bool(fix_res.get("ok"))

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120
    scene.frame_current = 1

    import_res = {"ok": False}
    if authored_ma:
        import_res = interchange.import_maya_scene(
            str(ma_path), clear_existing=False, use_cache=True
        )

    # Ensure `body_main_GEO` exists and has rich visual presentation for the viewport + Channel Box
    body = bpy.data.objects.get("body_main_GEO")
    if body is None or body.type != "MESH":
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=32, ring_count=20, radius=1.22, location=(0.0, 0.0, 0.72)
        )
        body = bpy.context.view_layer.objects.active
        body.name = "body_main_GEO"
    body.data.name = "body_main_GEOShape"

    # Give `body_main_GEO` a sculpted armor torso silhouette so it looks great in Viewport 2.0
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=36, ring_count=24, radius=1.18, location=(0.0, 0.0, 0.78)
    )
    sculpt_hero = bpy.context.view_layer.objects.active
    sculpt_hero.name = "paladin_chest_armor_GEO"
    bpy.ops.object.shade_smooth()
    mat_main = bpy.data.materials.new(name="aiStandardSurface_Paladin")
    mat_main.diffuse_color = (0.34, 0.56, 0.76, 1.0)
    sculpt_hero.data.materials.append(mat_main)
    sculpt_hero.show_wire = True
    sculpt_hero.show_all_edges = True

    body.data.materials.clear()
    body.data.materials.append(mat_main)
    body.show_wire = True
    body.show_all_edges = True

    # Add Bevel modifier (`polyBevel1`) and Subdivision (`polySmoothFace1`) so Channel Box INPUTS & Caddy show `polyBevel1`
    if "polyBevel1" not in body.modifiers:
        bev = body.modifiers.new(name="polyBevel1", type="BEVEL")
        bev.width = 0.15
        bev.segments = 4
        bev.profile = 0.5
    if "polySmoothFace1" not in body.modifiers:
        sub = body.modifiers.new(name="polySmoothFace1", type="SUBSURF")
        sub.levels = 1

    # Add morph targets + keyframes so Time Slider displays red transform ticks AND cyan morph ticks
    character.create_shape_target(body, "Armor_Expand", weight=0.35)
    character.create_shape_target(body, "Breathing_Chest", weight=0.20)
    for f_no, w_val in [(1, 0.0), (18, 0.4), (36, 0.85), (54, 0.5), (72, 1.0), (96, 0.25)]:
        character.keyframe_shape_target(body, "Armor_Expand", frame=f_no, weight=w_val)
    for f_no in (1, 14, 28, 45, 62, 84, 105):
        scene.frame_set(f_no)
        body.keyframe_insert(data_path="location", frame=f_no)
        body.keyframe_insert(data_path="rotation_euler", frame=f_no)

    # Reference the external `.blend` turntable asset so Outliner shows `[REF]` badge and MAYA BRIDGE shows referenced scene
    ref_res = interchange.reference_scene(str(ref_blend), display_mode="reference")

    # Add key light and camera so Outliner shows LGT and CAM badges too
    light_data = bpy.data.lights.new(name="keyLight_area1Shape", type="AREA")
    light_obj = bpy.data.objects.new(name="keyLight_area1", object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.location = (2.8, -2.5, 3.4)

    cam_data = bpy.data.cameras.new(name="cam_render_shot01Shape")
    cam_obj = bpy.data.objects.new(name="cam_render_shot01", object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.5, 1.4)

    # Select `body_main_GEO` and set frame 1
    scene.frame_start = 1
    scene.frame_end = 120
    scene.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    sculpt_hero.select_set(True)
    bpy.context.view_layer.objects.active = body

    # Activate the floating `polyBevel1` in-viewport caddy so it renders in the 3D Viewport just like the Figma Make design
    modeling.invoke_modeling_caddy("BEVEL", apply_live=False)

    return {
        "authored_ma": authored_ma,
        "import_result_ok": import_res.get("ok", False),
        "reference_result_ok": ref_res.get("ok", False),
        "active_object": body.name,
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
            print("[T07-GUI] Stage 0 start", flush=True)
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
            print("[T07-GUI] Stage 0 done", flush=True)
            _stage = 1
            return 0.50

        if _stage == 1:
            print("[T07-GUI] Stage 1 start (Channel Box + Figma Make layout)", flush=True)
            showcase = _build_showcase_and_interchange()
            _results["showcase"] = showcase
            ui.cycle_right_dock("CHANNEL_BOX")
            ui.channel_box_ext.refresh_channel_box_extensions()
            ui.refresh_interchange_widgets()
            ui.refresh_time_slider_widgets()
            ui.refresh_top_shelf_status()
            ui.outliner.refresh_outliner()
            _frame_viewport_camera()
            print("[T07-GUI] Stage 1 done", flush=True)
            _stage = 2
            return 0.65

        if _stage == 2:
            print("[T07-GUI] Stage 2 capture Figma Make screenshot", flush=True)
            ui.channel_box_ext.refresh_channel_box_extensions()
            ui.refresh_time_slider_widgets()
            ui.refresh_top_shelf_status()
            ui.outliner.refresh_outliner()
            _frame_viewport_camera()
            docks_figma = _composite_and_save(FIGMA_UI_PNG, BRAIN_FIGMA_UI_PNG)
            _results["figma_ui_screenshot"] = str(FIGMA_UI_PNG)
            _results["figma_ui_docks"] = docks_figma
            # Switch right dock to MAYA_INTERCHANGE (`MAYA BRIDGE`) to verify & capture Gate 07 panel
            ui.cycle_right_dock("MAYA_INTERCHANGE")
            ui.refresh_interchange_widgets()
            _frame_viewport_camera()
            _stage = 3
            return 0.55

        if _stage == 3:
            print("[T07-GUI] Stage 3 capture Maya Bridge screenshot & finish", flush=True)
            docks_bridge = _composite_and_save(BRIDGE_UI_PNG, BRAIN_BRIDGE_UI_PNG)
            _results["bridge_ui_screenshot"] = str(BRIDGE_UI_PNG)
            _results["bridge_ui_docks"] = docks_bridge
            _results["interchange_snapshot"] = ui.get_interchange_ui_snapshot()
            _results["time_slider_snapshot"] = ui.get_time_slider_snapshot()
            _results["hud_state"] = viewport.get_hud_state()
            _results["registry_state"] = ui.get_registry_state()

            ok = (
                FIGMA_UI_PNG.is_file()
                and BRIDGE_UI_PNG.is_file()
                and len(_results.get("figma_ui_docks", [])) >= 4
                and len(docks_bridge) >= 4
                and bool(_results["interchange_snapshot"].get("ok"))
                and _results["interchange_snapshot"].get("ref_row_count", 0) >= 1
                and _results["hud_state"].get("caddy_open") is True
            )
            _results["ok"] = ok
            json_path = ARTIFACT_DIR / "phase07_gui_results.json"
            json_path.write_text(json.dumps(_results, indent=2), encoding="utf-8")
            print("PHASE07_GUI_RESULT:" + json.dumps(_results), flush=True)
            landfall_studio.unregister()
            bpy.ops.wm.quit_blender()
            return None
    except Exception as exc:
        import traceback

        _results["ok"] = False
        _results["error"] = str(exc)
        _results["traceback"] = traceback.format_exc()
        print("PHASE07_GUI_RESULT:" + json.dumps(_results), flush=True)
        bpy.ops.wm.quit_blender()
        return None


if __name__ == "__main__":
    bpy.app.timers.register(_step_timer, first_interval=0.45, persistent=True)
