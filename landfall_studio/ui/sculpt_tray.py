"""Compact reference-led PySide6 Tool tray; uses the one sculpt dispatcher."""
import bpy
from . import zbrush_panel as zp
from ..sculpt import ops,state,preferences,extended,instances

TRAY_STYLE='''
QScrollArea#ZBrushStudioPanel { background:#292C30; border:0; }
QWidget#SculptReferenceContent { background:#292C30; }
QWidget#SculptPaletteBody { background:#303236; }
QGroupBox { background:#303236; border:1px solid #1D2023; border-radius:7px; margin-top:7px; padding-top:14px; font-weight:normal; }
QGroupBox::title { subcontrol-origin:margin; left:9px; padding:0 4px; color:#D8DCE2; }
QGroupBox::indicator { width:9px; height:9px; }
QPushButton,QToolButton { background:#3B3E42; color:#CDD0D4; border:1px solid #25282B; border-radius:3px; padding:2px 4px; min-height:21px; font-size:12px; }
QPushButton:checked,QToolButton:checked { background:#E78B20; color:#191C20; border-color:#9E6021; }
QPushButton:hover,QToolButton:hover { border-color:#B37430; background:#49453E; }
QPushButton:pressed,QToolButton:pressed { border-color:#E78B20; background:#66492E; }
QPushButton:disabled { color:#72767B; background:#34363A; border-color:#2B2D30; }
QLabel { background:transparent; color:#C9CDD2; font-size:12px; }
QFrame#SculptEmbeddedValue { background:transparent; border:0; }
QSlider::groove:horizontal { height:3px; background:#44474C; }
QSlider::sub-page:horizontal { background:#95612F; }
QSlider::handle:horizontal { width:15px; margin:-2px 0; border-radius:3px; background:#C48C4C; }
QSlider:disabled::handle:horizontal { background:#62666B; }
QTreeWidget,QListWidget { background:#292B2E; border:1px solid #26282B; border-radius:3px; }
QTreeWidget::item,QListWidget::item { min-height:31px; }
QTreeWidget::item:selected,QListWidget::item:selected { background:#454039; border:1px solid #A16B32; color:#EEE4D6; }
QScrollBar:vertical { width:8px; background:#292B2E; }
QScrollBar::handle:vertical { background:#94642E; min-height:30px; border-radius:3px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox { background:#34373B; color:#CCD0D6; border:1px solid #25282B; min-height:22px; padding:1px 4px; }
'''

def build(panel):
    from PySide6 import QtCore,QtGui,QtWidgets
    from .sculpt_input import polish,slider as tip_slider
    class ValueSpin(QtWidgets.QDoubleSpinBox):
        def resizeEvent(self,event):
            super().resizeEvent(event)
            self.lineEdit().setGeometry(2,0,max(1,self.width()-4),self.height())
    panel.root=QtWidgets.QScrollArea();panel.root.setObjectName('ZBrushStudioPanel');panel.root.setWidgetResizable(True)
    polish(panel.root)
    panel.root.setToolTip('Tap controls to use them. Drag vertically on buttons or empty tray space to scroll. Sliders keep their own drag; Ctrl+wheel adjusts a value.')
    panel.root.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    panel.root.setStyleSheet(zp.SCULPT_STYLE+TRAY_STYLE)
    panel.content=QtWidgets.QWidget();panel.content.setObjectName('SculptReferenceContent');panel.root.setWidget(panel.content)
    panel.content.setMinimumWidth(0)
    layout=QtWidgets.QVBoxLayout(panel.content);layout.setContentsMargins(5,3,5,8);layout.setSpacing(3)
    panel.controls={};panel.buttons={};panel.palettes={};panel.feature_widgets={};panel.option_widgets=[];panel._signature=None;panel._layer_signature=None
    panel.wells={name:QtWidgets.QPushButton(panel.content) for name in ('Stroke','Alpha','MatCap')}
    for w in panel.wells.values():w.hide()
    panel.brush_label=QtWidgets.QLabel(panel.content);panel.brush_label.hide()
    panel._extra_refresh=[];panel._dialogs=[];panel._mesh_icons={}

    def palette(title,pinned=False):
        group=QtWidgets.QGroupBox(title);group.setCheckable(not pinned)
        group.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Fixed)
        box=QtWidgets.QVBoxLayout(group);box.setContentsMargins(5,5,5,5);box.setSpacing(3)
        body=QtWidgets.QWidget();body.setObjectName('SculptPaletteBody');inner=QtWidgets.QVBoxLayout(body);inner.setContentsMargins(0,0,0,0);inner.setSpacing(2);box.addWidget(body)
        layout.addWidget(group);panel.palettes[title]=group
        data=preferences.get();checked=pinned or title==data['palette'] or title in data['pinned_palettes']
        group.setChecked(checked);body.setVisible(checked)
        group.setMaximumHeight(16777215 if checked else 26)
        def toggle(value):
            body.setVisible(value)
            group.setMaximumHeight(16777215 if value else 26)
            if not value:return
            shift=bool(QtWidgets.QApplication.keyboardModifiers()&QtCore.Qt.ShiftModifier)
            if not shift:
                for name,g in panel.palettes.items():
                    if g is not group and g.isCheckable():g.setChecked(False)
            saved=preferences.get();saved['palette']=title;saved['pinned_palettes']=[name for name,g in panel.palettes.items() if g is not group and g.isCheckable() and g.isChecked()] if shift else [];preferences.save()
        group.toggled.connect(toggle)
        return inner

    def nested(parent,title):
        group=QtWidgets.QGroupBox(title);group.setCheckable(True);group.setChecked(False)
        group.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Fixed)
        box=QtWidgets.QVBoxLayout(group);box.setContentsMargins(3,4,3,3);box.setSpacing(2)
        body=QtWidgets.QWidget();body.setObjectName('SculptPaletteBody');inner=QtWidgets.QVBoxLayout(body);inner.setContentsMargins(0,0,0,0);inner.setSpacing(2);box.addWidget(body);body.hide()
        group.setMaximumHeight(26)
        def toggle(value):
            body.setVisible(value);group.setMaximumHeight(16777215 if value else 26)
        group.toggled.connect(toggle);parent.addWidget(group);return inner

    def invoke(section,kind,**kw):return zp.command('PALETTE',section=section,kind=kind,**kw)

    def act(parent,label,section=None,kind=None,args=None,callback=None,hint='',disabled='',aliases=()):
        fn=callback or (lambda:invoke(section,kind,**(args or {})))
        button=zp.button(label,callback=lambda _:fn());button.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Fixed)
        button.setFixedHeight(26)
        button.setMinimumWidth(0);button.setToolTip(disabled or hint)
        if disabled:button.setEnabled(False)
        parent.addWidget(button);panel.buttons[label]=button
        for alias in aliases:panel.buttons[alias]=button
        panel.feature_widgets[(section,kind,label)]=button
        return button

    def pair(parent,entries):
        if any(len(entry[0])>22 for entry in entries):
            for label,section,kind,*rest in entries:act(parent,label,section,kind,**(rest[0] if rest else {}))
            return parent
        row=QtWidgets.QHBoxLayout();row.setSpacing(2);parent.addLayout(row)
        for entry in entries:
            label,section,kind,*rest=entry;act(row,label,section,kind,**(rest[0] if rest else {}))
        return row

    def basic(parent,label,action,args=None,aliases=()):return act(parent,label,callback=lambda:zp.command(action,**(args or {})),aliases=aliases)

    def option_value(parent,label,section,key,lo,hi,default=0,integer=False,action=None):
        frame=QtWidgets.QFrame();frame.setObjectName('SculptEmbeddedValue');frame.setFixedHeight(44);box=QtWidgets.QVBoxLayout(frame);box.setContentsMargins(2,0,2,0);box.setSpacing(0)
        top=QtWidgets.QHBoxLayout();top.setContentsMargins(0,0,0,0);name=QtWidgets.QLabel(label);value=ValueSpin()
        value.setDecimals(0 if integer else 2);value.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons);value.setRange(lo,hi);value.setFixedWidth(52);value.setKeyboardTracking(False)
        top.addWidget(name,1);top.addWidget(value);box.addLayout(top)
        slider=tip_slider();slider.setRange(int(lo*100),int(hi*100));box.addWidget(slider);parent.addWidget(frame)
        slider.setSingleStep(100 if integer else 1);slider.setPageStep(100 if integer else 10)
        slider.setObjectName('SculptOption_'+section+'_'+key);value.setObjectName('SculptValue_'+section+'_'+key)
        dirty=[False]
        def commit(v):
            v=int(round(v)) if integer else float(v)
            dirty[0]=False
            if action:
                action(v)
                if section in ('DEFORM_ACTION','MORPH_ACTION'):
                    guard=QtCore.QSignalBlocker(slider);slider.setValue(0);del guard
                    guard=QtCore.QSignalBlocker(value);value.setValue(0);del guard
            else:zp.command('PALETTE_OPTION',section=section,key=key,value=v)
        def display(v):
            guard=QtCore.QSignalBlocker(value);value.setValue(v);del guard
        slider.valueChanged.connect(lambda v:display(v/100))
        slider.sliderReleased.connect(lambda:commit(slider.value()/100))
        slider.actionTriggered.connect(lambda _:QtCore.QTimer.singleShot(0,lambda:commit(slider.value()/100)) if not slider.isSliderDown() else None)
        value.valueChanged.connect(lambda _:dirty.__setitem__(0,True))
        value.editingFinished.connect(lambda:commit(value.value()) if dirty[0] else None)
        panel.option_widgets.append((section,key,slider,value))
        return slider,value

    def toggle(parent,label,section,key,default=False):
        b=act(parent,label,callback=lambda:zp.command('PALETTE_OPTION',section=section,key=key,value=not bool((instances.config(section) if section in ('ArrayMesh','NanoMesh') else extended.settings(section)).get(key,default))))
        b.setCheckable(True);panel.option_widgets.append((section,key,b,None));return b

    def text(parent,label,section,key,choices):
        row=QtWidgets.QHBoxLayout();row.addWidget(QtWidgets.QLabel(label));combo=QtWidgets.QComboBox();combo.addItems(choices);combo.setMinimumWidth(0);row.addWidget(combo,1);parent.addLayout(row)
        combo.currentTextChanged.connect(lambda v:zp.command('PALETTE_OPTION',section=section,key=key,value=v));panel.option_widgets.append((section,key,combo,None));return combo

    def name_dialog(title,section,kind,current=''):
        d=polish(QtWidgets.QInputDialog());d.setInputMode(QtWidgets.QInputDialog.TextInput);d.setWindowTitle(title);d.setLabelText(title);d.setTextValue(current)
        d.textValueSelected.connect(lambda name:invoke(section,kind,name=name));panel._dialogs.append(d);zp.place_popup(d)

    def file_dialog(title,section,kind,extension,save=False):
        d=polish(QtWidgets.QFileDialog());d.setWindowTitle(title);d.setNameFilter(extension);d.setOption(QtWidgets.QFileDialog.DontUseNativeDialog,True)
        d.setFileMode(QtWidgets.QFileDialog.AnyFile if save else QtWidgets.QFileDialog.ExistingFile)
        if save:d.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        d.fileSelected.connect(lambda path:invoke(section,kind,path=path));panel._dialogs.append(d);zp.place_popup(d)

    def target_action(section,kind,**kw):
        choices=[o for o in ops.meshes() if o!=ops.active()]
        zp.show_menu([(o.name,lambda name=o.name:invoke(section,kind,target=name,**kw)) for o in choices] or [('Append a source SubTool first',lambda:None)])

    sub=palette('SubTool',True)
    option_value(sub,'Visible Count','SubTool','visible_count',2,12,4,integer=True)
    row=QtWidgets.QHBoxLayout();row.setSpacing(1);sub.addLayout(row);panel.visibility_sets=[]
    for index in range(1,9):
        b=act(row,'V'+str(index),'SubTool','VISIBILITY_SET',callback=lambda i=index:invoke('SubTool','VISIBILITY_SET',index=i,store=bool(QtWidgets.QApplication.keyboardModifiers()&QtCore.Qt.ShiftModifier)),hint='Click to recall; Shift-click to store this visibility set. Empty sets store on first click.')
        b.setCheckable(True);panel.visibility_sets.append(b)
    panel.subtools=QtWidgets.QTreeWidget();panel.subtools.setObjectName('SculptSubTools');panel.subtools.setHeaderHidden(True);panel.subtools.setRootIsDecorated(False);panel.subtools.setIconSize(QtCore.QSize(45,40));panel.subtools.setIndentation(0)
    panel.subtools.itemClicked.connect(panel.select_subtool);panel.subtools.itemChanged.connect(panel.visibility_changed);sub.addWidget(panel.subtools)
    pair(sub,[('List All',None,None,{'callback':lambda:zp.show_menu([(o.name,lambda n=o.name:zp.command('SUBTOOL',name=n)) for o in ops.meshes()])}),('↑','SubTool','UP'),('↓','SubTool','DOWN')])
    pair(sub,[('New Folder',None,None,{'callback':lambda:name_dialog('New Folder','SubTool','FOLDER')}),('↱','SubTool','MOVE_UP'),('↳','SubTool','MOVE_DOWN')])
    pair(sub,[('Rename',None,None,{'callback':lambda:name_dialog('Rename SubTool','SubTool','RENAME',ops.active().name)}),('AutoReorder','SubTool','AUTO_REORDER')])
    pair(sub,[('All Low','SubTool','ALL_LOW'),('All High','SubTool','ALL_HIGH')])
    pair(sub,[('All To Home','SubTool','HOME'),('All To Target','SubTool','TARGET')])
    pair(sub,[('Copy','SubTool','COPY'),('Paste','SubTool','PASTE')])
    pair(sub,[('Duplicate',None,None,{'callback':lambda:zp.command('DUPLICATE')}),('Append',None,None,{'callback':lambda:panel.primitive_menu(False)})])
    pair(sub,[('Delete',None,None,{'callback':lambda:zp.command('DELETE')}),('Insert',None,None,{'callback':lambda:panel.primitive_menu(True),'hint':'Insert Mesh joins primitive geometry into the active mesh; protected layers require Append.'})])
    pair(sub,[('Del Other','SubTool','DELETE_OTHER'),('Del All','SubTool','DELETE_ALL')])
    split=nested(sub,'Split')
    pair(split,[('Split Masked',None,None,{'callback':lambda:zp.command('SPLIT_MASKED')}),('Split Hidden','Topology','SPLIT_HIDDEN')])
    pair(split,[('Groups Split','Topology','SPLIT_GROUPS'),('Split Parts','Topology','SPLIT_PARTS')])
    merge=nested(sub,'Merge');pair(merge,[('Merge Down',None,None,{'callback':lambda:zp.command('MERGE_DOWN')}),('Merge Visible',None,None,{'callback':lambda:zp.command('MERGE_VISIBLE')})])
    boolean=nested(sub,'Boolean')
    for name,operation in [('Union','UNION'),('Subtract','DIFFERENCE'),('Intersect','INTERSECT')]:act(boolean,name,callback=lambda op=operation:target_action('Topology','BOOLEAN',operation=op),hint='Live native Boolean; source operand remains editable. Make Mesh creates a sculptable result.')
    act(boolean,'Make Boolean Mesh',callback=lambda:extended_make('Boolean'))
    project=nested(sub,'Project');act(project,'Project All',callback=lambda:target_action('Topology','PROJECT'),hint='Nearest-surface Shrinkwrap to a chosen source; source detail is preserved.')
    extract=nested(sub,'Extract');option_value(extract,'Thickness','EXTRACT','extract_thickness',.0001,1,.02,action=lambda v:zp.change('extract_thickness',v));basic(extract,'Extract','EXTRACT')

    geo=palette('Geometry');panel.level_label=QtWidgets.QLabel();geo.addWidget(panel.level_label)
    pair(geo,[('Lower Res',None,None,{'callback':lambda:zp.command('LOWER')}),('Higher Res',None,None,{'callback':lambda:zp.command('HIGHER')})])
    option_value(geo,'SDiv','SDIV','level',0,6,integer=True,action=lambda v:invoke('Geometry','LEVEL',value=v))
    pair(geo,[('Cage','Geometry','CAGE'),('Rstr','Geometry','RESTRICT')])
    pair(geo,[('Del Lower',None,None,{'callback':lambda:zp.command('DELETE_LOWER')}),('Del Higher',None,None,{'callback':lambda:zp.command('DELETE_HIGHER')})])
    act(geo,'Freeze SubDivision Levels','Geometry','FREEZE',hint='Freeze stores a recovery snapshot and lowers the base. Unfreeze rebuilds levels and adds a detail-projection modifier; inspect and Make Mesh to commit.')
    pair(geo,[('Reconstruct Subdiv','Geometry','RECONSTRUCT'),('Rebuild Subdiv','Geometry','REBUILD')])
    act(geo,'Convert BPR To Geo',disabled='BPR/FiberMesh render primitives belong to ZBrush. Use ArrayMesh or NanoMesh Make Mesh for native Blender instances.')
    r=QtWidgets.QHBoxLayout();geo.addLayout(r);basic(r,'Divide','DIVIDE');toggle(r,'Smt','Geometry','smooth',True);toggle(r,'Suv','Geometry','smooth_uv',True)
    act(geo,'ReUV',disabled='ZBrush ReUV has no matching Multires subdivision switch. Existing UV maps are retained; unwrap the base in the native UV Editor.')
    dynamic=nested(geo,'Dynamic Subdiv');toggle(dynamic,'Dynamic','Geometry','dynamic');option_value(dynamic,'Smooth Subdiv','Geometry','dynamic_levels',0,6,2,True);act(dynamic,'Apply Dynamic Subdiv','Geometry','APPLY_DYNAMIC')
    edge=nested(geo,'EdgeLoop');act(edge,'EdgeLoop','Topology','EDGE_LOOP',hint='Subdivide an open boundary using BMesh. Requires an open border.');act(edge,'Group Loops','Topology','GROUP_LOOPS',hint='Native BMesh bevel around Face Set boundaries.')
    crease=nested(geo,'Crease');option_value(crease,'Crease Level','Geometry','crease',0,1,1);pair(crease,[('Crease PG','Geometry','CREASE'),('Uncrease All','Geometry','UNCREASE')])
    clay=nested(geo,'ClayPolish');act(clay,'ClayPolish','Geometry','CLAY_POLISH',hint='Adapted boundary-aware smoothing on the base mesh. Inspect the result; this uses a different algorithm from ZBrush ClayPolish.')
    dyna=nested(geo,'DynaMesh');panel.dynamesh=zp.button('DynaMesh',callback=lambda v:zp.change('dynamesh_enabled',v),checkable=True);dyna.addWidget(panel.dynamesh)
    option_value(dyna,'Resolution','DYNAMESH','resolution',16,512,128,True,lambda v:zp.change('dynamesh_resolution',v));basic(dyna,'Re-DynaMesh','DYNAMESH')
    remesh=nested(geo,'ZRemesher');option_value(remesh,'Target Polygons','ZREMESHER','target',100,200000,5000,True,lambda v:zp.change('zremesher_target_polys',v));basic(remesh,'ZRemesher','ZREMESHER');
    for label,field in [('Keep Groups','keep_groups'),('Adaptive','adaptive')]:
        b=zp.button(label,callback=lambda v,f=field:zp.change(f,v),checkable=True);remesh.addWidget(b);panel.controls[field]=b
    topo=nested(geo,'Modify Topology')
    pair(topo,[('Del Hidden','Topology','DELETE_HIDDEN'),('WeldPoints','Topology','WELD')]);pair(topo,[('Triangulate','Topology','TRIANGULATE'),('To Quads','Topology','QUADS')]);pair(topo,[('Unweld Groups','Topology','UNWELD'),('Flip','Topology','FLIP')]);basic(topo,'Close Holes','CLOSE_HOLES')
    stager=nested(geo,'Stager');pair(stager,[('Store Home','SubTool','STORE_HOME'),('Store Target','SubTool','STORE_TARGET')]);pair(stager,[('Home','SubTool','HOME'),('Target','SubTool','TARGET')])

    array=palette('ArrayMesh')
    def preset(section,save=False):file_dialog('Save Preset' if save else 'Open Preset',section,'SAVE' if save else 'OPEN','JSON preset (*.json)',save)
    act(array,'Lightbox ▸ Array Presets',callback=lambda:preset('ArrayMesh'))
    pair(array,[('Open',None,None,{'callback':lambda:preset('ArrayMesh')}),('Save',None,None,{'callback':lambda:preset('ArrayMesh',True)})])
    toggle(array,'Array Mesh','ArrayMesh','enabled');act(array,'Transpose',callback=lambda:array_transform_dialog(panel),hint='Edit native object-offset transform in a floating inspector.')
    pair(array,[('SwitchXY','ArrayMesh','SWITCH_XY'),('SwitchXZ','ArrayMesh','SWITCH_XZ'),('SwitchYZ','ArrayMesh','SWITCH_YZ')])
    option_value(array,'Transform Stage','ArrayMesh','stage',0,15,0,True,lambda v:invoke('ArrayMesh','STAGE',value=v))
    pair(array,[('Append New','ArrayMesh','APPEND'),('Insert New','ArrayMesh','INSERT')]);pair(array,[('Reset','ArrayMesh','RESET'),('Delete','ArrayMesh','DELETE')]);pair(array,[('Copy','ArrayMesh','COPY'),('Paste','ArrayMesh','PASTE')])
    option_value(array,'Repeat','ArrayMesh','count',1,128,3,True)
    option_value(array,'Smooth','ArrayMesh','smooth',0,1,0)
    panel.content.findChild(QtWidgets.QSlider,'SculptOption_ArrayMesh_smooth').setToolTip('Native surface smoothing on the array result. Inter-stage path interpolation is unavailable.')
    pattern=nested(array,'Pattern')
    option_value(pattern,'PatternStart','ArrayMesh','pattern_start',0,128,0,True)
    option_value(pattern,'PatternOn','ArrayMesh','pattern_on',1,128,1,True)
    option_value(pattern,'PatternOff','ArrayMesh','pattern_off',0,128,0,True)
    act(pattern,'AlignToPath',callback=lambda:zp.show_menu([(o.name,lambda n=o.name:invoke('ArrayMesh','ALIGN_PATH',target=n)) for o in bpy.context.scene.objects if o.type=='CURVE'] or [('Add a native Curve first',lambda:None)]),hint='Native Curve modifier on the repeated surface.')
    transform=nested(array,'Offset / Scale / Rotate / Pivot')
    for prefix,values in [('Offset',(-10,10,0)),('Scale',(.01,5,1)),('Rotate',(-180,180,0)),('Pivot',(-10,10,0))]:
        section=nested(transform,prefix)
        for axis in 'XYZ':option_value(section,axis+' Amount','ArrayMesh',prefix.lower()+'_'+axis.lower(),values[0],values[1],values[2])
    r=QtWidgets.QHBoxLayout();array.addLayout(r)
    for axis in 'XYZ':toggle(r,axis+' Mirror','ArrayMesh','mirror_'+axis.lower())
    act(array,'Convert To NanoMesh','ArrayMesh','TO_NANO',hint='Create a source SubTool from the array base and instance it on the current faces.')
    r=QtWidgets.QHBoxLayout();array.addLayout(r);act(r,'Make Mesh','ArrayMesh','MAKE_MESH');toggle(r,'Extrude / Weld','ArrayMesh','extrude')
    panel.buttons['Extrude / Weld'].setToolTip('Merge coincident neighboring vertices using the native Array modifier. Arbitrary cap bridging is not performed.')

    nano=palette('NanoMesh');panel.nano_source=text(nano,'Source','NanoMesh','source',[]);panel.nano_source.setPlaceholderText('Choose source…')
    toggle(nano,'NanoMesh On','NanoMesh','enabled')
    toggle(nano,'Hide Others','NanoMesh','hide_others')
    option_value(nano,'Index','NanoMesh','index',0,31,0,True,lambda v:invoke('NanoMesh','INDEX',value=v))
    pair(nano,[('≪','NanoMesh','PREVIOUS'),('≫','NanoMesh','NEXT')]);pair(nano,[('Copy','NanoMesh','COPY'),('Paste','NanoMesh','PASTE')]);pair(nano,[('Edit Mesh','NanoMesh','EDIT_MESH'),('Edit Placement','NanoMesh','EDIT_PLACEMENT')])
    pair(nano,[('Split Screen','NanoMesh','SPLIT_SCREEN'),('Return Placement','NanoMesh','RETURN_PLACEMENT')])
    toggle(nano,'Show Instances','NanoMesh','show_instances',True);toggle(nano,'Show Placement','NanoMesh','show_placement',True);toggle(nano,'Freeze Placement','NanoMesh','freeze')
    text(nano,'Fit','NanoMesh','fit',['PROP','FIT','FILL','CONST'])
    option_value(nano,'Size','NanoMesh','size',.001,3,.15)
    for label,key,var in [('Width','width','w_var'),('Length','length','l_var'),('Height','height','h_var'),('XOffset','offset_x','x_var'),('YOffset','offset_y','y_var'),('ZOffset','offset_z','z_var'),('XRotation','rotate_x','rx_var'),('YRotation','rotate_y','ry_var'),('ZRotation','rotate_z','rz_var')]:
        row=QtWidgets.QHBoxLayout();nano.addLayout(row)
        a=QtWidgets.QVBoxLayout();b=QtWidgets.QVBoxLayout();row.addLayout(a,1);row.addLayout(b,1)
        rotate='Rotation' in label;offset='Offset' in label
        option_value(a,label,'NanoMesh',key,-180 if rotate else (-2 if offset else .01),180 if rotate else 5,0 if rotate or offset else 1)
        option_value(b,label[0]+'Var','NanoMesh',var,0,180 if rotate else 1,0)
    r=QtWidgets.QHBoxLayout();nano.addLayout(r);toggle(r,'Flip H','NanoMesh','flip_h');toggle(r,'Flip V','NanoMesh','flip_v')
    option_value(nano,'H Tile','NanoMesh','tile_h',1,10,1,True);option_value(nano,'V Tile','NanoMesh','tile_v',1,10,1,True)
    text(nano,'Pattern','NanoMesh','pattern',['GRID','DIAMOND']);option_value(nano,'Random Distribution','NanoMesh','random_distribution',0,1,0);option_value(nano,'Random Seed','NanoMesh','seed',0,10000,0,True);act(nano,'RandArray','NanoMesh','RANDOM_SEED')
    alignment=nested(nano,'Alignment');text(alignment,'Align to','NanoMesh','alignment',['NORMAL','EDGE','NONE'])
    color=nested(nano,'Colorize');act(color,'Source Color / UV',disabled='Instances retain the source mesh colors, materials and UVs. Per-index ZBrush MRGB and base-face texture projection are not implemented.')
    inventory=nested(nano,'Inventory');pair(inventory,[('Add Index','NanoMesh','ADD_INDEX'),('Delete','NanoMesh','DELETE')]);pair(inventory,[('One to Mesh','NanoMesh','ONE_TO_MESH'),('All to Mesh','NanoMesh','MAKE_MESH')]);act(inventory,'Clip',disabled='Per-face clipping of overlapping Nano geometry is not implemented. Fit scales the source to its placement face without cropping it.')

    layers=palette('Layers');panel.palettes['Layers  ⇄ Maya BlendShapes']=panel.palettes['Layers']
    panel.layer_list=QtWidgets.QListWidget();panel.layer_list.setObjectName('SculptLayers');panel.layer_list.setMaximumHeight(180);panel.layer_list.itemClicked.connect(lambda item:zp.command('LAYER',action='SELECT',name=item.text()));layers.addWidget(panel.layer_list)
    panel.strength=tip_slider();panel.strength.setTracking(False);panel.strength.setObjectName('SculptLayerStrength');panel.strength.setRange(-100,100);panel.strength.valueChanged.connect(panel.layer_strength);layers.addWidget(panel.strength)
    pair(layers,[('↑','Layers','UP'),('↓','Layers','DOWN'),('Merge Down','Layers','MERGE_DOWN'),('Invert','Layers','INVERT')])
    pair(layers,[('+', 'Layers','NEW',{'aliases':('+ New Layer',)}),('Name',None,None,{'callback':lambda:name_dialog('Layer Name','Layers','RENAME',ops.active().active_shape_key.name if ops.active().active_shape_key else '')}),('Duplicate','Layers','DUPLICATE'),('Delete','Layers','DELETE')])
    pair(layers,[('Split XYZ','Layers','SPLIT'),('Bake Current',None,None,{'callback':lambda:zp.command('LAYER',action='BAKE'),'aliases':('Bake to Base',)})])
    act(layers,'Bake All','Layers','BAKE_ALL');record=basic(layers,'REC','LAYER',{'action':'RECORD'});record.setCheckable(True);record.setToolTip('Record shape displacement at base resolution. Colors and masks remain shared mesh attributes, not independent layer channels.')
    act(layers,'Import MDD',callback=lambda:file_dialog('Import MDD','Layers','IMPORT_MDD','MDD point cache (*.mdd)'))
    option_value(layers,'MDD Speed','Layers','mdd_speed',.01,10,1)
    act(layers,'Record Deformation Animation',callback=lambda:file_dialog('Export Scene Deformation','Layers','EXPORT_MDD','MDD point cache (*.mdd)',True),hint='Export evaluated fixed-topology deformation over the current scene range to MDD.')
    basic(layers,'⇄ GoZ to Shape Editor','LAYER',{'action':'GOZ'})

    deform=palette('Deformation');axes=QtWidgets.QHBoxLayout();deform.addLayout(axes);axes.addWidget(QtWidgets.QLabel('Axes'),1)
    for axis in 'XYZ':
        b=zp.button(axis,callback=lambda _,a=axis:zp.command('PALETTE_OPTION',section='Deformation',key='axes',value=''.join(x for x in 'XYZ' if (x in extended.settings('Deformation')['axes'])!=(x==a))))
        b.setCheckable(True);axes.addWidget(b);panel._extra_refresh.append(lambda w=b,a=axis:w.setChecked(a in extended.settings('Deformation')['axes']))
    for label,kind in [('Unify','UNIFY'),('Mirror','MIRROR'),('Smart ReSym','SMART_RESYM'),('ReSym','RESYM')]:act(deform,label,'Deformation',kind,{'amount':1},hint='Local-space base vertices, respecting the selected axes and sculpt mask.')
    for label,kind in [('Polish','POLISH'),('Polish By Features','POLISH_FEATURES'),('Polish By Groups','POLISH_GROUPS'),('Polish Crisp Edges','CRISP'),('Relax','RELAX'),('Relax Plane Grid','RELAX_PLANE'),('Morph to Grid','MORPH_GRID'),('Offset','OFFSET'),('Rotate','ROTATE'),('Size','SIZE'),('Bend','BEND'),('SBend','SBEND'),('Skew','SKEW'),('SSkew','SSKEW'),('RFlatten','RFLATTEN'),('Flatten','FLATTEN'),('SFlatten','SFLATTEN'),('Twist','TWIST'),('Taper','TAPER'),('Squeeze','SQUEEZE'),('Noise','NOISE'),('Smooth','SMOOTH'),('Contrast','CONTRAST'),('Inflate','INFLATE'),('Inflate Balloon','BALLOON'),('Spherize','SPHERIZE'),('Gravity','GRAVITY'),('Perspective','PERSPECTIVE')]:
        slider,value=option_value(deform,label,'DEFORM_ACTION',kind,-1,1,0,action=lambda v,k=kind:invoke('Deformation',k,amount=v))
        slider.setToolTip('Release to apply to unmasked vertices. Returns to zero after applying. Ctrl+Z undoes the whole action.')
    pair(deform,[('Repeat To Active','Deformation','REPEAT_ACTIVE'),('Repeat To Other','Deformation','REPEAT_OTHER')]);act(deform,'Repeat To Folder','Deformation','REPEAT_FOLDER');toggle(deform,'Mask','Deformation','respect_mask',True)

    masking=palette('Masking')
    pair(masking,[('ViewMask','Masking','VIEW'),('Inverse',None,None,{'callback':lambda:zp.command('MASK',kind='INVERT'),'aliases':('Invert',)})])
    for entries in [[('Clear','CLEAR'),('MaskAll','ALL')],[('BlurMask','SMOOTH'),('SharpenMask','SHARPEN')],[('GrowMask','GROW'),('ShrinkMask','SHRINK')],[('BoostMask','CONTRAST_INCREASE'),('DiluteMask','CONTRAST_DECREASE')]]:
        pair(masking,[(label,None,None,{'callback':lambda k=kind:zp.command('MASK',kind=k),'aliases':('Mask All',) if kind=='ALL' else ()}) for label,kind in entries])
    act(masking,'Mask Changed Points','Masking','CHANGED',hint='Mask distance from StoreMT at the same base topology.')
    pair(masking,[('Flip By Poseable Symmetry','Masking','FLIP_SYMMETRY',{'hint':'Uses StoreMT rest-position correspondence when available, otherwise spatial matching. Automatic posed-topology inference is unavailable.'}),('Mirror By Poseable Symmetry','Masking','MIRROR_SYMMETRY',{'hint':'Uses StoreMT rest-position correspondence when available, otherwise spatial matching. Automatic posed-topology inference is unavailable.'})])
    act(masking,'Create Alpha','Masking','CREATE_ALPHA',hint='Pack a 256 px XY-projected mask image into the blend file.')
    features=nested(masking,'MaskByFeature')
    for label,key in [('Border','feature_border'),('Groups','feature_groups'),('Crease','feature_crease')]:toggle(features,label,'Masking',key,True)
    act(features,'MaskByFeature','Masking','FEATURE')
    draft=nested(masking,'MaskByDraft');option_value(draft,'Draft Angle','Masking','angle',0,180,45);text(draft,'Direction','Masking','axis',['X','Y','Z']);toggle(draft,'InvDir','Masking','invert_direction');act(draft,'SetDir from View',callback=lambda:set_direction('Masking'));act(draft,'MaskByDraft','Masking','DRAFT')
    act(masking,'Go To Unmasked Center','Masking','CENTER')
    adjust=nested(masking,'Mask Adjust');option_value(adjust,'Amount','Masking','mask_adjust',0,1,.5);act(adjust,'Apply','Masking','ADJUST')
    for title,kind in [('Mask By Fibers','FIBERS'),('Mask By AO','AO'),('Mask By Cavity','CAVITY'),('Mask By Depth','DEPTH'),('Mask By Normals','NORMALS'),('Mask By Smoothness','SMOOTHNESS'),('Mask PeaksAndValleys','PEAKS_VALLEYS'),('Mask By Color','COLOR'),('Mask By Alpha','ALPHA')]:
        inner=nested(masking,title)
        if kind=='AO':option_value(inner,'Scan Distance','Masking','ao_distance',.01,10,1);option_value(inner,'Samples','Masking','ao_samples',1,32,8,True)
        if kind in ('COLOR','CHANGED','SMOOTHNESS'):option_value(inner,'Tolerance','Masking','threshold',.001,1,.5)
        if kind in ('FIBERS','DEPTH','NORMALS'):text(inner,'Axis','Masking','axis',['X','Y','Z'])
        act(inner,title,'Masking',kind,hint='Root-to-tip gradient on disconnected converted hair meshes.' if kind=='FIBERS' else '')

    pg=palette('PolyGroups')
    pair(pg,[('Auto Groups','PolyGroups','AUTO'),('UV Groups','PolyGroups','UV')]);act(pg,'Auto Groups With UV','PolyGroups','AUTO_UV')
    act(pg,'Merge Similar Groups','PolyGroups','MERGE_SIMILAR');act(pg,'Merge Stray Groups','PolyGroups','MERGE_STRAY')
    act(pg,'Regroup By Edges','PolyGroups','EDGES');option_value(pg,'Edge Sensitivity','PolyGroups','edge_sensitivity',0,1,.5)
    act(pg,'Groups By Normals','PolyGroups','NORMALS');option_value(pg,'Max Angle','PolyGroups','angle',0,180,45)
    pair(pg,[('GroupVisible','PolyGroups','VISIBLE'),('ReGroupVisible','PolyGroups','REGROUP_VISIBLE')]);act(pg,'Group Front','PolyGroups','FRONT')
    basic(pg,'Group Masked','GROUP',{'mode':'MASKED'});act(pg,'Group Masked Clear Mask','PolyGroups','MASKED_CLEAR');act(pg,'Group As DynaMesh Sub',disabled='Blender voxel remesh does not interpret signed Face Sets as subtraction volumes. Use SubTool Boolean Subtract, then Make Boolean Mesh.')
    pair(pg,[('From Polypaint','PolyGroups','PAINT'),('From Masking','PolyGroups','MASKING')]);option_value(pg,'Paint Tolerance','PolyGroups','tolerance',.001,1,.1);option_value(pg,'Mask Tolerance','PolyGroups','mask_tolerance',0,1,.5)
    basic(pg,'Polyframe','POLYFRAME');pair(pg,[('ShowPt',None,None,{'callback':lambda:zp.command('VISIBILITY',kind='SHOW')}),('HidePt',None,None,{'callback':lambda:zp.command('VISIBILITY',kind='HIDE_UNMASKED')})])

    morph=palette('Morph Target')
    pair(morph,[('StoreMT','Morph Target','STORE'),('Switch','Morph Target','SWITCH')]);pair(morph,[('DelMT','Morph Target','DELETE'),('CreateDiff Mesh','Morph Target','DIFFERENCE')])
    for label,kind in [('Morph','MORPH'),('Morph Width','WIDTH'),('Morph Height','HEIGHT'),('Morph Depth','DEPTH'),('MorphDist','DIST')]:option_value(morph,label,'MORPH_ACTION',kind,-1,1,0,action=lambda v,k=kind:invoke('Morph Target',k,value=v))
    act(morph,'Project Morph',callback=lambda:target_action('Topology','PROJECT_MORPH'),hint='Nearest-surface projection modifier from a chosen source. StoreMT is preserved.')

    paint=palette('Polypaint');toggle(paint,'Colorize','Polypaint','colorize');toggle(paint,'Grd','Polypaint','gradient');act(paint,'Fill Color','Polypaint','FILL')
    act(paint,'Polypaint From Texture','Polypaint','FROM_TEXTURE');act(paint,'Polypaint From Polygroups','Polypaint','FROM_GROUPS');option_value(paint,'Adjust Colors','Polypaint','color_adjust',-1,1,.1);act(paint,'Apply Color Adjustment','Polypaint','ADJUST')
    pair(paint,[('Flip By Poseable Symmetry','Polypaint','FLIP_SYMMETRY',{'hint':'Uses StoreMT rest-position correspondence when available, otherwise spatial matching. Automatic posed-topology inference is unavailable.'}),('Mirror By Poseable Symmetry','Polypaint','MIRROR_SYMMETRY',{'hint':'Uses StoreMT rest-position correspondence when available, otherwise spatial matching. Automatic posed-topology inference is unavailable.'})])
    draft=nested(paint,'From Draft');option_value(draft,'Draft Angle','Polypaint','draft_angle',0,180,45);text(draft,'Direction','Polypaint','axis',['X','Y','Z']);act(draft,'SetDir from View',callback=lambda:set_direction('Polypaint'));toggle(draft,'InvDir','Polypaint','invert_direction');act(draft,'From Draft','Polypaint','DRAFT')
    thickness=nested(paint,'From Thickness');option_value(thickness,'Quality','Polypaint','quality',1,32,8,True);option_value(thickness,'Min Thickness','Polypaint','min_thickness',0,10,0);option_value(thickness,'Max Thickness','Polypaint','max_thickness',.001,10,1);act(thickness,'From Thickness','Polypaint','THICKNESS')

    options=palette('Canvas & Pen Preferences')
    for label,key in [('Automatic Sculpt Studio','auto_activate'),('Bbrush pen controls','bbrush_enabled'),('Shortcut HUD','show_shortcut_hud')]:
        cb=QtWidgets.QCheckBox(label);cb.toggled.connect(lambda v,k=key:zp.change(k,v));options.addWidget(cb);panel.controls[key]=cb
    basic(options,'Solo','SOLO');basic(options,'Ghost','GHOST');act(options,'Recovery snapshots…',callback=panel.recovery_menu)
    layout.addStretch(1)

def extended_make(label):
    return zp.command('PALETTE',section='Geometry',kind='MAKE_MESH',label=label)

def set_direction(section):
    direction=bpy.context.space_data.region_3d.view_rotation@__import__('mathutils').Vector((0,0,1))
    axis=max(range(3),key=lambda i:abs(direction[i]))
    zp.command('PALETTE_OPTION',section=section,key='direction',value=list(direction.normalized()))
    zp.command('PALETTE_OPTION',section=section,key='invert_direction',value=False)
    zp.command('PALETTE_OPTION',section=section,key='use_view_direction',value=True)

def array_transform_dialog(panel):
    from PySide6 import QtWidgets
    d=QtWidgets.QDialog();d.setWindowTitle('ArrayMesh · Transform Stage');layout=QtWidgets.QFormLayout(d)
    cfg=instances.config('ArrayMesh')
    for prefix in ('offset','scale','rotate','pivot'):
        for axis in 'xyz':
            key=prefix+'_'+axis;spin=QtWidgets.QDoubleSpinBox();spin.setRange(-180,180);spin.setValue(cfg[key]);spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda v,k=key:zp.command('PALETTE_OPTION',section='ArrayMesh',key=k,value=v));layout.addRow(prefix.title()+' '+axis.upper(),spin)
    panel._dialogs.append(d);zp.place_popup(d)

def refresh(panel):
    from PySide6 import QtCore,QtWidgets
    o=bpy.context.view_layer.objects.active
    if not o or o.type!='MESH':return
    for section,key,widget,value in panel.option_widgets:
        if widget.hasFocus() or (value and value.hasFocus()) or (isinstance(widget,QtWidgets.QSlider) and widget.isSliderDown()):continue
        if isinstance(widget,QtWidgets.QComboBox) and widget.view().isVisible():continue
        if section in ('ArrayMesh','NanoMesh'):cfg=instances.config(section,o)
        elif section=='EXTRACT':cfg={'extract_thickness':state.get().extract_thickness}
        elif section=='DYNAMESH':cfg={'resolution':state.get().dynamesh_resolution}
        elif section=='ZREMESHER':cfg={'target':state.get().zremesher_target_polys}
        elif section=='SDIV':cfg={'level':ops.multires().sculpt_levels if ops.multires() else 0}
        elif section in ('DEFORM_ACTION','MORPH_ACTION'):cfg={key:0}
        else:cfg=extended.settings(section,o)
        current=cfg.get(key,0);guard=QtCore.QSignalBlocker(widget)
        if isinstance(widget,QtWidgets.QAbstractButton):widget.setChecked(bool(current))
        elif isinstance(widget,QtWidgets.QComboBox):widget.setCurrentIndex(widget.findText(str(current)))
        else:
            widget.setValue(round(float(current)*100));value_guard=QtCore.QSignalBlocker(value);value.setValue(float(current));del value_guard
            value.lineEdit().setGeometry(2,0,max(1,value.width()-4),value.height())
        del guard
    choices=[x.name for x in ops.meshes() if x!=o];existing=[panel.nano_source.itemText(i) for i in range(panel.nano_source.count())]
    if choices!=existing and not panel.nano_source.view().isVisible():
        guard=QtCore.QSignalBlocker(panel.nano_source);panel.nano_source.clear();panel.nano_source.addItems(choices);panel.nano_source.setCurrentIndex(panel.nano_source.findText(instances.config('NanoMesh',o)['source']));del guard
    count=int(extended.settings('SubTool',o)['visible_count']);panel.subtools.setFixedHeight(max(72,min(280,count*48)))
    for i,b in enumerate(panel.visibility_sets,1):
        guard=QtCore.QSignalBlocker(b);b.setChecked(int(bpy.context.scene.get('_lf_visibility_active',1))==i);del guard
    for f in panel._extra_refresh:f()
    for index in range(panel.subtools.topLevelItemCount()):
        item=panel.subtools.topLevelItem(index);name=item.data(0,QtCore.Qt.UserRole);mesh=bpy.data.objects.get(name)
        if mesh and item.icon(0).isNull():item.setIcon(0,mesh_icon(panel,mesh))

def mesh_icon(panel,obj):
    from PySide6 import QtCore,QtGui
    from mathutils import Vector
    key=(obj.data.as_pointer(),len(obj.data.vertices),len(obj.data.polygons))
    if key in panel._mesh_icons:return panel._mesh_icons[key]
    pix=QtGui.QPixmap(48,44);pix.fill(QtCore.Qt.transparent);painter=QtGui.QPainter(pix);painter.setRenderHint(QtGui.QPainter.Antialiasing)
    if obj.data.vertices:
        rotation=Vector((1,-2,1)).to_track_quat('Z','Y').inverted()
        points=[rotation@v.co for v in obj.data.vertices]
        lo=[min(p[i] for p in points) for i in range(2)];hi=[max(p[i] for p in points) for i in range(2)];scale=37/max(hi[0]-lo[0],hi[1]-lo[1],.001)
        # Keep ordinary SubTools solid at thumbnail size. Sparse sampling made
        # the creature look like a point cloud rather than a mesh preview.
        stride=max(1,len(obj.data.polygons)//20000);faces=sorted(list(obj.data.polygons)[::stride],key=lambda p:sum(points[v].z for v in p.vertices)/len(p.vertices))
        painter.setPen(QtCore.Qt.NoPen)
        for face in faces:
            normal=rotation@face.normal;shade=int(110+120*max(0,normal.z));painter.setBrush(QtGui.QColor(shade,shade,shade))
            polygon=QtGui.QPolygonF([QtCore.QPointF(5+(points[v].x-lo[0])*scale,40-(points[v].y-lo[1])*scale) for v in face.vertices]);painter.drawPolygon(polygon)
    painter.end();icon=QtGui.QIcon(pix);panel._mesh_icons[key]=icon;return icon
