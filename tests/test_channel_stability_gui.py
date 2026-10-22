"""Disposable native GUI regression for live Channel Box transforms."""
import json
import sys
import traceback
import faulthandler
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'output/channel_stability_gui_results.json'
results = {'passed': [], 'failed': [], 'input_method': 'Native event_simulate plus Qt model/window event observations'}
trace_file = (ROOT / 'output/channel_stability_trace.log').open('w')
faulthandler.dump_traceback_later(45, repeat=True, file=trace_file)

def progress(stage):
    results['stage'] = stage
    OUT.write_text(json.dumps(results, indent=2), encoding='utf-8')

def check(name, ok, detail=None):
    results['passed' if ok else 'failed'].append(name if ok else {'name': name, 'detail': str(detail)})

def run():
    progress('factory scene')
    bpy.context.preferences.view.show_splash = False
    bpy.ops.wm.read_homefile()
    import landfall_studio
    from landfall_studio import ui
    from landfall_studio.ui import desktop, channel_box_ext
    progress('register')
    landfall_studio.register()
    from PySide6 import QtCore
    progress('desktop restore')
    ui.restore_workspace_desktop(restore_script_output=False)
    progress('scene setup')
    window = bpy.context.window_manager.windows[0]
    area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    ov = dict(window=window, screen=window.screen, area=area, region=region)
    with bpy.context.temp_override(**ov):
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.active_object
        obj['artist_value'] = 1.0
        obj.modifiers.new('Stable Bevel', 'BEVEL')
    yield .8
    # Establish a ready desktop, rather than attributing its deferred first
    # resize to the subsequent transform. Keep the no-move/no-resize gate below.
    from landfall_studio.sculpt import layout
    dock=desktop._right_dock._inner_dock
    results['layout_readiness']={'starting_rect':dock._last_rect,'starting_pending':len(layout._pending)}
    previous=None;stable=0
    for _ in range(30):
        rect=dock._last_rect
        stable=stable+1 if rect is not None and rect==previous and not layout._pending else 0
        if stable>=3:break
        previous=rect;yield .1
    results['layout_readiness'].update(settled_rect=dock._last_rect,pending=len(layout._pending),stable_frames=stable)
    if stable<3:raise RuntimeError('Initial native desktop layout did not settle')
    area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
    region=next(r for r in area.regions if r.type=='WINDOW')
    ov=dict(window=window,screen=window.screen,area=area,region=region)
    progress('transform checks')
    desktop.sync_channels_now()
    widget, slots = desktop.get_panel_widget_and_slots('channels')
    tbl = widget.tbl000
    ext = channel_box_ext._channel_box_ext_instance
    row = next(r for r in range(tbl.rowCount()) if tbl.item(r, slots.COL_NAME).text() == 'location_x')
    tbl.selectRow(row)
    item = tbl.item(row, slots.COL_VALUE)
    tree_item = ext.tree_inputs.topLevelItem(0)
    tree_item.setExpanded(False)
    resets = []
    tbl.model().modelReset.connect(lambda: resets.append(True))
    events = []
    class Observer(QtCore.QObject):
        def eventFilter(self, watched, event):
            if event.type() in (QtCore.QEvent.Hide, QtCore.QEvent.Show, QtCore.QEvent.Resize, QtCore.QEvent.Move):
                events.append(str(event.type()))
            return False
    observer = Observer(widget)
    widget.installEventFilter(observer)
    initial_rect = desktop._right_dock._inner_dock._last_rect
    for i in range(20):
        obj.location.x = i * .15
        bpy.context.view_layer.update()
        desktop._on_live_scene_or_depsgraph_update()
        yield .025
    check('transform values update live', abs(float(tbl.item(row, slots.COL_VALUE).text()) - 2.85) < .001)
    check('transform updates preserve value cell identity', tbl.item(row, slots.COL_VALUE) is item)
    check('transform updates do not reset Qt table model', not resets, resets)
    check('transform updates preserve channel selection', row in {i.row() for i in tbl.selectedIndexes()})
    check('transform updates preserve collapsed INPUTS node', ext.tree_inputs.topLevelItem(0) is tree_item and not tree_item.isExpanded())
    check('transform updates do not hide or reposition channel widget', not events, events)
    check('dock geometry stays cached', desktop._right_dock._inner_dock._last_rect == initial_rect)
    # A real native modal transform must also update the existing cells.
    progress('native modal move')
    before_move = obj.location.x
    with bpy.context.temp_override(**ov):
        bpy.ops.transform.translate('INVOKE_DEFAULT', constraint_axis=(True, False, False))
    yield .1
    x, y = region.x + region.width//2, region.y + region.height//2
    for i in range(1, 5):
        window.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x+i*12, y=y)
        yield .1
    window.event_simulate(type='LEFTMOUSE', value='PRESS', x=x+48, y=y)
    window.event_simulate(type='LEFTMOUSE', value='RELEASE', x=x+48, y=y)
    yield .3
    desktop.sync_channels_now()
    check('native modal move changes asset position', abs(obj.location.x-before_move) > .001)
    check('native modal move updates cell without replacing it', tbl.item(row, slots.COL_VALUE) is item and abs(float(item.text()) - obj.location.x) < .001)
    check('native modal move keeps table model intact', not resets, resets)
    # Structural changes still rebuild, and two-way editing still writes to bpy.
    obj.lock_location[0] = True
    desktop.sync_channels_now()
    check('lock change refreshes controller row state', bool(resets))
    obj.lock_location[0] = False
    desktop.sync_channels_now()
    result = desktop.set_channel_value_from_ui('location_x', 7.25)
    check('two way Qt edit still changes asset', result['ok'] and abs(obj.location.x-7.25) < .001, result)
    with bpy.context.temp_override(**ov):
        bpy.ops.mesh.primitive_uv_sphere_add()
        other = bpy.context.active_object
    desktop.sync_channels_now()
    check('selection change updates target and inputs', other.name in desktop.get_channels_snapshot()['target'] and ext.tree_inputs.topLevelItemCount() == 0)
    landfall_studio.unregister()
    faulthandler.cancel_dump_traceback_later()
    results['ok'] = not results['failed']
    OUT.write_text(json.dumps(results, indent=2), encoding='utf-8')
    bpy.ops.wm.quit_blender()

steps = run()
def tick():
    try:
        return next(steps)
    except StopIteration:
        return None
    except Exception:
        results['failed'].append(traceback.format_exc())
        results['ok'] = False
        OUT.write_text(json.dumps(results, indent=2), encoding='utf-8')
        bpy.ops.wm.quit_blender()
        return None
bpy.app.timers.register(tick, first_interval=.5, persistent=True)
