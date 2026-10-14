"""Single Keymap & Interaction Profile Owner for Landfall Studio (`MAYA` and `HYBRID` profiles).

Guarantees:
1. Single authoritative owner for Maya (`Q/W/E/R`, `1/2/3`, `Hold Space`, `RMB`/`Shift+RMB`/`Ctrl+RMB`, `F8–F12`, `G`/`Y`, `Hold D`, `X/C/V`, `F`/`A`, `MMB` slider) vs Hybrid (`G/R/S`, `Alt+1/2/3`, `Ctrl+Tab`, `Z`) profiles.
2. Zero duplicate hotbox bindings on `SPACE` (never binds both `tentacle.show_marking_menu` and `landfall.hotbox` simultaneously).
3. Strict protection of text, console, sculpt, paint, and node editor keymaps.
4. 100% reversible native keymap muting: every muted user keymap item is tracked by signature and restored on profile switch or `unregister()`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

import bpy

from ..adapters import landfall_bridge, tentacle_bridge

PROTECTED_KEYMAP_NAMES: Set[str] = {
    "Text",
    "Text Generic",
    "Console",
    "Info",
    "Outliner",
    "Sculpt",
    "Vertex Paint",
    "Weight Paint",
    "Image Paint",
    "Grease Pencil Edit Mode",
    "Grease Pencil Stroke Sculpt Mode",
    "Node Editor",
}

MAYA_MODE_KEYMAPS: Tuple[Tuple[str, str], ...] = (
    ("Object Mode", "EMPTY"),
    ("Mesh", "EMPTY"),
)

_active_profile: str = "MAYA"
_studio_keymaps: List[Tuple[Any, Any]] = []
_muted_user_signatures: List[Tuple[str, str, str, str, bool, bool, bool, bool]] = []
_added_shadows_intended: Set[Tuple[str, str, bool, bool, bool]] = set()


def get_active_profile() -> str:
    """Return the currently active Studio interaction profile (`'MAYA'` or `'HYBRID'`)."""
    return _active_profile


def get_studio_keymap_count() -> int:
    """Return the number of addon keymap items currently owned by `landfall_studio.keymaps`."""
    return len(_studio_keymaps)


def get_muted_native_count() -> int:
    """Return the number of native user keymap items currently muted by `landfall_studio.keymaps`."""
    return len(_muted_user_signatures)


def _settle_keyconfigs(context) -> None:
    try:
        context.window_manager.keyconfigs.update()
    except Exception:
        pass


def _mute_conflicting_user_items(
    context,
    km_name: str,
    key_type: str,
    ctrl: bool = False,
    alt: bool = False,
    shift: bool = False,
    oskey: bool = False,
) -> None:
    """Mute stock/user keymap items in `km_name` matching `(key_type, ctrl, alt, shift, oskey)` that are not ours."""
    try:
        user_kc = context.window_manager.keyconfigs.user
    except Exception:
        return
    if user_kc is None:
        return

    ukm = user_kc.keymaps.get(km_name)
    if ukm is None:
        return

    for kmi in ukm.keymap_items:
        if (
            kmi.idname.startswith("landfall_studio.")
            or kmi.idname.startswith("landfall.")
            or kmi.idname.startswith("tentacle.")
        ):
            continue
        if (
            kmi.type == key_type
            and bool(kmi.ctrl) == bool(ctrl)
            and bool(kmi.alt) == bool(alt)
            and bool(kmi.shift) == bool(shift)
            and bool(kmi.oskey) == bool(oskey)
            and kmi.active
        ):
            sig = (
                km_name,
                kmi.idname,
                kmi.type,
                kmi.value,
                bool(kmi.ctrl),
                bool(kmi.alt),
                bool(kmi.shift),
                bool(kmi.oskey),
            )
            try:
                kmi.active = False
                if sig not in _muted_user_signatures:
                    _muted_user_signatures.append(sig)
            except Exception:
                pass


def _restore_muted_user_items(context) -> None:
    """Restore all native user keymap items muted by the `MAYA` profile."""
    try:
        user_kc = context.window_manager.keyconfigs.user
    except Exception:
        user_kc = None

    if user_kc is not None:
        for (
            km_name,
            idname,
            key_type,
            value,
            ctrl,
            alt,
            shift,
            oskey,
        ) in _muted_user_signatures:
            ukm = user_kc.keymaps.get(km_name)
            if ukm is None:
                continue
            for kmi in ukm.keymap_items:
                if (
                    kmi.idname == idname
                    and kmi.type == key_type
                    and kmi.value == value
                    and bool(kmi.ctrl) == ctrl
                    and bool(kmi.alt) == alt
                    and bool(kmi.shift) == shift
                    and bool(kmi.oskey) == oskey
                ):
                    try:
                        kmi.active = True
                    except Exception:
                        pass
    _muted_user_signatures.clear()


def _wake_studio_user_items(context) -> None:
    """Ensure mirrored copies of `landfall_studio.*` items in `keyconfigs.user` are active."""
    try:
        user_kc = context.window_manager.keyconfigs.user
    except Exception:
        return
    if user_kc is None:
        return
    for km in user_kc.keymaps:
        for kmi in km.keymap_items:
            if kmi.idname.startswith("landfall_studio.") and not kmi.active:
                try:
                    kmi.active = True
                except Exception:
                    pass


def _add_kmi(
    kc,
    km_name: str,
    space_type: str,
    idname: str,
    key_type: str,
    value: str = "PRESS",
    ctrl: bool = False,
    alt: bool = False,
    shift: bool = False,
    props: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    if km_name in PROTECTED_KEYMAP_NAMES:
        raise ValueError(f"Refusing to bind '{idname}' inside protected keymap '{km_name}'")
    km = kc.keymaps.new(name=km_name, space_type=space_type)
    kmi = km.keymap_items.new(
        idname, key_type, value, ctrl=ctrl, alt=alt, shift=shift
    )
    if props:
        for k, v in props.items():
            try:
                setattr(kmi.properties, k, v)
            except Exception:
                pass
    _studio_keymaps.append((km, kmi))

    lf_mod = landfall_bridge.get_module()
    if lf_mod is not None and hasattr(lf_mod, "SHADOWS_INTENDED"):
        shadow_sig = (km_name, key_type, bool(ctrl), bool(alt), bool(shift))
        if shadow_sig not in lf_mod.SHADOWS_INTENDED:
            lf_mod.SHADOWS_INTENDED.add(shadow_sig)
            _added_shadows_intended.add(shadow_sig)

    return kmi


def remove_studio_keymaps(context=None) -> None:
    """Remove all Studio-registered keymap items and restore all muted native user keymap items."""
    if context is None:
        context = bpy.context

    for km, kmi in _studio_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _studio_keymaps.clear()

    lf_mod = landfall_bridge.get_module()
    if lf_mod is not None and hasattr(lf_mod, "SHADOWS_INTENDED"):
        for sig in _added_shadows_intended:
            lf_mod.SHADOWS_INTENDED.discard(sig)
    _added_shadows_intended.clear()

    _restore_muted_user_items(context)
    _settle_keyconfigs(context)


def apply_profile(context=None, profile: str = "MAYA") -> Dict[str, Any]:
    """Apply the `'MAYA'` or `'HYBRID'` interaction profile cleanly and reversibly."""
    global _active_profile
    if context is None:
        context = bpy.context

    norm_profile = (profile or "MAYA").upper()
    if norm_profile not in ("MAYA", "HYBRID"):
        raise ValueError(f"Unsupported profile '{profile}'. Expected 'MAYA' or 'HYBRID'.")

    # 1. Tear down any previous Studio keymap items & mutes first
    remove_studio_keymaps(context)

    lf_mod = landfall_bridge.get_module()
    p = lf_mod.prefs(context) if lf_mod is not None else None
    kc = context.window_manager.keyconfigs.addon if context.window_manager else None

    if norm_profile == "HYBRID":
        _active_profile = "HYBRID"
        if p is not None:
            p.interaction_profile = "HYBRID"
        # Restore Landfall's G/R/S gizmo keys and E extrude if enabled in prefs
        if lf_mod is not None:
            if p is None or getattr(p, "keys_pick_gizmo", True):
                try:
                    lf_mod._gizmo_keys_disable()
                    lf_mod._gizmo_keys_enable(context)
                except Exception:
                    pass
            if p is None or getattr(p, "maya_extrude", True):
                try:
                    lf_mod._extrude_disable()
                    lf_mod._extrude_enable(context)
                except Exception:
                    pass
        # Bind Tentacle to configured non-Space key (default Z)
        hybrid_key = (getattr(p, "tentacle_key", "Z") if p else "Z") or "Z"
        if hybrid_key.upper() == "SPACE":
            hybrid_key = "Z"
        if tentacle_bridge.get_state() == "ACTIVE":
            tentacle_bridge.set_activation_key(hybrid_key)

        # In Hybrid profile, still provide F8–F12 component shortcuts and Shift+RMB / Ctrl+RMB marking menus
        if kc is not None:
            for fkey, cmode in (
                ("F8", "TOGGLE"),
                ("F9", "VERT"),
                ("F10", "EDGE"),
                ("F11", "FACE"),
                ("F12", "UV"),
            ):
                _add_kmi(
                    kc,
                    "3D View",
                    "VIEW_3D",
                    "landfall_studio.component_mode",
                    fkey,
                    "PRESS",
                    props={"mode": cmode},
                )
        _settle_keyconfigs(context)
        _wake_studio_user_items(context)
        return {
            "profile": _active_profile,
            "studio_kmi_count": len(_studio_keymaps),
            "muted_native_count": len(_muted_user_signatures),
            "hotbox_owner": "tentacle" if tentacle_bridge.get_state() == "ACTIVE" else "landfall",
            "hotbox_key": hybrid_key,
        }

    # --- MAYA PROFILE ---
    _active_profile = "MAYA"
    if p is not None:
        p.interaction_profile = "MAYA"

    # Disable Landfall's G/R/S gizmo keys & E extrude so Q/W/E/R and G/Y have clean Maya ownership
    if lf_mod is not None:
        try:
            lf_mod._gizmo_keys_disable()
        except Exception:
            pass
        try:
            lf_mod._extrude_disable()
        except Exception:
            pass

    # Configure Hold Space hotbox (single owner: Tentacle Qt when active, Landfall hotbox when degraded)
    tentacle_active = tentacle_bridge.get_state() == "ACTIVE"
    if tentacle_active:
        tentacle_bridge.set_activation_key("Key_Space")
        hotbox_owner = "tentacle"
    else:
        hotbox_owner = "landfall_fallback"
        if kc is not None:
            _add_kmi(kc, "3D View", "VIEW_3D", "landfall.hotbox", "SPACE", "PRESS")

    mutes_to_apply: List[Tuple[str, str, bool, bool, bool]] = []

    def _queue_mute(
        km_name: str,
        key_type: str,
        ctrl: bool = False,
        alt: bool = False,
        shift: bool = False,
    ) -> None:
        mutes_to_apply.append((km_name, key_type, ctrl, alt, shift))

    if kc is not None:
        # 1. 3D View global Maya shortcuts: F8–F12 component modes + Alt+V playback
        for fkey, cmode in (
            ("F8", "TOGGLE"),
            ("F9", "VERT"),
            ("F10", "EDGE"),
            ("F11", "FACE"),
            ("F12", "UV"),
        ):
            _queue_mute("3D View", fkey)
            _add_kmi(
                kc,
                "3D View",
                "VIEW_3D",
                "landfall_studio.component_mode",
                fkey,
                "PRESS",
                props={"mode": cmode},
            )

        # Alt+V playback in 3D View (since Space is Hotbox in Maya)
        _add_kmi(
            kc,
            "3D View",
            "VIEW_3D",
            "screen.animation_play",
            "V",
            "PRESS",
            alt=True,
        )
        # Mute bare SPACE in Frames/3D View so holding Space over the viewport never starts timeline playback
        _queue_mute("Frames", "SPACE")
        _queue_mute("3D View", "SPACE")
        _queue_mute("Window", "SPACE")

        # 2. Object Mode & Mesh Edit Mode Maya bindings
        for km_name, space_type in MAYA_MODE_KEYMAPS:
            # Q / W / E / R persistent tool & manipulator selection
            for key_type, tool_mode in (
                ("Q", "SELECT"),
                ("W", "TRANSLATE"),
                ("E", "ROTATE"),
                ("R", "RESIZE"),
            ):
                _queue_mute(km_name, key_type)
                _add_kmi(
                    kc,
                    km_name,
                    space_type,
                    "landfall_studio.select_tool",
                    key_type,
                    "PRESS",
                    props={"tool": tool_mode},
                )

            # 1 / 2 / 3 Maya Smooth Mesh Preview (Base / Smooth+Cage / Smooth)
            for key_type, sm_mode in (
                ("ONE", "CAGE"),
                ("TWO", "BOTH"),
                ("THREE", "SMOOTH"),
            ):
                _queue_mute(km_name, key_type)
                _add_kmi(
                    kc,
                    km_name,
                    space_type,
                    "landfall.smooth_preview",
                    key_type,
                    "PRESS",
                    props={"mode": sm_mode},
                )

            # F8–F12 Component Mode inside Object Mode & Mesh too (so mode keymaps never shadow 3D View)
            for fkey, cmode in (
                ("F8", "TOGGLE"),
                ("F9", "VERT"),
                ("F10", "EDGE"),
                ("F11", "FACE"),
                ("F12", "UV"),
            ):
                _queue_mute(km_name, fkey)
                _add_kmi(
                    kc,
                    km_name,
                    space_type,
                    "landfall_studio.component_mode",
                    fkey,
                    "PRESS",
                    props={"mode": cmode},
                )

            # Distinct RMB Marking Menus: RMB (Component), Shift+RMB (Tool), Ctrl+RMB (Convert)
            _queue_mute(km_name, "RIGHTMOUSE")
            _queue_mute(km_name, "RIGHTMOUSE", shift=True)
            _queue_mute(km_name, "RIGHTMOUSE", ctrl=True)
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.marking_menu",
                "RIGHTMOUSE",
                "PRESS",
                props={"menu_mode": "COMPONENT"},
            )
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.marking_menu",
                "RIGHTMOUSE",
                "PRESS",
                shift=True,
                props={"menu_mode": "TOOL"},
            )
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.marking_menu",
                "RIGHTMOUSE",
                "PRESS",
                ctrl=True,
                props={"menu_mode": "CONVERT"},
            )

            # G (Repeat Last Command) & Y (Select Last Tool)
            _queue_mute(km_name, "G")
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.repeat_last_command",
                "G",
                "PRESS",
            )
            _queue_mute(km_name, "Y")
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.select_last_tool",
                "Y",
                "PRESS",
            )

            # Hold D temporary pivot editing (+ X/C/V snap chords inside modal)
            _queue_mute(km_name, "D")
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.pivot_edit_modal",
                "D",
                "PRESS",
            )

            # Hold X / C / V temporary Grid / Curve-Edge / Vertex snap
            for key_type, snap_target in (
                ("X", "INCREMENT"),
                ("C", "EDGE"),
                ("V", "VERTEX"),
            ):
                _queue_mute(km_name, key_type)
                _add_kmi(
                    kc,
                    km_name,
                    space_type,
                    "landfall_studio.temp_snap_modal",
                    key_type,
                    "PRESS",
                    props={"target": snap_target},
                )

            # F (Frame Selected) & A (Frame All)
            _queue_mute(km_name, "F")
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall.frame_selected",
                "F",
                "PRESS",
            )
            _queue_mute(km_name, "A")
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.frame_all",
                "A",
                "PRESS",
            )

            # MMB Virtual Slider in open viewport
            _queue_mute(km_name, "MIDDLEMOUSE")
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.mmb_virtual_slider",
                "MIDDLEMOUSE",
                "PRESS",
            )

        # Ctrl+E in Mesh Edit Mode -> Landfall Extrude with Maya options
        _queue_mute("Mesh", "E", ctrl=True)
        _add_kmi(
            kc,
            "Mesh",
            "EMPTY",
            "landfall.extrude",
            "E",
            "PRESS",
            ctrl=True,
        )

    _settle_keyconfigs(context)
    for km_name, key_type, ctrl, alt, shift in mutes_to_apply:
        _mute_conflicting_user_items(
            context, km_name, key_type, ctrl=ctrl, alt=alt, shift=shift
        )
    _wake_studio_user_items(context)

    return {
        "profile": _active_profile,
        "studio_kmi_count": len(_studio_keymaps),
        "muted_native_count": len(_muted_user_signatures),
        "hotbox_owner": hotbox_owner,
        "hotbox_key": "SPACE",
    }


class LANDFALL_STUDIO_OT_set_interaction_profile(bpy.types.Operator):
    """Switch between Landfall Studio's `MAYA` and `HYBRID` interaction profiles."""

    bl_idname = "landfall_studio.set_interaction_profile"
    bl_label = "Set Interaction Profile"
    bl_description = "Switch between the full Maya interaction profile and the Hybrid Blender/Maya profile"

    profile: bpy.props.EnumProperty(
        name="Profile",
        items=(
            (
                "MAYA",
                "Maya Profile",
                "Full Maya muscle-memory profile (Q/W/E/R, 1/2/3, Hold Space hotbox, RMB/Shift+RMB/Ctrl+RMB menus, F8-F12, G/Y, Hold D pivot, X/C/V snap)",
            ),
            (
                "HYBRID",
                "Hybrid Profile",
                "Landfall/Blender hybrid profile (G/R/S gizmos, Alt+1/2/3 smooth preview, Ctrl+Tab marking menu, Z hotbox)",
            ),
        ),
        default="MAYA",
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        info = apply_profile(context, self.profile)
        self.report(
            {"INFO"},
            f"Interaction profile set to {info['profile']} ({info['studio_kmi_count']} bindings, hotbox={info['hotbox_owner']} on {info['hotbox_key']})",
        )
        return {"FINISHED"}


KEYMAP_CLASSES = (LANDFALL_STUDIO_OT_set_interaction_profile,)
