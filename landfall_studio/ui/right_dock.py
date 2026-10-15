"""Right-hand `QtDock` subclass (`RightAreaQtDock`) hosting the Unified Maya Right Sidebar (`Channel Box / Layer Editor`, `Attribute Editor`, `Tool Settings`).

Extends `blendertk.ui_utils.qt_dock.QtDock` so the right side of the Blender main window
embeds a frameless Modern Maya right-dock container (`WS_CHILD`) with instant tab switching:
- `CHANNEL_BOX`: Upstream `Channels` (`tbl000`) + `SHAPES` + Parametric/Modifier `INPUTS` + `Display Layer Editor`
- `ATTRIBUTE_EDITOR`: Maya-style tabbed `Attribute Editor` (`Transform`, `Shape`, `Shader`, `Maya↔Blender Map`)
- `TOOL_SETTINGS`: Unified `Tool Settings` & Option Box (`□`) inspector
- `NATIVE_PROPERTIES`: Suspends the `WS_CHILD` overlay to expose Blender's native `PROPERTIES` editor in-place
- `FLOATING` / `HIDDEN`: Undocks to floating window or hides cleanly with zero duplicate Blender areas.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from . import (
    attribute_editor,
    channel_box_ext,
    hypershade_panel,
    interchange_panel,
    modeling_toolkit,
    shape_editor,
    style,
    tool_settings,
)


def _create_rotated_edge_tab(
    text: str,
    mode_key: str,
    on_click: Callable[[str], None],
    height: int = 114,
):
    """Create a Figma Make 26px-wide vertical rotated (-90 deg) edge tab button with a right-edge active bar."""
    from qtpy import QtCore, QtGui, QtWidgets

    class _MayaRotatedEdgeTab(QtWidgets.QPushButton):
        def __init__(self) -> None:
            super().__init__(text)
            self.mode_key = mode_key
            self._hovered = False
            self.setCheckable(True)
            self.setFixedSize(26, height)
            self.setCursor(QtCore.Qt.PointingHandCursor)
            self.setToolTip(f"{text} ({mode_key})")
            self.clicked.connect(lambda: on_click(mode_key))

        def enterEvent(self, event) -> None:
            self._hovered = True
            self.update()
            super().enterEvent(event)

        def leaveEvent(self, event) -> None:
            self._hovered = False
            self.update()
            super().leaveEvent(event)

        def paintEvent(self, _event) -> None:
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)
            w, h = self.width(), self.height()
            active = self.isChecked()

            bg = (
                QtGui.QColor("#22252A")
                if active
                else (QtGui.QColor("#22262C") if self._hovered else QtGui.QColor("#1B1E22"))
            )
            p.fillRect(0, 0, w, h, bg)

            # Bottom separator line
            p.setPen(QtGui.QColor("#2A2E35"))
            p.drawLine(0, h - 1, w, h - 1)
            # Right border line
            p.drawLine(w - 1, 0, w - 1, h)

            if active:
                p.fillRect(w - 2, 0, 2, h, QtGui.QColor("#38A3D8"))

            p.save()
            p.translate(w / 2.0, h / 2.0)
            p.rotate(-90.0)
            f = p.font()
            f.setPixelSize(9)
            f.setBold(True)
            f.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 0.8)
            p.setFont(f)
            p.setPen(
                QtGui.QColor("#E6EDF3")
                if active
                else (QtGui.QColor("#C8D1DC") if self._hovered else QtGui.QColor("#7D8590"))
            )
            text_rect = QtCore.QRectF(-h / 2.0 + 4.0, -w / 2.0, h - 8.0, w)
            p.drawText(text_rect, QtCore.Qt.AlignCenter, text)
            p.restore()
            p.end()

    return _MayaRotatedEdgeTab()


PANEL_TITLES = {
    "CHANNEL_BOX": "CHANNEL BOX / LAYER EDITOR",
    "MODELING_TOOLKIT": "MAYA MODELING TOOLKIT",
    "HYPERSHADE": "HYPERSHADE • MATERIAL BROWSER",
    "SHAPE_EDITOR": "SHAPE & SKIN WEIGHT EDITOR",
    "MAYA_INTERCHANGE": "MAYA .MA / .MB REFERENCE",
    "ATTRIBUTE_EDITOR": "ATTRIBUTE EDITOR",
    "TOOL_SETTINGS": "TOOL SETTINGS • OPTION BOX",
}

WORKSPACE_SPINE_TABS = {
    "Modeling Standard": ("CHANNEL_BOX", "MODELING_TOOLKIT", "ATTRIBUTE_EDITOR", "TOOL_SETTINGS"),
    "Maya Classic": ("CHANNEL_BOX", "MODELING_TOOLKIT", "ATTRIBUTE_EDITOR"),
    "Lookdev / Hypershade": ("HYPERSHADE", "ATTRIBUTE_EDITOR", "CHANNEL_BOX"),
    "FX & Geometry Nodes": ("CHANNEL_BOX", "ATTRIBUTE_EDITOR", "MODELING_TOOLKIT"),
    "Rigging & Deform": ("SHAPE_EDITOR", "CHANNEL_BOX", "ATTRIBUTE_EDITOR"),
    "Sculpt & Remesh Studio": ("TOOL_SETTINGS", "MODELING_TOOLKIT", "CHANNEL_BOX"),
    "Pipeline & .ma": ("MAYA_INTERCHANGE", "CHANNEL_BOX", "ATTRIBUTE_EDITOR"),
}

_tear_off_windows: dict[str, Any] = {}


def _create_tear_off_panel_widget(mode: str) -> Any:
    """Create a standalone instance of an editor widget for a floating Maya Tear-Off window."""
    m = (mode or "TOOL_SETTINGS").upper()
    if m == "HYPERSHADE":
        w = hypershade_panel.create_hypershade_widget()
        w.refresh_from_scene()
        return w
    if m == "SHAPE_EDITOR":
        w = shape_editor.create_shape_editor_widget()
        w.refresh_from_scene()
        return w
    if m == "MAYA_INTERCHANGE":
        w = interchange_panel.create_interchange_widget()
        w.refresh_from_scene()
        return w
    if m == "MODELING_TOOLKIT":
        w = modeling_toolkit.create_modeling_toolkit_widget()
        w.refresh_from_scene()
        return w
    if m == "ATTRIBUTE_EDITOR":
        ctrl = attribute_editor.MayaAttributeEditorWidget()
        ctrl.refresh()
        ctrl.widget._lf_ctrl = ctrl
        return ctrl.widget
    ctrl = tool_settings.MayaToolSettingsWidget()
    ctrl.refresh()
    ctrl.widget._lf_ctrl = ctrl
    return ctrl.widget


def tear_off_panel(mode: str, x: int = 240, y: int = 135, width: int = 380, height: int = 540) -> dict[str, Any]:
    """Undock/tear off `mode` into a standalone floating Maya Tear-Off window with a `[↙ Dock to Sidebar]` header."""
    from qtpy import QtCore, QtWidgets
    import blendertk as btk
    from blendertk.ui_utils.blender_window import BlenderWindow
    from . import desktop

    desktop.ensure_ui_handler()
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    m = (mode or "TOOL_SETTINGS").upper()
    title = PANEL_TITLES.get(m, m)

    if m in _tear_off_windows and _tear_off_windows[m] is not None:
        win = _tear_off_windows[m]
        try:
            win.show()
            win.raise_()
            return {"ok": True, "mode": m, "title": title, "floating": True, "reused": True}
        except Exception:
            _tear_off_windows.pop(m, None)

    win = QtWidgets.QFrame(None, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
    win.setObjectName("MayaTearOffWindow")
    style.apply_studio_style(win)
    win.setStyleSheet(
        win.styleSheet()
        + "\nQFrame#MayaTearOffWindow { background-color: #1E2126; border: 1px solid #38A3D8; border-radius: 3px; }"
    )

    vlay = QtWidgets.QVBoxLayout(win)
    vlay.setContentsMargins(1, 1, 1, 1)
    vlay.setSpacing(0)

    hdr = QtWidgets.QFrame()
    hdr.setObjectName("MayaStatusLine")
    hdr.setFixedHeight(26)
    hlay = QtWidgets.QHBoxLayout(hdr)
    hlay.setContentsMargins(8, 2, 6, 2)
    hlay.setSpacing(6)

    lbl_grip = QtWidgets.QLabel("⋮⋮")
    lbl_grip.setStyleSheet("color: #38A3D8; font-weight: 700; font-size: 11px; background: transparent;")
    hlay.addWidget(lbl_grip)

    lbl_title = QtWidgets.QLabel(f"TEAR-OFF • {title}")
    lbl_title.setStyleSheet("color: #E6EDF3; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; background: transparent;")
    hlay.addWidget(lbl_title)
    hlay.addStretch(1)

    btn_redock = QtWidgets.QPushButton("↙ Dock")
    btn_redock.setFixedHeight(19)
    btn_redock.setToolTip("Snap this torn-off editor back into the Right Sidebar Dock")
    btn_redock.clicked.connect(lambda: redock_panel(m))
    hlay.addWidget(btn_redock)

    btn_close = QtWidgets.QPushButton("✕")
    btn_close.setFixedSize(20, 19)
    btn_close.clicked.connect(lambda: close_tear_off_panel(m))
    hlay.addWidget(btn_close)

    vlay.addWidget(hdr)

    content = _create_tear_off_panel_widget(m)
    vlay.addWidget(content, 1)

    win.resize(int(width), int(height))
    win.move(int(x), int(y))
    try:
        bwin = btk.main_window()
        hwnd = BlenderWindow.window_hwnd(bwin) if bwin else None
        if hwnd:
            BlenderWindow.set_owner(win, hwnd)
    except Exception:
        pass
    win.show()
    win.raise_()
    _tear_off_windows[m] = win
    return {"ok": True, "mode": m, "title": title, "floating": True, "geometry": (x, y, width, height)}


def close_tear_off_panel(mode: str) -> dict[str, Any]:
    m = (mode or "").upper()
    win = _tear_off_windows.pop(m, None)
    if win is not None:
        try:
            win.hide()
            win.deleteLater()
        except Exception:
            pass
    return {"ok": True, "mode": m, "floating": False}


def redock_panel(mode: str) -> dict[str, Any]:
    """Close the floating Tear-Off window for `mode` and dock it into the Right Sidebar."""
    from . import desktop

    m = (mode or "CHANNEL_BOX").upper()
    close_tear_off_panel(m)
    res = desktop.cycle_right_dock(m)
    return {"ok": True, "mode": m, "floating": False, "dock_result": res}


def list_torn_off_panels() -> list[dict[str, Any]]:
    out = []
    for m, win in list(_tear_off_windows.items()):
        if win is not None and win.isVisible():
            g = win.geometry()
            out.append(
                {
                    "mode": m,
                    "title": PANEL_TITLES.get(m, m),
                    "rect": (g.x(), g.y(), g.width(), g.height()),
                    "widget": win,
                }
            )
    return out


def teardown_tear_off_windows() -> None:
    for m in list(_tear_off_windows.keys()):
        close_tear_off_panel(m)


class _RightSidebarHostWidget:
    """Frameless Qt container holding the Workspace-Aware Vertical Edge Tab Spine + Maya Panel Header Bar + `QStackedWidget`."""

    def __init__(self, on_mode_tab_clicked: Callable[[str], None]):
        from qtpy import QtCore, QtWidgets

        self._on_mode_tab_clicked = on_mode_tab_clicked
        self._active_mode = "CHANNEL_BOX"
        self._active_workspace_preset = "Modeling Standard"

        self.root = QtWidgets.QFrame()
        self.root.setObjectName("MayaPanelRoot")
        style.apply_studio_style(self.root)

        outer_hlay = QtWidgets.QHBoxLayout(self.root)
        outer_hlay.setContentsMargins(0, 0, 0, 0)
        outer_hlay.setSpacing(0)

        # 1. Left-Edge 26px Workspace-Aware Vertical Rotated Edge Tab Spine
        self.edge_strip = QtWidgets.QFrame()
        self.edge_strip.setObjectName("MayaEdgeTabStrip")
        self.edge_strip.setFixedWidth(26)
        elay = QtWidgets.QVBoxLayout(self.edge_strip)
        elay.setContentsMargins(0, 0, 0, 4)
        elay.setSpacing(0)

        self.edge_tabs = {}
        for label, mkey, h_px in (
            ("CHANNEL BOX", "CHANNEL_BOX", 104),
            ("MODELING TOOLKIT", "MODELING_TOOLKIT", 118),
            ("HYPERSHADE", "HYPERSHADE", 96),
            ("SHAPE EDITOR", "SHAPE_EDITOR", 96),
            ("MAYA BRIDGE", "MAYA_INTERCHANGE", 92),
            ("ATTRIBUTE EDITOR", "ATTRIBUTE_EDITOR", 112),
            ("TOOL SETTINGS", "TOOL_SETTINGS", 96),
        ):
            etab = _create_rotated_edge_tab(label, mkey, self._on_mode_tab_clicked, height=h_px)
            self.edge_tabs[mkey] = etab
            elay.addWidget(etab)

        elay.addStretch(1)

        # Bottom '+' Overflow / Tear-Off Launcher on the 26px spine
        self.btn_spine_more = QtWidgets.QPushButton("+")
        self.btn_spine_more.setFixedSize(22, 22)
        self.btn_spine_more.setToolTip("Open or Tear Off Specialized Editors (Hypershade, Shape Editor, .ma Bridge, Tool Settings)")
        self._build_spine_more_menu()
        elay.addWidget(self.btn_spine_more, 0, QtCore.Qt.AlignHCenter)

        outer_hlay.addWidget(self.edge_strip)

        # 2. Right Inspector Column (Clean Maya Tear-Off Header Bar + QStackedWidget)
        right_col = QtWidgets.QFrame()
        vlay = QtWidgets.QVBoxLayout(right_col)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)
        outer_hlay.addWidget(right_col, 1)

        # Clean Maya Panel Title + Tear-Off / Node Graph Header Bar (replaces the crowded 7-button row!)
        self.panel_header_bar = QtWidgets.QFrame()
        self.panel_header_bar.setObjectName("MayaStatusLine")
        self.panel_header_bar.setFixedHeight(26)
        hlay = QtWidgets.QHBoxLayout(self.panel_header_bar)
        hlay.setContentsMargins(8, 2, 6, 2)
        hlay.setSpacing(5)

        lbl_tear_dots = QtWidgets.QLabel("⋮⋮")
        lbl_tear_dots.setToolTip("Maya Tear-Off Panel Header — click '↗ Tear Off' to float this editor")
        lbl_tear_dots.setStyleSheet("color: #38A3D8; font-weight: 700; font-size: 11px; background: transparent;")
        hlay.addWidget(lbl_tear_dots)

        self.lbl_panel_title = QtWidgets.QLabel("CHANNEL BOX / LAYER EDITOR")
        self.lbl_panel_title.setStyleSheet(
            "color: #E6EDF3; font-size: 10px; font-weight: 700; letter-spacing: 0.6px; background: transparent;"
        )
        hlay.addWidget(self.lbl_panel_title)
        hlay.addStretch(1)

        self.btn_split_graph = QtWidgets.QPushButton("⇄ Node Graph")
        self.btn_split_graph.setCheckable(True)
        self.btn_split_graph.setFixedHeight(19)
        self.btn_split_graph.setToolTip("Toggle Bottom Blender Native Node Graph (Shader Editor / Geometry Nodes)")
        self.btn_split_graph.clicked.connect(self._on_split_graph_clicked)
        hlay.addWidget(self.btn_split_graph)

        self.btn_tear_off = QtWidgets.QPushButton("↗ Tear Off")
        self.btn_tear_off.setFixedHeight(19)
        self.btn_tear_off.setToolTip("Undock active panel into a floating Maya Tear-Off window")
        self.btn_tear_off.clicked.connect(self._on_tear_off_clicked)
        hlay.addWidget(self.btn_tear_off)

        vlay.addWidget(self.panel_header_bar)

        # Keep hidden compatibility button references for programmatic inspection
        self.btn_cb = QtWidgets.QPushButton("Ch Box")
        self.btn_cb.setCheckable(True)
        self.btn_mtk = QtWidgets.QPushButton("Mod TK")
        self.btn_mtk.setCheckable(True)
        self.btn_hs = QtWidgets.QPushButton("Hypershade")
        self.btn_hs.setCheckable(True)
        self.btn_se = QtWidgets.QPushButton("Shape")
        self.btn_se.setCheckable(True)
        self.btn_mi = QtWidgets.QPushButton(".ma")
        self.btn_mi.setCheckable(True)
        self.btn_ae = QtWidgets.QPushButton("Attr Ed")
        self.btn_ae.setCheckable(True)
        self.btn_ts = QtWidgets.QPushButton("Tool")
        self.btn_ts.setCheckable(True)

        self.stack = QtWidgets.QStackedWidget()
        vlay.addWidget(self.stack, 1)

        self.page_cb = QtWidgets.QWidget()
        self.page_cb_lay = QtWidgets.QVBoxLayout(self.page_cb)
        self.page_cb_lay.setContentsMargins(0, 0, 0, 0)
        self.page_cb_lay.setSpacing(0)
        self.stack.addWidget(self.page_cb)

        self.ae_ctrl = attribute_editor.ensure_attribute_editor_widget()
        self.stack.addWidget(self.ae_ctrl.widget if self.ae_ctrl else QtWidgets.QWidget())

        self.ts_ctrl = tool_settings.ensure_tool_settings_widget()
        self.stack.addWidget(self.ts_ctrl.widget if self.ts_ctrl else QtWidgets.QWidget())

        self.mtk_widget = modeling_toolkit.create_modeling_toolkit_widget()
        self.stack.addWidget(self.mtk_widget)

        self.se_widget = shape_editor.create_shape_editor_widget()
        self.stack.addWidget(self.se_widget)

        self.mi_widget = interchange_panel.create_interchange_widget()
        self.stack.addWidget(self.mi_widget)

        self.hs_widget = hypershade_panel.create_hypershade_widget()
        self.stack.addWidget(self.hs_widget)

        self._attached_channels = None
        self.set_workspace_spine_preset("Modeling Standard")

    def _build_spine_more_menu(self) -> None:
        from qtpy import QtWidgets

        menu = QtWidgets.QMenu(self.btn_spine_more)
        style.apply_studio_style(menu)
        for label, mkey in (
            ("Dock Channel Box / Layers", "CHANNEL_BOX"),
            ("Dock Modeling Toolkit", "MODELING_TOOLKIT"),
            ("Dock Hypershade Material Browser", "HYPERSHADE"),
            ("Dock Shape & Skin Editor", "SHAPE_EDITOR"),
            ("Dock Maya .ma Reference Editor", "MAYA_INTERCHANGE"),
            ("Dock Attribute Editor", "ATTRIBUTE_EDITOR"),
            ("Dock Tool Settings", "TOOL_SETTINGS"),
        ):
            act = menu.addAction(label)
            act.triggered.connect(lambda _=False, k=mkey: self._on_mode_tab_clicked(k))
        menu.addSeparator()
        for label, mkey in (
            ("↗ Tear Off Hypershade Window", "HYPERSHADE"),
            ("↗ Tear Off Shape & Skin Window", "SHAPE_EDITOR"),
            ("↗ Tear Off .ma Reference Window", "MAYA_INTERCHANGE"),
            ("↗ Tear Off Tool Settings Window", "TOOL_SETTINGS"),
        ):
            act = menu.addAction(label)
            act.triggered.connect(lambda _=False, k=mkey: tear_off_panel(k))
        self.btn_spine_more.setMenu(menu)

    def _on_tear_off_clicked(self) -> None:
        target = self._active_mode if self._active_mode != "CHANNEL_BOX" else "TOOL_SETTINGS"
        tear_off_panel(target)

    def _on_split_graph_clicked(self, checked: bool) -> None:
        from . import desktop

        if checked:
            graph_type = "SHADER" if self._active_mode == "HYPERSHADE" else "GEOMETRY_NODES"
            desktop.set_bottom_node_graph_split(enable=True, graph_type=graph_type)
        else:
            desktop.set_bottom_node_graph_split(enable=False)

    def set_workspace_spine_preset(self, preset_name: str) -> None:
        """Show only the relevant Core Maya Spine Tabs for `preset_name` so the right edge stays clean."""
        self._active_workspace_preset = preset_name or "Modeling Standard"
        allowed = set(WORKSPACE_SPINE_TABS.get(self._active_workspace_preset, WORKSPACE_SPINE_TABS["Modeling Standard"]))
        allowed.add(self._active_mode)
        for mkey, etab in self.edge_tabs.items():
            etab.setVisible(mkey in allowed)

    def attach_channels_widget(self, channels_widget: Any) -> None:
        if channels_widget is None:
            return
        ext = channel_box_ext.ensure_channel_box_extensions(channels_widget)
        if self._attached_channels is not channels_widget:
            self._attached_channels = channels_widget
            if ext is not None and getattr(ext, "obj_header_bar", None) is not None:
                self.page_cb_lay.addWidget(ext.obj_header_bar, 0)
            self.page_cb_lay.addWidget(channels_widget, 0)
            if ext is not None and ext.root is not None:
                self.page_cb_lay.addWidget(ext.root, 1)
                ext.root.show()
        channels_widget.show()

    def detach_channels_widget(self) -> Optional[Any]:
        w = self._attached_channels
        if w is not None:
            try:
                self.page_cb_lay.removeWidget(w)
                w.setParent(None)
            except Exception:
                pass
            self._attached_channels = None
        return w

    def set_active_page(self, mode: str) -> None:
        m = (mode or "CHANNEL_BOX").upper()
        self._active_mode = m
        self.lbl_panel_title.setText(PANEL_TITLES.get(m, m))
        self.btn_cb.setChecked(m == "CHANNEL_BOX")
        self.btn_mtk.setChecked(m == "MODELING_TOOLKIT")
        self.btn_hs.setChecked(m == "HYPERSHADE")
        self.btn_se.setChecked(m == "SHAPE_EDITOR")
        self.btn_mi.setChecked(m == "MAYA_INTERCHANGE")
        self.btn_ae.setChecked(m == "ATTRIBUTE_EDITOR")
        self.btn_ts.setChecked(m == "TOOL_SETTINGS")

        # Ensure the active tab is visible on the vertical spine along with the workspace's core tabs
        self.set_workspace_spine_preset(self._active_workspace_preset)
        for k, etab in self.edge_tabs.items():
            etab.setChecked(k == m)
            etab.update()

        if m == "ATTRIBUTE_EDITOR":
            if self.ae_ctrl is not None:
                self.ae_ctrl.refresh()
            self.stack.setCurrentIndex(1)
        elif m == "TOOL_SETTINGS":
            if self.ts_ctrl is not None:
                self.ts_ctrl.refresh()
            self.stack.setCurrentIndex(2)
        elif m == "MODELING_TOOLKIT":
            if self.mtk_widget is not None:
                self.mtk_widget.refresh_from_scene()
            self.stack.setCurrentIndex(3)
        elif m == "SHAPE_EDITOR":
            if self.se_widget is not None:
                self.se_widget.refresh_from_scene()
            self.stack.setCurrentIndex(4)
        elif m == "MAYA_INTERCHANGE":
            if self.mi_widget is not None:
                self.mi_widget.refresh_from_scene()
            self.stack.setCurrentIndex(5)
        elif m == "HYPERSHADE":
            if self.hs_widget is not None:
                self.hs_widget.refresh_from_scene()
            self.stack.setCurrentIndex(6)
        else:
            if self._attached_channels is not None:
                self._attached_channels.show()
            channel_box_ext.refresh_channel_box_extensions()
            self.stack.setCurrentIndex(0)


class RightAreaQtDock:
    """Right-column `WS_CHILD` dock manager supporting `Channel Box`, `Modeling Toolkit`, `Hypershade`, `Shape / Skin`, `Maya Interchange`, `Attribute Editor`, `Tool Settings`, and `Native Properties`."""

    DEFAULT_WIDTH = 340

    def __init__(
        self,
        editor: str = "Properties",
        area_header: bool = False,
        focus_on_hover: bool = True,
        on_detach: Optional[Callable[[], None]] = None,
    ):
        from blendertk.ui_utils.qt_dock import QtDock

        self._inner_dock = QtDock(
            editor=editor,
            area_header=area_header,
            focus_on_hover=focus_on_hover,
            on_detach=self._handle_inner_detach,
        )
        self._user_on_detach = on_detach
        self._created_split_area = False
        self._saved_header_flag: Optional[bool] = None
        self._mode: str = "HIDDEN"
        self._channels_widget = None
        self._host_container: Optional[_RightSidebarHostWidget] = None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def docked(self) -> bool:
        return bool(self._inner_dock.docked and self._mode == "CHANNEL_BOX")

    @property
    def is_qt_embedded(self) -> bool:
        return bool(
            self._inner_dock.docked
            and self._mode
            in (
                "CHANNEL_BOX",
                "MODELING_TOOLKIT",
                "HYPERSHADE",
                "SHAPE_EDITOR",
                "MAYA_INTERCHANGE",
                "ATTRIBUTE_EDITOR",
                "TOOL_SETTINGS",
            )
        )

    @property
    def area(self):
        return self._inner_dock.area

    @property
    def widget(self):
        return self._channels_widget or self._inner_dock.widget

    @property
    def host_widget(self):
        return self._host_container.root if self._host_container is not None else self.widget

    @classmethod
    def supported(cls) -> bool:
        from blendertk.ui_utils.qt_dock import QtDock

        return QtDock.supported()

    def _ensure_host_container(self) -> _RightSidebarHostWidget:
        if self._host_container is None:
            self._host_container = _RightSidebarHostWidget(
                on_mode_tab_clicked=self._on_sidebar_tab_clicked
            )
        return self._host_container

    def _on_sidebar_tab_clicked(self, target_mode: str) -> None:
        from . import desktop

        desktop.cycle_right_dock(target_mode)

    def _handle_inner_detach(self) -> None:
        self._created_split_area = False
        if self._mode in (
            "CHANNEL_BOX",
            "MODELING_TOOLKIT",
            "HYPERSHADE",
            "SHAPE_EDITOR",
            "MAYA_INTERCHANGE",
            "ATTRIBUTE_EDITOR",
            "TOOL_SETTINGS",
        ):
            self._mode = "HIDDEN"
        if self._user_on_detach is not None:
            try:
                self._user_on_detach()
            except Exception:
                pass

    @staticmethod
    def _find_or_create_right_area(window, width: int = DEFAULT_WIDTH):
        """Find the right-most `PROPERTIES` area in `window`, or split the widest `VIEW_3D` vertically once."""
        import bpy
        from blendertk.ui_utils._ui_utils import EDITOR_TYPES, _UiUtilsInternal

        ui_type = EDITOR_TYPES.get("Properties", "PROPERTIES")
        existing = [a for a in window.screen.areas if a.ui_type == ui_type]
        if existing:
            target_prop = max(existing, key=lambda a: (a.x, -a.y))
            return target_prop, False

        view3ds = [a for a in window.screen.areas if a.type == "VIEW_3D"]
        if not view3ds:
            return None, False
        target = max(view3ds, key=lambda a: a.width)
        if target.width <= width + 100:
            return None, False

        factor = max(0.2, min(0.88, 1.0 - (float(width) / float(target.width))))
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
        right_area = max(halves, key=lambda a: a.x)
        try:
            right_area.ui_type = ui_type
        except TypeError:
            return None, False
        return right_area, True

    def _dock_host_in_right_area(
        self,
        channels_widget: Any,
        target_mode: str = "CHANNEL_BOX",
        width: Optional[int] = None,
    ) -> bool:
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow

        if channels_widget is not None:
            self._channels_widget = channels_widget

        host = self._ensure_host_container()
        if self._channels_widget is not None:
            host.attach_channels_widget(self._channels_widget)
        host.set_active_page(target_mode)

        if not self.supported():
            self._mode = target_mode
            try:
                host.root.show()
                if self._channels_widget is not None:
                    self._channels_widget.show()
            except Exception:
                pass
            return False

        if self._inner_dock.docked and self._inner_dock.widget is host.root:
            self._mode = target_mode
            try:
                host.root.show()
                self._inner_dock._last_rect = None
                self._inner_dock._position(self._inner_dock.content_region())
            except Exception:
                pass
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
            area, created = self._find_or_create_right_area(
                window, width=width or self.DEFAULT_WIDTH
            )
            if area is None:
                return False
            self._created_split_area = created

        try:
            space = area.spaces.active
            if space is not None and self._saved_header_flag is None:
                self._saved_header_flag = bool(getattr(space, "show_region_header", True))
        except Exception:
            pass

        dock = self._inner_dock
        dock._stop_glue()
        dock._release_widget()

        dock._window, dock._area, dock._hwnd = window, area, hwnd
        dock._edge_pad = dock._native_edge_pad()
        dock._area_header = False
        dock._apply_area_header(window, area)

        if not dock._embed(host.root, hwnd):
            self.undock()
            return False

        dock._position(dock.content_region())
        dock._start_glue()
        try:
            for region in area.regions:
                region.tag_redraw()
        except Exception:
            pass

        self._mode = target_mode
        return True

    def dock_channel_box(self, widget: Any, width: Optional[int] = None) -> bool:
        """Embed the right sidebar showing `CHANNEL_BOX` (`Channels` + `SHAPES` + `INPUTS` + `Display Layers`)."""
        return self._dock_host_in_right_area(widget, target_mode="CHANNEL_BOX", width=width)

    def show_attribute_editor(
        self,
        properties_context: str = "OBJECT",
        use_native_properties: bool = False,
    ) -> bool:
        """Show the Maya Qt `Attribute Editor` tab in the right dock (or native Blender `PROPERTIES` if `use_native_properties=True`)."""
        if not use_native_properties:
            return self._dock_host_in_right_area(
                self._channels_widget, target_mode="ATTRIBUTE_EDITOR"
            )
        return self.show_native_properties(properties_context=properties_context)

    def show_tool_settings(self, tool_context: Optional[str] = None) -> bool:
        """Show the Maya Qt `Tool Settings` & Option Box (`□`) tab in the right dock."""
        tool_settings.ensure_tool_settings_widget(tool_context=tool_context)
        return self._dock_host_in_right_area(
            self._channels_widget, target_mode="TOOL_SETTINGS"
        )

    def show_modeling_toolkit(self) -> bool:
        """Show the Maya Qt `Modeling Toolkit` tab in the right dock."""
        modeling_toolkit.refresh_modeling_toolkit_widgets()
        return self._dock_host_in_right_area(
            self._channels_widget, target_mode="MODELING_TOOLKIT"
        )

    def show_shape_editor(self) -> bool:
        """Show the Maya Qt `Shape Editor & Skin Weights` tab in the right dock."""
        shape_editor.refresh_shape_editor_widgets()
        return self._dock_host_in_right_area(
            self._channels_widget, target_mode="SHAPE_EDITOR"
        )

    def show_maya_interchange(self) -> bool:
        """Show the Maya Qt `Maya .ma/.mb Interchange & Reference Manager` tab in the right dock."""
        interchange_panel.refresh_interchange_widgets()
        return self._dock_host_in_right_area(
            self._channels_widget, target_mode="MAYA_INTERCHANGE"
        )

    def show_hypershade(self) -> bool:
        """Show the Maya Qt `Hypershade Material Browser & Lookdev` tab in the right dock."""
        hypershade_panel.refresh_hypershade_widgets()
        return self._dock_host_in_right_area(
            self._channels_widget, target_mode="HYPERSHADE"
        )

    def show_native_properties(self, properties_context: str = "OBJECT") -> bool:
        """Suspend the `WS_CHILD` overlay to expose Blender's native `PROPERTIES` area."""
        import bpy
        import blendertk as btk

        dock = self._inner_dock
        dock._stop_glue()
        dock._release_widget()
        dock._last_rect = None

        if bpy.app.background:
            self._mode = "NATIVE_PROPERTIES"
            return True

        window = dock._window or btk.main_window()
        area = dock._area
        try:
            if area is not None and not any(r.type == "WINDOW" for r in area.regions):
                area = None
        except (ReferenceError, AttributeError):
            area = None

        if area is None and window is not None:
            area, created = self._find_or_create_right_area(
                window, width=self.DEFAULT_WIDTH
            )
            if area is not None:
                dock._window = window
                dock._area = area
                self._created_split_area = created

        if area is not None:
            try:
                space = area.spaces.active
                if space is not None:
                    if bpy.context.window is not None:
                        space.show_region_header = True
                    if properties_context:
                        try:
                            space.context = properties_context
                        except Exception:
                            pass
                for region in area.regions:
                    region.tag_redraw()
            except Exception:
                pass

        self._mode = "NATIVE_PROPERTIES"
        return area is not None

    def enforce_dock_geometry(self) -> Optional[tuple]:
        """Re-apply `BlenderWindow.move_child` to the active right-dock content region and return `(x, y, w, h)`."""
        if not self.is_qt_embedded:
            return None
        dock = self._inner_dock
        dock._last_rect = None
        dock._position(dock.content_region())
        return dock._last_rect

    def undock_to_floating(self, parent_fn: Optional[Callable[[object], None]] = None) -> bool:
        """Detach `Channels` from the right dock and present it as a floating owned top-level Qt window."""
        from qtpy import QtCore

        widget = self._channels_widget
        if self._host_container is not None:
            self._host_container.detach_channels_widget()
        self.undock(close_split_area=True)
        if widget is None:
            return False

        try:
            handle = widget.windowHandle()
            if handle is not None:
                handle.setParent(None)
            widget.setWindowFlags(
                (widget.windowFlags() & ~QtCore.Qt.FramelessWindowHint) | QtCore.Qt.Window
            )
            if parent_fn is not None:
                parent_fn(widget)
            widget.show()
            widget.raise_()
            self._mode = "FLOATING"
            return True
        except Exception:
            return False

    def undock(self, close_split_area: bool = True) -> None:
        """Release the embedded `WS_CHILD` widget and restore (or close, if split by us) the right area."""
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
            else:
                try:
                    space = area.spaces.active
                    if (
                        space is not None
                        and self._saved_header_flag is not None
                        and bpy.context.window is not None
                    ):
                        space.show_region_header = self._saved_header_flag
                except Exception:
                    pass

        dock._window = dock._area = dock._hwnd = None
        dock._last_rect = None
        self._mode = "HIDDEN"

    def teardown(self) -> None:
        """Full cleanup on `unregister()` or reload."""
        if self._host_container is not None:
            self._host_container.detach_channels_widget()
        self.undock(close_split_area=True)
        self._inner_dock.teardown()
        channel_box_ext.teardown_channel_box_extensions()
        attribute_editor.teardown_attribute_editor()
        tool_settings.teardown_tool_settings()
        interchange_panel.teardown_interchange_widgets()
        hypershade_panel.teardown_hypershade_widgets()
        teardown_tear_off_windows()
        if self._host_container is not None:
            try:
                self._host_container.root.hide()
                self._host_container.root.deleteLater()
            except Exception:
                pass
            self._host_container = None
        self._channels_widget = None
        self._saved_header_flag = None
        self._mode = "HIDDEN"
