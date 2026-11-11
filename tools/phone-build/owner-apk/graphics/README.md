# Optional graphics driver foundation (Track G)

These Java owners are packaged in the managed tool-host **picker preview**, not
wired to the game launcher. The existing System driver/Unity launch remains
unchanged. No real driver or third-party native code is bundled, downloaded or run.

- `GraphicsDriverPackage` owns bounded AdrenoTools ZIP staging and SHA-256/ARM64
  verification. A caller opens a user-selected SAF stream, or a user-requested
  download whose release row came from an APK-pinned manifest. It supplies a new
  directory under `Context.getFilesDir()` and a bounded `org.json` metadata reader.
  Only the declared library and metadata are extracted. The original archive is
  retained for provenance/license display. An unsuccessful stage is not selectable;
  the caller removes its own failed stage. Library bytes are rechecked before load.
- `TurnipRelease` requires source release/download agreement, a SHA-256 pin, Mesa
  Turnip family, MIT license, reviewed minimum Android API and supported Adreno
  generations. These are validated
  *reviewed manifest claims*, not proof that an arbitrary ZIP is open-source. The
  curator must audit the release/source/license before adding a row. User-imported
  packages are explicitly not marked curated. Metadata may declare an older API
  or a library name such as `vulkan.ad07XX.so`; admission combines the metadata,
  provider API 28 floor and reviewed curated API floor. No remote manifest is
  trusted here.
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
- `GraphicsDriverProviders` owns the picker-facing System/Turnip/PanVK choices.
  System is always available; unsupported/unknown hardware and the unconnected
  Unity loader explain why Turnip is unavailable. Mali/PanVK is an unavailable
  stub, never a selectable loader. Explicit Turnip selection rechecks package
  bytes, provider availability and API/generation constraints before persisting
  the next-launch preference. Selection never loads a library; reset never
  clears the process-wide native-attempt latch. `ActiveDriver` is separate from
  that preference and defaults to unavailable. Its populated form requires an
  observation of Unity's actual active physical device, with unsigned raw
  vendor/driver-version values and optional driver-properties text. No current
  runtime supplies that observation, so the UI must not invent an active name.

## Curated catalog admission

The APK-owned `GraphicsDriverProviders.curatedReleases()` is intentionally empty.
It lists neither unaudited Mesa archives nor proprietary Qualcomm drivers. A
download SHA alone does not prove an acceptable distribution. Each future row
needs a pinned Mesa commit and build recipe, independently checked archive hash,
bundled component license/copyright notices, and reviewed API/device/loader
constraints. The existing `TurnipRelease` validates those reviewed claims; ZIP
metadata cannot add a catalog row. libadrenotools remains source-pinned below,
not packaged or available merely because the picker can name it.

A bounded follow-up reviewed the open Mesa build recipe at
`rtiangha/Mesa-Turnip-Builder` commit
`fe76fa770c8d3999ee9d0d1503f90d6000c0d9d5`, upstream Mesa
`8e87a503ebd91408c88596d1b9eeb5f4c0b2088d` (26.2.6). The downloaded archive's
SHA-256 matched independently and its recipe, metadata and ELF note agreed on
API 28. It was **not admitted**: the archive lacked redistribution notices and
the builder project imposed non-commercial restrictions; fully pinned build
inputs and loader behavior also remain unqualified. No archive or driver binary
is committed, recommended or added to the catalog by that audit.

## Tool-host picker and synthetic contract

The explicit **Graphics drivers** button opens `OwnerGraphicsPicker`. Its banner
states that preferences live in this tool host, not the separately installed game.
Opening it never imports, downloads, loads or selects a custom driver. Active
details remain honestly unavailable; System reset persists only the next-launch
preference. Close/Back dismisses the dialog; repeated opens do not stack it and
activity destruction closes it. No game-profile or installer flow is started.

The Android settings button resolves the public
`Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS` action to an enabled/exported
system application, then opens that explicit component only on a tap. Missing
targets disable the button; denied or disappeared targets show unavailable.
The manifest declares only the narrow action query, retained when staging rewrites
game-package visibility. It does not claim a portable direct Graphics Driver
Preferences page, enable Developer options or write Android global preferences.

Synthetic smoke requests `graphics_fixture=true` on the tool-host intent. Only
debuggable `dev.ror2lab.installertest` on API 28+ displays the conspicuous fixture
mode and controls. It simulates Adreno/Mali capability rows but keeps the native
provider unavailable. The future lab harness may inject only `package.zip` and a
64-byte lowercase `sha256` pin into the freshly owned app's `files/graphics-fixture`.
The ZIP is at most 4 KiB and contains `meta.json` with schemaVersion 1, name
`Authored graphics fixture`, driverVersion `synthetic-only`, minApi 28 and libraryName
`libvulkan_fixture.so`; that library is exactly `GraphicsDriverFixture.library()`'s
64-byte non-executable ARM64 ELF header. The UI parses real bounded Android JSON,
checks the archive hash and actual package verifier, requires those exact synthetic
labels/bytes, and removes only its newly created verification stage even on failure.
It never publishes a curated row, writes a custom selection or invokes a loader.

Smoke controls: **Use System driver**, **View driver source and licenses**,
**Verify synthetic driver file**, **Show Mali fixture**, **Show Adreno fixture**,
**Close graphics drivers**. Selection/choice/result text uses the stable accessibility
descriptions `graphics-selection`, `graphics-choices`, `graphics-result`. The source
dialog closes with **Back to graphics drivers**. The smoke must not open Android
settings or grant permissions merely to exercise this UI. Actual APK/UI, SAF,
native binding and completed frames are separate unpassed gates.

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
2. Add the Android metadata adapter, app-private catalog/selection ownership and
   System driver details from Unity's active Vulkan physical device. Follow the
   property and Android settings constraints below; never change Android's setting.
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

With `JAVA_HOME` and `ANDROID_SDK_ROOT` (or `ANDROID_HOME`) configured, the suite
also compiles all production Java owners using the API 33 `android.jar` as the
Java 8 bootclasspath. It does not compile the desktop harness against Android.
This catches the Android/JDK bootstrap mismatch observed in #274 rather than
assuming a desktop `javac` pass proves Android compatibility. The check skips
explicitly when that SDK jar is absent; it does not download a toolchain or launch
a device. A successful compile is not API 28 runtime, filesystem durability,
APK integration, native-driver or first-frame qualification.

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


[SDK inspection run 42985707283](https://github.com/danielbuva/ror2-android-port/issues/177#issuecomment-6790792779)
compiled the V1 fixture successfully against the installed version's headers and
bundled ARM64 NDK, with zero Editor/device actions. Runtime preload, exact editor
revision and custom-driver/frame acceptance remain unverified.

`native/GraphicsDriverPreload.cpp` is an isolated qualification observer, not a
production driver switch or a packaged launcher plugin. It registers the V1
callback in `UnityPluginLoad`, returns the original resolver unchanged, and
exposes fixed bits through `GraphicsDriverPreloadStatus`. The expected `0x7f`
means loaded, Vulkan interface found, registration accepted, callback called,
device initialized, callback before initialization and non-null original resolver
preserved. Bit `0x80` marks invalid/repeated ordering; `0x100` marks unload.
No custom driver is opened and no completed-frame claim follows. The SDK inspector
now syntax-checks this source too; the previous published SDK run did not cover
this new observer. Host tests execute authored interface doubles, not real Unity.

## Isolated runtime qualification build

`scripts/build-graphics-preload-fixture.py --output work/rebuild/graphics-preload-<attempt>`
is the build owner for the next gate. It requires committed source, the pinned
Editor binary hash, 100 GiB free and the canonical Unity build mutex. It compiles
only the authored observer with the bundled ARM64 NDK and builds a new SDK-only
project. `GraphicsPreloadFixtureBuild.cs` explicitly sets and reads back
`PluginImporter.isPreloaded`, excludes Editor loading, selects Android ARM64 and
Vulkan, and requires a successful zero-error build. The resulting APK's plugin
must match the compiled library byte-for-byte. No game input or custom driver is
included. Logs, APK and generated project stay in the new ignored output.

`GraphicsPreloadFixture.cs` records the native ordering flags in the separate
`dev.ror2lab.graphicspreload` app's private result file and fixed JSON log marker.
It does not report completed-frame or custom-driver acceptance. The diagnostic
package must later be installed/run only through the serialized, owned-device
lab workflow, then stopped and removed with its display asleep. The build script
never installs, launches or touches a phone. Staging, receipt binding and timeout
cleanup are host-tested; the C# build and actual Android preload are not qualified.

## System details and Android settings

System means Android's selected driver, which may itself be an updatable driver.
Read properties from Unity's actual physical device, not a separate Vulkan
instance or the first enumerated GPU. `deviceName` identifies the GPU and
`apiVersion` the API. `driverVersion` is vendor-specific; retain its raw unsigned
decimal/hex value rather than universally decoding it as a Vulkan version.
The richer [`VkPhysicalDeviceDriverProperties`](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceDriverProperties.html)
requires Vulkan 1.2 or enumerated `VK_KHR_driver_properties`, plus a valid
[`vkGetPhysicalDeviceProperties2`](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceProperties2.html)
route for the existing instance/device. A non-null pointer alone is insufficient.
`driverInfo` is free-form information; `conformanceVersion` is the CTS version.
If the instance version or enabled-extension state is unknown, show baseline
properties and unavailable rich fields rather than adding interception for a label.

The portable public shortcut is
[`Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS`](https://developer.android.com/reference/android/provider/Settings#ACTION_APPLICATION_DEVELOPMENT_SETTINGS),
labelled **Open Android Developer options**, not a guaranteed direct Graphics
Driver Preferences link. Check availability with a narrow manifest query for API
30+ package visibility and catch unavailable/security failures. Never enable
Developer options or write global driver preferences. These adapters remain
unimplemented; this source contract does not claim device qualification.
