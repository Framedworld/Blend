"""Regression: in the launched sculpt demo, Undo after strokes + an IMM insert removes only the part,
keeps the strokes, and steps back through them (found in a real on-screen session)."""
import bpy,sys,json,traceback,os,hashlib
from pathlib import Path
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_UX_TEST_TAG','')
OUT=ROOT/'output'/('imm_undo_gui'+TAG+'.json')
report={'steps':[],'passed':[],'failed':[]}
def save():OUT.write_text(json.dumps(report,indent=2,default=str))
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
    ev('LEFTMOUSE','RELEASE',end);yield .4
def check(name,value,detail=None):
    report['passed' if value else 'failed'].append(name if value else {'test':name,'detail':detail});save()
def snap(label):
    body=bpy.data.objects.get('Creature_Sculpt')
    digest=None
    if body is not None:
        coords=[0.0]*(len(body.data.vertices)*3);body.data.vertices.foreach_get('co',coords)
        digest=hashlib.sha1(json.dumps([round(c,5) for c in coords]).encode()).hexdigest()[:10]
        keys=[(k.name,hashlib.sha1(json.dumps([round(c,5) for p in k.data for c in p.co]).encode()).hexdigest()[:10]) for k in (body.data.shape_keys.key_blocks if body.data.shape_keys else [])]
    else:keys=None
    from landfall_studio.sculpt import state
    report['steps'].append({'label':label,'mode':bpy.context.mode,'objects':sorted(o.name for o in bpy.data.objects),
        'base':digest,'keys':keys,'brush':state.get().active_zbrush_brush});save()

def suite():
    import landfall_studio
    from landfall_studio.ui import desktop
    from landfall_studio.sculpt import demo,state,gestures
    landfall_studio.register();desktop.restore_workspace_desktop()
    from landfall_studio.sculpt import preferences
    preferences.PATH=ROOT.parent/('.test_env/probe_imm_undo_prefs_'+str(os.getpid())+'.json');preferences._data=None
    yield 1.5
    demo.create_demo();yield 1.5
    snap('demo')
    body=bpy.data.objects['Creature_Sculpt']
    a=pos(body.matrix_world@Vector((-.3,-.8,.5)));b=pos(body.matrix_world@Vector((.3,-.8,.5)))
    yield from drag(a,b);snap('stroke 1')
    yield from drag((a[0],a[1]-20),(b[0],b[1]-20));snap('stroke 2')
    variant=os.environ.get('PROBE_VARIANT','all')  # diagnostic variants: no_new_handlers, direct, keys
    if variant=='keys':  # the ZBrush habit: pick the brush with B, I, M
        for k in ('B','I','M'):
            ev(k);ev(k,'RELEASE');yield .4
    else:
        from landfall_studio.sculpt import ops as sculpt_ops
        sculpt_ops.run('BRUSH',name='IMM Primitives');yield .4
    snap('after brush pick')
    report['variant']=variant
    import landfall_studio.sculpt as sculpt_pkg
    if variant=='no_new_handlers':
        for handlers,fn in ((bpy.app.handlers.undo_post,sculpt_pkg._history_changed),(bpy.app.handlers.redo_post,sculpt_pkg._history_changed),
                            (bpy.app.handlers.undo_pre,sculpt_pkg._remember_tool_state),(bpy.app.handlers.redo_pre,sculpt_pkg._remember_tool_state),
                            (bpy.app.handlers.depsgraph_update_post,sculpt_pkg._mode_watch)):
            while fn in handlers:handlers.remove(fn)
    report['undo_post_handlers']=[getattr(h,'__module__','?')+'.'+getattr(h,'__name__',repr(h)) for h in bpy.app.handlers.undo_post]
    report['undo_pre_handlers']=[getattr(h,'__module__','?')+'.'+getattr(h,'__name__',repr(h)) for h in bpy.app.handlers.undo_pre]
    save()
    cheek=pos(body.matrix_world@Vector((-.35,-.75,-.1)))
    yield from drag(cheek,(cheek[0]+40,cheek[1]));snap('IMM drag')
    report['gesture_history']=gestures.history[-6:]
    for i in range(4):
        if variant=='direct':
            with bpy.context.temp_override(**ctx()):report.setdefault('undo_results',[]).append(str(bpy.ops.ed.undo()))
        else:
            ev('Z',ctrl=True);ev('Z','RELEASE',ctrl=True)
        yield .8
        report.setdefault('last_ops',[]).append([o.bl_idname for o in bpy.context.window_manager.operators][-5:])
        snap(f'Ctrl+Z {i+1}')
    by={s['label']:s for s in report['steps']}
    after,first=by['IMM drag'],by['Ctrl+Z 1']
    check('IMM insert adds the part',any('IMM' in o for o in after['objects']))
    check('first Ctrl+Z removes only the inserted part',not any('IMM' in o for o in first['objects']) and 'Creature_Sculpt' in first['objects'],first['objects'])
    check('first Ctrl+Z keeps the sculpt strokes',first['keys']==after['keys'],(first['keys'],after['keys']))
    check('Undo keeps Sculpt mode and the IMM brush',first['mode']=='SCULPT' and first['brush']=='IMM Primitives')
    stroke_undone=next((s['label'] for s in report['steps'][report['steps'].index(first)+1:] if s['keys'] and s['keys']!=after['keys']),None)
    check('further Undo steps back through the strokes, not to the empty file',stroke_undone in ('Ctrl+Z 2','Ctrl+Z 3') and by[stroke_undone]['mode']=='SCULPT',stroke_undone)
    report['ok']=not report['failed']
    landfall_studio.unregister();save();bpy.ops.wm.quit_blender()

generator=None
def tick():
    global generator
    try:return next(generator)
    except StopIteration:return None
    except Exception:
        report['exception']=traceback.format_exc();save();print(traceback.format_exc());bpy.ops.wm.quit_blender();return None
def start():
    global generator
    bpy.context.preferences.view.show_splash=False
    generator=suite();bpy.app.timers.register(tick,first_interval=.5,persistent=True)
    return None
bpy.app.timers.register(start,first_interval=.5)
