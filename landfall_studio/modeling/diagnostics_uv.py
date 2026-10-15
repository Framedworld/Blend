"""Construction History Inspector, Guarded `Delete Non-Deformer History`, Read-Only Scene Diagnostics,
Deliberate Transform/Pivot Fixes, and UV/Material Utilities (`landfall_studio.modeling.diagnostics_uv`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import commands as cmd_registry
from ..ui import channel_box_ext

MODELING_MODIFIER_TYPES = frozenset(
    {
        "SUBSURF",
        "MULTIRES",
        "BEVEL",
        "SOLIDIFY",
        "MIRROR",
        "ARRAY",
        "BOOLEAN",
        "WEIGHTED_NORMAL",
        "NORMAL_EDIT",
        "TRIANGULATE",
        "DECIMATE",
        "WELD",
        "EDGE_SPLIT",
        "REMESH",
        "SCREW",
        "SKIN",
        "WIREFRAME",
    }
)

DEFORMER_MODIFIER_TYPES = frozenset(
    {
        "ARMATURE",
        "HOOK",
        "LATTICE",
        "MESH_DEFORM",
        "SURFACE_DEFORM",
        "SHRINKWRAP",
        "CURVE",
        "SIMPLE_DEFORM",
        "CAST",
        "CORRECTIVE_SMOOTH",
        "LAPLACIANSMOOTH",
        "SMOOTH",
        "DISPLACE",
        "WARP",
        "WAVE",
    }
)

TOPOLOGY_CHANGING_MODIFIER_TYPES = frozenset(
    {
        "SUBSURF",
        "MULTIRES",
        "BEVEL",
        "SOLIDIFY",
        "MIRROR",
        "ARRAY",
        "BOOLEAN",
        "TRIANGULATE",
        "DECIMATE",
        "WELD",
        "EDGE_SPLIT",
        "REMESH",
        "SCREW",
        "SKIN",
        "WIREFRAME",
    }
)


def _resolve_obj(obj_or_name: Any = None) -> Any:
    import bpy

    if obj_or_name is None:
        return getattr(bpy.context.view_layer.objects, "active", None)
    if isinstance(obj_or_name, str):
        return bpy.data.objects.get(obj_or_name)
    return obj_or_name


def snapshot_material_assignments(obj: Any) -> Dict[str, Any]:
    """Capture material slot names and per-polygon `material_index` tuple for verification."""
    if obj is None or getattr(obj, "type", "") != "MESH" or obj.data is None:
        return {"slots": [], "face_indices": ()}
    slots = [slot.material.name if slot.material else "" for slot in obj.material_slots]
    face_indices = tuple(int(p.material_index) for p in obj.data.polygons)
    return {
        "slots": slots,
        "face_indices": face_indices,
    }


def inspect_construction_history(obj_or_name: Any = None) -> Dict[str, Any]:
    """Read-only Construction History Inspector classifying modeling vs deformer modifiers and morph/rig guards."""
    obj = _resolve_obj(obj_or_name)
    if obj is None or getattr(obj, "type", "") != "MESH":
        return {
            "ok": False,
            "object_name": "",
            "parametric_input": None,
            "modeling_modifiers": [],
            "deformer_modifiers": [],
            "topology_changing_modifiers": [],
            "has_shape_keys": False,
            "shape_key_names": [],
            "has_vertex_groups": False,
            "vertex_group_names": [],
            "has_skin_armature": False,
            "shape_key_bake_hazard": False,
        }

    inputs_list = channel_box_ext.get_object_inputs(obj)
    prim_node = next((inp for inp in inputs_list if inp.get("kind") == "PRIMITIVE"), None)
    modeling_mods = []
    deformer_mods = []
    topo_mods = []

    for mod in obj.modifiers:
        mtype = str(mod.type)
        entry = {"name": mod.name, "type": mtype, "show_viewport": bool(mod.show_viewport)}
        if mtype in DEFORMER_MODIFIER_TYPES:
            deformer_mods.append(entry)
        else:
            modeling_mods.append(entry)
            if mtype in TOPOLOGY_CHANGING_MODIFIER_TYPES:
                topo_mods.append(mod.name)

    mesh = obj.data
    sk = getattr(mesh, "shape_keys", None)
    sk_blocks = list(sk.key_blocks) if (sk is not None and getattr(sk, "key_blocks", None)) else []
    sk_names = [kb.name for kb in sk_blocks]
    has_shape_keys = len(sk_names) > 0

    vg_names = [vg.name for vg in obj.vertex_groups]
    has_vgroups = len(vg_names) > 0
    has_armature = any(m["type"] == "ARMATURE" for m in deformer_mods) or (
        obj.parent is not None and getattr(obj.parent, "type", "") == "ARMATURE"
    )

    return {
        "ok": True,
        "object_name": obj.name,
        "linked_read_only": channel_box_ext.is_datablock_linked(obj),
        "parametric_input": prim_node.get("name") if prim_node else None,
        "modeling_modifiers": modeling_mods,
        "deformer_modifiers": deformer_mods,
        "modeling_count": len(modeling_mods),
        "deformer_count": len(deformer_mods),
        "topology_changing_modifiers": topo_mods,
        "has_shape_keys": has_shape_keys,
        "shape_key_names": sk_names,
        "has_vertex_groups": has_vgroups,
        "vertex_group_names": vg_names,
        "has_skin_armature": has_armature,
        "shape_key_bake_hazard": bool(has_shape_keys and len(topo_mods) > 0),
    }


def delete_non_deformer_history(
    obj_or_name: Any = None,
    force_remove_shape_keys: bool = False,
) -> Dict[str, Any]:
    """Implement Maya's `Edit > Delete by Type > Non-Deformer History`.

    - Applies only non-deformer modeling modifiers (`SUBSURF`, `BEVEL`, `SOLIDIFY`, `MIRROR`, etc.)
      and clears parametric `polyCube1` construction history.
    - Strictly preserves deformer modifiers (`ARMATURE`, `LATTICE`, `HOOK`, `SHRINKWRAP`, etc.)
      and all vertex-group skin weights.
    - Guards assets that have `Shape Keys` AND topology-changing modeling modifiers unless
      `force_remove_shape_keys=True`, preventing silent destruction of morph targets.
    """
    import bpy

    obj = _resolve_obj(obj_or_name)
    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False, "error": "Non-Deformer History deletion requires a MESH object."}

    if channel_box_ext.is_datablock_linked(obj):
        return {
            "ok": False,
            "read_only": True,
            "error": f"'{obj.name}' is linked from an external library and is read-only.",
        }

    info = inspect_construction_history(obj)
    if info["shape_key_bake_hazard"] and not force_remove_shape_keys:
        return {
            "ok": False,
            "guarded": True,
            "guarded_shape_keys": True,
            "object_name": obj.name,
            "reason": (
                f"Guarded morph asset '{obj.name}': cannot bake topology-changing modifiers "
                f"{info['topology_changing_modifiers']} onto mesh with Shape Keys {info['shape_key_names']}."
            ),
            "preserved_shape_keys": info["shape_key_names"],
            "preserved_deformers": [m["name"] for m in info["deformer_modifiers"]],
            "preserved_deformer_modifiers": [m["name"] for m in info["deformer_modifiers"]],
        }

    prev_mode = obj.mode
    if prev_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    applied_modifiers = []
    for mod_entry in info["modeling_modifiers"]:
        mod_name = mod_entry["name"]
        if obj.modifiers.get(mod_name) is not None:
            try:
                bpy.ops.object.modifier_apply(modifier=mod_name)
                applied_modifiers.append(mod_name)
            except Exception as exc:
                return {
                    "ok": False,
                    "object_name": obj.name,
                    "error": f"Failed applying non-deformer modifier '{mod_name}': {exc}",
                }

    # Clear parametric creation history node (`polyCube1`, etc.)
    if "_landfall_prim_history" in obj:
        try:
            del obj["_landfall_prim_history"]
        except Exception:
            pass
    if "landfall_prim_history" in obj:
        try:
            del obj["landfall_prim_history"]
        except Exception:
            pass

    if prev_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode=prev_mode)
        except Exception:
            pass

    post_info = inspect_construction_history(obj)
    cmd_registry.record_command(
        cmd_id="landfall_studio.delete_non_deformer_history",
        kwargs={"object_name": obj.name},
        callable_fn=lambda name=obj.name: delete_non_deformer_history(name),
        label="Delete Non-Deformer History",
        repeatable=True,
    )

    deformer_names = [m["name"] for m in post_info["deformer_modifiers"]]
    return {
        "ok": True,
        "guarded": False,
        "object_name": obj.name,
        "applied_modeling_modifiers": applied_modifiers,
        "preserved_deformers": deformer_names,
        "preserved_deformer_modifiers": deformer_names,
        "preserved_vertex_groups": post_info["vertex_group_names"],
        "preserved_shape_keys": post_info["shape_key_names"],
        "vertex_count": len(obj.data.vertices),
    }


def freeze_transformations_guarded(
    obj_or_name: Any = None,
    translate: bool = True,
    rotate: bool = True,
    scale: bool = True,
    preserve_children: bool = True,
    force_driven: bool = False,
) -> Dict[str, Any]:
    """Deliberate `Modify > Freeze Transformations` with rig/driver guards and child world-matrix preservation."""
    import bpy
    import blendertk as btk

    obj = _resolve_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "No object specified for Freeze Transformations."}
    if channel_box_ext.is_datablock_linked(obj):
        return {"ok": False, "read_only": True, "error": f"'{obj.name}' is linked and read-only."}

    # Check driving connections (drivers, action fcurves, constraints) and active armature skin
    driven_tags = btk.TransformDiagnostics._driving_connections(obj)
    has_armature_mod = any(m.type == "ARMATURE" for m in getattr(obj, "modifiers", []))
    if (driven_tags or has_armature_mod) and not force_driven:
        return {
            "ok": False,
            "guarded": True,
            "object_name": obj.name,
            "driven_tags": driven_tags,
            "has_armature_modifier": has_armature_mod,
            "reason": f"Guarded '{obj.name}': transform is driven or skinned to an Armature.",
        }

    # Snapshot children world matrices before freezing parent
    children = list(obj.children)
    child_world_before = {c.name: c.matrix_world.copy() for c in children}

    try:
        btk.freeze_transforms(
            [obj],
            location=bool(translate),
            rotation=bool(rotate),
            scale=bool(scale),
        )
    except Exception:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(
            location=bool(translate),
            rotation=bool(rotate),
            scale=bool(scale),
        )

    bpy.context.view_layer.update()
    max_child_delta = 0.0
    if preserve_children and children:
        for c in children:
            old_mw = child_world_before[c.name]
            c.matrix_world = old_mw
        bpy.context.view_layer.update()
        for c in children:
            old_mw = child_world_before[c.name]
            diff = max(abs(c.matrix_world[r][col] - old_mw[r][col]) for r in range(4) for col in range(4))
            max_child_delta = max(max_child_delta, float(diff))

    return {
        "ok": True,
        "guarded": False,
        "object_name": obj.name,
        "location": tuple(round(float(v), 5) for v in obj.location),
        "rotation_euler": tuple(round(float(v), 5) for v in obj.rotation_euler),
        "scale": tuple(round(float(v), 5) for v in obj.scale),
        "max_child_world_delta": max_child_delta,
        "max_child_matrix_diff": max_child_delta,
    }


def center_or_bake_pivot_guarded(
    obj_or_name: Any = None,
    mode: str = "CENTER",
    custom_world_pivot: Optional[Sequence[float]] = None,
    preserve_children: bool = True,
) -> Dict[str, Any]:
    """Deliberate `Modify > Center Pivot` / `Bake Pivot` preserving world vertex positions and child transforms."""
    import bpy
    from mathutils import Matrix, Vector

    obj = _resolve_obj(obj_or_name)
    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False, "error": "Center/Bake Pivot requires a MESH object."}
    if channel_box_ext.is_datablock_linked(obj):
        return {"ok": False, "read_only": True, "error": f"'{obj.name}' is linked and read-only."}

    children = list(obj.children)
    child_world_before = {c.name: c.matrix_world.copy() for c in children}

    mesh = obj.data
    mw = obj.matrix_world.copy()
    if not mesh.vertices:
        return {"ok": False, "error": "Mesh has no vertices."}

    world_verts = [mw @ v.co for v in mesh.vertices]
    min_x = min(p.x for p in world_verts)
    max_x = max(p.x for p in world_verts)
    min_y = min(p.y for p in world_verts)
    max_y = max(p.y for p in world_verts)
    min_z = min(p.z for p in world_verts)
    max_z = max(p.z for p in world_verts)

    m_upper = (mode or "CENTER").upper()
    if custom_world_pivot is not None:
        target_world_origin = Vector((float(custom_world_pivot[0]), float(custom_world_pivot[1]), float(custom_world_pivot[2])))
    elif m_upper == "BOTTOM":
        target_world_origin = Vector(((min_x + max_x) * 0.5, (min_y + max_y) * 0.5, min_z))
    else:
        target_world_origin = Vector(((min_x + max_x) * 0.5, (min_y + max_y) * 0.5, (min_z + max_z) * 0.5))

    new_mw = mw.copy()
    new_mw.translation = target_world_origin
    new_mw_inv = new_mw.inverted_safe()

    for v, w_co in zip(mesh.vertices, world_verts):
        v.co = new_mw_inv @ w_co
    mesh.update()

    obj.matrix_world = new_mw
    bpy.context.view_layer.update()

    max_child_delta = 0.0
    if preserve_children and children:
        for c in children:
            c.matrix_world = child_world_before[c.name]
        bpy.context.view_layer.update()
        for c in children:
            old_mw = child_world_before[c.name]
            diff = max(abs(c.matrix_world[r][col] - old_mw[r][col]) for r in range(4) for col in range(4))
            max_child_delta = max(max_child_delta, float(diff))

    max_vert_delta = max(
        ((obj.matrix_world @ v.co) - w_co).length
        for v, w_co in zip(mesh.vertices, world_verts)
    )

    return {
        "ok": True,
        "object_name": obj.name,
        "mode": m_upper,
        "new_origin_world": (float(target_world_origin.x), float(target_world_origin.y), float(target_world_origin.z)),
        "max_vertex_world_delta": float(max_vert_delta),
        "max_child_world_delta": float(max_child_delta),
        "max_child_matrix_diff": float(max_child_delta),
    }


def run_scene_diagnostics(objects: Any = None) -> Dict[str, Any]:
    """Run strictly read-only scene diagnostics across mesh topology, sheared transforms, and morph/rig hazards."""
    import bpy
    import blendertk as btk

    # Snapshot selection, active object, mode, and geometry counts to prove 100% read-only behavior
    active_before = getattr(bpy.context.view_layer.objects, "active", None)
    active_name_before = active_before.name if active_before is not None else ""
    mode_before = active_before.mode if active_before is not None else "OBJECT"
    sel_names_before = sorted(o.name for o in bpy.context.selected_objects)

    if objects is None:
        pool = list(bpy.context.scene.objects)
    elif hasattr(objects, "objects"):
        pool = list(objects.objects)
    else:
        pool = [_resolve_obj(o) for o in objects if _resolve_obj(o) is not None]

    meshes = [o for o in pool if getattr(o, "type", "") == "MESH"]
    vert_face_sig_before = {
        m.name: (len(m.data.vertices), len(m.data.edges), len(m.data.polygons))
        for m in meshes
        if m.data is not None
    }

    if meshes:
        mesh_counts = btk.MeshDiagnostics.find_problem_geometry(
            meshes,
            ngons=True,
            nonmanifold=True,
            nonplanar=True,
            concave=True,
            zero_area_faces=True,
            zero_length_edges=True,
            zero_uv_area=True,
            select=False,
        )
    else:
        mesh_counts = {
            "ngons": 0,
            "concave": 0,
            "nonplanar": 0,
            "interior": 0,
            "nonmanifold": 0,
            "loose": 0,
            "quads": 0,
            "zero_area_faces": 0,
            "zero_length_edges": 0,
            "zero_uv_area": 0,
        }

    non_ortho_raw = btk.TransformDiagnostics.get_non_orthogonal(
        pool, tolerance=1e-5, detailed=True
    )
    non_orthogonal = {
        obj.name: {
            "skew": float(info["skew"]),
            "cause": str(info["cause"]),
            "driven": list(info["driven"]),
        }
        for obj, info in non_ortho_raw.items()
    }

    history_reports = {m.name: inspect_construction_history(m) for m in meshes}
    morph_rig_hazards = [
        m_name
        for m_name, rep in history_reports.items()
        if rep.get("shape_key_bake_hazard") or rep.get("has_skin_armature")
    ]

    # Verify read-only invariants
    active_after = getattr(bpy.context.view_layer.objects, "active", None)
    active_name_after = active_after.name if active_after is not None else ""
    mode_after = active_after.mode if active_after is not None else "OBJECT"
    sel_names_after = sorted(o.name for o in bpy.context.selected_objects)
    vert_face_sig_after = {
        m.name: (len(m.data.vertices), len(m.data.edges), len(m.data.polygons))
        for m in meshes
        if m.data is not None
    }

    read_only_verified = (
        active_name_before == active_name_after
        and mode_before == mode_after
        and sel_names_before == sel_names_after
        and vert_face_sig_before == vert_face_sig_after
    )

    return {
        "ok": True,
        "read_only_verified": read_only_verified,
        "object_count": len(pool),
        "mesh_count": len(meshes),
        "mesh_issues": {k: int(v) for k, v in mesh_counts.items() if not k.startswith("_")},
        "non_orthogonal_objects": non_orthogonal,
        "transform_issues": {
            "sheared_transforms": len(non_orthogonal),
            "non_orthogonal": non_orthogonal,
        },
        "morph_rig_hazards": morph_rig_hazards,
        "history_reports": history_reports,
    }


# --------------------------------------------------------------------------------------
# UV & Material Utilities (backed by `blendertk.UvUtils`)
# --------------------------------------------------------------------------------------

def get_mesh_texel_density(
    obj_or_name: Any = None,
    map_size: int = 2048,
) -> Dict[str, Any]:
    """Measure texel density (`px/unit`) on `obj_or_name` via `blendertk.UvUtils.get_texel_density`."""
    import blendertk as btk

    obj = _resolve_obj(obj_or_name)
    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False, "error": "Texel density requires a MESH object."}

    td = btk.get_texel_density([obj], map_size=int(map_size))
    return {
        "ok": True,
        "object_name": obj.name,
        "map_size": int(map_size),
        "texel_density": float(td) if td is not None else 0.0,
    }


def set_mesh_texel_density(
    first_arg: Any = None,
    obj_or_name: Any = None,
    map_size: int = 2048,
    target_td: Optional[float] = None,
    density: Optional[float] = None,
) -> Dict[str, Any]:
    """Scale UV islands of `obj_or_name` to match `density` (`px/unit`) via `blendertk.UvUtils.set_texel_density`, preserving materials."""
    import blendertk as btk

    if isinstance(first_arg, (int, float)) and density is None and target_td is None:
        density = float(first_arg)
    elif first_arg is not None and not isinstance(first_arg, (int, float)) and obj_or_name is None:
        obj_or_name = first_arg

    target_val = float(target_td if target_td is not None else (density if density is not None else 256.0))
    obj = _resolve_obj(obj_or_name)
    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False, "error": "Texel density requires a MESH object."}

    mat_before = snapshot_material_assignments(obj)
    btk.set_texel_density([obj], density=target_val, map_size=int(map_size))
    achieved = btk.get_texel_density([obj], map_size=int(map_size))
    mat_after = snapshot_material_assignments(obj)
    ach_f = float(achieved) if achieved is not None else 0.0

    return {
        "ok": True,
        "object_name": obj.name,
        "target_density": target_val,
        "achieved_density": ach_f,
        "new_td": ach_f,
        "map_size": int(map_size),
        "materials_preserved": (mat_before == mat_after),
    }


def uv_unwrap_and_pack(
    obj_or_name: Any = None,
    margin: float = 0.02,
    angle_limit_deg: float = 66.0,
    method: str = "SMART",
) -> Dict[str, Any]:
    """Unwrap and pack UV islands on `obj_or_name` without altering material assignments."""
    import math
    import bpy
    import blendertk as btk

    obj = _resolve_obj(obj_or_name)
    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False, "error": "UV unwrap requires a MESH object."}

    mat_before = snapshot_material_assignments(obj)
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="map1")

    with btk.edit_mode([obj]):
        bpy.ops.mesh.select_all(action="SELECT")
        if str(method).upper() == "ANGLE":
            bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=float(margin))
        else:
            bpy.ops.uv.smart_project(
                angle_limit=math.radians(float(angle_limit_deg)),
                island_margin=float(margin),
            )
        bpy.ops.uv.pack_islands(margin=float(margin), rotate=True)

    mat_after = snapshot_material_assignments(obj)
    td = btk.get_texel_density([obj], map_size=2048)

    return {
        "ok": True,
        "object_name": obj.name,
        "uv_layer": obj.data.uv_layers.active.name if obj.data.uv_layers.active else "",
        "texel_density_2k": float(td) if td is not None else 0.0,
        "materials_preserved": (mat_before == mat_after),
    }


def uv_cleanup_sets_guarded(
    obj_or_name: Any = None,
    primary_name: str = "map1",
    keep_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Clean up redundant UV sets and standardize primary UV set name via `btk.cleanup_uv_sets`."""
    import blendertk as btk

    if keep_names and len(keep_names) > 0:
        primary_name = str(keep_names[0])

    obj = _resolve_obj(obj_or_name)
    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False, "error": "UV cleanup requires a MESH object."}

    mat_before = snapshot_material_assignments(obj)
    results = btk.cleanup_uv_sets(
        [obj],
        remove_empty=True,
        keep_only_primary=True,
        prefer_largest_area=False,
        rename_to_map1=(primary_name == "map1"),
    )
    mat_after = snapshot_material_assignments(obj)
    row = results[0] if results else None
    deleted = list(row.deleted) if row else []

    return {
        "ok": True,
        "object_name": obj.name,
        "final_uv_set": row.final_name if row else primary_name,
        "deleted_sets": deleted,
        "removed_uv_sets": deleted,
        "materials_preserved": (mat_before == mat_after),
    }
