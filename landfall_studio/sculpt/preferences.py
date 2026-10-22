"""Workspace-local UI choices; never writes Blender's global preferences."""
import json,os
from pathlib import Path

PATH=Path(__file__).resolve().parents[3]/'.landfall_studio/sculpt_ui.json'
DEFAULT_FAVORITES=('ST','CB','MV','DS','TD','HP','IN','PI')
_data=None
recent=[]

def get():
    global _data
    if _data is None:
        _data={'version':1,'favorites':list(DEFAULT_FAVORITES),'palette':'Geometry','pinned_palettes':[],'tray_collapsed':None}
        try:
            saved=json.loads(PATH.read_text(encoding='utf-8'))
            if saved.get('version')==1:
                from .brushes import CATALOG
                _data.update(favorites=list(dict.fromkeys(c for c in saved.get('favorites',DEFAULT_FAVORITES) if c in CATALOG)),
                    palette=str(saved.get('palette','Geometry')),pinned_palettes=list(saved.get('pinned_palettes',[])))
                if saved.get('tray_collapsed') in (True,False):_data['tray_collapsed']=saved['tray_collapsed']
        except (OSError,ValueError,TypeError):pass
    return _data

def save():
    PATH.parent.mkdir(parents=True,exist_ok=True)
    tmp=PATH.with_suffix('.tmp');tmp.write_text(json.dumps(get(),indent=2),encoding='utf-8');os.replace(tmp,PATH)

def favorite(code,enabled=None):
    values=get()['favorites'];enabled=code not in values if enabled is None else enabled
    if enabled and code not in values:values.append(code)
    elif not enabled and code in values:values.remove(code)
    save()

def reorder(code,index):
    values=get()['favorites']
    if code in values:values.remove(code);values.insert(max(0,min(len(values),index)),code);save()

def remember(code):
    if code in recent:recent.remove(code)
    recent.insert(0,code);del recent[3:]
