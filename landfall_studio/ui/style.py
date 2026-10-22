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


def elided_label(text='', parent=None):
    """Keep long production names readable without setting a panel's width."""
    from qtpy import QtCore, QtWidgets

    class ElidedLabel(QtWidgets.QLabel):
        def __init__(self):
            self.full_text = ''
            super().__init__(parent)
            self.setMinimumWidth(0)
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            self.setText(text)
        def setText(self, value):
            self.full_text = str(value)
            self.setToolTip(self.full_text)
            self._fit_text()
        def _fit_text(self):
            shown = self.fontMetrics().elidedText(self.full_text, QtCore.Qt.ElideMiddle, max(0, self.width()-16))
            if shown != super().text():
                super().setText(shown)
        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._fit_text()
        def changeEvent(self, event):
            super().changeEvent(event)
            if event.type() in (QtCore.QEvent.FontChange, QtCore.QEvent.StyleChange):
                self._fit_text()
        def sizeHint(self):
            return QtCore.QSize(80, super().sizeHint().height())
        def minimumSizeHint(self):
            return QtCore.QSize(0, super().minimumSizeHint().height())

    return ElidedLabel()


def compact_double_spin(parent=None):
    """A readable numeric editor inside both native-hosted and floating panels."""
    from qtpy import QtCore, QtWidgets

    class DenseSpin(QtWidgets.QDoubleSpinBox):
        def _fit_editor(self):
            self.lineEdit().setGeometry(4, 2, max(1, self.width()-8), max(1, self.height()-4))
        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._fit_editor()
        def showEvent(self, event):
            super().showEvent(event)
            self._fit_editor()

    spin = DenseSpin(parent)
    spin.setKeyboardTracking(False)
    spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
    spin.setMinimumWidth(58)
    spin.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    spin.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    spin.lineEdit().setMinimumWidth(0)
    # Avoid applying the outer field's padding/border to its inner text editor.
    spin.lineEdit().setStyleSheet(
        'QLineEdit { border: none; border-radius: 0; padding: 0; '
        'background: transparent; color: #DCE1E6; min-width: 0; }')
    return spin

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
        font-size: 10px;
        letter-spacing: 0.8px;
    }}

    QLabel#MayaFieldTag {{
        background: transparent;
        color: #68717C;
        font-weight: 700;
        font-size: 10px;
        letter-spacing: 1.0px;
    }}

    QLabel#MayaBadgeTeal {{
        background-color: #213745;
        color: #D4EAF4;
        border: 1px solid #277BA4;
        border-radius: 3px;
        padding: 1px 6px;
        font-weight: 700;
        font-size: 10px;
    }}

    QLabel#MayaBadgeGreen {{
        background-color: #1B3022;
        color: #B8EAC4;
        border: 1px solid #318B49;
        border-radius: 10px;
        padding: 1px 8px;
        font-weight: 700;
        font-size: 10px;
    }}

    QLabel#MayaBadgeAmber {{
        background-color: #3A2C18;
        color: #F2B857;
        border: 1px solid #664920;
        border-radius: 3px;
        padding: 1px 6px;
        font-weight: 700;
        font-size: 10px;
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
        border-radius: 4px;
        padding: 2px 9px;
        font-size: 11px;
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
        border-radius: 3px;
        padding: 1px 9px;
        font-size: 11px;
        font-weight: 500;
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
        font-size: 10px;
        font-weight: 700;
    }}

    QToolButton#MayaShelfTile {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2B2F35, stop:1 #22252A);
        color: #8D949D;
        border: 1px solid #32373E;
        border-radius: 3px;
        padding: 3px 2px 1px 2px;
        font-size: 10px;
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
        font-size: 11px;
        font-weight: 500;
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
        font-size: 10px;
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

    QFrame#MayaMainMenuBar {{
        background-color: {t['void']};
        border-bottom: 1px solid {t['border_dark']};
    }}

    QMenuBar {{
        background: transparent;
        color: {t['text_primary']};
        font-size: 12px;
        spacing: 2px;
    }}

    QMenuBar::item {{
        background: transparent;
        padding: 6px 8px;
        border-radius: 3px;
    }}

    QMenuBar::item:selected, QMenuBar::item:pressed {{
        background-color: {t['bg_hover']};
        color: #FFFFFF;
    }}

    QMenuBar#MayaPanelMenuBar {{
        background-color: {t['bg_panel']};
        border-bottom: 1px solid {t['border_dark']};
        font-size: 11px;
    }}

    QMenuBar#MayaPanelMenuBar::item {{
        padding: 4px 8px;
    }}

    QMenu {{
        background-color: {t['bg_header']};
        color: {t['text_primary']};
        border: 1px solid {t['border_light']};
        padding: 4px 0px;
        font-size: 12px;
    }}

    QMenu::item {{
        padding: 5px 28px 5px 16px;
    }}

    QMenu::item:selected {{
        background-color: {t['accent_teal_subtle']};
        color: #FFFFFF;
    }}

    QMenu::separator {{
        height: 1px;
        background: {t['border_mid']};
        margin: 4px 8px;
    }}

    QMenu::section {{
        color: {t['text_muted']};
        font-size: 10px;
        font-weight: 600;
        padding: 8px 16px 3px 16px;
        background: transparent;
    }}

    QFrame#MayaCollapseHandle {{
        background-color: {t['border_light']};
        border-radius: 1px;
    }}

    QToolButton#MayaStatusIcon {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 0px;
    }}

    QToolButton#MayaStatusIcon:hover {{
        background-color: {t['bg_hover']};
        border-color: {t['border_light']};
    }}

    QToolButton#MayaStatusIcon:checked {{
        background-color: {t['accent_teal_bg']};
        border: 1px solid {t['accent_teal']};
    }}

    QPushButton#MayaAccentButton {{
        background-color: {t['accent_teal_subtle']};
        color: {t['text_accent']};
        border: 1px solid {t['accent_teal']};
        font-weight: 500;
    }}

    QToolButton#MayaModToggle {{
        background-color: {t['bg_recess']};
        color: {t['text_muted']};
        border: 1px solid {t['border_mid']};
        border-radius: 3px;
        padding: 0px;
        font-size: 10px;
        font-weight: 600;
    }}

    QToolButton#MayaModToggle:checked {{
        background-color: {t['accent_teal_bg']};
        color: {t['text_bright']};
        border: 1px solid {t['accent_teal']};
    }}

    QLabel#MayaHelpLine {{
        background-color: {t['void']};
        color: {t['text_secondary']};
        font-size: 11px;
        padding: 0px 12px;
    }}
    """


def apply_studio_style(widget: Any) -> None:
    """Apply the Modern Maya Studio QSS stylesheet to `widget`."""
    if widget is None:
        return
    try:
        widget.setProperty('landfallStudioUi', True)
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


_save_pre_restored_spaces: List[Tuple[Any, bool, bool, bool, bool]] = []


def _set_view3d_region_flags(
    win: Any,
    area: Any,
    sp: Any,
    toolbar: Optional[bool] = None,
    header: Optional[bool] = None,
    tool_header: Optional[bool] = None,
    show_text: Optional[bool] = None,
) -> None:
    """Safely update 3D Viewport region visibility flags with a valid window in context.

    Blender's `rna_Space_show_region_*_update` calls `ED_region_visibility_change_update` ->
    `ED_area_init(C, CTX_wm_window(C), area)` -> `WM_window_get_active_workspace(win)`, which
    crashes with `EXCEPTION_ACCESS_VIOLATION` if `bpy.context.window` is `None` (e.g. inside a
    `bpy.app.timers` callback or after `bpy.ops.screen.area_close()` during dock teardown).
    """
    import bpy

    if show_text is not None:
        try:
            if hasattr(sp, "overlay") and hasattr(sp.overlay, "show_text"):
                if bool(sp.overlay.show_text) != bool(show_text):
                    sp.overlay.show_text = bool(show_text)
        except Exception:
            pass

    if win is None or getattr(win, "screen", None) is None:
        return

    try:
        # Region-visibility updates need a window in context (timers and post-area_close callbacks have none)
        with bpy.context.temp_override(window=win, screen=win.screen, area=area):
            if toolbar is not None and hasattr(sp, "show_region_toolbar"):
                if bool(sp.show_region_toolbar) != bool(toolbar):
                    sp.show_region_toolbar = bool(toolbar)
            if header is not None and hasattr(sp, "show_region_header"):
                if bool(sp.show_region_header) != bool(header):
                    sp.show_region_header = bool(header)
            if tool_header is not None and hasattr(sp, "show_region_tool_header"):
                if bool(sp.show_region_tool_header) != bool(tool_header):
                    sp.show_region_tool_header = bool(tool_header)
    except Exception:
        pass


def _on_save_pre_restore_viewport_headers(*_args) -> None:
    """Temporarily restore 3D Viewport headers, toolbars, and overlay text before saving a `.blend` file so saved files never hide Blender chrome for colleagues without Studio."""
    global _save_pre_restored_spaces
    _save_pre_restored_spaces.clear()
    if not _theme_applied:
        return
    try:
        import bpy

        wm = getattr(bpy.context, "window_manager", None)
        for win in (wm.windows if wm else []):
            if not win.screen:
                continue
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    sp = area.spaces.active
                    if sp is not None:
                        cur_tb = bool(getattr(sp, "show_region_toolbar", False))
                        cur_hdr = bool(getattr(sp, "show_region_header", False))
                        cur_thdr = bool(getattr(sp, "show_region_tool_header", False))
                        cur_txt = bool(getattr(getattr(sp, "overlay", None), "show_text", False))
                        _save_pre_restored_spaces.append((sp, cur_tb, cur_hdr, cur_thdr, cur_txt))
                        _set_view3d_region_flags(
                            win,
                            area,
                            sp,
                            toolbar=True,
                            header=True,
                            tool_header=True,
                            show_text=True,
                        )
    except Exception:
        pass


def _on_save_post_reapply_viewport_headers(*_args) -> None:
    """Re-apply Studio clean viewport state after `.blend` save completes."""
    global _save_pre_restored_spaces
    if not _save_pre_restored_spaces:
        return
    try:
        import bpy

        wm = getattr(bpy.context, "window_manager", None)
        sp_owner = {}
        for win in (wm.windows if wm else []):
            if not win.screen:
                continue
            for area in win.screen.areas:
                if area.type == "VIEW_3D" and area.spaces.active is not None:
                    sp_owner[int(area.spaces.active.as_pointer())] = (win, area)

        for sp, cur_tb, cur_hdr, cur_thdr, cur_txt in _save_pre_restored_spaces:
            try:
                win_area = sp_owner.get(int(sp.as_pointer()))
                if win_area is not None:
                    _set_view3d_region_flags(
                        win_area[0],
                        win_area[1],
                        sp,
                        toolbar=cur_tb,
                        header=cur_hdr,
                        tool_header=cur_thdr,
                        show_text=cur_txt,
                    )
            except Exception:
                pass
    finally:
        _save_pre_restored_spaces.clear()


def _ensure_save_handlers_registered() -> None:
    try:
        import bpy

        if _on_save_pre_restore_viewport_headers not in bpy.app.handlers.save_pre:
            bpy.app.handlers.save_pre.append(_on_save_pre_restore_viewport_headers)
        if _on_save_post_reapply_viewport_headers not in bpy.app.handlers.save_post:
            bpy.app.handlers.save_post.append(_on_save_post_reapply_viewport_headers)
    except Exception:
        pass


def _remove_save_handlers() -> None:
    try:
        import bpy

        if _on_save_pre_restore_viewport_headers in bpy.app.handlers.save_pre:
            bpy.app.handlers.save_pre.remove(_on_save_pre_restore_viewport_headers)
        if _on_save_post_reapply_viewport_headers in bpy.app.handlers.save_post:
            bpy.app.handlers.save_post.remove(_on_save_post_reapply_viewport_headers)
    except Exception:
        pass


def apply_modern_maya_theme_to_blender(
    context: Any = None,
    hide_stock_view3d_toolbar: bool = True,
) -> Dict[str, Any]:
    """Harmonize Blender's native chrome and 3D Viewport with the Figma Make Modern Maya dark-slate/teal palette (without dirtying userpref.blend)."""
    global _theme_applied
    try:
        import bpy
    except ImportError:
        return {"ok": False, "applied": False}

    ctx = context or bpy.context
    prefs = getattr(ctx, "preferences", None)
    if prefs is None or not prefs.themes:
        return {"ok": False, "applied": False}

    was_dirty = bool(getattr(prefs, "is_dirty", False))
    _ensure_save_handlers_registered()

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

    try:
        prefs.is_dirty = was_dirty
    except Exception:
        pass

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
                    if hide_stock_view3d_toolbar and hasattr(sp, "show_region_toolbar"):
                        ptr = int(sp.as_pointer())
                        if not any(p[0] == ptr for p in _saved_region_flags):
                            _saved_region_flags.append(
                                (
                                    ptr,
                                    bool(getattr(sp, "show_region_toolbar", True)),
                                    bool(getattr(sp, "show_region_ui", False)),
                                    bool(getattr(sp, "show_region_header", True)),
                                    bool(getattr(sp, "show_region_tool_header", True)),
                                )
                            )
                        _set_view3d_region_flags(
                            win,
                            area,
                            sp,
                            toolbar=False,
                            header=False,
                            tool_header=False,
                        )
                        hidden_toolbars += 1

    return {
        "ok": True,
        "applied": _theme_applied,
        "saved_theme_attr_count": len(_saved_theme_attrs),
        "hidden_toolbars": hidden_toolbars,
    }


def restore_blender_theme(context: Any = None) -> Dict[str, Any]:
    """Reversibly restore all Blender theme colors and viewport region flags modified by Studio."""
    global _theme_applied
    _remove_save_handlers()

    prefs = None
    was_dirty = False
    try:
        import bpy

        ctx = context or bpy.context
        prefs = getattr(ctx, "preferences", None)
        if prefs is not None:
            was_dirty = bool(getattr(prefs, "is_dirty", False))
    except Exception:
        pass

    restored = 0
    for owner, attr, saved_val in reversed(_saved_theme_attrs):
        try:
            setattr(owner, attr, saved_val)
            restored += 1
        except Exception:
            pass
    _saved_theme_attrs.clear()

    if prefs is not None:
        try:
            prefs.is_dirty = was_dirty
        except Exception:
            pass

    try:
        import bpy

        saved_map = {}
        for item in _saved_region_flags:
            if len(item) >= 5:
                saved_map[item[0]] = (item[1], item[2], item[3], item[4])
            else:
                saved_map[item[0]] = (item[1], item[2], True, True)
        wm = getattr(bpy.context, "window_manager", None)
        for win in (wm.windows if wm else []):
            if not win.screen:
                continue
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    sp = area.spaces.active
                    if sp is not None:
                        # Fallback to standard visible regions (True, False, True, True) if file was reloaded and pointer changed
                        tb, _ui, hdr, thdr = saved_map.get(int(sp.as_pointer()), (True, False, True, True))
                        _set_view3d_region_flags(
                            win,
                            area,
                            sp,
                            toolbar=tb,
                            header=hdr,
                            tool_header=thdr,
                            show_text=True,
                        )
    except Exception:
        pass

    _saved_region_flags.clear()
    _theme_applied = False
    return {"ok": True, "restored_attrs": restored}


def is_theme_applied() -> bool:
    return _theme_applied


def get_design_system_tokens() -> Dict[str, Any]:
    """Return the unified 3-layer Modern Maya Studio design system tokens (Blender Theme + GPU Overlays + Qt QSS)."""
    return {
        "palette": dict(MAYA_TOKENS),
        "layers": {
            "blender_theme": {
                "view3d_gradient_high": "#333940",
                "view3d_gradient_low": "#21262B",
                "active_selection_emerald": "#43DE8A",
                "component_selection_orange": "#F29E38",
                "panel_surface": MAYA_TOKENS["bg_panel"],
            },
            "gpu_overlays": {
                "strip_height_px": 26,
                "card_bg_rgba": (0.082, 0.098, 0.114, 0.85),
                "accent_teal_rgba": (0.22, 0.64, 0.85, 0.95),
                "live_emerald_rgba": (0.24, 0.65, 0.44, 0.85),
                "soft_select_amber_rgba": (0.94, 0.66, 0.22, 0.90),
            },
            "qt_docks": {
                "top_shelf_height_px": 104,
                "status_line_height_px": 32,
                "tool_box_width_px": 42,
                "right_edge_tab_strip_width_px": 26,
                "time_slider_height_px": 84,
            },
        },
    }


def verify_three_layer_theme_sync(dpi_scale: float = 1.0) -> Dict[str, Any]:
    """Audit unified visual tokens, shelf label lengths, and DPI scaling (`1.0x`, `1.25x`, `1.5x`)."""
    from . import shelf

    qss = get_studio_stylesheet()
    scale = max(0.75, min(2.5, float(dpi_scale or 1.0)))
    max_shelf_label_len = 0
    clipped_labels: List[str] = []
    for tab_name, items in shelf.SHELF_TABS.items():
        for item in items:
            lbl = str(item.get("label", ""))
            max_shelf_label_len = max(max_shelf_label_len, len(lbl))
            if len(lbl) > 10:
                clipped_labels.append(f"{tab_name}:{lbl}")

    return {
        "ok": len(clipped_labels) == 0 and bool(qss) and len(MAYA_TOKENS) >= 25,
        "dpi_scale": scale,
        "scaled_metrics": {
            "top_shelf_h": round(104.0 * scale, 1),
            "viewport_strip_h": round(26.0 * scale, 1),
            "channel_row_h": round(21.0 * scale, 1),
            "marking_menu_row_h": round(24.0 * scale, 1),
        },
        "theme_applied": _theme_applied,
        "saved_theme_attr_count": len(_saved_theme_attrs),
        "qss_length": len(qss),
        "max_shelf_label_len": max_shelf_label_len,
        "clipped_shelf_labels": clipped_labels,
    }
