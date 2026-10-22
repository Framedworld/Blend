"""Compare ordinary, isolated and minimal child environments for installed Maya.

Changes apply only to disposable subprocesses. No installs, registry, profile or
artist files are changed; initialization may create its isolated local prefs.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
MAYA = Path(r'C:\Program Files\Autodesk\Maya2024')
CHILD = ROOT/'scripts/probe_maya_standalone_child.py'
OUT = ROOT/'output/maya-standalone-diagnostic'
OUT.mkdir(parents=True, exist_ok=True)
tag = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
local = WORKSPACE/'.test_env'/('maya_environment_'+tag)
local.mkdir(parents=True, exist_ok=True)
report = {'generated':tag, 'scope':__doc__, 'cases':[],
          'source_sha256':{str(p.relative_to(WORKSPACE)):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (Path(__file__),CHILD)}}


def environment(minimal=False):
    inherited = dict(os.environ)
    if minimal:
        keep = {'SYSTEMROOT','WINDIR','SYSTEMDRIVE','COMSPEC','PROGRAMFILES','PROGRAMFILES(X86)',
                'PROGRAMDATA','COMMONPROGRAMFILES','COMMONPROGRAMFILES(X86)',
                'USERPROFILE','APPDATA','LOCALAPPDATA','USERNAME','USERDOMAIN',
                'PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS'}
        inherited = {k:v for k,v in inherited.items() if k.upper() in keep}
        inherited['PATH'] = os.pathsep.join((str(MAYA/'bin'),
            str(Path(os.environ['SystemRoot'])/'System32'),os.environ['SystemRoot']))
    inherited.update(TEMP=str(local), TMP=str(local), MAYA_APP_DIR=str(local/'maya'),
        MAYA_SKIP_USERSETUP_PY='1', MAYA_DISABLE_CIP='1', MAYA_DISABLE_CER='1',
        MAYA_DISABLE_CLIC_IPM='1', PYTHONNOUSERSITE='1')
    if minimal:
        inherited['MAYA_LOCATION'] = str(MAYA)
    return inherited


for name, flags, args, minimal in (
    ('ordinary',[],[],False),
    ('isolated_python',['-I','-S'],[],False),
    ('minimal_documented_environment',['-I','-S'],['--dll-directory'],True),
):
    log = OUT/(tag+'_'+name+'.log')
    command = [str(MAYA/'bin/mayapy.exe'),*flags,str(CHILD),*args]
    entry = {'name':name,'command':command,'log':str(log),'timeout':False}
    try:
        run = subprocess.run(command, env=environment(minimal), cwd=str(local),
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW)
        output = run.stdout.decode('utf-8',errors='replace')
        entry.update(exit=run.returncode,exit_hex=hex(run.returncode & 0xffffffff),
            initialized='MAYA_STANDALONE_INITIALIZED' in output,
            imported='MAYA_STANDALONE_IMPORTED' in output)
    except subprocess.TimeoutExpired as exc:
        output=(exc.stdout or b'').decode('utf-8',errors='replace')
        entry.update(timeout=True, initialized=False, imported=False)
    log.write_text(output,encoding='utf-8')
    report['cases'].append(entry)
    print(json.dumps(entry),flush=True)
    (OUT/(tag+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')

report['any_initialized'] = any(c['initialized'] for c in report['cases'])
report['production_changed'] = False
(OUT/(tag+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
(ROOT/'output/maya_standalone_diagnostic.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
sys.exit(0 if report['any_initialized'] else 1)
