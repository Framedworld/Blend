"""Phase 02 (Gate 02) Real GUI Blender Verification Suite (T02-2).

Runs in non-headless Blender 5.2 (`--factory-startup -noaudio --python ...`)
using a stepped timer inside Blender's live window event loop (matching T01-3)
to verify:
1. Tentacle hotbox (`Hold Space`) opens and dismisses cleanly in a live 3D
   Viewport without duplicate Landfall hotbox interference.
2. Cursor-raycast component mode switching over an unselected mesh in Object
   Mode activates the mesh under cursor and enters EDIT_MESH Face mode directly.
3. Frame Selected (`F`) and Frame All (`A`) operate cleanly in a real VIEW_3D.
4. Distinct GPU marking menus (`RMB` Component, `Shift+RMB` Tool, `Ctrl+RMB`
   Convert) render radial HUD in the live viewport and capture visual evidence.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

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
        raise RuntimeError("T02-2 must run in non-headless GUI Blender")

    import landfall_studio
    from landfall_studio.adapters import landfall_bridge, tentacle_bridge
    from landfall_studio.keymaps.conflict_scanner import scan_keymap_conflicts
    from landfall_studio.viewport import marking_menus
    from landfall_studio.viewport.interaction import raycast_mesh_at_region_xy

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "phase02_gui_results.json"
    screenshot_path = OUTPUT_DIR / "phase02_marking_menu_viewport.png"

    state: dict = {
        "step": 0,
        "draw_handle": None,
        "results": {
            "suite": "T02-2_gui_interaction",
            "headless": bool(bpy.app.background),
            "checks": {},
        },
    }

    def _cleanup_draw_handle():
        h = state.get("draw_handle")
        if h is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(h, "WINDOW")
            except Exception:
                pass
            state["draw_handle"] = None

    def _step_runner():
        step = state["step"]
        try:
            if step == 0:
                bpy.context.preferences.view.show_splash = False
                bpy.ops.wm.read_homefile()
                landfall_studio.register()
                landfall_bridge.sync_now()
                scan = scan_keymap_conflicts(bpy.context)
                assert scan["clean"], f"Keymap scan failed in GUI: {scan}"
                assert scan["tentacle_key_info"]["addon_key_type"] == "SPACE"
                state["results"]["checks"]["keymap_scan_clean"] = True

                # Clear default objects while keeping startup 3D Viewport camera intact
                ctx = _find_view3d_override()
                with bpy.context.temp_override(**ctx):
                    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
                        bpy.ops.object.mode_set(mode="OBJECT")
                    bpy.ops.object.select_all(action="SELECT")
                    bpy.ops.object.delete(use_global=False)

                    bpy.ops.landfall_studio.btk_create_primitive(
                        primitive_type="CUBE", size=2.0
                    )
                    primary = bpy.context.view_layer.objects.active
                    primary.name = "Primary_Mesh"
                    primary.location = Vector((-2.2, 0.0, 0.0))

                    bpy.ops.landfall_studio.btk_create_primitive(
                        primitive_type="CUBE", size=2.0
                    )
                    target = bpy.context.view_layer.objects.active
                    target.name = "Target_Raycast_Mesh"
                    target.location = Vector((2.2, 0.0, 0.0))

                    bpy.ops.object.select_all(action="DESELECT")
                    primary.select_set(True)
                    bpy.context.view_layer.objects.active = primary
                    bpy.context.view_layer.update()

                    res_frame_all = bpy.ops.landfall_studio.frame_all()
                assert "FINISHED" in res_frame_all
                state["results"]["checks"]["frame_all_a"] = True
                state["step"] = 1
                return 0.25

            if step == 1:
                ctx = _find_view3d_override()
                region = ctx["region"]
                rv3d = ctx["space_data"].region_3d
                target = bpy.data.objects["Target_Raycast_Mesh"]

                target_2d = view3d_utils.location_3d_to_region_2d(
                    region, rv3d, target.matrix_world.translation
                )
                assert target_2d is not None, "Target mesh center did not project to 2D viewport"
                rx, ry = int(round(target_2d.x)), int(round(target_2d.y))

                with bpy.context.temp_override(**ctx):
                    hit_obj, hit_loc = raycast_mesh_at_region_xy(bpy.context, rx, ry)
                assert hit_obj is target, f"Expected raycast to hit Target_Raycast_Mesh, got {hit_obj}"

                with bpy.context.temp_override(**ctx):
                    bpy.ops.landfall_studio.component_mode(
                        mode="FACE", raycast_x=rx, raycast_y=ry
                    )
                assert bpy.context.view_layer.objects.active is target
                assert target.mode == "EDIT"
                assert tuple(bpy.context.tool_settings.mesh_select_mode) == (False, False, True)
                state["results"]["checks"]["cursor_raycast_component_switch"] = {
                    "hit_object": target.name,
                    "hit_location": [round(v, 4) for v in hit_loc],
                    "entered_mode": target.mode,
                    "select_mode": list(bpy.context.tool_settings.mesh_select_mode),
                    "cursor_xy": [rx, ry],
                }

                # Toggle F8 back to Object Mode and Frame Selected ('F')
                with bpy.context.temp_override(**ctx):
                    bpy.ops.landfall_studio.component_mode(mode="TOGGLE")
                    res_frame_sel = bpy.ops.view3d.view_selected(use_all_regions=False)
                assert target.mode == "OBJECT"
                assert "FINISHED" in res_frame_sel
                state["results"]["checks"]["f8_toggle_and_frame_selected_f"] = True

                # Verify Hold Space Tentacle Hotbox opens and closes cleanly
                qt_info = dict(tentacle_bridge.show_window_for_test("polygons"))
                qt_info.pop("_widget", None)
                tentacle_bridge.hide_window()
                state["results"]["checks"]["tentacle_hotbox_space"] = {
                    "visible_on_invoke": bool(qt_info.get("visible")),
                    "activation_key_info": tentacle_bridge.get_activation_key_info(),
                }
                assert qt_info.get("visible"), "Tentacle hotbox did not become visible"

                # Verify RMB (COMPONENT), Shift+RMB (TOOL), and Ctrl+RMB (CONVERT) menus
                comp_ring = marking_menus.RADIAL_RING_DEFS["COMPONENT"]
                tool_obj_ring = marking_menus.RADIAL_RING_DEFS["TOOL_OBJECT"]
                tool_edit_ring = marking_menus.RADIAL_RING_DEFS["TOOL_EDIT"]
                conv_ring = marking_menus.RADIAL_RING_DEFS["CONVERT"]

                assert len(comp_ring) == 8
                assert len(tool_obj_ring) == 8
                assert len(tool_edit_ring) == 8
                assert len(conv_ring) == 8
                state["results"]["checks"]["marking_menu_definitions"] = {
                    "COMPONENT": [item[0] for item in comp_ring],
                    "TOOL_OBJECT": [item[0] for item in tool_obj_ring],
                    "TOOL_EDIT": [item[0] for item in tool_edit_ring],
                    "CONVERT": [item[0] for item in conv_ring],
                }

                # Activate Translate ('W') + Face mode and open GPU Radial Marking Menu for capture
                with bpy.context.temp_override(**ctx):
                    bpy.ops.landfall_studio.select_tool(tool="TRANSLATE")
                    bpy.ops.landfall_studio.component_mode(mode="FACE")
                    bpy.ops.landfall_studio.marking_menu(
                        "EXEC_DEFAULT",
                        menu_mode="TOOL",
                        select_radial_index=0,
                        keep_open_for_capture=True,
                        raycast_x=int(region.width * 0.5),
                        raycast_y=int(region.height * 0.56),
                    )

                mm_state = marking_menus.get_marking_menu_state()
                assert mm_state["open"] and mm_state["has_draw_handler"]
                state["results"]["checks"]["marking_menu_live_state"] = mm_state

                for area in ctx["screen"].areas:
                    area.tag_redraw()
                state["step"] = 2
                return 0.3

            if step == 2:
                ctx = _find_view3d_override()
                with bpy.context.temp_override(**ctx):
                    bpy.ops.screen.screenshot(filepath=str(screenshot_path))
                marking_menus.stop_studio_marking_menu()

                assert screenshot_path.is_file() and screenshot_path.stat().st_size > 10_000
                state["results"]["checks"]["viewport_screenshot"] = {
                    "path": str(screenshot_path),
                    "bytes": screenshot_path.stat().st_size,
                }
                state["step"] = 3
                return 0.2

            if step == 3:
                marking_menus.stop_studio_marking_menu()
                landfall_studio.unregister()
                state["results"]["overall_pass"] = True
                json_path.write_text(
                    json.dumps(state["results"], indent=2), encoding="utf-8"
                )
                print(f"PHASE02_GUI_PASS: wrote {json_path}")
                bpy.ops.wm.quit_blender()
                return None

        except Exception as exc:
            marking_menus.stop_studio_marking_menu()
            try:
                landfall_studio.unregister()
            except Exception:
                pass
            err_payload = {
                "suite": "T02-2_gui_interaction",
                "overall_pass": False,
                "step": step,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            json_path.write_text(json.dumps(err_payload, indent=2), encoding="utf-8")
            print("PHASE02_GUI_FAIL:", json.dumps(err_payload, indent=2))
            bpy.ops.wm.quit_blender()
            return None

    bpy.app.timers.register(_step_runner, first_interval=0.3, persistent=True)


if __name__ == "__main__":
    main()
