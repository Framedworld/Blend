# Maya runtime isolation — 2026-10-17

**External Maya interchange remains BLOCKED.** Three fresh disposable `mayapy`
processes reproduce `0xC0000005` while importing `maya.standalone`, before
`initialize()` runs and without importing Studio. This narrows the failure to
the native Maya runtime/dependency boundary; it does not identify a specific
repair or prove the installation is corrupt.

[Probe report](maya_standalone_diagnostic.json) and
[matching Windows fault records](maya-standalone-diagnostic/20261017T050433Z_windows_faults.json).

| Case | Result |
|---|---|
| Ordinary interpreter, local disposable Maya preferences | `0xC0000005`, standalone not imported |
| Python `-I -S`, no user/site Python setup | Same failure |
| Minimal child environment, Maya location/bin path, retained DLL-directory handle, Python `-I -S` | Same failure |

All three Windows Application Error records name the installed
`C:\Program Files\Autodesk\Maya2024\bin\mayaLib0.dll`, fault offset `0x1067`.
The interpreter reaches its ready marker; the next marker is importing
standalone, and the native access violation occurs there. Maya reports version
`24.0.0.4640` for the installed executable, using Python 3.10.8.

The minimal case follows Autodesk's documented Maya location/bin environment
setup, applied only to that child process. Autodesk documents importing and
initializing standalone as separate steps; initialization is never reached in
these probes. Sources: [standalone Windows environment](https://help.autodesk.com/cloudhelp/2023/CHS/Maya-SDK/files/Running-Standalone-Applications/Maya_SDK_Running_Standalone_Applications_RunOnWindows_html.html),
[Python outside Maya](https://help.autodesk.com/cloudhelp/2022/CHS/Maya-SDK/Maya-Python-API/PythonOutsideMayaSession.html).

No global environment, registry, Maya preferences, installation files, source
assets or running artist session was changed. No installer or download was
started. Each subprocess has a 30-second bound and its own local profile/temp.
The diagnostic imports no Blender/Qt/Studio code. This does not prove every
possible system conflict is absent; it shows that removing Studio and inherited
Python/site paths does not resolve the observed native failure.

Studio already presents discovered Maya as **Detected**, with a tooltip saying
successful conversion still requires initialization. Existing failure reporting
and staged-file protections remain. No speculative product workaround was added.
Successful `.ma`/`.mb` conversion still requires a working native Maya runtime,
followed by the actual interchange and round-trip acceptance suite.

Reproduce the bounded diagnosis with the workspace's ordinary external Python:

```powershell
python .\Blend\scripts\probe_maya_standalone.py
```

The probe intentionally returns exit 1 when no case initializes. That is a
BLOCKED runtime result, not passing interchange acceptance. Keep the JSON, three
native logs and matching Windows records when arranging Maya runtime repair.

## Native Maya ASCII route — 2026-10-22

Studio now reads and writes Maya ASCII geometry itself
(`landfall_studio/interchange/maya_ascii.py`), so `.ma` files no longer depend on
this runtime. **File → Import / Export → Maya ASCII (.ma, native)** covers the
transform hierarchy (translate/rotate/scale/rotate order/visibility), polygon
meshes (`.vt`, `.pt` tweaks, `.ed` hard/soft, `.fc` polyFaces), the default UV
set, Maya Y-up and file units. Shear from non-uniform parent scale is baked into
the shape so world positions match. Meshes that exist only as construction
history are reported as skipped, never imported empty. `.mb`, shaders, skinning
and animation still need a working Maya runtime.

When no runtime is detected, the existing Import/Save As Maya Scene commands use
this route for `.ma` and say so in their report. When a detected runtime fails
(this machine), the failure is reported unchanged with a hint to use the native
command; Studio never silently substitutes a reduced-fidelity file.
Evidence: `tests/test_maya_ascii_headless.py` 8/8 (Maya-format polyCube, history,
hierarchy/tweaks/rotate order, Blender→.ma→Blender world-space round trip with
UVs and hard edges); bridge contract suite 18/18 unchanged.
