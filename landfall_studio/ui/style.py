"""Modern Maya Studio Design System (Figma Make Token Spec), QSS Stylesheet Engine, and Reversible Blender Theme Synchronization.

Provides:
- `MAYA_TOKENS`: Unified dark-slate & Maya-teal design tokens extracted from the Figma Make
  "Modern Autodesk Maya Interface" prototype (`--void: #111315`, `--recess: #181A1D`,
  `--panel: #22252A`, `--header: #2A2E35`, `--line: #2E333B`, `--teal: #38A3D8`,
  `--emerald: #3FB950`, `--red: #E35D6A`, `--cyan: #5AC8DB`).
- `get_studio_stylesheet()`: Complete QSS stylesheet for docked and floating Qt panels.
- `apply_studio_style(widget)`: Applies the Modern Maya QSS and font hierarchy to a Qt widget tree.
- `apply_modern_maya_theme_to_blender(context)` & `restore_blender_theme(context)`:
  Synchronizes Blender's native window chrome with full reversible restoration on `unregister()`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

MAYA_TOKENS: Dict[str, str] = {
    "void": "#111315",
    "bg_deep": "#17191C",
    "bg_recess": "#181A1D",
    "bg_panel": "#22252A",
    "bg_header": "#2A2E35",
    "bg_card": "#292D33",
    "bg_hover": "#343941",
    "bg_pressed": "#1B1E22",
    "border_dark": "#101214",
    "border_mid": "#2E333B",
    "border_light": "#3E4550",
    "accent_teal": "#38A3D8",
    "accent_teal_bright": "#67C9EF",
    "accent_teal_bg": "#225976",
    "accent_teal_subtle": "#213745",
    "accent_green": "#3FB950",
    "accent_amber": "#E1A75C",
    "accent_red": "#E35D6A",
    "accent_cyan": "#5AC8DB",
    "axis_x": "#EC8B93",
    "axis_x_bg": "#3E272A",
    "axis_y": "#75D08B",
    "axis_y_bg": "#213B2A",
    "axis_z": "#76A9E5",
    "axis_z_bg": "#23334B",
    "text_primary": "#C9CDD3",
    "text_bright": "#E4E7E9",
    "text_secondary": "#8D949D",
    "text_muted": "#68717C",
    "text_accent": "#7CC2E3",
}

_saved_theme_attrs: List[Tuple[Any, str, Any]] = []
_saved_region_flags: List[Tuple[int, bool, bool]] = []
_theme_applied: bool = False


def get_studio_stylesheet() -> str:
    """Return the cohesive Modern Maya QSS stylesheet aligned with the Figma Make specification."""
    t = MAYA_TOKENS
    return f"""
    QWidget {{
        background-color: {t['bg_panel']};
        color: {t['text_primary']};
        font-family: "Inter", "Segoe UI", "SF Pro Text", sans-serif;
        font-size: 11px;
        selection-background-color: {t['accent_teal_bg']};
        selection-color: #EDF7FA;
    }}

    QFrame#MayaPanelRoot, QWidget#MayaPanelRoot {{
        background-color: {t['bg_panel']};
        border: 1px solid {t['border_dark']};
    }}

    QFrame#MayaStatusLine {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #292D32, stop:1 #22252A);
        border-bottom: 1px solid #0F1113;
    }}

    QFrame#MayaToolRail {{
        background-color: #1C1F23;
        border-right: 1px solid #141619;
    }}

    QFrame#MayaEdgeTabStrip {{
        background-color: #181A1D;
        border-right: 1px solid #34383E;
    }}

    QFrame#MayaShelfBar {{
        background-color: #1E2125;
        border-bottom: 1px solid #131619;
    }}

    QFrame#MayaSectionHeader {{
        background-color: {t['bg_header']};
        border-top: 1px solid {t['border_mid']};
        border-bottom: 1px solid #181A1E;
        padding: 2px 6px;
    }}

    QFrame#MayaColumnSubheader {{
        background-color: #1A1D20;
        border-bottom: 1px solid #262A30;
    }}

    QLabel#MayaSectionTitle {{
        background: transparent;
        color: {t['text_primary']};
        font-weight: 700;
        font-size: 9px;
        letter-spacing: 0.8px;
    }}

    QLabel#MayaFieldTag {{
        background: transparent;
        color: #68717C;
        font-weight: 700;
        font-size: 8px;
        letter-spacing: 1.0px;
    }}

    QLabel#MayaBadgeTeal {{
        background-color: #213745;
        color: #D4EAF4;
        border: 1px solid #277BA4;
        border-radius: 3px;
        padding: 1px 6px;
        font-weight: 700;
        font-size: 9px;
    }}

    QLabel#MayaBadgeGreen {{
        background-color: #1B3022;
        color: #B8EAC4;
        border: 1px solid #318B49;
        border-radius: 10px;
        padding: 1px 8px;
        font-weight: 700;
        font-size: 9px;
    }}

    QLabel#MayaBadgeAmber {{
        background-color: #3A2C18;
        color: #F2B857;
        border: 1px solid #664920;
        border-radius: 3px;
        padding: 1px 6px;
        font-weight: 700;
        font-size: 9px;
    }}

    QLabel#MayaMutedLabel {{
        background: transparent;
        color: {t['text_secondary']};
        font-size: 10px;
    }}

    QToolButton, QPushButton {{
        background-color: #262A30;
        color: {t['text_primary']};
        border: 1px solid #343941;
        border-radius: 3px;
        padding: 2px 7px;
        font-size: 10px;
    }}

    QToolButton:hover, QPushButton:hover {{
        background-color: {t['bg_hover']};
        border-color: #464E59;
        color: #FFFFFF;
    }}

    QToolButton:pressed, QPushButton:pressed {{
        background-color: {t['bg_pressed']};
        border-color: {t['accent_teal']};
    }}

    QToolButton:checked, QPushButton:checked {{
        background-color: #213745;
        color: #D4EAF4;
        border: 1px solid #277BA4;
        font-weight: 700;
    }}

    QPushButton#MayaMaskPill {{
        background-color: #25292E;
        color: #ABB1BA;
        border: 1px solid #343941;
        border-radius: 2px;
        padding: 1px 6px;
        font-size: 9px;
        font-weight: 600;
    }}

    QPushButton#MayaMaskPill:checked {{
        background-color: #213745;
        color: #D4EAF4;
        border: 1px solid #277BA4;
        font-weight: 700;
    }}

    QPushButton#MayaLiveCapsule {{
        background-color: #1F2328;
        color: #8D949D;
        border: 1px solid #323740;
        border-radius: 10px;
        padding: 1px 9px;
        font-size: 9px;
        font-weight: 700;
    }}

    QToolButton#MayaShelfTile {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2B2F35, stop:1 #22252A);
        color: #8D949D;
        border: 1px solid #32373E;
        border-radius: 3px;
        padding: 3px 2px 1px 2px;
        font-size: 8px;
        font-weight: 600;
    }}

    QToolButton#MayaShelfTile:hover {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #32373E, stop:1 #272B31);
        border: 1px solid #454C56;
        color: #DDE1E6;
    }}

    QToolButton#MayaShelfTile:pressed, QToolButton#MayaShelfTile:checked {{
        background-color: #29343A;
        border: 1px solid #3A5968;
        color: #D7ECF6;
    }}

    QToolButton#MayaToolBoxBtn {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #292D32, stop:1 #202328);
        border: 1px solid #30353B;
        border-radius: 3px;
        padding: 3px;
    }}

    QToolButton#MayaToolBoxBtn:hover {{
        background-color: #32373F;
        border-color: #464E58;
    }}

    QToolButton#MayaToolBoxBtn:checked {{
        background-color: #263741;
        border: 1px solid #387B9B;
    }}

    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {t['bg_deep']};
        color: #DCE1E6;
        border: 1px solid #30353C;
        border-radius: 3px;
        padding: 2px 6px;
        selection-background-color: {t['accent_teal_bg']};
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {t['accent_teal']};
        background-color: #141619;
    }}

    QLineEdit:read-only {{
        background-color: #1A1D21;
        color: {t['text_accent']};
        font-weight: 600;
        border: 1px solid #282C33;
    }}

    QTabWidget::pane {{
        border: 1px solid #131619;
        background-color: #1E2125;
        top: -1px;
    }}

    QTabBar::tab {{
        background-color: #24272C;
        color: #8A919A;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 4px 11px;
        margin-right: 1px;
        font-size: 9.5px;
        font-weight: 600;
    }}

    QTabBar::tab:hover {{
        background-color: #2A2E34;
        color: #D0D4DA;
    }}

    QTabBar::tab:selected {{
        background-color: #1E2125;
        color: #E4E7E9;
        border-bottom: 2px solid {t['accent_teal']};
    }}

    QTableWidget, QTableView, QTreeWidget, QTreeView, QListWidget {{
        background-color: #1E2126;
        alternate-background-color: #22252A;
        color: {t['text_primary']};
        gridline-color: #282C32;
        border: 1px solid #141619;
        selection-background-color: {t['accent_teal_bg']};
        selection-color: #EDF7FA;
        outline: 0;
    }}

    QHeaderView::section {{
        background-color: #1A1D20;
        color: #68717C;
        border: none;
        border-right: 1px solid #262A30;
        border-bottom: 1px solid #262A30;
        padding: 2px 6px;
        font-size: 8.5px;
        font-weight: 700;
        letter-spacing: 0.6px;
    }}

    QSplitter::handle {{
        background-color: #141619;
    }}

    QSplitter::handle:vertical {{
        height: 4px;
        background-color: #181A1D;
        border-top: 1px solid #2E333B;
        border-bottom: 1px solid #101214;
    }}

    QSplitter::handle:horizontal {{
        width: 4px;
        background-color: #181A1D;
    }}

    QScrollBar:vertical {{
        background: #17191C;
        width: 7px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: #343942;
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
    """Harmonize Blender's native chrome and 3D Viewport with the Figma Make Modern Maya dark-slate/teal palette."""
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
        # 1. Harmonize 3D Viewport background gradient to Figma Make studio radial slate (#3B444E -> #20252B)
        v3d_space = getattr(getattr(theme, "view_3d", None), "space", None)
        grad = getattr(v3d_space, "gradients", None) if v3d_space is not None else None
        if grad is not None:
            _save_and_set_color(grad, "high_gradient", (0.231, 0.267, 0.306))
            _save_and_set_color(grad, "gradient", (0.125, 0.145, 0.169))
        if v3d_space is not None:
            _save_and_set_color(v3d_space, "header", (0.133, 0.145, 0.165, 1.0))
        v3d = getattr(theme, "view_3d", None)
        if v3d is not None:
            _save_and_set_color(v3d, "object_active", (0.247, 0.725, 0.314))
            _save_and_set_color(v3d, "object_selected", (0.220, 0.639, 0.847))
            _save_and_set_color(v3d, "grid", (0.270, 0.310, 0.355, 0.55))

        # 2. Harmonize Topbar, Statusbar, Timeline, Outliner, and Properties to #22252A / #181A1D
        for ed_name in ("topbar", "statusbar", "dopesheet_editor", "outliner", "properties", "info"):
            ed = getattr(theme, ed_name, None)
            sp = getattr(ed, "space", None) if ed is not None else None
            if sp is not None:
                _save_and_set_color(sp, "back", (0.133, 0.145, 0.165))
                _save_and_set_color(sp, "header", (0.165, 0.180, 0.208, 1.0))

        # 3. Harmonize User Interface active item highlight to Maya Teal (#225976 / #38A3D8)
        ui = getattr(theme, "user_interface", None)
        if ui is not None:
            for wcol_name in ("wcol_regular", "wcol_tool", "wcol_option", "wcol_toggle", "wcol_Menu", "wcol_tab"):
                wcol = getattr(ui, wcol_name, None)
                if wcol is not None:
                    _save_and_set_color(wcol, "inner_sel", (0.133, 0.349, 0.463, 1.0))

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
