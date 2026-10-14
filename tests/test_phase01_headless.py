"""Phase 01 Headless Verification Suite for Landfall Studio.

Modes:
- `--mode=no-deps`: Simulates a clean Blender environment without PySide6/qtpy/Pillow,
  verifying zero unsolicited `pip install` calls, graceful degraded startup, working
  Landfall core operators, and clean teardown.
- `--mode=full`: Verifies full-stack bootstrap (Landfall + Tentacle + blendertk + Qt),
  pinned SHA lock matching, blendertk primitive creation & transform commands, Landfall
  smooth preview operator, workspace root sync, and double enable/disable lifecycle
  cleanup with zero leaked timers, handlers, or keymaps.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("no-deps", "full"), default="full")
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def _count_addon_keymaps() -> int:
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return 0
    return sum(len(km.keymap_items) for km in kc.keymaps)


def _snapshot_handlers() -> dict:
    return {
        "depsgraph_update_post": list(bpy.app.handlers.depsgraph_update_post),
        "load_post": list(bpy.app.handlers.load_post),
        "undo_post": list(bpy.app.handlers.undo_post),
        "redo_post": list(bpy.app.handlers.redo_post),
    }


def run_no_deps_test() -> dict:
    """Verify clean degraded startup when Qt dependencies are absent (Conflict C-01)."""
    with tempfile.TemporaryDirectory(prefix="lf_studio_empty_deps_") as empty_deps:
        os.environ["LANDFALL_STUDIO_DEPS"] = empty_deps
        os.environ["TENTACLE_QT_DEPS"] = empty_deps

        # Guard subprocess.run to prove zero unsolicited pip/ensurepip calls happen during register()
        pip_calls = []
        orig_run = subprocess.run

        def _guarded_run(cmd, *args, **kwargs):
            cmd_str = " ".join(str(x) for x in cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
            if "pip" in cmd_str or "ensurepip" in cmd_str:
                pip_calls.append(cmd_str)
                raise AssertionError(f"Forbidden unsolicited pip invocation during startup: {cmd_str}")
            return orig_run(cmd, *args, **kwargs)

        # Hide PySide6/qtpy if somehow on sys.path
        import importlib.util

        orig_find_spec = importlib.util.find_spec

        def _masked_find_spec(name, package=None):
            if name in ("PySide6", "qtpy", "PIL"):
                return None
            return orig_find_spec(name, package=package)

        subprocess.run = _guarded_run
        importlib.util.find_spec = _masked_find_spec
        try:
            import landfall_studio
            from landfall_studio import diagnostics
            from landfall_studio.adapters import landfall_bridge

            baseline_handlers = _snapshot_handlers()
            baseline_km_count = _count_addon_keymaps()

            landfall_studio.register()
            rep = diagnostics.get_report(custom_deps_dir=empty_deps)

            assert len(pip_calls) == 0, f"Unexpected pip calls: {pip_calls}"
            assert rep["qt_available"] is False, "Expected qt_available=False in no-deps mode"
            assert rep["subsystems"]["landfall_registered"] is True, "Landfall should still register"
            assert rep["subsystems"]["tentacle_state"] == "DEGRADED_MISSING_DEPS"
            assert "tentacle.tcl_blender" not in sys.modules, "tentacle.tcl_blender must not be imported when Qt is missing"

            # Verify a Landfall operator works in degraded mode
            bpy.ops.mesh.primitive_cube_add(size=2.0)
            res = bpy.ops.landfall.smooth_preview(mode="SMOOTH")
            assert "FINISHED" in res, f"landfall.smooth_preview failed: {res}"

            # Unregister and verify clean restoration
            landfall_studio.unregister()
            after_handlers = _snapshot_handlers()
            after_km_count = _count_addon_keymaps()

            for k in baseline_handlers:
                assert len(after_handlers[k]) == len(baseline_handlers[k]), (
                    f"Handler leak in {k}: before={len(baseline_handlers[k])}, after={len(after_handlers[k])}"
                )
            assert after_km_count == baseline_km_count, (
                f"Keymap leak: before={baseline_km_count}, after={after_km_count}"
            )

            lf_mod = landfall_bridge.get_module()
            for fn_name in ("_gizmos_sync", "_keymap_heal", "_deferred_sync"):
                fn = getattr(lf_mod, fn_name, None)
                assert not bpy.app.timers.is_registered(fn), f"Timer {fn_name} still registered!"

            return {
                "mode": "no-deps",
                "status": "PASS",
                "pip_calls_during_register": len(pip_calls),
                "qt_available": rep["qt_available"],
                "landfall_registered": True,
                "tentacle_state": rep["subsystems"]["tentacle_state"],
                "handlers_clean_after_unregister": True,
                "keymaps_clean_after_unregister": True,
            }
        finally:
            subprocess.run = orig_run
            importlib.util.find_spec = orig_find_spec


def run_full_stack_test() -> dict:
    """Verify full-stack headless integration (Landfall + Tentacle + blendertk + workspace sync + lifecycle)."""
    import landfall_studio
    from landfall_studio import diagnostics
    from landfall_studio.adapters import (
        blendertk_bridge,
        landfall_bridge,
        tentacle_bridge,
        workspace_bridge,
    )

    baseline_handlers = _snapshot_handlers()
    baseline_km_count = _count_addon_keymaps()
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr

    # Cycle 1: Register
    landfall_studio.register()
    rep = diagnostics.get_report()

    assert rep["qt_available"] is True, f"Expected Qt available, got: {rep['dependencies']['packages']}"
    assert rep["full_stack_ready"] is True, f"Expected full_stack_ready=True, got: {rep}"
    assert rep["subsystems"]["landfall_registered"] is True
    assert rep["subsystems"]["tentacle_state"] == "ACTIVE"
    assert rep["subsystems"]["tentacle_instance_active"] is True

    # Verify all 5 upstream repos match pinned SHAs
    for repo_name, repo_info in rep["dependencies"]["upstream"].items():
        assert repo_info["importable"] is True, f"Upstream {repo_name} not importable"
        assert repo_info["sha_matches"] is True, (
            f"SHA mismatch for {repo_name}: got {repo_info['git_sha']}, expected {repo_info['pinned_sha']}"
        )

    # Execute a real blendertk command via the registered operator
    op_res = bpy.ops.landfall_studio.btk_create_primitive(primitive_type="CUBE", size=2.0)
    assert "FINISHED" in op_res, f"btk_create_primitive failed: {op_res}"
    created_obj = bpy.data.objects.get("Studio_Btk_Cube")
    assert created_obj is not None, "Studio_Btk_Cube was not found in bpy.data.objects"
    assert len(created_obj.data.vertices) == 8
    assert len(created_obj.data.polygons) == 6

    # Execute a Landfall smooth preview operator on the blendertk-created object
    bpy.context.view_layer.objects.active = created_obj
    created_obj.select_set(True)
    lf_res = bpy.ops.landfall.smooth_preview(mode="BOTH")
    assert "FINISHED" in lf_res
    assert bpy.context.scene.landfall_cage_show is True

    # Verify unified workspace root synchronization between Landfall and blendertk
    import blendertk as btk

    with tempfile.TemporaryDirectory(prefix="lf_studio_ws_") as tmp_ws:
        synced_root = workspace_bridge.set_project_root(tmp_ws, write_workspace_mel=True)
        lf_mod = landfall_bridge.get_module()
        lf_prefs = lf_mod.prefs(bpy.context)
        btk_ws = os.path.normpath(str(btk.workspace_root()))
        assert os.path.normcase(lf_prefs.project_root) == os.path.normcase(synced_root)
        assert os.path.normcase(btk_ws) == os.path.normcase(synced_root)
        assert (Path(synced_root) / "workspace.mel").is_file()

    # Cycle 1: Unregister -> Cycle 2: Re-register -> Unregister (prove idempotency & zero leaks)
    landfall_studio.unregister()
    landfall_studio.register()
    assert tentacle_bridge.get_state() == "ACTIVE"
    landfall_studio.unregister()

    after_handlers = _snapshot_handlers()
    after_km_count = _count_addon_keymaps()

    for k in baseline_handlers:
        assert len(after_handlers[k]) == len(baseline_handlers[k]), (
            f"Handler leak in {k}: before={len(baseline_handlers[k])}, after={len(after_handlers[k])}"
        )
    assert after_km_count == baseline_km_count, (
        f"Keymap leak: before={baseline_km_count}, after={after_km_count}"
    )

    lf_mod = landfall_bridge.get_module()
    for fn_name in ("_gizmos_sync", "_keymap_heal", "_deferred_sync"):
        fn = getattr(lf_mod, fn_name, None)
        assert not bpy.app.timers.is_registered(fn), f"Landfall timer {fn_name} still registered!"

    tb_mod = sys.modules.get("tentacle.tcl_blender")
    if tb_mod is not None:
        assert tb_mod._KeymapBridge.poller is None, "Tentacle _KeymapBridge.poller still active!"
        assert tb_mod._QtHost._pump_registered is False, "Tentacle _QtHost._pump_registered still True!"

    assert sys.stdout is orig_stdout, "sys.stdout was not restored after unregister()"
    assert sys.stderr is orig_stderr, "sys.stderr was not restored after unregister()"

    return {
        "mode": "full",
        "status": "PASS",
        "blender_version": rep["blender"]["version_string"],
        "blender_commit": rep["blender"]["build_commit"],
        "python_version": rep["python"]["version"],
        "upstream_shas": {
            k: v["git_sha"] for k, v in rep["dependencies"]["upstream"].items()
        },
        "btk_created_object": created_obj.name,
        "btk_vert_count": len(created_obj.data.vertices),
        "landfall_smooth_cage_active": True,
        "workspace_sync_verified": True,
        "lifecycle_cycles_tested": 2,
        "handlers_clean_after_unregister": True,
        "keymaps_clean_after_unregister": True,
        "streams_restored": True,
    }


def main() -> int:
    args = _parse_args()
    if args.mode == "no-deps":
        result = run_no_deps_test()
    else:
        result = run_full_stack_test()

    print("PHASE01_HEADLESS_RESULT_JSON_BEGIN")
    print(json.dumps(result, indent=2))
    print("PHASE01_HEADLESS_RESULT_JSON_END")

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
