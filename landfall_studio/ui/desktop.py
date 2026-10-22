"""Unified Qt Window Desktop, Dock Manager, Selection Notifier, and Command Feedback Strip.

Integrates:
1. Canonical Qt tool windows & docks via a single `BlenderUiHandler` / `TclBlender` host:
   - `channels` (`Channels` / `ChannelsSlots`, default `"Keyable"` filter, dockable on right via `RightAreaQtDock` or floating)
   - `reference_manager` (`Reference Manager` / `ReferenceManagerSlots`, synced to canonical project root)
   - `workspace_editor` (`Workspace Editor` / `WorkspaceEditorSlots`, synced to canonical project root)
   - `script_output` (`Script Output` / `btk.ScriptConsole`, docked at bottom via `QtDock`)
2. Single `ScriptJobManager` selection & live transform/property notifier so `Channels` stays synchronized on
   selection changes, viewport transforms (`W/E/R`), `Undo`/`Redo`, and frame changes, and two-way edits write back to `bpy`.
3. `Ctrl+A` right-dock cycling (`landfall_studio.cycle_attribute_channels`) between `CHANNEL_BOX` and `ATTRIBUTE_EDITOR` (`PROPERTIES`).
4. Bottom command/result feedback strip (`get_command_feedback`, `set_command_feedback`, `execute_command_line`).
5. Screen/DPI geometry clamping, focus/resize/minimize/restore, and idempotent workspace restore with zero duplicate areas.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from ..adapters import landfall_bridge, tentacle_bridge, workspace_bridge
from ..bootstrap.deps import check_dependencies
from . import (
    attribute_editor,
    channel_box_ext,
    hotkey_passthrough,
    modeling_toolkit,
    outliner,
    shape_editor,
    shelf,
    style,
    time_slider,
    tool_settings,
)
from .right_dock import RightAreaQtDock

CANONICAL_PANELS = (
    "channels",
    "reference_manager",
    "workspace_editor",
    "script_output",
    "blendshape_animator",
)

_DESKTOP_SYNC_OWNER = object()
_registered: bool = False
_right_dock: Optional[RightAreaQtDock] = None
_top_shelf_dock: Optional[shelf.TopShelfQtDock] = None
_panel_registry: Dict[str, Dict[str, Any]] = {}
_last_selection_value_sig: Optional[Tuple[Any, ...]] = None
_channels_default_filter_applied: bool = False
_scene_restore_timer = None
_desktop_sizes = {}
_orig_btk_set_current_workspace: Optional[Any] = None
_syncing_workspace_hook: bool = False

_command_feedback: Dict[str, Any] = {
    "ok": True,
    "command": "Ready",
    "last_command": "Ready",
    "result": "Landfall Studio — Modern Maya Desktop Ready",
    "last_result": "Landfall Studio — Modern Maya Desktop Ready",
    "level": "INFO",
    "is_error": False,
    "timestamp": 0.0,
}


def _ensure_qt_events_flushed() -> None:
    """Flush posted Qt events safely without triggering nested GHOST modal loops."""
    try:
        from qtpy import QtCore, QtWidgets

        app = QtWidgets.QApplication.instance()
        if app is not None:
            QtCore.QCoreApplication.sendPostedEvents()
            QtCore.QCoreApplication.sendPostedEvents(
                None, QtCore.QEvent.DeferredDelete
            )
    except Exception:
        pass


_cached_ui_handler: Optional[Any] = None
_cached_ui_handler_tcl_id: Optional[int] = None


def ensure_ui_handler() -> Optional[Any]:
    """Return the single authoritative `BlenderUiHandler` sharing `TclBlender`'s `Switchboard`."""
    global _cached_ui_handler, _cached_ui_handler_tcl_id
    # Reuse the cached handler only while it is bound to the current Tentacle instance
    tcl_now = tentacle_bridge.get_tcl_instance()
    tcl_id = id(tcl_now) if tcl_now is not None else None
    if _cached_ui_handler is not None and _cached_ui_handler_tcl_id == tcl_id:
        return _cached_ui_handler
    _cached_ui_handler = None

    deps = check_dependencies()
    if not deps["full_stack_ready"]:
        return None

    try:
        from qtpy import QtWidgets
        import tentacle.tcl_blender as tcl_blender
        from blendertk.ui_utils.blender_ui_handler import BlenderUiHandler

        app = tcl_blender._QtHost.ensure_qapp()
        tcl_blender._QtHost.ensure_widget(app)
        tcl = tentacle_bridge.get_tcl_instance()
        if tcl is not None and getattr(tcl, "sb", None) is not None:
            _cached_ui_handler = BlenderUiHandler.instance(switchboard=tcl.sb)
        else:
            _cached_ui_handler = BlenderUiHandler.instance()
        _cached_ui_handler_tcl_id = id(tcl) if tcl is not None else None
        return _cached_ui_handler
    except Exception:
        return None


def _get_right_dock() -> RightAreaQtDock:
    global _right_dock
    if _right_dock is None:
        _right_dock = RightAreaQtDock(
            editor="Properties",
            area_header=False,
            focus_on_hover=True,
        )
    return _right_dock


def _get_top_shelf_dock() -> shelf.TopShelfQtDock:
    global _top_shelf_dock
    if _top_shelf_dock is None:
        _top_shelf_dock = shelf.TopShelfQtDock()
    return _top_shelf_dock


def _get_left_outliner_dock() -> outliner.LeftOutlinerQtDock:
    return outliner.get_left_outliner_dock()


def dock_top_shelf() -> Dict[str, Any]:
    ensure_ui_handler()
    tdock = _get_top_shelf_dock()
    ok = tdock.dock_shelf()
    _ensure_qt_events_flushed()
    return {"ok": True, "docked": bool(ok), "widget": tdock.widget is not None}


def dock_left_outliner() -> Dict[str, Any]:
    ensure_ui_handler()
    ldock = outliner.get_left_outliner_dock()
    ok = ldock.dock_outliner()
    _ensure_qt_events_flushed()
    return {"ok": True, "docked": bool(ok), "widget": ldock.widget is not None}


def dock_time_slider() -> Dict[str, Any]:
    ensure_ui_handler()
    ts_dock = time_slider.get_bottom_time_slider_dock()
    ok = ts_dock.dock_time_slider()
    _ensure_qt_events_flushed()
    return {"ok": True, "docked": bool(ok), "widget": ts_dock.widget is not None}


def toggle_left_outliner_dock() -> Dict[str, Any]:
    ldock = outliner.get_left_outliner_dock()
    if ldock.docked:
        ldock.undock(close_split_area=True)
        return {"ok": True, "docked": False}
    return dock_left_outliner()


def _parent_floating_to_blender(widget: Any) -> None:
    """Make floating Qt `widget` an OS-owned window of Blender's GHOST HWND and clamp to screen."""
    if widget is None:
        return
    tcl = tentacle_bridge.get_tcl_instance()
    if tcl is not None and hasattr(tcl, "_parent_to_blender"):
        try:
            tcl._parent_to_blender(widget)
        except Exception:
            pass
    clamp_widget_to_screen(widget)


def clamp_widget_to_screen(widget: Any) -> Dict[str, int]:
    """Clamp a floating Qt widget's frame geometry inside the available screen work area (DPI & multi-monitor safe)."""
    try:
        from qtpy import QtGui, QtWidgets

        if widget is None:
            return {"x": 0, "y": 0, "width": 0, "height": 0}

        geom = widget.geometry()
        w = max(int(geom.width() or 320), 200)
        h = max(int(geom.height() or 280), 140)
        x = int(geom.x())
        y = int(geom.y())

        screen = None
        if hasattr(QtGui.QGuiApplication, "screenAt"):
            screen = QtGui.QGuiApplication.screenAt(geom.center())
        if screen is None:
            screen = QtGui.QGuiApplication.primaryScreen()

        if screen is not None:
            avail = screen.availableGeometry()
            w = min(w, max(200, int(avail.width() - 24)))
            h = min(h, max(140, int(avail.height() - 24)))
            x = max(int(avail.left() + 8), min(x, int(avail.right() - w - 8)))
            y = max(int(avail.top() + 8), min(y, int(avail.bottom() - h - 8)))
            widget.setGeometry(x, y, w, h)

        final_g = widget.geometry()
        return {
            "x": int(final_g.x()),
            "y": int(final_g.y()),
            "width": int(final_g.width()),
            "height": int(final_g.height()),
        }
    except Exception:
        return {"x": 0, "y": 0, "width": 0, "height": 0}


def _resolve_slots(ui_handler: Any, panel_id: str, ui_widget: Any) -> Optional[Any]:
    """Resolve the Switchboard `<Tool>Slots` controller instance for `panel_id`."""
    if ui_handler is None:
        return None
    sb = getattr(ui_handler, "sb", None)
    if sb is None:
        return None
    try:
        return sb.get_slots_instance(ui_widget or panel_id)
    except Exception:
        return None


def _ensure_panel_initialized(panel_id: str, ui_widget: Any, slots: Any) -> None:
    """Ensure deferred Switchboard `*_init` methods have run so headless & docked queries see live widgets."""
    if ui_widget is None or slots is None:
        return
    for attr_name in ("header", "cmb000", "txt000", "txt001", "tbl000"):
        child = getattr(ui_widget, attr_name, None)
        init_fn = getattr(slots, f"{attr_name}_init", None)
        if child is not None and callable(init_fn):
            if not getattr(child, "_studio_init_ensured", False):
                try:
                    init_fn(child)
                    child._studio_init_ensured = True
                except Exception:
                    pass


def get_panel_widget_and_slots(panel_id: str) -> Tuple[Optional[Any], Optional[Any]]:
    """Retrieve `(widget, slots)` for a canonical or Switchboard panel without showing it."""
    norm_id = (panel_id or "").strip().lower()
    if norm_id == "script_output":
        try:
            from blendertk.env_utils.script_output import ScriptConsole

            console = ScriptConsole.instance()
            widget = console._ensure_widget()
            return widget, console
        except Exception:
            return None, None

    handler = ensure_ui_handler()
    if handler is None:
        return None, None

    try:
        # The shared Switchboard already owns/caches this live panel. UiHandler
        # .get() reapplies the full theme on every lookup, even during a mode
        # handoff with the panel reparented. Repeated restyling crashed Qt's
        # style teardown. Initialize once; explicit theme actions still own
        # subsequent style changes.
        ui_widget = handler.sb.get_ui(norm_id.split('#',1)[0])
        if ui_widget is not None and not ui_widget.property('landfallStyleInitialized'):
            handler.apply_styles(ui_widget)
            ui_widget.setProperty('landfallStyleInitialized',True)
    except Exception:
        ui_widget = None
    if ui_widget is None:
        return None, None

    slots = _resolve_slots(handler, norm_id, ui_widget)
    _ensure_panel_initialized(norm_id, ui_widget, slots)

    if norm_id == "channels":
        from . import channel_history
        channel_history.ensure(slots)
        global _channels_default_filter_applied
        if not _channels_default_filter_applied and slots is not None:
            _channels_default_filter_applied = True
            try:
                slots.apply_launch_config(filter="Keyable")
            except Exception:
                pass
    elif norm_id in ("workspace_editor", "reference_manager"):
        root = workspace_bridge.get_project_root()
        if root:
            _sync_single_panel_root(norm_id, ui_widget, slots, root)

    return ui_widget, slots


def open_panel(
    panel_id: str,
    docked: Optional[bool] = None,
    dock: Optional[bool] = None,
    filter_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Open `panel_id` (`channels`, `reference_manager`, `workspace_editor`, `script_output`, or any Switchboard UI)."""
    if docked is None and dock is not None:
        docked = bool(dock)
    norm_id = (panel_id or "channels").strip().lower()
    hotkey_passthrough.install_hotkey_filter()
    ensure_selection_and_value_sync()

    if norm_id == "script_output":
        from blendertk.env_utils.script_output import ScriptConsole

        console = ScriptConsole.instance()
        console._begin_capture()
        console._show()
        widget = console._ensure_widget()
        if not console.is_open() and widget is not None:
            # Headless / offscreen fallback so widget is still constructible and testable
            try:
                widget.show()
            except Exception:
                pass
        _ensure_qt_events_flushed()
        info = _update_registry_entry(
            "script_output",
            widget=widget,
            slots=console,
            mode="DOCKED_BOTTOM" if console._dock.docked else "OPEN",
        )
        set_command_feedback(
            f"open_panel('{norm_id}')",
            f"Script Output open (docked={console._dock.docked})",
        )
        return info

    widget, slots = get_panel_widget_and_slots(norm_id)
    if widget is None:
        return {
            "panel_id": norm_id,
            "ok": False,
            "visible": False,
            "docked": False,
            "mode": "UNAVAILABLE",
        }

    if norm_id == "channels":
        if filter_mode and slots is not None:
            try:
                slots.apply_launch_config(filter=filter_mode)
            except Exception:
                pass
        else:
            sync_channels_now()

        # Default for Channels is right-docked (CHANNEL_BOX) unless docked=False is explicitly passed
        use_dock = True if docked is None else bool(docked)
        rdock = _get_right_dock()
        if use_dock:
            ok_dock = rdock.dock_channel_box(widget)
            if ok_dock or not rdock.supported():
                _ensure_qt_events_flushed()
                info = _update_registry_entry(
                    "channels",
                    widget=widget,
                    slots=slots,
                    mode="CHANNEL_BOX",
                )
                set_command_feedback("open_panel('channels')", "Channel Box docked right")
                return info

        # Floating / headless path
        if rdock.docked:
            rdock.undock_to_floating(parent_fn=_parent_floating_to_blender)
        else:
            _parent_floating_to_blender(widget)
            widget.show()
            try:
                widget.raise_()
            except Exception:
                pass
            rdock._mode = "FLOATING"
        _ensure_qt_events_flushed()
        info = _update_registry_entry(
            "channels",
            widget=widget,
            slots=slots,
            mode="FLOATING",
        )
        set_command_feedback("open_panel('channels', docked=False)", "Channels floating window open")
        return info

    # Standalone floating tool windows (`reference_manager`, `workspace_editor`, etc.)
    handler = ensure_ui_handler()
    try:
        if handler is not None:
            handler.show(widget)
        if not widget.isVisible():
            widget.show()
        _parent_floating_to_blender(widget)
        widget.raise_()
    except Exception:
        pass

    if norm_id in ("workspace_editor", "reference_manager"):
        root = workspace_bridge.get_project_root()
        if root:
            _sync_single_panel_root(norm_id, widget, slots, root)

    _ensure_qt_events_flushed()
    info = _update_registry_entry(
        norm_id,
        widget=widget,
        slots=slots,
        mode="FLOATING",
    )
    set_command_feedback(f"open_panel('{norm_id}')", f"{norm_id} open")
    return info


def close_panel(panel_id: str) -> Dict[str, Any]:
    """Close/hide `panel_id` cleanly (undocking if docked)."""
    norm_id = (panel_id or "").strip().lower()
    if norm_id == "script_output":
        widget = None
        console = None
        try:
            from blendertk.env_utils.script_output import ScriptConsole

            console = ScriptConsole.instance()
            widget = console.widget or console._ensure_widget()
            console._hide()
            if widget is not None:
                widget.hide()
        except Exception:
            pass
        _ensure_qt_events_flushed()
        info = _update_registry_entry("script_output", widget=widget, slots=console, mode="HIDDEN")
        info["ok"] = True
        return info

    if norm_id == "channels" and _right_dock is not None:
        _right_dock.undock(close_split_area=True)

    widget, slots = get_panel_widget_and_slots(norm_id)
    if widget is not None:
        try:
            widget.hide()
        except Exception:
            pass
    _ensure_qt_events_flushed()
    return _update_registry_entry(norm_id, widget=widget, slots=slots, mode="HIDDEN")


def dock_panel(panel_id: str, width: Optional[int] = None) -> Dict[str, Any]:
    """Dock `panel_id` (`channels` on the right, `script_output` at the bottom)."""
    norm_id = (panel_id or "channels").strip().lower()
    if norm_id == "script_output":
        return open_panel("script_output", docked=True)
    if norm_id == "channels":
        widget, slots = get_panel_widget_and_slots("channels")
        if widget is None:
            return {"panel_id": "channels", "ok": False, "docked": False, "mode": "UNAVAILABLE"}
        rdock = _get_right_dock()
        rdock.dock_channel_box(widget, width=width)
        sync_channels_now()
        _ensure_qt_events_flushed()
        return _update_registry_entry(
            "channels",
            widget=widget,
            slots=slots,
            mode=rdock.mode,
        )
    return open_panel(norm_id, docked=True)


def undock_panel(panel_id: str) -> Dict[str, Any]:
    """Undock `panel_id` from a Blender area to a floating owned Qt tool window (or hide for `script_output`)."""
    norm_id = (panel_id or "channels").strip().lower()
    if norm_id == "script_output":
        return close_panel("script_output")
    if norm_id == "channels":
        widget, slots = get_panel_widget_and_slots("channels")
        if widget is None:
            return {"panel_id": "channels", "ok": False, "docked": False, "mode": "UNAVAILABLE"}
        rdock = _get_right_dock()
        rdock.undock_to_floating(parent_fn=_parent_floating_to_blender)
        _ensure_qt_events_flushed()
        return _update_registry_entry(
            "channels",
            widget=widget,
            slots=slots,
            mode="FLOATING",
        )
    return open_panel(norm_id, docked=False)


def focus_panel(panel_id: str) -> Dict[str, Any]:
    """Raise and focus `panel_id`."""
    norm_id = (panel_id or "").strip().lower()
    widget, slots = get_panel_widget_and_slots(norm_id)
    if widget is None:
        return {"panel_id": norm_id, "ok": False}
    try:
        if not widget.isVisible():
            open_panel(norm_id)
        widget.raise_()
        widget.activateWindow()
        widget.setFocus()
        _ensure_qt_events_flushed()
    except Exception:
        pass
    return _update_registry_entry(
        norm_id,
        widget=widget,
        slots=slots,
        mode=_panel_registry.get(norm_id, {}).get("mode", "FLOATING"),
    )


def resize_panel(panel_id: str, width: int, height: int) -> Dict[str, Any]:
    """Resize `panel_id`'s Qt window and clamp it to the available screen geometry."""
    norm_id = (panel_id or "").strip().lower()
    widget, slots = get_panel_widget_and_slots(norm_id)
    if widget is None:
        return {"panel_id": norm_id, "ok": False}
    try:
        # Disable auto-fit on Channels when caller explicitly resizes the window
        if norm_id == "channels" and slots is not None:
            chk_fit = getattr(slots, "_chk_auto_fit", None)
            if chk_fit is not None and chk_fit.isChecked():
                chk_fit.setChecked(False)
        widget.resize(max(200, int(width)), max(140, int(height)))
        if not (_right_dock is not None and norm_id == "channels" and _right_dock.docked):
            clamp_widget_to_screen(widget)
        _ensure_qt_events_flushed()
    except Exception:
        pass
    return _update_registry_entry(
        norm_id,
        widget=widget,
        slots=slots,
        mode=_panel_registry.get(norm_id, {}).get("mode", "FLOATING"),
    )


def minimize_panel(panel_id: str) -> Dict[str, Any]:
    """Minimize a floating Qt panel window (`showMinimized()`)."""
    norm_id = (panel_id or "").strip().lower()
    widget, slots = get_panel_widget_and_slots(norm_id)
    if widget is None:
        return {"panel_id": norm_id, "ok": False, "minimized": False}
    try:
        widget.showMinimized()
        _ensure_qt_events_flushed()
    except Exception:
        pass
    info = _update_registry_entry(
        norm_id,
        widget=widget,
        slots=slots,
        mode=_panel_registry.get(norm_id, {}).get("mode", "FLOATING"),
    )
    info["minimized"] = bool(widget.isMinimized())
    return info


def restore_panel(panel_id: str) -> Dict[str, Any]:
    """Restore a minimized floating Qt panel window (`showNormal()`)."""
    norm_id = (panel_id or "").strip().lower()
    widget, slots = get_panel_widget_and_slots(norm_id)
    if widget is None:
        return {"panel_id": norm_id, "ok": False, "minimized": False}
    try:
        widget.showNormal()
        clamp_widget_to_screen(widget)
        _ensure_qt_events_flushed()
    except Exception:
        pass
    info = _update_registry_entry(
        norm_id,
        widget=widget,
        slots=slots,
        mode=_panel_registry.get(norm_id, {}).get("mode", "FLOATING"),
    )
    info["minimized"] = bool(widget.isMinimized())
    return info


def cycle_right_dock(target_mode: Any = "CYCLE") -> Dict[str, Any]:
    """Cycle the right-hand dock (`Ctrl+A` in Maya) between `CHANNEL_BOX`, `MODELING_TOOLKIT`, `HYPERSHADE`, `SHAPE_EDITOR`, `MAYA_INTERCHANGE`, `ATTRIBUTE_EDITOR`, `TOOL_SETTINGS`, `NATIVE_PROPERTIES`, or `HIDDEN`."""
    from . import hypershade_panel, interchange_panel

    rdock = _get_right_dock()
    widget, slots = get_panel_widget_and_slots("channels")
    if widget is None:
        return {"ok": False, "mode": "UNAVAILABLE", "docked": False}

    req = target_mode.upper() if isinstance(target_mode, str) else "CYCLE"
    cur = rdock.mode
    if req == "CYCLE":
        # Maya Classic Ctrl+A toggles Channel Box <-> Attribute Editor
        next_mode = "ATTRIBUTE_EDITOR" if cur == "CHANNEL_BOX" else "CHANNEL_BOX"
    elif req == "CYCLE_3":
        order = ("CHANNEL_BOX", "ATTRIBUTE_EDITOR", "TOOL_SETTINGS", "HIDDEN")
        idx = (order.index(cur) + 1) % len(order) if cur in order else 0
        next_mode = order[idx]
    elif req in (
        "CHANNEL_BOX",
        "MODELING_TOOLKIT",
        "HYPERSHADE",
        "SHAPE_EDITOR",
        "MAYA_INTERCHANGE",
        "ATTRIBUTE_EDITOR",
        "TOOL_SETTINGS",
        "MODIFIER_STACK",
        "ZBRUSH_STUDIO",
        "NATIVE_PROPERTIES",
        "HIDDEN",
    ):
        next_mode = req
    else:
        next_mode = "CHANNEL_BOX"

    if next_mode == "CHANNEL_BOX":
        rdock.dock_channel_box(widget)
        sync_channels_now()
    elif next_mode == "MODELING_TOOLKIT":
        rdock.show_modeling_toolkit()
    elif next_mode == "HYPERSHADE":
        rdock.show_hypershade()
        hypershade_panel.refresh_hypershade_widgets()
    elif next_mode == "SHAPE_EDITOR":
        rdock.show_shape_editor()
    elif next_mode == "MAYA_INTERCHANGE":
        rdock.show_maya_interchange()
        interchange_panel.refresh_interchange_widgets()
    elif next_mode == "ATTRIBUTE_EDITOR":
        rdock.show_attribute_editor(properties_context="OBJECT")
        attribute_editor.refresh_attribute_editor()
    elif next_mode == "TOOL_SETTINGS":
        rdock.show_tool_settings()
        tool_settings.refresh_tool_settings_widget()
    elif next_mode == "MODIFIER_STACK":
        rdock.show_modifier_stack()
    elif next_mode == "ZBRUSH_STUDIO":
        rdock.show_zbrush_studio()
    elif next_mode == "NATIVE_PROPERTIES":
        rdock.show_native_properties(properties_context="OBJECT")
    else:
        rdock.undock(close_split_area=True)
        try:
            widget.hide()
        except Exception:
            pass

    _ensure_qt_events_flushed()
    info = _update_registry_entry("channels", widget=widget, slots=slots, mode=rdock.mode)
    set_command_feedback(
        "landfall_studio.cycle_attribute_channels",
        f"Right Dock: {rdock.mode}",
    )
    return info


_tracked_bottom_graph_area: Any = None
_bottom_graph_state: Dict[str, Any] = {
    "open": False,
    "graph_type": "NONE",
    "ui_type": "",
}
_active_workspace_layout: str = "Modeling Standard"


def get_bottom_node_graph_state() -> Dict[str, Any]:
    return dict(_bottom_graph_state)


def get_active_workspace_layout() -> str:
    return _active_workspace_layout


def set_bottom_node_graph_split(
    enable: bool = True,
    graph_type: str = "SHADER",
    height_ratio: float = 0.35,
) -> Dict[str, Any]:
    """Split or close a bottom native Blender Node Graph (`ShaderNodeTree` or `GeometryNodeTree`) below the 3D Viewport."""
    global _tracked_bottom_graph_area, _bottom_graph_state
    import bpy
    import blendertk as btk
    from blendertk.ui_utils._ui_utils import _UiUtilsInternal

    gtype = (graph_type or "SHADER").upper()
    ui_type_map = {
        "SHADER": "ShaderNodeTree",
        "SHADER_EDITOR": "ShaderNodeTree",
        "GEOMETRY": "GeometryNodeTree",
        "GEOMETRY_NODES": "GeometryNodeTree",
        "GRAPH_EDITOR": "FCURVES",
        "DOPE_SHEET": "DOPESHEET",
        "ASSET_BROWSER": "ASSETS",
        "UV_EDITOR": "UV",
    }
    ui_type = ui_type_map.get(gtype, "GeometryNodeTree")

    rdock = _get_right_dock()
    if rdock._host_container is not None and hasattr(rdock._host_container, "btn_split_graph"):
        rdock._host_container.btn_split_graph.blockSignals(True)
        rdock._host_container.btn_split_graph.setChecked(bool(enable))
        rdock._host_container.btn_split_graph.blockSignals(False)

    if bpy.app.background:
        _bottom_graph_state = {
            "ok": True,
            "open": bool(enable),
            "graph_type": gtype if enable else "NONE",
            "ui_type": ui_type if enable else "",
        }
        return dict(_bottom_graph_state)

    window = btk.main_window()
    if window is None or window.screen is None:
        return {"ok": False, "open": False}

    # Check if tracked bottom graph area is still valid
    valid_tracked = None
    if _tracked_bottom_graph_area is not None:
        for a in window.screen.areas:
            try:
                if a.as_pointer() == _tracked_bottom_graph_area.as_pointer():
                    valid_tracked = a
                    break
            except Exception:
                pass

    if not enable:
        if valid_tracked is not None:
            try:
                btk.close_area(window, valid_tracked)
            except Exception:
                pass
        _tracked_bottom_graph_area = None
        _bottom_graph_state = {
            "ok": True,
            "open": False,
            "graph_type": "NONE",
            "ui_type": "",
        }
        return dict(_bottom_graph_state)

    if valid_tracked is None:
        v3ds = [a for a in window.screen.areas if a.type == "VIEW_3D"]
        if not v3ds:
            return {"ok": False, "open": False}
        target_v3d = max(v3ds, key=lambda a: a.width * a.height)
        before_ptrs = {a.as_pointer() for a in window.screen.areas}
        factor = max(0.22, min(0.50, float(height_ratio)))
        try:
            with bpy.context.temp_override(
                window=window,
                screen=window.screen,
                area=target_v3d,
                region=_UiUtilsInternal._window_region(target_v3d),
            ):
                res = bpy.ops.screen.area_split(direction="HORIZONTAL", factor=factor)
        except Exception:
            res = {"CANCELLED"}
        if res == {"FINISHED"}:
            candidates = [a for a in window.screen.areas if a.as_pointer() not in before_ptrs] + [target_v3d]
            valid_tracked = min(candidates, key=lambda a: a.y)
            _tracked_bottom_graph_area = valid_tracked

    if valid_tracked is not None:
        try:
            valid_tracked.ui_type = ui_type
            with bpy.context.temp_override(window=window, screen=window.screen, area=valid_tracked):
                for sp in valid_tracked.spaces:
                    if hasattr(sp, "show_region_ui") and sp.show_region_ui:
                        sp.show_region_ui = False
                    if hasattr(sp, "show_region_toolbar") and sp.show_region_toolbar:
                        sp.show_region_toolbar = False
                    if gtype == "SHADER" and hasattr(sp, "shader_type"):
                        sp.shader_type = "OBJECT"
            for r in valid_tracked.regions:
                r.tag_redraw()
        except Exception:
            pass

    _bottom_graph_state = {
        "ok": valid_tracked is not None,
        "open": valid_tracked is not None,
        "graph_type": gtype,
        "ui_type": ui_type,
    }
    return dict(_bottom_graph_state)


def apply_workspace_layout(preset_name: str) -> Dict[str, Any]:
    """Configure a full multi-pane Maya × Blender Workspace Layout (`Modeling Standard`, `Maya Classic`, `Lookdev / Hypershade`, `FX & Geometry Nodes`, `Rigging & Deform`, `Sculpt & Remesh Studio`, `Pipeline & .ma`)."""
    global _active_workspace_layout
    from .. import continuity
    from . import channel_box_ext, right_dock, shelf

    preset = (preset_name or "Modeling Standard").strip()
    if preset == "Sculpt & Remesh Studio":
        from .. import sculpt
        sculpt.enter()
        return {"ok": True, "workspace_layout": preset, "right_dock_mode": "ZBRUSH_STUDIO"}
    from .. import sculpt
    if sculpt.is_engaged():
        sculpt.return_to_maya()
    _active_workspace_layout = preset

    rdock = _get_right_dock()
    host = rdock._ensure_host_container()
    host.set_workspace_spine_preset(preset)

    split_info = {"open": False, "graph_type": "NONE", "ui_type": ""}
    target_right = "CHANNEL_BOX"
    target_shelf_idx = 1

    if preset == "Lookdev / Hypershade":
        target_right = "HYPERSHADE"
        target_shelf_idx = 3  # UV Shading
        continuity.set_maya_viewport_shading("7")
        cycle_right_dock("HYPERSHADE")
        split_info = set_bottom_node_graph_split(enable=True, graph_type="SHADER", height_ratio=0.34)
    elif preset == "FX & Geometry Nodes":
        target_right = "CHANNEL_BOX"
        target_shelf_idx = 5  # FX / Nodes
        channel_box_ext.ensure_procedural_geonodes_modifier()
        cycle_right_dock("CHANNEL_BOX")
        split_info = set_bottom_node_graph_split(enable=True, graph_type="GEOMETRY_NODES", height_ratio=0.34)
    elif preset == "Rigging & Deform":
        target_right = "SHAPE_EDITOR"
        target_shelf_idx = 4  # Deform Rigging
        split_info = set_bottom_node_graph_split(enable=False)
        cycle_right_dock("SHAPE_EDITOR")
    elif preset == "Sculpt & Remesh Studio":
        target_right = "TOOL_SETTINGS"
        target_shelf_idx = 5  # FX / Nodes
        split_info = set_bottom_node_graph_split(enable=False)
        cycle_right_dock("TOOL_SETTINGS")
    elif preset == "Pipeline & .ma":
        target_right = "MAYA_INTERCHANGE"
        target_shelf_idx = 6  # Pipeline
        split_info = set_bottom_node_graph_split(enable=False)
        cycle_right_dock("MAYA_INTERCHANGE")
    else:
        target_right = "CHANNEL_BOX"
        target_shelf_idx = 1  # Modeling
        split_info = set_bottom_node_graph_split(enable=False)
        cycle_right_dock("CHANNEL_BOX")

    host.set_workspace_spine_preset(preset)
    for sh in getattr(shelf, "_shelf_instances", ()):
        try:
            if target_shelf_idx < sh.tabs.count():
                sh.tabs.setCurrentIndex(target_shelf_idx)
        except Exception:
            pass
    from . import main_menu

    main_menu.sync_workspace_selector(preset)

    visible_spine_tabs = [
        k for k, btn in host.edge_tabs.items() if not btn.isHidden()
    ]
    set_command_feedback(
        f"apply_workspace_layout('{preset}')",
        f"Layout: {preset} • Right Dock: {target_right} • Spine Tabs: {len(visible_spine_tabs)} • Split Graph: {split_info.get('graph_type', 'NONE')}",
    )
    return {
        "ok": True,
        "workspace_layout": preset,
        "right_dock_mode": rdock.mode,
        "visible_spine_tabs": visible_spine_tabs,
        "bottom_node_graph": split_info,
        "torn_off_panels": [p["mode"] for p in right_dock.list_torn_off_panels()],
    }


def _update_registry_entry(
    panel_id: str,
    widget: Any,
    slots: Any,
    mode: str,
) -> Dict[str, Any]:
    visible = False
    minimized = False
    win_id = 0
    geom_dict = {"x": 0, "y": 0, "width": 0, "height": 0}
    title = panel_id

    if widget is not None:
        try:
            visible = bool(widget.isVisible())
            minimized = bool(widget.isMinimized())
            win_id = int(widget.internalWinId() or 0)
            g = widget.geometry()
            geom_dict = {
                "x": int(g.x()),
                "y": int(g.y()),
                "width": int(g.width()),
                "height": int(g.height()),
            }
            title = str(widget.windowTitle() or widget.objectName() or panel_id)
        except Exception:
            pass

    docked = False
    if panel_id == "channels" and _right_dock is not None:
        docked = bool(_right_dock.docked)
    elif panel_id == "script_output":
        try:
            from blendertk.env_utils.script_output import ScriptConsole

            docked = bool(ScriptConsole.instance()._dock.docked)
        except Exception:
            docked = False

    entry = {
        "panel_id": panel_id,
        "ok": widget is not None,
        "title": title,
        "visible": visible,
        "minimized": minimized,
        "docked": docked,
        "mode": mode,
        "win_id": win_id,
        "width": geom_dict["width"],
        "height": geom_dict["height"],
        "geometry": geom_dict,
    }
    _panel_registry[panel_id] = entry
    return dict(entry)


def get_registry_state() -> Dict[str, Any]:
    """Return a live snapshot of all registered Qt panels, docks, and Window Manager area counts."""
    import bpy

    for pid in list(_panel_registry.keys()):
        w, s = get_panel_widget_and_slots(pid)
        mode = _panel_registry[pid].get("mode", "HIDDEN")
        if pid == "channels" and _right_dock is not None:
            mode = _right_dock.mode
        _update_registry_entry(pid, w, s, mode)

    win = bpy.context.window_manager.windows[0] if bpy.context.window_manager and bpy.context.window_manager.windows else None
    area_types = [a.ui_type for a in win.screen.areas] if win and win.screen else []
    rdock_mode = _right_dock.mode if _right_dock is not None else "HIDDEN"
    rdock_docked = bool(_right_dock.docked) if _right_dock is not None else False
    rdock_qt_embedded = bool(_right_dock.is_qt_embedded) if _right_dock is not None else False
    top_shelf_docked = bool(_top_shelf_dock.docked) if _top_shelf_dock is not None else False
    left_outliner_docked = bool(outliner.get_left_outliner_dock().docked) if _registered else False
    time_slider_docked = bool(time_slider.get_bottom_time_slider_dock().docked) if _registered else False

    return {
        "registered": _registered,
        "panels": {k: dict(v) for k, v in _panel_registry.items()},
        "right_dock": {
            "mode": rdock_mode,
            "docked": rdock_docked,
            "qt_embedded": rdock_qt_embedded,
        },
        "right_dock_mode": rdock_mode,
        "right_dock_embedded": rdock_docked,
        "right_dock_qt_embedded": rdock_qt_embedded,
        "top_shelf_docked": top_shelf_docked,
        "top_shelf_embedded": top_shelf_docked,
        "left_outliner_docked": left_outliner_docked,
        "left_outliner_embedded": left_outliner_docked,
        "time_slider_docked": time_slider_docked,
        "time_slider_embedded": time_slider_docked,
        "hotkey_filter_installed": hotkey_passthrough.is_filter_installed(),
        "project_root": workspace_bridge.get_project_root(),
        "command_feedback": get_command_feedback(),
        "area_count": len(area_types),
        "area_ui_types": area_types,
    }


# --------------------------------------------------------------------------------------
# Selection & Live Transform / Property Sync (`Channels` + `SHAPES/INPUTS` + `Outliner` + `AE`)
# --------------------------------------------------------------------------------------

def _compute_selection_value_sig() -> Tuple[Any, ...]:
    """Compute a fast immutable signature of the current selection's names, transforms, locks, modifiers, shape keys, and frame."""
    try:
        import bpy
        from blendertk.core_utils._core_utils import CoreUtils

        scene = getattr(bpy.context, "scene", None)
        cur_frame = int(scene.frame_current) if scene is not None else 1
        objs = list(CoreUtils.selected_objects())
        active = CoreUtils.active_object()
        active_name = active.name if active is not None else ""
        parts: List[Any] = [active_name, len(objs)]
        for o in objs:
            try:
                loc = tuple(round(float(v), 5) for v in o.location)
                rot = tuple(round(float(v), 5) for v in o.rotation_euler)
                scl = tuple(round(float(v), 5) for v in o.scale)
                lk = (
                    tuple(bool(x) for x in o.lock_location),
                    tuple(bool(x) for x in o.lock_rotation),
                    tuple(bool(x) for x in o.lock_scale),
                )
                cprops = tuple(
                    (k, repr(o[k]))
                    for k in sorted(o.keys())
                    if not k.startswith("btk_")
                )
                inputs={n['node_name']:tuple((a['name'],repr(a['value'])) for a in n['attributes']) for n in channel_box_ext.get_object_inputs(o)}
                mods = tuple((m.name,m.type,m.show_viewport,m.show_render,m.show_in_editmode,m.show_on_cage,m.show_expanded,inputs.get(m.name,())) for m in getattr(o, "modifiers", ()))
                skeys = ()
                if getattr(o, "type", None) == "MESH" and getattr(o.data, "shape_keys", None) is not None:
                    skeys = tuple(
                        (kb.name, round(float(kb.value), 4), bool(kb.mute))
                        for kb in o.data.shape_keys.key_blocks
                    )
                vgroups = tuple(
                    (vg.name, bool(getattr(vg, "lock_weight", False)))
                    for vg in getattr(o, "vertex_groups", ())
                )
                parent_name = o.parent.name if o.parent is not None else ""
                shape_name = o.data.name if o.data is not None else ""
                materials=[]
                for slot in o.material_slots:
                    mat=slot.material
                    if mat is None:continue
                    values=[]
                    if mat.use_nodes and mat.node_tree:
                        for node in mat.node_tree.nodes:
                            if node.type!='BSDF_PRINCIPLED':continue
                            for name in ('Base Color','Metallic','Roughness','Coat Weight','Emission Color','Emission Strength'):
                                socket=node.inputs.get(name)
                                if socket is not None:
                                    value=socket.default_value
                                    values.append((node.name,name,round(float(value),5) if isinstance(value,(int,float)) else tuple(round(float(v),5) for v in value)))
                    materials.append((mat.name,mat.use_nodes,tuple(values)))
                topology=(len(o.data.vertices),len(o.data.edges),len(o.data.polygons),tuple(layer.name for layer in o.data.uv_layers)) if o.type=='MESH' else ()
                parts.append((o.name, parent_name, shape_name, loc, rot, scl, lk, mods, skeys, vgroups, cprops,tuple(materials),topology))
            except Exception:
                continue
        # The material browser can display unassigned shaders. Selection-only
        # fingerprints otherwise miss their edits and library additions/removals.
        from . import hypershade_panel
        browser_materials=[]
        for browser in hypershade_panel._hypershade_widgets:
            try:
                name=browser._selected_mat_name
                mat=bpy.data.materials.get(name)
                values=[]
                if mat is not None and mat.use_nodes and mat.node_tree:
                    for node in mat.node_tree.nodes:
                        if node.type=='BSDF_PRINCIPLED':
                            for field in ('Base Color','Metallic','Roughness','Coat Weight','Emission Color','Emission Strength'):
                                socket=node.inputs.get(field)
                                if socket is not None:
                                    value=socket.default_value
                                    values.append((node.name,field,round(float(value),5) if isinstance(value,(int,float)) else tuple(round(float(v),5) for v in value)))
                browser_materials.append((name,tuple(values)))
            except (RuntimeError,ReferenceError):continue
        parts.append(('MATERIAL_LIBRARY',tuple((mat.name,mat.users) for mat in bpy.data.materials),tuple(browser_materials)))
        return tuple(parts)
    except Exception:
        return ()


def _is_animation_playing() -> bool:
    try:
        import bpy
        scr = getattr(bpy.context, "screen", None)
        if scr is not None and getattr(scr, "is_animation_playing", False):
            return True
        wm = getattr(bpy.context, "window_manager", None)
        for win in (wm.windows if wm else ()):
            if win.screen is not None and getattr(win.screen, "is_animation_playing", False):
                return True
    except Exception:
        pass
    return False


def _on_time_changed(*_args) -> None:
    """Lightweight handler for `timeChanged`: updates Time Slider and Channel Box values without rebuilding Outliner/Hypershade/Interchange."""
    time_slider.refresh_time_slider_widgets()
    sync_channels_now()
    if not _is_animation_playing():
        shape_editor.refresh_shape_editor_widgets()
        attribute_editor.refresh_attribute_editor()


def _on_live_scene_or_depsgraph_update(*_args) -> None:
    """Refresh Qt panels when selection or object values change (skipping heavy panel rebuilds during active playback)."""
    global _last_selection_value_sig
    from ..modeling.live_surface import invalidate_live_surface_cache
    invalidate_live_surface_cache(_args[-1] if _args else None)
    if _is_animation_playing():
        sync_channels_now()
        return
    sig = _compute_selection_value_sig()
    if sig == _last_selection_value_sig:
        return
    previous = _last_selection_value_sig
    _last_selection_value_sig = sig
    from . import hypershade_panel, interchange_panel

    sync_channels_now()
    attribute_editor.refresh_attribute_editor()
    # Moving the same objects only changes channel numbers. Rebuilding every
    # scene panel here needlessly disturbs Qt layouts during viewport drags.
    def structure(value):
        return (value[:2], tuple((p[:3], p[6:]) for p in value[2:])) if value else None
    if previous and structure(previous) == structure(sig):
        return
    channel_box_ext.refresh_channel_box_extensions()
    modeling_toolkit.refresh_modeling_toolkit_widgets()
    shape_editor.refresh_shape_editor_widgets()
    interchange_panel.refresh_interchange_widgets()
    hypershade_panel.refresh_hypershade_widgets()
    time_slider.refresh_time_slider_widgets()
    shelf.refresh_top_shelf_status()
    tool_settings.refresh_tool_settings_widget()
    outliner.refresh_outliner()
    from . import modifier_stack

    modifier_stack.refresh_modifier_stack_widgets()


def _on_scene_or_undo_sync(*_args) -> None:
    """Re-synchronize Display Layers and all Maya panels after Undo, Redo, or SceneOpened."""
    global _last_selection_value_sig
    _last_selection_value_sig = None
    from ..commands.scene_edits import cancel_all
    cancel_all(restore=False)
    extension=channel_box_ext._channel_box_ext_instance
    if extension is not None:
        extension._presentation_signature=None
    channel_box_ext.sync_all_display_layers_from_scene()
    _on_live_scene_or_depsgraph_update()


def _on_scene_opened(*_args):
    """Rebind the existing desktop owners after Blender replaces its screen."""
    import bpy
    from ..commands.scene_edits import cancel_all
    cancel_all(restore=False)
    global _scene_restore_timer,_last_selection_value_sig
    _last_selection_value_sig=None
    _desktop_sizes.clear()
    if bpy.app.background:
        return _on_scene_or_undo_sync()
    if _scene_restore_timer is None:
        def restore():
            global _scene_restore_timer
            if not _registered:
                _scene_restore_timer=None;return None
            try:restore_workspace_desktop(restore_script_output=False)
            finally:_scene_restore_timer=None
            from .. import sculpt
            sculpt.sync_mode()
            _on_scene_or_undo_sync()
            return None
        _scene_restore_timer=restore
        bpy.app.timers.register(restore,first_interval=.4,persistent=True)
    from .. import sculpt
    sculpt.reset_after_file_load()
    from ..commands.registry import clear_history
    clear_history()
    from ..modeling.caddy import _active_caddy
    _active_caddy.update(open=False,snapshot=None,object_name='',params={},result_fingerprint=None)


def sync_window_size(window):
    """Keep inspector widths useful when Blender scales editor fractions.

    Called by the existing menu dock tick; manual divider changes are remembered
    while the window size is stable. Sculpt owns its separate shelf sizing.
    """
    from ..sculpt import layout,is_engaged
    if _scene_restore_timer is not None or layout.active or is_engaged() or len(window.screen.areas)<3:return
    if not all((_right_dock,_top_shelf_dock)):return
    owners={'right':_right_dock,'left':outliner.get_left_outliner_dock(),'top':_top_shelf_dock,'bottom':time_slider.get_bottom_time_slider_dock()}
    areas={name:owner._inner_dock.area for name,owner in owners.items()}
    if not all(areas.values()):return
    widget=_right_dock.host_widget
    if widget is None:return
    dpr=widget.devicePixelRatioF();extent=(window.width,window.height,dpr);key=window.as_pointer()
    previous=_desktop_sizes.get(key)
    if previous is not None and previous['extent']==extent:
        # Do not remember intermediate fractions while our resize owner is
        # still applying the preceding window-size change.
        if any(pending[0]==key for pending in layout._pending):return
        _desktop_sizes[key]={'extent':extent,'sizes':{name:(area.width/dpr,area.height/dpr) for name,area in areas.items()}}
        return
    if previous is None:
        # The first observed frame can already be a restored/small window.
        # Normalize it once instead of accepting unusably narrow fractions.
        previous={'extent':extent,'sizes':{name:(area.width/dpr,area.height/dpr) for name,area in areas.items()}}
        _desktop_sizes[key]=previous
    sizes=previous['sizes'];previous['extent']=extent
    logical_width=window.width/dpr
    minimum_right=max(360,widget.minimumSizeHint().width()+16)
    right=min(max(minimum_right,sizes['right'][0]),max(260,logical_width-180-240))
    left=max(180,min(sizes['left'][0],logical_width-right-240))
    # Window dimensions can update before Blender recomputes its area fractions.
    # Apply on the existing next-tick queue even when an old area momentarily
    # appears to match the new target; otherwise that target is lost on reflow.
    layout._defer_size(window,areas['left'],round(left*dpr),None,'RIGHT')
    layout._defer_size(window,areas['right'],round(right*dpr),None,'LEFT')
    layout._defer_size(window,areas['top'],None,round(max(116,sizes['top'][1])*dpr),'BOTTOM')
    layout._defer_size(window,areas['bottom'],None,round(max(94,sizes['bottom'][1])*dpr),'TOP')


def ensure_selection_and_value_sync() -> bool:
    """Subscribe our unified listener to `btk.ScriptJobManager` (once per session)."""
    try:
        from blendertk.core_utils.script_job_manager import ScriptJobManager

        mgr = ScriptJobManager.instance()
        mgr.unsubscribe_all(_DESKTOP_SYNC_OWNER)
        for ev in (
            "SelectionChanged",
            "DepsgraphUpdated",
        ):
            mgr.subscribe(
                ev,
                _on_live_scene_or_depsgraph_update,
                owner=_DESKTOP_SYNC_OWNER,
                ephemeral=False,
            )
        mgr.subscribe(
            "timeChanged",
            _on_time_changed,
            owner=_DESKTOP_SYNC_OWNER,
            ephemeral=False,
        )
        mgr.subscribe('SceneOpened',_on_scene_opened,owner=_DESKTOP_SYNC_OWNER,ephemeral=False)
        for ev in ("Undo", "Redo"):
            mgr.subscribe(
                ev,
                _on_scene_or_undo_sync,
                owner=_DESKTOP_SYNC_OWNER,
                ephemeral=False,
            )
        return True
    except Exception:
        return False


def _sync_channel_rows(widget, slots) -> None:
    """Keep Qt items/selection stable while only channel values are changing."""
    tbl = widget.tbl000
    objects = slots.controller.get_selected_nodes()
    key = slots._filter_key()
    rows, states = slots.controller.build_table_data(objects, key, slots._filter_invert)
    descriptors = slots.controller.collect_channels(objects, key, slots._filter_invert) if objects else []
    signature = (
        tuple(o.as_pointer() for o in objects), repr(descriptors), repr(states),
        key, slots._filter_invert, slots._filter_enabled, widget.txt000.text(),
    )
    values = {row[0]: str(row[slots.COL_VALUE]) for row in rows}
    names = [tbl.item(r, slots.COL_NAME).text() if tbl.item(r, slots.COL_NAME) else ""
             for r in range(tbl.rowCount())]
    if signature != getattr(slots, "_lf_live_rows_signature", None) or any(n not in values for n in names):
        # Selection, filters, locks, connections or channel definitions changed.
        # Leave their full presentation to the existing blendertk controller.
        enabled = tbl.updatesEnabled()
        tbl.setUpdatesEnabled(False)
        try:
            slots._refresh_table(tbl)
            slots._lf_live_rows_signature = signature
        finally:
            tbl.setUpdatesEnabled(enabled)
        return
    blocked = tbl.blockSignals(True)
    try:
        for row, name in enumerate(names):
            item = tbl.item(row, slots.COL_VALUE)
            value = values.get(name)
            if item is not None and value is not None and item.text() != value:
                item.setText(value)
    finally:
        tbl.blockSignals(blocked)


def sync_channels_now() -> Dict[str, Any]:
    """Force an immediate refresh of the `Channels` Qt table + `SHAPES/INPUTS/Layers` from Blender's live selection."""
    global _last_selection_value_sig
    widget, slots = get_panel_widget_and_slots("channels")
    if widget is None or slots is None:
        return {"ok": False, "target": "", "filter": "", "rows": {}}

    from .channel_history import sync_targets
    sync_targets(slots)
    # Avoid interrupting an active MMB scrub or open cell editor
    if getattr(slots, "_scrub_state", None) is not None:
        return get_channels_snapshot()

    tbl = getattr(widget, "tbl000", None)
    if tbl is not None:
        from qtpy import QtWidgets
        if tbl.state()==QtWidgets.QAbstractItemView.EditingState or hotkey_passthrough.is_editable_text_widget(tbl):
            return get_channels_snapshot()

    try:
        channel_box_ext.ensure_channel_box_extensions(widget)
        if _right_dock is not None and _right_dock.is_qt_embedded:
            chk_fit = getattr(slots, "_chk_auto_fit", None)
            if chk_fit is not None and chk_fit.isChecked():
                chk_fit.blockSignals(True)
                chk_fit.setChecked(False)
                chk_fit.blockSignals(False)
        if tbl is not None:
            _sync_channel_rows(widget, slots)
        channel_box_ext.refresh_channel_box_extensions()
        _last_selection_value_sig = _compute_selection_value_sig()
        _ensure_qt_events_flushed()
        if _right_dock is not None and _right_dock.is_qt_embedded:
            _right_dock.enforce_dock_geometry()
    except Exception:
        pass
    return get_channels_snapshot()


def get_channels_snapshot() -> Dict[str, Any]:
    """Read back the live `Channels` target text, active filter, `{channel_name: display_value}` map, `SHAPES`, `INPUTS`, `Display Layers`, and `Animation Layers`."""
    import bpy
    from .. import advanced

    widget, slots = get_panel_widget_and_slots("channels")
    if widget is None or slots is None:
        return {
            "ok": False,
            "target": "",
            "header": "",
            "filter": "",
            "row_count": 0,
            "rows": {},
            "channels": {},
            "shape": {},
            "inputs": [],
            "display_layers": [],
            "anim_layers": [],
        }

    target_txt = ""
    filter_txt = ""
    rows_map: Dict[str, str] = {}
    row_count = 0

    try:
        txt1 = getattr(widget, "txt001", None)
        if txt1 is not None:
            target_txt = str(txt1.text() or "")
        cmb = getattr(widget, "cmb000", None)
        if cmb is not None:
            filter_txt = str(cmb.currentText() or "")
        tbl = getattr(widget, "tbl000", None)
        if tbl is not None:
            row_count = int(tbl.rowCount())
            for r in range(row_count):
                n_item = tbl.item(r, slots.COL_NAME)
                v_item = tbl.item(r, slots.COL_VALUE)
                if n_item is not None and v_item is not None:
                    cname = str(n_item.text() or "").strip()
                    cval = str(v_item.text() or "").strip()
                    if cname:
                        rows_map[cname] = cval
    except Exception:
        pass

    active = getattr(bpy.context.view_layer.objects, "active", None) if getattr(bpy.context, "view_layer", None) else None
    return {
        "ok": True,
        "target": target_txt,
        "header": target_txt,
        "filter": filter_txt,
        "row_count": row_count,
        "rows": rows_map,
        "channels": rows_map,
        "selected_channels": channel_box_ext.get_selected_channel_names(),
        "shape": channel_box_ext.get_object_shape_info(active),
        "inputs": channel_box_ext.get_object_inputs(active),
        "display_layers": channel_box_ext.list_display_layers(),
        "anim_layers": advanced.list_anim_layers(active) if active is not None else [],
    }


def set_channel_value_from_ui(channel_name: str, value: Any) -> Dict[str, Any]:
    """Edit `channel_name` through the `Channels` UI table (`tbl000`), verifying two-way Qt -> Blender mutation."""
    widget, slots = get_panel_widget_and_slots("channels")
    if widget is None or slots is None:
        return {"ok": False, "error": "Channels panel unavailable"}

    sync_channels_now()
    tbl = getattr(widget, "tbl000", None)
    if tbl is None:
        return {"ok": False, "error": "Channels table unavailable"}

    target_row = -1
    for r in range(tbl.rowCount()):
        item = tbl.item(r, slots.COL_NAME)
        if item is not None and item.text().strip() == channel_name:
            target_row = r
            break

    if target_row < 0:
        return {"ok": False, "error": f"Channel '{channel_name}' not found in table"}

    val_item = tbl.item(target_row, slots.COL_VALUE)
    if val_item is None:
        return {"ok": False, "error": "Value cell item missing"}

    # Mutate cell text with signals enabled so ChannelsSlots._handle_cell_edit fires exactly like user input
    val_item.setText(str(value))
    _ensure_qt_events_flushed()

    snap = get_channels_snapshot()
    set_command_feedback(
        f"setAttr {snap.get('target', 'object')}.{channel_name} {value}",
        f"{channel_name} = {snap['rows'].get(channel_name, value)}",
    )
    return {
        "ok": True,
        "channel": channel_name,
        "row": target_row,
        "ui_value": snap["rows"].get(channel_name),
        "snapshot": snap,
    }


# --------------------------------------------------------------------------------------
# Canonical Project Root Sync (`Workspace Editor` + `Reference Manager` + `workspace_bridge`)
# --------------------------------------------------------------------------------------

def _sync_single_panel_root(
    panel_id: str,
    ui_widget: Any,
    slots: Any,
    norm_root: str,
) -> None:
    if ui_widget is None or slots is None or not norm_root:
        return
    try:
        txt0 = getattr(ui_widget, "txt000", None)
        if panel_id == "workspace_editor":
            if txt0 is not None and os.path.normpath(txt0.text().strip() or "") != norm_root:
                txt0.blockSignals(True)
                txt0.setText(norm_root)
                txt0.blockSignals(False)
            ui_widget.settings.setValue("workspace_root", norm_root)
            slots._load()
        elif panel_id == "reference_manager":
            if txt0 is not None and os.path.normpath(txt0.text().strip() or "") != norm_root:
                txt0.blockSignals(True)
                txt0.setText(norm_root)
                txt0.blockSignals(False)
            ui_widget.settings.setValue("root_dir", norm_root)
            slots._populate_workspaces()
    except Exception:
        pass


def sync_project_root_to_panels(root_path: str) -> Dict[str, Any]:
    """Propagate canonical `root_path` into live `Workspace Editor` and `Reference Manager` Qt panels."""
    if not root_path:
        return {
            "ok": False,
            "root": "",
            "project_root": "",
            "synced_panels": [],
            "workspace_editor_synced": False,
            "reference_manager_synced": False,
        }
    norm_root = os.path.normpath(root_path)
    handler = ensure_ui_handler()
    if handler is None:
        return {
            "ok": False,
            "root": norm_root,
            "project_root": norm_root,
            "synced_panels": [],
            "workspace_editor_synced": False,
            "reference_manager_synced": False,
        }

    sb = getattr(handler, "sb", None)
    loaded = getattr(sb, "loaded_ui", {}) if sb is not None else {}

    synced = []
    for pid in ("workspace_editor", "reference_manager"):
        if pid in loaded or pid in _panel_registry:
            w, s = get_panel_widget_and_slots(pid)
            if w is not None and s is not None:
                _sync_single_panel_root(pid, w, s, norm_root)
                synced.append(pid)

    _ensure_qt_events_flushed()
    return {
        "ok": True,
        "root": norm_root,
        "project_root": norm_root,
        "synced_panels": synced,
        "workspace_editor_synced": "workspace_editor" in synced,
        "reference_manager_synced": "reference_manager" in synced,
    }


def set_project_root_and_sync(root_path: str) -> Dict[str, Any]:
    """Set canonical project root in `workspace_bridge` + `btk` and propagate to all open Qt panels."""
    ws_res = workspace_bridge.set_project_root(root_path, write_workspace_mel=True)
    if isinstance(ws_res, dict):
        canonical = ws_res.get("project_root") or os.path.normpath(root_path)
    else:
        canonical = str(ws_res or os.path.normpath(root_path))
    panel_res = sync_project_root_to_panels(canonical)
    mel_exists = os.path.isfile(os.path.join(canonical, "workspace.mel"))
    return {
        "ok": bool(canonical),
        "project_root": canonical,
        "workspace_mel_created": mel_exists,
        "synced_panels": panel_res["synced_panels"],
        "workspace_editor_synced": panel_res["workspace_editor_synced"],
        "reference_manager_synced": panel_res["reference_manager_synced"],
    }


def _install_btk_workspace_hook() -> None:
    """Hook `btk.set_current_workspace` so root edits made inside Qt panels propagate back to `workspace_bridge`."""
    global _orig_btk_set_current_workspace
    if _orig_btk_set_current_workspace is not None:
        return
    try:
        import blendertk as btk

        _orig_btk_set_current_workspace = btk.set_current_workspace

        def _hooked_set_current_workspace(root):
            global _syncing_workspace_hook
            res = _orig_btk_set_current_workspace(root)
            if root and not _syncing_workspace_hook:
                _syncing_workspace_hook = True
                try:
                    workspace_bridge.set_project_root(
                        str(root), write_workspace_mel=False
                    )
                    sync_project_root_to_panels(str(root))
                except Exception:
                    pass
                finally:
                    _syncing_workspace_hook = False
            return res

        btk.set_current_workspace = _hooked_set_current_workspace
    except Exception:
        pass


def _uninstall_btk_workspace_hook() -> None:
    global _orig_btk_set_current_workspace
    if _orig_btk_set_current_workspace is None:
        return
    try:
        import blendertk as btk

        btk.set_current_workspace = _orig_btk_set_current_workspace
    except Exception:
        pass
    _orig_btk_set_current_workspace = None


# --------------------------------------------------------------------------------------
# Workspace Desktop Restore (Idempotent, Zero Duplicate Areas)
# --------------------------------------------------------------------------------------

_statusbar_saved: Dict[int, bool] = {}


def set_blender_statusbar_hidden(hidden: bool) -> Dict[str, Any]:
    """Hide Blender's own status bar (the Studio command line + help line replace it), or restore it."""
    import bpy

    changed = 0
    wm = bpy.context.window_manager
    for win in (wm.windows if wm else ()):
        scr = win.screen
        if scr is None:
            continue
        key = scr.as_pointer()
        try:
            # The update callback re-inits areas and needs a window in context (timers have none)
            with bpy.context.temp_override(window=win, screen=scr):
                if hidden:
                    _statusbar_saved.setdefault(key, bool(scr.show_statusbar))
                    if scr.show_statusbar:
                        scr.show_statusbar = False
                        changed += 1
                elif key in _statusbar_saved:
                    scr.show_statusbar = _statusbar_saved.pop(key)
                    changed += 1
        except Exception:
            pass
    if not hidden:
        _statusbar_saved.clear()
    _sync_statusbar_save_handlers(hidden)
    return {"ok": True, "hidden": hidden, "changed": changed}


_statusbar_hidden_before_save: bool = False


def _on_save_pre_show_statusbar(*_args) -> None:
    """`show_statusbar` is stored per screen in the .blend: save files with Blender's status bar visible."""
    global _statusbar_hidden_before_save
    _statusbar_hidden_before_save = bool(_statusbar_saved)
    if _statusbar_hidden_before_save:
        import bpy

        for win in bpy.context.window_manager.windows:
            if win.screen is not None and win.screen.as_pointer() in _statusbar_saved:
                with bpy.context.temp_override(window=win, screen=win.screen):
                    win.screen.show_statusbar = _statusbar_saved[win.screen.as_pointer()]


def _on_save_post_hide_statusbar(*_args) -> None:
    if _statusbar_hidden_before_save:
        import bpy

        for win in bpy.context.window_manager.windows:
            if win.screen is not None and win.screen.as_pointer() in _statusbar_saved:
                with bpy.context.temp_override(window=win, screen=win.screen):
                    win.screen.show_statusbar = False


def _sync_statusbar_save_handlers(install: bool) -> None:
    import bpy

    pairs = ((bpy.app.handlers.save_pre, _on_save_pre_show_statusbar), (bpy.app.handlers.save_post, _on_save_post_hide_statusbar))
    for handlers, fn in pairs:
        if install and fn not in handlers:
            handlers.append(fn)
        elif not install and fn in handlers:
            handlers.remove(fn)


def restore_workspace_desktop(
    dock_channels: bool = True,
    restore_script_output: bool = False,
    dock_shelf: bool = True,
    dock_outliner: bool = True,
    dock_time_slider_bar: bool = True,
    apply_theme: bool = True,
    dock_menu_bar: bool = True,
    hide_blender_statusbar: bool = True,
) -> Dict[str, Any]:
    """Idempotently restore the Modern Maya Studio desktop layout without creating duplicate Blender areas."""
    import bpy

    win = bpy.context.window_manager.windows[0] if bpy.context.window_manager and bpy.context.window_manager.windows else None
    areas_before = len(win.screen.areas) if win and win.screen else 0

    hotkey_passthrough.install_hotkey_filter()
    ensure_selection_and_value_sync()
    _install_btk_workspace_hook()

    root = workspace_bridge.get_project_root()
    if root:
        sync_project_root_to_panels(root)

    if dock_outliner:
        dock_left_outliner()

    if dock_shelf:
        dock_top_shelf()

    if dock_channels:
        dock_panel("channels")

    if dock_time_slider_bar:
        dock_time_slider()

    if dock_menu_bar:
        from . import main_menu

        main_menu.dock_main_menu()

    if hide_blender_statusbar:
        set_blender_statusbar_hidden(True)

    if restore_script_output:
        open_panel("script_output", docked=True)

    if apply_theme:
        style.apply_modern_maya_theme_to_blender(bpy.context)

    from . import viewport_bar
    viewport_bar.register()

    areas_after = len(win.screen.areas) if win and win.screen else 0
    return {
        "ok": True,
        "areas_before": areas_before,
        "areas_after": areas_after,
        "right_dock_mode": _right_dock.mode if _right_dock is not None else "HIDDEN",
        "top_shelf_docked": bool(_top_shelf_dock.docked) if _top_shelf_dock is not None else False,
        "left_outliner_docked": bool(outliner.get_left_outliner_dock().docked),
        "time_slider_docked": bool(time_slider.get_bottom_time_slider_dock().docked),
        "hotkey_filter_installed": hotkey_passthrough.is_filter_installed(),
    }


# --------------------------------------------------------------------------------------
# Bottom Command / Result Feedback Strip
# --------------------------------------------------------------------------------------

def set_command_feedback(
    command: str,
    result: str,
    level: str = "INFO",
    echo_to_console: bool = False,
) -> Dict[str, Any]:
    """Update the Studio command/result feedback strip and mirror to Blender's status bar."""
    lvl = str(level or "INFO").upper()
    cmd_str = str(command or "")
    res_str = str(result or "")
    _command_feedback.update(
        {
            "ok": lvl != "ERROR",
            "command": cmd_str,
            "last_command": cmd_str,
            "result": res_str,
            "last_result": res_str,
            "level": lvl,
            "is_error": lvl == "ERROR",
            "timestamp": time.monotonic(),
        }
    )
    try:
        import bpy

        ws = getattr(bpy.context, "workspace", None)
        if ws is not None and hasattr(ws, "status_text_set"):
            ws.status_text_set(
                f"Python: {_command_feedback['command']}  |  Result: {_command_feedback['result']}"
            )
    except Exception:
        pass

    if echo_to_console:
        print(f"// Result: {_command_feedback['result']} ({_command_feedback['command']})")

    try:
        time_slider.refresh_time_slider_widgets()
    except Exception:
        pass

    return dict(_command_feedback)


def get_command_feedback() -> Dict[str, Any]:
    """Return the current command/result feedback strip state."""
    return dict(_command_feedback)


def execute_command_string(expr: str, context: Any = None) -> Dict[str, Any]:
    """Execute a Python or Studio command line expression from the bottom command strip and report result."""
    clean = (expr or "").strip()
    if not clean:
        return set_command_feedback("", "No command entered", level="WARNING")

    import bpy
    import blendertk as btk
    from .. import commands

    ns = {
        "bpy": bpy,
        "btk": btk,
        "context": context or bpy.context,
        "commands": commands,
        "workspace_bridge": workspace_bridge,
    }
    try:
        try:
            val = eval(clean, ns, ns)
            res_str = repr(val) if val is not None else "OK"
        except SyntaxError:
            exec(clean, ns, ns)
            res_str = "Executed"
        return set_command_feedback(clean, res_str, level="INFO", echo_to_console=True)
    except Exception as exc:
        return set_command_feedback(
            clean, f"Error: {exc}", level="ERROR", echo_to_console=True
        )


# --------------------------------------------------------------------------------------
# Lifecycle (register / unregister) + Blender Operators
# --------------------------------------------------------------------------------------

def register() -> None:
    """Initialize Qt desktop hooks, selection/value notifier, and hotkey passthrough filter."""
    global _registered
    _registered = True
    hotkey_passthrough.install_hotkey_filter()
    ensure_selection_and_value_sync()
    _install_btk_workspace_hook()


def unregister() -> None:
    """Cleanly tear down all docks, theme overrides, hotkey passthrough filter, ScriptJobManager subscriptions, and workspace hooks."""
    global _registered, _right_dock, _top_shelf_dock, _last_selection_value_sig, _channels_default_filter_applied
    global _cached_ui_handler, _cached_ui_handler_tcl_id
    global _scene_restore_timer
    import bpy
    if _scene_restore_timer is not None and bpy.app.timers.is_registered(_scene_restore_timer):bpy.app.timers.unregister(_scene_restore_timer)
    _scene_restore_timer=None

    from . import viewport_bar
    viewport_bar.unregister()

    _cached_ui_handler = None
    _cached_ui_handler_tcl_id = None
    hotkey_passthrough.uninstall_hotkey_filter()
    hotkey_passthrough.clear_passthrough_history()
    _uninstall_btk_workspace_hook()

    try:
        from blendertk.core_utils.script_job_manager import ScriptJobManager

        ScriptJobManager.instance().unsubscribe_all(_DESKTOP_SYNC_OWNER)
    except Exception:
        pass

    try:
        from . import hybrid_window, main_menu, modifier_stack

        hybrid_window.teardown_editor_windows()
        main_menu.teardown_main_menu()
        modifier_stack.teardown_modifier_stack_widgets()
    except Exception:
        pass
    try:
        set_blender_statusbar_hidden(False)
    except Exception:
        pass

    if _top_shelf_dock is not None:
        try:
            _top_shelf_dock.teardown()
        except Exception:
            pass
        _top_shelf_dock = None

    try:
        outliner.teardown_outliner()
    except Exception:
        pass

    try:
        time_slider.teardown_time_slider()
    except Exception:
        pass

    if _right_dock is not None:
        try:
            _right_dock.teardown()
        except Exception:
            pass
        _right_dock = None

    for pid in list(_panel_registry.keys()):
        try:
            close_panel(pid)
        except Exception:
            pass
    _panel_registry.clear()

    from . import channel_history
    channel_history.teardown()

    try:
        style.restore_blender_theme()
    except Exception:
        pass

    _last_selection_value_sig = None
    _channels_default_filter_applied = False
    _registered = False

    try:
        import bpy

        ws = getattr(bpy.context, "workspace", None)
        if ws is not None and hasattr(ws, "status_text_set"):
            ws.status_text_set(None)
    except Exception:
        pass


try:
    import bpy
except ImportError:
    bpy = None

if bpy is not None:

    class LANDFALL_STUDIO_OT_open_qt_panel(bpy.types.Operator):
        """Open a canonical Landfall Studio Qt desktop panel (`channels`, `reference_manager`, `workspace_editor`, `script_output`)."""

        bl_idname = "landfall_studio.open_qt_panel"
        bl_label = "Open Studio Qt Panel"
        bl_description = "Open Channels, Reference Manager, Workspace Editor, or Script Output"

        panel_id: bpy.props.StringProperty(
            name="Panel ID",
            default="channels",
            options={"SKIP_SAVE"},
        )
        docked: bpy.props.BoolProperty(
            name="Docked",
            default=True,
            options={"SKIP_SAVE"},
        )

        def execute(self, context):
            info = open_panel(self.panel_id, docked=self.docked)
            if not info.get("ok"):
                self.report(
                    {"WARNING"},
                    f"Could not open panel '{self.panel_id}' (Qt dependencies may not be installed).",
                )
                return {"CANCELLED"}
            self.report(
                {"INFO"},
                f"Opened {self.panel_id} (mode={info.get('mode')}, docked={info.get('docked')})",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_cycle_attribute_channels(bpy.types.Operator):
        """Cycle the right-hand dock between Maya's Channel Box (`Channels` Qt dock), Attribute Editor, and Tool Settings."""

        bl_idname = "landfall_studio.cycle_attribute_channels"
        bl_label = "Cycle Channel Box / Attribute Editor (Ctrl+A)"
        bl_description = "Cycle the right-hand dock between the Qt Channel Box, Attribute Editor, and Tool Settings"

        mode: bpy.props.EnumProperty(
            name="Mode",
            items=(
                ("CYCLE", "Cycle (Channel Box <-> Attribute Editor)", "Toggle between Channel Box and Attribute Editor"),
                ("CYCLE_3", "Cycle 3-Way (Channel Box -> Attribute Editor -> Tool Settings -> Hidden)", "Cycle all right-sidebar modes"),
                ("CHANNEL_BOX", "Channel Box", "Show the docked Qt Channel Box"),
                ("MODELING_TOOLKIT", "Modeling Toolkit", "Show the Maya Modeling Toolkit"),
                ("HYPERSHADE", "Hypershade", "Show the Maya Hypershade Material Browser & Lookdev dock"),
                ("SHAPE_EDITOR", "Shape / Skin Editor", "Show the Maya Shape Editor & Skin Weights dock"),
                ("MAYA_INTERCHANGE", "Maya Interchange & References", "Show the Maya .ma/.mb Interchange & Reference Manager"),
                ("ATTRIBUTE_EDITOR", "Attribute Editor", "Show the Maya Attribute Editor"),
                ("TOOL_SETTINGS", "Tool Settings", "Show the Maya Tool Settings & Option Box inspector"),
                ("NATIVE_PROPERTIES", "Native Properties", "Show native Blender Properties editor"),
                ("HIDDEN", "Hidden", "Hide the right-docked Channel Box overlay"),
            ),
            default="CYCLE",
            options={"SKIP_SAVE"},
        )

        def execute(self, context):
            info = cycle_right_dock(self.mode)
            if not info.get("ok"):
                self.report({"WARNING"}, "Channel Box / Attribute Editor cycle unavailable.")
                return {"CANCELLED"}
            self.report({"INFO"}, f"Right Dock: {info.get('mode')}")
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_toggle_script_output(bpy.types.Operator):
        """Toggle the docked `Script Output` (`ScriptConsole`) panel at the bottom of the Blender window."""

        bl_idname = "landfall_studio.toggle_script_output"
        bl_label = "Toggle Script Output"
        bl_description = "Show or hide the docked blendertk Script Output console"

        def execute(self, context):
            try:
                from blendertk.env_utils.script_output import ScriptConsole

                if ScriptConsole.instance().is_open():
                    close_panel("script_output")
                    self.report({"INFO"}, "Script Output hidden")
                else:
                    open_panel("script_output", docked=True)
                    self.report({"INFO"}, "Script Output shown")
                return {"FINISHED"}
            except Exception as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}

    class LANDFALL_STUDIO_OT_execute_command_line(bpy.types.Operator):
        """Execute a Python / Studio expression in the bottom command strip and update the result display."""

        bl_idname = "landfall_studio.execute_command_line"
        bl_label = "Execute Studio Command Line"
        bl_description = "Execute a Python or Studio command and display the result in the bottom feedback strip"

        command: bpy.props.StringProperty(
            name="Command",
            default="",
            options={"SKIP_SAVE"},
        )

        def execute(self, context):
            fb = execute_command_string(self.command)
            lvl = "ERROR" if fb["level"] == "ERROR" else "INFO"
            self.report({lvl}, f"{fb['command']} -> {fb['result']}")
            return {"FINISHED"} if lvl != "ERROR" else {"CANCELLED"}

    class LANDFALL_STUDIO_OT_maya_poly_primitive(bpy.types.Operator):
        """Create a Maya-named polygon primitive (`pCube1`, `pSphere1`, etc.) with `SHAPES` and live `INPUTS` construction history."""

        bl_idname = "landfall_studio.maya_poly_primitive"
        bl_label = "Create Maya Polygon Primitive"
        bl_description = "Create a polygon primitive with a Maya Shape name and live parametric INPUTS construction history"
        bl_options = {"REGISTER", "UNDO"}

        primitive_type: bpy.props.EnumProperty(
            name="Primitive",
            items=(
                ("CUBE", "Polygon Cube", "Create pCube with polyCube history"),
                ("SPHERE", "Polygon Sphere", "Create pSphere with polySphere history"),
                ("CYLINDER", "Polygon Cylinder", "Create pCylinder with polyCylinder history"),
                ("PLANE", "Polygon Plane", "Create pPlane with polyPlane history"),
            ),
            default="CUBE",
        )
        width: bpy.props.FloatProperty(name="Width", default=2.0, min=0.001, max=1000.0)
        height: bpy.props.FloatProperty(name="Height", default=2.0, min=0.001, max=1000.0)
        depth: bpy.props.FloatProperty(name="Depth", default=2.0, min=0.001, max=1000.0)
        radius: bpy.props.FloatProperty(name="Radius", default=1.0, min=0.001, max=1000.0)
        subdivisions_x: bpy.props.IntProperty(name="Subdivisions X", default=1, min=1, max=128)
        subdivisions_y: bpy.props.IntProperty(name="Subdivisions Y", default=1, min=1, max=128)
        subdivisions_z: bpy.props.IntProperty(name="Subdivisions Z", default=1, min=1, max=128)

        def execute(self, context):
            from .. import commands

            ptype = self.primitive_type
            kwargs = {"primitive_type": ptype}
            if ptype == "CUBE":
                kwargs.update(
                    width=self.width,
                    height=self.height,
                    depth=self.depth,
                    subdivisions_x=self.subdivisions_x,
                    subdivisions_y=self.subdivisions_y,
                    subdivisions_z=self.subdivisions_z,
                )
            elif ptype == "SPHERE":
                sx = self.subdivisions_x if self.subdivisions_x > 2 else 20
                sy = self.subdivisions_y if self.subdivisions_y > 2 else 16
                kwargs.update(radius=self.radius, subdivisions_x=sx, subdivisions_y=sy)
            elif ptype == "CYLINDER":
                sx = self.subdivisions_x if self.subdivisions_x > 2 else 20
                kwargs.update(
                    radius=self.radius,
                    height=self.height,
                    subdivisions_x=sx,
                    subdivisions_y=self.subdivisions_y,
                    subdivisions_z=self.subdivisions_z,
                )
            elif ptype == "PLANE":
                kwargs.update(
                    width=self.width,
                    height=self.height,
                    subdivisions_x=self.subdivisions_x,
                    subdivisions_y=self.subdivisions_y,
                )

            res = channel_box_ext.create_maya_primitive(**kwargs)
            commands.record_command(
                cmd_id="landfall_studio.maya_poly_primitive",
                kwargs=dict(kwargs),
                callable_fn=channel_box_ext.create_maya_primitive,
                label=f"Create Maya {ptype.title()}",
                repeatable=True,
            )
            sync_channels_now()
            outliner.refresh_outliner()
            return {"FINISHED"} if res.get("ok") else {"CANCELLED"}

    class LANDFALL_STUDIO_OT_delete_history(bpy.types.Operator):
        """Maya `Edit > Delete by Type > History` (`Alt+Shift+D`): apply modifiers and clear parametric creation history."""

        bl_idname = "landfall_studio.delete_history"
        bl_label = "Delete Construction History (Alt+Shift+D)"
        bl_description = "Apply mesh modifiers in order and clear parametric INPUTS history on the active object"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            res = channel_box_ext.delete_construction_history()
            if not res.get("ok"):
                self.report({"WARNING"}, str(res.get("error", "Could not delete history")))
                return {"CANCELLED"}
            sync_channels_now()
            attribute_editor.refresh_attribute_editor()
            outliner.refresh_outliner()
            set_command_feedback("DeleteHistory", f"{res.get('object_name')} (remaining inputs={res.get('remaining_inputs')})")
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_open_tool_settings(bpy.types.Operator):
        """Open the Maya `Tool Settings` & Option Box (`□`) inspector in the right dock."""

        bl_idname = "landfall_studio.open_tool_settings"
        bl_label = "Open Tool Settings (Option Box □)"
        bl_description = "Open the Maya Tool Settings & Option Box inspector for the specified tool"

        tool_context: bpy.props.StringProperty(
            name="Tool Context",
            default="TRANSLATE",
            options={"SKIP_SAVE"},
        )
        tool_id: bpy.props.StringProperty(
            name="Tool ID",
            default="",
            options={"SKIP_SAVE"},
        )

        def execute(self, context):
            target_ctx = self.tool_id or self.tool_context
            tool_settings.set_tool_setting("tool_context", target_ctx)
            cycle_right_dock("TOOL_SETTINGS")
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_outliner_reparent(bpy.types.Operator):
        """Maya Outliner `MMB` world-preserving reparenting operator (`bl_options = {'REGISTER', 'UNDO'}`)."""

        bl_idname = "landfall_studio.outliner_reparent"
        bl_label = "Reparent DAG Node (Preserve World)"
        bl_description = "Reparent child object under parent object (or world root) while preserving world-space transform"
        bl_options = {"REGISTER", "UNDO"}

        child_name: bpy.props.StringProperty(name="Child Object", default="", options={"SKIP_SAVE"})
        parent_name: bpy.props.StringProperty(name="Parent Object", default="", options={"SKIP_SAVE"})

        def execute(self, context):
            res = outliner.reparent_preserve_world(self.child_name, self.parent_name)
            if not res.get("ok"):
                self.report({"WARNING"}, str(res.get("error", "Reparent failed")))
                return {"CANCELLED"}
            sync_channels_now()
            outliner.refresh_outliner()
            set_command_feedback(
                f"parent {self.child_name} {self.parent_name or '-world'}",
                f"max_diff={res.get('max_matrix_diff')}",
            )
            return {"FINISHED"}

    UI_CLASSES = (
        LANDFALL_STUDIO_OT_open_qt_panel,
        LANDFALL_STUDIO_OT_cycle_attribute_channels,
        LANDFALL_STUDIO_OT_toggle_script_output,
        LANDFALL_STUDIO_OT_execute_command_line,
        LANDFALL_STUDIO_OT_maya_poly_primitive,
        LANDFALL_STUDIO_OT_delete_history,
        LANDFALL_STUDIO_OT_open_tool_settings,
        LANDFALL_STUDIO_OT_outliner_reparent,
    )
else:
    UI_CLASSES = ()
