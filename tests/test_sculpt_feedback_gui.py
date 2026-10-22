"""Disposable native checks for Alt zoom, optional grid and live pen feedback."""
import bpy,sys,json,traceback,ctypes,os
from pathlib import Path
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/sculpt_feedback_gui_results.json'
results={'passed':[],'failed':[],'input_method':'Native Blender events, live OS tip position, native viewport captures'}
def check(name,value,detail=None):
    results['passed' if value else 'failed'].append(name if value else {'test':name,'detail':detail});save()
def save():OUT.write_text(json.dumps(results,indent=2,default=str))
def ctx():
    from landfall_studio.sculpt import ops
    return ops.view_context()
def event(kind,value='PRESS',xy=(30,50),**mods):
    c=ctx();r=c['region'];c['window'].event_simulate(type=kind,value=value,x=int(r.x+xy[0]),y=int(r.y+xy[1]),**mods)
def tip(xy):
    from blendertk.ui_utils.blender_window import BlenderWindow
    c=ctx();r=c['region'];origin=BlenderWindow.client_origin(BlenderWindow.window_hwnd(c['window']))
    moved=ctypes.windll.user32.SetCursorPos(int(origin[0]+r.x+xy[0]),int(origin[1]+c['window'].height-1-r.y-xy[1]))
    results.setdefault('pointer_moves',[]).append(bool(moved))
def capture(name):
    with bpy.context.temp_override(**ctx()):bpy.ops.screen.screenshot(filepath=str(ROOT/'output'/name))
def zoom(delta):
    start=(50,100);event('LEFT_ALT',alt=True);event('MOUSEMOVE','NOTHING',start,alt=True);event('LEFTMOUSE',xy=start,alt=True);yield .1
    event('LEFT_ALT','RELEASE',start)
    for i in range(1,5):event('MOUSEMOVE','NOTHING',(start[0]+delta[0]*i/4,start[1]+delta[1]*i/4));yield .05
    event('LEFTMOUSE','RELEASE',(start[0]+delta[0],start[1]+delta[1]));yield .2
def suite():
    import landfall_studio
    landfall_studio.register()
    from landfall_studio.ui import desktop
    from landfall_studio import sculpt
    from landfall_studio.sculpt import ops,state,brushes,gestures,preferences
    from blendertk.ui_utils.blender_window import BlenderWindow
    preferences.PATH=ROOT.parent/('.test_env/sculpt_feedback_preferences_'+str(os.getpid())+'.json');preferences._data=None
    desktop.restore_workspace_desktop();yield .5
    c=ctx();hwnd=BlenderWindow.window_hwnd(c['window']);ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd)
    from ctypes import wintypes
    saved_pointer=wintypes.POINT();ctypes.windll.user32.GetCursorPos(ctypes.byref(saved_pointer))
    with bpy.context.temp_override(**ctx()):
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24)
        body=bpy.context.object;body.name='Cursor feedback surface'
        for polygon in body.data.polygons:polygon.use_smooth=True
        bpy.ops.view3d.view_axis(type='FRONT');bpy.context.space_data.region_3d.view_distance=6
        bpy.context.scene.landfall_grid_finite=True
        overlay=bpy.context.space_data.overlay
        fields=('show_floor','show_ortho_grid','show_axis_x','show_axis_y','show_axis_z')
        for field,value in zip(fields,(False,True,False,True,True)):setattr(overlay,field,value)
        original={f:getattr(overlay,f) for f in fields}
        sculpt.enter()
    yield 1
    c=ctx();overlay=c['area'].spaces.active.overlay
    check('ordinary Sculpt entry defaults all grid and axes off',not bpy.context.scene.landfall_grid_finite and not any(getattr(overlay,f) for f in fields),{'finite':bpy.context.scene.landfall_grid_finite,**{f:getattr(overlay,f) for f in fields}})
    with bpy.context.temp_override(**c):ops.run('FLOOR')
    yield .3
    check('grid can be enabled explicitly',bpy.context.scene.landfall_grid_finite)
    sculpt.sync_mode();yield .3
    check('sculpt polling preserves optional grid choice',bpy.context.scene.landfall_grid_finite)
    with bpy.context.temp_override(**ctx()):ops.run('FLOOR')
    yield .3
    check('grid toggle off leaves no infinite or orthographic grid',not bpy.context.scene.landfall_grid_finite and not any(getattr(overlay,f) for f in fields))
    rv=ctx()['area'].spaces.active.region_3d
    distance=rv.view_distance;yield from zoom((-30,-35))
    check('Alt-release pull away zooms in',rv.view_distance<distance,{'before':distance,'after':rv.view_distance})
    distance=rv.view_distance;yield from zoom((35,40))
    check('Alt-release push toward model zooms out',rv.view_distance>distance,{'before':distance,'after':rv.view_distance})
    with bpy.context.temp_override(**ctx()):
        bpy.ops.view3d.view_axis(type='FRONT');rv.view_location=(0,0,0);rv.view_distance=6
        brushes.select('ST');state.get().draw_size=42;state.get().z_intensity=65
        ops.layer('NEW',name='Tip feedback layer');bpy.ops.ed.undo_push(message='Cursor feedback stroke')
    yield .3
    c=ctx();r=c['region'];p=location_3d_to_region_2d(r,rv,Vector((-.25,-.95,.15)));p=(int(p.x),int(p.y))
    tip(p);event('MOUSEMOVE','NOTHING',p);yield .2
    with bpy.context.temp_override(**ctx()):hover=gestures.cursor_for_draw(bpy.context)
    check('hover uses ring and center crosshair presentation',not hover['pressed'] and hover['area']==c['area'].as_pointer())
    capture('sculpt_feedback_hover.png')
    before=[v.co.copy() for v in body.active_shape_key.data]
    event('LEFTMOUSE',xy=p);yield .15
    samples=[]
    for i in range(1,5):
        point=(p[0]+i*12,p[1]+i*3);event('MOUSEMOVE','NOTHING',point);yield .08
        # Sample immediately after positioning: a live user can move the
        # desktop pointer during the yielded native event interval.
        tip(point)
        with bpy.context.temp_override(**ctx()):pose=gestures.cursor_for_draw(bpy.context)
        samples.append({'expected':point,'actual':pose['xy'],'pressed':pose['pressed']})
    results['tip_samples']=samples
    results['stroke_modals']=[op.bl_idname for op in ctx()['window'].modal_operators]
    check('native paint stroke is active during feedback check','SCULPT_OT_brush_stroke' in results['stroke_modals'])
    check('held crosshair follows pen tip through native stroke',all(s['pressed'] and max(abs(a-b) for a,b in zip(s['actual'],s['expected']))<=1 for s in samples),samples)
    capture('sculpt_feedback_held.png')
    event('LEFTMOUSE','RELEASE',point);yield .25
    with bpy.context.temp_override(**ctx()):released=gestures.cursor_for_draw(bpy.context)
    check('release restores brush rings',not released['pressed'])
    check('feedback preserves actual native shape-layer stroke',any((v.co-co).length>1e-6 for v,co in zip(body.active_shape_key.data,before)))
    capture('sculpt_feedback_released.png')
    with bpy.context.temp_override(**ctx()):sculpt.return_to_maya()
    yield .5
    overlay=ctx()['area'].spaces.active.overlay
    check('Maya return restores its exact grid and axis state',bpy.context.scene.landfall_grid_finite and all(getattr(overlay,f)==v for f,v in original.items()),{f:getattr(overlay,f) for f in fields})
    with bpy.context.temp_override(**ctx()):sculpt.enter()
    yield .5
    check('reentering Sculpt starts grid off again',not bpy.context.scene.landfall_grid_finite and not any(getattr(ctx()['area'].spaces.active.overlay,f) for f in fields))
    ctypes.windll.user32.SetCursorPos(saved_pointer.x,saved_pointer.y)
    landfall_studio.unregister();save();bpy.ops.wm.quit_blender()
gen=None
def tick():
    try:return next(gen)
    except StopIteration:return None
    except Exception:results['failed'].append(traceback.format_exc());save();bpy.ops.wm.quit_blender();return None
def start():
    global gen
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile();gen=suite();bpy.app.timers.register(tick,persistent=True)
bpy.app.timers.register(start,first_interval=.5)
