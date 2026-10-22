"""Stage-by-stage disposable desktop presentation probe."""
import bpy,sys,ctypes,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent/'.deps/py313')]
from PIL import ImageGrab
def shot(name):
    import gpu
    ImageGrab.grab(all_screens=True).save(str(ROOT/'output'/('presentation_'+gpu.platform.backend_type_get().lower()+'_'+name+'.png')))
def stages():
    import os
    from ctypes import wintypes
    handles=[]
    @ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def enum(h,_):
        p=wintypes.DWORD();ctypes.windll.user32.GetWindowThreadProcessId(h,ctypes.byref(p))
        if p.value==os.getpid() and ctypes.windll.user32.IsWindowVisible(h):handles.append(h)
        return True
    ctypes.windll.user32.EnumWindows(enum,0);ctypes.windll.user32.ShowWindow(handles[0],3);ctypes.windll.user32.SetForegroundWindow(handles[0])
    yield 1
    shot('0_bare')
    import landfall_studio
    landfall_studio.register();yield 1
    from landfall_studio.sculpt import preferences
    preferences.PATH=ROOT.parent/'.test_env/presentation_probe_preferences.json';preferences._data=None
    shot('1_registered')
    from landfall_studio.ui import desktop
    desktop.restore_workspace_desktop();yield 1
    shot('2_maya')
    from landfall_studio.sculpt.demo import create_demo
    create_demo();yield 1
    shot('3_sculpt')
    from PySide6 import QtWidgets
    shown=[w for w in QtWidgets.QApplication.topLevelWidgets() if w.isVisible()]
    for w in shown:w.hide()
    yield 1
    shot('4_hidden')
    import gpu
    (ROOT/'output/presentation_backend.json').write_text(json.dumps(dict(backend=gpu.platform.backend_type_get(),device=gpu.platform.renderer_get())))
    bpy.ops.wm.quit_blender()
gen=None
def tick():
    try:return next(gen)
    except StopIteration:return None
def start():
    global gen
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile();gen=stages();bpy.app.timers.register(tick,persistent=True)
bpy.app.timers.register(start,first_interval=.5)
