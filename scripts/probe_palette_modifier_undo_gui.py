import bpy,json,traceback
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]/'output/palette_modifier_undo_probe.json'
report={}
class Probe(bpy.types.Operator):
 bl_idname='landfall_probe.modifier';bl_label='Modifier Probe';bl_options={'REGISTER','UNDO'}
 variant:bpy.props.IntProperty()
 def execute(self,c):
  o=c.object
  if self.variant==0:bpy.ops.object.modifier_add(type='ARRAY')
  else:
   m=o.modifiers.new('Probe','ARRAY')
   if self.variant==1:o.update_tag(refresh={'OBJECT','DATA','TIME'})
   elif self.variant==2:
    bpy.ops.object.mode_set(mode='OBJECT');bpy.ops.object.mode_set(mode='SCULPT')
   elif self.variant==3:
    bpy.ops.sculpt.mesh_filter(type='SCALE',strength=0);o.update_tag()
  return {'FINISHED'}
def suite():
 bpy.utils.register_class(Probe)
 w=bpy.context.window_manager.windows[0];a=next(a for a in w.screen.areas if a.type=='VIEW_3D');r=next(r for r in a.regions if r.type=='WINDOW')
 for v in range(4):
  with bpy.context.temp_override(window=w,area=a,region=r):
   if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
   bpy.ops.mesh.primitive_cube_add();o=bpy.context.object;name=o.name
   bpy.ops.object.mode_set(mode='SCULPT');bpy.ops.ed.undo_push(message='Baseline')
   bpy.ops.landfall_probe.modifier('EXEC_DEFAULT',True,variant=v)
   report[v]={'after':[(m.name,m.type) for m in o.modifiers]}
   bpy.context.window_manager.print_undo_steps()
  yield .1
  with bpy.context.temp_override(window=w,area=a,region=r):bpy.ops.ed.undo()
  yield .1
  o=bpy.data.objects.get(name);report[v]['undo']=[m.name for m in o.modifiers] if o else None;report[v]['mode']=bpy.context.mode
  OUT.write_text(json.dumps(report,indent=2))
 bpy.ops.wm.quit_blender()
gen=suite()
def tick():
 try:return next(gen)
 except StopIteration:return None
 except Exception:report['error']=traceback.format_exc();OUT.write_text(json.dumps(report,indent=2));bpy.ops.wm.quit_blender()
bpy.app.timers.register(tick,first_interval=.5)
