"""Diagnose native event routing after a docked Qt edit; factory scene only."""
import bpy,sys,json,ctypes,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
out=ROOT/'output/history_key_probe.json';data={}
def view():
 w=bpy.context.window_manager.windows[0];a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
 return dict(window=w,screen=w.screen,area=a,region=next(r for r in a.regions if r.type=='WINDOW'))
def key(kind,**mods):
 c=view();r=c['region'];kw=dict(x=r.x+r.width//2,y=r.y+r.height//2)
 c['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',**kw)
 for v in ('PRESS','RELEASE'):c['window'].event_simulate(type=kind,value=v,**kw,**mods)
def suite():
 bpy.context.preferences.view.show_splash=False
 bpy.ops.wm.read_homefile()
 import landfall_studio
 from landfall_studio import ui,commands
 from landfall_studio.ui import desktop,attribute_editor
 landfall_studio.register();yield .5;ui.restore_workspace_desktop(restore_script_output=False);yield .5
 from PySide6 import QtWidgets as W,QtCore as C,QtTest as T
 from blendertk.ui_utils.blender_window import BlenderWindow
 app=W.QApplication.instance();hwnd=BlenderWindow.window_hwnd(view()['window'])
 data['hwnd']=hwnd;data['ghosts']=BlenderWindow.process_ghost_hwnds()
 with bpy.context.temp_override(**view()):
  bpy.ops.ed.undo_push(message='Baseline');bpy.ops.transform.translate('EXEC_DEFAULT',True,value=(2,0,0))
 key('Q');yield .3;data['initial_tool']=commands.get_active_tool()
 desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
 field=attribute_editor.ensure_attribute_editor_widget().spn_tx
 app.setActiveWindow(field.window());field.window().activateWindow();field.setFocus()
 field.lineEdit().selectAll();T.QTest.keyClicks(field.lineEdit(),'7.5');T.QTest.keyClick(field.lineEdit(),C.Qt.Key_Return);yield .2
 data['typed']=bpy.data.objects['Cube'].location.x
 field.clearFocus();key('W');yield .3;data['tool_after_qt']=commands.get_active_tool()
 key('Z');yield .3;data['z_after_qt']=bpy.data.objects['Cube'].location.x
 ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(hwnd));BlenderWindow.set_keyboard_focus(hwnd);yield .3
 key('Q');yield .3;data['tool_after_focus']=commands.get_active_tool()
 key('Z');yield .3;data['z_after_focus']=bpy.data.objects['Cube'].location.x
 key('Z',ctrl=True);yield .3;data['ctrl_z']=bpy.data.objects['Cube'].location.x
 with bpy.context.temp_override(**view()):bpy.ops.ed.undo()
 yield .3;data['direct_undo']=bpy.data.objects['Cube'].location.x
 out.write_text(json.dumps(data,indent=2));landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
 try:return next(steps)
 except StopIteration:return None
 except Exception:
  data['error']=traceback.format_exc();out.write_text(json.dumps(data,indent=2));bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
