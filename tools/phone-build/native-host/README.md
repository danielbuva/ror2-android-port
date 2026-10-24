# Native build-tool app-host fixture

Current experimental support for one positive Android app-host contract. It
contains authored C, Java, C# and XML only. It is separate from the game, the
launcher and `tools/phone-build/host/`'s installed/writable refusal probe.
Results and limits are recorded once in
[J999](../../../docs/PORTING_JOURNAL.md#j999--host-the-existing-managed-build-tools-from-read-only-app-native-libraries).

`NativeToolHost.c` binds the existing .NET `hostfxr` command-line hosting ABI,
passes an explicit framework root and runs one managed application. Its ABI
declarations follow the [8.0.32 public header](https://github.com/dotnet/runtime/blob/v8.0.32/src/native/corehost/hostfxr.h).
It records the actual process identity, initialization/run exits and native
mapping paths. It implements no VM, game backend, framework resolver or JIT.
The framework-dependent hosting contract is described in
[Microsoft's native-hosting documentation](https://learn.microsoft.com/en-us/dotnet/core/tutorials/netcore-hosting).

`ToolHostActivity` owns each background attempt. It makes a fresh private data
directory, copies and hash-checks declared data assets, and requires every
declared native-library file to match its hash and be nonwritable to the app.
Framework-native links point to PackageManager's native-library directory;
OpenSSL's versioned names similarly point to installed libraries. The child
library search path contains only that directory and the owned links. The
activity asks the existing compiler for its version, compiles `Hello.cs` using
the supplied references, and runs its SHA-256 check. Each child has a deadline.
Logs and `files/tool-host-report.json` remain private. Failures are retained;
ownership-checked package removal belongs to the caller. Every report keeps
`securityQualified` false: this probe does not repeat or override J929.

## Build on Android

Stage this directory's five source files and explicit owner-supplied SDK
API 30 `android.jar`, build-tools 34.0.0 `d8.jar` and `apksigner.jar` together
under a receipt-owned workspace. Supply:

- `OWNED_TOOL_ROOT/usr`: the previously verified Android Clang 21/LLD and
  .NET 8.0.32 layout, including OpenSSL 3 libraries and notices;
- `OWNED_TOOL_ROOT/packaging/usr`: verified Android OpenJDK 21, `aapt` and
  `zipalign` tools;
- `VERIFIED_MATERIALS/compiler` and `refs`: the independently hash-verified
  public Roslyn 4.8.0 and .NET 8.0.32 reference material, with its notices.
  This fixture does not acquire, restore or authenticate those inputs.

Invoke the staged script using the owned Android Python host:

```sh
python3 -I -S build_fixture.py OWNED_TOOL_ROOT VERIFIED_MATERIALS NEW_OUTPUT
```

`NEW_OUTPUT` must have an existing parent and must not exist. The driver binds
inputs, compiles the C/Java sources, produces DEX, packages native ELF files
only as `lib/arm64-v8a/lib*.so`, and packages managed/compiler/reference files
as data assets. It uses a disposable encrypted signing key with an ephemeral
environment password, verifies signing/alignment, rechecks inputs and records
the first failure in `build-receipt.json`. Outputs and signing material stay
under ignored `work/`. No key or built APK is approved for distribution.

## Device contract and limits

Use only the explicitly assigned device. Refuse a pre-existing
`dev.ror2lab.phonebuildhostfixture`; bind the exact new APK hash and check fresh
storage, backing and reserve before installation. Verify target 33, actual
placement and native hashes. Two cold launches must use distinct data
directories. Independently read logs and require child UID/context equality,
the authored runtime/hash marker, expected native mappings, and no executable
file mapping from writable data. Keep actual values and observation flags
distinct. Remove only the package whose installed bytes match the ownership
receipt; verify absence, unchanged idle game, absent selector and display sleep.

This is a debuggable fixture without permissions or networking. It does not
qualify release delivery, Python/JDK/Clang app hosting, Unity tooling, the real
transform/converter chain in an app, cancellation/resume, tool licensing for
a public package, or security-policy enforcement. The build-tool framework's
implementation is not proposed for game execution. Route A and the desktop
owner-build fallback remain current.
