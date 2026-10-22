"""A dense native Multires/GPU silhouette check in a disposable GUI."""
import bpy,os,sys,json,traceback,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
result={'ok':False,'input_method':'Native GUI redraws and synthetic keyboard events'}
OUT=ROOT/'output/zbrush_density_results.json'
def save():OUT.write_text(json.dumps(result,indent=2,default=str))
def scene():
    import landfall_studio
    from landfall_studio.ui import desktop,viewport_bar
    from landfall_studio.sculpt import ops
    from landfall_studio.sculpt.demo import create_demo
    landfall_studio.register();desktop.restore_workspace_desktop()
    create_demo()
    from blendertk.ui_utils.blender_window import BlenderWindow
    import ctypes
    hwnd=BlenderWindow.window_hwnd(bpy.context.window_manager.windows[0])
    ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd)
    with bpy.context.temp_override(**ops.view_context()):
        ops.divide();ops.divide()
    for _ in range(8):
        for area in bpy.context.window_manager.windows[0].screen.areas:area.tag_redraw()
        yield .25
    bar=viewport_bar.get_bars()[0];canvas=bar.sculpt_canvas
    initial=canvas.render_calls
    result.update(sculpt_mode=bpy.context.mode,canvas_visible=canvas.root.isVisible(),silhouette_visible=canvas.silhouette.isVisible())
    with bpy.context.temp_override(**bar.context()):
        r=bar.context()['region'];w=bar.window
        for k in ('W','E','R','Q'):
            w.event_simulate(type=k,value='PRESS',x=r.x+r.width//2,y=r.y+r.height//2)
            w.event_simulate(type=k,value='RELEASE',x=r.x+r.width//2,y=r.y+r.height//2)
    yield 1.0
    result.update(triangles=canvas.silhouette.polygons,redraws=canvas.render_calls-initial,
        last_capture_ms=canvas.last_render_ms,max_capture_ms=canvas.max_render_ms,
        native_tool=bar.window.workspace.tools.from_space_view3d_mode('SCULPT',create=False).idname)
    image=canvas.silhouette.image
    result['ok']=bool(result['triangles']>200000 and result['redraws']>0 and image is not None and result['native_tool']=='builtin.brush')
    from PySide6 import QtGui
    # Hidden-desktop runs (LANDFALL_NO_OS_INPUT) must not copy screen pixels: they
    # would come from the artist's visible desktop, not this window.
    if not os.environ.get('LANDFALL_NO_OS_INPUT'):QtGui.QGuiApplication.primaryScreen().grabWindow(int(bar.hwnd)).save(str(ROOT/'output/zbrush_dense_window.png'))
    save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
generator=None
def tick():
    try:return next(generator)
    except StopIteration:return None
    except Exception:
        result['error']=traceback.format_exc();save();print(result['error']);bpy.ops.wm.quit_blender();return None
def start():
    global generator
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
    generator=scene();bpy.app.timers.register(tick,first_interval=.5,persistent=True)
bpy.app.timers.register(start,first_interval=.5)
