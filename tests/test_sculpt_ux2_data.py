"""Scene save/reopen and per-brush settings acceptance, disposable file only."""
import bpy,sys,json,traceback,os,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/sculpt_ux2_data_results.json';results={'passed':[],'failed':[]}
def check(name,value):
    results['passed' if value else 'failed'].append(name);OUT.write_text(json.dumps(results,indent=2))
import landfall_studio
landfall_studio.register()
from landfall_studio import sculpt
from landfall_studio.sculpt import ops,state,brushes,preferences
isolation_report=os.environ.get('LANDFALL_UI_ISOLATION_REPORT')
preferences.PATH=(Path(isolation_report).parent/'sculpt_preferences.json' if isolation_report
                  else ROOT.parent/('.test_env/ux2_preferences_'+uuid.uuid4().hex+'.json'))
preferences._data=None
try:
    results['preferences_path']=str(preferences.PATH)
    results['preferences_file_existed_before']=preferences.PATH.exists()
    check('fresh preference file starts absent',not results['preferences_file_existed_before'])
    results['initial_favorites']=list(preferences.get()['favorites'])
    check('fresh favorites start in approved order',results['initial_favorites']==['ST','CB','MV','DS','TD','HP','IN','PI'])
    with bpy.context.temp_override(**ops.view_context()):
        sculpt.enter();bpy.ops.ed.undo_push(message='UX baseline')
        brushes.select('ST');s=state.get();s.draw_size=96;s.z_intensity=73;s.focal_shift=18;s.lazy_mouse=True;s.z_mode='SUBTRACT'
        brushes.set_stroke(method='DOTS',alpha='NOISE')
        brushes.select('DS')
        check('fresh DamStandard subtracts',s.z_mode=='SUBTRACT' and state.brush().direction=='SUBTRACT')
        s.z_intensity=27;s.focal_shift=-70;brushes.set_stroke(method='ANCHORED',alpha='SQUARE')
        brushes.select('ST')
        check('Standard restores intensity focal direction lazy stroke alpha',round(s.z_intensity)==73 and round(s.focal_shift)==18 and s.z_mode=='SUBTRACT' and s.lazy_mouse and s.stroke_method=='DOTS' and s.alpha=='NOISE' and state.brush().texture is not None)
        brushes.select('DS')
        check('DamStandard restores its independent settings',round(state.brush().strength*100)==27 and s.stroke_method=='ANCHORED' and s.alpha=='SQUARE')
        check('Draw Size stays shared',s.draw_size==96 and state.brush().size==96)
        brushes.select('CR');check('fresh Crease subtracts',s.z_mode=='SUBTRACT')
        brushes.select('CB');check('ClayBuildup uses square alpha resource',s.alpha=='SQUARE' and state.brush().texture is not None)
        brushes.select('DS');brushes.reset()
        check('Reset restores preset and retains shared size',round(s.z_intensity)==50 and round(s.focal_shift)==-50 and s.z_mode=='SUBTRACT' and not s.lazy_mouse and s.stroke_method=='SPACE' and s.alpha=='NONE' and s.draw_size==96)
        preferences.favorite('SH',True);preferences.reorder('SH',0);preferences._data=None
        check('favorites persist explicit pin order',preferences.get()['favorites'][0]=='SH')
        before=list(preferences.get()['favorites']);preferences.remember('SM');preferences.remember('CL')
        check('recents never reorder favorites',preferences.get()['favorites']==before)
        brushes.select('ST');brushes.snapshot();path=ROOT.parent/'.test_env/ux2_brush_roundtrip.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        bpy.ops.wm.open_mainfile(filepath=str(path))
    with bpy.context.temp_override(**ops.view_context()):
        s=state.get();brushes.select('DS');brushes.select('ST')
        check('saved scene restores independent brush memory',round(s.z_intensity)==73 and s.stroke_method=='DOTS' and s.alpha=='NOISE' and s.draw_size==96)
except Exception:
    results['failed'].append(traceback.format_exc())
finally:
    try:sculpt.unregister()
    except Exception:results['failed'].append(traceback.format_exc())
    landfall_studio.unregister();OUT.write_text(json.dumps(results,indent=2));print('UX2_DATA',json.dumps(results))
