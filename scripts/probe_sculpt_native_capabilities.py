import bpy,json
from pathlib import Path
out={}
for space,names in {
    'sculpt': ['mesh_filter','color_filter','mask_filter','mask_from_cavity','mask_by_color','mask_init','face_sets_create','face_sets_init','symmetrize','optimize','dynamic_topology_toggle','paint_mask_extract'],
    'object':['multires_unsubdivide','multires_rebuild_subdiv','multires_base_apply','multires_reshape','multires_subdivide','modifier_apply','shape_key_move','shape_key_mirror'],
    'mesh':['vertices_smooth_laplacian','unsubdivide','uv_texture_add','intersect_boolean','subdivide','mark_sharp'],
    'paint':['mask_flood_fill','hide_show_masked'],
}.items():
    for name in names:
        try:
            rna=getattr(getattr(bpy.ops,space),name).get_rna_type()
            out[space+'.'+name]={p.identifier:{'type':p.type,'default':str(getattr(p,'default','')),'enum':[e.identifier for e in p.enum_items] if p.type=='ENUM' else []} for p in rna.properties if p.identifier!='rna_type'}
        except Exception as e:out[space+'.'+name]={'error':str(e)}
for name in ['ArrayModifier','SimpleDeformModifier','MultiresModifier','SubsurfModifier','ShrinkwrapModifier','GeometryNodeDistributePointsOnFaces','GeometryNodeInstanceOnPoints','GeometryNodeMeshToPoints']:
    rna=getattr(bpy.types,name).bl_rna
    out[name]={p.identifier:{'type':p.type,'enum':[e.identifier for e in p.enum_items] if p.type=='ENUM' else []} for p in rna.properties if not p.is_readonly}
Path(__file__).resolve().parents[1].joinpath('output/sculpt_native_capabilities.json').write_text(json.dumps(out,indent=2))
