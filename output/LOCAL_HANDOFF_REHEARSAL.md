# Local handoff rehearsal — 2026-10-17

Historical runtime snapshot: the later generated-asset/command round changes
eight production files. Its current-source validation is tracked separately in
[INSTANCE_LIFECYCLE_REVIEW.md](INSTANCE_LIFECYCLE_REVIEW.md). The relocation
evidence below is retained for its original source/copy hashes.

**PASS: 24/24 modeling checks and 27/27 sculpt/fresh-process checks**, actual Qt
DPR **1.25**. [Current acceptance](local_handoff_acceptance.json).
Both native Blender processes exit normally, with complete results, matching
process IDs, no missing required stages and callback/crash-clean logs.

This adds local relocation evidence on unchanged product code. It complements
the [multi-scale UX review](FULL_UX_REVIEW.md) and
[continuous artist session](CONTINUOUS_ARTIST_SESSION.md); it does not certify
a clean machine, physical input or a distributed installer.

Fresh independent review: **8/10, integrated and worthwhile**, no material
blocker in the tested relocated workflows. It verified all 5,665 source/copy
hashes and current runner/observer hashes at acceptance. The guide was clarified
afterward; that documentation-only change is recorded separately in
[local_handoff_documentation_followup.json](local_handoff_documentation_followup.json).

## What was checked

- Physically copy **5,665 runtime, dependency, license and launch files**
  (**723,418,262 bytes**) to a disposable folder with spaces and Unicode:
  `.test_env/Friend Handoff Élan Ω 20261017T051056Z`. No Git histories,
  original profiles, artist assets or prior results are copied.
- Verify every copied file against its original SHA-256. All original runtime
  input hashes still match after execution; no installer or download is used.
- Run the copied Windows launcher's real `-CheckOnly` path, verifying its returned
  workspace is the exact Unicode copy and Blender is 5.2.2 LTS.
- Start the unchanged copied `open_studio.py` entry point in native Blender,
  adding a separate test observer. Run modeling and creature sculpt-demo startup
  in distinct processes with isolated Blender resources and fresh Qt settings.
- Verify actual Studio, upstream, PySide6, Shiboken, Pillow, QtPy and packaging
  module origins inside the copy; verify the real viewport widgets are visible.
- Type an Attribute Editor transform, Undo/Redo through native viewport keys,
  operate the real Sculpt/favorite/Return buttons, and verify native state.
- Create a local project and a real external PNG, load it as an **unpacked FILE
  image**, assign it through a material, save/reopen and decode its pixels.
  The image path remains relative and resolves to the copied project.
- In the second fresh process, first start the creature demo, return to modeling,
  then open the first process's saved project. Verify the external texture,
  controls and modeling/sculpt handoff again. Its saved source scene is unchanged
  by the second process's unsaved edits.

Project/image setup and file saves/loads use production APIs. Typed edits,
native Undo/Redo and mode/favorite buttons use real synthetic input. The
`.cmd` files are copied and hash-verified; this does not claim a physical
double-click of them. Startup uses the production entry point plus the explicit
observer, rather than a test replacement for the desktop.

## Fresh settings and retained diagnostics

The first 22/25 native result established path relocation, but only Blender's
profile had been isolated. UITK also uses shared Windows QSettings and preset
stores. That earlier aggregate's `original_profile_used=false` field was too
broad and **must not support a fresh-Qt or no-shared-store claim**. It is retained
under `local-handoff/20261017T051241Z/`; the current stronger result supersedes it.

The corrected observer activates the existing **UITK TestSandbox** before
Studio's startup timer constructs Switchboard. Each process asserts the test
guard is active, both settings/preset roots resolve inside the fixture, and the
actual Switchboard QSettings uses local **INI** storage. Windows may show an
8.3 `FRIEND~2` alias; its resolved path is checked against the Unicode fixture.
This is test instrumentation, not a change to production settings behavior.
Earlier GUI suites are not retroactively claimed to have fresh Qt stores.
The ordinary production launcher does not make every UITK setting workspace-local;
some tool-window settings remain per Windows user. The friend guide now states
that distinction explicitly.

The runtime copy is reused only after all source/destination hashes are verified
and files are confirmed to be independent copies. Its previous test-only profile
is archived inside the fixture after checking both resolved absolute paths;
nothing is recursively deleted. The first two harness-only console encoding
failures are also retained. Diagnostic output now handles the Windows OEM
PowerShell stream without changing the real Unicode path.

Logs contain Qt deprecation warnings, brush-append notices and a few small native
shutdown memory diagnostics. They are callback/crash-clean, not warning-free.

## Reproduce and remaining gates

```powershell
python .\Blend\scripts\check_local_handoff.py
```

Use an ordinary external Python with standard-library support; this script does
not install packages. It launches two disposable native Blender sessions and
writes timestamped manifests/results/logs under `Blend/output/local-handoff/`.

Still required: actual friend-machine startup/dependency/asset-path testing,
physical pen/mouse and mixed-monitor feel, successful external Maya round trip,
full GPU-window visual capture and redistribution/dependency-license packaging.
The [Maya isolation diagnosis](MAYA_RUNTIME_DIAGNOSIS.md) now locates the observed
native import crash in `mayaLib0.dll`; it does not identify or perform a repair.
