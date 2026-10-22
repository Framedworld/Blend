import bpy,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def run():
    import landfall_studio
    from landfall_studio.ui import desktop
    from landfall_studio import sculpt
    landfall_studio.register();desktop.restore_workspace_desktop();sculpt.enter()
    bpy.app.timers.register(probe,first_interval=1.5,persistent=True)
def probe():
    from PySide6 import QtCore,QtTest,QtWidgets
    from landfall_studio.ui.main_menu import get_main_menu_dock
    m=get_main_menu_dock().ctrl.menubar;a=m.actions()[0];r=m.actionGeometry(a)
    QtTest.QTest.mouseClick(m,QtCore.Qt.LeftButton,pos=r.center())
    data={'class':str(type(m)),'press':getattr(m,'press_seen',False),'release':getattr(m,'release_seen',False),
        'immediate':getattr(m,'popup_visible_immediately',None),'visible':a.menu().isVisible(),'action':a.text(),'enabled':a.isEnabled(),'widget_visible':m.isVisible()}
    Path(ROOT/'output/menu_probe.json').write_text(json.dumps(data,indent=2))
    bpy.app.timers.register(finish,first_interval=.3,persistent=True)
def finish():
    from PySide6 import QtWidgets
    from landfall_studio.ui.main_menu import get_main_menu_dock
    m=get_main_menu_dock().ctrl.menubar;a=m.actions()[0]
    path=ROOT/'output/menu_probe.json';data=json.loads(path.read_text());data.update(later=a.menu().isVisible(),popup=str(QtWidgets.QApplication.activePopupWidget()))
    path.write_text(json.dumps(data,indent=2));bpy.ops.wm.quit_blender()
def start():
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile();bpy.app.timers.register(run,first_interval=.5,persistent=True)
bpy.app.timers.register(start,first_interval=.5)
