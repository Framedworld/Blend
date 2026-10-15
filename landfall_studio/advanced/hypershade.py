"""Maya Hypershade Material Browser, Shader Templates & Lookdev Bridge (`landfall_studio.advanced.hypershade`).

Bridges upstream `blendertk.MatUtils` and `pythontk.MapFactory` with Blender's native `ShaderNodeTree`
(Shader Editor):
- `list_scene_materials()`: Returns all scene materials with Principled/surface shader parameters
  (`base_color`, `metallic`, `roughness`, `ior`, `emission`), assigned object count, texture count,
  and UDIM tile status.
- `get_shader_templates()` / `create_from_template()` / `apply_template_to_material()`:
  Wraps `MatUtils.get_shader_templates()`, `MatUtils.create_shader_template()`, and
  `MatUtils.apply_shader_template()`.
- `assign_material_to_selection()` / `select_objects_with_material()`:
  Wraps `MatUtils.assign_mat()` and `MatUtils.select_by_material()`.
- `graph_material_in_shader_editor()`:
  Focuses the material on an active slot and opens/focuses Blender's native `Shader Editor` node
  graph (`MatUtils.graph_materials()`), or switches a split area to `ShaderNodeTree`.
- `auto_wire_pbr_textures()`:
  Uses `MatUtils.resolve_pbr_plan()` + `MatUtils.fix_color_spaces()` (`pythontk.MapFactory`) to
  automatically classify texture files (`BaseColor`, `Roughness`, `Metallic`, `Normal`, `Emission`,
  `ORM`) and wire a complete Principled BSDF shader graph.
- `cleanup_scene_materials()`:
  Wraps `MatUtils.find_materials_with_duplicate_textures()`, `MatUtils.reassign_duplicate_materials()`,
  and `MatUtils.delete_unused_materials()`.
- `audit_scene_textures()`:
  Wraps `MatUtils.get_image_records()` and `MatUtils.get_texture_info()`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence


def _find_principled_node(mat: Any) -> Optional[Any]:
    nt = getattr(mat, "node_tree", None) if mat is not None else None
    if nt is None:
        return None
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def _extract_shader_preview_props(mat: Any) -> Dict[str, Any]:
    """Read Principled BSDF / surface parameters for swatch rendering and quick-scrub inspector."""
    out: Dict[str, Any] = {
        "surface_type": "Principled BSDF",
        "base_color": (0.55, 0.58, 0.62, 1.0),
        "metallic": 0.0,
        "roughness": 0.45,
        "ior": 1.45,
        "coat_weight": 0.0,
        "emission_strength": 0.0,
    }
    if mat is None:
        return out
    try:
        dc = getattr(mat, "diffuse_color", None)
        if dc is not None and len(dc) >= 3:
            out["base_color"] = (float(dc[0]), float(dc[1]), float(dc[2]), float(dc[3]) if len(dc) > 3 else 1.0)
    except Exception:
        pass

    bsdf = _find_principled_node(mat)
    if bsdf is None:
        return out

    out["surface_type"] = bsdf.bl_label or bsdf.type

    def _read_float(sock_names: Sequence[str], default: float) -> float:
        for sname in sock_names:
            sock = bsdf.inputs.get(sname)
            if sock is not None and hasattr(sock, "default_value"):
                try:
                    return round(float(sock.default_value), 4)
                except Exception:
                    pass
        return default

    bc_sock = bsdf.inputs.get("Base Color")
    if bc_sock is not None and hasattr(bc_sock, "default_value"):
        try:
            v = bc_sock.default_value
            out["base_color"] = (round(float(v[0]), 4), round(float(v[1]), 4), round(float(v[2]), 4), 1.0)
        except Exception:
            pass

    out["metallic"] = _read_float(("Metallic",), 0.0)
    out["roughness"] = _read_float(("Roughness",), 0.45)
    out["ior"] = _read_float(("IOR",), 1.45)
    out["coat_weight"] = _read_float(("Coat Weight", "Clearcoat"), 0.0)
    out["emission_strength"] = _read_float(("Emission Strength",), 0.0)
    return out


def list_scene_materials() -> List[Dict[str, Any]]:
    """Return structured list of all materials in `bpy.data.materials` via `blendertk.MatUtils`."""
    import bpy
    from blendertk.mat_utils._mat_utils import MatUtils

    out: List[Dict[str, Any]] = []
    for mat in bpy.data.materials:
        if getattr(mat, "is_grease_pencil", False):
            continue
        users_objs = MatUtils.find_by_mat_id(mat)
        props = _extract_shader_preview_props(mat)
        tex_paths = MatUtils.get_texture_paths(materials=[mat], absolute=True)
        nt = getattr(mat, "node_tree", None)
        node_count = len(nt.nodes) if nt is not None else 0
        out.append(
            {
                "name": mat.name,
                "use_nodes": bool(getattr(mat, "use_nodes", False)),
                "surface_type": props["surface_type"],
                "base_color": props["base_color"],
                "metallic": props["metallic"],
                "roughness": props["roughness"],
                "ior": props["ior"],
                "coat_weight": props["coat_weight"],
                "emission_strength": props["emission_strength"],
                "assigned": len(users_objs) > 0,
                "object_count": len(users_objs),
                "objects": [o.name for o in users_objs],
                "node_count": node_count,
                "texture_count": len(tex_paths),
                "textures": [os.path.basename(p) for p in tex_paths],
            }
        )
    return out


def get_shader_templates() -> List[str]:
    """Return all Principled BSDF / `aiStandardSurface` preset template names from `blendertk.MatUtils`."""
    from blendertk.mat_utils._mat_utils import MatUtils

    base = list(MatUtils.get_shader_templates())
    if "standard" not in base:
        base.insert(0, "standard")
    return base


def create_from_template(
    template_name: str,
    *,
    name: Optional[str] = None,
    assign_to_selection: bool = True,
) -> Dict[str, Any]:
    """Create a new shader material from a `blendertk.MatUtils` template and optionally assign to active selection."""
    import bpy
    from blendertk.mat_utils._mat_utils import MatUtils

    templates = MatUtils.get_shader_templates()
    t_clean = str(template_name or "standard").strip()
    alias_map = {
        "metallic": "Metal",
        "metal": "Metal",
        "car_paint": "Clearcoat",
        "clearcoat": "Clearcoat",
        "subsurface": "Skin (SSS)",
        "skin": "Skin (SSS)",
        "glass": "Glass",
        "plastic": "Plastic",
        "rubber": "Rubber",
        "emission": "Emission",
        "emissive": "Emission",
    }
    if t_clean.lower() in alias_map:
        t_clean = alias_map[t_clean.lower()]
    is_standard = t_clean.lower() in ("standard", "aistandardsurface", "principled")
    if not is_standard and t_clean not in templates:
        # Case-insensitive fallback match
        matched = next((t for t in templates if t.lower() == t_clean.lower()), None)
        if matched is None:
            return {
                "ok": False,
                "error": f"Unknown shader template '{template_name}' (available: {['standard'] + list(templates)})",
            }
        t_clean = matched

    mat_name = name or f"aiStd_{t_clean.replace(' ', '_')}"
    if is_standard:
        mat = MatUtils.create_mat("standard", name=mat_name)
    else:
        mat = MatUtils.create_shader_template(t_clean, name=mat_name)
    props = _extract_shader_preview_props(mat)
    # Sync viewport diffuse_color so Solid (Material color) mode reflects the template immediately
    try:
        bc = props["base_color"]
        mat.diffuse_color = (bc[0], bc[1], bc[2], 1.0)
        mat.metallic = props["metallic"]
        mat.roughness = props["roughness"]
    except Exception:
        pass

    assigned_objs: List[str] = []
    if assign_to_selection:
        sel = [o for o in bpy.context.selected_objects if o.type in ("MESH", "CURVE", "SURFACE", "META", "FONT")]
        if not sel and bpy.context.view_layer.objects.active is not None:
            act = bpy.context.view_layer.objects.active
            if act.type in ("MESH", "CURVE", "SURFACE", "META", "FONT"):
                sel = [act]
        if sel:
            MatUtils.assign_mat(sel, mat)
            assigned_objs = [o.name for o in sel]

    return {
        "ok": True,
        "material": mat.name,
        "template": template_name,
        "assigned_objects": assigned_objs,
        "properties": props,
    }


def apply_template_to_material(mat_name: str, template_name: str) -> Dict[str, Any]:
    """Apply a `blendertk.MatUtils` shader preset onto an existing material."""
    import bpy
    from blendertk.mat_utils._mat_utils import MatUtils

    mat = bpy.data.materials.get(str(mat_name))
    if mat is None:
        return {"ok": False, "error": f"Material '{mat_name}' not found"}
    applied = MatUtils.apply_shader_template(mat, template_name)
    props = _extract_shader_preview_props(mat)
    try:
        bc = props["base_color"]
        mat.diffuse_color = (bc[0], bc[1], bc[2], 1.0)
        mat.metallic = props["metallic"]
        mat.roughness = props["roughness"]
    except Exception:
        pass
    return {
        "ok": bool(applied),
        "material": mat.name,
        "template": template_name,
        "applied_sockets": applied,
        "properties": props,
    }


def set_material_parameter(
    mat_name: str,
    param_name: str,
    value: Any,
) -> Dict[str, Any]:
    """Update a Principled BSDF parameter (`base_color`, `metallic`, `roughness`, `ior`, `coat_weight`, `emission_strength`)."""
    import bpy

    mat = bpy.data.materials.get(str(mat_name))
    if mat is None:
        return {"ok": False, "error": f"Material '{mat_name}' not found"}
    if not getattr(mat, "use_nodes", False):
        mat.use_nodes = True

    bsdf = _find_principled_node(mat)
    if bsdf is None:
        return {"ok": False, "error": f"Material '{mat_name}' has no Principled BSDF node"}

    key = param_name.lower().strip()
    if key == "base_color":
        col = tuple(float(c) for c in value[:3]) + (1.0,)
        sock = bsdf.inputs.get("Base Color")
        if sock is not None:
            sock.default_value = col
        mat.diffuse_color = col
    elif key == "metallic":
        fval = max(0.0, min(1.0, float(value)))
        sock = bsdf.inputs.get("Metallic")
        if sock is not None:
            sock.default_value = fval
        mat.metallic = fval
    elif key == "roughness":
        fval = max(0.0, min(1.0, float(value)))
        sock = bsdf.inputs.get("Roughness")
        if sock is not None:
            sock.default_value = fval
        mat.roughness = fval
    elif key == "ior":
        fval = max(1.0, min(3.0, float(value)))
        sock = bsdf.inputs.get("IOR")
        if sock is not None:
            sock.default_value = fval
    elif key in ("coat_weight", "clearcoat"):
        fval = max(0.0, min(1.0, float(value)))
        for sname in ("Coat Weight", "Clearcoat"):
            sock = bsdf.inputs.get(sname)
            if sock is not None:
                sock.default_value = fval
                break
    elif key == "emission_strength":
        fval = max(0.0, float(value))
        sock = bsdf.inputs.get("Emission Strength")
        if sock is not None:
            sock.default_value = fval
    else:
        return {"ok": False, "error": f"Unsupported material parameter '{param_name}'"}

    return {
        "ok": True,
        "material": mat.name,
        "param": key,
        "properties": _extract_shader_preview_props(mat),
    }


def assign_material_to_selection(mat_name: str, objects: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
    """Assign `mat_name` to the specified or currently selected objects via `MatUtils.assign_mat`."""
    import bpy
    from blendertk.mat_utils._mat_utils import MatUtils

    mat = bpy.data.materials.get(str(mat_name))
    if mat is None:
        return {"ok": False, "error": f"Material '{mat_name}' not found"}

    if objects is None:
        targets = [o for o in bpy.context.selected_objects if hasattr(o, "material_slots")]
        if not targets and bpy.context.view_layer.objects.active is not None:
            act = bpy.context.view_layer.objects.active
            if hasattr(act, "material_slots"):
                targets = [act]
    else:
        targets = [
            (bpy.data.objects.get(o) if isinstance(o, str) else o)
            for o in objects
        ]
        targets = [o for o in targets if o is not None and hasattr(o, "material_slots")]

    if not targets:
        return {"ok": False, "error": "No valid target objects selected for material assignment"}

    MatUtils.assign_mat(targets, mat)
    return {
        "ok": True,
        "material": mat.name,
        "assigned_objects": [o.name for o in targets],
    }


def select_objects_with_material(mat_name: str, add: bool = False) -> Dict[str, Any]:
    """Select all scene objects assigned `mat_name` (Maya Hypershade 'Select Objects With Material')."""
    import bpy
    from blendertk.mat_utils._mat_utils import MatUtils

    mat = bpy.data.materials.get(str(mat_name))
    if mat is None:
        return {"ok": False, "error": f"Material '{mat_name}' not found"}

    MatUtils.select_by_material(mat, add=add)
    users = MatUtils.find_by_mat_id(mat)
    return {
        "ok": True,
        "material": mat.name,
        "selected_objects": [o.name for o in users],
        "count": len(users),
    }


def graph_material_in_shader_editor(mat_name: str) -> Dict[str, Any]:
    """Focus `mat_name` on its user object and open/focus Blender's native Shader Editor node graph."""
    import bpy
    from blendertk.mat_utils._mat_utils import MatUtils

    mat = bpy.data.materials.get(str(mat_name))
    if mat is None:
        return {"ok": False, "error": f"Material '{mat_name}' not found"}

    users = MatUtils.find_by_mat_id(mat)
    active_obj_name = None
    if users:
        obj = users[0]
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        active_obj_name = obj.name
        for idx, slot in enumerate(obj.material_slots):
            if slot.material is mat:
                obj.active_material_index = idx
                break

    opened_gui = False
    if not bpy.app.background:
        try:
            MatUtils.graph_materials([mat])
            opened_gui = True
        except Exception:
            pass

    serialized = MatUtils.serialize_material(mat)
    return {
        "ok": True,
        "material": mat.name,
        "active_object": active_obj_name,
        "opened_shader_editor_gui": opened_gui,
        "node_graph": serialized,
    }


def auto_wire_pbr_textures(
    mat_name: str,
    texture_paths: Sequence[str],
    *,
    create_if_missing: bool = True,
) -> Dict[str, Any]:
    """Classify `texture_paths` via `MatUtils.resolve_pbr_plan` (`pythontk.MapFactory`), wire a Principled BSDF
    shader network (`Base Color`, `Roughness`, `Metallic`, `Normal Map`, `Emission`), and enforce color spaces.
    """
    import bpy
    from blendertk.mat_utils._mat_utils import MatUtils

    valid_paths = [os.path.abspath(str(p)) for p in texture_paths if p and os.path.isfile(str(p))]
    if not valid_paths:
        return {"ok": False, "error": "No existing texture files provided"}

    plan = MatUtils.resolve_pbr_plan(valid_paths)
    mat = bpy.data.materials.get(str(mat_name))
    if mat is None:
        if not create_if_missing:
            return {"ok": False, "error": f"Material '{mat_name}' not found"}
        mat = MatUtils.create_mat("standard", name=str(mat_name))
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = _find_principled_node(mat)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")

    wired_sockets: Dict[str, str] = {}
    y_cursor = 260.0

    # Wire classified maps into Principled BSDF
    socket_map = {
        "Base_Color": ("Base Color", "sRGB"),
        "Albedo": ("Base Color", "sRGB"),
        "Diffuse": ("Base Color", "sRGB"),
        "Roughness": ("Roughness", "Non-Color"),
        "Metallic": ("Metallic", "Non-Color"),
        "Metalness": ("Metallic", "Non-Color"),
        "Emissive": ("Emission Color", "sRGB"),
        "Emission": ("Emission Color", "sRGB"),
        "Specular": ("Specular IOR Level", "Non-Color"),
        "Normal": ("Normal", "Non-Color"),
        "Normal_OpenGL": ("Normal", "Non-Color"),
        "Normal_DirectX": ("Normal", "Non-Color"),
    }

    # Check both `plan`'s resolved dict and direct `ptk.MapFactory.resolve_map_types`
    import pythontk as ptk

    classified = ptk.MapFactory.resolve_map_types(valid_paths)
    for fpath in valid_paths:
        mtype = classified.get(fpath)
        if not mtype:
            continue
        target_info = socket_map.get(mtype)
        if target_info is None:
            # Fallback substring check
            low = mtype.lower()
            if "color" in low or "albedo" in low or "diffuse" in low:
                target_info = ("Base Color", "sRGB")
            elif "rough" in low:
                target_info = ("Roughness", "Non-Color")
            elif "metal" in low:
                target_info = ("Metallic", "Non-Color")
            elif "norm" in low:
                target_info = ("Normal", "Non-Color")
            elif "emis" in low:
                target_info = ("Emission Color", "sRGB")
        if target_info is None:
            continue

        sock_name, cspace = target_info
        tex_node = nt.nodes.new("ShaderNodeTexImage")
        tex_node.label = f"{mtype}"
        tex_node.location = (-520.0, y_cursor)
        y_cursor -= 260.0
        img = bpy.data.images.load(fpath, check_existing=True)
        try:
            img.colorspace_settings.name = cspace
        except Exception:
            pass
        tex_node.image = img

        if sock_name == "Normal":
            nrm_node = nt.nodes.new("ShaderNodeNormalMap")
            nrm_node.location = (-220.0, tex_node.location.y)
            nt.links.new(tex_node.outputs["Color"], nrm_node.inputs["Color"])
            if "Normal" in bsdf.inputs:
                nt.links.new(nrm_node.outputs["Normal"], bsdf.inputs["Normal"])
                wired_sockets["Normal"] = os.path.basename(fpath)
        else:
            in_sock = bsdf.inputs.get(sock_name)
            if in_sock is not None:
                nt.links.new(tex_node.outputs["Color"], in_sock)
                wired_sockets[sock_name] = os.path.basename(fpath)

    # Also run MatUtils.fix_color_spaces to guarantee non-color maps are marked Non-Color
    cs_fixed = MatUtils.fix_color_spaces()
    return {
        "ok": True,
        "material": mat.name,
        "wired_sockets": wired_sockets,
        "pbr_plan_keys": list(plan.keys()) if isinstance(plan, dict) else [],
        "colorspaces_checked": cs_fixed,
        "node_graph": MatUtils.serialize_material(mat),
    }


def cleanup_scene_materials(
    *,
    delete_unused: bool = True,
    merge_duplicates: bool = True,
) -> Dict[str, Any]:
    """Run Maya Hypershade scene material hygiene (`reassign_duplicate_materials` + `delete_unused_materials`)."""
    from blendertk.mat_utils._mat_utils import MatUtils

    merged_groups = 0
    if merge_duplicates:
        dup_groups = MatUtils.find_materials_with_duplicate_textures()
        if dup_groups:
            merged_groups = len(dup_groups)
            MatUtils.reassign_duplicate_materials(dup_groups, delete=True, verify=False)

    deleted_unused: List[str] = []
    if delete_unused:
        res = MatUtils.delete_unused_materials()
        if isinstance(res, (list, tuple, set)):
            deleted_unused = [str(x) for x in res]
        elif isinstance(res, int):
            deleted_unused = [f"unused_{i}" for i in range(res)]

    return {
        "ok": True,
        "merged_duplicate_groups": merged_groups,
        "deleted_unused": deleted_unused,
        "remaining_materials": [m["name"] for m in list_scene_materials()],
    }


def audit_scene_textures() -> Dict[str, Any]:
    """Return structured texture path & `<UDIM>` audit via `MatUtils.get_image_records()`."""
    from blendertk.mat_utils._mat_utils import MatUtils

    records = MatUtils.get_image_records()
    out_records = []
    missing_count = 0
    for r in records:
        exists = bool(r.get("exists"))
        if not exists:
            missing_count += 1
        out_records.append(
            {
                "name": r.get("name", ""),
                "filepath": r.get("filepath", ""),
                "abspath": r.get("abspath", ""),
                "exists": exists,
                "users": int(r.get("users", 0)),
            }
        )
    return {
        "ok": True,
        "total_images": len(out_records),
        "missing_count": missing_count,
        "images": out_records,
    }
