"""Qt -> Blender Viewport Hotkey Passthrough Filter (`QtViewportHotkeyFilter`).

Ensures that when a user clicks inside a docked (`WS_CHILD`) or floating Qt tool window
(`Channels`, `Reference Manager`, `Workspace Editor`, `Script Output`, or any Switchboard
panel) and keyboard focus is NOT inside an active editable text input (`QLineEdit`,
`QTextEdit`, `QPlainTextEdit`, `QAbstractSpinBox`, editable `QComboBox`, or an item view
in `EditingState`), pressing Maya viewport shortcuts (`Q/W/E/R`, `1/2/3`, `F`, `A`, `G`,
`Y`, `F8-F12`, `Space`, `Ctrl+Z`, `Ctrl+Shift+Z`, `Ctrl+A`) forwards execution cleanly
to Blender's 3D Viewport instead of being swallowed by Qt.
"""

from __future__ import annotations

import sys
import time
from typing import Any, Dict, List, Optional

_installed_filter: Optional[Any] = None
_passthrough_history: List[Dict[str, Any]] = []
MAX_PASSTHROUGH_LOG = 64


def is_editable_text_widget(widget: Any) -> bool:
    """Return True if `widget` (or the current `QApplication.focusWidget()`) is an active editable text input."""
    try:
        from qtpy import QtWidgets
    except Exception:
        return False

    app = QtWidgets.QApplication.instance()
    focus_w = app.focusWidget() if app is not None else None

    candidates = []
    for w in (focus_w, widget):
        if w is not None and w not in candidates:
            candidates.append(w)
            try:
                fp = w.focusProxy()
                if fp is not None and fp not in candidates:
                    candidates.append(fp)
            except Exception:
                pass

    for w in candidates:
        try:
            if isinstance(w, QtWidgets.QLineEdit):
                if not w.isReadOnly() and w.isEnabled():
                    return True
            elif isinstance(w, (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
                if not w.isReadOnly() and w.isEnabled():
                    return True
            elif isinstance(w, QtWidgets.QAbstractSpinBox):
                if not w.isReadOnly() and w.isEnabled():
                    return True
            elif isinstance(w, QtWidgets.QComboBox):
                if w.isEditable() and w.isEnabled():
                    return True
            elif isinstance(w, QtWidgets.QAbstractItemView):
                if w.state() == QtWidgets.QAbstractItemView.EditingState:
                    return True
                if hasattr(w, "active_editor"):
                    ed = w.active_editor()
                    if (
                        isinstance(ed, QtWidgets.QLineEdit)
                        and not ed.isReadOnly()
                        and ed.isVisible()
                    ):
                        return True
        except Exception:
            continue

    return False


def _widget_label(w: Any) -> str:
    if w is None:
        return "None"
    try:
        name = w.objectName() or ""
        cls_name = type(w).__name__
        return f"{name}:{cls_name}" if name else cls_name
    except Exception:
        return repr(w)


def _record_passthrough(
    key_name: str,
    action: str,
    target_widget: Any,
    forwarded: bool,
    reason: str = "",
) -> Dict[str, Any]:
    entry = {
        "key": key_name,
        "action": action,
        "target_widget": _widget_label(target_widget),
        "forwarded": bool(forwarded),
        "reason": reason,
        "timestamp": time.monotonic(),
    }
    _passthrough_history.append(entry)
    if len(_passthrough_history) > MAX_PASSTHROUGH_LOG:
        del _passthrough_history[:-MAX_PASSTHROUGH_LOG]
    return entry


def get_passthrough_history() -> List[Dict[str, Any]]:
    """Return a copy of recorded Qt hotkey passthrough events."""
    return list(_passthrough_history)


def get_last_passthrough_event() -> Optional[Dict[str, Any]]:
    """Return the most recent passthrough event record, or None."""
    return _passthrough_history[-1] if _passthrough_history else None


def clear_passthrough_history() -> None:
    """Clear the recorded passthrough history."""
    _passthrough_history.clear()


def _execute_in_view3d(callable_op) -> bool:
    """Execute `callable_op()` under a `VIEW_3D` context override when available, or directly in headless mode."""
    import bpy

    ctx = None
    if not bpy.app.background:
        try:
            import blendertk as btk

            ctx = btk.get_view3d_context()
        except Exception:
            ctx = None

    try:
        if ctx and ctx.get("window") and ctx.get("area"):
            with bpy.context.temp_override(**ctx):
                res = callable_op()
        else:
            res = callable_op()
        if isinstance(res, set):
            return "FINISHED" in res or "RUNNING_MODAL" in res
        return bool(res)
    except Exception:
        return False


def _return_os_focus_to_blender() -> None:
    """Best-effort return of Win32 keyboard focus to Blender's main GHOST window."""
    if sys.platform != "win32":
        return
    try:
        from PySide6 import QtWidgets
        if QtWidgets.QApplication.activePopupWidget() is not None or QtWidgets.QApplication.activeModalWidget() is not None:return
        if _installed_filter is not None and _installed_filter.sculpt_pointer.active:return
        import bpy

        if bpy.app.background:
            return
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow

        win = btk.main_window()
        hwnd = BlenderWindow.window_hwnd(win) if win is not None else None
        if hwnd:
            BlenderWindow.set_keyboard_focus(hwnd)
    except Exception:
        pass


def dispatch_qt_key_to_blender(
    key: int,
    modifiers: Any,
    target_widget: Any = None,
) -> Optional[Dict[str, Any]]:
    """Evaluate a Qt key press and forward it to Blender if it matches a Studio viewport shortcut."""
    from qtpy import QtCore
    import bpy
    from .. import keymaps

    Qt = QtCore.Qt
    from .input_policy import keeps_keyboard
    if keeps_keyboard(target_widget, key, modifiers):
        return None
    ctrl = bool(modifiers & Qt.ControlModifier)
    shift = bool(modifiers & Qt.ShiftModifier)
    alt = bool(modifiers & Qt.AltModifier)
    meta = bool(modifiers & Qt.MetaModifier)

    profile = keymaps.get_active_profile()
    if ctrl and not (alt or meta) and key in (Qt.Key_N,Qt.Key_O,Qt.Key_S,Qt.Key_Q):
        from . import menus
        from PySide6 import QtWidgets
        paths={Qt.Key_N:('Ctrl+N','wm.read_homefile'),Qt.Key_O:('Ctrl+O','landfall.project_open'),
               Qt.Key_S:('Ctrl+Shift+S' if shift else 'Ctrl+S','landfall.project_save_as' if shift else 'wm.save_mainfile'),
               Qt.Key_Q:('Ctrl+Q','wm.quit_blender')}
        label,path=paths[key]
        focus=QtWidgets.QApplication.focusWidget()
        if focus is not None:focus.clearFocus()  # Commit a pending numeric edit before saving.
        result=menus.run_op(path,invoke=True)
        return _record_passthrough(label,path,target_widget,isinstance(result,set) and bool(result & {'FINISHED','RUNNING_MODAL'}),'file_command')

    # Sculpt has its own ZBrush Q/W/E/R meanings (E=Scale, R=Rotate).
    # Reuse the same sculpt shortcut dispatcher used by the native keymap.
    if bpy.context.mode == 'SCULPT':
        from ..sculpt import state,is_engaged
        if is_engaged():
            action = None
            if not (alt or meta):
                if ctrl:
                    action = {Qt.Key_D:'DIVIDE', Qt.Key_W:'GROUP', Qt.Key_Plus:'GROW', Qt.Key_Minus:'SHRINK', Qt.Key_Up:'CONTRAST_UP', Qt.Key_Down:'CONTRAST_DOWN'}.get(key)
                elif shift:
                    action = {Qt.Key_D:'LOWER',Qt.Key_F:'POLYFRAME',Qt.Key_Question:'K'}.get(key)
                else:
                    action = {Qt.Key_B:'PALETTE',Qt.Key_S:'draw_size',Qt.Key_U:'z_intensity',Qt.Key_O:'focal_shift',Qt.Key_I:'z_intensity',Qt.Key_D:'HIGHER',
                              Qt.Key_Space:'QUICK',Qt.Key_Tab:'FOCUS_UI',
                              **{getattr(Qt,'Key_'+x):x for x in ('Q','W','E','R','X','L','K','P','F')}}.get(key)
            if action:
                if is_editable_text_widget(target_widget):
                    return _record_passthrough(str(key),action,target_widget,False,'editable_text_focus')
                ok=_execute_in_view3d(lambda:bpy.ops.landfall_studio.sculpt_shortcut(action=action))
                if action not in ('PALETTE','QUICK','draw_size','focal_shift','z_intensity'): _return_os_focus_to_blender()
                return _record_passthrough(str(key),action,target_widget,ok,'sculpt_shortcut')
            if not ctrl: return None
        elif not ctrl:
            return None

    # Map key + modifiers to (key_label, action_id, callable)
    key_label = None
    action_id = None
    op_fn = None
    focus_back = True

    if ctrl and not alt and not meta:
        if key == Qt.Key_D and not shift and profile == 'MAYA' and bpy.context.mode == 'OBJECT':
            key_label, action_id = 'Ctrl+D', 'landfall_studio.duplicate_objects'
            op_fn = lambda: bpy.ops.landfall_studio.duplicate_objects('EXEC_DEFAULT', True, linked=False)
        elif key == Qt.Key_Z and not shift:
            key_label = "Ctrl+Z"
            action_id = "ed.undo"
            op_fn = lambda: bpy.ops.ed.undo()
        elif (key == Qt.Key_Z and shift) or (key == Qt.Key_Y and not shift):
            key_label = "Ctrl+Shift+Z" if key == Qt.Key_Z else "Ctrl+Y"
            action_id = "ed.redo"
            op_fn = lambda: bpy.ops.ed.redo()
        elif key == Qt.Key_A and not shift:
            key_label = "Ctrl+A"
            action_id = "landfall_studio.cycle_attribute_channels"
            op_fn = lambda: bpy.ops.landfall_studio.cycle_attribute_channels()
            focus_back = False
    elif not ctrl and not alt and not shift and not meta:
        # Bare keys
        fkey_map = {
            Qt.Key_F8: ("F8", "TOGGLE"),
            Qt.Key_F9: ("F9", "VERT"),
            Qt.Key_F10: ("F10", "EDGE"),
            Qt.Key_F11: ("F11", "FACE"),
            Qt.Key_F12: ("F12", "UV"),
        }
        if key in fkey_map:
            k_str, cmode = fkey_map[key]
            key_label = k_str
            action_id = f"landfall_studio.component_mode({cmode})"
            op_fn = lambda m=cmode: bpy.ops.landfall_studio.component_mode(mode=m)
        elif profile == "MAYA":
            tool_map = {
                Qt.Key_Q: ("Q", "SELECT"),
                Qt.Key_W: ("W", "TRANSLATE"),
                Qt.Key_E: ("E", "ROTATE"),
                Qt.Key_R: ("R", "RESIZE"),
            }
            smooth_map = {
                Qt.Key_1: ("1", "CAGE"),
                Qt.Key_2: ("2", "BOTH"),
                Qt.Key_3: ("3", "SMOOTH"),
            }
            if key in tool_map:
                k_str, tmode = tool_map[key]
                key_label = k_str
                action_id = f"landfall_studio.select_tool({tmode})"
                op_fn = lambda t=tmode: bpy.ops.landfall_studio.select_tool(tool=t)
            elif key in (Qt.Key_4, Qt.Key_5, Qt.Key_6, Qt.Key_7):
                key_label = str(key - Qt.Key_0)
                action_id = "landfall_studio.viewport_shading"
                op_fn = lambda m=key_label: bpy.ops.landfall_studio.viewport_shading(mode=m)
            elif key == Qt.Key_S:
                key_label, action_id = "S", "landfall_studio.set_key"
                op_fn = lambda: bpy.ops.landfall_studio.set_key()
            elif key == Qt.Key_Z:
                key_label, action_id = "Z", "ed.undo"
                op_fn = lambda: bpy.ops.ed.undo()
            elif key in smooth_map:
                k_str, smode = smooth_map[key]
                key_label = k_str
                action_id = f"landfall.smooth_preview({smode})"
                op_fn = lambda s=smode: bpy.ops.landfall.smooth_preview(mode=s)
            elif key == Qt.Key_F:
                key_label = "F"
                action_id = "landfall.frame_selected"

                def _frame_sel():
                    if hasattr(bpy.ops, "landfall") and bpy.ops.landfall.frame_selected.poll():
                        return bpy.ops.landfall.frame_selected()
                    return bpy.ops.landfall_studio.frame_all()

                op_fn = _frame_sel
            elif key == Qt.Key_A:
                key_label = "A"
                action_id = "landfall_studio.frame_all"
                op_fn = lambda: bpy.ops.landfall_studio.frame_all()
            elif key == Qt.Key_G:
                key_label = "G"
                action_id = "landfall_studio.repeat_last_command"
                op_fn = lambda: bpy.ops.landfall_studio.repeat_last_command('EXEC_DEFAULT', True)
            elif key == Qt.Key_Y:
                key_label = "Y"
                action_id = "landfall_studio.select_last_tool"
                op_fn = lambda: bpy.ops.landfall_studio.select_last_tool()
            elif key == Qt.Key_Space:
                key_label = "Space"
                action_id = "tentacle.show_marking_menu"
                focus_back = False

                def _hotbox():
                    if hasattr(bpy.ops, "tentacle") and hasattr(
                        bpy.ops.tentacle, "show_marking_menu"
                    ):
                        return bpy.ops.tentacle.show_marking_menu(phase="press")
                    if hasattr(bpy.ops, "landfall") and hasattr(
                        bpy.ops.landfall, "hotbox"
                    ):
                        return bpy.ops.landfall.hotbox()
                    return {"CANCELLED"}

                op_fn = _hotbox

    if profile == "MAYA" and shift and not (ctrl or alt or meta) and key == Qt.Key_Z:
        key_label, action_id = "Shift+Z", "ed.redo"
        op_fn = lambda: bpy.ops.ed.redo()

    if op_fn is None or key_label is None or action_id is None:
        return None

    # Check if focus is inside an active editable text widget
    if is_editable_text_widget(target_widget):
        return _record_passthrough(
            key_name=key_label,
            action=action_id,
            target_widget=target_widget,
            forwarded=False,
            reason="editable_text_focus",
        )

    ok = _execute_in_view3d(op_fn)
    if focus_back:
        _return_os_focus_to_blender()

    return _record_passthrough(
        key_name=key_label,
        action=action_id,
        target_widget=target_widget,
        forwarded=ok,
        reason="forwarded_to_view3d" if ok else "operator_poll_or_exec_declined",
    )


def install_hotkey_filter() -> bool:
    """Install the singleton `QtViewportHotkeyFilter` on `QApplication.instance()`."""
    global _installed_filter
    try:
        from qtpy import QtCore, QtWidgets
    except Exception:
        return False

    app = QtWidgets.QApplication.instance()
    if app is None:
        return False

    if _installed_filter is not None:
        uninstall_hotkey_filter()

    class QtViewportHotkeyFilter(QtCore.QObject):
        """Application-wide Qt event filter forwarding non-text viewport hotkeys to Blender."""

        def __init__(self,parent):
            super().__init__(parent)
            self._keyboard_key=None
            self._keyboard_owner=None
            from .sculpt_input import PointerInput
            self.sculpt_pointer=PointerInput()
            from blendertk.ui_utils.qt_dock import QtDock
            self._dock_predicate=QtDock._interaction_in_flight
            self._pen_predicate=lambda:self.sculpt_pointer.active or self._dock_predicate()
            QtDock._interaction_in_flight=staticmethod(self._pen_predicate)

        def shutdown(self):
            self.sculpt_pointer.shutdown()
            from blendertk.ui_utils.qt_dock import QtDock
            if QtDock._interaction_in_flight is self._pen_predicate:
                QtDock._interaction_in_flight=staticmethod(self._dock_predicate)

        @property
        def passthrough_count(self) -> int:
            return sum(1 for e in _passthrough_history if e.get("forwarded"))

        @property
        def blocked_by_text_focus_count(self) -> int:
            return sum(
                1
                for e in _passthrough_history
                if not e.get("forwarded") and e.get("reason") == "editable_text_focus"
            )

        @property
        def last_passthrough_key(self) -> Optional[str]:
            for e in reversed(_passthrough_history):
                if e.get("forwarded"):
                    return e.get("key")
            return None

        def eventFilter(self, obj, event):
            try:
                etype=event.type()
                if etype in (QtCore.QEvent.KeyRelease,QtCore.QEvent.MouseButtonPress,
                             QtCore.QEvent.TabletPress,QtCore.QEvent.ApplicationDeactivate,
                             QtCore.QEvent.WindowDeactivate):
                    self._keyboard_key=None;self._keyboard_owner=None
                from ..commands.scene_edits import handle_input
                if self.sculpt_pointer.handle(obj,event):
                    handle_input(obj,event)
                    return True
                if handle_input(obj,event):return True
                from .input_policy import handle_wheel, keeps_keyboard
                if handle_wheel(obj,event):return True
                if QtWidgets.QApplication.activePopupWidget() is not None:
                    return False
                if isinstance(obj, QtWidgets.QWidget) and obj.window().objectName() in ("StudioQtMarkingMenu", "ZBrushBrushPalette", "ZBrushCursorSlider", "SculptPicker", "SculptColorPicker"):
                    return False
                if etype == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                    # Qt can propagate one unhandled edit key through each
                    # parent while a foreign native host has no Qt focusWidget.
                    # Keep its original text/picker ownership for this event;
                    # a generic parent must not turn it into a scene command.
                    # Qt/PySide can deliver distinct event wrappers to parents.
                    # Retain the key's originating widget until release; only
                    # its ancestor chain inherits that ownership. A later key
                    # on a different button still reaches the scene normally.
                    origin=self._keyboard_owner
                    if self._keyboard_key==event.key() and origin is not None:
                        try:
                            if obj is origin or (isinstance(obj,QtWidgets.QWidget) and obj.isAncestorOf(origin)):return False
                        except RuntimeError:pass  # The original editor was deleted.
                    self._keyboard_key=None;self._keyboard_owner=None
                    # Ignore synthetic/duplicate deliveries on QWindow when QWidget will receive it
                    if isinstance(obj, QtWidgets.QWidget):
                        if keeps_keyboard(obj,event.key(),event.modifiers()):
                            self._keyboard_key=event.key();self._keyboard_owner=obj
                            return False
                        rec = dispatch_qt_key_to_blender(
                            key=event.key(),
                            modifiers=event.modifiers(),
                            target_widget=obj,
                        )
                        if rec is not None and rec["forwarded"]:
                            event.accept()
                            return True
                        if rec is not None and rec.get('reason')=='editable_text_focus':
                            self._keyboard_key=event.key();self._keyboard_owner=obj
            except Exception:
                pass
            return False

    _installed_filter = QtViewportHotkeyFilter(app)
    app.installEventFilter(_installed_filter)
    return True


def get_hotkey_filter() -> Optional[Any]:
    """Return the active `QtViewportHotkeyFilter` instance, or None."""
    return _installed_filter


def uninstall_hotkey_filter() -> None:
    """Remove the `QtViewportHotkeyFilter` from `QApplication.instance()`."""
    global _installed_filter
    if _installed_filter is None:
        return
    try:
        from qtpy import QtWidgets

        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(_installed_filter)
        _installed_filter.shutdown()
        _installed_filter.deleteLater()
    except Exception:
        pass
    _installed_filter = None


def is_filter_installed() -> bool:
    """Return True if `QtViewportHotkeyFilter` is currently installed on `QApplication`."""
    return _installed_filter is not None

