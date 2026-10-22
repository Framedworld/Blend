# Sculpt reference pass

Deliver a native PySide6 tray organized like the ten supplied ZBrush palettes,
with working Blender equivalents, persistent scene settings and an explicit
feature map. Crossed-out SubTool sections (Bevel Pro, Align, Distribute, Remesh,
Project BasRelief) and Geometry sections (ShadowBox, Tessimate, Position, Size,
MeshIntegrity) are excluded. Grey reference controls are included in the audit;
grey does not mean crossed out.

1. Research: compare Maxon's reference semantics with installed Blender 5.2 RNA;
   record native, adapted and unavailable boundaries per control.
2. Native commands: extend the existing sculpt dispatcher for SubTool organization,
   geometry, arrays/surface instances, masks/groups, deformations, morphs, colors
   and layer management. Preserve native strokes and protected source data.
3. Tray: compact paired buttons, embedded value sliders, axis toggles, nested
   collapsible sections and persistent selection. Retain Landfall slate/amber.
4. Verify actual geometry/attributes/modifiers, Undo, save/reopen, native Qt actions,
   scrolling, scale/width behavior and previous Sculpt/Maya regressions. Capture
   each palette from actual Qt widgets; record any unsatisfied acceptance honestly.

| Palette | Blender foundation |
|---|---|
| SubTool | Mesh objects, collections, scene visibility sets, native Multires, Boolean/Shrinkwrap/Solidify |
| Geometry | Multires Unsubdivide/Rebuild, Subsurf, crease attributes, remesh/QuadriFlow, BMesh |
| ArrayMesh | Array + object offset transforms, editable stages, evaluated make-mesh |
| NanoMesh | Geometry Nodes instance-on-face placement, source objects, realized copies |
| Layers | Shape keys with exact base-index preservation, MDD point-cache interchange |
| Deformation | Native sculpt filters, masked vertex deformations, Simple Deform equivalents |
| Masking | Native mask filters/cavity plus attribute, normal, ray and connectivity masks |
| PolyGroups | Native sculpt Face Sets; UV, crease, normal, color and mask grouping |
| Morph Target | Stored shape data, indexed switching, blending and delta mesh |
| Polypaint | Mesh color attributes, native Paint brush/color filters and sampled colors |

Reference semantics: Maxon Tool/Polymesh reference pages for the ten named
palettes. API evidence: `sculpt_native_capabilities.json`. Existing full-window
GPU desktop capture limitation remains separate from actual Qt palette captures.
