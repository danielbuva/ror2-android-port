# Retained package assembly producer

Current experimental **host** support for Unity 2021.3.45f2, Android IL2CPP,
.NET Standard 2.1, development builds. This is one complete four-package input
producer, including Burst's required managed post-processor. No current game
build or launcher consumes it. It selects no runtime or final distribution
architecture. Android execution and full-player/native equivalence remain open.

The request may additionally supply `android_tools` from the owner-code backend.
Its explicit `dotnet` launcher replaces only the host executables, with an owned
.NET 8 runtime configuration for the unchanged SDK compiler and post-processor.
All original SDK and package pins remain checked. This is experimental Android
tool support; execution qualification is separate from the host result.

The owner supplies the exact macOS ARM64 SDK installation and source packages:
Burst 1.8.11, Collections 1.2.4, Mathematics 1.2.1 and SDK-builtin UGUI 1.0.0.
The first three are available at Unity's registry package endpoints:

- `https://packages.unity.com/com.unity.burst`
- `https://packages.unity.com/com.unity.collections`
- `https://packages.unity.com/com.unity.mathematics`

Select the exact version's `dist.tarball` and verify its published checksum.
Inspect/extract the owner's archives into versioned package roots; no installer
or package script is needed. Keep the SDK, archives, extracted sources and all
outputs private. Public availability does not grant this project permission to
redistribute SDK/compiler/package binaries. This tool performs no download,
terms acceptance or installation and reads no account credentials.

The private package directory must contain these roots, with each archive's
`package/` contents directly inside its named directory:

```
OWNER_PACKAGES/
  com.unity.burst@1.8.11/
  com.unity.collections@1.2.4/
  com.unity.mathematics@1.2.1/
  com.unity.ugui@1.0.0/
```

Copy UGUI from the owner's
`Unity.app/Contents/Resources/PackageManager/BuiltInPackages/com.unity.ugui`.
The SDK install root contains `Unity.app` and `PlaybackEngines`. Supply a private
request with three explicit canonical absolute paths:

```json
{
  "sdk_install": "/owner/sdk/2021.3.45f2",
  "packages": "/owner/private/packages",
  "output": "/owner/private/new-package-output"
}
```

Run from a public-source checkout:

```sh
python3 tools/phone-build/package-assemblies/produce.py PRIVATE_REQUEST.json
```

`produce.py` owns setup, profile/source/reference/tool validation, compiler and
post-processor children, readback, terminal state and teardown. `profile.json`
pins all 282 runtime sources, seven post-processor sources, required package
precompiled helpers and the 429-file host toolchain closure by normalized
path/hash aggregates. The existing SDK-reference selector independently pins
186 reference files. The 57 SDK builtin package metadata files used for version
defines are pinned separately. Nested same-assembly `.asmref` membership and case-insensitive
source order matter; foreign assembly boundaries and ignored folders are excluded.
The narrow version-define evaluator refuses unqualified present-package ranges.
This fixed profile is not a general Unity assembly-definition implementation.

Only the supplied SDK's Roslyn and managed IL post-processor are executed;
Unity's Editor and inspected game code are never launched. Mono/.NET here are
build tools, with no change to the IL2CPP game runtime. Captured project response
files, compiled assemblies and earlier player outputs are not accepted inputs.
All compiler/post-processor requests are generated from the pinned sources,
SDK references and explicit profile. The post-processor itself is compiled
fresh from the supplied Burst sources.

Output must be new, separate from inputs and have at least 1 GiB plus 128 MiB
free. Children run without shared compiler servers, have a 120-second bound and
are killed/reaped as a process group on interruption/timeout. Logs and completed
outputs remain on failure; reuse/resume is not supported. The owner may retain
or explicitly retire a successful reproducible output after preserving receipts;
this tool never removes an earlier run. No source input is edited. Input hashes
are checked again after the complete successful case.

`inputs.json` binds source/tool/reference hashes and generated compile requests;
per-stage logs and process receipts retain failures. `result.json` identifies
success and all four post-processed DLL hashes. DLLs/PDBs and raw reports stay
private. Success means production completed, not byte equality with an earlier
player, linking, native AOT, phone execution or device/performance acceptance.
The journal owns the complete captured-player comparison and its exclusions.
