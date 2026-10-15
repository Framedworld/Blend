# Landfall Studio — Blender Native Feature Continuity Map (Gate 09)

This document catalogs how **Landfall Studio** (`v0.9.0`) bridges Maya muscle-memory workflows with **Blender 5.2's native features**, guaranteeing that every shadowed Blender shortcut has a conflict-free fallback chord and that native Blender editors and modes (`Geometry Nodes`, `Shader Editor / Hypershade`, `UV Editor`, `Graph Editor`, `Dope Sheet`, `Asset Browser`, `Sculpt Mode`, and `Grease Pencil`) remain 100% accessible and keymap-safe.

---

## 1. Viewport 2.0 Display & Shading Continuity (`4 / 5 / 6 / 7` + `Alt+Z`)

| Maya Shortcut / UI Control | Maya Meaning | Blender 5.2 Mapping (`landfall_studio.viewport_shading`) | Top Viewport 2.0 Strip Pill |
| :--- | :--- | :--- | :--- |
| **`4`** | Wireframe Display | `space.shading.type = "WIREFRAME"` | `Wire [4]` |
| **`5`** | Smooth Shaded (Default Lighting) | `space.shading.type = "SOLID"`, `light = "STUDIO"`, `color_type = "MATERIAL"` | `Shaded [5]` |
| **`6`** | Shaded & Textured (Hardware Texturing) | `space.shading.type = "MATERIAL"` (`use_scene_lights = False`) with fallback to `SOLID` + `TEXTURE` | `Textured [6]` |
| **`7`** | Use All Scene Lights | `space.shading.type = "MATERIAL"`, `use_scene_lights = True` (or `RENDERED`) | `All Lights [7]` |
| **`Alt+Z`** | Toggle X-Ray / Shading | Toggles `space.shading.show_xray` (`mode="XRAY"`) | `X-Ray [Alt+Z]` |
| **Display Marking Menu (`RMB > Display`)** | Wireframe on Shaded / Isolate / Borders | Toggles `overlay.show_wireframes` + active `obj.show_wire`, `landfall.isolate`, and border edge highlights | `Wire on Shaded` |

---

## 2. Maya Soft Selection (`B`) ↔ Blender Proportional Editing (`O`)

| Maya Interaction | Studio Operator / Widget | Synchronized Blender RNA State |
| :--- | :--- | :--- |
| **Tap `B`** in 3D Viewport | `landfall_studio.soft_selection(action="MODAL_OR_TOGGLE")` | Toggles `scene.tool_settings.use_proportional_edit` **and** `use_proportional_edit_objects` |
| **Hold `B` + LMB-Drag** in 3D Viewport | `landfall_studio.soft_selection` modal falloff ring | Interactively resizes `scene.tool_settings.proportional_size` while drawing a 3-ring concentric Maya heatmap falloff indicator (`#EF3D38` → `#F5852E` → `#FAD142`) in `POST_PIXEL` HUD |
| **Tap `O`** (Blender Native) | Native Blender Proportional Editing | Remains active and synced two-way with Top Status Line `◎ Soft [B]`, Left Tool Box Rail `B` button, and Right `Tool Settings` panel |
| **Left Tool Box Rail `B` Button** | `MayaLeftSidebarWidget.btn_soft_rail` | Toggles Soft Selection and illuminates left `#F0A830` amber indicator bar |
| **Right Dock `Tool Settings` (`SOFT SELECTION (B)`)** | `MayaToolSettingsWidget` | Edits `Enable`, `Falloff Radius`, and `Falloff Curve` (`SMOOTH`, `SPHERE`, `ROOT`, `INVERSE_SQUARE`, `SHARP`, `LINEAR`) |

---

## 3. Shadowed Blender Shortcuts & Conflict-Free Fallback Chords (`MAYA` Profile)

| Maya Key (`MAYA` Profile) | Maya Studio Action | Shadowed Stock Blender Action | Conflict-Free Fallback Chord / Access Path |
| :--- | :--- | :--- | :--- |
| **`Hold Space`** | Maya Hotbox / Tentacle Switchboard | Play Animation (`screen.animation_play`) / Search | **`Alt+V`** (Play Animation) \| **`F3`** (Operator Search) |
| **`Q`** | Select Tool (`landfall_studio.select_tool` `SELECT`) | Quick Favorites (`SCREEN_MT_user_menu`) | **`Ctrl+Shift+Q`** (`wm.call_menu` `SCREEN_MT_user_menu`) |
| **`W / E / R`** | Move (`W`), Rotate (`E`), Scale (`R`) Persistent Manipulators | Context Menu (`W`), Extrude (`E`), Rotate (`R`) | **`Ctrl+E`** (`landfall.extrude`) \| **`Shift+RMB`** (Modeling Tool Marking Menu) \| **`HYBRID`** Profile (`G/R/S`) |
| **`G / Y`** | Repeat Last Command (`G`) / Select Last Tool (`Y`) | Translate Modal (`G`) / Split Selection (`Y`) | **`W`** (Move Manipulator) \| **`Shift+RMB > Detach / Separate`** |
| **`1 / 2 / 3`** | Smooth Mesh Preview: Base (`1`), Cage+Smooth (`2`), Smooth (`3`) | Edit Mesh Vertex/Edge/Face (`1/2/3`) & Collection Visibility | **`F9 / F10 / F11 / F12`** (`landfall_studio.component_mode`) \| **`RMB`** Marking Menu \| Top Status Line **`MASK`** Pills |
| **`4 / 5 / 6 / 7`** | Viewport 2.0 Shading: Wireframe (`4`), Shaded (`5`), Textured (`6`), All Lights (`7`) | Collection Visibility `4–7` | **`Alt+Z`** (X-Ray) \| Left/Right **Display Layers (`V/T/R`)** |
| **`B`** | Soft Selection Toggle & Hold `B` + LMB Falloff Radius Ring | Box Select (`view3d.select_box`) | **`O`** (Proportional Editing) \| Standard LMB Marquee Drag in `Q/W/E/R` |
| **`F`** | Frame Selected (`landfall.frame_selected`) | Make Edge/Face (`mesh.edge_face_add` in Edit Mesh) | **`Shift+F`** (`mesh.edge_face_add` in `Mesh` Edit Mode) \| Native **`F`** Brush Size preserved in Sculpt & Paint |
| **`A` / `Ctrl+A`** | Frame All (`A`) / Cycle Channel Box & Attribute Editor (`Ctrl+A`) | Select All (`A`) / Apply Transforms Menu (`Ctrl+A`) | **`Ctrl+Shift+A`** (`landfall_studio.select_all_toggle`) \| **`RMB > Select All`** \| **Freeze Transformations** |
| **`Hold X / C / V`** | Temporary Snap: Grid (`X`), Curve/Edge (`C`), Vertex (`V`) | Delete Menu (`X`), Circle Select (`C`), Rip (`V`) | **`Delete`** or **`BackSpace`** (`landfall_studio.smart_delete`) |

---

## 4. Native Blender Editors & Modes Bridge (`FX / Nodes` Shelf & Marking Menu)

| Native Blender Feature | Studio Bridge Target (`landfall_studio.native_bridge`) | Maya UI Entry Points | Protected Context Guarantee |
| :--- | :--- | :--- | :--- |
| **Geometry Nodes** | `GEOMETRY_NODES` (`ensure_geometry_nodes_on_active`) | Top Menu Set `FX [F5]` → **`FX / Nodes`** Shelf (`Geo Nodes` tile) & `RMB` / `Shift+RMB` Marking Menu | `Node Editor` keymap is in `PROTECTED_KEYMAP_NAMES` (`0` Studio overrides) |
| **Shader Editor / Hypershade** | `SHADER_EDITOR` (`ShaderNodeTree` + `Hypershade` Dock) | Top Status Line `Hypershade`, `UV & Shading` Shelf, `FX / Nodes` Shelf (`Shader Ed`) | `Node Editor` keymap is 100% protected |
| **UV Editor** | `UV_EDITOR` (`F12` UV Component Sync) | Top Status Line `MASK > UV`, `UV & Shading` Shelf, `FX / Nodes` Shelf (`UV Editor`) | UV Editor shortcuts untouched |
| **Graph Editor & Dope Sheet** | `GRAPH_EDITOR` / `DOPE_SHEET` | `FX / Nodes` Shelf (`Graph Ed`, `Dope Sheet`) + Bottom Time Slider / Range Slider | Animation channel editors untouched |
| **Asset Browser** | `ASSET_BROWSER` | `FX / Nodes` Shelf (`Assets`) | Asset Browser keymap untouched |
| **Sculpt Mode** | `SCULPT_MODE` (`bpy.ops.object.mode_set(mode="SCULPT")`) | `FX / Nodes` Shelf (`Sculpt`) & `RMB` / `Shift+RMB` Marking Menu | `Sculpt` keymap is in `PROTECTED_KEYMAP_NAMES` — native `F` (Brush Size) and `Shift+F` (Brush Strength) work natively |
| **Grease Pencil (v3)** | `GREASE_PENCIL` (Creates/activates `mayaGreasePencil1`) | `FX / Nodes` Shelf (`Grease Pcl`) & `RMB` / `Shift+RMB` Marking Menu | `Grease Pencil Edit Mode` & `Grease Pencil Stroke Sculpt Mode` keymaps are in `PROTECTED_KEYMAP_NAMES` |
