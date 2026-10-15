"""Maya-Style In-Viewport Heads-Up Caddies & `TargetWeld` Integration (`landfall_studio.modeling.caddy`).

Implements:
- Live non-destructive In-Viewport Heads-Up Caddies for:
  - `EXTRUDE` (`polyExtrudeFace1`): `thickness`, `offset`, `divisions`, `keep_faces_together`
  - `BEVEL` (`polyBevel1`): `width` (Fraction), `segments`, `profile`, `clamp_overlap`
  - `BRIDGE` (`polyBridgeEdge1`): `divisions`, `offset` (Twist), `smoothing_angle`
  - `CONNECT` (`polyConnectComponents1`): `segments`, `slide`, `pinch`
- Direct parameter scrubbing (`scrub_caddy_parameter`, `set_caddy_parameter`) that restores the
  clean baseline BMesh snapshot and re-evaluates the operation without stacking duplicate geometry.
- Shared command registry (`landfall_studio.commands`) integration so `G` repeats the last modeling
  operation with the active caddy parameters.
- `blendertk.TargetWeld` integration (`weld_vertices_target_weld` & `activate_target_weld`).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import commands as cmd_registry

CADDY_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "EXTRUDE": {
        "node_title": "polyExtrudeFace1",
        "params": [
            {"key": "thickness", "label": "Thickness", "type": "float", "default": 0.25, "min": -10.0, "max": 10.0, "step": 0.05},
            {"key": "offset", "label": "Local Translate Z / Offset", "type": "float", "default": 0.0, "min": -5.0, "max": 5.0, "step": 0.02},
            {"key": "divisions", "label": "Divisions", "type": "int", "default": 1, "min": 1, "max": 16, "step": 1},
            {"key": "keep_faces_together", "label": "Keep Faces Together", "type": "bool", "default": True},
        ],
    },
    "BEVEL": {
        "node_title": "polyBevel1",
        "params": [
            {"key": "width", "label": "Fraction (Width)", "type": "float", "default": 0.15, "min": 0.001, "max": 5.0, "step": 0.02},
            {"key": "segments", "label": "Segments", "type": "int", "default": 2, "min": 1, "max": 16, "step": 1},
            {"key": "profile", "label": "Profile (Depth)", "type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05},
            {"key": "clamp_overlap", "label": "Mitering / Clamp Overlap", "type": "bool", "default": True},
        ],
    },
    "BRIDGE": {
        "node_title": "polyBridgeEdge1",
        "params": [
            {"key": "divisions", "label": "Divisions", "type": "int", "default": 1, "min": 0, "max": 16, "step": 1},
            {"key": "offset", "label": "Twist / Offset", "type": "int", "default": 0, "min": -8, "max": 8, "step": 1},
            {"key": "smoothing_angle", "label": "Smooth Angle", "type": "float", "default": 30.0, "min": 0.0, "max": 180.0, "step": 5.0},
        ],
    },
    "CONNECT": {
        "node_title": "polyConnectComponents1",
        "params": [
            {"key": "segments", "label": "Segments", "type": "int", "default": 1, "min": 1, "max": 16, "step": 1},
            {"key": "slide", "label": "Slide", "type": "float", "default": 0.0, "min": -0.9, "max": 0.9, "step": 0.05},
            {"key": "pinch", "label": "Pinch", "type": "float", "default": 0.0, "min": -0.9, "max": 0.9, "step": 0.05},
        ],
    },
}

_active_caddy: Dict[str, Any] = {
    "open": False,
    "tool": "",
    "node_title": "",
    "object_name": "",
    "params": {},
    "active_param_key": "",
    "anchor_world": (0.0, 0.0, 0.0),
    "snapshot": None,
}


def _cleanup_snapshot_backup_mesh(snap: Optional[Dict[str, Any]]) -> None:
    if not isinstance(snap, dict):
        return
    b_name = snap.get("backup_mesh_name")
    if b_name:
        try:
            import bpy
            me = bpy.data.meshes.get(b_name)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        except Exception:
            pass
    snap["backup_mesh_name"] = ""


def _snapshot_mesh_state(obj: Any) -> Dict[str, Any]:
    """Capture a complete lossless Mesh + BMesh + selection + customdata (skin weights, shape keys, all UVs) snapshot."""
    import bpy
    import bmesh

    is_edit = obj.mode == "EDIT"
    if is_edit:
        obj.update_from_editmode()

    bm = bmesh.from_edit_mesh(obj.data) if is_edit else bmesh.new()
    if not is_edit:
        bm.from_mesh(obj.data)

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Create a full Mesh datablock copy so all customdata layers (dvert skin weights, shape keys, all UV sets, attributes) are preserved
    backup_mesh = obj.data.copy()
    backup_mesh.name = f"__landfall_caddy_snap_{obj.name}"

    vert_sel = [bool(v.select) for v in bm.verts]
    edge_sel = [bool(e.select) for e in bm.edges]
    face_sel = [bool(f.select) for f in bm.faces]

    # Compute world centroid of selected components for caddy anchor
    sel_coords = [obj.matrix_world @ v.co for v in bm.verts if v.select]
    if not sel_coords and bm.verts:
        sel_coords = [obj.matrix_world @ v.co for v in bm.verts]
    if sel_coords:
        cx = sum(p.x for p in sel_coords) / len(sel_coords)
        cy = sum(p.y for p in sel_coords) / len(sel_coords)
        cz = sum(p.z for p in sel_coords) / len(sel_coords)
        anchor = (float(cx), float(cy), float(cz))
    else:
        loc = obj.matrix_world.translation
        anchor = (float(loc.x), float(loc.y), float(loc.z))

    if not is_edit:
        bm.free()

    return {
        "backup_mesh_name": backup_mesh.name,
        "vert_sel": vert_sel,
        "edge_sel": edge_sel,
        "face_sel": face_sel,
        "anchor_world": anchor,
    }


def _restore_mesh_snapshot(obj: Any, snap: Dict[str, Any]) -> None:
    """Restore `obj`'s full BMesh geometry, customdata (skin weights, shape keys, all UV layers), and selections from `snap`."""
    import bpy
    import bmesh

    backup_mesh = bpy.data.meshes.get(snap.get("backup_mesh_name", ""))
    if backup_mesh is None:
        return

    is_edit = obj.mode == "EDIT"
    bm = bmesh.from_edit_mesh(obj.data) if is_edit else bmesh.new()
    bm.clear()
    bm.from_mesh(backup_mesh)

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    for v, sel in zip(bm.verts, snap.get("vert_sel", ())):
        v.select = sel
    for e, sel in zip(bm.edges, snap.get("edge_sel", ())):
        e.select = sel
    for f, sel in zip(bm.faces, snap.get("face_sel", ())):
        f.select = sel

    bm.normal_update()
    if is_edit:
        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
    else:
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()


def _execute_bm_operation(obj: Any, tool_upper: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the BMesh operation (`EXTRUDE`, `BEVEL`, `BRIDGE`, `CONNECT`) on `obj`."""
    import bmesh
    from mathutils import Vector

    is_edit = obj.mode == "EDIT"
    bm = bmesh.from_edit_mesh(obj.data) if is_edit else bmesh.new()
    if not is_edit:
        bm.from_mesh(obj.data)

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    if tool_upper == "EXTRUDE":
        thickness = float(params.get("thickness", 0.25))
        offset = float(params.get("offset", 0.0))
        divisions = max(1, int(params.get("divisions", 1)))
        keep_together = bool(params.get("keep_faces_together", True))

        sel_faces = [f for f in bm.faces if f.select]
        if not sel_faces and bm.faces:
            sel_faces = [bm.faces[0]]

        if keep_together:
            ret = bmesh.ops.extrude_face_region(bm, geom=sel_faces)
            geom_ex = ret.get("geom", [])
            ex_verts = [ele for ele in geom_ex if isinstance(ele, bmesh.types.BMVert)]
            ex_faces = [ele for ele in geom_ex if isinstance(ele, bmesh.types.BMFace)]
            ex_edges = [ele for ele in geom_ex if isinstance(ele, bmesh.types.BMEdge)]
            bmesh.ops.delete(bm, geom=sel_faces, context="FACES")

            # Compute average normal and center of extruded cap
            bm.normal_update()
            avg_n = Vector((0.0, 0.0, 0.0))
            center = Vector((0.0, 0.0, 0.0))
            for f in ex_faces:
                avg_n += f.normal
            if avg_n.length > 1e-6:
                avg_n.normalize()
            else:
                avg_n = Vector((0.0, 0.0, 1.0))

            if ex_verts:
                for v in ex_verts:
                    center += v.co
                center /= float(len(ex_verts))

            for v in ex_verts:
                v.co += avg_n * thickness
                if abs(offset) > 1e-6:
                    radial = v.co - (center + avg_n * thickness)
                    radial_t = radial - avg_n * radial.dot(avg_n)
                    if radial_t.length > 1e-6:
                        scale_fac = max(0.05, 1.0 - offset)
                        v.co = (center + avg_n * thickness) + radial_t * scale_fac

            if divisions > 1:
                # Side wall edges connect an ex_vert to a non-ex_vert
                ex_vert_set = set(ex_verts)
                side_edges = [
                    e
                    for e in bm.edges
                    if (e.verts[0] in ex_vert_set) ^ (e.verts[1] in ex_vert_set)
                ]
                if side_edges:
                    bmesh.ops.subdivide_edges(
                        bm, edges=side_edges, cuts=divisions - 1, use_grid_fill=True
                    )
        else:
            ret = bmesh.ops.extrude_discrete_faces(bm, faces=sel_faces)
            for f in ret.get("faces", []):
                nrm = f.normal.copy()
                f_center = f.calc_center_median()
                for v in f.verts:
                    v.co += nrm * thickness
                    if abs(offset) > 1e-6:
                        v.co = (f_center + nrm * thickness) + (v.co - (f_center + nrm * thickness)) * max(0.05, 1.0 - offset)

    elif tool_upper == "BEVEL":
        width = max(0.0005, float(params.get("width", 0.15)))
        segments = max(1, int(params.get("segments", 2)))
        profile = max(0.0, min(1.0, float(params.get("profile", 0.5))))
        clamp_overlap = bool(params.get("clamp_overlap", True))

        sel_edges = [e for e in bm.edges if e.select]
        if not sel_edges:
            sel_edges = list(bm.edges)
        if sel_edges:
            bmesh.ops.bevel(
                bm,
                geom=sel_edges,
                offset=width,
                offset_type="OFFSET",
                segments=segments,
                profile=profile,
                affect="EDGES",
                clamp_overlap=clamp_overlap,
            )

    elif tool_upper == "BRIDGE":
        divisions = max(0, int(params.get("divisions", 1)))
        offset = int(params.get("offset", 0))
        smoothing_angle = float(params.get("smoothing_angle", 30.0))

        sel_edges = [e for e in bm.edges if e.select]
        if len(sel_edges) < 2:
            sel_edges = [e for e in bm.edges if e.is_boundary]
        if len(sel_edges) >= 2:
            ret = bmesh.ops.bridge_loops(
                bm,
                edges=sel_edges,
                use_pairs=False,
                use_cyclic=False,
                use_merge=False,
                merge_factor=0.5,
                twist_offset=offset,
            )
            new_edges = ret.get("edges", [])
            threshold = math.radians(smoothing_angle)
            for e in new_edges:
                try:
                    e.smooth = e.calc_face_angle() < threshold
                except ValueError:
                    pass
            if divisions > 0 and new_edges:
                bmesh.ops.subdivide_edges(bm, edges=new_edges, cuts=divisions, use_grid_fill=True)

    elif tool_upper == "CONNECT":
        segments = max(1, int(params.get("segments", 1)))
        slide = max(-0.9, min(0.9, float(params.get("slide", 0.0))))
        pinch = max(-0.9, min(0.9, float(params.get("pinch", 0.0))))

        sel_edges = [e for e in bm.edges if e.select]
        if not sel_edges:
            sel_edges = list(bm.edges)

        # Record endpoint pairs for each edge before subdividing so we can apply slide & pinch
        edge_endpoints = [(e.verts[0].co.copy(), e.verts[1].co.copy()) for e in sel_edges]
        ret = bmesh.ops.subdivide_edges(
            bm,
            edges=sel_edges,
            cuts=segments,
            use_grid_fill=True,
            use_single_edge=True,
        )
        inner_verts = [ele for ele in ret.get("geom_inner", []) if isinstance(ele, bmesh.types.BMVert)]
        if inner_verts and (abs(slide) > 1e-4 or abs(pinch) > 1e-4):
            for v in inner_verts:
                # Find nearest original segment endpoints
                best_pair = None
                best_dist = 1e9
                for a_co, b_co in edge_endpoints:
                    ab = b_co - a_co
                    ab_len_sq = ab.length_squared
                    if ab_len_sq < 1e-10:
                        continue
                    t = max(0.0, min(1.0, (v.co - a_co).dot(ab) / ab_len_sq))
                    proj = a_co + ab * t
                    d = (v.co - proj).length
                    if d < best_dist:
                        best_dist = d
                        best_pair = (a_co, b_co, t)
                if best_pair is not None:
                    a_co, b_co, t = best_pair
                    # Pinch scales around midpoint 0.5; slide shifts uniformly in [0.05, 0.95]
                    t_pinched = 0.5 + (t - 0.5) * (1.0 + pinch)
                    t_final = max(0.05, min(0.95, t_pinched + slide * 0.45))
                    v.co = a_co.lerp(b_co, t_final)

    bm.normal_update()
    if is_edit:
        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
    else:
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

    return {
        "ok": True,
        "object_name": obj.name,
        "tool": tool_upper,
        "vertex_count": len(obj.data.vertices),
        "edge_count": len(obj.data.edges),
        "face_count": len(obj.data.polygons),
        "params": dict(params),
    }


def invoke_modeling_caddy(
    tool_type: str,
    target_obj_or_name: Any = None,
    params_dict: Optional[Dict[str, Any]] = None,
    **override_params: Any,
) -> Dict[str, Any]:
    """Invoke a modeling operation (`EXTRUDE`, `BEVEL`, `BRIDGE`, `CONNECT`) and open its live In-Viewport Caddy."""
    import bpy

    global _active_caddy
    t_upper = (tool_type or "EXTRUDE").strip().upper()
    if t_upper not in CADDY_SCHEMAS:
        return {"ok": False, "error": f"Unsupported caddy tool '{tool_type}'."}

    if isinstance(target_obj_or_name, dict) and params_dict is None:
        params_dict = target_obj_or_name
        target_obj_or_name = None

    if target_obj_or_name is None:
        obj = getattr(bpy.context.view_layer.objects, "active", None)
    elif isinstance(target_obj_or_name, str):
        obj = bpy.data.objects.get(target_obj_or_name)
    else:
        obj = target_obj_or_name

    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False, "error": f"{t_upper} caddy requires an active MESH object."}

    merged_overrides: Dict[str, Any] = {}
    if isinstance(params_dict, dict):
        merged_overrides.update(params_dict)
    merged_overrides.update(override_params)

    schema = CADDY_SCHEMAS[t_upper]
    params: Dict[str, Any] = {}
    for p_spec in schema["params"]:
        k = p_spec["key"]
        params[k] = merged_overrides.get(k, p_spec["default"])

    _cleanup_snapshot_backup_mesh(_active_caddy.get("snapshot"))
    snap = _snapshot_mesh_state(obj)
    res = _execute_bm_operation(obj, t_upper, params)

    _active_caddy = {
        "open": True,
        "tool": t_upper,
        "node_title": schema["node_title"],
        "object_name": obj.name,
        "params": dict(params),
        "active_param_key": schema["params"][0]["key"],
        "anchor_world": snap["anchor_world"],
        "snapshot": snap,
    }

    # Record in unified Studio command registry so 'G' repeats with current caddy parameters
    _record_caddy_in_command_registry(t_upper, params)

    return {
        "ok": True,
        "caddy_open": True,
        "tool": t_upper,
        "node_title": schema["node_title"],
        "object_name": obj.name,
        "params": dict(params),
        "vertex_count": res["vertex_count"],
        "edge_count": res["edge_count"],
        "face_count": res["face_count"],
    }


def _record_caddy_in_command_registry(tool_upper: str, params: Dict[str, Any]) -> None:
    snap_params = dict(params)
    cmd_registry.record_command(
        cmd_id=f"landfall_studio.caddy_{tool_upper.lower()}",
        kwargs={"tool_type": tool_upper, **snap_params},
        callable_fn=invoke_modeling_caddy,
        label=f"Maya {tool_upper.title()} ({CADDY_SCHEMAS[tool_upper]['node_title']})",
        repeatable=True,
    )


def set_caddy_parameter(param_key: str, value: Any) -> Dict[str, Any]:
    """Set a parameter on the currently open In-Viewport Caddy and live-re-evaluate from baseline snapshot."""
    import bpy

    global _active_caddy
    if not _active_caddy.get("open"):
        return {"ok": False, "error": "No In-Viewport Caddy is currently open."}

    t_upper = _active_caddy["tool"]
    schema = CADDY_SCHEMAS.get(t_upper)
    if schema is None:
        return {"ok": False, "error": "Invalid caddy schema."}

    p_spec = next((p for p in schema["params"] if p["key"] == param_key), None)
    if p_spec is None:
        return {"ok": False, "error": f"Unknown caddy parameter '{param_key}' for {t_upper}."}

    if p_spec["type"] == "int":
        coerced = max(int(p_spec["min"]), min(int(p_spec["max"]), int(round(float(value)))))
    elif p_spec["type"] == "float":
        coerced = max(float(p_spec["min"]), min(float(p_spec["max"]), round(float(value), 4)))
    else:
        coerced = bool(value)

    obj = bpy.data.objects.get(_active_caddy["object_name"])
    if obj is None or _active_caddy.get("snapshot") is None:
        return {"ok": False, "error": "Caddy target object or baseline snapshot is no longer valid."}

    _active_caddy["params"][param_key] = coerced
    _active_caddy["active_param_key"] = param_key

    _restore_mesh_snapshot(obj, _active_caddy["snapshot"])
    res = _execute_bm_operation(obj, t_upper, _active_caddy["params"])
    _record_caddy_in_command_registry(t_upper, _active_caddy["params"])

    return {
        "ok": True,
        "tool": t_upper,
        "param_key": param_key,
        "value": coerced,
        "params": dict(_active_caddy["params"]),
        "vertex_count": res["vertex_count"],
        "edge_count": res["edge_count"],
        "face_count": res["face_count"],
    }


def scrub_caddy_parameter(
    param_key: Optional[str] = None,
    delta_steps: float = 1.0,
    delta_px: Optional[float] = None,
) -> Dict[str, Any]:
    """Scrub a parameter on the active In-Viewport Caddy by `delta_steps * step` (or `delta_px / 10.0`)."""
    if not _active_caddy.get("open"):
        return {"ok": False, "error": "No In-Viewport Caddy is currently open."}

    if delta_px is not None:
        delta_steps = float(delta_px) / 10.0

    t_upper = _active_caddy["tool"]
    schema = CADDY_SCHEMAS[t_upper]
    key = param_key or _active_caddy.get("active_param_key") or schema["params"][0]["key"]
    p_spec = next((p for p in schema["params"] if p["key"] == key), None)
    if p_spec is None:
        return {"ok": False, "error": f"Unknown caddy parameter '{key}'."}

    cur_val = _active_caddy["params"].get(key, p_spec["default"])
    if p_spec["type"] == "bool":
        new_val = not bool(cur_val)
    else:
        step = float(p_spec.get("step", 0.05))
        new_val = float(cur_val) + float(delta_steps) * step

    return set_caddy_parameter(key, new_val)


def commit_or_close_caddy() -> Dict[str, Any]:
    """Commit and close the active In-Viewport Caddy."""
    global _active_caddy
    was_open = bool(_active_caddy.get("open"))
    tool = _active_caddy.get("tool", "")
    _cleanup_snapshot_backup_mesh(_active_caddy.get("snapshot"))
    _active_caddy["open"] = False
    _active_caddy["snapshot"] = None
    return {"ok": True, "was_open": was_open, "tool": tool}


commit_caddy = commit_or_close_caddy


def get_active_caddy_state() -> Dict[str, Any]:
    """Return a JSON-serializable snapshot of the active In-Viewport Heads-Up Caddy."""
    if not _active_caddy.get("open"):
        return {
            "open": False,
            "tool": "",
            "tool_id": "",
            "node_title": "",
            "object_name": "",
            "params": {},
            "values": {},
            "rows": [],
            "anchor_world": (0.0, 0.0, 0.0),
        }
    t_upper = _active_caddy["tool"]
    schema = CADDY_SCHEMAS.get(t_upper, {"params": []})
    rows = []
    for p_spec in schema["params"]:
        k = p_spec["key"]
        val = _active_caddy["params"].get(k, p_spec["default"])
        p_min = p_spec.get("min", 0.0)
        p_max = p_spec.get("max", 1.0)
        if p_spec["type"] in ("int", "float") and p_max > p_min:
            ratio = max(0.0, min(1.0, (float(val) - float(p_min)) / float(p_max - p_min)))
        else:
            ratio = 1.0 if val else 0.0
        rows.append(
            {
                "key": k,
                "label": p_spec["label"],
                "type": p_spec["type"],
                "value": val,
                "ratio": ratio,
                "active": (k == _active_caddy.get("active_param_key")),
            }
        )
    return {
        "open": True,
        "tool": t_upper,
        "tool_id": t_upper,
        "node_title": _active_caddy["node_title"],
        "object_name": _active_caddy["object_name"],
        "params": dict(_active_caddy["params"]),
        "values": dict(_active_caddy["params"]),
        "active_param_key": _active_caddy.get("active_param_key", ""),
        "rows": rows,
        "anchor_world": _active_caddy.get("anchor_world", (0.0, 0.0, 0.0)),
    }


# --------------------------------------------------------------------------------------
# `blendertk.TargetWeld` Integration
# --------------------------------------------------------------------------------------

def weld_vertices_target_weld(
    first_arg: Any = None,
    target_vert_index: Optional[int] = None,
    merge_to_center: bool = False,
    target_obj_or_name: Any = None,
    source_vert_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Weld `source_vert_index` onto `target_vert_index` via `blendertk.TargetWeld.weld_pair`."""
    import bmesh
    import bpy
    import blendertk as btk

    if isinstance(first_arg, int) and source_vert_index is None:
        source_vert_index = first_arg
    elif first_arg is not None and not isinstance(first_arg, int) and target_obj_or_name is None:
        target_obj_or_name = first_arg

    if source_vert_index is None or target_vert_index is None:
        return {"ok": False, "error": "source_vert_index and target_vert_index are required."}

    if target_obj_or_name is None:
        obj = getattr(bpy.context.view_layer.objects, "active", None)
    elif isinstance(target_obj_or_name, str):
        obj = bpy.data.objects.get(target_obj_or_name)
    else:
        obj = target_obj_or_name

    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False, "error": "Target Weld requires a MESH object."}

    is_edit = obj.mode == "EDIT"
    bm = bmesh.from_edit_mesh(obj.data) if is_edit else bmesh.new()
    if not is_edit:
        bm.from_mesh(obj.data)

    bm.verts.ensure_lookup_table()
    verts_before = len(bm.verts)
    if not (0 <= int(source_vert_index) < verts_before and 0 <= int(target_vert_index) < verts_before):
        if not is_edit:
            bm.free()
        return {"ok": False, "error": "Vertex indices out of range for Target Weld."}

    v_src = bm.verts[int(source_vert_index)]
    v_tgt = bm.verts[int(target_vert_index)]
    src_co = tuple(float(c) for c in v_src.co)
    tgt_co = tuple(float(c) for c in v_tgt.co)

    expected_co = tuple(
        float(c)
        for c in btk.TargetWeld.weld_position(src_co, tgt_co, bool(merge_to_center))
    )
    btk.TargetWeld.weld_pair(bm, v_src, v_tgt, bool(merge_to_center))
    bm.normal_update()

    if is_edit:
        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
    else:
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

    verts_after = len(obj.data.vertices)
    cmd_registry.record_command(
        cmd_id="landfall_studio.target_weld",
        kwargs={"merge_to_center": bool(merge_to_center)},
        callable_fn=lambda m=bool(merge_to_center): activate_target_weld(merge_to_center=m),
        label="Target Weld" if not merge_to_center else "Target Weld (Center)",
        repeatable=True,
    )

    return {
        "ok": True,
        "object_name": obj.name,
        "merge_to_center": bool(merge_to_center),
        "welded_position": expected_co,
        "welded_co": expected_co,
        "verts_before": verts_before,
        "verts_after": verts_after,
        "vertex_count": verts_after,
    }


def activate_target_weld(merge_to_center: bool = False) -> Dict[str, Any]:
    """Activate `blendertk.TargetWeld` modal vertex weld tool in the 3D Viewport."""
    import bpy
    import blendertk as btk

    if bpy.app.background:
        return {"ok": True, "background": True, "merge_to_center": bool(merge_to_center)}

    try:
        btk.TargetWeld.activate(merge_to_center=bool(merge_to_center))
        cmd_registry.record_command(
            cmd_id="landfall_studio.target_weld",
            kwargs={"merge_to_center": bool(merge_to_center)},
            callable_fn=lambda m=bool(merge_to_center): activate_target_weld(merge_to_center=m),
            label="Target Weld" if not merge_to_center else "Target Weld (Center)",
            repeatable=True,
        )
        return {"ok": True, "activated": True, "merge_to_center": bool(merge_to_center)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
