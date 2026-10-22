"""Validate every declared shelf dispatch and menu operator/property contract."""
import ast
import json
import sys
import traceback
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
results = {"passed": [], "failed": []}


def check(name, condition, detail=None):
    results["passed" if condition else "failed"].append(name if condition else {"test": name, "detail": detail})


def main():
    import landfall_studio
    from landfall_studio.ui import menus, shelf
    original_axis = bpy.context.preferences.inputs.view_zoom_axis
    landfall_studio.register()
    # Enumerate the actual UI definitions, including nested submenus.
    def walk(entries):
        for entry in entries:
            if entry[0] == "SUB":
                yield from walk(entry[2])
            elif entry[0] == "OP":
                yield entry
    count = 0
    for title, entries in menus.all_menu_entries():
        for _, label, path, invoke, props, hint in walk(entries):
            count += 1
            mod, name = path.split(".")
            try:
                rna = getattr(getattr(bpy.ops, mod), name).get_rna_type()
                invalid = []
                for key, value in props.items():
                    prop = rna.properties.get(key)
                    if prop is None:
                        invalid.append(key)
                    elif prop.type == "ENUM" and not prop.is_enum_flag and value not in prop.enum_items.keys():
                        invalid.append([key, value, list(prop.enum_items.keys())])
                check(f"menu contract: {title} / {label}", not invalid, invalid)
            except Exception as exc:
                check(f"menu contract: {title} / {label}", False, str(exc))
    results["menu_operator_entries"] = count
    source = ast.parse((ROOT / "landfall_studio/ui/shelf.py").read_text(encoding="utf-8"))
    fn = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "execute_shelf_item")
    handled = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "iid":
            for comparator in node.comparators:
                handled.update(n.value for n in ast.walk(comparator) if isinstance(n, ast.Constant) and isinstance(n.value, str))
    shelf_ids = {s["id"] for tab in shelf.SHELF_TABS.values() for s in tab}
    check("all shelf IDs dispatch", not (shelf_ids-handled), sorted(shelf_ids-handled))
    results["shelf_ids"] = len(shelf_ids)
    check("unknown action reports error", not shelf.execute_shelf_item("__unknown__")["ok"])
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.mesh.primitive_cube_add()
    target = bpy.context.active_object
    bpy.ops.mesh.primitive_cube_add(location=(1, 0, 0))
    operand = bpy.context.active_object
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    res = menus._boolean("UNION")
    bpy.context.view_layer.update()
    evaluated = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
    check("Union joins selected operand", res["ok"] and max(v.co.x for v in evaluated.data.vertices) > 1.5)
    target.modifiers.clear()
    res = menus._boolean("DIFFERENCE")
    bpy.context.view_layer.update()
    evaluated = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
    check("Difference subtracts selected operand", res["ok"] and max(v.co.x for v in evaluated.data.vertices) < .1)
    check("Boolean preserves source meshes", len(target.data.vertices) == 8 and len(operand.data.vertices) == 8)
    res = menus._assign_new_material()
    check("Assign New Material assigns selected meshes", res["ok"] and target.active_material == operand.active_material and target.active_material.use_nodes)
    for kind in ("CHILD_OF", "COPY_LOCATION", "COPY_ROTATION", "COPY_SCALE", "DAMPED_TRACK"):
        res = menus._constraint(kind)
        check("Constraint has a selected driver: " + kind,
              res["ok"] and target.constraints[-1].target == operand)
        target.constraints.clear()
    landfall_studio.unregister()
    check("navigation preference restored", bpy.context.preferences.inputs.view_zoom_axis == original_axis)


try:
    main()
except Exception:
    results["failed"].append({"exception": traceback.format_exc()})
results["ok"] = not results["failed"]
(ROOT / "output/controls_data_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print("CONTROLS_DATA_RESULT:" + json.dumps(results), flush=True)
sys.exit(0 if results["ok"] else 1)
