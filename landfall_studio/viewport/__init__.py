"""Viewport interaction and marking menu modules for Landfall Studio."""

from .interaction import (
    INTERACTION_CLASSES,
    apply_gizmo_for_tool,
    compute_pivot_snap_target,
    find_view3d_area_region,
    get_pivot_modal_state,
    raycast_mesh_at_region_xy,
    snap_object_pivot_world,
)
from .marking_menus import (
    MARKING_MENU_CLASSES,
    get_marking_menu_state,
    register_marking_menu_handlers,
    stop_studio_marking_menu,
    unregister_marking_menu_handlers,
)

VIEWPORT_CLASSES = INTERACTION_CLASSES + MARKING_MENU_CLASSES

__all__ = [
    "INTERACTION_CLASSES",
    "MARKING_MENU_CLASSES",
    "VIEWPORT_CLASSES",
    "apply_gizmo_for_tool",
    "compute_pivot_snap_target",
    "find_view3d_area_region",
    "get_marking_menu_state",
    "get_pivot_modal_state",
    "raycast_mesh_at_region_xy",
    "register_marking_menu_handlers",
    "snap_object_pivot_world",
    "stop_studio_marking_menu",
    "unregister_marking_menu_handlers",
]
