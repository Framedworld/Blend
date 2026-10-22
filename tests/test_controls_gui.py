"""Behavior checks through Blender's GUI event queue and PySide6 widget events.

Run in a disposable factory scene with --enable-event-simulate. Never attaches
to, saves, or changes a user's working scene. This is not physical-device QA.
"""
import json
import sys
import traceback
from pathlib import Path

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "controls_gui_results.json"
results = {"passed": [], "failed": [], "observations": {},
           "input_method": "Blender event_simulate and PySide6 QtTest; isolated GUI process"}


def check(name, condition, detail=None):
    results["passed" if condition else "failed"].append(name if condition else {"test": name, "detail": detail})
    save()


def save():
    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


def context():
    w = bpy.context.window_manager.windows[0]
    a = next(a for a in w.screen.areas if a.type == "VIEW_3D")
    r = next(r for r in a.regions if r.type == "WINDOW")
    return {"window": w, "screen": w.screen, "area": a, "region": r}


def event(kind, value="PRESS", xy=None, **mods):
    ov = context()
    r = ov["region"]
    x, y = xy or (r.x + r.width // 2, r.y + r.height // 2)
    ov["window"].event_simulate(type=kind, value=value, x=int(x), y=int(y), **mods)


def key(kind, **mods):
    event(kind, **mods)
    event(kind, "RELEASE", **mods)


def point(obj):
    ov = context()
    r = ov["region"]
    p = location_3d_to_region_2d(r, ov["area"].spaces.active.region_3d, obj.matrix_world.translation)
    return (int(p.x + r.x), int(p.y + r.y))


def click(obj, **mods):
    xy = point(obj)
    event("MOUSEMOVE", "NOTHING", xy, **mods)
    event("LEFTMOUSE", "PRESS", xy, **mods)
    event("LEFTMOUSE", "RELEASE", xy, **mods)


def selected():
    return {o.name for o in bpy.context.selected_objects}


def drag(button, start, end, **mods):
    for flag, kind in (("shift", "LEFT_SHIFT"), ("ctrl", "LEFT_CTRL"), ("alt", "LEFT_ALT")):
        if mods.get(flag):
            event(kind, "PRESS", start, **mods)
    yield 0.1
    event("MOUSEMOVE", "NOTHING", start, **mods)
    yield 0.1
    event(button, "PRESS", start, **mods)
    yield 0.1
    for i in range(1, 6):
        xy = (start[0] + (end[0]-start[0])*i/5, start[1] + (end[1]-start[1])*i/5)
        event("MOUSEMOVE", "NOTHING", xy, **mods)
        yield 0.06
    event(button, "RELEASE", end, **mods)
    yield 0.2
    for flag, kind in (("shift", "LEFT_SHIFT"), ("ctrl", "LEFT_CTRL"), ("alt", "LEFT_ALT")):
        if mods.get(flag):
            event(kind, "RELEASE", end)
    yield 0.1


def run():
    bpy.context.preferences.view.show_splash = False
    bpy.ops.wm.read_homefile()
    import landfall_studio
    from landfall_studio import commands, continuity, ui
    from landfall_studio.ui import desktop, menus, outliner, right_dock, viewport_bar
    landfall_studio.register()
    ui.restore_workspace_desktop(restore_script_output=False)
    from PySide6 import QtCore, QtTest, QtWidgets
    import qtpy
    check("single PySide6 binding", qtpy.API_NAME == "PySide6", qtpy.API_NAME)
    with bpy.context.temp_override(**context()):
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()
        objects = []
        for name, location in (("PickA", (-3, 0, 0)), ("PickB", (3, 0, 0)), ("PickC", (0, 5, 0))):
            bpy.ops.mesh.primitive_cube_add(size=1.8, location=location)
            bpy.context.active_object.name = name
            objects.append(bpy.context.active_object)
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = None
    a, b, c = objects
    rv = context()["area"].spaces.active.region_3d
    rv.view_rotation = Euler((0.95, 0, 0.65)).to_quaternion()
    rv.view_location = Vector((0, 1, 0))
    rv.view_distance = 19
    yield 0.8
    # These are key events, not direct calls to select_tool().
    for k, expected, native in (("Q", "SELECT", "builtin.select_box"), ("W", "TRANSLATE", "builtin.move"),
                                ("E", "ROTATE", "builtin.rotate"), ("R", "RESIZE", "builtin.scale")):
        key(k)
        yield 0.2
        actual = context()["window"].workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname
        check(k + " selects real tool", commands.get_active_tool() == expected and actual == native,
              [commands.get_active_tool(), actual])
    key("Q")
    yield 0.2
    for name, obj, mods, expected in (
        ("click selects", a, {}, {"PickA"}), ("click replaces", b, {}, {"PickB"}),
        ("Shift adds", a, {"shift": True}, {"PickA", "PickB"}),
        ("Shift toggles off", a, {"shift": True}, {"PickB"}),
        ("Ctrl removes", b, {"ctrl": True}, set()),
        ("Ctrl Shift adds", b, {"ctrl": True, "shift": True}, {"PickB"}),
        ("Ctrl Shift preserves selected", b, {"ctrl": True, "shift": True}, {"PickB"}),
    ):
        click(obj, **mods)
        yield 0.25
        check(name, selected() == expected, sorted(selected()))
    key("ESC")  # dismiss any native selection popup exposed by a failed check
    yield 0.1
    # Marquee gestures must select rather than transform when away from a gizmo.
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    def bounds(obj):
        ov = context()
        rr = ov["region"]
        pts = [location_3d_to_region_2d(rr, rv, obj.matrix_world @ Vector(p)) for p in obj.bound_box]
        return ((rr.x+min(p.x for p in pts)-8, rr.y+min(p.y for p in pts)-8),
                (rr.x+max(p.x for p in pts)+8, rr.y+max(p.y for p in pts)+8))
    box_start, box_end = bounds(b)
    for tool in ("Q", "W", "E", "R"):
        with bpy.context.temp_override(**context()):
            bpy.ops.object.select_all(action="DESELECT")
        key(tool)
        yield 0.2
        before = tuple(b.location)
        yield from drag("LEFTMOUSE", box_start, box_end)
        check(tool + " marquee selects without moving", selected() == {"PickB"} and tuple(b.location) == before, sorted(selected()))
    key("Q")
    yield 0.2
    for name, mods, expected in (("Shift marquee preserves selected", {"shift": True}, {"PickB"}),
                                  ("Ctrl Shift marquee adds", {"ctrl": True, "shift": True}, {"PickB"}),
                                  ("Ctrl marquee removes", {"ctrl": True}, set())):
        yield from drag("LEFTMOUSE", box_start, box_end, **mods)
        from landfall_studio.viewport.interaction import _last_marquee
        check(name, selected() == expected, {"selected": sorted(selected()), "marquee": dict(_last_marquee)})
    if "--selection-only" in sys.argv:
        results["ok"] = not results["failed"]
        save()
        landfall_studio.unregister()
        bpy.ops.wm.quit_blender()
        return
    # Pick a single target for transforms and component controls.
    with bpy.context.temp_override(**context()):
        bpy.ops.object.select_all(action="DESELECT")
        a.select_set(True)
        bpy.context.view_layer.objects.active = a
    # A front-facing, isolated manipulator gives a reproducible native handle
    # hit. Marquee bindings must never intercept a genuine gizmo drag.
    rv.view_rotation = (1, 0, 0, 0)
    rv.view_location = a.location.copy()
    rv.view_distance = 10
    key("W")
    yield 0.4
    center = point(a)
    before = a.location.copy()
    yield from drag("LEFTMOUSE", (center[0]+60, center[1]), (center[0]+110, center[1]))
    check("LMB Move gizmo changes X", a.location.x > before.x and abs(a.location.y-before.y) < .001,
          [tuple(before), tuple(a.location)])
    rv.view_location = a.location.copy()
    key("R")
    yield 0.3
    center = point(a)
    before = a.scale.copy()
    yield from drag("LEFTMOUSE", (center[0]+60, center[1]), (center[0]+105, center[1]))
    check("LMB Scale gizmo changes X", a.scale.x != before.x, [tuple(before), tuple(a.scale)])
    rv.view_rotation = Euler((0.95, 0, 0.65)).to_quaternion()
    rv.view_distance = 19
    yield 0.2
    for tool, attr in (("W", "location"), ("E", "rotation_euler"), ("R", "scale")):
        key(tool)
        yield 0.2
        before = tuple(getattr(a, attr))
        r = context()["region"]
        start = (r.x + int(r.width * .7), r.y + int(r.height * .4))
        yield from drag("MIDDLEMOUSE", start, (start[0]+60, start[1]))
        check(tool + " drag changes transform", before != tuple(getattr(a, attr)), [before, tuple(getattr(a, attr))])
    key("F9")
    yield 0.3
    check("F9 vertex mode", bpy.context.mode == "EDIT_MESH" and tuple(bpy.context.tool_settings.mesh_select_mode) == (True, False, False))
    key("F10")
    yield 0.2
    check("F10 edge mode", tuple(bpy.context.tool_settings.mesh_select_mode) == (False, True, False))
    key("F11")
    yield 0.2
    check("F11 face mode", tuple(bpy.context.tool_settings.mesh_select_mode) == (False, False, True))
    key("F8")
    yield 0.2
    check("F8 object mode", bpy.context.mode == "OBJECT", bpy.context.mode)
    # Navigation must have a real effect and the documented direction.
    r = context()["region"]
    start = (r.x + int(r.width*.65), r.y + int(r.height*.45))
    before = rv.view_distance
    yield from drag("RIGHTMOUSE", start, (start[0]+90, start[1]), alt=True)
    check("Alt RMB right dollies in", rv.view_distance < before, [before, rv.view_distance])
    before = rv.view_distance
    event("WHEELUPMOUSE", xy=start)
    yield 0.2
    check("wheel up dollies in", rv.view_distance < before, [before, rv.view_distance])
    before = tuple(rv.view_location)
    yield from drag("MIDDLEMOUSE", start, (start[0]+70, start[1]+25), alt=True)
    check("Alt MMB tracks", tuple(rv.view_location) != before)
    before = tuple(rv.view_rotation)
    yield from drag("LEFTMOUSE", start, (start[0]+70, start[1]+25), alt=True)
    check("Alt LMB tumbles", tuple(rv.view_rotation) != before)
    # RMB menu is a real PySide6 surface; click its vertex action.
    from landfall_studio.viewport import marking_menus as mm
    xy = point(a)
    event("RIGHTMOUSE", "PRESS", xy)
    yield 0.25
    event("RIGHTMOUSE", "RELEASE", xy)
    yield 0.2
    overlay = mm._studio_mm.get("qt_overlay")
    check("RMB opens PySide6 radial menu", overlay is not None and overlay.root.isVisible())
    if overlay:
        overlay.root.grab().save(str(ROOT / "output" / "controls_radial_qt.png"))
        QtTest.QTest.mouseClick(overlay.buttons[("radial", 0)], QtCore.Qt.LeftButton)
        yield 0.2
        check("Qt radial vertex action works", bpy.context.mode == "EDIT_MESH" and tuple(bpy.context.tool_settings.mesh_select_mode) == (True, False, False))
    key("F8")
    yield 0.2
    # Actual Qt mouse delivery to every viewport button, with backend readback.
    bar = viewport_bar.get_bars()[0]
    results["observations"]["viewport_menubar"] = {
        "size": [bar.menubar.width(), bar.menubar.height()],
        "actions": [[a.text(), bar.menubar.actionGeometry(a).width()] for a in bar.menubar.actions()]}
    bar.root.grab().save(str(ROOT / "output" / "controls_viewport_bar.png"))
    for mode in ("4", "5", "6", "7"):
        QtTest.QTest.mouseClick(bar.buttons[mode], QtCore.Qt.LeftButton)
        yield 0.3
        st = continuity.get_viewport_shading_state()
        check("Qt shading " + mode, st["maya_mode"] == mode, st)
    for button, field in (("WIRE_ON_SHADED", "wire_on_shaded"), ("XRAY", "xray"),
                           ("SSAO", "eevee_ssao"), ("SHADOWS", "eevee_shadows")):
        for _ in range(2):
            before = continuity.get_viewport_shading_state()[field]
            QtTest.QTest.mouseClick(bar.buttons[button], QtCore.Qt.LeftButton)
            yield 0.2
            check("Qt " + button + " toggles " + str(not before), continuity.get_viewport_shading_state()[field] != before)
    eevee = bpy.context.scene.eevee
    continuity.toggle_viewport_20_feature("SSAO", enable=True)
    check("AO reaches EEVEE 5.2 settings", eevee.use_fast_gi and eevee.use_raytracing and eevee.fast_gi_method == "AMBIENT_OCCLUSION_ONLY")
    for mode in ("CHANNEL_BOX", "ATTRIBUTE_EDITOR", "MODELING_TOOLKIT", "TOOL_SETTINGS", "MODIFIER_STACK", "HYPERSHADE", "SHAPE_EDITOR", "MAYA_INTERCHANGE"):
        res = desktop.cycle_right_dock(mode)
        yield 0.25
        check("panel opens " + mode, res.get("ok", False), res)
    desktop.cycle_right_dock("CHANNEL_BOX")
    # Click a Qt rail control, then type W into a text field: editing must win.
    rail = outliner.get_left_outliner_dock().ensure_outliner_widget()
    QtTest.QTest.mouseClick(rail.tool_btns["ROTATE"], QtCore.Qt.LeftButton)
    yield 0.2
    check("Qt tool rail activates Rotate", commands.get_active_tool() == "ROTATE")
    QtTest.QTest.mouseClick(rail.tool_btns["LASSO"], QtCore.Qt.LeftButton)
    yield 0.2
    check("Qt Lasso selects real lasso tool", context()["window"].workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname == "builtin.select_lasso")
    QtTest.QTest.mouseClick(rail.tool_btns["ROTATE"], QtCore.Qt.LeftButton)
    edit = QtWidgets.QLineEdit()
    edit.show()
    edit.setFocus()
    QtTest.QTest.keyClick(edit, QtCore.Qt.Key_W)
    check("text W stays text", edit.text() == "w" and commands.get_active_tool() == "ROTATE", edit.text())
    edit.close()
    # Menus and panels all use the same QApplication and Qt binding.
    check("viewport menus are connected", all(a.receivers(QtCore.SIGNAL("triggered(bool)")) > 0 for a in bar.actions.values()))
    results["observations"]["viewport_actions"] = sorted(bar.actions)
    results["observations"]["qt_version"] = QtCore.qVersion()
    from landfall_studio.ui import shelf, time_slider, channel_box_ext
    res = shelf.execute_shelf_item("isolate")
    check("Isolate shelf changes local view", res["ok"] and context()["area"].spaces.active.local_view is not None, res)
    shelf.execute_shelf_item("isolate")
    slider = time_slider.get_bottom_time_slider_dock()._ctrl
    frame_before = bpy.context.scene.frame_current
    QtTest.QTest.mouseClick(slider.scrub_bar, QtCore.Qt.LeftButton, pos=QtCore.QPoint(slider.scrub_bar.width()//2, 10))
    check("Qt time scrub changes frame", bpy.context.scene.frame_current != frame_before)
    slider.txt_command.setText("21 * 2")
    QtTest.QTest.mouseClick(slider.btn_cmd_lang, QtCore.Qt.LeftButton)
    check("Python button executes command", desktop.get_command_feedback()["result"] == "42", desktop.get_command_feedback())
    start_before = bpy.context.scene.frame_start
    pos = QtCore.QPoint(10, slider.range_bar.height()//2)
    QtTest.QTest.mousePress(slider.range_bar, QtCore.Qt.LeftButton, pos=pos)
    from PySide6 import QtGui
    move = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(55, pos.y()),
                            QtCore.QPointF(slider.range_bar.mapToGlobal(QtCore.QPoint(55, pos.y()))),
                            QtCore.Qt.NoButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    QtWidgets.QApplication.sendEvent(slider.range_bar, move)
    QtTest.QTest.mouseRelease(slider.range_bar, QtCore.Qt.LeftButton, pos=QtCore.QPoint(55, pos.y()))
    check("Qt range handle changes playback start", bpy.context.scene.frame_start > start_before)
    # Display only real authored layers and exercise both mini-layer controls.
    layer = channel_box_ext.create_display_layer(name="AuditLayer", assign_selected=True)
    rail._refresh_display_layers_mini()
    eye = rail.root.findChild(QtWidgets.QToolButton, "mini_visibility_AuditLayer")
    check("authored mini-layer has visibility control", eye is not None, layer)
    if eye:
        QtTest.QTest.mouseClick(eye, QtCore.Qt.LeftButton)
        check("mini-layer visibility affects object", a.hide_get())
        eye = rail.root.findChild(QtWidgets.QToolButton, "mini_visibility_AuditLayer")
        QtTest.QTest.mouseClick(eye, QtCore.Qt.LeftButton)
    # Restore selection for the modeling caddy fixture.
    channel_box_ext.set_display_layer_state("AuditLayer", visible=True)
    # Editable caddy must change geometry, then cancel back to the original.
    from landfall_studio.modeling import caddy
    with bpy.context.temp_override(**context()):
        bpy.ops.object.select_all(action="DESELECT")
        a.select_set(True)
        bpy.context.view_layer.objects.active = a
        original = [tuple(v.co) for v in a.data.vertices]
        opened = caddy.invoke_modeling_caddy("BEVEL", a)
    for _ in range(20):
        bars = viewport_bar.get_bars()
        bar = next((b for b in bars if b.area == context()["area"]), bar)
        if bar.caddy is not None:
            break
        yield 0.25
    check("real Qt caddy opens", bar.caddy is not None,
          {"invoke": opened, "state": caddy.get_active_caddy_state(), "bars": len(viewport_bar.get_bars())})
    if bar.caddy:
        bar.caddy.root.grab().save(str(ROOT / "output" / "controls_caddy_qt.png"))
        old_count = len(a.data.vertices)
        bar.caddy.fields["segments"].setValue(4)
        yield 0.2
        check("caddy field changes mesh", len(a.data.vertices) != old_count)
        QtTest.QTest.mouseClick(bar.caddy.cancel_button, QtCore.Qt.LeftButton)
        yield 0.3
        check("caddy cancel restores mesh", [tuple(v.co) for v in a.data.vertices] == original)
    key("S")
    yield 0.3
    keyed = bpy.data.objects.get("PickA")
    check("S sets transform keys", bool(keyed.animation_data and keyed.animation_data.action))
    key("Z")
    yield 0.3
    keyed = bpy.data.objects.get("PickA")
    check("Z undoes Set Key", not (keyed.animation_data and keyed.animation_data.action))
    key("Z", shift=True)
    yield 0.3
    keyed = bpy.data.objects.get("PickA")
    check("Shift Z redoes Set Key", bool(keyed.animation_data and keyed.animation_data.action))
    results["ok"] = not results["failed"]
    save()
    landfall_studio.unregister()
    bpy.ops.wm.quit_blender()


steps = run()


def tick():
    try:
        return next(steps)
    except StopIteration:
        return None
    except Exception:
        results["failed"].append({"exception": traceback.format_exc()})
        results["ok"] = False
        save()
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=0.5, persistent=True)
