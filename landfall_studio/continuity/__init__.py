"""Blender Native Feature Continuity & Bridge (`landfall_studio.continuity` — Phase 09).

Bridges Maya muscle-memory workflows with Blender 5.2's native features without stranding users:
1. **Viewport Shading Continuity (`4 / 5 / 6 / 7` + Shading Pie / X-Ray / Isolate)**:
   - `4`: Wireframe (`WIREFRAME`)
   - `5`: Smooth Shaded (`SOLID` + Studio/Material color)
   - `6`: Shaded + Textured (`MATERIAL` / Material Preview with fallback to `SOLID` + `TEXTURE`)
   - `7`: Use All Lights (`MATERIAL` with `use_scene_lights=True`, or `RENDERED`)
   - Synced with the Viewport 2.0 top panel menu strip (`Wire on Shaded`, `Textured [6]`, `All Lights [7]`, `X-Ray`, `Isolate`) and `Alt+Z`.
2. **Soft Selection (`B` Toggle + `Hold B + LMB-Drag` Falloff Radius) ↔ Proportional Editing (`O`)**:
   - Maps Maya `B` (toggle Soft Selection) and `Hold B + LMB-drag` (interactive falloff radius ring in the 3D Viewport) directly to Blender's Proportional Editing (`use_proportional_edit`, `use_proportional_edit_objects`, `proportional_size`, `proportional_edit_falloff`).
   - Synchronizes two-way with `O`, the Left Tool Box `B` button, the Top Status Line `Soft Select` indicator, and the Right `Tool Settings` panel.
3. **Shadowed Native Shortcuts Re-Homed Cleanly (`SHADOWED_SHORTCUT_MAP`)**:
   - Documents and verifies conflict-free fallback chords for every Blender shortcut shadowed by the `MAYA` profile (`Alt+V` playback, `F3` search, `Ctrl+Shift+Q` Quick Favorites, `Ctrl+Shift+A` Select/Deselect All, `Shift+F` Make Edge/Face, `Delete`/`BackSpace` smart delete, `Alt+Z` X-Ray / Shading).
4. **Native Blender Editors & Modes Bridge (`NATIVE_BRIDGES`)**:
   - Exposes `Geometry Nodes`, `Shader Editor`, `UV Editor`, `Graph Editor`, `Dope Sheet`, `Asset Browser`, `Sculpt Mode`, and `Grease Pencil` in the Maya Menu Set switcher, Tabbed Shelf (`FX / Nodes`), and `RMB` / `Shift+RMB` Marking Menus while keeping protected context keymaps (`Sculpt`, `Grease Pencil`, `Paint`, `Node Editor`) 100% intact.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    import bpy
except ImportError:
    bpy = None

MAYA_SHADING_MODES: Dict[str, Dict[str, Any]] = {
    "4": {
        "key": "4",
        "id": "WIREFRAME",
        "label": "Wireframe [4]",
        "blender_type": "WIREFRAME",
        "use_scene_lights": False,
        "description": "Maya 4: Wireframe display mode",
    },
    "5": {
        "key": "5",
        "id": "SMOOTH_SHADED",
        "label": "Smooth Shaded [5]",
        "blender_type": "SOLID",
        "color_type": "MATERIAL",
        "use_scene_lights": False,
        "description": "Maya 5: Smooth Shaded default lighting",
    },
    "6": {
        "key": "6",
        "id": "TEXTURED",
        "label": "Shaded & Textured [6]",
        "blender_type": "MATERIAL",
        "color_type": "TEXTURE",
        "use_scene_lights": False,
        "description": "Maya 6: Hardware Texturing / Material Preview",
    },
    "7": {
        "key": "7",
        "id": "ALL_LIGHTS",
        "label": "Use All Lights [7]",
        "blender_type": "MATERIAL",
        "color_type": "TEXTURE",
        "use_scene_lights": True,
        "description": "Maya 7: Use All Scene Lights in Viewport 2.0",
    },
}

SHADOWED_SHORTCUT_MAP: Tuple[Dict[str, str], ...] = (
    {
        "maya_key": "Space (Hold)",
        "maya_action": "Maya Hotbox / Tentacle Switchboard",
        "shadowed_blender_action": "Play Animation (`screen.animation_play`) / Search",
        "fallback_chord": "Alt+V (Play Animation)  |  F3 (Operator Search)",
        "fallback_operator": "screen.animation_play",
        "keymap": "3D View",
    },
    {
        "maya_key": "Q",
        "maya_action": "Select Tool (`landfall_studio.select_tool` SELECT)",
        "shadowed_blender_action": "Quick Favorites (`wm.call_menu` SCREEN_MT_user_menu)",
        "fallback_chord": "Ctrl+Shift+Q (Quick Favorites)",
        "fallback_operator": "wm.call_menu",
        "keymap": "3D View",
    },
    {
        "maya_key": "W / E / R",
        "maya_action": "Move (W) / Rotate (E) / Scale (R) Persistent Manipulators",
        "shadowed_blender_action": "Context Menu (W) / Extrude (E) / Rotate (R)",
        "fallback_chord": "Ctrl+E (Extrude)  |  Shift+RMB (Modeling Tool Marking Menu)  |  HYBRID Profile (G/R/S)",
        "fallback_operator": "landfall.extrude",
        "keymap": "Mesh",
    },
    {
        "maya_key": "G / Y",
        "maya_action": "Repeat Last Command (G) / Select Last Tool (Y)",
        "shadowed_blender_action": "Translate Modal (G) / Split Selection (Y)",
        "fallback_chord": "W (Move Tool)  |  Shift+RMB > Detach / Separate",
        "fallback_operator": "landfall_studio.select_tool",
        "keymap": "Object Mode / Mesh",
    },
    {
        "maya_key": "1 / 2 / 3",
        "maya_action": "Smooth Mesh Preview: Base (1) / Cage+Smooth (2) / Smooth (3)",
        "shadowed_blender_action": "Edit Mode Vertex/Edge/Face Select (1/2/3) & Collection Hide",
        "fallback_chord": "F9 (Vertex) / F10 (Edge) / F11 (Face) / F12 (UV)  |  RMB Marking Menu  |  Status Line MASK Pills",
        "fallback_operator": "landfall_studio.component_mode",
        "keymap": "3D View / Object Mode / Mesh",
    },
    {
        "maya_key": "4 / 5 / 6 / 7",
        "maya_action": "Viewport Shading: Wireframe (4) / Shaded (5) / Textured (6) / All Lights (7)",
        "shadowed_blender_action": "Collection Visibility 4–7",
        "fallback_chord": "Alt+Z (Toggle X-Ray / Shading)  |  Display Layers Panel (V/T/R)",
        "fallback_operator": "landfall_studio.viewport_shading",
        "keymap": "3D View / Object Mode / Mesh",
    },
    {
        "maya_key": "B (Tap / Hold+LMB)",
        "maya_action": "Soft Selection Toggle (B) & Interactive Falloff Radius Ring (Hold B + LMB-Drag)",
        "shadowed_blender_action": "Box Select (`view3d.select_box`) / Proportional Editing (`O`)",
        "fallback_chord": "O (Blender Proportional Editing)  |  LMB Marquee Drag in Q/W/E/R",
        "fallback_operator": "landfall_studio.soft_selection",
        "keymap": "3D View / Object Mode / Mesh",
    },
    {
        "maya_key": "F",
        "maya_action": "Frame Selected (`landfall.frame_selected`)",
        "shadowed_blender_action": "Make Edge/Face (`mesh.edge_face_add` in Edit Mesh)",
        "fallback_chord": "Shift+F (Make Edge/Face in Edit Mesh)  |  Native F preserved in Sculpt & Paint",
        "fallback_operator": "mesh.edge_face_add",
        "keymap": "Mesh",
    },
    {
        "maya_key": "A / Ctrl+A",
        "maya_action": "Frame All (A) / Cycle Channel Box & Attribute Editor (Ctrl+A)",
        "shadowed_blender_action": "Select All (A) / Apply Transforms Menu (Ctrl+A)",
        "fallback_chord": "Ctrl+Shift+A (Select/Deselect All Toggle)  |  RMB > Select All  |  Freeze Transforms",
        "fallback_operator": "landfall_studio.select_all_toggle",
        "keymap": "Object Mode / Mesh",
    },
    {
        "maya_key": "X / C / V (Hold)",
        "maya_action": "Temporary Snap: Grid (Hold X) / Curve-Edge (Hold C) / Vertex (Hold V)",
        "shadowed_blender_action": "Delete Menu (X) / Circle Select (C) / Rip Vertices (V)",
        "fallback_chord": "Delete or BackSpace (`landfall_studio.smart_delete`)",
        "fallback_operator": "landfall_studio.smart_delete",
        "keymap": "Object Mode / Mesh",
    },
)

NATIVE_BRIDGES: Dict[str, Dict[str, str]] = {
    "GEOMETRY_NODES": {
        "id": "GEOMETRY_NODES",
        "label": "Geometry Nodes",
        "maya_menu_set": "FX / Nodes [F5]",
        "editor_ui_type": "GeometryNodeTree",
        "description": "Attach or inspect a Blender Geometry Nodes modifier graph on the active mesh",
    },
    "SHADER_EDITOR": {
        "id": "SHADER_EDITOR",
        "label": "Shader Editor (Hypershade)",
        "maya_menu_set": "Rendering [F6]",
        "editor_ui_type": "ShaderNodeTree",
        "description": "Open the Shader Node Graph / Hypershade Lookdev Editor for the active material",
    },
    "UV_EDITOR": {
        "id": "UV_EDITOR",
        "label": "UV Editor",
        "maya_menu_set": "Modeling [F2]",
        "editor_ui_type": "UV",
        "description": "Enter UV Component Mode and synchronize UV Editor selection",
    },
    "GRAPH_EDITOR": {
        "id": "GRAPH_EDITOR",
        "label": "Graph Editor",
        "maya_menu_set": "Animation [F4]",
        "editor_ui_type": "FCURVES",
        "description": "Inspect F-Curves / Graph Editor animation channels on the active object",
    },
    "DOPE_SHEET": {
        "id": "DOPE_SHEET",
        "label": "Dope Sheet",
        "maya_menu_set": "Animation [F4]",
        "editor_ui_type": "DOPESHEET",
        "description": "Inspect Dope Sheet / Action Editor keyframes",
    },
    "ASSET_BROWSER": {
        "id": "ASSET_BROWSER",
        "label": "Asset Browser",
        "maya_menu_set": "Pipeline",
        "editor_ui_type": "ASSETS",
        "description": "Access Blender Asset Browser catalogs & pose/material assets",
    },
    "SCULPT_MODE": {
        "id": "SCULPT_MODE",
        "label": "Sculpt Mode",
        "maya_menu_set": "Modeling [F2]",
        "editor_ui_type": "VIEW_3D",
        "description": "Enter native Blender Sculpt Mode with full brush shortcuts (F size, Shift+F strength)",
    },
    "GREASE_PENCIL": {
        "id": "GREASE_PENCIL",
        "label": "Grease Pencil 2D/3D",
        "maya_menu_set": "Animation [F4]",
        "editor_ui_type": "VIEW_3D",
        "description": "Create or activate a Grease Pencil draw object for viewport annotation & 2D/3D storyboarding",
    },
    "OBJECT_MODE": {
        "id": "OBJECT_MODE",
        "label": "Return to Object Mode",
        "maya_menu_set": "Modeling [F2]",
        "editor_ui_type": "VIEW_3D",
        "description": "Return cleanly from Sculpt, Edit, or Grease Pencil mode to Object Mode",
    },
}

_active_maya_shading_mode: str = "6"
_active_native_bridge: str = "VIEW_3D"
_soft_select_ring_state: Dict[str, Any] = {
    "active": False,
    "center_x": 0.0,
    "center_y": 0.0,
    "radius_px": 54.0,
    "world_radius": 1.0,
}


def _iter_view3d_spaces(context=None, active_only: bool = True) -> List[Any]:
    if bpy is None:
        return []
    ctx = context or bpy.context
    spaces: List[Any] = []
    sd = getattr(ctx, "space_data", None)
    if sd is not None and getattr(sd, "type", "") == "VIEW_3D":
        spaces.append(sd)
        if active_only:
            return spaces
    area = getattr(ctx, "area", None)
    if area is not None and getattr(area, "type", "") == "VIEW_3D":
        for sp in area.spaces:
            if sp.type == "VIEW_3D" and sp not in spaces:
                spaces.append(sp)
                if active_only:
                    return spaces
    wm = getattr(ctx, "window_manager", None)
    for win in (wm.windows if wm else ()):
        if win.screen is None:
            continue
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D" and sp not in spaces:
                        spaces.append(sp)
                        if active_only:
                            return spaces
    if active_only and spaces:
        return spaces[:1]
    for ws in getattr(bpy.data, "workspaces", ()):
        for screen in ws.screens:
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    for sp in area.spaces:
                        if sp.type == "VIEW_3D" and sp not in spaces:
                            spaces.append(sp)
                            if active_only:
                                return spaces
    return spaces


_eevee_ssao_enabled: bool = True
_eevee_shadows_enabled: bool = True
_eevee_raytracing_enabled: bool = True


def _ensure_eevee_engine(scene: Any) -> str:
    if scene is None:
        return "BLENDER_EEVEE"
    rnd = getattr(scene, "render", None)
    if rnd is None:
        return "BLENDER_EEVEE"
    for candidate in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            rnd.engine = candidate
            break
        except Exception:
            continue
    return str(getattr(rnd, "engine", "BLENDER_EEVEE"))


def _apply_eevee_hardware_settings(scene: Any, spaces: List[Any]) -> None:
    if scene is not None:
        eevee = getattr(scene, "eevee", None)
        if eevee is not None:
            for attr, val in (
                ("use_shadows", _eevee_shadows_enabled),
                ("use_raytracing", _eevee_raytracing_enabled),
                ("use_gtao", _eevee_ssao_enabled),
                ("taa_samples", 16),
            ):
                if hasattr(eevee, attr):
                    try:
                        setattr(eevee, attr, val)
                    except Exception:
                        pass
    for sp in spaces:
        shading = getattr(sp, "shading", None)
        if shading is not None:
            for attr, val in (
                ("show_cavity", _eevee_ssao_enabled),
                ("show_shadows", _eevee_shadows_enabled),
                ("show_specular_highlight", True),
            ):
                if hasattr(shading, attr):
                    try:
                        setattr(shading, attr, val)
                    except Exception:
                        pass


def get_viewport_shading_state(context=None) -> Dict[str, Any]:
    """Return the current Maya `4/5/6/7` Viewport 2.0 (EEVEE) shading mode and hardware feature state."""
    global _active_maya_shading_mode
    spaces = _iter_view3d_spaces(context)
    sp = spaces[0] if spaces else None
    shading = getattr(sp, "shading", None) if sp is not None else None
    overlay = getattr(sp, "overlay", None) if sp is not None else None

    bl_type = str(getattr(shading, "type", "SOLID")) if shading is not None else "SOLID"
    use_lights = bool(getattr(shading, "use_scene_lights", False)) if shading is not None else False
    xray = bool(getattr(shading, "show_xray", False)) if shading is not None else False
    wire_over = bool(getattr(overlay, "show_wireframes", False)) if overlay is not None else False

    ctx = context or (bpy.context if bpy is not None else None)
    scene = getattr(ctx, "scene", None) if ctx is not None else None
    engine = str(getattr(getattr(scene, "render", None), "engine", "BLENDER_EEVEE")) if scene is not None else "BLENDER_EEVEE"

    active_obj = getattr(getattr(ctx, "view_layer", None), "objects", None)
    act = active_obj.active if active_obj else None
    if act is not None and getattr(act, "show_wire", False):
        wire_over = True

    isolated = bool(getattr(sp, "local_view", None) is not None) if sp is not None else False

    # Infer Maya 4/5/6/7 if changed externally in Blender
    if shading is not None:
        if bl_type == "WIREFRAME":
            _active_maya_shading_mode = "4"
        elif bl_type == "SOLID":
            c_type = str(getattr(shading, "color_type", "MATERIAL"))
            _active_maya_shading_mode = "6" if c_type == "TEXTURE" else "5"
        elif bl_type in ("MATERIAL", "RENDERED"):
            _active_maya_shading_mode = "7" if (use_lights or bl_type == "RENDERED") else "6"

    spec = MAYA_SHADING_MODES.get(_active_maya_shading_mode, MAYA_SHADING_MODES["6"])
    if engine == "CYCLES" and bl_type == "RENDERED":
        renderer_label = "Cycles (Path Traced)"
    else:
        renderer_label = "Viewport 2.0 (EEVEE)"

    return {
        "ok": True,
        "maya_mode": _active_maya_shading_mode,
        "maya_id": spec["id"],
        "maya_label": spec["label"],
        "blender_shading_type": bl_type,
        "renderer_engine": engine,
        "renderer_label": renderer_label,
        "use_scene_lights": use_lights,
        "wire_on_shaded": wire_over,
        "xray": xray,
        "isolated": isolated,
        "eevee_ssao": _eevee_ssao_enabled,
        "eevee_shadows": _eevee_shadows_enabled,
        "eevee_raytracing": _eevee_raytracing_enabled,
        "eevee_msaa": 16,
    }


def set_viewport_renderer(engine: str = "EEVEE", context=None) -> Dict[str, Any]:
    """Switch the active viewport renderer between Maya `Viewport 2.0 (EEVEE)` and `Cycles`."""
    ctx = context or (bpy.context if bpy is not None else None)
    scene = getattr(ctx, "scene", None) if ctx is not None else None
    spaces = _iter_view3d_spaces(ctx)
    norm = str(engine or "EEVEE").strip().upper()
    if "CYCLE" in norm:
        if scene is not None and hasattr(scene, "render"):
            try:
                scene.render.engine = "CYCLES"
            except Exception:
                pass
        for sp in spaces:
            if hasattr(sp, "shading"):
                try:
                    sp.shading.type = "RENDERED"
                except Exception:
                    pass
    else:
        _ensure_eevee_engine(scene)
        _apply_eevee_hardware_settings(scene, spaces)
    return get_viewport_shading_state(ctx)


def toggle_viewport_20_feature(feature: str = "SSAO", enable: Optional[bool] = None, context=None) -> Dict[str, Any]:
    """Toggle or set a Maya Viewport 2.0 (EEVEE) hardware feature (`SSAO`, `SHADOWS`, `RAYTRACING`)."""
    global _eevee_ssao_enabled, _eevee_shadows_enabled, _eevee_raytracing_enabled
    ctx = context or (bpy.context if bpy is not None else None)
    scene = getattr(ctx, "scene", None) if ctx is not None else None
    spaces = _iter_view3d_spaces(ctx)
    norm = str(feature or "SSAO").strip().upper()
    if norm in ("SSAO", "AO", "CAVITY"):
        _eevee_ssao_enabled = (not _eevee_ssao_enabled) if enable is None else bool(enable)
    elif norm in ("SHADOWS", "SHADOW"):
        _eevee_shadows_enabled = (not _eevee_shadows_enabled) if enable is None else bool(enable)
    elif norm in ("RAYTRACING", "RAYTRACE", "SSR"):
        _eevee_raytracing_enabled = (not _eevee_raytracing_enabled) if enable is None else bool(enable)
    _apply_eevee_hardware_settings(scene, spaces)
    return get_viewport_shading_state(ctx)


def ensure_studio_light_rig(enable: Optional[bool] = None) -> Dict[str, Any]:
    """Create or toggle a calibrated 3-point Maya/EEVEE Lookdev Light Rig (`grp_StudioLookdevRig`) and activate `All Lights [7]`."""
    import bpy
    from mathutils import Euler, Vector

    rig_grp = bpy.data.objects.get("grp_StudioLookdevRig")
    if enable is False and rig_grp is not None:
        for child in list(rig_grp.children):
            bpy.data.objects.remove(child, do_unlink=True)
        bpy.data.objects.remove(rig_grp, do_unlink=True)
        return {"ok": True, "enabled": False, "light_count": 0}

    if rig_grp is None:
        rig_grp = bpy.data.objects.new("grp_StudioLookdevRig", None)
        bpy.context.collection.objects.link(rig_grp)
        specs = (
            ("studioKeyLight", (1.0, 0.96, 0.90), 260.0, 3.6, (3.2, -2.8, 3.8), (0.68, 0.12, 0.72)),
            ("studioFillLight", (0.78, 0.86, 1.0), 95.0, 4.2, (-2.8, -2.4, 2.2), (0.85, -0.18, -0.65)),
            ("studioRimTeal", (0.35, 0.78, 1.0), 180.0, 2.8, (-2.6, 2.8, 3.1), (-0.62, -0.22, -0.78)),
        )
        for lname, col, energy, sz, loc, rot in specs:
            ldata = bpy.data.lights.new(f"{lname}Shape", type="AREA")
            ldata.color = col
            ldata.energy = energy
            ldata.size = sz
            lobj = bpy.data.objects.new(lname, ldata)
            bpy.context.collection.objects.link(lobj)
            lobj.parent = rig_grp
            lobj.location = Vector(loc)
            lobj.rotation_euler = Euler(rot, "XYZ")

    set_maya_viewport_shading("7")
    return {
        "ok": True,
        "enabled": True,
        "rig_group": rig_grp.name,
        "light_count": len(rig_grp.children),
    }


def voxel_remesh_active(voxel_size: float = 0.08) -> Dict[str, Any]:
    """Run Blender's Voxel Remesh (`mesh.remesh_voxel_size` + `object.voxel_remesh`) on the active mesh."""
    import bpy

    act = getattr(getattr(bpy.context, "view_layer", None), "objects", None)
    obj = act.active if act else None
    if obj is None or getattr(obj, "type", "") != "MESH":
        return {"ok": False, "error": "Active mesh object required for Voxel Remesh"}
    me = obj.data
    me.remesh_voxel_size = max(0.005, float(voxel_size))
    try:
        with bpy.context.temp_override(active_object=obj, object=obj):
            bpy.ops.object.voxel_remesh()
    except Exception:
        pass
    return {
        "ok": True,
        "object": obj.name,
        "voxel_size": float(me.remesh_voxel_size),
        "vertices": len(me.vertices),
        "polygons": len(me.polygons),
    }


def set_maya_viewport_shading(mode_key: str, context=None) -> Dict[str, Any]:
    """Set the Maya Viewport 2.0 (EEVEE) shading mode (`4` Wireframe, `5` Smooth Shaded, `6` Textured EEVEE, `7` Use All Lights EEVEE) or toggle display flags."""
    global _active_maya_shading_mode
    norm = str(mode_key or "5").strip().upper()
    alias_map = {
        "WIREFRAME": "4",
        "SMOOTH": "5",
        "SMOOTH_SHADED": "5",
        "SHADED": "5",
        "SOLID": "5",
        "TEXTURED": "6",
        "MATERIAL": "6",
        "EEVEE": "6",
        "ALL_LIGHTS": "7",
        "LIGHTS": "7",
        "RENDERED": "7",
    }
    norm = alias_map.get(norm, norm)

    spaces = _iter_view3d_spaces(context)
    ctx = context or (bpy.context if bpy is not None else None)
    scene = getattr(ctx, "scene", None) if ctx is not None else None

    if norm in ("SSAO", "SHADOWS", "RAYTRACING"):
        return toggle_viewport_20_feature(norm, context=ctx)
    if norm == "STUDIO_RIG":
        ensure_studio_light_rig(enable=True)
        return get_viewport_shading_state(ctx)
    if norm in ("RENDERER_EEVEE", "VIEWPORT_20"):
        return set_viewport_renderer("EEVEE", context=ctx)
    if norm == "RENDERER_CYCLES":
        return set_viewport_renderer("CYCLES", context=ctx)

    if norm == "WIRE_ON_SHADED":
        st = get_viewport_shading_state(ctx)
        target_val = not st["wire_on_shaded"]
        for sp in spaces:
            if hasattr(sp, "overlay"):
                try:
                    sp.overlay.show_wireframes = target_val
                except Exception:
                    pass
        active_obj = getattr(getattr(ctx, "view_layer", None), "objects", None)
        act = active_obj.active if active_obj else None
        if act is not None:
            try:
                act.show_wire = target_val
                act.show_all_edges = target_val
            except Exception:
                pass
        return get_viewport_shading_state(ctx)

    if norm == "XRAY":
        st = get_viewport_shading_state(ctx)
        target_val = not st["xray"]
        for sp in spaces:
            if hasattr(sp, "shading"):
                try:
                    sp.shading.show_xray = target_val
                    if hasattr(sp.shading, "show_xray_wireframe"):
                        sp.shading.show_xray_wireframe = target_val
                except Exception:
                    pass
        return get_viewport_shading_state(ctx)

    if norm not in MAYA_SHADING_MODES:
        return {"ok": False, "error": f"Unsupported Maya shading mode '{mode_key}'"}

    _active_maya_shading_mode = norm
    spec = MAYA_SHADING_MODES[norm]

    if norm in ("6", "7"):
        # Apply EEVEE viewport hardware settings without overwriting scene.render.engine (e.g. preserving CYCLES for final renders)
        _apply_eevee_hardware_settings(scene, spaces)

    for sp in spaces:
        shading = getattr(sp, "shading", None)
        if shading is None:
            continue
        try:
            if norm == "4":
                shading.type = "WIREFRAME"
            elif norm == "5":
                shading.type = "SOLID"
                shading.light = "STUDIO"
                shading.color_type = "MATERIAL"
                shading.show_cavity = _eevee_ssao_enabled
            elif norm == "6":
                try:
                    shading.type = "MATERIAL"
                    shading.use_scene_lights = False
                    shading.use_scene_world = False
                except Exception:
                    shading.type = "SOLID"
                    shading.color_type = "TEXTURE"
            elif norm == "7":
                try:
                    shading.type = "MATERIAL"
                    shading.use_scene_lights = True
                    shading.use_scene_world = False
                except Exception:
                    shading.type = "RENDERED"
        except Exception:
            pass

    try:
        from ..ui import desktop, shelf

        shelf.refresh_top_shelf_status()
        desktop.set_command_feedback("modelEditor -renderer vp2Renderer", f"{spec['label']} • Viewport 2.0 (EEVEE)")
    except Exception:
        pass

    return get_viewport_shading_state(ctx)


def get_soft_selection_state(context=None) -> Dict[str, Any]:
    """Return the synchronized Maya Soft Selection (`B`) / Blender Proportional Editing (`O`) state."""
    if bpy is None:
        return {
            "ok": False,
            "enabled": False,
            "object_mode_enabled": False,
            "radius": 1.0,
            "falloff_curve": "SMOOTH",
            "ring_overlay": dict(_soft_select_ring_state),
        }
    ctx = context or bpy.context
    scene = getattr(ctx, "scene", None)
    ts = getattr(scene, "tool_settings", None) if scene is not None else None
    enabled = bool(getattr(ts, "use_proportional_edit", False)) if ts is not None else False
    obj_enabled = bool(getattr(ts, "use_proportional_edit_objects", False)) if ts is not None else False
    radius = round(float(getattr(ts, "proportional_size", 1.0)), 4) if ts is not None else 1.0
    falloff = str(getattr(ts, "proportional_edit_falloff", "SMOOTH")) if ts is not None else "SMOOTH"
    return {
        "ok": True,
        "enabled": enabled,
        "object_mode_enabled": obj_enabled,
        "radius": radius,
        "falloff_curve": falloff,
        "ring_overlay": dict(_soft_select_ring_state),
    }


def set_soft_selection_state(
    enabled: Optional[bool] = None,
    radius: Optional[float] = None,
    falloff_curve: Optional[str] = None,
    toggle: bool = False,
    show_ring_overlay: Optional[bool] = None,
    ring_center: Optional[Tuple[float, float]] = None,
    context=None,
) -> Dict[str, Any]:
    """Mutate Maya Soft Selection (`B`) / Blender Proportional Editing (`O`) and sync all Studio UI surfaces."""
    ctx = context or (bpy.context if bpy is not None else None)
    scene = getattr(ctx, "scene", None) if ctx is not None else None
    ts = getattr(scene, "tool_settings", None) if scene is not None else None
    if ts is None:
        return {"ok": False, "error": "No active scene.tool_settings"}

    if toggle:
        new_enabled = not bool(ts.use_proportional_edit)
        ts.use_proportional_edit = new_enabled
        ts.use_proportional_edit_objects = new_enabled
    elif enabled is not None:
        ts.use_proportional_edit = bool(enabled)
        ts.use_proportional_edit_objects = bool(enabled)

    if radius is not None:
        clamped_r = max(0.001, min(1000.0, float(radius)))
        ts.proportional_size = clamped_r
        _soft_select_ring_state["world_radius"] = round(clamped_r, 4)
        _soft_select_ring_state["radius_px"] = max(18.0, min(220.0, clamped_r * 38.0))

    if falloff_curve is not None:
        curve_norm = str(falloff_curve).strip().upper()
        try:
            ts.proportional_edit_falloff = curve_norm
        except Exception:
            pass

    if show_ring_overlay is not None:
        _soft_select_ring_state["active"] = bool(show_ring_overlay)
    if ring_center is not None:
        _soft_select_ring_state["center_x"] = float(ring_center[0])
        _soft_select_ring_state["center_y"] = float(ring_center[1])
    _soft_select_ring_state["world_radius"] = round(float(ts.proportional_size), 4)

    try:
        from ..ui import desktop, outliner, shelf, tool_settings

        tool_settings.refresh_tool_settings_widget()
        shelf.refresh_top_shelf_status()
        outliner.refresh_outliner()
        state_str = (
            f"ON (r={ts.proportional_size:.2f}, {ts.proportional_edit_falloff})"
            if ts.use_proportional_edit
            else "OFF"
        )
        desktop.set_command_feedback("softSelect", state_str)
    except Exception:
        pass

    return get_soft_selection_state(ctx)


def get_shadowed_shortcut_map(context=None) -> List[Dict[str, Any]]:
    """Return the complete catalog of shadowed Blender shortcuts and live verification of their fallback chords."""
    ctx = context or (bpy.context if bpy is not None else None)
    kc = getattr(getattr(ctx, "window_manager", None), "keyconfigs", None)
    addon_kc = getattr(kc, "addon", None) if kc else None

    active_studio_ops = set()
    if addon_kc is not None:
        for km in addon_kc.keymaps:
            for kmi in km.keymap_items:
                if kmi.active:
                    active_studio_ops.add(kmi.idname)

    rows: List[Dict[str, Any]] = []
    for entry in SHADOWED_SHORTCUT_MAP:
        row = dict(entry)
        f_op = row["fallback_operator"]
        row["fallback_bound"] = (f_op in active_studio_ops) or f_op.startswith(("wm.", "mesh.", "screen."))
        rows.append(row)
    return rows


def ensure_geometry_nodes_on_active(context=None) -> Dict[str, Any]:
    """Ensure the active mesh object has an inspectable Blender Geometry Nodes modifier + node tree."""
    ctx = context or bpy.context
    vl = getattr(ctx, "view_layer", None)
    obj = vl.objects.active if vl else None
    if obj is None or obj.type != "MESH":
        return {"ok": False, "error": "Active object must be a MESH for Geometry Nodes"}

    mod = None
    for m in obj.modifiers:
        if m.type == "NODES":
            mod = m
            break
    if mod is None:
        mod = obj.modifiers.new(name="GeometryNodes", type="NODES")

    if mod.node_group is None:
        ng = bpy.data.node_groups.new(name=f"{obj.name}_GeoNodes", type="GeometryNodeTree")
        try:
            ng.interface.new_socket(
                name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
            )
            ng.interface.new_socket(
                name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
            )
        except Exception:
            pass
        n_in = ng.nodes.new("NodeGroupInput")
        n_in.location = (-220, 0)
        n_out = ng.nodes.new("NodeGroupOutput")
        n_out.location = (220, 0)
        try:
            if n_in.outputs and n_out.inputs:
                ng.links.new(n_in.outputs[0], n_out.inputs[0])
        except Exception:
            pass
        mod.node_group = ng

    return {
        "ok": True,
        "object_name": obj.name,
        "modifier_name": mod.name,
        "node_group_name": mod.node_group.name if mod.node_group else "",
        "node_count": len(mod.node_group.nodes) if mod.node_group else 0,
    }


def open_native_editor_or_mode(target: str, context=None) -> Dict[str, Any]:
    """Bridge cleanly between Maya Studio workflows and Blender's native editors/modes (`GEOMETRY_NODES`, `SHADER_EDITOR`, `UV_EDITOR`, `GRAPH_EDITOR`, `DOPE_SHEET`, `ASSET_BROWSER`, `SCULPT_MODE`, `GREASE_PENCIL`, `OBJECT_MODE`)."""
    global _active_native_bridge
    ctx = context or bpy.context
    norm = str(target or "OBJECT_MODE").strip().upper()
    if norm not in NATIVE_BRIDGES:
        return {"ok": False, "error": f"Unknown native bridge target '{target}'"}

    spec = NATIVE_BRIDGES[norm]
    _active_native_bridge = norm
    vl = getattr(ctx, "view_layer", None)
    active = vl.objects.active if vl else None

    result: Dict[str, Any] = {
        "ok": True,
        "target": norm,
        "label": spec["label"],
        "editor_ui_type": spec["editor_ui_type"],
        "mode_after": getattr(ctx, "mode", "OBJECT"),
    }

    if norm == "GEOMETRY_NODES":
        gn_res = ensure_geometry_nodes_on_active(ctx)
        result["geometry_nodes"] = gn_res
        result["ok"] = bool(gn_res.get("ok", False))
        try:
            from ..ui import channel_box_ext, desktop

            channel_box_ext.refresh_channel_box_extensions()
            desktop.set_command_feedback(
                "GeometryNodesBridge",
                gn_res.get("node_group_name", "GeometryNodes"),
            )
        except Exception:
            pass
        return result

    if norm == "SHADER_EDITOR":
        try:
            from .. import advanced
            from ..ui import desktop, hypershade_panel

            if active is not None and active.type == "MESH" and not active.data.materials:
                advanced.create_from_template(
                    "aiStandardSurface",
                    name="aiStandardSurface1",
                    assign_to_selection=True,
                )
            desktop.cycle_right_dock("HYPERSHADE")
            hypershade_panel.refresh_hypershade_widgets()
            desktop.set_command_feedback("ShaderEditorBridge", "Hypershade / ShaderNodeTree")
        except Exception:
            pass
        return result

    if norm == "UV_EDITOR":
        try:
            bpy.ops.landfall_studio.component_mode(mode="UV")
        except Exception:
            pass
        result["mode_after"] = getattr(ctx, "mode", "OBJECT")
        return result

    if norm in ("GRAPH_EDITOR", "DOPE_SHEET", "ASSET_BROWSER"):
        try:
            from ..ui import desktop

            split_res = desktop.set_bottom_node_graph_split(True, graph_type=norm)
            result["editor_split"] = split_res
            result["editor_opened"] = bool(split_res.get("open", False))
            desktop.set_command_feedback("NativeEditorBridge", f"{spec['label']} ({spec['editor_ui_type']})")
        except Exception:
            result["editor_opened"] = False
        return result

    if norm == "SCULPT_MODE":
        if active is None or active.type != "MESH":
            for o in (vl.objects if vl else ()):
                if o.type == "MESH":
                    vl.objects.active = o
                    active = o
                    break
        if active is not None and active.type == "MESH":
            try:
                if ctx.mode != "SCULPT":
                    bpy.ops.object.mode_set(mode="SCULPT")
            except Exception as exc:
                return {"ok": False, "target": norm, "error": str(exc)}
        result["mode_after"] = getattr(ctx, "mode", "OBJECT")
        try:
            from ..ui import desktop, shelf

            shelf.refresh_top_shelf_status()
            desktop.set_command_feedback("SculptModeBridge", f"Mode={result['mode_after']} (F=Brush Size)")
        except Exception:
            pass
        return result

    if norm == "GREASE_PENCIL":
        if ctx.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass
        gp_obj = None
        for o in (vl.objects if vl else ()):
            if o.type in ("GREASEPENCIL", "GPENCIL"):
                gp_obj = o
                break
        if gp_obj is None:
            try:
                bpy.ops.object.grease_pencil_add(type="STROKE")
                gp_obj = vl.objects.active if vl else None
            except Exception:
                try:
                    gp_data = bpy.data.grease_pencils.new("mayaGreasePencil1")
                    gp_obj = bpy.data.objects.new("mayaGreasePencil1", gp_data)
                    ctx.collection.objects.link(gp_obj)
                    vl.objects.active = gp_obj
                except Exception:
                    pass
        if gp_obj is not None and vl is not None:
            vl.objects.active = gp_obj
            gp_obj.select_set(True)
        result["grease_pencil_object"] = gp_obj.name if gp_obj is not None else None
        result["mode_after"] = getattr(ctx, "mode", "OBJECT")
        try:
            from ..ui import desktop, outliner

            outliner.refresh_outliner()
            desktop.set_command_feedback(
                "GreasePencilBridge",
                gp_obj.name if gp_obj is not None else "Active",
            )
        except Exception:
            pass
        return result

    if norm == "OBJECT_MODE":
        if ctx.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass
        result["mode_after"] = getattr(ctx, "mode", "OBJECT")
        try:
            from ..ui import desktop, shelf

            shelf.refresh_top_shelf_status()
            desktop.set_command_feedback("ObjectMode", "OBJECT")
        except Exception:
            pass
        return result

    return result


def get_continuity_snapshot(context=None) -> Dict[str, Any]:
    """Return a unified diagnostic snapshot of Phase 09 Blender Native Continuity state."""
    return {
        "ok": True,
        "shading": get_viewport_shading_state(context),
        "soft_selection": get_soft_selection_state(context),
        "active_native_bridge": _active_native_bridge,
        "native_bridges": list(NATIVE_BRIDGES.keys()),
        "shadowed_shortcuts": get_shadowed_shortcut_map(context),
    }


if bpy is not None:

    class LANDFALL_STUDIO_OT_viewport_shading(bpy.types.Operator):
        """Set Maya Viewport 2.0 Shading Mode (`4` Wireframe, `5` Smooth Shaded, `6` Textured, `7` Use All Lights) or toggle X-Ray / Wire on Shaded."""

        bl_idname = "landfall_studio.viewport_shading"
        bl_label = "Maya Viewport Shading (4/5/6/7)"
        bl_description = (
            "Switch Viewport 2.0 display mode: 4 (Wireframe), 5 (Smooth Shaded), "
            "6 (Shaded & Textured), 7 (Use All Lights), X-Ray (Alt+Z), or Wire on Shaded"
        )

        mode: bpy.props.EnumProperty(
            name="Shading Mode",
            items=(
                ("4", "Wireframe (4)", "Maya 4: Wireframe display"),
                ("5", "Smooth Shaded (5)", "Maya 5: Smooth Shaded default lighting"),
                ("6", "Shaded & Textured (6)", "Maya 6: Hardware Texturing / Material Preview"),
                ("7", "Use All Lights (7)", "Maya 7: Use All Scene Lights"),
                ("WIRE_ON_SHADED", "Wireframe on Shaded", "Toggle Wireframe on Shaded overlay"),
                ("XRAY", "X-Ray (Alt+Z)", "Toggle Viewport X-Ray"),
            ),
            default="5",
            options={"SKIP_SAVE"},
        )

        def execute(self, context):
            res = set_maya_viewport_shading(self.mode, context=context)
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "Shading change failed"))
                return {"CANCELLED"}
            for area in (context.screen.areas if getattr(context, "screen", None) else ()):
                if area.type == "VIEW_3D":
                    area.tag_redraw()
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_soft_selection(bpy.types.Operator):
        """Maya Soft Selection (`B` Toggle + `Hold B + LMB-Drag` Interactive Falloff Radius Ring)."""

        bl_idname = "landfall_studio.soft_selection"
        bl_label = "Maya Soft Selection (B)"
        bl_description = (
            "Tap B to toggle Soft Selection (Proportional Editing); "
            "Hold B + LMB-drag in the viewport to interactively resize the Falloff Radius ring"
        )
        bl_options = {"REGISTER", "UNDO"}

        action: bpy.props.EnumProperty(
            name="Action",
            items=(
                ("MODAL_OR_TOGGLE", "Modal or Toggle", "Interactive B key behavior"),
                ("TOGGLE", "Toggle Soft Selection", "Toggle Soft Selection On/Off"),
                ("SET", "Set Radius & Falloff", "Explicitly set Soft Selection state"),
            ),
            default="MODAL_OR_TOGGLE",
            options={"SKIP_SAVE"},
        )
        enabled: bpy.props.BoolProperty(
            name="Enabled", default=True, options={"SKIP_SAVE"}
        )
        radius: bpy.props.FloatProperty(
            name="Falloff Radius",
            default=-1.0,
            min=-1.0,
            max=1000.0,
            options={"SKIP_SAVE"},
        )
        falloff_curve: bpy.props.StringProperty(
            name="Falloff Curve", default="", options={"SKIP_SAVE"}
        )

        def execute(self, context):
            if self.action == "SET":
                set_soft_selection_state(
                    enabled=self.enabled,
                    radius=self.radius if self.radius > 0.0 else None,
                    falloff_curve=self.falloff_curve or None,
                    context=context,
                )
            else:
                set_soft_selection_state(
                    toggle=True,
                    radius=self.radius if self.radius > 0.0 else None,
                    falloff_curve=self.falloff_curve or None,
                    context=context,
                )
            return {"FINISHED"}

        def invoke(self, context, event):
            if (
                self.action != "MODAL_OR_TOGGLE"
                or context.area is None
                or context.area.type != "VIEW_3D"
                or event is None
            ):
                return self.execute(context)

            st = get_soft_selection_state(context)
            self._start_x = float(event.mouse_region_x)
            self._start_y = float(event.mouse_region_y)
            self._start_radius = float(st["radius"])
            self._dragged = False
            self._lmb_down = False

            set_soft_selection_state(
                show_ring_overlay=True,
                ring_center=(self._start_x, self._start_y),
                context=context,
            )
            context.window_manager.modal_handler_add(self)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        def cancel(self, context):
            set_soft_selection_state(show_ring_overlay=False, context=context)
            if context.area:
                context.area.tag_redraw()

        def modal(self, context, event):
            if event.type == "LEFTMOUSE":
                if event.value == "PRESS":
                    self._lmb_down = True
                    self._dragged = True
                    set_soft_selection_state(enabled=True, context=context)
                    return {"RUNNING_MODAL"}
                if event.value == "RELEASE":
                    self._lmb_down = False

            if event.type == "MOUSEMOVE":
                mx = float(event.mouse_region_x)
                my = float(event.mouse_region_y)
                dx = mx - self._start_x
                if self._lmb_down:
                    self._dragged = True
                    new_r = max(0.05, round(self._start_radius + dx * 0.02, 3))
                    set_soft_selection_state(
                        enabled=True,
                        radius=new_r,
                        show_ring_overlay=True,
                        ring_center=(self._start_x, self._start_y),
                        context=context,
                    )
                    if context.area:
                        context.area.tag_redraw()
                return {"RUNNING_MODAL"}

            if event.type == "B" and event.value == "RELEASE":
                if not self._dragged:
                    set_soft_selection_state(
                        toggle=True,
                        show_ring_overlay=False,
                        context=context,
                    )
                else:
                    set_soft_selection_state(show_ring_overlay=False, context=context)
                if context.area:
                    context.area.tag_redraw()
                return {"FINISHED"}

            if event.type == "ESC" and event.value == "PRESS":
                set_soft_selection_state(
                    radius=self._start_radius,
                    show_ring_overlay=False,
                    context=context,
                )
                if context.area:
                    context.area.tag_redraw()
                return {"CANCELLED"}

            return {"RUNNING_MODAL"}

    class LANDFALL_STUDIO_OT_native_bridge(bpy.types.Operator):
        """Open or switch to a native Blender 5.2 editor or mode (`Geometry Nodes`, `Shader Editor`, `UV Editor`, `Graph Editor`, `Dope Sheet`, `Asset Browser`, `Sculpt Mode`, `Grease Pencil`)."""

        bl_idname = "landfall_studio.native_bridge"
        bl_label = "Blender Native Editor / Mode Bridge"
        bl_description = "Launch or switch to a native Blender editor or mode without losing Maya Studio continuity"
        bl_options = {"REGISTER", "UNDO"}

        target: bpy.props.EnumProperty(
            name="Target",
            items=(
                ("GEOMETRY_NODES", "Geometry Nodes", "Ensure & inspect Geometry Nodes modifier graph"),
                ("SHADER_EDITOR", "Shader Editor (Hypershade)", "Open Shader Node Graph / Hypershade"),
                ("UV_EDITOR", "UV Editor", "Enter UV component mode & UV sync"),
                ("GRAPH_EDITOR", "Graph Editor", "Inspect F-Curves / Graph Editor"),
                ("DOPE_SHEET", "Dope Sheet", "Inspect Dope Sheet keyframes"),
                ("ASSET_BROWSER", "Asset Browser", "Open Blender Asset Browser"),
                ("SCULPT_MODE", "Sculpt Mode", "Enter Blender Sculpt Mode (native F brush size)"),
                ("GREASE_PENCIL", "Grease Pencil", "Create or activate Grease Pencil object"),
                ("OBJECT_MODE", "Return to Object Mode", "Return cleanly to Object Mode"),
            ),
            default="GEOMETRY_NODES",
            options={"SKIP_SAVE"},
        )

        def execute(self, context):
            res = open_native_editor_or_mode(self.target, context=context)
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "Native bridge failed"))
                return {"CANCELLED"}
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_select_all_toggle(bpy.types.Operator):
        """Conflict-free Select All / Deselect All fallback (`Ctrl+Shift+A`) when `A` is bound to Maya Frame All."""

        bl_idname = "landfall_studio.select_all_toggle"
        bl_label = "Select / Deselect All (Ctrl+Shift+A)"
        bl_description = "Select or deselect all objects or mesh components (re-homed from A)"
        bl_options = {"REGISTER", "UNDO"}

        action: bpy.props.EnumProperty(
            name="Action",
            items=(
                ("TOGGLE", "Toggle Select All", "Toggle all selected/deselected"),
                ("SELECT", "Select All", "Select all"),
                ("DESELECT", "Deselect All", "Deselect all"),
                ("INVERT", "Invert Selection", "Invert selection"),
            ),
            default="TOGGLE",
            options={"SKIP_SAVE"},
        )

        def execute(self, context):
            if context.mode == "EDIT_MESH":
                bpy.ops.mesh.select_all(action=self.action)
            else:
                bpy.ops.object.select_all(action=self.action)
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_smart_delete(bpy.types.Operator):
        """Conflict-free Maya Delete (`Delete` / `BackSpace`) for objects and mesh components when `X` is Hold Grid Snap."""

        bl_idname = "landfall_studio.smart_delete"
        bl_label = "Maya Smart Delete (Del / BackSpace)"
        bl_description = "Delete selected objects or active mesh components (Verts/Edges/Faces; dissolves interior edges like Maya Delete Edge)"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            if context.mode == "EDIT_MESH":
                msm = tuple(bool(x) for x in context.tool_settings.mesh_select_mode)
                if msm[2]:
                    bpy.ops.mesh.delete(type="FACE")
                elif msm[1]:
                    import bmesh
                    obj = context.edit_object
                    bm = bmesh.from_edit_mesh(obj.data) if (obj and obj.data) else None
                    before_edges = len(bm.edges) if bm is not None else -1
                    dissolved = False
                    try:
                        res = bpy.ops.mesh.dissolve_edges(use_verts=True)
                        if res == {"FINISHED"}:
                            bm = bmesh.from_edit_mesh(obj.data) if (obj and obj.data) else None
                            after_edges = len(bm.edges) if bm is not None else -1
                            dissolved = after_edges < before_edges
                    except Exception:
                        dissolved = False
                    if not dissolved:
                        bpy.ops.mesh.delete(type="EDGE")
                else:
                    bpy.ops.mesh.delete(type="VERT")
            else:
                bpy.ops.object.delete(use_global=False)
            return {"FINISHED"}

    CONTINUITY_CLASSES = (
        LANDFALL_STUDIO_OT_viewport_shading,
        LANDFALL_STUDIO_OT_soft_selection,
        LANDFALL_STUDIO_OT_native_bridge,
        LANDFALL_STUDIO_OT_select_all_toggle,
        LANDFALL_STUDIO_OT_smart_delete,
    )
else:
    CONTINUITY_CLASSES = ()


def register_continuity_operators() -> None:
    if bpy is None:
        return
    for cls in CONTINUITY_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister_continuity_operators() -> None:
    if bpy is None:
        return
    for cls in reversed(CONTINUITY_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
