"""Gate 05 — Modeling Caddies, `TargetWeld`, Scoped `Make Live`, `Quad Draw`, Scene Diagnostics, and UV/Material Utilities (`landfall_studio.modeling`)."""

from __future__ import annotations

from .caddy import (
    CADDY_SCHEMAS,
    activate_target_weld,
    commit_caddy,
    commit_or_close_caddy,
    get_active_caddy_state,
    invoke_modeling_caddy,
    scrub_caddy_parameter,
    set_caddy_parameter,
    weld_vertices_target_weld,
)
from .diagnostics_uv import (
    center_or_bake_pivot_guarded,
    delete_non_deformer_history,
    freeze_transformations_guarded,
    get_mesh_texel_density,
    inspect_construction_history,
    run_scene_diagnostics,
    set_mesh_texel_density,
    snapshot_material_assignments,
    uv_cleanup_sets_guarded,
    uv_unwrap_and_pack,
)
from .live_surface import (
    clear_live_surface,
    get_live_surface_object,
    get_live_surface_state,
    project_mesh_to_live_surface,
    project_point_to_live_surface,
    set_live_surface,
)
from .ops import MODELING_CLASSES
from .quad_draw import (
    clear_quad_draw_dots,
    ensure_retopo_mesh,
    extrude_quad_draw_strip,
    fill_quad_from_dots,
    get_quad_draw_dots,
    get_quad_draw_overlay_data,
    insert_quad_draw_loop,
    is_quad_draw_active,
    plot_quad_draw_dot,
    relax_quad_draw_verts,
    set_quad_draw_active,
)


def clear_modeling_state() -> None:
    """Reset transient modeling caddy, Quad Draw dots, and Make Live cache on unregister."""
    commit_or_close_caddy()
    clear_quad_draw_dots()
    set_quad_draw_active(False)
    try:
        clear_live_surface()
    except Exception:
        pass


__all__ = [
    "CADDY_SCHEMAS",
    "MODELING_CLASSES",
    "activate_target_weld",
    "center_or_bake_pivot_guarded",
    "clear_live_surface",
    "clear_modeling_state",
    "clear_quad_draw_dots",
    "commit_or_close_caddy",
    "delete_non_deformer_history",
    "ensure_retopo_mesh",
    "extrude_quad_draw_strip",
    "fill_quad_from_dots",
    "freeze_transformations_guarded",
    "get_active_caddy_state",
    "get_live_surface_object",
    "get_live_surface_state",
    "get_mesh_texel_density",
    "get_quad_draw_dots",
    "get_quad_draw_overlay_data",
    "insert_quad_draw_loop",
    "inspect_construction_history",
    "invoke_modeling_caddy",
    "is_quad_draw_active",
    "plot_quad_draw_dot",
    "project_mesh_to_live_surface",
    "project_point_to_live_surface",
    "relax_quad_draw_verts",
    "run_scene_diagnostics",
    "scrub_caddy_parameter",
    "set_caddy_parameter",
    "set_live_surface",
    "set_mesh_texel_density",
    "set_quad_draw_active",
    "snapshot_material_assignments",
    "uv_cleanup_sets_guarded",
    "uv_unwrap_and_pack",
    "weld_vertices_target_weld",
]
