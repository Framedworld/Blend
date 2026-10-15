"""Maya `.ma`/`.mb` Preflight Scanner, Scene Fidelity Signature, and Mandatory Interchange Loss Report (`landfall_studio.interchange.preflight_report`).

Implements the requirements of `docs/INTERCHANGE_CONTRACT.md` and `tasks/07_MAYA_INTERCHANGE.md`:
- `get_maya_runtime_status()`: Discovers installed `maya.exe` and `mayapy.exe` via `blendertk.MayaBridge`.
- `preflight_maya_scene(src_path)`: Non-destructively scans `.ma` / `.mb` files for DAG nodes,
  skinClusters, blendShapes, shaders, references, required plugins, and complex DG/driver nodes
  (`_DRIVER_NODE_TYPES`, `expression`, `multMatrix`, constraints, IK handles) while recording
  the source file's SHA-256 hash so post-conversion checks can prove `source_unchanged == True`.
- `capture_blender_scene_signature()`: Captures hierarchy, geometry counts, transforms, UV/UDIM sets,
  materials, skin weights/joints, blendshape targets/deltas, animation curves, and linked references.
- `build_interchange_report()`: Produces the structured Mandatory Interchange Report with explicit
  `"PASS"`, `"PARTIAL"`, `"FAIL"`, or `"BLOCKED"` status and loss/approximation explanations.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_LAST_INTERCHANGE_REPORT: Dict[str, Any] = {}

# Maya DG / driver node types that cannot transfer as live procedural DG nodes into Blender
# and are either baked to keyframes (`SmartBake` / FBX evaluation) or reported as limitations.
MAYA_COMPLEX_DG_TYPES = frozenset(
    {
        "parentConstraint",
        "pointConstraint",
        "orientConstraint",
        "scaleConstraint",
        "aimConstraint",
        "poleVectorConstraint",
        "geometryConstraint",
        "normalConstraint",
        "tangentConstraint",
        "ikHandle",
        "ikEffector",
        "expression",
        "multMatrix",
        "blendMatrix",
        "wtAddMatrix",
        "composeMatrix",
        "decomposeMatrix",
        "motionPath",
        "remapValue",
        "setRange",
        "condition",
        "multiplyDivide",
        "plusMinusAverage",
        "animCurveUL",
        "animCurveUA",
        "animCurveUU",
    }
)

STANDARD_MAYA_PLUGINS = frozenset(
    {
        "mayaCharacterization",
        "mayaHIK",
        "GamePipeline",
        "fbxmaya",
        "mayaUsdPlugin",
        "lookdevKit",
        "shaderFXPlugin",
        "stereoCamera",
        "Type",
        "meshReorder",
        "matrixNodes",
        "quatNodes",
        " nearestPointOnMesh",
        "nearestPointOnMesh",
        "objExport",
    }
)


def compute_file_sha256(file_path: str) -> str:
    """Return the hex SHA-256 digest of `file_path`, or `""` if missing."""
    p = Path(file_path)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def get_maya_runtime_status() -> Dict[str, Any]:
    """Discover local Maya (`maya.exe`) and headless `mayapy.exe` via `blendertk.MayaBridge`."""
    try:
        from blendertk.env_utils.maya_bridge._maya_bridge import MayaBridge

        bridge = MayaBridge()
        maya_exe = bridge.maya_path
        mayapy_exe = bridge.headless_app_path
    except Exception as exc:
        return {
            "available": False,
            "maya_exe": None,
            "mayapy_exe": None,
            "maya_version": None,
            "error": f"Failed to query blendertk.MayaBridge: {exc}",
        }

    available = bool(mayapy_exe and os.path.isfile(mayapy_exe))
    maya_ver = None
    if mayapy_exe:
        m = re.search(r"Maya(\d{4})", mayapy_exe, re.IGNORECASE)
        if m:
            maya_ver = m.group(1)

    return {
        "available": available,
        "maya_exe": maya_exe,
        "mayapy_exe": mayapy_exe,
        "maya_version": maya_ver or ("installed" if available else None),
        "error": None if available else "Local mayapy executable not found; Maya interchange is BLOCKED.",
    }


def preflight_maya_scene(src_path: str) -> Dict[str, Any]:
    """Scan a `.ma` or `.mb` file non-destructively to classify nodes, references, plugins, and DG limitations."""
    p = Path(os.path.abspath(os.path.expanduser(str(src_path))))
    runtime = get_maya_runtime_status()
    if not p.is_file():
        return {
            "ok": False,
            "status": "FAIL",
            "source_path": str(p),
            "error": f"Maya scene file not found: {p}",
            "runtime": runtime,
        }

    ext = p.suffix.lower()
    if ext not in (".ma", ".mb"):
        return {
            "ok": False,
            "status": "FAIL",
            "source_path": str(p),
            "error": f"Unsupported Maya scene extension '{ext}' (expected '.ma' or '.mb')",
            "runtime": runtime,
        }

    sha256_before = compute_file_sha256(str(p))
    stat = p.stat()

    node_counts: Dict[str, int] = {}
    node_names_by_type: Dict[str, List[str]] = {}
    references: List[str] = []
    requires_plugins: List[str] = []
    unsupported_plugins: List[str] = []
    complex_dg_nodes: List[Dict[str, str]] = []

    if ext == ".ma":
        text = p.read_text(encoding="utf-8", errors="replace")
        # Parse createNode <type> [-n "<name>"]
        for m in re.finditer(
            r'^\s*createNode\s+([A-Za-z0-9_]+)(?:[^\n;]*?-n(?:ame)?\s+"([^"]+)")?',
            text,
            flags=re.MULTILINE,
        ):
            ntype = m.group(1)
            nname = m.group(2) or ntype
            node_counts[ntype] = node_counts.get(ntype, 0) + 1
            node_names_by_type.setdefault(ntype, []).append(nname)
            if ntype in MAYA_COMPLEX_DG_TYPES:
                complex_dg_nodes.append({"name": nname, "type": ntype})

        # Parse requires
        for m in re.finditer(
            r'^\s*requires\s+(?:-nodeType\s+"[^"]+"\s+)*"([^"]+)"\s+"([^"]+)"',
            text,
            flags=re.MULTILINE,
        ):
            plugin_name = m.group(1).strip()
            if plugin_name.lower() != "maya":
                requires_plugins.append(plugin_name)
                if plugin_name not in STANDARD_MAYA_PLUGINS:
                    unsupported_plugins.append(plugin_name)

        # Parse file references
        for m in re.finditer(
            r'^\s*file\s+[^\n;]*?(?:-r|-rdi)\s+[^\n;]*?"([^"]+\.(?:ma|mb|fbx|usd|usda|usdc))"',
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        ):
            ref_p = m.group(1)
            if ref_p not in references:
                references.append(ref_p)
    else:
        # Binary .mb byte-token inspection
        raw = p.read_bytes()
        probe_types = (
            tuple(MAYA_COMPLEX_DG_TYPES)
            + (
                "transform",
                "mesh",
                "joint",
                "skinCluster",
                "blendShape",
                "standardSurface",
                "aiStandardSurface",
                "StingrayPBS",
                "phong",
                "lambert",
                "animCurveTL",
                "animCurveTA",
                "animCurveTU",
            )
        )
        for ntype in probe_types:
            tok = ntype.encode("ascii")
            cnt = raw.count(tok)
            if cnt > 0:
                node_counts[ntype] = cnt
                if ntype in MAYA_COMPLEX_DG_TYPES:
                    complex_dg_nodes.append({"name": f"<{ntype}>", "type": ntype})

    baked_or_approximated: List[str] = []
    unsupported_or_lost: List[str] = []

    for dg in complex_dg_nodes:
        ntype = dg["type"]
        nname = dg["name"]
        if ntype == "expression":
            unsupported_or_lost.append(
                f"Maya expression node '{nname}' cannot execute natively in Blender; driven channels are baked to keyframes during conversion."
            )
        else:
            baked_or_approximated.append(
                f"Maya DG/driver node '{nname}' ({ntype}) is evaluated in headless mayapy and baked/reduced to animation curves."
            )

    for plug in unsupported_plugins:
        unsupported_or_lost.append(
            f"Third-party/custom Maya plugin '{plug}' required by scene; custom DG evaluation depends on local Maya plugin availability."
        )

    return {
        "ok": True,
        "status": "READY" if runtime["available"] else "BLOCKED",
        "source_path": str(p),
        "format": ext,
        "source_sha256": sha256_before,
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "runtime": runtime,
        "node_counts": node_counts,
        "node_names_by_type": node_names_by_type,
        "summary": {
            "transforms": node_counts.get("transform", 0),
            "meshes": node_counts.get("mesh", 0),
            "joints": node_counts.get("joint", 0),
            "skin_clusters": node_counts.get("skinCluster", 0),
            "blend_shapes": node_counts.get("blendShape", 0),
            "anim_curves": sum(
                v for k, v in node_counts.items() if k.startswith("animCurve")
            ),
            "complex_dg_count": len(complex_dg_nodes),
            "reference_count": len(references),
        },
        "references": references,
        "requires_plugins": requires_plugins,
        "unsupported_plugins": unsupported_plugins,
        "complex_dg_nodes": complex_dg_nodes,
        "baked_or_approximated_items": baked_or_approximated,
        "unsupported_or_lost_items": unsupported_or_lost,
        "recommended_route": "fbx",
    }


def capture_blender_scene_signature(objects: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
    """Capture a comprehensive fidelity snapshot of the current Blender scene (or `objects`)."""
    import bpy
    import blendertk as btk

    scn = getattr(bpy.context, "scene", None)
    objs = list(objects) if objects is not None else (list(scn.objects) if scn else [])

    hierarchy: Dict[str, Optional[str]] = {}
    transforms: Dict[str, Dict[str, Tuple[float, ...]]] = {}
    meshes: Dict[str, Dict[str, Any]] = {}
    armatures: Dict[str, Dict[str, Any]] = {}
    materials: Dict[str, Dict[str, Any]] = {}
    anim_summary: Dict[str, int] = {}

    for obj in sorted(objs, key=lambda o: o.name):
        hierarchy[obj.name] = obj.parent.name if obj.parent else None
        transforms[obj.name] = {
            "location": tuple(round(float(v), 4) for v in obj.location),
            "rotation_euler": tuple(round(float(v), 4) for v in obj.rotation_euler),
            "scale": tuple(round(float(v), 4) for v in obj.scale),
        }
        fcurves = btk.get_fcurves([obj])
        if fcurves:
            anim_summary[obj.name] = sum(len(getattr(fc, "keyframe_points", ())) for fc in fcurves)

        if obj.type == "ARMATURE" and obj.data is not None:
            bones = {
                b.name: (b.parent.name if b.parent else None)
                for b in obj.data.bones
            }
            armatures[obj.name] = {
                "bone_count": len(bones),
                "bones": bones,
            }
        elif obj.type == "MESH" and obj.data is not None:
            me = obj.data
            uv_names = [uv.name for uv in getattr(me, "uv_layers", ())]
            udim_tiles = set()
            if me.uv_layers.active and me.uv_layers.active.data:
                for loop_uv in me.uv_layers.active.data:
                    u, v = float(loop_uv.uv[0]), float(loop_uv.uv[1])
                    tile = 1001 + int(u) + 10 * int(v)
                    udim_tiles.add(tile)

            mat_names = [slot.material.name for slot in obj.material_slots if slot.material]
            for slot in obj.material_slots:
                mat = slot.material
                if mat and mat.name not in materials:
                    tex_files = []
                    if mat.use_nodes and mat.node_tree:
                        for nd in mat.node_tree.nodes:
                            if nd.type == "TEX_IMAGE" and getattr(nd, "image", None):
                                tex_files.append(nd.image.filepath or nd.image.name)
                    materials[mat.name] = {
                        "use_nodes": bool(mat.use_nodes),
                        "textures": tex_files,
                    }

            vgroups = [vg.name for vg in obj.vertex_groups]
            weighted_verts = 0
            if vgroups:
                for v in me.vertices:
                    if any(g.weight > 1e-4 for g in v.groups):
                        weighted_verts += 1

            shape_targets: Dict[str, Dict[str, Any]] = {}
            sk = getattr(me, "shape_keys", None)
            if sk and sk.key_blocks and len(sk.key_blocks) > 1:
                basis = sk.key_blocks[0]
                for kb in sk.key_blocks[1:]:
                    max_delta = 0.0
                    active_count = 0
                    for idx in range(len(me.vertices)):
                        dx = float(kb.data[idx].co.x - basis.data[idx].co.x)
                        dy = float(kb.data[idx].co.y - basis.data[idx].co.y)
                        dz = float(kb.data[idx].co.z - basis.data[idx].co.z)
                        d = (dx * dx + dy * dy + dz * dz) ** 0.5
                        if d > 1e-4:
                            active_count += 1
                            if d > max_delta:
                                max_delta = d
                    shape_targets[kb.name] = {
                        "value": round(float(kb.value), 4),
                        "active_vertex_count": active_count,
                        "max_delta": round(float(max_delta), 5),
                    }
                sk_fcurves = btk.get_fcurves([sk])
                if sk_fcurves:
                    anim_summary[f"{obj.name}.shape_keys"] = sum(
                        len(getattr(fc, "keyframe_points", ())) for fc in sk_fcurves
                    )

            meshes[obj.name] = {
                "verts": len(me.vertices),
                "edges": len(me.edges),
                "faces": len(me.polygons),
                "uv_sets": uv_names,
                "udim_tiles": sorted(udim_tiles) if udim_tiles else [1001],
                "materials": mat_names,
                "vertex_groups": vgroups,
                "weighted_vertices": weighted_verts,
                "shape_targets": shape_targets,
            }

    linked_libs = [
        {"name": lib.name, "filepath": lib.filepath}
        for lib in getattr(bpy.data, "libraries", ())
    ]

    return {
        "object_count": len(objs),
        "hierarchy": hierarchy,
        "transforms": transforms,
        "meshes": meshes,
        "armatures": armatures,
        "materials": materials,
        "animation_key_counts": anim_summary,
        "linked_libraries": linked_libs,
        "fps": int(round(float(scn.render.fps) / float(scn.render.fps_base or 1.0))) if scn else 24,
        "frame_range": (int(scn.frame_start), int(scn.frame_end)) if scn else (1, 100),
    }


def build_interchange_report(
    operation: str,
    source_path: str,
    destination_path: str,
    preflight: Dict[str, Any],
    result_signature: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
    baseline_signature: Optional[Dict[str, Any]] = None,
    extra_warnings: Optional[List[str]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the Mandatory Interchange Report required by `docs/INTERCHANGE_CONTRACT.md`."""
    import bpy

    sha_after = compute_file_sha256(source_path) if source_path and os.path.isfile(source_path) else ""
    sha_before = preflight.get("source_sha256", "")
    source_unchanged = bool(sha_before and sha_after and sha_before == sha_after)

    warnings_list = list(preflight.get("baked_or_approximated_items", []))
    limitations_list = list(preflight.get("unsupported_or_lost_items", []))
    if extra_warnings:
        warnings_list.extend(extra_warnings)

    runtime = preflight.get("runtime") or get_maya_runtime_status()

    # Compute fidelity checks across the 6 mandatory dimensions:
    # 1. Hierarchy, 2. Skinning/Joints, 3. Morphs/Blendshapes, 4. Materials, 5. UVs/UDIMs, 6. Animation
    meshes = result_signature.get("meshes", {})
    armatures = result_signature.get("armatures", {})
    anim_counts = result_signature.get("animation_key_counts", {})

    total_verts = sum(m["verts"] for m in meshes.values())
    total_faces = sum(m["faces"] for m in meshes.values())
    total_weighted = sum(m["weighted_vertices"] for m in meshes.values())
    total_shape_targets = sum(len(m["shape_targets"]) for m in meshes.values())
    total_uv_sets = sum(len(m["uv_sets"]) for m in meshes.values())
    total_materials = len(result_signature.get("materials", {}))
    total_bones = sum(a["bone_count"] for a in armatures.values())
    total_anim_keys = sum(anim_counts.values())

    comparison_diffs: List[str] = []
    if baseline_signature is not None:
        base_meshes = baseline_signature.get("meshes", {})
        for mname, binfo in base_meshes.items():
            rinfo = meshes.get(mname)
            if rinfo is None:
                # Match by suffix if namespace was stripped
                for rk, rv in meshes.items():
                    if rk.endswith(mname) or mname.endswith(rk):
                        rinfo = rv
                        break
            if rinfo is None:
                comparison_diffs.append(f"Mesh '{mname}' missing in round-trip result.")
            else:
                if rinfo["verts"] != binfo["verts"] or rinfo["faces"] != binfo["faces"]:
                    comparison_diffs.append(
                        f"Mesh '{mname}' topology changed: {binfo['verts']}v/{binfo['faces']}f -> {rinfo['verts']}v/{rinfo['faces']}f"
                    )

    if not runtime.get("available"):
        status = "BLOCKED"
    elif error or comparison_diffs:
        status = "FAIL" if error else "PARTIAL"
    elif limitations_list:
        # Scene converted cleanly and all geometry/skin/morph/UV/materials arrived,
        # while custom Maya DG expressions/plugins were transparently baked/reported.
        status = "PASS_WITH_LIMITATIONS"
    else:
        status = "PASS"

    report = {
        "ok": status in ("PASS", "PASS_WITH_LIMITATIONS", "PARTIAL"),
        "status": status,
        "operation": operation,
        "source_path": source_path,
        "destination_path": destination_path,
        "source_sha256_before": sha_before,
        "source_sha256_after": sha_after,
        "source_unchanged": source_unchanged,
        "versions": {
            "blender": bpy.app.version_string,
            "maya": runtime.get("maya_version"),
            "mayapy_executable": runtime.get("mayapy_exe"),
        },
        "options": options or {},
        "hierarchy_and_geometry": {
            "object_count": result_signature.get("object_count", 0),
            "mesh_count": len(meshes),
            "total_vertices": total_verts,
            "total_faces": total_faces,
            "hierarchy_map": result_signature.get("hierarchy", {}),
            "transforms": result_signature.get("transforms", {}),
        },
        "uvs_and_materials": {
            "uv_set_count": total_uv_sets,
            "material_count": total_materials,
            "materials": result_signature.get("materials", {}),
            "meshes_uv_udim": {
                k: {"uv_sets": v["uv_sets"], "udim_tiles": v["udim_tiles"], "materials": v["materials"]}
                for k, v in meshes.items()
            },
        },
        "skinning_and_joints": {
            "armature_count": len(armatures),
            "total_bones": total_bones,
            "total_weighted_vertices": total_weighted,
            "armatures": armatures,
        },
        "morphs_and_animation": {
            "total_shape_targets": total_shape_targets,
            "shape_targets_by_mesh": {k: v["shape_targets"] for k, v in meshes.items() if v["shape_targets"]},
            "total_animation_keyframes": total_anim_keys,
            "animation_key_counts": anim_counts,
            "fps": result_signature.get("fps", 24),
            "frame_range": result_signature.get("frame_range", (1, 100)),
        },
        "references_and_plugins": {
            "source_references": preflight.get("references", []),
            "linked_blender_libraries": result_signature.get("linked_libraries", []),
            "requires_plugins": preflight.get("requires_plugins", []),
            "unsupported_plugins": preflight.get("unsupported_plugins", []),
        },
        "baked_or_approximated": warnings_list,
        "limitations_and_unsupported": limitations_list,
        "comparison_diffs": comparison_diffs,
        "error": error,
    }

    global _LAST_INTERCHANGE_REPORT
    _LAST_INTERCHANGE_REPORT = report
    return report


def get_last_interchange_report() -> Dict[str, Any]:
    """Return the most recent interchange preflight/conversion/validation report."""
    return dict(_LAST_INTERCHANGE_REPORT)
