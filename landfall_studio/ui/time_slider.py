"""Modern Maya `Time Slider + Range Slider` Bottom `WS_CHILD` Qt Dock (`landfall_studio.ui.time_slider`).

Replaces Blender's stock bottom `TIMELINE` area with an intentional Modern Maya Time Slider & Range Slider:
- **Row 1 — Maya Time Slider & Playback Transport:**
  - Custom-painted `MayaTimeScrubBar` with dark-slate frame ticks, red object/transform keyframe ticks (`#E5484D`),
    cyan/emerald Shape Key (`key_blocks`) keyframe ticks (`#38A3D8` / `#56D364`), and Maya-blue playhead badge (`#38A3D8`).
  - Interactive click/drag scrubbing (`bpy.context.scene.frame_set(f)`).
  - Current Frame spinbox + Transport buttons (`|<`, `<`, `Play`, `>`, `>|`) + `Set Key [S]` + `Auto Key` toggle + `24 fps` badge.
- **Row 2 — Maya Range Slider & Command Strip:**
  - `Start` / `Min` spinboxes, custom-painted `MayaRangeSliderBar`, `Max` / `End` spinboxes, and live `MEL/Py` command/status readout.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from . import style

_time_slider_instances: List[Any] = []
_bottom_time_slider_dock: Optional["BottomTimeSliderQtDock"] = None


def _collect_scene_timeline_state() -> Dict[str, Any]:
    """Read current frame, start/end range, FPS, auto-key state, and keyframe ticks from Blender."""
    state: Dict[str, Any] = {
        "frame_current": 1,
        "frame_start": 1,
        "frame_end": 100,
        "fps": 24,
        "auto_key": False,
        "transform_key_frames": [],
        "shape_key_frames": [],
        "active_object": "",
    }
    try:
        import bpy
        import blendertk as btk

        scn = getattr(bpy.context, "scene", None)
        if scn is None:
            return state
        state["frame_current"] = int(scn.frame_current)
        state["frame_start"] = int(scn.frame_start)
        state["frame_end"] = max(int(scn.frame_start) + 1, int(scn.frame_end))
        state["fps"] = int(round(float(scn.render.fps) / float(scn.render.fps_base or 1.0)))
        ts = getattr(scn, "tool_settings", None)
        if ts is not None:
            state["auto_key"] = bool(getattr(ts, "use_keyframe_insert_auto", False))

        obj = getattr(bpy.context, "active_object", None)
        if obj is None and bpy.context.view_layer:
            obj = bpy.context.view_layer.objects.active
        if obj is not None:
            state["active_object"] = obj.name
            t_frames = set()
            for fc in btk.get_fcurves([obj]):
                for kp in getattr(fc, "keyframe_points", ()):
                    t_frames.add(int(round(float(kp.co.x))))
            state["transform_key_frames"] = sorted(t_frames)

            sk = getattr(getattr(obj, "data", None), "shape_keys", None)
            if sk is not None:
                s_frames = set()
                for fc in btk.get_fcurves([sk]):
                    for kp in getattr(fc, "keyframe_points", ()):
                        s_frames.add(int(round(float(kp.co.x))))
                state["shape_key_frames"] = sorted(s_frames)
    except Exception:
        pass
    return state


class MayaTimeSliderController:
    """Controller and custom-painted Qt widget for the Modern Maya Time Slider + Range Slider."""

    def __init__(self):
        from qtpy import QtCore, QtGui, QtWidgets

        self._QtCore = QtCore
        self._QtGui = QtGui
        self._QtWidgets = QtWidgets
        self._updating = False

        self.root = QtWidgets.QFrame()
        self.root.setObjectName("LandfallMayaTimeSliderDock")
        style.apply_studio_style(self.root)

        self._build_ui()
        if self not in _time_slider_instances:
            _time_slider_instances.append(self)
        self.refresh_from_scene()

    def _build_ui(self) -> None:
        QtCore = self._QtCore
        QtGui = self._QtGui
        QtWidgets = self._QtWidgets

        ctrl = self

        class _MayaTimeScrubBar(QtWidgets.QWidget):
            """Custom-painted Maya Time Slider track with frame ticks, red/cyan keyframe ticks, and blue playhead."""

            def __init__(self, parent=None):
                super().__init__(parent)
                self.setMinimumHeight(28)
                self.setCursor(QtCore.Qt.PointingHandCursor)
                self.frame_start = 1
                self.frame_end = 100
                self.frame_current = 1
                self.transform_keys: List[int] = []
                self.shape_keys: List[int] = []

            def _frame_to_x(self, frame: float, w: int) -> float:
                span = max(1, self.frame_end - self.frame_start)
                pad = 14.0
                usable = max(10.0, float(w) - 2.0 * pad)
                ratio = (float(frame) - float(self.frame_start)) / float(span)
                return pad + max(0.0, min(1.0, ratio)) * usable

            def _x_to_frame(self, x: float, w: int) -> int:
                span = max(1, self.frame_end - self.frame_start)
                pad = 14.0
                usable = max(10.0, float(w) - 2.0 * pad)
                ratio = max(0.0, min(1.0, (float(x) - pad) / usable))
                return int(round(self.frame_start + ratio * span))

            def mousePressEvent(self, event) -> None:
                if event.button() in (QtCore.Qt.LeftButton, QtCore.Qt.MiddleButton):
                    f = self._x_to_frame(event.pos().x(), self.width())
                    ctrl.set_current_frame(f)

            def mouseMoveEvent(self, event) -> None:
                if event.buttons() & (QtCore.Qt.LeftButton | QtCore.Qt.MiddleButton):
                    f = self._x_to_frame(event.pos().x(), self.width())
                    ctrl.set_current_frame(f)

            def paintEvent(self, _event) -> None:
                p = QtGui.QPainter(self)
                p.setRenderHint(QtGui.QPainter.Antialiasing, True)
                w = self.width()
                h = self.height()

                # Recessed dark Maya Time Slider background
                p.fillRect(0, 0, w, h, QtGui.QColor("#17191C"))
                p.setPen(QtGui.QColor("#2C313A"))
                p.drawRect(0, 0, w - 1, h - 1)

                span = max(1, self.frame_end - self.frame_start)
                major_step = 10 if span <= 150 else (25 if span <= 400 else 50)
                minor_step = max(1, major_step // 5)

                font = p.font()
                font.setPixelSize(9)
                p.setFont(font)

                # Draw minor & major frame ticks
                for f in range(self.frame_start, self.frame_end + 1):
                    x = int(round(self._frame_to_x(f, w)))
                    is_major = (f == self.frame_start) or (f == self.frame_end) or (f % major_step == 0)
                    if is_major:
                        p.setPen(QtGui.QColor("#484F58"))
                        p.drawLine(x, h - 11, x, h - 2)
                        p.setPen(QtGui.QColor("#8B949E"))
                        p.drawText(x + 3, 10, str(f))
                    elif f % minor_step == 0:
                        p.setPen(QtGui.QColor("#2B3038"))
                        p.drawLine(x, h - 6, x, h - 2)

                # Draw red object/transform keyframe ticks
                for kf in self.transform_keys:
                    if self.frame_start <= kf <= self.frame_end:
                        kx = int(round(self._frame_to_x(kf, w)))
                        p.fillRect(kx - 1, 2, 3, h - 4, QtGui.QColor("#E5484D"))

                # Draw cyan/emerald Shape Key morph keyframe ticks
                for skf in self.shape_keys:
                    if self.frame_start <= skf <= self.frame_end:
                        kx = int(round(self._frame_to_x(skf, w)))
                        p.fillRect(kx - 1, 3, 3, h - 6, QtGui.QColor("#38A3D8"))
                        p.fillRect(kx - 2, h - 6, 5, 4, QtGui.QColor("#56D364"))

                # Draw Maya-Blue Current Frame Playhead Pill
                cx = int(round(self._frame_to_x(self.frame_current, w)))
                pill_w = 28
                pill_x = max(2, min(w - pill_w - 2, cx - pill_w // 2))
                p.fillRect(pill_x, 1, pill_w, h - 2, QtGui.QColor(56, 163, 216, 75))
                p.setPen(QtGui.QPen(QtGui.QColor("#38A3D8"), 1.5))
                p.drawLine(cx, 1, cx, h - 2)

                badge_rect = QtCore.QRectF(pill_x, 2, pill_w, 13)
                p.setBrush(QtGui.QColor("#246892"))
                p.setPen(QtGui.QColor("#58A6FF"))
                p.drawRoundedRect(badge_rect, 2.0, 2.0)

                font.setBold(True)
                p.setFont(font)
                p.setPen(QtGui.QColor("#FFFFFF"))
                p.drawText(badge_rect, QtCore.Qt.AlignCenter, str(self.frame_current))
                p.end()

        class _MayaRangeSliderBar(QtWidgets.QWidget):
            """Custom-painted Maya Range Slider bar with end-grip boxes and range label."""

            def __init__(self, parent=None):
                super().__init__(parent)
                self.setFixedHeight(18)
                self.frame_start = 1
                self.frame_end = 100

            def paintEvent(self, _event) -> None:
                p = QtGui.QPainter(self)
                p.setRenderHint(QtGui.QPainter.Antialiasing, True)
                w = self.width()
                h = self.height()

                p.fillRect(0, 0, w, h, QtGui.QColor("#16181B"))
                bar_rect = QtCore.QRectF(4, 2, max(16, w - 8), h - 4)
                p.setBrush(QtGui.QColor("#2A2F37"))
                p.setPen(QtGui.QColor("#3D4450"))
                p.drawRoundedRect(bar_rect, 2.0, 2.0)

                # Left and right Maya range grip handles
                p.fillRect(6, 4, 8, h - 8, QtGui.QColor("#58A6FF"))
                p.fillRect(max(16, w - 14), 4, 8, h - 8, QtGui.QColor("#58A6FF"))

                font = p.font()
                font.setPixelSize(9)
                p.setFont(font)
                p.setPen(QtGui.QColor("#9AA4B2"))
                p.drawText(
                    bar_rect,
                    QtCore.Qt.AlignCenter,
                    f"Playback Range: {self.frame_start}  ..  {self.frame_end}",
                )
                p.end()

        v_layout = QtWidgets.QVBoxLayout(self.root)
        v_layout.setContentsMargins(6, 2, 6, 2)
        v_layout.setSpacing(2)

        # Row 1: Time Slider + Frame Spin + Transport Controls + Set Key / Auto Key
        row1 = QtWidgets.QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(4)

        self.scrub_bar = _MayaTimeScrubBar(self.root)
        row1.addWidget(self.scrub_bar, 1)

        self.spin_current = QtWidgets.QSpinBox(self.root)
        self.spin_current.setRange(-10000, 100000)
        self.spin_current.setFixedWidth(54)
        self.spin_current.setFixedHeight(22)
        self.spin_current.setToolTip("Current Frame")
        self.spin_current.valueChanged.connect(self._on_spin_current_changed)
        row1.addWidget(self.spin_current)

        # Transport buttons
        for lbl, tip, fn in (
            ("|<", "Go to Start Frame", self._on_jump_start),
            ("<", "Step Back 1 Frame", lambda: self.step_frame(-1)),
            ("Play", "Play / Pause Animation (Alt+V)", self._on_toggle_play),
            (">", "Step Forward 1 Frame", lambda: self.step_frame(1)),
            (">|", "Go to End Frame", self._on_jump_end),
        ):
            b = QtWidgets.QPushButton(lbl, self.root)
            b.setToolTip(tip)
            b.setFixedHeight(22)
            b.setFixedWidth(36 if lbl == "Play" else 24)
            b.clicked.connect(fn)
            row1.addWidget(b)

        self.btn_set_key = QtWidgets.QPushButton("Set Key [S]", self.root)
        self.btn_set_key.setFixedHeight(22)
        self.btn_set_key.setStyleSheet(
            "background-color: #214D72; color: #E6EDF3; border: 1px solid #38A3D8; font-weight: 700; padding: 0 7px;"
        )
        self.btn_set_key.clicked.connect(self._on_set_key)
        row1.addWidget(self.btn_set_key)

        self.btn_auto_key = QtWidgets.QPushButton("Auto Key", self.root)
        self.btn_auto_key.setCheckable(True)
        self.btn_auto_key.setFixedHeight(22)
        self.btn_auto_key.clicked.connect(self._on_toggle_auto_key)
        row1.addWidget(self.btn_auto_key)

        self.lbl_fps = QtWidgets.QLabel("24 fps", self.root)
        self.lbl_fps.setStyleSheet(
            "background-color: #16181B; color: #8B949E; border: 1px solid #2C313A; "
            "border-radius: 2px; padding: 1px 6px; font-size: 10px; font-weight: 600;"
        )
        row1.addWidget(self.lbl_fps)

        v_layout.addLayout(row1)

        # Row 2: Range Slider + Start/Min/Max/End + Command Strip
        row2 = QtWidgets.QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(4)

        self.spin_start = QtWidgets.QSpinBox(self.root)
        self.spin_start.setRange(-10000, 100000)
        self.spin_start.setFixedWidth(48)
        self.spin_start.setFixedHeight(19)
        self.spin_start.setToolTip("Playback Start Frame")
        self.spin_start.valueChanged.connect(self._on_range_spin_changed)
        row2.addWidget(self.spin_start)

        self.range_bar = _MayaRangeSliderBar(self.root)
        row2.addWidget(self.range_bar, 1)

        self.spin_end = QtWidgets.QSpinBox(self.root)
        self.spin_end.setRange(-10000, 100000)
        self.spin_end.setFixedWidth(52)
        self.spin_end.setFixedHeight(19)
        self.spin_end.setToolTip("Playback End Frame")
        self.spin_end.valueChanged.connect(self._on_range_spin_changed)
        row2.addWidget(self.spin_end)

        self.lbl_key_summary = QtWidgets.QLabel("Keys: 0", self.root)
        self.lbl_key_summary.setStyleSheet(
            "background-color: #16181B; color: #58A6FF; border: 1px solid #2A3441; "
            "border-radius: 2px; padding: 1px 8px; font-size: 10px; font-weight: 600;"
        )
        row2.addWidget(self.lbl_key_summary)

        v_layout.addLayout(row2)

    def refresh_from_scene(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            st = _collect_scene_timeline_state()
            self.scrub_bar.frame_start = st["frame_start"]
            self.scrub_bar.frame_end = st["frame_end"]
            self.scrub_bar.frame_current = st["frame_current"]
            self.scrub_bar.transform_keys = st["transform_key_frames"]
            self.scrub_bar.shape_keys = st["shape_key_frames"]
            self.scrub_bar.update()

            self.range_bar.frame_start = st["frame_start"]
            self.range_bar.frame_end = st["frame_end"]
            self.range_bar.update()

            self.spin_current.setValue(st["frame_current"])
            self.spin_start.setValue(st["frame_start"])
            self.spin_end.setValue(st["frame_end"])
            self.lbl_fps.setText(f"{st['fps']} fps")

            ak = bool(st["auto_key"])
            self.btn_auto_key.setChecked(ak)
            if ak:
                self.btn_auto_key.setStyleSheet(
                    "background-color: #4A1D22; color: #FF7B72; border: 1px solid #E5484D; font-weight: 700;"
                )
            else:
                self.btn_auto_key.setStyleSheet("")

            n_t = len(st["transform_key_frames"])
            n_s = len(st["shape_key_frames"])
            self.lbl_key_summary.setText(f"Keys: {n_t} Xform | {n_s} Morph")
        finally:
            self._updating = False

    def set_current_frame(self, frame: int) -> None:
        try:
            import bpy
            from .. import character

            scn = getattr(bpy.context, "scene", None)
            if scn is not None:
                scn.frame_set(int(frame))
                obj = getattr(bpy.context, "active_object", None)
                if obj is not None and getattr(obj, "type", None) == "MESH":
                    character.evaluate_correctives_deterministic(obj)
        except Exception:
            pass
        self.refresh_from_scene()

    def step_frame(self, delta: int) -> None:
        st = _collect_scene_timeline_state()
        self.set_current_frame(st["frame_current"] + int(delta))

    def _on_spin_current_changed(self, val: int) -> None:
        if not self._updating:
            self.set_current_frame(int(val))

    def _on_range_spin_changed(self, _val: int) -> None:
        if self._updating:
            return
        try:
            import bpy

            scn = getattr(bpy.context, "scene", None)
            if scn is not None:
                s = int(self.spin_start.value())
                e = max(s + 1, int(self.spin_end.value()))
                scn.frame_start = s
                scn.frame_end = e
        except Exception:
            pass
        self.refresh_from_scene()

    def _on_jump_start(self) -> None:
        st = _collect_scene_timeline_state()
        self.set_current_frame(st["frame_start"])

    def _on_jump_end(self) -> None:
        st = _collect_scene_timeline_state()
        self.set_current_frame(st["frame_end"])

    def _on_toggle_play(self) -> None:
        try:
            import bpy

            bpy.ops.screen.animation_play()
        except Exception:
            pass

    def _on_set_key(self) -> None:
        try:
            import bpy
            from .. import character

            obj = getattr(bpy.context, "active_object", None)
            if obj is not None:
                obj.keyframe_insert(data_path="location")
                obj.keyframe_insert(data_path="rotation_euler")
                obj.keyframe_insert(data_path="scale")
                sk = getattr(getattr(obj, "data", None), "shape_keys", None)
                if sk is not None and len(sk.key_blocks) > 1:
                    for kb in sk.key_blocks[1:]:
                        if "_tween_w" not in kb.name:
                            character.keyframe_shape_target(obj, kb.name)
        except Exception:
            pass
        self.refresh_from_scene()

    def _on_toggle_auto_key(self, checked: bool) -> None:
        try:
            import bpy

            ts = getattr(getattr(bpy.context, "scene", None), "tool_settings", None)
            if ts is not None:
                ts.use_keyframe_insert_auto = bool(checked)
        except Exception:
            pass
        self.refresh_from_scene()


class BottomTimeSliderQtDock:
    """Bottom `WS_CHILD` dock manager embedding `MayaTimeSliderController` over Blender's `TIMELINE` area."""

    def __init__(self):
        from blendertk.ui_utils.qt_dock import QtDock

        self._inner_dock = QtDock(
            editor="Info",
            area_header=False,
            focus_on_hover=True,
            on_detach=self._handle_detach,
        )
        self._ctrl: Optional[MayaTimeSliderController] = None
        self._orig_ui_type: Optional[str] = None
        self._sync_timer: Optional[Any] = None

    @property
    def docked(self) -> bool:
        return bool(self._inner_dock.docked)

    @property
    def widget(self):
        return self._ctrl.root if self._ctrl is not None else None

    def ensure_widget(self) -> MayaTimeSliderController:
        if self._ctrl is None:
            self._ctrl = MayaTimeSliderController()
        return self._ctrl

    def _handle_detach(self) -> None:
        self._orig_ui_type = None

    @staticmethod
    def _find_timeline_area(window):
        for area in window.screen.areas:
            if getattr(area, "ui_type", "") == "TIMELINE" or area.type == "DOPESHEET_EDITOR":
                return area
        return None

    def _position_over_full_area(self) -> Optional[tuple]:
        from blendertk.ui_utils.blender_window import BlenderWindow

        dock = self._inner_dock
        if dock._area is None or dock._widget is None or dock._hwnd is None:
            return None
        rect = BlenderWindow.region_client_rect(dock._hwnd, dock._area)
        if rect is None:
            return None
        x, y, w, h = rect
        pad = dock._edge_pad or 3
        inset = max(0, min(pad, h - pad))
        rect = (x, y + inset, w, h - inset)
        if rect != dock._last_rect:
            try:
                child = int(dock._widget.winId())
                BlenderWindow.move_child(child, rect)
                dock._last_rect = rect
            except Exception:
                return None
        return dock._last_rect

    def _start_sync_timer(self) -> None:
        import bpy

        self._stop_sync_timer()
        self._sync_timer = self._sync_tick
        try:
            bpy.app.timers.register(self._sync_timer, first_interval=0.1, persistent=True)
        except Exception:
            pass

    def _stop_sync_timer(self) -> None:
        if self._sync_timer is None:
            return
        import bpy

        try:
            bpy.app.timers.unregister(self._sync_timer)
        except Exception:
            pass
        self._sync_timer = None

    def _sync_tick(self):
        from blendertk.ui_utils.blender_window import BlenderWindow

        dock = self._inner_dock
        if dock._widget is None:
            return None
        if dock.content_region() is None or not BlenderWindow.is_window(dock._hwnd):
            self.undock()
            return None
        self._position_over_full_area()
        return 0.15

    def dock_time_slider(self) -> bool:
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow

        ctrl = self.ensure_widget()
        if not self._inner_dock.supported():
            return False

        if self._inner_dock.docked and self._inner_dock.widget is ctrl.root:
            self.enforce_dock_geometry()
            ctrl.refresh_from_scene()
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
            area = self._find_timeline_area(window)
            if area is None:
                return False
            self._orig_ui_type = getattr(area, "ui_type", "TIMELINE")

        dock = self._inner_dock
        self._stop_sync_timer()
        dock._stop_glue()
        dock._release_widget()

        dock._window, dock._area, dock._hwnd = window, area, hwnd
        dock._edge_pad = dock._native_edge_pad()

        if not dock._embed(ctrl.root, hwnd):
            self.undock()
            return False

        dock._last_rect = None
        self._position_over_full_area()
        self._start_sync_timer()
        ctrl.refresh_from_scene()
        return True

    def enforce_dock_geometry(self) -> Optional[tuple]:
        if not self.docked:
            return None
        self._inner_dock._last_rect = None
        return self._position_over_full_area()

    def undock(self) -> None:
        self._stop_sync_timer()
        dock = self._inner_dock
        dock._stop_glue()
        dock._release_widget()
        self._orig_ui_type = None
        dock._window = dock._area = dock._hwnd = None
        dock._last_rect = None

    def teardown(self) -> None:
        self.undock()
        self._inner_dock.teardown()
        if self._ctrl is not None:
            try:
                self._ctrl.root.hide()
                self._ctrl.root.deleteLater()
            except Exception:
                pass
            self._ctrl = None


def get_bottom_time_slider_dock() -> BottomTimeSliderQtDock:
    global _bottom_time_slider_dock
    if _bottom_time_slider_dock is None:
        _bottom_time_slider_dock = BottomTimeSliderQtDock()
    return _bottom_time_slider_dock


def refresh_time_slider_widgets() -> None:
    for inst in list(_time_slider_instances):
        try:
            inst.refresh_from_scene()
        except Exception:
            pass


def get_time_slider_snapshot() -> Dict[str, Any]:
    refresh_time_slider_widgets()
    st = _collect_scene_timeline_state()
    dock = _bottom_time_slider_dock
    return {
        "ok": True,
        "docked": bool(dock.docked) if dock is not None else False,
        "widget_count": len(_time_slider_instances),
        **st,
    }


def teardown_time_slider() -> None:
    global _bottom_time_slider_dock
    if _bottom_time_slider_dock is not None:
        try:
            _bottom_time_slider_dock.teardown()
        except Exception:
            pass
        _bottom_time_slider_dock = None
    _time_slider_instances.clear()
