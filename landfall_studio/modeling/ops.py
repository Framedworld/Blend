"""Blender Operators (`bpy.types.Operator`) for Gate 05 Modeling, Caddies, Make Live, Quad Draw, Diagnostics & UV (`landfall_studio.modeling.ops`)."""

from __future__ import annotations

try:
    import bpy
except ImportError:
    bpy = None

from . import caddy, diagnostics_uv, live_surface, quad_draw

if bpy is not None:

    class LANDFALL_STUDIO_OT_modeling_caddy(bpy.types.Operator):
        """Invoke a Maya-style modeling operation (`Extrude`, `Bevel`, `Bridge`, `Connect`) with a live In-Viewport Heads-Up Caddy."""

        bl_idname = "landfall_studio.modeling_caddy"
        bl_label = "Maya Modeling Caddy"
        bl_description = "Invoke Extrude, Bevel, Bridge, or Connect with a live Maya In-Viewport Heads-Up Caddy"
        bl_options = {"REGISTER", "UNDO"}

        tool_type: bpy.props.EnumProperty(
            name="Tool",
            items=(
                ("EXTRUDE", "Extrude", "Maya polyExtrudeFace1 with live Thickness/Offset/Divisions caddy"),
                ("BEVEL", "Bevel", "Maya polyBevel1 with live Fraction/Segments/Profile caddy"),
                ("BRIDGE", "Bridge", "Maya polyBridgeEdge1 with live Divisions/Twist/Smooth caddy"),
                ("CONNECT", "Connect", "Maya polyConnectComponents1 with live Segments/Slide/Pinch caddy"),
            ),
            default="EXTRUDE",
        )
        tool_id: bpy.props.StringProperty(
            name="Tool ID",
            default="",
            options={"SKIP_SAVE"},
        )

        def execute(self, context):
            chosen_tool = (self.tool_id or self.tool_type or "EXTRUDE").strip().upper()
            res = caddy.invoke_modeling_caddy(chosen_tool)
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "Modeling caddy failed."))
                return {"CANCELLED"}
            for area in (context.screen.areas if context.screen else []):
                if area.type == "VIEW_3D":
                    area.tag_redraw()
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_scrub_caddy_param(bpy.types.Operator):
        """Adjust or scrub a parameter on the active In-Viewport Heads-Up Caddy."""

        bl_idname = "landfall_studio.scrub_caddy_param"
        bl_label = "Scrub Caddy Parameter"
        bl_description = "Adjust a parameter on the active Maya In-Viewport Heads-Up Caddy"
        bl_options = {"REGISTER", "UNDO"}

        param_key: bpy.props.StringProperty(name="Parameter Key", default="")
        delta_steps: bpy.props.FloatProperty(name="Delta Steps", default=1.0)

        def execute(self, context):
            res = caddy.scrub_caddy_parameter(
                param_key=self.param_key or None,
                delta_steps=float(self.delta_steps),
            )
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "No active caddy."))
                return {"CANCELLED"}
            for area in (context.screen.areas if context.screen else []):
                if area.type == "VIEW_3D":
                    area.tag_redraw()
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_target_weld(bpy.types.Operator):
        """Activate `blendertk.TargetWeld` modal vertex weld or weld two vertices programmatically."""

        bl_idname = "landfall_studio.target_weld"
        bl_label = "Maya Target Weld"
        bl_description = "Interactive drag-a-vertex-onto-another merge tool (blendertk.TargetWeld)"
        bl_options = {"REGISTER", "UNDO"}

        merge_to_center: bpy.props.BoolProperty(name="Merge to Center", default=False)
        source_index: bpy.props.IntProperty(name="Source Vertex", default=-1)
        target_index: bpy.props.IntProperty(name="Target Vertex", default=-1)

        def execute(self, context):
            if self.source_index >= 0 and self.target_index >= 0:
                res = caddy.weld_vertices_target_weld(
                    self.source_index,
                    self.target_index,
                    merge_to_center=bool(self.merge_to_center),
                )
            else:
                res = caddy.activate_target_weld(merge_to_center=bool(self.merge_to_center))
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "Target Weld failed."))
                return {"CANCELLED"}
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_make_live(bpy.types.Operator):
        """Designate or clear the scoped `Make Live` reference mesh for surface projection."""

        bl_idname = "landfall_studio.make_live"
        bl_label = "Make Live"
        bl_description = "Designate the selected mesh as the non-selectable Maya Live Surface for projection and Quad Draw"
        bl_options = {"REGISTER", "UNDO"}

        target_name: bpy.props.StringProperty(name="Target Mesh", default="")
        clear: bpy.props.BoolProperty(name="Clear Live Surface", default=False)
        toggle: bpy.props.BoolProperty(name="Toggle Live Surface", default=True)

        def execute(self, context):
            if self.clear:
                res = live_surface.clear_live_surface()
            else:
                res = live_surface.set_live_surface(
                    self.target_name or None,
                    toggle=bool(self.toggle),
                )
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "Make Live failed."))
                return {"CANCELLED"}
            for area in (context.screen.areas if context.screen else []):
                if area.type == "VIEW_3D":
                    area.tag_redraw()
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_quad_draw_modal(bpy.types.Operator):
        """Maya-style `Quad Draw` retopology modal & chord operator (`LMB` plot dot, `Shift` fill quad, `Ctrl` loop cut, `Shift-drag` relax, `Tab-drag` extrude strip)."""

        bl_idname = "landfall_studio.quad_draw_modal"
        bl_label = "Maya Quad Draw"
        bl_description = "Quad Draw retopology tool (LMB plot dots, Shift+LMB fill quad, Ctrl+LMB loop cut, Shift-drag relax, Tab-drag extrude strip)"
        bl_options = {"REGISTER", "UNDO"}

        action: bpy.props.EnumProperty(
            name="Action",
            items=(
                ("MODAL", "Interactive Modal", "Start interactive Quad Draw modal tool"),
                ("PLOT_DOT", "Plot Dot", "Plot a Quad Draw dot projected onto Make Live"),
                ("FILL_QUAD", "Fill Quad (Shift)", "Fill a quad from 4 plotted dots"),
                ("EXTRUDE_STRIP", "Extrude Strip (Tab)", "Extrude boundary edge strip onto Make Live"),
                ("LOOP_CUT", "Insert Loop (Ctrl)", "Insert an edge loop across the quad strip"),
                ("RELAX", "Relax Vertices (Shift-Drag)", "Relax vertices while constrained to Make Live"),
                ("CLEAR_DOTS", "Clear Dots", "Clear plotted Quad Draw dots"),
            ),
            default="MODAL",
        )
        point: bpy.props.FloatVectorProperty(name="World Point", size=3, default=(0.0, 0.0, 0.0))
        delta: bpy.props.FloatVectorProperty(name="Extrude Delta", size=3, default=(0.4, 0.0, 0.0))
        edge_index: bpy.props.IntProperty(name="Edge Index", default=0)
        factor: bpy.props.FloatProperty(name="Loop Factor", default=0.5, min=0.05, max=0.95)

        def execute(self, context):
            act = self.action
            if act == "PLOT_DOT":
                res = quad_draw.plot_quad_draw_dot(tuple(self.point))
            elif act == "FILL_QUAD":
                res = quad_draw.fill_quad_from_dots()
            elif act == "EXTRUDE_STRIP":
                res = quad_draw.extrude_quad_draw_strip(delta_world=tuple(self.delta), edge_index=self.edge_index)
            elif act == "LOOP_CUT":
                res = quad_draw.insert_quad_draw_loop(edge_index=self.edge_index, factor=self.factor)
            elif act == "RELAX":
                res = quad_draw.relax_quad_draw_verts()
            elif act == "CLEAR_DOTS":
                res = quad_draw.clear_quad_draw_dots()
            else:
                quad_draw.set_quad_draw_active(True)
                quad_draw.ensure_retopo_mesh()
                res = {"ok": True}

            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "Quad Draw action failed."))
                return {"CANCELLED"}
            for area in (context.screen.areas if context.screen else []):
                if area.type == "VIEW_3D":
                    area.tag_redraw()
            return {"FINISHED"}

        def invoke(self, context, event):
            if self.action != "MODAL" or bpy.app.background or context.area is None or context.area.type != "VIEW_3D":
                return self.execute(context)
            quad_draw.set_quad_draw_active(True)
            quad_draw.ensure_retopo_mesh()
            context.window_manager.modal_handler_add(self)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        def modal(self, context, event):
            from bpy_extras import view3d_utils

            if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
                quad_draw.set_quad_draw_active(False)
                if context.area:
                    context.area.tag_redraw()
                return {"FINISHED"}

            if event.alt or event.type in {"MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE"}:
                return {"PASS_THROUGH"}

            if event.type == "LEFTMOUSE" and event.value == "PRESS":
                region = context.region
                rv3d = context.region_data
                if region and rv3d:
                    coord = (event.mouse_region_x, event.mouse_region_y)
                    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
                    ray_vec = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
                    hit_info = live_surface.raycast_live_surface(
                        (ray_origin.x, ray_origin.y, ray_origin.z),
                        (ray_vec.x, ray_vec.y, ray_vec.z),
                    )
                    hit_loc = hit_info.get("location", (0.0, 0.0, 0.0))

                    if event.shift and not event.ctrl:
                        if len(quad_draw.get_quad_draw_dots()) >= 4:
                            quad_draw.fill_quad_from_dots()
                        else:
                            quad_draw.relax_quad_draw_verts(iterations=2)
                    elif event.ctrl and not event.shift:
                        quad_draw.insert_quad_draw_loop(edge_index=0, factor=0.5)
                    else:
                        quad_draw.plot_quad_draw_dot(hit_loc)

                    if context.area:
                        context.area.tag_redraw()
                    return {"RUNNING_MODAL"}

            return {"PASS_THROUGH"}

    class LANDFALL_STUDIO_OT_quad_draw(LANDFALL_STUDIO_OT_quad_draw_modal):
        """Alias operator (`landfall_studio.quad_draw`) for Maya Shift+RMB Marking Menu & Shelf."""

        bl_idname = "landfall_studio.quad_draw"
        bl_label = "Maya Quad Draw"

    class LANDFALL_STUDIO_OT_center_pivot_guarded(bpy.types.Operator):
        """Maya `Modify > Center Pivot` (`CENTER` or `BOTTOM`) with animated transform guard."""

        bl_idname = "landfall_studio.center_pivot_guarded"
        bl_label = "Center Pivot (Guarded)"
        bl_description = "Center or bottom-align object pivot while guarding animated transforms"
        bl_options = {"REGISTER", "UNDO"}

        mode: bpy.props.StringProperty(name="Mode", default="CENTER")
        allow_animated: bpy.props.BoolProperty(name="Allow Animated", default=False)

        def execute(self, context):
            from ..adapters import btk_bridge
            res = btk_bridge.center_pivot_guarded(mode=self.mode, allow_animated=bool(self.allow_animated))
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("reason") or res.get("error", "Center Pivot blocked."))
                return {"CANCELLED"}
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_freeze_transformations_guarded(bpy.types.Operator):
        """Maya `Modify > Freeze Transformations` with animated transform & negative-scale guard."""

        bl_idname = "landfall_studio.freeze_transformations_guarded"
        bl_label = "Freeze Transformations (Guarded)"
        bl_description = "Freeze object location, rotation, and scale while guarding animated transforms and negative scale"
        bl_options = {"REGISTER", "UNDO"}

        allow_animated: bpy.props.BoolProperty(name="Allow Animated", default=False)

        def execute(self, context):
            from ..adapters import btk_bridge
            res = btk_bridge.freeze_transformations_guarded(allow_animated=bool(self.allow_animated))
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("reason") or res.get("error", "Freeze Transformations blocked."))
                return {"CANCELLED"}
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_uv_unwrap_pack(bpy.types.Operator):
        """Auto Unwrap & Pack UV islands via `blendertk.UvUtils`."""

        bl_idname = "landfall_studio.uv_unwrap_pack"
        bl_label = "Auto Unwrap & Pack UVs"
        bl_description = "Unwrap and pack UV islands on active mesh"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            res = diagnostics_uv.uv_unwrap_and_pack()
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "UV Unwrap & Pack failed."))
                return {"CANCELLED"}
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_delete_non_deformer_history(bpy.types.Operator):
        """Delete non-deformer modeling construction history while preserving Armatures, skin weights, and Shape Keys."""

        bl_idname = "landfall_studio.delete_non_deformer_history"
        bl_label = "Delete Non-Deformer History"
        bl_description = "Edit > Delete by Type > Non-Deformer History (preserves Armature, Vertex Groups, and Shape Keys)"
        bl_options = {"REGISTER", "UNDO"}

        force_remove_shape_keys: bpy.props.BoolProperty(
            name="Force Bake Over Shape Keys",
            default=False,
        )

        def execute(self, context):
            res = diagnostics_uv.delete_non_deformer_history(
                force_remove_shape_keys=bool(self.force_remove_shape_keys)
            )
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("reason") or res.get("error", "Non-Deformer History guarded."))
                return {"CANCELLED"}
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_scene_diagnostics(bpy.types.Operator):
        """Run read-only scene diagnostics across topology, transforms, and morph/rig assets."""

        bl_idname = "landfall_studio.scene_diagnostics"
        bl_label = "Run Scene Diagnostics (Read-Only)"
        bl_description = "Inspect mesh topology, non-orthogonal transforms, and morph/rig hazards without mutating the scene"

        def execute(self, context):
            rep = diagnostics_uv.run_scene_diagnostics()
            issues = rep.get("mesh_issues", {})
            self.report(
                {"INFO"},
                f"Audit ({rep['mesh_count']} meshes): NGons={issues.get('ngons', 0)}, NonManifold={issues.get('nonmanifold', 0)}, Shear={len(rep.get('non_orthogonal_objects', {}))}",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_texel_density(bpy.types.Operator):
        """Measure or apply UV Texel Density (`px/unit`) via `blendertk.UvUtils`."""

        bl_idname = "landfall_studio.texel_density"
        bl_label = "UV Texel Density"
        bl_description = "Get or Set UV Texel Density (px/unit) across selected meshes"
        bl_options = {"REGISTER", "UNDO"}

        action: bpy.props.EnumProperty(
            name="Action",
            items=(
                ("GET", "Get Texel Density", "Measure current texel density"),
                ("SET", "Set Texel Density", "Apply target texel density"),
                ("UNWRAP_PACK", "Auto Unwrap & Pack", "Unwrap and pack UV islands"),
            ),
            default="GET",
        )
        density: bpy.props.FloatProperty(name="Target Density (px/m)", default=512.0, min=1.0, max=16384.0)
        map_size: bpy.props.IntProperty(name="Map Size", default=2048, min=64, max=16384)

        def execute(self, context):
            if self.action == "SET":
                res = diagnostics_uv.set_mesh_texel_density(self.density, map_size=self.map_size)
            elif self.action == "UNWRAP_PACK":
                res = diagnostics_uv.uv_unwrap_and_pack()
            else:
                res = diagnostics_uv.get_mesh_texel_density(map_size=self.map_size)
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "Texel density op failed."))
                return {"CANCELLED"}
            return {"FINISHED"}

    MODELING_CLASSES = (
        LANDFALL_STUDIO_OT_modeling_caddy,
        LANDFALL_STUDIO_OT_scrub_caddy_param,
        LANDFALL_STUDIO_OT_target_weld,
        LANDFALL_STUDIO_OT_make_live,
        LANDFALL_STUDIO_OT_quad_draw_modal,
        LANDFALL_STUDIO_OT_quad_draw,
        LANDFALL_STUDIO_OT_center_pivot_guarded,
        LANDFALL_STUDIO_OT_freeze_transformations_guarded,
        LANDFALL_STUDIO_OT_uv_unwrap_pack,
        LANDFALL_STUDIO_OT_delete_non_deformer_history,
        LANDFALL_STUDIO_OT_scene_diagnostics,
        LANDFALL_STUDIO_OT_texel_density,
    )
else:
    MODELING_CLASSES = ()
