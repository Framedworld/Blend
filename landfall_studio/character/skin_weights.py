"""Skin Weight Inspection, Locked-Weight Enforcement, Weight Hammer, Prune, Mirror & Controlled Transfer (`landfall_studio.character.skin_weights`).

Guarantees:
1. Locked vertex groups (`vg.lock_weight == True`, Maya `Hold` column) are NEVER silently overwritten
   by direct edits, normalization, pruning, Weight Hammer, mirroring, or weight transfer (`max_locked_weight_drift == 0.0`).
2. `VERTEX_INDEX` weight transfer requires strict topological connectivity (`validate_strict_topology`),
   blocking mismatched topology with a clear explanation.
3. `CLOSEST_SURFACE` weight transfer uses world-space `BVHTree` polygon interpolation and preserves
   target UVs, materials, and locked vertex groups.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from . import topology


def _get_vertex_weights_dict(obj: Any, v_idx: int) -> Dict[int, float]:
    v = obj.data.vertices[v_idx]
    return {int(g.group): float(g.weight) for g in v.groups if g.weight > 1e-8}


def snapshot_locked_weights(obj_or_name: Any) -> Dict[str, Dict[int, float]]:
    """Snapshot `{group_name: {vert_idx: weight}}` for all locked vertex groups (`vg.lock_weight == True`)."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {}
    locked_by_idx = {vg.index: vg.name for vg in obj.vertex_groups if vg.lock_weight}
    if not locked_by_idx:
        return {}
    snap: Dict[str, Dict[int, float]] = {name: {} for name in locked_by_idx.values()}
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group in locked_by_idx:
                snap[locked_by_idx[g.group]][v.index] = float(g.weight)
    return snap


def verify_locked_weights_preserved(
    obj_or_name: Any,
    before_locked_snap: Dict[str, Dict[int, float]],
) -> Dict[str, Any]:
    """Compare current locked vertex group weights against `before_locked_snap`."""
    after_snap = snapshot_locked_weights(obj_or_name)
    max_drift = 0.0
    for gname, before_verts in before_locked_snap.items():
        after_verts = after_snap.get(gname, {})
        all_v = set(before_verts.keys()) | set(after_verts.keys())
        for v_idx in all_v:
            w0 = before_verts.get(v_idx, 0.0)
            w1 = after_verts.get(v_idx, 0.0)
            d = abs(w1 - w0)
            if d > max_drift:
                max_drift = d
    return {
        "locked_weights_preserved": max_drift < 1e-6,
        "max_locked_weight_drift": float(max_drift),
        "locked_groups": sorted(before_locked_snap.keys()),
    }


def inspect_skin_weights(
    obj_or_name: Any,
    max_influences: int = 4,
) -> Dict[str, Any]:
    """Read-only skin weight audit for `obj`: groups, locks, normalization, unweighted verts, and max influences."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    arm_mods = [m for m in getattr(obj, "modifiers", ()) if m.type == "ARMATURE" and getattr(m, "object", None)]
    arm_obj = arm_mods[0].object if arm_mods else (obj.parent if getattr(obj.parent, "type", None) == "ARMATURE" else None)
    bone_names: Set[str] = set()
    if arm_obj is not None and getattr(arm_obj, "data", None) is not None:
        bone_names = {b.name for b in arm_obj.data.bones if getattr(b, "use_deform", True)}

    vgs = list(obj.vertex_groups)
    vg_by_idx = {vg.index: vg for vg in vgs}
    group_totals = {vg.index: 0.0 for vg in vgs}
    group_counts = {vg.index: 0 for vg in vgs}
    group_max = {vg.index: 0.0 for vg in vgs}

    unweighted_verts: List[int] = []
    unnormalized_verts: List[int] = []
    over_limit_verts: List[int] = []

    n_verts = len(obj.data.vertices)
    for v in obj.data.vertices:
        nz = [(g.group, float(g.weight)) for g in v.groups if g.group in vg_by_idx and g.weight > 1e-6]
        if not nz:
            unweighted_verts.append(v.index)
            continue
        tot = sum(w for _, w in nz)
        if abs(tot - 1.0) > 1e-3:
            unnormalized_verts.append(v.index)
        if len(nz) > max_influences:
            over_limit_verts.append(v.index)
        for g_idx, w in nz:
            group_totals[g_idx] += w
            group_counts[g_idx] += 1
            if w > group_max[g_idx]:
                group_max[g_idx] = w

    group_rows: List[Dict[str, Any]] = []
    for vg in vgs:
        cnt = group_counts[vg.index]
        avg_w = (group_totals[vg.index] / n_verts) if n_verts > 0 else 0.0
        group_rows.append(
            {
                "index": vg.index,
                "name": vg.name,
                "locked": bool(vg.lock_weight),
                "is_deform_bone": (vg.name in bone_names) if bone_names else True,
                "vertex_count": cnt,
                "average_weight": round(float(avg_w), 4),
                "max_weight": round(float(group_max[vg.index]), 4),
            }
        )

    return {
        "ok": True,
        "object_name": obj.name,
        "armature_name": arm_obj.name if arm_obj is not None else "",
        "vertex_count": n_verts,
        "group_count": len(vgs),
        "locked_groups": [vg.name for vg in vgs if vg.lock_weight],
        "unweighted_vertex_count": len(unweighted_verts),
        "unnormalized_vertex_count": len(unnormalized_verts),
        "over_limit_vertex_count": len(over_limit_verts),
        "max_influences_limit": max_influences,
        "groups": group_rows,
    }


def set_vertex_group_lock(
    obj_or_name: Any,
    group_name: str,
    locked: bool = True,
) -> Dict[str, Any]:
    """Set or toggle Maya-style `Hold` (`lock_weight`) on a vertex group."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}
    vg = obj.vertex_groups.get(group_name)
    if vg is None:
        return {"ok": False, "error": f"Vertex group '{group_name}' not found on '{obj.name}'."}
    vg.lock_weight = bool(locked)
    return {
        "ok": True,
        "object_name": obj.name,
        "group_name": vg.name,
        "locked": bool(vg.lock_weight),
    }


_NON_SKIN_GROUP_KEYWORDS = (
    "_mask",
    "mask_",
    "_pin",
    "pin_",
    "cloth_pin",
    "hair_mask",
    "_selection",
    "selection_",
)


def _get_skin_deform_group_indices(obj: Any) -> Set[int]:
    """Return vertex group indices that represent skin deform influences (excluding mask/pin/modifier groups)."""
    vgs = list(getattr(obj, "vertex_groups", ()))
    if not vgs:
        return set()

    arm_mods = [m for m in getattr(obj, "modifiers", ()) if m.type == "ARMATURE" and getattr(m, "object", None)]
    arm_obj = arm_mods[0].object if arm_mods else (obj.parent if getattr(getattr(obj, "parent", None), "type", None) == "ARMATURE" else None)
    bone_names: Set[str] = set()
    if arm_obj is not None and getattr(arm_obj, "data", None) is not None:
        bone_names = {b.name for b in arm_obj.data.bones if getattr(b, "use_deform", True)}

    # Collect vertex groups explicitly referenced by non-armature modifiers (Mask, Cloth pin, etc.)
    non_skin_mod_groups: Set[str] = set()
    for m in getattr(obj, "modifiers", ()):
        if m.type == "ARMATURE":
            continue
        vg_attr = getattr(m, "vertex_group", "")
        if vg_attr:
            non_skin_mod_groups.add(vg_attr)
        settings = getattr(m, "settings", None)
        if settings is not None:
            for attr in ("vertex_group_mass", "vertex_group_structural_stiffness", "vertex_group_bending", "vertex_group_shrink"):
                val = getattr(settings, attr, "")
                if val:
                    non_skin_mod_groups.add(val)

    if bone_names:
        matched = {vg.index for vg in vgs if vg.name in bone_names and vg.name not in non_skin_mod_groups}
        if matched:
            return matched

    skin_indices: Set[int] = set()
    for vg in vgs:
        low = vg.name.lower()
        if vg.name in non_skin_mod_groups:
            continue
        if low in ("mask", "pin", "cloth", "hair", "selection") or any(kw in low for kw in _NON_SKIN_GROUP_KEYWORDS):
            continue
        skin_indices.add(vg.index)
    return skin_indices


def _normalize_single_vertex(
    obj: Any,
    v_idx: int,
    respect_locks: bool = True,
    pinned_group_idx: Optional[int] = None,
    skin_indices: Optional[Set[int]] = None,
) -> None:
    """Normalize skin deform weights on vertex `v_idx` so total skin weight == 1.0 without altering locked or non-skin groups."""
    v = obj.data.vertices[v_idx]
    vgs = obj.vertex_groups
    if skin_indices is None:
        skin_indices = _get_skin_deform_group_indices(obj)
    locked_indices = {vg.index for vg in vgs if vg.lock_weight and vg.index in skin_indices} if respect_locks else set()
    if pinned_group_idx is not None and pinned_group_idx in skin_indices:
        locked_indices = set(locked_indices) | {pinned_group_idx}

    weights = {
        int(g.group): float(g.weight)
        for g in v.groups
        if int(g.group) < len(vgs) and int(g.group) in skin_indices
    }
    if not weights:
        return

    locked_sum = sum(w for g_idx, w in weights.items() if g_idx in locked_indices)
    unlocked_items = [(g_idx, w) for g_idx, w in weights.items() if g_idx not in locked_indices]

    if not unlocked_items:
        return

    budget = max(0.0, 1.0 - locked_sum)
    unlocked_sum = sum(w for _, w in unlocked_items)

    if budget <= 1e-8:
        for g_idx, _ in unlocked_items:
            vgs[g_idx].add([v_idx], 0.0, "REPLACE")
        return

    if unlocked_sum > 1e-8:
        scale = budget / unlocked_sum
        for g_idx, w in unlocked_items:
            vgs[g_idx].add([v_idx], float(w * scale), "REPLACE")
    else:
        share = budget / len(unlocked_items)
        for g_idx, _ in unlocked_items:
            vgs[g_idx].add([v_idx], float(share), "REPLACE")


def set_vertex_weight_respecting_locks(
    obj_or_name: Any,
    vertex_index: int,
    group_name: str,
    weight: float,
    normalize: bool = True,
) -> Dict[str, Any]:
    """Set `weight` on `(vertex_index, group_name)` while blocking edits to locked groups and preserving locked peers."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "blocked": True, "reason": "Object is not a valid MESH."}

    vg = obj.vertex_groups.get(group_name)
    if vg is None:
        return {"ok": False, "blocked": True, "reason": f"Vertex group '{group_name}' not found."}

    if vg.lock_weight:
        return {
            "ok": False,
            "blocked": True,
            "object_name": obj.name,
            "group_name": group_name,
            "reason": f"Blocked weight edit: vertex group '{group_name}' is locked (Hold Weight active).",
        }

    v_idx = int(vertex_index)
    if not (0 <= v_idx < len(obj.data.vertices)):
        return {"ok": False, "blocked": True, "reason": f"Vertex index {v_idx} out of range."}

    locked_snap = snapshot_locked_weights(obj)
    skin_indices = _get_skin_deform_group_indices(obj)

    v = obj.data.vertices[v_idx]
    locked_indices = {g.index for g in obj.vertex_groups if g.lock_weight and g.index in skin_indices}
    locked_sum = sum(float(g.weight) for g in v.groups if g.group in locked_indices)

    max_allowed = max(0.0, 1.0 - locked_sum) if (normalize and vg.index in skin_indices) else 1.0
    clamped = max(0.0, min(max_allowed, float(weight)))
    vg.add([v_idx], clamped, "REPLACE")

    if normalize and vg.index in skin_indices:
        _normalize_single_vertex(obj, v_idx, respect_locks=True, pinned_group_idx=vg.index, skin_indices=skin_indices)

    lock_check = verify_locked_weights_preserved(obj, locked_snap)
    return {
        "ok": True,
        "blocked": False,
        "object_name": obj.name,
        "vertex_index": v_idx,
        "group_name": group_name,
        "applied_weight": round(clamped, 6),
        **lock_check,
    }


def normalize_skin_weights(
    obj_or_name: Any,
    respect_locks: bool = True,
) -> Dict[str, Any]:
    """Normalize all vertex skin weights on `obj` while strictly preserving locked and non-skin vertex groups."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    uv_mat_snap = topology.snapshot_uvs_and_materials(obj)
    locked_snap = snapshot_locked_weights(obj)
    skin_indices = _get_skin_deform_group_indices(obj)

    n_verts = len(obj.data.vertices)
    for v_idx in range(n_verts):
        _normalize_single_vertex(obj, v_idx, respect_locks=respect_locks, skin_indices=skin_indices)

    obj.data.update()
    lock_check = verify_locked_weights_preserved(obj, locked_snap)
    uv_mat_check = topology.verify_uvs_and_materials_preserved(obj, uv_mat_snap)
    return {
        "ok": True,
        "object_name": obj.name,
        "normalized_vertices": n_verts,
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
        **lock_check,
    }


def prune_small_weights(
    obj_or_name: Any,
    threshold: float = 0.01,
    max_influences: int = 4,
    respect_locks: bool = True,
    normalize: bool = True,
) -> Dict[str, Any]:
    """Prune unlocked skin deform weights below `threshold` and cap per-vertex skin influences to `max_influences`."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    uv_mat_snap = topology.snapshot_uvs_and_materials(obj)
    locked_snap = snapshot_locked_weights(obj)
    vgs = obj.vertex_groups
    skin_indices = _get_skin_deform_group_indices(obj)
    locked_indices = {vg.index for vg in vgs if vg.lock_weight and vg.index in skin_indices} if respect_locks else set()

    pruned_entries = 0
    for v in obj.data.vertices:
        v_idx = v.index
        entries = [
            (int(g.group), float(g.weight))
            for g in v.groups
            if int(g.group) < len(vgs) and int(g.group) in skin_indices
        ]
        if not entries:
            continue

        locked_entries = [(gi, w) for gi, w in entries if gi in locked_indices]
        unlocked_entries = [(gi, w) for gi, w in entries if gi not in locked_indices]

        # 1. Remove unlocked entries below threshold
        kept_unlocked = []
        for gi, w in unlocked_entries:
            if w < threshold:
                vgs[gi].remove([v_idx])
                pruned_entries += 1
            else:
                kept_unlocked.append((gi, w))

        # 2. Cap total influences to max_influences (only dropping smallest unlocked entries)
        allowed_unlocked = max(0, int(max_influences) - len(locked_entries))
        if len(kept_unlocked) > allowed_unlocked:
            kept_unlocked.sort(key=lambda pair: pair[1], reverse=True)
            to_drop = kept_unlocked[allowed_unlocked:]
            kept_unlocked = kept_unlocked[:allowed_unlocked]
            for gi, _ in to_drop:
                vgs[gi].remove([v_idx])
                pruned_entries += 1

        if normalize:
            _normalize_single_vertex(obj, v_idx, respect_locks=respect_locks, skin_indices=skin_indices)

    obj.data.update()
    lock_check = verify_locked_weights_preserved(obj, locked_snap)
    uv_mat_check = topology.verify_uvs_and_materials_preserved(obj, uv_mat_snap)
    return {
        "ok": True,
        "object_name": obj.name,
        "pruned_entries": pruned_entries,
        "threshold": threshold,
        "max_influences": max_influences,
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
        **lock_check,
    }


def weight_hammer_vertices(
    obj_or_name: Any,
    vertex_indices: Optional[Sequence[int]] = None,
    respect_locks: bool = True,
    normalize: bool = True,
) -> Dict[str, Any]:
    """Maya `Weight Hammer`: set target vertices' unlocked skin weights to the average of their 1-ring neighbors."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    mesh = obj.data
    n_verts = len(mesh.vertices)
    if vertex_indices is None:
        sel = [v.index for v in mesh.vertices if v.select]
        targets = sel if sel else list(range(n_verts))
    else:
        targets = [int(i) for i in vertex_indices if 0 <= int(i) < n_verts]

    # Build 1-ring adjacency
    adj: Dict[int, List[int]] = {i: [] for i in range(n_verts)}
    for e in mesh.edges:
        v0, v1 = int(e.vertices[0]), int(e.vertices[1])
        adj[v0].append(v1)
        adj[v1].append(v0)

    # Snapshot all current weights before hammering
    all_weights = [_get_vertex_weights_dict(obj, i) for i in range(n_verts)]
    uv_mat_snap = topology.snapshot_uvs_and_materials(obj)
    locked_snap = snapshot_locked_weights(obj)

    vgs = obj.vertex_groups
    skin_indices = _get_skin_deform_group_indices(obj)
    locked_indices = {vg.index for vg in vgs if vg.lock_weight and vg.index in skin_indices} if respect_locks else set()
    unlocked_indices = [vg.index for vg in vgs if vg.index in skin_indices and vg.index not in locked_indices]

    for v_idx in targets:
        nbrs = adj.get(v_idx, [])
        if not nbrs:
            continue
        for gi in unlocked_indices:
            avg_w = sum(all_weights[nb].get(gi, 0.0) for nb in nbrs) / len(nbrs)
            if avg_w > 1e-6:
                vgs[gi].add([v_idx], float(avg_w), "REPLACE")
            else:
                try:
                    vgs[gi].remove([v_idx])
                except Exception:
                    pass
        if normalize:
            _normalize_single_vertex(obj, v_idx, respect_locks=respect_locks, skin_indices=skin_indices)

    mesh.update()
    lock_check = verify_locked_weights_preserved(obj, locked_snap)
    uv_mat_check = topology.verify_uvs_and_materials_preserved(obj, uv_mat_snap)
    return {
        "ok": True,
        "object_name": obj.name,
        "hammered_vertex_count": len(targets),
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
        **lock_check,
    }


def _resolve_mirror_group_name(name: str) -> str:
    pairs = (("_L", "_R"), (".L", ".R"), ("_l", "_r"), ("Left", "Right"), ("left", "right"))
    for left, right in pairs:
        if name.endswith(left):
            return name[: -len(left)] + right
        if name.endswith(right):
            return name[: -len(right)] + left
        if name.startswith(left):
            return right + name[len(left) :]
        if name.startswith(right):
            return left + name[len(right) :]
    return name


def mirror_skin_weights(
    obj_or_name: Any,
    direction: str = "PLUS_TO_MINUS",
    axis: str = "X",
    respect_locks: bool = True,
    normalize: bool = True,
) -> Dict[str, Any]:
    """Mirror skin weights across `axis` (`PLUS_TO_MINUS` or `MINUS_TO_PLUS`) while respecting locked and non-skin groups."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    mesh = obj.data
    n_verts = len(mesh.vertices)
    kd = KDTree(n_verts)
    for v in mesh.vertices:
        kd.insert(v.co, v.index)
    kd.balance()

    ax = axis.upper()
    ax_idx = 0 if ax == "X" else (1 if ax == "Y" else 2)
    plus_to_minus = direction.upper() != "MINUS_TO_PLUS"

    all_weights = [_get_vertex_weights_dict(obj, i) for i in range(n_verts)]
    uv_mat_snap = topology.snapshot_uvs_and_materials(obj)
    locked_snap = snapshot_locked_weights(obj)

    vgs = obj.vertex_groups
    skin_indices = _get_skin_deform_group_indices(obj)
    locked_indices = {vg.index for vg in vgs if vg.lock_weight and vg.index in skin_indices} if respect_locks else set()

    # Map each skin group index to its mirrored group index (creating target group if needed)
    mirror_group_map: Dict[int, int] = {}
    for vg in list(vgs):
        if vg.index not in skin_indices:
            continue
        mir_name = _resolve_mirror_group_name(vg.name)
        mir_vg = vgs.get(mir_name)
        if mir_vg is None:
            mir_vg = vgs.new(name=mir_name)
        skin_indices.add(mir_vg.index)
        mirror_group_map[vg.index] = mir_vg.index

    mirrored_verts = 0
    for v in mesh.vertices:
        coord_val = float(v.co[ax_idx])
        is_target_side = (coord_val < -1e-5) if plus_to_minus else (coord_val > 1e-5)
        if not is_target_side:
            continue

        query = v.co.copy()
        query[ax_idx] = -query[ax_idx]
        _co, src_v_idx, _dist = kd.find(query)
        src_weights = all_weights[src_v_idx]

        # Clear unlocked skin weights on target vertex first (leaving non-skin mask/pin groups untouched)
        for vg in vgs:
            if vg.index in skin_indices and vg.index not in locked_indices:
                try:
                    vg.remove([v.index])
                except Exception:
                    pass

        for src_gi, w in src_weights.items():
            if src_gi not in skin_indices:
                continue
            dst_gi = mirror_group_map.get(src_gi, src_gi)
            if dst_gi in locked_indices:
                continue
            vgs[dst_gi].add([v.index], float(w), "REPLACE")

        if normalize:
            _normalize_single_vertex(obj, v.index, respect_locks=respect_locks, skin_indices=skin_indices)
        mirrored_verts += 1

    mesh.update()
    lock_check = verify_locked_weights_preserved(obj, locked_snap)
    uv_mat_check = topology.verify_uvs_and_materials_preserved(obj, uv_mat_snap)
    return {
        "ok": True,
        "object_name": obj.name,
        "mirrored_vertices": mirrored_verts,
        "direction": direction,
        "axis": ax,
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
        **lock_check,
    }


def controlled_weight_transfer(
    source_obj_or_name: Any,
    target_obj_or_name: Any,
    method: str = "CLOSEST_SURFACE",
    group_names: Optional[Sequence[str]] = None,
    respect_target_locks: bool = True,
    normalize: bool = True,
) -> Dict[str, Any]:
    """Transfer skin weights from `source_obj` to `target_obj` while respecting locked target groups and UVs/materials.

    Methods:
    - `"VERTEX_INDEX"`: requires strict topological connectivity (`validate_strict_topology`). Blocks if mismatched!
    - `"CLOSEST_SURFACE"`: uses world-space `BVHTree` closest surface point + inverse-distance polygon vertex
      interpolation on `source_obj` to transfer weights onto arbitrary topology `target_obj`.
    """
    src_obj = topology._resolve_mesh_obj(source_obj_or_name)
    dst_obj = topology._resolve_mesh_obj(target_obj_or_name)
    if src_obj is None or dst_obj is None:
        return {"ok": False, "blocked": True, "reason": "Both source and target must be valid MESH objects."}

    mode = method.upper().strip()
    if mode == "VERTEX_INDEX":
        topo = topology.validate_strict_topology(src_obj, dst_obj)
        if not topo["ok"]:
            return {
                "ok": False,
                "blocked": True,
                "method": mode,
                "reason": f"Blocked VERTEX_INDEX weight transfer due to topological mismatch: {topo['reason']}",
                "topology": topo,
            }

    uv_mat_snap = topology.snapshot_uvs_and_materials(dst_obj)
    locked_snap = snapshot_locked_weights(dst_obj)

    src_vgs = list(src_obj.vertex_groups)
    if group_names is not None:
        allowed_names = set(group_names)
        src_vgs = [vg for vg in src_vgs if vg.name in allowed_names]

    # Ensure unlocked target vertex groups exist on dst_obj
    dst_locked_names = {vg.name for vg in dst_obj.vertex_groups if vg.lock_weight} if respect_target_locks else set()
    transfer_groups: List[Tuple[int, Any]] = []
    for svg in src_vgs:
        if svg.name in dst_locked_names:
            continue
        dvg = dst_obj.vertex_groups.get(svg.name)
        if dvg is None:
            dvg = dst_obj.vertex_groups.new(name=svg.name)
        transfer_groups.append((svg.index, dvg))

    src_all_weights = [_get_vertex_weights_dict(src_obj, i) for i in range(len(src_obj.data.vertices))]
    n_dst = len(dst_obj.data.vertices)

    if mode == "VERTEX_INDEX":
        for v_idx in range(n_dst):
            sw = src_all_weights[v_idx]
            for s_gi, dvg in transfer_groups:
                w = sw.get(s_gi, 0.0)
                if w > 1e-6:
                    dvg.add([v_idx], float(w), "REPLACE")
                else:
                    try:
                        dvg.remove([v_idx])
                    except Exception:
                        pass
            if normalize:
                _normalize_single_vertex(dst_obj, v_idx, respect_locks=respect_target_locks)
    else:
        # World-space BVHTree on source_obj
        src_mw = src_obj.matrix_world
        dst_mw = dst_obj.matrix_world
        src_world_verts = [src_mw @ v.co for v in src_obj.data.vertices]
        src_polys = [tuple(p.vertices) for p in src_obj.data.polygons]

        bvh = BVHTree.FromPolygons(src_world_verts, src_polys) if src_polys else None
        for v_idx, dv in enumerate(dst_obj.data.vertices):
            p_world = dst_mw @ dv.co
            interp_weights: Dict[int, float] = {}
            if bvh is not None:
                hit_loc, _hit_norm, hit_poly_idx, _hit_dist = bvh.find_nearest(p_world)
                if hit_loc is not None and hit_poly_idx is not None and 0 <= hit_poly_idx < len(src_polys):
                    poly_v_indices = src_polys[hit_poly_idx]
                    inv_dists: List[Tuple[int, float]] = []
                    for sv_i in poly_v_indices:
                        d = (src_world_verts[sv_i] - hit_loc).length
                        if d < 1e-6:
                            inv_dists = [(sv_i, 1.0)]
                            break
                        inv_dists.append((sv_i, 1.0 / d))
                    tot_inv = sum(val for _, val in inv_dists) or 1.0
                    for sv_i, val in inv_dists:
                        factor = val / tot_inv
                        for s_gi, w in src_all_weights[sv_i].items():
                            interp_weights[s_gi] = interp_weights.get(s_gi, 0.0) + factor * w

            for s_gi, dvg in transfer_groups:
                w = interp_weights.get(s_gi, 0.0)
                if w > 1e-6:
                    dvg.add([v_idx], float(w), "REPLACE")
                else:
                    try:
                        dvg.remove([v_idx])
                    except Exception:
                        pass
            if normalize:
                _normalize_single_vertex(dst_obj, v_idx, respect_locks=respect_target_locks)

    dst_obj.data.update()
    lock_check = verify_locked_weights_preserved(dst_obj, locked_snap)
    uv_mat_check = topology.verify_uvs_and_materials_preserved(dst_obj, uv_mat_snap)
    return {
        "ok": True,
        "blocked": False,
        "source_object": src_obj.name,
        "target_object": dst_obj.name,
        "method": mode,
        "transferred_group_count": len(transfer_groups),
        "skipped_locked_target_groups": sorted(dst_locked_names),
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
        **lock_check,
    }
