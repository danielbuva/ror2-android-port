# Architecture

What runs today, how it is built, and who owns what. The ADRs explain *why*
([ADR-001](ADR-001-port-architecture.md)); this page is the current map. Update it when a
file, owner or pipeline step is added, moved or retired. Results and evidence live in the
[journal](PORTING_JOURNAL.md); the files the build expects under `work/` are listed in
[LOCAL_STATE.md](LOCAL_STATE.md).

[Alpha policy](ALPHA_POLICY.md) owns packaging/acquisition decisions;
[screen inventory](SCREEN_COVERAGE.md) maps the current Android surfaces and their
remaining interaction gates.

Documentation entry points: [project home](../README.md) and
[player guide](PLAYER_GUIDE.md) explain availability for players.
[DEVELOPING.md](DEVELOPING.md) owns contributor setup, the repository map and
command reference, including the generated prototype-action table.
[PLAYTESTING.md](PLAYTESTING.md) owns the prepared-lab desktop fallback checklist:
matching build receipts, selected-device installation, assisted checks, manual
playtest limits and reviewed feedback. It introduces no installer or runtime step.
[Branding notes](assets/branding/README.md) record the two repository-only
promotional graphics and their sources; they are not part of the runtime pipeline.

Launcher presentation: [`launcher/`](../launcher/README.md) owns the approved
original background and dependency-free frontend. `controller.js` owns the
versioned host state/action adapter, subscription teardown and pending-action
guard; `app.js` owns views and navigation. No backend is connected by default.
The separate `demo/` is simulated and is never loaded by the frontend. This
package's `feedback.js` owns page-memory notes, explicit consumption of schema 1
sanitized baseline previews, an exact plain-text preview, review consent and
clipboard copy with manual fallback. Setup is the Diagnostics feedback route;
navigation removes listeners and retains notes in page memory, reload clears
them, and background host updates preserve the form. It projects typed,
bounded public facts into a new object and ignores unknown keys and draft URLs.
No raw receipt, log, device, storage, network or attachment access is added.
The notes are user-authored and require manual privacy review. The launcher
package is a public-alpha integration boundary, not an Android shell, new
build pipeline or runtime owner. Setup, lifecycle and acceptance gates are in
its README; the existing owner-built delivery route remains unchanged.

Public alpha delivery: [ADR-002](ADR-002-public-alpha-distribution.md) accepts
owner-built APKs and locally reconstructed content; [public-alpha.md](public-alpha.md)
holds open release work. ADR-001's architecture C and the runtime pipeline below
remain current. [phone-owner-build.md](phone-owner-build.md) assesses build stages
for phone-only delivery while retaining the desktop workflow as fallback; no
replacement game runtime or working build pipeline is selected. Public-input bootstrap,
performance equivalence and device acceptance remain open.

[Accepted-build reconstruction](accepted-build-reconstruction.md) compares a
fixed-target owner converter, private delta/frame replay and general Unity-project
reconstruction. `tools/phone-build/accepted-output/package.py` owns explicit private-packet
reproduction and framed emission. It verifies supplied target/profile/PC/SDK
inputs without generating independent Android target information. `assemble.py`
owns hash-bound unsigned APK assembly and required uncompressed/aligned resource
storage; canonical alignment and owner signing follow separately.
`unity_write.py` owns current experimental bounded UnityFS 7/8 and
serialized-v22 construction from explicit type metadata, object bodies and
resource streams. Object table order and physical body order remain independent.
It owns one temporary compressed stream, a bounded pinned codec child, block
deadlines and child teardown; callers own input provenance and retained outputs.
`build_bundle_lz4.py` builds the HC12/fast block helper `bundle_lz4.c` from a
separately acquired pinned public LZ4 archive, retaining its license, build logs
and terminal receipt. These structural writers generate no game content or
target relationships and have no game-build/runtime consumer. J1116 qualifies
all 133 accepted bundles as a structural control using accepted records; PC-only
object/layout derivation and phone qualification remain separate.
`object_produce.py` owns the current source-only pickup, player-death-effect,
teleport-material, objective-UI, teleporter-indicator, generic-pickup and
enemy-reward, Village Night, Helminth Roost, Habitat, Habitatfall and
Wispgraveyard, Sky Meadow, Solusweb, Ancient Loft, AI Test and Testscene slices.
Audited profiles `recipe/owner-pickup-objects.json`,
`recipe/owner-death-effect-objects.json`,
`recipe/owner-teleport-material-objects.json`, `recipe/owner-objective-ui-objects.json`,
`recipe/owner-teleporter-indicator-objects.json`,
`recipe/owner-generic-pickup-objects.json`,
`recipe/owner-enemy-reward-objects.json`,
`recipe/owner-villagenight-objects.json` and
`recipe/owner-helminthroost-objects.json`, `recipe/owner-habitat-objects.json` and
`recipe/owner-habitatfall-objects.json` and
`recipe/owner-wispgraveyard-objects.json`,
`recipe/owner-itskymeadow-objects.json` and
`recipe/owner-solusweb-objects.json` and
`recipe/owner-itancientloft-objects.json`, `recipe/owner-ai-test-objects.json` and
`recipe/owner-testscene-objects.json` select original bodies/type
metadata and checked pointer relationships. It generates container/preload
metadata with explicit local/external order, packs, layout and canonical
bundles through those writers. New disjoint output, pinned PC files/recipe/
codec and capacity checks set up the process; persisted output and unchanged
inputs precede a complete/failed receipt. The qualified dummy material moves
its original valid keywords into the invalid list without introducing strings
or material values. Explicit record-pack directory/receipt pins supply already
produced texture bodies and resources; the owner verifies them before/after,
assembles resource extents, and generates each asset's rooted container preloads.
It calls the existing `player_data.py` Sprite crop/importer helpers only when
needed, after module setup; no helper implementation is duplicated. The original
GenericPickup GameObject omits one checked native-audio component relationship,
preserving every remaining byte. Native Android Sprite shader references use
Unity's built-in resource identity. Physical preload partitions retain their
own order while container paths sort independently. Enemy reward explicitly
admits the owner's pinned SDK resource file and original script/behaviour
selectors. The existing `script_identity.properties_hash` owner derives the
MonoScript properties hash and MonoBehaviour type hash from original custom
fields and the SDK's editor base schema. All other body/type bytes remain
source-owned; SDK hashes are checked before and after production.
The streamed-scene slices process shared assets then the scene member. Each
member retains its own object/type/external tables and index identities. Scene
script tables derive from actual MonoBehaviour script pointers, independently
of physical script-first body placement. The existing checked reference
relationships generate sorted external PreloadData; native scene containers
preserve the original relocated scene path and streamed-scene semantics. The
existing scene export policy disables the selected MapZone owner and omits
checked original components; reflected bake removal uses ordinary PPtr remaps.
All scene meshes come through the existing pinned producer pack. Habitat also
consumes the qualified source Cubemap pack; original billboard bodies/types
remain unchanged apart from checked references. Setup, input admission, persisted verification and failure
retention share the prefab owner. Failure retains outputs and the codec context
reaps its child; exit ends the producer.
Wispgraveyard reproduces the accepted reduced diagnostic scene through the
same checked export omissions, including original Tree and scripted components.
It does not establish full original stage behavior.
Sky Meadow and Ancient Loft clear the checked original occlusion static-renderer
array while retaining the original GUID, occlusion pointer and portals. These full scene
slices append an existing source-produced component to the original SceneInfo
GameObject. Solusweb disables the two selected original bank behaviours and
omits only CharacterMaster's measured final debug field from body and schema;
the existing hash owner consumes that amended source schema. Its additional
preload relationship checks the original preload record, GameObject body and
external-member membership before emitting the mapped identity. These policies
retain the existing setup, input checks, persisted verification and teardown.
AI Test and Testscene reuse those same schema, Sprite, pointer and preload
policies without another producer branch. Their Sprite importer identities
follow the current accepted-input export and original scene relationships.

`player_data.py` owns the separate current 175-file player cohort: SDK/converter
resources, PC-derived script JSON, the three-object font file, original
line-breaking TextAssets, authored runtime/bootstrap JSON, 64 standalone Sprites and one
original TimerStringFormatter object, nine original TMP objects, 14 materials
and 72 standalone textures, plus the six-object SDK built-in UI file. Its audited
`recipe/owner-player-data.json`,
explicit original PC/SDK/converter inputs and converter receipt set up a new
target tree; checked pointer relocation and `unity_write.py` build serialized
files. Original Sprite geometry/UVs remain unchanged; source render-data crops
recover standalone rect/pivot/offset/border coordinates with float32 arithmetic.
The authored full-rectangle Sprite generates corners/triangles from original
bounds and recovered pivot/border/pixel scale through the existing HUD policy.
Importer identities derive from destination filenames. The scripted object
retains its source type/body with a relocated external script table. The
runtime JSON input is a pinned sibling of the profile. The separate pinned
`owner-bootstrap.json` retains the existing public attempt identity and four
original preload GUID relationships absent from the original catalog.
`texture_files` consumes explicit producer directories and pinned successful receipts in the existing object/
resource pack interface. `inline_texture` moves only existing produced pixels
inline, clears their stream descriptor and retains every other body byte; the
already-selected original font bundle supplies native Texture2D type metadata.
Pack/profile/input/extent hashes and unchanged providers precede completion.
Material clone import names follow the authored HUD builder. Its assigned
original Shader property table selects retained texture environments; all other
original material values remain unchanged. `builtin_ui` reads an explicitly
supplied, pinned SDK `Resources/unity_builtin_extra`, strips its six selected
objects' editor-only fields and relocates original local texture/importer IDs.
Original SDK mip pixels, Sprite geometry/physics/bones and the original PC
font/sharedassets Sprite native type identities supply the runtime output.
No Editor process is required.
The same owner reads the complete pinned current English JSON directory for
the authored `StageStrings` policy. It preserves quoted text while admitting
original trailing commas, applies the qualified filename/token collation and
later-file replacement order, then emits compact JSON inside a native TextAsset.
Original language providers are rechecked after the serialized output is written.
The additional font material preserves its original Sharpness value. Current
outputs use current originals only; historical originals serve independent
transformation qualification, with input drift kept separate from exact output
comparison. Serialized object/TextAsset destinations use the fixed Android
toolchain engine version while retaining source-derived native schemas.
The same player owner derives its two native shader-selection TextAssets from
original Material keywords and Shader declaration metadata. Its pinned
`recipe/owner-player-shader-manifests.json` supplies source selectors; embedded
type trees locate fields on every run. `scripts/lab/shader_metadata.py` owns the
shared pure declaration/variant policy used by both this reader and the existing
shader generators. It has no file, compiler or retained-state access. The player
owner admits and rechecks every original provider through final serialized
output. These JSON files supply selection metadata; compiled Shader production
remains a separate gate.
Selected TMP fonts derive their managed properties hashes through the shared
`script_identity.py` owner, using the actual original MonoScript identity,
original custom schema and an explicitly supplied pinned SDK
`unity editor resources` native base. Original script relationships are checked
before derivation; unselected scripted objects retain their original hashes.
The SDK provider and original script are rechecked through final output.
The landed RGBA producer/profile from PR75 supplies 54 selections; PR95 supplies
four additional standalone mip records;
the combined phone replay remains open. Persisted/input
hashes and complete/failed receipts define state and teardown. Neither owner consumes
replay files or a Unity project. Their
[setup and limits](../tools/phone-build/accepted-output/README.md#produce-the-first-complete-source-only-bundle)
remain separate from complete content assembly, installation and runtime acceptance.
`mesh_produce.py` owns a separate current experimental PC-input-only mesh
producer, using read-only bounded UnityFS access in `unity_bundle.py`, embedded
serialized-field extents and authored operations in `unity_mesh.py`, and the
audited `recipe/owner-meshes.json` selectors/settings. Explicit original input,
recipe hash and new output produce private object/resource packs plus an index
and terminal receipt. Setup verifies source pins/capacity, processing checks
every object and re-reads persisted extents, and failure/exit retain outputs
and end the process. [Its lifecycle and qualified scope](../tools/phone-build/accepted-output/README.md#produce-meshes-directly-from-original-pc-bundles)
remain separate from bundle assembly, the private replay receiver and current
game builds; two mesh cases are excluded and no runtime owner is added.
`scripts/lab/script_identity.py` additionally owns current pure managed script
properties-hash derivation. Callers supply original PC and exact SDK embedded
type metadata plus original script identity; the helper composes the SDK native
editor base with original custom fields and hashes their semantic metadata using
its existing authored MD4. It performs no file/process access or automatic
metadata replacement, and retains no state. Callers admit inputs, select the
needed hash policy, persist outputs and own setup/teardown. J1124 qualifies one
source-only EffectManagerHelper case; complete content and phone qualification
remain separate. Original script-file-ID derivation remains unchanged.
`record_produce.py` owns source-only AnimationClip and generic object-record
production through the same object-pack interface. Audited
`recipe/owner-animation-clips.json`, `recipe/owner-animator-controllers.json`,
`recipe/owner-material-records.json`, `recipe/owner-gameobjects.json`,
`recipe/owner-transforms.json` and `recipe/owner-generic-records.json`
select original records, checked pointer relationships and source-only animation
policies. Original embedded schemas identify typed float fields, reference-pose
and streamed/dense/constant arrays. Native Hermite packing reconstructs source
tangents with float32 operation order. Source binding permutations reorder
whole stream keys, delta ranges and root indices; dense curves retain the
measured import endpoint/signed-zero rules. Root rotations derive from original
indexed delta endpoints using ARM reciprocal-square-root arithmetic.
Setup admits a pinned recipe, unchanged original
PC bundles and separate new output with capacity reserve; source and persisted
record hashes gate its complete/failed receipt. It retains outputs and ends the
process on failure/exit. Generic and hierarchy records preserve every
non-pointer byte and native script/type identity;
material keyword demotion reuses the existing object owner's policy. No runtime
owner or Editor is added. [Setup and qualified scope](../tools/phone-build/accepted-output/README.md#produce-animation-and-generic-object-records)
remain separate from complete bundle/player-file assembly and phone acceptance.
`avatar_produce.py` owns current experimental PC-only Avatar production using
the same bounded reader and input-path admission. Its audited
`recipe/owner-avatars.json` selects original body/table extents and complete
source-entry ordering. Explicit PC root/recipe hash and separate new output
set up the process; before/after input checks, exact object hashes and persisted
readbacks precede its terminal complete/failed receipt. Exit tears down the
process and retains private packs. [Setup/lifecycle](../tools/phone-build/accepted-output/README.md#produce-avatars-directly-from-original-pc-bundles)
requires no private target/discovery file. All 228 accepted records qualify in
J1075; bundle assembly and game-build integration remain separate owners/gates.
`texture_produce.py` owns the current experimental Texture2D source producer. Audited `recipe/owner-uncompressed-textures.json` selects
original body/pixel ranges and generic import/stream placement; standard BC1
decoding, raw copying, fixed source-coordinate color extension and public
JPEG roundtripping introduce no target pixels. `build_texture_jpeg.py` owns
the current native JPEG-tool build from pinned public source providers and
an explicit compiler; `texture_jpeg.c` owns bounded stdin/stdout processing.
New private output, source/tool admission, bounded compiler/codec children,
retained notices and complete/failed receipts define setup/state/teardown.
Explicit PC root, recipe
hash, new output and capacity reserve set up the process. It verifies source
files before/after and every produced/persisted extent, writes private object/
resource packs and a complete/failed receipt, then exits and retains outputs.
Its [setup/lifecycle](../tools/phone-build/accepted-output/README.md#produce-uncompressed-textures-directly-from-original-pc-bundles)
adds a pinned public stb/IJG JPEG tool but no Unity SDK, Editor or private
discovery input. J1079 qualifies all 399 uncompressed records and the public
JPEG-tool build on Android. Other texture formats and complete bundle assembly
remain separate gates; no current game build or runtime consumes these packs.
The same owner's current experimental `--resume` reuses its original profile,
input/tool pins and existing output. Data fsync precedes every committed index
row; recovery checks the ordered persisted prefix before truncating uncommitted
tails and continuing. Initial/final receipts are replaced atomically. Host
SIGKILL recovery qualifies this contract; Android crash recovery remains open
after J1123. SDK colour bands run sequentially.
The same owner derives full-chain RGBA through `sdk-rgba-mips` and audited
`recipe/owner-rgba-mip-textures.json`; source top-level decode, transparency
extension, continuous float mip filtering and per-level SDK/public encoding
share the existing setup, verification, checkpoint and teardown. No target-byte
provider or separate output interface is added. Android qualification remains
open.
The same owner additionally derives face-major Cubemap records with audited
`recipe/owner-cubemap-textures.json`. It preserves the original full-chain face
stride, regenerates each face from its top level without a vertical flip, and
writes CompleteImageSize per face. Existing BC decoding, float mip filtering,
public ETC and SDK RGBA encoders share the same pack/checkpoint contract. The
native pixel helper owns BC6 byte conversion and HDR export-half/DoubleLDR mip
handling. Source identity and unresolved native reflections remain explicit
gates; no target pixel fallback is available.
The same owner supports the source Alpha8 cohort through
`recipe/owner-alpha-textures.json`: canonical original bodies/pixels are reused
with explicit target names, storage extents and unchanged-field admission.
`build_texture_etc.py` builds a separately acquired pinned public ETCPACK
provider and retains its license, logs and complete/failed receipt;
`texture_etc.cpp` owns bounded Alpha8 stdin/ETC2 stdout processing. The source
export's zero RGB and original alpha produce every pixel, without an SDK encoder.
[Setup/lifecycle](../tools/phone-build/accepted-output/README.md#produce-alpha8-textures-directly-from-original-pc-bundles)
requires the pinned native helper. J1082 qualifies the whole 4,326-record cohort
and helper build on Android. Other compressed textures, mip/cubemap production
and full bundle assembly remain open.
The same codec/producer now owns the ETC1 single-mip source path through
`recipe/owner-rgb-textures.json`. Its source-format decoding, original JPEG
policy and AG normal unpacking feed explicit color/normal encoder modes.
The Alpha8 helper is generalized as `build_texture_etc.py` / `texture_etc.cpp`,
with `--etc-codec` admission for both profiles. Setup/state/teardown and source/
persisted-output verification stay with the existing owners. J1088 qualifies
all 281 records on Android, the shared codec build and complete 5,006-record
RGB/Alpha8/uncompressed regression case. Mips and complete bundles remain open.
`build_texture_sdk.py` owns the current experimental SDK pipe/pixel helper build.
It accepts explicit native/compiler/provider roots, retains source/license/build
receipts and generates a private `sdk-tools.json` containing command, environment,
pixel tool and dependency pins. The existing texture owner admits it through
`--sdk-toolchain`, hashes every dependency before/after use and derives
`recipe/owner-rgba-textures.json` through `sdk-rgba`. `texture_pixels.c` uses the
attributed public bcdec header and owns the same integer transparency dilation
with bounded native coordinate buffers; `sdk_texture_codec.c` calls the separately supplied
SDK codec. Host-native SDK execution is an oracle; Android uses the public QEMU
runner and genuine GNU runtime. No game runtime owner or Editor/project build
is introduced. Full-cohort phone qualification remains pending.
The same native pixel owner has experimental BC4/BC5 byte-channel decoding and
linear/sRGB mip-chain pipe modes. It preserves byte units through the first
linear reduction, then continuous float32 levels. These modes have authored
exact-editor host controls; game-cohort and Android admission remain separate.
`etc1-mips` extends that texture owner with full-chain filtering, logical-tail
tiling and destination normal-metric selection. `owner-rgb-mip-textures.json`
provides the original/destination field and import relationships. The existing
public ETC tool also owns bounded Unity Crunch top-level decompression using
unchanged pinned Zlib headers, built by `build_texture_etc.py`. The SDK toolchain
supplies its native pixel helper; ETC1 mip production executes no SDK encoder.
J1110 qualifies all 1,589 records on the host; Android cohort qualification
remains open.
`build_sdk_runner.py` owns current experimental public Box64 acquisition-by-build
for standalone owner-supplied SDK tools. Explicit unchanged upstream source,
the pinned SDK NDK and host archive tools produce a private Android runner.
It owns bounded compiler process groups, retained licenses/logs and terminal
build receipts. `sdk_texture_codec.c` owns a bounded pipe/ABI adapter for a
separately supplied SDK codec, with C-locale GNU/Bionic compatibility entries.
[Setup and limits](../tools/phone-build/accepted-output/README.md#build-the-standalone-sdk-tool-runner)
keep this shell-only build-tool path separate from game execution and ordinary
app delivery. J1081 qualifies runner execution, while Linux RGBA texture
equivalence, shader/Burst tool execution and complete content production remain
open. No Editor/project workflow or game backend changes.
`sdk_inputs.py` owns current experimental owner-direct component extraction:
an explicitly supplied, pinned provider archive yields the three SDK-copy files
and, with `--android-package`, the generic Android Java/resource inputs in a new
private root. Bounded parsing, exact readback and terminal receipts remain with
that owner. `sdk_package.py` and the authored `SdkAndroidCode.java` API caller own
the experimental generic Android package slice: pinned SDK/public tools produce
four DEX entries, manifest/resources/icons and the two SDK native libraries.
The same owner generates both generic `META-INF` build metadata files: the
pinned AGP writer supplies app metadata, and the fixed authored target settings
supply the SDK-ordered Unity fingerprint. These files use no accepted APK input.
Setup creates new private outputs; teardown bounds children and retains logs;
source/tool hashes are checked before and after production. The existing
`owner-code/run_android.py::android_sdk_job` supplies the installed read-only JVM
and QEMU host. Java children retain the explicit app-host JVM/home/library
environment and use the current output's temporary directory. [Setup/lifecycle](../tools/phone-build/accepted-output/README.md#produce-the-generic-android-package-entries)
keeps this owner separate from content, game-code production and final signing.
The tool host starts children through Android `taskset 1` before interpreter/JVM
initialization; descendants inherit CPU 0 while the external thermal guard
continues. This applies to build tools only and trades throughput for startup
CPU restraint. J1109 qualifies host byte equivalence and ordinary-app production. Eleven phone
entries are raw-exact; two DEX files retain only compiler-class checksum and
header differences. Final composed installation remains open.
`phone_decode.py` in that directory owns current
experimental **support**, not game runtime: explicit new owned workspace, pinned
private package and verified PC/SDK inputs produce complete target files and an
unsigned APK. The process owns setup, bounded codec children, hashes/progress,
result state and child teardown at failure/exit; it retains failed outputs.
[Its README](../tools/phone-build/accepted-output/README.md) specifies the stream,
limits, tool build and lifecycle. No `./dev` game build or launcher consumes this
path. The packet's target information stays private; independent owner-input
production, ordinary app execution, owner signing/alignment, install/update and
public distribution of any game-bearing packet remain separate gates.

`tools/phone-build/owner-apk/` owns a separate experimental owner-APK bootstrap
candidate after reconstruction. `build_owner_apk.py` and `binary_manifest.py`
compile only authored Java, preserve the selected content bytes and move the
binary manifest's launcher filter to `PayloadBootstrapActivity`, with the
original Unity entry private to enforce preparation. An optional owner-selected
`version_code` changes only the original typed version attribute in addition
to routing; it must increase and updates retain the same private signer.
An optional complete `code` selection supplies independently produced IL2CPP,
metadata and Burst files; all three are required, their actual hashes are retained,
and comparison-target code files are not read. The same dictionary can also
include the complete 15-entry Android SDK cohort owned by
`accepted-output/sdk_package.py::SDK_ENTRIES`; partial cohorts and unknown names
refuse. The produced manifest feeds the existing routing/version patch, and
the other selected SDK outputs stream unchanged. Host fixtures cover this
18-entry composition without comparison-target files and retain input-drift
checks; complete phone installation/controls/performance remain open.
The same owner's current `--check-request` action inventories every selected
final target/code file, retaining actual hashes, raw comparison differences and
all missing/mismatched/invalid entries. Normal assembly writes `readiness.json`
and refuses blocked inputs before compiling its launcher. Check-only teardown
retains one new private report; it starts no compiler or device action. Complete
record packs do not satisfy final bundle/player-data paths, and this byte check
does not establish source provenance or device qualification.
Other content retains the existing
manifest layout/hashes. Source provenance and code/runtime qualification remain
with their producers (J1102).
`PayloadStore`
streams/hash-checks embedded runtime payload into the calling app's own external
files location, stages replacements, retains backups and gates launch of the
unchanged Unity activity. The activity owns worker/receipt/UI setup, pause/retry,
launch verification and teardown; the approved frontend connects through fixed
adapter-v1 actions. No existing Unity/game build consumes it and it is not a
selected final distribution architecture. [Setup and device gates](../tools/phone-build/owner-apk/README.md)
include ZIP size, duplicate storage cost, unknown-file acceptance and retained
user data. All APKs and embedded game data stay ignored/private.
The same APK owner has an explicit signing mode: acquired Java/zipalign/apksigner,
a separate durable private key directory and fresh output own key setup/reuse,
alignment/signing, content verification and failed-output retention. J1095
qualifies separate phone signing processes; no install is performed.
[Key/output lifecycle](../tools/phone-build/owner-apk/README.md#durable-owner-signing)
keeps signing identity outside disposable build output.

`tools/phone-build/package-assemblies/` owns a separate current experimental
host producer for the four retained Unity package assemblies and their required
Burst managed post-processing. It validates explicit owner SDK/package inputs,
generates compilation requests, compiles the processor, bounds/reaps children,
retains failures and writes input/output receipts in a new private root.
[Setup and lifecycle](../tools/phone-build/package-assemblies/README.md) describe
the fixed profile and exclusions. No captured project/player inputs or current
game build consume this owner; phone execution and full-player qualification
remain separate gates. Package versions and the native IL2CPP runtime stay fixed.

`scripts/lab/wwise_bank_index.py` owns the shared source bank/XML parser and a
current experimental owner-input entry independent of a lab project. Default
owner indexing executes no decoder; explicit metadata qualification shares the
legacy temporary-copy helper and never exports audio or writes original banks.
The owner entry binds accepted inventory before/after, owns a new private output
and terminal receipt, and retains failures without updating lab/current state.
[Setup and lifecycle](phone-owner-build.md#source-audio-inputs-without-a-project)
keep the original lab gate and runtime stage/request guards intact. No game build
automatically selects this source-only input path; Android execution is open.

[J1058's whole-player host case](PORTING_JOURNAL.md#j1058--strip-and-convert-the-complete-player-with-fixed-target-root-configuration)
reuses the named metadata/SDK registry/root-composition owners and exact SDK
UnityLinker/IL2CPP tools with independent DLL providers. Current target root and
preservation identities are explicit supplied configuration, not independently
derived scene semantics. LOCAL_STATE records setup, retained inputs and teardown.
[J1059](PORTING_JOURNAL.md#j1059--build-the-complete-native-arm64-game-library-without-unity-editor)
then completes native construction using the original SDK compiler policy.
These experiments have no current game-build consumer; public orchestration,
content production and Android execution remain separate gates.

`tools/phone-build/owner-code/native.py` owns the current experimental standalone
native stage of that same Editor-free chain. Audited
`recipe/owner-native-arm64.json` replaces the captured DAG with typed argument,
SDK-source/lump, translation-unit and link configuration. Explicit accepted
owner state, SDK, converter receipt, source providers and matching metadata
are checked before new private output setup and again at termination. The
owner keeps commands, tool logs, object receipts and terminal state; failures
retain their output. [Setup and teardown](../tools/phone-build/owner-code/README.md)
cover source-frame expansion, input immutability, child cleanup and capacity.
There is no shared project, Editor, device or current game-build consumer.
J1063 qualifies the complete source-input host command through native execution.
Independent content/Burst/shader production, licensed native input production
and full-player Android construction remain open.

The same native owner optionally runs explicit Linux NDK executables through a
public QEMU user-mode provider. It hashes the supplied GNU loader/runtime and
NDK tools, obtains one actual compiler/linker child command from the unchanged
Clang driver, and invokes it without a global Linux execution handler. Original
SDK ARM64 target data remain inputs. Android Clang 21/LLD remains the explicit
fallback; whole-player Linux app hosting and runtime parity are separate gates.

`owner-code/produce.py::burst` owns the unchanged acquired Burst compiler
invocation over freshly produced managed assemblies. Fixed-target metadata
selects its roots, actual SDK compilation API defines, options and tool hashes.
`GnuToolAdapter.c` supplies only the GNU build-tool low-address mappings and
explicit emulated child execution required by Mono/LLVM under QEMU. It is foreign
tool data, never linked into the ARM64 game. `native.py::compiled_jobs` validates
a completed object's source/command/input/hash receipts for an explicit relink;
the normal linker/stripper then use the selected profile order. Neither owner
reads an accepted ELF as a supplier.

`tools/phone-build/owner-code/shader.py` owns the experimental exact-SDK
Vulkan IPC client. An explicit compiler command/SDK directory and new private
output own setup, typed session state, reflection/diagnostics and child/socket
teardown. It invokes no Editor/project and selects no runtime shader.
[Setup and limits](../tools/phone-build/owner-code/README.md#standalone-sdk-shader-tool)
separate the qualified authored fixture (J1094) from original-cohort recovery,
serialized content construction and ordinary app admission.

`tools/phone-build/accepted-output/shader_produce.py` owns the current bounded
source-only Android Shader48 producer. Audited `recipe/owner-player-shaders.json`
selects ten authored sources, original Cloud/UI Alpha shader/material selectors,
PC schema/keyword registry,
source build settings and pinned SDK inputs. The existing compiler session owns
ShaderLab preprocessing, snippet/include identities and linked Vulkan emission;
fresh reflection supplies native parameter/program records and common tables.
The producer derives the pass key from source/capabilities/SDK inputs, constructs
the parsed form from source and schema defaults, requests HC9 through the existing
codec worker and emits complete files through `unity_write`. The SDK executable
is read as metadata only. Explicit read-only providers and a new disjoint output
set up production; before/after pins, complete-file comparison and terminal
success/failure receipts retain state. Compiler/codec contexts own teardown.
The original Cloud/UI paths use existing `shader_materials.cloud_source`,
`shader_materials.ui_source` and
`NativePrograms` to regenerate source from pinned PC shaders/materials through an
explicit public d3dasm tool/hash, without retained HLSL. Variant reflection
intersection owns common/native records; SDK capability names/flag moves drive
compilation separately from import preprocessing. J1144/J1146/J1147/J1151 qualify 125
complete host files; other shader families, mixed/built-in
files and phone/runtime gates remain open. No target body or Editor/project is
read. Setup is in the [producer README](../tools/phone-build/accepted-output/README.md#source-derived-player-shaders).

`tools/phone-build/owner-code/produce.py` owns the current experimental combined
whole-player backend: explicit hash-bound managed providers, audited target
roots, SDK-derived native identities, exact SDK stripping/conversion, verified
source-frame retention and the native stage above. It adds no runtime owner.
`recipe/owner-player-code.json` holds minimum fixed target identities/retention,
assembly order and tool hashes; no captured native table or response is read.
[Setup and lifecycle](../tools/phone-build/owner-code/README.md#combined-whole-player-backend)
name input setup, exclusive outputs, interstage drift checks, failed-state
retention and teardown. J1061 verifies the explicit-managed-input mode through
native planning; J1063 qualifies the complete source-input mode, including fresh
managed production and native linking.
No shared project, Editor, device or current build consumer is involved.

The same code owners accept an explicit fixed target (`profile` plus public
authored-source root). `recipe/owner-j850-code.json` binds its public source
commit and 114 inputs; `managed.py::target_run` composes existing public DLL
transforms, package production, original support/maps and target gameplay sources.
It excludes the later audio assemblies and developer-only MCP provider.
The backend keeps fixed SDK/root policy while `native.py::generated_profile`
compiles every translation unit from the actual target conversion. Setup owns
a new output and checks source/tool/owner state; failed outputs remain and process
teardown is unchanged. [Target setup and scope](../tools/phone-build/owner-code/README.md#fixed-accepted-source-target)
retain inherited scene/module and raw target/device comparison gates.

`tools/phone-build/owner-code/managed.py` owns current experimental original-input
managed production under the same `produce.py` entry. Audited
`recipe/owner-managed-code.json` names 320 original/SDK providers and the minimum
fresh support-source selection; all other game assemblies are generated by
existing owners. Explicit tool/package/authorized SDK inputs replace prepared
game DLLs and decompiled-source suppliers. [Setup/lifecycle](../tools/phone-build/owner-code/README.md#original-input-command)
cover fixed owner-work admission, exclusive outputs, immutable provider checks,
retention and teardown. Native products, bank/prefab data, decompiled sources,
managed artifacts and receipts stay private; no current game build selects them.
The original audio upper-level admissions and runtime owners are unchanged.

`tools/phone-build/owner-code/legacy_init.py` owns current experimental
historical Init-receipt compatibility. It requires the full accepted owner
inventory and exact configured source bank before materializing/executing the
byte-bound authored archive in `tools/phone-build/legacy/`. It retains the exact
historical source and receipt scope; there is no synthetic old hash on new code.
[Setup/lifecycle](../tools/phone-build/legacy/README.md) document the fixed private
source-root depth, exclusive outputs, refusal/failure retention and teardown.
The current public Init producer remains preferred for new callers; no shared
runtime owner, selector or build admission changes.

`scripts/lab/owner_audio_prefab.py` owns current experimental bounded host
reconstruction of one source audio prefab from the owner's original bundles.
`recipe/owner-audio-prefab.json` holds audited minimum identities and one clearly
labeled export-GUID configuration relationship. The owner validates source and
script/reference graphs, serializes the qualified profile, revalidates inputs
and retains terminal state in a new private output root. [Setup/lifecycle](phone-owner-build.md#bounded-source-audio-prefab)
requires no Editor/exported asset and adds no current game-build consumer or
runtime owner. Unknown shapes and hashes refuse; phone qualification remains open.

Phone build **support**: `scripts/lab/phone_bundle.py` writes the isolated authored
TextAsset bundle with only Python's standard library; its versioned native
schemas consume no class database or generated asset. `phone_content.py` owns
project staging and source/bundle hash checks for that fixture.
`tools/phone-build/ContentFixtureBuilder.cs` owns its exact-editor check and
separate player build; `ContentFixture.cs` loads either its embedded bundle or
a hash-bound candidate at a fixed path in its own data directory. It checks two
load/unload cycles and writes a private report. The three `phone-content-*` prototype
actions stage/check/build only this fixture under the primary checkout mutex.
See [probe setup and boundaries](../tools/phone-build/README.md). No game-runtime
owner or whole-catalog build calls this support path.

`scripts/lab/phone_texture_oracle.py` owns a separate current experimental
exact-editor texture oracle. The `phone-texture-fixture` action stages a fresh
SDK-only project with authored `TextureMipFixture.cs`; `phone-texture-check`
imports nine authored PNGs across linear, sRGB and normal settings under the
primary editor mutex. A linear RGBAFloat mirror, its native byte conversion and
native scalar transfer observations separate filtering from byte quantization.
The owner validates all
raw mip files, source/config
identity and persisted extents in a new attempt. Its output is a desktop
comparison oracle, never a phone/game production input. No player is built.
Teardown removes its generated project after evidence is retained; the earlier
authored content/player fixture and its frozen native provenance are separate.

`tools/phone-build/tool-host-fixture/Program.cs` owns a separate current
experimental .NET build-tool graph fixture (J1023). Its project selects the tool
framework only; explicit arguments select one of two authored graph sizes. The
process owns graph setup, complete stored-field checks, scalar reporting and
release at exit. It reads no game/SDK input and is never staged into the Unity
project. Its README names invocation and independent expected witnesses; raw
Android execution and linker adapters remain ignored local qualification state.
It adds no game runtime owner or current build consumer.

`scripts/lab/phone_apk.py` is separate packaging **support** for that authored
fixture only. Its standard-library parser increases a literal Android manifest
version code after checking the fixed package identity, substitutes the authored
bundle, preserves other entry bytes and removes obsolete signatures. It writes
new unsigned outputs; alignment and owner signing follow separately. The current
`phone-apk-fixture` action takes an ignored hash-bound request via `--target`;
the same file has a standalone Android CLI. It cannot repackage the game ID.

`phone_package_check.py` owns the separate fixture's device acceptance: require
explicit selection, local APK hashes, matching shell-workspace ownership and
fresh storage/capacity checks; exercise embedded input, refused hash drift,
phone-produced input, native reload/unload, a version-code upgrade and data
retention. Its `finally` removes only a package whose actual APK hash matches
the owned attempts and verifies display sleep. It records game APK hashes
read-only before/after. `phone-package-check` takes an ignored request and
writes private evidence under `work/experiments/phone-packaging/`.
The player publishes actual Android/Unity data paths in its private bootstrap
report; the runner binds canonical paths and their separate backing stores
before reading reports or copying candidates. Editor checks/builds each write
an isolated oracle report and require its pinned actual Unity version and
native content checks, independently of process exit status.

`ContentFixtureLinkerCapture.cs` is a fixture-only editor observer for the next
stripping experiment. It snapshots the active public UnityLinker callback's
complete input directory into the explicitly owned build attempt, preserving
source/hash identity and rejecting links or concurrent drift. It returns only
an inert linker XML. The builder records its final BuildReport identity;
`phone_content.validate_linker_capture` requires matching build/commit/version,
required assembly/scene/editor-data inputs and every copied hash before accepting
a fixture build. This does not establish Android stripping or input consumption
by itself; the fresh graph and emitted outputs still need independent binding.
It is never staged into the game project.

`phone_linker.py` owns experimental stripping **support** for that captured
authored fixture. The current `phone-linker-fixture` action verifies the explicit
fixture/callback/final-build identities, maps only known linker flags/input roots,
and stages unchanged captured files plus supplied SDK descriptors/tool DLLs.
Its standalone Android driver verifies input hashes, uses the separate .NET
build-tool host, retains output/log/failure receipts and disables unnecessary
tool analytics. Desktop-generated scene/editor root production remains an input;
matching output hashes and fresh execution evidence are separate acceptance
checks. No whole-catalog build or game runtime calls it.

`phone_linker_roots.py` owns the optional SDK-native metadata handoff for that
authored fixture only. An explicit `native_registry` binary/hash request causes
staging to omit the captured native table entirely and retain only validated
project scene/module-policy fields. At the actual Android stripping invocation,
the staged authored registry readers inspect the pinned SDK as data. The handoff
checks complete native identities/parents, orders rows by qualified name, and
creates a new `native-roots/EditorToUnityLinkerData.json` under the owned output.
UnityLinker receives that generated path; hashes/source/scope receipts bind it
through the converter boundary. Invalid SDK data, captured table leakage, source
or output drift and incomplete metadata refuse. Scene usage, TypesInScenes.xml,
module policy and managed compilation remain captured desktop inputs; complete
independent editor roots remain unqualified. There is no editor mutation or
whole-catalog/game consumer. Failure directories and earlier modes remain intact.

`phone_module_policy.py` owns an additional optional fixture-only policy profile.
With `module_policy: {"profile": "builtin-modules-no-overrides-v1"}` alongside
`native_registry`, staging omits captured module-policy arrays as well. It
requires the authored fixture's known source/file set, builtin-only manifest
and consistent package lock. Pinned editor/Android module data and SDK builtin
package metadata stay private. At stripping invocation the authored reader
resolves transitive builtin dependencies and derives disabled/unavailable
module exclusions from those SDK inputs. It writes `native-roots/module-policy.json`;
its input hashes, generated policy and reader hash are rechecked downstream.
Unknown schemas/versions, foreign packages, custom project code, nonstrippable
exclusions and unsupported profile requests refuse. Custom callbacks/overrides
are unsupported; this is not general Unity project policy. Scene usage,
TypesInScenes.xml and managed compilation remain captured desktop inputs.
The profile adds no editor, game-runtime or whole-catalog consumer.

`phone_roots.py` and `tools/phone-build/metadata/` own experimental read-only
host support for investigating independent root production. The current
`phone-root-contract` action binds the authored fixture/capture, inventories
editor/player SDK managed metadata with supplied pinned Cecil, and separates
explicit native-class attributes from short-name guesses. It executes only the
authored reader, never the inspected assemblies. Results/source hashes and
failures remain under `work/experiments/phone-roots/`; it generates no roots,
installs no package and performs no editor mutation. The original coverage
action uses host .NET 10. The separate scoped net8.0 reader/resolver has J866's
Android shell qualification; app hosting and complete roots remain unqualified.
The metadata reader's schema 2 also records full assembly identities, declared
references, base-type scopes and exported/forwarded types without resolving or
executing them. `phone_managed_types.py` owns pure investigation support for an
explicitly selected metadata group: it resolves exact scopes and forwarding
chains, including nested exports, and proves managed inheritance only when
every required definition is present. Duplicate assembly/type identities,
unsupported module exports, cycles and missing dependencies refuse. It never
fills gaps from another group or substitutes managed bases for native bases.
Setup is an explicit schema-2 inventory/group; teardown releases the in-memory
index. Its standalone metadata/group/new-output invocation verifies every
forwarding entry, binds the inventory hash, refuses output overwrite or input
drift, and emits a private observation report. No game build or linker stage
consumes this helper.

`phone_native_flags.py` owns separate current experimental native flag metadata.
Its standalone owner-SDK/new-report invocation checks the pinned binary and
reader hashes, reads the three static boolean bytes, and proves individual
stack-literal bytes for the root/nonobject registrations. Wider zero stores and
later byte writes remain distinct; conditional or unknown origins, alias stores,
frame movement, loops and escaping calls refuse. It packs abstract/sealed/editor
flags for unique persistent IDs. Setup is explicit owner SDK data and a new
private report; teardown releases parsed data. It executes no SDK code, stages
no editor project, produces no cache/scene roots and has no game/linker consumer.

`phone_wrapper_search.py` owns separate current experimental SDK search-order
support. `phone-wrapper-search --target REQUEST.json` accepts only the pinned
owner binary and stages that data with the three authored Python readers.
Its normal-path matcher proves the original native-name argument, Darwin
stack-passed formatter argument/result storage, file-backed namespace/assembly
pointer loads, common nonnull exits and preserved return value. Unknown data
flow, alias stores, loops, incomplete guards or unsupported string selection
refuse. Assembly templates and ordered namespaces come from the SDK; repeated
entries remain distinct. Setup is an explicit owner-binary request and a fresh
private attempt; teardown releases parsed data and retains reports/failures.
It executes no SDK function and supplies no cache population, scene roots,
project dependency closure, editor mutation or game/linker consumer. J869
qualifies this bounded metadata contract on the alpha Android shell; it does
not qualify normal app hosting or a complete wrapper cache.

`phone_wrapper_oracle.py` and `tools/phone-build/WrapperMetadataOracle.cs` own
separate current experimental **desktop verification**. The
`phone-wrapper-oracle` action stages a fresh SDK-only project or checks that
explicit project with the exact editor under the primary checkout mutex.
Committed source, project, editor and loaded assembly hashes bind the report.
Staging checks containment before creating anything and opens directory chains
and new files through descriptors that refuse symlinks. Every file write
rechecks scope; configured work-root and staging-parent links refuse before
outside writes. Foreign assets, drift, existing outputs and lock contention
also refuse. The C#
collector validates unique native identities and the complete parent graph
before querying concrete descendants of native Object. Root, abstract and
outside-hierarchy rows remain explicitly unqueried; null and empty query
results remain distinct. Setup is a new generated project/request; teardown is
the isolated batch process exiting, retaining logs and failed attempts. Neither
MCP editor is reused or stopped. Its private SDK observations are comparison
oracles, never phone-build/linker inputs, project scene roots or game behavior.

`phone_wrapper_population.py` owns the current experimental cache reconstruction
API. It decodes extra-registration operands from owner SDK data, uses the scoped
managed metadata universe and keeps direct names, inherited forward entries and
reverse registrations distinct. Its standalone invocation selects an owner SDK
binary, scoped inventory, managed SDK directory, corlib and new private output.
It binds the complete pinned 84-file managed set, inventory and reader hashes,
refusing replacement, missing files, mixed inputs and drift. J878 verifies forward
mappings on Android; J883 matches root-inclusive metadata to native SDK cache
observations. Complete consumer semantics and independent project roots remain open.
No game or linker consumer reads it.
`phone_wrapper_population_oracle.py` and `WrapperPopulationOracle.cs` own a
separate SDK-only desktop check. The explicit root/work/editor invocation stages
a fresh project using the guarded directory writer and runs under the existing
primary mutex. Committed sources, project inputs, SDK bytes and loaded assembly
hashes are checked. It adds abstract Object-descendant queries to the earlier
validated collector while retaining root/nonobject exclusions. Reflection-only
API discovery invokes no candidate method. Teardown is the isolated batch exit;
logs and failures remain local. Neither MCP editor nor a game project is reused.

The population oracle's explicit `--reverse` mode stages
`WrapperReverseOracle.cs` and a fresh layout generated by
`phone_wrapper_reverse.py`. The latter reads the pinned SDK as data to locate
the manager slot and cache vectors; it supplies no class/mapping table. Runtime
readable VM ranges include zero-fill tails without relaxing file-backed reads.
The collector reads only its own fresh SDK process through bounded VM copies,
checks stable vector bounds/bytes, and names opaque class pointers through public
metadata accessors in the already loaded SDK Mono library. It initializes no
runtime and calls no private SDK function. Committed transitive readers and the
existing build-lock helper are bound in the stage identity. Teardown remains
the isolated process exit; reports are private verification, never phone-build,
game or linker inputs. This mode is experimental and requires independent
cache comparison before any broader qualification. Forward slots use only the
SDK's observed runtime indices/IDs, with complete registry coverage; zero slots
remain absent entries. Root membership in native population is inclusive, while
the separate wrapper-query collector retains its root exclusion.

`phone_scene_usage_oracle.py` and `SceneUsageOracle.cs` own a current experimental
desktop verification step for the authored content fixture. An explicit
root/work/exact-editor invocation stages a fresh SDK-only project through the
existing guarded writer and claims the primary checkout's build mutex. The
collector creates a default scene with the authored `ContentFixture`, compiles
its Android player scripts into a fresh type database, and observes scene and
global-manager dependencies through the SDK content-build APIs. Loaded scene
objects remain separate from asset identifiers, referenced objects and usage-tag
objects; a live object without an asset identifier remains explicitly observed.
Included type arrays retain shared-wrapper multiplicity rather than inventing
unique native identities; global usage fields remain separate observations.
Unresolved
objects have no claimed support result, and null type responses stay distinct
from empty arrays. The receipt binds committed transitive source, the SDK,
staged inputs, scene and observed assemblies. Teardown disposes the type
database and usage sets and exits only this new batch process; failures and logs
remain local. No player is built, no MCP editor or game project is reused, and
no report supplies phone-build/linker inputs. Complete root production remains
unqualified. API knowledge comes from the pinned Unity reference source
[`ContentBuildInterface`](https://github.com/Unity-Technologies/UnityCsReference/blob/b052b1fe38b45d5aefa609a115c626ed2e74f3a6/Modules/BuildPipeline/Editor/Managed/ContentBuildInterface.bindings.cs)
and [`PlayerBuildInterface`](https://github.com/Unity-Technologies/UnityCsReference/blob/b052b1fe38b45d5aefa609a115c626ed2e74f3a6/Modules/BuildPipeline/Editor/Managed/PlayerBuildInterface.bindings.cs);
no reference implementation is copied.

`phone_manager_context.py` owns current experimental SDK registration metadata
inspection. Its standalone owner-binary/new-private-report invocation reads the
pinned SDK as data, without creating an editor project or executing SDK code.
It proves literal class-name arguments, lookup return stores, context-relative
slot indices and native manager ancestry. Declaration order stays separate from
slot order. The context bound must compare the incoming argument; unknown or
skipped definitions, clobbered operands, incomplete/aliased slots, ambiguous
native identities and unknown predicate shapes refuse. A separate bounded
predicate reader resolves the SDK's asset-dependency exclusion indices. Those
exclusions describe asset dependency collection, not native class retention.
Setup is the supplied SDK and a new private output; teardown releases parsed
bytes and preserves the report. Reader/SDK hashes bind the result. No live
context, target support, object retention or project/linker root is qualified;
no game or build consumer reads the output. Runtime context storage may be
zero-fill memory and is never treated as file-backed metadata.

`phone_manager_retention.py` owns separate current experimental SDK metadata
support. It derives the write-method dispatch offset from both bounded global
manager build consumers. A normal-control-flow proof requires the same nullable
context-lookup receiver for the vptr loads, call target and ABI argument.
Unknown operand effects, clobbers, skipped definitions, mismatched call sequences
and ambiguous consumers refuse. RTTI symbols, encoded type names and zero
offset-to-top validate each declared manager's complete primary vtable before
using its address point; an unverified two-word header is never assumed. The
selected target must match one method in that native class's ancestry.
Setup takes the pinned owner SDK and a fresh private report; teardown releases
parsed bytes and keeps source/SDK hashes and failed attempts. It neither invokes
the virtual methods nor evaluates live manager state, target support, exception
flow, serialized retention or final native usage. No build consumes its output;
all live/state/target/native-usage/root qualifications stay false.

`phone_platform_features.py` owns current experimental SDK Android feature
declaration support. It binds the comparison stub through Mach-O imported-symbol
and library metadata, identifies literal selector headers, and reads only the
closed Android append body. Literal addresses must be file-backed C strings;
output/selector/capacity receivers must preserve the entry parameters. Overflow
diagnostics, growth calls and their continuations have bounded known forms;
foreign entries, clobbers, aliases and unknown executed shapes refuse. A separate
generated-function extent bound leaves the earlier small-function readers
unchanged. No SDK instruction executes and no captured table supplies an input.
Setup is the exact supplied SDK and a new private report; teardown releases
parsed bytes and retains source/input hashes. Other platforms, target discovery,
module inclusion, state retention, native usage and roots remain unqualified.

`phone_platform_feature_oracle.py` and `PlatformFeatureOracle.cs` own separate
desktop verification. The runner creates a fresh SDK-only project and an authored
query request with no expected answers, then serializes its batch process under
the primary checkout's persistent Unity mutex. The collector observes the SDK's
Android discovery label and invokes its exact feature API; setup/teardown touches
only that new project and process. Hashes bind the source, SDK, queries and loaded
assemblies, and failures retain their attempt. These API answers are comparison
evidence only: neither a phone generator nor a game build reads the oracle report.
No player, scene or canonical game-build pointer is created or changed.

`phone_target_keys.py` with `phone_target_constructor.py` and
`phone_target_geometry.py` owns current experimental SDK target-key input
metadata. It derives an initializer's stack interval and consumer stride,
checks constructor write extents, and requires each typed-call or inline-copy
input to cover one distinct slot. Bounded operand proofs retain the key/string
arguments, byte/null coverage and mode-specific length continuations; unknown
effects, skipped definitions, zero-register values, aliases and incomplete
coverage refuse. The runtime tree's zero-fill address is an identity, never
file-backed content. Setup takes the exact supplied SDK and a fresh private
report; teardown releases parsed bytes and retains SDK/source hashes.
No SDK instruction executes and no captured table is an input. Constructor
results, populated maps, discovered target availability, module inclusion,
native usage and roots remain unqualified. No game build consumes this report.

`phone_target_records.py` owns a separate current experimental SDK operand-link
report. It reads string-copy source/destination offsets, pair value placement,
the insertion block's local node/key displacement and the platform-define
consumer's inline/heap field choice. Its only positive qualification is static
field alignment; it does not select a node, execute a constructor, evaluate hash
container semantics, populate a map or resolve a target. Renderer checks,
conditional module handling and record reset are recorded as unevaluated
barriers around insertion. Setup is committed reader/helpers and the pinned
owner SDK; teardown creates one new private JSON and retains failed attempts.
No SDK instruction executes, and no game build or root generator consumes it.

`phone_target_key_oracle.py` / `TargetKeyOracle.cs` own separate current desktop
observations of the SDK's public numeric-name API and internal reverse-name API.
The runner stages a fresh SDK-only project, with separate numeric/string query
lists and no expected pairs. Every batch uses the primary persistent Unity
mutex. Setup/teardown changes only that project and child process. Bind source,
SDK, query and loaded-assembly hashes. Observation completion is separate from
the saved exact-comparison result: spelling aliases, exceptions and mismatches
remain evidence, never normalized into a pass. SDK answers are not phone/game
inputs, and no scene, player or canonical build pointer is created or changed.

`phone_managed_compile.py` owns a current experimental authored compiler fixture.
Its explicit stage invocation copies hash-pinned owner Roslyn components, their
unchanged runtime configuration/license, the SDK Unity AOT core library and the
public `ConverterFixture.cs` into a fresh guarded work directory. It consumes
no captured response file, compiled player or game source. The standalone run
selects an explicit SDK or Android build-tool runtime profile, validates the
complete input set and invokes the same compiler with fixed C# 9, deterministic,
portable-debug, AnyCPU and development-optimization options. One fixed relative
output directory and a virtual source path keep fixture comparisons meaningful.
Setup is committed source and supplied SDK/tool inputs; teardown is the compiler
child exiting, with logs, runtime identity and failed attempts retained. This
does not start Unity, build a player, select a game backend or qualify managed
game compilation, editor-generated type databases or ordinary app hosting.
Its authored IL remains an input candidate for the existing IL2CPP pipeline.
J899 records Android repeatability and the failed raw desktop/Android equality
comparison. Compiler-host version and derived debug identities remain recorded;
no build consumer normalizes away that evidence.

`phone_unity_compile.py` owns a separate current experimental compilation of
the public `ContentFixture.cs` Unity API fixture. It stages pinned SDK compiler,
target managed modules, standard-library references, builtin package metadata
and the authored four-package manifest. It reuses `phone_module_policy.py` to
derive references on the selected host, excluding package-disabled modules;
captured Bee response files and editor reports are comparison evidence only.
The standalone runner verifies its authored sibling helpers before importing
them, works under Python isolation, and records a generated reference report
alongside implementation/reference DLLs and a portable PDB. Setup requires
committed authored sources, an explicit owner SDK and a qualified build-tool
host. One compiler child exits at teardown; failed stages/results stay private.
This fixed source contains no conditional directives. General defines,
generators, custom packages/callbacks, editor type databases, stripping and
player/game compilation remain separate gates. No game build consumes outputs.

`phone_compiled_linker.py` owns a separate current experimental handoff from the
qualified authored Android compiler profile to the existing fixture stripper.
It verifies the completed compiler input/output receipts and the pinned authored
SDK-root template, then creates a fresh stage with only its two compiler inputs
replaced. Historical stages, manifests and the original exact-replay converter
gate remain intact. Compiler code/data/reference fingerprints exclude only Git
commit metadata, so unchanged inputs remain eligible after unrelated commits;
the actual commits and every raw receipt/hash are preserved. Its standalone
runner checks the staged closure before and after the bounded linker child and
writes a separate `handoff-result.json` without modifying the child result.
Setup requires committed handoff code and explicit qualified input selections;
teardown is the linker child exiting, with failed stages and outputs retained.
Captured desktop scene/editor roots remain required. A passing stripper does
not qualify conversion, a player, game semantics or ordinary app hosting.

`phone_compiled_converter.py` owns the separate current experimental consumer
for that authored Android compiler/stripper profile. Setup requires committed
source, the pinned converter template and explicit successful stripping
stage/output selections. It copies and revalidates the complete supplier stage
and its raw receipts, then supplies the actual stripped closure to an unchanged
converter driver in a fresh stage. The nested converter plan and all retained
SDK inputs remain pinned; neither original replay consumer is relaxed. This
deliberately retains upstream proof inputs, with additional staging/storage
cost. Its standalone runner bounds the converter child, verifies immutable
inputs before and afterward, and records raw generated source/data hashes in a
separate `handoff-result.json`. Teardown is the child exiting; preserve failures
and receipts. Captured desktop scene/editor roots remain prerequisites. A
passing conversion alone does not qualify native compilation, metadata/player
loading, performance, game compilation or final tool distribution.
J920 qualifies this fixed authored conversion profile; the native/player
consumer remains a separate gate.

`phone_compiled_native.py` owns the separate current experimental native
consumer for that fixed profile. Setup requires committed sources, the exact
authored fixture request, its matching converter stage/output, the qualified
SDK native inventory and owner SDK paths. It checks both generated data files
against the exact base APK before capturing a fresh native graph with the
unchanged native stage builder. That graph must match the converter generation;
the SDK/target inventory must match qualification. Actual C++ bytes and ordered
compile/link arguments stay unchanged. Only generated plan scope annotations
are updated. The complete upstream proof, fixture sources/APK and native inputs
remain private and hash-bound. The bounded native child retains the original
exact object-reuse checks; failed stages/results remain evidence. Teardown is
the child exiting. `library_input` validates the resulting AArch64 shared-library
header, full library hash and provenance before returning the exact APK/library
pair for separate packaging/audit/player checks. No native build, player,
ordinary app hosting or game/performance qualification follows from host tests.
J921 separately qualifies the fixed authored native/player path on the assigned
device, with a full native compile, explicit APK/library binding and owned
load/update/refusal checks. It retains all desktop-root and full-game gates.
If the native child reaches its 1,800 s deadline, the wrapper records a failed
handoff with an unknown exit code and bounded stdout/stderr (64 KiB each),
preserving partial child results without admitting a library.

`phone_registry.py` and `phone_registry_literals.py` own separate experimental
static SDK metadata support.
The current `phone-native-registry` action accepts an explicit owner binary,
requires the pinned SDK hash, and stages an unchanged private copy with the
standalone standard-library Python reader. Bounded Mach-O symbols/data and
straight-line ARM64 constant propagation identify partial registration records,
parent pointers and generated module-registration arguments. A direct-call
index is restricted to the declared instruction section. Conservative backwards
argument slicing uses symbol and branch-derived scan bounds, including incoming branch
targets, and respects caller clobbers and runtime loads. Direct module arguments
must agree with the earlier generated-registration subset; no function name is
substituted for a missing argument. The literal helper reads selected descriptor
fields from bounded stack stores: definitions must dominate registration, entry
arguments must be preserved, and partial/conditional overwrites, later backedges,
frame movement, alias stores and unknown calls refuse. Its only intervening call
allowance is the exact assertion signature with file-backed literal strings and
integer arguments, never a passed descriptor. The action stages/hashes both
authored source files alongside the owner SDK; explicit file loading imports only
that authored helper under isolated Python. Unknown layouts, instructions,
arguments and parent identities refuse. It neither executes SDK instructions
nor supplies an execution backend. Source/input hashes, metadata and failures remain under
`work/experiments/phone-registry/`; exclusive output creation preserves attempts.
The same reader reports persistent native class IDs from the pinned descriptor's
explicit signed 32-bit field. Static data and bounded literal/entry-argument
origins are kept separate. Numeric literal selection checks exact width and
little-endian slices; partial/conditional definitions and ambiguous/invalid IDs
refuse. A scalar argument may reuse a wide-move literal held in an AAPCS64
callee-saved register only after a bounded CFG proof: its definition dominates
the use, every intervening instruction has a known register effect, no path
writes that register and no later backedge can revisit the use. This does not
select a branch or read runtime memory. ID metadata does not establish managed
wrapper names, scene usage or
manager/dependency roots. The six-field native projection remains unchanged.
Only the explicit authored-fixture SDK-native stripping mode consumes freshly
generated registry data. No whole-catalog build consumes it or receives complete
project roots from it; no editor or game state changes.

`tools/phone-build/host/` is separate experimental **support**. Its Android
driver owns compilation of authored C/Java/XML, DEX/APK production and disposable
signing from explicitly supplied local tools. `HostProbeActivity` owns one
background check of PackageManager-installed native execution and a writable
copy's refusal, then writes `files/host-report.json`. It uses no Unity/game
code, permissions or network. Setup and device cleanup are described in its
[README](../tools/phone-build/host/README.md); no game build calls it.
`phone_host_check.py` owns its explicit-device, hash-bound installation,
two launches, report/backing collection and ownership-checked teardown through
the current experimental `phone-host-check` action. The default target 30 and
explicit target 33 use separate literal manifests; the driver validates selection
and never rewrites either. Both require identical installed/control bytes,
observed app UID/context agreement and an actual writable-copy permission denial.
Optional unprivileged enforcement reads can remain unknown. Failed controls
retain their file metadata/backing and owned cleanup evidence.

`tools/phone-build/native-host/` owns a separate positive build-tool hosting
fixture. Its `NativeToolHost.c` calls the existing public hostfxr command-line
ABI; `ToolHostActivity` owns fresh data directories, asset/native hash checks,
read-only native links, bounded compiler/managed children and private reports.
`build_fixture.py` owns phone compilation, packaging, disposable signing and
input/failure receipts. Caller-owned installation/teardown requires explicit
device selection, fresh storage and an exact installed-APK ownership receipt.
Setup and unqualified boundaries are in its
[README](../tools/phone-build/native-host/README.md). This support path has no
game, launcher or whole-catalog consumer and adds no `./dev` action. It never
changes the existing refusal probe or reports security qualification.

`tools/phone-build/managed-host/` owns the connected experimental app-host
support. `stage.py` checks the public source/native metadata contract and stages
new owner-supplied SDK inputs; its builder owns the separate phone-built APK.
`NativePythonHost.c` selects the existing interpreter's isolated configuration;
`NativeDotnetMuxer.c` forwards actual framework queries/application invocations.
`NativeJavaHost.c` invokes the separately acquired headless JDK through JNI;
its javac/keytool/java entry names and read-only native dependencies are installed
by PackageManager. Java modules and configuration remain verified tool data.
The activity owns fresh data/native-link state and bounded children;
`run_profile.py` checks supplied input hashes and invokes the unchanged public
producer. Device installation, legitimate accepted-input transfer, independent
readbacks and exact-APK teardown remain caller-owned. See its
[README](../tools/phone-build/managed-host/README.md). No default build/runtime
consumer or `./dev` action is added, and J929 remains a failed security gate.
The integrated source selection refreshes the two authored helper pins while
retaining the same native/interpreter/compiler owners. J1074 qualifies its
generic app-host operation; fixed-target code jobs and the owner APK flow
extend the same owners without adding a content producer.

Its `ToolHostActivity.Runner` instrumentation entry runs the same worker without
opening an Activity. The optional caller-owned backend job invokes
`owner-code/run_android.py`, which verifies original/SDK/provider copies and
calls the existing backend using installed native .NET/compiler/linker/strip
tools. The builder's optional explicit native plan binds those generic ELF
providers and their data-tree links; no game file enters the tool APK. The worker
retains private reports and bounded child lifetime; the caller owns fresh storage,
exact package receipt, kernel thermal monitoring, output readback and cleanup.
The muxer keeps CoreLib in verified framework data. For .NET 10 it preserves
hostfxr selection/properties and loads the selected versioned native CLR through
the public CoreCLR ABI; ILSpy searches the matching native framework first.
The public transform producer retains its isolated .NET 8 enumeration contract.
Gameplay postprocessing sees one generated directory of the exact selected
reference providers, avoiding conflicting unselected sibling DLLs. All links and
managed/native outputs belong to the new private output/fixture lifetime.
This remains debug/ADB-assisted tool support, without security, final installer
or gameplay qualification.

The same app worker accepts explicit APK assembly/signing jobs through the
existing `owner-apk` owner. Its key directory is outside each disposable build
output. The Activity shows a completed private APK and hands a read-only content
URI to Android's installer only after a user button press; the private provider
permits only that verified output. Headless instrumentation never opens the
installer. Tool APK updates use a separate durable tool key. J1103 qualifies ordinary-app
Burst and authored-APK signing through these owners; installer/full-player
acceptance and device security remain separate gates.

`phone_native.py` owns experimental **support** for replaying the authored
content fixture's native graph. `phone-native-fixture` verifies an explicit
project/APK request, copies supplied runtime/NDK and generated source inputs
unchanged, regenerates only include wrappers from their ordered dependency
descriptions, and records structured compile/link arguments plus input hashes.
Its standalone Android driver checks those hashes, builds into a new output
directory and retains each command/log and the first failure. Clang/LLD host
changes are explicit; desktop stripping/code generation and private Unity
inputs remain dependencies. No game build uses this path.
Relinks may reuse only a hash-bound complete object set with equal source/target
inputs, compile plan and actual compiler arguments. Link repair selects the
original NDK static C++/ABI/GCC libraries explicitly and preserves old attempts.

`phone_native_apk.py` is separate packaging **support** for the authored content
fixture only. It requires base APK, ARM64 shared-library and unchanged metadata
hashes, substitutes that one native entry plus the version integer, retains
other entry bytes/notices, and removes obsolete signatures. Its current
`phone-native-apk-fixture` host action and standalone Android CLI produce new
unsigned outputs; alignment, signing and device checks follow separately.
The device checker also hashes the actually mapped IL2CPP library inside the
observed installed code directory, independently of the APK's expected entry.

`phone_converter.py` owns separate experimental **support** for replaying the
authored player's complete recorded IL2CPP code-generation command. The current
`phone-converter-fixture` action shares the native fixture's project/APK/source
guard, requires the exact assembly closure and known options, copies supplied
stripped assemblies/tool DLLs/icalls unchanged, and records their hashes.
The standalone Android driver uses a separate .NET build-tool host, verifies
inputs before execution, relocates only output paths, disables unnecessary
tool analytics and retains fresh output/log/failure directories. An optional
`linker` selector in its request binds the actual Android stripping stage/result,
all emitted hashes and exact DLL/symbol closure against the same fixture. Only
the recorded editor-report module order may differ; complete entries/other fields
are checked in memory and the actual report bytes are copied unchanged.
An explicit
optional `converter` selector in a native-fixture request binds that converter's
stage/result/output hashes, original stripped input closure and byte-identical
data/metadata before choosing its emitted C++ for native compilation. The game
runtime is still IL2CPP; desktop scene/editor-root production and permitted
proprietary tool delivery remain gates. No whole-catalog game build calls this owner.

Status words used below: **current** (part of the shipped whole-catalog game or the
commands that build it), **support** (editor builders, host fixtures and tooling around the
current path) and **historical** (kept for evidence; not reached by current commands).

## Build pipeline

Historical `input-update-check` uses `scripts/lab/historical_receipts.py` to
resolve an explicitly registered, hash-pinned optional-guard receipt against the
preserved original assembly before inventory/probe work. This support owner has
no runtime or build-selection side effects; its registration and local-state
contract are in [LOCAL_STATE.md](LOCAL_STATE.md#named-historical-optional-guard-evidence).

`scripts/prune-generated.py` (current) discards rebuildable build outputs under
`work/` while protecting the APKs pinned by `PORTING_STATE.md`, `docs/BASELINE.md`,
device receipts and the coordination lock; agents run it after each build/run task
(AGENTS.md "Storage hygiene").

`scripts/git-hooks/pre-push` delegates committed-source checks to
`scripts/ci-local.sh` in a fresh clone. Its support helper
`scripts/ci-hdiutil-volume.py` requests a 30 s timeout for each optional image
create/attach CLI, killing and reaping only its own timed-out caller. Ordinary
setup failure uses the existing temporary-directory fallback; an uncertain
attach preserves the scratch image without detach/removal. Verification retains
its original exit status. Disposable host-volume cleanup runs separately after verification,
with phase logs in Git-private `ci-cleanup/` metadata; a failed detach preserves
the scratch directory rather than deleting a mounted volume. Cleanup never
opens or stops an editor or uses a device. A blocked cleanup cannot hold a
completed verification, and failing verification still refuses the push.

The user's legitimate PC installation goes in; an ARM64 IL2CPP APK plus an independently
synced content payload comes out. Everything game-derived stays under the ignored `work/`.

| # | Step | Command | Main code | Output under `work/` |
| --- | --- | --- | --- | --- |
| 1 | Accept input | `./dev inspect --full`, then record the ID in `config/accepted-input.json` by hand | `scripts/lab/inventory.py` | `inventory/` |
| 2 | Check before building | `./dev preflight` (host + selected storage); `--host-only` omits device access; builds run host gates | `scripts/lab/build.py` (`preflight_host`, `preflight`) | selected preflight receipt; refuses on drift |
| 3 | Decompile and export | `./dev decompile`, `./dev export-project` | `scripts/lab/recovery.py` | `config/reconstruction.json`, exported project |
| 4 | Assembly transforms | `./dev prototype --action assembly-transforms-check` (verification only) | `scripts/lab/assembly_transforms.py` → `tools/assembly-transforms/` | none; verifies three transformed plugins in disposable `.local/` scratch |
| 5 | Compose the project | `./dev prototype --action composition-update-stage`, then `composition-update-dependencies` | `scripts/lab/composition_migration.py` | `lab-project/` |
| 6 | Whole-catalog content | `whole-catalog-prepare` → `-host` → `-repair-bindings` (when recorded) → `-contracts` → `-host-providers` | `scripts/lab/whole_catalog.py`, `tools/catalog/` | `experiments/whole-catalog/<timestamp>/` |
| 7 | Bundles, payload, APK | `whole-catalog-build`, or `whole-catalog-code-build` for a code-only change | `whole_catalog.py` (writes the linker descriptor through `preservation_descriptor`, J506; refuses uncommitted `tools/unity`, `tools/catalog`, `android/Assets/Editor` sources, `build.build_source_identity`, J738) → `build.py` → exact editor via MCP | APK + payload receipts, with `source.commit` |
| 8 | Install and sync | done by `whole-catalog-run`; alone: `./dev install`, `./dev sync-data` | `scripts/lab/device.py` | placement receipt |
| 9a | Catalog registration scan | `whole-catalog-run` | `whole_catalog.run_integration` | `integration-<timestamp>/device-<timestamp>/` |
| 9b | Gameplay run | `./dev check-baseline` for the standard check ([BASELINE.md](BASELINE.md)); broader runs still use untracked runners in `work/experiments/whole-catalog/gameplay/` ([debt](#known-structural-debt) item 8); captures: `./dev logs`, `crash`, `screenshot`, `perf` | `scripts/lab/baseline.py` + `device.py` | `experiments/baseline/<timestamp>/`, `movement-batch-*.json` |
| 10 | Record | append a journal entry, `python3 scripts/journal-index.py`, replace `PORTING_STATE.md` | — | — |

Steps 6–9a are the `./dev prototype --action whole-catalog-*` actions listed in
[whole-catalog-integration.md](whole-catalog-integration.md#reusable-fixes-and-commands).
`whole-catalog-run` installs, syncs and launches, but it pushes `whole-catalog-selection.json`,
which makes `PortSession.Start` exit: it checks catalog registration
(`whole-catalog-result.json`), not gameplay. Gameplay is launched by a runner that pushes an
attempt-bound `movement-batch-selection.json` and then launches the app.
The standard `baseline.py` owner checks selector absence with a successful,
complete runtime-directory observation before writes. Process replies are typed;
transport errors are never absence. Live reports remain bound to the launched
PID. Its teardown attempts removal, force-stop and the configured sleep policy,
verifies the resulting absence states and records them in `result.json`.
An unknown observation or failed cleanup refuses acceptance. Setup retains the
selected-device ownership/storage gates and APK-embedded attempt identity;
teardown handles a push that succeeded remotely before a local timeout.
`baseline_feedback.py` owns the separate host-only feedback projection: read one
explicit baseline result, validate typed facts and teardown claims, and create
one new local preview. Its fixed tokenless issue-draft URL is optional and never
opened automatically. Raw errors, paths and unknown fields are omitted; no device
or attachment collection occurs. Setup, exclusive output, process teardown and
review limits are in [BASELINE_FEEDBACK.md](BASELINE_FEEDBACK.md).
`AndroidFeedbackDraft` and `AndroidFeedbackScreen` own the separate native
settings feedback form: manual notes and fixed, bounded build facts produce
an exact preview, followed by explicit review consent and clipboard copy or a
fixed GitHub draft URL. Copy success requires reading back only the just-written
report; browser dispatch reports a request, not confirmed submission. The form
reads no receipt, log, account, device identifier or attachment. Back, settings
exit and session cleanup clear notes and consent. The settings/application/GUI
owners give the visible modal input priority while retaining the owned pause.
Android clipboard, browser handoff and the composed settings route require
device acceptance; host fixtures exercise the authored flow and refusal paths.
`LabDiagnostics` replaces `snapshot.json` on its existing periodic schedule.
Only its startup/lifecycle snapshots use the full `LAB_SNAPSHOT` console record;
periodic JSON is not retained by the original console. Original and error logging
stay unchanged. During completed-session reclamation, `SessionResourceBoundary`
releases already-destroyed HurtBox targets from returned bullet-hit pool entries,
with no live world/network, after deferred destruction. It preserves live and
checked-out hits and records its release count with existing registry cleanup.
The host memory summary keeps immediate post-collection and subsequent-menu
managed slopes separate, including the observed final menu without extrapolation.
The current `settings-write-interrupt-check` host diagnostic uses
`settings_write_interrupt_check.py` and the authored `LabPendingWriteStop` SDK
actor. It requires an idle, owned APK and a matched diagnostic menu selector,
saves the existing native values, observes the actual pending-file creation,
then requests normal shell-authorized package stop for the bound PID/UID. An
unchanged primary and retained pending transaction are required before cold
recovery/resave can qualify; a missed window refuses acceptance. The original
store performs every save. Teardown removes only its selector and unique SDK
temporary files, stops its owned process and verifies OLED sleep. Protected
profile/results hashes remain unchanged. The SDK actor exits explicitly after
its observer completes, with a separate 35-second process deadline because
Android may retain a non-daemon observer thread. Initial primary bytes and
observer failure output are preserved privately. This does not simulate power loss or
ENOSPC, and runtime qualification remains a separate journal gate.
The current `session-memory-check --memory-snapshots` diagnostic extends
`SessionResourceBoundary` with native/managed heap captures before presentation
at menus 2 and 4, after the completed worlds have been reclaimed. It requires an
attempt-matched opt-in and an idle Development player. Native callback completion
and a nonempty owned file are required before the host proceeds. The host copies
only that generated snapshot, verifies its SHA-256, then removes the exact device
file; profile/payload data are untouched. Snapshot allocation and pauses exclude
this case from ordinary growth/performance acceptance. The existing static-root
walk is a separate diagnostic. Heap files, databases and analysis stay private.
The public Unity `MemorySnapshotDataTools` CLI can analyze them without an Editor
package; no parser or third-party implementation is vendored into the lab/player.

`AndroidTouchInput` is the playable bridge's pointer producer. Stable finger IDs
own independent movement, camera and eight native action captures, plus pause.
Short action taps remain pending until a fixed tick consumes them; missing/canceled pointers,
pause, focus loss and viewport changes neutralize capture. Reacquisition requires
all touches to lift. Captured primary touch GUI events are claimed before legacy
widgets. The opening pointer retains GUI ownership through pause until lift,
so its release cannot close the new modal. Fresh modal gestures remain available.
A pause request from any captured finger queues through the existing settings
owner and neutralizes the bank immediately.
The native pause button shares its exact geometry with the producer; the lab
takeover button occupies the reserved top strip. `NovaInputBridge` routes these
requests through the existing original bank and `NovaThirdPersonView.LookTouch`; the adapter changes no motor,
transform, native skill or gameplay clock. The original world owner presents the
controls and permits explicit touch takeover of automatic diagnostics. Thor's
ordinary route is touch-only, with no measured controller mapping. Nova's
measured physical route and the explicit automatic route remain separate.
The actual production pointer owner and camera-delta method execute against the
pinned editor's managed Unity API in `test_android_touch_input.py`; native
consumption and full gestures still require the device case.

Settings persistence remains owned by `AndroidOfflineSettings`. Its existing
validated pending/primary/backup transaction is unchanged. `TrySave` converts
expected storage/validation failures into a bounded message; the settings owner
keeps its pause/modal and marks persistence false until an actual successful
retry. Difficulty changes use the same owner. Raw exceptions and private paths
do not enter the player message. `test_android_settings_store.py` executes the
production store on a real temporary filesystem with a controlled JSON peer;
partial-pending recovery is a contract test, not proof of a captured power loss.

The existing `OfflineApplicationSession` also owns `Screen.sleepTimeout` for a
validated playable coordinator, from `Start` before catalog preparation through
`OnDestroy`. Menus/loading retain the same awake policy as active play; release
restores the captured prior policy only while the owned NeverSleep value remains.
The body-input iterator keeps its historical screen lease only for non-playable
experiments, so playable input cleanup cannot overwrite application teardown.
Explicit Android sleep/background actions remain available. The production
lifetime methods execute in the native-feedback host fixture.

The exact editor is started with `./dev editor --target lab --action open`; send it one
mutation at a time. Device acceptance is always the real device, never the editor.

Current iteration support: `build_timing.py` owns host wall phases and
request-bounded editor-log/Bee observations. `LabBuild.cs` records inclusive
BuildReport steps, bundle generation and player duration; parallel compiler
work is distinct from elapsed time. `device.py` records install/storage and
payload hash/transfer phases. `common.cached_hashes` memoizes verified digests
by device/inode, size, modification and change times. Normal whole-catalog
builds rehash and regenerate `work/build-hash-cache.json`; explicit iteration
actions may reuse it. The cache retains only identities used by that operation.

`iteration_apk.py` owns `whole-catalog-fast-build` packaging. A normal build
generates `work/config/iteration-base.json` from its APK and Gradle inputs.
The fast action verifies frozen content, stages committed C#, runs the normal
Development IL2CPP native pipeline and stops at the last
`IPostGenerateGradleAndroidProject` callback before Gradle. The intentional
BuildPlayer cancellation and its original errors are recorded separately from
iteration-export completion; an unrelated build error refuses. Iteration enables
`StrictMode` callback dispatch; any observed Gradle build phase also refuses.
The host holds the editor mutex while it replaces the complete generated assets/native set,
preserves unchanged ZIP records, aligns and signs using the existing local lab
key. Failed attempts remain local; unsigned/alignment intermediates are removed
after packaging. Each normal cache retains its own `iteration-base.json`; the
active anchor is replaced only by another normal build. Iteration receipts
reference that normal cache's hash-verified `payload_directory`, without another
payload copy, and bind its previously verified signing certificate.
`whole-catalog-scripts-build` evaluates `BuildScriptsOnly` with the same owner;
it is not an acceptance build. `apk-member-compare` compares hash-bound builds
of the same source without hiding build metadata differences. Normal full-build
acceptance remains required. Commands and limits: [fast iteration](fast-iteration.md).
Linked worktrees use the [shared build owner](#shared-worktree-build-ownership).
Full staging retires predecessor-only authored C# copies through
`build.retire_staged_runtime_sources`: the previous successful build commit,
exact source bytes and pinned GUID must match before removal. A private
`work/coordination/staging-retirements/` receipt records that reproducible owner.
Edited/unknown files and code-only membership changes continue to refuse.
The three generated `StreamingAssets/Lab/*StageReceipt.json` files (camera,
original audio and music observer, plus their metadata) are APK-only provenance.
Code-only builds may regenerate those exact files while external bundle inputs,
audio bytes and all other StreamingAssets remain frozen. This uses the existing
`whole_player_inputs` contract, not a general StreamingAssets exception.
Host contracts: `test_iteration_apk.py`, `test_install_transport.py`,
`test_build_snapshots.py`. Build/experiment artifact snapshots use APFS clones
with an independent-copy fallback; snapshot verification can be requested while
ordinary builds hash each source artifact once.
`common.copy_file_clone` is the shared file-copy primitive. Camera/music
preimages and atomic stage replacements also use it, retaining their existing
scope checks, expected hashes, fsync and final rename. The hooks load this
authored sibling helper only when copying, keeping absent-receipt inspection
inert. The camera recipe pins this transitive source; synthetic atomic-copy
contracts are in `test_artifact_clone_hooks.py`.

Current optional debugging symbols (`--debug-symbols` on `build` or
`whole-catalog-code-build`) flow through `main.py`/`actions.py` to
`whole_catalog.py` and `build.py`. `LabBuild.cs` requests
`AndroidCreateSymbols.Debugging` in a fresh request directory; ordinary requests
select `Disabled`. Its `finally` restores the prior editor setting.
`scripts/lab/symbol_artifacts.py` verifies the sole request-owned ZIP, mandatory
APK/ZIP/library hashes, matching ARM64 ELF GNU Build IDs, named symbols and
DWARF information. The symbol-mode cache includes the validator hash and retains
both artifacts; missing, ambiguous or altered artifacts refuse reuse. These
files are generated build outputs, not new required local input. Archive reads
are bounded separately: 512 MiB for the stripped APK library and 2 GiB for the
full debugging library. Host contracts: `test_symbol_artifacts.py` and
`test_symbol_build_mode.py`. J765 validates the first exact-editor ZIP and
matching ELF identities after correcting the debugging size bound; canonical
build publication and device qualification still require the retry. Retention
alone does not symbolicate the existing `performance_capture.py` report.

`--capture-player-linker-inputs` on `whole-catalog-code-build` is current,
opt-in build support for audio integration. `PlayerLinkerInputCapture.cs` in
`android/Assets/Editor` implements the pinned editor's `IUnityLinkerProcessor`;
the existing Android-asset staging owns its copy. The callback preserves an
inert linker descriptor on ordinary builds. Opted-in captures require the
active request ID, committed source ID, accepted input ID and Android target.
They inventory only Unity's supplied pre-strip `inputDirectory` and independently
copy every DLL to request-owned ignored storage, checking hashes before and
after the copy. No Library/Bee directory search supplies inputs.

`scripts/lab/player_linker_receipt.py` verifies saved path/hash/size identities
and seals that inventory with the successful request and APK hash. `build.py`
gives each capture a fresh request-specific output/cache namespace and refuses
reuse; default builds retain their existing invocation/cache behavior. Output
ancestry, stale identities, changed snapshots and missing callback evidence
refuse.

The additional `--capture-il2cpp-invocation` opt-in requires
`--capture-player-linker-inputs` and remains false by default.
`Il2CppInvocationCapture.cs` owns its editor pre-build/final-report boundaries: bind the
active exact-version editor process, source/input/request and BuildReport GUID;
inventory Bee files and record the editor-log byte boundary before building;
then retain the unchanged prefix hash and new log slice for that same successful
BuildReport. `LabBuild.Build` completes the witness from the exact report returned
by `BuildPipeline.BuildPlayer`; the Unity postprocess callback leaves it pending
because its summary can still be `Unknown` (J975). Finalization retains strict
success, error-count and GUID checks and clears pending state. Ordinary builds
return before capture setup.

`bee_codegen_capture.py` owns the host verifier. It joins that fresh log slice
to the Player Bee graph, response-file metadata, changed conversion trace,
managed input closure and final APK/BuildReport identity, then copies and
rehashes the managed snapshot under request-owned ignored storage. Multiline
trace parsing rejects malformed separators and extra conversion/Player records.
Player invocation parsing admits one explicitly evidenced exit-4 timestamp
invalidation followed by successful same-editor Android DAG regeneration and
one successful retry on the same DAG and working directory (J977). Unsupported
failures, missing or ambiguous regeneration witnesses and multiple successes
still refuse; this does not relax conversion-trace freshness.
The toolchain's version and revision fields form the exact editor pin.
`build.py` calls this owner only for the explicit opt-in. Missing, unchanged or
inconsistent execution evidence refuses the enriched receipt while preserving
raw build outputs. No cache is cleared merely to obtain a receipt.

This is generic same-build evidence, not an exact argv vector, transformed-audio
stage equivalence or runtime acceptance. J852 qualifies host contracts only;
J975 records the actual Android callback's premature result and the corrected
host contract. J976 qualifies final-report receipt completion on the exact editor;
its unchanged conversion trace still refuses a fresh execution claim. J978
qualifies a fresh owning build after preserving only the exact prior graph-declared
trace output under the shared mutex; all other cache inputs remain intact.
`player_il2cpp_receipt.py` retains the historical J843 legacy-log verifier and
its tests; the current build no longer calls that legacy collector.

`test_player_linker_receipt.py` covers the existing input capture and opt-in
forwarding. `test_player_il2cpp_receipt.py` covers the joined receipt contract;
`test_describe_runtime.py` and `test_il2cpp_invocation_capture_runtime.py`
execute the authored C# helpers against minimal host stubs and skip without the
pinned Mono compiler. Exact-editor compilation and later device acceptance
remain separate. This narrow build-receipt addition serves original audio;
alpha retains packaging ownership.

`whole_catalog.analyze` owns the host dependency closure. Audit, reconciliation
and root-binding repair supply the accepted decompile root to
`entity_state_gameobject_fields`, a scoped field reader checked against the
accepted assembly metadata. `entity_state_reference_closure` follows serialized
string GUIDs only for native EntityStateGameObject fields, retaining inherited
field identity and nearer-field shadowing. It requires an exact unique original
GameObject catalog location and existing conversion; unresolved or ambiguous
edges remain explicit issues. Resolved files enter the existing closure walk
and manifest without becoming provider roots. No runtime loader alias or
gameplay-state replacement implements this repair. Host contracts live in
`tests/test_whole_catalog.py`; generated closure/manifest data remains ignored.

### Device selection and storage receipts

Device selection uses an explicit allowlist/default model.
`work/config/local.json` accepts `device_serials`,
`device_serial`, and `device_settings[serial]`. Device actions accept `--device SERIAL`
or `LAB_DEVICE=SERIAL`; with multiple attached devices and no explicit selector, they
refuse to choose. An explicit serial outside the configured allowlist also refuses.
Top-level legacy settings are fallback values for the default device only. Per-device
overrides cover `storage_mode` (`adopted` or `internal`), `internal_reserve_mib`,
`apk_install_limit`, `sleep_display_when_idle`, `display_models`, and `display_count`.
The exact Thor display profile requires two physical panels. `Device.display`
owns the original vendor `dual_screen_display_mode` for the current transaction,
selects top-only mode before wake and requires stable named physical-panel
ON/OFF readback. Nested contexts retain the first original mode. Teardown sleeps
the panels, restores that mode and verifies both OFF; an unsupported top-only
transition refuses and performs the same cleanup. J1071 records the current
firmware refusal, which blocks further Thor gameplay runs.

`scripts/lab/device_context.py` owns pure selection, storage policy and receipt namespace
resolution. Its explicit migration transaction requires verified ownership, preserves
source receipts/counters, and publishes `.device-context-active.json` last. Hashes in that
marker audit the original copy; ordinary receipt updates and reset keep the namespace
active. A malformed marker refuses selection. `Device` freezes the selected serial,
settings and receipt root. All current and
retained historical device callers use that instance's receipt API. CLI cleanup sleeps
only the exact instances it awakened, including on failure. Dual-panel profiles require
both physical internal panels to report OFF before sleep is accepted.

Receipt and evidence paths reject symlinks and non-directory components beneath the
chosen work root; an explicitly chosen work root may itself resolve through a symlink.
Every receipt lookup rechecks the active namespace and refuses a changed root. JSON
receipt/counter links also refuse, including dangling links during migration.
`Device.evidence_directory` validates new per-device evidence paths before creation.
Bootstrap smoke records install dispatch separately from success: an ambiguous failure
queries the selected package and cleans up only when it was absent before dispatch and
is now confirmed present. An unavailable follow-up query preserves the primary failure
and reports cleanup uncertainty.

`scripts/lab/installed_attempt.py` owns read-only diagnostic selector identity
for baseline, survivor and completed-session checks. After `Device.owned()`
validates selected-device ownership/placement, it reads the receipt's APK artifact
once, verifies that byte snapshot against the receipt hash, and parses the same
bytes with the existing UnityPy reader. Exactly one authored MovementBatchProbe
TextAsset must supply a nonempty attempt. No mutable project config, latest-build
attempt, cache search or timestamped run evidence supplies identity. The exact
owned artifact must remain available; missing/changed/ambiguous content refuses
before selector writes. This helper writes no receipts and changes no storage,
package or current-build gate. `test_installed_attempt.py` covers identity,
refusals and replacement during parsing; runner fixtures keep project and
installed attempts different.

`scripts/lab/build_lock.py` owns a persistent advisory kernel lock and owner diagnostics.
It is reentrant in one thread and hands its open descriptor to the editor client.
A child using an inherited descriptor validates and forwards that same descriptor
through further subprocess hops; its empty in-process registry does not drop the
parent lock. Invalid descriptors and released owner receipts refuse (J970). Build
coordinators retain it through staging, Unity completion and result publication; editor
actions share it and refuse an outstanding player build. Bootstrap batch builds use the
same path. Device runs do not acquire it. Direct editor player-build dispatch requires
the receipt-polling coordinator. Protected R9 direct helper integration remains deferred
while the parallel session owns that file; its supported CLI enters through the shared
whole-catalog/build coordinator.

Session ownership and the host build mutex are separate. The incumbent session must
remain able to use the existing CLIs while it holds its coordination file. A waiting
orchestrator checks that file before every editor/device action and can additionally set
`LAB_COORDINATION_GUARD=1` for transport-level refusal. That opt-in is not ownership
authentication. Migration always refuses while the file exists, regardless of this
setting. The host Unity build mutex is mandatory for every caller.

`./dev preflight` combines host/input validation with selected-device live storage checks.
`./dev build` runs host preflight only and holds the global Unity build lock at
`work/coordination/unity-build.lock`; install, sync and gameplay actions do not take that
lock. Every install still queries live storage and free space and enforces the selected
device reserve. Scoped receipts live under `work/device/<serial>/`. The explicit
`migrate-device-receipts` command migrates legacy `work/device/` receipts after the
coordination lock clears, preserve the originals, and write its activation marker last.
J595 migrated the configured Nova's receipts and verified both baseline modes after an
in-place adopted-storage install. Legacy receipt bytes remain intact. Extra devices and
their storage/display contracts remain unvalidated until explicitly allowlisted.

J755 records the authorized three-device configuration: baseline Nova uses adopted
storage only, second Nova and Thor use internal storage with live reserve gates.
The second Nova passes both standard game checks after the current attempt-bound
measured Nova mapping is supplied. J762 qualifies Thor's explicit automatic
diagnostic path through both standard checks; physical input remains unavailable.
Its two physical panels both verify OFF. Under the J818 session split, this
gameplay session owns original gameplay, audio and animations on adopted Nova.
The separate public-alpha session owns launcher/packaging, controls, settings/UI,
end-run menus, feedback, stability/memory and playtest tooling on internal Nova.
Thor is an unassigned shared spare and needs explicit agreement before use.
Each device has one runner; the shared Unity build lock still serializes builds.
These roles do not imply generic-controller, normal-game or performance
acceptance on the additional devices. Installs select an explicit device and
the session's own frozen APK rather than a mutable current-build pointer.

`InputSessionPolicy` in `NovaInputBoundary.cs` owns the explicit game-input
choice. The exact Nova model retains measured, attempt-bound physical input.
Only the observed Thor model with the existing `-bringup` selector permits
automatic diagnostic input without a physical mapping. Ordinary Thor selects
touch input and skips the physical-map startup wait; the explicit playable-start
configuration is still required. Missing and unknown model identities refuse.
`NovaInputBridge.automaticDiagnosticOnly`
defaults false, so legacy mapped and null-mapping behavior is retained.
The validated diagnostic path reports its source and unavailable physical
input, bypasses raw joystick/presence reads, and feeds the existing input bank.
The offline application/settings and integrated-world owners retain touch
menus, permit manual takeover when touch or measured physical input is available,
and guard physical restart/settings consumers.
Their existing iterator cleanup and bridge disable neutralize input and
release session ownership. `test_portable_diagnostic_input.py` executes the
production policy/predicates and checks consumer guards; device acceptance is
separate (J762). The default-start fixture also verifies that Nova keeps its
attempt-bound mapping wait and a default-off player stays disabled.
Availability flags are authoritative: Unity's JSON serializer
can emit default inline mapping/raw placeholders for null runtime references;
those wire values are not measured input.

`NovaInputBridge` also owns an opt-in cumulative skill-edge witness at the
existing `PushState` sink. `SurvivorSkillInputCoverage` enables it only for the
bounded MUL-T diagnostic, snapshots each request, and requires one fresh edge
after a later physics tick alongside the native callbacks and stance. It refuses
missing/reset/ambiguous witnesses and disables observation on stop/dispose;
neutral cancellation precedes sampling. Ordinary input requests and other
coverage modes retain their existing paths. Host contracts execute the production
counter/classifier, including late sampling and a second edge across separate
samples (`test_toolbot_input_edge_witness.py`). J764 records the motivating
device failure; the durable witness still needs its own device build.

CPU capture (`scripts/lab/performance_capture.py`, current host implementation):
`./dev perf --action cpu --target LABEL` takes a 15 s system simpleperf call graph
from the selected device's already running, owned foreground lab process. Setup
validates ownership, APK hash, one PID, foreground activity and the validated runtime
receipt. Before/after reports preserve available attempt/session/stage/frame context;
a changed process, APK or previously available session identity fails. It does not
launch gameplay or install a profiler. J610's first current-Nova attempt is refused
by Android perf-event permissions; no call graph is available from that path.
Raw profile, symbol report, receipt and failures stay in validated
`work/device/<serial>/performance/<attempt>/`. A symbol-report failure retains the
successful raw capture and explicitly records the report error. Teardown removes
only its unique remote profile after a verified nonempty pull; a failed pull or
timeout preserves the remote output without guessing a process to kill. The caller
retains ownership of the existing gameplay run and display. Host transport/refusal
contracts are in `test_performance_capture.py` and `test_performance_cli.py`.
Typed survivor/diagnostic/assistance/profile metadata and runtime errors accompany
each available endpoint. `stable_stage_gameplay` qualifies the two sampled
endpoints separately from raw capture success; missing context, non-playing
phase, changed scene/transition count or runtime errors prevent that claim.
Matching survivor identity is reported separately. These endpoint comparisons
do not prove uninterrupted gameplay or complete ability behavior between samples.
Explicit `--profile-scope app` selects an independent software task-clock:u
hypothesis and requires live selected-package DEBUGGABLE metadata. It retains
all ownership/PID/foreground/runtime endpoint checks, but labels the raw profile
as the owned package process set with pid_attribution_exact=false. The system
simpleperf may internally use Android's app-UID helper; the wrapper requests no
root, launch, restart, profiler installation or settings change. Device syntax
and permission support remain measured gates. Any denial is preserved without
retry or fallback; default PID mode remains unchanged. This mode is not a
successful trace until the selected device produces one.
J761 records a selected internal-storage device's app-scope capture. Its
qualification includes stable run/stage endpoints; it supplies no exact-PID,
managed-caller, frame-window or sustained-frame-rate guarantee. Camera frame
counters are cumulative, while timing recorder averages reset on each sample;
compare their actual intervals rather than treating a cumulative maximum as a
new stall in every report.

Bare `./dev perf` retains the existing dumpsys capture behavior.

Assembly transform verification (`scripts/lab/assembly_transforms.py`, current):
`recipe/assembly-transforms.json` pins the accepted input, AssemblyProbe sources,
Mono.Cecil and ordered arguments/input/output hashes. The checker first applies
`--optional-presentation-guard` to original `RoR2.dll`, then independently applies
`--wwise-unavailable` to the original API/MonoBehaviour Wwise pair. `AudioGuard` is
historical; the optional presentation transform already includes its getter change.
The checker copies managed DLLs to scratch for resolution, builds the tool there,
and compares rebuilt hashes with the recipe, generation marker and uniquely placed
project plugins. Any drift fails. `--work-dir` selects read-only inputs in another
local work tree. Temporary tool/intermediate/plugin files are removed on success
or failure; there is no persistent state. This verifies plugin bytes only, not
importers, script orders or project initialization. Host contracts:
`tests/test_assembly_transforms.py`.

Composed audio playback remains unqualified; J872 observes original engine/bank
readiness with the path warning removed; J875 localizes the first point-sound
failure to transform access after emitter acquisition returns. The default-off original-owner
integration uses `runtime/session/PortSessionOriginalAudioOwner.cs` after the
offline menu and before selected body activation. It coordinates the existing
`WwiseIntegrationManager.Init` and original prefab callbacks; `AkInitializer`
and `AudioManager` retain native initialization, service, focus/pause and
termination ownership. It adds no second native engine owner. Its bounded
snapshot refreshes at every session-report save, including teardown observations.
When original audio is Ready and passive capture is explicitly requested, it also
reads the managed default-listener count. It retains only a known flag and count;
default-off, pre-ready and failed reads remain unknown. This read-only census
does not establish native registration or retain listener objects.

The same coordinator attaches one callback to the initialized original
`AkSoundEngineInitialization.terminationDelegate` after admitted audio startup.
That source-owned delegate runs before its synchronous bank clearing. The
callback resumes the same initialized native engine on Android so focus-loss
suspension cannot withhold bank processing; it issues no Init, ClearBanks,
RenderAudio or Term call and changes no ordinary focus/pause or output routing.
Default-off, no-audio and unavailable-native startup paths do not attach it.
Once attached, native initialization governs teardown even if consumer readiness
has already been withdrawn.
The snapshot records whether it is attached; current-process logs retain the
native wakeup result or bounded failure type. The coordinator removes only its
callback after both original Term witnesses or on destruction, retaining other
delegate subscribers. The compiled owner fixture checks admission, duplicate
setup, returned/thrown native failures and owned removal. Healthy application
Quit remains a separate device gate; J1067 records the motivating ANR stack.

`runtime/session/OriginalNetworkSoundEventCatalogOwner.cs` owns process-scoped
native network-sound catalog admission after original engine/bank readiness and
before selected-world activation. It obtains the complete original definition
family through `WholeCatalogComposed`, delegates index assignment to the shipped
setter, and verifies count, exact definition references, indices and nonzero
native name hashes before announcing original catalog availability. A nonempty
foreign table is refused rather than overwritten. Nonzero hashes do not prove
bank-event presence or playback. Serializable bounded observations distinguish
unknown counts from measured zero and retain zero-ID ordinals. `PortSession`
records missing or failed admission as its primary failure before starting the
selected probe. Default-off/no-audio decoding remains under its existing owner.
Definitions remain rooted with process audio; session/stage teardown does not
clear native global indices. The existing audio lease and original Term witnesses
continue to govern bundle release. Host admission/failure contracts live in
`tests/test_original_audio_network_sound_host.py`; Android mapping and effect
playback remain separate device gates.

The complete source family includes original definitions with empty event-name
strings. Admission preserves every row and forwards those strings unchanged to
the original setter; removing them would change index identity. Null strings
refuse before native mapping. The snapshot separately records whether source
length was observed and bounded sorted empty/null ordinals. Empty-string hashes
remain distinct from authored event or bank presence evidence.

`tools/unity/support/audio/core/` owns admission, readiness and copied lifecycle
observations. `support/audio/bootstrap/` owns the explicit request, hash-bound
bank preparation, Android platform resolver, Java-first library load and native
monitor lease. These are separately compiled support assemblies, outside the
runtime source selection. Generated request and bank pins default to disabled;
build-time generators must write derived sources to ignored output directories.
Original audio can be admitted only after all declared preparation succeeds;
actual engine, bank and event results require device evidence.

`WholeCatalogComposed` supplies the existing GUID-bound settings asset and a
single process-audio lease over its existing content bundle and declared
dependency closure. Session locators and caches still detach normally.
Default-off release still unloads the bundles; an admitted audio owner defers
unload until both original Term calls return and active session ownership ends.
Only a refusal before both manager admission and native Init attempt can release
early. Retained input, attempt and manifest hashes constrain bundle reuse.
Its nested `RetainedDependencyOwners` captures the manifest's transitive bundle
graph, including cycles, against the exact loaded instances at audio admission.
`CleanupBodyCatalog` transfers its manual body bundle into this owner;
`TeleporterWorldSession.ReleaseObjectiveBundlePreload` transfers the existing
provider handle and location. Next-session acquisition transfers those owners
back without another native load or provider acquisition. The source audio
release gate remains authoritative. A Term during an active session defers
dependency release until `WholeCatalogComposed.Release`; a Term between sessions
releases the parked owners immediately. Ownership drift refuses before release
and preserves the lease identity for retry. The host contract is exercised by
`tests/test_retained_catalog_dependencies.py`; device restart and memory impact
remain unqualified (J914). The historical private composed-audio candidate below
is separate.

The current `whole-catalog-build` action invokes
`scripts/lab/original_game_audio_build_hook.py` under the existing host build
mutex, before computing project/cache identity. Missing local selection means
default off. An explicit `work/config/original-game-audio/selection.json`
binds every protected input; destination builds use their own work selection.
The original-audio producer's standalone observer compiler is shared by its
requested and default-off variants. Its exact deterministic output is qualified
against the music observer's active game/API/Core tuple; prior Core artifacts
remain restoration inputs only. The portable host contract skips when the pinned
Unity Mono/Roslyn is absent and otherwise reproduces the current output from two
source/output roots (J972).

`original_game_audio_produce.py` compiles the observer, core and bootstrap with
the pinned editor, Android define and deterministic compiler. The authored
`support/audio/managed-producer/` transforms the accepted raw API and guarded
game independently; `support/audio/generators/` produces bank and request pins
without editing authored sources. Native ABI inspection uses the official
Release plugin, distinct from the explicitly selected instrumented runtime.
Generated contracts precede derivative request sources to avoid circular pins.
Authored .NET helper builds disable SourceLink so changing repository revisions
does not change their pinned generated metadata (J863).
The cache binds producer sources, recipes, editor references, compiler/tool
identities and explicit inputs; cached generations revalidate that receipt.
The same build hook synchronizes the original `SoundEmitter.prefab` before
project/cache hashing. Requested audio restores its exact accepted `AkGameObj`
component; default off restores the sanitizer's stripped form. Accepted input,
source bytes, asset/script GUIDs and the selected project must match before
writing. The original component owns its runtime lifecycle; no replacement emitter
is introduced. `source_scene_candidate.prepare` also consumes that existing
validated audio selection: requested scenes preserve original Wwise/RTPC
components, serialized fields, references and enable states. Default-off scenes
retain the historical omission. Global-owner roots remain inactive. The current
full build synchronizes that mode before stage-map/cache generation; code-only
and fast builds refuse a change requiring scene content. Destination R6 uses
the same selection, while R9 refuses a changed mode instead of rewriting R6.
The process audio admission already precedes selected stage loading.
`StageGeometrySession` permits source SceneInfo audio only when the original
owner is Ready and records its loaded scene-audio component census. Original
scene activation/unload retains callback/bank/event teardown ownership. No
extra initialization, event, volume, position or output routing is added.
Host contracts cover scene variants and source activation/rollback/retirement;
composed stage audio and natural Quit require device evidence.
`original_game_audio_stage.py` checks exact assembly preimages, GUIDs and owned
payloads before staging. Requested stages also package the exact bank-cohort
receipt at `Assets/StreamingAssets/stage-receipt.json`, the URL consumed by
`GameAudioOriginalPayloadCopy`; the separate `Lab/OriginalGameAudioStageReceipt.json`
records project ownership. Historical 164/165-output bank-only stages remain
recognized for exact owned upgrades. Current R2 bank receipts keep 154 bank rows
and add a separate 120-row streamed-media closure; the artifact/project receipt
owns canonical `Media/<id>.wem` targets as a distinct role. The shared validator
binds source metadata, exact paths, IDs, references, hashes and sizes before writes.
`generators/original_media_plan.py` owns the pure selected-bank media plan,
checking both bank-index and SoundbanksInfo modes against the full accepted
inventory. `stage_original_game_banks.py` snapshots original media bytes as well
as banks into a new ignored stage root; no source game input is modified.
`GameAudioOriginalPayloadCopy` validates the request-bound receipt, checks existing
payloads and available bytes on the actual persistent filesystem, then copies
through verified temporary siblings before original Wwise initialization.
Its Android IO contract currently requires the bank root to equal the app's
persistent root; a nonempty bank subfolder refuses. It never changes native
paths or deletes conflicting data. New metadata/ownership and synthetic host
contracts are covered by `test_original_audio_media_plan.py`,
`test_original_audio_payload_copy_receipt.py` and the existing staging/pin tests.
These owners qualify content placement only; playback remains a device gate.
Default-off restores the ordinary guarded assemblies
and removes only prior receipt-owned audio payloads, preserving Unity metadata
sidecars. J865 adds one exact predecessor lineage for receipt-verified upgrade
or restoration; unknown module pairs still refuse. The managed transform checks
bank-request stack/branch placement before accepting its output. Current owner
source hashes and the historical ancestor manifest have separate artifact fields.
J870 preserves the original bank-path calculation while bypassing its filesystem
existence warning on Android, where StreamingAssets is an APK URI. The transform
imports the pinned editor's exact platform getter and enum; non-Android keeps
the original probe. The previous valid API can upgrade in place; the older
invalid-IL API is accepted only for restoration to default off.
`core/PointSoundDiagnosticObserver.cs` owns the separately selected point-sound
localization counters and first matching exception stage. Requested audio builds
instrument the exact composed game's original pool/prefab, transform, event-post
and timeout boundaries without changing their calls or exception behavior. The
producer passes the accepted Managed reference directory explicitly when writing
the isolated intermediate assembly. The generated request binds the resulting
game hash and the callsite capability pin; ordinary default-off assemblies retain
no injected calls. The predecessor and current API/game pairs may share an API
hash but must differ as complete pairs; unknown pairs refuse.

The per-session `pointSoundDiagnosticRequested` selector defaults false and
requires the integrated route, ready selected audio and instrumented callsites.
`PortSessionOriginalAudioOwner` owns the matching Unity log subscription;
the Core observer stores bounded scalar values only, never raw messages/stacks
or Unity objects. `PortSession.Save` refreshes its snapshot. Completion, lifecycle
recovery and `OnDestroy` disable and unsubscribe the observer idempotently,
without terminating or releasing the original process audio owner. Event/stage
correlation is best effort and cannot prove native posting or audible output.
The observer retains the existing acquisition markers independently of later
stages and freezes the first matching exception's path and known/unknown emitter
state. Stage zero is a valid first observation; later activity cannot overwrite it.
This adds no game callsite or change to the instrumented game DLL.

`bootstrap/OriginalGameAudioPassivePcmOwner.cs` and
`PassivePcmCaptureWindow.cs` own a separate default-off native-output diagnostic.
The explicit build selection binds its flag through the generated request;
the owner shares the existing native monitor lease and creates no engine or
events. `PortSession.Save` arms once after observing the existing playable-world
phase and positive simulation time.
The optional build selector
`passive_pcm_capture_after_authority_skill_requested` instead waits for a
recognized activation from the existing authoritative player's
`SurvivorSkillObserver`. `PortSession` owns the one-shot
`GameAudioOriginalPassivePcmActivityArmPolicy`;
setup-time callbacks are ignored, and integrated-world cleanup closes the
policy before any recovery return. Observer disposal removes the callback.
The selector defaults false and requires passive MainOutput capture; it refuses
the separate MusicController-output mode. It changes capture timing only and
does not establish that the skill emitted sound or caused the captured samples.
The pure `GameAudioOriginalPassivePcmGameplayGate` consumes requested/one-shot
state, the existing integrated-world phase and finite positive simulation time;
the unrelated results-report flag is not an admission input. The callback counts
bounded finite/nonzero samples with stop thresholds of 10 s or 600 successful
render frames, checked
on the next owner Update tick. Completion, unwind
and destruction close the window idempotently without delaying gameplay.
The exact transformed API guards both original Term paths before native teardown;
uncertain callback removal retains roots and refuses termination. Reports contain
scalar measurements, not audio data. During `capturing`, the report exposes
only its latest validated cached counters and callback output identity, retaining
the active state; they are not a quiescent or atomic PCM-frame proof. Unknown
states remain masked and terminal finalization keeps its fresh unregister check
(J982). Nonzero native PCM alone cannot establish
Android playback or physical audibility. Host fixtures check capture bounds,
ownership, default-off behavior and both actual pre-Term injection branches.

`bootstrap/PcmWaveformReadbackV1.cs` owns optional bounded waveform evidence
within that same capture request. The separate V1 metadata/copy API adds two
imports while `NativeWwiseMonitorLease` retains its eleven imports and schema
3 / 24-slot snapshot. The licensed native bridge preallocates a 1 MiB prefix
before registration; its callback does bounded copying without allocation or
file I/O. After successful exact unregister and native callback quiescence, the
window copies/validates at most 262,144 float32 samples before either original
Term. The finalizer keeps only that bounded managed copy and the Unity-reported
private persistent root. Neither the session profile nor public reports carry
audio bytes or paths.

The original callback-manager Term-return observer finalizes synchronously after
both recorded Term returns and verified monitor disarm (`DisarmAttempted`, state
3, known outcome). The owner Update is only an idempotent fallback with the same
gate; quit does not depend on a later frame. Unverified disarm, malformed data,
or write failure stays in `passivePcmWaveformReadbackFailure`, independent of
engine/capture failure and original teardown exceptions. Create-new raw/sidecar
pairs use a private capture nonce plus the independent native generation, so
later processes preserve older evidence. The sidecar records the three verified
Term/disarm witnesses and a raw-file hash. Successful persistence discards the
managed sample array; native buffer release follows the existing post-Term
monitor disarm. A busy callback retains native storage instead of unsafe release.

`scripts/lab/original_audio_pcm_waveform.py` is the current host-only exporter.
It validates the closed raw/sidecar pair, exact output identity, lifecycle
witnesses, layout/counts, finite samples and meters before writing an IEEE-float
WAV and receipt with create-new semantics. Its CLI requires all capture paths
under ignored `work/`; sample reads are capped before allocation. Explicit APK
identity is a host receipt binding, not an embedded sample attribution. Raw
persistence, WAV generation, event attribution and physical audibility are
separate facts. The existing recovered menu reports its measured Quit target
alongside Start, solely so an owned audio shutdown check can invoke the existing
`Application.Quit` button. Menu/input behavior is unchanged. Host fixtures compile
the actual bootstrap observer with a fake native API and cover failed disarm,
writer failure, no subsequent Update, and repeated-generation output separation.

The optional R2 build selection
`passive_pcm_capture_music_output_requested` selects the original music output
instead of main. It requires the existing passive-capture flag and is bound by
the actual build hook, cache, generated request/pin, artifact manifest and stage
receipt. Missing fields remain false; requested mismatch refuses. At the same
one-shot gameplay boundary, `PortSessionOriginalAudioOwner` snapshots the exact
live, ready, initialized original music owner and accepted non-sentinel output.
`GameAudioOriginalPassivePcmCaptureSelection` carries the immutable mode and
complete unsigned 64-bit selector through the capture window and native monitor
lease. Specific-output failure never silently falls back to main. Reports keep
requested selector and actual callback output identity separate, with exact
string companions for numeric consumers. Both custom native capture calls take
an unsigned 32-bit mode and unsigned 64-bit selector; the producer/stager bind
the corresponding native library. Removal uses the same frozen pair. Known
registration failure performs no removal; unknown native outcomes retain roots
and refuse Term. The previous exact owned native/API/game receipt tuples retain
their existing upgrade/restoration policy. J918 records host/native qualification;
player and selected-output playback remain separate gates.

`runtime/session/PortSessionOriginalMusicControllerOwner.cs` owns the accepted
original MusicController prefab for the admitted process audio lifetime.
`OriginalMusicControllerContract.cs` defines its pure admission and retirement
rules. The audio owner starts it once after the explicit original-audio request
becomes Ready; `PortSession.Save` copies its bounded scalar snapshot. The owner
checks the exact legacy key, source component/listener pair and music output
share set, then invokes the original preload path. It supplies no replacement
Run, camera, user, teleporter or event context. Missing source context remains
observable rather than synthesized. Default-off starts no music controller.

The same owner uses `MusicPcmJoinObserver.cs` and
`AkMusicPcmJoinQueryAdapter.cs` for a bounded read-only correlation record.
Only the requested passive capture's exact owned music output admits sampling;
capture, selector and controller output identities must agree and cleanup must
not have started. At most 24 rows, spaced by 0.5 s, query the playing ID already
returned by the original intro call, its event/segment information and the two
source music state groups. Existing callback/frame counters and finite monotonic
realtime bracket each row and the observed window boundaries. The temporary
`AkSegmentInfo` is disposed. Query failures, missing clocks and owner loss stay
unknown; an unobserved window end remains unknown. Rows retain scalars only, and
the helper has no independent lifecycle or callback registration. It never
posts events, sets state/RTPC values, changes track/output/capture behavior, or
claims output-event attribution or audibility. The existing owner owns setup,
snapshot publication and teardown. Runtime source/layout recipes and the audio
source cohort bind both helpers; synthetic owner fixtures and an optional exact
local API compile check the off-device contract.

The same named owner samples the original current-track getter, scene main/boss
track availability, teleporter gate, source parameter values and exact managed
listener membership at 0.5 s intervals. It reports a branch candidate separately
from the observed track; a source hook can change selection. At 1 s intervals,
while the existing engine reports initialized, it makes three read-only global
RTPC queries for master, music and parent music volume. Existing value fields
require successful finite results with global scope. A separate resolved-value
pair accepts successful finite Default, Global, GameObject or PlayingID scope,
retaining the returned scope; unavailable, unknown and failed values stay
unobserved. These are source/query values, not effective gain or playback.
Optional binding/sample exceptions clear known flags and cannot refuse the source owner. A throttled native query keeps its
own timestamp; failed samples and missing controllers invalidate stale values.
`CaptureSnapshot` also invalidates a missing controller before returning, so
same-frame destruction cannot leave a live-context claim. It never samples or
calls native middleware from report capture. The existing actual-owner host
fixture owns these contracts; player/runtime evidence remains separate.

The music owner retains its asynchronous catalog lease and instantiated source
root through original scene-callback retirement and synchronous source teardown.
Pending loads, failed preload or unobserved callback retirement prevent unsafe
release. `OriginalGameAudioPassivePcmOwner.RegisterMusicBeforeTerm` registers one
participant on the actual installed `PassivePcmCaptureWindow` guard, preserving
the API/Core delegate identity. The guard proves its capture callback absent
before invoking music cleanup; either refusal prevents original Term. After both
original Term calls return, the music lease can release. Owner destruction that
loses retirement observation keeps the state unknown and retains references.

The process owner can activate the original `TriggerIntroMusicStart` component
once after its exact owned controller's observed successful AddOutput queue
result, valid output identity, completed preload and live singleton checks.
`OriginalMusicControllerContract` owns the pure admission and one-shot policy.
Failure, cleanup, no-audio, stop and Term states refuse admission. The owner
creates an inactive child, adds the original component and activates it once;
that component performs its original startup callback. It then deactivates the
component and schedules the child for destruction. The snapshot records
activation requested and inactive retirement, not synchronous destruction or
event completion. The static claim survives same-process owner re-entry.
Timing is explicitly adapted process start; stock splash/intro timing remains
unqualified. The existing original-audio request defaults off. A synchronous
AddOutput success means queued acceptance; native activation and playback are
separate device gates.

The optional source-call observer samples the original MusicController
`AddOutput`, `RemoveOutput` and intro `PostEvent` returns, plus the original
selected MusicTrackDef `Play`/`Stop` state-call returns. Its Cecil transform
preserves native arguments, call count, return consumption and exception flow.
The named music owner joins exact controller/selected-track object identities,
clears temporary instantiation references, and retains bounded cumulative counts
plus the latest scalar per site. Missing callbacks and unknown identity stay
unproven. Exact delegates retire with the existing owner teardown. These returns
do not prove event completion, rendering, output activity or audibility.

The receipt follows audio staging: current API 1ced uses the measured
6f96 → a638 observer → 64628 camera chain. The old 27340 → 4bd3 camera chain,
and its older a205 camera output, remain receipt-bound restoration inputs only.
New staging refuses unknown API/output pairs and mixed observer/camera generations
before changing the project. The raw d540 camera path skips the new observer.
The host music-owner compile fixture compiles the actual owner, contract and observer against authored API-shape declarations and rejects
a static-class-as-value mutant; it does not model Unity lifecycle execution.

The completed passive PCM window exposes the callback's full unsigned output ID
with a separate observed flag and exact decimal-string companion. Known zero
remains distinct from unknown; a stale slot without a callback in this window
is unknown. The native capture uses its explicitly selected main or specific-output mode.
Comparing this identity with the exact owned MusicController output requires both
observations and successful AddOutput; neither equality nor inequality proves
playback or physical audibility.

`recipe/original-audio-owner-sources.json` pins the authored owner cohort and
runtime membership. Both producer compile modes validate its bytes and source
map; camera staging requires the same ancestor pin. Cache identity includes the
owner, source-selection and layout recipes. The narrow reflection surface in
`recipe/music-reflection-preservation.json` retains the bootstrap owner type,
process-owner getter and registration method. Portable synthetic contracts live
in `tests/test_original_music_controller.py`; actual post-strip metadata,
original callback behavior and playback remain separate build/device gates.

The lower-level `original_game_audio.py` is host staging support;
current Unity project mutation belongs to the mutex-protected build action.
Use a full bundle build for the first audio candidate: code-only payload reuse
retains its existing strict contract. J860 records host acceptance only;
post-strip/player, native bank and composed-game audio remain device gates.

Separate native diagnostics
use one disposable engine owner for exact bank buffers, listener/emitter,
event callback, bounded output capture and cumulative monitor; reverse cleanup
retains uncertain ownership. The private managed owner tests the retained
Wwise interface in fresh Unity players and is not the normal game controller.
Its Android filename resolver registers the verified app-private bank directory
with `AddBasePath` after `SetBasePath`, matching the official integration's
POSIX-storage seam. Each result has a separate diagnostic phase; refusal keeps
the first result through owned reverse cleanup. The private managed event owner
pumps RenderAudio with callback serialization each frame. Capture stop moves to
a bounded finalization state; the actual fixture caller keeps pumping while
healthy pending work waits for two consistent stable RIFF observations. Unknown
native outcomes retain ownership and prohibit unload/Term. The strict PCM
container profile preserves a zero valid-bits field as unknown precision;
container output, effective precision and physical audibility are separate facts. File loading, cumulative
middleware errors, event callbacks, PCM and composed gameplay have separate
acceptance gates; a successful bank result cannot qualify all of them.
Their setup/input boundaries are listed in
[LOCAL_STATE](LOCAL_STATE.md#isolated-wwise-diagnostic-inputs); experiment
acceptance and limits are recorded once in J740/J742 and J791. Neither diagnostic owner
changes the default assembly transforms or the current game build pipeline.

The private named-event fixture support adds a source-name-to-ID check before
string PostEvent and validates the matching completion through the same isolated
owner. Its stage/build adapter binds compiled code and the descendant input map;
a separate qualification can retain a raw failed host snapshot alongside a
successful Unity result and independently verified inputs. Device dispatch binds
both records and runs the negative control before the positive event, with owned
reverse cleanup. LOCAL_STATE names these private support producers; J845 owns
their result. They do not replace the original game initializer/controller or
make the game audio-capable.

The ignored native-build-feasibility producer recompiles the authorized Android
bridge against its exact SDK with an isolated, process-local NDK r25c. Unity
keeps its pinned r21 toolchain. Its authored same-library diagnostic bridge and
serializer hook must keep the monitor armed through engine and callback-manager
Term; explicit return witnesses gate disarm, and bounded capture counters do
not acquire another engine owner. J794 qualifies only the static ELF's export,
import and dependency closure. J802 corrects the output-ID width and loads the
replacement, then refuses its pre-Init callback-observation assumption before
engine Init. Registration and delivered callback coverage are separate facts;
monitor continuity and capture callbacks remain runtime gates. The library is
outside the game. The private NativeMonitorLease owns diagnostic registration,
return witnesses and disarm state; its injected API is a host contract seam,
not native callback evidence. First failure and uncertain outcomes remain
visible through owner teardown.

The next private monitor protocol uses schema 3 with 24 snapshot slots. A
conservative latch precedes the actual engine Init attempt; pre-Init registration
does not imply callback coverage. An exact native control marker gates bank and
event work after Init. Both actual Term returns gate disarm; post-Term message
delivery is explicitly unsupported. J810 records the loaded candidate's missing
marker and completed cleanup. J816's serviced wait moves Init-bank loading and
the initialization delegate after the marker. It records successful callback
and RenderAudio service, but still times out before bank/event work. Neither
startup change is an established SDK requirement. The next bounded diagnostic
exposes the first any-level managed message while retaining the exact native
marker gate; generic message delivery cannot qualify that gate. The isolated
stage/build adapter pins the editor instance, current managed sources, historical
provenance and importer metadata separately; partial reload responses and terminal
build requests remain preserved. These private support producers are listed in
LOCAL_STATE and do not enable audio in the game.

J821's first-message player builds with the helper imported and its complete
source/metadata closure frozen. Its Main attempt produces no bootstrap report,
so neither monitor delivery nor runtime storage backing is established there.
Startup observation precedes any further engine change; owned package removal
is separate from unobserved native owner teardown.

The private composed-audio candidate has separate `GameAudioProcessHost` and
`GameWwiseRuntime` owners for opt-in startup, bounded native service and owned
teardown, with an identity-bound `GameAudioPostEventGate` around the recovered
offline pickup callback. J820 qualifies its full frozen host closure scan and
three disabled-profile assembly identities. It is not a current game owner:
current-player source/APK binding and native runtime acceptance remain closed.
Exact Timeline/diagnostic-event and Collections indirect-call classifications
belong to its transform, without changing the pinned package implementations.

`tools/wwise-android-abi/generate.py` is a current, explicitly invoked host
support tool with policy in `recipe/wwise-android-abi.json`. It reads the
exact policy-bound accepted managed API, authorized local Wwise Android
declarations, the pinned Android OS-string helper source and ARM64 Release
plugin, and uses Unity-bundled Cecil. The writer applies the reviewed P/Invoke
metadata and one exact-signature OS-string call-operand rewrite, refusing
body/signature/operand drift and verifying every other method and assembly
contract after reopen. It publishes only new plans and candidates under ignored
`work/`, refusing overwrite and symlink paths. It remains separate from the default
assembly-transform and game-build paths. Its incomplete Android ABI candidate
has 11 unavailable imports and does not enable production audio. The authored
tool and policy are audited in `recipe/README.md`; synthetic host contracts
are in `tools/wwise-android-abi/test_synthetic.py`.

`scripts/lab/wwise_init_platform.py` is a current, explicitly invoked support
tool for those isolated diagnostics, with its metadata contract in
`recipe/wwise-init-android.json`. It requires the configured legitimate source,
a full inventory matching the accepted input and an explicit source hash. It
hashes and transforms one byte snapshot, removes only the checked unsupported
Controller Speaker metadata and retargets the two checked root buses to the
existing System device. It creates a new bank and receipt exclusively under
ignored `work/`; original inputs and the default game payload are untouched.
There is no persistent engine state or `./dev` action. Synthetic structural,
input-binding and path/refusal contracts are in
`tests/test_wwise_init_platform.py`. Native acceptance remains scoped to
J740/J742; this generator does not establish full-bank or controller fidelity.

The updated-input transform also guards native `SkillResponseBehavior.OnDestroy`
when its skill array was never initialized by `Start` (J638). An absent array
returns without event work; an existing array executes the original cleanup IL.
The generator preserves assembly/MVID/type/field/method identity and audits all
other bodies. `SkillResponseCleanupExactEditorFixture` invokes the native base
lifecycle on isolated inactive fixture objects and verifies subscription removal
without claiming automatic Unity lifecycle or culprit-template attribution.
`assembly_transforms.generate` produces these plugin bytes from supplied originals;
working-project staging must hold the host editor lock and batch asset editing,
verify the prior plugin/generation hashes, and update the local generation marker.

Incremental project rebuild (`scripts/lab/rebuild.py`, current, R0–R9):
`assembly_payload` owns the shared recipe-only DLL/importer generation. R1's
`assemblies` wrapper retains provenance membership/hash/size comparison before
project writes. The separate current `owner_assemblies.py` action uses that
producer with public output contracts and an exclusive new workspace: typed
input/source checks, preserved `attempt/`, a `project/` prefix, manifest and
`preparing`/`complete`/`failed` receipt. It reads no project oracle and writes no
lab generation/current-build marker. Setup, teardown and incomplete-project
limits are in [OWNER_ASSEMBLIES.md](OWNER_ASSEMBLIES.md).
The optional `public-dotnet8` profile delegates only the shared transform
producer to `public_transform_tools.py`. That stdlib owner validates the three
pinned public archives in `recipe/owner-public-tools.json`, extracts declared
members/notices, compiles public Cecil source and unchanged authored tool source,
checks actual runtime/provider witnesses and all three output hashes, and keeps
its own `public-tools-receipt.json` lifecycle under the exclusive attempt. Native
hosts and archive cache are explicit owner inputs. No network, upstream project
scripts, package restore, editor or device action occurs. The component CLI
exposes the same generator on an isolated Python host; it does not qualify a
complete input inventory or player. Default SDK/R1 production stays unchanged.
`unity_rebuild.py` owns R9 `unity-build` after `validate-bindings`: destination-only
host preflight, an exclusive operation lock, exact-editor batch invocation through
`whole_catalog.build_integration(destination=...)` → `build.build(destination=...)`
→ `LabBuild.BuildDestination` → the existing full `LabBuild.Build`. It runs two editor
sessions: `LabBuild.RepairDestinationPlugins` force-reimports the managed DLLs and exits,
so their recompilation settles; `BuildDestination` then reimports their asset dependents
in one batch per dependency layer (J585), runs the read-only script gate on the recovered
HUD/Menu components and TimerText targets, and enters the unchanged real build (J578–J581). Reimport errors that
pass 1's fresh import did not log are recorded and make R9 unequal after the build.
Per-asset missing-script counts and MonoScript identities live in the run's
`lab-build/script-audit.json` and successful destination receipt. `script_audit.py`
owns selection generation, working-editor MCP payload generation and comparison;
it never invokes an editor or stages working-project files. Scenes are audited from
their text, not opened; the destination error listener detaches before the real build
and on failure. Operator commands: [script gate](rebuild-plan.md#destination-script-import-gate).
The default project Library is destination-local. Per-attempt requests/logs/APKs/payload and
Android/Gradle homes stay under `.rebuild/unity/`; the summary and hash comparisons
are `.rebuild/unity-build.json`. Cleanup releases the R9 lock, preserving failed
runs; Unity locks are never removed. Both destination and working-project editors
must stay closed. The existing local debug signing key is copied read-only into
the destination to preserve in-place install compatibility. Real build cache keys,
paths, payload reuse and receipts keep their default behavior. `preflight --dest`
uses the same read-only host/input/binding gates without live preflight receipts.
`install --apk` and `sync-data --payload-dir` keep the existing `Device` safety
checks; explicit device-action `--work-dir` selects the existing device receipt
and config tree. Rebuild `--work-dir` is read-only. Comparison groups and exact
operator/restore commands: [R9](rebuild-plan.md#r9-isolated-unity-importbuild-current-not-yet-equivalent).
Host contracts: `tests/test_unity_rebuild.py`. The first R9 APK passed both device checks
but is not yet equivalent to the working project's (J582; causes in J583).

`build_entry_rebuild.py` owns host-only R7 `build-entries` and R8
`runtime-sources`, after `scene_rebuild.py` supplies R5/R6. It uses destination
`StageIO` buffers, explicit retained-input hash gates and completion markers. R7
regenerates its three decompiled map sources with the pinned decompiler
(`recovery.ilspy_project`) and reads the bootstrap attempt from the public recipe;
only the runtime-contract result remains a retained input (J597);
`finish` verifies selected output hashes/sizes before flushing. It shares
`whole_catalog.generate_build_maps`, `stage_build_sources` and
`generate_build_bootstrap` with the real build. `build.stage_android_assets`
retains the real copytree and provides buffered destination placement. No Unity
import or build runs here. `validate-bindings` is the final read-only host gate;
its receipts, membership rules, remaining pins and uncovered provenance are in
[rebuild-plan.md](rebuild-plan.md#r7r8-host-build-entries-and-sources).

`importer_rebuild.py` owns current host step `importer-identities`, after
`runtime-sources` and before `validate-bindings`/R9. It renders recorded public
GUIDs and shared importer schemas from `recipe/importer-identities.json`, including
the two music runtime sources (J890), checks
all selected hashes/sizes before placement and records
`.rebuild/importer-identities-result.json` plus its completion marker. Folder
importers are left to Unity at R9 (J575); R9 classifies them and rescans the
minted folder GUIDs for references. These receipts have
no process lifetime or cleanup requirement; reruns replace them only after the
cohort gates pass. `validate-bindings` requires the completion marker; R9 removes
this step's membership from its remaining `unity-generated` comparison. No local
provenance map is edited. Host contracts: `tests/test_importer_rebuild.py`;
[scope and operator usage](rebuild-plan.md#pre-import-importer-identities-current).

Host prerequisites (`shader_rebuild.py` and `project_input_rebuild.py`, current):
R1 → `shader-pipeline` → R2 → `project-inputs` → R3–R8 → `importer-identities` → final bindings.
Shader replay initializes R1's generation marker, validates the public retained-input
recipe, runs existing generators into destination scratch, then places only
map-matching outputs through `StageIO`. Its per-file blocked/result receipt owns
completion state; composition requires it and rechecks generated source hashes.
No shared pointers or Wine bottles are written. Native recovery remains a pinned
local-input blocker. `shader_source.output_directory` shares unchanged real action
paths and isolated pointer-free setup across all three generators.
`inherited_rebuild.py` owns per-file R2 host candidates: minimal importers from
ledger identities, one hash-gated accepted-export texture importer and three
includes through the existing pinned Unity package reader. Destination-only setup
passes candidates to `inherited_state.prepare`; it retains original hash/GUID
checks and store fallback for unregenerated files. Per-file origins and reasons
live in `.rebuild/inherited-rebuild-result.json`; transient buffers disappear
on flush/failure. The real stage's store placement paths remain unchanged.

Project inputs own public smoke settings, Burst default JSON, J369 Android graphics
tiers, archived independently authored editor
versions, explicit Nova importer metadata, shared Nova-axis generation and the
original-identity OBJ export. All outputs are buffered and gated before flush;
the completion receipt lives under destination `.rebuild/`. No new runtime state
or teardown is introduced. Setup is the accepted installation and public recipes;
failed native scratch is retained and later operator reruns use a new attempt
folder. No local input is retired. Exact membership, explicit R9 PlayerSettings/linker
obligations, provenance corrections and pin counts are maintained once in
[rebuild-plan.md](rebuild-plan.md#shader-prerequisite-and-remaining-project-inputs).
Host contracts: `test_shader_rebuild.py`, `test_project_input_rebuild.py`.

`./dev prototype --action rebuild-step --step assemblies` reconstructs the assembly
cohort, then compares every selected map path with the current project's actual
bytes. The ordered `STEPS` table declares each step's producer categories, path
selection and builder; categories alone are too broad to select a subsystem.
The local `receipts/provenance-map.json` supplies comparison membership and output
hashes. `--work-dir PATH` selects read-only local inputs (including the legitimate
installation configuration); the destination remains in **this clone's**
`work/rebuild/<input_id>/lab-project`. `--dest DIR` may select another isolated
project strictly beneath that rebuild root. Live-project destinations, redirects,
nested symlinks and hard-linked output files are refused. No Unity or device
operation is involved.

After composition, `--step catalog-closure` uses `whole_catalog.prepare_integration`
through `StageIO` and `catalog_rebuild.CatalogIO`; `--step dependencies` uses
`composition_migration.stage_missing_sources`, the support alias repair and the
optional-content sanitizer through that same boundary. R3 selects 259 map files;
R4 selects 1,238. Membership uses the map's exact producer function evidence,
since the broad `repo-builder` category also includes later steps. Each cohort is
hash/size-gated before buffered project writes are flushed, then compared with
the current project. R3 requires R2's destination config; R4 requires R3's completion marker and R2's
destination build config. The real actions retain their original write paths.

`catalog_analysis.ensure` (J725) regenerates the catalog analysis once per destination
under `.rebuild/catalog-inputs/`, running the live pipeline's own `audit_into`,
`native_inventory_into` and `reconcile_into` (the source catalog through `catalog_reader.py`
and `AssemblyProbe --catalog-names`, J714). Only `recipe/catalog-typed-corrections.json`, three
measured identities, is not regenerated. No previous analysis or live pointer is read. Destination GUID ownership, catalog manifests/import receipts,
dependency receipts and optional-content receipts are regenerated. No current
project owner map or historical output body is used as source. R3 buffers the
closure import and UI remaps; R4 buffers dependency import, support repair and
sanitization. Auxiliary R4 writes remain under `.rebuild/composition/`, and reads
prefer R2's redirected config. Before R7 places its importer, sanitization obtains
SilentProjectileBoundary's identity directly from `project-layout.json`. These buffers have no state after flush or failure.
Synthetic contracts: `tests/test_catalog_rebuild.py`.

R5/R6 replay (`scripts/lab/scene_rebuild.py`, current): `--step stage-variants`
uses `stage_variants.stage`, the existing Nova geometry projection and
`scene_contract`; `--step source-scenes` uses `source_scene_candidate.prepare`
for all 23 scenes. R5 owns 18 map files (16 later reduced scenes and two final
contracts); R6 owns 46 bodies/importers. Completion markers enforce order after
R4, and both steps validate selected hashes/sizes before flushing `StageIO`,
then compare actual bytes. The real actions keep their original paths. R6
omits the separate audio action because R1 owns its DLL outputs.
R5 reads no retained analysis input (J597): `script_identity.py` derives the MapZone
script lookup from the installation's shipped MonoScripts with Unity's MD4 file-ID
rule, and `scene_rebuild.node_graphs` finds the stage graphs as the export's
`RoR2.Navigation.NodeGraph` assets, each of which must still be its export copy
before R9. Destination scene bytes
determine pending variants even when R2 already supplies their config rows.
R5 reuses R2/R3's imported closure, validates graph hashes/GUIDs, reads R3's
regenerated manifest, and regenerates navigation/config/context receipts.
Temporary projections remain buffered and are discarded after placement;
auxiliary outputs stay under `.rebuild/`. R6 derives source-scene GUIDs/importers
from input identity and source metadata. Buffers have no state after success or
failure. R4 still defers later scene paths until the final binding gate, which
remains disabled through R8. Host contracts: `tests/test_scene_rebuild.py`.

`recipe/original-assemblies.json` pins 49 Managed source identities and importer
parameters: 45 unchanged originals, installation-sourced SimpleJSON and three
originals transformed using J563. `recipe/templates/original-assembly.meta`
supplies the common importer schema; GUIDs, creation times and execution orders
reproduce the retained metadata without copying it from the project or export.
J563's shared `assembly_transforms.generate` builds an isolated tool copy and
replays the pinned transforms, with tool intermediates, CLI home, package cache
and temporary files beneath the destination. Scratch is removed on success or
failure. The full 98-file cohort is validated before project files are placed;
reruns overwrite only that cohort. R2 initializes a separate generation marker from these recipes after validating
R1 assembly placement.

Composition rebuild (`scripts/lab/composition_io.py`, current, R2):
`rebuild-step --step composition` runs `composition_migration.stage` through
`StageIO` against the isolated destination. Its selection comes from
`composition_rebuild.recipe_inputs` (J597): asset transforms, the addition ledger,
the public runtime/content recipes and `recipe/composition.json`, with source GUIDs
and catalog closure from the catalog analysis regenerated in the destination (J725). The rebuild reads no
migration evidence (B1, B3–B6, B8), previous project, live content selection or old
run attempt; the real action still takes them through `migration_inputs`. The same owner keeps real-stage writes
at their original paths when no destination is supplied. Export membership comes
from canonical catalog closure/resolved-mesh relocation plus the identifier-only residual
`recipe/composition-export-copies.json`; provenance gates each selected source's
size/hash before placement. The package manifest is rendered from the public
project-layout dependencies. Assembly identity comes from R1's public recipes,
never the working project's marker. Host/input preflight gates remain active;
device storage and preflight receipts belong to subsequent install/build work.

Stage transforms, additions, selected shader outputs, scene contracts, script
orders, runtime config and receipts use the same staging functions. Pending stage
bytes are visible to later stage reads and checked against provenance before
publication. Intermediate project products stay in the destination for subsequent
builders; auxiliary config/receipt outputs go under `.rebuild/composition/`, with
logical paths relative to the selected input work root. The comparison excludes
only that coordinator namespace and `.port-input.json` outside its three mapped
areas. Pending state is discarded on failure; copied exports and the generation
marker remain available for inspection. There is no Unity/device operation.

The dependency builder `stage_missing_sources` runs after complete catalog import
in the rebuild order; it is unchanged and still called inline by the real stage
action. Only the rebuild path defers J565's removed/unowned binding guard, retaining
the diagnostic and original unresolved identifiers for later builders. The final
`validate-bindings` step is registered last and refuses execution until R3–R8 are
implemented. No successful R2 comparison establishes that final gate. Host
contracts: `tests/test_composition_rebuild.py`, including the real-stage write path.

`--compare-only` requires an existing destination and performs no writes or tool
execution. Reports list identical, different, missing (which side), and extra
paths, with counts and a nonzero exit on differences. Files owned by other map
steps may coexist; files absent from the map are extra. Host contracts:
`tests/test_rebuild.py`; this is reconstruction tooling, not device acceptance.

Inherited-state store and ledger (`scripts/lab/inherited_state.py`, current):
`./dev prototype --action inherited-store-capture` validates and copies exactly the
189 inherited asset/meta pairs from the selected previous project into
`work/inherited-store/<input_id>/`, publishing only a complete hash/GUID-verified
store. An existing store must match exactly; capture never repairs drift.
`composition_migration.plan_additions` verifies that store and combines its pairs
with the 40 recipe-generated additions before any project writes, preserving
inherited YAML normalization. No addition is copied from the previous project by
current stage. `inherited-state-check` verifies the store and regenerates the
shader/export/package cohorts against ledger hashes in scratch, without historical
copies; `--work-dir PATH` selects read-only inputs. Store lifecycle and remaining
coordinator blockers are in [LOCAL_STATE.md](LOCAL_STATE.md#named-inherited-store-current).
Host contracts: `tests/test_inherited_state.py`. The full migration coordinator
still reads historical config/identity/provenance contracts listed there; addition
planner independence does not establish full direct composition.

Non-shader addition owners (`scripts/lab/export_additions.py` and
`scripts/lab/unity_package_additions.py`, current): composition prepares the full
asset/importer pairs before any staging writes, checking complete membership,
target identity and both ledger hashes. WarpRamp uses the accepted export's
hash-gated identity operation; its importer retains the export bytes except the
explicit inherited GUID and creation-time field. The used TMP properties include
comes from the hash-pinned TextMesh Pro 3.0.6 package bundled with the exact editor,
read in memory with no package installation or assembly-provider change. Its
importer uses `authored_additions.shader_importer` with the inherited GUID.
These owners have no runtime state or teardown; they return bytes and retain no
temporary output. Missing or drifting inputs fail before staging. Required local
inputs are the existing accepted export and documented Unity toolchain; neither
owner reads a timestamped run folder. Other non-shader additions remain inherited;
their individual blockers and third-party source requirements are audited in
`recipe/README.md`. Host contracts: `tests/test_nonshader_additions.py`.

Generator-owned shader additions (`scripts/lab/shader_additions.py`, current):
composition prepares all nine pairs before writing, using the existing deferred
and material generators with selected resources and temporary output directories.
The shared authored importer schema supplies each ledger GUID. Generator inputs,
selected pipeline receipts and final body/importer hashes are gated; staging does
not read the previous project for these pairs or overwrite them with selected
source copies. Temporary output is deleted on success or failure. DeferredLighting
reuses hash-verified, validated independent HLSL intermediates from the selected
pipeline receipt; it never invokes Wine in this isolated mode. The native DXBC,
HLSL and bound layout must agree with that receipt. The selected deferred pipeline's
`program-*-independent/program-*.hlsl` files remain required local inputs produced
by `shader_programs.NativePrograms.bound`; the composition selection locates them,
with no timestamped directory encoded in source. Other selected programs run
the pinned native decompiler and roundtrip check in scratch. No rendering or
input-bootstrap reproducibility follows from this host byte comparison.
Host contracts: `tests/test_shader_additions.py`,
`tests/test_shader_independent_reuse.py`.

Project equivalence harness (`scripts/lab/project_manifest.py`, current):
`./dev prototype --action project-manifest-capture` writes an ignored receipt of every file
under the generated project's `Assets/`, `Packages/` and `ProjectSettings/` (path, SHA-256,
size) plus the build cache's external inputs; `--action project-manifest-compare --compare A B`
reports added, removed and changed paths and exits non-zero on any difference. It never
writes to the project. Each step of the [migration removal plan](migration-removal-plan.md)
must compare equal against the previous receipt.

Pointer chain for the latest evidence: `experiments/whole-catalog/latest.json` →
`integration-latest.json` → build, device and composed receipts.
`checkpoints/LAST_OBSERVED_WHOLE_CATALOG.json` pins the accepted scope.

Asset transformations (`scripts/lab/asset_transforms.py`, current):
`recipe/asset-transforms.json` selects 222 accepted-export assets with source hashes:
28 SurfaceDefs, six identity copies, ten activation-only prefabs and all 178
structural prefabs/scenes. The generator returns bytes and export-derived metadata
without writes; `integrated_objective` shares the SurfaceDef field operation logic.

Identity copies preserve source bytes. General `set_field` operations select a
GameObject hierarchy path, native class or external script identity, zero-based
component occurrence and mapping field path. Duplicate hierarchy paths require an
explicit zero-based `hierarchy_occurrence` in source record order; otherwise they
fail. Consecutive non-identity field edits share a per-generation selector index;
renames, hierarchy/identity changes and structural operations flush it.
Four UI prefabs first apply the existing input-gated, hash-pinned uGUI mapping.

`remove_components` takes source fileIDs and an exact match count, preserving
surviving IDs and record order. Each deleted component must have one correct owner
membership. Explicit `retain_null_slots` identifiers replace selected memberships
with null slots instead of deleting them. `null_reference` and
`null_array_element` require an owner selector, a mapping/sequence field path,
exactly one match and the expected nonzero local reference. Array indices are
zero-based and retain entries; external references fail the nulling precondition.
`remove_scene_settings` separately deletes explicit ownerless class 29/104/157/196
records, with fileID/class/count checks. All deletion operations reject surviving
local references; hierarchy deletion remains unsupported.

`add_component` constructs the authored empty MeshRenderer and
SilentProjectileBoundary schemas from typed fields. It selects a surviving owner
by source fileID and allocates the sanitizer's SHA-256-derived IDs (renderer base
7,000,000,000,000,000; silent base 8,000,000,000,000,000), incrementing collisions.
The recipe's relative `id_seed_path` is an allocation namespace, never a path read
from disk. Explicit first/last membership placement preserves the migration's
ordering; records append in recipe order. Bodies are generated, never copied YAML.

`composition_migration.stage` prepares every recipe pair before project writes,
checks the existing provenance/output/conflict gates and metadata equality, then
writes those pairs instead of copying preview assets. `prepare_asset_transforms`
validates these rows using export bytes and the plan's hashes without opening
preview/previous asset files. The surrounding migration still reads historical
plans, mappings, configs and 200 additions; 15 use tracked sources and 14 use
export-based deck constructors.
There is no persistent generator state or teardown. The current read-only action
`./dev prototype --action asset-transforms-check` compares every recipe asset/meta
pair with the migration preview oracle (or project when no preview exists), checks
project metadata, lists differences and exits nonzero on drift. Exclusive
structural cohorts report equality separately; the removal cohort also counts
deleted components. Later project transformations are reported separately without
rewriting either side. Host contracts are in `tests/test_asset_transforms.py` and
`tests/test_asset_structural_operations.py`; device acceptance is a separate gate.

The same owner constructs the 14 director-deck additions selected by
`recipe/deck-transforms.json`. `generate_deck` selects category/card spans from
seven hash-pinned export decks, preserves retained fields and order, prefixes the
name, and omits default elite fields from the older serialization schema. Explicit
field/weight omissions preserve the inherited sparse Sky Meadow champion card;
they do not repair its gameplay. `generate_deck_asset` supplies a minimal native
importer with the stable lab GUID. `prepare_decks` requires complete composition
membership and matching identities before any writes; staging retains target
relocation and uses the existing addition writer. No persistent state or teardown
is needed. The current `asset-transforms-check` also reports `deck_cohort` against
the normalized previous-project addition oracle, compares metadata, fails on pair
drift and lists current-project changes separately. Host contracts live in
`tests/test_deck_transforms.py`; the recipe audit explains selections and prior art.

Authored additions (`scripts/lab/authored_additions.py`, current) owns
`recipe/authored-additions.json`: 14 tracked shader sources and one include, their
source hashes and stable lab GUIDs. Its pure generator returns source/importer
bytes; `composition_migration.stage` prepares the entire cohort before project
writes and retains ownership of writing/target relocation. There is no persistent
generator state or teardown. Missing membership, GUID mismatch and source drift
fail closed. Other additions still inherit the previous project. The current
`./dev prototype --action authored-additions-check` is a read-only comparison of
asset and metadata bytes against the migration copy rule. It does not compare
later shader replacements or run Unity. Host contracts are in
`tests/test_authored_additions.py`; provenance is in `recipe/README.md`.

## Android runtime

The shipped game runs inside the lab harness `PortSession`
(`tools/unity/runtime/session/PortSession.cs`, 70 `partial` files). The runtime configuration is the
untracked `Resources/MovementBatchProbe.json` (unchanged resource/file name) in the
generated project, parsed as the
184-field `SessionConfig`. `SessionReport` is the report written back as `movement-batch-*.json`
(and the `movement-batch-selection.json` override); config values the report shows are
copied into it explicitly (J517).

Start-up, in order:

1. `Init` (`PortSession.cs:402`, `RuntimeInitializeOnLoad` after scene load): if the
   `MovementBatchProbe` resource exists, create the harness object.
2. `Start` (`:407`): exits if `whole-catalog-selection.json` exists in persistent data (the
   separate catalog bootstrap owns that run), then **waits 8 s**.
3. Read the config. Without a `movement-batch-selection.json` override and with
   `launchPlayableSlice` set, wait for an attempt-bound `nova-input-mapping.json` in
   persistent data, then select case `body-state-spawn-state-auto-nova-spine`. Payload sync
   (`device.py`) does not push that mapping; only the historical `movement-batch-run`
   (`scene_runtime.py:629–631`) and some untracked runners do. The menu reads it too
   (`OfflineApplicationBoundary.cs:45`).
4. Begin presentation (`AndroidMaterialPresentation.Begin`), collect garbage left by a
   previous session, `Save()` phase `started`.
5. Catalog fixture: `RegisterBodyCatalog` (composed whole catalog), then
   `PrepareTeleportMaterial` and `PrepareBarrierEffect` when configured.
6. `AwaitOfflineRunStart` (`OfflineApplicationBoundary.cs:34`): offline settings, the
   recovered survivor/difficulty/loadout menu, and the wait for Start.
7. `RunSelectedProbe`: when `IsPlayableSpine()` (`PrimaryFireBoundary.cs:12`, a prefix
   match on `body-state-spawn-state-auto-nova-spine`) it runs `GameSession()`, which runs
   `BodyLifecycle()`; the same flag turns on the game path inside the boundaries it calls.
   Any other id goes to `LabExperiment()` (`LabExperiments.cs`), the 116-label switch of
   historical experiments. Both run inside the same `try`/`finally` (J513).

Teardown, in order, after `RunSelectedProbe` returns or throws:

1. `RunSelectedProbe`'s `finally`: `CleanupLanding`, destroy the obstacle, body host and
   staging roots, disconnect the recovered client and shut down the owned network server.
2. In `Start`: `VerifyEnemyCleanup` → `VerifyIntegratedWorldCleanup` (integrated world) →
   `VerifyAutomaticModelDestruction` → `CleanupEnemyRewards` → `CleanupPlayerDeathEffect`
   → `CleanupBodyCatalog` → `CleanupTeleportMaterial` → `CleanupBarrierEffect` →
   `CleanupSpawnConfig` → `CleanupStageGeometry` → `AndroidMaterialPresentation.Finish` →
   `ReclaimCompletedSessionResources` (only after a clean, successful integrated session) →
   `Save()` phase `complete` → `RestartWorldAfterCleanup`.

The enemy, world, model, teleport-material and barrier steps run through `RunGuarded`
(`PortSession.cs`), which records the failure and moves on. The reward,
death-effect, geometry and reclaim steps, and the synchronous cleanup calls outside the
`CleanupBodyCatalog` `try`, have no wrapper: an exception there stops the remaining
release steps. `Start` itself has no
enclosing `finally`, and `PortSession` has no `OnDestroy` or `OnApplicationQuit`:
an error during catalog preparation or the menu, or the app being killed, skips the
post-run release sequence. Per-boundary teardown inside the session (the 17-step call
order and each `finally`) is in
[architecture-file-map.md](architecture-file-map.md#d-playable-spine-runtime-sequence-and-ownership).

## Ownership

Each staged runtime file starts with a two-line header naming its subsystem, whether it is
on the game path, and its setup and teardown methods (J516).

Most `*Boundary.cs` files are `partial class PortSession`: their state is fields on
the coordinator, not a separate owner. Only the types marked **own type** keep their own
state. Host tests are in `tests/`; editor fixtures (`tools/catalog/*Host.cs`) run in the
exact editor. There is no per-subsystem device check yet: catalog registration is checked
by `whole-catalog-run`, and everything else by a gameplay runner's `movement-batch-*.json`
report, read against the journal entry that defines what it must show.

| Subsystem | Main files (`tools/unity/`) | State | Setup → teardown | Host test / editor fixture |
| --- | --- | --- | --- | --- |
| Touch game input | `runtime/input/AndroidTouchInput.cs`, `NovaInputBridge`, `NovaThirdPersonView` | Bridge-owned pointer captures, held/pending action states, viewport geometry and primitive report; no game objects or native gameplay ownership | Playable body input setup → `Poll`/fixed-tick consumption and world GUI → `Neutral`/pause/focus/disable release; require lift before reacquiring | `test_android_touch_input.py` runs production pointer/camera code against exact managed Unity API; Android consumer case is separate |
| Original equipment highlights | `runtime/catalog/OriginalEquipmentHighlightAssetsBoundary.cs`, existing `PortSession.OriginalStats` and `BodyCatalogBoundary` | nested `OriginalEquipmentHighlightAssetsSession` owns three typed source-location handles, exact static assignments, cancellation state and a primitive session report; prepopulated or competing slots refuse | After `SetEquipmentDefs`, prepare before body activation; retain through world/stage lifetime. At `CleanupBodyCatalog`, require body/model/world-player destruction, restore only owned assignments, refuse remaining foreign slots, release handles and clear retained locator/operation references before bundle unload. Cleanup failures remain visible and retain catalog ownership. | `test_equipment_highlight_assets_owner.py`, authored `EquipmentHighlightOwnerProgram.cs` and stubs; Android materialization and original highlighting remain device gates |
| Session and entry | `PortSession`, `OfflineApplicationBoundary`, `SessionResourceBoundary`, `ActiveClientBoundary`, `OfflineRunSeedBoundary`, `SurvivorSelectionBoundary` | nested `OfflineRunSeedSession` (`IDisposable`) **own type** holds the cached seed, session id and source; nested `ActiveClientSession` (`IDisposable`) **own type** holds the owned body/master authority identities and client-scene ownership flag; `activeBodyClient`, `activeBodyOwner`, remaining state and `SessionReport r` (including `r.activeClient` and `r.rewards.seedSource`) stay on the coordinator; nested `OfflineApplicationSession` (`IDisposable`) owns application/menu state and the captured screen timeout | `Start` (acquire the playable awake policy before catalog preparation; `OnDestroy` releases it) → `AwaitOfflineRunStart` → `RunSelectedProbe`; `ConnectActiveBodyClient` → `CleanupActiveBodyClient` (calls `Dispose`: remove master then body authority, disconnect then shut down client) → coordinator server shutdown → `FinishActiveClientSceneCleanup`; active-client owner created on first use and retained after cleanup; `CollectPriorSessionGarbage` → `ReclaimCompletedSessionResources`; `SelectOwnedRunSeed` calls session `SelectOwnedRunSeed` (owner created on first use and retained; session id controls refresh; `Dispose` is a no-op with no teardown call) | `AndroidLifecycleHost.cs` |
| Catalog and resources | `BodyCatalogBoundary`, `WholeCatalogComposed`, `WholeCatalogLoader`, `SpawnStateBoundary`, `OriginalBodyVisualBoundary`, `OriginalGlobalCommonAssetsBoundary`, `TeleportMaterialBoundary`, `BarrierEffectBoundary` | `WholeCatalogComposed` **own type** (static); nested `TeleportMaterialSession` and `BarrierEffectSession` (`IDisposable`) **own types** hold the teleport material (locator, async handle, material, overlays) and the barrier effect (constants, locator, async handle, prefab, effect-slot snapshots, owned material copies); nested `OriginalBodyVisualSession` and `OriginalGlobalCommonAssetsSession` (`IDisposable`) **own types** each hold their native slot snapshots and async handle lists; nested `SpawnStateSession` (`IDisposable`) **own type** holds native state/preload snapshots and spawn delay/sound restoration; `ownsStateCatalog` stays shared on the coordinator; teleport, `r.barrier*` and `r.world` report fields remain coordinator observations; the rest coordinator fields; nested `BodyCatalogSession` (`IDisposable`) **own types** hold their files' private state | `RegisterBodyCatalog` (calls `WholeCatalogComposed.Prepare`) → `CleanupBodyCatalog` (calls `Release`); `PrepareBarrierEffect` → `ObserveBarrierEffect` / `ProbeBarrierEffectLifecycle` → `CleanupBarrierEffect` (awaited coroutine, preserving Start's setup and release order; `Dispose` is a no-op because release requires the coroutine's frame yields); `PrepareOriginalBodyVisualReferences` → `PrepareOriginalGlobalCommonAssets` → `CleanupOriginalGlobalCommonAssets` → `CleanupOriginalBodyVisualReferences` (each cleanup calls its owner's `Dispose`: restore slots, clear snapshots, release handles, clear handles, mark the coordinator report); `PrepareSpawnStateCatalog` forwards to `SpawnStateSession` without changing catalog/config/preload construction order; later `CleanupSpawnConfig` calls `Dispose` (objective, enemy and spine config cleanup, then spawn delay/sound restoration, then `RestoreWholeStateOwnership`); owners created on first use and retained after cleanup | `test_whole_catalog.py`, `test_composed_support.py`, `test_body_visual_map.py`, `test_common_assets_map.py`, `test_stage_variant_graph_roots.py`; `WholeCatalogHost.cs` |
| Manual Moon boundary (existing config) | `NovaInputBoundary`, `NovaInputBridge`, `IntegratedStageBoundary` | `ManualMoonBoundary` is a pure four-completed-transition gate shared by the automatic input loop and transport entry guard; `NovaInputBridge` applies its diagnostic-only hold at every fixed tick, preserving touch-equipment requests and the physical-controller route when diagnostic input is off. It refuses any subsequent or explicit `moon2` transport while `pauseBeforeMoon` is enabled. The ordinary path and default `false` remain unchanged; the report records stage/count and a fixed-tick witness only after the sink actually runs. | Input-loop gate before transport/producers; transport guard before destination resolution or stage mutation | `SurvivorSkillInputHost.cs` (exact-editor bridge sink contract; no Moon/runtime acceptance) |
| Input and camera | `NovaInputBoundary`, `NovaInputBridge`, `NovaThirdPersonView`, `AndroidPresentationCamera`, `NovaDiagnosticDisplay`, `AndroidNativeSourceCameraRigOwner` | nested `NovaInputSession` (`IDisposable`) **own type** holds trace cursors and the input iterators with local mapping, landing, camera and loop state; `NovaThirdPersonView` keeps its own camera/orbit state; `worldView` and `worldEquipmentBridge` stay shared on the coordinator; `NovaInputBridge`, `AndroidPresentationCamera`, `NovaDiagnosticDisplay` and opt-in `AndroidNativeSourceSkinLifecycle` (with pure `AndroidNativeSkinActivationPolicy`) remain **own types**; the native-skin owner is attached to the selected source model, retains only its native skin subscription and Android material clones through body lifetime, and writes scalar evidence into `NovaReport`; the per-run `SessionReport` selector defaults false; reports remain coordinator observations | `NovaRawBoundary` / `NovaInputBoundary` forward to the session; input teardown stays in its iterator `finally` in the same order; `NovaInputBridge.OnDisable` neutralises input; owner created on first use and retained after its no-op `Dispose` so final `Save` can flush traces | `test_nova_input_presence.py`, `test_nova_bridge_evidence.py`, `test_input_migration.py` |
| Settings | `AndroidOfflineSettings`, `OfflineSettingsBoundary`, `AndroidFeedbackDraft`, `AndroidFeedbackScreen` | `AndroidOfflineSettings` **own type**, kept across sessions; nested `OfflineSettingsSession` (`IDisposable`) **own type** holds the saved pause time scale and feedback screen; feedback draft owns only in-memory text, preview and consent; settings owns the two-step end-run confirmation and clears it on cancel/exit/cleanup; the recovered-menu owner disables its native Canvas while settings is visible; store reference, visibility and pause flags stay on the coordinator for menu/Nova input | `PrepareOfflineSettings` (calls `OfflineSettingsSession.Prepare`) → explicit settings feedback Open/Draw/Close → `CleanupOfflineSettingsPause` (calls `Dispose`, clears feedback and releases an owned pause only) | `test_android_feedback.py` executes the production model, screen and settings/input callers with controlled host peers; device acceptance is separate |
| Progression and profile | `AndroidProgressionBoundary`, `AndroidOfflineProfile`, `AndroidProfileBoundary`, `OfflineLoadoutBoundary` | `AndroidProgressionBoundary` (`IDisposable`), `AndroidOfflineProfile` and nested `AndroidProfileSession` (`IDisposable`) **own types**; session owns loadout preview, catalog snapshots, redirect lease and event/discovery listeners; progression reference, results/save-system state, world references and pending menu loadout stay shared on the coordinator | `ApplyAndroidProfileLoadoutBeforeSpawn` (calls `AndroidProfileSession.ApplyLoadoutBeforeSpawn`) → `PrepareAndroidProfile` (calls session `Prepare`, then `AndroidProgressionBoundary.Prepare`) → `CleanupAndroidProfile` (calls session `Dispose`, including progression `Dispose`); results installs the save system before profile setup and restores it after profile cleanup | `AndroidProgressionHost.cs`, `AndroidDiscoveryHost.cs`, `AndroidProfileHost.cs` |
| Results | `IntegratedResultsBoundary` (with `AndroidProfileSaveSystem` in `AndroidProfileBoundary`) | nested `IntegratedResultsSession` (`IDisposable`) **own type** holds ending templates/catalog restoration, statistics callbacks and event context, ledger directory, save-system swap/restore and result listeners; serializer guards remain static; `resultsSaveSystem`, `resultsLedger`, `resultsStats` and `resultsRunReport` stay shared on the coordinator; `r.results` remains the coordinator observation | `PrepareResultsKeyItems` may precede `PrepareIntegratedResults` (calls session `Prepare`) → `CleanupIntegratedResults` (calls `Dispose`: profile cleanup precedes save-system restore); owner created on first use and retained after `Dispose` | — |
| HUD and UI | `RecoveredHudBoundary`, `RecoveredHudPresentation`, `RecoveredHudFeedback`, `RecoveredPickupPresentation`, `MoonPillarPresentation` | nested `RecoveredHudSession` (`IDisposable`) **own type** holds menu events, reference-rendering restoration and text reflection/restoration state; `recoveredHud`, `recoveredMenu`, `recoveredTextSettings` and `ownsRecoveredText` stay shared on the coordinator; feedback/queue state and pickup bindings stay in the existing presentation component **own types**; `r.hud` remains the coordinator observation | Session startup prepares owned text after prior-session collection, before presentation/catalog and independent of menu bypass; separate `PrepareRecoveredText`/`Menu`/`Hud` → `CleanupRecoveredHud` (calls `Dispose`, HUD then menu only), `CleanupRecoveredMenu`, `CleanupRecoveredText` (later catalog teardown); owner created on first use and retained after `Dispose` | — |
| World, director and combat | `IntegratedWorldBoundary`, `AutomaticSpawnBoundary`, `AutomaticDirectorBoundary`, `EnemySpineBoundary`, `StagePopulationBoundary`, `WholeInteractableBoundary`, `RunClockBoundary`, `PlayerDefeatBoundary`, the `World*` item boundaries (27 files) | nested `RunClockSession` (`IDisposable`) **own type** holds original clock callbacks, async lifecycle, scene-catalog restoration and timestamps; `clockSceneDefs` and `priorClockScene` stay shared on the coordinator; nested `PlayerDefeatSession` (`IDisposable`) **own type** holds the death-effect locator, async handle, prefab, observed effects and defeat body; nested `WorldHealingItemsSession` and `WorldLegendaryItemsSession` (`IDisposable`) **own types** hold healing source names, Warbanner reflection/callback and observed instances, and legendary controller names, observed instances and remote-transform/host-authority snapshots, respectively (static fields remain static); `r.runClock`, `r.playerDefeat`, `r.procContent` and `r.itemBehaviors` remain coordinator observations; shared world registries and remaining boundaries use coordinator fields; nested `WorldItemDisplaySession`, `WorldDotSession`, `WorldItemBehaviorSession` (`IDisposable`) **own types** hold their files' private item-display, DOT and item-behaviour state (J534); for the opt-in selected-skin path, `AndroidNativeSourceSkinLifecycle` owns the native `CharacterModel` inventory callback and `WorldItemDisplaySession` observes it only for presentation; nested `CombatSpineSession`, `StageBossContentSession` (`IDisposable`) **own types** hold their files' private state; nested `PrimaryFireSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldProcContentSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldEquipmentSession`, `AutomaticDirectorSession` (`IDisposable`) **own types** hold their files' private state; nested `EnemyRewardSession` (`IDisposable`) **own types** hold their files' private state; nested `WholeInteractableSession` (`IDisposable`) **own type** holds owned templates/cards, player-spawn points and the native spawn-point prefab snapshot/lease; `wholeSceneDirector`, `wholeStageContext`, shared world/commerce collections and reports remain on the coordinator; nested `WholePopulationSession` (`IDisposable`) **own types** hold their files' private state; nested `EnemySpineSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldFlightEquipmentSession` (`IDisposable`) **own types** hold their files' private state; nested `IntegratedWorldSession` (`IDisposable`) **own types** hold their files' private state | `PrepareIntegratedWorld` → `CleanupIntegratedWorld` → `VerifyIntegratedWorldCleanup`; `PrepareEnemy` → `CleanupEnemy` → `VerifyEnemyCleanup`; `PrepareRunSceneContext` → `StartOriginalRunClock` → `CleanupRunClock` (calls `Dispose`) → later `ReleaseCompletedRunAsyncAssets` after Run teardown; `PreparePlayerDefeat` → `ObservePlayerDefeat` → `CleanupPlayerDeathEffect` (awaited coroutine: detach listener, destroy effects, release prefab references then handle, remove locator; `Dispose` detaches the listener only); `PrepareWorldHealingItemSource` / `ObserveWorldHealingItems` → `CleanupWorldHealingItems` (calls `Dispose`: final observation, level callback removal, instance destruction); `PrepareWorldLegendaryItemSource` / `ObserveWorldLegendaryItems` → `CleanupWorldLegendaryItems` (calls `Dispose`: final observation, instance destruction, remote-transform then host-authority restoration); all four owners created on first use and retained after cleanup; `PopulateWholeStage` → `CleanupWholeStageInteractables` (stage objects only) → `CleanupWholeInteractables` (calls `Dispose`: stage cleanup, spawn-point prefab restoration, lease release); interactable owner created on first use and retained across stage turnover and cleanup | `test_scene_acceptance.py` (acceptance helpers) |
| Position indicators | `TeamIndicatorQueueBoundary`, `AutomaticSpawnBoundary`, `SessionResourceBoundary` | nested `TeamIndicatorQueueSession` owns the cached original queue-processor delegate and first dispatch failure; the automatic body iterator temporarily owns only its captured source-enabled root `TeamComponent` references | capture before the existing disable loop; restore only in the integrated-world path and clear before activation yield; process the original queue from the port fixed tick only while `RoR2Application` is inactive; native component lifecycle plus J787 completed-session pruning remain teardown owners | `tests/test_team_indicator_helpers.py` (authored synthetic lifecycle contract; actual renderer remains an editor/device gate) |
| Equipment expansion availability | `runtime/world/EnemyRewardBoundary.cs`, existing `PortSession.OriginalStats` call site | `EnemyRewardSession` owns one `RewardEquipmentExpansionMaskLease`, retaining the exact native Run and rented mask before population | Integrated survivor state setup acquires before spawn; reward preparation reuses the exact lease; pre-rule refresh locks all required expansions and the later existing rule-ready refresh uses native availability. Partial setup and ordinary disposal return once before Run disable; foreign replacements survive and recovery retains ownership. Item-mask and RNG setup retain their existing phase. | `test_reward_equipment_mask_lease.py`, authored host doubles in `tests/fixtures/reward_equipment_mask_lease.cs` |
| Commerce and pickups | `WorldCommerceBoundary`, `ChestPurchaseBoundary`, `ChestEjectionBoundary`, `ItemPickupBoundary`, `GenericPickupBoundary`, `MoneyCostBoundary`, `PickupDropletFlightBoundary` (10 files) | nested `ChestEjectionSession` (`IDisposable`) **own type** holds chest animation snapshots, source effect pool/cache references, observed effects/returns, owned material copies and droplet/model references; `chestEjectionBegan` stays shared with ChestPurchase on the coordinator; `r.chestEjection` remains the coordinator observation; remaining boundaries use coordinator fields; nested `GenericPickupSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldCommerceSession` (`IDisposable`) **own types** hold their files' private state | `PrepareWorldCommerce` → `CleanupWorldCommerce`; `OwnChestAnimationSources` / `PrepareChestEjection` → `ObserveChestEjection` / `FinishChestEjection` → `CleanupChestEjection` (calls `Dispose`: droplet destruction, source effect pools/cache cleanup, material destruction) → diagnostic `CheckChestEjectionCleanup` after chest/pickup cleanup; owner created on first use and retained after cleanup | — |
| Stage transport and teleporter | `TeleporterWorldBoundary`, `IntegratedStageBoundary`, `AndroidStageTransport`, `StageGeometryBoundary`, `GoldshoresBoundary`, `MoonMissionBoundary`, `MoonEscapeBoundary` | nested `StageGeometrySession` (`IDisposable`) **own type** holds owned billboard copies, Moon-volume mode, map-zone activation/source names and observation callbacks; geometry bundle, scene, materials, source-object/context roots, first-stage selection and `r.stage` stay shared on the coordinator; remaining boundaries use coordinator fields; nested `IntegratedStageSession` (`IDisposable`) **own types** hold their files' private state; nested `TeleporterWorldSession` (`IDisposable`) **own types** hold their files' private state | `PrepareTeleporterWorld` → `CleanupTeleporterWorld`; `PrepareStageTransport` → `CleanupStageTransport`; `PrepareStageGeometry` / `LoadStageGeometry` forward to the session; source-context deactivation stays separate; `CleanupStageGeometry` remains an awaited coroutine at the same call sites, including after `CleanupSpawnConfig` in `Start` (pause zones, detach observations, unload scene, destroy billboards then materials, unload bundle, mark coordinator report); owner created on first use and retained across stage handoffs; `Dispose` is a no-op | — |
| Combat-input first-failure witness | `TeleporterWorldSession.ObjectiveCombatInput`, `ObjectiveCombatInputFailureWitness`, existing `WorldReport` | Only explicit skill-coverage diagnostics allocate/reuse the witness; the ordinary path enters the same core directly. Read-group, row and CLR/Unity-null states describe already-read operands. The first NRE snapshot is copied to the report before bare rethrow; diagnostic failures cannot replace it. No operand becomes optional. | Per-call reset; no retained Unity references; the report survives existing cleanup, which remains authoritative | `test_objective_combat_input_failure_witness.py` executes the production wrapper, witness and report DTO against a synthetic core; runtime cause remains open (J811) |
| First-stage source lifecycle (diagnostic) | `runtime/stage/FirstStageDiagnosticGate.cs`, `FirstStageSourceOwners.cs`, `SourceStageIdentityLifecycle.cs`; existing stage/objective/population boundaries | `IntegratedStageSession` owns the exact source identity transaction and its Director bridge; `TeleporterWorldSession` owns the inactive prepared objective and exact native placement; `WholeStagePopulationObservation` owns pre-start listeners | Explicit per-attempt `SessionReport.nativeFirstStageLifecycleDiagnosticAttempt` defaults off, supports Golemplains/Lakes only and always marks assisted. Prepare native inputs → activate/spawn audited source cohort → genuine Run scene change and server Stage-begin → natural SceneDirector population/Teleporter Start. Retire owned actors/interactables → exact Stage → objective → source cohort → providers. Transport refuses before mutation. | `FirstStageDiagnosticGateFixture.cs` (pure production gates and an inactive native managed-field lease fixture; actual native lifecycle remains a separate device gate) |
| Siren encounter | `runtime/stage/SirenEncounterBoundary.cs`, `SirenEncounterEggTargets.cs`, `SirenNativeListeningSnapshotPolicy.cs`, `SirenNativeListeningSnapshotReader.cs` | `SirenEncounterSession` (`IDisposable`) owns the exact source encounter, its network-spawn lease, native BossGroup listener, observation clock, and private native egg-list/object/ID baseline; `SirenEncounterReport` retains bounded scalar last-sample data, never Unity object references | `IntegratedStageSession.BeginOriginalStage` after source population and native `Stage.Start` → bounded stage tick → `CleanupSirenEncounter` before transition/unload or transport disposal; a new exact native `Listening` instance starts a fresh snapshot, listener exit releases private references but preserves timestamped last-observed scalars, and owner cleanup releases references | `SirenEncounterHost.cs` (exact-editor selection/transaction fixture; native lifecycle and snapshot integration remain unverified) |
| Siren source entry | `runtime/stage/SirenSourceEntrySession.cs` | `IntegratedStageSession` retains the `SirenSourceEntrySession` (`IDisposable`) and its exact source scene, ID-11 toggle target snapshots, source-spawner disable witnesses, egg identities/poses and per-row retirement progress; reports remain in `r.stageProgress.sirenSourceEntries` | With the exact temporary Stage current, preflight the inactive imported Ship Graveyard identities before the existing Director owner activates ID 2; retain the entry owner first and lease only that exact root/identity activation, requiring it to stay unregistered. Activate ID 11 under the same temporary Stage, then release that Stage. Native toggle `Awake` consumes destination RNG already generated by original Run advancement; perform the existing single Run stage callback then the complete native global callback; observe natural spawners and admit the existing ID-10 owner only after the exact cohort gate. Cleanup retries pending captured eggs, removes witnesses, restores toggle targets and retires/restores ID 11; moved, ambiguous or unknown rows retain recovery context; the first identity refusal reports its expected/actual match, name, active state and registration operands without mutation | `test_siren_source_entry_contract.py`, `test_siren_partial_retirement.py`, `test_siren_source_stage_handoff.py`, `test_siren_source_director_handoff.py` (host contract/retry/order fixtures; editor import and native device lifecycle remain gates) |
| Shaders and presentation | `AndroidMaterialPresentation`, `AndroidNativeDeferredPresentation`, `Android*Presentation.shader` (18 files) | **own types** (static) | `Begin` → `Finish` | `test_shader_bindings.py`, `test_shader_metadata.py`, `test_pc_draw_export.py` |
| Developer controls | `DebugAccelerationBoundary` ([debug-acceleration.md](debug-acceleration.md)) | nested `DebugAccelerationSession` (`IDisposable`) **own type** holds the body, saved god mode, ownership flag, charge scan/callback set and grant inventory; `debugPanel` stays shared with IntegratedWorld's graphics button; sticky "assisted" flags stay in the coordinator report | `PrepareDebugAcceleration` (calls `DebugAccelerationSession.Prepare`) → `CleanupDebugAcceleration` (calls `Dispose`; owner retained) | `test_debug_acceleration.py` |

`AndroidProfileSession` reserves each original achievement event before its
detached profile transaction, suppressing reentrant and duplicate delivery.
A thrown transaction releases only that event reservation for a later genuine
callback; successful refusal and post-transaction reporting failures retain it.
Session disposal clears the set. The extracted production-method fixture in
`tests/test_offline_achievement_event_retry.py` checks this host contract (J1039).

For the explicitly selected native-skin diagnostic only,
`NovaDiagnosticDisplay.CaptureNativeSourceSkinReport` asks the existing lifecycle
owner for a read-only visual sample at the five-second report-save cadence.
It copies selected-model visibility/invisibility, Animator state and identity,
the owned camera's SceneCamera/rig association and at most 32 renderer records.
Only the first shared material is sampled; total slot count remains unknown.
Exceptions publish a partial diagnostic instead of escaping report saving.
No renderer, material, camera or visibility state is changed.

The same selected-model owner subscribes once to the exact owned source
SceneCamera pre-render event after its camera/rig/body identity gate. Its first
matching callback records a separate scalar snapshot: frame/time, model state,
at most 12 renderer samples and a bounded 256-entry exact InstanceTracker join.
The same sample reads the static shared-material cache shape (at most 16
buckets, scalar lengths only) and the original material-dirty getter, preserving
unknown/null/truncation states without initializing or changing either.
A complete miss is known-negative; an over-cap miss or accessor failure is unknown.
Later callbacks do not recapture. OnDestroy removes the exact delegate before
existing cleanup. This observes one subscriber boundary and does not prove the
original per-model update completed or that final pixels match the source. The report retains
the last complete pre-disposal sample without retaining Unity object references;
teardown observations remain separate. The production-owner synthetic host
contract covers boundedness, read failures and preservation of native state.

`runtime/input/CharacterModelMaterialCacheOwner.cs` owns the process-lifetime
material-cache prerequisite for this original selected-model path.
`AndroidNativeSourceSkinLifecycle.PrepareInactive` calls it after the existing
model/body, audio and source-enabled gates and before adding the lifecycle
component or activating the model. It validates the exact private static source
field/method contract and bounded cache shape. A valid existing cache is
preserved; a null cache invokes only the retained original
`CharacterModel.InitSharedMaterialsArrays` method and verifies its result.
Malformed state or an uncertain invocation is terminal and is not retried.
The owner retains types and immutable outcomes, without Unity object references.
Session teardown leaves the original static cache intact. Its detached public-field
DTO is recorded in `nativeSourceSkinLifecycle.materialCacheInitialization`;
`initializerAttempted` is process-lifetime invocation-attempt evidence, including
failed calls, and does not claim that an exceptional target method completed.
The owner does not replay the broad startup phase or implement renderer updates.
`test_character_model_material_cache_host.py` exercises source-preservation,
single invocation, malformed-contract, partial-failure and DTO contracts against
authored inert fixtures; device rendering remains a separate gate.

`AutomaticSpawnBoundary` captures the owned body's live, source-enabled root
state machines before callback isolation. Only integrated-world startup restores
those machines after the existing selected-skill setup, counting newly enabled
callbacks in the strict existing check. Source-disabled machines and minimal
probe scheduling are preserved. The temporary snapshot is released before body
activation/yield; existing body/session teardown owns the components.
`test_automatic_spawn_state_machine_restore.py` executes the production restore
helper with fake-null, identity, source-disabled and nonintegrated cases.

The same automatic-spawn iterator captures source-enabled root Huntress trackers
before isolation and restores them only for integrated-world bodies, after
checking the owned root, serialized indicator prefab, input/team references and
finite positive update frequency. Unity retains ownership of the original
Awake/OnEnable/Start/FixedUpdate lifecycle; body/session teardown retires the
component. Disabled source components and other probe modes retain their prior
scheduling. `test_huntress_tracker_activation.py` executes the authored capture,
restore and target-read eligibility contracts. Native targeting still needs
device evidence; the original indicator's separate application-update callback
is not driven by this restoration. See J808.

The same boundary captures canonical skill-machine identities before yielding.
Cleanup merges entry and current canonical bindings, admits only machines on
the owned live body root, and keeps native remapping such as MUL-T's Weapon2.
Only recorded native body destruction permits already-destroyed child machines.
Each counter-only observer acquires a release lease before its event add;
independent releases run even when source recovery retains the native world.
Destructive teardown remains behind that recovery guard. Cleanup faults are
recorded without replacing a primary iterator exception.
`test_automatic_spawn_cleanup_lease.py` executes these production helpers with
synthetic lifetime, partial-subscription and remapping cases (J792).

`PrimaryFireSession` preserves original pistol, reload, barrage and dodge sound
configuration in integrated world play. Historical component fixtures retain
their silent strings. Existing visual exclusions are independent; no event,
routing or gameplay value is synthesized. Setup clones only the reload
configuration; disposal restores captured statics and destroys that owned clone.
The production setup/exclusion/disposal host fixture covers both modes,
including the initial report-mode flag still being unset during configuration.
The owner captures the configured mode and native readiness during setup;
it never treats the later report assignment as startup authority.

Once the original audio owner is ready, existing actor, projectile, pickup,
effect and model adapters preserve source sound identities and authored Wwise
enable states. Unavailable audio retains the historical silent boundary.
`SilentProjectileBoundary` preserves a nonempty native start event in that mode
and retains the original absent-event branch for empty/null values. Other
gameplay, visual isolation and cleanup responsibilities stay with those owners.

For selected PCM diagnostics, the first observed original pistol state records
one read-only source sound/registration/native-voice/global-SFX-volume sample
with a realtime stamp. Voice arrays retain at most eight IDs; failed queries
keep their raw result and never invent active IDs. The sample performs no event,
registration, enable, routing or volume mutation and retains no Unity reference.
It joins existing PCM timing without attributing samples or proving audibility.
The existing source-camera render evidence also reports requested/actual path,
HDR, depth mode and active color space to distinguish pipeline state from a
visual-parity claim.

`PrimaryFireSession` reuses one scalar operand snapshot during observation and
freezes a separate first-failure snapshot only on refusal or accessor exception.
It captures the live body, locator, primary slot, state machine and state in
order; healthy ticks add no snapshot allocation, identity query or diagnostic
string construction. No native slot, state, stock or readiness is repaired.
The coordinator's `RecordPrimarySessionFailure` preserves the first error;
`AutomaticSpawnBoundary` uses a non-reporting strict cleanup validator and
records secondary detail in `automaticSpawnCleanupError`. These diagnostics
share the existing session report lifetime and retain no Unity references.
`test_primary_operand_witness.py` executes the production observer and guarded
iterator with fake-null, single-read, thrown-accessor and cleanup-failure cases
(J796). J797 observes a CLR-null primary slot on a live MUL-T body/locator.
The input owner computes one `commandoPrimaryDiagnostic` gate from the native
Commando body catalog identity for each session. Only that gate enables the
Commando-specific primary observer, completion readiness read and Commando HUD.
General playable-spine setup and survivor skill coverage retain their existing
scope, as does strict canonical-machine cleanup. The identity policy executes
in `test_toolbot_commando_observer_scope.py`; consumer wiring is checked from
source, while the observer's strict missing-operand behavior is executed by the
existing operand test. J801 verifies the scope correction on device: both
Commando defaults retain the observer, while MUL-T bypasses it and then reaches
a separate shared combat-observer failure. Full-kit acceptance remains open.

CombatSpineSession samples primary and body-state operands independently. Its
single-read helpers record CLR-null/fake-null or missing-state samples without
writing native skills or state. An unavailable sample leaves the previous known
state identity intact; unobserved transitions remain unknown. Other combat
observations continue, and unexpected accessor failures still propagate. The
extracted production contract is tests/test_combat_observer_operands.py; strict
skill-machine cleanup and native ability acceptance remain separate (J804).

Only an explicit Siren source-entry diagnostic entering Ship Graveyard wraps
the existing population and original-stage iterators with
`SirenSourceEntryObservedRoutine` in the existing source-entry owner file.
`IntegratedStageSession` records entry, return and the original exception in
three scalar transport fields before outer cleanup can mask the failure.
The observer forwards yielded values and rethrows the same native exception;
reporting callback failures cannot replace it. It acquires no iterator or
scene cleanup ownership. `SirenSourceEntryFailureClassification` preserves an
earlier failure and distinguishes absent registration from failed cleanup.
`test_siren_source_transport_exception.py` executes these production helpers,
including throwing `Current`, `Reset` and reporting callbacks. Lifecycle,
identity, retirement, recovery and the manual Moon gate remain device gates.

Build, device and safety tooling has its own tests: `test_build_identity.py`,
`test_build_snapshots.py`, `test_apk_identity.py`, `test_adb_target.py`,
`test_lab_safety.py`, `test_public_privacy.py`.

Stage-context preparation seams (J639) remain inside those existing owners.
`EnemySpineSession.PrepareEnemy` forwards mandatory `PrepareEnemyContext` then
its actor fixture. `EnemySpineSession` owns idempotent damage/death event
subscriptions: the native first-stage context subscribes before source actor
activation, while the default fixture subscribes at its existing setup point.
Ownership begins before the first add, normal cleanup removes exact delegates
before actors, and source-stage recovery retains the owner and observations.
`test_enemy_actor_observation.py` executes the authored helpers/callbacks and
cleanup against host collaborators, including partial setup and unrelated
listeners. `EnemySpineSession.ObserveEnemy` samples each live target, state
machine, motor and health component independently, including bodies without a
CharacterMotor. Missing enemy reports skip only dependent reward/actor fields;
navigation and director observers keep their own lifetimes. Prior samples and
death facts survive unavailable components. `test_enemy_observer_lifetime.py`
executes that production method with live, missing and destroyed collaborators.
These host fixtures do not raise native gameplay events.

`IntegratedStageSession` retains an exact effect-pool map/pool/helper return
batch until native retirement is proven. It issues each original return once;
the existing transport and final reward-cleanup coroutines cross one actual
Unity frame only when loans remain, allowing native deferred destruction to
finish before the strict zero-loan and inactive-pool/destroyed witnesses.
Unknown, interrupted or failed ownership retains the batch and dependent
assets. The synchronous native scene-exit listener keeps its immediate guard
and ordering. `RunClockSession.ReleaseCompletedRunAsyncAssets` is now awaited
by `EnemyRewardSession.CleanupEnemyRewards` before forced asset release;
transport awaits the same fence before scene unload.
`test_effect_loan_return_lifecycle.py` executes the production owners/caller
seams with authored immediate, deferred, stuck and foreign-owner collaborators.
It does not identify the exact residual from J746 or qualify native loss.

`AutomaticDirectorSession`
separates native elite/catalog/
player initialization from the existing one-card director activation.
Its native first-stage path registers only the exact existing inactive player
controller before results prepare their statistics component. The later catalog
setup adopts that same registration without another Awake/OnEnable; the existing
director owner removes it even if results fail before a director report exists.
Native stage deck selection records the full deck but defers source director
property/enabled writes to FirstStageSourceOwners after its final cold preflight.
That owner binds both decks before genuine activation; default selection retains
its existing immediate writes. `NativeDirectorDeckSetterFixture.cs`, staged by
the same source producer, checks native setter effects on an inactive component
without a Run or network session.
`WholeInteractableSession` also owns the native first-stage borrowed drop-table
transaction. After exact source identities/toggle targets are captured, it
qualifies Lakes' Chest2 and Wake reward fields, clones four Basic tables through
`TeleporterWorldSession.ObjectiveDropTable`, verifies serialized configuration,
and regenerates choices from the current Run before activation. Positive-weight
categories require current lists; only the ordinary chest requires a nonempty
selector. Empty optional reward tiers remain empty. The known Scrapper exclusion
table and late-bound reward-creator slot are validated without replacement.
`NativeBorrowedFieldLease` records each binding before mutation and restores
only its exact owned/original values. Identity unspawn precedes reverse field
restoration, which precedes toggle restoration and objective resource release.
A foreign replacement retains recovery state and owned resources. Golemplains
has no known chest/Wake consumer. This qualifies accepted known component shapes;
it does not discover arbitrary future table consumers. The portable
`test_native_source_loot_contract.py` executes the extracted lease and checks
source ordering with authored fixtures. Native Run regeneration/roll remains a
device gate.
`TeleporterWorldSession.PrepareInactiveObjectiveTemplate` prepares its owned
clone before the existing direct spawn. `WholeInteractableSession` uses a
short-lived `WholeStagePopulationObservation` to store the exact selection/spawn
delegates and spawn-point baseline around its existing manual native `Start`.
Its `finally` retains sequential detach/collection behavior. These extractions
preserve the current public call order, setup fields and teardown owners; they
enable no native source-stage cohort, new selector or RNG-order claim.

The Siren encounter draft activates and network-spawns only the original inactive
`shipgraveyard` encounter identity. It preserves the source FSM, scripted boss
card, squad, rewards and separately expansion-gated portal callback. It never
calls global scene spawning, so the existing source-disabled MapZones retain
their own boundary. The report distinguishes a selected owner, live eggs, native
encounter start and the exact native BossGroup defeat event. Native squad-member
and summon callbacks identify the original boss and its probes without scanning
all masters. Cleanup validates the complete owned actor set before requesting
body/master destruction; changed identities or ownership refuse retirement.
It detaches its callbacks first, unspawns the source identity, restores its active
state and synchronously destroys only that owned scene instance while the server
is active. This runs the native squad's `OnDestroy` unsubscribe before the existing
session shutdown, which precedes deferred geometry unload. Actor destruction
requests are recorded as requests; `cleanupDisposed` must be read alongside
`cleanupError` and the individual cleanup flags. Egg placement, native spawn/unspawn,
rewards and teardown still need device acceptance. No separate probe switch case
implements this behavior.

Native teleporter retirement (`TeleporterWorldSession`, current source draft,
J600): this owner captures the exact instantiated host and network identity,
marks possible activation before detaching it from inactive staging, and keeps
ownership through partial setup. Final disposal unregisters the identity and
synchronously destroys only that host while the server remains active. This lets
the native `CombatSquad.OnDestroy` remove its server-gated static callbacks before
the outer session shuts down networking. A never-activated inactive host with no
network identity/listeners has a separate partial-setup cleanup path. Exact-target
death/summon callback counts before and after retirement remain as scalar fields
in `ObjectiveReport`; the read-only `NativeCombatSquadListenerEvidence` helper
preserves destroyed Unity wrappers and never restores or modifies event lists.
The existing stage-handoff destruction/two-yield path remains unchanged.
`TeleporterLifetimeHost.Run()` is a Play Mode native-callback fixture, staged by
`whole_catalog.stage_build_sources`; exact-editor execution and Android callback
retirement pass (J601/J609). Repeated-session memory attribution remains open.
No new probe switch case implements the cleanup.

Survivor ability observations (`SurvivorSkillObserver.cs`, current runtime source):
`IntegratedWorldSession` creates this independent `IDisposable` owner after local
player authority is connected. It holds only that body's four original skill slots,
definition snapshots and authority/server callback subscriptions. Native callbacks
use the original `SkillLocator.FindSkillSlot` at each event, preserving Toolbot's
component reassignment and the source precedence for aliased slots. They count
activation per slot; a once-per-second sample records active definitions,
stock and state-machine context. Definition names are cached until the original
definition changes. Removed native components clear live slot context while retaining
historical activation counters. Suppressed missing callbacks are a classified non-pass.
Cleanup detaches both managed callbacks, including after Unity
destroys the native body, then clears all body/skill/definition references before
world teardown. The report is `SessionReport.survivorSkills`; it proves callback
execution, not targeting, placement, effects or complete ability semantics.
The separate `components` report covers every GenericSkill on that body by exact
component identity, including Toolbot/Captain auxiliary loadout components that
native `FindSkillSlot` maps to None. It retains current component indices and
canonical mapping separately from the four slot counters. Bounded samples
reconcile components; a live same-body callback missing from the cache triggers
one immediate reconciliation so its first activation is retained. Removed/body-
destroyed components clear live state while scalar counts remain. Callback lookup
and canonical labels avoid per-activation LINQ closures and enum conversions.
This source draft passed its extended synthetic fixture (J602); auxiliary native
ability execution on Android remains pending. The four-slot device check keeps
its narrower canonical-slot criteria.
`SurvivorSkillHost.Run()` is the exact-editor synthetic ownership/override fixture.
It also checks that the loadout menu retains original component indices and uses
`hideInLoadoutSelect`, independently of character-select visibility. The existing
`OfflineLoadoutBoundary` owns that menu's scroll state, resets it at menu entry or
survivor change, and scrolls the source-selected rows above a fixed footer so
Toolbot's five and Captain's six loadout rows remain reachable.

`./dev prototype --action survivor-kit-check --target all` (current host action,
`scripts/lab/survivor_check.py`) runs the eleven base survivor catalog keys
sequentially in the integrated Lakes world. A comma-separated `--target` selects a
subset. Commando/Huntress use ordinary selection; locked base survivors use an
explicit diagnostic override and invincibility, never permanent profile awards or
expansion availability. Before launching, the runner verifies selected storage
policy against both the ownership receipt and live storage/package placement;
internal-storage reserve remains the install owner's gate. It does not infer
controller support from storage policy. A case needs 60 s of live world play and positive native
authority **and** server activations on all four slots; at 180 s it reports missing
activation evidence. Source-suppressed callbacks remain unproven. First failure,
first-stage departure or process exit ends the batch. Current-process errors are
polled every 10 s, stop the case even when report error fields are empty, and are
checked again in the final log; known handled Windows shader-target messages use
the existing filter. Results preserve the first failure and observed error list.
Each case preserves its first-world screenshot, frozen report, log and crash
evidence under `work/experiments/survivor-check/`. Cleanup removes the selector,
stops the owned app and sleeps the display. Every ADB command checks the parallel
session's coordination lock. Host contracts: `tests/test_survivor_check.py`.
This supplements both unchanged baseline modes; it does not replace them.

The current optional `--expected-apk-sha256` on survivor-kit-check and both
session cleanup actions binds a diagnostic to the selected device's matching
ownership receipt. `scripts/lab/installed_attempt.py` owns hash syntax and
receipt binding, then its existing reader verifies the receipt APK bytes and
extracts the unique embedded attempt before any selector push or launch.
Explicit binding never reads the mutable global current-build pointer, installs
an APK or claims the selected APK is current. Omission retains current-build
equality at check start. The survivor batch resolves this binding once before
its target loop, allowing host builds to finish during independent device runs.
Results record `apk_binding_mode`; default baseline acceptance remains separate.
Refusal/workflow contracts: `tests/test_owned_apk_diagnostic_binding.py` and the
existing installed-attempt, survivor and session cleanup tests.

`DeveloperSkillVariantSelection.cs` is the current, explicitly assisted per-run
loadout boundary owned by `AndroidProfileSession`. The optional
`survivor-kit-check --target <base-key> --skill-variants <ignored-json>` accepts
exactly one survivor. Its JSON object contains `survivor` and `entries`; each
entry contains `componentIndex`, `familyCatalogIndex`, `variantIndex` and
`skillCatalogIndex`. The runner refuses unknown/duplicate fields and duplicate
components before device access. The runtime independently validates the actual
body component order, native catalog identities, family bounds and expansion
requirements. Base-game locked variants remain diagnostic choices, never earned
profile choices or expansion access.

Before `SpawnBody`, the profile owner retains the unchanged profile/default
preview, copies the native master loadout, applies the requested indices through
native loadout APIs and calls `CharacterMaster.SetLoadoutServer`. It verifies
the resulting body against effective per-run variants while checking the saved
profile against its original preview. Diagnostic selections bypass menu-edited
loadout persistence. The master owns this temporary native loadout; profile
cleanup clears the preview/effective arrays, and existing body/master teardown
retires the run. No `SkillFamily`, unlock or persistent profile is edited.

`SessionReport.developerSkillVariantOverrideReport` records request/application
and refusal. A session-level assisted marker is saved before native mutation;
debug report initialization carries it forward, and permanent discovery,
achievement and result gates consult it directly. The launch file cannot supply
that trusted marker. Diagnostic `survivorSkills.skillVariantInventory` and the
override report expose bounded actual component/family/variant/SkillDef indices
for constructing a later explicit selector. Selected native loadout indices and
live runtime definitions are separate: prefab assets have no `GenericSkill.Awake`,
and a live skill can have a temporary override. Invalid or oversized inventories
refuse rather than truncate. This adds no ordinary menu eligibility.
A live inventory binds reciprocal native body/master ownership and exact server
mappings, with the catalog prefab's matching component/family order. Override
inventory takes precedence only for an explicitly requested override; Unity's
empty default inline reports do not displace the actual live observation.
The host result keeps that authoring inventory and labels pre-spawn and live
post-spawn inventories separately in both full-kit and isolated checks. A
requested alternate in the four-slot check must also match the final live
family, selected variant, selected SkillDef and runtime definition/index, with
the effective native loadout agreeing. Non-requested passive/auxiliary runtime
identities gain no invented activation requirement.

Host parser/assessment contracts are in `tests/test_survivor_check.py` and dispatch
contracts in `tests/test_cli_actions.py`. The existing fixture producer stages
`DeveloperSkillVariantSelectionFixture.cs` for exact-editor native API and strict
input checks. Its separate unawakened-prefab contract requires an already loaded
and registered native catalog prefab; idle API checks do not prove application
to that prefab. Source/host evidence and later device variant results stay
separate in the journal.

The checker also classifies J602's current component inventory independently
of the four-slot gate: four components for most base bodies, five for Toolbot
and Croco, six for Captain. Current indexes/instance identities must be unique
and complete; removed history is separate. Missing older instrumentation is
explicitly unavailable. Passive and auxiliary components need no invented
activation requirement; valid inventory is not complete ability acceptance.

`SurvivorSkillInputCoverage` (diagnostic input owner, default unconstructed)
is selected only by `SessionReport.diagnosticSkillCoverage`, which the skill
check explicitly enables. `IntegratedWorldSession` creates it after live
authority, bridge, assist tracking and skill observation exist; applies it
after the ordinary automatic producer; and disposes it before the observer
and body. It resolves current canonical components at each request, reads
native `CanExecute`, and overlays a single 0.25 s ordinary skill-button pulse.
Requests are bounded to 12 and 120 s, spaced by 6 s. Reports distinguish
eligibility, requests, later input-bank edges and native callback counts.
Manual/foreign input changes survive release. No cooldown, stock, skill state
or movement is written. `SurvivorSkillInputHost` tests synthetic routing,
dynamic slots, stale-edge refusal, ownership, bounds and disposal in the
exact editor. Real survivor behavior remains a device gate.

An optional `--skill-slot` on `survivor-kit-check` composes with the existing
strict per-run variant selector for one base survivor. The same owner enforces
one selected native skill request during each 0.25 s pulse and masks all other
skill requests at the input sink for the full 60 s observation interval, even
after the selected input edge and callback pair appear. It also blocks automatic
diagnostic equipment requests while preserving explicit touch input. The result
requires the exact live post-spawn component/family/variant identity, a later
input-bank edge, and fresh authority/server callbacks. It is assisted single-slot
input evidence, not a four-slot kit pass, slot-causality proof, or complete
ability-output acceptance. The special-slot request does not synthesize a
contextual primary input for Huntress Snipe. Omitting `--skill-slot` retains the
all-four behavior above.

The explicit `--toolbot-offhand` option requires one Toolbot target and the
exact native Buzzsaw/Dual Wield variant tuples. The same input owner validates
the live five-component loadout, requests special once, observes native Dual
Wield with its contextual secondary override and Weapon2, then requests
secondary once. It requires later input-bank edges, both native callback pairs
and FireBuzzsaw on Weapon2. The isolated input sink masks competing automatic
skill requests; manual input, identity loss, neutralization or the bounded
deadline stops the sequence. Disposal releases the owned input state before
the observer/body. The default selector remains false. Aggregate damage
counters provide context only; this mode establishes no slot-specific damage
or complete ability semantics. Host contracts extract the production phase
policy and check selector/refusal routing.

The same owner takes four one-shot readiness snapshots only in this Toolbot
mode: before special, after the native Dual Wield override, at the first
secondary-readiness refusal or sequence stop, and separately at the actual
terminal stop. The final snapshot retains its own phase, outcome, elapsed time,
frame count and fixed time without replacing the first refusal. They read stock, recharge,
enabled state, both native readiness predicates, the configured machine name,
the actual resolved machine reference, and the separately named Weapon/Weapon2
machines. Each machine also reports enabled/active state, update-transition
eligibility, pending-main status, configured main type and public networker/index/
authority values. An assigned index is not proof of private network-array
membership; the pending target type has no public API and stays unavailable.
Missing operands and exceptions have explicit status fields;
`captured` distinguishes a real snapshot from an empty serialized object.
A missing or destroyed resolved reference stays unavailable rather than
falling back to an empty-name lookup. No native readiness gate changes.
The report owns these values for the session; disposal releases input before
the observer/body. `test_toolbot_readiness_observation.py` exercises the
production resolver, including Unity-style fake-null references;
`test_toolbot_terminal_readiness_capture.py` executes distinct, idempotent
first-refusal/terminal headers and checks bounded public queries.

The default-off `--captain-supply-beacon` selector composes in this same owner
for one assisted Captain run with the exact native six-component identity and
no variant/slot/Toolbot selector. It snapshots the existing bridge's cumulative
real `InputBankTest.PushState` edge witness before each of two bounded pulses:
Captain special, then re-mapped native SupplyDrop1 on primary. It waits for the
original setup state, both original slot remaps, read-only valid-placement
observation, native authority/server callback deltas, the original healing call
state, an increased CaptainSupplyDrop count owned by the same `CharacterMaster`,
and return to ordinary body state with that deployable still present. Edge
counter reset/multiple increments, lost ownership, neutralization, changed
identity, timeout, or unresolved teardown stop/refuse without writing skill
state, stock, cooldown, placement, deployables, or profile values. The overlay
remains masked while an original native state is pending and disposes only its
owned bridge input/witness. This proves neither supply-drop damage/healing nor
presentation/full ability semantics; those remain separate device gates.
The auxiliary SupplyDrop1 uses native `CanExecute` without an extra Unity
component-enabled requirement, matching the original input dispatcher. A
primary pulse still requires the current setup state, exact slot remaps and
current valid native placement. The report separates current placement and
remap-gated native readiness from the historical positive placement witness;
bounded timeout labels identify the last failing operands.
`test_captain_supply_readiness.py` executes the extracted production phase and
readiness policies, including a disabled auxiliary component.
The setup identity requires the serialized Skillswap activation machine with
`EntityStates.Captain.Weapon.SetupSupplyDrop`; the state's namespace does not
name its machine. `test_captain_setup_identity.py` executes this production
predicate and rejects the former Weapon assumption, other states and missing
identity.
Family names use an explicit `ScriptableObject` base-object read: the accepted
native `SkillFamily` API hides the name property with an unavailable getter.
The same read supplies refusal details, separately from the serialized
`GenericSkill.skillName` label. `test_toolbot_family_name_shadow.py` executes
the production identity/refusal methods with that API shape and rejects
mutated family/catalog/variant/runtime identities.

Siren egg diagnostic input (`SirenEggDiagnosticInput.cs`, explicit default-off
per-attempt selection): `SessionReport.diagnosticSirenEggInput` constructs an
independent world-owned input lease only when selected. Jump snapshots carry a
write revision and fixed-consumption boundary so release preserves a later
producer write and cannot duplicate a consumed pulse. Before ordinary input
producers it releases its prior owned values; afterward it may navigate, aim
and request primary against the nearest currently visible original registered egg.
When all revalidated candidates are occluded, the nearest remains the navigation
target with primary released. Candidate caches above 12 refuse before physics
queries. A fixed scalar witness samples the real Huntress tracker target and
separates missing, disabled and inactive trackers before reading an active
tracker; target states distinguish destroyed, unidentified and known targets,
selected/native ID matches and requested primary. It records live tracker
settings and current geometry without refreshing native tracking or claiming its last LOS/range/cone
decision. If only same-egg NoTarget observations occur, a read-only scalar window
can use the existing delayed slot after 0.5 s of samples with gaps at most
0.25 s; invalid/discontinuous observations reset it. The two-snapshot stage cap
stays fixed and this changes no native target behavior. Two optional, one-shot
eligibility snapshots use the first visible
primary mismatch and a later null target with the same selected egg. They
record the held input aim before this frame's write, exact HurtBox registry
membership with a 4,096-entry cap, current body/team/layer/health/collider data,
and finite range/cone/LOS observations. Cached native target age remains
unknown; truncated absence and unavailable operands remain unknown. Optional
snapshot failures are reported separately, while the existing native target
getter still propagates its original exception before any input action.
Snapshot data survives the existing stop/disposal path; no engine reference
is retained by the report. `test_siren_target_eligibility_witness.py` executes
the authored membership, geometry-policy and getter-rethrow contracts.
`SirenNavigationObservation.cs` is the same world's bounded, read-only
approach recorder and pure input-ownership policy. On an assisted diagnostic
frame with the exact source scene, owner and native mission listener active,
`NovaInputBoundary` gives the Siren adapter the sole automated route write.
Manual takeover or nearby hostile combat retains the existing general route.
The Siren adapter writes its route before reading the pending sample, then
queues the next request; writer and reader use the same stage-relative clock.
No player control mapping or native target/encounter rule changes.
After the same selected egg remains outside the active
native tracker range for 0.5 seconds, it pairs a previous owned
bridge request with a later bridge fixed tick. At most eight samples over eight
seconds record copied input-bank movement, motor/position, source path node and
real path-request identity; labels are capped at 64 characters. Objective stall
is recorded with an explicit availability flag at trigger and request time;
zero or unavailable stall does not prevent observation of a progressing route.
It closes on
manual/owner/bridge/egg change, unavailable operands, clock rollback, yield,
terminal stop or disposal. No normal run or inactive Siren selection starts it.
The context reads native state; route cadence, movement and gameplay remain
owned by the existing navigator/motor. Reports contain no Unity references.
`test_siren_navigation_observation.py` executes the production recorder with a
tracked synthetic reader/contract fixture; the original native-target test
includes the new report types without replacing its witness assertions.
The existing aim helper can issue at most 24 linecasts per active
sample for the inspected original egg shape; inactive selection does no witness
work. It yields to manual control and nearby hostile combat. Native encounter start, source/stage
loss, transport, first failure and the 180 s observation budget latch a stop.
No damage, egg counter, native registration, encounter state or spawn is written.

A separate default-false `sirenNativeEncounterContinuationRequested` selector
uses these same owners after exact source-entry registration. Its launch keeps
the legacy egg-input selector off, and it arms ordinary egg input only after
the live source owner and original Listening state are ready. Entry-only mode
retains its current canonical-registration guard. Continuation retains the
previous exact registration witness while original egg deaths change the list,
holds the next transport request and stops on native encounter start plus an
exact callback-captured boss master, positive network ID and local-object map.
The witness also requires the original catalog body, native monster squad,
active source scene, server identity and absence of player/foreign minion
ownership. The 180 s budget uses world elapsed minus the world-relative stage
entry offset; invalid clock operands refuse. Finalization disarms input and
retains the existing source/encounter retirement and recovery rules. The
continuation's completed flag means this bounded encounter-start observation,
not boss defeat or mission completion. The extracted production contract and
stateful identity witness run in
`test_siren_native_encounter_continuation.py`; device acceptance remains open
(J800).

`SirenEncounterEggTargets.cs` extends the existing source encounter owner. Its
0.5 s sample reads the exact current native Listening registration flag/list,
then caches only native registered eggs. Each input lookup revalidates source
body/catalog/asset identity, exact server object mapping, same active scene,
living health and the original main HurtBox relationship. A replaced native
Listening state cannot inherit the old list. A registered empty list yields no
target; runtime names alone never authorize input. Cleanup clears the cache and
all engine references before source encounter teardown. The editor fixture
checks the imported original asset and native field contracts, plus synthetic
input ownership/yield/stop cases; it does not certify actual mission completion.

Engineer shield compatibility (`EngiShieldHitGuard.cs`):
`IntegratedWorldSession` acquires `EngiShieldHitGuardTemplateLease` only for the
selected original Engi body, before automatic skill input. The caller loads the
exact owned catalog shield template and requires a non-scene asset. The lease
validates its native blocker/Collision references and adds only an authored
component to that in-memory template; native type, serialized fields, collider,
network identity and deployed state remain unchanged. Each Unity-created shield
runs the guard after native Awake, captures its exact native rejection delegate,
and handles only an actual-null world-hit HurtBox. Valid HurtBox targets use the
captured native filter. Processor identity, owner/collider liveness and callback
ownership are checked; missing or destroyed targets remain visible failures.
The first guarded world hit per instance emits a bounded lab log marker.

At host destruction, each instance withdraws only its still-owned callback via
the native HurtBox setter, including a destroyed managed wrapper whose inactive
Collision child never received OnDisable. Foreign replacements remain untouched.
Explicit live component detach restores the captured native callback first;
template release uses this separate path. Both paths clear owned references.
`VerifyIntegratedWorldCleanup`, after server shutdown and two frame
yields, requires scene guard clones to be gone before restoring/removing only
the template component. The existing catalog owner retains asset lifetime.
`r.world.engiShieldGuardPrepared/Released` records the lease boundaries.
`EngiShieldHitGuardHost` is a genuine Play Mode native-filter/clone fixture;
it manually activates the source Collision child and does not certify native
deployment timing or a bundle-template mutation on Android. J614 records its
evidence; J617 adds exact native rejector-list identity checks for inactive
destruction and explicit detach. Native skill/device acceptance remains separate.

LightningStake diagnostics (`LightningStakeDiagnosticObserver.cs`, current
read-only owner): the integrated world creates it after catalogs/report setup,
tracks at most three live exact catalog/server-mapped projectile identities,
releases their sampling slots when identities retire, and disposes with the
world. Its report counter retains cumulative admissions across turnover.
Registry discovery retains the six-frame cadence; only retained objects receive
per-frame finite/stuck checks. A shared policy caps each identity at 12 scalar
snapshots and all history at 36 rows. It reserves the last per-identity slot for
the first observed finite-to-nonfinite transition; at a full history that
transition can replace only the oldest ordinary row. A latched capped status
exposes refused/replaced history without a per-frame string allocation.
Transition-only history cannot grow, and between-scan short lifetimes remain
unobserved. Disposal releases live slots and makes the policy inert. The first
observation is explicitly not a known spawn position.

`r.world.lightningStakes` retains root/network/Rigidbody values, velocities,
owner attribution and native stick/victim/local-offset/ancestry observations.
Frame/fixed-time clocks accompany world seconds. No native fire/collision hook,
transform correction or error filter is added. Diagnostic read failures expose
an inert status separately from native runtime errors. The source-asset/policy
fixture checks minimum imported identity/geometry and actual sampling limits;
`test_lightning_stake_observer.py` executes the extracted policy and identity
retirement with authored host collaborators. Report replacement/status remain
source-inspected there. Only a device trace can identify a runtime transition,
and neither fixture nor
first sample proves native fire input. J623's intermittent corruption remains
unresolved until new evidence identifies its producer.

Engineer native outputs (`EngineerNativeOutputObserver.cs`, current authored source):
`IntegratedWorldSession` creates this read-only `IDisposable` owner for the exact
live original Engineer after local authority and skill observation exist. A
once-per-second sample reads only that master's native deployable list. Mines
and bubbles require their native slots, reciprocal owner and exact projectile
catalog identity with a server-local network mapping. Bubble deployment state
and ownership of the exact source Collision HurtBox guard filter are separate
counters. Turret masters require native deployable/minion ownership and the
original master index; live bodies additionally require reciprocal master/body
references, original body index and server mappings. The original summon event
records exact owner/current catalog master attribution independently of samples.
No skill, stock, damage, deployable, state or gameplay object is changed.
The native deployable wrapper may be uninitialized before first registration;
the observer uses its bool contract before Count/indexing and never initializes
the master's backing list. An idle exact-editor fixture covers that cold state.

The report is `r.world.engiNativeOutputs`. Unique observed counts and native
mine state names survive cleanup as scalars; they do not prove damage, turret
attacks, shield blocking, the guarded-null-hit branch, or every transient output
between samples. Disposal before skill/body teardown detaches the summon event
and clears retained engine references, sets and scratch storage. The source
asset fixture reads minimum GUID/relationship contracts without activation;
its separate Play Mode clone fixture checks real guard/HurtBox remapping and
retires only fixture-owned callbacks. The adapted-catalog fixture requires
initialized lab catalogs and has its own execution gate. These fixture contracts
do not substitute for actual server-created Android outputs.

Native objective exit telemetry (current authored source, J632):
`TeleporterWorldSession` owns scalar snapshots at activation edges, its existing
begin/finish subscriptions, and three bounded post-finish observations. Summary
state-change saves follow the complete observation. `ObjectiveExitTraceBuffer`
reserves initial/first-fault/terminal evidence within 16 entries; separate UTC,
frame, fixed, world, Run and Stage clocks avoid conflating time domains. Setup
resets controls per objective, teardown uses the existing exact subscriptions,
and read failures make only telemetry inert. No native method/input/state is
changed. `TeleporterExitTraceSourceContractFixture` checks the exact native API
and production buffer through the existing fixture producer. Android trace
acceptance remains pending; J641's APK contains this telemetry source.

`WorldCommerceSession` owns the typed ShrineUseEffect baseline and synchronous
native-purchase attribution counts from setup through final cleanup. Its inline
`NativeShrineEffectAttributionWitness` reports failure operands (baseline,
final, delta, aggregate and four concrete shrine callback counts). Those counts
share the existing session lifetime; they do not intercept native loads or claim
their caller. Cleanup still requires exact equality before releasing references;
a mismatch retains the existing recovery refusal.

For the explicit native-first-stage diagnostic only, this owner also owns an
inline `NativeShrineEffectOperationSnapshot`: one weak operation baseline before
the first boss-shrine observation, one post-purchase snapshot and one reserved
final-cleanup snapshot. Read-only locator/cache reflection records actual
operation/version/result identity and reference counts, current versus setup
legacy GUID, support-array index and native effect-catalog index. Locator/raw
location/cache/match/string limits and incomplete/error markers are explicit.
The report retains scalar strings only; the baseline retains weak references.
It adds no load, wait, acquire, release, profiler callback or per-frame polling.
Capture failures stay diagnostic and the strict refusal remains authoritative.
Post-event state is not proof of the native call's exact lookup or a rendered
effect. The existing `FirstStageDiagnosticGateFixture.cs` producer owns the
authored operation fixture: it runs twice, verifies shared-operation/count and
missing/error cases, then checks exact provider/locator/cache restoration.
The compiled formatter host contract preserves the ordinary failure prefix.

Native teardown restores the source cohort and borrowed tables before final
commerce reconciliation. `TeleporterWorldSession.Dispose` performs that
reconciliation while the baseline objective-support leases still exist, then
releases support. `IntegratedWorldSession` resumes its remaining cleanup afterward.
`test_native_commerce_release_order.py` compiles the actual two native branches
and support tail against the authored `native_commerce_release_order_host.cs`
ownership contracts, including refusal before baseline release.

Survivor combat output observation (authored source, J642):
`IntegratedWorldSession` owns a disposable `SurvivorCombatOutputObserver` beside
the skill observer; `r.world.survivorCombatOutputs` holds bounded scalar reports.
Setup requires the exact live server-mapped body/master and subscribes one stored
native damage delegate. Direct body damage, mapped projectile inflictors and
reciprocal owned summons remain separate attribution facts. A one-second sample
visits at most 4,096 server identities; scan truncation and sampled live counts
are explicit. Histories retain 32 damage facts and 64 distinct network IDs;
overflow observations and retained unique IDs are separate counts. Unity damage
time and world sampling time are separately labelled. Network-ID reuse and
short-lived outputs limit coverage; no skill slot is inferred from timing.
Each damage fact also records attacker/victim native catalog names from
`BodyCatalog.GetBodyName` at the event. These use the existing cached native
strings; missing bodies/indices remain explicit empty names. The unchanged
body/network indices and reciprocal ownership checks determine attribution.
Names help interpret a later exact index without reconstructing catalog order.
The exact-editor API/None fixture reports whether any positive native entry was
available; idle editor catalogs remain uninitialized. The existing first-stage
editor fixture source also owns `MageEarthShardsStaticConfigFixture`: exact
staged config/projectile GUID-path identity, native `ApplyStatic` after distinct
sentinels, and finally verified restoration of all captured mutable state fields.
It creates no Run/catalog/network and proves no device projectile output.
Portable tests execute
the authored helper against an authored catalog double.
Cleanup detaches before body/skill retirement and releases owner references.
An observer read failure records its first bounded error and makes only telemetry
inert. A pending unsubscribe retains its recovery handle for disposal/retry before
replacement; partial reports are never complete output evidence. The exact-editor
fixture checks native API, caps and fault/disposal contracts without native objects
or global event dispatch. This owner changes no gameplay, authority, stock or RNG.
For an explicit isolated-slot request only, the existing observer may arm up to
three one-second projectile-observation windows, with a 0.05-second cadence and
at most 60 extra scans per session. The inline pure
`TransientProjectileWindowSchedule` is owned/disposed with the observer;
`IntegratedWorldSession` resets its request cursor on setup/cleanup and arms a
window when its existing input owner issues a request. Normal runs retain the
one-second scan deadline. All scans reuse the same native server/owner/catalog
checks, 4,096-object bound and 64-record history. In-window baseline scans count
as observations without using the extra-scan budget. Reports separate request,
accepted/drop, scan/cap, expiry and maximum observed gap; these are partial after
an observer fault. A request window does not prove state entry, projectile
causality, complete transient coverage or per-slot damage. The extracted actual
timing policy has a compiled portable host contract.

`TeleportMaterialSession` also owns final overlay/material release.
`TeleportOverlayRegistryOwnership`, in the same authored file, reads the native
active registry prefix to resolve exact wrapper identity before public removal.
A remembered `managerIndex` alone cannot authorize removal. After tracked
overlays are retired and deferred destruction yields, the owner runs the public
native overlay update to prune destroyed-host entries, then requires the global
registry to be empty before releasing material resources. Live foreign overlays
remain intact and cause refusal. The owner neither clears nor replaces the
registry. `TeleportOverlayLifetimeHost` reproduces stale-index reuse and native
destroyed-host pruning in isolated exact-editor Play Mode; it restores only its
fixture-owned entries. Actual completed-session cleanup and restart pass in J609.

`./dev prototype --action session-cleanup-check` (current support action,
`scripts/lab/session_cleanup_check.py`) observes the existing first-stage loss
and restart flow with automatic diagnostic input and every gameplay debug
assist disabled. Optional `--target <base survivor>` selects the exact survivor;
the default remains Commando, and locked base choices are labelled diagnostic
overrides. Every current report must match that choice before any menu/restart
tap. It requires a genuine player death/result, native teleporter listener
retirement while the server is active, and live session 2 in the same process. It verifies the receipt-backed APK against its host artifact, freezes
profile counts, and refuses stale reports, runtime errors or departure from
Lakes. Setup preserves and removes only the owned report targets; teardown
preserves foreign selectors, verifies process termination and sleeps the display.
Raw evidence stays in validated `work/device/<serial>/experiments/session-cleanup/<attempt>/`.
UI-abandon startup waits at most 60 s from its first world-playing snapshot for
sampled positive health/maxHealth, ready/input evidence and the required guard.
Only then does its 60 s host interval start. Death/ending evidence stays fatal
through startup; any sampled interruption after the interval begins refuses.
The check cannot certify an unassisted run, permanent unlocks or a memory leak
fix. Host contracts live in `tests/test_session_cleanup_check.py`; J609 records
Android acceptance on the earlier J608 APK; the current candidate needs its own check.

`./dev prototype --action session-abandon-check` (current support action)
uses the same runner with an explicit separate ending contract. After at least
60 s of sampled ready, living first-stage play it taps only the reported
settings and end-run controls, requiring Unity/Android screen-grid agreement.
It observes the existing offline UI abandon flow, native listener/template
cleanup and a same-process restart. Explicit no-death/no-ending/no-result fields
and unchanged profile counts are required. Locked diagnostic targets may launch
directly; free targets require the ordinary menu. This action does not invoke
death, result or teardown methods and does not change difficulty/settings.
Free-target abandon also requires the returned session-2 menu and validates the
saved session-1 completion before tapping Start again. It requires the newly
reported settings screen dimensions in the installed APK;
older APKs refuse those taps. Genuine native loss remains the separate default
session-cleanup-check contract.

The host-only `HostMilestoneTiming` helper in the same runner records one-time
`time.monotonic()` offsets from `device.launch()` return. It marks observed
menu/world reports, returned UI commands, validated completed cleanup and the
existing healthy session-2 predicate. Missing milestones and out-of-order
interval endpoints remain null; abandon may observe the menu before validating
the completion report. `host_timing` is emitted in result/summary evidence only.
These measurements change no acceptance gate and are neither native CPU/FPS nor
proof that a warm batch executor exists.

Both cleanup actions accept the current optional `--skill-variants` JSON for
one base survivor, using the skill check's strict selector parser before device
access. The attempt-bound selector stays until runner finalization; a fresh
coordinator rereads it, so each session independently applies and verifies the
request. The runner distinguishes pre-mutation catalog metadata, effective
native loadout indices and the post-spawn setup snapshot, and requires the
sticky assisted marker. Setup snapshots are explicitly not continuous ability
observations. Original loss and UI-abandon remain separate contracts.

For APKs with combat-output instrumentation, the runner checks the first ready
healthy observer, completed-session detachment and fresh restarted attachment;
inert/error reports fail even after detachment. It waits for ready positive
health, diagnostic input and the Engineer guard before classifying startup.
Older absent instrumentation is explicitly unavailable, never a positive
observer lifecycle result. Host contracts remain in
`tests/test_session_cleanup_check.py`; this adds no runtime or profile writer.

`./dev prototype --action session-memory-check --expected-apk-sha256 <hash>`
(current support action, `scripts/lab/session_memory_check.py`) repeats the
ordinary Commando menu start, at least 60 s of ready Lakes play and the same UI
abandon five times by default, then stops at the next menu. Explicit `--sessions`
selects 3 to 32 sessions for a longer series without changing runtime gameplay.
Each completed
`movement-completed-session-<k>.json` must pass `abandon_contract` (reused through
an index-checked session-1 view) before the next start, and profile counts must
stay frozen. It collects the existing `SessionResourceBoundary` samples plus host
`dumpsys meminfo` TOTAL PSS at every menu and reports per-session slopes from
session 2 onward. It is an observation runner: it attributes no retaining root
and certifies no leak fix. It binds only an explicit owned APK hash, refuses a
`--target`, and keeps evidence under `work/device/<serial>/experiments/session-memory/`.
Host contracts: `tests/test_session_memory_check.py`.

`session-memory-root-check` is the same runner with the launch selector's
`diagnosticCompletedRootWalkSession` set to the final menu's session index.
`SessionResourceBoundary` reads only that value (and the attempt) from the
selector itself. At that one `before-presentation` sample, after every measured
session and outside live gameplay, it runs the Unity-free
`CompletedSessionRootWalk` over static fields of every loaded type plus live
`MonoBehaviour`/`ScriptableObject` objects as named roots. The walk is a bounded
(1,000,000 objects) breadth-first, read-only field/array/delegate-target walk
that skips weak references and reflection metadata. It records up to 16
shortest paths to completed probes/reports, its node count, truncation and read
failures in the sample. Reading an uninitialized static field runs that type's
static constructor; J773 saw this register an original achievement callback
that the progression owner then refused. The walk therefore runs only at the
final menu and stays off by default. Host contract:
`tests/test_completed_session_root_walk.py` compiles the production block with
the pinned Mono/Roslyn.

`ReclaimCompletedSessionResources` also owns one adapted Android lifecycle
step (J775). Original `BaseAI.Awake` subscribes to the static
`GlobalEventManager.onCharacterDepossessed` and never unsubscribes, so every
spawned AI stays reachable. After the world is cleaned, with no Run or network,
the owner removes only entries whose `BaseAI` Unity has already destroyed,
through the Unity-free `CompletedSessionRootWalk.RemoveTargets`. It records the
count on the `completed-before-reclaim` sample. Live subscribers and accumulation
within one run are unchanged. J775 measured no managed-memory effect from it.
The same step (J787) removes Unity-destroyed entries from the original static
`ItemDisplayRuleSet.instancesList`, `PickupDropTable.instancesList` and
`TeamComponent.indicatorSetupQueue`. The first two keep assets from each
session's unloaded whole-catalog bundle. The named indicator owner now restores
source-enabled root components and services the original queue while the native
application dispatcher is inactive; native lifecycle owns initialization.
Completed-session pruning remains available for destroyed queue entries.
Per-registry removed/remaining counts are recorded; actual indicator rendering
remains a device gate (J804).
The final-menu walk also records a census: the 60 most frequent reachable
types with object counts and primitive-array bytes (`rootWalkCensus`).

`AndroidProfileSession` also owns the exact native timed-chest `Opening.onOpened`
subscription. That event has no sender or chest identity; it is recorded as a
global native observation for the sole owned offline profile. Setup captures
the exact Run/body/master and stable Android store/save-system owners. Each
callback resolves the current profile after prior transactions may replace its
object, validates the current owner/profile identities, then uses the existing
unassisted detached native achievement transaction. Teardown removes the exact
delegate and clears captures before releasing profile state. Assisted attempts
remain excluded; positive ordinary event delivery and saved awards are runtime
gates. `AndroidProgressionHost` exercises complete event metadata, detached
native grant/duplicate behavior and profile replacement in an isolated fixture,
without synthesizing the source event.

`scripts/lab/source_identity_metadata.py` owns the source identity/toggle
metadata read by `SourceStageIdentityLifecycle`. Existing
`whole_catalog.generate_build_maps` emits it into `WholeStageContexts.json`
from the exact staged `SourceScenes` bytes and their generated candidate
receipt; mismatched hashes refuse. It retains nonzero network scene IDs,
source component/object IDs, ordered group ranges, full slot widths and nulls.
Runtime bindings resolve exact object references through an ordered Transform
path under a uniquely named/shaped root, validating names, sibling counts and
child indices. Identical same-name/root-shape ambiguity refuses. Static
metadata for other Base scenes does not extend the runtime scene gate.

The early `original_stage_contexts` policy call remains independent of staged
source scenes and receipts. R5 policy paths explicitly omit identity metadata;
the nonempty post-R6 R7 map generation requires it, then R8 stages the consumer
and `SourceIdentityTransformParityFixture`. The fixture uses a disposable
inactive preview hierarchy, verifies Python/C# Unicode hashing and exact
ordered path resolution, and destroys/closes that hierarchy in `finally`.
No native Run, networking or real source scene is started by the fixture.
Host contracts: `test_source_identity_metadata.py`,
`test_source_identity_context_phase.py`, `test_source_identity_transform_parity.py`.

The first-stage source lifecycle diagnostic retains the full native stage deck,
source toggle references and original Run RNG. It omits the older temporary
Beetle/CombatDirector fixture, arms population observers before native Start,
and records only genuine native server Stage-begin. The offline path has no
local NetworkUser, so server-begin does not prove Stage.Start's client
continuation or `onStageStartGlobal`. Unknown/platform global scene-change
subscribers refuse; no event queue is cleared to force progress.

`WholeInteractableSession` captures each source table binding's exact component,
GameObject, scene, label and instance IDs before changing its borrowed field.
`NativeSourceBindingRestorePolicy` in the same owner file requires the bound,
valid, loaded, active scene. A live component must still reference the captured
live GameObject in that scene. For a destroyed component, the captured GameObject
must independently be Unity-fake-null with both managed references retained;
bind-time validation must identify one of the four exact mutable native public
PickupDropTable fields. The existing captured lease then restores that managed
field and still refuses foreign replacements. A component-only destruction with
a live GameObject/child consumer refuses. No field restoration is skipped and
providers remain held until all leases restore; failure retains recovery state.
`NativeSourceBindingWitnessFormatter` reports each predicate without dereferencing
dead wrappers. The portable policy/lease and formatting tests do not simulate
Unity destruction.

The existing editor fixture file also owns
`NativeSourceFieldFixture.WakeManagedFieldLeaseExactEditorFixture`: a disposable
inactive preview hierarchy exercises the production field schema and policy,
component-only destruction with a surviving child pickup consumer, full hierarchy
retirement, managed field restoration, idempotence and foreign replacement.
It restores before releasing temporary tables and closes the preview scene in
finally. It does not start gameplay or establish that native WakeSpawner ran.

Source identity retirement verifies the captured server mapping and current
ID mapping are absent after owned `UnSpawn`, then invokes native `Reset` for
the exact retained captured ID even when host-mode `OnNetworkDestroy` already
cleared `isServer`. Changed IDs/foreign remapping refuse; the postcondition
requires zero ID and cleared server/client flags before active-state restore.
No private identity state is assigned. `test_native_identity_reset.py` executes
the authored production rollback method against host-order HLAPI doubles;
actual native cleanup/restart remains a device gate.

`sourceStageLifecycleRecoveryRequired` keeps the exact nested iterator,
body/master, Run, server/client, scene and provider/catalog graph alive after
partial native acquisition or failed retirement. Destructive upstream finalizers
stop at that gate; an incomplete retained attempt is a failure. A narrow early
Director-prepare catch can conservatively retain recovery after restoring the
SceneDirector before observer disarm. Main-path safe abort disarms first; the
early edge is not represented as a successful safe abort. Native callback order,
placement, cleanup and failure recovery still require runtime evidence.

C# under `tools/` is formatted with `clang-format -i` using the repository's `.clang-format`
(J544). It never rewraps string literals or comments, so a correct reformat leaves each file
identical once whitespace is removed; check that before committing a reformat. CI does not
enforce it, because other clang-format versions format C# differently.

Host CI also runs Ruff (pinned in `tools/lab-requirements.txt`, configured in `ruff.toml`):
`ruff check` and `ruff format --check` on every Python file a change touches. `scripts/` and
`tests/` are ruff-formatted (J518); `ruff.toml` lists the rules still off and why.

`scripts/readme-actions.py` (support) generates the marked current-action table in
`docs/DEVELOPING.md` from `scripts/lab/actions.py`, preserving registry order and excluding
historical actions. Run it after changing registry names, status or help; host CI runs
`python scripts/readme-actions.py --check` beside the journal-index freshness check.
The script name stays stable after relocation from the player-facing README.
`tests/test_readme_actions.py` covers rendering, idempotence, freshness checks and
leaving the player landing page untouched.

## Source folders

`tools/unity/runtime/` groups authored sources by owner: `session` (including
`PortSession.cs`), `catalog`, `commerce`, `input`, `presentation`, `progression`,
`shaders`, `stage` and `world`. `tools/unity/experiments/` holds historical probes,
linker descriptors and `LabExperiments.cs` (still selected for the current player).
The detailed paths and status remain in [architecture-file-map.md](architecture-file-map.md).

`recipe/runtime-sources.json` contains paths relative to `tools/unity`. Every builder
stages sources by basename, preserving generated project paths and Unity-owned metadata.
The reader rejects duplicate basenames, including collisions with generated sources;
the strict staged C# membership and byte comparison checks remain in `build.py`.
`recipe/project-layout.json` owns those 92 authored script GUIDs and the 36 direct
package dependency pins, audited in `recipe/README.md`. `build.py` checks staged
`.meta` GUIDs and `Packages/manifest.json` dependencies after source validation on
the current whole-catalog build path, before cache lookup or editor invocation.
The check is read-only: it neither generates metadata nor installs packages;
existing staging retains ownership of those writes until the direct composer lands.
`recipe/runtime-config.json` records the 183 present public `SessionConfig` fields
(options and content identifiers; audit in `recipe/README.md`). `build.py` validates
them after layout validation, before cache lookup or editor invocation, without
writing the config. Extra staged keys remain allowed. The absent
`detailedVisualDiagnostics` field stays untracked until explicitly configured.
`recipe/content.json` records the 14 present public bundle-selection fields
(4,304 asset-path strings, including 4,184 `prefabAssets` entries; audit and complete
reader/writer inventory in `recipe/README.md`). `build.py` validates the work
`scene-probe-build.json` after runtime config with the same strict equality helper,
before cache lookup or editor invocation. Extra work keys remain allowed; the
validator never writes either input. At the start of both full and code-only
`whole_catalog.build_integration`, `build.generate_runtime_config(project)` and
`build.generate_content_recipe()` replace these files from the public recipes
before source validation or staging. They use sorted, two-space JSON plus a final
newline, preserve values/types/list order, and retain no extra keys. No later
current build step writes either file. Composition migration still writes its
intermediate configs before this entry point; those writes are superseded here.
The first build after this change must be a full `whole-catalog-build`: the runtime
resource is a payload input. See the [generation audit](../recipe/README.md#config-generation).

## File status

Every file in `tools/unity`, `tools/catalog` and `scripts/lab`, and every `prototype`
action, is classified with its staging site and a runtime call site in
[architecture-file-map.md](architecture-file-map.md). Totals:

| Area | Current | Support | Historical |
| --- | ---: | ---: | ---: |
| `tools/unity` + `tools/catalog` (135 files) | 94 | 26 | 15 |
| `scripts/lab` (43 modules) | 9 | 24 | 10 |
| Named `prototype` actions (177; default fallback excluded) | 12 | — | 165 |

Historical `tools/unity` files (not staged by any current builder; none exists in the
generated project): `AudioAssetProbe`, `CharacterMotorOrderProbe`,
`CollectionsRuntimeProbe`, `CommandoPosePreview`, `KinematicBatchProbe`,
`LoadingSceneProbe`, `MetadataDispatchProbe`, `ReferenceIdentityProbe`, `RoR2SliceProbe`,
`StartupSegmentProbe`, the three `RewiredTrial*` files, and `ControllerAddressLink.xml`
and `TeleporterTimelineLink.xml`. `ReconstructionProbe.cs` is support: `./dev
export-project` wires it into the exported project. Current whole-catalog C# source
membership is the audited `recipe/runtime-sources.json` selection, read by `build.py`
and staged by `whole_catalog.build_integration`. Its `stage_runtime_sources`
helper validates the selected source/metadata cohort before writing, then seeds
absent metadata from authored sidecars with matching fixed project-layout GUIDs.
Existing Unity-owned `.meta` files are retained. Intentional null-GUID sources
without sidecars retain first-import behavior. Source and metadata paths remain
player-only payload exceptions (J973).
`build.py` declares the three generated visual maps separately and rejects missing
authored sources or unlisted staged C# files. `test_runtime_sources.py` checks the
selection and its independence from generated-project history.

The current `scripts/lab` modules are `build`, `composition_migration`, `device`,
`graphics`, `health`, `inventory`, `main`, `recovery` and `whole_catalog` (helpers such as
`common` count as support); the
current `prototype` actions are the ten in
[whole-catalog-integration.md](whole-catalog-integration.md#reusable-fixes-and-commands)
plus `project-manifest-capture`, `project-manifest-compare`,
`asset-transforms-check` (owned by `asset_transforms`) and
`authored-additions-check` (owned by `authored_additions`), plus
`inherited-state-check` and `inherited-store-capture` (owned by `inherited_state`).

### Mercenary impact-effect adapter

`BodyCatalogSession.MercEvisImpactEffectLease` in `BodyCatalogBoundary.cs`
owns the Evis-only compatibility adapter. `EnemyRewardSession` requests it
only for the selected Mercenary teleporter-loop session. Setup clones the
shared swing visual under an inactive owner, preserves its native one-second
timer, adds a nonpooled EffectComponent and a lifetime marker, appends one
native EffectCatalog entry, then redirects the registered Evis projectile's
impact field. The shared GroundLight2 visual and baked catalog indices remain
unchanged. No projectile catalog entry is added.

`RestoreComposedEffects` checks exact catalog/field ownership and refuses live
projectile or marked effect references before restoring the Evis field,
registered indices, sound metadata, prior catalog and availability. It removes
only the adapter's cache entry and destroys its owner after restoration. A
refusal retains the lease for diagnosis. Setup failures use the same ownership
checks for rollback, including the ordinary non-Merc path. Deferred teleporter
support uses `RegisterComposedEffects` after initial setup; it preflights the
whole request and records each field mutation before writes. Teardown restores
the accumulated stack in reverse so definitions sharing a prefab component
recover the original index. Initial setup uses its separately scoped registration
path and the same reverse restoration rule.

`MercEvisImpactEffectExactEditorFixture.cs` is support code staged by
`whole_catalog.stage_build_sources` into `Assets/Editor`. Its public `Run()`
requires the pinned, compiled, idle editor with no network session or populated
EffectCatalog. It initializes Addressables through the public API with generated
empty test settings/catalog, then exercises the actual owner and native
SetEntries in three restored generations. The fixture tests later-registration
failure, default-path rollback, live-projectile refusal, source immutability,
and provider/cache restoration. Generated initialization files remain under
`work/tests/merc-evis-impact-effect/addressables-init/` for the initialized
locator's lifetime. This fixture does not prove device effect presentation.

The existing `shader_source.bind_hlsl` resource/interface binder preserves
measured non-output `noperspective SV_POSITION0` inputs. Other qualified
interfaces refuse until measured; this support alone selects no replacement
shader or runtime presentation behavior (J953).

The same binder admits only measured fixed-size non-builtin `float4` arrays
(J1002). Register reads must fit the native buffer; lengths, types, offsets and
array shapes are validated before output. Array declarations retain their
extent for the consuming wrapper to place after the variable name. Unknown
shapes refuse. This host support has no runtime state or teardown and does not
activate a replacement shader.

`scripts/lab/shader_outline.py` owns the current
`shader-outline-candidate --target outline-highlight` host action. Its fixed
public `recipe/shader-outline-candidate.json` binds the accepted catalog,
serialized object, four executable records, measured layouts, pass state and
authored helper/tool hashes. It generates only ignored local evidence beneath
`work/generated-shader-candidates/outline-highlight-r4/<input_id>/`; unchanged
inputs may reuse identical output, while drift refuses overwrite. R3 maps the
measured all-channel mask value 15 to ShaderLab `RGBA`; unmeasured numeric or
symbolic masks refuse. R4 refreshes the bounded-array helper pin while preserving
both R3 and R2 outputs; the generated shader bytes are unchanged. Vertex and
fragment interfaces remain distinct so the measured fragment-position
interpolation survives. It has no runtime setup or teardown. The optional
catalog consumer below stages this generated source; J965 qualifies the isolated
exact-editor Android bundle fixture. Android appearance remains a separate gate.

`scripts/lab/shader_ramp_fog.py` owns the source-bound single-pass
`shader-ramp-fog` and `shader-screen-damage` host actions. The first also accepts
`--target sobel-buffer` or `--target sobel-outline`; no target retains RampFog.
Each target uses its fixed public `recipe/shader-<target>-candidate.json`. Each validates the
accepted installation, exact native object/blob/program topology, measured
interfaces and tool/helper pins before publishing new ignored evidence.
The shared wrapper uses the validated native shader name and pass state;
it retains recovered definitions before their calling wrappers. No game
expressions or compiled programs are public inputs.

Current output roots are
`work/generated-shader-candidates/ramp-fog-r5/<input_id>/` and
`work/generated-shader-candidates/screen-damage-r1/<input_id>/`, plus
`work/generated-shader-candidates/{sobel-buffer,sobel-outline}-r1/<input_id>/`.
SobelBuffer retains its separate fragment parameter record; binding slots name
vertex/fragment stages independently of serialized record indices. Prior RampFog
outputs remain preserved. Native programs, layouts, independent disassembly,
byte roundtrips and source-immutability receipts accompany each candidate.
The producer has no runtime setup or teardown; the original PostProcessLayer
and effect renderer remain its consumers. Compilation and device appearance
are separate gates, as in the earlier J965 RampFog bundle fixture.

`scripts/lab/shader_translucent.py` owns the current host-only
`shader-translucent` action (J1003). Its fixed public
`recipe/shader-translucent-candidate.json` binds the accepted installation,
inventory, four source shader identities, pass counts, keyword axes and exact
authored/native tool pins. It imports the repository binder directly and writes
only new ignored evidence under
`work/generated-shader-candidates/translucent-camera-r2/<input_id>/`.
Input/tool drift, symlinked output roots, unknown metadata and colliding output
paths refuse before publication. The generator retains EfficientBlur's two
source passes/shared fragment and QuickDumbBlur's measured `FLIP_V` axis.
R2 refreshes the shared signature-helper receipt while retaining the four
shader identities and pass/keyword contracts. It has no runtime setup or
teardown. J1009 verifies isolated Android/Vulkan
compilation and cleanup. J1012 adds catalog consumption; J1017 installs the
complete six-row payload after a full catalog/player build. Android rendering
and matched PC appearance remain separate gates.

`whole_catalog.prepare_integration` owns the optional shader catalog override
(J966/J1012). The public `recipe/shader-catalog-overrides.json` is a default-off
exact identity allowlist for Outline Highlight, RampFog, the four Translucent
candidates, ScreenDamage and the SobelBuffer/SobelOutline pair. Ignored
`work/config/shader-catalog-overrides.json` explicitly
activates it for one accepted input. Before writing, staging validates all
current generator/recipe chains, candidate source/metadata receipts and original
catalog relationships. For Translucent, ScreenDamage and Sobel it validates the catalog
address GUID and distinct original exporter metadata GUID independently, plus source
path/object identity, pass count and keyword shape. Only generated shader bodies
replace their catalog files; existing `.meta` bytes stay identical. The attempt
receipt and project `.rebuild` mirror/marker bind the selector digest.
`catalog_rebuild` and `rebuild.compare` validate those exact exceptions and retain
ordinary provenance comparison elsewhere. Historical exact two-, six- and seven-row receipts
remain supported; current staging selects all nine rows and rejects partial
cohorts. Both current-project and destination staging persist the marker;
disabling an already-staged override refuses before
catalog writes and requires a clean destination. The generator owns candidate
creation; catalog staging owns setup and receipts; there is no runtime owner or
teardown. This changes content and requires a full bundle/player build, not a
code-only build. No Android appearance or visual parity is implied.

`scripts/lab/shader_postprocessing_bloom.py` owns the separately selected
Post Processing Bloom source batch and its source-camera CopyStd companion.
The fixed public `recipe/shader-postprocessing-bloom-candidate.json` pins Unity's
Post Processing 2.3.0 archive, license and nine-pass Bloom/two-pass CopyStd
contracts. This version is a compatible source reference, not an identification of the game's package
version. The ignored input-bound `work/config/postprocessing-bloom.json`
activates generation during whole-catalog preparation. The generator preserves
each source shader's metadata and its exact `PostProcessResources.bloom`
reference while replacing the one-pass exported placeholders with complete
shaders and transitive includes. CopyStd is limited to the exact resource of
the original Main Camera, whose enabled NaN-propagation guard requires pass 1.
This source incompatibility does not identify the caller of an unnamed runtime
Blit error. Upstream source stays under ignored `work/`; no Post Processing
runtime package is installed alongside the existing game
assembly. Catalog staging owns the batch receipt and drift checks; replay
comparison accepts only its recorded source exceptions. This is a build-time
owner with no runtime state or teardown. Isolated replay reads a previously
generated, hash-checked candidate and refuses to create it in live inputs.
It requires a full content/player
build; Android rendering and PC appearance remain separate gates.

`scripts/lab/shader_postprocessing_uber.py` owns a separate default-off Uber
shader batch for the exact `Main Camera` → `PostProcessResources_53.uber`
reference. It pins the accepted export's camera, resource, shader metadata and
`ppRunBase` Bloom/effect settings, then generates the official Post Processing
2.3.0 Uber shader, five AO/LUT compute programs, two AO/LUT graphics programs
and their 18-file HLSL closure from the locally pinned archive. The seven
additional programs use deterministic lab GUIDs in the existing loading scene's
Resources directory; original resource, compute assets and camera bytes stay
unchanged. Their original resource slots, kernel names and thread groups are
pinned in the recipe. `WholeCatalogBuild.ValidateSourceCameraPrograms` exercises
the actual imports and all 22 kernels in host initialization and full builds. That
archive is a compatible source reference, not proof of the game's shipped
package version. `PostProcessLayer.RenderBuiltins` selects pass 0 of the
three-pass source shader. The ignored
`work/config/postprocessing-uber.json` selector is independently input-bound;
the stage marker and receipt use a separate schema so existing Bloom/CopyStd
receipts remain readable. Preparation validates selectors before writing
catalog assets; stage preserves source `.meta`, resource and camera bytes and
refuses unknown candidate preimages. Catalog verification and rebuild
comparison replay only the exact receipt-bound files and includes. The normal
whole-catalog preparation path is the build owner. Generation has no runtime
state or teardown and makes no Android appearance claim.

Composition staging uses `StageIO.preflight` host/input gates, including for
the primary project. It does not query device storage or require an attached
device; installation owns the live storage checks.

## Shared worktree build ownership

`build.py` and `whole_catalog.py` own the lane-only iteration bundle-compression
option: the accepted chunked LZ4 default is unchanged; explicit uncompressed
builds use a separate exact-content/payload reuse ledger and iteration receipt.
`LabBuild.cs` selects the bundle option without changing the bundle map and logs
the bundle-phase boundaries. Normal anchors and frozen payloads remain separate;
an ordinary full build restores them after iteration. Setup/teardown and commands
are in [build lanes](build-lanes.md#iteration-bundle-compression).

`scripts/lab/build_lanes.py` owns current `./dev lane` creation/list/removal and
`LAB_LANE=NAME` build dispatch. Each detached checkout has an APFS clone of
prepared inputs, private writable editor/Gradle state, its own MCP port and a
persistent lock outside the removable tree. Creation snapshots under the
canonical mutex; later source selection/builds use only the lane lock. Creation
and every build/editor-open restage authored inputs from the selected checkout
through `build.restage_lane_sources`, `whole_catalog` runtime/editor staging,
`project_input_rebuild.stage_editor_inputs` for pinned baseline templates, and
the ordinary Android/audio owners. Extra C# is retired only after matching a
predecessor Git blob, with source/metadata hashes and a removal receipt. Unknown
or edited files refuse. `original_game_audio_build_hook.restage_authored_for_lane`
uses a small APFS reference clone to unwind camera/music without changing live
content; the producer selects the checkout's own generation.
`original_game_audio_stage` owns the three-DLL refresh and verified preimages in
`work/lane-authored-audio`; its pending receipt preserves full audio/overlay
bindings. Ordinary whole-catalog composition restores those preimages before
its existing overlay/audio staging. Lane teardown deletes this private state.
Generated content, game inputs and canonical staging are untouched. Completed
artifacts are cloned/verified into canonical cache without changing current-build
pointers. Teardown verifies process identities, stops private Gradle daemons
through their own registry, retains logs/receipts, removes
the checkout/work clone and preserves published artifacts. The pruner delegates
old stopped lane removal to this owner. Lane device access refuses before ADB;
device operations remain canonical. `BootstrapMcp` owns per-editor connection
and reload setup with a short global preference lease and restoration, while
`editor.py` checks the selected project through its lane endpoint. Setup and
teardown: [build lanes](build-lanes.md). Host ownership contracts are in
`test_build_lanes.py`; the actual asynchronous bootstrap executes against authored
preference/bridge doubles in `test_bootstrap_mcp.py`. Editor/package pins stay fixed.

`scripts/lab/shared_checkout_build.py` owns the current
`./dev prototype --action shared-catalog-code-build` (`--full` for content),
`shared-catalog-fast-build` and `shared-catalog-scripts-build` actions. A linked worker
checkout selects its clean committed HEAD in the clean primary checkout only
while holding the primary Unity mutex. The ordinary primary `./dev` host
preflight, source staging and selected ordinary build action run with that same
inherited lock.
The action copies no Unity project and performs no device operation. Its
private receipt under `work/coordination/shared-builds/` records the selected
commit and restoration outcome.

Teardown restores the original primary branch/commit after success or failure.
Unexpected edits or moved refs refuse restoration and preserve those files for
recovery; no stash, reset or authored-source patch is used. Workers must keep
primary source edits serialized with this operation. Run generated-output
pruning after the build, as for the ordinary build actions.

## Known structural debt

First verified against `af2e101`; status updated after J597. Each step was its own commit with
host tests, a zero-error exact-editor build and a device check.

Still open:

1. **The from-scratch rebuild is not yet equivalent or self-contained**
   ([rebuild-plan.md](rebuild-plan.md)). `./dev prototype --action rebuild-step` builds a
   separate destination in twelve host steps, each byte-identical to the working project
   (J567–J575); from a clean checkout of a gated build commit they reproduce 87,184 files
   (J750), and R9 there builds an APK that passed both device checks first time, with one
   differing gate file (BlueNoise drift) (J751); with that importer restored in the working
   project, R9 reports `equal: true` (J752). R9 builds it into an APK that passed both device checks (J582), but R9
   still reports it unequal. With the J584 Timeline pin and the J585 layered reimport, the J586
   rerun logs no new reimport error and passes both checks first time; its APK differs from the
   baseline only in `Hidden/Compositing` (open), the path-dependent Burst library and build
   metadata. The last differing gate file is `BlueNoise_R8_1.png.meta`, working-project drift (J592).
2. **The rebuild still has local inputs, and the working project is still migrated.** Since
   J597 the rebuild's R2 takes its selection from public recipes and reads no migration
   evidence (B1, B3–B6, B8), previous project or live pointer; R5 pins nothing and R7 pins one
   contract result. Since J725 R2–R4's catalog analysis is regenerated on the host in the
   destination. Left: 47 local analysis inputs read by recorded hash (R7's runtime contracts,
   still an editor export; 46 shader recovery inputs), 14 inherited-store files (12 from the editor-side `RecoveredHudBuilder`,
   FastDirector, the TMP mobile shader), and the local provenance map, which also selects
   membership (export copies, step cohorts), not only compares. The working project's own
   stage still runs the migration (`migration_inputs`); switching it is commit 9 of the
   [migration removal plan](migration-removal-plan.md).
3. **The session is still selected by id.** `Start` waits 8 s and picks the session from a
   string id; the playable spine runs `GameSession()` (J513) and the 116 historical cases live
   in `LabExperiments.cs`. Having `Start` call `GameSession` directly is the remaining step.
4. **Shared coordinator state.** 40 owners hold their subsystems' private state (J519–J540),
   but fields that several subsystems read (player, teleporter, results save system, HUD and
   menu roots, settings visibility and others) still live on `PortSession`. 23 boundary files
   have no private state worth an owner, and the three Moon files were deferred because
   neither standard check reaches them.
5. **Hard-coded run folders.** `scene_runtime.py:59`, `:515` and `:883`, and
   `input_migration.py:90` read fixed timestamped evidence folders (all in historical actions).
6. **Experiment drivers outside Git.** Broader gameplay runs still use about 89 untracked
   runner scripts in `work/experiments/whole-catalog/gameplay/`; the standard checks are
   tracked as `./dev check-baseline` and `--stage-exit` ([BASELINE.md](BASELINE.md)).
7. **Names.** Four staged diagnostic probes and six game-path shaders keep "Probe"/"Preview"
   names; renaming shaders changes names that code and materials look up, for no functional
   gain.

Resolved during the cleanup: dormant text patches on authored C# (J505/J506); build membership
by history (`recipe/runtime-sources.json`, J509, paths after the folder split J543); the 9
copies of the exception wrapper (`RunGuarded`, J511); config and report sharing one type
(`SessionConfig` J517, `SessionReport` J541); the coordinator name (`PortSession`, J542);
command sprawl (`scripts/lab/actions.py`, J512, README table generated J545); Python and C#
formatting (J518, J544); the flat `tools/unity` folder (J543).


### Opt-in native source view camera

`AndroidNativeSourceCameraRigOwner` is a view-only diagnostic gated by the existing
per-run native-skin request, whose default is false. It instantiates the accepted base
`Prefabs/Main Camera` asset (GUID `5aa1ab10a641d6f4e836da719179fa20`) and retains its
original `CameraRigController`, `SceneCamera`, PlayerBasic mode, selected body/team
target and callback owner. It creates no LocalUser or NetworkUser and changes no input,
HUD, projection, renderer visibility or materials. Alpha owns input and UI integration.
Its clone removes Unity AudioListeners. With original audio Ready and the native
engine initialized, it preserves the exact source default AkAudioListener and
co-located AkGameObj; default-off removes that pair. Their original Unity callbacks
own registration and removal. Lost readiness deactivates the staging root, and
disposal captures exact managed membership before and after deactivation.
`OriginalWwiseCameraListenerContract.cs` owns the serializable scalar observations;
the visual report refreshes after disposal and retains the object ID. The original
wrapper discards native Add/Remove results, so these remain explicitly unobserved.
Neither managed membership nor this camera establishes spatial playback. The marker
is compiled into RoR2.dll for exact-profile rig association; the runtime owner
remains off by default. When Console is absent, an activation scope guards only
the owned cloned `SceneCamera` from its Console-dependent graphics configuration;
the owner explicitly reports reduced fidelity using source prefab defaults.
`AndroidNativeSourceCameraPrerequisites.cs` resolves the original Sobel shader,
Outline Highlight, Vision Limit and TranslucentImage DownTent while the clone is
inactive; its exact SceneCamera activation scope is released in `finally`.
For the explicitly requested visual source-skin diagnostic, the owner may attach
`AndroidNativeSourceOutlinePassObservationPolicy` and sample the already-created
private Outline material once at the exact owned camera's `Camera.onPreRender`.
It does not subscribe to the Outline callback (which changes `NeedsHighlight`),
request highlights, create/replace a material or invoke a blit. Its scalar report
records only camera/component identity and existing material pass/shader metadata;
it does not show that pass 1 ran or explain an unknown-material log.
For the requested visual camera only, the same owner restores the original
graphics roles suppressed with the inactive application root. Setup reads
the stage supplied by NovaInputSession through NovaDiagnosticDisplay, then its
`RoR2Application.BehavioursToEnableDuringStartup`,
selects its `ppApplication_opt` and `ppDisabler_opt` global volumes and validates
the source camera's volume mask. It clones each setting into owned profiles and
child volumes, preserving serialized active/enabled flags, values and volume
priority/weight/layer. It clones the camera's resource object and both nested
program tables, binds only the seven qualified AO/LUT references and calls the
original public `PostProcessLayer.Init` before activation. Original resources
and the application stay unchanged/inactive; Console graphics preferences remain
unavailable and no brightness, gamma or exposure tuning is invented. The original PostProcessLayer,
SobelCommandBuffer and SobelOutlineRenderer retain rendering ownership.
One exact-camera post-render sample records blended Sobel/AO/grading settings,
resource binding and kernel readiness separately from appearance acceptance.
Disposal/disable unsubscribes, disables both owned volumes (native unregister)
and destroys only owned profiles/settings/resources. Audio-context-only cameras
do not create this presentation.
`test_source_sobel_lifecycle.py` executes production setup/sample/teardown with
inert fixtures, including original resource/profile immutability, preserved
inactive effects, missing programs/kernels and idempotent owned teardown.

The narrow catalog root set also retains RampFog for the original post-process
renderer. `whole_catalog.py` validates each exact address key, typed location and
accepted source conversion; `WholeCatalogBuild.cs` verifies its bundle owner and
built bundle before emitting the runtime catalog. Adding a root requires full
catalog generation; a code-only build reuses the previous payload. Discovery is
separate from supported Android shader programs and pass behavior. The bound marker pumps the original
private `EarlyUpdate` only for this owned null-viewer rig while the application
owner is inactive. Awake attempts binding once; the existing pump retries an
absent delegate only after the same exact ownership/readiness guard passes.
Successful binding is reused, and the original callback owns target/context
assignment. It tracks real target/context readiness before installing or
removing the override; lost context deactivates and destroys only the owned
staging root. These are source dependencies and lifecycle contracts only;
bundle/Unity/runtime readiness remains unproven.

The existing source-skin visual snapshot reads its owned camera marker's binding,
delegate, pump count and native update gates at the existing report cadence.
Optional field resolution is independent of camera admission. Typed known flags
and bounded errors retain unavailable observations as unknown; capture invokes
no callback and does not change camera or target state.

For ordinary requested audio, `IntegratedWorldSession` queues its audio-only
camera request during world preparation. `ObserveIntegratedWorld` consumes it
once at the first exact-owned-body playing update, after the preparation
coroutine completes. The original owner starts the same five-second admission
window there; opt-in, visual-diagnostic exclusion and source readiness gates are
unchanged. World cleanup cancels pending creation before ordinary owner release,
without claiming an uncreated context was released. The production schedule and
cleanup helper execute in `test_deferred_audio_camera_creation.py` (J1011).

For ordinary requested audio, the same owner retains bounded first/latest
admission inputs in `AndroidNativeAudioCameraAdmissionEvidence` (J1005).
`IntegratedWorldBoundary` copies this scalar-only DTO into its world report
during observation and on both sides of owned release, so retirement cannot
erase the earlier false operand. Each sample resets known/value pairs before
early returns. Cached music fields retain their source timestamp and refresh
flag at the existing 0.5 s snapshot cadence. Timing projections are finite with
explicit validity flags; raw source values still feed the unchanged gates.
The DTO retains no Unity objects and is released with its world report.
`test_camera_admission_evidence.py` compiles/runs the pure production contract
with pinned Unity Mono/Roslyn, skipping when those tools are unavailable. These
observations establish neither readiness nor audio/rendering acceptance.
J1006 verifies the latest sample on Android but finds that its recursively
typed first-sample field is absent from JSON despite metadata retention.
J1030 confirms that omission using the imported production report types.
J1032 moves the 141 existing scalars into serializable
`AndroidNativeAudioCameraAdmissionScalars`, preserving the evidence type's full
name and fields. Its concrete first-sample DTO inherits the same scalar schema
and has no further sample edge. The existing owner snapshots it once through
`CopyAsFirstSample`; report copies independently retain that bounded sample and
sanitize floats without changing readiness or observation cadence.
`tests/fixtures/CameraAdmissionJsonExactEditorFixture.cs` is an optional
exact-editor fixture, outside the player source selection. Under the shared
editor mutex, stage it temporarily as an Editor source after recipe-driven
runtime staging/import, invoke its `Run` method from `Assembly-CSharp-Editor`,
preserve its JSON, then remove only that owned fixture and generated metadata
before releasing the editor. It directly checks the actual five production
report/DTO types in `Assembly-CSharp`; it loads no scene and enters no Play Mode.
J1032 passes zero/one/two-sample serialization and raw JSON checks in the pinned
editor. Android report serialization remains a separate device gate.

`AndroidNativeSourceSkinLifecycle` also owns one cached render-evidence snapshot
at the first ready selected-skin/camera observation. It records at most 12 camera
records and 32 renderer records, including camera clear/depth/clip/mask settings
and eight-corner bounds projected through the exact owned camera. Camera counts
above capacity, count races and getter failures retain an explicitly incomplete
owned-camera observation. Non-finite projections remain unknown. Material names
sample only the existing first shared material and shader, bounded to 96
characters; total slots and later names remain unknown. No full material-array
query is introduced. The snapshot contains scalar/string data, keeps its original
frame/realtime through later reports and survives disposal in the final report;
it retains no Unity objects. It changes no rendering state and does not establish
that a later screenshot represents its captured frame. The existing lifecycle
host fixture checks these limits, and `Unity2021CameraApiCompile.cs` checks the
pinned editor API without connecting to an editor.

The current whole-catalog path restores only an exact prior camera stage result
to its guarded 3124, 1034 or 6f96 preimage, runs the original-audio producer,
then inserts the source-output observer after the exact 6f96 result when selected,
and applies the camera producer to that immediate result. Destination R8/R9 rebuilds
unwind an owned prior camera result and retain their existing build route.
The active exact profiles are 3124/API 107 to 494ba9, 1034/API d540 to 83513f,
PointSound game 6f96 with either d540 or 1ced to 0da94a, and its observed-music
27340 intermediate with either API to 4bd3b2. The PointSound route consumes
its exact 165-row audio stage receipt for either explicit passive-PCM state;
camera staging does not enable the PCM diagnostic. Arbitrary API/game pairs
refuse; the 793 API is restore-only. Historical outputs, including failed
41b66, require matching camera/audio receipts and preimage bytes for restoration.
The previous d5fc52/e4aeeb/2ae5d9/a2054 outputs remain restore-only under their
exact input/API/profile tuple and existing receipt/preimage checks.
The marker copier preserves exception handlers and maps their types and instruction
boundaries. Its independent verifier receives the compiled source helper and
compares the copied handler table before accepting output; a removed-handler
mutant checks this boundary. Cecil reference resolution is
materialized from the current project plugin DLLs and the exact pinned Unity engine
modules/Mono BCL. Its receipt is a host type-resolution input, not the full player
linker/IL2CPP closure or an APK/runtime acceptance record.


## LightningStake source-call observer

`runtime/world/LightningStakeSourceCallObserver.cs` owns opt-in bounded
pre-projectile snapshots. `PortSession` validates the selector before setup and
accepts only the two existing Nova source-selected integrated-world routes with
a selected survivor. `IntegratedWorldSession` creates the observer after the
world report exists, saves changed counts through its existing observation
cadence, and detaches the exact bridge delegate during teardown. An ownership
conflict marks session failure while remaining world cleanup continues.
The Cecil producer inserts a default-off branch immediately before the original
projectile call, preserving its receiver, source struct local and original
call. The observer stores at most eight scalar-only rows; it retains no game
objects and changes no projectile operands. Producer, music-return observer
and native-camera profiles bind the resulting managed chain separately.
`DamageInfo.force` is observed as an invariant vector triplet string with a
separate finite flag; projectile force remains the source scalar. The host
contract optionally compiles this owner against the exact current game/Unity
assemblies with synthetic game types disabled (J974).
Historical exact profiles remain available. This diagnostic identifies source
operands; it is not a projectile repair or gameplay acceptance.


### Original audio source camera context candidate

`IntegratedWorldSession` owns setup, reporting and release of the non-rendering
original-audio mode in `AndroidNativeSourceCameraRigOwner` (J988). Selected ready
audio uses the original Main Camera prefab and exact source listener; unrequested
audio and the explicit source-view diagnostic do not enter this mode. The rig
must be sole index zero, target the selected body and supply a fresh source
MusicController observation under a bounded readiness wait. The lifecycle
contract in `AndroidNativeSourceCameraRigContract.cs` separates waiting,
admission and retirement. Invalid context retires only its owned staging root.
J998 allows only an active audio-only rig with an initially unset mode to wait
for original Start initialization. Finite clock checks and a five-second
initial-admission deadline bound both mode and context readiness. It never
assigns the source mode; inactive/foreign state, post-ready loss and invalid
clocks retire the owner. Reports distinguish sampled activity/mode values from
known/unknown flags. The separate visual diagnostic retains its immediate
mode gate.

The source Camera stays disabled with no pose camera or provider override.
Original global camera/spectation/listener callbacks remain active and may
initialize the source global damage-number manager. The owner observes that
manager without acquiring or destroying it. World cleanup observes exact owned
root inactivity and managed listener removal, restores the scene camera pointer
and separately records a deferred destroy request; actual destruction remains
unobserved. Native listener outcome, spatial correctness and audibility remain
separate gates. J996 builds this candidate and passes both standard controls,
but its context retires before readiness and a source-prefab shader lookup fails. These remain
separate qualification gates. J997 makes the source TranslucentImageSource
Start dependency set explicit in the catalog roots and preactivation checks:
QuickDumbBlur, DownTent, EfficientBlur and FillCrop. The existing exact typed
location/conversion and built-bundle ownership checks cover all four. J997
restores lookup dependencies from placeholder exports; J1012 adds the recovered
blur/crop sources through the six-row catalog consumer. J1017 installs that
payload and separately verifies bounded camera readiness. Rendering, native
listener outcome and audible playback remain unqualified.


## Scripted multi-touch device input

Current `./dev prototype --action touch-gesture --target REQUEST.json` uses
`scripts/lab/touch_gesture.py` and authored
`tools/android-touch-gesture/LabTouchGesture.java`. The bundled SDK compiles a
content-addressed local DEX. Requests bind the existing owned APK hash, observed
PID and viewport; stale processes and foreign focused windows on display 0 refuse before
deployment. Android 13's `InputManager.injectInputEvent(event, mode, targetUid)`
confines every motion event to the owned app UID under ordinary adb shell
permission. Unavailable targeted injection refuses; there is no global-input
fallback or permission/hidden-API-policy change.

The source knowledge is the pinned Android 13
[InputManager](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/hardware/input/InputManager.java)
and the public [MotionEvent](https://developer.android.com/reference/android/view/MotionEvent)
pointer-ID/action contract; no platform implementation is copied. Each gesture
is bounded to 128 steps/30 s of waits, cancels a final hold and removes its
unique temporary device DEX/request files. A dispatch failure stops only the
still-matching owned game process. Success leaves the session/display running.
The driver observes only the owned UID's foreground process state through the
normal shell API. Leaving that state ends the pointer stream with
`termination: focus-lost`, before display sleep; completed steps report
`termination: steps-complete`. It sends no stale pointer event to a background
window. The caller checks termination and verifies native focus release/resume
separately.
Receipts and raw motion evidence stay ignored. This verifies software delivery;
it never qualifies physical buttons, a touchscreen digitizer or normal play.
