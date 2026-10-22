import bpy,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import landfall_studio
landfall_studio.register()
from landfall_studio.sculpt import ops,state,extended
with bpy.context.temp_override(**ops.view_context()):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8)
    bpy.ops.object.mode_set(mode='SCULPT');bpy.ops.ed.undo_push(message='Probe baseline')
    ops.dispatch('BRUSH',name='ST')
    def snapshot(label):
        b=state.brush();print(label,b.name,b.texture,state.get().alpha,bpy.context.mode,flush=True)
    snapshot('start');extended.morph('STORE');snapshot('morph')
    ops.dispatch('STROKE',alpha='NOISE');snapshot('alpha')
    extended.mask('ALPHA');snapshot('result')
landfall_studio.unregister()
