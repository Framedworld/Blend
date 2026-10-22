"""Hybrid editor windows (`landfall_studio.ui.hybrid_window`).

Hosts Blender-native editors (node canvases, Spreadsheet, Graph Editor, ...) in their own OS
window — Blender's analogue of Maya's floating editor windows — and can attach Studio Qt panels
to named areas of that window, using the same `WS_CHILD` embedding as the main docks.

- `open_editor_window(key)`: open (or raise) the window registered under `key` in `EDITOR_WINDOWS`.
- One window per key is reused, like the right dock's tear-off registry.
- Hosted windows are closed before a `.blend` save and reopened after it, so they never get
  stored in the file (Blender saves every open window into the file's window manager).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

# key -> spec. `splits`: (side, ui_type, size_px); `qt_panels`: (side, factory_name, size_px).
EDITOR_WINDOWS: Dict[str, Dict[str, Any]] = {
    "COMPONENT_EDITOR": {"title": "Component Editor", "ui_type": "SPREADSHEET", "size": (1100, 560)},
    "CONTENT_BROWSER": {"title": "Content Browser", "ui_type": "ASSETS", "size": (1100, 640)},
    "SCRIPT_EDITOR": {
        "title": "Script Editor",
        "ui_type": "INFO",
        "size": (980, 680),
        "splits": [("BOTTOM", "TEXT_EDITOR", 380)],
    },
    "GEOMETRY_NODE_EDITOR": {
        "title": "Geometry Node Editor",
        "ui_type": "GeometryNodeTree",
        "size": (1320, 820),
        "splits": [("BOTTOM", "SPREADSHEET", 220)],
        "qt_panels": [("RIGHT", "group_inputs", 300)],
    },
    "UV_EDITOR": {"title": "UV Editor", "ui_type": "UV", "size": (980, 820)},
    "HYPERSHADE_GRAPH": {"title": "Hypershade Work Area", "ui_type": "ShaderNodeTree", "size": (1200, 760)},
    "RENDER_SETTINGS": {"title": "Render Settings", "ui_type": "PROPERTIES", "size": (520, 820), "properties_context": "RENDER"},
    "COMPOSITOR": {"title": "Compositor", "ui_type": "CompositorNodeTree", "size": (1200, 760)},
    "RENDER_VIEW": {"title": "Render View", "ui_type": "IMAGE_EDITOR", "size": (1100, 760)},
    "GRAPH_EDITOR": {"title": "Graph Editor", "ui_type": "FCURVES", "size": (1200, 620)},
    "DOPE_SHEET": {"title": "Dope Sheet", "ui_type": "DOPESHEET", "size": (1200, 520)},
    "TIME_EDITOR": {"title": "Time Editor", "ui_type": "NLA_EDITOR", "size": (1200, 520)},
    "DRIVER_EDITOR": {"title": "Driver Editor", "ui_type": "DRIVERS", "size": (1200, 620)},
    "VIDEO_SEQUENCER": {"title": "Video Sequencer", "ui_type": "SEQUENCE_EDITOR", "size": (1280, 720)},
    "MOTION_TRACKING": {"title": "Motion Tracking", "ui_type": "CLIP_EDITOR", "size": (1280, 760)},
}

# Qt panel factories referenced by name from `qt_panels` (kept lazy so importing stays Qt-free).
QT_PANEL_FACTORIES: Dict[str, Callable[[], Any]] = {}

_open: Dict[str, Dict[str, Any]] = {}
_reopen_after_save: List[str] = []


def register_qt_panel_factory(name: str, factory: Callable[[], Any]) -> None:
    QT_PANEL_FACTORIES[name] = factory


def _window_region(area):
    for r in area.regions:
        if r.type == "WINDOW":
            return r
    return area.regions[0] if len(area.regions) else None


def _window_alive(win) -> bool:
    import bpy

    try:
        ptr = win.as_pointer()
    except (ReferenceError, AttributeError):
        return False
    return any(w.as_pointer() == ptr for w in bpy.context.window_manager.windows)


def _split(window, area, side: str, size_px: int):
    """Split `area` and return the new area on `side` (BOTTOM/TOP/LEFT/RIGHT) sized ~`size_px`."""
    import bpy

    vertical = side in ("LEFT", "RIGHT")
    total = area.width if vertical else area.height
    if total <= size_px + 80:
        return None
    frac = float(size_px) / float(total)
    factor = frac if side in ("BOTTOM", "LEFT") else 1.0 - frac
    before = {a.as_pointer() for a in window.screen.areas}
    try:
        with bpy.context.temp_override(window=window, screen=window.screen, area=area, region=_window_region(area)):
            res = bpy.ops.screen.area_split(direction="VERTICAL" if vertical else "HORIZONTAL", factor=max(0.05, min(0.95, factor)))
    except (RuntimeError, TypeError):
        return None
    if res != {"FINISHED"}:
        return None
    halves = [a for a in window.screen.areas if a.as_pointer() not in before] + [area]
    if side == "BOTTOM":
        return min(halves, key=lambda a: a.y)
    if side == "TOP":
        return max(halves, key=lambda a: a.y)
    if side == "LEFT":
        return min(halves, key=lambda a: a.x)
    return max(halves, key=lambda a: a.x)


def _set_native_window_frame(hwnd: Optional[int], title: str, size) -> Optional[int]:
    """Give the new GHOST window a Studio title and size (Windows only)."""
    try:
        import ctypes

        if not hwnd:
            return None
        user32 = ctypes.windll.user32
        user32.SetWindowTextW(ctypes.c_void_p(int(hwnd)), f"Landfall · {title}")
        if size:
            w, h = int(size[0]), int(size[1])
            sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            user32.SetWindowPos(ctypes.c_void_p(int(hwnd)), None, max(0, (sw - w) // 2), max(0, (sh - h) // 2), w, h, 0x0004 | 0x0010)
        return int(hwnd)
    except Exception:
        return None


def _embed_qt_panel(window, area, factory_name: str, hwnd: Optional[int]):
    """Embed a Studio Qt panel over `area` in `window` (GHOST handle `hwnd`); returns the QtDock (or None)."""
    factory = QT_PANEL_FACTORIES.get(factory_name)
    if factory is None:
        return None
    try:
        from blendertk.ui_utils.qt_dock import QtDock

        if not QtDock.supported():
            return None
        if not hwnd:
            return None
        widget = factory()
        dock = QtDock(editor="Info", area_header=False, focus_on_hover=True)
        dock._window, dock._area, dock._hwnd = window, area, hwnd
        dock._edge_pad = dock._native_edge_pad()
        dock._area_header = False
        dock._apply_area_header(window, area)
        if not dock._embed(getattr(widget, "root", widget), hwnd):
            return None
        dock._ctrl = widget
        dock._position(dock.content_region())
        dock._start_glue()
        return dock
    except Exception:
        return None


def open_editor_window(key: str) -> Dict[str, Any]:
    """Open the hosted editor window `key` (or raise it if already open)."""
    import bpy
    import blendertk as btk

    k = (key or "").upper()
    spec = EDITOR_WINDOWS.get(k)
    if spec is None:
        return {"ok": False, "error": f"Unknown editor window '{key}'"}

    entry = _open.get(k)
    if entry is not None and _window_alive(entry["window"]):
        try:
            import ctypes

            if entry.get("hwnd"):
                ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(int(entry["hwnd"])))
        except Exception:
            pass
        return {"ok": True, "key": k, "reused": True, "title": spec["title"]}

    if bpy.app.background:
        return {"ok": False, "key": k, "error": "Editor windows need the Blender GUI"}

    main = btk.main_window()
    if main is None or main.screen is None:
        return {"ok": False, "key": k, "error": "No main window"}
    src_area = next((a for a in main.screen.areas if a.type == "VIEW_3D"), main.screen.areas[0])
    before = {w.as_pointer() for w in bpy.context.window_manager.windows}
    try:
        with bpy.context.temp_override(window=main, screen=main.screen, area=src_area, region=_window_region(src_area)):
            bpy.ops.wm.window_new()
    except RuntimeError as exc:
        return {"ok": False, "key": k, "error": str(exc)}
    new_wins = [w for w in bpy.context.window_manager.windows if w.as_pointer() not in before]
    if not new_wins:
        return {"ok": False, "key": k, "error": "window_new did not open a window"}
    win = new_wins[0]
    area = win.screen.areas[0]
    try:
        area.ui_type = spec["ui_type"]
    except TypeError as exc:
        return {"ok": False, "key": k, "error": str(exc)}
    if spec.get("properties_context"):
        try:
            area.spaces.active.context = spec["properties_context"]
        except Exception:
            pass

    # Resolve the GHOST handle now: `window_hwnd` matches by client size, which the resize below changes
    hwnd = None
    try:
        from blendertk.ui_utils.blender_window import BlenderWindow

        hwnd = BlenderWindow.window_hwnd(win)
    except Exception:
        hwnd = None
    _set_native_window_frame(hwnd, spec["title"], spec.get("size"))

    side_areas: Dict[str, Any] = {}
    for side, ui_type, size_px in spec.get("splits", ()):
        sub = _split(win, area, side, size_px)
        if sub is not None:
            try:
                sub.ui_type = ui_type
            except TypeError:
                pass
            side_areas[side] = sub

    qt_docks = []
    for side, factory_name, size_px in spec.get("qt_panels", ()):
        sub = _split(win, area, side, size_px)
        if sub is None:
            continue
        try:
            sub.ui_type = "INFO"
        except TypeError:
            pass
        dock = _embed_qt_panel(win, sub, factory_name, hwnd)
        if dock is not None:
            qt_docks.append(dock)

    _open[k] = {"window": win, "hwnd": hwnd, "areas": side_areas, "qt_docks": qt_docks, "title": spec["title"]}
    _ensure_save_handlers()
    return {"ok": True, "key": k, "reused": False, "title": spec["title"], "qt_panels": len(qt_docks), "hwnd": hwnd}


def _release_entry(entry: Dict[str, Any]) -> None:
    for dock in entry.get("qt_docks", ()):
        try:
            dock.teardown()
        except Exception:
            pass
        ctrl = getattr(dock, "_ctrl", None)
        root = getattr(ctrl, "root", ctrl)
        try:
            root.hide()
            root.deleteLater()
        except Exception:
            pass


def close_editor_window(key: str) -> Dict[str, Any]:
    import bpy

    k = (key or "").upper()
    entry = _open.pop(k, None)
    if entry is None:
        return {"ok": True, "key": k, "closed": False}
    _release_entry(entry)
    win = entry["window"]
    closed = False
    if _window_alive(win):
        try:
            with bpy.context.temp_override(window=win, screen=win.screen):
                bpy.ops.wm.window_close()
            closed = True
        except Exception:
            closed = False
    return {"ok": True, "key": k, "closed": closed}


def list_editor_windows() -> List[Dict[str, Any]]:
    out = []
    for k, entry in list(_open.items()):
        if not _window_alive(entry["window"]):
            _release_entry(entry)
            _open.pop(k, None)
            continue
        w = entry["window"]
        out.append({"key": k, "title": entry["title"], "size": (int(w.width), int(w.height)), "qt_panels": len(entry.get("qt_docks", ())), "hwnd": entry.get("hwnd")})
    return out


def teardown_editor_windows() -> None:
    for k in list(_open.keys()):
        close_editor_window(k)
    _remove_save_handlers()


# --- keep hosted windows out of saved .blend files -------------------------------------
def _on_save_pre(*_args) -> None:
    _reopen_after_save.clear()
    for k in list(_open.keys()):
        _reopen_after_save.append(k)
        close_editor_window(k)


def _on_save_post(*_args) -> None:
    keys = list(_reopen_after_save)
    _reopen_after_save.clear()
    if not keys:
        return
    import bpy

    def _reopen():
        for k in keys:
            open_editor_window(k)
        return None

    bpy.app.timers.register(_reopen, first_interval=0.05)


def _ensure_save_handlers() -> None:
    import bpy

    if _on_save_pre not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(_on_save_pre)
    if _on_save_post not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(_on_save_post)


def _remove_save_handlers() -> None:
    try:
        import bpy

        if _on_save_pre in bpy.app.handlers.save_pre:
            bpy.app.handlers.save_pre.remove(_on_save_pre)
        if _on_save_post in bpy.app.handlers.save_post:
            bpy.app.handlers.save_post.remove(_on_save_post)
    except Exception:
        pass
