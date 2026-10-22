"""Studio Qt edits participate in Blender's native history, never a second stack.

Callbacks exist only during a synchronous operator invocation. The operator is
internal and deliberately not REGISTER/repeatable: native Undo/Redo restores
Blender data, rather than replaying a callback against stale scene references.
"""
from __future__ import annotations

import itertools
from typing import Any, Callable

try:
    import bpy
except ImportError:
    bpy = None

_serial = itertools.count(1)
_pending = {}
_depth = 0
_gestures = set()


def _value(value):
    if isinstance(value, dict):return tuple(sorted((k,_value(v)) for k,v in value.items()))
    if isinstance(value, (tuple,list)):return tuple(_value(v) for v in value)
    return value


class ValueGesture:
    """Preview one scalar gesture, then commit its end value as one native edit."""
    def __init__(self,label,read,write,widget=None,preview_write=None,read_state=None,on_cancel=None,on_abandon=None):
        self.label,self.read,self.write,self.widget=label,read,write,widget
        self.preview_write=preview_write or write
        self.read_state=read_state or read
        self.on_cancel=on_cancel
        self.on_abandon=on_abandon
        self.initial=read();self.active=True;self.previewed=False
        _gestures.add(self)

    def preview(self,value):
        if self.active:
            self.previewed=True
            return self.preview_write(value)

    def finish(self,final=None):
        if not self.active:return
        self.active=False;_gestures.discard(self)
        try:
            final=self.read() if final is None else final
            if _value(final)==_value(self.initial):return
            self.preview_write(self.initial)
            return commit(self.label,lambda:self.write(final),self.read_state)
        except (ReferenceError,KeyError,AttributeError):return

    def cancel(self,restore=True):
        if not self.active:return
        self.active=False;_gestures.discard(self)
        if restore:
            try:self.preview_write(self.initial)
            except (ReferenceError,KeyError,AttributeError,RuntimeError):pass
        if restore and self.on_cancel:
            try:self.on_cancel()
            except RuntimeError:pass  # Its Qt owner may already be closing.
        elif not restore and self.on_abandon:
            try:self.on_abandon()
            except RuntimeError:pass


def cancel_all(restore=True):
    for gesture in list(_gestures):gesture.cancel(restore)


def handle_input(obj,event):
    """Called by Studio's existing input owner; never installs another filter."""
    if not _gestures:return False
    from qtpy import QtCore
    if event.type()==QtCore.QEvent.KeyPress and event.key()==QtCore.Qt.Key_Escape:
        cancel_all();event.accept();return True
    if event.type()==QtCore.QEvent.ApplicationDeactivate:cancel_all()
    elif event.type()==QtCore.QEvent.WindowDeactivate:
        for gesture in list(_gestures):
            if gesture.widget is not None and gesture.widget.window()==obj:gesture.cancel()
    elif event.type()==QtCore.QEvent.Hide:
        from qtpy import QtWidgets
        if isinstance(obj,QtWidgets.QWidget):
            for gesture in list(_gestures):
                if gesture.widget is obj or (gesture.widget is not None and obj.isAncestorOf(gesture.widget)):gesture.cancel()
    return False


def commit(label: str, callback: Callable[[], Any], read_state=None):
    """Commit one user action; optional state reader rejects unchanged edits."""
    if bpy is None or bpy.app.background or _depth:
        return callback()
    # A different user action retires any unfinished inspector preview first.
    # ValueGesture.finish removes itself before calling commit.
    cancel_all()
    token=str(next(_serial))
    request={'callback':callback,'read':read_state,'label':label,'result':None}
    _pending[token]=request
    try:
        from ..ui.menus import view3d_override
        with bpy.context.temp_override(**view3d_override()):
            bpy.ops.landfall_studio.scene_edit('EXEC_DEFAULT',True,token=token)
        result=request['result']
    finally:
        _pending.pop(token,None)
    if isinstance(result,dict) and not result.get('ok',True):
        from ..ui.desktop import set_command_feedback
        set_command_feedback(label,result.get('error') or result.get('reason') or 'Edit did not finish','ERROR')
    return result


if bpy is not None:
    class LANDFALL_STUDIO_OT_scene_edit(bpy.types.Operator):
        bl_idname='landfall_studio.scene_edit'
        bl_label='Edit Studio Properties'
        bl_options={'UNDO','INTERNAL'}
        token:bpy.props.StringProperty(options={'SKIP_SAVE'})

        def execute(self,context):
            global _depth
            request=_pending.get(self.token)
            if request is None:return {'CANCELLED'}
            reader=request['read']
            try:
                before=_value(reader()) if reader else None
                _depth+=1
                try:result=request['callback']()
                finally:_depth-=1
                request['result']=result
                if result is False or (isinstance(result,dict) and not result.get('ok',True)):
                    return {'CANCELLED'}
                if reader and before==_value(reader()):return {'CANCELLED'}
                return {'FINISHED'}
            except Exception as exc:
                request['result']={'ok':False,'error':str(exc)}
                self.report({'WARNING'},str(exc))
                return {'CANCELLED'}

    CLASSES=(LANDFALL_STUDIO_OT_scene_edit,)
else:
    CLASSES=()
