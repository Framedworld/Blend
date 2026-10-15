"""Non-Destructive Skin Weight Layers Proof (`landfall_studio.advanced.weight_layers`).

Provides a Maya / ngSkinTools-inspired layered skin weight stack on top of Blender's
`obj.vertex_groups` while strictly honoring `vg.lock_weight` (`landfall_studio.character.skin_weights`):
- `ensure_base_weight_layer(obj)`: Snapshots current `vertex_groups` weights into the `BaseWeights`
  layer stored in `obj.data["_lf_weight_layers_json"]`.
- `list_weight_layers(obj)`: Lists `BaseWeights` plus all non-destructive override/additive layers
  (`name`, `mode` [`OVERRIDE` / `ADD`], `weight` `0.0..1.0`, `enabled`, `affected_vertices`).
- `create_weight_layer(obj, name="WeightLayer1", mode="OVERRIDE", weight=1.0)`
- `set_layer_vertex_weights(obj, layer_name, group_name, vertex_weights_map)`: Authors sparse
  vertex weights (`{vert_idx: weight_float}`) onto `layer_name` and re-evaluates the composite stack.
- `set_weight_layer_state(obj, layer_name, *, weight=None, enabled=None, mode=None)`
- `evaluate_weight_layers(obj)`: Composites `BaseWeights` + enabled layers in order, strictly skips
  locked vertex groups (`vg.lock_weight == True`), normalizes unlocked influences so every vertex
  sums to `1.0`, and writes the result to `obj.vertex_groups`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional

WEIGHT_LAYERS_PROP = "_lf_weight_layers_json"


def _resolve_mesh_obj(obj: Any = None) -> Optional[Any]:
    import bpy

    if obj is None:
        target = getattr(bpy.context.view_layer.objects, "active", None)
    elif isinstance(obj, str):
        target = bpy.data.objects.get(obj)
    else:
        target = obj
    if target is None or getattr(target, "type", None) != "MESH" or getattr(target, "data", None) is None:
        return None
    return target


def _snapshot_current_vertex_groups(obj: Any) -> Dict[str, Dict[str, float]]:
    """Return `{group_name: {str(v_idx): weight}}` for all vertex groups on `obj`."""
    idx_to_name = {vg.index: vg.name for vg in obj.vertex_groups}
    snap: Dict[str, Dict[str, float]] = {vg.name: {} for vg in obj.vertex_groups}
    for v in obj.data.vertices:
        for g_elem in v.groups:
            gname = idx_to_name.get(g_elem.group)
            if gname is not None and g_elem.weight > 1e-6:
                snap[gname][str(v.index)] = round(float(g_elem.weight), 6)
    return snap


def _load_stack(obj: Any) -> List[Dict[str, Any]]:
    raw = obj.data.get(WEIGHT_LAYERS_PROP)
    if raw:
        try:
            data = json.loads(str(raw))
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            pass
    base_weights = _snapshot_current_vertex_groups(obj)
    stack = [
        {
            "name": "BaseWeights",
            "is_base": True,
            "mode": "BASE",
            "weight": 1.0,
            "enabled": True,
            "weights": base_weights,
        }
    ]
    obj.data[WEIGHT_LAYERS_PROP] = json.dumps(stack)
    return stack


def _save_stack(obj: Any, stack: List[Dict[str, Any]]) -> None:
    obj.data[WEIGHT_LAYERS_PROP] = json.dumps(stack)


def ensure_base_weight_layer(obj: Any = None, *, resnapshot_base: bool = False) -> Dict[str, Any]:
    """Ensure `obj.data` has an initialized `BaseWeights` layer stack."""
    target = _resolve_mesh_obj(obj)
    if target is None:
        return {"ok": False, "error": "Target is not a valid MESH object"}
    stack = _load_stack(target)
    if resnapshot_base and stack:
        stack[0]["weights"] = _snapshot_current_vertex_groups(target)
        _save_stack(target, stack)
    return {
        "ok": True,
        "object": target.name,
        "layer_count": len(stack),
    }


def list_weight_layers(obj: Any = None) -> List[Dict[str, Any]]:
    """Return summary metadata for all weight layers on `obj`."""
    target = _resolve_mesh_obj(obj)
    if target is None:
        return []
    stack = _load_stack(target)
    out: List[Dict[str, Any]] = []
    for entry in stack:
        w_map = entry.get("weights", {}) or {}
        verts = set()
        for g_dict in w_map.values():
            verts.update(g_dict.keys())
        out.append(
            {
                "name": entry.get("name", "Layer"),
                "is_base": bool(entry.get("is_base", False)),
                "mode": entry.get("mode", "OVERRIDE"),
                "weight": round(float(entry.get("weight", 1.0)), 4),
                "enabled": bool(entry.get("enabled", True)),
                "affected_vertices": len(verts),
                "groups": sorted(w_map.keys()),
            }
        )
    return out


def create_weight_layer(
    obj: Any = None,
    name: str = "WeightLayer1",
    *,
    mode: str = "OVERRIDE",
    weight: float = 1.0,
) -> Dict[str, Any]:
    """Create a new non-destructive skin weight layer (`OVERRIDE` or `ADD`) above `BaseWeights`."""
    target = _resolve_mesh_obj(obj)
    if target is None:
        return {"ok": False, "error": "Target is not a valid MESH object"}
    stack = _load_stack(target)
    existing = {e["name"] for e in stack}
    final_name = str(name or "WeightLayer1").strip()
    idx = 1
    while final_name in existing:
        idx += 1
        final_name = f"WeightLayer{idx}"

    m_up = "ADD" if str(mode or "OVERRIDE").upper() == "ADD" else "OVERRIDE"
    stack.append(
        {
            "name": final_name,
            "is_base": False,
            "mode": m_up,
            "weight": max(0.0, min(1.0, float(weight))),
            "enabled": True,
            "weights": {},
        }
    )
    _save_stack(target, stack)
    return {
        "ok": True,
        "object": target.name,
        "layer": final_name,
        "mode": m_up,
        "weight": round(float(weight), 4),
        "layers": list_weight_layers(target),
    }


def set_layer_vertex_weights(
    obj: Any,
    layer_name: str,
    group_name: str,
    vertex_weights: Mapping[int, float],
    *,
    evaluate: bool = True,
) -> Dict[str, Any]:
    """Author sparse `{vertex_index: weight}` on `layer_name` for `group_name` (blocks locked groups)."""
    target = _resolve_mesh_obj(obj)
    if target is None:
        return {"ok": False, "error": "Target is not a valid MESH object"}

    vg = target.vertex_groups.get(str(group_name))
    if vg is None:
        return {"ok": False, "error": f"Vertex group '{group_name}' not found on {target.name}"}
    if vg.lock_weight:
        return {
            "ok": False,
            "status": "BLOCKED",
            "error": f"Vertex group '{group_name}' is locked (lock_weight=True); cannot author layer weights",
        }

    stack = _load_stack(target)
    layer = next((e for e in stack if e["name"] == str(layer_name)), None)
    if layer is None:
        return {"ok": False, "error": f"Weight layer '{layer_name}' not found"}

    g_dict = layer["weights"].setdefault(vg.name, {})
    for v_idx, w_val in vertex_weights.items():
        g_dict[str(int(v_idx))] = max(0.0, min(1.0, float(w_val)))

    _save_stack(target, stack)
    eval_res = evaluate_weight_layers(target) if evaluate else {"ok": True}
    return {
        "ok": True,
        "object": target.name,
        "layer": layer["name"],
        "group": vg.name,
        "authored_count": len(vertex_weights),
        "evaluation": eval_res,
    }


def set_weight_layer_state(
    obj: Any,
    layer_name: str,
    *,
    weight: Optional[float] = None,
    enabled: Optional[bool] = None,
    mode: Optional[str] = None,
    evaluate: bool = True,
) -> Dict[str, Any]:
    """Update `weight` (`0.0..1.0`), `enabled`, or `mode` on `layer_name` and re-evaluate composite weights."""
    target = _resolve_mesh_obj(obj)
    if target is None:
        return {"ok": False, "error": "Target is not a valid MESH object"}
    stack = _load_stack(target)
    layer = next((e for e in stack if e["name"] == str(layer_name)), None)
    if layer is None:
        return {"ok": False, "error": f"Weight layer '{layer_name}' not found"}

    if weight is not None and not layer.get("is_base"):
        layer["weight"] = max(0.0, min(1.0, float(weight)))
    if enabled is not None and not layer.get("is_base"):
        layer["enabled"] = bool(enabled)
    if mode is not None and not layer.get("is_base"):
        layer["mode"] = "ADD" if str(mode).upper() == "ADD" else "OVERRIDE"

    _save_stack(target, stack)
    eval_res = evaluate_weight_layers(target) if evaluate else {"ok": True}
    return {
        "ok": True,
        "object": target.name,
        "layer": layer["name"],
        "layers": list_weight_layers(target),
        "evaluation": eval_res,
    }


def evaluate_weight_layers(obj: Any = None) -> Dict[str, Any]:
    """Deterministically composite `BaseWeights` + enabled weight layers onto `obj.vertex_groups`,
    strictly preserving locked vertex groups (`vg.lock_weight == True`) and normalizing unlocked weights.
    """
    target = _resolve_mesh_obj(obj)
    if target is None:
        return {"ok": False, "error": "Target is not a valid MESH object"}

    stack = _load_stack(target)
    base_weights = stack[0].get("weights", {}) if stack else {}

    all_vgs = list(target.vertex_groups)
    locked_names = {vg.name for vg in all_vgs if vg.lock_weight}
    unlocked_vgs = [vg for vg in all_vgs if not vg.lock_weight]

    n_verts = len(target.data.vertices)
    # Initialize per-vertex unlocked map from BaseWeights
    comp: Dict[int, Dict[str, float]] = {}
    for v_idx in range(n_verts):
        v_str = str(v_idx)
        comp[v_idx] = {
            vg.name: float(base_weights.get(vg.name, {}).get(v_str, 0.0))
            for vg in unlocked_vgs
        }

    # Apply non-base layers in stack order
    for layer in stack[1:]:
        if not layer.get("enabled", True):
            continue
        opacity = max(0.0, min(1.0, float(layer.get("weight", 1.0))))
        if opacity <= 1e-6:
            continue
        l_mode = layer.get("mode", "OVERRIDE")
        l_weights = layer.get("weights", {}) or {}
        for gname, v_dict in l_weights.items():
            if gname in locked_names:
                continue
            for v_str, target_w in v_dict.items():
                v_idx = int(v_str)
                if v_idx not in comp or gname not in comp[v_idx]:
                    continue
                cur_w = comp[v_idx][gname]
                if l_mode == "ADD":
                    comp[v_idx][gname] = max(0.0, min(1.0, cur_w + float(target_w) * opacity))
                else:
                    comp[v_idx][gname] = cur_w * (1.0 - opacity) + float(target_w) * opacity

    # Write composited unlocked weights and normalize alongside locked weights
    idx_to_name = {vg.index: vg.name for vg in all_vgs}
    for v in target.data.vertices:
        v_idx = v.index
        locked_sum = 0.0
        for g_elem in v.groups:
            gname = idx_to_name.get(g_elem.group)
            if gname in locked_names:
                locked_sum += float(g_elem.weight)
        avail = max(0.0, 1.0 - locked_sum)
        u_map = comp[v_idx]
        u_sum = sum(max(0.0, w) for w in u_map.values())
        for vg in unlocked_vgs:
            raw_w = max(0.0, u_map.get(vg.name, 0.0))
            final_w = (raw_w / u_sum) * avail if u_sum > 1e-8 else 0.0
            vg.add([v_idx], final_w, "REPLACE")

    target.data.update()
    return {
        "ok": True,
        "object": target.name,
        "evaluated_layers": len(stack),
        "locked_groups_preserved": sorted(locked_names),
    }
