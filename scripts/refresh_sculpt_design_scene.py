"""Render the disposable creature reference with Sculpt's default grid off."""
import bpy,sys,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def suite():
    import landfall_studio
    landfall_studio.register()
    from landfall_studio.ui import desktop
    from landfall_studio.sculpt import preferences,ops,gestures
    preferences.PATH=ROOT.parent/'.test_env/sculpt_reference_preferences.json';preferences._data=None
    desktop.restore_workspace_desktop()
    from landfall_studio.sculpt.demo import create_demo
    create_demo();yield 1
    from landfall_studio.viewport import sculpt_hud
    sculpt_hud._rendering_offscreen=True
    c=ops.view_context();gestures.cursor.update(area=0,xy=(-1000,-1000))
    c['area'].tag_redraw();yield .15
    output=ROOT/'output/sculpt-design'
    with bpy.context.temp_override(**c):bpy.ops.screen.screenshot(filepath=str(output/'assets/creature-scene.png'))
    r=c['region'];w=c['window']
    rect=(r.x+r.width*.05,w.height-r.y-r.height+r.height*.05,r.width*.9,r.height*.9)
    source=(output/'index.html').read_text(encoding='utf-8')
    replacement='<svg class="scene" viewBox="'+' '.join(str(round(v,2)) for v in rect)+'" preserveAspectRatio="xMidYMid slice"><image href="assets/creature-scene.png" width="'+str(w.width)+'" height="'+str(w.height)+'"/>'
    source=re.sub(r'<svg class="scene"[^>]*><image[^>]*/>',lambda _:replacement,source,count=1)
    (output/'index.html').write_text(source,encoding='utf-8')
    (output/'scene-reference.json').write_text(json.dumps({'source':'Disposable existing creature demo','grid':False,'image_size':[w.width,w.height],'viewBox':rect},indent=2))
    landfall_studio.unregister();bpy.ops.wm.quit_blender()
gen=None
def tick():
    try:return next(gen)
    except StopIteration:return None
def start():
    global gen
    bpy.context.preferences.view.show_splash=False;bpy.ops.wm.read_homefile();gen=suite();bpy.app.timers.register(tick,persistent=True)
bpy.app.timers.register(start,first_interval=.5)
