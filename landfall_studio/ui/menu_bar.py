"""Use Qt's menu activation and popup grab lifecycle inside the hosted bar."""


def create_menu_bar():
    from PySide6 import QtWidgets

    # The embedded bar already has a Qt parent and a native Blender owner.
    # QMenuBar coordinates press/release, hover switching, keyboard navigation
    # and popup focus together. Manually activating/reparenting its QMenus can
    # dismiss a menu on the next native focus message after the opening click.
    bar=QtWidgets.QMenuBar()
    bar.setNativeMenuBar(False)
    return bar
