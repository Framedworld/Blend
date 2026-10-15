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

    font_id = 0

    # 0. Figma Make Top 26px Viewport Panel Menu Strip ("Panels  View  Shading  Lighting  Show  Renderer  Panels")
    strip_h = 26.0
    strip_y = rh - strip_h
    _draw_rect_2d(shader, 0.0, strip_y, rw, strip_h, (0.125, 0.14, 0.16, 0.94))
    _draw_rect_2d(shader, 0.0, strip_y, rw, 1.0, (0.07, 0.08, 0.09, 0.95))

    blf.size(font_id, 10.5)
    menu_x = 12.0
    for m_txt in ("Panels", "View", "Shading", "Lighting", "Show", "Renderer"):
        blf.color(font_id, 0.61, 0.65, 0.70, 0.95)
        blf.position(font_id, menu_x, strip_y + 8.0, 0)
        blf.draw(font_id, m_txt)
        mw, _ = blf.dimensions(font_id, m_txt)
        menu_x += mw + 14.0

    # Divider + Viewport Quick Toggles (Wireframe on Shaded | Textured | Use All Lights | Viewport 2.0)
    _draw_rect_2d(shader, menu_x - 4.0, strip_y + 5.0, 1.0, 16.0, (0.20, 0.23, 0.27, 0.95))
    menu_x += 6.0

    for b_txt, b_active in (
        ("Wire on Shaded", True),
        ("Textured [6]", True),
        ("All Lights [7]", False),
        ("X-Ray", False),
        ("Isolate", False),
    ):
        bw, _ = blf.dimensions(font_id, b_txt)
        pill_w = bw + 12.0
        if menu_x + pill_w < rw - 150.0:
            if b_active:
                _draw_rect_2d(shader, menu_x, strip_y + 4.0, pill_w, 18.0, (0.14, 0.24, 0.33, 0.92))
                _draw_border_2d(shader, menu_x, strip_y + 4.0, pill_w, 18.0, 1.0, (0.22, 0.64, 0.85, 0.88))
                blf.color(font_id, 0.56, 0.84, 0.98, 1.0)
            else:
                _draw_rect_2d(shader, menu_x, strip_y + 4.0, pill_w, 18.0, (0.10, 0.11, 0.13, 0.78))
                blf.color(font_id, 0.58, 0.63, 0.69, 0.90)
            blf.position(font_id, menu_x + 6.0, strip_y + 8.0, 0)
            blf.draw(font_id, b_txt)
            menu_x += pill_w + 5.0

    # Right-side Renderer badge ("Viewport 2.0 (DirectX 11 / OpenGL)")
    vp_badge = "Viewport 2.0  •  sRGB gamma"
    vpw, _ = blf.dimensions(font_id, vp_badge)
    if rw > 420.0:
        blf.color(font_id, 0.49, 0.54, 0.60, 0.92)
        blf.position(font_id, rw - vpw - 12.0, strip_y + 8.0, 0)
        blf.draw(font_id, vp_badge)

    # 1. Top-Left Figma Make Maya POLY COUNT HUD Card
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
    card_top_y = strip_y - 12.0
    box_w = 194.0
    box_h = 122.0
    card_bottom_y = card_top_y - box_h

    # Translucent dark-glass card (#15191DD8) + 1px border (#FFFFFF1A) + left accent bar
    _draw_rect_2d(shader, pad_x - 6.0, card_bottom_y, box_w, box_h, (0.082, 0.098, 0.114, 0.85))
    _draw_border_2d(shader, pad_x - 6.0, card_bottom_y, box_w, box_h, 1.0, (0.24, 0.28, 0.33, 0.72))
    _draw_rect_2d(shader, pad_x - 6.0, card_bottom_y, 2.5, box_h, (0.22, 0.64, 0.85, 0.95))

    # Card title: "POLY COUNT" (#7CC2E3) + column headers ("SCENE" | "SEL")
    blf.size(font_id, 9.5)
    blf.color(font_id, 0.486, 0.761, 0.890, 0.98)
    blf.position(font_id, pad_x + 4.0, card_top_y - 15.0, 0)
    blf.draw(font_id, "POLY COUNT")

    blf.size(font_id, 8.5)
    blf.color(font_id, 0.49, 0.53, 0.58, 0.90)
    blf.position(font_id, pad_x + 76.0, card_top_y - 15.0, 0)
    blf.draw(font_id, "SCENE")
    blf.position(font_id, pad_x + 134.0, card_top_y - 15.0, 0)
    blf.draw(font_id, "SEL")

    _draw_rect_2d(shader, pad_x, card_top_y - 20.0, box_w - 14.0, 1.0, (0.20, 0.23, 0.27, 0.75))

    blf.size(font_id, 10.5)
    rows = (
        ("Verts", stats["verts_total"], stats["verts_sel"]),
        ("Edges", stats["edges_total"], stats["edges_sel"]),
        ("Faces", stats["faces_total"], stats["faces_sel"]),
        ("Tris", stats["tris_total"], stats["tris_sel"]),
        ("UVs", stats["uvs_total"], stats["uvs_sel"]),
    )
    for idx, (label, tot_val, sel_val) in enumerate(rows):
        ry = card_top_y - 34.0 - idx * 14.5
        blf.color(font_id, 0.55, 0.60, 0.66, 0.95)
        blf.position(font_id, pad_x + 4.0, ry, 0)
        blf.draw(font_id, label)
        blf.color(font_id, 0.82, 0.86, 0.91, 0.96)
        blf.position(font_id, pad_x + 76.0, ry, 0)
        blf.draw(font_id, f"{int(tot_val):,}")
        blf.color(font_id, 0.41, 0.72, 0.86, 0.98)
        blf.position(font_id, pad_x + 134.0, ry, 0)
        blf.draw(font_id, f"{int(sel_val):,}")

    # Amber "Selected:" footer line inside Poly Count card
    _draw_rect_2d(shader, pad_x, card_bottom_y + 18.0, box_w - 14.0, 1.0, (0.20, 0.23, 0.27, 0.75))
    active_obj = getattr(getattr(context, "view_layer", None), "objects", None)
    active_name = active_obj.active.name if (active_obj and active_obj.active) else "None"
    blf.size(font_id, 9.5)
    blf.color(font_id, 0.90, 0.66, 0.29, 0.98)
    blf.position(font_id, pad_x + 4.0, card_bottom_y + 5.0, 0)
    blf.draw(font_id, f"Selected:  {active_name}")

    # 2. Top-Center Figma Make Live Surface / Active Mode Capsule
    live_active = bool(stats.get("live_surface_active"))
    live_name = str(stats.get("live_surface_name") or "")
    mode_upper = str(stats["mode_label"]).upper()
    if live_active and live_name:
        capsule_txt = f"●  LIVE SURFACE: {live_name}   •   {mode_upper}"
    else:
        capsule_txt = f"●  LIVE SURFACE   •   {mode_upper}   •   {stats['tool_label']}"
    if stats.get("quad_draw_active"):
        capsule_txt += "   •   QUAD DRAW"

    blf.size(font_id, 10.5)
    tw, _ = blf.dimensions(font_id, capsule_txt)
    bx = (rw - tw) * 0.5 - 14.0
    by = strip_y - 30.0
    _draw_rect_2d(shader, bx, by - 5.0, tw + 28.0, 22.0, (0.075, 0.145, 0.125, 0.90))
    _draw_border_2d(shader, bx, by - 5.0, tw + 28.0, 22.0, 1.0, (0.24, 0.65, 0.44, 0.85))
    blf.color(font_id, 0.49, 0.89, 0.66, 1.0)
    blf.position(font_id, bx + 14.0, by + 1.0, 0)
    blf.draw(font_id, capsule_txt)

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
                    _draw_rect_2d(shader, dx - 5.5, dy - 5.5, 11.0, 11.0, (0.04, 0.11, 0.15, 0.94))
                    _draw_rect_2d(shader, dx - 3.8, dy - 3.8, 7.6, 7.6, (0.18, 0.92, 0.72, 0.98))
                    blf.size(font_id, 9.5)
                    blf.color(font_id, 0.75, 0.98, 0.90, 0.98)
                    blf.position(font_id, dx + 7.5, dy - 3.0, 0)
                    blf.draw(font_id, f"v{d_idx + 1}")
    except Exception:
        pass

    # 4. Figma Make In-Viewport Floating Dark-Glass Caddy (polyBevel1 / polyExtrudeFace1 / polyBridgeEdge1 / polyConnectComponents1)
    try:
        from .. import modeling

        caddy = modeling.get_active_caddy_state()
        if caddy.get("open"):
            rows_list = caddy.get("rows", [])
            node_title = str(caddy.get("node_title") or caddy.get("tool") or "polyBevel1")

            cw_box = 274.0
            row_h = 24.0
            header_h = 26.0
            footer_h = 28.0
            ch_box = header_h + len(rows_list) * row_h + footer_h + 10.0

            cx_box = min(max(pad_x + 40.0, rw * 0.53), rw - cw_box - 22.0)
            cy_box = max(52.0, rh * 0.20)

            # Drop shadow & dark-glass card body (#25282DF0) + 1px border (#444A54)
            _draw_rect_2d(shader, cx_box + 4.0, cy_box - 4.0, cw_box, ch_box, (0.02, 0.03, 0.04, 0.65))
            _draw_rect_2d(shader, cx_box, cy_box, cw_box, ch_box, (0.145, 0.157, 0.176, 0.95))
            _draw_border_2d(shader, cx_box, cy_box, cw_box, ch_box, 1.0, (0.267, 0.290, 0.329, 0.95))

            # Top header bar (#343941 -> #2B2F36) + 2px top accent bar (#38A3D8)
            hy = cy_box + ch_box - header_h
            _draw_rect_2d(shader, cx_box, hy, cw_box, header_h, (0.19, 0.21, 0.245, 0.98))
            _draw_rect_2d(shader, cx_box, hy + header_h - 2.0, cw_box, 2.0, (0.22, 0.64, 0.85, 1.0))

            # Glowing cyan status dot + node_title ("polyBevel1")
            _draw_rect_2d(shader, cx_box + 10.0, hy + 9.0, 6.0, 6.0, (0.22, 0.64, 0.85, 1.0))
            blf.size(font_id, 11)
            blf.color(font_id, 0.95, 0.97, 1.0, 1.0)
            blf.position(font_id, cx_box + 22.0, hy + 7.0, 0)
            blf.draw(font_id, node_title)

            # Right-side header subtitle ("MMB Virtual Slider")
            sub_hdr = "MMB Scrub"
            blf.size(font_id, 9.0)
            shw, _ = blf.dimensions(font_id, sub_hdr)
            blf.color(font_id, 0.49, 0.54, 0.60, 0.95)
            blf.position(font_id, cx_box + cw_box - shw - 10.0, hy + 8.0, 0)
            blf.draw(font_id, sub_hdr)

            # Parameter rows: Label + Horizontal Scrub Track (#16181B) + Cyan Thumb (#69B8DC) + Numeric Box (#15171A)
            for p_idx, rspec in enumerate(rows_list):
                py = hy - (p_idx + 1) * row_h - 2.0
                plabel = str(rspec.get("label", rspec.get("key", "")))
                if len(plabel) > 16:
                    plabel = plabel[:16]
                ptype = str(rspec.get("type", "float"))
                pval = rspec.get("value", 0.0)
                fill_ratio = max(0.0, min(1.0, float(rspec.get("ratio", 0.0))))
                is_active = bool(rspec.get("active", p_idx == 0))

                if is_active:
                    _draw_rect_2d(shader, cx_box + 4.0, py, cw_box - 8.0, row_h - 2.0, (0.18, 0.27, 0.36, 0.55))
                    _draw_rect_2d(shader, cx_box + 4.0, py, 2.5, row_h - 2.0, (0.22, 0.64, 0.85, 1.0))

                blf.size(font_id, 10.0)
                blf.color(font_id, 0.86, 0.90, 0.95, 0.98 if is_active else 0.82)
                blf.position(font_id, cx_box + 11.0, py + 6.0, 0)
                blf.draw(font_id, plabel)

                # Horizontal Scrub Slider Track
                track_x = cx_box + 116.0
                track_w = 88.0
                track_y = py + 8.0
                track_h = 5.0
                _draw_rect_2d(shader, track_x, track_y, track_w, track_h, (0.086, 0.094, 0.106, 0.95))
                if fill_ratio > 0.01:
                    _draw_rect_2d(
                        shader,
                        track_x,
                        track_y,
                        track_w * fill_ratio,
                        track_h,
                        (0.22, 0.64, 0.85, 0.92),
                    )
                # Slider thumb handle (#69B8DC)
                thumb_x = track_x + track_w * fill_ratio - 3.0
                _draw_rect_2d(shader, thumb_x, track_y - 2.5, 6.0, track_h + 5.0, (0.41, 0.72, 0.86, 1.0))

                # Recessed Numeric Value Box (#15171A) on right
                num_x = cx_box + cw_box - 60.0
                num_w = 52.0
                _draw_rect_2d(shader, num_x, py + 3.0, num_w, row_h - 7.0, (0.082, 0.090, 0.102, 0.96))
                _draw_border_2d(
                    shader,
                    num_x,
                    py + 3.0,
                    num_w,
                    row_h - 7.0,
                    1.0,
                    (0.22, 0.64, 0.85, 0.90) if is_active else (0.19, 0.21, 0.25, 0.85),
                )

                if ptype == "bool":
                    val_txt = "On" if pval else "Off"
                elif ptype == "int":
                    val_txt = str(int(round(float(pval))))
                else:
                    val_txt = f"{float(pval):.2f}"
                blf.size(font_id, 9.5)
                vw, _ = blf.dimensions(font_id, val_txt)
                blf.color(font_id, 0.41, 0.72, 0.86, 1.0) if is_active else blf.color(font_id, 0.82, 0.87, 0.92, 0.95)
                blf.position(font_id, num_x + num_w - vw - 5.0, py + 6.0, 0)
                blf.draw(font_id, val_txt)

            # Bottom Figma Make Caddy Action Pill Buttons ("Auto Fit: ON" | "Chamfer: ON" | "Mitering: Auto")
            btn_y = cy_box + 6.0
            btn_x = cx_box + 8.0
            for pill_lbl, pill_on in (("Auto Fit: ON", False), ("Chamfer: ON", True), ("Mitering: Auto", False)):
                blf.size(font_id, 8.5)
                pw, _ = blf.dimensions(font_id, pill_lbl)
                pbox_w = pw + 12.0
                if pill_on:
                    _draw_rect_2d(shader, btn_x, btn_y, pbox_w, 17.0, (0.12, 0.24, 0.33, 0.95))
                    _draw_border_2d(shader, btn_x, btn_y, pbox_w, 17.0, 1.0, (0.22, 0.64, 0.85, 0.90))
                    blf.color(font_id, 0.41, 0.72, 0.86, 1.0)
                else:
                    _draw_rect_2d(shader, btn_x, btn_y, pbox_w, 17.0, (0.11, 0.125, 0.145, 0.92))
                    _draw_border_2d(shader, btn_x, btn_y, pbox_w, 17.0, 1.0, (0.21, 0.24, 0.28, 0.88))
                    blf.color(font_id, 0.62, 0.67, 0.72, 0.92)
                blf.position(font_id, btn_x + 6.0, btn_y + 4.5, 0)
                blf.draw(font_id, pill_lbl)
                btn_x += pbox_w + 5.0
    except Exception:
        pass

    # 5. Bottom-Center Figma Make Camera Pill ("persp  |  35mm")
    cam_base = str(stats["camera_label"])
    cam_txt = f"{cam_base}   |   35mm" if "mm" not in cam_base else cam_base
    blf.size(font_id, 10.5)
    cw, _ = blf.dimensions(font_id, cam_txt)
    cx = (rw - cw) * 0.5
    cy = 14.0
    _draw_rect_2d(shader, cx - 12.0, cy - 5.0, cw + 24.0, 19.0, (0.082, 0.098, 0.114, 0.78))
    _draw_border_2d(shader, cx - 12.0, cy - 5.0, cw + 24.0, 19.0, 1.0, (0.20, 0.23, 0.27, 0.75))
    blf.color(font_id, 0.64, 0.70, 0.76, 0.95)
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
