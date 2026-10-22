"""Unified Command Registry and Tool State Service for Landfall Studio.

Provides:
1. Single command registration and execution across Studio operators, `blendertk`, `tentacle`, and `landfall`.
2. Repeatable command history backing Maya's `G` (Repeat Last Command).
3. Persistent tool state (`Q/W/E/R`) and `last_non_select_tool` backing Maya's `Y` (Select Last Tool).
4. Active manipulator axis (`X`, `Y`, `Z`, `VIEW`) backing Maya's Viewport `MMB` Virtual Slider.
5. Last component selection mode (`VERT`, `EDGE`, `FACE`, `MULTI`) backing Maya's `F8` Object/Component toggle.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

VALID_TOOLS = ("SELECT", "TRANSLATE", "ROTATE", "RESIZE")
VALID_AXES = ("X", "Y", "Z", "VIEW")
VALID_COMPONENT_MODES = ("VERT", "EDGE", "FACE", "MULTI")

_registered_commands: Dict[str, Dict[str, Any]] = {}
_command_history: List[Dict[str, Any]] = []
MAX_HISTORY = 64

_tool_state: Dict[str, str] = {
    "active_tool": "TRANSLATE",
    "last_non_select_tool": "TRANSLATE",
    "active_axis": "X",
    "last_component_mode": "VERT",
}


def get_active_tool() -> str:
    """Return current active transform/select tool (`SELECT`, `TRANSLATE`, `ROTATE`, `RESIZE`)."""
    return _tool_state["active_tool"]


def get_last_non_select_tool() -> str:
    """Return last active non-select transform tool (`TRANSLATE`, `ROTATE`, `RESIZE`) for `Y` recall."""
    return _tool_state["last_non_select_tool"]


def set_active_tool(tool: str, axis: Optional[str] = None) -> str:
    """Set the active tool and update `last_non_select_tool` when `tool != 'SELECT'`."""
    norm = (tool or "TRANSLATE").upper()
    if norm not in VALID_TOOLS:
        raise ValueError(f"Unsupported tool '{tool}'. Expected one of {VALID_TOOLS}.")
    _tool_state["active_tool"] = norm
    if norm != "SELECT":
        _tool_state["last_non_select_tool"] = norm
    if axis is not None:
        set_active_axis(axis)
    return norm


def get_active_axis() -> str:
    """Return the active manipulator axis (`X`, `Y`, `Z`, or `VIEW`) for MMB virtual slider scrubbing."""
    return _tool_state["active_axis"]


def set_active_axis(axis: str) -> str:
    """Set the active manipulator axis (`X`, `Y`, `Z`, or `VIEW`)."""
    norm = (axis or "X").upper()
    if norm not in VALID_AXES:
        raise ValueError(f"Unsupported axis '{axis}'. Expected one of {VALID_AXES}.")
    _tool_state["active_axis"] = norm
    return norm


def get_last_component_mode() -> str:
    """Return the last active mesh component mode (`VERT`, `EDGE`, `FACE`, `MULTI`)."""
    return _tool_state["last_component_mode"]


def set_last_component_mode(mode: str) -> str:
    """Record the last active mesh component mode (`VERT`, `EDGE`, `FACE`, `MULTI`)."""
    norm = (mode or "VERT").upper()
    if norm in VALID_COMPONENT_MODES:
        _tool_state["last_component_mode"] = norm
    return _tool_state["last_component_mode"]


def register_command(
    cmd_id: str,
    handler: Callable[..., Any],
    label: str = "",
    category: str = "general",
    repeatable: bool = True,
) -> None:
    """Register a named command in the unified Studio command table."""
    _registered_commands[cmd_id] = {
        "id": cmd_id,
        "label": label or cmd_id,
        "handler": handler,
        "category": category,
        "repeatable": bool(repeatable),
    }


def record_command(
    cmd_id: str,
    kwargs: Optional[Dict[str, Any]] = None,
    callable_fn: Optional[Callable[..., Any]] = None,
    label: Optional[str] = None,
    repeatable: bool = True,
) -> Optional[Dict[str, Any]]:
    """Record an executed command in the repeatable Studio history stack."""
    if not repeatable:
        return None

    spec = _registered_commands.get(cmd_id)
    entry = {
        "id": cmd_id,
        "label": label or (spec["label"] if spec else cmd_id),
        "kwargs": dict(kwargs or {}),
        "callable": callable_fn or (spec["handler"] if spec else None),
        "timestamp": time.monotonic(),
    }
    _command_history.append(entry)
    if len(_command_history) > MAX_HISTORY:
        del _command_history[:-MAX_HISTORY]

    try:
        from .. import ui

        ui.set_command_feedback(
            command=entry["id"],
            result=entry["label"],
            level="INFO",
        )
    except Exception:
        pass

    return entry


def execute_command(cmd_id: str, **kwargs: Any) -> Any:
    """Execute a registered command by ID and record it if repeatable."""
    spec = _registered_commands.get(cmd_id)
    if spec is None:
        raise KeyError(f"Command '{cmd_id}' is not registered in landfall_studio.commands")
    result = spec["handler"](**kwargs)
    if spec.get("repeatable", True) and _command_result_succeeded(result):
        record_command(
            cmd_id=cmd_id,
            kwargs=kwargs,
            callable_fn=spec["handler"],
            label=spec["label"],
            repeatable=True,
        )
    return result


def _command_result_succeeded(result: Any) -> bool:
    """Understand both Studio result dictionaries and Blender operator status sets."""
    if isinstance(result, dict):
        return bool(result.get("ok", True))
    if isinstance(result, set):
        return "CANCELLED" not in result and bool(result & {"FINISHED", "RUNNING_MODAL"})
    return result is not False


def get_last_command() -> Optional[Dict[str, Any]]:
    """Return the most recently recorded repeatable command, or `None`."""
    return _command_history[-1] if _command_history else None


def get_command_history() -> List[Dict[str, Any]]:
    """Return a shallow copy of the command history list."""
    return list(_command_history)


def _resolve_bpy_op(op_path: str) -> Optional[Callable[..., Any]]:
    """Resolve a `'module.op_name'` string to `bpy.ops.<module>.<op_name>`."""
    try:
        import bpy

        mod_name, _, op_name = op_path.partition(".")
        if not mod_name or not op_name:
            return None
        mod = getattr(bpy.ops, mod_name, None)
        return getattr(mod, op_name, None) if mod is not None else None
    except Exception:
        return None


def repeat_last_command() -> Dict[str, Any]:
    """Repeat the most recent Studio command (`G` in Maya profile), or fall back to `bpy.ops.screen.repeat_last`."""
    last = get_last_command()
    if last is not None:
        fn = last.get("callable")
        kwargs = dict(last.get("kwargs") or {})
        cmd_id = last["id"]
        if fn is None:
            fn = _resolve_bpy_op(cmd_id)
        if fn is not None:
            try:
                res = fn(**kwargs)
            except Exception as exc:
                return {
                    "ok": False,
                    "source": "studio_registry",
                    "id": cmd_id,
                    "label": last.get("label", cmd_id),
                    "error": str(exc),
                }
            if not _command_result_succeeded(res):
                error = res.get("error") or res.get("reason") if isinstance(res, dict) else None
                return {
                    "ok": False,
                    "source": "studio_registry",
                    "id": cmd_id,
                    "label": last.get("label", cmd_id),
                    "result": str(res),
                    "error": error or f"Command did not finish: {res}",
                }
            # Re-stamp timestamp on repeat
            last["timestamp"] = time.monotonic()
            try:
                from .. import ui

                ui.set_command_feedback(
                    command=f"repeatLast ({cmd_id})",
                    result=last.get("label", cmd_id),
                    level="INFO",
                )
            except Exception:
                pass
            return {
                "ok": True,
                "source": "studio_registry",
                "id": cmd_id,
                "label": last.get("label", cmd_id),
                "kwargs": kwargs,
                "result": str(res),
            }

    # Fallback to Blender's native repeat_last if no Studio command has been recorded yet
    try:
        import bpy

        if bpy.ops.screen.repeat_last.poll():
            res = bpy.ops.screen.repeat_last()
            return {
                "ok": "FINISHED" in res,
                "source": "blender_repeat_last",
                "id": "screen.repeat_last",
                "label": "Repeat Last (Native)",
                "kwargs": {},
                "result": str(res),
            }
    except Exception as exc:
        return {
            "ok": False,
            "source": "none",
            "id": "",
            "error": str(exc),
        }

    return {
        "ok": False,
        "source": "none",
        "id": "",
        "error": "No repeatable command recorded yet",
    }


def clear_state() -> None:
    """Reset command history and tool state (called on `unregister()`)."""
    from .scene_edits import cancel_all
    cancel_all()
    _command_history.clear()
    _registered_commands.clear()
    _tool_state.update(
        {
            "active_tool": "TRANSLATE",
            "last_non_select_tool": "TRANSLATE",
            "active_axis": "X",
            "last_component_mode": "VERT",
        }
    )


def clear_history():
    """Repeat does not retain references to objects from a replaced scene."""
    _command_history.clear()
