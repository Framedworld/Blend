"""Native Blender duplication remains native, with independent Studio helpers.

Factory assets only. event_simulate exercises actual viewport/search input;
direct operator/data probes are separately identified. No physical input claim.
"""
import ctypes
import json
import os
from pathlib import Path
import statistics
import sys
import threading
import time
import traceback
from types import SimpleNamespace

import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_INSTANCE_TAG','')
OUT=ROOT/('output/native_duplicate_gui'+TAG+'.json')
report={'ok':False,'passed':[],'failed':[],'routes':[],
        'boundary':'Factory scene; actual Blender simulated keys/search; direct operator, transform and guard diagnostics labeled separately. No physical pen claim.'}

def save():OUT.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
def check(label,value,detail=None):
    report['passed' if value else 'failed'].append(label if value else {'test':label,'detail':detail});save()
def view():
    w=bpy.context.window_manager.windows[0]
    a=max((a for a in w.screen.areas if a.type=='VIEW_3D'),key=lambda a:a.width*a.height)
    return dict(window=w,screen=w.screen,area=a,region=next(r for r in a.regions if r.type=='WINDOW'))
def surface(o):
    bpy.context.view_layer.update();o=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=o.to_mesh()
    try:return [v.co.copy() for v in m.vertices]
    finally:o.to_mesh_clear()
def same(a,b):return len(a)==len(b) and max(((x-y).length for x,y in zip(a,b)),default=0)<2e-5
def helper_names():return {o.name for o in bpy.data.objects if o.get('_lf_instance_helper')}
def authored(o):
    return {'vertices':[tuple(v.co) for v in o.data.vertices],
            'uv':[tuple(v.uv) for v in o.data.uv_layers.active.data],
            'keys':[(k.name,[tuple(v.co) for v in k.data]) for k in o.data.shape_keys.key_blocks],
            'weight':o.vertex_groups['Skin preservation'].weight(0)}

def suite():
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile()
    import landfall_studio
    landfall_studio.register()
    from landfall_studio import ui
    from landfall_studio.sculpt import extended,instances
    ui.restore_workspace_desktop(restore_script_output=False)
    from PySide6 import QtWidgets as W
    from blendertk.ui_utils.blender_window import BlenderWindow
    app=W.QApplication.instance();yield .8
    report['dpr']=app.primaryScreen().devicePixelRatio()
    ctypes.windll.user32.ShowWindow(BlenderWindow.window_hwnd(view()['window']),3);yield .2
    def focus():
        if app.focusWidget():app.focusWidget().clearFocus()
        app.setActiveWindow(None)
        BlenderWindow.set_keyboard_focus(BlenderWindow.window_hwnd(view()['window']))
        c=view();r=c['region']
        c['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',x=r.x+r.width//2,y=r.y+r.height//2)
    def key(key,unicode='',**mods):
        c=view();r=c['region'];kw=dict(x=r.x+r.width//2,y=r.y+r.height//2)
        c['window'].event_simulate(type=key,value='PRESS',unicode=unicode,**kw,**mods)
        c['window'].event_simulate(type=key,value='RELEASE',**kw,**mods)
    def text(value):
        for character in value:key('SPACE' if character==' ' else character.upper(),unicode=character)
    def select(names):
        with bpy.context.temp_override(**view()):
            bpy.ops.object.select_all(action='DESELECT')
            for name in names:bpy.data.objects[name].select_set(True)
            bpy.context.view_layer.objects.active=bpy.data.objects[names[0]]
    originals={};baselines={};buffers={}
    for section in ('ArrayMesh','NanoMesh'):
        with bpy.context.temp_override(**view()):
            bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_cube_add();o=bpy.context.object
            o.name='Native '+section
            o.shape_key_add(name='Basis');o.shape_key_add(name='Authored Form').data[0].co.z+=.15
            o.vertex_groups.new(name='Skin preservation').add([0],.7,'REPLACE')
            if section=='NanoMesh':
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.4);source=bpy.context.object
                source.select_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o
                extended.option(section,'source',source.name)
            extended.option(section,'enabled',True)
            originals[section]=o.name;baselines[section]=surface(o);buffers[section]=authored(o)
            bpy.ops.ed.undo_push(message=section+' native duplicate fixture')
        for route,linked,cancel in (('Direct native operator',False,False),('Direct linked operator',True,False),
                                    ('Shift+D numeric move',False,False),('Shift+D cancel move',False,True),
                                    ('Alt+D numeric move',True,False),('F3 Duplicate Objects',False,False),
                                    ('F3 Duplicate Linked',True,False)):
            name=originals[section];label=section+' '+route;select([name]);focus();yield .1
            before_objects=set(bpy.data.objects.keys());before_helpers=helper_names()
            if route.startswith('Direct'):
                with bpy.context.temp_override(**view()):bpy.ops.object.duplicate('EXEC_DEFAULT',True,linked=linked)
            elif route.startswith('F3'):
                key('F3');yield .2
                text('Duplicate Linked' if linked else 'Duplicate Objects');yield .2
                key('RET');yield .2
            else:key('D',alt=linked,shift=not linked);yield .2
            if not route.startswith('Direct'):
                if cancel:key('ESC')
                else:
                    key('X');key('FOUR',unicode='4');key('RET')
            yield .25
            cp=bpy.context.object;cp_name=cp.name;current=surface(cp)
            owned=[h.name for h in instances.instance_helpers(cp)]
            native_id=bpy.context.window_manager.operators[-1].bl_idname if bpy.context.window_manager.operators else None
            report['routes'].append({'label':label,'operator':native_id,'original':name,'copy':cp_name,'helpers':owned,'location':tuple(cp.location)})
            check(label+' creates exactly one selected copy',set(bpy.data.objects.keys())-before_objects=={cp_name,*owned} and cp_name!=name and [o.name for o in bpy.context.selected_objects]==[cp_name])
            check(label+' preserves expected native mesh sharing',(cp.data==bpy.data.objects[name].data)==linked)
            check(label+' owns independent placement IDs',bool(owned) and all(h.parent==cp for h in instances.instance_helpers(cp)))
            check(label+' preserves source UV shape keys and skin',authored(cp)==buffers[section] and authored(bpy.data.objects[name])==buffers[section])
            check(label+' keeps local generated surface',same(baselines[section],current) and same(baselines[section],surface(bpy.data.objects[name])))
            if route.startswith('F3'):
                check(label+' executes native Blender macro',native_id in ('OBJECT_OT_duplicate_move','OBJECT_OT_duplicate_move_linked'),native_id)
            if not route.startswith('Direct'):
                check(label+' retains native move or cancel',abs(cp.location.x-(0 if cancel else 4))<1e-5 and abs(cp.location.y)<1e-5 and abs(cp.location.z)<1e-5,tuple(cp.location))
            # A direct transform is a data diagnostic, not a second input claim.
            cp.location=(5,-3,2);cp.rotation_euler=(.2,.3,.5);cp.scale=(1.2,.8,1.4)
            check(label+' transforms independently',same(baselines[section],surface(cp)) and same(baselines[section],surface(bpy.data.objects[name])))
            for cycle in range(3):
                focus();key('Z');yield .2
                check(label+' Undo '+str(cycle+1)+' removes copy and only its helpers',set(bpy.data.objects.keys())==before_objects and helper_names()==before_helpers)
                key('Z',shift=True);yield .2
                cp=bpy.data.objects.get(cp_name);current=surface(cp) if cp else []
                check(label+' Redo '+str(cycle+1)+' restores independent copy',cp is not None and same(baselines[section],current) and all(h.parent==cp for h in instances.instance_helpers(cp)) and len(helper_names()-before_helpers)==len(owned))
    # Native multi-selection with transformed parent relationships.
    with bpy.context.temp_override(**view()):
        group=bpy.data.objects.new('Artist Parent',None);bpy.context.collection.objects.link(group)
        group.location=(-2,3,4);group.rotation_euler=(.2,.4,-.3);group.scale=(1.2,.9,1.1)
        for name in originals.values():bpy.data.objects[name].parent=group
        bpy.ops.ed.undo_push(message='Native multi-object fixture')
    select(list(originals.values()));before=set(bpy.data.objects.keys());focus();key('D',shift=True);yield .2
    key('Y');key('THREE',unicode='3');key('RET');yield .25
    copies=list(bpy.context.selected_objects);copy_names=[o.name for o in copies]
    check('Multi-object Shift+D duplicates both selected assets',len(copies)==2 and all(o.name not in originals.values() for o in copies))
    for o in copies:
        section='NanoMesh' if '_lf_nano_inventory' in o else 'ArrayMesh'
        check(section+' multi-object copy retains artist parent and local geometry',o.parent and o.parent.name=='Artist Parent' and same(baselines[section],surface(o)) and all(h.parent==o for h in instances.instance_helpers(o)))
    focus();key('Z');yield .2
    check('Multi-object duplicate has one native Undo',set(bpy.data.objects.keys())==before)
    key('Z',shift=True);yield .2
    check('Multi-object Redo restores both isolated assets',all(bpy.data.objects.get(n) and all(h.parent==bpy.data.objects[n] for h in instances.instance_helpers(bpy.data.objects[n])) for n in copy_names))
    # Unflagged artist-owned offset references must remain deliberately shared.
    with bpy.context.temp_override(**view()):
        bpy.ops.mesh.primitive_cube_add();artist=bpy.context.object;artist.name='Artist Shared Offset'
        offset=bpy.data.objects.new('Artist Offset',None);bpy.context.collection.objects.link(offset)
        artist.modifiers.new('Artist Array','ARRAY').offset_object=offset
        bpy.ops.object.duplicate('EXEC_DEFAULT',True);cp=bpy.context.object;surface(cp)
        check('Native duplication preserves ordinary artist offset reference',cp.modifiers['Artist Array'].offset_object==offset)
    instances.register_handlers();instances.register_handlers()
    check('Native ownership repair has exactly one registered owner',bpy.app.handlers.depsgraph_update_pre.count(instances.sync_native_owners)==1)
    # Guard probes return before reading any bpy data on workers or render graphs.
    errors=[]
    def worker():
        try:instances.sync_native_owners(None)
        except Exception as exc:errors.append(str(exc))
    thread=threading.Thread(target=worker);thread.start();thread.join()
    try:instances.sync_native_owners(None,SimpleNamespace(mode='RENDER'))
    except Exception as exc:errors.append(str(exc))
    check('Worker and render guard diagnostics do not access scene data',not errors,errors)
    # Measure idle scan cost against a realistic large object list, without
    # allocating geometry per object or counting native graph evaluation time.
    mesh=bpy.data.meshes.new('Idle object fixture')
    for i in range(2000):bpy.context.scene.collection.objects.link(bpy.data.objects.new('Idle '+str(i),mesh))
    surface(bpy.data.objects[originals['ArrayMesh']]);before_ids=set(bpy.data.objects.keys());before_groups=set(bpy.data.node_groups.keys())
    durations=[]
    for _ in range(30):
        started=time.perf_counter();instances.sync_native_owners(bpy.context.scene);durations.append((time.perf_counter()-started)*1000)
    report['idle_scan_ms']={'objects':len(bpy.context.scene.objects),'median':statistics.median(durations),'p95':sorted(durations)[28],'max':max(durations)}
    check('Repeated evaluation creates no additional helper or node IDs',set(bpy.data.objects.keys())==before_ids and set(bpy.data.node_groups.keys())==before_groups)
    check('Idle ownership scan stays below 4ms median for 2000 objects',statistics.median(durations)<4,report['idle_scan_ms'])
    for o in list(bpy.data.objects):
        if o.data==mesh:bpy.data.objects.remove(o,do_unlink=True)
    path=Path(os.environ['BLENDER_USER_RESOURCES']).parent/'native_duplicate_roundtrip.blend'
    bpy.context.preferences.filepaths.file_preview_type='NONE'
    with bpy.context.temp_override(**view()):bpy.ops.wm.save_as_mainfile(filepath=str(path))
    yield .2
    bpy.ops.wm.open_mainfile(filepath=str(path));yield .5
    check('Save reopen retains native ownership handler once',bpy.app.handlers.depsgraph_update_pre.count(instances.sync_native_owners)==1)
    check('Save reopen retains every generated placement owner',all(all(h.parent==o for h in instances.instance_helpers(o)) for o in bpy.context.scene.objects if o.type=='MESH' and ('_lf_array_stages' in o or '_lf_nano_inventory' in o)))
    select([originals['ArrayMesh']]);focus();key('D',shift=True);yield .2
    key('ESC');yield .2
    cp=bpy.context.object;surface(cp)
    check('Native duplication still isolates placements after reopen',cp.name!=originals['ArrayMesh'] and all(h.parent==cp for h in instances.instance_helpers(cp)))
    report['ok']=not report['failed'];save()
    landfall_studio.unregister()
    check('Unregister removes native ownership handler',instances.sync_native_owners not in bpy.app.handlers.depsgraph_update_pre)
    report['ok']=not report['failed'];save();bpy.ops.wm.quit_blender()

steps=suite()
def tick():
    try:return next(steps)
    except StopIteration:return None
    except Exception:
        report['failed'].append({'exception':traceback.format_exc()});save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
