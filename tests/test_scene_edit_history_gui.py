"""Real inspector input interleaved with native Undo/Redo; disposable scene."""
import bpy,sys,json,traceback,ctypes,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_HISTORY_TAG','')
OUT=ROOT/('output/scene_edit_history_gui'+TAG+'.json')
result={'ok':False,'passed':[],'failed':[],
 'boundary':'Native Blender factory scene; QtTest controls and native simulated Undo/Redo keys'}
def save():OUT.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
def check(name,yes,detail=None):
 result['passed' if yes else 'failed'].append(name if yes else {'test':name,'detail':detail});save()
def obj():return bpy.data.objects['Cube']
def view():
 w=bpy.context.window_manager.windows[0];a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
 return {'window':w,'screen':w.screen,'area':a,'region':next(r for r in a.regions if r.type=='WINDOW')}
def suite():
 bpy.context.preferences.view.show_splash=False
 bpy.ops.wm.read_homefile()
 import landfall_studio
 from landfall_studio import ui
 from landfall_studio.ui import desktop,attribute_editor,modifier_stack,hybrid_window
 from landfall_studio.commands import scene_edits
 landfall_studio.register();yield .5
 ui.restore_workspace_desktop(restore_script_output=False);yield .5
 from PySide6 import QtWidgets as W,QtCore as C,QtTest as T,QtGui as G
 from blendertk.ui_utils.blender_window import BlenderWindow
 app=W.QApplication.instance();hwnd=BlenderWindow.window_hwnd(view()['window'])
 ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd)
 if os.environ.get('LANDFALL_HISTORY_TRACE'):
  class FocusTrace(C.QObject):
   def eventFilter(self,watched,event):
    if event.type() in (C.QEvent.WindowActivate,C.QEvent.WindowDeactivate,C.QEvent.ApplicationActivate,C.QEvent.ApplicationDeactivate):
     result.setdefault('focus_trace',[]).append({'event':str(event.type()),'widget':type(watched).__name__,
       'gestures':[g.label for g in scene_edits._gestures]})
    return False
  focus_trace=FocusTrace();app.installEventFilter(focus_trace)
 def focus(field):
  G.QCursor.setPos(field.mapToGlobal(field.rect().center()))
  app.setActiveWindow(field.window());field.window().activateWindow();field.setFocus(C.Qt.MouseFocusReason)
  native=int(field.window().internalWinId() or 0)
  if native:BlenderWindow.set_keyboard_focus(native)
 def type_value(field,text):
  focus(field);line=field.lineEdit() if hasattr(field,'lineEdit') else field
  line.selectAll();T.QTest.keyClicks(line,text);T.QTest.keyClick(line,C.Qt.Key_Return)
 def click(widget):T.QTest.mouseClick(widget,C.Qt.LeftButton)
 def history(redo=False):
  focused=app.focusWidget()
  if focused:focused.clearFocus()
  app.setActiveWindow(None);ctypes.windll.user32.SetFocus(hwnd)
  c=view();r=c['region']
  c['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',x=r.x+r.width//2,y=r.y+r.height//2)
  c['window'].event_simulate(type='Z',value='PRESS',shift=redo,x=r.x+r.width//2,y=r.y+r.height//2)
  c['window'].event_simulate(type='Z',value='RELEASE',shift=redo,x=r.x+r.width//2,y=r.y+r.height//2)
 def marker(delta=.25):
  with bpy.context.temp_override(**view()):bpy.ops.transform.translate('EXEC_DEFAULT',True,value=(delta,0,0))
 def value(mat='HistoryShader',key='Roughness'):
  m=bpy.data.materials[mat];n=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
  return float(n.inputs[key].default_value)
 def drag_start(slider):
  # Native window activation is queued. Drain it before injecting a held Qt
  # gesture, just as a physical press follows pointer/window activation.
  focus(slider);yield .15
  opt=W.QStyleOptionSlider();slider.initStyleOption(opt)
  handle=slider.style().subControlRect(W.QStyle.CC_Slider,opt,W.QStyle.SC_SliderHandle,slider)
  T.QTest.mousePress(slider,C.Qt.LeftButton,pos=handle.center())
  for ratio in (.45,.6,.8):T.QTest.mouseMove(slider,C.QPoint(round(slider.width()*ratio),slider.height()//2))
 def drag_end(slider):T.QTest.mouseRelease(slider,C.Qt.LeftButton,pos=C.QPoint(round(slider.width()*.8),slider.height()//2))
 # Set up authored data once, then seed native history before user actions.
 o=obj();o.shape_key_add(name='Basis');o.shape_key_add(name='HistoryTarget').value=.2
 o.active_shape_key_index=1
 m=o.modifiers.new('HistoryBevel','BEVEL');m.width=.1
 mat=bpy.data.materials.new('HistoryShader');mat.use_nodes=True;o.data.materials.clear();o.data.materials.append(mat)
 node=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');node.inputs['Roughness'].default_value=.37;mat.roughness=.61
 with bpy.context.temp_override(**view()):bpy.ops.ed.undo_push(message='Authored history fixture')
 marker(2);yield .2
 desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
 ae=attribute_editor.ensure_attribute_editor_widget();result['dpr']=ae.spn_tx.devicePixelRatioF();type_value(ae.spn_tx,'7.5');yield .2
 check('typed AE transform changes actual data',abs(obj().location.x-7.5)<1e-5)
 history();yield .3
 check('one native Undo restores only the typed transform',abs(obj().location.x-2)<1e-5,obj().location.x)
 if abs(obj().location.x-2)>1e-5:
  from landfall_studio import keymaps
  result['history_diagnostic']={'profile':keymaps.get_active_profile(),'mode':bpy.context.mode,
   'modal':[op.bl_idname for op in view()['window'].modal_operators],
   'maps':{kc.name:{km.name:[{'id':k.idname,'active':k.active,'ctrl':k.ctrl,'shift':k.shift,'alt':k.alt,'value':k.value}
    for k in km.keymap_items if k.type=='Z'] for km in kc.keymaps if km.name in ('3D View','Object Mode','Screen')}
    for kc in bpy.context.window_manager.keyconfigs}}
  save()
 check('Undo automatically refreshes the Attribute Editor',abs(ae.spn_tx.value()-2)<.001,ae.spn_tx.value())
 history(True);yield .3
 check('native Redo restores the typed transform',abs(obj().location.x-7.5)<1e-5,obj().location.x)
 check('Redo keeps authored shape targets',obj().data.shape_keys.key_blocks.get('HistoryTarget') is not None)
 # Modifier text, invalid/no-op commits, flags, duplicate/delete.
 desktop.cycle_right_dock('MODIFIER_STACK');yield .2
 stack=desktop._right_dock._ensure_host_container().ms_panel
 def field():return next(e for e in stack.root.findChildren(W.QLineEdit) if abs(float(e.text())-.1)<.00001)
 type_value(field(),'.425');yield .2
 check('modifier field commits through native history',abs(obj().modifiers['HistoryBevel'].width-.425)<1e-5)
 history();yield .25
 check('Undo restores modifier input',abs(obj().modifiers['HistoryBevel'].width-.1)<1e-5)
 history(True);yield .25
 check('Redo restores modifier input',abs(obj().modifiers['HistoryBevel'].width-.425)<1e-5)
 prior=obj().location.x;marker();yield .2
 edit=next(e for e in stack.root.findChildren(W.QLineEdit) if abs(float(e.text())-.425)<.00001)
 type_value(edit,edit.text());yield .1
 edit=next(e for e in stack.root.findChildren(W.QLineEdit) if abs(float(e.text())-.425)<.00001)
 type_value(edit,'invalid');yield .2
 check('invalid modifier edit reports a useful error',desktop.get_command_feedback()['is_error'])
 history();yield .25
 check('invalid and unchanged edits add no phantom history step',abs(obj().location.x-prior)<1e-5 and abs(obj().modifiers['HistoryBevel'].width-.425)<1e-5)
 history(True);yield .2
 toggle=next(b for b in stack.root.findChildren(W.QToolButton) if b.text()=='V');click(toggle);yield .15
 check('modifier visibility click changes actual modifier',not obj().modifiers['HistoryBevel'].show_viewport)
 history();yield .25
 check('modifier visibility is undoable',obj().modifiers['HistoryBevel'].show_viewport)
 history(True);yield .2
 click(stack.action_buttons['duplicate']);yield .2
 check('modifier duplicate click makes one copy',len(obj().modifiers)==2)
 history();yield .25
 check('modifier duplicate has one Undo step',len(obj().modifiers)==1)
 history(True);yield .2
 click(stack.action_buttons['delete']);yield .2
 check('modifier delete click removes active card',len(obj().modifiers)==1)
 history();yield .25
 check('modifier deletion is restored by Undo',len(obj().modifiers)==2)
 history(True);yield .2
 # Shape drag is one step, preserving native marker below it.
 desktop.cycle_right_dock('SHAPE_EDITOR');yield .2
 shape=desktop._right_dock._ensure_host_container().se_widget
 row=next(r for r in range(shape._shape_table.rowCount()) if shape._shape_table.item(r,0).text()=='HistoryTarget')
 shape._shape_table.selectRow(row);yield .1
 start=obj().data.shape_keys.key_blocks['HistoryTarget'].value
 prior=obj().location.x;marker();yield .15
 yield from drag_start(shape._weight_slider);yield .1;drag_end(shape._weight_slider);yield .2
 end=obj().data.shape_keys.key_blocks['HistoryTarget'].value
 check('real shape slider drag previews and commits',end>start+.1,[start,end])
 history();yield .25
 check('one Undo restores the entire shape drag',abs(obj().data.shape_keys.key_blocks['HistoryTarget'].value-start)<1e-5,[start,end,obj().data.shape_keys.key_blocks['HistoryTarget'].value])
 check('shape Undo preserves preceding native transform',abs(obj().location.x-prior-.25)<1e-5)
 history();yield .25
 check('next Undo reaches preceding native transform',abs(obj().location.x-prior)<1e-5,obj().location.x)
 history(True);yield .2;history(True);yield .25
 check('Redo restores the whole shape drag in one step',abs(obj().data.shape_keys.key_blocks['HistoryTarget'].value-end)<1e-5)
 start=end;prior=obj().location.x;marker();yield .15
 yield from drag_start(shape._weight_slider);T.QTest.keyClick(shape._weight_slider,C.Qt.Key_Escape);yield .1
 check('Escape cancels a shape preview',abs(obj().data.shape_keys.key_blocks['HistoryTarget'].value-start)<1e-5)
 drag_end(shape._weight_slider);yield .15
 history();yield .25
 check('cancelled drag does not consume history',abs(obj().location.x-prior)<1e-5)
 history(True);yield .2
 # Shader preview must preserve both node and legacy material fields on cancel.
 desktop.cycle_right_dock('HYPERSHADE');yield .2
 hs=desktop._right_dock._ensure_host_container().hs_widget
 row=next(r for r in range(hs.tbl_mats.rowCount()) if hs.tbl_mats.item(r,0).text()=='HistoryShader');hs.tbl_mats.selectRow(row)
 start=value();rna=bpy.data.materials['HistoryShader'].roughness
 prior=obj().location.x;marker();yield .15
 yield from drag_start(hs._sliders['roughness']);yield .1;drag_end(hs._sliders['roughness']);yield .2
 end=value();check('shader drag commits actual node value',end>start+.1,[start,end])
 history();yield .25
 check('one Undo restores shader gesture and legacy field',abs(value()-start)<1e-5 and abs(bpy.data.materials['HistoryShader'].roughness-rna)<1e-5)
 history();yield .25
 check('shader drag adds exactly one history step',abs(obj().location.x-prior)<1e-5)
 history(True);yield .2;history(True);yield .2
 check('Redo restores shader end value',abs(value()-end)<1e-5)
 start=value();rna=bpy.data.materials['HistoryShader'].roughness
 yield from drag_start(hs._sliders['roughness']);T.QTest.keyClick(hs._sliders['roughness'],C.Qt.Key_Escape);yield .1
 check('shader cancellation restores exact node and RNA baselines',abs(value()-start)<1e-5 and abs(bpy.data.materials['HistoryShader'].roughness-rna)<1e-5)
 drag_end(hs._sliders['roughness']);yield .2
 check('released cancelled gestures retain no ownership',not scene_edits._gestures and not scene_edits._pending)
 # Channel Box: actual single-click text editor, MMB scrub and lock icon.
 desktop.cycle_right_dock('CHANNEL_BOX');desktop.sync_channels_now();yield .2
 channels,slots=desktop.get_panel_widget_and_slots('channels');table=channels.tbl000
 def channel_row(path,index):
  return next(i for i,d in enumerate(slots._row_descriptors) if d.get('data_path')==path and d.get('index')==index)
 row=channel_row('location',1);item=table.item(row,slots.COL_VALUE);table.scrollToItem(item);yield .1
 result['channel_diagnostic']={'visible':table.isVisible(),'rect':str(table.rect()),'cell_rect':str(table.visualItemRect(item)),
  'edit_columns':list(table._single_click_edit_columns),'flags':str(item.flags()),'row':row,'col':slots.COL_VALUE,
  'index_at':table.indexAt(table.visualItemRect(item).center()).column(),'enabled':table.isEnabled()};save()
 # QtTest bypasses the OS activation sequence. Drain that sequence before
 # delivering the single click, as a physical window activation would do.
 focus(table);yield .1
 T.QTest.mouseClick(table.viewport(),C.Qt.LeftButton,pos=table.visualItemRect(item).center());yield .1
 editors=[e for e in table.findChildren(W.QLineEdit) if e.isVisible()]
 check('Channel Box single click opens its visible editor',bool(editors),result['channel_diagnostic'])
 if not editors:raise RuntimeError('Channel Box editor did not open')
 slots._refresh_table(table)
 check('live refresh preserves an open Channel Box editor',editors[0].isVisible() and table.state()==W.QAbstractItemView.EditingState)
 type_value(editors[0],'3.25');yield .2
 check('single-click Channel Box editor commits actual transform',abs(obj().location.y-3.25)<1e-5)
 history();yield .25
 check('Channel Box typed edit has native Undo',abs(obj().location.y)<1e-5,obj().location.y)
 history(True);yield .25
 check('Channel Box typed edit has native Redo',abs(obj().location.y-3.25)<1e-5,obj().location.y)
 def scrub_start():
  row=channel_row('location',1);cell=table.visualItemRect(table.item(row,slots.COL_VALUE)).center()
  focus(table);T.QTest.mousePress(table.viewport(),C.Qt.MiddleButton,pos=cell)
  for dx in (10,25,50):
   p=cell+C.QPoint(dx,0);global_p=table.viewport().mapToGlobal(p)
   G.QCursor.setPos(global_p)
   app.sendEvent(table.viewport(),G.QMouseEvent(C.QEvent.MouseMove,C.QPointF(p),C.QPointF(global_p),C.Qt.NoButton,C.Qt.MiddleButton,C.Qt.NoModifier))
  return cell
 def scrub_end(cell):T.QTest.mouseRelease(table.viewport(),C.Qt.MiddleButton,pos=cell+C.QPoint(50,0))
 prior=obj().location.x;marker();yield .15
 start=obj().location.y;cell=scrub_start();yield .1;scrub_end(cell);yield .15;end=obj().location.y
 check('real Channel Box MMB drag changes its original channel',end>start+.1,[start,end])
 history();yield .25
 check('Channel Box scrub is one Undo step',abs(obj().location.y-start)<1e-5,obj().location.y)
 history();yield .25
 check('Channel Box scrub preserves preceding native history',abs(obj().location.x-prior)<1e-5,obj().location.x)
 history(True);yield .2;history(True);yield .2
 check('Channel Box scrub redoes its complete end value',abs(obj().location.y-end)<1e-5,obj().location.y)
 start=end;cell=scrub_start();T.QTest.keyClick(table,C.Qt.Key_Escape);yield .1
 check('Escape cancels Channel Box MMB preview',abs(obj().location.y-start)<1e-5,obj().location.y)
 scrub_end(cell);yield .1
 # Change selection before Qt can deliver SelectionChanged/Enter callbacks.
 def other_fixture():
  other=bpy.data.objects.new('HistoryOther',bpy.data.meshes.new('HistoryOtherMesh'))
  bpy.context.scene.collection.objects.link(other);other.location.y=.75
 scene_edits.commit('Other object fixture',other_fixture);yield .15
 def select(name):
  for o in bpy.context.selected_objects:o.select_set(False)
  o=bpy.data.objects[name];o.select_set(True);bpy.context.view_layer.objects.active=o
 def open_y():
  row=channel_row('location',1);item=table.item(row,slots.COL_VALUE);table.scrollToItem(item)
  T.QTest.mouseClick(table.viewport(),C.Qt.LeftButton,pos=table.visualItemRect(item).center())
  return table.cellWidget(row,slots.COL_VALUE)
 focus(table);yield .1;editor=open_y();yield .1
 before=obj().location.y;editor.selectAll();T.QTest.keyClicks(editor,'9.125')
 select('HistoryOther');T.QTest.keyClick(editor,C.Qt.Key_Return);yield .2
 check('pending Channel Box text cannot mutate a new selection',abs(bpy.data.objects['HistoryOther'].location.y-.75)<1e-5)
 check('selection change discards text without changing original object',abs(obj().location.y-before)<1e-5)
 select('Cube');desktop.sync_channels_now();yield .15
 cell=scrub_start();select('HistoryOther')
 p=cell+C.QPoint(70,0);global_p=table.viewport().mapToGlobal(p)
 app.sendEvent(table.viewport(),G.QMouseEvent(C.QEvent.MouseMove,C.QPointF(p),C.QPointF(global_p),C.Qt.NoButton,C.Qt.MiddleButton,C.Qt.NoModifier))
 desktop.sync_channels_now();yield .15
 check('selection change cancels original Channel Box scrub preview',abs(obj().location.y-before)<1e-5,obj().location.y)
 check('cancelled Channel Box scrub leaves new selection unchanged',abs(bpy.data.objects['HistoryOther'].location.y-.75)<1e-5)
 scrub_end(cell);select('Cube');desktop.sync_channels_now();yield .15
 row=channel_row('location',1)
 T.QTest.mouseClick(table.viewport(),C.Qt.LeftButton,pos=table.visualItemRect(table.item(row,slots.COL_LOCK)).center());yield .15
 check('Channel Box lock icon locks its actual channel',obj().lock_location[1])
 history();yield .25
 check('Channel Box lock icon is undoable',not obj().lock_location[1])
 history(True);yield .25
 check('Channel Box lock icon is redoable',obj().lock_location[1])
 from landfall_studio.ui import channel_box_ext
 extra=channel_box_ext.ensure_channel_box_extensions(channels);tree=extra.tree_inputs
 node=next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if tree.topLevelItem(i).text(0)=='HistoryBevel')
 node.setExpanded(True)
 child=next(node.child(i) for i in range(node.childCount()) if node.child(i).data(0,C.Qt.UserRole)[1]=='width')
 tree.scrollToItem(child);focus(tree);yield .1
 cell=tree.visualItemRect(child);pos=C.QPoint(tree.columnViewportPosition(1)+tree.columnWidth(1)//2,cell.center().y())
 T.QTest.mouseClick(tree.viewport(),C.Qt.LeftButton,pos=pos);T.QTest.mouseDClick(tree.viewport(),C.Qt.LeftButton,pos=pos);yield .1
 editor=next(e for e in tree.findChildren(W.QLineEdit) if e.isVisible());type_value(editor,'.23125');yield .2
 check('Channel Box INPUTS editor changes exact modifier value',abs(obj().modifiers['HistoryBevel'].width-.23125)<1e-6,{'value':obj().modifiers['HistoryBevel'].width,'feedback':desktop.get_command_feedback()})
 history();yield .25
 check('Channel Box INPUTS editor has native Undo',abs(obj().modifiers['HistoryBevel'].width-.425)<1e-5)
 history(True);yield .25
 check('Channel Box INPUTS editor has native Redo',abs(obj().modifiers['HistoryBevel'].width-.23125)<1e-6)
 count=len(obj().modifiers);click(extra.btn_add_geonodes);yield .2
 check('Channel Box Add GeoNodes button adds one native modifier',len(obj().modifiers)==count+1)
 history();yield .25
 check('Channel Box Add GeoNodes button has one Undo step',len(obj().modifiers)==count)
 history(True);yield .25
 check('Channel Box Add GeoNodes button is redoable',len(obj().modifiers)==count+1)
 # Remove the generated network through the same native history service so the
 # graph-window scenario below can target its one purpose-built Amount socket.
 scene_edits.commit('Remove generated fixture nodes',lambda:obj().modifiers.remove(obj().modifiers['geoNodes_Procedural1']));yield .15
 # An interrupted shader gesture restores the original material, including
 # legacy non-node materials whose node creation must be deferred to commit.
 desktop.cycle_right_dock('HYPERSHADE');yield .15
 row=next(r for r in range(hs.tbl_mats.rowCount()) if hs.tbl_mats.item(r,0).text()=='HistoryShader');hs.tbl_mats.selectRow(row)
 start=value();yield from drag_start(hs._sliders['roughness']);app.sendEvent(hs.window(),C.QEvent(C.QEvent.WindowDeactivate));yield .1
 check('focus loss restores shader preview',abs(value()-start)<1e-5)
 drag_end(hs._sliders['roughness']);yield .1
 def precise_fixture():
  m=bpy.data.materials['HistoryShader'];next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Roughness'].default_value=.371234
 scene_edits.commit('Precise shader fixture',precise_fixture);yield .15
 prior=obj().location.x;marker();yield .1
 slider=hs._sliders['roughness'];focus(slider);opt=W.QStyleOptionSlider();slider.initStyleOption(opt)
 handle=slider.style().subControlRect(W.QStyle.CC_Slider,opt,W.QStyle.SC_SliderHandle,slider)
 start=value();T.QTest.mouseClick(slider,C.Qt.LeftButton,pos=handle.center());yield .15
 check('stationary shader handle tap preserves full precision',value()==start,[start,value()])
 history();yield .25
 check('stationary shader handle tap adds no history step',abs(obj().location.x-prior)<1e-5)
 history(True);yield .15
 def legacy_fixture():
  legacy=bpy.data.materials.new('HistoryLegacy');legacy.use_nodes=False;legacy.roughness=.29
  result['material_capability']={'non_node_material_available':not legacy.use_nodes,'new_material_has_node_tree':bool(legacy.node_tree)}
 scene_edits.commit('Legacy material fixture',legacy_fixture);yield .2
 row=next(r for r in range(hs.tbl_mats.rowCount()) if hs.tbl_mats.item(r,0).text()=='HistoryLegacy');hs.tbl_mats.selectRow(row)
 start=value('HistoryLegacy');rna=bpy.data.materials['HistoryLegacy'].roughness
 def material_state():
  m=bpy.data.materials['HistoryLegacy'];return (m.use_nodes,m.roughness,value('HistoryLegacy'),tuple((n.name,n.type) for n in m.node_tree.nodes),len(m.node_tree.links))
 original=material_state()
 yield from drag_start(hs._sliders['roughness']);T.QTest.keyClick(hs._sliders['roughness'],C.Qt.Key_Escape);yield .1;drag_end(hs._sliders['roughness']);yield .1
 check('cancelled default shader drag preserves its exact original graph and values',material_state()==original,[original,material_state()])
 yield from drag_start(hs._sliders['roughness']);drag_end(hs._sliders['roughness']);yield .2
 check('default shader drag commits actual node value',bpy.data.materials['HistoryLegacy'].use_nodes and value('HistoryLegacy')>.5)
 history();yield .25
 check('Undo restores default shader original graph and values',material_state()==original,[original,material_state()])
 history(True);yield .25
 check('Redo restores default shader gesture',bpy.data.materials['HistoryLegacy'].use_nodes and value('HistoryLegacy')>.5)
 start=value('HistoryShader');yield from drag_start(hs._sliders['roughness']);yield .1
 scene_edits.commit('Delete preview material',lambda:bpy.data.materials.remove(bpy.data.materials['HistoryLegacy']));yield .15
 drag_end(hs._sliders['roughness']);yield .1
 check('material deletion safely retires a held shader gesture',not scene_edits._gestures and not hs._sliders['roughness'].isSliderDown())
 check('deleted material gesture cannot affect another material',value('HistoryShader')==start)
 history();yield .25
 check('Undo after material deletion restores its pre-gesture value',bpy.data.materials.get('HistoryLegacy') is not None and value('HistoryLegacy')>.5)
 history(True);yield .25
 prior=obj().location.x;marker();yield .1
 before_materials={m.name for m in bpy.data.materials};click(next(b for b in hs.findChildren(W.QPushButton) if b.text()=='Chrome'));yield .2
 created={m.name for m in bpy.data.materials}-before_materials
 check('shader preset button creates and assigns one material',len(created)==1 and obj().active_material.name in created,
  {'created':list(created),'active_material':obj().active_material.name,'selected':[o.name for o in bpy.context.selected_objects],'feedback':desktop.get_command_feedback()})
 history();yield .25
 check('one Undo removes shader preset and assignment',{m.name for m in bpy.data.materials}==before_materials)
 history();yield .25
 check('shader preset preserves preceding native history',abs(obj().location.x-prior)<1e-5)
 history(True);yield .2;history(True);yield .2
 for label,fields in (
  ('Chrome',{'Metallic':1,'Roughness':.08}),('Brushed Metal',{'Metallic':1,'Roughness':.5}),
  ('Gold',{'Metallic':1,'Roughness':.2}),('Car Paint',{'Coat Weight':1,'Roughness':.24}),
  ('Glass',{'Transmission Weight':1,'Roughness':0}),('Skin SSS',{'Subsurface Weight':.2,'Roughness':.4}),
  ('Plastic',{'Metallic':0,'Roughness':.35}),('Emission',{'Emission Strength':2})):
  before_names={m.name for m in bpy.data.materials};old_material=obj().active_material.name
  click(next(b for b in hs.findChildren(W.QPushButton) if b.text()==label));yield .15
  new_names={m.name for m in bpy.data.materials}-before_names
  material=obj().active_material
  node=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
  check(label+' button creates and assigns its actual shader',len(new_names)==1 and material.name in new_names and
    all(abs(node.inputs[field].default_value-expected)<1e-5 for field,expected in fields.items()),{'created':list(new_names),'active':material.name})
  history();yield .2
  check(label+' creation and assignment undo together',{m.name for m in bpy.data.materials}==before_names and obj().active_material.name==old_material)
  history(True);yield .2
  check(label+' creation and assignment redo together',new_names.issubset({m.name for m in bpy.data.materials}) and obj().active_material.name in new_names)
 # Actual node editor window and its production Group Inputs controller.
 def fixture_nodes():
  group=bpy.data.node_groups.new('HistoryNodes','GeometryNodeTree')
  group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
  group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
  socket=group.interface.new_socket(name='Amount',in_out='INPUT',socket_type='NodeSocketFloat')
  ni=group.nodes.new('NodeGroupInput');no=group.nodes.new('NodeGroupOutput');group.links.new(ni.outputs['Geometry'],no.inputs['Geometry'])
  from landfall_studio.ui.channel_box_ext import _set_gn_socket_value
  mod=obj().modifiers.new('HistoryNodes','NODES');mod.node_group=group;_set_gn_socket_value(mod,socket.identifier,.2)
  return {'ok':True}
 scene_edits.commit('Node fixture',fixture_nodes);yield .2
 desktop.cycle_right_dock('MODIFIER_STACK');yield .15
 graph=next(b for b in stack.root.findChildren(W.QPushButton) if b.text()=='Graph ↗');click(graph);yield .7
 check('Blender Geometry Nodes graph opens with Qt controls',len(bpy.context.window_manager.windows)==2 and bool(modifier_stack._group_input_instances))
 inputs=modifier_stack._group_input_instances[-1]
 edit=next(e for e in inputs.root.findChildren(W.QLineEdit) if e.text().startswith('0.2'))
 type_value(edit,'.65');yield .15
 ident=next(s.identifier for s in bpy.data.node_groups['HistoryNodes'].interface.items_tree if s.name=='Amount')
 from landfall_studio.ui.channel_box_ext import _get_gn_socket_value
 def gn_value():return _get_gn_socket_value(obj().modifiers['HistoryNodes'],ident)
 check('native Group Inputs edits actual node modifier',abs(gn_value()-.65)<1e-5)
 history();yield .25
 check('Undo restores Geometry Nodes input',abs(gn_value()-.2)<1e-5)
 history(True);yield .25
 check('Redo restores Geometry Nodes input',abs(gn_value()-.65)<1e-5)
 check('history service releases every synchronous callback and gesture',not scene_edits._pending and not scene_edits._gestures)
 # Replacing the scene while a gesture is held must abandon old RNA closures.
 from landfall_studio.ui import menus,channel_history
 desktop.cycle_right_dock('SHAPE_EDITOR');yield .15
 shape=desktop._right_dock._ensure_host_container().se_widget
 row=next(r for r in range(shape._shape_table.rowCount()) if shape._shape_table.item(r,0).text()=='HistoryTarget');shape._shape_table.selectRow(row)
 saved_weight=obj().data.shape_keys.key_blocks['HistoryTarget'].value
 path=ROOT.parent/'.test_env'/'history_reload_fixture.blend'
 bpy.ops.wm.save_as_mainfile(filepath=str(path),copy=True);yield .2
 yield from drag_start(shape._weight_slider);yield .1
 check('scene-replacement scenario starts a real held gesture',bool(scene_edits._gestures))
 menus.run_op('wm.open_mainfile',filepath=str(path));yield 1.5
 shape=desktop._right_dock._ensure_host_container().se_widget
 check('scene replacement abandons stale gesture ownership',not scene_edits._gestures and not getattr(shape,'_weight_gesture',None))
 check('scene replacement preserves saved shape value',abs(obj().data.shape_keys.key_blocks['HistoryTarget'].value-saved_weight)<1e-5)
 drag_end(shape._weight_slider);yield .1
 check('post-load pen release cannot apply a stale preview',abs(obj().data.shape_keys.key_blocks['HistoryTarget'].value-saved_weight)<1e-5)
 landfall_studio.unregister();yield .1
 check('unregister removes local channel history adapters',not channel_history._adapters and not scene_edits._gestures and not scene_edits._pending)
 landfall_studio.register();ui.restore_workspace_desktop(restore_script_output=False);yield .5
 desktop.get_panel_widget_and_slots('channels');desktop.get_panel_widget_and_slots('channels')
 check('re-register installs one live channel history adapter',len(channel_history._adapters)==1,len(channel_history._adapters))
 result['ok']=not result['failed'];save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
 try:return next(steps)
 except StopIteration:return None
 except Exception:
  result['failed'].append({'exception':traceback.format_exc()});save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
