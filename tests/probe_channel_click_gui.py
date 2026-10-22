"""Diagnostic of native Channel Box single-click editing; factory data only."""
import bpy,sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));data={}
out=ROOT/'output/channel_click_probe.json'
def suite():
 bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
 import landfall_studio
 from landfall_studio import ui
 from landfall_studio.ui import desktop
 landfall_studio.register();ui.restore_workspace_desktop(restore_script_output=False);yield .7
 from PySide6 import QtWidgets as W,QtCore as C,QtTest as T
 channels,slots=desktop.get_panel_widget_and_slots('channels');table=channels.tbl000
 app=W.QApplication.instance();app.setActiveWindow(table.window());table.window().activateWindow();table.setFocus();yield .1
 row=next(i for i,d in enumerate(slots._row_descriptors) if d.get('data_path')=='location' and d.get('index')==1)
 item=table.item(row,slots.COL_VALUE);table.scrollToItem(item)
 logs=[];original=table.mouseReleaseEvent
 def release(event):
  logs.append({'kind':'release','col':table.indexAt(event.pos()).column(),'button':str(event.button()),'drag':table._drag_occurred})
  original(event)
  logs.append({'kind':'after','state':str(table.state()),'children':[(type(w).__name__,w.isVisible(),w.objectName()) for w in table.findChildren(W.QWidget)]})
 table.mouseReleaseEvent=release
 def snapshot():
  return {'state':str(table.state()),'cell_widget':str(table.cellWidget(row,slots.COL_VALUE)),
   'focus':str(app.focusWidget()),'children':[(type(w).__name__,w.isVisible(),w.objectName()) for w in table.findChildren(W.QWidget)]}
 T.QTest.mouseClick(table.viewport(),C.Qt.LeftButton,pos=table.visualItemRect(item).center());yield .15
 data['click']=snapshot();data['logs']=logs.copy()
 T.QTest.mouseDClick(table.viewport(),C.Qt.LeftButton,pos=table.visualItemRect(item).center());yield .15
 data['double']=snapshot()
 table.editItem(item);yield .15;data['explicit']=snapshot()
 out.write_text(json.dumps(data,indent=2));landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
 try:return next(steps)
 except StopIteration:return None
 except Exception:
  data['error']=traceback.format_exc();out.write_text(json.dumps(data,indent=2));bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
