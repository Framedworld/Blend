"""Real GUI event checks. Uses synthetic native/Qt input, not a physical tablet."""
import bpy,sys,json,traceback,math,os
from pathlib import Path
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/zbrush_sculpt_gui_results.json'
results={'passed':[],'failed':[],'input_method':'Blender event_simulate and PySide6 QtTest in isolated factory GUI','observations':{}}

def save(): OUT.write_text(json.dumps(results,indent=2,default=str))
def check(name,value,detail=None):
    results['passed' if value else 'failed'].append(name if value else {'test':name,'detail':detail}); save()
def ctx():
    w=bpy.context.window_manager.windows[0]; a=next(a for a in w.screen.areas if a.type=='VIEW_3D'); r=next(r for r in a.regions if r.type=='WINDOW')
    return {'window':w,'area':a,'region':r}
def ev(kind,value='PRESS',xy=None,**mods):
    c=ctx(); r=c['region']; x,y=xy or (r.x+r.width//2,r.y+r.height//2)
    c['window'].event_simulate(type=kind,value=value,x=int(x),y=int(y),**mods)
def key(kind,**mods): ev(kind,**mods); ev(kind,'RELEASE',**mods)
def region_xy(x,y): r=ctx()['region']; return (r.x+x,r.y+y)
def pos(obj,offset=(0,0,0)):
    c=ctx(); p=location_3d_to_region_2d(c['region'],c['area'].spaces.active.region_3d,obj.matrix_world@Vector(offset)); return region_xy(p.x,p.y)
def click(xy,**mods):
    for name,kind in [('alt','LEFT_ALT'),('ctrl','LEFT_CTRL'),('shift','LEFT_SHIFT')]:
        if mods.get(name): ev(kind,xy=xy,**mods)
    ev('MOUSEMOVE','NOTHING',xy,**mods); ev('LEFTMOUSE',xy=xy,**mods); ev('LEFTMOUSE','RELEASE',xy,**mods)
    for name,kind in [('alt','LEFT_ALT'),('ctrl','LEFT_CTRL'),('shift','LEFT_SHIFT')]:
        if mods.get(name): ev(kind,'RELEASE',xy)
def drag(start,end,release_alt=False,**mods):
    for name,kind in [('alt','LEFT_ALT'),('ctrl','LEFT_CTRL'),('shift','LEFT_SHIFT')]:
        if mods.get(name): ev(kind,xy=start,**mods)
    yield .1
    ev('MOUSEMOVE','NOTHING',start,**mods); ev('LEFTMOUSE',xy=start,**mods)
    yield .1
    for i in range(1,9):
        xy=(start[0]+(end[0]-start[0])*i/8,start[1]+(end[1]-start[1])*i/8)
        if release_alt and i==4:
            ev('LEFT_ALT','RELEASE',xy); mods['alt']=False
        ev('MOUSEMOVE','NOTHING',xy,**mods); yield .055
    ev('LEFTMOUSE','RELEASE',end,**mods); yield .15
    for name,kind in [('alt','LEFT_ALT'),('ctrl','LEFT_CTRL'),('shift','LEFT_SHIFT')]:
        if mods.get(name): ev(kind,'RELEASE',end)
    yield .15

def lasso(start,end):
    ev('LEFT_CTRL',xy=start,ctrl=True);ev('MOUSEMOVE','NOTHING',start,ctrl=True)
    ev('LEFTMOUSE',xy=start,ctrl=True);yield .1
    for point in [(end[0],start[1]),end,(start[0],end[1]),start]:
        ev('MOUSEMOVE','NOTHING',point,ctrl=True);yield .1
    ev('LEFTMOUSE','RELEASE',start,ctrl=True);ev('LEFT_CTRL','RELEASE',start);yield .2

def suite():
    import landfall_studio
    from landfall_studio.ui import desktop,shelf,viewport_bar,zbrush_panel
    from landfall_studio.sculpt import state,brushes,ops,gestures
    from landfall_studio import sculpt
    landfall_studio.register(); desktop.restore_workspace_desktop()
    from landfall_studio.sculpt import preferences
    preferences.PATH=ROOT.parent/('.test_env/ux2_legacy_gui_preferences_'+str(os.getpid())+'.json');preferences._data=None
    from PySide6 import QtCore,QtGui,QtTest,QtWidgets
    from blendertk.ui_utils.blender_window import BlenderWindow
    import ctypes
    if '--trace-focus' in sys.argv:
        import inspect
        original_focus = BlenderWindow.set_keyboard_focus
        focus_calls = []
        def trace_focus(cls, target):
            if len(focus_calls) < 100:
                focus_calls.append({'target': target, 'caller': [(f.function, f.filename.split('\\')[-1]) for f in inspect.stack()[1:4]],
                    'popup': str(QtWidgets.QApplication.activePopupWidget()), 'before': BlenderWindow.keyboard_focus()})
                results['observations']['focus_calls'] = focus_calls
            return original_focus(target)
        BlenderWindow.set_keyboard_focus = classmethod(trace_focus)
    hwnd=BlenderWindow.window_hwnd(ctx()['window']);ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd)
    yield 1.5
    stock_sculpt=[(i.idname,i.type,i.value,i.ctrl,i.shift,i.alt,i.active) for i in bpy.context.window_manager.keyconfigs.user.keymaps['Sculpt'].keymap_items if not i.idname.startswith('landfall_studio.')]
    stock_view=[(i.idname,i.type,i.value,i.ctrl,i.shift,i.alt,i.active) for i in bpy.context.window_manager.keyconfigs.user.keymaps['3D View'].keymap_items]
    original_shading=ctx()['area'].spaces.active.shading.type
    with bpy.context.temp_override(**ctx()):
        bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_monkey_add()
        body=bpy.context.object; body.name='Creature · Sculpt Body'
        sub=body.modifiers.new('Test subdivision','SUBSURF'); sub.levels=2
        bpy.ops.object.modifier_apply(modifier=sub.name)
        for p in body.data.polygons:p.use_smooth=True
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,location=(2.5,0,0))
        other=bpy.context.object; other.name='Creature · Head SubTool'; other.scale=(.5,.5,.5)
        bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); bpy.context.view_layer.objects.active=body
        bpy.ops.view3d.view_axis(type='FRONT'); ctx()['area'].spaces.active.region_3d.view_distance=7
        desktop.apply_workspace_layout('Maya Classic'); desktop.cycle_right_dock('MODELING_TOOLKIT')
        bpy.ops.object.mode_set(mode='SCULPT')
    yield 1
    check('native mode change automatically engages Studio',sculpt.is_engaged() and desktop._right_dock.mode=='ZBRUSH_STUDIO')
    check('sculpt shelf and header visible',all(sh.active_shelf_name=='ZBrush Sculpt' for sh in shelf._shelf_instances))
    sh=shelf._shelf_instances[0].sculpt_header
    panel=desktop._right_dock._ensure_host_container().sculpt_panel
    check('PySide6 widgets are actual visible controls',sh.root.isVisible() and panel.root.isVisible() and type(sh.buttons['Return']).__module__.startswith('PySide6'))
    def header_option(label):
        menu=sh.overflow();yield .1
        action=next(a for a in menu.actions() if a.text()==label)
        QtTest.QTest.mouseClick(menu,QtCore.Qt.LeftButton,pos=menu.actionGeometry(action).center());yield .1
    from landfall_studio.ui.main_menu import get_main_menu_dock
    menubar=get_main_menu_dock().ctrl.menubar
    first=menubar.actions()[0];rect=menubar.actionGeometry(first)
    menu_events=[]
    class MenuEvents(QtCore.QObject):
        def eventFilter(self,obj,event):
            if event.type() in (QtCore.QEvent.Show,QtCore.QEvent.Hide,QtCore.QEvent.WindowActivate,QtCore.QEvent.WindowDeactivate,QtCore.QEvent.FocusIn,QtCore.QEvent.FocusOut):
                menu_events.append((str(event.type()),obj.isVisible(),BlenderWindow.keyboard_focus()))
            return False
    menu_monitor=MenuEvents(first.menu());first.menu().installEventFilter(menu_monitor)
    popup_events=[]
    class PopupEvents(QtCore.QObject):
        def eventFilter(self,obj,event):
            if obj.objectName() in ('ZBrushBrushPalette','ZBrushCursorSlider') and event.type() in (QtCore.QEvent.Show,QtCore.QEvent.Hide,QtCore.QEvent.WindowActivate,QtCore.QEvent.WindowDeactivate):
                popup_events.append((obj.objectName(),str(event.type()),BlenderWindow.keyboard_focus(),[(f.name,f.filename.split('\\')[-1]) for f in traceback.extract_stack(limit=6)] if event.type()==QtCore.QEvent.Hide else []))
            return False
    popup_monitor=PopupEvents(menubar);QtWidgets.QApplication.instance().installEventFilter(popup_monitor)
    check('main menu labels are visible rather than overflow-only',rect.width()>0)
    QtGui.QCursor.setPos(menubar.mapToGlobal(rect.center()));yield .1
    QtTest.QTest.mouseClick(menubar,QtCore.Qt.LeftButton,pos=rect.center())
    results['observations']['file_menu_immediate']=first.menu().isVisible();yield .2
    check('main File label opens actual Qt menu',first.menu().isVisible(),menu_events)
    results['observations']['native_windows'] = [(w.objectName(), int(w.internalWinId() or 0), w.isVisible()) for w in QtWidgets.QApplication.topLevelWidgets() if w.internalWinId()]
    results['observations']['blender_hwnd'] = hwnd
    results['observations']['file_menu_events']=menu_events
    results['observations']['main_menu']={'geometry':menubar.geometry().getRect(),'hint':(menubar.sizeHint().width(),menubar.sizeHint().height()),'first_action':rect.getRect()}
    first.menu().close();yield .1
    # Native viewport shortcuts need the real pointer in their originating view.
    # The menu check above deliberately left it over the foreign Qt top bar.
    origin=BlenderWindow.client_origin(hwnd);region=ctx()['region']
    ctypes.windll.user32.SetCursorPos(origin[0]+region.x+region.width//2,
        origin[1]+ctx()['window'].height-1-region.y-region.height//2)
    ev('MOUSEMOVE','NOTHING');yield .2
    results['observations']['sculpt_bindings']=len(landfall_studio.keymaps.profiles._sculpt_keymaps)
    for kind,tool in [('W','builtin.move'),('E','builtin.scale'),('R','builtin.rotate'),('Q','builtin.brush')]:
        key(kind); yield .3
        with bpy.context.temp_override(**ctx()):current=bpy.context.workspace.tools.from_space_view3d_mode('SCULPT',create=False).idname
        check('native sculpt key '+kind,current==tool,current)
    # Qt focus uses exactly the same sculpt mapping.
    sh.buttons['DRAW'].setFocus(); QtTest.QTest.keyClick(sh.buttons['DRAW'],QtCore.Qt.Key_E); yield .25
    with bpy.context.temp_override(**ctx()):current=bpy.context.workspace.tools.from_space_view3d_mode('SCULPT',create=False).idname
    check('Qt focused E selects Scale in Sculpt',current=='builtin.scale',current)
    key('Q'); yield .2
    # B is sent through the native queue; subsequent mnemonic keys go to Qt.
    key('B'); yield .3
    popup=next((w for w in QtWidgets.QApplication.topLevelWidgets() if w.objectName()=='ZBrushBrushPalette' and w.isVisible()),None)
    check('native B opens real Qt brush palette',popup is not None,[(w.objectName(),w.isVisible(),getattr(w,'finished',None)) for w in zbrush_panel._popups])
    results['observations']['popup_events']=popup_events
    if popup:
        from blendertk.ui_utils.blender_window import BlenderWindow
        check('brush popup owns native keyboard focus',BlenderWindow.keyboard_focus()==int(popup.winId()))
        QtTest.QTest.keyClick(popup,QtCore.Qt.Key_C); yield .1
        check('brush first letter filters choices',popup.buttons['CB'].isEnabled() and not popup.buttons['DS'].isEnabled())
        QtTest.QTest.keyClick(popup,QtCore.Qt.Key_B); yield .2
        check('B C B selects configured ClayBuildup',state.get().active_zbrush_brush=='ClayBuildup' and state.brush().sculpt_brush_type=='CLAY_STRIPS')
        check('mnemonic palette closes after choice',not popup.isVisible())
    for k,field,value in [('S','draw_size',72),('U','z_intensity',81),('O','focal_shift',20),('I','z_intensity',64)]:
        key(k); yield .25
        slider=next((w.findChild(QtWidgets.QSlider,'SculptCursorSlider_'+field) for w in QtWidgets.QApplication.topLevelWidgets() if w.objectName()=='ZBrushCursorSlider' and w.isVisible()),None)
        check('native '+k+' opens cursor slider',slider is not None,[(w.objectName(),w.isVisible(),getattr(w,'finished',None)) for w in zbrush_panel._popups])
        if slider:
            slider.setValue(value); check(field+' slider changes actual brush',round(getattr(state.get(),field))==value)
            slider.window().close()
    if '--focus-only' in sys.argv:
        save();landfall_studio.unregister();bpy.ops.wm.quit_blender();return
    key('L'); yield .2; check('native L toggles LazyMouse',state.brush().use_smooth_stroke)
    # Turn it off for short stroke checks.
    key('L'); yield .2
    mirror_before=body.use_mesh_mirror_x
    key('X'); yield .2; check('native X toggles mesh symmetry',body.use_mesh_mirror_x!=mirror_before)
    key('F',shift=True); yield .2; check('native Shift F toggles actual polyframe',body.show_wire and state.get().polyframe_active)
    key('F',shift=True); yield .2
    blank=region_xy(25,120); blank_end=region_xy(90,170)
    rv=ctx()['area'].spaces.active.region_3d
    bar=next(b for b in viewport_bar.get_bars() if b.area==ctx()['area'])
    canvas=bar.sculpt_canvas
    QtTest.QTest.mouseClick(canvas.more,QtCore.Qt.LeftButton);yield .1
    for label,read in [('Persp P',lambda:rv.is_perspective),('Floor',lambda:bool(bpy.context.scene.landfall_grid_finite)),
        ('L.Sym',lambda:any(getattr(body,'use_mesh_mirror_'+axis) for axis in 'xyz')),('PolyF ⇧F',lambda:body.show_wire),
        ('Transp',lambda:ctx()['area'].spaces.active.shading.show_xray),('Ghost',lambda:other.display_type=='WIRE'),
        ('Solo',lambda:other.hide_get()),('Xpose',lambda:bool(ops._xpose))]:
        old=read();QtTest.QTest.mouseClick(canvas.buttons[label],QtCore.Qt.LeftButton);yield .15
        check('Qt canvas '+label+' changes native state',read()!=old)
        QtTest.QTest.mouseClick(canvas.buttons[label],QtCore.Qt.LeftButton);yield .15
        check('Qt canvas '+label+' restores native state',read()==old)
    for label,mode in [('Move','MOVE'),('Zoom','ZOOM'),('Rotate','ROTATE'),('Draw Q','DRAW')]:
        QtTest.QTest.mouseClick(canvas.buttons[label],QtCore.Qt.LeftButton);yield .1
        check('Qt canvas '+label+' owns pen navigation',state.get().navigation_tool==mode)
    rot=rv.view_rotation.copy(); yield from drag(blank,blank_end)
    check('blank pen drag orbits native view',rot.rotation_difference(rv.view_rotation).angle>.01,gestures.history[-3:])
    loc=rv.view_location.copy(); yield from drag(blank,blank_end,alt=True)
    check('Alt blank pen drag pans native view',(loc-rv.view_location).length>.01,gestures.history[-3:])
    dist=rv.view_distance; yield from drag(blank,blank_end,alt=True,release_alt=True)
    check('release Alt during drag zooms native view',abs(dist-rv.view_distance)>.01,gestures.history[-3:])
    with bpy.context.temp_override(**ctx()): bpy.ops.view3d.view_axis(type='FRONT'); rv.view_location=(0,0,0); rv.view_distance=7
    yield .25
    click(pos(other),alt=True); yield .45
    check('Alt click transfers Sculpt SubTool',bpy.context.active_object==other and bpy.context.mode=='SCULPT',gestures.history[-3:])
    with bpy.context.temp_override(**ctx()):ops.switch_subtool(body); brushes.select('ST'); state.get().draw_size=55; state.get().z_intensity=60
    yield .3
    body_name=body.name;other_name=other.name
    mirror=tuple(getattr(body,'use_mesh_mirror_'+axis) for axis in 'xyz')
    for axis in 'xyz':setattr(body,'use_mesh_mirror_'+axis,False)
    before_move=[v.co.copy() for v in body.data.vertices]
    with bpy.context.temp_override(**ctx()):bpy.ops.ed.undo_push(message='Sculpt transform fixture baseline')
    key('W');yield .25
    move_start=pos(body,(-.6,-.8,.3))
    yield from drag(move_start,(move_start[0]+55,move_start[1]+25))
    deltas=[v.co-co for v,co in zip(body.data.vertices,before_move)]
    mean=sum(deltas,Vector())/len(deltas)
    check('W drag moves the sculpt surface uniformly without a brush stroke',mean.length>.001 and max((d-mean).length for d in deltas)<1e-4)
    key('Z',ctrl=True);yield .25
    body=bpy.data.objects[body_name];other=bpy.data.objects[other_name]
    check('Move Undo restores geometry and active sculpt SubTool',bpy.context.view_layer.objects.active==body and all((v.co-co).length<1e-6 for v,co in zip(body.data.vertices,before_move)))
    for axis,value in zip('xyz',mirror):setattr(body,'use_mesh_mirror_'+axis,value)
    key('Q');yield .2
    start=pos(body,(-.35,-.8,.3)); end=(start[0]+90,start[1])
    before=[v.co.copy() for v in body.data.vertices]
    body_name=body.name;other_name=other.name
    yield from drag(start,end)
    check('native pen stroke actually deforms mesh',any((v.co-co).length>1e-6 for v,co in zip(body.data.vertices,before)),gestures.history[-4:])
    key('Z',ctrl=True); yield .3
    body=bpy.data.objects[body_name];other=bpy.data.objects[other_name]
    check('native sculpt stroke Undo restores geometry',all((v.co-co).length<1e-6 for v,co in zip(body.data.vertices,before)))
    key('Z',ctrl=True,shift=True); yield .3
    body=bpy.data.objects[body_name];other=bpy.data.objects[other_name]
    check('native sculpt stroke Redo restores deformation',any((v.co-co).length>1e-6 for v,co in zip(body.data.vertices,before)))
    before_inverse=[v.co.copy() for v in body.data.vertices]
    yield from drag(start,end,alt=True)
    check('Alt on mesh performs real inverted sculpt stroke',any((v.co-co).length>1e-6 for v,co in zip(body.data.vertices,before_inverse)))
    before_smooth=[v.co.copy() for v in body.data.vertices]
    yield from drag(start,end,shift=True)
    check('Shift on mesh performs real smooth stroke',any((v.co-co).length>1e-6 for v,co in zip(body.data.vertices,before_smooth)))
    QtTest.QTest.mouseClick(sh.buttons['SUBTRACT'],QtCore.Qt.LeftButton);yield .1
    check('Qt ZSub drives actual brush direction',state.brush().direction=='SUBTRACT')
    QtTest.QTest.mouseClick(sh.buttons['ADD'],QtCore.Qt.LeftButton);yield .1
    yield from drag(start,end,ctrl=True)
    check('Ctrl pen stroke actually paints mask',max(ops.mask_values(body))>.01,gestures.history[-4:])
    amount=sum(ops.mask_values(body))
    yield from drag(start,end,ctrl=True,alt=True)
    check('Ctrl Alt native pen drag erases mask',sum(ops.mask_values(body))<amount)
    click(start,ctrl=True); yield .15
    check('Ctrl on mesh click blurs mask',gestures.history[-1]['action']=='BLUR_MASK',gestures.history[-3:])
    click(start,ctrl=True,alt=True); yield .15
    check('Ctrl Alt on mesh click sharpens mask',gestures.history[-1]['action']=='SHARPEN_MASK',gestures.history[-3:])
    click(blank,ctrl=True); yield .3
    check('Ctrl blank click inverts actual mask',sum(ops.mask_values(body))>len(body.data.vertices)*.5,gestures.history[-4:])
    yield from drag(blank,blank_end,ctrl=True)
    check('Ctrl blank drag clears actual mask',max(ops.mask_values(body))<.001,gestures.history[-4:])
    yield from drag(blank,blank_end,ctrl=True,alt=True)
    check('Ctrl Alt blank drag fills actual mask',min(ops.mask_values(body))>.99,gestures.history[-4:])
    with bpy.context.temp_override(**ctx()):ops.dispatch('MASK',kind='CLEAR')
    # Box gestures start in blank and enclose the center of the mesh.
    r=ctx()['region']; box_a=region_xy(r.width*.25,r.height*.25); box_b=region_xy(r.width*.58,r.height*.7)
    yield from drag(box_a,box_b,ctrl=True)
    check('blank marquee overlap creates real box mask',max(ops.mask_values(body))>.9,gestures.history[-4:])
    with bpy.context.temp_override(**ctx()):ops.dispatch('MASK',kind='CLEAR');state.get().mask_marquee='LASSO'
    yield from lasso(box_a,box_b)
    check('closed lasso pen path creates actual mask',max(ops.mask_values(body))>.9,gestures.history[-3:])
    state.get().mask_marquee='BOX'
    key('W',ctrl=True); yield .2
    check('Ctrl W creates real face sets',body.data.attributes.get('.sculpt_face_set') is not None)
    yield from drag(box_a,box_b,ctrl=True,shift=True)
    hidden=body.data.attributes.get('.hide_poly')
    check('Ctrl Shift box hides actual mesh faces',hidden is not None and any(x.value for x in hidden.data),gestures.history[-3:])
    click(blank,ctrl=True,shift=True); yield .25
    hidden=body.data.attributes.get('.hide_poly')
    check('Ctrl Shift blank click shows all faces',hidden is None or not any(x.value for x in hidden.data))
    # Re-DynaMesh must be reached through the signature blank pen gesture.
    with bpy.context.temp_override(**ctx()):
        ops.switch_subtool(other);state.get().dynamesh_enabled=True;state.get().dynamesh_resolution=24
        ops.dispatch('MASK',kind='CLEAR');old_count=len(other.data.vertices)
    yield from drag(blank,blank_end,ctrl=True)
    check('Ctrl blank drag performs real DynaMesh when mask empty',len(other.data.vertices)!=old_count)
    with bpy.context.temp_override(**ctx()):
        state.get().dynamesh_enabled=False;ops.switch_subtool(body)
    yield from drag(box_a,box_b,ctrl=True,shift=True,alt=True)
    hidden=body.data.attributes.get('.hide_poly')
    check('Ctrl Shift Alt box hides inside actual mesh',hidden is not None and any(x.value for x in hidden.data))
    click(blank,ctrl=True,shift=True); yield .2
    yield from drag(blank,blank_end,shift=True)
    check('Shift blank orbit snaps to orthographic view',rv.view_perspective=='ORTHO')
    with bpy.context.temp_override(**ctx()):bpy.ops.view3d.view_axis(type='FRONT');rv.view_distance=7
    yield .2
    yield from header_option('Material paint')
    with bpy.context.temp_override(**ctx()):
        body.data.materials.clear()
        body.data.materials.append(bpy.data.materials.new('Test base'))
        body.data.materials.append(bpy.data.materials.new('Test sculpt paint'))
        body.active_material_index=1
        ops.dispatch('MASK',kind='CLEAR')
    start=pos(body,(-.35,-.8,.3));end=(start[0]+90,start[1])
    yield from drag(start,end)
    check('M paints actual face material assignments',any(p.material_index==1 for p in body.data.polygons))
    yield from header_option('Material paint')
    yield from header_option('Rgb paint');yield .2
    check('Rgb activates native sculpt color brush',state.brush().sculpt_brush_type=='PAINT')
    state.brush().color=(1,0,0)
    yield from drag(start,end)
    colors=body.data.color_attributes.active_color
    check('Rgb stroke writes real mesh color data',colors is not None and len(colors.data)>0)
    results['observations']['rgb']={'tool':ctx()['window'].workspace.tools.from_space_view3d_mode('SCULPT',create=False).idname,'active':bpy.context.view_layer.objects.active.name,'history':gestures.history[-3:]}
    yield from header_option('Rgb paint');yield .2
    key('D',ctrl=True);yield .3
    with bpy.context.temp_override(**ctx()):m=ops.multires()
    check('native Ctrl D divides multires surface',m is not None and m.total_levels==1)
    key('D',shift=True);yield .2
    check('native Shift D lowers actual sculpt resolution',m is not None and m.sculpt_levels==0)
    key('D');yield .2
    check('native D raises actual sculpt resolution',m is not None and m.sculpt_levels==1)
    with bpy.context.temp_override(**ctx()):
        ops.resolution(-1)
        with ops.object_mode():body.modifiers.remove(m)
    # Real Qt button events and geometry changes.
    panel.palettes['Masking'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['Mask All']);yield .2
    QtTest.QTest.mouseClick(panel.buttons['Mask All'],QtCore.Qt.LeftButton); yield .2
    check('Qt Mask All changes native mesh mask',min(ops.mask_values(body))>.99)
    QtTest.QTest.mouseClick(panel.buttons['Clear'],QtCore.Qt.LeftButton); yield .2
    panel.palettes['Layers  ⇄ Maya BlendShapes'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['+ New Layer']);yield .2
    QtTest.QTest.mouseClick(panel.buttons['+ New Layer'],QtCore.Qt.LeftButton); yield .2
    check('Qt New Layer creates shared shape target',body.active_shape_key_index>0)
    layer_name=body.active_shape_key.name
    basis=[v.co.copy() for v in body.data.shape_keys.reference_key.data]
    layer_before=[v.co.copy() for v in body.active_shape_key.data]
    yield from drag(start,end)
    check('native sculpt records into selected shared layer',any((v.co-co).length>1e-6 for v,co in zip(body.active_shape_key.data,layer_before)))
    check('sculpt layer stroke preserves Basis',all((v.co-co).length<1e-6 for v,co in zip(body.data.shape_keys.reference_key.data,basis)))
    panel.strength.setValue(37); yield .1
    check('Qt layer strength changes actual shape key',abs(body.active_shape_key.value-.37)<1e-5)
    # Snapshot widgets from the live window, not rendered mockups.
    bar=next(b for b in viewport_bar.get_bars() if b.area==ctx()['area'])
    check('Qt canvas nav and real silhouette active',bar.sculpt_canvas.root.isVisible() and bool(bar.sculpt_canvas.silhouette.polygons))
    image=bar.sculpt_canvas.silhouette.image
    if image:
        samples={image.pixelColor(x,y).name() for x in range(0,image.width(),8) for y in range(0,image.height(),8)}
    else:samples=set()
    check('GPU silhouette contains foreground and background',len(samples)>1,sorted(samples))
    results['observations']['layout']={'shelf_root_geometry':shelf._shelf_instances[0].root.geometry().getRect(),'header_geometry':sh.root.geometry().getRect(),
        'shelf_area':[(a.type,a.x,a.y,a.width,a.height) for a in ctx()['window'].screen.areas],
        'viewport_regions':[(r.type,r.x,r.y,r.width,r.height) for r in ctx()['area'].regions],
        'bar_rect':bar.last_rect,'header_minimum_size':(sh.root.minimumSizeHint().width(),sh.root.minimumSizeHint().height())}
    sh.root.grab().save(str(ROOT/'output/zbrush_header.png'))
    panel.root.grab().save(str(ROOT/'output/zbrush_tool_tray.png'))
    bar.sculpt_canvas.silhouette.grab().save(str(ROOT/'output/zbrush_silhouette.png'))
    bar.sculpt_canvas.root.grab().save(str(ROOT/'output/zbrush_canvas_buttons.png'))
    state.get().show_shortcut_hud=True; yield .3
    ev('MOUSEMOVE','NOTHING',pos(body)); yield .3
    with bpy.context.temp_override(**ctx()):bpy.ops.screen.screenshot(filepath=str(ROOT/'output/zbrush_native_frame.png'))
    # Hidden-desktop runs (LANDFALL_NO_OS_INPUT) must not copy screen pixels: they
    # would come from the artist's visible desktop, not this window.
    try:
        if os.environ.get('LANDFALL_NO_OS_INPUT'):raise RuntimeError('screen capture skipped on hidden desktop')
        from PIL import ImageGrab
        capture=ImageGrab.grab(all_screens=True)
        capture.save(str(ROOT/'output/zbrush_desktop_capture.png'))
        results['observations']['desktop_capture_extrema']=capture.getextrema()
    except Exception as exc:results['observations']['desktop_capture_error']=str(exc)
    try:
        from PySide6 import QtGui
        from blendertk.ui_utils.blender_window import BlenderWindow
        if os.environ.get('LANDFALL_NO_OS_INPUT'):raise RuntimeError('screen capture skipped on hidden desktop')
        hwnd=BlenderWindow.window_hwnd(ctx()['window'])
        screen=QtGui.QGuiApplication.primaryScreen()
        screen.grabWindow(int(hwnd)).save(str(ROOT/'output/zbrush_window_capture.png'))
    except Exception as exc:results['observations']['window_capture_error']=str(exc)
    QtTest.QTest.mouseClick(panel.buttons['⇄ GoZ to Shape Editor'],QtCore.Qt.LeftButton); yield .5
    check('GoZ Qt button returns to Shape Editor',not sculpt.is_engaged() and bpy.context.mode=='OBJECT' and desktop._right_dock.mode=='SHAPE_EDITOR')
    se=desktop._right_dock._ensure_host_container().se_widget
    check('GoZ Shape Editor focuses exact sculpt layer',se._selected_key_name==layer_name,se._selected_key_name)
    check('previous Maya workspace restored',desktop.get_active_workspace_layout()=='Maya Classic')
    check('previous Maya viewport shading restored',ctx()['area'].spaces.active.shading.type==original_shading)
    # Native mode exit restores the previous page, including non-default page.
    desktop.cycle_right_dock('MODELING_TOOLKIT')
    with bpy.context.temp_override(**ctx()):bpy.ops.object.mode_set(mode='SCULPT')
    yield .5
    with bpy.context.temp_override(**ctx()):bpy.ops.object.mode_set(mode='OBJECT')
    yield .5
    check('external Sculpt exit restores previous dock page',desktop._right_dock.mode=='MODELING_TOOLKIT')
    check('sculpt native bindings removed on exit',not landfall_studio.keymaps.profiles._sculpt_keymaps)
    restored=[(i.idname,i.type,i.value,i.ctrl,i.shift,i.alt,i.active) for i in bpy.context.window_manager.keyconfigs.user.keymaps['Sculpt'].keymap_items if not i.idname.startswith('landfall_studio.')]
    check('native Sculpt bindings regain original active state',all(x in restored for x in stock_sculpt),[x for x in stock_sculpt if x not in restored])
    restored_view=[(i.idname,i.type,i.value,i.ctrl,i.shift,i.alt,i.active) for i in bpy.context.window_manager.keyconfigs.user.keymaps['3D View'].keymap_items]
    check('original viewport bindings regain original active state',all(x in restored_view for x in stock_view),[x for x in stock_view if x not in restored_view])
    results['observations']['gesture_history']=gestures.history
    landfall_studio.unregister()
    check('GUI unregister releases sculpt HUD and Qt canvas',not hasattr(bpy.types.Scene,'landfall_sculpt') and not viewport_bar.get_bars())
    save()
    print('SCULPT_GUI_RESULTS',len(results['passed']),'passed',len(results['failed']),'failed')
    bpy.ops.wm.quit_blender()

generator=None
def tick():
    global generator
    try:return next(generator)
    except StopIteration:return None
    except Exception:
        check('suite exception',False,traceback.format_exc()); print(traceback.format_exc()); bpy.ops.wm.quit_blender(); return None
def start():
    global generator
    bpy.context.preferences.view.show_splash=False
    bpy.ops.wm.read_homefile()
    generator=suite(); bpy.app.timers.register(tick,first_interval=.5,persistent=True)
    return None
bpy.app.timers.register(start,first_interval=.5)
