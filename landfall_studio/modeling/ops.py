"""Blender Operators (`bpy.types.Operator`) for Gate 05 Modeling, Caddies, Make Live, Quad Draw, Diagnostics & UV (`landfall_studio.modeling.ops`)."""

from __future__ import annotations

try:
    import bpy
except ImportError:
    bpy = None

from . import caddy, diagnostics_uv, live_surface, quad_draw


def _quad_draw_edge_at_cursor(context, event):
    """Pick a nearby projected retopology edge for a discrete Ctrl-click."""
    from bpy_extras import view3d_utils
    from mathutils import Vector

    obj = quad_draw.ensure_retopo_mesh()
    if obj.mode == "EDIT":
        obj.update_from_editmode()
    mouse = Vector((event.mouse_region_x, event.mouse_region_y))
    best_index, best_distance = None, 28.0
    for edge in obj.data.edges:
        endpoints = [view3d_utils.location_3d_to_region_2d(context.region, context.region_data,
            obj.matrix_world @ obj.data.vertices[index].co) for index in edge.vertices]
        if any(point is None for point in endpoints):
            continue
        start, end = endpoints
        delta = end - start
        factor = max(0.0, min(1.0, (mouse-start).dot(delta) / max(delta.length_squared, 1e-12)))
        distance = (mouse - (start + delta * factor)).length
        if distance < best_distance:
            best_index, best_distance = edge.index, distance
    return best_index


if bpy is not None:

    class LANDFALL_STUDIO_OT_duplicate_objects(bpy.types.Operator):
        """Duplicate in place, retaining native data and independent generated helpers."""

        bl_idname = "landfall_studio.duplicate_objects"
        bl_label = "Duplicate Objects"
        bl_description = "Duplicate selected objects in place; move the selected copies with W"
        bl_options = {"REGISTER", "UNDO"}

        linked: bpy.props.BoolProperty(name="Instance", default=False, options={'SKIP_SAVE'},
            description="Share the original mesh data; object transforms and generated placement helpers remain independent")

        @classmethod
        def poll(cls, context):
            return context.mode == 'OBJECT' and bool(context.selected_editable_objects)

        def execute(self, context):
            from ..sculpt.instances import ensure_owners
            from ..commands import record_command

            status = bpy.ops.object.duplicate('EXEC_DEFAULT', linked=self.linked)
            if 'FINISHED' not in status:
                return {'CANCELLED'}
            for obj in context.selected_objects:
                ensure_owners(obj)
            record_command(self.bl_idname, kwargs={'linked':self.linked},
                callable_fn=bpy.ops.landfall_studio.duplicate_objects,
                label='Duplicate Instance' if self.linked else 'Duplicate')
            return {'FINISHED'}

    def _maya_group_name():
        index = 1
        while bpy.data.objects.get(f"group{index}") is not None:
            index += 1
        return f"group{index}"

    class LANDFALL_STUDIO_OT_group_objects(bpy.types.Operator):
        """Maya Ctrl+G: parent the selection under a new empty group transform."""

        bl_idname = "landfall_studio.group_objects"
        bl_label = "Group"
        bl_description = ("Group the selected objects under a new transform with its pivot at their "
                          "bounding-box center, as Maya's Ctrl+G. World positions are unchanged")
        bl_options = {"REGISTER", "UNDO"}

        @classmethod
        def poll(cls, context):
            return context.mode == 'OBJECT' and bool(context.selected_editable_objects)

        def execute(self, context):
            from mathutils import Matrix, Vector

            members = list(context.selected_editable_objects)
            # Only top-most selected objects move; selected children follow their parents.
            chosen = set(members)
            roots = [o for o in members if not any(p in chosen for p in _ancestors(o))]
            corners = [o.matrix_world @ Vector(c) for o in members for c in o.bound_box]
            if not corners:
                corners = [o.matrix_world.translation for o in members]
            low = Vector(tuple(min(c[i] for c in corners) for i in range(3)))
            high = Vector(tuple(max(c[i] for c in corners) for i in range(3)))
            parents = {o.parent for o in roots}
            common = parents.pop() if len(parents) == 1 else None
            group = bpy.data.objects.new(_maya_group_name(), None)
            group.empty_display_type = 'PLAIN_AXES'
            group.empty_display_size = max(0.1, (high - low).length * 0.1)
            collection = roots[0].users_collection[0] if roots[0].users_collection else context.collection
            collection.objects.link(group)
            # Maya nests a new group under the selection's common parent.
            group.parent = common
            group.matrix_world = Matrix.Translation((low + high) / 2.0)
            context.view_layer.update()
            for obj in roots:
                world = obj.matrix_world.copy()
                obj.parent = group
                obj.matrix_world = world
            for obj in context.selected_objects:
                obj.select_set(False)
            group.select_set(True)
            context.view_layer.objects.active = group
            self.report({'INFO'}, f"Grouped {len(roots)} object(s) under {group.name}")
            return {'FINISHED'}

    class LANDFALL_STUDIO_OT_ungroup_objects(bpy.types.Operator):
        """Maya Ungroup: move a group's children to its parent and remove the group."""

        bl_idname = "landfall_studio.ungroup_objects"
        bl_label = "Ungroup"
        bl_description = "Remove the selected group transforms, keeping their children in place"
        bl_options = {"REGISTER", "UNDO"}

        @classmethod
        def poll(cls, context):
            return context.mode == 'OBJECT' and any(
                o.type == 'EMPTY' and o.children for o in context.selected_editable_objects)

        def execute(self, context):
            groups = [o for o in context.selected_editable_objects if o.type == 'EMPTY' and o.children]
            released = []
            for group in groups:
                for child in list(group.children):
                    world = child.matrix_world.copy()
                    child.parent = group.parent
                    child.matrix_world = world
                    released.append(child)
                bpy.data.objects.remove(group, do_unlink=True)
            for obj in context.selected_objects:
                obj.select_set(False)
            for child in released:
                child.select_set(True)
            if released:
                context.view_layer.objects.active = released[0]
            return {'FINISHED'}

    def _ancestors(obj):
        parent = obj.parent
        while parent is not None:
            yield parent
            parent = parent.parent

    class LANDFALL_STUDIO_OT_maya_extrude(bpy.types.Operator):
        """Maya Ctrl+E: extrude faces in place and hand over to the manipulator and caddy."""

        bl_idname = "landfall_studio.maya_extrude"
        bl_label = "Extrude"
        bl_description = ("Extrude the selected faces in place, as Maya's Ctrl+E. Drag the "
                          "manipulator to set Thickness and Offset, or type them in the caddy")
        bl_options = {"REGISTER", "UNDO"}

        @classmethod
        def poll(cls, context):
            obj = context.active_object
            return obj is not None and obj.type == "MESH" and context.mode == "EDIT_MESH"

        def invoke(self, context, event):
            return self.execute(context)

        def execute(self, context):
            obj = context.active_object
            obj.update_from_editmode()
            if not any(polygon.select for polygon in obj.data.polygons):
                # Edges and vertices keep the familiar extrude-and-drag. That
                # modal records its own history; this wrapper records none.
                bpy.ops.landfall.extrude('INVOKE_DEFAULT')
                return {"CANCELLED"}
            res = caddy.begin_maya_extrude(context)
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("error", "Extrude failed."))
                return {"CANCELLED"}
            return {"FINISHED"}

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
            # Every Extrude route is Maya's one Extrude (see begin_maya_extrude).
            res = (caddy.begin_maya_extrude(context) if chosen_tool == "EXTRUDE"
                   else caddy.invoke_modeling_caddy(chosen_tool))
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
        """Quad Draw: click dots, Shift-click to fill four dots, Ctrl-click an edge to insert a loop."""

        bl_idname = "landfall_studio.quad_draw_modal"
        bl_label = "Maya Quad Draw"
        bl_description = "Click a surface to plot dots; Shift-click fills four dots or relaxes the mesh; Ctrl-click a nearby retopology edge inserts a loop; Escape exits. Use the Toolkit buttons for Strip and Relax"
        bl_options = {"REGISTER", "UNDO"}

        action: bpy.props.EnumProperty(
            name="Action",
            items=(
                ("MODAL", "Interactive Modal", "Start interactive Quad Draw modal tool"),
                ("PLOT_DOT", "Plot Dot", "Plot a Quad Draw dot projected onto Make Live"),
                ("FILL_QUAD", "Fill Quad (Shift)", "Fill a quad from 4 plotted dots"),
                ("EXTRUDE_STRIP", "Extrude Strip", "Extrude a boundary edge using the Delta parameter"),
                ("LOOP_CUT", "Insert Loop (Ctrl)", "Insert an edge loop across the quad strip"),
                ("RELAX", "Relax Mesh", "Relax retopology vertices while constrained to Make Live"),
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
                if not bpy.app.background and context.area is not None and context.area.type == "VIEW_3D":
                    return self.invoke(context, None)
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
                    if event.shift and not event.ctrl:
                        if len(quad_draw.get_quad_draw_dots()) >= 4:
                            res = quad_draw.fill_quad_from_dots(consume_dots=True)
                        else:
                            res = quad_draw.relax_quad_draw_verts(iterations=2)
                    elif event.ctrl and not event.shift:
                        edge_index = _quad_draw_edge_at_cursor(context, event)
                        if edge_index is None:
                            self.report({"WARNING"}, "Quad Draw: Ctrl-click near a retopology edge to insert a loop.")
                            return {"RUNNING_MODAL"}
                        res = quad_draw.insert_quad_draw_loop(edge_index=edge_index, factor=0.5)
                    else:
                        hit_info = live_surface.raycast_live_surface(tuple(ray_origin), tuple(ray_vec))
                        if not hit_info.get("ok"):
                            self.report({"WARNING"}, "Quad Draw: click a mesh surface to place a point.")
                            return {"RUNNING_MODAL"}
                        res = quad_draw.plot_quad_draw_dot(hit_info["location"])
                    if not res.get("ok"):
                        self.report({"WARNING"}, res.get("error", "Quad Draw action could not finish."))

                    if context.area:
                        context.area.tag_redraw()
                    return {"RUNNING_MODAL"}

            return {"PASS_THROUGH"}

    class LANDFALL_STUDIO_OT_quad_draw(LANDFALL_STUDIO_OT_quad_draw_modal):
        """Alias operator (`landfall_studio.quad_draw`) for Maya Shift+RMB Marking Menu & Shelf."""

        bl_idname = "landfall_studio.quad_draw"
        bl_label = "Maya Quad Draw"

    class LANDFALL_STUDIO_OT_center_pivot_guarded(bpy.types.Operator):
        """Maya `Modify > Center Pivot` preserving world vertex positions and child transforms."""

        bl_idname = "landfall_studio.center_pivot_guarded"
        bl_label = "Center Pivot (Guarded)"
        bl_description = "Center the object pivot while preserving world-space geometry and child transforms"
        bl_options = {"REGISTER", "UNDO"}

        mode: bpy.props.StringProperty(name="Mode", default="CENTER")

        def execute(self, context):
            res = diagnostics_uv.center_or_bake_pivot_guarded(mode=self.mode)
            if not res.get("ok"):
                self.report({"WARNING"}, res.get("reason") or res.get("error", "Center Pivot blocked."))
                return {"CANCELLED"}
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_freeze_transformations_guarded(bpy.types.Operator):
        """Maya `Modify > Freeze Transformations` with driven/skinned transform guard."""

        bl_idname = "landfall_studio.freeze_transformations_guarded"
        bl_label = "Freeze Transformations (Guarded)"
        bl_description = "Freeze object location, rotation, and scale while guarding driven or skinned transforms"
        bl_options = {"REGISTER", "UNDO"}

        allow_animated: bpy.props.BoolProperty(name="Allow Driven / Skinned", default=False)

        def execute(self, context):
            res = diagnostics_uv.freeze_transformations_guarded(force_driven=bool(self.allow_animated))
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
        LANDFALL_STUDIO_OT_duplicate_objects,
        LANDFALL_STUDIO_OT_group_objects,
        LANDFALL_STUDIO_OT_ungroup_objects,
        LANDFALL_STUDIO_OT_maya_extrude,
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
