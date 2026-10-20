# Wwise Android ABI generator

This explicitly invoked support tool derives a draft Android managed ABI candidate from the
accepted `AK.Wwise.Unity.API.dll`, the matching authorized Wwise Unity Integration Android
declarations, and the pinned Android ARM64 Release plugin. It performs a host-only metadata
transformation. It does not enable production audio, prove native ABI behavior, prove event
playback, or establish middleware readiness. Eleven imports without verified Android
counterparts remain unavailable; full-enable mode is refused.

## Inputs and output boundary

`generate.py` verifies the accepted-input record, complete local inventory, authored original-
assembly recipe, configured legitimate game path, and exact managed assembly hash. It extracts
retained P/Invoke declarations from that assembly with the authored Cecil inspector, parses
the reviewed Android declarations from the local Integration, verifies the hash-pinned
Android `AkOSChar*` string-decoder source, then checks the native plugin hash and exported-name
set. Export membership does not establish a function prototype or implementation behavior.

The authored writer pins the source assembly, policy, and deterministic plan. It refuses
output under the configured game installation, symlinked paths, and overwrites; writes to a
sibling temporary; reopens and verifies the candidate; and atomically publishes only after
verification. It changes reviewed P/Invoke entrypoints, the 88 reviewed
`LPWStr`-to-`LPStr` parameter annotations, and one policy-declared managed call operand.
`AkSoundEngine.StringFromIntPtrOSString(IntPtr)` must match its exact reviewed three-instruction
body and wide-helper operand before that operand is replaced with the Android byte-string
helper. Unexpected signatures, overloads, bodies or operands refuse generation. The 11 imports
without a verified Android counterpart remain unchanged and are reported unavailable.
Round-trip verification includes assembly identity/MVID, types, members, layout, field offsets,
custom-attribute blobs, all method bodies (allowing only the declared call-operand delta),
locals, exception handlers, references, imports and resources.

Outputs must be new ignored paths beneath repository `work/`. The policy at `recipe/wwise-
android-abi.json` is public authored metadata and pins the accepted input and source hashes.
No SDK, native library, accepted-input record, generated plan, candidate, or game-derived
content is included.

## Host invocation

Use the repository toolchain through `scripts/env.sh`. The generator resolves `dotnet` from
`PATH` or `--dotnet`, and Unity-bundled Mono.Cecil from `UNITY_EDITOR`, `WWISE_CECIL`, or
`--cecil`. Multiple bundled Cecil versions require an explicit selection; the command below
selects the pinned 0.11.1 assembly. The Integration source, native plugin, and NDK `llvm-nm`
are local inputs and are never copied by this tool.

```sh
source scripts/env.sh
mkdir -p work/coordination/wwise-abi-generator
python3 tools/wwise-android-abi/generate.py \
  --android-source work/wwise/unity-android-3208-extracted/Wwise/API/Runtime/Generated/Android/AkSoundEnginePINVOKE_Android.cs \
  --android-os-string-source work/wwise/unity-android-3208-extracted/Wwise/API/Runtime/Handwritten/Android/AkSoundEngine.cs \
  --native-so work/wwise/unity-android-3208-extracted/Wwise/API/Runtime/Plugins/Android/arm64-v8a/Release/libAkSoundEngine.so \
  --llvm-nm "$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-nm" \
  --cecil "$(dirname "$UNITY_EDITOR")/../MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll" \
  --output work/coordination/wwise-abi-generator/plan.json \
  --candidate work/coordination/wwise-abi-generator/candidate.dll
```

Plan and candidate paths must be new, ignored files beneath `work/`; leaf names must be 1–128
characters matching `[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)*`. This portable lowercase
ASCII contract rejects uppercase, Unicode, trailing dots, repeated dots, and other ambiguous
spellings before accepted-input or source analysis. Existing parent paths are compared with
`os.path.samefile` to reject aliases. The default writer accepts only the exact reviewed
production profile and cannot mark it ready for full enablement. Its synthetic profile is
compiled only by tests with `WWISE_TEST_ONLY` and is not exposed by the default production
writer.

## Offline host tests

Eight synthetic tests require no game installation, Wwise SDK, or proprietary input. They check
parameter/return `LPArray` contracts, reject changed marshal properties, verify filename and
path guards, exercise the declared decoder rewrite and reject wrong operands, body shapes and
overloads. Tests use the
selected `dotnet` and Unity-bundled Mono.Cecil. Generated build and fixture scratch is placed
under ignored `work/tests/wwise-android-abi/` and removed after each test run.

```sh
source scripts/env.sh
WWISE_DOTNET="$(command -v dotnet)" \
WWISE_CECIL="$(dirname "$UNITY_EDITOR")/../MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll" \
python3 tools/wwise-android-abi/test_synthetic.py -v
```

The tool is separate from `tools/assembly-transforms`, so it cannot enter that project's
wildcard compile or change default recipes or output hashes. It is current support tooling,
not a current game-build dependency. No Unity project, recipe, build, device, or tracked
default transform is changed by invoking its host action.
