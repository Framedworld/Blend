"""Bridge for lifecycle-managing the Tentacle Qt host and Switchboard UI in Blender.

Guarantees:
1. Never imports `tentacle.tcl_blender` unless pre-flight checks confirm `PySide6`, `qtpy`,
   `Pillow` (`PIL`), and `numpy` are already installed (preventing `_QtBootstrap.run()` from
   running an unsolicited `pip install` at startup — Conflict C-01).
2. Controls `btk.ScriptConsole.restore()` during `TclBlender.__init__` so `sys.stdout` and
   Blender areas are not hijacked unless `auto_restore_script_console` is enabled (Conflict C-08).
3. Cleanly tears down `_QtHost` event pump timer, `_KeymapBridge` keymaps/operator/poller,
   `SelectionOrder` depsgraph handler, `ScriptConsole`, and retired `MarkingMenu` widgets
   when `landfall_studio.unregister()` runs.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional

from ..bootstrap.deps import check_dependencies

_tcl_instance: Optional[Any] = None
_tentacle_state: str = "UNINITIALIZED"
_pump_timer_fn: Optional[Any] = None
_sculpt_suspended=None

def suspend_sculpt_hotbox(enabled):
    """Pause activation without rebinding/persisting the user's chosen shortcut."""
    global _sculpt_suspended
    module=sys.modules.get('tentacle.tcl_blender');tcl=_tcl_instance
    if not module or not tcl:return
    bridge=module._KeymapBridge
    if enabled and _sculpt_suspended is None:
        _sculpt_suspended=(tcl._on_activation_press,bridge.poller is not None)
        if bridge.gesture_active:bridge.drive_release()
        bridge.uninstall_poller()
        tcl._on_activation_press=lambda *a,**k:None
    elif not enabled and _sculpt_suspended is not None:
        original,had_poller=_sculpt_suspended;tcl._on_activation_press=original
        _sculpt_suspended=None
        if had_poller:bridge.install_poller(tcl,tcl._activation_key_str)


def get_state() -> str:
    """Return current Tentacle bridge state (`UNINITIALIZED`, `DEGRADED_MISSING_DEPS`, `ACTIVE`, `DISABLED`)."""
    return _tentacle_state


def get_tcl_instance() -> Optional[Any]:
    """Return the active `TclBlender` instance, if initialized."""
    return _tcl_instance


def register(
    key_show: str = "Z",
    auto_restore_script_console: bool = False,
    custom_upstream_root: Optional[str] = None,
    custom_deps_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Initialize the Tentacle Qt host and `TclBlender` marking menu if dependencies are ready."""
    global _tcl_instance, _tentacle_state, _pump_timer_fn

    dep_status = check_dependencies(
        custom_upstream_root=custom_upstream_root,
        custom_deps_dir=custom_deps_dir,
    )
    if not dep_status["full_stack_ready"]:
        _tentacle_state = "DEGRADED_MISSING_DEPS"
        return {
            "ok": False,
            "state": _tentacle_state,
            "missing_pip_specs": dep_status["missing_pip_specs"],
        }

    import bpy
    import blendertk as btk
    import tentacle.tcl_blender as tcl_blender

    # uitk's background page warm-up briefly realizes a suppressed full-screen
    # window. Qt can deactivate a live Studio popup even though that window is
    # never painted. Keep this optional work out of Sculpt and all live popups.
    tcl_class = tcl_blender.TclBlender
    if not getattr(tcl_class, '_studio_preload_guarded', False):
        original_preload_next = tcl_class._preload_next
        def _studio_preload_next(self):
            from PySide6 import QtCore, QtWidgets
            if (not self._retired and self._preload_queue and
                    ((_sculpt_suspended is not None and self is _tcl_instance) or
                     QtWidgets.QApplication.activePopupWidget() is not None)):
                QtCore.QTimer.singleShot(1000, self._preload_next)
                return
            return original_preload_next(self)
        tcl_class._preload_next = _studio_preload_next
        tcl_class._studio_preload_guarded = True

    # Capture any timer registered by _QtHost.start_pump so we can unregister it immediately on teardown
    orig_timer_register = bpy.app.timers.register
    captured_timers = []

    def _tracking_timer_register(fn, *args, **kwargs):
        captured_timers.append(fn)
        return orig_timer_register(fn, *args, **kwargs)

    # Optionally suppress unsolicited ScriptConsole.restore() during TclBlender.__init__
    orig_restore = None
    so_mod = None
    if not auto_restore_script_console:
        try:
            from blendertk.env_utils import script_output as so_mod

            orig_restore = so_mod.ScriptConsole.restore
            so_mod.ScriptConsole.restore = classmethod(lambda cls: None)
        except Exception:
            so_mod = None

    bpy.app.timers.register = _tracking_timer_register
    try:
        # Ensure _KeymapBridge._vk_for_key supports multi-letter keys like Key_Space (0x20) on Windows
        if sys.platform == "win32" and not getattr(
            tcl_blender._KeymapBridge, "_studio_vk_patched", False
        ):
            orig_vk_for_key = tcl_blender._KeymapBridge._vk_for_key
            extra_vk_map = {
                "SPACE": 0x20,
                "TAB": 0x09,
                "ACCENT_GRAVE": 0xC0,
                "QUOTELEFT": 0xC0,
            }

            def _studio_vk_for_key(ks):
                res = orig_vk_for_key(ks)
                if res is not None:
                    return res
                norm_name = (ks or "").replace("Key_", "").upper()
                return extra_vk_map.get(norm_name)

            tcl_blender._KeymapBridge._vk_for_key = staticmethod(_studio_vk_for_key)
            tcl_blender._KeymapBridge._studio_vk_patched = True

        app = tcl_blender._QtHost.ensure_qapp()
        tcl_blender._QtHost.ensure_widget(app)
        tcl_blender._QtHost.start_pump(app)
        for fn in captured_timers:
            if getattr(fn, "__name__", "") == "_pump":
                _pump_timer_fn = fn

        if tcl_blender._KeymapBridge.tcl is not None:
            _tcl_instance = tcl_blender._KeymapBridge.tcl
            set_activation_key(key_show)
        else:
            _tcl_instance = tcl_blender.TclBlender(key_show=key_show)
    finally:
        bpy.app.timers.register = orig_timer_register
        if so_mod is not None and orig_restore is not None:
            so_mod.ScriptConsole.restore = orig_restore

    _tentacle_state = "ACTIVE"
    return {
        "ok": True,
        "state": _tentacle_state,
        "tcl_class": type(_tcl_instance).__name__ if _tcl_instance is not None else None,
        "key_show": key_show,
    }


def set_activation_key(key_show: str) -> bool:
    """Rebind the live Tentacle instance's activation key (both Qt chord table and Blender 3D View keymap)."""
    if _tcl_instance is None:
        return False
    tb_mod = sys.modules.get("tentacle.tcl_blender")
    qt_key = key_show if key_show.startswith("Key_") else f"Key_{key_show.capitalize() if len(key_show) > 1 and not (key_show[0].upper() == 'F' and key_show[1:].isdigit()) else key_show.upper()}"
    try:
        _tcl_instance.set_activation_key(qt_key)
        if tb_mod is not None:
            tb_mod._KeymapBridge.rebind(_tcl_instance, qt_key)
        return True
    except Exception as exc:
        print(f"[landfall_studio] set_activation_key({qt_key}) warning: {exc}")
        return False


def get_activation_key_info() -> Dict[str, Any]:
    """Return diagnostic details on Tentacle's current Blender & Qt activation key binding."""
    tb_mod = sys.modules.get("tentacle.tcl_blender")
    if tb_mod is None or _tcl_instance is None:
        return {
            "active": False,
            "addon_key_type": None,
            "active_vk": None,
            "qt_key": None,
        }
    return {
        "active": True,
        "addon_key_type": tb_mod._KeymapBridge.addon_key_type(),
        "active_vk": tb_mod._KeymapBridge.active_vk,
        "qt_key": getattr(_tcl_instance, "_activation_key_str", None),
        "keymap_count": len(tb_mod._KeymapBridge.keymaps),
    }


def show_window_for_test(ui_name: str = "polygons") -> Dict[str, Any]:
    """Open and pump a real Tentacle Qt Switchboard tool window (`polygons` by default) for GUI verification."""
    if _tcl_instance is None:
        raise RuntimeError("Tentacle is not initialized.")

    from qtpy import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance()
    ui_widget = _tcl_instance.get(ui_name)
    _tcl_instance.show(ui_name)
    if ui_widget is not None and not ui_widget.isVisible():
        ui_widget.show()

    QtCore.QCoreApplication.sendPostedEvents()
    QtCore.QCoreApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)

    target = ui_widget if ui_widget is not None else _tcl_instance
    visible = bool(target.isVisible())
    win_id = int(target.winId()) if visible else 0
    geom = target.geometry()
    size = (geom.width(), geom.height())
    child_buttons = len(target.findChildren(QtWidgets.QAbstractButton))

    return {
        "ui_name": ui_name,
        "visible": visible,
        "win_id": win_id,
        "size": size,
        "window_title": target.windowTitle() or target.objectName() or ui_name,
        "child_button_count": child_buttons,
        "qapp_exists": app is not None,
        "has_switchboard": getattr(_tcl_instance, "sb", None) is not None,
        "_widget": target,
    }


def hide_window() -> None:
    """Hide active Tentacle Qt windows if visible."""
    if _tcl_instance is not None:
        try:
            for win in list(getattr(_tcl_instance.sb, "visible_windows", [])):
                try:
                    win.hide()
                except Exception:
                    pass
            _tcl_instance.hide()
            from qtpy import QtCore

            QtCore.QCoreApplication.sendPostedEvents()
        except Exception:
            pass


def unregister() -> None:
    """Cleanly tear down Tentacle keymaps, pollers, timers, handlers, and console hooks."""
    global _tcl_instance, _tentacle_state, _pump_timer_fn

    import bpy

    # 1. Retire MarkingMenu instances & reset ScriptJobManager if tentacle is loaded
    tcl_mod = sys.modules.get("tentacle.tcl")
    retired = []
    if tcl_mod is not None:
        try:
            retired = tcl_mod.Tcl.prepare_reload("blender")
        except Exception:
            pass

    # 2. Tear down _KeymapBridge (keymaps, operator, poller timer)
    tb_mod = sys.modules.get("tentacle.tcl_blender")
    if tb_mod is not None:
        try:
            tb_mod._KeymapBridge.teardown()
        except Exception:
            pass
        try:
            tb_mod._ClickDebugger.disable()
        except Exception:
            pass

        # Stop _QtHost pump timer immediately
        try:
            from qtpy import QtCore, QtWidgets

            app = QtWidgets.QApplication.instance()
            if app is not None:
                app._tentacle_pump_token = None
            tb_mod._QtHost._pump_registered = False
        except Exception:
            pass

    if _pump_timer_fn is not None:
        try:
            if bpy.app.timers.is_registered(_pump_timer_fn):
                bpy.app.timers.unregister(_pump_timer_fn)
        except Exception:
            pass
        _pump_timer_fn = None

    # 3. Tear down ScriptConsole if instantiated (restores sys.stdout / sys.stderr)
    so_mod = sys.modules.get("blendertk.env_utils.script_output")
    if so_mod is not None:
        try:
            console = getattr(so_mod.ScriptConsole, "_instance", None)
            if console is not None:
                console.teardown()
        except Exception:
            pass

    # 4. Disable SelectionOrder depsgraph handler if enabled
    sel_mod = sys.modules.get("blendertk.edit_utils.selection")
    if sel_mod is not None:
        try:
            sel_mod.SelectionOrder.disable()
        except Exception:
            pass

    # 5. Dispose retired MarkingMenu instances and flush DeferredDelete events
    if tcl_mod is not None and retired:
        try:
            tcl_mod.Tcl.dispose_retired(retired)
            from qtpy import QtCore

            QtCore.QCoreApplication.sendPostedEvents(
                None, QtCore.QEvent.DeferredDelete
            )
        except Exception:
            pass

    _tcl_instance = None
    _tentacle_state = "DISABLED"
