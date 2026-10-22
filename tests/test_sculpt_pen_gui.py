"""Native Studio pen UI acceptance; synthetic QTabletEvent, not physical-device QA."""
import bpy,sys,json,traceback,os,ctypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_PEN_TAG','');OUT=ROOT/('output/sculpt_pen_gui'+TAG+'.json')
result={'passed':[],'failed':[],'input':'Synthetic QTabletEvent + native Qt widget events in disposable Blender; physical driver/tablet feel unverified'}
def save():OUT.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
def check(name,yes,detail=None):result['passed' if yes else 'failed'].append(name if yes else {'test':name,'detail':detail});save()
def suite():
 import landfall_studio
 from landfall_studio import ui,sculpt
 from landfall_studio.ui import desktop,zbrush_panel as zp,sculpt_widgets as sw,hotkey_passthrough as hp
 from landfall_studio.sculpt import ops,state,preferences,extended,layout
 from landfall_studio.sculpt.demo import create_demo
 preferences.PATH=ROOT.parent/('.test_env/pen_preferences_'+str(os.getpid())+'.json');preferences._data=None
 landfall_studio.register();yield .5;ui.restore_workspace_desktop(restore_script_output=False);yield .5
 from PySide6 import QtCore as C,QtGui as G,QtWidgets as W,QtTest as T
 from blendertk.ui_utils.blender_window import BlenderWindow
 from blendertk.ui_utils.qt_dock import QtDock
 with bpy.context.temp_override(**ops.view_context()):create_demo()
 yield 1
 hwnd=BlenderWindow.window_hwnd(ops.view_context()['window']);ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd);yield .5
 panel=desktop._right_dock._ensure_host_container().sculpt_panel;pointer=hp.get_hotkey_filter().sculpt_pointer;dock_predicate=hp.get_hotkey_filter()._dock_predicate
 result['dpr']=panel.root.devicePixelRatioF()
 pen=G.QPointingDevice('Studio test pen',91,G.QInputDevice.DeviceType.Stylus,G.QPointingDevice.PointerType.Pen,G.QInputDevice.Capability.Position|G.QInputDevice.Capability.Pressure,1,3)
 def tablet(widget,kind,global_pos=None,button=C.Qt.LeftButton,pressure=.001):
  p=G.QCursor.pos() if global_pos is None else global_pos
  p=C.QPointF(p);local=C.QPointF(widget.mapFromGlobal(p.toPoint()))
  event=G.QTabletEvent(kind,pen,local,p,pressure if kind!=C.QEvent.TabletRelease else 0,0,0,0,0,0,C.Qt.NoModifier,button if kind!=C.QEvent.TabletMove else C.Qt.NoButton,C.Qt.NoButton if kind==C.QEvent.TabletRelease else button)
  W.QApplication.sendEvent(widget,event)
 def position(w):return C.QPointF(w.mapToGlobal(w.rect().center()))
 def tap(w,p=None):
  p=p or position(w);tablet(w,C.QEvent.TabletPress,p);tablet(w,C.QEvent.TabletRelease,p)
 def mouse(w,kind,p,source=C.Qt.MouseEventNotSynthesized):
  event=G.QMouseEvent(kind,C.QPointF(w.mapFromGlobal(p.toPoint())),C.QPointF(w.window().mapFromGlobal(p.toPoint())),p,C.Qt.LeftButton,C.Qt.NoButton if kind==C.QEvent.MouseButtonRelease else C.Qt.LeftButton,C.Qt.NoModifier,source);W.QApplication.sendEvent(w,event)
 def wheel(w,ctrl=False):
  p=position(w);e=G.QWheelEvent(C.QPointF(w.rect().center()),p,C.QPoint(),C.QPoint(0,-120),C.Qt.NoButton,C.Qt.ControlModifier if ctrl else C.Qt.NoModifier,C.Qt.NoScrollPhase,False);W.QApplication.sendEvent(w,e)
 check('right tray opts into scoped pen input',pointer.scope(panel.root) is panel.root)
 panel.palettes['Masking'].setChecked(True);button=panel.buttons['Mask All'];panel.root.ensureWidgetVisible(button);yield .2
 clicks=[];button.clicked.connect(lambda:clicks.append(1));p=position(button)
 tablet(button,C.QEvent.TabletPress,p,pressure=.00001)
 check('light contact gives immediate pressed feedback',button.isDown())
 check('dock focus owner respects pen contact',QtDock._interaction_in_flight())
 tablet(button,C.QEvent.TabletRelease,p);yield .1
 check('first pen tap activates actual mask once',len(clicks)==1 and min(ops.mask_values())>.99)
 for kind in (C.QEvent.MouseButtonPress,C.QEvent.MouseButtonRelease):mouse(button,kind,p,C.Qt.MouseEventSynthesizedBySystem)
 check('driver mouse echoes do not activate twice',len(clicks)==1)
 for kind in (C.QEvent.MouseButtonPress,C.QEvent.MouseButtonRelease):mouse(button,kind,p)
 check('real mouse works immediately after pen',len(clicks)==2)
 for _ in range(4):tap(button)
 check('rapid separate pen taps each activate once',len(clicks)==6)
 p=position(button);tablet(panel.root,C.QEvent.TabletPress,p);tablet(panel.root,C.QEvent.TabletRelease,p)
 check('container-level pen delivery resolves the actual button',len(clicks)==7)
 clear=panel.buttons['Clear'];panel.root.ensureWidgetVisible(clear);yield .1
 bar=panel.root.verticalScrollBar();start=bar.value();p=position(clear)
 tablet(clear,C.QEvent.TabletPress,p);tablet(clear,C.QEvent.TabletMove,p+C.QPointF(0,-110));tablet(clear,C.QEvent.TabletRelease,p+C.QPointF(0,-110));yield .1
 check('vertical pen drag from button scrolls tray',bar.value()>=start+100,{'before':start,'after':bar.value()})
 check('scrolling from Clear does not clear mask',min(ops.mask_values())>.99)
 check('scroll ends without stuck button or pointer owner',not clear.isDown() and not pointer.active and W.QWidget.mouseGrabber() is None)
 panel.palettes['Geometry'].setChecked(True);panel.root.verticalScrollBar().setValue(0);yield .1
 background=panel.content;p=C.QPointF(panel.root.viewport().mapToGlobal(C.QPoint(2,160)));start=bar.value()
 tablet(background,C.QEvent.TabletPress,p);tablet(background,C.QEvent.TabletMove,p+C.QPointF(0,-40))
 check('empty tray space grabs and follows pen one to one',bar.value()==start+40,{'before':start,'after':bar.value(),'maximum':bar.maximum()})
 tablet(background,C.QEvent.TabletMove,p+C.QPointF(0,-6000));tablet(background,C.QEvent.TabletRelease,p+C.QPointF(0,-6000))
 check('tray grab stops at the content boundary',bar.value()==bar.maximum())
 group=panel.palettes['Deformation'];panel.root.ensureWidgetVisible(group);yield .1
 p=C.QPointF(group.mapToGlobal(C.QPoint(group.width()-30,14)));old=group.isChecked();tap(group,p);yield .15
 check('full palette title width responds to a pen tap',group.isChecked()!=old)
 panel.root.ensureWidgetVisible(group);yield .1
 p=C.QPointF(group.mapToGlobal(C.QPoint(group.width()-30,14)));old=group.isChecked();start=bar.value()
 tablet(group,C.QEvent.TabletPress,p);tablet(group,C.QEvent.TabletMove,p+C.QPointF(0,-70));tablet(group,C.QEvent.TabletRelease,p+C.QPointF(0,-70))
 check('dragging palette header scrolls without collapsing',group.isChecked()==old and bar.value()>start)
 panel.palettes['Geometry'].setChecked(True);panel.root.verticalScrollBar().setValue(0);yield .15
 size=panel.content.findChild(W.QSlider,'SculptOption_SubTool_visible_count');panel.root.ensureWidgetVisible(size);yield .1
 check('parameter slider has larger pen target',size.height()>=18)
 p=C.QPointF(size.mapToGlobal(C.QPoint(round(size.width()*.75),size.height()//2)));tap(size,p);yield .1
 check('pen slider tap goes directly to touched value',9<=extended.settings('SubTool')['visible_count']<=10,{'value':extended.settings('SubTool')['visible_count'],'slider':size.value()})
 original=extended.settings('SubTool')['visible_count'];T.QTest.keyClick(size,C.Qt.Key_Left);yield .1
 check('slider keyboard step commits actual integer setting',extended.settings('SubTool')['visible_count']==original-1)
 p=position(size);start=bar.value();releases=[];size.sliderReleased.connect(lambda:releases.append(1))
 tablet(size,C.QEvent.TabletPress,p);tablet(size,C.QEvent.TabletMove,p+C.QPointF(size.width(),35));tablet(size,C.QEvent.TabletRelease,p+C.QPointF(size.width(),35));yield .1
 check('slider drag remains a parameter gesture outside target',extended.settings('SubTool')['visible_count']==12 and len(releases)==1 and bar.value()==start)
 original=extended.settings('SubTool')['visible_count'];p=position(size)
 tablet(size,C.QEvent.TabletPress,p);tablet(size,C.QEvent.TabletMove,p-C.QPointF(60,0));T.QTest.keyClick(size,C.Qt.Key_Escape);tablet(size,C.QEvent.TabletRelease,p-C.QPointF(60,0));yield .1
 check('Escape cancels pending slider without committing',extended.settings('SubTool')['visible_count']==original and not pointer.active and not size.isSliderDown())
 panel.root.verticalScrollBar().setValue(100);old_value=size.value();start=bar.value();wheel(size);yield .1
 check('wheel over slider scrolls instead of changing value',size.value()==old_value and bar.value()>start)
 number=panel.content.findChild(W.QDoubleSpinBox,'SculptValue_SubTool_visible_count');old_value=number.value();start=bar.value();wheel(number);yield .1
 check('wheel over numeric value scrolls safely',number.value()==old_value and bar.value()>start)
 panel.root.ensureWidgetVisible(number);yield .1;tap(number.lineEdit());T.QTest.keyClick(number.lineEdit(),C.Qt.Key_A,C.Qt.ControlModifier);T.QTest.keyClicks(number.lineEdit(),'7');T.QTest.keyClick(number.lineEdit(),C.Qt.Key_Return);yield .1
 check('pen focuses numeric entry and Enter commits',extended.settings('SubTool')['visible_count']==7)
 panel.palettes['NanoMesh'].setChecked(True);panel.root.ensureWidgetVisible(panel.nano_source);yield .1
 source=panel.nano_source.currentText();start=bar.value();wheel(panel.nano_source);yield .1
 check('wheel over source picker does not change source',panel.nano_source.currentText()==source and bar.value()>start)
 panel.root.ensureWidgetVisible(panel.nano_source);tap(panel.nano_source)
 result['combo_immediate']={'visible':panel.nano_source.view().isVisible(),'contact':pointer.active}
 yield .15
 check('pen tap opens source popup immediately on first try',result['combo_immediate']['visible'] and panel.nano_source.view().isVisible(),result['combo_immediate'])
 view=panel.nano_source.view();index=panel.nano_source.model().index(0,0);p=C.QPointF(view.viewport().mapToGlobal(view.visualRect(index).center()));tap(view.viewport(),p);yield .15
 check('pen selects real source from combo popup',bool(extended.settings('NanoMesh').get('source')) and not view.isVisible(),{'source':extended.settings('NanoMesh').get('source'),'display':panel.nano_source.currentText(),'popup_visible':view.isVisible()})
 # App focus loss cancels a pending command and allows the next complete tap.
 panel.palettes['Masking'].setChecked(True);panel.root.ensureWidgetVisible(clear);yield .1
 p=position(clear);tablet(clear,C.QEvent.TabletPress,p)
 W.QApplication.sendEvent(W.QApplication.instance(),C.QEvent(C.QEvent.ApplicationDeactivate));yield .1
 check('focus loss clears contact and pressed state',not pointer.active and not clear.isDown())
 tablet(clear,C.QEvent.TabletRelease,p);tap(clear);yield .1
 check('next pen tap works after interrupted contact',max(ops.mask_values())<.001)
 # Favorite, picker, persistent Quick controls and native canvas buttons.
 favorite=layout._favorites.tiles['DS'];stable=dict(layout._favorites.tiles);tap(favorite);yield .15
 check('pen selects favorite brush on first tap',state.get().active_zbrush_brush=='DamStandard')
 check('favorite widgets remain stable when brushes change',all(layout._favorites.tiles.get(c) is w for c,w in stable.items()))
 sw.set_origin();popup=sw.show_quick();yield .15
 symmetry=popup.toggles['Sym X'];before=ops.active().use_mesh_mirror_x;p=position(symmetry);tablet(popup,C.QEvent.TabletPress,p);tablet(popup,C.QEvent.TabletRelease,p);yield .15
 check('Quick toggle applies and retains popup focus',popup.isVisible() and ops.active().use_mesh_mirror_x!=before)
 quick=popup.sliders['draw_size'];p=C.QPointF(quick.mapToGlobal(C.QPoint(round(quick.width()*.8),quick.height()//2)));tap(quick,p);yield .1
 check('pen Quick slider updates actual brush immediately',state.brush().size>350)
 popup.finish(True);yield .1
 popup=sw.show_brush_palette();yield .15;tap(popup.buttons['CB']);yield .15
 check('pen brush-browser choice applies and closes once',state.get().active_zbrush_brush=='ClayBuildup' and not popup.isVisible())
 tap(layout._left.wells['Stroke']);yield .15
 menu=W.QApplication.activePopupWidget();action=next(a for a in menu.actions() if a.text()=='Dots');tap(menu,C.QPointF(menu.mapToGlobal(menu.actionGeometry(action).center())));yield .1
 check('pen menu item applies actual stroke and closes',state.get().stroke_method=='DOTS' and not menu.isVisible())
 favorite=layout._favorites.tiles['CB'];p=position(favorite)
 tablet(favorite,C.QEvent.TabletPress,p,button=C.Qt.RightButton);tablet(favorite,C.QEvent.TabletRelease,p,button=C.Qt.RightButton);yield .1
 menu=W.QApplication.activePopupWidget();check('pen barrel opens brush context menu',menu is not None and menu.isVisible())
 if menu:menu.close()
 from landfall_studio.ui import viewport_bar
 floor=viewport_bar.get_bars()[0].sculpt_canvas.buttons['Floor'];before=bpy.context.scene.landfall_grid_finite;tap(floor);yield .1
 check('canvas navigation strip accepts first pen tap',bpy.context.scene.landfall_grid_finite!=before);tap(floor)
 silhouette=viewport_bar.get_bars()[0].sculpt_canvas.silhouette;original=state.get().silhouette_scale
 p=C.QPointF(silhouette.mapToGlobal(C.QPoint(silhouette.width()-4,silhouette.height()-4)));tablet(silhouette,C.QEvent.TabletPress,p);tablet(silhouette,C.QEvent.TabletMove,p+C.QPointF(20,0))
 check('pen grabs silhouette resize handle',state.get().silhouette_scale>original)
 T.QTest.keyClick(silhouette,C.Qt.Key_Escape);tablet(silhouette,C.QEvent.TabletRelease,p+C.QPointF(20,0))
 check('cancelled silhouette resize restores scale and releases handle',state.get().silhouette_scale==original and silhouette.resize_anchor is None)
 p=C.QPointF(silhouette.mapToGlobal(C.QPoint(silhouette.width()-4,silhouette.height()-4)));tablet(silhouette,C.QEvent.TabletPress,p);tablet(silhouette,C.QEvent.TabletMove,p+C.QPointF(20,0));silhouette.hide()
 check('hiding a custom pen control cancels ownership safely',not pointer.active and silhouette.resize_anchor is None and state.get().silhouette_scale==original)
 tablet(silhouette,C.QEvent.TabletRelease,p+C.QPointF(20,0));viewport_bar.get_bars()[0].sculpt_canvas.sync()
 panel.palettes['Geometry'].setChecked(True);disabled=panel.buttons['Convert BPR To Geo'];panel.root.ensureWidgetVisible(disabled);yield .1
 calls=[];disabled.clicked.connect(lambda:calls.append(1));tap(disabled);check('disabled controls never activate from pen contact',not calls)
 popup=sw.show_quick();yield .1
 before=[tuple(v.co) for v in ops.active().data.vertices];p=C.QPointF(popup.mapToGlobal(C.QPoint(-20,-20)))
 tablet(popup,C.QEvent.TabletPress,p);tablet(popup,C.QEvent.TabletRelease,p);yield .15
 check('outside pen dismissal consumes contact without a stroke',not popup.isVisible() and before==[tuple(v.co) for v in ops.active().data.vertices])
 pointer.cancel();check('all pointer ownership is released',not pointer.active and W.QWidget.mouseGrabber() is None)
 layout.toggle_tray();yield .2
 drawer_button=layout._drawer.findChild(W.QPushButton);tap(drawer_button);yield .2
 check('pen opens collapsed tool tray on first tap',not layout._drawer_collapsed and panel.root.isVisible())
 panel.root.grab().save(str(ROOT/('output/sculpt_pen_tray'+TAG+'.png')))
 result['pointer_history']=pointer.history;result['pointer_errors']=pointer.errors
 check('pen adapter reports no event processing errors',not pointer.errors)
 native=list(pointer.native.items());check('Windows pen gesture settings are local to UI handles',bool(native))
 hp.uninstall_hotkey_filter();check('input teardown restores original dock focus predicate',QtDock._interaction_in_flight is dock_predicate)
 restored=True;ctypes.windll.user32.GetPropW.restype=ctypes.c_void_p
 for handle,(ref,old) in native:
  widget=ref()
  try:
   if widget and int(widget.internalWinId() or 0)==handle:restored &= ctypes.windll.user32.GetPropW(ctypes.c_void_p(handle),'MicrosoftTabletPenServiceProperty')==old
  except RuntimeError:pass
 check('input teardown restores UI Windows pen properties',restored)
 result['ok']=not result['failed'];save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
 try:return next(steps)
 except StopIteration:return None
 except Exception:result['failed'].append({'exception':traceback.format_exc()});result['ok']=False;save();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
