"""Runtime and module availability diagnostics for Landfall Studio."""

from __future__ import annotations

import platform
import sys
from typing import Any, Dict, Optional

from . import ui
from .adapters import landfall_bridge, tentacle_bridge, workspace_bridge
from .bootstrap.deps import check_dependencies


def get_report(
    custom_upstream_root: Optional[str] = None,
    custom_deps_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a structured diagnostic dictionary covering host, deps, upstream repos, and bridges."""
    blender_info: Dict[str, Any] = {
        "available": False,
        "version": None,
        "version_string": None,
        "build_commit": None,
        "background": True,
    }
    try:
        import bpy

        commit = getattr(bpy.app, "build_hash", b"")
        if isinstance(commit, bytes):
            commit = commit.decode("utf-8", errors="replace")
        blender_info = {
            "available": True,
            "version": tuple(bpy.app.version),
            "version_string": bpy.app.version_string,
            "build_commit": str(commit),
            "background": bool(bpy.app.background),
        }
    except Exception:
        pass

    deps = check_dependencies(
        custom_upstream_root=custom_upstream_root,
        custom_deps_dir=custom_deps_dir,
    )

    ui_state = ui.get_registry_state()

    return {
        "blender": blender_info,
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "platform": sys.platform,
            "machine": platform.machine(),
        },
        "dependencies": deps,
        "qt_available": bool(deps["qt_ready"]),
        "full_stack_ready": bool(deps["full_stack_ready"]),
        "subsystems": {
            "landfall_registered": landfall_bridge.is_registered(),
            "tentacle_state": tentacle_bridge.get_state(),
            "tentacle_instance_active": tentacle_bridge.get_tcl_instance() is not None,
            "workspace_root": workspace_bridge.get_project_root(),
            "qt_desktop_registered": ui_state["registered"],
            "right_dock_mode": ui_state["right_dock"]["mode"],
        },
    }


def format_report(report: Optional[Dict[str, Any]] = None) -> str:
    """Format a human-readable diagnostic summary."""
    data = report or get_report()
    b = data["blender"]
    p = data["python"]
    deps = data["dependencies"]
    sub = data["subsystems"]

    lines = [
        "=== Landfall Studio Diagnostics ===",
        f"Blender : {b['version_string']} (commit {b['build_commit']}, background={b['background']})",
        f"Python  : {p['version']} ({p['executable']})",
        f"Deps Dir: {deps['deps_dir']} (exists={deps['deps_dir_exists']})",
        "--- Python Packages ---",
    ]
    for pkg_name, pkg_info in deps["packages"].items():
        status_str = "OK" if pkg_info["available"] else f"MISSING ({pkg_info['pip_spec']})"
        lines.append(f"  {pkg_name:10s}: {status_str} [{pkg_info['origin'] or 'not found'}]")

    lines.append("--- Upstream Repositories ---")
    for repo_name, repo_info in deps["upstream"].items():
        imp = "OK" if repo_info["importable"] else "MISSING"
        sha = (repo_info["git_sha"] or "unknown")[:10]
        match = "LOCKED" if repo_info["sha_matches"] else "DRIFT/UNKNOWN"
        lines.append(
            f"  {repo_name:10s}: {imp:7s} | SHA={sha} ({match}) | {repo_info['checkout_dir']}"
        )

    lines.extend(
        [
            "--- Subsystems ---",
            f"  Landfall Registered : {sub['landfall_registered']}",
            f"  Tentacle State      : {sub['tentacle_state']} (instance={sub['tentacle_instance_active']})",
            f"  Qt Desktop Ready    : {sub.get('qt_desktop_registered')} (right_dock={sub.get('right_dock_mode')})",
            f"  Workspace Root      : {sub['workspace_root'] or '<not set>'}",
            "===================================",
        ]
    )
    return "\n".join(lines)
