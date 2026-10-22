"""Docked Maya `.ma`/`.mb` Interchange, Reference Editor & Loss Report Inspector (`landfall_studio.ui.interchange_panel`).

Provides the `MAYA_INTERCHANGE` tab inside `RightAreaQtDock`:
1. **Maya Bridge & `.ma`/`.mb` Scene Exchange:**
   - Displays discovered local Maya runtime (`Maya 2024 • mayapy.exe`).
   - File path selector + Carrier (`FBX` / `USD`) + Rig Mode (`Auto SmartBake` / `Always Bake` / `Raw` / `RigGraph`).
   - Action buttons: `Preflight .ma/.mb`, `Import .ma/.mb`, `Save As .ma/.mb`, `Send to Maya`, and `Open Full Bridge`.
2. **Maya Reference Editor (`.blend`, `.ma`, `.mb`, `.fbx`, `.usd`):**
   - Table of linked references (`FILE | MODE (N/R/T) | OBJS | SOURCE`) with clickable `Normal / Reference / Template` cycle, `Reference Scene`, `Reload`, `Remove`, `Unlink & Import (Approved)`, and `Open Workspace Reference Mgr`.
3. **Live Interchange Preflight & Mandatory Loss Report:**
   - Displays `STATUS` badge (`PASS`, `PASS_WITH_LIMITATIONS`, `PARTIAL`, `BLOCKED`), `Source SHA-256 Unchanged` verification badge, and a detailed tree/log of hierarchy, skinning, morphs, materials, UVs, and baked/unsupported Maya DG nodes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .. import interchange
from . import style

_interchange_widgets: List[Any] = []


def get_interchange_ui_snapshot() -> Dict[str, Any]:
    """Return a structured snapshot of the Maya Interchange & Reference Editor state for tests and UI sync."""
    runtime = interchange.get_maya_runtime_status()
    refs = interchange.list_scene_references()
    last_rep = interchange.get_last_interchange_report()
    return {
        "ok": True,
        "runtime": runtime,
        "references": refs,
        "reference_count": len(refs),
        "ref_row_count": len(refs),
        "last_report": last_rep,
    }


def create_interchange_widget() -> Any:
    """Create the docked Maya Interchange & Reference Editor Qt widget."""
    from qtpy import QtCore, QtGui, QtWidgets

    class _MayaInterchangeWidget(QtWidgets.QFrame):
        def __init__(self):
            super().__init__()
            self.setObjectName("MayaPanelRoot")
            style.apply_studio_style(self)
            self._updating = False
            self._build_ui()
            if self not in _interchange_widgets:
                _interchange_widgets.append(self)
            self.refresh_from_scene()

        def _build_ui(self) -> None:
            vlay = QtWidgets.QVBoxLayout(self)
            vlay.setContentsMargins(0, 0, 0, 0)
            vlay.setSpacing(0)

            # Top Panel Header (matching Figma Make `.panel-head`)
            head = QtWidgets.QFrame()
            head.setObjectName("MayaSectionHeader")
            head.setFixedHeight(29)
            hlay = QtWidgets.QHBoxLayout(head)
            hlay.setContentsMargins(10, 0, 8, 0)
            lbl_title = QtWidgets.QLabel("MAYA INTERCHANGE & REFERENCES")
            lbl_title.setObjectName("MayaSectionTitle")
            self.lbl_runtime_badge = QtWidgets.QLabel("Maya 2024")
            self.lbl_runtime_badge.setObjectName("MayaBadgeGreen")
            hlay.addWidget(lbl_title)
            hlay.addStretch(1)
            hlay.addWidget(self.lbl_runtime_badge)
            vlay.addWidget(head)

            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
            body = QtWidgets.QWidget()
            blay = QtWidgets.QVBoxLayout(body)
            blay.setContentsMargins(8, 8, 8, 8)
            blay.setSpacing(8)

            # --- Section 1: Maya .ma / .mb Scene Exchange ---
            sec1 = QtWidgets.QFrame()
            sec1.setObjectName("MayaSectionHeader")
            s1_lay = QtWidgets.QHBoxLayout(sec1)
            s1_lay.setContentsMargins(6, 3, 6, 3)
            s1_lbl = QtWidgets.QLabel("▾  MAYA SCENE (.MA / .MB) BRIDGE")
            s1_lbl.setObjectName("MayaSectionTitle")
            s1_lay.addWidget(s1_lbl)
            blay.addWidget(sec1)

            path_row = QtWidgets.QHBoxLayout()
            path_row.setSpacing(4)
            self.txt_ma_path = QtWidgets.QLineEdit()
            self.txt_ma_path.setPlaceholderText("Import source .ma / .mb scene file...")
            btn_browse = QtWidgets.QPushButton("…")
            btn_browse.setFixedWidth(26)
            btn_browse.setToolTip("Browse for source .ma or .mb file to import")
            btn_browse.clicked.connect(self._on_browse_ma)
            path_row.addWidget(self.txt_ma_path, 1)
            path_row.addWidget(btn_browse)
            blay.addLayout(path_row)

            save_row = QtWidgets.QHBoxLayout()
            save_row.setSpacing(4)
            self.txt_save_ma_path = QtWidgets.QLineEdit()
            self.txt_save_ma_path.setPlaceholderText("Export / Save As .ma destination path...")
            btn_browse_save = QtWidgets.QPushButton("…")
            btn_browse_save.setFixedWidth(26)
            btn_browse_save.setToolTip("Browse for destination .ma or .mb file to save")
            btn_browse_save.clicked.connect(self._on_browse_save_ma)
            save_row.addWidget(self.txt_save_ma_path, 1)
            save_row.addWidget(btn_browse_save)
            blay.addLayout(save_row)

            opts_row = QtWidgets.QHBoxLayout()
            opts_row.setSpacing(4)
            lbl_c = QtWidgets.QLabel("Carrier:")
            lbl_c.setObjectName("MayaMutedLabel")
            self.cmb_carrier = QtWidgets.QComboBox()
            self.cmb_carrier.addItems(["fbx", "usd"])
            lbl_r = QtWidgets.QLabel("Rig:")
            lbl_r.setObjectName("MayaMutedLabel")
            self.cmb_rig_mode = QtWidgets.QComboBox()
            self.cmb_rig_mode.addItems(["auto", "bake", "raw", "rig"])
            opts_row.addWidget(lbl_c)
            opts_row.addWidget(self.cmb_carrier, 1)
            opts_row.addWidget(lbl_r)
            opts_row.addWidget(self.cmb_rig_mode, 1)
            blay.addLayout(opts_row)

            grid_btns = QtWidgets.QGridLayout()
            grid_btns.setSpacing(4)
            self.btn_preflight = QtWidgets.QPushButton("Preflight .ma")
            self.btn_import_ma = QtWidgets.QPushButton("Import .ma / .mb")
            self.btn_save_ma = QtWidgets.QPushButton("Save As .ma")
            self.btn_send_maya = QtWidgets.QPushButton("Send to Maya")
            self.btn_preflight.clicked.connect(self._on_preflight_clicked)
            self.btn_import_ma.clicked.connect(self._on_import_clicked)
            self.btn_save_ma.clicked.connect(self._on_save_clicked)
            self.btn_send_maya.clicked.connect(self._on_send_clicked)
            grid_btns.addWidget(self.btn_preflight, 0, 0)
            grid_btns.addWidget(self.btn_import_ma, 0, 1)
            grid_btns.addWidget(self.btn_save_ma, 1, 0)
            grid_btns.addWidget(self.btn_send_maya, 1, 1)
            blay.addLayout(grid_btns)

            # --- Section 2: Reference Editor ---
            sec2 = QtWidgets.QFrame()
            sec2.setObjectName("MayaSectionHeader")
            s2_lay = QtWidgets.QHBoxLayout(sec2)
            s2_lay.setContentsMargins(6, 3, 6, 3)
            s2_lbl = QtWidgets.QLabel("▾  REFERENCE EDITOR (.BLEND / .MA / .USD)")
            s2_lbl.setObjectName("MayaSectionTitle")
            btn_open_rm = QtWidgets.QPushButton("Full Ref Mgr")
            btn_open_rm.setFixedHeight(18)
            btn_open_rm.clicked.connect(self._on_open_full_ref_mgr)
            s2_lay.addWidget(s2_lbl)
            s2_lay.addStretch(1)
            s2_lay.addWidget(btn_open_rm)
            blay.addWidget(sec2)

            self.tbl_refs = QtWidgets.QTableWidget(0, 3)
            self.tbl_refs.setHorizontalHeaderLabels(["REFERENCE", "MODE", "OBJS"])
            self.tbl_refs.horizontalHeader().setStretchLastSection(False)
            self.tbl_refs.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            self.tbl_refs.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
            self.tbl_refs.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
            self.tbl_refs.setColumnWidth(1, 56)
            self.tbl_refs.setColumnWidth(2, 42)
            self.tbl_refs.verticalHeader().setVisible(False)
            self.tbl_refs.setFixedHeight(105)
            self.tbl_refs.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.tbl_refs.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.tbl_refs.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            blay.addWidget(self.tbl_refs)

            ref_btns = QtWidgets.QHBoxLayout()
            ref_btns.setSpacing(4)
            btn_ref_add = QtWidgets.QPushButton("+ Reference")
            btn_ref_mode = QtWidgets.QPushButton("Cycle N/R/T")
            btn_ref_reload = QtWidgets.QPushButton("Reload")
            btn_ref_remove = QtWidgets.QPushButton("Remove")
            self.btn_ref_mode,self.btn_ref_reload,self.btn_ref_remove=btn_ref_mode,btn_ref_reload,btn_ref_remove
            btn_ref_add.clicked.connect(self._on_reference_add)
            btn_ref_mode.clicked.connect(self._on_reference_cycle_mode)
            btn_ref_reload.clicked.connect(self._on_reference_reload)
            btn_ref_remove.clicked.connect(self._on_reference_remove)
            ref_btns.addWidget(btn_ref_add)
            ref_btns.addWidget(btn_ref_mode)
            ref_btns.addWidget(btn_ref_reload)
            ref_btns.addWidget(btn_ref_remove)
            blay.addLayout(ref_btns)
            self.tbl_refs.itemSelectionChanged.connect(self._sync_reference_actions)

            # --- Section 3: Mandatory Preflight & Loss Report ---
            sec3 = QtWidgets.QFrame()
            sec3.setObjectName("MayaSectionHeader")
            s3_lay = QtWidgets.QHBoxLayout(sec3)
            s3_lay.setContentsMargins(6, 3, 6, 3)
            s3_lbl = QtWidgets.QLabel("▾  INTERCHANGE PREFLIGHT & LOSS REPORT")
            s3_lbl.setObjectName("MayaSectionTitle")
            self.lbl_status_pill = QtWidgets.QLabel("READY")
            self.lbl_status_pill.setObjectName("MayaBadgeTeal")
            s3_lay.addWidget(s3_lbl)
            s3_lay.addStretch(1)
            s3_lay.addWidget(self.lbl_status_pill)
            blay.addWidget(sec3)

            self.txt_report = QtWidgets.QPlainTextEdit()
            self.txt_report.setReadOnly(True)
            self.txt_report.setFixedHeight(155)
            self.txt_report.setStyleSheet(
                "background-color: #141619; color: #C9CDD3; border: 1px solid #2E333B; "
                "font-family: Consolas, 'SFMono-Regular', monospace; font-size: 10px;"
            )
            blay.addWidget(self.txt_report)

            blay.addStretch(1)
            scroll.setWidget(body)
            vlay.addWidget(scroll, 1)

        def _default_export_path_from_import(self, import_path: str) -> str:
            import os
            if not import_path:
                return ""
            base, ext = os.path.splitext(import_path)
            if ext.lower() not in (".ma", ".mb"):
                ext = ".ma"
            return f"{base}_export{ext}"

        def _on_browse_ma(self) -> None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Select Maya Scene or Reference",
                "",
                "Maya & DCC Scenes (*.ma *.mb *.blend *.fbx *.usd *.usda *.usdc)",
            )
            if path:
                self.txt_ma_path.setText(path)
                if not self.txt_save_ma_path.text().strip():
                    self.txt_save_ma_path.setText(self._default_export_path_from_import(path))

        def _on_browse_save_ma(self) -> None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save As Maya Scene (.ma / .mb)",
                self.txt_save_ma_path.text().strip() or self._default_export_path_from_import(self.txt_ma_path.text().strip()),
                "Maya Scenes (*.ma *.mb)",
            )
            if path:
                self.txt_save_ma_path.setText(path)

        def _on_preflight_clicked(self) -> None:
            p = self.txt_ma_path.text().strip()
            if not p:
                return self._render_report_text({'ok':False,'error':'Choose a Maya source file first.'})
            pf = interchange.preflight_maya_scene(p)
            self._render_report_text(pf)

        def _on_import_clicked(self) -> None:
            p = self.txt_ma_path.text().strip()
            if not p:
                return self._render_report_text({'ok':False,'error':'Choose a Maya source file first.'})
            if not self.txt_save_ma_path.text().strip():
                self.txt_save_ma_path.setText(self._default_export_path_from_import(p))
            rep = interchange.import_maya_scene(
                p,
                via=self.cmb_carrier.currentText(),
                rig_mode=self.cmb_rig_mode.currentText(),
            )
            self.refresh_from_scene()
            self._render_report_text(rep)

        def _on_save_clicked(self) -> None:
            src_p = self.txt_ma_path.text().strip()
            dst_p = self.txt_save_ma_path.text().strip()
            if not dst_p:
                if src_p:
                    dst_p = self._default_export_path_from_import(src_p)
                    self.txt_save_ma_path.setText(dst_p)
                else:
                    return self._render_report_text({'ok':False,'error':'Choose a destination file first.'})
            from pathlib import Path
            destination=Path(dst_p).expanduser()
            if destination.suffix.lower() not in ('.ma','.mb'):destination=destination.with_suffix('.ma')
            dst_p=str(destination)
            if destination.is_file():
                answer=QtWidgets.QMessageBox.question(self,'Replace Maya scene?',f'Replace the existing file?\n{destination}',QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No,QtWidgets.QMessageBox.No)
                if answer!=QtWidgets.QMessageBox.Yes:return
            rep = interchange.save_as_maya_scene(
                dst_p,
                carrier=self.cmb_carrier.currentText(),
                protected_source_path=src_p or None,
                allow_overwrite_source=False,
            )
            self.refresh_from_scene()
            self._render_report_text(rep)

        def _on_send_clicked(self) -> None:
            rep = interchange.send_to_maya(
                carrier=self.cmb_carrier.currentText(),
                dry_run=False,
            )
            self._render_report_text(rep)

        def _on_open_full_ref_mgr(self) -> None:
            from . import desktop

            desktop.open_panel("reference_manager", docked=False)

        def _selected_ref_name(self) -> str:
            row = self.tbl_refs.currentRow()
            if row < 0:
                return ""
            item = self.tbl_refs.item(row, 0)
            return item.text() if item else ""

        def _on_reference_add(self) -> None:
            p = self.txt_ma_path.text().strip()
            if not p:
                p,_=QtWidgets.QFileDialog.getOpenFileName(self,'Reference scene','','Scene files (*.blend *.ma *.mb *.usd *.usda *.usdc);;All files (*)')
                if not p:return
            res = interchange.reference_scene(p)
            self.refresh_from_scene()
            self._render_report_text(res)

        def _on_reference_cycle_mode(self) -> None:
            name = self._selected_ref_name()
            if not name:
                return
            refs = {r["name"]: r for r in interchange.list_scene_references()}
            cur = refs.get(name, {}).get("display_mode", "off")
            nxt = {"off": "reference", "reference": "template", "template": "off"}.get(cur, "off")
            result=interchange.set_reference_mode(name, nxt)
            self.refresh_from_scene()
            self._render_report_text(result)

        def _on_reference_reload(self) -> None:
            name = self._selected_ref_name()
            if name:
                result=interchange.reload_reference_scene(name)
                self.refresh_from_scene()
                self._render_report_text(result)

        def _on_reference_remove(self) -> None:
            name = self._selected_ref_name()
            if name:
                result=interchange.remove_reference_scene(name)
                self.refresh_from_scene()
                self._render_report_text(result)

        def _sync_reference_actions(self):
            selected=bool(self._selected_ref_name())
            for button in (self.btn_ref_mode,self.btn_ref_reload,self.btn_ref_remove):
                button.setEnabled(selected)
                button.setToolTip('' if selected else 'Select a reference row first.')

        def _render_report_text(self, rep: Dict[str, Any], publish=True) -> None:
            if not rep:
                return
            self._shown_report=rep
            failed=not rep.get('ok',True) or bool(rep.get('error'))
            st = rep.get("status", "ERROR" if failed else "READY")
            self.lbl_status_pill.setText(st)
            from . import desktop
            if publish:desktop.set_command_feedback('Interchange',rep.get('error') or st,'ERROR' if failed else 'INFO')
            lines = [
                f"STATUS: {st} | Source Unchanged: {rep.get('source_unchanged', 'Not measured')}",
                f"Source: {rep.get('source_path', '-')}",
            ]
            if "hierarchy_and_geometry" in rep:
                hg = rep["hierarchy_and_geometry"]
                sk = rep.get("skinning_and_joints", {})
                ma = rep.get("morphs_and_animation", {})
                um = rep.get("uvs_and_materials", {})
                lines.append(
                    f"Objects: {hg.get('object_count', 0)} | Meshes: {hg.get('mesh_count', 0)} "
                    f"({hg.get('total_vertices', 0)}v / {hg.get('total_faces', 0)}f)"
                )
                lines.append(
                    f"Bones: {sk.get('total_bones', 0)} | Skinned Verts: {sk.get('total_weighted_vertices', 0)} | "
                    f"Shape Targets: {ma.get('total_shape_targets', 0)}"
                )
                lines.append(
                    f"UV Sets: {um.get('uv_set_count', 0)} | Materials: {um.get('material_count', 0)} | "
                    f"Anim Keys: {ma.get('total_animation_keyframes', 0)}"
                )
            elif "summary" in rep:
                sm = rep["summary"]
                lines.append(
                    f"Preflight: Transforms={sm.get('transforms', 0)} Meshes={sm.get('meshes', 0)} "
                    f"Joints={sm.get('joints', 0)} Skin={sm.get('skin_clusters', 0)} Morphs={sm.get('blend_shapes', 0)}"
                )

            for b in rep.get("baked_or_approximated", rep.get("baked_or_approximated_items", [])):
                lines.append(f"[BAKED] {b}")
            for lim in rep.get("limitations_and_unsupported", rep.get("unsupported_or_lost_items", [])):
                lines.append(f"[LIMITATION] {lim}")
            if rep.get("error"):
                lines.append(f"[ERROR] {rep['error']}")

            self.txt_report.setPlainText("\n".join(lines))

        def refresh_from_scene(self) -> None:
            if self._updating:
                return
            self._updating = True
            try:
                snap = get_interchange_ui_snapshot()
                rt = snap["runtime"]
                if rt.get("available"):
                    self.lbl_runtime_badge.setText(f"Maya {rt.get('maya_version') or ''} • Detected")
                    self.lbl_runtime_badge.setToolTip('Runtime found. Conversion still requires Maya to initialize successfully; inspect the operation report.')
                    self.lbl_runtime_badge.setObjectName("MayaBadgeAmber")
                else:
                    self.lbl_runtime_badge.setText("Maya Missing (BLOCKED)")
                    self.lbl_runtime_badge.setObjectName("MayaBadgeAmber")

                refs = snap["references"]
                selected=self._selected_ref_name()
                self.tbl_refs.setRowCount(len(refs))
                for idx, r in enumerate(refs):
                    it_name = QtWidgets.QTableWidgetItem(r["name"])
                    it_name.setToolTip(str(r.get('filepath') or r.get('path') or r.get('source_path') or '')+('' if r.get('exists',True) else '\nMissing file — use File > Find Missing Files.'))
                    mode_lbl = {"off": "Normal (N)", "reference": "Ref (R)", "template": "Tmpl (T)"}.get(
                        r["display_mode"], r["display_mode"]
                    )
                    it_mode = QtWidgets.QTableWidgetItem(mode_lbl)
                    it_objs = QtWidgets.QTableWidgetItem(str(r["object_count"]))
                    self.tbl_refs.setItem(idx, 0, it_name)
                    self.tbl_refs.setItem(idx, 1, it_mode)
                    self.tbl_refs.setItem(idx, 2, it_objs)
                    if r['name']==selected:self.tbl_refs.selectRow(idx)
                self._sync_reference_actions()

                latest=getattr(self,'_shown_report',None) or snap['last_report']
                if latest:
                    self._render_report_text(latest,publish=False)
                elif not self.txt_report.toPlainText():
                    self.txt_report.setPlainText(
                        f"Maya Runtime: {rt.get('mayapy_exe') or 'Not Found'}\n"
                        "Conversion requires a working Maya runtime. Operations report conversion failures here."
                    )
            finally:
                self._updating = False

    # A Qt signal must never leave a stale PASS visible after a caught file or
    # converter error. Keep the existing actions/dispatcher; normalize feedback.
    def guarded_action(method):
        def call(self,*_args):
            try:return method(self)
            except Exception as exc:
                return self._render_report_text({'ok':False,'status':'ERROR','error':str(exc)})
        return call
    for name in ('_on_preflight_clicked','_on_import_clicked','_on_save_clicked','_on_send_clicked','_on_reference_add','_on_reference_cycle_mode','_on_reference_reload','_on_reference_remove'):
        setattr(_MayaInterchangeWidget,name,guarded_action(getattr(_MayaInterchangeWidget,name)))
    return _MayaInterchangeWidget()


def refresh_interchange_widgets() -> None:
    for w in list(_interchange_widgets):
        try:
            w.refresh_from_scene()
        except Exception:
            pass
