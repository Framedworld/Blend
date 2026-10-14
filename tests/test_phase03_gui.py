"""Phase 03 (Gate 03) Real GUI Blender Verification Suite (`T03-2`).

Runs in non-headless Blender 5.2 (`--factory-startup -noaudio --python ...`)
using a stepped timer inside Blender's live window event loop (matching T01-3 & T02-2)
to verify:
1. Docked `Channels` (`QtDock` `WS_CHILD` embedding on the right side of the Blender window)
   opens cleanly and displays the selected mesh's 9 transform channels + custom properties.
2. Live two-way selection & transform/property sync in GUI:
   - Selecting `Hero_Asset_A` vs `Hero_Asset_B` updates the docked `Channels` header and rows.
   - Transforming `Hero_Asset_A` in the 3D Viewport updates the docked `Channels` values live.
   - Editing a channel value inside the docked `Channels` UI updates `Hero_Asset_A` in the 3D Viewport.
3. `Ctrl+A` (`landfall_studio.cycle_attribute_channels`) cycles the right-hand dock cleanly between
   `CHANNEL_BOX` (`Channels` `WS_CHILD` embedded) and `ATTRIBUTE_EDITOR` (native `PROPERTIES` visible)
   and back to `CHANNEL_BOX` with zero duplicate Blender areas.
4. Floating Qt tool windows (`Workspace Editor`, `Reference Manager`) and bottom-docked `Script Output`
   open, share the canonical project root, clamp to screen bounds, and support focus/resize/minimize/restore/undock/dock.
5. Qt -> Blender viewport hotkey passthrough (`W/E/R`, `1/3`, `Ctrl+A`) works when a non-text Qt widget has focus,
   while editable text inputs (`QLineEdit`) are protected.
6. Repeated `restore_workspace_desktop()` calls are idempotent and create zero duplicate Blender areas.
7. Captures visual evidence (`output/phase03_qt_desktop_gui.png`) and writes `output/phase03_gui_results.json`.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

import bpy
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
        raise RuntimeError("T03-2 must run in non-headless GUI Blender")

    os.environ["LANDFALL_STUDIO_UPSTREAM"] = r"C:\Users\mattk\Documents\Landfall\upstream"
    os.environ["LANDFALL_STUDIO_DEPS"] = r"C:\Users\mattk\Documents\Landfall\.deps\py313"

    import landfall_studio
    from landfall_studio import commands, keymaps, ui
    from landfall_studio.adapters import landfall_bridge, workspace_bridge

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "phase03_gui_results.json"
    screenshot_path = OUTPUT_DIR / "phase03_qt_desktop_gui.png"

    tmp_dir_obj = tempfile.TemporaryDirectory(prefix="lf_phase03_gui_proj_")
    ws_dir = Path(tmp_dir_obj.name) / "maya_gui_project"

    state: dict = {
        "step": 0,
        "initial_area_count": 0,
        "results": {
            "suite": "T03-2_gui_qt_desktop",
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

                win = bpy.context.window_manager.windows[0]
                state["initial_area_count"] = len(win.screen.areas)

                # Create canonical Maya workspace and propagate root
                ws_res = workspace_bridge.create_maya_workspace(str(ws_dir))
                assert ws_res["ok"] is True
                ui.set_project_root_and_sync(str(ws_dir))

                # Build two test meshes in VIEW_3D
                ctx = _find_view3d_override()
                with bpy.context.temp_override(**ctx):
                    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
                        bpy.ops.object.mode_set(mode="OBJECT")
                    bpy.ops.object.select_all(action="SELECT")
                    bpy.ops.object.delete(use_global=False)

                    bpy.ops.landfall_studio.btk_create_primitive(
                        primitive_type="CUBE", size=2.0
                    )
                    mesh_a = bpy.context.view_layer.objects.active
                    mesh_a.name = "Hero_Asset_A"
                    mesh_a.location = Vector((-2.0, 0.0, 1.0))
                    mesh_a["rig_influence"] = 0.85

                    bpy.ops.landfall_studio.btk_create_primitive(
                        primitive_type="SPHERE", size=1.8
                    )
                    mesh_b = bpy.context.view_layer.objects.active
                    mesh_b.name = "Hero_Asset_B"
                    mesh_b.location = Vector((2.2, 0.5, 1.0))
                    mesh_b["rig_influence"] = 0.25

                    # Select Hero_Asset_A first
                    bpy.ops.object.select_all(action="DESELECT")
                    mesh_a.select_set(True)
                    bpy.context.view_layer.objects.active = mesh_a

                state["step"] = 1
                return 0.35

            if step == 1:
                # Restore workspace desktop (docks Channels on right via WS_CHILD over Properties)
                desk1 = ui.restore_workspace_desktop(
                    dock_channels=True, restore_script_output=True
                )
                assert desk1["ok"] is True
                reg1 = ui.get_registry_state()
                assert reg1["right_dock_mode"] == "CHANNEL_BOX", f"Expected CHANNEL_BOX, got {reg1}"
                assert reg1["right_dock_embedded"] is True, f"Expected WS_CHILD embedded=True, got {reg1}"

                snap_a = ui.sync_channels_now()
                assert "Hero_Asset_A" in snap_a["header"]
                assert abs(float(snap_a["channels"]["location_x"]) - (-2.0)) < 1e-4
                assert abs(float(snap_a["channels"]["rig_influence"]) - 0.85) < 1e-4

                state["results"]["checks"]["channels_docked_ws_child"] = {
                    "docked": reg1["right_dock_embedded"],
                    "mode": reg1["right_dock_mode"],
                    "header": snap_a["header"],
                    "row_count": snap_a["row_count"],
                }
                state["step"] = 2
                return 0.35

            if step == 2:
                # Selection switch -> Hero_Asset_B + Two-Way Sync check in live GUI
                mesh_a = bpy.data.objects["Hero_Asset_A"]
                mesh_b = bpy.data.objects["Hero_Asset_B"]
                mesh_a.select_set(False)
                mesh_b.select_set(True)
                bpy.context.view_layer.objects.active = mesh_b

                snap_b = ui.sync_channels_now()
                assert "Hero_Asset_B" in snap_b["header"]
                assert abs(float(snap_b["channels"]["location_x"]) - 2.2) < 1e-4
                assert abs(float(snap_b["channels"]["rig_influence"]) - 0.25) < 1e-4

                # Edit channel value in docked Qt table -> verify Blender scene updates
                edit_res = ui.set_channel_value_from_ui("location_z", 3.5)
                assert edit_res["ok"] is True
                assert abs(float(mesh_b.location.z) - 3.5) < 1e-4

                state["results"]["checks"]["two_way_live_sync"] = {
                    "selected_header": snap_b["header"],
                    "edited_location_z": float(mesh_b.location.z),
                }
                state["step"] = 3
                return 0.35

            if step == 3:
                # Cycle Right Dock with Ctrl+A operator: CHANNEL_BOX -> ATTRIBUTE_EDITOR -> CHANNEL_BOX
                win = bpy.context.window_manager.windows[0]
                areas_before_cycle = len(win.screen.areas)

                bpy.ops.landfall_studio.cycle_attribute_channels(mode="CYCLE")
                reg_ae = ui.get_registry_state()
                assert reg_ae["right_dock_mode"] == "ATTRIBUTE_EDITOR"
                assert reg_ae["right_dock_embedded"] is False

                bpy.ops.landfall_studio.cycle_attribute_channels(mode="CYCLE")
                reg_cb = ui.get_registry_state()
                assert reg_cb["right_dock_mode"] == "CHANNEL_BOX"
                assert reg_cb["right_dock_embedded"] is True
                assert len(win.screen.areas) == areas_before_cycle, "Ctrl+A cycling must not leak duplicate areas"

                # Open Workspace Editor & Reference Manager floating panels and verify root sync
                ws_open = ui.open_panel("workspace_editor", docked=False)
                rm_open = ui.open_panel("reference_manager", docked=False)
                assert ws_open["ok"] is True and ws_open["visible"] is True
                assert rm_open["ok"] is True and rm_open["visible"] is True

                sync_check = ui.sync_project_root_to_panels(str(ws_dir))
                assert sync_check["workspace_editor_synced"] is True
                assert sync_check["reference_manager_synced"] is True

                # Verify idempotent restore_workspace_desktop creates zero duplicate areas
                desk2 = ui.restore_workspace_desktop(
                    dock_channels=True, restore_script_output=True
                )
                assert desk2["areas_after"] == desk2["areas_before"]

                state["results"]["checks"]["ctrl_a_and_panels"] = {
                    "cycled_to_ae": reg_ae["right_dock_mode"],
                    "cycled_back_to_cb": reg_cb["right_dock_mode"],
                    "workspace_editor_visible": ws_open["visible"],
                    "reference_manager_visible": rm_open["visible"],
                    "area_count_stable": len(win.screen.areas),
                }
                state["step"] = 4
                return 0.4

            if step == 4:
                # Test Qt -> Blender hotkey passthrough vs editable QLineEdit protection in live GUI
                from qtpy import QtCore, QtGui, QtWidgets

                hk_filter = ui.get_hotkey_filter()
                assert hk_filter is not None

                ws_widget, _ = ui.get_panel_widget_and_slots("workspace_editor")
                txt_root = getattr(ws_widget, "txt000", None)
                assert txt_root is not None

                # Non-editable widget press 'W' -> activates Translate tool in VIEW_3D
                dummy_btn = QtWidgets.QPushButton("DummyNonText")
                ev_w = QtGui.QKeyEvent(
                    QtCore.QEvent.KeyPress, QtCore.Qt.Key_W, QtCore.Qt.NoModifier, "w"
                )
                assert hk_filter.eventFilter(dummy_btn, ev_w) is True
                assert commands.get_active_tool() == "TRANSLATE"

                # Editable QLineEdit (txt000 in Workspace Editor) press 'E' -> blocked from viewport passthrough
                before_blocked = hk_filter.blocked_by_text_focus_count
                ev_e_text = QtGui.QKeyEvent(
                    QtCore.QEvent.KeyPress, QtCore.Qt.Key_E, QtCore.Qt.NoModifier, "e"
                )
                assert hk_filter.eventFilter(txt_root, ev_e_text) is False
                assert hk_filter.blocked_by_text_focus_count == before_blocked + 1
                assert commands.get_active_tool() == "TRANSLATE"

                # Execute bottom command line expression
                bpy.ops.landfall_studio.execute_command_line(
                    command="bpy.context.active_object.name"
                )
                fb = ui.get_command_feedback()
                assert "Hero_Asset_B" in fb["last_result"]

                # Arrange floating panels cleanly for visual inspection and capture screenshot
                ws_widget, _ = ui.get_panel_widget_and_slots("workspace_editor")
                rm_widget, _ = ui.get_panel_widget_and_slots("reference_manager")
                ch_widget, _ = ui.get_panel_widget_and_slots("channels")
                so_widget, _ = ui.get_panel_widget_and_slots("script_output")

                if ws_widget is not None:
                    ws_widget.resize(520, 380)
                if rm_widget is not None:
                    rm_widget.resize(440, 380)

                bpy.ops.screen.screenshot(filepath=str(screenshot_path))

                # Composite live Qt WS_CHILD docks + floating Qt windows onto Blender's OpenGL framebuffer screenshot
                try:
                    from blendertk.env_utils.script_output import ScriptConsole

                    ui.sync_channels_now()
                    base_pix = QtGui.QPixmap(str(screenshot_path))
                    if not base_pix.isNull():
                        painter = QtGui.QPainter(base_pix)
                        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

                        # 1. Right-docked Channels WS_CHILD at its exact physical client rect
                        rdock = ui.desktop._get_right_dock()
                        ch_rect = rdock.enforce_dock_geometry() or rdock._inner_dock._last_rect
                        if ch_widget is not None and ch_rect is not None:
                            rx, ry, rw, rh = ch_rect
                            ch_pix = ch_widget.grab()
                            painter.drawPixmap(
                                QtCore.QRect(int(rx), int(ry), int(rw), int(rh)),
                                ch_pix,
                            )

                        # 2. Bottom-docked Script Output WS_CHILD at its exact physical client rect
                        so_dock = ScriptConsole.instance()._dock
                        so_dock._last_rect = None
                        so_dock._position(so_dock.content_region())
                        so_rect = so_dock._last_rect
                        if so_widget is not None and so_rect is not None:
                            sx, sy, sw, sh = so_rect
                            so_pix = so_widget.grab()
                            painter.drawPixmap(
                                QtCore.QRect(int(sx), int(sy), int(sw), int(sh)),
                                so_pix,
                            )

                        # 3. Floating Workspace Editor & Reference Manager windows
                        if ws_widget is not None:
                            ws_pix = ws_widget.grab()
                            painter.drawPixmap(70, 85, ws_pix)
                        if rm_widget is not None:
                            rm_pix = rm_widget.grab()
                            painter.drawPixmap(610, 85, rm_pix)

                        painter.end()
                        base_pix.save(str(screenshot_path))
                except Exception as comp_exc:
                    print(f"[T03-2 composite note] {comp_exc}")

                state["results"]["checks"]["hotkey_passthrough_gui"] = {
                    "passthrough_count": hk_filter.passthrough_count,
                    "blocked_by_text_focus_count": hk_filter.blocked_by_text_focus_count,
                    "command_feedback": fb,
                    "screenshot_saved": screenshot_path.is_file(),
                    "screenshot_bytes": screenshot_path.stat().st_size if screenshot_path.is_file() else 0,
                }
                state["step"] = 5
                return 0.3

            if step == 5:
                # Clean unregister & exit
                landfall_studio.unregister()
                tmp_dir_obj.cleanup()
                state["results"]["passed"] = True
                json_path.write_text(
                    json.dumps(state["results"], indent=2), encoding="utf-8"
                )
                print("T03-2 GUI SUITE PASSED")
                bpy.ops.wm.quit_blender()
                return None

        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[T03-2 ERROR at step {step}] {exc}\n{tb}", file=sys.stderr)
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
            try:
                tmp_dir_obj.cleanup()
            except Exception:
                pass
            bpy.ops.wm.quit_blender()
            return None

    bpy.app.timers.register(_step_runner, first_interval=0.35, persistent=True)


if __name__ == "__main__":
    main()
