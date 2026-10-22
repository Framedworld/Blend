"""Native Undo for the existing Channels controller and its Qt gestures.

The adapter is local to the live Studio slots instance. It neither patches the
upstream Channels class nor adds another event filter, dispatcher or undo stack.
"""
from __future__ import annotations

from contextlib import contextmanager
from ..commands import scene_edits

_adapters = []
_preview_depth = 0


@contextmanager
def native_preview():
    """A native modal operator already owns the history for these previews."""
    global _preview_depth
    _preview_depth += 1
    try:
        yield
    finally:
        _preview_depth -= 1


def _freeze(value):
    if hasattr(value, 'to_dict'):
        return _freeze(value.to_dict())
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    try:
        return tuple(_freeze(item) for item in value)
    except TypeError:
        return repr(value)


def _state(controller, objects):
    """Exact edited channels, custom properties, locks and animation state."""
    def curve(fc):
        return (fc.data_path, fc.array_index, fc.mute,
                tuple((tuple(k.co), tuple(k.handle_left), tuple(k.handle_right),
                       k.interpolation, k.type) for k in fc.keyframe_points))
    return tuple((o.name, tuple(o.location), tuple(o.rotation_euler),
                  tuple(o.rotation_quaternion), tuple(o.rotation_axis_angle),
                  tuple(o.scale), tuple(o.lock_location), tuple(o.lock_rotation),
                  tuple(o.lock_scale), o.lock_rotation_w, o.lock_rotations_4d, o.rotation_mode, _freeze(dict(o.items())),
                  tuple(curve(fc) for fc in controller._iter_fcurves(o)),
                  tuple(curve(fc) for fc in getattr(o.animation_data, 'drivers', ())))
                 for o in objects)


class _Adapter:
    _MUTATIONS = {
        'set_channel_value': 'Edit Channel', 'set_lock': 'Channel Lock',
        'reset_to_default': 'Reset Channels', 'set_key_at_current_time': 'Key Channels',
        'break_connections': 'Break Channel Connections', 'set_mute': 'Mute Channels',
        'set_breakdown_key': 'Channel Breakdown', 'create_attribute': 'Add Attribute',
        'delete_attributes': 'Delete Attributes', 'rename_attribute': 'Rename Attribute',
        'rename_node': 'Rename Object', 'paste_values': 'Paste Channels',
        'freeze_transforms': 'Freeze Transforms', 'unfreeze_transforms': 'Unfreeze Transforms',
    }

    def __init__(self, slots):
        self.slots, self.controller = slots, slots.controller
        self.gesture = None
        self.originals = {}
        table=slots.ui.tbl000
        def targets():
            return tuple(o.as_pointer() for o in self.controller.get_selected_nodes())
        self.presented_targets=targets()
        self.current_targets=targets
        original_refresh=slots._refresh_table
        def refresh(widget):
            from qtpy import QtWidgets
            current=targets()
            if widget.state()==QtWidgets.QAbstractItemView.EditingState:
                if current==self.presented_targets:
                    return  # A native HWND focus handoff can briefly clear Qt focus.
                editor=widget.indexWidget(widget.currentIndex())
                if editor is not None:
                    widget.closeEditor(editor,QtWidgets.QAbstractItemDelegate.RevertModelCache)
            if self.gesture and self.gesture.active and current!=self.presented_targets:
                self.gesture.cancel()
            result=original_refresh(widget)
            self.presented_targets=current
            return result
        self.replace(slots,'_refresh_table',refresh)
        for name, label in self._MUTATIONS.items():
            original = getattr(self.controller, name)
            def mutate(objects, *args, _original=original, _label=label, **kwargs):
                if _preview_depth:
                    return _original(objects, *args, **kwargs)
                targets = list(objects) if isinstance(objects, (tuple, list)) else [objects]
                targets = [o for o in targets if o is not None]
                current=self.current_targets()
                if current!=self.presented_targets or any(o.as_pointer() not in current for o in targets):
                    self.sync_targets()
                    from .desktop import set_command_feedback
                    set_command_feedback(_label,'Selection changed; the pending channel edit was discarded','WARNING')
                    return False
                if getattr(slots,'_scrub_state',None) is not None:
                    return _original(objects,*args,**kwargs)
                return scene_edits.commit(_label, lambda: _original(objects, *args, **kwargs),
                                          lambda: _state(self.controller, targets))
            self.replace(self.controller, name, mutate)

        start, finish, wheel = slots._on_scrub_started, slots._on_scrub_finished, slots._on_wheel_scrolled

        def started(row, col):
            if self.gesture:
                self.gesture.cancel()
            start(row, col)
            state = getattr(slots, '_scrub_state', None)
            if not state:
                return
            targets, descriptor = list(state['starts']), dict(state['descriptor'])
            def read():
                return tuple(self.controller.get_channel_value(o, descriptor) for o in targets)
            def write(values):
                for o, value in zip(targets, values):
                    self.originals[(self.controller, 'set_channel_value')]([o], descriptor, str(value))
            def cancel(refresh=True):
                slots._scrub_state = None
                if slots.ui.tbl000._scrub_active is not None:
                    from uitk.managers.cursor_manager import CursorManager
                    slots.ui.tbl000._scrub_active=None
                    CursorManager.pop(slots.ui.tbl000)
                self.gesture=None
                if refresh:slots._refresh_table(slots.ui.tbl000)
            self.gesture = scene_edits.ValueGesture('Scrub Channel', read, write,
                widget=slots.ui.tbl000, on_cancel=cancel,on_abandon=lambda:cancel(False))

        def finished(row, col):
            gesture, self.gesture = self.gesture, None
            if gesture:
                gesture.finish()
            return finish(row, col)

        def scrolled(*args):
            targets = list(self.controller.get_selected_nodes())
            return scene_edits.commit('Step Channel', lambda: wheel(*args),
                                      lambda: _state(self.controller, targets))

        self.replace(slots, '_on_scrub_started', started)
        self.replace(slots, '_on_scrub_finished', finished)
        self.replace(slots, '_on_wheel_scrolled', scrolled)
        # The upstream owner rewires from these same methods on subsequent shows.
        slots._wire_table_signals(slots.ui.tbl000)

    def replace(self, owner, name, replacement):
        self.originals[(owner, name)] = getattr(owner, name)
        setattr(owner, name, replacement)

    def sync_targets(self):
        if self.current_targets()!=self.presented_targets:
            self.slots._refresh_table(self.slots.ui.tbl000)

    def uninstall(self):
        if self.gesture:
            self.gesture.cancel()
        for (owner, name), original in self.originals.items():
            setattr(owner, name, original)
        try:
            self.slots._wire_table_signals(self.slots.ui.tbl000)
        except RuntimeError:
            pass  # The upstream panel may have been destroyed first.


def ensure(slots):
    if slots is None or any(adapter.slots is slots for adapter in _adapters):
        return
    _adapters.append(_Adapter(slots))


def teardown():
    for adapter in _adapters:
        adapter.uninstall()
    _adapters.clear()


def sync_targets(slots):
    for adapter in _adapters:
        if adapter.slots is slots:
            adapter.sync_targets()
            return
