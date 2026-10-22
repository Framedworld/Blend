"""Shared sculpt controls, artwork, cursor popups and viewport provenance."""
import bpy
from ..sculpt import state,brushes,preferences,ops,gestures

_origin=None
_widgets=[]
_current_popup=None

def set_origin(context=None):
    global _origin
    live=ops.view_context(context)
    _origin=_context_ids(live)
    return live

def _context_ids(live):
    return tuple(live[key].as_pointer() for key in ('window','area','region'))

def _resolve_context(ids):
    """Resolve only through current owners; never dereference saved Window RNA."""
    if not ids:return None
    for window in bpy.context.window_manager.windows:
        if window.as_pointer()!=ids[0]:continue
        for area in window.screen.areas:
            if area.as_pointer()!=ids[1] or area.type!='VIEW_3D':continue
            region=next((r for r in area.regions if r.type=='WINDOW' and r.as_pointer()==ids[2]),None)
            if region:return dict(window=window,area=area,region=region)
    return None

def forget_origin():
    global _origin
    _origin=None

def context():
    live=_resolve_context(_origin)
    if live:return live
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type=='VIEW_3D' and a.as_pointer()==gestures.cursor['area']:
                return {'window':w,'area':a,'region':next(r for r in a.regions if r.type=='WINDOW')}
    return ops.view_context()

def command(action,**kw):
    from .zbrush_panel import command as run
    with bpy.context.temp_override(**context()):return run(action,**kw)

def brush_tile(code,callback=None):
    from PySide6 import QtCore,QtWidgets
    b=QtWidgets.QToolButton();b.setObjectName('sculpt_brush_'+code)
    b.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon);b.setIcon(brushes.icon(code));b.setIconSize(QtCore.QSize(66,48))
    b.setText(brushes.CATALOG[code][0]);b.setCheckable(True);b.setFocusPolicy(QtCore.Qt.NoFocus)
    badge=QtWidgets.QLabel(code,b);badge.setGeometry(4,2,24,14);badge.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
    badge.setStyleSheet('color:#FF922B;background:transparent;font-size:10px;')
    b.setToolTip(brushes.CATALOG[code][0]+' · B '+code[0]+' '+code[1]+'\n'+brushes.PURPOSE[code]+'\nRight-click to pin or reorder')
    b.clicked.connect(lambda:(callback(code) if callback else command('BRUSH',name=code)))
    b.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    def menu(_):
        from .zbrush_panel import show_menu
        values=preferences.get()['favorites'];pinned=code in values
        items=[('Unpin brush' if pinned else 'Pin to favorites',lambda:preferences.favorite(code))]
        if pinned:
            idx=values.index(code)
            if idx:items.append(('Move left',lambda:preferences.reorder(code,idx-1)))
            if idx<len(values)-1:items.append(('Move right',lambda:preferences.reorder(code,idx+1)))
        items.append(('Reset current brush',lambda:command('RESET_BRUSH')))
        show_menu(items)
    b.customContextMenuRequested.connect(menu)
    return b

class BrushShelf:
    def __init__(self):
        from PySide6 import QtCore,QtWidgets
        from .zbrush_panel import SCULPT_STYLE,button,_headers
        self.root=QtWidgets.QScrollArea();self.root.setObjectName('SculptBrushShelf');self.root.setStyleSheet(SCULPT_STYLE);self.root.setWidgetResizable(True)
        from .sculpt_input import polish
        polish(self.root)
        content=QtWidgets.QWidget();self.root.setWidget(content)
        lay=QtWidgets.QVBoxLayout(content);lay.setContentsMargins(5,5,5,5);lay.setSpacing(5)
        self.wells={}
        callbacks={'Brush':show_brush_palette,'Stroke':lambda:self.picker('stroke_menu'),'Alpha':lambda:self.picker('alpha_menu'),'Material':lambda:self.picker('matcap_menu')}
        for name in callbacks:
            b=QtWidgets.QToolButton();b.setObjectName('SculptWell_'+name);b.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            b.setFocusPolicy(QtCore.Qt.NoFocus);b.setIconSize(QtCore.QSize(76,54));b.setMinimumHeight(72 if name=='Brush' else 64)
            b.clicked.connect(callbacks[name]);lay.addWidget(b);self.wells[name]=b
        colors=QtWidgets.QHBoxLayout()
        self.color=button('',callback=lambda _:self.header().pick_color());self.color.setObjectName('SculptPrimaryColor');self.color.setToolTip('Primary sculpt color');self.color.setMinimumHeight(24)
        self.secondary=button('',callback=lambda _:self.pick_secondary());self.secondary.setObjectName('SculptSecondaryColor');self.secondary.setToolTip('Secondary sculpt color');self.secondary.setMinimumHeight(24)
        colors.addWidget(self.color);colors.addWidget(self.secondary);lay.addLayout(colors)
        self.mode=QtWidgets.QLabel();self.mode.setAlignment(QtCore.Qt.AlignCenter);lay.addWidget(self.mode)
        lay.addStretch(1)
        self.dag=button('⇄ Maya DAG',callback=lambda _:self.open_dag());self.dag.setStyleSheet('color:#38A3D8');lay.addWidget(self.dag)
        _widgets.append(self);self.refresh()
    def header(self):
        from .zbrush_panel import _headers
        return _headers[0]
    def picker(self,name):
        from .zbrush_panel import _panels
        return getattr(_panels[0],name)()
    def open_dag(self):
        from ..sculpt import layout
        layout.open_dag()
    def pick_secondary(self):
        from .zbrush_panel import pick_brush_color
        return pick_brush_color(secondary=True)
    def refresh(self):
        from PySide6 import QtCore,QtGui
        s=state.get();code=brushes.code_for(s.active_zbrush_brush)
        labels={'Brush':s.active_zbrush_brush+'\nB','Stroke':s.stroke_method.replace('_',' ').title(),'Alpha':{'NONE':'Round','SQUARE':'Square','NOISE':'Noise'}[s.alpha], 'Material':s.active_matcap}
        for name,b in self.wells.items():
            b.setText(labels[name]);b.setToolTip(name+' · '+labels[name])
            compact=self.root.height()<500
            b.setIconSize(QtCore.QSize(64 if compact else 76,40 if compact else 54))
            b.setIcon(brushes.icon(code if name=='Brush' else {'Stroke':'SH','Alpha':'MP','Material':'IN'}[name]))
        self.wells['Brush'].setText(s.active_zbrush_brush.replace('ClayBuildup','Clay\nBuildup').replace('DamStandard','Dam\nStandard').replace(' Topological','\nTopological').replace('SnakeHook','Snake\nHook')+'\nB')
        self.wells['Brush'].setToolTip(s.active_zbrush_brush+' · B\n'+brushes.PURPOSE[code])
        # Wells are visual previews of the current stroke, alpha and material.
        self.wells['Stroke'].setIcon(stroke_icon(s.stroke_method))
        self.wells['Alpha'].setIcon(alpha_icon(s.alpha))
        self.wells['Material'].setIcon(material_icon(s.active_matcap))
        held=gestures.cursor
        label='Visibility · held' if held['ctrl'] and held['shift'] else ('Mask · held' if held['ctrl'] else ('Smooth · held' if held['shift'] else ('ZSub' if s.z_mode=='SUBTRACT' else 'ZAdd')))
        self.mode.setText(label)
        b=state.brush()
        if b:
            for widget,color in ((self.color,b.color),(self.secondary,b.secondary_color)):
                value=QtGui.QColor.fromRgbF(*color).name();widget.setStyleSheet('background:'+value+';color:'+('#111' if sum(color)>1.5 else '#eee'))

def _svg_icon(svg):
    from PySide6 import QtCore,QtGui,QtSvg
    pix=QtGui.QPixmap(76,54);pix.fill(QtCore.Qt.transparent)
    p=QtGui.QPainter(pix);QtSvg.QSvgRenderer(svg.encode()).render(p);p.end();return QtGui.QIcon(pix)

def stroke_icon(method):
    extra='stroke-dasharray="1 7"' if method=='DOTS' else ('stroke-dasharray="3 5"' if method=='SPACE' else '')
    return _svg_icon('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 76 54"><path d="M8 38 Q22 3 40 28 T68 16" fill="none" stroke="#ecb98c" stroke-width="6" stroke-linecap="round" '+extra+'/></svg>')

def alpha_icon(alpha):
    shape='<rect x="18" y="7" width="40" height="40" fill="#e3d3bf"/>' if alpha=='SQUARE' else ('<path d="M13 15 L24 8 L33 23 L44 7 L58 18 L64 38 L48 44 L35 34 L17 46Z" fill="#b5a18c"/>' if alpha=='NOISE' else '<circle cx="38" cy="27" r="22" fill="url(#a)"/>')
    return _svg_icon('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 76 54"><defs><radialGradient id="a"><stop stop-color="#f2e5d6"/><stop offset="1" stop-color="#292d33"/></radialGradient></defs>'+shape+'</svg>')

def material_icon(name):
    rgb=ops.MATCAPS.get(name,ops.MATCAPS['Grey Clay'])[1];c='#'+''.join(f'{int(x*255):02x}' for x in rgb)
    return _svg_icon('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 76 54"><defs><radialGradient id="m" cx="36%" cy="30%"><stop stop-color="#f2d6bc"/><stop offset=".48" stop-color="'+c+'"/><stop offset="1" stop-color="#16181c"/></radialGradient></defs><circle cx="38" cy="27" r="24" fill="url(#m)"/></svg>')

class Favorites:
    def __init__(self):
        from PySide6 import QtWidgets
        from .zbrush_panel import SCULPT_STYLE
        self.root=QtWidgets.QScrollArea();self.root.setObjectName('SculptFavorites');self.root.setStyleSheet(SCULPT_STYLE);self.root.setWidgetResizable(True)
        from .sculpt_input import polish
        polish(self.root)
        content=QtWidgets.QWidget();self.root.setWidget(content)
        self.row=QtWidgets.QHBoxLayout(content);self.row.setContentsMargins(5,2,5,2);self.row.setSpacing(3)
        self.signature=None;self.tiles={};self.recents=[];_widgets.append(self);self.refresh()
    def refresh(self):
        from PySide6 import QtCore,QtWidgets
        from .zbrush_panel import button
        s=state.get();codes=preferences.get()['favorites'];recent=[c for c in preferences.recent if c not in codes];sig=(tuple(codes),tuple(recent))
        if sig!=self.signature:
            if self.signature is None or sig[0]!=self.signature[0]:
                while self.row.count():
                    item=self.row.takeAt(0)
                    if item.widget():item.widget().deleteLater()
                self.tiles={}
                for code in codes:
                    b=brush_tile(code);b.setMinimumWidth(43);self.row.addWidget(b);self.tiles[code]=b
                browse=button('Brushes\nB',callback=lambda _:show_brush_palette());browse.setMinimumHeight(48);self.row.addWidget(browse);self.row.addStretch(1)
            else:
                for b in self.recents:self.row.removeWidget(b);b.deleteLater()
            self.recents=[]
            for code in recent:
                b=brush_tile(code);b.setToolTip('Recent · '+b.toolTip());self.row.insertWidget(self.row.count()-1,b);self.recents.append(b)
            self.signature=sig
        compact=self.root.width()<900
        for code,b in self.tiles.items():
            b.setChecked(brushes.CATALOG[code][0]==s.active_zbrush_brush);b.setIconSize(QtCore.QSize(46 if compact else 66,36 if compact else 48))
            b.setMaximumWidth(66 if compact else 88)
        for b in self.recents:
            b.setVisible(not compact);b.setChecked(b.objectName()=='sculpt_brush_'+brushes.code_for(s.active_zbrush_brush))

def refresh():
    for obj in list(_widgets):
        try:obj.refresh()
        except RuntimeError:_widgets.remove(obj)

def close_popup(cancel=False):
    global _current_popup
    popup=_current_popup;_current_popup=None
    try:
        if popup is not None and popup.isVisible():popup.finish(cancel)
    except RuntimeError:pass

def popup_base(name,momentary=False):
    from PySide6 import QtCore,QtWidgets
    from .zbrush_panel import SCULPT_STYLE,_popups,discard_closed_popups
    global _current_popup
    close_popup();discard_closed_popups()
    class Popup(QtWidgets.QFrame):
        def __init__(self):
            super().__init__(None,QtCore.Qt.Popup)
            self.setObjectName(name);self.setStyleSheet(SCULPT_STYLE);self._context_ids=_context_ids(context())
            from .sculpt_input import polish
            polish(self)
            self.saved={key:getattr(state.get(),key) for key in (*brushes.FIELDS,'draw_size')}
            self.saved_object=bpy.context.view_layer.objects.active
            self.saved_symmetry=[getattr(self.saved_object,'use_mesh_mirror_'+axis,False) for axis in 'xyz']
            self.finished=False;self.momentary=momentary
            QtWidgets.QApplication.instance().installEventFilter(self)
        @property
        def context_override(self):
            live=_resolve_context(self._context_ids)
            if live is None:raise RuntimeError('The originating sculpt viewport was closed')
            return live
        def finish(self,cancel=False):
            if self.finished:return
            self.finished=True
            if cancel and _resolve_context(self._context_ids):
                with bpy.context.temp_override(**self.context_override):
                    s=state.get();state.hydrating=True
                    try:
                        for key,value in self.saved.items():setattr(s,key,value)
                    finally:state.hydrating=False
                    state.apply_brush_settings();brushes.set_stroke(method=s.stroke_method,alpha=s.alpha)
                    try:
                        for axis,value in zip('xyz',self.saved_symmetry):setattr(self.saved_object,'use_mesh_mirror_'+axis,value)
                    except (ReferenceError,AttributeError):pass
            self.close()
        def eventFilter(self,obj,event):
            if self.finished:return False
            if event.type()==QtCore.QEvent.KeyPress and event.key()==QtCore.Qt.Key_Escape:
                self.finish(True);return True
            if event.type()==QtCore.QEvent.KeyRelease and event.key()==QtCore.Qt.Key_Space and self.momentary:
                self.finish();return True
            if event.type()==QtCore.QEvent.ApplicationDeactivate or (event.type()==QtCore.QEvent.WindowDeactivate and obj is self and getattr(self,'_focus_armed',False)):
                self.finish(True)
            return False
        def changeEvent(self,event):
            if event.type()==QtCore.QEvent.WindowDeactivate and getattr(self,'_focus_armed',False) and not self.finished:self.finish(True)
            super().changeEvent(event)
        def hideEvent(self,event):
            global _current_popup
            if _current_popup is self:_current_popup=None
            self.finished=True;QtWidgets.QApplication.instance().removeEventFilter(self)
            from blendertk.ui_utils.blender_window import BlenderWindow
            live=_resolve_context(self._context_ids)
            if live:BlenderWindow.set_keyboard_focus(BlenderWindow.window_hwnd(live['window']))
            super().hideEvent(event)
        def keyPressEvent(self,event):
            if hasattr(self,'on_key'):self.on_key(event)
            else:super().keyPressEvent(event)
        def mousePressEvent(self,event):
            # Qt clears this flag on each new mouse event. Set it for the
            # dismissal press itself so it cannot replay into the canvas.
            self.setAttribute(QtCore.Qt.WA_NoMouseReplay,True)
            super().mousePressEvent(event)
    popup=Popup();_current_popup=popup;_popups.append(popup)
    return popup

def show_brush_palette():
    from PySide6 import QtCore,QtWidgets
    from .zbrush_panel import place_popup
    popup=popup_base('ZBrushBrushPalette');popup.prefix=''
    lay=QtWidgets.QVBoxLayout(popup);popup.title=QtWidgets.QLabel('B › Choose two brush letters');lay.addWidget(popup.title)
    search=QtWidgets.QLineEdit();search.setObjectName('SculptBrushSearch');search.setPlaceholderText('Search brushes…');lay.addWidget(search)
    grid=QtWidgets.QGridLayout();lay.addLayout(grid);popup.buttons={}
    def choose(code):
        popup.finish()
        with bpy.context.temp_override(**popup.context_override):command('BRUSH',name=code)
    for i,code in enumerate(brushes.CATALOG):
        b=brush_tile(code,choose);b.setFixedSize(116,82);b.setChecked(brushes.CATALOG[code][0]==state.get().active_zbrush_brush)
        popup.buttons[code]=b;grid.addWidget(b,i//5,i%5)
    def filtered():
        text=search.text().lower()
        for code,b in popup.buttons.items():b.setEnabled((not popup.prefix or code.startswith(popup.prefix)) and (not text or text in brushes.CATALOG[code][0].lower()))
        popup.title.setText('B › '+popup.prefix+' › second letter' if popup.prefix else 'B › Choose two brush letters')
    search.textChanged.connect(lambda _:filtered())
    def key(event):
        k=event.text().upper()
        if event.key()==QtCore.Qt.Key_Backspace:popup.prefix=''
        elif popup.prefix and popup.prefix+k in brushes.CATALOG:choose(popup.prefix+k);return
        elif len(k)==1 and any(c.startswith(k) for c in brushes.CATALOG):popup.prefix=k
        filtered();event.accept()
    popup.on_key=key;place_popup(popup);popup.setFocus();return popup

def show_quick(momentary=False,field=None):
    from PySide6 import QtCore,QtWidgets
    from .sculpt_input import slider as tip_slider
    from .zbrush_panel import place_popup,button,change
    popup=popup_base('ZBrushCursorSlider' if field else 'SculptQuickMenu',momentary)
    lay=QtWidgets.QVBoxLayout(popup);lay.addWidget(QtWidgets.QLabel(state.get().active_zbrush_brush))
    popup.sliders={}
    for key,label,lo,hi in [('draw_size','Draw Size',1,500),('z_intensity','ZIntensity',0,100),('focal_shift','Focal Shift',-100,100)]:
        if field and key!=field:continue
        row=QtWidgets.QHBoxLayout();text=QtWidgets.QLabel(label);value=QtWidgets.QLabel(str(round(getattr(state.get(),key))));row.addWidget(text);row.addStretch(1);row.addWidget(value);lay.addLayout(row)
        slider=tip_slider();slider.setObjectName('SculptCursorSlider_'+key);slider.setFixedWidth(280);slider.setRange(lo,hi);slider.setValue(round(getattr(state.get(),key)))
        def update(v,k=key,w=value):
            with bpy.context.temp_override(**popup.context_override):change(k,v)
            w.setText(str(v))
        slider.valueChanged.connect(update);lay.addWidget(slider);popup.sliders[key]=slider
    if not field:
        row=QtWidgets.QHBoxLayout()
        popup.toggles={}
        def sync_toggles():
            s=state.get();o=bpy.context.view_layer.objects.active
            for label,value in [('ZAdd',s.z_mode=='ADD'),('ZSub',s.z_mode=='SUBTRACT'),('Sym X',bool(o and o.use_mesh_mirror_x)),('Lazy',s.lazy_mouse)]:popup.toggles[label].setChecked(value)
        for label,fn in [('ZAdd',lambda:change('z_mode','ADD')),('ZSub',lambda:change('z_mode','SUBTRACT')),('Sym X',lambda:command('SYMMETRY')),('Lazy',lambda:change('lazy_mouse',not state.get().lazy_mouse))]:
            def update_toggle(_,f=fn):
                with bpy.context.temp_override(**popup.context_override):f();sync_toggles()
            b=button(label,callback=update_toggle,checkable=True);popup.toggles[label]=b;row.addWidget(b)
        sync_toggles()
        lay.addLayout(row);favorites=QtWidgets.QHBoxLayout()
        for code in preferences.get()['favorites'][:4]:
            def choose(c):popup.finish();command('BRUSH',name=c)
            b=brush_tile(code,choose);b.setFixedWidth(67);favorites.addWidget(b)
        lay.addLayout(favorites)
    place_popup(popup);popup.setFocus();return popup

def teardown():
    global _origin,_current_popup
    close_popup();_origin=None;_current_popup=None;_widgets.clear()
