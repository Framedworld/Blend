"""Actual layer GoZ button must have exactly one native mode-boundary Undo."""
import bpy,sys,os,json,ctypes,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_INSTANCE_TAG','')
OUT=ROOT/('output/layer_goz_history_gui'+TAG+'.json')
report={'ok':False,'passed':[],'failed':[],'trace':[]}
def save():OUT.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
def check(label,value,detail=None):
    report['passed' if value else 'failed'].append(label if value else {'test':label,'detail':detail});save()
def view():
    w=bpy.context.window_manager.windows[0];a=max((a for a in w.screen.areas if a.type=='VIEW_3D'),key=lambda a:a.width*a.height)
    return dict(window=w,screen=w.screen,area=a,region=next(r for r in a.regions if r.type=='WINDOW'))
def arrays():
    return {k.name:[tuple(v.co) for v in k.data] for k in bpy.data.objects['Layer GoZ Fixture'].data.shape_keys.key_blocks}
def suite():
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
    import landfall_studio
    from landfall_studio import sculpt,ui
    from landfall_studio.ui import desktop,attribute_editor
    from PySide6 import QtCore as C,QtWidgets as W,QtGui as G,QtTest as T
    landfall_studio.register();ui.restore_workspace_desktop(restore_script_output=False);yield .8
    from blendertk.ui_utils.blender_window import BlenderWindow
    app=W.QApplication.instance();hwnd=BlenderWindow.window_hwnd(view()['window'])
    ctypes.windll.user32.ShowWindow(hwnd,3);yield .2
    def key(redo=False):
        if app.focusWidget():app.focusWidget().clearFocus()
        app.setActiveWindow(None);BlenderWindow.set_keyboard_focus(hwnd)
        context=view();r=context['region'];kw=dict(x=r.x+r.width//2,y=r.y+r.height//2)
        context['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',**kw)
        for value in ('PRESS','RELEASE'):context['window'].event_simulate(type='Z',value=value,shift=redo,**kw)
    def trace(stage):
        obj=bpy.data.objects['Layer GoZ Fixture']
        report['trace'].append({'stage':stage,'mode':bpy.context.mode,'dock':desktop._right_dock.mode,
                                'key':obj.active_shape_key.name,'x':obj.location.x,
                                'engaged':sculpt.is_engaged(),'automatic':sculpt.state.get().auto_activate,
                                'scene_restore_pending':desktop._scene_restore_timer is not None});save()
    with bpy.context.temp_override(**view()):
        obj=bpy.context.object;obj.name='Layer GoZ Fixture';obj.shape_key_add(name='Basis')
        form=obj.shape_key_add(name='Authored Layer');form.data[0].co.z+=.125;form.value=1
        obj.active_shape_key_index=1
        sculpt.enter();bpy.ops.ed.undo_push(message='Sculpt layer target fixture')
    yield .4
    expected=arrays();panel=desktop._right_dock._ensure_host_container().sculpt_panel
    panel.palettes['Layers'].setChecked(True);yield .15
    button=panel.buttons['⇄ GoZ to Shape Editor'];panel.root.ensureWidgetVisible(button);yield .15
    check('actual layer GoZ button is visible and enabled',button.isVisible() and button.isEnabled(),
          {'visible':button.isVisible(),'enabled':button.isEnabled(),'geometry':str(button.geometry())})
    if not button.isVisible() or not button.isEnabled():raise RuntimeError('Layer GoZ click precondition failed')
    T.QTest.mouseClick(button,C.Qt.LeftButton);yield .4;trace('actual GoZ click')
    check('layer GoZ opens exact Shape Editor target',bpy.context.mode=='OBJECT' and desktop._right_dock.mode=='SHAPE_EDITOR' and bpy.data.objects['Layer GoZ Fixture'].active_shape_key.name=='Authored Layer' and arrays()==expected)
    if bpy.context.mode!='OBJECT':raise RuntimeError('Actual GoZ command did not return before history test')
    key();yield .5;trace('first boundary Undo')
    extra=bpy.context.mode!='SCULPT'
    check('one layer GoZ Undo crosses directly to Sculpt',not extra and sculpt.is_engaged() and desktop._right_dock.mode=='ZBRUSH_STUDIO' and arrays()==expected)
    if extra:
        key();yield .35;trace('diagnostic second boundary Undo')
    key(True);yield .35;trace('first boundary Redo')
    if extra:key(True);yield .35;trace('diagnostic second boundary Redo')
    check('layer GoZ Redo restores exact Modeling Shape Editor',bpy.context.mode=='OBJECT' and desktop._right_dock.mode=='SHAPE_EDITOR' and bpy.data.objects['Layer GoZ Fixture'].active_shape_key.name=='Authored Layer' and arrays()==expected)
    desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
    field=attribute_editor.ensure_attribute_editor_widget().spn_tx
    G.QCursor.setPos(field.mapToGlobal(field.rect().center()));app.setActiveWindow(field.window());field.window().activateWindow();field.setFocus()
    field.lineEdit().selectAll();T.QTest.keyClicks(field.lineEdit(),'7.5');T.QTest.keyClick(field.lineEdit(),C.Qt.Key_Return);yield .2
    check('model edit after layer return commits',abs(bpy.data.objects['Layer GoZ Fixture'].location.x-7.5)<1e-5)
    key();yield .35;trace('model transform Undo')
    check('one model Undo stays in Modeling and preserves layer arrays',bpy.context.mode=='OBJECT' and not sculpt.is_engaged() and abs(bpy.data.objects['Layer GoZ Fixture'].location.x)<1e-5 and arrays()==expected)
    report['ok']=not report['failed'];save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
    try:return next(steps)
    except StopIteration:return None
    except Exception:
        report['failed'].append({'exception':traceback.format_exc()});save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
