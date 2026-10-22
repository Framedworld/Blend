"""Shared native-test bootstrap: fresh UITK stores before any Studio objects.

Use as the first --python argument, before a native test script. Production
startup/settings behavior is unchanged. The existing upstream TestSandbox owns
the redirection; this file verifies it and records the actual live backend.
"""
import json
import os
from pathlib import Path
import sys
import time

import bpy

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent
OUT=Path(os.environ['LANDFALL_UI_ISOLATION_REPORT'])
os.environ['QT_API']='pyside6'
for relative in ('.deps/py313','upstream/pythontk','upstream/uitk'):
    sys.path.insert(0,str(WORKSPACE/relative))
from uitk.testing import TestSandbox
from qtpy import QtCore

stores=TestSandbox.activate()
sys.path.insert(0,str(ROOT))
from landfall_studio.sculpt import preferences
preferences.PATH=OUT.parent/'sculpt_preferences.json'
preferences._data=None
preferences.recent.clear()
report={'ok':False,'pid':os.getpid(),'background':bpy.app.background,
        'activated_at':time.time(),'settings_roots':[str(path) for path in stores],
        'sculpt_preferences':str(preferences.PATH),
        'actual_switchboard_verified':False}


def save():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')


def local(path):
    return Path(path).resolve().is_relative_to(WORKSPACE/'.test_env')


try:
    if not TestSandbox.is_active() or not all(local(path) for path in stores):
        raise RuntimeError('Native test stores are not isolated under the workspace test root')
    probe=QtCore.QSettings('LandfallStudioTesting','isolation')
    if probe.format()!=QtCore.QSettings.IniFormat or not local(probe.fileName()):
        raise RuntimeError('Test QSettings probe would use a shared/nonlocal store')
    probe.setValue('pid',os.getpid())
    probe.sync()
    if int(probe.value('pid'))!=os.getpid():
        raise RuntimeError('Local QSettings round trip failed')
    report.update(ok=True,probe_file=probe.fileName(),guard_class=QtCore.QSettings.__name__)
    save()
except Exception as exc:
    report['error']=str(exc)
    save()
    raise


def observe_switchboard():
    module=sys.modules.get('landfall_studio.adapters.tentacle_bridge')
    host=module.get_tcl_instance() if module else None
    if host is None:
        return .1
    try:
        settings=host.sb.settings.settings
        valid=TestSandbox.is_active() and settings.format()==QtCore.QSettings.IniFormat and local(settings.fileName())
        report.update(ok=bool(valid),actual_switchboard_verified=bool(valid),
                      switchboard_file=settings.fileName(),verified_at=time.time(),
                      active_sculpt_preferences=str(preferences.PATH))
        if not local(preferences.PATH):
            valid=False
            report.update(ok=False,actual_switchboard_verified=False)
        save()
        if not valid:
            raise RuntimeError('Live Switchboard bypassed the native test settings sandbox')
    except Exception as exc:
        report.update(ok=False,error=str(exc))
        save()
        raise
    return None


if not bpy.app.background:
    bpy.app.timers.register(observe_switchboard,first_interval=.1,persistent=True)
