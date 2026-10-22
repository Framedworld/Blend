"""Top-Docked Maya Status Line & Tabbed Icon Shelf — Figma Make Spec (`landfall_studio.ui.shelf`).

Provides:
- `SHELF_TABS`: Canonical Maya shelf definitions (`Polygons`, `Modeling`, `Subdiv & Display`,
  `UV & Shading`, `Deform & Rigging`, `Pipeline`) with vector icon names, labels, single-click
  commands, and double-click / `□` option-box Tool Settings targets.
- `MayaShelfWidget`: Two-row Modern Maya top bar matching the Figma Make prototype:
  - **Row 1 — Maya Status Line (`34px`)**: Cyan Hexagonal Maya `M` mark, Menu Set selector (`Modeling [F2]`),
    Quick `.ma` File/Interchange trio (`Open`, `Save`, `.ma`), joined `MASK` (`Obj | Vtx | Edg | Face | UV`)
    pill bar, `SNAP` magnets (`Grid`, `Curve`, `Point`, `Pivot`), glowing emerald `● LIVE SURFACE` capsule,
    `Symmetry OFF` pill, History actions, and right-aligned `Modeling Standard ▾` workspace selector.
  - **Row 2 — Tabbed Icon Shelf (`66px`)**: Left-aligned with the DAG Outliner column (`42px` offset),
    `2px` bottom Maya-teal (`#38A3D8`) active tab bar, `MAYA 2026.1` corner label, and `46x44px` top-beveled
    `_MayaShelfTileButton` tiles with a `2px` top `#38A3D8` bar on active tools.
- `TopShelfQtDock`: `WS_CHILD` dock manager embedding `MayaShelfWidget` at the top of the 3D Viewport.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import commands as cmd_registry
from . import channel_box_ext, icons, menus, style, tool_settings

SHELF_TABS: Dict[str, List[Dict[str, str]]] = {
    "Polygons": [
        {"id": "poly_cube", "label": "Cube", "icon": "poly_cube", "tool_ctx": "POLY_CUBE", "tip": "Create Polygon Cube (Double-click / □ for Option Box)"},
        {"id": "poly_sphere", "label": "Sphere", "icon": "poly_sphere", "tool_ctx": "POLY_SPHERE", "tip": "Create Polygon Sphere (Double-click / □ for Option Box)"},
        {"id": "poly_plane", "label": "Plane", "icon": "poly_plane", "tool_ctx": "POLY_PLANE", "tip": "Create Polygon Plane (Double-click / □ for Option Box)"},
        {"id": "poly_cylinder", "label": "Cylinder", "icon": "poly_cylinder", "tool_ctx": "POLY_CYLINDER", "tip": "Create Polygon Cylinder (Double-click / □ for Option Box)"},
        {"id": "bevel", "label": "Bevel", "icon": "bevel", "tool_ctx": "BEVEL", "tip": "Poly Bevel + In-Viewport Caddy (Double-click / □ for Option Box)"},
        {"id": "extrude", "label": "Extrude", "icon": "extrude", "tool_ctx": "EXTRUDE", "tip": "Poly Extrude + In-Viewport Caddy (Double-click / □ for Option Box)"},
        {"id": "bridge", "label": "Bridge", "icon": "bridge", "tool_ctx": "BRIDGE", "tip": "Bridge Edge Loops + In-Viewport Caddy"},
        {"id": "connect", "label": "Connect", "icon": "connect", "tool_ctx": "CONNECT", "tip": "Connect Components + In-Viewport Caddy"},
        {"id": "smooth_3", "label": "Smooth", "icon": "smooth_3", "tool_ctx": "SUBDIV", "tip": "Smooth Mesh Preview (3)"},
        {"id": "target_weld", "label": "Tgt Weld", "icon": "target_weld", "tool_ctx": "MERGE", "tip": "Maya Target Weld Tool (blendertk.TargetWeld)"},
        {"id": "quad_draw", "label": "Retopo", "icon": "quad_draw", "tool_ctx": "SUBDIV", "tip": "Maya Quad Draw Retopology Tool"},
        {"id": "make_live", "label": "Live", "icon": "make_live", "tool_ctx": "PIVOT", "tip": "Designate Selected Mesh as Scoped Live Surface"},
        {"id": "center_pivot", "label": "Center Piv", "icon": "center_pivot", "tool_ctx": "PIVOT", "tip": "Modify > Center Pivot"},
        {"id": "non_def_history", "label": "Non-Def", "icon": "non_def_history", "tool_ctx": "HISTORY", "tip": "Edit > Delete by Type > Non-Deformer History"},
        {"id": "delete_history", "label": "Del Hist", "icon": "delete_history", "tool_ctx": "HISTORY", "tip": "Edit > Delete by Type > History (Alt+Shift+D)"},
        {"id": "freeze_transforms", "label": "Freeze", "icon": "freeze_transforms", "tool_ctx": "FREEZE", "tip": "Modify > Freeze Transformations"},
    ],
    "Modeling": [
        {"id": "poly_cube", "label": "Cube", "icon": "poly_cube", "tool_ctx": "POLY_CUBE", "tip": "Create Polygon Cube"},
        {"id": "poly_sphere", "label": "Sphere", "icon": "poly_sphere", "tool_ctx": "POLY_SPHERE", "tip": "Create Polygon Sphere"},
        {"id": "poly_plane", "label": "Plane", "icon": "poly_plane", "tool_ctx": "POLY_PLANE", "tip": "Create Polygon Plane"},
        {"id": "poly_cylinder", "label": "Cylinder", "icon": "poly_cylinder", "tool_ctx": "POLY_CYLINDER", "tip": "Create Polygon Cylinder"},
        {"id": "bevel", "label": "Bevel", "icon": "bevel", "tool_ctx": "BEVEL", "tip": "Poly Bevel + In-Viewport Caddy"},
        {"id": "extrude", "label": "Extrude", "icon": "extrude", "tool_ctx": "EXTRUDE", "tip": "Poly Extrude + In-Viewport Caddy"},
        {"id": "bridge", "label": "Bridge", "icon": "bridge", "tool_ctx": "BRIDGE", "tip": "Bridge Edge Loops + In-Viewport Caddy"},
        {"id": "connect", "label": "Connect", "icon": "connect", "tool_ctx": "CONNECT", "tip": "Connect Components + In-Viewport Caddy"},
        {"id": "smooth_3", "label": "Smooth", "icon": "smooth_3", "tool_ctx": "SUBDIV", "tip": "Smooth Mesh Preview (3)"},
        {"id": "target_weld", "label": "Tgt Weld", "icon": "target_weld", "tool_ctx": "MERGE", "tip": "Target Weld Vertices"},
        {"id": "quad_draw", "label": "Retopo", "icon": "quad_draw", "tool_ctx": "SUBDIV", "tip": "Quad Draw Retopology Tool"},
        {"id": "make_live", "label": "Live", "icon": "make_live", "tool_ctx": "PIVOT", "tip": "Toggle Scoped Make Live Surface"},
        {"id": "non_def_history", "label": "Non-Def", "icon": "non_def_history", "tool_ctx": "HISTORY", "tip": "Delete Non-Deformer History"},
        {"id": "scene_audit", "label": "Audit", "icon": "scene_audit", "tool_ctx": "PIPELINE", "tip": "Run Read-Only Scene Diagnostics"},
    ],
    "Subdiv & Display": [
        {"id": "smooth_1", "label": "Mode 1", "icon": "smooth_1", "tool_ctx": "SUBDIV", "tip": "Base Mesh Display (1)"},
        {"id": "smooth_2", "label": "Mode 2", "icon": "smooth_2", "tool_ctx": "SUBDIV", "tip": "Cage + Smooth Display (2)"},
        {"id": "smooth_3", "label": "Mode 3", "icon": "smooth_3", "tool_ctx": "SUBDIV", "tip": "Smooth Subdiv Display (3)"},
        {"id": "shade_4", "label": "Wire [4]", "icon": "wire_on_shaded", "tool_ctx": "DISPLAY", "tip": "Maya 4: Wireframe Display Mode"},
        {"id": "shade_5", "label": "Shaded [5]", "icon": "poly_sphere", "tool_ctx": "DISPLAY", "tip": "Maya 5: Smooth Shaded Display Mode"},
        {"id": "shade_6", "label": "Tex [6]", "icon": "pbr_shader", "tool_ctx": "DISPLAY", "tip": "Maya 6: Shaded & Textured Display Mode"},
        {"id": "shade_7", "label": "Lights [7]", "icon": "pbr_shader", "tool_ctx": "DISPLAY", "tip": "Maya 7: Use All Scene Lights"},
        {"id": "soft_select", "label": "Soft [B]", "icon": "smooth_3", "tool_ctx": "SOFT_SELECT", "tip": "Toggle Maya Soft Selection (B) / Proportional Editing (O)"},
        {"id": "wire_on_shaded", "label": "Wire/Shd", "icon": "wire_on_shaded", "tool_ctx": "DISPLAY", "tip": "Toggle Wireframe on Shaded"},
        {"id": "xray", "label": "X-Ray", "icon": "xray", "tool_ctx": "DISPLAY", "tip": "Toggle Viewport X-Ray (Alt+Z)"},
        {"id": "border_edges", "label": "Borders", "icon": "border_edges", "tool_ctx": "DISPLAY", "tip": "Toggle Open Border Edge Highlight"},
        {"id": "isolate", "label": "Isolate", "icon": "isolate", "tool_ctx": "DISPLAY", "tip": "Isolate Selected"},
    ],
    "UV & Shading": [
        {"id": "hypershade", "label": "Hypershade", "icon": "pbr_shader", "tool_ctx": "SHADER", "tip": "Open Maya Hypershade Material Browser & Shader Graph"},
        {"id": "pbr_shader", "label": "Std Surf", "icon": "pbr_shader", "tool_ctx": "SHADER", "tip": "Assign New Standard Surface / Principled Shader"},
        {"id": "uv_mode", "label": "UV Mode", "icon": "uv_unwrap", "tool_ctx": "UV", "tip": "Enter UV Component Mode (F12)"},
        {"id": "uv_unwrap_pack", "label": "Auto UV", "icon": "uv_unwrap", "tool_ctx": "UV", "tip": "Auto Unwrap & Pack UVs"},
        {"id": "texel_density", "label": "Texel Den", "icon": "texel_density", "tool_ctx": "UV", "tip": "Measure / Apply Texel Density (2048 Map)"},
        {"id": "wire_on_shaded", "label": "Wire/Shd", "icon": "wire_on_shaded", "tool_ctx": "DISPLAY", "tip": "Toggle Wireframe on Shaded"},
    ],
    "Deform & Rigging": [
        {"id": "shape_editor", "label": "Shape Ed", "icon": "blendshape", "tool_ctx": "RIGGING", "tip": "Open Maya Shape Editor & Skin Weights Dock"},
        {"id": "blendshape_anim", "label": "Correctiv", "icon": "blendshape", "tool_ctx": "RIGGING", "tip": "Open BlendshapeAnimator Corrective In-Betweens UI"},
        {"id": "extract_target", "label": "Extr Tgt", "icon": "extract_target", "tool_ctx": "RIGGING", "tip": "Extract Active Shape Target Mesh (Hold Reference)"},
        {"id": "sync_target", "label": "Sync Tgt", "icon": "extract_target", "tool_ctx": "RIGGING", "tip": "Sync Extracted Target Back to Shape Key (Strict Topology)"},
        {"id": "weight_hammer", "label": "Wt Hammer", "icon": "weight_hammer", "tool_ctx": "RIGGING", "tip": "Maya Weight Hammer (Respects Locked Influences)"},
        {"id": "mirror_weights", "label": "Mirror Wts", "icon": "mirror_weights", "tool_ctx": "RIGGING", "tip": "Mirror Skin Weights Across X Axis (Respects Locks)"},
        {"id": "skin_transfer", "label": "Copy Skin", "icon": "skin_transfer", "tool_ctx": "RIGGING", "tip": "Controlled Skin Weight Transfer (Preserve Locked Weights)"},
        {"id": "joint_tool", "label": "Joint", "icon": "joint_tool", "tool_ctx": "RIGGING", "tip": "Create Armature / Joint"},
        {"id": "non_def_history", "label": "Non-Def", "icon": "non_def_history", "tool_ctx": "HISTORY", "tip": "Delete Non-Deformer History (Preserves Rig/ShapeKeys)"},
        {"id": "freeze_transforms", "label": "Freeze", "icon": "freeze_transforms", "tool_ctx": "FREEZE", "tip": "Freeze Transformations"},
    ],
    "FX / Nodes": [
        {"id": "geometry_nodes", "label": "Geo Nodes", "icon": "hierarchy_mgr", "tool_ctx": "NODES", "tip": "Attach / Inspect Blender Geometry Nodes Graph on Active Mesh"},
        {"id": "hypershade", "label": "Shader Ed", "icon": "pbr_shader", "tool_ctx": "SHADER", "tip": "Open Shader Editor / Maya Hypershade Node Graph"},
        {"id": "sculpt_mode", "label": "Sculpt", "icon": "smooth_3", "tool_ctx": "SCULPT", "tip": "Enter Blender Sculpt Mode (Native F Brush Size / Shift+F Strength)"},
        {"id": "grease_pencil", "label": "Grease Pcl", "icon": "quad_draw", "tool_ctx": "GPENCIL", "tip": "Create / Activate Grease Pencil 2D/3D Object"},
        {"id": "uv_editor", "label": "UV Editor", "icon": "uv_unwrap", "tool_ctx": "UV", "tip": "Open UV Component Mode & UV Sync"},
        {"id": "graph_editor", "label": "Graph Ed", "icon": "blendshape", "tool_ctx": "ANIM", "tip": "Inspect Graph Editor (F-Curves)"},
        {"id": "dope_sheet", "label": "DopeSht", "icon": "hierarchy_mgr", "tool_ctx": "ANIM", "tip": "Inspect Dope Sheet Keyframes"},
        {"id": "asset_browser", "label": "Assets", "icon": "workspace_ed", "tool_ctx": "PIPELINE", "tip": "Open Blender Asset Browser"},
        {"id": "soft_select", "label": "Soft [B]", "icon": "smooth_3", "tool_ctx": "SOFT_SELECT", "tip": "Toggle Maya Soft Selection (B) / Hold B+LMB Radius Ring"},
    ],
    "Pipeline": [
        {"id": "maya_bridge_tab", "label": "Maya .ma", "icon": "reference_mgr", "tool_ctx": "PIPELINE", "tip": "Open Maya .ma/.mb Interchange & Reference Dock"},
        {"id": "import_maya", "label": "Import .ma", "icon": "workspace_ed", "tool_ctx": "PIPELINE", "tip": "Import Maya Scene (.ma / .mb) via mayapy"},
        {"id": "save_maya", "label": "Save .ma", "icon": "workspace_ed", "tool_ctx": "PIPELINE", "tip": "Save As Maya Scene (.ma / .mb) via mayapy"},
        {"id": "send_maya", "label": "Send Maya", "icon": "reference_mgr", "tool_ctx": "PIPELINE", "tip": "Send Selection to Maya (blendertk.MayaBridge)"},
        {"id": "workspace_ed", "label": "Workspace", "icon": "workspace_ed", "tool_ctx": "PIPELINE", "tip": "Open Project Workspace Editor (workspace.mel)"},
        {"id": "reference_mgr", "label": "References", "icon": "reference_mgr", "tool_ctx": "PIPELINE", "tip": "Open Maya Reference Editor"},
        {"id": "scene_audit", "label": "Scn Audit", "icon": "scene_audit", "tool_ctx": "PIPELINE", "tip": "Run Read-Only Scene Diagnostics"},
        {"id": "new_display_layer", "label": "+ Layer", "icon": "quad_view", "tool_ctx": "LAYERS", "tip": "Create Display Layer from Selected Objects"},
        {"id": "script_output", "label": "Script Ed", "icon": "hierarchy_mgr", "tool_ctx": "PIPELINE", "tip": "Toggle Script Output Console"},
    ],
}

_active_shelf_tool_id: str = "bevel"


def execute_shelf_item(item_id: str) -> Dict[str, Any]:
    """Execute a Maya Shelf button command by `item_id` and record in command feedback."""
    global _active_shelf_tool_id
    import bpy
    from .. import character, interchange, modeling
    from . import desktop, hypershade_panel, interchange_panel, modeling_toolkit, shape_editor

    iid = (item_id or "").strip().lower()
    _active_shelf_tool_id = iid
    refresh_top_shelf_status()

    if iid == "hypershade":
        res = desktop.cycle_right_dock("HYPERSHADE")
        hypershade_panel.refresh_hypershade_widgets()
        desktop.set_command_feedback("HypershadeWindow", "Hypershade Lookdev Dock Open")
        return {"ok": True, "item_id": iid, "result": res}

    if iid in ("maya_bridge_tab", "import_maya", "save_maya"):
        res = desktop.cycle_right_dock("MAYA_INTERCHANGE")
        interchange_panel.refresh_interchange_widgets()
        desktop.set_command_feedback("MayaBridge", f"Interchange Dock ({iid})")
        return {"ok": True, "item_id": iid, "result": res}

    if iid == "send_maya":
        res = interchange.send_to_maya(scope="SELECTED", dry_run=False)
        interchange_panel.refresh_interchange_widgets()
        desktop.set_command_feedback("SendToMaya", res.get("status", "OK"))
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "shape_editor":
        res = desktop.cycle_right_dock("SHAPE_EDITOR")
        desktop.set_command_feedback("ShapeEditor", "Shape / Skin Dock Open")
        return {"ok": True, "item_id": iid, "result": res}

    if iid == "isolate":
        res = menus.run_op("view3d.localview")
        return {"ok": res == {"FINISHED"}, "item_id": iid, "result": str(res)}

    if iid == "joint_tool":
        # Create an actual editable armature rather than just changing feedback.
        res = menus.run_op("object.armature_add", enter_editmode=True)
        return {"ok": res == {"FINISHED"}, "item_id": iid, "result": str(res)}

    if iid == "blendshape_anim":
        res = desktop.open_panel("blendshape_animator", docked=False)
        desktop.set_command_feedback("BlendshapeAnimator", "Opened")
        return {"ok": res.get("ok", True), "item_id": iid, "result": res}

    if iid == "extract_target":
        snap = shape_editor.get_shape_editor_snapshot()
        targets = snap.get("shape_targets", [])
        tname = targets[0]["name"] if targets else "Target1"
        if not targets:
            character.create_shape_target(target_name=tname, weight=1.0)
        res = character.extract_target_mesh_with_reference(target_name=tname)
        shape_editor.refresh_shape_editor_widgets()
        desktop.set_command_feedback("ExtractShapeTarget", res.get("extracted_object", tname))
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "sync_target":
        res = character.sync_extracted_target_to_shape_key()
        shape_editor.refresh_shape_editor_widgets()
        desktop.set_command_feedback("SyncShapeTarget", res.get("target_name", "Synced"))
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "weight_hammer":
        res = character.weight_hammer_vertices()
        shape_editor.refresh_shape_editor_widgets()
        desktop.set_command_feedback("weightHammerVerts", f"verts={res.get('hammered_vertex_count', 0)}")
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "mirror_weights":
        res = character.mirror_skin_weights(direction="POSITIVE_TO_NEGATIVE")
        shape_editor.refresh_shape_editor_widgets()
        desktop.set_command_feedback("copySkinWeights -mirror", f"verts={res.get('mirrored_vertex_count', 0)}")
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "skin_transfer":
        sel = [o for o in getattr(bpy.context, "selected_objects", ()) if o.type == "MESH"]
        active = getattr(bpy.context.view_layer.objects, "active", None)
        others = [o for o in sel if o != active]
        src = others[0] if others else active
        res = character.controlled_weight_transfer(source_obj=src, target_obj=active, method="CLOSEST_SURFACE")
        shape_editor.refresh_shape_editor_widgets()
        desktop.set_command_feedback("copySkinWeights", f"transferred={res.get('transferred_vertex_count', 0)}")
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid in ("poly_cube", "poly_sphere", "poly_cylinder", "poly_plane"):
        ptype = iid.replace("poly_", "").upper()
        opts = tool_settings.get_tool_settings_snapshot()["option_box"]
        res = channel_box_ext.create_maya_primitive(
            primitive_type=ptype,
            width=opts["prim_width"],
            height=opts["prim_height"],
            depth=opts["prim_depth"],
            radius=opts["prim_radius"],
            subdivisions_x=opts["prim_subdivisions_x"],
            subdivisions_y=opts["prim_subdivisions_y"],
            subdivisions_z=opts["prim_subdivisions_z"],
        )
        cmd_registry.record_command(
            cmd_id=f"shelf.{iid}",
            kwargs={
                "primitive_type": ptype,
                "width": opts["prim_width"], "height": opts["prim_height"],
                "depth": opts["prim_depth"], "radius": opts["prim_radius"],
                "subdivisions_x": opts["prim_subdivisions_x"],
                "subdivisions_y": opts["prim_subdivisions_y"],
                "subdivisions_z": opts["prim_subdivisions_z"],
            },
            callable_fn=channel_box_ext.create_maya_primitive,
            label=f"Poly {ptype.title()}",
            repeatable=True,
        )
        desktop.sync_channels_now()
        channel_box_ext.refresh_channel_box_extensions()
        desktop.set_command_feedback(f"poly{ptype.title()}", res.get("object_name", ptype))
        return {"ok": True, "item_id": iid, "result": res}

    if iid in ("bevel", "extrude", "bridge", "connect"):
        if iid == "extrude":
            from ..modeling import caddy
            res = caddy.begin_maya_extrude()
        else:
            res = modeling.invoke_modeling_caddy(iid.upper())
        desktop.sync_channels_now()
        channel_box_ext.refresh_channel_box_extensions()
        modeling_toolkit.refresh_modeling_toolkit_widgets()
        desktop.set_command_feedback(f"poly{iid.title()}", str(res.get("node_title") or res.get("error", iid)),
            level="INFO" if res.get("ok") else "ERROR")
        return {"ok": res.get("ok", True), "item_id": iid, "result": res}

    if iid == "target_weld":
        res = modeling.activate_target_weld(merge_to_center=False)
        desktop.set_command_feedback("TargetWeldTool", "Active" if res.get("ok") else res.get("error", "Could not activate"),
            level="INFO" if res.get("ok") else "ERROR")
        return {"ok": res.get("ok", True), "item_id": iid, "result": res}

    if iid == "quad_draw":
        res = menus.run_op("landfall_studio.quad_draw_modal", invoke=True)
        modeling_toolkit.refresh_modeling_toolkit_widgets()
        return {"ok": bool(res and res & {"FINISHED", "RUNNING_MODAL"}), "item_id": iid, "result": str(res)}

    if iid == "make_live":
        res = modeling.set_live_surface(toggle=True)
        refresh_top_shelf_status()
        modeling_toolkit.refresh_modeling_toolkit_widgets()
        desktop.set_command_feedback(
            "MakeLive",
            (res.get("object_name") if res.get("active") else "Cleared") if res.get("ok") else res.get("error", "Make Live failed"),
            level="INFO" if res.get("ok") else "ERROR",
        )
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "non_def_history":
        res = modeling.delete_non_deformer_history()
        desktop.sync_channels_now()
        channel_box_ext.refresh_channel_box_extensions()
        modeling_toolkit.refresh_modeling_toolkit_widgets()
        desktop.set_command_feedback(
            "BakeNonDefHistory",
            res.get("reason") if res.get("guarded") else res.get("object_name", "OK"),
        )
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "scene_audit":
        rep = modeling.run_scene_diagnostics()
        issues = rep.get("mesh_issues", {})
        desktop.set_command_feedback(
            "SceneAudit",
            f"NGons={issues.get('ngons', 0)} NonManifold={issues.get('nonmanifold', 0)}",
        )
        return {"ok": True, "item_id": iid, "result": rep}

    if iid == "uv_unwrap_pack":
        res = modeling.uv_unwrap_and_pack()
        desktop.set_command_feedback("polyAutoProjection", res.get("object_name", "OK"))
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "texel_density":
        res = modeling.get_mesh_texel_density(map_size=2048)
        desktop.set_command_feedback(
            "texelDensity",
            f"{res.get('texel_density', 0.0):.1f} px/m",
        )
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "center_pivot":
        res = modeling.center_or_bake_pivot_guarded(mode="CENTER")
        desktop.sync_channels_now()
        desktop.set_command_feedback("CenterPivot", res.get("object_name", "OK"))
        return {"ok": res.get("ok", True), "item_id": iid, "result": res}

    if iid == "delete_history":
        res = channel_box_ext.delete_construction_history()
        desktop.sync_channels_now()
        channel_box_ext.refresh_channel_box_extensions()
        desktop.set_command_feedback("DeleteHistory", res.get("object_name", "OK"))
        return {"ok": res.get("ok", False), "item_id": iid, "result": res}

    if iid == "freeze_transforms":
        res = modeling.freeze_transformations_guarded()
        desktop.sync_channels_now()
        desktop.set_command_feedback(
            "FreezeTransformations",
            res.get("reason") if res.get("guarded") else res.get("object_name", "OK"),
        )
        return {"ok": res.get("ok", True), "item_id": iid, "result": res}

    if iid in ("smooth_1", "smooth_2", "smooth_3"):
        mode_map = {"smooth_1": "CAGE", "smooth_2": "BOTH", "smooth_3": "SMOOTH"}
        try:
            bpy.ops.landfall.smooth_preview(mode=mode_map[iid])
        except Exception:
            pass
        desktop.set_command_feedback("displaySmoothness", mode_map[iid])
        return {"ok": True, "item_id": iid}

    if iid in ("shade_4", "shade_5", "shade_6", "shade_7"):
        from .. import continuity

        sh_key = iid.split("_")[-1]
        res = continuity.set_maya_viewport_shading(sh_key)
        return {"ok": res.get("ok", True), "item_id": iid, "result": res}

    if iid == "soft_select":
        from .. import continuity

        res = continuity.set_soft_selection_state(toggle=True)
        return {"ok": res.get("ok", True), "item_id": iid, "result": res}

    if iid in (
        "geometry_nodes",
        "sculpt_mode",
        "grease_pencil",
        "uv_editor",
        "graph_editor",
        "dope_sheet",
        "asset_browser",
    ):
        from .. import continuity

        res = continuity.open_native_editor_or_mode(iid.upper())
        return {"ok": res.get("ok", True), "item_id": iid, "result": res}

    if iid == "wire_on_shaded":
        from .. import continuity

        res = continuity.set_maya_viewport_shading("WIRE_ON_SHADED")
        desktop.set_command_feedback("WireframeOnShaded", "Toggled")
        return {"ok": True, "item_id": iid, "result": res}

    if iid == "xray":
        from .. import continuity

        res = continuity.set_maya_viewport_shading("XRAY")
        desktop.set_command_feedback("ToggleXRay", "Toggled")
        return {"ok": True, "item_id": iid, "result": res}

    if iid == "border_edges":
        res = menus.run_op("landfall.toggle_scene_flag", prop="landfall_border_show")
        return {"ok": res == {"FINISHED"}, "item_id": iid, "result": str(res)}

    if iid == "uv_mode":
        try:
            bpy.ops.landfall_studio.component_mode(mode="UV")
        except Exception:
            pass
        return {"ok": True, "item_id": iid}

    if iid == "pbr_shader":
        res = attribute_editor_assign_shader()
        return {"ok": True, "item_id": iid, "result": res}

    if iid == "workspace_ed":
        return desktop.open_panel("workspace_editor", docked=False)

    if iid == "reference_mgr":
        return desktop.open_panel("reference_manager", docked=False)

    if iid == "script_output":
        return desktop.open_panel("script_output", docked=True)

    if iid == "new_display_layer":
        res = channel_box_ext.create_display_layer(assign_selected=True)
        channel_box_ext.refresh_channel_box_extensions()
        return {"ok": True, "item_id": iid, "result": res}

    error = f"No shelf action is registered for '{iid}'"
    desktop.set_command_feedback(iid, error, level="ERROR")
    return {"ok": False, "item_id": iid, "error": error}


def attribute_editor_assign_shader() -> Dict[str, Any]:
    from . import attribute_editor

    return attribute_editor.set_attribute_editor_value(
        "material", "material_name", "aiStandardSurface1"
    )


def open_tool_settings_for_shelf_item(item_id: str, tool_ctx: Optional[str] = None) -> Dict[str, Any]:
    """Open the `Tool Settings` (`□` Option Box) inspector in the right dock for `item_id`."""
    from . import desktop

    ctx_name = tool_ctx or item_id.upper()
    tool_settings.set_tool_setting("tool_context", ctx_name)
    res = desktop.cycle_right_dock("TOOL_SETTINGS")
    desktop.set_command_feedback(f"{item_id} Option Box (□)", f"Tool Settings: {ctx_name}")
    return res


def _create_maya_hex_logo_widget():
    """Create the Figma Make `24x24px` cyan hexagonal Maya `M` badge."""
    from qtpy import QtCore, QtGui, QtWidgets

    class _MayaHexLogo(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.setFixedSize(24, 24)
            self.setToolTip("Landfall Studio — Modern Maya Experience in Blender 5.2")

        def paintEvent(self, _event):
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)
            poly = QtGui.QPolygonF(
                [
                    QtCore.QPointF(12.0, 1.0),
                    QtCore.QPointF(22.0, 6.5),
                    QtCore.QPointF(22.0, 17.5),
                    QtCore.QPointF(12.0, 23.0),
                    QtCore.QPointF(2.0, 17.5),
                    QtCore.QPointF(2.0, 6.5),
                ]
            )
            grad = QtGui.QLinearGradient(0, 0, 24, 24)
            grad.setColorAt(0.0, QtGui.QColor("#33AFD2"))
            grad.setColorAt(1.0, QtGui.QColor("#207DA4"))
            p.setBrush(QtGui.QBrush(grad))
            p.setPen(QtGui.QPen(QtGui.QColor("#69D2F0"), 1.0))
            p.drawPolygon(poly)

            f = p.font()
            f.setPixelSize(11)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QtGui.QColor("#FFFFFF"))
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, "M")
            p.end()

    return _MayaHexLogo()


def _create_shelf_tile_button(spec: Dict[str, str]):
    """Create a Figma Make `46x44px` Maya Shelf tile button with top inner bevel, 2px top `#38A3D8` active bar, and `□` option-box badge."""
    from qtpy import QtCore, QtGui, QtWidgets

    class _MayaShelfTileButton(QtWidgets.QToolButton):
        def __init__(self, item_spec: Dict[str, str]):
            super().__init__()
            self.spec = item_spec
            self.setObjectName("MayaShelfTile")
            self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            self.setIcon(icons.get_icon(item_spec["icon"], 24))
            self.setIconSize(QtCore.QSize(24, 24))
            self.setText(item_spec["label"])
            self.setToolTip(item_spec.get("tip", item_spec["label"]))
            self.setFixedSize(54, 52)
            self.setCheckable(True)

        def mousePressEvent(self, event):
            if event.button() == QtCore.Qt.LeftButton and event.pos().x() >= self.width() - 13 and event.pos().y() <= 13:
                open_tool_settings_for_shelf_item(
                    self.spec["id"], self.spec.get("tool_ctx")
                )
                event.accept()
                return
            if event.button() == QtCore.Qt.RightButton:
                open_tool_settings_for_shelf_item(
                    self.spec["id"], self.spec.get("tool_ctx")
                )
                event.accept()
                return
            super().mousePressEvent(event)

        def mouseDoubleClickEvent(self, event):
            open_tool_settings_for_shelf_item(
                self.spec["id"], self.spec.get("tool_ctx")
            )
            event.accept()

        def paintEvent(self, event):
            super().paintEvent(event)
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.Antialiasing, False)
            is_act = self.isChecked() or (self.spec["id"] == _active_shelf_tool_id)
            if is_act:
                # Figma Make `.shelf-tile.active::after` 2px top Maya-teal bar
                p.fillRect(0, 0, self.width(), 2, QtGui.QColor("#38A3D8"))
            else:
                # Top inner bevel highlight
                p.fillRect(1, 1, self.width() - 2, 1, QtGui.QColor("#383D45"))
            # Subtle Maya '□' option box glyph in top-right corner
            p.setPen(QtGui.QPen(QtGui.QColor("#5C6672"), 1))
            p.drawRect(self.width() - 9, 4, 5, 5)
            p.end()

    btn = _MayaShelfTileButton(spec)
    from .menus import _safe_call
    btn.clicked.connect(lambda: _safe_call(lambda:execute_shelf_item(spec['id']),spec['label']))
    return btn


class MayaShelfWidget:
    """Two-row Modern Maya Status Line + Tabbed Icon Shelf Qt widget (Figma Make Spec)."""

    def __init__(self, parent: Any = None):
        from qtpy import QtCore, QtWidgets

        self.root = QtWidgets.QFrame(parent)
        self.root.setObjectName("MayaPanelRoot")
        style.apply_studio_style(self.root)

        vlay = QtWidgets.QVBoxLayout(self.root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # --- Row 1: Maya Status Line (32px, Figma Make `.status-line`) ---
        status_bar = QtWidgets.QFrame()
        status_bar.setObjectName("MayaStatusLine")
        status_bar.setFixedHeight(40)
        slay = QtWidgets.QHBoxLayout(status_bar)
        slay.setContentsMargins(10, 4, 10, 4)
        slay.setSpacing(10)

        # Maya Status Line order: menu set | scene | selection mode + mask | snap | live / symmetry / soft | history & render ... editor toggles
        self.cmb_menu_set = QtWidgets.QComboBox()
        self.cmb_menu_set.addItems(["Modeling  [F2]", "Rigging  [F3]", "Animation  [F4]", "FX  [F5]", "Rendering  [F6]"])
        self.cmb_menu_set.setFixedWidth(126)
        self.cmb_menu_set.setFixedHeight(24)
        self.cmb_menu_set.setToolTip("Menu Set — switches the right-hand menus of the Main Menu Bar")
        self.cmb_menu_set.currentIndexChanged.connect(self._on_menu_set_changed)
        slay.addWidget(self.cmb_menu_set)

        def _icon_group(items):
            grp = QtWidgets.QFrame()
            glay = QtWidgets.QHBoxLayout(grp)
            glay.setContentsMargins(0, 0, 0, 0)
            glay.setSpacing(2)
            handle = QtWidgets.QFrame()
            handle.setObjectName("MayaCollapseHandle")
            handle.setFixedSize(3, 18)
            glay.addWidget(handle)
            btns = []
            for icon_key, tip, cb, checkable in items:
                b = QtWidgets.QToolButton()
                b.setObjectName("MayaStatusIcon")
                b.setIcon(icons.get_icon(icon_key, 16))
                b.setIconSize(QtCore.QSize(16, 16))
                b.setFixedSize(26, 24)
                b.setToolTip(tip)
                b.setCheckable(checkable)
                b.clicked.connect(cb)
                glay.addWidget(b)
                btns.append(b)
            return grp, btns

        scene_grp, _ = _icon_group(
            [
                ("scene_new", "New Scene (Ctrl+N)", lambda: menus.run_op("wm.read_homefile", invoke=True), False),
                ("scene_open", "Open Scene (Ctrl+O)", lambda: menus.run_op("landfall.project_open", invoke=True), False),
                ("scene_save", "Save Scene (Ctrl+S)", lambda: menus.run_op("wm.save_mainfile", invoke=True), False),
            ]
        )
        slay.addWidget(scene_grp)

        self.mask_btns: Dict[str, Any] = {}
        selmode_grp, sel_btns = _icon_group(
            [
                ("sel_hierarchy", "Select by hierarchy (selects children)", lambda: menus.run_op("object.select_grouped", type="CHILDREN_RECURSIVE", extend=True), False),
                ("sel_object", "Select by object type (F8)", lambda: self._set_component_mode("OBJECT"), True),
                ("sel_component", "Select by component type (F8)", lambda: self._set_component_mode("TOGGLE"), False),
            ]
        )
        self.mask_btns["OBJECT"] = sel_btns[1]
        sel_btns[1].setChecked(True)
        slay.addWidget(selmode_grp)

        mask_group_frame = QtWidgets.QFrame()
        mglay = QtWidgets.QHBoxLayout(mask_group_frame)
        mglay.setContentsMargins(0, 0, 0, 0)
        mglay.setSpacing(1)
        for pill_text, mode_id, tip in (
            ("Vertex", "VERT", "Vertex Component Mode (F9)"),
            ("Edge", "EDGE", "Edge Component Mode (F10)"),
            ("Face", "FACE", "Face Component Mode (F11)"),
            ("UV", "UV", "UV Component Mode (F12)"),
        ):
            btn = QtWidgets.QPushButton(pill_text)
            btn.setObjectName("MayaMaskPill")
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, m=mode_id: self._set_component_mode(m))
            mglay.addWidget(btn)
            self.mask_btns[mode_id] = btn
        slay.addWidget(mask_group_frame)

        snap_grp, _ = _icon_group(
            [
                ("snap_grid", "Snap to Grid (Hold X)", lambda: self._trigger_snap_toggle("INCREMENT"), False),
                ("snap_curve", "Snap to Curve / Edge (Hold C)", lambda: self._trigger_snap_toggle("EDGE"), False),
                ("snap_point", "Snap to Point / Vertex (Hold V)", lambda: self._trigger_snap_toggle("VERTEX"), False),
                ("snap_plane", "Snap to Surface / Face", lambda: self._trigger_snap_toggle("FACE"), False),
                ("snap_pivot", "Edit Pivot Mode (Hold D)", lambda: self._trigger_snap_toggle("PIVOT"), False),
            ]
        )
        slay.addWidget(snap_grp)

        self.btn_live_surface = QtWidgets.QPushButton("● No Live Surface")
        self.btn_live_surface.setObjectName("MayaLiveCapsule")
        self.btn_live_surface.setFixedHeight(24)
        self.btn_live_surface.setToolTip("Make Selected Mesh Live (Scoped Surface Projection)")
        self.btn_live_surface.clicked.connect(lambda: execute_shelf_item("make_live"))
        slay.addWidget(self.btn_live_surface)

        self.btn_symmetry = QtWidgets.QPushButton("Symmetry: Off ▾")
        self.btn_symmetry.setFixedHeight(24)
        sym_menu = QtWidgets.QMenu(self.btn_symmetry)
        style.apply_studio_style(sym_menu)
        for axis in ("Off", "Object X", "Object Y", "Object Z"):
            sym_menu.addAction(axis, lambda _=False, a=axis: self._set_symmetry(a))
        self.btn_symmetry.setMenu(sym_menu)
        slay.addWidget(self.btn_symmetry)

        self.btn_soft_select = QtWidgets.QPushButton("Soft Select  B")
        self.btn_soft_select.setFixedHeight(24)
        self.btn_soft_select.setToolTip("Toggle Maya Soft Selection (B) / Hold B + LMB-Drag Falloff Radius Ring")
        self.btn_soft_select.clicked.connect(lambda: execute_shelf_item("soft_select"))
        slay.addWidget(self.btn_soft_select)

        hist_grp, _ = _icon_group(
            [
                ("history", "Undo History", lambda: menus.run_op("ed.undo_history", invoke=True), False),
                ("render_frame", "Render the current frame", lambda: menus.run_op("render.render", invoke=True), False),
            ]
        )
        slay.addWidget(hist_grp)

        slay.addStretch(1)

        toggle_grp, toggle_btns = _icon_group(
            [
                ("panel_attr_editor", "Show or hide the Attribute Editor", lambda: self._on_workspace_toggle("ATTRIBUTE_EDITOR"), True),
                ("panel_tool_settings", "Show or hide the Tool Settings", lambda: self._on_workspace_toggle("TOOL_SETTINGS"), True),
                ("panel_channel_box", "Show or hide the Channel Box / Layer Editor", lambda: self._on_workspace_toggle("CHANNEL_BOX"), True),
                ("panel_modifier_stack", "Show or hide the Modifier Stack", lambda: self._on_workspace_toggle("MODIFIER_STACK"), True),
            ]
        )
        self.editor_toggles = dict(zip(("ATTRIBUTE_EDITOR", "TOOL_SETTINGS", "CHANNEL_BOX", "MODIFIER_STACK"), toggle_btns))
        slay.addWidget(toggle_grp)


        vlay.addWidget(status_bar)
        self.maya_status_bar = status_bar

        # --- Row 2: Tabbed Icon Shelf (88px: 28px tabs + 54x52 tools) ---
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setFixedHeight(88)
        self.tabs.setStyleSheet(
            "QTabWidget::tab-bar { left: 52px; } "
            "QTabBar::tab { height: 24px; padding: 2px 14px; }"
        )

        self.tile_buttons: Dict[str, List[Any]] = {}

        for tab_name, items in SHELF_TABS.items():
            page = QtWidgets.QFrame()
            page.setObjectName("MayaShelfBar")
            play = QtWidgets.QHBoxLayout(page)
            # 42px left margin aligns shelf tiles directly with the Outliner column past the 42px Tool Rail!
            play.setContentsMargins(52, 4, 8, 4)
            play.setSpacing(6)
            self.tile_buttons[tab_name] = []
            for spec in items:
                tile = _create_shelf_tile_button(spec)
                play.addWidget(tile)
                self.tile_buttons[tab_name].append(tile)
            play.addStretch(1)
            self.tabs.addTab(page, tab_name)

        # Default to `Modeling` tab (index 1) matching Figma Make prototype
        if self.tabs.count() > 1:
            self.tabs.setCurrentIndex(1)

        vlay.addWidget(self.tabs)
        from .zbrush_panel import SculptHeader
        self.sculpt_header = SculptHeader()
        vlay.addWidget(self.sculpt_header.root)
        self.sculpt_header.root.hide()
        # Explicit strip height avoids a stale Qt layout minimum retaining both
        # the hidden Maya rows and Sculpt rows after a mode switch.
        self.root.setFixedHeight(130)
        _shelf_instances.append(self)
        self.refresh_status()

    def set_sculpt_mode(self, enabled):
        self.root.setFixedHeight(54 if enabled else 130)
        self.maya_status_bar.setVisible(not enabled)
        self.tabs.setVisible(not enabled)
        self.sculpt_header.root.setVisible(enabled)
        if enabled:
            self.sculpt_header.refresh()

    @property
    def active_shelf_name(self):
        return 'ZBrush Sculpt' if self.sculpt_header.root.isVisible() else self.tabs.tabText(self.tabs.currentIndex())

    @staticmethod
    def _make_vsep():
        from qtpy import QtWidgets

        sep = QtWidgets.QFrame()
        sep.setFixedWidth(2)
        sep.setFixedHeight(18)
        sep.setStyleSheet("background-color: #101214; border-right: 1px solid #353A41;")
        return sep

    def _on_menu_set_changed(self, idx: int) -> None:
        from . import main_menu

        tab_map = {0: 1, 1: 4, 2: 4, 3: 5, 4: 3}
        if idx in tab_map and tab_map[idx] < self.tabs.count():
            self.tabs.setCurrentIndex(tab_map[idx])
        main_menu.set_menu_set(self.cmb_menu_set.itemText(idx))

    def _set_symmetry(self, label: str) -> None:
        import bpy

        obj = getattr(bpy.context, "active_object", None)
        mesh = getattr(obj, "data", None) if obj is not None and obj.type == "MESH" else None
        if mesh is not None:
            for axis in "xyz":
                setattr(mesh, f"use_mirror_{axis}", label == f"Object {axis.upper()}")
        self.refresh_status()

    def _set_component_mode(self, mode_id: str) -> None:
        import bpy

        for mid, btn in self.mask_btns.items():
            btn.blockSignals(True)
            btn.setChecked(mid == mode_id)
            btn.blockSignals(False)
        try:
            bpy.ops.landfall_studio.component_mode(mode=mode_id)
        except Exception:
            pass

    def _trigger_snap_toggle(self, snap_elem: str) -> None:
        import bpy

        ts = getattr(getattr(bpy.context, "scene", None), "tool_settings", None)
        if ts is None:
            return
        if snap_elem == "PIVOT":
            ts.use_transform_data_origin = not bool(ts.use_transform_data_origin)
        else:
            ts.use_snap = True
            ts.snap_elements = {snap_elem}

    def _tear_off_from_menu(self, mode_target: str) -> None:
        from . import right_dock

        right_dock.tear_off_panel(mode_target)

    def _on_workspace_toggle(self, target: str) -> None:
        from . import desktop

        if target == "OUTLINER":
            desktop.toggle_left_outliner_dock()
        else:
            desktop.cycle_right_dock(target)

    def refresh_status(self) -> None:
        from .. import continuity, modeling

        st = modeling.get_live_surface_state()
        if st.get("active") and st.get("object_name"):
            self.btn_live_surface.setText(f"● LIVE · {st['object_name']}")
            self.btn_live_surface.setStyleSheet(
                "background-color: #1B3022; color: #E4E7E9; border: 1px solid #3FB950; "
                "border-radius: 12px; padding: 1px 10px; font-weight: 600; font-size: 11px;"
            )
        else:
            self.btn_live_surface.setText("● No Live Surface")
            self.btn_live_surface.setStyleSheet("")

        soft_st = continuity.get_soft_selection_state()
        if hasattr(self, "btn_soft_select"):
            if soft_st.get("enabled"):
                self.btn_soft_select.setText(f"Soft Select  B · {soft_st.get('radius', 1.0):.2f}")
                self.btn_soft_select.setStyleSheet(
                    "background-color: #3D2810; color: #FAD075; border: 1px solid #C88A2E; font-weight: 600;"
                )
            else:
                self.btn_soft_select.setText("Soft Select  B")
                self.btn_soft_select.setStyleSheet("")

        try:
            import bpy

            obj = getattr(bpy.context, "active_object", None)
            mesh = getattr(obj, "data", None) if obj is not None and obj.type == "MESH" else None
            axis = next((a.upper() for a in "xyz" if mesh is not None and getattr(mesh, f"use_mirror_{a}", False)), None)
            self.btn_symmetry.setText(f"Symmetry: Object {axis} ▾" if axis else "Symmetry: Off ▾")
        except Exception:
            pass

        try:
            from . import desktop

            mode = desktop._get_right_dock().mode
            for key, btn in getattr(self, "editor_toggles", {}).items():
                btn.blockSignals(True)
                btn.setChecked(key == mode)
                btn.blockSignals(False)
        except Exception:
            pass

        for tab_tiles in self.tile_buttons.values():
            for tile in tab_tiles:
                tile.setChecked(tile.spec["id"] == _active_shelf_tool_id)
                tile.update()


_shelf_instances: List[MayaShelfWidget] = []


def refresh_top_shelf_status() -> None:
    """Refresh the Top Status Line (`Live: <Surface>` pill and active shelf tile) across all active shelf widgets."""
    for inst in list(_shelf_instances):
        try:
            inst.refresh_status()
        except Exception:
            pass


class TopShelfQtDock:
    """Top `WS_CHILD` dock manager embedding `MayaShelfWidget` across the top of the 3D Viewport."""

    DEFAULT_HEIGHT = 130

    def __init__(self):
        from blendertk.ui_utils.qt_dock import QtDock

        self._inner_dock = QtDock(
            editor="Info",
            area_header=False,
            focus_on_hover=True,
            on_detach=self._handle_detach,
        )
        self._created_split_area = False
        self._shelf_ctrl: Optional[MayaShelfWidget] = None

    @property
    def docked(self) -> bool:
        return bool(self._inner_dock.docked)

    @property
    def widget(self):
        return self._shelf_ctrl.root if self._shelf_ctrl is not None else None

    def ensure_shelf_widget(self) -> MayaShelfWidget:
        if self._shelf_ctrl is None:
            self._shelf_ctrl = MayaShelfWidget()
        return self._shelf_ctrl

    def _handle_detach(self) -> None:
        self._created_split_area = False

    @staticmethod
    def _find_or_create_top_area(window, height: int = DEFAULT_HEIGHT):
        import bpy
        from blendertk.ui_utils._ui_utils import _UiUtilsInternal

        view3ds = [a for a in window.screen.areas if a.type == "VIEW_3D"]
        if not view3ds:
            return None, False
        target = max(view3ds, key=lambda a: a.height)
        if target.height <= height + 120:
            return None, False

        factor = max(0.25, min(0.92, 1.0 - (float(height) / float(target.height))))
        before = {a.as_pointer() for a in window.screen.areas}
        try:
            with bpy.context.temp_override(
                window=window,
                screen=window.screen,
                area=target,
                region=_UiUtilsInternal._window_region(target),
            ):
                res = bpy.ops.screen.area_split(direction="HORIZONTAL", factor=factor)
        except (RuntimeError, TypeError):
            return None, False
        if res != {"FINISHED"}:
            return None, False

        new_areas = [a for a in window.screen.areas if a.as_pointer() not in before]
        if not new_areas:
            return None, False
        top_area = min([new_areas[0], target], key=lambda a: (a.height, a.y))
        try:
            top_area.ui_type = "INFO"
        except TypeError:
            return None, False
        return top_area, True

    def dock_shelf(self, height: Optional[int] = None) -> bool:
        import blendertk as btk
        from blendertk.ui_utils.blender_window import BlenderWindow

        ctrl = self.ensure_shelf_widget()
        if not self._inner_dock.supported():
            try:
                ctrl.root.show()
            except Exception:
                pass
            return False

        if self._inner_dock.docked and self._inner_dock.widget is ctrl.root:
            self.enforce_dock_geometry()
            return True

        window = btk.main_window()
        if window is None:
            return False
        hwnd = BlenderWindow.window_hwnd(window)
        if hwnd is None:
            return False

        area = self._inner_dock.area
        try:
            if area is not None and not any(r.type == "WINDOW" for r in area.regions):
                area = None
        except (ReferenceError, AttributeError):
            area = None

        if area is None:
            area, created = self._find_or_create_top_area(
                window, height=height or round(self.DEFAULT_HEIGHT * ctrl.root.devicePixelRatioF())
            )
            if area is None:
                return False
            self._created_split_area = created

        dock = self._inner_dock
        dock._stop_glue()
        dock._release_widget()

        dock._window, dock._area, dock._hwnd = window, area, hwnd
        dock._edge_pad = 0
        dock._area_header = False
        dock._apply_area_header(window, area)

        if not dock._embed(ctrl.root, hwnd):
            self.undock()
            return False

        dock._position(dock.content_region())
        dock._start_glue()
        try:
            for region in area.regions:
                region.tag_redraw()
        except Exception:
            pass
        return True

    def enforce_dock_geometry(self) -> Optional[tuple]:
        if not self.docked:
            return None
        dock = self._inner_dock
        dock._last_rect = None
        dock._position(dock.content_region())
        return dock._last_rect

    def undock(self, close_split_area: bool = True) -> None:
        import bpy
        import blendertk as btk

        dock = self._inner_dock
        window = dock._window
        area = dock._area
        dock._stop_glue()
        dock._release_widget()

        if area is not None and window is not None and not bpy.app.background:
            if close_split_area and self._created_split_area:
                try:
                    btk.close_area(window, area)
                except Exception:
                    pass
                self._created_split_area = False

        dock._window = dock._area = dock._hwnd = None
        dock._last_rect = None

    def teardown(self) -> None:
        self.undock(close_split_area=True)
        self._inner_dock.teardown()
        if self._shelf_ctrl is not None:
            try:
                self._shelf_ctrl.root.hide()
                self._shelf_ctrl.root.deleteLater()
            except Exception:
                pass
            self._shelf_ctrl = None
