"""Sculpt mode lifecycle, independent of how the artist changes Blender mode."""
import bpy
from . import state, brushes, ops, gestures

_engaged=False
_previous=None
_timer=None
_trackers=set()
_last_mode='OBJECT'
_maya_canvas={}


def _space_snapshot(space):
    fields=('show_region_asset_shelf','show_region_tool_header','show_gizmo_object_translate','show_gizmo_object_rotate','show_gizmo_object_scale')
    saved={key:getattr(space,key) for key in fields}
    shade_fields=('type','light','studio_light','color_type','single_color','show_cavity','show_shadows','show_xray','xray_alpha','background_type','background_color')
    saved['shading']={key:tuple(getattr(space.shading,key)) if key in ('single_color','background_color') else getattr(space.shading,key) for key in shade_fields}
    saved['face_sets']=space.overlay.show_sculpt_face_sets
    saved['overlay']={key:getattr(space.overlay,key) for key in ('show_floor','show_ortho_grid','show_axis_x','show_axis_y','show_axis_z')}
    return saved


def _remember_maya_canvas():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type=='VIEW_3D':_maya_canvas[(window.as_pointer(),area.as_pointer())]=_space_snapshot(area.spaces.active)


def is_engaged(): return _engaged


def reset_after_file_load():
    """Loaded files have new scene/window data; old return snapshots are invalid."""
    global _engaged,_previous,_last_mode
    from ..ui import sculpt_widgets
    sculpt_widgets.forget_origin()
    from . import layout
    layout.abandon_after_load()
    ops._xpose.clear();ops._solo_hidden.clear();ops._ghost_display.clear()
    from ..ui import desktop
    desktop._active_workspace_layout=(_previous or {}).get('workspace','Modeling Standard')
    if desktop._active_workspace_layout=='Sculpt & Remesh Studio':desktop._active_workspace_layout='Modeling Standard'
    _engaged=False;_previous=None;_last_mode='OBJECT';_trackers.clear();_maya_canvas.clear()
    from ..adapters import tentacle_bridge
    tentacle_bridge.suspend_sculpt_hotbox(False)


def engage():
    global _engaged,_previous
    if _engaged: return
    ops.restore_recording()
    from ..ui import desktop,shelf,main_menu
    _previous={'workspace':desktop.get_active_workspace_layout(),
               'right':desktop._right_dock.mode if desktop._right_dock else 'CHANNEL_BOX',
               'shelves':[x.tabs.currentIndex() for x in shelf._shelf_instances],
               'mode':_last_mode,'spaces':[],
               'brush_cursor':bpy.context.tool_settings.sculpt.show_brush}
    _previous['finite_grid']=getattr(bpy.context.scene,'landfall_grid_finite',None)
    unified=bpy.context.tool_settings.sculpt.unified_paint_settings
    _previous['unified']={field:getattr(unified,field) for field in ('use_unified_size','use_unified_strength')}
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type!='VIEW_3D': continue
            sp=a.spaces.active
            saved=_maya_canvas.get((w.as_pointer(),a.as_pointer()),_space_snapshot(sp))
            _previous['spaces'].append((w,a,saved))
            with bpy.context.temp_override(window=w,area=a,region=next(r for r in a.regions if r.type=='WINDOW')):
                if sp.show_region_asset_shelf:bpy.ops.screen.region_toggle(region_type='ASSET_SHELF')
                if sp.show_region_tool_header:bpy.ops.screen.region_toggle(region_type='TOOL_HEADER')
                ops.matcap(state.get().active_matcap)
                sp.overlay.show_sculpt_face_sets=state.get().polyframe_active
    with bpy.context.temp_override(**ops.view_context()):
        brushes.select(state.get().active_zbrush_brush)
        ops.dispatch('TOOL',tool='DRAW')
    bpy.context.tool_settings.sculpt.show_brush=False
    _engaged=True
    desktop._active_workspace_layout='Sculpt & Remesh Studio'
    if not bpy.app.background:main_menu.sync_workspace_selector('Sculpt & Remesh Studio')
    if not bpy.app.background and desktop._right_dock is not None:
        desktop.cycle_right_dock('ZBRUSH_STUDIO')
        desktop._right_dock._ensure_host_container().set_workspace_spine_preset('Sculpt & Remesh Studio')
    for sh in shelf._shelf_instances: sh.set_sculpt_mode(True)
    if not bpy.app.background:
        from . import layout
        layout.engage()
    from ..adapters import tentacle_bridge
    tentacle_bridge.suspend_sculpt_hotbox(True)
    # Landfall's finite-grid callback enables the infinite native grid when
    # switched off. Set the scene flag first, then hide every sculpt grid.
    if hasattr(bpy.context.scene,'landfall_grid_finite'):bpy.context.scene.landfall_grid_finite=False
    for window,area,_ in _previous['spaces']:
        for field in ('show_floor','show_ortho_grid','show_axis_x','show_axis_y','show_axis_z'):
            setattr(area.spaces.active.overlay,field,False)


def disengage(shape_editor=False):
    global _engaged,_previous
    if not _engaged: return
    from . import layout
    layout.disengage()
    from ..adapters import tentacle_bridge
    tentacle_bridge.suspend_sculpt_hotbox(False)
    from ..ui import desktop,shelf,main_menu
    _engaged=False
    if state.get().solo_active: ops.toggle_solo()
    if state.get().ghost_transparency_active: ops.ghost()
    if ops._xpose: ops.xpose()
    prev=_previous or {}
    if prev.get('finite_grid') is not None:bpy.context.scene.landfall_grid_finite=prev['finite_grid']
    bpy.context.tool_settings.sculpt.show_brush=prev.get('brush_cursor',True)
    for field,value in prev.get('unified',{}).items():setattr(bpy.context.tool_settings.sculpt.unified_paint_settings,field,value)
    restore=[]
    for win in bpy.context.window_manager.windows:
        candidates=[(a,v) for w,a,v in prev.get('spaces',[]) if w==win]
        for area in win.screen.areas:
            if area.type=='VIEW_3D' and candidates:
                values=next((v for a,v in candidates if a==area),candidates[0][1])
                restore.append((win,area,values))
    for win,area,values in restore:
        try:
            if area.type!='VIEW_3D':continue
            with bpy.context.temp_override(window=win,area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
                sp=area.spaces.active
                for key,value in values.items():
                    if key in ('show_region_asset_shelf','show_region_tool_header'):
                        if getattr(sp,key)!=value:bpy.ops.screen.region_toggle(region_type='ASSET_SHELF' if key=='show_region_asset_shelf' else 'TOOL_HEADER')
                    elif key=='shading':
                        for field,setting in value.items():setattr(sp.shading,field,setting)
                    elif key=='face_sets':sp.overlay.show_sculpt_face_sets=value
                    elif key=='overlay':
                        for field,setting in value.items():setattr(sp.overlay,field,setting)
                    else:setattr(sp,key,value)
        except ReferenceError:pass
    for i,sh in enumerate(shelf._shelf_instances):
        sh.set_sculpt_mode(False)
        indices=prev.get('shelves',[])
        if i<len(indices): sh.tabs.setCurrentIndex(indices[i])
    desktop._active_workspace_layout=prev.get('workspace','Modeling Standard')
    if not bpy.app.background and desktop._right_dock is not None:
        if shape_editor:
            from ..ui import shape_editor as shape_ui
            o=bpy.context.active_object
            for widget in shape_ui._active_se_widgets:
                widget._selected_key_name=o.active_shape_key.name if o and o.active_shape_key else ''
        desktop.cycle_right_dock('SHAPE_EDITOR' if shape_editor else prev.get('right','CHANNEL_BOX'))
        desktop._right_dock._ensure_host_container().set_workspace_spine_preset(desktop._active_workspace_layout)
        main_menu.sync_workspace_selector(desktop._active_workspace_layout)
    _previous=None


def enter(context=None):
    global _last_mode
    with bpy.context.temp_override(**ops.view_context(context)):
        ops.active()
        if ops.active().library or ops.active().data.library:
            ops.switch_subtool(ops.surface_copy(ops.active()))
        if bpy.context.mode!='SCULPT':
            _last_mode=bpy.context.mode
            _remember_maya_canvas()
            if _last_mode=='EDIT_MESH':bpy.ops.object.mode_set(mode='OBJECT')
            from .instances import ensure_owners
            ensure_owners(ops.active())
            ops.restore_recording()
            bpy.ops.object.mode_set(mode='SCULPT')
        if not _engaged:engage()
        sync_mode()
    return {'ok':True,'mode':'SCULPT','engaged':_engaged}


def return_to_maya(shape_editor=False):
    with bpy.context.temp_override(**ops.view_context()):
        native_mode=(_previous or {}).get('mode','OBJECT')
        obj=bpy.context.object
        leaving_sculpt=bool(obj and obj.mode=='SCULPT')
        return_key=ops.shape_editor_return_key(obj) if shape_editor and obj and obj.type=='MESH' else None
        return_name=return_key.name if return_key else None
        if obj and obj.type=='MESH' and obj.mode=='SCULPT':ops.remember_recording(obj)
        if bpy.context.object and bpy.context.object.mode!='OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        # Retarget only after leaving the native Sculpt session, whose current
        # vertex buffer can still belong to Basis at a higher Multires level.
        if return_name:
            obj.active_shape_key_index=obj.data.shape_keys.key_blocks.find(return_name)
            obj.show_only_shape_key=False
        disengage(shape_editor)
        if native_mode=='EDIT_MESH' and not shape_editor and bpy.context.object:bpy.ops.object.mode_set(mode='EDIT')
        from ..keymaps import profiles
        profiles.sync_sculpt_keymaps(False)
        profiles.sync_sculpt_transforms(False)
        if leaving_sculpt and not bpy.app.background and bpy.context.preferences.edit.use_global_undo:
            # A Python/Qt mode switch does not create the native Object-mode
            # snapshot that a subsequent inspector edit must undo back to.
            # Keep this explicit boundary in Blender's existing history so the
            # first modeling Undo restores the edit without reopening Sculpt.
            bpy.ops.ed.undo_push(message='Return to Modeling')
    return {'ok':True,'mode':bpy.context.mode,'shape_editor':shape_editor,'layer':return_name}


def sync_mode():
    global _last_mode
    from ..keymaps import profiles
    from ..ui import desktop
    if desktop._scene_restore_timer is not None:return bpy.context.mode=='SCULPT'
    sculpt=bpy.context.mode=='SCULPT'
    profiles.sync_sculpt_transforms(sculpt)
    if sculpt and state.get().auto_activate and not _engaged: engage()
    elif not sculpt and _engaged: disengage()
    if not sculpt:
        _last_mode=bpy.context.mode
        _remember_maya_canvas()
    profiles.sync_sculpt_keymaps(sculpt and _engaged)
    if sculpt and _engaged and state.get().bbrush_enabled:profiles.sync_sculpt_paint_mode()
    if _engaged:bpy.context.tool_settings.sculpt.show_brush=not state.get().bbrush_enabled
    if sculpt and _engaged:ops.stop_grid_layer_recording()
    if not bpy.app.background:
        from . import layout
        if sculpt and _engaged:
            if not layout.active:layout.engage()
            layout.sync()
        from ..ui.zbrush_panel import refresh
        refresh()
        live={(w.as_pointer(),a.as_pointer()) for w in bpy.context.window_manager.windows for a in w.screen.areas if a.type=='VIEW_3D'}
        _trackers.intersection_update(live)
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type!='VIEW_3D': continue
                key=(w.as_pointer(),a.as_pointer())
                if sculpt and _engaged:
                    with bpy.context.temp_override(window=w,area=a,region=next(r for r in a.regions if r.type=='WINDOW')):
                        # Blender can reopen its asset shelf/tool header during
                        # native mode round-trips used by geometry operations.
                        if a.spaces.active.show_region_asset_shelf:bpy.ops.screen.region_toggle(region_type='ASSET_SHELF')
                        if a.spaces.active.show_region_tool_header:bpy.ops.screen.region_toggle(region_type='TOOL_HEADER')
                if sculpt and key not in _trackers:
                    with bpy.context.temp_override(window=w,area=a,region=next(r for r in a.regions if r.type=='WINDOW')):
                        bpy.ops.landfall_studio.sculpt_cursor('INVOKE_DEFAULT')
                    _trackers.add(key)
    return sculpt


def _poll():
    try: sync_mode()
    except Exception as exc: print('[Sculpt Studio]',exc)
    return 0.2


_settle_checks=0
# Brush choice and its dials are tool state, not model data: ZBrush and Blender
# never undo them. They live on the scene, so carry them across Undo/Redo.
_TOOL_FIELDS=('active_zbrush_brush','imm_part','draw_size','z_intensity','focal_shift','lazy_mouse','sculptris_detail')
_tool_state=None


@bpy.app.handlers.persistent
def _remember_tool_state(*_):
    global _tool_state
    try:
        s=state.get()
        _tool_state={f:getattr(s,f) for f in _TOOL_FIELDS if hasattr(s,f)}
    except (AttributeError,RuntimeError):
        _tool_state=None


def _restore_tool_state():
    global _tool_state
    # Blender re-enters Sculpt a tick or two after undo_post; wait for it.
    if not _tool_state or bpy.context.mode!='SCULPT':return
    saved,_tool_state=dict(_tool_state),None
    s=state.get()
    brush=saved.pop('active_zbrush_brush',None)
    if brush and brush!=s.active_zbrush_brush:
        try:
            with bpy.context.temp_override(**ops.view_context()):brushes.select(brush)
        except Exception as exc:print('[Sculpt Studio] brush restore:',exc)
    for field,value in saved.items():
        if getattr(s,field)!=value:setattr(s,field,value)


def _sync_soon():
    global _settle_checks
    try: sync_mode()
    except Exception as exc: print('[Sculpt Studio]',exc)
    try: _restore_tool_state()
    except Exception as exc: print('[Sculpt Studio]',exc)
    _settle_checks-=1
    if _settle_checks>0:return 0.05
    global _tool_state
    _tool_state=None
    return None


@bpy.app.handlers.persistent
def _history_changed(*_):
    """Undo/Redo can cross into or out of Sculpt: follow it within a frame or
    two, not the next poll. Blender re-enters the restored mode only after
    undo_post, so keep checking briefly until that has happened."""
    global _settle_checks
    _settle_checks=6
    if not bpy.app.timers.is_registered(_sync_soon):
        bpy.app.timers.register(_sync_soon,first_interval=0.0)


@bpy.app.handlers.persistent
def _mode_watch(scene=None,depsgraph=None):
    """Any route into or out of Sculpt (native keys, undo boundaries, other
    add-ons) updates the depsgraph; engage on the next tick, not the next poll."""
    try:
        sculpt=bpy.context.mode=='SCULPT'
        wanted=sculpt!=_engaged and (not sculpt or state.get().auto_activate)
    except (AttributeError,RuntimeError):return
    if wanted:_history_changed()


def register():
    global _timer
    state.register()
    from ..viewport import sculpt_hud
    from . import instances
    registered=[]
    try:
        for cls in (ops.LANDFALL_STUDIO_OT_sculpt_command,)+gestures.CLASSES:
            bpy.utils.register_class(cls);registered.append(cls)
        sculpt_hud.register()
        instances.register_handlers()
        _timer=_poll
        bpy.app.timers.register(_timer,first_interval=0.5,persistent=True)
        for handlers in (bpy.app.handlers.undo_post,bpy.app.handlers.redo_post):
            if _history_changed not in handlers:handlers.append(_history_changed)
        for handlers in (bpy.app.handlers.undo_pre,bpy.app.handlers.redo_pre):
            if _remember_tool_state not in handlers:handlers.append(_remember_tool_state)
        if _mode_watch not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(_mode_watch)
    except Exception:
        instances.unregister_handlers()
        sculpt_hud.unregister()
        for cls in reversed(registered):bpy.utils.unregister_class(cls)
        state.unregister()
        _timer=None
        raise


def unregister():
    global _timer,_engaged,_previous
    if not hasattr(bpy.types.Scene,'landfall_sculpt'):return
    from . import instances
    instances.unregister_handlers()
    from ..keymaps import profiles
    profiles.sync_sculpt_keymaps(False)
    profiles.sync_sculpt_transforms(False)
    if _timer and bpy.app.timers.is_registered(_timer): bpy.app.timers.unregister(_timer)
    _timer=None
    for handlers in (bpy.app.handlers.undo_post,bpy.app.handlers.redo_post):
        while _history_changed in handlers:handlers.remove(_history_changed)
    for handlers in (bpy.app.handlers.undo_pre,bpy.app.handlers.redo_pre):
        while _remember_tool_state in handlers:handlers.remove(_remember_tool_state)
    while _mode_watch in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_mode_watch)
    if bpy.app.timers.is_registered(_sync_soon):bpy.app.timers.unregister(_sync_soon)
    gestures.tracker_generation+=1
    gestures._pointer_windows.clear()
    _trackers.clear()
    _maya_canvas.clear()
    from ..viewport import sculpt_hud
    sculpt_hud.unregister()
    from ..ui import zbrush_panel
    zbrush_panel.teardown()
    if _engaged:disengage()
    _engaged=False; _previous=None
    for cls in reversed((ops.LANDFALL_STUDIO_OT_sculpt_command,)+gestures.CLASSES): bpy.utils.unregister_class(cls)
    state.unregister()
