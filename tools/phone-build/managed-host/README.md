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
are unsupported. Encrypted disposable signing material and all build outputs
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
