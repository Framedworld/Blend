"""Actual tray/AE/history input around generated assets; disposable GUI only."""
import ctypes
import json
import os
from pathlib import Path
import sys
import traceback

import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_INSTANCE_TAG','')
OUT=ROOT/('output/instance_transform_gui'+TAG+'.json')
result={'ok':False,'passed':[],'failed':[],'observations':{},
        'input':'Native PySide6 QtTest and Blender events; procedural fixture setup and explicit mode transitions'}


def save():OUT.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')


def check(name,value,detail=None):
    result['passed' if value else 'failed'].append(name if value else {'test':name,'detail':detail})
    save()


def view():
    from landfall_studio.sculpt.ops import view_context
    candidate=view_context()
    window=candidate['window']
    area=max((a for a in window.screen.areas if a.type=='VIEW_3D'),key=lambda a:a.width*a.height)
    if candidate['area']!=area:
        route={'candidate':[candidate['area'].x,candidate['area'].y,candidate['area'].width,candidate['area'].height],
               'canvas':[area.x,area.y,area.width,area.height]}
        if route not in result.setdefault('context_routes',[]):result['context_routes'].append(route)
    return {'window':window,'screen':window.screen,'area':area,'region':next(r for r in area.regions if r.type=='WINDOW')}


def surface(obj):
    bpy.context.view_layer.update()
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    try:return [tuple(v.co) for v in mesh.vertices]
    finally:evaluated.to_mesh_clear()


def same(before,after,label):
    delta=max((sum((a[i]-b[i])**2 for i in range(3))**.5 for a,b in zip(before,after)),default=0)
    result['observations'][label]={'vertices':len(after),'max_local_delta':delta}
    return len(before)==len(after) and delta<2e-5


def suite():
    # Match the native interaction fixtures: a factory first-launch splash can
    # otherwise consume viewport keys while docked Qt controls still respond.
    bpy.context.preferences.view.show_splash=False
    bpy.ops.wm.read_homefile()
    import landfall_studio
    from landfall_studio import ui,sculpt
    from landfall_studio.sculpt import ops
    from landfall_studio.ui import desktop,attribute_editor,zbrush_panel
    landfall_studio.register();yield .5
    ui.restore_workspace_desktop(restore_script_output=False);yield .7
    from PySide6 import QtWidgets as W,QtCore as C,QtGui as G,QtTest as T
    from blendertk.ui_utils.blender_window import BlenderWindow
    app=W.QApplication.instance()
    hwnd=BlenderWindow.window_hwnd(view()['window'])
    result['initial_native_window']=hwnd
    for _ in range(20):
        if hwnd:break
        yield .1
        hwnd=BlenderWindow.window_hwnd(view()['window'])
    if not hwnd:raise RuntimeError('Native test window did not resolve after layout settled')
    result['native_window']=hwnd
    ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd)
    yield .3
    result['dpr']=app.primaryScreen().devicePixelRatio()

    def history_observer(*_):
        result.setdefault('native_history_events',[]).append({
            'mode':bpy.context.mode,
            'assets':{o.name:list(o.location) for o in bpy.data.objects if o.name.startswith('GUI ') and o.type=='MESH'},
            'operators':[o.bl_idname for o in bpy.context.window_manager.operators][-8:]})
    bpy.app.handlers.undo_post.append(history_observer)
    bpy.app.handlers.redo_post.append(history_observer)

    def type_value(field,value):
        app.setActiveWindow(field.window());field.window().activateWindow()
        field.setFocus(C.Qt.MouseFocusReason)
        G.QCursor.setPos(field.mapToGlobal(field.rect().center()))
        field.lineEdit().selectAll();T.QTest.keyClicks(field.lineEdit(),str(value))
        T.QTest.keyClick(field.lineEdit(),C.Qt.Key_Return)

    def history(redo=False):
        if os.environ.get('LANDFALL_INSTANCE_DIRECT_HISTORY'):
            with bpy.context.temp_override(**view()):
                status=bpy.ops.ed.redo() if redo else bpy.ops.ed.undo()
            result.setdefault('direct_history',[]).append({'redo':redo,'status':str(status)})
            return
        focused=app.focusWidget()
        if focused:focused.clearFocus()
        app.setActiveWindow(None)
        context=view();region=context['region'];window=context['window']
        result.setdefault('keymap_history',[]).append({
            'redo':redo,'mode':bpy.context.mode,
            'modal_operators':[op.bl_idname for op in window.modal_operators],
            'undo_poll':bpy.ops.ed.undo.poll(),
            'qt_popup':str(app.activePopupWidget()),'qt_modal':str(app.activeModalWidget()),
            'bindings':[(config.name,km.name,item.idname,item.active,item.ctrl,item.shift,item.alt)
                        for config in (bpy.context.window_manager.keyconfigs.addon,bpy.context.window_manager.keyconfigs.user)
                        for km in config.keymaps if km.name in ('3D View','Object Mode')
                        for item in km.keymap_items if item.type=='Z'],
            'physical_modifiers':{str(code):bool(ctypes.windll.user32.GetAsyncKeyState(code)&0x8000) for code in (16,17,18)}})
        origin=BlenderWindow.client_origin(hwnd)
        ctypes.windll.user32.SetCursorPos(origin[0]+region.x+region.width//2,
                                         origin[1]+window.height-1-region.y-region.height//2)
        user32=ctypes.windll.user32
        user32.GetForegroundWindow.restype=ctypes.c_void_p
        foreground_thread=user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),None)
        test_thread=ctypes.windll.kernel32.GetCurrentThreadId()
        attached=bool(foreground_thread and foreground_thread!=test_thread and
                      user32.AttachThreadInput(test_thread,foreground_thread,True))
        try:
            user32.BringWindowToTop(ctypes.c_void_p(hwnd))
            user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
        finally:
            if attached:user32.AttachThreadInput(test_thread,foreground_thread,False)
        BlenderWindow.set_keyboard_focus(hwnd)
        yield .15  # Drain native activation before keyboard input follows it.
        window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=region.x+region.width//2,y=region.y+region.height//2)
        yield .05
        BlenderWindow.set_keyboard_focus(hwnd)
        if os.environ.get('LANDFALL_INSTANCE_WINDOWS_HISTORY'):
            user32=ctypes.windll.user32
            user32.GetForegroundWindow.restype=ctypes.c_void_p
            pid=ctypes.c_ulong()
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd),ctypes.byref(pid))
            result.setdefault('native_focus',[]).append({'expected_pid':os.getpid(),'target_pid':pid.value,
                                                        'target':hwnd,'foreground':user32.GetForegroundWindow(),
                                                        'keyboard_focus':user32.GetFocus()})
            if pid.value!=os.getpid() or user32.GetForegroundWindow()!=hwnd or user32.GetFocus()!=hwnd:
                raise RuntimeError('Refusing keyboard input outside this owned foreground test window')
            result['input']='Native QtTest controls and foreground/PID-guarded Win32 keyboard; synthetic input'
            if redo:user32.keybd_event(0x10,user32.MapVirtualKeyW(0x10,0),0,0)
            try:
                scan=user32.MapVirtualKeyW(0x5A,0)
                user32.keybd_event(0x5A,scan,0,0)
                yield .08
                user32.keybd_event(0x5A,scan,2,0)
            finally:
                if redo:user32.keybd_event(0x10,user32.MapVirtualKeyW(0x10,0),2,0)
            return
        for value in ('PRESS','RELEASE'):
            window.event_simulate(type='Z',value=value,shift=redo,x=region.x+region.width//2,y=region.y+region.height//2)

    saved={}
    for section,button in (('ArrayMesh','Array Mesh'),('NanoMesh','NanoMesh On')):
        with bpy.context.temp_override(**view()):
            if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.mesh.primitive_cube_add();original=bpy.context.object
            original.name='GUI '+section
            name=original.name
            if section=='NanoMesh':
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.4)
                source=bpy.context.object;source.name='GUI Nano Source';source.select_set(False)
                original.select_set(True);bpy.context.view_layer.objects.active=original
            sculpt.enter()
        yield .4
        panel=desktop._right_dock._ensure_host_container().sculpt_panel
        panel.palettes[section].setChecked(True)
        if section=='NanoMesh':panel.nano_source.setCurrentText(source.name)
        panel.root.ensureWidgetVisible(panel.buttons[button]);yield .15
        T.QTest.mouseClick(panel.buttons[button],C.Qt.LeftButton);yield .2
        expected=surface(bpy.data.objects[name])
        check(section+' tray enable generates actual geometry',len(expected)>8 and ops.last_result.get('ok'))
        return_button=next(header.buttons['Return'] for header in zbrush_panel._headers if header.root.isVisible())
        T.QTest.mouseClick(return_button,C.Qt.LeftButton);yield .4
        desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
        editor=attribute_editor.ensure_attribute_editor_widget()
        type_value(editor.spn_tx,4);yield .2
        check(section+' typed model move retains local generated shape',abs(bpy.data.objects[name].location.x-4)<1e-5 and same(expected,surface(bpy.data.objects[name]),section+' typed translate'))
        yield from history();yield .3
        check(section+' native Undo restores transform and generated shape',abs(bpy.data.objects[name].location.x)<1e-5 and same(expected,surface(bpy.data.objects[name]),section+' Undo'),{'translate_x':bpy.data.objects[name].location.x,'mode':bpy.context.mode})
        check(section+' first model Undo retains modeling workspace',bpy.context.mode=='OBJECT' and not sculpt.is_engaged() and desktop._right_dock.mode=='ATTRIBUTE_EDITOR',
              {'mode':bpy.context.mode,'engaged':sculpt.is_engaged(),'right_dock':desktop._right_dock.mode})
        yield from history(True);yield .3
        check(section+' native Redo restores transform and generated shape',abs(bpy.data.objects[name].location.x-4)<1e-5 and same(expected,surface(bpy.data.objects[name]),section+' Redo'))
        yield from history();yield .2
        yield from history();yield .3
        # Studio engages its Sculpt workspace asynchronously after the native
        # mode returns (within a few timer ticks); wait for it, bounded.
        for _ in range(10):
            if bpy.context.mode=='SCULPT' and sculpt.is_engaged():break
            yield .1
        boundary_state={'mode':bpy.context.mode,'engaged':sculpt.is_engaged(),'same':same(expected,surface(bpy.data.objects[name]),section+' boundary Undo'),
                        'translate_x':bpy.data.objects[name].location.x}
        check(section+' undoing explicit GoZ boundary restores Sculpt without losing generated data',boundary_state['mode']=='SCULPT' and boundary_state['engaged'] and boundary_state['same'],boundary_state)
        yield from history(True);yield .3
        check(section+' redoing explicit GoZ boundary restores Modeling',bpy.context.mode=='OBJECT' and not sculpt.is_engaged() and abs(bpy.data.objects[name].location.x)<1e-5)
        yield from history(True);yield .25
        check(section+' Redo after mode-boundary cycle restores model edit',bpy.context.mode=='OBJECT' and abs(bpy.data.objects[name].location.x-4)<1e-5)
        type_value(editor.spn_rz,35);yield .15
        type_value(editor.spn_sx,1.5);yield .2
        check(section+' typed rotation and scale retain generated shape',same(expected,surface(bpy.data.objects[name]),section+' rotate scale'))
        with bpy.context.temp_override(**view()):sculpt.enter()
        yield .4
        panel=desktop._right_dock._ensure_host_container().sculpt_panel
        duplicate=next(w for w in panel.palettes['SubTool'].findChildren(W.QPushButton) if w.text()=='Duplicate')
        panel.root.ensureWidgetVisible(duplicate);yield .15
        T.QTest.mouseClick(duplicate,C.Qt.LeftButton);yield .3
        copy_name=ops.active().name
        check(section+' actual SubTool Duplicate preserves surface',copy_name!=name and same(expected,surface(ops.active()),section+' duplicate'))
        # Use the existing sidebar history route while native Sculpt owns input.
        helper_names=[obj.name for obj in bpy.data.objects if obj.get('_lf_instance_helper') and obj.parent==ops.active()]
        if os.environ.get('LANDFALL_INSTANCE_DIRECT_HISTORY'):
            with bpy.context.temp_override(**view()):bpy.ops.ed.undo()
        else:
            app.setActiveWindow(panel.root.window());panel.root.window().activateWindow();panel.root.setFocus()
            yield .15
            duplicate.setFocus(C.Qt.MouseFocusReason)
            T.QTest.keyClick(duplicate,C.Qt.Key_Z,C.Qt.ControlModifier)
        yield .3
        check(section+' one Undo removes duplicate and its owned helpers',bpy.data.objects.get(copy_name) is None and bpy.data.objects.get(name) is not None and helper_names and all(bpy.data.objects.get(n) is None for n in helper_names))
        if os.environ.get('LANDFALL_INSTANCE_DIRECT_HISTORY'):
            with bpy.context.temp_override(**view()):bpy.ops.ed.redo()
        else:
            app.setActiveWindow(panel.root.window());panel.root.window().activateWindow();panel.root.setFocus()
            yield .15
            duplicate.setFocus(C.Qt.MouseFocusReason)
            T.QTest.keyClick(duplicate,C.Qt.Key_Z,C.Qt.ControlModifier|C.Qt.ShiftModifier)
        yield .3
        copy=bpy.data.objects.get(copy_name)
        from landfall_studio.ui import hotkey_passthrough
        check(section+' Redo restores independent duplicate',copy is not None and same(expected,surface(copy),section+' duplicate Redo'),
              {'passthrough':hotkey_passthrough.get_last_passthrough_event(),
               'qt_focus':str(app.focusWidget()),'qt_popup':str(app.activePopupWidget()),'qt_modal':str(app.activeModalWidget())})
        return_button=next(header.buttons['Return'] for header in zbrush_panel._headers if header.root.isVisible())
        T.QTest.mouseClick(return_button,C.Qt.LeftButton);yield .4
        desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .15
        editor=attribute_editor.ensure_attribute_editor_widget()
        type_value(editor.spn_tx,9);yield .2
        copy=bpy.data.objects[copy_name];original=bpy.data.objects[name]
        check(section+' copied asset moves through actual model inspector',abs(copy.location.x-9)<1e-5 and same(expected,surface(copy),section+' copied move'))
        check(section+' moving copy preserves original asset',abs(original.location.x-4)<1e-5 and same(expected,surface(original),section+' original after copy move'))
        saved[name]=surface(original);saved[copy_name]=surface(copy)

    path=Path(os.environ['LANDFALL_UI_ISOLATION_REPORT']).parent/'generated_assets_roundtrip.blend'
    with bpy.context.temp_override(**view()):bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path));yield 1
    check('fresh file load restores all generated assets',all(name in bpy.data.objects for name in saved))
    for name,expected in saved.items():
        obj=bpy.data.objects[name];obj.location.y+=3
        check('saved generated asset follows after reopen '+name,same(expected,surface(obj),'reopen '+name))
    result['ok']=not result['failed'];save()
    landfall_studio.unregister();bpy.ops.wm.quit_blender()


steps=suite()


def tick():
    try:return next(steps)
    except StopIteration:return None
    except Exception:
        result['failed'].append({'exception':traceback.format_exc()});save()
        traceback.print_exc();bpy.ops.wm.quit_blender();return None


bpy.app.timers.register(tick,first_interval=.5,persistent=True)
