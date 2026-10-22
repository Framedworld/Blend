"""Native Qt reference tray actions, undo and actual QWidget captures."""
import bpy,json,sys,traceback,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_REFERENCE_TAG','')
OUT=ROOT/('output/sculpt_reference_gui'+TAG+'.json');CAP=ROOT/('output/sculpt-reference'+TAG);CAP.mkdir(exist_ok=True)
result={'passed':[],'failed':[],'captures':[],'input':'Native Blender + PySide6 QtTest; QWidget captures, not a browser mockup'}
def save():OUT.write_text(json.dumps(result,indent=2,default=str))
def check(name,value,detail=None):result['passed' if value else 'failed'].append(name if value else {'test':name,'detail':detail});save()
def ctx():
    from landfall_studio.sculpt import ops
    return ops.view_context()
def key(name,**mods):
    c=ctx();r=c['region']
    for flag,kind in (('ctrl','LEFT_CTRL'),('shift','LEFT_SHIFT'),('alt','LEFT_ALT')):
        if mods.get(flag):c['window'].event_simulate(type=kind,value='PRESS',x=r.x+r.width//2,y=r.y+r.height//2,**mods)
    for value in ('PRESS','RELEASE'):c['window'].event_simulate(type=name,value=value,x=r.x+r.width//2,y=r.y+r.height//2,**mods)
    for flag,kind in (('ctrl','LEFT_CTRL'),('shift','LEFT_SHIFT'),('alt','LEFT_ALT')):
        if mods.get(flag):c['window'].event_simulate(type=kind,value='RELEASE',x=r.x+r.width//2,y=r.y+r.height//2)

def suite():
    import landfall_studio
    from landfall_studio import ui,sculpt
    from landfall_studio.sculpt import ops,state,extended,instances,preferences,layout
    from landfall_studio.sculpt.demo import create_demo
    from landfall_studio.ui import desktop,zbrush_panel
    preferences.PATH=ROOT.parent/('.test_env/reference_gui_preferences_'+str(os.getpid())+'.json');preferences._data=None
    landfall_studio.register();yield .5
    ui.restore_workspace_desktop(restore_script_output=False);yield .5
    from PySide6 import QtCore,QtGui,QtWidgets,QtTest
    from blendertk.ui_utils.blender_window import BlenderWindow
    import ctypes
    with bpy.context.temp_override(**ctx()):create_demo()
    yield 1
    hwnd=BlenderWindow.window_hwnd(ctx()['window'])
    for _ in range(10):
        if hwnd:break
        yield .2;hwnd=BlenderWindow.window_hwnd(ctx()['window'])
    if not hwnd:raise RuntimeError('Native window unavailable after startup settles')
    ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd);yield .3
    panel=desktop._right_dock._ensure_host_container().sculpt_panel
    result['qt_dpr']=panel.root.devicePixelRatioF()
    names=['SubTool','Geometry','ArrayMesh','NanoMesh','Layers','Deformation','Masking','PolyGroups','Morph Target','Polypaint']
    check('all ten reference palettes exist',all(name in panel.palettes for name in names))
    excluded={'Bevel Pro','Align','Distribute','Remesh','Project BasRelief','ShadowBox','Tessimate','Position','MeshIntegrity'}
    check('crossed out reference sections are excluded',not any(g.title() in excluded for g in panel.content.findChildren(QtWidgets.QGroupBox)))
    check('active tray is native PySide6',type(panel.root).__module__.startswith('PySide6'))
    check('Geometry is default expanded tool palette',panel.palettes['Geometry'].isChecked())
    check('SDiv value editor is readable',panel.content.findChild(QtWidgets.QDoubleSpinBox,'SculptValue_SDIV_level').lineEdit().width()>20)
    check('unset NanoMesh source shows an explicit choice',panel.nano_source.currentIndex()==-1 and bool(panel.nano_source.placeholderText()))
    panel.palettes['NanoMesh'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['NanoMesh On']);yield .1
    QtTest.QTest.mouseClick(panel.buttons['NanoMesh On'],QtCore.Qt.LeftButton);yield .1
    check('missing source rejects NanoMesh enable without stale toggle',not ops.last_result.get('ok') and not instances.config('NanoMesh')['enabled'] and not panel.buttons['NanoMesh On'].isChecked())
    for name in names:
        group=panel.palettes[name]
        if group.isCheckable():group.setChecked(True)
        panel.root.ensureWidgetVisible(group);yield .12
        check(name+' opens visible native controls',group.isVisible() and group.height()>30)
        path=CAP/(name.replace(' ','-')+'.png');group.grab().save(str(path));result['captures'].append(str(path))
        viewport=panel.root.viewport()
        check(name+' fits tray width',group.width()<=viewport.width()+2,{'group':group.width(),'viewport':viewport.width()})
    panel.palettes['Geometry'].setChecked(True);panel.root.verticalScrollBar().setValue(0);yield .2
    path=CAP/'default-tray.png';panel.root.grab().save(str(path));result['captures'].append(str(path))
    result['window_sizes']=[]
    for width,height in ((1280,720),(1920,1080),(2560,1440)):
        ctypes.windll.user32.ShowWindow(hwnd,9);ctypes.windll.user32.SetWindowPos(hwnd,0,0,0,width,height,0x0040);yield 1
        if layout._drawer_collapsed:
            check('narrow window exposes drawer '+str(width),layout._drawer.isVisible())
            layout.toggle_tray();yield .5
        root=panel.root;rect=ctypes.wintypes.RECT();ctypes.windll.user32.GetWindowRect(hwnd,ctypes.byref(rect))
        result['window_sizes'].append({'requested':[width,height],'actual':[rect.right-rect.left,rect.bottom-rect.top],'tray':[root.width(),root.height()],'dpr':root.devicePixelRatioF()})
        check('native tray fits window '+str(width),root.isVisible() and root.horizontalScrollBar().maximum()==0 and panel.palettes['Geometry'].width()<=root.viewport().width()+2,result['window_sizes'][-1])
        root.grab().save(str(CAP/('tray-'+str(width)+'.png')))
        layout.auto_tray();yield .2
    ctypes.windll.user32.ShowWindow(hwnd,3);yield .3
    # Real button dispatch through the existing undoable operator.
    o=ops.active();name=o.name
    panel.palettes['Morph Target'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['StoreMT']);yield .1
    QtTest.QTest.mouseClick(panel.buttons['StoreMT'],QtCore.Qt.LeftButton);yield .1
    check('StoreMT Qt click stores actual point attribute',ops.active().data.attributes.get('sculpt_morph_target') is not None)
    # Use a clean base mesh for native transform undo and generated arrays.
    with bpy.context.temp_override(**ctx()):
        bpy.ops.object.mode_set(mode='OBJECT');bpy.ops.mesh.primitive_cube_add();fixture=bpy.context.object;fixture.name='Reference UI Fixture';bpy.ops.object.mode_set(mode='SCULPT');bpy.ops.ed.undo_push(message='Reference GUI baseline')
    yield .3
    panel.palettes['Masking'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['Mask All']);yield .1
    QtTest.QTest.mouseClick(panel.buttons['Mask All'],QtCore.Qt.LeftButton);yield .1
    check('MaskAll Qt click changes native mask',min(ops.mask_values())>.99)
    QtTest.QTest.mouseClick(panel.buttons['Clear'],QtCore.Qt.LeftButton);yield .1
    check('Clear Qt click clears native mask',max(ops.mask_values())<.001)
    panel.palettes['PolyGroups'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['Auto Groups']);yield .1
    QtTest.QTest.mouseClick(panel.buttons['Auto Groups'],QtCore.Qt.LeftButton);yield .1
    check('Auto Groups Qt click creates native Face Sets',ops.active().data.attributes.get('.sculpt_face_set') is not None)
    panel.palettes['Deformation'].setChecked(True)
    slider=panel.content.findChild(QtWidgets.QSlider,'SculptOption_DEFORM_ACTION_OFFSET');panel.root.ensureWidgetVisible(slider);yield .1
    before=[tuple(v.co) for v in ops.active().data.vertices]
    slider.setValue(30);slider.sliderReleased.emit();yield .2
    check('deformation slider changes actual mesh',before!=[tuple(v.co) for v in ops.active().data.vertices])
    c=ctx();r=c['region'];origin=BlenderWindow.client_origin(hwnd)
    ctypes.windll.user32.SetCursorPos(origin[0]+r.x+r.width//2,origin[1]+c['window'].height-1-r.y-r.height//2)
    ctypes.windll.user32.SetForegroundWindow(hwnd);BlenderWindow.set_keyboard_focus(hwnd)
    c['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',x=r.x+r.width//2,y=r.y+r.height//2);yield .1
    # Test the actual sidebar keyboard route here. Native viewport Ctrl+Z/Redo
    # is separately exercised by the unchanged 93-check sculpt GUI regression.
    panel.root.setFocus()
    QtTest.QTest.keyClick(panel.root,QtCore.Qt.Key_Z,QtCore.Qt.ControlModifier);yield .2
    result['z_bindings']=[(km.name,k.idname,k.active,k.ctrl,k.shift,k.alt) for km in bpy.context.window_manager.keyconfigs.user.keymaps for k in km.keymap_items if k.type=='Z' and k.ctrl]
    fixture=bpy.data.objects.get('Reference UI Fixture')
    undone=bool(fixture and before==[tuple(v.co) for v in fixture.data.vertices])
    result['undo_observation']={'mode':bpy.context.mode,'focus':BlenderWindow.keyboard_focus(),'hwnd':hwnd,'before':before,'after':[tuple(v.co) for v in fixture.data.vertices] if fixture else None,'operator':bpy.context.active_operator.bl_idname if bpy.context.active_operator else None}
    check('sidebar Ctrl Z restores full slider action once',undone,result['undo_observation'])
    if not undone:
        with bpy.context.temp_override(**ctx()):bpy.ops.ed.undo()
        fixture=bpy.data.objects.get('Reference UI Fixture')
        result['undo_observation']['direct_after']=[tuple(v.co) for v in fixture.data.vertices] if fixture else None
    def sidebar_undo(redo=False):
        panel.root.setFocus();QtTest.QTest.keyClick(panel.root,QtCore.Qt.Key_Z,QtCore.Qt.ControlModifier|(QtCore.Qt.ShiftModifier if redo else QtCore.Qt.NoModifier))
    # Real generated mask, Face Set, color and Morph edits must share native Undo.
    panel.palettes['Masking'].setChecked(True)
    group=next(g for g in panel.content.findChildren(QtWidgets.QGroupBox) if g.title()=='Mask By Depth');group.setChecked(True)
    panel.root.ensureWidgetVisible(panel.buttons['Mask By Depth']);yield .1
    previous_mask=ops.mask_values();QtTest.QTest.mouseClick(panel.buttons['Mask By Depth'],QtCore.Qt.LeftButton);yield .1
    check('generated depth mask has nonuniform actual values',max(ops.mask_values())-min(ops.mask_values())>.5)
    sidebar_undo();yield .15
    check('generated mask Undo restores previous values',ops.mask_values()==previous_mask)
    panel.palettes['PolyGroups'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['Groups By Normals']);yield .1
    previous_groups=extended.face_values(ops.active());QtTest.QTest.mouseClick(panel.buttons['Groups By Normals'],QtCore.Qt.LeftButton);yield .1
    check('normal angle grouping creates distinct real Face Sets',len(set(extended.face_values(ops.active())))>1)
    sidebar_undo();yield .15
    check('custom Face Set grouping Undo restores previous groups',extended.face_values(ops.active())==previous_groups)
    panel.palettes['Polypaint'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['Fill Color']);yield .1
    state.brush().color=(.2,.6,.3);old_colors=extended.vertex_colors(ops.active())
    QtTest.QTest.mouseClick(panel.buttons['Fill Color'],QtCore.Qt.LeftButton);yield .15
    check('Polypaint fill writes actual vertex colors',extended.vertex_colors(ops.active())!=old_colors)
    sidebar_undo();yield .15
    check('Polypaint fill Undo restores previous colors',all(max(abs(a-b) for a,b in zip(c,d))<1e-5 for c,d in zip(extended.vertex_colors(ops.active()),old_colors)))
    panel.palettes['Morph Target'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['StoreMT']);yield .1
    QtTest.QTest.mouseClick(panel.buttons['StoreMT'],QtCore.Qt.LeftButton);yield .1
    zbrush_panel.command('PALETTE',section='Deformation',kind='OFFSET',amount=.3,axes='X');yield .1
    morph_before=[tuple(v.co) for v in ops.active().data.vertices]
    mslider=panel.content.findChild(QtWidgets.QSlider,'SculptOption_MORPH_ACTION_MORPH');mslider.setValue(50);mslider.sliderReleased.emit();yield .1
    check('Morph slider changes stored-target geometry',morph_before!=[tuple(v.co) for v in ops.active().data.vertices])
    sidebar_undo();yield .15
    check('Morph Undo restores pre-blend geometry',morph_before==[tuple(v.co) for v in ops.active().data.vertices])
    panel.palettes['ArrayMesh'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['Array Mesh']);yield .1
    QtTest.QTest.mouseClick(panel.buttons['Array Mesh'],QtCore.Qt.LeftButton);yield .2
    check('Array Mesh Qt toggle enables real Array modifier',any(m.type=='ARRAY' and m.show_viewport for m in ops.active().modifiers))
    array_before=[tuple(v.co) for v in ops.active().data.vertices]
    sidebar_undo();yield .15
    check('Array toggle Undo restores prior modifier state',not any(m.type=='ARRAY' and m.show_viewport for m in ops.active().modifiers),{'modifiers':[(m.name,m.show_viewport) for m in ops.active().modifiers],'config':instances.config('ArrayMesh')})
    check('modifier Undo retains sculpt geometry and mode',bpy.context.mode=='SCULPT' and array_before==[tuple(v.co) for v in ops.active().data.vertices])
    sidebar_undo(True);yield .15
    check('Array toggle Redo restores generated preview',any(m.type=='ARRAY' and m.show_viewport for m in ops.active().modifiers))
    panel.palettes['NanoMesh'].setChecked(True);panel.root.ensureWidgetVisible(panel.nano_source);yield .1
    source=next(o.name for o in ops.meshes() if o!=ops.active() and o.name.startswith('Horn'))
    panel.nano_source.setCurrentIndex(panel.nano_source.findText(source));yield .1
    check('NanoMesh Qt source choice updates actual configuration',instances.config('NanoMesh')['source']==source)
    panel.root.ensureWidgetVisible(panel.buttons['NanoMesh On']);QtTest.QTest.mouseClick(panel.buttons['NanoMesh On'],QtCore.Qt.LeftButton);yield .2
    check('NanoMesh Qt toggle creates actual Geometry Nodes preview',any(m.type=='NODES' and m.name.startswith('Sculpt NanoMesh') and m.show_viewport for m in ops.active().modifiers))
    sidebar_undo();yield .15
    check('NanoMesh toggle Undo disables generated instances',not any(m.name.startswith('Sculpt NanoMesh') and m.show_viewport for m in ops.active().modifiers))
    panel.palettes['Layers'].setChecked(True);panel.root.ensureWidgetVisible(panel.buttons['+ New Layer']);yield .1
    QtTest.QTest.mouseClick(panel.buttons['+ New Layer'],QtCore.Qt.LeftButton);yield .2
    check('Layers New creates actual recording shape layer',ops.active().active_shape_key_index>0 and state.get().record_layer)
    check('unavailable BPR action is explained and disabled',not panel.buttons['Convert BPR To Geo'].isEnabled() and bool(panel.buttons['Convert BPR To Geo'].toolTip()))
    check('no horizontal tray scrolling',panel.root.horizontalScrollBar().maximum()==0)
    sculpt.return_to_maya();yield .3
    check('reference UI returns to original Maya dock',desktop._right_dock.mode!='ZBRUSH_STUDIO')
    result['ok']=not result['failed'];save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
    try:return next(steps)
    except StopIteration:return None
    except Exception:
        result['failed'].append({'exception':traceback.format_exc()});result['ok']=False;save();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
