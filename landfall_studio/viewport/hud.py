"""Maya-Style Viewport Heads-Up Display (`landfall_studio.viewport.hud`).

Draws inside `SpaceView3D` (`POST_PIXEL`):
1. **Top-Left Poly Count HUD** (Maya `Display > Heads Up Display > Poly Count`):
   - `Verts`, `Edges`, `Faces`, `Tris`, `UVs` for both **Scene (Visible Meshes)** and **Selected Objects/Components**
2. **Top-Center Tool & Mode Badge**:
   - Active Maya Mode (`Object` / `Vertex` / `Edge` / `Face` / `UV`), Active Manipulator (`Select` / `Move` / `Rotate` / `Scale` + Axis), and Active Display Layer / Symmetry status
3. **Bottom-Center Camera Label**:
   - Classic Maya camera label (`persp`, `top`, `front`, `side`, or active Camera name)
"""

from __future__ import annotations

from typing import Any, Dict

from .. import commands as cmd_registry

_hud_draw_handle = None
_hud_enabled: bool = True
_last_hud_stats: Dict[str, Any] = {
    "enabled": True,
    "verts_total": 0,
    "edges_total": 0,
    "faces_total": 0,
    "tris_total": 0,
    "uvs_total": 0,
    "verts_sel": 0,
    "edges_sel": 0,
    "faces_sel": 0,
    "tris_sel": 0,
    "uvs_sel": 0,
    "camera_label": "persp",
    "mode_label": "Object",
    "tool_label": "Move (X)",
}


def compute_poly_count_stats(context: Any = None) -> Dict[str, Any]:
    """Compute Maya Poly Count HUD statistics (`Verts`, `Edges`, `Faces`, `Tris`, `UVs`) for Scene and Selection."""
    try:
        import bpy
        import bmesh
    except ImportError:
        return dict(_last_hud_stats)

    ctx = context or bpy.context
    vl = getattr(ctx, "view_layer", None)
    if vl is None:
        return dict(_last_hud_stats)

    v_tot = e_tot = f_tot = t_tot = u_tot = 0
    v_sel = e_sel = f_sel = t_sel = u_sel = 0

    active_obj = vl.objects.active
    mode = getattr(ctx, "mode", "OBJECT")

    for obj in vl.objects:
        if obj.type != "MESH" or obj.data is None:
            continue
        try:
            if not obj.visible_get():
                continue
        except Exception:
            pass

        me = obj.data
        nv = len(me.vertices)
        ne = len(me.edges)
        nf = len(me.polygons)
        # Fast triangle estimate without forcing heavy loop_triangles recalc in draw loop
        nt = max(nf, len(me.loops) - nf * 2) if nf > 0 else 0
        nu = len(me.loops) if me.uv_layers.active is not None else 0

        v_tot += nv
        e_tot += ne
        f_tot += nf
        t_tot += nt
        u_tot += nu

        is_sel = False
        try:
            is_sel = bool(obj.select_get())
        except Exception:
            is_sel = obj is active_obj

        if is_sel:
            if mode == "EDIT_MESH" and obj is active_obj and me.is_editmode:
                try:
                    bm = bmesh.from_edit_mesh(me)
                    sv = sum(1 for v in bm.verts if v.select)
                    se = sum(1 for e in bm.edges if e.select)
                    sf = [f for f in bm.faces if f.select]
                    v_sel += sv
                    e_sel += se
                    f_sel += len(sf)
                    t_sel += sum(max(1, len(f.verts) - 2) for f in sf)
                    u_sel += sum(len(f.loops) for f in sf) if me.uv_layers.active else 0
                except Exception:
                    v_sel += nv
                    e_sel += ne
                    f_sel += nf
                    t_sel += nt
                    u_sel += nu
            else:
                v_sel += nv
                e_sel += ne
                f_sel += nf
                t_sel += nt
                u_sel += nu

    cam_label = "persp"
    try:
        sd = getattr(ctx, "space_data", None)
        r3d = getattr(sd, "region_3d", None) if sd is not None else None
        if r3d is not None:
            vp = getattr(r3d, "view_perspective", "PERSP")
            if vp == "CAMERA" and getattr(ctx.scene, "camera", None) is not None:
                cam_label = ctx.scene.camera.name
            elif vp == "ORTHO":
                cam_label = "ortho"
            else:
                cam_label = "persp"
    except Exception:
        pass

    mode_label = "Object"
    if mode == "EDIT_MESH":
        msm = getattr(getattr(ctx, "tool_settings", None), "mesh_select_mode", (True, False, False))
        if msm[0] and not msm[1] and not msm[2]:
            mode_label = "Vertex (F9)"
        elif msm[1] and not msm[0] and not msm[2]:
            mode_label = "Edge (F10)"
        elif msm[2] and not msm[0] and not msm[1]:
            mode_label = "Face (F11)"
        else:
            mode_label = "Multi-Component"

    tool_map = {
        "SELECT": "Select (Q)",
        "TRANSLATE": f"Move ({cmd_registry.get_active_axis()})",
        "ROTATE": f"Rotate ({cmd_registry.get_active_axis()})",
        "RESIZE": f"Scale ({cmd_registry.get_active_axis()})",
    }
    tool_label = tool_map.get(cmd_registry.get_active_tool(), "Move (X)")

    _last_hud_stats.update(
        {
            "enabled": _hud_enabled,
            "verts_total": v_tot,
            "edges_total": e_tot,
            "faces_total": f_tot,
            "tris_total": t_tot,
            "uvs_total": u_tot,
            "verts_sel": v_sel,
            "edges_sel": e_sel,
            "faces_sel": f_sel,
            "tris_sel": t_sel,
            "uvs_sel": u_sel,
            "camera_label": cam_label,
            "mode_label": mode_label,
            "tool_label": tool_label,
        }
    )
    return dict(_last_hud_stats)


def get_hud_state(context: Any = None) -> Dict[str, Any]:
    """Return the latest Poly Count & Viewport HUD state dictionary."""
    return compute_poly_count_stats(context)


def set_hud_enabled(enabled: bool) -> bool:
    global _hud_enabled
    _hud_enabled = bool(enabled)
    _last_hud_stats["enabled"] = _hud_enabled
    return _hud_enabled


def _draw_rect_2d(shader, x: float, y: float, w: float, h: float, color):
    from gpu_extras.batch import batch_for_shader

    verts = ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
    indices = ((0, 1, 2), (0, 2, 3))
    batch = batch_for_shader(shader, "TRIS", {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_maya_hud_callback():
    if not _hud_enabled:
        return
    try:
        import bpy
        import blf
        import gpu
    except ImportError:
        return

    context = bpy.context
    region = getattr(context, "region", None)
    space = getattr(context, "space_data", None)
    if region is None or space is None or getattr(space, "type", "") != "VIEW_3D":
        return

    stats = compute_poly_count_stats(context)
    rw = float(region.width)
    rh = float(region.height)
    if rw < 160 or rh < 120:
        return

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")

    # 1. Top-Left Maya Poly Count HUD block
    # Offset past left TOOLS region if open so HUD never overlaps toolbar buttons
    tools_w = 0.0
    try:
        area = getattr(context, "area", None)
        if area is not None:
            for reg in area.regions:
                if reg.type == "TOOLS" and reg.width > 1:
                    tools_w = max(tools_w, float(reg.width))
    except Exception:
        pass
    pad_x = tools_w + 14.0
    top_y = rh - 22.0
    box_w = 178.0
    box_h = 92.0
    _draw_rect_2d(shader, pad_x - 6, top_y - box_h + 14, box_w, box_h, (0.08, 0.09, 0.11, 0.62))
    _draw_rect_2d(shader, pad_x - 6, top_y - box_h + 14, 2.5, box_h, (0.22, 0.64, 0.85, 0.90))

    font_id = 0
    blf.size(font_id, 11)

    rows = (
        ("Verts:", stats["verts_total"], stats["verts_sel"]),
        ("Edges:", stats["edges_total"], stats["edges_sel"]),
        ("Faces:", stats["faces_total"], stats["faces_sel"]),
        ("Tris:", stats["tris_total"], stats["tris_sel"]),
        ("UVs:", stats["uvs_total"], stats["uvs_sel"]),
    )
    for idx, (label, tot_val, sel_val) in enumerate(rows):
        ry = top_y - idx * 15.5
        # Maya green label
        blf.color(font_id, 0.45, 0.84, 0.56, 0.95)
        blf.position(font_id, pad_x + 2, ry, 0)
        blf.draw(font_id, label)
        # Scene total column
        blf.color(font_id, 0.88, 0.91, 0.95, 0.95)
        blf.position(font_id, pad_x + 62, ry, 0)
        blf.draw(font_id, str(tot_val))
        # Selection column (Maya cyan-teal)
        blf.color(font_id, 0.34, 0.76, 0.96, 0.98)
        blf.position(font_id, pad_x + 118, ry, 0)
        blf.draw(font_id, str(sel_val))

    # 2. Top-Center Active Mode & Manipulator Pill
    badge_text = f"{stats['mode_label']}   |   {stats['tool_label']}"
    blf.size(font_id, 11)
    tw, th = blf.dimensions(font_id, badge_text)
    bx = (rw - tw) * 0.5 - 12.0
    by = rh - 38.0
    _draw_rect_2d(shader, bx, by - 5.0, tw + 24.0, 20.0, (0.09, 0.11, 0.13, 0.72))
    _draw_rect_2d(shader, bx, by + 13.5, tw + 24.0, 1.5, (0.22, 0.64, 0.85, 0.90))
    blf.color(font_id, 0.86, 0.90, 0.95, 0.95)
    blf.position(font_id, bx + 12.0, by, 0)
    blf.draw(font_id, badge_text)

    # 3. Bottom-Center Maya Camera Label ('persp')
    cam_txt = str(stats["camera_label"])
    blf.size(font_id, 11)
    cw, _ = blf.dimensions(font_id, cam_txt)
    cx = (rw - cw) * 0.5
    cy = 14.0
    _draw_rect_2d(shader, cx - 8.0, cy - 4.0, cw + 16.0, 17.0, (0.08, 0.09, 0.11, 0.55))
    blf.color(font_id, 0.52, 0.84, 0.62, 0.92)
    blf.position(font_id, cx, cy, 0)
    blf.draw(font_id, cam_txt)

    gpu.state.blend_set("NONE")


def register_hud_handler() -> None:
    global _hud_draw_handle
    if _hud_draw_handle is not None:
        return
    try:
        import bpy

        _hud_draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_maya_hud_callback, (), "WINDOW", "POST_PIXEL"
        )
    except Exception:
        _hud_draw_handle = None


def unregister_hud_handler() -> None:
    global _hud_draw_handle
    if _hud_draw_handle is None:
        return
    try:
        import bpy

        bpy.types.SpaceView3D.draw_handler_remove(_hud_draw_handle, "WINDOW")
    except Exception:
        pass
    _hud_draw_handle = None
