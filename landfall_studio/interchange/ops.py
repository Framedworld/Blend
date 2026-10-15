"""Blender Operators for Gate 07 Maya Scene Interchange & References (`landfall_studio.interchange.ops`).

Registers:
- `LANDFALL_STUDIO_OT_import_maya_scene` (`landfall_studio.import_maya_scene`)
- `LANDFALL_STUDIO_OT_save_as_maya_scene` (`landfall_studio.save_as_maya_scene`)
- `LANDFALL_STUDIO_OT_send_to_maya` (`landfall_studio.send_to_maya`)
- `LANDFALL_STUDIO_OT_reference_scene` (`landfall_studio.reference_scene`)
- `LANDFALL_STUDIO_OT_validate_interchange` (`landfall_studio.validate_interchange`)
"""

from __future__ import annotations

from typing import Tuple
import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Operator

from . import maya_bridge, preflight_report, reference_scene


class LANDFALL_STUDIO_OT_import_maya_scene(Operator):
    bl_idname = "landfall_studio.import_maya_scene"
    bl_label = "Import Maya Scene (.ma / .mb)"
    bl_description = "Import a Maya scene (.ma/.mb) via headless mayapy with preflight and loss report"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(name="File Path", subtype="FILE_PATH", default="")
    via: EnumProperty(
        name="Carrier",
        items=(
            ("fbx", "FBX Intermediate", "Convert via FBX + HandoffManifest sidecar"),
            ("usd", "USD Intermediate", "Convert via mayaUSDExport + instance replay"),
        ),
        default="fbx",
    )
    rig_mode: EnumProperty(
        name="Rig Mode",
        items=(
            ("auto", "Auto SmartBake", "Bake driven animation when detected"),
            ("bake", "Always Bake", "Always run SmartBake"),
            ("raw", "Raw", "Do not bake driven channels"),
            ("rig", "RigGraph", "Transfer supported rig constraints"),
        ),
        default="auto",
    )
    clear_existing: BoolProperty(name="Clear Scene First", default=False)

    def execute(self, context):
        if not self.filepath:
            self.report({"WARNING"}, "No .ma/.mb filepath specified")
            return {"CANCELLED"}
        res = maya_bridge.import_maya_scene(
            self.filepath,
            via=self.via,
            rig_mode=self.rig_mode,
            clear_existing=self.clear_existing,
        )
        if not res.get("ok"):
            self.report({"WARNING"}, res.get("error") or f"Import status: {res.get('status')}")
            return {"CANCELLED"}
        self.report(
            {"INFO"},
            f"Imported Maya scene ({res.get('status')}): {len(res.get('imported_objects', []))} object(s)",
        )
        return {"FINISHED"}


class LANDFALL_STUDIO_OT_save_as_maya_scene(Operator):
    bl_idname = "landfall_studio.save_as_maya_scene"
    bl_label = "Save As Maya Scene (.ma / .mb)"
    bl_description = "Save the current scene or selection as a native Maya .ma or .mb scene via headless mayapy"
    bl_options = {"REGISTER"}

    filepath: StringProperty(name="Destination File Path", subtype="FILE_PATH", default="")
    scope: EnumProperty(
        name="Scope",
        items=(
            ("ALL", "Entire Scene", "Export entire scene"),
            ("SELECTED", "Selected Objects", "Export selected hierarchy closure"),
        ),
        default="ALL",
    )
    carrier: EnumProperty(
        name="Carrier",
        items=(("fbx", "FBX", "FBX carrier"), ("usd", "USD", "USD carrier")),
        default="fbx",
    )
    include_animation: BoolProperty(name="Include Animation", default=True)
    protected_source_path: StringProperty(name="Protected Source Path", default="")

    def execute(self, context):
        if not self.filepath:
            self.report({"WARNING"}, "No destination .ma/.mb filepath specified")
            return {"CANCELLED"}
        res = maya_bridge.save_as_maya_scene(
            self.filepath,
            scope=self.scope,
            carrier=self.carrier,
            include_animation=self.include_animation,
            protected_source_path=self.protected_source_path or None,
        )
        if not res.get("ok"):
            self.report({"WARNING"}, res.get("error") or "Save As Maya Scene failed")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Saved Maya scene: {res.get('written_path')}")
        return {"FINISHED"}


class LANDFALL_STUDIO_OT_send_to_maya(Operator):
    bl_idname = "landfall_studio.send_to_maya"
    bl_label = "Send to Maya"
    bl_description = "Send selected objects or scene to Maya via blendertk.MayaBridge"
    bl_options = {"REGISTER"}

    scope: EnumProperty(
        name="Scope",
        items=(
            ("SELECTED", "Selected Objects", "Send selected objects"),
            ("ALL", "Entire Scene", "Send entire scene"),
        ),
        default="SELECTED",
    )
    dry_run: BoolProperty(name="Dry Run (Stage Only)", default=False)

    def execute(self, context):
        res = maya_bridge.send_to_maya(scope=self.scope, dry_run=self.dry_run)
        if not res.get("ok"):
            self.report({"WARNING"}, res.get("error") or "Send to Maya failed")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Send to Maya ({res.get('status')}): {res.get('object_count', 0)} object(s)")
        return {"FINISHED"}


class LANDFALL_STUDIO_OT_reference_scene(Operator):
    bl_idname = "landfall_studio.reference_scene"
    bl_label = "Reference Scene (.blend / .ma / .mb / .fbx / .usd)"
    bl_description = "Create, reload, remove, or set display mode on a scene reference"
    bl_options = {"REGISTER", "UNDO"}

    action: EnumProperty(
        name="Action",
        items=(
            ("LINK", "Create Reference", "Link a .blend or bake+link a .ma/.mb/.fbx/.usd reference"),
            ("MODE", "Set Display Mode", "Set Normal / Reference / Template display mode"),
            ("RELOAD", "Reload Reference", "Reload linked library from disk"),
            ("REMOVE", "Remove Reference", "Unlink and remove reference"),
            ("IMPORT", "Unlink and Import", "Convert linked reference into local objects (requires approval)"),
        ),
        default="LINK",
    )
    filepath: StringProperty(name="File / Library", subtype="FILE_PATH", default="")
    display_mode: EnumProperty(
        name="Display Mode",
        items=(
            ("off", "Normal", "Normal selectable shaded display"),
            ("reference", "Reference (R)", "Shaded unselectable reference"),
            ("template", "Template (T)", "Wireframe unselectable template"),
        ),
        default="off",
    )
    approved: BoolProperty(name="Approve Make Local", default=False)

    def execute(self, context):
        act = self.action
        if act == "LINK":
            res = reference_scene.reference_scene(self.filepath, display_mode=self.display_mode)
        elif act == "MODE":
            res = reference_scene.set_reference_mode(self.filepath, mode=self.display_mode)
        elif act == "RELOAD":
            res = reference_scene.reload_reference_scene(self.filepath)
        elif act == "REMOVE":
            res = reference_scene.remove_reference_scene(self.filepath)
        elif act == "IMPORT":
            res = reference_scene.unlink_and_import_reference(self.filepath, approved=self.approved)
        else:
            res = {"ok": False, "error": f"Unknown reference action {act}"}

        if not res.get("ok"):
            self.report({"WARNING"}, res.get("error") or f"Reference action {act} failed")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Reference {act}: OK")
        return {"FINISHED"}


class LANDFALL_STUDIO_OT_validate_interchange(Operator):
    bl_idname = "landfall_studio.validate_interchange"
    bl_label = "Validate Maya Interchange"
    bl_description = "Run preflight or round-trip validation on a Maya .ma/.mb scene"
    bl_options = {"REGISTER"}

    source_path: StringProperty(name="Source .ma/.mb", subtype="FILE_PATH", default="")
    roundtrip_path: StringProperty(name="Roundtrip .ma/.mb", subtype="FILE_PATH", default="")

    def execute(self, context):
        if self.source_path and self.roundtrip_path:
            res = maya_bridge.validate_interchange_roundtrip(self.source_path, self.roundtrip_path)
        elif self.source_path:
            res = preflight_report.preflight_maya_scene(self.source_path)
        else:
            res = preflight_report.get_last_interchange_report()
        if not res.get("ok"):
            self.report({"WARNING"}, res.get("error") or "Interchange validation reported issues")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Interchange validation status: {res.get('status')}")
        return {"FINISHED"}


_CLASSES: Tuple[type, ...] = (
    LANDFALL_STUDIO_OT_import_maya_scene,
    LANDFALL_STUDIO_OT_save_as_maya_scene,
    LANDFALL_STUDIO_OT_send_to_maya,
    LANDFALL_STUDIO_OT_reference_scene,
    LANDFALL_STUDIO_OT_validate_interchange,
)


def register_interchange_operators() -> None:
    for cls in _CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister_interchange_operators() -> None:
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
