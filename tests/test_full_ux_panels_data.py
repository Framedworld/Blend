"""Disposable, headless checks for panel target ownership and primitive input safety."""
import json
import sys
import traceback
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
results = {"passed": [], "failed": []}


def check(name, condition, detail=None):
    results["passed" if condition else "failed"].append(name if condition else {"name": name, "detail": str(detail)})


def run():
    from landfall_studio.ui import attribute_editor as ae, channel_box_ext as cb, desktop, tool_settings as ts
    from landfall_studio import modeling
    from landfall_studio.character import topology

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    first = cb.create_maya_primitive("CUBE", name="PanelTargetA")
    a = bpy.data.objects[first["object_name"]]
    second = cb.create_maya_primitive("CUBE", name="PanelTargetB")
    b = bpy.data.objects[second["object_name"]]
    controller = ae.MayaAttributeEditorWidget.__new__(ae.MayaAttributeEditorWidget)
    controller._updating = False
    controller._target_object = a
    refreshes = []
    controller.refresh = lambda: refreshes.append(True)
    controller._commit_value("transform", "translate_x", 17)
    check("pending AE edit cannot write to a different active object", a.location.x == 0 and b.location.x == 0 and refreshes)
    bpy.context.view_layer.objects.active = a
    controller._commit_value("transform", "scale_x", -2)
    controller._commit_value("transform", "scale_y", 0)
    check("AE commits preserve negative and zero scale", a.scale.x == -2 and a.scale.y == 0)

    ma = a.modifiers.new("PanelBevel", "BEVEL")
    mb = b.modifiers.new("PanelBevel", "BEVEL")
    ma.width, mb.width = .1, .2
    cb._selected_input_target = (ma.name, "width")
    cb._selected_input_owner = a.name
    bpy.context.view_layer.objects.active = b
    original_panel_lookup = desktop.get_panel_widget_and_slots
    desktop.get_panel_widget_and_slots = lambda name: (None, None)
    try:
        cb.scrub_selected_channels(.15)
        check("stale INPUTS selection cannot scrub same-named modifier on another object",
              abs(mb.width - .2) < 1e-6 and cb._selected_input_target is None)
        cb._selected_input_target = (ma.name, "width")
        cb._selected_input_owner = a.name
        bpy.context.view_layer.objects.active = a
        cb.scrub_selected_channels(.15)
        check("owned INPUTS selection still scrubs its modifier", abs(ma.width - .25) < 1e-6)
    finally:
        desktop.get_panel_widget_and_slots = original_panel_lookup
        cb.clear_input_scrub_target()

    node = cb.get_object_inputs(a)[0]["node_name"]
    check("ordinary primitive dimensions remain editable", cb.set_object_input_attribute(a, node, "width", 3)["ok"])
    bounded = cb.set_object_input_attribute(a, node, "subdivisions_x", 128)
    check("primitive metadata reports the builder's effective cube bound", bounded["ok"] and bounded["value"] == 64
          and json.loads(a[cb._INPUT_META_KEY])["params"]["subdivisions_x"] == 64, bounded)
    before = a[cb._INPUT_META_KEY]
    a.shape_key_add(name="Basis")
    a.shape_key_add(name="Smile")
    count = len(a.data.vertices)
    blocked = cb.set_object_input_attribute(a, node, "subdivisions_x", 3)
    check("primitive INPUTS protects shape keys and history metadata", not blocked["ok"] and a[cb._INPUT_META_KEY] == before
          and len(a.data.vertices) == count and len(a.data.shape_keys.key_blocks) == 2, blocked)

    sphere = cb.create_maya_primitive("SPHERE", name="UvPrimitive")
    obj = bpy.data.objects[sphere["object_name"]]
    node = cb.get_object_inputs(obj)[0]["node_name"]
    uvs = topology.snapshot_uvs_and_materials(obj)["uv_layers"]
    changed = cb.set_object_input_attribute(obj, node, "radius", 2)
    check("ordinary sphere radius remains editable without changing UV state", changed["ok"] and topology.snapshot_uvs_and_materials(obj)["uv_layers"] == uvs, changed)
    bounded = cb.set_object_input_attribute(obj, node, "subdivisions_x", 1)
    check("primitive metadata reports the builder's effective sphere minimum", bounded["ok"] and bounded["value"] == 3, bounded)
    if obj.data.uv_layers.active is None:
        obj.data.uv_layers.new(name="ArtistUVs")
    obj.data.uv_layers.active.data[0].uv.x += .125
    custom_uvs = topology.snapshot_uvs_and_materials(obj)["uv_layers"]
    blocked = cb.set_object_input_attribute(obj, node, "subdivisions_x", 24)
    check("custom UVs block primitive regeneration without data loss", not blocked["ok"]
          and topology.snapshot_uvs_and_materials(obj)["uv_layers"] == custom_uvs, blocked)

    primitive = cb.create_maya_primitive("CUBE", name="WeightedPrimitive")
    obj = bpy.data.objects[primitive["object_name"]]
    node = cb.get_object_inputs(obj)[0]["node_name"]
    group = obj.vertex_groups.new(name="Joint")
    group.add([0], .8, "REPLACE")
    blocked = cb.set_object_input_attribute(obj, node, "width", 4)
    check("skin weights block primitive regeneration", not blocked["ok"] and abs(group.weight(0) - .8) < 1e-6, blocked)
    shared = obj.copy()
    bpy.context.collection.objects.link(shared)
    blocked = cb.set_object_input_attribute(obj, node, "width", 4)
    check("shared mesh data blocks primitive regeneration", not blocked["ok"] and "single-user" in blocked["error"], blocked)

    ts._active_tool_context = "TRANSLATE"
    ts.set_tool_setting("soft_select_enabled", True)
    ts.reset_tool_settings()
    check("Reset Tool disables soft selection in object and edit modes", not bpy.context.scene.tool_settings.use_proportional_edit
          and not bpy.context.scene.tool_settings.use_proportional_edit_objects)
    check("unsupported Apply Option Box reports failure", not ts.apply_current_tool_option_box()["ok"])
    calls = []
    original_caddy = modeling.invoke_modeling_caddy
    modeling.invoke_modeling_caddy = lambda tool, **kwargs: calls.append((tool, kwargs)) or {"ok": True}
    try:
        ts._active_tool_context = "BEVEL"
        ts._option_box_state.update(bevel_width=.35, bevel_segments=3)
        ts.apply_current_tool_option_box()
        ts._active_tool_context = "EXTRUDE"
        ts._option_box_state["extrude_offset"] = .8
        ts.apply_current_tool_option_box()
        check("option boxes route matching parameters through the modeling caddy",
              calls[0][0] == "BEVEL" and calls[0][1]["params_dict"] == {"width": .35, "segments": 3}
              and calls[1][0] == "EXTRUDE" and calls[1][1]["params_dict"] == {"thickness": .8}
              and not obj.modifiers, calls)
    finally:
        modeling.invoke_modeling_caddy = original_caddy


try:
    run()
except Exception:
    results["failed"].append({"exception": traceback.format_exc()})
results["ok"] = not results["failed"]
(ROOT / "output/full_ux_panels_data_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print("FULL_UX_PANELS_DATA_RESULT:" + json.dumps(results), flush=True)
sys.exit(0 if results["ok"] else 1)
