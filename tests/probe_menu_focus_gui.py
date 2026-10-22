"""Disposable diagnostic of native focus while opening a Studio Qt menu."""
import bpy,sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
result={'focus_calls':[],'events':[]}
def suite():
    import landfall_studio
    landfall_studio.register()
    from landfall_studio.sculpt import preferences
    preferences.PATH=ROOT.parent/'.test_env/menu_focus_preferences.json';preferences._data=None
    from landfall_studio.ui import desktop,main_menu
    desktop.restore_workspace_desktop()
    from landfall_studio import sculpt
    sculpt.enter();yield 1
    from PySide6 import QtWidgets,QtCore,QtGui,QtTest
    from blendertk.ui_utils.blender_window import BlenderWindow
    import ctypes
    hwnd=BlenderWindow.window_hwnd(bpy.context.window_manager.windows[0]);ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd)
    yield 1
    original=BlenderWindow.set_keyboard_focus;descriptor=BlenderWindow.__dict__['set_keyboard_focus']
    def tracked(cls,handle):
        result['focus_calls'].append({'target':int(handle),'stack':traceback.format_stack(limit=5)})
        return original(handle)
    BlenderWindow.set_keyboard_focus=classmethod(tracked)
    menu_bar=main_menu.get_main_menu_dock().ctrl.menubar;action=menu_bar.actions()[0];menu=action.menu()
    def observation():
        focus=BlenderWindow.keyboard_focus();widget=QtWidgets.QWidget.find(focus or 0)
        return dict(focus=focus,widget=widget.objectName() if widget else None,popup=str(QtWidgets.QApplication.activePopupWidget()),foreground=int(ctypes.windll.user32.GetForegroundWindow()),host=hwnd)
    class Monitor(QtCore.QObject):
        def eventFilter(self,obj,event):
            if event.type() in (QtCore.QEvent.Show,QtCore.QEvent.Hide,QtCore.QEvent.WindowActivate,QtCore.QEvent.WindowDeactivate,QtCore.QEvent.FocusIn,QtCore.QEvent.FocusOut):result['events'].append({'event':str(event.type()),**observation()})
            return False
    monitor=Monitor(menu);menu.installEventFilter(monitor)
    rect=menu_bar.actionGeometry(action);QtGui.QCursor.setPos(menu_bar.mapToGlobal(rect.center()));yield .1
    QtTest.QTest.mouseClick(menu_bar,QtCore.Qt.LeftButton,pos=rect.center());result['immediate']=dict(visible=menu.isVisible(),**observation())
    yield .3
    result['later']=dict(visible=menu.isVisible(),**observation())
    (ROOT/'output/menu_focus_probe.json').write_text(json.dumps(result,indent=2))
    BlenderWindow.set_keyboard_focus=descriptor
    menu.close();landfall_studio.unregister();bpy.ops.wm.quit_blender()
gen=None
def tick():
    try:return next(gen)
    except StopIteration:return None
def start():
    global gen
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile();gen=suite();bpy.app.timers.register(tick,persistent=True)
bpy.app.timers.register(start,first_interval=.5)
