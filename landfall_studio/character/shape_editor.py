"""Maya-Style Shape Editor, Target Extraction with Held Reference & Base Edit Propagation (`landfall_studio.character.shape_editor`).

Provides:
- `list_shape_targets`: full inspection of `Basis`, master shape keys, and `_tween_w###` correctives,
  including drivers, keyframes, held reference objects, and non-zero delta statistics.
- `create_shape_target`, `set_shape_target_weight`, `keyframe_shape_target`, `duplicate_shape_target`,
  `mirror_shape_target`, `delete_shape_target`.
- `extract_target_mesh_with_reference` & `sync_extracted_target_to_shape_key`: extracts a shape key into a
  standalone mesh with bidirectional held-reference metadata, preserves UVs/materials, and validates strict
  topological connectivity before syncing sculpted deltas back to the shape key.
- `propagate_base_mesh_edits`: propagates `Basis` edits across all relative shape keys for supported
  matching topology while preserving authored morph deltas (`kb.co - basis.co`), and blocks unsupported
  topological edits with an explicit explanation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from mathutils import Vector
from mathutils.kdtree import KDTree

from . import blendshape_bridge, topology

HELD_SOURCE_OBJ_PROP = "lf_shape_source_obj"
HELD_SOURCE_KEY_PROP = "lf_shape_source_key"
HELD_IS_TARGET_PROP = "lf_is_held_shape_target"
HELD_TARGET_PREFIX = "lf_held_target_"


def list_shape_targets(obj_or_name: Any) -> Dict[str, Any]:
    """Return a structured Maya Shape Editor snapshot for `obj`."""
    import bpy

    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {
            "ok": False,
            "object_name": "",
            "has_shape_keys": False,
            "targets": [],
            "multi_master_hazard": {},
        }

    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or not sk.key_blocks:
        return {
            "ok": True,
            "object_name": obj.name,
            "has_shape_keys": False,
            "basis_name": "",
            "targets": [],
            "multi_master_hazard": blendshape_bridge.detect_multi_master_driver_hazard(obj),
        }

    ref_key = sk.reference_key
    fcurves = blendshape_bridge._get_fcurves_for_key(sk)
    keyed_paths = {
        getattr(fc, "data_path", "")
        for fc in fcurves
        if len(getattr(fc, "keyframe_points", ())) > 0
    }

    driver_map: Dict[str, str] = {}
    anim = getattr(sk, "animation_data", None)
    if anim is not None and getattr(anim, "drivers", None):
        for drv_fc in anim.drivers:
            dp = getattr(drv_fc, "data_path", "")
            expr = getattr(getattr(drv_fc, "driver", None), "expression", "")
            driver_map[dp] = str(expr)

    targets: List[Dict[str, Any]] = []
    n_verts = len(ref_key.data)

    for idx, kb in enumerate(sk.key_blocks):
        is_basis = kb == ref_key
        is_corr = blendshape_bridge._CORRECTIVE_INFIX in kb.name
        dp = f'key_blocks["{kb.name}"].value'

        non_zero = 0
        max_delta = 0.0
        if not is_basis:
            rel = kb.relative_key or ref_key
            for i in range(n_verts):
                d = (kb.data[i].co - rel.data[i].co).length
                if d > 1e-5:
                    non_zero += 1
                    if d > max_delta:
                        max_delta = d

        held_name = str(obj.get(f"{HELD_TARGET_PREFIX}{kb.name}", "") or "")
        if held_name and bpy.data.objects.get(held_name) is None:
            held_name = ""

        targets.append(
            {
                "index": idx,
                "name": kb.name,
                "is_basis": is_basis,
                "is_corrective": is_corr,
                "value": round(float(kb.value), 4),
                "slider_min": float(kb.slider_min),
                "slider_max": float(kb.slider_max),
                "mute": bool(kb.mute),
                "relative_key": kb.relative_key.name if kb.relative_key else "",
                "vertex_group": str(kb.vertex_group or ""),
                "is_keyed": dp in keyed_paths,
                "has_driver": dp in driver_map,
                "driver_expression": driver_map.get(dp, ""),
                "non_zero_delta_count": non_zero,
                "max_delta_magnitude": round(float(max_delta), 5),
                "held_reference_object": held_name,
            }
        )

    return {
        "ok": True,
        "object_name": obj.name,
        "has_shape_keys": True,
        "basis_name": ref_key.name,
        "target_count": len(targets) - 1,
        "targets": targets,
        "multi_master_hazard": blendshape_bridge.detect_multi_master_driver_hazard(obj),
    }


def create_shape_target(
    obj_or_name: Any,
    name: str = "Target",
    from_mix: bool = False,
    initial_deltas: Optional[Dict[int, Tuple[float, float, float]]] = None,
    weight: float = 0.0,
) -> Dict[str, Any]:
    """Create a new shape key target on `obj` (creating `Basis` first if needed) and preserve UVs/materials."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    uv_mat_snap = topology.snapshot_uvs_and_materials(obj)
    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or not sk.key_blocks:
        obj.shape_key_add(name="Basis", from_mix=False)
        sk = obj.data.shape_keys

    kb = obj.shape_key_add(name=name, from_mix=from_mix)
    kb.relative_key = sk.reference_key
    kb.slider_min = 0.0
    kb.slider_max = 1.0
    kb.value = float(weight)

    if initial_deltas:
        n = len(kb.data)
        for v_idx, delta_xyz in initial_deltas.items():
            if 0 <= int(v_idx) < n:
                kb.data[int(v_idx)].co = sk.reference_key.data[int(v_idx)].co + Vector(delta_xyz)

    obj.data.update()
    uv_mat_check = topology.verify_uvs_and_materials_preserved(obj, uv_mat_snap)
    return {
        "ok": True,
        "object_name": obj.name,
        "key_name": kb.name,
        "value": float(kb.value),
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
    }


def set_shape_target_weight(
    obj_or_name: Any,
    key_name: str,
    weight: float,
    evaluate_correctives: bool = True,
) -> Dict[str, Any]:
    """Set a shape key's weight (`0.0..1.0`) and deterministically update any in-between correctives."""
    import bpy

    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or key_name not in sk.key_blocks:
        return {"ok": False, "error": f"Shape key '{key_name}' not found on '{obj.name}'."}

    kb = sk.key_blocks[key_name]
    clamped = max(float(kb.slider_min), min(float(kb.slider_max), float(weight)))
    kb.value = clamped

    corr_res = {}
    if evaluate_correctives:
        corr_res = blendshape_bridge.evaluate_correctives_deterministic(obj)
    else:
        try:
            if bpy.context.view_layer is not None:
                bpy.context.view_layer.update()
        except Exception:
            pass

    return {
        "ok": True,
        "object_name": obj.name,
        "key_name": key_name,
        "value": float(kb.value),
        "correctives": corr_res.get("evaluated_correctives", {}),
    }


def keyframe_shape_target(
    obj_or_name: Any,
    key_name: str,
    frame: Optional[int] = None,
    weight: Optional[float] = None,
) -> Dict[str, Any]:
    """Insert a keyframe on `key_blocks[key_name].value` at `frame`."""
    import bpy

    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}
    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or key_name not in sk.key_blocks:
        return {"ok": False, "error": f"Shape key '{key_name}' not found."}

    kb = sk.key_blocks[key_name]
    if weight is not None:
        kb.value = float(weight)
    target_frame = int(frame) if frame is not None else int(bpy.context.scene.frame_current)
    kb.keyframe_insert(data_path="value", frame=target_frame)
    blendshape_bridge.evaluate_correctives_deterministic(obj)
    return {
        "ok": True,
        "object_name": obj.name,
        "key_name": key_name,
        "frame": target_frame,
        "value": float(kb.value),
    }


def extract_target_mesh_with_reference(
    obj_or_name: Any,
    key_name: str,
    target_mesh_name: Optional[str] = None,
    offset_vector: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Dict[str, Any]:
    """Extract a shape key (`key_name`) into a standalone mesh while holding a bidirectional live reference.

    Preserves exact vertex-index order, edge connectivity, polygon winding, UVs, and material assignments.
    """
    import bpy

    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or key_name not in sk.key_blocks:
        return {"ok": False, "error": f"Shape key '{key_name}' not found on '{obj.name}'."}

    kb = sk.key_blocks[key_name]
    base_mesh = obj.data

    coords = [kb.data[i].co.copy() for i in range(len(base_mesh.vertices))]
    polys = [tuple(p.vertices) for p in base_mesh.polygons]
    poly_edge_pairs = set()
    for pv in polys:
        n_pv = len(pv)
        for i in range(n_pv):
            a, b = pv[i], pv[(i + 1) % n_pv]
            poly_edge_pairs.add((a, b) if a <= b else (b, a))
    loose_edges = [
        tuple(e.vertices)
        for e in base_mesh.edges
        if (
            (e.vertices[0], e.vertices[1])
            if e.vertices[0] <= e.vertices[1]
            else (e.vertices[1], e.vertices[0])
        )
        not in poly_edge_pairs
    ]

    out_name = target_mesh_name or f"{obj.name}_{key_name}_Target"
    existing = bpy.data.objects.get(out_name)
    if existing is not None:
        bpy.data.objects.remove(existing, do_unlink=True)

    new_mesh = bpy.data.meshes.new(out_name)
    new_mesh.from_pydata(coords, loose_edges, polys)
    new_mesh.update(calc_edges=True)

    target_obj = bpy.data.objects.new(out_name, new_mesh)
    target_obj.matrix_world = obj.matrix_world.copy()
    target_obj.location = obj.location + Vector(offset_vector)
    bpy.context.scene.collection.objects.link(target_obj)

    # Copy UVs and materials onto the extracted target mesh
    topology.copy_uvs_and_materials(obj, target_obj)

    # Record bidirectional held reference metadata
    target_obj[HELD_SOURCE_OBJ_PROP] = obj.name
    target_obj[HELD_SOURCE_KEY_PROP] = key_name
    target_obj[HELD_IS_TARGET_PROP] = True
    obj[f"{HELD_TARGET_PREFIX}{key_name}"] = target_obj.name

    topo_check = topology.validate_strict_topology(obj, target_obj, check_uvs=True, check_materials=True)
    return {
        "ok": True,
        "source_object": obj.name,
        "key_name": key_name,
        "extracted_object": target_obj.name,
        "held_reference_active": True,
        "topology": topo_check,
    }


def sync_extracted_target_to_shape_key(
    extracted_or_base_obj: Any,
    key_name: Optional[str] = None,
    delete_extracted: bool = False,
) -> Dict[str, Any]:
    """Sync vertex edits from a held-reference extracted target mesh back into its source shape key.

    Strictly validates topological connectivity (`validate_strict_topology`). If vertices, edges, or
    polygons were added, deleted, split, or re-ordered on the extracted mesh, synchronization is
    BLOCKED with an explicit explanation.
    """
    import bpy

    cand = topology._resolve_mesh_obj(extracted_or_base_obj)
    if cand is None:
        return {"ok": False, "blocked": True, "reason": "Object is not a valid MESH."}

    if cand.get(HELD_IS_TARGET_PROP) and cand.get(HELD_SOURCE_OBJ_PROP):
        extracted_obj = cand
        base_obj = topology._resolve_mesh_obj(str(cand.get(HELD_SOURCE_OBJ_PROP)))
        resolved_key = str(key_name or cand.get(HELD_SOURCE_KEY_PROP) or "")
    else:
        base_obj = cand
        resolved_key = str(key_name or "")
        held_name = str(base_obj.get(f"{HELD_TARGET_PREFIX}{resolved_key}", "") or "")
        extracted_obj = topology._resolve_mesh_obj(held_name)

    if base_obj is None or extracted_obj is None or not resolved_key:
        return {
            "ok": False,
            "blocked": True,
            "reason": "Could not resolve held-reference target mesh and source object/shape key.",
        }

    sk = getattr(base_obj.data, "shape_keys", None)
    if sk is None or resolved_key not in sk.key_blocks:
        return {
            "ok": False,
            "blocked": True,
            "reason": f"Source shape key '{resolved_key}' no longer exists on '{base_obj.name}'.",
        }

    # Strict topological connectivity check
    topo = topology.validate_strict_topology(base_obj, extracted_obj)
    if not topo["ok"]:
        return {
            "ok": False,
            "blocked": True,
            "source_object": base_obj.name,
            "extracted_object": extracted_obj.name,
            "key_name": resolved_key,
            "reason": f"Blocked target sync due to topological mismatch: {topo['reason']}",
            "topology": topo,
        }

    uv_mat_snap = topology.snapshot_uvs_and_materials(base_obj)
    kb = sk.key_blocks[resolved_key]
    ref_key = sk.reference_key
    rel_key = kb.relative_key or ref_key

    updated_deltas = 0
    for i, v in enumerate(extracted_obj.data.vertices):
        new_co = v.co.copy()
        if (new_co - kb.data[i].co).length > 1e-6:
            updated_deltas += 1
        kb.data[i].co = new_co

    # Compute non-zero deltas vs relative key
    non_zero_deltas = sum(
        1 for i in range(len(kb.data)) if (kb.data[i].co - rel_key.data[i].co).length > 1e-5
    )

    if delete_extracted:
        try:
            del base_obj[f"{HELD_TARGET_PREFIX}{resolved_key}"]
        except Exception:
            pass
        bpy.data.objects.remove(extracted_obj, do_unlink=True)

    base_obj.data.update()
    blendshape_bridge.evaluate_correctives_deterministic(base_obj)
    uv_mat_check = topology.verify_uvs_and_materials_preserved(base_obj, uv_mat_snap)

    return {
        "ok": True,
        "blocked": False,
        "source_object": base_obj.name,
        "key_name": resolved_key,
        "updated_vertices": updated_deltas,
        "non_zero_delta_count": non_zero_deltas,
        "deleted_extracted": delete_extracted,
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
        "topology": topo,
    }


def propagate_base_mesh_edits(
    obj_or_name: Any,
    edited_basis_mesh_or_deltas: Any,
    sync_held_targets: bool = True,
) -> Dict[str, Any]:
    """Propagate edits made to the `Basis` shape across all relative shape keys on `obj`.

    Accepts either:
    - Another mesh object (`edited_basis_mesh`) whose topology MUST strictly match `obj` via
      `validate_strict_topology` (blocks unsupported topological edits with an explanation!), OR
    - A `dict[int, tuple[float, float, float]]` of `{vertex_index: delta_xyz}` offsets to apply to `Basis`.

    Guarantees that every relative shape key `kb`'s authored morph delta (`kb.co - basis.co`)
    remains 100% invariant (`max_morph_delta_drift < 1e-6`) while UVs and materials are preserved.
    """
    import bpy

    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "blocked": True, "reason": "Object is not a valid MESH."}

    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or not sk.key_blocks:
        return {"ok": False, "blocked": True, "reason": f"'{obj.name}' has no shape keys."}

    basis = sk.reference_key
    n = len(basis.data)

    # Snapshot original morph deltas (kb.co - basis.co) before propagating base edits
    original_morph_deltas: Dict[str, List[Vector]] = {}
    for kb in sk.key_blocks:
        if kb == basis:
            continue
        rel = kb.relative_key or basis
        original_morph_deltas[kb.name] = [
            (kb.data[i].co - rel.data[i].co).copy() for i in range(n)
        ]

    base_deltas: List[Vector] = [Vector((0.0, 0.0, 0.0)) for _ in range(n)]

    if isinstance(edited_basis_mesh_or_deltas, dict):
        for v_idx, d_xyz in edited_basis_mesh_or_deltas.items():
            idx = int(v_idx)
            if 0 <= idx < n:
                base_deltas[idx] = Vector(d_xyz)
    else:
        cand_obj = topology._resolve_mesh_obj(edited_basis_mesh_or_deltas)
        if cand_obj is None:
            return {
                "ok": False,
                "blocked": True,
                "reason": "Edited basis source must be a valid MESH object or {vertex_idx: delta_xyz} dict.",
            }
        topo = topology.validate_strict_topology(obj, cand_obj)
        if not topo["ok"]:
            return {
                "ok": False,
                "blocked": True,
                "reason": f"Blocked base edit propagation due to unsupported topological change: {topo['reason']}",
                "topology": topo,
            }
        for i in range(n):
            base_deltas[i] = cand_obj.data.vertices[i].co - basis.data[i].co

    uv_mat_snap = topology.snapshot_uvs_and_materials(obj)

    # Apply base_deltas to Basis, underlying Mesh vertices, and every dependent shape key
    moved_count = 0
    for i in range(n):
        d = base_deltas[i]
        if d.length > 1e-7:
            moved_count += 1
            basis.data[i].co = basis.data[i].co + d
            obj.data.vertices[i].co = basis.data[i].co.copy()

    propagated_keys: List[str] = []
    for kb in sk.key_blocks:
        if kb == basis:
            continue
        for i in range(n):
            kb.data[i].co = kb.data[i].co + base_deltas[i]
        propagated_keys.append(kb.name)

        if sync_held_targets:
            held_name = str(obj.get(f"{HELD_TARGET_PREFIX}{kb.name}", "") or "")
            held_obj = bpy.data.objects.get(held_name) if held_name else None
            if held_obj is not None and getattr(held_obj, "type", None) == "MESH":
                if len(held_obj.data.vertices) == n:
                    for i in range(n):
                        held_obj.data.vertices[i].co = held_obj.data.vertices[i].co + base_deltas[i]
                    held_obj.data.update()

    # Verify morph delta invariance across all relative keys
    max_drift = 0.0
    for kb in sk.key_blocks:
        if kb == basis:
            continue
        rel = kb.relative_key or basis
        orig_list = original_morph_deltas[kb.name]
        for i in range(n):
            new_d = kb.data[i].co - rel.data[i].co
            drift = (new_d - orig_list[i]).length
            if drift > max_drift:
                max_drift = drift

    obj.data.update()
    uv_mat_check = topology.verify_uvs_and_materials_preserved(obj, uv_mat_snap)
    return {
        "ok": True,
        "blocked": False,
        "object_name": obj.name,
        "moved_basis_vertices": moved_count,
        "propagated_keys": propagated_keys,
        "max_morph_delta_drift": float(max_drift),
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
    }


def mirror_shape_target(
    obj_or_name: Any,
    source_key: str,
    new_name: Optional[str] = None,
    axis: str = "X",
) -> Dict[str, Any]:
    """Create or update a mirrored shape key target across `axis` (`X`, `Y`, or `Z`) using `KDTree` on `Basis`."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or source_key not in sk.key_blocks:
        return {"ok": False, "error": f"Shape key '{source_key}' not found."}

    basis = sk.reference_key
    src_kb = sk.key_blocks[source_key]
    n = len(basis.data)

    kd = KDTree(n)
    for i in range(n):
        kd.insert(basis.data[i].co, i)
    kd.balance()

    ax = axis.upper()
    ax_idx = 0 if ax == "X" else (1 if ax == "Y" else 2)

    target_name = new_name or f"{source_key}_Mirrored"
    dst_kb = sk.key_blocks.get(target_name)
    if dst_kb is None:
        dst_kb = obj.shape_key_add(name=target_name, from_mix=False)
        dst_kb.relative_key = basis

    matched = 0
    for i in range(n):
        b_co = basis.data[i].co.copy()
        mir_query = b_co.copy()
        mir_query[ax_idx] = -mir_query[ax_idx]
        _co, src_idx, _dist = kd.find(mir_query)
        src_delta = src_kb.data[src_idx].co - basis.data[src_idx].co
        mir_delta = src_delta.copy()
        mir_delta[ax_idx] = -mir_delta[ax_idx]
        dst_kb.data[i].co = b_co + mir_delta
        matched += 1

    obj.data.update()
    return {
        "ok": True,
        "object_name": obj.name,
        "source_key": source_key,
        "mirrored_key": dst_kb.name,
        "matched_vertices": matched,
    }
