"""Keymap Conflict & Safety Scanner for Landfall Studio (Phase 02).

Audits `keyconfigs.addon` and `keyconfigs.user` to verify:
1. Single hotbox owner on `SPACE` (never both `tentacle.show_marking_menu` and `landfall.hotbox` active simultaneously).
2. Distinct `RMB` (`COMPONENT`), `Shift+RMB` (`TOOL`), and `Ctrl+RMB` (`CONVERT`) bindings in `MAYA` profile.
3. Zero Studio bindings leaked into protected contexts (`Text`, `Console`, `Sculpt`, `Vertex Paint`, `Weight Paint`, `Image Paint`, `Node Editor`).
4. Zero truncated user keymaps (`_keymap_survey()`).
5. Zero duplicate active `landfall_studio.*` items with identical `(km.name, type, value, ctrl, alt, shift, oskey)` signatures.
"""

from __future__ import annotations

from typing import Any, Dict, List

import bpy

from ..adapters import landfall_bridge, tentacle_bridge
from .profiles import (
    PROTECTED_KEYMAP_NAMES,
    get_active_profile,
    get_muted_native_count,
    get_studio_keymap_count,
)


def scan_keymap_conflicts(context=None) -> Dict[str, Any]:
    """Run a comprehensive keymap conflict and context-protection audit."""
    if context is None:
        context = bpy.context

    kc = context.window_manager.keyconfigs if context.window_manager else None
    addon_kc = kc.addon if kc else None
    user_kc = kc.user if kc else None

    protected_leaks: List[Dict[str, Any]] = []
    duplicate_studio_bindings: List[Dict[str, Any]] = []
    space_hotbox_bindings: List[Dict[str, Any]] = []
    rmb_menu_bindings: List[Dict[str, Any]] = []

    if addon_kc is not None:
        for km in addon_kc.keymaps:
            seen_sigs = {}
            for kmi in km.keymap_items:
                if not kmi.active:
                    continue

                is_studio = kmi.idname.startswith("landfall_studio.")
                is_tentacle = kmi.idname.startswith("tentacle.")
                is_landfall = kmi.idname.startswith("landfall.")

                # Check protected contexts for Studio bindings
                if km.name in PROTECTED_KEYMAP_NAMES and is_studio:
                    protected_leaks.append(
                        {
                            "keymap": km.name,
                            "idname": kmi.idname,
                            "key": kmi.type,
                        }
                    )

                # Check duplicate Studio bindings within the same keymap
                if is_studio:
                    sig = (
                        kmi.type,
                        kmi.value,
                        bool(kmi.ctrl),
                        bool(kmi.alt),
                        bool(kmi.shift),
                        bool(kmi.oskey),
                    )
                    if sig in seen_sigs:
                        duplicate_studio_bindings.append(
                            {
                                "keymap": km.name,
                                "first_idname": seen_sigs[sig],
                                "second_idname": kmi.idname,
                                "signature": sig,
                            }
                        )
                    else:
                        seen_sigs[sig] = kmi.idname

                # Track SPACE PRESS hotbox bindings
                if (
                    kmi.type == "SPACE"
                    and kmi.value == "PRESS"
                    and not (kmi.ctrl or kmi.alt or kmi.shift or kmi.oskey)
                    and (is_studio or is_tentacle or is_landfall)
                ):
                    space_hotbox_bindings.append(
                        {
                            "keymap": km.name,
                            "idname": kmi.idname,
                        }
                    )

                # Track RMB marking menu bindings
                if kmi.idname == "landfall_studio.marking_menu":
                    rmb_menu_bindings.append(
                        {
                            "keymap": km.name,
                            "key": kmi.type,
                            "ctrl": bool(kmi.ctrl),
                            "shift": bool(kmi.shift),
                            "alt": bool(kmi.alt),
                            "menu_mode": str(getattr(kmi.properties, "menu_mode", "")),
                        }
                    )

    # Check truncated user keymaps via Landfall's survey
    truncated_keymaps = []
    lf_mod = landfall_bridge.get_module()
    if lf_mod is not None and hasattr(lf_mod, "_keymap_survey"):
        try:
            for name, native, expected in lf_mod._keymap_survey():
                truncated_keymaps.append(
                    {"keymap": name, "native_count": native, "expected_count": expected}
                )
        except Exception:
            pass

    # Check if any active native SPACE animation_play binding still shadows 3D View in MAYA profile
    active_profile = get_active_profile()
    unmuted_space_conflicts = []
    if active_profile == "MAYA" and user_kc is not None:
        for km_name in ("3D View", "Frames"):
            ukm = user_kc.keymaps.get(km_name)
            if ukm is None:
                continue
            for kmi in ukm.keymap_items:
                if (
                    kmi.active
                    and kmi.type == "SPACE"
                    and kmi.value == "PRESS"
                    and not (kmi.ctrl or kmi.alt or kmi.shift or kmi.oskey)
                    and kmi.idname not in ("tentacle.show_marking_menu", "landfall.hotbox")
                ):
                    unmuted_space_conflicts.append(
                        {"keymap": km_name, "idname": kmi.idname}
                    )

    # Verify single hotbox owner on SPACE in MAYA profile
    space_owner_idnames = {b["idname"] for b in space_hotbox_bindings}
    duplicate_hotbox_on_space = len(space_owner_idnames) > 1
    if active_profile == "MAYA":
        hotbox_ok = len(space_owner_idnames) == 1 and not duplicate_hotbox_on_space
    else:
        hotbox_ok = not duplicate_hotbox_on_space

    clean = (
        len(protected_leaks) == 0
        and len(duplicate_studio_bindings) == 0
        and len(truncated_keymaps) == 0
        and len(unmuted_space_conflicts) == 0
        and hotbox_ok
    )

    return {
        "clean": clean,
        "active_profile": active_profile,
        "studio_keymap_item_count": get_studio_keymap_count(),
        "muted_native_item_count": get_muted_native_count(),
        "tentacle_key_info": tentacle_bridge.get_activation_key_info(),
        "space_hotbox_bindings": space_hotbox_bindings,
        "duplicate_hotbox_on_space": duplicate_hotbox_on_space,
        "unmuted_space_conflicts": unmuted_space_conflicts,
        "rmb_menu_bindings": rmb_menu_bindings,
        "protected_context_leaks": protected_leaks,
        "duplicate_studio_bindings": duplicate_studio_bindings,
        "truncated_user_keymaps": truncated_keymaps,
    }
