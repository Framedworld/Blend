"""Observer for the unmodified Studio entry point in a relocated local fixture.

The runner supplies a copied runtime tree, isolated resources and no original
source paths. Setup/save/load use production APIs; typed edits and mode buttons
use native synthetic input. This is local relocation, not a clean-machine test.
"""
import ctypes
import json
import os
from pathlib import Path
import sys
import time
import traceback

import bpy

COPY = Path(os.environ['LANDFALL_HANDOFF_COPY']).resolve()
OUT = Path(os.environ['LANDFALL_HANDOFF_RESULT'])
MODE = os.environ['LANDFALL_HANDOFF_MODE']
PROJECT = COPY/'Artist Project Élan'
SCENE = PROJECT/'handoff scene Ω.blend'
TEXTURE = PROJECT/'sourceimages/Surface Ω.png'
result = {'ok':False,'completed':False,'mode':MODE,'pid':os.getpid(),
          'passed':[],'failed':[],'boundary':__doc__}

# open_studio.py has only registered its startup timer when this second
# --python observer runs. Install the upstream test guard BEFORE that timer
# constructs Switchboard/QSettings, so no shared artist Qt store is consumed.
for relative in ('.deps/py313','upstream/pythontk','upstream/uitk'):
    sys.path.insert(0,str(COPY/relative))
from uitk.testing import TestSandbox
_test_stores = TestSandbox.activate()
result['test_stores'] = [str(path) for path in _test_stores]


def save():
    OUT.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')


def check(name, value, detail=None):
    result['passed' if value else 'failed'].append(name if value else {'test':name,'detail':detail})
    save()


def require(name, value, detail=None):
    check(name,value,detail)
    if not value:
        raise RuntimeError(name)


def view():
    w=bpy.context.window_manager.windows[0]
    a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
    return dict(window=w,area=a,region=next(r for r in a.regions if r.type=='WINDOW'))


def suite():
    deadline=time.monotonic()+60
    startup_path=COPY/'Blend/output/interactive_startup.json'
    startup={}
    while time.monotonic()<deadline:
        if startup_path.exists():
            try:
                startup=json.loads(startup_path.read_text(encoding='utf-8'))
            except (ValueError,OSError):
                startup={}
        if startup.get('pid')==os.getpid() and startup.get('ok'):
            break
        if startup.get('pid')==os.getpid() and startup.get('error'):
            raise RuntimeError(startup['error'])
        yield .5
    require('unmodified copied entry point becomes ready',
            startup.get('ok') and startup.get('pid')==os.getpid(),startup)
    result['startup']=startup
    import landfall_studio
    from landfall_studio import sculpt
    from landfall_studio.ui import desktop,shelf,viewport_bar,attribute_editor,menus
    from landfall_studio.sculpt import layout,state
    from landfall_studio.bootstrap import deps
    from landfall_studio.adapters import workspace_bridge,tentacle_bridge
    from PySide6 import QtCore as C,QtWidgets as W,QtGui as G,QtTest as T
    from blendertk.ui_utils.blender_window import BlenderWindow
    import PIL,qtpy,shiboken6,packaging
    report=deps.check_dependencies(force_refresh=True)
    check('copied dependency stack is ready without installers',report['full_stack_ready'])
    module_names=('landfall_studio','landfall_studio._upstream_landfall',
                  'tentacle','blendertk','uitk','pythontk','PySide6','shiboken6','PIL','qtpy','packaging')
    origins={name:str(Path(sys.modules[name].__file__).resolve()) for name in module_names}
    result['module_origins']=origins
    require('every Studio and Qt module comes from the relocated copy',
            all(Path(path).is_relative_to(COPY) for path in origins.values()),origins)
    check('all loaded Studio source modules stay within the copy',
          all(Path(module.__file__).resolve().is_relative_to(COPY)
              for name,module in list(sys.modules.items())
              if name.startswith('landfall_studio') and getattr(module,'__file__',None)))
    check('native PySide6 is the shared binding',qtpy.API_NAME=='PySide6')
    bars=viewport_bar.get_bars()
    check('copied native viewport widgets are visible',bool(bars) and all(b.root.isVisible() for b in bars))
    result['dpr']=G.QGuiApplication.primaryScreen().devicePixelRatio()
    app=W.QApplication.instance()
    require('shared Qt settings use fresh local test stores',TestSandbox.is_active()
            and all(Path(path).resolve().is_relative_to(COPY) for path in _test_stores),
            result['test_stores'])
    switchboard=tentacle_bridge.get_tcl_instance().sb
    settings=switchboard.settings.settings
    result['switchboard_settings']=settings.fileName()
    require('Switchboard uses relocated INI settings',settings.format()==C.QSettings.IniFormat
            and Path(settings.fileName()).resolve().is_relative_to(COPY),settings.fileName())

    def focus(widget):
        G.QCursor.setPos(widget.mapToGlobal(widget.rect().center()))
        app.setActiveWindow(widget.window())
        widget.window().activateWindow()
        widget.setFocus()
        hwnd=int(widget.window().internalWinId() or 0)
        if hwnd:
            BlenderWindow.set_keyboard_focus(hwnd)

    def click(widget):
        require('mode action is visible and enabled',widget.isVisible() and widget.isEnabled(),widget.text())
        focus(widget)
        T.QTest.mouseClick(widget,C.Qt.LeftButton)
        yield .5

    def native_key(kind,**mods):
        if app.focusWidget():
            app.focusWidget().clearFocus()
        app.setActiveWindow(None)
        c=view();r=c['region']
        hwnd=BlenderWindow.window_hwnd(c['window'])
        origin=BlenderWindow.client_origin(hwnd)
        x,y=r.x+r.width//2,r.y+r.height//2
        ctypes.windll.user32.SetCursorPos(origin[0]+x,origin[1]+c['window'].height-1-y)
        BlenderWindow.set_keyboard_focus(hwnd)
        c['window'].event_simulate(type='MOUSEMOVE',value='NOTHING',x=x,y=y)
        c['window'].event_simulate(type=kind,value='PRESS',x=x,y=y,**mods)
        c['window'].event_simulate(type=kind,value='RELEASE',x=x,y=y,**mods)

    if MODE=='sculpt':
        require('copied sculpt launcher creates the creature and pen workspace',
                startup.get('sculpt_active') and startup.get('pen_input_active')
                and bpy.context.object.name=='Creature_Sculpt' and sculpt.is_engaged())
        check('copied brush imagery loads without developer paths',
              all(not tile.icon().isNull() for tile in layout._favorites.tiles.values()))
        yield from click(shelf._shelf_instances[0].sculpt_header.buttons['Return'])
        require('demo Return restores modeling',not sculpt.is_engaged() and bpy.context.mode=='OBJECT')
        require('first-process project file exists before fresh-process reopen',SCENE.is_file())
        menus.run_op('wm.open_mainfile',filepath=str(SCENE))
        yield 1.5
    else:
        require('copied modeling launcher starts in Object mode',
                bpy.context.mode=='OBJECT' and not sculpt.is_engaged())
        workspace_bridge.set_project_root(str(PROJECT))
        check('project setup creates its local workspace file',(PROJECT/'workspace.mel').is_file())
        TEXTURE.parent.mkdir(parents=True,exist_ok=True)
        generated=bpy.data.images.new('Fixture Texture Source',width=8,height=8)
        generated.generated_color=(.8,.25,.08,1)
        generated.filepath_raw=str(TEXTURE)
        generated.file_format='PNG'
        generated.save()
        image=bpy.data.images.load(str(TEXTURE),check_existing=False)
        image.name='Handoff Texture'
        bpy.data.images.remove(generated)
        image.filepath='//sourceimages/Surface Ω.png'
        mat=bpy.data.materials.new('Handoff Material')
        node=mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image=image
        mat.node_tree.links.new(node.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        bpy.context.object.data.materials.clear()
        bpy.context.object.data.materials.append(mat)

    desktop.cycle_right_dock('ATTRIBUTE_EDITOR')
    yield .3
    ae=attribute_editor.ensure_attribute_editor_widget()
    name=bpy.context.object.name
    before=bpy.context.object.location.x
    target=2.5 if MODE=='sculpt' else 1.75
    focus(ae.spn_tx)
    ae.spn_tx.lineEdit().selectAll()
    T.QTest.keyClicks(ae.spn_tx.lineEdit(),str(target))
    T.QTest.keyClick(ae.spn_tx,C.Qt.Key_Return)
    yield .25
    check('typed inspector edit works from the copied runtime',abs(bpy.data.objects[name].location.x-target)<1e-6)
    native_key('Z')
    yield .3
    check('copied runtime keeps native inspector Undo',abs(bpy.data.objects[name].location.x-before)<1e-6)
    native_key('Z',shift=True)
    yield .3
    check('copied runtime keeps native inspector Redo',abs(bpy.data.objects[name].location.x-target)<1e-6)
    if MODE=='modeling':
        bpy.ops.wm.save_as_mainfile(filepath=str(SCENE))
        yield .2
        menus.run_op('wm.open_mainfile',filepath=str(SCENE))
        yield 1.5
    image=bpy.data.images.get('Handoff Texture')
    require('reopened scene retains its real external image',image is not None)
    resolved=Path(bpy.path.abspath(image.filepath)).resolve()
    check('reopened texture is relative and resolves inside the copied project',
          image.filepath.startswith('//') and resolved==TEXTURE.resolve() and resolved.is_file(),str(resolved))
    check('external texture actually decodes after reopen',image.source=='FILE'
          and not image.packed_file and tuple(image.size)==(8,8)
          and image.pixels[0]>.1)
    check('reopened material still uses the external texture',
          any(n.type=='TEX_IMAGE' and n.image==image for n in bpy.data.materials['Handoff Material'].node_tree.nodes))
    result['scene']=str(SCENE);result['texture']=str(resolved)
    sh=shelf._shelf_instances[0]
    tab,tiles=next((tab,tiles) for tab,tiles in sh.tile_buttons.items()
                   if any(t.spec['id']=='sculpt_mode' for t in tiles))
    sh.tabs.setCurrentIndex(list(sh.tile_buttons).index(tab))
    yield .2
    yield from click(next(t for t in tiles if t.spec['id']=='sculpt_mode'))
    require('copied saved-scene Sculpt button enters the actual workspace',
            sculpt.is_engaged() and bpy.context.mode=='SCULPT')
    check('copied brush icons remain available after file load',
          all(not tile.icon().isNull() for tile in layout._favorites.tiles.values()))
    yield from click(layout._favorites.tiles['DS'])
    check('copied favorite activates its native subtractive brush',
          state.get().active_zbrush_brush=='DamStandard' and state.brush().direction=='SUBTRACT')
    yield from click(shelf._shelf_instances[0].sculpt_header.buttons['Return'])
    check('copied scene returns to the modeling workspace',
          not sculpt.is_engaged() and bpy.context.mode=='OBJECT')
    result['completed']=True
    result['ok']=not result['failed']
    save()
    landfall_studio.unregister()
    print('LOCAL_HANDOFF_RESULT',MODE,len(result['passed']),'passed',len(result['failed']),'failed',flush=True)
    bpy.ops.wm.quit_blender()


steps=suite()


def tick():
    try:
        return next(steps)
    except StopIteration:
        return None
    except Exception:
        result['failed'].append({'exception':traceback.format_exc()})
        save()
        traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick,first_interval=.75,persistent=True)
