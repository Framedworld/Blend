"""Maya-Style Animation Layers Proof Backed by Blender NLA (`landfall_studio.advanced.anim_layers`).

Provides a non-destructive Maya `AnimLayer` workflow (`BaseAnimation` + additive/override layers)
mapped onto Blender's NLA stack (`obj.animation_data.nla_tracks`):
- `ensure_base_animation_layer(obj)`: Ensures `obj.animation_data` has a `BaseAnimation` NLA track
  holding any existing base keyframes so layered tweaks never overwrite the base performance.
- `list_anim_layers(obj)`: Lists `BaseAnimation` plus all `AnimLayer*` tracks with `name`, `mode`
  (`ADD` -> NLA `COMBINE` / `ADD`, `OVERRIDE` -> NLA `REPLACE`), `weight` (`0.0..1.0` strip
  `influence`), `mute`, `solo`, `lock`, and `keyframe_count`.
- `create_anim_layer(obj, name="AnimLayer1", mode="ADD", weight=1.0)`: Creates a new NLA track +
  dedicated Action strip (`use_animated_influence = True`) so artists can keyframe additive offsets
  or full overrides on top of `BaseAnimation`.
- `set_anim_layer_state(obj, layer_name, *, weight=None, mute=None, solo=None, lock=None, mode=None)`
- `keyframe_on_anim_layer(obj, layer_name, data_path, index, value, frame)`: Inserts a keyframe
  directly into `layer_name`'s Action and refreshes the NLA strip range.
- `remove_anim_layer(obj, layer_name)`: Removes a non-base animation layer without harming
  `BaseAnimation`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _resolve_obj(obj: Any = None) -> Optional[Any]:
    import bpy

    if obj is None:
        return getattr(bpy.context.view_layer.objects, "active", None)
    if isinstance(obj, str):
        return bpy.data.objects.get(obj)
    return obj


def _iter_action_fcurves(action: Any) -> List[Any]:
    """Return F-Curves from a Blender Action across Blender 4.x and Blender 5.x slotted Actions."""
    if action is None:
        return []
    fc = getattr(action, "fcurves", None)
    if fc is not None and len(fc) > 0:
        return list(fc)
    out: List[Any] = []
    try:
        for layer in getattr(action, "layers", ()):
            for strip in getattr(layer, "strips", ()):
                for cbag in getattr(strip, "channelbags", ()):
                    out.extend(getattr(cbag, "fcurves", ()))
    except Exception:
        pass
    return out


def _count_action_keyframes(action: Any) -> int:
    total = 0
    for fc in _iter_action_fcurves(action):
        total += len(getattr(fc, "keyframe_points", ()))
    return total


def _ensure_fcurve_on_action(action: Any, obj: Any, data_path: str, index: int = 0) -> Optional[Any]:
    """Find or create an F-Curve on `action` compatible with Blender 5.2 slotted Actions."""
    for fc in _iter_action_fcurves(action):
        if fc.data_path == data_path and int(fc.array_index) == int(index):
            return fc

    # Try direct `action.fcurves.new` first
    fcurves = getattr(action, "fcurves", None)
    if fcurves is not None and hasattr(fcurves, "new"):
        try:
            return fcurves.new(data_path=data_path, index=int(index))
        except Exception:
            pass

    # Blender 5.x slotted Action channelbag path
    try:
        slots = getattr(action, "slots", None)
        slot = slots[0] if (slots and len(slots) > 0) else slots.new(id_type="OBJECT", name=obj.name)
        layers = getattr(action, "layers", None)
        layer = layers[0] if (layers and len(layers) > 0) else layers.new("Layer")
        strips = getattr(layer, "strips", None)
        strip = strips[0] if (strips and len(strips) > 0) else strips.new(type="KEYFRAME")
        cbag = strip.channelbag(slot, ensure=True)
        return cbag.fcurves.new(data_path=data_path, index=int(index))
    except Exception:
        return None


def _ensure_strip_slot(strip: Any, act: Any, target: Any) -> None:
    """Ensure Blender 5.2 slotted Action has its slot bound to `strip.action_slot` so NLA evaluates F-Curves."""
    try:
        slots = getattr(act, "slots", None)
        if slots is not None:
            slot = slots[0] if len(slots) > 0 else slots.new(id_type="OBJECT", name=target.name)
            if hasattr(strip, "action_slot") and getattr(strip, "action_slot", None) is None:
                strip.action_slot = slot
    except Exception:
        pass


def _sync_strip_range(strip: Any, f_start: float, f_end: float) -> None:
    """Keep NLA strip frame range and action frame range 1:1 (scale = 1.0) so keyframes evaluate at exact frames."""
    s = float(min(f_start, f_end))
    e = float(max(f_end, s + 1.0))
    try:
        strip.scale = 1.0
        strip.action_frame_start = s
        strip.action_frame_end = e
        strip.frame_start = s
        strip.frame_end = e
        strip.scale = 1.0
    except Exception:
        pass


def _set_strip_influence(strip: Any, weight: float) -> None:
    """Set NLA strip influence (`0.0..1.0`) and keyframe its constant influence F-Curve so `frame_set` preserves it."""
    w = max(0.0, min(1.0, float(weight)))
    strip.use_animated_influence = True
    strip.influence = w
    try:
        fcs = getattr(strip, "fcurves", None)
        if fcs is not None:
            fc = next((f for f in fcs if f.data_path == "influence"), None)
            if fc is not None:
                while len(fc.keyframe_points) > 0:
                    fc.keyframe_points.remove(fc.keyframe_points[-1])
                kp = fc.keyframe_points.insert(frame=1.0, value=w)
                kp.interpolation = "CONSTANT"
                fc.update()
                return
        strip.keyframe_insert(data_path="influence", frame=1)
    except Exception:
        pass


def ensure_base_animation_layer(obj: Any = None) -> Dict[str, Any]:
    """Ensure `obj` has `animation_data` and a `BaseAnimation` NLA track."""
    import bpy

    target = _resolve_obj(obj)
    if target is None:
        return {"ok": False, "error": "No target object"}

    adt = target.animation_data
    if adt is None:
        adt = target.animation_data_create()

    scene = bpy.context.scene
    f_start = int(getattr(scene, "frame_start", 1))
    f_end = int(getattr(scene, "frame_end", 120))

    base_track = None
    for trk in adt.nla_tracks:
        if trk.name == "BaseAnimation":
            base_track = trk
            break

    if base_track is None:
        base_track = adt.nla_tracks.new()
        base_track.name = "BaseAnimation"
        has_existing_action = adt.action is not None
        if has_existing_action:
            act = adt.action
            adt.action = None
            try:
                act_range = act.frame_range
                s_start = min(f_start, int(act_range[0]))
                s_end = max(f_end, int(round(float(act_range[1]))))
            except Exception:
                s_start, s_end = f_start, f_end
        else:
            act = bpy.data.actions.new(name=f"{target.name}_BaseAnimation")
            _ensure_fcurve_on_action(act, target, "location", 0)
            s_start, s_end = f_start, f_end
        strip = base_track.strips.new(name="BaseAnimation", start=s_start, action=act)
        _ensure_strip_slot(strip, act, target)
        strip.blend_type = "REPLACE"
        strip.extrapolation = "HOLD"
        _sync_strip_range(strip, s_start, s_end)

    return {
        "ok": True,
        "object": target.name,
        "base_track": base_track.name,
    }


def list_anim_layers(obj: Any = None) -> List[Dict[str, Any]]:
    """Return structured list of Maya-style Animation Layers on `obj`."""
    target = _resolve_obj(obj)
    if target is None:
        return []
    adt = getattr(target, "animation_data", None)
    if adt is None or len(adt.nla_tracks) == 0:
        act = getattr(adt, "action", None) if adt is not None else None
        return [
            {
                "name": "BaseAnimation",
                "is_base": True,
                "mode": "BASE",
                "blend_type": "REPLACE",
                "weight": 1.0,
                "mute": False,
                "solo": False,
                "lock": False,
                "keyframe_count": _count_action_keyframes(act),
            }
        ]

    out: List[Dict[str, Any]] = []
    for idx, trk in enumerate(adt.nla_tracks):
        strip = trk.strips[0] if len(trk.strips) > 0 else None
        act = strip.action if strip is not None else None
        btype = getattr(strip, "blend_type", "REPLACE") if strip is not None else "REPLACE"
        is_base = idx == 0 or trk.name == "BaseAnimation"
        mode = "BASE" if is_base else ("ADD" if btype in ("ADD", "COMBINE") else "OVERRIDE")
        weight = float(getattr(strip, "influence", 1.0)) if strip is not None else 1.0
        out.append(
            {
                "name": trk.name,
                "is_base": is_base,
                "mode": mode,
                "blend_type": btype,
                "weight": round(weight, 4),
                "mute": bool(trk.mute),
                "solo": bool(trk.is_solo),
                "lock": bool(trk.lock),
                "keyframe_count": _count_action_keyframes(act),
            }
        )
    return out


def create_anim_layer(
    obj: Any = None,
    name: str = "AnimLayer1",
    *,
    mode: str = "ADD",
    weight: float = 1.0,
) -> Dict[str, Any]:
    """Create a new Maya-style `AnimLayer` (`ADD` or `OVERRIDE`) on top of `BaseAnimation`."""
    import bpy

    if isinstance(obj, str) and obj not in bpy.data.objects and name == "AnimLayer1":
        name = obj
        obj = None

    target = _resolve_obj(obj)
    if target is None:
        return {"ok": False, "error": "No target object"}

    ensure_base_animation_layer(target)
    adt = target.animation_data

    existing_names = {t.name for t in adt.nla_tracks}
    final_name = str(name or "AnimLayer1").strip()
    suffix = 1
    while final_name in existing_names:
        suffix += 1
        final_name = f"AnimLayer{suffix}"

    scene = bpy.context.scene
    f_start = int(getattr(scene, "frame_start", 1))
    f_end = int(getattr(scene, "frame_end", 120))

    trk = adt.nla_tracks.new()
    trk.name = final_name
    act = bpy.data.actions.new(name=f"{target.name}_{final_name}")
    _ensure_fcurve_on_action(act, target, "location", 0)
    strip = trk.strips.new(name=final_name, start=f_start, action=act)
    _ensure_strip_slot(strip, act, target)

    mode_up = str(mode or "ADD").upper()
    strip.blend_type = "ADD" if mode_up == "ADD" else "REPLACE"
    strip.extrapolation = "HOLD"
    _sync_strip_range(strip, f_start, f_end)
    _set_strip_influence(strip, weight)

    return {
        "ok": True,
        "object": target.name,
        "layer": final_name,
        "mode": "ADD" if strip.blend_type == "ADD" else "OVERRIDE",
        "weight": round(float(strip.influence), 4),
        "layers": list_anim_layers(target),
    }


def set_anim_layer_state(
    obj: Any = None,
    layer_name: str = "",
    *,
    weight: Optional[float] = None,
    mute: Optional[bool] = None,
    solo: Optional[bool] = None,
    lock: Optional[bool] = None,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Update weight (`0.0..1.0`), `mute`, `solo`, `lock`, or `mode` (`ADD`/`OVERRIDE`) on `layer_name`."""
    import bpy

    if isinstance(obj, str) and not layer_name and obj not in bpy.data.objects:
        layer_name = obj
        obj = None

    target = _resolve_obj(obj)
    if target is None or target.animation_data is None:
        return {"ok": False, "error": "Target object has no animation layers"}

    adt = target.animation_data
    trk = adt.nla_tracks.get(str(layer_name))
    if trk is None:
        return {"ok": False, "error": f"Animation layer '{layer_name}' not found"}

    strip = trk.strips[0] if len(trk.strips) > 0 else None
    if weight is not None and strip is not None:
        _set_strip_influence(strip, weight)
    if mute is not None:
        trk.mute = bool(mute)
    if solo is not None:
        trk.is_solo = bool(solo)
    if lock is not None:
        trk.lock = bool(lock)
    if mode is not None and strip is not None and trk.name != "BaseAnimation":
        m_up = str(mode).upper()
        strip.blend_type = "ADD" if m_up == "ADD" else "REPLACE"

    try:
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)
        bpy.context.view_layer.update()
    except Exception:
        pass

    return {
        "ok": True,
        "object": target.name,
        "layer": trk.name,
        "layers": list_anim_layers(target),
    }


def keyframe_on_anim_layer(
    obj: Any = None,
    layer_name: str = "BaseAnimation",
    data_path: str = "location",
    index: int = 0,
    *,
    value: Optional[float] = None,
    values: Optional[Dict[str, Sequence[float]]] = None,
    frame: Optional[float] = None,
) -> Dict[str, Any]:
    """Insert a keyframe (`data_path[index] = value` or `values={path: vec}`) directly on `layer_name`'s NLA strip Action."""
    import bpy

    if isinstance(obj, str) and obj not in bpy.data.objects:
        layer_name = obj
        obj = None

    target = _resolve_obj(obj)
    if target is None:
        return {"ok": False, "error": "No target object"}

    ensure_base_animation_layer(target)
    adt = target.animation_data
    trk = adt.nla_tracks.get(str(layer_name))
    if trk is None:
        return {"ok": False, "error": f"Animation layer '{layer_name}' not found"}
    if trk.lock:
        return {
            "ok": False,
            "status": "BLOCKED",
            "error": f"Animation layer '{layer_name}' is locked",
        }

    strip = trk.strips[0] if len(trk.strips) > 0 else None
    if strip is None or strip.action is None:
        return {"ok": False, "error": f"Animation layer '{layer_name}' has no Action strip"}

    f_no = float(frame if frame is not None else bpy.context.scene.frame_current)

    pairs: List[tuple[str, int, float]] = []
    if values:
        for dp, vec in values.items():
            if isinstance(vec, (list, tuple)):
                for idx_i, v_i in enumerate(vec):
                    pairs.append((dp, idx_i, float(v_i)))
            else:
                pairs.append((dp, 0, float(vec)))
    elif value is not None:
        pairs.append((data_path, int(index), float(value)))
    else:
        cur_attr = getattr(target, data_path, None)
        if cur_attr is not None and hasattr(cur_attr, "__getitem__"):
            pairs.append((data_path, int(index), float(cur_attr[int(index)])))
        else:
            pairs.append((data_path, int(index), float(cur_attr or 0.0)))

    for dp, idx_i, val_i in pairs:
        fc = _ensure_fcurve_on_action(strip.action, target, dp, index=int(idx_i))
        if fc is None:
            return {"ok": False, "error": f"Could not create F-Curve for {dp}[{idx_i}]"}
        kp = fc.keyframe_points.insert(frame=f_no, value=float(val_i), options={"FAST"})
        kp.interpolation = "BEZIER"
        fc.update()

    _ensure_strip_slot(strip, strip.action, target)
    _sync_strip_range(strip, min(strip.frame_start, f_no), max(strip.frame_end, f_no))

    try:
        bpy.context.scene.frame_set(int(round(f_no)))
        bpy.context.view_layer.update()
    except Exception:
        pass

    return {
        "ok": True,
        "object": target.name,
        "layer": trk.name,
        "data_path": data_path,
        "index": int(index),
        "frame": f_no,
        "value": float(pairs[-1][2]) if pairs else 0.0,
        "keyframe_count": _count_action_keyframes(strip.action),
    }


def remove_anim_layer(obj: Any = None, layer_name: str = "") -> Dict[str, Any]:
    """Remove a non-base `AnimLayer` NLA track cleanly."""
    import bpy

    if isinstance(obj, str) and not layer_name and obj not in bpy.data.objects:
        layer_name = obj
        obj = None

    target = _resolve_obj(obj)
    if target is None or target.animation_data is None:
        return {"ok": False, "error": "Target object has no animation layers"}
    if str(layer_name) == "BaseAnimation":
        return {"ok": False, "status": "BLOCKED", "error": "Cannot delete BaseAnimation layer"}

    adt = target.animation_data
    trk = adt.nla_tracks.get(str(layer_name))
    if trk is None:
        return {"ok": False, "error": f"Animation layer '{layer_name}' not found"}

    adt.nla_tracks.remove(trk)
    return {
        "ok": True,
        "object": target.name,
        "removed": str(layer_name),
        "layers": list_anim_layers(target),
    }
