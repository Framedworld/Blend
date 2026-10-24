LANDFALL STUDIO BETA: READ ME FIRST
====================================

Thanks for testing. Landfall Studio is Maya-style modeling and ZBrush-style
sculpting in one program, built on Blender 5.2 (included; your own Blender, if
you have one, is not touched).


INSTALLING
----------
1. Run LandfallStudioSetup-<version>.exe.
2. Windows may say "Windows protected your PC". The beta is not code-signed yet.
   Click "More info", then "Run anyway".
3. Click Install. No administrator rights are needed; it installs for your
   Windows account only and takes about a minute.

Needs Windows 10 or 11 (64-bit) and a graphics card that supports OpenGL 4.3,
which covers most from 2014 onward. A pen tablet is recommended for sculpting.


STARTING
--------
Start menu > Landfall Studio:
  Landfall Studio    modeling, the Maya way
  Landfall Sculpt    opens the sculpting studio with a demo creature
  Report a Problem   saves a report to your Desktop (see below)

The first start can take up to a minute while a small window says "Starting...".
Later starts are faster.


FIRST FIVE MINUTES: MODELING
----------------------------
Q / W / E / R           select / move / rotate / scale
Alt + left/mid/right    orbit / pan / zoom
F / A                   frame selection / frame all
F8 / F9 / F10 / F11     object / vertices / edges / faces
1 / 2 / 3               smooth preview
4 / 5 / 6 / 7           wireframe / shaded / textured / lit
Ctrl+D                  duplicate      Ctrl+G  group
Ctrl+E                  extrude        G       repeat last command
Z / Shift+Z             undo / redo    Hold Space  hotbox
Ctrl+S / Ctrl+O         save / open

Help > Studio Controls lists everything inside the program.


FIRST FIVE MINUTES: SCULPTING
-----------------------------
Q / W / E / R           draw / move / scale / rotate
B, then two letters     choose a brush (B S T = Standard)
S / U / O               draw size / Z intensity / focal shift
Shift / Ctrl            smooth / mask
Ctrl+Shift              hide and show parts
Space                   quick controls
Tab                     hide or show the shelves
GoZ Return              back to modeling


SAVING AND GETTING WORK BACK
----------------------------
Save early as a .blend file and press Ctrl+S often.
If Studio closes unexpectedly, start it again and choose
File > Recover > Auto Save (saved every 2 minutes) or File > Recover > Last Session.


REPORTING A PROBLEM
-------------------
If Studio closes unexpectedly it offers to save a problem report. You can also
use Help > Report a Problem inside Studio, or Start menu > Landfall Studio >
Report a Problem.

The report is a zip on your Desktop with logs and system details. It does not
include your scene. Send it to the person who invited you to the beta, with a
few words on what you were doing. A screenshot helps a lot too.

Things we would most like to hear about:
  - anything a Maya or ZBrush habit made you expect that did not happen
  - anything that felt slow, confusing or hard to find
  - crashes, and what you did just before


KNOWN LIMITS IN THIS BETA
-------------------------
- Maya files: .ma (Maya ASCII) geometry opens and saves without Maya
  (File > Import / Export). .mb files, shaders and rigs need Maya installed.
- Pen pressure has been tested with simulated input; real tablet feel is one of
  the things we want your feedback on.
- There is no automatic update yet. To update, run the newer installer; it
  replaces the old version and keeps your settings.


UNINSTALLING
------------
Start menu > Landfall Studio > Uninstall Landfall Studio, or Windows Settings >
Apps > Installed apps > Landfall Studio. Your own .blend files are never removed.
