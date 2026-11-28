# App-hosted public transform fixture

Current experimental support connecting the existing public transform producer
to the separate [native-host fixture](../native-host/README.md). It uses the
existing Python and .NET build tools. Route A's IL2CPP game runtime and desktop
fallback remain authoritative. Full results and limits are recorded once in
[J1001](../../../docs/history/journal-J1-J1177/PORTING_JOURNAL.md#j1001--run-the-unchanged-public-transform-producer-inside-the-android-app-host).
[J1074](../../../docs/history/journal-J1-J1177/PORTING_JOURNAL.md#j1074--qualify-the-integrated-public-transform-tools-inside-the-android-app-host)
qualifies the integrated source pins with a complete phone build, two cold
app-host runs and copied-input refusal. Full game construction remains open.

`NativePythonHost.c` configures the supplied Python 3.14.8 through its public
[opaque initialization API](https://docs.python.org/3.14/c-api/init_config.html).
It selects isolated configuration, explicit home/module paths and arguments,
disables environment/site imports and bytecode writes, and preserves the script
exit. It explicitly searches the packaged player dependency directory.
`NativeDotnetMuxer.c` implements only the protocol needed by the public
producer: actual framework enumeration, `exec APP` and direct framework-dependent
application execution through the public
[hostfxr ABI](https://github.com/dotnet/runtime/blob/v8.0.32/src/native/corehost/hostfxr.h).
Host diagnostics and mappings go to stderr so compiler stdout retains its
contract. Neither shim implements an interpreter, VM or game execution backend.

`stage.py` owns hash-gated source staging. The audited
`recipe/owner-app-host-tools.json` pins the scoped native files/links and 21
unchanged public producer inputs. The provided source tree must contain the
exact pinned public profile; the integrated source selection is named by
`source_head` and verified per file.
No network fetch or private-history fallback occurs. Stage the fixture and
explicit owner SDK inputs into a new ignored destination:

```sh
python3 tools/phone-build/managed-host/stage.py \
  --profile-source PUBLIC_PROFILE_CHECKOUT \
  --sdk OWNER_ANDROID_SDK \
  --dest work/rebuild/managed-host-stage
```

This copies the base fixture's C/Hello/target-33 manifest, the new bridge sources,
the public producer, and API-33 `android.jar` plus build-tools-34.0.0 `d8.jar` and
`apksigner.jar`. Source drift, links, existing or unowned destinations refuse.
The source stage contains no game input. SDK jars are compile tools and are not
packaged into the app. Staging does not approve tool redistribution.

The seven managed-host Java sources compile with `-source 8 -target 8
-parameters -bootclasspath android.jar`. The API-33 bootclasspath does not
provide the lambda bootstrap method; callbacks use anonymous interface
implementations rather than lambdas. `test_owner_phone_flow.py` repeats this
compile contract when `ANDROID_SDK_ROOT` (or `ANDROID_HOME`) provides API 33.
It explicitly skips that compile when the SDK jar is absent; it never downloads
SDK tools or builds an APK.

Invoke the staged builder **on Android** with the previously verified tool
workspace, public compiler/reference materials and three phone-acquired archives:

```sh
python3 -I -S build_fixture.py \
  OWNED_TOOL_ROOT VERIFIED_MATERIALS NEW_OUTPUT ACQUIRED_ARCHIVES
```

The base fixture README describes supplied Clang/JDK/packaging prerequisites.
Additionally supply the fixed Python home at `OWNED_TOOL_ROOT/python/usr`.
The new builder validates native pins and archive hashes, packages native ELF
only under `lib/arm64-v8a/`, and puts Python/.NET managed data, public source and
archives in assets. Native Python extensions/dependencies are installed files;
their data-tree links resolve to that directory. Unselected Python extensions
are unsupported. Private durable signing material and all build outputs
stay ignored. No generated APK is approved for public distribution.

The native plan includes CPython's `_sqlite3` and its pinned SQLite dependency
for the existing bundle producer's disk indexes. Supply the versioned regular
SQLite file under the Python home; the installed native link supplies its
`libsqlite3.so` dependency name. Android execution of the complete signed bundle
chain remains a separate qualification gate.

For the debuggable fixture, instrumentation accepts `-e action release-build`
to run the existing signed update worker using the provisioned
`owner-input/update-request.json`. Without an action it retains the original
fixture path; other actions refuse. Release trust, source/configuration inputs,
signature checks and thermal supervision retain their existing owners. Resolve
the instrumentation component from the exact installed APK. This headless build
entry neither installs nor launches the converted game.

`ToolHostActivity` owns each fresh data directory, data/native hash checks,
installed native links and bounded children. The original authored compiler/run
control remains, followed by `run_profile.py`. That entry checks actual isolated
Python flags and the supplied Managed-file manifest, then invokes the unchanged
public CLI. The CLI's archive/source/reference/provider/golden-output gates stay
active. It never executes the inspected game assemblies. Reports, derived DLLs,
paths and logs remain private; reports keep security qualification false.

## Caller-owned device inputs and teardown

Use the existing explicit-device, fresh-storage/reserve and exact installed-APK
ownership rules. Refuse an unowned pre-existing fixture package; updates require
the exact current ownership receipt and the retained tool signer. After installing only
the hash-bound fixture, supply `files/user-input/Managed/` and a separate
`files/user-input/input-hashes.json` under its app UID. The manifest has schema 1,
the accepted input ID and `files: {DLL_NAME: SHA256}` for the scoped 146-file
cohort. The caller must independently match its legitimate source to the already
accepted inventory before transfer and recheck originals afterward. This app
manifest is a drift check, not ownership/authentication or a new input approval.
Game files and this private input manifest must never enter the fixture APK.

Require two cold attempts with distinct data directories, independent exact
golden DLL readbacks, actual loaded-provider/runtime witnesses, child/app UID
and context equality, and native mapping/hash checks. Verify all file-backed
executable mappings resolve to the installed native or Android system roots;
anonymous JIT mappings are a separate category. A copied-input corruption
control must refuse before producer output. Preserve failures and receipts;
remove only the package matching the ownership receipt, verify absence, and
confirm the original input/game bytes, stopped state and display sleep.

The scoped prefix control has no game/whole-catalog consumer or new `./dev`
action.
ADB-assisted input staging, the debuggable app, supplied tools and fixed profile
do not qualify production bootstrap/delivery, general Python/native dependencies,
Unity execution/content/player production, full-player signing, cancellation/resume,
ownership acquisition, final installation UX or matched performance. J929's
writable-execution refusal remains failed.

## Headless whole-player code jobs

The existing worker also accepts `{"textures": {...}, "output": "work/rgba"}`
requests. `textures` requires `profile` (relative to staged `repo`),
`profile_sha256` and `pc` (relative to private `owner-input`). Optional
`jpeg_codec` and `etc_codec` pins contain `path` relative to the installed native
library directory and `sha256`; `sdk_toolchain` uses the same pin shape with a
private input-relative descriptor path. The descriptor retains the texture
producer's exact absolute SDK/runtime dependency pins. Providers must already
be acquired and executable in the app sandbox; this route does not acquire or
relocate them. Optional boolean `resume` selects a verified durable checkpoint.
Output is private input-relative; a new output is required unless resuming.
The existing texture owner checks profiles, original bundles, tools and persisted
extents; the worker checks supplied input hashes before and after production.
Process exit tears down the job; receipts/checkpoints persist for the caller.
The existing thermal supervisor still wraps the worker. Host authored-pack
production/resume passes; ordinary-app texture execution remains unqualified.

`stage.py --owner-backend` also stages the tracked authored owners and target
profiles. Pass `--backend-tools PATH` to stage the private plan with the
installer sources and bind it in the staging receipt. Use a canonical
destination when the checkout links to shared `work/`. The plan supplies
hash-bound compiler, linker, strip and Python-extension ELF providers, native
data-tree links and Clang resources to the existing builder. An optional .NET 10 framework
keeps the pinned ILSpy tool runnable; .NET 8 remains selected by the Unity tool
and public transform runtime configurations. Native providers enter only the
PackageManager library directory; input game/SDK/target sources are separate
caller-owned app data. SDK/tool acquisition rights remain separate from hosting.

For native Clang caching, supply the following ARM64 packages from the
[Termux main repository](https://packages.termux.dev/apt/termux-main/pool/main/).
Verify each archive before extracting the provider and verify the extracted
ELF before adding it to the private backend plan.

| Package below `pool/main/` | Archive SHA-256 | Native provider and SHA-256 |
| --- | --- | --- |
| `c/ccache/ccache_4.14.3_aarch64.deb` | `3b133bb448768fb256d53811c8712457314d927c55de0249668d62a5d2124401` | `usr/bin/ccache` · `07b6f502526067d2f570484afec803242b4011ca36653d41dd86fd5f3e6e5b33` |
| `f/fmt/fmt_1:12.2.1_aarch64.deb` | `562111c110ef5b8ebdfd0688c8d63c890aa255e0091567d2fabbe86f49a0b537` | `usr/lib/libfmt.so` · `997f94d81413e5ec382902944f09661814a5d5b1d9b8a5549c06130ef5645c66` |
| `lib/hiredis/libhiredis_1.5.1_aarch64.deb` | `d55cd230363ef09a30786f61265cc611f450deec73a6b439c0859d2772056725` | `usr/lib/libhiredis.so` · `0c869801699ad85fe99d951c177a3b43d68849ef6c903a3a6e9d0b50bf70f3fa` |
| `x/xxhash/xxhash_0.8.4_aarch64.deb` | `e747c95589d887156db013c7d198a83fc539315bb6ac52f0e6e204eb740443c6` | `usr/lib/libxxhash.so.0.8.4` · `c6bd49d3b0341c518f9a2b8e1e62390177618ea6a0ddbb253d90476d0426b71d` |

Include `libccache.so`, `libfmt.so`, `libhiredis.so` and
`libccache_xxhash.so` in `natives`, alongside the toolhost's existing
`libandroid-spawn.so`, `libc++_shared.so` and `libzstd.so.1` providers.
Map `native-links/ccache` to `libccache.so` and
`native-links/libxxhash.so.0` to `libccache_xxhash.so` in `links`.
Retain the package license notices. Toolhost removal clears its app-private
cache along with the rest of its data.

For the signed owner backend, build the Python wheelhouse on the host. Use
cibuildwheel 4.3.4, the Python `build` package and a separate Android SDK with
NDK 27.3.13750724 installed. The wheel producer uses CPython 3.14.8, ARM64
and API 24, with pinned PyPI sources, IJG JPEG source and the CPython Android
extensions used by the wheel imports.

```sh
python3 tools/phone-build/managed-host/build_python_wheels.py \
  --sdk "$WHEEL_SDK" --output work/rebuild/toolhost-wheelhouse
```

Set `python_wheels` in the backend configuration to the wheelhouse directory
and `python_built_wheels` to the contents of its `built-wheel-hashes.json`.
Supply the Android `mmap.cpython-314-aarch64-linux-android.so` provider as
`libpyext_mmap.so` and link it at
`python/lib/python3.14/lib-dynload/mmap.cpython-314-aarch64-linux-android.so`.
The builder checks the wheel hashes, retains the notices and stages extensions
in the APK's native library directory. `check_python.py` imports the staged
phone entry points and release producers in an isolated interpreter using the
import plan from `recipe/owner-app-host-tools.json`. This software is based
in part on the work of the Independent JPEG Group.

For signed texture jobs, add the outputs of
`build_texture_jpeg.py`, `build_texture_etc.py` and `build_texture_sdk.py`
to `natives` as `libtexture-jpeg.so`, `libtexture-etc.so` and
`libtexture-pixels.so` respectively. Build the native pixel helper with
`build_texture_sdk.py --pixels-only --compiler TARGET_CLANG --output NEW_DIR`
before the owner SDK arrives. For macOS cross-builds, use the bundled NDK's
`aarch64-linux-android24-clang` for JPEG and pixels and its
`aarch64-linux-android24-clang++` for ETC. Include `libqemu-x86_64.so`,
`libc++_shared.so` and the pinned QEMU dependency closure with its actual
SONAME aliases under `native-links/` in `links`.
Set `texture_sdk_guest` to a directory containing the built x86-64
`texture-sdk-codec` and the GNU runtime arranged under `linux/` as listed
in `recipe/owner-app-host-tools.json`. The builder copies only those pinned
paths into the private fixture, and the host grants the verified guest wrapper
mode `0700` after asset extraction for QEMU's executable check. Retain the
providers' license notices. The owner-acquired Unity codec is extracted by a
separate signed conversion job.

Signed player Shader jobs use two additional native executables. Add them to
`natives` as `libd3dasm.so` and `libhlsl-decompiler.so` with their SHA-256
values. Build d3dasm's `d3dasm-cli` package from the pinned d3dasm and cfglib
revisions using `cargo build --locked --release --target aarch64-linux-android`.
Use the bundled NDK API 24 Clang linker and the AArch64 LLVM unwind archive
from NDK r25c with `-L native=ARCHIVE_DIRECTORY` for the Rust runtime. Invoke
`shader_recovery.build_native_hlsl` with the pinned HLSLDecompiler checkout,
putting the bundled NDK bin directory first on `PATH`. Set
`CCC_OVERRIDE_OPTIONS` to `# +--target=aarch64-linux-android24 +-static-libstdc++ +-fsigned-char`
so the fallback preserves the source's signed `char` semantics. Retain the
public tools' license notices with the packaged providers.
[Source pins](../../../docs/shader-recovery.md#pinned-tools-and-local-prerequisites)

The signed direct ComputeShader recipe uses a two-tool Android backend. Put
the following four archives in `PUBLIC_SHADER_SOURCES`, using these filenames.
`build_shader_tools.py` checks their exact SHA-256 pins before extracting them.

| Filename | Source |
| --- | --- |
| `vkd3d-2.0.tar.xz` | [Wine vkd3d 2.0](https://dl.winehq.org/vkd3d/source/vkd3d-2.0.tar.xz) |
| `spirv-tools.tar.gz` | [SPIRV-Tools v2026.4](https://codeload.github.com/KhronosGroup/SPIRV-Tools/tar.gz/ef96ed763b43b59b33b31b362f09a02b729fa1c9) |
| `spirv-headers.tar.gz` | [SPIRV-Headers dependency](https://codeload.github.com/KhronosGroup/SPIRV-Headers/tar.gz/496543121ce6419f23d6fa5d7194ba66c36212d2) |
| `vulkan-headers.tar.gz` | [Vulkan headers 1.4.350.1](https://codeload.github.com/KhronosGroup/Vulkan-Headers/tar.gz/refs/tags/vulkan-sdk-1.4.350.1) |

Use GNU Bison 3.8.2, CMake 4 and Ninja on the build host.

```sh
source scripts/env.sh
python3 tools/phone-build/managed-host/build_shader_tools.py \
  --sources "$PUBLIC_SHADER_SOURCES" --ndk "$ANDROID_NDK_ROOT" \
  --bison "$BISON_382" --output work/rebuild/android-shader-tools
```

Merge the two `natives` rows from `native-tools.json` into the managed-host
backend configuration. PackageManager installs the executable files, and the
signed job receipt records their hashes. With any distributed copies, include
the builder's `notices`, `public-sources` and `relink` directories so recipients
can audit and relink vkd3d. The builder's command logs and `native-tools.json`
contain local paths and stay with the private build. The current direct recipe
selects the original Histogram ComputeShader. Its output is a typed record
pack for bundle assembly.

The builder applies `vkd3d-structured-srv.patch` to the pinned vkd3d source
and includes it in `public-sources`. Apply the same patch at the archive root
before rebuilding the vkd3d libraries for relinking.

For the signed graphics profile, pass `--graphics` and add these archives to
the same source directory. Stage all five `natives` rows from the receipt.
The builder keeps the additional upstream notices and the glslang Android CLI
patch with the public source archives. The patch enables the tool and keeps
diagnostic paths compatible with the pinned Unity NDK.

| Filename | Source |
| --- | --- |
| `smol-v.tar.gz` | [SMOL-V source revision](https://codeload.github.com/aras-p/smol-v/tar.gz/55000efe742f56d8b51223b9ea7775a8f0501881) |
| `spirv-cross.tar.gz` | [SPIRV-Cross Vulkan SDK 1.4.363.0](https://codeload.github.com/KhronosGroup/SPIRV-Cross/tar.gz/refs/tags/vulkan-sdk-1.4.363.0) |
| `glslang.tar.gz` | [glslang 16.6.0](https://codeload.github.com/KhronosGroup/glslang/tar.gz/refs/tags/16.6.0) |

The muxer keeps CoreLib in the selected framework's verified data directory via
the public hostfxr runtime-property API. For .NET 10 it uses the public
[CoreCLR hosting ABI](https://github.com/dotnet/runtime/blob/v10.0.0/src/coreclr/hosts/inc/coreclrhost.h)
with those same resolved properties and the selected CLR library. This avoids
hostpolicy recombining the canonical installed directory with the .NET 8 native
filename. ILSpy's child also searches its selected .NET 10 native links first;
mixing the two native framework families causes measured startup/shutdown
failures. The public transform producer sees an isolated .NET 8 framework tree
and retains its exact enumeration and golden-output checks.

Use `ToolHostActivity.Runner` instrumentation to execute the worker without an
Activity or a display wake. `files/owner-input/request.json` selects either
explicit managed providers or the fixed-target source request consumed by
`owner-code/run_android.py`. The worker owns its fresh source/framework directory,
native/data checks and child deadline. Each tool child starts through Android's
`taskset 1`, restricting startup and inherited descendants to CPU 0 before Python
or the JVM initializes. This trades throughput for bounded startup CPU use on
the assigned devices; it supplements the caller's thermal watcher and does not
establish a temperature limit. Timeout first signals the controller so
it can reap its process groups. The caller retains receipts/results, verifies
loaded providers/output bytes, monitors kernel temperatures and releases the
owned package/lease afterward. The thermal service can be unavailable despite
reporting status 0; battery temperature alone does not measure CPU hotspots.

Install the LLD provider as `lib-ld.lld-.so`. The pinned
[LLD dispatcher](https://github.com/llvm/llvm-project/blob/llvmorg-21.1.8/lld/Common/DriverDispatcher.cpp)
recognizes the `ld.lld` filename segment as its GNU driver. The normal linker
flags and original SDK target runtime remain unchanged; no extra wrapper or
modified LLD binary is required.

These remain debug/ADB-assisted private tool jobs. The fixed original-input
gameplay source, complete content/Burst/shaders, full APK, app signing,
ordinary installation and game/performance acceptance are separate gates.

## Headless JDK and owner APK jobs

An explicit `java_home` in the private backend tool plan selects the acquired
JDK. The phone builder compiles `NativeJavaHost.c` against its JNI headers and
installs javac, keytool and java entry points plus the headless VM dependency
closure as read-only PackageManager native files. Modules, security policy and
configuration are hash-verified tool data. The JNI launcher uses the explicit
VM path and Java home; it never loads ART as the build VM. The acquired JDK's
[Android pathname adaptation](https://github.com/termux/termux-packages/blob/master/packages/openjdk-21/0017-Try-to-get-libjvm.so-path-from-proc-self-maps-on-and.patch)
derives its initial data home from `dladdr(libjvm)`, before ordinary property
parsing. The authored launcher adapts that one reported path to the logical JDK
data layout. The actual ELF is opened from the installed native directory and
its executable mappings retain that location; no VM binary is patched. Existing SDK JARs
provide javac's Android reference surface, D8 and apksigner. The caller's extra
native plan must include the JDK's Android spawn and shared-memory dependencies. The
acquired JDK truncates tagged heap pointers under Android 13's default allocator.
An exec child has fresh allocator state, so an app-manifest opt-out does not
cover it. Before loading the VM, this launcher uses Bionic's documented API 31
`mallopt(M_BIONIC_SET_HEAP_TAGGING_LEVEL, M_HEAP_TAGGING_LEVEL_NONE)`
[allocator option](https://android.googlesource.com/platform/bionic/+/refs/tags/android-13.0.0_r1/libc/include/malloc.h).
It refuses when that child-local compatibility setting is unavailable. No device
policy, parent app allocator or game manifest changes. This does not repair the
upstream JDK's tagged-pointer limitation or qualify other allocator/API versions.

The optional plan `package` selects a separate lab tool identity while retaining
Java class names and private provider authority. It cannot select the game
package. The builder keeps its durable tool signer at `TOOLROOT/owner-tool-key`,
outside disposable build outputs; retain that directory for compatible updates.
This key is separate from the game owner's signing key. No key enters the APK.

Under `files/owner-input/`, a request `{"signing": {"unsigned":
"INPUT.apk", "key_directory": "keys"}, "output": "work/sign-v1"}`
selects existing owner signing. All paths are relative to that private input
root. `input-hashes.json` pins the immutable supplied files; the durable key
directory and output are generated state. A packaging request instead supplies
`targets`, `manifest`, all three `code` paths, `key_directory` and `version_code`
inside `packaging`; it invokes the existing complete APK owner first. Inputs
remain distinct from tool APK assets. Each output must be new.

Successful signing publishes `owner-apk-ready.json` and the worker binds its APK
hash into the private report. Opening the Activity displays the package/version
and enables an install button. Only that button opens unknown-source settings
or Android's installer, using a private read-only content provider. Headless
Runner jobs never launch UI. Retain the private owner key independently of
disposable outputs and before removing this tool package. Final installer/game
acceptance remains separate from successful tool execution.

[J1103](../../../docs/history/journal-J1-J1177/PORTING_JOURNAL.md#j1103--produce-fixed-target-burst-and-sign-owner-apks-in-the-android-tool-host)
qualifies fixed-target Burst and two authored APK signing processes in this
ordinary app host, with actual native hash/mapping/UID/context evidence. It does
not qualify full-player assembly, installer UI or game performance. The separate
original-input native compilation remains active until its own terminal result
and explicit corrected relink. Device policy/security qualification stays open.

## Phone-only installer surface (host-qualified, not device-qualified)

Installer version 3 keeps the existing signed release updater, source-only
producers, thermal supervisor and `OwnerInstaller` PackageInstaller path. The
Activity now prepares a signed installation plan, asks Android's Storage Access
Framework for a folder or ZIP and retains read-only URI permission. No input URI,
file bytes or local inventory is sent to the release network client.

`OwnerInputSource` owns Android provider access and revocation recovery;
`OwnerInputImport` is the host-tested stream copier. It imports only signed-manifest
paths directly into `owner-input/import/files`, verifies sizes/SHA-256 and retains
whole verified files for resume. ZIP input is streamed once, without a private
archive-sized copy; ignored extra members have a bounded decompression budget.
Traversal, aliases, duplicate ZIP entries, mismatches and missing inputs refuse.
The free-space estimate includes remaining copies, the signed workspace budget,
2 GiB reserve and 5% of remaining input bytes. A changed manifest retains the
previous files in an import-local `previous-import-*` directory rather than
silently deleting them. Python rehashes exact final membership before reconstruction;
Java progress/receipts are never input admission proof. Only deterministic unfinished
native copy fragments are discarded automatically.

`OwnerBuildService` owns the worker independently of Activity recreation and task
removal, with an ongoing foreground notification and a partial wake lock during
local work. Pause/resume/cancel feed the existing thermal supervisor; user pause
never pauses its sensor loop or overrides its cooling decision. These controls
stop when work hands off to Android installation and do not apply to profile
verification or recovery. Provider cancel
uses `CancellationSignal` and closes the active source stream. Battery admission
requires a measured temperature of at most 35 C at any charge level. The
supervisor pauses at 90 C on the hottest readable SoC zone. The screen displays signed
stages, byte/job progress, elapsed time, first failure, live duty-runner readings
and Android battery charge/health; unavailable or old readings are marked.

Process death/reboot preserves source grants, verified files and stage checkpoints.
There is no boot receiver, sticky restart or automatic work after reboot: Resume is
explicit and all reused bytes are revalidated. Cancelling keeps verified checkpoints.
The service signals the existing supervisor, whose teardown kills/reaps its process
family even while paused. Retrying an install failure uses the existing session
installer rather than reconstructing completed stages. After an explicitly started
reconstruction succeeds, the service hands the ready APK to `OwnerInstaller` if
Android permits installation; otherwise the UI asks the user to grant permission
and continue. The notification remains through a pending session/consent; only
package/version/signer readback marks installation complete. An adopted-storage
session also requires placement readback.

Synthetic JVM import/session tests, source/manifest lifecycle contracts and Android
API compilation do not establish real SAF-provider behavior, Android process-death
or reboot behavior, notification delivery, battery/thermal measurements, actual
PackageInstaller consent, a complete signed release recipe or a playable game.
Those remain device/release acceptance gates. This work creates no APK or key.

## Alpha update, rollback and profile-retention boundary

Installer version 3 selects only `dev.ror2lab.alpha` in the final UI. The existing
`OwnerInstaller` session path remains authoritative, including its Android 12+
request for no extra user action on eligible same-key updates; Android may still
require confirmation. Repeated clicks or activity recreation do not create a
second session. `OwnerAlphaInstall` adds exact installed APK/code/certificate
readback and an installer-private ownership receipt; an occupied unowned identity
or changed signer is refused without uninstalling. A signed issued-version row
binds source, accepted input, toolchain, payload, APK and certificate. Dispatch
consumes the code durably: a failed/cancelled session requires a newly issued
higher-code build rather than a downgrade or reused code.

The rollback button rebuilds the previous verified installed release with the
same owner key and a higher Android code. Publisher release numbering is separate
from installed/issued codes. `installed-release.json` and
`previous-installed-release.json` retain whole signed release manifests and
private signed-APK references, not copies of game data. Only verified successful
installation rotates these references. The UI reports retained APK bytes,
installer-filesystem free bytes and schema/key eligibility; release operations
prune older unreferenced generated APK artifacts while protecting current,
previous and the active ready build. Alpha APKs and sessions request external
placement. Turn on **Require adopted storage** to check mounted capacity before
dispatch and verify the installed APK and private data backing before success.
An existing install must already be on the selected adopted volume before an
update. A misplaced fresh install requires exact receipt and APK checks before
the installer asks Android to remove it. Confirm the Android dialog to finish
recording the refused placement.

Before an update/rollback, the certificate-bound game provider at
`dev.ror2lab.alpha.retention` snapshots the allowlisted Android-local profile and
settings under the **game UID**, freezes game launch, and returns a token, schema
and byte count. The installer and game are different UIDs/signers: the installer
never opens game-private files. `pending-install.json` retains the transaction
before session commit. The target release must read the snapshot's schema.
After exact installed identity readback, the foreground service verifies the
snapshot against live data, restores only if necessary, verifies again, publishes
the installed receipt, then releases the game launch freeze. A cancelled/failed
session verifies/restores the prior installation before releasing it. Recovery
failure keeps the token/freeze and exposes an explicit recovery button; fully
stop the game and resolve space/permission errors before retrying. No failure
path silently adopts another identity, clears data, or uninstalls. A certificate-bound
read-only `status` call also proves a previously released token. If the installer
died after release and gameplay has since resumed, recovery rechecks the installed
APK/code/certificate and signed issue ledger, then finalizes only the pending
receipt. It never restores an old snapshot over that newer legitimate gameplay.
An active token still requires the full verify/restore/verify/release sequence;
an unknown token or changed identity remains blocked. Snapshots
remain private in the game's no-backup storage; current and previous verified
snapshots are retained by its retention owner, separate from release artifacts.

`test_owner_alpha_installer.py` executes these orchestration/refusal paths with
synthetic streams and a provider double, alongside the original session tests.
Full source compilation against `android.jar` is not device acceptance: ordinary
PackageInstaller callbacks, actual installed storage/backing and real game
profile/settings across cold starts still require explicit device qualification.

## Explicit debug release source

Only a debuggable installer accepts an explicitly provisioned private
`owner-input/debug-release-source.json` containing `enabled: true` and `base_url`.
The base is an explicit loopback HTTP address and port reached through the lab's
reverse tunnel. `latest.json` and all three signed release assets stay within
that base. The installer uses its provisioned publisher keys for this source.
Synthetic tests can also supply both `key_id` and `public_key` to add a new
publisher under an unused ID. The UI labels the test source prominently.

Release builds reject this configuration, including partial configuration,
before contacting any server. Debuggability is read from Android application
flags, not from the configuration. Removing the file restores the pinned
production source and trust. No signature, version, ownership, same-key,
rollback or profile-retention check is bypassed.

The synthetic acceptance entrypoint is `scripts/lab-installer-updates.py`.
First request `/lab toolhost ref=<branch>`; the runner builds the separate
`dev.ror2lab.installertest` package and caches it by source commit. Then run
`/lab script ref=<branch> -- scripts/lab-installer-updates.py --host-only`
to prepare synthetic fixtures without a phone. The phone command is
`/lab script ref=<branch> device=<authorized-alias> -- scripts/lab-installer-updates.py`.
The runner supplies the leased device serial; this script never selects a phone
from a remembered identifier. Its toolhost builder must use an available authorized
device too. Only after the owner explicitly approves enabling unknown-source installation
for that disposable package may the invocation add `--allow-test-installs`.

The script resolves `LAB_TOOLHOST_ROOT` and `scripts/env.sh` on the lab host;
it requires Android platform 33, build-tools 34.0.0 and the configured NDK/JDK.
It refuses existing alpha/test packages, uses only original synthetic inputs,
creates throwaway publisher keys outside the checkout, and exercises the real
checker, rebuild, signing, retention and PackageInstaller path. It never reads
the builder's private test-publisher key. Results are fixed PASS/FAIL case lines;
raw subprocess output, private selectors, keys and APKs stay on the lab host.
Cleanup removes only this run's hash-verified packages and reverse tunnel and
verifies package absence. A host-only result is not phone acceptance.
