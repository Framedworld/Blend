"""One command implementation for sculpt Qt controls, shortcuts and gestures."""
import json
import math
from contextlib import contextmanager
import bpy
import bmesh
from mathutils import Vector
from . import state, brushes

_solo_hidden = {}
_ghost_display = {}
_xpose = {}
last_result = {}


def view_context(context=None):
    ctx = context or bpy.context
    if ctx.area and ctx.area.type == 'VIEW_3D' and ctx.region and ctx.region.type == 'WINDOW':
        return {'window':ctx.window,'area':ctx.area,'region':ctx.region}
    for w in ctx.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return {'window':w,'area':a,'region':next(r for r in a.regions if r.type=='WINDOW')}
    raise RuntimeError('A 3D viewport is required')


def meshes(context=None):
    return sorted([o for o in (context or bpy.context).view_layer.objects if o.type=='MESH' and not o.get('_landfall_recovery') and not o.get('_lf_instance_helper')],key=lambda o:(int(o.get('_lf_subtool_order',100000)),o.name))


def active(context=None):
    o = (context or bpy.context).view_layer.objects.active
    if o is None or o.type != 'MESH':
        raise RuntimeError('Select a mesh SubTool')
    return o


def remember_recording(obj=None):
    o=obj or active();s=state.get()
    o['_landfall_sculpt_record']=s.record_layer
    o['_landfall_sculpt_record_name']=s.record_layer_name


def restore_recording(obj=None):
    """Modeling selection changes do not carry another SubTool's layer state."""
    o=obj or active();s=state.get()
    s.record_layer=bool(o.get('_landfall_sculpt_record',False)) and o.active_shape_key_index>0
    s.record_layer_name=o.get('_landfall_sculpt_record_name','')


@contextmanager
def object_mode():
    obj=bpy.context.view_layer.objects.active
    prev = obj.mode if obj else 'OBJECT'
    if prev=='SCULPT':
        remember_recording(obj)
    if prev != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    try:
        yield
    finally:
        o = bpy.context.view_layer.objects.active
        if o and o.type=='MESH' and prev=='SCULPT':
            bpy.ops.object.mode_set(mode='SCULPT')


def switch_subtool(obj):
    if isinstance(obj,str):
        obj = bpy.data.objects[obj]
    if obj.type!='MESH' or obj.get('_landfall_recovery'):
        raise RuntimeError('SubTool must be an editable scene mesh')
    if obj.library or obj.data.library:
        with object_mode():
            return switch_subtool(surface_copy(obj))
    sculpt = bpy.context.mode=='SCULPT'
    previous=bpy.context.view_layer.objects.active
    if sculpt and previous and previous.type=='MESH':
        remember_recording(previous)
    if bpy.context.object and bpy.context.object.mode!='OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    from .instances import ensure_owners
    ensure_owners(obj)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if sculpt:
        bpy.ops.object.mode_set(mode='SCULPT')
    restore_recording(obj)
    if state.get().solo_active:
        for mesh in meshes():mesh.hide_set(mesh!=obj)
    if state.get().ghost_transparency_active:
        for mesh in meshes():
            if mesh.name not in _ghost_display:_ghost_display[mesh.name]=(mesh.display_type,tuple(mesh.color))
            mesh.display_type=_ghost_display[mesh.name][0] if mesh==obj else 'WIRE'
    # One selection drives both the Qt SubTool list and existing Maya Outliner.
    from ..viewport import sculpt_hud
    sculpt_hud.flash_name = obj.name
    import time
    sculpt_hud.flash_until = time.monotonic()+0.8
    return {'ok':True,'subtool':obj.name}


def recovery(obj, reason):
    """In-memory recovery data, excluded from rendering and sculpt lists."""
    coll = bpy.data.collections.get('Landfall Sculpt Recovery')
    if coll is None:
        coll = bpy.data.collections.new('Landfall Sculpt Recovery')
        bpy.context.scene.collection.children.link(coll)
    cp = obj.copy()
    cp.data = obj.data.copy()
    cp.name = f'{obj.name} · before {reason}'
    cp['_landfall_recovery'] = True
    cp['_landfall_original_hide_render']=obj.hide_render
    coll.objects.link(cp)
    from .instances import ensure_owners
    ensure_owners(cp)
    cp.hide_render = True
    cp.hide_set(True)
    return cp


def surface_copy(obj):
    dg=bpy.context.evaluated_depsgraph_get()
    data=bpy.data.meshes.new_from_object(obj.evaluated_get(dg),depsgraph=dg)
    copy=bpy.data.objects.new(obj.name+' · Sculpt Copy',data)
    bpy.context.collection.objects.link(copy)
    copy.parent=obj.parent;copy.matrix_world=obj.matrix_world
    obj.hide_set(True)
    return copy


def topology_target(reason):
    o = active()
    if o.data.shape_keys or o.vertex_groups or o.library or o.data.library or any(m.type=='ARMATURE' or (m.type=='MULTIRES' and m.total_levels) for m in o.modifiers):
        # Stage a standalone surface rather than deleting the artist's rig/keys.
        with object_mode():
            cp=surface_copy(o)
            switch_subtool(cp)
        o = cp
    recovery(o,reason)
    return o


def mask_values(obj=None):
    o = obj or active()
    a = o.data.attributes.get('.sculpt_mask')
    return [d.value for d in a.data] if a else [0.0]*len(o.data.vertices)


def set_mask(values, obj=None):
    o = obj or active()
    a = o.data.attributes.get('.sculpt_mask') or o.data.attributes.new('.sculpt_mask','FLOAT','POINT')
    a.data.foreach_set('value', values)
    o.data.update()


def multires(create=False):
    o = active()
    m = next((m for m in o.modifiers if m.type=='MULTIRES'),None)
    if m is None and create:
        # Preserve existing Maya smooth-preview settings; hide that duplicate
        # subdivision while the real multires surface is active.
        for sub in o.modifiers:
            if sub.type=='SUBSURF':
                saved=dict(o.get('_landfall_sculpt_preview_modifiers',{}))
                saved[sub.name]=sub.show_viewport
                o['_landfall_sculpt_preview_modifiers']=saved
                sub.show_viewport = False
        m = o.modifiers.new('Landfall Sculpt Levels','MULTIRES')
    return m


def point_count(obj,highest=False):
    """Exact Catmull-Clark topology count without evaluating sculpt grids."""
    m=next((m for m in obj.modifiers if m.type=='MULTIRES' and m.show_viewport),None)
    if m is None:return len(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices)
    levels=m.total_levels if highest else (m.sculpt_levels if obj.mode=='SCULPT' else m.levels)
    vertices,edges,faces,loops=len(obj.data.vertices),len(obj.data.edges),len(obj.data.polygons),len(obj.data.loops)
    for _ in range(levels):vertices,edges,faces,loops=vertices+edges+faces,2*edges+loops,loops,4*loops
    return vertices


def divide():
    o = active()
    # Multires retains base topology/shape keys; no destructive key removal.
    recovery(o,'Divide')
    with object_mode():
        m = multires(True)
        if m.total_levels >= 6 or len(o.data.polygons)*4**(m.total_levels+1)>4000000:
            raise RuntimeError('Subdivision limit reached (4 million faces)')
        from .extended import settings
        cfg=settings('Geometry')
        m.uv_smooth='PRESERVE_BOUNDARIES' if cfg['smooth_uv'] else 'NONE'
        bpy.ops.object.multires_subdivide(modifier=m.name,mode='CATMULL_CLARK' if cfg['smooth'] else 'SIMPLE')
        m.levels = m.sculpt_levels = m.total_levels
        m.render_levels = m.total_levels
    stop_grid_layer_recording()
    return {'ok':True,'level':m.sculpt_levels,'total':m.total_levels}


def resolution(delta):
    m = multires()
    if m is None:
        raise RuntimeError('Divide the SubTool first')
    m.sculpt_levels = max(0,min(m.total_levels,m.sculpt_levels+delta))
    m.levels = m.sculpt_levels
    stop_grid_layer_recording()
    return {'ok':True,'level':m.sculpt_levels}


def stop_grid_layer_recording():
    """Shape keys have base vertices; Multires grid detail is shared data."""
    o=active();m=multires();s=state.get()
    if m and m.sculpt_levels>0 and s.record_layer:
        if o.mode=='SCULPT':
            # Rebuild the session when moving from a key's base buffer to the
            # shared Multires grids, as for explicit layer selection.
            with object_mode():return stop_grid_layer_recording()
        s.record_layer_name=o.active_shape_key.name if o.active_shape_key else ''
        s.record_layer=False;o.active_shape_key_index=0;o.show_only_shape_key=False
        o['_landfall_sculpt_record']=False
        o['_landfall_sculpt_record_name']=s.record_layer_name


def shape_editor_return_key(obj=None):
    """Keep the base layer target while shared Multires detail uses Basis."""
    o=obj or active()
    keys=o.data.shape_keys.key_blocks if o.data.shape_keys else None
    if not keys:return None
    if o.active_shape_key_index>0:return o.active_shape_key
    name=o.get('_landfall_sculpt_record_name','')
    key=keys.get(name)
    return key if key and key!=o.data.shape_keys.reference_key else None


def delete_lower_levels():
    """New base at current SDiv; reshape the retained upper surface onto it.

    Blender exposes no delete-lower RNA operator. Stage this reconstruction on
    a new object and compare the final surface before hiding the original.
    """
    source=active(); old=multires()
    if old is None or old.sculpt_levels==0:
        raise RuntimeError('The current subdivision has no lower levels')
    current,total=old.sculpt_levels,old.total_levels
    saved=(old.levels,old.sculpt_levels)
    target=high_obj=None
    with object_mode():
        try:
            dg=bpy.context.evaluated_depsgraph_get()
            old.levels=old.sculpt_levels=current; bpy.context.view_layer.update()
            base=bpy.data.meshes.new_from_object(source.evaluated_get(dg),depsgraph=dg)
            old.levels=old.sculpt_levels=total; bpy.context.view_layer.update()
            high=bpy.data.meshes.new_from_object(source.evaluated_get(dg),depsgraph=dg)
        finally:
            old.levels,old.sculpt_levels=saved
            bpy.context.view_layer.update()
        target=bpy.data.objects.new(source.name+' · New Base',base)
        bpy.context.collection.objects.link(target); target.matrix_world=source.matrix_world
        bpy.ops.object.select_all(action='DESELECT'); target.select_set(True); bpy.context.view_layer.objects.active=target
        try:
            if total>current:
                mod=target.modifiers.new('Landfall Sculpt Levels','MULTIRES')
                for _ in range(total-current):bpy.ops.object.multires_subdivide(modifier=mod.name)
                mod.levels=mod.sculpt_levels=mod.render_levels=mod.total_levels
                high_obj=bpy.data.objects.new('Landfall temporary reshape source',high)
                bpy.context.collection.objects.link(high_obj); high_obj.matrix_world=source.matrix_world; high_obj.select_set(True)
                result=bpy.ops.object.multires_reshape(modifier=mod.name)
                if 'FINISHED' not in result:raise RuntimeError('Cannot preserve the upper sculpt surface')
                bpy.context.view_layer.update()
                dg=bpy.context.evaluated_depsgraph_get(); evaluated=target.evaluated_get(dg).to_mesh()
                try:
                    if len(evaluated.vertices)!=len(high.vertices):raise RuntimeError('Upper surface vertex count changed')
                    error=max(((a.co-b.co).length for a,b in zip(evaluated.vertices,high.vertices)),default=0)
                    if error>max(source.dimensions)*1e-5:raise RuntimeError('Upper surface validation failed; original preserved')
                finally:target.evaluated_get(dg).to_mesh_clear()
                mod.levels=mod.sculpt_levels=0
            source.hide_set(True)
            switch_subtool(target)
        except Exception:
            bpy.data.objects.remove(target,do_unlink=True)
            bpy.context.view_layer.objects.active=source; source.select_set(True)
            raise
        finally:
            if high_obj:bpy.data.objects.remove(high_obj,do_unlink=True)
            if high.users==0:bpy.data.meshes.remove(high)
    return {'ok':True,'base_level':current,'retained_upper_levels':total-current,'subtool':target.name}


def remesh(quad=False):
    o = topology_target('ZRemesher' if quad else 'DynaMesh')
    s = state.get()
    if multires():
        # Bake a copy of the currently evaluated surface before remeshing it.
        with object_mode():
            dg = bpy.context.evaluated_depsgraph_get()
            data = bpy.data.meshes.new_from_object(o.evaluated_get(dg),depsgraph=dg)
            o.modifiers.clear()
            o.data = data
    with object_mode():
        if quad:
            bpy.ops.object.quadriflow_remesh(target_faces=s.zremesher_target_polys,
                use_preserve_sharp=s.keep_groups,use_preserve_boundary=s.keep_groups,
                preserve_attributes=s.keep_groups,smooth_normals=s.adaptive,seed=0)
        else:
            extent=max((max(v.co[i] for v in o.data.vertices)-min(v.co[i] for v in o.data.vertices) for i in range(3)),default=0)
            if extent<=1e-8:raise RuntimeError('The sculpt surface has no volume')
            o.data.remesh_voxel_size = extent/s.dynamesh_resolution
            o.data.use_remesh_preserve_volume = True
            bpy.ops.object.voxel_remesh()
    return {'ok':True,'vertices':len(o.data.vertices),'faces':len(o.data.polygons)}


def append(primitive='SPHERE',join=False):
    src = active()
    if join and (src.data.shape_keys or src.vertex_groups):
        raise RuntimeError('Insert Mesh requires a surface without shape keys or skin data; use Append')
    with object_mode():
        bpy.ops.object.select_all(action='DESELECT')
        if primitive=='CUBE':
            bpy.ops.mesh.primitive_cube_add(size=0.5,location=bpy.context.scene.cursor.location)
        elif primitive=='CYLINDER':
            bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=0.25,depth=0.5,location=bpy.context.scene.cursor.location)
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=0.25,location=bpy.context.scene.cursor.location)
        new = active()
        new.name = 'SubTool · '+primitive.title()
        for p in new.data.polygons:
            p.use_smooth=True
        if join:
            recovery(src,'Insert Mesh')
            src.select_set(True)
            bpy.context.view_layer.objects.active=src
            bpy.ops.object.join()
    return {'ok':True,'subtool':active().name}


IMM_PRIMITIVES=('SPHERE','CUBE','CYLINDER')
IMM_COLLECTION='IMM Parts'


def imm_parts():
    """Insertable parts: primitives, then meshes in the IMM Parts collection."""
    parts=list(IMM_PRIMITIVES)
    coll=bpy.data.collections.get(IMM_COLLECTION)
    if coll:parts+=[o.name for o in coll.objects if o.type=='MESH']
    return parts


def imm_add_part(obj=None):
    """Keep a copy of a mesh as an IMM part (ZBrush: create an InsertMesh brush)."""
    obj=obj or active()
    coll=bpy.data.collections.get(IMM_COLLECTION)
    if coll is None:
        coll=bpy.data.collections.new(IMM_COLLECTION)
        bpy.context.scene.collection.children.link(coll)
    coll.hide_viewport=coll.hide_render=True
    part=bpy.data.objects.new('IMM '+obj.name,obj.data.copy())
    part['_landfall_imm_part']=True
    coll.objects.link(part)
    state.get().imm_part=part.name
    return {'ok':True,'part':part.name}


def _imm_mesh(part):
    import bmesh
    if part in IMM_PRIMITIVES:
        bm=bmesh.new()
        if part=='CUBE':bmesh.ops.create_cube(bm,size=1.0)
        elif part=='CYLINDER':bmesh.ops.create_cone(bm,cap_ends=True,segments=32,radius1=.5,radius2=.5,depth=1.0)
        else:bmesh.ops.create_uvsphere(bm,u_segments=32,v_segments=16,radius=.5)
        mesh=bpy.data.meshes.new('IMM '+part.title());bm.to_mesh(mesh);bm.free()
        for p in mesh.polygons:p.use_smooth=True
        return mesh,part.title()
    source=bpy.data.objects.get(part)
    if source is None or source.type!='MESH':
        raise RuntimeError(f'IMM part "{part}" is no longer available; choose another part')
    return source.data.copy(),part.removeprefix('IMM ')


def _imm_join_blocker(src):
    """Why the part cannot join the sculpted SubTool, or '' when it can."""
    m=multires()
    if m and m.total_levels>0:
        return 'the SubTool has subdivision levels'
    if src.data.shape_keys is not None:
        return 'the SubTool has layers'
    if getattr(src,'use_dynamic_topology_sculpting',False):
        return 'Sculptris Pro is on'
    if src.data.users>1 or src.library or src.data.library:
        return 'the SubTool shares or links its mesh'
    return ''


def _imm_join(src,part):
    """Join `part` into `src`, mask the existing surface, give the part a group."""
    import bmesh
    from mathutils import Matrix
    old_count=len(src.data.vertices)
    faces=src.data.attributes.get('.sculpt_face_set')
    next_group=(max((d.value for d in faces.data),default=0)+1) if faces else 2
    with object_mode():
        bm=bmesh.new();bm.from_mesh(src.data)
        local=src.matrix_world.inverted()@part.matrix_world
        piece=part.data.copy();piece.transform(local)
        bm.from_mesh(piece);bm.to_mesh(src.data);bm.free()
        bpy.data.meshes.remove(piece)
        mesh=src.data
        mask=mesh.attributes.get('.sculpt_mask') or mesh.attributes.new('.sculpt_mask','FLOAT','POINT')
        values=[1.0]*old_count+[0.0]*(len(mesh.vertices)-old_count)
        mask.data.foreach_set('value',values)
        sets=mesh.attributes.get('.sculpt_face_set') or mesh.attributes.new('.sculpt_face_set','INT','FACE')
        if not faces:
            sets.data.foreach_set('value',[1]*len(mesh.polygons))
        for poly in mesh.polygons:
            if all(v>=old_count for v in poly.vertices):sets.data[poly.index].value=next_group
        mesh.update()
    return len(src.data.vertices)-old_count


def imm_insert(location,normal,size,part=None):
    """Insert a part on the surface as a new SubTool (ZBrush InsertMesh).

    The part's +Z follows the surface normal, its largest extent becomes
    `size`, and it is centred on the hit. The sculpted SubTool stays active.
    """
    from mathutils import Matrix,Vector
    src=active();part=part or state.get().imm_part
    mesh,label=_imm_mesh(part)
    extent=max(max(v.co[a] for v in mesh.vertices)-min(v.co[a] for v in mesh.vertices) for a in range(3)) if mesh.vertices else 1.0
    factor=max(float(size),1e-4)/max(extent,1e-6)
    normal=Vector(normal);normal=normal.normalized() if normal.length>1e-9 else Vector((0,0,1))
    rotation=normal.to_track_quat('Z','Y').to_matrix().to_4x4()
    obj=bpy.data.objects.new('SubTool · IMM '+label,mesh)
    for coll in src.users_collection or (bpy.context.collection,):
        coll.objects.link(obj);break
    obj.matrix_world=Matrix.Translation(Vector(location))@rotation@Matrix.Diagonal((factor,factor,factor,1))
    if state.get().imm_into_subtool:
        blocker=_imm_join_blocker(src)
        if not blocker:
            mesh_data=obj.data
            added=_imm_join(src,obj)
            bpy.data.objects.remove(obj);bpy.data.meshes.remove(mesh_data)
            return {'ok':True,'joined_into':src.name,'part':part,'size':float(size),'part_vertices':added}
        return {'ok':True,'subtool':obj.name,'part':part,'size':float(size),
                'note':f'Inserted as a new SubTool because {blocker}.'}
    return {'ok':True,'subtool':obj.name,'part':part,'size':float(size)}


def extract(split=False):
    src = active()
    if split:
        src=topology_target('Split Masked')
        result=bpy.ops.sculpt.paint_mask_slice(mask_threshold=.5,fill_holes=True,new_object=True)
    else:
        # Native 5.2 extraction evaluates the current sculpt surface and mask,
        # including Multires grids and active shape keys, rather than slicing
        # only the undeformed base mesh by polygon averages.
        result=bpy.ops.sculpt.paint_mask_extract(mask_threshold=.5,add_boundary_loop=False,
            smooth_iterations=0,apply_shrinkwrap=False,add_solidify=True)
    cp=active()
    if 'FINISHED' not in result or cp==src:
        raise RuntimeError('Mask an area before extracting')
    cp.name=src.name+(' · Split' if split else ' · Extract')
    if not split:
        mod=next((m for m in cp.modifiers if m.type=='SOLIDIFY'),None)
        if mod:mod.thickness=state.get().extract_thickness;mod.offset=0
    if bpy.context.mode!='SCULPT':bpy.ops.object.mode_set(mode='SCULPT')
    return {'ok':True,'subtool':cp.name,'faces':len(cp.data.polygons)}


def merge(visible=False):
    src=active()
    choices=[o for o in meshes() if o.visible_get() and o!=src]
    if not choices: raise RuntimeError('No other visible SubTool to merge')
    chosen=choices if visible else choices[:1]
    # Merge into a new evaluated surface; all originals stay in the scene.
    with object_mode():
        bpy.ops.object.select_all(action='DESELECT')
        copies=[]
        dg=bpy.context.evaluated_depsgraph_get()
        for o in [src]+chosen:
            data=bpy.data.meshes.new_from_object(o.evaluated_get(dg),depsgraph=dg)
            cp=bpy.data.objects.new(o.name+' · Merge',data)
            bpy.context.collection.objects.link(cp)
            cp.matrix_world=o.matrix_world; cp.select_set(True); copies.append(cp)
            o.hide_set(True)
        bpy.context.view_layer.objects.active=copies[0]
        bpy.ops.object.join()
        active().name=src.name+' · Merged'
    return {'ok':True,'subtool':active().name}


def toggle_solo():
    global _solo_hidden
    s=state.get()
    if not s.solo_active:
        o=active()
        _solo_hidden={x.name:x.hide_get() for x in meshes()}
        for x in meshes():
            if x!=o: x.hide_set(True)
    else:
        for name,hidden in _solo_hidden.items():
            if name in bpy.data.objects: bpy.data.objects[name].hide_set(hidden)
        _solo_hidden={}
    s.solo_active=not s.solo_active
    return {'ok':True,'solo':s.solo_active}


def ghost():
    global _ghost_display
    s=state.get()
    if not s.ghost_transparency_active:
        o=active()
        for x in meshes():
            _ghost_display[x.name]=(x.display_type,tuple(x.color))
            if x!=o:
                x.display_type='WIRE'
    else:
        for n,(display,color) in _ghost_display.items():
            if n in bpy.data.objects:
                bpy.data.objects[n].display_type=display
                bpy.data.objects[n].color=color
        _ghost_display={}
    s.ghost_transparency_active=not s.ghost_transparency_active
    return {'ok':True,'ghost':s.ghost_transparency_active}


def xpose():
    global _xpose
    if _xpose:
        for n,loc in _xpose.items():
            if n in bpy.data.objects: bpy.data.objects[n].location=loc
        _xpose={}
    else:
        visible=[o for o in meshes() if o.visible_get()]
        if not visible: return {'ok':True}
        center=sum((o.matrix_world.translation for o in visible),Vector())/len(visible)
        for i,o in enumerate(visible):
            _xpose[o.name]=o.location.copy()
            direction=o.matrix_world.translation-center
            if direction.length<0.001: direction=Vector((math.cos(i*2.4),math.sin(i*2.4),0))
            o.location+=direction.normalized()*max(o.dimensions)*0.5
    return {'ok':True,'xpose':bool(_xpose)}


def groups(mode):
    o=active()
    if mode in ('MASKED','VISIBLE'):
        bpy.ops.sculpt.face_sets_create(mode=mode)
    elif mode=='CLEAR':
        a=o.data.attributes.get('.sculpt_face_set')
        if a: o.data.attributes.remove(a)
    else:
        a=o.data.attributes.get('.sculpt_face_set') or o.data.attributes.new('.sculpt_face_set','INT','FACE')
        if mode=='NORMALS':
            values=[1+max(range(3),key=lambda i:abs(p.normal[i]))*2+int(sum(p.normal)<0) for p in o.data.polygons]
        else:
            # Connected face islands, not collection names or vertex ordering.
            verts={v.index:[] for v in o.data.vertices}
            for p in o.data.polygons:
                for v in p.vertices: verts[v].append(p.index)
            unseen=set(range(len(o.data.polygons))); values=[0]*len(unseen); group=0
            while unseen:
                group+=1; todo=[unseen.pop()]
                while todo:
                    i=todo.pop(); values[i]=group
                    for v in o.data.polygons[i].vertices:
                        for j in verts[v]:
                            if j in unseen: unseen.remove(j); todo.append(j)
        a.data.foreach_set('value',values)
        o.data.update()
    return {'ok':True}


def deform(kind):
    o=active(); amount=state.get().deformation_amount
    if multires() and multires().sculpt_levels:
        if kind=='UNIFY':raise RuntimeError('Lower to base resolution before Unify Scale')
        types={'INFLATE':'INFLATE','POLISH':'SURFACE_SMOOTH','CRISP':'SHARPEN','SMOOTH':'SMOOTH','RELAX':'RELAX','CONTRAST':'ENHANCE_DETAILS'}
        result=bpy.ops.sculpt.mesh_filter(type=types[kind],strength=amount,iteration_count=1,deform_axis={'X','Y','Z'})
        if 'FINISHED' not in result:raise RuntimeError('Native sculpt filter could not run')
        return {'ok':True,'filter':types[kind],'points':point_count(o)}
    key=o.active_shape_key if o.data.shape_keys and o.active_shape_key_index>0 else None
    coords=[v.co.copy() for v in (key.data if key else o.data.vertices)]
    weights=mask_values(o)
    if kind=='UNIFY':
        extent=max(max(v[i] for v in coords)-min(v[i] for v in coords) for i in range(3))
        center=sum(coords,Vector())/max(1,len(coords))
        out=[(v-center)*2/max(extent,1e-8) for v in coords]
    elif kind=='INFLATE':
        out=[co+v.normal*amount*(1-weights[v.index]) for co,v in zip(coords,o.data.vertices)]
    else:
        adjacent=[set() for _ in coords]
        for e in o.data.edges:
            a,b=e.vertices; adjacent[a].add(b); adjacent[b].add(a)
        out=[]
        for i,co in enumerate(coords):
            avg=sum((coords[j] for j in adjacent[i]),Vector())/max(1,len(adjacent[i]))
            delta=(avg-co)*min(abs(amount),1)*(1-weights[i])
            if kind in ('POLISH','CRISP'):
                n=o.data.vertices[i].normal
                delta=n*delta.dot(n)*(0.4 if kind=='CRISP' else 1)
            if kind=='CONTRAST': delta=-delta
            out.append(co+delta)
    for v,co in zip(key.data if key else o.data.vertices,out): v.co=co
    o.data.update()
    return {'ok':True,'vertices':len(out)}


def layer(action, name='Sculpt Layer', value=None):
    o=active()
    if o.mode=='SCULPT' and action in ('NEW','SELECT','RECORD','BAKE'):
        # Rebuild the native Sculpt session with the chosen shape-key target.
        # Changing only active_shape_key_index leaves an existing session
        # pointing at its previous vertex buffer (notably the launch demo).
        with object_mode():return layer(action,name,value)
    if action in ('NEW','RECORD') and (action=='NEW' or not state.get().record_layer):
        m=multires()
        if m:m.levels=m.sculpt_levels=0
    if action=='NEW':
        if not o.data.shape_keys: o.shape_key_add(name='Basis')
        key=o.shape_key_add(name=name,from_mix=False)
        key.value=1
        o.active_shape_key_index=len(o.data.shape_keys.key_blocks)-1
        state.get().record_layer=True
        state.get().record_layer_name=key.name
    elif action=='SELECT':
        keys=o.data.shape_keys.key_blocks if o.data.shape_keys else []
        idx=next((i for i,k in enumerate(keys) if k.name==name),None)
        if idx is None: raise RuntimeError('Layer no longer exists')
        o.active_shape_key_index=idx
        if state.get().record_layer:state.get().record_layer_name=name
    elif action=='VALUE':
        key=o.data.shape_keys.key_blocks[name]
        key.slider_min=min(key.slider_min,float(value));key.slider_max=max(key.slider_max,float(value))
        key.value=value
    elif action=='RECORD':
        s=state.get()
        if s.record_layer:
            s.record_layer_name=o.active_shape_key.name if o.active_shape_key else ''
            s.record_layer=False; o.active_shape_key_index=0
            o.show_only_shape_key=False
        else:
            keys=o.data.shape_keys.key_blocks if o.data.shape_keys else []
            if not o.active_shape_key_index and s.record_layer_name not in keys:return layer('NEW')
            if not o.active_shape_key_index:layer('SELECT',name=s.record_layer_name)
            s.record_layer=True
            s.record_layer_name=o.active_shape_key.name
            o.show_only_shape_key=True
    elif action=='BAKE':
        if not o.data.shape_keys or o.active_shape_key_index==0:
            raise RuntimeError('Select a sculpt layer to bake')
        recovery(o,'Bake Layer')
        key=o.active_shape_key; basis=o.data.shape_keys.reference_key
        delta=[(v.co-b.co)*key.value for v,b in zip(key.data,basis.data)]
        for k in o.data.shape_keys.key_blocks:
            if k==key: continue
            for v,d in zip(k.data,delta): v.co+=d
        o.shape_key_remove(key)
        if o.active_shape_key_index==0:
            state.get().record_layer=False;state.get().record_layer_name=''
    elif action=='GOZ':
        if shape_editor_return_key(o) is None:raise RuntimeError('Select a sculpt layer to open in the Shape Editor')
        from . import return_to_maya
        result=return_to_maya(shape_editor=True)
        return result
    remember_recording(o)
    return {'ok':True,'layer':o.active_shape_key.name if o.active_shape_key else None}


MATCAPS={'Red Wax':('red_wax.exr',(0.65,0.12,0.08)),
         'Grey Clay':('basic_grey.exr',(0.48,0.49,0.52)),
         'Chavant':('clay_green.exr',(0.36,0.30,0.16)),
         'Skin Shade':('clay_warm.exr',(0.65,0.43,0.32)),
         'Pearl Cavity':('pearl.exr',(0.65,0.67,0.72)),
         'Flat Silhouette':('',(0.85,0.85,0.85))}


def matcap(name):
    sh=bpy.context.space_data.shading
    desired,color=MATCAPS[name]
    sh.type='SOLID'; sh.color_type='SINGLE'; sh.single_color=color
    available=[x.name for x in bpy.context.preferences.studio_lights if x.type=='MATCAP']
    if desired:
        if desired not in available:
            desired=next((a for a in available if name.split()[0].lower() in a.lower()),available[0])
        sh.light='MATCAP'; sh.studiolight_rotate_z=0; sh.studio_light=desired
        sh.show_cavity=name=='Pearl Cavity'
    else:
        sh.light='FLAT'; sh.show_shadows=False; sh.show_cavity=False
    state.get().active_matcap=name
    return {'ok':True,'matcap':name,'native':sh.studio_light}


def dispatch(command_id, **kw):
    if command_id=='PALETTE':
        from .extended import dispatch as dispatch_palette
        return dispatch_palette(**kw)
    if command_id=='PALETTE_OPTION':
        from .extended import option
        return option(**kw)
    action=command_id
    s=state.get()
    if action=='BRUSH': return brushes.select(kw['name'])
    if action=='RESET_BRUSH':return brushes.reset()
    if action=='FOCUS_UI':
        from . import layout
        return layout.toggle_focus()
    if action=='TRAY_AUTO':
        from . import layout
        return layout.auto_tray()
    if action=='STROKE': return brushes.set_stroke(**kw)
    if action=='SUBTOOL': return switch_subtool(kw['name'])
    if action=='DIVIDE': return divide()
    if action=='LOWER': return resolution(-1)
    if action=='HIGHER': return resolution(1)
    if action in ('DELETE_HIGHER','DELETE_LOWER'):
        if action=='DELETE_LOWER':return delete_lower_levels()
        m=multires()
        if not m: raise RuntimeError('No subdivision levels')
        recovery(active(),action)
        with object_mode():
            bpy.ops.object.multires_higher_levels_delete(modifier=m.name)
        return {'ok':True}
    if action=='DYNAMESH':
        s.dynamesh_enabled=True
        return remesh()
    if action=='ZREMESHER': return remesh(True)
    if action in ('APPEND','INSERT'): return append(kw.get('primitive','SPHERE'),action=='INSERT')
    if action=='IMM_INSERT': return imm_insert(kw['location'],kw['normal'],kw['size'],kw.get('part'))
    if action=='IMM_TARGET':
        s.imm_into_subtool=bool(kw.get('into_subtool'));return {'ok':True,'into_subtool':s.imm_into_subtool}
    if action=='IMM_PART':
        if kw.get('part')=='__ACTIVE__':return imm_add_part()
        s.imm_part=kw['part'];return {'ok':True,'part':s.imm_part}
    if action=='EXTRACT': return extract()
    if action=='SPLIT_MASKED': return extract(True)
    if action=='DUPLICATE':
        o=active(); cp=o.copy(); cp.data=o.data.copy(); bpy.context.collection.objects.link(cp)
        cp['_landfall_sculpt_record']=s.record_layer
        cp['_landfall_sculpt_record_name']=s.record_layer_name
        return switch_subtool(cp)
    if action=='RESTORE':
        source=bpy.data.objects.get(kw['name'])
        if source is None or not source.get('_landfall_recovery'):raise RuntimeError('Recovery snapshot no longer exists')
        cp=source.copy();cp.data=source.data.copy();cp.name=source.name.split(' · before ')[0]+' · Recovered'
        del cp['_landfall_recovery']
        cp.hide_render=bool(cp.get('_landfall_original_hide_render',False))
        bpy.context.collection.objects.link(cp)
        return switch_subtool(cp)
    if action=='DELETE':
        o=active(); recovery(o,'Delete'); choices=[x for x in meshes() if x!=o and (x.visible_get() or s.solo_active)]
        with object_mode():
            bpy.data.objects.remove(o,do_unlink=True)
            if choices: switch_subtool(choices[0])
        return {'ok':True}
    if action in ('MERGE_DOWN','MERGE_VISIBLE'): return merge(action=='MERGE_VISIBLE')
    if action=='SOLO': return toggle_solo()
    if action=='GHOST': return ghost()
    if action=='XPOSE': return xpose()
    if action=='GROUP': return groups(kw['mode'])
    if action=='DEFORM': return deform(kw['kind'])
    if action=='LAYER': return layer(**kw)
    if action=='MATCAP': return matcap(kw['name'])
    if action=='PAINT_MATERIAL':
        o=active();name=kw.get('name')
        material=bpy.data.materials.get(name) if name else None
        if material is None:
            material=bpy.data.materials.new('Sculpt Paint Material')
            material.diffuse_color=(*state.brush().color,1)
            material.use_nodes=True
            material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=material.diffuse_color
        index=next((i for i,m in enumerate(o.data.materials) if m==material),None)
        if index is None:o.data.materials.append(material);index=len(o.data.materials)-1
        o.active_material_index=index
        return {'ok':True,'material':material.name}
    if action=='MASK':
        kind=kw['kind']
        if kind in ('ALL','CLEAR','INVERT'):
            bpy.ops.paint.mask_flood_fill(mode='INVERT' if kind=='INVERT' else 'VALUE',value=1 if kind=='ALL' else 0)
        else: bpy.ops.sculpt.mask_filter(filter_type=kind,iterations=1,auto_iteration_count=False)
        return {'ok':True}
    if action=='VISIBILITY':
        kind=kw['kind']
        if kind=='INVERT': bpy.ops.paint.visibility_invert()
        elif kind=='SHOW': bpy.ops.paint.hide_show_all(action='SHOW')
        elif kind=='HIDE_UNMASKED':
            bpy.ops.paint.mask_flood_fill(mode='INVERT'); bpy.ops.paint.hide_show_masked(action='HIDE'); bpy.ops.paint.mask_flood_fill(mode='INVERT')
        return {'ok':True}
    if action in ('MIRROR','CLOSE_HOLES'):
        o=topology_target(action)
        with object_mode():
            bm=bmesh.new(); bm.from_mesh(o.data)
            if action=='MIRROR':
                axis=kw.get('axis','X')
                bmesh.ops.symmetrize(bm,input=list(bm.verts)+list(bm.edges)+list(bm.faces),direction=axis,dist=0.0001)
            else: bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=0)
            bm.to_mesh(o.data); bm.free()
        return {'ok':True}
    if action=='TOOL':
        tool=kw['tool']; s.navigation_tool='DRAW'
        if tool in ('MOVE','ROTATE','SCALE') and active().active_shape_key_index and not s.record_layer:
            raise RuntimeError('Enable layer REC before transforming a sculpt layer')
        bpy.ops.wm.tool_set_by_id(name={'DRAW':brushes.tool_id(state.brush()),'MOVE':'builtin.move','SCALE':'builtin.scale','ROTATE':'builtin.rotate','SELECT_RECT':'builtin.box_hide'}[tool])
        sp=bpy.context.space_data
        sp.show_gizmo_object_translate=tool=='MOVE'
        sp.show_gizmo_object_rotate=tool=='ROTATE'
        sp.show_gizmo_object_scale=tool=='SCALE'
        from ..keymaps import profiles
        profiles.sync_sculpt_paint_mode()
        return {'ok':True}
    if action=='NAV':
        dispatch('TOOL',tool='DRAW')
        s.navigation_tool=kw['tool']
        return {'ok':True}
    if action=='TOGGLE':
        field=kw['field']; setattr(s,field,not getattr(s,field)); return {'ok':True}
    if action=='SCULPTRIS_PRO': return sculptris_pro(kw.get('enable'))
    if action=='SYMMETRY':
        o=active(); axis=kw.get('axis','X'); p='use_mesh_mirror_'+axis.lower(); setattr(o,p,not getattr(o,p)); return {'ok':True}
    if action=='POLYFRAME':
        s.polyframe_active=not s.polyframe_active
        bpy.context.space_data.overlay.show_sculpt_face_sets=s.polyframe_active
        active().show_wire=s.polyframe_active; active().show_all_edges=s.polyframe_active
        return {'ok':True}
    if action=='PERSP': bpy.ops.view3d.view_persportho(); return {'ok':True}
    if action=='FLOOR':
        scene=bpy.context.scene; ov=bpy.context.space_data.overlay
        if hasattr(scene,'landfall_grid_finite'):
            visible=scene.landfall_grid_finite or ov.show_floor
            scene.landfall_grid_finite=not visible
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type=='VIEW_3D':
                        for field in ('show_floor','show_ortho_grid','show_axis_x','show_axis_y','show_axis_z'):setattr(area.spaces.active.overlay,field,False)
        else:
            visible=ov.show_floor or ov.show_ortho_grid
            ov.show_floor=ov.show_ortho_grid=not visible
        return {'ok':True}
    if action=='LOCAL': bpy.ops.view3d.localview(); return {'ok':True}
    if action=='LOCAL_SYM':
        o=active();fields=['use_mesh_mirror_'+axis for axis in 'xyz']
        axes=[getattr(o,field) for field in fields]
        if any(axes):
            o['_landfall_sculpt_symmetry_axes']=axes
            for field in fields:setattr(o,field,False)
        else:
            saved=o.get('_landfall_sculpt_symmetry_axes',(True,False,False))
            for field,value in zip(fields,saved):setattr(o,field,bool(value))
        return {'ok':True}
    if action=='FRAME': bpy.ops.view3d.view_selected(); return {'ok':True}
    if action=='TRANSP':
        sh=bpy.context.space_data.shading; sh.show_xray=not sh.show_xray; sh.xray_alpha=0.35; return {'ok':True}
    if action=='RETURN':
        from . import return_to_maya
        return return_to_maya()
    raise ValueError('Unknown sculpt action: '+action)


def sculptris_pro(enable=None):
    """ZBrush Sculptris Pro on Blender's dynamic topology.

    Detail follows the brush size (Blender's Brush detail), as Sculptris Pro's
    adaptive mode does. Like ZBrush, it refuses a mesh with subdivision levels
    or layers, which dynamic tessellation would discard.
    """
    o=active()
    on=bool(o.use_dynamic_topology_sculpting)
    wanted=(not on) if enable is None else bool(enable)
    if wanted==on: return {'ok':True,'sculptris_pro':on}
    if wanted:
        if multires():
            raise RuntimeError('Sculptris Pro needs a mesh without subdivision levels. '
                               'Use Del Lower / Del Higher, or DynaMesh, first.')
        if o.data.shape_keys is not None:
            raise RuntimeError('Sculptris Pro cannot run on a mesh with Layers. Bake or delete the layers first.')
        sculpt=bpy.context.scene.tool_settings.sculpt
        sculpt.detail_type_method='BRUSH'
        sculpt.detail_percent=state.get().sculptris_detail
    bpy.ops.sculpt.dynamic_topology_toggle()
    return {'ok':True,'sculptris_pro':bool(o.use_dynamic_topology_sculpting)}


class LANDFALL_STUDIO_OT_sculpt_command(bpy.types.Operator):
    bl_idname='landfall_studio.sculpt_command'
    bl_label='Sculpt Studio Command'
    bl_options={'REGISTER','UNDO'}
    action:bpy.props.StringProperty()
    arguments:bpy.props.StringProperty(default='{}')

    def execute(self,context):
        global last_result
        try:
            last_result=dispatch(self.action,**json.loads(self.arguments))
            return {'FINISHED'}
        except Exception as exc:
            last_result={'ok':False,'error':str(exc),'action':self.action}
            self.report({'WARNING'},str(exc))
            return {'CANCELLED'}


def _global_undo_push(message,anchor=None):
    """Push a global (memfile) Undo step while Sculpt mode is active.

    Undo picks its step type from the context object: with an Object-mode
    object, or none at all, Blender records a global step instead of a Sculpt one.
    """
    with bpy.context.temp_override(active_object=anchor,object=anchor,
                                   selected_objects=[anchor] if anchor else []):
        bpy.ops.ed.undo_push(message=message)


def run(command_id, **kw):
    # Qt slots call bpy operators from Python, whose default undo argument is
    # False. Explicitly record data commands through this existing undo owner.
    state_only={'BRUSH','RESET_BRUSH','STROKE','SUBTOOL','MATCAP','TOOL','NAV','TOGGLE','SYMMETRY','POLYFRAME','PERSP','FLOOR','LOCAL','LOCAL_SYM','FRAME','TRANSP','RETURN','FOCUS_UI','TRAY_AUTO','SOLO','GHOST','XPOSE'}
    undoable=command_id not in state_only
    if command_id=='LAYER' and kw.get('action')=='GOZ':
        undoable=False  # return_to_maya owns the single native mode boundary.
    if command_id in ('MASK','GROUP','SCULPTRIS_PRO'):
        undoable=False  # Native Sculpt operators already push their own nodes.
    # In Sculpt mode every Undo step is a Sculpt step, which stores mesh edits
    # but not new objects; and Blender 5.2 does not reload global state when
    # stepping from a global step back to a Sculpt one. So an insert is
    # bracketed by two global steps: a checkpoint of the current work, then the
    # insert. One Undo reloads the checkpoint (part gone, strokes kept).
    adds_object=command_id=='IMM_INSERT' and bpy.context.mode=='SCULPT'
    if adds_object:undoable=False
    with bpy.context.temp_override(**view_context()):
        instance_edit=command_id in ('PALETTE','PALETTE_OPTION') and kw.get('section') in ('ArrayMesh','NanoMesh') and kw.get('kind') not in ('EDIT_MESH','RETURN_PLACEMENT','EDIT_PLACEMENT','SPLIT_SCREEN','COPY','SAVE')
        if instance_edit and bpy.context.mode=='SCULPT':
            # Blender 5.2 does not restore modifier IDs when stepping directly
            # from a global entry to an earlier Sculpt node. Capture a native
            # global baseline before the modifier edit. Strokes keep their
            # existing Sculpt history; no parallel undo stack is introduced.
            bpy.ops.ed.undo_push(message='Sculpt modifier baseline')
        if adds_object:_global_undo_push('Before Insert Mesh')
        bpy.ops.landfall_studio.sculpt_command('EXEC_DEFAULT',undoable,action=command_id,arguments=json.dumps(kw))
        if adds_object and last_result.get('ok'):
            # A new part object is in Object mode; a joined part leaves no
            # such object, and no context object also gives a global step.
            part=bpy.data.objects.get(last_result.get('subtool',''))
            _global_undo_push('Insert Mesh',part)
    from ..ui.desktop import set_command_feedback
    set_command_feedback('Sculpt · '+command_id,str(last_result),'INFO' if last_result.get('ok') else 'ERROR')
    return dict(last_result)
