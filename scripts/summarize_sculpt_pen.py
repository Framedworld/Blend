"""Summarize executed native UI scenarios; do not promote physical pen acceptance."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
files={
 'pen_100':'sculpt_pen_gui_scale100.json','pen_125':'sculpt_pen_gui_scale125.json','pen_150':'sculpt_pen_gui_scale150.json',
 'sculpt':'zbrush_sculpt_gui_results.json','workspace':'sculpt_ux2_gui_results_pen.json',
 'maya_controls':'controls_gui_results.json','channel_stability':'channel_stability_gui_results.json',
 'cursor_grid_zoom':'sculpt_feedback_gui_results.json','reference_sidebar':'sculpt_reference_gui_pen.json'}
results={}
for name,file in files.items():
 data=json.loads((OUT/file).read_text(encoding='utf-8'))
 if data['failed'] or not data['passed']:raise RuntimeError(name+' failed')
 if name.startswith('pen_') and (len(data['passed'])!=47 or not data.get('ok')):raise RuntimeError(name+' final run unfinished')
 results[name]={'file':file,'passed':len(data['passed']),'failed':0}
 if name.startswith('pen_'):results[name].update(dpr=data['dpr'],input=data['input'],event_errors=data['pointer_errors'])
paths=['ui/sculpt_input.py','ui/hotkey_passthrough.py','ui/sculpt_tray.py','ui/sculpt_widgets.py','ui/zbrush_panel.py','ui/viewport_bar.py','sculpt/layout.py','viewport/sculpt_hud.py']
report={'ok':True,'suites':results,'source_sha256':{p:hashlib.sha256((ROOT/'landfall_studio'/p).read_bytes()).hexdigest() for p in paths},
 'independent_review':'Read-only code review; no actionable findings. No physical-device or GUI review by the reviewer.',
 'physical_tablet_acceptance':'UNVERIFIED - synthetic tablet events do not measure driver delivery or physical feel',
 'whole_window_gpu_visual_acceptance':'BLOCKED - existing factory Blender presentation/capture issue',
 'behavior_reference':'SCULPT_PEN_UX.md'}
(OUT/'sculpt_pen_acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({name:data['passed'] for name,data in results.items()}))
