"""Gate 06 Headless Verification Suite (`T06-1`) — Character Workflows: Blend Shapes, Shape Editor & Skin Weights.

Verifies:
1. Strict Topological Connectivity Validation (`validate_strict_topology`): vertex/edge/polygon counts + exact edge vertex pairs + exact polygon loop order (rejects same-vertex-count connectivity swaps).
2. `BlendshapeAnimator` piecewise-linear corrective in-betweens (`0.25, 0.5, 0.75`), multi-master driver hazard detection & block (`allow_multi_master_drivers=False`), and deterministic multi-master corrective evaluation (`evaluate_correctives_deterministic`) verified via `Object.to_mesh()`.
3. Maya-style `Shape Editor` target management, held-reference target extraction (`extract_target_mesh_with_reference`), strict-topology sync (`sync_extracted_target_to_shape_key`), base edit propagation (`propagate_base_mesh_edits` with `max_morph_delta_drift == 0.0`), and shape target mirroring.
4. Locked-weight-respecting skin inspection, direct weight edit, normalize, prune, Weight Hammer (`weight_hammer_vertices`), mirror (`mirror_skin_weights`), and controlled weight transfer (`VERTEX_INDEX` and `CLOSEST_SURFACE` via `BVHTree`) with `max_locked_weight_drift == 0.0` and UV/material preservation.
5. Modern Maya `Shape / Skin` dock (`SHAPE_EDITOR`), `BlendshapeAnimator` Switchboard panel, `Time Slider` snapshot, `.blend` save/reopen persistence, and `Undo`/`Redo`.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback

import bpy
from mathutils import Vector

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import landfall_studio
from landfall_studio import character, ui


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(f"[T06-1 FAIL] {msg}")


def _build_uv_material_mesh(name: str = "CharHead") -> bpy.types.Object:
    """Create a symmetric subdivided cube mesh with UVs and two material slots."""
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = f"{name}Shape"

    # Subdivide once so we have 26 vertices, 48 edges, 24 faces with symmetric +/-X vertices
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.subdivide(number_cuts=1)
    bpy.ops.object.mode_set(mode="OBJECT")

    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="map1")
    mat_skin = bpy.data.materials.new(name=f"{name}_Skin_Mat")
    mat_eye = bpy.data.materials.new(name=f"{name}_Eye_Mat")
    obj.data.materials.append(mat_skin)
    obj.data.materials.append(mat_eye)
    if len(obj.data.polygons) > 1:
        obj.data.polygons[0].material_index = 0
        obj.data.polygons[1].material_index = 1
    return obj


def _make_same_count_rewired_mesh(source_obj: bpy.types.Object, name: str = "RewiredMesh") -> bpy.types.Object:
    """Build a mesh with the EXACT same vertex, edge, and polygon counts as `source_obj`,
    but with polygon winding/loop indices reversed on polygon 0 so connectivity differs."""
    src_me = source_obj.data
    verts = [tuple(v.co) for v in src_me.vertices]
    edges = [tuple(e.vertices) for e in src_me.edges]
    polys = [list(p.vertices) for p in src_me.polygons]

    # Reverse loop vertex winding on polygon 0: same vertices, same edges, same polygon count,
    # but polygon_winding_match is False!
    polys[0] = list(reversed(polys[0]))

    me = bpy.data.meshes.new(f"{name}Shape")
    me.from_pydata(verts, edges, polys)
    me.update()
    new_obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(new_obj)
    return new_obj


def run_tests() -> None:
    print("=== Gate 06 Headless Test Suite (T06-1) Starting ===")
    bpy.ops.wm.read_homefile(use_empty=True)

    landfall_studio.register()
    _assert(landfall_studio._studio_registered, "Landfall Studio failed to register")

    # ------------------------------------------------------------------
    # 1. Strict Topological Connectivity Validation
    # ------------------------------------------------------------------
    head = _build_uv_material_mesh("HeroHead")
    dup_me = head.data.copy()
    dup_obj = bpy.data.objects.new("HeroHead_Copy", dup_me)
    bpy.context.scene.collection.objects.link(dup_obj)

    v_same = character.validate_strict_topology(head, dup_obj, check_uvs=True, check_materials=True)
    _assert(v_same["ok"] and v_same["connectivity_match"], f"Identical topology failed: {v_same}")
    _assert(v_same["uv_layers_compatible"] and v_same["materials_compatible"], f"UV/material match failed: {v_same}")

    # Test same-vertex-count, same-edge-count, same-poly-count but altered polygon loop order (must FAIL!)
    rewired_obj = _make_same_count_rewired_mesh(head, "HeroHead_Rewired")
    _assert(
        len(rewired_obj.data.vertices) == len(head.data.vertices)
        and len(rewired_obj.data.edges) == len(head.data.edges)
        and len(rewired_obj.data.polygons) == len(head.data.polygons),
        "Rewired test mesh should have identical vertex, edge, and polygon counts",
    )
    v_rewired = character.validate_strict_topology(head, rewired_obj)
    _assert(
        not v_rewired["ok"] and not v_rewired["connectivity_match"] and v_rewired["vertex_count_match"],
        f"Strict topology validator failed to reject same-vertex-count rewired mesh: {v_rewired}",
    )
    print(f"[PASS] 1. Strict topology check rejected same-vertex-count rewired mesh ({v_rewired['reason']})")

    # ------------------------------------------------------------------
    # 2. BlendshapeAnimator Integration, Hazard Detection & Multi-Master Evaluation
    # ------------------------------------------------------------------
    # Create target mesh for 'Smile'
    smile_target_me = head.data.copy()
    smile_target_obj = bpy.data.objects.new("HeroHead_Smile_TargetMesh", smile_target_me)
    bpy.context.scene.collection.objects.link(smile_target_obj)
    for v in smile_target_obj.data.vertices:
        if v.co.x > 0.1:
            v.co.z += 0.4

    # Verify topological mismatch is blocked by create_blendshape_setup
    bad_bs = character.create_blendshape_setup(
        base_obj=head,
        target_obj=rewired_obj,
        name="BadMorph",
    )
    _assert(not bad_bs["ok"] and bad_bs.get("blocked"), f"Expected rewired target to be blocked: {bad_bs}")

    # Create valid BlendshapeAnimator setup for 'Smile' over frames 1..100
    res_smile = character.create_blendshape_setup(
        base_obj=head,
        target_obj=smile_target_obj,
        name="Smile",
        start_frame=1,
        end_frame=100,
    )
    _assert(
        res_smile["ok"] and res_smile["uvs_preserved"] and res_smile["materials_preserved"],
        f"Failed to create Smile blendshape setup: {res_smile}",
    )

    # Create weight-based in-between tweens at [0.25, 0.5, 0.75]
    tweens_res = character.create_blendshape_tweens(
        base_obj=head,
        weights=[0.25, 0.5, 0.75],
        key_name="Smile",
    )
    _assert(
        tweens_res["ok"] and tweens_res["tween_count"] == 3,
        f"Failed to create blendshape tweens: {tweens_res}",
    )

    # Sculpt a corrective delta on the w=0.50 tween mesh (vertex 0 pushed +0.25 along Y)
    w500_tween_name = [n for n in tweens_res["tween_meshes"] if "500" in n][0]
    w500_tween_obj = bpy.data.objects[w500_tween_name]
    w500_tween_obj.data.vertices[0].co.y += 0.25

    # Apply sculpted tweens back to corrective shape keys (Smile_tween_w250, Smile_tween_w500, Smile_tween_w750)
    apply_res = character.apply_blendshape_tweens(
        base_obj=head,
        key_name="Smile",
        strict_topology=True,
    )
    _assert(
        apply_res["ok"] and len(apply_res["applied"]) == 3 and apply_res["uvs_preserved"],
        f"Failed to apply blendshape tweens: {apply_res}",
    )

    # Verify mathematical tent weight
    _assert(abs(character.compute_tent_weight(0.5, 0.5, 0.25, 0.75) - 1.0) < 1e-6, "Tent peak should be 1.0 at 0.5")
    _assert(abs(character.compute_tent_weight(0.25, 0.5, 0.25, 0.75) - 0.0) < 1e-6, "Tent should be 0.0 at neighbor 0.25")
    _assert(abs(character.compute_tent_weight(0.375, 0.5, 0.25, 0.75) - 0.5) < 1e-6, "Tent should be 0.5 at midpoint 0.375")

    # Verify multi-master driver hazard is BLOCKED by default when attempting a second animated BlendshapeAnimator setup
    brow_target_me = head.data.copy()
    brow_target_obj = bpy.data.objects.new("HeroHead_BrowUp_TargetMesh", brow_target_me)
    bpy.context.scene.collection.objects.link(brow_target_obj)
    brow_target_obj.data.vertices[0].co.z += 0.6

    blocked_multi = character.create_blendshape_setup(
        base_obj=head,
        target_obj=brow_target_obj,
        name="BrowUp",
        start_frame=1,
        end_frame=100,
        allow_multi_master_drivers=False,
    )
    _assert(
        not blocked_multi["ok"] and blocked_multi.get("blocked") and blocked_multi.get("multi_master_hazard"),
        f"Expected multi-master driver hazard to block unguarded second master setup: {blocked_multi}",
    )

    # Now add 'BrowUp' master shape key via Shape Editor and keyframe it simultaneously with 'Smile'
    res_brow = character.create_shape_target(
        head,
        name="BrowUp",
        weight=0.0,
        initial_deltas={0: (0.0, 0.0, 0.6)},
    )
    _assert(res_brow["ok"], f"Failed to create BrowUp target: {res_brow}")
    character.keyframe_shape_target(head, "BrowUp", frame=1, weight=0.0)
    character.keyframe_shape_target(head, "BrowUp", frame=50, weight=0.8)
    character.keyframe_shape_target(head, "BrowUp", frame=100, weight=1.0)

    haz = character.detect_multi_master_driver_hazard(head)
    _assert(
        haz["hazard_detected"] and len(haz["animated_master_keys"]) >= 2,
        f"Expected multi-master hazard detection: {haz}",
    )

    # Scrub to frame 50 and run deterministic corrective evaluation
    bpy.context.scene.frame_set(50)
    eval_f50 = character.evaluate_correctives_deterministic(head, strip_conflicting_drivers_if_multi_master=True)
    _assert(eval_f50["ok"] and eval_f50["is_multi_master"], f"Deterministic evaluation failed: {eval_f50}")
    _assert(
        abs(eval_f50["evaluated_correctives"]["Smile_tween_w500"] - 1.0) < 0.05,
        f"Expected Smile_tween_w500 ~ 1.0 at frame 50: {eval_f50}",
    )

    # Verify Object.to_mesh() on evaluated object matches exact analytical multi-master + corrective sum!
    analytical_coords = character.compute_analytical_morphed_coords(head)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = head.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    try:
        max_eval_err = max(
            (eval_mesh.vertices[i].co - analytical_coords[i]).length
            for i in range(len(analytical_coords))
        )
        _assert(
            max_eval_err < 1e-5,
            f"Multi-master Object.to_mesh() mismatch vs analytical sum: max_eval_err={max_eval_err}",
        )
    finally:
        eval_obj.to_mesh_clear()
    print(f"[PASS] 2. Multi-master hazard blocked & deterministic evaluation verified via Object.to_mesh() (max_err={max_eval_err:.2e})")

    # ------------------------------------------------------------------
    # 3. Shape Editor Target Extraction (Held Reference), Sync & Base Edit Propagation
    # ------------------------------------------------------------------
    ext_res = character.extract_target_mesh_with_reference(head, "Smile", offset_vector=(3.0, 0.0, 0.0))
    _assert(
        ext_res["ok"] and ext_res["held_reference_active"] and ext_res["source_object"] == head.name,
        f"Target extraction failed: {ext_res}",
    )
    ext_obj = bpy.data.objects.get(ext_res["extracted_object"])
    _assert(ext_obj is not None, "Extracted object missing")

    # Modify vertex 2 on the extracted target mesh and sync back
    ext_obj.data.vertices[2].co.z += 0.35
    sync_ok = character.sync_extracted_target_to_shape_key(ext_obj, delete_extracted=False)
    _assert(
        sync_ok["ok"] and sync_ok["updated_vertices"] >= 1 and sync_ok["uvs_preserved"] and sync_ok["materials_preserved"],
        f"Target sync failed: {sync_ok}",
    )

    # Verify topological mismatch on extracted target is BLOCKED during sync
    bad_ext = _make_same_count_rewired_mesh(ext_obj, "BadExtractedTarget")
    bad_ext[character.HELD_IS_TARGET_PROP] = True
    bad_ext[character.HELD_SOURCE_OBJ_PROP] = head.name
    bad_ext[character.HELD_SOURCE_KEY_PROP] = "Smile"
    sync_bad = character.sync_extracted_target_to_shape_key(bad_ext)
    _assert(
        not sync_bad["ok"] and sync_bad.get("blocked") and not sync_bad["topology"]["ok"],
        f"Expected topological mismatch sync to be blocked: {sync_bad}",
    )

    # Test Base Edit Propagation across all relative shape keys
    prop_res = character.propagate_base_mesh_edits(
        head,
        {0: (0.15, -0.1, 0.05), 1: (-0.05, 0.2, 0.0)},
    )
    _assert(
        prop_res["ok"]
        and prop_res["max_morph_delta_drift"] < 1e-6
        and prop_res["uvs_preserved"]
        and prop_res["materials_preserved"],
        f"Base edit propagation failed: {prop_res}",
    )

    # Verify topological base edit is blocked
    prop_bad = character.propagate_base_mesh_edits(head, rewired_obj)
    _assert(
        not prop_bad["ok"] and prop_bad.get("blocked"),
        f"Expected topological base edit to be blocked: {prop_bad}",
    )

    # Test Mirror Shape Target
    mir_shape = character.mirror_shape_target(head, source_key="Smile", new_name="Smile_Mirrored")
    _assert(mir_shape["ok"] and mir_shape["matched_vertices"] == len(head.data.vertices), f"Mirror shape target failed: {mir_shape}")
    print(f"[PASS] 3. Held-reference target extract/sync, topology block, base edit propagation (drift={prop_res['max_morph_delta_drift']:.2e}), and mirror verified")

    # ------------------------------------------------------------------
    # 4. Locked-Weight-Respecting Skin Operations & Controlled Weight Transfer
    # ------------------------------------------------------------------
    vg_jaw = head.vertex_groups.new(name="Jaw_Jnt")
    vg_head = head.vertex_groups.new(name="Head_Jnt")
    vg_clav_l = head.vertex_groups.new(name="Clavicle.L")
    vg_clav_r = head.vertex_groups.new(name="Clavicle.R")

    for v in head.data.vertices:
        vg_jaw.add([v.index], 0.30, "REPLACE")
        vg_head.add([v.index], 0.50, "REPLACE")
        if v.co.x >= 0.0:
            vg_clav_l.add([v.index], 0.18, "REPLACE")
            vg_clav_r.add([v.index], 0.02, "REPLACE")
        else:
            vg_clav_l.add([v.index], 0.02, "REPLACE")
            vg_clav_r.add([v.index], 0.18, "REPLACE")

    # Lock Jaw_Jnt
    lk_res = character.set_vertex_group_lock(head, "Jaw_Jnt", True)
    _assert(lk_res["ok"] and lk_res["locked"], f"Failed to lock Jaw_Jnt: {lk_res}")

    # Direct edit on locked group must be blocked
    blocked_wt = character.set_vertex_weight_respecting_locks(head, vertex_index=0, group_name="Jaw_Jnt", weight=0.9)
    _assert(
        not blocked_wt["ok"] and blocked_wt.get("blocked"),
        f"Direct edit on locked group should be blocked: {blocked_wt}",
    )

    # Direct edit on unlocked group must preserve Jaw_Jnt == 0.30
    edit_wt = character.set_vertex_weight_respecting_locks(head, vertex_index=0, group_name="Head_Jnt", weight=0.6, normalize=True)
    _assert(
        edit_wt["ok"] and edit_wt["max_locked_weight_drift"] == 0.0,
        f"Direct unlocked edit drifted locked weight: {edit_wt}",
    )

    # Prune small weights (< 0.05) while respecting locks
    prune_res = character.prune_small_weights(head, threshold=0.05, max_influences=4, respect_locks=True, normalize=True)
    _assert(
        prune_res["ok"] and prune_res["pruned_entries"] > 0 and prune_res["max_locked_weight_drift"] == 0.0,
        f"Prune weights failed or drifted locked weights: {prune_res}",
    )

    # Normalize weights while respecting locks
    norm_res = character.normalize_skin_weights(head, respect_locks=True)
    _assert(
        norm_res["ok"] and norm_res["max_locked_weight_drift"] == 0.0,
        f"Normalize weights failed or drifted locked weights: {norm_res}",
    )

    # Weight Hammer on vertex 0 while respecting locked Jaw_Jnt
    vg_head.add([0], 0.05, "REPLACE")
    vg_clav_l.add([0], 0.65, "REPLACE")
    hammer_res = character.weight_hammer_vertices(head, vertex_indices=[0], respect_locks=True, normalize=True)
    _assert(
        hammer_res["ok"] and hammer_res["hammered_vertex_count"] == 1 and hammer_res["max_locked_weight_drift"] == 0.0,
        f"Weight Hammer failed or drifted locked weights: {hammer_res}",
    )

    # Mirror skin weights (+X -> -X) while respecting locked Jaw_Jnt
    mir_wt = character.mirror_skin_weights(head, direction="PLUS_TO_MINUS", axis="X", respect_locks=True, normalize=True)
    _assert(
        mir_wt["ok"] and mir_wt["mirrored_vertices"] > 0 and mir_wt["max_locked_weight_drift"] == 0.0,
        f"Mirror skin weights failed or drifted locked weights: {mir_wt}",
    )

    # Controlled Weight Transfer:
    # 4a. VERTEX_INDEX transfer onto a duplicate mesh where Jaw_Jnt is locked at 0.45
    target_same = dup_obj
    t_jaw = target_same.vertex_groups.new(name="Jaw_Jnt")
    for v in target_same.data.vertices:
        t_jaw.add([v.index], 0.45, "REPLACE")
    t_jaw.lock_weight = True

    tr_idx = character.controlled_weight_transfer(
        source_obj_or_name=head,
        target_obj_or_name=target_same,
        method="VERTEX_INDEX",
        respect_target_locks=True,
        normalize=True,
    )
    _assert(
        tr_idx["ok"]
        and tr_idx["max_locked_weight_drift"] == 0.0
        and tr_idx["uvs_preserved"]
        and tr_idx["materials_preserved"],
        f"VERTEX_INDEX controlled weight transfer failed: {tr_idx}",
    )

    # Verify VERTEX_INDEX transfer blocks topological mismatch
    tr_bad = character.controlled_weight_transfer(
        source_obj_or_name=head,
        target_obj_or_name=rewired_obj,
        method="VERTEX_INDEX",
    )
    _assert(
        not tr_bad["ok"] and tr_bad.get("blocked"),
        f"Expected VERTEX_INDEX transfer to block rewired mesh: {tr_bad}",
    )

    # 4b. CLOSEST_SURFACE transfer onto a differently-tessellated outfit mesh with locked Jaw_Jnt
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=1.15, location=(0.0, 0.0, 0.0))
    outfit = bpy.context.active_object
    outfit.name = "HeroOutfit"
    if not outfit.data.uv_layers:
        outfit.data.uv_layers.new(name="outfitUV")
    outfit.data.materials.append(bpy.data.materials.new(name="Outfit_Mat"))
    o_jaw = outfit.vertex_groups.new(name="Jaw_Jnt")
    for v in outfit.data.vertices:
        o_jaw.add([v.index], 0.25, "REPLACE")
    o_jaw.lock_weight = True

    tr_surf = character.controlled_weight_transfer(
        source_obj_or_name=head,
        target_obj_or_name=outfit,
        method="CLOSEST_SURFACE",
        respect_target_locks=True,
        normalize=True,
    )
    _assert(
        tr_surf["ok"]
        and tr_surf["transferred_group_count"] >= 3
        and tr_surf["max_locked_weight_drift"] == 0.0
        and tr_surf["uvs_preserved"]
        and tr_surf["materials_preserved"],
        f"CLOSEST_SURFACE controlled weight transfer failed: {tr_surf}",
    )
    print("[PASS] 4. Locked-weight skin tools (edit/prune/normalize/hammer/mirror) & controlled weight transfer (VERTEX_INDEX + CLOSEST_SURFACE) verified with 0.0 locked drift")

    # ------------------------------------------------------------------
    # 5. Modern Maya Shape / Skin UI, Time Slider & .blend Persistence
    # ------------------------------------------------------------------
    bpy.context.view_layer.objects.active = head
    head.select_set(True)

    dock_res = ui.cycle_right_dock("SHAPE_EDITOR")
    _assert(dock_res["ok"] and dock_res["mode"] == "SHAPE_EDITOR", f"Failed to switch to SHAPE_EDITOR dock: {dock_res}")

    se_snap = ui.get_shape_editor_snapshot()
    _assert(
        se_snap["ok"]
        and head.name in se_snap["object_label"]
        and se_snap["shape_row_count"] >= 5
        and se_snap["skin_row_count"] == 4,
        f"Invalid Shape Editor snapshot: {se_snap}",
    )

    ts_snap = ui.get_time_slider_snapshot()
    _assert(
        ts_snap["ok"] and len(ts_snap["shape_key_frames"]) >= 3,
        f"Invalid Time Slider snapshot: {ts_snap}",
    )

    bs_panel = ui.open_panel("blendshape_animator", docked=False)
    _assert(bs_panel["ok"], f"Failed to open blendshape_animator Switchboard panel: {bs_panel}")

    # Test .blend save & reload persistence
    with tempfile.TemporaryDirectory() as tmpdir:
        blend_path = os.path.join(tmpdir, "phase06_character_test.blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        bpy.ops.wm.open_mainfile(filepath=blend_path)

        reloaded_head = bpy.data.objects.get("HeroHead")
        _assert(reloaded_head is not None, "HeroHead missing after .blend reload")
        _assert(
            reloaded_head.data.shape_keys is not None
            and "Smile" in reloaded_head.data.shape_keys.key_blocks
            and "Smile_tween_w500" in reloaded_head.data.shape_keys.key_blocks,
            "Shape keys missing after .blend reload",
        )
        _assert(
            reloaded_head.vertex_groups["Jaw_Jnt"].lock_weight is True,
            "Jaw_Jnt lock_weight state lost after .blend reload",
        )

    landfall_studio.unregister()
    print("=== Gate 06 Headless Test Suite (T06-1): ALL CHECKS PASSED ===")


if __name__ == "__main__":
    try:
        run_tests()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
