# App-hosted public transform fixture

Current experimental support connecting the existing public transform producer
to the separate [native-host fixture](../native-host/README.md). It uses the
existing Python and .NET build tools. Route A's IL2CPP game runtime and desktop
fallback remain authoritative. Full results and limits are recorded once in
[J1001](../../../docs/PORTING_JOURNAL.md#j1001--run-the-unchanged-public-transform-producer-inside-the-android-app-host).
[J1074](../../../docs/PORTING_JOURNAL.md#j1074--qualify-the-integrated-public-transform-tools-inside-the-android-app-host)
qualifies the integrated source pins with a complete phone build, two cold
app-host runs and copied-input refusal. Full game construction remains open.

`NativePythonHost.c` configures the supplied Python 3.14.8 through its public
[opaque initialization API](https://docs.python.org/3.14/c-api/init_config.html).
It selects isolated configuration, explicit home/module paths and arguments,
disables environment/site imports and bytecode writes, and preserves the script
exit. `NativeDotnetMuxer.c` implements only the protocol needed by the public
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
the public producer, and API-30 `android.jar` plus build-tools-34.0.0 `d8.jar` and
`apksigner.jar`. Source drift, links, existing or unowned destinations refuse.
The source stage contains no game input. SDK jars are compile tools and are not
packaged into the app. Staging does not approve tool redistribution.

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

`ToolHostActivity` owns each fresh data directory, data/native hash checks,
installed native links and bounded children. The original authored compiler/run
control remains, followed by `run_profile.py`. That entry checks actual isolated
Python flags and the supplied Managed-file manifest, then invokes the unchanged
public CLI. The CLI's archive/source/reference/provider/golden-output gates stay
active. It never executes the inspected game assemblies. Reports, derived DLLs,
paths and logs remain private; reports keep security qualification false.

## Caller-owned device inputs and teardown

Use the existing explicit-device, fresh-storage/reserve and exact installed-APK
ownership rules. Refuse any pre-existing fixture package. After installing only
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

There is no game, launcher or whole-catalog consumer and no new `./dev` action.
ADB-assisted input staging, the debuggable app, supplied tools and fixed profile
do not qualify production bootstrap/delivery, general Python/native dependencies,
Unity execution/content/player production, durable signing, cancellation/resume,
ownership acquisition, final installation UX or matched performance. J929's
writable-execution refusal remains failed.

## Headless whole-player code jobs

`stage.py --owner-backend` also stages the tracked authored owners and target
profiles. An explicit private `backend-tools.json` supplies hash-bound generic
compiler/linker/strip/Python-extension ELF providers, native data-tree links and
Clang resources to the existing builder. An optional supplied .NET 10 framework
keeps the pinned ILSpy tool runnable; .NET 8 remains selected by the Unity tool
and public transform runtime configurations. Native providers enter only the
PackageManager library directory; input game/SDK/target sources are separate
caller-owned app data. SDK/tool acquisition rights remain separate from hosting.

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
native/data checks and child deadline. Timeout first signals the controller so
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
tool app selects Android's documented
[`allowNativeHeapPointerTagging=false`](https://source.android.com/docs/security/test/tagged-pointers)
compatibility setting: the acquired JDK truncates a tagged heap pointer under
the default Android 13 app allocator. This is scoped to this build-tool app,
changes no device policy or game manifest, and does not qualify future MTE
devices or repair that upstream JDK limitation.

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
