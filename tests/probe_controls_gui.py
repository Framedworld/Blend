"""Probe actual OS input in a disposable factory Blender window."""
import ctypes
import json
import sys
import traceback
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
out = ROOT / "output" / "controls_probe.json"
report = {"checks": {}}
step = 0


class STUDIO_OT_input_probe(bpy.types.Operator):
    bl_idname = "wm.studio_input_probe"
    bl_label = "Temporary input observer"

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'Q', 'W', 'E', 'R'}:
            report.setdefault('events', []).append([event.type, event.value,
                event.mouse_x, event.mouse_y, str(context.area.type) if context.area else None])
        return {'PASS_THROUGH'}


def tick():
    global step, win, area, region, hwnd
    try:
        import landfall_studio
        from landfall_studio import commands, ui
        from landfall_studio.ui import menus
        if step == 0:
            bpy.context.preferences.view.show_splash = False
            bpy.ops.wm.read_homefile()
            landfall_studio.register()
            ui.restore_workspace_desktop(restore_script_output=False)
        from blendertk.ui_utils.blender_window import BlenderWindow
        if step == 0:
            from qtpy import API_NAME, QT_VERSION
            report["qt"] = [API_NAME, QT_VERSION]
            win = bpy.context.window_manager.windows[0]
            hwnd = BlenderWindow.window_hwnd(win)
            ctypes.windll.user32.ShowWindow(hwnd, 3)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        elif step == 1:
            ov = menus.view3d_override()
            area, region = ov["area"], ov["region"]
            origin = (ctypes.c_long * 2)(0, 0)
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(origin))
            ctypes.windll.user32.SetCursorPos(origin[0] + region.x + region.width // 2,
                                             origin[1] + win.height - region.y - region.height // 2)
            BlenderWindow.set_keyboard_focus(hwnd)
            bpy.utils.register_class(STUDIO_OT_input_probe)
            with bpy.context.temp_override(**ov):
                bpy.ops.wm.studio_input_probe('INVOKE_DEFAULT')
            inp = bpy.context.preferences.inputs
            report["inputs"] = {p.identifier: getattr(inp, p.identifier) for p in inp.bl_rna.properties
                                if "zoom" in p.identifier or "rotate" in p.identifier}
            report["bindings"] = []
            for km in bpy.context.window_manager.keyconfigs.user.keymaps:
                if km.name in ("Object Mode", "Mesh", "3D View") or km.name.startswith("3D View Tool"):
                    for k in km.keymap_items:
                        if k.type in ("Q", "W", "E", "R", "LEFTMOUSE") and k.active:
                            report["bindings"].append([km.name, k.idname, k.type, k.value,
                                k.ctrl, k.shift, k.alt, k.any])
        elif 2 <= step <= 9:
            key = "QWER"[(step - 2) // 2]
            if step % 2 == 0:
                x, y = region.x + region.width // 2, region.y + region.height // 2
                win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
                win.cursor_warp(x, y)
                win.event_simulate(type=key, value='PRESS', unicode=key.lower(), x=x, y=y)
                win.event_simulate(type=key, value='RELEASE', x=x, y=y)
            else:
                sp = area.spaces.active
                report["checks"][key] = {"studio_tool": commands.get_active_tool(),
                    "native_tool": win.workspace.tools.from_space_view3d_mode(bpy.context.mode, create=False).idname,
                    "gizmos": [sp.show_gizmo_object_translate, sp.show_gizmo_object_rotate, sp.show_gizmo_object_scale]}
        else:
            with bpy.context.temp_override(**menus.view3d_override()):
                bpy.ops.screen.screenshot(filepath=str(ROOT / "output" / "controls_native_frame.png"))
            from PIL import ImageGrab
            rect = (ctypes.c_long * 4)()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            ImageGrab.grab(bbox=tuple(rect)).save(str(ROOT / "output" / "controls_probe.png"))
            out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
            bpy.ops.wm.quit_blender()
            return None
        out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        step += 1
        return 1.0 if step > 1 else 2.0
    except Exception:
        report["error"] = traceback.format_exc()
        out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=0.5, persistent=True)
