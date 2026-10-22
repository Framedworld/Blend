**8/10 for the implemented Studio-owned workflows. Highest gate: integrated and worthwhile.** This does not certify the full replacement goal.

Prior directives:

- **LANDED:** Array/Nano geometry follows translation, rotation, scaling and parenting. Renaming preserves ownership; copied and frozen SubTools remain independent.
- **LANDED:** Curve paths and artist modifier ordering survive settings changes. Legacy helpers migrate on Sculpt entry. Clipboard and recovery snapshots preserve generated placements.
- **LANDED:** Studio Duplicate/Instance, Maya Ctrl+D, Qt Ctrl+D and Repeat share the canonical native operation, with correct mesh sharing and single-step Undo.
- **LANDED:** Text-origin keys remain owned by editors during parent propagation. Both GoZ return routes have one native boundary; undoing the next modeling edit retains modeling mode.
- **NOT DONE:** Raw Blender Shift+D/F3 duplicate routes still bypass that dependency isolation.

I independently verified [final acceptance](C:/Users/mattk/Documents/Landfall/Blend/output/instance_lifecycle_acceptance.json): **15/15 suites, 1,046 checks**, fresh results, normal exits and no traceback/access-violation markers. All **140 source hashes** match. Eleven GUI processes verified actual isolated Switchboard backends; three background guards and the Blender-only control remain correctly distinguished.

The actual layer GoZ test proves one Undo returns directly to the Sculpt tray, one Redo restores the exact Shape Editor target, and subsequent modeling Undo preserves complete layer arrays. Current 1280-pixel panel captures have readable controls; these are panel captures, not whole-window GPU certification.

No material blocker remains within the tested Studio-owned routes. Remaining recommendations:

1. Close the raw Shift+D/F3 duplication bypass while preserving native move/cancel semantics.
2. Test repeated stage deletion, clipboard replacement and recovery restoration before certifying helper retirement across long sessions.
3. Validate the new input routes at 100% and 150% scaling, then complete physical-pen, friend-machine and external-Maya gates separately.
