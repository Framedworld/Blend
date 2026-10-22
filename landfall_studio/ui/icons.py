"""Vector Icon Engine for the Modern Maya Studio Shell (`landfall_studio.ui.icons`).

Renders crisp anti-aliased multi-tone vector `QIcon` and `QPixmap` assets modeled on
Autodesk Maya's Shelf, Tool Box, Status Line, and Outliner DAG node iconography:
- Polygon Primitives: `poly_cube`, `poly_sphere`, `poly_cylinder`, `poly_plane`
- Mesh Modeling: `extrude`, `bevel`, `bridge`, `merge_verts`, `multi_cut`, `quad_draw`
- Pivot & History: `center_pivot`, `delete_history`, `freeze_transforms`, `bake_pivot`
- Subdiv & Viewport: `smooth_1`, `smooth_2`, `smooth_3`, `xray`, `wire_on_shaded`, `border_edges`, `isolate`, `quad_view`
- UV & Shading: `uv_unwrap`, `uv_seam`, `pbr_shader`, `normal_angle`
- Rigging & Pipeline: `joint_tool`, `mirror_joints`, `weight_hammer`, `blendshape`, `reference_mgr`, `workspace_ed`, `hierarchy_mgr`
- Tool Box (`Q/W/E/R/Y`): `tool_select`, `tool_lasso`, `tool_move`, `tool_rotate`, `tool_scale`, `tool_last`
- Status Line Magnets & Masks: `snap_grid`, `snap_curve`, `snap_point`, `snap_pivot`, `mask_obj`, `mask_vert`, `mask_edge`, `mask_face`, `mask_uv`
- Outliner DAG Nodes: `dag_transform`, `dag_mesh`, `dag_curve`, `dag_camera`, `dag_light`, `dag_armature`, `dag_modifier`, `dag_collection`
"""

from __future__ import annotations

from typing import Dict, Tuple

_ICON_CACHE: Dict[Tuple[str, int], object] = {}


def get_icon(name: str, size: int = 24):
    """Return a cached multi-tone anti-aliased `QIcon` for `name` at `size` px."""
    from qtpy import QtGui

    key = (name, int(size))
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    pix = render_svg_pixmap(name, size=size) if name in SVG_ICON_PATHS else render_pixmap(name, size=size)
    icon = QtGui.QIcon(pix)
    _ICON_CACHE[key] = icon
    return icon


# Stroke-style 24x24 icons for the Maya-order Status Line (scene, selection mode, editor toggles)
SVG_ICON_PATHS: Dict[str, str] = {
    "scene_new": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M12 12v6M9 15h6"/>',
    "scene_open": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "scene_save": '<path d="M5 3h11l3 3v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M7 3v5h8V3"/><path d="M7 21v-7h10v7"/>',
    "sel_hierarchy": '<rect x="9" y="3" width="6" height="5" rx="1"/><rect x="3" y="16" width="6" height="5" rx="1"/><rect x="15" y="16" width="6" height="5" rx="1"/><path d="M12 8v4M6 16v-4h12v4"/>',
    "sel_object": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
    "sel_component": '<circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M7 5h10M5 7v10M19 7v10M7 19h10"/>',
    "snap_plane": '<path d="M3 15l9-5 9 5-9 5z"/><path d="M12 10V3"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 3"/>',
    "render_frame": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="12" cy="12" r="3"/>',
    "panel_attr_editor": '<path d="M8 6h13M8 12h13M8 18h13M3 6h2M3 12h2M3 18h2"/>',
    "panel_tool_settings": '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    "panel_channel_box": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M10 4v16"/>',
    "panel_modifier_stack": '<rect x="4" y="3" width="16" height="5" rx="1"/><rect x="4" y="10" width="16" height="5" rx="1"/><rect x="4" y="17" width="16" height="4" rx="1"/>',
    "layout_single": '<rect x="3" y="4" width="18" height="16" rx="1.5"/>',
    "layout_four": '<rect x="3" y="4" width="18" height="16" rx="1.5"/><path d="M12 4v16M3 12h18"/>',
    "layout_outliner": '<rect x="3" y="4" width="18" height="16" rx="1.5"/><path d="M9 4v16"/>',
    "layout_graph": '<rect x="3" y="4" width="18" height="16" rx="1.5"/><path d="M3 14h18"/>',
}


def render_svg_pixmap(name: str, size: int = 24, color: str = "#C9CDD3"):
    """Render one of `SVG_ICON_PATHS` as a crisp stroke icon (falls back to the QPainter engine without QtSvg)."""
    from qtpy import QtCore, QtGui

    s = max(12, int(size))
    try:
        from qtpy import QtSvg
    except Exception:
        return render_pixmap(name, size=s)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{SVG_ICON_PATHS[name]}</svg>'
    )
    pix = QtGui.QPixmap(s, s)
    pix.fill(QtCore.Qt.transparent)
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8")))
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    renderer.render(p)
    p.end()
    return pix


def render_pixmap(name: str, size: int = 24):
    """Render a vector `QPixmap` for `name` using `QPainter` with Maya slate/teal/amber accents."""
    from qtpy import QtCore, QtGui

    s = max(12, int(size))
    pix = QtGui.QPixmap(s, s)
    pix.fill(QtCore.Qt.transparent)

    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)

    # Normalize drawing coordinate space to 24x24
    scale = s / 24.0
    p.scale(scale, scale)

    # Standard Maya-inspired palette
    c_slate = QtGui.QColor("#8C98A8")
    c_light = QtGui.QColor("#DCE3EC")
    c_dark = QtGui.QColor("#20242A")
    c_teal = QtGui.QColor("#38A3D8")
    c_teal_fill = QtGui.QColor(56, 163, 216, 150)
    c_amber = QtGui.QColor("#E5A33D")
    c_amber_fill = QtGui.QColor(229, 163, 61, 175)
    c_green = QtGui.QColor("#59B86E")
    c_red = QtGui.QColor("#E05A5A")
    c_blue = QtGui.QColor("#4F95E0")
    c_purple = QtGui.QColor("#9E7AE0")

    pen_light = QtGui.QPen(c_light, 1.4, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
    pen_teal = QtGui.QPen(c_teal, 1.6, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
    pen_amber = QtGui.QPen(c_amber, 1.6, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
    pen_dark = QtGui.QPen(c_dark, 1.2)

    key = (name or "").strip().lower()

    if key in ("poly_cube", "cube"):
        # Isometric 3D polygon cube (Maya orange/amber + slate shading)
        top = QtGui.QPolygonF([QtCore.QPointF(12, 3), QtCore.QPointF(20, 7.5), QtCore.QPointF(12, 12), QtCore.QPointF(4, 7.5)])
        left = QtGui.QPolygonF([QtCore.QPointF(4, 7.5), QtCore.QPointF(12, 12), QtCore.QPointF(12, 21), QtCore.QPointF(4, 16.5)])
        right = QtGui.QPolygonF([QtCore.QPointF(12, 12), QtCore.QPointF(20, 7.5), QtCore.QPointF(20, 16.5), QtCore.QPointF(12, 21)])
        p.setPen(pen_dark)
        p.setBrush(QtGui.QColor("#D89B48"))
        p.drawPolygon(top)
        p.setBrush(QtGui.QColor("#A8732A"))
        p.drawPolygon(left)
        p.setBrush(QtGui.QColor("#7D531B"))
        p.drawPolygon(right)
        p.setPen(QtGui.QPen(QtGui.QColor("#F4C87D"), 1.1))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawPolygon(top)

    elif key in ("poly_sphere", "sphere"):
        grad = QtGui.QRadialGradient(9, 8, 11)
        grad.setColorAt(0.0, QtGui.QColor("#F2C272"))
        grad.setColorAt(0.55, QtGui.QColor("#BA7E2D"))
        grad.setColorAt(1.0, QtGui.QColor("#5C3C12"))
        p.setPen(QtGui.QPen(QtGui.QColor("#F0C070"), 1.1))
        p.setBrush(grad)
        p.drawEllipse(QtCore.QRectF(3.5, 3.5, 17, 17))
        # Latitude/longitude wireframe arcs
        p.setPen(QtGui.QPen(QtGui.QColor(255, 235, 195, 130), 0.9))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawEllipse(QtCore.QRectF(3.5, 8.5, 17, 7))
        p.drawEllipse(QtCore.QRectF(8.5, 3.5, 7, 17))

    elif key in ("poly_cylinder", "cylinder"):
        p.setPen(QtGui.QPen(QtGui.QColor("#E6B363"), 1.1))
        p.setBrush(QtGui.QColor("#996826"))
        p.drawRect(QtCore.QRectF(5, 6.5, 14, 11.5))
        p.setBrush(QtGui.QColor("#7D531B"))
        p.drawEllipse(QtCore.QRectF(5, 15.2, 14, 5))
        p.setBrush(QtGui.QColor("#DCA04C"))
        p.drawEllipse(QtCore.QRectF(5, 4, 14, 5))

    elif key in ("poly_plane", "plane"):
        poly = QtGui.QPolygonF([QtCore.QPointF(12, 5), QtCore.QPointF(21, 11), QtCore.QPointF(12, 18), QtCore.QPointF(3, 11)])
        p.setPen(QtGui.QPen(QtGui.QColor("#F0C070"), 1.2))
        p.setBrush(QtGui.QColor("#AD782F"))
        p.drawPolygon(poly)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 235, 195, 140), 0.9))
        p.drawLine(QtCore.QPointF(7.5, 8), QtCore.QPointF(16.5, 14.5))
        p.drawLine(QtCore.QPointF(16.5, 8), QtCore.QPointF(7.5, 14.5))

    elif key == "extrude":
        # Base polygon + extruded highlighted top face + upward arrow
        base = QtGui.QPolygonF([QtCore.QPointF(4, 16), QtCore.QPointF(12, 20), QtCore.QPointF(20, 16), QtCore.QPointF(12, 12)])
        p.setPen(QtGui.QPen(c_slate, 1.1))
        p.setBrush(QtGui.QColor("#4B5360"))
        p.drawPolygon(base)
        top = QtGui.QPolygonF([QtCore.QPointF(6.5, 9.5), QtCore.QPointF(12, 12.5), QtCore.QPointF(17.5, 9.5), QtCore.QPointF(12, 6.5)])
        p.setPen(pen_amber)
        p.setBrush(c_amber_fill)
        p.drawPolygon(top)
        p.setPen(pen_teal)
        p.drawLine(QtCore.QPointF(12, 10), QtCore.QPointF(12, 2.5))
        p.drawLine(QtCore.QPointF(12, 2.5), QtCore.QPointF(9.2, 5.2))
        p.drawLine(QtCore.QPointF(12, 2.5), QtCore.QPointF(14.8, 5.2))

    elif key == "bevel":
        # Cube corner with amber chamfered bevel strip
        p.setPen(pen_light)
        p.setBrush(QtGui.QColor("#525B69"))
        p.drawRect(QtCore.QRectF(4, 8, 12, 12))
        chamfer = QtGui.QPolygonF([QtCore.QPointF(4, 8), QtCore.QPointF(10, 4), QtCore.QPointF(20, 4), QtCore.QPointF(16, 8)])
        p.setPen(pen_amber)
        p.setBrush(c_amber_fill)
        p.drawPolygon(chamfer)
        side = QtGui.QPolygonF([QtCore.QPointF(16, 8), QtCore.QPointF(20, 4), QtCore.QPointF(20, 15), QtCore.QPointF(16, 20)])
        p.setPen(pen_light)
        p.setBrush(QtGui.QColor("#3E4652"))
        p.drawPolygon(side)

    elif key == "bridge":
        p.setPen(pen_light)
        p.setBrush(QtGui.QColor("#4E5766"))
        p.drawRect(QtCore.QRectF(2.5, 6, 5.5, 12))
        p.drawRect(QtCore.QRectF(16, 6, 5.5, 12))
        p.setPen(pen_amber)
        p.setBrush(c_amber_fill)
        p.drawRect(QtCore.QRectF(8, 7.5, 8, 9))

    elif key == "merge_verts":
        p.setPen(QtGui.QPen(c_slate, 1.3))
        p.drawLine(QtCore.QPointF(4, 5), QtCore.QPointF(12, 12))
        p.drawLine(QtCore.QPointF(20, 5), QtCore.QPointF(12, 12))
        p.drawLine(QtCore.QPointF(4, 19), QtCore.QPointF(12, 12))
        p.drawLine(QtCore.QPointF(20, 19), QtCore.QPointF(12, 12))
        p.setBrush(c_teal)
        p.setPen(pen_dark)
        for pt in (QtCore.QPointF(4, 5), QtCore.QPointF(20, 5), QtCore.QPointF(4, 19), QtCore.QPointF(20, 19)):
            p.drawEllipse(pt, 2.2, 2.2)
        p.setBrush(c_amber)
        p.drawEllipse(QtCore.QPointF(12, 12), 3.6, 3.6)

    elif key in ("center_pivot", "snap_pivot"):
        p.setPen(QtGui.QPen(c_slate, 1.2, QtCore.Qt.DashLine))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRect(QtCore.QRectF(4, 4, 16, 16))
        p.setPen(QtGui.QPen(c_red, 1.8))
        p.drawLine(QtCore.QPointF(12, 12), QtCore.QPointF(19, 12))
        p.setPen(QtGui.QPen(c_green, 1.8))
        p.drawLine(QtCore.QPointF(12, 12), QtCore.QPointF(12, 5))
        p.setPen(QtGui.QPen(c_amber, 1.5))
        p.setBrush(c_amber)
        p.drawEllipse(QtCore.QPointF(12, 12), 2.8, 2.8)

    elif key == "delete_history":
        # Stack of construction nodes with lightning / clear badge
        p.setPen(QtGui.QPen(c_green, 1.3))
        p.setBrush(QtGui.QColor(89, 184, 110, 90))
        p.drawRect(QtCore.QRectF(3.5, 4, 12, 4.5))
        p.drawRect(QtCore.QRectF(3.5, 10, 12, 4.5))
        p.setPen(QtGui.QPen(c_red, 2.2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawLine(QtCore.QPointF(13, 13), QtCore.QPointF(20.5, 20.5))
        p.drawLine(QtCore.QPointF(20.5, 13), QtCore.QPointF(13, 20.5))

    elif key == "freeze_transforms":
        # Snowflake / zeroed axis crystal
        p.setPen(QtGui.QPen(QtGui.QColor("#66C8FF"), 1.7, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawLine(QtCore.QPointF(12, 3), QtCore.QPointF(12, 21))
        p.drawLine(QtCore.QPointF(4.2, 7.5), QtCore.QPointF(19.8, 16.5))
        p.drawLine(QtCore.QPointF(19.8, 7.5), QtCore.QPointF(4.2, 16.5))
        p.setBrush(QtGui.QColor("#38A3D8"))
        p.drawEllipse(QtCore.QPointF(12, 12), 2.6, 2.6)

    elif key in ("smooth_1", "smooth_2", "smooth_3"):
        lvl = key[-1]
        p.setPen(pen_teal if lvl != "1" else pen_light)
        p.setBrush(c_teal_fill if lvl == "3" else QtGui.QColor("#343B46"))
        if lvl == "1":
            p.drawRect(QtCore.QRectF(4.5, 4.5, 15, 15))
        elif lvl == "2":
            p.setPen(QtGui.QPen(c_slate, 1.1, QtCore.Qt.DashLine))
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawRect(QtCore.QRectF(3.5, 3.5, 17, 17))
            p.setPen(pen_teal)
            p.setBrush(c_teal_fill)
            p.drawEllipse(QtCore.QRectF(5, 5, 14, 14))
        else:
            p.drawEllipse(QtCore.QRectF(4, 4, 16, 16))
        font = p.font()
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QtGui.QColor("#FFFFFF"))
        p.drawText(QtCore.QRectF(0, 0, 24, 24), QtCore.Qt.AlignCenter, lvl)

    elif key == "xray":
        p.setPen(QtGui.QPen(c_teal, 1.3, QtCore.Qt.DashLine))
        p.setBrush(QtGui.QColor(56, 163, 216, 65))
        p.drawRect(QtCore.QRectF(4, 6, 11, 11))
        p.setPen(QtGui.QPen(c_light, 1.3))
        p.setBrush(QtGui.QColor(220, 227, 236, 95))
        p.drawRect(QtCore.QRectF(9, 9, 11, 11))

    elif key == "wire_on_shaded":
        p.setPen(pen_teal)
        p.setBrush(QtGui.QColor("#4C5666"))
        p.drawEllipse(QtCore.QRectF(3.5, 3.5, 17, 17))
        p.drawLine(QtCore.QPointF(3.5, 12), QtCore.QPointF(20.5, 12))
        p.drawLine(QtCore.QPointF(12, 3.5), QtCore.QPointF(12, 20.5))

    elif key == "border_edges":
        p.setPen(QtGui.QPen(c_slate, 1.0))
        p.setBrush(QtGui.QColor("#39414E"))
        p.drawRect(QtCore.QRectF(4, 4, 16, 16))
        p.setPen(QtGui.QPen(c_green, 2.4))
        p.drawRect(QtCore.QRectF(4, 4, 16, 16))

    elif key == "isolate":
        p.setPen(pen_amber)
        p.setBrush(c_amber_fill)
        p.drawEllipse(QtCore.QRectF(7, 7, 10, 10))
        p.setPen(QtGui.QPen(c_teal, 1.3))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRect(QtCore.QRectF(3, 3, 18, 18))

    elif key == "quad_view":
        p.setPen(pen_light)
        p.setBrush(QtGui.QColor("#2F3540"))
        p.drawRect(QtCore.QRectF(3, 3, 8, 8))
        p.drawRect(QtCore.QRectF(13, 3, 8, 8))
        p.drawRect(QtCore.QRectF(3, 13, 8, 8))
        p.setPen(pen_teal)
        p.setBrush(c_teal_fill)
        p.drawRect(QtCore.QRectF(13, 13, 8, 8))

    elif key in ("uv_unwrap", "mask_uv"):
        # Maya UV unfolded cross layout
        p.setPen(QtGui.QPen(c_green, 1.2))
        p.setBrush(QtGui.QColor(89, 184, 110, 110))
        for rx, ry in ((9, 3), (9, 8), (4, 8), (14, 8), (9, 13), (9, 18)):
            p.drawRect(QtCore.QRectF(rx, ry, 5, 5))

    elif key == "pbr_shader":
        grad = QtGui.QRadialGradient(9, 8, 11)
        grad.setColorAt(0.0, QtGui.QColor("#FFFFFF"))
        grad.setColorAt(0.35, QtGui.QColor("#58B8F0"))
        grad.setColorAt(1.0, QtGui.QColor("#1A3A54"))
        p.setPen(pen_teal)
        p.setBrush(grad)
        p.drawEllipse(QtCore.QRectF(3.5, 3.5, 17, 17))

    elif key in ("joint_tool", "dag_armature"):
        p.setPen(QtGui.QPen(c_teal, 1.8))
        p.drawLine(QtCore.QPointF(6, 18), QtCore.QPointF(18, 6))
        p.setBrush(c_amber)
        p.setPen(pen_dark)
        p.drawEllipse(QtCore.QPointF(6, 18), 3.2, 3.2)
        p.setBrush(c_teal)
        p.drawEllipse(QtCore.QPointF(18, 6), 2.8, 2.8)

    elif key in ("reference_mgr", "workspace_ed", "hierarchy_mgr"):
        p.setPen(pen_teal if key == "reference_mgr" else pen_amber)
        p.setBrush(c_teal_fill if key == "reference_mgr" else c_amber_fill)
        p.drawPolygon(
            QtGui.QPolygonF(
                [
                    QtCore.QPointF(3, 6),
                    QtCore.QPointF(10, 6),
                    QtCore.QPointF(12, 8.5),
                    QtCore.QPointF(21, 8.5),
                    QtCore.QPointF(21, 19),
                    QtCore.QPointF(3, 19),
                ]
            )
        )

    elif key == "tool_select":
        # Maya white/teal selection cursor arrow
        arrow = QtGui.QPolygonF(
            [
                QtCore.QPointF(6, 3),
                QtCore.QPointF(6, 18.5),
                QtCore.QPointF(10.2, 14.8),
                QtCore.QPointF(13.2, 20.5),
                QtCore.QPointF(15.6, 19.3),
                QtCore.QPointF(12.6, 13.6),
                QtCore.QPointF(18, 13.6),
            ]
        )
        p.setPen(pen_dark)
        p.setBrush(c_light)
        p.drawPolygon(arrow)

    elif key == "tool_lasso":
        path = QtGui.QPainterPath()
        path.moveTo(5, 8)
        path.cubicTo(5, 3, 19, 3, 19, 10)
        path.cubicTo(19, 17, 10, 18, 7, 15)
        path.closeSubpath()
        p.setPen(QtGui.QPen(c_teal, 1.6, QtCore.Qt.DashLine))
        p.setBrush(QtGui.QColor(56, 163, 216, 55))
        p.drawPath(path)

    elif key == "tool_move":
        # Classic RGB/Teal 3-axis move manipulator arrows
        p.setPen(QtGui.QPen(c_green, 2.0, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawLine(QtCore.QPointF(12, 13), QtCore.QPointF(12, 3.5))
        p.drawLine(QtCore.QPointF(12, 3.5), QtCore.QPointF(9.5, 6.5))
        p.drawLine(QtCore.QPointF(12, 3.5), QtCore.QPointF(14.5, 6.5))
        p.setPen(QtGui.QPen(c_red, 2.0, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawLine(QtCore.QPointF(12, 13), QtCore.QPointF(21, 13))
        p.drawLine(QtCore.QPointF(21, 13), QtCore.QPointF(18, 10.5))
        p.drawLine(QtCore.QPointF(21, 13), QtCore.QPointF(18, 15.5))
        p.setPen(QtGui.QPen(c_blue, 2.0, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawLine(QtCore.QPointF(12, 13), QtCore.QPointF(5, 19.5))
        p.setBrush(c_amber)
        p.setPen(pen_dark)
        p.drawRect(QtCore.QRectF(10, 11, 4, 4))

    elif key == "tool_rotate":
        p.setBrush(QtCore.Qt.NoBrush)
        p.setPen(QtGui.QPen(c_teal, 1.5))
        p.drawEllipse(QtCore.QRectF(3.5, 3.5, 17, 17))
        p.setPen(QtGui.QPen(c_red, 1.6))
        p.drawEllipse(QtCore.QRectF(3.5, 8.5, 17, 7))
        p.setPen(QtGui.QPen(c_green, 1.6))
        p.drawEllipse(QtCore.QRectF(8.5, 3.5, 7, 17))

    elif key == "tool_scale":
        p.setPen(QtGui.QPen(c_green, 1.8))
        p.drawLine(QtCore.QPointF(12, 13), QtCore.QPointF(12, 5))
        p.setBrush(c_green)
        p.drawRect(QtCore.QRectF(10, 3, 4, 4))
        p.setPen(QtGui.QPen(c_red, 1.8))
        p.drawLine(QtCore.QPointF(12, 13), QtCore.QPointF(20, 13))
        p.setBrush(c_red)
        p.drawRect(QtCore.QRectF(18, 11, 4, 4))
        p.setPen(QtGui.QPen(c_blue, 1.8))
        p.drawLine(QtCore.QPointF(12, 13), QtCore.QPointF(5.5, 19))
        p.setBrush(c_blue)
        p.drawRect(QtCore.QRectF(3.5, 17, 4, 4))
        p.setBrush(c_amber)
        p.setPen(pen_dark)
        p.drawRect(QtCore.QRectF(9.5, 10.5, 5, 5))

    elif key in ("snap_grid", "snap_curve", "snap_point"):
        # Maya horseshoe magnet + target indicator
        p.setPen(QtGui.QPen(c_teal, 2.2, QtCore.Qt.SolidLine, QtCore.Qt.FlatCap))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawArc(QtCore.QRectF(5, 4, 14, 13), 0, 180 * 16)
        p.drawLine(QtCore.QPointF(5, 10.5), QtCore.QPointF(5, 16))
        p.drawLine(QtCore.QPointF(19, 10.5), QtCore.QPointF(19, 16))
        p.setPen(QtGui.QPen(c_amber, 2.2))
        p.drawLine(QtCore.QPointF(5, 16.5), QtCore.QPointF(5, 19))
        p.drawLine(QtCore.QPointF(19, 16.5), QtCore.QPointF(19, 19))
        if key == "snap_grid":
            p.setPen(QtGui.QPen(c_light, 1.2))
            p.drawLine(QtCore.QPointF(9, 20), QtCore.QPointF(15, 20))
            p.drawLine(QtCore.QPointF(12, 17), QtCore.QPointF(12, 22))
        elif key == "snap_point":
            p.setBrush(c_amber)
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(QtCore.QPointF(12, 19.5), 2.5, 2.5)

    elif key in ("mask_obj", "dag_transform"):
        p.setPen(pen_teal)
        p.setBrush(c_teal_fill)
        p.drawRect(QtCore.QRectF(5, 5, 14, 14))
        p.setPen(QtGui.QPen(c_light, 1.3))
        p.drawLine(QtCore.QPointF(12, 7), QtCore.QPointF(12, 17))
        p.drawLine(QtCore.QPointF(7, 12), QtCore.QPointF(17, 12))

    elif key == "mask_vert":
        p.setPen(QtGui.QPen(c_slate, 1.2))
        p.drawRect(QtCore.QRectF(6, 6, 12, 12))
        p.setBrush(c_amber)
        p.setPen(pen_dark)
        for vx, vy in ((6, 6), (18, 6), (6, 18), (18, 18)):
            p.drawEllipse(QtCore.QPointF(vx, vy), 2.8, 2.8)

    elif key == "mask_edge":
        p.setPen(QtGui.QPen(c_slate, 1.2))
        p.drawRect(QtCore.QRectF(5, 5, 14, 14))
        p.setPen(QtGui.QPen(c_amber, 2.8))
        p.drawLine(QtCore.QPointF(5, 5), QtCore.QPointF(19, 5))
        p.drawLine(QtCore.QPointF(19, 5), QtCore.QPointF(19, 19))

    elif key in ("mask_face", "dag_mesh"):
        p.setPen(pen_amber if key == "mask_face" else pen_teal)
        p.setBrush(c_amber_fill if key == "mask_face" else c_teal_fill)
        p.drawRect(QtCore.QRectF(4.5, 4.5, 15, 15))
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 140), 1.0))
        p.drawLine(QtCore.QPointF(4.5, 12), QtCore.QPointF(19.5, 12))
        p.drawLine(QtCore.QPointF(12, 4.5), QtCore.QPointF(12, 19.5))

    elif key == "dag_camera":
        p.setPen(pen_light)
        p.setBrush(QtGui.QColor("#53687E"))
        p.drawRect(QtCore.QRectF(3.5, 7.5, 11.5, 9))
        lens = QtGui.QPolygonF([QtCore.QPointF(15, 10), QtCore.QPointF(20.5, 7), QtCore.QPointF(20.5, 17), QtCore.QPointF(15, 14)])
        p.setBrush(c_teal)
        p.drawPolygon(lens)

    elif key == "dag_light":
        p.setPen(pen_amber)
        p.setBrush(c_amber)
        p.drawEllipse(QtCore.QPointF(12, 12), 4.5, 4.5)
        for dx, dy in ((0, -8), (0, 8), (-8, 0), (8, 0), (-5.6, -5.6), (5.6, -5.6), (-5.6, 5.6), (5.6, 5.6)):
            p.drawLine(QtCore.QPointF(12 + dx * 0.65, 12 + dy * 0.65), QtCore.QPointF(12 + dx, 12 + dy))

    elif key == "dag_modifier":
        p.setPen(QtGui.QPen(c_green, 1.6))
        p.setBrush(QtGui.QColor(89, 184, 110, 120))
        p.drawRoundedRect(QtCore.QRectF(4.5, 5.5, 15, 13), 2.5, 2.5)
        p.setPen(QtGui.QPen(c_light, 1.4))
        p.drawLine(QtCore.QPointF(8, 12), QtCore.QPointF(16, 12))

    elif key == "dag_curve":
        path = QtGui.QPainterPath()
        path.moveTo(4, 18)
        path.cubicTo(6, 4, 18, 20, 20, 6)
        p.setPen(QtGui.QPen(c_purple, 2.0))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawPath(path)

    elif key == "quad_draw":
        # Maya Quad Draw icon: cyan/teal quad surface with 4 glowing green plotted corner dots
        quad = QtGui.QPolygonF([QtCore.QPointF(6, 6), QtCore.QPointF(18, 5), QtCore.QPointF(19, 18), QtCore.QPointF(5, 17)])
        p.setPen(pen_teal)
        p.setBrush(c_teal_fill)
        p.drawPolygon(quad)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 130), 1.0, QtCore.Qt.DashLine))
        p.drawLine(QtCore.QPointF(12, 5.5), QtCore.QPointF(12, 17.5))
        p.drawLine(QtCore.QPointF(5.5, 11.5), QtCore.QPointF(18.5, 11.5))
        p.setBrush(c_green)
        p.setPen(pen_dark)
        for pt in (QtCore.QPointF(6, 6), QtCore.QPointF(18, 5), QtCore.QPointF(19, 18), QtCore.QPointF(5, 17)):
            p.drawEllipse(pt, 2.7, 2.7)

    elif key == "target_weld":
        # Maya Target Weld icon: yellow source vert + dashed line + arrow to aqua target vert
        p.setPen(QtGui.QPen(c_light, 1.5, QtCore.Qt.DashLine))
        p.drawLine(QtCore.QPointF(6, 17), QtCore.QPointF(17, 7))
        p.setPen(QtGui.QPen(c_teal, 1.6))
        p.drawLine(QtCore.QPointF(17, 7), QtCore.QPointF(12.5, 7.5))
        p.drawLine(QtCore.QPointF(17, 7), QtCore.QPointF(16.5, 11.5))
        p.setBrush(c_amber)
        p.setPen(pen_dark)
        p.drawRect(QtCore.QRectF(3.5, 14.5, 5, 5))
        p.setBrush(c_teal)
        p.drawEllipse(QtCore.QPointF(17.5, 6.5), 3.3, 3.3)

    elif key == "make_live":
        # Maya Make Live magnet + emerald sphere badge
        p.setPen(QtGui.QPen(c_green, 2.2, QtCore.Qt.SolidLine, QtCore.Qt.FlatCap))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawArc(QtCore.QRectF(5, 4, 14, 13), 0, 180 * 16)
        p.drawLine(QtCore.QPointF(5, 10.5), QtCore.QPointF(5, 16))
        p.drawLine(QtCore.QPointF(19, 10.5), QtCore.QPointF(19, 16))
        p.setPen(QtGui.QPen(c_light, 2.2))
        p.drawLine(QtCore.QPointF(5, 16.5), QtCore.QPointF(5, 19))
        p.drawLine(QtCore.QPointF(19, 16.5), QtCore.QPointF(19, 19))
        p.setBrush(c_green)
        p.setPen(pen_dark)
        p.drawEllipse(QtCore.QPointF(12, 18.5), 3.2, 3.2)

    elif key == "connect":
        # Polygon quad with bright amber mid-edge connection cut
        p.setPen(pen_light)
        p.setBrush(QtGui.QColor("#3E4652"))
        p.drawRect(QtCore.QRectF(4, 5, 16, 14))
        p.setPen(QtGui.QPen(c_amber, 2.2))
        p.drawLine(QtCore.QPointF(4, 12), QtCore.QPointF(20, 12))
        p.setBrush(c_amber)
        p.setPen(pen_dark)
        p.drawEllipse(QtCore.QPointF(4, 12), 2.5, 2.5)
        p.drawEllipse(QtCore.QPointF(20, 12), 2.5, 2.5)

    elif key == "non_def_history":
        # Deformer bone preserved (green) + modeling history cleared (amber/teal)
        p.setPen(QtGui.QPen(c_green, 1.8))
        p.drawLine(QtCore.QPointF(5, 19), QtCore.QPointF(12, 12))
        p.setBrush(c_green)
        p.drawEllipse(QtCore.QPointF(5, 19), 2.5, 2.5)
        p.setPen(QtGui.QPen(c_amber, 1.6))
        p.setBrush(c_amber_fill)
        p.drawRect(QtCore.QRectF(11, 4, 9, 6))

    elif key == "texel_density":
        # 2x2 UV checker grid with teal/amber density squares
        p.setPen(pen_dark)
        p.setBrush(c_teal)
        p.drawRect(QtCore.QRectF(4, 4, 8, 8))
        p.drawRect(QtCore.QRectF(12, 12, 8, 8))
        p.setBrush(QtGui.QColor("#2F3540"))
        p.drawRect(QtCore.QRectF(12, 4, 8, 8))
        p.drawRect(QtCore.QRectF(4, 12, 8, 8))
        p.setPen(QtGui.QPen(c_amber, 1.4))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRect(QtCore.QRectF(4, 4, 16, 16))

    elif key == "scene_audit":
        # Diagnostic shield / magnifying check
        p.setPen(QtGui.QPen(c_teal, 1.8))
        p.setBrush(c_teal_fill)
        p.drawEllipse(QtCore.QRectF(4, 4, 13, 13))
        p.drawLine(QtCore.QPointF(15, 15), QtCore.QPointF(20, 20))
        p.setPen(QtGui.QPen(c_green, 2.0, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        p.drawLine(QtCore.QPointF(7.5, 10.5), QtCore.QPointF(10, 13))
        p.drawLine(QtCore.QPointF(10, 13), QtCore.QPointF(14, 8))

    elif key == "blendshape":
        # Maya Shape Editor / BlendShape icon: neutral silhouette + cyan morphed curve + slider dot
        p.setPen(QtGui.QPen(c_slate, 1.3, QtCore.Qt.DashLine))
        p.setBrush(QtGui.QColor("#343B46"))
        p.drawEllipse(QtCore.QRectF(3.5, 4.5, 11, 13))
        p.setPen(pen_teal)
        p.setBrush(c_teal_fill)
        p.drawEllipse(QtCore.QRectF(8.5, 3.5, 12, 14))
        p.setPen(QtGui.QPen(c_amber, 1.8))
        p.drawLine(QtCore.QPointF(4, 20.5), QtCore.QPointF(20, 20.5))
        p.setBrush(c_amber)
        p.setPen(pen_dark)
        p.drawEllipse(QtCore.QPointF(15, 20.5), 2.5, 2.5)

    elif key == "weight_hammer":
        # Maya Weight Hammer icon: metallic hammer head + handle + glowing cyan vertex
        p.setPen(QtGui.QPen(c_amber, 2.2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawLine(QtCore.QPointF(7, 17), QtCore.QPointF(15, 9))
        head = QtGui.QPolygonF([QtCore.QPointF(11, 5), QtCore.QPointF(19, 5), QtCore.QPointF(19, 10), QtCore.QPointF(13, 10)])
        p.setPen(pen_light)
        p.setBrush(QtGui.QColor("#626E80"))
        p.drawPolygon(head)
        p.setBrush(c_teal)
        p.setPen(pen_dark)
        p.drawEllipse(QtCore.QPointF(6, 18.5), 3.0, 3.0)

    elif key == "mirror_weights":
        # Symmetry axis + mirrored bone/weight triangles
        p.setPen(QtGui.QPen(c_amber, 1.5, QtCore.Qt.DashLine))
        p.drawLine(QtCore.QPointF(12, 2.5), QtCore.QPointF(12, 21.5))
        left_tri = QtGui.QPolygonF([QtCore.QPointF(10, 6), QtCore.QPointF(3.5, 12), QtCore.QPointF(10, 18)])
        right_tri = QtGui.QPolygonF([QtCore.QPointF(14, 6), QtCore.QPointF(20.5, 12), QtCore.QPointF(14, 18)])
        p.setPen(pen_light)
        p.setBrush(QtGui.QColor("#485260"))
        p.drawPolygon(left_tri)
        p.setPen(pen_teal)
        p.setBrush(c_teal_fill)
        p.drawPolygon(right_tri)

    elif key == "extract_target":
        # Base mesh + extracted target mesh with link arrow
        p.setPen(QtGui.QPen(c_slate, 1.2))
        p.setBrush(QtGui.QColor("#38404C"))
        p.drawRect(QtCore.QRectF(3, 8, 9, 11))
        p.setPen(QtGui.QPen(c_green, 1.5))
        p.setBrush(QtGui.QColor(89, 184, 110, 110))
        p.drawRect(QtCore.QRectF(12, 4, 9, 11))
        p.setPen(QtGui.QPen(c_amber, 1.8))
        p.drawLine(QtCore.QPointF(7.5, 8), QtCore.QPointF(15.5, 8))

    elif key == "skin_transfer":
        # Source cage -> Target surface weight transfer
        p.setPen(pen_amber)
        p.setBrush(c_amber_fill)
        p.drawEllipse(QtCore.QRectF(3, 5, 8, 14))
        p.setPen(pen_teal)
        p.setBrush(c_teal_fill)
        p.drawEllipse(QtCore.QRectF(13, 5, 8, 14))
        p.setPen(QtGui.QPen(c_light, 1.8))
        p.drawLine(QtCore.QPointF(9, 12), QtCore.QPointF(15, 12))
        p.drawLine(QtCore.QPointF(15, 12), QtCore.QPointF(12.5, 9.5))
        p.drawLine(QtCore.QPointF(15, 12), QtCore.QPointF(12.5, 14.5))

    else:
        # Clean fallback geometric diamond badge
        poly = QtGui.QPolygonF([QtCore.QPointF(12, 4), QtCore.QPointF(20, 12), QtCore.QPointF(12, 20), QtCore.QPointF(4, 12)])
        p.setPen(pen_teal)
        p.setBrush(c_teal_fill)
        p.drawPolygon(poly)

    p.end()
    return pix
