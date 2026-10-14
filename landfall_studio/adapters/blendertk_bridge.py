"""Bridge for invoking blendertk operations and exposing studio operators."""

from __future__ import annotations

from types import ModuleType
from typing import Any, Dict, Optional

from ..bootstrap.deps import check_dependencies


def get_btk(
    custom_upstream_root: Optional[str] = None,
    custom_deps_dir: Optional[str] = None,
) -> Optional[ModuleType]:
    """Return the `blendertk` module if all required dependencies are available."""
    status = check_dependencies(
        custom_upstream_root=custom_upstream_root,
        custom_deps_dir=custom_deps_dir,
    )
    if not status["full_stack_ready"]:
        return None
    import blendertk as btk

    return btk


def execute_sample_command(
    primitive_type: str = "CUBE",
    name: str = "Studio_Btk_Cube",
    size: float = 2.0,
) -> Dict[str, Any]:
    """Execute a verified `blendertk` scene/modeling operation on the active Blender scene.

    Creates a polygon primitive mesh and runs `blendertk.XformUtils.drop_to_grid`,
    `blendertk.XformUtils.center_pivot`, `blendertk.XformUtils.freeze_transforms`,
    and `blendertk.XformUtils.get_world_bbox`, returning structured verification metadata.
    """
    btk = get_btk()
    if btk is None:
        raise RuntimeError(
            "blendertk is not ready; install Qt/Python dependencies first."
        )

    import bpy

    kind = primitive_type.upper()
    if kind == "SPHERE":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=size * 0.5, location=(0.0, 0.0, 1.5))
    elif kind == "CYLINDER":
        bpy.ops.mesh.primitive_cylinder_add(radius=size * 0.5, depth=size, location=(0.0, 0.0, 1.5))
    elif kind == "PLANE":
        bpy.ops.mesh.primitive_plane_add(size=size, location=(0.0, 0.0, 1.5))
    else:
        bpy.ops.mesh.primitive_cube_add(size=size, location=(0.0, 0.0, 1.5))

    obj = bpy.context.active_object
    if obj is None:
        raise RuntimeError(f"Failed to create {kind} mesh")
    obj.name = name
    if obj.data is not None:
        obj.data.name = f"{name}_Mesh"

    # Exercise real blendertk XformUtils commands on the created mesh
    btk.XformUtils.drop_to_grid(obj, align="Min", center_pivot=True)
    btk.XformUtils.freeze_transforms(
        obj, location=True, rotation=True, scale=True, store=True
    )
    bbox_min, bbox_max = btk.XformUtils.get_world_bbox(obj)
    stored_xform = btk.XformUtils.has_stored_transforms(obj).get(obj, False)

    mesh = obj.data
    return {
        "ok": True,
        "object_name": obj.name,
        "vertex_count": len(mesh.vertices),
        "edge_count": len(mesh.edges),
        "polygon_count": len(mesh.polygons),
        "location": tuple(round(v, 5) for v in obj.location),
        "scale": tuple(round(v, 5) for v in obj.scale),
        "bbox_min": tuple(round(v, 5) for v in bbox_min),
        "bbox_max": tuple(round(v, 5) for v in bbox_max),
        "has_stored_transforms": bool(stored_xform),
        "btk_version": getattr(btk, "__version__", "unknown"),
    }
