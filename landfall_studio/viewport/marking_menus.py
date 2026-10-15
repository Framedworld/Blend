"""Maya-style context-sensitive GPU Marking Menus for Landfall Studio (Phase 02).

Provides three distinct RMB marking menu modes:
- `COMPONENT` (`RMB`): Seamless Vertex / Edge / Face / Multi / UV / Object Mode with cursor raycast target selection, plus Display & Snap branches.
- `TOOL` (`Shift+RMB`): Context-sensitive modeling tools (Object mode: Primitives, Freeze/Center Pivot, Combine, Smooth; Edit mode: Extrude, Bevel, Loop Cut, Bridge, Connect, Merge/Weld, Knife).
- `CONVERT` (`Ctrl+RMB`): Component conversion (To Vertices, To Edges, To Faces, To Edge Loop, To Edge Ring, To Boundary/Perimeter, Grow/Shrink).

Supports both:
1. Gesture mode (`Press -> Drag -> Highlight -> Release RMB` executes the highlighted radial/list item).
2. Click-discovery mode (releasing `RMB` inside the center dead-zone keeps the menu open for click navigation).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import blf
import bpy
import gpu
from bpy.app.handlers import persistent
from gpu_extras.batch import batch_for_shader

from ..commands import registry as cmd_registry
from .interaction import find_view3d_area_region

MM_DIRS: Tuple[Tuple[int, int], ...] = (
    (-148, 0),    # 0: West
    (148, 0),     # 1: East
    (0, 98),      # 2: South
    (0, -98),     # 3: North
    (-110, -68),  # 4: North-West
    (110, -68),   # 5: North-East
    (-110, 68),   # 6: South-West
    (110, 68),    # 7: South-East
)

MM_LIST_TOP = 128
DEAD_ZONE_PX = 18.0

# Modern Maya Studio palette tokens for the GPU Marking Menu
COL_BG = (0.145, 0.16, 0.18, 0.94)
COL_PANEL = (0.12, 0.135, 0.155, 0.96)
COL_BRANCH = (0.18, 0.44, 0.58, 0.95)
COL_OPEN = (0.26, 0.62, 0.78, 1.0)
COL_HOT_FILL = (0.22, 0.60, 0.84, 1.0)
COL_HOT_EDGE = (0.85, 0.95, 1.0, 0.75)
COL_BORDER = (0.42, 0.48, 0.54, 0.45)
COL_LINE = (0.32, 0.72, 0.92, 0.85)
COL_TEXT = (0.92, 0.94, 0.96, 1.0)
COL_MUTED = (0.62, 0.66, 0.72, 0.85)

RADIAL_RING_DEFS: Dict[str, Tuple[Tuple[str, Optional[str], Optional[Dict[str, Any]], Optional[str]], ...]] = {
    "COMPONENT": (
        ("Vertex", "landfall_studio.component_mode", {"mode": "VERT"}, None),
        ("Multi", "landfall_studio.component_mode", {"mode": "MULTI"}, None),
        ("Face", "landfall_studio.component_mode", {"mode": "FACE"}, None),
        ("Edge", "landfall_studio.component_mode", {"mode": "EDGE"}, None),
        ("Display", None, None, "display"),
        ("Object Mode", "landfall_studio.component_mode", {"mode": "OBJECT"}, None),
        ("UV Mode", "landfall_studio.component_mode", {"mode": "UV"}, None),
        ("Snap", None, None, "snap"),
    ),
    "TOOL_OBJECT": (
        ("Poly Cube", "landfall_studio.btk_create_primitive", {"primitive_type": "CUBE"}, None),
        ("Poly Sphere", "landfall_studio.btk_create_primitive", {"primitive_type": "SPHERE"}, None),
        ("Poly Plane", "landfall_studio.btk_create_primitive", {"primitive_type": "PLANE"}, None),
        ("Poly Cylinder", "landfall_studio.btk_create_primitive", {"primitive_type": "CYLINDER"}, None),
        ("Center Pivot", "landfall_studio.center_pivot_guarded", {"mode": "CENTER"}, None),
        ("Freeze Xforms", "landfall_studio.freeze_transformations_guarded", {}, None),
        ("Make Live", "landfall_studio.make_live", {"toggle": True}, None),
        ("Quad Draw", "landfall_studio.quad_draw", {}, None),
    ),
    "TOOL_EDIT": (
        ("Extrude", "landfall_studio.modeling_caddy", {"tool_type": "EXTRUDE"}, None),
        ("Bevel", "landfall_studio.modeling_caddy", {"tool_type": "BEVEL"}, None),
        ("Bridge", "landfall_studio.modeling_caddy", {"tool_type": "BRIDGE"}, None),
        ("Connect", "landfall_studio.modeling_caddy", {"tool_type": "CONNECT"}, None),
        ("Target Weld", "landfall_studio.target_weld", {}, None),
        ("Quad Draw", "landfall_studio.quad_draw_modal", {}, None),
        ("Loop Cut", "mesh.loopcut_slide", {}, None),
        ("Merge Dist", "landfall.merge_by_distance", {}, None),
    ),
    "CONVERT": (
        ("To Vertices", "landfall_studio.convert_selection", {"target": "VERT"}, None),
        ("To Edge Loop", "landfall_studio.convert_selection", {"target": "EDGE_LOOP"}, None),
        ("To Faces", "landfall_studio.convert_selection", {"target": "FACE"}, None),
        ("To Edges", "landfall_studio.convert_selection", {"target": "EDGE"}, None),
        ("Grow Selection", "landfall_studio.convert_selection", {"target": "GROW"}, None),
        ("To Edge Ring", "landfall_studio.convert_selection", {"target": "EDGE_RING"}, None),
        ("Shrink Selection", "landfall_studio.convert_selection", {"target": "SHRINK"}, None),
        ("To Boundary", "landfall_studio.convert_selection", {"target": "BOUNDARY"}, None),
    ),
}

LIST_DEFS: Dict[str, Tuple[Tuple[str, str, Dict[str, Any]], ...]] = {
    "base_component_edit": (
        ("Select All (Ctrl+Shift+A)", "mesh.select_all", {"action": "SELECT"}),
        ("Select None", "mesh.select_all", {"action": "DESELECT"}),
        ("Select Inverse", "landfall.select_inverse", {}),
        ("Soft Selection (B)", "landfall_studio.soft_selection", {"action": "TOGGLE"}),
        ("Select Border Edges", "landfall.select_boundaries", {}),
        ("Grow Selection", "mesh.select_more", {}),
        ("Shrink Selection", "mesh.select_less", {}),
    ),
    "base_component_object": (
        ("Select All (Ctrl+Shift+A)", "object.select_all", {"action": "SELECT"}),
        ("Select None", "object.select_all", {"action": "DESELECT"}),
        ("Select Inverse", "landfall.select_inverse", {}),
        ("Soft Selection (B)", "landfall_studio.soft_selection", {"action": "TOGGLE"}),
        ("Geometry Nodes", "landfall_studio.native_bridge", {"target": "GEOMETRY_NODES"}),
        ("Sculpt Mode", "landfall_studio.native_bridge", {"target": "SCULPT_MODE"}),
        ("Grease Pencil", "landfall_studio.native_bridge", {"target": "GREASE_PENCIL"}),
        ("Frame Selected (F)", "landfall.frame_selected", {}),
        ("Frame All (A)", "landfall_studio.frame_all", {}),
    ),
    "tool_edit": (
        ("Inset Faces", "mesh.inset", {}),
        ("Subdivide", "mesh.subdivide", {}),
        ("Detach / Separate", "landfall.detach_separate", {}),
        ("Make Edge/Face (Shift+F)", "mesh.edge_face_add", {}),
        ("Grid Fill", "mesh.fill_grid", {}),
        ("Spin Edge", "mesh.edge_rotate", {}),
        ("Unwrap + Pack", "landfall_studio.uv_unwrap_pack", {}),
        ("Non-Def History", "landfall_studio.delete_non_deformer_history", {}),
    ),
    "tool_object": (
        ("Base Cage (1)", "landfall.smooth_preview", {"mode": "CAGE"}),
        ("Smooth + Cage (2)", "landfall.smooth_preview", {"mode": "BOTH"}),
        ("Smooth Only (3)", "landfall.smooth_preview", {"mode": "SMOOTH"}),
        ("Geometry Nodes", "landfall_studio.native_bridge", {"target": "GEOMETRY_NODES"}),
        ("Shader / Hypershade", "landfall_studio.native_bridge", {"target": "SHADER_EDITOR"}),
        ("Sculpt Mode", "landfall_studio.native_bridge", {"target": "SCULPT_MODE"}),
        ("Grease Pencil", "landfall_studio.native_bridge", {"target": "GREASE_PENCIL"}),
        ("Non-Def History", "landfall_studio.delete_non_deformer_history", {}),
        ("Scene Diagnostics", "landfall_studio.scene_diagnostics", {}),
        ("Repeat Last (G)", "landfall_studio.repeat_last_command", {}),
    ),
    "convert_list": (
        ("To Vertices", "landfall_studio.convert_selection", {"target": "VERT"}),
        ("To Edges", "landfall_studio.convert_selection", {"target": "EDGE"}),
        ("To Faces", "landfall_studio.convert_selection", {"target": "FACE"}),
        ("To Edge Loop", "landfall_studio.convert_selection", {"target": "EDGE_LOOP"}),
        ("To Edge Ring", "landfall_studio.convert_selection", {"target": "EDGE_RING"}),
        ("To Boundary Edges", "landfall_studio.convert_selection", {"target": "BOUNDARY"}),
    ),
    "display": (
        ("Wireframe (4)", "landfall_studio.viewport_shading", {"mode": "4"}),
        ("Smooth Shaded (5)", "landfall_studio.viewport_shading", {"mode": "5"}),
        ("Textured (6)", "landfall_studio.viewport_shading", {"mode": "6"}),
        ("Use All Lights (7)", "landfall_studio.viewport_shading", {"mode": "7"}),
        ("Wire on Shaded", "landfall_studio.viewport_shading", {"mode": "WIRE_ON_SHADED"}),
        ("X-Ray (Alt+Z)", "landfall_studio.viewport_shading", {"mode": "XRAY"}),
        ("Isolate Selected", "landfall.isolate", {}),
        ("Border Edges", "landfall.toggle_scene_flag", {"prop": "landfall_border_show"}),
    ),
    "snap": (
        ("Snap to Grid (X)", "landfall.set_snap", {"target": "INCREMENT"}),
        ("Snap to Edge (C)", "landfall.set_snap", {"target": "EDGE"}),
        ("Snap to Vertex (V)", "landfall.set_snap", {"target": "VERTEX"}),
        ("Snap to Face", "landfall.set_snap", {"target": "FACE"}),
        ("Snap to Edge Center", "landfall.set_snap", {"target": "EDGE_MIDPOINT"}),
        ("Snapping Off", "landfall.set_snap", {"target": "OFF"}),
    ),
}

_studio_mm: Dict[str, Any] = {
    "open": False,
    "handle": None,
    "menu_mode": "COMPONENT",
    "x": 0.0,
    "y": 0.0,
    "cursor_x": 0.0,
    "cursor_y": 0.0,
    "area": None,
    "region": None,
    "window": None,
    "list": "base_component_object",
    "anchor": None,
    "hot": None,
    "rects": [],
    "layout": None,
}


def get_marking_menu_state() -> Dict[str, Any]:
    """Return a clean diagnostic snapshot of the Studio Marking Menu state."""
    return {
        "open": bool(_studio_mm["open"]),
        "menu_mode": _studio_mm["menu_mode"],
        "list": _studio_mm["list"],
        "hot": _studio_mm["hot"],
        "origin": (_studio_mm["x"], _studio_mm["y"]),
        "cursor": (_studio_mm["cursor_x"], _studio_mm["cursor_y"]),
        "rect_count": len(_studio_mm["rects"]),
        "has_draw_handler": _studio_mm["handle"] is not None,
    }


def _ring_key_for_mode(context, menu_mode: str) -> str:
    if menu_mode == "TOOL":
        return "TOOL_EDIT" if context.mode == "EDIT_MESH" else "TOOL_OBJECT"
    if menu_mode == "CONVERT":
        return "CONVERT"
    return "COMPONENT"


def _base_list_for_mode(context, menu_mode: str) -> str:
    if menu_mode == "TOOL":
        return "tool_edit" if context.mode == "EDIT_MESH" else "tool_object"
    if menu_mode == "CONVERT":
        return "convert_list"
    return (
        "base_component_edit"
        if context.mode == "EDIT_MESH"
        else "base_component_object"
    )


def _text_w(font: int, size: float, text: str) -> float:
    blf.size(font, size)
    return blf.dimensions(font, text)[0]


MM_COMPASS_LABELS: Tuple[str, ...] = ("W", "E", "S", "N", "NW", "NE", "SW", "SE")

MM_HOTKEY_BADGES: Dict[str, str] = {
    "Vertex": "F9",
    "Edge": "F10",
    "Face": "F11",
    "UV Mode": "F12",
    "Object Mode": "F8",
    "Multi": "F8+",
    "Extrude": "Ctrl+E",
    "Bevel": "Ctrl+B",
    "Loop Cut": "Ctrl+R",
    "Target Weld": "Weld",
    "Quad Draw": "Live",
    "Make Live": "Magnet",
    "Center Pivot": "Hold D",
    "Freeze Xforms": "Freeze",
}


def _rects_batch(rects: List[Tuple[float, float, float, float]]):
    verts, tris = [], []
    for x, y, w, h in rects:
        n = len(verts)
        verts.extend(((x, y), (x + w, y), (x + w, y + h), (x, y + h)))
        tris.extend(((n, n + 1, n + 2), (n, n + 2, n + 3)))
    if not verts:
        return None
    try:
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        return batch_for_shader(shader, "TRIS", {"pos": verts}, indices=tris)
    except Exception:
        return None


def _thick_line_batch(x0: float, y0: float, x1: float, y1: float, thickness: float = 2.4):
    import math

    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy)
    if dist < 1e-3:
        return None
    nx, ny = -dy / dist * (thickness * 0.5), dx / dist * (thickness * 0.5)
    verts = (
        (x0 + nx, y0 + ny),
        (x0 - nx, y0 - ny),
        (x1 - nx, y1 - ny),
        (x1 + nx, y1 + ny),
    )
    try:
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        return batch_for_shader(shader, "TRIS", {"pos": verts}, indices=((0, 1, 2), (0, 2, 3)))
    except Exception:
        return None


def _ring_batch(cx: float, cy: float, radius: float, thickness: float = 2.0, segments: int = 36):
    import math

    r_in = max(1.0, radius - thickness * 0.5)
    r_out = radius + thickness * 0.5
    verts, indices = [], []
    v_idx = 0
    for i in range(segments):
        a0 = (2.0 * math.pi * i) / segments
        a1 = (2.0 * math.pi * (i + 1)) / segments
        c0, s0 = math.cos(a0), math.sin(a0)
        c1, s1 = math.cos(a1), math.sin(a1)
        verts.extend(
            (
                (cx + c0 * r_in, cy + s0 * r_in),
                (cx + c0 * r_out, cy + s0 * r_out),
                (cx + c1 * r_out, cy + s1 * r_out),
                (cx + c1 * r_in, cy + s1 * r_in),
            )
        )
        indices.append((v_idx, v_idx + 1, v_idx + 2))
        indices.append((v_idx, v_idx + 2, v_idx + 3))
        v_idx += 4
    try:
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        return batch_for_shader(shader, "TRIS", {"pos": verts}, indices=indices)
    except Exception:
        return None


def _split_row_badge(label: str) -> Tuple[str, str]:
    if "(" in label and label.endswith(")"):
        base, _, rest = label.rpartition("(")
        return base.strip(), rest[:-1].strip()
    return label, MM_HOTKEY_BADGES.get(label, "")


def _build_mm_layout(context) -> None:
    font = 0
    scale = getattr(context.preferences.system, "ui_scale", 1.0) or 1.0
    size = 11.5 * scale
    pad_x, pad_y, row_h = 11.0 * scale, 5.5 * scale, 24.0 * scale
    cx, cy = _studio_mm["x"], _studio_mm["y"]
    menu_mode = _studio_mm["menu_mode"]

    ring_key = _ring_key_for_mode(context, menu_mode)
    radial = RADIAL_RING_DEFS[ring_key]

    chips = []
    for index, (label, path, props, branch) in enumerate(radial):
        dx, dy = MM_DIRS[index]
        compass = MM_COMPASS_LABELS[index] if index < len(MM_COMPASS_LABELS) else ""
        hk_badge = MM_HOTKEY_BADGES.get(label, "▸" if branch else "")
        badge_extra = (_text_w(font, 9.0 * scale, hk_badge) + 14.0 * scale) if hk_badge else 0.0
        compass_extra = 22.0 * scale
        w = max(112.0 * scale, _text_w(font, size, label) + pad_x * 2 + compass_extra + badge_extra)
        x, y = cx + dx * scale, cy - dy * scale
        chips.append(
            {
                "key": ("radial", index),
                "label": label,
                "compass": compass,
                "hotkey": hk_badge,
                "cx": x,
                "cy": y,
                "branch": bool(branch),
                "branch_name": branch,
                "open": branch is not None and branch == _studio_mm["list"],
                "x": x - w * 0.5,
                "y": y - row_h * 0.5,
                "w": w,
                "h": row_h,
            }
        )

    if _studio_mm["list"] not in LIST_DEFS:
        _studio_mm["list"] = _base_list_for_mode(context, menu_mode)
    items = LIST_DEFS[_studio_mm["list"]]
    two = len(items) > 6
    half = (len(items) + 1) // 2 if two else len(items)
    border, gap = 6.0 * scale, 6.0 * scale
    col_w = max(168.0 * scale, max(_text_w(font, size, t) for t, _p, _k in items) + pad_x * 2 + 18.0 * scale)
    total_w = border * 2 + col_w * (2 if two else 1) + (gap if two else 0)
    list_header_h = 20.0 * scale
    total_h = border * 2 + half * row_h + list_header_h

    ax, ay = (
        _studio_mm["anchor"]
        if _studio_mm["anchor"]
        else (cx, cy - MM_LIST_TOP * scale)
    )
    left, top = ax - total_w * 0.5, ay

    rows = []
    for index, (label, _path, _props) in enumerate(items):
        column = 1 if (two and index >= half) else 0
        row = index - half if column else index
        clean_lbl, row_hk = _split_row_badge(label)
        rows.append(
            {
                "key": ("list", index),
                "label": clean_lbl,
                "hotkey": row_hk,
                "x": left + border + column * (col_w + gap),
                "y": top - list_header_h - border - (row + 1) * row_h,
                "w": col_w,
                "h": row_h - 1.0,
            }
        )

    header_titles = {
        "COMPONENT": "MAYA MARKING MENU  •  COMPONENT / OBJECT [RMB]",
        "TOOL": "MAYA MARKING MENU  •  MODELING TOOLS [Shift+RMB]",
        "CONVERT": "MAYA MARKING MENU  •  CONVERT SELECTION [Ctrl+RMB]",
    }
    header_text = header_titles.get(menu_mode, "MAYA MARKING MENU")
    header_w = _text_w(font, 10.5 * scale, header_text) + pad_x * 2.4
    header_rect = (cx - header_w * 0.5, cy + 128.0 * scale, header_w, 22.0 * scale)

    _studio_mm["rects"] = [
        (c["key"], c["x"], c["y"], c["w"], c["h"]) for c in chips
    ] + [(r["key"], r["x"], r["y"], r["w"], r["h"]) for r in rows]

    plain = [(c["x"], c["y"], c["w"], c["h"]) for c in chips if not c["branch"]]
    branchy = [
        (c["x"], c["y"], c["w"], c["h"])
        for c in chips
        if c["branch"] and not c["open"]
    ]
    opened = [(c["x"], c["y"], c["w"], c["h"]) for c in chips if c["open"]]
    accents = [(c["x"], c["y"], 2.5 * scale, c["h"]) for c in chips]
    px, py, pw, ph = (left, top - total_h, total_w, total_h)
    edge = max(1.0, scale)

    _studio_mm["layout"] = {
        "font": font,
        "size": size,
        "pad_x": pad_x,
        "pad_y": pad_y,
        "scale": scale,
        "chips": chips,
        "rows": rows,
        "header_text": header_text,
        "header_rect": header_rect,
        "list_header_rect": (px, top - list_header_h, pw, list_header_h),
        "panel": (px, py, pw, ph),
        "batch_plain": _rects_batch(plain),
        "batch_branch": _rects_batch(branchy),
        "batch_open": _rects_batch(opened),
        "batch_accents": _rects_batch(accents),
        "batch_header": _rects_batch([header_rect]),
        "batch_header_edge": _rects_batch(
            [(header_rect[0] - edge, header_rect[1] - edge, header_rect[2] + edge * 2, header_rect[3] + edge * 2)]
        ),
        "batch_border": _rects_batch(
            [(px - edge, py - edge, pw + edge * 2, ph + edge * 2)]
        ),
        "batch_panel": _rects_batch([(px, py, pw, ph)]),
        "batch_list_header": _rects_batch([(px, top - list_header_h, pw, list_header_h)]),
    }


def _studio_mm_draw() -> None:
    if not _studio_mm["open"]:
        return
    context = bpy.context
    region = getattr(context, "region", None)
    if region is None or getattr(region, "type", "") != "WINDOW":
        return
    target_area = _studio_mm.get("area")
    target_region = _studio_mm.get("region")
    if target_area is not None and getattr(context, "area", None) is not None and context.area != target_area:
        return
    if target_region is not None and region != target_region:
        return
    if _studio_mm.get("layout") is None:
        _build_mm_layout(context)

    lay = _studio_mm["layout"]
    font, size = lay["font"], lay["size"]
    pad_x, pad_y, scale = lay["pad_x"], lay["pad_y"], lay["scale"]
    hot = _studio_mm["hot"]

    gpu.state.blend_set("ALPHA")
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    shader.bind()

    def paint(batch, color):
        if batch is not None:
            shader.uniform_float("color", color)
            batch.draw(shader)

    cx, cy = _studio_mm["x"], _studio_mm["y"]
    mx, my = _studio_mm["cursor_x"], _studio_mm["cursor_y"]

    # 1. Subtle radial spoke guide lines from center ring to each radial chip
    for chip in lay["chips"]:
        spoke = _thick_line_batch(cx, cy, chip["cx"], chip["cy"], thickness=1.2 * scale)
        paint(spoke, (0.22, 0.34, 0.44, 0.35))

    # 2. Active directional connector line + origin target ring
    if (mx - cx) ** 2 + (my - cy) ** 2 > 16.0:
        conn = _thick_line_batch(cx, cy, mx, my, thickness=2.6 * scale)
        paint(conn, (0.24, 0.72, 0.96, 0.95))
    paint(_ring_batch(cx, cy, 13.0 * scale, thickness=2.0 * scale), (0.24, 0.70, 0.94, 0.92))
    paint(_rects_batch([(cx - 3.0 * scale, cy - 3.0 * scale, 6.0 * scale, 6.0 * scale)]), (0.48, 0.86, 1.0, 1.0))

    # 3. Header pill, Radial cards, and Secondary Branch Panel
    paint(lay["batch_header_edge"], (0.22, 0.64, 0.85, 0.85))
    paint(lay["batch_header"], (0.09, 0.11, 0.13, 0.95))
    paint(lay["batch_plain"], (0.11, 0.125, 0.145, 0.95))
    paint(lay["batch_branch"], (0.14, 0.28, 0.38, 0.96))
    paint(lay["batch_open"], (0.20, 0.48, 0.64, 0.98))
    paint(lay["batch_accents"], (0.22, 0.64, 0.85, 0.95))
    paint(lay["batch_border"], (0.24, 0.34, 0.44, 0.78))
    paint(lay["batch_panel"], (0.10, 0.115, 0.135, 0.96))
    paint(lay["batch_list_header"], (0.13, 0.16, 0.19, 0.98))

    # 4. Highlighted active item (card or row)
    if hot is not None:
        for item in lay["chips"] + lay["rows"]:
            if item["key"] == hot:
                x, y, w, h = item["x"], item["y"], item["w"], item["h"]
                g = max(1.5, 1.8 * scale)
                paint(_rects_batch([(x - g, y - g, w + g * 2, h + g * 2)]), (0.36, 0.78, 0.98, 0.95))
                paint(_rects_batch([(x, y, w, h)]), (0.14, 0.35, 0.47, 0.98))
                break

    # 5. Header text
    hx, hy, _hw, _hh = lay["header_rect"]
    blf.size(font, 10.0 * scale)
    blf.color(font, 0.49, 0.78, 0.92, 1.0)
    blf.position(font, hx + pad_x, hy + 5.5 * scale, 0)
    blf.draw(font, lay["header_text"])

    # List section header text
    lhx, lhy, _lhw, _lhh = lay["list_header_rect"]
    blf.size(font, 8.8 * scale)
    blf.color(font, 0.54, 0.62, 0.70, 0.92)
    blf.position(font, lhx + 8.0 * scale, lhy + 5.5 * scale, 0)
    blf.draw(font, f"QUICK ACTIONS  •  {str(_studio_mm['list']).upper()}")

    # 6. Radial Chip labels + Compass badges + Right-aligned Hotkey badges
    for chip in lay["chips"]:
        is_hot = chip["key"] == hot
        cx_box, cy_box, cw_box, ch_box = chip["x"], chip["y"], chip["w"], chip["h"]
        # Compass pill on left
        blf.size(font, 8.5 * scale)
        blf.color(font, 0.36, 0.76, 0.95, 0.95) if is_hot else blf.color(font, 0.48, 0.56, 0.64, 0.88)
        blf.position(font, cx_box + 7.0 * scale, cy_box + pad_y + 1.5 * scale, 0)
        blf.draw(font, chip["compass"])

        # Main label
        blf.size(font, size)
        blf.color(font, 0.98, 0.99, 1.0, 1.0) if is_hot else blf.color(font, *COL_TEXT)
        blf.position(font, cx_box + 26.0 * scale, cy_box + pad_y + 1.0 * scale, 0)
        blf.draw(font, chip["label"])

        # Right-aligned hotkey badge
        hk = chip.get("hotkey", "")
        if hk:
            blf.size(font, 8.5 * scale)
            hkw = _text_w(font, 8.5 * scale, hk)
            bx = cx_box + cw_box - hkw - 10.0 * scale
            by = cy_box + 3.5 * scale
            paint(_rects_batch([(bx - 4.0 * scale, by, hkw + 8.0 * scale, ch_box - 7.0 * scale)]), (0.08, 0.10, 0.12, 0.85))
            blf.color(font, 0.48, 0.82, 0.98, 0.98) if is_hot else blf.color(font, 0.58, 0.66, 0.74, 0.90)
            blf.position(font, bx, cy_box + pad_y + 1.5 * scale, 0)
            blf.draw(font, hk)

    # 7. Secondary Branch List rows + Right-aligned Hotkey badges
    for idx_r, row in enumerate(lay["rows"]):
        is_hot = row["key"] == hot
        if idx_r % 2 == 1 and not is_hot:
            paint(_rects_batch([(row["x"], row["y"], row["w"], row["h"])]), (0.115, 0.13, 0.15, 0.65))
        blf.size(font, 10.5 * scale)
        blf.color(font, 0.98, 0.99, 1.0, 1.0) if is_hot else blf.color(font, 0.86, 0.90, 0.94, 0.96)
        blf.position(font, row["x"] + 8.0 * scale, row["y"] + pad_y, 0)
        blf.draw(font, row["label"])
        rhk = row.get("hotkey", "")
        if rhk:
            blf.size(font, 8.5 * scale)
            rhkw = _text_w(font, 8.5 * scale, rhk)
            blf.color(font, 0.45, 0.78, 0.95, 0.95) if is_hot else blf.color(font, 0.52, 0.58, 0.65, 0.88)
            blf.position(font, row["x"] + row["w"] - rhkw - 8.0 * scale, row["y"] + pad_y + 0.5 * scale, 0)
            blf.draw(font, rhk)

    gpu.state.blend_set("NONE")


def _studio_mm_hit(mx: float, my: float) -> Optional[Tuple[str, int]]:
    for key, x, y, w, h in _studio_mm["rects"]:
        if x <= mx <= x + w and y <= my <= y + h:
            return key
    # Directional wedge fallback if cursor is dragged outside the dead-zone
    cx, cy = _studio_mm["x"], _studio_mm["y"]
    dx, dy = mx - cx, cy - my
    if dx * dx + dy * dy >= (DEAD_ZONE_PX * 1.6) ** 2 and dy < MM_LIST_TOP * 0.85:
        best_idx = 0
        best_dot = -1e9
        for idx, (rx, ry) in enumerate(MM_DIRS):
            length = (rx * rx + ry * ry) ** 0.5 or 1.0
            dot = (dx * rx + dy * ry) / length
            if dot > best_dot:
                best_dot = dot
                best_idx = idx
        return ("radial", best_idx)
    return None


def stop_studio_marking_menu() -> None:
    """Remove the active Studio Marking Menu draw handler and clear state."""
    handle = _studio_mm.get("handle")
    if handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
        except Exception:
            pass
    _studio_mm["handle"] = None
    _studio_mm["open"] = False
    _studio_mm["rects"] = []
    _studio_mm["hot"] = None
    _studio_mm["layout"] = None


@persistent
def _on_load_post_close_mm(*_args) -> None:
    stop_studio_marking_menu()


def _dispatch_mm_action(
    label: str,
    path: str,
    props: Optional[Dict[str, Any]],
    area,
    region,
    origin_x: float,
    origin_y: float,
) -> bool:
    """Execute a marking menu item and record it in the Studio command registry."""
    if not path:
        return False
    call_props = dict(props or {})
    if path == "landfall_studio.component_mode" and call_props.get("mode") in (
        "VERT",
        "EDGE",
        "FACE",
        "MULTI",
        "UV",
    ):
        call_props.setdefault("raycast_x", int(origin_x))
        call_props.setdefault("raycast_y", int(origin_y))

    mod_name, _, op_name = path.partition(".")
    op_mod = getattr(bpy.ops, mod_name, None)
    op_fn = getattr(op_mod, op_name, None) if op_mod is not None else None
    if op_fn is None:
        return False

    def _exec_op(**kw):
        try:
            if area is not None and region is not None:
                with bpy.context.temp_override(area=area, region=region):
                    return op_fn("EXEC_DEFAULT", **kw)
            return op_fn("EXEC_DEFAULT", **kw)
        except Exception:
            if area is not None and region is not None:
                with bpy.context.temp_override(area=area, region=region):
                    return op_fn("INVOKE_DEFAULT", **kw)
            return op_fn("INVOKE_DEFAULT", **kw)

    try:
        _exec_op(**call_props)
        repeatable = path not in (
            "landfall_studio.component_mode",
            "landfall.frame_selected",
            "landfall_studio.frame_all",
            "landfall_studio.repeat_last_command",
        )
        if repeatable:
            cmd_registry.record_command(
                cmd_id=path,
                kwargs=call_props,
                callable_fn=lambda **kw: _exec_op(**kw),
                label=label,
                repeatable=True,
            )
        return True
    except Exception as exc:
        print(f"[landfall_studio] Marking menu command {path} failed: {exc}")
        return False


class LANDFALL_STUDIO_OT_marking_menu(bpy.types.Operator):
    """Context-sensitive Maya Marking Menu (`COMPONENT` on RMB, `TOOL` on Shift+RMB, `CONVERT` on Ctrl+RMB)."""

    bl_idname = "landfall_studio.marking_menu"
    bl_label = "Maya Marking Menu"
    bl_description = (
        "Open Maya-style radial + list marking menu (COMPONENT on RMB, "
        "TOOL on Shift+RMB, CONVERT on Ctrl+RMB)"
    )

    menu_mode: bpy.props.EnumProperty(
        name="Menu Mode",
        items=(
            ("COMPONENT", "Component / Object (RMB)", "Vertex, Edge, Face, Multi, UV, Object Mode"),
            ("TOOL", "Context Modeling Tools (Shift+RMB)", "Context-sensitive modeling and primitive tools"),
            ("CONVERT", "Convert Selection (Ctrl+RMB)", "Convert selection between vertices, edges, faces, loops, and boundaries"),
        ),
        default="COMPONENT",
        options={"SKIP_SAVE"},
    )
    select_radial_index: bpy.props.IntProperty(
        default=-1, options={"SKIP_SAVE", "HIDDEN"}
    )
    keep_open_for_capture: bpy.props.BoolProperty(
        default=False, options={"SKIP_SAVE", "HIDDEN"}
    )
    raycast_x: bpy.props.IntProperty(default=-1, options={"SKIP_SAVE", "HIDDEN"})
    raycast_y: bpy.props.IntProperty(default=-1, options={"SKIP_SAVE", "HIDDEN"})

    def _open_overlay(self, context, px: float, py: float):
        area, region = find_view3d_area_region(context)
        if area is None or region is None:
            return None, None
        stop_studio_marking_menu()
        _studio_mm.update(
            {
                "open": True,
                "menu_mode": self.menu_mode,
                "x": float(px),
                "y": float(py),
                "cursor_x": float(px),
                "cursor_y": float(py),
                "area": area,
                "region": region,
                "window": getattr(context, "window", None),
                "list": _base_list_for_mode(context, self.menu_mode),
                "anchor": None,
                "hot": None,
                "rects": [],
                "layout": None,
            }
        )
        _build_mm_layout(context)
        _studio_mm["handle"] = bpy.types.SpaceView3D.draw_handler_add(
            _studio_mm_draw, (), "WINDOW", "POST_PIXEL"
        )
        area.tag_redraw()
        return area, region

    def execute(self, context):
        """Programmatic execution path for automated GUI/headless verification."""
        area, region = find_view3d_area_region(context)
        px = float(self.raycast_x if self.raycast_x >= 0 else (region.width * 0.5 if region else 400))
        py = float(self.raycast_y if self.raycast_y >= 0 else (region.height * 0.5 if region else 300))

        self._open_overlay(context, px, py)

        if 0 <= self.select_radial_index < 8:
            _studio_mm["hot"] = ("radial", self.select_radial_index)
            dx, dy = MM_DIRS[self.select_radial_index]
            _studio_mm["cursor_x"] = px + dx
            _studio_mm["cursor_y"] = py - dy
            if not self.keep_open_for_capture:
                ring_key = _ring_key_for_mode(context, self.menu_mode)
                label, path, props, branch = RADIAL_RING_DEFS[ring_key][
                    self.select_radial_index
                ]
                stop_studio_marking_menu()
                if path:
                    _dispatch_mm_action(label, path, props, area, region, px, py)
                elif branch:
                    _studio_mm["list"] = branch
                return {"FINISHED"}

        if not self.keep_open_for_capture:
            stop_studio_marking_menu()
        return {"FINISHED"}

    def invoke(self, context, event):
        if _studio_mm["open"]:
            stop_studio_marking_menu()
            if context.area:
                context.area.tag_redraw()
            return {"CANCELLED"}

        if context.area is None or context.area.type != "VIEW_3D":
            return self.execute(context)

        px = float(event.mouse_region_x)
        py = float(event.mouse_region_y)
        self._open_overlay(context, px, py)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _close(self, context):
        stop_studio_marking_menu()
        if context.area:
            context.area.tag_redraw()

    def cancel(self, context):
        self._close(context)

    def _activate_hit(self, context, hit: Tuple[str, int]) -> bool:
        """Activate a radial chip or list row. Returns True if the menu should close."""
        kind, index = hit
        area, region = _studio_mm["area"], _studio_mm["region"]
        ox, oy = _studio_mm["x"], _studio_mm["y"]
        menu_mode = _studio_mm["menu_mode"]

        if kind == "radial":
            ring_key = _ring_key_for_mode(context, menu_mode)
            label, path, props, branch = RADIAL_RING_DEFS[ring_key][index]
            if branch:
                if _studio_mm["list"] == branch:
                    _studio_mm["list"] = _base_list_for_mode(context, menu_mode)
                    _studio_mm["anchor"] = None
                else:
                    scale = getattr(context.preferences.system, "ui_scale", 1.0) or 1.0
                    dx, dy = MM_DIRS[index]
                    _studio_mm["list"] = branch
                    _studio_mm["anchor"] = (
                        ox + dx * scale,
                        oy - dy * scale - 14.0 * scale,
                    )
                _studio_mm["layout"] = None
                if context.area:
                    context.area.tag_redraw()
                return False

            self._close(context)
            _dispatch_mm_action(label, path, props, area, region, ox, oy)
            return True

        label, path, props = LIST_DEFS[_studio_mm["list"]][index]
        self._close(context)
        _dispatch_mm_action(label, path, props, area, region, ox, oy)
        return True

    def modal(self, context, event):
        if not _studio_mm["open"]:
            return {"FINISHED"}

        if event.type == "MOUSEMOVE":
            mx, my = float(event.mouse_region_x), float(event.mouse_region_y)
            _studio_mm["cursor_x"] = mx
            _studio_mm["cursor_y"] = my
            hot = _studio_mm_hit(mx, my)
            if hot != _studio_mm["hot"]:
                _studio_mm["hot"] = hot
            if context.area:
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if event.type == "ESC" and event.value == "PRESS":
            self._close(context)
            return {"CANCELLED"}

        # Gesture completion: releasing RIGHTMOUSE outside the center dead-zone triggers the highlighted item
        if event.type == "RIGHTMOUSE" and event.value == "RELEASE":
            mx, my = float(event.mouse_region_x), float(event.mouse_region_y)
            dist_sq = (mx - _studio_mm["x"]) ** 2 + (my - _studio_mm["y"]) ** 2
            if dist_sq > DEAD_ZONE_PX**2:
                hit = _studio_mm_hit(mx, my)
                if hit is not None:
                    closed = self._activate_hit(context, hit)
                    if closed:
                        return {"FINISHED"}
                    return {"RUNNING_MODAL"}
                self._close(context)
                return {"CANCELLED"}
            # Quick tap inside dead-zone: keep menu open for click discovery
            return {"RUNNING_MODAL"}

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            mx, my = float(event.mouse_region_x), float(event.mouse_region_y)
            hit = _studio_mm_hit(mx, my)
            if hit is None:
                self._close(context)
                return {"CANCELLED"}
            closed = self._activate_hit(context, hit)
            return {"FINISHED"} if closed else {"RUNNING_MODAL"}

        return {"RUNNING_MODAL"}


MARKING_MENU_CLASSES = (LANDFALL_STUDIO_OT_marking_menu,)


def register_marking_menu_handlers() -> None:
    if _on_load_post_close_mm not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post_close_mm)


def unregister_marking_menu_handlers() -> None:
    stop_studio_marking_menu()
    if _on_load_post_close_mm in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post_close_mm)
