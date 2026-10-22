"""Pen dispatcher scoped to Sculpt. Native strokes retain tablet pressure."""
import math
import time
import bpy
from mathutils import Quaternion, Vector
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d, region_2d_to_location_3d, location_3d_to_region_2d
from . import state, ops

history=[]
cursor={'xy':(-1000,-1000),'ctrl':False,'shift':False,'alt':False,'area':0}
imm_preview=None  # (start_xy, radius_px or None, area pointer) while dragging an IMM part
marquee=None
tracker_generation=0
_pointer_windows={}


def update_cursor(context,event):
    cursor.update(ctrl=event.ctrl,shift=event.shift,alt=event.alt)
    if event.type in ('MOUSEMOVE','INBETWEEN_MOUSEMOVE','LEFTMOUSE'):
        cursor.update(xy=(event.mouse_region_x,event.mouse_region_y),area=context.area.as_pointer())
    elif event.type=='WINDOW_DEACTIVATE':
        cursor.update(xy=(-1000,-1000),area=0)


def _pointer_in_region(context):
    """Read the live pen/mouse position while a native paint modal owns events."""
    import sys
    if sys.platform!='win32':return None
    import ctypes
    from ctypes import wintypes
    from blendertk.ui_utils.blender_window import BlenderWindow
    key=context.window.as_pointer();hwnd=_pointer_windows.get(key)
    if not hwnd or not BlenderWindow.is_window(hwnd):
        hwnd=BlenderWindow.window_hwnd(context.window);_pointer_windows[key]=hwnd
    if not hwnd:return None
    point=wintypes.POINT()
    user=ctypes.windll.user32
    if not user.GetCursorPos(ctypes.byref(point)) or not user.ScreenToClient(ctypes.c_void_p(hwnd),ctypes.byref(point)):return None
    return (point.x-context.region.x,context.window.height-1-point.y-context.region.y)


def cursor_for_draw(context):
    """Native paint blocks the monitor; sample its tip without owning its stroke."""
    result=dict(cursor)
    modals={op.bl_idname for op in context.window.modal_operators}
    native='SCULPT_OT_brush_stroke' in modals
    result['pressed']=native or 'LANDFALL_STUDIO_OT_sculpt_pen' in modals
    if native and cursor['area']==context.area.as_pointer():
        xy=_pointer_in_region(context)
        if xy is not None:result['xy']=xy;cursor['xy']=xy
    return result


def record(action, **kw):
    history.append({'action':action,**kw})
    del history[:-80]


def raycast(context, xy):
    r,rv=context.region,context.region_data
    origin=region_2d_to_origin_3d(r,rv,xy)
    direction=region_2d_to_vector_3d(r,rv,xy)
    hit,loc,normal,index,obj,matrix=context.scene.ray_cast(context.evaluated_depsgraph_get(),origin,direction)
    if not hit or obj.type!='MESH' or obj.get('_landfall_recovery'):
        return {'kind':'BLANK','object':None,'face':-1}
    obj=obj.original
    return {'kind':'ACTIVE' if obj==context.active_object else 'OTHER','object':obj,'face':index,'location':loc,'normal':normal}


def classify(hit, ctrl=False,shift=False,alt=False):
    if ctrl and shift: return 'VISIBILITY'
    if ctrl: return 'MASK'
    if hit=='OTHER' and alt: return 'SUBTOOL'
    if hit=='BLANK': return 'PAN' if alt else 'ORBIT'
    if hit=='ACTIVE': return 'SMOOTH' if shift else ('INVERT' if alt else 'STROKE')
    return 'IGNORE'


def bounds(a,b):
    return dict(xmin=int(min(a[0],b[0])),xmax=int(max(a[0],b[0])),ymin=int(min(a[1],b[1])),ymax=int(max(a[1],b[1])))


def overlaps_mesh(context, a,b):
    """Projected triangle/rectangle intersection, including crossing edges."""
    o=ops.active();evaluated=o.evaluated_get(context.evaluated_depsgraph_get())
    bb=bounds(a,b)
    corners=[location_3d_to_region_2d(context.region,context.region_data,o.matrix_world@Vector(p)) for p in evaluated.bound_box]
    if all(p is not None for p in corners):
        if max(p.x for p in corners)<bb['xmin'] or min(p.x for p in corners)>bb['xmax'] or max(p.y for p in corners)<bb['ymin'] or min(p.y for p in corners)>bb['ymax']:
            return False
    mesh=evaluated.to_mesh()
    try:return _overlap_surface(context,o.matrix_world,mesh,a,b)
    finally:evaluated.to_mesh_clear()


def _overlap_surface(context,matrix,mesh,a,b):
    import numpy as np
    mesh.calc_loop_triangles()
    bb=bounds(a,b); lo=Vector((bb['xmin'],bb['ymin'])); hi=Vector((bb['xmax'],bb['ymax']))
    co=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',co)
    projection=np.asarray(context.region_data.perspective_matrix@matrix,dtype=np.float64)
    clip=co.reshape(-1,3)@projection[:,:3].T+projection[:,3]
    valid=clip[:,3]>1e-8
    coords=np.divide(clip[:,:2],clip[:,3,None],out=np.zeros((len(clip),2)),where=valid[:,None])
    coords=(coords*.5+.5)*np.asarray((context.region.width,context.region.height))
    indices=np.empty(len(mesh.loop_triangles)*3,dtype=np.int32);mesh.loop_triangles.foreach_get('vertices',indices);indices=indices.reshape(-1,3)
    if not len(indices):return False
    tris=coords[indices]
    candidates=valid[indices].all(axis=1)&(tris[:,:,0].max(axis=1)>=lo.x)&(tris[:,:,0].min(axis=1)<=hi.x)&(tris[:,:,1].max(axis=1)>=lo.y)&(tris[:,:,1].min(axis=1)<=hi.y)
    hidden=mesh.attributes.get('.hide_poly')
    if hidden:
        values=np.empty(len(mesh.polygons),dtype=np.bool_);hidden.data.foreach_get('value',values)
        polygons=np.empty(len(mesh.loop_triangles),dtype=np.int32);mesh.loop_triangles.foreach_get('polygon_index',polygons)
        candidates &= ~values[polygons]
    tris=tris[candidates]
    if not len(tris):return False
    if (((tris[:,:,0]>=lo.x)&(tris[:,:,0]<=hi.x)&(tris[:,:,1]>=lo.y)&(tris[:,:,1]<=hi.y))).any():return True
    corners=[lo,Vector((hi.x,lo.y)),hi,Vector((lo.x,hi.y))]
    def inside(p, tri):
        signs=[(tri[(i+1)%3]-tri[i]).cross(p-tri[i]) for i in range(3)]
        return all(x>=0 for x in signs) or all(x<=0 for x in signs)
    def segment(p,q):
        t0,t1=0.,1.; d=q-p
        for i in range(2):
            if abs(d[i])<1e-8:
                if p[i]<lo[i] or p[i]>hi[i]: return False
            else:
                x,y=sorted(((lo[i]-p[i])/d[i],(hi[i]-p[i])/d[i]))
                t0=max(t0,x); t1=min(t1,y)
                if t0>t1: return False
        return True
    for tri in tris:
        ps=[Vector(point) for point in tri]
        if any(inside(p,ps) for p in corners): return True
        if any(segment(ps[i],ps[(i+1)%3]) for i in range(3)): return True
    return False


def finish_mask(context, hit, start,end,alt,drag,path=None):
    if not drag:
        return ops.dispatch('MASK',kind=('SHARPEN' if alt else 'SMOOTH') if hit['kind']=='ACTIVE' else 'INVERT')
    marquee_start,marquee_end=start,end
    if state.get().mask_marquee=='LASSO' and path:
        marquee_start=(min(p[0] for p in path),min(p[1] for p in path))
        marquee_end=(max(p[0] for p in path),max(p[1] for p in path))
    if overlaps_mesh(context,marquee_start,marquee_end):
        if state.get().mask_marquee=='LASSO' and path:
            bpy.ops.paint.mask_lasso_gesture(path=[{'name':'','loc':p,'time':i*0.01} for i,p in enumerate(path)],value=0 if alt else 1,mode='VALUE')
        else:
            bpy.ops.paint.mask_box_gesture(**bounds(start,end),value=0 if alt else 1,mode='VALUE',wait_for_input=False)
    elif alt:
        ops.dispatch('MASK',kind='ALL')
    elif state.get().dynamesh_enabled and max(ops.mask_values(),default=0)<0.001:
        return ops.dispatch('DYNAMESH')
    else:
        ops.dispatch('MASK',kind='CLEAR')
    return {'ok':True}


def finish_visibility(context,hit,start,end,alt,drag):
    if not drag:
        if hit['kind']=='ACTIVE':
            a=ops.active().data.attributes.get('.sculpt_face_set')
            group=a.data[hit['face']].value if a and 0<=hit['face']<len(a.data) else 1
            bpy.ops.sculpt.face_set_change_visibility(mode='SHOW_ACTIVE',active_face_set=group)
        else: ops.dispatch('VISIBILITY',kind='SHOW')
    elif overlaps_mesh(context,start,end):
        bpy.ops.paint.hide_show(**bounds(start,end),action='HIDE',area='Inside' if alt else 'OUTSIDE',wait_for_input=False)
    else: ops.dispatch('VISIBILITY',kind='INVERT')
    return {'ok':True}


def sculpt_poll(cls,context):
    return context.mode=='SCULPT' and context.area and context.area.type=='VIEW_3D' and hasattr(context.scene,'landfall_sculpt') and state.get(context).bbrush_enabled


def material_dab(context,xy,pressure=1,erase=False):
    """Face material paint plus optional per-corner RGB, on existing topology."""
    o=ops.active(context); mesh=o.data; s=state.get(context); b=state.brush(context)
    if not mesh.materials:
        mat=bpy.data.materials.new('Landfall Sculpt Material'); mat.diffuse_color=(*b.color,1)
        mesh.materials.append(mat)
    color_attr=None
    if s.rgb_enabled:
        color_attr=mesh.color_attributes.active_color
        if color_attr is None or color_attr.domain!='CORNER':
            previous=color_attr
            color_attr=mesh.color_attributes.get('Landfall Sculpt Color') or mesh.color_attributes.new('Landfall Sculpt Color','BYTE_COLOR','CORNER')
            for loop in mesh.loops:
                color_attr.data[loop.index].color=previous.data[loop.vertex_index].color if previous and previous.domain=='POINT' else (1,1,1,1)
            mesh.color_attributes.active_color=color_attr
    masks=ops.mask_values(o); changed=False
    radius=b.size; focal=(s.focal_shift+100)/200
    for p in mesh.polygons:
        if p.hide or sum(masks[i] for i in p.vertices)/len(p.vertices)>.5:continue
        point=location_3d_to_region_2d(context.region,context.region_data,o.matrix_world@p.center)
        if point is None: continue
        d=(point-Vector(xy)).length/max(radius,1)
        if d>1:continue
        p.material_index=0 if erase else o.active_material_index
        if color_attr:
            factor=min(1,max(0,(1-d)/max(1-focal,1e-5)))*pressure*s.z_intensity/100
            for i in p.loop_indices:
                old=color_attr.data[i].color
                target=b.secondary_color if erase else b.color
                color_attr.data[i].color=tuple(old[j]*(1-factor)+target[j]*factor for j in range(3))+(1,)
        changed=True
    if changed:mesh.update()
    return changed


class LANDFALL_STUDIO_OT_sculpt_pen(bpy.types.Operator):
    bl_idname='landfall_studio.sculpt_pen'
    bl_label='ZBrush Pen Gesture'
    bl_options={'BLOCKING','UNDO'}
    poll=classmethod(sculpt_poll)

    def invoke(self,context,event):
        global marquee
        update_cursor(context,event)
        from ..ui.sculpt_widgets import set_origin
        set_origin(context)
        self.start=self.prev=(event.mouse_region_x,event.mouse_region_y)
        self.hit=raycast(context,self.start)
        self.action=classify(self.hit['kind'],event.ctrl,event.shift,event.alt)
        self.alt=event.alt; self.drag=False; self.path=[self.start]
        self.rv=context.region_data; self.alt_released=False
        self.start_rotation=self.rv.view_rotation.copy()
        self.start_distance=self.rv.view_distance
        self.start_location=self.rv.view_location.copy()
        self.start_perspective=self.rv.view_perspective
        s=state.get()
        active_tool=context.workspace.tools.from_space_view3d_mode('SCULPT',create=False)
        if s.mrgb_enabled and s.navigation_tool=='DRAW' and (not active_tool or active_tool.idname=='builtin.brush' or active_tool.idname.startswith('builtin_brush.')) and self.hit['kind']=='ACTIVE' and not(event.ctrl or event.shift):
            self.action='MATERIAL'
            o=ops.active(context)
            self.material_backup=[p.material_index for p in o.data.polygons]
            self.material_count=len(o.data.materials)
            self.color_names={attr.name for attr in o.data.color_attributes}
            attr=o.data.color_attributes.active_color
            self.color_backup=(attr.name,[tuple(x.color) for x in attr.data]) if attr else None
            material_dab(context,self.start,event.pressure or 1,event.alt)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        if not(event.ctrl or event.shift or event.alt) and s.navigation_tool!='DRAW':
            self.action={'MOVE':'PAN','ZOOM':'ZOOM','ROTATE':'ORBIT'}[s.navigation_tool]
        if self.action in ('STROKE','INVERT','SMOOTH'):
            m=ops.multires()
            if ops.active().active_shape_key_index and m and m.sculpt_levels>0 and state.brush().sculpt_brush_type not in ('MASK','PAINT','DRAW_FACE_SETS'):
                self.report({'WARNING'},'Shape layers record base vertices; enable REC to return to base resolution')
                return {'FINISHED'}
            if ops.active().active_shape_key_index and not s.record_layer and state.brush().sculpt_brush_type not in ('MASK','PAINT','DRAW_FACE_SETS'):
                self.report({'WARNING'},'Enable layer REC before sculpting this layer')
                return {'FINISHED'}
            tool=context.workspace.tools.from_space_view3d_mode('SCULPT',create=False)
            if tool and tool.idname in ('builtin.move','builtin.rotate','builtin.scale'):
                return {'PASS_THROUGH'}
            if s.active_zbrush_brush=='IMM Primitives':
                # ZBrush InsertMesh: drag on the surface to place and size the
                # current part, aligned to the surface normal.
                self.action='IMM'
                context.window_manager.modal_handler_add(self)
                return {'RUNNING_MODAL'}
            record(self.action,hit=self.hit['kind'])
            # The next owned keymap item invokes the native stroke directly.
            # Nesting a native paint modal inside a Python modal leaves an
            # invalid undo context on Blender 5.2 when the stroke finishes.
            return {'PASS_THROUGH'}
        if self.action=='MASK' and self.hit['kind']=='ACTIVE':
            if event.value=='CLICK':
                finish_mask(context,self.hit,self.start,self.start,self.alt,False)
                record('SHARPEN_MASK' if self.alt else 'BLUR_MASK')
                return {'FINISHED'}
            # Native CLICK_DRAG fallback retains the original tablet stroke.
            record('MASK_PRESS',erase=self.alt)
            return {'PASS_THROUGH'}
        if event.value=='CLICK': return {'PASS_THROUGH'}
        if self.action=='IGNORE': return {'PASS_THROUGH'}

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self,context,event):
        global marquee
        update_cursor(context,event)
        if context.mode!='SCULPT' or event.type in ('ESC','RIGHTMOUSE','WINDOW_DEACTIVATE'):
            if self.action=='MATERIAL' and context.mode=='SCULPT':
                o=ops.active(context)
                for p,value in zip(o.data.polygons,self.material_backup):p.material_index=value
                if self.color_backup:
                    name,colors=self.color_backup; attr=o.data.color_attributes.get(name)
                    if attr:
                        for item,color in zip(attr.data,colors):item.color=color
                for attr in list(o.data.color_attributes):
                    if attr.name not in self.color_names:o.data.color_attributes.remove(attr)
                while len(o.data.materials)>self.material_count:o.data.materials.pop(index=len(o.data.materials)-1)
                o.data.update()
            if self.action in ('ORBIT','PAN','ZOOM'):
                self.rv.view_rotation=self.start_rotation
                self.rv.view_distance=self.start_distance
                self.rv.view_location=self.start_location
                self.rv.view_perspective=self.start_perspective
            marquee=None
            return {'CANCELLED'}
        xy=(event.mouse_region_x,event.mouse_region_y)
        if event.type in ('LEFT_ALT','RIGHT_ALT') and event.value=='RELEASE' and self.action=='PAN':
            self.action='ZOOM'; self.prev=xy; self.alt_released=True
        if self.action=='IMM':
            return self._imm_modal(context,event,xy)
        if event.type=='MOUSEMOVE':
            self.drag=self.drag or math.dist(self.start,xy)>=6
            self.path.append(xy)
            dx,dy=xy[0]-self.prev[0],xy[1]-self.prev[1]
            if self.action=='MATERIAL':
                material_dab(context,xy,event.pressure or 1,self.alt)
            elif self.action in ('MASK','VISIBILITY'):
                marquee=(self.start,xy,context.area.as_pointer())
            elif self.drag:
                if self.action=='ORBIT':
                    if event.shift:
                        direction=self.rv.view_rotation@Vector((0,0,1))
                        idx=max(range(3),key=lambda i:abs(direction[i]))
                        axis=(('RIGHT','LEFT'),('BACK','FRONT'),('TOP','BOTTOM'))[idx][direction[idx]<0]
                        bpy.ops.view3d.view_axis(type=axis,align_active=False)
                    else:
                        q=Quaternion((0,0,1),-dx*0.008)
                        right=self.rv.view_rotation@Vector((1,0,0))
                        self.rv.view_rotation=q@Quaternion(right,dy*0.008)@self.rv.view_rotation
                        if self.rv.view_perspective!='CAMERA': self.rv.view_perspective='PERSP'
                elif self.action=='PAN':
                    prev=region_2d_to_location_3d(context.region,self.rv,self.prev,self.rv.view_location)
                    curr=region_2d_to_location_3d(context.region,self.rv,xy,self.rv.view_location)
                    self.rv.view_location+=prev-curr
                elif self.action=='ZOOM':
                    sign=1 if self.alt_released else -1
                    self.rv.view_distance=max(0.001,min(1e6,self.rv.view_distance*math.exp(sign*(dx+dy)*0.008)))
            self.prev=xy
            context.area.tag_redraw()
        if event.type=='LEFTMOUSE' and event.value=='RELEASE':
            try:
                if self.action=='SUBTOOL' and not self.drag:
                    ops.switch_subtool(self.hit['object'])
                elif (self.action=='ORBIT' and not self.drag and self.hit['kind']=='BLANK'
                      and state.get().active_zbrush_brush=='IMM Primitives'):
                    # A plain click on empty canvas chooses the part, like
                    # ZBrush's IMM palette; a drag there still orbits.
                    self.rv.view_rotation=self.start_rotation
                    from ..ui.zbrush_panel import show_imm_picker
                    show_imm_picker()
                elif self.action=='MASK': finish_mask(context,self.hit,self.start,xy,self.alt,self.drag,self.path)
                elif self.action=='VISIBILITY': finish_visibility(context,self.hit,self.start,xy,self.alt,self.drag)
                record(self.action,hit=self.hit['kind'],drag=self.drag,alt_released=self.alt_released)
            except Exception as exc:
                self.report({'WARNING'},str(exc))
                record('ERROR',error=str(exc))
            marquee=None
            return {'FINISHED'}
        return {'RUNNING_MODAL'}


def imm_world_size(context,hit_location,start_xy,radius_px):
    """World length of a screen radius at the hit depth."""
    from bpy_extras.view3d_utils import region_2d_to_location_3d
    a=region_2d_to_location_3d(context.region,context.region_data,start_xy,hit_location)
    b=region_2d_to_location_3d(context.region,context.region_data,(start_xy[0]+radius_px,start_xy[1]),hit_location)
    return (b-a).length*2.0


def _imm_modal(self,context,event,xy):
    global imm_preview
    s=state.get()
    if event.type in ('ESC','RIGHTMOUSE') or context.mode!='SCULPT':
        imm_preview=None;context.area.tag_redraw();return {'CANCELLED'}
    radius=max(math.dist(self.start,xy),1.0)
    if event.type=='MOUSEMOVE':
        self.drag=self.drag or radius>=6
        imm_preview=(self.start,radius if self.drag else None,context.area.as_pointer())
        context.area.tag_redraw()
    if event.type=='LEFTMOUSE' and event.value=='RELEASE':
        imm_preview=None;context.area.tag_redraw()
        b=state.brush();brush_px=b.size if b else s.draw_size
        size=imm_world_size(context,self.hit['location'],self.start,radius if self.drag else brush_px)
        try:
            result=ops.run('IMM_INSERT',location=list(self.hit['location']),normal=list(self.hit['normal']),
                           size=size,part=s.imm_part)
            record('IMM',part=s.imm_part,size=size,ok=result.get('ok'))
            if not result.get('ok'):self.report({'WARNING'},result.get('error','Insert failed'))
        except Exception as exc:
            self.report({'WARNING'},str(exc));record('ERROR',error=str(exc))
        return {'FINISHED'}
    return {'RUNNING_MODAL'}


LANDFALL_STUDIO_OT_sculpt_pen._imm_modal=_imm_modal


class LANDFALL_STUDIO_OT_sculpt_shortcut(bpy.types.Operator):
    bl_idname='landfall_studio.sculpt_shortcut'
    bl_label='ZBrush Sculpt Shortcut'
    action:bpy.props.StringProperty()
    @classmethod
    def poll(cls,context):
        return context.mode=='SCULPT' and context.area and context.area.type=='VIEW_3D' and hasattr(context.scene,'landfall_sculpt')

    def invoke(self,context,event):
        from ..ui.sculpt_widgets import set_origin
        set_origin(context)
        return self.execute(context)

    def execute(self,context):
        from ..ui import zbrush_panel
        a=self.action
        from ..ui import sculpt_widgets
        sculpt_widgets.set_origin(context)
        if a in ('QUICK','QUICK_STICKY'):sculpt_widgets.show_quick(momentary=a=='QUICK')
        elif a=='QUICK_RELEASE':sculpt_widgets.close_popup()
        elif a=='FOCUS_UI':
            from . import layout
            layout.request_focus()
        elif a=='PALETTE': zbrush_panel.show_brush_palette()
        elif a in ('draw_size','focal_shift','z_intensity'): zbrush_panel.show_slider(a)
        else:
            mapping={'Q':('TOOL',{'tool':'DRAW'}),'W':('TOOL',{'tool':'MOVE'}),'E':('TOOL',{'tool':'SCALE'}),'R':('TOOL',{'tool':'ROTATE'}),
                     'X':('SYMMETRY',{}),'L':('TOGGLE',{'field':'lazy_mouse'}),'K':('TOGGLE',{'field':'show_shortcut_hud'}),
                     'P':('PERSP',{}),'F':('FRAME',{}),'POLYFRAME':('POLYFRAME',{}),'DIVIDE':('DIVIDE',{}),
                     'LOWER':('LOWER',{}),'HIGHER':('HIGHER',{}),'GROUP':('GROUP',{'mode':'MASKED'}),
                     'GROW':('MASK',{'kind':'GROW'}),'SHRINK':('MASK',{'kind':'SHRINK'}),
                     'CONTRAST_UP':('MASK',{'kind':'CONTRAST_INCREASE'}),'CONTRAST_DOWN':('MASK',{'kind':'CONTRAST_DECREASE'})}
            action,args=mapping[a]; ops.run(action,**args)
        return {'FINISHED'}


class LANDFALL_STUDIO_OT_sculpt_cursor(bpy.types.Operator):
    bl_idname='landfall_studio.sculpt_cursor'
    bl_label='Sculpt Cursor Monitor'
    bl_options={'INTERNAL'}

    def invoke(self,context,event):
        self.generation=tracker_generation
        self.area=context.area.as_pointer()
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self,context,event):
        if self.generation!=tracker_generation: return {'FINISHED','PASS_THROUGH'}
        if not context.window or not any(area.as_pointer()==self.area for area in context.window.screen.areas):
            return {'FINISHED','PASS_THROUGH'}
        if context.area and context.area.as_pointer()==self.area:
            update_cursor(context,event)
            if context.mode=='SCULPT': context.area.tag_redraw()
        return {'PASS_THROUGH'}


CLASSES=(LANDFALL_STUDIO_OT_sculpt_pen,LANDFALL_STUDIO_OT_sculpt_shortcut,LANDFALL_STUDIO_OT_sculpt_cursor)
