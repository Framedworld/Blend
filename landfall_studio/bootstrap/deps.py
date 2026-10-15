"""Pre-flight dependency checker and explicit opt-in installer for Landfall Studio.

CRITICAL SAFETY CONTRACT (AGENTS.md Rule 8 & Conflict C-01):
`tentacle/tcl_blender.py` executes `_QtBootstrap.run()` at module import time (line 265),
which runs `ensurepip` and `pip install PySide6 qtpy` if Qt is missing.
This module checks package availability via `importlib.util.find_spec` BEFORE any import
of `tentacle.tcl_blender` occurs, guaranteeing zero unsolicited package installations on
startup or extension enable.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .paths import configure_sys_path, get_deps_dir, resolve_upstream_paths

REQUIRED_PYTHON_PACKAGES = (
    ("numpy", "numpy>=1.24"),
    ("PIL", "Pillow>=9.1"),
    ("PySide6", "PySide6"),
    ("qtpy", "qtpy>=2.0"),
)


def _spec_info(module_name: str) -> Dict[str, object]:
    """Check whether `module_name` can be located without executing side-effectful submodules."""
    try:
        spec = importlib.util.find_spec(module_name)
    except (ModuleNotFoundError, ValueError):
        spec = None

    if spec is None:
        return {
            "name": module_name,
            "available": False,
            "origin": None,
        }
    return {
        "name": module_name,
        "available": True,
        "origin": getattr(spec, "origin", None),
    }


_deps_cache: Dict[tuple, Dict[str, object]] = {}


def invalidate_dependency_cache() -> None:
    """Clear the cached dependency report (e.g. after installing packages or changing paths)."""
    _deps_cache.clear()


def check_dependencies(
    custom_upstream_root: Optional[str] = None,
    custom_deps_dir: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, object]:
    """Perform a non-destructive pre-flight check of Python packages and upstream repos.

    Never triggers `pip install` or imports `tentacle.tcl_blender`. Cached per `(upstream_root, deps_dir)`.
    """
    cache_key = (str(custom_upstream_root or ""), str(custom_deps_dir or ""))
    if not force_refresh and cache_key in _deps_cache:
        return dict(_deps_cache[cache_key])

    path_report = configure_sys_path(
        custom_upstream_root=custom_upstream_root,
        custom_deps_dir=custom_deps_dir,
    )

    packages: Dict[str, Dict[str, object]] = {}
    missing_pip_specs: List[str] = []

    for import_name, pip_spec in REQUIRED_PYTHON_PACKAGES:
        info = _spec_info(import_name)
        info["pip_spec"] = pip_spec
        packages[import_name] = info
        if not info["available"]:
            missing_pip_specs.append(pip_spec)

    upstream = path_report["upstream"]
    upstream_specs: Dict[str, Dict[str, object]] = {}
    for name in ("pythontk", "uitk", "blendertk", "tentacle"):
        spec_data = _spec_info(name)
        upstream_specs[name] = {
            **upstream[name],
            "importable": spec_data["available"],
            "origin": spec_data["origin"],
        }

    landfall_info = upstream["landfall"]
    upstream_specs["landfall"] = {
        **landfall_info,
        "importable": bool(landfall_info["exists"]),
        "origin": landfall_info["init_file"] if landfall_info["exists"] else None,
    }

    qt_ready = bool(
        packages["PySide6"]["available"]
        and packages["qtpy"]["available"]
        and packages["PIL"]["available"]
        and packages["numpy"]["available"]
    )

    full_stack_ready = bool(
        qt_ready
        and all(upstream_specs[k]["importable"] for k in ("landfall", "pythontk", "uitk", "blendertk", "tentacle"))
    )

    result = {
        "deps_dir": path_report["deps_dir"],
        "deps_dir_exists": path_report["deps_dir_exists"],
        "packages": packages,
        "missing_pip_specs": missing_pip_specs,
        "upstream": upstream_specs,
        "qt_ready": qt_ready,
        "full_stack_ready": full_stack_ready,
    }
    _deps_cache[cache_key] = result
    return dict(result)


def is_qt_ready(
    custom_upstream_root: Optional[str] = None,
    custom_deps_dir: Optional[str] = None,
) -> bool:
    """Return True only when PySide6, qtpy, Pillow, and numpy are all importable."""
    return bool(
        check_dependencies(
            custom_upstream_root=custom_upstream_root,
            custom_deps_dir=custom_deps_dir,
        )["qt_ready"]
    )


def is_full_stack_ready(
    custom_upstream_root: Optional[str] = None,
    custom_deps_dir: Optional[str] = None,
) -> bool:
    """Return True when all Python dependencies and all 5 upstream repos are ready."""
    return bool(
        check_dependencies(
            custom_upstream_root=custom_upstream_root,
            custom_deps_dir=custom_deps_dir,
        )["full_stack_ready"]
    )


def install_dependencies(
    target_dir: Optional[str] = None,
    packages: Optional[List[str]] = None,
) -> Dict[str, object]:
    """Explicit opt-in installer for missing Python/Qt packages (`Pillow`, `PySide6`, `qtpy`).

    Must ONLY be called by explicit user action (`landfall_studio.install_dependencies`
    operator or `scripts/provision_deps.py`). Never called automatically during `register()`.
    """
    resolved_target = Path(target_dir).resolve() if target_dir else get_deps_dir()
    resolved_target.mkdir(parents=True, exist_ok=True)

    status = check_dependencies(custom_deps_dir=str(resolved_target), force_refresh=True)
    to_install = packages if packages is not None else list(status["missing_pip_specs"])

    if not to_install:
        return {
            "ok": True,
            "target_dir": str(resolved_target),
            "installed": [],
            "message": "All required dependencies are already installed.",
        }

    python_exe = sys.executable
    # Ensure pip is available in Blender's bundled Python
    try:
        import pip  # noqa: F401
    except ImportError:
        subprocess.run(
            [python_exe, "-m", "ensurepip", "--upgrade"],
            capture_output=True,
            text=True,
            check=False,
        )

    cmd = [
        python_exe,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(resolved_target),
        *to_install,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    os.environ["TENTACLE_QT_DEPS"] = str(resolved_target)
    if str(resolved_target) not in sys.path:
        sys.path.insert(0, str(resolved_target))
    importlib.invalidate_caches()
    invalidate_dependency_cache()

    post_status = check_dependencies(custom_deps_dir=str(resolved_target), force_refresh=True)
    return {
        "ok": proc.returncode == 0 and post_status["qt_ready"],
        "returncode": proc.returncode,
        "target_dir": str(resolved_target),
        "requested": to_install,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "qt_ready": post_status["qt_ready"],
        "full_stack_ready": post_status["full_stack_ready"],
    }
