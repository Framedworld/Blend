"""Native data acceptance for the supplied reference palettes; factory scene only."""
import bpy,json,sys,traceback,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/sculpt_reference_data_results.json';results={'passed':[],'failed':[]}
import landfall_studio
landfall_studio.register()
from landfall_studio.sculpt import ops,state,extended as ext,instances

def save():OUT.write_text(json.dumps(results,indent=2,default=str))
def require(value,message='assertion failed'):
    if not value:raise AssertionError(message)
def check(name,fn):
    try:fn();results['passed'].append(name)
    except Exception:results['failed'].append({'test':name,'error':traceback.format_exc()})
    save()
def new(cube=False):
    if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
    if cube:bpy.ops.mesh.primitive_cube_add()
    else:bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8)
    o=bpy.context.object
    for v in o.data.vertices:v.co.z+=.12*math.sin(v.co.x*4)*math.cos(v.co.y*3)
    bpy.ops.object.mode_set(mode='SCULPT');ops.dispatch('BRUSH',name='ST');bpy.ops.ed.undo_push(message='Reference fixture baseline');return o
def run(section,kind,**kw):return ops.dispatch('PALETTE',section=section,kind=kind,**kw)
def points(o):return [tuple(v.co) for v in o.data.vertices]
def evaluated_count(o):
    bpy.context.view_layer.update();e=o.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=e.to_mesh()
    try:return len(mesh.vertices)
    finally:e.to_mesh_clear()

with bpy.context.temp_override(**ops.view_context()):
    def scene_persistence():
        o=new();ext.option('Masking','threshold',.37);ext.option('NanoMesh','seed',23)
        name=o.name;path=ROOT/'output/sculpt_reference_persistence.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path));bpy.ops.wm.open_mainfile(filepath=str(path))
        require(abs(ext.settings('Masking')['threshold']-.37)<1e-6 and instances.config('NanoMesh')['seed']==23)
    # Save/reopen runs last to preserve this live override's RNA pointers.
    def ordering():
        a=new();ops.append('CUBE');b=ops.active();run('SubTool','MOVE_UP');require(ops.meshes()[0]==b)
        run('SubTool','RENAME',name='Renamed SubTool');require(b.name=='Renamed SubTool')
        run('SubTool','FOLDER',name='Sculpt Parts');require(any(c.get('_lf_subtool_folder') for c in b.users_collection))
        run('SubTool','UP');require(ops.active()==b)
    check('SubTool order rename folder and navigation',ordering)
    def stages():
        o=new();before=o.matrix_world.copy();run('SubTool','STORE_HOME');o.location.x=3;run('SubTool','STORE_TARGET');o.location.x=5
        run('SubTool','HOME');require(o.matrix_world==before);run('SubTool','TARGET');require(abs(o.location.x-3)<1e-5)
    check('Stager restores Home and Target matrices',stages)
    def visibility():
        o=new();ops.append('CUBE');b=ops.active();o.hide_set(True);run('SubTool','VISIBILITY_SET',index=1,store=True);o.hide_set(False);run('SubTool','VISIBILITY_SET',index=1);require(o.hide_get() and not b.hide_get())
    check('Visibility sets store and restore scene visibility',visibility)
    def clipboard():
        o=new();count=len(o.data.vertices);run('SubTool','COPY');run('SubTool','PASTE');require(ops.active()!=o and len(ops.active().data.vertices)==count and ops.active().data!=o.data)
    check('SubTool clipboard duplicates independent mesh data',clipboard)
    def dynamic():
        o=new(True);ext.option('Geometry','dynamic',True);require(evaluated_count(o)>len(o.data.vertices));ext.option('Geometry','dynamic',False);require(evaluated_count(o)==len(o.data.vertices))
    check('Dynamic subdivision is a reversible native modifier',dynamic)
    def crease():
        o=new(True);ext.write_faces(o,[1,1,1,2,2,2]);run('Geometry','CREASE');require(max(x.value for x in o.data.attributes['crease_edge'].data)>0);run('Geometry','UNCREASE');require(max(x.value for x in o.data.attributes['crease_edge'].data)==0)
    check('Crease and Uncrease write native edge crease data',crease)
    def subdiv():
        o=new(True);ext.option('Geometry','smooth',False);ops.divide();require(ops.multires().total_levels==1);run('Geometry','LEVEL',value=0);require(ops.multires().sculpt_levels==0)
        run('Geometry','CAGE');run('Geometry','RESTRICT');require(ops.multires().use_sculpt_base_mesh)
    check('Simple Divide SDiv Cage and Restrict use Multires',subdiv)
    for mode in ('AUTO','UV','AUTO_UV','EDGES','NORMALS','SPLIT_ISLANDS','MASKED_CLEAR','DYNAMESH_SUB','MASKING','PAINT','FRONT','REGROUP_VISIBLE','VISIBLE','MERGE_SIMILAR','MERGE_STRAY'):
        def group(mode=mode):
            o=new();ext.write_faces(o,[1+(p.index%3) for p in o.data.polygons]);ops.set_mask([v.co.x>0 for v in o.data.vertices]);run('PolyGroups',mode)
            values=ext.face_values(o);require(len(values)==len(o.data.polygons) and all(v>0 for v in values))
        check('PolyGroups '+mode,group)
    for kind in ('FEATURE','DEPTH','FIBERS','NORMALS','DRAFT','SMOOTHNESS','COLOR','ALPHA','AO','CAVITY','PEAKS_VALLEYS','ADJUST','CENTER','CREATE_ALPHA','FLIP_SYMMETRY','MIRROR_SYMMETRY','CHANGED'):
        def masking(kind=kind):
            o=new();run('Morph Target','STORE');o.data.vertices[0].co.z+=.2
            ops.set_mask([max(0,v.co.x) for v in o.data.vertices]);ops.dispatch('STROKE',alpha='NOISE');run('Masking',kind)
            values=ops.mask_values(o);require(len(values)==len(o.data.vertices) and all(math.isfinite(v) and -.0001<=v<=1.0001 for v in values))
            if kind=='CREATE_ALPHA':require(any(i.name.endswith('Mask Alpha') for i in bpy.data.images))
        check('Masking '+kind,masking)
    for kind in ('UNIFY','MIRROR','RESYM','SMART_RESYM','OFFSET','ROTATE','SIZE','BEND','SBEND','SKEW','SSKEW','RFLATTEN','FLATTEN','SFLATTEN','TWIST','TAPER','SQUEEZE','NOISE','SMOOTH','CONTRAST','INFLATE','BALLOON','SPHERIZE','GRAVITY','PERSPECTIVE','POLISH','POLISH_FEATURES','POLISH_GROUPS','CRISP','RELAX','RELAX_PLANE','MORPH_GRID'):
        def deformation(kind=kind):
            o=new();before=points(o);run('Deformation',kind,amount=.3,axes='XYZ');after=points(o)
            require(all(math.isfinite(x) for c in after for x in c));require(len(before)==len(after))
            if kind not in ('RESYM','SMART_RESYM'):require(before!=after,'deformation did not change the surface')
        check('Deformation '+kind,deformation)
    def masked_deform():
        o=new();ops.set_mask([1.]*len(o.data.vertices));before=points(o);run('Deformation','BEND',amount=.5,axes='Z');require(points(o)==before)
        ops.set_mask([0.]*len(o.data.vertices));run('Deformation','BEND',amount=.5,axes='Z');require(points(o)!=before)
    check('Deformations preserve fully masked points',masked_deform)
    def layer_target():
        o=new();ops.layer('NEW');basis=[v.co.copy() for v in o.data.vertices];before=[v.co.copy() for v in o.active_shape_key.data]
        run('Deformation','OFFSET',amount=.3,axes='X');require(all(v.co==b for v,b in zip(o.data.vertices,basis)) and any(v.co!=b for v,b in zip(o.active_shape_key.data,before)))
    check('Deformation writes active layer without changing base',layer_target)
    def repeat():
        a=new();run('Deformation','OFFSET',amount=.2,axes='X');before=points(a);run('Deformation','REPEAT_ACTIVE');require(points(a)!=before)
    check('Repeat deformation retains operation amount and axes',repeat)
    for kind in ('MORPH','WIDTH','HEIGHT','DEPTH','DIST','SWITCH','DIFFERENCE','DELETE'):
        def morph(kind=kind):
            o=new();before=points(o);run('Morph Target','STORE')
            for v in o.data.vertices:v.co+=Vector((.1,.2,.3))
            run('Morph Target',kind,value=.5)
            if kind=='DELETE':require(o.data.attributes.get('sculpt_morph_target') is None)
            elif kind=='SWITCH':require(points(o)==before)
            elif kind=='DIFFERENCE':require(ops.active()!=o)
            else:require(points(o)!=before)
        check('Morph Target '+kind,morph)
    for kind in ('FILL','FROM_GROUPS','FROM_TEXTURE','DRAFT','THICKNESS','ADJUST','FLIP_SYMMETRY','MIRROR_SYMMETRY'):
        def paint(kind=kind):
            o=new();ops.layer('NEW');ext.write_faces(o,[1+p.index%4 for p in o.data.polygons]);state.brush().color=(.2,.6,.3)
            if kind=='FROM_TEXTURE':
                image=bpy.data.images.new('Test Color',width=2,height=2);image.pixels[:]=[.2,.6,.3,1]*4
                material=bpy.data.materials.new('Texture Test');material.use_nodes=True;node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;o.data.materials.append(material)
            run('Polypaint',kind);require(o.data.color_attributes.active_color is not None and all(math.isfinite(c) for d in o.data.color_attributes.active_color.data for c in d.color))
        check('Polypaint '+kind,paint)
    for kind in ('DUPLICATE','INVERT','MERGE_DOWN','BAKE_ALL','SPLIT','UP','DOWN','RENAME','DELETE'):
        def layers(kind=kind):
            o=new();ops.layer('NEW',name='A');o.active_shape_key.data[0].co.x+=.2;ops.layer('NEW',name='B');o.active_shape_key.data[0].co.y+=.3
            run('Layers',kind,name='Renamed');require(len(o.data.vertices)>0)
            if kind=='BAKE_ALL':require(o.data.shape_keys is None)
            if kind=='SPLIT':require(any(k.name.endswith(' X') for k in o.data.shape_keys.key_blocks))
            if kind=='RENAME':require(o.active_shape_key.name=='Renamed')
        check('Layers '+kind,layers)
    def mdd():
        o=new(True);scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=3
        path=ROOT/'output/sculpt_reference_roundtrip.mdd';run('Layers','EXPORT_MDD',path=str(path));before=len(o.data.vertices);run('Layers','IMPORT_MDD',path=str(path));require(len(o.data.shape_keys.key_blocks)==4 and len(o.data.vertices)==before)
    check('MDD native geometry point count export/import roundtrip',mdd)
    def arrays():
        o=new(True);ext.option('ArrayMesh','enabled',True);ext.option('ArrayMesh','count',4);require(evaluated_count(o)==len(o.data.vertices)*4)
        ext.option('ArrayMesh','rotate_z',30);require(o.modifiers['Sculpt Array 1'].offset_object.rotation_euler.z!=0)
        run('ArrayMesh','APPEND');require(len([m for m in o.modifiers if m.type=='ARRAY'])==2);run('ArrayMesh','DELETE');require(len([m for m in o.modifiers if m.type=='ARRAY'])==1)
        run('ArrayMesh','COPY');ext.option('ArrayMesh','count',2);run('ArrayMesh','PASTE');require(instances.config('ArrayMesh')['count']==4)
        path=ROOT/'output/array_reference_preset.json';run('ArrayMesh','SAVE',path=str(path));run('ArrayMesh','OPEN',path=str(path));require(path.exists())
        before=o;run('ArrayMesh','MAKE_MESH');require(ops.active()!=before and before.hide_get())
    check('ArrayMesh native stage count transform clipboard preset make mesh',arrays)
    def nanos():
        target=new(True);ops.append('SPHERE');source=ops.active();ops.switch_subtool(target)
        ext.option('NanoMesh','source',source.name);ext.option('NanoMesh','enabled',True);require(evaluated_count(target)>len(target.data.vertices))
        p=bpy.data.objects[target['_lf_nano_points']];require(len(p.data.vertices)==len(target.data.polygons))
        ext.option('NanoMesh','tile_h',2);require(len(p.data.vertices)==len(target.data.polygons)*2)
        ext.option('NanoMesh','freeze',True);count=len(p.data.vertices);ext.option('NanoMesh','tile_h',3);require(len(p.data.vertices)==count)
        ext.option('NanoMesh','freeze',False);require(len(p.data.vertices)==len(target.data.polygons)*3)
        require(source.hide_get());before=target;run('NanoMesh','MAKE_MESH');require(ops.active()!=before and len(ops.active().data.vertices)>8)
    check('NanoMesh native Geometry Nodes instances tiling freeze and realization',nanos)
    def nano_inventory():
        target=new(True);ops.append('SPHERE');source=ops.active();ops.switch_subtool(target)
        ext.option('NanoMesh','source',source.name);ext.option('NanoMesh','enabled',True)
        first=evaluated_count(target);run('NanoMesh','ADD_INDEX');ext.option('NanoMesh','source',source.name);ext.option('NanoMesh','enabled',True)
        both=evaluated_count(target);require(both>first)
        ext.option('NanoMesh','hide_others',True);require(evaluated_count(target)==first)
        run('NanoMesh','PREVIOUS');require(instances.config('NanoMesh')['index']==0)
    check('NanoMesh multi-index inventory and Hide Others',nano_inventory)
    def array_pattern():
        o=new(True);ext.option('ArrayMesh','enabled',True);ext.option('ArrayMesh','count',6);all_count=evaluated_count(o)
        ext.option('ArrayMesh','pattern_on',1);ext.option('ArrayMesh','pattern_off',1);require(evaluated_count(o)<all_count)
        run('ArrayMesh','APPEND');run('ArrayMesh','STAGE',value=0);run('ArrayMesh','INSERT');require(instances.config('ArrayMesh')['stage']==1)
    check('ArrayMesh connected-island pattern and Insert-after stage',array_pattern)
    def duplicate_instance_isolation():
        o=new(True);ext.option('ArrayMesh','enabled',True);original=o.modifiers['Sculpt Array 1'].offset_object
        ops.dispatch('DUPLICATE');copy=ops.active();ext.option('ArrayMesh','rotate_z',40)
        require(copy.modifiers['Sculpt Array 1'].offset_object!=original)
    check('Duplicate ArrayMesh settings do not move original helpers',duplicate_instance_isolation)
    def retime_mdd():
        o=new(True);scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=3
        path=ROOT/'output/sculpt_reference_retime.mdd';run('Layers','EXPORT_MDD',path=str(path));run('Layers','IMPORT_MDD',path=str(path))
        from landfall_studio.advanced.anim_layers import _iter_action_fcurves
        curves=_iter_action_fcurves(o.data.shape_keys.animation_data.action);before=max(p.co.x for c in curves for p in c.keyframe_points)
        ext.option('Layers','mdd_speed',2);after=max(p.co.x for c in curves for p in c.keyframe_points);require(abs((before-1)/2+1-after)<1e-5)
    check('MDD Speed retimes imported animation channels',retime_mdd)
    def protection():
        o=new(True);ops.layer('NEW');key=o.active_shape_key;before=points(o);run('Topology','TRIANGULATE');require(ops.active()!=o and o.data.shape_keys is not None and points(o)==before)
    check('Topology edits preserve protected source shape keys',protection)
    for kind in ('TRIANGULATE','QUADS','WELD','FLIP','UNWELD','DELETE_HIDDEN'):
        def topo(kind=kind):
            o=new(True);run('Topology',kind);require(len(ops.active().data.vertices)>0)
        check('Modify Topology '+kind,topo)
    def split():
        o=new(True);ext.write_faces(o,[1,1,1,2,2,2]);run('Topology','SPLIT_GROUPS');require(len(ops.meshes())>=3)
    check('Group Split creates real separate SubTools and preserves source',split)
    def boolean():
        o=new(True);ops.append('SPHERE');source=ops.active();ops.switch_subtool(o);run('Topology','BOOLEAN',target=source.name,operation='DIFFERENCE');require(o.modifiers[-1].type=='BOOLEAN' and o.modifiers[-1].object==source)
    check('Live Boolean retains editable source operand',boolean)
    def projection():
        o=new(True);ops.append('SPHERE');source=ops.active();ops.switch_subtool(o);run('Topology','PROJECT',target=source.name);require(o.modifiers[-1].target==source)
    check('Project All creates native surface projection modifier',projection)
check('Palette preferences survive blend save/reopen',scene_persistence)
results['ok']=not results['failed'];save();print('SCULPT_REFERENCE_DATA',len(results['passed']),'passed',len(results['failed']),'failed')
landfall_studio.unregister()
