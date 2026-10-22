import bpy,sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));report={}
class UndoProbe(bpy.types.Operator):
    bl_idname='landfall_probe.edit';bl_label='Palette Undo Probe';bl_options={'REGISTER','UNDO'}
    variant:bpy.props.IntProperty()
    def execute(self,context):
        o=context.object
        if self.variant==0:
            bpy.ops.sculpt.mesh_filter(type='SCALE',strength=0)
            for v in o.data.vertices:v.co.x+=.3
            o.data.update();bpy.ops.sculpt.optimize()
        elif self.variant==1:
            bpy.ops.object.mode_set(mode='OBJECT')
            for v in o.data.vertices:v.co.x+=.3
            o.data.update();o.data.update_tag();o.update_tag()
            bpy.ops.ed.undo_push(message='Palette changed')
            bpy.ops.object.mode_set(mode='SCULPT')
        elif self.variant==2:
            bpy.ops.sculpt.mesh_filter(type='SCALE',strength=.01)
            for v in o.data.vertices:v.co.x+=.3
            o.data.update();bpy.ops.sculpt.optimize()
        return {'FINISHED'}
def suite():
    bpy.utils.register_class(UndoProbe)
    win=bpy.context.window_manager.windows[0];area=next(a for a in win.screen.areas if a.type=='VIEW_3D');region=next(r for r in area.regions if r.type=='WINDOW')
    for variant in range(3):
        with bpy.context.temp_override(window=win,area=area,region=region):
            if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.mesh.primitive_cube_add();o=bpy.context.object;name=o.name
            bpy.ops.object.mode_set(mode='SCULPT');bpy.ops.ed.undo_push(message='Variant baseline')
            before=[tuple(v.co) for v in o.data.vertices]
            bpy.ops.landfall_probe.edit('EXEC_DEFAULT',True,variant=variant)
            report[variant]={'before':before,'after':[tuple(v.co) for v in o.data.vertices]}
        yield .1
        with bpy.context.temp_override(window=win,area=area,region=region):bpy.ops.ed.undo()
        yield .1
        o=bpy.data.objects.get(name);report[variant]['undo']=[tuple(v.co) for v in o.data.vertices] if o else None;report[variant]['mode']=bpy.context.mode
        (ROOT/'output/palette_undo_probe.json').write_text(json.dumps(report,indent=2))
    bpy.ops.wm.quit_blender()
steps=suite()
def tick():
    try:return next(steps)
    except StopIteration:return None
    except Exception:
        report['error']=traceback.format_exc();(ROOT/'output/palette_undo_probe.json').write_text(json.dumps(report,indent=2));bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5)
