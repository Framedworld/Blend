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


class _RightSidebarHostWidget:
    """Frameless Qt container holding the Figma Make vertical rotated edge tab strip + top tab bar + `QStackedWidget`."""

    def __init__(self, on_mode_tab_clicked: Callable[[str], None]):
        from qtpy import QtCore, QtWidgets

        self._on_mode_tab_clicked = on_mode_tab_clicked
        self.root = QtWidgets.QFrame()
        self.root.setObjectName("MayaPanelRoot")
        style.apply_studio_style(self.root)

        outer_hlay = QtWidgets.QHBoxLayout(self.root)
        outer_hlay.setContentsMargins(0, 0, 0, 0)
        outer_hlay.setSpacing(0)

        # 1. Figma Make Left-Edge 26px Vertical Rotated Edge Tab Strip
        self.edge_strip = QtWidgets.QFrame()
        self.edge_strip.setObjectName("MayaEdgeTabStrip")
        self.edge_strip.setFixedWidth(26)
        elay = QtWidgets.QVBoxLayout(self.edge_strip)
        elay.setContentsMargins(0, 0, 0, 0)
        elay.setSpacing(0)

        self.edge_tabs = {}
        for label, mkey, h_px in (
            ("CHANNEL BOX", "CHANNEL_BOX", 108),
            ("MODELING TOOLKIT", "MODELING_TOOLKIT", 122),
            ("SHAPE EDITOR", "SHAPE_EDITOR", 104),
            ("MAYA BRIDGE", "MAYA_INTERCHANGE", 100),
            ("ATTRIBUTE EDITOR", "ATTRIBUTE_EDITOR", 118),
            ("TOOL SETTINGS", "TOOL_SETTINGS", 104),
        ):
            etab = _create_rotated_edge_tab(label, mkey, self._on_mode_tab_clicked, height=h_px)
            self.edge_tabs[mkey] = etab
            elay.addWidget(etab)
        elay.addStretch(1)
        outer_hlay.addWidget(self.edge_strip)

        # 2. Right Inspector Column (Header Bar + Compact Tab Strip + QStackedWidget)
        right_col = QtWidgets.QFrame()
        vlay = QtWidgets.QVBoxLayout(right_col)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)
        outer_hlay.addWidget(right_col, 1)

        # Top Maya Sidebar Tab Bar (Ch Box | Mod Toolkit | Shape / Skin | .ma Bridge | Attr Ed | Tool Set)
        tab_strip = QtWidgets.QFrame()
        tab_strip.setObjectName("MayaStatusLine")
        tlay = QtWidgets.QHBoxLayout(tab_strip)
        tlay.setContentsMargins(2, 2, 2, 2)
        tlay.setSpacing(2)

        self.btn_cb = QtWidgets.QPushButton("Ch Box")
        self.btn_cb.setCheckable(True)
        self.btn_cb.setFixedHeight(21)
        self.btn_cb.clicked.connect(lambda: self._on_mode_tab_clicked("CHANNEL_BOX"))

        self.btn_mtk = QtWidgets.QPushButton("Mod TK")
        self.btn_mtk.setCheckable(True)
        self.btn_mtk.setFixedHeight(21)
        self.btn_mtk.clicked.connect(lambda: self._on_mode_tab_clicked("MODELING_TOOLKIT"))

        self.btn_se = QtWidgets.QPushButton("Shape/Skin")
        self.btn_se.setCheckable(True)
        self.btn_se.setFixedHeight(21)
        self.btn_se.clicked.connect(lambda: self._on_mode_tab_clicked("SHAPE_EDITOR"))

        self.btn_mi = QtWidgets.QPushButton(".ma Bridge")
        self.btn_mi.setCheckable(True)
        self.btn_mi.setFixedHeight(21)
        self.btn_mi.setToolTip("Maya .ma/.mb Interchange & Reference Manager")
        self.btn_mi.clicked.connect(lambda: self._on_mode_tab_clicked("MAYA_INTERCHANGE"))

        self.btn_ae = QtWidgets.QPushButton("Attr Ed")
        self.btn_ae.setCheckable(True)
        self.btn_ae.setFixedHeight(21)
        self.btn_ae.clicked.connect(lambda: self._on_mode_tab_clicked("ATTRIBUTE_EDITOR"))

        self.btn_ts = QtWidgets.QPushButton("Tool Set")
        self.btn_ts.setCheckable(True)
        self.btn_ts.setFixedHeight(21)
        self.btn_ts.clicked.connect(lambda: self._on_mode_tab_clicked("TOOL_SETTINGS"))

        tlay.addWidget(self.btn_cb, 1)
        tlay.addWidget(self.btn_mtk, 1)
        tlay.addWidget(self.btn_se, 1)
        tlay.addWidget(self.btn_mi, 1)
        tlay.addWidget(self.btn_ae, 1)
        tlay.addWidget(self.btn_ts, 1)
        vlay.addWidget(tab_strip)

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

        self._attached_channels = None

    def attach_channels_widget(self, channels_widget: Any) -> None:
        if channels_widget is None:
            return
        ext = channel_box_ext.ensure_channel_box_extensions(channels_widget)
        if self._attached_channels is not channels_widget:
            self._attached_channels = channels_widget
            if ext is not None and getattr(ext, "obj_header_bar", None) is not None:
                self.page_cb_lay.addWidget(ext.obj_header_bar, 0)
            self.page_cb_lay.addWidget(channels_widget, 5)
            if ext is not None and ext.root is not None:
                self.page_cb_lay.addWidget(ext.root, 6)
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
        self.btn_cb.setChecked(m == "CHANNEL_BOX")
        self.btn_mtk.setChecked(m == "MODELING_TOOLKIT")
        self.btn_se.setChecked(m == "SHAPE_EDITOR")
        self.btn_mi.setChecked(m == "MAYA_INTERCHANGE")
        self.btn_ae.setChecked(m == "ATTRIBUTE_EDITOR")
        self.btn_ts.setChecked(m == "TOOL_SETTINGS")

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
        else:
            if self._attached_channels is not None:
                self._attached_channels.show()
            channel_box_ext.refresh_channel_box_extensions()
            self.stack.setCurrentIndex(0)


class RightAreaQtDock:
    """Right-column `WS_CHILD` dock manager supporting `Channel Box`, `Modeling Toolkit`, `Shape / Skin`, `Maya Interchange`, `Attribute Editor`, `Tool Settings`, and `Native Properties`."""

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
