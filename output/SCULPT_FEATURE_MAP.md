# Sculpt Studio reference feature map

This pass uses the ten supplied screenshots as the layout reference. Red-crossed
sections are excluded. A grey control in a screenshot was still included in this
audit. The tray is native PySide6, using the existing command/keymap/dock owners.

**Native** means Blender supplies the operation or data model. **Adapted** means
the visible workflow is implemented using a different algorithm. **Boundary**
means the exact reference feature is not implemented; it must not be advertised
as one-to-one parity. No enabled button is a visual-only prototype.

## SubTool

| Reference controls | Implementation / status |
|---|---|
| Visible Count, mesh list, eye, List All | Native object list with mesh thumbnails; viewport count controls list height, not object visibility. Alphabetical List All popup. |
| V1–V8 | Scene-persistent visibility sets; click recalls, Shift-click stores. |
| New Folder, arrows, Rename, AutoReorder | Tagged native collections, explicit saved ordering, selection navigation; AutoReorder uses polygon count. |
| All Low / All High | Native Multires levels for every SubTool. |
| All To Home / Target | Stored object matrices; Geometry/Stager supplies the store controls. |
| Copy / Paste / Duplicate | Independent mesh datablocks and generated helper IDs; Copy retains an unlinked clipboard object in the blend. Recovery snapshots retain independent placements. |
| Append / Insert | Primitive picker; Append creates a SubTool, Insert joins geometry. Insert protects shape keys/skin data by requiring Append. |
| Delete / Del Other / Del All | Recovery copies retained; Del All leaves an editable empty target. |
| Split | Native mask slice, plus groups, hidden faces and connected parts on staged targets. |
| Merge | Evaluated copies joined into a new SubTool; originals retained. |
| Boolean | Live native Exact Boolean with chosen operand; Make Boolean Mesh creates the evaluated sculpt copy. |
| Project | Nearest-surface Shrinkwrap to an explicit source. Adapted; not ZBrush iterative detail transfer. |
| Extract | Native sculpt mask extraction and Solidify thickness. |

Excluded here: Bevel Pro, Align, Distribute, Remesh, Project BasRelief.
Source: [Maxon SubTool reference](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/subtool/subtool.html).

## Geometry

| Reference controls | Implementation / status |
|---|---|
| Lower/Higher Res, SDiv, Cage, Rstr, Del Lower/Higher | Native Multires; existing staged delete-lower reconstruction retained. Cage toggles cage display; Rstr uses base-mesh sculpting. |
| Freeze SubDivision | Adapted snapshot → low base → reconstructed levels plus projection modifier. It preserves the original high detail, but requires inspection/Make Mesh rather than ZBrush's automatic reproject transaction. |
| Reconstruct / Rebuild Subdiv | Native Multires Unsubdivide / Rebuild. Valid quad topology is required. |
| Divide / Smt / Suv | Native Catmull-Clark or Simple subdivision, with UV smoothing choice. |
| Convert BPR To Geo | Boundary: no BPR render primitives in Blender. Disabled with explanation; generated Blender geometry uses Make Mesh. |
| ReUV | Boundary: no equivalent subdivision-time switch. Existing UVs are preserved; unwrap through Blender's UV editor. |
| Dynamic Subdiv | Native Subsurf preview, level control and staged Apply. |
| EdgeLoop / Group Loops | Adapted open-boundary subdivision and bevel around Face Set boundaries. Does not reproduce ZBrush panel-loop generation. |
| Crease | Native crease-edge attribute, using group borders/open edges; Uncrease All. |
| ClayPolish | Adapted boundary-aware smoothing; no claim of the proprietary ClayPolish algorithm. |
| DynaMesh / ZRemesher | Existing native voxel remesh / QuadriFlow and settings. Different algorithms. |
| Modify Topology | BMesh delete hidden, weld, triangulate/quads, unweld group borders, flip and close holes. Protected sources are staged. |
| Stager | Scene-persistent Home/Target matrices. |

Excluded here: ShadowBox, Tessimate, Position, Size, MeshIntegrity.
Source: [Maxon Geometry reference](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/geometry/geometry.html).

## ArrayMesh

| Reference controls | Implementation / status |
|---|---|
| Presets / Open / Save | Native adapter JSON presets; proprietary ZAR files are not supported. |
| Array Mesh, Repeat | Reversible native Array modifiers. Count includes the original. Local child offsets follow object/group transforms; changing settings retains the Curve path and artist modifier order. |
| Transpose | Floating transform inspector; edits the native offset object. No ZBrush Action Line. |
| Transform Stage, Append/Insert, Reset/Delete, Copy/Paste | Saved stages and native modifier stack. Insert follows the current stage. |
| SwitchXY/XZ/YZ | Swaps local transform components. Adapted from working-plane switching. |
| Offset / Scale / Rotate / Pivot, XYZ Amount | Native object-offset matrix. Amounts are per repetition; ZBrush's final-instance amounts/profile curves differ. |
| Smooth | Native Smooth modifier on the generated surface, not inter-stage path interpolation. |
| Pattern Start/On/Off | Geometry Nodes island visibility pattern; assumes a connected source. |
| AlignToPath | Native Curve modifier, explicitly selected curve. |
| XYZ Mirror | Signed scale per stage. |
| Make Mesh | Evaluated sculptable copy; original stack retained. |
| Convert To NanoMesh | Adapted: uses a copied source on the target's existing faces; it does not generate ZBrush placement polygons from each array instance. |
| Extrude | Labeled Extrude/Weld: merges coincident native array vertices. Arbitrary group-cap bridging, Close and Angle are boundaries. |
| Lock Pos/Size, Chain, Pattern Length, AlignToAxis, XYZ Align/Profile | Boundaries in this pass. The native offset/pivot/curve controls cover useful alternatives, but these exact ZBrush stage/path/profile constraints are not implemented. |

Source: [Maxon ArrayMesh reference](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/array-mesh/array-mesh.html).

## NanoMesh

| Reference controls | Implementation / status |
|---|---|
| Source preview/selector, On, arrows/Index | Native source mesh selector and persistent per-target index inventory. Geometry Nodes instances use face centers/tiles. |
| Hide Others | Only the current index remains visible; other configured indexes are retained. |
| Copy/Paste, Edit Mesh / Placement | Copy index settings; source editing returns through Return Placement. Edit Placement enters native mesh Edit Mode. |
| Split Screen | Native second viewport; shared Blender selection/mode remains global. Not independent ZBrush document halves. |
| Show Instances / Placement, Freeze | Node output toggles and preserved placement points. Local parented placements follow object/group transforms, including frozen previews and independent copies. |
| Prop / Fit / Fill / Const | Proportional/constant source scale or face-size fitting/filling. Non-quad shapes use approximate local dimensions. |
| Clip | Boundary: no per-face clipping of overlapping instance geometry. Disabled with explanation. |
| Size, Width/Length/Height, offsets, rotations, variation | Deterministic transforms in native point attributes consumed by Geometry Nodes. |
| Flip H/V, H/V Tile, Pattern, Random Distribution/Seed/RandArray | Grid/diamond tiling, mirrors, deterministic density and randomization. |
| Alignment | Normal, face-edge frame or none. Short/long/near/random-edge variants are boundaries. |
| Colorize / Uv | Source colors/materials/UVs survive instancing. Per-index MRGB, modulation by base color, texture projection and UV rebinding remain boundaries. |
| Inventory | Add index, delete index, realize one or all to mesh. ZBrush All-to-Brush/IMM asset interchange remains a boundary; choose another source to replace an index. |

Source: [Maxon NanoMesh reference](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/nanomesh/nanomesh.html).

## Layers

| Reference controls | Implementation / status |
|---|---|
| List / intensity / New / REC | Existing native relative shape keys and base-resolution recording, shared with the exact Maya Shape Editor target. |
| Move, Name, Duplicate, Delete, Merge Down, Invert | Native key ordering/name/data with indexed geometry preservation. |
| Split | Labeled Split XYZ: splits geometry displacement into axis layers. ZBrush mixed shape/color/mask layer splitting is a boundary. |
| Bake Current / Bake All | Current-weight deltas baked to base; recovery kept. |
| Import MDD, Speed, Record Deformation Animation | Fixed-point-count MDD import to animated shape samples and scene-range evaluated MDD export. Speed retimes imported channels. |
| Color/mask recording | Boundary: those remain shared native mesh attributes, not independently recorded layers. |

Source: [Maxon Layers reference](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/layers/layers.html).

## Deformation

| Reference controls | Implementation / status |
|---|---|
| Unify / Mirror / ReSym / Smart ReSym | Indexed vertex transformations; symmetry can use stored Morph Target correspondence. Spatial fallback is approximate, not topology-based poseable symmetry inference. |
| Polish / By Features / By Groups / Crisp / Relax | Native dense sculpt filters; adapted base-mesh smoothing/border protection. |
| Relax Plane Grid / Morph to Grid | Adapted flattening/grid snap at base level. |
| Offset / Rotate / Size / Bend / SBend / Skew / SSkew | Mask-weighted base-coordinate deformations on selected axes. |
| RFlatten / Flatten / SFlatten / Twist / Taper / Squeeze | Adapted local-space deformations, preserved vertex indexing. |
| Noise / Smooth / Contrast / Inflate / Balloon / Spherize / Gravity / Perspective | Native dense filters where available; masked base equivalents otherwise. Exact proprietary variants are not claimed. |
| Repeat Active / Other / Folder / Mask | Reuses operation, amount, axes and mask preference across targets. |

Dense Multires supports its native filter subset. Other operations require base
resolution rather than silently deforming an unrelated surface.
Source: [Maxon Deformation reference](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/deformation/deformation.html).

## Masking

| Reference controls | Implementation / status |
|---|---|
| ViewMask / Inverse / Clear / MaskAll | Native overlay and mask operators. |
| Blur/Sharpen/Grow/Shrink/Boost/Dilute | Native sculpt mask filters. |
| Changed Points | Distance from StoreMT. |
| Flip/Mirror By Poseable Symmetry | Stored-rest-target index mapping, otherwise spatial matching; not automatic posed-topology inference. |
| Create Alpha | Packed XY mask projection image; not a filled silhouette rasterizer. |
| MaskByFeature / Border / Groups / Crease | Mesh boundaries, Face Set borders and crease attributes. |
| Draft / angle / SetDir / InvDir | Normal-direction threshold; view direction or selected axis. |
| Go To Unmasked Center | Native 3D cursor to unmasked centroid. |
| Adjust / Fibers / AO / Cavity / Depth / Normals / Smoothness / PeaksAndValleys / Color / Alpha | Native cavity, deterministic ray AO, axis/root-tip, curvature, color distance and texture sampling. Fibers expects converted mesh islands; no FiberMesh engine. |
| Apply | Each generation/filter button applies directly; threshold/quality values are saved settings. |

Source: [Maxon Masking reference](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/masking/masking.html).

## PolyGroups

| Reference controls | Implementation / status |
|---|---|
| Auto / UV / Auto With UV | Native Face Sets from connectivity or actual UV islands. |
| Merge Similar / Stray | Adapted color similarity and small-group adjacency merging. |
| Regroup Edges / sensitivity / Normals / angle | Native sharp-edge grouping and explicit angular normal clustering. |
| Visible / ReGroupVisible / Front | Visible/front face assignment into real Face Sets. |
| Masked / Clear Mask / From Masking | Real mask thresholds to Face Sets. |
| As DynaMesh Sub | Boundary: signed voxel subtraction by Face Set is unavailable. Disabled with an explanation pointing to SubTool Boolean Subtract and Make Boolean Mesh. |
| From Polypaint / tolerances | Color bins and mask thresholds. |
| Coverage / cluster / additive / PolishG / changed-points groups | Boundaries in this pass; use group creation and Deformation controls separately. |

Sources: [Maxon PolyGroups](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/polygroups/polygroups.html), [Blender Face Sets](https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/editing/face_sets.html).

## Morph Target

StoreMT uses a separate persistent point-vector attribute, not an extra user
layer. Switch exchanges positions; DelMT removes the snapshot; Morph and per-axis
sliders blend to it; MorphDist uses normalized displacement. CreateDiff Mesh
creates a delta-vector mesh copy, not ZBrush's shell-difference algorithm. Project
Morph uses a chosen-source Shrinkwrap modifier. Base topology must match.
Source: [Maxon Morph Target](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/morph-target/morph-target.html).

## Polypaint

Colorize displays mesh color attributes; Grd affects Fill Color. Texture transfer
samples an active UV map/image; group colors use deterministic colors; adjustments
respect masks. Symmetry uses stored rest correspondence or spatial fallback.
Draft colors use normals and a chosen direction. Thickness colors use bounded
inward ray sampling; Quality controls sample count, with min/max remapping. These
are native attribute workflows with adapted algorithms, not ZBrush paint storage
or its exact thickness/symmetry algorithms. Native RGB brush painting remains
available in the header overflow.
Source: [Maxon Polypaint](https://help.maxon.net/zbr/en-us/Content/html/reference-guide/tool/polymesh/polypaint/polypaint.html).

## Safety and acceptance

Linked/rigged/keyed/Multires topology changes preserve a staged source and recovery
copy. Native strokes and tablet pressure retain their existing engine. New
geometry commands use the existing Blender undo owner, including native Sculpt
undo nodes for custom vertex changes. Test results and native captures are
recorded separately; this feature map is not a declaration of exact ZBrush parity.

Array/NanoMesh edits insert a native global-history checkpoint before changing
modifiers. This fixes one-step command Undo after Sculpt-node edits in Blender
5.2; it can leave an extra unchanged checkpoint when continuing further back
through history. No replacement stroke engine or parallel undo stack is used.

## Insert Multi Mesh (IMM) — 2026-10-22

| Reference behavior | Implementation / status |
|---|---|
| Drag an IMM part onto the surface | Native: the IMM brush places the current part centred on the hit, its +Z on the surface normal, largest extent set by the drag radius (a click uses the brush size). Live circle preview while dragging. |
| Part library / create InsertMesh from a SubTool | Adapted: primitives plus any mesh in the hidden **IMM Parts** collection; *Add Active SubTool as Part* copies the SubTool into it. Blender asset-library parts are a natural next step. |
| Choose the part | Click empty canvas with the IMM brush; a drag there still orbits. |
| Insert into the current SubTool with auto-masking | Native: picker → *Insert into Current SubTool* joins the part, masks the existing surface and gives the part its own polygroup (Face Set); DynaMesh then fuses it. With subdivision levels, layers or Sculptris Pro active it inserts as a new SubTool and says why (ZBrush also blocks topology changes there). |
| Undo | One native Undo removes the insert; brush, part and dials are tool state and survive Undo/Redo. |

Evidence: `test_imm_headless.py` 6/6, `test_imm_gui.py` 18/18, `test_imm_undo_gui.py` 5/5 (hidden-desktop native events; undo also confirmed on screen).
