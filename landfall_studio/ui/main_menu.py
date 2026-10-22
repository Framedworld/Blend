"""Main Menu Bar (`landfall_studio.ui.main_menu`).

One 32px row replacing Blender's top bar, as in Maya:
logo · common menus (File … Windows) · menu-set menus (Mesh, Edit Mesh … for Modeling) · Help ·
Workspace dropdown on the right.

Blender has no API to hide its top bar, so `MainMenuBarQtDock` embeds the Qt row as a
`WS_CHILD` of the main window and keeps it glued over the top bar strip (the band above the
top-most screen area), re-syncing on a timer like the bottom Time Slider dock.
"""

from __future__ import annotations

from typing import Any, List, Optional

from . import menus, style

WORKSPACE_PRESETS = (
    "Modeling Standard",
    "Maya Classic",
    "Lookdev / Hypershade",
    "FX & Geometry Nodes",
    "Rigging & Deform",
    "Sculpt & Remesh Studio",
    "Pipeline & .ma",
)

_active_menu_set: str = "Modeling"
_bar_instances: List["MainMenuBarWidget"] = []
_menu_dock: Optional["MainMenuBarQtDock"] = None


def get_active_menu_set() -> str:
    return _active_menu_set


def set_menu_set(name: str) -> dict:
    """Switch the right-hand menus to menu set `name` (Modeling, Rigging, Animation, FX, Rendering)."""
    global _active_menu_set
    clean = next((n for n in menus.MENU_SET_NAMES if n.lower() == (name or "").split()[0].lower()), "Modeling")
    _active_menu_set = clean
    for bar in list(_bar_instances):
        try:
            bar.rebuild_menu_set()
        except Exception:
            pass
    return {"ok": True, "menu_set": clean, "menus": [m for m, _ in menus.MENU_SETS[clean]]}


def sync_workspace_selector(preset: str) -> None:
    for bar in list(_bar_instances):
        try:
            idx = bar.cmb_workspace.findText(preset)
            if idx >= 0 and bar.cmb_workspace.currentIndex() != idx:
                bar.cmb_workspace.blockSignals(True)
                bar.cmb_workspace.setCurrentIndex(idx)
                bar.cmb_workspace.blockSignals(False)
        except Exception:
            pass


class MainMenuBarWidget:
    """Logo + QMenuBar (common + menu-set menus + Help) + Workspace dropdown."""

    def __init__(self, parent: Any = None):
        from qtpy import QtCore, QtWidgets
        from .shelf import _create_maya_hex_logo_widget

        self.root = QtWidgets.QFrame(parent)
        self.root.setObjectName("MayaMainMenuBar")
        style.apply_studio_style(self.root)
        self.root.setFixedHeight(26)
        lay = QtWidgets.QHBoxLayout(self.root)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)
        lay.addWidget(_create_maya_hex_logo_widget())

        from .menu_bar import create_menu_bar
        self.menubar = create_menu_bar()
        self.menubar.setObjectName("MayaMenuBar")
        self.menubar.setStyleSheet('QMenuBar {font-size:11px;} QMenuBar::item {padding:2px 8px;}')
        self.menubar.setNativeMenuBar(False)
        self.menubar.setFixedHeight(26)
        lay.addWidget(self.menubar, 1)
        lay.addStretch(1)
        self._set_menu_actions: List[Any] = []
        for title, entries in menus.COMMON_MENUS:
            m = self.menubar.addMenu(title)
            menus.build_qmenu(m, entries)
        self._sep_action = self.menubar.addSeparator()
        self._help_menu = QtWidgets.QMenu("Help", self.menubar)
        menus.build_qmenu(self._help_menu, menus.HELP_MENU)
        self.rebuild_menu_set()

        lbl = QtWidgets.QLabel("Workspace:")
        lbl.setObjectName("MayaMutedLabel")
        lay.addWidget(lbl)
        self.cmb_workspace = QtWidgets.QComboBox()
        self.cmb_workspace.addItems(list(WORKSPACE_PRESETS))
        self.cmb_workspace.setFixedWidth(170)
        self.cmb_workspace.setFixedHeight(24)
        self.cmb_workspace.currentIndexChanged.connect(self._on_workspace_changed)
        lay.addWidget(self.cmb_workspace)
        _bar_instances.append(self)

    def rebuild_menu_set(self) -> None:
        from qtpy import QtWidgets

        for act in self._set_menu_actions:
            self.menubar.removeAction(act)
            menu = act.menu()
            if menu is not None and menu is not self._help_menu:
                menu.deleteLater()
            elif menu is None:
                act.deleteLater()
        self._set_menu_actions = []
        for title, entries in menus.MENU_SETS[_active_menu_set]:
            m = QtWidgets.QMenu(title, self.menubar)
            menus.build_qmenu(m, entries)
            self._set_menu_actions.append(self.menubar.addMenu(m))
        sep = self.menubar.addSeparator()
        self._set_menu_actions.append(sep)
        self._set_menu_actions.append(self.menubar.addMenu(self._help_menu))
        self.menubar.setFixedWidth(self.menubar.sizeHint().width()+12)

    def menu_titles(self) -> List[str]:
        return [a.text() for a in self.menubar.actions() if a.text()]

    def set_sculpt_mode(self,enabled):
        from . import zbrush_panel as sculpt_ui
        if not hasattr(self,'_sculpt_actions'):
            from PySide6 import QtWidgets
            self._sculpt_actions=[]
            from ..sculpt import brushes,ops
            specs={
                'Brush':[(v[0]+'\tB '+k[0]+' '+k[1],lambda c=k:sculpt_ui.command('BRUSH',name=c)) for k,v in brushes.CATALOG.items()],
                'Stroke':[(x.title(),lambda m=x:sculpt_ui.command('STROKE',method=m)) for x in ('SPACE','DOTS','DRAG_DOT','ANCHORED','AIRBRUSH')],
                'Alpha':[(label,lambda a=key:sculpt_ui.command('STROKE',alpha=a)) for key,label in [('NONE','Round'),('SQUARE','Square'),('NOISE','Noise')]],
                'Material':[(n,lambda name=n:sculpt_ui.command('MATCAP',name=name)) for n in ops.MATCAPS],
                'Tool':[(label,lambda cmd=a:sculpt_ui.command(cmd)) for label,a in [('Divide','DIVIDE'),('Re-DynaMesh','DYNAMESH'),('ZRemesher','ZREMESHER'),('Reset Current Brush','RESET_BRUSH'),('GoZ Return','RETURN')]]}
            for title,entries in specs.items():
                menu=QtWidgets.QMenu(title,self.menubar)
                for label,fn in entries:menu.addAction(label).triggered.connect(lambda _,f=fn:f())
                self._sculpt_actions.append(self.menubar.addMenu(menu))
        for action in self.menubar.actions():
            action.setVisible(enabled if action in self._sculpt_actions else (not enabled or action.text() in ('File','Edit','Windows','Help')))
        self.menubar.setFixedWidth(self.menubar.sizeHint().width()+12)

    def _on_workspace_changed(self, idx: int) -> None:
        from . import desktop
        try:
            desktop.apply_workspace_layout(self.cmb_workspace.itemText(idx))
        except Exception as exc:
            desktop.set_command_feedback('Workspace',str(exc),'ERROR')
            sync_workspace_selector(desktop.get_active_workspace_layout())


class MainMenuBarQtDock:
    """Keeps `MainMenuBarWidget` embedded over Blender's top bar strip in the main window."""

    SYNC_INTERVAL = 0.2

    def __init__(self):
        self.ctrl: Optional[MainMenuBarWidget] = None
        self._hwnd: Optional[int] = None
        self._window = None
        self._last_rect = None
        self._timer = None
        self._embedded = False

    @property
    def widget(self):
        return self.ctrl.root if self.ctrl is not None else None

    @staticmethod
    def topbar_client_rect(window, hwnd) -> Optional[tuple]:
        """(x, y, w, h) of the band above the top-most screen area, in client coords."""
        from blendertk.ui_utils.blender_window import BlenderWindow
        import bpy
        window=next((w for w in bpy.context.window_manager.windows if BlenderWindow.window_hwnd(w)==hwnd),None)

        size = BlenderWindow.client_size(hwnd)
        if size is None or window is None or window.screen is None:
            return None
        try:
            top = max(int(a.y) + int(a.height) for a in window.screen.areas)
        except (ValueError, ReferenceError):
            return None
        h = int(window.height) - top
        if h <= 4:
            return None
        return (0, 0, int(size[0]), h)

    def dock(self) -> bool:
        import bpy
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow
        from blendertk.ui_utils.qt_dock import QtDock

        if bpy.app.background or not QtDock.supported():
            return False
        if self.ctrl is None:
            self.ctrl = MainMenuBarWidget()
        window = btk.main_window()
        hwnd = BlenderWindow.window_hwnd(window) if window is not None else None
        if not hwnd:
            return False
        self._window, self._hwnd = window, hwnd
        if not self._embedded:
            helper = QtDock(editor="Info", area_header=False, focus_on_hover=True)
            helper._window, helper._hwnd = window, hwnd
            if not helper._embed(self.ctrl.root, hwnd):
                return False
            self._helper = helper
            self._embedded = True
        self._last_rect = None
        self.sync()
        if self._timer is None:
            self._timer = self._tick
            bpy.app.timers.register(self._timer, first_interval=self.SYNC_INTERVAL, persistent=True)
        return True

    def sync(self) -> Optional[tuple]:
        import bpy
        from ..sculpt import layout
        if layout.focus:
            if self.ctrl:self.ctrl.root.hide()
            return None
        from blendertk.ui_utils.blender_window import BlenderWindow

        if self.ctrl is None or self._hwnd is None:
            return None
        live=next((w for w in bpy.context.window_manager.windows if BlenderWindow.window_hwnd(w)==self._hwnd),None)
        if live is not None:
            self._window=live
            from .desktop import sync_window_size
            sync_window_size(live)
        rect = self.topbar_client_rect(self._window, self._hwnd)
        if rect is None:
            return self._last_rect
        if rect != self._last_rect:
            try:
                available=max(60,int(rect[2]/self.ctrl.root.devicePixelRatioF())-330)
                self.ctrl.menubar.setFixedWidth(min(available,self.ctrl.menubar.sizeHint().width()+12))
                BlenderWindow.move_child(int(self.ctrl.root.winId()), rect)
                self.ctrl.root.show()
                self._last_rect = rect
            except Exception:
                return None
        return self._last_rect

    def _tick(self):
        from blendertk.ui_utils.blender_window import BlenderWindow

        if self.ctrl is None or not BlenderWindow.is_window(self._hwnd):
            self._timer = None
            return None
        self.sync()
        return self.SYNC_INTERVAL

    def enforce_dock_geometry(self) -> Optional[tuple]:
        self._last_rect = None
        return self.sync()

    def teardown(self) -> None:
        import bpy

        if self._timer is not None:
            try:
                bpy.app.timers.unregister(self._timer)
            except Exception:
                pass
            self._timer = None
        helper = getattr(self, "_helper", None)
        if helper is not None:
            try:
                helper._release_widget()
            except Exception:
                pass
        if self.ctrl is not None:
            try:
                if self.ctrl in _bar_instances:
                    _bar_instances.remove(self.ctrl)
                self.ctrl.root.hide()
                self.ctrl.root.deleteLater()
            except Exception:
                pass
        self.ctrl = None
        self._embedded = False
        self._hwnd = self._window = None


def get_main_menu_dock() -> MainMenuBarQtDock:
    global _menu_dock
    if _menu_dock is None:
        _menu_dock = MainMenuBarQtDock()
    return _menu_dock


def dock_main_menu() -> dict:
    ok = get_main_menu_dock().dock()
    return {"ok": ok, "rect": get_main_menu_dock()._last_rect}


def teardown_main_menu() -> None:
    global _menu_dock
    if _menu_dock is not None:
        _menu_dock.teardown()
        _menu_dock = None
