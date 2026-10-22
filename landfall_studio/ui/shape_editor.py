"""Modern Maya `Shape Editor & Skin Weights` Docked Panel (`landfall_studio.ui.shape_editor`).

Provides the `SHAPE_EDITOR` (`Shape / Skin`) tab inside `RightAreaQtDock`:
1. **Shape Editor (BlendShapes & In-Between Correctives):**
   - Multi-Master Driver Hazard status pill (`SAFE` vs `MULTI-MASTER HAZARD`)
   - Live Shape Target table (`Basis`, master morphs, `_tween_w###` tent correctives, and `[HELD REF]` badges)
   - Interactive Target Weight slider (`0.000 .. 1.000`) + `Key [S]` button
   - Action strip: `+ Add Target`, `Extract (Held Ref)`, `Sync Held Target`, `Propagate Base`, `Mirror`, `Blendshape Animator...`
2. **Skin Weights & Locked Influences (`Hold`):**
   - Active Armature & Normalization summary (`Rig`, `Unnormalized`, `Over-Limit`)
   - Influence table showing every bone vertex group, `Hold (Lock)` status (`LOCKED` vs `Open`), Average Weight, and Max Weight
   - Skin action strip: `Toggle Hold`, `Weight Hammer`, `Normalize`, `Prune (<0.01)`, `Mirror L↔R`, `Transfer Weights`
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from . import channel_box_ext, icons, style

_active_se_widgets: List[Any] = []


def create_shape_editor_widget(parent: Optional[Any] = None) -> Optional[Any]:
    """Create and return a `MayaShapeEditorWidget` instance."""
    try:
        from qtpy import QtCore, QtGui, QtWidgets
    except ImportError:
        return None

    class MayaShapeEditorWidget(QtWidgets.QScrollArea):
        def __init__(self, parent_widget=None):
            super().__init__(parent_widget)
            self.setObjectName("LandfallMayaShapeEditor")
            self.setWidgetResizable(True)
            self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.setFrameShape(QtWidgets.QFrame.NoFrame)
            # Use the existing pointer owner for direct pen taps and tray grabs.
            self.setProperty('landfallSculptInput', True)
            style.apply_studio_style(self)
            self._updating_ui = False
            self._selected_key_name: str = ""
            self._selected_group_name: str = ""
            self._target_mesh = None
            self._weight_drag_owner = None
            self._mesh_action_buttons = []
            self._build_ui()
            if self not in _active_se_widgets:
                _active_se_widgets.append(self)
            self.destroyed.connect(lambda *_: _active_se_widgets.remove(self) if self in _active_se_widgets else None)
            self.refresh_from_scene()

        def _build_ui(self) -> None:
            content = QtWidgets.QWidget()
            self.setWidget(content)
            layout = QtWidgets.QVBoxLayout(content)
            layout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.setSpacing(6)

            # 1. Top Object & Multi-Master Hazard Status Bar
            top_row = QtWidgets.QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(6)

            self._obj_label = style.elided_label("MESH: (None)")
            self._obj_label.setStyleSheet(
                "color: #E2E8F0; font-weight: 700; font-size: 11px; padding: 2px 4px;"
            )
            top_row.addWidget(self._obj_label, 1)

            self._hazard_pill = QtWidgets.QLabel("MORPH: SAFE")
            self._hazard_pill.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
            self._hazard_pill.setAlignment(QtCore.Qt.AlignCenter)
            self._hazard_pill.setStyleSheet(
                "background-color: #163026; color: #56D364; border: 1px solid #2EA043; "
                "border-radius: 3px; padding: 2px 7px; font-weight: 700; font-size: 10px;"
            )
            top_row.addWidget(self._hazard_pill)
            layout.addLayout(top_row)

            # 2. SHAPE EDITOR SECTION
            shape_hdr = QtWidgets.QLabel("SHAPE EDITOR  |  BLENDSHAPES & IN-BETWEENS")
            shape_hdr.setProperty("mayaSectionHeader", True)
            layout.addWidget(shape_hdr)

            self._shape_table = QtWidgets.QTableWidget(0, 4, self)
            self._shape_table.setHorizontalHeaderLabels(["Target / Key", "Weight", "Type / Held Ref", "Drv/Key"])
            self._shape_table.verticalHeader().setVisible(False)
            self._shape_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self._shape_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self._shape_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self._shape_table.setFixedHeight(148)
            hdr = self._shape_table.horizontalHeader()
            hdr.setStretchLastSection(True)
            hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            self._shape_table.itemSelectionChanged.connect(self._on_shape_row_selected)
            layout.addWidget(self._shape_table)

            # Target Weight Scrub Slider Row
            slider_row = QtWidgets.QHBoxLayout()
            slider_row.setContentsMargins(0, 0, 0, 0)
            slider_row.setSpacing(5)

            self._active_key_lbl = QtWidgets.QLabel("Weight:")
            self._active_key_lbl.setStyleSheet("color: #9AA4B2; font-size: 11px; font-weight: 600;")
            slider_row.addWidget(self._active_key_lbl)

            from .sculpt_input import slider
            self._weight_slider = slider(self)
            self._weight_slider.setRange(0, 1000)
            self._weight_slider.setValue(0)
            self._weight_slider.valueChanged.connect(self._on_weight_slider_changed)
            self._weight_slider.sliderPressed.connect(self._begin_weight_drag)
            self._weight_slider.sliderReleased.connect(self._end_weight_drag)
            slider_row.addWidget(self._weight_slider, 1)

            self._weight_spin = style.compact_double_spin(self)
            self._weight_spin.setRange(0.0, 1.0)
            self._weight_spin.setSingleStep(0.05)
            self._weight_spin.setDecimals(3)
            self._weight_spin.setKeyboardTracking(False)
            self._weight_spin.setFixedWidth(72)
            self._weight_spin.valueChanged.connect(self._on_weight_spin_changed)
            slider_row.addWidget(self._weight_spin)

            self._btn_key_shape = QtWidgets.QPushButton("Key [S]")
            self._btn_key_shape.setFixedHeight(22)
            self._btn_key_shape.setStyleSheet(
                "background-color: #3A2024; color: #FF7B72; border: 1px solid #8E363A; font-weight: 700;"
            )
            self._btn_key_shape.clicked.connect(self._on_keyframe_selected_shape)
            slider_row.addWidget(self._btn_key_shape)
            layout.addLayout(slider_row)

            # Two columns keep complete labels readable in the narrow dock.
            s_grid = QtWidgets.QGridLayout()
            s_grid.setContentsMargins(0, 0, 0, 0)
            s_grid.setSpacing(4)

            shape_btns = [
                ("+ Add Target", "blendshape", self._on_add_target),
                ("Extract (Held)", "duplicate", self._on_extract_target),
                ("Sync Held Ref", "bake_pivot", self._on_sync_held_target),
                ("In-Betweens", "smooth_preview", self._on_eval_correctives),
                ("Mirror Shape", "mirror", self._on_mirror_shape),
                ("Shape Animator...", "blendshape", self._on_open_blendshape_animator),
            ]
            for idx, (label, icon_name, cb) in enumerate(shape_btns):
                btn = QtWidgets.QPushButton(label, self)
                ic = icons.get_icon(icon_name, size=14)
                if ic is not None:
                    btn.setIcon(ic)
                btn.setFixedHeight(24)
                btn.setToolTip(label)
                btn.clicked.connect(cb)
                if cb != self._on_open_blendshape_animator:
                    self._mesh_action_buttons.append(btn)
                s_grid.addWidget(btn, idx // 2, idx % 2)
            layout.addLayout(s_grid)

            # 3. SKIN WEIGHTS & LOCKED INFLUENCES SECTION
            skin_hdr = QtWidgets.QLabel("SKIN WEIGHTS  |  INFLUENCES & HOLD LOCKS")
            skin_hdr.setProperty("mayaSectionHeader", True)
            layout.addWidget(skin_hdr)

            self._skin_summary_lbl = style.elided_label("Rig: (None) | Groups: 0 | Locked: 0")
            self._skin_summary_lbl.setStyleSheet(
                "background-color: #16181B; color: #79C0FF; border: 1px solid #2A2E35; "
                "border-radius: 3px; padding: 3px 6px; font-size: 10px; font-weight: 600;"
            )
            layout.addWidget(self._skin_summary_lbl)

            self._skin_table = QtWidgets.QTableWidget(0, 4, self)
            self._skin_table.setHorizontalHeaderLabels(["Bone / Group", "Hold (Lock)", "Avg W", "Max W"])
            self._skin_table.verticalHeader().setVisible(False)
            self._skin_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self._skin_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self._skin_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self._skin_table.setFixedHeight(138)
            shdr = self._skin_table.horizontalHeader()
            shdr.setStretchLastSection(True)
            shdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            shdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            shdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            self._skin_table.itemSelectionChanged.connect(self._on_skin_row_selected)
            layout.addWidget(self._skin_table)

            w_grid = QtWidgets.QGridLayout()
            w_grid.setContentsMargins(0, 0, 0, 0)
            w_grid.setSpacing(4)

            skin_btns = [
                ("Hold Influence", "freeze_transforms", self._on_toggle_group_lock, "Toggle the selected influence's weight lock"),
                ("Weight Hammer", "target_weld", self._on_weight_hammer, "Average selected vertex weights from their neighbors, respecting locks"),
                ("Normalize", "bind_skin", self._on_normalize_weights, "Normalize weights while preserving locked influences"),
                ("Prune Weights", "delete_non_deformer", self._on_prune_weights, "Prune weights below 0.01, keeping up to four influences and respecting locks"),
                ("Mirror Weights", "mirror", self._on_mirror_weights, "Mirror left/right skin weights, respecting locks"),
                ("Audit Skin", "scene_audit", self.refresh_from_scene, "Refresh the skin and shape summaries and validation status"),
            ]
            for idx, (label, icon_name, cb, tooltip) in enumerate(skin_btns):
                btn = QtWidgets.QPushButton(label, self)
                ic = icons.get_icon(icon_name, size=14)
                if ic is not None:
                    btn.setIcon(ic)
                btn.setFixedHeight(24)
                btn.setToolTip(tooltip)
                btn.clicked.connect(cb)
                if cb != self.refresh_from_scene:
                    self._mesh_action_buttons.append(btn)
                w_grid.addWidget(btn, idx // 2, idx % 2)
            layout.addLayout(w_grid)

            layout.addStretch(1)

        def _active_mesh(self):
            try:
                import bpy

                obj = getattr(bpy.context, "active_object", None)
                if obj is None and bpy.context.view_layer:
                    obj = bpy.context.view_layer.objects.active
                if obj is not None and getattr(obj, "type", None) == "MESH":
                    return obj
                for o in getattr(bpy.context, "selected_objects", ()):
                    if getattr(o, "type", None) == "MESH":
                        return o
            except Exception:
                pass
            return None

        def _editable_mesh(self):
            obj = self._active_mesh()
            if obj is None or obj != self._target_mesh:
                self.refresh_from_scene()
                return None
            if any(channel_box_ext.is_datablock_linked(data) for data in (obj, obj.data, obj.data.shape_keys)):
                return None
            return obj

        def _begin_weight_drag(self) -> None:
            self._weight_drag_owner = (self._target_mesh, self._selected_key_name)
            from ..commands.scene_edits import ValueGesture
            from .. import character
            obj,key=self._weight_drag_owner
            self._weight_gesture=ValueGesture('Shape weight',
                lambda:obj.data.shape_keys.key_blocks[key].value,
                lambda value:character.set_shape_target_weight(obj,key,value),self._weight_slider,
                on_cancel=self._cancel_weight_drag,on_abandon=lambda:self._cancel_weight_drag(False))

        def _cancel_weight_drag(self, refresh=True) -> None:
            self._weight_gesture=None
            self._weight_drag_owner=None
            guard=QtCore.QSignalBlocker(self._weight_slider)
            self._weight_slider.setSliderDown(False)
            del guard
            if refresh:self.refresh_from_scene()

        def _end_weight_drag(self) -> None:
            gesture=getattr(self,'_weight_gesture',None)
            if gesture:gesture.finish()
            self._weight_gesture=None
            self._weight_drag_owner = None
            self.refresh_from_scene()

        def refresh_from_scene(self) -> None:
            if self._updating_ui:
                return
            self._updating_ui = True
            shape_guard = QtCore.QSignalBlocker(self._shape_table)
            skin_guard = QtCore.QSignalBlocker(self._skin_table)
            shape_scroll = self._shape_table.verticalScrollBar().value()
            skin_scroll = self._skin_table.verticalScrollBar().value()
            try:
                from .. import character

                obj = self._active_mesh()
                gesture=getattr(self,'_weight_gesture',None)
                if gesture and gesture.active and (obj,self._selected_key_name)!=self._weight_drag_owner:
                    gesture.cancel()
                same_target = obj is not None and obj == self._target_mesh
                self._target_mesh = obj
                editable = obj is not None and not any(channel_box_ext.is_datablock_linked(data)
                                                       for data in (obj, obj.data, obj.data.shape_keys))
                for button in self._mesh_action_buttons:
                    button.setEnabled(editable)
                if obj is None:
                    self._selected_key_name = ""
                    self._selected_group_name = ""
                    self._obj_label.setText("MESH: (None Selected)")
                    self._shape_table.setRowCount(0)
                    self._skin_table.setRowCount(0)
                    self._skin_summary_lbl.setText("Rig: (None) | Groups: 0 | Locked: 0")
                    self._active_key_lbl.setText("Weight:")
                    self._weight_slider.setValue(0)
                    self._weight_spin.setValue(0)
                    self._weight_slider.setEnabled(False)
                    self._weight_spin.setEnabled(False)
                    self._btn_key_shape.setEnabled(False)
                    self._hazard_pill.setText("MORPH: NO MESH")
                    return

                shape_info = character.list_shape_targets(obj)
                skin_info = character.inspect_skin_weights(obj)

                self._obj_label.setText(
                    f"MESH: {obj.name}  ({skin_info.get('vertex_count', 0)}v)"
                )

                haz = shape_info.get("multi_master_hazard", {})
                if haz.get("hazard_detected"):
                    self._hazard_pill.setText("MULTI-MASTER: DET. EVAL")
                    self._hazard_pill.setStyleSheet(
                        "background-color: #382A14; color: #F0B72F; border: 1px solid #B58118; "
                        "border-radius: 3px; padding: 2px 7px; font-weight: 700; font-size: 10px;"
                    )
                else:
                    self._hazard_pill.setText("MORPH: SAFE")
                    self._hazard_pill.setStyleSheet(
                        "background-color: #163026; color: #56D364; border: 1px solid #2EA043; "
                        "border-radius: 3px; padding: 2px 7px; font-weight: 700; font-size: 10px;"
                    )

                targets = shape_info.get("targets", [])
                if not same_target:
                    self._selected_key_name = ""
                    self._selected_group_name = ""
                self._shape_table.setRowCount(len(targets))
                sel_row = -1
                for r_idx, t in enumerate(targets):
                    t_name = t["name"]
                    disp_name = f"  ↳ {t_name}" if t["is_corrective"] else t_name
                    item_name = QtWidgets.QTableWidgetItem(disp_name)
                    item_name.setData(QtCore.Qt.UserRole, t_name)
                    if t["is_basis"]:
                        item_name.setForeground(QtGui.QColor("#8B949E"))
                    elif t["is_corrective"]:
                        item_name.setForeground(QtGui.QColor("#79C0FF"))
                    else:
                        item_name.setForeground(QtGui.QColor("#E6EDF3"))

                    val_str = "REF" if t["is_basis"] else f"{t['value']:.3f}"
                    item_val = QtWidgets.QTableWidgetItem(val_str)
                    item_val.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    item_val.setForeground(QtGui.QColor("#58A6FF" if not t["is_basis"] else "#6E7681"))

                    if t["held_reference_object"]:
                        type_str = f"HELD: {t['held_reference_object']}"
                        type_col = "#56D364"
                    elif t["is_basis"]:
                        type_str = "Basis"
                        type_col = "#8B949E"
                    elif t["is_corrective"]:
                        type_str = "In-Between"
                        type_col = "#D2A8FF"
                    else:
                        type_str = f"Target ({t['non_zero_delta_count']}Δ)"
                        type_col = "#A5D6FF"
                    item_type = QtWidgets.QTableWidgetItem(type_str)
                    item_type.setForeground(QtGui.QColor(type_col))

                    drv_str = "DRV" if t["has_driver"] else ("KEY" if t["is_keyed"] else "-")
                    item_drv = QtWidgets.QTableWidgetItem(drv_str)
                    item_drv.setTextAlignment(QtCore.Qt.AlignCenter)
                    if t["is_keyed"]:
                        item_drv.setForeground(QtGui.QColor("#FF7B72"))
                    elif t["has_driver"]:
                        item_drv.setForeground(QtGui.QColor("#D2A8FF"))

                    self._update_table_item(self._shape_table, r_idx, 0, item_name)
                    self._update_table_item(self._shape_table, r_idx, 1, item_val)
                    self._update_table_item(self._shape_table, r_idx, 2, item_type)
                    self._update_table_item(self._shape_table, r_idx, 3, item_drv)

                    if t_name == self._selected_key_name or (sel_row == -1 and not t["is_basis"]):
                        sel_row = r_idx

                if sel_row >= 0:
                    self._shape_table.selectRow(sel_row)
                    t_sel = targets[sel_row]
                    self._selected_key_name = t_sel["name"]
                    self._active_key_lbl.setText('Weight:')
                    self._active_key_lbl.setToolTip(t_sel['name'])
                    key_block = obj.data.shape_keys.key_blocks.get(t_sel["name"])
                    self._sync_weight_controls(key_block, editable, same_target)
                else:
                    self._selected_key_name = ""
                    self._active_key_lbl.setText("Weight:")
                    self._weight_slider.setValue(0)
                    self._weight_spin.setValue(0)
                    self._weight_slider.setEnabled(False)
                    self._weight_spin.setEnabled(False)
                    self._btn_key_shape.setEnabled(False)

                # Populate Skin Table
                arm_name = skin_info.get("armature_name") or "(Unbound)"
                groups = skin_info.get("groups", [])
                locked_list = skin_info.get("locked_groups", [])
                unnorm = skin_info.get("unnormalized_vertex_count", 0)
                self._skin_summary_lbl.setText(
                    f"Rig: {arm_name} | Groups: {len(groups)} | Locked: {len(locked_list)} | Unnorm: {unnorm}"
                )

                self._skin_table.setRowCount(len(groups))
                skin_sel_row = -1
                for r_idx, g in enumerate(groups):
                    g_name = g["name"]
                    item_g = QtWidgets.QTableWidgetItem(g_name)
                    item_g.setData(QtCore.Qt.UserRole, g_name)
                    item_g.setForeground(QtGui.QColor("#E6EDF3"))

                    is_lk = bool(g["locked"])
                    lk_item = QtWidgets.QTableWidgetItem("LOCKED" if is_lk else "Open")
                    lk_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    lk_item.setForeground(QtGui.QColor("#F0B72F" if is_lk else "#7D8590"))

                    avg_item = QtWidgets.QTableWidgetItem(f"{g['average_weight']:.3f}")
                    avg_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    avg_item.setForeground(QtGui.QColor("#79C0FF"))

                    max_item = QtWidgets.QTableWidgetItem(f"{g['max_weight']:.3f}")
                    max_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    max_item.setForeground(QtGui.QColor("#56D364"))

                    self._update_table_item(self._skin_table, r_idx, 0, item_g)
                    self._update_table_item(self._skin_table, r_idx, 1, lk_item)
                    self._update_table_item(self._skin_table, r_idx, 2, avg_item)
                    self._update_table_item(self._skin_table, r_idx, 3, max_item)
                    if g_name == self._selected_group_name or (skin_sel_row == -1 and is_lk):
                        skin_sel_row = r_idx
                if skin_sel_row == -1 and groups:
                    skin_sel_row = 0
                if skin_sel_row >= 0:
                    self._skin_table.selectRow(skin_sel_row)
                    self._selected_group_name = groups[skin_sel_row]["name"]
                else:
                    self._selected_group_name = ""
            finally:
                self._shape_table.verticalScrollBar().setValue(shape_scroll)
                self._skin_table.verticalScrollBar().setValue(skin_scroll)
                del shape_guard, skin_guard
                self._updating_ui = False

        def _update_table_item(self, table, row, column, item) -> None:
            current = table.item(row, column)
            if current is None:
                table.setItem(row, column, item)
                return
            current.setText(item.text())
            current.setData(QtCore.Qt.UserRole, item.data(QtCore.Qt.UserRole))
            current.setForeground(item.foreground())
            current.setTextAlignment(item.textAlignment())

        def _sync_weight_controls(self, key_block, editable: bool, same_target: bool = True) -> None:
            basis = (key_block is None or key_block == self._target_mesh.data.shape_keys.reference_key)
            enabled = editable and not basis
            self._weight_slider.setEnabled(enabled)
            self._weight_spin.setEnabled(enabled)
            self._btn_key_shape.setEnabled(enabled)
            if key_block is None:
                return
            if not self._weight_slider.isSliderDown():
                self._weight_slider.setRange(round(key_block.slider_min * 1000), round(key_block.slider_max * 1000))
                self._weight_slider.setValue(round(key_block.value * 1000))
            if not (same_target and self._weight_spin.hasFocus()):
                self._weight_spin.setRange(key_block.slider_min, key_block.slider_max)
                self._weight_spin.setValue(key_block.value)

        def _on_shape_row_selected(self) -> None:
            if self._updating_ui:
                return
            obj = self._active_mesh()
            if obj is None or obj != self._target_mesh:
                self.refresh_from_scene()
                return
            row = self._shape_table.currentRow()
            if row < 0:
                return
            it = self._shape_table.item(row, 0)
            if it is None:
                return
            kname = str(it.data(QtCore.Qt.UserRole) or it.text().strip())
            self._selected_key_name = kname
            self._active_key_lbl.setText('Weight:')
            self._active_key_lbl.setToolTip(kname)
            if obj and getattr(obj.data, "shape_keys", None) and kname in obj.data.shape_keys.key_blocks:
                self._updating_ui = True
                try:
                    editable = self._editable_mesh() is not None
                    self._sync_weight_controls(obj.data.shape_keys.key_blocks[kname], editable, False)
                    if editable:
                        obj.active_shape_key_index = obj.data.shape_keys.key_blocks.find(kname)
                finally:
                    self._updating_ui = False

        def _on_skin_row_selected(self) -> None:
            if self._updating_ui:
                return
            if self._active_mesh() != self._target_mesh:
                self.refresh_from_scene()
                return
            row = self._skin_table.currentRow()
            if row < 0:
                return
            it = self._skin_table.item(row, 0)
            if it is not None:
                self._selected_group_name = str(it.data(QtCore.Qt.UserRole) or it.text().strip())

        def _on_weight_slider_changed(self, slider_val: int) -> None:
            if self._updating_ui or not self._selected_key_name:
                return
            w = float(slider_val) / 1000.0
            from .. import character

            obj = self._editable_mesh()
            if self._weight_drag_owner is not None and self._weight_drag_owner != (obj, self._selected_key_name):
                return
            if obj is not None:
                from ..commands.scene_edits import commit
                gesture=getattr(self,'_weight_gesture',None)
                key=self._selected_key_name
                if gesture:gesture.preview(w)
                else:commit('Shape weight',lambda:character.set_shape_target_weight(obj,key,w),lambda:obj.data.shape_keys.key_blocks[key].value)
                self.refresh_from_scene()

        def _on_weight_spin_changed(self, val: float) -> None:
            if self._updating_ui or not self._selected_key_name:
                return
            from .. import character

            obj = self._editable_mesh()
            if obj is not None:
                from ..commands.scene_edits import commit
                key=self._selected_key_name
                commit('Shape weight',lambda:character.set_shape_target_weight(obj,key,float(val)),lambda:obj.data.shape_keys.key_blocks[key].value)
                self.refresh_from_scene()

        def _on_keyframe_selected_shape(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None and self._selected_key_name:
                from ..commands.scene_edits import commit
                commit('Key Shape',lambda:character.keyframe_shape_target(obj,self._selected_key_name))
                self.refresh_from_scene()

        def _on_add_target(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None:
                from ..commands.scene_edits import commit
                commit('Add Shape Target',lambda:character.create_shape_target(obj,name='MorphTarget',from_mix=True))
                self.refresh_from_scene()

        def _on_extract_target(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None and self._selected_key_name:
                from ..commands.scene_edits import commit
                commit('Extract Shape Target',lambda:character.extract_target_mesh_with_reference(
                    obj,self._selected_key_name,offset_vector=(2.2,0.0,0.0)))
                self.refresh_from_scene()

        def _on_sync_held_target(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None:
                from ..commands.scene_edits import commit
                commit('Sync Held Shape',lambda:character.sync_extracted_target_to_shape_key(obj,key_name=self._selected_key_name or None))
                self.refresh_from_scene()

        def _on_eval_correctives(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None:
                from ..commands.scene_edits import commit
                commit('Evaluate Correctives',lambda:character.evaluate_correctives_deterministic(obj))
                self.refresh_from_scene()

        def _on_mirror_shape(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None and self._selected_key_name:
                from ..commands.scene_edits import commit
                commit('Mirror Shape',lambda:character.mirror_shape_target(obj,self._selected_key_name))
                self.refresh_from_scene()

        def _on_open_blendshape_animator(self) -> None:
            from . import desktop

            desktop.open_panel("blendshape_animator")

        def _on_toggle_group_lock(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None and self._selected_group_name:
                vg = obj.vertex_groups.get(self._selected_group_name)
                if vg is not None:
                    from ..commands.scene_edits import commit
                    commit('Influence Lock',lambda:character.set_vertex_group_lock(obj,vg.name,locked=not vg.lock_weight))
                    self.refresh_from_scene()

        def _on_weight_hammer(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None:
                from ..commands.scene_edits import commit
                commit('Weight Hammer',lambda:character.weight_hammer_vertices(obj,respect_locks=True,normalize=True))
                self.refresh_from_scene()

        def _on_normalize_weights(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None:
                from ..commands.scene_edits import commit
                commit('Normalize Weights',lambda:character.normalize_skin_weights(obj,respect_locks=True))
                self.refresh_from_scene()

        def _on_prune_weights(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None:
                from ..commands.scene_edits import commit
                commit('Prune Weights',lambda:character.prune_small_weights(obj,threshold=.01,max_influences=4,respect_locks=True))
                self.refresh_from_scene()

        def _on_mirror_weights(self) -> None:
            from .. import character

            obj = self._editable_mesh()
            if obj is not None:
                from ..commands.scene_edits import commit
                commit('Mirror Weights',lambda:character.mirror_skin_weights(obj,respect_locks=True,normalize=True))
                self.refresh_from_scene()

    return MayaShapeEditorWidget(parent)


def refresh_shape_editor_widgets() -> None:
    """Refresh all live `MayaShapeEditorWidget` instances from the current scene."""
    for w in list(_active_se_widgets):
        try:
            w.refresh_from_scene()
        except Exception:
            pass


def get_shape_editor_snapshot() -> Dict[str, Any]:
    """Return a structured snapshot of the active `MayaShapeEditorWidget` for headless & GUI tests."""
    refresh_shape_editor_widgets()
    if not _active_se_widgets:
        return {"ok": False, "widget_count": 0}
    w = _active_se_widgets[-1]
    try:
        shape_rows = []
        for r in range(w._shape_table.rowCount()):
            shape_rows.append(
                {
                    "name": w._shape_table.item(r, 0).text().strip() if w._shape_table.item(r, 0) else "",
                    "weight": w._shape_table.item(r, 1).text().strip() if w._shape_table.item(r, 1) else "",
                    "type": w._shape_table.item(r, 2).text().strip() if w._shape_table.item(r, 2) else "",
                    "drv_key": w._shape_table.item(r, 3).text().strip() if w._shape_table.item(r, 3) else "",
                }
            )
        skin_rows = []
        for r in range(w._skin_table.rowCount()):
            skin_rows.append(
                {
                    "group": w._skin_table.item(r, 0).text().strip() if w._skin_table.item(r, 0) else "",
                    "lock": w._skin_table.item(r, 1).text().strip() if w._skin_table.item(r, 1) else "",
                    "avg_weight": w._skin_table.item(r, 2).text().strip() if w._skin_table.item(r, 2) else "",
                    "max_weight": w._skin_table.item(r, 3).text().strip() if w._skin_table.item(r, 3) else "",
                }
            )
        return {
            "ok": True,
            "widget_count": len(_active_se_widgets),
            "object_label": w._obj_label.text(),
            "hazard_pill": w._hazard_pill.text(),
            "skin_summary": w._skin_summary_lbl.text(),
            "selected_key_name": w._selected_key_name,
            "selected_group_name": w._selected_group_name,
            "shape_row_count": len(shape_rows),
            "shape_rows": shape_rows,
            "skin_row_count": len(skin_rows),
            "skin_rows": skin_rows,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
