"""Review viewer for supplied screenshots and actual native Qt captures."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output';inputs=OUT/'sculpt-reference-input';inputs.mkdir(exist_ok=True)
names=['SubTool','Geometry','ArrayMesh','NanoMesh','Layers','Deformation','Masking','PolyGroups','Morph Target','Polypaint']
ids=['b840eb1c-cb3b-49cf-a574-8bbce6ba339a','4b8e5816-69ab-4eac-b2db-89bb933fc7e7','50c6cb14-5cbe-4c8b-a7fa-4ce316b3d129','0238b034-a120-4d2e-bc65-06e46f5ba0c0','273e3a27-504f-4275-ba20-8ed12b9249ca','2cfb9b87-8fc4-4ab5-afbf-68093f91906a','c187b92e-43c3-42e1-ad79-476c3e849c99','86c491bf-8c59-4797-b7b3-36df3a727675','f5910fb5-7ea2-4a93-a8f4-1729a8c8c3c5','11183d6a-16c0-40d5-bc25-452013289a66']
for name,id in zip(names,ids):
    source=Path('C:/Users/mattk/AppData/Local/Temp')/('codex-clipboard-'+id+'.png')
    if source.exists():shutil.copy2(source,inputs/(name.replace(' ','-')+'.png'))
html='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Sculpt Studio · Native reference pass</title><style>
*{box-sizing:border-box}body{margin:0;background:#1b1e22;color:#d8dce2;font:15px system-ui}header{padding:28px 36px;border-bottom:1px solid #383d45}h1{font-size:26px;margin:0 0 8px}p{color:#aeb5bf;max-width:950px;line-height:1.55}a{color:#e9a754}nav{display:flex;flex-wrap:wrap;gap:7px;padding:20px 36px}button{background:#33363b;color:#ddd;border:1px solid #4b5057;border-radius:4px;padding:8px 14px;cursor:pointer}button[aria-selected=true]{background:#85551f;border-color:#e19a48}.pair{display:none;max-width:1120px;margin:0 auto;padding:0 28px 40px;gap:28px;grid-template-columns:1fr 1.4fr}.pair.active{display:grid}.figure{padding:18px;background:#25282d;border:1px solid #3b4047;border-radius:8px;align-self:start}.figure h2{font-size:16px;margin:0 0 16px;color:#e7b278}.figure img{display:block;max-width:100%;width:auto;height:auto;margin:auto}footer{padding:20px 36px;border-top:1px solid #383d45;color:#9da5b0;font-size:13px}@media(max-width:700px){.pair{grid-template-columns:1fr}}
</style><header><h1>LANDFALL / SCULPT STUDIO</h1><p>Reference-led native Tool tray. Compare the supplied ZBrush images with actual PySide6 widget captures. Crossed-out sections are excluded. Captures demonstrate appearance; Blender runs the tools. This review viewer contains no sculpt engine.</p><a href="SCULPT_FEATURE_MAP.md">Feature map and documented differences</a> · <a href="SCULPT_REFERENCE_PASS.md">Validation report</a></header><nav>'''
for i,name in enumerate(names):html+=f'<button data-index="{i}" aria-selected="{str(i==1).lower()}">{name}</button>'
html+='</nav>'
for i,name in enumerate(names):
    file=name.replace(' ','-')+'.png'
    html+=f'<section class="pair {"active" if i==1 else ""}" data-index="{i}"><div class="figure"><h2>Supplied reference · {name}</h2><img src="sculpt-reference-input/{file}" alt="Supplied {name} reference"></div><div class="figure"><h2>Native Landfall PySide6 · {name}</h2><img src="sculpt-reference/{file}" alt="Actual native {name} widget capture"></div></section>'
html+='''<footer>Native controls use the existing Blender scene, dispatcher, keymap and Qt application. Unsupported proprietary functions are explained in the feature map and disabled tooltips. Whole-window GPU capture limitations remain separate from these native Qt images.</footer><script>document.querySelectorAll('button[data-index]').forEach(b=>b.onclick=()=>{document.querySelectorAll('button[data-index]').forEach(x=>x.setAttribute('aria-selected',String(x===b)));document.querySelectorAll('.pair').forEach(x=>x.classList.toggle('active',x.dataset.index===b.dataset.index))})</script></html>'''
(OUT/'sculpt-reference-gallery.html').write_text(html,encoding='utf-8')
