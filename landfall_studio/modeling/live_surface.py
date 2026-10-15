"""Scoped `Make Live` Surface Targeting & Projection (`landfall_studio.modeling.live_surface`).

Implements Maya's `Modify > Make Live` workflow in Blender:
- Designates a specific reference mesh (`live_object_name`) as the active Live Surface.
- Makes the designated live mesh non-selectable (`hide_select = True`) and enables its wireframe
  overlay (`show_wire = True`, `show_all_edges = True`) as a visual indicator while storing its
  original state for clean restoration when `Make Live` is turned off.
- Builds a cached world-space `mathutils.bvhtree.BVHTree` strictly from the designated live mesh
  so `project_point_to_live_surface` and `project_mesh_to_live_surface` snap exclusively onto the
  designated target and ignore bystander meshes in the scene.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

_LIVE_SCENE_KEY = "landfall_live_surface"
_LIVE_STATE_BACKUP_KEY = "_landfall_live_prev_state"

_live_bvh_cache: Dict[str, Any] = {
    "object_name": "",
    "matrix_sig": None,
    "vert_count": -1,
    "poly_count": -1,
    "bvh": None,
}


def _resolve_mesh_object(obj_or_name: Any) -> Any:
    import bpy

    if obj_or_name is None:
        return None
    if isinstance(obj_or_name, str):
        obj = bpy.data.objects.get(obj_or_name)
    else:
        obj = obj_or_name
    if obj is not None and getattr(obj, "type", "") == "MESH":
        return obj
    return None


def get_live_surface_object() -> Any:
    """Return the currently designated `Make Live` `bpy.types.Object`, or `None`."""
    import bpy

    scene = getattr(bpy.context, "scene", None)
    if scene is None:
        return None
    live_name = str(scene.get(_LIVE_SCENE_KEY, "") or "")
    if not live_name:
        return None
    obj = bpy.data.objects.get(live_name)
    if obj is None or getattr(obj, "type", "") != "MESH":
        return None
    return obj


def get_live_surface_state() -> Dict[str, Any]:
    """Return structured status of the active `Make Live` surface."""
    obj = get_live_surface_object()
    if obj is None:
        return {
            "active": False,
            "object_name": "",
            "hide_select": False,
            "show_wire": False,
            "vertex_count": 0,
            "polygon_count": 0,
        }
    mesh = obj.data
    return {
        "active": True,
        "object_name": obj.name,
        "hide_select": bool(obj.hide_select),
        "show_wire": bool(obj.show_wire),
        "vertex_count": len(mesh.vertices) if mesh else 0,
        "polygon_count": len(mesh.polygons) if mesh else 0,
    }


def _restore_object_live_visuals(obj: Any) -> None:
    """Restore `hide_select` and `show_wire` on a previously live object."""
    if obj is None:
        return
    try:
        raw = obj.get(_LIVE_STATE_BACKUP_KEY, None)
        if raw is not None:
            import json

            saved = json.loads(str(raw))
            obj.hide_select = bool(saved.get("hide_select", False))
            obj.show_wire = bool(saved.get("show_wire", False))
            obj.show_all_edges = bool(saved.get("show_all_edges", False))
            if "color" in saved and len(saved["color"]) == 4:
                obj.color = tuple(float(c) for c in saved["color"])
            del obj[_LIVE_STATE_BACKUP_KEY]
        else:
            obj.hide_select = False
            obj.show_wire = False
            obj.show_all_edges = False
    except Exception:
        try:
            obj.hide_select = False
        except Exception:
            pass


def clear_live_surface() -> Dict[str, Any]:
    """Deactivate `Make Live` and restore the previous live object's selectability and display."""
    import bpy

    global _live_bvh_cache
    prev_obj = get_live_surface_object()
    prev_name = prev_obj.name if prev_obj is not None else ""
    if prev_obj is not None:
        _restore_object_live_visuals(prev_obj)

    scene = getattr(bpy.context, "scene", None)
    if scene is not None and _LIVE_SCENE_KEY in scene:
        try:
            del scene[_LIVE_SCENE_KEY]
        except Exception:
            scene[_LIVE_SCENE_KEY] = ""

    _live_bvh_cache = {
        "object_name": "",
        "matrix_sig": None,
        "vert_count": -1,
        "poly_count": -1,
        "bvh": None,
    }
    return {
        "ok": True,
        "active": False,
        "cleared_object": prev_name,
        "restored_selectable": (not bool(prev_obj.hide_select)) if prev_obj is not None else True,
    }


def set_live_surface(obj_or_name: Any = None, toggle: bool = False) -> Dict[str, Any]:
    """Designate `obj_or_name` (or the active mesh if `None`) as the scoped `Make Live` surface."""
    import json
    import bpy

    if obj_or_name is None:
        obj = getattr(bpy.context.view_layer.objects, "active", None)
    else:
        obj = _resolve_mesh_object(obj_or_name)

    current_live = get_live_surface_object()
    if obj is None:
        if toggle and current_live is not None:
            return clear_live_surface()
        return {"ok": False, "error": "Make Live requires a target mesh object."}

    if toggle and current_live is not None and current_live.name == obj.name:
        return clear_live_surface()

    if current_live is not None and current_live.name != obj.name:
        _restore_object_live_visuals(current_live)

    # Save original state before applying Make Live lock + visual wireframe indicator
    if _LIVE_STATE_BACKUP_KEY not in obj:
        backup = {
            "hide_select": bool(obj.hide_select),
            "show_wire": bool(obj.show_wire),
            "show_all_edges": bool(obj.show_all_edges),
            "color": [float(c) for c in obj.color],
        }
        obj[_LIVE_STATE_BACKUP_KEY] = json.dumps(backup)

    # Make Live visual & selection lock (Maya dark-emerald wireframe, unselectable)
    obj.hide_select = True
    obj.show_wire = True
    obj.show_all_edges = True
    obj.color = (0.18, 0.82, 0.58, 1.0)
    try:
        obj.select_set(False)
    except Exception:
        pass

    scene = getattr(bpy.context, "scene", None)
    if scene is not None:
        scene[_LIVE_SCENE_KEY] = obj.name

    # Pre-warm BVH cache
    _get_or_build_live_bvh(obj)

    return {
        "ok": True,
        "active": True,
        "object_name": obj.name,
        "hide_select": bool(obj.hide_select),
        "show_wire": bool(obj.show_wire),
    }


def _get_or_build_live_bvh(live_obj: Any = None):
    """Build or return a cached world-space `BVHTree` strictly for `live_obj`."""
    import bmesh
    from mathutils.bvhtree import BVHTree

    global _live_bvh_cache
    obj = live_obj if live_obj is not None else get_live_surface_object()
    if obj is None or getattr(obj, "type", "") != "MESH" or obj.data is None:
        return None

    mesh = obj.data
    mw = obj.matrix_world
    mat_sig = tuple(round(float(v), 6) for row in mw for v in row)
    v_cnt = len(mesh.vertices)
    p_cnt = len(mesh.polygons)

    if (
        _live_bvh_cache["bvh"] is not None
        and _live_bvh_cache["object_name"] == obj.name
        and _live_bvh_cache["matrix_sig"] == mat_sig
        and _live_bvh_cache["vert_count"] == v_cnt
        and _live_bvh_cache["poly_count"] == p_cnt
    ):
        return _live_bvh_cache["bvh"]

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.transform(mw)
    bm.normal_update()
    bvh = BVHTree.FromBMesh(bm)
    bm.free()

    _live_bvh_cache = {
        "object_name": obj.name,
        "matrix_sig": mat_sig,
        "vert_count": v_cnt,
        "poly_count": p_cnt,
        "bvh": bvh,
    }
    return bvh


def project_point_to_live_surface(
    world_point: Tuple[float, float, float],
    max_distance: float = 1e6,
    surface_offset: float = 0.0,
) -> Dict[str, Any]:
    """Project `world_point` strictly onto the designated `Make Live` surface via BVHTree."""
    from mathutils import Vector

    live_obj = get_live_surface_object()
    if live_obj is None:
        pt = tuple(float(c) for c in world_point)
        return {
            "ok": False,
            "projected": False,
            "location": pt,
            "normal": (0.0, 0.0, 1.0),
            "face_index": -1,
            "distance": 0.0,
            "live_object": "",
        }

    bvh = _get_or_build_live_bvh(live_obj)
    if bvh is None:
        pt = tuple(float(c) for c in world_point)
        return {
            "ok": False,
            "projected": False,
            "location": pt,
            "normal": (0.0, 0.0, 1.0),
            "face_index": -1,
            "distance": 0.0,
            "live_object": live_obj.name,
        }

    q = Vector((float(world_point[0]), float(world_point[1]), float(world_point[2])))
    loc, nrm, face_idx, dist = bvh.find_nearest(q, float(max_distance))
    if loc is None:
        return {
            "ok": False,
            "projected": False,
            "location": (q.x, q.y, q.z),
            "normal": (0.0, 0.0, 1.0),
            "face_index": -1,
            "distance": -1.0,
            "live_object": live_obj.name,
        }

    normal_vec = nrm.normalized() if nrm.length > 1e-8 else Vector((0.0, 0.0, 1.0))
    final_loc = loc + normal_vec * float(surface_offset)
    return {
        "ok": True,
        "projected": True,
        "location": (float(final_loc.x), float(final_loc.y), float(final_loc.z)),
        "normal": (float(normal_vec.x), float(normal_vec.y), float(normal_vec.z)),
        "face_index": int(face_idx) if face_idx is not None else -1,
        "distance": float(dist) if dist is not None else 0.0,
        "live_object": live_obj.name,
    }


def raycast_live_surface(
    ray_origin: Tuple[float, float, float],
    ray_direction: Tuple[float, float, float],
    max_distance: float = 1e6,
    surface_offset: float = 0.0,
) -> Dict[str, Any]:
    """Cast a ray `(ray_origin, ray_direction)` directly against the designated `Make Live` BVHTree."""
    from mathutils import Vector

    origin = Vector((float(ray_origin[0]), float(ray_origin[1]), float(ray_origin[2])))
    direction = Vector((float(ray_direction[0]), float(ray_direction[1]), float(ray_direction[2]))).normalized()

    live_obj = get_live_surface_object()
    if live_obj is not None:
        bvh = _get_or_build_live_bvh(live_obj)
        if bvh is not None:
            loc, nrm, face_idx, dist = bvh.ray_cast(origin, direction, float(max_distance))
            if loc is not None:
                normal_vec = nrm.normalized() if nrm and nrm.length > 1e-8 else Vector((0.0, 0.0, 1.0))
                final_loc = loc + normal_vec * float(surface_offset)
                return {
                    "ok": True,
                    "hit": True,
                    "location": (float(final_loc.x), float(final_loc.y), float(final_loc.z)),
                    "normal": (float(normal_vec.x), float(normal_vec.y), float(normal_vec.z)),
                    "face_index": int(face_idx) if face_idx is not None else -1,
                    "distance": float(dist) if dist is not None else 0.0,
                    "live_object": live_obj.name,
                }
            # Fallback if ray narrowly misses silhouette: project closest point to ray
            fallback_pt = origin + direction * 4.0
            return project_point_to_live_surface(
                (fallback_pt.x, fallback_pt.y, fallback_pt.z),
                max_distance=max_distance,
                surface_offset=surface_offset,
            )

    # No Make Live surface: try scene ray_cast against visible meshes
    try:
        import bpy
        depsgraph = bpy.context.evaluated_depsgraph_get()
        hit, loc, nrm, face_idx, hit_obj, _mat = bpy.context.scene.ray_cast(
            depsgraph, origin, direction, distance=float(max_distance)
        )
        if hit and loc is not None:
            normal_vec = nrm.normalized() if nrm and nrm.length > 1e-8 else Vector((0.0, 0.0, 1.0))
            final_loc = loc + normal_vec * float(surface_offset)
            return {
                "ok": True,
                "hit": True,
                "location": (float(final_loc.x), float(final_loc.y), float(final_loc.z)),
                "normal": (float(normal_vec.x), float(normal_vec.y), float(normal_vec.z)),
                "face_index": int(face_idx) if face_idx is not None else -1,
                "distance": float((loc - origin).length),
                "live_object": hit_obj.name if hit_obj is not None else "",
            }
    except Exception:
        pass

    fallback_pt = origin + direction * 4.0
    return {
        "ok": False,
        "hit": False,
        "location": (float(fallback_pt.x), float(fallback_pt.y), float(fallback_pt.z)),
        "normal": (0.0, 0.0, 1.0),
        "face_index": -1,
        "distance": 4.0,
        "live_object": "",
    }


def project_mesh_to_live_surface(
    target_obj_or_name: Any = None,
    selected_only: bool = False,
    surface_offset: float = 0.0,
) -> Dict[str, Any]:
    """Project vertices of `target_obj_or_name` strictly onto the designated `Make Live` surface."""
    import bmesh
    import bpy
    from mathutils import Vector

    live_obj = get_live_surface_object()
    if live_obj is None:
        return {"ok": False, "error": "No Make Live surface is currently active."}

    if target_obj_or_name is None:
        target_obj = getattr(bpy.context.view_layer.objects, "active", None)
    else:
        target_obj = _resolve_mesh_object(target_obj_or_name)

    if target_obj is None or getattr(target_obj, "type", "") != "MESH":
        return {"ok": False, "error": "Target object for live projection must be a MESH."}
    if target_obj.name == live_obj.name:
        return {"ok": False, "error": "Cannot project the Make Live surface onto itself."}

    bvh = _get_or_build_live_bvh(live_obj)
    if bvh is None:
        return {"ok": False, "error": "Could not build BVHTree for Make Live surface."}

    mw = target_obj.matrix_world
    mw_inv = mw.inverted_safe()
    projected_count = 0
    max_deviation = 0.0

    if target_obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(target_obj.data)
        bm.verts.ensure_lookup_table()
        verts = [v for v in bm.verts if (v.select or not selected_only)]
        for v in verts:
            w_pt = mw @ v.co
            loc, nrm, _idx, _dist = bvh.find_nearest(w_pt)
            if loc is not None:
                n_vec = nrm.normalized() if nrm and nrm.length > 1e-8 else Vector((0.0, 0.0, 1.0))
                snapped_w = loc + n_vec * float(surface_offset)
                v.co = mw_inv @ snapped_w
                projected_count += 1
                _, _, _, post_dist = bvh.find_nearest(mw @ v.co)
                if post_dist is not None:
                    max_deviation = max(max_deviation, float(post_dist))
        bm.normal_update()
        bmesh.update_edit_mesh(target_obj.data, loop_triangles=True, destructive=False)
    else:
        mesh = target_obj.data
        verts = [v for v in mesh.vertices if (v.select or not selected_only)]
        for v in verts:
            w_pt = mw @ v.co
            loc, nrm, _idx, _dist = bvh.find_nearest(w_pt)
            if loc is not None:
                n_vec = nrm.normalized() if nrm and nrm.length > 1e-8 else Vector((0.0, 0.0, 1.0))
                snapped_w = loc + n_vec * float(surface_offset)
                v.co = mw_inv @ snapped_w
                projected_count += 1
                _, _, _, post_dist = bvh.find_nearest(mw @ v.co)
                if post_dist is not None:
                    max_deviation = max(max_deviation, float(post_dist))
        mesh.update()

    return {
        "ok": True,
        "target_object": target_obj.name,
        "live_object": live_obj.name,
        "projected_vertex_count": projected_count,
        "max_surface_deviation": max_deviation,
    }
