"""Top-Docked Maya Status Line & Tabbed Icon Shelf (`landfall_studio.ui.shelf`).

Provides:
- `SHELF_TABS`: Canonical Maya shelf definitions (`Polygons`, `Modeling`, `Subdiv & Display`,
  `UV & Shading`, `Deform & Rigging`, `Pipeline`) with vector icon names, labels, single-click
  commands, and double-click / `□` option-box Tool Settings targets.
- `MayaShelfWidget`: Two-row Modern Maya top bar:
  - **Row 1 — Maya Status Line**: Menu Set selector (`Modeling [F2]`, `Rigging [F3]`, `Animation [F4]`,
    `Rendering [F6]`), Selection Mode Masks (`Object F8`, `Vertex F9`, `Edge F10`, `Face F11`, `UV F12`),
    Snap Magnets (`Grid X`, `Curve C`, `Point V`, `Pivot D`), History actions (`Center Pivot`,
    `Delete History`, `Freeze`), and right-aligned Sidebar Workspace Toggles (`Outliner`, `Channel Box`,
    `Tool Settings`, `Attribute Editor`).
  - **Row 2 — Tabbed Icon Shelf**: Custom `_MayaShelfTileButton` tiles where single-click executes the
    command and double-click (or clicking the top-right `□` badge) opens `Tool Settings`.
- `TopShelfQtDock`: `WS_CHILD` dock manager embedding `MayaShelfWidget` at the top of the 3D Viewport.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .. import commands as cmd_registry
from . import channel_box_ext, icons, style, tool_settings

SHELF_TABS: Dict[str, List[Dict[str, str]]] = {
    "Polygons": [
        {"id": "poly_cube", "label": "Cube", "icon": "poly_cube", "tool_ctx": "POLY_CUBE", "tip": "Create Polygon Cube (Double-click / □ for Option Box)"},
        {"id": "poly_sphere", "label": "Sphere", "icon": "poly_sphere", "tool_ctx": "POLY_SPHERE", "tip": "Create Polygon Sphere (Double-click / □ for Option Box)"},
        {"id": "poly_cylinder", "label": "Cylinder", "icon": "poly_cylinder", "tool_ctx": "POLY_CYLINDER", "tip": "Create Polygon Cylinder (Double-click / □ for Option Box)"},
        {"id": "poly_plane", "label": "Plane", "icon": "poly_plane", "tool_ctx": "POLY_PLANE", "tip": "Create Polygon Plane (Double-click / □ for Option Box)"},
        {"id": "extrude", "label": "Extrude", "icon": "extrude", "tool_ctx": "EXTRUDE", "tip": "Poly Extrude / Solidify (Double-click / □ for Option Box)"},
        {"id": "bevel", "label": "Bevel", "icon": "bevel", "tool_ctx": "BEVEL", "tip": "Poly Bevel (Double-click / □ for Option Box)"},
        {"id": "bridge", "label": "Bridge", "icon": "bridge", "tool_ctx": "BRIDGE", "tip": "Bridge Edge Loops"},
        {"id": "merge_verts", "label": "Merge", "icon": "merge_verts", "tool_ctx": "MERGE", "tip": "Merge Vertices at Center / By Distance"},
        {"id": "center_pivot", "label": "Center Piv", "icon": "center_pivot", "tool_ctx": "PIVOT", "tip": "Modify > Center Pivot"},
        {"id": "delete_history", "label": "Del Hist", "icon": "delete_history", "tool_ctx": "HISTORY", "tip": "Edit > Delete by Type > History (Alt+Shift+D)"},
        {"id": "freeze_transforms", "label": "Freeze", "icon": "freeze_transforms", "tool_ctx": "FREEZE", "tip": "Modify > Freeze Transformations"},
    ],
    "Modeling": [
        {"id": "extrude", "label": "Extrude", "icon": "extrude", "tool_ctx": "EXTRUDE", "tip": "Poly Extrude"},
        {"id": "bevel", "label": "Bevel", "icon": "bevel", "tool_ctx": "BEVEL", "tip": "Poly Bevel"},
        {"id": "bridge", "label": "Bridge", "icon": "bridge", "tool_ctx": "BRIDGE", "tip": "Bridge Edge Loops"},
        {"id": "merge_verts", "label": "Merge", "icon": "merge_verts", "tool_ctx": "MERGE", "tip": "Merge Vertices"},
        {"id": "smooth_1", "label": "Cage (1)", "icon": "smooth_1", "tool_ctx": "SUBDIV", "tip": "Smooth Mesh Preview: Base Cage (1)"},
        {"id": "smooth_2", "label": "Both (2)", "icon": "smooth_2", "tool_ctx": "SUBDIV", "tip": "Smooth Mesh Preview: Cage + Subdiv (2)"},
        {"id": "smooth_3", "label": "Smooth (3)", "icon": "smooth_3", "tool_ctx": "SUBDIV", "tip": "Smooth Mesh Preview: Smooth (3)"},
        {"id": "border_edges", "label": "Borders", "icon": "border_edges", "tool_ctx": "DISPLAY", "tip": "Toggle Maya Border Edge Highlight"},
        {"id": "center_pivot", "label": "Center Piv", "icon": "center_pivot", "tool_ctx": "PIVOT", "tip": "Center Pivot"},
        {"id": "delete_history", "label": "Del Hist", "icon": "delete_history", "tool_ctx": "HISTORY", "tip": "Delete Construction History"},
    ],
    "Subdiv & Display": [
        {"id": "smooth_1", "label": "Mode 1", "icon": "smooth_1", "tool_ctx": "SUBDIV", "tip": "Base Mesh Display (1)"},
        {"id": "smooth_2", "label": "Mode 2", "icon": "smooth_2", "tool_ctx": "SUBDIV", "tip": "Cage + Smooth Display (2)"},
        {"id": "smooth_3", "label": "Mode 3", "icon": "smooth_3", "tool_ctx": "SUBDIV", "tip": "Smooth Subdiv Display (3)"},
        {"id": "wire_on_shaded", "label": "Wireframe", "icon": "wire_on_shaded", "tool_ctx": "DISPLAY", "tip": "Toggle Wireframe on Shaded"},
        {"id": "xray", "label": "X-Ray", "icon": "xray", "tool_ctx": "DISPLAY", "tip": "Toggle Viewport X-Ray"},
        {"id": "border_edges", "label": "Borders", "icon": "border_edges", "tool_ctx": "DISPLAY", "tip": "Toggle Open Border Edge Highlight"},
        {"id": "isolate", "label": "Isolate", "icon": "isolate", "tool_ctx": "DISPLAY", "tip": "Isolate Selected (Ctrl+1)"},
    ],
    "UV & Shading": [
        {"id": "uv_mode", "label": "UV Mode", "icon": "uv_unwrap", "tool_ctx": "UV", "tip": "Enter UV Component Mode (F12)"},
        {"id": "pbr_shader", "label": "Std Surface", "icon": "pbr_shader", "tool_ctx": "SHADER", "tip": "Assign New Standard Surface / Principled Shader"},
        {"id": "wire_on_shaded", "label": "Wire/Shaded", "icon": "wire_on_shaded", "tool_ctx": "DISPLAY", "tip": "Toggle Wireframe on Shaded"},
    ],
    "Deform & Rigging": [
        {"id": "joint_tool", "label": "Create Joint", "icon": "joint_tool", "tool_ctx": "RIGGING", "tip": "Create Armature / Joint"},
        {"id": "bevel", "label": "Bevel Mod", "icon": "bevel", "tool_ctx": "BEVEL", "tip": "Add Bevel Input Node"},
        {"id": "extrude", "label": "Solidify", "icon": "extrude", "tool_ctx": "EXTRUDE", "tip": "Add Solidify Input Node"},
        {"id": "freeze_transforms", "label": "Freeze", "icon": "freeze_transforms", "tool_ctx": "FREEZE", "tip": "Freeze Transformations"},
        {"id": "delete_history", "label": "Bake Hist", "icon": "delete_history", "tool_ctx": "HISTORY", "tip": "Delete Non-Deformer / Construction History"},
    ],
    "Pipeline": [
        {"id": "workspace_ed", "label": "Workspace", "icon": "workspace_ed", "tool_ctx": "PIPELINE", "tip": "Open Project Workspace Editor (workspace.mel)"},
        {"id": "reference_mgr", "label": "References", "icon": "reference_mgr", "tool_ctx": "PIPELINE", "tip": "Open Maya Reference Editor"},
        {"id": "new_display_layer", "label": "+ Layer", "icon": "quad_view", "tool_ctx": "LAYERS", "tip": "Create Display Layer from Selected Objects"},
        {"id": "script_output", "label": "Script Ed", "icon": "hierarchy_mgr", "tool_ctx": "PIPELINE", "tip": "Toggle Script Output Console"},
    ],
}


def execute_shelf_item(item_id: str) -> Dict[str, Any]:
    """Execute a Maya Shelf button command by `item_id` and record in command feedback."""
    import bpy
    from . import desktop

    iid = (item_id or "").strip().lower()
    if iid in ("poly_cube", "poly_sphere", "poly_cylinder", "poly_plane"):
        ptype = iid.replace("poly_", "").upper()
        opts = tool_settings.get_tool_settings_snapshot()["option_box"]
        res = channel_box_ext.create_maya_primitive(
            primitive_type=ptype,
            width=opts["prim_width"],
            height=opts["prim_height"],
            depth=opts["prim_depth"],
            radius=opts["prim_radius"],
            subdivisions_x=opts["prim_subdivisions_x"],
            subdivisions_y=opts["prim_subdivisions_y"],
            subdivisions_z=opts["prim_subdivisions_z"],
        )
        cmd_registry.record_command(
            cmd_id=f"shelf.{iid}",
            kwargs={"primitive_type": ptype},
            callable_fn=lambda p=ptype: channel_box_ext.create_maya_primitive(primitive_type=p),
            label=f"Poly {ptype.title()}",
            repeatable=True,
        )
        desktop.sync_channels_now()
        channel_box_ext.refresh_channel_box_extensions()
        desktop.set_command_feedback(f"poly{ptype.title()}", res.get("object_name", ptype))
        return {"ok": True, "item_id": iid, "result": res}

    if iid in ("bevel", "extrude"):
        tool_settings.set_tool_setting("tool_context", iid.upper())
        res = tool_settings.apply_current_tool_option_box()
        desktop.sync_channels_now()
        channel_box_ext.refresh_channel_box_extensions()
        desktop.set_command_feedback(f"poly{iid.title()}", str(res.get("modifier", iid)))
        return {"ok": True, "item_id": iid, "result": res}

    if iid == "center_pivot":
        active = getattr(bpy.context.view_layer.objects, "active", None)
        if active is not None:
            try:
                import blendertk as btk

                btk.bake_pivot(active, to="CENTER")
            except Exception:
                try:
                    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
                except Exception:
                    pass
        desktop.sync_channels_now()
        desktop.set_command_feedback("CenterPivot", active.name if active else "OK")
        return {"ok": True, "item_id": iid}

    if iid == "delete_history":
        res = channel_box_ext.delete_construction_history()
        desktop.sync_channels_now()
        channel_box_ext.refresh_channel_box_extensions()
        desktop.set_command_feedback("DeleteHistory", res.get("object_name", "OK"))
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "freeze_transforms":
        active = getattr(bpy.context.view_layer.objects, "active", None)
        if active is not None and not channel_box_ext.is_datablock_linked(active):
            try:
                import blendertk as btk

                btk.freeze_transforms(
                    [active], location=True, rotation=True, scale=True
                )
            except Exception:
                pass
        desktop.sync_channels_now()
        desktop.set_command_feedback("FreezeTransformations", active.name if active else "OK")
        return {"ok": True, "item_id": iid}

    if iid in ("smooth_1", "smooth_2", "smooth_3"):
        mode_map = {"smooth_1": "CAGE", "smooth_2": "BOTH", "smooth_3": "SMOOTH"}
        try:
            bpy.ops.landfall.smooth_preview(mode=mode_map[iid])
        except Exception:
            pass
        desktop.set_command_feedback("displaySmoothness", mode_map[iid])
        return {"ok": True, "item_id": iid}

    if iid == "wire_on_shaded":
        active = getattr(bpy.context.view_layer.objects, "active", None)
        if active is not None:
            active.show_wire = not bool(active.show_wire)
            active.show_all_edges = active.show_wire
        desktop.set_command_feedback("WireframeOnShaded", "Toggled")
        return {"ok": True, "item_id": iid}

    if iid == "xray":
        wm = getattr(bpy.context, "window_manager", None)
        for win in (wm.windows if wm else []):
            for a in (win.screen.areas if win.screen else []):
                if a.type == "VIEW_3D":
                    sp = a.spaces.active
                    if sp is not None and hasattr(sp, "shading"):
                        sp.shading.show_xray = not bool(sp.shading.show_xray)
        desktop.set_command_feedback("ToggleXRay", "Toggled")
        return {"ok": True, "item_id": iid}

    if iid == "border_edges":
        try:
            bpy.ops.landfall.toggle_border_edges()
        except Exception:
            pass
        return {"ok": True, "item_id": iid}

    if iid == "uv_mode":
        try:
            bpy.ops.landfall_studio.component_mode(mode="UV")
        except Exception:
            pass
        return {"ok": True, "item_id": iid}

    if iid == "pbr_shader":
        res = attribute_editor_assign_shader()
        return {"ok": True, "item_id": iid, "result": res}

    if iid == "workspace_ed":
        return desktop.open_panel("workspace_editor", docked=False)

    if iid == "reference_mgr":
        return desktop.open_panel("reference_manager", docked=False)

    if iid == "script_output":
        return desktop.open_panel("script_output", docked=True)

    if iid == "new_display_layer":
        res = channel_box_ext.create_display_layer(assign_selected=True)
        channel_box_ext.refresh_channel_box_extensions()
        return {"ok": True, "item_id": iid, "result": res}

    desktop.set_command_feedback(iid, "Executed")
    return {"ok": True, "item_id": iid}


def attribute_editor_assign_shader() -> Dict[str, Any]:
    from . import attribute_editor

    return attribute_editor.set_attribute_editor_value(
        "material", "material_name", "aiStandardSurface1"
    )


def open_tool_settings_for_shelf_item(item_id: str, tool_ctx: Optional[str] = None) -> Dict[str, Any]:
    """Open the `Tool Settings` (`□` Option Box) inspector in the right dock for `item_id`."""
    from . import desktop

    ctx_name = tool_ctx or item_id.upper()
    tool_settings.set_tool_setting("tool_context", ctx_name)
    res = desktop.cycle_right_dock("TOOL_SETTINGS")
    desktop.set_command_feedback(f"{item_id} Option Box (□)", f"Tool Settings: {ctx_name}")
    return res


def _create_shelf_tile_button(spec: Dict[str, str]):
    """Create a Maya Shelf tile button with single-click execute, double-click Tool Settings, and a top-right `□` badge."""
    from qtpy import QtCore, QtGui, QtWidgets

    class _MayaShelfTileButton(QtWidgets.QToolButton):
        def __init__(self, item_spec: Dict[str, str]):
            super().__init__()
            self.spec = item_spec
            self.setObjectName("MayaShelfTile")
            self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            self.setIcon(icons.get_icon(item_spec["icon"], 22))
            self.setIconSize(QtCore.QSize(22, 22))
            self.setText(item_spec["label"])
            self.setToolTip(item_spec.get("tip", item_spec["label"]))
            self.setFixedSize(48, 42)

        def mousePressEvent(self, event):
            # Clicking the top-right 12x12 '□' option-box corner opens Tool Settings directly
            if event.button() == QtCore.Qt.LeftButton and event.pos().x() >= self.width() - 13 and event.pos().y() <= 13:
                open_tool_settings_for_shelf_item(
                    self.spec["id"], self.spec.get("tool_ctx")
                )
                event.accept()
                return
            if event.button() == QtCore.Qt.RightButton:
                open_tool_settings_for_shelf_item(
                    self.spec["id"], self.spec.get("tool_ctx")
                )
                event.accept()
                return
            super().mousePressEvent(event)

        def mouseDoubleClickEvent(self, event):
            open_tool_settings_for_shelf_item(
                self.spec["id"], self.spec.get("tool_ctx")
            )
            event.accept()

        def paintEvent(self, event):
            super().paintEvent(event)
            # Draw subtle Maya '□' option box glyph in top-right corner
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.Antialiasing, False)
            p.setPen(QtGui.QPen(QtGui.QColor("#6E7B8B"), 1))
            p.drawRect(self.width() - 10, 3, 6, 6)
            p.end()

    btn = _MayaShelfTileButton(spec)
    btn.clicked.connect(lambda: execute_shelf_item(spec["id"]))
    return btn


class MayaShelfWidget:
    """Two-row Modern Maya Status Line + Tabbed Icon Shelf Qt widget."""

    def __init__(self, parent: Any = None):
        from qtpy import QtCore, QtWidgets

        self.root = QtWidgets.QFrame(parent)
        self.root.setObjectName("MayaPanelRoot")
        style.apply_studio_style(self.root)

        vlay = QtWidgets.QVBoxLayout(self.root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # --- Row 1: Maya Status Line (26px) ---
        status_bar = QtWidgets.QFrame()
        status_bar.setObjectName("MayaStatusLine")
        status_bar.setFixedHeight(26)
        slay = QtWidgets.QHBoxLayout(status_bar)
        slay.setContentsMargins(6, 2, 6, 2)
        slay.setSpacing(4)

        # Menu Set Selector
        self.cmb_menu_set = QtWidgets.QComboBox()
        self.cmb_menu_set.addItems(
            ["Modeling [F2]", "Rigging [F3]", "Animation [F4]", "FX [F5]", "Rendering [F6]"]
        )
        self.cmb_menu_set.setFixedWidth(115)
        self.cmb_menu_set.currentIndexChanged.connect(self._on_menu_set_changed)
        slay.addWidget(self.cmb_menu_set)

        slay.addWidget(self._make_vsep())

        # Selection Mode Masks (F8 Object, F9 Vertex, F10 Edge, F11 Face, F12 UV)
        for mask_icon, mode_id, tip in (
            ("mask_obj", "OBJECT", "Object Mode (F8)"),
            ("mask_vert", "VERT", "Vertex Component Mode (F9)"),
            ("mask_edge", "EDGE", "Edge Component Mode (F10)"),
            ("mask_face", "FACE", "Face Component Mode (F11)"),
            ("mask_uv", "UV", "UV Component Mode (F12)"),
        ):
            btn = QtWidgets.QToolButton()
            btn.setIcon(icons.get_icon(mask_icon, 16))
            btn.setIconSize(QtCore.QSize(16, 16))
            btn.setFixedSize(22, 20)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, m=mode_id: self._set_component_mode(m))
            slay.addWidget(btn)

        slay.addWidget(self._make_vsep())

        # Snap Magnets (X Grid, C Curve/Edge, V Point/Vertex, D Pivot)
        for snap_icon, snap_elem, tip in (
            ("snap_grid", "INCREMENT", "Snap to Grid (Hold X)"),
            ("snap_curve", "EDGE", "Snap to Curve / Edge (Hold C)"),
            ("snap_point", "VERTEX", "Snap to Point / Vertex (Hold V)"),
            ("snap_pivot", "PIVOT", "Edit Pivot Mode (Hold D)"),
        ):
            btn = QtWidgets.QToolButton()
            btn.setIcon(icons.get_icon(snap_icon, 16))
            btn.setIconSize(QtCore.QSize(16, 16))
            btn.setFixedSize(22, 20)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, s=snap_elem: self._trigger_snap_toggle(s))
            slay.addWidget(btn)

        slay.addWidget(self._make_vsep())

        # History / Transform quick actions
        for act_icon, act_id, tip in (
            ("center_pivot", "center_pivot", "Center Pivot"),
            ("delete_history", "delete_history", "Delete by Type > History (Alt+Shift+D)"),
            ("freeze_transforms", "freeze_transforms", "Freeze Transformations"),
        ):
            btn = QtWidgets.QToolButton()
            btn.setIcon(icons.get_icon(act_icon, 16))
            btn.setIconSize(QtCore.QSize(16, 16))
            btn.setFixedSize(22, 20)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, a=act_id: execute_shelf_item(a))
            slay.addWidget(btn)

        slay.addStretch(1)

        # Workspace Label Badge + Right Sidebar Quick Toggles
        lbl_ws = QtWidgets.QLabel("Maya Classic")
        lbl_ws.setObjectName("MayaBadgeTeal")
        slay.addWidget(lbl_ws)

        for lbl, mode_target, tip in (
            ("Outliner", "OUTLINER", "Toggle Left DAG Outliner"),
            ("Ch Box", "CHANNEL_BOX", "Show Channel Box / Layer Editor (Ctrl+A)"),
            ("Tool Set", "TOOL_SETTINGS", "Show Tool Settings (□)"),
            ("Attr Ed", "ATTRIBUTE_EDITOR", "Show Attribute Editor (Ctrl+A)"),
        ):
            b = QtWidgets.QPushButton(lbl)
            b.setFixedHeight(20)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, m=mode_target: self._on_workspace_toggle(m))
            slay.addWidget(b)

        vlay.addWidget(status_bar)

        # --- Row 2: Tabbed Icon Shelf (62px) ---
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setFixedHeight(64)
        self.tile_buttons: Dict[str, List[Any]] = {}

        for tab_name, items in SHELF_TABS.items():
            page = QtWidgets.QFrame()
            page.setObjectName("MayaShelfBar")
            play = QtWidgets.QHBoxLayout(page)
            play.setContentsMargins(6, 2, 6, 2)
            play.setSpacing(4)
            self.tile_buttons[tab_name] = []
            for spec in items:
                tile = _create_shelf_tile_button(spec)
                play.addWidget(tile)
                self.tile_buttons[tab_name].append(tile)
            play.addStretch(1)
            self.tabs.addTab(page, tab_name)

        vlay.addWidget(self.tabs)

    @staticmethod
    def _make_vsep():
        from qtpy import QtWidgets

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("color: #141619;")
        return sep

    def _on_menu_set_changed(self, idx: int) -> None:
        tab_map = {0: 0, 1: 4, 2: 4, 3: 2, 4: 3}
        if idx in tab_map and tab_map[idx] < self.tabs.count():
            self.tabs.setCurrentIndex(tab_map[idx])

    def _set_component_mode(self, mode_id: str) -> None:
        import bpy

        try:
            bpy.ops.landfall_studio.component_mode(mode=mode_id)
        except Exception:
            pass

    def _trigger_snap_toggle(self, snap_elem: str) -> None:
        import bpy

        ts = getattr(getattr(bpy.context, "scene", None), "tool_settings", None)
        if ts is None:
            return
        if snap_elem == "PIVOT":
            ts.use_transform_data_origin = not bool(ts.use_transform_data_origin)
        else:
            ts.use_snap = True
            ts.snap_elements = {snap_elem}

    def _on_workspace_toggle(self, target: str) -> None:
        from . import desktop

        if target == "OUTLINER":
            desktop.toggle_left_outliner_dock()
        else:
            desktop.cycle_right_dock(target)


class TopShelfQtDock:
    """Top `WS_CHILD` dock manager embedding `MayaShelfWidget` across the top of the 3D Viewport."""

    DEFAULT_HEIGHT = 90

    def __init__(self):
        from blendertk.ui_utils.qt_dock import QtDock

        self._inner_dock = QtDock(
            editor="Info",
            area_header=False,
            focus_on_hover=True,
            on_detach=self._handle_detach,
        )
        self._created_split_area = False
        self._shelf_ctrl: Optional[MayaShelfWidget] = None

    @property
    def docked(self) -> bool:
        return bool(self._inner_dock.docked)

    @property
    def widget(self):
        return self._shelf_ctrl.root if self._shelf_ctrl is not None else None

    def ensure_shelf_widget(self) -> MayaShelfWidget:
        if self._shelf_ctrl is None:
            self._shelf_ctrl = MayaShelfWidget()
        return self._shelf_ctrl

    def _handle_detach(self) -> None:
        self._created_split_area = False

    @staticmethod
    def _find_or_create_top_area(window, height: int = DEFAULT_HEIGHT):
        import bpy
        from blendertk.ui_utils._ui_utils import _UiUtilsInternal

        view3ds = [a for a in window.screen.areas if a.type == "VIEW_3D"]
        if not view3ds:
            return None, False
        target = max(view3ds, key=lambda a: a.height)
        if target.height <= height + 120:
            return None, False

        # In Blender HORIZONTAL split, factor is the bottom fraction; 1 - factor is the top strip
        factor = max(0.25, min(0.92, 1.0 - (float(height) / float(target.height))))
        before = {a.as_pointer() for a in window.screen.areas}
        try:
            with bpy.context.temp_override(
                window=window,
                screen=window.screen,
                area=target,
                region=_UiUtilsInternal._window_region(target),
            ):
                res = bpy.ops.screen.area_split(direction="HORIZONTAL", factor=factor)
        except (RuntimeError, TypeError):
            return None, False
        if res != {"FINISHED"}:
            return None, False

        new_areas = [a for a in window.screen.areas if a.as_pointer() not in before]
        if not new_areas:
            return None, False
        # Pick the shorter 90px strip at the top (whereas max(key=a.y) picked the 880px viewport)
        top_area = min([new_areas[0], target], key=lambda a: (a.height, a.y))
        try:
            top_area.ui_type = "INFO"
        except TypeError:
            return None, False
        return top_area, True

    def dock_shelf(self, height: Optional[int] = None) -> bool:
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow

        ctrl = self.ensure_shelf_widget()
        if not self._inner_dock.supported():
            try:
                ctrl.root.show()
            except Exception:
                pass
            return False

        if self._inner_dock.docked and self._inner_dock.widget is ctrl.root:
            self.enforce_dock_geometry()
            return True

        window = btk.main_window()
        if window is None:
            return False
        hwnd = BlenderWindow.window_hwnd(window)
        if hwnd is None:
            return False

        area = self._inner_dock.area
        try:
            if area is not None and not any(r.type == "WINDOW" for r in area.regions):
                area = None
        except (ReferenceError, AttributeError):
            area = None

        if area is None:
            area, created = self._find_or_create_top_area(
                window, height=height or self.DEFAULT_HEIGHT
            )
            if area is None:
                return False
            self._created_split_area = created

        dock = self._inner_dock
        dock._stop_glue()
        dock._release_widget()

        dock._window, dock._area, dock._hwnd = window, area, hwnd
        dock._edge_pad = dock._native_edge_pad()
        dock._area_header = False
        dock._apply_area_header(window, area)

        if not dock._embed(ctrl.root, hwnd):
            self.undock()
            return False

        dock._position(dock.content_region())
        dock._start_glue()
        try:
            for region in area.regions:
                region.tag_redraw()
        except Exception:
            pass
        return True

    def enforce_dock_geometry(self) -> Optional[tuple]:
        if not self.docked:
            return None
        dock = self._inner_dock
        dock._last_rect = None
        dock._position(dock.content_region())
        return dock._last_rect

    def undock(self, close_split_area: bool = True) -> None:
        import bpy
        import blendertk as btk

        dock = self._inner_dock
        window = dock._window
        area = dock._area
        dock._stop_glue()
        dock._release_widget()

        if area is not None and window is not None and not bpy.app.background:
            if close_split_area and self._created_split_area:
                try:
                    btk.close_area(window, area)
                except Exception:
                    pass
                self._created_split_area = False

        dock._window = dock._area = dock._hwnd = None
        dock._last_rect = None

    def teardown(self) -> None:
        self.undock(close_split_area=True)
        self._inner_dock.teardown()
        if self._shelf_ctrl is not None:
            try:
                self._shelf_ctrl.root.hide()
                self._shelf_ctrl.root.deleteLater()
            except Exception:
                pass
            self._shelf_ctrl = None
