"""Blender-only numerical control using the continuous session's saved baseline.

Does not import or register Studio. Native viewport paint and stock Ctrl+Z are
used. This diagnostic measures preservation error; it does not certify parity.
"""
import bpy
import json
import hashlib
import math
from mathutils import Vector
from bpy_extras import view3d_utils
from pathlib import Path
import sys
import struct
import shutil
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/native_multires_undo_precision.json'
result = {'ok': False, 'boundary': __doc__}


def save():
    OUT.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')


def view():
    w = bpy.context.window_manager.windows[0]
    a = next(a for a in w.screen.areas if a.type == 'VIEW_3D')
    return dict(window=w, area=a,
                region=next(r for r in a.regions if r.type == 'WINDOW'))


def surface():
    return bpy.data.objects['Artist Session Form']


def evaluated():
    c = view()
    with bpy.context.temp_override(**c):
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.update()
        obj = surface().evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = obj.to_mesh()
        try:
            points = [tuple(v.co) for v in mesh.vertices]
        finally:
            obj.to_mesh_clear()
        bpy.ops.object.mode_set(mode='SCULPT')
    return points


def delta(a, b):
    distances = [sum((x-y)**2 for x, y in zip(p, q))**.5 for p, q in zip(a, b)]
    worst = max(range(len(distances)), key=distances.__getitem__)
    def ordered(value):
        bits = struct.unpack('>I', struct.pack('>f', value))[0]
        return ~bits & 0xffffffff if bits & 0x80000000 else bits | 0x80000000
    return dict(max_delta=distances[worst], changed=sum(d != 0 for d in distances),
                rms_delta=math.sqrt(sum(d*d for d in distances)/len(distances)),
                vertices=len(a), expected=b[worst], actual=a[worst], worst_index=worst,
                worst_signed_components=[x-y for x,y in zip(a[worst],b[worst])],
                worst_component_ulps=[abs(ordered(x)-ordered(y)) for x,y in zip(a[worst],b[worst])])


def suite():
    source = ROOT.parent/'.test_env/continuous_artist_pre_detail.blend'
    baseline = ROOT.parent/'.test_env/native_multires_precision_baseline.blend'
    shutil.copyfile(source, baseline)
    result['baseline'] = str(baseline)
    result['baseline_sha256'] = hashlib.sha256(baseline.read_bytes()).hexdigest()
    result['probe_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(baseline))
    yield .7
    result['studio_imported'] = any(n == 'landfall_studio' or n.startswith('landfall_studio.') for n in sys.modules)
    if result['studio_imported']:
        raise RuntimeError('Native control must not load Studio')
    c = view()
    r = c['region']
    rv = c['area'].spaces.active.region_3d
    if surface().mode != 'SCULPT':
        with bpy.context.temp_override(**c):
            bpy.ops.object.mode_set(mode='SCULPT')
    center = view3d_utils.location_3d_to_region_2d(r, rv, surface().matrix_world.translation)
    corners = [view3d_utils.location_3d_to_region_2d(r, rv, surface().matrix_world@Vector(p)) for p in surface().bound_box]
    radius = (max(p.x for p in corners)-min(p.x for p in corners))/2
    x, y = int(r.x+center.x-radius*.16), int(r.y+center.y)
    result['brush'] = bpy.context.tool_settings.sculpt.brush.name
    result['native_tool'] = c['window'].workspace.tools.from_space_view3d_mode('SCULPT', create=False).idname
    key_baseline = {k.name:[tuple(v.co) for v in k.data]
                    for k in surface().data.shape_keys.key_blocks}
    before = evaluated()
    result['no_stroke_rebuilds'] = []
    for repeat in range(4):
        again = evaluated()
        result['no_stroke_rebuilds'].append(delta(again, before))
        before = again

    def event(kind, value='PRESS', dx=0, **mods):
        c['window'].event_simulate(type=kind, value=value, x=x+dx, y=y, **mods)

    event('MOUSEMOVE', 'NOTHING')
    event('LEFTMOUSE')
    yield .12
    result['press_modals'] = [o.bl_idname for o in c['window'].modal_operators]
    if 'SCULPT_OT_brush_stroke' not in result['press_modals']:
        raise RuntimeError('Native control did not start paint')
    for dx in (7, 14, 21, 28, 35):
        event('MOUSEMOVE', 'NOTHING', dx)
        yield .07
    event('LEFTMOUSE', 'RELEASE', 35)
    yield .3
    painted = evaluated()
    result['paint'] = delta(painted, before)
    if result['paint']['max_delta'] <= 1e-4:
        raise RuntimeError('Native control stroke must change the actual surface')
    event('Z', ctrl=True)
    event('Z', 'RELEASE', ctrl=True)
    yield .3
    undone = evaluated()
    result['undo'] = delta(undone, before)
    event('Z', ctrl=True, shift=True)
    event('Z', 'RELEASE', ctrl=True, shift=True)
    yield .3
    result['redo'] = delta(evaluated(), painted)
    result['repeat_history_cycles'] = []
    for repeat in range(9):
        event('Z', ctrl=True)
        event('Z', 'RELEASE', ctrl=True)
        yield .15
        undo = delta(evaluated(), before)
        event('Z', ctrl=True, shift=True)
        event('Z', 'RELEASE', ctrl=True, shift=True)
        yield .15
        redo = delta(evaluated(), painted)
        result['repeat_history_cycles'].append(dict(cycle=repeat+2, undo=undo, redo=redo))
    result['shape_buffers_exact'] = all(
        [tuple(v.co) for v in k.data] == key_baseline[k.name]
        for k in surface().data.shape_keys.key_blocks)
    result['ok'] = True
    save()
    bpy.ops.wm.quit_blender()


steps = suite()


def tick():
    try:
        return next(steps)
    except StopIteration:
        return None
    except Exception:
        result['error'] = traceback.format_exc()
        save()
        traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=.5, persistent=True)
