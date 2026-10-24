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
hashes. This initial archive is not install-ready: it compresses `resources.arsc`.
Use the separate assembly step below before alignment/signing. Ordinary Android
app execution and installation/update remain unqualified.

The initial public source differs from the phone-tested source only by Ruff
formatting, with an identical AST and retained alias receipt. Final review then
found and fixed a startup containment defect: lexical ancestry accepted `..`.
The current receiver rejects parent components/symlinks, resolves every existing
root strictly and checks canonical receipt-owned ancestry before opening output.
All original stream/reconstruction functions and the full reconstruction body
retain identical ASTs; the added startup guard has authored host coverage and
awaits device qualification. Exact versions and receipts remain private. These
host contracts do not establish game readiness.

## Produce meshes directly from original PC bundles

`mesh_produce.py`, `unity_bundle.py` and `unity_mesh.py` own current experimental
PC-input-only mesh production. They use Python 3.11+ standard-library modules
on the host and Android, with no Editor, UnityPy, SDK or target-content input:

```sh
python3 -I -S -B tools/phone-build/accepted-output/mesh_produce.py \
  --profile recipe/owner-meshes.json --profile-sha256 RECIPE_SHA256 \
  --pc ORIGINAL_PC_ROOT --output NEW_PRIVATE_OUTPUT
```

Stage those three sibling Python files and the audited recipe on Android using
the owner's permitted interpreter acquisition path. Explicitly select the
authorized device and receipt-owned workspace for lab staging. The original PC
root is read-only; the output must be new and separate. File hashes identify
the accepted input and make no ownership or authentication claim.

The recipe selects 652 original bundles and produces 13,231 of 13,233 accepted
mesh records. Two tangent/importer cases are explicitly excluded. Operations
preserve original field bytes except declared import flags, collision-cache
removal, names/resource references, vertex stream inlining, channel dimension
normalization and float normal/tangent half conversion. Half conversion rounds
halfway away from zero. Source schema controls field extents, including nested
alignment. The reader qualifies little-endian serialized v22 and UnityFS 7/8
from Unity 2021.3 with raw/LZ4 compression; other compression is refused.

The process checks every selected original file before/after use, bounds reads
and decompressed blocks to 64 MiB, retains two blocks and requires all generated
object hashes to match. It writes `objects.bin`, `resources.bin`, their
`index.jsonl` and a terminal complete/failed `result.json`. All persisted extents
are re-read; failed outputs are retained. It requires expected object capacity
plus 2 GiB free before starting. Peak RSS uses the platform's native
`resource.getrusage` units. Exit tears down the only producer process.

These game-derived packs remain private. They are inputs for a future bundle
assembler, not UnityFS bundles, a replacement private replay packet, or an APK.
[J1070](../../../docs/PORTING_JOURNAL.md#j1070--produce-the-accepted-mesh-cohort-from-original-pc-bundles-on-android)
records host and phone qualification. Remaining meshes, non-mesh content,
bundle assembly, native game-code phone production and the complete owner
installation remain separate gates. No current game build consumes this path.

## Acquire the three SDK-copy inputs

`sdk_inputs.py` is current experimental acquisition support for an owner's exact
[2021.3.45f2 Android support component](https://unity.com/releases/editor/whats-new/2021.3.45f2).
Obtain it directly from the provider under the owner's applicable terms. The
helper performs no download or license acceptance and includes no SDK binaries.
It requires the fixed component size/SHA-256 declared in its source, validates
container identity, streams the component and writes only the three pinned
SDK-copy files under `PlaybackEngines/AndroidPlayer/` in a new private root:

```sh
python3 -I -S tools/phone-build/accepted-output/sdk_inputs.py \
  --component OWNER_DOWNLOADED_ANDROID_SUPPORT.pkg --output NEW_PRIVATE_SDK_ROOT
```

Use Python 3.11+ and an existing private parent directory outside the original
game installation. Keep the output and receipt ignored. Success independently
rehashes every selected file; failure retains the new attempt. Existing output,
unknown input, unsafe paths, selected symlinks, duplicate/missing members and
content drift refuse. The process exits after its complete/failed receipt;
there is no service, installer-script execution or current game-build mutation.

[J1064](../../../docs/PORTING_JOURNAL.md#j1064--acquire-exact-generic-android-sdk-inputs-without-installing-the-editor)
records the complete host component case. Android execution is unqualified.
The directory can supply `package.py`'s explicit SDK root; it is not the complete
compiler, game/content producer, Android converter or public SDK distribution.

## Reproduce and stream a private packet

`package.py create` reproduces every compressed frame from explicit accepted
output files, an existing pinned private profile, owner PC files, supplied SDK
and the pinned upstream encoder. It verifies the entire declared PC inventory
before and after creation, refuses input/output overlap and existing output,
and requires every produced frame to match the qualified frame hash. It copies
the exact manifest bytes; timing goes into a separate creation receipt. This
reproduces a packet, not the original Android target's independent derivation.
The profile and accepted output files remain required private local inputs.

```sh
python3 -I -S tools/phone-build/accepted-output/package.py create \
  --manifest PRIVATE_PROFILE --manifest-sha256 PROFILE_SHA256 \
  --targets OWNER_TARGET_ROOT --pc ORIGINAL_INPUT_ROOT --sdk OWNER_SDK_ROOT \
  --codec PINNED_ZSTD_ENCODER --output NEW_PRIVATE_PACKET
python3 -I -S tools/phone-build/accepted-output/package.py stream \
  --package PRIVATE_PACKET --manifest-sha256 PROFILE_SHA256 --sdk OWNER_SDK_ROOT \
  > PRIVATE_STREAM
```

`stream` verifies all inputs before writing the header, then checks each file
again as it emits the receiver protocol. It writes only binary protocol bytes to
stdout. A caller may pipe this directly to the owned receiver without saving
another packet copy. Keep pipeline failure propagation enabled and retain both
producer and receiver results. A transport's exit alone does not prove decoding.
The encoder is a separate supplied host tool pinned by the private profile;
it is not the Android decoder binary. Authored host integration fixtures cover
SDK copies, original-file deltas, independent frames, exact framing, roundtrip
content, damaged-frame refusal and preserved inputs/outputs.

## Assemble, align and sign

`assemble.py` rebuilds the same hash-bound non-signature APK entries into a new
archive, storing `resources.arsc` uncompressed on a verified 4-byte local-data
boundary. Android [requires that storage/alignment for target API 30+](https://developer.android.com/about/versions/11/behavior-changes-11#compressed-resource-file).
It preserves all entry contents, refuses output/input overlap and existing
output, removes stale v1 signatures and independently reopens/hashes its result.
Native libraries retain the qualified profile's compressed packaging policy;
this is not a general manifest/native-page-size migration tool.

```sh
python3 -I -S tools/phone-build/accepted-output/assemble.py \
  --manifest PRIVATE_PROFILE --manifest-sha256 PROFILE_SHA256 \
  --targets RECONSTRUCTED_TARGET_ROOT --output NEW_UNSIGNED_APK
```

Run supplied `zipalign -p -v 4 NEW_UNSIGNED_APK NEW_ALIGNED_APK`, then supplied
`apksigner` with a private, persistent owner key. [Alignment precedes signing](https://developer.android.com/tools/zipalign).
Enable v1 **and** v2/v3 to cover the accepted manifest's declared older API
range and current Android requirements; disabling v1 makes default verification
fail for that full range even though newer signature blocks exist. Pass key
passwords through an environment or protected interactive input, never source,
command literals or published logs. Run `apksigner verify --verbose` and
`zipalign -c -p -v 4` on the final signed file, then independently verify all
non-signature entry hashes. Freshly generated signature entries are expected.
Never reuse a repository author's key for a public owner's install, and retain
the owner's signing identity across updates.

The complete target has passed host assembly, canonical alignment and v1/v2/v3
signature verification with the existing local lab identity read-only; no key
was sent to Android. This qualifies the packaging mechanism on the host, not
phone-side signing, normal installation/update, 16 KiB device support or game
behavior/performance. The accepted game code and rendering content stay intact.

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
