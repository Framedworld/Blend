"""Collect final, already executed reference-pass acceptance evidence."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'
files={
    'reference_data':'sculpt_reference_data_results.json',
    'native_ui_100':'sculpt_reference_gui_scale100.json',
    'native_ui_125':'sculpt_reference_gui_scale125.json',
    'native_ui_150':'sculpt_reference_gui_scale150.json',
    'sculpt_data':'zbrush_sculpt_results.json',
    'brush_memory':'sculpt_ux2_data_results.json',
    'sculpt_gui':'zbrush_sculpt_gui_results.json',
    'workspace_gui':'sculpt_ux2_gui_results_reference_final.json',
    'maya_controls':'controls_gui_results.json',
    'channel_stability':'channel_stability_gui_results.json',
    'cursor_grid_zoom':'sculpt_feedback_gui_results.json',
}
results={}
for name,file in files.items():
    value=json.loads((OUT/file).read_text(encoding='utf-8'))
    results[name]={'file':file,'passed':len(value['passed']),'failed':value['failed']}
    if value['failed'] or not value['passed']:raise RuntimeError(name+' did not pass')
    if name.startswith('native_ui'):
        if not value.get('ok'):raise RuntimeError(name+' did not finish')
        results[name].update(dpr=value['qt_dpr'],window_sizes=value['window_sizes'])
dense=json.loads((OUT/'zbrush_density_results.json').read_text())
if not dense['ok']:raise RuntimeError('Dense Multires check failed')
gallery=json.loads((OUT/'sculpt_reference_gallery_results.json').read_text())
if gallery['errors'] or not all(all(v for k,v in c.items() if k!='name') for c in gallery['checks']):raise RuntimeError('Gallery failed')
sources=['sculpt/extended.py','sculpt/instances.py','sculpt/ops.py','sculpt/layout.py','ui/sculpt_tray.py','ui/zbrush_panel.py']
report={'ok':True,'engine':'Blender 5.2.2 LTS / native PySide6',
        'suites':results,'dense_multires':dense,'gallery':gallery,
        'full_window_gpu_visual_acceptance':'BLOCKED - existing factory Blender capture issue',
        'exact_zbrush_parity':False,
        'boundaries':'SCULPT_FEATURE_MAP.md',
        'source_sha256':{s:hashlib.sha256((ROOT/'landfall_studio'/s).read_bytes()).hexdigest() for s in sources}}
startup=json.loads((OUT/'interactive_startup.json').read_text())
if not (startup.get('ok') and startup.get('sculpt_active') and startup.get('qt_binding')=='PySide6'):raise RuntimeError('Interactive demo did not verify')
report['interactive_startup']=startup
(OUT/'sculpt_reference_acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({name:r['passed'] for name,r in results.items()}))
