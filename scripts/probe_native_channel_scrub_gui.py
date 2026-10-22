"""Native viewport MMB history with the Studio Channel Box adapter installed."""
import bpy,json,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/native_channel_scrub_gui.json'
result={'ok':False,'passed':[],'failed':[],
 'boundary':'Disposable factory scene; native simulated viewport MMB and Z/Shift-Z, real Qt typed transform'}
def save():OUT.write_text(json.dumps(result,indent=2),encoding='utf-8')
def check(name,yes,detail=None):
 result['passed' if yes else 'failed'].append(name if yes else {'test':name,'detail':detail});save()
def obj():return bpy.data.objects['Cube']
def view():
 w=bpy.context.window_manager.windows[0];a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
 return dict(window=w,screen=w.screen,area=a,region=next(r for r in a.regions if r.type=='WINDOW'))
def event(kind,value='PRESS',dx=0,**mods):
 c=view();r=c['region']
 c['window'].event_simulate(type=kind,value=value,x=r.x+int(r.width*.7)+dx,y=r.y+int(r.height*.4),**mods)
def key(kind,**mods):
 from PySide6 import QtWidgets as W
 from blendertk.ui_utils.blender_window import BlenderWindow
 app=W.QApplication.instance()
 if app.focusWidget():app.focusWidget().clearFocus()
 app.setActiveWindow(None);BlenderWindow.set_keyboard_focus(BlenderWindow.window_hwnd(view()['window']))
 event('MOUSEMOVE','NOTHING');event(kind,**mods);event(kind,'RELEASE',**mods)
def drag(cancel=False):
 before=obj().location.y
 event('MOUSEMOVE','NOTHING');yield .1;event('MIDDLEMOUSE');yield .1
 for dx in (10,25,50):event('MOUSEMOVE','NOTHING',dx);yield .06
 if cancel:
  check('native viewport channel preview changes before Escape',abs(obj().location.y-before)>.1)
  event('ESC',dx=50);event('ESC','RELEASE',50)
  event('MIDDLEMOUSE','RELEASE',50)
 else:event('MIDDLEMOUSE','RELEASE',50)
 yield .2
def suite():
 bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
 import landfall_studio
 from landfall_studio import ui
 from landfall_studio.ui import desktop,channel_box_ext,channel_history,attribute_editor
 from landfall_studio.commands import scene_edits
 landfall_studio.register();ui.restore_workspace_desktop(restore_script_output=False);yield .8
 desktop.cycle_right_dock('CHANNEL_BOX');yield .2
 obj().location=(2,.5,0)
 with bpy.context.temp_override(**view()):
  bpy.ops.ed.undo_push(message='Native scrub fixture');bpy.ops.transform.translate('EXEC_DEFAULT',True,value=(.25,0,0))
 desktop.sync_channels_now();channel_box_ext.select_channels_in_ui(['location_y']);yield .2
 check('live Studio channel history adapter is installed',len(channel_history._adapters)==1)
 key('W');yield .15
 before=obj().location.y;yield from drag();end=obj().location.y
 check('viewport MMB scrubs highlighted Channel Box channel',end>before+.1 and abs(obj().location.x-2.25)<1e-5,[before,end])
 key('Z');yield .25
 check('one native Undo restores complete viewport channel drag',abs(obj().location.y-before)<1e-5,obj().location.y)
 key('Z');yield .25
 check('viewport channel drag leaves preceding native history intact',abs(obj().location.x-2)<1e-5,obj().location.x)
 key('Z',shift=True);yield .2;key('Z',shift=True);yield .25
 check('native Redo restores viewport drag in one step',abs(obj().location.y-end)<1e-5,obj().location.y)
 desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
 from PySide6 import QtCore as C,QtWidgets as W,QtTest as T
 app=W.QApplication.instance();field=attribute_editor.ensure_attribute_editor_widget().spn_ty
 app.setActiveWindow(field.window());field.setFocus();field.lineEdit().selectAll()
 T.QTest.keyClicks(field.lineEdit(),'3.125');T.QTest.keyClick(field.lineEdit(),C.Qt.Key_Return);field.clearFocus();yield .2
 check('Qt inspector works after native viewport scrub',abs(obj().location.y-3.125)<1e-5)
 key('Z');yield .25
 check('Undo after Qt edit returns to native scrub end value',abs(obj().location.y-end)<1e-5,obj().location.y)
 key('Z');yield .25
 check('next Undo returns to native scrub start value',abs(obj().location.y-before)<1e-5,obj().location.y)
 key('Z',shift=True);yield .2
 start=obj().location.y;yield from drag(cancel=True)
 check('Escape cancels viewport transform-channel scrub',abs(obj().location.y-start)<1e-5,obj().location.y)
 check('viewport previews create no pending Qt callbacks or gestures',not scene_edits._pending and not scene_edits._gestures)
 result['ok']=not result['failed'];save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
 try:return next(steps)
 except StopIteration:return None
 except Exception:
  result['failed'].append({'exception':traceback.format_exc()});save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
