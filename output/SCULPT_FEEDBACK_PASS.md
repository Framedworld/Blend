# Sculpt feedback and Channel Box corrections

Alt-click-release zoom now pulls in when dragging away from the model and pulls
out when pushing toward it. The dedicated Zoom tool and Maya navigation keep
their existing direction.

Sculpt entry hides finite, infinite, orthographic grids and axes. Floor remains
optional, including after deferred upstream startup synchronization. GoZ restores
the exact preceding grid/axis state. No global preference is written.

The hover cursor has rings and a small center crosshair. A held native brush
stroke hides the rings and tracks the actual tip with the crosshair. Native paint
consumes mouse motion, so drawing reads the Windows pointer in the originating
viewport without moving it. The native paint engine still owns strokes and undo.

Native viewport images, inspected for grid/cursor appearance:

- [Hover](sculpt_feedback_hover.png)
- [Held native stroke](sculpt_feedback_held.png)
- [Released](sculpt_feedback_released.png)

The editable prototype and its three desktop references use a fresh grid-free
capture of the same creature demo. Browser interactions also demonstrate the
hover/held/released cursor and optional grid.

Channel Box live updates retain the existing Qt cells and selected channels when
only values change. Selection, filters, locks, connections and channel definitions
still use the blendertk rebuild. SHAPES/INPUTS/layer sections refresh only when
their displayed data changes, retaining collapsed INPUTS during movement. The
right dock keeps its geometry cache so unchanged bounds do not force a Windows
child-window reposition on each transform update.

Popup follow-up: Qt menus keep their own native grab; sculpt popup ownership is
established before showing. Tentacle's optional background menu warm-up pauses
while Sculpt owns input or a Qt popup is active. Its suppressed full-screen
realization could otherwise deactivate a live popup. The queued warm-up resumes
after returning to Maya. Explicit native keyboard focus remains on sculpt frames.

Validation:

- 13 native sculpt feedback GUI checks passed, including live native brush motion,
  first entry/reentry grid defaults, optional grid and exact Maya grid restoration.
- 93 sculpt GUI and 77 sculpt data regressions passed.
- 15 browser prototype checks passed, with no page errors.
- 13 Channel Box GUI checks passed: real native move changes geometry position
  while preserving Qt item identity, model, channel selection and INPUTS expansion.
  Lock changes, target switching and two-way value edits remain functional.
- 44 second-pass workspace GUI checks passed at actual Qt DPR 1.25, including
  popup synchronization, focus-loss rollback, first stroke placement and repeated
  exact dock/keymap restoration. The earlier 1.00/1.50 matrix remains baseline.
- 71 Maya GUI checks passed after the shared desktop/focus changes.

The native shortcut fixture now moves the physical pointer back into its source
viewport after the menu hover check. This keeps real Windows hover focus aligned
with simulated viewport input. Intermediate focus failures and probe logs are
retained in `channel_*results.json`; final regressions use the original assertions.

The previous full-window desktop GPU capture limitation remains separate from
these internal native viewport images. See [second-pass report](SCULPT_UX_PASS2.md).

Fresh updated interactive demo left open: PID 9764. `interactive_startup.json`
confirms PySide6/Tentacle active, Sculpt Studio active, one viewport bar and three
SubTools. A separate desktop process check confirms responsiveness. Artist source
files were not saved or overwritten by these disposable checks or the launcher.
