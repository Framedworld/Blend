"""Disposable native scene tests for Sculpt Studio. Never saves user assets."""
import bpy,json,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
results={'passed':[],'failed':[],'input_method':'Native Blender scene/API checks; separate GUI suite required'}
OUT=ROOT/'output/zbrush_sculpt_results.json'
def check(name,condition,detail=None):
    results['passed' if condition else 'failed'].append(name if condition else {'test':name,'detail':detail})
    OUT.write_text(json.dumps(results,indent=2,default=str))
def test(name,fn):
    try: fn(); check(name,True)
    except Exception: check(name,False,traceback.format_exc())
def require(value):
    if not value: raise AssertionError(value)

import landfall_studio
landfall_studio.register()
from landfall_studio import sculpt
from landfall_studio.sculpt import state,brushes,ops,gestures
with bpy.context.temp_override(**ops.view_context()):
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16)
    body=bpy.context.object; body.name='Creature Body'
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=12,location=(2,0,0))
    other=bpy.context.object; other.name='Creature Head'
    bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); bpy.context.view_layer.objects.active=body
    test('enter sculpt mode',lambda:require(sculpt.enter()['engaged'] and bpy.context.mode=='SCULPT'))
    bpy.ops.ed.undo_push(message='Sculpt test baseline')
    for code,(label,native,_) in brushes.CATALOG.items():
        test('brush '+code+' '+label,lambda c=code,l=label:require(brushes.select(c)['brush']==l and state.brush().name.startswith('Landfall')))
    def controls():
        brushes.select('ST'); s=state.get(); s.draw_size=87; s.focal_shift=40; s.z_intensity=63; s.z_mode='SUBTRACT'; s.lazy_mouse=True
        b=state.brush(); require(b.size==87 and abs(b.hardness-.7)<1e-5 and abs(b.strength-.63)<1e-5 and b.direction=='SUBTRACT' and b.use_smooth_stroke)
    test('live brush size hardness strength direction lazy settings',controls)
    def brush_pickers():
        for method in ('SPACE','DOTS','DRAG_DOT','ANCHORED','AIRBRUSH'):
            brushes.set_stroke(method=method);require(state.brush().stroke_method==method)
        for alpha in ('SQUARE','NOISE'):
            brushes.set_stroke(alpha=alpha);require(state.brush().texture is not None)
        brushes.set_stroke(alpha='NONE',method='SPACE');require(state.brush().texture is None)
        brushes.select('MT');require(state.brush().mesh_automasking_settings.use_automasking_topology)
        brushes.select('MP');require(state.brush().sculpt_brush_type=='MASK')
        brushes.select('ST')
    test('stroke and alpha pickers configure actual brush resources',brush_pickers)
    for hit,ctrl,shift,alt,expected in [('BLANK',0,0,0,'ORBIT'),('BLANK',0,0,1,'PAN'),('OTHER',0,0,1,'SUBTOOL'),('ACTIVE',0,0,0,'STROKE'),('ACTIVE',0,0,1,'INVERT'),('ACTIVE',0,1,0,'SMOOTH'),('ACTIVE',1,0,0,'MASK'),('BLANK',1,1,0,'VISIBILITY')]:
        test('classify '+expected,lambda h=hit,c=ctrl,s=shift,a=alt,e=expected:require(gestures.classify(h,c,s,a)==e))
    test('Alt click switching semantics',lambda:require(ops.switch_subtool(other)['subtool']==other.name and bpy.context.mode=='SCULPT' and bpy.context.active_object==other))
    ops.switch_subtool(body)
    bpy.ops.ed.undo_push(message='Mask test baseline')
    def mask():
        for kind in ('ALL','INVERT','CLEAR','SMOOTH','SHARPEN','GROW','SHRINK','CONTRAST_INCREASE','CONTRAST_DECREASE'): ops.dispatch('MASK',kind=kind)
        ops.dispatch('MASK',kind='ALL'); require(min(ops.mask_values())>0.99)
        ops.dispatch('MASK',kind='INVERT'); require(max(ops.mask_values())<.01)
    test('native mask fill invert clear filters',mask)
    for kind in ('VISIBLE','MASKED','LOOSE','NORMALS','CLEAR'):
        test('face sets '+kind,lambda k=kind:require(ops.dispatch('GROUP',mode=k)['ok']))
    for kind in ('SHOW','INVERT','HIDE_UNMASKED','SHOW'):
        test('visibility '+kind,lambda k=kind:require(ops.dispatch('VISIBILITY',kind=k)['ok']))
    def levels():
        ops.divide(); require(ops.multires().total_levels==1)
        ops.divide(); require(ops.multires().total_levels==2)
        ops.resolution(-1); require(ops.multires().sculpt_levels==1)
        ops.resolution(1); require(ops.multires().sculpt_levels==2)
    test('real multires divide and lower higher',levels)
    def count_grid():
        count=ops.point_count(body)
        with ops.object_mode():
            dg=bpy.context.evaluated_depsgraph_get();obj=body.evaluated_get(dg);mesh=obj.to_mesh()
            try:require(count==len(mesh.vertices) and count>len(body.data.vertices))
            finally:obj.to_mesh_clear()
    test('point counter matches evaluated Multires surface topology',count_grid)
    def multires_filter():
        def coordinates():
            with ops.object_mode():
                dg=bpy.context.evaluated_depsgraph_get();obj=body.evaluated_get(dg);mesh=obj.to_mesh()
                try:return [v.co.copy() for v in mesh.vertices]
                finally:obj.to_mesh_clear()
        before=coordinates();ops.deform('INFLATE');after=coordinates()
        require(any((a-b).length>1e-6 for a,b in zip(after,before)))
    test('native deformation filter edits the high subdivision surface',multires_filter)
    def shared_preview():
        bpy.ops.landfall.smooth_preview(mode='CAGE');require(ops.multires().levels==0)
        bpy.ops.landfall.smooth_preview(mode='BOTH');require(ops.multires().levels==2 and bpy.context.scene.landfall_cage_show)
        bpy.ops.landfall.smooth_preview(mode='SMOOTH');require(ops.multires().levels==2 and not bpy.context.scene.landfall_cage_show)
        require(not any(m.type=='SUBSURF' for m in body.modifiers))
    test('Maya 1 2 3 shares actual Multires without extra subdivision',shared_preview)
    def delete_lower():
        ops.resolution(-1)
        result=ops.dispatch('DELETE_LOWER')
        require(result['retained_upper_levels']==1 and ops.multires().total_levels==1 and ops.multires().sculpt_levels==0)
        require(body in list(bpy.context.scene.objects))
        ops.switch_subtool(body); ops.resolution(1)
    test('delete lower stages new base and retains validated upper surface',delete_lower)
    test('delete higher subdivision levels',lambda:(ops.resolution(-1),ops.dispatch('DELETE_HIGHER'),require(ops.multires().total_levels==1)))
    # Leave multires asset intact for continuity checks; use a second test surface.
    ops.switch_subtool(other)
    def layer():
        ops.layer('NEW',name='Smile Corrective'); key=other.active_shape_key; key.data[0].co.x+=.2
        ops.layer('VALUE',name=key.name,value=.4); require(abs(key.value-.4)<1e-5)
        ops.layer('SELECT',name=key.name); require(other.active_shape_key.name=='Smile Corrective')
    test('sculpt layers are actual editable shape keys',layer)
    def record():
        ops.layer('RECORD');require(other.active_shape_key_index==0 and not state.get().record_layer)
        ops.layer('RECORD');require(other.active_shape_key.name=='Smile Corrective' and state.get().record_layer)
    test('layer REC toggles actual recording target and restores it',record)
    def grid_layer_policy():
        ops.dispatch('DUPLICATE');copy=ops.active();name=copy.active_shape_key.name
        ops.divide()
        require(not state.get().record_layer and copy.active_shape_key_index==0 and ops.multires().sculpt_levels==1)
        ops.layer('SELECT',name=name);ops.layer('RECORD')
        require(state.get().record_layer and copy.active_shape_key.name==name and ops.multires().sculpt_levels==0)
        ops.resolution(1)
        require(not state.get().record_layer and copy.active_shape_key_index==0)
        ops.switch_subtool(other)
    test('layer REC uses base resolution and higher grids stop recording safely',grid_layer_policy)
    def bake_layer():
        original=other
        ops.dispatch('DUPLICATE');copy=ops.active()
        basis=copy.data.shape_keys.reference_key.data[0].co.copy()
        sculpted=copy.active_shape_key;name=sculpted.name
        expected=basis+(sculpted.data[0].co-basis)*sculpted.value
        ops.layer('BAKE')
        require(name not in copy.data.shape_keys.key_blocks and (copy.data.shape_keys.reference_key.data[0].co-expected).length<1e-6)
        require(original.data.shape_keys.key_blocks.get(name) is not None)
        ops.switch_subtool(original)
    test('Bake to Base commits layer geometry and preserves original SubTool',bake_layer)
    def protected_remesh():
        keys=other.data.shape_keys; n=len(other.data.vertices); state.get().dynamesh_resolution=24
        result=ops.dispatch('DYNAMESH'); require(result['ok'] and bpy.context.object!=other and other.data.shape_keys==keys and len(other.data.vertices)==n)
    test('DynaMesh stages protected shape key source',protected_remesh)
    surface=bpy.context.object
    def extract():
        ops.set_mask([1. if v.co.z>0 else 0 for v in surface.data.vertices]); result=ops.dispatch('EXTRACT')
        require(result['faces']>0 and len(bpy.context.object.modifiers)==1 and bpy.context.object.modifiers[0].type=='SOLIDIFY')
        require(surface in list(bpy.context.scene.objects))
    test('masked extract creates solidified shell',extract)
    ops.switch_subtool(surface)
    test('split masked produces real new mesh',lambda:require(ops.dispatch('SPLIT_MASKED')['faces']>0))
    ops.switch_subtool(surface)
    def duplicate():
        before=len(ops.meshes()); ops.dispatch('DUPLICATE'); require(len(ops.meshes())==before+1 and bpy.context.object.data!=surface.data)
    test('independent SubTool duplicate',duplicate)
    def solo():
        before={o.name:o.hide_get() for o in ops.meshes()}; ops.toggle_solo(); ops.toggle_solo(); require(all(o.hide_get()==before[o.name] for o in ops.meshes()))
    test('Solo preserves prior visibility',solo)
    test('Ghost restores display states',lambda:(ops.ghost(),ops.ghost(),require(not state.get().ghost_transparency_active)))
    def solo_switch():
        before={o.name:o.hide_get() for o in ops.meshes()};ops.toggle_solo();ops.switch_subtool(surface)
        require(sum(o.visible_get() for o in ops.meshes())==1)
        ops.toggle_solo();require(all(o.hide_get()==before[o.name] for o in ops.meshes()))
    test('Solo SubTool switch keeps one surface and restores original visibility',solo_switch)
    test('Xpose restores exact object locations',lambda:(ops.xpose(),ops.xpose(),require(not ops._xpose)))
    for matcap in ops.MATCAPS:
        test('matcap '+matcap,lambda n=matcap:require(ops.matcap(n)['ok']))
    for kind in ('INFLATE','POLISH','CRISP','SMOOTH','RELAX','CONTRAST','UNIFY'):
        test('deform '+kind,lambda k=kind:require(ops.deform(k)['ok']))
    test('mirror and weld',lambda:require(ops.dispatch('MIRROR',axis='X')['ok']))
    test('close holes',lambda:require(ops.dispatch('CLOSE_HOLES')['ok']))
    # A clean closed sphere is a representative QuadriFlow input.
    ops.append(); state.get().zremesher_target_polys=200
    test('native QuadriFlow ZRemesher',lambda:require(ops.remesh(True)['faces']>0))
    test('merge creates new surface preserves originals',lambda:require(ops.merge()['ok']))
    def recover():
        backup=next(o for o in bpy.context.scene.objects if o.get('_landfall_recovery'))
        result=ops.dispatch('RESTORE',name=backup.name)
        require(result['ok'] and active_copy_is_valid(backup))
    def active_copy_is_valid(backup):
        copy=bpy.context.view_layer.objects.active
        return not copy.get('_landfall_recovery') and copy.data!=backup.data and len(copy.data.vertices)==len(backup.data.vertices)
    test('Recovery restores independent editable copy without deleting snapshot',recover)
    ops.switch_subtool(other)
    test('GoZ focuses exact shape target and returns Object mode',lambda:require(ops.layer('GOZ')['ok'] and bpy.context.mode=='OBJECT' and other.active_shape_key.name=='Smile Corrective'))
    test('Maya layout restore clears sculpt mode state',lambda:require(not sculpt.is_engaged()))
    test('scoped keymaps restored',lambda:require(not landfall_studio.keymaps.profiles._sculpt_keymaps and not landfall_studio.keymaps.profiles._sculpt_muted))
landfall_studio.unregister()
check('unregister removes Scene settings',not hasattr(bpy.types.Scene,'landfall_sculpt'))
print('SCULPT_RESULTS',len(results['passed']),'passed',len(results['failed']),'failed')
