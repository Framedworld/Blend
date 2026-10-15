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
   - Plotted dot counter + `Fill Quad (Shift)`, `Extrude Strip (Tab)`, `Loop Cut (Ctrl)`, `Relax (Shift-Drag)`, `Clear Dots`
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

            # 1. Selection Masks Bar
            sec_sel = QtWidgets.QLabel("SELECTION & SYMMETRY")
            sec_sel.setObjectName("MayaSectionHeader")
            outer.addWidget(sec_sel)

            mask_row = QtWidgets.QHBoxLayout()
            mask_row.setSpacing(3)
            for label, icon_name, mode_code in (
                ("Object", "mask_obj", "TOGGLE"),
                ("Vert", "mask_vert", "VERT"),
                ("Edge", "mask_edge", "EDGE"),
                ("Face", "mask_face", "FACE"),
                ("UV", "mask_uv", "UV"),
            ):
                btn = QtWidgets.QPushButton(label)
                btn.setIcon(icons.get_icon(icon_name, 14))
                btn.setFixedHeight(24)
                btn.clicked.connect(lambda _c=False, m=mode_code: self._set_component_mode(m))
                mask_row.addWidget(btn)
            outer.addLayout(mask_row)

            # 2. Transform Constraints & Scoped Make Live
            sec_live = QtWidgets.QLabel("TRANSFORM CONSTRAINTS  |  MAKE LIVE")
            sec_live.setObjectName("MayaSectionHeader")
            outer.addWidget(sec_live)

            live_row = QtWidgets.QHBoxLayout()
            live_row.setSpacing(4)
            self.lbl_live_target = QtWidgets.QLabel("Live Surface: Off")
            self.lbl_live_target.setStyleSheet(
                "background-color: #16181B; color: #9BA5B4; border: 1px solid #30363F; "
                "border-radius: 3px; padding: 3px 6px; font-weight: 600;"
            )
            live_row.addWidget(self.lbl_live_target, 1)

            btn_make_live = QtWidgets.QPushButton("Make Live")
            btn_make_live.setIcon(icons.get_icon("make_live", 14))
            btn_make_live.setFixedHeight(23)
            btn_make_live.clicked.connect(self._on_make_live)
            live_row.addWidget(btn_make_live)

            btn_clear_live = QtWidgets.QPushButton("Clear")
            btn_clear_live.setFixedHeight(23)
            btn_clear_live.clicked.connect(self._on_clear_live)
            live_row.addWidget(btn_clear_live)
            outer.addLayout(live_row)

            # 3. Mesh & Components Tool Grid (Caddy-Enabled)
            sec_tools = QtWidgets.QLabel("COMPONENTS & TOOLS  (IN-VIEWPORT CADDY)")
            sec_tools.setObjectName("MayaSectionHeader")
            outer.addWidget(sec_tools)

            grid = QtWidgets.QGridLayout()
            grid.setHorizontalSpacing(4)
            grid.setVerticalSpacing(4)

            tool_buttons = [
                ("Extrude", "extrude", lambda: self._invoke_caddy("EXTRUDE")),
                ("Bevel", "bevel", lambda: self._invoke_caddy("BEVEL")),
                ("Bridge", "bridge", lambda: self._invoke_caddy("BRIDGE")),
                ("Connect", "connect", lambda: self._invoke_caddy("CONNECT")),
                ("Target Weld", "target_weld", self._on_target_weld),
                ("Quad Draw", "quad_draw", self._on_quad_draw_activate),
            ]
            for idx, (lbl, icn, cb) in enumerate(tool_buttons):
                btn = QtWidgets.QPushButton(lbl)
                btn.setIcon(icons.get_icon(icn, 16))
                btn.setFixedHeight(26)
                btn.clicked.connect(cb)
                grid.addWidget(btn, idx // 2, idx % 2)
            outer.addLayout(grid)

            # 4. Live Caddy Inspector
            self.lbl_caddy_header = QtWidgets.QLabel("ACTIVE CADDY: None")
            self.lbl_caddy_header.setObjectName("MayaSectionHeader")
            outer.addWidget(self.lbl_caddy_header)

            self.caddy_form_host = QtWidgets.QWidget()
            self.caddy_form = QtWidgets.QFormLayout(self.caddy_form_host)
            self.caddy_form.setContentsMargins(4, 2, 4, 2)
            self.caddy_form.setSpacing(3)
            outer.addWidget(self.caddy_form_host)

            # 5. Quad Draw Retopology Chord Strip
            sec_qd = QtWidgets.QLabel("QUAD DRAW RETOPOLOGY")
            sec_qd.setObjectName("MayaSectionHeader")
            outer.addWidget(sec_qd)

            qd_row1 = QtWidgets.QHBoxLayout()
            qd_row1.setSpacing(3)
            self.lbl_qd_dots = QtWidgets.QLabel("Dots: 0")
            self.lbl_qd_dots.setStyleSheet("color: #4ADE80; font-weight: 700; padding: 0 4px;")
            qd_row1.addWidget(self.lbl_qd_dots)

            for lbl, cb in (
                ("Fill [Shift]", self._on_qd_fill),
                ("Strip [Tab]", self._on_qd_strip),
                ("Loop [Ctrl]", self._on_qd_loop),
                ("Relax", self._on_qd_relax),
            ):
                b = QtWidgets.QPushButton(lbl)
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
            sec_diag = QtWidgets.QLabel("SCENE DIAGNOSTICS & HISTORY")
            sec_diag.setObjectName("MayaSectionHeader")
            outer.addWidget(sec_diag)

            hist_row = QtWidgets.QHBoxLayout()
            hist_row.setSpacing(4)
            for lbl, icn, cb in (
                ("Non-Def Hist", "non_def_history", self._on_non_def_history),
                ("Freeze", "freeze_transforms", self._on_freeze_guarded),
                ("Audit Scene", "scene_audit", self._on_run_diagnostics),
            ):
                b = QtWidgets.QPushButton(lbl)
                b.setIcon(icons.get_icon(icn, 14))
                b.setFixedHeight(23)
                b.clicked.connect(cb)
                hist_row.addWidget(b)
            outer.addLayout(hist_row)

            self.lbl_diag_status = QtWidgets.QLabel("Diagnostics: Ready (Read-Only)")
            self.lbl_diag_status.setStyleSheet(
                "background-color: #16181B; color: #9BA5B4; border: 1px solid #2C313A; "
                "border-radius: 3px; padding: 4px 6px; font-size: 10px;"
            )
            self.lbl_diag_status.setWordWrap(True)
            outer.addWidget(self.lbl_diag_status)

            outer.addStretch(1)
            self.refresh_from_scene()

        def _set_component_mode(self, mode_code: str):
            import bpy

            try:
                bpy.ops.landfall_studio.component_mode(mode=mode_code)
            except Exception:
                pass
            self.refresh_from_scene()

        def _on_make_live(self):
            modeling.set_live_surface(toggle=True)
            self.refresh_from_scene()

        def _on_clear_live(self):
            modeling.clear_live_surface()
            self.refresh_from_scene()

        def _invoke_caddy(self, tool_type: str):
            modeling.invoke_modeling_caddy(tool_type)
            self.refresh_from_scene()

        def _on_target_weld(self):
            modeling.activate_target_weld(merge_to_center=False)
            self.refresh_from_scene()

        def _on_quad_draw_activate(self):
            modeling.set_quad_draw_active(True)
            modeling.ensure_retopo_mesh()
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
            self.lbl_qd_dots.setText(f"Dots: {qd_st['dot_count']}")

            # 3. Active Caddy rows
            while self.caddy_form.rowCount() > 0:
                self.caddy_form.removeRow(0)

            c_st = modeling.get_active_caddy_state()
            if c_st.get("open"):
                self.lbl_caddy_header.setText(
                    f"ACTIVE CADDY: {c_st['node_title']}  ({c_st['object_name']})"
                )
                for row in c_st.get("rows", []):
                    lbl = QtWidgets.QLabel(str(row["label"]))
                    val = QtWidgets.QLabel(str(row["value"]))
                    val.setStyleSheet(
                        "background-color: #16181B; color: #54B8EE; border: 1px solid #2E343D; "
                        "border-radius: 2px; padding: 2px 6px; font-weight: 600;"
                    )
                    self.caddy_form.addRow(lbl, val)
            else:
                self.lbl_caddy_header.setText("ACTIVE CADDY: None (Select Extrude / Bevel / Bridge / Connect)")

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

