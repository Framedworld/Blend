"""Model Duplicate via real menus/keys with native history and generated geometry."""
import bpy,sys,os,json,ctypes,traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_INSTANCE_TAG','')
OUT=ROOT/('output/model_duplicate_gui'+TAG+'.json')
result={'ok':False,'passed':[],'failed':[],
        'boundary':'Factory scene; native simulated viewport keys and actual QtTest menu/key input; no physical input claim.'}

def save():OUT.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')

def check(label,value,detail=None):
    result['passed' if value else 'failed'].append(label if value else {'test':label,'detail':detail});save()

def view():
    window=bpy.context.window_manager.windows[0]
    area=max((a for a in window.screen.areas if a.type=='VIEW_3D'),key=lambda a:a.width*a.height)
    return dict(window=window,screen=window.screen,area=area,region=next(r for r in area.regions if r.type=='WINDOW'))

def evaluated(obj):
    bpy.context.view_layer.update();obj=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=obj.to_mesh()
    try:return [v.co.copy() for v in mesh.vertices]
    finally:obj.to_mesh_clear()

def same(a,b):return len(a)==len(b) and max(((x-y).length for x,y in zip(a,b)),default=0)<2e-5

def suite():
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
    import landfall_studio
    from landfall_studio import ui,sculpt,keymaps,commands
    from landfall_studio.ui import desktop,menus,attribute_editor,hotkey_passthrough
    from landfall_studio.sculpt import extended,ops
    from PySide6 import QtWidgets as W,QtCore as C,QtGui as G,QtTest as T
    landfall_studio.register();ui.restore_workspace_desktop(restore_script_output=False);yield .8
    from blendertk.ui_utils.blender_window import BlenderWindow
    app=W.QApplication.instance();hwnd=BlenderWindow.window_hwnd(view()['window'])
    result['dpr']=app.primaryScreen().devicePixelRatio()
    ctypes.windll.user32.ShowWindow(hwnd,3);yield .3
    def native(key,**mods):
        if app.focusWidget():app.focusWidget().clearFocus()
        app.setActiveWindow(None);BlenderWindow.set_keyboard_focus(hwnd)
        context=view();r=context['region'];kw=dict(x=r.x+r.width//2,y=r.y+r.height//2)
        context['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',**kw)
        for value in ('PRESS','RELEASE'):context['window'].event_simulate(type=key,value=value,**kw,**mods)
    desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
    editor=attribute_editor.ensure_attribute_editor_widget()
    with bpy.context.temp_override(**view()):
        obj=bpy.context.object;obj.name='Duplicate Original'
        obj.shape_key_add(name='Basis');obj.shape_key_add(name='Authored Form').data[0].co.z+=.2
        obj.vertex_groups.new(name='Skin preservation').add([0],.7,'REPLACE')
        before_uv=[tuple(loop.uv) for loop in obj.data.uv_layers.active.data]
        bpy.ops.ed.undo_push(message='Authored duplicate fixture')
    original_name=obj.name
    native('D',ctrl=True);yield .25
    copy=bpy.context.object;copy_name=copy.name
    check('native Maya Ctrl+D duplicates exactly once in place',copy_name!=original_name and len([o for o in bpy.data.objects if o.name.startswith('Duplicate Original')])==2 and copy.location==bpy.data.objects[original_name].location)
    check('regular Duplicate owns independent mesh and shape keys',copy.data!=bpy.data.objects[original_name].data and copy.data.shape_keys!=bpy.data.objects[original_name].data.shape_keys)
    check('Duplicate preserves authored UVs and skin weight',before_uv==[tuple(loop.uv) for loop in copy.data.uv_layers.active.data] and abs(copy.vertex_groups['Skin preservation'].weight(0)-.7)<1e-6)
    native('Z');yield .25
    check('one native Undo removes Ctrl+D copy',bpy.data.objects.get(copy_name) is None and bpy.data.objects.get(original_name) is not None)
    native('Z',shift=True);yield .25
    check('native Redo restores Ctrl+D copy',bpy.data.objects.get(copy_name) is not None)
    native('G');yield .25
    repeated=bpy.context.object.name
    check('G repeats Duplicate once',repeated!=copy_name and len([o for o in bpy.data.objects if o.name.startswith('Duplicate Original')])==3)
    native('Z');yield .25
    check('one Undo removes only repeated copy',bpy.data.objects.get(repeated) is None and bpy.data.objects.get(copy_name) is not None)
    # An actively edited value owns Ctrl+D rather than duplicating scene data.
    editor=attribute_editor.ensure_attribute_editor_widget();field=editor.spn_tx
    G.QCursor.setPos(field.mapToGlobal(field.rect().center()))
    app.setActiveWindow(field.window());field.window().activateWindow();yield .15
    field.setFocus(C.Qt.MouseFocusReason)
    T.QTest.mouseClick(field.lineEdit(),C.Qt.LeftButton);yield .15
    check('numeric input owns actual Qt text focus',hotkey_passthrough.is_editable_text_widget(field.lineEdit()),
          {'focus':str(app.focusWidget()),'enabled':field.isEnabled(),'visible':field.isVisible(),'readonly':field.isReadOnly()})
    class TextTrace(C.QObject):
        def eventFilter(self,widget,event):
            if event.type()==C.QEvent.KeyPress and event.key()==C.Qt.Key_D:
                result.setdefault('text_key_trace',[]).append({'widget':str(widget),'focus':str(app.focusWidget()),
                    'editable':hotkey_passthrough.is_editable_text_widget(widget),'event':id(event)})
            return False
    trace=TextTrace();app.installEventFilter(trace)
    prior=len(bpy.data.objects);T.QTest.keyClick(field.lineEdit(),C.Qt.Key_D,C.Qt.ControlModifier);yield .2
    app.removeEventFilter(trace)
    result['text_key_passthrough']=hotkey_passthrough.get_passthrough_history()
    check('Ctrl+D in editable text preserves scene',len(bpy.data.objects)==prior,hotkey_passthrough.get_last_passthrough_event())
    for key,mod,label in ((C.Qt.Key_G,C.Qt.NoModifier,'Repeat'),
                          (C.Qt.Key_Z,C.Qt.ControlModifier,'Undo'),
                          (C.Qt.Key_Z,C.Qt.ControlModifier|C.Qt.ShiftModifier,'Redo')):
        before_names=set(bpy.data.objects.keys())
        T.QTest.keyClick(field.lineEdit(),key,mod);yield .15
        check(label+' in numeric input preserves scene objects',set(bpy.data.objects.keys())==before_names,hotkey_passthrough.get_last_passthrough_event())
    # Focus a real, non-text control for the global Qt shortcut route.
    menu=W.QMenu();menus.build_qmenu(menu,menus.EDIT_MENU)
    menu.setProperty('landfallStudioUi',True)
    button=W.QPushButton('Shortcut input target',editor.widget)
    button.show();app.setActiveWindow(button.window());button.window().activateWindow();yield .15
    prior=len(bpy.data.objects)
    button.setFocus();T.QTest.keyClick(button,C.Qt.Key_D,C.Qt.ControlModifier);yield .25
    qt_copy=bpy.context.object.name
    check('Qt Ctrl+D creates exactly one copy',len(bpy.data.objects)==prior+1 and qt_copy!=copy_name,hotkey_passthrough.get_last_passthrough_event())
    native('Z');yield .25
    check('Qt Ctrl+D has one native Undo step',bpy.data.objects.get(qt_copy) is None)
    for route in ('Qt G','Edit Repeat Last'):
        prior=len(bpy.data.objects)
        if route=='Qt G':
            app.setActiveWindow(button.window());button.window().activateWindow();yield .15
            button.setFocus();T.QTest.keyClick(button,C.Qt.Key_G)
        else:
            action=next(a for a in menu.actions() if a.text().split('\t')[0]=='Repeat Last')
            menu.popup(C.QPoint(400,300));yield .15
            T.QTest.mouseClick(menu,C.Qt.LeftButton,pos=menu.actionGeometry(action).center())
        yield .25
        repeated=bpy.context.object.name
        check(route+' repeats Duplicate exactly once',len(bpy.data.objects)==prior+1)
        native('Z');yield .25
        check(route+' has one native Undo step',bpy.data.objects.get(repeated) is None and bpy.data.objects.get(copy_name) is not None)
    for section in ('ArrayMesh','NanoMesh'):
        with bpy.context.temp_override(**view()):
            bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_cube_add();original=bpy.context.object
            original.name='Model '+section
            if section=='NanoMesh':
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.4);source=bpy.context.object
                source.select_set(False);original.select_set(True);bpy.context.view_layer.objects.active=original
                extended.option(section,'source',source.name)
            extended.option(section,'enabled',True)
            bpy.ops.ed.undo_push(message=section+' model fixture')
        base=evaluated(original);name=original.name
        for linked,label in ((False,'Duplicate'),(True,'Duplicate Instance')):
            with bpy.context.temp_override(**view()):
                bpy.ops.object.select_all(action='DESELECT');original=bpy.data.objects[name]
                original.select_set(True);bpy.context.view_layer.objects.active=original
            action=next(a for a in menu.actions() if a.text().split('\t')[0]==label)
            menu.popup(C.QPoint(400,300));yield .15
            T.QTest.mouseClick(menu,C.Qt.LeftButton,pos=menu.actionGeometry(action).center());yield .25
            original=bpy.data.objects[name]
            copy=bpy.context.object;copy_name=copy.name
            helpers=[o.name for o in bpy.data.objects if o.get('_lf_instance_helper') and o.parent==copy]
            check(section+' actual Edit '+label+' selects one in-place copy',copy_name!=name and copy.location==original.location and same(base,evaluated(copy)))
            check(section+' '+label+' has correct mesh sharing',(copy.data==original.data)==linked,
                  {'copy_mesh':copy.data.name,'original_mesh':original.data.name,'command':commands.get_last_command()})
            check(section+' '+label+' owns generated helper IDs',bool(helpers))
            # Native inspector transforms are already covered in the companion
            # scenario; this direct transform isolates copy/helper data safety.
            copy.location=(5,-3,2);copy.rotation_euler=(.2,.3,.5)
            check(section+' '+label+' follows copied object independently',same(base,evaluated(copy)) and same(base,evaluated(original)))
            native('Z');yield .25
            check(section+' '+label+' one Undo removes copy and helper IDs',bpy.data.objects.get(copy_name) is None and all(bpy.data.objects.get(n) is None for n in helpers))
            native('Z',shift=True);yield .25
            check(section+' '+label+' Redo restores independent geometry',bpy.data.objects.get(copy_name) is not None and same(base,evaluated(bpy.data.objects[copy_name])) )
    # Same Ctrl+D remains Divide while Sculpt Studio owns input.
    with bpy.context.temp_override(**view()):sculpt.enter()
    yield .4
    panel=desktop._right_dock._ensure_host_container().sculpt_panel
    target=panel.buttons['Divide'];panel.root.ensureWidgetVisible(target);yield .15
    app.setActiveWindow(target.window());target.window().activateWindow();yield .15
    target.setFocus();before={o.name for o in ops.meshes()};active_name=ops.active().name
    T.QTest.keyClick(target,C.Qt.Key_D,C.Qt.ControlModifier);yield .4
    check('Sculpt Qt Ctrl+D retains Divide and creates no duplicate',ops.multires() is not None and ops.multires().total_levels==1 and {o.name for o in ops.meshes()}==before and ops.active().name==active_name,hotkey_passthrough.get_last_passthrough_event())
    with bpy.context.temp_override(**view()):sculpt.return_to_maya()
    yield .3
    keymaps.apply_profile(bpy.context,'HYBRID');yield .2
    check('Hybrid profile removes Maya Ctrl+D binding',not any(item.idname=='landfall_studio.duplicate_objects' for km in bpy.context.window_manager.keyconfigs.addon.keymaps for item in km.keymap_items))
    keymaps.apply_profile(bpy.context,'MAYA');yield .2
    check('Maya profile restores one Ctrl+D owner',sum(item.idname=='landfall_studio.duplicate_objects' and item.type=='D' and item.ctrl for km in bpy.context.window_manager.keyconfigs.addon.keymaps for item in km.keymap_items)==1)
    menu.close();button.deleteLater();result['ok']=not result['failed'];save()
    landfall_studio.unregister();bpy.ops.wm.quit_blender()

steps=suite()
def tick():
    try:return next(steps)
    except StopIteration:return None
    except Exception:
        result['failed'].append({'exception':traceback.format_exc()});save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
