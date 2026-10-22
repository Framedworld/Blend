"""Docked Maya Hypershade Material Browser, Shader Ball Swatch Bin & Texture Path Inspector (`landfall_studio.ui.hypershade_panel`).

Provides the `HYPERSHADE` tab inside `RightAreaQtDock`:
1. **Scene Material Swatch Bin (`SCENE MATERIALS`):**
   - Custom `_MayaShaderBallSwatchDelegate` renders a 3D-lit shader ball swatch (`base_color`, `metallic` reflection tint, and `roughness`-scaled specular hotspot) next to each material name, surface shader type, assigned mesh count, and texture map count.
   - 1-click Maya Hypershade toolbar: `Assign to Sel`, `Select Meshes`, `Graph in Shader Editor` (opens/focuses Blender's native `ShaderNodeTree` graph), `Purge Unused`, `Merge Duplicates`, `Fix ColorSpaces`.
2. **Shader Templates (`aiStandardSurface` / `Principled` Presets):**
   - 1-click preset pills (`Chrome`, `Brushed Metal`, `Gold`, `Car Paint`, `Glass`, `Subsurface Skin`, `Plastic`, `Ceramic`, `Rubber`, `Emission`) backed by `blendertk.MatUtils.create_shader_template`.
3. **Active Shader Attribute Scrubbers & Texture / `<UDIM>` Path Audit:**
   - Live sliders/spinboxes for `Metallic`, `Roughness`, `IOR`, `Coat Weight`, and `Emission` on the selected material.
   - Live table of scene image/UDIM textures (`IMAGE | COLORSPACE / PATH | STATUS`).
"""

from __future__ import annotations

from typing import Any, Dict, List
from .. import advanced
from . import channel_box_ext, style
from ..commands import scene_edits


def _material_value(mat,key):
    socket={'metallic':'Metallic','roughness':'Roughness','coat_weight':'Coat Weight','emission_strength':'Emission Strength'}[key]
    if mat.use_nodes and mat.node_tree:
        node=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if node:return float(node.inputs[socket].default_value)
    return float(getattr(mat,key,0.0))


def _material_edit_state(mat,key):
    return mat.use_nodes,mat.roughness,mat.metallic,_material_value(mat,key)

_hypershade_widgets: List[Any] = []


def get_hypershade_ui_snapshot() -> Dict[str, Any]:
    """Return a structured snapshot of the Maya Hypershade Browser state for headless & GUI tests."""
    mats = advanced.list_scene_materials()
    templates = advanced.get_shader_templates()
    tex_audit = advanced.audit_scene_textures()
    return {
        "ok": True,
        "material_count": len(mats),
        "materials": mats,
        "templates": templates,
        "texture_audit": tex_audit,
    }


def create_hypershade_widget() -> Any:
    """Create the docked Maya Hypershade & Lookdev Browser Qt widget."""
    from qtpy import QtCore, QtGui, QtWidgets

    class _MayaShaderBallSwatchDelegate(QtWidgets.QStyledItemDelegate):
        """Custom painter that draws a 3D specular shader ball swatch + Maya material name in column 0."""

        def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> None:
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            rect = option.rect
            is_sel = bool(option.state & QtWidgets.QStyle.State_Selected)

            if is_sel:
                grad = QtGui.QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
                grad.setColorAt(0.0, QtGui.QColor("#225976"))
                grad.setColorAt(1.0, QtGui.QColor("#254759"))
                painter.fillRect(rect, grad)
                painter.fillRect(QtCore.QRect(rect.left(), rect.top(), 2, rect.height()), QtGui.QColor("#38A3D8"))
            elif index.row() % 2 == 1:
                painter.fillRect(rect, QtGui.QColor("#1A1D21"))
            else:
                painter.fillRect(rect, QtGui.QColor("#16181B"))

            col = index.column()
            text = str(index.data(QtCore.Qt.DisplayRole) or "")

            if col == 0:
                meta = index.data(QtCore.Qt.UserRole) or {}
                bc = meta.get("base_color", (0.55, 0.58, 0.62, 1.0))
                metal = float(meta.get("metallic", 0.0))
                rough = float(meta.get("roughness", 0.45))

                # Draw 16x16 3D shader ball sphere
                cx = rect.left() + 14.0
                cy = rect.center().y()
                r = 7.5
                ball_grad = QtGui.QRadialGradient(cx - 2.5, cy - 2.5, r * 1.45)

                r_col = int(max(0, min(255, bc[0] * 255)))
                g_col = int(max(0, min(255, bc[1] * 255)))
                b_col = int(max(0, min(255, bc[2] * 255)))
                base_qcol = QtGui.QColor(r_col, g_col, b_col)

                # Specular highlight intensity scales inversely with roughness
                spec_boost = int((1.0 - rough * 0.75) * 140)
                hi_qcol = QtGui.QColor(
                    min(255, r_col + spec_boost),
                    min(255, g_col + spec_boost),
                    min(255, b_col + spec_boost),
                )
                shadow_factor = 0.25 if metal > 0.5 else 0.42
                lo_qcol = QtGui.QColor(
                    int(r_col * shadow_factor),
                    int(g_col * shadow_factor),
                    int(b_col * shadow_factor),
                )

                ball_grad.setColorAt(0.0, hi_qcol)
                ball_grad.setColorAt(0.55, base_qcol)
                ball_grad.setColorAt(1.0, lo_qcol)

                painter.setPen(QtGui.QPen(QtGui.QColor("#38A3D8" if is_sel else "#353B44"), 1.0))
                painter.setBrush(QtGui.QBrush(ball_grad))
                painter.drawEllipse(QtCore.QPointF(cx, cy), r, r)

                # Draw material name
                painter.setPen(QtGui.QColor("#FFFFFF" if is_sel else "#E2E6EC"))
                f = painter.font()
                f.setPixelSize(11)
                f.setBold(is_sel)
                painter.setFont(f)
                text_rect = QtCore.QRect(rect.left() + 28, rect.top(), rect.width() - 30, rect.height())
                painter.drawText(text_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, text)
            elif col == 1:
                # Surface shader badge
                painter.setPen(QtGui.QColor("#69B8DC" if is_sel else "#8E96A0"))
                f = painter.font()
                f.setPixelSize(10)
                painter.setFont(f)
                painter.drawText(rect.adjusted(4, 0, -4, 0), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, text)
            else:
                # Assigned mesh / texture counts
                painter.setPen(QtGui.QColor("#3FB950" if text != "0" else "#6E7681"))
                f = painter.font()
                f.setPixelSize(10)
                f.setBold(text != "0")
                painter.setFont(f)
                painter.drawText(rect.adjusted(2, 0, -6, 0), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight, text)

            painter.restore()

    class _MayaHypershadeWidget(QtWidgets.QFrame):
        def __init__(self):
            super().__init__()
            self.setObjectName("MayaPanelRoot")
            style.apply_studio_style(self)
            self._updating = False
            self._selected_mat_name = ""
            self._selected_material = None
            self._slider_drag_owner = None
            self._build_ui()
            if self not in _hypershade_widgets:
                _hypershade_widgets.append(self)
            self.destroyed.connect(lambda *_: _hypershade_widgets.remove(self) if self in _hypershade_widgets else None)
            self.refresh_from_scene()

        def _build_ui(self) -> None:
            vlay = QtWidgets.QVBoxLayout(self)
            vlay.setContentsMargins(0, 0, 0, 0)
            vlay.setSpacing(0)

            # 1. Top Panel Header
            head = QtWidgets.QFrame()
            head.setObjectName("MayaSectionHeader")
            head.setFixedHeight(28)
            hlay = QtWidgets.QHBoxLayout(head)
            hlay.setContentsMargins(8, 0, 8, 0)
            hlay.setSpacing(6)

            lbl_title = QtWidgets.QLabel("HYPERSHADE / LOOKDEV BROWSER")
            lbl_title.setStyleSheet("color: #CDD3DC; font-weight: 700; font-size: 10px; letter-spacing: 0.7px;")
            hlay.addWidget(lbl_title)
            hlay.addStretch(1)

            self.lbl_mat_badge = QtWidgets.QLabel("0 Shaders")
            self.lbl_mat_badge.setStyleSheet(
                "background-color: #1B3022; color: #3FB950; border: 1px solid #2A5A38; "
                "border-radius: 8px; padding: 1px 7px; font-size: 10px; font-weight: 700;"
            )
            hlay.addWidget(self.lbl_mat_badge)
            vlay.addWidget(head)

            # 2. Scene Material Swatch Bin Section
            sec_bin = QtWidgets.QFrame()
            sec_bin.setStyleSheet("background-color: #262A31; border-bottom: 1px solid #141619;")
            sec_bin.setFixedHeight(22)
            blay = QtWidgets.QHBoxLayout(sec_bin)
            blay.setContentsMargins(8, 0, 8, 0)
            lbl_bin = QtWidgets.QLabel("▾  SCENE MATERIALS (SWATCH BIN)")
            lbl_bin.setStyleSheet("color: #A6B0BD; font-weight: 700; font-size: 10px; letter-spacing: 0.6px;")
            blay.addWidget(lbl_bin)
            blay.addStretch(1)

            btn_graph = QtWidgets.QPushButton("Graph Network ↗")
            btn_graph.setObjectName("MayaAccentButton")
            btn_graph.setFixedHeight(17)
            btn_graph.setToolTip("Open Blender's native Shader Editor focused on the selected material's node graph")
            btn_graph.clicked.connect(self._on_graph_selected)
            self.btn_graph = btn_graph
            blay.addWidget(btn_graph)
            vlay.addWidget(sec_bin)

            self.tbl_mats = QtWidgets.QTableWidget(0, 4)
            self.tbl_mats.setHorizontalHeaderLabels(["SHADER", "TYPE", "MSH", "TEX"])
            self.tbl_mats.verticalHeader().setVisible(False)
            self.tbl_mats.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.tbl_mats.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.tbl_mats.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.tbl_mats.setShowGrid(False)
            self.tbl_mats.setFixedHeight(165)
            self.tbl_mats.setItemDelegate(_MayaShaderBallSwatchDelegate(self.tbl_mats))
            hdr = self.tbl_mats.horizontalHeader()
            hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
            hdr.resizeSection(1, 78)
            hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
            hdr.resizeSection(2, 36)
            hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
            hdr.resizeSection(3, 36)
            self.tbl_mats.itemSelectionChanged.connect(self._on_mat_selected)
            vlay.addWidget(self.tbl_mats)

            # Action Bar under Swatch Bin
            act_bar = QtWidgets.QFrame()
            act_bar.setStyleSheet("background-color: #1E2126; border-bottom: 1px solid #2E333B;")
            alay = QtWidgets.QGridLayout(act_bar)
            alay.setContentsMargins(6, 5, 6, 5)
            alay.setSpacing(4)

            self.btn_assign = QtWidgets.QPushButton("Assign to Sel")
            self.btn_assign.setObjectName("MayaAccentButton")
            self.btn_assign.setFixedHeight(21)
            self.btn_assign.clicked.connect(self._on_assign_selected)

            self.btn_sel_objs = QtWidgets.QPushButton("Select Objects")
            self.btn_sel_objs.setFixedHeight(21)
            self.btn_sel_objs.clicked.connect(self._on_select_objects)

            self.btn_purge = QtWidgets.QPushButton("Purge Unused")
            self.btn_purge.setFixedHeight(21)
            self.btn_purge.clicked.connect(self._on_purge_unused)

            self.btn_fix_cs = QtWidgets.QPushButton("Fix ColorSpaces")
            self.btn_fix_cs.setFixedHeight(21)
            self.btn_fix_cs.clicked.connect(self._on_fix_colorspaces)

            alay.addWidget(self.btn_assign, 0, 0)
            alay.addWidget(self.btn_sel_objs, 0, 1)
            alay.addWidget(self.btn_purge, 1, 0)
            alay.addWidget(self.btn_fix_cs, 1, 1)
            vlay.addWidget(act_bar)

            # 3. Shader Templates (`aiStandardSurface` / `Principled` Presets)
            sec_tpl = QtWidgets.QFrame()
            sec_tpl.setStyleSheet("background-color: #262A31; border-bottom: 1px solid #141619;")
            sec_tpl.setFixedHeight(22)
            tlay = QtWidgets.QHBoxLayout(sec_tpl)
            tlay.setContentsMargins(8, 0, 8, 0)
            lbl_tpl = QtWidgets.QLabel("▾  CREATE MAYA SHADER PRESET (AISTANDARDSURFACE)")
            lbl_tpl.setStyleSheet("color: #A6B0BD; font-weight: 700; font-size: 10px; letter-spacing: 0.6px;")
            tlay.addWidget(lbl_tpl)
            vlay.addWidget(sec_tpl)

            tpl_frame = QtWidgets.QFrame()
            tpl_frame.setStyleSheet("background-color: #1C1F24; border-bottom: 1px solid #2E333B;")
            tpl_grid = QtWidgets.QGridLayout(tpl_frame)
            tpl_grid.setContentsMargins(6, 5, 6, 5)
            tpl_grid.setSpacing(4)

            featured_templates = [
                ("Chrome", "Chrome"),
                ("Brushed Metal", "Brushed Metal"),
                ("Gold", "Gold"),
                ("Car Paint", "Car Paint"),
                ("Glass", "Glass"),
                ("Skin SSS", "Subsurface Skin"),
                ("Plastic", "Plastic"),
                ("Emission", "Emission"),
            ]
            for i, (lbl, tpl_key) in enumerate(featured_templates):
                b = QtWidgets.QPushButton(lbl)
                b.setFixedHeight(20)
                b.setToolTip(f"Create & assign '{tpl_key}' shader preset")
                b.clicked.connect(lambda _=False, tk=tpl_key: self._on_create_template(tk))
                tpl_grid.addWidget(b, i // 4, i % 4)
            vlay.addWidget(tpl_frame)

            # 4. Active Shader Quick-Scrub Inspector
            sec_prm = QtWidgets.QFrame()
            sec_prm.setStyleSheet("background-color: #262A31; border-bottom: 1px solid #141619;")
            sec_prm.setFixedHeight(22)
            play = QtWidgets.QHBoxLayout(sec_prm)
            play.setContentsMargins(8, 0, 8, 0)
            self.lbl_active_shader = style.elided_label("▾  SHADER ATTRIBUTES: (None)")
            self.lbl_active_shader.setStyleSheet("color: #A6B0BD; font-weight: 700; font-size: 10px; letter-spacing: 0.6px;")
            play.addWidget(self.lbl_active_shader)
            vlay.addWidget(sec_prm)

            prm_box = QtWidgets.QFrame()
            prm_box.setStyleSheet("background-color: #181A1D; border-bottom: 1px solid #2E333B;")
            prm_lay = QtWidgets.QGridLayout(prm_box)
            prm_lay.setContentsMargins(8, 6, 8, 6)
            prm_lay.setHorizontalSpacing(8)
            prm_lay.setVerticalSpacing(4)

            self._sliders: Dict[str, Any] = {}
            self._val_labels: Dict[str, Any] = {}
            for row_idx, (p_key, p_lbl, p_max) in enumerate(
                [
                    ("metallic", "Metalness", 100),
                    ("roughness", "Specular Roughness", 100),
                    ("coat_weight", "Coat Weight", 100),
                    ("emission_strength", "Emission Weight", 200),
                ]
            ):
                lbl = QtWidgets.QLabel(p_lbl)
                lbl.setStyleSheet("color: #9AA2AE; font-size: 10px;")
                from .sculpt_input import slider
                sld = slider()
                sld.setRange(0, p_max)
                sld.setFixedHeight(16)
                vlbl = QtWidgets.QLabel("0.00")
                vlbl.setFixedWidth(36)
                vlbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                vlbl.setStyleSheet("color: #69B8DC; font-family: 'Consolas', monospace; font-size: 10px; font-weight: 700;")
                sld.valueChanged.connect(lambda val, pk=p_key: self._on_slider_changed(pk, val / 100.0))
                sld.sliderPressed.connect(lambda pk=p_key: self._begin_slider_drag(pk))
                sld.sliderReleased.connect(self._end_slider_drag)
                prm_lay.addWidget(lbl, row_idx, 0)
                prm_lay.addWidget(sld, row_idx, 1)
                prm_lay.addWidget(vlbl, row_idx, 2)
                self._sliders[p_key] = sld
                self._val_labels[p_key] = vlbl
            vlay.addWidget(prm_box)

            # 5. Scene Texture & UDIM Path Editor Table
            sec_tex = QtWidgets.QFrame()
            sec_tex.setStyleSheet("background-color: #262A31; border-bottom: 1px solid #141619;")
            sec_tex.setFixedHeight(22)
            xlay = QtWidgets.QHBoxLayout(sec_tex)
            xlay.setContentsMargins(8, 0, 8, 0)
            lbl_tex = QtWidgets.QLabel("▾  FILE TEXTURES & UDIM PATH AUDIT")
            lbl_tex.setStyleSheet("color: #A6B0BD; font-weight: 700; font-size: 10px; letter-spacing: 0.6px;")
            xlay.addWidget(lbl_tex)
            vlay.addWidget(sec_tex)

            self.tbl_tex = QtWidgets.QTableWidget(0, 3)
            self.tbl_tex.setHorizontalHeaderLabels(["IMAGE NODE", "PATH", "OK"])
            self.tbl_tex.verticalHeader().setVisible(False)
            self.tbl_tex.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.tbl_tex.setShowGrid(False)
            thdr = self.tbl_tex.horizontalHeader()
            thdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            thdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
            thdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
            thdr.resizeSection(2, 36)
            vlay.addWidget(self.tbl_tex, 1)

        def _current_mat_name(self) -> str:
            row = self.tbl_mats.currentRow()
            if row >= 0:
                it = self.tbl_mats.item(row, 0)
                if it is not None:
                    return str(it.text())
            return self._selected_mat_name

        def _on_mat_selected(self) -> None:
            if self._updating:
                return
            mname = self._current_mat_name()
            if not mname:
                return
            gesture=getattr(self,'_material_gesture',None)
            if gesture and gesture.active and self._slider_drag_owner and self._slider_drag_owner[0].name!=mname:
                gesture.cancel()
            self._selected_mat_name = mname
            self._sync_parameter_sliders(mname)

        def _sync_parameter_sliders(self, mat_name: str, rec=None) -> None:
            import bpy

            if rec is None and mat_name:
                rec = next((m for m in advanced.list_scene_materials() if m["name"] == mat_name), None)
            mat = bpy.data.materials.get(mat_name) if rec is not None else None
            self._selected_material = mat
            editable = mat is not None and not channel_box_ext.is_datablock_linked(mat)
            if mat is not None and mat.use_nodes:
                editable = editable and mat.node_tree is not None and any(node.type == "BSDF_PRINCIPLED" for node in mat.node_tree.nodes)
            previous = self._updating
            self._updating = True
            try:
                self.lbl_active_shader.setText(f"▾  SHADER ATTRIBUTES: {mat_name}" if mat is not None else "▾  SHADER ATTRIBUTES: (No Material)")
                for button in (self.btn_assign, self.btn_sel_objs, self.btn_graph):
                    button.setEnabled(mat is not None)
                for pk in ("metallic", "roughness", "coat_weight", "emission_strength"):
                    val = float(rec.get(pk, 0.0)) if rec is not None else 0.0
                    slider = self._sliders[pk]
                    slider.setEnabled(editable)
                    if not slider.isSliderDown():
                        slider.setMaximum(max(200 if pk == "emission_strength" else 100, int(round(val * 100.0))))
                        slider.setValue(int(round(val * 100.0)))
                    self._val_labels[pk].setText(f"{val:.2f}")
            finally:
                self._updating = previous

        def _begin_slider_drag(self, param_key: str) -> None:
            self._slider_drag_owner = (self._selected_material, param_key)
            mat=self._selected_material
            original_value=_material_value(mat,param_key)
            original_roughness,original_metallic=mat.roughness,mat.metallic
            has_nodes=mat.use_nodes
            def preview(value):
                # A legacy material has no shader to preview. Defer node creation
                # until the one final commit so Escape never leaves a new tree.
                if not has_nodes:return
                result=advanced.set_material_parameter(mat.name,param_key,value)
                if value==original_value:
                    mat.roughness,mat.metallic=original_roughness,original_metallic
                return result
            self._material_gesture=scene_edits.ValueGesture('Shader '+param_key,
                lambda:_material_value(mat,param_key),
                lambda value:advanced.set_material_parameter(mat.name,param_key,value),self._sliders[param_key],
                preview_write=preview,read_state=lambda:_material_edit_state(mat,param_key),
                on_cancel=self._cancel_slider_drag,on_abandon=lambda:self._cancel_slider_drag(False))

        def _cancel_slider_drag(self, refresh=True) -> None:
            owner=self._slider_drag_owner
            self._material_gesture=None
            self._slider_drag_owner=None
            if owner:
                guard=QtCore.QSignalBlocker(self._sliders[owner[1]])
                self._sliders[owner[1]].setSliderDown(False)
                del guard
            if refresh:self.refresh_from_scene()

        def _end_slider_drag(self) -> None:
            gesture=getattr(self,'_material_gesture',None)
            if gesture:gesture.finish(self._sliders[self._slider_drag_owner[1]].value()/100.0 if gesture.previewed else None)
            self._material_gesture=None
            self._slider_drag_owner = None
            self.refresh_from_scene()

        def _on_slider_changed(self, param_key: str, float_val: float) -> None:
            if self._updating:
                return
            mname = self._current_mat_name()
            if not mname:
                return
            import bpy

            mat = bpy.data.materials.get(mname)
            if mat is None or mat != self._selected_material or channel_box_ext.is_datablock_linked(mat):
                self.refresh_from_scene()
                return
            if self._slider_drag_owner is not None and self._slider_drag_owner != (mat, param_key):
                return
            self._val_labels[param_key].setText(f"{float_val:.2f}")
            gesture=getattr(self,'_material_gesture',None)
            if gesture:
                gesture.preview(float_val)
                if gesture.active and not mat.use_nodes:return
            else:scene_edits.commit('Shader '+param_key,lambda:advanced.set_material_parameter(mname,param_key,float_val),lambda:_material_edit_state(mat,param_key))
            self.refresh_from_scene()

        def _on_create_template(self, template_key: str) -> None:
            res = scene_edits.commit('Create Shader',lambda:advanced.create_from_template(template_key,assign_to_selection=True))
            if res.get("ok"):
                self._selected_mat_name = res["material"]
            self.refresh_from_scene()

        def _on_assign_selected(self) -> None:
            mname = self._current_mat_name()
            if mname:
                scene_edits.commit('Assign Shader',lambda:advanced.assign_material_to_selection(mname))
                self.refresh_from_scene()

        def _on_select_objects(self) -> None:
            mname = self._current_mat_name()
            if mname:
                scene_edits.commit('Select Shader Objects',lambda:advanced.select_objects_with_material(mname))
                self.refresh_from_scene()

        def _on_graph_selected(self) -> None:
            mname = self._current_mat_name()
            if mname:
                advanced.graph_material_in_shader_editor(mname)

        def _on_purge_unused(self) -> None:
            scene_edits.commit('Clean Shader Library',lambda:advanced.cleanup_scene_materials(delete_unused=True,merge_duplicates=True))
            self.refresh_from_scene()

        def _on_fix_colorspaces(self) -> None:
            from blendertk.mat_utils._mat_utils import MatUtils

            import bpy
            scene_edits.commit('Fix Color Spaces',MatUtils.fix_color_spaces,
                lambda:tuple((image.name,image.colorspace_settings.name) for image in bpy.data.images))
            self.refresh_from_scene()

        def refresh_from_scene(self) -> None:
            if self._updating:
                return
            self._updating = True
            material_guard = QtCore.QSignalBlocker(self.tbl_mats)
            texture_guard = QtCore.QSignalBlocker(self.tbl_tex)
            material_scroll = self.tbl_mats.verticalScrollBar().value()
            texture_scroll = self.tbl_tex.verticalScrollBar().value()
            try:
                snap = get_hypershade_ui_snapshot()
                mats = snap["materials"]
                self.lbl_mat_badge.setText(f"{len(mats)} Shaders")

                self.tbl_mats.setRowCount(len(mats))
                sel_row = 0
                for idx, m in enumerate(mats):
                    if m["name"] == self._selected_mat_name:
                        sel_row = idx
                    it_name = QtWidgets.QTableWidgetItem(m["name"])
                    it_name.setData(QtCore.Qt.UserRole, m)
                    it_type = QtWidgets.QTableWidgetItem("aiStandard" if m["use_nodes"] else "Surface")
                    it_msh = QtWidgets.QTableWidgetItem(str(m["object_count"]))
                    it_tex = QtWidgets.QTableWidgetItem(str(m["texture_count"]))
                    self._update_table_item(self.tbl_mats, idx, 0, it_name)
                    self._update_table_item(self.tbl_mats, idx, 1, it_type)
                    self._update_table_item(self.tbl_mats, idx, 2, it_msh)
                    self._update_table_item(self.tbl_mats, idx, 3, it_tex)
                    self.tbl_mats.setRowHeight(idx, 23)

                if mats:
                    self.tbl_mats.selectRow(sel_row)
                    active_m = mats[sel_row]["name"]
                    self._selected_mat_name = active_m
                    self._sync_parameter_sliders(active_m, mats[sel_row])
                else:
                    self._selected_mat_name = ""
                    self._sync_parameter_sliders("")

                imgs = snap["texture_audit"].get("images", [])
                self.tbl_tex.setRowCount(len(imgs))
                for idx, img in enumerate(imgs):
                    it_img = QtWidgets.QTableWidgetItem(img["name"])
                    it_path = QtWidgets.QTableWidgetItem(img["filepath"] or img["abspath"])
                    it_ok = QtWidgets.QTableWidgetItem("OK" if img["exists"] else "MISS")
                    self._update_table_item(self.tbl_tex, idx, 0, it_img)
                    self._update_table_item(self.tbl_tex, idx, 1, it_path)
                    self._update_table_item(self.tbl_tex, idx, 2, it_ok)
                    self.tbl_tex.setRowHeight(idx, 20)
            finally:
                self.tbl_mats.verticalScrollBar().setValue(material_scroll)
                self.tbl_tex.verticalScrollBar().setValue(texture_scroll)
                del material_guard, texture_guard
                self._updating = False

        def _update_table_item(self, table, row, column, item) -> None:
            current = table.item(row, column)
            if current is None:
                table.setItem(row, column, item)
                return
            current.setText(item.text())
            current.setData(QtCore.Qt.UserRole, item.data(QtCore.Qt.UserRole))

    return _MayaHypershadeWidget()


def refresh_hypershade_widgets() -> None:
    for w in list(_hypershade_widgets):
        try:
            w.refresh_from_scene()
        except Exception:
            pass
