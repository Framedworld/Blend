"""Blender Operators for Gate 08 — Hypershade Material Browser, Animation Layers & Weight Layers (`landfall_studio.advanced.ops`)."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy.types import Operator

from . import anim_layers, hypershade, weight_layers


class LANDFALL_OT_create_shader_template(Operator):
    bl_idname = "landfall_studio.create_shader_template"
    bl_label = "Create Maya Shader Template"
    bl_options = {"REGISTER", "UNDO"}

    template_name: StringProperty(name="Template", default="Chrome")
    material_name: StringProperty(name="Name", default="")
    assign_to_selection: BoolProperty(name="Assign to Selection", default=True)

    def execute(self, context):
        res = hypershade.create_from_template(
            self.template_name,
            name=self.material_name or None,
            assign_to_selection=self.assign_to_selection,
        )
        if not res.get("ok"):
            self.report({"ERROR"}, str(res.get("error", "Failed to create shader template")))
            return {"CANCELLED"}
        try:
            from .. import ui

            ui.set_command_feedback(
                f"hypershade.create_from_template('{self.template_name}')",
                f"Created {res['material']} ({self.template_name})",
            )
            ui.refresh_hypershade_widgets()
        except Exception:
            pass
        return {"FINISHED"}


class LANDFALL_OT_assign_material(Operator):
    bl_idname = "landfall_studio.assign_material"
    bl_label = "Assign Material to Selection"
    bl_options = {"REGISTER", "UNDO"}

    material_name: StringProperty(name="Material", default="")

    def execute(self, context):
        res = hypershade.assign_material_to_selection(self.material_name)
        if not res.get("ok"):
            self.report({"ERROR"}, str(res.get("error", "Assign material failed")))
            return {"CANCELLED"}
        try:
            from .. import ui

            ui.set_command_feedback(
                f"hypershade.assign_material_to_selection('{self.material_name}')",
                f"Assigned {self.material_name} -> {len(res['assigned_objects'])} object(s)",
            )
            ui.refresh_hypershade_widgets()
        except Exception:
            pass
        return {"FINISHED"}


class LANDFALL_OT_graph_material(Operator):
    bl_idname = "landfall_studio.graph_material"
    bl_label = "Graph Material in Shader Editor"
    bl_options = {"REGISTER"}

    material_name: StringProperty(name="Material", default="")

    def execute(self, context):
        res = hypershade.graph_material_in_shader_editor(self.material_name)
        if not res.get("ok"):
            self.report({"ERROR"}, str(res.get("error", "Graph material failed")))
            return {"CANCELLED"}
        try:
            from .. import ui

            ui.set_command_feedback(
                f"hypershade.graph_material_in_shader_editor('{self.material_name}')",
                f"Graphed {self.material_name} in Blender Shader Editor",
            )
        except Exception:
            pass
        return {"FINISHED"}


class LANDFALL_OT_create_anim_layer(Operator):
    bl_idname = "landfall_studio.create_anim_layer"
    bl_label = "Create Animation Layer"
    bl_options = {"REGISTER", "UNDO"}

    layer_name: StringProperty(name="Layer Name", default="AnimLayer1")
    mode: StringProperty(name="Mode", default="ADD")
    weight: FloatProperty(name="Weight", default=1.0, min=0.0, max=1.0)

    def execute(self, context):
        res = anim_layers.create_anim_layer(
            None, name=self.layer_name, mode=self.mode, weight=self.weight
        )
        if not res.get("ok"):
            self.report({"ERROR"}, str(res.get("error", "Create anim layer failed")))
            return {"CANCELLED"}
        try:
            from .. import ui

            ui.set_command_feedback(
                f"anim_layers.create_anim_layer('{res['layer']}', mode='{res['mode']}')",
                f"Created AnimLayer: {res['layer']} ({res['mode']})",
            )
            ui.channel_box_ext.refresh_channel_box_extensions()
        except Exception:
            pass
        return {"FINISHED"}


class LANDFALL_OT_create_weight_layer(Operator):
    bl_idname = "landfall_studio.create_weight_layer"
    bl_label = "Create Skin Weight Layer"
    bl_options = {"REGISTER", "UNDO"}

    layer_name: StringProperty(name="Layer Name", default="WeightLayer1")
    mode: StringProperty(name="Mode", default="OVERRIDE")
    weight: FloatProperty(name="Weight", default=1.0, min=0.0, max=1.0)

    def execute(self, context):
        res = weight_layers.create_weight_layer(
            None, name=self.layer_name, mode=self.mode, weight=self.weight
        )
        if not res.get("ok"):
            self.report({"ERROR"}, str(res.get("error", "Create weight layer failed")))
            return {"CANCELLED"}
        try:
            from .. import ui

            ui.set_command_feedback(
                f"weight_layers.create_weight_layer('{res['layer']}', mode='{res['mode']}')",
                f"Created WeightLayer: {res['layer']} ({res['mode']})",
            )
        except Exception:
            pass
        return {"FINISHED"}


ADVANCED_CLASSES = (
    LANDFALL_OT_create_shader_template,
    LANDFALL_OT_assign_material,
    LANDFALL_OT_graph_material,
    LANDFALL_OT_create_anim_layer,
    LANDFALL_OT_create_weight_layer,
)


def register_advanced_operators() -> None:
    for cls in ADVANCED_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister_advanced_operators() -> None:
    for cls in reversed(ADVANCED_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
