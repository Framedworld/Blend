"""Native viewport MMB history with the Studio Channel Box adapter installed."""
import bpy,json,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/native_channel_scrub_extended_gui.json'
result={'ok':False,'passed':[],'failed':[],
 'boundary':'Disposable factory scene; native simulated viewport MMB and Z/Shift-Z, real Qt typed transform'}
def save():OUT.write_text(json.dumps(result,indent=2),encoding='utf-8')
def check(name,yes,detail=None):
 result['passed' if yes else 'failed'].append(name if yes else {'test':name,'detail':detail});save()
def obj():return bpy.data.objects['Cube']
def view():
 w=bpy.context.window_manager.windows[0];a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
 return dict(window=w,screen=w.screen,area=a,region=next(r for r in a.regions if r.type=='WINDOW'))
def event(kind,value='PRESS',dx=0,**mods):
 c=view();r=c['region']
 c['window'].event_simulate(type=kind,value=value,x=r.x+int(r.width*.7)+dx,y=r.y+int(r.height*.4),**mods)
def key(kind,**mods):
 from PySide6 import QtWidgets as W
 from blendertk.ui_utils.blender_window import BlenderWindow
 app=W.QApplication.instance()
 if app.focusWidget():app.focusWidget().clearFocus()
 app.setActiveWindow(None);BlenderWindow.set_keyboard_focus(BlenderWindow.window_hwnd(view()['window']))
 event('MOUSEMOVE','NOTHING');event(kind,**mods);event(kind,'RELEASE',**mods)
def drag(cancel=False,read=None):
 read=read or (lambda:obj().location.y)
 before=read()
 event('MOUSEMOVE','NOTHING');yield .1;event('MIDDLEMOUSE');yield .1
 for dx in (10,25,50):event('MOUSEMOVE','NOTHING',dx);yield .06
 if cancel:
  check('native viewport channel preview changes before '+str(cancel),abs(read()-before)>.01,[before,read()])
  cancel_key=cancel if isinstance(cancel,str) else 'ESC'
  event(cancel_key,dx=50);event(cancel_key,'RELEASE',50)
  event('MIDDLEMOUSE','RELEASE',50)
 else:event('MIDDLEMOUSE','RELEASE',50)
 yield .2
def suite():
 bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
 import landfall_studio
 from landfall_studio import ui
 from landfall_studio.ui import desktop,channel_box_ext,channel_history,attribute_editor
 from landfall_studio.commands import scene_edits
 landfall_studio.register();ui.restore_workspace_desktop(restore_script_output=False);yield .8
 desktop.cycle_right_dock('CHANNEL_BOX');yield .2
 obj().location=(2,.5,0)
 with bpy.context.temp_override(**view()):
  bpy.ops.ed.undo_push(message='Native scrub fixture');bpy.ops.transform.translate('EXEC_DEFAULT',True,value=(.25,0,0))
 desktop.sync_channels_now();channel_box_ext.select_channels_in_ui(['location_y']);yield .2
 check('live Studio channel history adapter is installed',len(channel_history._adapters)==1)
 key('W');yield .15
 before=obj().location.y;yield from drag();end=obj().location.y
 check('viewport MMB scrubs highlighted Channel Box channel',end>before+.1 and abs(obj().location.x-2.25)<1e-5,[before,end])
 key('Z');yield .25
 check('one native Undo restores complete viewport channel drag',abs(obj().location.y-before)<1e-5,obj().location.y)
 key('Z');yield .25
 check('viewport channel drag leaves preceding native history intact',abs(obj().location.x-2)<1e-5,obj().location.x)
 key('Z',shift=True);yield .2;key('Z',shift=True);yield .25
 check('native Redo restores viewport drag in one step',abs(obj().location.y-end)<1e-5,obj().location.y)
 desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
 from PySide6 import QtCore as C,QtWidgets as W,QtTest as T
 app=W.QApplication.instance();field=attribute_editor.ensure_attribute_editor_widget().spn_ty
 app.setActiveWindow(field.window());field.setFocus();field.lineEdit().selectAll()
 T.QTest.keyClicks(field.lineEdit(),'3.125');T.QTest.keyClick(field.lineEdit(),C.Qt.Key_Return);field.clearFocus();yield .2
 check('Qt inspector works after native viewport scrub',abs(obj().location.y-3.125)<1e-5)
 key('Z');yield .25
 check('Undo after Qt edit returns to native scrub end value',abs(obj().location.y-end)<1e-5,obj().location.y)
 key('Z');yield .25
 check('next Undo returns to native scrub start value',abs(obj().location.y-before)<1e-5,obj().location.y)
 key('Z',shift=True);yield .2
 start=obj().location.y;yield from drag(cancel=True)
 check('Escape cancels viewport transform-channel scrub',abs(obj().location.y-start)<1e-5,obj().location.y)
 check('viewport previews create no pending Qt callbacks or gestures',not scene_edits._pending and not scene_edits._gestures)
 # Actual custom and INPUTS targets use different write paths. Cancellation must
 # restore their exact native values, not only the object's transforms.
 desktop.cycle_right_dock('CHANNEL_BOX');yield .2
 def custom_fixture():obj()['UXCustom']=.371234;obj().id_properties_ui('UXCustom').update(default=.371234,min=-10,max=10)
 scene_edits.commit('Custom scrub fixture',custom_fixture);desktop.sync_channels_now();yield .2
 selected=channel_box_ext.select_channels_in_ui(['UXCustom']);check('custom channel can be highlighted',selected==['UXCustom'],selected)
 for cancel_key in ('ESC','RIGHTMOUSE'):
  start=obj()['UXCustom'];key('W');yield .1
  yield from drag(cancel=cancel_key,read=lambda:obj()['UXCustom'])
  check(cancel_key+' restores exact custom property',obj()['UXCustom']==start,[start,obj()['UXCustom']])
  # Do not let a known failed cancellation contaminate the next independent case.
  obj()['UXCustom']=start
 channels,_=desktop.get_panel_widget_and_slots('channels')
 extra=channel_box_ext.ensure_channel_box_extensions(channels);tree=extra.tree_inputs
 def select_input(node_name,attr):
  desktop.sync_channels_now();channel_box_ext.refresh_channel_box_extensions();yield .1
  node=next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if tree.topLevelItem(i).text(0)==node_name)
  node.setExpanded(True)
  child=next(node.child(i) for i in range(node.childCount()) if node.child(i).data(0,C.Qt.UserRole)[1]==attr)
  tree.scrollToItem(child);app.setActiveWindow(tree.window());tree.setFocus();yield .1
  pos=C.QPoint(min(tree.columnWidth(0)-5,75),tree.visualItemRect(child).center().y())
  T.QTest.mouseClick(tree.viewport(),C.Qt.LeftButton,pos=pos);yield .15
  check('real INPUTS click selects '+node_name+'.'+attr,channel_box_ext._selected_input_target==(node_name,attr),channel_box_ext._selected_input_target)
 def bevel_fixture():obj().modifiers.new('UXBevel','BEVEL').width=.231234
 scene_edits.commit('Modifier scrub fixture',bevel_fixture);yield .2
 yield from select_input('UXBevel','width')
 for cancel_key in ('ESC','RIGHTMOUSE'):
  start=obj().modifiers['UXBevel'].width
  yield from drag(cancel=cancel_key,read=lambda:obj().modifiers['UXBevel'].width)
  check(cancel_key+' restores exact modifier input',obj().modifiers['UXBevel'].width==start,[start,obj().modifiers['UXBevel'].width])
  obj().modifiers['UXBevel'].width=start
 scene_edits.commit('GN scrub fixture',lambda:channel_box_ext.ensure_procedural_geonodes_modifier(obj()));yield .2
 mod=obj().modifiers['geoNodes_Procedural1']
 socket=next(s for s in mod.node_group.interface.items_tree if s.name=='Surface Offset')
 ident=socket.identifier;channel_box_ext._set_gn_socket_value(mod,ident,.1234567)
 yield from select_input(mod.name,ident)
 start=channel_box_ext._get_gn_socket_value(mod,ident,0)
 yield from drag(cancel='ESC',read=lambda:channel_box_ext._get_gn_socket_value(obj().modifiers['geoNodes_Procedural1'],ident,0))
 check('Escape restores exact GN input',channel_box_ext._get_gn_socket_value(mod,ident,0)==start,[start,channel_box_ext._get_gn_socket_value(mod,ident,0)])
 channel_box_ext._set_gn_socket_value(mod,ident,start)
 # Integer deltas accumulate from the gesture origin instead of rounding every
 # mouse event to zero. A cancelled gesture must not consume a history step.
 def integer_fixture():
  obj()['UXInteger']=3;obj().id_properties_ui('UXInteger').update(default=3,min=0,max=100)
 scene_edits.commit('Integer scrub fixture',integer_fixture);desktop.sync_channels_now();yield .15
 channel_box_ext.select_channels_in_ui(['UXInteger']);yield .1
 event('MOUSEMOVE','NOTHING');event('MIDDLEMOUSE');yield .1
 for dx in range(5,81,5):event('MOUSEMOVE','NOTHING',dx);yield .02
 event('MIDDLEMOUSE','RELEASE',80);yield .2
 check('integer channel accumulates small native motion',obj()['UXInteger']==4,obj()['UXInteger'])
 key('Z');yield .2
 check('one Undo restores complete integer drag',obj()['UXInteger']==3,obj()['UXInteger'])
 key('Z',shift=True);yield .2
 check('one Redo restores complete integer drag',obj()['UXInteger']==4,obj()['UXInteger'])
 # Real custom-property history and a preceding native transform coexist.
 channel_box_ext.select_channels_in_ui(['UXCustom']);yield .1
 with bpy.context.temp_override(**view()):bpy.ops.transform.translate('EXEC_DEFAULT',True,value=(.125,0,0))
 prior_x=obj().location.x;start=obj()['UXCustom']
 yield from drag(cancel='ESC',read=lambda:obj()['UXCustom'])
 check('cancelled custom drag restores its baseline before Undo',obj()['UXCustom']==start)
 key('Z');yield .2
 check('cancelled custom drag leaves preceding native Undo intact',abs(obj().location.x-(prior_x-.125))<1e-5,obj().location.x)
 key('Z',shift=True);yield .2
 # Socket types that need native typed editors stay visible and read-only;
 # they must never be coerced into a numeric MMB operation.
 def typed_fixture():
  mod=obj().modifiers['geoNodes_Procedural1'];ng=mod.node_group
  values=(('Text','NodeSocketString','Artist label'),('Object','NodeSocketObject',bpy.data.objects['Camera']),
          ('Collection','NodeSocketCollection',bpy.data.collections.new('UXSocketCollection')),
          ('Material','NodeSocketMaterial',bpy.data.materials.new('UXSocketMaterial')),
          ('Vector','NodeSocketVector',(1,2,3)))
  for name,kind,value in values:
   socket=ng.interface.new_socket(name=name,in_out='INPUT',socket_type=kind)
   socket.default_value=value
  obj()['UXToggle']=True;obj().update_tag();bpy.context.view_layer.update()
 scene_edits.commit('Typed socket fixture',typed_fixture);desktop.sync_channels_now();yield .2
 mod=obj().modifiers['geoNodes_Procedural1']
 from landfall_studio.ui import modifier_stack
 desktop.cycle_right_dock('MODIFIER_STACK');yield .15
 mod.show_expanded=True;obj().modifiers.active=mod
 stack=desktop._right_dock._ensure_host_container().ms_panel;stack.refresh();yield .1
 group=modifier_stack.create_group_inputs_widget();desktop._parent_floating_to_blender(group.root);group.root.show();yield .15
 for label in ('Text','Object','Collection','Material','Vector'):
  for owner,root in (('Modifier Stack',stack.root),('Group Inputs',group.root)):
   caption=next(l for l in root.findChildren(W.QLabel) if l.text()==label)
   editor=caption.parentWidget().findChild(W.QLineEdit)
   check(owner+' shows '+label+' as a native-editor field',editor.isReadOnly() and 'native Geometry Nodes' in editor.toolTip())
 group.root.close();desktop.cycle_right_dock('CHANNEL_BOX');yield .2
 for label in ('Text','Object','Collection','Material','Vector'):
  socket=next(s for s in mod.node_group.interface.items_tree if s.name==label);socket_id=socket.identifier
  attr=next(a for n in channel_box_ext.get_object_inputs(obj()) if n['node_name']==mod.name for a in n['attributes'] if a['name']==socket_id)
  check('native '+label+' socket is shown read-only',attr['type']=='text' and not attr['editable'],attr)
  yield from select_input(mod.name,socket_id)
  def raw():
   val=channel_box_ext._get_gn_socket_value(obj().modifiers['geoNodes_Procedural1'],socket_id,socket.default_value)
   return tuple(val) if hasattr(val,'__len__') and not isinstance(val,str) else val
  start=raw();transforms=(tuple(obj().location),tuple(obj().rotation_euler),tuple(obj().scale))
  yield from drag()
  check('MMB leaves '+label+' socket and transforms unchanged',raw()==start and transforms==(tuple(obj().location),tuple(obj().rotation_euler),tuple(obj().scale)))
  rejected=channel_box_ext.set_object_input_attribute(obj(),mod.name,socket_id,99)
  check('numeric edit rejects '+label+' socket without mutation',not rejected['ok'] and raw()==start,rejected)
 for value in ('nan','inf','oops'):
  start=channel_box_ext._get_gn_socket_value(mod,ident,0)
  rejected=channel_box_ext.set_object_input_attribute(obj(),mod.name,ident,value)
  check('GN input rejects '+value+' without mutation',not rejected['ok'] and channel_box_ext._get_gn_socket_value(mod,ident,0)==start,rejected)
 channel_box_ext.select_channels_in_ui(['UXToggle']);yield .1
 transforms=(tuple(obj().location),tuple(obj().rotation_euler),tuple(obj().scale));yield from drag()
 check('boolean custom channel keeps its actual toggle during MMB',obj()['UXToggle'] is True)
 check('boolean custom channel cannot fall through to transforming object',transforms==(tuple(obj().location),tuple(obj().rotation_euler),tuple(obj().scale)))
 # A parametric primitive must restore its geometry and its metadata together.
 def primitive_fixture():
  obj().name='PreviousScrubFixture';channel_box_ext.create_maya_primitive('CUBE',name='Cube')
 scene_edits.commit('Primitive scrub fixture',primitive_fixture)
 yield .2;node_name=json.loads(obj()[channel_box_ext._INPUT_META_KEY])['node_name']
 yield from select_input(node_name,'width')
 metadata=obj()[channel_box_ext._INPUT_META_KEY];coords=tuple(tuple(v.co) for v in obj().data.vertices)
 start=json.loads(metadata)['params']['width']
 yield from drag(cancel='ESC',read=lambda:json.loads(obj()[channel_box_ext._INPUT_META_KEY])['params']['width'])
 check('Escape restores exact primitive metadata',obj()[channel_box_ext._INPUT_META_KEY]==metadata)
 check('Escape restores exact primitive geometry',tuple(tuple(v.co) for v in obj().data.vertices)==coords)
 result['ok']=not result['failed'];save();landfall_studio.unregister();bpy.ops.wm.quit_blender()
steps=suite()
def tick():
 try:return next(steps)
 except StopIteration:return None
 except Exception:
  result['failed'].append({'exception':traceback.format_exc()});save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
