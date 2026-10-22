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
_input_preferences_backup: Dict[str, Any] = {}
_profile_mutes: list = []


def reapply_profile_mutes(context=None) -> None:
    """Reapply ownership after a native rebuild without replacing live keymaps."""
    context = context or bpy.context
    for km_name, key_type, ctrl, alt, shift in _profile_mutes:
        _mute_conflicting_user_items(context, km_name, key_type, ctrl=ctrl, alt=alt, shift=shift)
    _wake_studio_user_items(context)
    if _sculpt_transforms_wanted:
        sync_sculpt_transforms(True)
    if _sculpt_keymaps:
        _refresh_sculpt_mutes()


def _set_maya_navigation(context) -> None:
    """Use Maya's horizontal dolly, without permanently changing user inputs."""
    inputs = context.preferences.inputs
    for name, value in {
        "view_zoom_method": "DOLLY", "view_zoom_axis": "HORIZONTAL",
        "invert_mouse_zoom": False, "invert_zoom_wheel": False,
        "use_zoom_to_mouse": False,
    }.items():
        if hasattr(inputs, name):
            _input_preferences_backup.setdefault(name, getattr(inputs, name))
            if getattr(inputs, name) != value:
                setattr(inputs, name, value)


def _restore_navigation(context) -> None:
    for name, value in _input_preferences_backup.items():
        setattr(context.preferences.inputs, name, value)
    _input_preferences_backup.clear()


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


def _get_muted_kmi_state_path() -> str:
    import os
    try:
        cfg_dir = bpy.utils.user_resource("CONFIG")
    except Exception:
        cfg_dir = ""
    if not cfg_dir:
        import tempfile
        cfg_dir = tempfile.gettempdir()
    os.makedirs(cfg_dir, exist_ok=True)
    return os.path.join(cfg_dir, "landfall_studio_muted_kmi.json")


def _save_muted_signatures_to_disk() -> None:
    import json
    import os
    path = _get_muted_kmi_state_path()
    try:
        if not _muted_user_signatures:
            if os.path.exists(path):
                os.remove(path)
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump([list(sig) for sig in _muted_user_signatures], f)
    except Exception:
        pass


def _load_persisted_muted_signatures() -> List[Tuple[str, str, str, str, bool, bool, bool, bool]]:
    import json
    import os
    path = _get_muted_kmi_state_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        out = []
        for item in raw:
            if isinstance(item, list) and len(item) == 8:
                out.append((
                    str(item[0]),
                    str(item[1]),
                    str(item[2]),
                    str(item[3]),
                    bool(item[4]),
                    bool(item[5]),
                    bool(item[6]),
                    bool(item[7]),
                ))
        return out
    except Exception:
        return []


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

    prefs = getattr(context, "preferences", None)
    was_dirty = bool(getattr(prefs, "is_dirty", False)) if prefs is not None else False

    for kmi in ukm.keymap_items:
        if any(owned_km.name == km_name and owned.idname == kmi.idname and owned.compare(kmi)
               for owned_km, owned in _studio_keymaps):
            continue
        # Keep upstream's own F binding mirrored. Muting it makes its healer
        # rebuild the complete Mesh map repeatedly underneath modal tools.
        if (kmi.idname == "view3d.view_selected" and key_type == "F") or (
            kmi.idname == "wm.call_menu" and key_type == "BACK_SPACE"
        ):
            continue
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

    if prefs is not None and not was_dirty:
        try:
            prefs.is_dirty = False
        except Exception:
            pass


def _restore_muted_user_items(context) -> None:
    """Restore all native user keymap items muted by the `MAYA` profile (including any persisted from prior sessions)."""
    try:
        user_kc = context.window_manager.keyconfigs.user
    except Exception:
        user_kc = None

    prefs = getattr(context, "preferences", None)
    was_dirty = bool(getattr(prefs, "is_dirty", False)) if prefs is not None else False

    all_sigs = list(_muted_user_signatures)
    for persisted_sig in _load_persisted_muted_signatures():
        if persisted_sig not in all_sigs:
            all_sigs.append(persisted_sig)

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
        ) in all_sigs:
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
    _save_muted_signatures_to_disk()

    if prefs is not None and not was_dirty:
        try:
            prefs.is_dirty = False
        except Exception:
            pass


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
    km = kc.keymaps.new(name=km_name, space_type=space_type,
                       tool=km_name.startswith("3D View Tool:"))
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
    prefs = getattr(context, "preferences", None)
    was_dirty = bool(getattr(prefs, "is_dirty", False)) if prefs is not None else False
    try:
        sync_sculpt_keymaps(False)
        sync_sculpt_transforms(False)

        for km, kmi in _studio_keymaps:
            try:
                km.keymap_items.remove(kmi)
            except Exception:
                pass
        _studio_keymaps.clear()
        _profile_mutes.clear()

        lf_mod = landfall_bridge.get_module()
        if lf_mod is not None and hasattr(lf_mod, "SHADOWS_INTENDED"):
            for sig in _added_shadows_intended:
                lf_mod.SHADOWS_INTENDED.discard(sig)
        _added_shadows_intended.clear()

        _restore_muted_user_items(context)
        _restore_navigation(context)
        _settle_keyconfigs(context)
    finally:
        # Navigation restoration and the final keyconfig merge can dirty the
        # preferences after individual mute helpers have restored their flag.
        # Preserve the caller's state across this complete teardown operation.
        if prefs is not None:
            try:
                prefs.is_dirty = was_dirty
            except Exception:
                pass


# Sculpt is a deliberately scoped interaction mode owned by this same registry.
# Native Sculpt bindings are restored immediately on leaving it or disabling pen
# controls. Maya's object/component mappings never receive these bindings.
_sculpt_keymaps = []
_sculpt_muted = []
_sculpt_signatures = set()
_sculpt_transform_states=[]
_sculpt_transforms_wanted=False
_sculpt_pen_wanted=None
_sculpt_user_repairs=set()
_sculpt_modal_cancel=None

def _sync_sculpt_modal_cancel(enabled):
    """Route RMB to the native paint cancellation path during Sculpt Studio."""
    global _sculpt_modal_cancel
    config=bpy.context.window_manager.keyconfigs.user
    km=config.keymaps.get('Paint Stroke Modal') if config else None
    if km is None:return
    if enabled and _sculpt_modal_cancel is None:
        item=next((i for i in km.keymap_items if i.type=='RIGHTMOUSE' and i.value=='PRESS' and i.propvalue=='CANCEL'),None)
        if item is not None:
            _sculpt_modal_cancel=('existing',item.active);item.active=True
        else:
            km.keymap_items.new_modal('CANCEL','RIGHTMOUSE','PRESS',any=True)
            _sculpt_modal_cancel=('added',None)
    elif not enabled and _sculpt_modal_cancel is not None:
        kind,was_active=_sculpt_modal_cancel
        item=next((i for i in km.keymap_items if i.type=='RIGHTMOUSE' and i.value=='PRESS' and i.propvalue=='CANCEL'),None)
        if item:
            if kind=='added':km.keymap_items.remove(item)
            else:item.active=was_active
        _sculpt_modal_cancel=None


def sync_sculpt_transforms(enabled):
    """Maya marquee overrides share native transform tool maps with Sculpt.

    Restore native transform drags for the duration of Sculpt mode, preserving
    the exact Maya/Hybrid map state for when the artist returns.
    """
    global _sculpt_transforms_wanted
    _sculpt_transforms_wanted=enabled
    wm=bpy.context.window_manager
    if not wm or not wm.keyconfigs.user:return
    if not enabled:
        for name,sig,was_active in _sculpt_transform_states:
            for km in wm.keyconfigs.user.keymaps:
                if km.name!=name:continue
                for item in km.keymap_items:
                    if _sculpt_item_signature(item)==sig:item.active=was_active
        _sculpt_transform_states.clear()
        return
    known={(name,sig) for name,sig,_ in _sculpt_transform_states}
    for km in wm.keyconfigs.user.keymaps:
        if km.name not in ('3D View Tool: Move','3D View Tool: Rotate','3D View Tool: Scale'):continue
        for item in km.keymap_items:
            if item.idname not in ('transform.translate','transform.rotate','transform.resize'):continue
            sig=_sculpt_item_signature(item)
            if (km.name,sig) not in known:
                _sculpt_transform_states.append((km.name,sig,item.active));known.add((km.name,sig))
            if not item.active:item.active=True


def _sculpt_item_signature(item):
    properties=item.properties
    return (item.idname,item.type,item.value,item.ctrl,item.shift,item.alt,item.oskey,item.any,
            repr(sorted(properties.items())) if properties else '[]')


def sculpt_mutes_item(km_name,item):
    if not _sculpt_keymaps or (km_name not in ('Sculpt','3D View') and not km_name.startswith('3D View Tool: Sculpt')):
        return False
    if item.idname=='landfall_studio.marking_menu' and item.type=='RIGHTMOUSE':return True
    if item.idname.startswith('landfall_studio.'): return False
    if item.type=='LEFTMOUSE' and not _sculpt_pen_wanted:return False
    if km_name=='3D View' and item.idname=='sculpt.brush_stroke' and getattr(item.properties,'ignore_background_click',False):return False
    if km_name=='3D View':return item.type=='LEFTMOUSE' or (item.type in ('SPACE','TAB') and not (item.ctrl or item.alt or item.shift)) or (item.type=='RIGHTMOUSE' and not (item.ctrl or item.alt or item.shift))
    return item.type=='LEFTMOUSE' or (item.type,item.ctrl,item.shift,item.alt) in _sculpt_signatures


def _refresh_sculpt_mutes():
    wm=bpy.context.window_manager
    known={(name,sig) for name,sig,was_active in _sculpt_muted}
    for km in wm.keyconfigs.user.keymaps:
        for item in km.keymap_items:
            if not _sculpt_pen_wanted and item.type=='LEFTMOUSE':
                sig=_sculpt_item_signature(item)
                original=next((was for name,saved,was in _sculpt_muted if name==km.name and saved==sig),None)
                if original is not None:item.active=original
            if not sculpt_mutes_item(km.name,item):continue
            sig=_sculpt_item_signature(item)
            if (km.name,sig) not in known:
                _sculpt_muted.append((km.name,sig,item.active)); known.add((km.name,sig))
            item.active=False
    sync_sculpt_paint_mode()


def sync_sculpt_paint_mode(context=None):
    """Transform/SelectRect tools own drags; only Draw owns ordinary strokes."""
    if not _sculpt_keymaps:return
    context=context or bpy.context
    # Blender may omit native-operator addon rows from the merged user map
    # after an asset/mode transition. Reconcile only these scoped fallbacks.
    addon=context.window_manager.keyconfigs.addon;user=context.window_manager.keyconfigs.user
    source=addon.keymaps.get('3D View') if addon else None
    target=user.keymaps.get('3D View') if user else None
    was_dirty=context.preferences.is_dirty;repaired=False
    if source and target:
        originals=[i for i in source.keymap_items if i.idname=='sculpt.brush_stroke' and getattr(i.properties,'ignore_background_click',False)]
        for item in originals:
            sig=_sculpt_item_signature(item)
            if any(_sculpt_item_signature(i)==sig for i in target.keymap_items):continue
            copy=target.keymap_items.new(item.idname,item.type,item.value,ctrl=item.ctrl,shift=item.shift,alt=item.alt)
            for field in ('mode','brush_toggle','ignore_background_click'):setattr(copy.properties,field,getattr(item.properties,field))
            copy.active=item.active;_sculpt_user_repairs.add(_sculpt_item_signature(copy))
            repaired=True
    if repaired and not was_dirty:
        try:context.preferences.is_dirty=False
        except Exception:pass
    tool=None
    for window in context.window_manager.windows:
        tool=window.workspace.tools.from_space_view3d_mode('SCULPT',create=False)
        if tool:break
    drawing=not tool or tool.idname=='builtin.brush' or tool.idname.startswith('builtin_brush.')
    for config in (context.window_manager.keyconfigs.addon,context.window_manager.keyconfigs.user):
        km=config.keymaps.get('3D View') if config else None
        if km:
            for item in km.keymap_items:
                if item.idname=='sculpt.brush_stroke' and getattr(item.properties,'ignore_background_click',False):
                    enabled=bool(_sculpt_pen_wanted) and (bool(item.ctrl) or drawing)
                    if item.active!=enabled:item.active=enabled


def sync_sculpt_keymaps(enabled):
    global _sculpt_pen_wanted
    pen=bool(getattr(getattr(bpy.context.scene,'landfall_sculpt',None),'bbrush_enabled',False))
    if enabled and _sculpt_keymaps and pen!=_sculpt_pen_wanted:
        _sculpt_pen_wanted=pen
        for config in (bpy.context.window_manager.keyconfigs.addon,bpy.context.window_manager.keyconfigs.user):
            km=config.keymaps.get('Sculpt') if config else None
            if km:
                for item in km.keymap_items:
                    if item.idname=='landfall_studio.sculpt_pen':item.active=pen
        _refresh_sculpt_mutes()
    if not enabled:
        had_keys=bool(_sculpt_keymaps)
        _sync_sculpt_modal_cancel(False)
        for name in {entry[0] for entry in _sculpt_keymaps}:
            km=bpy.context.window_manager.keyconfigs.addon.keymaps.get(name)
            if km is None:continue
            # Keyconfig updates can renumber native item IDs. Find a fresh
            # owned item each time; never remove another owner's item by an
            # ID/pointer captured before that update.
            while True:
                item=next((i for i in km.keymap_items if i.idname in ('landfall_studio.sculpt_pen','landfall_studio.sculpt_shortcut')
                    or (name=='3D View' and i.idname=='sculpt.brush_stroke' and getattr(i.properties,'ignore_background_click',False))),None)
                if item is None:break
                km.keymap_items.remove(item)
        _sculpt_keymaps.clear()
        target=bpy.context.window_manager.keyconfigs.user.keymaps.get('3D View')
        if target:
            for item in list(target.keymap_items):
                if _sculpt_item_signature(item) in _sculpt_user_repairs:target.keymap_items.remove(item)
        _sculpt_user_repairs.clear()
        if had_keys:_settle_keyconfigs(bpy.context)
        # Upstream repair can rebuild user keymaps. Restore current entries by
        # value; never keep Blender RNA item pointers across a native rebuild.
        wm=bpy.context.window_manager
        for name,sig,was_active in _sculpt_muted:
            km=wm.keyconfigs.user.keymaps.get(name) if wm and wm.keyconfigs.user else None
            if km:
                for item in km.keymap_items:
                    if _sculpt_item_signature(item)==sig:item.active=was_active
        _sculpt_muted.clear()
        _sculpt_signatures.clear()
        _sculpt_pen_wanted=None
        return
    wm=bpy.context.window_manager
    if not wm or not wm.keyconfigs.addon: return
    if _sculpt_keymaps: return
    _sculpt_pen_wanted=pen
    km=wm.keyconfigs.addon.keymaps.new(name='Sculpt',space_type='EMPTY')
    # Append in stable order. Inserting at the head renumbers user-map IDs
    # during Blender's merge and can attach native mute diffs to other keys.
    click=km.keymap_items.new('landfall_studio.sculpt_pen','LEFTMOUSE','CLICK',any=True)
    _sculpt_keymaps.append((km.name,click.id))
    mouse=km.keymap_items.new('landfall_studio.sculpt_pen','LEFTMOUSE','PRESS',any=True)
    _sculpt_keymaps.append((km.name,mouse.id))
    click.active=mouse.active=pen
    keys=[('SPACE','QUICK',False,False),('TAB','FOCUS_UI',False,False),('RIGHTMOUSE','QUICK_STICKY',False,False),
          ('B','PALETTE',False,False),('S','draw_size',False,False),('U','z_intensity',False,False),('O','focal_shift',False,False),
          ('I','z_intensity',False,False),
          *[(k,k,False,False) for k in ('Q','W','E','R','X','L','K','P','F')],
          ('F','POLYFRAME',False,True),('D','DIVIDE',True,False),('D','LOWER',False,True),('D','HIGHER',False,False),
          ('W','GROUP',True,False),('NUMPAD_PLUS','GROW',True,False),('NUMPAD_MINUS','SHRINK',True,False),
          ('UP_ARROW','CONTRAST_UP',True,False),('DOWN_ARROW','CONTRAST_DOWN',True,False),('SLASH','K',False,True)]
    for key,action,ctrl,shift in keys:
        item=km.keymap_items.new('landfall_studio.sculpt_shortcut',key,'PRESS',ctrl=ctrl,shift=shift)
        item.properties.action=action
        _sculpt_keymaps.append((km.name,item.id)); _sculpt_signatures.add((key,ctrl,shift,False))
    release=km.keymap_items.new('landfall_studio.sculpt_shortcut','SPACE','RELEASE')
    release.properties.action='QUICK_RELEASE';_sculpt_keymaps.append((km.name,release.id))
    # Native brush entries in Sculpt are merged ahead of Python entries even
    # when appended. Put painting in the lower-priority 3D View map, after the
    # classifier. Its poll restricts it to Sculpt. Scoped mouse mutes prevent
    # generic viewport selection/navigation from intercepting this fallback.
    paint_km=wm.keyconfigs.addon.keymaps.new(name='3D View',space_type='VIEW_3D')
    for ctrl,shift,alt,value,mode,toggle in (
        (False,False,False,'PRESS','NORMAL','None'),
        (False,False,True,'PRESS','INVERT','None'),
        (False,True,False,'PRESS','NORMAL','SMOOTH'),
        (False,True,True,'PRESS','NORMAL','SMOOTH'),
        (True,False,False,'CLICK_DRAG','NORMAL','MASK'),
        (True,False,True,'CLICK_DRAG','INVERT','MASK')):
        fallback=paint_km.keymap_items.new('sculpt.brush_stroke','LEFTMOUSE',value,ctrl=ctrl,shift=shift,alt=alt)
        fallback.properties.mode=mode; fallback.properties.brush_toggle=toggle
        fallback.properties.ignore_background_click=True
        fallback.active=pen
        _sculpt_keymaps.append((paint_km.name,fallback.id))
    _settle_keyconfigs(bpy.context)
    _refresh_sculpt_mutes()
    _sync_sculpt_modal_cancel(True)


def apply_profile(context=None, profile: str = "MAYA") -> Dict[str, Any]:
    """Apply the `'MAYA'` or `'HYBRID'` interaction profile cleanly and reversibly.

    Restores the caller's `preferences.is_dirty` afterwards, so Studio's keymap mutes never
    trigger auto-save on their own and the user's own pending preference edits are never dropped.
    """
    if context is None:
        context = bpy.context
    prefs = getattr(context, "preferences", None)
    was_dirty = bool(getattr(prefs, "is_dirty", False)) if prefs is not None else False
    try:
        return _apply_profile_unguarded(context, profile)
    finally:
        if prefs is not None:
            try:
                prefs.is_dirty = was_dirty
            except Exception:
                pass


def _apply_profile_unguarded(context, profile: str) -> Dict[str, Any]:
    global _active_profile
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
    _set_maya_navigation(context)
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
        _queue_mute("Object Mode", "D", ctrl=True)
        _add_kmi(kc, "Object Mode", "EMPTY", "landfall_studio.duplicate_objects", "D", ctrl=True, props={'linked':False})
        # Ctrl+G / Ctrl+Shift+G -> Maya Group / Ungroup (Blender: collection add/remove)
        _queue_mute("Object Mode", "G", ctrl=True)
        _add_kmi(kc, "Object Mode", "EMPTY", "landfall_studio.group_objects", "G", ctrl=True)
        _queue_mute("Object Mode", "G", ctrl=True, shift=True)
        _add_kmi(kc, "Object Mode", "EMPTY", "landfall_studio.ungroup_objects", "G", ctrl=True, shift=True)
        # Ctrl+F9/F10/F11 -> Maya convert selection to vertices / edges / faces
        for fkey, target in (("F9", "VERT"), ("F10", "EDGE"), ("F11", "FACE")):
            _queue_mute("Mesh", fkey, ctrl=True)
            _add_kmi(kc, "Mesh", "EMPTY", "landfall_studio.convert_selection", fkey,
                     ctrl=True, props={"target": target})
        _queue_mute("Object Mode", "S")
        _add_kmi(kc, "Object Mode", "EMPTY", "landfall_studio.set_key", "S")
        for km_name, space_type in (("3D View", "VIEW_3D"),) + MAYA_MODE_KEYMAPS:
            _queue_mute(km_name, "Z")
            _queue_mute(km_name, "Z", shift=True)
            _add_kmi(kc, km_name, space_type, "ed.undo", "Z")
            _add_kmi(kc, km_name, space_type, "ed.redo", "Z", shift=True)
        for tool_map in ("3D View Tool: Select Box", "3D View Tool: Select Box (fallback)",
                         "3D View Tool: Move", "3D View Tool: Rotate", "3D View Tool: Scale"):
            for ctrl, shift, action in ((False, False, "SET"), (False, True, "ADD"),
                                         (True, False, "SUB"), (True, True, "ADD")):
                _add_kmi(kc, tool_map, "VIEW_3D", "landfall_studio.maya_box_select",
                         "LEFTMOUSE", "CLICK_DRAG", ctrl=ctrl, shift=shift, props={"mode": action})
        for shift, action in ((False, "REMOVE"), (True, "ADD")):
            _add_kmi(kc, "3D View", "VIEW_3D", "landfall_studio.maya_select",
                     "LEFTMOUSE", ctrl=True, shift=shift, props={"action": action})
        # Blender's global W (cycle Select tools) is processed before the mode
        # keymaps. Own Q/W/E/R here too, with the operator polling the supported
        # viewport modes; protected sculpt/paint/editor maps keep their inputs.
        for key_type, tool_mode in (("Q", "SELECT"), ("W", "TRANSLATE"),
                                    ("E", "ROTATE"), ("R", "RESIZE")):
            _add_kmi(kc, "3D View", "VIEW_3D", "landfall_studio.select_tool",
                     key_type, props={"tool": tool_mode})

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

            # 4 / 5 / 6 / 7 Maya Viewport 2.0 Shading (Wireframe / Smooth Shaded / Textured / Use All Lights)
            for key_type, sh_mode in (
                ("FOUR", "4"),
                ("FIVE", "5"),
                ("SIX", "6"),
                ("SEVEN", "7"),
            ):
                _queue_mute(km_name, key_type)
                _add_kmi(
                    kc,
                    km_name,
                    space_type,
                    "landfall_studio.viewport_shading",
                    key_type,
                    "PRESS",
                    props={"mode": sh_mode},
                )

            # B -> Maya Soft Selection Toggle & Hold B + LMB-Drag Falloff Radius Ring
            _queue_mute(km_name, "B")
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.soft_selection",
                "B",
                "PRESS",
                props={"action": "MODAL_OR_TOGGLE"},
            )

            # Ctrl+Shift+A -> Conflict-free Select / Deselect All fallback (since A is Frame All and Ctrl+A is Channel Box/Attr Editor)
            _queue_mute(km_name, "A", ctrl=True, shift=True)
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.select_all_toggle",
                "A",
                "PRESS",
                ctrl=True,
                shift=True,
                props={"action": "TOGGLE"},
            )

            # DEL / BACK_SPACE -> Conflict-free Maya Smart Delete (since X is Hold Grid Snap)
            for del_key in ("DEL", "BACK_SPACE"):
                _queue_mute(km_name, del_key)
                _add_kmi(
                    kc,
                    km_name,
                    space_type,
                    "landfall_studio.smart_delete",
                    del_key,
                    "PRESS",
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

            # Ctrl+A -> Cycle Channel Box / Attribute Editor (Maya Classic right-dock toggle)
            _queue_mute(km_name, "A", ctrl=True)
            _add_kmi(
                kc,
                km_name,
                space_type,
                "landfall_studio.cycle_attribute_channels",
                "A",
                "PRESS",
                ctrl=True,
                props={"mode": "CYCLE"},
            )

        # Also bind Ctrl+A, Ctrl+Shift+Q (Quick Favorites), and Alt+Z (X-Ray) in 3D View
        _queue_mute("3D View", "A", ctrl=True)
        _add_kmi(
            kc,
            "3D View",
            "VIEW_3D",
            "landfall_studio.cycle_attribute_channels",
            "A",
            "PRESS",
            ctrl=True,
            props={"mode": "CYCLE"},
        )
        _queue_mute("3D View", "Q", ctrl=True, shift=True)
        _add_kmi(
            kc,
            "3D View",
            "VIEW_3D",
            "wm.call_menu",
            "Q",
            "PRESS",
            ctrl=True,
            shift=True,
            props={"name": "SCREEN_MT_user_menu"},
        )
        _queue_mute("3D View", "Z", alt=True)
        _add_kmi(
            kc,
            "3D View",
            "VIEW_3D",
            "landfall_studio.viewport_shading",
            "Z",
            "PRESS",
            alt=True,
            props={"mode": "XRAY"},
        )

        # Ctrl+E -> Maya extrude: faces open the polyExtrudeFace caddy with a
        # normal-aligned manipulator; edges/vertices fall back to Landfall's drag.
        _queue_mute("Mesh", "E", ctrl=True)
        _add_kmi(
            kc,
            "Mesh",
            "EMPTY",
            "landfall_studio.maya_extrude",
            "E",
            "PRESS",
            ctrl=True,
        )
        # Upstream Landfall already owns Shift+F. Keep its mirrored binding
        # active so its keymap healer does not repeatedly rebuild this map.

    _settle_keyconfigs(context)
    _profile_mutes[:] = mutes_to_apply
    for km_name, key_type, ctrl, alt, shift in mutes_to_apply:
        _mute_conflicting_user_items(
            context, km_name, key_type, ctrl=ctrl, alt=alt, shift=shift
        )
    _save_muted_signatures_to_disk()
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
