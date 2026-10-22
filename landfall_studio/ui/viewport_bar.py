"""Real PySide6 menus and controls embedded above each Blender viewport.

The rendering canvas and transform gizmos remain Blender's native editors.
Every apparent button in this strip is a QWidget with a connected action.
"""
from __future__ import annotations

from typing import Any

_bars: dict = {}
_timer = None
HEIGHT = 30


class ViewportBar:
    def __init__(self, window, area, hwnd):
        from PySide6 import QtCore, QtWidgets
        from blendertk.ui_utils.qt_dock import QtDock
        from . import style

        self.window, self.area, self.hwnd = window, area, hwnd
        self.caddy = None
        self.sculpt_canvas = None
        self.root = QtWidgets.QFrame()
        self.root.setObjectName("StudioViewportBar")
        self.root.setFocusPolicy(QtCore.Qt.NoFocus)
        style.apply_studio_style(self.root)
        layout = QtWidgets.QHBoxLayout(self.root)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(3)
        from .menu_bar import create_menu_bar
        self.menubar = create_menu_bar()
        self.menubar.setObjectName("MayaPanelMenuBar")
        self.menubar.setNativeMenuBar(False)
        self.menubar.setFixedHeight(26)
        self.menubar.setFocusPolicy(QtCore.Qt.NoFocus)
        layout.addWidget(self.menubar)
        self.buttons: dict[str, Any] = {}
        self.actions: dict[str, Any] = {}
        self._build_menus()
        self.menubar.setFixedWidth(max(360, self.menubar.sizeHint().width() + 12))
        self.scroller = QtWidgets.QScrollArea()
        self.scroller.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroller.setWidgetResizable(True)
        self.scroller.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroller.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        contents = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(contents)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        for key, label, tip in (
            ("4", "4 Wire", "Wireframe (4)"), ("5", "5 Shaded", "Smooth shaded (5)"),
            ("6", "6 Textured", "Materials with studio lighting (6)"),
            ("7", "7 All Lights", "Materials with scene lighting (7)"),
            ("WIRE_ON_SHADED", "Wire", "Wireframe on shaded"),
            ("XRAY", "X-Ray", "X-Ray selection (switches to solid shading)"),
            ("SSAO", "SSAO", "Screen-space ambient occlusion"),
            ("SHADOWS", "Shadows", "Viewport shadows"),
        ):
            button = QtWidgets.QToolButton()
            button.setObjectName("viewport_" + key)
            button.setText(label)
            button.setToolTip(tip)
            button.setCheckable(True)
            button.setFocusPolicy(QtCore.Qt.NoFocus)
            button.clicked.connect(lambda _=False, k=key: self.shading(k))
            row.addWidget(button)
            self.buttons[key] = button
        self.renderer = QtWidgets.QLabel()
        self.renderer.setObjectName("MayaMutedLabel")
        row.addWidget(self.renderer)
        row.addStretch(1)
        self.scroller.setWidget(contents)
        layout.addWidget(self.scroller, 1)
        self.helper = QtDock(editor="Info", area_header=False, focus_on_hover=True)
        from .zbrush_panel import button
        self.sculpt_strip=QtWidgets.QWidget();strip=QtWidgets.QHBoxLayout(self.sculpt_strip);strip.setContentsMargins(0,0,0,0)
        from .sculpt_input import polish
        polish(self.sculpt_strip)
        display=QtWidgets.QToolButton();display.setText('Display');display.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        display_menu=QtWidgets.QMenu(display)
        for action in self.menubar.actions():display_menu.addAction(action)
        display.setMenu(display_menu);strip.addWidget(display)
        for label,fn in [('Brushes B',lambda:__import__(__package__+'.sculpt_widgets',fromlist=['show_brush_palette']).show_brush_palette()),
            ('Quick · Space',lambda:__import__(__package__+'.sculpt_widgets',fromlist=['show_quick']).show_quick()),
            ('Tool tray',lambda:__import__('landfall_studio.sculpt.layout',fromlist=['toggle_tray']).toggle_tray()),
            ('Focus · Tab',lambda:__import__('landfall_studio.sculpt.layout',fromlist=['toggle_focus']).toggle_focus()),
            ('?',lambda:__import__('landfall_studio.sculpt.ops',fromlist=['run']).run('TOGGLE',field='show_shortcut_hud'))]:
            strip.addWidget(button(label,callback=lambda _,f=fn:self.run(f)))
        strip.addStretch(1);layout.addWidget(self.sculpt_strip);self.sculpt_strip.hide()
        self.helper._window, self.helper._hwnd = window, hwnd
        if not self.helper._embed(self.root, hwnd):
            self.root.deleteLater()
            raise RuntimeError("Could not embed the viewport control strip")
        self.last_rect = None
        self.sync()

    def context(self):
        import bpy
        windows=list(bpy.context.window_manager.windows)
        window=next((w for w in windows if w==self.window),windows[0] if windows else None)
        if window is None:raise RuntimeError('No Blender window is available.')
        area=next((a for a in window.screen.areas if a==self.area),None)
        if area is None:area=next((a for a in window.screen.areas if a.type=='VIEW_3D'),None)
        if area is None:raise RuntimeError('Open a 3D viewport to use this command.')
        self.window,self.area=window,area
        return {"window": window, "screen": window.screen, "area": area,
                "region": next(r for r in area.regions if r.type == "WINDOW")}

    def run(self, action):
        import bpy
        from . import desktop
        from .hotkey_passthrough import _return_os_focus_to_blender
        try:
            with bpy.context.temp_override(**self.context()):
                result = action()
            if isinstance(result, dict) and not result.get("ok", True):
                raise RuntimeError(result.get("error", str(result)))
            desktop.set_command_feedback("Viewport", str(result), "INFO")
        except Exception as exc:
            desktop.set_command_feedback("Viewport", str(exc), "ERROR")
            result = {"ok": False, "error": str(exc)}
        self.refresh()
        _return_os_focus_to_blender()
        return result

    def sync_caddy(self):
        from ..modeling.caddy import get_active_caddy_state
        from .caddy_panel import CaddyPanel
        state = get_active_caddy_state()
        key = (state.get("tool"), state.get("object_name"))
        if self.caddy is not None and (not state["open"] or self.caddy.key != key):
            self.caddy.teardown()
            self.caddy = None
        if state["open"]:
            if self.caddy is None:
                self.caddy = CaddyPanel(self, state)
            self.caddy.sync(state)

    def shading(self, mode):
        from .. import continuity
        return self.run(lambda: continuity.set_maya_viewport_shading(mode))

    def _build_menus(self):
        import bpy
        from . import desktop, main_menu
        from .. import continuity
        from ..viewport import hud

        def item(menu, key, label, fn):
            action = menu.addAction(label)
            action.setObjectName("viewport_action_" + key)
            action.triggered.connect(lambda _=False, f=fn: self.run(f))
            self.actions[key] = action

        view = self.menubar.addMenu("View")
        item(view, "frame_selected", "Frame Selected\tF", lambda: bpy.ops.landfall.frame_selected())
        item(view, "frame_all", "Frame All\tA", lambda: bpy.ops.landfall_studio.frame_all())
        for label, axis in (("Perspective / Orthographic", None), ("Front", "FRONT"),
                            ("Back", "BACK"), ("Left", "LEFT"), ("Right", "RIGHT"),
                            ("Top", "TOP"), ("Bottom", "BOTTOM")):
            item(view, "view_" + str(axis), label,
                 (lambda: bpy.ops.view3d.view_persportho()) if axis is None else
                 (lambda a=axis: bpy.ops.view3d.view_axis(type=a)))
        item(view, "isolate", "Isolate Selection", lambda: bpy.ops.view3d.localview())
        shading = self.menubar.addMenu("Shading")
        for mode, label in (("4", "Wireframe"), ("5", "Smooth Shaded"), ("6", "Textured"),
                            ("7", "Use All Lights"), ("WIRE_ON_SHADED", "Wire on Shaded"), ("XRAY", "X-Ray")):
            item(shading, "shade_" + mode, label, lambda m=mode: continuity.set_maya_viewport_shading(m))
        lighting = self.menubar.addMenu("Lighting")
        for mode, label in (("SSAO", "Ambient Occlusion"), ("SHADOWS", "Shadows"),
                            ("RAYTRACING", "Raytracing"), ("STUDIO_RIG", "Create Studio Light Rig")):
            item(lighting, "light_" + mode, label, lambda m=mode: continuity.set_maya_viewport_shading(m))
        show = self.menubar.addMenu("Show")
        for attr, label in (("show_floor", "Grid"), ("show_overlays", "Overlays"),
                            ("show_outline_selected", "Selection Outline"), ("show_extras", "Cameras / Lights")):
            item(show, attr, label, lambda a=attr: self._toggle_overlay(a))
        item(show, "hud", "Poly Count HUD", lambda: hud.set_hud_enabled(not hud.get_hud_state().get("enabled", True)))
        renderer = self.menubar.addMenu("Renderer")
        for engine, label in (("EEVEE", "Viewport 2.0 (EEVEE)"), ("CYCLES", "Cycles")):
            item(renderer, "renderer_" + engine, label, lambda e=engine: continuity.set_viewport_renderer(e))
        panels = self.menubar.addMenu("Panels")
        item(panels, "quad", "Four View / Single View", lambda: bpy.ops.screen.region_quadview())
        for preset in main_menu.WORKSPACE_PRESETS:
            item(panels, "layout_" + preset, preset, lambda p=preset: desktop.apply_workspace_layout(p))

    def _toggle_overlay(self, attr):
        import bpy
        overlay = self.area.spaces.active.overlay
        if attr == "show_floor" and hasattr(bpy.context.scene, "landfall_grid_finite"):
            visible = bool(bpy.context.scene.landfall_grid_finite or overlay.show_floor)
            bpy.context.scene.landfall_grid_finite = not visible
            if visible:
                overlay.show_floor = False
            return {"ok": True, "grid_visible": not visible}
        setattr(overlay, attr, not getattr(overlay, attr))
        return {"ok": True, attr: getattr(overlay, attr)}

    def refresh(self):
        import bpy
        from .. import continuity
        with bpy.context.temp_override(**self.context()):
            state = continuity.get_viewport_shading_state()
        values = {str(i): state["maya_mode"] == str(i) for i in (4, 5, 6, 7)}
        values.update(WIRE_ON_SHADED=state["wire_on_shaded"], XRAY=state["xray"],
                      SSAO=state["eevee_ssao"], SHADOWS=state["eevee_shadows"])
        for key, button in self.buttons.items():
            button.setChecked(values[key])
        checked={**{'shade_'+k:v for k,v in values.items()},'light_SSAO':state['eevee_ssao'],
            'light_SHADOWS':state['eevee_shadows'],'light_RAYTRACING':state['eevee_raytracing'],
            'isolate':state['isolated'],'renderer_EEVEE':state['renderer_engine'].startswith('BLENDER_EEVEE'),
            'renderer_CYCLES':state['renderer_engine']=='CYCLES'}
        overlay=self.area.spaces.active.overlay
        for attr in ('show_floor','show_overlays','show_outline_selected','show_extras'):
            checked[attr]=bool(getattr(overlay,attr))
        checked['show_floor']=bool(overlay.show_floor or getattr(bpy.context.scene,'landfall_grid_finite',False))
        from ..viewport import hud
        checked['hud']=hud.get_hud_state().get('enabled',False)
        for key,value in checked.items():
            action=self.actions.get(key)
            if action is not None:action.setCheckable(True);action.setChecked(value)
        self.renderer.setText(state["renderer_label"])
        for region in self.area.regions:
            region.tag_redraw()

    def sync(self):
        import bpy
        from ..sculpt import layout as sculpt_layout,is_engaged
        sculpt=bpy.context.mode=='SCULPT' and is_engaged()
        self.menubar.setVisible(not sculpt);self.scroller.setVisible(not sculpt);self.sculpt_strip.setVisible(sculpt)
        from blendertk.ui_utils.blender_window import BlenderWindow
        region = next(r for r in self.area.regions if r.type == "WINDOW")
        rect = BlenderWindow.region_client_rect(self.hwnd, region)
        if rect is None:
            return
        x, y, width, height = rect
        rect = (x, y, width, min(HEIGHT, height))
        if rect != self.last_rect:
            BlenderWindow.move_child(int(self.root.winId()), rect)
            self.root.show()
            self.last_rect = rect
        if sculpt_layout.focus:self.root.hide()
        elif not self.root.isVisible():self.root.show()
        self.refresh()
        self.sync_caddy()
        if hasattr(__import__('bpy').context.scene, 'landfall_sculpt'):
            from ..viewport.sculpt_hud import SculptCanvas
            if self.sculpt_canvas is None:
                self.sculpt_canvas = SculptCanvas(self)
            self.sculpt_canvas.sync()

    def teardown(self):
        if self.sculpt_canvas is not None:
            self.sculpt_canvas.teardown()
        if self.caddy is not None:
            self.caddy.teardown()
        self.helper._release_widget()
        self.root.hide()
        self.root.deleteLater()


def _sync():
    import bpy
    from blendertk.ui_utils.blender_window import BlenderWindow
    live = set()
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            key = (win.as_pointer(), area.as_pointer())
            live.add(key)
            if key not in _bars:
                hwnd = BlenderWindow.window_hwnd(win)
                if hwnd:
                    _bars[key] = ViewportBar(win, area, hwnd)
            if key in _bars:
                _bars[key].window=win
                _bars[key].area=area
                _bars[key].sync()
    for key in set(_bars) - live:
        _bars.pop(key).teardown()
    return 0.25


def register():
    global _timer
    import bpy
    if bpy.app.background or _timer is not None:
        return
    _sync()
    _timer = _sync
    bpy.app.timers.register(_timer, first_interval=0.25, persistent=True)


def unregister():
    global _timer
    import bpy
    if _timer is not None and bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)
    _timer = None
    for bar in _bars.values():
        bar.teardown()
    _bars.clear()


def get_bars():
    return list(_bars.values())
