"""Phase 11 GUI capture: rev 2 desktop + Phase 1 hybrid windows and Modifier Stack (`tests/test_phase11_gui.py`).

Launches a fresh Blender GUI (never attach to a running one):
    blender --factory-startup --python tests/test_phase11_gui.py

Shots (written to `output/` and the agent pack output folder):
1. `phase11_desktop_rev2.png`        Main Menu Bar over Blender's top bar, Maya-order Status Line, shelf,
                                       tool rail + quick layouts, Outliner menus, right dock with outer-edge tabs,
                                       Channel Box menus, Layer Editor (Display / Render / Anim), Help Line.
2. `phase11_modifier_stack_dock.png` Right dock on the Modifier Stack tab + the remapped Windows menu open.
3. `phase11_geometry_node_window.png` Hybrid Geometry Node Editor window: native canvas + Spreadsheet + Qt Group Inputs.
4. `phase11_modifier_stack_floating.png` Floating Modifier Stack tear-off over the desktop.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (str(REPO_ROOT), str(REPO_ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import landfall_studio
from landfall_studio import continuity, ui
from landfall_studio.ui import channel_box_ext, desktop, hybrid_window, main_menu, modifier_stack, right_dock, shelf, style
import test_phase10_gui as p10

OUT_DIRS = [REPO_ROOT / "output", p10.AGENT_OUT_DIR]
_stage = 0
_results: dict = {"ok": False, "shots": {}, "checks": {}}
_menu_overlay = None  # (QMenu, client_x, client_y) composited into shot 2


def _show_viewport_chrome() -> None:
    """Hide Blender's per-viewport header/toolbar but keep the navigation gizmo (Maya's ViewCube)."""
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                # Region-visibility updates need a window in context (a timer has none) or Blender crashes
                with bpy.context.temp_override(window=win, screen=win.screen, area=area):
                    for sp in area.spaces:
                        if sp.type == "VIEW_3D":
                            sp.show_region_toolbar = False
                            sp.show_region_header = False
                            sp.show_region_tool_header = False
                            sp.show_gizmo = True
                            sp.show_gizmo_navigate = True
                for r in area.regions:
                    r.tag_redraw()


def _grab_into(painter, widget, rect, app):
    from qtpy import QtCore

    if widget is None or rect is None:
        return False
    x, y, w, h = rect
    hint = widget.minimumSizeHint()
    _results.setdefault("sizes", {})[widget.objectName() or type(widget).__name__] = {"rect": [int(w), int(h)], "min_hint": [hint.width(), hint.height()]}
    widget.resize(int(w), int(h))
    if app is not None:
        app.processEvents()
    painter.drawPixmap(QtCore.QRect(int(x), int(y), int(w), int(h)), widget.grab())
    return True


def _capture(shot: str, window=None, extra=()):
    """Screenshot `window` (default main) and composite every Qt surface embedded in it."""
    import ctypes
    from qtpy import QtCore, QtGui, QtWidgets
    import blendertk as btk
    from blendertk.ui_utils.blender_window import BlenderWindow

    win = window or btk.main_window()
    for d in OUT_DIRS:
        d.mkdir(parents=True, exist_ok=True)
    target = OUT_DIRS[0] / shot
    hwnd = BlenderWindow.window_hwnd(win)
    if hwnd:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    area = next((a for a in win.screen.areas if a.ui_type in ("VIEW_3D", "GeometryNodeTree")), win.screen.areas[0])
    region = next((r for r in area.regions if r.type == "WINDOW"), area.regions[0])
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        bpy.ops.screen.screenshot(filepath=str(target))

    pix = QtGui.QPixmap(str(target))
    composited = []
    painter = QtGui.QPainter(pix)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
    try:
        if window is None:
            mdock = main_menu.get_main_menu_dock()
            if _grab_into(painter, mdock.widget, mdock.enforce_dock_geometry(), app):
                composited.append("main_menu")
            sdock = desktop._get_top_shelf_dock()
            if _grab_into(painter, sdock.widget, sdock.enforce_dock_geometry() or sdock._inner_dock._last_rect, app):
                composited.append("status_line_shelf")
            ldock = desktop._get_left_outliner_dock()
            if _grab_into(painter, ldock.widget, ldock.enforce_dock_geometry() or ldock._inner_dock._last_rect, app):
                composited.append("tool_rail_outliner")
            rdock = desktop._get_right_dock()
            if _grab_into(painter, rdock.host_widget, rdock.enforce_dock_geometry() or rdock._inner_dock._last_rect, app):
                composited.append("right_dock")
            tdock = ui.time_slider.get_bottom_time_slider_dock()
            if _grab_into(painter, tdock.widget, tdock.enforce_dock_geometry() or tdock._inner_dock._last_rect, app):
                composited.append("time_slider_help_line")
            for t in right_dock.list_torn_off_panels():
                if _grab_into(painter, t["widget"], t["rect"], app):
                    composited.append(f"tear_off:{t['mode']}")
        for widget, rect, label in extra:
            if _grab_into(painter, widget, rect, app):
                composited.append(label)
        if _menu_overlay is not None and window is None:
            menu, mx, my = _menu_overlay
            painter.drawPixmap(int(mx), int(my), menu.grab())
            composited.append("windows_menu")
    finally:
        painter.end()
    for d in OUT_DIRS:
        pix.save(str(d / shot))
    _results["shots"][shot] = composited
    return composited


def _open_windows_menu():
    """Pop the Main Menu Bar's Windows menu so the shot shows the remapped editor list."""
    global _menu_overlay
    from qtpy import QtCore, QtWidgets

    bar = main_menu.get_main_menu_dock().ctrl
    act = next(a for a in bar.menubar.actions() if a.text() == "Windows")
    menu = act.menu()
    geo = bar.menubar.actionGeometry(act)
    origin = bar.menubar.mapTo(bar.root, geo.bottomLeft())
    rect = main_menu.get_main_menu_dock()._last_rect or (0, 0, 0, 32)
    menu.popup(bar.menubar.mapToGlobal(geo.bottomLeft()))
    QtWidgets.QApplication.instance().processEvents()
    _menu_overlay = (menu, rect[0] + origin.x(), rect[1] + origin.y())


def _step():
    global _stage, _menu_overlay
    try:
        if _stage == 0:
            bpy.context.preferences.view.show_splash = False
            bpy.ops.wm.read_homefile()
            p10._maximize_and_bring_to_front()
            landfall_studio.register()
            _results["desktop"] = ui.restore_workspace_desktop(dock_channels=True, restore_script_output=False)
            _show_viewport_chrome()
            _stage = 1
            return 0.6

        if _stage == 1:
            _show_viewport_chrome()
            hero = p10._setup_hero_eevee_scene()
            modifier_stack.add_modifier("BEVEL", hero)
            hero.modifiers[-1].show_expanded = True
            modifier_stack.add_modifier("WEIGHTED_NORMAL", hero)
            modeling_obj = hero
            continuity.set_maya_viewport_shading("7")
            desktop.apply_workspace_layout("Modeling Standard")
            desktop.sync_channels_now()
            channel_box_ext.refresh_channel_box_extensions()
            shelf.refresh_top_shelf_status()
            ui.refresh_time_slider_widgets()
            desktop.set_command_feedback("apply_workspace_layout('Modeling Standard')", "Modeling Standard · Channel Box · Viewport 2.0 (EEVEE)")
            p10._frame_viewport_camera(dist=5.1)
            _results["checks"]["menu_titles"] = main_menu.get_main_menu_dock().ctrl.menu_titles() if main_menu.get_main_menu_dock().ctrl else []
            _results["checks"]["statusbar_hidden"] = not bpy.context.window_manager.windows[0].screen.show_statusbar
            _results["checks"]["modifiers"] = [m.name for m in modeling_obj.modifiers]
            _stage = 2
            return 0.7

        if _stage == 2:
            _show_viewport_chrome()
            _results["checks"]["toolbar_flags"] = [
                (a.ui_type, sp.show_region_toolbar, [r.width for r in a.regions if r.type == "TOOLS"])
                for w in bpy.context.window_manager.windows for a in w.screen.areas if a.type == "VIEW_3D"
                for sp in a.spaces if sp.type == "VIEW_3D"
            ]
            _capture("phase11_desktop_rev2.png")
            desktop.cycle_right_dock("MODIFIER_STACK")
            _open_windows_menu()
            _stage = 3
            return 0.6

        if _stage == 3:
            _capture("phase11_modifier_stack_dock.png")
            _menu_overlay[0].hide()
            _menu_overlay = None
            hero = bpy.data.objects.get("pCylinder_HeroMech")
            gn = next(m for m in hero.modifiers if m.type == "NODES")
            res = modifier_stack.open_graph_for_modifier(gn.name, hero)
            _results["checks"]["gn_window"] = {k: v for k, v in res.items() if k != "hwnd"}
            _stage = 4
            return 1.2

        if _stage == 4:
            entry = hybrid_window._open.get("GEOMETRY_NODE_EDITOR")
            extra = []
            if entry is not None:
                for dock in entry["qt_docks"]:
                    dock._last_rect = None
                    dock._position(dock.content_region())
                    extra.append((getattr(dock._ctrl, "root", None), dock._last_rect, "group_inputs_panel"))
                _capture("phase11_geometry_node_window.png", window=entry["window"], extra=extra)
            _results["checks"]["editor_windows"] = [{k: v for k, v in w.items() if k != "hwnd"} for w in hybrid_window.list_editor_windows()]
            hybrid_window.close_editor_window("GEOMETRY_NODE_EDITOR")
            desktop.cycle_right_dock("CHANNEL_BOX")
            right_dock.tear_off_panel("MODIFIER_STACK", x=980, y=170, width=420, height=600)
            _stage = 5
            return 0.6

        if _stage == 5:
            _capture("phase11_modifier_stack_floating.png")
            right_dock.teardown_tear_off_windows()
            shots = _results["shots"]
            _results["ok"] = bool(
                len(shots) == 4
                and "main_menu" in shots.get("phase11_desktop_rev2.png", [])
                and "windows_menu" in shots.get("phase11_modifier_stack_dock.png", [])
                and "group_inputs_panel" in shots.get("phase11_geometry_node_window.png", [])
                and _results["checks"].get("statusbar_hidden")
            )
            for d in OUT_DIRS:
                (d / "phase11_gui_results.json").write_text(json.dumps(_results, indent=2, default=str), encoding="utf-8")
            print("PHASE11_GUI_RESULT:" + json.dumps(_results, default=str), flush=True)
            landfall_studio.unregister()
            bpy.ops.wm.quit_blender()
            return None
    except Exception as exc:
        import traceback

        _results["error"] = str(exc)
        _results["traceback"] = traceback.format_exc()
        print("PHASE11_GUI_RESULT:" + json.dumps(_results, default=str), flush=True)
        bpy.ops.wm.quit_blender()
        return None


if __name__ == "__main__":
    bpy.app.timers.register(_step, first_interval=0.45, persistent=True)
