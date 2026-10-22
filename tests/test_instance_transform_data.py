"""Generated sculpt geometry must travel with its asset; factory fixtures only."""
import json
import os
from pathlib import Path
import sys
import traceback

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TAG = os.environ.get('LANDFALL_INSTANCE_TAG', '')
OUT = ROOT / ('output/instance_transform_data' + TAG + '.json')
report = {'ok': False, 'passed': [], 'failed': [], 'observations': {}}


def save():
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')


def require(value, message):
    if not value:
        raise AssertionError(message)


def check(name, fn):
    try:
        fn()
        report['passed'].append(name)
    except Exception:
        report['failed'].append({'test': name, 'error': traceback.format_exc()})
    save()


def fresh():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = 'Placement Asset'
    return obj


def surface(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return [vertex.co.copy() for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def same_surface(before, after, label):
    require(len(before) == len(after), label + ': generated vertex count changed')
    delta = max(((a - b).length for a, b in zip(before, after)), default=0)
    report['observations'][label] = {'vertices': len(after), 'max_local_delta': delta}
    require(delta < 2e-5, label + ': generated geometry drifted by ' + str(delta))


import landfall_studio
landfall_studio.register()
from landfall_studio.sculpt import extended as ext, instances, ops


def setup(section):
    obj = fresh()
    if section == 'NanoMesh':
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=.4)
        source = bpy.context.object
        source.name = 'Instance Source'
        bpy.context.view_layer.objects.active = obj
        source.select_set(False)
        obj.select_set(True)
        ext.option(section, 'source', source.name)
    ext.option(section, 'enabled', True)
    return obj


def travel(section, transform):
    obj = setup(section)
    base = [v.co.copy() for v in obj.data.vertices]
    before = surface(obj)
    if transform == 'translate':
        obj.location = (4, -3, 2)
    elif transform == 'rotate_scale':
        obj.rotation_euler = (.3, -.2, .7)
        obj.scale = (1.5, .8, 2)
    elif transform == 'parent':
        parent = bpy.data.objects.new('Artist Group', None)
        bpy.context.collection.objects.link(parent)
        obj.parent = parent
        parent.location = (-2, 3, 5)
        parent.rotation_euler = (.2, .4, -.3)
        parent.scale = (1.2, .9, 1.1)
    elif transform == 'frozen':
        ext.option(section, 'freeze', True)
        before = surface(obj)
        obj.location = (3, 2, -4)
    same_surface(before, surface(obj), section + ' ' + transform)
    require(all(a == b.co for a, b in zip(base, obj.data.vertices)), 'Source vertex coordinates changed')


def rename(section):
    obj = setup(section)
    helper = (obj.modifiers['Sculpt Array 1'].offset_object if section == 'ArrayMesh'
              else bpy.data.objects[obj['_lf_nano_points']])
    obj.name = 'Renamed Artist Asset'
    ext.option(section, 'count' if section == 'ArrayMesh' else 'size', 4 if section == 'ArrayMesh' else .25)
    current = (obj.modifiers['Sculpt Array 1'].offset_object if section == 'ArrayMesh'
               else bpy.data.objects[obj['_lf_nano_points']])
    require(current == helper, 'Renaming the artist asset replaced its placement owner')


def curve_retained():
    obj = setup('ArrayMesh')
    curve_data = bpy.data.curves.new('Artist Path', 'CURVE')
    curve_data.dimensions = '3D'
    spline = curve_data.splines.new('POLY')
    spline.points.add(2)
    for point, coordinate in zip(spline.points, ((0, 0, 0, 1), (4, 0, 0, 1), (8, 3, 0, 1))):
        point.co = coordinate
    curve = bpy.data.objects.new('Artist Path', curve_data)
    bpy.context.collection.objects.link(curve)
    instances.dispatch('ArrayMesh', 'ALIGN_PATH', target=curve.name)
    path = obj.modifiers.get('Sculpt Array Path')
    ext.option('ArrayMesh', 'count', 5)
    ext.option('ArrayMesh', 'rotate_z', 20)
    require(obj.modifiers.get('Sculpt Array Path') == path, 'Editing the array removed its assigned path')
    require(path.object == curve, 'Editing the array changed its path target')
    instances.dispatch('ArrayMesh', 'APPEND')
    require(all(obj.modifiers.find(m.name) < obj.modifiers.find(path.name)
                for m in obj.modifiers if m.type == 'ARRAY'), 'New array stage runs after the curve path')
    instances.dispatch('ArrayMesh', 'DELETE')
    require(obj.modifiers.get('Sculpt Array Path') == path, 'Deleting a stage removed the path')
    require(len([m for m in obj.modifiers if m.type == 'ARRAY']) == 1, 'Deleted stage survived')


def independent_copy(section, frozen=False):
    original = setup(section)
    if frozen:
        ext.option(section, 'freeze', True)
    before = surface(original)
    ops.dispatch('DUPLICATE')
    copy = ops.active()
    copy.location = (3, -4, 2)
    copy.rotation_euler = (.2, .4, .1)
    same_surface(before, surface(copy), section + ' duplicate' + (' frozen' if frozen else ''))
    ext.option(section, 'count' if section == 'ArrayMesh' else 'tile_h', 5)
    same_surface(before, surface(original), section + ' source after copy edit')
    if frozen:
        require(len(surface(copy)) == len(before), 'Copy lost frozen placement geometry')


def legacy(section):
    obj=setup(section)
    before=surface(obj)
    for helper in list(obj.children):
        if helper.get('_lf_instance_helper'):
            world=helper.matrix_world.copy();helper.parent=None;helper.matrix_world=world
    obj.location=(4,-2,3)
    # Ordinary artist entry must migrate a saved legacy helper as well as
    # newly generated objects, before the next object transform occurs.
    from landfall_studio import sculpt
    sculpt.enter()
    sculpt.return_to_maya()
    same_surface(before,surface(obj),section+' legacy adoption')


def snapshot(section,clipboard):
    original=setup(section);before=surface(original)
    if clipboard:
        ext.subtool('COPY')
    else:
        recovery=ops.recovery(original,'Instance snapshot');recovery_name=recovery.name
    ext.option(section,'rotate_z' if section=='ArrayMesh' else 'size',35 if section=='ArrayMesh' else .8)
    if clipboard:ext.subtool('PASTE')
    else:ops.dispatch('RESTORE',name=recovery_name)
    same_surface(before,surface(ops.active()),section+(' clipboard snapshot' if clipboard else ' recovery snapshot'))


def artist_stack():
    obj=setup('ArrayMesh');instances.dispatch('ArrayMesh','APPEND')
    bevel=obj.modifiers.new('Artist Interleaved Bevel','BEVEL');bevel.width=.1
    obj.modifiers.move(obj.modifiers.find(bevel.name),obj.modifiers.find('Sculpt Array 2'))
    before=[m.name for m in obj.modifiers]
    ext.option('ArrayMesh','count',4)
    require([m.name for m in obj.modifiers]==before,'Array setting moved an artist modifier across a stage')


with bpy.context.temp_override(**ops.view_context()):
    for section in ('ArrayMesh', 'NanoMesh'):
        for transform in ('translate', 'rotate_scale', 'parent'):
            check(section + ' follows asset ' + transform, lambda s=section, t=transform: travel(s, t))
        check(section + ' preserves owner through rename', lambda s=section: rename(s))
        check(section + ' duplicate moves and edits independently', lambda s=section: independent_copy(s))
        check(section+' adopts legacy world-space helpers',lambda s=section:legacy(s))
        check(section+' clipboard snapshots generated geometry',lambda s=section:snapshot(s,True))
        check(section+' recovery snapshots generated geometry',lambda s=section:snapshot(s,False))
    check('Frozen NanoMesh follows asset transform', lambda: travel('NanoMesh', 'frozen'))
    check('Frozen NanoMesh duplicate retains placement', lambda: independent_copy('NanoMesh', True))
    check('Array path survives setting and stage edits', curve_retained)
    check('Array setting preserves artist modifier interleaving',artist_stack)

landfall_studio.unregister()
report['ok'] = not report['failed']
save()
print('INSTANCE_TRANSFORM', len(report['passed']), 'passed', len(report['failed']), 'failed')
