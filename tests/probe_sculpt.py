import bpy, json
from pathlib import Path
r = {}
for name in ('sculpt.brush_stroke','paint.mask_box_gesture','paint.hide_show','paint.hide_show_masked','paint.visibility_invert','sculpt.mask_filter','sculpt.face_sets_create','sculpt.face_set_change_visibility','object.multires_subdivide','object.multires_higher_levels_delete','object.multires_base_apply','object.quadriflow_remesh','brush.asset_activate','object.transfer_mode'):
    try:
        ns, op = name.split('.')
        r[name] = {p.identifier: {'type':p.type, 'default':str(getattr(p,'default',None)), 'enum': [x.identifier for x in p.enum_items] if p.type=='ENUM' else []} for p in getattr(getattr(bpy.ops,ns),op).get_rna_type().properties if p.identifier!='rna_type'}
    except Exception as e: r[name]=str(e)
r['brush_props'] = {p.identifier:p.type for p in bpy.types.Brush.bl_rna.properties}
r['stroke_props'] = {p.identifier:p.type for p in bpy.types.OperatorStrokeElement.bl_rna.properties}
r['assets'] = [str(x) for x in Path(bpy.utils.system_resource('DATAFILES')).rglob('*Sculpt*')]
Path(__file__).resolve().parents[1].joinpath('output/sculpt_probe.json').write_text(json.dumps(r,indent=2))
