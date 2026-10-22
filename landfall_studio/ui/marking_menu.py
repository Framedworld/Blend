"""PySide6 radial menu surface for Studio's existing marking-menu actions."""
from __future__ import annotations


class QtMarkingMenu:
    def __init__(self, operator, window, area, region):
        from PySide6 import QtCore, QtGui, QtWidgets
        from blendertk.ui_utils.blender_window import BlenderWindow
        from . import style
        self.operator, self.window, self.area, self.region = operator, window, area, region
        owner = self

        class Surface(QtWidgets.QWidget):
            def mouseMoveEvent(self, event):
                from ..viewport import marking_menus as mm
                mm._studio_mm["cursor_x"] = event.position().x() * owner.dpr
                mm._studio_mm["cursor_y"] = region.height - event.position().y() * owner.dpr
                self.update()

            def mousePressEvent(self, event):
                if event.button() == QtCore.Qt.LeftButton:
                    owner.close()

            def mouseReleaseEvent(self, event):
                if event.button() != QtCore.Qt.RightButton:
                    return
                from ..viewport import marking_menus as mm
                x, y = event.position().x() * owner.dpr, region.height - event.position().y() * owner.dpr
                if (x-mm._studio_mm["x"])**2 + (y-mm._studio_mm["y"])**2 <= mm.DEAD_ZONE_PX**2:
                    return
                hit = mm._studio_mm_hit(x, y)
                owner.activate(hit) if hit is not None else owner.close()

            def keyPressEvent(self, event):
                if event.key() == QtCore.Qt.Key_Escape:
                    owner.close()
                else:
                    super().keyPressEvent(event)

            def paintEvent(self, event):
                from ..viewport import marking_menus as mm
                painter = QtGui.QPainter(self)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                origin = QtCore.QPointF(mm._studio_mm["x"]/owner.dpr, (region.height-mm._studio_mm["y"])/owner.dpr)
                cursor = QtCore.QPointF(mm._studio_mm["cursor_x"]/owner.dpr, (region.height-mm._studio_mm["cursor_y"])/owner.dpr)
                painter.setPen(QtGui.QPen(QtGui.QColor("#38A3D8"), 2))
                painter.drawLine(origin, cursor)
                painter.drawEllipse(origin, 7, 7)
                painter.end()

        self.root = Surface()
        self.root.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.root.setObjectName("StudioQtMarkingMenu")
        self.root.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.root.setMouseTracking(True)
        self.root.setFocusPolicy(QtCore.Qt.StrongFocus)
        style.apply_studio_style(self.root)
        self.buttons = {}
        hwnd = BlenderWindow.window_hwnd(window)
        # An owned translucent top-level is required. A viewport-sized native
        # child would make WS_CLIPCHILDREN suppress the entire Blender canvas.
        BlenderWindow.set_owner(self.root, hwnd)
        rect = BlenderWindow.region_client_rect(hwnd, region)
        import ctypes
        origin = (ctypes.c_long * 2)(rect[0], rect[1])
        ctypes.windll.user32.ClientToScreen(ctypes.c_void_p(hwnd), ctypes.byref(origin))
        self.root.show()
        self.dpr = self.root.devicePixelRatioF()
        BlenderWindow.move_child(int(self.root.winId()), (origin[0], origin[1], rect[2], rect[3]))
        self.root.raise_()
        self.root.setFocus()
        self.rebuild()

    def context(self):
        return {"window": self.window, "screen": self.window.screen, "area": self.area, "region": self.region}

    def rebuild(self):
        import bpy
        from PySide6 import QtCore, QtWidgets
        from ..viewport import marking_menus as mm
        for button in self.buttons.values():
            button.hide()
            button.deleteLater()
        self.buttons.clear()
        with bpy.context.temp_override(**self.context()):
            mm._build_mm_layout(bpy.context)
        layout = mm._studio_mm["layout"]
        for item in layout["chips"] + layout["rows"]:
            button = QtWidgets.QPushButton(item["label"], self.root)
            button.setObjectName("marking_" + str(item["key"]))
            button.setFocusPolicy(QtCore.Qt.NoFocus)
            button.setGeometry(int(item["x"]/self.dpr), int((self.region.height-item["y"]-item["h"])/self.dpr),
                               int(item["w"]/self.dpr), int(item["h"]/self.dpr))
            button.clicked.connect(lambda _=False, k=item["key"]: self.activate(k))
            button.show()
            self.buttons[item["key"]] = button

    def activate(self, hit):
        import bpy
        from ..viewport import marking_menus as mm
        with bpy.context.temp_override(**self.context()):
            closed = self.operator._activate_hit(bpy.context, hit)
        if not closed and mm._studio_mm["open"]:
            self.rebuild()

    def close(self):
        from ..viewport.marking_menus import stop_studio_marking_menu
        stop_studio_marking_menu()

    def teardown(self):
        from .hotkey_passthrough import _return_os_focus_to_blender
        self.root.hide()
        self.root.deleteLater()
        _return_os_focus_to_blender()
