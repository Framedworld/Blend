import bpy, json
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'output'/'native_events.json'
stage=0
report={}
def tick():
    global stage
    w=bpy.context.window_manager.windows[0]
    a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
    r=next(r for r in a.regions if r.type=='WINDOW')
    if stage==0:
        w.event_simulate(type='ESC',value='PRESS')
        w.event_simulate(type='ESC',value='RELEASE')
    elif stage==1:
        w.event_simulate(type='MOUSEMOVE',value='NOTHING',x=r.x+r.width//2,y=r.y+r.height//2)
        w.event_simulate(type='W',value='PRESS',unicode='w',x=r.x+r.width//2,y=r.y+r.height//2)
        w.event_simulate(type='W',value='RELEASE',x=r.x+r.width//2,y=r.y+r.height//2)
    else:
        report['tool']=w.workspace.tools.from_space_view3d_mode('OBJECT',create=False).idname
        report['operators']=[o.bl_idname for o in bpy.context.window_manager.operators]
        out.write_text(json.dumps(report))
        bpy.ops.wm.quit_blender()
        return None
    stage+=1
    return 1
bpy.app.timers.register(tick,first_interval=1)
