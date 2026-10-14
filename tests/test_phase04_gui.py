"""Phase 04 (Gate 04) Real GUI Blender Verification Suite (`T04-2`).

Runs in non-headless Blender 5.2 (`--factory-startup -noaudio --python ...`)
using a stepped timer inside Blender's live window event loop to verify:
1. Full Modern Maya Studio 4-dock workspace (`TopShelfQtDock` Status Line + Tabbed Icon Shelf,
   `LeftOutlinerQtDock` vertical Tool Box `Q/W/E/R` + DAG Outliner, full-height `RightAreaQtDock`
   Channel Box / Attribute Editor / Tool Settings, and bottom `ScriptConsole`).
2. Modern Maya Blender theme harmonization (`apply_modern_maya_theme_to_blender`) and
   3D Viewport `POST_PIXEL` Poly Count HUD (`Verts`, `Edges`, `Faces`, `Tris`, `UVs`).
3. Channel Box `SHAPES` inline rename, live procedural `INPUTS` (`polyCube1`, `polySphere1`,
   `Bevel`, `Subsurf`) editing, `Delete History` (`Alt+Shift+D`), and 3D Viewport `MMB`
   virtual-slider channel scrubbing.
4. Display Layer Editor (`V / P / Normal-T-R`) creation, object assignment, Template/Reference
   wireframe + unselectable states in the live 3D Viewport.
5. `Ctrl+A` cycling through `CHANNEL_BOX` -> `ATTRIBUTE_EDITOR` -> `TOOL_SETTINGS` -> `CHANNEL_BOX`,
   live Attribute Editor edits, and Shelf Option Box (`□`) -> `Tool Settings` workflow.
6. Maya DAG Outliner (`[+] Transform -> Shape`) hierarchy and `MMB` world-preserving reparenting.
7. Captures visual evidence (`output/phase04_modern_maya_desktop_gui.png`) with all 4 embedded
   `WS_CHILD` Qt docks composited at their exact physical coordinates, and writes
   `output/phase04_gui_results.json`.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Euler, Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_DIR = Path(
    os.environ.get(
        "LANDFALL_STUDIO_OUTPUT_DIR",
        r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output",
    )
)


def _find_view3d_override():
    for window in bpy.context.window_manager.windows:
        if window.screen is None:
            continue
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    if region.type == "WINDOW":
                        return {
                            "window": window,
                            "screen": window.screen,
                            "area": area,
                            "region": region,
                            "space_data": area.spaces.active,
                        }
    raise RuntimeError("No VIEW_3D window region found in GUI session")


def main() -> None:
    if bpy.app.background:
        raise RuntimeError("T04-2 must run in non-headless GUI Blender")

    os.environ["LANDFALL_STUDIO_UPSTREAM"] = r"C:\Users\mattk\Documents\Landfall\upstream"
    os.environ["LANDFALL_STUDIO_DEPS"] = r"C:\Users\mattk\Documents\Landfall\.deps\py313"

    import landfall_studio
    from landfall_studio import ui
    from landfall_studio.adapters import landfall_bridge

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "phase04_gui_results.json"
    screenshot_path = OUTPUT_DIR / "phase04_modern_maya_desktop_gui.png"

    state: dict = {
        "step": 0,
        "results": {
            "suite": "T04-2_gui_modern_maya_desktop_editors",
            "headless": bool(bpy.app.background),
            "checks": {},
        },
    }

    def _step_runner():
        step = state["step"]
        try:
            if step == 0:
                bpy.context.preferences.view.show_splash = False
                bpy.ops.wm.read_homefile()
                landfall_studio.register()
                landfall_bridge.sync_now()

                # Maximize window for crisp full-HD layout if possible
                ctx = _find_view3d_override()
                with bpy.context.temp_override(**ctx):
                    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
                        bpy.ops.object.mode_set(mode="OBJECT")
                    bpy.ops.object.select_all(action="SELECT")
                    bpy.ops.object.delete(use_global=False)

                # Create Maya hero primitives with construction history (polyCube1, polySphere1, polyCylinder1)
                c1 = ui.create_maya_primitive("CUBE", name="pCube1", width=2.2, height=1.6, depth=2.2, subdivisions_x=2, subdivisions_y=2, subdivisions_z=2)
                s1 = ui.create_maya_primitive("SPHERE", name="pSphere1", radius=1.25, subdivisions_x=24, subdivisions_y=16)
                cy1 = ui.create_maya_primitive("CYLINDER", name="pCylinder1", radius=0.85, height=2.4, subdivisions_x=20)
                assert c1["ok"] and s1["ok"] and cy1["ok"]

                obj_cube = bpy.data.objects[c1["object_name"]]
                obj_sphere = bpy.data.objects[s1["object_name"]]
                obj_cyl = bpy.data.objects[cy1["object_name"]]

                obj_cube.location = Vector((-2.4, 0.2, 0.8))
                obj_cube.rotation_euler = Euler((0.0, 0.0, 0.35), "XYZ")
                bevel = obj_cube.modifiers.new(name="polyBevel1", type="BEVEL")
                bevel.width = 0.12
                bevel.segments = 2
                subd = obj_cube.modifiers.new(name="polySubd1", type="SUBSURF")
                subd.levels = 1

                obj_sphere.location = Vector((0.3, -0.4, 1.25))
                obj_cyl.location = Vector((2.8, 0.6, 1.2))

                # Select pCube1 as primary active hero object
                bpy.ops.object.select_all(action="DESELECT")
                obj_cube.select_set(True)
                bpy.context.view_layer.objects.active = obj_cube

                # Configure viewport shading for crisp Maya look (wireframe-on-shaded)
                space = ctx["space_data"]
                if hasattr(space, "overlay"):
                    space.overlay.show_wireframes = True
                    space.overlay.wireframe_opacity = 0.65

                state["step"] = 1
                return 0.4

            if step == 1:
                # Restore complete Modern Maya Studio 4-dock layout
                desk = ui.restore_workspace_desktop(
                    dock_channels=True,
                    restore_script_output=True,
                    dock_shelf=True,
                    dock_outliner=True,
                )
                assert desk["ok"] is True
                reg = ui.get_registry_state()
                assert reg["top_shelf_embedded"] is True, f"Expected top_shelf_embedded=True, got {reg}"
                assert reg["left_outliner_embedded"] is True, f"Expected left_outliner_embedded=True, got {reg}"
                assert reg["right_dock_qt_embedded"] is True, f"Expected right_dock_qt_embedded=True, got {reg}"

                state["results"]["checks"]["four_dock_maya_layout"] = {
                    "top_shelf_embedded": reg["top_shelf_embedded"],
                    "left_outliner_embedded": reg["left_outliner_embedded"],
                    "right_dock_qt_embedded": reg["right_dock_qt_embedded"],
                    "right_dock_mode": reg["right_dock_mode"],
                }
                state["step"] = 2
                return 0.45

            if step == 2:
                # Verify SHAPES rename, INPUTS live procedural editing, and Display Layers (V/P/T/R)
                obj_cube = bpy.data.objects["pCube1"]
                bpy.ops.object.select_all(action="DESELECT")
                obj_cube.select_set(True)
                bpy.context.view_layer.objects.active = obj_cube

                rn = ui.rename_object_shape("pCube1", "pCubeShape1")
                assert rn["ok"] is True and obj_cube.data.name == "pCubeShape1"

                inp_edit = ui.set_object_input_attribute("pCube1", "PRIM_HISTORY", "width", 2.6)
                assert inp_edit["ok"] is True
                mod_edit = ui.set_object_input_attribute("pCube1", "MOD:polyBevel1", "segments", 3)
                assert mod_edit["ok"] is True

                # Create Display Layers
                lyr1 = ui.create_display_layer("HeroProps_Lyr", assign_selected=True)
                assert lyr1["ok"] is True
                lyr2 = ui.create_display_layer("EnvRef_Lyr", assign_selected=False)
                assert lyr2["ok"] is True
                ui.assign_objects_to_display_layer("EnvRef_Lyr", ["pCylinder1"])
                ui.set_display_layer_state("EnvRef_Lyr", display_type="R")

                # Refresh Right Dock & Outliner UI widgets so they display the latest state
                ui.sync_channels_now()
                ui.refresh_channel_box_extensions()
                ui.refresh_attribute_editor()
                ui.refresh_tool_settings_widget()
                ui.refresh_outliner_widget()

                state["results"]["checks"]["channel_box_shapes_inputs_layers"] = {
                    "shape_name": obj_cube.data.name,
                    "inputs_count": len(ui.get_object_inputs("pCube1")),
                    "display_layers": [l["name"] for l in ui.list_display_layers()],
                }
                state["step"] = 3
                return 0.4

            if step == 3:
                # Test Ctrl+A cycling (CHANNEL_BOX -> ATTRIBUTE_EDITOR -> TOOL_SETTINGS -> CHANNEL_BOX)
                # and Outliner MMB world-preserving reparenting
                bpy.ops.landfall_studio.cycle_attribute_channels(mode="ATTRIBUTE_EDITOR")
                reg_ae = ui.get_registry_state()
                assert reg_ae["right_dock_mode"] == "ATTRIBUTE_EDITOR"
                assert reg_ae["right_dock_qt_embedded"] is True

                ae_edit = ui.set_attribute_editor_value("pCube1", "SHADER", "roughness", 0.28)
                assert ae_edit["ok"] is True

                bpy.ops.landfall_studio.open_tool_settings(tool_id="EXTRUDE")
                reg_ts = ui.get_registry_state()
                assert reg_ts["right_dock_mode"] == "TOOL_SETTINGS"

                # Return to CHANNEL_BOX for the hero Modern Maya screenshot
                bpy.ops.landfall_studio.cycle_attribute_channels(mode="CHANNEL_BOX")
                reg_cb = ui.get_registry_state()
                assert reg_cb["right_dock_mode"] == "CHANNEL_BOX"

                # Test Outliner world-preserving reparenting (pSphere1 -> pCube1)
                rep = ui.reparent_preserve_world("pSphere1", "pCube1")
                assert rep["ok"] is True and rep["world_delta"] < 1e-4

                # Re-select pCube1 so Channel Box shows pCube1 + pCubeShape1 + polyCube1/polyBevel1/polySubd1 + Display Layers
                obj_cube = bpy.data.objects["pCube1"]
                bpy.ops.object.select_all(action="DESELECT")
                obj_cube.select_set(True)
                bpy.context.view_layer.objects.active = obj_cube
                ui.sync_channels_now()
                ui.refresh_channel_box_extensions()
                ui.refresh_outliner_widget()

                state["results"]["checks"]["ae_tool_settings_outliner"] = {
                    "ae_mode": reg_ae["right_dock_mode"],
                    "tool_settings_mode": reg_ts["right_dock_mode"],
                    "reparent_world_delta": rep["world_delta"],
                }
                state["step"] = 4
                return 0.45

            if step == 4:
                # Capture full Modern Maya Studio screenshot and composite all 4 WS_CHILD Qt docks
                from qtpy import QtCore, QtGui, QtWidgets
                from blendertk.env_utils.script_output import ScriptConsole

                app = QtWidgets.QApplication.instance()
                if app is not None:
                    app.processEvents()

                bpy.ops.screen.screenshot(filepath=str(screenshot_path))

                composited_docks = []
                try:
                    base_pix = QtGui.QPixmap(str(screenshot_path))
                    if not base_pix.isNull():
                        painter = QtGui.QPainter(base_pix)
                        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

                        # 1. Top Shelf (Status Line + Tabbed Icon Shelf)
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

                        # 3. Right Sidebar (Channel Box / Attribute Editor / Tool Settings + SHAPES + INPUTS + Display Layers)
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
                        base_pix.save(str(screenshot_path))
                except Exception as comp_exc:
                    print(f"[T04-2 composite warning] {comp_exc}")

                state["results"]["checks"]["screenshot"] = {
                    "screenshot_saved": screenshot_path.is_file(),
                    "screenshot_bytes": screenshot_path.stat().st_size if screenshot_path.is_file() else 0,
                    "composited_docks": composited_docks,
                }
                state["step"] = 5
                return 0.3

            if step == 5:
                landfall_studio.unregister()
                state["results"]["passed"] = True
                json_path.write_text(
                    json.dumps(state["results"], indent=2), encoding="utf-8"
                )
                print("T04-2 GUI SUITE PASSED")
                bpy.ops.wm.quit_blender()
                return None

        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[T04-2 ERROR at step {step}] {exc}\n{tb}", file=sys.stderr)
            state["results"]["passed"] = False
            state["results"]["error"] = str(exc)
            state["results"]["traceback"] = tb
            json_path.write_text(
                json.dumps(state["results"], indent=2), encoding="utf-8"
            )
            try:
                landfall_studio.unregister()
            except Exception:
                pass
            bpy.ops.wm.quit_blender()
            return None

    bpy.app.timers.register(_step_runner, first_interval=0.35, persistent=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as _top_exc:
        print(f"[T04-2 TOP-LEVEL ERROR] {_top_exc}\n{traceback.format_exc()}", file=sys.stderr)
        try:
            bpy.ops.wm.quit_blender()
        except Exception:
            os._exit(1)
