"""Second-pass native UI acceptance. Uses disposable factory demo only."""
import bpy,sys,json,traceback,ctypes,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_UX_TEST_TAG','')
OUT=ROOT/('output/sculpt_ux2_gui_results'+TAG+'.json');results={'passed':[],'failed':[],'captures':[],'input_method':'Blender native event_simulate, PySide6 QtTest, native Windows sizing'}
def check(name,value,detail=None):
    results['passed' if value else 'failed'].append(name if value else {'test':name,'detail':detail});save()
def save():OUT.write_text(json.dumps(results,indent=2,default=str))
def ctx():
    from landfall_studio.sculpt.ops import view_context
    return view_context()
def key(name,value='PRESS',**mods):
    c=ctx();r=c['region']
    from PySide6 import QtWidgets
    if value=='PRESS' and name not in ('LEFT_SHIFT','LEFT_CTRL','LEFT_ALT') and QtWidgets.QApplication.activePopupWidget() is None:
        from blendertk.ui_utils.blender_window import BlenderWindow
        app=QtWidgets.QApplication.instance()
        if app.focusWidget():app.focusWidget().clearFocus()
        app.setActiveWindow(None)
        hwnd=BlenderWindow.window_hwnd(c['window']);origin=BlenderWindow.client_origin(hwnd)
        ctypes.windll.user32.SetCursorPos(origin[0]+r.x+r.width//2,origin[1]+c['window'].height-1-r.y-r.height//2)
        BlenderWindow.set_keyboard_focus(hwnd)
    c['window'].event_simulate(type=name,value=value,x=r.x+r.width//2,y=r.y+r.height//2,**mods)
def capture(name,hwnd):
    from PySide6.QtGui import QGuiApplication
    # Hidden-desktop runs (LANDFALL_NO_OS_INPUT) must not copy screen pixels: they
    # would come from the artist's visible desktop, not this window.
    if os.environ.get('LANDFALL_NO_OS_INPUT'):results.setdefault('captures_skipped',[]).append(name);return
    path=ROOT/'output'/(TAG.lstrip('_')+'_'+name if TAG else name);QGuiApplication.primaryScreen().grabWindow(int(hwnd)).save(str(path));results['captures'].append(str(path));save()
def suite():
    import landfall_studio
    landfall_studio.register()
    from landfall_studio.ui import desktop,sculpt_widgets,zbrush_panel,viewport_bar,shelf,main_menu
    from landfall_studio.sculpt import ops,state,layout,preferences,brushes
    from landfall_studio.sculpt.demo import create_demo
    from landfall_studio.adapters import tentacle_bridge
    from PySide6 import QtCore,QtWidgets,QtTest,QtGui
    from blendertk.ui_utils.blender_window import BlenderWindow
    results['qt_device_pixel_ratio']=QtGui.QGuiApplication.primaryScreen().devicePixelRatio()
    preferences.PATH=ROOT.parent/('.test_env/ux2_gui_preferences_'+str(os.getpid())+'.json');preferences._data=None
    desktop.restore_workspace_desktop()
    original={a.as_pointer():(a.width,a.height) for a in ctx()['window'].screen.areas}
    original_key=tentacle_bridge.get_activation_key_info()['qt_key']
    modal=bpy.context.window_manager.keyconfigs.user.keymaps.get('Paint Stroke Modal')
    original_modal=[(i.type,i.value,i.propvalue,i.active) for i in modal.keymap_items] if modal else []
    create_demo();yield 1
    hwnd=BlenderWindow.window_hwnd(ctx()['window']);ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd);yield .5
    check('Sculpt layout owns actual left and bottom widgets',layout.active and layout._owners['left']._inner_dock.widget.objectName()=='SculptBrushShelf' and layout._owners['bottom']._inner_dock.widget.objectName()=='SculptFavorites')
    check('brush wells have real image previews',all(not b.icon().isNull() for b in layout._left.wells.values()))
    check('favorite order matches approved defaults',list(layout._favorites.tiles)==list(preferences.DEFAULT_FAVORITES))
    check('native canvas reclaims Maya shelf and Outliner area',layout._owners['left']._inner_dock.area.width<original[layout._owners['left']._inner_dock.area.as_pointer()][0] and layout._owners['top']._inner_dock.area.height<original[layout._owners['top']._inner_dock.area.as_pointer()][1])
    check('Tentacle activation suspended without rebinding',tentacle_bridge._sculpt_suspended is not None and tentacle_bridge.get_activation_key_info()['qt_key']==original_key)
    panel=zbrush_panel._panels[0]
    geometry=next(g for n,g in panel.palettes.items() if n=='Geometry');mask=panel.palettes['Masking']
    check('Geometry starts expanded and other tool palettes closed',geometry.isChecked() and not mask.isChecked())
    mask.setChecked(True);check('accordion opens one tool palette',mask.isChecked() and not geometry.isChecked());geometry.setChecked(True)
    QtTest.QTest.mouseClick(layout._favorites.tiles['DS'],QtCore.Qt.LeftButton);yield .2
    check('one-click favorite activates actual subtractive brush',state.get().active_zbrush_brush=='DamStandard' and state.brush().direction=='SUBTRACT')
    active_before=state.get().active_zbrush_brush
    key('LEFT_SHIFT',shift=True);yield .25
    check('Smooth held indicator does not replace selected brush','Smooth' in layout._left.mode.text() and state.get().active_zbrush_brush==active_before)
    key('LEFT_SHIFT','RELEASE');yield .25
    check('modifier release restores brush indicator','held' not in layout._left.mode.text())
    key('B');key('B','RELEASE');yield .2
    popup=sculpt_widgets._current_popup;check('native B opens thumbnail browser',popup is not None and popup.isVisible() and all(not b.icon().isNull() for b in popup.buttons.values()))
    if popup:
        positions={c:b.geometry().getRect() for c,b in popup.buttons.items()}
        QtTest.QTest.keyClick(popup,QtCore.Qt.Key_C);yield .1
        check('filter does not move brush tiles',positions=={c:b.geometry().getRect() for c,b in popup.buttons.items()})
        QtTest.QTest.keyClick(popup,QtCore.Qt.Key_B);yield .2
        check('B C B selects real ClayBuildup',state.get().active_zbrush_brush=='ClayBuildup' and state.get().alpha=='SQUARE')
    before=state.get().draw_size;key('SPACE');yield .3
    popup=sculpt_widgets._current_popup;check('Space opens momentary Quick Menu',popup.isVisible() and popup.objectName()=='SculptQuickMenu' and popup.momentary)
    popup.sliders['draw_size'].setValue(83);yield .1
    check('Quick Menu updates actual brush and header',state.brush().size==83 and shelf._shelf_instances[0].sculpt_header.fields['draw_size'].value()==83)
    key('SPACE','RELEASE');yield .2
    check('Space release commits and closes',not popup.isVisible() and state.brush().size==83)
    key('RIGHTMOUSE');key('RIGHTMOUSE','RELEASE');yield .2
    popup=sculpt_widgets._current_popup;check('RMB opens persistent quick controls',popup.isVisible() and not popup.momentary)
    mirror_before=bpy.context.view_layer.objects.active.use_mesh_mirror_x
    QtTest.QTest.mouseClick(popup.toggles['Sym X'],QtCore.Qt.LeftButton)
    popup.sliders['draw_size'].setValue(117);QtTest.QTest.keyClick(popup,QtCore.Qt.Key_Escape);yield .2
    check('Escape restores pre-popup settings',not popup.isVisible() and state.brush().size==83)
    check('Escape restores quick-menu symmetry',bpy.context.view_layer.objects.active.use_mesh_mirror_x==mirror_before)
    popup=sculpt_widgets.show_quick();popup.sliders['draw_size'].setValue(132)
    QtWidgets.QApplication.sendEvent(popup,QtCore.QEvent(QtCore.QEvent.WindowDeactivate));yield .2
    check('focus loss cancels parameter preview',not popup.isVisible() and state.brush().size==83)
    protected=bpy.context.view_layer.objects.active
    protected_points=[v.co.copy() for v in protected.active_shape_key.data]
    popup=sculpt_widgets.show_quick()
    QtTest.QTest.mouseClick(popup,QtCore.Qt.LeftButton,pos=QtCore.QPoint(-8,-8));yield .2
    check('outside dismissal closes without a sculpt stroke',not popup.isVisible() and all((v.co-co).length<1e-6 for v,co in zip(protected.active_shape_key.data,protected_points)))
    # First native stroke after a dismissed popup must target the original mesh.
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from mathutils import Vector
    with bpy.context.temp_override(**ctx()):
        brushes.select('ST');state.get().z_intensity=60;bpy.ops.ed.undo_push(message='First stroke after popup')
    yield .3
    body=bpy.context.view_layer.objects.active;before=[v.co.copy() for v in body.active_shape_key.data];base_before=[v.co.copy() for v in body.data.vertices]
    c=ctx();r=c['region'];p=location_3d_to_region_2d(r,c['area'].spaces.active.region_3d,body.matrix_world@Vector((-.35,-.8,.3)))
    xy=(int(r.x+p.x),int(r.y+p.y))
    from landfall_studio.sculpt import gestures
    with bpy.context.temp_override(**c):
        hit=gestures.raycast(bpy.context,(p.x,p.y));results['first_stroke']={'hit':hit['kind'],'brush':state.brush().name,'tool':c['window'].workspace.tools.from_space_view3d_mode('SCULPT',create=False).idname,'record':state.get().record_layer,'layer':body.active_shape_key_index,'mask_max':max(ops.mask_values(body))}
    c['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',x=xy[0],y=xy[1]);c['window'].event_simulate(type='LEFTMOUSE',value='PRESS',x=xy[0],y=xy[1]);yield .1
    for i in range(1,7):
        c['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',x=xy[0]+i*8,y=xy[1]);yield .06
    c['window'].event_simulate(type='LEFTMOUSE',value='RELEASE',x=xy[0]+48,y=xy[1]);yield .2
    results['first_stroke']['key_delta']=max((v.co-co).length for v,co in zip(body.active_shape_key.data,before))
    results['first_stroke']['mesh_delta']=max((v.co-co).length for v,co in zip(body.data.vertices,base_before))
    check('first native stroke after popup changes selected shape layer',any((v.co-co).length>1e-6 for v,co in zip(body.active_shape_key.data,before)) and bpy.context.view_layer.objects.active==body)
    results['first_stroke']['gestures']=list(gestures.history[-5:])
    results['first_stroke']['fallbacks']=[(config.name,i.active,i.value,i.ctrl,i.shift,i.alt) for config in (bpy.context.window_manager.keyconfigs.addon,bpy.context.window_manager.keyconfigs.user) for i in config.keymaps['3D View'].keymap_items if i.idname=='sculpt.brush_stroke']
    results['first_stroke']['strength']=state.brush().strength
    cancel_before=[v.co.copy() for v in body.active_shape_key.data]
    c['window'].event_simulate(type='LEFTMOUSE',value='PRESS',x=xy[0],y=xy[1]);yield .1
    c['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',x=xy[0]+30,y=xy[1]);yield .1
    c['window'].event_simulate(type='RIGHTMOUSE',value='PRESS',x=xy[0]+30,y=xy[1]);yield .1
    c['window'].event_simulate(type='RIGHTMOUSE',value='RELEASE',x=xy[0]+30,y=xy[1]);c['window'].event_simulate(type='LEFTMOUSE',value='RELEASE',x=xy[0]+30,y=xy[1]);yield .2
    check('RMB during stroke does not open quick controls',sculpt_widgets._current_popup is None)
    check('RMB stroke cancellation restores geometry',all((v.co-co).length<1e-6 for v,co in zip(body.active_shape_key.data,cancel_before)))
    key('TAB');key('TAB','RELEASE');yield .5
    check('Tab expands native canvas without leaving Sculpt',layout.focus and bpy.context.mode=='SCULPT' and len(ctx()['window'].screen.areas)==1 and not layout._left.root.isVisible())
    capture('sculpt_ux2_focus.png',hwnd)
    key('TAB');key('TAB','RELEASE');yield .7
    check('Tab restores shelves and Sculpt mode',not layout.focus and layout._left.root.isVisible() and bpy.context.mode=='SCULPT')
    state.get().bbrush_enabled=False;yield .3
    key('TAB');key('TAB','RELEASE');yield .3
    check('focus mode remains accessible with pen controls disabled',layout.focus and bpy.context.mode=='SCULPT',{'focus':layout.focus,'mode':bpy.context.mode,'tab':[(i.idname,i.active) for i in bpy.context.window_manager.keyconfigs.user.keymaps['Sculpt'].keymap_items if i.type=='TAB']})
    key('TAB');key('TAB','RELEASE');yield .3
    state.get().bbrush_enabled=True;yield .3
    maps=bpy.context.window_manager.keyconfigs.user.keymaps
    focus_rows=lambda name:[i for i in maps[name].keymap_items if i.idname=='landfall_studio.sculpt_shortcut' and i.properties.action=='FOCUS_UI' and i.active]
    check('focus shortcut retains its scoped input owner',len(focus_rows('Sculpt'))==1 and not focus_rows('Screen'))
    with bpy.context.temp_override(**ctx()):bpy.ops.landfall_studio.sculpt_shortcut(action='FOCUS_UI')
    check('native focus command returns before replacing its screen',not layout.focus and layout._focus_timer is not None)
    yield .2
    check('deferred focus resolves a live native viewport',layout.focus and len(ctx()['window'].screen.areas)==1)
    with bpy.context.temp_override(**ctx()):bpy.ops.landfall_studio.sculpt_shortcut(action='FOCUS_UI')
    yield .2
    check('deferred focus restores the original areas',not layout.focus and len(ctx()['window'].screen.areas)>1)
    a=layout._owners['left']._inner_dock.area;w=ctx()['window']
    w.event_simulate(type='TAB',value='PRESS',x=a.x+a.width//2,y=a.y+a.height//2)
    w.event_simulate(type='TAB',value='RELEASE',x=a.x+a.width//2,y=a.y+a.height//2);yield .2
    check('native non-viewport Tab does not enter canvas focus',not layout.focus)
    expected_areas=len(ctx()['window'].screen.areas)
    for iteration in range(12):
        key('TAB');key('TAB','RELEASE');yield .1
        entered=layout.focus and len(ctx()['window'].screen.areas)==1
        key('TAB');key('TAB','RELEASE');yield .15
        check('native focus stress cycle '+str(iteration+1),entered and not layout.focus and len(ctx()['window'].screen.areas)==expected_areas)
    # The browser retains the viewport which invoked it, not the first area.
    with bpy.context.temp_override(**ctx()):bpy.ops.screen.area_split(direction='VERTICAL',factor=.5)
    yield .3
    views=sorted((a for a in ctx()['window'].screen.areas if a.type=='VIEW_3D'),key=lambda a:a.x)
    second=views[-1];override={'window':ctx()['window'],'area':second,'region':next(r for r in second.regions if r.type=='WINDOW')}
    views[0].spaces.active.show_gizmo_object_translate=True
    with bpy.context.temp_override(**override):sculpt_widgets.set_origin();popup=sculpt_widgets.show_brush_palette()
    yield .2
    check('popup retains second viewport context',popup.context_override['area']==second)
    QtTest.QTest.keyClick(popup,QtCore.Qt.Key_C);QtTest.QTest.keyClick(popup,QtCore.Qt.Key_B);yield .2
    check('brush activation changes invoking viewport only',views[0].spaces.active.show_gizmo_object_translate and not second.spaces.active.show_gizmo_object_translate)
    import blendertk as btk
    btk.close_area(ctx()['window'],second);yield .3
    for width,height in ((1280,720),(1920,1080),(2560,1440)):
        ctypes.windll.user32.ShowWindow(hwnd,9);ctypes.windll.user32.SetWindowPos(hwnd,0,0,0,width,height,0x0040);yield .8
        capture(f'sculpt_ux2_native_{width}.png',hwnd)
        header=shelf._shelf_instances[0].sculpt_header
        check(f'essential controls fit {width}',all(w.mapTo(header.root,QtCore.QPoint()).x()+w.width()<=header.root.width()+1 for w in header.fields.values()),{'root':header.root.width(),'fields':[(k,w.mapTo(header.root,QtCore.QPoint()).x(),w.width()) for k,w in header.fields.items()]})
        check(f'parameter text is readable {width}',all(w.lineEdit().width()>=w.fontMetrics().horizontalAdvance(w.text())+6 for w in header.fields.values()),{k:w.lineEdit().width() for k,w in header.fields.items()})
    results['saved_layout']=[(n,w,h) for n,win,a,w,h,widget in layout._saved]
    pointer=QtGui.QCursor.pos()
    with bpy.context.temp_override(**ctx()):ops.layer('GOZ')
    yield .7
    results['resize_events']=layout.resize_events;results['pending_resizes']=len(layout._pending)
    check('mode return never warps OS pointer',QtGui.QCursor.pos()==pointer)
    check('GoZ restores Maya docks and exact shape target',not layout.active and desktop._right_dock.mode=='SHAPE_EDITOR' and bpy.context.view_layer.objects.active.active_shape_key.name=='Creature Form Pass')
    check('Tentacle original activation restored',tentacle_bridge._sculpt_suspended is None and tentacle_bridge.get_activation_key_info()['qt_key']==original_key)
    check('GoZ clears scoped focus input and pending requests',not focus_rows('Sculpt') and layout._focus_timer is None)
    modal=bpy.context.window_manager.keyconfigs.user.keymaps.get('Paint Stroke Modal')
    check('native paint cancellation map restored exactly',[(i.type,i.value,i.propvalue,i.active) for i in modal.keymap_items]==original_modal)
    check('Maya left and bottom widgets restored',desktop._get_left_outliner_dock()._inner_dock.widget.objectName()!='SculptBrushShelf' and __import__('landfall_studio.ui.time_slider',fromlist=['get_bottom_time_slider_dock']).get_bottom_time_slider_dock()._inner_dock.widget.objectName()!='SculptFavorites')
    left=desktop._get_left_outliner_dock()._inner_dock.area;top=desktop._get_top_shelf_dock()._inner_dock.area
    check('GoZ restores original Maya pane widths and shelf height',abs(left.width-original[left.as_pointer()][0])<=3 and abs(top.height-original[top.as_pointer()][1])<=3,{'left':left.width,'expected_left':original[left.as_pointer()][0],'top':top.height,'expected_top':original[top.as_pointer()][1]})
    capture('sculpt_ux2_maya_return.png',hwnd)
    # Record the original crash path without changing the acceptance behavior:
    # resolving a cached Channels panel during repeated handoffs must not need
    # another full theme teardown. Explicit theme changes use their own action.
    handler=desktop.ensure_ui_handler();apply_styles=handler.apply_styles;style_calls=[]
    def observe_style(widget,*args,**kwargs):
        style_calls.append(widget.objectName());return apply_styles(widget,*args,**kwargs)
    handler.apply_styles=observe_style
    for iteration in range(3):
        from landfall_studio import sculpt
        sculpt.enter();yield .4
        if iteration==0:
            key('TAB');key('TAB','RELEASE');yield .2
            check('GoZ recovery can begin inside fullscreen focus',layout.focus)
        elif iteration==1:
            with bpy.context.temp_override(**ctx()):bpy.ops.landfall_studio.sculpt_shortcut(action='FOCUS_UI')
        sculpt.return_to_maya(shape_editor=True);yield .4
        check('repeated handoff restores layout '+str(iteration+1),not layout.active and not layout.focus and layout._focus_timer is None and len(sculpt_widgets._widgets)==0 and desktop._right_dock.mode=='SHAPE_EDITOR')
    handler.apply_styles=apply_styles;results['handoff_theme_applications']=style_calls
    landfall_studio.unregister();save();bpy.ops.wm.quit_blender()
generator=None
def tick():
    try:return next(generator)
    except StopIteration:return None
    except Exception:
        results['failed'].append(traceback.format_exc());save();print(traceback.format_exc());bpy.ops.wm.quit_blender();return None
def start():
    global generator
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile();generator=suite();bpy.app.timers.register(tick,first_interval=.5,persistent=True)
bpy.app.timers.register(start,first_interval=.5)
