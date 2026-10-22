"""Reference-palette operations, dispatched by the existing undoable sculpt command.
Blender owns its meshes/modifiers/attributes. No second stroke engine or keymap.
Base-index operations reject Multires grids; topology changes use staged targets.
"""
import colorsys
import json
import math
import random
import struct
from contextlib import nullcontext
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from . import ops, state
DEFAULTS = {
 'SubTool': {'visible_count':4, 'visibility_set':1},
 'Geometry': {'smooth':True,'smooth_uv':True,'dynamic':False,'dynamic_levels':2,'crease':1.0,'edge_loops':1},
 'Masking': {'threshold':.5,'angle':45.,'ao_distance':1.,'ao_samples':8,'feature_border':True,'feature_groups':True,'feature_crease':True,'axis':'Z','invert_direction':False,'mask_adjust':.5},
 'PolyGroups': {'angle':45.,'tolerance':.1,'mask_tolerance':.5,'edge_sensitivity':.5,'coverage':1.0,'cluster':0.,'additive':False},
 'Deformation': {'axes':'X','respect_mask':True},
 'Morph Target': {'morph':0.,'width':0.,'height':0.,'depth':0.,'dist':0.},
 'Polypaint': {'colorize':False,'gradient':False,'draft_angle':45.,'axis':'Z','invert_direction':False,'quality':8,'min_thickness':0.,'max_thickness':1.,'color_adjust':.1},
 'Layers': {'mdd_speed':1.0},
}
_clipboard = {}
_last_deformation = None


def settings(section, obj=None):
    o=obj or ops.active()
    try:saved=json.loads(o.get('_lf_palette_'+section,'{}'))
    except (ValueError,TypeError):saved={}
    return dict(DEFAULTS.get(section,{}), **saved)


def option(section,key,value,obj=None):
    o=obj or ops.active();storage='_lf_palette_'+section;original=o.get(storage);values=settings(section,o);previous=values.get(key);values[key]=value
    if section in ('Masking','Polypaint') and key=='axis':values['use_view_direction']=False
    o['_lf_palette_'+section]=json.dumps(values)
    if section=='Layers' and key=='mdd_speed' and o.data.shape_keys and o.data.shape_keys.animation_data:
        from ..advanced.anim_layers import _iter_action_fcurves
        for curve in _iter_action_fcurves(o.data.shape_keys.animation_data.action):
            if 'MDD ' in curve.data_path:
                for point in curve.keyframe_points:point.co.x=1+(point.co.x-1)*float(previous or 1)/max(float(value),.001)
                curve.update()
    if section in ('ArrayMesh','NanoMesh'):
        from . import instances
        try:return instances.update(section,o)
        except Exception:
            if original is None:
                if storage in o:del o[storage]
            else:o[storage]=original
            try:instances.update(section,o)
            except Exception:pass
            raise
    if section=='Geometry' and key.startswith('dynamic'):
        return geometry('DYNAMIC')
    if section=='Polypaint' and key=='colorize':return polypaint('COLORIZE')
    return {'ok':True,'option':key,'value':value}


def base_target():
    o=ops.active();m=ops.multires()
    if m and m.sculpt_levels:
        raise RuntimeError('Lower to base resolution for indexed vertex/attribute editing; high sculpt grids remain unchanged')
    if o.library or o.data.library:raise RuntimeError('Make a local Sculpt Copy before editing linked data')
    return o


def coordinates(o=None):
    o=o or base_target()
    target=o.active_shape_key.data if o.data.shape_keys and o.active_shape_key_index else o.data.vertices
    return target,[v.co.copy() for v in target]


def adjacency(o):
    adjacent=[set() for _ in o.data.vertices]
    for e in o.data.edges:
        a,b=e.vertices;adjacent[a].add(b);adjacent[b].add(a)
    return adjacent


def face_values(o):
    attr=o.data.attributes.get('.sculpt_face_set')
    return [x.value for x in attr.data] if attr else [1]*len(o.data.polygons)


def write_faces(o,values):
    attr=o.data.attributes.get('.sculpt_face_set') or o.data.attributes.new('.sculpt_face_set','INT','FACE')
    attr.data.foreach_set('value',values);o.data.update()


def vertex_colors(o):
    attr=o.data.color_attributes.active_color
    if attr is None:return [(1.,1.,1.,1.)]*len(o.data.vertices)
    if attr.domain=='POINT':return [tuple(v.color) for v in attr.data]
    colors=[Vector((0.,0.,0.,0.)) for _ in o.data.vertices];counts=[0]*len(colors)
    for loop in o.data.loops:
        colors[loop.vertex_index]+=Vector(attr.data[loop.index].color);counts[loop.vertex_index]+=1
    return [tuple(c/max(1,n)) for c,n in zip(colors,counts)]


def write_colors(o,colors):
    attr=o.data.color_attributes.get('Sculpt Polypaint')
    if attr is None:attr=o.data.color_attributes.new('Sculpt Polypaint','FLOAT_COLOR','POINT')
    attr.data.foreach_set('color',[channel for c in colors for channel in c])
    o.data.color_attributes.active_color=attr;o.data.color_attributes.active=attr;o.data.update()
    return attr


def subtool(kind, **kw):
    o=ops.active();meshes=ops.meshes();index=meshes.index(o)
    if kind in ('UP','DOWN'):
        return ops.switch_subtool(meshes[max(0,min(len(meshes)-1,index+(-1 if kind=='UP' else 1)))])
    if kind in ('MOVE_UP','MOVE_DOWN','AUTO_REORDER'):
        if kind=='AUTO_REORDER':meshes.sort(key=lambda x:len(x.data.polygons),reverse=True)
        else:
            other=max(0,min(len(meshes)-1,index+(-1 if kind=='MOVE_UP' else 1)))
            meshes[index],meshes[other]=meshes[other],meshes[index]
        for i,x in enumerate(meshes):x['_lf_subtool_order']=i
    elif kind=='RENAME':
        name=str(kw.get('name','')).strip()
        if not name:raise RuntimeError('Enter a SubTool name')
        o.name=name
    elif kind=='FOLDER':
        name=str(kw.get('name','Sculpt Folder')).strip() or 'Sculpt Folder'
        folder=bpy.data.collections.new(name);folder['_lf_subtool_folder']=True
        bpy.context.scene.collection.children.link(folder)
        folder.objects.link(o)
        for c in list(o.users_collection):
            if c!=folder and c.get('_lf_subtool_folder'):c.objects.unlink(o)
    elif kind in ('ALL_LOW','ALL_HIGH'):
        for x in meshes:
            for m in x.modifiers:
                if m.type=='MULTIRES':m.levels=m.sculpt_levels=0 if kind=='ALL_LOW' else m.total_levels
        ops.stop_grid_layer_recording()
    elif kind in ('STORE_HOME','STORE_TARGET','HOME','TARGET'):
        bpy.context.view_layer.update()
        key='_lf_stage_'+('home' if kind.endswith('HOME') else 'target')
        targets=meshes if kw.get('all',True) else [o]
        restored=0
        for x in targets:
            if kind.startswith('STORE'):x[key]=[v for row in x.matrix_world for v in row]
            elif key in x:
                raw=x[key];x.matrix_world=Matrix([raw[i:i+4] for i in range(0,16,4)])
                restored+=1
        if not kind.startswith('STORE') and not restored:raise RuntimeError('Store this Stager pose first')
    elif kind=='COPY':
        old=bpy.data.objects.get('_Landfall SubTool Clipboard')
        if old and old.get('_lf_clipboard'):bpy.data.objects.remove(old,do_unlink=True)
        cp=o.copy();cp.data=o.data.copy();cp.name='_Landfall SubTool Clipboard';cp['_lf_clipboard']=True
        # An unlinked datablock survives selection/visibility changes, saved in blend.
        cp.use_fake_user=True
        from .instances import ensure_owners
        ensure_owners(cp)
    elif kind=='PASTE':
        source=next((x for x in bpy.data.objects if x.get('_lf_clipboard')),None)
        if not source:raise RuntimeError('Copy a SubTool first')
        cp=source.copy();cp.data=source.data.copy();del cp['_lf_clipboard'];cp.use_fake_user=False
        cp.name=o.name+' Copy';bpy.context.collection.objects.link(cp);return ops.switch_subtool(cp)
    elif kind in ('DELETE_OTHER','DELETE_ALL'):
        targets=[x for x in meshes if kind=='DELETE_ALL' or x!=o]
        with ops.object_mode():
            for x in targets:
                ops.recovery(x,kind);bpy.data.objects.remove(x,do_unlink=True)
            if kind=='DELETE_ALL':
                # Leave an editable empty target, keeping workspace/context valid.
                mesh=bpy.data.meshes.new('Empty SubTool');cp=bpy.data.objects.new('Empty SubTool',mesh)
                bpy.context.collection.objects.link(cp);ops.switch_subtool(cp)
    elif kind=='VISIBILITY_SET':
        key='_lf_visibility_'+str(int(kw['index']));scene=bpy.context.scene
        if kw.get('store') or key not in scene:scene[key]=json.dumps({x.name:not x.hide_get() for x in meshes})
        else:
            visible=json.loads(scene[key])
            for x in meshes:x.hide_set(not visible.get(x.name,False))
            if o.hide_get():
                other=next((x for x in meshes if not x.hide_get()),None)
                if other:ops.switch_subtool(other)
        scene['_lf_visibility_active']=int(kw['index'])
    else:raise ValueError(kind)
    return {'ok':True,'subtool':ops.active().name}


def topology(kind, **kw):
    o=ops.topology_target(kind)
    with ops.object_mode():
        if kind.startswith('SPLIT_'):
            bm=bmesh.new();bm.from_mesh(o.data)
            try:
                if kind=='SPLIT_GROUPS':
                    layer=bm.faces.layers.int.get('.sculpt_face_set');grouped={}
                    for f in bm.faces:grouped.setdefault(f[layer] if layer else 1,[]).append(f.index)
                    parts=list(grouped.values())
                elif kind=='SPLIT_HIDDEN':parts=[[p.index for p in o.data.polygons if p.hide],[p.index for p in o.data.polygons if not p.hide]]
                else:
                    unseen=set(bm.faces);parts=[]
                    while unseen:
                        seed=unseen.pop();todo=[seed];part=[]
                        while todo:
                            f=todo.pop();part.append(f.index)
                            for v in f.verts:
                                for neighbor in v.link_faces:
                                    if neighbor in unseen:unseen.remove(neighbor);todo.append(neighbor)
                        parts.append(part)
                parts=[p for p in parts if p]
                if len(parts)<2:raise RuntimeError('The surface has no separate regions to split')
                copies=[]
                for part in parts:
                    cp=o.copy();cp.data=o.data.copy();cp.name=o.name+' · Part';bpy.context.collection.objects.link(cp)
                    cut=bmesh.new();cut.from_mesh(cp.data);cut.faces.ensure_lookup_table()
                    keep=set(part);bmesh.ops.delete(cut,geom=[f for f in cut.faces if f.index not in keep],context='FACES')
                    cut.to_mesh(cp.data);cut.free();copies.append(cp)
                o.hide_set(True);ops.switch_subtool(copies[0])
            finally:bm.free()
        elif kind=='BOOLEAN':
            other=bpy.data.objects.get(kw.get('target',''))
            if not other or other==o:raise RuntimeError('Choose a different SubTool as the Boolean operand')
            m=o.modifiers.new('Sculpt Boolean','BOOLEAN');m.operation=kw.get('operation','DIFFERENCE');m.object=other;m.solver='EXACT'
            # Live preview preserves operands; Make Mesh is explicit.
            other.display_type='WIRE';other.hide_render=True
        elif kind in ('PROJECT','PROJECT_MORPH'):
            other=bpy.data.objects.get(kw.get('target',''))
            if not other or other==o:raise RuntimeError('Choose the projection source SubTool')
            m=o.modifiers.new('Sculpt Surface Projection','SHRINKWRAP');m.target=other
            m.wrap_method='NEAREST_SURFACEPOINT';m.offset=float(kw.get('offset',0))
        else:
            bm=bmesh.new();bm.from_mesh(o.data)
            try:
                if kind=='DELETE_HIDDEN':bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.hide],context='FACES')
                elif kind=='WELD':bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=float(kw.get('distance',.0001)))
                elif kind=='TRIANGULATE':bmesh.ops.triangulate(bm,faces=list(bm.faces))
                elif kind=='QUADS':bmesh.ops.join_triangles(bm,faces=list(bm.faces),angle_face_threshold=math.pi,angle_shape_threshold=math.pi)
                elif kind=='EDGE_LOOP':
                    selected=[e for e in bm.edges if e.is_boundary]
                    if not selected:raise RuntimeError('EdgeLoop requires an open boundary; use a masked extraction or hide/delete a region')
                    bmesh.ops.subdivide_edges(bm,edges=selected,cuts=int(kw.get('cuts',1)),use_grid_fill=True)
                elif kind=='GROUP_LOOPS':
                    fs=bm.faces.layers.int.get('.sculpt_face_set')
                    edges=[e for e in bm.edges if len(e.link_faces)==2 and fs and e.link_faces[0][fs]!=e.link_faces[1][fs]]
                    if not edges:raise RuntimeError('Create distinct PolyGroups before Group Loops')
                    bmesh.ops.bevel(bm,geom=edges,offset=.02,segments=int(kw.get('cuts',1)),affect='EDGES')
                elif kind=='UNWELD':
                    fs=bm.faces.layers.int.get('.sculpt_face_set')
                    edges=[e for e in bm.edges if fs and len(e.link_faces)==2 and e.link_faces[0][fs]!=e.link_faces[1][fs]]
                    bmesh.ops.split_edges(bm,edges=edges)
                elif kind=='FLIP':bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
                else:raise ValueError(kind)
                bm.to_mesh(o.data)
            finally:bm.free()
    return {'ok':True,'operation':kind,'subtool':ops.active().name}


def geometry(kind, **kw):
    o=ops.active();cfg=settings('Geometry');m=ops.multires()
    if kind=='MAKE_MESH':return make_mesh(kw.get('label','Evaluated Mesh'))
    if kind=='LEVEL':
        if not m:raise RuntimeError('Divide first')
        m.levels=m.sculpt_levels=max(0,min(m.total_levels,int(kw['value'])));ops.stop_grid_layer_recording()
    elif kind in ('RECONSTRUCT','REBUILD','CAGE','RESTRICT'):
        if kind in ('RECONSTRUCT','REBUILD'):
            o=ops.topology_target(kind)
            with ops.object_mode():
                m=ops.multires(True)
                result=(bpy.ops.object.multires_unsubdivide if kind=='RECONSTRUCT' else bpy.ops.object.multires_rebuild_subdiv)(modifier=m.name)
                if 'FINISHED' not in result:raise RuntimeError('Native Multires could not reconstruct this topology')
        elif m:
            if kind=='CAGE':m.show_on_cage=not m.show_on_cage
            else:m.use_sculpt_base_mesh=not m.use_sculpt_base_mesh
        else:raise RuntimeError('Divide first')
    elif kind=='DYNAMIC':
        m=next((m for m in o.modifiers if m.name=='Sculpt Dynamic Subdiv' and m.type=='SUBSURF'),None)
        if not m:m=o.modifiers.new('Sculpt Dynamic Subdiv','SUBSURF')
        m.levels=m.render_levels=int(cfg['dynamic_levels']);m.show_viewport=bool(cfg['dynamic']);m.show_in_editmode=True
    elif kind=='APPLY_DYNAMIC':
        m=next((m for m in o.modifiers if m.name=='Sculpt Dynamic Subdiv'),None)
        if not m:raise RuntimeError('Enable Dynamic Subdiv first')
        return make_mesh('Dynamic Subdiv')
    elif kind=='FREEZE':
        if '_lf_frozen_source' not in o:
            if not m or not m.total_levels:raise RuntimeError('Divide before freezing subdivision detail')
            source=ops.recovery(o,'Freeze Subdivision');o['_lf_frozen_source']=source.name
            m.levels=m.sculpt_levels=0
        else:
            source=bpy.data.objects.get(o['_lf_frozen_source'])
            if not source:raise RuntimeError('Frozen detail snapshot is missing')
            # Shrinkwrap a new subdivided surface to the preserved high detail.
            with ops.object_mode():
                if not ops.multires():ops.multires(True)
                m=ops.multires();original=next((x for x in source.modifiers if x.type=='MULTIRES'),None)
                levels=original.total_levels if original else 1
                while m.total_levels<levels:bpy.ops.object.multires_subdivide(modifier=m.name)
                m.levels=m.sculpt_levels=levels
                projection=o.modifiers.new('Frozen Detail Projection','SHRINKWRAP');projection.target=source
                projection.wrap_method='NEAREST_SURFACEPOINT';source.hide_set(False);source.display_type='WIRE'
            del o['_lf_frozen_source']
    elif kind in ('CREASE','UNCREASE'):
        o=base_target();values=face_values(o);edge_faces=[[] for _ in o.data.edges];edge_by_key={tuple(sorted(e.vertices)):e.index for e in o.data.edges}
        for p in o.data.polygons:
            for key in p.edge_keys:edge_faces[edge_by_key[tuple(sorted(key))]].append(values[p.index])
        attr=o.data.attributes.get('crease_edge') or o.data.attributes.new('crease_edge','FLOAT','EDGE')
        for i,d in enumerate(attr.data):d.value=0 if kind=='UNCREASE' else (cfg['crease'] if len(edge_faces[i])<2 or len(set(edge_faces[i]))>1 else 0)
        o.data.update()
    elif kind=='CLAY_POLISH':
        return deformation('POLISH_FEATURES',amount=.25,axes='XYZ')
    else:raise ValueError(kind)
    return {'ok':True,'geometry':kind}


def make_mesh(label='Evaluated Surface'):
    o=ops.active()
    with ops.object_mode():
        cp=ops.surface_copy(o);cp.name=o.name+' · '+label;ops.switch_subtool(cp)
    return {'ok':True,'subtool':cp.name,'vertices':len(cp.data.vertices)}


def mirror_indices(o, axis='X'):
    _,coords=coordinates(o)
    stored=o.data.attributes.get('sculpt_morph_target')
    if stored:coords=[v.vector.copy() for v in stored.data]
    kd=KDTree(len(coords))
    for i,co in enumerate(coords):kd.insert(co,i)
    kd.balance();axis='XYZ'.index(axis);mapping=[]
    for co in coords:
        reflected=co.copy();reflected[axis]*=-1;mapping.append(kd.find(reflected)[1])
    return mapping


def mask(kind, **kw):
    o=base_target();cfg=settings('Masking');old=ops.mask_values(o);adj=adjacency(o);_,coords=coordinates(o)
    if o.mode=='SCULPT' and kind not in ('VIEW','CENTER','CREATE_ALPHA','CAVITY','PEAKS_VALLEYS'):
        # Native mask undo nodes capture the original values. Restore those
        # immediately before computing the requested custom mask.
        bpy.ops.paint.mask_flood_fill(mode='INVERT')
        ops.set_mask(old,o)
    threshold=cfg['threshold'];axis='XYZ'.index(cfg['axis'])
    if kind=='VIEW':
        overlay=bpy.context.space_data.overlay;overlay.show_sculpt_mask=not overlay.show_sculpt_mask
        return {'ok':True,'visible':overlay.show_sculpt_mask}
    if kind in ('CAVITY','PEAKS_VALLEYS'):
        bpy.ops.sculpt.mask_from_cavity(factor=.5,blur_steps=2,invert=kind=='PEAKS_VALLEYS');return {'ok':True}
    if kind in ('FLIP_SYMMETRY','MIRROR_SYMMETRY'):
        mirrored=[old[j] for j in mirror_indices(o,cfg['axis'])]
        values=mirrored if kind=='FLIP_SYMMETRY' else [max(a,b) for a,b in zip(old,mirrored)]
    elif kind=='FEATURE':
        fs=face_values(o);incident=[set() for _ in coords];edge_faces={tuple(sorted(e.vertices)):[] for e in o.data.edges}
        for p in o.data.polygons:
            for v in p.vertices:incident[v].add(fs[p.index])
            for key in p.edge_keys:edge_faces[tuple(sorted(key))].append(p.index)
        crease=o.data.attributes.get('crease_edge');values=[0.]*len(coords)
        for e in o.data.edges:
            border=len(edge_faces[tuple(sorted(e.vertices))])<2
            feature=(cfg['feature_border'] and border) or (cfg['feature_groups'] and any(len(incident[v])>1 for v in e.vertices)) or (cfg['feature_crease'] and crease and crease.data[e.index].value>0)
            if feature:
                for v in e.vertices:values[v]=1
    elif kind in ('DEPTH','FIBERS'):
        lo=min(c[axis] for c in coords);span=max(c[axis] for c in coords)-lo
        values=[(c[axis]-lo)/max(span,1e-8) for c in coords]
        if kind=='FIBERS':
            # Per loose-part root-to-tip gradient, useful for converted hair meshes.
            unseen=set(range(len(coords)))
            while unseen:
                todo=[unseen.pop()];part=[]
                while todo:
                    i=todo.pop();part.append(i)
                    for j in adj[i]:
                        if j in unseen:unseen.remove(j);todo.append(j)
                lo=min(coords[i][axis] for i in part);hi=max(coords[i][axis] for i in part)
                for i in part:values[i]=(coords[i][axis]-lo)/max(hi-lo,1e-8)
    elif kind in ('NORMALS','DRAFT'):
        direction=Vector((0,0,0));direction[axis]=-1 if cfg['invert_direction'] else 1
        if cfg.get('use_view_direction'):direction=Vector(cfg['direction'])*(-1 if cfg['invert_direction'] else 1)
        cutoff=math.cos(math.radians(cfg['angle']))
        values=[max(0.,min(1.,(v.normal.dot(direction)-cutoff)/max(1-cutoff,1e-6))) for v in o.data.vertices]
    elif kind in ('SMOOTHNESS','CHANGED'):
        if kind=='CHANGED':
            target=o.data.attributes.get('sculpt_morph_target')
            if not target:raise RuntimeError('Store a Morph Target first')
            values=[min(1.,(c-b.vector).length/max(threshold,.0001)) for c,b in zip(coords,target.data)]
        else:
            values=[min(1.,sum(1-o.data.vertices[i].normal.dot(o.data.vertices[j].normal) for j in adj[i])/max(1,len(adj[i]))/max(threshold,.001)) for i in range(len(coords))]
    elif kind=='COLOR':
        color=state.brush().color;values=[max(0.,1-Vector(c[:3]).__sub__(Vector(color)).length/max(threshold,.001)) for c in vertex_colors(o)]
    elif kind=='ALPHA':
        texture=state.brush().texture
        if not texture:raise RuntimeError('Choose a brush Alpha texture first')
        values=[max(0.,min(1.,float(texture.evaluate(c)[3]))) for c in coords]
    elif kind=='AO':
        tree=BVHTree.FromPolygons(coords,[list(p.vertices) for p in o.data.polygons],all_triangles=False)
        values=[];distance=cfg['ao_distance'];samples=int(cfg['ao_samples']);epsilon=max(distance*1e-5,1e-6)
        if len(coords)*samples>2000000:raise RuntimeError('Reduce AO samples or base point count below 2 million ray tests')
        for v,c in zip(o.data.vertices,coords):
            n=v.normal.normalized();basis=n.to_track_quat('Z','Y');hits=0
            for j in range(samples):
                a=j*2.39996323;z=(j+.5)/samples;r=math.sqrt(1-z*z)
                ray=basis@Vector((r*math.cos(a),r*math.sin(a),z))
                if tree.ray_cast(c+n*epsilon,ray,distance)[0] is not None:hits+=1
            values.append(hits/samples)
    elif kind=='ADJUST':values=[min(1,max(0,v+cfg['mask_adjust']-.5)) for v in old]
    elif kind=='CENTER':
        valid=[c for c,v in zip(coords,old) if v<.5]
        if not valid:raise RuntimeError('No unmasked vertices')
        bpy.context.scene.cursor.location=o.matrix_world@(sum(valid,Vector())/len(valid));return {'ok':True}
    elif kind=='CREATE_ALPHA':
        # Orthographic XY splat of the mask, explicitly an image datablock.
        size=256;pixels=[0.]*(size*size*4);xs=[c.x for c in coords];ys=[c.y for c in coords]
        for c,value in zip(coords,old):
            x=min(size-1,int((c.x-min(xs))/max(max(xs)-min(xs),1e-8)*(size-1)))
            y=min(size-1,int((c.y-min(ys))/max(max(ys)-min(ys),1e-8)*(size-1)));i=4*(y*size+x)
            pixels[i:i+4]=[value,value,value,1]
        image=bpy.data.images.new(o.name+' Mask Alpha',width=size,height=size);image.pixels.foreach_set(pixels);image.pack()
        return {'ok':True,'image':image.name}
    else:raise ValueError(kind)
    ops.set_mask(values,o)
    if o.mode=='SCULPT':bpy.ops.sculpt.optimize()
    return {'ok':True,'mask':kind,'min':min(values,default=0),'max':max(values,default=0)}


def polygroup(kind, **kw):
    o=base_target();cfg=settings('PolyGroups')
    native={'AUTO':'LOOSE_PARTS','UV':'UV_SEAMS','AUTO_UV':'UV_SEAMS','EDGES':'SHARP_EDGES','NORMALS':'NORMALS','SPLIT_ISLANDS':'FACE_SET_BOUNDARIES'}
    if kind not in ('AUTO','EDGES','SPLIT_ISLANDS') and o.mode=='SCULPT':
        previous=face_values(o);bpy.ops.sculpt.face_sets_init(mode='FACE_SET_BOUNDARIES');write_faces(o,previous)
    if kind=='NORMALS':
        neighbors=[set() for _ in o.data.polygons];edge_faces={tuple(sorted(e.vertices)):[] for e in o.data.edges}
        for p in o.data.polygons:
            for edge in p.edge_keys:edge_faces[tuple(sorted(edge))].append(p.index)
        for faces in edge_faces.values():
            for a in faces:
                for b in faces:
                    if a!=b:neighbors[a].add(b)
        unseen=set(range(len(neighbors)));values=[0]*len(neighbors);group=0;cosine=math.cos(math.radians(cfg['angle']))
        while unseen:
            seed=unseen.pop();group+=1;normal=o.data.polygons[seed].normal;todo=[seed]
            while todo:
                i=todo.pop();values[i]=group
                for j in neighbors[i]:
                    if j in unseen and normal.dot(o.data.polygons[j].normal)>=cosine:unseen.remove(j);todo.append(j)
        write_faces(o,values);bpy.ops.sculpt.optimize();return {'ok':True,'groups':group}
    if kind in ('UV','AUTO_UV'):
        from bpy_extras.mesh_utils import mesh_linked_uv_islands
        if not o.data.uv_layers.active:raise RuntimeError('UV Groups requires a UV map')
        values=[1]*len(o.data.polygons)
        for group,island in enumerate(mesh_linked_uv_islands(o.data),1):
            for face in island:values[face]=group
        write_faces(o,values);return {'ok':True,'groups':len(set(values))}
    if kind in native:
        threshold=math.radians(cfg['angle']) if kind=='NORMALS' else cfg['edge_sensitivity']
        bpy.ops.sculpt.face_sets_init(mode=native[kind],threshold=threshold);return {'ok':True}
    values=face_values(o)
    if kind in ('MERGE_SIMILAR','MERGE_STRAY'):
        counts={v:values.count(v) for v in set(values)}
        if kind=='MERGE_STRAY':
            incident={tuple(sorted(e.vertices)):[] for e in o.data.edges}
            for p in o.data.polygons:
                for key in p.edge_keys:incident[tuple(sorted(key))].append(p.index)
            for faces in incident.values():
                if len(faces)==2:
                    a,b=faces
                    if counts[values[a]]<max(2,len(values)*cfg['tolerance']):values[a]=values[b]
        else:
            colors=vertex_colors(o);group_colors={}
            for g in set(values):
                indices={v for p in o.data.polygons if values[p.index]==g for v in p.vertices}
                group_colors[g]=sum((Vector(colors[v][:3]) for v in indices),Vector())/max(1,len(indices))
            representatives=[];mapping={}
            for g,c in group_colors.items():
                match=next((r for r in representatives if (c-group_colors[r]).length<=cfg['tolerance']),None)
                mapping[g]=match or g
                if match is None:representatives.append(g)
            values=[mapping[v] for v in values]
    elif kind in ('MASKED_CLEAR','DYNAMESH_SUB','MASKING'):
        weights=ops.mask_values(o);group=max(values,default=0)+1
        values=[group if sum(weights[v] for v in p.vertices)/len(p.vertices)>=cfg['mask_tolerance'] else values[p.index] for p in o.data.polygons]
        if kind=='MASKED_CLEAR':ops.set_mask([0.]*len(o.data.vertices),o)
        if kind=='DYNAMESH_SUB':o['_lf_dynamesh_sub_group']=group
    elif kind=='PAINT':
        colors=vertex_colors(o);bins={};values=[]
        for p in o.data.polygons:
            c=sum((Vector(colors[v][:3]) for v in p.vertices),Vector())/len(p.vertices)
            key=tuple(round(x/max(cfg['tolerance'],.001)) for x in c)
            if key not in bins:bins[key]=len(bins)+1
            values.append(bins[key])
    elif kind in ('FRONT','REGROUP_VISIBLE'):
        group=max(values,default=0)+1
        direction=bpy.context.space_data.region_3d.view_rotation@Vector((0,0,1))
        for p in o.data.polygons:
            if not p.hide and (kind=='REGROUP_VISIBLE' or p.normal.dot(direction)>=math.cos(math.radians(cfg['angle']))):values[p.index]=group
    elif kind=='VISIBLE':return ops.groups('VISIBLE')
    else:raise ValueError(kind)
    write_faces(o,values);return {'ok':True,'groups':len(set(values))}


def deformation(kind, amount=.1, axes=None, repeat=False, _captured=False, **kw):
    global _last_deformation
    obj=ops.active();level=ops.multires()
    if obj.mode=='SCULPT' and not (level and level.sculpt_levels) and not _captured and not kind.startswith('REPEAT'):
        # A zero-strength native filter captures position undo nodes without
        # changing the surface. Python RNA edits alone bypass Sculpt undo.
        bpy.ops.sculpt.mesh_filter(type='SCALE',strength=0,iteration_count=1)
    cfg=settings('Deformation');axes=axes or cfg['axes'];selected=[i for i,a in enumerate('XYZ') if a in axes]
    if not selected:raise RuntimeError('Enable at least one axis')
    if len(selected)>1 and kind in ('ROTATE','BEND','SBEND','SKEW','SSKEW','TWIST','TAPER','SQUEEZE','PERSPECTIVE'):
        for axis in axes:deformation(kind,amount,axis,repeat=True,_captured=True)
        if not repeat:_last_deformation=(kind,amount,axes)
        return {'ok':True,'deformation':kind,'axes':axes}
    if kind.startswith('REPEAT'):
        if _last_deformation is None:raise RuntimeError('Apply a deformation first')
        k,a,ax=_last_deformation;source=ops.active()
        targets=[source] if kind=='REPEAT_ACTIVE' else [o for o in ops.meshes() if o!=source and not o.hide_get() and (kind!='REPEAT_FOLDER' or set(o.users_collection)&set(source.users_collection))]
        for o in targets:
            ops.switch_subtool(o);deformation(k,a,ax,repeat=True)
        ops.switch_subtool(source);return {'ok':True,'subtools':len(targets)}
    o=ops.active();m=ops.multires()
    filters={'POLISH':'SURFACE_SMOOTH','POLISH_FEATURES':'SURFACE_SMOOTH','POLISH_GROUPS':'RELAX_FACE_SETS','CRISP':'SHARPEN','RELAX':'RELAX','SMOOTH':'SMOOTH','CONTRAST':'ENHANCE_DETAILS','INFLATE':'INFLATE','BALLOON':'INFLATE','SPHERIZE':'SPHERE','NOISE':'RANDOM','SIZE':'SCALE'}
    if m and m.sculpt_levels:
        if kind not in filters:raise RuntimeError('Lower to base resolution for this deformation; dense levels support native sculpt filters')
        bpy.ops.sculpt.mesh_filter(type=filters[kind],strength=amount,iteration_count=1,deform_axis=set(axes))
    else:
        o=base_target();target,coords=coordinates(o)
        if not coords:raise RuntimeError('The SubTool has no vertices')
        adj=adjacency(o);mask_values=ops.mask_values(o) if cfg['respect_mask'] else [0]*len(coords)
        lo=Vector(tuple(min(c[i] for c in coords) for i in range(3)));hi=Vector(tuple(max(c[i] for c in coords) for i in range(3)));center=(lo+hi)/2
        span=hi-lo;axis=selected[0];cross=[i for i in range(3) if i!=axis];rng=random.Random(42)
        groups=face_values(o);incident=[set() for _ in coords]
        for p in o.data.polygons:
            for v in p.vertices:incident[v].add(groups[p.index])
        mirrored=mirror_indices(o,'XYZ'[axis]) if kind in ('RESYM','SMART_RESYM') else None
        out=[]
        for index,co in enumerate(coords):
            p=co.copy();local=co-center;t=(co[axis]-center[axis])/max(span[axis],1e-8)
            normal=o.data.vertices[index].normal
            if kind=='UNIFY':p=local*2/max(max(span),1e-8)
            elif kind=='MIRROR':
                for a in selected:p[a]=-p[a]
            elif kind in ('RESYM','SMART_RESYM'):
                mirrored_co=coords[mirrored[index]].copy();mirrored_co[axis]*=-1;p=(co+mirrored_co)/2
            elif kind=='OFFSET':
                for a in selected:p[a]+=amount
            elif kind=='ROTATE':p=center+Matrix.Rotation(amount*math.pi,4,'XYZ'[axis])@local
            elif kind=='SIZE':
                for a in selected:p[a]=center[a]+local[a]*(1+amount)
            elif kind in ('BEND','SBEND','TWIST'):
                angle=amount*t*math.pi*(math.sin(t*math.pi) if kind=='SBEND' else 1)
                rotation_axis='XYZ'[axis if kind=='TWIST' else cross[1]]
                p=center+Matrix.Rotation(angle,4,rotation_axis)@local
            elif kind in ('SKEW','SSKEW'):p[cross[0]]+=amount*(math.sin(t*math.pi) if kind=='SSKEW' else t)*span[axis]
            elif kind in ('TAPER','SQUEEZE','PERSPECTIVE'):
                factor=1+amount*(t if kind in ('TAPER','PERSPECTIVE') else (4*t*t-1))
                for a in cross:p[a]=center[a]+local[a]*factor
            elif kind in ('FLATTEN','RFLATTEN','SFLATTEN','RELAX_PLANE','MORPH_GRID'):
                for a in selected:p[a]=center[a] if kind!='MORPH_GRID' else round(p[a]/max(abs(amount),.001))*max(abs(amount),.001)
                if kind=='RFLATTEN':p=center+Matrix.Rotation(amount,4,'XYZ'[cross[0]])@(p-center)
                if kind=='SFLATTEN':p[axis]+=math.sin(local[cross[0]]*math.pi)*amount
            elif kind=='GRAVITY':p[axis]-=amount*(1-abs(t))
            elif kind=='NOISE':p+=Vector(tuple(rng.uniform(-amount,amount) if a in selected else 0 for a in range(3)))
            elif kind in ('INFLATE','BALLOON'):p+=normal*amount
            elif kind=='SPHERIZE':p=center+local.normalized()*max(span)/2
            else:
                avg=sum((coords[j] for j in adj[index]),Vector())/max(1,len(adj[index]));delta=avg-co
                if kind in ('POLISH','POLISH_FEATURES','CRISP'):delta=normal*delta.dot(normal)
                if kind=='POLISH_FEATURES' and len(incident[index])>1:delta*=0
                if kind=='POLISH_GROUPS' and len(incident[index])>1:delta*=0
                if kind in ('CONTRAST','CRISP'):delta=-delta
                if kind not in ('POLISH','POLISH_FEATURES','POLISH_GROUPS','CRISP','SMOOTH','RELAX','CONTRAST'):raise ValueError(kind)
                p=co+delta
            # Amount sliders are momentary actions; mask weights apply to all axes.
            blend=1 if kind in ('OFFSET','ROTATE','SIZE','BEND','SBEND','TWIST','SKEW','SSKEW','TAPER','SQUEEZE','PERSPECTIVE','GRAVITY','NOISE','INFLATE','BALLOON','MORPH_GRID','UNIFY','MIRROR','RESYM','SMART_RESYM') else min(1,abs(amount))
            out.append(co+(p-co)*blend*(1-mask_values[index]))
        for v,co in zip(target,out):v.co=co
        o.data.update()
        if o.mode=='SCULPT':bpy.ops.sculpt.optimize()
    if not repeat:_last_deformation=(kind,amount,axes)
    return {'ok':True,'deformation':kind,'axes':axes}


def morph(kind, value=0., **kw):
    o=base_target()
    if o.mode=='SCULPT' and kind not in ('STORE','DELETE','DIFFERENCE'):
        bpy.ops.sculpt.mesh_filter(type='SCALE',strength=0,iteration_count=1)
    with nullcontext():
        stored=o.data.attributes.get('sculpt_morph_target')
        target,current=coordinates(o)
        if kind=='STORE':
            stored=stored or o.data.attributes.new('sculpt_morph_target','FLOAT_VECTOR','POINT')
            stored.data.foreach_set('vector',[v for c in current for v in c])
            o['_lf_morph_count']=len(current)
            for key in ('_lf_morph_blend_base','_lf_morph_last_output'):
                if key in o:del o[key]
        elif not stored or int(o.get('_lf_morph_count',-1))!=len(current):
            raise RuntimeError('StoreMT first; Morph Target requires identical base topology')
        elif kind=='DELETE':
            o.data.attributes.remove(stored)
            for key in ('_lf_morph_blend_base','_lf_morph_last_output','_lf_morph_count'):
                if key in o:del o[key]
        elif kind=='SWITCH':
            old=[v.vector.copy() for v in stored.data]
            for a,b,c,d in zip(target,stored.data,current,old):a.co=d;b.vector=c
            for key in ('_lf_morph_blend_base','_lf_morph_last_output'):
                if key in o:del o[key]
            o.data.update()
        elif kind=='DIFFERENCE':
            delta=[c-b.vector for c,b in zip(current,stored.data)]
            cp=o.copy();cp.data=o.data.copy();bpy.context.collection.objects.link(cp);cp.name=o.name+' · Morph Difference'
            if cp.data.shape_keys:cp.shape_key_clear()
            for v,c in zip(cp.data.vertices,delta):v.co=c
            return ops.switch_subtool(cp)
        else:
            raw=[v for c in current for v in c]
            last=list(o.get('_lf_morph_last_output',[]))
            if len(last)!=len(raw) or any(abs(a-b)>1e-6 for a,b in zip(raw,last)):
                o['_lf_morph_blend_base']=raw
            baseline_raw=o.get('_lf_morph_blend_base',raw)
            baseline=[Vector(baseline_raw[i:i+3]) for i in range(0,len(baseline_raw),3)]
            axis={'WIDTH':0,'HEIGHT':1,'DEPTH':2}.get(kind);weights=ops.mask_values(o)
            for i,(v,c,b) in enumerate(zip(target,baseline,stored.data)):
                delta=b.vector-c
                if axis is not None:delta=Vector(tuple(delta[a] if a==axis else 0 for a in range(3)))
                if kind=='DIST':delta=delta.normalized()*value
                else:delta*=value
                v.co=c+delta*(1-weights[i])
            o['_lf_morph_last_output']=[v for item in target for v in item.co]
            o.data.update()
    if o.mode=='SCULPT':bpy.ops.sculpt.optimize()
    return {'ok':True,'morph':kind}


def polypaint(kind, **kw):
    o=base_target();cfg=settings('Polypaint');colors=vertex_colors(o);weights=ops.mask_values(o)
    brush=state.brush();primary=tuple(brush.color);secondary=tuple(brush.secondary_color)
    if kind=='COLORIZE':
        sp=bpy.context.space_data;sp.shading.type='SOLID';sp.shading.light='STUDIO';sp.shading.color_type='VERTEX' if cfg['colorize'] else 'MATERIAL'
        if cfg['colorize'] and o.data.color_attributes.active_color is None:write_colors(o,colors)
        return {'ok':True}
    write_colors(o,colors)
    if o.mode=='SCULPT':bpy.ops.sculpt.color_filter(type='FILL',strength=0,use_immediate=True)
    if kind=='FROM_GROUPS':
        groups=face_values(o);sums=[Vector((0,0,0)) for _ in colors];counts=[0]*len(colors)
        for p in o.data.polygons:
            rgb=colorsys.hsv_to_rgb((groups[p.index]*.61803398875)%1,.65,.85)
            for v in p.vertices:sums[v]+=Vector(rgb);counts[v]+=1
        result=[(*tuple(c/max(1,n)),1) for c,n in zip(sums,counts)]
    elif kind in ('FLIP_SYMMETRY','MIRROR_SYMMETRY'):
        mapping=mirror_indices(o,cfg['axis']);result=[colors[i] for i in mapping]
        if kind=='MIRROR_SYMMETRY':
            ax='XYZ'.index(cfg['axis']);result=[result[i] if v.co[ax]>0 else colors[i] for i,v in enumerate(o.data.vertices)]
    elif kind=='FROM_TEXTURE':
        uv=o.data.uv_layers.active;image=None
        for mat in o.data.materials:
            if mat and mat.use_nodes:
                node=next((n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image),None)
                if node:image=node.image;break
        if not uv or not image:raise RuntimeError('An active UV map and material Image Texture are required')
        pixels=list(image.pixels);width,height=image.size;result=list(colors)
        for loop in o.data.loops:
            u,v=uv.data[loop.index].uv;x=int((u%1)*(width-1));y=int((v%1)*(height-1));i=(y*width+x)*image.channels
            result[loop.vertex_index]=tuple(pixels[i:i+3])+(1,)
    elif kind in ('DRAFT','THICKNESS'):
        ax='XYZ'.index(cfg['axis']);direction=Vector((0,0,0));direction[ax]=-1 if cfg['invert_direction'] else 1
        if cfg.get('use_view_direction'):direction=Vector(cfg['direction'])*(-1 if cfg['invert_direction'] else 1)
        values=[]
        if kind=='THICKNESS':
            coords=[v.co.copy() for v in o.data.vertices];tree=BVHTree.FromPolygons(coords,[list(p.vertices) for p in o.data.polygons]);epsilon=1e-5
            if len(coords)*int(cfg['quality'])>2000000:raise RuntimeError('Lower Thickness quality or base point count below 2 million ray tests')
        for v in o.data.vertices:
            if kind=='DRAFT':t=max(0,min(1,(v.normal.dot(direction)-math.cos(math.radians(cfg['draft_angle'])))/max(1-math.cos(math.radians(cfg['draft_angle'])),1e-6)))
            else:
                distances=[];samples=int(cfg['quality']);basis=(-v.normal).to_track_quat('Z','Y')
                for j in range(samples):
                    theta=j*2.39996323;r=.15*math.sqrt(j/max(1,samples-1));direction=basis@Vector((r*math.cos(theta),r*math.sin(theta),math.sqrt(1-r*r)))
                    hit=tree.ray_cast(v.co-v.normal*epsilon,direction)
                    if hit[0] is not None:distances.append(hit[3])
                dist=sum(distances)/len(distances) if distances else cfg['max_thickness']
                t=max(0,min(1,(dist-cfg['min_thickness'])/max(cfg['max_thickness']-cfg['min_thickness'],1e-6)))
            values.append(t)
        result=[tuple(primary[a]*(1-t)+secondary[a]*t for a in range(3))+(1,) for t in values]
    elif kind=='ADJUST':
        amount=cfg['color_adjust'];result=[tuple(max(0,min(1,c+amount)) for c in color[:3])+(1,) for color in colors]
    elif kind=='FILL':
        if cfg['gradient']:
            zs=[v.co.z for v in o.data.vertices];lo=min(zs);span=max(zs)-lo
            result=[tuple(primary[a]*(1-(z-lo)/max(span,1e-8))+secondary[a]*(z-lo)/max(span,1e-8) for a in range(3))+(1,) for z in zs]
        else:result=[(*primary,1)]*len(colors)
    else:raise ValueError(kind)
    result=[tuple(a+(b-a)*(1-m) for a,b in zip(old,new)) for old,new,m in zip(colors,result,weights)]
    attr=write_colors(o,result)
    if o.mode=='SCULPT':bpy.ops.sculpt.optimize()
    option('Polypaint','colorize',True,o)
    return {'ok':True,'attribute':attr.name,'colors':len(result)}


def layer(kind, **kw):
    o=base_target()
    if kind=='NEW':return ops.layer('NEW',name=kw.get('name','Sculpt Layer'))
    keys=o.data.shape_keys.key_blocks if o.data.shape_keys else []
    key=o.active_shape_key
    if kind not in ('IMPORT_MDD','EXPORT_MDD') and (not key or o.active_shape_key_index==0):raise RuntimeError('Select a sculpt layer first')
    with ops.object_mode():
        if kind in ('UP','DOWN'):
            bpy.ops.object.shape_key_move(type='UP' if kind=='UP' else 'DOWN')
        elif kind=='RENAME':key.name=kw.get('name','Sculpt Layer')
        elif kind=='DUPLICATE':
            cp=o.shape_key_add(name=key.name+' Copy',from_mix=False)
            for v,src in zip(cp.data,key.data):v.co=src.co
            cp.value=key.value;o.active_shape_key_index=len(o.data.shape_keys.key_blocks)-1
        elif kind=='DELETE':o.shape_key_remove(key)
        elif kind=='INVERT':
            for v,b in zip(key.data,keys[0].data):v.co=b.co-(v.co-b.co)
        elif kind=='MERGE_DOWN':
            index=o.active_shape_key_index
            if index<2:raise RuntimeError('The first layer has no layer below it; use Bake Current')
            below=keys[index-1];basis=keys[0]
            for a,b,c in zip(below.data,key.data,basis.data):a.co=c.co+(a.co-c.co)*below.value+(b.co-c.co)*key.value
            below.value=1;o.shape_key_remove(key)
        elif kind=='BAKE_ALL':
            ops.recovery(o,'Bake All Layers');coords=[v.co.copy() for v in keys[0].data]
            for k in keys[1:]:
                if k.name=='Sculpt Morph Target' or k.mute:continue
                for i,(v,b) in enumerate(zip(k.data,keys[0].data)):coords[i]+=(v.co-b.co)*k.value
            o.shape_key_clear()
            for v,c in zip(o.data.vertices,coords):v.co=c
            state.get().record_layer=False
        elif kind=='SPLIT':
            # Blender shape layers contain shape only; explicit separation by axis.
            basis=keys[0];original=[v.co.copy() for v in key.data]
            for axis in range(3):
                cp=o.shape_key_add(name=key.name+' '+'XYZ'[axis],from_mix=False);cp.value=key.value
                for v,b,c in zip(cp.data,basis.data,original):v.co=b.co;v.co[axis]=c[axis]
            o.shape_key_remove(key)
        elif kind=='IMPORT_MDD':return import_mdd(kw['path'])
        elif kind=='EXPORT_MDD':return export_mdd(kw['path'])
        else:raise ValueError(kind)
    return {'ok':True,'layer':kind}


def import_mdd(path):
    o=base_target();data=Path(path).read_bytes()
    if len(data)<8:raise RuntimeError('Invalid MDD header')
    frames,points=struct.unpack_from('>2i',data)
    if frames<1 or frames>1000 or points!=len(o.data.vertices):raise RuntimeError('MDD must have 1–1000 samples and the same base vertex count')
    if len(data)!=8+4*frames+12*frames*points:raise RuntimeError('MDD byte count does not match its header')
    times=struct.unpack_from('>'+str(frames)+'f',data,8);offset=8+4*frames;fps=bpy.context.scene.render.fps/bpy.context.scene.render.fps_base
    speed=settings('Layers')['mdd_speed']
    if not o.data.shape_keys:o.shape_key_add(name='Basis')
    for f,time in enumerate(times):
        k=o.shape_key_add(name=f'MDD {f+1:04}',from_mix=False)
        raw=struct.unpack_from('>'+str(points*3)+'f',data,offset+f*points*12)
        for i,v in enumerate(k.data):v.co=raw[i*3:i*3+3]
        frame=1+time*fps/max(speed,.001)
        previous=1+times[f-1]*fps/max(speed,.001) if f else frame-1
        following=1+times[f+1]*fps/max(speed,.001) if f+1<frames else frame+1
        for when,value in ((previous,0),(frame,1),(following,0)):
            k.value=value;k.keyframe_insert(data_path='value',frame=when)
        k.value=0
    from ..advanced.anim_layers import _iter_action_fcurves
    for curve in _iter_action_fcurves(o.data.shape_keys.animation_data.action):
        if 'MDD ' in curve.data_path:
            for point in curve.keyframe_points:point.interpolation='LINEAR'
    return {'ok':True,'frames':frames,'points':points}


def export_mdd(path):
    o=ops.active();scene=bpy.context.scene;old=scene.frame_current;frames=scene.frame_end-scene.frame_start+1
    if not 1<=frames<=1000:raise RuntimeError('Use a scene range of 1–1000 frames')
    samples=[];points=None;fps=scene.render.fps/scene.render.fps_base
    try:
        for frame in range(scene.frame_start,scene.frame_end+1):
            scene.frame_set(frame);evaluated=o.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            try:
                if points is None:
                    points=len(mesh.vertices)
                    if points*frames>10000000:raise RuntimeError('MDD export exceeds 10 million point samples')
                if len(mesh.vertices)!=points:raise RuntimeError('MDD requires fixed point count across the scene range')
                samples.append([c for v in mesh.vertices for c in v.co])
            finally:evaluated.to_mesh_clear()
        if points*frames>10000000:raise RuntimeError('MDD export exceeds 10 million point samples')
        data=struct.pack('>2i',frames,points)+struct.pack('>'+str(frames)+'f',*[i/fps for i in range(frames)])
        for sample in samples:data+=struct.pack('>'+str(len(sample))+'f',*sample)
        Path(path).write_bytes(data)
    finally:scene.frame_set(old)
    return {'ok':True,'path':str(path),'frames':frames,'points':points}


def dispatch(section,kind,**kw):
    functions={'SubTool':subtool,'Geometry':geometry,'Topology':topology,'Masking':mask,'PolyGroups':polygroup,'Deformation':deformation,'Morph Target':morph,'Polypaint':polypaint,'Layers':layer}
    if section in ('ArrayMesh','NanoMesh'):
        from . import instances
        return instances.dispatch(section,kind,**kw)
    return functions[section](kind,**kw)
