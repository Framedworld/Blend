"""Bridge for loading and lifecycle-managing pinned upstream Landfall without copying."""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType
from typing import Callable, Dict, Optional

from ..bootstrap.paths import resolve_upstream_paths

_landfall_module: Optional[ModuleType] = None
_registered: bool = False
_fallback_prefs: Optional[object] = None


class _FallbackLandfallPrefs:
    """In-memory preferences fallback used when `register()` is called directly via script
    rather than `bpy.ops.preferences.addon_enable(module=...)`."""

    def __init__(self, default_tree: str = ""):
        self.project_root = ""
        self.tree = default_tree
        self.maya_selection = True
        self.wire_follows_mode = True
        self.maya_edit_wire = True
        self.maya_highlight = True
        self.write_workspace_mel = True
        self.set_render_path = True
        self.add_asset_library = True
        self.keys_in_labels = False
        self.theme_backup = ""
        self.show_transform_hint = True
        self.backspace_deletes = True
        self.chain_after_edit = True
        self.marking_menu = True
        self.maya_extrude = True
        self.keys_pick_gizmo = True
        self.gizmo_keys_only = True
        self.heal_keymaps = True
        self.maya_gizmos = True
        self.gizmo_flags = [True, False, False]
        self.colors_wanted = True
        self.maya_navigation = True
        # Studio extension properties
        self.upstream_root = ""
        self.deps_dir = ""
        self.enable_tentacle = True
        self.tentacle_key = "Z"
        self.auto_restore_script_console = False
        self.interaction_profile = "MAYA"


def get_module() -> Optional[ModuleType]:
    """Return the loaded upstream `landfall` module, if any."""
    return _landfall_module


def is_registered() -> bool:
    """Return True if upstream Landfall is currently registered."""
    return _registered


def load_upstream_landfall(
    addon_package: str,
    custom_upstream_root: Optional[str] = None,
    prefs_draw_hook: Optional[Callable] = None,
) -> ModuleType:
    """Load the pinned `landfall/__init__.py` module and bind its package ID."""
    global _landfall_module, _fallback_prefs

    if _landfall_module is not None:
        return _landfall_module

    resolved = resolve_upstream_paths(custom_upstream_root)["landfall"]
    if not resolved["exists"]:
        raise FileNotFoundError(
            f"Pinned Landfall checkout not found at {resolved['init_file']}"
        )

    init_file = str(resolved["init_file"])
    mod_name = f"{addon_package}._upstream_landfall"
    spec = importlib.util.spec_from_file_location(mod_name, init_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create module spec for {init_file}")

    module = importlib.util.module_from_spec(spec)
    module.__package__ = addon_package
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)

    # Ensure LANDFALL_Prefs uses the unified addon package bl_idname
    if hasattr(module, "LANDFALL_Prefs"):
        import bpy

        prefs_cls = module.LANDFALL_Prefs
        prefs_cls.bl_idname = addon_package
        annotations = getattr(prefs_cls, "__annotations__", {})
        annotations["upstream_root"] = bpy.props.StringProperty(
            name="Upstream Repos Root",
            description="Directory containing pinned checkouts of landfall, tentacle, blendertk, pythontk, and uitk",
            subtype="DIR_PATH",
            default="",
        )
        annotations["deps_dir"] = bpy.props.StringProperty(
            name="Qt / Python Dependencies Folder",
            description="Isolated directory where PySide6, qtpy, and Pillow are installed",
            subtype="DIR_PATH",
            default="",
        )
        annotations["enable_tentacle"] = bpy.props.BoolProperty(
            name="Enable Tentacle Qt Host & Marking Menu",
            description="Initialize the Tentacle Qt event loop and marking menu when Qt dependencies are available",
            default=True,
        )
        annotations["tentacle_key"] = bpy.props.StringProperty(
            name="Tentacle Activation Key (Hybrid Mode)",
            description="Activation key for Tentacle marking menu in Hybrid mode (Maya mode uses Space)",
            default="Z",
        )
        annotations["auto_restore_script_console"] = bpy.props.BoolProperty(
            name="Auto-Restore blendertk Script Output Console",
            description="Automatically restore the docked Qt Script Output console on startup",
            default=False,
        )
        annotations["interaction_profile"] = bpy.props.EnumProperty(
            name="Interaction Profile",
            description="Choose between full Maya interaction profile and Hybrid Blender/Maya profile",
            items=(
                ("MAYA", "Maya", "Full Maya muscle-memory profile (Q/W/E/R, 1/2/3, Space hotbox, RMB/Shift+RMB/Ctrl+RMB menus)"),
                ("HYBRID", "Hybrid", "Landfall/Blender hybrid profile (G/R/S gizmos, Alt+1/2/3 smooth, Ctrl+Tab menu, Z hotbox)"),
            ),
            default="MAYA",
        )
        prefs_cls.__annotations__ = annotations

        if prefs_draw_hook is not None and not getattr(prefs_cls, "_studio_draw_wrapped", False):
            orig_draw = prefs_cls.draw

            def _wrapped_draw(self, context):
                prefs_draw_hook(self, context)
                self.layout.separator()
                orig_draw(self, context)

            prefs_cls.draw = _wrapped_draw
            prefs_cls._studio_draw_wrapped = True

    default_tree = getattr(module, "DEFAULT_TREE", "")
    _fallback_prefs = _FallbackLandfallPrefs(default_tree=default_tree)

    orig_prefs_fn = module.prefs

    def _studio_prefs(context):
        res = orig_prefs_fn(context)
        if res is not None:
            return res
        return _fallback_prefs

    module.prefs = _studio_prefs

    # Wrap _apply_project so Landfall project changes sync to blendertk
    if hasattr(module, "_apply_project"):
        orig_apply_project = module._apply_project

        def _wrapped_apply_project(context, root):
            orig_apply_project(context, root)
            try:
                from . import workspace_bridge

                workspace_bridge.sync_from_landfall(root)
            except Exception:
                pass

        module._apply_project = _wrapped_apply_project

    # Wrap _reapply_mutes so any keymap heal pass preserves the active Studio interaction profile
    if hasattr(module, "_reapply_mutes"):
        orig_reapply_mutes = module._reapply_mutes

        def _wrapped_reapply_mutes():
            orig_reapply_mutes()
            try:
                import bpy
                from .. import keymaps

                if _registered:
                    keymaps.apply_profile(bpy.context, keymaps.get_active_profile())
            except Exception:
                pass

        module._reapply_mutes = _wrapped_reapply_mutes

    _landfall_module = module
    return module


_suspended_standalone_module: Optional[str] = None
_addon_package_for_recheck: str = ""


def _suspend_standalone_landfall(addon_package: str) -> Optional[str]:
    """Suspend an enabled standalone Landfall add-on in memory only, so its classes, keymaps and timers
    don't run twice. It stays enabled in Preferences, and `_resume_standalone_landfall` re-registers it."""
    global _suspended_standalone_module
    if _suspended_standalone_module is not None:
        return _suspended_standalone_module
    conflict = _detect_standalone_landfall_conflict(addon_package)
    if not conflict["conflict"]:
        return None
    mod_name = str(conflict["standalone_module"] or "")
    standalone = sys.modules.get(mod_name)
    if standalone is None or not hasattr(standalone, "unregister"):
        print(f"[landfall_studio] Standalone Landfall '{mod_name}' is active but could not be suspended.")
        return None

    prefs_obj = None
    was_dirty = False
    try:
        import bpy

        prefs_obj = getattr(bpy.context, "preferences", None)
        was_dirty = bool(getattr(prefs_obj, "is_dirty", False)) if prefs_obj is not None else False
    except Exception:
        pass
    try:
        standalone.unregister()
        _suspended_standalone_module = mod_name
        print(f"[landfall_studio] Suspended standalone Landfall '{mod_name}' for this session (still enabled in Preferences).")
    except Exception as exc:
        print(f"[landfall_studio] Could not suspend standalone Landfall '{mod_name}': {exc}")
    finally:
        if prefs_obj is not None:
            try:
                prefs_obj.is_dirty = was_dirty
            except Exception:
                pass
    return _suspended_standalone_module


def _resume_standalone_landfall() -> None:
    """Re-register a standalone Landfall add-on suspended by Studio, if the user still has it enabled."""
    global _suspended_standalone_module
    mod_name = _suspended_standalone_module
    _suspended_standalone_module = None
    if not mod_name:
        return
    try:
        import bpy

        still_enabled = mod_name in getattr(bpy.context.preferences, "addons", {})
        standalone = sys.modules.get(mod_name)
        if still_enabled and standalone is not None and hasattr(standalone, "register"):
            standalone.register()
    except Exception as exc:
        print(f"[landfall_studio] Could not resume standalone Landfall '{mod_name}': {exc}")


def _deferred_standalone_recheck():
    """If the standalone add-on registered after Studio at startup, suspend it and re-register Studio's
    Landfall so Studio's classes (replaced by the standalone's identical bl_idnames) are live again."""
    if not _registered or _landfall_module is None or _suspended_standalone_module is not None:
        return None
    if _suspend_standalone_landfall(_addon_package_for_recheck) is not None:
        try:
            _landfall_module.unregister()
        except Exception:
            pass
        try:
            _landfall_module.register()
        except Exception as exc:
            print(f"[landfall_studio] Re-registering Studio Landfall after standalone suspend failed: {exc}")
    return None


def _detect_standalone_landfall_conflict(addon_package: str) -> Dict[str, object]:
    """Detect if the standalone Landfall add-on is simultaneously enabled in Blender."""
    try:
        import bpy

        prefs = getattr(bpy.context, "preferences", None)
        addons = getattr(prefs, "addons", {}) if prefs is not None else {}
        for mod_key in list(addons.keys()):
            if mod_key != addon_package and (
                mod_key == "landfall" or mod_key.endswith(".landfall")
            ):
                return {"conflict": True, "standalone_module": mod_key}
        if hasattr(bpy.types, "LANDFALL_OT_smooth_preview"):
            cls = getattr(bpy.types, "LANDFALL_OT_smooth_preview")
            mod_str = getattr(cls, "__module__", "")
            if mod_str and not mod_str.startswith(addon_package):
                return {"conflict": True, "standalone_module": mod_str}
    except Exception:
        pass
    return {"conflict": False, "standalone_module": None}


def register(
    addon_package: str,
    custom_upstream_root: Optional[str] = None,
    prefs_draw_hook: Optional[Callable] = None,
) -> bool:
    """Register the upstream Landfall viewport, theme, overlays, and operators (guarded against standalone Landfall coexistence)."""
    global _registered, _addon_package_for_recheck
    if _registered:
        return True

    _suspend_standalone_landfall(addon_package)

    module = load_upstream_landfall(
        addon_package=addon_package,
        custom_upstream_root=custom_upstream_root,
        prefs_draw_hook=prefs_draw_hook,
    )

    was_dirty = False
    prefs_obj = None
    try:
        import bpy

        prefs_obj = getattr(bpy.context, "preferences", None)
        if prefs_obj is not None:
            was_dirty = bool(getattr(prefs_obj, "is_dirty", False))
    except Exception:
        pass

    module.register()

    if prefs_obj is not None:
        try:
            prefs_obj.is_dirty = was_dirty
        except Exception:
            pass

    _registered = True
    _addon_package_for_recheck = addon_package
    try:
        import bpy

        # The standalone add-on may register after Studio at startup; re-check once everything is loaded
        if not bpy.app.timers.is_registered(_deferred_standalone_recheck):
            bpy.app.timers.register(_deferred_standalone_recheck, first_interval=0.5)
    except Exception:
        pass
    return True


def sync_now() -> None:
    """Run Landfall's deferred viewport/theme/grid sync immediately if registered (without dirtying preferences)."""
    if _landfall_module is not None and _registered:
        was_dirty = False
        prefs_obj = None
        try:
            import bpy

            prefs_obj = getattr(bpy.context, "preferences", None)
            if prefs_obj is not None:
                was_dirty = bool(getattr(prefs_obj, "is_dirty", False))
            if hasattr(_landfall_module, "_deferred_sync"):
                _landfall_module._deferred_sync()
        except Exception:
            pass
        finally:
            if prefs_obj is not None:
                try:
                    prefs_obj.is_dirty = was_dirty
                except Exception:
                    pass


def unregister() -> None:
    """Unregister upstream Landfall and guarantee zero leftover timers or draw handlers."""
    global _registered
    if not _registered or _landfall_module is None:
        return
    was_dirty = False
    prefs_obj = None
    try:
        import bpy

        prefs_obj = getattr(bpy.context, "preferences", None)
        if prefs_obj is not None:
            was_dirty = bool(getattr(prefs_obj, "is_dirty", False))
    except Exception:
        pass
    try:
        if bpy.app.timers.is_registered(_deferred_standalone_recheck):
            bpy.app.timers.unregister(_deferred_standalone_recheck)
    except Exception:
        pass
    try:
        _landfall_module.unregister()
    finally:
        # Belt-and-suspenders timer & handler verification
        try:
            import bpy

            for fn_name in ("_gizmos_sync", "_keymap_heal", "_deferred_sync"):
                fn = getattr(_landfall_module, fn_name, None)
                if fn is not None and bpy.app.timers.is_registered(fn):
                    bpy.app.timers.unregister(fn)
            if prefs_obj is not None:
                prefs_obj.is_dirty = was_dirty
        except Exception:
            pass
        _registered = False
        _resume_standalone_landfall()
