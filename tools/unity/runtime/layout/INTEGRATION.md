# Layout model entry points for gameplay workers

The touch path below is wired into the lab runtime; the separate recovered HUD
scale/group editor remains an authored host model. Device acceptance is separate.

1. Supply a `LayoutProjection(width, height, left, top, right, bottom)` from actual
   display/safe-area observations. All coordinates here use top-left, x-right,
   y-down display pixels and normalized safe-area rectangles. Convert Unity/screen
   conventions explicitly; refresh when the display or insets change.
2. Construct authored `TouchLayoutDocument` defaults and `HudLayoutModel` defaults.
   Choose separate private file paths and use `LayoutPreferenceStore.LoadTouch`
   / `LoadHud`. Missing means editable defaults. Invalid/Unavailable can use read-only
   defaults, not automatic overwrite or fabricated success.
3. For the editor, create `TouchLayoutEditor` and `TouchEditorGesture` with intended
   minimum pixel sizes. Pass editor-only Down/Move/Up events with stable pointer
   IDs. Caller chooses drag versus resize handle. Call CancelPointer on pointer
   cancellation; Cancel on focus loss, navigation, teardown and display changes.
   Do not route these events as gameplay controls or mutate its active draft from
   another control. Draw Draft for preview, Document for committed preferences.
4. Use `HudLayoutEditor.Begin/SetScale/SetGroup/Preview` for temporary HUD editing,
   then Confirm or Cancel. `HudLayoutModel.Project(profile, group, projection)`
   resolves sparse overrides and anchor scaling without changing preferences.
   Scene callers request only groups they can display, retaining other preferences.
5. Confirm/Up changes memory only. An unchanged gesture leaves undo/redo intact. Invoke SaveTouch/SaveHud explicitly on the
   committed model when saving is intended, handle I/O errors and retain unsaved
   UI state. One adapter serializes its calls; the integrator must serialize other
   writers and own private-path security. No directory-fsync or power-loss claim.
6. The touch HUD uses the projected rectangle for both rendering and hit testing,
   with saved opacity but no secondary scale multiplier. The eight action IDs
   must match the live HUD. Movement, look and the fixed pause escape route stay
   unchanged; pause takes priority over an overlapping custom action target. The
   separate HUD model uses its documented anchor scaling. Neither model implies
   physical accessibility or visual parity.

Publishing-host command (must execute actual C# tests, not just skip):

```
python3 -m unittest -v tests.test_layout_projection tests.test_touch_layout_document tests.test_hud_layout_model tests.test_layout_preference_store tests.test_touch_editor_gesture tests.test_layout_editor_journey tests.test_touch_layout_session
```

Device acceptance remains open: real safe-area/orientation changes, multitouch and
lost focus, editor exit/cancel/re-entry, separate gameplay dispatch, control sizes
and opacity, HUD scene transitions, saved-file restart and physical write/power
interruption. Do not mark these passed from host fixtures or compilation alone.

The composed authored journey additionally exercises cancel-before-first-save,
commit/save/restart, interrupted display changes, failed durable save with an
unchanged prior file and retained retryable memory, independent HUD persistence,
and corrupt restart refusal. It is model/file evidence, not an Android UI test.

The host-tested `TouchLayoutSession` provides the lifecycle boundary for the
touch editor. Construct it at startup with the actual feature gate, defaults and
one private store. Render `Current` outside the editor, and render
`EditorDocument` plus `Draft` inside it. Route only editor pointers to the
session; use `CancelGesture` when geometry or focus changes. Use
`SaveAndClose` for a deliberate save/exit, and keep the editor open on failure
for retry or discard. Unchanged exits do not touch disk. Use
`DiscardAndClose` for cancellation or teardown. An invalid or unavailable file
keeps defaults visible but blocks editing without repairing or overwriting the
file; report `StartupState` rather than saying the owner's layout loaded.
The touch-only settings panel exposes an unchecked `Edit touch controls layout`
request. Use **Save and close** to persist the request and open the editor on
the paused run or offline start screen. Editor **Save layout** commits the
layout and clears the request; **Back** discards edits and also closes the
request. A failed settings reset remains retryable without rewriting a
committed layout. The saved geometry loads on restart even while the editor
is off. Defaults render if the layout is missing, corrupt, or unavailable;
invalid or unavailable owner files are not replaced. The editor owns only
its single GUI pointer. Physical routing, visual placement and interruption
behavior still need Unity/device acceptance.
