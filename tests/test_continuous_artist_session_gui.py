"""A continuous native model -> base sculpt -> detail -> Shape Editor session.

Only initial meshes are procedural fixtures. Deformation comes from native
viewport events; visible controls are operated through Qt input. No physical
tablet, clean-machine, or external Maya interoperability claim.
"""
import ctypes
import json
import math
import os
from pathlib import Path
import sys
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'output/continuous_artist_session_gui.json'
FORM = 'Artist Session Form'
OTHER = 'Artist Session Accessory'
# Blender-only control on this unit-radius brush-authored fixture measured
# max 1.3113e-6 / RMS 2.546e-8 over ten native Undo/Redo cycles. No-stroke
# rebuilds were exact. This allowance applies to evaluated grid Undo only;
# every Basis and shape-layer buffer remains an exact comparison.
GRID_UNDO_MAX = 2e-6
GRID_UNDO_RMS = 5e-8
result = {'ok': False, 'passed': [], 'failed': [], 'observations': {},
          'boundary': __doc__}


def save():
    OUT.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')


def check(name, value, detail=None):
    result['passed' if value else 'failed'].append(
        name if value else {'test': name, 'detail': detail})
    save()


def require(name, value, detail=None):
    check(name, value, detail)
    if not value:
        raise RuntimeError(name)


def form():
    return bpy.data.objects[FORM]


def points(key):
    return [tuple(v.co) for v in key.data]


def difference(a, b):
    if len(a) != len(b):
        return float('inf')
    return max((sum((x-y)**2 for x, y in zip(p, q))**.5
                for p, q in zip(a, b)), default=0)


def view():
    w = bpy.context.window_manager.windows[0]
    a = next(a for a in w.screen.areas if a.type == 'VIEW_3D')
    return dict(window=w, area=a,
                region=next(r for r in a.regions if r.type == 'WINDOW'))


def suite():
    bpy.context.preferences.view.show_splash = False
    bpy.ops.wm.read_homefile()
    import landfall_studio
    from landfall_studio import ui, sculpt
    from landfall_studio.ui import (desktop, attribute_editor, shelf,
                                   zbrush_panel, sculpt_widgets)
    from landfall_studio.sculpt import ops, state, layout, preferences, gestures
    preferences.PATH = ROOT.parent / ('.test_env/continuous_artist_preferences_'+str(os.getpid())+'.json')
    preferences._data = None
    landfall_studio.register()
    ui.restore_workspace_desktop(restore_script_output=False)
    yield 1.0
    from PySide6 import QtCore as C, QtWidgets as W, QtGui as G, QtTest as T
    from blendertk.ui_utils.blender_window import BlenderWindow
    app = W.QApplication.instance()
    hwnd = BlenderWindow.window_hwnd(view()['window'])
    ctypes.windll.user32.ShowWindow(hwnd, 3)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    yield .4
    result['dpr'] = G.QGuiApplication.primaryScreen().devicePixelRatio()

    def focus(widget):
        G.QCursor.setPos(widget.mapToGlobal(widget.rect().center()))
        app.setActiveWindow(widget.window())
        widget.window().activateWindow()
        widget.setFocus()
        target = int(widget.window().internalWinId() or 0)
        if target:
            BlenderWindow.set_keyboard_focus(target)

    def click(widget):
        ancestor = widget.parentWidget()
        while ancestor and not isinstance(ancestor, W.QScrollArea):
            ancestor = ancestor.parentWidget()
        if ancestor:
            ancestor.ensureWidgetVisible(widget)
        yield .15
        require('reachable control: ' + widget.text(), widget.isVisible()
                and widget.isEnabled(), widget.objectName())
        focus(widget)
        T.QTest.mouseClick(widget, C.Qt.LeftButton)
        yield .25

    def native_focus(xy=None):
        if app.focusWidget():
            app.focusWidget().clearFocus()
        app.setActiveWindow(None)
        c = view()
        r = c['region']
        x, y = xy or (r.x+r.width//2, r.y+r.height//2)
        origin = BlenderWindow.client_origin(BlenderWindow.window_hwnd(c['window']))
        ctypes.windll.user32.SetCursorPos(origin[0]+x,
                                       origin[1]+c['window'].height-1-y)
        BlenderWindow.set_keyboard_focus(BlenderWindow.window_hwnd(c['window']))

    def event(kind, value='PRESS', xy=None, **mods):
        c = view()
        r = c['region']
        x, y = xy or (r.x+r.width//2, r.y+r.height//2)
        c['window'].event_simulate(type=kind, value=value, x=int(x), y=int(y), **mods)

    def key(kind, **mods):
        native_focus()
        event('MOUSEMOVE', 'NOTHING')
        event(kind, **mods)
        event(kind, 'RELEASE', **mods)

    def stroke(label, shift=False, ctrl=False, x_fraction=.46):
        c = view()
        r = c['region']
        projected = view3d_utils.location_3d_to_region_2d(
            r, c['area'].spaces.active.region_3d, form().matrix_world.translation)
        require(label+' has a projected surface target', projected is not None)
        corners = [view3d_utils.location_3d_to_region_2d(
            r, c['area'].spaces.active.region_3d, form().matrix_world @ Vector(corner))
            for corner in form().bound_box]
        radius = (max(p.x for p in corners)-min(p.x for p in corners))/2
        xy = (r.x+int(projected.x+radius*4*(x_fraction-.5)), r.y+int(projected.y))
        local_xy = (xy[0]-r.x, xy[1]-r.y)
        rv = c['area'].spaces.active.region_3d
        origin = view3d_utils.region_2d_to_origin_3d(r, rv, local_xy)
        direction = view3d_utils.region_2d_to_vector_3d(r, rv, local_xy)
        hit = bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),
                                       origin, direction)
        result['observations'][label+' setup'] = dict(
            region=(r.x,r.y,r.width,r.height), projected=tuple(projected), projected_radius=radius,
            view_location=tuple(rv.view_location), view_distance=rv.view_distance,
            layer=form().active_shape_key_index,
            record=state.get().record_layer, modals=[o.bl_idname for o in c['window'].modal_operators])
        require(label+' starts on the active surface', hit[0] and hit[4] == form(),
                hit[4].name if hit[0] else 'no hit')
        native_focus(xy)
        yield .15
        mods = dict(shift=shift, ctrl=ctrl)
        for enabled, name in ((shift, 'LEFT_SHIFT'), (ctrl, 'LEFT_CTRL')):
            if enabled:
                event(name, xy=xy, **mods)
        event('MOUSEMOVE', 'NOTHING', xy, **mods)
        event('LEFTMOUSE', xy=xy, **mods)
        yield .12
        if ctrl:
            # Ctrl-click blurs; native masking starts only on CLICK_DRAG.
            event('MOUSEMOVE', 'NOTHING', (xy[0]+14, xy[1]), **mods)
            yield .12
        modals = [o.bl_idname for o in c['window'].modal_operators]
        require(label+' uses native Sculpt paint', 'SCULPT_OT_brush_stroke' in modals,
                modals)
        for dx in ((21, 28, 35, 42, 49) if ctrl else (7, 14, 21, 28, 35)):
            event('MOUSEMOVE', 'NOTHING', (xy[0]+dx, xy[1]), **mods)
            yield .07
        end_x = xy[0]+(49 if ctrl else 35)
        event('LEFTMOUSE', 'RELEASE', (end_x, xy[1]), **mods)
        for enabled, name in ((shift, 'LEFT_SHIFT'), (ctrl, 'LEFT_CTRL')):
            if enabled:
                event(name, 'RELEASE', (end_x, xy[1]))
        yield .3

    def evaluated():
        with bpy.context.temp_override(**view()), ops.object_mode():
            bpy.context.view_layer.update()
            obj = form().evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = obj.to_mesh()
            try:
                return [tuple(v.co) for v in mesh.vertices]
            finally:
                obj.to_mesh_clear()

    # Fixture construction is explicit; no authored scene is loaded or edited.
    with bpy.context.temp_override(**view()):
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32)
        bpy.context.object.name = FORM
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12,
                                            radius=.45, location=(3, 0, 0))
        bpy.context.object.name = OTHER
        bpy.context.object.select_set(False)
        form().select_set(True)
        bpy.context.view_layer.objects.active = form()
        bpy.ops.ed.undo_push(message='Artist session fixture')
    desktop.cycle_right_dock('ATTRIBUTE_EDITOR')
    yield .3
    ae = attribute_editor.ensure_attribute_editor_widget()
    focus(ae.spn_sx)
    ae.spn_sx.lineEdit().selectAll()
    T.QTest.keyClicks(ae.spn_sx.lineEdit(), '1.15')
    T.QTest.keyClick(ae.spn_sx, C.Qt.Key_Return)
    yield .25
    check('modeling scale edit reaches actual selected mesh', abs(form().scale.x-1.15)<1e-6)
    key('Z')
    yield .25
    check('modeling Undo restores scale before sculpting', form().scale.x == 1)
    key('Z', shift=True)
    yield .25
    check('modeling Redo restores scale before sculpting', abs(form().scale.x-1.15)<1e-6)
    sh = shelf._shelf_instances[0]
    tab, tiles = next((name, tiles) for name, tiles in sh.tile_buttons.items()
                      if any(t.spec['id'] == 'sculpt_mode' for t in tiles))
    sh.tabs.setCurrentIndex(list(sh.tile_buttons).index(tab))
    yield from click(next(t for t in tiles if t.spec['id'] == 'sculpt_mode'))
    yield .5
    require('shelf enters actual Sculpt Studio', sculpt.is_engaged()
            and bpy.context.mode == 'SCULPT')
    panel = zbrush_panel._panels[0]
    key('F')
    yield .3
    panel.palettes['Layers'].setChecked(True)
    yield from click(panel.buttons['+ New Layer'])
    require('layer button starts base recording', form().active_shape_key_index > 0
            and state.get().record_layer)
    layer_name = form().active_shape_key.name
    basis = points(form().data.shape_keys.reference_key)
    empty_layer = points(form().active_shape_key)
    yield from click(layout._favorites.tiles['ST'])
    state.get().draw_size = 90
    state.get().z_intensity = 70
    yield .2
    yield from stroke('base form stroke')
    base = points(form().data.shape_keys.key_blocks[layer_name])
    require('native base stroke records a meaningful layer delta',
            difference(base, empty_layer) > 1e-4, difference(base, empty_layer))
    check('base stroke preserves every Basis vertex',
          points(form().data.shape_keys.reference_key) == basis)
    key('Z')
    yield .3
    check('base stroke Undo restores the complete empty layer',
          points(form().data.shape_keys.key_blocks[layer_name]) == empty_layer)
    key('Z', shift=True)
    yield .3
    check('base stroke Redo restores all authored layer vertices',
          points(form().data.shape_keys.key_blocks[layer_name]) == base)
    yield from stroke('temporary Smooth stroke', shift=True)
    smoothed = points(form().data.shape_keys.key_blocks[layer_name])
    require('held Smooth changes the recorded base form', difference(smoothed, base)>1e-5,
            difference(smoothed, base))
    check('Smooth release restores the chosen brush presentation',
          state.get().active_zbrush_brush == 'Standard' and 'held' not in layout._left.mode.text())
    yield from stroke('mask stroke', ctrl=True, x_fraction=.53)
    require('native mask stroke writes protection', max(ops.mask_values(form()))>.01)
    check('mask stroke does not edit the base layer',
          points(form().data.shape_keys.key_blocks[layer_name]) == smoothed)
    panel.palettes['Masking'].setChecked(True)
    yield from click(panel.buttons['Clear'])
    check('Mask Clear removes actual protection', max(ops.mask_values(form()))<.001)
    # Select another real SubTool, then return through the actual list rows.
    panel.root.ensureWidgetVisible(panel.subtools)
    yield .25
    for name in (OTHER, FORM):
        item = next(panel.subtools.topLevelItem(i) for i in range(panel.subtools.topLevelItemCount())
                    if panel.subtools.topLevelItem(i).data(0, C.Qt.UserRole) == name)
        panel.subtools.scrollToItem(item)
        focus(panel.subtools)
        rect = panel.subtools.visualItemRect(item)
        T.QTest.mouseClick(panel.subtools.viewport(), C.Qt.LeftButton,
                           pos=C.QPoint(max(60, rect.center().x()), rect.center().y()))
        yield .3
        require('SubTool row selects '+name, bpy.context.object.name == name
                and bpy.context.mode == 'SCULPT')
    check('SubTool return retains exact base layer and recording',
          form().active_shape_key.name == layer_name and state.get().record_layer
          and points(form().active_shape_key) == smoothed)
    key('F')
    yield .25
    panel.palettes['Geometry'].setChecked(True)
    yield from click(panel.buttons['Divide'])
    require('Divide enters native Multires detail', ops.multires() is not None
            and ops.multires().sculpt_levels == 1 and not state.get().record_layer)
    check('Divide remembers base target and preserves complete layer',
          ops.shape_editor_return_key().name == layer_name
          and points(form().data.shape_keys.key_blocks[layer_name]) == smoothed)
    # Three-key mnemonic selection uses the same browser as an artist.
    key('B')
    yield .2
    popup = sculpt_widgets._current_popup
    require('B opens the real brush browser mid-session', popup is not None and popup.isVisible())
    T.QTest.keyClick(popup, C.Qt.Key_D)
    T.QTest.keyClick(popup, C.Qt.Key_S)
    yield .3
    check('B D S selects actual subtractive DamStandard',
          state.get().active_zbrush_brush == 'DamStandard' and state.brush().direction == 'SUBTRACT')
    before_detail = evaluated()
    # Preserve this exact native state for a separate Blender-only precision
    # control. Saving a copy does not replace the running scene or history.
    baseline_fixture = ROOT.parent / '.test_env/continuous_artist_pre_detail.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(baseline_fixture), copy=True)
    yield .2
    yield from stroke('high-resolution detail stroke')
    detail = evaluated()
    require('native detail stroke changes evaluated Multires surface',
            difference(detail, before_detail)>1e-4, difference(detail, before_detail))
    check('detail preserves the entire base layer and Basis',
          points(form().data.shape_keys.key_blocks[layer_name]) == smoothed
          and points(form().data.shape_keys.reference_key) == basis)
    key('Z')
    yield .3
    undo_detail = evaluated()
    undo_delta = difference(undo_detail, before_detail)
    undo_rms = math.sqrt(sum(sum((x-y)**2 for x,y in zip(p,q))
                             for p,q in zip(undo_detail,before_detail))/len(before_detail))
    result['observations']['detail_undo'] = dict(
        delta=undo_delta, rms=undo_rms, max_allowance=GRID_UNDO_MAX,
        rms_allowance=GRID_UNDO_RMS, native_control='native_multires_undo_precision.json',
        layer=form().active_shape_key_index,
        level=ops.multires().sculpt_levels, mode=bpy.context.mode,
        changed=sum(p != q for p, q in zip(undo_detail, before_detail)),
        base_delta=difference(points(form().data.shape_keys.key_blocks[layer_name]), smoothed))
    check('detail Undo restores evaluated pre-stroke surface',
          undo_delta<GRID_UNDO_MAX and undo_rms<GRID_UNDO_RMS,
          result['observations']['detail_undo'])
    key('Z', shift=True)
    yield .3
    check('detail Redo restores evaluated surface', difference(evaluated(), detail)<1e-6)
    fixture = ROOT.parent / '.test_env/continuous_artist_session.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(fixture), copy=True)
    yield .2
    from landfall_studio.ui import menus
    menus.run_op('wm.open_mainfile', filepath=str(fixture))
    yield 1.5
    check('reopen preserves complete base data and target',
          points(form().data.shape_keys.key_blocks[layer_name]) == smoothed
          and points(form().data.shape_keys.reference_key) == basis
          and ops.shape_editor_return_key().name == layer_name)
    check('reopen preserves native high detail', difference(evaluated(), detail)<1e-6)
    sculpt.enter()
    yield .5
    panel = zbrush_panel._panels[0]
    panel.palettes['Layers'].setChecked(True)
    yield from click(panel.buttons['⇄ GoZ to Shape Editor'])
    yield .4
    check('GoZ returns to Modeling Shape Editor', not sculpt.is_engaged()
          and bpy.context.mode == 'OBJECT' and desktop._right_dock.mode == 'SHAPE_EDITOR')
    se = desktop._right_dock._ensure_host_container().se_widget
    check('Shape Editor selects the actual brush-authored layer',
          se._target_mesh == form() and se._selected_key_name == layer_name
          and form().active_shape_key.name == layer_name)
    check('GoZ retains complete base and high-detail work',
          points(form().data.shape_keys.key_blocks[layer_name]) == smoothed
          and points(form().data.shape_keys.reference_key) == basis
          and difference(evaluated(), detail)<1e-6)
    result['observations'].update(base_delta=difference(base, empty_layer),
        smoothing_delta=difference(smoothed, base), detail_delta=difference(detail, before_detail),
        layer=layer_name, vertices=len(basis), evaluated_vertices=len(detail),
        recent_gestures=list(gestures.history[-12:]))
    result['ok'] = not result['failed']
    save()
    landfall_studio.unregister()
    print('CONTINUOUS_ARTIST_SESSION', len(result['passed']), 'passed', len(result['failed']), 'failed', flush=True)
    bpy.ops.wm.quit_blender()


steps = suite()


def tick():
    try:
        return next(steps)
    except StopIteration:
        return None
    except Exception:
        result['failed'].append({'exception': traceback.format_exc()})
        save()
        traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=.5, persistent=True)
