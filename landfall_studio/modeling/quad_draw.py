"""Real Modal & Programmatic `Quad Draw` Retopology Engine (`landfall_studio.modeling.quad_draw`).

Replaces the upstream `builtin.poly_build` stub with a Maya-style `Quad Draw` retopology workflow
that projects onto the scoped `Make Live` surface (`live_surface.py`):
- **Plot Dots (`LMB` / `plot_quad_draw_dot`):** Plots reference dots snapped to the `Make Live`
  surface (with surface normal stored).
- **`Shift` Quad Fill (`Shift+LMB` / `fill_quad_from_dots`):** Builds an oriented quad face from
  4 plotted dots (or boundary vertices + dots within `auto_weld_dist`), aligning the quad normal
  with the `Make Live` surface normal and welding shared boundary vertices automatically.
- **`Tab-Drag` Extrude Strip (`Tab+LMB` / `extrude_quad_draw_strip`):** Extrudes a boundary edge
  along a world-space delta vector and projects the new quad strip vertices onto the `Make Live`
  surface.
- **`Ctrl` Loop Cut (`Ctrl+LMB` / `insert_quad_draw_loop`):** Walks the connected quad ring across
  the target edge, inserts a new edge loop at `factor` (`0.0..1.0`), and projects all new loop
  vertices onto the `Make Live` surface.
- **`Shift-Drag` Relax (`Shift+Drag` / `relax_quad_draw_verts`):** Performs Laplacian / tangent
  relaxation across vertices while re-projecting onto the `Make Live` surface.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import commands as cmd_registry
from . import live_surface

_quad_draw_dots: List[Dict[str, Any]] = []
_quad_draw_active: bool = False
_quad_draw_retopo_object_name: str = ""
_quad_draw_auto_weld_dist: float = 0.08


def is_quad_draw_active() -> bool:
    return bool(_quad_draw_active)


def set_quad_draw_active(active: bool) -> None:
    global _quad_draw_active
    _quad_draw_active = bool(active)


def get_quad_draw_dots() -> List[Dict[str, Any]]:
    """Return a copy of the plotted Quad Draw reference dots."""
    return [dict(d) for d in _quad_draw_dots]


def clear_quad_draw_dots() -> Dict[str, Any]:
    """Clear all plotted Quad Draw dots."""
    global _quad_draw_dots
    count = len(_quad_draw_dots)
    _quad_draw_dots = []
    return {"ok": True, "cleared_count": count}


def ensure_retopo_mesh(target_obj_or_name: Any = None) -> Any:
    """Resolve or create the editable retopology mesh object for `Quad Draw`."""
    import bpy

    global _quad_draw_retopo_object_name
    live_obj = live_surface.get_live_surface_object()
    live_name = live_obj.name if live_obj is not None else ""

    if target_obj_or_name is not None:
        if isinstance(target_obj_or_name, str):
            cand = bpy.data.objects.get(target_obj_or_name)
        else:
            cand = target_obj_or_name
        if cand is not None and getattr(cand, "type", "") == "MESH" and cand.name != live_name:
            _quad_draw_retopo_object_name = cand.name
            return cand

    if _quad_draw_retopo_object_name:
        existing = bpy.data.objects.get(_quad_draw_retopo_object_name)
        if existing is not None and getattr(existing, "type", "") == "MESH" and existing.name != live_name:
            return existing

    base_name = f"{live_name}_Retopo" if live_name else "QuadDraw_Retopo"
    existing_retopo = bpy.data.objects.get(base_name)
    if existing_retopo is not None and getattr(existing_retopo, "type", "") == "MESH":
        _quad_draw_retopo_object_name = existing_retopo.name
        return existing_retopo

    active = getattr(bpy.context.view_layer.objects, "active", None)
    if (
        active is not None
        and getattr(active, "type", "") == "MESH"
        and active.name != live_name
        and (active.name.endswith("_Retopo") or len(active.data.polygons) == 0)
    ):
        _quad_draw_retopo_object_name = active.name
        return active

    # Create a new `<Live>_Retopo` or `QuadDraw_Retopo` mesh at world origin
    mesh = bpy.data.meshes.new(f"{base_name}Shape")
    obj = bpy.data.objects.new(base_name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.show_wire = True
    obj.show_all_edges = True
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    _quad_draw_retopo_object_name = obj.name
    return obj


def plot_quad_draw_dot(
    world_point: Sequence[float],
    project_to_live: bool = True,
    surface_offset: float = 0.0,
) -> Dict[str, Any]:
    """Plot a `Quad Draw` construction dot in world space, projected onto `Make Live` if active."""
    global _quad_draw_dots, _quad_draw_active
    _quad_draw_active = True

    pt = (float(world_point[0]), float(world_point[1]), float(world_point[2]))
    nrm = (0.0, 0.0, 1.0)
    live_name = ""

    if project_to_live and live_surface.get_live_surface_object() is not None:
        proj = live_surface.project_point_to_live_surface(pt, surface_offset=surface_offset)
        if proj.get("ok"):
            pt = proj["location"]
            nrm = proj["normal"]
            live_name = proj["live_object"]

    dot_entry = {
        "index": len(_quad_draw_dots),
        "location": pt,
        "normal": nrm,
        "live_object": live_name,
        "projected": bool(live_name),
    }
    _quad_draw_dots.append(dot_entry)
    return {
        "ok": True,
        "dot_index": dot_entry["index"],
        "location": pt,
        "normal": nrm,
        "live_object": live_name,
        "projected": bool(live_name),
        "total_dots": len(_quad_draw_dots),
    }


def _order_quad_points_in_tangent_plane(
    points: List[Tuple[float, float, float]],
    normals: List[Tuple[float, float, float]],
) -> Tuple[List[int], Tuple[float, float, float]]:
    """Order 4 3D points counter-clockwise in the tangent plane perpendicular to their average normal."""
    from mathutils import Vector

    vecs = [Vector(p) for p in points]
    center = (vecs[0] + vecs[1] + vecs[2] + vecs[3]) * 0.25

    avg_n = Vector((0.0, 0.0, 0.0))
    for n in normals:
        avg_n += Vector(n)
    if avg_n.length < 1e-6:
        # Derive normal from cross product
        avg_n = (vecs[1] - vecs[0]).cross(vecs[2] - vecs[0])
    if avg_n.length < 1e-6:
        avg_n = Vector((0.0, 0.0, 1.0))
    avg_n.normalize()

    # Build orthonormal tangent basis (t_u, t_v)
    up = Vector((0.0, 0.0, 1.0)) if abs(avg_n.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    t_u = avg_n.cross(up).normalized()
    t_v = avg_n.cross(t_u).normalized()

    angles = []
    for idx, v in enumerate(vecs):
        rel = v - center
        u = rel.dot(t_u)
        v_coord = rel.dot(t_v)
        ang = math.atan2(v_coord, u)
        angles.append((ang, idx))

    angles.sort(key=lambda item: item[0])
    ordered = [idx for _ang, idx in angles]

    # Verify winding vs avg_n
    p0, p1, p2 = vecs[ordered[0]], vecs[ordered[1]], vecs[ordered[2]]
    tri_n = (p1 - p0).cross(p2 - p0)
    if tri_n.dot(avg_n) < 0.0:
        ordered.reverse()

    return ordered, (float(avg_n.x), float(avg_n.y), float(avg_n.z))


def _get_or_create_bm_vert(bm: Any, local_co: Any, weld_dist: float):
    """Find an existing BMesh vertex within `weld_dist` of `local_co`, or create a new one."""
    best_v = None
    best_d = float(weld_dist)
    for v in bm.verts:
        d = (v.co - local_co).length
        if d <= best_d:
            best_d = d
            best_v = v
    if best_v is not None:
        return best_v, True
    return bm.verts.new(local_co), False


def fill_quad_from_dots(
    dot_indices: Optional[Sequence[int]] = None,
    target_obj_or_name: Any = None,
    auto_weld_dist: float = _quad_draw_auto_weld_dist,
    consume_dots: bool = False,
) -> Dict[str, Any]:
    """Create a topological quad face (`Shift+LMB` in Quad Draw) from 4 plotted dots."""
    import bmesh
    from mathutils import Vector

    global _quad_draw_dots, _quad_draw_active
    _quad_draw_active = True

    if len(_quad_draw_dots) < 4:
        return {
            "ok": False,
            "error": f"Quad Draw fill requires at least 4 plotted dots (found {len(_quad_draw_dots)}).",
        }

    if dot_indices is not None and not isinstance(dot_indices, (list, tuple)):
        if target_obj_or_name is None:
            target_obj_or_name = dot_indices
        dot_indices = None

    if dot_indices is not None and len(dot_indices) == 4:
        chosen_indices = [int(i) for i in dot_indices]
    else:
        # Use the most recently plotted 4 dots
        n = len(_quad_draw_dots)
        chosen_indices = [n - 4, n - 3, n - 2, n - 1]

    pts = [_quad_draw_dots[i]["location"] for i in chosen_indices]
    nrms = [_quad_draw_dots[i].get("normal", (0.0, 0.0, 1.0)) for i in chosen_indices]
    order, avg_normal = _order_quad_points_in_tangent_plane(pts, nrms)
    ordered_pts = [pts[i] for i in order]

    retopo_obj = ensure_retopo_mesh(target_obj_or_name)
    mw_inv = retopo_obj.matrix_world.inverted_safe()

    is_edit = retopo_obj.mode == "EDIT"
    bm = bmesh.from_edit_mesh(retopo_obj.data) if is_edit else bmesh.new()
    if not is_edit:
        bm.from_mesh(retopo_obj.data)

    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    quad_verts = []
    welded_count = 0
    for w_pt in ordered_pts:
        local_co = mw_inv @ Vector(w_pt)
        v, welded = _get_or_create_bm_vert(bm, local_co, auto_weld_dist)
        if welded:
            welded_count += 1
        quad_verts.append(v)

    # Guard duplicate vertices
    if len(set(quad_verts)) < 4:
        if not is_edit:
            bm.free()
        return {"ok": False, "error": "Plotted dots collapsed to fewer than 4 distinct vertices."}

    existing_face = bm.faces.get(quad_verts)
    if existing_face is None:
        face = bm.faces.new(quad_verts)
    else:
        face = existing_face

    bm.normal_update()
    # Ensure world-space face normal aligns with the Make Live surface normal
    world_face_n = (retopo_obj.matrix_world.to_3x3() @ face.normal).normalized()
    if world_face_n.dot(Vector(avg_normal)) < 0.0:
        face.normal_flip()
        bm.normal_update()

    for f in bm.faces:
        f.select = (f == face)

    if is_edit:
        bmesh.update_edit_mesh(retopo_obj.data, loop_triangles=True, destructive=True)
    else:
        bm.to_mesh(retopo_obj.data)
        bm.free()
        retopo_obj.data.update()

    if consume_dots:
        keep = [d for idx, d in enumerate(_quad_draw_dots) if idx not in set(chosen_indices)]
        for new_i, d in enumerate(keep):
            d["index"] = new_i
        _quad_draw_dots = keep

    cmd_registry.record_command(
        cmd_id="landfall_studio.quad_draw_fill",
        kwargs={"target_obj": retopo_obj.name},
        callable_fn=lambda: fill_quad_from_dots(target_obj_or_name=retopo_obj.name),
        label="Quad Draw: Fill Quad",
        repeatable=True,
    )

    vc = len(retopo_obj.data.vertices)
    fc = len(retopo_obj.data.polygons)
    return {
        "ok": True,
        "retopo_object": retopo_obj.name,
        "object_name": retopo_obj.name,
        "vertex_count": vc,
        "verts": vc,
        "face_count": fc,
        "faces": fc,
        "welded_vertices": welded_count,
        "face_normal_aligned": True,
    }


def extrude_quad_draw_strip(
    first_arg: Any = None,
    edge_index: Optional[int] = None,
    target_obj_or_name: Any = None,
    project_to_live: bool = True,
    delta_world: Sequence[float] = (0.4, 0.0, 0.0),
) -> Dict[str, Any]:
    """Extrude a boundary edge strip (`Tab + Drag` in Quad Draw) and snap to `Make Live`."""
    import bmesh
    from mathutils import Vector

    if first_arg is not None:
        if isinstance(first_arg, (tuple, list)) and len(first_arg) == 3:
            delta_world = first_arg
        elif target_obj_or_name is None:
            target_obj_or_name = first_arg

    retopo_obj = ensure_retopo_mesh(target_obj_or_name)
    mw = retopo_obj.matrix_world
    mw_inv = mw.inverted_safe()
    delta_v = Vector((float(delta_world[0]), float(delta_world[1]), float(delta_world[2])))

    is_edit = retopo_obj.mode == "EDIT"
    bm = bmesh.from_edit_mesh(retopo_obj.data) if is_edit else bmesh.new()
    if not is_edit:
        bm.from_mesh(retopo_obj.data)

    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    target_edge = None
    if edge_index is not None and 0 <= int(edge_index) < len(bm.edges):
        target_edge = bm.edges[int(edge_index)]
    else:
        # Prefer selected boundary edge, otherwise first boundary edge with best alignment to delta_v
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        sel_boundary = [e for e in boundary_edges if e.select]
        pool = sel_boundary if sel_boundary else boundary_edges
        if pool:
            target_edge = pool[0]

    if target_edge is None:
        if not is_edit:
            bm.free()
        return {"ok": False, "error": "No boundary edge available to extrude a Quad Draw strip."}

    v0, v1 = target_edge.verts[0], target_edge.verts[1]
    w0_new = (mw @ v0.co) + delta_v
    w1_new = (mw @ v1.co) + delta_v
    nrm_avg = Vector((0.0, 0.0, 1.0))

    if project_to_live and live_surface.get_live_surface_object() is not None:
        p0 = live_surface.project_point_to_live_surface((w0_new.x, w0_new.y, w0_new.z))
        p1 = live_surface.project_point_to_live_surface((w1_new.x, w1_new.y, w1_new.z))
        if p0.get("ok"):
            w0_new = Vector(p0["location"])
            nrm_avg = Vector(p0["normal"])
        if p1.get("ok"):
            w1_new = Vector(p1["location"])
            nrm_avg = (nrm_avg + Vector(p1["normal"])).normalized()

    nv0 = bm.verts.new(mw_inv @ w0_new)
    nv1 = bm.verts.new(mw_inv @ w1_new)
    new_face = bm.faces.new((v0, v1, nv1, nv0))
    bm.normal_update()

    # Align normal with adjacent face or live surface normal
    if target_edge.link_faces:
        adj_n = target_edge.link_faces[0].normal
        if new_face.normal.dot(adj_n) < 0.0:
            new_face.normal_flip()
    else:
        world_fn = (mw.to_3x3() @ new_face.normal).normalized()
        if world_fn.dot(nrm_avg) < 0.0:
            new_face.normal_flip()
    bm.normal_update()

    if is_edit:
        bmesh.update_edit_mesh(retopo_obj.data, loop_triangles=True, destructive=True)
    else:
        bm.to_mesh(retopo_obj.data)
        bm.free()
        retopo_obj.data.update()

    vc = len(retopo_obj.data.vertices)
    fc = len(retopo_obj.data.polygons)
    return {
        "ok": True,
        "retopo_object": retopo_obj.name,
        "object_name": retopo_obj.name,
        "vertex_count": vc,
        "verts": vc,
        "face_count": fc,
        "faces": fc,
    }


def insert_quad_draw_loop(
    first_arg: Any = None,
    factor: float = 0.5,
    target_obj_or_name: Any = None,
    project_to_live: bool = True,
    edge_index: int = 0,
    cuts: int = 1,
) -> Dict[str, Any]:
    """Insert an edge loop (`Ctrl + LMB` in Quad Draw) across the quad ring containing `edge_index`."""
    import bmesh
    from mathutils import Vector

    if first_arg is not None:
        if isinstance(first_arg, int):
            edge_index = first_arg
        elif target_obj_or_name is None:
            target_obj_or_name = first_arg

    retopo_obj = ensure_retopo_mesh(target_obj_or_name)
    mw = retopo_obj.matrix_world
    mw_inv = mw.inverted_safe()
    t_fac = max(0.05, min(0.95, float(factor)))

    is_edit = retopo_obj.mode == "EDIT"
    bm = bmesh.from_edit_mesh(retopo_obj.data) if is_edit else bmesh.new()
    if not is_edit:
        bm.from_mesh(retopo_obj.data)

    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    if not bm.edges:
        if not is_edit:
            bm.free()
        return {"ok": False, "error": "Mesh has no edges for loop cut."}

    idx = max(0, min(len(bm.edges) - 1, int(edge_index)))
    seed_edge = bm.edges[idx]

    # Collect parallel ring of edges across connected quad faces
    ring_edges = [seed_edge]
    visited_edges = {seed_edge}
    queue = [seed_edge]
    while queue:
        cur_e = queue.pop(0)
        for f in cur_e.link_faces:
            if len(f.edges) == 4:
                edges_list = list(f.edges)
                pos = edges_list.index(cur_e)
                opp_e = edges_list[(pos + 2) % 4]
                if opp_e not in visited_edges:
                    visited_edges.add(opp_e)
                    ring_edges.append(opp_e)
                    queue.append(opp_e)

    # Subdivide the parallel ring edges with cuts and use_grid_fill=True
    ret = bmesh.ops.subdivide_edges(
        bm,
        edges=ring_edges,
        cuts=max(1, int(cuts)),
        use_grid_fill=True,
        use_single_edge=True,
    )
    inner_verts = [ele for ele in ret.get("geom_inner", []) if isinstance(ele, bmesh.types.BMVert)]

    # Apply factor slide and project new loop vertices onto Make Live surface
    for v in inner_verts:
        if abs(t_fac - 0.5) > 1e-4:
            # Find connected original endpoints along the split edge
            link_verts = [e.other_vert(v) for e in v.link_edges if e.other_vert(v) not in inner_verts]
            if len(link_verts) == 2:
                v.co = link_verts[0].co.lerp(link_verts[1].co, t_fac)
        if project_to_live and live_surface.get_live_surface_object() is not None:
            w_pt = mw @ v.co
            proj = live_surface.project_point_to_live_surface((w_pt.x, w_pt.y, w_pt.z))
            if proj.get("ok"):
                v.co = mw_inv @ Vector(proj["location"])

    bm.normal_update()
    if is_edit:
        bmesh.update_edit_mesh(retopo_obj.data, loop_triangles=True, destructive=True)
    else:
        bm.to_mesh(retopo_obj.data)
        bm.free()
        retopo_obj.data.update()

    vc = len(retopo_obj.data.vertices)
    fc = len(retopo_obj.data.polygons)
    return {
        "ok": True,
        "retopo_object": retopo_obj.name,
        "object_name": retopo_obj.name,
        "ring_edge_count": len(ring_edges),
        "new_loop_vert_count": len(inner_verts),
        "vertex_count": vc,
        "verts": vc,
        "face_count": fc,
        "faces": fc,
    }


def relax_quad_draw_verts(
    target_obj_or_name: Any = None,
    iterations: int = 3,
    strength: float = 0.55,
    selected_only: bool = False,
    lock_boundary: bool = False,
    project_to_live: bool = True,
) -> Dict[str, Any]:
    """Relax vertices (`Shift + Drag` in Quad Draw) via Laplacian smoothing + `Make Live` re-projection."""
    import bmesh
    from mathutils import Vector

    retopo_obj = ensure_retopo_mesh(target_obj_or_name)
    mw = retopo_obj.matrix_world
    mw_inv = mw.inverted_safe()
    alpha = max(0.05, min(1.0, float(strength)))

    is_edit = retopo_obj.mode == "EDIT"
    bm = bmesh.from_edit_mesh(retopo_obj.data) if is_edit else bmesh.new()
    if not is_edit:
        bm.from_mesh(retopo_obj.data)

    bm.verts.ensure_lookup_table()
    target_verts = [
        v
        for v in bm.verts
        if (v.select or not selected_only) and (not lock_boundary or not v.is_boundary)
    ]

    for _ in range(max(1, int(iterations))):
        new_positions = {}
        for v in target_verts:
            neighbors = [e.other_vert(v) for e in v.link_edges]
            if not neighbors:
                continue
            avg_co = Vector((0.0, 0.0, 0.0))
            for nb in neighbors:
                avg_co += nb.co
            avg_co /= float(len(neighbors))
            blended = v.co.lerp(avg_co, alpha)

            if project_to_live and live_surface.get_live_surface_object() is not None:
                w_pt = mw @ blended
                proj = live_surface.project_point_to_live_surface((w_pt.x, w_pt.y, w_pt.z))
                if proj.get("ok"):
                    blended = mw_inv @ Vector(proj["location"])
            new_positions[v] = blended

        for v, co in new_positions.items():
            v.co = co

    bm.normal_update()

    # Measure max surface deviation after relax
    max_dev = 0.0
    if project_to_live and live_surface.get_live_surface_object() is not None:
        for v in bm.verts:
            w_pt = mw @ v.co
            proj = live_surface.project_point_to_live_surface((w_pt.x, w_pt.y, w_pt.z))
            if proj.get("ok"):
                max_dev = max(max_dev, float(proj["distance"]))

    if is_edit:
        bmesh.update_edit_mesh(retopo_obj.data, loop_triangles=True, destructive=False)
    else:
        bm.to_mesh(retopo_obj.data)
        bm.free()
        retopo_obj.data.update()

    return {
        "ok": True,
        "retopo_object": retopo_obj.name,
        "relaxed_vertex_count": len(target_verts),
        "max_surface_deviation": max_dev,
    }


def get_quad_draw_overlay_data() -> Dict[str, Any]:
    """Return current Quad Draw dots and retopo mesh info for the 3D Viewport HUD/overlay."""
    return {
        "active": bool(_quad_draw_active),
        "retopo_object": _quad_draw_retopo_object_name,
        "dots": list(_quad_draw_dots),
        "dot_count": len(_quad_draw_dots),
    }
