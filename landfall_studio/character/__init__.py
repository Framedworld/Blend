"""Gate 06 Character Art Production Package (`landfall_studio.character`).

Exports:
- Strict topological connectivity, UV, and material validation (`topology.py`)
- `BlendshapeAnimator` integration, multi-master driver hazard detection, and deterministic tent evaluator (`blendshape_bridge.py`)
- Maya-style Shape Editor, target extraction with held reference, and base edit propagation (`shape_editor.py`)
- Locked-weight-respecting skin inspection, Weight Hammer, Prune, Normalize, Mirror, and Controlled Transfer (`skin_weights.py`)
- Blender Operators (`ops.py`)
"""

from __future__ import annotations

from .blendshape_bridge import (
    apply_blendshape_tweens,
    compute_analytical_morphed_coords,
    compute_tent_weight,
    create_blendshape_setup,
    create_blendshape_tweens,
    detect_multi_master_driver_hazard,
    evaluate_correctives_deterministic,
    register_handlers,
    unregister_handlers,
)
from .ops import CHARACTER_CLASSES
from .shape_editor import (
    HELD_IS_TARGET_PROP,
    HELD_SOURCE_KEY_PROP,
    HELD_SOURCE_OBJ_PROP,
    HELD_TARGET_PREFIX,
    create_shape_target,
    extract_target_mesh_with_reference,
    keyframe_shape_target,
    list_shape_targets,
    mirror_shape_target,
    propagate_base_mesh_edits,
    set_shape_target_weight,
    sync_extracted_target_to_shape_key,
)
from .skin_weights import (
    controlled_weight_transfer,
    inspect_skin_weights,
    mirror_skin_weights,
    normalize_skin_weights,
    prune_small_weights,
    set_vertex_group_lock,
    set_vertex_weight_respecting_locks,
    snapshot_locked_weights,
    verify_locked_weights_preserved,
    weight_hammer_vertices,
)
from .topology import (
    copy_uvs_and_materials,
    snapshot_uvs_and_materials,
    validate_strict_topology,
    verify_uvs_and_materials_preserved,
)

__all__ = [
    "CHARACTER_CLASSES",
    "HELD_IS_TARGET_PROP",
    "HELD_SOURCE_KEY_PROP",
    "HELD_SOURCE_OBJ_PROP",
    "HELD_TARGET_PREFIX",
    "apply_blendshape_tweens",
    "compute_analytical_morphed_coords",
    "compute_tent_weight",
    "controlled_weight_transfer",
    "copy_uvs_and_materials",
    "create_blendshape_setup",
    "create_blendshape_tweens",
    "create_shape_target",
    "detect_multi_master_driver_hazard",
    "evaluate_correctives_deterministic",
    "extract_target_mesh_with_reference",
    "inspect_skin_weights",
    "keyframe_shape_target",
    "list_shape_targets",
    "mirror_shape_target",
    "mirror_skin_weights",
    "normalize_skin_weights",
    "propagate_base_mesh_edits",
    "prune_small_weights",
    "register_handlers",
    "set_shape_target_weight",
    "set_vertex_group_lock",
    "set_vertex_weight_respecting_locks",
    "snapshot_locked_weights",
    "snapshot_uvs_and_materials",
    "sync_extracted_target_to_shape_key",
    "unregister_handlers",
    "validate_strict_topology",
    "verify_locked_weights_preserved",
    "verify_uvs_and_materials_preserved",
    "weight_hammer_vertices",
]
