"""Trace the real sculpt File-menu activation in a disposable GUI."""
import bpy,sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
test=ROOT/'tests/test_zbrush_sculpt_gui.py'
ns={'__file__':str(test),'__name__':'menu_focus_probe'}
exec(compile(test.read_text(encoding='utf-8').split('\ngenerator=None')[0],str(test),'exec'),ns)
ns['OUT']=ROOT/'output/menu_focus_probe.json'
sys.argv.append('--trace-focus')
calls=[]
def start():
 bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
 import landfall_studio
 landfall_studio.register()
 from landfall_studio.ui import desktop,menu_bar
 from PySide6 import QtCore,QtWidgets
 if '--stock-bar' in sys.argv:
  def stock_bar():
   bar=QtWidgets.QMenuBar();bar.setNativeMenuBar(False);return bar
  menu_bar.create_menu_bar=stock_bar
 events=[]
 class Events(QtCore.QObject):
  def eventFilter(self,obj,event):
   if event.type() in (QtCore.QEvent.WindowActivate,QtCore.QEvent.WindowDeactivate,QtCore.QEvent.FocusIn,QtCore.QEvent.FocusOut,QtCore.QEvent.Show,QtCore.QEvent.Hide):
    events.append((str(event.type()),type(obj).__name__,obj.objectName(),str(QtWidgets.QApplication.activeWindow()),str(QtWidgets.QApplication.activePopupWidget())))
   return False
 app=QtWidgets.QApplication.instance()
 # Installed after register has constructed the QApplication on the first step.
 monitor=None
 original=desktop._parent_floating_to_blender
 def parent(widget):
  calls.append({'phase':'parent_before','visible':widget.isVisible(),'name':widget.objectName()})
  if '--skip-owner' not in sys.argv:original(widget)
  calls.append({'phase':'parent_after','visible':widget.isVisible()})
 desktop._parent_floating_to_blender=parent
 steps=ns['suite']()
 def tick():
  try:
   nonlocal monitor
   delay=next(steps)
   app=QtWidgets.QApplication.instance()
   if monitor is None and app:
    monitor=Events(app);app.installEventFilter(monitor)
   checks=ns['results']['passed']+ns['results']['failed']
   if any((x if isinstance(x,str) else x.get('test'))=='main File label opens actual Qt menu' for x in checks):
    ns['results']['observations']['parent_calls']=calls;ns['results']['observations']['probe_args']=sys.argv;ns['results']['observations']['qt_events']=events;ns['save']();bpy.ops.wm.quit_blender();return None
   return delay
  except Exception:
   ns['check']('probe exception',False,traceback.format_exc());bpy.ops.wm.quit_blender();return None
 bpy.app.timers.register(tick,first_interval=.5,persistent=True)
bpy.app.timers.register(start,first_interval=.5)
