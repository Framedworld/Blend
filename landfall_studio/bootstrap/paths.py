"""Pinned upstream path resolution and sys.path management for Landfall Studio.

Resolves pinned checkouts of landfall, pythontk, uitk, blendertk, and tentacle
without copying upstream repositories into the extension tree.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

PINNED_SHAS: Dict[str, str] = {
    "landfall": "7aa2de8ae4d9765016da671829e8ab05fd29a162",
    "tentacle": "d26fb9a38470e03bcafcd2770ce034b5f256da91",
    "blendertk": "d55d1ca61d5568582bbffe8ec0af458d1e8aa8b6",
    "pythontk": "fb4f9bbada625eacee393ce9059677454ab527d1",
    "uitk": "87973895554daab8b7cdb90d2e449492a805148c",
}

UPSTREAM_REPOS = ("pythontk", "uitk", "blendertk", "tentacle", "landfall")

_added_sys_paths: list[str] = []
_git_sha_cache: Dict[str, Optional[str]] = {}


def _package_root() -> Path:
    """Return the `landfall_studio` package directory."""
    return Path(__file__).resolve().parent.parent


def _repo_root() -> Path:
    """Return the parent checkout containing `landfall_studio` (`Framedworld/Blend`)."""
    return _package_root().parent


def _read_saved_addon_pref(attr_name: str) -> str:
    """Read a saved path preference (`upstream_root` or `deps_dir`) from Blender's AddonPreferences if available."""
    try:
        import bpy

        prefs = getattr(bpy.context, "preferences", None)
        addons = getattr(prefs, "addons", None) if prefs is not None else None
        if addons is not None:
            for key in ("landfall_studio", __package__.split(".")[0] if __package__ else "landfall_studio"):
                addon = addons.get(key)
                if addon is not None and getattr(addon, "preferences", None) is not None:
                    val = str(getattr(addon.preferences, attr_name, "") or "").strip()
                    if val:
                        return val
    except Exception:
        pass
    return ""


def get_upstream_root(custom_root: Optional[str] = None) -> Path:
    """Resolve the directory holding pinned upstream checkouts.

    Search order:
    1. Explicit `custom_root` argument (e.g. from AddonPreferences)
    2. Saved `AddonPreferences.upstream_root` in Blender
    3. `LANDFALL_STUDIO_UPSTREAM_ROOT` environment variable
    4. `<repo_root>/../upstream` (sibling `upstream/` directory)
    5. `<repo_root>/upstream`
    """
    candidates = []
    effective_custom = (custom_root or "").strip() or _read_saved_addon_pref("upstream_root")
    if effective_custom:
        candidates.append(Path(effective_custom))
    env_root = os.environ.get("LANDFALL_STUDIO_UPSTREAM_ROOT", "").strip()
    if env_root:
        candidates.append(Path(env_root))

    repo = _repo_root()
    candidates.append(repo.parent / "upstream")
    candidates.append(repo / "upstream")

    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    if effective_custom:
        return Path(effective_custom).resolve()
    return (repo.parent / "upstream").resolve()


def get_deps_dir(custom_deps_dir: Optional[str] = None) -> Path:
    """Resolve the external Python/Qt dependencies directory.

    Search order:
    1. Explicit `custom_deps_dir` argument
    2. Saved `AddonPreferences.deps_dir` in Blender
    3. `LANDFALL_STUDIO_DEPS` environment variable
    4. `TENTACLE_QT_DEPS` environment variable
    5. `<repo_root>/../.deps/py313` (isolated local workspace dependency folder)
    6. `bpy.utils.user_resource('SCRIPTS', path='addons/modules')` when inside Blender
    """
    effective_custom = (custom_deps_dir or "").strip() or _read_saved_addon_pref("deps_dir")
    if effective_custom:
        return Path(effective_custom).resolve()

    for env_key in ("LANDFALL_STUDIO_DEPS", "TENTACLE_QT_DEPS"):
        val = os.environ.get(env_key, "").strip()
        if val:
            return Path(val).resolve()

    workspace_deps = (_repo_root().parent / ".deps" / f"py{sys.version_info.major}{sys.version_info.minor}").resolve()
    if workspace_deps.is_dir():
        return workspace_deps

    try:
        import bpy

        user_mods = bpy.utils.user_resource("SCRIPTS", path=os.path.join("addons", "modules"))
        if user_mods:
            return Path(user_mods).resolve()
    except Exception:
        pass

    return workspace_deps


def resolve_upstream_paths(custom_root: Optional[str] = None) -> Dict[str, Dict[str, object]]:
    """Return resolved filesystem paths and git metadata for all 5 upstream packages."""
    upstream_root = get_upstream_root(custom_root)
    repo_root = _repo_root()
    results: Dict[str, Dict[str, object]] = {}

    for name in UPSTREAM_REPOS:
        checkout_dir = upstream_root / name
        if name == "landfall" and not checkout_dir.is_dir():
            # Fallback to parent Blend repository root which is a Landfall checkout
            if (repo_root / "__init__.py").is_file() and (repo_root / "blender_manifest.toml").is_file():
                checkout_dir = repo_root

        exists = checkout_dir.is_dir()
        if name == "landfall":
            import_root = checkout_dir.parent if checkout_dir.name == "landfall" else checkout_dir
            init_file = checkout_dir / "__init__.py"
        else:
            import_root = checkout_dir
            init_file = checkout_dir / name / "__init__.py"

        sha = _read_git_sha(checkout_dir) if exists else None
        pinned = PINNED_SHAS.get(name)
        results[name] = {
            "name": name,
            "checkout_dir": str(checkout_dir),
            "import_root": str(import_root),
            "init_file": str(init_file),
            "exists": bool(exists and init_file.is_file()),
            "git_sha": sha,
            "pinned_sha": pinned,
            "sha_matches": bool(sha and pinned and sha.lower() == pinned.lower()),
        }
    return results


def _read_git_sha(repo_dir: Path) -> Optional[str]:
    """Read HEAD commit SHA from a git checkout without mutating state (cached per repo_dir)."""
    cache_key = str(repo_dir)
    if cache_key in _git_sha_cache:
        return _git_sha_cache[cache_key]

    git_dir = repo_dir / ".git"
    if not git_dir.exists():
        _git_sha_cache[cache_key] = None
        return None
    try:
        head_file = git_dir / "HEAD" if git_dir.is_dir() else None
        if head_file and head_file.is_file():
            content = head_file.read_text(encoding="utf-8").strip()
            if content.startswith("ref: "):
                ref_path = git_dir / content[5:].strip()
                if ref_path.is_file():
                    sha = ref_path.read_text(encoding="utf-8").strip()
                    _git_sha_cache[cache_key] = sha
                    return sha
                packed_refs = git_dir / "packed-refs"
                if packed_refs.is_file():
                    ref_name = content[5:].strip()
                    for line in packed_refs.read_text(encoding="utf-8").splitlines():
                        if line and not line.startswith("#") and not line.startswith("^"):
                            parts = line.split()
                            if len(parts) == 2 and parts[1] == ref_name:
                                _git_sha_cache[cache_key] = parts[0]
                                return parts[0]
            elif len(content) == 40:
                _git_sha_cache[cache_key] = content
                return content
    except Exception:
        pass

    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if proc.returncode == 0:
            sha = proc.stdout.strip()
            _git_sha_cache[cache_key] = sha
            return sha
    except Exception:
        pass
    _git_sha_cache[cache_key] = None
    return None


def configure_sys_path(
    custom_upstream_root: Optional[str] = None,
    custom_deps_dir: Optional[str] = None,
) -> Dict[str, object]:
    """Register the dependency directory and upstream package roots on `sys.path`.

    Also sets `TENTACLE_QT_DEPS` in `os.environ` when the dependency directory exists
    so `tentacle` uses the same isolated directory.
    """
    deps_dir = get_deps_dir(custom_deps_dir)
    if deps_dir.is_dir():
        deps_str = str(deps_dir)
        os.environ["TENTACLE_QT_DEPS"] = deps_str
        if deps_str not in sys.path:
            sys.path.insert(0, deps_str)
            _added_sys_paths.append(deps_str)

    resolved = resolve_upstream_paths(custom_upstream_root)
    # Add pythontk, uitk, blendertk, tentacle import roots in dependency order
    for name in ("pythontk", "uitk", "blendertk", "tentacle"):
        info = resolved[name]
        if info["exists"]:
            root_str = str(info["import_root"])
            if root_str not in sys.path:
                sys.path.insert(0, root_str)
                _added_sys_paths.append(root_str)

    return {
        "deps_dir": str(deps_dir),
        "deps_dir_exists": deps_dir.is_dir(),
        "upstream": resolved,
    }
