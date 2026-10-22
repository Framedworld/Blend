"""Phase 11 headless checks: rev 2 menus + Phase 1 hybrid windows and Modifier Stack (`tests/test_phase11_headless.py`).

Run: blender --background --factory-startup --python tests/test_phase11_headless.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import landfall_studio
from landfall_studio.ui import hybrid_window, main_menu, menus, modifier_stack

results = {"passed": [], "failed": []}


def check(name, cond, detail=""):
    (results["passed"] if cond else results["failed"]).append(name if cond else f"{name}: {detail}")


def main():
    landfall_studio.register()

    # 1. Every operator referenced by the Main Menu Bar, menu sets, and Windows menu exists
    missing = sorted({op for _t, entries in menus.all_menu_entries() for op in menus.iter_ops(entries) if not menus.op_exists(op)})
    check("menu operators all exist", not missing, missing)

    # 2. Menu sets switch the right-hand menus
    for name, first in (("Rigging  [F3]", "Skeleton"), ("Animation", "Key"), ("FX", "Physics"), ("Rendering", "Lighting/Shading"), ("Modeling", "Mesh")):
        res = main_menu.set_menu_set(name)
        check(f"menu set {name.split()[0]}", res["menus"][0] == first, res)

    # 3. Windows menu covers every hosted editor window and each spec has a valid editor type
    win_keys = {e[2].__closure__[0].cell_contents for e in menus.WINDOWS_MENU if e[0] == "FN" and e[2].__name__ == "_open"}
    check("windows menu lists all hosted editors", win_keys == set(hybrid_window.EDITOR_WINDOWS) - {"HYPERSHADE_GRAPH"} | {"HYPERSHADE_GRAPH"}, sorted(set(hybrid_window.EDITOR_WINDOWS) - win_keys))
    from blendertk.ui_utils._ui_utils import EDITOR_TYPES

    area_types = set(EDITOR_TYPES.values()) | {"INFO"}  # Area.ui_type items are context-dependent (empty headless)
    bad = [k for k, spec in hybrid_window.EDITOR_WINDOWS.items() if spec["ui_type"] not in area_types or any(t not in area_types for _s, t, _p in spec.get("splits", ()))]
    check("hosted editor ui_types valid", not bad, bad)
    res = hybrid_window.open_editor_window("GEOMETRY_NODE_EDITOR")
    check("editor windows refuse cleanly in background", res["ok"] is False and "GUI" in res.get("error", ""), res)

    # 4. Modifier Stack data API
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    for t in ("BEVEL", "SUBSURF", "NODES", "ARMATURE"):
        r = modifier_stack.add_modifier(t)
        check(f"add {t}", r["ok"], r)
    snap = modifier_stack.get_modifier_stack_snapshot(obj)
    names = [m["name"] for m in snap["modifiers"]]
    cats = [m["category"] for m in snap["modifiers"]]
    check("snapshot order + categories", cats == ["GENERATE", "GENERATE", "NODES", "DEFORM"], cats)
    bevel = snap["modifiers"][0]
    check("bevel exposes channel box attrs", {a["name"] for a in bevel["attrs"]} >= {"width", "segments"}, bevel["attrs"])
    gn = snap["modifiers"][2]
    check("geometry nodes card summary", gn["summary"].startswith("Geometry Nodes"), gn["summary"])

    r = modifier_stack.move_modifier(names[3], 0, obj)
    check("move armature to top", r.get("order", [None])[0] == names[3], r)
    r = modifier_stack.set_modifier_toggle(names[0], "V", False, obj)
    check("toggle viewport", r["ok"] and obj.modifiers[names[0]].show_viewport is False, r)
    r = modifier_stack.set_active_modifier(names[2], obj)
    check("set active modifier", r["ok"] and obj.modifiers.active.name == names[2], r)
    modifier_stack.set_order_mode("MAYA")
    check("maya order mode", modifier_stack.get_modifier_stack_snapshot(obj)["order"] == "MAYA")
    modifier_stack.set_order_mode("BLENDER")
    r = modifier_stack.duplicate_modifier(names[1], obj)
    check("duplicate subsurf", r["ok"] and len(obj.modifiers) == 5, r)
    r = modifier_stack.apply_modifier(names[1], obj)
    check("apply subsurf", r["ok"] and obj.modifiers.get(names[1]) is None, r)
    r = modifier_stack.remove_modifier(names[0], obj)
    check("remove bevel", r["ok"] and obj.modifiers.get(names[0]) is None, r)

    out = {"suite": "phase11_headless", "passed": len(results["passed"]), "failed": results["failed"]}
    print("PHASE11_HEADLESS_RESULT:" + json.dumps(out), flush=True)
    landfall_studio.unregister()


try:
    main()
except Exception:
    import traceback

    print("PHASE11_HEADLESS_RESULT:" + json.dumps({"crash": traceback.format_exc()}), flush=True)
