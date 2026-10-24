"""Scene-owned sculpt controls. Brush controls always write to the real brush."""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, IntVectorProperty, StringProperty, CollectionProperty

hydrating=False

class BrushMemory(bpy.types.PropertyGroup):
    settings: StringProperty(default='{}')


def brush(context=None):
    return (context or bpy.context).tool_settings.sculpt.brush


def apply_brush_settings(self=None, context=None):
    if hydrating:return
    ctx = context or bpy.context
    s = self or ctx.scene.landfall_sculpt
    b = brush(ctx)
    if b is None:
        return
    ups = ctx.tool_settings.sculpt.unified_paint_settings
    ups.use_unified_size = False
    ups.use_unified_strength = False
    b.size = s.draw_size
    b.strength = s.z_intensity / 100.0
    subtract=s.z_mode=='SUBTRACT'
    directions={'INFLATE':('INFLATE','DEFLATE'),'PINCH':('PINCH','MAGNIFY'),
                'SMOOTH':('SMOOTH','ENHANCE_DETAILS'),'GRAB':('DEFAULT','DEFAULT'),
                'SNAKE_HOOK':('DEFAULT','DEFAULT'),'PAINT':('ADD','SUBTRACT')}
    direction=directions.get(b.sculpt_brush_type,('ADD','SUBTRACT'))[subtract]
    if b.sculpt_brush_type!='PAINT': b.direction = direction
    b.hardness = (s.focal_shift + 100.0) / 200.0
    b.use_smooth_stroke = s.lazy_mouse
    b.smooth_stroke_radius = s.lazy_radius
    b.smooth_stroke_factor = s.lazy_smooth


class SculptState(bpy.types.PropertyGroup):
    brushes: CollectionProperty(type=BrushMemory)
    auto_activate: BoolProperty(name="Automatic ZBrush Sculpt Studio", default=True)
    bbrush_enabled: BoolProperty(name="Bbrush pen controls", default=True)
    active_zbrush_brush: StringProperty(default="Standard")
    imm_into_subtool: BoolProperty(name='Insert into SubTool', default=False,
        description='Join inserted parts into the sculpted SubTool and mask the rest, as ZBrush does')
    imm_part: StringProperty(name='IMM Part', default='SPHERE',
        description='Part the IMM brush inserts: a primitive or a mesh in the IMM Parts collection')
    z_mode: EnumProperty(items=[('ADD', 'ZAdd', ''), ('SUBTRACT', 'ZSub', '')], default='ADD', update=apply_brush_settings)
    rgb_enabled: BoolProperty(default=False)
    mrgb_enabled: BoolProperty(default=False)
    draw_size: IntProperty(default=50, min=1, max=500, update=apply_brush_settings)
    focal_shift: FloatProperty(default=-50, min=-100, max=100, update=apply_brush_settings)
    z_intensity: FloatProperty(default=50, min=0, max=100, update=apply_brush_settings)
    lazy_mouse: BoolProperty(default=False, update=apply_brush_settings)
    lazy_radius: IntProperty(default=75, min=1, max=200, update=apply_brush_settings)
    lazy_smooth: FloatProperty(default=0.9, min=0, max=0.99, update=apply_brush_settings)
    dynamesh_enabled: BoolProperty(default=False)
    sculptris_detail: FloatProperty(name='Sculptris Pro Detail', default=25.0, min=5.0, max=100.0,
        description='Triangle size as a percentage of the brush size (smaller is finer)')
    dynamesh_resolution: IntProperty(default=128, min=16, max=512)
    zremesher_target_polys: IntProperty(default=5000, min=100, max=200000)
    keep_groups: BoolProperty(default=True)
    adaptive: BoolProperty(default=True)
    silhouette_mode: EnumProperty(items=[('ONLY_SCULPT', 'Only Sculpt', ''), ('ALWAYS', 'Always', ''), ('DISABLE', 'Hide', '')], default='ONLY_SCULPT')
    silhouette_scale: FloatProperty(default=1, min=0.4, max=3)
    silhouette_pos: IntVectorProperty(size=2, default=(18, 48))
    show_shortcut_hud: BoolProperty(default=False)
    solo_active: BoolProperty(default=False)
    polyframe_active: BoolProperty(default=False)
    ghost_transparency_active: BoolProperty(default=False)
    active_matcap: StringProperty(default="Grey Clay")
    stroke_method: EnumProperty(items=[(x,x.title(),'') for x in ('SPACE','DOTS','DRAG_DOT','ANCHORED','AIRBRUSH')], default='SPACE')
    alpha: EnumProperty(items=[('NONE','Round',''),('SQUARE','Square',''),('NOISE','Noise','')], default='NONE')
    mask_marquee: EnumProperty(items=[('BOX','Box',''),('LASSO','Lasso','')], default='BOX')
    extract_thickness: FloatProperty(default=0.02, min=0.0001, max=10)
    deformation_amount: FloatProperty(default=0.1, min=-1, max=1)
    record_layer: BoolProperty(default=False)
    record_layer_name: StringProperty(default='')
    navigation_tool: EnumProperty(items=[(x,x.title(),'') for x in ('DRAW','MOVE','ZOOM','ROTATE')], default='DRAW')


def get(context=None):
    return (context or bpy.context).scene.landfall_sculpt


def register():
    bpy.utils.register_class(BrushMemory)
    bpy.utils.register_class(SculptState)
    bpy.types.Scene.landfall_sculpt = bpy.props.PointerProperty(type=SculptState)


def unregister():
    del bpy.types.Scene.landfall_sculpt
    bpy.utils.unregister_class(SculptState)
    bpy.utils.unregister_class(BrushMemory)
