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


def ensure_mayapy_sitecustomize_env(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Ensure `PYTHONPATH` starts with a bootstrap `sitecustomize.py` that preloads `mayaLib0.dll` with `DONT_RESOLVE_DLL_REFERENCES` on Windows."""
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
            "import ctypes, os, sys\n"
            "try:\n"
            "    bin_dir = os.path.dirname(sys.executable)\n"
            "    lib0 = os.path.join(bin_dir, 'mayaLib0.dll')\n"
            "    if os.path.isfile(lib0):\n"
            "        if hasattr(os, 'add_dll_directory'):\n"
            "            os.add_dll_directory(bin_dir)\n"
            "        k32 = ctypes.WinDLL('kernel32', use_last_error=True)\n"
            "        k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint]\n"
            "        k32.LoadLibraryExW.restype = ctypes.c_void_p\n"
            "        k32.LoadLibraryExW(lib0, None, 0x0001)\n"
            "except Exception:\n"
            "    pass\n"
        )
        with open(sc_path, "w", encoding="utf-8") as f:
            f.write(sc_code)

    existing_pp = out_env.get("PYTHONPATH", "")
    parts = [p for p in existing_pp.split(os.pathsep) if p and os.path.normcase(p) != os.path.normcase(_MAYAPY_BOOTSTRAP_DIR)]
    out_env["PYTHONPATH"] = os.pathsep.join([_MAYAPY_BOOTSTRAP_DIR] + parts)
    return out_env


def _install_mayapy_env_hooks() -> None:
    """Wrap `MayaBridge._headless_env` and `MayaBridge._launch_env` in-memory so `MayaSceneImport` and `MayaBridge.save_as` inherit the `sitecustomize.py` bootstrap."""
    try:
        from blendertk.env_utils.maya_bridge._maya_bridge import MayaBridge

        if getattr(MayaBridge, "_lf_headless_hooked", False):
            return
        orig_headless = MayaBridge._headless_env
        orig_launch = MayaBridge._launch_env

        @staticmethod
        def _wrapped_headless_env():
            base = orig_headless()
            return ensure_mayapy_sitecustomize_env(base)

        @staticmethod
        def _wrapped_launch_env():
            base = orig_launch()
            return ensure_mayapy_sitecustomize_env(base)

        MayaBridge._headless_env = _wrapped_headless_env
        MayaBridge._launch_env = _wrapped_launch_env
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

    if clear_existing:
        for obj in list(bpy.data.objects):
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                pass

    importer = MayaSceneImport()
    imported_objs = []
    err_msg = None
    try:
        imported_objs = importer.import_scene(
            preflight["source_path"],
            via=via,
            rig_mode=rig_mode,
            use_cache=use_cache,
            timeout=timeout,
            include_animation=True,
        )
    except Exception as exc:
        err_msg = str(exc)

    sig = preflight_report.capture_blender_scene_signature(
        imported_objs if imported_objs else None
    )
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

    # Never overwrite protected original source file unless explicitly approved
    if protected_source_path and not allow_overwrite_source:
        src_abs = Path(os.path.abspath(os.path.expanduser(str(protected_source_path))))
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
        written_path = str(getattr(res, "artifact", None) or res or dst)
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

    res = bridge.send(objects=objs, template="import", mode="send_to", params=params)
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
