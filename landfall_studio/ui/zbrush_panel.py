"""PySide6 Sculpt Studio widgets. All scene actions use sculpt.ops.run."""
import bpy
from ..sculpt import state, brushes, ops

_panels=[]
_headers=[]
_popups=[]
SCULPT_STYLE='''
QWidget { background:#1B1E22; color:#D8DCE2; font-size:11px; }
QGroupBox { border:1px solid #34383E; margin-top:7px; padding-top:12px; font-weight:bold; }
QGroupBox::title { color:#FF922B; subcontrol-origin:margin; left:8px; }
QPushButton,QToolButton { background:#292D33; border:1px solid #41464F; border-radius:3px; padding:4px; }
QPushButton:hover,QToolButton:hover { border-color:#FF922B; background:#383028; }
QPushButton:pressed,QToolButton:pressed { border-color:#FF922B; background:#66492E; }
QPushButton:checked,QToolButton:checked { background:#704014; border-color:#E87D0D; color:white; }
QSlider::groove:horizontal { height:5px; background:#383D45; }
QSlider::handle:horizontal { background:#FF922B; width:10px; margin:-4px 0; border-radius:3px; }
QSlider::sub-page:horizontal { background:#E87D0D; }
QComboBox,QSpinBox,QDoubleSpinBox { background:#22252A; border:1px solid #41464F; min-height:21px; }
QSpinBox,QDoubleSpinBox { padding:0px 3px; }
QSpinBox QLineEdit,QDoubleSpinBox QLineEdit { padding:0px; border:0; min-width:0; background:transparent; }
QTreeWidget,QListWidget { background:#191C20; border:1px solid #34383E; }
QTreeWidget::item:selected,QListWidget::item:selected { background:#704014; }
QScrollArea { border:0; }
QScrollBar:horizontal { height:8px; background:#22252A; }
QScrollBar::handle:horizontal { background:#565D66; min-width:25px; }
QLabel#GoZLink { color:#38A3D8; }
'''


def button(label, action=None, args=None, callback=None, checkable=False):
    from PySide6 import QtCore,QtWidgets
    b=QtWidgets.QPushButton(label)
    b.setObjectName('sculpt_'+(action or label))
    b.setCheckable(checkable); b.setFocusPolicy(QtCore.Qt.NoFocus)
    b.clicked.connect(lambda checked=False: callback(checked) if callback else command(action,**(args or {})))
    return b


def command(command_id,**kw):
    from .sculpt_widgets import context
    with bpy.context.temp_override(**context()):result=ops.run(command_id,**kw)
    refresh()
    from .hotkey_passthrough import _return_os_focus_to_blender
    _return_os_focus_to_blender()
    return result


def change(field,value):
    setattr(state.get(),field,value)
    refresh()

def pick_brush_color(secondary=False):
    from PySide6 import QtGui,QtWidgets
    b=state.brush()
    if b is None:return
    discard_closed_popups()
    dialog=QtWidgets.QColorDialog(QtGui.QColor.fromRgbF(*(b.secondary_color if secondary else b.color)))
    dialog.setObjectName('SculptColorPicker');dialog.setWindowTitle('Secondary Color' if secondary else 'Sculpt Color')
    dialog.setOption(QtWidgets.QColorDialog.DontUseNativeDialog,True)
    def selected(color):
        brush=state.brush()
        if brush and color.isValid():setattr(brush,'secondary_color' if secondary else 'color',(color.redF(),color.greenF(),color.blueF()))
    dialog.colorSelected.connect(selected);_popups.append(dialog);place_popup(dialog);return dialog


def path(obj):
    result=[]
    while obj:
        result.append(obj.name); obj=obj.parent
    return '|'+ '|'.join(reversed(result))


def make_spin(field,lo,hi,real=False,width=80):
    from PySide6 import QtWidgets
    # The inherited host theme can leave a NoButtons editor only one pixel
    # wide. Own its inset explicitly so values remain readable at every DPR.
    base=QtWidgets.QDoubleSpinBox if real else QtWidgets.QSpinBox
    class SculptSpin(base):
        def resizeEvent(self,event):
            super().resizeEvent(event)
            self.lineEdit().setGeometry(4,1,max(1,self.width()-8),max(1,self.height()-2))
    w=SculptSpin()
    w.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
    w.setObjectName('sculpt_'+field); w.setRange(lo,hi); w.setKeyboardTracking(False)
    w.setFixedWidth(width)
    # ZBrush shows Z Intensity and Focal Shift as whole numbers.
    if real: w.setDecimals(3 if field=='extract_thickness' else 0 if field in ('z_intensity','focal_shift') else 1); w.setSingleStep(0.01 if field=='extract_thickness' else 1)
    w.setValue(getattr(state.get(),field)); w.valueChanged.connect(lambda value:change(field,value))
    return w


class SculptPanel:
    def __init__(self):
        from .sculpt_tray import build
        build(self)
        _panels.append(self)
        self.refresh()

    def primitive_menu(self,insert=False):
        show_menu([('Sphere',lambda:command('INSERT' if insert else 'APPEND',primitive='SPHERE')),
                   ('Cube',lambda:command('INSERT' if insert else 'APPEND',primitive='CUBE')),
                   ('Cylinder',lambda:command('INSERT' if insert else 'APPEND',primitive='CYLINDER'))])

    def recovery_menu(self):
        entries=[(o.name,lambda name=o.name:command('RESTORE',name=name)) for o in bpy.context.scene.objects if o.get('_landfall_recovery')]
        return show_menu(entries or [('No geometry snapshots yet',lambda:None)])

    def stroke_menu(self): show_menu([(x.title(),lambda m=x:command('STROKE',method=m)) for x in ('SPACE','DOTS','DRAG_DOT','ANCHORED','AIRBRUSH')])
    def alpha_menu(self): show_menu([(label,lambda a=key:command('STROKE',alpha=a)) for label,key in [('Round','NONE'),('Square','SQUARE'),('Noise','NOISE')]])
    def matcap_menu(self): show_menu([(name,lambda n=name:command('MATCAP',name=n)) for name in ops.MATCAPS])

    def select_subtool(self,item,column):
        from PySide6 import QtCore
        name=item.data(0,QtCore.Qt.UserRole)
        if name!=getattr(bpy.context.view_layer.objects.active,'name',''): command('SUBTOOL',name=name)

    def visibility_changed(self,item,column):
        from PySide6 import QtCore
        obj=bpy.data.objects.get(item.data(0,QtCore.Qt.UserRole))
        if obj: obj.hide_set(item.checkState(0)!=QtCore.Qt.Checked)

    def layer_strength(self,value):
        o=bpy.context.view_layer.objects.active
        if o and o.active_shape_key and o.active_shape_key_index:
            command('LAYER',action='VALUE',name=o.active_shape_key.name,value=value/100)

    def refresh(self):
        from PySide6 import QtCore,QtWidgets
        s=state.get(); o=bpy.context.view_layer.objects.active
        self.brush_label.setText(s.active_zbrush_brush+'  ·  '+s.active_matcap)
        self.wells['Stroke'].setText('Stroke\n'+s.stroke_method.replace('_',' ').title())
        self.wells['Alpha'].setText('Alpha\n'+{'NONE':'Round','SQUARE':'Square','NOISE':'Noise'}[s.alpha])
        self.wells['MatCap'].setToolTip(s.active_matcap)
        for key,w in self.controls.items():
            if w.hasFocus(): continue
            guard=QtCore.QSignalBlocker(w)
            if isinstance(w,QtWidgets.QAbstractButton): w.setChecked(getattr(s,key))
            else: w.setValue(getattr(s,key))
            del guard
        self.dynamesh.setChecked(s.dynamesh_enabled)
        sig=tuple((x.name,path(x),x.hide_get(),x==o) for x in ops.meshes())
        if sig!=self._signature:
            guard=QtCore.QSignalBlocker(self.subtools); self.subtools.clear()
            for name,dag,hidden,selected in sig:
                item=QtWidgets.QTreeWidgetItem([name]); item.setToolTip(0,dag); item.setData(0,QtCore.Qt.UserRole,name)
                item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable); item.setCheckState(0,QtCore.Qt.Unchecked if hidden else QtCore.Qt.Checked)
                self.subtools.addTopLevelItem(item)
                if selected: self.subtools.setCurrentItem(item)
            self._signature=sig; del guard
        m=next((m for m in o.modifiers if m.type=='MULTIRES'),None) if o else None
        self.level_label.setText(f'SDiv {m.sculpt_levels if m else 0} / {m.total_levels if m else 0}')
        keys=o.data.shape_keys.key_blocks if o and o.type=='MESH' and o.data.shape_keys else []
        layer_sig=(o.name if o else '',tuple((k.name,k.value) for k in keys),o.active_shape_key_index if o else 0)
        if layer_sig!=self._layer_signature:
            self.layer_list.clear()
            for i,k in enumerate(keys):
                if i==0: continue
                self.layer_list.addItem(k.name)
                if i==o.active_shape_key_index: self.layer_list.setCurrentRow(i-1)
            guard=QtCore.QSignalBlocker(self.strength)
            self.strength.setValue(round(o.active_shape_key.value*100) if o and o.active_shape_key else 0)
            del guard; self._layer_signature=layer_sig
        self.buttons['REC'].setChecked(s.record_layer)
        from .sculpt_tray import refresh as refresh_tray
        refresh_tray(self)


class SculptHeader:
    def __init__(self):
        from PySide6 import QtCore,QtWidgets
        self.root=QtWidgets.QWidget(); self.root.setObjectName('ZBrushTopHeader'); self.root.setStyleSheet(SCULPT_STYLE)
        from .sculpt_input import polish
        polish(self.root)
        self.root.setFixedHeight(52)
        outer=QtWidgets.QVBoxLayout(self.root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        scroller=QtWidgets.QScrollArea(); scroller.setWidgetResizable(True); scroller.setFixedHeight(43)
        scroller.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff); scroller.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        content=QtWidgets.QWidget(); scroller.setWidget(content); row=QtWidgets.QHBoxLayout(content); row.setContentsMargins(4,2,4,2); row.setSpacing(3)
        self.buttons={}; self.fields={}
        ret=button('⇄ GoZ','RETURN');ret.setToolTip('Return to the previous Maya workspace');ret.setFixedWidth(55);ret.setStyleSheet('color:#38A3D8;border-color:#38A3D8;');row.addWidget(ret);self.buttons['Return']=ret
        self.bbrush=button('Bbrush ON',callback=lambda v:change('bbrush_enabled',v),checkable=True); row.addWidget(self.bbrush)
        for label,tool in [('Draw Q','DRAW'),('Move W','MOVE'),('Scale E','SCALE'),('Rotate R','ROTATE')]:
            b=button(label[-1],'TOOL',{'tool':tool},checkable=True);b.setToolTip(label);b.setFixedWidth(28);row.addWidget(b);self.buttons[tool]=b
        for label,value in [('ZAdd','ADD'),('ZSub','SUBTRACT')]:
            b=button(label,callback=lambda _,v=value:change('z_mode',v),checkable=True);b.setFixedWidth(44);row.addWidget(b);self.buttons[value]=b
        # RGB uses Blender's native sculpt color-paint brush and mesh color data.
        self.rgb=button('Rgb',callback=lambda v:self.rgb_mode(v),checkable=True); row.addWidget(self.rgb)
        self.material=button('M',callback=lambda v:self.material_mode(v),checkable=True)
        self.material.setToolTip('Paint active face material · right-click to choose material · enable Rgb to paint color with it')
        self.material.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.material.customContextMenuRequested.connect(lambda _:self.pick_material())
        row.addWidget(self.material)
        self.color_button=button('Color',callback=lambda _:self.pick_color()); row.addWidget(self.color_button)
        for label,key,lo,hi in [('Size','draw_size',1,500),('Int','z_intensity',0,100),('Focal','focal_shift',-100,100)]:
            row.addWidget(QtWidgets.QLabel(label));w=make_spin(key,lo,hi,key!='draw_size',58);row.addWidget(w);self.fields[key]=w
        self.lazy=button('Lazy L',callback=lambda v:change('lazy_mouse',v),checkable=True); row.addWidget(self.lazy)
        self.sculptris=button('SPro',callback=lambda v:command('SCULPTRIS_PRO',enable=v),checkable=True)
        self.sculptris.setToolTip('Sculptris Pro: add and remove triangles under the brush as you sculpt '
                                  '(Blender dynamic topology; detail follows the brush size)')
        row.addWidget(self.sculptris)
        for axis in 'XYZ':
            b=button(axis,'SYMMETRY',{'axis':axis},checkable=True); row.addWidget(b); self.buttons['sym'+axis]=b
        self.counts=QtWidgets.QLabel(); row.addWidget(self.counts)
        self.tiles={}
        self.bbrush.hide();self.rgb.hide();self.material.hide();self.color_button.hide();self.counts.hide()
        self.buttons['symY'].hide();self.buttons['symZ'].hide()
        more=button('⋯',callback=lambda _:self.overflow());more.setFixedWidth(28);row.addWidget(more)
        row.addStretch(1);outer.addWidget(scroller)
        self.root.resizeEvent=lambda e:self.responsive()
        _headers.append(self); self.refresh()

    def responsive(self):
        compact=self.root.width()<900
        self.lazy.setVisible(not compact);self.buttons['symX'].setVisible(not compact);self.sculptris.setVisible(not compact)

    def overflow(self):
        return show_menu([('Bbrush pen controls',lambda:self.bbrush.click()),('Rgb paint',lambda:self.rgb.click()),
            ('Material paint',lambda:self.material.click()),('Choose paint material…',self.pick_material),('Color…',self.pick_color),
            ('LazyMouse',lambda:self.lazy.click()),('Sculptris Pro',lambda:self.sculptris.click()),('X symmetry',lambda:command('SYMMETRY',axis='X')),
            ('Y symmetry',lambda:command('SYMMETRY',axis='Y')),('Z symmetry',lambda:command('SYMMETRY',axis='Z')),
            ('SelectRect',lambda:command('TOOL',tool='SELECT_RECT')),('Reset Current Brush',lambda:command('RESET_BRUSH')),
            ('Automatic tray layout',lambda:command('TRAY_AUTO')),
            ('Point count: '+self.counts.text(),lambda:None)])

    def rgb_mode(self,enabled):
        s=state.get(); s.rgb_enabled=enabled
        if enabled:
            with bpy.context.temp_override(**ops.view_context()):
                with bpy.data.libraries.load(str(brushes.catalog_path()),link=False,assets_only=True) as (src,dst): dst.brushes=['Paint Hard Pressure']
                b=dst.brushes[0].copy(); b.name='Landfall · RGB Paint'; b.asset_mark()
                bpy.ops.brush.asset_activate(asset_library_type='LOCAL',relative_asset_identifier='Brush/'+b.name)
                ops.dispatch('TOOL',tool='DRAW')
                state.apply_brush_settings()
                sp=bpy.context.space_data; sp.shading.type='SOLID'; sp.shading.light='STUDIO'; sp.shading.color_type='VERTEX'
        else:
            command('BRUSH',name=s.active_zbrush_brush)
            if s.mrgb_enabled:
                with bpy.context.temp_override(**ops.view_context()):
                    sp=bpy.context.space_data;sp.shading.light='STUDIO';sp.shading.color_type='MATERIAL'
            else:command('MATCAP',name=s.active_matcap)

    def material_mode(self,enabled):
        s=state.get();s.mrgb_enabled=enabled
        with bpy.context.temp_override(**ops.view_context()):
            sp=bpy.context.space_data
            if enabled:
                sp.shading.type='SOLID';sp.shading.light='STUDIO';sp.shading.color_type='VERTEX' if s.rgb_enabled else 'MATERIAL'
            elif not s.rgb_enabled:command('MATCAP',name=s.active_matcap)

    def pick_color(self):
        return pick_brush_color()

    def pick_material(self):
        return show_menu([('+ New material from brush color',lambda:command('PAINT_MATERIAL')),
            *[(m.name,lambda name=m.name:command('PAINT_MATERIAL',name=name)) for m in bpy.data.materials]])

    def refresh(self):
        from PySide6 import QtCore
        s=state.get(); o=bpy.context.view_layer.objects.active
        self.bbrush.setChecked(s.bbrush_enabled); self.bbrush.setText('Bbrush '+('ON' if s.bbrush_enabled else 'OFF'))
        self.lazy.setChecked(s.lazy_mouse); self.rgb.setChecked(s.rgb_enabled); self.material.setChecked(s.mrgb_enabled)
        self.sculptris.setChecked(bool(o and o.type=='MESH' and o.use_dynamic_topology_sculpting))
        for key,w in self.fields.items():
            if not w.hasFocus():
                guard=QtCore.QSignalBlocker(w); w.setValue(getattr(s,key)); del guard
        self.buttons['ADD'].setChecked(s.z_mode=='ADD'); self.buttons['SUBTRACT'].setChecked(s.z_mode=='SUBTRACT')
        for name,b in self.tiles.items(): b.setChecked(name==s.active_zbrush_brush)
        for axis in 'XYZ': self.buttons['sym'+axis].setChecked(bool(o and getattr(o,'use_mesh_mirror_'+axis.lower(),False)))
        window=ops.view_context()['window']
        tool=window.workspace.tools.from_space_view3d_mode('SCULPT',create=False)
        for key,value in [('DRAW','builtin.brush'),('MOVE','builtin.move'),('SCALE','builtin.scale'),('ROTATE','builtin.rotate')]:
            self.buttons[key].setChecked(bool(tool and (tool.idname==value or (key=='DRAW' and tool.idname.startswith('builtin_brush.')))))
        self.counts.setText(f'ActivePoints: {ops.point_count(o) if o and o.type=="MESH" else 0:,} | TotalPoints: {sum(ops.point_count(x,True) for x in ops.meshes()):,}')


def show_menu(entries):
    from PySide6 import QtGui,QtWidgets
    discard_closed_popups()
    menu=QtWidgets.QMenu(); menu.setObjectName('SculptPicker'); menu.setStyleSheet(SCULPT_STYLE)
    from .sculpt_input import polish
    polish(menu)
    for label,fn in entries: menu.addAction(label).triggered.connect(lambda _,f=fn:f())
    _popups.append(menu); menu.popup(QtGui.QCursor.pos())
    return menu


def show_imm_picker():
    """Choose the part the IMM brush drags onto the surface."""
    current=state.get().imm_part
    items=[(('● ' if p==current else '')+(p.title() if p in ops.IMM_PRIMITIVES else p.removeprefix('IMM ')),
            lambda name=p:command('IMM_PART',part=name)) for p in ops.imm_parts()]
    items.append(('Add Active SubTool as Part',lambda:command('IMM_PART',part='__ACTIVE__')))
    into=state.get().imm_into_subtool
    items.append((('● ' if not into else '')+'Insert as New SubTool',lambda:command('IMM_TARGET',into_subtool=False)))
    items.append((('● ' if into else '')+'Insert into Current SubTool (mask the rest)',lambda:command('IMM_TARGET',into_subtool=True)))
    return show_menu(items)


def show_brush_palette():
    from .sculpt_widgets import show_brush_palette as show
    return show()


def show_slider(field):
    from .sculpt_widgets import show_quick
    return show_quick(field=field)


def discard_closed_popups():
    for popup in list(_popups):
        try:
            if popup.isVisible():continue
            popup.deleteLater()
        except RuntimeError:pass
        _popups.remove(popup)


def place_popup(popup):
    from PySide6 import QtGui
    from .sculpt_input import polish
    polish(popup)
    from .desktop import _parent_floating_to_blender
    from blendertk.ui_utils.blender_window import BlenderWindow
    popup.adjustSize()
    popup.move(QtGui.QCursor.pos())
    _parent_floating_to_blender(popup)
    popup.show();popup.raise_();popup.setFocus()
    BlenderWindow.set_keyboard_focus(int(popup.winId()))
    popup._focus_armed=True


def refresh():
    from . import sculpt_widgets
    sculpt_widgets.refresh()
    for panel in _panels+_headers:
        try:
            if panel.root.isVisible(): panel.refresh()
        except RuntimeError: pass


def teardown():
    from . import sculpt_widgets
    sculpt_widgets.teardown()
    for popup in _popups:
        try: popup.close(); popup.deleteLater()
        except RuntimeError: pass
    _popups.clear(); _panels.clear(); _headers.clear()
