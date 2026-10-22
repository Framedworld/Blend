"""Studio-wide native widget scenarios in a disposable factory Blender process.

QtTest provides synthetic mouse/keyboard events. This is not physical mouse or
tablet certification. Existing controls_gui supplies Blender canvas events.
"""
import ctypes
import json
import os
import sys
import traceback
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TAG=os.environ.get('LANDFALL_FULL_UX_TAG','')
OUT=ROOT/('output/full_ux_gui'+TAG+'.json')
CAPTURES=ROOT/('output/full-ux'+TAG)
CAPTURES.mkdir(exist_ok=True)
report={'ok':False,'passed':[],'failed':[],'input':'Native PySide6 QtTest + real Blender data; synthetic input','panels':{},'buttons':[]}
def save():OUT.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
def check(label,condition,detail=None):
    report['passed' if condition else 'failed'].append(label if condition else {'test':label,'detail':detail});save()
def context():
    window=bpy.context.window_manager.windows[0]
    area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
    return {'window':window,'screen':window.screen,'area':area,'region':next(r for r in area.regions if r.type=='WINDOW')}
def suite():
    bpy.context.preferences.view.show_splash=False
    bpy.ops.wm.read_homefile()
    import landfall_studio
    from landfall_studio import ui,commands,modeling
    from landfall_studio.ui import desktop,menus,main_menu,shelf,outliner,attribute_editor as ae,tool_settings as ts,channel_box_ext as cb,modifier_stack as ms,right_dock,hotkey_passthrough as hp,style,viewport_bar
    from landfall_studio.sculpt import preferences
    preferences.PATH=ROOT.parent/('.test_env/full_ux_preferences_'+str(os.getpid())+'.json');preferences._data=None
    landfall_studio.register();yield .5
    ui.restore_workspace_desktop(restore_script_output=False);yield .8
    from PySide6 import QtCore as C,QtGui as G,QtWidgets as W,QtTest as T
    from blendertk.ui_utils.blender_window import BlenderWindow
    app=W.QApplication.instance()
    hwnd=BlenderWindow.window_hwnd(context()['window'])
    ctypes.windll.user32.ShowWindow(hwnd,3);ctypes.windll.user32.SetForegroundWindow(hwnd);yield .4
    report['dpr']=W.QApplication.primaryScreen().devicePixelRatio()
    def click(widget):T.QTest.mouseClick(widget,C.Qt.LeftButton)
    def focus(widget):
        app.setActiveWindow(widget.window());widget.window().activateWindow();widget.setFocus(C.Qt.MouseFocusReason)
    def select(obj):
        for item in bpy.context.view_layer.objects:item.select_set(False)
        if obj:obj.select_set(True)
        bpy.context.view_layer.objects.active=obj
        desktop._on_scene_or_undo_sync()
    def wheel(widget,ctrl=False):
        p=C.QPointF(widget.mapToGlobal(widget.rect().center()))
        ev=G.QWheelEvent(C.QPointF(widget.rect().center()),p,C.QPoint(),C.QPoint(0,-120),C.Qt.NoButton,C.Qt.ControlModifier if ctrl else C.Qt.NoModifier,C.Qt.NoScrollPhase,False)
        app.sendEvent(widget,ev)
    cube=bpy.data.objects['Cube'];select(cube)
    # Every registered operator menu is checked against its current native poll.
    for title,entries in menus.all_menu_entries():
        menu=W.QMenu();menus.build_qmenu(menu,entries)
        for current in [menu]+menu.findChildren(W.QMenu):
            current.aboutToShow.emit()
            for action in current.actions():
                data=action.data()
                if isinstance(data,dict) and 'operator' in data:
                    path=data['operator'];module,name=path.split('.',1)
                    with bpy.context.temp_override(**context()):expected=getattr(getattr(bpy.ops,module),name).poll()
                    check('availability '+title+' / '+action.text(),action.isEnabled()==expected and (expected or bool(action.toolTip())))
        menu.deleteLater()
    menu=W.QMenu();menus.build_qmenu(menu,[menus.O('Unavailable fixture','landfall_missing.no_such_command')]);menu.aboutToShow.emit()
    check('unavailable installation command is disabled with explanation',not menu.actions()[0].isEnabled() and bool(menu.actions()[0].toolTip()));menu.deleteLater()
    menus._safe_call(lambda:{'ok':False,'error':'Select two meshes.'},'Boolean fixture')
    check('failed callable reports useful error',desktop.get_command_feedback()['is_error'] and desktop.get_command_feedback()['result']=='Select two meshes.')
    menus._safe_call(lambda:{'CANCELLED'},'Cancelled dialog')
    check('cancelled command does not show success or error',desktop.get_command_feedback()['result']=='Cancelled' and not desktop.get_command_feedback()['is_error'])
    # Dialogs and native controls retain their own keyboard actions.
    dialog=W.QDialog();dialog.setWindowModality(C.Qt.ApplicationModal)
    layout=W.QVBoxLayout(dialog);button=W.QPushButton('Close');layout.addWidget(button)
    dialog.show();button.setFocus();yield .1
    commands.set_active_tool('ROTATE');T.QTest.keyClick(button,C.Qt.Key_W)
    check('modal dialog does not forward viewport W',commands.get_active_tool()=='ROTATE')
    dialog.close();dialog.deleteLater();yield .1
    frame=W.QFrame();style.apply_studio_style(frame);lay=W.QVBoxLayout(frame)
    toggle=W.QCheckBox('Native keyboard activation');lay.addWidget(toggle)
    combo=W.QComboBox();combo.addItems(['World','Local','Normal']);lay.addWidget(combo)
    frame.show();focus(toggle);T.QTest.keyClick(toggle,C.Qt.Key_Space)
    check('Space activates focused native checkbox',toggle.isChecked())
    focus(combo);T.QTest.keyClick(combo,C.Qt.Key_W)
    check('focused picker retains type-ahead W',commands.get_active_tool()=='ROTATE')
    combo.setCurrentIndex(1);wheel(combo)
    check('wheel does not change a closed picker',combo.currentIndex()==1)
    frame.close();frame.deleteLater();yield .1
    # Attribute Editor reads viewport changes and preserves unfinished text.
    desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .2
    editor=ae.ensure_attribute_editor_widget();cube.location.x=3.25
    desktop._on_live_scene_or_depsgraph_update()
    check('AE follows ordinary viewport transforms',abs(editor.spn_tx.value()-3.25)<.001)
    focus(editor.spn_sx);editor.spn_sx.lineEdit().selectAll();T.QTest.keyClicks(editor.spn_sx.lineEdit(),'-2.5')
    check('AE numeric field retains native focus',editor.spn_sx.hasFocus())
    before=editor.spn_sx.lineEdit().text();ae.refresh_attribute_editor()
    check('idle AE refresh preserves pending text',editor.spn_sx.lineEdit().text()==before)
    T.QTest.keyClick(editor.spn_sx.lineEdit(),C.Qt.Key_Return)
    check('AE accepts negative scale',abs(cube.scale.x+2.5)<.001,cube.scale.x)
    editor.spn_sx.clearFocus();before=cube.location.x;wheel(editor.spn_tx)
    check('wheel cannot accidentally move the selected object',cube.location.x==before)
    wheel(editor.spn_tx,True)
    check('Ctrl wheel explicitly adjusts a transform',cube.location.x!=before)
    select(None);editor.refresh()
    check('AE disables stale fields when selection is empty',not editor.tabs.isEnabled())
    select(cube)
    # Floating and docked inspectors share refresh, without sharing stale bindings.
    floating=right_dock.tear_off_panel('ATTRIBUTE_EDITOR');yield .2
    controllers=[x for x in ae._ae_instances if x is not editor]
    check('floating AE registers for scene updates',bool(controllers),floating)
    if controllers:
        detached=controllers[-1];cube.location.y=6.25;desktop._on_live_scene_or_depsgraph_update()
        check('floating AE follows viewport transform',abs(detached.spn_ty.value()-6.25)<.001)
    right_dock.close_tear_off_panel('ATTRIBUTE_EDITOR');yield .1
    right_dock.tear_off_panel('TOOL_SETTINGS');yield .1
    floating_win=right_dock._tear_off_windows['TOOL_SETTINGS'];grip=floating_win._studio_grip
    start=floating_win.pos();local=C.QPoint(12,12);global_start=grip.mapToGlobal(local)
    T.QTest.mousePress(grip,C.Qt.LeftButton,pos=local)
    move=G.QMouseEvent(C.QEvent.MouseMove,C.QPointF(local+C.QPoint(25,15)),C.QPointF(global_start+C.QPoint(25,15)),C.Qt.NoButton,C.Qt.LeftButton,C.Qt.NoModifier)
    app.sendEvent(grip,move);T.QTest.mouseRelease(grip,C.Qt.LeftButton,pos=local)
    check('floating editor header can move the window',floating_win.pos()!=start)
    check('floating editor exposes a native resize grip',bool(floating_win.findChildren(W.QSizeGrip)))
    right_dock.close_tear_off_panel('TOOL_SETTINGS');yield .1
    # Nested Outliner selection/expansion survive a structural refresh.
    with bpy.context.temp_override(**context()):bpy.ops.object.empty_add()
    parent=bpy.context.active_object;parent.name='UX_Parent';cube.parent=parent;select(cube)
    rail=outliner.get_left_outliner_dock().ensure_outliner_widget()
    def items():
        it=W.QTreeWidgetItemIterator(rail.tree);found=[]
        while it.value():found.append(it.value());it+=1
        return found
    rail.refresh();child=next(x for x in items() if x.text(0)==cube.name)
    check('parented selected object has Outliner highlight',child.isSelected())
    top=next(x for x in items() if x.text(0)==parent.name);top.setExpanded(False);rail.refresh()
    top=next(x for x in items() if x.text(0)==parent.name)
    check('Outliner preserves collapsed parent',not top.isExpanded())
    top.setExpanded(True);rail.txt_search.setText('Cube');rail.refresh()
    check('Outliner search preserves Blender selection',cube.select_get())
    rail.txt_search.clear();rail.refresh()
    # INPUTS selection must not steal a subsequent transform scrub.
    bevel=cube.modifiers.new('UX_Bevel','BEVEL');bevel.width=.1
    desktop.cycle_right_dock('CHANNEL_BOX');desktop.sync_channels_now();cb.refresh_channel_box_extensions();yield .2
    channels,slots=desktop.get_panel_widget_and_slots('channels');extra=cb.ensure_channel_box_extensions(channels)
    tree=extra.tree_inputs
    node=next((tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if tree.topLevelItem(i).text(0)==bevel.name),None)
    check('Channel Box exposes actual modifier inputs',node is not None)
    if node:
        node.setExpanded(True);item=node.child(0);tree.setCurrentItem(item);item.setSelected(True)
        cb.select_channels_in_ui(['location_x'])
        before=bevel.width;before_x=cube.location.x
        res=cb.scrub_selected_channels(.5)
        check('transform selection clears old INPUTS scrub target',bevel.width==before and cube.location.x!=before_x,res)
    # Modifier fields preserve editing and are bound to their displayed object.
    desktop.cycle_right_dock('MODIFIER_STACK');yield .2
    host=desktop._right_dock._ensure_host_container();stack=host.ms_panel
    bevel.show_expanded=True;stack.refresh()
    edits=stack.cards_host.findChildren(W.QLineEdit)
    check('Modifier Stack exposes editable native fields',bool(edits))
    if edits:
        field=edits[0];focus(field);field.setText('0.375');stack.refresh()
        check('modifier refresh preserves current editor',field in stack.cards_host.findChildren(W.QLineEdit) and field.text()=='0.375')
        field.clearFocus()
    stack.refresh();yield .2
    check('modifier card is visibly rendered after refresh',bool(stack._cards) and stack._cards[0].isVisible() and stack._cards[0].height()>40)
    field=stack.cards_host.findChildren(W.QLineEdit)[0];focus(field);field.setText('oops');T.QTest.keyClick(field,C.Qt.Key_Return);yield .2
    check('invalid modifier text reports failure without changing mesh',desktop.get_command_feedback()['is_error'] and abs(bevel.width-.375)<.001)
    field=stack.cards_host.findChildren(W.QLineEdit)[0]
    check('invalid modifier text resets to actual value',field.text()!='oops')
    field.clearFocus()
    desktop._last_selection_value_sig=desktop._compute_selection_value_sig();bevel.width=.425
    desktop._on_live_scene_or_depsgraph_update();yield .2
    check('external modifier edits refresh inspector fields',any(abs(float(e.text())-.425)<.001 for e in stack.cards_host.findChildren(W.QLineEdit)))
    # Shape and material editing: real values, extended ranges and stable rows.
    select(cube);cube.shape_key_add(name='Basis');target=cube.shape_key_add(name='UX_Target');target.slider_min=-1;target.slider_max=2
    desktop.cycle_right_dock('SHAPE_EDITOR');yield .2
    shape=host.se_widget;shape.refresh_from_scene()
    check('shape weight controls use the actual key range',shape._weight_spin.minimum()==-1 and shape._weight_spin.maximum()==2)
    focus(shape._weight_spin);shape._weight_spin.lineEdit().selectAll();T.QTest.keyClicks(shape._weight_spin.lineEdit(),'1.5');T.QTest.keyClick(shape._weight_spin.lineEdit(),C.Qt.Key_Return)
    check('typed shape weight changes actual target',abs(target.value-1.5)<.001,target.value)
    shape._weight_spin.clearFocus();row=shape._shape_table.item(1,0);shape.refresh_from_scene()
    check('shape rows remain stable on idle refresh',shape._shape_table.item(1,0) is row)
    select(None);shape.refresh_from_scene()
    check('shape controls disable without a mesh',not shape._weight_spin.isEnabled() and not shape._selected_key_name)
    select(cube);desktop.cycle_right_dock('HYPERSHADE');yield .2
    hs=host.hs_widget
    preset=next(b for b in hs.findChildren(W.QPushButton) if b.text()=='Plastic');click(preset);yield .2
    material=cube.active_material;check('material preset click assigns actual material',material is not None and material.name==hs._selected_mat_name)
    node=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    node.inputs['Roughness'].default_value=.37;desktop._on_live_scene_or_depsgraph_update();yield .1
    check('external shader edits update Hypershade',hs._sliders['roughness'].value()==37,hs._sliders['roughness'].value())
    row=hs.tbl_mats.item(hs.tbl_mats.currentRow(),0);hs.refresh_from_scene()
    check('material rows remain stable on idle refresh',hs.tbl_mats.item(hs.tbl_mats.currentRow(),0) is row)
    unused=bpy.data.materials.new('UX_Unassigned');unused.use_nodes=True
    desktop._on_live_scene_or_depsgraph_update();yield .1
    check('material browser notices unassigned library additions',any(hs.tbl_mats.item(r,0).text()==unused.name for r in range(hs.tbl_mats.rowCount())))
    row=next(r for r in range(hs.tbl_mats.rowCount()) if hs.tbl_mats.item(r,0).text()==unused.name);hs.tbl_mats.selectRow(row)
    desktop._last_selection_value_sig=desktop._compute_selection_value_sig()
    next(n for n in unused.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Roughness'].default_value=.29
    desktop._on_live_scene_or_depsgraph_update();yield .1
    check('external edits update displayed unassigned material',hs._sliders['roughness'].value()==29)
    before=node.inputs['Metallic'].default_value;wheel(hs._sliders['metallic'])
    check('wheel over shader slider does not edit the material',node.inputs['Metallic'].default_value==before)
    ts.set_tool_setting('soft_select_enabled',True);ts.reset_tool_settings()
    check('Reset Tool clears both soft-selection modes',not bpy.context.scene.tool_settings.use_proportional_edit and not bpy.context.scene.tool_settings.use_proportional_edit_objects)
    # Timeline clicks/typing and command strip execute once.
    timeline=ui.time_slider.get_bottom_time_slider_dock()._ctrl
    scene=bpy.context.scene;scene.frame_set(17);timeline.refresh_from_scene()
    click(timeline.btn_auto_key);check('Auto Key button updates scene',scene.tool_settings.use_keyframe_insert_auto==timeline.btn_auto_key.isChecked())
    click(timeline.btn_auto_key)
    focus(timeline.spin_current);timeline.spin_current.lineEdit().setText('42');timeline.refresh_from_scene()
    check('timeline refresh preserves unfinished frame text',timeline.spin_current.lineEdit().text()=='42')
    T.QTest.keyClick(timeline.spin_current.lineEdit(),C.Qt.Key_Return)
    check('typed current frame commits on Enter',scene.frame_current==42)
    timeline.spin_current.clearFocus();scene['ux_click_count']=0
    timeline.txt_command.setText("bpy.context.scene['ux_click_count'] += 1");click(timeline.btn_cmd_lang)
    check('command button invokes exactly once',scene['ux_click_count']==1 and not timeline.txt_command.text())
    timeline.txt_command.setText('this_is_not_a_valid_command()');T.QTest.keyClick(timeline.txt_command,C.Qt.Key_Return)
    check('command errors are visible',desktop.get_command_feedback()['is_error'])
    # Inspect every native sidebar page; keep an inventory with actual button bounds.
    for mode in ('CHANNEL_BOX','ATTRIBUTE_EDITOR','TOOL_SETTINGS','MODELING_TOOLKIT','MODIFIER_STACK','HYPERSHADE','SHAPE_EDITOR','MAYA_INTERCHANGE'):
        desktop.cycle_right_dock(mode);yield .15
        current=host.stack.currentWidget();current.grab().save(str(CAPTURES/(mode+'.png')))
        report['panels'][mode]={'visible':current.isVisible(),'width':current.width(),'height':current.height(),'minimum_hint':[current.minimumSizeHint().width(),current.minimumSizeHint().height()]}
        check(mode+' opens a native visible page',current.isVisible())
        for b in current.findChildren(W.QAbstractButton):
            if b.isVisible():report['buttons'].append({'panel':mode,'label':b.text(),'name':b.objectName(),'enabled':b.isEnabled(),'tip':b.toolTip(),'size':[b.width(),b.height()]})
        if mode=='MODIFIER_STACK':
            report['modifier_cards']=[{'visible':c.isVisible(),'geometry':[c.x(),c.y(),c.width(),c.height()]} for c in stack._cards]
            check('modifier card survives leaving and reopening its page',bool(stack._cards) and stack._cards[0].isVisible() and stack._cards[0].height()>40)
    bridge=host.mi_widget
    check('runtime badge distinguishes discovery from readiness','Ready' not in bridge.lbl_runtime_badge.text())
    bridge.txt_ma_path.clear();click(bridge.btn_preflight)
    check('missing interchange source gives actionable feedback','Choose a Maya source' in bridge.txt_report.toPlainText())
    bridge.refresh_from_scene()
    check('idle refresh cannot replace latest error with old success','Choose a Maya source' in bridge.txt_report.toPlainText())
    desktop.set_command_feedback('Modeling fixture','Done');bridge.refresh_from_scene()
    check('report repaint does not overwrite newer command feedback',desktop.get_command_feedback()['command']=='Modeling fixture')
    check('reference commands disabled without a row',not bridge.btn_ref_reload.isEnabled() and not bridge.btn_ref_remove.isEnabled())
    # Menu-set changes must not accumulate hidden menus indefinitely.
    bar=main_menu.get_main_menu_dock().ctrl
    count=len(bar.menubar.findChildren(W.QMenu))
    for name in ('Animation','Rigging','FX','Rendering','Modeling')*2:
        main_menu.set_menu_set(name);app.sendPostedEvents(None,C.QEvent.DeferredDelete)
    check('repeated menu-set changes do not leak menus',len(bar.menubar.findChildren(W.QMenu))<=count+2,[count,len(bar.menubar.findChildren(W.QMenu))])
    # Click actual menu labels: merely inventorying their actions missed a
    # foreign-parent focus bug that dismissed the popup on its next message.
    for title in ('File','Edit','Mesh','Help'):
        action=next(a for a in bar.menubar.actions() if a.text().replace('&','')==title)
        rect=bar.menubar.actionGeometry(action)
        # QtTest bypasses Windows' activation sequence. Settle the real hosted
        # window focus before injecting its click (as in the inspector tests).
        focus(bar.menubar)
        native=int(bar.menubar.window().internalWinId() or 0)
        if native:BlenderWindow.set_keyboard_focus(native)
        G.QCursor.setPos(bar.menubar.mapToGlobal(rect.center()));yield .1
        report.setdefault('menu_clicks',[]).append({'title':title,'visible_before':action.menu().isVisible(),
            'active_window':str(app.activeWindow()),'focus':str(app.focusWidget())})
        T.QTest.mouseClick(bar.menubar,C.Qt.LeftButton,pos=rect.center());yield .2
        check('single click keeps '+title+' menu open',action.menu().isVisible())
        T.QTest.keyClick(action.menu(),C.Qt.Key_Escape);yield .1
        check('Escape dismisses '+title+' menu',not action.menu().isVisible())
    # Also exercise the OS activation path from Blender's canvas, without
    # pre-activating the Qt bar. These are Windows mouse/key messages, still
    # synthetic input rather than physical-device certification.
    # On a hidden test desktop OS clicks would reach the artist's visible
    # desktop instead, so this route is reported as not exercised.
    os_input=not os.environ.get('LANDFALL_NO_OS_INPUT')
    if not os_input:report['native_menu_clicks_skipped']='LANDFALL_NO_OS_INPUT: hidden desktop run'
    for title in (('File','Edit','Mesh','Help') if os_input else ()):
        from ctypes import wintypes
        user=ctypes.windll.user32
        user.WindowFromPoint.argtypes=[wintypes.POINT];user.WindowFromPoint.restype=wintypes.HWND
        user.GetForegroundWindow.restype=wintypes.HWND
        action=next(a for a in bar.menubar.actions() if a.text().replace('&','')==title)
        if app.focusWidget():app.focusWidget().clearFocus()
        app.setActiveWindow(None)
        hwnd=BlenderWindow.window_hwnd(context()['window'])
        if not hwnd:raise RuntimeError('Native click fixture has no unique live GHOST window')
        foreground=user.GetForegroundWindow()
        foreground_thread=user.GetWindowThreadProcessId(foreground,None)
        test_thread=ctypes.windll.kernel32.GetCurrentThreadId()
        attached=bool(foreground_thread and foreground_thread!=test_thread and user.AttachThreadInput(test_thread,foreground_thread,True))
        try:
            # A background-shell test is denied bare SetForegroundWindow by
            # Windows. Use the upstream harness's scoped thread-input idiom.
            user.ShowWindow(ctypes.c_void_p(hwnd),9)
            user.BringWindowToTop(ctypes.c_void_p(hwnd));user.SetForegroundWindow(ctypes.c_void_p(hwnd))
        finally:
            if attached:user.AttachThreadInput(test_thread,foreground_thread,False)
        BlenderWindow.set_keyboard_focus(hwnd);yield .15
        # Qt global coordinates are logical. Derive OS pixels from the actual
        # hosted HWND bounds, including custom QT_SCALE_FACTOR in this matrix.
        frame=bar.menubar.window();frame_hwnd=int(frame.internalWinId())
        origin=BlenderWindow.client_origin(frame_hwnd);size=BlenderWindow.client_size(frame_hwnd)
        local=bar.menubar.mapTo(frame,bar.menubar.actionGeometry(action).center())
        p=wintypes.POINT(origin[0]+round(local.x()*size[0]/frame.width()),origin[1]+round(local.y()*size[1]/frame.height()))
        user.SetCursorPos(p.x,p.y);yield .1
        hit=user.WindowFromPoint(p);hit_pid=wintypes.DWORD();user.GetWindowThreadProcessId(hit,ctypes.byref(hit_pid))
        foreground=user.GetForegroundWindow();foreground_pid=wintypes.DWORD();user.GetWindowThreadProcessId(foreground,ctypes.byref(foreground_pid))
        owned=hit_pid.value==os.getpid() and foreground_pid.value==os.getpid()
        report.setdefault('native_menu_clicks',[]).append({'title':title,'point':[p.x,p.y],'host_origin':origin,'host_size':size,
            'logical_size':[frame.width(),frame.height()],'hit_pid':hit_pid.value,'foreground_pid':foreground_pid.value,'test_pid':os.getpid(),'hwnd':hwnd})
        check('Windows click target belongs to test Blender for '+title,owned,report['native_menu_clicks'][-1])
        if not owned:raise RuntimeError('Native click fixture could not acquire its own Blender window; no OS click sent')
        user.mouse_event(0x0002,0,0,0,0);yield .04
        user.mouse_event(0x0004,0,0,0,0);yield .2
        check('Windows single click opens '+title+' from canvas focus',action.menu().isVisible())
        user.keybd_event(0x1B,0,0,0);user.keybd_event(0x1B,0,0x0002,0);yield .15
        check('Windows Escape dismisses '+title+' menu',not action.menu().isVisible())
    desktop.apply_workspace_layout('Modeling Standard');yield .3
    before=len(context()['window'].screen.areas)
    ui.restore_workspace_desktop(restore_script_output=False);yield .3
    check('desktop restore is idempotent',len(context()['window'].screen.areas)==before)
    # Full native desktop geometry plus widget captures at common window sizes.
    cube.name='Creature_Body_Retopo_With_An_Imported_Production_Name_'*3
    material.name='Creature_Skin_Lookdev_With_An_Imported_Production_Name_'*3
    cube.active_material=material
    arm_data=bpy.data.armatures.new('UXLongNameRigData')
    rig=bpy.data.objects.new('Creature_Main_Armature_With_An_Imported_Production_Name_'*3,arm_data)
    scene.collection.objects.link(rig)
    arm_mod=cube.modifiers.new('UXLongNameRig','ARMATURE');arm_mod.object=rig
    shape.refresh_from_scene()
    from ctypes import wintypes
    ctypes.windll.user32.ShowWindow(hwnd,9)
    for width,height in ((1280,720),(1920,1080),(2560,1440)):
        rect=wintypes.RECT();ctypes.windll.user32.GetWindowRect(hwnd,ctypes.byref(rect));client=BlenderWindow.client_size(hwnd)
        ctypes.windll.user32.SetWindowPos(hwnd,None,0,0,width+(rect.right-rect.left-client[0]),height+(rect.bottom-rect.top-client[1]),0)
        yield .6
        desktop.cycle_right_dock('ATTRIBUTE_EDITOR');yield .1
        panel=editor.widget;fields=[getattr(editor,'spn_'+axis) for axis in ('tx','ty','tz','sx','sy','sz')]
        geometry=[{'value':f.lineEdit().text(),'editor_width':f.lineEdit().width(),'field_width':f.width(),'text_width':f.fontMetrics().horizontalAdvance(f.lineEdit().text())} for f in fields]
        report.setdefault('responsive',[]).append({'requested':[width,height],'actual_client':BlenderWindow.client_size(hwnd),'fields':geometry})
        check('readable transform fields at '+str(width),all(g['editor_width']>=g['text_width']+2 for g in geometry),geometry)
        check('transform controls fit their inspector at '+str(width),all(f.mapTo(panel,C.QPoint(f.width(),0)).x()<=panel.width() for f in fields),{'panel':panel.width(),'field_rights':[f.mapTo(panel,C.QPoint(f.width(),0)).x() for f in fields]})
        check('AE tabs retain discoverable roles at '+str(width),editor.tabs.tabText(0)=='Transform' and editor.tabs.tabText(1)=='Shape'
              and 'Transform' in editor.tabs.tabToolTip(0) and cube.name in editor.tabs.tabToolTip(0))
        check('AE production name has its own readable row at '+str(width),editor.lbl_node_title.width()>panel.width()*.85
              and cube.name in editor.lbl_node_title.toolTip(),{'title_width':editor.lbl_node_title.width(),'panel_width':panel.width(),'text':editor.lbl_node_title.text()})
        check('native viewport retains canvas at '+str(width),context()['region'].width>200 and context()['region'].height>150)
        root=host.root;region=desktop._right_dock._inner_dock.content_region()
        report['responsive'][-1]['sidebar']={'root':root.width(),'native_region':region.width,'dpr':root.devicePixelRatioF(),
             'minimum_hint':root.minimumSizeHint().width(),'area_width':desktop._right_dock._inner_dock.area.width,'extent':[context()['window'].width,context()['window'].height]}
        from landfall_studio.sculpt import layout as sculpt_layout
        report['responsive'][-1]['resize_queue']={'pending':len(sculpt_layout._pending),'last_events':sculpt_layout.resize_events[-12:]}
        check('long names cannot enlarge the shared sidebar at '+str(width),root.width()<=region.width/root.devicePixelRatioF()+2,
              {'root':root.width(),'native_region':region.width,'dpr':root.devicePixelRatioF(),'hint':root.minimumSizeHint().width()})
        panel.grab().save(str(CAPTURES/('ATTRIBUTE_EDITOR_'+str(width)+'.png')))
        desktop.cycle_right_dock('MODIFIER_STACK');yield .1
        stack.root.grab().save(str(CAPTURES/('MODIFIER_STACK_'+str(width)+'.png')))
        desktop.cycle_right_dock('SHAPE_EDITOR');yield .1
        check('long mesh and rig names keep Shape/Skin within viewport at '+str(width),shape.widget().width()<=shape.viewport().width(),
              {'content':shape.widget().width(),'viewport':shape.viewport().width(),'mesh':cube.name,'rig':rig.name})
        badge=shape._hazard_pill;right=badge.mapTo(shape.viewport(),C.QPoint(badge.width(),0)).x()
        check('morph status badge is fully readable at '+str(width),right<=shape.viewport().width() and badge.width()>=badge.fontMetrics().horizontalAdvance(badge.text())+12,
              {'right':right,'viewport':shape.viewport().width(),'badge':badge.width(),'text':badge.text()})
        check('elided production names retain their complete tooltip at '+str(width),cube.name in shape._obj_label.toolTip() and rig.name in shape._skin_summary_lbl.toolTip()
              and shape._obj_label.fontMetrics().horizontalAdvance(shape._obj_label.text())<=shape._obj_label.width(),shape._obj_label.text())
        shape.ensureWidgetVisible(shape._weight_spin);yield .05
        field=shape._weight_spin
        check('readable shape weight at '+str(width),field.lineEdit().width()>=field.fontMetrics().horizontalAdvance(field.lineEdit().text())+2,
              {'editor':field.lineEdit().width(),'text':field.lineEdit().text()})
        buttons=[b for b in shape.findChildren(W.QPushButton) if b.isVisible()]
        metrics=[{'label':b.text(),'width':b.width(),'required':b.fontMetrics().horizontalAdvance(b.text())+(b.iconSize().width()+4 if not b.icon().isNull() else 0)+16} for b in buttons]
        check('complete shape and skin action labels at '+str(width),all(m['width']>=m['required'] for m in metrics),metrics)
        shape.verticalScrollBar().setValue(0);shape.grab().save(str(CAPTURES/('SHAPE_EDITOR_'+str(width)+'_top.png')))
        bottom=next(b for b in buttons if b.text()=='Audit Skin');shape.ensureWidgetVisible(bottom);yield .05
        end=bottom.mapTo(shape.viewport(),C.QPoint(0,bottom.height()))
        check('bottom skin actions are reachable at '+str(width),0<end.y()<=shape.viewport().height(),[end.y(),shape.viewport().height()])
        shape.grab().save(str(CAPTURES/('SHAPE_EDITOR_'+str(width)+'_bottom.png')))
        if width==1280:
            pen=G.QPointingDevice('Studio model pen',93,G.QInputDevice.DeviceType.Stylus,G.QPointingDevice.PointerType.Pen,
                 G.QInputDevice.Capability.Position|G.QInputDevice.Capability.Pressure,1,3)
            def tablet(widget,kind,p):
                local=C.QPointF(widget.mapFromGlobal(p.toPoint()))
                e=G.QTabletEvent(kind,pen,local,p,.00001 if kind!=C.QEvent.TabletRelease else 0,0,0,0,0,0,C.Qt.NoModifier,
                    C.Qt.NoButton if kind==C.QEvent.TabletMove else C.Qt.LeftButton,C.Qt.NoButton if kind==C.QEvent.TabletRelease else C.Qt.LeftButton)
                app.sendEvent(widget,e)
            activations=[];bottom.clicked.connect(lambda:activations.append(1))
            p=C.QPointF(bottom.mapToGlobal(bottom.rect().center()))
            tablet(bottom,C.QEvent.TabletPress,p);tablet(bottom,C.QEvent.TabletRelease,p);yield .05
            check('light pen contact activates a modeling panel button once',len(activations)==1,len(activations))
            scroll=shape.verticalScrollBar()
            if scroll.maximum()>0:
                scroll.setValue(0);p=C.QPointF(shape.viewport().mapToGlobal(C.QPoint(2,shape.viewport().height()*2//3)))
                tablet(shape.viewport(),C.QEvent.TabletPress,p)
                tablet(shape.viewport(),C.QEvent.TabletMove,p-C.QPointF(0,70))
                tablet(shape.viewport(),C.QEvent.TabletRelease,p-C.QPointF(0,70));yield .05
                check('pen grabs and scrolls Shape/Skin without activating an action',scroll.value()>0 and len(activations)==1,[scroll.value(),len(activations)])
    report['ok']=not report['failed'];save()
    landfall_studio.unregister();bpy.ops.wm.quit_blender()

steps=suite()
def tick():
    try:return next(steps)
    except StopIteration:return None
    except Exception:
        report['failed'].append({'exception':traceback.format_exc()});save();traceback.print_exc();bpy.ops.wm.quit_blender();return None
bpy.app.timers.register(tick,first_interval=.5,persistent=True)
