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

    # 2. Sync blendertk current_workspace if available
    try:
        import blendertk as btk

        btk.set_current_workspace(norm_root)
    except Exception:
        pass

    return norm_root


def sync_from_landfall(root_path: Optional[str] = None) -> Optional[str]:
    """Propagate Landfall's project_root into blendertk's current_workspace."""
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
    return norm_root
