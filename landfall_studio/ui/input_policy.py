"""Small native-widget rules used by Studio's existing application filter.

This does not translate mouse/pen contacts or own focus. Sculpt's pointer adapter
and Qt's native widgets retain those responsibilities.
"""


def studio_scope(widget):
    from PySide6 import QtWidgets
    while isinstance(widget, QtWidgets.QWidget):
        if widget.property('landfallStudioUi'):
            return widget
        widget = widget.parentWidget()
    return None


def handle_wheel(widget, event):
    """Plain wheel scrolls inspectors; Ctrl+wheel explicitly adjusts a value."""
    from PySide6 import QtCore, QtGui, QtWidgets
    if event.type() != QtCore.QEvent.Wheel or studio_scope(widget) is None:
        return False
    if QtWidgets.QApplication.activePopupWidget() is not None:
        return False
    if event.modifiers() & QtCore.Qt.ControlModifier:
        return False
    field = widget
    while isinstance(field, QtWidgets.QWidget):
        if isinstance(field, (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox, QtWidgets.QAbstractSlider)):
            if isinstance(field, QtWidgets.QScrollBar):
                return False
            parent = field.parentWidget()
            while isinstance(parent, QtWidgets.QWidget):
                if isinstance(parent, QtWidgets.QAbstractScrollArea):
                    viewport = parent.viewport()
                    local = viewport.mapFromGlobal(event.globalPosition().toPoint())
                    forwarded = QtGui.QWheelEvent(QtCore.QPointF(local), event.globalPosition(),
                        event.pixelDelta(), event.angleDelta(), event.buttons(), event.modifiers(),
                        event.phase(), event.inverted(), event.source())
                    QtWidgets.QApplication.sendEvent(viewport, forwarded)
                    event.accept()
                    return True
                parent = parent.parentWidget()
            event.accept()
            return True
        field = field.parentWidget()
    return False


def keeps_keyboard(widget, key, modifiers=None):
    """Dialogs and focused native pickers/buttons keep their normal key behavior."""
    from PySide6 import QtCore, QtWidgets
    if QtWidgets.QApplication.activeModalWidget() is not None:
        return True
    if isinstance(widget, QtWidgets.QWidget) and isinstance(widget.window(), QtWidgets.QDialog):
        return True
    focus = QtWidgets.QApplication.focusWidget()
    file_shortcut=bool(modifiers and modifiers & QtCore.Qt.ControlModifier) and key in (QtCore.Qt.Key_N,QtCore.Qt.Key_O,QtCore.Qt.Key_S,QtCore.Qt.Key_Q)
    if not file_shortcut and (isinstance(widget, QtWidgets.QComboBox) or isinstance(focus, QtWidgets.QComboBox)):
        return True
    if key in (QtCore.Qt.Key_Space, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
        return isinstance(widget, QtWidgets.QAbstractButton) or isinstance(focus, QtWidgets.QAbstractButton)
    return False
