"""Landfall Studio — Unified Maya-oriented Blender environment.

Integrates pinned checkouts of:
- `landfall` (viewport theme, finite grid, smooth cage, border edges, persistent gizmos, navigation)
- `tentacle` (Qt host, Switchboard UI, marking menus, slot controllers)
- `blendertk` / `pythontk` / `uitk` (modeling, attributes, rigging, scene & workspace utilities)

Strictly enforces:
- Zero wholesale repository copying (resolves pinned checkouts dynamically)
- Zero unsolicited `pip install` on startup or enable (explicit opt-in installer operator)
- Predictable `register()` and `unregister()` with complete cleanup of timers, handlers, and keymaps.
"""

from __future__ import annotations

try:
    import bpy
except ImportError:  # Allow standalone Python CLI tools to import landfall_studio.bootstrap
    bpy = None

from . import character, commands, diagnostics, keymaps, modeling, ui, viewport
from .adapters import blendertk_bridge, landfall_bridge, tentacle_bridge, workspace_bridge
from .bootstrap import deps, paths

bl_info = {
    "name": "Landfall Studio",
    "author": "Framedworld",
    "version": (0, 6, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > Landfall | Preferences > Add-ons > Landfall Studio",
    "description": "Unified Maya-oriented Blender environment (Landfall + Tentacle + blendertk)",
    "category": "3D View",
}


if bpy is not None:

    class LANDFALL_STUDIO_OT_install_dependencies(bpy.types.Operator):
        """Explicit opt-in installer for PySide6, qtpy, and Pillow into the configured dependencies directory."""

        bl_idname = "landfall_studio.install_dependencies"
        bl_label = "Install Qt & Python Dependencies"
        bl_description = (
            "Explicitly install PySide6, qtpy, and Pillow into the Landfall Studio "
            "dependencies folder and initialize the Tentacle Qt host"
        )

        target_dir: bpy.props.StringProperty(
            name="Target Directory",
            subtype="DIR_PATH",
            default="",
            options={"SKIP_SAVE"},
        )

        def execute(self, context):
            lf_mod = landfall_bridge.get_module()
            p = lf_mod.prefs(context) if lf_mod is not None else None
            custom_deps = self.target_dir or (getattr(p, "deps_dir", "") if p else "")
            custom_upstream = getattr(p, "upstream_root", "") if p else ""

            result = deps.install_dependencies(target_dir=custom_deps or None)
            if not result["ok"]:
                self.report(
                    {"ERROR"},
                    f"Dependency install failed (code {result.get('returncode')}): {result.get('stderr', '')[:180]}",
                )
                return {"CANCELLED"}

            if p is not None and getattr(p, "enable_tentacle", True):
                profile = getattr(p, "interaction_profile", "MAYA") or "MAYA"
                key_show = (
                    "Key_Space"
                    if profile == "MAYA"
                    else (getattr(p, "tentacle_key", "Z") or "Z")
                )
                tentacle_bridge.register(
                    key_show=key_show,
                    auto_restore_script_console=bool(
                        getattr(p, "auto_restore_script_console", False)
                    ),
                    custom_upstream_root=custom_upstream or None,
                    custom_deps_dir=result["target_dir"],
                )
                ui.register()
                keymaps.apply_profile(context, profile)

            self.report(
                {"INFO"},
                f"Dependencies ready in {result['target_dir']} (Tentacle={tentacle_bridge.get_state()})",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_diagnostics_report(bpy.types.Operator):
        """Generate and print the Landfall Studio module & runtime diagnostic report."""

        bl_idname = "landfall_studio.diagnostics_report"
        bl_label = "Run Studio Diagnostics"
        bl_description = "Print a full diagnostic report of upstream SHAs, Qt packages, and active bridges"

        def execute(self, context):
            rep = diagnostics.get_report()
            text = diagnostics.format_report(rep)
            print(text)
            self.report(
                {"INFO"},
                f"Diagnostics: Qt={rep['qt_available']}, FullStack={rep['full_stack_ready']}, Tentacle={rep['subsystems']['tentacle_state']}",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_show_tentacle(bpy.types.Operator):
        """Open the Tentacle Qt Marking Menu / Switchboard window."""

        bl_idname = "landfall_studio.show_tentacle"
        bl_label = "Open Tentacle Marking Menu"
        bl_description = "Show the Tentacle Qt Switchboard marking menu window"

        def execute(self, context):
            if tentacle_bridge.get_tcl_instance() is None:
                lf_mod = landfall_bridge.get_module()
                p = lf_mod.prefs(context) if lf_mod is not None else None
                profile = getattr(p, "interaction_profile", "MAYA") if p else "MAYA"
                key_show = (
                    "Key_Space"
                    if profile == "MAYA"
                    else (getattr(p, "tentacle_key", "Z") if p else "Z")
                )
                res = tentacle_bridge.register(
                    key_show=key_show,
                    auto_restore_script_console=bool(
                        getattr(p, "auto_restore_script_console", False)
                    )
                    if p
                    else False,
                )
                if not res["ok"]:
                    self.report(
                        {"WARNING"},
                        "Tentacle Qt dependencies are missing. Use 'Install Qt & Python Dependencies' in Preferences.",
                    )
                    return {"CANCELLED"}
                ui.register()

            info = tentacle_bridge.show_window_for_test()
            if not info["visible"]:
                self.report({"WARNING"}, "Tentacle Qt window did not become visible.")
                return {"CANCELLED"}
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_btk_create_primitive(bpy.types.Operator):
        """Create a polygon primitive and center/freeze its pivot using blendertk."""

        bl_idname = "landfall_studio.btk_create_primitive"
        bl_label = "Create Primitive (blendertk)"
        bl_description = "Create a polygon mesh via blendertk.Primitives and center/freeze its transforms"
        bl_options = {"REGISTER", "UNDO"}

        primitive_type: bpy.props.EnumProperty(
            name="Primitive",
            items=(
                ("CUBE", "Cube", "Create a polygon cube via blendertk"),
                ("SPHERE", "Sphere", "Create a polygon sphere via blendertk"),
                ("CYLINDER", "Cylinder", "Create a polygon cylinder via blendertk"),
                ("PLANE", "Plane", "Create a polygon plane via blendertk"),
            ),
            default="CUBE",
        )
        size: bpy.props.FloatProperty(
            name="Size",
            default=2.0,
            min=0.01,
            max=1000.0,
        )

        def execute(self, context):
            prim_type = self.primitive_type
            prim_size = float(self.size)
            try:
                res = blendertk_bridge.execute_sample_command(
                    primitive_type=prim_type,
                    size=prim_size,
                )
            except Exception as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}

            active_obj = getattr(context.view_layer.objects, "active", None)
            if active_obj is not None:
                ui.attach_primitive_history(
                    active_obj,
                    prim_type=prim_type,
                    width=prim_size,
                    height=prim_size,
                    depth=prim_size,
                    radius=prim_size * 0.5,
                )

            # Record in unified Studio command history so 'G' repeats primitive creation
            commands.record_command(
                cmd_id="landfall_studio.btk_create_primitive",
                kwargs={"primitive_type": prim_type, "size": prim_size},
                callable_fn=lambda primitive_type=prim_type, size=prim_size: blendertk_bridge.execute_sample_command(
                    primitive_type=primitive_type, size=size
                ),
                label=f"Create {prim_type.title()} (blendertk)",
                repeatable=True,
            )

            self.report(
                {"INFO"},
                f"Created {res['object_name']} ({res['vertex_count']} verts, {res['polygon_count']} faces) via blendertk {res['btk_version']}",
            )
            return {"FINISHED"}

    STUDIO_CLASSES = (
        (
            LANDFALL_STUDIO_OT_install_dependencies,
            LANDFALL_STUDIO_OT_diagnostics_report,
            LANDFALL_STUDIO_OT_show_tentacle,
            LANDFALL_STUDIO_OT_btk_create_primitive,
        )
        + viewport.VIEWPORT_CLASSES
        + keymaps.KEYMAP_CLASSES
        + ui.UI_CLASSES
        + modeling.MODELING_CLASSES
        + character.CHARACTER_CLASSES
    )
else:
    STUDIO_CLASSES = ()

_studio_registered = False


def _draw_studio_preferences(prefs_self, context):
    """Render Landfall Studio integration diagnostics, profile controls, and Qt desktop controls in Preferences."""
    layout = prefs_self.layout
    box = layout.box()
    box.label(
        text="Landfall Studio — Unified Maya Environment (Phase 06)",
        icon="PREFERENCES",
    )

    rep = diagnostics.get_report(
        custom_upstream_root=getattr(prefs_self, "upstream_root", "") or None,
        custom_deps_dir=getattr(prefs_self, "deps_dir", "") or None,
    )
    dep_data = rep["dependencies"]

    col = box.column(align=True)
    prof_row = col.row(align=True)
    prof_row.label(text=f"Active Profile: {keymaps.get_active_profile()}")
    prof_row.operator(
        "landfall_studio.set_interaction_profile", text="Maya Profile"
    ).profile = "MAYA"
    prof_row.operator(
        "landfall_studio.set_interaction_profile", text="Hybrid Profile"
    ).profile = "HYBRID"

    col.prop(prefs_self, "upstream_root")
    col.prop(prefs_self, "deps_dir")
    col.prop(prefs_self, "enable_tentacle")
    row = col.row(align=True)
    row.prop(prefs_self, "tentacle_key")
    row.prop(prefs_self, "auto_restore_script_console")

    status_box = box.box()
    status_box.label(
        text=f"Full Stack Ready: {'YES' if rep['full_stack_ready'] else 'NO (Missing Deps)'}",
        icon="CHECKMARK" if rep["full_stack_ready"] else "ERROR",
    )
    pkg_row = status_box.row(align=True)
    for pkg_name, pkg_info in dep_data["packages"].items():
        pkg_row.label(
            text=f"{pkg_name}: {'OK' if pkg_info['available'] else 'Missing'}",
            icon="CHECKMARK" if pkg_info["available"] else "CANCEL",
        )

    act_row = box.row(align=True)
    act_row.operator(
        "landfall_studio.install_dependencies",
        text="Install Qt & Python Dependencies",
        icon="IMPORT",
    )
    act_row.operator(
        "landfall_studio.diagnostics_report",
        text="Diagnostics",
        icon="INFO",
    )
    if rep["full_stack_ready"]:
        act_row.operator(
            "landfall_studio.show_tentacle",
            text="Open Tentacle UI",
            icon="WINDOW",
        )
        qt_row = box.row(align=True)
        op_cb = qt_row.operator("landfall_studio.open_qt_panel", text="Channel Box")
        op_cb.panel_id = "channels"
        op_cb.docked = True
        op_ws = qt_row.operator("landfall_studio.open_qt_panel", text="Workspace Editor")
        op_ws.panel_id = "workspace_editor"
        op_ws.docked = False
        op_rm = qt_row.operator("landfall_studio.open_qt_panel", text="Reference Manager")
        op_rm.panel_id = "reference_manager"
        op_rm.docked = False
        qt_row.operator("landfall_studio.toggle_script_output", text="Script Output")


def register():
    """Register Landfall Studio: upstream paths, Landfall viewport/tools, studio operators, Tentacle Qt host, UI desktop, and Maya profile."""
    global _studio_registered
    if _studio_registered:
        return

    pkg_name = __package__ or "landfall_studio"

    # 1. Pre-flight check of paths and dependencies (never triggers pip install)
    dep_status = deps.check_dependencies()

    # 2. Register Studio operators (bootstrap, viewport interaction, marking menus, keymap profile, Qt UI desktop, character)
    for cls in STUDIO_CLASSES:
        bpy.utils.register_class(cls)
    viewport.register_marking_menu_handlers()
    viewport.register_hud_handler()
    character.register_handlers()

    # 3. Register pinned upstream Landfall (theme, finite grid, smooth cage, border edges, gizmos, navigation)
    landfall_bridge.register(
        addon_package=pkg_name,
        prefs_draw_hook=_draw_studio_preferences,
    )

    # 4. Initialize Tentacle Qt host & Switchboard only if all Qt/Python dependencies are present
    lf_mod = landfall_bridge.get_module()
    p = lf_mod.prefs(bpy.context) if lf_mod is not None else None
    enable_tentacle = getattr(p, "enable_tentacle", True) if p is not None else True
    profile = getattr(p, "interaction_profile", "MAYA") if p is not None else "MAYA"
    key_show = (
        "Key_Space"
        if profile == "MAYA"
        else ((getattr(p, "tentacle_key", "Z") if p is not None else "Z") or "Z")
    )
    auto_console = (
        bool(getattr(p, "auto_restore_script_console", False)) if p is not None else False
    )

    if enable_tentacle and dep_status["full_stack_ready"]:
        tentacle_bridge.register(
            key_show=key_show,
            auto_restore_script_console=auto_console,
        )
        workspace_bridge.sync_from_landfall()
    else:
        # Record degraded state without auto-installing anything
        tentacle_bridge.register(
            key_show=key_show,
            auto_restore_script_console=auto_console,
        )

    # 5. Register unified Qt window desktop & workspace integration
    ui.register()

    # 6. Apply interaction profile (MAYA by default) and initialize persistent Move gizmo
    keymaps.apply_profile(bpy.context, profile=profile)
    commands.set_active_tool("TRANSLATE", axis="X")
    viewport.apply_gizmo_for_tool(bpy.context, "TRANSLATE")

    _studio_registered = True


def unregister():
    """Unregister Landfall Studio and restore all Blender theme, viewport, keymap, Qt desktop, handler, and timer states."""
    global _studio_registered
    if not _studio_registered:
        return

    # 1. Remove Studio keymap bindings and restore all muted native user keymap items
    try:
        keymaps.remove_studio_keymaps(bpy.context)
    except Exception as exc:
        print(f"[landfall_studio] keymaps unregister warning: {exc}")

    # 2. Tear down unified Qt window desktop & right dock before tearing down Tentacle QApplication
    try:
        ui.unregister()
    except Exception as exc:
        print(f"[landfall_studio] ui unregister warning: {exc}")

    # 3. Stop any open Studio marking menu & HUD draw handlers and clear command, modeling, and character state
    try:
        viewport.unregister_hud_handler()
        viewport.unregister_marking_menu_handlers()
        character.unregister_handlers()
        modeling.clear_modeling_state()
        commands.clear_state()
    except Exception as exc:
        print(f"[landfall_studio] viewport/commands unregister warning: {exc}")

    # 4. Tear down Tentacle Qt host, pollers, keymaps, SelectionOrder, and ScriptConsole
    try:
        tentacle_bridge.unregister()
    except Exception as exc:
        print(f"[landfall_studio] tentacle_bridge unregister warning: {exc}")

    # 5. Tear down upstream Landfall (restores theme, viewport grid, navigation prefs, draw handlers, timers, keymaps)
    try:
        landfall_bridge.unregister()
    except Exception as exc:
        print(f"[landfall_studio] landfall_bridge unregister warning: {exc}")

    # 6. Unregister Studio operators
    for cls in reversed(STUDIO_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    _studio_registered = False


