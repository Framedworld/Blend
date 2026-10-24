"""Maya-style menu definitions shared by the Main Menu Bar and panel menu bars (`landfall_studio.ui.menus`).

Entries are plain data so they can be validated headless:
- `O(label, "module.op", invoke=False, **props)`: run a Blender operator in a 3D View context.
- `F(label, callable)`: run a Python callable.
- `S(label, [entries])`: submenu.  `SEP`: separator.  `H(text)`: section header.
`hint` (shown right-aligned, like a shortcut) carries the hotkey or the Blender editor name.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

SEP = ("SEP",)


def O(label: str, op: str, invoke: bool = False, hint: str = "", **props: Any) -> Tuple:
    return ("OP", label, op, invoke, props, hint)


def F(label: str, fn: Callable[[], Any], hint: str = "") -> Tuple:
    return ("FN", label, fn, hint)


def S(label: str, entries: List[Tuple]) -> Tuple:
    return ("SUB", label, entries)


def H(text: str) -> Tuple:
    return ("HEAD", text)


# --------------------------------------------------------------------------------------
# Execution helpers
# --------------------------------------------------------------------------------------
def view3d_override() -> Dict[str, Any]:
    import bpy
    import blendertk as btk

    win = btk.main_window() or bpy.context.window_manager.windows[0]
    ov: Dict[str, Any] = {"window": win, "screen": win.screen}
    area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
    if area is not None:
        ov["area"] = area
        ov["region"] = next((r for r in area.regions if r.type == "WINDOW"), None)
    return ov


# Interactive commands that open their own file-browser window; everything else
# invoked from a menu draws or works inside the viewport.
_SEPARATE_WINDOW_OPS = ("import", "export", "_open", "open_mainfile", "save_as", "find_missing",
                        "userpref", "recover_auto_save", "render.render", "import_maya_ascii", "export_maya_ascii")


def _bring_cursor_to_viewport(override: Dict[str, Any], op_path: str) -> bool:
    """Start in-window popups and modal tools in the viewport, not under the menu.

    Blender opens popups and starts modal tools at the mouse position. After a
    click in Studio's Qt menu bar that position lies under the Qt panels, which
    always draw above Blender's own UI, hiding the popup.
    """
    if any(token in op_path for token in _SEPARATE_WINDOW_OPS):
        return False
    window, region = override.get("window"), override.get("region")
    if window is None or region is None:
        return False
    try:
        window.cursor_warp(int(region.x + region.width / 2), int(region.y + region.height / 2))
        return True
    except Exception:
        return False


def run_op(op_path: str, invoke: bool = False, **props: Any) -> Any:
    """Run `module.op` with a main-window 3D View override; reports failures to the command line."""
    import bpy

    mod_name, _, op_name = op_path.partition(".")
    try:
        fn = getattr(getattr(bpy.ops, mod_name), op_name)
        args = ("INVOKE_DEFAULT" if invoke else "EXEC_DEFAULT",)
        # This operator is also invoked from native keys. Python/Qt callers
        # explicitly enable its native Undo entry, just as those keys do.
        if op_path in ('landfall_studio.duplicate_objects','landfall_studio.repeat_last_command'):args += (True,)
        if op_path in ('wm.read_homefile','wm.open_mainfile','wm.revert_mainfile','landfall.project_open'):
            res = fn(*args, **props)
        else:
            override = view3d_override()
            if invoke and not bpy.app.background:
                _bring_cursor_to_viewport(override, op_path)
            with bpy.context.temp_override(**override):
                res = fn(*args, **props)
        _feedback(op_path, "Cancelled" if "CANCELLED" in res else "Ready" if "RUNNING_MODAL" in res else "Done", "INFO")
        return res
    except Exception as exc:
        _feedback(op_path, f"Error: {exc}", "ERROR")
        return None


def _feedback(cmd: str, result: str, level: str) -> None:
    try:
        from . import desktop

        desktop.set_command_feedback(cmd, result, level=level)
    except Exception:
        pass


def op_exists(op_path: str) -> bool:
    import bpy

    mod_name, _, op_name = op_path.partition(".")
    try:
        getattr(getattr(bpy.ops, mod_name), op_name).get_rna_type()
        return True
    except Exception:
        return False


def iter_ops(entries: List[Tuple]):
    for e in entries:
        if e[0] == "OP":
            yield e[2]
        elif e[0] == "SUB":
            yield from iter_ops(e[2])


def build_qmenu(menu, entries: List[Tuple]) -> None:
    """Populate a `QMenu` from entry data."""
    operators = []
    menu.setToolTipsVisible(True)
    for e in entries:
        kind = e[0]
        if kind == "SEP":
            menu.addSeparator()
        elif kind == "HEAD":
            menu.addSection(e[1])
        elif kind == "SUB":
            sub = menu.addMenu(e[1])
            build_qmenu(sub, e[2])
        elif kind == "OP":
            _, label, op, invoke, props, hint = e
            act = menu.addAction(f"{label}\t{hint}" if hint else label)
            act.setData({'operator':op,'properties':props})
            operators.append((act,op))
            act.triggered.connect(lambda _=False, o=op, i=invoke, p=props: run_op(o, invoke=i, **p))
        elif kind == "FN":
            _, label, fn, hint = e
            act = menu.addAction(f"{label}\t{hint}" if hint else label)
            act.triggered.connect(lambda _=False, f=fn, l=label: _safe_call(f, l))
    def availability():
        import bpy
        for action, path in operators:
            available = False
            reason = ''
            try:
                module, name = path.split('.',1)
                operator = getattr(getattr(bpy.ops,module),name)
                operator.get_rna_type()
                with bpy.context.temp_override(**view3d_override()):available = operator.poll()
                if not available:
                    reason = ('Switch to mesh component mode and select the components to edit.' if module in ('mesh','uv') else
                              'Select compatible objects in the viewport, then try this command.')
            except Exception:
                reason = 'This command is unavailable in this Blender installation.'
            action.setEnabled(available)
            action.setToolTip(reason)
            action.setStatusTip(reason)
    if operators:menu.aboutToShow.connect(availability)


def _safe_call(fn: Callable[[], Any], label: str) -> Any:
    try:
        res = fn()
        failed = isinstance(res,dict) and not res.get('ok',True)
        cancelled = isinstance(res,set) and 'CANCELLED' in res
        nested=res.get('result',{}) if isinstance(res,dict) else {}
        nested=nested if isinstance(nested,dict) else {}
        message = (res.get('error') or res.get('reason') or nested.get('error') or nested.get('reason') or res.get('status') or ('Done' if not failed else str(res))) if isinstance(res,dict) else ('Cancelled' if cancelled else 'Done')
        _feedback(label, str(message), 'ERROR' if failed else 'INFO')
        return res
    except Exception as exc:
        _feedback(label, f"Error: {exc}", "ERROR")
        return {'ok':False,'error':str(exc)}


# --------------------------------------------------------------------------------------
# Callables (lazy imports keep this module importable without Qt)
# --------------------------------------------------------------------------------------
def _editor(key: str) -> Callable[[], Any]:
    def _open():
        from . import hybrid_window

        return hybrid_window.open_editor_window(key)

    return _open


def _dock(mode: str) -> Callable[[], Any]:
    def _show():
        from . import desktop

        return desktop.cycle_right_dock(mode)

    return _show


def _tear_off(mode: str) -> Callable[[], Any]:
    def _show():
        from . import right_dock

        return right_dock.tear_off_panel(mode)

    return _show


def _prim(kind: str) -> Callable[[], Any]:
    def _make():
        from . import channel_box_ext

        return channel_box_ext.create_maya_primitive(kind)

    return _make


def _shelf(item: str) -> Callable[[], Any]:
    def _run():
        from . import shelf

        return shelf.execute_shelf_item(item)

    return _run


def _shading(mode: str) -> Callable[[], Any]:
    def _run():
        from .. import continuity

        return continuity.set_maya_viewport_shading(mode)

    return _run


def _toggle_outliner():
    from . import desktop

    return desktop.toggle_left_outliner_dock()


def _toggle_hud():
    from ..viewport import hud

    return hud.set_hud_enabled(not hud.get_hud_state().get("enabled", True))


def _caddy(tool: str) -> Callable[[], Any]:
    def _run():
        from .. import modeling

        if tool == "EXTRUDE":
            from ..modeling import caddy
            return caddy.begin_maya_extrude()
        return modeling.invoke_modeling_caddy(tool)

    return _run


def _skin(fn_name: str) -> Callable[[], Any]:
    def _run():
        from .. import character

        return getattr(character, fn_name)(_active_name())

    return _run


def _active_name() -> Optional[str]:
    import bpy

    obj = bpy.context.view_layer.objects.active
    return obj.name if obj is not None else None


def _set_menu_set(name: str) -> Callable[[], Any]:
    def _run():
        from . import main_menu

        return main_menu.set_menu_set(name)

    return _run


# --------------------------------------------------------------------------------------
# Common menus (left side, same in every menu set)
# --------------------------------------------------------------------------------------
FILE_MENU = [
    O("New Scene", "wm.read_homefile", invoke=True, hint="Ctrl+N"),
    O("Open Scene…", "landfall.project_open", invoke=True, hint="Ctrl+O"),
    O("Save Scene", "wm.save_mainfile", invoke=True, hint="Ctrl+S"),
    O("Save Scene As…", "landfall.project_save_as", invoke=True, hint="Ctrl+Shift+S"),
    O("Make External Paths Relative", "landfall.paths_relative"),
    O("Find Missing Files…", "file.find_missing_files", invoke=True),
    S("Recover", [
        O("Last Session", "wm.recover_last_session", invoke=True),
        O("Auto Save…", "wm.recover_auto_save", invoke=True),
    ]),
    SEP,
    H("Maya Interchange"),
    F("Import Maya Scene (.ma / .mb)…", _shelf("import_maya")),
    F("Save As Maya Scene (.ma / .mb)…", _shelf("save_maya")),
    F("Reference Editor", _dock("MAYA_INTERCHANGE")),
    SEP,
    S("Import", [
        O("Maya ASCII (.ma, native)…", "landfall_studio.import_maya_ascii", invoke=True),
        O("FBX (.fbx)…", "import_scene.fbx", invoke=True),
        O("Wavefront (.obj)…", "wm.obj_import", invoke=True),
        O("USD (.usd*)…", "wm.usd_import", invoke=True),
        O("Alembic (.abc)…", "wm.alembic_import", invoke=True),
        O("glTF 2.0 (.glb / .gltf)…", "import_scene.gltf", invoke=True),
    ]),
    S("Export", [
        O("Maya ASCII (.ma, native)…", "landfall_studio.export_maya_ascii", invoke=True),
        O("FBX (.fbx)…", "export_scene.fbx", invoke=True),
        O("Wavefront (.obj)…", "wm.obj_export", invoke=True),
        O("USD (.usd*)…", "wm.usd_export", invoke=True),
        O("Alembic (.abc)…", "wm.alembic_export", invoke=True),
        O("glTF 2.0 (.glb / .gltf)…", "export_scene.gltf", invoke=True),
    ]),
    SEP,
    O("Preferences…", "screen.userpref_show", invoke=True),
    O("Quit", "wm.quit_blender", invoke=True, hint="Ctrl+Q"),
]

EDIT_MENU = [
    O("Undo", "ed.undo", hint="Ctrl+Z"),
    O("Redo", "ed.redo", hint="Ctrl+Shift+Z"),
    O("Repeat Last", "landfall_studio.repeat_last_command", hint="G"),
    O("Undo History…", "ed.undo_history", invoke=True),
    SEP,
    O("Duplicate", "landfall_studio.duplicate_objects", hint="Ctrl+D", linked=False),
    O("Duplicate Instance", "landfall_studio.duplicate_objects", linked=True),
    O("Delete", "landfall_studio.smart_delete", hint="Del"),
    SEP,
    O("Group", "landfall_studio.group_objects", hint="Ctrl+G"),
    O("Ungroup", "landfall_studio.ungroup_objects", hint="Ctrl+Shift+G"),
    SEP,
    H("Delete by Type"),
    O("History", "landfall_studio.delete_history", hint="Alt+Shift+D"),
    O("Non-Deformer History", "landfall_studio.delete_non_deformer_history"),
    SEP,
    O("Select All", "landfall_studio.select_all_toggle", action="SELECT", hint="Ctrl+Shift+A"),
]

CREATE_MENU = [
    S("Polygon Primitives", [F("Cube", _prim("CUBE")), F("Sphere", _prim("SPHERE")), F("Cylinder", _prim("CYLINDER")), F("Plane", _prim("PLANE"))]),
    S("Lights", [
        O("Point Light", "object.light_add", type="POINT"),
        O("Spot Light", "object.light_add", type="SPOT"),
        O("Area Light", "object.light_add", type="AREA"),
        O("Directional (Sun) Light", "object.light_add", type="SUN"),
    ]),
    O("Camera", "object.camera_add"),
    O("Locator", "object.empty_add", type="PLAIN_AXES"),
    S("Curve Tools", [O("Bezier Curve", "curve.primitive_bezier_curve_add"), O("Circle", "curve.primitive_bezier_circle_add")]),
    O("Text", "object.text_add"),
    SEP,
    O("Grease Pencil", "landfall_studio.native_bridge", target="GREASE_PENCIL"),
]

SELECT_MENU = [
    O("All", "landfall_studio.select_all_toggle", action="SELECT", hint="Ctrl+Shift+A"),
    O("Deselect All", "landfall_studio.select_all_toggle", action="DESELECT"),
    O("Invert", "landfall_studio.select_all_toggle", action="INVERT"),
    SEP,
    O("Grow", "landfall_studio.convert_selection", target="GROW", hint=">"),
    O("Shrink", "landfall_studio.convert_selection", target="SHRINK", hint="<"),
    O("Select Edge Loop", "landfall_studio.convert_selection", target="EDGE_LOOP"),
    O("Select Edge Ring", "landfall_studio.convert_selection", target="EDGE_RING"),
    O("Select Border Edges", "landfall_studio.convert_selection", target="BOUNDARY"),
    SEP,
    H("Convert Selection"),
    O("To Vertices", "landfall_studio.convert_selection", target="VERT", hint="Ctrl+F9"),
    O("To Edges", "landfall_studio.convert_selection", target="EDGE", hint="Ctrl+F10"),
    O("To Faces", "landfall_studio.convert_selection", target="FACE", hint="Ctrl+F11"),
]

MODIFY_MENU = [
    O("Center Pivot", "landfall_studio.center_pivot_guarded"),
    O("Freeze Transformations", "landfall_studio.freeze_transformations_guarded"),
    S("Reset Transformations", [O("Translate", "object.location_clear"), O("Rotate", "object.rotation_clear"), O("Scale", "object.scale_clear")]),
    SEP,
    O("Make Live", "landfall_studio.make_live", toggle=True),
    O("Snap Pivot to Grid", "landfall_studio.pivot_edit_modal", snap_mode="GRID"),
    SEP,
    O("Parent", "object.parent_set", invoke=True, hint="P"),
    O("Unparent", "object.parent_clear", type="CLEAR_KEEP_TRANSFORM", hint="Shift+P"),
]

DISPLAY_MENU = [
    H("Shading"),
    F("Wireframe", _shading("4"), "4"),
    F("Smooth Shaded", _shading("5"), "5"),
    F("Shaded & Textured", _shading("6"), "6"),
    F("Use All Lights", _shading("7"), "7"),
    F("Wireframe on Shaded", _shading("WIRE_ON_SHADED")),
    F("X-Ray", _shading("XRAY"), "Alt+Z"),
    SEP,
    O("Isolate Selected", "view3d.localview", invoke=True, hint="/"),
    O("Hide Selection", "object.hide_view_set", hint="H"),
    O("Show All", "object.hide_view_clear", hint="Alt+H"),
    SEP,
    F("Heads Up Display", _toggle_hud),
]

WINDOWS_MENU = [
    H("General Editors"),
    F("Component Editor", _editor("COMPONENT_EDITOR"), "Spreadsheet"),
    F("Content Browser", _editor("CONTENT_BROWSER"), "Asset Browser"),
    F("Script Editor", _editor("SCRIPT_EDITOR"), "Text + Info"),
    F("Outliner", _toggle_outliner, "Qt"),
    H("Modeling Editors"),
    F("Modifier Stack", _dock("MODIFIER_STACK"), "Qt · dock"),
    F("Modifier Stack (Floating)", _tear_off("MODIFIER_STACK"), "Qt · window"),
    F("Geometry Node Editor", _editor("GEOMETRY_NODE_EDITOR"), "Geometry Nodes"),
    F("UV Editor", _editor("UV_EDITOR"), "UV / Image"),
    F("Modeling Toolkit", _dock("MODELING_TOOLKIT"), "Qt"),
    H("Rendering Editors"),
    F("Hypershade", _dock("HYPERSHADE"), "Qt browser"),
    F("Hypershade Work Area", _editor("HYPERSHADE_GRAPH"), "Shader Editor"),
    F("Render Settings", _editor("RENDER_SETTINGS"), "Properties › Render"),
    F("Compositor", _editor("COMPOSITOR"), "Compositor"),
    F("Render View", _editor("RENDER_VIEW"), "Image › Render"),
    H("Animation Editors"),
    F("Graph Editor", _editor("GRAPH_EDITOR"), "Graph Editor"),
    F("Dope Sheet", _editor("DOPE_SHEET"), "Dope Sheet"),
    F("Time Editor", _editor("TIME_EDITOR"), "NLA"),
    F("Driver Editor", _editor("DRIVER_EDITOR"), "Drivers"),
    F("Shape Editor", _dock("SHAPE_EDITOR"), "Qt"),
    H("Panels"),
    F("Channel Box / Layer Editor", _dock("CHANNEL_BOX"), "Ctrl+A"),
    F("Attribute Editor", _dock("ATTRIBUTE_EDITOR"), "Ctrl+A"),
    F("Tool Settings", _dock("TOOL_SETTINGS")),
    H("Blender Only"),
    O("Grease Pencil", "landfall_studio.native_bridge", target="GREASE_PENCIL", hint="Draw mode"),
    F("Video Sequencer", _editor("VIDEO_SEQUENCER"), "Sequencer"),
    F("Motion Tracking", _editor("MOTION_TRACKING"), "Movie Clip"),
]

def _studio_controls():
    from PySide6 import QtCore,QtWidgets
    from . import desktop
    box=QtWidgets.QMessageBox()
    box.setWindowTitle('Landfall Studio controls')
    box.setTextFormat(QtCore.Qt.RichText)
    box.setText('<b>Modeling</b><br>Q Select · W Move · E Rotate · R Scale<br>'
        'Click replaces selection; Shift toggles; Ctrl removes.<br>'
        'Alt+left drag orbits · Alt+middle drag pans · Alt+right drag zooms.<br>'
        'F frames selection · A frames all · 1/2/3 smooth preview · 4/5/6/7 shading.<br>'
        'F8 object/components · F9 vertices · F10 edges · F11 faces · F12 UV.<br>'
        'Ctrl+D duplicates in place · W moves the selected copy. Edit → Duplicate Instance shares mesh data.<br>'
        'G repeats · Y recalls the last tool · S sets keys · Z / Shift+Z undo/redo.<br><br>'
        '<b>Sculpt Studio</b><br>Q Draw · W Move · E Scale · R Rotate<br>'
        'B then two letters chooses a brush · S Draw Size · U Z Intensity · O Focal Shift.<br>'
        'Space quick controls · Tab canvas focus.<br>'
        'Shift smooths · Ctrl masks · Ctrl+Shift controls visibility.<br>'
        'Drag a tray button, title or empty space vertically to scroll.<br><br>'
        '<b>Panels and files</b><br>Plain wheel scrolls; Ctrl+wheel adjusts a value.<br>'
        'Enter commits numbers. Use the header to move a floating editor and its corner to resize.<br>'
        'Ctrl+S saves · Ctrl+Shift+S Save As · Ctrl+O opens · Ctrl+N creates a scene.<br>'
        'Use GoZ Return to resume modeling. Disabled commands explain their required context.')
    box.setStandardButtons(QtWidgets.QMessageBox.Close)
    desktop._parent_floating_to_blender(box)
    box.exec()
    return {'ok':True}


HELP_MENU = [
    F('Studio Controls…',_studio_controls),
    O("Report a Problem…", "landfall_studio.report_problem"),
    O("Landfall Studio Diagnostics", "landfall_studio.diagnostics_report"),
    O("Blender Manual", "wm.url_open", url="https://docs.blender.org/manual/en/latest/"),
]

COMMON_MENUS: List[Tuple[str, List[Tuple]]] = [
    ("File", FILE_MENU),
    ("Edit", EDIT_MENU),
    ("Create", CREATE_MENU),
    ("Select", SELECT_MENU),
    ("Modify", MODIFY_MENU),
    ("Display", DISPLAY_MENU),
    ("Windows", WINDOWS_MENU),
]

# --------------------------------------------------------------------------------------
# Menu-set menus (right side; switch with the Status Line menu set selector)
# --------------------------------------------------------------------------------------
_DEFORM = [
    O("Lattice", "object.add", type="LATTICE"),
    F("Shrinkwrap", lambda: _add_mod("SHRINKWRAP")),
    F("Smooth (Corrective)", lambda: _add_mod("CORRECTIVE_SMOOTH")),
    F("Simple Deform (Bend / Twist)", lambda: _add_mod("SIMPLE_DEFORM")),
    F("Wave", lambda: _add_mod("WAVE")),
]


def _add_mod(mod_type: str):
    from . import modifier_stack

    return modifier_stack.add_modifier(mod_type)


def _boolean(operation: str):
    import bpy
    from . import modifier_stack
    obj = bpy.context.view_layer.objects.active
    operands = [o for o in bpy.context.selected_objects if o != obj and o.type == "MESH"]
    if obj is None or obj.type != "MESH" or not operands:
        return {"ok": False, "error": "Select two meshes; the active mesh receives the Boolean."}
    result = modifier_stack.add_modifier("BOOLEAN", obj)
    if result["ok"]:
        mod = obj.modifiers[result["modifier"]]
        mod.operation = operation
        mod.object = operands[0]
    return result


def _assign_new_material():
    import bpy
    objects = [o for o in bpy.context.selected_objects if hasattr(o.data, "materials")]
    if not objects:
        return {"ok": False, "error": "Select an object that supports materials."}
    mat = bpy.data.materials.new("StandardSurface")
    mat.use_nodes = True
    for obj in objects:
        if obj.data.materials:
            obj.data.materials[obj.active_material_index] = mat
        else:
            obj.data.materials.append(mat)
    return {"ok": True, "material": mat.name, "objects": [o.name for o in objects]}


def _constraint(kind: str):
    import bpy
    owner = bpy.context.view_layer.objects.active
    drivers = [o for o in bpy.context.selected_objects if o != owner]
    if owner is None or not drivers:
        return {"ok": False, "error": "Select the driver, then the object to constrain."}
    con = owner.constraints.new(kind)
    con.target = drivers[0]
    if kind == "CHILD_OF":
        con.inverse_matrix = drivers[0].matrix_world.inverted_safe()
    elif kind == "DAMPED_TRACK":
        con.track_axis = "TRACK_X"
    return {"ok": True, "constraint": con.name, "target": con.target.name}


MENU_SETS: Dict[str, List[Tuple[str, List[Tuple]]]] = {
    "Modeling": [
        ("Mesh", [
            O("Combine", "object.join", hint="Ctrl+J"),
            O("Separate", "mesh.separate", type="LOOSE"),
            O("Extract", "mesh.separate", type="SELECTED"),
            S("Booleans", [F("Union", lambda: _boolean("UNION")), F("Difference", lambda: _boolean("DIFFERENCE")),
                           F("Intersection", lambda: _boolean("INTERSECT"))]),
            SEP,
            F("Smooth", lambda: _add_mod("SUBSURF")),
            F("Reduce", lambda: _add_mod("DECIMATE")),
            F("Mirror", lambda: _add_mod("MIRROR")),
            O("Symmetrize", "mesh.symmetrize", invoke=True),
            F("Remesh (Voxel)", lambda: __import__("landfall_studio.continuity", fromlist=["x"]).voxel_remesh_active()),
            O("Retopologize (QuadriFlow)", "object.quadriflow_remesh", invoke=True),
            SEP,
            O("Fill Hole", "mesh.fill_holes"),
            O("Triangulate", "mesh.quads_convert_to_tris"),
            O("Quadrangulate", "mesh.tris_convert_to_quads"),
            O("Cleanup…", "mesh.dissolve_degenerate"),
        ]),
        ("Edit Mesh", [
            H("Components"),
            O("Add Divisions", "mesh.subdivide"),
            F("Bevel", _caddy("BEVEL"), "Ctrl+B"),
            F("Bridge", _caddy("BRIDGE")),
            O("Circularize", "transform.tosphere", invoke=True),
            O("Collapse", "mesh.merge", type="COLLAPSE"),
            F("Connect", _caddy("CONNECT")),
            O("Detach", "mesh.edge_split", type="VERT"),
            F("Extrude", _caddy("EXTRUDE"), "Ctrl+E"),
            O("Merge", "mesh.remove_doubles"),
            O("Merge to Center", "mesh.merge", type="CENTER"),
            O("Average Vertices", "mesh.vertices_smooth", factor=0.5, repeat=1),
            O("Chamfer Vertex", "mesh.bevel", invoke=True, affect="VERTICES"),
            O("Poke Face", "mesh.poke"),
            O("Duplicate", "mesh.duplicate_move", invoke=True),
            SEP,
            H("Edges"),
            O("Flip Triangle Edge", "mesh.edge_rotate", use_ccw=False),
            O("Spin Edge Backward", "mesh.edge_rotate", use_ccw=True),
            O("Delete Edge/Vertex", "landfall_studio.smart_delete", hint="Del"),
            SEP,
            H("Tools"),
            O("Insert Edge Loop", "mesh.loopcut_slide", invoke=True, hint="Ctrl+R"),
            O("Offset Edge Loop", "mesh.offset_edge_loops_slide", invoke=True),
            O("Slide Edge", "transform.edge_slide", invoke=True),
            O("Multi-Cut (Knife)", "mesh.knife_tool", invoke=True, hint="K"),
            O("Target Weld", "landfall_studio.target_weld"),
        ]),
        ("Mesh Tools", [
            O("Append to Polygon", "mesh.edge_face_add", hint="Shift+F"),
            F("Connect", _caddy("CONNECT")),
            O("Crease", "transform.edge_crease", invoke=True),
            O("Create Polygon", "wm.tool_set_by_id", name="builtin.poly_build"),
            O("Insert Edge Loop", "mesh.loopcut_slide", invoke=True, hint="Ctrl+R"),
            O("Make Live", "landfall_studio.make_live", toggle=True),
            O("Multi-Cut (Knife)", "mesh.knife_tool", invoke=True, hint="K"),
            O("Offset Edge Loop", "mesh.offset_edge_loops_slide", invoke=True),
            O("Quad Draw", "landfall_studio.quad_draw_modal", invoke=True),
            O("Slide Edge", "transform.edge_slide", invoke=True),
            O("Target Weld", "landfall_studio.target_weld"),
        ]),
        ("Mesh Display", [
            O("Conform Normals", "mesh.normals_make_consistent", inside=False),
            O("Reverse Normals", "mesh.flip_normals"),
            O("Soften Edge (Shade Smooth)", "object.shade_smooth"),
            O("Harden Edge (Shade Flat)", "object.shade_flat"),
        ]),
        ("Deform", _DEFORM),
        ("UV", [
            F("UV Editor", _editor("UV_EDITOR")),
            H("Create"),
            O("Automatic (Smart UV Project)", "uv.smart_project"),
            O("Planar", "uv.project_from_view", camera_bounds=False, scale_to_bounds=True),
            O("Cylindrical", "uv.cylinder_project"),
            O("Spherical", "uv.sphere_project"),
            O("Cube (Box)", "uv.cube_project"),
            H("Modify"),
            O("Cut UV Edges", "mesh.mark_seam", clear=False),
            O("Sew UV Edges", "mesh.mark_seam", clear=True),
            O("Unfold", "uv.unwrap", method="CONFORMAL"),
            O("Layout", "uv.pack_islands"),
            O("Unwrap + Pack", "landfall_studio.uv_unwrap_pack"),
            O("Texel Density", "landfall_studio.texel_density", action="GET"),
        ]),
        ("Generate", [
            F("Geometry Nodes Modifier", lambda: _add_mod("NODES")),
            F("Geometry Node Editor", _editor("GEOMETRY_NODE_EDITOR")),
            F("Modifier Stack", _dock("MODIFIER_STACK")),
        ]),
        ("Cache", [O("Alembic Export…", "wm.alembic_export", invoke=True), O("Alembic Import…", "wm.alembic_import", invoke=True)]),
    ],
    "Rigging": [
        ("Skeleton", [O("Add Armature", "object.armature_add"), O("Mirror Joints (Symmetrize)", "armature.symmetrize")]),
        ("Skin", [
            O("Bind Skin (Automatic Weights)", "object.parent_set", type="ARMATURE_AUTO"),
            O("Paint Skin Weights", "object.mode_set", mode="WEIGHT_PAINT"),
            F("Normalize Weights", _skin("normalize_skin_weights")),
            F("Mirror Weights", _skin("mirror_skin_weights")),
            F("Shape Editor", _dock("SHAPE_EDITOR")),
        ]),
        ("Deform", _DEFORM),
        ("Constrain", [
            F("Parent", lambda: _constraint("CHILD_OF")),
            F("Point", lambda: _constraint("COPY_LOCATION")),
            F("Orient", lambda: _constraint("COPY_ROTATION")),
            F("Scale", lambda: _constraint("COPY_SCALE")),
            F("Aim", lambda: _constraint("DAMPED_TRACK")),
        ]),
        ("Control", [F("Driver Editor", _editor("DRIVER_EDITOR")), O("Add Driver to Property…", "anim.driver_button_add", invoke=True)]),
    ],
    "Animation": [
        ("Key", [O("Set Key", "landfall_studio.set_key", hint="S"), O("Delete Keys", "anim.keyframe_delete_v3d"), F("Graph Editor", _editor("GRAPH_EDITOR")), F("Dope Sheet", _editor("DOPE_SHEET"))]),
        ("Playback", [O("Play / Stop", "screen.animation_play", hint="Alt+V"), O("Go to Start", "screen.frame_jump", end=False), O("Go to End", "screen.frame_jump", end=True)]),
        ("Visualize", [O("Create Motion Trail", "object.paths_calculate", invoke=True), O("Delete Motion Trail", "object.paths_clear")]),
        ("Deform", _DEFORM),
        ("Constrain", [F("Parent", lambda: _constraint("CHILD_OF")), F("Aim", lambda: _constraint("DAMPED_TRACK"))]),
        ("Layers", [F("Time Editor (NLA)", _editor("TIME_EDITOR"))]),
    ],
    "FX": [
        ("Physics", [
            F("Cloth", lambda: _add_mod("CLOTH")),
            F("Soft Body", lambda: _add_mod("SOFT_BODY")),
            F("Collision", lambda: _add_mod("COLLISION")),
            O("Rigid Body (Active)", "rigidbody.object_add", type="ACTIVE"),
            O("Rigid Body (Passive)", "rigidbody.object_add", type="PASSIVE"),
        ]),
        ("Particles", [O("Add Particle System", "object.particle_system_add")]),
        ("Fields", [O("Wind", "object.effector_add", type="WIND"), O("Turbulence", "object.effector_add", type="TURBULENCE"), O("Force", "object.effector_add", type="FORCE")]),
        ("Nodes", [F("Geometry Nodes Modifier", lambda: _add_mod("NODES")), F("Geometry Node Editor", _editor("GEOMETRY_NODE_EDITOR"))]),
    ],
    "Rendering": [
        ("Lighting/Shading", [F("Hypershade", _dock("HYPERSHADE")), F("Hypershade Work Area", _editor("HYPERSHADE_GRAPH")), F("Assign New Material", _assign_new_material)]),
        ("Texturing", [O("3D Paint Tool (Texture Paint)", "object.mode_set", mode="TEXTURE_PAINT"), O("Vertex Paint", "object.mode_set", mode="VERTEX_PAINT")]),
        ("Render", [O("Render Current Frame", "render.render", invoke=True), F("Render Settings", _editor("RENDER_SETTINGS")), F("Render View", _editor("RENDER_VIEW"))]),
        ("Bake", [O("Transfer Maps (Cycles Bake)", "object.bake", invoke=True)]),
    ],
}

MENU_SET_NAMES = ("Modeling", "Rigging", "Animation", "FX", "Rendering")


def all_menu_entries() -> List[Tuple[str, List[Tuple]]]:
    out = list(COMMON_MENUS) + [("Help", HELP_MENU)]
    for menus in MENU_SETS.values():
        out.extend(menus)
    return out
