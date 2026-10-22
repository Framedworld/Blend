"""Disposable launch fixture, never applied to a loaded artist scene."""
import math
import sys
import bpy
from . import enter,ops,state


def create_demo():
    if '--factory-startup' not in sys.argv or '--sculpt-demo' not in sys.argv or bpy.data.filepath:
        raise RuntimeError('Sculpt demo requires a fresh factory launch with --sculpt-demo')
    with bpy.context.temp_override(**ops.view_context()):
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        root=bpy.data.objects.new('GoZ_Creature_grp',None);bpy.context.collection.objects.link(root)
        bpy.ops.mesh.primitive_monkey_add()
        body=ops.active();body.name='Creature_Sculpt';body.parent=root
        mod=body.modifiers.new('Demo surface','SUBSURF');mod.levels=2
        bpy.ops.object.modifier_apply(modifier=mod.name)
        for p in body.data.polygons:p.use_smooth=True
        for side in (-1,1):
            bpy.ops.mesh.primitive_cone_add(vertices=40,radius1=.13,radius2=.015,depth=.6,
                location=(side*.63,.05,.95),rotation=(0,side*math.radians(20),0))
            horn=ops.active();horn.name='Horn_L' if side<0 else 'Horn_R';horn.parent=root
            for p in horn.data.polygons:p.use_smooth=True
        bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
        enter()
        ops.layer('NEW',name='Creature Form Pass')
        ops.matcap('Red Wax')
        s=state.get();s.show_shortcut_hud=False;s.draw_size=60;s.z_intensity=30;s.focal_shift=-40
        bpy.context.scene.landfall_grid_finite=False
        sp=bpy.context.space_data
        for field in ('show_floor','show_ortho_grid','show_axis_x','show_axis_y','show_axis_z'):setattr(sp.overlay,field,False)
        sp.shading.background_type='VIEWPORT';sp.shading.background_color=(.09,.10,.115)
        bpy.ops.view3d.view_axis(type='FRONT');sp.region_3d.view_location=(0,0,.15);sp.region_3d.view_distance=5
    return {'object':body.name,'vertices':len(body.data.vertices),'layer':body.active_shape_key.name}
