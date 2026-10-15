"""Gate 08 — Maya Hypershade Material Browser, NLA Animation Layers & Non-Destructive Weight Layers (`landfall_studio.advanced`)."""

from __future__ import annotations

from .anim_layers import (
    create_anim_layer,
    ensure_base_animation_layer,
    keyframe_on_anim_layer,
    list_anim_layers,
    remove_anim_layer,
    set_anim_layer_state,
)
from .hypershade import (
    apply_template_to_material,
    assign_material_to_selection,
    audit_scene_textures,
    auto_wire_pbr_textures,
    cleanup_scene_materials,
    create_from_template,
    get_shader_templates,
    graph_material_in_shader_editor,
    list_scene_materials,
    select_objects_with_material,
    set_material_parameter,
)
from .ops import ADVANCED_CLASSES, register_advanced_operators, unregister_advanced_operators
from .weight_layers import (
    create_weight_layer,
    ensure_base_weight_layer,
    evaluate_weight_layers,
    list_weight_layers,
    set_layer_vertex_weights,
    set_weight_layer_state,
)

__all__ = [
    "ADVANCED_CLASSES",
    "apply_template_to_material",
    "assign_material_to_selection",
    "audit_scene_textures",
    "auto_wire_pbr_textures",
    "cleanup_scene_materials",
    "create_anim_layer",
    "create_from_template",
    "create_weight_layer",
    "ensure_base_animation_layer",
    "ensure_base_weight_layer",
    "evaluate_weight_layers",
    "get_shader_templates",
    "graph_material_in_shader_editor",
    "keyframe_on_anim_layer",
    "list_anim_layers",
    "list_scene_materials",
    "list_weight_layers",
    "register_advanced_operators",
    "remove_anim_layer",
    "select_objects_with_material",
    "set_anim_layer_state",
    "set_layer_vertex_weights",
    "set_material_parameter",
    "set_weight_layer_state",
    "unregister_advanced_operators",
]
