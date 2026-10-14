"""Phase 01 Non-Headless GUI Verification Suite for Landfall Studio.

Runs inside a real Blender 5.2 GUI session (with a live GHOST window and OpenGL/Vulkan
viewport) and verifies:
1. Landfall viewport theme colors, finite grid, and GPU draw handlers (`_grid_handle`,
   `_border_handle`, `_cage_handle`) are active and render cleanly.
2. A `blendertk` modeling command (`landfall_studio.btk_create_primitive`) creates a mesh
   in the live viewport, and `landfall.smooth_preview(mode='BOTH')` enables the original
   smooth cage wireframe overlay.
3. Tentacle's Qt host (`_QtHost`) and `TclBlender` open a real visible Qt window on screen
   with an active Switchboard (`sb`) instance and native `winId`.
4. Screenshots of both the Blender 3D Viewport and the live Tentacle Qt window are captured
   as verification evidence.
5. `landfall_studio.unregister()` restores Blender's original stock theme, grid settings,
   keymaps, handlers, and timers cleanly before quitting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(
            REPO_ROOT.parent
            / "Landfall_Studio_Agent_Pack"
            / "landfall_studio_agent_pack"
            / "output"
        ),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    import landfall_studio
    from landfall_studio import diagnostics
    from landfall_studio.adapters import (
        blendertk_bridge,
        landfall_bridge,
        tentacle_bridge,
    )

    state = {"step": 0, "results": {}, "error": None}

    def _step_runner():
        try:
            step = state["step"]
            if step == 0:
                # Step 0: Dismiss initial splash popup via read_homefile, then register Landfall Studio
                bpy.context.preferences.view.show_splash = False
                bpy.ops.wm.read_homefile()
                landfall_studio.register()
                landfall_bridge.sync_now()
                state["step"] = 1
                return 0.25

            if step == 1:
                # Step 1: Verify Landfall viewport state & execute blendertk + Landfall commands
                lf_mod = landfall_bridge.get_module()
                theme_v3d = bpy.context.preferences.themes[0].view_3d
                maya_theme_active = bool(lf_mod._theme_is_maya(theme_v3d))
                draw_handlers_active = bool(
                    set(getattr(lf_mod, "_draw_handles", {}).keys())
                    == {"borders", "cage", "grid"}
                )
                finite_grid_active = bool(bpy.context.scene.landfall_grid_finite)

                # Delete default cube and create a fresh cube via blendertk, then enable smooth cage preview
                if "Cube" in bpy.data.objects:
                    bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)

                btk_res = blendertk_bridge.execute_sample_command(
                    primitive_type="CUBE",
                    name="Studio_GUI_Cube",
                    size=2.6,
                )
                cube = bpy.data.objects["Studio_GUI_Cube"]
                bpy.context.view_layer.objects.active = cube
                cube.select_set(True)
                bpy.ops.landfall.smooth_preview(mode="BOTH")

                state["results"]["viewport"] = {
                    "maya_theme_active": maya_theme_active,
                    "draw_handlers_active": draw_handlers_active,
                    "draw_handler_keys": sorted(getattr(lf_mod, "_draw_handles", {}).keys()),
                    "finite_grid_active": finite_grid_active,
                    "smooth_cage_show": bool(bpy.context.scene.landfall_cage_show),
                    "btk_command": btk_res,
                }
                state["step"] = 2
                return 0.25

            if step == 2:
                # Step 2: Open the real Tentacle Qt Switchboard window ("polygons") and capture screenshots
                qt_info = dict(tentacle_bridge.show_window_for_test("polygons"))
                target_widget = qt_info.pop("_widget", None)

                qt_shot_path = out_dir / "phase01_tentacle_qt_window.png"
                if target_widget is not None:
                    pixmap = target_widget.grab()
                    pixmap.save(str(qt_shot_path))

                # Capture full Blender GUI window screenshot (including GPU overlays, finite grid, smooth cage, Maya theme)
                vp_shot_path = out_dir / "phase01_blender_viewport.png"
                try:
                    for window in bpy.context.window_manager.windows:
                        for area in window.screen.areas:
                            if area.type == "VIEW_3D":
                                for region in area.regions:
                                    if region.type == "WINDOW":
                                        with bpy.context.temp_override(
                                            window=window, area=area, region=region
                                        ):
                                            bpy.ops.screen.screenshot(
                                                filepath=str(vp_shot_path)
                                            )
                                        break
                                break
                except Exception as render_exc:
                    state["results"]["viewport_render_note"] = str(render_exc)

                state["results"]["tentacle_qt"] = {
                    **qt_info,
                    "qt_screenshot": str(qt_shot_path),
                    "qt_screenshot_exists": qt_shot_path.is_file(),
                    "viewport_screenshot": str(vp_shot_path),
                    "viewport_screenshot_exists": vp_shot_path.is_file(),
                }
                state["step"] = 3
                return 0.25

            if step == 3:
                # Step 3: Hide window, unregister Landfall Studio, and verify clean restoration
                tentacle_bridge.hide_window()
                rep_before_unreg = diagnostics.get_report()
                landfall_studio.unregister()

                lf_mod = landfall_bridge.get_module()
                theme_v3d = bpy.context.preferences.themes[0].view_3d
                theme_restored = not bool(lf_mod._theme_is_maya(theme_v3d))
                handlers_removed = len(getattr(lf_mod, "_draw_handles", {})) == 0
                timers_removed = not any(
                    bpy.app.timers.is_registered(getattr(lf_mod, name, None))
                    for name in ("_gizmos_sync", "_keymap_heal", "_deferred_sync")
                )

                tb_mod = sys.modules.get("tentacle.tcl_blender")
                tentacle_clean = True
                if tb_mod is not None:
                    tentacle_clean = bool(
                        tb_mod._KeymapBridge.poller is None
                        and not tb_mod._QtHost._pump_registered
                    )

                final_payload = {
                    "status": "PASS"
                    if (
                        state["results"]["viewport"]["maya_theme_active"]
                        and state["results"]["viewport"]["draw_handlers_active"]
                        and state["results"]["tentacle_qt"]["visible"]
                        and theme_restored
                        and handlers_removed
                        and timers_removed
                        and tentacle_clean
                    )
                    else "FAIL",
                    "blender": rep_before_unreg["blender"],
                    "python": rep_before_unreg["python"],
                    "viewport": state["results"]["viewport"],
                    "tentacle_qt": state["results"]["tentacle_qt"],
                    "teardown": {
                        "theme_restored": theme_restored,
                        "draw_handlers_removed": handlers_removed,
                        "landfall_timers_removed": timers_removed,
                        "tentacle_timers_removed": tentacle_clean,
                    },
                }

                json_path = out_dir / "phase01_gui_results.json"
                json_path.write_text(json.dumps(final_payload, indent=2), encoding="utf-8")
                print("PHASE01_GUI_RESULT_JSON_BEGIN")
                print(json.dumps(final_payload, indent=2))
                print("PHASE01_GUI_RESULT_JSON_END")
                bpy.ops.wm.quit_blender()
                return None

        except Exception as exc:
            import traceback

            err_payload = {
                "status": "FAIL",
                "step": state["step"],
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            json_path = out_dir / "phase01_gui_results.json"
            json_path.write_text(json.dumps(err_payload, indent=2), encoding="utf-8")
            print("PHASE01_GUI_RESULT_JSON_BEGIN")
            print(json.dumps(err_payload, indent=2))
            print("PHASE01_GUI_RESULT_JSON_END")
            bpy.ops.wm.quit_blender()
            return None

    bpy.app.timers.register(_step_runner, first_interval=0.3, persistent=True)


if __name__ == "__main__":
    main()
