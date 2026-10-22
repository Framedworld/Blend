"""Configured local copies of Blender Essentials brushes; two-letter catalog."""
from pathlib import Path
import json
import bpy
from . import state

CATALOG = {
    'ST': ('Standard', 'Draw', {'curve_preset':'SMOOTH','auto_smooth_factor':0.0,'normal_weight':0.0}),
    'CB': ('ClayBuildup', 'Clay Strips', {'use_accumulate':True, 'tip_roundness':0.0,'auto_smooth_factor':0.05,'normal_radius_factor':0.5}),
    'CL': ('Clay', 'Clay', {'auto_smooth_factor':0.1,'plane_offset':0.0}),
    'CR': ('Crease', 'Crease Polish', {}),
    'MV': ('Move', 'Grab', {}),
    'MT': ('Move Topological', 'Grab', {'use_automasking_topology':True}),
    'DS': ('DamStandard', 'Draw Sharp', {'curve_preset':'SHARP','crease_pinch_factor':0.65,'auto_smooth_factor':0.0}),
    'TD': ('TrimDynamic', 'Scrape/Fill', {'use_multiplane_scrape_dynamic':True,'plane_offset':0.0,'auto_smooth_factor':0.15}),
    'HP': ('hPolish', 'Flatten/Contrast', {'use_plane_trim':True,'use_original_plane':True,'use_original_normal':True,'plane_offset':0.0}),
    'IN': ('Inflate', 'Inflate/Deflate', {}),
    'PI': ('Pinch', 'Pinch/Magnify', {}),
    'SH': ('SnakeHook', 'Snake Hook', {}),
    'SM': ('Smooth', 'Smooth', {}),
    'MP': ('MaskPen', 'Mask', {}),
    'IM': ('IMM Primitives', 'Draw', {}),
}

FIELDS=('z_intensity','focal_shift','stroke_method','alpha','lazy_mouse','lazy_radius','lazy_smooth','z_mode')
PURPOSE={
    'ST':'Build or carve rounded forms.', 'CB':'Build broad clay planes in layers.',
    'CL':'Lay down soft, broad clay masses.', 'CR':'Carve a crease and pinch its edges.',
    'MV':'Pull the silhouette and adjust large proportions.', 'MT':'Move only the connected surface under the brush.',
    'DS':'Cut crisp grooves and separate forms.', 'TD':'Trim peaks into broad planar facets.',
    'HP':'Flatten and polish planes.', 'IN':'Expand or deflate the surface along its normals.',
    'PI':'Gather a surface toward the stroke.', 'SH':'Pull long extensions from the surface.',
    'SM':'Relax bumps and blend transitions.', 'MP':'Paint a mask to protect the surface.',
    'IM':'Drag on the surface to insert the current part; click empty canvas to choose a part.',
}
ASSETS=Path(__file__).resolve().parents[1]/'assets/sculpt'

def code_for(name):return next((k for k,v in CATALOG.items() if name in (k,v[0])), 'ST')

def icon(code):
    from PySide6.QtGui import QIcon
    return QIcon(str(ASSETS/(code+'.svg')))

def snapshot(context=None):
    s=state.get(context);b=state.brush(context)
    if b is None or b.name!='Landfall · '+s.active_zbrush_brush:return
    # Read the actual native brush as well as UI-only alpha/direction state.
    values={key:getattr(s,key) for key in FIELDS}
    values.update(z_intensity=b.strength*100,focal_shift=b.hardness*200-100,
        stroke_method=b.stroke_method,lazy_mouse=b.use_smooth_stroke,
        lazy_radius=b.smooth_stroke_radius,lazy_smooth=b.smooth_stroke_factor)
    entry=s.brushes.get(s.active_zbrush_brush)
    if entry is None:entry=s.brushes.add();entry.name=s.active_zbrush_brush
    entry.settings=json.dumps(values)

def restore(label,context=None):
    s=state.get(context);entry=s.brushes.get(label)
    values={'z_intensity':50.,'focal_shift':-50.,'stroke_method':'SPACE','alpha':'SQUARE' if label=='ClayBuildup' else 'NONE',
        'lazy_mouse':False,'lazy_radius':75,'lazy_smooth':.9,'z_mode':'SUBTRACT' if label in ('DamStandard','Crease') else 'ADD'}
    if entry:
        try:values.update({k:v for k,v in json.loads(entry.settings).items() if k in FIELDS})
        except (ValueError,TypeError):pass
    state.hydrating=True
    try:
        for key,value in values.items():setattr(s,key,value)
    finally:state.hydrating=False
    state.apply_brush_settings(s,context)
    set_stroke(method=s.stroke_method,alpha=s.alpha,context=context)

def reset(context=None):
    ctx=context or bpy.context;s=state.get(ctx);label=s.active_zbrush_brush
    entry=s.brushes.get(label)
    if entry:s.brushes.remove(s.brushes.find(label))
    old=bpy.data.brushes.get('Landfall · '+label)
    if old:old.asset_clear();old.name+=' · Previous'
    return select(label,ctx,remember=False)


def catalog_path():
    return Path(bpy.utils.system_resource('DATAFILES')) / 'assets/brushes/essentials_brushes-mesh_sculpt.blend'


def tool_id(brush):
    return {'MASK':'builtin_brush.mask','PAINT':'builtin_brush.paint','DRAW_FACE_SETS':'builtin_brush.draw_face_sets'}.get(brush.sculpt_brush_type if brush else '', 'builtin.brush')


def select(name, context=None, remember=True):
    ctx = context or bpy.context
    if remember:snapshot(ctx)
    spec = next((v for k,v in CATALOG.items() if name in (k,v[0])), None)
    if spec is None:
        raise ValueError('Unknown sculpt brush: ' + name)
    label, native, settings = spec
    local_name = 'Landfall · ' + label
    b = bpy.data.brushes.get(local_name)
    if b is None:
        with bpy.data.libraries.load(str(catalog_path()), link=False, assets_only=True) as (src,dst):
            if native not in src.brushes:
                raise RuntimeError(f'Bundled brush {native!r} unavailable; found {src.brushes}')
            dst.brushes = [native]
        b = dst.brushes[0].copy()
        b.name = local_name
        b.asset_mark()
        for key,value in settings.items():
            if hasattr(b,key):
                setattr(b,key,value)
            elif hasattr(b.mesh_automasking_settings,key):
                setattr(b.mesh_automasking_settings,key,value)
    # Paint.brush is readonly in 5.x: activate an actual local brush asset.
    result = bpy.ops.brush.asset_activate(asset_library_type='LOCAL', relative_asset_identifier='Brush/' + b.name)
    if 'FINISHED' not in result:
        raise RuntimeError('Unable to activate ' + label)
    s = state.get(ctx)
    s.active_zbrush_brush = label
    s.rgb_enabled = False
    s.navigation_tool = 'DRAW'
    restore(label,ctx)
    bpy.ops.wm.tool_set_by_id(name=tool_id(b))
    sp=ctx.space_data
    if sp and sp.type=='VIEW_3D':
        sp.show_gizmo_object_translate=False
        sp.show_gizmo_object_rotate=False
        sp.show_gizmo_object_scale=False
    from ..keymaps import profiles
    if profiles._sculpt_keymaps:
        profiles._settle_keyconfigs(ctx)
        profiles._refresh_sculpt_mutes()
    profiles.sync_sculpt_paint_mode(ctx)
    from . import preferences
    preferences.remember(code_for(label))
    return {'ok':True, 'brush':label, 'native':b.sculpt_brush_type}


def set_stroke(method=None, alpha=None, context=None):
    s, b = state.get(context), state.brush(context)
    if method is not None:
        s.stroke_method = method
        b.stroke_method = method
    if alpha is not None:
        s.alpha = alpha
        if alpha == 'NONE':
            b.texture = None
            b.tip_roundness = 1
        elif alpha == 'SQUARE':
            tex=bpy.data.textures.get('Landfall Sculpt Square')
            if tex is None:
                image=bpy.data.images.new('Landfall Sculpt Square',width=64,height=64,alpha=True)
                image.pixels.foreach_set([component for y in range(64) for x in range(64) for component in ((1.,1.,1.,1.) if 12<=x<52 and 12<=y<52 else (0.,0.,0.,1.))])
                tex=bpy.data.textures.new('Landfall Sculpt Square',type='IMAGE');tex.image=image
            b.texture = tex
            b.texture_slot.map_mode='VIEW_PLANE'
            b.tip_roundness = 0
        else:
            tex = bpy.data.textures.get('Landfall Sculpt Noise') or bpy.data.textures.new('Landfall Sculpt Noise', type='CLOUDS')
            b.texture = tex
    return {'ok':True}
