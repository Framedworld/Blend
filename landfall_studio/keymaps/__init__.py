"""Keymap profile management and conflict scanner for Landfall Studio."""

from .conflict_scanner import scan_keymap_conflicts
from .profiles import (
    KEYMAP_CLASSES,
    PROTECTED_KEYMAP_NAMES,
    apply_profile,
    get_active_profile,
    get_muted_native_count,
    get_studio_keymap_count,
    remove_studio_keymaps,
)

__all__ = [
    "KEYMAP_CLASSES",
    "PROTECTED_KEYMAP_NAMES",
    "apply_profile",
    "get_active_profile",
    "get_muted_native_count",
    "get_studio_keymap_count",
    "remove_studio_keymaps",
    "scan_keymap_conflicts",
]
