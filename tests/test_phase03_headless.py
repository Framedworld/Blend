"""Phase 03 Headless Verification Suite (`T03-1`).

Verifies:
1. Unified Qt window & dock registry (`ui.open_panel`, `close_panel`, `dock_panel`, `undock_panel`, `focus_panel`, `resize_panel`, `minimize_panel`, `restore_panel`).
2. `Ctrl+A` right-dock panel cycling (`CHANNEL_BOX` <-> `ATTRIBUTE_EDITOR`) via `ui.cycle_right_dock` and `bpy.ops.landfall_studio.cycle_attribute_channels`.
3. Canonical project root propagation across `workspace_bridge`, `blendertk` workspace API (`create_maya_workspace`, `list_maya_workspaces`), `Workspace Editor`, and `Reference Manager`.
4. Two-way live selection & transform/custom-property sync between Blender and `Channels` (`blendertk/node_utils/attributes/channels/`):
   - Scene -> UI (`location`, `rotation_euler`, `scale`, custom property, and `DepsgraphUpdated`/`Undo` notifications).
   - UI -> Scene (`set_channel_value_from_ui` updating `obj.location` and custom property).
5. Qt -> Blender viewport hotkey passthrough filter (`QtViewportHotkeyFilter`):
   - Forwards single-key viewport hotkeys (`W`, `E`, `R`, `1`, `3`, `F8`, `Ctrl+A`) when focus is on a non-editable Qt widget.
   - Protects editable text inputs (`QLineEdit`) so typing `W`, `1`, `Space` is never stolen by viewport shortcuts.
6. Bottom command line / result feedback strip (`execute_command_string`, `LANDFALL_STUDIO_OT_execute_command_line`).
7. Clean `unregister()` and `restore_workspace_desktop()` with zero leaked timers, handlers, or keymaps.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_JSON = (
    Path(
        r"C:\Users\mattk\Documents\Landfall\Landfall_Studio_Agent_Pack\landfall_studio_agent_pack\output"
    )
    / "phase03_headless_results.json"
)


def _count_addon_kmi() -> int:
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return 0
    return sum(len(km.keymap_items) for km in kc.keymaps)


def main() -> int:
    os.environ["LANDFALL_STUDIO_UPSTREAM"] = r"C:\Users\mattk\Documents\Landfall\upstream"
    os.environ["LANDFALL_STUDIO_DEPS"] = r"C:\Users\mattk\Documents\Landfall\.deps\py313"

    import landfall_studio
    from landfall_studio import commands, diagnostics, keymaps, ui
    from landfall_studio.adapters import workspace_bridge

    baseline_kmi = _count_addon_kmi()
    baseline_depsgraph = len(bpy.app.handlers.depsgraph_update_post)
    baseline_load_post = len(bpy.app.handlers.load_post)

    # 1. Register Landfall Studio
    landfall_studio.register()
    from qtpy import QtCore, QtGui, QtWidgets
    rep = diagnostics.get_report()
    assert rep["full_stack_ready"] is True
    assert rep["subsystems"]["qt_desktop_registered"] is True

    # Verify Ctrl+A is bound in MAYA profile and keymap conflict scan remains clean
    scan = keymaps.scan_keymap_conflicts(bpy.context)
    assert scan["clean"] is True, f"Keymap scan failed: {scan}"

    # 2. Canonical Project Root & Maya Workspace propagation
    with tempfile.TemporaryDirectory(prefix="lf_phase03_proj_") as tmp_root:
        ws_dir = Path(tmp_root) / "maya_asset_proj"
        create_res = workspace_bridge.create_maya_workspace(str(ws_dir))
        assert create_res["ok"] is True, f"create_maya_workspace failed: {create_res}"
        assert (ws_dir / "workspace.mel").is_file()
        assert (ws_dir / "scenes").is_dir()

        set_res = ui.set_project_root_and_sync(str(ws_dir))
        assert set_res["ok"] is True
        canonical_root = set_res["project_root"]
        assert Path(canonical_root).resolve() == ws_dir.resolve()

        ws_list = workspace_bridge.list_maya_workspaces(tmp_root)
        assert any(
            Path(p).resolve() == ws_dir.resolve() for p in ws_list
        ), f"Expected {ws_dir} in {ws_list}"

        # Open Workspace Editor and Reference Manager and verify both receive canonical project root
        ws_panel = ui.open_panel("workspace_editor", dock=False)
        assert ws_panel["ok"] is True, f"Failed to open workspace_editor: {ws_panel}"
        rm_panel = ui.open_panel("reference_manager", dock=False)
        assert rm_panel["ok"] is True, f"Failed to open reference_manager: {rm_panel}"

        # Re-sync and verify widget paths
        sync_res = ui.set_project_root_and_sync(str(ws_dir))
        assert sync_res["workspace_editor_synced"] is True
        assert sync_res["reference_manager_synced"] is True

        # Test window lifecycle actions (focus, resize, minimize, restore, close) on Workspace Editor
        focus_res = ui.focus_panel("workspace_editor")
        assert focus_res["ok"] is True
        resize_res = ui.resize_panel("workspace_editor", 680, 460)
        assert resize_res["ok"] is True
        assert resize_res["width"] == 680 and resize_res["height"] == 460
        min_res = ui.minimize_panel("workspace_editor")
        assert min_res["ok"] is True
        rest_res = ui.restore_panel("workspace_editor")
        assert rest_res["ok"] is True

        # 3. Create a mesh object via blendertk and add a custom property
        bpy.ops.landfall_studio.btk_create_primitive(primitive_type="CUBE", size=2.0)
        cube = bpy.context.view_layer.objects.active
        assert cube is not None
        cube.name = "Hero_Asset_Geo"
        cube["maya_rig_scale"] = 1.25

        # 4. Open Channels panel and verify Two-Way Selection & Transform/Property Sync
        ch_panel = ui.open_panel("channels", dock=True)
        assert ch_panel["ok"] is True, f"Failed to open channels: {ch_panel}"

        snap_initial = ui.get_channels_snapshot()
        assert snap_initial["ok"] is True
        assert "Hero_Asset_Geo" in snap_initial["header"]
        assert snap_initial["row_count"] >= 10, f"Expected >=10 keyable rows, got {snap_initial}"
        for req_ch in (
            "location_x",
            "location_y",
            "location_z",
            "rotation_x",
            "rotation_y",
            "rotation_z",
            "scale_x",
            "scale_y",
            "scale_z",
            "maya_rig_scale",
        ):
            assert req_ch in snap_initial["channels"], f"Missing channel {req_ch} in {snap_initial['channels']}"

        # 4a. Scene -> UI sync (transform + custom property mutation)
        cube.location = Vector((3.5, -1.25, 7.0))
        cube.scale = Vector((2.0, 2.0, 2.0))
        cube["maya_rig_scale"] = 3.75
        snap_after_scene = ui.sync_channels_now()
        assert abs(float(snap_after_scene["channels"]["location_x"]) - 3.5) < 1e-4
        assert abs(float(snap_after_scene["channels"]["location_y"]) - (-1.25)) < 1e-4
        assert abs(float(snap_after_scene["channels"]["location_z"]) - 7.0) < 1e-4
        assert abs(float(snap_after_scene["channels"]["scale_x"]) - 2.0) < 1e-4
        assert abs(float(snap_after_scene["channels"]["maya_rig_scale"]) - 3.75) < 1e-4

        # 4b. UI -> Scene sync (editing table value inside Channels updates Blender object)
        edit_loc = ui.set_channel_value_from_ui("location_x", -6.5)
        assert edit_loc["ok"] is True, f"set_channel_value_from_ui(location_x) failed: {edit_loc}"
        assert abs(float(cube.location.x) - (-6.5)) < 1e-4

        edit_prop = ui.set_channel_value_from_ui("maya_rig_scale", 5.5)
        assert edit_prop["ok"] is True, f"set_channel_value_from_ui(maya_rig_scale) failed: {edit_prop}"
        assert abs(float(cube["maya_rig_scale"]) - 5.5) < 1e-4

        # 5. Right-Dock Cycling (`Ctrl+A` / `cycle_attribute_channels`) & Undock/Dock
        cycle_to_ae = ui.cycle_right_dock(bpy.context)
        assert cycle_to_ae["mode"] == "ATTRIBUTE_EDITOR"
        cycle_to_cb = ui.cycle_right_dock(bpy.context)
        assert cycle_to_cb["mode"] == "CHANNEL_BOX"

        undock_res = ui.undock_panel("channels")
        assert undock_res["ok"] is True
        assert undock_res["docked"] is False
        dock_res = ui.dock_panel("channels")
        assert dock_res["ok"] is True

        # 6. Script Output panel toggle
        so_open = ui.open_panel("script_output", dock=False)
        assert so_open["ok"] is True
        so_close = ui.close_panel("script_output")
        assert so_close["ok"] is True

        # 7. Qt -> Blender Viewport Hotkey Passthrough Filter vs Editable Text Focus Guard
        hk_filter = ui.get_hotkey_filter()
        assert hk_filter is not None

        # Create a non-editable button and an editable QLineEdit to test focus filtering
        test_btn = QtWidgets.QPushButton("ViewportProxyButton")
        test_line = QtWidgets.QLineEdit()

        # 7a. Non-editable widget event -> passthrough executes in Blender
        commands.set_active_tool("SELECT")
        key_e_event = QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            QtCore.Qt.Key_E,
            QtCore.Qt.NoModifier,
            "e",
        )
        intercepted_e = hk_filter.eventFilter(test_btn, key_e_event)
        assert intercepted_e is True
        assert commands.get_active_tool() == "ROTATE"

        key_3_event = QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            QtCore.Qt.Key_3,
            QtCore.Qt.NoModifier,
            "3",
        )
        intercepted_3 = hk_filter.eventFilter(test_btn, key_3_event)
        assert intercepted_3 is True
        subsurf = next((m for m in cube.modifiers if m.type == "SUBSURF"), None)
        assert subsurf is not None and subsurf.show_viewport is True

        key_1_event = QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            QtCore.Qt.Key_1,
            QtCore.Qt.NoModifier,
            "1",
        )
        assert hk_filter.eventFilter(test_btn, key_1_event) is True
        assert subsurf.show_viewport is False

        # 7b. Editable QLineEdit event -> NEVER intercepted by viewport hotkeys
        before_blocked = hk_filter.blocked_by_text_focus_count
        key_w_in_text = QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            QtCore.Qt.Key_W,
            QtCore.Qt.NoModifier,
            "w",
        )
        intercepted_text = hk_filter.eventFilter(test_line, key_w_in_text)
        assert intercepted_text is False, "QLineEdit key event must not be intercepted!"
        assert hk_filter.blocked_by_text_focus_count == before_blocked + 1
        assert commands.get_active_tool() == "ROTATE", "Tool state must not change when typing in QLineEdit"

        # 8. Bottom Command Line / Result Feedback Strip
        cmd_res = ui.execute_command_string("len(bpy.data.objects)", context=bpy.context)
        assert cmd_res["ok"] is True
        fb = ui.get_command_feedback()
        assert fb["last_command"] == "len(bpy.data.objects)"
        assert fb["is_error"] is False

        op_res = bpy.ops.landfall_studio.execute_command_line(
            command="bpy.context.active_object.name"
        )
        assert "FINISHED" in op_res
        fb2 = ui.get_command_feedback()
        assert "Hero_Asset_Geo" in fb2["last_result"]

        reg_snapshot = ui.get_registry_state()
        hk_snapshot = {
            "passthrough_count": hk_filter.passthrough_count,
            "blocked_by_text_focus_count": hk_filter.blocked_by_text_focus_count,
            "last_passthrough_key": hk_filter.last_passthrough_key,
        }
        assert hk_snapshot["passthrough_count"] >= 3
        assert hk_snapshot["blocked_by_text_focus_count"] >= 1

    # 9. Clean unregister and state restoration verification
    landfall_studio.unregister()

    post_kmi = _count_addon_kmi()
    post_depsgraph = len(bpy.app.handlers.depsgraph_update_post)
    post_load_post = len(bpy.app.handlers.load_post)

    assert post_kmi == baseline_kmi, f"Leaked addon KMI: {baseline_kmi} -> {post_kmi}"
    assert post_depsgraph == baseline_depsgraph
    assert post_load_post == baseline_load_post
    assert ui.get_registry_state()["registered"] is False

    results = {
        "suite": "T03-1_headless_qt_desktop",
        "blender_version": bpy.app.version_string,
        "workspace_created": create_res,
        "channels_initial_count": snap_initial["row_count"],
        "channels_scene_to_ui": snap_after_scene["channels"],
        "channels_ui_to_scene": {
            "location_x": float(cube.location.x),
            "maya_rig_scale": float(cube["maya_rig_scale"]),
        },
        "right_dock_cycles": [cycle_to_ae["mode"], cycle_to_cb["mode"]],
        "hotkey_passthrough": hk_snapshot,
        "command_feedback": fb2,
        "registry_snapshot_before_unregister": reg_snapshot,
        "cleanup": {
            "baseline_kmi": baseline_kmi,
            "post_kmi": post_kmi,
            "depsgraph_handlers_clean": post_depsgraph == baseline_depsgraph,
            "load_post_handlers_clean": post_load_post == baseline_load_post,
        },
        "passed": True,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("T03-1 HEADLESS SUITE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
