"""Editable PySide6 modeling caddy, backed by the lossless modeling snapshot."""
from __future__ import annotations


class CaddyPanel:
    def __init__(self, bar, state):
        from PySide6 import QtCore, QtWidgets
        from blendertk.ui_utils.qt_dock import QtDock
        from ..modeling.caddy import CADDY_SCHEMAS
        from . import style
        self.bar = bar
        self.key = (state["tool"], state["object_name"])
        self.fields = {}
        self.root = QtWidgets.QFrame()
        self.root.setObjectName("StudioModelingCaddy")
        style.apply_studio_style(self.root)
        layout = QtWidgets.QVBoxLayout(self.root)
        layout.addWidget(QtWidgets.QLabel(state["node_title"]))
        form = QtWidgets.QFormLayout()
        for spec in CADDY_SCHEMAS[state["tool"]]["params"]:
            key = spec["key"]
            if spec["type"] == "bool":
                field = QtWidgets.QCheckBox()
                field.toggled.connect(lambda value, k=key: self.change(k, value))
            else:
                field = QtWidgets.QSpinBox() if spec["type"] == "int" else QtWidgets.QDoubleSpinBox()
                field.setRange(spec["min"], spec["max"])
                field.setSingleStep(spec["step"])
                field.setKeyboardTracking(False)
                field.valueChanged.connect(lambda value, k=key: self.change(k, value))
            field.setObjectName("caddy_" + key)
            self.fields[key] = field
            form.addRow(spec["label"], field)
        layout.addLayout(form)
        row = QtWidgets.QHBoxLayout()
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.apply_button.clicked.connect(self.commit)
        self.cancel_button.clicked.connect(self.cancel)
        row.addWidget(self.apply_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self.root.setFixedWidth(340)
        self.root.adjustSize()
        self.helper = QtDock(editor="Info", area_header=False, focus_on_hover=True)
        self.helper._window, self.helper._hwnd = bar.window, bar.hwnd
        if not self.helper._embed(self.root, bar.hwnd):
            raise RuntimeError("Could not embed modeling caddy")
        self.sync(state)

    def change(self, key, value):
        from ..modeling.caddy import set_caddy_parameter
        self.bar.run(lambda: set_caddy_parameter(key, value))

    def commit(self):
        from ..modeling.caddy import commit_or_close_caddy
        self.bar.run(commit_or_close_caddy)

    def cancel(self):
        from ..modeling.caddy import cancel_caddy
        self.bar.run(cancel_caddy)

    def sync(self, state):
        from PySide6 import QtCore, QtWidgets
        from blendertk.ui_utils.blender_window import BlenderWindow
        for key, field in self.fields.items():
            # Do not overwrite text halfway through editing a number.
            if field.hasFocus():
                continue
            guard = QtCore.QSignalBlocker(field)
            if isinstance(field, QtWidgets.QCheckBox):
                field.setChecked(state["params"][key])
            else:
                field.setValue(state["params"][key])
            del guard
        x, y, width, height = self.bar.last_rect
        panel_height = self.root.sizeHint().height()
        BlenderWindow.move_child(int(self.root.winId()),
            (x + max(0, width - 350), y + height + 60, min(width, 340), panel_height))

    def teardown(self):
        self.helper._release_widget()
        self.root.hide()
        self.root.deleteLater()
