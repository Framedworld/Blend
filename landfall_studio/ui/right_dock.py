"""Right-hand `QtDock` subclass (`RightAreaQtDock`) for Maya Classic Channel Box <-> Attribute Editor cycling.

Extends `blendertk.ui_utils.qt_dock.QtDock` so a Qt panel (such as `Channels`) can dock
on the **right side** of the Blender main window over the existing `PROPERTIES` area (or a
single tracked vertical split if no `PROPERTIES` area exists), and cleanly cycle between:
- `CHANNEL_BOX`: `WS_CHILD` `Channels` Qt panel embedded over the right-hand area
- `ATTRIBUTE_EDITOR`: `WS_CHILD` overlay suspended/hidden so native `PROPERTIES` is visible in-place
- `FLOATING`: `Channels` un-embedded and shown as an OS-owned floating top-level Qt tool window
- `HIDDEN`: `WS_CHILD` hidden (and any temporary split area closed), with zero duplicate areas created.
"""

from __future__ import annotations

import sys
from typing import Callable, Optional


class RightAreaQtDock:
    """Right-column `WS_CHILD` dock manager supporting `Ctrl+A` Channel Box <-> Attribute Editor cycling."""

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
        self._mode: str = "HIDDEN"  # "CHANNEL_BOX", "ATTRIBUTE_EDITOR", "FLOATING", "HIDDEN"
        self._widget = None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def docked(self) -> bool:
        return bool(self._inner_dock.docked and self._mode == "CHANNEL_BOX")

    @property
    def area(self):
        return self._inner_dock.area

    @property
    def widget(self):
        return self._widget or self._inner_dock.widget

    @classmethod
    def supported(cls) -> bool:
        from blendertk.ui_utils.qt_dock import QtDock

        return QtDock.supported()

    def _handle_inner_detach(self) -> None:
        self._created_split_area = False
        if self._mode == "CHANNEL_BOX":
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
            # Pick the right-most, bottom-most Properties area (standard Blender right column)
            target_prop = max(existing, key=lambda a: (a.x, -a.y))
            return target_prop, False

        view3ds = [a for a in window.screen.areas if a.type == "VIEW_3D"]
        if not view3ds:
            return None, False
        target = max(view3ds, key=lambda a: a.width)
        if target.width <= width + 100:
            return None, False

        # In Blender, VERTICAL split factor is the fraction given to the left half
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

    def dock_channel_box(self, widget, width: Optional[int] = None) -> bool:
        """Embed `widget` (`Channels`) over the right-hand dock area (`CHANNEL_BOX` mode)."""
        import bpy
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow

        self._widget = widget

        if not self.supported():
            # Headless / offscreen fallback: track logical state and show widget offscreen
            self._mode = "CHANNEL_BOX"
            try:
                widget.show()
            except Exception:
                pass
            return False

        if self._inner_dock.docked and self._inner_dock.widget is widget:
            self._mode = "CHANNEL_BOX"
            try:
                widget.show()
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

        # Reuse tracked area if still alive, else find/create right area
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

        # Save original header visibility before hiding native area header for embedded Qt
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

        if not dock._embed(widget, hwnd):
            self.undock()
            return False

        dock._position(dock.content_region())
        dock._start_glue()
        try:
            for region in area.regions:
                region.tag_redraw()
        except Exception:
            pass

        self._mode = "CHANNEL_BOX"
        return True

    def enforce_dock_geometry(self) -> Optional[tuple]:
        """Re-apply `BlenderWindow.move_child` to the active right-dock content region and return `(x, y, w, h)`."""
        if not self.docked:
            return None
        dock = self._inner_dock
        dock._last_rect = None
        dock._position(dock.content_region())
        return dock._last_rect

    def show_attribute_editor(
        self, properties_context: str = "OBJECT"
    ) -> bool:
        """Suspend the `Channels` `WS_CHILD` overlay and expose the native `PROPERTIES` area (`ATTRIBUTE_EDITOR` mode)."""
        import bpy
        import blendertk as btk

        dock = self._inner_dock
        dock._stop_glue()
        dock._release_widget()
        dock._last_rect = None

        if bpy.app.background:
            self._mode = "ATTRIBUTE_EDITOR"
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

        self._mode = "ATTRIBUTE_EDITOR"
        return area is not None

    def undock_to_floating(self, parent_fn: Optional[Callable[[object], None]] = None) -> bool:
        """Detach `widget` from the right dock and present it as a floating owned top-level Qt window."""
        from qtpy import QtCore

        widget = self.widget
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
                # Restore the existing PROPERTIES area's header flag
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
        self.undock(close_split_area=True)
        self._inner_dock.teardown()
        self._widget = None
        self._saved_header_flag = None
        self._mode = "HIDDEN"
