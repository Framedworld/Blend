"""Gate 06 GUI Verification & Screenshot Suite (`T06-2`):
Verifies the full 5-dock Modern Maya Studio desktop with:
- Docked `Shape / Skin` right sidebar tab (`SHAPE_EDITOR`)
- Top Shelf switched to `Deform & Rigging` shelf tab & `Shape / Skin` workspace button active
- Embedded `BottomTimeSliderQtDock` (`landfall_studio/ui/time_slider.py`) over Blender's `TIMELINE` area displaying custom-painted Maya Time Slider (dark scrub track, frame ticks, red transform key ticks, cyan/emerald morph key ticks, Maya-blue current frame playhead, transport controls, `Set Key [S]`, `Auto Key`) and Maya Range Slider (`1 .. 120`, `24 fps`)
- `Hero_Character_Head` with multi-master shape keys (`Smile`, `Smile_tween_w250`, `Smile_tween_w500`, `Smile_tween_w750`, `BrowUp`) evaluated deterministically at frame 50 (`evaluate_correctives_deterministic`) + locked/unlocked skin influences (`Jaw_Jnt` [LOCKED], `Head_Jnt`, `Neck_Jnt`, `Clavicle.L`, `Clavicle.R`)
- `Hero_Character_Head_Smile_Target` held-reference extracted target mesh (`extract_target_mesh_with_reference`) displayed alongside `Hero_Character_Head` and `Hero_Armature`
- Captures `output/phase06_character_maya_ui_gui.png`.
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

import landfall_studio
from landfall_studio import character, ui, viewport

ARTIFACT_PNG = Path(
    r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output\phase06_character_maya_ui_gui.png"
)
BRAIN_PNG = Path(
    r"C:\Users\mattk\.gemini\antigravity\brain\7b1d9264-a274-459e-8c9a-2432ca72975f\phase06_character_maya_ui_gui.png"
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
                            r3d.view_location = Vector((0.35, 0.0, 0.65))
                            r3d.view_distance = 5.6
                            r3d.view_rotation = Euler((1.12, 0.0, 0.52), "XYZ").to_quaternion()
                for reg in area.regions:
                    reg.tag_redraw()


def _build_character_showcase_scene() -> dict:
    # Clear default cube/light
    for obj in list(bpy.data.objects):
        if obj.type in ("MESH", "LIGHT", "ARMATURE"):
            bpy.data.objects.remove(obj, do_unlink=True)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120
    scene.frame_current = 1

    # 1. Create `Hero_Character_Head` at center-left
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=40, ring_count=24, radius=1.25, location=(-1.15, 0.0, 0.72)
    )
    head = bpy.context.view_layer.objects.active
    head.name = "Hero_Character_Head"
    head.data.name = "Hero_Character_HeadShape"
    bpy.ops.object.shade_smooth()

    # Sculpt subtle facial proportions onto Basis so it reads like a stylized character bust
    for v in head.data.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z
        # Elongate cranium/chin slightly & flatten cheek sides
        v.co.z = z * 1.18
        v.co.x = x * 0.88
        if y < -0.35 and -0.35 < z < 0.35:
            # Nose bridge & brow ridge protrusion
            v.co.y -= 0.14 * max(0.0, 0.45 - abs(x))

    head.data.update()

    mat_skin = bpy.data.materials.new(name="aiStandardCharacterSkin")
    mat_skin.diffuse_color = (0.36, 0.56, 0.78, 1.0)
    head.data.materials.append(mat_skin)
    head.show_wire = True
    head.show_all_edges = True

    # 2. Author primary morph targets `Smile` and `BrowUp` + corrective in-betweens
    character.create_shape_target(head, "Smile", weight=0.0)
    character.create_shape_target(head, "BrowUp", weight=0.0)

    basis_kb = head.data.shape_keys.key_blocks["Basis"]
    smile_kb = head.data.shape_keys.key_blocks["Smile"]
    brow_kb = head.data.shape_keys.key_blocks["BrowUp"]

    for i, b_elem in enumerate(basis_kb.data):
        bx, by, bz = b_elem.co.x, b_elem.co.y, b_elem.co.z
        # Smile lifts corners of mouth/cheeks outward and upward
        if by < -0.15 and bz < 0.25:
            smile_kb.data[i].co = Vector(
                (bx * 1.22, by - 0.12, bz + 0.28 * abs(bx))
            )
        # BrowUp lifts upper forehead/brow arch
        if by < -0.10 and bz > 0.15:
            brow_kb.data[i].co = Vector((bx, by - 0.08, bz + 0.26))

    # Create corrective in-betweens at weights 0.25, 0.50, 0.75 for `Smile`
    for w_val, suffix, boost in [
        (0.25, "w250", 0.06),
        (0.50, "w500", 0.14),
        (0.75, "w750", 0.08),
    ]:
        t_name = f"Smile_tween_{suffix}"
        character.create_shape_target(head, t_name, weight=0.0)
        tkb = head.data.shape_keys.key_blocks[t_name]
        for i, b_elem in enumerate(basis_kb.data):
            s_co = Vector(smile_kb.data[i].co)
            b_co = Vector(b_elem.co)
            lerp_co = b_co.lerp(s_co, w_val)
            if b_co.y < -0.20:
                lerp_co.z += boost * abs(b_co.x)
            tkb.data[i].co = lerp_co

    # Keyframe `Smile` and `BrowUp` across frames 1, 25, 50, 75, 100 + transform keys at 1, 40, 80, 110
    for f_no, s_val, b_val in [
        (1, 0.0, 0.0),
        (25, 0.25, 0.35),
        (50, 0.50, 0.75),
        (75, 0.75, 0.45),
        (100, 1.0, 0.90),
    ]:
        character.keyframe_shape_target(head, "Smile", frame=f_no, weight=s_val)
        character.keyframe_shape_target(head, "BrowUp", frame=f_no, weight=b_val)

    for f_no in (1, 40, 80, 110):
        scene.frame_set(f_no)
        head.keyframe_insert(data_path="location", frame=f_no)
        head.keyframe_insert(data_path="rotation_euler", frame=f_no)

    # 3. Extract Held-Reference Target Mesh for `Smile` (`Hero_Character_Head_Smile_Target`)
    ext_res = character.extract_target_mesh_with_reference(
        head, "Smile", offset_vector=(2.65, 0.0, 0.0)
    )
    target_obj = bpy.data.objects.get(ext_res["extracted_object"])
    if target_obj is not None:
        mat_tgt = bpy.data.materials.new(name="aiExtractedMorphTarget")
        mat_tgt.diffuse_color = (0.18, 0.76, 0.64, 1.0)
        target_obj.data.materials.clear()
        target_obj.data.materials.append(mat_tgt)
        target_obj.show_wire = True
        target_obj.show_all_edges = True

    # 4. Create `Hero_Armature` + skin weight groups (`Jaw_Jnt` [LOCKED], `Head_Jnt`, `Neck_Jnt`, `Clavicle.L`, `Clavicle.R`)
    arm_data = bpy.data.armatures.new("Hero_ArmatureShape")
    arm_obj = bpy.data.objects.new("Hero_Armature", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    arm_obj.location = (-1.15, 0.0, 0.0)

    # Author skin weights on `Hero_Character_Head` and lock `Jaw_Jnt`
    arm_mod = head.modifiers.new(name="SkinCluster1", type="ARMATURE")
    arm_mod.object = arm_obj
    vg_jaw = head.vertex_groups.new(name="Jaw_Jnt")
    vg_head = head.vertex_groups.new(name="Head_Jnt")
    vg_neck = head.vertex_groups.new(name="Neck_Jnt")
    vg_clav_l = head.vertex_groups.new(name="Clavicle.L")
    vg_clav_r = head.vertex_groups.new(name="Clavicle.R")

    for v in head.data.vertices:
        z_val = v.co.z
        x_val = v.co.x
        w_jaw = max(0.05, min(0.55, 0.35 - 0.25 * z_val))
        rem = 1.0 - w_jaw
        w_head = rem * 0.62
        w_neck = rem * 0.22
        w_side = rem * 0.16
        vg_jaw.add([v.index], w_jaw, "REPLACE")
        vg_head.add([v.index], w_head, "REPLACE")
        vg_neck.add([v.index], w_neck, "REPLACE")
        if x_val >= 0.0:
            vg_clav_l.add([v.index], w_side, "REPLACE")
        else:
            vg_clav_r.add([v.index], w_side, "REPLACE")

    character.set_vertex_group_lock(head, "Jaw_Jnt", True)
    norm_res = character.normalize_skin_weights(head)

    # Make `Hero_Character_Head` active and scrub to frame 50 so `Smile_tween_w500` evaluates at 1.0
    bpy.ops.object.select_all(action="DESELECT")
    head.select_set(True)
    bpy.context.view_layer.objects.active = head
    head.active_shape_key_index = head.data.shape_keys.key_blocks.find("Smile")

    character.register_handlers()
    scene.frame_set(50)
    eval_res = character.evaluate_correctives_deterministic(head)
    skin_rep = character.inspect_skin_weights(head)

    return {
        "head_object": head.name,
        "extracted_target": ext_res,
        "deterministic_eval_frame_50": eval_res,
        "normalize_skin": norm_res,
        "skin_inspection": {
            "group_count": skin_rep["group_count"],
            "locked_groups": skin_rep["locked_groups"],
            "unnormalized_vertex_count": skin_rep["unnormalized_vertex_count"],
        },
    }


def _step_timer():
    global _stage
    try:
        if _stage == 0:
            print("[T06-2] Stage 0 start", flush=True)
            bpy.context.preferences.view.show_splash = False
            bpy.ops.wm.read_homefile()
            _maximize_and_bring_to_front()
            landfall_studio.register()
            desk = ui.restore_workspace_desktop(
                dock_channels=True,
                restore_script_output=True,
                dock_shelf=True,
                dock_outliner=True,
                dock_time_slider_bar=True,
                apply_theme=True,
            )
            _results["desktop_restore"] = desk
            print("[T06-2] Stage 0 done", flush=True)
            _stage = 1
            return 0.45

        if _stage == 1:
            print("[T06-2] Stage 1 start", flush=True)
            showcase = _build_character_showcase_scene()
            _results["showcase"] = showcase
            print("[T06-2] Stage 1 scene built", flush=True)
            # Switch Right Dock to Shape / Skin (`SHAPE_EDITOR`)
            cyc = ui.cycle_right_dock("SHAPE_EDITOR")
            # Switch Top Shelf to `Deform & Rigging` tab (index 4)
            sdock = ui.desktop._get_top_shelf_dock()
            if sdock._shelf_ctrl is not None:
                sdock._shelf_ctrl.tabs.setCurrentIndex(4)

            ui.refresh_shape_editor_widgets()
            ui.refresh_time_slider_widgets()
            ui.refresh_top_shelf_status()
            ui.outliner.refresh_outliner()
            _frame_viewport_camera()
            _results["right_dock_cycle"] = cyc
            print("[T06-2] Stage 1 done", flush=True)
            _stage = 2
            return 0.55

        if _stage == 2:
            print("[T06-2] Stage 2 start", flush=True)
            # Select `Smile` in the Shape Editor widget & `Jaw_Jnt` in the skin table so full inspector state is visible
            w_list = getattr(ui.shape_editor, "_active_se_widgets", [])
            if w_list:
                w = w_list[-1]
                w.refresh_from_scene()
                if w._shape_table.rowCount() > 1:
                    w._shape_table.selectRow(1)
                if w._skin_table.rowCount() > 0:
                    w._skin_table.selectRow(0)

            ui.refresh_time_slider_widgets()
            ui.refresh_top_shelf_status()
            _frame_viewport_camera()
            _results["shape_editor_snapshot"] = ui.get_shape_editor_snapshot()
            _results["time_slider_snapshot"] = ui.get_time_slider_snapshot()
            _results["hud_state"] = viewport.get_hud_state()
            _results["registry_state"] = ui.get_registry_state()
            print("[T06-2] Stage 2 done", flush=True)
            _stage = 3
            return 0.55

        if _stage == 3:
            print("[T06-2] Stage 3 start", flush=True)
            from qtpy import QtCore, QtGui, QtWidgets
            import blendertk as btk
            from blendertk.ui_utils.blender_window import BlenderWindow
            from blendertk.env_utils.script_output import ScriptConsole

            ARTIFACT_PNG.parent.mkdir(parents=True, exist_ok=True)
            BRAIN_PNG.parent.mkdir(parents=True, exist_ok=True)

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
                bpy.ops.screen.screenshot(filepath=str(ARTIFACT_PNG))
            print("[T06-2] Screenshot captured", flush=True)

            composited_docks = []
            try:
                base_pix = QtGui.QPixmap(str(ARTIFACT_PNG))
                if not base_pix.isNull():
                    painter = QtGui.QPainter(base_pix)
                    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

                    try:
                        # 1. Top Shelf (Status Line with Shape / Skin active + Deform & Rigging Shelf Tab)
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

                        # 3. Right Sidebar (Shape / Skin tab active)
                        rdock = ui.desktop._get_right_dock()
                        r_rect = rdock.enforce_dock_geometry() or rdock._inner_dock._last_rect
                        if rdock.host_widget is not None and r_rect is not None:
                            rx, ry, rw, rh = r_rect
                            rdock.host_widget.resize(int(rw), int(rh))
                            if app is not None:
                                app.processEvents()
                            r_pix = rdock.host_widget.grab()
                            painter.drawPixmap(QtCore.QRect(int(rx), int(ry), int(lw if rw <= 0 else rw), int(rh)), r_pix)
                            composited_docks.append("right_sidebar")

                        # 4. Bottom Maya Time Slider + Range Slider
                        tdock = ui.time_slider.get_bottom_time_slider_dock()
                        t_rect = tdock.enforce_dock_geometry() or tdock._inner_dock._last_rect
                        if tdock.widget is not None and t_rect is not None:
                            tx, ty, tw, th = t_rect
                            tdock.widget.resize(int(tw), int(th))
                            if app is not None:
                                app.processEvents()
                            t_pix = tdock.widget.grab()
                            painter.drawPixmap(QtCore.QRect(int(tx), int(ty), int(tw), int(th)), t_pix)
                            composited_docks.append("time_slider")

                        # 5. Bottom Script Output / Command Line
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
                    finally:
                        painter.end()

                    base_pix.save(str(ARTIFACT_PNG))
                    base_pix.save(str(BRAIN_PNG))
            except Exception as comp_exc:
                print(f"[T06-2 composite warning] {comp_exc}", flush=True)

            captured = ARTIFACT_PNG.is_file()
            _results["screenshot_saved"] = captured
            _results["screenshot_path"] = str(ARTIFACT_PNG)
            _results["composited_docks"] = composited_docks

            # Verify key assertions
            reg = _results["registry_state"]
            se = _results["shape_editor_snapshot"]
            ts = _results["time_slider_snapshot"]
            ok = (
                bool(reg.get("top_shelf_docked"))
                and bool(reg.get("left_outliner_docked"))
                and bool(reg.get("time_slider_docked"))
                and reg.get("right_dock_mode") == "SHAPE_EDITOR"
                and bool(se.get("ok"))
                and se.get("shape_row_count", 0) >= 5
                and se.get("skin_row_count", 0) == 5
                and bool(ts.get("ok"))
                and ts.get("frame_current") == 50
                and len(ts.get("shape_key_frames", [])) >= 5
                and len(composited_docks) == 5
                and captured
            )
            _results["ok"] = ok
            json_path = ARTIFACT_PNG.parent / "phase06_gui_results.json"
            json_path.write_text(json.dumps(_results, indent=2), encoding="utf-8")
            print("PHASE06_GUI_RESULT:" + json.dumps(_results), flush=True)
            landfall_studio.unregister()
            bpy.ops.wm.quit_blender()
            return None
    except Exception as exc:
        import traceback

        _results["ok"] = False
        _results["error"] = str(exc)
        _results["traceback"] = traceback.format_exc()
        print("PHASE06_GUI_RESULT:" + json.dumps(_results))
        bpy.ops.wm.quit_blender()
        return None


if __name__ == "__main__":
    bpy.app.timers.register(_step_timer, first_interval=0.4, persistent=True)
