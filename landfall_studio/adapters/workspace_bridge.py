"""Unified workspace/project root bridge between Landfall and blendertk (Conflict C-06)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from . import landfall_bridge

_current_project_root: str = ""


def get_project_root() -> str:
    """Return the active canonical project root across Landfall and blendertk."""
    global _current_project_root
    lf_mod = landfall_bridge.get_module()
    if lf_mod is not None:
        try:
            import bpy

            p = lf_mod.prefs(bpy.context)
            if p is not None and getattr(p, "project_root", ""):
                _current_project_root = os.path.normpath(p.project_root)
                return _current_project_root
        except Exception:
            pass

    try:
        import sys

        if "blendertk" in sys.modules:
            import blendertk as btk

            ws_root = btk.workspace_root()
            if ws_root:
                _current_project_root = os.path.normpath(str(ws_root))
                return _current_project_root
    except Exception:
        pass

    return _current_project_root


def set_project_root(root_path: str, write_workspace_mel: bool = True) -> str:
    """Set the canonical project root in both Landfall and blendertk/pythontk."""
    global _current_project_root
    norm_root = os.path.normpath(str(Path(root_path).resolve()))
    os.makedirs(norm_root, exist_ok=True)
    _current_project_root = norm_root

    # 1. Sync Landfall preferences & workspace.mel if loaded
    lf_mod = landfall_bridge.get_module()
    if lf_mod is not None:
        try:
            import bpy

            p = lf_mod.prefs(bpy.context)
            if p is not None:
                p.project_root = norm_root
            if write_workspace_mel and hasattr(lf_mod, "_write_workspace_mel"):
                lf_mod._write_workspace_mel(norm_root)
        except Exception:
            pass

    # 2. Sync blendertk current_workspace & workspace.mel if available
    try:
        import blendertk as btk

        if write_workspace_mel:
            btk.create_workspace(norm_root, create_dirs=True)
        btk.set_current_workspace(norm_root)
    except Exception:
        pass

    # 3. Sync any open Qt panels (Workspace Editor / Reference Manager)
    try:
        from .. import ui

        ui.sync_project_root_to_panels(norm_root)
    except Exception:
        pass

    return norm_root


def sync_from_landfall(root_path: Optional[str] = None) -> Optional[str]:
    """Propagate Landfall's project_root into blendertk's current_workspace and open Qt panels."""
    global _current_project_root
    target = root_path or get_project_root()
    if not target:
        return None
    norm_root = os.path.normpath(target)
    _current_project_root = norm_root
    try:
        import blendertk as btk

        btk.set_current_workspace(norm_root)
    except Exception:
        pass
    try:
        from .. import ui

        ui.sync_project_root_to_panels(norm_root)
    except Exception:
        pass
    return norm_root


def create_maya_workspace(root_path: str, create_dirs: bool = True) -> dict:
    """Create a Maya-style workspace (`workspace.mel` + directory tree) at `root_path` and set it active."""
    norm_root = set_project_root(root_path, write_workspace_mel=True)
    mel_file = Path(norm_root) / "workspace.mel"
    if not mel_file.is_file():
        try:
            import blendertk as btk

            btk.create_workspace(norm_root, create_dirs=create_dirs)
        except Exception:
            mel_file.write_text(
                '//Maya 2024 Project Definition\nworkspace -fr "scenes" "scenes";\nworkspace -fr "sourceImages" "sourceimages";\n',
                encoding="utf-8",
            )
            if create_dirs:
                (Path(norm_root) / "scenes").mkdir(parents=True, exist_ok=True)
                (Path(norm_root) / "sourceimages").mkdir(parents=True, exist_ok=True)
    elif create_dirs:
        (Path(norm_root) / "scenes").mkdir(parents=True, exist_ok=True)
        (Path(norm_root) / "sourceimages").mkdir(parents=True, exist_ok=True)

    return {
        "ok": mel_file.is_file(),
        "project_root": norm_root,
        "workspace_mel": str(mel_file),
    }


def list_maya_workspaces(search_root: str) -> list[str]:
    """Return discovered Maya workspaces under `search_root` via `blendertk.list_workspaces` (with filesystem fallback)."""
    norm_search = os.path.normpath(str(Path(search_root).resolve()))
    results: list[str] = []
    try:
        import blendertk as btk

        found = btk.list_workspaces(norm_search)
        if isinstance(found, dict):
            results.extend(os.path.normpath(str(v)) for v in found.values())
        elif isinstance(found, (list, tuple, set)):
            for item in found:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    results.append(os.path.normpath(str(item[1])))
                else:
                    results.append(os.path.normpath(str(item)))
    except Exception:
        pass

    # Ensure direct children containing workspace.mel are included
    try:
        for mel in Path(norm_search).rglob("workspace.mel"):
            cand = os.path.normpath(str(mel.parent.resolve()))
            if cand not in results:
                results.append(cand)
    except Exception:
        pass

    return results


