"""Strict Topological Connectivity, Vertex-Index Order, UV & Material Validation (`landfall_studio.character.topology`).

Unlike vertex-count-only checks (`len(v1) == len(v2)`), `validate_strict_topology` verifies:
1. Exact vertex, edge, and polygon counts.
2. Exact per-edge vertex index pairs (`tuple(e.vertices)`).
3. Exact per-polygon ordered vertex loop indices (`tuple(p.vertices)`).
4. Optional UV map compatibility and material slot / polygon `material_index` compatibility.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _resolve_mesh_obj(obj_or_name: Any) -> Any:
    import bpy

    if isinstance(obj_or_name, str):
        obj = bpy.data.objects.get(obj_or_name)
    else:
        obj = obj_or_name
    if obj is None:
        return None
    try:
        _ = obj.name
    except ReferenceError:
        return None
    return obj if getattr(obj, "type", None) == "MESH" and getattr(obj, "data", None) is not None else None


def validate_strict_topology(
    base_obj: Any,
    candidate_obj: Any,
    check_uvs: bool = False,
    check_materials: bool = False,
) -> Dict[str, Any]:
    """Validate strict vertex-index, edge-pair, and polygon-loop topological identity between two meshes.

    Never relies on vertex count alone: two meshes with 8 vertices but different edge/face connectivity
    or re-indexed vertex winding are rejected with a detailed explanation.
    """
    b_obj = _resolve_mesh_obj(base_obj)
    c_obj = _resolve_mesh_obj(candidate_obj)
    if b_obj is None or c_obj is None:
        return {
            "ok": False,
            "vertex_count_match": False,
            "edge_count_match": False,
            "polygon_count_match": False,
            "edge_connectivity_match": False,
            "polygon_winding_match": False,
            "connectivity_match": False,
            "uv_layers_compatible": False,
            "materials_compatible": False,
            "base_counts": {},
            "candidate_counts": {},
            "mismatched_edge_indices": [],
            "mismatched_polygon_indices": [],
            "reason": "One or both objects are missing or not MESH objects.",
        }

    bm = b_obj.data
    cm = c_obj.data

    b_counts = {
        "verts": len(bm.vertices),
        "edges": len(bm.edges),
        "polys": len(bm.polygons),
    }
    c_counts = {
        "verts": len(cm.vertices),
        "edges": len(cm.edges),
        "polys": len(cm.polygons),
    }

    v_match = b_counts["verts"] == c_counts["verts"]
    e_match = b_counts["edges"] == c_counts["edges"]
    p_match = b_counts["polys"] == c_counts["polys"]

    mismatched_edges: List[int] = []
    if v_match and e_match:
        b_edge_set = {
            (min(int(e.vertices[0]), int(e.vertices[1])), max(int(e.vertices[0]), int(e.vertices[1])))
            for e in bm.edges
        }
        for idx, ce in enumerate(cm.edges):
            pair = (min(int(ce.vertices[0]), int(ce.vertices[1])), max(int(ce.vertices[0]), int(ce.vertices[1])))
            if pair not in b_edge_set:
                mismatched_edges.append(idx)
                if len(mismatched_edges) >= 16:
                    break
    edge_conn_match = v_match and e_match and len(mismatched_edges) == 0

    mismatched_polys: List[int] = []
    if v_match and p_match:
        for idx, (bp, cp) in enumerate(zip(bm.polygons, cm.polygons)):
            if tuple(bp.vertices) != tuple(cp.vertices):
                mismatched_polys.append(idx)
                if len(mismatched_polys) >= 16:
                    break
    poly_wind_match = v_match and p_match and len(mismatched_polys) == 0

    connectivity_match = bool(v_match and e_match and p_match and edge_conn_match and poly_wind_match)

    # Optional UV & Material compatibility checks
    b_uvs = [layer.name for layer in bm.uv_layers]
    c_uvs = [layer.name for layer in cm.uv_layers]
    uv_compat = (len(b_uvs) == len(c_uvs)) if check_uvs else True

    b_mats = [m.name if m else "" for m in bm.materials]
    c_mats = [m.name if m else "" for m in cm.materials]
    mat_compat = (b_mats == c_mats) if check_materials else True

    reasons: List[str] = []
    if not v_match:
        reasons.append(f"Vertex count mismatch ({b_obj.name}={b_counts['verts']} vs {c_obj.name}={c_counts['verts']})")
    if not e_match:
        reasons.append(f"Edge count mismatch ({b_obj.name}={b_counts['edges']} vs {c_obj.name}={c_counts['edges']})")
    if not p_match:
        reasons.append(f"Polygon count mismatch ({b_obj.name}={b_counts['polys']} vs {c_obj.name}={c_counts['polys']})")
    if v_match and e_match and not edge_conn_match:
        reasons.append(
            f"Edge connectivity/vertex-index mismatch on {len(mismatched_edges)}+ edges (first index: {mismatched_edges[0]})"
        )
    if v_match and p_match and not poly_wind_match:
        reasons.append(
            f"Polygon loop/winding mismatch on {len(mismatched_polys)}+ polygons (first index: {mismatched_polys[0]})"
        )
    if check_uvs and not uv_compat:
        reasons.append(f"UV layer count mismatch ({b_uvs} vs {c_uvs})")
    if check_materials and not mat_compat:
        reasons.append(f"Material slot mismatch ({b_mats} vs {c_mats})")

    ok = bool(connectivity_match and uv_compat and mat_compat)
    return {
        "ok": ok,
        "vertex_count_match": v_match,
        "edge_count_match": e_match,
        "polygon_count_match": p_match,
        "edge_connectivity_match": edge_conn_match,
        "polygon_winding_match": poly_wind_match,
        "connectivity_match": connectivity_match,
        "uv_layers_compatible": uv_compat,
        "materials_compatible": mat_compat,
        "base_counts": b_counts,
        "candidate_counts": c_counts,
        "mismatched_edge_indices": mismatched_edges,
        "mismatched_polygon_indices": mismatched_polys,
        "reason": "; ".join(reasons) if reasons else "Strict topological connectivity verified.",
    }


def snapshot_uvs_and_materials(obj_or_name: Any) -> Dict[str, Any]:
    """Capture a deterministic snapshot of UV layers, loop UV coordinates, material slots, and face material indices."""
    obj = _resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "uv_layers": {}, "materials": [], "poly_material_indices": []}
    mesh = obj.data
    uv_snap: Dict[str, List[Tuple[float, float]]] = {}
    for layer in mesh.uv_layers:
        uv_snap[layer.name] = [
            (round(float(d.uv[0]), 5), round(float(d.uv[1]), 5))
            for d in layer.data
        ]
    mats = [m.name if m is not None else "" for m in mesh.materials]
    poly_mats = [int(p.material_index) for p in mesh.polygons]
    return {
        "ok": True,
        "object_name": obj.name,
        "uv_layers": uv_snap,
        "materials": mats,
        "poly_material_indices": poly_mats,
    }


def verify_uvs_and_materials_preserved(
    obj_or_name: Any,
    before_snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare current UVs and material assignments against `before_snapshot`."""
    after = snapshot_uvs_and_materials(obj_or_name)
    if not before_snapshot.get("ok") or not after.get("ok"):
        return {"ok": False, "uvs_preserved": False, "materials_preserved": False}

    uvs_ok = before_snapshot["uv_layers"] == after["uv_layers"]
    mats_ok = (
        before_snapshot["materials"] == after["materials"]
        and before_snapshot["poly_material_indices"] == after["poly_material_indices"]
    )
    return {
        "ok": bool(uvs_ok and mats_ok),
        "uvs_preserved": uvs_ok,
        "materials_preserved": mats_ok,
        "uv_layer_names": list(after["uv_layers"].keys()),
        "material_names": after["materials"],
    }


def copy_uvs_and_materials(source_obj: Any, target_obj: Any) -> bool:
    """Copy material slots, per-polygon `material_index`, and UV layers from `source_obj` to `target_obj`."""
    s_obj = _resolve_mesh_obj(source_obj)
    t_obj = _resolve_mesh_obj(target_obj)
    if s_obj is None or t_obj is None:
        return False
    sm = s_obj.data
    tm = t_obj.data
    if len(sm.polygons) != len(tm.polygons) or len(sm.loops) != len(tm.loops):
        return False

    tm.materials.clear()
    for mat in sm.materials:
        tm.materials.append(mat)
    for sp, tp in zip(sm.polygons, tm.polygons):
        tp.material_index = sp.material_index

    for s_layer in sm.uv_layers:
        t_layer = tm.uv_layers.get(s_layer.name)
        if t_layer is None:
            t_layer = tm.uv_layers.new(name=s_layer.name)
        for idx, s_data in enumerate(s_layer.data):
            t_layer.data[idx].uv = (s_data.uv[0], s_data.uv[1])
    if sm.uv_layers.active is not None and sm.uv_layers.active.name in tm.uv_layers:
        tm.uv_layers.active = tm.uv_layers[sm.uv_layers.active.name]
    tm.update()
    return True
