"""Maya Channel Box Extensions: `SHAPES`, Parametric & Modifier `INPUTS`, Display Layer Editor, and Viewport `MMB` Channel Scrubbing.

Extends the upstream `Channels` (`ChannelsSlots`) Qt panel with:
1. **3D Viewport `MMB` Virtual-Slider Channel Scrubbing & Multi-Object Channel Edits:**
   - Queries/sets selected channel rows in `tbl000` (`select_channels_in_ui`, `get_selected_channel_names`,
     `scrub_selected_channels`) so `landfall_studio.mmb_virtual_slider` in the 3D Viewport scrubs
     highlighted Channel Box attributes across all selected objects (or active `INPUTS` attributes).
2. **`SHAPES` Section:**
   - Displays the active object's `Object.data` shape datablock name (e.g. `pCubeShape1` / `<Obj>Shape`)
     and Blender datablock type (`MESH`, `CURVE`, `CAMERA`, `LIGHT`, `ARMATURE`), with inline rename
     and read-only protection when `Object.data.library` is linked.
3. **`INPUTS` Section (Parametric Creation History + Live Modifier Stack):**
   - Stores parametric creation history on primitives created via `create_maya_primitive` /
     `landfall_studio.maya_poly_primitive` (`polyCube1`, `polySphere1`, `polyCylinder1`, `polyPlane1`)
     with live non-destructive BMesh regeneration when `width`, `height`, `depth`, `radius`, or
     `subdivisions_x/y/z` are edited.
   - Exposes active Blender modifiers (`SUBSURF`, `BEVEL`, `SOLIDIFY`, `ARRAY`, `MIRROR`, `SIMPLE_DEFORM`)
     as live-editable input rows (`levels`, `width`, `segments`, `thickness`, `count`, `angle`, etc.).
   - Provides `delete_construction_history` (`landfall_studio.delete_history`, `Alt+Shift+D` in Maya)
     which applies mesh modifiers in order and strips the parametric creation node.
4. **Lower Splitter — Maya Display Layer Editor (`V`, `P`, `Normal / T / R`):**
   - Backed by native Blender collections (`_lf_display_layer = True`) so layers, memberships, and
     states (`V` visible, `P` playback visible, `N` Normal / `T` Template wireframe unselectable /
     `R` Reference shaded unselectable) survive `.blend` save/reopen and `Undo`/`Redo`.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

from . import icons, style

_INPUT_META_KEY = "_lf_poly_input"
_DISPLAY_LAYER_ROOT_NAME = "Maya_Display_Layers"
_DISPLAY_LAYER_TAG = "_lf_display_layer"

# Canonical parameters for each Maya polygon primitive history node
PRIMITIVE_SPECS: Dict[str, Dict[str, Any]] = {
    "CUBE": {
        "node_prefix": "polyCube",
        "defaults": {
            "width": 2.0,
            "height": 2.0,
            "depth": 2.0,
            "subdivisions_x": 1,
            "subdivisions_y": 1,
            "subdivisions_z": 1,
        },
        "order": (
            "width",
            "height",
            "depth",
            "subdivisions_x",
            "subdivisions_y",
            "subdivisions_z",
        ),
    },
    "SPHERE": {
        "node_prefix": "polySphere",
        "defaults": {
            "radius": 1.0,
            "subdivisions_x": 20,
            "subdivisions_y": 16,
        },
        "order": ("radius", "subdivisions_x", "subdivisions_y"),
    },
    "CYLINDER": {
        "node_prefix": "polyCylinder",
        "defaults": {
            "radius": 1.0,
            "height": 2.0,
            "subdivisions_x": 20,
            "subdivisions_y": 1,
            "subdivisions_z": 1,
        },
        "order": (
            "radius",
            "height",
            "subdivisions_x",
            "subdivisions_y",
            "subdivisions_z",
        ),
    },
    "PLANE": {
        "node_prefix": "polyPlane",
        "defaults": {
            "width": 2.0,
            "height": 2.0,
            "subdivisions_x": 1,
            "subdivisions_y": 1,
        },
        "order": ("width", "height", "subdivisions_x", "subdivisions_y"),
    },
}

# Exposed live-editable attributes for common Blender modifiers in INPUTS
MODIFIER_EXPOSED_ATTRS: Dict[str, Tuple[Tuple[str, str, str], ...]] = {
    "SUBSURF": (
        ("levels", "Subdivisions (Viewport)", "int"),
        ("render_levels", "Subdivisions (Render)", "int"),
    ),
    "BEVEL": (
        ("width", "Offset / Width", "float"),
        ("segments", "Segments", "int"),
        ("profile", "Profile", "float"),
    ),
    "SOLIDIFY": (
        ("thickness", "Thickness", "float"),
        ("offset", "Offset", "float"),
    ),
    "ARRAY": (
        ("count", "Count", "int"),
    ),
    "MIRROR": (
        ("merge_threshold", "Merge Distance", "float"),
    ),
    "SIMPLE_DEFORM": (
        ("angle", "Angle", "angle"),
        ("factor", "Factor", "float"),
    ),
    "DECIMATE": (
        ("ratio", "Ratio", "float"),
    ),
}

_prim_counter: int = 0


def is_datablock_linked(id_block: Any) -> bool:
    """Return True if `id_block` comes from an external linked `.blend` library and is not editable locally."""
    if id_block is None:
        return False
    lib = getattr(id_block, "library", None)
    if lib is None:
        return False
    # If it is a library override, check if system override
    override = getattr(id_block, "override_library", None)
    if override is not None and not getattr(override, "is_system_override", False):
        return False
    return True


# --------------------------------------------------------------------------------------
# 1. Parametric Primitive Creation & Live INPUTS History Regeneration
# --------------------------------------------------------------------------------------

def _build_primitive_bmesh(prim_type: str, params: Dict[str, Any]):
    """Construct a BMesh for `prim_type` (`CUBE`, `SPHERE`, `CYLINDER`, `PLANE`) from `params`."""
    import bmesh
    from mathutils import Matrix, Vector

    bm = bmesh.new()
    ptype = (prim_type or "CUBE").upper()

    if ptype == "CUBE":
        w = max(0.001, float(params.get("width", 2.0)))
        h = max(0.001, float(params.get("height", 2.0)))
        d = max(0.001, float(params.get("depth", 2.0)))
        sx = max(1, min(64, int(params.get("subdivisions_x", 1))))
        sy = max(1, min(64, int(params.get("subdivisions_y", 1))))
        sz = max(1, min(64, int(params.get("subdivisions_z", 1))))

        # Build subdivided 6-face box with exact (sx, sy, sz) grid topology
        verts_grid = {}

        def _get_v(ix: int, iy: int, iz: int):
            key = (ix, iy, iz)
            if key not in verts_grid:
                x = (-0.5 + (ix / float(sx))) * w
                y = (-0.5 + (iy / float(sy))) * d
                z = (-0.5 + (iz / float(sz))) * h
                verts_grid[key] = bm.verts.new((x, y, z))
            return verts_grid[key]

        # -Z and +Z faces
        for ix in range(sx):
            for iy in range(sy):
                bm.faces.new((_get_v(ix, iy, 0), _get_v(ix, iy + 1, 0), _get_v(ix + 1, iy + 1, 0), _get_v(ix + 1, iy, 0)))
                bm.faces.new((_get_v(ix, iy, sz), _get_v(ix + 1, iy, sz), _get_v(ix + 1, iy + 1, sz), _get_v(ix, iy + 1, sz)))
        # -Y and +Y faces
        for ix in range(sx):
            for iz in range(sz):
                bm.faces.new((_get_v(ix, 0, iz), _get_v(ix + 1, 0, iz), _get_v(ix + 1, 0, iz + 1), _get_v(ix, 0, iz + 1)))
                bm.faces.new((_get_v(ix, sy, iz), _get_v(ix, sy, iz + 1), _get_v(ix + 1, sy, iz + 1), _get_v(ix + 1, sy, iz)))
        # -X and +X faces
        for iy in range(sy):
            for iz in range(sz):
                bm.faces.new((_get_v(0, iy, iz), _get_v(0, iy, iz + 1), _get_v(0, iy + 1, iz + 1), _get_v(0, iy + 1, iz)))
                bm.faces.new((_get_v(sx, iy, iz), _get_v(sx, iy + 1, iz), _get_v(sx, iy + 1, iz + 1), _get_v(sx, iy, iz + 1)))

        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    elif ptype == "SPHERE":
        r = max(0.001, float(params.get("radius", 1.0)))
        sx = max(3, min(128, int(params.get("subdivisions_x", 20))))
        sy = max(3, min(128, int(params.get("subdivisions_y", 16))))
        bmesh.ops.create_uvsphere(
            bm,
            u_segments=sx,
            v_segments=sy,
            radius=r,
            calc_uvs=True,
        )

    elif ptype == "CYLINDER":
        r = max(0.001, float(params.get("radius", 1.0)))
        h = max(0.001, float(params.get("height", 2.0)))
        sx = max(3, min(128, int(params.get("subdivisions_x", 20))))
        sy = max(1, min(64, int(params.get("subdivisions_y", 1))))
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=sx,
            radius1=r,
            radius2=r,
            depth=h,
            calc_uvs=True,
        )
        if sy > 1:
            # Subdivide vertical edges to create height divisions
            vert_edges = [
                e
                for e in bm.edges
                if abs(e.verts[0].co.z - e.verts[1].co.z) > h * 0.5
            ]
            if vert_edges:
                bmesh.ops.subdivide_edges(bm, edges=vert_edges, cuts=sy - 1, use_grid_fill=True)

    elif ptype == "PLANE":
        w = max(0.001, float(params.get("width", 2.0)))
        h = max(0.001, float(params.get("height", 2.0)))
        sx = max(1, min(128, int(params.get("subdivisions_x", 1))))
        sy = max(1, min(128, int(params.get("subdivisions_y", 1))))
        bmesh.ops.create_grid(
            bm,
            x_segments=sx,
            y_segments=sy,
            size=0.5,
            matrix=Matrix.Diagonal(Vector((w, h, 1.0, 1.0))),
            calc_uvs=True,
        )

    else:
        bmesh.ops.create_cube(bm, size=2.0, calc_uvs=True)

    return bm


def attach_primitive_history(
    obj: Any,
    prim_type: str = "CUBE",
    node_name: Optional[str] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """Attach Maya-style parametric primitive creation history (`polyCube1`, etc.) to `obj`."""
    global _prim_counter
    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False}

    ptype = (prim_type or "CUBE").upper()
    spec = PRIMITIVE_SPECS.get(ptype, PRIMITIVE_SPECS["CUBE"])
    _prim_counter += 1
    nname = node_name or f"{spec['node_prefix']}{_prim_counter}"

    params = dict(spec["defaults"])
    for k, v in overrides.items():
        if k in params and v is not None:
            params[k] = type(params[k])(v)

    payload = {
        "node_name": nname,
        "prim_type": ptype,
        "params": params,
    }
    obj[_INPUT_META_KEY] = json.dumps(payload)

    # Also ensure Maya-style Shape naming (<Obj>Shape) if default
    if obj.data is not None and not is_datablock_linked(obj.data):
        if not obj.data.name.endswith("Shape"):
            try:
                obj.data.name = f"{obj.name}Shape"
            except Exception:
                pass

    return payload


def create_maya_primitive(
    primitive_type: str = "CUBE",
    name: Optional[str] = None,
    **param_overrides: Any,
) -> Dict[str, Any]:
    """Create a Maya-named polygon primitive (`pCube1` + `pCubeShape1` + `polyCube1` history node)."""
    import bpy

    ptype = (primitive_type or "CUBE").upper()
    spec = PRIMITIVE_SPECS.get(ptype, PRIMITIVE_SPECS["CUBE"])
    params = dict(spec["defaults"])
    if "size" in param_overrides and ptype in ("CUBE", "PLANE"):
        sz = float(param_overrides.pop("size"))
        params["width"] = sz
        params["height"] = sz
        if "depth" in params:
            params["depth"] = sz
    elif "size" in param_overrides and ptype in ("SPHERE", "CYLINDER"):
        sz = float(param_overrides.pop("size"))
        params["radius"] = sz * 0.5

    for k, v in param_overrides.items():
        if k in params and v is not None:
            params[k] = type(params[k])(v)

    prefix_map = {
        "CUBE": "pCube",
        "SPHERE": "pSphere",
        "CYLINDER": "pCylinder",
        "PLANE": "pPlane",
    }
    base_prefix = name or prefix_map.get(ptype, "pMesh")
    idx = 1
    while f"{base_prefix}{idx}" in bpy.data.objects:
        idx += 1
    obj_name = name if (name and name not in bpy.data.objects) else f"{base_prefix}{idx}"
    shape_name = f"{obj_name}Shape"

    mesh = bpy.data.meshes.new(shape_name)
    bm = _build_primitive_bmesh(ptype, params)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(obj_name, mesh)
    ctx = bpy.context
    col = getattr(ctx, "collection", None) or ctx.scene.collection
    col.objects.link(obj)

    for o in list(_safe_selected_objects(ctx)):
        try:
            o.select_set(False)
        except Exception:
            pass
    obj.select_set(True)
    ctx.view_layer.objects.active = obj

    hist = attach_primitive_history(
        obj,
        prim_type=ptype,
        node_name=f"{spec['node_prefix']}{idx}",
        **params,
    )
    return {
        "ok": True,
        "object": obj,
        "object_name": obj.name,
        "shape_name": obj.data.name,
        "input_node": hist["node_name"],
        "primitive_type": ptype,
        "params": dict(hist["params"]),
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
    }


def _resolve_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        import bpy

        return bpy.data.objects.get(obj)
    return obj


def get_object_shape_info(obj: Any) -> Dict[str, Any]:
    """Return Maya `SHAPES` descriptor for `obj` (`shape_name`, `shape_type`, `linked`, `editable`)."""
    obj = _resolve_obj(obj)
    if obj is None:
        return {
            "has_shape": False,
            "object_name": "",
            "shape_name": "",
            "shape_type": "EMPTY",
            "linked": False,
            "editable": False,
        }
    data = getattr(obj, "data", None)
    if data is None:
        return {
            "has_shape": False,
            "object_name": obj.name,
            "shape_name": "",
            "shape_type": obj.type,
            "linked": is_datablock_linked(obj),
            "editable": False,
        }
    linked = is_datablock_linked(obj) or is_datablock_linked(data)
    return {
        "has_shape": True,
        "object_name": obj.name,
        "shape_name": data.name,
        "shape_type": obj.type,
        "linked": linked,
        "editable": not linked,
        "vertices": len(getattr(data, "vertices", ())),
        "polygons": len(getattr(data, "polygons", ())),
    }


def rename_object_shape(obj: Any, new_shape_name: str) -> Dict[str, Any]:
    """Rename `obj.data` (the Maya Shape datablock) safely, respecting linked library locks."""
    obj = _resolve_obj(obj)
    info = get_object_shape_info(obj)
    if not info["has_shape"]:
        return {"ok": False, "error": "Object has no shape datablock"}
    if info["linked"]:
        return {"ok": False, "error": "Cannot rename linked library shape datablock", "linked": True}
    clean = (new_shape_name or "").strip()
    if not clean:
        return {"ok": False, "error": "Shape name cannot be empty"}
    obj.data.name = clean
    return get_object_shape_info(obj) | {"ok": True}


def get_object_inputs(obj: Any) -> List[Dict[str, Any]]:
    """Return ordered list of Maya `INPUTS` history nodes (parametric primitive node + active Blender modifiers)."""
    obj = _resolve_obj(obj)
    if obj is None:
        return []
    nodes: List[Dict[str, Any]] = []
    linked = is_datablock_linked(obj) or is_datablock_linked(getattr(obj, "data", None))

    # 1. Parametric creation history node (if present on mesh)
    raw = obj.get(_INPUT_META_KEY) if hasattr(obj, "get") else None
    if raw and getattr(obj, "type", "") == "MESH":
        try:
            meta = json.loads(str(raw))
            ptype = meta.get("prim_type", "CUBE")
            spec = PRIMITIVE_SPECS.get(ptype, PRIMITIVE_SPECS["CUBE"])
            params = meta.get("params", {})
            attrs = []
            for pname in spec["order"]:
                if pname in params:
                    val = params[pname]
                    atype = "int" if pname.startswith("subdivisions") else "float"
                    attrs.append(
                        {
                            "name": pname,
                            "label": pname.replace("_", " ").title(),
                            "value": val,
                            "type": atype,
                            "editable": not linked,
                        }
                    )
            nodes.append(
                {
                    "node_name": meta.get("node_name", spec["node_prefix"] + "1"),
                    "node_type": f"POLY_{ptype}",
                    "kind": "primitive",
                    "linked": linked,
                    "editable": not linked,
                    "attributes": attrs,
                }
            )
        except Exception:
            pass

    # 2. Active Blender modifiers (including Geometry Nodes socket inputs!) mapped as construction inputs
    for mod in getattr(obj, "modifiers", ()):
        mtype = getattr(mod, "type", "")
        attrs = []
        if mtype == "NODES" and getattr(mod, "node_group", None) is not None:
            ng = mod.node_group
            iface = getattr(ng, "interface", None)
            for item in getattr(iface, "items_tree", ()):
                if getattr(item, "item_type", "") != "SOCKET" or getattr(item, "in_out", "") != "INPUT":
                    continue
                stype = str(getattr(item, "socket_type", ""))
                if stype == "NodeSocketGeometry":
                    continue
                ident = str(getattr(item, "identifier", ""))
                label = str(getattr(item, "name", ident))
                if not ident:
                    continue
                raw_val = _get_gn_socket_value(mod, ident, getattr(item, "default_value", 0.0))
                if "Int" in stype or isinstance(raw_val, int) and not isinstance(raw_val, bool):
                    atype = "int"
                    val = int(raw_val)
                elif "Bool" in stype or isinstance(raw_val, bool):
                    atype = "int"
                    val = 1 if bool(raw_val) else 0
                elif hasattr(raw_val, "__len__") and not isinstance(raw_val, (str, bytes)):
                    continue
                else:
                    atype = "float"
                    try:
                        val = round(float(raw_val), 4)
                    except Exception:
                        val = 0.0
                attrs.append(
                    {
                        "name": ident,
                        "label": label,
                        "value": val,
                        "type": atype,
                        "editable": not is_datablock_linked(obj),
                    }
                )
        else:
            attr_specs = MODIFIER_EXPOSED_ATTRS.get(mtype, ())
            for prop_name, label, atype in attr_specs:
                if hasattr(mod, prop_name):
                    raw_val = getattr(mod, prop_name)
                    if atype == "angle":
                        val = round(math.degrees(float(raw_val)), 4)
                    elif atype == "float":
                        val = round(float(raw_val), 4)
                    else:
                        val = int(raw_val)
                    attrs.append(
                        {
                            "name": prop_name,
                            "label": label,
                            "value": val,
                            "type": atype,
                            "editable": not is_datablock_linked(obj),
                        }
                    )
        nodes.append(
            {
                "node_name": mod.name,
                "node_type": "GEOMETRY_NODES" if mtype == "NODES" else mtype,
                "kind": "geometry_nodes" if mtype == "NODES" else "modifier",
                "show_viewport": bool(getattr(mod, "show_viewport", True)),
                "linked": is_datablock_linked(obj),
                "editable": not is_datablock_linked(obj),
                "attributes": attrs,
            }
        )

    return nodes


def _get_gn_socket_value(mod: Any, ident: str, default: Any = 0.0) -> Any:
    """Read a Geometry Nodes socket value on Blender 5.2 (`mod.properties.inputs.<ident>.value`) or Blender 4.x (`mod[ident]`)."""
    try:
        props = getattr(mod, "properties", None)
        inps = getattr(props, "inputs", None) if props is not None else None
        if inps is not None and hasattr(inps, ident):
            slot = getattr(inps, ident)
            if hasattr(slot, "value"):
                return slot.value
    except Exception:
        pass
    try:
        return mod[ident]
    except Exception:
        return default


def _set_gn_socket_value(mod: Any, ident: str, value: Any) -> bool:
    """Write a Geometry Nodes socket value on Blender 5.2 (`mod.properties.inputs.<ident>.value`) or Blender 4.x (`mod[ident]`)."""
    try:
        props = getattr(mod, "properties", None)
        inps = getattr(props, "inputs", None) if props is not None else None
        if inps is not None and hasattr(inps, ident):
            slot = getattr(inps, ident)
            if hasattr(slot, "value"):
                slot.value = value
                return True
    except Exception:
        pass
    try:
        mod[ident] = value
        return True
    except Exception:
        return False


def ensure_procedural_geonodes_modifier(
    obj: Any = None,
    name: str = "geoNodes_Procedural1",
) -> Dict[str, Any]:
    """Create or update a Blender 5.2 Geometry Nodes modifier with exposed procedural sockets (`Subdivide_Level`, `Inflate_Offset`, `Crease_Sharpness`) for Maya `Channel Box -> INPUTS`."""
    import bpy

    target = _resolve_obj(obj) or getattr(bpy.context.view_layer.objects, "active", None)
    if target is None or getattr(target, "type", "") != "MESH":
        return {"ok": False, "error": "Active mesh object required for Geometry Nodes"}

    mod = target.modifiers.get(name)
    if mod is None or mod.type != "NODES":
        mod = target.modifiers.new(name=name, type="NODES")

    ng_name = f"{name}_Group"
    ng = bpy.data.node_groups.get(ng_name)
    if ng is None:
        ng = bpy.data.node_groups.new(name=ng_name, type="GeometryNodeTree")
        iface = ng.interface
        iface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        iface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

        s_sub = iface.new_socket(name="Subdivide Level", in_out="INPUT", socket_type="NodeSocketInt")
        s_sub.default_value = 1
        s_sub.min_value = 0
        s_sub.max_value = 4

        s_inf = iface.new_socket(name="Surface Offset", in_out="INPUT", socket_type="NodeSocketFloat")
        s_inf.default_value = 0.04
        s_inf.min_value = -1.0
        s_inf.max_value = 1.0

        s_crs = iface.new_socket(name="Edge Crease", in_out="INPUT", socket_type="NodeSocketFloat")
        s_crs.default_value = 0.25
        s_crs.min_value = 0.0
        s_crs.max_value = 1.0

        n_in = ng.nodes.new("NodeGroupInput")
        n_in.location = (-360, 0)
        n_sub = ng.nodes.new("GeometryNodeSubdivisionSurface")
        n_sub.location = (-120, 40)
        n_out = ng.nodes.new("NodeGroupOutput")
        n_out.location = (160, 0)

        ng.links.new(n_in.outputs[0], n_sub.inputs["Mesh"])
        if len(n_in.outputs) > 1 and "Level" in n_sub.inputs:
            ng.links.new(n_in.outputs[1], n_sub.inputs["Level"])
        if len(n_in.outputs) > 3 and "Edge Crease" in n_sub.inputs:
            ng.links.new(n_in.outputs[3], n_sub.inputs["Edge Crease"])
        ng.links.new(n_sub.outputs["Mesh"], n_out.inputs[0])

    mod.node_group = ng
    # Initialize socket defaults on modifier instance
    for item in getattr(ng.interface, "items_tree", ()):
        if getattr(item, "item_type", "") == "SOCKET" and getattr(item, "in_out", "") == "INPUT":
            ident = getattr(item, "identifier", "")
            if ident and getattr(item, "socket_type", "") != "NodeSocketGeometry":
                _set_gn_socket_value(mod, ident, getattr(item, "default_value", 0))
    target.update_tag()
    return {
        "ok": True,
        "object": target.name,
        "modifier": mod.name,
        "node_group": ng.name,
        "inputs": get_object_inputs(target),
    }


def set_object_input_attribute(
    obj: Any,
    node_name: str,
    attr_name: str,
    value: Any,
) -> Dict[str, Any]:
    """Mutate an `INPUTS` attribute (`polyCube1.width`, `polySphere1.subdivisions_x`, `Bevel.segments`, or `Geometry Nodes` socket) and update live geometry."""
    obj = _resolve_obj(obj)
    if obj is None:
        return {"ok": False, "error": "No object specified"}
    if is_datablock_linked(obj) or is_datablock_linked(getattr(obj, "data", None)):
        return {
            "ok": False,
            "linked": True,
            "error": f"Object '{obj.name}' is linked from an external library and cannot be edited.",
        }

    clean_node = node_name[4:] if isinstance(node_name, str) and node_name.startswith("MOD:") else node_name

    # Check parametric creation node first
    raw = obj.get(_INPUT_META_KEY) if hasattr(obj, "get") else None
    if raw and getattr(obj, "type", "") == "MESH":
        try:
            meta = json.loads(str(raw))
        except Exception:
            meta = None
        if meta and (
            meta.get("node_name") == clean_node
            or str(clean_node).lower() in ("primitive", "prim_history", meta.get("prim_type", "").lower())
        ):
            params = dict(meta.get("params", {}))
            if attr_name not in params:
                return {"ok": False, "error": f"Unknown input attribute '{attr_name}' on {node_name}"}
            if attr_name.startswith("subdivisions"):
                params[attr_name] = max(1, min(128, int(round(float(value)))))
            else:
                params[attr_name] = max(0.001, float(value))
            meta["params"] = params
            obj[_INPUT_META_KEY] = json.dumps(meta)

            # Regenerate base mesh non-destructively while preserving material slots
            me = obj.data
            saved_mats = [m for m in me.materials]
            if getattr(me, "is_editmode", False):
                import bmesh

                bm_edit = bmesh.from_edit_mesh(me)
                bm_edit.clear()
                bm_new = _build_primitive_bmesh(meta.get("prim_type", "CUBE"), params)
                for v in bm_new.verts:
                    bm_edit.verts.new(v.co)
                bm_edit.verts.ensure_lookup_table()
                for f in bm_new.faces:
                    bm_edit.faces.new([bm_edit.verts[v.index] for v in f.verts])
                bm_new.free()
                bmesh.update_edit_mesh(me)
            else:
                bm = _build_primitive_bmesh(meta.get("prim_type", "CUBE"), params)
                bm.to_mesh(me)
                bm.free()
                me.update()
            if not me.materials and saved_mats:
                for m in saved_mats:
                    me.materials.append(m)
            obj.update_tag()
            return {
                "ok": True,
                "kind": "primitive",
                "node_name": meta.get("node_name"),
                "attr_name": attr_name,
                "value": params[attr_name],
                "vertex_count": len(me.vertices),
                "face_count": len(me.polygons),
            }

    # Check Blender modifiers (including Geometry Nodes socket inputs)
    mod = getattr(obj, "modifiers", {}).get(clean_node)
    if mod is not None and getattr(mod, "type", "") == "NODES" and getattr(mod, "node_group", None) is not None:
        iface = getattr(mod.node_group, "interface", None)
        for item in getattr(iface, "items_tree", ()):
            if getattr(item, "item_type", "") == "SOCKET" and getattr(item, "in_out", "") == "INPUT":
                ident = str(getattr(item, "identifier", ""))
                sname = str(getattr(item, "name", ""))
                if attr_name in (ident, sname):
                    stype = str(getattr(item, "socket_type", ""))
                    if "Int" in stype:
                        new_val = int(round(float(value)))
                    elif "Bool" in stype:
                        new_val = bool(int(round(float(value))))
                    else:
                        new_val = float(value)
                    _set_gn_socket_value(mod, ident, new_val)
                    obj.update_tag()
                    return {
                        "ok": True,
                        "kind": "geometry_nodes",
                        "node_name": mod.name,
                        "attr_name": ident,
                        "label": sname,
                        "value": _get_gn_socket_value(mod, ident, new_val),
                    }

    if mod is not None and hasattr(mod, attr_name):
        mtype = getattr(mod, "type", "")
        attr_specs = dict((a, t) for a, _, t in MODIFIER_EXPOSED_ATTRS.get(mtype, ()))
        atype = attr_specs.get(attr_name, "float")
        try:
            if atype == "int" or isinstance(getattr(mod, attr_name), int):
                new_val = max(0, int(round(float(value))))
                setattr(mod, attr_name, new_val)
            elif atype == "angle":
                deg_val = float(value)
                setattr(mod, attr_name, math.radians(deg_val))
                new_val = deg_val
            else:
                new_val = float(value)
                setattr(mod, attr_name, new_val)
            obj.update_tag()
            return {
                "ok": True,
                "kind": "modifier",
                "node_name": mod.name,
                "attr_name": attr_name,
                "value": new_val,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    return {"ok": False, "error": f"Input node '{node_name}' or attribute '{attr_name}' not found"}


def delete_construction_history(
    obj: Any = None,
    apply_modifiers: bool = True,
    force_remove_shape_keys: bool = False,
) -> Dict[str, Any]:
    """Maya `Edit > Delete by Type > History` (`Alt+Shift+D`): apply modifiers and clear parametric creation history while guarding Shape Keys."""
    import bpy

    target = _resolve_obj(obj) or getattr(bpy.context.view_layer.objects, "active", None)
    if target is None:
        return {"ok": False, "error": "No active object"}
    if is_datablock_linked(target) or is_datablock_linked(getattr(target, "data", None)):
        return {"ok": False, "linked": True, "error": "Cannot delete history on linked library data"}

    applied_mods: List[str] = []
    skipped_mods: List[str] = []
    cleared_prim: Optional[str] = None

    if _INPUT_META_KEY in target:
        try:
            meta = json.loads(str(target[_INPUT_META_KEY]))
            cleared_prim = meta.get("node_name")
        except Exception:
            cleared_prim = _INPUT_META_KEY
        del target[_INPUT_META_KEY]

    if apply_modifiers and getattr(target, "type", "") == "MESH" and len(target.modifiers) > 0:
        sk = getattr(target.data, "shape_keys", None)
        has_shape_keys = sk is not None and len(getattr(sk, "key_blocks", ())) > 0

        if has_shape_keys and not force_remove_shape_keys:
            # Guard shape keys: never run destructive evaluated-mesh replacement when shape keys exist!
            # Instead, apply non-topology-changing deform modifiers per shape key or skip topology modifiers with a warning.
            return {
                "ok": False,
                "blocked": True,
                "shape_keys_preserved": True,
                "object_name": target.name,
                "cleared_primitive_node": cleared_prim,
                "applied_modifiers": applied_mods,
                "skipped_modifiers": [m.name for m in target.modifiers],
                "reason": (
                    f"Guarded Delete History on '{target.name}': mesh has {len(sk.key_blocks)} Shape Keys. "
                    "Applying modifiers would destroy Shape Keys unless force_remove_shape_keys=True."
                ),
            }

        prev_active = bpy.context.view_layer.objects.active
        prev_mode = getattr(target, "mode", "OBJECT")
        try:
            bpy.context.view_layer.objects.active = target
            if prev_mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            for mod in list(target.modifiers):
                mname = mod.name
                try:
                    bpy.ops.object.modifier_apply(modifier=mname)
                    applied_mods.append(mname)
                except Exception:
                    # Fallback evaluated mesh bake ONLY when no shape keys exist (or force_remove_shape_keys=True)
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                    eval_obj = target.evaluated_get(depsgraph)
                    new_me = bpy.data.meshes.new_from_object(eval_obj)
                    old_name = target.data.name
                    old_me = target.data
                    target.modifiers.clear()
                    target.data = new_me
                    target.data.name = old_name
                    if old_me.users == 0:
                        bpy.data.meshes.remove(old_me)
                    applied_mods.append(mname)
                    break
            if prev_mode != "OBJECT":
                bpy.ops.object.mode_set(mode=prev_mode)
        finally:
            if prev_active is not None and prev_active.name in bpy.data.objects:
                bpy.context.view_layer.objects.active = prev_active

    return {
        "ok": True,
        "object_name": target.name,
        "cleared_primitive_node": cleared_prim,
        "applied_modifiers": applied_mods,
        "skipped_modifiers": skipped_mods,
        "remaining_inputs": len(get_object_inputs(target)),
    }


# --------------------------------------------------------------------------------------
# 2. Maya Display Layer Editor (`V`, `P`, `Normal / T / R`)
# --------------------------------------------------------------------------------------

def _ensure_display_layer_root():
    import bpy

    scene = bpy.context.scene
    root = bpy.data.collections.get(_DISPLAY_LAYER_ROOT_NAME)
    if root is None:
        root = bpy.data.collections.new(_DISPLAY_LAYER_ROOT_NAME)
    if root.name not in scene.collection.children:
        try:
            scene.collection.children.link(root)
        except Exception:
            pass
    return root


def _apply_layer_state_to_members(col: Any) -> None:
    """Synchronize `V` (visibility) and `N/T/R` (Normal / Template / Reference) onto all member objects of `col`."""
    vis = bool(col.get("_lf_layer_visible", True))
    mode = str(col.get("_lf_layer_mode", "N") or "N").upper()

    col.hide_viewport = not vis
    for obj in list(col.objects):
        if is_datablock_linked(obj):
            continue
        try:
            obj.hide_set(not vis)
        except Exception:
            pass
        try:
            obj.hide_viewport = not vis
        except Exception:
            pass

        if mode == "T":
            # Template: Wireframe + Unselectable
            if "_lf_orig_display_type" not in obj:
                obj["_lf_orig_display_type"] = str(getattr(obj, "display_type", "TEXTURED"))
            obj.display_type = "WIRE"
            obj.hide_select = True
        elif mode == "R":
            # Reference: Shaded/Textured + Unselectable
            orig_dt = str(obj.get("_lf_orig_display_type", "TEXTURED") or "TEXTURED")
            obj.display_type = orig_dt
            obj.hide_select = True
        else:
            # Normal: Shaded/Textured + Selectable
            orig_dt = str(obj.get("_lf_orig_display_type", "TEXTURED") or "TEXTURED")
            obj.display_type = orig_dt
            obj.hide_select = False


def list_display_layers() -> List[Dict[str, Any]]:
    """Return all Maya Display Layers in the current scene."""
    import bpy

    layers: List[Dict[str, Any]] = []
    for col in bpy.data.collections:
        if not col.get(_DISPLAY_LAYER_TAG, False):
            continue
        vis = bool(col.get("_lf_layer_visible", True))
        pb = bool(col.get("_lf_layer_playback", True))
        mode = str(col.get("_lf_layer_mode", "N") or "N").upper()
        members = [o.name for o in col.objects]
        layers.append(
            {
                "name": col.name,
                "visible": vis,
                "playback": pb,
                "mode": mode,  # "N" (Normal), "T" (Template), "R" (Reference)
                "members": members,
                "member_count": len(members),
            }
        )
    return layers


def _safe_selected_objects(ctx: Any = None) -> List[Any]:
    import bpy

    c = ctx or bpy.context
    sel = getattr(c, "selected_objects", None)
    if sel is not None:
        return list(sel)
    vl = getattr(c, "view_layer", None)
    if vl is not None:
        return [o for o in vl.objects if o.select_get()]
    return []


def create_display_layer(
    name: Optional[str] = None,
    assign_selected: bool = True,
) -> Dict[str, Any]:
    """Create a Maya Display Layer (`layer1`, `layer2`, ...) and optionally assign selected objects."""
    import bpy

    root = _ensure_display_layer_root()
    idx = 1
    while f"layer{idx}" in bpy.data.collections:
        idx += 1
    lname = (name or "").strip() or f"layer{idx}"

    col = bpy.data.collections.get(lname)
    if col is None:
        col = bpy.data.collections.new(lname)
    if col.name not in root.children:
        try:
            root.children.link(col)
        except Exception:
            pass

    col[_DISPLAY_LAYER_TAG] = True
    col["_lf_layer_visible"] = True
    col["_lf_layer_playback"] = True
    col["_lf_layer_mode"] = "N"

    if assign_selected:
        assign_objects_to_display_layer(col.name, _safe_selected_objects())
    else:
        _apply_layer_state_to_members(col)

    return next((l for l in list_display_layers() if l["name"] == col.name), {"name": col.name}) | {"ok": True}


def delete_display_layer(layer_name: str) -> Dict[str, Any]:
    """Delete a Maya Display Layer and restore its member objects to `Normal` selectable state."""
    import bpy

    col = bpy.data.collections.get(layer_name)
    if col is None or not col.get(_DISPLAY_LAYER_TAG, False):
        return {"ok": False, "error": f"Display layer '{layer_name}' not found"}

    col["_lf_layer_visible"] = True
    col["_lf_layer_mode"] = "N"
    _apply_layer_state_to_members(col)
    bpy.data.collections.remove(col)
    return {"ok": True, "deleted": layer_name, "layers": list_display_layers()}


def assign_objects_to_display_layer(
    layer_name: str,
    objects: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Assign `objects` (or current selection) exclusively to Display Layer `layer_name`."""
    import bpy

    col = bpy.data.collections.get(layer_name)
    if col is None or not col.get(_DISPLAY_LAYER_TAG, False):
        return {"ok": False, "error": f"Display layer '{layer_name}' not found"}

    raw_targets = objects if objects is not None else _safe_selected_objects()
    targets = [o for o in (_resolve_obj(x) for x in raw_targets) if o is not None]
    # Remove from any other Display Layer first (Maya objects belong to one Display Layer at a time)
    for other in bpy.data.collections:
        if other is not col and other.get(_DISPLAY_LAYER_TAG, False):
            for o in targets:
                if o.name in other.objects:
                    other.objects.unlink(o)

    for o in targets:
        if o.name not in col.objects:
            col.objects.link(o)

    _apply_layer_state_to_members(col)
    return next((l for l in list_display_layers() if l["name"] == col.name), {"name": col.name}) | {"ok": True}


def set_display_layer_state(
    layer_name: str,
    visible: Optional[bool] = None,
    playback: Optional[bool] = None,
    mode: Optional[str] = None,
    cycle_mode: bool = False,
    display_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Update `V` (`visible`), `P` (`playback`), or `mode` (`N` / `T` / `R`) on Display Layer `layer_name`."""
    import bpy

    col = bpy.data.collections.get(layer_name)
    if col is None or not col.get(_DISPLAY_LAYER_TAG, False):
        return {"ok": False, "error": f"Display layer '{layer_name}' not found"}

    if visible is not None:
        col["_lf_layer_visible"] = bool(visible)
    if playback is not None:
        col["_lf_layer_playback"] = bool(playback)

    eff_mode = mode if mode is not None else display_type
    if cycle_mode:
        cur = str(col.get("_lf_layer_mode", "N") or "N").upper()
        order = ("N", "T", "R")
        col["_lf_layer_mode"] = order[(order.index(cur) + 1) % len(order)] if cur in order else "T"
    elif eff_mode is not None:
        m = str(eff_mode).upper()
        if m in ("N", "NORMAL", ""):
            col["_lf_layer_mode"] = "N"
        elif m in ("T", "TEMPLATE"):
            col["_lf_layer_mode"] = "T"
        elif m in ("R", "REFERENCE"):
            col["_lf_layer_mode"] = "R"

    _apply_layer_state_to_members(col)
    return next((l for l in list_display_layers() if l["name"] == col.name), {"name": col.name}) | {"ok": True}


def sync_all_display_layers_from_scene() -> List[Dict[str, Any]]:
    """Re-apply Display Layer `V / P / T / R` states after file load or Undo/Redo."""
    import bpy

    for col in bpy.data.collections:
        if col.get(_DISPLAY_LAYER_TAG, False):
            _apply_layer_state_to_members(col)
    return list_display_layers()


# --------------------------------------------------------------------------------------
# 3. Channel Selection & 3D Viewport MMB Virtual-Slider Channel Scrubbing
# --------------------------------------------------------------------------------------

_selected_input_target: Optional[Tuple[str, str]] = None  # (node_name, attr_name)
_explicit_selected_channels: List[str] = []


def _get_table_selected_descriptors(tbl: Any, slots: Any) -> List[Dict[str, Any]]:
    """Resolve currently selected row descriptors from `tbl000` or explicit selection."""
    row_descs = getattr(slots, "_row_descriptors", None) or []
    by_name = {d["name"]: d for d in row_descs if isinstance(d, dict) and "name" in d}

    selected_rows = sorted({idx.row() for idx in tbl.selectedIndexes()})
    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for r in selected_rows:
        if 0 <= r < len(row_descs):
            d = row_descs[r]
            if isinstance(d, dict) and d.get("name") and d["name"] not in seen:
                seen.add(d["name"])
                result.append(d)
        else:
            item = tbl.item(r, getattr(slots, "COL_NAME", 1))
            if item is not None:
                cname = item.text().strip()
                if cname in by_name and cname not in seen:
                    seen.add(cname)
                    result.append(by_name[cname])

    if not result and _explicit_selected_channels:
        for cname in _explicit_selected_channels:
            if cname in by_name and cname not in seen:
                seen.add(cname)
                result.append(by_name[cname])
    return result


def select_channels_in_ui(channel_names: List[str]) -> List[str]:
    """Programmatically select rows in the `Channels` table (`tbl000`) by channel name."""
    global _explicit_selected_channels
    from . import desktop
    from qtpy import QtCore

    _explicit_selected_channels = [str(n).strip() for n in channel_names if str(n).strip()]
    widget, slots = desktop.get_panel_widget_and_slots("channels")
    if widget is None or slots is None:
        return list(_explicit_selected_channels)
    desktop.sync_channels_now()
    tbl = getattr(widget, "tbl000", None)
    if tbl is None:
        return list(_explicit_selected_channels)

    wanted = set(_explicit_selected_channels)
    tbl.clearSelection()
    sel_model = tbl.selectionModel()
    matched: List[str] = []
    row_descs = getattr(slots, "_row_descriptors", None) or []
    for r in range(tbl.rowCount()):
        cname = ""
        if 0 <= r < len(row_descs) and isinstance(row_descs[r], dict):
            cname = str(row_descs[r].get("name", "")).strip()
        if not cname:
            item = tbl.item(r, slots.COL_NAME)
            if item is not None:
                cname = item.text().strip()
        if cname and cname in wanted:
            idx = tbl.model().index(r, slots.COL_VALUE)
            if sel_model is not None:
                sel_model.select(
                    idx,
                    QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows,
                )
            matched.append(cname)
    _explicit_selected_channels = list(matched)
    return matched


def get_selected_channel_names() -> List[str]:
    """Return the list of currently selected channel names in `Channels` (`tbl000`)."""
    from . import desktop

    widget, slots = desktop.get_panel_widget_and_slots("channels")
    if widget is None or slots is None:
        return list(_explicit_selected_channels)
    tbl = getattr(widget, "tbl000", None)
    if tbl is None:
        return list(_explicit_selected_channels)
    descriptors = _get_table_selected_descriptors(tbl, slots)
    return [d["name"] for d in descriptors]


def scrub_selected_channels(delta: float, objects: Optional[List[Any]] = None) -> Dict[str, Any]:
    """Scrub highlighted Channel Box channels (or selected `INPUTS` attribute) across all selected objects."""
    import bpy
    from . import desktop

    # 1. If an INPUTS row is actively selected for scrubbing, scrub it first
    if _selected_input_target is not None:
        node_name, attr_name = _selected_input_target
        active = getattr(bpy.context.view_layer.objects, "active", None)
        if active is not None:
            for node in get_object_inputs(active):
                if node["node_name"] == node_name:
                    for attr in node["attributes"]:
                        if attr["name"] == attr_name:
                            cur_val = float(attr["value"])
                            step = round(delta) if attr["type"] == "int" else delta
                            res = set_object_input_attribute(active, node_name, attr_name, cur_val + step)
                            refresh_channel_box_extensions()
                            return {"ok": res.get("ok", False), "mode": "INPUTS", "result": res}

    # 2. Check selected transform/custom channels in the Channel Box
    widget, slots = desktop.get_panel_widget_and_slots("channels")
    if widget is None or slots is None:
        return {"ok": False, "scrubbed_channels": [], "object_count": 0}

    tbl = getattr(widget, "tbl000", None)
    if tbl is None:
        return {"ok": False, "scrubbed_channels": [], "object_count": 0}

    descriptors = _get_table_selected_descriptors(tbl, slots)
    if not descriptors:
        return {"ok": False, "scrubbed_channels": [], "object_count": 0}

    targets = objects if objects is not None else slots.controller.get_selected_nodes()
    targets = [o for o in targets if not is_datablock_linked(o)]
    if not targets:
        return {"ok": False, "scrubbed_channels": [], "object_count": 0}

    scrubbed_names: List[str] = []
    for d in descriptors:
        cname = d["name"]
        scrubbed_names.append(cname)
        for obj in targets:
            if slots.controller.is_locked(obj, d):
                continue
            cur = slots._scrub_value(obj, d)
            if cur is None:
                continue
            if d.get("type") == "int":
                new_val = int(round(cur + delta))
            else:
                new_val = float(cur + delta)
            slots.controller.set_channel_value([obj], d, str(new_val))

    desktop.sync_channels_now()
    refresh_channel_box_extensions()
    return {
        "ok": True,
        "mode": "CHANNELS",
        "scrubbed_channels": scrubbed_names,
        "object_count": len(targets),
    }


# --------------------------------------------------------------------------------------
# 4. Embedded Channel Box Extension Widget (`SHAPES` + `INPUTS` + `Display Layer Editor`)
# --------------------------------------------------------------------------------------

class MayaChannelBoxExtensionWidget:
    """Controller & Qt sub-panel embedded inside `Channels` providing Figma Make Object Header, `SHAPES`, `INPUTS`, and `Display Layers`."""

    def __init__(self, host_channels_widget: Any):
        from qtpy import QtCore, QtGui, QtWidgets

        self.host = host_channels_widget
        self._updating = False

        # Figma Make Channel Box Object Header Bar ("body_main_GEO" + "mesh transform")
        self.obj_header_bar = QtWidgets.QFrame()
        self.obj_header_bar.setObjectName("MayaSectionHeader")
        self.obj_header_bar.setFixedHeight(28)
        oh_lay = QtWidgets.QHBoxLayout(self.obj_header_bar)
        oh_lay.setContentsMargins(8, 3, 8, 3)
        oh_lay.setSpacing(6)

        self.lbl_obj_icon = QtWidgets.QLabel()
        self.lbl_obj_icon.setPixmap(icons.get_icon("dag_mesh", 14).pixmap(14, 14))
        oh_lay.addWidget(self.lbl_obj_icon)

        self.lbl_obj_name = QtWidgets.QLabel("pCube1")
        self.lbl_obj_name.setStyleSheet(
            "color: #FFFFFF; font-size: 11px; font-weight: 700; background: transparent; border: none;"
        )
        oh_lay.addWidget(self.lbl_obj_name)
        oh_lay.addStretch(1)

        self.lbl_obj_subtitle = QtWidgets.QLabel("mesh transform")
        self.lbl_obj_subtitle.setStyleSheet(
            "color: #7D8590; font-size: 9px; font-family: 'Cascadia Mono', 'Consolas', monospace; background: transparent; border: none;"
        )
        oh_lay.addWidget(self.lbl_obj_subtitle)

        # Install Figma Make X/Y/Z Axis Badge Delegate on tbl000 column 1 (Channel Name)
        self._install_axis_badge_delegate(host_channels_widget)

        self.root = QtWidgets.QFrame(host_channels_widget)
        self.root.setObjectName("MayaChannelBoxExt")
        vlay = QtWidgets.QVBoxLayout(self.root)
        vlay.setContentsMargins(0, 2, 0, 0)
        vlay.setSpacing(2)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self.root)
        vlay.addWidget(self.splitter, 1)

        # --- Top half of extension: SHAPES + INPUTS ---
        hist_pane = QtWidgets.QFrame()
        hlay = QtWidgets.QVBoxLayout(hist_pane)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(2)

        # SHAPES Header + Row
        shapes_hdr = QtWidgets.QFrame()
        shapes_hdr.setObjectName("MayaSectionHeader")
        sh_row = QtWidgets.QHBoxLayout(shapes_hdr)
        sh_row.setContentsMargins(6, 2, 6, 2)
        lbl_sh = QtWidgets.QLabel("SHAPES")
        lbl_sh.setObjectName("MayaSectionTitle")
        self.lbl_shape_type = QtWidgets.QLabel("MESH")
        self.lbl_shape_type.setObjectName("MayaBadgeTeal")
        sh_row.addWidget(lbl_sh)
        sh_row.addStretch(1)
        sh_row.addWidget(self.lbl_shape_type)
        hlay.addWidget(shapes_hdr)

        shape_edit_row = QtWidgets.QHBoxLayout()
        shape_edit_row.setContentsMargins(4, 1, 4, 1)
        self.txt_shape_name = QtWidgets.QLineEdit()
        self.txt_shape_name.setPlaceholderText("No Shape Node")
        self.txt_shape_name.setStyleSheet(
            "color: #69B8DC; font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 11px;"
        )
        self.txt_shape_name.editingFinished.connect(self._on_shape_renamed)
        shape_edit_row.addWidget(self.txt_shape_name)
        hlay.addLayout(shape_edit_row)

        # INPUTS Header + Action Buttons (+ GeoNodes & Delete History)
        inputs_hdr = QtWidgets.QFrame()
        inputs_hdr.setObjectName("MayaSectionHeader")
        in_row = QtWidgets.QHBoxLayout(inputs_hdr)
        in_row.setContentsMargins(6, 2, 4, 2)
        in_row.setSpacing(4)
        lbl_in = QtWidgets.QLabel("INPUTS")
        lbl_in.setObjectName("MayaSectionTitle")
        self.btn_add_geonodes = QtWidgets.QPushButton("+ GeoNodes")
        self.btn_add_geonodes.setToolTip("Add procedural Blender Geometry Nodes network with exposed sockets in INPUTS")
        self.btn_add_geonodes.setFixedHeight(18)
        self.btn_add_geonodes.clicked.connect(self._on_add_geonodes_clicked)
        self.btn_del_history = QtWidgets.QPushButton("Delete History")
        self.btn_del_history.setToolTip("Apply modifiers and clear parametric creation history (Alt+Shift+D)")
        self.btn_del_history.setFixedHeight(18)
        self.btn_del_history.clicked.connect(self._on_delete_history_clicked)
        in_row.addWidget(lbl_in)
        in_row.addStretch(1)
        in_row.addWidget(self.btn_add_geonodes)
        in_row.addWidget(self.btn_del_history)
        hlay.addWidget(inputs_hdr)

        # INPUTS Tree/Table (Node -> Attributes)
        self.tree_inputs = QtWidgets.QTreeWidget()
        self.tree_inputs.setHeaderLabels(["History / Attribute", "Value"])
        self.tree_inputs.setAlternatingRowColors(True)
        self.tree_inputs.setRootIsDecorated(True)
        self.tree_inputs.setIndentation(12)
        self.tree_inputs.header().setStretchLastSection(True)
        self.tree_inputs.header().resizeSection(0, 145)
        self.tree_inputs.itemChanged.connect(self._on_input_item_edited)
        self.tree_inputs.itemSelectionChanged.connect(self._on_input_selection_changed)
        hlay.addWidget(self.tree_inputs, 1)

        self.splitter.addWidget(hist_pane)

        # --- Bottom half of extension: Maya Layer Editor (`Display | Anim` Tabs) ---
        layer_pane = QtWidgets.QFrame()
        llay = QtWidgets.QVBoxLayout(layer_pane)
        llay.setContentsMargins(0, 0, 0, 0)
        llay.setSpacing(2)

        layer_hdr = QtWidgets.QFrame()
        layer_hdr.setObjectName("MayaSectionHeader")
        lr_row = QtWidgets.QHBoxLayout(layer_hdr)
        lr_row.setContentsMargins(6, 2, 4, 2)
        lr_row.setSpacing(3)

        lbl_lr = QtWidgets.QLabel("LAYERS")
        lbl_lr.setObjectName("MayaSectionTitle")
        lr_row.addWidget(lbl_lr)

        # Maya Layer Editor Tab Toggle: Display | Anim
        self.btn_tab_display = QtWidgets.QPushButton("Display")
        self.btn_tab_display.setObjectName("MayaMaskPill")
        self.btn_tab_display.setCheckable(True)
        self.btn_tab_display.setChecked(True)
        self.btn_tab_display.setFixedHeight(18)
        self.btn_tab_display.clicked.connect(lambda: self.set_layer_editor_tab("DISPLAY"))
        lr_row.addWidget(self.btn_tab_display)

        self.btn_tab_anim = QtWidgets.QPushButton("Anim")
        self.btn_tab_anim.setObjectName("MayaMaskPill")
        self.btn_tab_anim.setCheckable(True)
        self.btn_tab_anim.setChecked(False)
        self.btn_tab_anim.setFixedHeight(18)
        self.btn_tab_anim.clicked.connect(lambda: self.set_layer_editor_tab("ANIM"))
        lr_row.addWidget(self.btn_tab_anim)

        lr_row.addStretch(1)

        self.btn_new_layer = QtWidgets.QPushButton("+ Layer")
        self.btn_new_layer.setToolTip("Create new Display or Animation Layer")
        self.btn_new_layer.setFixedHeight(18)
        self.btn_new_layer.clicked.connect(self._on_new_layer_clicked)

        self.btn_assign_layer = QtWidgets.QPushButton("Assign")
        self.btn_assign_layer.setToolTip("Assign selected objects / Key selected on active layer")
        self.btn_assign_layer.setFixedHeight(18)
        self.btn_assign_layer.clicked.connect(self._on_assign_layer_clicked)

        self.btn_del_layer = QtWidgets.QPushButton("Del")
        self.btn_del_layer.setToolTip("Delete selected Display or Animation Layer")
        self.btn_del_layer.setFixedHeight(18)
        self.btn_del_layer.clicked.connect(self._on_delete_layer_clicked)

        lr_row.addWidget(self.btn_new_layer)
        lr_row.addWidget(self.btn_assign_layer)
        lr_row.addWidget(self.btn_del_layer)
        llay.addWidget(layer_hdr)

        self.layer_stack = QtWidgets.QStackedWidget()
        llay.addWidget(self.layer_stack, 1)

        # Page 0: Maya Display Layers (V | P | Mode | Layer Name | #)
        self.tbl_layers = QtWidgets.QTableWidget(0, 5)
        self.tbl_layers.setHorizontalHeaderLabels(["V", "P", "Mode", "Layer Name", "#"])
        self.tbl_layers.verticalHeader().setVisible(False)
        self.tbl_layers.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_layers.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_layers.horizontalHeader().resizeSection(0, 24)
        self.tbl_layers.horizontalHeader().resizeSection(1, 24)
        self.tbl_layers.horizontalHeader().resizeSection(2, 34)
        self.tbl_layers.horizontalHeader().resizeSection(4, 28)
        self.tbl_layers.horizontalHeader().setStretchLastSection(False)
        from qtpy.QtWidgets import QHeaderView

        self.tbl_layers.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tbl_layers.cellClicked.connect(self._on_layer_cell_clicked)
        self.layer_stack.addWidget(self.tbl_layers)

        # Page 1: Maya Animation Layers (M | S | L | Mode | Layer Name | Wt)
        self.tbl_anim_layers = QtWidgets.QTableWidget(0, 6)
        self.tbl_anim_layers.setHorizontalHeaderLabels(["M", "S", "L", "Mode", "Anim Layer", "Wt"])
        self.tbl_anim_layers.verticalHeader().setVisible(False)
        self.tbl_anim_layers.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_anim_layers.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_anim_layers.horizontalHeader().resizeSection(0, 22)
        self.tbl_anim_layers.horizontalHeader().resizeSection(1, 22)
        self.tbl_anim_layers.horizontalHeader().resizeSection(2, 22)
        self.tbl_anim_layers.horizontalHeader().resizeSection(3, 36)
        self.tbl_anim_layers.horizontalHeader().resizeSection(5, 38)
        self.tbl_anim_layers.horizontalHeader().setStretchLastSection(False)
        self.tbl_anim_layers.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tbl_anim_layers.cellClicked.connect(self._on_anim_layer_cell_clicked)
        self.layer_stack.addWidget(self.tbl_anim_layers)

        self._active_layer_tab = "DISPLAY"
        self.splitter.addWidget(layer_pane)
        self.splitter.setSizes([185, 145])

    def set_layer_editor_tab(self, tab_mode: str) -> None:
        m = (tab_mode or "DISPLAY").upper()
        self._active_layer_tab = "ANIM" if m == "ANIM" else "DISPLAY"
        self.btn_tab_display.blockSignals(True)
        self.btn_tab_anim.blockSignals(True)
        self.btn_tab_display.setChecked(self._active_layer_tab == "DISPLAY")
        self.btn_tab_anim.setChecked(self._active_layer_tab == "ANIM")
        self.btn_tab_display.blockSignals(False)
        self.btn_tab_anim.blockSignals(False)
        if self._active_layer_tab == "ANIM":
            self.btn_new_layer.setText("+ Anim")
            self.btn_assign_layer.setText("Key")
            self.layer_stack.setCurrentIndex(1)
        else:
            self.btn_new_layer.setText("+ Layer")
            self.btn_assign_layer.setText("Assign")
            self.layer_stack.setCurrentIndex(0)
        self.refresh()

    def _install_axis_badge_delegate(self, channels_widget: Any) -> None:
        """Install a custom `QStyledItemDelegate` on `tbl000` column 1 to render Maya channel names (`Translate X`, `Rotate Y`, `Scale Z`) with X/Y/Z axis dots."""
        try:
            from qtpy import QtCore, QtGui, QtWidgets

            tbl = getattr(channels_widget, "tbl000", None)
            if tbl is None:
                return

            axis_colors = {
                "X": QtGui.QColor("#E35D6A"),
                "Y": QtGui.QColor("#4AB866"),
                "Z": QtGui.QColor("#4E9CE6"),
            }
            maya_labels = {
                "location_x": "Translate X",
                "location_y": "Translate Y",
                "location_z": "Translate Z",
                "rotation_x": "Rotate X",
                "rotation_y": "Rotate Y",
                "rotation_z": "Rotate Z",
                "scale_x": "Scale X",
                "scale_y": "Scale Y",
                "scale_z": "Scale Z",
                "hide_viewport": "Visibility",
            }

            class _MayaChannelAxisDelegate(QtWidgets.QStyledItemDelegate):
                def sizeHint(self, option, index):
                    base = super().sizeHint(option, index)
                    return QtCore.QSize(max(116, base.width() + 34), max(20, base.height()))

                def paint(self, painter, option, index) -> None:
                    raw = str(index.data(QtCore.Qt.DisplayRole) or "").strip()
                    if not raw:
                        super().paint(painter, option, index)
                        return

                    painter.save()
                    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
                    r = option.rect
                    is_sel = bool(option.state & QtWidgets.QStyle.State_Selected)
                    if is_sel:
                        painter.fillRect(r, QtGui.QColor("#225976"))
                    elif index.row() % 2 == 1:
                        painter.fillRect(r, QtGui.QColor("#22252A"))
                    else:
                        painter.fillRect(r, QtGui.QColor("#1E2126"))

                    label = maya_labels.get(raw, raw)
                    last_ch = label[-1].upper() if label else ""
                    text_x = r.left() + 6
                    if last_ch in axis_colors and (
                        raw.endswith(("_x", "_y", "_z"))
                        or label.endswith((" X", " Y", " Z"))
                    ):
                        dot_rect = QtCore.QRectF(
                            float(r.left() + 6),
                            float(r.center().y() - 3.0),
                            6.0,
                            6.0,
                        )
                        painter.setPen(QtCore.Qt.NoPen)
                        painter.setBrush(axis_colors[last_ch])
                        painter.drawEllipse(dot_rect)
                        text_x = r.left() + 17

                    f = painter.font()
                    f.setPixelSize(11)
                    f.setBold(is_sel)
                    painter.setFont(f)
                    painter.setPen(QtGui.QColor("#FFFFFF" if is_sel else "#D5DCE6"))
                    text_rect = QtCore.QRect(text_x, r.top(), max(10, r.width() - (text_x - r.left()) - 4), r.height())
                    painter.drawText(text_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, label)
                    painter.restore()

            delegate = _MayaChannelAxisDelegate(tbl)
            tbl.setItemDelegateForColumn(0, delegate)
            tbl._lf_axis_delegate_installed = True
            tbl._lf_axis_delegate = delegate
        except Exception:
            pass

    def _clamp_host_channel_table_height(self) -> None:
        """Keep `channels_widget` and `tbl000` compact so `SHAPES` and `INPUTS` sit directly below `Scale Z`."""
        try:
            if self.host is None:
                return
            for attr_name in ("header", "footer", "txt001"):
                sub = getattr(self.host, attr_name, None)
                if sub is not None and hasattr(sub, "hide"):
                    sub.hide()
            self.host.setMinimumHeight(0)
            self.host.setMaximumHeight(212)
            tbl = getattr(self.host, "tbl000", None)
            if tbl is not None:
                tbl.setMinimumHeight(0)
                tbl.setMaximumHeight(180)
                if tbl.columnCount() > 0 and tbl.columnWidth(0) < 108:
                    tbl.setColumnWidth(0, 108)
                if getattr(tbl, "_lf_axis_delegate", None) is not None:
                    tbl.setItemDelegateForColumn(0, tbl._lf_axis_delegate)
                tbl.viewport().update()
        except Exception:
            pass

    def refresh(self) -> None:
        """Synchronize Object Header, `SHAPES`, `INPUTS`, `Display Layers`, and `Animation Layers` from Blender's live scene."""
        if self._updating:
            return
        self._updating = True
        try:
            import bpy
            from qtpy import QtCore, QtGui, QtWidgets
            from .. import advanced

            self._clamp_host_channel_table_height()

            active = getattr(bpy.context.view_layer.objects, "active", None) if bpy.context.view_layer else None
            sinfo = get_object_shape_info(active)

            if active is not None:
                self.lbl_obj_name.setText(active.name)
                otype = str(getattr(active, "type", "EMPTY")).lower()
                sub = f"{otype} transform" if otype != "empty" else "dag group"
                if sinfo["linked"]:
                    sub += " (ref)"
                self.lbl_obj_subtitle.setText(sub)
            else:
                self.lbl_obj_name.setText("(No Selection)")
                self.lbl_obj_subtitle.setText("idle")

            self.lbl_shape_type.setText(
                f"{sinfo['shape_type']} (LINKED)" if sinfo["linked"] else str(sinfo["shape_type"])
            )
            self.txt_shape_name.blockSignals(True)
            self.txt_shape_name.setText(sinfo["shape_name"] if sinfo["has_shape"] else "(None)")
            self.txt_shape_name.setReadOnly(not sinfo["editable"])
            self.txt_shape_name.blockSignals(False)

            # Populate INPUTS tree with Figma Make emerald active dot indicator
            self.tree_inputs.blockSignals(True)
            self.tree_inputs.clear()
            inputs = get_object_inputs(active)
            for node in inputs:
                status_prefix = "● " if node.get("show_viewport", True) else "○ "
                top = QtWidgets.QTreeWidgetItem([node["node_name"], f"{status_prefix}{node['node_type']}"])
                top.setIcon(0, icons.get_icon("dag_modifier", 14))
                font = top.font(0)
                font.setBold(True)
                top.setFont(0, font)
                top.setForeground(0, QtGui.QBrush(QtGui.QColor("#C8D1DC")))
                top.setForeground(
                    1,
                    QtGui.QBrush(
                        QtGui.QColor("#4AB866" if node.get("show_viewport", True) else "#6E7681")
                    ),
                )
                top.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self.tree_inputs.addTopLevelItem(top)

                for attr in node["attributes"]:
                    child = QtWidgets.QTreeWidgetItem([attr["label"], str(attr["value"])])
                    child.setData(0, QtCore.Qt.UserRole, (node["node_name"], attr["name"]))
                    flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                    if attr.get("editable", True):
                        flags |= QtCore.Qt.ItemIsEditable
                    child.setFlags(flags)
                    child.setForeground(0, QtGui.QBrush(QtGui.QColor("#B8C2D0")))
                    child.setForeground(1, QtGui.QBrush(QtGui.QColor("#66C2F0")))
                    top.addChild(child)
                top.setExpanded(True)
            self.tree_inputs.blockSignals(False)

            # Populate Display Layers table
            layers = list_display_layers()
            self.tbl_layers.blockSignals(True)
            self.tbl_layers.setRowCount(len(layers))
            for r, lyr in enumerate(layers):
                v_item = QtWidgets.QTableWidgetItem("V" if lyr["visible"] else " ")
                v_item.setTextAlignment(QtCore.Qt.AlignCenter)
                v_item.setForeground(
                    QtGui.QBrush(QtGui.QColor("#66C2F0" if lyr["visible"] else "#555B66"))
                )
                v_item.setData(QtCore.Qt.UserRole, lyr["name"])

                p_item = QtWidgets.QTableWidgetItem("P" if lyr["playback"] else " ")
                p_item.setTextAlignment(QtCore.Qt.AlignCenter)
                p_item.setForeground(
                    QtGui.QBrush(QtGui.QColor("#7ED491" if lyr["playback"] else "#555B66"))
                )

                mode_str = " " if lyr["mode"] == "N" else lyr["mode"]
                m_item = QtWidgets.QTableWidgetItem(mode_str)
                m_item.setTextAlignment(QtCore.Qt.AlignCenter)
                m_color = "#F2B857" if lyr["mode"] == "T" else ("#66C2F0" if lyr["mode"] == "R" else "#9DA5B1")
                m_item.setForeground(QtGui.QBrush(QtGui.QColor(m_color)))

                n_item = QtWidgets.QTableWidgetItem(lyr["name"])
                c_item = QtWidgets.QTableWidgetItem(str(lyr["member_count"]))
                c_item.setTextAlignment(QtCore.Qt.AlignCenter)

                self.tbl_layers.setItem(r, 0, v_item)
                self.tbl_layers.setItem(r, 1, p_item)
                self.tbl_layers.setItem(r, 2, m_item)
                self.tbl_layers.setItem(r, 3, n_item)
                self.tbl_layers.setItem(r, 4, c_item)
                self.tbl_layers.setRowHeight(r, 20)
            self.tbl_layers.blockSignals(False)

            # Populate Animation Layers table
            anim_lyrs = advanced.list_anim_layers(active) if active is not None else []
            self.tbl_anim_layers.blockSignals(True)
            self.tbl_anim_layers.setRowCount(len(anim_lyrs))
            for r, alyr in enumerate(anim_lyrs):
                m_item = QtWidgets.QTableWidgetItem("M" if alyr["mute"] else "·")
                m_item.setTextAlignment(QtCore.Qt.AlignCenter)
                m_item.setForeground(QtGui.QBrush(QtGui.QColor("#E35D6A" if alyr["mute"] else "#555B66")))
                m_item.setData(QtCore.Qt.UserRole, alyr["name"])

                s_item = QtWidgets.QTableWidgetItem("S" if alyr["solo"] else "·")
                s_item.setTextAlignment(QtCore.Qt.AlignCenter)
                s_item.setForeground(QtGui.QBrush(QtGui.QColor("#E5A93C" if alyr["solo"] else "#555B66")))

                l_item = QtWidgets.QTableWidgetItem("L" if alyr["lock"] else "·")
                l_item.setTextAlignment(QtCore.Qt.AlignCenter)
                l_item.setForeground(QtGui.QBrush(QtGui.QColor("#69B8DC" if alyr["lock"] else "#555B66")))

                mode_short = "BASE" if alyr["is_base"] else ("OVR" if alyr["mode"] == "OVERRIDE" else "ADD")
                md_item = QtWidgets.QTableWidgetItem(mode_short)
                md_item.setTextAlignment(QtCore.Qt.AlignCenter)
                md_item.setForeground(
                    QtGui.QBrush(QtGui.QColor("#4AB866" if mode_short == "ADD" else "#69B8DC"))
                )

                nm_item = QtWidgets.QTableWidgetItem(alyr["name"])
                nm_item.setForeground(QtGui.QBrush(QtGui.QColor("#E6EDF3")))

                wt_item = QtWidgets.QTableWidgetItem(f"{float(alyr['weight']):.2f}")
                wt_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                wt_item.setForeground(QtGui.QBrush(QtGui.QColor("#69B8DC")))

                self.tbl_anim_layers.setItem(r, 0, m_item)
                self.tbl_anim_layers.setItem(r, 1, s_item)
                self.tbl_anim_layers.setItem(r, 2, l_item)
                self.tbl_anim_layers.setItem(r, 3, md_item)
                self.tbl_anim_layers.setItem(r, 4, nm_item)
                self.tbl_anim_layers.setItem(r, 5, wt_item)
                self.tbl_anim_layers.setRowHeight(r, 20)
            self.tbl_anim_layers.blockSignals(False)
        except Exception:
            pass
        finally:
            self._updating = False

    def _on_shape_renamed(self) -> None:
        if self._updating:
            return
        import bpy

        active = getattr(bpy.context.view_layer.objects, "active", None)
        if active is not None:
            rename_object_shape(active, self.txt_shape_name.text())
            self.refresh()

    def _on_input_selection_changed(self) -> None:
        global _selected_input_target
        from qtpy import QtCore

        items = self.tree_inputs.selectedItems()
        if not items:
            _selected_input_target = None
            return
        meta = items[0].data(0, QtCore.Qt.UserRole)
        if isinstance(meta, tuple) and len(meta) == 2:
            _selected_input_target = (str(meta[0]), str(meta[1]))
        else:
            _selected_input_target = None

    def _on_input_item_edited(self, item: Any, column: int) -> None:
        if self._updating or column != 1 or item is None:
            return
        import bpy
        from qtpy import QtCore

        meta = item.data(0, QtCore.Qt.UserRole)
        if not (isinstance(meta, tuple) and len(meta) == 2):
            return
        node_name, attr_name = meta
        active = getattr(bpy.context.view_layer.objects, "active", None)
        if active is not None:
            set_object_input_attribute(active, str(node_name), str(attr_name), item.text(1))
            self.refresh()

    def _on_add_geonodes_clicked(self) -> None:
        ensure_procedural_geonodes_modifier()
        self.refresh()

    def _on_delete_history_clicked(self) -> None:
        import bpy

        try:
            bpy.ops.landfall_studio.delete_history()
        except Exception:
            delete_construction_history()
        self.refresh()

    def _on_new_layer_clicked(self) -> None:
        if self._active_layer_tab == "ANIM":
            from .. import advanced

            advanced.create_anim_layer(mode="ADD", weight=1.0)
            self.refresh()
            return
        create_display_layer(assign_selected=True)
        self.refresh()

    def _on_assign_layer_clicked(self) -> None:
        from qtpy import QtCore

        if self._active_layer_tab == "ANIM":
            from .. import advanced

            row = self.tbl_anim_layers.currentRow()
            item = self.tbl_anim_layers.item(max(0, row), 0)
            lname = str(item.data(QtCore.Qt.UserRole) or "") if item is not None else ""
            if lname:
                advanced.keyframe_on_anim_layer(layer_name=lname)
                self.refresh()
            return

        row = self.tbl_layers.currentRow()
        if row < 0:
            return
        item = self.tbl_layers.item(row, 0)
        if item is not None:
            lname = str(item.data(QtCore.Qt.UserRole) or "")
            if lname:
                assign_objects_to_display_layer(lname)
                self.refresh()

    def _on_delete_layer_clicked(self) -> None:
        from qtpy import QtCore

        if self._active_layer_tab == "ANIM":
            from .. import advanced

            row = self.tbl_anim_layers.currentRow()
            if row < 0:
                return
            item = self.tbl_anim_layers.item(row, 0)
            lname = str(item.data(QtCore.Qt.UserRole) or "") if item is not None else ""
            if lname:
                advanced.remove_anim_layer(layer_name=lname)
                self.refresh()
            return

        row = self.tbl_layers.currentRow()
        if row < 0:
            return
        item = self.tbl_layers.item(row, 0)
        if item is not None:
            lname = str(item.data(QtCore.Qt.UserRole) or "")
            if lname:
                delete_display_layer(lname)
                self.refresh()

    def _on_layer_cell_clicked(self, row: int, col: int) -> None:
        from qtpy import QtCore

        item = self.tbl_layers.item(row, 0)
        if item is None:
            return
        lname = str(item.data(QtCore.Qt.UserRole) or "")
        if not lname:
            return
        info = next((l for l in list_display_layers() if l["name"] == lname), None)
        if info is None:
            return
        if col == 0:
            set_display_layer_state(lname, visible=not info["visible"])
        elif col == 1:
            set_display_layer_state(lname, playback=not info["playback"])
        elif col == 2:
            set_display_layer_state(lname, cycle_mode=True)
        self.refresh()

    def _on_anim_layer_cell_clicked(self, row: int, col: int) -> None:
        from qtpy import QtCore
        from .. import advanced

        item = self.tbl_anim_layers.item(row, 0)
        if item is None:
            return
        lname = str(item.data(QtCore.Qt.UserRole) or "")
        if not lname:
            return
        info = next((l for l in advanced.list_anim_layers() if l["name"] == lname), None)
        if info is None:
            return
        if col == 0:
            advanced.set_anim_layer_state(layer_name=lname, mute=not info["mute"])
        elif col == 1:
            advanced.set_anim_layer_state(layer_name=lname, solo=not info["solo"])
        elif col == 2:
            advanced.set_anim_layer_state(layer_name=lname, lock=not info["lock"])
        elif col == 3 and not info["is_base"]:
            next_m = "OVERRIDE" if info["mode"] == "ADD" else "ADD"
            advanced.set_anim_layer_state(layer_name=lname, mode=next_m)
        self.refresh()


_channel_box_ext_instance: Optional[MayaChannelBoxExtensionWidget] = None


def ensure_channel_box_extensions(channels_widget: Any) -> Optional[MayaChannelBoxExtensionWidget]:
    """Attach `MayaChannelBoxExtensionWidget` (`SHAPES` + `INPUTS` + `Display/Anim Layers`) to `channels_widget`."""
    global _channel_box_ext_instance
    if channels_widget is None:
        return None
    if _channel_box_ext_instance is not None and _channel_box_ext_instance.host is channels_widget:
        style.apply_studio_style(channels_widget)
        _channel_box_ext_instance.refresh()
        return _channel_box_ext_instance

    try:
        style.apply_studio_style(channels_widget)
        # Hide floating uitk header bar and cap Channel Box height so SHAPES & INPUTS sit flush below Scale Z
        hdr = getattr(channels_widget, "header", None)
        if hdr is not None:
            hdr.hide()
        txt1 = getattr(channels_widget, "txt001", None)
        if txt1 is not None:
            txt1.hide()
        channels_widget.setMinimumHeight(0)
        channels_widget.setMaximumHeight(212)
        ext = MayaChannelBoxExtensionWidget(channels_widget)
        channels_widget._lf_cb_ext_container = ext
        _channel_box_ext_instance = ext
        ext.refresh()
        return ext
    except Exception:
        return None


def refresh_channel_box_extensions() -> None:
    if _channel_box_ext_instance is not None:
        _channel_box_ext_instance.refresh()


def teardown_channel_box_extensions() -> None:
    global _channel_box_ext_instance, _selected_input_target
    _selected_input_target = None
    if _channel_box_ext_instance is not None:
        try:
            if getattr(_channel_box_ext_instance, "obj_header_bar", None) is not None:
                _channel_box_ext_instance.obj_header_bar.hide()
                _channel_box_ext_instance.obj_header_bar.deleteLater()
            _channel_box_ext_instance.root.hide()
            _channel_box_ext_instance.root.deleteLater()
        except Exception:
            pass
        _channel_box_ext_instance = None
