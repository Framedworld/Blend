# Sculpt Studio implementation

The supplied GoZ Studio plan is the acceptance checklist. Implement within Studio's
existing Qt desktop, keymap owner and native Blender scene; do not install Bbrush
or introduce another QApplication/event pump.

1. Probe Blender 5.2 RNA and bundled brush assets. Add persistent sculpt settings,
   configured brush catalog, shared operators and protected topology staging.
2. Add scoped sculpt bindings through the existing profile owner and a raycast
   pen dispatcher. Exercise actual native strokes and GUI input events.
3. Add real PySide6 sculpt header, brush palette, tool tray and canvas buttons.
   Detect mode changes from any entry point and restore the previous desktop.
4. Add current-view silhouette, brush rings, gesture bounds and shortcut overlay.
5. Verify scene semantics headlessly and Qt/native input in an isolated GUI;
   document unsupported or approximate behavior separately from passing checks.

Reference inspected: AIGODLIKE/Bbrush master README, sculpt lifecycle and manifest
(version 1.5.1, GPL-3.0-or-later). Implementation is original; no Bbrush code is
vendored. Blender 5.2 RNA is authoritative where the request uses older enum names
(hide_show uses `Inside`, not `INSIDE`, and has no `ALL` area).
