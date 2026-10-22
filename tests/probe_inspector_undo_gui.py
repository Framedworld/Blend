"""Diagnostic: real Qt AE edit followed by native Undo/Redo, factory data only."""
import bpy,sys,json,traceback,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/('output/inspector_undo'+os.environ.get('LANDFALL_HISTORY_TAG','_probe')+'.json')
result={'boundary':'Disposable native Blender; QtTest edit and bpy native Undo/Redo'}
def save():OUT.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
def view():
 w=bpy.context.window_manager.windows[0];a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
 return {'window':w,'area':a,'region':next(r for r in a.regions if r.type=='WINDOW')}
def suite():
 import landfall_studio
 from landfall_studio import ui
 from landfall_studio.ui import desktop,attribute_editor
 landfall_studio.register();yield .5
 ui.restore_workspace_desktop(restore_script_output=False);yield .5
 from PySide6 import QtWidgets as W,QtCore as C,QtTest as T
 app=W.QApplication.instance()
 with bpy.context.temp_override(**view()):
  bpy.ops.ed.undo_push(message='Inspector baseline')
  bpy.ops.transform.translate('EXEC_DEFAULT',True,value=(2,0,0))
 yield .2
 desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
 editor=attribute_editor.ensure_attribute_editor_widget();field=editor.spn_tx
 app.setActiveWindow(field.window());field.setFocus();field.lineEdit().selectAll()
 T.QTest.keyClicks(field.lineEdit(),'7.5');T.QTest.keyClick(field.lineEdit(),C.Qt.Key_Return);yield .2
 result['before']=2;result['typed']=bpy.data.objects['Cube'].location.x
 field.clearFocus()
 with bpy.context.temp_override(**view()):bpy.ops.ed.undo()
 yield .3
 result['undo']=bpy.data.objects['Cube'].location.x
 with bpy.context.temp_override(**view()):bpy.ops.ed.redo()
 yield .3
 result['redo']=bpy.data.objects['Cube'].location.x
 save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
 try:return next(steps)
 except StopIteration:return None
 except Exception:
  result['error']=traceback.format_exc();save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5)
