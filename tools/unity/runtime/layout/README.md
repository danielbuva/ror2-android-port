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
