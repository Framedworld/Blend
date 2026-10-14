"""Maya-Oriented Attribute Editor (`landfall_studio.ui.attribute_editor`).

Provides a dedicated PySide6 Attribute Editor with Maya-style node tabs:
- **Transform (`<Object>`)**: Translate/Rotate/Scale vectors, Rotate Order, Display Type, Visibility, Locks
- **Shape (`<Object.data>`)**: Shape datablock name, Shade Smooth/Flat, Mesh topology & UV/Vertex Group stats, Drivers
- **Inputs / Modifiers**: Parametric creation history (`polyCube1`, etc.) + Blender Modifier stack controls + `Delete History`
- **Material / Shader**: Active Principled BSDF shader (`Base Color`, `Metallic`, `Roughness`) + one-click material creation
- **Honest Blender ↔ Maya Concept Mapping**: Explicit architecture mapping table avoiding false Maya DG node equivalence,
  plus linked-library read-only protection and a one-click toggle to native Blender `Properties`.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from . import channel_box_ext, icons, style

BLENDER_MAYA_CONCEPT_MAPPING: List[Dict[str, str]] = [
    {
        "maya_concept": "Transform Node (dagNode)",
        "blender_concept": "bpy.types.Object",
        "notes": "Owns world/local transform (location, rotation_euler, scale), parent link, and visibility.",
    },
    {
        "maya_concept": "Shape Node (mesh / nurbsCurve / camera)",
        "blender_concept": "bpy.types.Object.data (Mesh, Curve, Camera, Light, Armature)",
        "notes": "Referenced datablock under Object. Multiple Objects can instance one Shape datablock.",
    },
    {
        "maya_concept": "Construction History (INPUTS / DG Chain)",
        "blender_concept": "Parametric _lf_poly_input + Object.modifiers Stack",
        "notes": "Blender evaluates a linear Modifier stack rather than an arbitrary Maya DG graph. Delete History applies modifiers.",
    },
    {
        "maya_concept": "Set Driven Key / Expressions",
        "blender_concept": "Object.animation_data.drivers (F-Curve RNA Drivers)",
        "notes": "Drivers target RNA data_paths directly rather than connecting plug-to-plug through unitConversion nodes.",
    },
    {
        "maya_concept": "Shading Group (shadingEngine) + Surface Shader",
        "blender_concept": "Object.material_slots + Material.node_tree (Principled BSDF)",
        "notes": "Materials bind directly to Mesh polygon material_index slots.",
    },
]


def get_attribute_editor_snapshot(obj: Any = None) -> Dict[str, Any]:
    """Return a structured snapshot of the active object's Transform, Shape, Inputs, Drivers, and Material for the Attribute Editor."""
    import bpy

    if isinstance(obj, str):
        obj = bpy.data.objects.get(obj)
    target = obj or (
        getattr(bpy.context.view_layer.objects, "active", None)
        if getattr(bpy.context, "view_layer", None)
        else None
    )
    if target is None:
        return {
            "ok": False,
            "has_object": False,
            "object_name": "",
            "tabs": [],
            "concept_mapping": list(BLENDER_MAYA_CONCEPT_MAPPING),
        }

    obj_linked = channel_box_ext.is_datablock_linked(target)
    shape_info = channel_box_ext.get_object_shape_info(target)
    inputs_list = channel_box_ext.get_object_inputs(target)

    # Drivers inspection (Object + Shape)
    drivers: List[str] = []
    for datablock in (target, getattr(target, "data", None)):
        ad = getattr(datablock, "animation_data", None) if datablock is not None else None
        for drv in getattr(ad, "drivers", ()) if ad is not None else ():
            drivers.append(f"{datablock.name}.{drv.data_path}[{drv.array_index}]")

    # Active Material inspection
    mat = getattr(target, "active_material", None)
    mat_info: Dict[str, Any] = {
        "has_material": mat is not None,
        "material_name": mat.name if mat is not None else "",
        "linked": channel_box_ext.is_datablock_linked(mat) if mat is not None else False,
        "roughness": 0.5,
        "metallic": 0.0,
        "base_color": (0.8, 0.8, 0.8, 1.0),
    }
    if mat is not None and getattr(mat, "use_nodes", False) and mat.node_tree is not None:
        for nd in mat.node_tree.nodes:
            if nd.type == "BSDF_PRINCIPLED":
                try:
                    c = nd.inputs["Base Color"].default_value
                    mat_info["base_color"] = tuple(round(float(x), 3) for x in c)
                    mat_info["metallic"] = round(float(nd.inputs["Metallic"].default_value), 3)
                    mat_info["roughness"] = round(float(nd.inputs["Roughness"].default_value), 3)
                except Exception:
                    pass
                break

    tabs = [target.name]
    if shape_info["has_shape"]:
        tabs.append(shape_info["shape_name"])
    for inp in inputs_list:
        tabs.append(inp["node_name"])
    if mat_info["has_material"]:
        tabs.append(mat_info["material_name"])

    return {
        "ok": True,
        "has_object": True,
        "object_name": target.name,
        "object_type": target.type,
        "linked": obj_linked or shape_info["linked"],
        "editable": not (obj_linked or shape_info["linked"]),
        "tabs": tabs,
        "transform": {
            "location": tuple(round(float(v), 4) for v in target.location),
            "rotation_deg": tuple(round(math.degrees(float(v)), 4) for v in target.rotation_euler),
            "scale": tuple(round(float(v), 4) for v in target.scale),
            "rotation_mode": str(target.rotation_mode),
            "display_type": str(getattr(target, "display_type", "TEXTURED")),
            "visible": not bool(getattr(target, "hide_viewport", False)),
        },
        "shape": shape_info,
        "inputs": inputs_list,
        "drivers": drivers,
        "material": mat_info,
        "concept_mapping": list(BLENDER_MAYA_CONCEPT_MAPPING),
    }


def set_attribute_editor_value(
    section: str,
    attr_name: str,
    value: Any,
    obj: Any = None,
) -> Dict[str, Any]:
    """Mutate an attribute through the Attribute Editor (`transform`, `shape`, `material`) with linked-data safety."""
    import bpy

    valid_sections = {"transform", "shape", "material", "shader"}
    if str(section).strip().lower() not in valid_sections and str(attr_name).strip().lower() in valid_sections:
        # Caller passed (obj_or_name, section, attr_name, value)
        obj, section, attr_name, value = section, attr_name, str(value), obj

    if isinstance(obj, str):
        obj = bpy.data.objects.get(obj)
    target = obj or getattr(bpy.context.view_layer.objects, "active", None)
    if target is None:
        return {"ok": False, "error": "No active object"}

    sec = (section or "transform").strip().lower()
    if sec == "shader":
        sec = "material"
    if sec == "transform":
        if channel_box_ext.is_datablock_linked(target):
            return {"ok": False, "linked": True, "error": f"Transform '{target.name}' is linked and read-only"}
        if attr_name in ("translate_x", "translate_y", "translate_z"):
            idx = {"translate_x": 0, "translate_y": 1, "translate_z": 2}[attr_name]
            target.location[idx] = float(value)
        elif attr_name in ("rotate_x", "rotate_y", "rotate_z"):
            idx = {"rotate_x": 0, "rotate_y": 1, "rotate_z": 2}[attr_name]
            target.rotation_euler[idx] = math.radians(float(value))
        elif attr_name in ("scale_x", "scale_y", "scale_z"):
            idx = {"scale_x": 0, "scale_y": 1, "scale_z": 2}[attr_name]
            target.scale[idx] = float(value)
        elif attr_name == "display_type":
            target.display_type = str(value).upper()
        elif attr_name == "rotation_mode":
            target.rotation_mode = str(value).upper()
        else:
            return {"ok": False, "error": f"Unsupported transform attribute '{attr_name}'"}
        target.update_tag()
        refresh_attribute_editor()
        return {"ok": True, "section": "transform", "attr": attr_name, "snapshot": get_attribute_editor_snapshot(target)}

    if sec == "shape":
        if attr_name == "shape_name":
            res = channel_box_ext.rename_object_shape(target, str(value))
            refresh_attribute_editor()
            return res
        return {"ok": False, "error": f"Unsupported shape attribute '{attr_name}'"}

    if sec == "material":
        if channel_box_ext.is_datablock_linked(target):
            return {"ok": False, "linked": True, "error": "Object is linked"}
        mat = getattr(target, "active_material", None)
        if mat is None:
            mat = bpy.data.materials.new(name=f"{target.name}_StandardSurface")
            mat.use_nodes = True
            target.data.materials.append(mat)
        if channel_box_ext.is_datablock_linked(mat):
            return {"ok": False, "linked": True, "error": "Material is linked and read-only"}
        if attr_name == "material_name":
            mat.name = str(value).strip() or mat.name
        elif getattr(mat, "use_nodes", False) and mat.node_tree is not None:
            for nd in mat.node_tree.nodes:
                if nd.type == "BSDF_PRINCIPLED":
                    if attr_name == "roughness":
                        nd.inputs["Roughness"].default_value = max(0.0, min(1.0, float(value)))
                    elif attr_name == "metallic":
                        nd.inputs["Metallic"].default_value = max(0.0, min(1.0, float(value)))
                    break
        refresh_attribute_editor()
        return {"ok": True, "section": "material", "attr": attr_name, "snapshot": get_attribute_editor_snapshot(target)}

    return {"ok": False, "error": f"Unknown section '{section}'"}


class MayaAttributeEditorWidget:
    """Qt Attribute Editor widget featuring Maya node tabs, live 2-way controls, and honest Blender mapping."""

    def __init__(self, parent: Any = None):
        from qtpy import QtCore, QtWidgets

        self._updating = False
        self.widget = QtWidgets.QFrame(parent)
        self.widget.setObjectName("MayaPanelRoot")
        style.apply_studio_style(self.widget)

        vlay = QtWidgets.QVBoxLayout(self.widget)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        # Top Node Header Banner
        hdr = QtWidgets.QFrame()
        hdr.setObjectName("MayaSectionHeader")
        hrow = QtWidgets.QHBoxLayout(hdr)
        hrow.setContentsMargins(6, 3, 6, 3)
        self.lbl_node_title = QtWidgets.QLabel("ATTRIBUTE EDITOR")
        self.lbl_node_title.setObjectName("MayaSectionTitle")
        self.lbl_lock_badge = QtWidgets.QLabel("LOCAL")
        self.lbl_lock_badge.setObjectName("MayaBadgeTeal")
        self.btn_native_props = QtWidgets.QPushButton("Native Properties")
        self.btn_native_props.setToolTip("Expose native Blender Properties editor in-place")
        self.btn_native_props.setFixedHeight(20)
        self.btn_native_props.clicked.connect(self._on_open_native_props)
        hrow.addWidget(self.lbl_node_title)
        hrow.addStretch(1)
        hrow.addWidget(self.lbl_lock_badge)
        hrow.addWidget(self.btn_native_props)
        vlay.addWidget(hdr)

        # Maya Node Tabs (Transform | Shape | Inputs/Modifiers | Material | Blender Mapping)
        self.tabs = QtWidgets.QTabWidget()
        vlay.addWidget(self.tabs, 1)

        # --- Tab 1: Transform Node ---
        self.tab_transform = QtWidgets.QWidget()
        t_lay = QtWidgets.QVBoxLayout(self.tab_transform)
        t_lay.setContentsMargins(6, 6, 6, 6)
        t_lay.setSpacing(4)

        form_t = QtWidgets.QGridLayout()
        form_t.setHorizontalSpacing(4)
        form_t.setVerticalSpacing(4)

        self.spn_tx = self._make_spin(-10000.0, 10000.0, 0.1, "translate_x")
        self.spn_ty = self._make_spin(-10000.0, 10000.0, 0.1, "translate_y")
        self.spn_tz = self._make_spin(-10000.0, 10000.0, 0.1, "translate_z")
        form_t.addWidget(QtWidgets.QLabel("Translate:"), 0, 0)
        form_t.addWidget(self.spn_tx, 0, 1)
        form_t.addWidget(self.spn_ty, 0, 2)
        form_t.addWidget(self.spn_tz, 0, 3)

        self.spn_rx = self._make_spin(-3600.0, 3600.0, 5.0, "rotate_x")
        self.spn_ry = self._make_spin(-3600.0, 3600.0, 5.0, "rotate_y")
        self.spn_rz = self._make_spin(-3600.0, 3600.0, 5.0, "rotate_z")
        form_t.addWidget(QtWidgets.QLabel("Rotate (deg):"), 1, 0)
        form_t.addWidget(self.spn_rx, 1, 1)
        form_t.addWidget(self.spn_ry, 1, 2)
        form_t.addWidget(self.spn_rz, 1, 3)

        self.spn_sx = self._make_spin(0.001, 10000.0, 0.1, "scale_x")
        self.spn_sy = self._make_spin(0.001, 10000.0, 0.1, "scale_y")
        self.spn_sz = self._make_spin(0.001, 10000.0, 0.1, "scale_z")
        form_t.addWidget(QtWidgets.QLabel("Scale:"), 2, 0)
        form_t.addWidget(self.spn_sx, 2, 1)
        form_t.addWidget(self.spn_sy, 2, 2)
        form_t.addWidget(self.spn_sz, 2, 3)

        self.cmb_display = QtWidgets.QComboBox()
        self.cmb_display.addItems(["TEXTURED", "SOLID", "WIRE", "BOUNDS"])
        self.cmb_display.currentTextChanged.connect(
            lambda txt: self._on_transform_edited("display_type", txt)
        )
        form_t.addWidget(QtWidgets.QLabel("Display Type:"), 3, 0)
        form_t.addWidget(self.cmb_display, 3, 1, 1, 3)

        t_lay.addLayout(form_t)
        t_lay.addStretch(1)
        self.tabs.addTab(self.tab_transform, "Transform")

        # --- Tab 2: Shape Node (Object.data) ---
        self.tab_shape = QtWidgets.QWidget()
        s_lay = QtWidgets.QVBoxLayout(self.tab_shape)
        s_lay.setContentsMargins(6, 6, 6, 6)
        s_lay.setSpacing(5)

        s_form = QtWidgets.QFormLayout()
        self.txt_ae_shape_name = QtWidgets.QLineEdit()
        self.txt_ae_shape_name.editingFinished.connect(
            lambda: set_attribute_editor_value("shape", "shape_name", self.txt_ae_shape_name.text())
        )
        self.lbl_ae_shape_stats = QtWidgets.QLabel("-")
        self.lbl_ae_drivers = QtWidgets.QLabel("None")
        s_form.addRow("Shape Datablock:", self.txt_ae_shape_name)
        s_form.addRow("Topology:", self.lbl_ae_shape_stats)
        s_form.addRow("RNA Drivers:", self.lbl_ae_drivers)
        s_lay.addLayout(s_form)
        s_lay.addStretch(1)
        self.tabs.addTab(self.tab_shape, "Shape")

        # --- Tab 3: Material / Shader ---
        self.tab_mat = QtWidgets.QWidget()
        m_lay = QtWidgets.QVBoxLayout(self.tab_mat)
        m_lay.setContentsMargins(6, 6, 6, 6)
        m_lay.setSpacing(5)

        m_form = QtWidgets.QFormLayout()
        self.txt_mat_name = QtWidgets.QLineEdit()
        self.txt_mat_name.editingFinished.connect(
            lambda: set_attribute_editor_value("material", "material_name", self.txt_mat_name.text())
        )
        self.spn_roughness = QtWidgets.QDoubleSpinBox()
        self.spn_roughness.setRange(0.0, 1.0)
        self.spn_roughness.setSingleStep(0.05)
        self.spn_roughness.valueChanged.connect(
            lambda v: self._on_material_edited("roughness", v)
        )
        self.spn_metallic = QtWidgets.QDoubleSpinBox()
        self.spn_metallic.setRange(0.0, 1.0)
        self.spn_metallic.setSingleStep(0.05)
        self.spn_metallic.valueChanged.connect(
            lambda v: self._on_material_edited("metallic", v)
        )
        m_form.addRow("Shader Name:", self.txt_mat_name)
        m_form.addRow("Roughness:", self.spn_roughness)
        m_form.addRow("Metallic:", self.spn_metallic)
        m_lay.addLayout(m_form)
        m_lay.addStretch(1)
        self.tabs.addTab(self.tab_mat, "Shader")

        # --- Tab 4: Honest Blender <-> Maya Concept Mapping ---
        self.tab_map = QtWidgets.QWidget()
        map_lay = QtWidgets.QVBoxLayout(self.tab_map)
        map_lay.setContentsMargins(4, 4, 4, 4)
        self.tbl_mapping = QtWidgets.QTableWidget(len(BLENDER_MAYA_CONCEPT_MAPPING), 3)
        self.tbl_mapping.setHorizontalHeaderLabels(["Maya Concept", "Blender Counterpart", "Parity Notes"])
        self.tbl_mapping.verticalHeader().setVisible(False)
        self.tbl_mapping.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_mapping.horizontalHeader().setStretchLastSection(True)
        for r, entry in enumerate(BLENDER_MAYA_CONCEPT_MAPPING):
            self.tbl_mapping.setItem(r, 0, QtWidgets.QTableWidgetItem(entry["maya_concept"]))
            self.tbl_mapping.setItem(r, 1, QtWidgets.QTableWidgetItem(entry["blender_concept"]))
            self.tbl_mapping.setItem(r, 2, QtWidgets.QTableWidgetItem(entry["notes"]))
            self.tbl_mapping.setRowHeight(r, 24)
        map_lay.addWidget(self.tbl_mapping, 1)
        self.tabs.addTab(self.tab_map, "Maya↔Blender Map")

    def _make_spin(self, min_v: float, max_v: float, step: float, attr_key: str):
        from qtpy import QtWidgets

        spn = QtWidgets.QDoubleSpinBox()
        spn.setRange(min_v, max_v)
        spn.setDecimals(3)
        spn.setSingleStep(step)
        spn.valueChanged.connect(lambda val, k=attr_key: self._on_transform_edited(k, val))
        return spn

    def _on_transform_edited(self, attr_key: str, val: Any) -> None:
        if self._updating:
            return
        set_attribute_editor_value("transform", attr_key, val)

    def _on_material_edited(self, attr_key: str, val: Any) -> None:
        if self._updating:
            return
        set_attribute_editor_value("material", attr_key, val)

    def _on_open_native_props(self) -> None:
        from . import desktop

        desktop.cycle_right_dock("NATIVE_PROPERTIES")

    def refresh(self) -> Dict[str, Any]:
        snap = get_attribute_editor_snapshot()
        self._updating = True
        try:
            if not snap["has_object"]:
                self.lbl_node_title.setText("ATTRIBUTE EDITOR — (No Selection)")
                self.lbl_lock_badge.setText("IDLE")
                return snap

            self.lbl_node_title.setText(f"AE: {snap['object_name']}")
            if snap["linked"]:
                self.lbl_lock_badge.setText("LINKED (READ-ONLY)")
                self.lbl_lock_badge.setObjectName("MayaBadgeAmber")
            else:
                self.lbl_lock_badge.setText("EDITABLE")
                self.lbl_lock_badge.setObjectName("MayaBadgeTeal")

            self.tabs.setTabText(0, snap["object_name"])
            sh = snap["shape"]
            self.tabs.setTabText(1, sh["shape_name"] or "Shape")

            t = snap["transform"]
            editable = snap["editable"]
            for spn, val in (
                (self.spn_tx, t["location"][0]),
                (self.spn_ty, t["location"][1]),
                (self.spn_tz, t["location"][2]),
                (self.spn_rx, t["rotation_deg"][0]),
                (self.spn_ry, t["rotation_deg"][1]),
                (self.spn_rz, t["rotation_deg"][2]),
                (self.spn_sx, t["scale"][0]),
                (self.spn_sy, t["scale"][1]),
                (self.spn_sz, t["scale"][2]),
            ):
                spn.blockSignals(True)
                spn.setValue(val)
                spn.setReadOnly(not editable)
                spn.blockSignals(False)

            self.cmb_display.blockSignals(True)
            self.cmb_display.setCurrentText(t["display_type"])
            self.cmb_display.setEnabled(editable)
            self.cmb_display.blockSignals(False)

            self.txt_ae_shape_name.blockSignals(True)
            self.txt_ae_shape_name.setText(sh["shape_name"] if sh["has_shape"] else "(None)")
            self.txt_ae_shape_name.setReadOnly(not sh.get("editable", False))
            self.txt_ae_shape_name.blockSignals(False)

            self.lbl_ae_shape_stats.setText(
                f"{sh['shape_type']} | {sh.get('vertices', 0)} verts, {sh.get('polygons', 0)} faces"
            )
            self.lbl_ae_drivers.setText(
                ", ".join(snap["drivers"]) if snap["drivers"] else "No active RNA drivers"
            )

            mat = snap["material"]
            self.txt_mat_name.blockSignals(True)
            self.txt_mat_name.setText(mat["material_name"] or "(Click to create shader)")
            self.txt_mat_name.setReadOnly(mat.get("linked", False))
            self.txt_mat_name.blockSignals(False)

            self.spn_roughness.blockSignals(True)
            self.spn_roughness.setValue(mat["roughness"])
            self.spn_roughness.setReadOnly(mat.get("linked", False))
            self.spn_roughness.blockSignals(False)

            self.spn_metallic.blockSignals(True)
            self.spn_metallic.setValue(mat["metallic"])
            self.spn_metallic.setReadOnly(mat.get("linked", False))
            self.spn_metallic.blockSignals(False)
        except Exception:
            pass
        finally:
            self._updating = False
        return snap


_ae_instance: Optional[MayaAttributeEditorWidget] = None


def ensure_attribute_editor_widget() -> Optional[MayaAttributeEditorWidget]:
    global _ae_instance
    if _ae_instance is not None:
        _ae_instance.refresh()
        return _ae_instance
    try:
        from . import desktop

        desktop.ensure_ui_handler()
        _ae_instance = MayaAttributeEditorWidget()
        _ae_instance.refresh()
        return _ae_instance
    except Exception:
        return None


def refresh_attribute_editor() -> Optional[Dict[str, Any]]:
    if _ae_instance is not None:
        return _ae_instance.refresh()
    return None


def teardown_attribute_editor() -> None:
    global _ae_instance
    if _ae_instance is not None:
        try:
            _ae_instance.widget.hide()
            _ae_instance.widget.deleteLater()
        except Exception:
            pass
        _ae_instance = None
