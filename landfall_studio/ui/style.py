"""Modern Maya Studio Design System, QSS Stylesheet Engine, and Reversible Blender Theme Synchronization.

Provides:
- `MAYA_TOKENS`: Unified dark-slate & Maya-teal design tokens (`#181A1D` recessed wells,
  `#23262A` panel surfaces, `#2B2E34` section headers, `#38A3D8` / `#2B5B78` Maya-teal accents,
  `#59A869` construction-history green, `#E09F3E` pivot/soft-select amber).
- `get_studio_stylesheet()`: Complete QSS stylesheet for docked and floating Qt panels
  (`TopShelfQtDock`, `LeftOutlinerQtDock`, `RightAreaQtDock`, `Channels`, `Attribute Editor`,
  `Tool Settings`, `Display Layer Editor`, `Outliner`).
- `apply_studio_style(widget)`: Applies the Modern Maya QSS and font hierarchy to a Qt widget tree.
- `apply_modern_maya_theme_to_blender(context)` & `restore_blender_theme(context)`:
  Synchronizes Blender's native window chrome (Topbar, Statusbar, Timeline, View3D gradient,
  and hides the redundant left `T` toolbar when the Maya Tool Box is docked) with full
  reversible restoration on `unregister()`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

MAYA_TOKENS: Dict[str, str] = {
    "bg_deep": "#181A1D",
    "bg_panel": "#23262A",
    "bg_header": "#2B2E34",
    "bg_card": "#2F333A",
    "bg_hover": "#3A404A",
    "bg_pressed": "#1F2226",
    "border_dark": "#131518",
    "border_mid": "#323740",
    "border_light": "#434954",
    "accent_teal": "#38A3D8",
    "accent_teal_bright": "#56B8E8",
    "accent_teal_bg": "#26536E",
    "accent_teal_subtle": "#1E3848",
    "accent_green": "#59A869",
    "accent_amber": "#E09F3E",
    "accent_red": "#D9534F",
    "axis_x": "#E05A5A",
    "axis_y": "#68B85E",
    "axis_z": "#4F95E0",
    "text_primary": "#E4E8EE",
    "text_secondary": "#A0A8B4",
    "text_muted": "#6E7582",
    "text_accent": "#66C2F0",
}

_saved_theme_attrs: List[Tuple[Any, str, Any]] = []
_saved_region_flags: List[Tuple[int, bool, bool]] = []
_theme_applied: bool = False


def get_studio_stylesheet() -> str:
    """Return the cohesive Modern Maya QSS stylesheet."""
    t = MAYA_TOKENS
    return f"""
    QWidget {{
        background-color: {t['bg_panel']};
        color: {t['text_primary']};
        font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
        font-size: 11px;
        selection-background-color: {t['accent_teal_bg']};
        selection-color: #FFFFFF;
    }}

    QFrame#MayaPanelRoot, QWidget#MayaPanelRoot {{
        background-color: {t['bg_panel']};
        border: 1px solid {t['border_dark']};
    }}

    QFrame#MayaStatusLine {{
        background-color: {t['bg_header']};
        border-bottom: 1px solid {t['border_dark']};
    }}

    QFrame#MayaShelfBar {{
        background-color: {t['bg_panel']};
        border-bottom: 1px solid {t['border_dark']};
    }}

    QFrame#MayaSectionHeader {{
        background-color: {t['bg_header']};
        border-top: 1px solid {t['border_mid']};
        border-bottom: 1px solid {t['border_dark']};
        padding: 2px 6px;
    }}

    QLabel#MayaSectionTitle {{
        background: transparent;
        color: {t['text_primary']};
        font-weight: 700;
        font-size: 10px;
        letter-spacing: 0.6px;
    }}

    QLabel#MayaBadgeTeal {{
        background-color: {t['accent_teal_subtle']};
        color: {t['text_accent']};
        border: 1px solid {t['accent_teal_bg']};
        border-radius: 2px;
        padding: 1px 5px;
        font-weight: 600;
        font-size: 10px;
    }}

    QLabel#MayaBadgeGreen {{
        background-color: #1D3524;
        color: #7ED491;
        border: 1px solid #2E5939;
        border-radius: 2px;
        padding: 1px 5px;
        font-weight: 600;
        font-size: 10px;
    }}

    QLabel#MayaBadgeAmber {{
        background-color: #3A2C18;
        color: #F2B857;
        border: 1px solid #664920;
        border-radius: 2px;
        padding: 1px 5px;
        font-weight: 600;
        font-size: 10px;
    }}

    QLabel#MayaMutedLabel {{
        background: transparent;
        color: {t['text_secondary']};
        font-size: 10px;
    }}

    QToolButton, QPushButton {{
        background-color: {t['bg_card']};
        color: {t['text_primary']};
        border: 1px solid {t['border_dark']};
        border-radius: 2px;
        padding: 2px 6px;
        font-size: 11px;
    }}

    QToolButton:hover, QPushButton:hover {{
        background-color: {t['bg_hover']};
        border-color: {t['border_light']};
    }}

    QToolButton:pressed, QPushButton:pressed {{
        background-color: {t['bg_pressed']};
        border-color: {t['accent_teal']};
    }}

    QToolButton:checked, QPushButton:checked {{
        background-color: {t['accent_teal_bg']};
        color: #FFFFFF;
        border: 1px solid {t['accent_teal']};
        font-weight: 600;
    }}

    QToolButton#MayaShelfTile {{
        background-color: #292D33;
        color: {t['text_primary']};
        border: 1px solid #1C1F24;
        border-radius: 3px;
        padding: 2px 3px 1px 3px;
        font-size: 9px;
    }}

    QToolButton#MayaShelfTile:hover {{
        background-color: #343A43;
        border: 1px solid {t['accent_teal']};
    }}

    QToolButton#MayaShelfTile:pressed {{
        background-color: {t['accent_teal_bg']};
    }}

    QToolButton#MayaToolBoxBtn {{
        background-color: #282B31;
        border: 1px solid #191B1F;
        border-radius: 3px;
        padding: 3px;
    }}

    QToolButton#MayaToolBoxBtn:hover {{
        background-color: #353A42;
        border-color: {t['border_light']};
    }}

    QToolButton#MayaToolBoxBtn:checked {{
        background-color: {t['accent_teal_bg']};
        border: 1px solid {t['accent_teal_bright']};
    }}

    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {t['bg_deep']};
        color: {t['text_primary']};
        border: 1px solid {t['border_mid']};
        border-radius: 2px;
        padding: 2px 5px;
        selection-background-color: {t['accent_teal_bg']};
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {t['accent_teal']};
        background-color: #141619;
    }}

    QLineEdit:read-only {{
        background-color: #1D2024;
        color: {t['text_accent']};
        font-weight: 600;
        border: 1px solid #282C33;
    }}

    QTabWidget::pane {{
        border: 1px solid {t['border_dark']};
        background-color: {t['bg_panel']};
        top: -1px;
    }}

    QTabBar::tab {{
        background-color: #1E2024;
        color: {t['text_secondary']};
        border: 1px solid {t['border_dark']};
        border-bottom: none;
        padding: 3px 10px;
        margin-right: 1px;
        font-size: 10px;
        font-weight: 600;
    }}

    QTabBar::tab:hover {{
        background-color: #2A2E35;
        color: {t['text_primary']};
    }}

    QTabBar::tab:selected {{
        background-color: {t['bg_panel']};
        color: #FFFFFF;
        border-top: 2px solid {t['accent_teal']};
    }}

    QTableWidget, QTableView, QTreeWidget, QTreeView, QListWidget {{
        background-color: {t['bg_deep']};
        alternate-background-color: #1D2024;
        color: {t['text_primary']};
        gridline-color: #252930;
        border: 1px solid {t['border_dark']};
        selection-background-color: {t['accent_teal_bg']};
        selection-color: #FFFFFF;
        outline: 0;
    }}

    QHeaderView::section {{
        background-color: {t['bg_header']};
        color: {t['text_secondary']};
        border: none;
        border-right: 1px solid {t['border_dark']};
        border-bottom: 1px solid {t['border_dark']};
        padding: 2px 5px;
        font-size: 10px;
        font-weight: 600;
    }}

    QSplitter::handle {{
        background-color: {t['border_dark']};
    }}

    QSplitter::handle:vertical {{
        height: 4px;
        background-color: #1A1C20;
        border-top: 1px solid #31363F;
        border-bottom: 1px solid #101214;
    }}

    QSplitter::handle:horizontal {{
        width: 4px;
        background-color: #1A1C20;
    }}

    QScrollBar:vertical {{
        background: {t['bg_deep']};
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: #3B4049;
        min-height: 20px;
        border-radius: 3px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {t['accent_teal']};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """


def apply_studio_style(widget: Any) -> None:
    """Apply the Modern Maya Studio QSS stylesheet to `widget`."""
    if widget is None:
        return
    try:
        widget.setStyleSheet(get_studio_stylesheet())
    except Exception:
        pass


def _save_and_set_color(owner: Any, attr: str, rgba_or_rgb: Tuple[float, ...]) -> None:
    """Backup `getattr(owner, attr)` once and assign `rgba_or_rgb`."""
    if owner is None or not hasattr(owner, attr):
        return
    try:
        cur = getattr(owner, attr)
        saved = tuple(float(x) for x in cur)
        _saved_theme_attrs.append((owner, attr, saved))
        setattr(owner, attr, rgba_or_rgb[: len(saved)])
    except Exception:
        pass


def apply_modern_maya_theme_to_blender(
    context: Any = None,
    hide_stock_view3d_toolbar: bool = True,
) -> Dict[str, Any]:
    """Harmonize Blender's native chrome and 3D Viewport with the Modern Maya dark-slate/teal palette."""
    global _theme_applied
    try:
        import bpy
    except ImportError:
        return {"ok": False, "applied": False}

    ctx = context or bpy.context
    prefs = getattr(ctx, "preferences", None)
    if prefs is None or not prefs.themes:
        return {"ok": False, "applied": False}

    theme = prefs.themes[0]
    if not _theme_applied:
        # 1. Harmonize 3D Viewport background gradient to Maya dark studio slate-blue
        v3d_space = getattr(getattr(theme, "view_3d", None), "space", None)
        grad = getattr(v3d_space, "gradients", None) if v3d_space is not None else None
        if grad is not None:
            _save_and_set_color(grad, "high_gradient", (0.21, 0.24, 0.28))
            _save_and_set_color(grad, "gradient", (0.10, 0.11, 0.13))
        if v3d_space is not None:
            _save_and_set_color(v3d_space, "header", (0.14, 0.15, 0.165, 1.0))
        v3d = getattr(theme, "view_3d", None)
        if v3d is not None:
            _save_and_set_color(v3d, "object_active", (0.27, 0.88, 0.62))
            _save_and_set_color(v3d, "object_selected", (0.22, 0.64, 0.85))
            _save_and_set_color(v3d, "grid", (0.24, 0.27, 0.31, 0.55))

        # 2. Harmonize Topbar, Statusbar, Timeline, Outliner, and Properties to #23262A / #181A1D
        for ed_name in ("topbar", "statusbar", "dopesheet_editor", "outliner", "properties", "info"):
            ed = getattr(theme, ed_name, None)
            sp = getattr(ed, "space", None) if ed is not None else None
            if sp is not None:
                _save_and_set_color(sp, "back", (0.137, 0.149, 0.165))
                _save_and_set_color(sp, "header", (0.168, 0.180, 0.204, 1.0))

        # 3. Harmonize User Interface active item highlight to Maya Teal (#26536E / #38A3D8)
        ui = getattr(theme, "user_interface", None)
        if ui is not None:
            for wcol_name in ("wcol_regular", "wcol_tool", "wcol_option", "wcol_toggle", "wcol_Menu", "wcol_tab"):
                wcol = getattr(ui, wcol_name, None)
                if wcol is not None:
                    _save_and_set_color(wcol, "inner_sel", (0.16, 0.36, 0.48, 1.0))

        _theme_applied = True

    # 4. Hide stock Blender left 'T' toolbar and overlapping 'User Perspective' text in 3D Viewport
    hidden_toolbars = 0
    wm = getattr(bpy.context, "window_manager", None)
    for win in (wm.windows if wm else []):
        if not win.screen:
            continue
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                sp = area.spaces.active
                if sp is not None:
                    try:
                        if hasattr(sp, "overlay") and hasattr(sp.overlay, "show_text"):
                            sp.overlay.show_text = False
                    except Exception:
                        pass
                    if hide_stock_view3d_toolbar and getattr(bpy.context, "window", None) is not None and hasattr(sp, "show_region_toolbar"):
                        ptr = int(sp.as_pointer())
                        if not any(p == ptr for p, _, _ in _saved_region_flags):
                            _saved_region_flags.append(
                                (
                                    ptr,
                                    bool(getattr(sp, "show_region_toolbar", True)),
                                    bool(getattr(sp, "show_region_ui", False)),
                                )
                            )
                        try:
                            if sp.show_region_toolbar:
                                sp.show_region_toolbar = False
                            hidden_toolbars += 1
                        except Exception:
                            pass

    return {
        "ok": True,
        "applied": _theme_applied,
        "saved_theme_attr_count": len(_saved_theme_attrs),
        "hidden_toolbars": hidden_toolbars,
    }


def restore_blender_theme(context: Any = None) -> Dict[str, Any]:
    """Reversibly restore all Blender theme colors and viewport region flags modified by Studio."""
    global _theme_applied
    restored = 0
    for owner, attr, saved_val in reversed(_saved_theme_attrs):
        try:
            setattr(owner, attr, saved_val)
            restored += 1
        except Exception:
            pass
    _saved_theme_attrs.clear()

    try:
        import bpy

        if getattr(bpy.context, "window", None) is not None:
            saved_map = {ptr: (tb, ui) for ptr, tb, ui in _saved_region_flags}
            wm = getattr(bpy.context, "window_manager", None)
            for win in (wm.windows if wm else []):
                if not win.screen:
                    continue
                for area in win.screen.areas:
                    if area.type == "VIEW_3D":
                        sp = area.spaces.active
                        if sp is not None and int(sp.as_pointer()) in saved_map:
                            tb, _ = saved_map[int(sp.as_pointer())]
                            try:
                                sp.show_region_toolbar = tb
                            except Exception:
                                pass
    except Exception:
        pass

    _saved_region_flags.clear()
    _theme_applied = False
    return {"ok": True, "restored_attrs": restored}


def is_theme_applied() -> bool:
    return _theme_applied
