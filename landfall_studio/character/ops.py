"""Blender Operators (`bpy.types.Operator`) for Gate 06 Character Art, Shape Editor & Skin Weights (`landfall_studio.character.ops`)."""

from __future__ import annotations

from typing import Any, List

try:
    import bpy
except ImportError:
    bpy = None

from . import blendshape_bridge, shape_editor, skin_weights


def _build_operator_classes() -> List[Any]:
    if bpy is None:
        return []

    class LANDFALL_STUDIO_OT_shape_add_target(bpy.types.Operator):
        bl_idname = "landfall_studio.shape_add_target"
        bl_label = "Add Shape Target (Maya Shape Editor)"
        bl_description = "Create a new Shape Key target on the active mesh"
        bl_options = {"REGISTER", "UNDO"}

        target_name: bpy.props.StringProperty(name="Target Name", default="Target", options={"SKIP_SAVE"})
        from_mix: bpy.props.BoolProperty(name="From Mix", default=False, options={"SKIP_SAVE"})

        def execute(self, context):
            from .. import commands, ui

            obj = getattr(context, "active_object", None)
            res = shape_editor.create_shape_target(obj, name=self.target_name, from_mix=self.from_mix)
            if not res.get("ok"):
                self.report({"WARNING"}, str(res.get("error", "Could not add shape target")))
                return {"CANCELLED"}
            commands.record_command(
                cmd_id=self.bl_idname,
                kwargs={"target_name": self.target_name, "from_mix": self.from_mix},
                callable_fn=lambda: shape_editor.create_shape_target(
                    getattr(bpy.context, "active_object", None),
                    name=self.target_name,
                    from_mix=self.from_mix,
                ),
                label=f"Add Shape Target ({res['key_name']})",
                repeatable=True,
            )
            ui.set_command_feedback(self.bl_idname, f"Created Shape Key: {res['key_name']}")
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_shape_extract_target(bpy.types.Operator):
        bl_idname = "landfall_studio.shape_extract_target"
        bl_label = "Extract Shape Target (Held Reference)"
        bl_description = "Extract a Shape Key into a standalone editable mesh while holding a bidirectional live reference"
        bl_options = {"REGISTER", "UNDO"}

        key_name: bpy.props.StringProperty(name="Key Name", default="", options={"SKIP_SAVE"})
        offset_x: bpy.props.FloatProperty(name="Offset X", default=2.2, options={"SKIP_SAVE"})

        def execute(self, context):
            from .. import ui

            obj = getattr(context, "active_object", None)
            if obj is None or getattr(obj, "type", None) != "MESH":
                self.report({"WARNING"}, "Select a mesh with shape keys.")
                return {"CANCELLED"}
            kname = self.key_name
            if not kname:
                sk = getattr(obj.data, "shape_keys", None)
                if sk and len(sk.key_blocks) > 1:
                    kname = obj.active_shape_key.name if obj.active_shape_key and obj.active_shape_key != sk.reference_key else sk.key_blocks[1].name
            res = shape_editor.extract_target_mesh_with_reference(
                obj, kname, offset_vector=(self.offset_x, 0.0, 0.0)
            )
            if not res.get("ok"):
                self.report({"WARNING"}, str(res.get("error", "Extract failed")))
                return {"CANCELLED"}
            ui.set_command_feedback(
                self.bl_idname,
                f"Extracted '{res['key_name']}' -> {res['extracted_object']} (Held Ref)",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_shape_sync_held_target(bpy.types.Operator):
        bl_idname = "landfall_studio.shape_sync_held_target"
        bl_label = "Sync Held Reference Target"
        bl_description = "Validate strict topological connectivity and sync sculpted vertex deltas back to the source Shape Key"
        bl_options = {"REGISTER", "UNDO"}

        key_name: bpy.props.StringProperty(name="Key Name", default="", options={"SKIP_SAVE"})
        delete_extracted: bpy.props.BoolProperty(name="Delete Extracted", default=False, options={"SKIP_SAVE"})

        def execute(self, context):
            from .. import ui

            obj = getattr(context, "active_object", None)
            res = shape_editor.sync_extracted_target_to_shape_key(
                obj, key_name=self.key_name or None, delete_extracted=self.delete_extracted
            )
            if not res.get("ok"):
                self.report({"WARNING"}, str(res.get("reason", "Sync blocked")))
                ui.set_command_feedback(self.bl_idname, str(res.get("reason", "Sync blocked")), level="WARNING")
                return {"CANCELLED"}
            ui.set_command_feedback(
                self.bl_idname,
                f"Synced '{res['key_name']}' ({res['updated_vertices']} verts updated)",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_skin_weight_hammer(bpy.types.Operator):
        bl_idname = "landfall_studio.skin_weight_hammer"
        bl_label = "Weight Hammer (Maya Skin)"
        bl_description = "Set selected/active vertices' unlocked skin weights to the average of their 1-ring topological neighbors"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            from .. import commands, ui

            obj = getattr(context, "active_object", None)
            res = skin_weights.weight_hammer_vertices(obj, respect_locks=True, normalize=True)
            if not res.get("ok"):
                self.report({"WARNING"}, str(res.get("error", "Weight Hammer failed")))
                return {"CANCELLED"}
            commands.record_command(
                cmd_id=self.bl_idname,
                kwargs={},
                callable_fn=lambda: skin_weights.weight_hammer_vertices(
                    getattr(bpy.context, "active_object", None), respect_locks=True, normalize=True
                ),
                label="Weight Hammer",
                repeatable=True,
            )
            ui.set_command_feedback(
                self.bl_idname,
                f"Weight Hammer: {res['hammered_vertex_count']} verts (locks preserved)",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_skin_normalize_weights(bpy.types.Operator):
        bl_idname = "landfall_studio.skin_normalize_weights"
        bl_label = "Normalize Skin Weights (Respect Locks)"
        bl_description = "Normalize skin weights to 1.0 while strictly preserving locked vertex groups"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            from .. import commands, ui

            obj = getattr(context, "active_object", None)
            res = skin_weights.normalize_skin_weights(obj, respect_locks=True)
            if not res.get("ok"):
                self.report({"WARNING"}, str(res.get("error", "Normalize failed")))
                return {"CANCELLED"}
            commands.record_command(
                cmd_id=self.bl_idname,
                kwargs={},
                callable_fn=lambda: skin_weights.normalize_skin_weights(
                    getattr(bpy.context, "active_object", None), respect_locks=True
                ),
                label="Normalize Skin Weights",
                repeatable=True,
            )
            ui.set_command_feedback(
                self.bl_idname,
                f"Normalized {res['normalized_vertices']} verts (locked drift={res['max_locked_weight_drift']:.1e})",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_skin_prune_weights(bpy.types.Operator):
        bl_idname = "landfall_studio.skin_prune_weights"
        bl_label = "Prune Small Weights (Respect Locks)"
        bl_description = "Remove unlocked skin weights below threshold and cap max influences without touching locked groups"
        bl_options = {"REGISTER", "UNDO"}

        threshold: bpy.props.FloatProperty(name="Threshold", default=0.01, min=0.0, max=0.5, options={"SKIP_SAVE"})
        max_influences: bpy.props.IntProperty(name="Max Influences", default=4, min=1, max=16, options={"SKIP_SAVE"})

        def execute(self, context):
            from .. import commands, ui

            obj = getattr(context, "active_object", None)
            res = skin_weights.prune_small_weights(
                obj, threshold=self.threshold, max_influences=self.max_influences, respect_locks=True
            )
            if not res.get("ok"):
                self.report({"WARNING"}, str(res.get("error", "Prune failed")))
                return {"CANCELLED"}
            commands.record_command(
                cmd_id=self.bl_idname,
                kwargs={"threshold": self.threshold, "max_influences": self.max_influences},
                callable_fn=lambda: skin_weights.prune_small_weights(
                    getattr(bpy.context, "active_object", None),
                    threshold=self.threshold,
                    max_influences=self.max_influences,
                    respect_locks=True,
                ),
                label="Prune Small Weights",
                repeatable=True,
            )
            ui.set_command_feedback(
                self.bl_idname,
                f"Pruned {res['pruned_entries']} entries (<{self.threshold}, max_inf={self.max_influences})",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_skin_mirror_weights(bpy.types.Operator):
        bl_idname = "landfall_studio.skin_mirror_weights"
        bl_label = "Mirror Skin Weights (Respect Locks)"
        bl_description = "Mirror skin weights across symmetry plane (_L <-> _R) while preserving locked groups"
        bl_options = {"REGISTER", "UNDO"}

        direction: bpy.props.StringProperty(name="Direction", default="PLUS_TO_MINUS", options={"SKIP_SAVE"})
        axis: bpy.props.StringProperty(name="Axis", default="X", options={"SKIP_SAVE"})

        def execute(self, context):
            from .. import commands, ui

            obj = getattr(context, "active_object", None)
            res = skin_weights.mirror_skin_weights(
                obj, direction=self.direction, axis=self.axis, respect_locks=True
            )
            if not res.get("ok"):
                self.report({"WARNING"}, str(res.get("error", "Mirror weights failed")))
                return {"CANCELLED"}
            commands.record_command(
                cmd_id=self.bl_idname,
                kwargs={"direction": self.direction, "axis": self.axis},
                callable_fn=lambda: skin_weights.mirror_skin_weights(
                    getattr(bpy.context, "active_object", None),
                    direction=self.direction,
                    axis=self.axis,
                    respect_locks=True,
                ),
                label="Mirror Skin Weights",
                repeatable=True,
            )
            ui.set_command_feedback(
                self.bl_idname,
                f"Mirrored {res['mirrored_vertices']} verts ({self.direction} {self.axis})",
            )
            return {"FINISHED"}

    class LANDFALL_STUDIO_OT_open_blendshape_animator(bpy.types.Operator):
        bl_idname = "landfall_studio.open_blendshape_animator"
        bl_label = "Open Blendshape Animator"
        bl_description = "Open the Blendshape Animator Qt tool window"

        def execute(self, context):
            from .. import ui

            info = ui.open_panel("blendshape_animator")
            ui.set_command_feedback(
                self.bl_idname,
                f"Blendshape Animator: {'Open' if info.get('ok') else 'Unavailable'}",
            )
            return {"FINISHED"} if info.get("ok") else {"CANCELLED"}

    return [
        LANDFALL_STUDIO_OT_shape_add_target,
        LANDFALL_STUDIO_OT_shape_extract_target,
        LANDFALL_STUDIO_OT_shape_sync_held_target,
        LANDFALL_STUDIO_OT_skin_weight_hammer,
        LANDFALL_STUDIO_OT_skin_normalize_weights,
        LANDFALL_STUDIO_OT_skin_prune_weights,
        LANDFALL_STUDIO_OT_skin_mirror_weights,
        LANDFALL_STUDIO_OT_open_blendshape_animator,
    ]


CHARACTER_CLASSES = tuple(_build_operator_classes())
