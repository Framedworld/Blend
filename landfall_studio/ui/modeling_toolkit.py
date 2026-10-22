"""Maya Modeling Toolkit Dock Widget (`landfall_studio.ui.modeling_toolkit`).

Provides Maya's signature right-sidebar **Modeling Toolkit** tab containing:
1. **Component Selection & Transform Constraints (`Make Live`):**
   - Multi-Component / Object / Vertex / Edge / Face / UV buttons
   - Live Surface readout (`[LIVE] <ObjectName>` or `Off`) + `Make Live` / `Clear` / `Snap Mesh` actions
2. **Mesh & Component Tools Grid:**
   - `Extrude`, `Bevel`, `Bridge`, `Connect`, `Target Weld`, `Quad Draw`, `Combine`, `Separate`
3. **Live In-Viewport Caddy Parameters (`polyExtrudeFace1`, `polyBevel1`, `polyBridgeEdge1`, `polyConnectComponents1`):**
   - Synchronized live with the 3D Viewport floating caddy
4. **Quad Draw Retopology Controls:**
   - Plotted dot counter + Fill Quad, Extrude Strip, Insert Loop and Relax Mesh buttons
5. **UV Texel Density & Unwrap Bar:**
   - `Get TD`, `Set TD` (`px/m` @ `2048`), `Unwrap & Pack`, `Clean UV Sets`
6. **Scene Diagnostics & Construction History Inspector:**
   - Read-only `Audit Scene` summary (`NGons`, `Non-Manifold`, `Sheared`, `Rig/Morph Guards`)
   - `Non-Deformer History`, `Freeze (Guarded)`, `Center Pivot`
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import modeling
from . import icons, style

_active_mtk_widgets: List[Any] = []


def refresh_modeling_toolkit_widgets() -> None:
    for w in list(_active_mtk_widgets):
        try:
            w.refresh_from_scene()
        except Exception:
            pass


def create_modeling_toolkit_widget(parent: Any = None):
    """Instantiate the PySide6 `MayaModelingToolkitWidget`."""
    from qtpy import QtCore, QtWidgets

    class MayaModelingToolkitWidget(QtWidgets.QWidget):
        def __init__(self, parent_widget=None):
            super().__init__(parent_widget)
            self.setObjectName("MayaPanelRoot")
            style.apply_studio_style(self)

            outer = QtWidgets.QVBoxLayout(self)
            outer.setContentsMargins(6, 6, 6, 6)
            outer.setSpacing(6)

            def section(text):
                header = QtWidgets.QLabel(text)
                header.setObjectName("MayaSectionHeader")
                outer.addWidget(header)
                return header

            def button(label, icon_name, callback, tip="", height=24, size=14):
                btn = QtWidgets.QPushButton(label)
                if icon_name:
                    btn.setIcon(icons.get_icon(icon_name, size))
                btn.setFixedHeight(height)
                if tip:
                    btn.setToolTip(tip)
                btn.clicked.connect(callback)
                return btn

            # Selection: Maya's toolkit leads with component modes,
            # symmetry and soft selection, the three things set per edit.
            section("SELECTION")
            mask_row = QtWidgets.QHBoxLayout()
            mask_row.setSpacing(3)
            for label, icon_name, mode_code, key in (
                ("Object", "mask_obj", "OBJECT", "F8"),
                ("Vertex", "mask_vert", "VERT", "F9"),
                ("Edge", "mask_edge", "EDGE", "F10"),
                ("Face", "mask_face", "FACE", "F11"),
                ("UV", "mask_uv", "UV", "F12"),
            ):
                mask_row.addWidget(button(label, icon_name,
                    lambda _c=False, m=mode_code: self._set_component_mode(m),
                    f"{label} selection ({key})"))
            outer.addLayout(mask_row)

            option_row = QtWidgets.QHBoxLayout()
            option_row.setSpacing(10)
            self.chk_symmetry = QtWidgets.QCheckBox("Symmetry X")
            self.chk_symmetry.setToolTip("Mirror component edits across the object's X axis")
            self.chk_symmetry.toggled.connect(lambda on: self._set_tool_setting("symmetry_x", on))
            self.chk_soft = QtWidgets.QCheckBox("Soft Select (B)")
            self.chk_soft.setToolTip("Falloff for component transforms; radius in Tool Settings")
            self.chk_soft.toggled.connect(lambda on: self._set_tool_setting("soft_select_enabled", on))
            option_row.addWidget(self.chk_symmetry)
            option_row.addWidget(self.chk_soft)
            option_row.addStretch(1)
            outer.addLayout(option_row)

            # Mesh: whole-object operations.
            section("MESH")
            mesh_row = QtWidgets.QHBoxLayout()
            mesh_row.setSpacing(4)
            for label, tip, fn in (
                ("Combine", "Join the selected meshes into the active one (Ctrl+J)",
                 lambda: self._run_menu("object.join")),
                ("Separate", "Split loose parts into separate objects",
                 lambda: self._run_menu("mesh.separate", type="LOOSE")),
                ("Smooth", "Add a subdivision surface, as Maya's Smooth",
                 lambda: self._add_modifier("SUBSURF")),
                ("Mirror", "Add a Mirror modifier across X",
                 lambda: self._add_modifier("MIRROR")),
            ):
                mesh_row.addWidget(button(label, "", fn, tip, height=23))
            outer.addLayout(mesh_row)

            # Components: the four caddy operations.
            section("COMPONENTS")
            grid = QtWidgets.QGridLayout()
            grid.setHorizontalSpacing(4)
            grid.setVerticalSpacing(4)
            for idx, (lbl, icn, tool, tip) in enumerate((
                ("Extrude", "extrude", "EXTRUDE", "Extrude faces (Ctrl+E); drag the manipulator or edit the caddy"),
                ("Bevel", "bevel", "BEVEL", "Bevel edges (Ctrl+B)"),
                ("Bridge", "bridge", "BRIDGE", "Bridge two selected edge loops"),
                ("Connect", "connect", "CONNECT", "Connect selected edges with new edge loops"),
            )):
                grid.addWidget(button(lbl, icn, lambda _c=False, t=tool: self._invoke_caddy(t), tip, 26, 16),
                               idx // 2, idx % 2)
            outer.addLayout(grid)

            # The open operation's live values, mirroring the viewport caddy.
            self.lbl_caddy_header = QtWidgets.QLabel("")
            self.lbl_caddy_header.setObjectName("MayaSubtleNote")
            self.lbl_caddy_header.setWordWrap(True)
            self.lbl_caddy_header.setStyleSheet("color: #8B95A5; padding: 1px 4px;")
            outer.addWidget(self.lbl_caddy_header)

            self.caddy_form_host = QtWidgets.QWidget()
            self.caddy_form = QtWidgets.QFormLayout(self.caddy_form_host)
            self.caddy_form.setContentsMargins(4, 2, 4, 2)
            self.caddy_form.setSpacing(3)
            outer.addWidget(self.caddy_form_host)

            # Tools: interactive tools, as in Maya's toolkit.
            section("TOOLS")
            tools = QtWidgets.QGridLayout()
            tools.setHorizontalSpacing(4)
            tools.setVerticalSpacing(4)
            for idx, (lbl, icn, cb, tip) in enumerate((
                ("Multi-Cut", "", lambda: self._run_menu("mesh.knife_tool", invoke=True),
                 "Cut new edges across faces (K)"),
                ("Quad Draw", "quad_draw", self._on_quad_draw_activate,
                 "Draw retopology quads on the Live surface"),
                ("Target Weld", "target_weld", self._on_target_weld,
                 "Drag one vertex onto another to weld them"),
                ("Make Live", "make_live", self._on_make_live,
                 "Snap new geometry to the selected surface"),
            )):
                tools.addWidget(button(lbl, icn, cb, tip, 26, 16), idx // 2, idx % 2)
            outer.addLayout(tools)

            live_row = QtWidgets.QHBoxLayout()
            live_row.setSpacing(4)
            self.lbl_live_target = QtWidgets.QLabel("Live Surface: Off")
            self.lbl_live_target.setStyleSheet(
                "background-color: #16181B; color: #9BA5B4; border: 1px solid #30363F; "
                "border-radius: 3px; padding: 3px 6px; font-weight: 600;"
            )
            live_row.addWidget(self.lbl_live_target, 1)
            btn_clear_live = button("Clear", "", self._on_clear_live, "Stop snapping to the Live surface", 23)
            live_row.addWidget(btn_clear_live)
            outer.addLayout(live_row)

            qd_row1 = QtWidgets.QHBoxLayout()
            qd_row1.setSpacing(3)
            self.lbl_qd_dots = QtWidgets.QLabel("Quad Draw: 0 dots")
            self.lbl_qd_dots.setStyleSheet("color: #8B95A5; padding: 0 4px;")
            qd_row1.addWidget(self.lbl_qd_dots)

            for lbl, tip, cb in (
                ("Fill", "Build a quad from the four most recent plotted dots.", self._on_qd_fill),
                ("Strip +X", "Extrude the selected boundary edge 0.4 units along world X; uses the first boundary edge when none is selected.", self._on_qd_strip),
                ("Loop", "Insert a centered loop across the first quad strip. Ctrl-click a retopology edge in Quad Draw to choose a strip.", self._on_qd_loop),
                ("Relax", "Smooth retopology vertices and project them back onto the live surface.", self._on_qd_relax),
            ):
                b = QtWidgets.QPushButton(lbl)
                b.setToolTip(tip)
                b.setFixedHeight(22)
                b.clicked.connect(cb)
                qd_row1.addWidget(b)
            outer.addLayout(qd_row1)

            # 6. UV & Texel Density
            sec_uv = QtWidgets.QLabel("UV & TEXEL DENSITY (2048 MAP)")
            sec_uv.setObjectName("MayaSectionHeader")
            outer.addWidget(sec_uv)

            uv_row = QtWidgets.QHBoxLayout()
            uv_row.setSpacing(4)
            self.spn_td = QtWidgets.QDoubleSpinBox()
            self.spn_td.setRange(1.0, 8192.0)
            self.spn_td.setDecimals(1)
            self.spn_td.setSuffix(" px/m")
            self.spn_td.setValue(256.0)
            self.spn_td.setFixedHeight(22)
            uv_row.addWidget(self.spn_td, 1)

            for lbl, cb in (
                ("Get TD", self._on_get_td),
                ("Set TD", self._on_set_td),
                ("Unwrap+Pack", self._on_unwrap_pack),
            ):
                b = QtWidgets.QPushButton(lbl)
                b.setFixedHeight(22)
                b.clicked.connect(cb)
                uv_row.addWidget(b)
            outer.addLayout(uv_row)

            # 7. Scene Diagnostics & Non-Deformer History
            sec_diag = QtWidgets.QLabel("HISTORY & CLEANUP")
            sec_diag.setObjectName("MayaSectionHeader")
            outer.addWidget(sec_diag)

            hist_row = QtWidgets.QHBoxLayout()
            hist_row.setSpacing(4)
            for lbl, icn, cb in (
                ("Non-Deformer History", "non_def_history", self._on_non_def_history),
                ("Freeze", "freeze_transforms", self._on_freeze_guarded),
                ("Audit Scene", "scene_audit", self._on_run_diagnostics),
            ):
                b = QtWidgets.QPushButton(lbl)
                b.setIcon(icons.get_icon(icn, 14))
                b.setFixedHeight(23)
                b.clicked.connect(cb)
                hist_row.addWidget(b)
            outer.addLayout(hist_row)

            self.lbl_diag_status = QtWidgets.QLabel("Audit Scene checks topology without changing it.")
            self.lbl_diag_status.setStyleSheet(
                "background-color: #16181B; color: #9BA5B4; border: 1px solid #2C313A; "
                "border-radius: 3px; padding: 4px 6px; font-size: 10px;"
            )
            self.lbl_diag_status.setWordWrap(True)
            outer.addWidget(self.lbl_diag_status)

            outer.addStretch(1)
            self.refresh_from_scene()

        def _set_tool_setting(self, key, value):
            if getattr(self, "_syncing", False):
                return
            from . import tool_settings
            tool_settings.set_tool_setting(key, value)
            self.refresh_from_scene()

        def _run_menu(self, op_path, invoke=False, **props):
            from . import menus
            menus.run_op(op_path, invoke=invoke, **props)
            self.refresh_from_scene()

        def _add_modifier(self, kind):
            from . import menus
            result = menus._safe_call(lambda: menus._add_mod(kind), kind.title())
            self.refresh_from_scene()
            return result

        def _set_component_mode(self, mode_code: str):
            import bpy

            try:
                bpy.ops.landfall_studio.component_mode(mode=mode_code)
            except Exception:
                pass
            self.refresh_from_scene()

        def _on_make_live(self):
            result = modeling.set_live_surface(toggle=True)
            if not result.get("ok"):
                self.lbl_diag_status.setText(result.get("error", "Make Live could not finish."))
            self.refresh_from_scene()

        def _on_clear_live(self):
            modeling.clear_live_surface()
            self.refresh_from_scene()

        def _invoke_caddy(self, tool_type: str):
            if tool_type == "EXTRUDE":
                from ..modeling import caddy
                result = caddy.begin_maya_extrude()
            else:
                result = modeling.invoke_modeling_caddy(tool_type)
            if not result.get("ok"):
                self.lbl_diag_status.setText(result.get("error", "Select components for this tool."))
            self.refresh_from_scene()

        def _on_target_weld(self):
            modeling.activate_target_weld(merge_to_center=False)
            self.refresh_from_scene()

        def _on_quad_draw_activate(self):
            from . import menus
            menus.run_op("landfall_studio.quad_draw_modal", invoke=True)
            self.refresh_from_scene()

        def _on_qd_fill(self):
            modeling.fill_quad_from_dots()
            self.refresh_from_scene()

        def _on_qd_strip(self):
            modeling.extrude_quad_draw_strip()
            self.refresh_from_scene()

        def _on_qd_loop(self):
            modeling.insert_quad_draw_loop()
            self.refresh_from_scene()

        def _on_qd_relax(self):
            modeling.relax_quad_draw_verts()
            self.refresh_from_scene()

        def _on_get_td(self):
            res = modeling.get_mesh_texel_density(map_size=2048)
            if res.get("ok"):
                self.spn_td.setValue(float(res.get("texel_density", 256.0)))

        def _on_set_td(self):
            modeling.set_mesh_texel_density(float(self.spn_td.value()), map_size=2048)
            self.refresh_from_scene()

        def _on_unwrap_pack(self):
            res = modeling.uv_unwrap_and_pack()
            if res.get("ok") and res.get("texel_density_2k"):
                self.spn_td.setValue(float(res["texel_density_2k"]))
            self.refresh_from_scene()

        def _on_non_def_history(self):
            res = modeling.delete_non_deformer_history()
            if res.get("guarded"):
                self.lbl_diag_status.setText(f"GUARDED: {res.get('reason')}")
            elif res.get("ok"):
                self.lbl_diag_status.setText(
                    f"Non-Def History Baked: {len(res.get('applied_modeling_modifiers', []))} mod(s), "
                    f"preserved {len(res.get('preserved_deformers', []))} deformer(s)."
                )
            self.refresh_from_scene()

        def _on_freeze_guarded(self):
            res = modeling.freeze_transformations_guarded()
            if res.get("guarded"):
                self.lbl_diag_status.setText(f"GUARDED: {res.get('reason')}")
            elif res.get("ok"):
                self.lbl_diag_status.setText(f"Frozen Transforms on '{res.get('object_name')}'.")
            self.refresh_from_scene()

        def _on_run_diagnostics(self):
            rep = modeling.run_scene_diagnostics()
            issues = rep.get("mesh_issues", {})
            sheared = len(rep.get("non_orthogonal_objects", {}))
            hazards = len(rep.get("morph_rig_hazards", []))
            self.lbl_diag_status.setText(
                f"Audit ({rep.get('mesh_count', 0)} meshes) | NGons: {issues.get('ngons', 0)} | "
                f"Non-Manifold: {issues.get('nonmanifold', 0)} | Sheared: {sheared} | Rig/Morph: {hazards}"
            )

        def refresh_from_scene(self):
            from qtpy import QtWidgets

            # 1. Live Surface status
            live_st = modeling.get_live_surface_state()
            if live_st.get("active"):
                self.lbl_live_target.setText(f"LIVE: {live_st['object_name']}")
                self.lbl_live_target.setStyleSheet(
                    "background-color: #133326; color: #4ADE80; border: 1px solid #289E68; "
                    "border-radius: 3px; padding: 3px 6px; font-weight: 700;"
                )
            else:
                self.lbl_live_target.setText("Live Surface: Off")
                self.lbl_live_target.setStyleSheet(
                    "background-color: #16181B; color: #9BA5B4; border: 1px solid #30363F; "
                    "border-radius: 3px; padding: 3px 6px; font-weight: 600;"
                )

            # 2. Quad Draw dots
            qd_st = modeling.get_quad_draw_overlay_data()
            self.lbl_qd_dots.setText(f"Quad Draw: {qd_st['dot_count']} dots")

            from . import tool_settings
            snap = tool_settings.get_tool_settings_snapshot()
            self._syncing = True
            try:
                for box, value in ((self.chk_symmetry, snap["symmetry"]["x"]),
                                   (self.chk_soft, snap["soft_select_enabled"])):
                    if box.isChecked() != bool(value):
                        box.setChecked(bool(value))
            finally:
                self._syncing = False

            # 3. Active Caddy rows
            while self.caddy_form.rowCount() > 0:
                self.caddy_form.removeRow(0)

            c_st = modeling.get_active_caddy_state()
            if c_st.get("open"):
                self.lbl_caddy_header.setText(f"{c_st['node_title']} · {c_st['object_name']}")
                for row in c_st.get("rows", []):
                    lbl = QtWidgets.QLabel(str(row["label"]))
                    val = QtWidgets.QLabel(str(row["value"]))
                    val.setStyleSheet(
                        "background-color: #16181B; color: #54B8EE; border: 1px solid #2E343D; "
                        "border-radius: 2px; padding: 2px 6px; font-weight: 600;"
                    )
                    self.caddy_form.addRow(lbl, val)
            else:
                self.lbl_caddy_header.setText("Select components, then Extrude, Bevel, Bridge or Connect.")

    widget = MayaModelingToolkitWidget(parent)
    _active_mtk_widgets.append(widget)
    return widget


def get_modeling_toolkit_snapshot() -> Dict[str, Any]:
    """Return a diagnostic snapshot of the Modeling Toolkit panel and live modeling state."""
    w = _active_mtk_widgets[-1] if _active_mtk_widgets else None
    live_st = modeling.get_live_surface_state()
    caddy_st = modeling.get_active_caddy_state()
    qd_st = modeling.get_quad_draw_overlay_data()
    return {
        "ok": w is not None,
        "widget_count": len(_active_mtk_widgets),
        "live_label": str(w.lbl_live_target.text()) if w is not None else "",
        "quad_draw_dots_label": str(w.lbl_qd_dots.text()) if w is not None else "",
        "caddy_header_label": str(w.lbl_caddy_header.text()) if w is not None else "",
        "diag_status_label": str(w.lbl_diag_status.text()) if w is not None else "",
        "texel_density_spin": float(w.spn_td.value()) if w is not None else 0.0,
        "live_surface": live_st,
        "caddy": caddy_st,
        "quad_draw": qd_st,
    }

