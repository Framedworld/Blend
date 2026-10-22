"""Open the workspace's Studio desktop and leave Blender running for interactive use."""

import json
import sys
import time
import traceback
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORT = ROOT / "output" / "interactive_startup.json"
state = {"ok": False, "pid": __import__("os").getpid()}


def write_report():
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(state, indent=2), encoding="utf-8")


def verify_open():
    from landfall_studio.adapters import tentacle_bridge
    from landfall_studio.ui import viewport_bar
    import qtpy
    qt_active = tentacle_bridge.get_state() == "ACTIVE" and qtpy.API_NAME == "PySide6"
    bars = viewport_bar.get_bars()
    state.update(
        ok=bool(qt_active and bars and all(b.root.isVisible() for b in bars)),
        verified_at=time.time(),
        windows=len(bpy.context.window_manager.windows),
        tentacle_state=tentacle_bridge.get_state(),
        qt_binding=qtpy.API_NAME,
        viewport_bars=len(bars),
    )
    if '--sculpt-demo' in sys.argv:
        from landfall_studio import sculpt
        from landfall_studio.ui import desktop
        from landfall_studio.sculpt import ops
        state.update(sculpt_active=sculpt.is_engaged(),right_dock=desktop._right_dock.mode,
            active_subtool=bpy.context.view_layer.objects.active.name,subtools=len(ops.meshes()))
        from landfall_studio.ui.hotkey_passthrough import get_hotkey_filter
        owner=get_hotkey_filter();pointer=getattr(owner,'sculpt_pointer',None)
        state.update(pen_input_active=pointer is not None,pen_ui_windows=len(pointer.native) if pointer else 0)
        state['ok']=state['ok'] and state['sculpt_active'] and state['right_dock']=='ZBRUSH_STUDIO' and state['pen_input_active']
    write_report()
    if "--audit-capture" in sys.argv and bars:
        bars[0].root.grab().save(str(ROOT / "output" / "interactive_viewport_bar.png"))
        bars[0].menubar.grab().save(str(ROOT / "output" / "interactive_viewport_menus.png"))
        if "--sculpt-demo" in sys.argv:
            from PySide6 import QtGui
            from blendertk.ui_utils.blender_window import BlenderWindow
            hwnd=BlenderWindow.window_hwnd(bars[0].window)
            QtGui.QGuiApplication.primaryScreen().grabWindow(int(hwnd)).save(str(ROOT/'output/zbrush_demo_window.png'))
    print("LANDFALL_INTERACTIVE_READY:" + json.dumps(state), flush=True)
    return None


def open_studio():
    try:
        # This launcher starts a fresh factory scene. Close Blender's startup
        # splash before adding foreign Qt child windows over the canvas: an
        # obscured splash otherwise keeps consuming every viewport key/click.
        bpy.context.preferences.view.show_splash = False
        bpy.ops.wm.read_homefile(use_empty=False)
        import landfall_studio
        from landfall_studio import ui
        landfall_studio.register()
        bpy.context.preferences.view.show_splash = False
        state["desktop"] = ui.restore_workspace_desktop(restore_script_output=False)
        if "--sculpt-demo" in sys.argv:
            from landfall_studio.sculpt.demo import create_demo
            state['sculpt_demo']=create_demo()
            if '--save-sculpt-demo' in sys.argv:
                name='sculpt_ux2_demo.blend' if '--sculpt-ux2' in sys.argv else 'zbrush_sculpt_demo.blend'
                bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output'/name))
        import ctypes
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow
        hwnd = BlenderWindow.window_hwnd(btk.main_window())
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 3)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        state["opened_at"] = time.time()
        write_report()
        bpy.app.timers.register(verify_open, first_interval=20.0)
    except Exception:
        state["error"] = traceback.format_exc()
        write_report()
        traceback.print_exc()
    return None


bpy.app.timers.register(open_studio, first_interval=0.5)
