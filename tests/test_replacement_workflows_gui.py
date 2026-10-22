"""Real inspectors/native input across rotation modes and Layer/Divide/GoZ."""
import bpy,sys,json,traceback,ctypes,math,os
from pathlib import Path
from mathutils import Euler
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/replacement_workflows_gui.json'
result={'ok':False,'passed':[],'failed':[],
 'boundary':'Disposable native Blender scene; QtTest clicks/typing and native simulated viewport input. No physical tablet or external Maya claim.'}
def save():OUT.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
def check(name,yes,detail=None):
 result['passed' if yes else 'failed'].append(name if yes else {'test':name,'detail':detail});save()
def view():
 w=bpy.context.window_manager.windows[0];a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
 return dict(window=w,screen=w.screen,area=a,region=next(r for r in a.regions if r.type=='WINDOW'))
def obj():return bpy.data.objects['Rotation Fixture']
def surface():return bpy.data.objects['Layer Return Fixture']
def event(kind,value='PRESS',dx=0,**mods):
 c=view();r=c['region'];c['window'].event_simulate(type=kind,value=value,x=r.x+int(r.width*.6)+dx,y=r.y+int(r.height*.45),**mods)
def native_focus():
 from PySide6 import QtWidgets as W
 from blendertk.ui_utils.blender_window import BlenderWindow
 app=W.QApplication.instance()
 if app.focusWidget():app.focusWidget().clearFocus()
 app.setActiveWindow(None);c=view();r=c['region'];hwnd=BlenderWindow.window_hwnd(c['window']);origin=BlenderWindow.client_origin(hwnd)
 ctypes.windll.user32.SetCursorPos(origin[0]+r.x+int(r.width*.6),origin[1]+c['window'].height-1-r.y-int(r.height*.45))
 BlenderWindow.set_keyboard_focus(hwnd)
def key(kind,**mods):
 native_focus();event('MOUSEMOVE','NOTHING');event(kind,**mods);event(kind,'RELEASE',**mods)
def orientation(o):
 bpy.context.view_layer.update();return o.matrix_basis.to_quaternion().copy()
def same(a,b):return abs(a.dot(b))>1-1e-6
def point_difference(a,b):
 if len(a)!=len(b):return {'lengths':[len(a),len(b)]}
 return {'max_delta':max((sum((x-y)**2 for x,y in zip(p,q))**.5 for p,q in zip(a,b)),default=0),
         'changed':sum(p!=q for p,q in zip(a,b))}
def points_close(a,b):
 # The native float32 Multires evaluation changes a few ulps when its grids
 # are flushed/rebuilt. The unit-radius fixture tolerance is 1e-6 local units.
 return len(a)==len(b) and point_difference(a,b)['max_delta']<1e-6

def suite():
 bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
 import landfall_studio
 from landfall_studio import ui,sculpt
 from landfall_studio.ui import desktop,attribute_editor,channel_box_ext,zbrush_panel
 from landfall_studio.commands import scene_edits,registry
 from landfall_studio.modeling import rotation
 from landfall_studio.sculpt import ops,state
 landfall_studio.register();ui.restore_workspace_desktop(restore_script_output=False);yield .8
 from PySide6 import QtCore as C,QtWidgets as W,QtGui as G,QtTest as T
 from blendertk.ui_utils.blender_window import BlenderWindow
 app=W.QApplication.instance();hwnd=BlenderWindow.window_hwnd(view()['window'])
 ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd);yield .3
 bpy.context.object.name='Rotation Fixture'
 def focus(widget):
  G.QCursor.setPos(widget.mapToGlobal(widget.rect().center()));app.setActiveWindow(widget.window());widget.window().activateWindow();widget.setFocus()
  hwnd=int(widget.window().internalWinId() or 0)
  if hwnd:BlenderWindow.set_keyboard_focus(hwnd)
 def type_value(widget,text,activate=True):
  if activate:focus(widget);yield .15
  edit=widget.lineEdit() if hasattr(widget,'lineEdit') else widget
  edit.selectAll();T.QTest.keyClicks(edit,text);T.QTest.keyClick(edit,C.Qt.Key_Return);yield .2
 def seed(mode):
  o=obj();o.animation_data_clear();o.lock_rotation=(False,False,False);o.lock_rotation_w=False;o.lock_rotations_4d=False
  o.rotation_mode='XYZ';o.rotation_euler=(.23,.38,-.41);rotation.set_mode(o,mode)
  o.rotation_euler=(0,0,0)
 for mode in (() if os.environ.get('LANDFALL_WORKFLOW_SCULPT_ONLY') else ('QUATERNION','AXIS_ANGLE')):
  seed(mode);baseline=orientation(obj());raw=tuple(obj().rotation_euler)
  with bpy.context.temp_override(**view()):bpy.ops.ed.undo_push(message=mode+' rotation fixture')
  desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
  ae=attribute_editor.ensure_attribute_editor_widget();snap=attribute_editor.get_attribute_editor_snapshot(obj())
  check(mode+' AE displays actual orientation',all(abs(v-math.degrees(x))<.001 for v,x in zip(snap['transform']['rotation_deg'],baseline.to_euler('XYZ'))))
  yield from type_value(ae.spn_rx,'30')
  expected=baseline.to_euler('XYZ');expected.x=math.radians(30);changed=orientation(obj())
  check(mode+' AE edit rotates actual object',same(changed,expected.to_quaternion()) and not same(changed,baseline))
  check(mode+' AE preserves native mode and unused Euler storage',obj().rotation_mode==mode and tuple(obj().rotation_euler)==raw)
  key('Z');yield .25
  check(mode+' AE Undo restores exact orientation',same(orientation(obj()),baseline))
  key('Z',shift=True);yield .25
  check(mode+' AE Redo restores actual orientation',same(orientation(obj()),changed))
  desktop.cycle_right_dock('CHANNEL_BOX');desktop.sync_channels_now();yield .25
  channels,slots=desktop.get_panel_widget_and_slots('channels');table=channels.tbl000;path='rotation_quaternion' if mode=='QUATERNION' else 'rotation_axis_angle'
  descs=[d for d in slots._row_descriptors if d['data_path']==path]
  check(mode+' Channel Box exposes four native rotation channels',len(descs)==4,[d['name'] for d in descs])
  check(mode+' Channel Box does not show unused Euler channels',not any(d['data_path']=='rotation_euler' for d in slots._row_descriptors))
  component=1 if mode=='QUATERNION' else 0
  row=next(i for i,d in enumerate(slots._row_descriptors) if d['data_path']==path and d['index']==component)
  descriptor=dict(slots._row_descriptors[row]);item=table.item(row,slots.COL_VALUE);table.scrollToItem(item)
  focus(table);yield .15
  T.QTest.mouseClick(table.viewport(),C.Qt.LeftButton,pos=table.visualItemRect(item).center());yield .1
  editors=[e for e in table.findChildren(W.QLineEdit) if e.isVisible()]
  check(mode+' native rotation channel opens on one click',bool(editors))
  if not editors:raise RuntimeError('Rotation channel editor missing')
  yield .3
  retained=any(e is editors[0] and e.isVisible() for e in table.findChildren(W.QLineEdit)) and table.state()==W.QAbstractItemView.EditingState
  check(mode+' channel editor stays open while the user pauses',retained)
  if not retained:raise RuntimeError('Rotation editor was lost during an idle hold')
  old=tuple(getattr(obj(),path));text='.45' if mode=='QUATERNION' else '65'
  yield from type_value(editors[0],text,activate=False)
  edited=tuple(getattr(obj(),path));after=orientation(obj())
  check(mode+' Channel Box changes correct native component',abs(edited[component]-(.45 if mode=='QUATERNION' else math.radians(65)))<1e-5 and not same(changed,after),edited)
  key('Z');yield .25
  check(mode+' channel Undo restores exact raw representation',tuple(getattr(obj(),path))==old)
  key('Z',shift=True);yield .25
  check(mode+' channel Redo restores native component',tuple(getattr(obj(),path))==edited)
  # Existing controller actions must use the same RNA path for animation/locks.
  slots.controller.set_key_at_current_time([obj()],descriptor);yield .2
  curves=list(slots.controller._iter_fcurves(obj()))
  check(mode+' channel keys native path and component',any(fc.data_path==path and fc.array_index==component for fc in curves) and not any(fc.data_path=='rotation_euler' for fc in curves))
  check(mode+' keyed channel indicator matches native animation',slots.controller.classify_connection(obj(),descriptor)=='keyframe_active')
  obj().animation_data_clear();slots.controller.set_lock([obj()],descs,True);yield .1
  check(mode+' native rotation locks apply to four components',obj().lock_rotation_w and all(obj().lock_rotation) and all(slots.controller.is_locked(obj(),d) for d in descs))
  slots.controller.set_lock([obj()],descs,False);slots.controller.reset_to_default([obj()],descs);yield .15
  check(mode+' Reset restores native identity rotation',same(orientation(obj()),Euler((0,0,0)).to_quaternion()))
  seed(mode);desktop.sync_channels_now();channel_box_ext.select_channels_in_ui([]);table.clearSelection();yield .1
  registry.set_active_tool('ROTATE');registry.set_active_axis('Z');before=rotation.snapshot(obj());q=orientation(obj())
  with bpy.context.temp_override(**view()):bpy.ops.ed.undo_push(message=mode+' native rotation baseline')
  native_focus();yield .15;event('MOUSEMOVE','NOTHING');event('MIDDLEMOUSE');yield .1
  for dx in (10,25,50):event('MOUSEMOVE','NOTHING',dx);yield .06
  check(mode+' native viewport MMB rotates actual orientation',not same(orientation(obj()),q))
  event('ESC',dx=50);event('ESC','RELEASE',50);event('MIDDLEMOUSE','RELEASE',50);yield .2
  check(mode+' Escape restores every raw rotation value',rotation.snapshot(obj())==before)
  native_focus();yield .1;event('MIDDLEMOUSE');yield .1
  for dx in (10,25,50):event('MOUSEMOVE','NOTHING',dx);yield .06
  event('MIDDLEMOUSE','RELEASE',50);yield .2;after=orientation(obj())
  check(mode+' released viewport MMB commits native rotation',not same(after,q) and obj().rotation_mode==mode)
  key('Z');yield .25
  check(mode+' viewport rotation has one native Undo',same(orientation(obj()),q),[tuple(orientation(obj())),tuple(q)])
  key('Z',shift=True);yield .25
  check(mode+' viewport rotation has native Redo',same(orientation(obj()),after))
  # A rotation-mode change must not jump the object.
  before=orientation(obj());attribute_editor.set_attribute_editor_value('transform','rotation_mode','ZYX',obj())
  check(mode+' changing rotation representation preserves orientation',same(orientation(obj()),before))
 # Mixed modes share location/scale, never cross-wire native rotation indices.
 from blendertk.node_utils.attributes.channels._channels import Channels
 other=obj().copy();other.data=obj().data.copy();bpy.context.collection.objects.link(other);other.rotation_mode='QUATERNION'
 mixed=Channels.collect_channels([obj(),other],'all')
 check('mixed rotation modes do not cross-wire rotation components',not any(d['data_path'].startswith('rotation_') for d in mixed))
 bpy.data.objects.remove(other,do_unlink=True)
 # Start a real base layer, Divide with smooth-preview ownership, preserve exact
 # deltas/detail and saved state, then return through the actual GoZ tray button.
 with bpy.context.temp_override(**view()):
  obj().hide_set(True)
  bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=12)
  o=bpy.context.object;o.name='Layer Return Fixture';bpy.ops.landfall.smooth_preview(mode='SMOOTH')
 sculpt.enter();yield .5
 ops.run('LAYER',action='NEW',name='Recorded Form Pass');yield .2
 surface().active_shape_key.data[0].co.z+=.1
 basis=tuple(surface().data.shape_keys.reference_key.data[0].co);target=tuple(surface().active_shape_key.data[0].co)
 ops.run('DIVIDE');yield .4
 check('Divide stops base-layer recording at grid detail',not state.get().record_layer and surface().active_shape_key_index==0)
 check('Divide retains remembered exact Shape Editor target',state.get().record_layer_name=='Recorded Form Pass' and ops.shape_editor_return_key().name=='Recorded Form Pass')
 check('Divide preserves authored base layer delta',tuple(surface().data.shape_keys.key_blocks['Recorded Form Pass'].data[0].co)==target and tuple(surface().data.shape_keys.reference_key.data[0].co)==basis)
 check('Divide uses one visible subdivision owner',len([m for m in surface().modifiers if m.show_viewport and m.type in ('SUBSURF','MULTIRES')])==1)
 def evaluated_points():
  # Native Multires strokes live in the Sculpt grids/PBVH until mode exit.
  # Observe their flushed evaluated surface, rather than Sculpt's base mesh.
  with ops.object_mode():
   bpy.context.view_layer.update();e=surface().evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=e.to_mesh()
   try:return [tuple(v.co) for v in mesh.vertices]
   finally:e.to_mesh_clear()
 ops.run('FRAME');yield .3
 from bpy_extras import view3d_utils
 c=view();r=c['region'];xy=(r.width//2,r.height//2)
 origin=view3d_utils.region_2d_to_origin_3d(r,c['area'].spaces.active.region_3d,xy)
 direction=view3d_utils.region_2d_to_vector_3d(r,c['area'].spaces.active.region_3d,xy)
 hit=bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),origin,direction)
 check('detail stroke starts on actual SubTool surface',hit[0] and hit[4]==surface(),hit[4].name if hit[0] else 'no hit')
 if not hit[0] or hit[4]!=surface():raise RuntimeError('Sculpt fixture must hit its actual surface before stroke/Undo')
 native_focus()
 origin_px=BlenderWindow.client_origin(hwnd)
 ctypes.windll.user32.SetCursorPos(origin_px[0]+r.x+xy[0],origin_px[1]+c['window'].height-1-r.y-xy[1]);yield .15
 from landfall_studio.sculpt import gestures
 result['detail_setup']={'brush':state.brush().name,'strength':state.brush().strength,'size':state.brush().size,'record':state.get().record_layer,
  'active_key':surface().active_shape_key_index,'mode':bpy.context.mode,'level':ops.multires().sculpt_levels,
  'tool':c['window'].workspace.tools.from_space_view3d_mode('SCULPT',create=False).idname}
 before_detail=evaluated_points()
 def stroke_event(kind,value,dx=0):c['window'].event_simulate(type=kind,value=value,x=r.x+xy[0]+dx,y=r.y+xy[1])
 stroke_event('MOUSEMOVE','NOTHING');stroke_event('LEFTMOUSE','PRESS');yield .1
 result['detail_setup']['press_modals']=[o.bl_idname for o in c['window'].modal_operators]
 check('detail stroke is owned by native Sculpt paint', 'SCULPT_OT_brush_stroke' in result['detail_setup']['press_modals'])
 for dx in (8,16,24,32,40):stroke_event('MOUSEMOVE','NOTHING',dx);yield .06
 stroke_event('LEFTMOUSE','RELEASE',40);yield .3
 detail=evaluated_points()
 result['detail_setup']['fallbacks']=[(config.name,item.active,item.type,item.value,item.ctrl,item.shift,item.alt) for config in (bpy.context.window_manager.keyconfigs.addon,bpy.context.window_manager.keyconfigs.user) for item in config.keymaps['3D View'].keymap_items if item.idname=='sculpt.brush_stroke']
 result['detail_setup']['gestures']=list(gestures.history[-5:]);result['detail_setup']['modal']=[o.bl_idname for o in c['window'].modal_operators]
 result['detail_setup']['surface_change']=point_difference(detail,before_detail)
 changed=point_difference(detail,before_detail)['max_delta']>1e-4
 check('native stroke adds high-resolution Multires detail',changed,result['detail_setup']['surface_change'])
 if not changed:raise RuntimeError('Detail must change before testing its history or persistence')
 check('grid detail does not overwrite base layer or Basis',tuple(surface().data.shape_keys.key_blocks['Recorded Form Pass'].data[0].co)==target and tuple(surface().data.shape_keys.reference_key.data[0].co)==basis)
 key('Z');yield .25
 undo_points=evaluated_points();check('native Undo restores pre-detail surface',points_close(undo_points,before_detail),point_difference(undo_points,before_detail))
 key('Z',shift=True);yield .25
 redo_points=evaluated_points();check('native Redo restores high-resolution detail',points_close(redo_points,detail),point_difference(redo_points,detail))
 fixture=ROOT.parent/'.test_env/replacement_workflow_fixture.blend'
 bpy.ops.wm.save_as_mainfile(filepath=str(fixture),copy=True);yield .2
 from landfall_studio.ui import menus
 menus.run_op('wm.open_mainfile',filepath=str(fixture));yield 1.5
 check('save/reopen retains remembered sculpt layer',ops.shape_editor_return_key().name=='Recorded Form Pass')
 check('save/reopen retains base target data and Multires',tuple(surface().data.shape_keys.key_blocks['Recorded Form Pass'].data[0].co)==target and ops.multires().total_levels==1)
 saved_points=evaluated_points();check('save/reopen retains high-resolution detail',points_close(saved_points,detail),point_difference(saved_points,detail))
 sculpt.enter();yield .5
 panel=zbrush_panel._panels[0];panel.palettes['Layers'].setChecked(True);yield .2
 button=next(b for b in panel.content.findChildren(W.QPushButton) if b.text()=='⇄ GoZ to Shape Editor')
 ancestor=button.parentWidget()
 while ancestor and not isinstance(ancestor,W.QScrollArea):ancestor=ancestor.parentWidget()
 if ancestor:ancestor.ensureWidgetVisible(button)
 focus(button);yield .15;T.QTest.mouseClick(button,C.Qt.LeftButton);yield .6
 check('GoZ button exits Sculpt and opens Shape Editor',bpy.context.mode=='OBJECT' and desktop._right_dock.mode=='SHAPE_EDITOR',bpy.context.mode)
 check('GoZ restores exact remembered active shape key',surface().active_shape_key.name=='Recorded Form Pass')
 shape=desktop._right_dock._ensure_host_container().se_widget
 check('Shape Editor shows returned mesh and exact layer',shape._target_mesh==surface() and shape._selected_key_name=='Recorded Form Pass',[shape._target_mesh,shape._selected_key_name])
 check('GoZ preserves base delta and high-resolution level',tuple(surface().data.shape_keys.key_blocks['Recorded Form Pass'].data[0].co)==target and ops.multires().total_levels==1)
 returned_points=evaluated_points();check('GoZ preserves evaluated high-resolution detail',points_close(returned_points,detail),point_difference(returned_points,detail))
 # Existing smooth-preview wrapper must continue using Multires after return.
 def evaluated_count():
  bpy.context.view_layer.update();e=surface().evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
  try:return len(m.vertices)
  finally:e.to_mesh_clear()
 count=evaluated_count()
 with bpy.context.temp_override(**view()):bpy.ops.landfall.smooth_preview(mode='SMOOTH')
 check('smooth preview after GoZ does not add duplicate subdivision',evaluated_count()==count and len([m for m in surface().modifiers if m.show_viewport and m.type in ('SUBSURF','MULTIRES')])==1)
 for repeat in range(3):
  sculpt.enter();yield .3;sculpt.return_to_maya(shape_editor=True);yield .3
  check('repeated Sculpt/GoZ preserves exact layer '+str(repeat+1),surface().active_shape_key.name=='Recorded Form Pass' and shape._selected_key_name=='Recorded Form Pass')
 # Leave A in Modeling, then select B there (rather than through SubTools).
 # Both contain A's remembered name, so a stale global name cannot pass by luck.
 with bpy.context.temp_override(**view()):
  bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_uv_sphere_add(segments=8,ring_count=6,location=(4,0,0))
 second=bpy.context.object;second.name='Second Layer Fixture'
 second.shape_key_add(name='Basis');second.shape_key_add(name='Recorded Form Pass');second.shape_key_add(name='Second Object Layer').value=1
 second['_landfall_sculpt_record_name']='Second Object Layer';second['_landfall_sculpt_record']=False;second.active_shape_key_index=0
 sculpt.enter();yield .3
 check('Modeling selection hydrates the selected mesh layer state',state.get().record_layer_name=='Second Object Layer')
 sculpt.return_to_maya(shape_editor=True);yield .3
 check('GoZ restores second mesh own target despite shared layer names',second.active_shape_key.name=='Second Object Layer' and shape._target_mesh==second and shape._selected_key_name=='Second Object Layer')
 second.active_shape_key_index=0;second.shape_key_remove(second.data.shape_keys.key_blocks['Second Object Layer'])
 check('deleted remembered layer is not replaced by another target',ops.shape_editor_return_key(second) is None)
 with bpy.context.temp_override(**view()):
  second.select_set(False);surface().select_set(True);bpy.context.view_layer.objects.active=surface()
 surface().active_shape_key_index=0;sculpt.enter();yield .3;sculpt.return_to_maya(shape_editor=True);yield .3
 check('returning to first mesh restores its own layer',surface().active_shape_key.name=='Recorded Form Pass' and shape._selected_key_name=='Recorded Form Pass')
 final_points=evaluated_points();check('two-object transitions preserve first mesh base and detail',tuple(surface().data.shape_keys.key_blocks['Recorded Form Pass'].data[0].co)==target and points_close(final_points,detail),point_difference(final_points,detail))
 with bpy.context.temp_override(**view()):
  second.select_set(True)
  bpy.ops.landfall.smooth_preview(mode='CAGE')
  check('mixed selection preview 1 uses Multires base and ordinary cage',ops.multires().levels==0 and not any(m.show_viewport for m in second.modifiers if m.type=='SUBSURF'))
  bpy.ops.landfall.smooth_preview(mode='BOTH')
  check('mixed selection preview 2 shares native subdivision owners',ops.multires().levels==ops.multires().total_levels and bpy.context.scene.landfall_cage_show and any(m.show_viewport for m in second.modifiers if m.type=='SUBSURF'))
  bpy.ops.landfall.smooth_preview(mode='SMOOTH')
 check('mixed selection preview 3 preserves high-resolution detail',points_close(evaluated_points(),detail) and len([m for m in surface().modifiers if m.show_viewport and m.type in ('SUBSURF','MULTIRES')])==1)
 # Removing the Multires owner is a deliberate modifier edit. Its native Undo
 # must recover the real grids; ordinary preview can then use SUBSURF again.
 desktop.cycle_right_dock('MODIFIER_STACK');yield .25
 stack=desktop._right_dock._ensure_host_container().ms_panel
 from landfall_studio.ui import modifier_stack
 modifier_stack.set_active_modifier(ops.multires().name,surface());yield .1
 with bpy.context.temp_override(**view()):bpy.ops.ed.undo_push(message='Multires removal fixture')
 focus(stack.action_buttons['delete']);yield .15;T.QTest.mouseClick(stack.action_buttons['delete'],C.Qt.LeftButton);yield .2
 check('modifier Delete removes selected Multires owner',ops.multires() is None)
 key('Z');yield .3
 check('one Undo restores deleted Multires grids and detail',ops.multires() is not None and points_close(evaluated_points(),detail))
 check('workflow leaves no stale inspector callbacks',not scene_edits._pending and not scene_edits._gestures)
 result['ok']=not result['failed'];save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
 try:return next(steps)
 except StopIteration:return None
 except Exception:
  result['failed'].append({'exception':traceback.format_exc()});save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
