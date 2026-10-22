"""Maya-Style Unified Tool Settings & Option Box (`□`) Inspector (`landfall_studio.ui.tool_settings`).

Opened automatically when the user:
- Double-clicks any tool in the Maya Tool Box (`Q/W/E/R`) or Tabbed Shelf, or
- Clicks a menu / shelf `□` option box (`landfall_studio.open_tool_settings`), or
- Selects the `Tool Settings` tab in the right-hand dock.

Synchronizes two-way with Blender's `scene.tool_settings` and Studio tool defaults:
- **Axis Orientation**: `World` (`GLOBAL`), `Object / Local` (`LOCAL`), `Normal` (`NORMAL`), `View` (`VIEW`), `Gimbal` (`GIMBAL`)
- **Transform Pivot**: `Median Point`, `Active Element`, `3D Cursor`, `Individual Origins`
- **Soft Selection (`B`)**: `Enable Soft Select` (`use_proportional_edit`), `Falloff Radius` (`proportional_size`), `Falloff Curve`
- **Symmetry**: `Object X`, `Object Y`, `Object Z` (`mesh.use_mirror_x/y/z`)
- **Option Box (`□`) Parameters**: Context-specific options for `polyCube`, `polySphere`, `extrude`, `bevel` (`width`, `segments`, `divisions`, `offset`) + `Apply` and `Reset Tool`.
"""

from __future__ import annotations

import weakref
from typing import Any, Dict, Optional

from .. import commands as cmd_registry
from . import channel_box_ext, style

ORIENTATION_MAYA_TO_BLENDER = {
    "WORLD": "GLOBAL",
    "GLOBAL": "GLOBAL",
    "OBJECT": "LOCAL",
    "LOCAL": "LOCAL",
    "NORMAL": "NORMAL",
    "COMPONENT": "NORMAL",
    "VIEW": "VIEW",
    "GIMBAL": "GIMBAL",
}

ORIENTATION_BLENDER_TO_MAYA = {
    "GLOBAL": "World",
    "LOCAL": "Object",
    "NORMAL": "Component / Normal",
    "VIEW": "View",
    "GIMBAL": "Gimbal",
}

DEFAULT_OPTION_BOX_PARAMS: Dict[str, Any] = {
    "bevel_width": 0.15,
    "bevel_segments": 2,
    "extrude_offset": 0.5,
    "prim_width": 2.0,
    "prim_height": 2.0,
    "prim_depth": 2.0,
    "prim_radius": 1.0,
    "prim_subdivisions_x": 1,
    "prim_subdivisions_y": 1,
    "prim_subdivisions_z": 1,
}

_option_box_state: Dict[str, Any] = dict(DEFAULT_OPTION_BOX_PARAMS)
_active_tool_context: str = "TRANSLATE"
_ts_instances: weakref.WeakSet = weakref.WeakSet()


# Display labels as Maya shows them; Blender's identifiers stay the data.
PIVOT_LABELS = (("Median", "MEDIAN_POINT"), ("Active Element", "ACTIVE_ELEMENT"),
                ("3D Cursor", "CURSOR"), ("Individual Origins", "INDIVIDUAL_ORIGINS"),
                ("Bounding Box Center", "BOUNDING_BOX_CENTER"))
FALLOFF_LABELS = (("Smooth", "SMOOTH"), ("Sphere", "SPHERE"), ("Root", "ROOT"),
                  ("Inverse Square", "INVERSE_SQUARE"), ("Sharp", "SHARP"), ("Linear", "LINEAR"),
                  ("Constant", "CONSTANT"), ("Random", "RANDOM"))
TOOL_TITLES = {"TRANSLATE": "Move Tool", "MOVE": "Move Tool", "ROTATE": "Rotate Tool",
               "RESIZE": "Scale Tool", "SCALE": "Scale Tool", "SELECT": "Select Tool"}


def get_tool_settings_snapshot(context: Any = None) -> Dict[str, Any]:
    """Read back the current Maya Tool Settings state from Blender and Studio."""
    import bpy

    ctx = context or bpy.context
    scene = getattr(ctx, "scene", None)
    ts = getattr(scene, "tool_settings", None) if scene is not None else None

    orient_bl = "GLOBAL"
    if scene is not None and getattr(scene, "transform_orientation_slots", None):
        try:
            orient_bl = str(scene.transform_orientation_slots[0].type)
        except Exception:
            orient_bl = "GLOBAL"

    soft_enabled = bool(getattr(ts, "use_proportional_edit", False)) if ts is not None else False
    soft_radius = round(float(getattr(ts, "proportional_size", 1.0)), 4) if ts is not None else 1.0
    soft_falloff = str(getattr(ts, "proportional_edit_falloff", "SMOOTH")) if ts is not None else "SMOOTH"
    pivot_point = str(getattr(ts, "transform_pivot_point", "MEDIAN_POINT")) if ts is not None else "MEDIAN_POINT"
    snap_enabled = bool(getattr(ts, "use_snap", False)) if ts is not None else False

    active_obj = getattr(ctx.view_layer.objects, "active", None) if getattr(ctx, "view_layer", None) else None
    me = getattr(active_obj, "data", None) if active_obj is not None and active_obj.type == "MESH" else None
    sym_x = bool(getattr(me, "use_mirror_x", False)) if me is not None else False
    sym_y = bool(getattr(me, "use_mirror_y", False)) if me is not None else False
    sym_z = bool(getattr(me, "use_mirror_z", False)) if me is not None else False

    return {
        "ok": True,
        "tool_context": _active_tool_context,
        "active_manipulator": cmd_registry.get_active_tool(),
        "active_axis": cmd_registry.get_active_axis(),
        "axis_orientation_blender": orient_bl,
        "axis_orientation_maya": ORIENTATION_BLENDER_TO_MAYA.get(orient_bl, "World"),
        "pivot_point": pivot_point,
        "soft_select_enabled": soft_enabled,
        "soft_select_radius": soft_radius,
        "soft_select_falloff": soft_falloff,
        "snap_enabled": snap_enabled,
        "symmetry": {"x": sym_x, "y": sym_y, "z": sym_z},
        "option_box": dict(_option_box_state),
    }


def set_tool_setting(key: str, value: Any, context: Any = None) -> Dict[str, Any]:
    """Mutate a Tool Settings parameter (`axis_orientation`, `soft_select_enabled`, `soft_select_radius`, `symmetry_x`, or option-box param)."""
    global _active_tool_context
    import bpy

    ctx = context or bpy.context
    scene = getattr(ctx, "scene", None)
    ts = getattr(scene, "tool_settings", None) if scene is not None else None
    k = (key or "").strip().lower()

    if k == "tool_context":
        _active_tool_context = str(value).upper()
    elif k in ("axis_orientation", "orientation"):
        target_bl = ORIENTATION_MAYA_TO_BLENDER.get(str(value).upper(), "GLOBAL")
        if scene is not None and getattr(scene, "transform_orientation_slots", None):
            scene.transform_orientation_slots[0].type = target_bl
    elif k == "pivot_point" and ts is not None:
        ts.transform_pivot_point = str(value).upper()
    elif k in ("soft_select_enabled", "soft_select") and ts is not None:
        ts.use_proportional_edit = bool(value)
        ts.use_proportional_edit_objects = bool(value)
    elif k in ("soft_select_radius", "falloff_radius") and ts is not None:
        ts.proportional_size = max(0.001, float(value))
    elif k == "soft_select_falloff" and ts is not None:
        ts.proportional_edit_falloff = str(value).upper()
    elif k == "snap_enabled" and ts is not None:
        ts.use_snap = bool(value)
    elif k in ("symmetry_x", "symmetry_y", "symmetry_z"):
        axis = k[-1]
        active_obj = getattr(ctx.view_layer.objects, "active", None)
        if active_obj is not None and active_obj.type == "MESH" and active_obj.data is not None:
            if not channel_box_ext.is_datablock_linked(active_obj.data):
                setattr(active_obj.data, f"use_mirror_{axis}", bool(value))
    elif k in _option_box_state:
        default_val = DEFAULT_OPTION_BOX_PARAMS[k]
        _option_box_state[k] = type(default_val)(value)
    else:
        return {"ok": False, "error": f"Unknown tool setting '{key}'"}

    refresh_tool_settings_widget()
    try:
        from . import outliner, shelf

        shelf.refresh_top_shelf_status()
        outliner.refresh_outliner()
    except Exception:
        pass
    return get_tool_settings_snapshot(ctx)


def reset_tool_settings(tool_context: Optional[str] = None, context: Any = None) -> Dict[str, Any]:
    """Reset the active tool's settings to Maya factory defaults (`Reset Tool` button)."""
    global _active_tool_context
    import bpy

    if tool_context:
        _active_tool_context = str(tool_context).upper()

    ctx = context or bpy.context
    scene = getattr(ctx, "scene", None)
    ts = getattr(scene, "tool_settings", None) if scene is not None else None

    if scene is not None and getattr(scene, "transform_orientation_slots", None):
        try:
            scene.transform_orientation_slots[0].type = "GLOBAL"
        except Exception:
            pass
    if ts is not None:
        ts.use_proportional_edit = False
        ts.use_proportional_edit_objects = False
        ts.proportional_size = 1.0
        ts.proportional_edit_falloff = "SMOOTH"
        ts.transform_pivot_point = "MEDIAN_POINT"
        ts.use_snap = False

    active_obj = getattr(ctx.view_layer.objects, "active", None) if getattr(ctx, "view_layer", None) else None
    if active_obj is not None and active_obj.type == "MESH" and active_obj.data is not None:
        if not channel_box_ext.is_datablock_linked(active_obj.data):
            active_obj.data.use_mirror_x = False
            active_obj.data.use_mirror_y = False
            active_obj.data.use_mirror_z = False

    _option_box_state.clear()
    _option_box_state.update(DEFAULT_OPTION_BOX_PARAMS)
    refresh_tool_settings_widget()
    return get_tool_settings_snapshot(ctx)


def apply_current_tool_option_box() -> Dict[str, Any]:
    """Execute the currently focused tool/command using its Option Box (`□`) parameters."""
    import bpy

    tc = (_active_tool_context or "TRANSLATE").upper()

    def finish(result):
        result.setdefault("executed", tc)
        try:
            from . import desktop

            desktop.set_command_feedback(
                f"tool_settings.apply('{tc}')",
                "OK" if result.get("ok") else result.get("error", "Unable to apply options"),
                level="INFO" if result.get("ok") else "WARNING",
            )
        except Exception:
            pass
        if result.get("ok"):
            channel_box_ext.refresh_channel_box_extensions()
        return result

    if tc in ("CUBE", "SPHERE", "CYLINDER", "PLANE", "POLY_CUBE", "POLY_SPHERE", "POLY_CYLINDER", "POLY_PLANE"):
        ptype = tc.replace("POLY_", "")
        res = channel_box_ext.create_maya_primitive(
            primitive_type=ptype,
            width=_option_box_state["prim_width"],
            height=_option_box_state["prim_height"],
            depth=_option_box_state["prim_depth"],
            radius=_option_box_state["prim_radius"],
            subdivisions_x=_option_box_state["prim_subdivisions_x"],
            subdivisions_y=_option_box_state["prim_subdivisions_y"],
            subdivisions_z=_option_box_state["prim_subdivisions_z"],
        )
        return finish({"ok": bool(res.get("ok")), "executed": f"create_maya_primitive({ptype})", "result": res,
                       **({"error": res.get("error", "Primitive creation failed")} if not res.get("ok") else {})})

    if tc in ("BEVEL", "EXTRUDE"):
        from .. import modeling

        active = getattr(bpy.context.view_layer.objects, "active", None)
        if active is None or active.type != "MESH":
            return finish({"ok": False, "error": f"{tc.title()} requires an active mesh"})
        if channel_box_ext.is_datablock_linked(active) or channel_box_ext.is_datablock_linked(active.data):
            return finish({"ok": False, "error": "Linked mesh data is read-only"})
        params = ({"width": float(_option_box_state["bevel_width"]), "segments": int(_option_box_state["bevel_segments"])}
                  if tc == "BEVEL" else {"thickness": float(_option_box_state["extrude_offset"])})
        try:
            return finish(modeling.invoke_modeling_caddy(tc, target_obj_or_name=active, params_dict=params))
        except (RuntimeError, ValueError, TypeError) as exc:
            return finish({"ok": False, "error": str(exc)})

    return finish({"ok": False, "error": f"No option-box action is available for {tc.title()}"})


class MayaToolSettingsWidget:
    """Qt Tool Settings & Option Box (`□`) inspector panel."""

    def __init__(self, parent: Any = None):
        from qtpy import QtCore, QtWidgets

        self._updating = False
        self.widget = QtWidgets.QFrame(parent)
        self.widget.setObjectName("MayaPanelRoot")
        style.apply_studio_style(self.widget)

        vlay = QtWidgets.QVBoxLayout(self.widget)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(5)

        # Header with Active Tool & Reset Tool button
        hdr = QtWidgets.QFrame()
        hdr.setObjectName("MayaSectionHeader")
        hrow = QtWidgets.QHBoxLayout(hdr)
        hrow.setContentsMargins(6, 3, 6, 3)
        self.lbl_title = QtWidgets.QLabel("TOOL SETTINGS: MOVE")
        self.lbl_title.setObjectName("MayaSectionTitle")
        self.btn_reset = QtWidgets.QPushButton("Reset Tool")
        self.btn_reset.setFixedHeight(20)
        self.btn_reset.clicked.connect(lambda: reset_tool_settings())
        hrow.addWidget(self.lbl_title)
        hrow.addStretch(1)
        hrow.addWidget(self.btn_reset)
        vlay.addWidget(hdr)

        # Section 1: Transform & Manipulator Orientation
        grp_orient = QtWidgets.QFrame()
        flay1 = QtWidgets.QFormLayout(grp_orient)
        flay1.setContentsMargins(4, 4, 4, 4)
        self.cmb_orient = QtWidgets.QComboBox()
        self.cmb_orient.addItems(["World", "Object", "Component / Normal", "View", "Gimbal"])
        self.cmb_orient.currentTextChanged.connect(self._on_orient_changed)
        self.cmb_pivot = QtWidgets.QComboBox()
        for label, value in PIVOT_LABELS:
            self.cmb_pivot.addItem(label, value)
        self.cmb_pivot.currentIndexChanged.connect(
            lambda _i: set_tool_setting("pivot_point", self.cmb_pivot.currentData()) if not self._updating else None
        )
        self.chk_snap = QtWidgets.QCheckBox("Step / Discrete Snap")
        self.chk_snap.toggled.connect(
            lambda b: set_tool_setting("snap_enabled", b) if not self._updating else None
        )
        flay1.addRow("Axis Orientation:", self.cmb_orient)
        flay1.addRow("Pivot Center:", self.cmb_pivot)
        flay1.addRow("Snapping:", self.chk_snap)
        vlay.addWidget(grp_orient)

        # Section 2: Soft Selection (B)
        soft_hdr = QtWidgets.QFrame()
        soft_hdr.setObjectName("MayaSectionHeader")
        srow = QtWidgets.QHBoxLayout(soft_hdr)
        srow.setContentsMargins(6, 2, 6, 2)
        lbl_soft = QtWidgets.QLabel("SOFT SELECTION (B)")
        lbl_soft.setObjectName("MayaSectionTitle")
        srow.addWidget(lbl_soft)
        vlay.addWidget(soft_hdr)

        grp_soft = QtWidgets.QFrame()
        flay2 = QtWidgets.QFormLayout(grp_soft)
        flay2.setContentsMargins(4, 4, 4, 4)
        self.chk_soft = QtWidgets.QCheckBox("Soft Select")
        self.chk_soft.toggled.connect(
            lambda b: set_tool_setting("soft_select_enabled", b) if not self._updating else None
        )
        self.spn_soft_radius = QtWidgets.QDoubleSpinBox()
        self.spn_soft_radius.setRange(0.01, 500.0)
        self.spn_soft_radius.setSingleStep(0.25)
        self.spn_soft_radius.setKeyboardTracking(False)
        self.spn_soft_radius.valueChanged.connect(
            lambda v: set_tool_setting("soft_select_radius", v) if not self._updating else None
        )
        self.cmb_falloff = QtWidgets.QComboBox()
        for label, value in FALLOFF_LABELS:
            self.cmb_falloff.addItem(label, value)
        self.cmb_falloff.currentIndexChanged.connect(
            lambda _i: set_tool_setting("soft_select_falloff", self.cmb_falloff.currentData()) if not self._updating else None
        )
        flay2.addRow("Enable:", self.chk_soft)
        flay2.addRow("Falloff Radius:", self.spn_soft_radius)
        flay2.addRow("Falloff Curve:", self.cmb_falloff)
        vlay.addWidget(grp_soft)

        # Section 3: Mesh Symmetry
        sym_hdr = QtWidgets.QFrame()
        sym_hdr.setObjectName("MayaSectionHeader")
        sym_row = QtWidgets.QHBoxLayout(sym_hdr)
        sym_row.setContentsMargins(6, 2, 6, 2)
        lbl_sym = QtWidgets.QLabel("SYMMETRY SETTINGS")
        lbl_sym.setObjectName("MayaSectionTitle")
        sym_row.addWidget(lbl_sym)
        vlay.addWidget(sym_hdr)

        sym_bar = QtWidgets.QHBoxLayout()
        sym_bar.setContentsMargins(6, 2, 6, 2)
        self.chk_sym_x = QtWidgets.QCheckBox("Object X")
        self.chk_sym_y = QtWidgets.QCheckBox("Object Y")
        self.chk_sym_z = QtWidgets.QCheckBox("Object Z")
        self.chk_sym_x.toggled.connect(lambda b: set_tool_setting("symmetry_x", b) if not self._updating else None)
        self.chk_sym_y.toggled.connect(lambda b: set_tool_setting("symmetry_y", b) if not self._updating else None)
        self.chk_sym_z.toggled.connect(lambda b: set_tool_setting("symmetry_z", b) if not self._updating else None)
        sym_bar.addWidget(self.chk_sym_x)
        sym_bar.addWidget(self.chk_sym_y)
        sym_bar.addWidget(self.chk_sym_z)
        vlay.addLayout(sym_bar)

        # Section 4: Command / Shelf Option Box (□) Parameters
        opt_hdr = QtWidgets.QFrame()
        opt_hdr.setObjectName("MayaSectionHeader")
        orow = QtWidgets.QHBoxLayout(opt_hdr)
        orow.setContentsMargins(6, 2, 6, 2)
        lbl_opt = QtWidgets.QLabel("OPTION BOX DEFAULTS (□)")
        lbl_opt.setObjectName("MayaSectionTitle")
        orow.addWidget(lbl_opt)
        vlay.addWidget(opt_hdr)

        grp_opt = QtWidgets.QFrame()
        flay3 = QtWidgets.QFormLayout(grp_opt)
        flay3.setContentsMargins(4, 4, 4, 4)
        self.spn_bevel_w = QtWidgets.QDoubleSpinBox()
        self.spn_bevel_w.setRange(0.001, 50.0)
        self.spn_bevel_w.setSingleStep(0.05)
        self.spn_bevel_w.setKeyboardTracking(False)
        self.spn_bevel_w.valueChanged.connect(lambda v: set_tool_setting("bevel_width", v) if not self._updating else None)

        self.spn_bevel_seg = QtWidgets.QSpinBox()
        self.spn_bevel_seg.setRange(1, 32)
        self.spn_bevel_seg.setKeyboardTracking(False)
        self.spn_bevel_seg.valueChanged.connect(lambda v: set_tool_setting("bevel_segments", v) if not self._updating else None)

        self.spn_prim_subx = QtWidgets.QSpinBox()
        self.spn_prim_subx.setRange(1, 64)
        self.spn_prim_subx.setKeyboardTracking(False)
        self.spn_prim_subx.valueChanged.connect(lambda v: set_tool_setting("prim_subdivisions_x", v) if not self._updating else None)

        flay3.addRow("Bevel Width:", self.spn_bevel_w)
        flay3.addRow("Bevel Segments:", self.spn_bevel_seg)
        flay3.addRow("Primitive Divisions X:", self.spn_prim_subx)
        vlay.addWidget(grp_opt)

        act_row = QtWidgets.QHBoxLayout()
        self.btn_apply = QtWidgets.QPushButton("Apply")
        self.btn_apply.setToolTip("Run the current command with these option box values")
        self.btn_apply.clicked.connect(lambda: apply_current_tool_option_box())
        act_row.addWidget(self.btn_apply)
        vlay.addLayout(act_row)
        vlay.addStretch(1)
        _ts_instances.add(self)

    def _on_orient_changed(self, txt: str) -> None:
        if self._updating:
            return
        rev = {
            "World": "WORLD",
            "Object": "OBJECT",
            "Component / Normal": "NORMAL",
            "View": "VIEW",
            "Gimbal": "GIMBAL",
        }
        set_tool_setting("axis_orientation", rev.get(txt, "WORLD"))

    def refresh(self) -> Dict[str, Any]:
        from qtpy import QtWidgets

        snap = get_tool_settings_snapshot()

        def sync(control, value, method="setValue"):
            focus = QtWidgets.QApplication.focusWidget()
            if control.hasFocus() or (focus is not None and control.isAncestorOf(focus)):
                return
            if isinstance(control, QtWidgets.QComboBox) and control.view().isVisible():
                return
            if method == "setData":
                index = control.findData(value)
                if index >= 0 and index != control.currentIndex():
                    control.setCurrentIndex(index)
                return
            current = control.currentText() if method == "setCurrentText" else control.value()
            if current == value:
                return
            getattr(control, method)(value)

        self._updating = True
        try:
            self.lbl_title.setText(TOOL_TITLES.get(str(snap['tool_context']).upper(),
                                                   f"{str(snap['tool_context']).replace('_', ' ').title()} Tool"))
            sync(self.cmb_orient, snap["axis_orientation_maya"], "setCurrentText")
            sync(self.cmb_pivot, snap["pivot_point"], "setData")
            self.chk_snap.setChecked(snap["snap_enabled"])
            self.chk_soft.setChecked(snap["soft_select_enabled"])
            sync(self.spn_soft_radius, snap["soft_select_radius"])
            sync(self.cmb_falloff, snap["soft_select_falloff"], "setData")
            self.chk_sym_x.setChecked(snap["symmetry"]["x"])
            self.chk_sym_y.setChecked(snap["symmetry"]["y"])
            self.chk_sym_z.setChecked(snap["symmetry"]["z"])
            sync(self.spn_bevel_w, snap["option_box"]["bevel_width"])
            sync(self.spn_bevel_seg, snap["option_box"]["bevel_segments"])
            sync(self.spn_prim_subx, snap["option_box"]["prim_subdivisions_x"])
        except Exception:
            pass
        finally:
            self._updating = False
        return snap


_ts_instance: Optional[MayaToolSettingsWidget] = None


def ensure_tool_settings_widget(tool_context: Optional[str] = None) -> Optional[MayaToolSettingsWidget]:
    global _ts_instance, _active_tool_context
    if tool_context:
        _active_tool_context = str(tool_context).upper()
    if _ts_instance is not None:
        _ts_instance.refresh()
        return _ts_instance
    try:
        from . import desktop

        desktop.ensure_ui_handler()
        _ts_instance = MayaToolSettingsWidget()
        _ts_instance.refresh()
        return _ts_instance
    except Exception:
        return None


def refresh_tool_settings_widget() -> Optional[Dict[str, Any]]:
    result = None
    for controller in list(_ts_instances):
        try:
            controller.widget.objectName()
            snap = controller.refresh()
            if controller is _ts_instance or result is None:
                result = snap
        except RuntimeError:
            _ts_instances.discard(controller)
    return result


def teardown_tool_settings() -> None:
    global _ts_instance
    for controller in list(_ts_instances):
        try:
            controller.widget.hide()
            controller.widget.deleteLater()
        except Exception:
            pass
    _ts_instances.clear()
    _ts_instance = None
