"""Unified command dispatch, repeatable command history (`G`), and tool state tracking (`Q/W/E/R`, `Y`)."""

from . import scene_edits

from .registry import (
    clear_state,
    execute_command,
    get_active_axis,
    get_active_tool,
    get_command_history,
    get_last_command,
    get_last_component_mode,
    get_last_non_select_tool,
    record_command,
    register_command,
    repeat_last_command,
    set_active_axis,
    set_active_tool,
    set_last_component_mode,
)

__all__ = [
    "clear_state",
    "execute_command",
    "get_active_axis",
    "get_active_tool",
    "get_command_history",
    "get_last_command",
    "get_last_component_mode",
    "get_last_non_select_tool",
    "record_command",
    "register_command",
    "repeat_last_command",
    "set_active_axis",
    "set_active_tool",
    "set_last_component_mode",
]
