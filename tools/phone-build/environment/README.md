# Native source environment capture

Current experimental source library for an owner-built converter tool player.
`RuntimeEnvironmentProducer.cs` owns SDK-sky rendering, ambient-probe evaluation,
reflection capture, half-float face/mip readback and output receipts. It is not
linked into the game. Main Nova qualifies native capture through a separate
SDK-built diagnostic player. Phone-built tool construction and conversion
admission remain open.
`RuntimeEnvironmentFixture.cs` is an exact-editor diagnostic builder for a
separate IL2CPP ARM64/Vulkan tool package, with a clone of the SDK default sky
material bundle and an otherwise empty scene. Stage it under `Assets/Editor`
and the two
runtime sources under `Assets` in a new isolated SDK project. Its menu action
`Tools/P1/Build Runtime Environment Fixture` retains its APK, source bundle and
build receipt outside that disposable project. These host-built diagnostic
outputs are never required public conversion inputs.
`RuntimeEnvironmentTool.cs` reads an explicitly transferred `request.json` from
its private persistent-data directory and invokes the producer once, writing
`output-<id>/result.json` there; startup failures write `startup-error.txt`. The
controller must refuse an existing tool installation and collect its outputs.
The controller must also query current storage and runtime backing, retain its
ownership receipt, uninstall only its owned disposable package, release its
lease and sleep the display when done.

The caller supplies a new destination directory and a request containing a source
recipe hash, a source-produced SDK material bundle and its hash, material name,
128-pixel resolution and the authored light rotation. The pinned linear SDK
player loads that material, creates an owned directional light, camera and
sky-only reflection probe, asks the native renderer to finish, then reads all
faces/mips as RGBAHalf. Unity evaluates the ambient probe through its existing
native API. No historical Cubemap, ambient array or private editor cache is read.

`result.json` records source pins, SDK/API identity, native HDR decode values,
27 final ambient coefficients and each generated face/mip extent and SHA-256.
The final-probe label is explicit; serialized-probe interpretation still needs
qualification for any consumer. Image files are generated SDK-derived data and
remain private. This is not yet a Unity
Cubemap record or a complete `level0` producer, and none of these outputs is
currently admitted into APK assembly. The phone control produces all 48 finite
face/mip images and 27 ambient
coefficients. Its input material properties and keywords match the independent
SDK default exactly; the final ambient differs from the SDK desktop-generated
reference by at most 0.000162162. No raw-exact or lighting-compatibility acceptance
is claimed. HDR encoding, filtered reflection equivalence, serialized Cubemap
admission and complete default-scene construction remain open.

One component owns one operation. It refuses an existing output directory,
restores sky/sun/realtime-probe state, unloads its bundle and destroys owned Unity
objects on success, failure or component destruction. The caller owns tool-player
lifetime, thermal/device supervision, output collection, package receipts and
mandatory display sleep and scratch cleanup. A separate disposable package must
refuse pre-existing installations; it must not replace a game or alter saves.
Use the existing device-cycle workflow for diagnostic installation and capture.

The source calls public SDK APIs and contains no copied SDK/game implementation,
material/program data or generated pixels. The owner supplies the permitted SDK
and generated bundle locally; this directory grants no redistribution or license
rights and performs no ownership or entitlement substitution.
