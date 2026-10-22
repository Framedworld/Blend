"""Non-destructive native arrays and per-face NanoMesh-style instances."""
import json
import math
from pathlib import Path
from threading import current_thread, main_thread
import bpy
from mathutils import Vector, Matrix, Euler
from . import ops

ARRAY_DEFAULTS={'enabled':False,'count':3,'offset_x':1.2,'offset_y':0.,'offset_z':0.,'scale_x':1.,'scale_y':1.,'scale_z':1.,'rotate_x':0.,'rotate_y':0.,'rotate_z':0.,'pivot_x':0.,'pivot_y':0.,'pivot_z':0.,'stage':0,'smooth':0.,'pattern_start':0,'pattern_length':1,'pattern_on':1,'pattern_off':0,'mirror_x':False,'mirror_y':False,'mirror_z':False,'align_x':0.,'align_y':0.,'align_z':0.,'extrude':False,'close':False,'angle':30.}
NANO_DEFAULTS={'enabled':False,'source':'','index':0,'hide_others':False,'size':.15,'width':1.,'length':1.,'height':1.,'offset_x':0.,'offset_y':0.,'offset_z':0.,'rotate_x':0.,'rotate_y':0.,'rotate_z':0.,'w_var':0.,'l_var':0.,'h_var':0.,'x_var':0.,'y_var':0.,'z_var':0.,'rx_var':0.,'ry_var':0.,'rz_var':0.,'flip_h':False,'flip_v':False,'tile_h':1,'tile_v':1,'pattern':'GRID','random_distribution':0.,'seed':0,'alignment':'NORMAL','fit':'PROP','show_instances':True,'show_placement':True,'freeze':False,'colorize':False,'uv':True,'modulate_color':0.}
_clipboard={}
_syncing_native_owners=False

def config(section,o=None):
    from .extended import settings
    defaults=ARRAY_DEFAULTS if section=='ArrayMesh' else NANO_DEFAULTS
    return dict(defaults,**settings(section,o))

def save(section,cfg,o):o['_lf_palette_'+section]=json.dumps(cfg)

def modifier(o,name,kind):
    m=o.modifiers.get(name)
    if m is None:m=o.modifiers.new(name,kind)
    return m


def owns_helper(helper,o):
    # Parenting is an ID relationship and survives artist renaming. The name
    # fallback adopts older unparented helpers on their next settings update.
    return bool(helper and helper.get('_lf_instance_helper') and
                (helper.parent==o or (helper.parent is None and helper.get('_lf_owner')==o.name)))


def attach_helper(helper,o,local_matrix):
    # Offsets/placements belong to the asset's local frame. Native parenting
    # handles object, group and animated transforms without a refresh callback.
    helper.parent=o
    helper.matrix_parent_inverse=Matrix.Identity(4)
    helper.matrix_basis=local_matrix
    helper['_lf_owner']=o.name


def ensure_owners(o):
    """Give a copied SubTool independent offset/placement IDs before using it."""
    if any(m.type=='ARRAY' and m.name.startswith('Sculpt Array ')
           and m.offset_object and m.offset_object.get('_lf_instance_helper')
           and m.offset_object.parent is None for m in o.modifiers):
        # Old files stored world-space offsets. Reconstruct the authored local
        # stage matrices, even if the asset has already moved since it was saved.
        array_update(o,config('ArrayMesh',o))
    copies={}

    def owned(helper,placement=False):
        if not helper or not helper.get('_lf_instance_helper'):
            return helper
        if owns_helper(helper,o):
            if helper.parent is None and placement:attach_helper(helper,o,Matrix.Identity(4))
            return helper
        if helper in copies:return copies[helper]
        copy=helper.copy()
        if helper.data:copy.data=helper.data.copy()
        collection=next(iter(o.users_collection),bpy.context.collection)
        collection.objects.link(copy)
        owner=bpy.data.objects.get(helper.get('_lf_owner',''))
        if placement:local=Matrix.Identity(4)
        elif helper.parent:local=helper.matrix_parent_inverse@helper.matrix_basis
        elif owner:local=owner.matrix_world.inverted_safe()@helper.matrix_world
        else:local=helper.matrix_world.copy()
        attach_helper(copy,o,local)
        copy.hide_render=True;copy.hide_set(True)
        copies[helper]=copy
        for key in list(o.keys()):
            if key.startswith('_lf_nano_points') and o[key]==helper.name:o[key]=copy.name
        return copy

    for m in o.modifiers:
        if m.type=='ARRAY':
            helper=owned(m.offset_object)
            if helper!=m.offset_object:m.offset_object=helper
        elif m.type=='NODES' and m.node_group:
            references=[node for node in m.node_group.nodes if node.bl_idname=='GeometryNodeObjectInfo'
                        and node.inputs['Object'].default_value
                        and node.inputs['Object'].default_value.get('_lf_instance_helper')
                        and (node.inputs['Object'].default_value.parent is None
                             or not owns_helper(node.inputs['Object'].default_value,o))]
            if not references:continue
            if m.node_group.users>1 or m.node_group.library:m.node_group=m.node_group.copy()
            for node in m.node_group.nodes:
                if node.bl_idname=='GeometryNodeObjectInfo':
                    helper=node.inputs['Object'].default_value
                    replacement=owned(helper,True)
                    if replacement!=helper:node.inputs['Object'].default_value=replacement


def instance_helpers(o):
    """Only Studio's flagged implementation IDs, never artist references."""
    for m in o.modifiers:
        if m.type=='ARRAY':
            helper=m.offset_object
            if helper and helper.get('_lf_instance_helper'):yield helper
        elif m.type=='NODES' and m.node_group:
            for node in m.node_group.nodes:
                if node.bl_idname=='GeometryNodeObjectInfo':
                    helper=node.inputs['Object'].default_value
                    if helper and helper.get('_lf_instance_helper'):yield helper


@bpy.app.handlers.persistent
def sync_native_owners(scene,depsgraph=None):
    """Isolate native copies before evaluation, inside Blender's own history.

    Native duplicate/move macros and operator search remain Blender-owned.
    No timer, operator replacement or second Undo entry repairs their data.
    Rendering and worker threads must never allocate or rewire scene IDs here.
    Do not retain RNA references across Undo/load; inspect current scene IDs.
    """
    global _syncing_native_owners
    if (_syncing_native_owners or current_thread() is not main_thread()
            or (depsgraph is not None and depsgraph.mode!='VIEWPORT')
            or bpy.app.is_job_running('RENDER')):return
    _syncing_native_owners=True
    try:
        for o in tuple(scene.objects):
            if (o.type!='MESH' or not o.is_editable
                    or not ('_lf_array_stages' in o or '_lf_nano_inventory' in o)):continue
            if any(not owns_helper(helper,o) for helper in instance_helpers(o)):
                ensure_owners(o)
    finally:_syncing_native_owners=False


def register_handlers():
    if sync_native_owners not in bpy.app.handlers.depsgraph_update_pre:
        bpy.app.handlers.depsgraph_update_pre.append(sync_native_owners)


def unregister_handlers():
    if sync_native_owners in bpy.app.handlers.depsgraph_update_pre:
        bpy.app.handlers.depsgraph_update_pre.remove(sync_native_owners)

def update(section,o=None):
    o=o or ops.active();cfg=config(section,o)
    result=array_update(o,cfg) if section=='ArrayMesh' else nano_update(o,cfg)
    # RNA modifier writes must tag the owning ID for native global undo,
    # including when the preceding history entry is a Sculpt node.
    o.update_tag(refresh={'OBJECT','DATA','TIME'})
    return result

def array_update(o,cfg):
    stages=json.loads(o.get('_lf_array_stages','[]'))
    if not stages:stages=[dict(cfg)]
    stage=max(0,min(len(stages)-1,int(cfg['stage'])));stages[stage]=dict(cfg)
    o['_lf_array_stages']=json.dumps(stages)
    for i,values in enumerate(stages):
        name=f'Sculpt Array {i+1}';existing=o.modifiers.get(name);m=modifier(o,name,'ARRAY')
        if existing is None:
            post=[o.modifiers.find(name) for name in ('Sculpt Array Smooth','Sculpt Array Pattern','Sculpt Array Path') if o.modifiers.get(name)]
            if post:o.modifiers.move(o.modifiers.find(m.name),min(post))
        m.count=max(1,int(values['count']));m.use_relative_offset=False;m.use_constant_offset=False;m.use_object_offset=True
        m.show_viewport=m.show_render=bool(cfg['enabled']);m.use_merge_vertices=bool(values['extrude'])
        if values['extrude']:m.merge_threshold=.001
        helper=m.offset_object
        if not owns_helper(helper,o):
            helper=bpy.data.objects.new(o.name+' · Array Offset '+str(i+1),None)
            helper['_lf_instance_helper']=True;helper['_lf_owner']=o.name;bpy.context.collection.objects.link(helper);m.offset_object=helper
            helper.hide_render=True;helper.hide_set(True)
        extent=[max(float(o.dimensions[a]),.001) for a in range(3)]
        # Base mesh dimensions avoid feedback as the evaluated array grows.
        if o.data.vertices:extent=[max(v.co[a] for v in o.data.vertices)-min(v.co[a] for v in o.data.vertices) for a in range(3)]
        offset=Vector(tuple(values['offset_'+a]*max(extent[j],.001) for j,a in enumerate('xyz')))
        pivot=Vector(tuple(values['pivot_'+a] for a in 'xyz'))
        rotation=Euler(tuple(math.radians(values['rotate_'+a]) for a in 'xyz')).to_matrix().to_4x4()
        scale=Matrix.Diagonal(Vector(tuple(values['scale_'+a]*(-1 if values['mirror_'+a] else 1) for a in 'xyz')+(1,)))
        transform=Matrix.Translation(offset+pivot)@rotation@scale@Matrix.Translation(-pivot)
        attach_helper(helper,o,transform)
    for m in list(o.modifiers):
        # Only numeric Array stages are retired. Path, Smooth and Pattern have
        # the same prefix but remain separate native operations in this stack.
        if m.type=='ARRAY' and m.name.startswith('Sculpt Array ') and m.name[len('Sculpt Array '):].isdigit() and m.name not in {f'Sculpt Array {i+1}' for i in range(len(stages))}:o.modifiers.remove(m)
    smooth=modifier(o,'Sculpt Array Smooth','SMOOTH');smooth.factor=float(cfg['smooth']);smooth.iterations=2
    smooth.show_viewport=smooth.show_render=bool(cfg['enabled'] and cfg['smooth'])
    pattern=modifier(o,'Sculpt Array Pattern','NODES')
    pattern.show_viewport=pattern.show_render=bool(cfg['enabled'] and cfg['pattern_off']>0)
    if cfg['pattern_off']>0:
        group=pattern.node_group
        if group is None:
            group=bpy.data.node_groups.new(o.name+' Array Pattern','GeometryNodeTree');pattern.node_group=group
            group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
        elif group.users>1:group=group.copy();pattern.node_group=group
        group.nodes.clear();nodes=group.nodes;links=group.links
        inp=nodes.new('NodeGroupInput');out=nodes.new('NodeGroupOutput');islands=nodes.new('GeometryNodeInputMeshIsland')
        subtract=nodes.new('ShaderNodeMath');subtract.operation='SUBTRACT';subtract.inputs[1].default_value=int(cfg['pattern_start']);links.new(islands.outputs['Island Index'],subtract.inputs[0])
        modulo=nodes.new('ShaderNodeMath');modulo.operation='FLOORED_MODULO';modulo.inputs[1].default_value=max(1,int(cfg['pattern_on'])+int(cfg['pattern_off']));links.new(subtract.outputs[0],modulo.inputs[0])
        compare=nodes.new('ShaderNodeMath');compare.operation='GREATER_THAN';compare.inputs[1].default_value=int(cfg['pattern_on'])-.5;links.new(modulo.outputs[0],compare.inputs[0])
        delete=nodes.new('GeometryNodeDeleteGeometry');delete.domain='POINT';links.new(inp.outputs['Geometry'],delete.inputs['Geometry']);links.new(compare.outputs[0],delete.inputs['Selection']);links.new(delete.outputs['Geometry'],out.inputs['Geometry'])
    return {'ok':True,'stages':len(stages),'count':int(cfg['count'])}

def nano_update(o,cfg):
    inventory=json.loads(o.get('_lf_nano_inventory','[]')) or [dict(cfg)]
    index=max(0,min(len(inventory)-1,int(cfg['index'])));cfg['index']=index;inventory[index]=dict(cfg)
    o['_lf_nano_inventory']=json.dumps(inventory)
    name='Sculpt NanoMesh' if index==0 else f'Sculpt NanoMesh {index+1}'
    source=bpy.data.objects.get(cfg['source'])
    existing=o.modifiers.get(name)
    if not source or source==o or source.type!='MESH':
        if existing:existing.show_viewport=False
        if cfg['enabled']:raise RuntimeError('Choose another mesh SubTool as the NanoMesh source')
        return {'ok':True,'enabled':False}
    # Placements are native mesh points with attributes consumed by Geometry Nodes.
    # Deterministic per-face tiles give stable placement as settings are adjusted.
    import random
    rng=random.Random(int(cfg['seed']));positions=[];rotations=[];scales=[]
    colors=o.data.color_attributes.active_color
    if len(o.data.polygons)*cfg['tile_h']*cfg['tile_v']>100000:raise RuntimeError('NanoMesh preview is limited to 100,000 instances')
    for p in o.data.polygons:
        if p.hide:continue
        vertices=[o.data.vertices[v].co for v in p.vertices]
        center=p.center.copy();normal=p.normal.copy()
        tangent=(vertices[1]-vertices[0]).normalized() if len(vertices)>1 else Vector((1,0,0))
        if tangent.length<1e-6:tangent=Vector((1,0,0))
        bitangent=normal.cross(tangent).normalized()
        edge_u=(vertices[1]-vertices[0]).length if len(vertices)>1 else 1
        edge_v=max((v-center).length for v in vertices)*1.4
        if cfg['alignment']=='NONE':rotation=Euler((0,0,0))
        elif cfg['alignment']=='NORMAL':rotation=normal.to_track_quat('Z','Y').to_euler()
        else:
            mat=Matrix((tangent,bitangent,normal)).transposed();rotation=mat.to_euler()
        for u in range(int(cfg['tile_h'])):
            for v in range(int(cfg['tile_v'])):
                if cfg['random_distribution'] and rng.random()>1-cfg['random_distribution']:continue
                x=(u+.5)/cfg['tile_h']-.5;y=(v+.5)/cfg['tile_v']-.5
                if cfg['pattern']=='DIAMOND':x+=.5/cfg['tile_h']*(v%2)
                pos=center+tangent*(x*edge_u+cfg['offset_x'])+bitangent*(y*edge_v+cfg['offset_y'])+normal*cfg['offset_z']
                pos+=tangent*rng.uniform(-cfg['x_var'],cfg['x_var'])+bitangent*rng.uniform(-cfg['y_var'],cfg['y_var'])+normal*rng.uniform(-cfg['z_var'],cfg['z_var'])
                rot=Euler(tuple(rotation[a]+math.radians(cfg['rotate_'+'xyz'[a]]+rng.uniform(-cfg[('rx_var','ry_var','rz_var')[a]],cfg[('rx_var','ry_var','rz_var')[a]])) for a in range(3)))
                size=cfg['size']
                if cfg['fit'] in ('FIT','FILL'):size*=min(edge_u/cfg['tile_h'],edge_v/cfg['tile_v']) if cfg['fit']=='FIT' else max(edge_u/cfg['tile_h'],edge_v/cfg['tile_v'])
                scale=[size*cfg[a]*(1+rng.uniform(-cfg[var],cfg[var])) for a,var in [('width','w_var'),('length','l_var'),('height','h_var')]]
                if cfg['flip_h']:scale[0]*=-1
                if cfg['flip_v']:scale[1]*=-1
                positions.append(pos);rotations.append(tuple(rot));scales.append(scale)
    m=existing or o.modifiers.new(name,'NODES')
    old_points=bpy.data.objects.get(o.get('_lf_nano_points_'+str(index),''))
    if not owns_helper(old_points,o):old_points=None
    if old_points:attach_helper(old_points,o,Matrix.Identity(4))
    if old_points and cfg['freeze'] and m.node_group:
        m.show_viewport=bool(cfg['enabled']);return {'ok':True,'instances':len(old_points.data.vertices),'frozen':True}
    if old_points is None:
        mesh=bpy.data.meshes.new(o.name+' · Nano Placement');points=bpy.data.objects.new(mesh.name,mesh)
        points['_lf_instance_helper']=True;points['_lf_owner']=o.name;bpy.context.collection.objects.link(points);points.hide_render=True;points.hide_set(True)
        o['_lf_nano_points_'+str(index)]=points.name
    else:points=old_points
    o['_lf_nano_points']=points.name
    points.data.clear_geometry();points.data.from_pydata(positions,[],[]);points.data.update()
    attach_helper(points,o,Matrix.Identity(4))
    for name,values in [('nano_rotation',rotations),('nano_scale',scales)]:
        attr=points.data.attributes.get(name) or points.data.attributes.new(name,'FLOAT_VECTOR','POINT')
        attr.data.foreach_set('vector',[v for value in values for v in value])
    if m.node_group:
        group=m.node_group
        if group.users>1:group=group.copy();m.node_group=group
        group.nodes.clear()
    else:
        group=bpy.data.node_groups.new(o.name+' · NanoMesh','GeometryNodeTree');m.node_group=group
        group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
        group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    nodes=group.nodes;links=group.links
    inp=nodes.new('NodeGroupInput');out=nodes.new('NodeGroupOutput')
    info=nodes.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=source;info.transform_space='ORIGINAL'
    pointinfo=nodes.new('GeometryNodeObjectInfo');pointinfo.inputs['Object'].default_value=points;pointinfo.transform_space='RELATIVE'
    instance=nodes.new('GeometryNodeInstanceOnPoints');links.new(pointinfo.outputs['Geometry'],instance.inputs['Points']);links.new(info.outputs['Geometry'],instance.inputs['Instance'])
    for name,socket in [('nano_rotation','Rotation'),('nano_scale','Scale')]:
        node=nodes.new('GeometryNodeInputNamedAttribute');node.data_type='FLOAT_VECTOR';node.inputs['Name'].default_value=name
        links.new(node.outputs['Attribute'],instance.inputs[socket])
    join=nodes.new('GeometryNodeJoinGeometry')
    if cfg['show_placement']:links.new(inp.outputs['Geometry'],join.inputs['Geometry'])
    if cfg['show_instances']:links.new(instance.outputs['Instances'],join.inputs['Geometry'])
    realize=nodes.new('GeometryNodeRealizeInstances');links.new(join.outputs['Geometry'],realize.inputs['Geometry']);links.new(realize.outputs['Geometry'],out.inputs['Geometry'])
    for i,slot in enumerate(inventory):
        other=o.modifiers.get('Sculpt NanoMesh' if i==0 else f'Sculpt NanoMesh {i+1}')
        if other:other.show_viewport=other.show_render=bool(slot['enabled'] and (not cfg['hide_others'] or i==index))
    m.show_in_editmode=False
    source.hide_set(True)
    return {'ok':True,'instances':len(positions),'source':source.name}

def dispatch(section,kind,**kw):
    from .extended import make_mesh,subtool
    o=ops.active();cfg=config(section,o)
    if kind=='UPDATE':return update(section,o)
    if kind=='COPY':_clipboard[section]=dict(cfg);return {'ok':True}
    if kind=='PASTE':
        if section not in _clipboard:raise RuntimeError('Copy settings first')
        cfg.update(_clipboard[section]);save(section,cfg,o);return update(section,o)
    if kind in ('OPEN','SAVE'):
        path=Path(kw['path'])
        if kind=='SAVE':path.write_text(json.dumps({'section':section,'settings':cfg},indent=2))
        else:
            data=json.loads(path.read_text())
            if data.get('section')!=section:raise RuntimeError('This preset belongs to another palette')
            allowed=set(ARRAY_DEFAULTS if section=='ArrayMesh' else NANO_DEFAULTS)
            cfg.update({k:v for k,v in data.get('settings',{}).items() if k in allowed});save(section,cfg,o);return update(section,o)
        return {'ok':True,'path':str(path)}
    if kind=='RESET':
        index=cfg['stage'] if section=='ArrayMesh' else cfg['index']
        cfg=dict(ARRAY_DEFAULTS if section=='ArrayMesh' else NANO_DEFAULTS)
        cfg['stage' if section=='ArrayMesh' else 'index']=index
        save(section,cfg,o);return update(section,o)
    if kind=='MAKE_MESH':return make_mesh(section+' Mesh')
    if section=='ArrayMesh':
        stages=json.loads(o.get('_lf_array_stages','[]')) or [dict(cfg)]
        index=max(0,min(len(stages)-1,int(cfg['stage'])))
        if kind in ('APPEND','INSERT'):
            stages.insert(len(stages) if kind=='APPEND' else index+1,dict(ARRAY_DEFAULTS,enabled=True));cfg=stages[-1] if kind=='APPEND' else stages[index+1]
            cfg['stage']=len(stages)-1 if kind=='APPEND' else index+1
        elif kind=='DELETE':
            stages.pop(index)
            if not stages:stages=[dict(ARRAY_DEFAULTS)]
            index=min(index,len(stages)-1);cfg=stages[index];cfg['stage']=index
        elif kind=='STAGE':
            index=max(0,min(len(stages)-1,int(kw['value'])));cfg=dict(stages[index]);cfg['stage']=index
        elif kind.startswith('SWITCH_'):
            a,b=kind[-2:].lower()
            for prefix in ('offset_','scale_','rotate_','pivot_'):cfg[prefix+a],cfg[prefix+b]=cfg[prefix+b],cfg[prefix+a]
        elif kind=='TO_NANO':
            cp=ops.active().copy();cp.data=o.data.copy();cp.name=o.name+' · Array Source';bpy.context.collection.objects.link(cp)
            for m in list(cp.modifiers):
                if m.type=='ARRAY':cp.modifiers.remove(m)
            nano=dict(NANO_DEFAULTS,source=cp.name,enabled=True);save('NanoMesh',nano,o);return nano_update(o,nano)
        elif kind=='ALIGN_PATH':
            curve=bpy.data.objects.get(kw.get('target',''))
            if not curve or curve.type!='CURVE':raise RuntimeError('Choose a Curve object for the array path')
            m=modifier(o,'Sculpt Array Path','CURVE');m.object=curve;m.deform_axis='POS_X'
            return {'ok':True,'curve':curve.name}
        else:raise ValueError(kind)
        o['_lf_array_stages']=json.dumps(stages);save(section,cfg,o);return array_update(o,cfg)
    if kind=='EDIT_MESH':
        source=bpy.data.objects.get(cfg['source'])
        if not source:raise RuntimeError('Choose a source mesh first')
        source['_lf_nano_return']=o.name;return ops.switch_subtool(source)
    if kind=='RETURN_PLACEMENT':
        target=bpy.data.objects.get(o.get('_lf_nano_return',''))
        if not target:raise RuntimeError('Use Edit Mesh from a NanoMesh placement first')
        return ops.switch_subtool(target)
    if kind=='SPLIT_SCREEN':
        bpy.ops.screen.area_split(direction='VERTICAL',factor=.5);return {'ok':True}
    if kind=='EDIT_PLACEMENT':
        # Native Edit Mode changes the actual placement surface.
        bpy.ops.object.mode_set(mode='EDIT');return {'ok':True,'mode':'EDIT_MESH'}
    inventory=json.loads(o.get('_lf_nano_inventory','[]')) or [dict(cfg)]
    if kind in ('PREVIOUS','NEXT','INDEX'):
        index=(int(cfg['index'])+(-1 if kind=='PREVIOUS' else 1))%len(inventory) if kind!='INDEX' else max(0,min(len(inventory)-1,int(kw['value'])))
        cfg=dict(inventory[index]);cfg['index']=index
    elif kind=='ADD_INDEX':
        cfg=dict(NANO_DEFAULTS,index=len(inventory));inventory.append(cfg);o['_lf_nano_inventory']=json.dumps(inventory)
    elif kind=='ONE_TO_MESH':
        mods=[(m,m.show_viewport) for m in o.modifiers if m.name.startswith('Sculpt NanoMesh')]
        selected='Sculpt NanoMesh' if cfg['index']==0 else f"Sculpt NanoMesh {cfg['index']+1}"
        try:
            for m,_ in mods:m.show_viewport=m.name==selected
            return make_mesh('NanoMesh Index '+str(cfg['index']+1))
        finally:
            for m,visible in mods:m.show_viewport=visible
    elif kind=='RANDOM_SEED':cfg['seed']=int(cfg['seed'])+1
    elif kind=='DELETE':
        name='Sculpt NanoMesh' if cfg['index']==0 else f"Sculpt NanoMesh {cfg['index']+1}"
        if o.modifiers.get(name):o.modifiers.remove(o.modifiers[name])
        cfg['enabled']=False
    else:raise ValueError(kind)
    save(section,cfg,o);return nano_update(o,cfg)
