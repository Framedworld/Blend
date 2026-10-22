# Native sculpt tray layout

Use the [comparison gallery](sculpt-reference-gallery.html) for actual widget
images and the [feature map](SCULPT_FEATURE_MAP.md) for operation semantics.

| Element | Native specification |
|---|---|
| Dock | 320 logical pixels; fits within the existing right dock owner, including its edge strip |
| Outer padding | Left/right 5 px, top 3 px, bottom 8 px; palette gap 3 px |
| Palette body | 5 px inset, 2 px control gaps; nested palettes use 3 px insets |
| Buttons | 26 px height; paired equal-width controls; long labels use a full row |
| Embedded values | 44 px block, 52 px numeric field above a compact slider with an 18–22 px pen target; no horizontal scrolling |
| SubTool icons | Actual local mesh projection, 48 × 44 px; selected item retains name and visibility checkbox |
| Background | Outer `#292C30`; palette `#303236`; button `#3B3E42` |
| Text | `#CDD0D4`; disabled `#72767B` |
| Selected state | Amber `#E78B20`, dark text `#191C20` |
| Sliders | Groove `#44474C`, fill `#95612F`, handle `#C48C4C` |
| Expand behavior | SubTool stays open; one main palette at a time; Shift-click retains additional palettes |
| Small windows | Below 1100 logical window pixels, the tray becomes a 36 px drawer; the tray toggle reopens the full controls |
| Window resize | Restore intended logical shelf/tray sizes after Blender scales native editor fractions |
| Return | Restore the modeling dock arrangement through the existing lifecycle |

The numeric editor owns its text inset so inherited host styles cannot collapse
the value area. Native palette images are captured at actual Qt DPR 1.00, 1.25
and 1.50. Window sizes and measured tray geometry are recorded in the GUI result
files; whole-window GPU screenshot acceptance remains separate.

Interaction specification: [pen UX pass](SCULPT_PEN_UX.md).
