"""Maya-like viewport interaction operators for Landfall Studio (Phase 02).

Implements:
- `landfall_studio.select_tool` (`Q / W / E / R` persistent gizmo & active-axis state)
- `landfall_studio.select_last_tool` (`Y` recall last non-select transform tool)
- `landfall_studio.repeat_last_command` (`G` repeat last command across Studio/blendertk/Tentacle/Blender)
- `landfall_studio.component_mode` (`F8–F12` & `RMB` seamless Object↔Edit component switching with cursor raycast)
- `landfall_studio.convert_selection` (`Ctrl+RMB` component conversion: Verts, Edges, Faces, Loop, Ring, Boundary)
- `landfall_studio.pivot_edit_modal` (`Hold D` temporary pivot editing + `X/C/V` grid/edge/vertex pivot snapping with guaranteed restore)
- `landfall_studio.temp_snap_modal` (`Hold X / C / V` temporary grid/edge/vertex snap with guaranteed restore)
- `landfall_studio.mmb_virtual_slider` (`MMB-drag` in open viewport along active manipulator axis)
- `landfall_studio.frame_all` (`A` frame all objects/components in 3D View)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import bmesh
import bpy
import mathutils
from bpy_extras import view3d_utils

from ..adapters import landfall_bridge
from ..commands import registry as cmd_registry

GIZMO_FLAGS = (
    "show_gizmo_object_translate",
    "show_gizmo_object_rotate",
    "show_gizmo_object_scale",
)

TOOL_TO_GIZMO_FLAGS: Dict[str, Tuple[bool, bool, bool]] = {
    "SELECT": (False, False, False),
    "TRANSLATE": (True, False, False),
    "ROTATE": (False, True, False),
    "RESIZE": (False, False, True),
}

# Active modal state snapshot so tests and cancel handlers can inspect or force-restore
_pivot_modal_state: Dict[str, Any] = {
    "active": False,
    "snap_mode": "NONE",
    "saved_origin_flag": False,
    "saved_use_snap": False,
    "saved_snap_elements": set(),
    "saved_pivot_point": "MEDIAN_POINT",
    "saved_gizmo_flags": (True, False, False),
    "saved_active_tool": "TRANSLATE",
}


def get_pivot_modal_state() -> Dict[str, Any]:
    """Return a copy of the current pivot-edit modal state for diagnostics and tests."""
    return dict(_pivot_modal_state)


def apply_gizmo_for_tool(context, tool: str) -> Tuple[bool, bool, bool]:
    """Activate the real viewport tool as well as its persistent manipulator."""
    norm = (tool or "TRANSLATE").upper()
    flags = TOOL_TO_GIZMO_FLAGS.get(norm, (True, False, False))

    # Flags alone leave Blender's previous tool (often Select Box) active. The
    # active tool owns drag handling and its own keymap, so it must agree with
    # the Studio tool shown in the shelf and Channel Box.
    native_tool = {"SELECT": "builtin.select_box", "TRANSLATE": "builtin.move",
                   "ROTATE": "builtin.rotate", "RESIZE": "builtin.scale"}.get(norm)
    if native_tool and not bpy.app.background:
        for win in context.window_manager.windows:
            for area in win.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                if region is None:
                    continue
                with context.temp_override(window=win, screen=win.screen, area=area, region=region):
                    if context.mode in {"OBJECT", "EDIT_MESH", "POSE"}:
                        active = win.workspace.tools.from_space_view3d_mode(context.mode, create=False)
                        if active is None or active.idname != native_tool:
                            bpy.ops.wm.tool_set_by_id(name=native_tool)

    lf_mod = landfall_bridge.get_module()
    if lf_mod is not None:
        p = lf_mod.prefs(context)
        if p is not None:
            try:
                p.gizmo_flags = list(flags)
            except Exception:
                pass
        if hasattr(lf_mod, "_gizmos_attempts") and hasattr(lf_mod, "GIZMO_ROUNDS"):
            try:
                lf_mod._gizmos_attempts[0] = lf_mod.GIZMO_ROUNDS
            except Exception:
                pass
        if hasattr(lf_mod, "_gizmos_apply"):
            try:
                lf_mod._gizmos_apply(flags)
            except Exception:
                pass

    # Ensure all active and workspace VIEW_3D spaces reflect the gizmo flags
    for ws in bpy.data.workspaces:
        for screen in ws.screens:
            for area in screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        try:
                            space.show_gizmo = True
                            for attr, val in zip(GIZMO_FLAGS, flags):
                                setattr(space, attr, val)
                        except Exception:
                            pass
    return flags


def find_view3d_area_region(context) -> Tuple[Optional[Any], Optional[Any]]:
    """Find the active or first available `VIEW_3D` `(area, window_region)`."""
    if getattr(context, "area", None) is not None and context.area.type == "VIEW_3D":
        reg = getattr(context, "region", None)
        if reg is not None and reg.type == "WINDOW":
            return context.area, reg
        for r in context.area.regions:
            if r.type == "WINDOW":
                return context.area, r

    wm = getattr(context, "window_manager", None)
    if wm is None:
        return None, None
    for win in wm.windows:
        if win.screen is None:
            continue
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for r in area.regions:
                    if r.type == "WINDOW":
                        return area, r
    return None, None


def raycast_mesh_at_region_xy(
    context,
    region_x: float,
    region_y: float,
    area=None,
    region=None,
) -> Tuple[Optional[Any], Optional[mathutils.Vector]]:
    """Raycast into the scene from `(region_x, region_y)` in a `VIEW_3D` region.
    Returns `(hit_mesh_object, hit_world_location)` or `(None, None)`."""
    if area is None or region is None:
        area, region = find_view3d_area_region(context)
    if area is None or region is None:
        return None, None

    rv3d = getattr(context, "region_data", None)
    if rv3d is None:
        for sp in area.spaces:
            if sp.type == "VIEW_3D":
                rv3d = sp.region_3d
                break
    if rv3d is None:
        return None, None

    coord = (float(region_x), float(region_y))
    try:
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        depsgraph = context.evaluated_depsgraph_get()
        hit, location, _normal, _index, obj, _matrix = context.scene.ray_cast(
            depsgraph, origin, direction
        )
        if hit and obj is not None and obj.type == "MESH":
            return obj, location
    except Exception:
        pass
    return None, None


def snap_object_pivot_world(obj, target_world: mathutils.Vector) -> mathutils.Vector:
    """Move `obj`'s origin/pivot to `target_world` without moving world-space geometry, shape keys, instanced copies, or child objects."""
    if obj is None or obj.type != "MESH" or obj.data is None:
        raise ValueError("Pivot snap requires an active MESH object.")

    target_vec = mathutils.Vector(target_world)
    old_world_mat = obj.matrix_world.copy()
    inv_old_world = old_world_mat.inverted_safe()

    old_origin_world = old_world_mat.translation.copy()
    delta_world = target_vec - old_origin_world
    if delta_world.length < 1e-8:
        return target_vec

    # Convert new world origin into local-space offset for vertices
    new_origin_local = inv_old_world @ target_vec

    # Find any instanced mesh users sharing obj.data so their world-space geometry does not shift
    instanced_users = [
        o for o in bpy.data.objects
        if o is not obj and getattr(o, "type", "") == "MESH" and o.data is obj.data
    ]

    # Preserve direct children world matrices (for obj and any instanced users)
    children_world = [(child, child.matrix_world.copy()) for child in obj.children]
    for inst_obj in instanced_users:
        for child in inst_obj.children:
            children_world.append((child, child.matrix_world.copy()))

    sk = getattr(obj.data, "shape_keys", None)
    kb_pre_first = {}
    if sk is not None and sk.key_blocks:
        for kb in sk.key_blocks:
            if len(kb.data) > 0:
                kb_pre_first[kb.name] = kb.data[0].co.copy()

    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        bmesh.ops.translate(bm, verts=bm.verts, vec=-new_origin_local)
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    else:
        obj.data.transform(mathutils.Matrix.Translation(-new_origin_local))
        obj.data.update()

    # Ensure all shape keys (Basis and all non-basis targets) are shifted by -new_origin_local
    if sk is not None and sk.key_blocks:
        for kb in sk.key_blocks:
            if len(kb.data) == 0:
                continue
            pre_co0 = kb_pre_first.get(kb.name)
            expected_co0 = (pre_co0 - new_origin_local) if pre_co0 is not None else None
            if expected_co0 is not None and (kb.data[0].co - expected_co0).length > 1e-6:
                for pt in kb.data:
                    pt.co -= new_origin_local
        sk.update_tag()

    # Update object world translation
    new_world_mat = old_world_mat.copy()
    new_world_mat.translation = target_vec
    obj.matrix_world = new_world_mat

    # Counter-translate any instanced objects sharing obj.data so their world-space vertices remain stationary
    local_shift_mat = mathutils.Matrix.Translation(new_origin_local)
    for inst_obj in instanced_users:
        try:
            inst_obj.matrix_world = inst_obj.matrix_world @ local_shift_mat
        except Exception:
            pass

    for child, c_world in children_world:
        try:
            child.matrix_world = c_world
        except Exception:
            pass

    return target_vec


def compute_pivot_snap_target(
    context,
    obj,
    snap_mode: str,
    region_x: Optional[float] = None,
    region_y: Optional[float] = None,
    explicit_target: Optional[Tuple[float, float, float]] = None,
) -> mathutils.Vector:
    """Compute a world-space pivot snap target for `VERTEX`, `EDGE`, or `GRID`."""
    if explicit_target is not None:
        return mathutils.Vector(explicit_target)

    mode = (snap_mode or "VERTEX").upper()
    mesh = obj.data
    mw = obj.matrix_world

    # Optional 2D screen-distance weighting if region coordinates are provided
    area, region = find_view3d_area_region(context)
    rv3d = None
    if area is not None:
        for sp in area.spaces:
            if sp.type == "VIEW_3D":
                rv3d = sp.region_3d
                break

    def _dist_metric(world_pt: mathutils.Vector) -> float:
        if (
            region_x is not None
            and region_y is not None
            and region_x >= 0
            and region_y >= 0
            and region is not None
            and rv3d is not None
        ):
            proj = view3d_utils.location_3d_to_region_2d(region, rv3d, world_pt)
            if proj is not None:
                return (proj.x - region_x) ** 2 + (proj.y - region_y) ** 2
        return (world_pt - mw.translation).length_squared

    if mode == "VERTEX":
        if obj.mode == "EDIT":
            bm = bmesh.from_edit_mesh(mesh)
            verts_world = [mw @ v.co for v in bm.verts]
        else:
            verts_world = [mw @ v.co for v in mesh.vertices]
        if not verts_world:
            return mw.translation.copy()
        # Pick the closest vertex (or furthest from origin if no cursor coord is given and origin is at center)
        if region_x is not None and region_x >= 0:
            return min(verts_world, key=_dist_metric)
        return max(verts_world, key=lambda p: (p - mw.translation).length_squared)

    if mode == "EDGE":
        if obj.mode == "EDIT":
            bm = bmesh.from_edit_mesh(mesh)
            mids_world = [
                mw @ ((e.verts[0].co + e.verts[1].co) * 0.5) for e in bm.edges
            ]
        else:
            verts = mesh.vertices
            mids_world = [
                mw @ ((verts[e.vertices[0]].co + verts[e.vertices[1]].co) * 0.5)
                for e in mesh.edges
            ]
        if not mids_world:
            return mw.translation.copy()
        if region_x is not None and region_x >= 0:
            return min(mids_world, key=_dist_metric)
        return max(mids_world, key=lambda p: (p - mw.translation).length_squared)

    if mode in ("GRID", "INCREMENT"):
        cell = float(getattr(context.scene, "landfall_grid_cell", 1.0) or 1.0)
        loc = mw.translation
        return mathutils.Vector(
            (
                round(loc.x / cell) * cell,
                round(loc.y / cell) * cell,
                round(loc.z / cell) * cell,
            )
        )

    return mw.translation.copy()


def _refresh_help_line() -> None:
    """Update the Help Line (bottom bar) for the newly active tool."""
    try:
        from ..ui import time_slider

        time_slider.refresh_time_slider_widgets()
    except Exception:
        pass


_last_marquee = {}


class LANDFALL_STUDIO_OT_set_key(bpy.types.Operator):
    """Set transform keys on the selected objects (Maya S)."""
    bl_idname = "landfall_studio.set_key"
    bl_label = "Set Key"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        keyed = 0
        for obj in context.selected_objects:
            if obj.library is not None:
                continue
            rotation = "rotation_quaternion" if obj.rotation_mode == "QUATERNION" else (
                "rotation_axis_angle" if obj.rotation_mode == "AXIS_ANGLE" else "rotation_euler")
            for path in ("location", rotation, "scale"):
                obj.keyframe_insert(data_path=path, group="Transforms")
            shape_keys = getattr(getattr(obj, "data", None), "shape_keys", None)
            if shape_keys is not None:
                from .. import character
                for target in shape_keys.key_blocks[1:]:
                    if "_tween_w" not in target.name:
                        character.keyframe_shape_target(obj, target.name)
            keyed += 1
        return {"FINISHED"} if keyed else {"CANCELLED"}


class LANDFALL_STUDIO_OT_maya_box_select(bpy.types.Operator):
    """Marquee selection from any Maya tool; gizmo handlers keep transform drags."""
    bl_idname = "landfall_studio.maya_box_select"
    bl_label = "Maya Marquee Selection"
    mode: bpy.props.EnumProperty(items=tuple((v, v.title(), "") for v in ("SET", "ADD", "SUB", "XOR")))

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D" and context.mode in {"OBJECT", "EDIT_MESH"}

    def invoke(self, context, event):
        _last_marquee.update(mode=self.mode, finished=False)
        self._x0 = event.mouse_prev_press_x - context.region.x
        self._y0 = event.mouse_prev_press_y - context.region.y
        self._x1, self._y1 = event.mouse_region_x, event.mouse_region_y
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), "WINDOW", "POST_PIXEL")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _draw(self):
        import gpu
        from gpu_extras.batch import batch_for_shader
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        points = [(self._x0, self._y0), (self._x1, self._y0),
                  (self._x1, self._y1), (self._x0, self._y1), (self._x0, self._y0)]
        shader.bind()
        shader.uniform_float("color", (0.22, 0.64, 0.85, 1.0))
        batch_for_shader(shader, "LINE_STRIP", {"pos": points}).draw(shader)

    def cancel(self, context):
        if getattr(self, "_handle", None) is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        context.area.tag_redraw()

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self.cancel(context)
            return {"CANCELLED"}
        if event.type == "MOUSEMOVE":
            self._x1, self._y1 = event.mouse_region_x, event.mouse_region_y
            context.area.tag_redraw()
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            _last_marquee["finished"] = True
            self.cancel(context)
            # Execute with an explicit mode. Blender's generic box gesture
            # interprets Shift/Ctrl itself; use our explicit selection policy.
            return bpy.ops.view3d.select_box(
                xmin=int(min(self._x0, self._x1)), xmax=int(max(self._x0, self._x1)),
                ymin=int(min(self._y0, self._y1)), ymax=int(max(self._y0, self._y1)),
                mode=self.mode, wait_for_input=False)
        return {"RUNNING_MODAL"}


class LANDFALL_STUDIO_OT_maya_select(bpy.types.Operator):
    """Maya modifier selection: Ctrl removes; Ctrl+Shift adds without toggling."""
    bl_idname = "landfall_studio.maya_select"
    bl_label = "Maya Modified Selection"
    bl_options = {"UNDO"}
    action: bpy.props.EnumProperty(items=(("REMOVE", "Remove", ""), ("ADD", "Add", "")))

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D" and context.mode in {"OBJECT", "EDIT_MESH"}

    def invoke(self, context, event):
        return bpy.ops.view3d.select(
            location=(event.mouse_region_x, event.mouse_region_y),
            deselect=self.action == "REMOVE", extend=self.action == "ADD",
            toggle=False, deselect_all=False, enumerate=False)


class LANDFALL_STUDIO_OT_select_tool(bpy.types.Operator):
    """Select active Maya tool (`Q` Select, `W` Move, `E` Rotate, `R` Scale) with persistent manipulator."""

    bl_idname = "landfall_studio.select_tool"
    bl_label = "Select Maya Tool (Q/W/E/R)"
    bl_description = "Activate Select (Q), Move (W), Rotate (E), or Scale (R) persistent manipulator"

    @classmethod
    def poll(cls, context):
        return context.mode in {"OBJECT", "EDIT_MESH", "POSE"}

    tool: bpy.props.EnumProperty(
        name="Tool",
        items=(
            ("SELECT", "Select (Q)", "Selection mode (hide transform gizmos)"),
            ("TRANSLATE", "Move (W)", "Move tool with persistent translate gizmo"),
            ("ROTATE", "Rotate (E)", "Rotate tool with persistent rotate gizmo"),
            ("RESIZE", "Scale (R)", "Scale tool with persistent scale gizmo"),
        ),
        default="TRANSLATE",
        options={"SKIP_SAVE"},
    )
    axis: bpy.props.EnumProperty(
        name="Active Axis",
        items=(
            ("KEEP", "Keep Current", "Keep the current active manipulator axis"),
            ("X", "X Axis", "Set active axis to X"),
            ("Y", "Y Axis", "Set active axis to Y"),
            ("Z", "Z Axis", "Set active axis to Z"),
            ("VIEW", "View Plane", "Set active axis to View Plane"),
        ),
        default="KEEP",
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        axis_arg = None if self.axis == "KEEP" else self.axis
        cmd_registry.set_active_tool(self.tool, axis=axis_arg)
        apply_gizmo_for_tool(context, self.tool)
        _refresh_help_line()
        return {"FINISHED"}


class LANDFALL_STUDIO_OT_select_last_tool(bpy.types.Operator):
    """Re-activate the last used non-select transform tool (`Y` in Maya)."""

    bl_idname = "landfall_studio.select_last_tool"
    bl_label = "Select Last Tool (Y)"
    bl_description = "Re-activate the last non-select tool (Move, Rotate, or Scale)"

    def execute(self, context):
        last_tool = cmd_registry.get_last_non_select_tool()
        cmd_registry.set_active_tool(last_tool)
        apply_gizmo_for_tool(context, last_tool)
        return {"FINISHED"}


class LANDFALL_STUDIO_OT_repeat_last_command(bpy.types.Operator):
    """Repeat the last executed Studio, blendertk, Tentacle, or Blender command (`G` in Maya)."""

    bl_idname = "landfall_studio.repeat_last_command"
    bl_label = "Repeat Last Command (G)"
    bl_description = "Repeat the last modeling or scene command (G)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        res = cmd_registry.repeat_last_command()
        if not res["ok"]:
            self.report({"WARNING"}, res.get("error", "Nothing to repeat"))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Repeated: {res.get('label', res.get('id'))}")
        return {"FINISHED"}


class LANDFALL_STUDIO_OT_component_mode(bpy.types.Operator):
    """Switch seamlessly between Object Mode and Vertex/Edge/Face/UV component modes (`F8–F12` & `RMB`)."""

    bl_idname = "landfall_studio.component_mode"
    bl_label = "Maya Component Mode"
    bl_description = (
        "Seamlessly switch between Object Mode (F8) and Vertex (F9), Edge (F10), "
        "Face (F11), Multi, or UV (F12) component selection without manual Tab switching"
    )
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("TOGGLE", "Toggle Object/Component (F8)", "Toggle between Object Mode and the last Component Mode"),
            ("OBJECT", "Object Mode", "Return to Object Mode"),
            ("VERT", "Vertex (F9)", "Enter Vertex selection mode"),
            ("EDGE", "Edge (F10)", "Enter Edge selection mode"),
            ("FACE", "Face (F11)", "Enter Face selection mode"),
            ("MULTI", "Multi-Component", "Enable Vertex, Edge, and Face selection simultaneously"),
            ("UV", "UV (F12)", "Enter UV selection mode"),
        ),
        default="TOGGLE",
        options={"SKIP_SAVE"},
    )
    raycast_x: bpy.props.IntProperty(default=-1, options={"SKIP_SAVE", "HIDDEN"})
    raycast_y: bpy.props.IntProperty(default=-1, options={"SKIP_SAVE", "HIDDEN"})

    def invoke(self, context, event):
        if self.raycast_x < 0 and self.raycast_y < 0 and event is not None:
            self.raycast_x = int(getattr(event, "mouse_region_x", -1))
            self.raycast_y = int(getattr(event, "mouse_region_y", -1))
        return self.execute(context)

    def _current_mesh_component_tag(self, context) -> str:
        msm = tuple(bool(x) for x in context.tool_settings.mesh_select_mode)
        if msm == (True, False, False):
            return "VERT"
        if msm == (False, True, False):
            return "EDGE"
        if msm == (False, False, True):
            return "FACE"
        return "MULTI"

    def _ensure_target_mesh(self, context):
        """Ensure a valid MESH object is active, raycasting under `(raycast_x, raycast_y)` if available."""
        if self.raycast_x >= 0 and self.raycast_y >= 0:
            hit_obj, _loc = raycast_mesh_at_region_xy(
                context, self.raycast_x, self.raycast_y
            )
            if hit_obj is not None and hit_obj.type == "MESH":
                if context.mode != "OBJECT":
                    try:
                        bpy.ops.object.mode_set(mode="OBJECT")
                    except Exception:
                        pass
                for o in list(context.selected_objects):
                    if o != hit_obj:
                        o.select_set(False)
                hit_obj.select_set(True)
                context.view_layer.objects.active = hit_obj
                return hit_obj

        active = context.view_layer.objects.active
        if active is not None and active.type == "MESH":
            if not active.select_get():
                active.select_set(True)
            return active

        for o in context.selected_objects:
            if o.type == "MESH":
                context.view_layer.objects.active = o
                return o
        return None

    def execute(self, context):
        target_mode = self.mode

        if target_mode == "OBJECT":
            if context.mode == "EDIT_MESH":
                cmd_registry.set_last_component_mode(
                    self._current_mesh_component_tag(context)
                )
            if context.mode != "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode="OBJECT")
                except Exception as exc:
                    self.report({"WARNING"}, f"Could not enter Object Mode: {exc}")
                    return {"CANCELLED"}
            return {"FINISHED"}

        if target_mode == "TOGGLE":
            if context.mode == "EDIT_MESH":
                cmd_registry.set_last_component_mode(
                    self._current_mesh_component_tag(context)
                )
                try:
                    bpy.ops.object.mode_set(mode="OBJECT")
                except Exception as exc:
                    self.report({"WARNING"}, f"Could not toggle to Object Mode: {exc}")
                    return {"CANCELLED"}
                return {"FINISHED"}
            target_mode = cmd_registry.get_last_component_mode()

        # Component modes: VERT, EDGE, FACE, MULTI, UV
        obj = self._ensure_target_mesh(context)
        if obj is None:
            self.report({"WARNING"}, "No mesh object active or under cursor")
            return {"CANCELLED"}

        if context.mode != "EDIT_MESH":
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except Exception as exc:
                self.report({"WARNING"}, f"Could not enter Edit Mode: {exc}")
                return {"CANCELLED"}

        mode_map = {
            "VERT": (True, False, False),
            "EDGE": (False, True, False),
            "FACE": (False, False, True),
            "MULTI": (True, True, True),
            "UV": (True, False, True),
        }
        msm = mode_map.get(target_mode, (True, False, False))
        context.tool_settings.mesh_select_mode = msm
        if target_mode == "UV":
            context.tool_settings.use_uv_select_sync = True
        else:
            cmd_registry.set_last_component_mode(target_mode)

        return {"FINISHED"}


class LANDFALL_STUDIO_OT_convert_selection(bpy.types.Operator):
    """Convert component selection (`Ctrl+RMB` in Maya): To Vertices, Edges, Faces, Loop, Ring, or Boundary."""

    bl_idname = "landfall_studio.convert_selection"
    bl_label = "Convert Component Selection (Ctrl+RMB)"
    bl_description = "Convert current mesh selection to Vertices, Edges, Faces, Edge Loop, Edge Ring, or Boundary"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.EnumProperty(
        name="Convert To",
        items=(
            ("VERT", "To Vertices", "Convert selected components to incident vertices"),
            ("EDGE", "To Edges", "Convert selected components to incident edges"),
            ("FACE", "To Faces", "Convert selected components to incident faces"),
            ("EDGE_LOOP", "To Edge Loop", "Expand edge selection to full edge loops"),
            ("EDGE_RING", "To Edge Ring", "Expand edge selection to full edge rings"),
            ("BOUNDARY", "To Edge Perimeter / Boundary", "Convert selection to boundary/perimeter edges"),
            ("GROW", "Grow Selection", "Grow component selection"),
            ("SHRINK", "Shrink Selection", "Shrink component selection"),
        ),
        default="VERT",
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "No active mesh for component conversion")
            return {"CANCELLED"}

        if context.mode != "EDIT_MESH":
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except Exception as exc:
                self.report({"WARNING"}, f"Could not enter Edit Mode: {exc}")
                return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        if self.target == "GROW":
            bpy.ops.mesh.select_more()
            return {"FINISHED"}

        if self.target == "SHRINK":
            bpy.ops.mesh.select_less()
            return {"FINISHED"}

        if self.target == "VERT":
            sel_verts = {v for v in bm.verts if v.select}
            for e in bm.edges:
                if e.select:
                    sel_verts.update(e.verts)
            for f in bm.faces:
                if f.select:
                    sel_verts.update(f.verts)
            for f in bm.faces:
                f.select_set(False)
            for e in bm.edges:
                e.select_set(False)
            for v in bm.verts:
                v.select_set(v in sel_verts)
            context.tool_settings.mesh_select_mode = (True, False, False)
            bm.select_mode = {"VERT"}
            cmd_registry.set_last_component_mode("VERT")
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            return {"FINISHED"}

        if self.target == "EDGE":
            sel_edges = {e for e in bm.edges if e.select}
            for f in bm.faces:
                if f.select:
                    sel_edges.update(f.edges)
            if not sel_edges:
                for v in bm.verts:
                    if v.select:
                        sel_edges.update(v.link_edges)
            for f in bm.faces:
                f.select_set(False)
            for v in bm.verts:
                v.select_set(False)
            for e in bm.edges:
                e.select_set(e in sel_edges)
            context.tool_settings.mesh_select_mode = (False, True, False)
            bm.select_mode = {"EDGE"}
            cmd_registry.set_last_component_mode("EDGE")
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            return {"FINISHED"}

        if self.target == "FACE":
            sel_faces = {f for f in bm.faces if f.select}
            if not sel_faces:
                for e in bm.edges:
                    if e.select:
                        sel_faces.update(e.link_faces)
            if not sel_faces:
                for v in bm.verts:
                    if v.select:
                        sel_faces.update(v.link_faces)
            for v in bm.verts:
                v.select_set(False)
            for e in bm.edges:
                e.select_set(False)
            for f in bm.faces:
                f.select_set(f in sel_faces)
            context.tool_settings.mesh_select_mode = (False, False, True)
            bm.select_mode = {"FACE"}
            cmd_registry.set_last_component_mode("FACE")
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            return {"FINISHED"}

        if self.target in ("EDGE_LOOP", "EDGE_RING"):
            # Ensure incident edges are selected first if vertices/faces were selected
            if not any(e.select for e in bm.edges):
                for v in bm.verts:
                    if v.select:
                        for e in v.link_edges:
                            e.select_set(True)
            context.tool_settings.mesh_select_mode = (False, True, False)
            bm.select_mode = {"EDGE"}
            cmd_registry.set_last_component_mode("EDGE")
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            bpy.ops.mesh.loop_multi_select(ring=(self.target == "EDGE_RING"))
            return {"FINISHED"}

        if self.target == "BOUNDARY":
            sel_faces = [f for f in bm.faces if f.select]
            if sel_faces:
                sel_face_set = set(sel_faces)
                boundary_edges = {
                    e
                    for f in sel_faces
                    for e in f.edges
                    if e.is_boundary
                    or sum(1 for lf in e.link_faces if lf in sel_face_set) == 1
                }
            else:
                boundary_edges = {e for e in bm.edges if e.is_boundary}

            for f in bm.faces:
                f.select_set(False)
            for v in bm.verts:
                v.select_set(False)
            for e in bm.edges:
                e.select_set(e in boundary_edges)
            context.tool_settings.mesh_select_mode = (False, True, False)
            bm.select_mode = {"EDGE"}
            cmd_registry.set_last_component_mode("EDGE")
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            return {"FINISHED"}

        return {"FINISHED"}


class LANDFALL_STUDIO_OT_pivot_edit_modal(bpy.types.Operator):
    """Hold `D` for temporary Maya pivot editing with live `X` (Grid), `C` (Edge), and `V` (Vertex) snap chords."""

    bl_idname = "landfall_studio.pivot_edit_modal"
    bl_label = "Temporary Pivot Edit (Hold D)"
    bl_description = (
        "Hold D to edit the object's pivot point; hold X (Grid), C (Edge), or V (Vertex) "
        "to snap the pivot, and release D or press Escape to restore the active tool"
    )
    bl_options = {"REGISTER", "UNDO"}

    snap_mode: bpy.props.EnumProperty(
        name="Snap Mode",
        items=(
            ("NONE", "Free Pivot", "Edit pivot without forced snap"),
            ("VERTEX", "Vertex Snap (D+V)", "Snap pivot to vertex"),
            ("EDGE", "Edge Snap (D+C)", "Snap pivot to edge midpoint"),
            ("GRID", "Grid Snap (D+X)", "Snap pivot to floor grid"),
        ),
        default="NONE",
        options={"SKIP_SAVE"},
    )
    use_target_co: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE", "HIDDEN"})
    target_co: bpy.props.FloatVectorProperty(
        size=3, default=(0.0, 0.0, 0.0), options={"SKIP_SAVE", "HIDDEN"}
    )
    simulate_cancel: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE", "HIDDEN"})

    def _enter_pivot_state(self, context):
        ts = context.scene.tool_settings
        lf_mod = landfall_bridge.get_module()
        p = lf_mod.prefs(context) if lf_mod is not None else None
        saved_gizmos = (
            tuple(bool(x) for x in p.gizmo_flags) if p is not None else (True, False, False)
        )

        _pivot_modal_state.update(
            {
                "active": True,
                "snap_mode": self.snap_mode,
                "saved_origin_flag": bool(ts.use_transform_data_origin),
                "saved_use_snap": bool(ts.use_snap),
                "saved_snap_elements": set(ts.snap_elements),
                "saved_pivot_point": str(ts.transform_pivot_point),
                "saved_gizmo_flags": saved_gizmos,
                "saved_active_tool": cmd_registry.get_active_tool(),
            }
        )
        ts.use_transform_data_origin = True
        self._apply_snap_chord(context, self.snap_mode)
        # Ensure translate gizmo is visible while editing pivot
        apply_gizmo_for_tool(context, "TRANSLATE")

    def _apply_snap_chord(self, context, mode: str):
        ts = context.scene.tool_settings
        _pivot_modal_state["snap_mode"] = mode
        if mode == "VERTEX":
            ts.use_snap = True
            ts.snap_elements = {"VERTEX"}
        elif mode == "EDGE":
            ts.use_snap = True
            ts.snap_elements = {"EDGE", "EDGE_MIDPOINT"}
        elif mode == "GRID":
            ts.use_snap = True
            ts.snap_elements = {"INCREMENT"}

    def _restore_pivot_state(self, context):
        ts = context.scene.tool_settings
        ts.use_transform_data_origin = bool(_pivot_modal_state["saved_origin_flag"])
        ts.use_snap = bool(_pivot_modal_state["saved_use_snap"])
        try:
            if _pivot_modal_state["saved_snap_elements"]:
                ts.snap_elements = set(_pivot_modal_state["saved_snap_elements"])
        except Exception:
            pass
        try:
            ts.transform_pivot_point = str(_pivot_modal_state["saved_pivot_point"])
        except Exception:
            pass
        saved_tool = _pivot_modal_state.get("saved_active_tool", "TRANSLATE")
        cmd_registry.set_active_tool(saved_tool)
        apply_gizmo_for_tool(context, saved_tool)
        _pivot_modal_state["active"] = False
        _pivot_modal_state["snap_mode"] = "NONE"

    def execute(self, context):
        """Deterministic execution path for automated tests or direct pivot snapping."""
        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "No active mesh object for pivot edit")
            return {"CANCELLED"}

        old_origin = obj.matrix_world.translation.copy()
        self._enter_pivot_state(context)
        try:
            if self.simulate_cancel:
                # Verify that cancel/Escape restores everything without mutating origin
                return {"CANCELLED"}

            if self.snap_mode != "NONE" or self.use_target_co:
                explicit = tuple(self.target_co) if self.use_target_co else None
                target = compute_pivot_snap_target(
                    context, obj, self.snap_mode, explicit_target=explicit
                )
                snap_object_pivot_world(obj, target)
        finally:
            self._restore_pivot_state(context)
            if self.simulate_cancel and (obj.matrix_world.translation - old_origin).length > 1e-6:
                snap_object_pivot_world(obj, old_origin)

        return {"FINISHED"}

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            return self.execute(context)

        obj = context.view_layer.objects.active
        if obj is None:
            self.report({"WARNING"}, "No active object for pivot editing")
            return {"CANCELLED"}

        self._initial_origin = obj.matrix_world.translation.copy() if obj.type == "MESH" else None
        self._enter_pivot_state(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        self._restore_pivot_state(context)
        if context.area:
            context.area.tag_redraw()

    def modal(self, context, event):
        if not _pivot_modal_state["active"]:
            return {"FINISHED"}

        # Release D -> finish and restore active tool & snap state
        if event.type == "D" and event.value == "RELEASE":
            self._restore_pivot_state(context)
            if context.area:
                context.area.tag_redraw()
            return {"FINISHED"}

        # Escape -> cancel, rollback pivot if snapped during this hold, and restore state
        if event.type == "ESC" and event.value == "PRESS":
            obj = context.view_layer.objects.active
            if (
                obj is not None
                and obj.type == "MESH"
                and getattr(self, "_initial_origin", None) is not None
            ):
                try:
                    snap_object_pivot_world(obj, self._initial_origin)
                except Exception:
                    pass
            self._restore_pivot_state(context)
            if context.area:
                context.area.tag_redraw()
            return {"CANCELLED"}

        # Live X / C / V snap chord keys while D is held
        if event.type in ("X", "C", "V"):
            if event.value == "PRESS":
                chord_map = {"X": "GRID", "C": "EDGE", "V": "VERTEX"}
                self._apply_snap_chord(context, chord_map[event.type])
                return {"RUNNING_MODAL"}
            if event.value == "RELEASE":
                self._apply_snap_chord(context, "NONE")
                return {"RUNNING_MODAL"}

        # Click or MMB with active snap chord snaps pivot to the hovered vertex/edge/grid
        if (
            event.type in ("LEFTMOUSE", "MIDDLEMOUSE")
            and event.value == "PRESS"
            and _pivot_modal_state["snap_mode"] != "NONE"
        ):
            obj = context.view_layer.objects.active
            if obj is not None and obj.type == "MESH":
                target = compute_pivot_snap_target(
                    context,
                    obj,
                    _pivot_modal_state["snap_mode"],
                    region_x=event.mouse_region_x,
                    region_y=event.mouse_region_y,
                )
                snap_object_pivot_world(obj, target)
                if context.area:
                    context.area.tag_redraw()
                return {"RUNNING_MODAL"}

        return {"PASS_THROUGH"}


class LANDFALL_STUDIO_OT_temp_snap_modal(bpy.types.Operator):
    """Hold `X` (Grid), `C` (Curve/Edge), or `V` (Vertex) for temporary Maya snapping, restoring on release."""

    bl_idname = "landfall_studio.temp_snap_modal"
    bl_label = "Temporary Maya Snap (Hold X/C/V)"
    bl_description = "Temporarily enable Grid (X), Edge/Curve (C), or Vertex (V) snap while held"

    target: bpy.props.EnumProperty(
        name="Snap Target",
        items=(
            ("INCREMENT", "Grid (X)", "Snap to grid increments"),
            ("EDGE", "Edge / Curve (C)", "Snap to edges and curves"),
            ("VERTEX", "Vertex (V)", "Snap to vertices"),
        ),
        default="VERTEX",
        options={"SKIP_SAVE"},
    )
    release_key: bpy.props.StringProperty(default="V", options={"SKIP_SAVE", "HIDDEN"})

    def _save_and_enable(self, context):
        ts = context.scene.tool_settings
        self._saved_use_snap = bool(ts.use_snap)
        self._saved_elements = set(ts.snap_elements)
        ts.use_snap = True
        ts.snap_elements = {self.target}

    def _restore(self, context):
        ts = context.scene.tool_settings
        ts.use_snap = getattr(self, "_saved_use_snap", False)
        saved_elems = getattr(self, "_saved_elements", None)
        if saved_elems:
            try:
                ts.snap_elements = set(saved_elems)
            except Exception:
                pass

    def execute(self, context):
        self._save_and_enable(context)
        self._restore(context)
        return {"FINISHED"}

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"PASS_THROUGH"}
        self.release_key = event.type or self.release_key
        self._save_and_enable(context)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        self._restore(context)

    def modal(self, context, event):
        if (event.type == self.release_key and event.value == "RELEASE") or (
            event.type == "ESC" and event.value == "PRESS"
        ):
            self._restore(context)
            return {"FINISHED"}
        return {"PASS_THROUGH"}


class LANDFALL_STUDIO_OT_mmb_virtual_slider(bpy.types.Operator):
    """Maya-style open-viewport MMB virtual slider along selected Channel Box attributes or active manipulator axis."""

    bl_idname = "landfall_studio.mmb_virtual_slider"
    bl_label = "MMB Virtual Slider"
    bl_description = "Drag MMB in the viewport to scrub selected Channel Box attributes or the active Move/Rotate/Scale axis"
    bl_options = {"REGISTER", "UNDO"}

    delta: bpy.props.FloatProperty(
        name="Delta",
        default=0.0,
        description="Transform or channel delta",
        options={"SKIP_SAVE"},
    )
    prefer_channel_box: bpy.props.BoolProperty(
        name="Prefer Channel Box Selection",
        default=True,
        description="If channels are highlighted in the Channel Box, scrub them across selected objects",
        options={"SKIP_SAVE"},
    )

    def _has_selected_channels(self) -> bool:
        if not self.prefer_channel_box:
            return False
        try:
            from ..ui import channel_box_ext

            if channel_box_ext._selected_input_target is not None:
                return True
            return len(channel_box_ext.get_selected_channel_names()) > 0
        except Exception:
            return False

    def _apply_delta(self, context, delta_val: float):
        session = getattr(self, '_channel_scrub', None)
        if session is not None:
            return session.apply(delta_val)

        tool = cmd_registry.get_active_tool()
        axis = cmd_registry.get_active_axis()
        idx = {"X": 0, "Y": 1, "Z": 2}.get(axis, 0)

        targets = list(context.selected_objects)
        active = context.view_layer.objects.active
        if active is not None and active not in targets:
            targets.append(active)

        for obj in targets:
            if getattr(obj, "mode", "OBJECT") == "EDIT" and getattr(obj, "type", "") == "MESH" and obj.data is not None:
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()
                sel_verts = [v for v in bm.verts if v.select]
                if not sel_verts:
                    continue
                if tool == "TRANSLATE":
                    vec = mathutils.Vector((0.0, 0.0, 0.0))
                    if axis == "VIEW":
                        vec.x = delta_val
                        vec.y = delta_val
                    else:
                        vec[idx] = delta_val
                    for v in sel_verts:
                        v.co += vec
                elif tool == "ROTATE":
                    center = sum((v.co for v in sel_verts), mathutils.Vector((0.0, 0.0, 0.0))) / len(sel_verts)
                    rot_axis = "Z" if axis == "VIEW" else (axis if axis in ("X", "Y", "Z") else "X")
                    rot_mat = mathutils.Matrix.Rotation(delta_val, 3, rot_axis)
                    for v in sel_verts:
                        v.co = center + rot_mat @ (v.co - center)
                elif tool == "RESIZE":
                    center = sum((v.co for v in sel_verts), mathutils.Vector((0.0, 0.0, 0.0))) / len(sel_verts)
                    factor = max(0.001, 1.0 + delta_val)
                    for v in sel_verts:
                        diff = v.co - center
                        if axis == "VIEW":
                            v.co = center + diff * factor
                        else:
                            diff[idx] *= factor
                            v.co = center + diff
                bm.normal_update()
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
                continue

            if tool == "TRANSLATE":
                if axis == "VIEW":
                    obj.location.x += delta_val
                    obj.location.y += delta_val
                else:
                    obj.location[idx] += delta_val
            elif tool == "ROTATE":
                from ..modeling import rotation
                component = 2 if axis == 'VIEW' else idx
                rotation.set_component(obj, component, rotation.euler(obj)[component] + delta_val)
            elif tool == "RESIZE":
                if axis == "VIEW":
                    obj.scale.x = max(0.001, obj.scale.x + delta_val)
                    obj.scale.y = max(0.001, obj.scale.y + delta_val)
                    obj.scale.z = max(0.001, obj.scale.z + delta_val)
                else:
                    obj.scale[idx] = max(0.001, obj.scale[idx] + delta_val)
        return True

    def execute(self, context):
        tool = cmd_registry.get_active_tool()
        if tool == "SELECT" and not self._has_selected_channels():
            return {"CANCELLED"}
        from ..ui import channel_box_ext
        has_cb = self._has_selected_channels()
        self._channel_scrub = channel_box_ext.begin_channel_scrub() if has_cb else None
        if has_cb and self._channel_scrub is None:
            return {"CANCELLED"}
        return {"FINISHED"} if self._apply_delta(context, self.delta) else {"CANCELLED"}

    def invoke(self, context, event):
        tool = cmd_registry.get_active_tool()
        has_cb = self._has_selected_channels()
        if (tool == "SELECT" and not has_cb) or context.area is None or context.area.type != "VIEW_3D":
            return {"PASS_THROUGH"}

        targets = list(context.selected_objects)
        active = context.view_layer.objects.active
        if active is not None and active not in targets:
            targets.append(active)
        if not targets:
            return {"PASS_THROUGH"}

        from ..ui import channel_box_ext
        self._channel_scrub = channel_box_ext.begin_channel_scrub() if has_cb else None
        if has_cb and self._channel_scrub is None:
            return {"CANCELLED"}
        self._moved = False

        self._start_x = event.mouse_region_x
        self._last_x = event.mouse_region_x
        self._snapshots = []
        for o in targets:
            edit_verts = None
            if getattr(o, "mode", "OBJECT") == "EDIT" and getattr(o, "type", "") == "MESH" and o.data is not None:
                try:
                    bm = bmesh.from_edit_mesh(o.data)
                    bm.verts.ensure_lookup_table()
                    edit_verts = [v.co.copy() for v in bm.verts]
                except Exception:
                    edit_verts = None
            from ..modeling import rotation
            self._snapshots.append((o, o.location.copy(), rotation.snapshot(o), o.scale.copy(), edit_verts))
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _rollback(self):
        session = getattr(self, '_channel_scrub', None)
        if session is not None:
            session.restore()
        for o, loc, rot, sca, edit_verts in getattr(self, "_snapshots", []):
            try:
                o.location = loc
                from ..modeling import rotation
                rotation.restore(o, rot)
                o.scale = sca
                if edit_verts is not None and getattr(o, "mode", "OBJECT") == "EDIT" and o.data is not None:
                    bm = bmesh.from_edit_mesh(o.data)
                    bm.verts.ensure_lookup_table()
                    for v, saved_co in zip(bm.verts, edit_verts):
                        v.co = saved_co
                    bm.normal_update()
                    bmesh.update_edit_mesh(o.data, loop_triangles=False, destructive=False)
            except Exception:
                pass

    def cancel(self, context):
        self._rollback()

    def modal(self, context, event):
        if event.type == "MOUSEMOVE":
            dx = event.mouse_region_x - self._last_x
            self._last_x = event.mouse_region_x
            mult = 0.01
            if event.ctrl:
                mult *= 0.1
            elif event.shift:
                mult *= 2.5
            if not self._apply_delta(context, dx * mult):
                self._rollback()
                return {"CANCELLED"}
            self._moved = self._moved or bool(dx)
            if context.area:
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if event.type == "MIDDLEMOUSE" and event.value == "RELEASE":
            session = getattr(self, '_channel_scrub', None)
            changed = session.changed() if session is not None else self._moved
            return {"FINISHED"} if changed else {"CANCELLED"}

        if (event.type in ("ESC", "RIGHTMOUSE") and event.value == "PRESS") or event.type == 'WINDOW_DEACTIVATE':
            self._rollback()
            if context.area:
                context.area.tag_redraw()
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}


class LANDFALL_STUDIO_OT_frame_all(bpy.types.Operator):
    """Frame all visible objects/components in the active 3D Viewport (`A` in Maya profile)."""

    bl_idname = "landfall_studio.frame_all"
    bl_label = "Frame All (A)"
    bl_description = "Frame all objects in the 3D Viewport (Maya A shortcut)"

    def execute(self, context):
        area, region = find_view3d_area_region(context)
        if area is None or region is None:
            self.report({"WARNING"}, "No 3D Viewport available")
            return {"CANCELLED"}
        try:
            with context.temp_override(area=area, region=region):
                bpy.ops.view3d.view_all(center=False)
                bpy.ops.view3d.zoom(delta=-1)
        except Exception as exc:
            self.report({"WARNING"}, f"Could not frame all: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


INTERACTION_CLASSES = (
    LANDFALL_STUDIO_OT_set_key,
    LANDFALL_STUDIO_OT_maya_box_select,
    LANDFALL_STUDIO_OT_maya_select,
    LANDFALL_STUDIO_OT_select_tool,
    LANDFALL_STUDIO_OT_select_last_tool,
    LANDFALL_STUDIO_OT_repeat_last_command,
    LANDFALL_STUDIO_OT_component_mode,
    LANDFALL_STUDIO_OT_convert_selection,
    LANDFALL_STUDIO_OT_pivot_edit_modal,
    LANDFALL_STUDIO_OT_temp_snap_modal,
    LANDFALL_STUDIO_OT_mmb_virtual_slider,
    LANDFALL_STUDIO_OT_frame_all,
)
