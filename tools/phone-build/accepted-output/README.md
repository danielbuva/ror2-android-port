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

## Construct serialized files and UnityFS containers

`unity_write.py` is a current experimental structural writer. It receives
explicit source-derived type metadata, destination identities/order and already
produced object/resource streams. It does not derive those relationships or
read an accepted target as a content provider. `write_serialized` preserves
object-table order separately from physical body order, writes little-endian
v22 metadata and the big-endian envelope, and streams bodies into their declared
extents. It adds zero padding without adding final object alignment.

`write_bundle` streams ordered members through globally consecutive 128 KiB
blocks. Its current accepted-target policy uses UnityFS 8, HC12, raw fallback
when compression expands a block, a generated block directory and zero alignment
padding. Per-bundle engine versions remain explicit. Raw and fast-LZ4 policies,
version 7 and block-info-at-end are also supported by the structural interface.
The writer retains only one pending block and the directory in memory, with
compressed data in a temporary file beside the output; exit removes that file.
It does not alter runtime, shader, texture, animation or ownership semantics.

Build the bounded persistent codec worker from an explicitly supplied public
[LZ4 v1.9.4 archive](https://github.com/lz4/lz4/releases/tag/v1.9.4):

```sh
python3 -I -S tools/phone-build/accepted-output/build_bundle_lz4.py \
  --lz4-archive OWNER_LZ4_ARCHIVE --compiler EXPLICIT_COMPILER \
  --output NEW_PRIVATE_TOOL_OUTPUT
```

The builder checks the archive pin and all compiler/source hashes, retains the
BSD license, notices and compiler logs, and writes a complete/failed receipt.
Android compilation additionally selects `--android-tool-root` through the
existing acquired native Clang 21 layout. No SDK codec or Unity project is used.
The Python `codec(path, sha256)` context owns one helper process, 64 MiB request
bounds, per-block deadlines, independent decoded-byte verification and teardown.
Object provenance, new final-output admission, drift checks and retained failure
receipts belong to the calling producer. Structural qualification against
all 133 accepted bundles passes byte-exact in J1116 with 198.125 MiB peak
host RSS. This is an accepted-record roundtrip control, not PC-input-only
production or phone qualification.

## Produce the first complete source-only bundle

`object_produce.py` currently qualifies the complete pickup-droplet and
player-death-effect bundles from original PC records. The audited recipe contains original selectors, checked
PPtr relationships, destination identities/dependencies and comparison hashes.
All content bodies and embedded type metadata come from the original input;
the producer generates AssetBundle container/preload metadata and relocates
only checked pointers. It generates the complete serialized member and writes
the UnityFS with the pinned native helper:

```sh
python3 -I -S -B tools/phone-build/accepted-output/object_produce.py \
  --profile recipe/owner-pickup-objects.json --profile-sha256 RECIPE_SHA256 \
  --pc ORIGINAL_PC_ROOT --codec NATIVE_BUNDLE_LZ4 \
  --codec-sha256 CODEC_SHA256 --output NEW_PRIVATE_OUTPUT
```

The output retains `objects.bin`, `index.jsonl` and `layout.json` in the existing
pack interface, plus the actual `payload/pickup-droplet-lab` target-tree file.
The layout's type hash/tree/script identity and external GUID bytes are encoded
as hexadecimal for JSON transport; they are source-derived output, never public
target templates. Explicit source/recipe/codec admission and 2 GiB reserve
precede processing. Every body, serialized member, final bundle and persisted
extent must match its comparison hash; source hashes/stats are checked before
and after. A complete/failed `result.json` retains state, failure retains its
output, and the codec context reaps its child. The second slice uses
`recipe/owner-death-effect-objects.json` through the same command and owner. Its original rooted graph contains 36 bodies and a generated
container; only checked references change. Its container requires external
preloads before local preloads. These complete bundle slices are not a general
object converter. Their dependent bundles and full target tree remain separate
gates.

J1120 extends the same owner to three more complete source-derived bundles:
`owner-objective-ui-objects.json`, `owner-teleporter-indicator-objects.json`
and `owner-generic-pickup-objects.json`. Each uses original PC bodies/types,
checked references and explicit rooted container relationships. Sprites reuse
the player owner's crop/importer policy. GenericPickup additionally omits its
one checked original AkGameObj component; remaining original values are retained.
The qualified dummy material keeps its original keywords in the invalid list.

Supply each independently produced texture pack explicitly, repeating
`--record-pack PACK_DIRECTORY RESULT_JSON_SHA256` after the command above.
Objective UI and generic pickup require the RGBA pack; teleporter indicator
requires RGBA and Alpha8 packs. Successful, input/profile-bound receipts and
all pack file hashes are checked before/after production. Original PC records
supply their native type metadata; packs supply texture bodies and resource
extents. The owner assembles those resource members and records provider receipt
hashes in its own result. No comparison tree or replay file is a provider.
These six full bundles are host byte-exact to J850; complete catalog/remaining
content production and phone/runtime qualification remain open. Unity's textual
build-side `.manifest` files are excluded by the existing APK readiness checker;
their build-cache hashes are not reproduced by this slice.

`owner-enemy-reward-objects.json` uses the same owner with
`--sdk OWNER_UNITY_APP_ROOT`. Its pinned SDK input is
`Contents/Resources/unity editor resources`; the Editor is never started.
Original MonoScript and MonoBehaviour selectors feed the existing
`scripts/lab/script_identity.py::properties_hash` helper. Original identity
strings and custom schema fields, combined with the SDK editor base schema,
generate the script properties/type hash. The recipe includes no hash literal
or target type template. Every other script/type byte remains source-owned.
SDK hashes are checked before/after, and the complete serialized member/bundle
still must match its comparison hashes. Physical preload partitions and sorted
container paths are independent; native default resources retain their SDK
GUID/path rather than an AssetBundle archive path. J1132 qualifies all 203
objects and the complete 65,286-byte enemy-reward bundle raw-exact on the host,
bringing the complete source bundle count to seven. Phone qualification remains open.

## Produce named player-data files

`player_data.py` produces 175 canonical `apk/assets/bin/Data/...` files:
SDK default resources, three fresh converter resource files, two script metadata
JSON files derived from original PC metadata plus authored initialization/order,
the embedded font serialized file, two original line-breaking TextAssets, the
authored runtime and bootstrap JSON TextAssets, 64 standalone Sprite files,
the original TimerStringFormatter, nine original TMP objects, 14 materials, the six-object SDK built-in UI file and 72 standalone
textures from existing source-produced packs. The font, material and texture bodies and their
type identities/dependency come from one original PC bundle; only
four checked reference identities change. The generic writer generates its
tree-stripped Android metadata and object layout. Original Sprites retain
geometry/UVs, regenerate their importer GUID/local identity from the
destination filename and relocate one checked texture reference. Their texture
providers remain separate inputs to full composition. The authored full-rectangle
Sprite generates four corners and two triangles from original bounds and
recovered pivot/border/pixel scale, matching the existing HUD policy. The runtime TextAsset
formats the pinned sibling `runtime-config.json` through the existing authored
JSON policy. The pinned `owner-bootstrap.json` follows the existing
`generate_build_bootstrap` policy with the public fixed attempt identity and
four original preload keys absent from the original catalog. These are minimum
source relationships, not object bodies or a target byte template.

The English Strings TextAsset reads all pinned JSON files from the current
original `StreamingAssets/Language/en` directory. The authored builder's
qualified collation and later-file replacements determine its contents; no
cached table, historical installation or game text is distributed. Original
trailing commas are accepted without changing quoted values. The complete
file set and source hashes must match the profile. The fifth font-material
clone likewise preserves every original scalar, including Sharpness. Both
files differ from J850 because their current original inputs changed; historical
originals qualify the same transformation separately. This does not make either
file an exact J850 match or qualify phone production.

```sh
python3 -I -S -B tools/phone-build/accepted-output/player_data.py \
  --profile recipe/owner-player-data.json --profile-sha256 RECIPE_SHA256 \
  --pc ORIGINAL_PC_ROOT --sdk OWNER_ANDROID_PLAYER_SDK \
  --builtin-extra OWNER_SDK_RESOURCES/unity_builtin_extra \
  --editor-resources "OWNER_SDK_RESOURCES/unity editor resources" \
  --converter FRESH_CONVERTER_OUTPUT \
  --converter-receipt-sha256 CONVERTER_RECEIPT_SHA256 \
  --texture-pack UNCOMPRESSED_PACK UNCOMPRESSED_RECEIPT_SHA256 \
  --texture-pack ALPHA_ETC_PACK ALPHA_ETC_RECEIPT_SHA256 \
  --texture-pack RGB_ETC_PACK RGB_ETC_RECEIPT_SHA256 \
  --texture-pack RGBA_PACK RGBA_RECEIPT_SHA256 \
  --texture-pack RGBA_MIP_PACK RGBA_MIP_RECEIPT_SHA256 \
  --output NEW_PRIVATE_TARGET_TREE
```

Each texture directory is an existing producer's `objects.bin`, `resources.bin`,
`index.jsonl` and successful `result.json`; pass the hash of that receipt. The
profile selects producer profile hashes and bundle/member/path IDs, never
physical private paths or pixel literals. Uncompressed/RGB/Alpha8 producers are
documented below. The 54 RGBA selections use the separately audited, landed
[PR75 producer/profile](https://github.com/danielbuva/ror2-android-port/pull/75).
The built-in UI input is the full pinned file from the owner-supplied exact
SDK's editor Resources directory; no Editor process or project is used. Only
its selected original Texture/Sprite fields survive editor-field stripping.
Material clones use the existing authored importer names and derive retained
texture properties from the assigned original Shader declarations, preserving
all other source values. This supplies no compiled shader programs.

The two native shader-selection TextAssets read original material keywords and
Shader declaration metadata through embedded source type trees. Their sibling
`owner-player-shader-manifests.json` recipe pins original providers and object
identities without storing keyword inventories or shader programs. The shared
pure policy in `scripts/lab/shader_metadata.py` also serves the existing shader
generators. Preserve this repository-relative helper path when staging the
player owner on Android, and keep the pinned selector recipe beside the player
profile. No UnityPy, cached inventory, compiler or Editor is needed for these
two JSON files.

Six selected TMP fonts derive managed properties hashes from their original
MonoScript class/namespace/assembly identity, original custom schema and the
exact SDK native MonoBehaviour base. Supply the full pinned SDK
`unity editor resources` explicitly with `--editor-resources`; the existing
built-in UI provider lacks this schema. The profile's source descriptors select
original script and SDK records; no destination type hash is an input. The
shared `scripts/lab/script_identity.py` computes the hash. Checked original
script relationships and input rechecks precede completion. Other scripted
objects retain their original type hashes.

No texture producer is changed by this assembly step. Streamed records retain
all native fields and move only their verified produced pixels inline; existing
inline records remain unchanged. Native type metadata comes from the already
selected original PC font bundle. Receipt/input/profile and complete pack hashes,
selected extents and source stream descriptors are verified before use; provider
hashes are checked again before completion. A missing/failed/changed pack refuses.

Stage the player owner and its existing Python dependencies at their
repository-relative paths for an Android replay, including
`scripts/lab/shader_metadata.py` and `scripts/lab/script_identity.py`. Keep the
pinned `runtime-config.json`, `owner-bootstrap.json` and
`owner-player-shader-manifests.json` beside the selected player profile. No native codec is
needed for this assembly step; its texture producers retain their own codec/SDK
requirements. The converter input is its successful `result.json` and its
three `data/Resources/...` outputs, not files extracted from an accepted APK.
The original PC root, SDK and converter are read-only and disjoint from the new
output. Input hashes, converter completion, source/body/reference relationships,
capacity and persisted readbacks precede the complete/failed receipt. Failure
retains output; exit ends the producer. These host-qualified files do not
close the remaining player-data, shader, animation or phone-install gates.

Both producers emit target paths accepted by the existing owner-APK readiness
checker. A partial tree remains incomplete: no missing file is supplied from
the private replay tree. Full-source assembly and device/runtime qualification
remain required before promotion.

J1117 extends this owner to 75 files, including all 63 PC-derived standalone
Sprites, an authored full-rectangle Sprite and one original TimerStringFormatter object. Explicit per-file source
selectors retain their actual receipt provenance. A source render-data crop
selector recovers standalone coordinates through pinned AssetRipper arithmetic;
no target geometry/pixel/coordinate values are supplied. The original scripted
object retains its type hash and fields with a generated external script table.
The same `object_produce.py` invocation accepts the audited
`owner-teleport-material-objects.json`: its qualified dummy shader demotes the
original keyword strings while preserving material values. All 75 player files
and that full bundle are host byte-exact; phone/runtime gates remain open.

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

## Produce Avatars directly from original PC bundles

`avatar_produce.py` is a current experimental source-only producer. Use Python
3.11+ and stage it alongside `mesh_produce.py`, `unity_bundle.py` and
`unity_mesh.py`, with the audited `recipe/owner-avatars.json`:

```sh
python3 -I -S -B tools/phone-build/accepted-output/avatar_produce.py \
  --profile recipe/owner-avatars.json --profile-sha256 RECIPE_SHA256 \
  --pc ORIGINAL_PC_ROOT --output NEW_PRIVATE_OUTPUT
```

Setup checks recipe/input pins, separate new output and expected size plus
2 GiB reserve. The producer reads bounded source body ranges from 178 original
bundles: 172 records remain byte-identical and 56 reorder complete existing
`m_TOS` hash/string entries. All native rig/pose data, strings, padding and
surrounding bytes come from the original body. Orders must be bijective and
table bounds exact. There is no target-content, SDK, Editor or UnityPy input.

It checks original bundle hashes before/after, requires every output hash and
re-reads persisted `objects.bin` extents through `index.jsonl`. A terminal
complete/failed `result.json` retains outputs; process exit is teardown. Keep
all output private. Android lab staging requires explicit authorized selection
and the existing workspace/interpreter receipts. [J1075](../../../docs/PORTING_JOURNAL.md#j1075--produce-every-accepted-avatar-from-original-pc-bundles-on-android)
qualifies all 228 records on host and phone. Packs require later complete bundle
assembly; no current build or runtime consumes them.

## Produce uncompressed textures directly from original PC bundles

`texture_produce.py` owns a current experimental PC-input-only producer for
the qualified uncompressed Texture2D cohort. Use Python 3.11+ on macOS, Linux
or Android, staging it alongside `mesh_produce.py`, `unity_bundle.py` and
`unity_mesh.py`, the audited recipe and the public JPEG tool described below:

```sh
python3 -I -S -B tools/phone-build/accepted-output/texture_produce.py \
  --profile recipe/owner-uncompressed-textures.json --profile-sha256 RECIPE_SHA256 \
  --pc ORIGINAL_PC_ROOT --output NEW_PRIVATE_OUTPUT \
  --jpeg-codec PUBLIC_JPEG_TOOL --jpeg-codec-sha256 TOOL_SHA256
```

The producer copies original raw pixel/mip bytes, decodes BC1 top mips to RGB,
extends transparent RGB with fixed cardinal Manhattan jump flooding, or applies
the source export's JPEG roundtrip. Dilation propagates original nonzero-alpha
texel coordinates at offsets 16, 8, 4, 2 and 1, retains the current coordinate
on equal distance, then considers left, right, preceding row and following row.
Only RGB changes; source alpha is retained. This is a fixed qualified policy,
not a general texture importer. [Microsoft's BC1 specification](https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression#bc1)
defines the authored decoder's endpoint palettes, selectors and transparent
RGB projection. Metadata work preserves untouched fields and changes only
declared name, image size/format, alpha/usage and inline/resource placement.
The JPEG tool uses public stb/IJG sources; no Editor, UnityPy, Unity SDK or
target-content input is used.

`build_texture_jpeg.py` owns the current native JPEG-tool build. Supply these
unchanged public sources, obtained separately under their included terms:

| Provider | SHA-256 |
| --- | --- |
| [IJG 9b source archive](https://www.ijg.org/files/jpegsrc.v9b.tar.gz) | `566241ad815df935390b341a5d3d15a73a4000e5aab40c58505324c2855cbbb8` |
| [stb image writer at 003501f6](https://raw.githubusercontent.com/nothings/stb/003501f6d7a8668ce8b6d875e34dd97ad0d5d5b5/stb_image_write.h) | `cbd5f0ad7a9cf4468affb36354a1d2338034f2c12473cf1a8e32053cb6914a05` |

```sh
python3 -I -S -B tools/phone-build/accepted-output/build_texture_jpeg.py \
  --jpeg-archive JPEG_SOURCE_TAR_GZ --stb-header STB_IMAGE_WRITE_H \
  --compiler EXPLICIT_C_COMPILER --output NEW_PRIVATE_TOOL_OUTPUT
```

On Android, add `--android-tool-root OWNED_TOOL_ROOT` for the existing native
Clang 21/sysroot/linker policy; select its `usr/bin/clang-21` explicitly. Host
Clang and that Android policy use the same scalar C sources and disable fused
floating-point contraction. The builder verifies provider/source/tool hashes,
extracts only the named regular source/header members, adds authored Unix
configuration and the `texture_jpeg.c` wrapper, bounds/reaps the compiler and
retains build logs/result. It performs no download, Editor operation or game
execution. The new output must be outside its input files. Keep its notices
with the tool: **this software is based in part on the work of the Independent
JPEG Group**. The full IJG README and unchanged stb header retain their terms;
the wrapper and configuration are authored additions.

`texture-jpeg WIDTH HEIGHT` reads exactly one bottom-up RGB image from stdin,
encodes a top-down quality-90 JPEG and decodes with IJG 9b fast integer IDCT
and ordinary chroma upsampling. It writes bottom-up RGB to stdout. Input/output
dimensions are bounded; the helper has no file-output interface. The producer
requires its explicit SHA-256, bounds the child and verifies the resulting
pixel extent/hash. No codec executable or game JPEG is tracked or shipped as
a reconstruction literal. Set `ROR2_TEXTURE_JPEG` to the locally built tool's
absolute path to run the authored native-codec host control; dependency-free
CI skips that control explicitly.

Setup checks recipe/input pins, new separate output and expected object/resource
capacity plus 2 GiB reserve. Source hashes/stat checks run before/after use;
every output must match its pinned object and pixel hash. Persisted extents
are independently reread through `index.jsonl` in `objects.bin` and
`resources.bin`. Terminal `result.json` records success/failure, elapsed time
and peak process RSS in bytes; failed outputs remain and process exit is
teardown. Keep all generated data private. Android lab staging requires
explicit authorized selection, workspace ownership and a permitted interpreter.

The profile now covers all 399 uncompressed records. These packs require a
later complete bundle assembler and do not qualify other
texture formats, game execution or the full phone-only owner installation.
No current game build consumes this path.

The complete host/phone case, public-source Android codec build and controls
are recorded in
[J1079](../../../docs/PORTING_JOURNAL.md#j1079--complete-uncompressed-texture-production-from-pc-bundles-on-android).
The current explicit profile targets the accepted J850 content; a later target
needs its own reviewed profile. No current game build consumes these packs.

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

## Build the standalone SDK tool runner

Current experimental support for **build tools only**. The game retains native
IL2CPP ARM64 execution. The runner starts explicit owner-supplied standalone
libraries/programs; it registers no executable handler and opens no Editor or
Unity project. Shell qualification is recorded in [J1081](../../../docs/PORTING_JOURNAL.md#j1081--run-owner-supplied-standalone-sdk-tools-through-a-public-android-runner).
Ordinary app execution and each further SDK tool require their own qualification.

Acquire unchanged public [Box64](https://github.com/ptitSeb/box64) source at
`420eda69ff51ab5d5a7cbc3dee2e70433be3411d` (MIT). Supply the pinned Unity SDK
NDK 21.3.6528147, public host CMake and LLVM archive/strip programs. On the
supported macOS host, source `scripts/env.sh`, then choose explicit paths:

```sh
python3 tools/phone-build/accepted-output/build_sdk_runner.py \
  --source "$BOX64_SOURCE" --ndk "$ANDROID_NDK_ROOT" \
  --cmake "$CMAKE" --archiver "$LLVM_AR" --ranlib "$LLVM_RANLIB" \
  --stripper "$LLVM_STRIP" --output "$NEW_RUNNER_OUTPUT"
```

The new output contains `box64`, upstream `LICENSE.txt`, commands, logs and a
complete/failed receipt. The builder pins its build tools before/after, targets Android
API 28, uses four host compile jobs and terminates its compiler process group on
failure/timeout. It retains outputs. Preserve multicall executable names such
as `llvm-ranlib` and `llvm-strip`; resolving them to `llvm-ar`/`llvm-objcopy`
changes command dispatch. The SDK compiler/sysroot/LLD remain selected; public
host archive tools avoid the SDK's old archiver failure on current macOS.

The owner may separately acquire the official
[Linux 2021.3.45f2 SDK archive](https://download.unity3d.com/download_unity/88f88f591b2e/LinuxEditorInstaller/Unity-2021.3.45f2.tar.xz)
(3,263,644,788 bytes), require SHA-256
`faaeafc17dd251ae0d3489ef762929f393928ad19b60d1f9b4155bb7d25d76d3`,
and select only these members. Extracting them does not install or start the
Editor. SDK binaries remain explicit private inputs and are not redistributed.

| Member | SHA-256 |
| --- | --- |
| `Editor/etccompress.so` | `4dc31e0bc2591141648b238fa158fe700dd37c13f62fe3f165618ba85c1a2293` |
| `Editor/Data/Tools/UnityShaderCompiler` | `c80dd80426848a1cd83eb7d9a430b66f06b6221d9ef85ed0b41ddcb255dd7dfa` |
| `Editor/Data/Tools/libdxcompiler.so` | `79f53a5e8c05adbb92af99127bf3889625c7977d1d161f4d898fe5eaade6bfce` |
| `Editor/libfreeimage-3.18.0.so` | `5a0677dcb425b4b8a8776a4bfbc98b8d7ec8509727afb3ac1e67a9cefceba1b3` |

The bounded `sdk_texture_codec.c` control adapter takes the SDK image descriptor
**by value**. Build its Android x86 entry point with the same NDK:

```sh
"$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/clang" \
  --target=x86_64-linux-android28 -fuse-ld=lld -std=c11 \
  -Wall -Wextra -Werror -O2 -fPIE -pie -Wl,--export-dynamic \
  tools/phone-build/accepted-output/sdk_texture_codec.c -ldl \
  -o "$NEW_CODEC_OUTPUT"
```

Box64's Android build expects a Bionic entry point. This adapter supplies
standard GNU errno/assertion entries and C-locale message identity needed by
this library; assertions still abort. Supply Debian Bullseye's `libgcc-s1`
10.2.1-6 amd64 package from its official package index, requiring package SHA-256
`e478f2709d8474165bb664de42e16950c391f30eaa55bc9b3573281d83a29daf`.
Its `libgcc_s.so.1` requires SHA-256
`2d771c2e232fce107c7ec7f9a64b9a804e6d6737063088a2d8096b149a0af8cd`.
Keep provider copyright/license notices with any redistributed public runtime.
No SDK implementation is incorporated into the authored adapter.

In a leased, explicit owned Android workspace, select the runtime library path
and call `box64 CODEC SDK_LIBRARY WIDTH HEIGHT FORMAT SPACE`, feeding exactly
`WIDTH * HEIGHT * 4` RGBA bytes on stdin and retaining compressed stdout privately.
Format `0` is ETC1 RGB; `2` is ETC2 RGBA8. Space `0` selects gamma/perceptual;
`2` selects the qualified normal-data path. The adapter uses backend 1/quality 1,
checks output size and refuses malformed input without emitting texture bytes.
J1081's Linux RGBA outputs differ in decoded pixels from the accepted target;
this diagnostic is **not** an admitted RGBA producer or receipt equivalence.
ShaderCompiler and Burst execution remain separate open gates. No current game
build consumes this runner or the diagnostic output.

## Produce Alpha8 textures directly from original PC bundles

Current experimental source-only content producer, qualified for the complete
4,326-record **source Alpha8/single-mip** target cohort in
[J1082](../../../docs/PORTING_JOURNAL.md#j1082--produce-the-complete-alpha8-texture-cohort-from-pc-bundles-on-android).
The explicit `recipe/owner-alpha-textures.json` profile requires SHA-256
`fa23bc2cdc71234e3a5d4a084519a63bb59c6ef321e790fb964c295c8bd1d51a`.
It reuses 82 original texture bodies/pixel extents from nine original PC bundles,
with unchanged-field matching and explicit target name/storage relationships.
There are no pixel samples, encoded blocks or target byte frames in the recipe.

Acquire the unchanged public [ETCPACK 2.74 source archive](https://codeload.github.com/Ericsson/ETCPACK/tar.gz/14a64d9d19318fb9f81ce339b7103ffa0f1781d7)
(995,165 bytes), requiring SHA-256
`5fc5cad3e8ccd930a82f38da208f24c35b9a565a622092d0d4a37847000c98d2`.
Its Software License Agreement permits binary compression products and restricts
source redistribution. Encoder source is not vendored here. Keep the retained
provider license/notice beside the locally built codec:

```sh
python3 tools/phone-build/accepted-output/build_texture_etc.py \
  --archive "$ETCPACK_ARCHIVE" --compiler "$CXX_COMPILER" \
  --output "$NEW_ETC_CODEC_OUTPUT"
```

On Android add `--android-tool-root "$OWNED_TOOL_ROOT"` and select that root's
`usr/bin/clang-21`. The existing owned public Clang/sysroot/libc++/linker closure
is required. The sysroot is the tool root above `usr`; selecting `usr` duplicates
C++ header search paths. The builder extracts only four unchanged source/header
files plus the license, supplies an authored timing compatibility header for the
unused upstream CLI, and builds an authored pipe adapter. Compiler children are
bounded and terminated as process groups; complete/failed receipts, logs,
licenses and private outputs are retained. No Unity SDK encoder is needed.

```sh
python3 -I -S -B tools/phone-build/accepted-output/texture_produce.py \
  --profile recipe/owner-alpha-textures.json \
  --profile-sha256 fa23bc2cdc71234e3a5d4a084519a63bb59c6ef321e790fb964c295c8bd1d51a \
  --pc "$ORIGINAL_PC_ROOT" --output "$NEW_TEXTURE_OUTPUT" \
  --etc-codec "$ETC_CODEC" --etc-codec-sha256 "$ETC_CODEC_SHA256"
```

The pinned source export maps Alpha8 samples to original alpha plus zero RGB.
The native adapter generates the generic black color block and compresses those
original alpha samples; it reads no target bytes. The common producer verifies
all source files and produced/persisted body/resource extents, then retains
private packs, index and terminal receipt. Existing output and wrong codec pins
refuse; wrong pins refuse before output creation. Setup and teardown follow the
uncompressed producer above. On Android explicitly lease the assigned device
and use the existing owned interpreter/runtime/library path. Nine authored
texture contracts include three non-game alpha patterns and malformed inputs.
Other source formats, mip/cubemap generation, complete bundle assembly, ordinary
app tool delivery and complete phone-only installation remain open.

## Produce ETC1 single-mip textures directly from original PC bundles

Current experimental source-only path. The complete host/phone-qualified profile is
`recipe/owner-rgb-textures.json`, SHA-256
`2c4c1c416f676d09a93f987d1ea9f1ecda46aa279baee5799a196beec59fc4ed`.
It covers all 281 ETC1/single-mip records, including both authored composition
ramp aliases, through 274 canonical sources in 79 original PC bundles. The
profile contains selectors, field bounds, hashes and original JPEG policy;
there are no colors, normal vectors, palettes or encoded blocks.

Build the shared public codec using `build_texture_etc.py` above. Its explicit
`alpha8`, `rgb` and `normal` pipe modes share the same provider, compiler and
license owner; the producer selects the mode. The former experimental
`build_texture_alpha.py` / `--alpha-codec` names remain historical at J1082's
source commit. Current Alpha8 and RGB profiles use `--etc-codec`.

```sh
python3 -I -S -B tools/phone-build/accepted-output/texture_produce.py \
  --profile recipe/owner-rgb-textures.json \
  --profile-sha256 2c4c1c416f676d09a93f987d1ea9f1ecda46aa279baee5799a196beec59fc4ed \
  --pc "$ORIGINAL_PC_ROOT" --output "$NEW_TEXTURE_OUTPUT" \
  --etc-codec "$ETC_CODEC" --etc-codec-sha256 "$ETC_CODEC_SHA256" \
  --jpeg-codec "$JPEG_CODEC" --jpeg-codec-sha256 "$JPEG_CODEC_SHA256"
```

The same public JPEG tool remains required for source images whose original
paths select JPEG export. Normal unpacking uses original AG coordinates and an
integer square root; original pixel samples feed every output. The shared
producer verifies every original input and produced/persisted body/resource
extent before success, retaining failed outputs and refusing existing output
or codec drift. [J1088](../../../docs/PORTING_JOURNAL.md#j1088--produce-every-single-mip-etc1-texture-from-pc-bundles-on-android)
qualifies all 281 records, the shared codec build and the complete 5,006-record
RGB/Alpha8/uncompressed regression case on Android. Twelve authored contracts
pass with both real codecs. Complete bundles, mip/cubemap production and
ordinary app delivery remain open.

### Produce the generic Android package entries

Current experimental support: `sdk_inputs.py --android-package` extracts the
additional pinned SDK Java/templates/resources from the same owner-downloaded
component. No installer or Editor runs. `sdk_package.py --request PRIVATE.json`
accepts explicit absolute `sdk`, `android_jar`, `aapt`, `java`, `javac`, `jars` and
new `output` paths. `jars` maps the exact filenames in `TOOL_JARS` to separately
acquired public provider files. AGP/Android tools come from Google's Maven
repository; Guava, Kotlin, JavaWriter and ASM come from Maven Central. Source and
provider binaries are never distributed here. Public hashes are pinned in the
owner; raw requests/results stay ignored. On Android the existing app-host
`android_sdk` request supplies private inputs and the installed read-only JVM
plus QEMU with its explicit GNU loader/library directories.

The producer creates `resources/apk/` with the generic Android entries and
retains intermediate source, process logs and `result.json`. The authored Java
caller invokes unchanged public SDK tools; it contains no SDK implementation or
game Java. Its 15-entry cohort includes AGP's `app-metadata.properties`, generated
by the pinned provider's writer, and Unity's build fingerprint generated from
the fixed authored J850 settings (exact SDK version, IL2CPP, Development,
engine stripping disabled and optimized frame pacing enabled). The latter uses
the exact SDK field order and trailing separator, without a newline or BOM.
Neither file reads an accepted APK or content tree. The APK tree is disjoint
from content's `assets/bin/Data`/payload and
the three explicit game-code outputs. Accepted APK bytes are never suppliers.
J1109 records host equivalence and successful ordinary-app production. Eleven
phone entries are raw-exact; `classes2.dex` and `classes4.dex` differ only in
embedded class checksums and derived DEX headers because the Java 11 and 21
compilers order class constant pools differently. All remaining DEX bytes match;
no output rewriting is used. Composed installation remains open. Failed new
outputs are retained, and active private inputs are unchanged. Remove only disposable generated outputs after evidence
is recorded; run the mandatory repository pruner after build/run work.

## Resume interrupted texture production

The existing texture producer's current experimental `--resume` accepts the
same command, profile, PC input, codec/toolchain pins and output directory as
the interrupted run. Normal invocation still requires a new output directory.
The initial `result.json` persists those pins before encoding. Every completed
object/resource extent is flushed and fsynced before its index row commits.
Resume verifies the ordered index and all persisted extents against the
profile, removes only uncommitted tails, and skips completed texture outputs.
Unknown files, mismatched pins and corrupt committed data refuse recovery.
The `objects.bin`, `resources.bin` and `index.jsonl` formats stay unchanged.

Five authored host tests include real SIGKILL recovery and byte-exact fresh-run
comparison. Android crash recovery remains open after
[J1123](../../../docs/PORTING_JOURNAL.md#j1123--guarded-rgba-phone-batch-loses-transport-admission-stays-open).
Recover the interrupted device's evidence and boot reason before cleanup or
another run. SDK colour bands now execute one at a time; thermal monitoring
and device ownership remain the caller's responsibility.

## Produce single-mip RGBA textures with the owner-supplied SDK

Current experimental source-only support; full phone-cohort qualification is
pending. `recipe/owner-rgba-textures.json`, SHA-256
`76e596c4ec3049e471f292d42b2b623092e05596a1a756be66ff08e73bbe6f96`,
selects 1,277 canonical original textures from 535 PC bundles for the remaining
1,333 non-Alpha8 ETC2 RGBA/single-mip records. It contains selectors, hashes and
importer/storage relationships, with no pixel or encoded-block literals.

`build_texture_sdk.py` owns the current SDK pipe/BC7 helper build. Its native BC7
adapter uses the attributed unchanged public bcdec header under its MIT
alternative, retaining its license. The SDK encoder is separately supplied by
the owner, never included in this repository or a game-bearing packet. Select
`Editor/etccompress.so` from the exact official Linux SDK archive documented
above, SHA-256 `4dc31e0bc2591141648b238fa158fe700dd37c13f62fe3f165618ba85c1a2293`.
Preserve SDK provider terms and the separate public QEMU/GNU license notices;
the build performs no download or license acceptance.

Android requires an explicit public QEMU x86-64 runtime root containing
`bin/qemu-x86_64`, its native dependencies under `lib`, and genuine GNU loader/
libraries under `linux`. The separate GNU development sysroot contains its
headers, startup objects and nonshared libc support. Current required provider
versions and reasons are listed in [LOCAL_STATE](../../../docs/LOCAL_STATE.md).
The explicit native tool root is above `usr`, matching the other native helper
builds. Use the configured device lease/owned workspace during lab staging:

```sh
python3 -I -S -B tools/phone-build/accepted-output/build_texture_sdk.py \
  --compiler "$NATIVE_TOOL_ROOT/usr/bin/clang-21" \
  --linker "$NATIVE_TOOL_ROOT/usr/bin/ld.lld" \
  --android-tool-root "$NATIVE_TOOL_ROOT" \
  --library "$SDK_TEXTURE_LIBRARY" --qemu-root "$QEMU_ROOT" \
  --sysroot "$GNU_DEVELOPMENT_SYSROOT" --output "$NEW_CODEC_OUTPUT"
```

The native Clang builds the BC7 adapter for Android ARM64 and the SDK C ABI
adapter for Linux x86-64. QEMU executes only that standalone build tool; game
execution stays native IL2CPP ARM64. The SDK descriptor is passed by value, with
backend 1, ETC2 RGB format 1, quality 1 and color metric 0. The existing
public ETC helper encodes EAC alpha natively; the producer interleaves each
eight-byte alpha block with its eight-byte SDK colour block. No SDK source or
binary is patched, and no Editor/project workflow runs. The builder preserves
all provider/source pins, commands, bounded compiler logs, notices and complete/
failed receipts. New output is mandatory. It generates `sdk-tools.json` with an
explicit command, environment, pixel tool and every codec/runtime dependency pin.

For a host-native SDK oracle, omit QEMU/sysroot/linker/Android-root options and
select the owner's exact Mac SDK `etccompress.dylib`; its admitted SHA-256 is
`d44cabed1440522efcdf486863176fdea4a0ca26984f43637a611c31dbb518ef`.
This is a separate host tool case, not Android admission.

```sh
python3 -I -S -B tools/phone-build/accepted-output/texture_produce.py \
  --profile recipe/owner-rgba-textures.json \
  --profile-sha256 76e596c4ec3049e471f292d42b2b623092e05596a1a756be66ff08e73bbe6f96 \
  --pc "$ORIGINAL_PC_ROOT" --output "$NEW_TEXTURE_OUTPUT" \
  --sdk-toolchain "$NEW_CODEC_OUTPUT/sdk-tools.json" \
  --sdk-toolchain-sha256 "$SDK_TOOLCHAIN_SHA256" \
  --etc-codec "$PUBLIC_ETC_CODEC" --etc-codec-sha256 "$PUBLIC_ETC_CODEC_SHA256"
```

The existing producer owns source decoding, transparency dilation, field
projection, capacity reservation and every produced/persisted body/pixel check.
BC3 and BC7 use the bounded native decoder; RGBA retains the existing copy path.
The authored BC3 decoder preserves the qualified byte expansion and integer
color/alpha interpolation, including logical edge cropping.
The same native pixel helper performs the existing integer transparency
dilation, keeping coordinate buffers outside the Python parent and freeing them
before pipe output. Its authored seed/tie controls match the standard-library
implementation; whole-cohort hashes remain the admission authority.
SDK encoding runs one block band at a time, each at most
262,144 pixels and aligned to four rows. Raster-order concatenation preserves
the exact block stream; decoding/dilation still cover the complete source image.
Each codec child retains its 120-second deadline, with bounded pending input and
output. It checks the toolchain file and every dependency before output creation and
again before success. Existing output, input/tool drift and differing codec
extents refuse; failed attempts remain private. Compiler/codec children are
bounded and reaped. No game data is shipped with the public source or profiles.
Complete bundles, remaining textures/mips/cubemaps and ordinary app delivery
remain open.

## Produce animation and generic object records

`record_produce.py` is a current experimental source-only producer. Run with
Python 3 and the sibling public producer/reader modules:

```sh
python3 -I -S -B tools/phone-build/accepted-output/record_produce.py \
  --profile recipe/owner-animation-clips.json --profile-sha256 RECIPE_SHA256 \
  --pc ORIGINAL_PC_ROOT --output NEW_PRIVATE_OUTPUT
```

Use `recipe/owner-animator-controllers.json` for the qualified controller
cohort, `recipe/owner-material-records.json` for materials,
`recipe/owner-gameobjects.json` / `recipe/owner-transforms.json` for hierarchy
records, and `recipe/owner-generic-records.json` for the qualified native and
scripted records. A recipe contains source selectors/hashes, target relationships/hashes
and named source transformations, never target object bytes. The producer
reads original embedded schemas and records, relocates checked PPtrs, and
verifies each full result against its accepted hash. Animation policies clear
original reference-pose arrays while preserving the importer size, canonicalize
schema-declared float values or packed float words, and fold only complete,
exclusive constant streamed curves. The expanded profile additionally selects
native Hermite coefficient packing, original binding permutations, constant
folding and measured dense endpoint/signed-zero rules. Whole streamed keys sort
by their remapped indices; value ranges and root indices follow the same source
permutation. Root quaternions derive from indexed original delta endpoints,
with the measured ARM float32 normalization. No native library or instruction
emulator is required. Original event strings, values, paths,
curve data and other non-transformed bytes remain original. Generic controllers
and the qualified hierarchy/native/scripted records change only PPtrs,
preserving original type and script identities. The material path reuses the existing original keyword
demotion operation; it introduces no material or shader value.

Setup requires a matching recipe hash, pinned unchanged original PC bundles,
new output outside the input and expected output capacity plus 2 GiB reserve.
Before/after source hashes and independently re-read persisted extents gate
success. Failure retains the partial output and `result.json`; exit tears down
the process. Successful outputs are `objects.bin`, `index.jsonl` and
`result.json`, matching the Avatar producer's bundle/member/path-ID interface.
Bundle/player-file callers independently obtain original native type metadata
and generate destination layout. There is no replay, SDK, UnityPy or Editor
input to production.

J1133 qualifies 3,246 AnimationClips, 27,114 GameObjects, 176,689 Transforms
and 29,473 generic records on the host. J1119 additionally qualifies 232
AnimatorControllers and 4,979 Materials. This partial cohort closes no final-file readiness entry by
itself; complete source-only content and ordinary-app/device qualification
remain open. Outputs and all discovery/comparison evidence stay ignored.
The native pixel tool additionally exposes experimental `bc4`, `bc5`,
`mips-linear` and `mips-srgb` pipe modes. BC4/BC5 accept the complete compressed
logical top mip and emit cropped RGBA with unused colour channels zero and alpha
255. Their byte-channel interpolation retains the pinned upstream one-unit
bias. The mip modes accept exactly `width * height * 4` RGBA bytes and emit all
logical levels, including the original, through 1 by 1 in raster order. The
first linear reduction precedes normalization; later levels retain float32
values without intermediate byte quantization. Gamma conversion applies only
to RGB. The builder disables floating-point contraction and links native libm.
All 87 authored exact-editor byte levels match on the host. These modes do not
establish Android equivalence; the ETC1 host cohort is qualified below.

## Produce ETC1 mip chains

Current experimental support: J1110 qualifies all 1,589 records on the host.
Full Android cohort qualification remains open.
`recipe/owner-rgb-mip-textures.json`, SHA-256
`380d6d4c2a7f64db1bac10cefa0c6d31ec7cbfb1e817cd4fd2d7067643cb4283`,
selects 1,548 canonical originals for all 1,589 ETC1 mip-chain records. Use the
same texture producer with this profile, the current `--etc-codec` and
`--jpeg-codec` paths/pins, and a current `--sdk-toolchain` path/pin. This operation
uses only that toolchain's native pixel helper, not the standalone SDK encoder.
Source decoding/unpacking precedes transparency extension or the selected JPEG
round trip. Float mip levels remain continuous; only emitted logical levels are
quantized. Tail levels tile to complete ETC blocks. Destination usage selects the
existing normal or perceptual ETC metric. The nine-field projection additionally
sets mip count and colour space, preserving every unselected original byte.

The current public ETC builder also compiles the unchanged vendored Unity Crunch
headers under their retained Zlib notice. `texture-etc WIDTH HEIGHT uncrunch-bc1`
and `uncrunch-bc3` accept a bounded original CRN stream on stdin, verify dimensions,
format and a single face, and emit only its top BC level. These are intermediate
owner-derived bytes; no Crunch image is distributed. The builder pins all three
headers and their complete license before/after compilation and emits
`CRUNCH-LICENSE.txt` alongside the existing provider notices.


## Produce RGBA mip chains

Current experimental source operation: `sdk-rgba-mips`. J1128 qualifies all
1,523 records on the host; Android qualification remains open. Use the existing texture
producer and explicit SDK/public ETC tools with
`recipe/owner-rgba-mip-textures.json`, SHA-256
`723c4e641349941a172aef28d6a4b23eee2954c5390cd7257a75a54cd0bf66fd`.
The profile selects 1,399 canonical source transformations for 1,523 records,
including four standalone player textures. It retains the same object/resource
pack and index interface consumed by the bundle/player owners.

The owner decodes only the original top mip, extends transparent RGB, generates
continuous float32 mip levels and repeats logical tail levels into complete
blocks. SDK colour compression and the existing public EAC alpha encoder derive
every level. For sRGB import all four channels first normalize with float32
`1 / 255`; the gamma transfer applies only to RGB. Linear import preserves the
existing byte-unit first reduction. The exact-editor fixture includes varying
alpha to distinguish these arithmetic contracts. No Editor/project executes in
production. Android cohort qualification remains open.

## Produce source-derived cubemaps

J1128 qualifies the complete 110-record profile on the host.
Use the existing texture producer with `recipe/owner-cubemap-textures.json`,
SHA-256
`319691fd4c11591b87b4aae654b00a1cd7789105b43be2cd52a090bb98cb2526`,
and explicit current `--etc-codec`, `--jpeg-codec` and `--sdk-toolchain` paths
and SHA-256 pins. Its 110 records select originals from 68 PC bundles:
50 `cube-mips`, 56 `cube-hdr` and four `cube-rgba-mips`. The existing
`objects.bin`, `resources.bin`, `index.jsonl` and `result.json` contract is
unchanged. Thirteen native generated-sky/baked-probe records are excluded;
their source pixel derivation remains open.

Each operation reads the six original face chains with their original per-face
stride and regenerates levels from each face's top mip, preserving face order
and orientation. Ordinary colour uses the existing continuous float mip and
perceptual ETC path. HDR import preserves the measured exporter half conversion,
float mip filtering and DoubleLDR quantization before uniform ETC encoding;
destination colour space selects the transfer before quantization. The four
RGBA cubes use the SDK colour/public EAC alpha path. CompleteImageSize remains
per face; the resource extent contains all six faces. Original metadata outside
the selected nine fields is retained. No target pixel supplier or Editor/project
executes in production. Complete Android qualification remains open.

`owner-villagenight-objects.json` uses the same object owner for the complete
two-member streamed-scene bundle. Supply its independently produced mesh pack
with `--record-pack DIRECTORY RESULT_JSON_SHA256`. Shared assets precede the
scene member; each retains its own type/script/external tables and persisted
index member identity. The scene's script table includes only actually used
script pointers, including references into the shared member. Generated native
PreloadData collects the qualified external reference relationships; the native
streamed-scene container preserves original path case. Original scene export
component omissions and inactive MapZone policy remain checked transformations.
The scene layout output uses a `members` list in physical member order and the
receipt records each serialized member hash. No Editor or accepted target input
is needed for production; complete bundle comparison and phone acceptance are
separate gates.

The same streamed-scene command accepts `owner-helminthroost-objects.json`
and the existing mesh pack. J1135 qualifies its 6,853 records and complete
9,593,495-byte bundle raw-exact on the host without further producer changes.
Together with J1134 and J1132, nine full source-derived host bundles are now
qualified. Phone and complete catalog/content acceptance remain open.

J1138 adds `owner-habitatfall-objects.json` and `owner-habitat-objects.json`
through the unchanged scene owner. Both consume the mesh pack; Habitat also
requires the qualified source cubemap pack. Original billboard records retain
all non-pointer bytes and native type metadata. The complete bundles compare
raw-exact on the host, bringing this owner cohort to eleven full bundles.
Phone qualification and complete content/catalog remain open.

`owner-wispgraveyard-objects.json` uses the same streamed-scene command and
qualified mesh pack. It needs no SDK schema, texture or cubemap input. Its
checked original component omissions reproduce J850's reduced diagnostic
scene, including Tree and scripted components; full original stage behavior
remains unqualified. See J1142 for the complete host result. Phone acceptance
and complete content/catalog remain open.

The same command supports `owner-itskymeadow-objects.json`,
`owner-itancientloft-objects.json` and `owner-solusweb-objects.json` with the
pinned editor-resource `--sdk` root. Sky Meadow and Ancient Loft consume the
existing mesh, uncompressed-texture and RGBA-mip packs;
Solusweb consumes only the mesh record pack. Their checked native scene/schema
policies preserve original record data outside the measured changes. The
Solusweb extra preload verifies membership in original PC metadata before using
its mapped GameObject identity. Setup and output lifecycle are unchanged;
J1145 owns the host result, with phone/runtime acceptance open.
