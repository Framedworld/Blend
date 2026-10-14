"""Explicit CLI provisioning script for Landfall Studio Python/Qt dependencies.

Installs `Pillow>=9.1`, `PySide6`, and `qtpy>=2.0` into an isolated directory
(`C:\\Users\\mattk\\Documents\\Landfall\\.deps\\py313` by default) using Blender's
bundled Python interpreter.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from landfall_studio.bootstrap import deps, paths  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly provision Qt and Python dependencies for Landfall Studio."
    )
    parser.add_argument(
        "--target",
        default="",
        help="Target directory for installed packages (defaults to isolated .deps/py313).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check and print current dependency status without installing.",
    )
    args = parser.parse_args()

    target_dir = args.target or str(paths.get_deps_dir())
    if args.check_only:
        status = deps.check_dependencies(custom_deps_dir=target_dir)
        print(json.dumps(status, indent=2))
        return 0 if status["full_stack_ready"] else 1

    print(f"[landfall_studio] Provisioning dependencies into: {target_dir}")
    result = deps.install_dependencies(target_dir=target_dir)
    print(json.dumps({k: v for k, v in result.items() if k not in ("stdout", "stderr")}, indent=2))
    if not result["ok"]:
        print("STDERR:", result.get("stderr", ""), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
