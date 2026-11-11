# Optional graphics driver foundation (Track G)

These Android-independent Java owners are **not yet packaged or wired to the
launcher**. The existing System driver/Unity launch remains unchanged. No real
driver or third-party native code is bundled, downloaded or run by this slice.

- `GraphicsDriverPackage` owns bounded AdrenoTools ZIP staging and SHA-256/ARM64
  verification. A caller opens a user-selected SAF stream, or a user-requested
  download whose release row came from an APK-pinned manifest. It supplies a new
  directory under `Context.getFilesDir()` and a bounded `org.json` metadata reader.
  Only the declared library and metadata are extracted. The original archive is
  retained for provenance/license display. An unsuccessful stage is not selectable;
  the caller removes its own failed stage. Library bytes are rechecked before load.
- `TurnipRelease` requires source release/download agreement, a SHA-256 pin, Mesa
  Turnip family, MIT license and supported Adreno generations. These are validated
  *reviewed manifest claims*, not proof that an arbitrary ZIP is open-source. The
  curator must audit the release/source/license before adding a row. User-imported
  packages are explicitly not marked curated. No remote manifest is trusted here.
- `GraphicsDriverPolicy.Provider` is the detect/available/install/verify/load/
  fallback boundary. System is the default outcome and has no provider calls.
  Future Android/native adapters must not advertise custom-driver availability
  until the intended loader is actually connected to Unity. Unsupported GPUs
  should show System driver details and an explanation, not a disabled import.
- `GraphicsDriverPolicy.State` owns app-private, atomically replaced and synced
  selection/launch state. `begin` persists a pending marker before invoking native
  code. A new process seeing that marker resets to System without retrying custom
  code. A process-wide latch prevents repeated calls or newly constructed state
  objects from authorizing a System hot-swap after any native custom attempt.
  A live load/self-check failure requires a **process restart**, not replacing
  a Vulkan driver under live objects. `firstFrame` clears the pending marker only
  after both intended-driver identity and a completed Vulkan frame are attested.
  The Android owner must serialize calls, require explicit selection/reset, retain
  the returned user-facing reason across restart and finish the process cleanly.
- Custom pipeline cache namespaces derive from the archive hash, not mutable ZIP
  labels. The native adapter still needs to bind the Vulkan pipelineCacheUUID,
  implement cache-directory use/teardown and supply a versioned System cache key.

## Prior art and integration gates

Inspected libadrenotools at commit
[`8fae8ce254dfc1344527e05301e43f37dea2df80`](https://github.com/bylaws/libadrenotools/tree/8fae8ce254dfc1344527e05301e43f37dea2df80),
BSD-2-Clause. Its `include/adrenotools/driver.h` requires app-private custom
libraries and the actual `ApplicationInfo.nativeLibraryDir` for hooks. Native
libraries must be extracted (legacy packaging). `adrenotools_open_libvulkan`
returns a separate loader handle: successfully opening it does **not** establish
that Unity used that driver. No upstream code is copied in this slice.

Remaining before any option can be enabled:

1. Verify the exact Unity 2021.3.45f2 early Vulkan interception API, package the
   source-pinned BSD-2 libadrenotools/hook libraries, and attest actual runtime
   driver identity plus first completed frame. A hanging or crashing native load
   requires bounded process recovery. Do not use turbo/clock-control APIs.
2. Add the Android metadata adapter, app-private catalog/selection ownership,
   generic System driver name/version from Vulkan properties and availability-
   checked Graphics Driver Preferences deep link. Never change Android's setting.
3. Implement explicit SAF import and user-tapped, hash-verified Turnip download,
   license display, source review and one-tap reset. Do not list/link/bundle
   extracted proprietary Qualcomm drivers. Historical `turnip-target.json` is
   not an audited curated catalog. Keep the curated list empty until reviewed.
4. Wire driver-keyed caches and first-frame callback to the durable policy, then
   run serialized `/lab toolhost` and Thor stock/Turnip FPS/frame-pacing acceptance
   after the installer and interrupted-write tracks. Host checks are not GPU,
   native packaging, device or game-readiness evidence.

Run `python -m unittest discover -s tests -p test_graphics_driver.py` with a JDK.
The Java harness uses authored non-executable ELF headers and synthetic ZIPs. It
executes hash/manifest/archive/architecture gates, unchanged System default,
unsupported GPU/generation, unavailable loader, load/self-check failures, process
crash recovery, successful first-frame state and one-tap reset policy. The metadata
reader is a test adapter; Android JSON parsing is deliberately not qualified yet.

## Installed SDK inspection

`scripts/inspect-graphics-driver-sdk.py` performs a bounded, compile-only check
using the installed editor version from `environment/toolchain.json`, its
`PluginAPI` headers and its bundled Android NDK. The authored
`native/UnityVulkanContract.cpp` checks the V1 resolver callback signature and
registration result with `-fsyntax-only` for ARM64. It does not load a plugin,
launch Unity, produce binaries or touch a phone. Output contains only fixed
classifications and public SDK/fixture hashes; compiler text and paths stay
unreported. A passing result does not verify the editor revision, runtime preload
order or custom-driver operation. Run through the serialized lab queue when the
SDK is unavailable on the VM, without substituting another SDK.

The exact [Unity 2021.3.45f2 editor API](https://github.com/Unity-Technologies/UnityCsReference/blob/89faa1ec44f6e086390816d26a9de43ccf32772c/Modules/AssetPipelineEditor/Public/PluginImporter.bindings.cs#L189-L195)
exposes `PluginImporter.isPreloaded`. The later native-plugin build owner should
set that property explicitly (the Inspector calls it **Load on startup**), not
call the internal binding name `SetIsPreloaded` or rely only on a library-name
convention. This verifies the editor API, not Android runtime preload order.
The current official native-rendering sample is a 2023.1 project with no checked-in
Android plugin, so it is not evidence for the pinned Android target. No upstream
SDK/header code is copied into this repository.
