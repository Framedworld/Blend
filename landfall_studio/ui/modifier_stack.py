"""Maya-style Modifier Stack window (`landfall_studio.ui.modifier_stack`).

Qt panel over the active object's Blender modifier stack:
- Drag a card's `⠿` handle onto another card to reorder (`object.modifier_move_to_index`).
- Category chip, expand arrow (Blender's own `show_expanded`), and E / C / V / R toggles
  (`show_in_editmode`, `show_on_cage`, `show_viewport`, `show_render`).
- Expanded cards edit the same attributes as Channel Box › INPUTS, including Geometry Nodes sockets.
- `Graph ↗` on a Geometry Nodes card makes it the active modifier and opens the Geometry Node Editor window.
- Order switch: Blender order (top → bottom evaluation) or Maya order (newest first, like INPUTS).

`GroupInputsPanel` is the small Qt panel docked inside the Geometry Node Editor window: the
active Geometry Nodes modifier's inputs, the same values as Channel Box › INPUTS.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import channel_box_ext, style
from ..commands import scene_edits


def _history_state(obj):
    def freeze(value):
        if hasattr(value,'session_uid'):return ('ID',value.session_uid)
        if isinstance(value,(str,int,float,bool,type(None))):return value
        try:return tuple(value)
        except TypeError:return repr(value)
    def custom_values(modifier):
        try:return tuple((name,freeze(modifier[name])) for name in modifier.keys())
        except TypeError:return ()
    def node_values(modifier):
        group=getattr(modifier,'node_group',None)
        if modifier.type!='NODES' or group is None:return ()
        return (group.session_uid,tuple((s.identifier,freeze(channel_box_ext._get_gn_socket_value(modifier,s.identifier)))
                    for s in group.interface.items_tree if getattr(s,'item_type','')=='SOCKET'
                    and getattr(s,'in_out','')=='INPUT' and getattr(s,'socket_type','')!='NodeSocketGeometry'))
    return tuple((m.name,m.type,m.show_viewport,m.show_render,m.show_in_editmode,m.show_on_cage,
                  tuple((name,freeze(getattr(m,name))) for name,_,_ in channel_box_ext.MODIFIER_EXPOSED_ATTRS.get(m.type,()) if hasattr(m,name)),
                  custom_values(m),node_values(m)) for m in obj.modifiers)


def _edit(label,callback,obj=None):
    owner=obj or _active_object()
    return scene_edits.commit(label,callback,lambda:_history_state(owner)) if owner else callback()

CATEGORY_COLORS: Dict[str, str] = {
    "GENERATE": "#5AC8DB",
    "DEFORM": "#E1A75C",
    "EDIT": "#8D949D",
    "NORMALS": "#B48EDB",
    "PHYSICS": "#E35D6A",
    "NODES": "#3FB950",
}

ADD_MENU: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Generate", ("ARRAY", "BEVEL", "BOOLEAN", "BUILD", "DECIMATE", "EDGE_SPLIT", "MASK", "MIRROR", "MULTIRES", "REMESH", "SCREW", "SKIN", "SOLIDIFY", "SUBSURF", "TRIANGULATE", "WELD", "WIREFRAME")),
    ("Deform", ("ARMATURE", "CAST", "CURVE", "DISPLACE", "HOOK", "LAPLACIANDEFORM", "LATTICE", "MESH_DEFORM", "SHRINKWRAP", "SIMPLE_DEFORM", "SMOOTH", "CORRECTIVE_SMOOTH", "LAPLACIANSMOOTH", "SURFACE_DEFORM", "WARP", "WAVE")),
    ("Edit", ("DATA_TRANSFER", "MESH_CACHE", "UV_PROJECT", "UV_WARP", "VERTEX_WEIGHT_EDIT", "VERTEX_WEIGHT_MIX", "VERTEX_WEIGHT_PROXIMITY")),
    ("Normals", ("NORMAL_EDIT", "WEIGHTED_NORMAL")),
    ("Physics", ("CLOTH", "COLLISION", "DYNAMIC_PAINT", "EXPLODE", "OCEAN", "SOFT_BODY")),
    ("Geometry Nodes", ("NODES",)),
)

_TYPE_TO_CATEGORY: Dict[str, str] = {}
for _cat, _types in ADD_MENU:
    for _t in _types:
        _TYPE_TO_CATEGORY[_t] = "NODES" if _cat == "Geometry Nodes" else _cat.upper()

_stack_instances: List["ModifierStackPanel"] = []
_group_input_instances: List["GroupInputsPanel"] = []
_order_mode: str = "BLENDER"


def modifier_category(mod_type: str) -> str:
    return _TYPE_TO_CATEGORY.get(mod_type, "EDIT")


def _pretty(mod_type: str) -> str:
    return mod_type.replace("_", " ").title().replace("Uv", "UV").replace("Subsurf", "Subdivision Surface")


def _active_object():
    import bpy

    vl = getattr(bpy.context, "view_layer", None)
    return vl.objects.active if vl is not None else None


def _summary(mod) -> str:
    t = mod.type
    try:
        if t == "SUBSURF":
            return f"Levels {mod.levels} / Render {mod.render_levels}"
        if t == "BEVEL":
            return f"Width {mod.width:.3f} · {mod.segments} segment{'s' if mod.segments != 1 else ''}"
        if t == "MIRROR":
            axes = "".join(a for a, on in zip("XYZ", mod.use_axis) if on) or "–"
            return f"{axes} · {'bisect · ' if any(mod.use_bisect_axis) else ''}{'clip' if mod.use_clip else 'no clip'}"
        if t == "ARMATURE":
            return f"{mod.object.name if mod.object else 'no armature'}{' · preserve volume' if mod.use_deform_preserve_volume else ''}"
        if t == "NODES":
            ng = mod.node_group
            n_in = 0
            if ng is not None:
                n_in = sum(1 for it in ng.interface.items_tree if getattr(it, "item_type", "") == "SOCKET" and getattr(it, "in_out", "") == "INPUT" and getattr(it, "socket_type", "") != "NodeSocketGeometry")
            return f"Geometry Nodes · {ng.name if ng else 'no group'} · {n_in} input{'s' if n_in != 1 else ''}"
        if t == "SOLIDIFY":
            return f"Thickness {mod.thickness:.3f}"
        if t == "ARRAY":
            return f"Count {mod.count}"
        if t == "DECIMATE":
            return f"Ratio {mod.ratio:.2f}"
    except Exception:
        pass
    return _pretty(t)


def _input_attrs_by_modifier(obj) -> Dict[str, List[Dict[str, Any]]]:
    """Map modifier name -> editable attrs, reusing the Channel Box INPUTS reader."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    try:
        for node in channel_box_ext.get_object_inputs(obj):
            if node.get("kind") in ("modifier", "geometry_nodes"):
                out[node["node_name"]] = list(node.get("attributes", []))
    except Exception:
        pass
    return out


def _with_object(obj, fn):
    """Run `fn()` with `obj` active in OBJECT mode and a 3D View context override."""
    import bpy
    import blendertk as btk

    win = btk.main_window() or bpy.context.window_manager.windows[0]
    area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
    ov: Dict[str, Any] = {"window": win, "screen": win.screen, "object": obj, "active_object": obj}
    if area is not None:
        ov["area"] = area
        ov["region"] = next((r for r in area.regions if r.type == "WINDOW"), None)
    prev_mode = getattr(obj, "mode", "OBJECT")
    with bpy.context.temp_override(**ov):
        if prev_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            return fn()
        finally:
            if prev_mode != "OBJECT" and obj.name in bpy.data.objects:
                try:
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass


# --------------------------------------------------------------------------------------
# Data-level actions (also used headless by tests)
# --------------------------------------------------------------------------------------
def get_modifier_stack_snapshot(obj: Any = None) -> Dict[str, Any]:
    obj = obj or _active_object()
    if obj is None or not hasattr(obj, "modifiers"):
        return {"ok": False, "object": None, "modifiers": []}
    attrs = _input_attrs_by_modifier(obj)
    mods = []
    for i, m in enumerate(obj.modifiers):
        mods.append(
            {
                "index": i,
                "name": m.name,
                "type": m.type,
                "category": modifier_category(m.type),
                "summary": _summary(m),
                "active": bool(getattr(m, "is_active", False)),
                "expanded": bool(getattr(m, "show_expanded", False)),
                "toggles": {
                    "E": bool(getattr(m, "show_in_editmode", False)),
                    "C": bool(getattr(m, "show_on_cage", False)),
                    "V": bool(getattr(m, "show_viewport", True)),
                    "R": bool(getattr(m, "show_render", True)),
                },
                "attrs": attrs.get(m.name, []),
            }
        )
    return {"ok": True, "object": obj.name, "order": _order_mode, "modifiers": mods}


def add_modifier(mod_type: str, obj: Any = None) -> Dict[str, Any]:
    obj = obj or _active_object()
    if obj is None:
        return {"ok": False, "error": "No active object"}
    try:
        name = _pretty(mod_type) if mod_type != "NODES" else "GeometryNodes"
        mod = obj.modifiers.new(name=name, type=mod_type)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if mod_type == "NODES":
        from .. import continuity

        continuity.ensure_geometry_nodes_on_active()
    obj.modifiers.active = mod
    refresh_modifier_stack_widgets()
    return {"ok": True, "modifier": mod.name, "type": mod_type}


def move_modifier(name: str, index: int, obj: Any = None) -> Dict[str, Any]:
    import bpy

    obj = obj or _active_object()
    if obj is None or obj.modifiers.get(name) is None:
        return {"ok": False, "error": f"Modifier '{name}' not found"}
    index = max(0, min(len(obj.modifiers) - 1, int(index)))
    try:
        _with_object(obj, lambda: bpy.ops.object.modifier_move_to_index(modifier=name, index=index))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    refresh_modifier_stack_widgets()
    return {"ok": True, "order": [m.name for m in obj.modifiers]}


def set_modifier_toggle(name: str, flag: str, value: bool, obj: Any = None) -> Dict[str, Any]:
    obj = obj or _active_object()
    mod = obj.modifiers.get(name) if obj is not None else None
    attr = {"E": "show_in_editmode", "C": "show_on_cage", "V": "show_viewport", "R": "show_render"}.get(flag.upper())
    if mod is None or attr is None or not hasattr(mod, attr):
        return {"ok": False, "error": f"Cannot set {flag} on '{name}'"}
    setattr(mod, attr, bool(value))
    refresh_modifier_stack_widgets()
    return {"ok": True, "modifier": name, attr: bool(getattr(mod, attr))}


def set_active_modifier(name: str, obj: Any = None) -> Dict[str, Any]:
    obj = obj or _active_object()
    mod = obj.modifiers.get(name) if obj is not None else None
    if mod is None:
        return {"ok": False, "error": f"Modifier '{name}' not found"}
    obj.modifiers.active = mod
    refresh_group_inputs_widgets()
    return {"ok": True, "active": mod.name}


def apply_modifier(name: str, obj: Any = None) -> Dict[str, Any]:
    import bpy

    obj = obj or _active_object()
    if obj is None or obj.modifiers.get(name) is None:
        return {"ok": False, "error": f"Modifier '{name}' not found"}
    try:
        _with_object(obj, lambda: bpy.ops.object.modifier_apply(modifier=name))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    refresh_modifier_stack_widgets()
    return {"ok": True, "applied": name}


def duplicate_modifier(name: str, obj: Any = None) -> Dict[str, Any]:
    import bpy

    obj = obj or _active_object()
    if obj is None or obj.modifiers.get(name) is None:
        return {"ok": False, "error": f"Modifier '{name}' not found"}
    try:
        _with_object(obj, lambda: bpy.ops.object.modifier_copy(modifier=name))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    refresh_modifier_stack_widgets()
    return {"ok": True, "order": [m.name for m in obj.modifiers]}


def remove_modifier(name: str, obj: Any = None) -> Dict[str, Any]:
    obj = obj or _active_object()
    mod = obj.modifiers.get(name) if obj is not None else None
    if mod is None:
        return {"ok": False, "error": f"Modifier '{name}' not found"}
    obj.modifiers.remove(mod)
    refresh_modifier_stack_widgets()
    return {"ok": True, "removed": name}


def open_graph_for_modifier(name: str, obj: Any = None) -> Dict[str, Any]:
    res = set_active_modifier(name, obj)
    if not res.get("ok"):
        return res
    from . import hybrid_window

    return hybrid_window.open_editor_window("GEOMETRY_NODE_EDITOR")


def set_order_mode(mode: str) -> str:
    global _order_mode
    _order_mode = "MAYA" if (mode or "").upper() == "MAYA" else "BLENDER"
    refresh_modifier_stack_widgets()
    return _order_mode


# --------------------------------------------------------------------------------------
# Qt widgets
# --------------------------------------------------------------------------------------
def _field(parent_lay, label: str, value: Any, on_commit, indent: int = 46, editable=True, tip=''):
    from qtpy import QtCore, QtWidgets

    row = QtWidgets.QFrame()
    row.setFixedHeight(26)
    lay = QtWidgets.QHBoxLayout(row)
    lay.setContentsMargins(indent, 0, 10, 0)
    lay.setSpacing(8)
    lbl = style.elided_label(label)
    lbl.setStyleSheet("background: transparent; color: #C9CDD3; font-size: 11px;")
    edit = QtWidgets.QLineEdit(str(value))
    edit.setFixedWidth(96)
    edit.setFixedHeight(22)
    edit.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    edit.setStyleSheet("font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 11px;")
    edit.setReadOnly(not editable)
    if editable:
        edit.editingFinished.connect(lambda: on_commit(edit.text()))
    if tip:
        lbl.setToolTip(label+'\n'+tip);edit.setToolTip(tip)
    lay.addWidget(lbl, 1)
    lay.addWidget(edit)
    parent_lay.addWidget(row)
    return edit


class ModifierStackPanel:
    """Qt Modifier Stack panel for the active object (docked tab, tear-off, or window)."""

    def __init__(self, parent: Any = None):
        from qtpy import QtCore, QtWidgets

        self.root = QtWidgets.QFrame(parent)
        self.root.setObjectName("MayaPanelRoot")
        style.apply_studio_style(self.root)
        self.root.setMinimumWidth(260)
        vlay = QtWidgets.QVBoxLayout(self.root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        menubar = QtWidgets.QMenuBar()
        menubar.setObjectName("MayaPanelMenuBar")
        m_edit = menubar.addMenu("Edit")
        m_edit.addAction("Apply Active", lambda _=False: self._act("apply"))
        m_edit.addAction("Duplicate Active", lambda _=False: self._act("duplicate"))
        m_edit.addAction("Delete Active", lambda _=False: self._act("delete"))
        self.menu_add = menubar.addMenu("Add")
        self._fill_add_menu(self.menu_add)
        m_order = menubar.addMenu("Order")
        m_order.addAction("Blender order (top → bottom)", lambda _=False: set_order_mode("BLENDER"))
        m_order.addAction("Maya order (newest first)", lambda _=False: set_order_mode("MAYA"))
        m_show = menubar.addMenu("Show")
        m_show.addAction("Expand All", lambda _=False: self._expand_all(True))
        m_show.addAction("Collapse All", lambda _=False: self._expand_all(False))
        vlay.addWidget(menubar)

        bar = QtWidgets.QFrame()
        bar.setFixedHeight(40)
        blay = QtWidgets.QHBoxLayout(bar)
        blay.setContentsMargins(10, 6, 10, 6)
        blay.setSpacing(6)
        self.btn_add = QtWidgets.QPushButton("+ Add Modifier ▾")
        self.btn_add.setObjectName("MayaAccentButton")
        add_menu = QtWidgets.QMenu(self.btn_add)
        style.apply_studio_style(add_menu)
        self._fill_add_menu(add_menu)
        self.btn_add.setMenu(add_menu)
        blay.addWidget(self.btn_add)
        blay.addStretch(1)
        lbl_order = QtWidgets.QLabel("Order")
        lbl_order.setObjectName("MayaMutedLabel")
        blay.addWidget(lbl_order)
        self.btn_blender = QtWidgets.QPushButton("Blender order")
        self.btn_maya = QtWidgets.QPushButton("Maya order")
        for b, mode in ((self.btn_blender, "BLENDER"), (self.btn_maya, "MAYA")):
            b.setCheckable(True)
            b.setFixedHeight(24)
            b.setText('Blender ↓' if mode=='BLENDER' else 'Maya ↑')
            b.setToolTip('Evaluation order, top to bottom' if mode=='BLENDER' else 'Newest modifier first; evaluation order is unchanged')
            b.clicked.connect(lambda _=False, m=mode: set_order_mode(m))
            blay.addWidget(b)
        vlay.addWidget(bar)

        self.lbl_object = style.elided_label("No object selected")
        self.lbl_object.setStyleSheet("background: #2A2E35; color: #E4E7E9; font-size: 11px; font-weight: 600; padding: 6px 12px; border-top: 1px solid #101214; border-bottom: 1px solid #101214;")
        vlay.addWidget(self.lbl_object)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.cards_host = QtWidgets.QWidget()
        self.cards_lay = QtWidgets.QVBoxLayout(self.cards_host)
        self.cards_lay.setContentsMargins(0, 0, 0, 0)
        self.cards_lay.setSpacing(0)
        self.cards_lay.addStretch(1)
        self.scroll.setWidget(self.cards_host)
        vlay.addWidget(self.scroll, 1)

        foot = QtWidgets.QFrame()
        foot.setFixedHeight(70)
        foot.setStyleSheet("background: #2A2E35; border-top: 1px solid #101214;")
        flay = QtWidgets.QGridLayout(foot)
        flay.setContentsMargins(10, 8, 10, 8)
        flay.setSpacing(6)
        self.action_buttons={}
        for index,(label, key) in enumerate((("Apply", "apply"), ("Apply Non-Deformers", "non_def"), ("Duplicate", "duplicate"), ("Delete", "delete"))):
            b = QtWidgets.QPushButton(label)
            b.setFixedHeight(26)
            b.clicked.connect(lambda _=False, k=key: self._act(k))
            flay.addWidget(b,index//2,index%2)
            self.action_buttons[key]=b
        vlay.addWidget(foot)

        self._cards: List[Any] = []
        _stack_instances.append(self)
        self.refresh()

    # -- menus & actions ---------------------------------------------------------------
    def _fill_add_menu(self, menu) -> None:
        for cat, types in ADD_MENU:
            sub = menu.addMenu(cat)
            for t in types:
                sub.addAction("Geometry Nodes" if t == "NODES" else _pretty(t), lambda _=False, tt=t: self._add_modifier(tt))

    def _add_modifier(self,kind):
        from .menus import _safe_call
        return _safe_call(lambda:_edit('Add Modifier',lambda:add_modifier(kind)),'Add Modifier')

    def _active_name(self) -> Optional[str]:
        obj = _active_object()
        if obj is None or not getattr(obj, "modifiers", None):
            return None
        act = obj.modifiers.active
        return act.name if act is not None else obj.modifiers[-1].name

    def _act(self, key: str) -> None:
        name = self._active_name()
        res: Dict[str, Any] = {}
        if key == "non_def":
            from .. import modeling

            res = _edit('Apply Non-Deformers',modeling.delete_non_deformer_history)
        elif name is None:
            return
        elif key == "apply":
            res = _edit('Apply Modifier',lambda:apply_modifier(name))
        elif key == "duplicate":
            res = _edit('Duplicate Modifier',lambda:duplicate_modifier(name))
        elif key == "delete":
            res = _edit('Delete Modifier',lambda:remove_modifier(name))
        try:
            from . import desktop

            desktop.set_command_feedback(f"modifier_stack.{key}('{name or ''}')", "OK" if res.get("ok") else res.get("error") or res.get("reason", "Blocked"), level="INFO" if res.get("ok") else "WARNING")
        except Exception:
            pass
        refresh_modifier_stack_widgets()

    def _expand_all(self, expanded: bool) -> None:
        obj = _active_object()
        for m in getattr(obj, "modifiers", ()):
            m.show_expanded = expanded
        self.refresh()

    # -- build -------------------------------------------------------------------------
    def refresh(self) -> Dict[str, Any]:
        if getattr(self,'_refreshing',False):return get_modifier_stack_snapshot()
        self._refreshing=True
        try:return self._refresh_impl()
        finally:self._refreshing=False

    def _refresh_impl(self) -> Dict[str, Any]:
        from qtpy import QtWidgets

        snap = get_modifier_stack_snapshot()
        focus=QtWidgets.QApplication.focusWidget()
        if not getattr(self,'_force_refresh',False) and snap.get('object')==getattr(self,'_displayed_object',None) and focus is not None and self.cards_host.isAncestorOf(focus) and isinstance(focus,QtWidgets.QLineEdit):
            return snap
        self._force_refresh=False
        self._displayed_object=snap.get('object')
        self.btn_add.setEnabled(bool(snap.get('object')) and not snap.get('linked',False))
        for key,button in self.action_buttons.items():
            button.setEnabled(bool(snap.get('object')) and bool(snap.get('modifiers')))
            button.setToolTip('Select a modifier card first.' if not snap.get('modifiers') else 'Acts on the active modifier card.')
        self.btn_blender.setChecked(_order_mode == "BLENDER")
        self.btn_maya.setChecked(_order_mode == "MAYA")
        count = len(snap.get('modifiers', ()))
        self.lbl_object.setText(f"{snap['object']}  ·  {count} modifier{'s' if count != 1 else ''}" if snap.get("object") else "No object selected")
        for c in self._cards:
            for editor in c.findChildren(QtWidgets.QLineEdit):editor.blockSignals(True)
            c.setParent(None)
            c.deleteLater()
        self._cards = []
        mods = list(snap.get("modifiers", []))
        if _order_mode == "MAYA":
            mods.reverse()
        for info in mods:
            card = self._build_card(info, snap["object"])
            self.cards_lay.insertWidget(self.cards_lay.count() - 1, card)
            card.show()
            self._cards.append(card)
        if not mods and snap.get("object"):
            empty = QtWidgets.QLabel("No modifiers yet. Use + Add Modifier to start a stack.")
            empty.setObjectName("MayaMutedLabel")
            empty.setWordWrap(True)
            empty.setContentsMargins(12, 12, 12, 12)
            self.cards_lay.insertWidget(0, empty)
            self._cards.append(empty)
        return snap

    def _build_card(self, info: Dict[str, Any], obj_name: str):
        from qtpy import QtCore, QtGui, QtWidgets

        panel = self

        class _Card(QtWidgets.QFrame):
            def __init__(self):
                super().__init__()
                self.setAcceptDrops(True)
                self.mod_name = info["name"]

            def mousePressEvent(self, event):
                set_active_modifier(self.mod_name)
                refresh_modifier_stack_widgets()
                super().mousePressEvent(event)

            def dragEnterEvent(self, event):
                if event.mimeData().hasText() and event.mimeData().text().startswith("lf-mod:"):
                    event.acceptProposedAction()

            def dropEvent(self, event):
                src = event.mimeData().text().split(":", 1)[1]
                if src != self.mod_name:
                    _edit('Reorder Modifier',lambda:move_modifier(src,info['index']))
                event.acceptProposedAction()

        class _Handle(QtWidgets.QLabel):
            def mousePressEvent(self, event):
                if event.button() == QtCore.Qt.LeftButton:
                    drag = QtGui.QDrag(self)
                    mime = QtCore.QMimeData()
                    mime.setText(f"lf-mod:{info['name']}")
                    drag.setMimeData(mime)
                    drag.exec(QtCore.Qt.MoveAction)

        card = _Card()
        card.setObjectName("MayaModCard")
        bg = "#292D33" if info["active"] else ("#25282D" if info["expanded"] else "#22252A")
        card.setStyleSheet(f"QFrame#MayaModCard {{ background: {bg}; border-bottom: 1px solid #101214; }}")
        clay = QtWidgets.QVBoxLayout(card)
        clay.setContentsMargins(0, 0, 0, 6 if info["expanded"] else 0)
        clay.setSpacing(0)

        head = QtWidgets.QFrame()
        head.setFixedHeight(42)
        head.setStyleSheet("background: transparent;")
        hl = QtWidgets.QHBoxLayout(head)
        hl.setContentsMargins(8, 0, 10, 0)
        hl.setSpacing(8)
        handle = _Handle("⠿")
        handle.setCursor(QtCore.Qt.OpenHandCursor)
        handle.setToolTip("Drag onto another modifier to reorder")
        handle.setStyleSheet("background: transparent; color: #68717C; font-size: 14px;")
        hl.addWidget(handle)
        chip = QtWidgets.QFrame()
        chip.setFixedSize(4, 24)
        chip.setStyleSheet(f"background: {CATEGORY_COLORS.get(info['category'], '#8D949D')}; border-radius: 2px;")
        hl.addWidget(chip)
        arrow = QtWidgets.QToolButton()
        arrow.setText("▾" if info["expanded"] else "▸")
        arrow.setAutoRaise(True)
        arrow.setFixedSize(18, 18)
        arrow.setStyleSheet("background: transparent; border: none; color: #8D949D; font-size: 11px;")
        arrow.clicked.connect(lambda: self._toggle_expand(info["name"]))
        hl.addWidget(arrow)
        names = QtWidgets.QVBoxLayout()
        names.setSpacing(0)
        lbl_n = style.elided_label(info["name"])
        lbl_n.setStyleSheet("background: transparent; color: #E4E7E9; font-size: 11px; font-weight: 600;")
        lbl_s = style.elided_label(info["summary"])
        lbl_s.setStyleSheet("background: transparent; color: #8D949D; font-size: 10px;")
        names.addWidget(lbl_n)
        names.addWidget(lbl_s)
        hl.addLayout(names, 1)
        if info["type"] == "NODES":
            gbtn = QtWidgets.QPushButton("Graph ↗")
            gbtn.setObjectName("MayaAccentButton")
            gbtn.setFixedHeight(22)
            gbtn.setToolTip("Open this modifier's node graph in the Geometry Node Editor window")
            gbtn.clicked.connect(lambda: open_graph_for_modifier(info["name"]))
            hl.addWidget(gbtn)
        tips = {"E": "Show in Edit Mode", "C": "Adjust edit cage to modifier result", "V": "Show in Viewport", "R": "Use in Render"}
        for flag in ("E", "C", "V", "R"):
            t = QtWidgets.QToolButton()
            t.setText(flag)
            t.setCheckable(True)
            t.setChecked(info["toggles"][flag])
            t.setFixedSize(22, 22)
            t.setToolTip(tips[flag])
            t.setObjectName("MayaModToggle")
            t.toggled.connect(lambda on, f=flag:_edit('Modifier '+f,lambda:set_modifier_toggle(info['name'],f,on)))
            hl.addWidget(t)
        clay.addWidget(head)

        if info["expanded"]:
            for a in info["attrs"]:
                _field(clay, a.get("label", a["name"]), a.get("value", ""), lambda txt, an=a["name"]: self._commit(info["name"], an, txt, obj_name),
                       editable=a.get('editable',True),tip=a.get('tip',''))
            if not info["attrs"]:
                hint = QtWidgets.QLabel("Edit the remaining settings in Attribute Editor › Inputs / Modifiers.")
                hint.setObjectName("MayaMutedLabel")
                hint.setContentsMargins(46, 2, 10, 4)
                hint.setWordWrap(True)
                clay.addWidget(hint)
        return card

    def _toggle_expand(self, name: str) -> None:
        obj = _active_object()
        mod = obj.modifiers.get(name) if obj is not None else None
        if mod is not None:
            set_active_modifier(name)
            mod.show_expanded = not mod.show_expanded
        refresh_modifier_stack_widgets()

    def _commit(self, mod_name: str, attr_name: str, text: str, owner_name=None) -> None:
        obj = _active_object()
        if obj is None or (owner_name is not None and obj.name!=owner_name):
            return
        set_active_modifier(mod_name)
        if obj is None:
            return
        from .menus import _safe_call
        result=_safe_call(lambda:_edit('Modifier '+attr_name,lambda:channel_box_ext.set_object_input_attribute(obj,mod_name,attr_name,text),obj),'Modifier '+attr_name)
        self._force_refresh=not bool(result and result.get('ok'))
        try:
            channel_box_ext.refresh_channel_box_extensions()
        except Exception:
            pass
        refresh_modifier_stack_widgets()
        return result


class GroupInputsPanel:
    """Qt side panel for the Geometry Node Editor window: the active Geometry Nodes modifier's inputs."""

    def __init__(self, parent: Any = None):
        from qtpy import QtWidgets

        self.root = QtWidgets.QFrame(parent)
        self.root.setObjectName("MayaPanelRoot")
        style.apply_studio_style(self.root)
        self.vlay = QtWidgets.QVBoxLayout(self.root)
        self.vlay.setContentsMargins(0, 0, 0, 0)
        self.vlay.setSpacing(0)
        hdr = QtWidgets.QFrame()
        hdr.setObjectName("MayaSectionHeader")
        hdr.setFixedHeight(28)
        hl = QtWidgets.QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 8, 0)
        t = QtWidgets.QLabel("GROUP INPUTS")
        t.setObjectName("MayaSectionTitle")
        hl.addWidget(t)
        hl.addStretch(1)
        self.vlay.addWidget(hdr)
        self.lbl_target = style.elided_label("")
        self.lbl_target.setObjectName("MayaMutedLabel")
        self.lbl_target.setContentsMargins(12, 6, 12, 6)
        self.vlay.addWidget(self.lbl_target)
        self.body = QtWidgets.QWidget()
        self.body_lay = QtWidgets.QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(0)
        self.vlay.addWidget(self.body)
        note = QtWidgets.QLabel("Same values as Channel Box › INPUTS.")
        note.setObjectName("MayaMutedLabel")
        note.setContentsMargins(12, 8, 12, 8)
        self.vlay.addWidget(note)
        self.vlay.addStretch(1)
        _group_input_instances.append(self)
        self.refresh()

    def refresh(self) -> None:
        from qtpy import QtWidgets
        obj = _active_object()
        mod = obj.modifiers.active if obj is not None and getattr(obj, "modifiers", None) else None
        target=(obj.name,mod.name) if mod is not None else None
        focus=QtWidgets.QApplication.focusWidget()
        if not getattr(self,'_force_refresh',False) and target==getattr(self,'_target',None) and focus is not None and self.body.isAncestorOf(focus) and isinstance(focus,QtWidgets.QLineEdit):return
        self._force_refresh=False
        self._target=target
        while self.body_lay.count():
            item = self.body_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                for editor in w.findChildren(QtWidgets.QLineEdit):editor.blockSignals(True)
                w.deleteLater()
        if mod is None or mod.type != "NODES":
            self.lbl_target.setText("Select a Geometry Nodes modifier in the Modifier Stack or Channel Box.")
            return
        self.lbl_target.setText(f"{obj.name} › {mod.name}")
        for a in _input_attrs_by_modifier(obj).get(mod.name, []):
            _field(self.body_lay, a.get("label", a["name"]), a.get("value", ""), lambda txt, an=a["name"], mn=mod.name, owner=obj:self._commit(owner,mn,an,txt),
                   indent=12,editable=a.get('editable',True),tip=a.get('tip',''))

    def _commit(self,owner,modifier,attribute,text):
        if _active_object()!=owner:return
        from .menus import _safe_call
        from qtpy import QtCore
        result=_safe_call(lambda:_edit('Node input '+attribute,lambda:channel_box_ext.set_object_input_attribute(owner,modifier,attribute,text),owner),'Node input '+attribute)
        self._force_refresh=not bool(result and result.get('ok'))
        QtCore.QTimer.singleShot(0,refresh_group_inputs_widgets)
        return result


def create_modifier_stack_widget() -> ModifierStackPanel:
    return ModifierStackPanel()


def create_group_inputs_widget() -> GroupInputsPanel:
    return GroupInputsPanel()


def _alive(w) -> bool:
    try:
        w.root.objectName()
        return True
    except Exception:
        return False


_refresh_pending: bool = False


def refresh_modifier_stack_widgets() -> None:
    """Rebuild the stack panels on the next event-loop tick.

    Deferred because most callers are signal handlers of widgets the rebuild deletes.
    """
    global _refresh_pending
    try:
        from qtpy import QtCore, QtWidgets

        if QtWidgets.QApplication.instance() is not None:
            if not _refresh_pending:
                _refresh_pending = True
                QtCore.QTimer.singleShot(0, _refresh_now)
            return
    except Exception:
        pass
    _refresh_now()


def _refresh_now() -> None:
    global _refresh_pending
    _refresh_pending = False
    for w in list(_stack_instances):
        if not _alive(w):
            _stack_instances.remove(w)
            continue
        try:
            w.refresh()
        except Exception:
            pass
    refresh_group_inputs_widgets()


def refresh_group_inputs_widgets() -> None:
    for w in list(_group_input_instances):
        if not _alive(w):
            _group_input_instances.remove(w)
            continue
        try:
            w.refresh()
        except Exception:
            pass


def teardown_modifier_stack_widgets() -> None:
    for w in list(_stack_instances) + list(_group_input_instances):
        try:
            w.root.hide()
            w.root.deleteLater()
        except Exception:
            pass
    _stack_instances.clear()
    _group_input_instances.clear()


def _register_window_panels() -> None:
    from . import hybrid_window

    hybrid_window.register_qt_panel_factory("group_inputs", create_group_inputs_widget)


_register_window_panels()
