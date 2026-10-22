"""Local relocation fixture; does not build or distribute a release package.

Copy only runtime packages, licenses and launch files to a disposable path with
spaces/Unicode. Use the copied launcher preflight and unchanged production entry
point plus a separate native test observer. No artist scene or profile is used.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent
BLENDER=Path(os.environ.get('LANDFALL_BLENDER_EXE',r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'))
OBSERVER=ROOT/'tests/test_local_handoff_gui.py'
tag=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
prepared=None
if len(sys.argv)>1:
    if len(sys.argv)!=3 or sys.argv[1]!='--prepared-report':
        raise SystemExit('Usage: check_local_handoff.py [--prepared-report prior_acceptance.json]')
    prepared_path=Path(sys.argv[2]).resolve()
    if not prepared_path.is_relative_to(ROOT/'output/local-handoff'):
        raise SystemExit('Prepared report must belong to this local test runner')
    prepared=json.loads(prepared_path.read_text(encoding='utf-8'))
COPY=Path(prepared['copy']).resolve() if prepared else WORKSPACE/'.test_env'/('Friend Handoff Élan Ω '+tag)
if not COPY.is_relative_to(WORKSPACE/'.test_env') or not COPY.name.startswith('Friend Handoff '):
    raise SystemExit('Prepared fixture escaped the intended local test directory')
EVIDENCE=ROOT/'output/local-handoff'/tag
COPY.mkdir(parents=True,exist_ok=bool(prepared))
EVIDENCE.mkdir(parents=True)
report={'generated':tag,'ok':False,'scope':__doc__,'copy':str(COPY),'runs':[]}
manifest={}


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def copy_file(source,dest):
    source,dest=Path(source),Path(dest)
    if not dest.resolve().is_relative_to(COPY):
        raise RuntimeError('Relocation destination escaped the test fixture')
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,dest)
    digest=sha(source)
    if digest!=sha(dest):
        raise RuntimeError('Copied file hash mismatch: '+str(dest))
    manifest[str(source.relative_to(WORKSPACE))]={'sha256':digest,'bytes':source.stat().st_size}
    return str(dest)


def copy_tree(relative):
    source=WORKSPACE/relative
    shutil.copytree(source,COPY/relative,copy_function=copy_file,
                    ignore=shutil.ignore_patterns('__pycache__','.git','*.pyc'))


def save():
    (EVIDENCE/'acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (ROOT/'output/local_handoff_acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


try:
    if prepared:
        manifest_path=Path(prepared['copy_manifest']).resolve()
        if not manifest_path.is_relative_to(ROOT/'output/local-handoff') or sha(manifest_path)!=prepared['copy_manifest_sha256']:
            raise RuntimeError('Prepared copy manifest is not intact')
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        for relative,entry in manifest.items():
            source,dest=WORKSPACE/relative,COPY/relative
            if not source.resolve().is_relative_to(WORKSPACE) or not dest.resolve().is_relative_to(COPY):
                raise RuntimeError('Prepared manifest path escaped its allowed roots')
            if source.samefile(dest) or sha(source)!=entry['sha256'] or sha(dest)!=entry['sha256']:
                raise RuntimeError('Prepared runtime content is not an intact independent copy')
        profile=COPY/'.landfall_studio'
        if profile.exists():
            archive=COPY/('.previous-test-profile-'+tag)
            # Move only this runner's disposable profile, preserving evidence.
            # Both resolved absolute targets must remain immediate children of
            # the already-validated fixture root. No cross-shell file commands.
            if profile.is_symlink() or profile.resolve().parent!=COPY or archive.resolve().parent!=COPY:
                raise RuntimeError('Disposable profile archive escaped the fixture')
            profile.rename(archive)
            report['archived_previous_test_profile']=str(archive)
        report['reused_prepared_report']=str(prepared_path)
    else:
        copy_tree(Path('Blend/landfall_studio'))
        copy_tree(Path('.deps/py313'))
        for name in ('tentacle','blendertk','uitk','pythontk'):
            copy_tree(Path('upstream')/name/name)
            for filename in ('LICENSE','COPYING.LESSER','pyproject.toml'):
                source=WORKSPACE/'upstream'/name/filename
                if source.is_file():
                    copy_file(source,COPY/source.relative_to(WORKSPACE))
        for relative in ('upstream/landfall/__init__.py','upstream/landfall/blender_manifest.toml','upstream/landfall/LICENSE',
                         'Blend/scripts/launch_studio.ps1','Blend/scripts/open_studio.py',
                         'Blend/output/FRIEND_QUICK_START.md','Open Landfall Studio.cmd','Open Landfall Sculpt Studio.cmd'):
            copy_file(WORKSPACE/relative,COPY/relative)
    manifest_path=EVIDENCE/'copy_manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    report.update(copied_files=len(manifest),copied_bytes=sum(f['bytes'] for f in manifest.values()),
                  copy_manifest=str(manifest_path),copy_manifest_sha256=sha(manifest_path),
                  observer_sha256=sha(OBSERVER),runner_sha256=sha(Path(__file__)))
    # A Windows parent console may use cp1252 even when filesystem/argv fully
    # support Unicode. Keep diagnostic transport ASCII-safe without altering
    # the real Unicode fixture path.
    print(json.dumps({'relocated_fixture':str(COPY),'files':len(manifest)}),flush=True)
    base_env=dict(os.environ)
    for name in ('PYTHONPATH','PYTHONHOME','LANDFALL_WORKFLOW_SCULPT_ONLY'):
        base_env.pop(name,None)
    base_env.update(LANDFALL_STUDIO_UPSTREAM_ROOT=str(COPY/'upstream'),
        LANDFALL_STUDIO_DEPS=str(COPY/'.deps/py313'),TENTACLE_QT_DEPS=str(COPY/'.deps/py313'),
        LANDFALL_HANDOFF_COPY=str(COPY),QT_API='pyside6')
    preflight=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(COPY/'Blend/scripts/launch_studio.ps1'),'-CheckOnly','-BlenderPath',str(BLENDER)],
        cwd=COPY,env=base_env,capture_output=True,timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW)
    preflight_text=(preflight.stdout+preflight.stderr).decode('oem',errors='replace')
    (EVIDENCE/'launcher_preflight.log').write_text(preflight_text,encoding='utf-8')
    launch_data=json.loads(preflight.stdout.decode('oem')) if preflight.returncode==0 else {}
    launch_ok=preflight.returncode==0 and launch_data.get('ok') and Path(launch_data['workspace']).resolve()==COPY and launch_data.get('installs_or_downloads') is False
    report['launcher_preflight']={'ok':bool(launch_ok),'exit':preflight.returncode,
                                  'log':str(EVIDENCE/'launcher_preflight.log'),'result':launch_data}
    if not launch_ok:
        raise RuntimeError('Copied launcher preflight failed')
    critical={'unmodified copied entry point becomes ready',
        'shared Qt settings use fresh local test stores','Switchboard uses relocated INI settings',
        'every Studio and Qt module comes from the relocated copy',
        'native PySide6 is the shared binding',
        'typed inspector edit works from the copied runtime',
        'copied runtime keeps native inspector Undo','copied runtime keeps native inspector Redo',
        'reopened texture is relative and resolves inside the copied project',
        'external texture actually decodes after reopen',
        'copied saved-scene Sculpt button enters the actual workspace',
        'copied favorite activates its native subtractive brush',
        'copied scene returns to the modeling workspace'}
    for mode in ('modeling','sculpt'):
        result_path=EVIDENCE/(mode+'.json')
        log_path=EVIDENCE/(mode+'.log')
        env=dict(base_env)
        temp=COPY/'.landfall_studio'/mode/'temp'
        temp.mkdir(parents=True)
        env.update(BLENDER_USER_RESOURCES=str(temp.parent/'blender'),TEMP=str(temp),TMP=str(temp),
                   LANDFALL_HANDOFF_RESULT=str(result_path),LANDFALL_HANDOFF_MODE=mode)
        args=[str(BLENDER),'--factory-startup','--enable-event-simulate','--python-exit-code','1',
              '--python',str(COPY/'Blend/scripts/open_studio.py'),'--python',str(OBSERVER)]
        if mode=='sculpt':
            args+=['--','--sculpt-demo']
        scene=COPY/'Artist Project Élan/handoff scene Ω.blend'
        original_scene=sha(scene) if mode=='sculpt' and scene.is_file() else None
        with log_path.open('wb') as log:
            process=subprocess.Popen(args,cwd=COPY,env=env,stdout=log,stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                code=process.wait(timeout=150)
            except subprocess.TimeoutExpired:
                process.kill()  # Only this owned disposable child, never an artist process.
                code=process.wait()
        data=json.loads(result_path.read_text(encoding='utf-8')) if result_path.is_file() else {}
        content=log_path.read_text(encoding='utf-8',errors='replace')
        missing=sorted(critical-set(data.get('passed',[])))
        clean=not any(s in content for s in ('Traceback (most recent call last)','EXCEPTION_ACCESS_VIOLATION','[Sculpt pen UI] RuntimeError'))
        scene_preserved=original_scene is None or (scene.is_file() and sha(scene)==original_scene)
        passed=code==0 and data.get('pid')==process.pid and data.get('ok') and data.get('completed') and not data.get('failed') and not missing and clean and scene_preserved
        entry={'mode':mode,'ok':bool(passed),'pid':process.pid,'exit':code,
               'passed':len(data.get('passed',[])),'failed':data.get('failed',[]),
               'missing_required_stages':missing,'clean_log':clean,'scene_source_preserved':scene_preserved,
               'result':str(result_path),'log':str(log_path),'dpr':data.get('dpr')}
        report['runs'].append(entry)
        print(json.dumps(entry),flush=True)
        save()
        if not passed:
            raise RuntimeError(mode+' relocated native workflow failed')
    changes=[relative for relative,entry in manifest.items() if sha(WORKSPACE/relative)!=entry['sha256']]
    report.update(original_sources_unchanged=not changes,source_changes=changes,
                  blender_profile_isolated=True,qt_settings_isolated=True,distributed=False,
                  ok=not changes and all(r['ok'] for r in report['runs']))
except Exception as exc:
    report['error']=str(exc)
    print(json.dumps({'LOCAL_HANDOFF_FAILED':str(exc)}),flush=True)
finally:
    save()
sys.exit(0 if report['ok'] else 1)
