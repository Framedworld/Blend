"""Sculpt-only read-only native cursor/gesture overlay and actual Qt canvas UI."""
import math
import time
import bpy
from mathutils import Vector
from ..sculpt import state,gestures,ops

_handle=None
_canvases=[]
_rendering_offscreen=False
flash_name=''
flash_until=0


def draw():
    if _rendering_offscreen:return
    if not hasattr(bpy.context.scene,'landfall_sculpt'): return
    area=bpy.context.area
    import gpu
    # GPUOffScreen restores its framebuffer binding, not the caller's viewport
    # or render state. Keep thumbnail drawing local to this draw callback.
    viewport=gpu.state.viewport_get();scissor=gpu.state.scissor_get()
    depth=gpu.state.depth_test_get();mask=gpu.state.depth_mask_get();blend=gpu.state.blend_get()
    try:
        for canvas in _canvases:
            if canvas.bar.area==area and canvas.silhouette.isVisible():canvas.render_silhouette()
    finally:
        gpu.state.viewport_set(*viewport);gpu.state.scissor_set(*scissor)
        gpu.state.depth_test_set(depth);gpu.state.depth_mask_set(mask);gpu.state.blend_set(blend)
    if bpy.context.mode!='SCULPT':return
    import gpu,blf
    from gpu_extras.batch import batch_for_shader
    s=state.get(); c=gestures.cursor_for_draw(bpy.context)
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    def lines(points,color,closed=False):
        if closed: points=points+[points[0]]
        shader.bind(); shader.uniform_float('color',color)
        batch_for_shader(shader,'LINE_STRIP',{'pos':points}).draw(shader)
    gpu.state.blend_set('ALPHA'); gpu.state.line_width_set(1.5)
    if s.bbrush_enabled and c['area']==area.as_pointer():
        color=(.32,.81,.40,1) if c['ctrl'] and c['shift'] else ((1,.83,.23,1) if c['ctrl'] else ((.22,.64,.85,1) if c['shift'] else (1,.23,.19,1)))
        x,y=c['xy']; b=state.brush()
        radius=b.size if b else s.draw_size
        if not c['pressed']:
            for size in (radius,max(1,radius*(s.focal_shift+100)/200)):
                points=[(x+math.cos(i*math.tau/96)*size,y+math.sin(i*math.tau/96)*size) for i in range(97)]
                lines(points,color)
        lines([(x-4,y),(x+4,y)],color)
        lines([(x,y-4),(x,y+4)],color)
    if gestures.imm_preview and gestures.imm_preview[2]==area.as_pointer() and gestures.imm_preview[1]:
        (x,y),size,_=gestures.imm_preview
        lines([(x+math.cos(i*math.tau/64)*size,y+math.sin(i*math.tau/64)*size) for i in range(65)],(1,.65,.1,1))
        lines([(x-6,y),(x+6,y)],(1,.65,.1,1));lines([(x,y-6),(x,y+6)],(1,.65,.1,1))
    if gestures.marquee and gestures.marquee[2]==area.as_pointer():
        a,b,_=gestures.marquee
        lines([a,(b[0],a[1]),b,(a[0],b[1])],(1,.65,.1,1),True)
    def text(x,y,message,color=(.9,.9,.9,1),size=12):
        blf.position(0,x,y,0); blf.size(0,size); blf.color(0,*color); blf.draw(0,message)
    if s.show_shortcut_hud:
        for i,label in enumerate(['B → two brush letters   S Size   U Intensity   O Focal',
            'Blank drag: Orbit  ·  Alt: Pan  ·  release Alt: Zoom',
            'Shift: Smooth / Ortho snap  ·  Alt click: SubTool',
            'Ctrl: Mask  ·  Ctrl Alt: Erase  ·  Ctrl Shift: Hide',
            'Ctrl D: Divide  ·  D / Shift D: Levels  ·  K: Hide help']):
            text(20,100-i*17,label)
    if time.monotonic()<flash_until: text(24,bpy.context.region.height-235,flash_name,(1,.57,.17,1),18)
    gpu.state.line_width_set(1); gpu.state.blend_set('NONE')


class SculptCanvas:
    """Real embedded PySide6 navigation and resizable silhouette for one view."""
    def __init__(self,bar):
        from PySide6 import QtCore,QtGui,QtWidgets
        from blendertk.ui_utils.qt_dock import QtDock
        from ..ui.zbrush_panel import SCULPT_STYLE,button
        self.bar=bar; self.helpers=[]; self.buttons={}; self._last_silhouette=0
        self._offscreen=None;self._batches=[];self._mesh_signature=None;self._size=160
        self.render_calls=0;self.last_render_ms=0;self.max_render_ms=0
        self.root=QtWidgets.QFrame(); self.root.setObjectName('ZBrushCanvasButtons'); self.root.setStyleSheet(SCULPT_STYLE)
        from ..ui.sculpt_input import polish
        polish(self.root)
        lay=QtWidgets.QVBoxLayout(self.root); lay.setContentsMargins(2,2,2,2); lay.setSpacing(2)
        self.advanced=[]
        for label,action,args in [('Persp P','PERSP',{}),('Floor','FLOOR',{}),('Local','LOCAL',{}),('L.Sym','LOCAL_SYM',{}),('Frame F','FRAME',{}),
                    ('Move','NAV',{'tool':'MOVE'}),('Zoom','NAV',{'tool':'ZOOM'}),('Rotate','NAV',{'tool':'ROTATE'}),('Draw Q','NAV',{'tool':'DRAW'}),
                    ('PolyF ⇧F','POLYFRAME',{}),('Transp','TRANSP',{}),('Ghost','GHOST',{}),('Solo','SOLO',{}),('Xpose','XPOSE',{})]:
            if label in ('Move','PolyF ⇧F'):
                line=QtWidgets.QFrame();line.setFrameShape(QtWidgets.QFrame.HLine);lay.addWidget(line)
            b=button(label,callback=lambda _,a=action,k=args:self.bar.run(lambda:ops.run(a,**k)),checkable=action in ('SOLO','POLYFRAME','GHOST','PERSP','FLOOR','NAV','TRANSP','LOCAL','LOCAL_SYM','XPOSE'))
            b.setFixedHeight(25); lay.addWidget(b); self.buttons[label]=b
            if label in ('Local','L.Sym','Ghost','Xpose'):self.advanced.append(b);b.hide()
        self.more=button('More…',callback=lambda v:[b.setVisible(v) for b in self.advanced],checkable=True);lay.addWidget(self.more)
        self.root.setFixedWidth(64)
        self.buttons['L.Sym'].setToolTip('Native symmetry in this SubTool’s local frame · toggle enabled axes')
        self.buttons['Ghost'].setToolTip('Show other SubTools as wire ghosts')
        for label,tip in [('Move','Move the canvas · pan the view'),('Zoom','Zoom the canvas'),('Rotate','Rotate the canvas · orbit the view'),('Draw Q','Return to pen sculpting'),('Frame F','Frame the active SubTool')]:self.buttons[label].setToolTip(tip)
        owner=self
        class Silhouette(QtWidgets.QWidget):
            def __init__(self):
                super().__init__(); self.polygons=[]; self.image=None; self.setObjectName('ZBrushSilhouetteCanvas'); self.resize_anchor=None
            def paintEvent(self,event):
                p=QtGui.QPainter(self); p.fillRect(self.rect(),QtGui.QColor('#121417'))
                p.setRenderHint(QtGui.QPainter.Antialiasing,True)
                if self.image is not None:p.drawImage(self.rect(),self.image)
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QColor('#7B828C')); p.drawRect(self.rect().adjusted(0,0,-1,-1))
                p.setPen(QtGui.QColor('#E87D0D')); p.drawText(7,15,'SILHOUETTE')
                p.drawLine(self.width()-12,self.height()-3,self.width()-3,self.height()-12)
                p.drawLine(self.width()-7,self.height()-3,self.width()-3,self.height()-7)
            def mousePressEvent(self,e):
                if e.button()==QtCore.Qt.LeftButton and e.position().x()>self.width()-20 and e.position().y()>self.height()-20:
                    self.resize_anchor=(e.globalPosition(),state.get().silhouette_scale)
                elif e.button()==QtCore.Qt.RightButton:
                    from ..ui.zbrush_panel import show_menu,change
                    show_menu([(label,lambda v=value:change('silhouette_mode',v)) for label,value in [('Only Sculpt','ONLY_SCULPT'),('Always','ALWAYS'),('Hide','DISABLE')]])
            def mouseMoveEvent(self,e):
                if self.resize_anchor and e.buttons()&QtCore.Qt.LeftButton:
                    pos,scale=self.resize_anchor
                    state.get().silhouette_scale=max(.4,min(3,scale+(e.globalPosition().x()-pos.x())/160))
                    owner.sync()
            def mouseReleaseEvent(self,e): self.resize_anchor=None
            def cancel_pen_interaction(self):
                if self.resize_anchor:
                    state.get().silhouette_scale=self.resize_anchor[1];self.resize_anchor=None
                    if self.isVisible():owner.sync()
        self.silhouette=Silhouette()
        polish(self.silhouette)
        _canvases.append(self)
        for root in (self.root,self.silhouette):
            helper=QtDock(editor='Info',area_header=False,focus_on_hover=True)
            helper._window,helper._hwnd=bar.window,bar.hwnd
            if not helper._embed(root,bar.hwnd): raise RuntimeError('Cannot embed sculpt canvas widgets')
            self.helpers.append(helper)
        self.sync()

    def update_silhouette(self,size):
        # Rendering belongs to Blender's GPU draw context. The Qt timer only
        # requests it; a dense sculpt is never projected face-by-face in Python.
        self._size=size
        self.bar.area.tag_redraw()

    def render_silhouette(self):
        import gpu,numpy as np
        from gpu_extras.batch import batch_for_shader
        from mathutils import Matrix
        from PySide6 import QtGui
        now=time.monotonic()
        if now-self._last_silhouette<.12:return
        started=time.perf_counter()
        self._last_silhouette=now
        context=bpy.context;rv=context.region_data;dg=context.evaluated_depsgraph_get()
        visible=[o for o in ops.meshes() if o.visible_get()]
        if any(any(m.type=='MULTIRES' and m.sculpt_levels>0 and m.show_viewport for m in obj.modifiers) for obj in visible):
            self.render_multires_silhouette(visible,started)
            return
        signature=tuple((o.name,o.data.as_pointer(),len(o.data.vertices),len(o.data.polygons),tuple(o.matrix_world)) for o in visible)
        # Refresh dynamic vertex buffers while sculpting, retaining topology
        # batches during camera-only changes. Native evaluated meshes include
        # visible Multires levels and current corrective shapes.
        if signature!=self._mesh_signature or now-getattr(self,'_buffer_time',0)>.5:
            self._batches=[];points=[];triangle_count=0
            shader=gpu.shader.from_builtin('UNIFORM_COLOR')
            for obj in visible:
                evaluated=obj.evaluated_get(dg);mesh=evaluated.to_mesh()
                try:
                    mesh.calc_loop_triangles()
                    coords=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',coords)
                    indices=np.empty(len(mesh.loop_triangles)*3,dtype=np.int32);mesh.loop_triangles.foreach_get('vertices',indices)
                    indices=indices.reshape(-1,3)
                    hidden=mesh.attributes.get('.hide_poly')
                    if hidden and len(indices):
                        hides=np.empty(len(mesh.polygons),dtype=np.bool_);hidden.data.foreach_get('value',hides)
                        faces=np.empty(len(mesh.loop_triangles),dtype=np.int32);mesh.loop_triangles.foreach_get('polygon_index',faces)
                        indices=indices[~hides[faces]]
                    batch=batch_for_shader(shader,'TRIS',{'pos':coords.reshape(-1,3)},indices=indices)
                    self._batches.append((batch,obj.matrix_world.copy()))
                    triangle_count+=len(indices)
                    points.extend(obj.matrix_world@Vector(corner) for corner in evaluated.bound_box)
                finally:evaluated.to_mesh_clear()
            self._bounds=points;self.silhouette.polygons=triangle_count
            self._mesh_signature=signature;self._buffer_time=now
        projected=[]
        for point in getattr(self,'_bounds',[]):
            clip=rv.perspective_matrix@point.to_4d()
            if clip.w>1e-6:projected.append(Vector((clip.x/clip.w,clip.y/clip.w)))
        if not projected:return
        lo=Vector((min(p.x for p in projected),min(p.y for p in projected)))
        hi=Vector((max(p.x for p in projected),max(p.y for p in projected)))
        # NDC x and y have different pixel scales in a wide viewport. Preserve
        # the apparent shape when fitting the current view into a square.
        aspect=context.region.width/max(1,context.region.height)
        width=(hi.x-lo.x)*aspect;height=hi.y-lo.y
        factor=1.7/max(width,height,1e-6);center=(lo+hi)*.5
        fit=Matrix.Identity(4);fit[0][0]=factor*aspect;fit[1][1]=factor
        fit[0][3]=-center.x*factor*aspect;fit[1][3]=-center.y*factor
        size=self._size
        if self._offscreen is None or self._offscreen.width!=size:
            if self._offscreen:self._offscreen.free()
            self._offscreen=gpu.types.GPUOffScreen(size,size)
        with self._offscreen.bind():
            fb=gpu.state.active_framebuffer_get();fb.clear(color=(.07,.08,.09,1))
            gpu.state.depth_test_set('NONE');gpu.state.blend_set('NONE')
            with gpu.matrix.push_pop(),gpu.matrix.push_pop_projection():
                gpu.matrix.load_projection_matrix(fit@rv.perspective_matrix)
                shader=gpu.shader.from_builtin('UNIFORM_COLOR')
                shader.bind();shader.uniform_float('color',(.85,.86,.87,1))
                for batch,matrix in self._batches:
                    gpu.matrix.load_matrix(matrix);batch.draw(shader)
            pixels=np.asarray(fb.read_color(0,0,size,size,4,0,'UBYTE'),dtype=np.uint8).tobytes()
        image=QtGui.QImage(pixels,size,size,size*4,QtGui.QImage.Format_RGBA8888)
        self.silhouette.image=image.mirrored(False,True).copy();self.silhouette.update()
        self.render_calls=getattr(self,'render_calls',0)+1
        self.last_render_ms=(time.perf_counter()-started)*1000
        self.max_render_ms=max(getattr(self,'max_render_ms',0),self.last_render_ms)

    def render_multires_silhouette(self,visible,started):
        """Read the already-rendered depth, including native live sculpt grids.

        Re-entering DrawManager from its own draw callback is unsafe. The
        viewport depth has the exact visible Multires surface without another
        render, an object-mode switch or a stale base-mesh approximation.
        """
        import gpu,numpy as np
        from PySide6 import QtCore,QtGui
        triangles=0
        for obj in visible:
            m=next((m for m in obj.modifiers if m.type=='MULTIRES' and m.show_viewport),None)
            if m and m.sculpt_levels:
                triangles+=len(obj.data.loops)*4**(m.sculpt_levels-1)*2
            else:obj.data.calc_loop_triangles();triangles+=len(obj.data.loop_triangles)
        x,y,width,height=gpu.state.viewport_get()
        depth=np.asarray(gpu.state.active_framebuffer_get().read_depth(x,y,width,height),dtype=np.float32).reshape(height,width)
        mask=(depth>1e-6)&(depth<1-1e-6)
        yy,xx=np.nonzero(mask)
        if not len(xx):return
        crop=mask[yy.min():yy.max()+1,xx.min():xx.max()+1]
        pixels=np.empty((*crop.shape,4),dtype=np.uint8)
        pixels[:,:,:3]=np.where(crop[:,:,None],218,18);pixels[:,:,3]=255
        image=QtGui.QImage(pixels.tobytes(),crop.shape[1],crop.shape[0],crop.shape[1]*4,QtGui.QImage.Format_RGBA8888).mirrored(False,True).copy()
        size=self._size
        image=image.scaled(size-20,size-34,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation)
        canvas=QtGui.QImage(size,size,QtGui.QImage.Format_RGBA8888);canvas.fill(QtGui.QColor('#121417'))
        painter=QtGui.QPainter(canvas);painter.drawImage((size-image.width())//2,24+(size-34-image.height())//2,image);painter.end()
        self.silhouette.image=canvas;self.silhouette.polygons=triangles;self.silhouette.update()
        self.depth_viewport=(x,y,width,height)
        self.render_calls+=1;self.last_render_ms=(time.perf_counter()-started)*1000;self.max_render_ms=max(self.max_render_ms,self.last_render_ms)

    def sync(self):
        from blendertk.ui_utils.blender_window import BlenderWindow
        s=state.get(); sculpt=bpy.context.mode=='SCULPT'
        from ..sculpt import is_engaged
        from ..sculpt import layout
        show=sculpt and is_engaged() and not layout.focus
        self.root.setVisible(show)
        region=next(r for r in self.bar.area.regions if r.type=='WINDOW')
        rect=BlenderWindow.region_client_rect(self.bar.hwnd,region)
        if not rect: return
        x,y,w,h=rect
        if show:
            BlenderWindow.move_child(int(self.root.winId()),(x+w-68,y+38,64,min(h-42,max(320,self.root.sizeHint().height()))))
            with bpy.context.temp_override(**self.bar.context()):
                sp=bpy.context.space_data
                values={'Solo':s.solo_active,'Ghost':s.ghost_transparency_active,'PolyF ⇧F':s.polyframe_active,
                    'Persp P':sp.region_3d.is_perspective,'Floor':sp.overlay.show_floor or bool(getattr(bpy.context.scene,'landfall_grid_finite',False)),
                    'Transp':sp.shading.show_xray,'Local':bool(sp.local_view),'L.Sym':any(getattr(ops.active(),'use_mesh_mirror_'+axis) for axis in 'xyz'),'Xpose':bool(ops._xpose)}
                values.update({label:s.navigation_tool==mode for label,mode in [('Draw Q','DRAW'),('Move','MOVE'),('Zoom','ZOOM'),('Rotate','ROTATE')]})
                for label,value in values.items(): self.buttons[label].setChecked(value)
        mini=not layout.focus and (s.silhouette_mode=='ALWAYS' or (s.silhouette_mode=='ONLY_SCULPT' and show))
        self.silhouette.setVisible(mini)
        if mini:
            size=int(160*s.silhouette_scale)
            BlenderWindow.move_child(int(self.silhouette.winId()),(x+s.silhouette_pos[0],y+s.silhouette_pos[1],size,size))
            self.update_silhouette(size)

    def teardown(self):
        if self in _canvases:_canvases.remove(self)
        if self._offscreen:
            self._offscreen.free();self._offscreen=None
        for helper in self.helpers: helper._release_widget()
        for root in (self.root,self.silhouette): root.hide(); root.deleteLater()


def register():
    global _handle
    if not bpy.app.background and _handle is None: _handle=bpy.types.SpaceView3D.draw_handler_add(draw,(),'WINDOW','POST_PIXEL')


def unregister():
    global _handle
    if _handle is not None: bpy.types.SpaceView3D.draw_handler_remove(_handle,'WINDOW')
    _handle=None
