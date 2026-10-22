"""Pen UI adapter, called by Studio's existing QApplication input owner.

Only marked sculpt widgets are handled. Blender's canvas/stroke events never
enter this path. UI contacts use Qt logical coordinates and native widget actions.
"""
import time
import weakref


def polish(root):
    from PySide6 import QtCore
    root.setProperty('landfallSculptInput',True)
    root.setAttribute(QtCore.Qt.WA_TabletTracking,True)
    return root


def slider(parent=None):
    """Direct-position tip/mouse taps; native dragging, arrows and release signal."""
    from PySide6 import QtCore,QtWidgets
    class TipSlider(QtWidgets.QSlider):
        def mousePressEvent(self,event):
            if event.button()!=QtCore.Qt.LeftButton:return super().mousePressEvent(event)
            opt=QtWidgets.QStyleOptionSlider();self.initStyleOption(opt)
            style=self.style();groove=style.subControlRect(QtWidgets.QStyle.CC_Slider,opt,QtWidgets.QStyle.SC_SliderGroove,self)
            handle=style.subControlRect(QtWidgets.QStyle.CC_Slider,opt,QtWidgets.QStyle.SC_SliderHandle,self)
            self.setFocus(QtCore.Qt.MouseFocusReason)
            self._tip_handle_grab=handle.contains(event.position().toPoint())
            self._tip_origin=event.position().x();self._tip_start=self.sliderPosition()
            self.setSliderDown(True)
            if self._tip_handle_grab:
                event.accept();return
            pos=event.position().x()-groove.x()-handle.width()/2
            self.setSliderPosition(QtWidgets.QStyle.sliderValueFromPosition(self.minimum(),self.maximum(),round(pos),max(1,groove.width()-handle.width()),opt.upsideDown))
            event.accept()
        def mouseMoveEvent(self,event):
            if self.isSliderDown():
                opt=QtWidgets.QStyleOptionSlider();self.initStyleOption(opt)
                style=self.style();groove=style.subControlRect(QtWidgets.QStyle.CC_Slider,opt,QtWidgets.QStyle.SC_SliderGroove,self)
                handle=style.subControlRect(QtWidgets.QStyle.CC_Slider,opt,QtWidgets.QStyle.SC_SliderHandle,self)
                span=max(1,groove.width()-handle.width())
                if getattr(self,'_tip_handle_grab',False):
                    delta=round((event.position().x()-self._tip_origin)*(self.maximum()-self.minimum())/span)
                    self.setSliderPosition(self._tip_start+(-delta if opt.upsideDown else delta))
                else:
                    pos=event.position().x()-groove.x()-handle.width()/2
                    self.setSliderPosition(QtWidgets.QStyle.sliderValueFromPosition(self.minimum(),self.maximum(),round(pos),span,opt.upsideDown))
                event.accept()
            else:super().mouseMoveEvent(event)
        def mouseReleaseEvent(self,event):
            if event.button()==QtCore.Qt.LeftButton and self.isSliderDown():
                self.setValue(self.sliderPosition());self.setSliderDown(False);event.accept()
            else:super().mouseReleaseEvent(event)
    w=TipSlider(QtCore.Qt.Horizontal,parent);w.setMinimumHeight(18);w.setMaximumHeight(22)
    return w


class PointerInput:
    def __init__(self):
        from PySide6 import QtCore,QtGui,QtWidgets
        self.C=QtCore;self.G=QtGui;self.W=QtWidgets
        self.gesture=None;self.tablet=None;self.dispatching=False
        self.echo_position=None;self.echo_until=0.;self.native={};self.grabbed=None;self.history=[];self.errors=[]

    @property
    def active(self):return self.gesture is not None or self.tablet is not None

    def scope(self,obj):
        while isinstance(obj,self.W.QWidget):
            if obj.property('landfallSculptInput'):return obj
            obj=obj.parentWidget()
        return None

    def scroll(self,obj):
        # Item rows and scrollbars keep their native editing/selection gestures.
        while isinstance(obj,self.W.QWidget):
            if isinstance(obj,self.W.QAbstractItemView):return None
            if isinstance(obj,self.W.QScrollArea):
                return obj if obj.verticalScrollBar().maximum() or obj.horizontalScrollBar().maximum() else None
            obj=obj.parentWidget()
        return None

    def combo(self,obj):
        while isinstance(obj,self.W.QWidget):
            if isinstance(obj,self.W.QComboBox):return obj
            obj=obj.parentWidget()
        return None

    def _native_pen(self,obj):
        # Local HWND opt-out from Windows press-and-hold/flick interpretation.
        # Never create native child handles or change the user's tablet settings.
        import sys
        if sys.platform!='win32' or not obj.property('landfallSculptInput'):return
        import ctypes
        hwnd=int(obj.internalWinId() or 0)
        if not hwnd:return
        existing=self.native.get(hwnd)
        if existing and existing[0]() is obj:return
        # Windows may reuse the handle of a destroyed picker for a new one.
        if existing:self.native.pop(hwnd)
        user=ctypes.windll.user32;user.GetPropW.restype=ctypes.c_void_p
        key='MicrosoftTabletPenServiceProperty';old=user.GetPropW(ctypes.c_void_p(hwnd),key)
        flags=int(old or 0)|0x1|0x8|0x10|0x10000
        if user.SetPropW(ctypes.c_void_p(hwnd),key,ctypes.c_void_p(flags)):
            self.native[hwnd]=(weakref.ref(obj),old)

    def _grab(self,target):
        if self.W.QWidget.mouseGrabber() is None:
            target.grabMouse();self.grabbed=target

    def _release_grab(self,target=None):
        grab=self.W.QWidget.mouseGrabber()
        if grab and (grab is self.grabbed or grab is target):grab.releaseMouse()
        self.grabbed=None

    def cancel(self):
        g=self.gesture;t=self.tablet;self.gesture=None;self.tablet=None
        if t:
            try:
                target=t['target']
                if hasattr(target,'cancel_pen_interaction'):target.cancel_pen_interaction()
            except RuntimeError:pass
        if g:
            try:
                target=g['target']
                if isinstance(target,self.W.QAbstractButton):target.setDown(False)
                if isinstance(target,self.W.QSlider):
                    guard=self.C.QSignalBlocker(target) if getattr(target.window(),'finished',False) else None
                    target.setValue(g['value']);del guard
                    guard=self.C.QSignalBlocker(target);target.setSliderDown(False);del guard
                if g['area']:g['area'].viewport().unsetCursor()
            except RuntimeError:pass
        self._release_grab(g['target'] if g else None)

    def shutdown(self):
        self.cancel()
        import sys
        if sys.platform=='win32':
            import ctypes
            user=ctypes.windll.user32;key='MicrosoftTabletPenServiceProperty'
            for hwnd,(ref,old) in self.native.items():
                widget=ref()
                try:
                    if widget is None or int(widget.internalWinId() or 0)!=hwnd:continue
                    if old:user.SetPropW(ctypes.c_void_p(hwnd),key,ctypes.c_void_p(old))
                    else:user.RemovePropW(ctypes.c_void_p(hwnd),key)
                except RuntimeError:pass
        self.native.clear()

    def _send_mouse(self,target,kind,position,button,buttons,mods):
        local=self.C.QPointF(target.mapFromGlobal(position.toPoint()))
        scene=self.C.QPointF(target.window().mapFromGlobal(position.toPoint()))
        event=self.G.QMouseEvent(kind,local,scene,position,button,buttons,mods,self.C.Qt.MouseEventSynthesizedByApplication)
        if self._mouse(target,event):return
        self.dispatching=True
        try:self.W.QApplication.sendEvent(target,event)
        finally:self.dispatching=False

    def _tablet(self,obj,event):
        C=self.C;kind=event.type();position=event.globalPosition()
        if kind==C.QEvent.TabletPress:
            root=self.scope(obj)
            if root is None:return False
            self.cancel()
            popup=self.W.QApplication.activePopupWidget()
            outside=popup and not popup.rect().contains(popup.mapFromGlobal(position.toPoint()))
            surface=popup or root
            # Preserve an already resolved control or popup viewport. Re-hit
            # only container deliveries, never the underlying tray beneath a
            # floating combo/menu window.
            if not outside and (obj is root or type(obj) in (self.W.QWidget,self.W.QFrame,self.W.QScrollArea)):
                obj=obj.childAt(obj.mapFromGlobal(position.toPoint())) or obj
            self.history.append({'target':obj.objectName(),'class':type(obj).__name__,'popup':type(popup).__name__ if popup else None,'outside':bool(outside)})
            self.history=self.history[-48:]
            self.tablet={'target':obj,'dismissed':bool(outside)}
            if outside:
                popup.setAttribute(C.Qt.WA_NoMouseReplay,True)
                if hasattr(popup,'finish'):popup.finish()
                else:popup.close()
            else:
                combo=self.combo(obj)
                if combo and combo.isEnabled() and not (combo.isEditable() and isinstance(obj,self.W.QLineEdit)) and event.button()==C.Qt.LeftButton:
                    # Native combo containers intentionally discard an opening
                    # mouse release. Route pen taps through the widget API so a
                    # rapid second tap selects the visible item consistently.
                    self.tablet['combo']=combo
                    if popup:
                        view=combo.view();index=view.indexAt(view.viewport().mapFromGlobal(position.toPoint()))
                        self.tablet['index']=index
                        if index.isValid():view.setCurrentIndex(index)
                    else:
                        combo.setFocus(C.Qt.MouseFocusReason)
                        animated=self.W.QApplication.isEffectEnabled(C.Qt.UI_AnimateCombo)
                        self.W.QApplication.setEffectEnabled(C.Qt.UI_AnimateCombo,False)
                        try:combo.showPopup()
                        finally:self.W.QApplication.setEffectEnabled(C.Qt.UI_AnimateCombo,animated)
                else:self._grab(obj)
        if self.tablet is None:return False
        record=self.tablet;target=record['target']
        self.echo_position=position;self.echo_until=time.monotonic()+.15
        button=event.button()
        if kind==C.QEvent.TabletRelease:
            self.tablet=None;self._release_grab()
        if 'combo' in record:
            if kind==C.QEvent.TabletRelease and 'index' in record:
                combo=record['combo'];view=combo.view();local=view.viewport().mapFromGlobal(position.toPoint())
                index=view.indexAt(local)
                if view.viewport().rect().contains(local) and index.isValid() and index==record['index']:
                    combo.setCurrentIndex(index.row());combo.activated.emit(index.row());combo.hidePopup()
        elif not record['dismissed']:
            types={C.QEvent.TabletPress:C.QEvent.MouseButtonPress,C.QEvent.TabletMove:C.QEvent.MouseMove,C.QEvent.TabletRelease:C.QEvent.MouseButtonRelease}
            self._send_mouse(target,types[kind],position,button,event.buttons(),event.modifiers())
            if kind==C.QEvent.TabletRelease and button==C.Qt.RightButton:
                context=self.G.QContextMenuEvent(self.G.QContextMenuEvent.Mouse,target.mapFromGlobal(position.toPoint()),position.toPoint(),event.modifiers())
                self.W.QApplication.sendEvent(target,context)
        event.accept();return True

    def _mouse(self,obj,event):
        C=self.C;W=self.W;kind=event.type();position=event.globalPosition()
        if kind==C.QEvent.MouseButtonPress:
            if event.button()!=C.Qt.LeftButton:return False
            root=self.scope(obj)
            if root is None:return False
            area=self.scroll(obj)
            target=obj
            while isinstance(target,W.QWidget) and target is not root and not isinstance(target,(W.QAbstractButton,W.QAbstractSlider,W.QAbstractSpinBox,W.QComboBox,W.QLineEdit,W.QAbstractItemView,W.QGroupBox)):
                target=target.parentWidget()
            header=isinstance(target,W.QGroupBox) and target.isCheckable() and target.mapFromGlobal(position.toPoint()).y()<=25
            button=isinstance(target,W.QAbstractButton) and target.isEnabled()
            value=isinstance(target,(W.QAbstractSlider,W.QAbstractSpinBox,W.QComboBox,W.QLineEdit,W.QAbstractItemView))
            mode='header' if header else ('button' if button else ('control' if value else 'background'))
            if area is None and mode=='background':return False
            axis='x' if area and not area.verticalScrollBar().maximum() and area.horizontalScrollBar().maximum() else 'y'
            bar=(area.horizontalScrollBar() if axis=='x' else area.verticalScrollBar()) if area else None
            self.gesture={'target':target,'area':area,'bar':bar,'axis':axis,'mode':mode,'start':position,'scroll':bar.value() if bar else 0,'drag':False,'value':target.value() if isinstance(target,W.QSlider) else None}
            if area and mode in ('header','background'):self._grab(target)
            return mode in ('header','background')
        g=self.gesture
        if g is None:return False
        if kind==C.QEvent.MouseMove:
            delta=position-g['start'];area=g['area'];along=delta.x() if g['axis']=='x' else delta.y();across=delta.y() if g['axis']=='x' else delta.x()
            if area and g['mode']!='control' and (g['drag'] or (abs(along)>=8 and abs(along)>abs(across)*1.15)):
                g['drag']=True
                if isinstance(g['target'],W.QAbstractButton):g['target'].setDown(False)
                area.viewport().setCursor(C.Qt.SizeHorCursor if g['axis']=='x' else C.Qt.SizeVerCursor)
                g['bar'].setValue(g['scroll']-round(along))
                return True
            return g['mode'] in ('header','background')
        if kind==C.QEvent.MouseButtonRelease and event.button()==C.Qt.LeftButton:
            self.gesture=None
            if g['area']:g['area'].viewport().unsetCursor()
            if g['mode'] in ('header','background') or g['drag']:self._release_grab(g['target'])
            if g['mode']=='header' and not g['drag'] and (position-g['start']).manhattanLength()<12:
                g['target'].setChecked(not g['target'].isChecked())
            return g['mode'] in ('header','background') or g['drag']
        return False

    def handle(self,obj,event):
        try:return self._handle(obj,event)
        except Exception as exc:
            message=type(exc).__name__+': '+str(exc)
            if message not in self.errors:print('[Sculpt pen UI] '+message,flush=True)
            self.errors.append(message);self.errors=self.errors[-16:]
            self.cancel()
            if isinstance(obj,self.W.QWidget) and self.scope(obj):event.accept();return True
            return False

    def _handle(self,obj,event):
        if self.dispatching:return False
        C=self.C;W=self.W;kind=event.type()
        if kind in (C.QEvent.ApplicationDeactivate,C.QEvent.TabletLeaveProximity):
            self.cancel();return False
        contact=self.gesture or (self.tablet if self.tablet and not self.tablet.get('dismissed') else None)
        if kind==C.QEvent.Hide and contact:
            target=contact['target']
            if obj is target or (isinstance(obj,W.QWidget) and obj.isAncestorOf(target)):self.cancel()
        if not isinstance(obj,W.QWidget):return False
        if kind in (C.QEvent.Show,C.QEvent.WinIdChange):self._native_pen(obj)
        if kind in (C.QEvent.TabletPress,C.QEvent.TabletMove,C.QEvent.TabletRelease):return self._tablet(obj,event)
        if kind==C.QEvent.KeyPress and event.key()==C.Qt.Key_Escape and self.active:
            self.cancel();event.accept();return True
        if kind in (C.QEvent.MouseButtonPress,C.QEvent.MouseMove,C.QEvent.MouseButtonRelease):
            root=self.scope(obj)
            if self.echo_position is not None and root and event.source()!=C.Qt.MouseEventNotSynthesized and time.monotonic()<self.echo_until and (event.globalPosition()-self.echo_position).manhattanLength()<12:
                event.accept();return True
            if self.gesture or root:return self._mouse(obj,event)
        if kind==C.QEvent.Wheel and self.scope(obj) and not (event.modifiers()&C.Qt.ControlModifier):
            target=obj
            while target and not isinstance(target,(W.QAbstractSpinBox,W.QComboBox,W.QAbstractSlider)):
                target=target.parentWidget()
            if target and not isinstance(target,W.QScrollBar):
                area=self.scroll(target)
                if area:
                    bar=area.verticalScrollBar();delta=event.pixelDelta().y() or event.angleDelta().y()/120*bar.singleStep()*3
                    bar.setValue(bar.value()-round(delta));event.accept();return True
        return False
