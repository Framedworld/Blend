"""Left-Docked Maya Tool Box & DAG Outliner (`landfall_studio.ui.outliner`).

Provides:
- `reparent_preserve_world(child_name, parent_name)`: Reparents `child` under `parent` (or unparents
  to world root when `parent_name=""`) while preserving world-space `matrix_world` within `1e-5`.
- `get_dag_outliner_snapshot(filter_text="", show_shapes=True)`: Returns the hierarchical Maya DAG tree
  where each `Transform` (`Object`) expands `[+]` to show its child `Shape` (`Object.data`), active
  `Modifiers`, and child `Transform` nodes.
- `MayaLeftSidebarWidget`: Combines the vertical **Maya Tool Box** (`Select Q`, `Lasso`, `Move W`,
  `Rotate E`, `Scale R`, `Last Tool Y`, double-click opens `Tool Settings`) on the far left with the
  **Maya DAG Outliner** (`QTreeWidget` supporting search filtering, `[Shapes]` expansion, two-way
  selection sync, and `MMB` drag-and-drop world-preserving reparenting).
- `LeftOutlinerQtDock`: `WS_CHILD` dock manager embedding `MayaLeftSidebarWidget` on the left side of
  the 3D Viewport.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .. import commands as cmd_registry
from . import channel_box_ext, icons, style, tool_settings


def _is_descendant_of(candidate_parent: Any, child_obj: Any) -> bool:
    cur = getattr(candidate_parent, "parent", None)
    visited = set()
    while cur is not None and cur.name not in visited:
        if cur == child_obj:
            return True
        visited.add(cur.name)
        cur = getattr(cur, "parent", None)
    return False


def reparent_preserve_world(
    child_name: str,
    parent_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Reparent `child_name` under `parent_name` (or unparent to world root if empty/None) while preserving `matrix_world`."""
    import bpy

    child = bpy.data.objects.get(child_name or "")
    if child is None:
        return {"ok": False, "error": f"Child object '{child_name}' not found"}
    if channel_box_ext.is_datablock_linked(child):
        return {
            "ok": False,
            "linked": True,
            "error": f"Cannot reparent linked library object '{child.name}'",
        }

    clean_parent = (parent_name or "").strip()
    parent_obj = bpy.data.objects.get(clean_parent) if clean_parent else None
    if clean_parent and parent_obj is None:
        return {"ok": False, "error": f"Parent object '{clean_parent}' not found"}

    if parent_obj is not None:
        if parent_obj == child:
            return {"ok": False, "error": "Cannot parent an object to itself"}
        if _is_descendant_of(parent_obj, child):
            return {"ok": False, "error": "Cannot parent an object to its own descendant (cycle)"}

    # Ensure view layer matrices are current before capturing world matrix
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass

    world_before = child.matrix_world.copy()
    child.parent = parent_obj
    if parent_obj is not None:
        child.matrix_parent_inverse = parent_obj.matrix_world.inverted_safe()
    child.matrix_world = world_before

    try:
        bpy.context.view_layer.update()
    except Exception:
        pass

    world_after = child.matrix_world.copy()
    max_diff = max(
        abs(world_before[r][c] - world_after[r][c])
        for r in range(4)
        for c in range(4)
    )
    refresh_outliner()
    return {
        "ok": True,
        "child": child.name,
        "parent": parent_obj.name if parent_obj is not None else None,
        "max_matrix_diff": round(float(max_diff), 7),
        "world_delta": round(float(max_diff), 7),
        "world_translation": tuple(round(float(v), 5) for v in world_after.translation),
    }


def _build_dag_node(obj: Any, children_map: Dict[str, List[Any]], show_shapes: bool) -> Dict[str, Any]:
    sinfo = channel_box_ext.get_object_shape_info(obj)
    sub_nodes: List[Dict[str, Any]] = []

    if show_shapes and sinfo["has_shape"]:
        sub_nodes.append(
            {
                "name": sinfo["shape_name"],
                "kind": "SHAPE",
                "owner_object": obj.name,
                "shape_type": sinfo["shape_type"],
                "linked": sinfo["linked"],
                "children": [],
            }
        )

    if show_shapes:
        for mod in getattr(obj, "modifiers", ()):
            sub_nodes.append(
                {
                    "name": mod.name,
                    "kind": "MODIFIER",
                    "owner_object": obj.name,
                    "modifier_type": mod.type,
                    "children": [],
                }
            )

    for ch_obj in children_map.get(obj.name, ()):
        sub_nodes.append(_build_dag_node(ch_obj, children_map, show_shapes))

    is_sel = False
    try:
        is_sel = bool(obj.select_get())
    except Exception:
        pass

    return {
        "name": obj.name,
        "kind": "TRANSFORM",
        "object_type": obj.type,
        "shape_name": sinfo["shape_name"],
        "parent": obj.parent.name if obj.parent is not None else None,
        "selected": is_sel,
        "linked": channel_box_ext.is_datablock_linked(obj),
        "children": sub_nodes,
    }


def get_dag_outliner_snapshot(
    filter_text: str = "",
    show_shapes: bool = True,
) -> Dict[str, Any]:
    """Build a Maya DAG Outliner snapshot (`Transform` -> `[+]` `Shape` + child `Transform` nodes)."""
    import bpy

    scene = getattr(bpy.context, "scene", None)
    if scene is None:
        return {"ok": False, "roots": [], "object_count": 0}

    flt = (filter_text or "").strip().lower()
    all_objs = sorted(list(scene.objects), key=lambda o: o.name.lower())

    children_map: Dict[str, List[Any]] = {}
    roots_objs: List[Any] = []
    for o in all_objs:
        if flt and flt not in o.name.lower() and (o.data is None or flt not in o.data.name.lower()):
            continue
        if o.parent is not None and not flt:
            children_map.setdefault(o.parent.name, []).append(o)
        else:
            roots_objs.append(o)

    roots = [_build_dag_node(ro, children_map, show_shapes) for ro in roots_objs]
    return {
        "ok": True,
        "filter": filter_text,
        "show_shapes": show_shapes,
        "object_count": len(all_objs),
        "root_count": len(roots),
        "roots": roots,
    }


def select_in_outliner(object_names: List[str]) -> Dict[str, Any]:
    """Select `object_names` in Blender and synchronize the Maya DAG Outliner & Channel Box."""
    import bpy
    from . import desktop

    vl = getattr(bpy.context, "view_layer", None)
    if vl is None:
        return {"ok": False, "selected": []}

    wanted = set(object_names)
    for o in list(vl.objects):
        try:
            o.select_set(o.name in wanted)
        except Exception:
            pass

    active_set = None
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj is not None and obj.name in vl.objects:
            active_set = obj
    if active_set is not None:
        vl.objects.active = active_set

    desktop.sync_channels_now()
    channel_box_ext.refresh_channel_box_extensions()
    refresh_outliner()
    return {
        "ok": True,
        "selected": [o.name for o in vl.objects if o.select_get()],
        "active": vl.objects.active.name if vl.objects.active else None,
    }


def _create_dag_tree_widget(on_reparent_drop, on_selection_changed):
    from qtpy import QtCore, QtWidgets

    class _MayaDagTreeWidget(QtWidgets.QTreeWidget):
        """QTreeWidget supporting Maya MMB (or LMB) drag-and-drop world-preserving reparenting."""

        def __init__(self):
            super().__init__()
            self.setHeaderHidden(True)
            self.setAlternatingRowColors(True)
            self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
            self.setDragEnabled(True)
            self.setAcceptDrops(True)
            self.setDropIndicatorShown(True)
            self.setIndentation(14)
            self._drag_source_obj: Optional[str] = None
            self.itemSelectionChanged.connect(on_selection_changed)

        def mousePressEvent(self, event):
            item = self.itemAt(event.pos())
            if item is not None:
                obj_name = item.data(0, QtCore.Qt.UserRole)
                self._drag_source_obj = str(obj_name) if obj_name else None
            if event.button() == QtCore.Qt.MiddleButton and item is not None:
                # Allow MMB drag initiation just like Maya Outliner
                self.setCurrentItem(item)
                fake_ev = type(event)(
                    QtCore.QEvent.MouseButtonPress,
                    event.localPos(),
                    event.windowPos(),
                    event.screenPos(),
                    QtCore.Qt.LeftButton,
                    QtCore.Qt.LeftButton,
                    event.modifiers(),
                )
                super().mousePressEvent(fake_ev)
                return
            super().mousePressEvent(event)

        def dropEvent(self, event):
            target_item = self.itemAt(event.pos())
            src_name = self._drag_source_obj
            if not src_name:
                sel = self.selectedItems()
                if sel:
                    src_name = str(sel[0].data(0, QtCore.Qt.UserRole) or "")

            parent_name = ""
            if target_item is not None:
                parent_name = str(target_item.data(0, QtCore.Qt.UserRole) or "")

            event.ignore()
            if src_name and src_name != parent_name:
                on_reparent_drop(src_name, parent_name)

    return _MayaDagTreeWidget()


class MayaLeftSidebarWidget:
    """Combined Left Maya Tool Box (`Q/W/E/R/Y`) + Expandable DAG Outliner."""

    def __init__(self, parent: Any = None):
        from qtpy import QtCore, QtWidgets

        self._updating = False
        self.root = QtWidgets.QFrame(parent)
        self.root.setObjectName("MayaPanelRoot")
        style.apply_studio_style(self.root)

        hlay = QtWidgets.QHBoxLayout(self.root)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(0)

        # --- Left Strip: Classic Maya Vertical Tool Box (36px wide) ---
        toolbox = QtWidgets.QFrame()
        toolbox.setObjectName("MayaStatusLine")
        toolbox.setFixedWidth(36)
        tblay = QtWidgets.QVBoxLayout(toolbox)
        tblay.setContentsMargins(3, 4, 3, 4)
        tblay.setSpacing(4)

        self.tool_btns: Dict[str, Any] = {}
        for tool_id, icon_name, tip in (
            ("SELECT", "tool_select", "Select Tool (Q) — Double-click for Tool Settings"),
            ("LASSO", "tool_lasso", "Lasso Select Tool"),
            ("TRANSLATE", "tool_move", "Move Tool (W) — Double-click for Tool Settings"),
            ("ROTATE", "tool_rotate", "Rotate Tool (E) — Double-click for Tool Settings"),
            ("RESIZE", "tool_scale", "Scale Tool (R) — Double-click for Tool Settings"),
        ):
            btn = self._make_toolbox_button(tool_id, icon_name, tip)
            tblay.addWidget(btn)
            self.tool_btns[tool_id] = btn

        tblay.addStretch(1)

        # Quick Layout Preset buttons at bottom of Maya Tool Box
        for lay_icon, lay_tip, lay_cb in (
            ("mask_obj", "Single Perspective View", lambda: self._on_quick_layout("PERSP")),
            ("quad_view", "Frame All (A)", lambda: self._on_quick_layout("FRAME_ALL")),
            ("snap_pivot", "Center Pivot", lambda: self._on_quick_layout("CENTER_PIVOT")),
        ):
            lbtn = QtWidgets.QToolButton()
            lbtn.setObjectName("MayaToolBoxBtn")
            lbtn.setIcon(icons.get_icon(lay_icon, 18))
            lbtn.setIconSize(QtCore.QSize(18, 18))
            lbtn.setFixedSize(28, 26)
            lbtn.setToolTip(lay_tip)
            lbtn.clicked.connect(lay_cb)
            tblay.addWidget(lbtn)

        hlay.addWidget(toolbox)

        # --- Right Pane: Maya DAG Outliner ---
        outliner_pane = QtWidgets.QFrame()
        olay = QtWidgets.QVBoxLayout(outliner_pane)
        olay.setContentsMargins(2, 2, 2, 2)
        olay.setSpacing(2)

        hdr = QtWidgets.QFrame()
        hdr.setObjectName("MayaSectionHeader")
        hrow = QtWidgets.QHBoxLayout(hdr)
        hrow.setContentsMargins(5, 2, 4, 2)
        lbl = QtWidgets.QLabel("OUTLINER (DAG)")
        lbl.setObjectName("MayaSectionTitle")
        self.chk_shapes = QtWidgets.QCheckBox("Shapes")
        self.chk_shapes.setChecked(True)
        self.chk_shapes.setToolTip("Display expandable [+] Shape & Modifier nodes under Transform nodes")
        self.chk_shapes.toggled.connect(lambda _: self.refresh())
        hrow.addWidget(lbl)
        hrow.addStretch(1)
        hrow.addWidget(self.chk_shapes)
        olay.addWidget(hdr)

        # Search filter + Unparent to World button
        srow = QtWidgets.QHBoxLayout()
        srow.setContentsMargins(2, 1, 2, 1)
        srow.setSpacing(2)
        self.txt_search = QtWidgets.QLineEdit()
        self.txt_search.setPlaceholderText("Filter DAG nodes...")
        self.txt_search.textChanged.connect(lambda _: self.refresh())
        self.btn_unparent = QtWidgets.QPushButton("Unparent")
        self.btn_unparent.setToolTip("Unparent selected object to World root (Shift+P) preserving world transform")
        self.btn_unparent.setFixedHeight(20)
        self.btn_unparent.clicked.connect(self._on_unparent_clicked)
        srow.addWidget(self.txt_search, 1)
        srow.addWidget(self.btn_unparent)
        olay.addLayout(srow)

        self.tree = _create_dag_tree_widget(
            on_reparent_drop=self._on_tree_reparent,
            on_selection_changed=self._on_tree_selection_changed,
        )
        olay.addWidget(self.tree, 1)

        hlay.addWidget(outliner_pane, 1)

    def _make_toolbox_button(self, tool_id: str, icon_name: str, tip: str):
        from qtpy import QtCore, QtWidgets

        parent_self = self

        class _ToolBoxBtn(QtWidgets.QToolButton):
            def mouseDoubleClickEvent(self, event):
                from . import desktop

                tool_settings.set_tool_setting("tool_context", tool_id)
                desktop.cycle_right_dock("TOOL_SETTINGS")
                event.accept()

        btn = _ToolBoxBtn()
        btn.setObjectName("MayaToolBoxBtn")
        btn.setCheckable(True)
        btn.setIcon(icons.get_icon(icon_name, 20))
        btn.setIconSize(QtCore.QSize(20, 20))
        btn.setFixedSize(28, 28)
        btn.setToolTip(tip)
        btn.clicked.connect(lambda _=False, t=tool_id: parent_self._activate_tool(t))
        return btn

    def _activate_tool(self, tool_id: str) -> None:
        import bpy

        actual = "SELECT" if tool_id == "LASSO" else tool_id
        try:
            bpy.ops.landfall_studio.select_tool(tool=actual)
        except Exception:
            cmd_registry.set_active_tool(actual)
        self._sync_toolbox_highlight()

    def _sync_toolbox_highlight(self) -> None:
        cur = cmd_registry.get_active_tool()
        for tid, btn in self.tool_btns.items():
            btn.blockSignals(True)
            btn.setChecked(tid == cur)
            btn.blockSignals(False)

    def _on_quick_layout(self, action: str) -> None:
        import bpy

        if action == "FRAME_ALL":
            try:
                bpy.ops.landfall_studio.frame_all()
            except Exception:
                pass
        elif action == "CENTER_PIVOT":
            from . import shelf

            shelf.execute_shelf_item("center_pivot")

    def _on_unparent_clicked(self) -> None:
        import bpy

        active = getattr(bpy.context.view_layer.objects, "active", None)
        if active is not None and active.parent is not None:
            try:
                bpy.ops.landfall_studio.outliner_reparent(
                    child_name=active.name, parent_name=""
                )
            except Exception:
                reparent_preserve_world(active.name, "")
            self.refresh()

    def _on_tree_reparent(self, child_name: str, parent_name: str) -> None:
        import bpy

        try:
            bpy.ops.landfall_studio.outliner_reparent(
                child_name=child_name, parent_name=parent_name
            )
        except Exception:
            reparent_preserve_world(child_name, parent_name)
        self.refresh()

    def _on_tree_selection_changed(self) -> None:
        if self._updating:
            return
        from qtpy import QtCore

        names: List[str] = []
        for item in self.tree.selectedItems():
            obj_name = item.data(0, QtCore.Qt.UserRole)
            if obj_name and str(obj_name) not in names:
                names.append(str(obj_name))
        if names:
            self._updating = True
            try:
                select_in_outliner(names)
            finally:
                self._updating = False

    def _populate_node_item(self, node: Dict[str, Any]):
        from qtpy import QtCore, QtGui, QtWidgets

        kind = node["kind"]
        if kind == "SHAPE":
            label = f"{node['name']}  [{node['shape_type']}]"
            item = QtWidgets.QTreeWidgetItem([label])
            item.setData(0, QtCore.Qt.UserRole, node["owner_object"])
            icon_map = {
                "MESH": "dag_mesh",
                "CAMERA": "dag_camera",
                "LIGHT": "dag_light",
                "ARMATURE": "dag_armature",
                "CURVE": "dag_curve",
            }
            item.setIcon(0, icons.get_icon(icon_map.get(node["shape_type"], "dag_mesh"), 14))
            item.setForeground(0, QtGui.QBrush(QtGui.QColor("#7AB8DC")))
            return item

        if kind == "MODIFIER":
            label = f"{node['name']}  ({node['modifier_type']})"
            item = QtWidgets.QTreeWidgetItem([label])
            item.setData(0, QtCore.Qt.UserRole, node["owner_object"])
            item.setIcon(0, icons.get_icon("dag_modifier", 14))
            item.setForeground(0, QtGui.QBrush(QtGui.QColor("#7ED491")))
            return item

        # TRANSFORM node
        item = QtWidgets.QTreeWidgetItem([node["name"]])
        item.setData(0, QtCore.Qt.UserRole, node["name"])
        item.setIcon(0, icons.get_icon("dag_transform", 15))
        font = item.font(0)
        font.setBold(bool(node.get("selected")))
        item.setFont(0, font)
        if node.get("linked"):
            item.setForeground(0, QtGui.QBrush(QtGui.QColor("#F2B857")))
        elif node.get("selected"):
            item.setForeground(0, QtGui.QBrush(QtGui.QColor("#66E0A3")))
        else:
            item.setForeground(0, QtGui.QBrush(QtGui.QColor("#E4E8EE")))

        for ch in node.get("children", ()):
            ch_item = self._populate_node_item(ch)
            item.addChild(ch_item)

        if node.get("selected") or any(c["kind"] == "TRANSFORM" for c in node.get("children", ())):
            item.setExpanded(True)
        return item

    def refresh(self) -> Dict[str, Any]:
        if self._updating:
            return get_dag_outliner_snapshot(
                filter_text=self.txt_search.text(),
                show_shapes=self.chk_shapes.isChecked(),
            )
        self._updating = True
        try:
            self._sync_toolbox_highlight()
            snap = get_dag_outliner_snapshot(
                filter_text=self.txt_search.text(),
                show_shapes=self.chk_shapes.isChecked(),
            )
            self.tree.blockSignals(True)
            self.tree.clear()
            for rnode in snap.get("roots", ()):
                top_item = self._populate_node_item(rnode)
                self.tree.addTopLevelItem(top_item)
                if rnode.get("selected") or any(
                    c.get("kind") == "TRANSFORM" for c in rnode.get("children", ())
                ):
                    top_item.setExpanded(True)
                if rnode.get("selected"):
                    top_item.setSelected(True)
            self.tree.blockSignals(False)
            return snap
        finally:
            self._updating = False


class LeftOutlinerQtDock:
    """Left-column `WS_CHILD` dock manager embedding `MayaLeftSidebarWidget` (Tool Box + DAG Outliner)."""

    DEFAULT_WIDTH = 240

    def __init__(self):
        from blendertk.ui_utils.qt_dock import QtDock

        self._inner_dock = QtDock(
            editor="Outliner",
            area_header=False,
            focus_on_hover=True,
            on_detach=self._handle_detach,
        )
        self._created_split_area = False
        self._outliner_ctrl: Optional[MayaLeftSidebarWidget] = None

    @property
    def docked(self) -> bool:
        return bool(self._inner_dock.docked)

    @property
    def widget(self):
        return self._outliner_ctrl.root if self._outliner_ctrl is not None else None

    def ensure_outliner_widget(self) -> MayaLeftSidebarWidget:
        if self._outliner_ctrl is None:
            self._outliner_ctrl = MayaLeftSidebarWidget()
        self._outliner_ctrl.refresh()
        return self._outliner_ctrl

    def _handle_detach(self) -> None:
        self._created_split_area = False

    @staticmethod
    def _find_or_create_left_area(window, width: int = DEFAULT_WIDTH):
        import bpy
        from blendertk.ui_utils._ui_utils import _UiUtilsInternal

        # If a left-side OUTLINER area already exists (x < window.width * 0.35), reuse it
        existing_left = [
            a
            for a in window.screen.areas
            if a.ui_type == "OUTLINER" and a.x < (window.width * 0.35)
        ]
        if existing_left:
            return min(existing_left, key=lambda a: a.x), False

        # Close redundant right-side stock Blender OUTLINER so right PROPERTIES spans full height!
        right_outliners = [
            a
            for a in window.screen.areas
            if a.ui_type == "OUTLINER" and a.x >= (window.width * 0.35)
        ]
        for ro in right_outliners:
            try:
                import blendertk as btk

                btk.close_area(window, ro)
            except Exception:
                pass

        view3ds = [a for a in window.screen.areas if a.type == "VIEW_3D"]
        if not view3ds:
            return None, False
        target = max(view3ds, key=lambda a: a.width)
        if target.width <= width + 180:
            return None, False

        # In Blender VERTICAL split, factor is the left fraction
        factor = max(0.14, min(0.42, float(width) / float(target.width)))
        before = {a.as_pointer() for a in window.screen.areas}
        try:
            with bpy.context.temp_override(
                window=window,
                screen=window.screen,
                area=target,
                region=_UiUtilsInternal._window_region(target),
            ):
                res = bpy.ops.screen.area_split(direction="VERTICAL", factor=factor)
        except (RuntimeError, TypeError):
            return None, False
        if res != {"FINISHED"}:
            return None, False

        halves = [a for a in window.screen.areas if a.as_pointer() not in before] + [target]
        left_area = min(halves, key=lambda a: a.x)
        try:
            left_area.ui_type = "OUTLINER"
        except TypeError:
            return None, False
        return left_area, True

    def dock_outliner(self, width: Optional[int] = None) -> bool:
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow

        ctrl = self.ensure_outliner_widget()
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
            area, created = self._find_or_create_left_area(
                window, width=width or self.DEFAULT_WIDTH
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
        if self._outliner_ctrl is not None:
            try:
                self._outliner_ctrl.root.hide()
                self._outliner_ctrl.root.deleteLater()
            except Exception:
                pass
            self._outliner_ctrl = None


_left_outliner_dock: Optional[LeftOutlinerQtDock] = None


def get_left_outliner_dock() -> LeftOutlinerQtDock:
    global _left_outliner_dock
    if _left_outliner_dock is None:
        _left_outliner_dock = LeftOutlinerQtDock()
    return _left_outliner_dock


def refresh_outliner() -> Optional[Dict[str, Any]]:
    if _left_outliner_dock is not None and _left_outliner_dock._outliner_ctrl is not None:
        return _left_outliner_dock._outliner_ctrl.refresh()
    return None


refresh_outliner_widget = refresh_outliner


def teardown_outliner() -> None:
    global _left_outliner_dock
    if _left_outliner_dock is not None:
        _left_outliner_dock.teardown()
        _left_outliner_dock = None
