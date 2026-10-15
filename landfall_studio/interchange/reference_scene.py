"""Maya Reference Scene & Library Reference Manager (`landfall_studio.interchange.reference_scene`).

Wraps `blendertk.EnvUtils` (`list_libraries`, `link_blend_file`, `reload_library`, `remove_library`,
`make_library_local`, `set_reference_display_mode`, `get_reference_display_mode`) and
`blendertk.MayaSceneImport` (`bake_scene`):
- `reference_scene(src_path, display_mode="off")`:
  - Native `.blend` files are linked directly as Blender library references (`link_blend_file`).
  - Foreign `.ma` / `.mb` / `.fbx` / `.usd` files are baked non-destructively into a staged cache
    `.blend` (`bake_scene`) and linked as a live Blender library reference, leaving the source
    file untouched and never converting references into independent local objects without approval.
- `list_scene_references()`: Lists all active references (`library`, `filepath`, `exists`,
  `display_mode`, `object_count`, `foreign_source`).
- `set_reference_display_mode(library_or_path, mode)`: Sets `off` (Normal), `reference` (Shaded locked),
  or `template` (Wireframe locked).
- `reload_reference(library_or_path)` & `remove_reference(library_or_path)`.
- `unlink_and_import_reference(library_or_path, approved=False)`: Guarded `make_library_local` that
  refuses to flatten linked reference structures into independent local objects unless `approved=True`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import preflight_report

FOREIGN_REFERENCE_EXTENSIONS = (".ma", ".mb", ".fbx", ".usd", ".usda", ".usdc", ".usdz")


def _resolve_library_record(library_or_path: str) -> Optional[Dict[str, Any]]:
    from blendertk.env_utils._env_utils import EnvUtils

    target = str(library_or_path or "").strip()
    if not target:
        return None
    norm_target = os.path.normcase(os.path.abspath(target)) if os.path.isabs(target) or os.path.exists(target) else target.lower()

    for rec in EnvUtils.list_libraries():
        lib_name = rec["name"].lower()
        lib_abs = os.path.normcase(rec["abspath"]) if rec["abspath"] else ""
        if target.lower() == lib_name or norm_target == lib_abs or target in (rec["filepath"], rec["abspath"]):
            return rec
        # Also check if a foreign source path matches BAKE_INFO_TEXT
        foreign_src = _get_library_foreign_source(rec["library"])
        if foreign_src and os.path.normcase(os.path.abspath(foreign_src)) == norm_target:
            return rec
    return None


def _get_library_foreign_source(lib_block: Any) -> Optional[str]:
    """Read `.btk_bake_info` or custom property if this library was baked from a foreign `.ma`/`.mb`."""
    try:
        from blendertk.env_utils.maya_bridge._scene_import import MayaSceneImport

        ap = os.path.abspath(lib_block.filepath)
        info = MayaSceneImport.bake_info(ap)
        if info and info.get("btk_bake_source"):
            return str(info["btk_bake_source"])
    except Exception:
        pass
    try:
        src = lib_block.get("_lf_foreign_source")
        if src:
            return str(src)
    except Exception:
        pass
    return None


def list_scene_references() -> List[Dict[str, Any]]:
    """Return structured list of all active file references in the current Blender scene."""
    import bpy
    from blendertk.env_utils._env_utils import EnvUtils

    out: List[Dict[str, Any]] = []
    for rec in EnvUtils.list_libraries():
        lib = rec["library"]
        mode = EnvUtils.get_reference_display_mode(lib)
        obj_names = [
            o.name
            for o in bpy.data.objects
            if o.library == lib
            or (
                o.instance_type == "COLLECTION"
                and o.instance_collection is not None
                and o.instance_collection.library == lib
            )
        ]
        foreign = _get_library_foreign_source(lib)
        out.append(
            {
                "name": rec["name"],
                "filepath": rec["filepath"],
                "abspath": rec["abspath"],
                "exists": bool(rec["exists"]),
                "display_mode": mode,
                "object_count": len(obj_names),
                "objects": obj_names,
                "foreign_source": foreign,
            }
        )
    return out


def reference_scene(
    src_path: str,
    *,
    display_mode: str = "off",
    instance: bool = False,
) -> Dict[str, Any]:
    """Reference a `.blend` or foreign `.ma`/`.mb`/`.fbx`/`.usd` file into the active scene."""
    import bpy
    from blendertk.env_utils._env_utils import EnvUtils
    from blendertk.env_utils.maya_bridge._scene_import import MayaSceneImport

    p = Path(os.path.abspath(os.path.expanduser(str(src_path))))
    if not p.is_file():
        return {
            "ok": False,
            "status": "FAIL",
            "source_path": str(p),
            "error": f"Reference target file does not exist: {p}",
        }

    ext = p.suffix.lower()
    sha_before = preflight_report.compute_file_sha256(str(p))
    blend_to_link = str(p)
    foreign_source: Optional[str] = None

    if ext in FOREIGN_REFERENCE_EXTENSIONS:
        foreign_source = str(p)
        if ext in (".ma", ".mb"):
            runtime = preflight_report.get_maya_runtime_status()
            if not runtime.get("available"):
                return {
                    "ok": False,
                    "status": "BLOCKED",
                    "source_path": str(p),
                    "error": runtime.get("error", "mayapy not available to bake .ma/.mb reference"),
                }
        try:
            importer = MayaSceneImport(blender_path=bpy.app.binary_path)
            proj_root = EnvUtils.scene_project_root() or str(p.parent)
            baked_res = importer.bake_scene(str(p), use_cache=True, project=proj_root)
            blend_to_link = str(getattr(baked_res, "artifact", None) or baked_res)
        except Exception as exc:
            return {
                "ok": False,
                "status": "FAIL",
                "source_path": str(p),
                "error": f"Failed to bake foreign reference '{p.name}': {exc}",
            }

    count = EnvUtils.link_blend_file(
        blend_to_link,
        link=True,
        instance=instance,
        relative=False,
    )
    if count <= 0 and not EnvUtils.is_blend_linked(blend_to_link):
        return {
            "ok": False,
            "status": "FAIL",
            "source_path": str(p),
            "linked_blend": blend_to_link,
            "error": f"No collections or objects could be linked from {blend_to_link}",
        }

    rec = _resolve_library_record(blend_to_link)
    lib_name = rec["name"] if rec else os.path.basename(blend_to_link)
    if rec and foreign_source:
        try:
            rec["library"]["_lf_foreign_source"] = foreign_source
        except Exception:
            pass

    if display_mode in ("off", "reference", "template") and rec:
        EnvUtils.set_reference_display_mode(rec["library"], display_mode)

    sha_after = preflight_report.compute_file_sha256(str(p))
    return {
        "ok": True,
        "status": "PASS",
        "source_path": str(p),
        "linked_blend": blend_to_link,
        "library_name": lib_name,
        "linked_count": count,
        "display_mode": display_mode,
        "source_unchanged": bool(sha_before and sha_before == sha_after),
    }


def set_reference_mode(library_or_path: str, mode: str = "reference") -> Dict[str, Any]:
    """Set display mode (`off` / `reference` / `template`) on a linked reference library."""
    from blendertk.env_utils._env_utils import EnvUtils

    rec = _resolve_library_record(library_or_path)
    if rec is None:
        return {"ok": False, "error": f"Reference '{library_or_path}' not found in scene."}
    norm_mode = (mode or "off").lower()
    if norm_mode == "normal":
        norm_mode = "off"
    if norm_mode not in ("off", "reference", "template"):
        return {"ok": False, "error": f"Invalid reference display mode '{mode}'."}

    updated = EnvUtils.set_reference_display_mode(rec["library"], norm_mode)
    return {
        "ok": True,
        "library_name": rec["name"],
        "display_mode": EnvUtils.get_reference_display_mode(rec["library"]),
        "updated": bool(updated),
    }


def reload_reference_scene(library_or_path: str) -> Dict[str, Any]:
    """Reload a linked reference library from disk."""
    from blendertk.env_utils._env_utils import EnvUtils

    rec = _resolve_library_record(library_or_path)
    if rec is None:
        return {"ok": False, "error": f"Reference '{library_or_path}' not found in scene."}
    if not rec.get("exists"):
        return {
            "ok": False,
            "missing_target": True,
            "error": f"Reference target file is missing on disk: {rec.get('abspath')}",
        }
    ok = EnvUtils.reload_library(rec["library"])
    return {"ok": bool(ok), "library_name": rec["name"], "filepath": rec["abspath"]}


def remove_reference_scene(library_or_path: str) -> Dict[str, Any]:
    """Un-reference (unlink and remove) a linked reference library from the scene."""
    from blendertk.env_utils._env_utils import EnvUtils

    rec = _resolve_library_record(library_or_path)
    if rec is None:
        return {"ok": False, "error": f"Reference '{library_or_path}' not found in scene."}
    name = rec["name"]
    ok = EnvUtils.remove_library(rec["library"])
    return {"ok": bool(ok), "removed_library": name}


def unlink_and_import_reference(
    library_or_path: str,
    *,
    approved: bool = False,
    scene_data: str = "merge",
) -> Dict[str, Any]:
    """Convert a linked reference into independent local datablocks ONLY when `approved=True`."""
    from blendertk.env_utils._env_utils import EnvUtils

    if not approved:
        return {
            "ok": False,
            "guarded": True,
            "error": (
                "Converting a linked reference into independent local objects requires explicit approval "
                "(pass approved=True)."
            ),
        }

    rec = _resolve_library_record(library_or_path)
    if rec is None:
        return {"ok": False, "error": f"Reference '{library_or_path}' not found in scene."}

    name = rec["name"]
    localized_count = EnvUtils.make_library_local(rec["library"], scene_data=scene_data)
    return {
        "ok": localized_count > 0,
        "library_name": name,
        "localized_datablock_count": int(localized_count),
    }
