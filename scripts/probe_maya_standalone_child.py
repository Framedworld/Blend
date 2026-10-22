"""Disposable mayapy diagnostic. No Studio imports or user-scene changes."""
import ctypes
import faulthandler
import json
import os
from pathlib import Path
import sys

faulthandler.enable()
ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
root = Path(sys.executable).resolve().parent.parent
if str(root/'Python/Lib/site-packages') not in sys.path:
    sys.path.append(str(root/'Python/Lib/site-packages'))
print(json.dumps({'stage':'interpreter_ready','python':sys.version,
    'executable':sys.executable,'isolated':sys.flags.isolated,
    'no_site':sys.flags.no_site,'studio_imported':any(n.startswith('landfall_studio') for n in sys.modules)}), flush=True)
_dll_search = None
if '--dll-directory' in sys.argv:
    _dll_search = os.add_dll_directory(str(root/'bin'))
    print('MAYA_BIN_DLL_DIRECTORY_RETAINED', flush=True)
print('IMPORTING_MAYA_STANDALONE', flush=True)
import maya.standalone
print('MAYA_STANDALONE_IMPORTED', flush=True)
maya.standalone.initialize(name='python')
print('MAYA_STANDALONE_INITIALIZED', flush=True)
import maya.cmds as cmds
print(json.dumps({'stage':'maya_ready','version':cmds.about(version=True),
                  'batch':cmds.about(batch=True)}), flush=True)
maya.standalone.uninitialize()
print('MAYA_STANDALONE_UNINITIALIZED', flush=True)
