# Host-only owner layout models

These pure C# owners have no UnityEngine dependency and are not connected to live
input, HUD rendering or gameplay. Authored host fixtures are not device evidence.

`LayoutProjection` defines schema 1: top-left origin, x right and y down, with
normalized rectangles relative to the inset safe area. Insets are supplied by the
caller; this library does not discover cutouts or rotate device insets. Projection
and inverse projection require rectangles to fit. Inverse projection snaps only
boundary roundoff within 1e-12 of the safe span; larger excursions are refused. Explicit `Clamp` supports drag
and resize drafts, saturating oversized pixel minimums to available space.
`RotateClockwise` rotates normalized geometry; callers supply the new display and
insets separately. Aspect changes preserve normalized positions, not physical
control size or appearance. No policy is inferred for control actions or anchors.

`tests/test_layout_projection.py` compiles actual sources with host Mono/mcs or the
pinned Unity Mono/Roslyn. It skips executable geometry checks when neither exists;
a source-only check is not equivalent to executing the C# model.

## Touch document and transactions

`TouchLayoutDocument` owns immutable named profiles and generic control IDs, with
safe-area normalized rectangles, scale (.25..4) and opacity (0..1). Arrays are
copied on construction and access. Scale is independent authored metadata, not a
second rectangle transform: this model does not compute rendered size or hitboxes.
No ID maps to gameplay actions. Profiles preserve their authored ordering.

The bounded interchange format is UTF-8-compatible ASCII text: header
`touch-layout<TAB>1<LF>`, then `P<TAB>profile-name<LF>` followed by one or more
`C<TAB>id<TAB>x<TAB>y<TAB>width<TAB>height<TAB>scale<TAB>opacity<LF>` records.
Numbers use invariant round-trip formatting. IDs/names are 1..64 ASCII letters,
digits, underscores or hyphens, case-sensitive; localized display labels are not
part of this format. Limits: 16 profiles, 128 controls each, 1 MiB text. Imports
refuse unknown records/versions, duplicates, nonfinite/out-of-bounds geometry and
invalid limits rather than silently repairing them. Only LF line endings are
accepted. Caller owns file I/O and atomic durable persistence.

`TouchLayoutEditor` owns the committed document, one selected control draft, and
32 in-memory undo/redo snapshots. Begin/SetDraft/DragResize never change committed
state; Confirm commits, Cancel discards. DragResize explicitly clamps through the
projection contract and pixel minimums. Import validates completely before commit.
Import, Reset and history navigation refuse while a draft is active; callers must
confirm or cancel it first. Reset restores a profile from the constructor defaults;
unknown default names refuse. Successful new commits discard redo; failed actions
leave committed data and history unchanged. Undo history is session-only, not
serialized. Named profile construction/import is the data API, not a live editor UI.

`tests/test_touch_layout_document.py` exercises actual C# isolation, history,
round-trip/import refusals and bounds when the same host compiler is available.

## HUD preferences and preview

`HudLayoutModel` owns immutable authored default groups and named profiles with a
uniform UI scale (.5..2) and sparse group overrides. `HudLayoutEditor` stages a
single profile: SetScale/SetGroup/Preview do not mutate committed preferences;
Confirm applies and Cancel discards. Import and Reset require an idle editor.
Reset removes that profile's overrides and restores scale 1; untouched groups
always resolve to the supplied authored defaults. Arrays are defensively copied.

Group rectangles use the projection contract. Anchor values 0..4 mean top-left,
top-right, bottom-left, bottom-right and center. Scaling preserves that point of
the original normalized rectangle, then clamps to the safe area (saturating size
at its span). Insets/aspect are caller-supplied; projecting an available scene's
subset of group IDs never removes preferences for absent groups. There is no scene
listener, display detection or live HUD renderer. Overlap and visual suitability
remain the future UI integrator's responsibility.

Preferences export as `hud-layout<TAB>1<LF>`, then
`P<TAB>name<TAB>scale<LF>` and zero or more
`G<TAB>id<TAB>anchor-number<TAB>x<TAB>y<TAB>width<TAB>height<LF>` records.
Same identifier and LF/finite invariant-number conventions as touch documents;
limits are 16 profiles, 128 default groups/overrides per profile and 1 MiB text.
Defaults themselves are not exported: import requires the caller's authored
defaults, rejects unknown group IDs, malformed data and versions, and validates
all preferences before replacing state. This prevents imported preferences from
rewriting defaults. A changed authored group catalog needs explicit caller
migration; missing/unknown IDs are not silently dropped. Caller owns file I/O and
durable persistence, independently of these in-memory transactions.

`tests/test_hud_layout_model.py` compiles only the projection and HUD source, not
the touch document. Its fixture covers profile/default isolation, preview/cancel,
anchor scaling across aspect/inset changes, round-trip and failed imports. A
compiler-less host skip is not execution evidence.

## File persistence adapter

`LayoutPreferenceStore` is an optional separate file adapter, not live wiring.
Construct it with one caller-owned regular-file path in an existing private
directory. Use distinct files for touch and HUD. LoadTouch/LoadHud return Loaded,
Missing, Invalid or Unavailable. Only a genuinely missing file returns the supplied
default model; corrupt/oversized/invalid UTF-8 data returns no model and is left
untouched. Missing directories and read/access errors are unavailable, not defaults.

SaveTouch/SaveHud serialize a validated immutable model, refuse to overwrite invalid
or unreadable existing data, write a uniquely named same-directory temporary file,
flush it to disk, then atomically replace the old file (or move for a first save).
There is no delete-then-move fallback. Unsupported atomic replacement fails without
removing the old file. Temporary cleanup is best effort. Caller must handle save
errors separately from editor Confirm; a confirmed in-memory draft is not a saved
file. Explicit corrupt-file recovery/backup decisions belong to the caller, not an
automatic reset. Reads are bounded to 1 MiB plus one detection byte.

Calls on one adapter are serialized. Caller owns path security and must serialize
writers across instances/processes; shared/untrusted directories are unsupported.
File content is flushed, but no portable directory-fsync or hardware power-loss
guarantee is claimed. Host tests use authored temporary files, real replace/read
operations and injected write/publish/read failures. Physical interruption, Android
storage behavior and runtime integration remain device-worker responsibilities.
