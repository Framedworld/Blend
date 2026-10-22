import bpy,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import landfall_studio
landfall_studio.register()
from landfall_studio import sculpt
from landfall_studio.keymaps import profiles
from landfall_studio.sculpt import ops
out={}
def snap(label):
    out[label]=[(i.idname,i.type,i.value,i.ctrl,i.shift,i.alt,i.active,repr(sorted(i.properties.items()))) for i in bpy.context.window_manager.keyconfigs.user.keymaps['Sculpt'].keymap_items]
with bpy.context.temp_override(**ops.view_context()):
    snap('before');sculpt.enter();snap('during')
    out['muted']=profiles._sculpt_muted.copy()
    out['owned_ids']=profiles._sculpt_keymaps.copy()
    out['addon_during']=[(i.id,i.idname,i.type,str(list(i.properties.items()))) for i in bpy.context.window_manager.keyconfigs.addon.keymaps['Sculpt'].keymap_items]
    sculpt.return_to_maya();snap('after')
    bpy.context.window_manager.keyconfigs.update();snap('after_update')
Path(ROOT/'output/sculpt_keys_probe.json').write_text(json.dumps(out,indent=2))
landfall_studio.unregister()
