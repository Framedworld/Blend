"""Maya `.ma`/`.mb` Scene Interchange Engine (`landfall_studio.interchange.maya_bridge`).

Wraps upstream `blendertk.MayaBridge` (`_maya_bridge.py`) and `blendertk.MayaSceneImport` (`_scene_import.py`)
with local `mayapy.exe` execution, staged conversion, non-destructive source-preservation guarantees,
and the Mandatory Interchange Report required by `docs/INTERCHANGE_CONTRACT.md`:
- `import_maya_scene(src_path, ...)`: Converts `.ma`/`.mb` via headless `mayapy`, imports into Blender,
  verifies `sha256(src_path)` is unchanged, and records the full loss/fidelity report.
- `save_as_maya_scene(dst_path, ...)`: Exports Blender selection or whole scene to native `.ma` or `.mb`
  via `MayaBridge.save_as` and headless `mayapy`, guarded against overwriting original source files.
- `send_to_maya(scope="SELECTED", dry_run=False, ...)`: Hands off to interactive Maya (`MayaBridge.send`)
  or stages and validates the hand-off payload in `dry_run` mode.
- `generate_maya_fixture_ma(out_ma_path)`: Uses local `mayapy.exe` to author a real Maya 2024 `.ma`
  fixture with hierarchy, skinned mesh (`skinCluster`), morphs (`blendShape`), materials/UVs,
  keyframes, and a custom Maya DG `expression` node for round-trip & loss-report verification.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import preflight_report

_MAYAPY_BOOTSTRAP_DIR: Optional[str] = None
_last_imported_source_path: Optional[str] = None


def _bridge_result_error(result: Any, operation: str) -> Optional[str]:
    """Reject upstream's handled failures before inspecting an existing artifact.

    Both MayaBridge operations return a nonempty result dict on success and
    ``None`` on handled failures. The save deliverer judges the produced artifact,
    so its diagnostic return code alone is not a reliable success criterion.
    """
    if not isinstance(result, dict) or not result:
        return f"MayaBridge.{operation} did not complete successfully; see Script Output for details."
    if result.get("ok") is False or result.get("success") is False or result.get("error"):
        return str(result.get("error") or f"MayaBridge.{operation} reported a failure.")
    if str(result.get("status", "")).upper() in {"FAIL", "FAILED", "ERROR", "BLOCKED", "CANCELLED"}:
        return f"MayaBridge.{operation} reported {result['status']}."
    return None


def ensure_mayapy_sitecustomize_env(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Ensure headless `mayapy` has Maya's `bin` directory registered on the DLL search path while chaining any studio `sitecustomize.py`."""
    global _MAYAPY_BOOTSTRAP_DIR
    import tempfile

    out_env = dict(env if env is not None else os.environ)
    if os.name != "nt":
        return out_env

    if _MAYAPY_BOOTSTRAP_DIR is None or not os.path.isdir(_MAYAPY_BOOTSTRAP_DIR):
        _MAYAPY_BOOTSTRAP_DIR = os.path.join(tempfile.gettempdir(), "lf_mayapy_bootstrap")
        os.makedirs(_MAYAPY_BOOTSTRAP_DIR, exist_ok=True)
        sc_path = os.path.join(_MAYAPY_BOOTSTRAP_DIR, "sitecustomize.py")
        sc_code = (
            "import ctypes, os, runpy, sys\n"
            "_this_dir = os.path.normcase(os.path.abspath(os.path.dirname(__file__)))\n"
            "try:\n"
            "    bin_dir = os.path.dirname(sys.executable)\n"
            "    if os.path.isdir(bin_dir):\n"
            "        if hasattr(os, 'add_dll_directory'):\n"
            "            os.add_dll_directory(bin_dir)\n"
            "        os.environ['PATH'] = bin_dir + os.pathsep + os.environ.get('PATH', '')\n"
            "    lib0 = os.path.join(bin_dir, 'mayaLib0.dll')\n"
            "    if os.path.isfile(lib0):\n"
            "        k32 = ctypes.WinDLL('kernel32', use_last_error=True)\n"
            "        k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint]\n"
            "        k32.LoadLibraryExW.restype = ctypes.c_void_p\n"
            "        # Use LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS (0x00001100), fallback to 0\n"
            "        h = k32.LoadLibraryExW(lib0, None, 0x00001100)\n"
            "        if not h:\n"
            "            k32.LoadLibraryExW(lib0, None, 0x0001)\n"
            "except Exception:\n"
            "    pass\n"
            "# Chain-load any downstream studio sitecustomize.py on sys.path so studio setups are never shadowed\n"
            "for _p in list(sys.path):\n"
            "    if not _p:\n"
            "        continue\n"
            "    try:\n"
            "        if os.path.normcase(os.path.abspath(_p)) == _this_dir:\n"
            "            continue\n"
            "        _cand = os.path.join(_p, 'sitecustomize.py')\n"
            "        if os.path.isfile(_cand):\n"
            "            runpy.run_path(_cand, init_globals=globals())\n"
            "            break\n"
            "    except Exception:\n"
            "        pass\n"
        )
        with open(sc_path, "w", encoding="utf-8") as f:
            f.write(sc_code)

    existing_pp = out_env.get("PYTHONPATH", "")
    parts = [p for p in existing_pp.split(os.pathsep) if p and os.path.normcase(p) != os.path.normcase(_MAYAPY_BOOTSTRAP_DIR)]
    out_env["PYTHONPATH"] = os.pathsep.join([_MAYAPY_BOOTSTRAP_DIR] + parts)
    return out_env


def _install_mayapy_env_hooks() -> None:
    """Wrap `MayaBridge._headless_env` in-memory for headless `mayapy` without overriding interactive Maya's `_launch_env`."""
    try:
        from blendertk.env_utils.maya_bridge._maya_bridge import MayaBridge

        if getattr(MayaBridge, "_lf_headless_hooked", False):
            return
        orig_headless = MayaBridge._headless_env

        @staticmethod
        def _wrapped_headless_env():
            base = orig_headless()
            return ensure_mayapy_sitecustomize_env(base)

        MayaBridge._headless_env = _wrapped_headless_env
        MayaBridge._lf_headless_hooked = True
    except Exception:
        pass


_install_mayapy_env_hooks()


def generate_maya_fixture_ma(out_ma_path: str, timeout: float = 120.0) -> Dict[str, Any]:
    """Use local `mayapy.exe` to generate a real Maya `.ma` fixture with hierarchy, skinning, morphs, materials, UVs, animation, and a custom DG expression."""
    _install_mayapy_env_hooks()
    runtime = preflight_report.get_maya_runtime_status()
    if not runtime.get("available"):
        return {
            "ok": False,
            "status": "BLOCKED",
            "error": runtime.get("error", "mayapy not available"),
        }

    mayapy = runtime["mayapy_exe"]
    dst = Path(os.path.abspath(os.path.expanduser(str(out_ma_path))))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst_posix = str(dst).replace("\\", "/")

    script = f"""
import os
import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds

cmds.file(new=True, force=True)
cmds.currentUnit(time="film")
cmds.playbackOptions(minTime=1, maxTime=24, animationStartTime=1, animationEndTime=24)

# 1. Hierarchy Groups
env_grp = cmds.group(empty=True, name="environment_GRP")
char_grp = cmds.group(empty=True, name="heroChar_GRP")
rig_grp = cmds.group(empty=True, name="controls_RIG", parent=char_grp)

# 2. Mesh with UVs
body_mesh, body_poly = cmds.polyCube(name="body_main_GEO", width=2.0, height=3.0, depth=1.5, sx=2, sy=3, sz=2)
cmds.delete(body_mesh, constructionHistory=True)
cmds.parent(body_mesh, char_grp)

# 3. BlendShape targets (Smile & BrowUp) BEFORE skinning so history order is standard
smile_dup = cmds.duplicate(body_mesh, name="Smile")[0]
cmds.move(0.35, 0.25, 0.15, smile_dup + ".vtx[0:5]", relative=True)
brow_dup = cmds.duplicate(body_mesh, name="BrowUp")[0]
cmds.move(0.0, 0.45, 0.0, brow_dup + ".vtx[6:11]", relative=True)

bs = cmds.blendShape(smile_dup, brow_dup, body_mesh, name="heroMorph_BS")[0]
cmds.delete(smile_dup, brow_dup)

# Keyframe BlendShape target weight
cmds.setKeyframe(bs + ".Smile", time=1, value=0.0)
cmds.setKeyframe(bs + ".Smile", time=12, value=0.85)
cmds.setKeyframe(bs + ".Smile", time=24, value=0.25)
cmds.setAttr(bs + ".BrowUp", 0.4)

# 4. Joint Hierarchy & SkinCluster
cmds.select(clear=True)
root_jnt = cmds.joint(name="root_JNT", position=(0.0, -1.0, 0.0))
spine_jnt = cmds.joint(name="spine_JNT", position=(0.0, 0.5, 0.0))
head_jnt = cmds.joint(name="head_JNT", position=(0.0, 1.5, 0.0))
cmds.parent(root_jnt, rig_grp)

skin = cmds.skinCluster(root_jnt, spine_jnt, head_jnt, body_mesh, name="body_skinCluster", toSelectedBones=True)[0]

# Keyframe Joint Animation
cmds.setKeyframe(root_jnt + ".translateY", time=1, value=-1.0)
cmds.setKeyframe(root_jnt + ".translateY", time=12, value=-0.5)
cmds.setKeyframe(root_jnt + ".translateY", time=24, value=-1.0)
cmds.setKeyframe(spine_jnt + ".rotateZ", time=1, value=0.0)
cmds.setKeyframe(spine_jnt + ".rotateZ", time=12, value=18.0)
cmds.setKeyframe(spine_jnt + ".rotateZ", time=24, value=0.0)

# 5. Material & Shading Group
shd = cmds.shadingNode("phong", asShader=True, name="heroBody_MAT")
cmds.setAttr(shd + ".color", 0.22, 0.64, 0.85, type="double3")
sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="heroBody_MATSG")
cmds.connectAttr(shd + ".outColor", sg + ".surfaceShader", force=True)
cmds.sets(body_mesh, edit=True, forceElement=sg)

# 6. Custom Maya DG Expression + multMatrix node (to exercise loss-report preflight detection)
mm = cmds.createNode("multMatrix", name="customRig_MMX")
cmds.expression(name="customDriver_EXP", string="environment_GRP.rotateY = frame * 1.5;", alwaysEvaluate=False)

cmds.file(rename="{dst_posix}")
cmds.file(save=True, type="mayaAscii", force=True)
os._exit(0)
"""
    from blendertk.env_utils.maya_bridge._maya_bridge import MayaBridge

    env = ensure_mayapy_sitecustomize_env(MayaBridge._headless_env())

    proc = subprocess.run(
        [mayapy, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if not dst.is_file() or dst.stat().st_size == 0:
        return {
            "ok": False,
            "status": "FAIL",
            "error": (
                f"Failed to generate Maya fixture at {dst} (rc={proc.returncode}): "
                f"{proc.stderr or proc.stdout}"
            ),
        }

    pf = preflight_report.preflight_maya_scene(str(dst))
    return {
        "ok": True,
        "status": "PASS",
        "fixture_path": str(dst),
        "size_bytes": pf.get("size_bytes", 0),
        "sha256": pf["source_sha256"],
        "preflight": pf,
    }


def _native_ascii_import(preflight: Dict[str, Any], src_path: str, clear_existing: bool,
                         reason: str) -> Dict[str, Any]:
    """Import a .ma through the native reader when no Maya runtime can convert it."""
    import bpy
    from . import maya_ascii

    originals = list(bpy.context.scene.objects) if clear_existing else []
    result = maya_ascii.import_maya_ascii(src_path)
    error = None if result.get("ok") else result.get("error", "Native Maya ASCII import failed.")
    imported = [bpy.data.objects[n] for n in result.get("objects", []) if n in bpy.data.objects]
    if not error and clear_existing:
        for obj in originals:
            # Objects also used by another scene are kept, as on the mayapy route.
            if obj not in imported and all(sc == bpy.context.scene for sc in obj.users_scene):
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except ReferenceError:
                    pass
    global _last_imported_source_path
    if not error:
        _last_imported_source_path = str(src_path)
    sig = preflight_report.capture_blender_scene_signature(imported)
    report = preflight_report.build_interchange_report(
        operation="IMPORT_MAYA_SCENE",
        source_path=str(src_path),
        destination_path="<blender_scene>",
        preflight=preflight,
        result_signature=sig,
        options={"route": "native_ascii", "reason": reason},
        error=error,
    )
    report["imported_objects"] = [o.name for o in imported]
    report["route"] = "native_ascii"
    report["skipped"] = result.get("skipped", [])
    report["route_note"] = (
        "Imported with Studio's native Maya ASCII reader (geometry, hierarchy, UVs, hard edges). "
        + reason)
    return report


def import_maya_scene(
    src_path: str,
    *,
    via: str = "fbx",
    rig_mode: str = "auto",
    use_cache: bool = False,
    clear_existing: bool = False,
    timeout: Optional[float] = 180.0,
) -> Dict[str, Any]:
    """Import a `.ma` or `.mb` Maya scene via `blendertk.MayaSceneImport` and local `mayapy.exe`."""
    import bpy
    from blendertk.env_utils.maya_bridge._scene_import import MayaSceneImport

    preflight = preflight_report.preflight_maya_scene(src_path)
    if not preflight.get("ok"):
        rep = preflight_report.build_interchange_report(
            operation="IMPORT_MAYA_SCENE",
            source_path=str(src_path),
            destination_path="<blender_scene>",
            preflight=preflight,
            result_signature={},
            options={"via": via, "rig_mode": rig_mode},
            error=preflight.get("error", "Preflight failed"),
        )
        return rep

    is_ascii = str(preflight.get("source_path", src_path)).lower().endswith(".ma")
    if preflight.get("status") == "BLOCKED" and is_ascii:
        return _native_ascii_import(preflight, preflight.get("source_path", src_path), clear_existing,
                                    "No working Maya runtime was available.")
    if preflight.get("status") == "BLOCKED":
        rep = preflight_report.build_interchange_report(
            operation="IMPORT_MAYA_SCENE",
            source_path=preflight["source_path"],
            destination_path="<blender_scene>",
            preflight=preflight,
            result_signature={},
            options={"via": via, "rig_mode": rig_mode},
            error=preflight["runtime"].get("error", "Maya not installed"),
        )
        return rep

    # Conversion/import can fail even when mayapy was discovered. Keep the
    # artist's existing scene until the importer has returned a valid result.
    original_objs = list(bpy.context.scene.objects) if clear_existing else []
    shared_originals = [
        obj.name for obj in original_objs
        if any(scene != bpy.context.scene for scene in getattr(obj, "users_scene", ()))
    ]
    if shared_originals:
        report = preflight_report.build_interchange_report(
            operation="IMPORT_MAYA_SCENE",
            source_path=preflight["source_path"],
            destination_path="<blender_scene>",
            preflight=preflight,
            result_signature={},
            options={"via": via, "rig_mode": rig_mode, "clear_existing": True},
            error=(
                "Cannot clear the scene because these objects also belong to another scene: "
                + ", ".join(shared_originals)
                + ". Import without Clear Scene First or make the objects independent first."
            ),
        )
        report["imported_objects"] = []
        return report
    importer = MayaSceneImport()
    imported_objs = []
    import_completed = False
    err_msg = None
    try:
        imported = importer.import_scene(
            preflight["source_path"],
            via=via,
            rig_mode=rig_mode,
            use_cache=use_cache,
            timeout=timeout,
            include_animation=True,
            scene_settings=True if clear_existing else "auto",
        )
        if imported is None:
            raise RuntimeError("MayaSceneImport.import_scene did not return a completed import result.")
        imported_objs = list(imported)
        summary = preflight.get("summary", {})
        if not imported_objs and any(summary.get(key, 0) for key in ("transforms", "meshes", "joints")):
            raise RuntimeError("Maya scene contains objects, but the import created no objects; existing scene preserved.")
        import_completed = True
    except Exception as exc:
        err_msg = str(exc)

    if import_completed and clear_existing:
        cleanup_errors = []
        for obj in original_objs:
            if obj in imported_objs:
                continue
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except ReferenceError:
                continue
            except Exception as exc:
                cleanup_errors.append(str(exc))
        if cleanup_errors:
            err_msg = "Import completed, but clearing original objects failed: " + "; ".join(cleanup_errors)

    global _last_imported_source_path
    if import_completed:
        _last_imported_source_path = str(preflight["source_path"])

    sig = preflight_report.capture_blender_scene_signature(imported_objs)
    report = preflight_report.build_interchange_report(
        operation="IMPORT_MAYA_SCENE",
        source_path=preflight["source_path"],
        destination_path="<blender_scene>",
        preflight=preflight,
        result_signature=sig,
        options={"via": via, "rig_mode": rig_mode, "use_cache": use_cache},
        error=err_msg,
    )
    report["imported_objects"] = [getattr(o, "name", str(o)) for o in (imported_objs or [])]
    if not import_completed and is_ascii:
        # A detected Maya failed: report it as-is, and point at the native route.
        report["hint"] = "File > Import > Maya ASCII (native) reads .ma geometry without a Maya runtime."
    return report


def _native_ascii_save(dst: Path, scope: str, reason: str) -> Dict[str, Any]:
    """Write a .ma with Studio's native writer when no Maya runtime can convert."""
    import bpy
    from . import maya_ascii

    if (scope or "ALL").upper() == "SELECTED" and getattr(bpy.context, "selected_objects", None):
        objects = list(bpy.context.selected_objects)
    else:
        objects = list(bpy.context.scene.objects)
    result = maya_ascii.export_maya_ascii(str(dst), objects)
    written = preflight_report.preflight_maya_scene(str(dst))
    report = preflight_report.build_interchange_report(
        operation="SAVE_AS_MAYA_SCENE",
        source_path=str(dst),
        destination_path=str(dst),
        preflight=written,
        result_signature=preflight_report.capture_blender_scene_signature(objects),
        options={"route": "native_ascii", "reason": reason},
        error=None if result.get("ok") else result.get("error"),
    )
    report["written_path"] = str(dst)
    report["route"] = "native_ascii"
    report["route_note"] = ("Saved with Studio's native Maya ASCII writer (geometry, hierarchy, UVs, "
                            "hard edges; no shaders, skinning or animation). " + reason)
    return report


def save_as_maya_scene(
    dst_path: str,
    *,
    scope: str = "ALL",
    carrier: str = "fbx",
    shader_type: str = "stingray",
    include_animation: bool = True,
    protected_source_path: Optional[str] = None,
    allow_overwrite_source: bool = False,
) -> Dict[str, Any]:
    """Save the current Blender scene (or selection) as a native `.ma` or `.mb` file via `blendertk.MayaBridge.save_as`."""
    import bpy
    from blendertk.env_utils.maya_bridge._maya_bridge import MayaBridge

    dst = Path(os.path.abspath(os.path.expanduser(str(dst_path))))
    if dst.suffix.lower() not in (".ma", ".mb"):
        dst = dst.with_suffix(".ma")

    effective_protected = protected_source_path or _last_imported_source_path
    # Never overwrite protected original source file unless explicitly approved
    if effective_protected and not allow_overwrite_source:
        src_abs = Path(os.path.abspath(os.path.expanduser(str(effective_protected))))
        if dst.resolve() == src_abs.resolve():
            return {
                "ok": False,
                "status": "FAIL",
                "operation": "SAVE_AS_MAYA_SCENE",
                "destination_path": str(dst),
                "error": (
                    f"Refusing to overwrite original source Maya scene '{src_abs}'. "
                    "Choose a staged/new destination path or pass allow_overwrite_source=True."
                ),
            }

    runtime = preflight_report.get_maya_runtime_status()
    if not runtime.get("available") and dst.suffix.lower() == ".ma":
        return _native_ascii_save(dst, scope, "No working Maya runtime was available.")
    if not runtime.get("available"):
        return {
            "ok": False,
            "status": "BLOCKED",
            "operation": "SAVE_AS_MAYA_SCENE",
            "destination_path": str(dst),
            "error": runtime.get("error", "mayapy not available"),
        }

    dst.parent.mkdir(parents=True, exist_ok=True)
    scope_upper = (scope or "ALL").upper()
    if scope_upper == "SELECTED":
        export_objs = list(getattr(bpy.context, "selected_objects", ()))
        if not export_objs:
            export_objs = list(bpy.context.scene.objects)
    else:
        export_objs = list(bpy.context.scene.objects)

    before_sig = preflight_report.capture_blender_scene_signature(export_objs)

    bridge = MayaBridge()
    params = {
        "SCOPE": "selected" if scope_upper == "SELECTED" else "scene",
        "CARRIER": carrier,
        "INCLUDE_MATERIALS": True,
        "INCLUDE_SCENE_DATA": True,
        "SHADER_TYPE": shader_type,
        "EMBED_TEXTURES": True,
        "APPLY_UNIT_SCALE": True,
        "INCLUDE_ANIMATION": bool(include_animation),
        "TRIANGULATE": False,
    }

    written_path = None
    err_msg = None
    try:
        res = bridge.save_as(str(dst), objects=export_objs, params=params)
        err_msg = _bridge_result_error(res, "save_as")
        if err_msg is None:
            written_path = str(res.get("output") or "")
            if not written_path:
                err_msg = "MayaBridge.save_as did not return the output artifact for this conversion."
            elif Path(written_path).resolve() != dst.resolve():
                err_msg = f"MayaBridge.save_as returned an unexpected output path: {written_path}"
    except Exception as exc:
        err_msg = str(exc)

    if err_msg or not dst.is_file() or dst.stat().st_size == 0:
        return {
            "ok": False,
            "status": "FAIL",
            "operation": "SAVE_AS_MAYA_SCENE",
            "destination_path": str(dst),
            "error": err_msg or f"MayaBridge.save_as did not produce a valid file at {dst}",
        }

    # Verify the written .ma/.mb file contains real Maya scene nodes (never conflate bare file write with conversion)
    written_pf = preflight_report.preflight_maya_scene(str(dst))
    has_geometry_or_transforms = (
        written_pf.get("summary", {}).get("meshes", 0) > 0
        or written_pf.get("summary", {}).get("transforms", 0) > 0
    )
    if not has_geometry_or_transforms and export_objs:
        return {
            "ok": False,
            "status": "FAIL",
            "operation": "SAVE_AS_MAYA_SCENE",
            "destination_path": str(dst),
            "written_preflight": written_pf,
            "error": "Saved .ma/.mb file contains no Maya mesh or transform nodes.",
        }

    report = preflight_report.build_interchange_report(
        operation="SAVE_AS_MAYA_SCENE",
        source_path=str(dst),
        destination_path=str(dst),
        preflight=written_pf,
        result_signature=before_sig,
        options=params,
    )
    report["written_path"] = str(written_path or dst)
    report["written_preflight"] = written_pf
    return report


def send_to_maya(
    *,
    scope: str = "SELECTED",
    carrier: str = "fbx",
    shader_type: str = "stingray",
    include_animation: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Send selected objects (or whole scene) to Maya via `blendertk.MayaBridge`."""
    import bpy
    from blendertk.env_utils.maya_bridge._maya_bridge import MayaBridge

    runtime = preflight_report.get_maya_runtime_status()
    if not runtime.get("available"):
        return {
            "ok": False,
            "status": "BLOCKED",
            "operation": "SEND_TO_MAYA",
            "error": runtime.get("error", "Maya executable not found"),
        }

    scope_upper = (scope or "SELECTED").upper()
    if scope_upper == "SELECTED":
        objs = list(getattr(bpy.context, "selected_objects", ()))
        if not objs:
            objs = list(bpy.context.scene.objects)
    else:
        objs = list(bpy.context.scene.objects)

    bridge = MayaBridge()
    params = {
        "SCOPE": "selected" if scope_upper == "SELECTED" else "scene",
        "CARRIER": carrier,
        "INCLUDE_MATERIALS": True,
        "INCLUDE_SCENE_DATA": True,
        "SHADER_TYPE": shader_type,
        "EMBED_TEXTURES": True,
        "APPLY_UNIT_SCALE": True,
        "INCLUDE_ANIMATION": bool(include_animation),
        "CLEAR_SCENE": False,
        "FRAME_VIEW": True,
    }

    if dry_run:
        # Stage the rendered import template and verify object closure without spawning a GUI Maya window
        closure = bridge._hierarchy_closure(objs, descend=True)
        ctx = bridge.render_context(params)
        return {
            "ok": True,
            "status": "STAGED_DRY_RUN",
            "operation": "SEND_TO_MAYA",
            "maya_exe": bridge.maya_path,
            "object_count": len(closure),
            "objects": [o.name for o in closure],
            "render_context_keys": sorted(ctx.keys()),
        }

    try:
        res = bridge.send(objects=objs, template="import", mode="send_to", params=params)
        err_msg = _bridge_result_error(res, "send")
    except Exception as exc:
        res = None
        err_msg = str(exc)
    if err_msg:
        return {
            "ok": False,
            "status": "FAIL",
            "operation": "SEND_TO_MAYA",
            "maya_exe": bridge.maya_path,
            "object_count": len(objs),
            "error": err_msg,
        }
    return {
        "ok": True,
        "status": "SENT",
        "operation": "SEND_TO_MAYA",
        "maya_exe": bridge.maya_path,
        "object_count": len(objs),
        "result": str(res),
    }


def validate_interchange_roundtrip(
    src_ma_path: str,
    roundtrip_ma_path: str,
    *,
    via: str = "fbx",
) -> Dict[str, Any]:
    """Execute and validate a full `.ma -> Blender -> Save As .ma -> Re-Import` round-trip."""
    src_pf_before = preflight_report.preflight_maya_scene(src_ma_path)
    if not src_pf_before.get("ok"):
        return src_pf_before
    if src_pf_before.get("status") == "BLOCKED":
        return preflight_report.build_interchange_report(
            operation="VALIDATE_ROUNDTRIP",
            source_path=src_ma_path,
            destination_path=roundtrip_ma_path,
            preflight=src_pf_before,
            result_signature={},
            error=src_pf_before["runtime"].get("error"),
        )

    sha_initial = src_pf_before["source_sha256"]

    # Step 1: Import original .ma into clean Blender scene
    imp1 = import_maya_scene(src_ma_path, via=via, clear_existing=True, use_cache=False)
    if not imp1.get("ok"):
        return imp1
    sig_after_import1 = preflight_report.capture_blender_scene_signature()

    # Step 2: Save As a staged second .ma file (protecting src_ma_path)
    save_res = save_as_maya_scene(
        roundtrip_ma_path,
        scope="ALL",
        carrier=via,
        include_animation=True,
        protected_source_path=src_ma_path,
    )
    if not save_res.get("ok"):
        return save_res

    # Step 3: Re-import the saved round-trip .ma into a clean Blender scene to verify round-trip fidelity
    imp2 = import_maya_scene(roundtrip_ma_path, via=via, clear_existing=True, use_cache=False)
    sig_after_import2 = preflight_report.capture_blender_scene_signature()

    # Verify original source .ma was never modified at any point
    sha_final = preflight_report.compute_file_sha256(src_ma_path)
    source_unchanged = bool(sha_initial and sha_initial == sha_final)

    final_report = preflight_report.build_interchange_report(
        operation="VALIDATE_ROUNDTRIP",
        source_path=src_ma_path,
        destination_path=roundtrip_ma_path,
        preflight=src_pf_before,
        result_signature=sig_after_import1,
        baseline_signature=sig_after_import2,
        options={"via": via},
    )
    final_report["source_unchanged"] = source_unchanged
    final_report["import_1_signature"] = sig_after_import1
    final_report["import_2_signature"] = sig_after_import2
    final_report["saved_ma_preflight"] = save_res.get("written_preflight", {})
    return final_report
