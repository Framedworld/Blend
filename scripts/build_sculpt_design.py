"""Create original shared brush artwork and the editable UI reference."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'landfall_studio/assets/sculpt'
ASSETS.mkdir(parents=True,exist_ok=True)
STROKES={
    'ST':('Standard','M15 49 Q31 12 49 33 T81 24'),
    'CB':('ClayBuildup','M17 50 L29 22 M28 53 L41 22 M40 53 L53 23 M52 50 L65 22 M64 49 L77 21'),
    'CL':('Clay','M17 47 Q35 19 50 34 T79 27'),
    'CR':('Crease','M17 49 L42 28 L53 46 L78 22'),
    'MV':('Move','M15 43 C34 53 30 8 55 29 L77 28 M65 18 L78 28 L67 40'),
    'MT':('Move Topological','M16 43 C29 62 41 17 55 29 L78 28 M65 18 L78 28 L67 40'),
    'DS':('DamStandard','M16 49 Q38 18 49 36 T79 24'),
    'TD':('TrimDynamic','M15 50 L34 27 L58 27 L80 15 M24 51 L41 35 L67 35'),
    'HP':('hPolish','M18 49 L33 30 L73 30 M25 49 L77 49'),
    'IN':('Inflate','M17 47 Q47 -2 79 46'),
    'PI':('Pinch','M17 23 Q47 50 79 23 M17 50 Q47 23 79 50'),
    'SH':('SnakeHook','M18 48 C60 68 70 5 49 22 C32 36 71 44 79 18'),
    'SM':('Smooth','M17 38 Q32 21 47 38 T79 38 M23 49 Q47 36 72 49'),
    'MP':('MaskPen','M19 47 L31 24 L75 24 L64 47 Z'),
    'IM':('IMM Primitives','M18 28 L31 20 L44 28 L44 45 L31 53 L18 45 Z M57 26 A14 14 0 1 1 57 54 A14 14 0 1 1 57 26'),
}
for code,(name,path) in STROKES.items():
    width=10 if code in ('ST','CB','CL','IN') else (3 if code in ('DS','CR','PI') else 5)
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="96" height="72" viewBox="0 0 96 72"><defs><radialGradient id="g"><stop stop-color="#555a61"/><stop offset="1" stop-color="#22262c"/></radialGradient><filter id="s"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#060709"/></filter></defs><rect width="96" height="72" rx="7" fill="#20242a"/><ellipse cx="48" cy="37" rx="39" ry="29" fill="url(#g)"/><path d="{path}" stroke="#e5b589" stroke-width="{width}" fill="{'#a87545' if code=='MP' else 'none'}" stroke-linecap="round" stroke-linejoin="round" filter="url(#s)"/><path d="{path}" stroke="#ffe0bc" stroke-opacity=".4" stroke-width="1.2" fill="none"/></svg>'''
    (ASSETS/(code+'.svg')).write_text(svg,encoding='utf-8')
print('Original brush artwork:',len(STROKES))
design=ROOT/'output/sculpt-design/assets';(design/'brushes').mkdir(parents=True,exist_ok=True)
for image in ASSETS.glob('*.svg'):shutil.copyfile(image,design/'brushes'/image.name)
for source,name in [('zbrush_demo_window.png','creature-scene.png'),('zbrush_silhouette.png','silhouette.png')]:
    if (ROOT/'output'/source).exists():shutil.copyfile(ROOT/'output'/source,design/name)
