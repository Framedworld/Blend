"""Sculpt presentation through the existing desktop dock owners."""
import bpy

active=False
focus=False
_saved=[]
_owners={}
_left=None
_favorites=None
_dag=None
_drawer=None
_drawer_open=False
_tray_override=None
_drawer_collapsed=False
_pending={}
_resize_timer=None
resize_events=[]
_window_extent=None
_focus_timer=None
_focus_target=None


def _cancel_focus_request():
    global _focus_timer,_focus_target
    if _focus_timer and bpy.app.timers.is_registered(_focus_timer):bpy.app.timers.unregister(_focus_timer)
    _focus_timer=_focus_target=None


def request_focus():
    """Leave native area event iteration before replacing a fullscreen screen."""
    global _focus_timer,_focus_target
    if not active:return {'ok':False,'error':'Sculpt desktop is not docked'}
    _focus_target=not (_focus_target if _focus_timer else focus)
    if _focus_timer is None:
        def apply():
            global _focus_timer,_focus_target
            if _focus_timer is not apply:return None
            target=_focus_target;_focus_timer=_focus_target=None
            if active and target!=focus:toggle_focus()
            return None
        _focus_timer=apply
        bpy.app.timers.register(apply,first_interval=.01)
    return {'ok':True,'focus':_focus_target,'pending':True}


def abandon_after_load():
    """Drop presentation snapshots without touching areas freed by a file load."""
    global active,focus,_saved,_owners,_left,_favorites,_drawer,_dag,_drawer_collapsed,_pending,_resize_timer,_window_extent
    from ..ui import sculpt_widgets,main_menu
    _cancel_focus_request()
    sculpt_widgets.close_popup()
    for owner in _owners.values():
        dock=owner._inner_dock
        dock._stop_glue();dock._release_widget()
        dock._window=dock._area=dock._hwnd=None;dock._widget=None;dock._last_rect=None
    if _dag:
        try:_dag.close()
        except RuntimeError:pass
    for controller in (_left,_favorites):
        if controller:
            controller.root.hide();controller.root.deleteLater()
            if controller in sculpt_widgets._widgets:sculpt_widgets._widgets.remove(controller)
    if _drawer:
        _drawer.hide();_drawer.deleteLater()
    if _resize_timer and bpy.app.timers.is_registered(_resize_timer):bpy.app.timers.unregister(_resize_timer)
    for bar in main_menu._bar_instances:bar.set_sculpt_mode(False)
    active=focus=_drawer_collapsed=False;_saved=[];_owners={};_pending={}
    _left=_favorites=_drawer=_dag=_resize_timer=_window_extent=None

def _defer_size(window,area,width,height,edge):
    global _resize_timer
    _pending[(window.as_pointer(),area.as_pointer())]=(window,area,width,height,edge,0)
    if _resize_timer is None or not bpy.app.timers.is_registered(_resize_timer):
        _resize_timer=_apply_pending;bpy.app.timers.register(_resize_timer,first_interval=.05)


def _clear_hover(window):
    # Area-edge polling reads Screen.active_region, which a context override
    # cannot clear. Native screen exit resets it. A same-callback maximize /
    # restore uses public RNA, keeps the original areas and never warps the pen.
    area=next((a for a in window.screen.areas if a.type=='VIEW_3D'),None)
    if area is None or len(window.screen.areas)==1:return
    overlays=[(a,{k:getattr(a.spaces.active.overlay,k) for k in ('show_floor','show_ortho_grid','show_axis_x','show_axis_y','show_axis_z')}) for a in window.screen.areas if a.type=='VIEW_3D']
    grid=getattr(window.scene,'landfall_grid_finite',None)
    with bpy.context.temp_override(window=window,area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
        bpy.ops.screen.screen_full_area(use_hide_panels=False)
    from . import gestures
    from . import _trackers
    gestures.tracker_generation+=1;_trackers.clear()
    area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
    with bpy.context.temp_override(window=window,area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
        bpy.ops.screen.screen_full_area(use_hide_panels=False)

    if grid is not None:window.scene.landfall_grid_finite=grid
    for saved_area,values in overlays:
        for key,value in values.items():setattr(saved_area.spaces.active.overlay,key,value)


def _apply_pending():
    global _resize_timer
    if focus or _focus_timer is not None:return .1
    from PySide6 import QtWidgets,QtCore
    from blendertk.ui_utils.qt_dock import QtDock
    from ..commands import scene_edits
    if QtDock._interaction_in_flight() or scene_edits._gestures:return .1
    if QtWidgets.QApplication.activePopupWidget() is not None or QtWidgets.QApplication.mouseButtons()!=QtCore.Qt.NoButton:return .1
    import ctypes
    if any(ctypes.windll.user32.GetAsyncKeyState(vk)&0x8000 for vk in (1,2,4)):return .1
    windows={w.as_pointer():w for w in bpy.context.window_manager.windows}
    for key in list(_pending):
        window=windows.get(key[0])
        if window is None or not any(a.as_pointer()==key[1] for a in window.screen.areas):_pending.pop(key,None)
    windows={key[0]:windows[key[0]] for key in _pending}
    for window in windows.values():
        with bpy.context.temp_override(window=window,region=None):
            if not bpy.ops.screen.area_move.poll():_clear_hover(window)
    for key,record in list(_pending.items()):
        window,area,width,height,edge,tries=record
        try:
            window=windows.get(key[0])
            area=next((a for a in window.screen.areas if a.as_pointer()==key[1]),None) if window else None
            if area is None:
                _pending.pop(key,None);continue
            done=_size(window,area,width,height,edge,defer=False)
            # An operator can trigger a newer request; never erase or replace it
            # with the old retry's result or attempt count.
            if _pending.get(key) is not record:continue
            if done:_pending.pop(key,None)
            elif tries<20:_pending[key]=(window,area,width,height,edge,tries+1)
            else:print('[Sculpt layout] Cannot restore pane dimensions');_pending.pop(key,None)
        except (ReferenceError,TypeError):_pending.pop(key,None)
    if _pending:return .05
    _resize_timer=None;return None

def _swap(owner,widget):
    dock=owner._inner_dock
    dock._stop_glue();dock._release_widget()
    if not dock._embed(widget,dock._hwnd):raise RuntimeError('Cannot embed Sculpt shelf')
    dock._last_rect=None
    if hasattr(owner,'_position_over_full_area'):owner._position_over_full_area()
    else:dock._position(dock.content_region())
    if hasattr(owner,'_start_sync_timer'):owner._start_sync_timer()
    else:dock._start_glue()

def _size(window,area,width=None,height=None,edge='LEFT',defer=True):
    if not area:return
    try:
        window=next((w for w in bpy.context.window_manager.windows if w==window),None)
        if window is None:return False
        area=next((a for a in window.screen.areas if a==area),None)
        if area is None:return False
        # A new sizing intent supersedes an older deferred one even when it
        # succeeds immediately. Otherwise a queued Sculpt resize can run after
        # GoZ has restored the saved Maya dimensions and shrink them again.
        if defer:_pending.pop((window.as_pointer(),area.as_pointer()),None)
        if width is not None:
            delta=(width-area.width) if edge=='RIGHT' else (area.width-width)
            x=area.x+area.width if edge=='RIGHT' else area.x
            y=area.y+area.height//2
        else:
            delta=(area.height-height) if edge=='BOTTOM' else (height-area.height)
            x=area.x+area.width//2;y=area.y if edge=='BOTTOM' else area.y+area.height
        if abs(delta)>2:
            # Native area-edge operators require main-window context, no region.
            with bpy.context.temp_override(window=window,screen=window.screen,area=area,region=None):
                if not bpy.ops.screen.area_move.poll():
                    if defer:_defer_size(window,area,width,height,edge)
                    return False
                result=bpy.ops.screen.area_move(x=int(x),y=int(y),delta=int(delta))
                resize_events.append((area.type,int(x),int(y),int(delta),str(result),width,height))
                if 'FINISHED' not in result:
                    if defer:_defer_size(window,area,width,height,edge)
                    return False
                # A successful native edge move can be clamped by an adjacent
                # pane or await the next layout pass. Keep the same intent
                # queued until live geometry reaches it, rather than caching
                # that intermediate width as the user's chosen size.
                actual = area.width if width is not None else area.height
                target = width if width is not None else height
                if abs(actual-target)>2:
                    if defer:_defer_size(window,area,width,height,edge)
                    return False
        return True
    except (ReferenceError,TypeError):return False

def engage():
    global active,_left,_favorites,_saved,_owners,_drawer_open,_tray_override,_window_extent
    if bpy.app.background or active:return
    from ..ui import desktop,outliner,time_slider,main_menu,sculpt_widgets
    left=outliner.get_left_outliner_dock();bottom=time_slider.get_bottom_time_slider_dock();top=desktop._get_top_shelf_dock();right=desktop._right_dock
    if not all(x and x._inner_dock._area for x in (left,bottom,top,right)):return
    _owners={'left':left,'bottom':bottom,'top':top,'right':right}
    _saved=[(name,x._inner_dock._window,x._inner_dock._area,x._inner_dock._area.width,x._inner_dock._area.height,x._inner_dock._widget) for name,x in _owners.items()]
    _left=sculpt_widgets.BrushShelf();_favorites=sculpt_widgets.Favorites();active=True;_drawer_open=False
    from . import preferences
    _tray_override=preferences.get().get('tray_collapsed')
    _swap(left,_left.root);_swap(bottom,_favorites.root)
    dpr=_left.root.devicePixelRatioF();win=top._inner_dock._window
    _window_extent=(win.width,win.height)
    _size(win,left._inner_dock._area,width=round(104*dpr),edge='RIGHT')
    _size(win,top._inner_dock._area,height=round(54*dpr),edge='BOTTOM')
    _size(win,bottom._inner_dock._area,height=round(84*dpr),edge='TOP')
    _size(win,right._inner_dock._area,width=round(320*dpr),edge='LEFT')
    for bar in main_menu._bar_instances:bar.set_sculpt_mode(True)
    sync()

def sync():
    global _drawer,_drawer_collapsed,_window_extent
    if not active or bpy.app.background:return
    from ..ui import sculpt_widgets
    sculpt_widgets.refresh()
    if focus:
        for owner in _owners.values():
            if owner._inner_dock._widget:owner._inner_dock._widget.hide()
        return
    left=_owners['left'];win=left._inner_dock._window
    extent=(win.width,win.height);resized=extent!=_window_extent;_window_extent=extent
    narrow=win.width/max(1,_left.root.devicePixelRatioF())<1100
    collapse=narrow if _tray_override is None else _tray_override
    right=_owners['right'];dock=right._inner_dock
    if collapse!=_drawer_collapsed:
        if collapse:
            from PySide6 import QtWidgets
            from ..ui.zbrush_panel import button,SCULPT_STYLE
            if _drawer is None:
                _drawer=QtWidgets.QFrame();_drawer.setStyleSheet(SCULPT_STYLE)
                from ..ui.sculpt_input import polish
                polish(_drawer)
                lay=QtWidgets.QVBoxLayout(_drawer);lay.setContentsMargins(0,4,0,4)
                b=button('‹',callback=lambda _:toggle_tray());b.setToolTip('Open Sculpt tool tray');lay.addWidget(b);lay.addStretch(1)
            _swap(right,_drawer);_size(win,dock._area,width=round(36*_left.root.devicePixelRatioF()),edge='LEFT')
        else:
            _swap(right,next(x[5] for x in _saved if x[0]=='right'))
            _size(win,dock._area,width=round(320*_left.root.devicePixelRatioF()),edge='LEFT')
        _drawer_collapsed=collapse
    if resized:
        # Blender scales editor fractions with the host window. Restore the
        # intended logical shelf/tray sizes after a window resize, otherwise
        # the tool tray can shrink to 126 px despite ample canvas space.
        dpr=_left.root.devicePixelRatioF()
        _size(win,left._inner_dock._area,width=round(104*dpr),edge='RIGHT')
        _size(win,_owners['top']._inner_dock._area,height=round(54*dpr),edge='BOTTOM')
        _size(win,_owners['bottom']._inner_dock._area,height=round(84*dpr),edge='TOP')
        _size(win,dock._area,width=round((36 if collapse else 320)*dpr),edge='LEFT')

def toggle_tray():
    global _tray_override
    from . import preferences
    _tray_override=not _drawer_collapsed;preferences.get()['tray_collapsed']=_tray_override;preferences.save()
    sync();return {'ok':True,'open':not _drawer_collapsed}

def auto_tray():
    global _tray_override
    from . import preferences
    _tray_override=None;preferences.get()['tray_collapsed']=None;preferences.save();sync();return {'ok':True}

def toggle_focus():
    global focus
    _cancel_focus_request()
    if not active:return {'ok':False,'error':'Sculpt desktop is not docked'}
    from ..ui import sculpt_widgets,main_menu
    sculpt_widgets.close_popup()
    from . import ops
    ctx=sculpt_widgets.context()
    if not focus:
        for owner in _owners.values():
            owner._inner_dock._stop_glue();owner._inner_dock._stop_focus_follow()
            if hasattr(owner,'_stop_sync_timer'):owner._stop_sync_timer()
            if owner._inner_dock._widget:owner._inner_dock._widget.hide()
        focus=True
        with bpy.context.temp_override(**ctx):bpy.ops.screen.screen_full_area(use_hide_panels=False)
    else:
        with bpy.context.temp_override(**ops.view_context()):bpy.ops.screen.screen_full_area(use_hide_panels=False)
        focus=False
        for owner in _owners.values():
            dock=owner._inner_dock;dock._last_rect=None
            if dock._widget:dock._widget.show()
            if hasattr(owner,'_start_sync_timer'):owner._start_sync_timer();owner._position_over_full_area()
            else:dock._position(dock.content_region());dock._start_glue()
            dock._start_focus_follow()
        main_menu.get_main_menu_dock().enforce_dock_geometry()
    sync();return {'ok':True,'focus':focus}

def open_dag():
    global _dag
    from PySide6 import QtWidgets
    from ..ui.zbrush_panel import place_popup,_popups
    try:
        if _dag and _dag.isVisible():_dag.raise_();return
    except RuntimeError:_dag=None
    original=next((x[5] for x in _saved if x[0]=='left'),None)
    if original is None:return
    class Dag(QtWidgets.QDialog):
        def closeEvent(self,event):
            original.setParent(None);original.hide();super().closeEvent(event)
    _dag=Dag();_dag.setObjectName('SculptDag');_dag.setWindowTitle('Maya DAG · same scene')
    lay=QtWidgets.QVBoxLayout(_dag);lay.setContentsMargins(0,0,0,0);lay.addWidget(original);original.show();_dag.resize(360,600)
    _popups.append(_dag);place_popup(_dag)

def disengage():
    global active,focus,_saved,_owners,_left,_favorites,_drawer_collapsed
    _cancel_focus_request()
    if not active:return
    if focus:toggle_focus()
    from ..ui import main_menu,sculpt_widgets
    sculpt_widgets.close_popup()
    try:
        if _dag:_dag.close()
    except RuntimeError:pass
    for name,win,area,width,height,widget in _saved:
        try:
            if name in ('left','bottom') or (name=='right' and _drawer_collapsed):_swap(_owners[name],widget)
            if name in ('left','right'):_size(win,area,width=width,edge='RIGHT' if name=='left' else 'LEFT')
            else:_size(win,area,height=height,edge='BOTTOM' if name=='top' else 'TOP')
        except ReferenceError:pass
    for bar in main_menu._bar_instances:bar.set_sculpt_mode(False)
    for obj in (_left,_favorites):
        if obj:
            obj.root.hide();obj.root.deleteLater()
            if obj in sculpt_widgets._widgets:sculpt_widgets._widgets.remove(obj)
    active=False;focus=False;_saved=[];_owners={};_left=_favorites=None;_drawer_collapsed=False
