# Accepted-output reconstruction support

`phone_decode.py` is the current experimental Android shell receiver for one
complete, pinned accepted-output profile. It preserves native IL2CPP code and
Android content by reproducing their exact bytes. It runs no game, Unity Editor,
managed compiler or game native compiler. It adds no game runtime owner.

The receiver is authored public tooling. **Its input package is private
game-bearing data, not a public reconstruction recipe.** The complete result
and failure history are recorded in [J1042](../../../docs/PORTING_JOURNAL.md#j1042--reconstruct-the-complete-accepted-output-on-android).
The [assessment](../../../docs/accepted-build-reconstruction.md) distinguishes
this working replay path from independent PC-input-only production and public
distribution. No package, SDK binary, original input, output or signing key is
included here. File verification makes no ownership/authentication claim.

## Inputs and lifecycle

The four explicit arguments are an already created **new** run directory,
read-only original input root, accepted input manifest and locally owned shell
workspace. All must be inside a workspace named
`/data/local/tmp/ror2-phone-proof-<32 lowercase hex characters>`. Select that
workspace only through its local ownership receipt and the explicitly authorized
device configuration. The receiver refuses symlink components, existing output
files, input/profile drift and escaped manifest paths. Do not point it at a
legitimate installation for output.

Stage a supplied Python 3.11+ interpreter/standard library and the exact codec
below using their permitted acquisition paths. The tested Android interpreter
was Python 3.14. Place the codec at `NEW_RUN/zstd-decompress`. Invoke:

```sh
python3 -I -S phone_decode.py NEW_RUN INPUT_ROOT INPUT_MANIFEST OWNED_WORKSPACE < PRIVATE_STREAM
```

The wire format is `R2DLT01\n` (eight bytes), a big-endian unsigned 32-bit
manifest length, the exact pinned UTF-8 JSON manifest, then one frame per target
in manifest order. SDK-copy rows contain raw SDK bytes. Other rows contain
exactly `patch_bytes` of Zstandard data, optionally using the declared original
PC file as a raw prefix dictionary. Every frame/input/output is hash checked.
Manifest, input and codec pins are explicit constants in the receiver.
Changing profiles requires a new whole-output qualification.

Use a raw bidirectional transport for streamed operation. The lab used
`adb shell -T` with an explicitly selected device and one safely quoted remote
command; `adb exec-out` does not forward standard input. No package is stored
on the phone when frames are streamed. The producer/relay that generated the
private qualified stream remains required local orchestration, documented in
[LOCAL_STATE](../../../docs/LOCAL_STATE.md); no current game build consumes it.

The process owns its new output directory, progress/result receipts and codec
children. It samples combined receiver/codec RSS and available RAM/disk, enforcing
512 MiB family RSS, 512 MiB available RAM, 2 GiB free disk and a 900-second
deadline. Initial admission additionally requires full output/APK capacity.
Codec windows are capped at 256 MB. These are sampled limits, not an OS memory
quota. The receiver terminates only its own codec child on failure/cancellation;
successful and failed outputs remain in the owned run directory for evidence.
No existing package/data is deleted or installed.

The output includes all 840 target files and a deterministic **unsigned** APK
with obsolete signatures removed. It verifies the 571 remaining APK entry
hashes. ZIP compression/alignment, owner signing, installation/update and an
ordinary Android app host are separate, unqualified steps. In particular,
`resources.arsc` compression and resource/native-library alignment must be
resolved before presenting this experimental archive as installable.

The public source differs from the phone-tested source only by repository Ruff
formatting; their complete ASTs match. Exact source hashes and the alias receipt
are retained with the private experiment evidence. The host contracts exercise
real receiver path and stream functions with authored fixtures; they do not
qualify Android process admission or game readiness.

## Reproduce the Android codec

Obtain the official [Zstandard v1.5.7 source archive](https://github.com/facebook/zstd/releases/tag/v1.5.7).
Require SHA-256
`eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3`.
Keep the upstream `LICENSE` notice (BSD-3-Clause option) alongside the resulting
codec. No Unity/NDK material is redistributed by this repository.

From a freshly extracted source directory, source this repository's
`scripts/env.sh`, and select the bundled NDK 21.3.6528147 host toolchain:

```sh
make -C programs -j2 zstd-decompress \
  CC="$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android21-clang" \
  CFLAGS='-O2 -fPIE' LDFLAGS=-pie \
  HAVE_THREAD=0 HAVE_ZLIB=0 HAVE_LZMA=0 HAVE_LZ4=0
```

The qualified ELF is AArch64/API 21, 175,312 bytes, with interpreter
`/system/bin/linker64` and only `libdl.so`/`libc.so` dependencies. Require SHA-256
`721a84f550c0261d6808c9ba82f03ace65890248f7b43b51ca19ff778e201442`;
a differing build needs investigation and an explicit new profile, not a silent
pin update. This compiler builds the reconstruction utility only; it does not
replace the game toolchain or execution backend.
