"""Native fresh-file/save/reopen/editor lifecycle; all writes are disposable."""
import bpy,sys,json,traceback,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/full_ux_file_gui.json'
result={'ok':False,'passed':[],'failed':[],'boundary':'Factory scene and local temporary files; synthetic Qt events'}
def save():OUT.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
def check(name,yes,detail=None):result['passed' if yes else 'failed'].append(name if yes else {'test':name,'detail':detail});save()
def view():
 w=bpy.context.window_manager.windows[0];a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
 return {'window':w,'screen':w.screen,'area':a,'region':next(r for r in a.regions if r.type=='WINDOW')}
def suite():
 bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
 import landfall_studio
 from landfall_studio import ui,commands,continuity
 from landfall_studio.ui import desktop,main_menu,viewport_bar,menus,hybrid_window
 from landfall_studio.sculpt import preferences
 preferences.PATH=ROOT.parent/('.test_env/file_ux_prefs_'+str(os.getpid())+'.json');preferences._data=None
 landfall_studio.register();yield .5;ui.restore_workspace_desktop(restore_script_output=False);yield .5
 from PySide6 import QtCore as C,QtWidgets as W,QtTest as T
 local=ROOT.parent/'.test_env/full_ux_file_fixture.blend'
 cube=bpy.data.objects['Cube'];cube.name='Friend_Blockout';cube.location.x=2.5
 with bpy.context.temp_override(**view()):bpy.ops.wm.save_as_mainfile(filepath=str(local))
 check('new scene saves to local file',local.is_file())
 cube.location.y=4.5
 bar=main_menu.get_main_menu_dock().ctrl
 action=next(a for a in bar.menubar.actions() if a.text()=='File');menu=action.menu()
 menu.popup(bar.menubar.mapToGlobal(bar.menubar.actionGeometry(action).bottomLeft()));yield .2
 save_action=next(a for a in menu.actions() if a.text().split('\t')[0]=='Save Scene')
 T.QTest.mouseClick(menu,C.Qt.LeftButton,pos=menu.actionGeometry(save_action).center());yield .5
 check('File Save Scene click commits current file',bpy.data.filepath==str(local) and not bpy.data.is_dirty)
 cube.location.z=3.5
 field=desktop._right_dock._ensure_host_container().ae_ctrl.spn_tx
 desktop.cycle_right_dock('ATTRIBUTE_EDITOR');W.QApplication.setActiveWindow(field.window());field.setFocus()
 T.QTest.keyClick(field,C.Qt.Key_S,C.Qt.ControlModifier);yield .3
 check('Ctrl S saves from a focused Qt inspector',not bpy.data.is_dirty)
 bpy.ops.wm.open_mainfile(filepath=str(local))
 yield 2
 obj=bpy.data.objects.get('Friend_Blockout')
 check('saved scene reopens with edits',obj is not None and abs(obj.location.y-4.5)<.001)
 bars=viewport_bar.get_bars()
 check('viewport Qt controls recover after reopen',bool(bars) and all(b.root.isVisible() for b in bars))
 try:
  state=desktop.restore_workspace_desktop(restore_script_output=False)
  yield .5
  check('desktop restore after reopen succeeds',state.get('ok'),state)
 except Exception as exc:check('desktop restore after reopen succeeds',False,str(exc))
 before=len(view()['window'].screen.areas);ui.restore_workspace_desktop(restore_script_output=False);yield .3
 check('reopened desktop restore stays idempotent',len(view()['window'].screen.areas)==before)
 with bpy.context.temp_override(**view()):
  bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
  response=continuity.open_native_editor_or_mode('UV_EDITOR')
 yield .5
 check('UV button opens a real native editor window',response.get('ok') and response.get('editor_opened') and any(a.ui_type=='UV' for w in bpy.context.window_manager.windows for a in w.screen.areas),response)
 # Close only windows created by this disposable script, through existing owner.
 hybrid_window.teardown_editor_windows();yield .3
 with bpy.context.temp_override(**view()):
  if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
 from landfall_studio import sculpt
 from landfall_studio.sculpt import ops,state
 with bpy.context.temp_override(**view()):sculpt.enter();ops.run('BRUSH',name='MV')
 yield .5
 sculpt_file=ROOT.parent/'.test_env/full_ux_sculpt_file_fixture.blend'
 expected_brush=state.get().active_zbrush_brush
 ops.xpose()
 bpy.context.view_layer.objects.active.location.x=100  # Different loaded-scene position with same object name.
 bpy.ops.wm.save_as_mainfile(filepath=str(sculpt_file))
 bpy.ops.wm.open_mainfile(filepath=str(sculpt_file));yield 2
 check('saved sculpt session reopens without stale UI owners',sculpt.is_engaged() and desktop._right_dock.mode=='ZBRUSH_STUDIO',{'mode':bpy.context.mode,'right':desktop._right_dock.mode})
 check('saved sculpt brush remains selected',expected_brush=='Move' and state.get().active_zbrush_brush==expected_brush,{'before':expected_brush,'after':state.get().active_zbrush_brush})
 check('file load clears prior Xpose session cache',not ops._xpose)
 with bpy.context.temp_override(**view()):response=sculpt.return_to_maya(shape_editor=True)
 yield .4
 check('GoZ return after reopen restores Shape Editor',response.get('ok') and not sculpt.is_engaged() and desktop._right_dock.mode=='SHAPE_EDITOR',response)
 check('GoZ cannot apply prior file positions to same-named objects',abs(bpy.context.view_layer.objects.active.location.x-100)<.001)
 menus.run_op('wm.read_homefile')
 menus.run_op('wm.read_homefile')  # A second load before the deferred restore fires.
 yield 2
 check('New Scene creates fresh factory content',bpy.data.objects.get('Friend_Blockout') is None and bpy.data.objects.get('Cube') is not None)
 ui.restore_workspace_desktop(restore_script_output=False);yield .5
 bars=viewport_bar.get_bars()
 check('New Scene restores usable viewport Qt controls',bool(bars) and all(b.root.isVisible() for b in bars))
 check('rapid repeated file loads release recovery guard',desktop._scene_restore_timer is None)
 result['ok']=not result['failed'];save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
 try:return next(steps)
 except StopIteration:return None
 except Exception:
  result['failed'].append({'exception':traceback.format_exc()});save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
