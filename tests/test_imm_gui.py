"""IMM brush through real viewport events: drag-insert, undo, blank-click picker, orbit."""
import bpy,sys,json,traceback,os
from pathlib import Path
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_UX_TEST_TAG','')
OUT=ROOT/'output'/('imm_gui'+TAG+'.json')
results={'passed':[],'failed':[],'input_method':'Blender event_simulate in a disposable factory GUI; synthetic, not a physical pen','observations':{}}

def save():OUT.write_text(json.dumps(results,indent=2,default=str))
def check(name,value,detail=None):
    results['passed' if value else 'failed'].append(name if value else {'test':name,'detail':detail});save()
def ctx():
    w=bpy.context.window_manager.windows[0];a=next(a for a in w.screen.areas if a.type=='VIEW_3D');r=next(r for r in a.regions if r.type=='WINDOW')
    return {'window':w,'area':a,'region':r}
def ev(kind,value='PRESS',xy=None,**mods):
    c=ctx();r=c['region'];x,y=xy or (r.x+r.width//2,r.y+r.height//2)
    c['window'].event_simulate(type=kind,value=value,x=int(x),y=int(y),**mods)
def pos(world):
    c=ctx();p=location_3d_to_region_2d(c['region'],c['area'].spaces.active.region_3d,world);r=c['region'];return (r.x+p.x,r.y+p.y)
def drag(start,end):
    ev('MOUSEMOVE','NOTHING',start);ev('LEFTMOUSE',xy=start);yield .1
    for i in range(1,9):
        ev('MOUSEMOVE','NOTHING',(start[0]+(end[0]-start[0])*i/8,start[1]+(end[1]-start[1])*i/8));yield .05
    ev('LEFTMOUSE','RELEASE',end);yield .3

def suite():
    import landfall_studio
    from landfall_studio.ui import desktop,zbrush_panel
    from landfall_studio.sculpt import state,brushes,ops,gestures
    from landfall_studio import sculpt
    landfall_studio.register();desktop.restore_workspace_desktop()
    from landfall_studio.sculpt import preferences
    preferences.PATH=ROOT.parent/('.test_env/imm_gui_preferences_'+str(os.getpid())+'.json');preferences._data=None
    yield 1.5
    with bpy.context.temp_override(**ctx()):
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=1.0)
        body=bpy.context.object;body.name='IMM Body'
        bpy.ops.view3d.view_axis(type='FRONT');ctx()['area'].spaces.active.region_3d.view_distance=6
        # Python-run setup operators record no history; checkpoint it so the
        # Undo under test can only remove the insert.
        bpy.ops.ed.undo_push(message='IMM fixture')
        bpy.ops.object.mode_set(mode='SCULPT')
        bpy.ops.ed.undo_push(message='IMM fixture sculpt')
    yield 1
    check('Studio engages for sculpting',sculpt.is_engaged())
    with bpy.context.temp_override(**ops.view_context()):brushes.select('IMM Primitives')
    state.get().imm_part='CUBE'
    yield .3
    before=set(bpy.data.objects.keys())
    centre=pos(Vector((0,-1,0)))
    yield from drag(centre,(centre[0]+60,centre[1]))
    added=[bpy.data.objects[n] for n in set(bpy.data.objects.keys())-before]
    check('drag on the surface inserts exactly one part',len(added)==1,[o.name for o in added])
    if added:
        part=added[0]
        axis=(part.matrix_world.to_3x3()@Vector((0,0,1))).normalized()
        check('part follows the surface normal',axis.dot(Vector((0,-1,0)))>0.95,tuple(axis))
        check('part sits on the surface where the drag started',(part.matrix_world.translation-Vector((0,-1,0))).length<0.08,tuple(part.matrix_world.translation))
        check('drag radius sets the part size',0.15<max(part.dimensions)<1.5,tuple(part.dimensions))
        check('sculpted SubTool stays active in Sculpt',bpy.context.view_layer.objects.active==body and bpy.context.mode=='SCULPT')
        results['observations']['part']={'name':part.name,'dimensions':tuple(part.dimensions)}
    ev('Z',ctrl=True);ev('Z','RELEASE',ctrl=True);yield .6
    check('one Undo removes the inserted part',set(bpy.data.objects.keys())==before,sorted(set(bpy.data.objects.keys())-before))
    check('Undo keeps sculpting the original SubTool',bpy.context.mode=='SCULPT' and bpy.context.view_layer.objects.active.name=='IMM Body')
    check('Undo keeps the chosen brush and part (tool state is not undone)',
          state.get().active_zbrush_brush=='IMM Primitives' and state.get().imm_part=='CUBE',
          (state.get().active_zbrush_brush,state.get().imm_part))
    # A plain click on empty canvas opens the part picker; a drag there orbits.
    r=ctx()['region'];blank=(r.x+40,r.y+r.height-60)
    ev('MOUSEMOVE','NOTHING',blank);ev('LEFTMOUSE',xy=blank);ev('LEFTMOUSE','RELEASE',xy=blank);yield .4
    results['observations']['blank_click_history']=gestures.history[-4:]
    results['observations']['popups']=[(m.objectName(),m.isVisible()) for m in zbrush_panel._popups]
    picker=next((m for m in zbrush_panel._popups if m.objectName()=='SculptPicker' and m.isVisible()),None)
    labels=[a.text() for a in picker.actions()] if picker else []
    check('blank click opens the IMM part picker',picker is not None and 'Add Active SubTool as Part' in labels,labels)
    check('picker marks the current part',any(l.startswith('● ') and 'Cube' in l for l in labels),labels)
    if picker:picker.close()
    yield .2
    rotation=ctx()['area'].spaces.active.region_3d.view_rotation.copy()
    yield from drag(blank,(blank[0]+120,blank[1]-40))
    check('blank drag still orbits with the IMM brush',ctx()['area'].spaces.active.region_3d.view_rotation!=rotation)
    check('blank drag inserts nothing',set(bpy.data.objects.keys())==before)
    # Insert into the current SubTool: joins, masks the existing surface.
    state.get().imm_into_subtool=True
    with bpy.context.temp_override(**ctx()):bpy.ops.ed.undo_push(message='IMM join fixture')
    verts=len(body.data.vertices)
    centre=pos(Vector((0,-1,0)))
    yield from drag(centre,(centre[0]+50,centre[1]))
    check('into-SubTool insert adds no object',set(bpy.data.objects.keys())==before,sorted(set(bpy.data.objects.keys())-before))
    joined=len(body.data.vertices)
    check('into-SubTool insert joins the part geometry',joined==verts+8,(verts,joined))
    mask=body.data.attributes.get('.sculpt_mask')
    check('existing surface is masked, part is free',mask is not None and mask.data[0].value==1.0 and mask.data[joined-1].value==0.0)
    with bpy.context.temp_override(**ctx()):bpy.ops.paint.mask_flood_fill(mode='INVERT')
    yield .2
    mask=body.data.attributes.get('.sculpt_mask')
    check('Sculpt mode uses the same mask data (native invert flips it)',mask is not None and mask.data[0].value==0.0 and mask.data[joined-1].value==1.0)
    ev('Z',ctrl=True);ev('Z','RELEASE',ctrl=True);yield .6
    ev('Z',ctrl=True);ev('Z','RELEASE',ctrl=True);yield .6
    restored=bpy.data.objects['IMM Body']  # global Undo reloads objects; old references are stale
    check('Undo removes the joined part',len(restored.data.vertices)==verts,(len(restored.data.vertices),verts))
    landfall_studio.unregister()
    results['ok']=not results['failed'];save()
    print('IMM_GUI_RESULTS',len(results['passed']),'passed',len(results['failed']),'failed')
    bpy.ops.wm.quit_blender()

generator=None
def tick():
    global generator
    try:return next(generator)
    except StopIteration:return None
    except Exception:
        check('suite exception',False,traceback.format_exc());print(traceback.format_exc());bpy.ops.wm.quit_blender();return None
def start():
    global generator
    bpy.context.preferences.view.show_splash=False
    bpy.ops.wm.read_homefile()
    generator=suite();bpy.app.timers.register(tick,first_interval=.5,persistent=True)
    return None
bpy.app.timers.register(start,first_interval=.5)
