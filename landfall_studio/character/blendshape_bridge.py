"""Blendshape Animator Integration, Strict Topology Guard & Multi-Master Corrective Evaluator (`landfall_studio.character.blendshape_bridge`).

Wraps `blendertk.anim_utils.blendshape_animator.BlendshapeAnimator` while addressing both
upstream audit findings from `output/UPSTREAM_AUDIT.md`:
1. Replaces vertex-count-only checks with `validate_strict_topology` (verifying vertex count,
   edge vertex pairs, and polygon loop winding).
2. Guards against the Blender 5.1/5.2 C++ depsgraph bug where multiple animated master shape keys
   sharing a `Key` ID with scripted tent-driver correctives fail to evaluate one master key's mix
   contribution in `Object.to_mesh()`. When multiple animated master keys are present:
   - Blocks unguarded setups by default (`allow_multi_master_drivers=False`) with an explicit explanation.
   - When opted in (`allow_multi_master_drivers=True` / `evaluate_correctives_deterministic`),
     evaluates tent-function corrective weights in Python and removes the conflicting C++ scripted
     drivers on multi-master meshes so Blender's native shape-key mixer evaluates ALL master keys
     and ALL piecewise-linear in-between correctives accurately in `Object.to_mesh()` and the viewport.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from mathutils import Vector

from . import topology

_CORRECTIVE_INFIX = "_tween_w"
_frame_handler_installed: bool = False


def _get_fcurves_for_key(shape_keys: Any) -> List[Any]:
    if shape_keys is None:
        return []
    try:
        import blendertk as btk

        return list(btk.get_fcurves([shape_keys]))
    except Exception:
        anim = getattr(shape_keys, "animation_data", None)
        act = getattr(anim, "action", None) if anim else None
        if act is not None and hasattr(act, "fcurves"):
            return list(act.fcurves)
        return []


def detect_multi_master_driver_hazard(obj_or_name: Any) -> Dict[str, Any]:
    """Inspect `obj`'s Shape Keys for the Blender 5.1/5.2 multi-master animated driver hazard."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {
            "ok": False,
            "has_shape_keys": False,
            "animated_master_keys": [],
            "driven_corrective_keys": [],
            "all_corrective_keys": [],
            "hazard_detected": False,
            "explanation": "Object is not a valid MESH.",
        }

    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or len(sk.key_blocks) < 2:
        return {
            "ok": True,
            "object_name": obj.name,
            "has_shape_keys": False,
            "animated_master_keys": [],
            "driven_corrective_keys": [],
            "all_corrective_keys": [],
            "hazard_detected": False,
            "explanation": "No shape keys present.",
        }

    fcurves = _get_fcurves_for_key(sk)
    animated_masters: List[str] = []
    for fc in fcurves:
        dp = getattr(fc, "data_path", "")
        if dp.startswith('key_blocks["') and dp.endswith('"].value'):
            kname = dp[len('key_blocks["') : -len('"].value')]
            if _CORRECTIVE_INFIX not in kname and len( getattr(fc, "keyframe_points", ()) ) > 0:
                if kname not in animated_masters:
                    animated_masters.append(kname)

    all_correctives: List[str] = []
    for kb in sk.key_blocks:
        if _CORRECTIVE_INFIX in kb.name:
            all_correctives.append(kb.name)

    driven_correctives: List[str] = []
    anim = getattr(sk, "animation_data", None)
    if anim is not None and getattr(anim, "drivers", None):
        for drv_fc in anim.drivers:
            dp = getattr(drv_fc, "data_path", "")
            if dp.startswith('key_blocks["') and dp.endswith('"].value'):
                kname = dp[len('key_blocks["') : -len('"].value')]
                if _CORRECTIVE_INFIX in kname:
                    driven_correctives.append(kname)

    hazard = len(animated_masters) >= 2 and (len(driven_correctives) > 0 or len(all_correctives) > 0)
    if hazard:
        explanation = (
            f"Multi-master morph hazard on '{obj.name}': animated master keys {sorted(animated_masters)} "
            f"coexist with in-between correctives {sorted(all_correctives)}. In Blender 5.1/5.2, native C++ "
            "scripted drivers on a shared Key datablock can drop one master key's mix contribution in "
            "Object.to_mesh(). Use evaluate_correctives_deterministic() to evaluate tent weights safely."
        )
    else:
        explanation = "Single-master or driver-free shape key setup (safe)."

    return {
        "ok": True,
        "object_name": obj.name,
        "has_shape_keys": True,
        "animated_master_keys": sorted(animated_masters),
        "driven_corrective_keys": sorted(driven_correctives),
        "all_corrective_keys": sorted(all_correctives),
        "hazard_detected": hazard,
        "explanation": explanation,
    }


def compute_tent_weight(master_val: float, w: float, w_prev: float, w_next: float) -> float:
    """Exact piecewise-linear tent (hat) function matching Maya's in-between blendShape weight."""
    m = float(master_val)
    if m < w_prev or m > w_next:
        return 0.0
    if m <= w:
        return 1.0 if abs(w - w_prev) < 1e-9 else (m - w_prev) / (w - w_prev)
    return 1.0 if abs(w_next - w) < 1e-9 else (w_next - m) / (w_next - w)


def evaluate_correctives_deterministic(
    obj_or_name: Any,
    strip_conflicting_drivers_if_multi_master: bool = True,
) -> Dict[str, Any]:
    """Deterministically evaluate all `_tween_w###` corrective shape key weights on `obj`.

    Key insight: Blender's C++ depsgraph bug ONLY triggers when scripted drivers (`anim.drivers`)
    coexist with multiple animated master keys on the same `Key` datablock. Plain (un-driven) shape
    keys on the same `Key` datablock blend 100% accurately in `Object.to_mesh()`!
    Therefore, when 2+ master keys are present (or `strip_conflicting_drivers_if_multi_master=True`),
    removing the scripted driver from `_tween_w###` and setting `corr_kb.value = compute_tent_weight(...)`
    directly in Python makes both `Object.to_mesh()` and the 3D Viewport match the exact piecewise-linear
    in-between formula across ALL master keys simultaneously!
    """
    import bpy

    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return {"ok": False, "error": "Object is not a valid MESH."}

    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or len(sk.key_blocks) < 2:
        return {"ok": True, "object_name": obj.name, "evaluated_correctives": {}, "master_values": {}}

    # Group correctives by their master key prefix
    groups: Dict[str, List[Tuple[float, Any]]] = {}
    master_values: Dict[str, float] = {}
    ref_key = sk.reference_key

    for kb in sk.key_blocks:
        if kb == ref_key:
            continue
        if _CORRECTIVE_INFIX in kb.name:
            master_name, w_str = kb.name.split(_CORRECTIVE_INFIX, 1)
            try:
                w = int(w_str) / 1000.0
            except ValueError:
                continue
            groups.setdefault(master_name, []).append((w, kb))
        else:
            master_values[kb.name] = float(kb.value)

    hazard_info = detect_multi_master_driver_hazard(obj)
    is_multi_master = len(master_values) >= 2 or hazard_info["hazard_detected"]

    evaluated_correctives: Dict[str, float] = {}
    drivers_stripped: List[str] = []

    for master_name, corr_list in groups.items():
        m_kb = sk.key_blocks.get(master_name)
        if m_kb is None:
            continue
        m_val = float(m_kb.value)
        master_values[master_name] = m_val

        sorted_corrs = sorted(corr_list, key=lambda pair: pair[0])
        n = len(sorted_corrs)
        for idx, (w, corr_kb) in enumerate(sorted_corrs):
            w_prev = sorted_corrs[idx - 1][0] if idx > 0 else 0.0
            w_next = sorted_corrs[idx + 1][0] if idx < n - 1 else 1.0
            tent_val = compute_tent_weight(m_val, w, w_prev, w_next)

            if strip_conflicting_drivers_if_multi_master and is_multi_master:
                try:
                    if corr_kb.driver_remove("value"):
                        drivers_stripped.append(corr_kb.name)
                except Exception:
                    pass

            corr_kb.value = float(tent_val)
            evaluated_correctives[corr_kb.name] = round(float(tent_val), 6)

    try:
        sk.update_tag()
        obj.data.update_tag()
        if bpy.context.view_layer is not None:
            bpy.context.view_layer.update()
    except Exception:
        pass

    return {
        "ok": True,
        "object_name": obj.name,
        "is_multi_master": is_multi_master,
        "master_values": master_values,
        "evaluated_correctives": evaluated_correctives,
        "drivers_stripped": drivers_stripped,
    }


def compute_analytical_morphed_coords(obj_or_name: Any) -> List[Vector]:
    """Compute exact analytical vertex positions `Basis + sum_k(kb.value * (kb.co - Basis.co))` for verification."""
    obj = topology._resolve_mesh_obj(obj_or_name)
    if obj is None:
        return []
    sk = getattr(obj.data, "shape_keys", None)
    if sk is None or not sk.key_blocks:
        return [v.co.copy() for v in obj.data.vertices]

    basis = sk.reference_key
    n = len(basis.data)
    out = [basis.data[i].co.copy() for i in range(n)]
    for kb in sk.key_blocks:
        if kb == basis or kb.mute:
            continue
        val = float(kb.value)
        if abs(val) < 1e-8:
            continue
        rel = kb.relative_key or basis
        for i in range(n):
            out[i] += val * (kb.data[i].co - rel.data[i].co)
    return out


def create_blendshape_setup(
    base_obj: Any,
    target_obj: Any,
    name: str = "morph",
    start_frame: int = 1,
    end_frame: int = 100,
    allow_multi_master_drivers: bool = False,
    test_setup: bool = False,
) -> Dict[str, Any]:
    """Create a Blendshape Animator morph setup with strict topological validation and multi-master driver guard."""
    b_obj = topology._resolve_mesh_obj(base_obj)
    t_obj = topology._resolve_mesh_obj(target_obj)
    if b_obj is None or t_obj is None:
        return {
            "ok": False,
            "blocked": True,
            "reason": "Both base_obj and target_obj must be valid MESH objects.",
        }

    # 1. Strict topological connectivity check (blocks vertex-count-only shortcuts!)
    topo = topology.validate_strict_topology(b_obj, t_obj)
    if not topo["ok"]:
        return {
            "ok": False,
            "blocked": True,
            "reason": f"Topological connectivity mismatch blocked Blendshape setup: {topo['reason']}",
            "topology": topo,
        }

    # 2. Check for existing animated master keys + correctives hazard
    sk = getattr(b_obj.data, "shape_keys", None)
    if sk is not None:
        fcurves = _get_fcurves_for_key(sk)
        other_animated = set()
        for fc in fcurves:
            dp = getattr(fc, "data_path", "")
            if dp.startswith('key_blocks["') and dp.endswith('"].value'):
                kname = dp[len('key_blocks["') : -len('"].value')]
                if kname != name and _CORRECTIVE_INFIX not in kname and len(getattr(fc, "keyframe_points", ())) > 0:
                    other_animated.add(kname)
        if other_animated and not allow_multi_master_drivers:
            return {
                "ok": False,
                "blocked": True,
                "multi_master_hazard": True,
                "existing_animated_masters": sorted(other_animated),
                "reason": (
                    f"Blocked binding second animated master key '{name}' onto '{b_obj.name}' which already "
                    f"animates {sorted(other_animated)}. Pass allow_multi_master_drivers=True to enable "
                    "Landfall Studio's deterministic corrective evaluator."
                ),
            }

    from blendertk.anim_utils.blendshape_animator._blendshape_animator import BlendshapeAnimator

    uv_mat_snap = topology.snapshot_uvs_and_materials(b_obj)
    animator = BlendshapeAnimator()
    ok = animator.create(
        base_obj=b_obj,
        target_obj=t_obj,
        start_frame=start_frame,
        end_frame=end_frame,
        name=name,
        test_setup=test_setup,
    )
    uv_mat_check = topology.verify_uvs_and_materials_preserved(b_obj, uv_mat_snap)

    return {
        "ok": bool(ok),
        "blocked": False,
        "base_object": b_obj.name,
        "target_object": t_obj.name,
        "key_name": animator.key_name,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "topology": topo,
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
    }


def create_blendshape_tweens(
    base_obj: Any,
    weights: Optional[List[float]] = None,
    frames: Optional[List[int]] = None,
    count: int = 3,
    key_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create weight-based or frame-based in-between tween meshes and preserve UVs/materials on each tween."""
    b_obj = topology._resolve_mesh_obj(base_obj)
    if b_obj is None:
        return {"ok": False, "error": "Base object is not a valid MESH."}

    from blendertk.anim_utils.blendshape_animator._blendshape_animator import BlendshapeAnimator

    if key_name:
        b_obj["blendshape_animator_key"] = key_name
    animator = BlendshapeAnimator.from_existing(b_obj)
    if animator is None:
        return {"ok": False, "error": f"No existing BlendshapeAnimator setup found on '{b_obj.name}'."}

    if frames:
        tweens = animator.edit_frame_based(frames=frames)
    else:
        tweens = animator.edit_weight_based(weights=weights, count=count)

    tween_names: List[str] = []
    for t in tweens:
        topology.copy_uvs_and_materials(b_obj, t.obj)
        tween_names.append(t.mesh)

    return {
        "ok": len(tweens) > 0,
        "base_object": b_obj.name,
        "key_name": animator.key_name,
        "tween_count": len(tweens),
        "tween_meshes": tween_names,
        "weights": [t.weight for t in tweens],
    }


def apply_blendshape_tweens(
    base_obj: Any,
    key_name: Optional[str] = None,
    strict_topology: bool = True,
    use_deterministic_multi_master: bool = True,
) -> Dict[str, Any]:
    """Apply sculpted tween meshes back to corrective shape keys with strict topological connectivity checks."""
    b_obj = topology._resolve_mesh_obj(base_obj)
    if b_obj is None:
        return {"ok": False, "error": "Base object is not a valid MESH."}

    from blendertk.anim_utils.blendshape_animator._blendshape_animator import BlendshapeAnimator
    from blendertk.anim_utils.blendshape_animator.applicator import ApplyStatus
    from blendertk.anim_utils.blendshape_animator.target import Targets

    if key_name:
        b_obj["blendshape_animator_key"] = key_name
    animator = BlendshapeAnimator.from_existing(b_obj)
    if animator is None:
        return {"ok": False, "error": f"No existing BlendshapeAnimator setup found on '{b_obj.name}'."}

    all_tweens = Targets.find_all_targets(
        key_block_name=animator.key_name,
        base_mesh_name=b_obj.name,
    )
    if not all_tweens:
        return {"ok": False, "error": "No tween meshes found for setup.", "applied": [], "rejected": []}

    valid_tweens = []
    rejected_tweens = []
    for t in all_tweens:
        if strict_topology:
            topo = topology.validate_strict_topology(b_obj, t.obj)
            if not topo["ok"]:
                rejected_tweens.append({"mesh": t.mesh, "weight": t.weight, "reason": topo["reason"]})
                continue
        valid_tweens.append(t)

    if not valid_tweens:
        return {
            "ok": False,
            "blocked": True,
            "reason": f"All {len(rejected_tweens)} tween(s) failed strict topological connectivity validation.",
            "applied": [],
            "rejected": rejected_tweens,
        }

    uv_mat_snap = topology.snapshot_uvs_and_materials(b_obj)
    results = animator.tween_applicator.apply_tweens(valid_tweens, validate_topology=False)
    applied_names = [t.mesh for t, st in results if st is ApplyStatus.APPLIED]

    det_eval = {}
    if use_deterministic_multi_master:
        det_eval = evaluate_correctives_deterministic(
            b_obj, strip_conflicting_drivers_if_multi_master=True
        )

    uv_mat_check = topology.verify_uvs_and_materials_preserved(b_obj, uv_mat_snap)
    return {
        "ok": len(applied_names) > 0 and len(rejected_tweens) == 0,
        "partial_ok": len(applied_names) > 0,
        "base_object": b_obj.name,
        "key_name": animator.key_name,
        "applied": applied_names,
        "rejected": rejected_tweens,
        "deterministic_eval": det_eval,
        "uvs_preserved": uv_mat_check["uvs_preserved"],
        "materials_preserved": uv_mat_check["materials_preserved"],
    }


def _on_frame_change_post(scene: Any, *_args: Any) -> None:
    """Keep multi-master corrective shape keys synchronized during timeline scrubbing."""
    try:
        for obj in getattr(scene, "objects", ()):
            if getattr(obj, "type", None) != "MESH" or getattr(obj, "data", None) is None:
                continue
            sk = getattr(obj.data, "shape_keys", None)
            if sk is None or len(sk.key_blocks) < 3:
                continue
            if any(_CORRECTIVE_INFIX in kb.name for kb in sk.key_blocks):
                evaluate_correctives_deterministic(obj, strip_conflicting_drivers_if_multi_master=True)
    except Exception:
        pass


def register_handlers() -> None:
    global _frame_handler_installed
    try:
        import bpy

        if _on_frame_change_post not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(_on_frame_change_post)
        _frame_handler_installed = True
    except Exception:
        pass


def unregister_handlers() -> None:
    global _frame_handler_installed
    try:
        import bpy

        while _on_frame_change_post in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(_on_frame_change_post)
        _frame_handler_installed = False
    except Exception:
        pass
