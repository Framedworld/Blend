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

    # Query Modeling state (Make Live, In-Viewport Caddy, Quad Draw)
    live_name = ""
    live_active = False
    caddy_state: Dict[str, Any] = {"open": False}
    qd_state: Dict[str, Any] = {"active": False, "dots": []}
    try:
        from .. import modeling

        ls = modeling.get_live_surface_state()
        live_active = bool(ls.get("active"))
        live_name = str(ls.get("object_name") or "")
        caddy_state = modeling.get_active_caddy_state()
        qd_state = modeling.get_quad_draw_overlay_data()
    except Exception:
        pass

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
            "live_surface_active": live_active,
            "live_surface_name": live_name,
            "caddy_open": bool(caddy_state.get("open")),
            "caddy_tool_id": caddy_state.get("tool_id", ""),
            "caddy_node_title": caddy_state.get("node_title", ""),
            "caddy_values": dict(caddy_state.get("values", {})),
            "quad_draw_active": bool(qd_state.get("active")),
            "quad_draw_dot_count": len(qd_state.get("dots", [])),
        }
    )
    return dict(_last_hud_stats)


def get_hud_state(context: Any = None) -> Dict[str, Any]:
    """Return the latest Poly Count, Live Surface, Caddy, & Viewport HUD state dictionary."""
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


def _draw_border_2d(shader, x: float, y: float, w: float, h: float, thickness: float, color):
    _draw_rect_2d(shader, x, y + h - thickness, w, thickness, color)
    _draw_rect_2d(shader, x, y, w, thickness, color)
    _draw_rect_2d(shader, x, y, thickness, h, color)
    _draw_rect_2d(shader, x + w - thickness, y, thickness, h, color)


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
    tools_w = 0.0
    try:
        area = getattr(context, "area", None)
        if area is not None:
            for reg in area.regions:
                if reg.type == "TOOLS" and reg.width > 1:
                    tools_w = max(tools_w, float(reg.width))
    except Exception:
        pass
    pad_x = tools_w + 18.0
    top_y = rh - 50.0
    box_w = 178.0
    box_h = 92.0
    _draw_rect_2d(shader, pad_x - 6, top_y - box_h + 14, box_w, box_h, (0.08, 0.09, 0.11, 0.68))
    _draw_rect_2d(shader, pad_x - 6, top_y - box_h + 14, 2.5, box_h, (0.22, 0.64, 0.85, 0.92))

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
        blf.color(font_id, 0.45, 0.84, 0.56, 0.95)
        blf.position(font_id, pad_x + 2, ry, 0)
        blf.draw(font_id, label)
        blf.color(font_id, 0.88, 0.91, 0.95, 0.95)
        blf.position(font_id, pad_x + 62, ry, 0)
        blf.draw(font_id, str(tot_val))
        blf.color(font_id, 0.34, 0.76, 0.96, 0.98)
        blf.position(font_id, pad_x + 118, ry, 0)
        blf.draw(font_id, str(sel_val))

    # 2. Top-Center Active Mode & Manipulator Pill + Make Live Badge
    badge_text = f"{stats['mode_label']}   |   {stats['tool_label']}"
    if stats.get("quad_draw_active"):
        badge_text += "   |   Quad Draw"
    blf.size(font_id, 11)
    tw, th = blf.dimensions(font_id, badge_text)
    bx = (rw - tw) * 0.5 - 12.0
    by = rh - 38.0
    _draw_rect_2d(shader, bx, by - 5.0, tw + 24.0, 20.0, (0.09, 0.11, 0.13, 0.78))
    _draw_rect_2d(shader, bx, by + 13.5, tw + 24.0, 1.5, (0.22, 0.64, 0.85, 0.90))
    blf.color(font_id, 0.86, 0.90, 0.95, 0.95)
    blf.position(font_id, bx + 12.0, by, 0)
    blf.draw(font_id, badge_text)

    if stats.get("live_surface_active") and stats.get("live_surface_name"):
        live_txt = f"LIVE SURFACE: {stats['live_surface_name']}"
        blf.size(font_id, 10.5)
        lw, _ = blf.dimensions(font_id, live_txt)
        lx = (rw - lw) * 0.5 - 10.0
        ly = by - 24.0
        _draw_rect_2d(shader, lx, ly - 4.0, lw + 20.0, 18.0, (0.06, 0.22, 0.15, 0.86))
        _draw_border_2d(shader, lx, ly - 4.0, lw + 20.0, 18.0, 1.0, (0.22, 0.85, 0.52, 0.92))
        blf.color(font_id, 0.36, 0.95, 0.62, 1.0)
        blf.position(font_id, lx + 10.0, ly, 0)
        blf.draw(font_id, live_txt)

    # 3. Quad Draw Plotted Construction Dots in 3D Viewport
    try:
        from .. import modeling
        from bpy_extras.view3d_utils import location_3d_to_region_2d

        qd = modeling.get_quad_draw_overlay_data()
        r3d = getattr(space, "region_3d", None)
        dots = qd.get("dots", [])
        if r3d is not None and dots:
            for d_idx, pt_item in enumerate(dots):
                pt3 = pt_item["location"] if isinstance(pt_item, dict) else pt_item
                co2d = location_3d_to_region_2d(region, r3d, pt3)
                if co2d is not None:
                    dx, dy = float(co2d[0]), float(co2d[1])
                    # Outer dark halo + inner glowing cyan/emerald dot
                    _draw_rect_2d(shader, dx - 5.5, dy - 5.5, 11.0, 11.0, (0.04, 0.11, 0.15, 0.94))
                    _draw_rect_2d(shader, dx - 3.8, dy - 3.8, 7.6, 7.6, (0.18, 0.92, 0.72, 0.98))
                    blf.size(font_id, 9.5)
                    blf.color(font_id, 0.75, 0.98, 0.90, 0.98)
                    blf.position(font_id, dx + 7.5, dy - 3.0, 0)
                    blf.draw(font_id, f"v{d_idx + 1}")
    except Exception:
        pass

    # 4. Maya In-Viewport Heads-Up Caddy (polyExtrudeFace1 / polyBevel1 / polyBridgeEdge1 / polyConnectComponents1)
    try:
        from .. import modeling

        caddy = modeling.get_active_caddy_state()
        if caddy.get("open"):
            rows_list = caddy.get("rows", [])
            node_title = str(caddy.get("node_title") or caddy.get("tool") or "polyCaddy1")

            cw_box = 242.0
            row_h = 22.0
            header_h = 24.0
            footer_h = 18.0
            ch_box = header_h + len(rows_list) * row_h + footer_h + 8.0

            # Position in lower-right quadrant of viewport (just like Maya's floating In-View Editor caddy)
            cx_box = min(max(pad_x + 40.0, rw * 0.56), rw - cw_box - 22.0)
            cy_box = max(48.0, rh * 0.22)

            # Drop shadow & main card body
            _draw_rect_2d(shader, cx_box + 3.0, cy_box - 3.0, cw_box, ch_box, (0.02, 0.03, 0.04, 0.58))
            _draw_rect_2d(shader, cx_box, cy_box, cw_box, ch_box, (0.10, 0.115, 0.135, 0.94))
            _draw_border_2d(shader, cx_box, cy_box, cw_box, ch_box, 1.0, (0.28, 0.58, 0.82, 0.88))

            # Top header bar
            hy = cy_box + ch_box - header_h
            _draw_rect_2d(shader, cx_box, hy, cw_box, header_h, (0.15, 0.24, 0.34, 0.96))
            _draw_rect_2d(shader, cx_box, hy + header_h - 2.0, cw_box, 2.0, (0.26, 0.68, 0.94, 1.0))

            blf.size(font_id, 11)
            blf.color(font_id, 0.92, 0.96, 1.0, 1.0)
            blf.position(font_id, cx_box + 10.0, hy + 6.0, 0)
            blf.draw(font_id, node_title)

            obj_tag = str(caddy.get("object_name") or "")
            if obj_tag:
                blf.size(font_id, 9.5)
                otw, _ = blf.dimensions(font_id, obj_tag)
                blf.color(font_id, 0.56, 0.78, 0.94, 0.92)
                blf.position(font_id, cx_box + cw_box - otw - 8.0, hy + 6.5, 0)
                blf.draw(font_id, obj_tag)

            # Parameter rows with visual scrub bar
            for p_idx, rspec in enumerate(rows_list):
                py = hy - (p_idx + 1) * row_h - 2.0
                plabel = str(rspec.get("label", rspec.get("key", "")))
                ptype = str(rspec.get("type", "float"))
                pval = rspec.get("value", 0.0)
                fill_ratio = max(0.0, min(1.0, float(rspec.get("ratio", 0.0))))
                is_active = bool(rspec.get("active", p_idx == 0))

                if is_active:
                    _draw_rect_2d(shader, cx_box + 4.0, py, cw_box - 8.0, row_h - 2.0, (0.18, 0.32, 0.46, 0.65))
                    _draw_rect_2d(shader, cx_box + 4.0, py, 2.5, row_h - 2.0, (0.32, 0.78, 0.98, 1.0))
                else:
                    _draw_rect_2d(shader, cx_box + 4.0, py, cw_box - 8.0, row_h - 2.0, (0.08, 0.09, 0.11, 0.55))

                # Value fill bar on right half
                bar_x = cx_box + 122.0
                bar_w = cw_box - 130.0
                _draw_rect_2d(shader, bar_x, py + 2.0, bar_w, row_h - 6.0, (0.06, 0.07, 0.08, 0.85))
                if fill_ratio > 0.01:
                    _draw_rect_2d(
                        shader,
                        bar_x,
                        py + 2.0,
                        bar_w * fill_ratio,
                        row_h - 6.0,
                        (0.22, 0.58, 0.84, 0.58) if is_active else (0.18, 0.44, 0.64, 0.42),
                    )

                blf.size(font_id, 10.5)
                blf.color(font_id, 0.86, 0.90, 0.95, 0.98 if is_active else 0.85)
                blf.position(font_id, cx_box + 11.0, py + 5.0, 0)
                blf.draw(font_id, plabel)

                if ptype == "bool":
                    val_txt = "On" if pval else "Off"
                elif ptype == "int":
                    val_txt = str(int(round(float(pval))))
                else:
                    val_txt = f"{float(pval):.3f}"
                vw, _ = blf.dimensions(font_id, val_txt)
                blf.color(font_id, 0.42, 0.86, 1.0, 1.0) if is_active else blf.color(font_id, 0.82, 0.88, 0.94, 0.92)
                blf.position(font_id, bar_x + bar_w - vw - 6.0, py + 5.0, 0)
                blf.draw(font_id, val_txt)

            # Footer hint
            blf.size(font_id, 9.0)
            blf.color(font_id, 0.55, 0.64, 0.72, 0.88)
            blf.position(font_id, cx_box + 10.0, cy_box + 5.0, 0)
            blf.draw(font_id, "MMB Scrub  |  Up/Down Row  |  Enter Commit")
    except Exception:
        pass

    # 5. Bottom-Center Maya Camera Label ('persp')
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
