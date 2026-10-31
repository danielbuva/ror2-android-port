# Build recipes

## Original assembly placement audit (R1, 2026-10-18)

`original-assemblies.json` records only source/project identities, source SHA-256,
GUIDs and importer parameters for 49 DLLs. All sources, including SimpleJSON,
are the user's accepted installation's Managed files; no package fallback is used.
The cohort is 45 unchanged original DLLs, SimpleJSON, and the three J563 originals
before transformation. No DLL bytes, game implementation, serialized game asset
bodies, private paths or installation/device identifiers are included.
`templates/original-assembly.meta` is the common authored Unity PluginImporter
schema, with per-DLL GUID, timestamp and execution-order parameters. Its fixed
platform flags and validation settings preserve current import behavior.

Read-only inspection verified all 49 source hashes and all 49 generated importer
byte streams against the local current project. R1 applies the existing pinned
J563 transformation recipe on top of the originals and gates all 98 final output
hashes/sizes against the local provenance map before placement. Real-data step
execution and its 98-path byte comparison remain an operator action; synthetic
fixtures exercise the coordinator and its failure boundaries.

Prior art: reviewed `docs/community-prior-art.md` and pinned ThunderKit
`Editor/Addressable/Config/ImportAddressableCatalog.cs` at
`95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a`. Its `File.Copy` technique retains
source artifact bytes but does not initialize Android assembly importers or
prove transformations. R1 therefore preserves installation bytes by identity,
generates importer settings explicitly, and reuses J563 rather than introducing
new assembly transforms. No community implementation was copied.

## Recipe boundaries

Tracked, audited inputs that describe how the lab turns a legitimate game installation into
the Android build: authored transformations, configuration and reproducible build steps. The
goal is a build that needs only this repository, the documented toolchain and the user's own
installation, never the private history under `work/`.

What belongs here, and what does not:

- **Tracked:** independently authored transformations, selections and configuration;
  identifiers and hashes needed to apply them; measured mappings between public
  identities (for example Unity package GUIDs).
- **Tracked when needed (user decision, 2026-10-17):** the minimum game-derived identifiers and
  relationships needed to locate, transform and reconstruct content from the user's own
  installation, such as ordinary asset paths, GUIDs, catalog names and keys. A recipe must
  enable local reconstruction, never substitute for owning the game: it must not reproduce
  protected content or circumvent access controls.
- **Never tracked:** generated game-derived content (assets, decompiled source, bundles,
  catalogs), private configuration (`work/config/local.json`, device or storage
  identifiers, home paths) and protected third-party material.
- Readers of game-input-derived recipes stay input-gated: they check the recipe's
  `input_id` (and source hashes where recorded) against the accepted input before using it.
  Repository-authored source selections are independent of the game input.

Before adding a file, audit it for provenance, privacy, licensing and sensitive contents,
record the result below, and run `python3 scripts/audit-public.py`. Where a generator can
produce the file from the input, prefer tracking the generator.

## Audit record

`owner-j850-code.json` additionally names the 69 legitimate debug-symbol
companions required by the fixed target's managed closure. These are SDK or
freshly produced package/gameplay PDB inputs, kept private and verified before
and after stripping. No symbol bytes, protected implementation, device identity
or private path is recorded. Their presence affects stripped PE sizes and the
unchanged SDK converter's size-based assembly ordering. Manual provenance,
privacy, licensing and sensitive-content review: 2026-10-24. This extends the
existing source-only target recipe; accepted metadata is used for comparison.


J1087 refreshes only the reviewed authored world-owner source hash and its
audio-cohort manifest binding after native egg-range measurement changes.
No input game hash, gameplay value, asset content or ownership gate changes.
Manual provenance/privacy/licensing review: 2026-10-24.

The requested-audio source-scene transformation preserves original Wwise/RTPC
blocks from the owner's accepted local export through the existing generator.
The public change contains authored selection/lifecycle logic and synthetic
contracts only; no serialized scene body, event payload, bank or middleware
implementation is included. Default-off transformation and source hierarchy
ownership remain intact. Pinned R2API.Sound bank initialization/lifetime knowledge
informs admission, without copying its implementation or adding another native
engine owner. Manual provenance/privacy/licensing review: 2026-10-24. Generated
scenes, receipts and raw device evidence remain ignored.

`owner-uncompressed-textures.json` selects original bundle/member/object and
pixel extents, field bounds, destination identities/layout and verification
hashes. Pixel operations are copying original bytes, standard BC1 top-mip
decoding to RGB, fixed cardinal Manhattan source-coordinate dilation, and
quality-90 JPEG roundtripping through public stb/IJG source tools. Destination
names, inline/stream placement and generic
format/alpha/usage settings are serialization/import metadata. No pixel array,
palette, target byte patch/frame, image, codec implementation or target float
literal is included. Every pixel is copied or calculated from original PC
data. The successor includes the 38 dilation and five JPEG cases formerly
excluded; complete host and Android replays pass. These
minimum identifiers/relationships do not replace ownership or authentication.
Manual provenance, privacy, licensing and sensitive-content review: 2026-10-24.
Pinned UnityPy 1.25.3 field/resource observations and Microsoft's public BC1
format documentation inform the authored reader/decoder. The public
[jump-flooding paper](https://www.comp.nus.edu.sg/~tants/jfa/i3d06-submitted.pdf)
describes coordinate propagation; bounded exact-SDK observations and original
pixel comparisons identify the fixed metric/pass/tie configuration. No native
SDK implementation, game pixels or target-fed coordinate/color mapping is
copied. Public JPEG dependencies are acquired unchanged under their retained
IJG and stb terms, separately from this metadata recipe. Discovery, generated packs and raw evidence remain
ignored. This audit does not qualify complete bundles or an owner installation.
J1079 records the complete host/phone cohort, public-source Android codec build
and controls; J1076 preserves the preceding bounded result.

`owner-avatars.json` contains original bundle/member/object identities, hashes,
source body and table extents, destination identities/hashes and permutations
of original hash/string table entries. The 56 permutations describe incidental
serialization order; no bone path/string, pose, rig, geometry, target float,
byte patch or compressed frame is included. The other 172 records are copied
unchanged from the owner's input. Every generated byte comes from original PC
bundles. This minimum identity/layout metadata does not replace owning the game
or assert entitlement. Manual provenance, privacy, licensing and sensitive
content review: 2026-10-24. Pinned UnityPy 1.25.3 type-tree observations informed
field boundaries; no upstream implementation or protected content was copied.
Raw discovery, original bodies and generated packs remain ignored. J1075 owns
qualification and limits.

`owner-meshes.json` selects original bundle hashes, embedded member/object
identities and source vertex-resource extents, then names accepted destination
identities, sizes and verification hashes. Its only operations are authored
import settings, cache removal, minimal name/reference relocation, stream
inlining and float normal/tangent conversion. It contains no vertex/index
arrays, collision data, compressed target frames, arbitrary byte patches or
target float literals. Source content is required for every generated mesh.
The two unresolved tangent/importer records are explicitly excluded. The
minimum asset identifiers and relationships locate/reconstruct the owner's
content under the existing recipe boundary; they do not establish ownership.
Manual provenance, privacy, licensing and sensitive-content review: 2026-10-24.
Format knowledge was checked against pinned UnityPy 1.25.3 and the upstream
LZ4 block specification; no upstream implementation, game data or proprietary
SDK code was copied. Generated packs and raw discovery/device evidence remain
ignored. Qualification and limits are recorded in J1070.

`shader-postprocessing-bloom-candidate.json` pins a default-off, input-bound
replacement of the exported one-pass Bloom placeholders and the exact original
Main Camera's CopyStd placeholder using official Unity Post Processing 2.3.0
nine-pass Bloom and two-pass CopyStd sources. The public recipe and authored
generator contain source selectors, package/license hashes and reference/pass
relationships only. The archive, shader/include implementation and generated
project files stay ignored. The existing game runtime assembly is retained;
the package is used as a compatible source reference, not asserted to be the
game's original package version. No proprietary game body, private path,
account/device data or credential is added. Manual provenance/privacy review:
2026-10-23. The local archive retains its Unity Companion License notice;
runtime and visual acceptance require their own evidence.

`shader-postprocessing-uber-candidate.json` pins the exact accepted Main Camera
resource field, source Uber placeholder, run profile settings, and official
Post Processing 2.3.0 archive/license/source hashes. The shader source declares
three passes and the accepted caller selects pass 0; generation also pins the
shader closure and preserves each source asset's `.meta`, resource, and camera
bytes. The same recipe now binds five AO/LUT compute and two AO/LUT graphics
programs to the original resource fields, asset identities and 22 kernel/thread
group contracts. These use new deterministic lab GUIDs under the loading scene's
Resources directory. No original program body, profile values or code is tracked;
only the minimum reconstruction identities and compatibility contracts are public.
The archive and generated source
remain local under the Unity Companion License. This package is a compatible
source reference, not a claim about the game's shipped package version. The
default-off activation and separate receipt are explicit; no Android or PC
visual parity is claimed. Manual provenance/privacy review: 2026-10-24.

| File | Replaces | Provenance | Privacy and licensing | Readers |
| --- | --- | --- | --- | --- |
| `owner-objective-ui-objects.json` | Private objective-UI bundle | Original object/type selectors, checked pointers, Sprite importer/crop relationships, produced texture profile and rooted container preloads. | No content body, type-tree/hash template, pixels, geometry or scalar override; audit below, 2026-10-25. | Existing `object_produce.py`; J1120 host qualification, phone gate open. |
| `owner-teleporter-indicator-objects.json` | Private teleporter-indicator bundle | Original selectors, Sprite relationships, produced RGBA/Alpha8 profiles, dummy-material keyword policy and rooted container preloads. | No content/type/pixel/keyword literals or scalar patches; audit below, 2026-10-25. | Existing `object_produce.py`; J1120 host qualification, phone gate open. |
| `owner-generic-pickup-objects.json` | Private generic-pickup bundle | Original rooted object/type selectors, checked PPtrs, one omitted component identity, Sprite/texture profiles and container relationships. | No content/type/pixel/template or scalar patches; audit below, 2026-10-25. | Existing `object_produce.py`; J1120 host qualification, phone gate open. |
| `owner-enemy-reward-objects.json` | Private enemy-reward bundle | Original object/script/behaviour selectors, pinned SDK base-schema selector, checked PPtrs, component omissions and rooted container relationships. | No body, type tree/hash or scalar template; audit below, 2026-10-25. | Existing `object_produce.py`; complete host and phone qualification tracked separately. |
| `owner-villagenight-objects.json` | Private Village Night streamed scene | Original object/type selectors, checked PPtr/component relationships, scene/member identities and source mesh profile. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1134 host exact, phone open. |
| `owner-helminthroost-objects.json` | Private Helminth Roost streamed scene | Original object/type selectors, checked PPtr/component relationships, scene/member identities and source mesh profile. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1135 host exact, phone open. |
| `owner-habitatfall-objects.json` | Private habitatfall streamed scene | Original object/type selectors, checked scene/component/PPtr relationships and existing source mesh/cube pack selectors. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1138 host exact, phone open. |
| `owner-habitat-objects.json` | Private habitat streamed scene | Original object/type selectors, checked scene/component/PPtr relationships and existing source mesh/cube pack selectors. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1138 host exact, phone open. |
| `owner-wispgraveyard-objects.json` | Private Wispgraveyard reduced diagnostic scene | Original object/type selectors, checked export component omissions, scene/member/PPtr relationships and qualified mesh profile. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1142 host exact, phone open. |
| `owner-itskymeadow-objects.json` | Private Sky Meadow scene | Original selectors, checked SceneInfo component/occlusion-array/PPtr policies, Sprite relationships, SDK schema and qualified mesh/texture profiles. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1145 host exact, phone open. |
| `owner-solusweb-objects.json` | Private Solusweb scene | Original selectors, checked SceneInfo/bank/final CharacterMaster field policies, original preload GameObject membership and qualified mesh profile. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1145 host exact, phone open. |
| `owner-itancientloft-objects.json` | Private Ancient Loft scene | Original selectors, checked SceneInfo/occlusion-array/PPtr policies, current-input Sprite GUID relationships, SDK schema and qualified mesh/texture profiles. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1145 host exact, phone open. |
| `owner-ai-test-objects.json` | Private AI Test scene | Original selectors, checked CharacterMaster body/schema omission, source Sprite identities, SDK schema and qualified mesh/texture profiles. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1150 host exact, phone open. |
| `owner-testscene-objects.json` | Private Testscene scene | Original selectors, checked CharacterMaster body/schema omission, source Sprite identities, original preload membership, SDK schema and qualified mesh/texture profiles. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1150 host exact, phone open. |
| `owner-windows-shaders.json` | Original Windows comparison payload | Current original bundle path, length and integrity hash for the existing unchanged-file copy operation. | Provenance/privacy/licensing audit below, 2026-10-25; no programs or historical reconstruction input. | Existing `object_produce.py`; current host drift-explained, phone open. |
| `owner-barrier-objects.json` | Retained Barrier payload | Original body/type selectors, checked source pointers, named legacy import policies and independently produced media/Shader pins. | Provenance/privacy/licensing audit below, 2026-10-25; no protected body, tree or media template. | Existing `object_produce.py`; host exact, phone open. |
| `owner-goldshores-spine-objects.json` | Goldshores reduced spine payload | Current original object/type selectors, actual-schema PPtr relationships, qualified media and source Shader profiles. | Provenance/privacy/licensing audit below, 2026-10-25; no body/tree/media/program template. | Existing `object_produce.py`; complete host qualification, phone open. |
| `owner-goldshores-source-objects.json` | Goldshores source-scene payload | Current original object/type selectors, actual-schema PPtr relationships, qualified media and source Shader profiles. | Provenance/privacy/licensing audit below, 2026-10-25; no body/tree/media/program template. | Existing `object_produce.py`; complete host qualification, phone open. |
| `owner-goldshores-objects.json` | Goldshores whole-scene payload | Current original object/type selectors, actual-schema PPtr relationships, qualified media and source Shader profiles. | Provenance/privacy/licensing audit below, 2026-10-25; no body/tree/media/program template. | Existing `object_produce.py`; complete host qualification, phone open. |
| `owner-barrier-shaders.json` | Barrier source Shader records | Current original Shader selector, pinned public template revision, supplied SDK33 source metadata and SDK45 compiler identities, source filename and destination relationships. | Provenance/privacy/licensing audit below, 2026-10-25; no programs, pass keys or accepted tables. | `payload_shader_records.py`; bounded two-record host proof, phone open. |
| `owner-rootjungle-postprocess-shaders.json` | Rootjungle post-processing Shader records | Current original forms, source filenames, pinned public templates and acquired SDK45 context; shared record extents for two scene variants. | Provenance/privacy/licensing audit below, 2026-10-25; no protected source, programs or target tables. | Existing `payload_shader_records.py`; 24 host records exact, phone open. |
| `owner-rootjungle-spine-standard-shaders.json` | Root spine Standard | Current original Material/Shader/scene selectors, SDK45 source/compiler pins and destination relationships. | Provenance/privacy/licensing audit below, 2026-10-25; no programs, hashes-as-input or target tables. | Existing `payload_shader_records.py`; bounded host record exact, phone open. |
| `owner-goldshores-spine-standard-shaders.json` | Gold spine Standard | Current original Material/Shader/scene selectors, SDK45 source/compiler pins and destination relationships. | Provenance/privacy/licensing audit below, 2026-10-25; no programs, hashes-as-input or target tables. | Existing `payload_shader_records.py`; bounded host record exact, phone open. |
| `owner-goldshores-standard-shaders.json` | Gold/Root whole and Gold source Standard | Current original Material/Shader/scene selectors, SDK45 source/compiler pins and destination relationships. | Provenance/privacy/licensing audit below, 2026-10-25; no programs, hashes-as-input or target tables. | Existing `payload_shader_records.py`; bounded host record exact, phone open. |
| `owner-shipgraveyard-postprocess-shaders.json` | Shipgraveyard post-processing | Current original forms, resource field identities, pinned templates and SDK compiler context. | Audited below, 2026-10-25; no protected source/program/table. | Existing Shader pack owner; 24 host records exact, phone open. |
| `owner-repurposedcrater-hidevertices-shaders.json` | Repurposed Crater HideVertices | Original Shader/form selector, public dummy-source template and SDK pins. | Audited below, 2026-10-25; no generated content. | Existing Shader pack owner; host record exact, phone open. |
| `owner-testotherbrother-skybox-shaders.json` | TestOtherBrother Skybox | Original scene/material/Shader pointer chain and pinned SDK106 source/compiler. | Audited below, 2026-10-25; no target variants or program content. | Existing Shader pack owner; host record exact, phone open. |
| `owner-wispgraveyard-source-objects.json` | Private Wispgraveyard source-scene variant | Original object/type selectors, checked source pointers and import policies, original curve/component relationships, current Sprite identities, SDK schema and qualified media profiles. | No body/tree/curve/geometry/pixel template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1155 host exact, phone open. |
| `owner-teleport-material-objects.json` | Private teleport-material bundle | Original material/type selectors, checked references, named dummy-shader keyword policy and container relationships. | No material/shader body, keyword literal, numeric override or target template; audit below, 2026-10-25. | Source-only `object_produce.py`; J1117 host qualification, phone gate open. |
| `owner-death-effect-objects.json` | Private replay player-death-effect bundle | Rooted original graph/script selectors, checked pointer extents, preload/dependency identities and hashes. | No body, type-tree snapshot, scalar/curve override or target delta; audit below, 2026-10-25. | Existing original-input-only `object_produce.py`; J1115 host qualification, phone gate open. |
| `owner-pickup-objects.json` | Private replay pickup bundle | Original selectors, hashes, checked pointer extents and destination relationships. | No bodies, type trees or target deltas; full audit below, 2026-10-25. | Original-input-only `object_produce.py`; J1113 host qualification, phone gate open. |
| `owner-bootstrap.json` | Authored bootstrap TextAsset | Existing public build-entry attempt identity/input ID and four original preload GUID relationships absent from the original catalog. | No object/body/type-tree/target template or protected text; audit below, 2026-10-25. | Existing `player_data.text_files`; J1118 host qualification, phone gate open. |
| `owner-player-data.json` | 177 private player files | Original object selectors, checked pointers/importer relationships, authored JSON/assembly order, registry witnesses and existing source-produced record identities. | No game bodies, pixels, text payloads, type-hash overrides or private identifiers; full audits below, 2026-10-25. | Explicit PC/SDK/fresh-converter, source-produced managed providers, original importer inputs and pinned record packs; phone gate open. |
| `owner-player-registry.json` | Complete script registry source selection | Minimum original bundle/member/type witnesses, source tree hashes, immutable authored membership and importer identities. | No native/custom tree bytes, DLLs, code bodies, target IDs or property-hash overrides; audit below, 2026-10-25. | Existing script identity/player owners, original PC files, exact SDK, successful managed production and original package sources/metas. |
| `owner-player-shaders.json` | Private source-derived player Shader files | Authored ShaderLab/settings pins, original Shader/material/schema selectors, acquired SDK/include pins and final comparison hashes. | No target record, type hash, pass key, program, protected math or private identifier; full audit below, 2026-10-25. | Source-only `shader_produce.py`; J1144 host qualification, phone/runtime gates open. |
| `owner-player-shader-manifests.json` | Two native selection TextAssets | Original Material/Shader selectors, source asset identities and admission hashes. | No keyword inventory, shader programs, material values, serialized templates or private identifiers; audit below, 2026-10-25. | Original PC fields plus the shared authored selection policy; complete shader and phone gates remain open. |
| `owner-uncompressed-textures.json` | Private replay uncompressed texture bodies/pixels | Original/destination selectors, source extents, generic import/placement metadata and hashes; copy, BC1, source-coordinate dilation and public JPEG policy. | No pixels, palettes, target literals/patches, native SDK implementation or image/library bytes; full audit above, 2026-10-24. All 399 records qualify on host/Android in J1079. | Explicit PC-input-only `texture_produce.py` and separately built public JPEG tool; no current game-build consumer. |
| `owner-alpha-textures.json` | Private replay source Alpha8/single-mip texture cohort (J1082) | Canonical original/destination selectors, source/field extents, import/storage settings and hashes. | No alpha samples, encoded blocks, target byte frames, protected source or private identifiers; full audit below, 2026-10-24. | Original-PC-input-only `texture_produce.py` plus separately built public codec; no game-build consumer. |
| `owner-rgb-textures.json` | Complete ETC1/single-mip target cohort | Original/destination selectors, field/pixel extents, hashes and source JPEG policy; composition aliases reuse original Warp/Elite ramps. | No colors, normal vectors, palettes, encoded blocks or target byte frames; audit below, 2026-10-24. | Original-input-only `texture_produce.py` and public ETC/JPEG tools; J1088 qualifies all 281 records on Android. |
| `owner-rgba-textures.json` | Complete non-Alpha8 ETC2 RGBA/single-mip target cohort | Original/destination selectors, byte/field extents, hashes and canonical source relationships. | No pixels, palettes, encoded blocks, SDK implementation, private paths or target byte frames; audit below, 2026-10-24. | Existing source-only texture owner plus separately supplied SDK codec and public BC7 decoder; J1199 qualifies all 1,333 records through the Android shell producer; app-host execution remains open. |
| `owner-hierarchy-records-1.jsonl.gz` | Qualified graph-selected original object relationships | Pinned original/destination selectors, hashes and checked PPtrs only; bounded source groups, decoded by the public audit. | No body/type template, scalar, float, gameplay value or private identifier; audit below, 2026-10-25. | Existing `record_produce.py`; J1143 full source-only host qualification; phone/assembly gates open. |
| `owner-hierarchy-records-2.jsonl.gz` | Qualified graph-selected original object relationships | Pinned original/destination selectors, hashes and checked PPtrs only; bounded source groups, decoded by the public audit. | No body/type template, scalar, float, gameplay value or private identifier; audit below, 2026-10-25. | Existing `record_produce.py`; J1143 full source-only host qualification; phone/assembly gates open. |
| `owner-hierarchy-records-3.jsonl.gz` | Qualified graph-selected original object relationships | Pinned original/destination selectors, hashes and checked PPtrs only; bounded source groups, decoded by the public audit. | No body/type template, scalar, float, gameplay value or private identifier; audit below, 2026-10-25. | Existing `record_produce.py`; J1143 full source-only host qualification; phone/assembly gates open. |
| `owner-hierarchy-records-4.jsonl.gz` | Qualified graph-selected original object relationships | Pinned original/destination selectors, hashes and checked PPtrs only; bounded source groups, decoded by the public audit. | No body/type template, scalar, float, gameplay value or private identifier; audit below, 2026-10-25. | Existing `record_produce.py`; J1143 full source-only host qualification; phone/assembly gates open. |
| `owner-generic-records.json` | Qualified remaining native/scripted object records | Original selectors/hashes, destination identities and checked PPtr relationships. | Every source field, script ID and native type hash is preserved; no state/property/particle value or target template. Audit below, 2026-10-25. | Source-only `record_produce.py`; host cohort and open phone/assembly gates recorded with the generic slice. |
| `owner-gameobjects.json` | Qualified private GameObject record cohort | Original source bundle/member/object selectors and hashes, destination identities and checked PPtrs. | No component value, body or target template; original fields and native type identity preserved. Audit below, 2026-10-25. | Source-only `record_produce.py`; host qualification and remaining gates recorded with the hierarchy slice. |
| `owner-transforms.json` | Qualified private Transform record cohort | Original source bundle/member/object selectors and hashes, destination identities and checked PPtrs. | No position, rotation, scale, hierarchy template or target scalar; source fields/native type identity preserved. Audit below, 2026-10-25. | Source-only `record_produce.py`; host qualification and remaining gates recorded with the hierarchy slice. |
| `owner-animation-clips.json` | Qualified private AnimationClip object cohort | Original selectors/hashes, destination relationships and named source-schema animation policies. | No curve, pose, event/string/body template, arbitrary patch or target scalar; audit below, 2026-10-25. | Source-only `record_produce.py`; J1119 host qualification, full cohort/phone gate open. |
| `owner-material-records.json` | Qualified private Material object cohort | Original selectors/hashes, checked PPtr relationships and existing dummy-shader keyword policy. | No material value, keyword string, shader program, body template or target scalar; audit below, 2026-10-25. | Source-only `record_produce.py`; J1119 host qualification, remaining materials/phone gate open. |
| `owner-animator-controllers.json` | Qualified private AnimatorController object cohort | Original selectors/hashes and checked PPtr relationships only. | No native controller body, TOS table, curve/state value or target template; audit below, 2026-10-25. | Source-only `record_produce.py`; J1119 host qualification, full cohort/phone gate open. |
| `owner-rgb-mip-textures.json` | Complete ETC1 mip-chain target cohort | Original/destination selectors, field/pixel extents, hashes, full mip counts and source JPEG/normal relationships. | No pixels, vectors, encoded blocks, SDK bytes or target frames; audit below, 2026-10-24. | Existing texture owner, native pixel/mip helper and public ETC/JPEG/Unity Crunch tools; J1110 qualifies the full host cohort, Android pending. |
| `owner-rgba-mip-textures.json` | Full RGBA mip-chain target cohort | Original/destination selectors, field/resource extents, source import relationships and hashes. | No pixels, block literals, serialized templates or SDK bytes; audit below, 2026-10-25. | Existing texture owner plus explicit SDK/public EAC tools; J1128 host qualification, Android open. |
| `owner-cubemap-textures.json` | 110 source-derived Cubemaps | Original face-chain selectors, field/resource extents, import relationships and hashes. | No pixels, encoded blocks, target body templates or native-probe fallback; audit below, 2026-10-25. | Existing texture owner and pinned public/SDK tools; J1128 host qualification, Android open. |
| `owner-source-baked-reflections.json` | Two original baked HDR probes | Original record/stream selectors, hashes and storage relationships; retains all original mip bytes. | No pixels, blocks, serialized templates, private settings or generated target supplier; audit below, 2026-10-29. | Existing texture owner, opt-in `cube-preserve`; device native format support required; full-file admission open. |
| `owner-avatars.json` | Private replay Avatar bodies (J1075) | Minimum original/destination identities, hashes, source extents and source-entry permutations. | No strings, poses, rig/geometry values, target literals or byte frames; full audit above, 2026-10-24. | Explicit PC-input-only `avatar_produce.py`; no current game-build consumer. |
| `owner-meshes.json` | Protected mesh bodies in the private replay packet, for the included cohort only (J1070) | Original bundle/object/resource selectors, destination identities/hashes and authored import/conversion settings. | No geometry arrays, collision data, target byte frames or float literals; full audit above, 2026-10-24. Two cases remain excluded. | Explicit original-input-only `mesh_produce.py`; no current game-build consumer. |
| `shader-postprocessing-bloom-candidate.json` | Exported one-pass Bloom and exact source-camera CopyStd placeholders | Accepted-input source/meta/resource identities, official Unity package/license hashes and pass contracts; authored camera staging pin refreshed without changing camera transforms. | Authored selection metadata only; upstream source and generated content stay local under Unity Companion License. Manual audit 2026-10-23 described above. | `shader_postprocessing_bloom`, whole-catalog preparation and catalog replay comparison; default off. |
| `shader-postprocessing-uber-candidate.json` | Exact source-camera `PostProcessResources.uber` one-pass constant-white placeholder | Accepted-input Main Camera/resource/shader/profile identities, official archive/license/source hashes, pass-0 call contract, seven original AO/LUT resource joins, 22 kernel/thread groups and transitive includes. | Reconstruction metadata only; official shader/includes and generated candidates stay ignored under Unity Companion License. Package 2.3.0 is a compatible reference, not a shipped-version claim. Audited 2026-10-24. | `shader_postprocessing_uber`, whole-catalog preparation and catalog replay comparison; independent default-off activation. |

| `owner-app-host-tools.json` | Private scoped native-host staging plan | Exact open Python/dependency file hashes, relative package paths/link targets and 21 pinned public producer source hashes; source commit is a retrieval hint. | Authored tool metadata only; no binary, SDK/game content, keys, credentials, private paths or device/storage identifiers. License/distribution boundaries are recorded below. Audited 2026-10-23. | `tools/phone-build/managed-host/stage.py` validates the fixed profile; its staged phone builder verifies file hashes and creates a separate private fixture, with no game/default-build consumer. |
| `wwise-init-android.json` | Private fixture-only Init metadata generator constants (J744) | Minimum source-bank path, format/identity/size and plugin/device/bus relationships; generated bank bodies remain local. | Authored parsing/serialization and metadata only; accepted full inventory plus explicit source hash required, exclusive ignored outputs, no SDK/media/implementation/private identifiers. Audit details below. | `wwise_init_platform.py`, explicitly invoked support tool; no current game-build dependency. |
| `tools/phone-build/legacy/transform_init.py.txt` | Exact authored historical Init transformer source | Bounded parsing/serialization and minimum format/plugin/device/bus identities, retained byte-exact for truthful historical receipts. | No bank/media bytes, SDK or wwiser implementation, private path, binary, credential or account/device identifier. Audited 2026-10-24. | Formatted owner wrapper checks full accepted inventory and configured bank before materializing/executing exact source; outputs remain ignored. |
| `owner-audio-prefab.json` | One exported source audio prefab as a local analysis input (J1055) | Four accepted bundle identities, minimum root/script/reference metadata and one explicit generated export-GUID binding; values come from original type trees. | Authored derivation and metadata only; no serialized asset/template bodies, game/SDK source, media, personal/device/account identifiers or secrets. Full audit below. | `owner_audio_prefab.py`, current experimental host support; no automatic game-build consumer. |
| `wwise-android-abi.json` | Explicit support-mode Wwise managed ABI candidate generator | Exact accepted input ID; retained API hash; official Android declaration and OS-string helper source hashes; ARM64 Release plugin identity/export hashes; minimal import/parameter rewrites, one exact-signature OS-string helper call-operand rewrite and unavailable import names. | Authored transformation policy and metadata identifiers only; authorized local Integration source inspected read-only. No SDK code, binary, managed assembly, private path, account/device data, bank or audio content is copied. The 11 unavailable imports and `enable_production_audio: false` remain explicit. Audited 2026-10-20. | `tools/wwise-android-abi/generate.py` validates the exact local profile and writes new ignored plan/candidate outputs; its strict Cecil writer and synthetic tests verify the declared changes and preservation. Explicit support tool, separate from default builds. |
| `inherited-rebuild.json` | One texture-importer host input | Accepted input, minimum export metadata identity/hash, inherited GUID and creation-time parameter. | No texture/importer body or private identifiers; accepted local export only. | `inherited_rebuild` gates source and final ledger hashes. |
| `inherited-rebuild-package.json` | Three remaining TMP include bodies | Existing TMP 3.0.6 package/archive pins, three source selectors/hashes and inherited GUIDs. | Unity Companion License, authorized local editor package; no third-party bytes tracked. | Existing `unity_package_additions.generate_pairs`, isolated R2 replay only. |
| `rebuild-r9-obligations.json` | Two previously unknown producers | Public PlayerSettings/editor callback identities and authored setup notes. | No private settings, reflected game type lists or XML content. | Coverage and validate-bindings report explicit editor obligations with local target hashes. |
| `shader-rebuild-inputs.json` | Explicit shader recovery/census/fallback dependencies and selections | Accepted input ID, work-relative hashes, output basenames and topology; no recovered content. | Private bodies remain ignored; no account/device data, credentials or new licensed code. Audited 2026-10-18. | `shader_rebuild` validates all 46 pins; retained recovery remains a blocker (63 retained records including R3–R8). |
| `lightning-stake-source-call-observer.json` | Default-off observation before one original projectile call | Accepted source fingerprint, original call identity, selector policy and authored owner/transform hashes. | Minimal reconstruction identities only; no protected method body, game binary, private replay path or device evidence. Audited 2026-10-22. | The composed Cecil producer and named runtime observer preserve original operands and call; Android behavior remains unqualified. |
| `shader-catalog-overrides.json` | Optional exact-identity catalog override allowlist | Six existing shader location IDs, catalog keys, distinct exporter GUIDs where required, source paths and current public generator/recipe hashes. | Minimum reconstruction metadata only; no shader body, binary, private path or device data. Audited 2026-10-22. | `whole_catalog.prepare_integration`, `catalog_rebuild`, `rebuild.compare`; activation is separate ignored input-bound state. |
| `shader-outline-candidate.json` | Two-pass local Outline Highlight candidate | Accepted input/catalog/bundle/object identities, four program/layout digests, pass metadata and pinned helper/tool identities. R3 maps the measured all-channel mask (15) to ShaderLab `RGBA`; unmeasured masks refuse. | Minimum reconstruction selectors only; no shader program, HLSL, serialized asset body, private path, or executable. Audited 2026-10-22. | `scripts/lab/shader_outline.py` reads this fixed public recipe and reconstructs ignored input-scoped evidence; optional exact-identity catalog consumer (J966); Android appearance remains unqualified. |
| `shader-translucent-candidate.json` | Four local source-camera blur/crop candidates | Accepted input/bundle identity, minimum shader paths/names/object IDs, separate catalog keys and exporter metadata GUIDs, pass/keyword relationships and exact authored/tool digests. | Reconstruction metadata only; no source shader body, program math, binary, private path, account/device data or tool implementation. Audited 2026-10-23. | `scripts/lab/shader_translucent.py` reads the accepted local installation and writes ignored candidates; no current catalog consumer or runtime acceptance. |
| `shader-ramp-fog-candidate.json` | One input-gated local RampFog source candidate | Accepted input ID, minimum asset-bundle path/hash, shader path ID/name, record indices/stages and exact program/blob digests; pinned authored helper and disassembler identities. R3 preserves the prior candidate after the shared helper pin changes; its numeric render state is unchanged. | Metadata and reconstruction policy only; no DXBC, HLSL, ShaderLab body, serialized asset body, private path or tool binary. Audited 2026-10-22. | `scripts/lab/shader_ramp_fog.py` reads this fixed public recipe and the user's accepted local input, then writes only ignored work output. No fallback/private recipe and optional exact-identity catalog consumer (J966); Android appearance remains unqualified. |
| `shader-screen-damage-candidate.json` | Exact native ScreenDamage single-pass reconstruction | Accepted input/bundle/object/blob identities, native record topology, tool/helper pins and stable output root. | Minimum reconstruction identities and hashes only; no serialized content, native program, shader expressions, private path or device/account data. Audited 2026-10-24. | The existing single-pass generator emits private source from the legitimate local bundle. Catalog consumption is default-off; generation does not establish editor or Android appearance acceptance. |
| `shader-sobel-buffer-candidate.json` | Native depth-edge mask and outline composite | Accepted bundle/object/blob identity, exact record/stage topology, tool/helper hashes and stable output roots. | Minimum reconstruction selectors/hashes only; no source profile values, shader expressions, program bytes or private identifiers. Audited 2026-10-24. | Existing native single-pass generator emits ignored local sources; the existing default-off shader catalog consumer preserves both catalog and exporter GUIDs. Rendering and appearance require separate editor/device evidence. |
| `shader-sobel-outline-candidate.json` | Native outline composite | Accepted bundle/object/blob identity, exact record/stage topology, tool/helper hashes and stable output roots. | Minimum reconstruction selectors/hashes only; no source profile values, shader expressions, program bytes or private identifiers. Audited 2026-10-24. | Existing native single-pass generator emits ignored local sources; the existing default-off shader catalog consumer preserves both catalog and exporter GUIDs. Rendering and appearance require separate editor/device evidence. |
| `project-inputs.json` | Remaining independently authored project inputs and original geometry identity | Public smoke/editor source identities, exact public Git commits, original bundle/mesh/hash identities. | No original geometry or private settings bodies; archived templates are our own public source. Audited 2026-10-18. | `project_input_rebuild` renders/stages/exports and hash-gates 26 complete files, including Burst defaults and authored Android graphics tiers. |
| `build-entry-inputs.json` | R7/R8 inputs: the bootstrap attempt name, the decompiled sources R7 regenerates, and one retained contract result | Accepted input ID, attempt name, assembly name/SHA-256, decompiler pin, three output paths/SHA-256, and one work-relative path/SHA-256. | No decompiled bodies, catalog data, binaries, private roots, credentials or account/device identifiers. Audited 2026-10-18; revised J597. | `build_entry_rebuild.BuildEntryIO` gates the contract result; `BuildEntryIO.decompiled` regenerates and hash-gates the sources. Only the contract result is a blocker. |
| `rebuild-binding-targets.json` | J565 final binding membership | Accepted input ID and 104 minimum project asset identities from the regenerated R2 guard. | Identifiers only, no serialized content, private roots or device/account data. Audited 2026-10-18. | Final validation requires all identifiers in both the regenerated R2 receipt and destination; R4 deferred targets are checked too. |
| `scene-rebuild-inputs.json` | Explicit temporary R5 frozen baseline; MapZone script identities now regenerated | Accepted input ID, one work-relative path and SHA-256, and the assembly whose script identities R5 derives. | No baseline contents, script implementation, private roots, binary or account/device data. Audited 2026-10-18; revised J597. | `scene_rebuild.SceneIO` gates the baseline before scratch publication and derives `moon-script-identities.txt` from the installation (`script_identity.py`); the baseline remains a fresh-rebuild blocker. |
| `catalog-typed-corrections.json` | The three typed-import corrections an exact-editor typed import measured once (J725) | Accepted input ID, shipped `catalog.json` SHA-256, location IDs, original/source asset paths, native object names, serialized-file names and path IDs; no bodies. | No catalog bodies, binaries, private roots or device/account identifiers; identities only, the minimum needed to replay `reconcile` on the host. Audited 2026-10-19. | `catalog_analysis.regenerate` writes them as the reconcile receipt in the destination; the rest of R2–R4's analysis is regenerated from the installation. |
| `composition.json` | R2 migration selection B1 and the GUID part of B5 in the rebuild path | Accepted input ID; how many runtime-recipe stages composition stages (7); two accepted-export global-texture paths with SHA-256 and their resource names; 90 previous-input → current-export GUID pairs, exactly those that change inherited store bodies. | GUIDs and asset paths only; no bodies, maps beyond the 90 needed pairs, private roots or device/account data. Audited J597. | `composition_rebuild.recipe_inputs`, with `asset-transforms.json`, `inherited-state.json`, `runtime-config.json`, `content.json` and the shader recipe, replaces B1, B3–B6 and B8 for R2. |
| `composition-export-copies.json` | Residual R2 export membership outside canonical catalog closure relocation | 128 export-path → project-path pairs and accepted input ID. | Asset identifiers only; no bodies, private roots, device/account identifiers or third-party source. Audited 2026-10-18. | `composition_io.export_membership`; all bytes come from the accepted export and are hash/size-gated against the local map. |
| `assembly-transforms.json` | Implicit historical plugin transform sequence (migration-removal commit 7, verification scope); J638 adds the reviewed updated-input unstarted skill-response cleanup guard; J714 adds the read-only `--catalog-names` source (tool hashes only; transform outputs unchanged) | Existing authored AssemblyProbe modes, exact ordered argument identifiers, accepted original/output SHA-256, tool source hashes and supplied Mono.Cecil hash. Historical producers: `integrated_objective.transform_optional_presentation`, `source_scene_candidate.stage_unavailable_audio`; current local oracles: generation marker and reviewed transform receipts. | Minimum DLL names, mode/argument identifiers and hashes only; no IL, binaries, decompiled source, middleware, private paths or device/account data. Original assemblies and Cecil must be supplied locally; no ownership or authentication changes. Updated source is an authored null check plus structural audit, with no copied native method body. Audited 2026-10-19. | Current `assembly_transforms.py` verifies in disposable `.local/` scratch. Its shared generator also supplies the three transformed DLLs to R1 below. |
| `owner-public-tools.json` | Optional public .NET 8 build-tool profile qualified from pinned public source/packages | Three public archive identities, member SHA-256/Git blobs, notice and witness hashes, exact qualified host versions; public package signatures checked during qualification. | Public tool metadata only; MIT declarations and retained notices audited 2026-10-23 UTC in the section below. No binary, signing key, game content, SDK implementation, credential or private identifier is tracked. Native host/dependency delivery remains a separate audit. | Current opt-in `public_transform_tools.py`; default SDK/R1 producer stays unchanged. |
| `original-assemblies.json` | R1 installation assembly placement and importer initialization | Accepted Managed source hashes and project paths; retained GUIDs, creation times and execution orders. The tracked common importer template supplies fixed settings. | Identifiers/settings/hashes only; no DLL bytes, IL, decompiled source, private paths or account data. All 49 sources, including SimpleJSON, come from the legitimate installation. Audit above, 2026-10-18. | Current `rebuild.py` reconstructs 49 DLL/importer pairs under the isolated destination, applies J563, gates 98 output hashes/sizes and compares actual project bytes. |
| `export-additions.json` | Inherited WarpRamp asset/meta pair | Hash-pinned accepted-export PNG and importer, identity operation, inherited GUID and importer creation-time parameter. | J548 identifiers, hashes and necessary importer parameters only. The creation time is an exporter field, not a device/account/session identifier. No PNG or importer body is tracked. Audited 2026-10-17. | `export_additions.py` returns the exact pair without history or filesystem writes; composition prepares it before staging. |
| `unity-package-additions.json` | Used inherited TMP properties include pair | Unity's `com.unity.textmeshpro` 3.0.6 archive bundled with the pinned editor; outer archive, Essential Resources archive and selected include hashes; output GUID. | Package `LICENSE.md` identifies the Unity Companion License for Unity-dependent projects. The operator supplies the authorised installed package. Coordinates, hashes and selectors only; no third-party source, package, license text or importer body is tracked. Audited 2026-10-17. | `unity_package_additions.py` reads both archives in memory, selects one include and uses the existing authored importer generator. Composition stages the pair without installing TMP or changing assembly providers. |
| `deck-transforms.json` | 14 inherited director-deck addition pairs | Seven hash-pinned accepted-export base-scene decks, category names, spawn-card GUID selections, stable output GUIDs and explicit field omissions. | J548 minimum identifiers/relationships only; no serialized cards, asset/importer bodies, protected content, private paths or device/account data. Input/source gates require the legitimate export. Audited 2026-10-17. | `asset_transforms.py` owns the `deck` constructor and read-only comparison; `composition_migration.stage` prepares all 14 before writes without reading their historical bytes. |
| `inherited-state.json` | J558 local-state ledger, not replacement content | 229 addition paths, inherited asset/meta SHA-256 and GUIDs; current identities/hashes; generator input/output identifiers and static reference chains. | J548 minimal identifiers/relationships, hashes and authored blocker classifications only. No shader programs, importer/asset bodies, private paths or device/account data. Reviewed 2026-10-17. | Current `inherited_state.py` checks inherited pairs and regenerates nine shader pairs plus WarpRamp and the TMP properties include, comparing complete pairs against the previous project and ledger after input gating. Selected receipts and generator input hashes remain pinned. Usage/comparison fields are reviewed snapshots; see [LOCAL_STATE](../docs/LOCAL_STATE.md#inherited-additions-ledger-j558). |
| `authored-additions.json` | 15 inherited shader/include addition pairs | Existing tracked sources (14 shaders, one include), source hashes, output paths and stable lab GUIDs only. | No new shader content, importer bodies, game content or private identifiers. Importers use an authored minimal schema. This audits the selection/identities, not redistribution rights for unrelated recovered shader programs. Reviewed 2026-10-17. | `authored_additions.py` generates bytes without history; `composition_migration.stage` prepares the complete cohort before writes; `authored-additions-check` compares with the migration oracle read-only. Independent of game input; the oracle check gates composition/UI input IDs. |
| `asset-transforms.json` | Preview copies for 28 SurfaceDefs, six identity assets, ten field-only prefabs and all 178 structural prefabs/scenes (migration-removal commit 4 cohorts) | Accepted-export selectors/SHA-256; authored clearing, identity, typed field edits, explicit local-reference nulling, component/settings deletion and two typed adapter constructors. Four UI prefabs reuse the hash-pinned uGUI mapping. | J548 minimal source/output, hierarchy/script, removal/owner identifiers, field paths, reference preconditions, activation/reflection values and deterministic allocation namespaces only. No YAML blocks, original component bodies, importer bodies, private paths or historical asset reads. Constructor defaults are authored schemas matching the existing sanitizer; seed names preserve its IDs without reading the named location. Provenance/privacy/licensing audit extended 2026-10-17. | `asset_transforms.py` gates input/source hashes and returns asset/meta bytes; `composition_migration.stage` verifies them against the existing plan before writing. Current `asset-transforms-check` compares the migration-stage oracle, reports exclusive structural cohorts and lists later project changes separately, without writing. |
| `hud-ui-remaps.json` | `work/config/hud-ui-remaps.json` (LOCAL_STATE blocker B2) | 43 rows mapping Unity's own uGUI script identities: the precompiled `UnityEngine.UI.dll` reference in exported scenes (`from`) to the public `com.unity.ugui` package script GUID (`to`), with the type name and package path. Measured for input `6af7ed94…`; re-verified for the 2021.3.45f2 toolchain. | No game content, names or assets; identifiers and hashes only. One repo-relative evidence path. Audited 2026-10-17. | `composition_migration.py`, `whole_catalog.py`, `source_scene_candidate.py`, `integrated_objective.py`; each checks `input_id`, two also the `UnityEngine.UI.dll` hash |
| `runtime-sources.json` | Explicit and existing-file membership in `build.py` and the `whole_catalog.build_integration` copy loop | Authored file list: 118 sorted C# paths relative to `tools/unity`; coordinator entry renamed to `PortSession.cs` (source name only). Initial selection reproduces the old rules using generated-project filenames and existence only. | No game content, generated source, private paths or identifiers; repository-authored source names only. Audited 2026-10-17. | `build.py` derives player-only source and `.meta` inputs; `whole_catalog.py` stages the same selection. No game input dependency. |
| `runtime-sources.native-view-camera.json` | Explicit 118-source runtime selection for the default-off native view-camera route | Authored C# source paths and authored first-import script identities, including the native-skin lifecycle, camera contract/owner, and diagnostic boundary. | Source names and lab script GUIDs only; no game or SDK implementation, serialized content, private path, device/account data, or binary. Audited 2026-10-20. | `whole_catalog.py` validates source membership and stages the selected runtime files; runtime camera admission remains default-off and separately gated. |
| `importer-identities.json` | Pre-import host importer identity placement | 137 script selections (106 reuse project-layout GUIDs; 31 extra authored script GUIDs, 17 added in J751 for new editor hosts and fixtures), 175 lab shader GUIDs and six lab asset GUID/template selections. | J548 minimum output identities for exact reconstruction; public importer schemas only, no game bodies, private paths or account/device data. | `importer_rebuild.py` renders public templates, gates the complete cohort against local provenance and compares via the rebuild coordinator. |
| `project-layout.json` | Inherited authored script identities and package dependency selection | 117 GUID lines for authored sources in `runtime-sources.json`; 36 public direct dependency pins. | Identifiers and public package coordinates only; no importer bodies, game-derived content or private URLs. Per-package audit below, 2026-10-17. | `build.py` validates staged identities and manifest dependencies without writing them. No game input dependency. |
| `project-layout-current.json` | Current full source layout with the selected native camera owner | Authored script GUID identities for 118 runtime sources and public Unity package coordinates. | GUIDs identify authored project scripts; package coordinates are public. No protected asset body, game implementation, private path, device/account data, or third-party implementation is included. Audited 2026-10-20. | `build.py` and `whole_catalog.py` validate authored script/importer membership and public package dependencies before staging. |
| `runtime-config.json` | Public selection in ignored `Resources/MovementBatchProbe.json`; generated at whole-catalog build entry | The lab's runtime selection for the accepted input `6af7ed94…` (Steam build 25475991); 183 present `SessionConfig` keys, preserving values and JSON types. | Authored options and necessary identifiers/relationships only; no protected content. 45 authored fields (44 present), 139 selector fields, 0 private/content fields. Excluded: `detailedVisualDiagnostics` is absent locally, so no value is invented. Audit details below, 2026-10-17. | `build.py` checks recipe keys against staged config after layout validation; extra local/obsolete keys remain allowed. Build-entry generation replaces the whole object before existing accepted-input-gated validation; no extra keys survive generation. |
| `content.json` | Public selection in ignored `work/scene-probe-build.json`; generated at whole-catalog build entry | Accepted input `6af7ed94…` (Steam build 25475991); 14 current build fields, 4,304 path strings, values and array order unchanged. | J548 permits these minimal selectors; no asset bodies, private paths or device/storage identities. Includes 61 Wwise asset UUID filenames, not middleware or banks. All fields retained; audit below, 2026-10-17. | `build.py` validates after runtime config on the accepted-input-gated whole-catalog path, before cache lookup/editor invocation. Build-entry generation replaces the work file from this recipe before validation. |
| `native-view-camera-transform.json` | Exact, default-off native view-camera transform producer | Four existing camera pairs plus two exact music-observer intermediate pairs, authored output/tool/source hashes, disabled-by-default request gate, and minimum base-prefab path/GUID. | Minimum identifiers only; no serialized content, IL, game implementation, protected assembly/prefab, private path, device/account data, or third-party code. The operator supplies legitimate local input. Audited 2026-10-21. | `native_view_camera_transform.py` and `native_view_camera_build_hook.py` validate source and profile hashes; generated assemblies/resolver files remain under ignored `work/`. Player closure, APK binding and runtime acceptance are separate gates. |
| `music-reflection-preservation.json` | Original MusicController bootstrap reflection contract | Authored assembly/type/member names and narrow preservation requirements for the pinned editor. | No implementation, game data, SDK code, binary, private path or device/account identifier. Audited 2026-10-21. | Synthetic metadata fixtures verify the declaration; same-build post-strip inspection is required before runtime qualification. |
| `original-audio-owner-sources.json` | Exact authored original-audio owner, bounded waveform and music-query cohort | Repository source hashes, source membership, authored script identities and historical ancestor hash. | Authored code identifiers and hashes only; no game implementation, content, SDK code, binary, private path or device/account data. Audited 2026-10-21. | Both producer modes validate the recipe and owner hashes; camera staging pins the same recipe, and actual owner bytes participate in generation cache identity. |
| `owner-native-arm64.json` | J1059 native build configuration | SDK-relative selectors, six flag templates, translation-unit identities/link ordering and a portable SDK cohort hash. | No source bodies, game data, compiled bytes, captured graph, private paths or account/device data. Audited 2026-10-24. | Explicit accepted input, source/converter/metadata binding; no Editor/project or device consumer. |
| `owner-player-code.json` | Current target root/retention and SDK linker/converter policy | Minimum scene/type/member identities, preservation flags, assembly order and tool hashes. | No method body, serialized object value, native registration table, binary, private path or account/device data. Audited 2026-10-24. | Full reviewed owner input and explicit hash-bound managed providers; exact SDK tools and derived native identities. |
| `owner-managed-code.json` | Current owner managed-provider/source configuration | 48 original and 272 SDK relative providers/hashes, 12 produced identities, 14 support selectors, generic tool/package identities. | No game/SDK implementation, generated source/DLL, private path, account/device identifier or credential. Audited 2026-10-24. | Accepted full original inventory; explicit tools/packages/authorized SDK inputs; existing strict transforms/contracts. |
| `owner-j850-code.json` | Fixed accepted authored-source target | Public source commit and 114 relative file hashes, accepted comparison hash, 329 managed/90 converter identities and inherited selector-only SDK/root policy. | No game/SDK implementation, native bytes, serialized values, private paths or identifiers. Audited 2026-10-24. | Independent owner sources/tools; inherited root and target byte/device parity remain explicit qualification gates. |

`runtime-sources.json` lists paths relative to `tools/unity`, staged at
`Assets/LabLoadingScene` by basename. Basename collisions (including generated sources)
are rejected. Staging copies the C# sources only and retains existing
Unity-owned `.meta` files; both paths remain player-only inputs for payload reuse.
Generated visual maps and non-source player inputs remain declared in `build.py`.
Missing authored sources and unlisted staged C# files fail validation. Historical
source lists in `nova_bridge.py` and `scene_runtime.py` remain independent; their
coordinator source entry is now `PortSession`, with resource/file names unchanged.

## Project layout audit (2026-10-17)

`project-layout.json` records 92 authored source GUIDs keyed by the same relative
paths as `runtime-sources.json`, and the 36 direct package dependency pins below.
Only filenames, the `guid:` lines of those sources' staged metadata, and manifest
dependency names/versions/public URLs were inspected in the generated project.
The GUIDs identify repository-authored scripts referenced by bundles; they contain
no game assets or importer bodies and must remain stable. These identifiers and
public dependency coordinates are independent of the accepted game input.
`build.py` validates them after staged-source validation for whole-catalog builds.
Validation never writes metadata or packages; generation belongs to a later step.

Each dependency is retained to preserve the current project contract; this is not
an assertion that every enabled module is individually used. Unity registry
packages come from Unity, while `com.unity.modules.*` are built-in modules supplied
by the pinned editor, not third-party registry downloads ([Unity manual][modules]).
Only names, versions and a public pinned Git URL are published, not package source,
licensed binaries, license texts or local package caches. No dependency was private
or game-derived, so all 36 are retained. ProjectSettings, lockfiles, generated
visual-map GUIDs and all other metadata fields are outside this extraction.

License evidence is Unity's published documentation for the pinned package release
lines and CoplayDev's license at the exact tag; no package-cache content was read.
Built-in modules remain under the operator's applicable Unity Software license
([software terms][software]), not an open-source redistribution grant.

| Dependency | Pin | Provenance / license evidence | Publication decision |
| --- | --- | --- | --- |
| `com.coplaydev.unity-mcp` | `v10.2.0`, `MCPForUnity` (public Git URL in recipe) | CoplayDev public Git repository; [MIT at v10.2.0][mcp-license] | Public coordinate only; retain. |
| `com.unity.burst` | `1.8.11` | Unity registry; [Unity Companion License (source); Unity Package Distribution License (otherwise)][burst-license] | Public coordinate only; retain. |
| `com.unity.collections` | `1.2.4` | Unity registry; [Unity Companion License for Unity-dependent projects][collections-license] | Public coordinate only; retain. |
| `com.unity.mathematics` | `1.2.1` | Unity registry; [Unity Companion License for Unity-dependent projects][mathematics-license] | Public coordinate only; retain. |
| `com.unity.modules.ai` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.androidjni` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.animation` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.assetbundle` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.audio` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.cloth` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.director` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.imageconversion` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.imgui` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.jsonserialize` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.particlesystem` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.physics` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.physics2d` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.screencapture` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.terrain` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.terrainphysics` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.tilemap` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.ui` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.uielements` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.umbra` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unityanalytics` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequest` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequestassetbundle` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequestaudio` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequesttexture` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequestwww` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.vehicles` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.video` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.vr` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.wind` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.xr` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.ugui` | `1.0.0` | Unity registry; [Unity Companion License for Unity-dependent projects][ugui-license] | Public coordinate only; retain. |

[modules]: https://docs.unity3d.com/2021.3/Documentation/Manual/upm-ui-disable.html
[software]: https://unity.com/legal/editor-terms-of-service/software
[mcp-license]: https://github.com/CoplayDev/unity-mcp/blob/v10.2.0/LICENSE
[burst-license]: https://docs.unity3d.com/Packages/com.unity.burst@1.8/license/LICENSE.html
[collections-license]: https://docs.unity3d.com/Packages/com.unity.collections@1.2/license/LICENSE.html
[mathematics-license]: https://docs.unity3d.com/Packages/com.unity.mathematics@1.2/license/LICENSE.html
[ugui-license]: https://docs.unity3d.com/Packages/com.unity.ugui@1.0/license/LICENSE.html

The survivor activation observer adds one repository-authored runtime source to
both source/layout selections (93 entries). It contains no game-derived data;
the source is staged by the existing build producer. Its actual first-import GUID
is pinned in the layout (J596). `SurvivorSkillHost.cs` is an authored editor-only fixture,
staged by that same producer; neither file introduces a local content input.

The Siren encounter draft adds `runtime/stage/SirenEncounterBoundary.cs` to both
source/layout selections (94 entries). This repository-authored owner contains
only source API calls and the minimum scene/object/card identity contract; no
serialized scene, original algorithm, asset body or middleware is reproduced.
Its actual first-import GUID is pinned in the layout (J596). `SirenEncounterHost.cs` is an authored
editor-only selection/transaction fixture staged by the existing build producer.
Neither file adds a local content input. Audited 2026-10-18; device acceptance
and R8 source/importer/provenance replay remain pending.

J600's teleporter retirement draft changes the existing authored runtime source,
with no new runtime GUID or content input. The new `TeleporterLifetimeHost.cs`
fixture is staged by the existing build producer and uses public native lifecycle
calls plus read-only exact event-target counts. It contains no original gameplay
algorithm, asset body or middleware. Audited 2026-10-19; Play Mode/device acceptance
and R8 source/importer/provenance replay remain pending.

J602 extends the authored observer/fixture with auxiliary component accounting
and binds two existing all-death observers to the accepted system-death event.
It adds no runtime file, GUID, content selection or local build input. Event and
component names identify only the minimum original API contract; no native
algorithm or serialized game data is copied. Audited 2026-10-19. R8 replay and
Android acceptance of these new observations remain separate gates.

J606 adds the repository-authored diagnostic input owner
`runtime/input/SurvivorSkillInputCoverage.cs` to both selections (95 entries),
with its actual imported GUID pinned after exact-editor validation. The owner
uses native readiness and ordinary bridge inputs; no original skill algorithm,
asset body or state configuration is copied. Its authored editor fixture is
staged by the existing producer. The selection flag is default-off runtime
diagnostic state, not a new local content input. Audited 2026-10-19; device
acceptance and R8 source/importer/provenance replay remain separate gates.

J607 changes the existing authored teleport-material owner to resolve native
overlay instance identity before public removal and run native validation after
world destruction. Its helper reads private registry metadata; it does not copy
or replace the native manager algorithm. The new authored Play Mode fixture
uses public native APIs and synthetic objects only. No runtime file/GUID,
content selection or required local input is added. Audited 2026-10-19;
completed-session device acceptance and R8 replay remain pending.

J614 adds the authored `runtime/world/EngiShieldHitGuard.cs` compatibility owner
to both selections (96 entries), with its actual imported GUID pinned. Its
minimum asset path and native component/member names identify the original
Engineer shield contract; no asset body, native blocking algorithm or community
implementation is copied. The guard delegates valid entity hits to the original
method and handles only the measured null-world-hit boundary. Its authored Play
Mode fixture uses the accepted imported prefab privately and publishes only
contract results. Audited 2026-10-19; Android acceptance and R8 source/importer/
provenance replay remain separate gates.

J617 changes the same authored guard's destruction boundary after exact-editor
native inactive-child retention evidence. It uses only the existing public
HurtBox callback setter for its exact still-owned slot; it does not copy or
replace a native list algorithm. The fixture publishes authored contracts,
including foreign callback preservation, without proprietary source or content.
The survivor check uses native body index/master linkage after owned catalog
template replacement. No new path, asset identity or required local input is
added. Audited 2026-10-19; device evidence and rebuild replay remain separate.

The Engineer native output observer adds the authored
`runtime/world/EngineerNativeOutputObserver.cs` to both selections (97 entries),
with its exact-editor imported GUID pinned. It reads native deployable/summon
APIs and stable catalog identities; no original algorithm, state machine or
asset body is copied. Its editor-only fixture names only the six minimum
Engineer asset GUIDs and paths needed to validate the original skill family,
projectiles and turret master/body relationships. The existing producer stages
both files; there is no new required local content input. Audited 2026-10-19;
Android output evidence and R8 source/importer/provenance replay remain separate
gates.

Siren diagnostic input adds the two authored sources
`runtime/input/SirenEggDiagnosticInput.cs` and
`runtime/stage/SirenEncounterEggTargets.cs` to both selections (99 entries).
They contain input ownership, read-only native registration/identity checks and
minimum original API/asset names; no game scene, state algorithm, damage rule or
asset body is copied. The editor-only fixture validates the one minimum source
egg GUID/relationship and synthetic lease contracts. Existing staging owns all
three files. The flag is explicit per-attempt state, default-off, with no new
resource setting or local content input. Audited 2026-10-19; exact-editor and
Android mission evidence plus R8 replay remain independent gates.

The authored `runtime/world/LightningStakeDiagnosticObserver.cs` brings both
source/layout selections to 100 entries. It replaces the existing inline
read-only samples with a named bounded owner and shared sampling policy, using
native public projectile/stick/network APIs only. The editor fixture names the
one minimum source prefab GUID/path and compares local component/geometry
contracts without reproducing the asset. No original implementation, content,
private identifier or required local input is added. Audited 2026-10-19;
exact-editor execution, device attribution and R8 replay remain separate gates.

The explicit abandon checker changes only authored host contracts and adds two
screen dimension report fields to an existing runtime owner. It uses reported
existing UI controls; no gameplay, death/result or native teardown algorithm
is copied or replaced. No new runtime file, GUID or local content input is
introduced by that report addition. Audited 2026-10-19.

In `project-layout.json`, a runtime source whose GUID is `null` is new and not yet imported by
Unity: the build skips its `.meta` check until its first build, after which the GUID is
recorded.

## Runtime config audit (2026-10-17)

All 184 `SessionConfig` fields were reviewed against the current local runtime
selection, including nested array/object leaves. Of these, 183 are present; the
369-key local config also has 186 keys outside `SessionConfig` (not 185, because
one current field is absent). Those extra keys were not extracted. The recipe
contains exactly the 183 present public fields, sorted recursively; array order,
empty selectors, scalar types and nested relationships are preserved.

Classification is by top-level field: 45 authored options (44 present), 139 game
selectors, and 0 private/content fields. Selector records may include lab flags
and numeric contract counts alongside their identifiers. These counts, delays,
gravity and cost are lab configuration/contract values, not serialized asset
payloads. This audit grants no redistribution rights to the assets they locate.

Excluded/doubtful-key review:

- `detailedVisualDiagnostics`: authored flag absent from the local JSON. Excluded;
  no `null`, default or inferred value is published or required by validation.
- `attempt`: retained as an authored label for the accepted build, not a timestamp,
  private run directory or device identity.
- `moneySourceSha256`: retained as a source identity precondition (a hash only),
  not source code or a payload.
- `objectiveActors`: retained; body/card/avatar/controller/mesh/material selectors,
  renderer paths and activation relationships only, with lab booleans. No mesh,
  animation or material contents.
- `integratedStages`: retained; scene/bundle/graph identifiers, hierarchy selectors,
  activation/omission relationships and numeric contract counts only. No scene
  serialization, geometry or component payloads.
- `stageCombatDecks`: retained; stage/deck identifiers and contract counts only,
  without spawn-card/category payloads.
- `worldChestBreadth`: retained; prefab and animation-clip identifiers only,
  without animation contents.
- `visualCaptureStage`, `visualCaptureRenderer`, `barrierCompletionType`,
  `barrierCompletionMethod`, `barrierEffectAsset`, `barrierEffectKey`: retained as
  empty selector strings; no capture location or content is present.

No present field contains an absolute/home path, device/storage/account identity,
private-run timestamp or protected content. Game asset paths are project-relative;
resource paths, GUIDs, catalog names and sound event names identify content that
must still be reconstructed from the operator's legitimate input. No external
`work/` file was changed during extraction. Build-entry generation and removal of
obsolete local keys are now implemented; see [Config generation](#config-generation).

Every field is assigned below; the absent authored flag remains in its class.

| Class | Fields |
| --- | --- |
| Authored option | `attempt`, `automaticDirector`, `barrelInteraction`, `combatSpine`, `detailedVisualDiagnostics` |
| Authored option | `directorSpawnLimit`, `enemyRewards`, `enemySpine`, `enhancedPresentation`, `freshRunSeed` |
| Authored option | `initializeLoadoutTables`, `integratedResults`, `integratedRuntimeSeconds`, `integratedTransitionTarget`, `integratedWorld` |
| Authored option | `launchPlayableSlice`, `moneySourceCost`, `moonMission`, `originalActiveClient`, `originalAimPresentation` |
| Authored option | `originalChestDropTable`, `originalChestEjection`, `originalChestPurchase`, `originalClientCoin`, `originalDefaultPickup` |
| Authored option | `originalInputBarrel`, `originalInteractionSelection`, `originalItemPickup`, `originalMoneyCost`, `originalPickupDropletCollision` |
| Authored option | `originalPickupDropletFlight`, `originalPickupDropletLoad`, `originalRunClock`, `pauseBeforeMoon`, `recoveredHudEnabled` |
| Authored option | `sourceGravity`, `sourceQueriesHitTriggers`, `sourceSpawnDelay`, `sourceStageBossDeck`, `stageGeometry` |
| Authored option | `stageMapZoneCount`, `stagePreviewCallbacks`, `statBuffs`, `teleporterLoop`, `worldItemDisplays` |
| Game selector | `artifactAsset`, `barrelAsset`, `barrierCompletionMethod`, `barrierCompletionType`, `barrierEffectAsset` |
| Game selector | `barrierEffectKey`, `batteryAsset`, `bodyAsset`, `chestAsset`, `chestDropTableAsset` |
| Game selector | `chestLootItemAsset`, `commandArtifactAsset`, `delusionArtifactAsset`, `displayAssets`, `enemyAirGraphAsset` |
| Game selector | `enemyAttackConfigAsset`, `enemyAvatarAsset`, `enemyBodyAsset`, `enemyControllerAsset`, `enemyDeathBuffAsset` |
| Game selector | `enemyDeathEquipment`, `enemyDeathItems`, `enemyDirectorAsset`, `enemyDirectorDeckAsset`, `enemyDirectorTeamAssets` |
| Game selector | `enemyDirectorTeamKeys`, `enemyEliteAssets`, `enemyGroundGraphAsset`, `enemyHonorArtifactAsset`, `enemyMasterAsset` |
| Game selector | `enemyMaterialAsset`, `enemyRewardAssets`, `enemyRewardKeys`, `enemySleepConfigAsset`, `enemySpawnCardAsset` |
| Game selector | `enemySpawnConfigAsset`, `enemySpawnItems`, `enemyWispArtifactAsset`, `freeUnlockBuffAsset`, `genericPickupKey` |
| Game selector | `glassAsset`, `gummyAsset`, `hiddenBuffAsset`, `intangibleBuffAsset`, `integratedStages` |
| Game selector | `juggleBuffAsset`, `jumpBoostAsset`, `jumpStrikeAsset`, `junkAsset`, `knockBuffAsset` |
| Game selector | `lowerPricedChestsAsset`, `lowerPricedConsumedAsset`, `lunarPrimaryAsset`, `lunarSecondaryAsset`, `lunarSpecialAsset` |
| Game selector | `lunarTeleporterAsset`, `lunarUtilityAsset`, `masterAsset`, `medkitBuffAsset`, `moneySourceSha256` |
| Game selector | `moonCatalog`, `multiShopCardAsset`, `objectiveActors`, `objectiveArtifactAssets`, `objectiveConfigAssets` |
| Game selector | `objectiveEffectAssets`, `objectiveItemAssets`, `objectiveItemNames`, `objectiveStunAsset`, `objectiveSupportAssets` |
| Game selector | `objectiveSupportKeys`, `objectiveSupportPaths`, `objectiveTMPSettingsAsset`, `objectiveTMPSettingsKey`, `objectiveWardBuffAsset` |
| Game selector | `objectiveWardVisualAssets`, `originalStageSceneNames`, `pickupAsset`, `pickupDropletAsset`, `pickupDropletKey` |
| Game selector | `playerDeathEffectAsset`, `playerDeathEffectKey`, `potionAsset`, `primaryFireConfigAsset`, `primaryItemAsset` |
| Game selector | `primaryReloadConfigAsset`, `randomlyLunarAsset`, `recycleAsset`, `resultsEndingAssets`, `runEventFlagsToResetOnLoop` |
| Game selector | `runSceneDefAsset`, `runSceneDefAssets`, `secondaryConfigAsset`, `soulBuffAsset`, `sourceSpawnSound` |
| Game selector | `spawnConfigAsset`, `specialConfigAsset`, `stageBossArmorBuffAsset`, `stageCombatDecks`, `stageGrandparentSunAsset` |
| Game selector | `stageMapZoneActiveNames`, `stageMiniCardAsset`, `stageMiniCardKey`, `stageMiniCardPath`, `stageOverheatBuffAsset` |
| Game selector | `stageOverheatVisualAsset`, `stagePopulationFamilies`, `stagePreviewNames`, `stageVagrantOverlayAsset`, `stageVagrantOverlayKey` |
| Game selector | `statItemAsset`, `teleportMaterialAsset`, `teleportMaterialKey`, `teleporterAsset`, `teleporterIndicatorAsset` |
| Game selector | `teleporterIndicatorKey`, `tonicBuffAsset`, `utilityConfigAsset`, `visualCaptureRenderer`, `visualCaptureStage` |
| Game selector | `voidEquipmentAsset`, `worldAdditionalLootItems`, `worldChestBreadth`, `worldCommerceAssets`, `worldDotBuffAssets` |
| Game selector | `worldDotBurnMaterialAsset`, `worldEquipmentAssets`, `worldEquipmentBuffAssets`, `worldEquipmentChestAsset`, `worldEquipmentContextItemAsset` |
| Game selector | `worldEquipmentSupportPaths`, `worldGlassesAsset`, `worldItemBehaviorBuffAssets`, `worldLootSlowBuffAsset`, `worldLootSupportPaths` |
| Game selector | `worldLunarCoinAsset`, `worldProcBuffAssets`, `worldProcSupportPaths`, `worldSlugAsset` |

## Content recipe audit (2026-10-17)

`content.json` preserves exactly the 14 present fields consumed by the current
whole-catalog build. Its 382,040 bytes are below the 5 MB extraction limit. Keys
are sorted; string case, list order and duplicates are unchanged. Despite its
name, `prefabAssets` contains 4,184 mixed asset selectors, not only prefabs.
The source is the existing local bundle selection for Steam build 25475991;
no assets or serialized asset bodies were extracted. This grants no rights to
redistribute any selected asset. Local reconstruction still requires the user's
legitimate installation and existing accepted-input preflight.

Every leaf was reviewed as a project-relative `Assets/` path (case insensitive).
No absolute/home paths, device/storage/account identifiers, run timestamps,
credentials, URLs, serialized components, geometry, text payloads or middleware
contents occur. **Excluded present fields: none.** The builder also declares and
checks `barrierEffect` and `nextStageScene`, but neither is present locally; no
value or default is invented for either. The file hash is a cache input, not a
reason to publish additional fields in a future manifest.

61 `prefabAssets` selectors have UUID filenames beneath
`Assets/WholeGame/Wwise/ScriptableObjects/`: 58 Event and 3 Soundbank assets.
These are asset identities allowed by J548, not device/storage UUIDs, audio data,
Wwise banks or proprietary middleware. The broad UUID pattern in
`scripts/audit-public.py` flags them; this is a documented manual classification,
not a claim that the unmodified pattern scanner accepts this new file. No
scanner rules were weakened. All other privacy patterns pass on the new recipe.

Sizes below are UTF-8 bytes of each value serialized with
`json.dumps(value, indent=2, sort_keys=True)` (excluding its field name and the
outer object's additional indentation). All rows are allowed list/selector
fields. Builder references are in `android/Assets/Editor/LabBuild.cs`.

| Field | Path strings | Value bytes | Current bundle reader line(s) |
| --- | ---: | ---: | --- |
| `enemyRewardAssets` | 5 | 349 | 189–191 |
| `genericPickup` | 1 | 56 | 185–187 |
| `nextStageScenes` | 23 | 1,547 | 126–129 |
| `objectiveSupportAssets` | 60 | 4,658 | 146–166 |
| `objectiveTMPSettings` | 1 | 66 | 168–170 |
| `pickupDroplet` | 1 | 56 | 181–183 |
| `playerDeathEffect` | 1 | 60 | 176–178 |
| `prefab` | 1 | 68 | 136–138 |
| `prefabAssets` | 4,184 | 364,357 | 138 |
| `scene` | 1 | 67 | 120–121 |
| `sourceStageScenes` | 23 | 1,605 | 131–134 |
| `stageScene` | 1 | 65 | 122–124 |
| `teleportMaterial` | 1 | 72 | 140–142 |
| `teleporterIndicator` | 1 | 97 | 172–174 |

The bundle plan reads all 14 fields before the `reusePayload` decision; a normal
whole-catalog build appends the catalog bundles to this plan at LabBuild.cs:200.
`build.validate_runtime_support` separately reads `objectiveSupportAssets` and
`prefabAssets` for provider ownership. `build_cache_key` hashes the entire work
file as `bundle_recipe`; it does not interpret individual fields. The new
validation compares recipe fields with strict JSON types, permits extra local
keys, reports differing key names only and never writes either input.

### Reader/writer inventory

Paths below are relative to `scripts/lab/` unless otherwise qualified. Line
numbers refer to this change. R = JSON read; W = JSON write; C = copy from a
historical snapshot (reads source, writes work); H = full-file hash; E = existence
check. Snapshot copies do not parse fields. The inventory includes support and
historical paths as well as the current build. No `tools/` code opens or writes
`scene-probe-build.json`: `tools/unity/experiments/LoadingSceneProbe.cs:15,136–143`
uses `prefabAssets` from a separate runtime probe config, not this work manifest.

| File | Readers | Writers |
| --- | --- | --- |
| `build.py` | R 298 (new equality check), R 384 (support ownership), H 361 | none |
| `project_manifest.py` | H 15 | none |
| `whole_catalog.py` | E 1272 | none |
| `composition_migration.py` | R 191, 340 (recursive asset paths/retargeting) | W 427 |
| `source_scene_candidate.py` | R 128 | W 231 (alias `recipe_path` at 127) |
| `stage_variants.py` | R 87; byte reads 119, 226; H 247 | W 101, 233; rollback byte write 258 (alias at 85) |
| `scene_runtime.py` | R 658 (snapshot), 1239, 1825, 1925 | W 309, 660, 1241, 1831; C 425, 475, 543, 734, 788, 828, 869, 947, 1399 |
| `integrated_objective.py` | R 439, 671 | W 459, 680 |
| `integrated_results.py` | R 65 | W 67 |
| `primary_fire.py` | R 29 (rollback receipt), 95 | W 98 |
| `nova_bridge.py` | R 29, 320, 565, 848, 903, 1202, 1341, 1500, 1514 | W 352, 567, 854, 905, 1214, 1343, 1502, 1519 |
| `integrated_moon.py` | R 363 (reused for both writes) | W 389, 419 |
| `android/Assets/Editor/LabBuild.cs` | R 68 (presentation-only), 117 (current build); schema 218 | none |

Implementation/verification outcome: [J550](../docs/history/journal-J1-J1177/PORTING_JOURNAL.md#j550--track-the-content-recipe-as-a-public-recipe).

## Config generation

Migration-removal commit 3, second half: `build.generate_runtime_config(project)`
and `build.generate_content_recipe()` write exactly the audited recipe objects to
`Assets/LabLoadingScene/Resources/MovementBatchProbe.json` in the generated project
and `work/scene-probe-build.json`. No defaults, inherited keys or new selectors are
added. The existing atomic JSON writer sorts object keys recursively, indents by
two spaces and adds a final newline. Array order, duplicates, case and JSON types
are preserved. Missing, invalid or empty recipes fail clearly before that target
is written. No recipe contents or provenance changed in this step.

Both full and code-only `whole_catalog.build_integration` calls generate before
source validation/staging. The existing validators remain post-generation checks.
The first build after this change requires a full `whole-catalog-build`, because
`Resources/MovementBatchProbe.json` is a payload input. Host checks do not establish
project equivalence or device acceptance.

### Current writers and ordering

- `build.generate_runtime_config` and `build.generate_content_recipe`: authoritative
  replacements at build entry. No subsequent current build step writes either file.
- `composition_migration.stage`: retained intermediate writes of the retargeted
  previous-project runtime config (including attempt, pause, cost and refreshed
  scene contracts), and retargeted content selection. Both are replaced at build
  entry. The migration itself still depends on the previous project; this step
  removes that dependency only for the final build configs.
- `integrated_objective.sanitize_optional_content`, reached by
  `composition_migration.stage_missing_sources`: retained `prefabAssets` update
  during dependency staging, before build-entry generation. Its asset transforms
  retain the silent-audio Wwise stripping policy. The later original-audio build
  hook conditionally restores only the exact accepted SoundEmitter `AkGameObj`
  component, and returns it to that stripped form for default off. No source
  serialized bytes are tracked. It is not reached after generation in either
  current build path.

Historical writers are unchanged: `source_scene_candidate.prepare`,
`stage_variants.stage` (including rollback), `scene_runtime` (staging, snapshot
copies, probe/config updates), `nova_bridge`, `primary_fire`, `integrated_results`,
`integrated_moon`, and `integrated_objective.stage_objective`. Their earlier
reader/writer inventory above remains the historical reference. Neither
`LabBuild.cs` nor `whole_catalog` writes these configs after generation.

### Current content-field readers checked

- `android/Assets/Editor/LabBuild.cs`, `Build`: all 14 recipe fields listed in the
  audit table above. Also checks optional `barrierEffect` and `nextStageScene`,
  which were already absent and remain absent/default; neither is dropped by
  generation. `BuildPresentation` reads `stageScene` and `nextStageScenes`.
- `build.build` → `validate_runtime_support`: `objectiveSupportAssets` and
  `prefabAssets`. `validate_content_recipe` compares every public recipe key.
- `composition_migration.stage_missing_sources`: recursively collects all string
  asset paths, without requiring any other key. Its sanitizer reads
  `teleportMaterial`, `barrierEffect`, `playerDeathEffect`, `pickupDroplet`,
  `genericPickup`, `teleporterIndicator`, `objectiveTMPSettings`,
  `enemyRewardAssets`, `objectiveSupportAssets`, and `prefabAssets`.
- `composition_migration.stage`: `prefabAssets`, recursive retargeting, then
  `refresh_scene_contracts` reads `stageScene`. These are migration intermediates
  before authoritative generation.
- `build.build_cache_key` and `project_manifest._external_inputs`: full-file hash,
  no field interpretation. `whole_catalog.build_integration`: existence check,
  no content-field reads.

No current reader requires a dropped field. Runtime readers and build field
accesses are unchanged. Synthetic host generation fixtures include unrelated-file
preservation, exact recipe output, strict validator compatibility, determinism,
idempotence, missing/invalid recipes and both build entry paths.

## Asset operation contract

`authored-additions.json` is a separate, repository-authored source cohort. Its
source hashes intentionally reject unreviewed source drift. Its GUIDs preserve
serialized references and its importer constructor preserves the pinned editor's
empty-field whitespace. No historical importer body is stored. The generator
returns asset/meta bytes; composition owns writing and target relocation, after
checking exact selection membership and GUID identity. It does not initialize a
Unity project or infer GUIDs from names. Remaining additions still use the existing
historical path. The sibling current action `authored-additions-check` compares
both bytes against the migration-stage copy rule, not later shader replacement.

Prior-art scope: the existing extraction/reconstruction guidance in
`docs/community-prior-art.md` and pinned ThunderKit
`Editor/Addressable/Config/ImportAddressableCatalog.cs` (commit
`95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a`) distinguish copying source artifacts
from converting target-platform content. This cohort only stages existing authored
source text with stable Unity identities; it introduces no new shader recovery,
catalog conversion or gameplay mechanism. No community implementation was copied.

`identity` copies the hash-checked export bytes, including line endings, without
normalization. Metadata remains governed by the existing export importer rule.
`set_field` selects an owner by hierarchy path segments, class ID, external script
reference (`null` for native classes) and zero-based occurrence among that owner's
matching source records. A duplicate hierarchy path fails rather than selecting
an arbitrary owner. `field_path` traverses named block mappings, and
`expected_matches` must be the integer 1. Typed values support integers, finite
floats, booleans, quoted strings and local/external reference identifiers. The
runner preserves surrounding bytes, comments, whitespace and record order;
arrays, inline subfields and multiline values are outside this operation's contract.

The existing SurfaceDef operations retain their restricted four-field contract.
`remap_references` names only the existing audited uGUI mapping recipe and its
SHA-256, with accepted-input validation. It is explicit so activation field edits
do not implicitly normalize unrelated references.

Prior-art review for this extension reused the serialization-identity subsystem
and `serialization_rebase` hierarchy/record helpers. The pinned ThunderKit
`FileIdUtil.Compute` derives script file IDs from namespace/name, and AssetRipper
`MonoScriptExtensions.IsFullNameEqual` distinguishes assembly/namespace/class.
Those existing J430 clues support exact script-reference selection rather than
component display names; native GameObject selectors use class ID 1 and no script.
No community implementation or game serialization was copied into the recipe or
runner. The real export and migration oracle govern the selected operations.

`remove_components` contains only the source component fileIDs and an integer
`expected_matches` equal to their count. The source SHA-256 gates those identifiers;
no Unity allocation is involved. Each selected record must have a surviving
GameObject owner and exactly one membership entry on that owner. GameObjects,
Transforms, RectTransforms and ownerless scene settings cannot be removed. The
runner deletes records and membership lines, preserving other bytes and rejecting
surviving local references to deleted records. External references with the same
fileID are preserved. Reference nulling, empty component slots, array filtering,
scene settings deletion and component creation need separate operations.

The removal cohort's provenance audit covers 100 current export prefabs and 208
deletion identifiers. Its source/output paths, source hashes and removal lists are
the only new recipe data; they describe relationships needed to reconstruct local
outputs and contain no serialized record bodies or substitute game content.
The serialization prior-art review again inspected pinned ThunderKit
`FileIdUtil.Compute` (namespace/name-derived script IDs) and AssetRipper
`MonoScriptExtensions.IsFullNameEqual` (assembly/namespace/class identity).
These distinguish script identities from component object IDs; deletions here
use exact hash-gated source object IDs, never a display-name guess. Existing
`integrated_objective.sanitize_optional_content` supplies the deletion/membership
technique; its broader nulling and component-addition policies are not implicit
in this operation. No third-party implementation was copied.

## Director deck constructor audit (2026-10-17)

`deck-transforms.json` describes the 14 `Director-*.asset` additions under
`Assets/LabLoadingScene/CompletenessClosure/`. Each derives from exactly one
accepted-export deck under `Assets/RoR2/Base/Scenes/`; no merging or new cards is
needed. Source names and hashes gate reconstruction; category names and spawn-card
GUIDs select source spans. The tables below use spawn-card basenames for readability
(the `csc` prefix is omitted). C = Champions, M = Minibosses, B = Basic Monsters.
Only the listed cards/categories survive, in recipe order; all other source cards
and categories are dropped. Every deck drops Special / `cscScav`.

| Output suffix (ordinary `Director-`) | Export source (`Scenes/`) | C kept | M kept | B kept |
| --- | --- | --- | --- | --- |
| dampcavesimple | `dampcave/dccsDampCaveMonsters.asset` | none | none | Lemurian |
| foggyswamp | `foggyswamp/dccsFoggySwampMonsters.asset` | BeetleQueen | Golem | Lemurian, LesserWisp, Beetle |
| frozenwall | `frozenwall/dccsFrozenWallMonsters.asset` | none | none | Lemurian, LesserWisp |
| golemplains | `golemplains/dccsGolemplainsMonsters.asset` | BeetleQueen | Golem | Lemurian, Beetle, LesserWisp |
| shipgraveyard | `shipgraveyard/dccsShipgraveyardMonsters.asset` | none | none | Beetle |
| skymeadow | `skymeadow/dccsSkyMeadowMonsters.asset` | none | none | LesserWisp |
| wispgraveyard | `wispgraveyard/dccsWispGraveyardMonsters.asset` | none | BeetleGuard | Beetle, LesserWisp |

The seven `Director-Breadth-` outputs use those same respective export decks:

| Output suffix (`Director-Breadth-`) | C kept | M kept | B kept | Additional cards dropped (besides Scav) |
| --- | --- | --- | --- | --- |
| dampcavesimple | ImpBoss | GreaterWisp, LemurianBruiser, Bell | Lemurian, Imp, HermitCrab | TitanDampCave, MagmaWorm, ElectricWorm |
| foggyswamp | BeetleQueen, Vagrant | Golem, Bell | Lemurian, LesserWisp, Jellyfish, Beetle | TitanBlackBeach |
| frozenwall | ClayBoss, ImpBoss | GreaterWisp, Bison | Lemurian, LesserWisp, Imp | MagmaWorm, ElectricWorm, GolemSnowy, Nullifier |
| golemplains | TitanGolemPlains, BeetleQueen, Vagrant | Golem, GreaterWisp | Lemurian, Beetle, Jellyfish, HermitCrab, LesserWisp | none |
| shipgraveyard | RoboBallBoss, Vagrant | Bell, GreaterWisp, LemurianBruiser | Beetle, Jellyfish | MagmaWorm, Nullifier, Vulture |
| skymeadow | RoboBallBoss, Grandparent | GreaterWisp, Parent, LemurianBruiser | LesserWisp, MiniMushroom, Bell | MagmaWorm, ElectricWorm, Nullifier |
| wispgraveyard | ClayBoss, ImpBoss | BeetleGuard, GreaterWisp, ClayBruiser | Beetle, LesserWisp, Imp | Gravekeeper, Vulture |

For all 14, the name gains `Android supported ` and the retained cards omit the
newer `isExclusivelyElite` and `eliteDef` fields. The constructor requires those
source fields to be default (`0` and a null reference), preventing silent loss of
an elite restriction. Retained category weights, card weights, spawn-card
references, spawn distances, overhead flags, minimum-stage requirements and
unlockable restrictions otherwise remain unchanged. In particular, Golemplains
Breadth retains Jellyfish's distance 2 / minimum stage 1 / overhead 1 and
HermitCrab's distance 2 / minimum stage 1 / overhead 0.

The sole sparse exception is inherited `Director-Breadth-skymeadow`: its Champions
category lacks `selectionWeight`; Grandparent retains only its spawn-card reference
and card `selectionWeight: 2`, omitting distance, overhead, minimum stage and both
unlockable strings/references. These are explicit `omit_weight` / `omit_fields`
selectors. This preserves an existing anomaly, without claiming it is correct at
runtime. No source weight is changed or invented. No Unity-allocated IDs are
required: the standalone export record and generated native importer use fileID
11400000; the recipe supplies each existing lab GUID. The importer is an authored
minimal schema and carries no source timestamp or bundle membership.

Prior-art review: pinned R2API.Director `DirectorAPIinternal.cs` at
`f539511eabf87f02afddb5a83cafd2f4704c85ad`,
`GetDirectorCardHoldersFromDCCS`, distinguishes category/card selection and
`MonsterCategoryWeightsPerDccs` preserves category weights separately. This agrees
with the director observations in `docs/community-prior-art.md`; it does not
provide Android reconstruction or byte-stable serialization. The constructor
therefore reuses hash-gated export spans, never community/game implementations or
serialized payloads in a public recipe. The synthetic fixtures exercise source
restrictions, selection, default-only elite omission, the sparse exception,
metadata, complete stage membership and read-only oracle comparison.

The inherited ledger remains a historical census: this change does not relabel
its device-verification status. Deck generation and comparison need the accepted
export; only the comparison reads the previous-project oracle. No generated
asset bodies belong in this directory.

## Non-shader addition provenance audit (2026-10-17)

The census has 22 inherited non-shader entries at J561: 19 used and three unused.
Only complete inherited pairs qualify here. Matching the later current project is
reported separately and does not replace an inherited hash. The two new owners
supply exactly the inherited bytes, including importer whitespace and GUIDs;
composition's existing `stage_addition` writes them without reading history.
The ledger now has 40 reproducible, 189 inherited and zero retired additions.
No shader entry is relabelled. These are host reconstruction claims only.

`export-additions.json` uses the existing `asset_transforms.generate_asset`
identity operation for WarpRamp. Both export files are hash-gated; the importer
changes only GUID and `timeCreated`, with exactly one creation-time field required.
The numeric importer parameter preserves a mechanical export field rather than
tracking an importer body. EliteRamp's image differs, so importer similarity is
insufficient to make it reproducible.

`unity-package-additions.json` pins the editor-bundled
`com.unity.textmeshpro-3.0.6.tgz` and its
`package/Package Resources/TMP Essential Resources.unitypackage` member. Both archive
hashes and the selected source hash are required. The package's own `LICENSE.md`
identifies the Unity Companion License for Unity-dependent projects. The source
is the operator's authorised Unity installation; it is not downloaded, extracted
into this repository, installed as a Unity package or redistributed here. The
reader rejects duplicate/nonregular members and ambiguous source selectors. The
include's `.meta` is produced by the existing authored include-importer schema.
`UNITY_EDITOR` may locate the installed editor; absent that environment setting,
the default uses `environment/toolchain.json`'s editor version. A different archive
fails its hash check regardless of its filename/version label.

The same Essential Resources archive also matches the bodies of the three unused
TMP includes, so a precise authorised recovery source is known for them. They are
not selected for staging. Its mobile shader does **not** match the inherited
mobile shader; this audit neither replaces that shader nor changes the shader
reconstruction policy.

All used entries are listed below. Paths without a prefix are under
`Assets/LabLoadingScene/Resources/`; material and UI basenames are under
`RecoveredUI/`. A blocked row remains inherited, even where current bytes match a
current generator. An export search found no inherited body match except WarpRamp.

| Entry | Complete inherited pair | Source or remaining requirement |
| --- | --- | --- |
| `EnemyClosure/FastDirector.prefab` (under `Assets/LabLoadingScene/`) | Blocked | Existing `nova_bridge.stage_enemy_spine` refuses the stale enemy catalog before output. Its fixed scene record IDs also resolve to unrelated accepted-export objects. Needs a reviewed catalog/source-identity rebase; the guard was retained. |
| `AndroidNativeEliteRamp.png` | Blocked | Accepted-export image differs; importer-only GUID/time repair cannot reproduce it. |
| `AndroidNativeWarpRamp.png` | Reproduced | Hash-pinned `texRampCompositeLight.png` identity plus explicit inherited importer parameters. |
| `AndroidNativeMaterialFamilies.json` | Blocked | Full existing material generator succeeds in scratch and matches the current project body, but differs from the inherited body. |
| `AndroidNativeStandardVariants.json` | Blocked | Full existing deferred generator succeeds in scratch and matches the current project body, but differs from the inherited body. |
| `MovementBatchProbe.json` | Blocked | Runtime-config generation matches current bytes. Its 183-key recipe cannot reproduce the inherited 366-key object; 186 old keys are absent from the recipe. Existing current config generation remains authoritative. |
| `FontMaterial0.mat` | Blocked | Unity material cloning/serialization; legitimate Bombardier `tmpBombDropshadow` font/atlas input and stable exact-editor pair fixture needed. |
| `FontMaterial1.mat` | Blocked | Same serializer requirement; legitimate RiskofRain `RiskofRainFont` font/atlas input needed. |
| `FontMaterial2.mat` | Blocked | Same serializer requirement; legitimate DLC3 SharedSuffering `tmpBombDropshadow` font/atlas and UI hologram input needed. |
| `FontMaterial3.mat` | Blocked | Same serializer requirement; legitimate Noto `NotoSans-Regular` font/atlas input needed. |
| `FontMaterial4.mat` | Blocked | Same serializer requirement; legitimate SquaresBold `tmpSquaresBold` font/atlas input needed. |
| `NativeUiMaterial0.mat` | Blocked | Builder clones source UI material, binds Family6Variant0 and saves via AssetDatabase. No isolated stable pair generator. |
| `NativeUiMaterial1.mat` | Blocked | Same serializer requirement, using its separate source UI material/texture inputs. |
| `Hud.prefab` | Blocked | RecoveredHudBuilder requires source roots, an initialized exact-editor project and native font shader. PrefabUtility serialization/local object IDs are unproven in isolation. |
| `Menu.prefab` | Blocked | Same exact-editor requirement, with source menu roots. |
| `Owned full-rectangle texCrosshairNibBar.asset` | Blocked | Builder requires native sprite-contract data, `Sprite.Create` and AssetDatabase serialization with stable local identity. |
| `Strings.json` | Blocked | Current legitimate English input has 5,578 tokens versus 4,677 inherited: 901 added and 14 changed values. Scratch comparison of the existing merge policy differs; no language text is tracked. |
| `TMP Settings.asset` | Blocked | Builder clones source settings and rebinds the font using SerializedObject; source settings/font identities and exact-editor serialization remain unproven. |
| `RecoveredUI/FontShader/TMPro_Properties.cginc` | Reproduced | Authorised local TextMesh Pro 3.0.6 Essential Resources source, archive/source hashes and inherited-GUID importer generator. |

RecoveredHudBuilder has no host-only output-directory interface: it loads typed
Unity assets, uses AssetDatabase/PrefabUtility and allocates serialized objects.
It was inspected, not invoked against the live project. Running it requires an
isolated exact-editor fixture with fully reconstructed dependencies and stable
identities; merely retaining `.meta` GUIDs does not prove serialized body equality.
No font binary is itself one of these 22 ledger entries. The materials/settings
reference game-specific font assets/atlases, which must come from the accepted
legitimate installation/export with exact input/source hashes; a similarly named
public font or arbitrary TMP example cannot substitute. No font or third-party
content is copied into tracked files.

The five unused entries below each have zero references outside their own file
in a conservative static search of current-project `Assets/` excluding `.meta`,
tracked `tools/unity`, `recipe/content.json` and `recipe/runtime-config.json`.
Search keys are the GUID, exact asset path and filename, plus the resource stem
for shaders. The scan includes the current native resource manifests and shader
includes. Namespace `TMPro` alone is not treated as a reference to `TMPro.cginc`.
This scoped absence is evidence for a retirement review, not device verification
or permission to delete historical state.

| Unused entry | Recommendation | Recovery/reference evidence |
| --- | --- | --- |
| `AndroidNativeFamily8Variant0.shader` | Retire candidate; keep now | No static references or selected generator output; retain J558 rollback protection. |
| `AndroidNativeFamily8Variant7.shader` | Retire candidate; keep now | No static references or selected generator output; retain J558 rollback protection. |
| `RecoveredUI/FontShader/TMPro.cginc` | Retire candidate; keep now | No static references; matching authorised TMP 3.0.6 source identified. |
| `RecoveredUI/FontShader/TMPro_Mobile.cginc` | Retire candidate; keep now | No static references; matching authorised TMP 3.0.6 source identified. |
| `RecoveredUI/FontShader/TMPro_Surface.cginc` | Retire candidate; keep now | No static references; matching authorised TMP 3.0.6 source identified. |

Prior-art scope is source-artifact identity/importer preservation. The review
reused `docs/community-prior-art.md` and inspected pinned ThunderKit
`Editor/Addressable/Config/ImportAddressableCatalog.cs` at
`95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a`: its `File.Copy` operations preserve
catalog/settings artifacts but provide no Android conversion or Unity serializer
reproducibility. That distinction supports identity copying only after both bytes
are proven. No community implementation, game serialization or third-party source
was copied into the recipes or generators. Existing shader/material generators
were run with explicit scratch output and their selected independent intermediates;
their existing pins and contracts were retained.

The new host fixtures cover both complete pairs, read-only source handling,
source/importer/archive drift, stable GUIDs, missing/duplicate/relocated stage
members, accepted-input gates, path/symlink escapes, archive ambiguity and the
read-only inherited oracle check. `./dev doctor` was intentionally not invoked:
it writes `work/doctor.json`, outside this task's authorised read-only work scope.
Builds, editor mutations, device commands, Git index/commits, journal and state
updates are outside this task.

## Composition export membership audit (R2, 2026-10-18)

`composition-export-copies.json` records only 128 export/project path identities.
The canonical catalog membership rule maps each reconciled closure file and its
importer from `Assets/` to `Assets/WholeGame/`, skipping DLLs and reusing existing
GUID owners. Composition additionally stages explicit recipe/store pairs and
selected native resources. R2 also reuses `whole_catalog.source_mesh_subobjects` to select uniquely resolved
native mesh exports using the existing typed/native identity checks. These rules
and the composition plan still do not identify the entire unchanged-export
cohort: ambiguous native meshes, historical dependencies and relocated
tool/settings files extend beyond resolved membership. R2 records that residual
selection rather than running R3's native bundle recovery/conversions or
discovering membership by searching the working project.
The recipe includes relocated and retained identities; it does not copy any
serialized asset content, importer content, hashes of private evidence, local
paths, original code, binary data, credentials or account/device identifiers.
The source paths are minimal identifiers required for local reconstruction from
the user's legitimate export. They provide no substitute for that input.

The local provenance map selects unchanged bytes among these candidates and
supplies hash/size gates, never source identities. On the current map the canonical
closure rule accounts for 83,385 files, resolved mesh expansion adds 496,
and the residual recipe accounts for 128; R1 owns the
other 42 export-identical assembly importers. Recipe transforms/importers, shader
and package generators, inherited store normalization and their existing pins
remain authoritative. No game-derived output was added to tracked files.

Prior-art scope: read `docs/community-prior-art.md` and inspected pinned ThunderKit
`Editor/Addressable/Config/ImportAddressableCatalog.cs` at
`95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a`. Its `File.Copy` preserves selected
catalog/settings artifacts but supplies neither this membership nor Android
conversion. R2 reuses existing stage recipes and validates source identity; no
community code or content was copied. Real-data execution remains an operator
check. Doctor was not run because it writes outside the authorized destination.

## R2–R4 catalog analysis audit (2026-10-19, J714, J725)

The ten hash-pinned local analysis inputs (`catalog-rebuild-inputs.json`) are retired.
`catalog_analysis.ensure` regenerates the source catalog (host reader, J714), the
original contract, GUID index/repairs, host closure, native container receipts, native
conversions and reconciled closure inside the destination, from the legitimate
installation, the accepted export and the accepted decompilation. Mesh sub-object
recovery and the support field contract now run as in the live pipeline. Only
`catalog-typed-corrections.json` remains: three measured asset identities, no bodies.
No protected bodies, middleware, private roots, credentials, account/device identifiers
or binary content are added to the recipe.

Prior art: re-read `docs/community-prior-art.md` and pinned ThunderKit
`ImportAddressableCatalog.cs` at `95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a`.
Its desktop catalog/settings copy does not reconstruct Android content or supply
a host catalog decoder. This replay reuses the lab's measured closure, owner and
UI rules; no new content loader or community implementation is introduced.

## R5/R6 retained-input and replay audit (2026-10-18)

`scene-rebuild-inputs.json` pins `whole-catalog-code-base.json` and
`moon-script-identities.txt`. The baseline supplies accepted compact graph hashes;
the script identity list supplies the measured MapZone TeamFilter identity used
by the existing geometry projection. Neither is regenerated here. Both stay
ignored, are validated together before catalog scratch is written, and are read
through destination-backed `StageIO`. Removing these retained inputs, together
with R3/R4's ten catalog-analysis inputs, remains an explicit fresh-rebuild
blocker. The recipe contains only work-relative identities, SHA-256 and the
accepted input ID: no game YAML, protected source, private roots, credentials,
binary content or device/account identifiers. This pins local input and grants
no redistribution rights.

R5 reuses `stage_variants.stage`, `nova_bridge.stage_first_stage_geometry` and
`composition_migration.scene_contract`. Pending scenes are determined from the
destination's measured output hashes; composition's final config rows alone do
not imply later scenes exist. R2/R3 already supply the imported closure; R5
checks graph body hashes and original GUIDs rather than staging another closure.
The regenerated R3 manifest supplies pool identities. Reduced bodies, the two
final scene repairs, navigation selection and contexts are regenerated. R6
reuses `source_scene_candidate.prepare` for all 23 scenes and derives importers
from accepted source metadata and deterministic scene GUIDs. It does not invoke
`stage_unavailable_audio`: R1 already owns both DLLs. No output body comes from
the live project. Each selected cohort is gated before buffered writes flush,
then compared against actual current-project bytes by the coordinator.

Prior-art scope: read `docs/community-prior-art.md` and the pinned R2API.Director
`DirectorAPIinternal.cs` at `f539511e` (see `reference/community-sources.json`).
Its `ClassicStageInfo.Start` / `SceneCatalog.Init` hooks and 1.4.0 DCCS timing
comment distinguish catalog identity from runtime scene population. This replay
retains those existing validation boundaries and introduces no runtime scene
loader or community code. Synthetic host checks cover the original real-action
write paths as well as destination-only replay; real-data execution remains an
operator action. Doctor was not run because it writes outside the authorized
destination. No Unity/device commands, journal/state edits or commits were made.

## R7/R8 host replay audit (2026-10-18)

Revised in J597. R7 no longer reads retained decompilation: `BuildEntryIO.decompiled`
runs the pinned ilspycmd 11.0.0.9375 (`recovery.ilspy_project`, the same invocation
`./dev decompile` uses) on the installation's `RoR2.dll`, after checking the recorded
assembly SHA-256, into destination scratch. It places only the three map sources,
each gated by its recorded SHA-256, and deletes the scratch tree. The recipe records
the assembly hash and output hashes, never decompiled text. The bootstrap attempt is
now the public string `bootstrap_attempt` instead of a read of the historical
manifest: it is a run timestamp already published in the journal (J576), carries no
private path or identifier, and only names the generation the bootstrap bytes embed.
`contracts.json` remains a retained input; its exporter needs Unity. The paragraph
below describes the original audit.

`build-entry-inputs.json` pins three accepted decompilation files, the imported
runtime-contract result and the original manifest used only for its bootstrap
attempt identity. All five are validated before any new scratch publication.
They remain explicit fresh-rebuild blockers: decompilation has not been replayed
here, the contract exporter requires Unity, and an arbitrary newly generated
attempt name cannot reproduce the current bootstrap bytes. The regenerated R3
manifest supplies every location, key and stage pool identity; it never falls
back to the live manifest. R3's ten and R5's two earlier pins remain blockers.
Only identities/hashes enter this recipe, never protected input contents.

`rebuild-binding-targets.json` retains the minimum 104 project identities reported
by the destination R2 guard (23 source scenes and 81 whole-game paths), matching
J565. Validation checks that the regenerated guard still includes that complete
set, then requires those files and every R4 deferred target in the destination.
No historical binding report is an implicit input.

The extracted `whole_catalog.generate_build_maps`, `stage_build_sources` and
`generate_build_bootstrap` keep their real-action write paths. The real build
still runs config generation, membership validation, maps/animation/context,
source/linker staging, bootstrap generation and `build` in that order. The
Android asset copy remains after staged-source validation inside `build`.
Destination replay buffers these same writes through `StageIO`, hash/size-gates
all selected products, and leaves remaining Unity import/metadata allocation to R9.
Synthetic host tests cover replay and production placement/order; no real-data
execution, editor, build or device claim is made.

Prior-art scope: re-read `docs/community-prior-art.md` and pinned ThunderKit
`ImportAddressableCatalog.cs` at `95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a`.
Its copy into `Assets/StreamingAssets/aa` supplies no Android reconstruction,
serialization or linker solution. These steps reuse existing measured lab
producers and introduce no community code or runtime loading mechanism.

## Shader and project-input host replay audit (2026-10-18)

`shader-rebuild-inputs.json` records accepted-input identity, work-relative hashes,
selected analysis locations/output basenames and water topology. It contains no
recovered tree, native program, final shader body or HLSL expression. Its retained
inputs remain private rebuild debt; see the single detailed inventory and limits
in [rebuild-plan.md](../docs/rebuild-plan.md#shader-prerequisite-and-remaining-project-inputs).
Existing source/tool/binary and roundtrip gates remain. Pinned d3dasm CLI failure
text and prior-art guidance were inspected; no community implementation is copied.
The J558 store and ledger are unchanged; changed output bodies are never used as
fallbacks or accepted on the basis of host generation.

`project-inputs.json` names existing public smoke templates, original mesh bundle/
object/hash identities and exact public historical editor source commits/paths.
The three `templates/rebuild-editors/*.cs` are independently authored repository
source taken from those Git blobs, byte for byte, to reproduce stale staged editor
inputs without Git history at rebuild time. They are frozen templates, not new
runtime code and not targets of the current C# formatter. The `ordered-script.meta`
template contains only Unity importer structure and the authored -20000 order;
its GUID comes from the already public project-layout recipe. Geometry is exported
locally from the owned installation; no OBJ vertices are published. No private
settings bodies or game-reflected association lists/XML are promoted to templates.

Manual provenance/privacy review: these additions contain configuration, minimum
identity selections/hashes and our own historical tooling only. No original game
asset/body, decompiled implementation, proprietary middleware, account data,
credential, signing material, device/storage/display identifier, private absolute
path or personal email is included. No new licenses or dependency versions are
introduced; UnityPy remains the existing pinned host exporter. Pattern scanning
supplements this review. The provenance map is local and unchanged: no generator
was found; corrections are reported in rebuild-plan rather than hand-editing it.

## Remaining-input and inherited-file replay audit (2026-10-18)

The implementation and per-group inventory are in
[rebuild-plan.md](../docs/rebuild-plan.md#r2-inherited-file-host-replay).
`project-inputs.json` now includes only authored/public Burst default fields and
a hash of the public smoke graphics baseline. Burst 1.8.11's
`Editor/BurstPlatformAotSettings.cs` was inspected locally: InitialiseDefaults,
ShouldSerialiseOut and SerialiseOut establish values, membership and ordered JSON
format. No package implementation was copied. Graphics tier settings come from
J369's authored API calls/readback; the new renderer is independently authored.
No private PlayerSettings body or reflected association list is published.

`inherited-rebuild.json` pins one accepted-export importer source hash and
GUID/time parameters. `inherited-rebuild-package.json` reuses existing package and
nested-resource archive hashes with three additional source selectors/hashes.
The package reader enforces its existing archive/member/source/complete-pair
checks. Generated importers use public ledger GUIDs, minimal schemas and standard
Unity main-object IDs; each final stream must match the ledger hash.
No body is recovered from a timestamped run or current project. No inherited
ledger status, usage, comparison, capture or integrity-check policy is changed.
The real composition stage retains its existing store read/write paths; only
isolated rebuild replay selects new per-file candidates before placement.

Prior art: inspected pinned ThunderKit ImportAddressableCatalog.cs
(`95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a`) and RoR2ImportExtensions
Editor/SetDeferredShading.cs (`477ad9b52e66e59080049fc3a65645ddb4db2cef`).
The former preserves bytes by copying; the latter sets desktop tier rendering
path using GetTierSettings/SetTierSettings, but supplies no Android settings or
serializer proof. J369's measured Android contract therefore remains authoritative.
No community implementation, original game content, package source, account data,
credentials, private absolute path, device/storage identity or binary is tracked.
No new dependency version, native recovery run or retained local-analysis pin is
introduced. No Unity/device action, harness execution, journal/state edit or Git
mutation is part of this host-only change. Doctor is omitted because it writes
outside the authorized harness destination.

## Pre-import importer identity audit (2026-10-18)

`importer-identities.json` and the five `templates/*-importer.meta` schemas move
286 importers from editor allocation to host placement. Script identities reuse
`project-layout.json` wherever present. The 14 additional identities belong to ten
authored editor tools, three generated visual-map scripts and LabDiagnostics.
The selected 105 script importers all have execution order 0; the existing
`ordered-script.meta` and project-inputs owner retain NovaInputBridge's -20000.
The shader template records the measured empty texture maps and preprocessor
setting. Default/text/model templates retain lab scene, JSON, XML and OBJ
importer settings; the model schema has no vertices, named subobjects, hierarchy
or game material data. None of these GUIDs grants access to game content.

Folder identities are **not published** (Claude's review, J575). Codex first
recorded all 3,227 folder path/GUID pairs here, about 328 KB, mostly the complete
WholeGame folder tree, which mirrors the game's asset layout. A scan of 77,788
destination files (33,773 serialized assets) found no reference to any folder GUID,
so these identities are not necessary to reconstruct anything; they would only make
unused metadata byte-identical. J548 permits the *minimum* necessary identifiers, so
the folder group was removed: Unity mints folder importers at R9, which classifies
them (only the GUID line may differ, or the folder is empty and absent) and re-runs
the reference scan on the minted GUIDs, failing on any reference. Script, shader and
other asset GUIDs stay, because serialized assets reference them.
No new file under `work/` is required as input. Destination receipts are generated
by `importer_rebuild.importer_identities` and never loaded from a historical run.

Prior-art scope: read `docs/community-prior-art.md` and inspected pinned ThunderKit
`Editor/Addressable/Config/ImportAddressableCatalog.cs` at
`95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a`. Its selected catalog/settings File.Copy
preserves bytes, but supplies no pre-import Android script/shader identity replay.
This is authored importer-schema reconstruction; no community implementation,
original game content, third-party code, credential or private capture is copied.
The working project is only a read-only comparison oracle during verification;
public templates and recorded IDs are the generator's only output inputs.
Doctor is omitted because it writes outside the authorized harness destination.
No Unity, build, device, shared-work mutation, Git write, journal or state action
is authorized in this host-only change.

## Objective exit telemetry audit (2026-10-19, J632)

The existing authored runtime source and new editor fixture contain only authored
observation/retention policy and minimum native API member names. No native
implementation, game asset data, captures or proprietary content is copied.
Existing stage_build_sources produces the fixture; no new ignored build input is
required. The runtime selection remains 100 authored files. Native snapshots are
local evidence and stay ignored, outside public recipes.

### J642 survivor combat observation source audit

Add the authored `runtime/world/SurvivorCombatOutputObserver.cs` to both
runtime source and layout selections (101 files), pinning its Unity-imported
script GUID. The existing stage_build_sources producer stages this file and
its exact-editor fixture. The report types contain authored scalar diagnostics;
API/type/field names are the minimum needed for native ownership and damage
observation. No native method body, original asset, middleware, device identity,
private path or account data is reproduced. The public runtime selection and
GUID are authored reconstruction inputs. Audited 2026-10-19; device acceptance
and output coverage remain separate from the passing editor contracts in J642.

### Per-run skill variant selection audit (2026-10-19)

The 102nd runtime source, `DeveloperSkillVariantSelection.cs`, its authored
imported GUID and editor fixture contain authored validation, observation and
native API calls. Runtime selection data stays in ignored, explicit per-command
JSON; no new ignored build input is required. Only minimum catalog/API identities
are used. No native method body, original asset, middleware, profile, entitlement,
private path or device identity is copied. The existing source/fixture producer
stages these inputs. A diagnostic native loadout is temporary; normal profile
eligibility and permanent awards remain separate.

### First-stage source lifecycle audit (2026-10-19)

The 105-source selection adds authored `FirstStageDiagnosticGate.cs`,
`FirstStageSourceOwners.cs` and `SourceStageIdentityLifecycle.cs`, their
Unity-imported GUIDs, and a pure-gate exact-editor fixture staged by the existing
producer. Existing input, stage, population and session owners integrate the
transaction behind a default-off per-attempt diagnostic. The code contains
validation, scoped native API calls, owned state restoration and minimum source
scene identities/toggle relationships required to reconstruct and verify the
local scene. It contains no native gameplay method body, original asset,
proprietary middleware, profile data, entitlement, private path or device
identifier. It does not grant expansions, ownership or achievements. The owner
always marks the attempt assisted and refuses unsupported scenes/subscribers.
The fixture checks authored decisions only; native lifecycle/device acceptance
is separate. No new ignored build input is needed. Replay changed authored
sources and fixture through R8; Phase 2 outputs are not edited.

### Timed-chest ordinary event integration audit (2026-10-19)

Existing authored profile/progression owners add the native timed-chest event
subscription and minimum achievement/reward API identities; the existing editor
fixture validates metadata and detached local profile transactions. These are
scoped authored observation, identity validation and cleanup calls, with no
native event or gameplay method body copied. No asset, middleware, platform
identity, local profile, private path or device identifier is added. Stable
store ownership allows legitimate profile replacement; existing assisted-run
exclusion and entitlement rejection remain. Existing source/fixture staging
reproduces the change through R8. No new local build input or linker roots.

### Early native player context audit (2026-10-19)

The existing AutomaticDirectorSession extracts its authored controller
registration and adopts that owned registration before native results setup.
Exact existing server identities, scoped native lifecycle calls and cleanup
remain in their current owners. No game method body, asset, profile, middleware,
platform identity, private path or device identifier is copied. No new source
selection, local input, entitlement or linker root is introduced. R8 reproduces
the two changed authored runtime sources; Phase 2 outputs remain untouched.

### Typed state-reference closure audit (2026-10-19)

The authored host closure reader adds typed string-reference discovery from the
already required accepted decompile. Only native API/type identities and field
relationships are inspected locally; no source declaration, game method body,
asset, middleware or private evidence is included in the recipe. Synthetic host
tests are authored fixtures. The existing reconciliation and staging producers
reconstruct dependency files from the legitimate input and preserve original
catalog identity without inventing aliases or ownership. Regenerated closure
and manifest inputs affect downstream content and R3/R8 replay; no Phase 2 output
is edited. No new local build prerequisite is introduced.

### Native Director deck-order audit (2026-10-19)

The authored selector defers its existing deck/enabled writes to the existing
native first-stage owner after strict preflight. The editor-only fixture calls
the native setter on an owned inactive component with an empty authored deck,
observes minimum API/private-field identities and releases its objects. No
native method body, source asset, platform identity, middleware, private path or
device data is copied. The existing producer stages the fixture; runtime source
membership remains 105. Replay selector/fixture inputs through R8; no new local
build prerequisite or Phase 2 output edit is introduced.

### Native actor observation ownership audit (2026-10-19)

The existing EnemySpineSession extracts ownership of its existing native damage
and death subscriptions. The public host contract extracts authored methods and
uses authored event/data collaborators; it copies no native gameplay body or
community implementation. Only minimum native API identities are named. No
asset, middleware, account, private path or device data is added. Source count
remains 105; the existing producer and R8 reproduce the changed owner. No new
local build input, runtime diagnostic case, entitlement or Phase 2 edit occurs.

### Rolling projectile observation audit (2026-10-19)

The existing authored LightningStake observer recycles its bounded live identity
slots and caps serialized history. Its editor fixture updates shared-policy
assertions; the portable host test extracts authored policy/retirement methods
and uses authored collaborators. No native implementation, asset content,
community code, profile, private path or device identity is copied. Native
projectile behavior and source-asset identity assertions stay unchanged. The
existing producer stages the updated fixture and runtime owner; membership stays
105. Replay these inputs through R8; no new ignored input or Phase 2 edit occurs.

### Native source loot field ownership audit (2026-10-19)

The existing WholeInteractableSession qualifies minimum source component, scene
identity and table-name relationships, then clones native configuration locally
and compares it at runtime. No serialized weight/tag values or native gameplay
body is copied into the authored recipe. The generic borrowed-field lease,
portable host collaborators and synthetic inventory fixture are authored code
and minimum reconstruction relationships. No asset, middleware, profile,
entitlement, private path or device identity is added. Native availability,
weights and RNG remain authoritative, including empty optional tiers. Existing
source/fixture producers and the 105-source selection remain; replay changed
runtime owners through R8. No new ignored build input or Phase 2 edit occurs.

### Source identity metadata audit (2026-10-19)

The authored source identity reader, runtime binding validation and editor
preview fixture replace hand-maintained identity/toggle arrays with generated
local metadata. They contain only parsing, canonical shape hashing, owned
reference checks and minimum native API/script identities. Synthetic fixture
names/hierarchies are authored. Actual source object/component IDs, serialized
ranges, null slots and hierarchy relationships are emitted only under ignored
`work/` from legitimate staged scenes after their existing receipt hash gate.
No native method body, original scene/assets, middleware, private path,
device/account identifier or entitlement is reproduced in public source.
No activation policy, gameplay selection, native RNG or ownership grant is
changed. Existing R5 policy calls stay early/receipt-independent; replay
strict maps at R7 after R6, and the changed source/fixture through R8. No
Phase 2 output is edited by this change.

## Mercenary adapter source and fixture audit (J731)

The authored runtime adapter and exact-editor fixture name only the minimum
Mercenary projectile, shared visual, state configuration, baked-catalog path
and lookup keys needed to verify the accepted local relationship. No game
implementation, serialized asset body, visual, media, bank or middleware is
copied into public source. The fixture's empty Addressables settings/catalog
are independently generated test data. Native behavior was inspected locally;
pinned R2API.ContentManagement `ContentAddition.AddEffect` informs the root
EffectComponent prerequisite without supplying implementation. Generated clones
and test data stay local. These runtime and fixture changes affect R8 staging.

J733 extends the same authored owner/fixture with deferred field-mutation
bookkeeping and a synthetic CoinEmitter lookup fixture. No additional source
asset body, implementation or protected material is included. Exact native
baked indices and original files remain local inputs; the public change affects
R8 source staging and is independently checked in the pinned editor.

## Native actor observer audit (J741)

The enemy observation change is authored null/lifetime handling around existing
native API fields. Its host collaborators and measurements are independently
authored; no original method body, prefab serialization, game media, SDK or
private evidence is copied. Minimum component/type identities explain why
bodies can expose different motor implementations. Original assets and the
read-only component-layout receipt stay ignored. Spawn, damage, native event
dispatch and entitlement behavior are unchanged. The runtime source is staged
through R8; no new ignored production input or build step is introduced.

### Android Init output-metadata fixture recipe (J744)

This authored script describes one explicitly scoped Android sink-metadata
experiment. The JSON names the minimum bank path, format/version identity,
plugin registrations, audio-device IDs and top-level bus relationships needed
to recognize the accepted source structure; it contains no bank bytes, serialized
parameter blocks, SDK code, game implementation, or locally generated receipt.
The transformer accepts the configured game's source path only when its bytes
match both the operator-supplied SHA-256 and the matching entry in a full local
inventory whose input ID is currently accepted. It writes only new output and
receipt files under Git-ignored `work/`.

Prior art is the pinned wwiser Wwise-150 graph parser as an observation aid, the
installed SDK's `SetBusDevice`/sink-registration contracts, and R2API.Sound's
Init-first bank lifetime. The transform itself is authored parsing and
serialization code; no parser implementation or middleware binary is vendored.
An isolated Android native run has passed for the specific accepted input and
Global UI event, but that does not establish controller-output fidelity, every
bank path, or the retained Unity/Wwise managed lifecycle. Do not make this a
normal game-build dependency or claim it is a completed audio port.

Provenance/licensing/privacy review covers the small metadata identifiers,
minimum source-bank path and authored algorithm above. Independent review and
Root's integration review confirm the action still requires the user's accepted
legitimate installation; twelve synthetic contracts and a byte-identical local
reproduction pass. The generated bank, operator-supplied input hash,
receipt, SDK, native binaries, device evidence and absolute local paths remain
local ignored state.

## Native effect-loan retirement audit (J748)

Three existing authored owners now retain exact effect-pool/loan references
through native callbacks and a bounded Unity frame fence. Native API/type/member
names identify the required ownership and retirement contract; no original
implementation, decompiled source, serialized assets, assemblies, media or SDK
code is included. The portable host fixture contains authored lifecycle
collaborators and executes the public production owner methods. Compile inputs,
raw evidence and generated outputs remain ignored. The runtime changes affect
R8 source staging and add no private production input or build-step text patch.

## MUL-T offhand input-sequence audit

The three existing runtime owners add authored diagnostic selection, bounded
input scheduling and native-state observation. The exact component/family/skill
tuples and minimum state/type/member names identify the user's accepted native
loadout and contextual override; they reproduce no original implementation,
serialized content, animation or media. The host runner and portable fixture
are independently authored. Pinned R2API.LoadoutAPI distinguishes catalog and
family registration from live ability execution; the accepted local native
state and skill sources supply the actual contract. No community source is
copied. This changes R8 runtime staging, adds no private build input and does
not change the normal selected loadout, unlocks or entitlement behavior.

## Explicit Thor diagnostic-input audit

Five existing authored owners add an exact-model/session policy and scoped
automatic input availability. The model names are public product identities,
not device serials. No observed axis/button values, mapping contents,
proprietary input implementation, game source or middleware is copied.
The pinned Starstorm2 main-state input-bank observation informs the seam;
it supplies no Android backend or Thor mapping. Nova mapping validation and
Rewired pins remain in place. Host collaborators and guard checks are authored.
R8 stages the changed sources through its existing generator; no new GUID,
content selector, protected input or private build dependency is introduced.
Reviewed 2026-10-19; host results and device limits are recorded in J757.

J758 extends the existing MUL-T owner's refusal with minimum family/SkillDef
and selected-row identity observations. These authored diagnostic strings copy
no original implementation or serialized data, retain every acceptance guard,
and add no content input. Runtime results and raw evidence remain ignored;
R8 reproduces the source change through its existing staging step.

J760 corrects those two family-name reads using the public Unity base-object
API. The synthetic host collaborators reproduce the API shape independently;
no original class or method implementation is tracked. The same exact native
selection predicates remain, with no content, ownership or entitlement change.
R8 stages the existing authored owner; the new test adds no build input.

## Siren source-entry runtime owner audit (2026-10-19)

The source-entry draft adds the authored runtime owner
`runtime/stage/SirenSourceEntrySession.cs` to both public source selections.
Its new layout GUID is `null` until Unity imports the source. The source uses
native lifecycle APIs and exact local scene identity metadata to observe original
source-spawner output; it contains no egg cloning, serialized game content,
original algorithm, or copied protected implementation. Existing stager
selection is manifest-driven, so this owner is listed explicitly in
`runtime-sources.json` and `project-layout.json`; no build-time text replacement
or private source input is added. The host contract exercises source cohort
refusal and cleanup null/destroyed-object distinctions. Provenance/privacy review
covers this authored code and minimum identity metadata only. Editor import,
R8 reproduction and device behavior remain separate acceptance gates.


### Team position-indicator owner (2026-10-20)

`runtime/world/TeamIndicatorQueueBoundary.cs` is repository-authored runtime
source, explicitly listed in runtime-sources.json (107 entries). The exact
Unity import generates the identity recorded in project-layout.json. The owner
calls the original queue processor only while the native application dispatcher
is inactive and retains native TeamComponent lifecycle ownership. No game
implementation, serialized content, device data or third-party source is included.
Authored host tests use a synthetic lifecycle contract and do not extract
protected methods. J804 records the provenance audit and remaining device gates.


### Bounded Siren approach observation (2026-10-20)

`runtime/input/SirenNavigationObservation.cs` is repository-authored diagnostic
source, listed in `runtime-sources.json` (108 entries). Its layout GUID starts
null under the documented first-import contract; record Unity's generated GUID
after import. The owner reads existing source input/motor/path state and stores
only bounded copied values. It changes no original navigation, targeting,
damage, entitlement, profile or scene content. The synthetic host fixture and
public APIs contain no copied game/community implementation. This membership
and provenance/privacy audit adds no private build input or text replacement;
R8/R9 must replay the new authored source. J825 records host qualification and
keeps Unity/device execution unaccepted.

### Native selected-skin lifecycle (2026-10-20)

`runtime/input/AndroidNativeSourceSkinLifecycle.cs` and
`AndroidNativeSkinActivationPolicy.cs` are repository-authored owners listed in
the 110-entry runtime manifest. Their layout GUIDs start null under the existing
first-import contract. They preserve native skin selection/provider lifetime and
adapt copied material references only on an explicit per-run request. The small
material-registry release method removes only adapter-owned copies. Public
synthetic C# fixtures/assertions contain no game/community implementation. This
provenance/privacy audit adds no protected asset, SDK source or private input;
R8/R9 must replay the authored sources and membership. J826 records qualification
and the still-open Unity/device/parity gates.

### Exclusive native item-display inventory dispatch (2026-10-20)

`runtime/input/AndroidNativeItemDisplayDispatch.cs` is repository-authored pure
ownership/dispatch policy in the 111-entry runtime manifest. Its layout identity
was first imported under the existing null-identity contract; J840 records the
actual authored Unity importer GUID for subsequent replay. The native skin owner
validates exact live body/model/report identity and readiness; the world display
session keeps its eligible rule copy and Android presentation while avoiding a
second native inventory writer. Public synthetic event and actual-owner fixtures
contain authored contracts only, with minimum existing type/asset names and no
game/community implementation, serialized content, private paths or new protected
input. J838 records host qualification; R8/R9 must replay the authored sources
and membership. Device behavior and visual parity remain separate gates.

### Original Wwise process-owner admission (2026-10-20)

`runtime/session/PortSessionOriginalAudioOwner.cs` is authored coordination code
in the 112-entry runtime selection. Its layout identity starts null under the
first-import contract. The authored `support/audio/core/` and `bootstrap/`
sources compile as support assemblies; they preserve original Wwise startup,
bank callbacks and shutdown rather than reproducing those implementations.
The catalog change adds one explicitly admitted process-audio bundle lease;
default-off bundle release is unchanged. Skin activation accepts either the
silent boundary or observed original-owner readiness.

These sources contain API contracts, minimum asset identities, runtime pins
and authored observation/admission rules only. They contain no game or SDK
implementation, serialized asset, soundbank, native binary, credential or
private device/path data. Generated request/bank pins are disabled placeholders;
accepted local inputs and protected generated outputs remain ignored. R8/R9
must replay the source selection and support-assembly producer. Host source
qualification does not establish a built APK, bank readiness or audible output.

The bank-receipt packaging repair adds only an authored artifact role, the
runtime copier's required relative path and strict ownership/hash checks.
The selected cohort receipt and its bank contents remain generated under
ignored `work/`; no receipt bytes or protected audio are added to this recipe.
Synthetic staging/ZIP tests check the path contract without game content.

The passive PCM diagnostic adds authored callback ownership, bounded scalar
measurement and an exact API pre-Term guard; it copies no SDK implementation,
audio or native library. The SoundEmitter restorer publishes only minimum asset,
component and input/hash relationships; protected serialized bytes are read from
the accepted export and written only under ignored `work/`. Unknown source or
project drift refuses. These changes use existing local inputs, introduce no
new protected recipe payload and require replay of the runtime/support producer
and full bundle build. Provenance/privacy review: 2026-10-20; device acceptance
and audible output remain separate gates.

### Native source view camera (2026-10-20)

`AndroidNativeSourceCameraRigOwner.cs` is an authored, opt-in view-only owner
that borrows the staged base `Main Camera` resource through its exact asset
identity. It does not create a local/network user, alter input/UI policy, force
renderer visibility, or claim player-camera parity. Its marker transform is
strictly admitted for the existing 3124/API 107 default-off output, the
1034/API d540 audio output, PointSound 6f96/API d540, and the R10
PointSound 6f96/API 1ced output. The R10 profile requires a complete 165-row
stage receipt and artifact-manifest match, and an explicit boolean
`passive_pcm_capture_requested` that may be either true or false. The 793 API
remains restore-only for the earlier 1034 output. All transforms are
hash-bound to the exact profile and resolver identities; an explicit runtime
request still refuses if its merged marker is absent or source context is not
ready.

The source camera keeps its exact AkAudioListener/AkGameObj pair only after
original audio readiness and native initialization. Original Unity callbacks
own activation and removal; lost readiness deactivates the staging root.
`OriginalWwiseCameraListenerContract.cs` serializes scalar managed-membership
and teardown observations, retaining unknown native Add/Remove results. The
optional ready-and-PCM-gated census retains only a known flag and count. These
are authored lifecycle adapters and observations, not copied game implementation
or replacement audio behavior. Their portable fixtures use synthetic state.
The source lists include the listener contract with a first-import GUID slot;
no protected camera/audio payload is added. Provenance/privacy audit:
2026-10-20. Native registration, spatial output and playback remain unqualified.

The owner and transform sources are repository-authored. Public fixtures are
synthetic; protected camera prefab bytes and local game DLLs are only read from
the accepted local export and remain under ignored `work/`. No serialized game
content, SDK implementation, sound bank, native binary, private path, or device
identifier is included. Host qualification does not establish player-linker or
IL2CPP closure, APK binding, camera enablement, runtime acceptance, or audio
spatialization.


### Original MusicController lifecycle owner (2026-10-21)

`runtime/session/PortSessionOriginalMusicControllerOwner.cs` and
`OriginalMusicControllerContract.cs` are authored owners listed in both
`runtime-sources.json` and `runtime-sources.native-view-camera.json`. Their
layout GUIDs are stable authored identities. The owner uses the accepted
MusicController prefab selector and source lifecycle; it creates no LocalUser,
NetworkUser, Run, teleporter, or ownership/authentication result. The passive
PCM owner exposes a supplemental pre-Term callback slot while retaining its
original API/Core delegate identity. No game source, serialized prefab body,
bank, native library, protected binary, private path, or third-party source is
added. The candidate remains opt-in through the existing original-audio
selection and reports output/playback as unobserved. The exact source/input
cohort and ancestor hash are recorded in
`recipe/original-audio-owner-sources.json`; changing runtime source membership
invalidates the current stage/ancestor receipt and requires re-generation.

J913's startup adapter adds the original fieldless trigger component by type
after exact owned queue-result admission. Its policy remains in the existing
contract file and both source files retain their authored membership/importer
identities. Public fixtures contain empty API declarations and a pure-policy
harness; the original callback implementation remains in the user's ignored
game assembly. No splash asset, bank, SDK code or binary is published. The
adapter's timing is labelled as adapted and source queue acceptance does not
qualify playback.

J910 extends only authored passive-capture reports with an observed flag and
full unsigned output ID plus exact decimal serialization. Runtime values remain
in ignored local reports; no captured identifier or additional native/SDK code
is published. The changed owner cohort and ancestor pins are regenerated.

The authored output observer is a follow-on Cecil pass between the exact 6f96
audio output and native-camera stage. It reads only the return codes from the
original MusicController `AddOutput` and `RemoveOutput` calls; it does not add
native calls or establish playback, track selection, spatialization, or
audibility. Its receipt binds to the preceding audio stage receipt. Only the
exact 27340 intermediate with d540 or 1ced API can select the camera follow-on;
all runtime and acceptance gates remain closed.

The 2026-10-21 integration audit also covers
`music-reflection-preservation.json`, a declaration of the exact authored
bootstrap reflection surface, and `original-audio-owner-sources.json`, hashes
and source membership for repository-authored owners. They contain no game
implementation or serialized payload. Producer and camera ancestor pins must
match the tracked owner recipe; host refusal tests cover changed recipe bytes
and mismatched source maps. The reflection declaration requires separate
post-strip inspection before runtime qualification.

J890 adds the two authored music script importer selections to the existing
`importer-identities.json` generator, using their recorded project-layout GUIDs
and shared MonoImporter template. This covers both first placement in the
current project and reconstruction; no generated metadata is published.


### Original camera prerequisite composition (private R4)

The committed Music owner source set is preserved and extended with the exact
`AndroidNativeSourceCameraPrerequisites` runtime source. The full and native
camera runtime lists both contain 118 sorted paths; `project-layout.json` and
the original-audio owner-cohort recipe retain all prior Music rows and add the
new helper identity as an authored, not-yet-imported GUID. The camera opt-in
remains disabled. When the actual Console is absent, only the exact owned
source camera skips its Console-dependent configuration and reports reduced
fidelity using prefab defaults. Three exact shader roots are added to the
whole-catalog profile; no shader implementation is included. Host compilation
and static transformation do not establish bundle, player, APK, or runtime
readiness.

### Camera stage restore-only predecessor output (R5)

The camera build hook can unwind the exact historical `f6bc...` output only
when the current 6f96 game/API stage receipt, audio stage receipt hash and
mode, declared 1ced or d540 profile, and 6f96 preimage snapshot all match. This
hash is restore-only. Current generation pins are listed below; no new staging
path chooses this predecessor.
The exact local R12 receipt and snapshot are qualification evidence under
ignored `work/`; no generated DLL or receipt is published here. The predecessor
is not runtime accepted and restores only the exact game preimage.


### Historical camera profile output requalification (R6)

The Console-guard camera transform is qualified against four exact pairs:
3124/API 107 produces `e237af...`; 1034/API d540 produces `aa7ca...`;
PointSound 6f96/API d540 and 6f96/API 1ced both produce `41b66...`.
The 1ced row is the current R12 requested-audio profile; it remains an
explicitly matched input and is not inferred from the d540 row. The independent
Cecil transformer and verifier were run for all four pairs using frozen managed
inputs and resolved plugin/Unity references. The SceneCamera prefix's computed
maximum stack is at least 3; the emitted module hashes remained stable after
that explicit stack bound was added.

Older `236fab...` (3124/API 107) and `e16e...` (1034/d540 and the legacy
1034/793 receipt only) are restore-only receipt outputs. The exact historical
`f6bc...` output remains restore-only for the two 6f96 API profiles. Restore
requires the existing camera receipt, its matching audio-stage receipt and mode,
exact profile/API/game bytes, and the original input snapshot; none of these
outputs can be selected for new camera generation. The default-off R8 receipt
was replayed in an isolated project and restored 236fab to exact 3124 bytes;
receipt, API, output, snapshot, mode and profile mutants refused without writes.
The R12 f6bc receipt replay remains covered by the inherited R5 fixture.

R6 adds authored host contracts for the exact four profile mapping and
restore-only separation. Full player closure, IL2CPP conversion, APK binding,
camera activation and runtime acceptance remain false. No device or Unity build
was run.

### Current camera exception-handler preservation

J900 repairs the authored marker copier's omission of exception-handler
metadata. It preserves handler type, imported catch type and every instruction
boundary, including nullable ends. The independent verifier receives the exact
compiled helper as a third input and compares its handler table to the copied
marker. A host fixture removes the copied table and must be rejected.

J900's exact outputs were 3124/API 107 to `d5fc52...`, 1034/API d540 to
`e4aeeb...`, and 6f96 with d540 or 1ced to `2ae5d9...`. The previous R6
outputs are now receipt-bound restore-only, including the failed R14 `41b66...`.
Existing older predecessor restoration remains available. No generated assembly,
helper binary, private receipt or protected source is published. The runtime
marker's authored source and original-audio owner cohort are unchanged.
This audit covers the authored copier/verifier, pin updates and host fixtures;
player, camera activation, rendering and playback still require device evidence.

### Current camera deferred delegate binding

J916 moves the authored marker's reflection/delegate setup into one helper
shared by Awake and the existing guarded pump. It retries only an absent
delegate after exact owned rig/provider/target readiness; original source
callbacks still own target and camera context. No proprietary implementation
is reproduced. The fixture contains independently authored API shapes and
tests delayed readiness, single delegate reuse and exception behavior.

Root regenerates all six exact profiles from accepted local input: 3124/API107
to `494ba9...`, 1034/d540 to `83513f...`, 6f96 with d540 or 1ced to
`0da94a...`, and the 27340 music-observer intermediate with either API to
`4bd3b2...`. Previous d5fc52/e4aeeb/2ae5d9/a2054 outputs remain receipt-bound
restore-only under exact profile/API/input tuples and all existing audio,
observer, ownership and preimage checks. SDK/game-derived DLLs, resolver
snapshots, receipts and device reports remain ignored. The source/hash update
and synthetic fixtures pass the public-content boundary; device camera
readiness, visual parity and audio acceptance remain separate gates.


### Exact music-output passive capture source audit

J918 extends the authored passive monitor's immutable selector and request
plumbing. Source/default-off admission, full 64-bit identity, matching removal,
unknown-outcome Term refusal and cache/stage ownership have host contracts.
The owner cohort recipe and camera build-hook ancestor pin name only reviewed
authored sources; original game/API transform outputs remain independently
pinned. Previous exact native/API/game receipts remain restore/upgrade inputs,
never a permissive unknown-module admission.

The custom native ABI requires a paired licensed local library, recorded in
`docs/LOCAL_STATE.md`. Its SDK-derived bridge, licensed sources/archives, native
outputs, game assemblies, banks and raw device reports stay ignored. Public
changes contain authored interfaces, adapters, tests, hashes and result notes;
no protected SDK implementation is reproduced. This audit does not authorize
redistributing middleware or game content. Rebuild staging must replay these
committed producer/transform sources. J917's camera screenshot failure and
J918's untested Android capture remain explicit; neither host tests nor library
static audit qualify audio playback, rendering parity or physical audibility.

## Selected-skin render observer audit (J922, 2026-10-21)

Refresh only `native-view-camera-transform.json`'s authored skin-lifecycle source
hash after adding bounded, read-only camera/renderer observations. Existing exact
game/API/profile/output identities and default-off admission remain unchanged.
The owner, synthetic host contracts and compile-only Unity Camera API fixture
are independently authored; no game, SDK or community implementation, generated
asset, private device/storage identity or binary is published. The recipe still
requires legitimate local input and reproduces the staged authored source.

## Original music-context observation audit (J923, 2026-10-21)

Refresh `original-audio-owner-sources.json` for the authored music owner's
read-only observations and retain the previous cohort as its parent hash.
Refresh producer/camera source pins together; exact game/API outputs, native
capture ABI/library, source asset identities and runtime defaults are unchanged.
The owner, synthetic API-shape fixtures and observation harness are authored
here. Names/signatures are the minimum interoperation knowledge checked against
the accepted local API/game assemblies and official local SDK query surface;
no implementation, SDK/game binary, decompiled source, bank or private identity
is copied. Generated requests, metadata inspection and device reports remain
ignored. The normal producer regenerates this staged source from public inputs.


J925 changes three authored music-track identity observations to the current
cached-name API. The synthetic host fixture now rejects the obsolete accessor,
and the existing portable compile suite checks the regression. Owner cohort,
producer and camera pins refresh together. No protected implementation, game
asset, middleware binary, private path or identifier is added. Runtime source
regeneration is required; this audit does not qualify a player or playback.


## Original music native-return and resolved-value audit (J928, 2026-10-21)

Refresh the authored owner cohort, observer transform, camera admission and
producer pins together. The current exact 1ced API path is 6f96 → a638 → 64628;
older observer/camera outputs remain receipt-bound restoration inputs. Public
changes contain authored scalar observers, signatures, tests, hashes and pipeline
relationships required to reproduce the transformation from legitimate input.
No original method implementation, decompiled source, game/SDK binary, bank,
private device identity or raw report is published. The observer does not replay
native calls or replace their outcomes. Rebuild staging must replay these sources;
host qualification does not establish a player, playback or audibility.


## Source pre-render observation audit (J932, 2026-10-21)

Refresh the existing native camera recipe's authored skin-owner hash for a
bounded passive event/tracker observation. Existing game/API/native output hashes
are unchanged. Only independently authored owner/test code, API identity knowledge
and result notes are published; no original implementation, asset, raw capture,
private identity or SDK binary is copied. The same source generator stages the
owner; no timestamped private evidence becomes a build input. Host contracts do
not establish visual parity, callback completion or source animation acceptance.

### Passive native Siren `Listening` snapshot observer (2026-10-21)

`runtime/stage/SirenNativeListeningSnapshotPolicy.cs` and
`runtime/stage/SirenNativeListeningSnapshotReader.cs` are authored diagnostic
runtime sources. The default and native-view-camera runtime source selections
include both paths; `project-layout.json` carries null GUIDs until their first
Unity import assigns authored script metadata. The observer reads only the
existing Siren owner cadence and stores bounded scalar values plus a bounded
slot array. Listener exit releases retained Unity references while preserving
an explicitly marked, timestamped last-observed snapshot; the next distinct
native `Listening` instance begins with a fresh report. No protected game
implementation, assets, serialized content, or third-party source is added.
The existing cleanup/refusal owner is unchanged. Host coverage exercises the
listener-exit lifecycle and source seams, but Unity import and device behavior
remain unverified. This provenance note adds no private build input or text
replacement.


### Source camera material-state observation (2026-10-22)

The existing authored `AndroidNativeSourceSkinLifecycle` callback now reads
bounded scalar cache shape and the original public material-dirty getter.
It retains no original cache or material references and changes no renderer
state. The authored host fixture extracts the actual observation body and
report types against inert stubs; no protected source or private evidence is
required to reproduce it. The same runtime source recipe stages this owner.


### Complete original streamed-media staging (2026-10-22)

The authored `support/audio/generators/original_media_plan.py` planner and
extended bank generator derive the complete selected-bank external-media
closure from the user's accepted full inventory, bank index and SoundbanksInfo.
The R2 receipt separates banks and media and binds source pins, canonical paths,
IDs, references, sizes and hashes. Only generated ignored stages contain banks,
WEMs or their private row inventories; no media, XML or SDK implementation is
published. The existing authored stager, request-pin generators and runtime
payload-copy owner consume the exact receipt. Their source/recipe pins and
cache identity change together. Synthetic fixtures contain only authored bytes,
metadata, API stubs and copier-contract tests. No authored runtime source is
changed by a build-time text replacement. Native IO path knowledge is recorded
as a compatibility requirement; no SDK code is copied into the recipe.

### Original material-cache prerequisite (2026-10-22)

The authored `runtime/input/CharacterModelMaterialCacheOwner.cs` and its small
integration in the existing inactive source-skin lifecycle call the original
retained cache initializer through its exact field/method contract. The owner
does not reproduce that initializer's implementation or a broader game startup
phase. It preserves existing source-owned cache state and records a detached
process-lifetime report. Synthetic C# fixtures implement inert contracts only;
no game assembly, decompiled body, asset, SDK source or private evidence is added.
Both runtime source lists and their layout/owner-cohort maps include the new
path with a null script GUID until import. Producer/camera recipe pins change
together. No new ignored build input or build-time source replacement is added.
The host contracts do not establish Android rendering or visual parity.


### Original camera RampFog catalog root (J949)

The camera recipe adds only the minimum Shader location, GUID and accepted
source-path relationship required to reconstruct RampFog locally. The Python
root generator, Unity catalog validator and recipe agree on the exact four
roots. No shader source, serialized content, IL or generated bundle is included.
Provenance/privacy review: accepted input and exact conversion are local; pinned
EditorKit registration informs discovery only. Audited 2026-10-22. Regenerate
the full catalog to obtain the new root; Android program/pass support and visual
acceptance remain separate gates.


### Bounded original-output waveform evidence (J950)

The owner cohort retains the existing process audio and original model-cache
contracts and adds only authored V1 sample readback/finalization. The bootstrap
helper is compiled by the existing support-source glob; runtime-source membership
and Unity script identities remain unchanged. Source hashes and the historical
parent manifest are refreshed together in the producer and camera hook. The
accepted native pin now names the separately built, audited waveform extension;
predecessor native and staging lineages remain exact rollback inputs.

Public material contains authored C#/Python, synthetic host fixtures, ABI names
and hashes. It contains no samples, banks, asset bytes, SDK source or native
binary. Required protected integration inputs and their local generator/receipts
are documented in LOCAL_STATE. The current host exporter writes generated audio
only beneath ignored work. The two read-only Quit-coordinate report fields are
the minimal existing-menu diagnostic dependency for original audio shutdown;
button behavior is unchanged. Provenance/privacy audit: 2026-10-22. Android
waveform capture, content attribution and audibility remain separate gates.

### Local RampFog candidate recipe (2026-10-22)

`shader-ramp-fog-candidate.json` contains the accepted input identifier, one
source bundle path/hash, shader path ID/name, serialized-blob digest, program
record identities/digests, helper source hashes, and pinned external-tool
revision/binary hashes. Those are the minimum selectors needed to reconstruct
the user's local shader candidate. ShaderLab, DXBC, HLSL, serialized pass data,
tool binaries, private installation path and device evidence stay under
ignored `work/`. `shader_ramp_fog.py` reads only this fixed public recipe; it
does not search for an adjacent or private fallback recipe. Its output is a
stable input-keyed local candidate, optionally consumed by the exact-identity
catalog override (J966).

Prior art: `docs/community-prior-art.md` and `docs/shader-recovery.md`,
especially J329 and J364/J365, record the exporter limitation and why exact
native program bytes, tool roundtrips and independent interface reads are
useful while insufficient for equivalence. This candidate retains measured
native pass metadata and uses the repository's authored HLSL/resource/state
helpers. The translated program math is generated locally and is not published
in the recipe. No source-code or asset content is substituted for ownership.
Unity compilation, Android backend support and rendered appearance remain
separate checks; the current candidate does not claim any of them. Audited
2026-10-22.

### Local Outline Highlight candidate recipe (2026-10-22)

`shader-outline-candidate.json` records minimum source selectors, hashes and
measured pass/interface metadata for locally reconstructing the accepted
installation's two-pass shader. Protected native programs, translated math,
serialized objects and generated ShaderLab remain ignored. The authored action
checks the fixed public recipe, original catalog/bundle/object identity and
pinned helpers/tools; no private fallback recipe is used. Independent shader
recovery prior art is documented in `docs/community-prior-art.md` and
`docs/shader-recovery.md`. In particular, the pinned d3dasm interpolation
handling informed preservation of the measured pixel-position qualifier.
No upstream implementation is copied into this recipe or generator. The host
result establishes reconstruction provenance and topology only. Compilation,
resource timing, backend behavior and original appearance require separate
qualification. Provenance/privacy audit: 2026-10-22.


### LightningStake source-call observer (2026-10-22)

`lightning-stake-source-call-observer.json` records the accepted guarded source
fingerprint, one original call identity, branch/operand contract, default-off
selector and authored owner/transform hashes. Source lists and the project-layout
recipe include its authored GUID. The composed producer's provenance includes
the owner and changed integration sources. No protected implementation, game
assembly, project content or raw device evidence is published. Private producer
output locations and replay results are excluded from this recipe. Public
metadata supplies the minimum identities for local reproduction.

The exact local chain continues through the native music-return observer and
native-camera transform. Their profile pins distinguish new source from
historical lineages and remain default-off. The original call and operands stay
on the original route. The observer does not assert a successful spawn or repair
nonfinite gameplay values. Prior-art lifecycle guidance comes from the pinned
Starstorm2 SwiftSkateboard subscription/teardown pattern, documented in the
community prior-art map; no implementation is copied. Provenance/privacy audit:
2026-10-22. Android behavior requires its own built-player evidence.


### Two-shader catalog override allowlist (2026-10-22)

`shader-catalog-overrides.json` names exactly the existing Outline Highlight and
RampFog catalog locations, original GUIDs, keys and source paths, plus current
public generator/recipe hashes. These identifiers are the minimum relationships
needed to reconstruct and stage the user's legitimate local content. No shader
body, program, binary, device data or private path is published. The public
allowlist stays default-off; activation is separate input-bound ignored state.
Staging preserves original metadata, records generated candidate provenance and
joins the selector digest in its receipts. J965's isolated Android bundle compile
passes; full player rendering and PC parity remain separate gates. Prior-art
provenance remains the shader recovery contracts described above. Public source,
privacy and provenance audit: 2026-10-22.

J972 refreshes the camera recipe's authored music-stage source pin after the
canonical deterministic Core artifact is qualified. The active exact tuple and
receipt-bound predecessor restoration remain separate. Only authored producer,
synthetic compiler contracts, identities and hashes are published; observer/game
binaries, raw replay records and private paths stay ignored. The C# observer source
and game transformation outputs are unchanged. Provenance/privacy audit:
2026-10-22.

J973 refreshes the camera recipe's whole-catalog source pin for authored runtime
metadata staging. It changes no camera transform output or protected input.
Only authored staging code, synthetic metadata contracts and its source digest
are published; generated project metadata and build evidence remain ignored.
Provenance/privacy audit: 2026-10-22.

## Public owner-transform build tools

`owner-public-tools.json` is an authored input profile for the isolated optional
`public-dotnet8` transform producer. It contains only public archive URLs, exact
archive/member sizes and hashes, Cecil Git blob identities, runtime constraints
and notice/witness metadata. The compiler is Microsoft.Net.Compilers.Toolset
4.8.0 (Roslyn source `e091728607ca0fc9efca55ccfb3e59259c6b5a0a`); references are
Microsoft.NETCore.App.Ref 8.0.32 (runtime source
`b9a49e4a6d3a444a3685e318c74a7892d01873f7`); Cecil source is
`mono/cecil` at `8021f3fbe75715a1762e725594d8c00cce3679d8`. Each declares MIT.
Compiler/reference archives were signature-verified during qualification;
runtime use checks pinned hashes and Cecil source Git blobs. Source/member
selection matches the public projects and retained profile evidence, not game
output or SDK implementation dumps. The full Roslyn MIT notice is retained at
`tools/owner-build/licenses/Roslyn-LICENSE.txt`; archive license and third-party
notices are extracted with the inputs. No signing key is selected or published.

The authored `PublicProviderWitness.cs` checks only the build-tool provider's
loaded identity/hash and runtime. No original game method, proprietary source,
binary, account/device/storage data or credential is included in this profile.
Archives, extracted implementation source, compiler outputs, game-derived DLLs
and raw evidence stay ignored. This audit covers these public build-tool inputs,
not native host/dependency redistribution or complete player delivery.
Provenance/privacy audit: 2026-10-23 UTC.

J991 extends the original-audio source cohort and both runtime source selections
with the authored network-sound catalog admission owner. The project-layout
entry awaits its first Unity import. Updated coordinator/session hashes and
producer/cache identities bind the exact authored source; the prior cohort is
retained as parent. Only public API names, authored admission/report code and
controlled test observations are tracked. No original setter implementation,
definition contents, event inventory, game/middleware binary, device identity or
private path is included. Generated content still requires accepted legitimate
input. Provenance/privacy audit: 2026-10-23.

J974 refreshes the original-audio owner cohort and Lightning diagnostic source
identity after correcting a vector-valued API observation. Only authored report,
observer, fixture and producer/binding changes are published. Original game and
middleware binaries, generated metadata and raw compiler records remain ignored;
no original gameplay method or protected content is reproduced. The camera
recipe refresh binds the reviewed authored hook to the new owner cohort.
Provenance/privacy audit: 2026-10-22.


J994 refreshes the authored catalog-owner cohort and dependent producer/hook
hashes after preserving original empty-name definition rows. Public fixtures
use synthetic names/values and controlled API observations. Only authored
admission/report behavior and hashes are published; source asset values,
provider inventories, original or middleware code/binaries and raw evidence
remain ignored. Runtime source membership and local inputs are unchanged.
Provenance/privacy audit: 2026-10-23.

J997 adds the source camera component's exact EfficientBlur and FillCrop
Addressables roots and makes its already-present QuickDumbBlur dependency
explicit alongside DownTent. Only minimum source names, keys, typed catalog
locations and authored preactivation/validation code are published. Shader
bodies, source component code, generated catalogs/bundles and raw device
evidence stay ignored; accepted legitimate input supplies the original content.
The camera recipe refreshes authored prerequisite/catalog source digests.
Exact exported paths do not prove shader fidelity: these blur/crop exports use
placeholder bodies, and actual rendering semantics remain unqualified.
Provenance/privacy audit: 2026-10-23.

J998 refreshes the authored source camera lifecycle and world-report cohort,
retaining the prior owner manifest as parent. Only authored bounded admission,
scalar observations, producer/hook pins and synthetic host fixtures are
published. Native camera/game/middleware implementations and compiler outputs
stay ignored. No new content or required local input is added; source Start
assignment and callbacks remain original. Provenance/privacy audit: 2026-10-23.

J1002 extends the authored shader binder only for measured fixed `float4`
arrays and validates native buffer extents and byte offsets. Synthetic fixtures
contain invented names and layouts; no recovered program math is tracked.
Outline and RampFog recipes refresh the helper digest and select new R4 output
directories, preserving the R3 candidates. Regenerated shader bytes are
unchanged. Only authored support, metadata pins and generic host fixtures are
published; source programs, generated ShaderLab/DXBC and raw tool evidence stay
ignored. The public two-shader activation allowlist stays default-off. No new
shader body, catalog exception or device capability is accepted by this helper
checkpoint. Provenance/privacy audit: 2026-10-23.

J1003 adds the source-bound four-shader Translucent candidate recipe. It names
only the minimum accepted bundle/object/catalog/exporter identities, measured
pass/keyword relationships and tool/helper digests. The authored generator
reconstructs private shader outputs from the user's accepted installation;
it embeds no recovered program math or third-party implementation and imports
the repository binder directly. Generated ShaderLab/HLSL/DXBC and serialized
source evidence remain ignored. No original content, middleware, credential,
private root or raw device evidence is published. No catalog selection or
runtime/rendering acceptance follows from generation. Provenance/privacy
audit: 2026-10-23.

J1005 refreshes the authored world-report/audio owner cohort and camera source
pins for bounded first/latest admission observations. Its pure C# host fixture
tests the actual authored DTO, finite projections, unknown values and preserved
gate outcomes. Only authored support, synthetic fixture inputs and metadata
digests are published. Original camera/game/middleware implementations,
generated reports and raw evidence remain ignored. No new content recipe or
local input is added; reconstruction must replay the updated source cohort.
Provenance/privacy audit: 2026-10-23.


J1012 extends the default-off catalog allowlist to the four source-bound
Translucent candidates. Only minimum catalog/exporter identities, exact paths,
pass/keyword relationships and authored generator digests are published.
Original metadata is preserved; generated shader programs, native code and raw
compile/device evidence stay ignored. The source cohort update in J1011 likewise
publishes only authored lifecycle code and source digests, with unchanged
membership. No proprietary body, private identifier or runtime acceptance is
added. Provenance/privacy audit: 2026-10-23.

J1014 adds one authored equipment-highlight asset owner to the runtime-source,
script GUID and importer memberships and refreshes its exact audio/camera
source cohort. It publishes only the minimum three source field/key/prefab
relationships needed to load the user's reconstructed content. Ownership,
cancellation and teardown logic and synthetic host fixtures are authored here;
no original implementation, prefab, serialized data, middleware, generated
binary, private path or device identifier is included. Existing reconstruction
steps must replay the updated runtime and importer recipes. Provenance/privacy
audit: 2026-10-23. Android loading and original highlighting remain unaccepted.

J1015 supplies that authored script's MonoImporter sidecar using the existing
recipe GUID. It contains generic importer settings and an authored identity
only; no exported game metadata or protected content. The identity and source
cohort are unchanged. Provenance/privacy audit: 2026-10-23.

J1032 refreshes the camera recipe's authored contract and owner source digests
for the nonrecursive admission-report schema. The scalar fields, copy logic,
synthetic host checks and optional exact-editor fixture are authored here; no
original implementation, protected metadata body, middleware, generated game
content, private identifier or raw report is published. Existing runtime-source
reconstruction must replay this source cohort. Provenance/privacy audit:
2026-10-23. Editor serialization passes; player behavior remains a device gate.

J1033 adds the authored existing-material observation policy to the runtime and
project-layout memberships and synchronizes the original-audio producer/camera
owner-manifest pins. It publishes only authored ownership/report code, synthetic
host fixtures, exact source digests and the minimum current Outline field/shader
relationship. No original implementation, shader body, generated asset,
proprietary middleware, private path or raw device evidence is included.
Reconstruction must replay this source cohort. Provenance/privacy audit:
2026-10-23. Runtime material identity and rendering remain unverified.

## Source WwiseGlobal prefab identity audit (2026-10-24)

`owner-audio-prefab.json` is a minimal input/identity recipe for one source
prefab, not a serialized asset or target-bearing patch. It contains the accepted
input ID, four necessary original bundle paths/hashes/sizes, parser version,
root/collection/object identities, required component/script counts and one
external source-object to export-GUID relationship. The target size/hash is a
validation contract and supplies no output bytes. These identifiers are the
minimum lookup/relationship information needed by the bounded reconstruction.

The external InitializationSettings GUID is explicitly **export configuration**:
the pinned export collection allocates a GUID; it is not a PC catalog GUID or
an independently derived original identity. The recipe binds that configured
identity to the actual original collection/object/class/script, which the
producer validates. All serialized names, bank selections, values and original
object relationships are read from the legitimate input bundles, never stored
in this recipe or copied from an exported prefab. Existing audited assembly
GUIDs and `script_identity` supply script-pointer identity. No SDK/game source,
serialized object body, bank/media data, private path, account/device/storage
identifier, credential or signing material is included. The fixed input and
source hashes refuse unknown versions; this does not substitute for owning the
game or perform entitlement/authentication checks.

Prior art: inspected AssetRipper `1ac666f47d8e9dedf96afb0b914c70d7656151ea`,
`ExportIdHandler`, `Project/AssetsExportCollection`, `AssetExportCollection` and
`Processing/Editor/EditorFormatConverterAsync`, plus the identity-root behavior
of `Numerics/QuaternionExtensions`. These establish exporter ID allocation,
configuration GUID origin and editor-only metadata/sign rules. The authored
serializer uses mathematical empty-input XXH64 behavior, existing audited MD4
script identity and versioned Unity YAML schema; no upstream implementation or
exported YAML/template content is copied. The local MIT-licensed
AssetRipper.Primitives 3.2.0 identity reference was inspected only for API
knowledge; no third-party implementation is vendored. The private complete
9,560-byte comparison and initial quoting/signed-zero mismatch remain ignored.
The generic authored fixtures contain no original bank selections or asset data.

## Editor-free native owner configuration

`owner-native-arm64.json` extracts configuration from the qualified J1059 native
build: six argument templates, the original SDK-relative source/include-lump
relationships, fixed generated translation-unit filename membership and exact
compile/link ordering. The SDK/tool cohort is pinned by one portable aggregate
of relative paths and SHA-256 hashes, including the original objcopy tool and the complete NDK tree (linker, implicit
headers, CRT objects, system libraries and compiler runtime).
There are no source bodies, implementation snippets, serialized game values,
SDK registration tables, compiled game or SDK bytes, captured DAG nodes,
private absolute paths, device/account identifiers, credentials or keys.
The generated filenames identify the minimum translation-unit/link membership;
they cannot supply game code or replace ownership. The consuming native owner
requires the reviewed legitimate input and an explicit successful converter
receipt with all source hashes and matching metadata. Source is read only from
owner-supplied SDK and converter providers. No SDK grant or runtime equivalence
is inferred from this configuration. Manual provenance, privacy, licensing and
sensitive-content audit: 2026-10-24. Host compiler policy is preserved; Android
hosting and game acceptance remain open.

## Fixed target roots and code-generation configuration

`owner-player-code.json` records the qualified current target's 471 scene/type
identity relationships, empty serialized-type JSON set, explicit module policy,
six preservation XML documents, 332 managed provider identities, 11 root
assemblies, 93 converter assembly identities/order and 327 SDK tool/config file
hashes. Its XML contains selector elements and attributes only: type/member names,
preservation/serialization flags and relationships, never method bodies or
serialized object values. The original current XML bytes are retained to avoid
unexamined selector changes. In particular, the four inherited Burst selectors
are preserved as observed configuration, not asserted to resolve to all intended
members. The runtime's existing source behavior is unchanged.

The captured SDK native table is deliberately absent. The public existing static
reader derives its 318 identities from the owner's exact SDK binary at execution.
No SDK implementation, game method body, generated game code/data, native table,
compiled binary, captured response/DAG, private path, account/device identity,
credential or key is included. This is fixed R36-era target configuration with
original conservative Android IL2CPP policy, not a claim of independently inferred
scene semantics or accepted-output parity. It can only configure reconstruction
from the complete explicit owner-supplied provider cohort and reviewed legitimate
input. Main independently checked the six XMLs against prior configuration and
confirmed selector-only contents and exact project-field equality. Manual
provenance, privacy, licensing and sensitive-content audit: 2026-10-24.

The Android-host closure additionally pins the 17 original LinkerDescriptors
files and the original empty `il2cpp_root` marker. These are SDK-relative names
and hashes only; none of their SDK content is published. The marker retains the
SDK's normal root discovery when the tools run from a copied SDK tree. The host
already consumed these descriptors implicitly; the explicit pins close that
input gap without changing stripping policy. Manual provenance/privacy and
sensitive-content review repeated 2026-10-24.

`owner-j850-code.json` selects the public authored sources of J850 by their
commit and individual hashes, with the original input identity unchanged. Its
player configuration is the above published selector-only configuration with
the three later original-audio assemblies removed. It does not carry generated
game code or target content. The developer-only MCP input remains excluded;
the converter's complete actual source cohort determines generated native jobs.
These differences and inherited scene/module configuration remain visible
comparison gates. The source hashes were checked against the public Git commit;
all other retained selector/tool fields equal the already audited profile.
Manual provenance, privacy, licensing and sensitive-content audit: 2026-10-24.


## Historical authored Init source compatibility

`tools/phone-build/legacy/transform_init.py.txt` is the exact 18,170-byte authored
source from the J740/J744 experiment, SHA-256
`91c72d254ba9473d93ffb18c4be2233be1781b6072b08571aed7f607e76e9b37`.
Full readable source review finds bounded chunk/HIRC parsing, serialization and
exclusive ignored-output handling, with only minimum accepted-bank, plugin,
format, device and bus identities/relationships. It contains no bank/media body,
SDK implementation, vendored wwiser code, credentials, private path or account
identifier. Existing J744 provenance records pinned wwiser as an observation aid,
not copied implementation or a runtime dependency. Main independently reviewed
this origin and all source/receipt bindings. Audit: 2026-10-24.

The archive retains its original source bytes, formatting and historical scope
text. Like existing readable C# source templates, it is a versioned source
artifact explicitly consumed by a formatted current wrapper; it is not a Ruff
exemption for current Python. `owner-code/legacy_init.py` first validates full
accepted owner state and the configured original bank, then materializes the
exact artifact under ignored work at the original root-relative depth and runs
it. The real source reads its own bytes for its receipt. No new execution is
assigned a historical digest: output and receipt result from actual byte-exact
source execution. The wrapper checks source/input/output/receipt bindings again
afterwards, and retains failures/source for review. Only minimum metadata is
tracked; all generated banks, receipts, tool materializations and logs stay local.

Use current `wwise_init_platform.py` and a truthful fresh receipt for new callers.
This archival compatibility owner exists for unchanged historical receipt pins;
it grants no new middleware, game-media or controller-output rights and claims
no broader routing, audible, retained-runtime or phone acceptance. It changes no
current game-build selector or runtime request/stage admission.


## Original-input managed owner configuration

`owner-managed-code.json` contains the minimum relative identities and hashes
for 48 original PC and 272 generic SDK providers, the 12 DLL identities that the
existing producers must generate or acquire from an official generic package,
and the selected 14 original support source identities. It also pins the
qualified decompiler version and generic Newtonsoft/decoder identities. The
support identities select fresh decompilation from the owner's original DLL;
no decompiled body or generated assembly is tracked. No method implementation,
asset/media value, SDK body, binary, captured source/graph/response, private path,
credential or account/device identity is included. Audit: 2026-10-24.

The new source owner composes existing transformations, original catalog readers,
map generators, package/gameplay compilers and audio contract/pin owners rather
than adding gameplay or middleware mechanisms. Accepted inventory and provider
hashes gate every original/SDK lookup. All generated content remains ignored.
The archive-based Init compatibility source is separately audited above. Licensed
Wwise inputs remain explicit required inputs, not independently reproduced or
approved for redistribution. Current source compilation uses the exact qualified
host SDK policy and diagnostic target configuration; no runtime change, original
installation mutation, fabricated project admission or phone/performance claim
is introduced.

Native settings feedback adds two authored C# owners and generic MonoImporter
sidecars to the public runtime, project-layout and importer memberships. The
audio cohort repeats those memberships; its producer/camera manifest pins are
refreshed without changing audio owners, transforms or licensed inputs. The
form uses manual notes and bounded public build tags only. No game-derived
implementation, generated game content, logs, account/device/storage identity,
credential, signing key or middleware is added. Provenance/privacy audit:
2026-10-23. Native clipboard/browser acceptance remains a device gate.

Fast-iteration infrastructure refreshes only the camera recipe's authored
`whole_catalog.py` source digest for build timing, clone copies, verified
predecessor staging retirement and optional pre-Gradle dispatch. Camera transforms, game/API profiles and generated outputs
are unchanged. Provenance/privacy audit: 2026-10-24; authored tooling and source
digests only, with no protected content or private identifiers.

The same audit binds the authored `common.py` clone primitive as the camera/music
hooks' transitive `artifact_copy` source. Only their file-copy operation changes;
existing preimage/output hashes, atomic publication and exact module profiles
remain required. No generated assembly or protected implementation is included.

## App-host build-tool metadata audit (2026-10-23)

`owner-app-host-tools.json` contains relative paths, names, hashes and native
link selections for the scoped Python 3.14.8 build-tool profile, plus 21 public
producer source digests. Its source commit is a retrieval hint; readers compare
actual bytes. Native selections come from the previously supplied open Android
Python/dependency packages and observed imports, with no implementation or
binary copied into this repository. Source selectors refer only to audited
public repository code/metadata and notices. No legitimate game data,
account/authentication state, device/storage identity, home path or signing
material appears in the recipe.

The authored C shims use the public CPython opaque initialization and hostfxr
hosting declarations; no upstream implementation is copied. Python/framework
and dependency license notices remain with the supplied tools and private
fixture. This audit approves metadata/source tracking, not public SDK/tool/APK
redistribution. The debuggable fixture, caller-supplied tools and app-data
input manifest do not establish ownership/authentication, complete dependency
bootstrap or security-policy enforcement. Route A and the working game build
are unchanged. Setup and unsupported modes are documented in
`tools/phone-build/managed-host/README.md`; the experiment result lives only in
J1001.


The app-host profile source pins were refreshed on 2026-10-24 for the integrated
public profile: `assembly_transforms.py` and `common.py` changed while the
public transform component and C# sources remained unchanged. The source hint
now names the integrated public commit; per-file hashes remain authoritative.
The current common helper imports `contextvars`; an explicit assigned-device
check confirms `_contextvars` is built into the supplied Android Python, so no
native library or dependency selection is added. This is authored tool metadata,
not game input or a redistribution approval. Original input admission and the
fixture's remaining device gates still apply.
Build-lane configuration refreshes the camera recipe's transitive authored
`common.py` digest only. The copy primitive, camera/game transformations and
licensed inputs are unchanged. New lane state is generated below ignored local
paths; no captured source, game data, account/device identity or key is tracked.
Provenance/privacy audit: 2026-10-24.

Iteration bundle compression refreshes the authored whole-catalog producer
source digest. It adds only a private-lane uncompressed output choice and a
separate exact-input/payload reuse receipt. Acceptance compression and all
camera transformations remain unchanged. Provenance/privacy audit: 2026-10-24;
authored tooling only, no generated game content or private identifiers.

Build lanes also refresh the app-host profile's authored `common.py` digest.
The addition is a host workspace configuration lookup; it adds no import,
changes no shared transformation/copy function, and is unused by the phone
producer. This is a transitive source-pin audit, not a new Android qualification.
No native/package selection or redistribution approval changes. Audit: 2026-10-24.

`owner-alpha-textures.json` is the current experimental source-only Alpha8
Texture2D single-mip recipe for the fixed J850 target and accepted original input. Its
selectors reuse 82 canonical original textures from nine PC bundles for 4,326
target records. Canonicalization requires matching original pixel hashes and
all unchanged serialized fields; names, storage extents and target hashes remain
explicit relationships. The profile contains only minimum paths/IDs, field
layouts, hashes and importer/storage settings. It contains no alpha samples,
encoded blocks, target byte frames, protected source, SDK binary or private
identifier. Every produced image byte comes from the owner's source Alpha8
samples through a public encoder, including generic zero RGB defined by the
pinned source export format.

The authored `texture_etc.cpp` adapter and `build_texture_etc.py` use an
explicit, separately acquired pinned Ericsson ETCPACK source archive. Upstream
encoder source is unchanged and is not vendored or redistributed in source
form. The build retains the provider's Software License Agreement and an
addition/provenance notice beside private outputs. Codec/profile outputs and
raw discovery evidence stay ignored. The public recipe/adapter introduces no
ownership, authentication or entitlement behavior. Provenance, licensing,
privacy and sensitive-content audit: 2026-10-24. J1082 records the complete
phone cohort and public codec build; other texture/mip and bundle assembly
gates remain open.


The authored `owner-code/shader.py` client implements only observed exact-SDK
IPC framing, platform selection and source/keyword requests. It includes no SDK
implementation, shader payload, recovered game source, private host path or
protected tool. Old community clients provide a version clue and official Unity
enums provide API identities; no upstream implementation was copied. Owners
supply their separately acquired compiler/plugins/includes and runtime providers.
All generated shader/code and raw inspection evidence stay ignored. No ownership,
entitlement, authentication or license result is synthesized. This tool adds no
permission to redistribute acquired SDK components or derived game outputs.
Provenance, privacy, licensing and sensitive-content audit: 2026-10-24; J1094.
`owner-rgb-textures.json` extends the same source-only texture owner to the 281
ETC1/single-mip target records. Only original/destination identities, byte
extents, hashes and importer/storage relationships are included. The source
JPEG choice comes from original image-path metadata; the encoder consumes only
original PC pixels through standard BC1/BC3, RGBA/RGB/Red16 conversion, AG normal
unpacking and the existing public JPEG transform. Two authored ramp aliases
reuse `composition.json`; same-name emissive data is pinned to its correct
original source. No pixel, palette, normal-vector array, encoded block, target
byte frame, private path or credential is included.

The shared current native owner is named `build_texture_etc.py` /
`texture_etc.cpp`, extending the former Alpha8 helper instead of introducing a
second compiler/encoder owner. Source acquisition and upstream license retention
remain unchanged. J1082's historical source/command names remain reproducible at
its recorded commit. Provenance, licensing, privacy and sensitive-content audit:
2026-10-24. Final outputs/raw evidence stay ignored; full public production and
its device result are recorded separately.

## Android touch input owner

`AndroidTouchInput.cs` and its explicit script GUID are authored Android pointer
routing, geometry and primitive observation code. The runtime membership lists,
project layout and importer replay include that source. No game asset, image,
serialized game object or middleware implementation is added. Touch buttons
produce the existing original input-bank action slots; the existing camera
adapter consumes pixel deltas. The measured Nova controller mapping remains
separate, and Thor touch never claims physical-controller qualification.

Prior-art review uses the pinned Starstorm2 `BorgMain` at `a9a4badd`: native
`inputBank.jump.down`, authority and base-state scheduling are the consumer
boundary. No community implementation is copied. Public source hashes for the
existing world owner and its manifest/camera-hook chain are updated solely for
the authored manual-input availability and touch presentation changes. Generated
APK/payloads, raw pointer/device evidence and private mapping files remain under
ignored `work/`.


The touch pause request shares the settings button geometry and enters the
existing pause owner; captured primary touch events are claimed before legacy
IMGUI widgets. Native-bank edge/held observations are primitive harness data,
with no retained game objects or gameplay mutation. The authored Java/Python
`touch-gesture` helper uses the Android 13 target-UID injection API under normal
adb shell permission. Its local DEX and device requests are generated privately
from source; no platform implementation, SDK binary, game content, account data
or raw device evidence is published with this helper.

The touch integration reuses J1080's landed original scene-audio lifecycle.
Source pins are refreshed for the reviewed merged `PortSession` startup and
`IntegratedWorldBoundary` touch/UI changes. Original scene audio retains the
existing native-owner readiness gate. This updates authored source provenance;
accepted game input and distribution grants are unchanged. Audit: 2026-10-24.

Completed-session native heap capture extends the authored resource owner only.
The selector, two idle-menu capture points, callback report and exact hash-checked
host transfer contain no original implementation, serialized game object or
third-party parser. Raw snapshots can contain protected/private runtime bytes and
stay under ignored local evidence; they are never tooling distribution inputs.
The host-only Unity snapshot-analysis source is separately pinned and inspected
in community prior art, not vendored. Provenance/privacy audit: 2026-10-24;
this does not add any runtime/content redistribution grant.

`memory-snapshot-data-tools-empty-array.patch` is an authored, zero-context
transformation for the optional host-only Unity analysis CLI at source
`86af1fe8b60bfcb5e6fbe63e85377887aec32ef5`. It returns the known VM header for
zero-length arrays whose open generic element has no concrete size, and adds
an authored synthetic-heap test that retains nonempty-size refusal. Apply with
`git apply --unidiff-zero` only after verifying that exact public source pin.
No upstream implementation or captured heap bytes are included. J1091 records
31 passing tests and actual-file decode/export; the provider's Unity Companion
License/notices stay with the private checkout and outputs. Provenance/privacy
audit: 2026-10-24; no runtime/content redistribution grant changes.

`memory-snapshot-data-tools-root-labels.patch` is a second authored, zero-context
transformation for the same pinned CLI, applied after the empty-array patch. It
prints one stderr line per proven root while the crawler seeds them:
`LAB_GC_HANDLE_ROOT <managed_object_index> <gc handle index>` and
`LAB_STATIC_ROOT <managed_object_index> <type>.<field>`, with indexes matching
the DuckDB export's `managed_objects`. It restores the private J1122 root-label
adaptation for retained-root attribution; behaviour and outputs are otherwise
unchanged. No upstream implementation or heap bytes are included.
Provenance/privacy audit: 2026-10-27; no runtime/content redistribution grant changes.

### Lane source-restaging audit

The camera recipe's `whole_catalog.py` source digest is refreshed for extracting
its existing Editor source selection into a shared staging owner and restoring
receipted authored audio preimages before the ordinary composition steps. The
selected sources, camera transform and runtime behavior are unchanged. The
change contains authored tooling only, with no protected content or new public
identifiers. Lane staging uses the same runtime/editor/plugin owners and keeps
generated assets, original files and canonical staging outside its write set.


The owner APK signing addition is authored generic JDK/zipalign/apksigner
orchestration. Its explicit local tool/key directory inputs and generated APKs,
passwords, keys and raw command logs remain private. No SDK/tool implementation,
private signing material, game content or authentication/ownership adapter is
added to recipes. Public tests use authored tool/key/content witnesses only.
Tool acquisition and distribution permissions remain separate; successful APK
signing supplies no game entitlement. Provenance, privacy, licensing and
sensitive-content audit: 2026-10-24; J1095.

The J1098 native target-selection correction remaps object indices through the
existing audited link sequence; it changes no recipe/source/tool bytes or compiler
options. Its synthetic regression contains authored path/argument witnesses only.
Accepted ELF/symbol bytes are private comparison evidence, never build inputs.
Provenance/privacy/licensing and sensitive-content audit: 2026-10-24.
The J1091 diagnostic-retention correction changes authored `LabDiagnostics`
publication and the existing completed-session resource owner only. Fresh file
snapshots and startup discovery remain; periodic JSON is not sent to the original
console. Accepted-input field knowledge identifies the returned bullet-hit pool's
stale destroyed target. The bounded cleanup contains no copied original method
body and changes no hit result, live actor or pool storage. Host peers are authored
synthetic fixtures. Provenance/privacy audit: 2026-10-24; no game or snapshot bytes
are included and ownership/distribution boundaries remain unchanged.

The authored `LabPendingWriteStop` and its host case observe a native settings
pending transaction without changing player code or supplying file contents.
SDK APIs provide the observer and same-UID signal for the PID/UID-bound writer;
standard debug `run-as` selects that UID and refuses an unavailable grant. No Android source or
SDK binary is copied. Its DEX and unique temporary markers are generated from
tracked source, hash-verified and removed by the existing SDK tool workflow.
Raw pending files and recovery evidence stay private. Provenance/privacy audit:
2026-10-24; native device qualification remains separate from host compilation.
The actor explicitly exits and has a daemon deadline after inspection of the
Android 13 FileObserver thread lifecycle (AOSP android-13.0.0_r1); no platform
implementation is copied. Authored JVM fixtures exercise exit with a live
non-daemon peer and deadline termination. Initial settings bytes and observer
failure streams remain private evidence, not public fixtures.

J1102 adds authored APK input selection for the three explicit code outputs,
synthetic ZIP/tool witnesses, and documentation of the existing Vulkan linked
program response. No recipe target hashes, SDK implementation, decoded shader
bytes, original expression or protected content is published. Public smol-v
source is acquired privately for validation only, at its cited revision.
Provenance/privacy/licensing and sensitive-content audit: 2026-10-24.

The fixed-target Burst policy adds generic SDK compiler option/define metadata,
root names and exact acquired-tool hashes only. These define lists are the SDK
compilation API's hash inputs, separate from player compilation flags. The MCP
name contributes metadata only; no MCP DLL/code is rooted, copied or shipped.
Authored GNU adapters and JNI invocation launchers contain no SDK implementation
or game behavior. Their tools, generated libraries, source-derived outputs and
private keys remain local. Completed-object relinking reads explicit validated
owner outputs, never accepted ELF bytes. Public tests contain authored synthetic
ELF/command/path witnesses. Provenance/privacy/licensing and sensitive-content
audit: 2026-10-24; acquisition/distribution rights remain separate gates.

Generic Android SDK package transformation audit (J1109): the authored
`sdk_package.py`/`SdkAndroidCode.java` callers and fixed package settings contain
no SDK implementation, game Java, assets, captured bytecode or signing material.
Exact SDK/public-tool hashes identify owner-acquired inputs only. SDK Java and
resource data, generated classes/DEX/APK members and raw receipts remain ignored.
The fixed package label/settings originate in the lab's authored build setup.
The same transformation generates the two generic Android build metadata files:
the pinned AGP writer receives its schema/tool versions and absent AGDE version;
the Unity fingerprint serializes fixed authored build settings in the exact SDK
field order. No accepted metadata bytes, SDK implementation or game-derived
content is embedded in the caller. Provenance/privacy/licensing and sensitive
content audit: 2026-10-25; provider redistribution remains a separate gate.

The generic UnityFS/serialized writer and LZ4 helper contain authored wire-format
orchestration only. The separately acquired unchanged public LZ4 v1.9.4 provider
is pinned by archive hash; its BSD license/notices remain with private build
outputs. No game record, compressed block, schema snapshot, SDK implementation,
target byte literal or private path is embedded in the writer or its authored
fixtures. Structural target roundtrips remain private validation, independent
of source-only object production. Provenance/privacy/licensing and
sensitive-content audit: 2026-10-25.

`owner-pickup-objects.json` selects two legitimate original bundles, their object
and type identities, exact source/comparison hashes, checked PPtr extents and
destination/dependency/container relationships. It contains no object body,
type-tree snapshot, protected gameplay field value or target delta. The producer
copies source type trees and source-owned fields, relocates only those declared
identities and generates generic container metadata. `owner-player-data.json`
similarly records original script JSON selectors, fixed project assembly order,
font/material/texture selectors, checked pointer relationships and comparison
hashes. Font/image/body/type/dependency bytes come from original input; SDK and
fresh converter resources remain owner-supplied generated inputs. Assembly names
and source/target identities are minimum fixed-target reconstruction metadata,
not copied implementations. The five initializer identities are public authored
lab declarations. No private path, credential, native binary, target literal or
redistribution grant is added. Provenance, privacy, licensing and sensitive-content
audit: 2026-10-25; J1113. All game-derived output stays private.

J1115 extends `owner-player-data.json` with two original line-breaking text
selectors, the pinned authored `runtime-config.json` input and twelve original
standalone Sprite selectors. The Sprite operation regenerates only its importer
GUID/local identity from the destination filename and relocates a checked
texture pointer. Geometry, UVs, colors, text and source type identities are
read from legitimate input, never stored in the profile. The existing runtime
recipe is independently authored public configuration, formatted by its current
owner. No rendered image, font/text payload, encoded block or target field
array is included. The sprite texture file names are minimum dependency
relationships; texture production remains a separate owner/gate.

`owner-death-effect-objects.json` selects the original rooted prefab and its
MonoScripts, with checked pointer relationships and comparison hashes. All
non-reference fields and embedded type metadata come directly from the source;
there are no numeric overrides or serialized templates. External-first preload
ordering is structural metadata, needed by the measured target container.
Provenance/privacy/licensing/sensitive-content audit: 2026-10-25; J1115.
All game-derived outputs and raw discovery evidence remain ignored. No
ownership, authentication, entitlement or redistribution grant is added.

J1117 extends `owner-player-data.json` to all 63 PC-derived standalone Sprites
plus an authored full-rectangle Sprite and one original TimerStringFormatter
object, for 75 final player files.
Per-file source selectors refer to original PC bundles; source rectangle extents
select the variable-length Sprite render-data field. The 32 cropped records
recover rect/pivot/offset/border from original coordinates using the pinned
AssetRipper coordinate formula and float32 operation ordering. Geometry/UVs
and source type hashes remain original. No target coordinate, border, vertex,
image or text value is recorded. The one MonoBehaviour retains its original
body/type identity and relocates a checked script PPtr into a generated external
script table; its MonoScript identity is independently compared to the original.

`owner-teleport-material-objects.json` selects one original material/type tree
and three checked references, plus generated AssetBundle metadata. Its named
dummy-shader policy moves original valid keywords into the original invalid
list without adding strings or changing material values. The existing authored
scene owner explicitly retains this exported dummy shader; pinned AssetRipper
DummyShaderTextExporter confirms that shader export's scope. No shader program,
material array, keyword literal or target delta is in the profile. Source fields
are reused or transformed by these explicit source-coordinate/platform policies.
Provenance/privacy/licensing/sensitive-content audit: 2026-10-25; J1117.
All outputs and discovery/comparison records remain ignored; this grants no
ownership, authentication, entitlement or redistribution permission.

The one additional authored full-rectangle crosshair applies the existing
`RecoveredHudBuilder.cs` Sprite.Create policy. Original bounds/pivot/border/pixel
scale generate four corners and two triangles; no target vector, geometry or
byte template is in the profile. Its separately checked source/output extents
are required because this generated body changes size. All 64 standalone Sprites
qualify in J1117; original image/texture providers remain separate.
## SDK-assisted RGBA texture production

`owner-rgba-textures.json` contains only original/destination identities, byte
extents, hashes and importer/storage relationships for the 1,333 non-Alpha8
ETC2 RGBA/single-mip records. Canonicalization preserves original pixel hashes
and every unchanged field hash. Seven duplicated basenames select their exact
original object identities. All output pixels are derived from the owner's PC
bundles through decoding and the existing authored transparency transform;
no accepted pixel, encoded block or target byte frame is stored in the recipe.

The separately owner-supplied Unity SDK codec remains private under its provider
terms. Only the authored C ABI/pipe adapter and reproducible build instructions
are tracked; neither SDK implementation nor SDK binary is distributed. The
standalone Linux tool uses the separately acquired public QEMU/GNU runtime,
without an Editor/project workflow or game emulation. Local toolchain commands,
paths and dependency pins are generated in ignored output, not committed.

`tools/phone-build/accepted-output/third_party/bcdec/` contains unchanged public
bcdec source from `80859ed3b7afb1c527a2a99d70c61457bea72d0c` under its MIT
alternative, retaining the complete upstream license. The generic codec's
standard tables are public upstream material, not game or SDK-derived bytes.
The authored bounded `texture_pixels.c` pipe adapter uses its existing BC7 API
and independently implements the already qualified integer BC3 interpolation.
RGBA production now combines the already audited public ETCPACK EAC alpha
blocks with owner-SDK ETC2 RGB colour blocks. Both planes are derived from the
same original pixels and interleaved in standard block order; no target block
is a production input. The existing native ETC tool is an explicit pinned
dependency of this operation.
Provider identities and license selection are documented beside the header.
Provenance, licensing, privacy and sensitive-content audit: 2026-10-24. This
source/recipe audit grants no game/SDK redistribution rights or ownership,
authentication or entitlement success. Generated packs and raw evidence stay
ignored; whole-cohort phone qualification is separate.



J1118 extends the existing player profile with nine original TMP/material
selectors and 68 standalone texture mappings. The nine bodies and type
identities remain source-owned; 40 checked PPtr relationships and the existing
dummy-shader keyword policy introduce no target scalar or string values. The
texture mappings select existing producer profile/bundle/member/path IDs. Their
successful pinned packs supply original-input-derived bodies/pixels; assembly
only inlines those pixels and clears their former stream descriptor. Original
native Texture2D metadata comes from the already selected PC font bundle. No
pixel, shader, body/type-hash literal or serialized template is in this profile.
The complete cohort uses the separately audited RGBA producer/profile landed
in PR75; existing RGB/Alpha8/uncompressed providers remain unchanged. Provenance/privacy/licensing/sensitive-content
audit: 2026-10-25; J1118. Raw discovery, receipts and all generated content stay
ignored. Phone qualification and ownership/entitlement/distribution boundaries
remain unchanged.

J1118's `owner-bootstrap.json` uses the existing public fixed attempt identity
from `build-entry-inputs.json` and the accepted input identity. Four minimum
original `preloadGUIDReferences` relationships are selected from the original
Engi, Huntress, Reaperboss and Totem state records and independently confirmed
absent from the original Addressables catalog's decoded string keys. Their
sorted membership follows the existing `generate_build_bootstrap` policy.
The existing TextAsset writer reads its native type metadata from the already
selected original PC bundle and serializes this authored descriptor. No game
text, object body, type hash, shader, target byte frame or private identifier
is included. Full original field extents and membership proof stay ignored.
Provenance/privacy/licensing/sensitive-content audit: 2026-10-25; J1118.

J1120 audits `owner-objective-ui-objects.json`,
`owner-teleporter-indicator-objects.json` and
`owner-generic-pickup-objects.json` for provenance, privacy, licensing and
sensitive content (2026-10-25). Original PC selectors and comparison hashes
admit the accepted legitimate input. Local/external IDs, rooted preload sets,
Sprite importer GUIDs and native-resource paths are the minimum reconstruction
relationships. Source crop extents select original Sprite data; the existing
source-coordinate algorithm supplies every coordinate and geometry byte.
Texture profile hashes select independently produced record/resource packs;
no pixels or encoded blocks are included. Script bodies, properties hashes,
embedded type metadata and all non-reference values come from original input.
The GenericPickup component omission names its checked original AkGameObj
relationship, with remaining component order and GameObject bytes preserved.
The qualified dummy material policy moves original keyword strings without
introducing any string or value. No target type tree/hash, serialized body,
protected text, image, gameplay value, original implementation, credential,
private path or device identifier is stored. All generated bodies/resources,
raw comparisons and discovery artifacts remain ignored. This grants no
ownership, authentication, entitlement or content redistribution capability.

## Animation and generic object records

`owner-animation-clips.json`, `owner-animator-controllers.json` and
`owner-material-records.json` contain only
original source bundle/member/object selectors and hashes, destination
relationships/verification hashes and named transformations. Original type trees
are read from PC bundles; no source/target type-tree snapshot is tracked.
Animation policies select schema-typed float canonicalization, original
reference-pose removal, constant-curve folding, checked PPtr remaps and the
existing importer binding-attribute mask. No pose vector, curve coefficient,
event string, native controller value, state graph, target byte template or
arbitrary scalar replacement is present. Controller policies preserve original
state data while selecting complete clip/behaviour permutations, exported
path/name CRC regeneration, opposed-vector endpoint calculation and loop flags
read from pinned original clip leaves. Materials reuse checked original fields and the existing named keyword
demotion policy, preserving every original keyword string/value and total body
length. Source matching admits only unique original records with unchanged
native type identity; ambiguous matches remain excluded. These are partial
object cohorts, not independently assembled files.
Provenance/privacy/licensing/sensitive-content audit: 2026-10-25; J1119.
All discovery evidence, source bodies and generated packs remain ignored;
this grants no game/SDK redistribution, ownership, authentication or entitlement
permission. Host and ordinary-app/device qualifications remain separate.
The pixel helper's experimental mip modes use authored float32 box filtering
and sRGB transfer formulas, checked against nongame authored-image observations
from the exact SDK. Host tests retain hashes of those authored observations,
never protected pixels. BC4/BC5 decoding consults AssetRipper TextureDecoder
2.6.3 `Bc4`, `Bc5` and `BcHelpers.SmoothAlphaBlock`, the version selected by
AssetRipper `1ac666f47d8e9dedf96afb0b914c70d7656151ea`. Its channel layout and
one-unit interpolation bias explain the independent source-image comparison;
the bounded C adapter is authored here. No BC4/BC5 game output or mip-derived
literal table is distributed. Whole game-cohort and Android checks remain open.

`owner-rgb-mip-textures.json` extends the same source-only texture owner to
1,589 ETC1 mip-chain records, using 1,548 canonical source transformations from
380 original PC bundles. SHA-256:
`380d6d4c2a7f64db1bac10cefa0c6d31ec7cbfb1e817cd4fd2d7067643cb4283`.
The nine selected fields add mip count and colour space to the existing seven
texture fields. Remaining metadata is copied from the original object. Flags
select source normal unpacking/JPEG policy and destination mip/normal handling;
all content comes from original pixels. Duplicate names select the exact PC
bundle/member/path-ID instance. A `.jpeg` original follows the same authored
JPEG round trip as `.jpg` inputs. No exporter image is a production input.

The vendored Unity Crunch material is unchanged public decompression source
from `Unity-Technologies/crunch` commit
`8708900eca8ec609d279270e72936258f81ddfb7`, selected by the pinned AssetRipper
conversion package. Its complete Zlib notice and origin are retained beside
three headers. The authored pipe adapter validates dimensions, one face,
DXT1/DXT5 format, bounded input/output and decode success before writing bytes.
It emits only the owner's decoded top BC level; the existing native pixel/mip
and public ETC tools derive every target level. The compiler disables strict
aliasing for the header adapter as required upstream; ETCPACK objects keep their
existing compiler flags. A separate authored malloc compatibility header handles
host compilation, without changing upstream source.

Provenance, licensing, privacy and sensitive-content review: 2026-10-24. Only
source selectors, hashes, format/import flags, names and storage relationships
required for reconstruction are published. No protected pixel/block/curve table,
SDK implementation or target frame is included. Full public-producer and Android
qualification remain separate gates; generated packs and raw evidence stay
ignored. Provider licenses grant no game or SDK redistribution permission.


`owner-rgba-mip-textures.json` extends the existing source texture owner to
1,523 full-chain RGBA records: 1,519 bundle records and four standalone player
records. The 1,399 canonical source transformations select 319 original PC
bundle entries. Profile SHA-256:
`723c4e641349941a172aef28d6a4b23eee2954c5390cd7257a75a54cd0bf66fd`.
It contains original bundle/member/path-ID selectors, field/pixel extents and
hashes, destination identities and import/storage relationships. The nine-field
projection preserves all unselected source metadata. Seven ambiguous original
names are resolved by exact target/source identities; there is no name-wide
pixel override. Every decoded, extended, filtered and encoded pixel comes from
original PC input. No exporter image or accepted target byte supplier is read
by production.

Provenance, privacy, licensing and sensitive-content audit: 2026-10-25; J1128.
This profile carries no pixel/block literals, serialized templates, proprietary
implementation, private path/device identity, credential or SDK bytes. The
existing public BC/Crunch decoders and ETCPACK retain their prior notices; SDK
compression uses the separately supplied permitted toolchain. Authored mip
controls observe only generated nongame patterns. No game/SDK redistribution,
ownership, authentication or entitlement success is granted. Generated packs
and raw evidence remain ignored; host equivalence and Android qualification
are separate gates.


`owner-cubemap-textures.json` selects 110 source-derived Cubemap records from
68 original PC bundles. SHA-256:
`319691fd4c11591b87b4aae654b00a1cd7789105b43be2cd52a090bb98cb2526`.
Its source selectors, field/resource extents, hashes and destination import/
storage relationships use the existing texture profile shape. Original
AssetBundle container paths resolve renamed/unnamed originals without retaining
exported images. The 50 ordinary ETC1, 56 HDR ETC1 and four RGBA records regenerate
all six faces and their mip chains from original top-level pixels. The 13
unresolved native reflection cubes are absent; this profile supplies no fallback
for them.

Provenance, privacy, licensing and sensitive-content audit: 2026-10-25; J1128.
Only reconstruction identifiers, comparison hashes and generic import/storage
settings are distributed. No target pixels, mip/block literals, serialized
body/type templates, protected implementation, private paths/identifiers or
credentials are present. The unchanged public bcdec decoder retains its MIT
alternative notice; authored BC6 byte/export-half/DoubleLDR transformations are
source algorithms. Existing ETCPACK/SDK acquisition and licensing boundaries
apply. Pinned AssetRipper TextureConverter/ExrWriter source informs face strides,
orientation and export half conversion; no upstream implementation or exporter
image is copied. Provider terms grant no game/SDK redistribution, ownership,
authentication or entitlement capability. Generated packs remain ignored.
The GameObject/Transform record profiles select only uniquely matched original
records with equal native type identity. Every non-pointer byte remains source
owned, including original component entries and local position/rotation/scale.
Only checked original-to-destination PPtrs change. No graph/body template,
component scalar, coordinate, target value or arbitrary byte patch is present.
Profiles are compact JSON because the admitted hierarchy cohort has 203,803
destination relationships; this changes no parser or recipe format.
Provenance/privacy/licensing/sensitive-content audit: 2026-10-25. All original
content, produced packs and discovery evidence remain ignored; no ownership,
entitlement or redistribution grant is added.

The generic record profile admits eleven additional original classes, including
MonoBehaviour/ScriptableObject, particle data, renderer/collider/settings and
RectTransform records. Matching requires equal class ID, native type hash,
script identity and every non-pointer body byte, with exactly one physical
source. The producer changes only checked PPtrs; scripted metadata is passed
through, and this cohort does not use the separate script-hash recomputation
policy. No code, gameplay state, particle curve/value, native body/type template,
coordinate or arbitrary byte patch is recorded. Provenance/privacy/licensing/
sensitive-content audit: 2026-10-25. Outputs and raw matching evidence stay
ignored; final bundle/player integration and phone qualification remain open.

The expanded animation profile additionally selects native coefficient packing,
source-binding permutations/constant folds, dense endpoint repetition and
source quaternion normalization. Root quaternions use original indexed delta
endpoints, not target poses. Binding permutations move complete stream keys,
delta ranges and root indices together. Dense signed-zero import rules operate
only on the selected original samples and ranges. All coefficients, quaternion values, dense
samples and delta ranges are computed from original values; the recipe contains
only source ordinals, field-policy flags and verification hashes. It contains
no target sample, pose, curve coefficient, range or byte patch. The existing
pointer/attribute transformations remain checked original relationships.
Provenance/privacy/licensing/sensitive-content audit: 2026-10-25.

`owner-enemy-reward-objects.json` is audited for provenance, privacy, licensing
and sensitive content (2026-10-25). Original PC object/body/type selectors,
checked pointer relationships and component omissions reconstruct the selected
rooted effects. Container roots, dependencies and preload partitions are
audited minimum reconstruction relationships; accepted outputs informed their
discovery but supply no body or type template. The two mesh bodies are
unchanged original records, already covered by the source mesh qualification.
The SDK selector names a native MonoBehaviour base schema in the separately
supplied pinned toolchain. Original MonoScript identity strings and original
MonoBehaviour custom fields feed the existing source hash helper. No target
properties/type hash, serialized tree/body, protected text, pixel, geometry,
shader, gameplay scalar, private path/device identity or credential is stored.
Generated records, raw comparisons and source discovery remain ignored. This
recipe grants no ownership, authentication, entitlement, SDK/game acquisition
or redistribution capability; phone execution and complete installation remain
separate gates.


`owner-villagenight-objects.json` is audited for provenance, licensing, privacy
and sensitive content (2026-10-25). It contains original PC bundle/member/object
selectors and hashes, checked local/external pointer and component relationships,
source-produced mesh selectors and comparison hashes. Original bodies and embedded
type metadata are read locally. Scene/container/member identities and dependencies
are minimum reconstruction relationships, never serialized templates. The named
inactive MapZone policy retains the existing authored scene export behaviour.
The omitted ReflectionProbe bake is represented by a checked null PPtr. No
original scene text, geometry, pixels, shader, gameplay scalar or serialized
body/tree is distributed; raw discovery/output/comparison data stays ignored.
This grants no game/SDK redistribution, acquisition, ownership, authentication
or entitlement permission. Host and phone qualification remain separate.

`owner-helminthroost-objects.json` receives the same provenance/licensing/
privacy/sensitive-content audit (2026-10-25). Its original PC/source-produced
mesh selectors, hashes and checked scene relationships require no additional
body/type transformation. The existing component omission, inactive MapZone
and original bake omission policies apply. It stores no original scene text,
geometry, pixels, shader, gameplay scalar, serialized template, private path,
device identity or credential. All raw outputs/evidence stay ignored. No game/
SDK redistribution, ownership/authentication or entitlement capability is granted.

J1126 extends `owner-player-data.json` with seven original material selections
and the six-object built-in UI file. Material names follow the existing authored
HUD importer names; original shader property declarations select retained
texture environments, preserving every other source value. The built-in file
selects six SDK object IDs and strips source-schema-identified editor fields.
Its pixels, geometry, physics and bone records remain SDK-owned; native runtime
type identities come from the already selected original PC font/Sprite files.
The caller supplies the exact pinned `Resources/unity_builtin_extra` explicitly;
no SDK data, original object bytes, shader programs, scalar overrides or target
templates are tracked. The profile contains minimum source/dependency identities
and comparison hashes. Provenance/privacy/licensing/sensitive-content audit:
2026-10-25; J1126. SDK acquisition and use remain subject to the owner's Unity
rights; all generated content and raw evidence remain ignored.


`owner-player-shader-manifests.json` selects 4,904 original Material records and
12 original Shader declarations for the two native selection TextAssets. Bundle,
member and path IDs, source asset identities, relationship selectors and hashes
are the minimum inputs needed to reread the existing shader-selection policy
from the owner's original files. Embedded schemas locate fields at runtime; no
keyword inventory, shader program, material value, text payload or serialized
target template is stored. The player profile pins this sibling recipe.

Provenance, privacy, licensing and sensitive-content audit: 2026-10-25. The shared
pure metadata functions are factored from existing authored shader generators;
no extracted upstream implementation or AST-extraction mechanism is distributed.
Source selectors grant no game or SDK redistribution rights, ownership,
authentication or entitlement capability. All generated JSON, original fields
and raw evidence remain ignored. Compiled Shader production and phone
qualification remain independent gates.

The player profile additionally selects six original TMP font objects and one
SDK native MonoBehaviour base from the explicitly supplied `unity editor
resources`. Original MonoScript identities and schemas feed the existing public
properties-hash algorithm; no destination type hash or schema is stored. Source
script relationships are admitted before hash derivation. Four standalone mip
textures consume the landed public RGBA mip profile without changing its producer
or storing pixel data. Provenance/privacy/licensing/sensitive-content review:
2026-10-25. Only required source selectors, dependency relationships and
comparison hashes are added; original SDK/game files and raw evidence remain
private. The existing SDK acquisition and use requirements apply.

Shared shader-policy factoring also refreshes existing generator helper pins,
their recipe pins and all seven current catalog override pin pairs. The change
introduces only authored helper identity hashes, without altering original
shader-selection identities or relaxing source admission. Review: 2026-10-25.

`owner-habitat-objects.json` and `owner-habitatfall-objects.json` receive the
same provenance, licensing, privacy and sensitive-content audit (2026-10-25).
They store only original source/type selectors, comparison hashes, checked
scene/component/PPtr relationships and qualified mesh/cubemap profile selectors.
Original billboard body/type bytes are supplied by the PC input. Native scene
metadata is generated; inactive MapZone/component/bake policies are unchanged.
No protected geometry, pixels, scalar, scene text, serialized template, private
path/device identity or credential is published. No game/SDK redistribution,
ownership, authentication or entitlement capability is granted. Generated
content/raw evidence stays ignored; host and phone gates remain separate.


## Wispgraveyard source relationship audit

`owner-wispgraveyard-objects.json` receives provenance, privacy, licensing and
sensitive-content review on 2026-10-25. It contains original PC object/type
selectors, hashes, checked component/PPtr relationships and an existing
qualified mesh-pack profile. Original bodies, type schemas, geometry and scene
values remain owner-supplied. Component omissions follow the accepted reduced
diagnostic scene export and extend beyond native audio; they do not authorize
new gameplay changes. Native metadata is generated from the produced graph.
No body/tree/scalar template, private path, device identifier or credential is
published. There is no additional game/SDK redistribution, ownership,
authentication or entitlement grant. Generated content/raw evidence stays
ignored; J1142 records host qualification with the phone gate open.


## Full scene source policy audit

`owner-itskymeadow-objects.json`, `owner-solusweb-objects.json` and
`owner-itancientloft-objects.json` receive provenance, privacy, licensing and
sensitive-content review on 2026-10-25. They contain original PC object/type
selectors, SDK selector/hash, checked component/occlusion/bank/schema policies,
Sprite GUID relationships and existing qualified record-pack identities.
Solusweb's minimum preload relationship includes original source membership
and hashes; its destination agrees with the existing source GameObject recipe.
The CharacterMaster field name is required transformation metadata, not a
copied schema or implementation. Ancient Loft's GUID uses the current accepted
input export and scene relationship. All original bodies/type schemas, scene
values, geometry and pixels stay owner-supplied. No accepted template, scalar
patch, private path, device identifier, credential or additional redistribution,
authentication, ownership or entitlement grant is introduced. J1145 owns the
complete host evidence; phone and runtime gates stay open.

The player profile additionally selects the current original English JSON files
for the existing authored `StageStrings` transformation and the fifth original
font-material clone. Language entries are source paths, byte counts and hashes;
the material selection contains original object/shader relationships and checked
pointer relocations. No game text, cached token table, material scalar, serialized
body, historical input path or target-byte override is included. Output hashes
identify the deterministic current-input files, whose historical-input drift is
qualified separately; they do not assert exact J850 equality.

Provenance, privacy, licensing and sensitive-content audit: 2026-10-25. Original
current files are reread and checked through output completion. Historical
originals remain private qualification inputs and are never required for owner
reconstruction. Serialized destinations retain the fixed Android toolchain
identity and original native schemas. These selectors grant no game/SDK
redistribution, ownership, authentication or entitlement capability. All original
text, material values, generated files and detailed drift evidence stay ignored.

`owner-ai-test-objects.json` and `owner-testscene-objects.json` receive the same
provenance, privacy, licensing and sensitive-content audit on 2026-10-25.
They extend only the existing original-body/type selectors, checked pointer
relationships, SDK schema and mesh/texture pack identities. Their icon Sprite
GUIDs are checked against the current accepted-input export, its input receipt
and the corresponding original scene reference. Testscene's additional preload
GameObject is checked against the original preload membership and member
identity; it is not a target body supplier. CharacterMaster uses the existing
guarded final-field body/schema omission and original custom-field hash owner.
No new scalar policy, schema/body template, protected media, private path,
identifier, credential or redistribution/ownership/authentication grant is
introduced. Generated data and raw evidence stay ignored. J1150 owns the full
host results; Android and complete installation remain open.

### Source-derived player Shader profile (J1144)

`owner-player-shaders.json` is an authored selection for the bounded complete
authored/original native/font and SDK builtin producer. It records only the accepted original-input identity,
original native-schema/Shader/material provider paths/members/path IDs and hashes, public authored
source/settings pins, acquired SDK tool/include-inventory pins and explained
build settings. Output names and final size/hash are comparison contracts after
source-only generation. They supply no Shader body, type-hash literal, program,
include contents, game math, target pass key or serialized template.

Provenance/privacy/licensing review: the fourteen authored shaders are existing tracked
lab-authored identity/visibility/presentation passes; native schema and builtin registry remain sourced
from the owner's legitimate PC files. Platform defaults and compiler-version data
are read from the exact owner-acquired SDK, never shipped as SDK binary data.
The existing public LZ4 provider retains its upstream license; the SpookyHash V2
algorithm is public domain and its test vectors use authored bytes. No protected
input, private path, account/device identifier, credential or generated shader
output is added. This audit authorizes tooling/selection metadata only, with no
new redistribution or ownership claim. Full evidence and remaining gates are
recorded once in J1144/J1146/J1147/J1151/J1157.

The original UI Alpha extension selects one original Shader and two original
Materials, derives their feature sets and regenerates every selected original
program through the existing pinned public d3dasm/NativePrograms owner. Original
property/render state is source-owned; generated HLSL and Android variant/native
records remain private. The existing source emitter is factored without changing
its generated ShaderLab. No retained decompilation, original body/template,
accepted Shader program/table or target key is embedded in the recipe. The public
MIT-licensed decompiler is separately built and caller-supplied with a hash;
this audit grants no distribution right for the resulting game-derived HLSL or
Android files. Manual extension review: 2026-10-25, J1147.

The Cloud extension reuses the existing audited shader-manifest material policy,
selects original Shader/material relationships and regenerates the qualified 113
feature sets through the same original-program recovery/compiler. The source
emitter factoring retains existing generated text; no broad replacement census,
retained source, native body, original program or accepted table is shipped.
The Particle/Water extension reads existing tracked authored source and build
fog settings. Only selectors, authored-source/tool identities and postproduction
comparison hashes extend the existing recipe. Manual provenance, privacy,
licensing and sensitive-content review: 2026-10-25, J1151. This introduces no
SDK/game redistribution or ownership/entitlement grant; phone qualification
remains open.






Collision-policy restoration refreshes the authored world-owner, producer and
transitive camera source pins. The world change observes the original projectile
collision contract before gameplay; the producer reads the verified legitimate
input and restores only generated project settings. No original matrix values,
game source, protected assets, device identifiers or private paths are tracked.
The source camera and original audio transformations retain their existing
ownership and behavior. Provenance/privacy audit: 2026-10-24; device impact
acceptance remains separate.


PR #68 integration refreshes the actual authored owner and camera source pins
after combining current main's touch/settings, idle heap capture and diagnostic
retention with source rendering, Siren lifecycle and collision-policy changes.
The existing editor-source staging and audio restoration owners remain in use.
No original input, protected bytes, middleware selection, account entitlement
or ownership boundary changes. Audit: 2026-10-24; a newly built normal player
and device checks remain required for the integrated source.


The automatic Huntress landing candidate after J1105 changes only authored
diagnostic input admission in the existing world/objective owners. It reads
original state configuration through native constructors and existing imported
assets, measures the current source scene, and releases at most two inert state
references at existing teardown. Original state implementations/configurations,
physics and legitimate input remain unchanged. No new private build input,
source implementation, original asset bytes or runtime export is tracked; the
existing world-owner source pin is refreshed for the reviewed authored change.
Host and editor contracts remain separate from Android route acceptance.


The destination MainOutput candidate adds only an explicit per-run arm gate and
owned scalar witnesses in the existing session, plus its public diagnostic
runner/tests. It reuses the accepted one-shot capture and original authority
callback without changing native audio ownership, bank data, event routing or
provider generation. It adds no build input, SDK payload or original bytes to
the repository. Existing first-stage defaults remain unchanged; original audio
playback and destination statistics require separate device evidence.

The destination arm gate refreshes the existing `PortSession.cs` source pin,
its owner-recipe digest and the dependent producer/camera provenance pins.
Only that reviewed authored source changes in the frozen owner cohort. These
checks remain mandatory; the normal player build must regenerate its source-bound
bootstrap rather than reuse an older frozen payload.

The follow-up mobility correction counts complete native fixed ticks when
predicting automatic Blink admission. An authored ledge fixture distinguishes
the nominal endpoint from the actual endpoint; an inert exact-editor machine
executes only the original clock callback, with no motor or network authority.
The Engineer Laser Cutter fixture reads minimal original config/asset identities,
applies the native config APIs to inert states, inspects their native phase
construction and restores every captured static. It retains no original config
payload, implementation, audio or asset bytes in Git. These are authored contract
checks and an input-admission correction, with device behavior still unverified.

J1152 integration refreshes direct and transitive shader-helper hash pins after
merging current main's metadata validation with the source Sobel producer.
Manual provenance/privacy review retains existing authored tooling and recipe
selectors only; no protected content or new build input is introduced. Frozen
R58 predates this integration; no device qualification is implied.
`owner-windows-shaders.json` receives a provenance, privacy, licensing and
sensitive-content audit on 2026-10-25. It names only the current original file
and its length/integrity hash, preserving the unchanged-file copy already owned
by `prepare.py`. It contains no shader program or protected asset bytes.
Historical originals qualify the same copy transformation against J850 only;
the current reconstruction uses the current legitimate installation exclusively.
Its current output is drift-explained, separate from exact reconstruction.
The recipe grants no redistribution, ownership or authentication rights.

`owner-wispgraveyard-source-objects.json` receives the same provenance,
privacy, licensing and sensitive-content audit on 2026-10-25. All curve operands
come from original behaviours and Transform hierarchies; the recipe contains
only their selectors. The authored mathematical reconstruction introduces no
curve samples, numeric delta or copied game implementation. Named global-owner
suppression follows the existing source-scene import policy. Current Sprite
GUIDs are checked against the current accepted-input export and original scene
references. Independent review checks every original-schema pointer extent and
source value; equivalent source wind/mesh relationships remain explicit.
The compact JSON decodes identically to the audited profile. No protected body,
type tree, media, private path, credential, account or redistribution grant is
included. J1155 owns the complete host result; phone qualification remains open.

The four compressed hierarchy-record recipes contain only original bundle,
member and object selectors/hashes plus destination identities, verification
hashes and checked PPtr relationships. They preserve every original non-PPtr
byte and native/script type identity. Discovery anchors identity through
qualified Transform/RectTransform graphs and component backlinks, excluding
conflicts; body fingerprints alone do not seed GameObject identity.
Provenance/privacy/licensing/sensitive-content audit: 2026-10-25. A complete
field whitelist walk admits 2,498,566 rows with no value, float, curve, code,
body or type template. Compression is deterministic metadata storage, required
to keep individual public files below the hosting limit. JSONL source groups
are bounded to 8 MiB so phone production need not load the whole cohort;
the staged public audit expands and scans every group. Existing CLI and output
pack fields remain unchanged. J1143 qualifies full public host execution and independent persisted comparison;
no phone, assembled-file or runtime result is implied. All bodies,
raw source/target evidence and generated packs remain ignored. This grants no
game/SDK redistribution, ownership, authentication or entitlement permission.


The expanded animation/controller policies derive root-average motion, merged
Hermite coefficients, equal-curve ordering, material path CRCs and controller
clip/state/behaviour relationships from original source values and selected
source identities. Complete equal binding/channel/delta checks precede duplicate
binding collapse. Controller loop flags come from hash-pinned original clip
leaves, not recipe booleans. Provenance/privacy/licensing/sensitive-content
audit: 2026-10-25; J1143. The profiles contain source ordinals, named operations,
selectors, hashes and relationships; no target float/scalar/body/type template,
SDK implementation or private identifier. Existing source, SDK, ownership and
redistribution boundaries remain unchanged. Generated content stays ignored.

The remaining standalone Shader extension retains the same audited selection
profile. Native wrapper feature sets come from the shared original-material
policy; original DXBC is interpreted locally by pinned public tools. The optional
portable HLSLDecompiler provider is built from its pinned public MIT source with
license notices retained in the local output. SDK disassembly supplies fresh
assembly to that provider; retained decompilation and generated programs are
never recipe inputs. The producer preserves the existing source emitters and
uses source declarations, original material use and authored build settings for
variant retention.

The three AssetRipper dummy font exporters consume explicitly supplied,
content-pinned resources from the recorded upstream revision. Those GPL-3.0
resource bodies are acquired locally and are not vendored into the public
Python/recipe. Their existing original-property export policy is reproduced;
it does not recover the original font shader implementation or qualify visual
parity. The remaining mobile font pass reads the acquired SDK's pinned TMP
package and applies only the recorded authored Shader declaration rename, with
original FontMaterial relationships deciding used feature sets. No template text,
original property value, retained ShaderLab, native table or accepted body is
published. Source/tool identities, selectors and comparison hashes grant no
additional upstream/game/SDK redistribution, ownership or entitlement rights.
Generated source, compiler data and final bodies remain ignored locally.
Provenance, privacy, licensing and sensitive-content review: 2026-10-25.

The SDK builtin/shared extension reads the pinned acquired SDK's source forms,
snippets and declarations. The builtin closure is reconstructed from original PC
Shader IDs, source GraphicsSettings and the Android video resource relationship;
missing SDK identities and source-empty forms are excluded by source state.
Original PC native schemas supply serialization identity. The existing public
writer frames the builtin file; source material references allocate shared
Standard/Skybox IDs and their builtin-resource dependencies. The shared output
uses the existing object-pack contract. No accepted record roster, header/body,
compiled shader, target type hash or native program is a supplier. Vulkan's
stage-owner count follows the acquired SDK's initialization/transfer contract,
including zero-job shaders. Global constants and structured instancing buffers
use source SDK callback/layout contracts. Updated historical candidate helper
pins reflect the existing emitter factoring, with no previous source-generation
behavior change. Manual audit: 2026-10-25, J1157. All SDK/game/source-derived
bodies and detailed observations remain local; existing acquisition, license
and redistribution boundaries continue to apply.

### Retained Barrier source profiles

`owner-barrier-objects.json` and `owner-barrier-shaders.json` receive provenance,
privacy, licensing and sensitive-content review on 2026-10-25. These authored
selectors reconstruct the fixed retained Barrier build from current legitimate
originals. Its source engine metadata, Gamma settings and default Android tiers
follow its original build lineage. The SDK33 files are separately acquired
source/hash metadata; only the pinned SDK45 standalone compiler executes.
The public pinned AssetRipper template is acquired separately with its license.
No original Shader, SDK include, generated ShaderLab, compiled program, type
tree, pass hash or target table is stored in either recipe.

The named legacy AnimateShaderAlpha import projection removes only two checked
zero-valued additions in current original records and derives the corresponding
hashes through the existing SDK editor-schema owner. The historical original
DLL/prefab qualifies that retained shape only; production opens neither. The
PluginImporter default-order policy changes one checked original script field.
All other source bytes remain original apart from checked pointer relocations
and existing qualified media transformations. The independent source audit
checks actual original PPtr spans and script/component relationships. This
metadata grants no game/SDK redistribution, ownership or authentication rights.
Generated objects, resource streams, templates and compiler logs remain ignored.
Phone reconstruction, installation and runtime qualification remain open.

`owner-rootjungle-postprocess-shaders.json` receives the same provenance,
privacy, licensing and sensitive-content review on 2026-10-25. It selects 24
current original Shader forms and their original source-body hashes, public
Default/SingleTexture templates and the current acquired SDK45 context. Original
PostProcessResources relationships and current export GUID metadata independently
qualify its authored filenames; exports are never production suppliers. The
profile contains no template text, executable, reflection, type tree, key or
accepted record table. Fresh SDK compilation qualifies identical native programs
for the selected Android quality tiers, including the original 2DArray property.
One produced extent serves both explicit destination relationships through the
existing record-pack contract. This closes no final Rootjungle bundle by itself.
Original content, generated source, SDK data and compiled outputs stay ignored;
no new redistribution or ownership right is granted.

The three `owner-*-standard-shaders.json` profiles receive provenance, privacy,
licensing and sensitive-content review on 2026-10-25. They select current
original Material/Shader relationships and supplied SDK45 Standard source.
Original scene/retained authored dependency relationships explain the bounded
material seeds: Default/DebugRed/JunkShrineRock for the whole context,
Default/DebugRed for Gold spine and Default/Green for Root spine. Original
DebugRed enables emission and instancing; Green enables emission without
instancing. Source fog and actual lightmap/renderer usage qualify runtime
retention. Baking preferences alone do not establish a runtime lightmap.
The same source-derived row order drives the shared SDK compiler's native pool
ordering; no accepted record/index mapping is read. Original and SDK fallback
relationships resolve the explicit destination resource identity.

Only selectors, tool/source pins, authored context and destination identities
are tracked. Neither historical game inputs nor exported scenes/templates,
programs, native records, type trees, scalar replacements or target tables
supply reconstruction. Generated source, compiled content and raw evidence
remain ignored. The profiles grant no ownership, authentication or SDK/game
redistribution rights. Complete bundles and phone acceptance are separate gates.

The three `owner-goldshores*-objects.json` profiles receive provenance, privacy,
licensing and sensitive-content review on 2026-10-25. Their compact authored
JSON contains only current original object/type selectors, checked pointer
relationships, current input GUID relationships, named import policies and
qualified media/Shader profile identities. Independent schema audits verify
original pointer extents/values and source script/component relationships.
Existing owners derive mesh/texture records, script identities, scene tables
and preloads; no generated object or type-tree template enters a recipe.
The profiles carry no historical input requirement, credential, private path,
protected body, curve, geometry, pixel or program. Original/SDK data and all
produced bundles stay ignored; no redistribution or ownership right is granted.

## Complete player registry and default-scene recipe audit — 2026-10-25

`owner-player-registry.json` selects one canonical original witness per unique
script identity/schema, with the source MonoScript member needed to resolve
those relationships. Paths, member names, type indexes, source hashes and CLR
identities are minimum reconstruction metadata. The source census, never an
accepted comparison, determines membership. No tree bytes, object bodies, DLLs,
decompiled implementation, protected text, pixels or middleware are included.
The original PC installation remains read-only. Its original bundles and native
startup file supply all game-derived records locally.

Authored source membership and known importer identities come from the existing
public J850 source/configuration and current public identity maps. Siren's one
previously unset importer identity is preserved from the current authored
project as explicit recipe configuration. It belongs to the laboratory's own
C# source; its raw generated `.meta` file is not published. The adjacent archived
J850 source/meta pair is unavailable: source admission establishes the existing
current importer, stable class/path/assembly and observed pre-J850 timestamps,
with that provenance limitation retained in the private audit. This does not
introduce a historical game-input dependency, an implicit identity fallback or
a change to the current game project's importer map.

Original package source/meta pairs use the existing code-owner input contract:
archive-qualified Burst, Collections and Mathematics, exact SDK UGUI and
TestRunner sources, and the pinned public MCP runtime source/asmdef/meta set.
Importer-only sources do not change compilation membership. Dependency source
licenses and SDK acquisition/ownership boundaries remain with their existing
providers; none of their binaries or source bodies is copied into this recipe.
`dnfile` and `pefile` are existing pinned metadata-reader dependencies.

The implementation uses pinned AssetRipper/ThunderKit importer identity
knowledge and AssetRipper's CLR field/generic serialization rules. Exact native
field-transfer facts are verified on an authored SDK-only fixture. Its generated
binary is private verification evidence, never a production provider. Native
hashes are computed from original schemas and actual CLR metadata; an explicitly
unsupported native contract may retain its original record only when its DLL
provider is unchanged. The recipe contains no comparison-selected replacement
hashes or destination script-ID table.

`owner-player-data.json` also names the original startup/shared source records
and Wisp native RenderSettings witness for the default-scene file. Runtime native
type identity must match before schema reuse. SDK resources, source-produced
shader declarations and the existing shader object pack supply the other
records; the authored Cube/diagnostics construction policy selects preloads by
source identity. The shared writer owns allocation/linkage, with no target
header or captured metadata template. All source and pack providers are checked
again at completion. Pattern scanning supplements this manual provenance,
privacy and sensitive-content review; phone/runtime qualification is separate.

## Root and PP scene object profiles (J1170, 2026-10-25)

The six profiles below select current original object/type records, checked
pointer relationships, source GUID relationships and existing named import
policies. Their source-only producer is the existing `object_produce.py`;
media and Shader bodies arrive through independently produced record packs.
No new producer or runtime owner is added.

| Recipe | SHA-256 |
| --- | --- |
| `owner-rootjungle-objects.json` | `6e17c9e40ced968b73cb4d27956217b7b04bbb0293585e13f267ee3983d9402b` |
| `owner-rootjungle-source-objects.json` | `6fecc35de3b3aac0ca7ee34af3542a803ed12cae2a409f40952f3553354e42e4` |
| `owner-rootjungle-spine-objects.json` | `99ca43f8d6c2e61189338e0ebdef428df266615024233d3185fcf7c667a29c8d` |
| `owner-mysteryspace-objects.json` | `c3441252ca1efb648ca73b59122c1b8fbdffcd6a58986826f904f77d7730e246` |
| `owner-eclipseworld-objects.json` | `4c0aa1fd65112878256bcf3dc295825adaaeafcb86a5a4de84690a95204c77b7` |
| `owner-helminthroost-source-objects.json` | `897151fdc9fc781e80b3fdec37aa7bd8554cbc976d23eb4af0aaf063fbfbdbe5` |

| `owner-eclipseworld-postprocess.json` | `40110337a0dcbf92c7d1f96665dc73c37c0d357b2ead9fad5574090d4e46b68d` |
| `owner-helminthroost-source-postprocess.json` | `b2ffee927b6d87cb2dd013f29e4868ace34ecaf92362b838a7b7dbb0fe8ba4a6` |
| `owner-mysteryspace-postprocess.json` | `e8325b36e76478f734e4f243858c87d00afb1ee0bdbad4206f2b926ba94aea2a` |

The three `owner-{mysteryspace,eclipseworld,helminthroost-source}-postprocess.json`
profiles are byte-unchanged qualified peer selector recipes for the existing
source Shader carrier. They pin SDK/public-tool inputs, authored build settings,
original Shader identities and source-derived export paths/destinations; they
contain no ShaderLab, template text, native program or serialized body.

Manual provenance, privacy, licensing and sensitive-content audit: 2026-10-25.
All nine recipes contain only selectors, pins, checked relationships and
authored policies. Object profile compaction preserves every decoded value.
No private identifiers, copied game source, original scalar/curve/pixel/body
values or target type-tree templates are published. Current originals and
explicitly acquired SDK/public resources remain required; no historical file
is a reconstruction supplier. Generated content and raw evidence stay ignored.
Existing ownership, license and redistribution boundaries remain unchanged.

The Shipgraveyard post-processing, Repurposed Crater HideVertices and
TestOtherBrother Skybox Shader profiles receive provenance, privacy, licensing
and sensitive-content review on 2026-10-25. Only original selectors, hashes,
source relationships, public-template/SDK pins and destination identities are
tracked. No game/SDK source, program, target keyword table, private path or
credential is included. All generated content stays ignored; these profiles
grant no ownership or redistribution right. Phone execution remains open.

The four `owner-{blackbeach2,shipgraveyard,testotherbrother,repurposedcrater}-standard-shaders.json`
profiles receive provenance, privacy, licensing and sensitive-content review on
2026-10-26. They contain original material/scene selectors, source and SDK hashes,
authored compiler settings and destination identities. Recursive original pointer
closure determines the selected material features; no target program, keyword
table, source text, private path or serialized body is included. The existing
Shader owner generates private packs; all original/SDK inputs remain external.
These recipes grant no redistribution or ownership right; phone gates stay open.

| Recipe | SHA-256 |
| --- | --- |
| `owner-blackbeach2-standard-shaders.json` | `941f10f7aa298fdc02ad5ab09aed57a86178b2e242ac0f577d7d31d6a6ea8d9e` |
| `owner-repurposedcrater-standard-shaders.json` | `b54f8b21390941b606c1f3d1bf94763d34bebc05d2146345524aed52319d32ab` |
| `owner-shipgraveyard-standard-shaders.json` | `4f4a62fa2e02f7d6b3c7f2f297f65ed0fb9e06326068b5ebddc43fad22f80cdd` |
| `owner-testotherbrother-standard-shaders.json` | `7912dc1de94cd12163c793463be09b106461671911116d062e1cfd4f5a0dd963` |

## Five complete scene object profiles (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-logbook-objects.json` | `f22910dea81582365fdc3bb5660af38e6bcbbfec33c8c7d4ac2e5bd2b033a5b8` |
| `owner-blackbeach2-source-objects.json` | `742d0f289dbb6cca936859f5bd9b0cdb2ecd11ead58379ebdf48c044b41d8819` |
| `owner-shipgraveyard-source-objects.json` | `84140a27fe439a1c53ac24da70f2080afc240954314500ab7722499aca1e6e96` |
| `owner-testotherbrother-objects.json` | `1fe65b6b2f9029d3f65b1b7203f8305263d8db8abc72af316c3bee4cfcdee46a` |
| `owner-repurposedcrater-objects.json` | `dce073a775ec75d33dad778d41a8b130795a7ae8548828196c56f0911ac49b33` |
| `owner-logbook-postprocess.json` | `4c8c3eb31ab469a53d5875212be856a6fb601e561ac9410280ce5983d3a4a85d` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain source selectors, hashes, checked pointer relationships and
authored import policies only. Compaction preserves every decoded selector.
Logbook post-processing is the byte-unchanged qualified source Shader recipe.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Current legitimate PC files, SDK resources and checked
record packs remain required. Generated outputs and evidence stay ignored.
Existing redistribution and ownership boundaries apply; phone execution and
runtime qualification remain open.

The camera transform recipe whole-catalog source pin follows the pure integration
metadata extraction. Manual provenance/privacy review: this pin references only
authored public Python; no game content, local paths or device evidence is added.

The preparation-trace source cohort refresh pins only authored world-owner log
markers and updates the matching audio/camera manifest and build-hook hashes.
Manual provenance,
privacy, licensing and sensitive-content review found public source hashes only;
no game-derived content, private paths or runtime evidence is included. Existing
input and redistribution requirements remain unchanged.

## Eight scene Shader profiles (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-lakes-standard-shaders.json` | `909c81d5ce199cdc9fb2288c1f207d89bf35a3f08bd44c553fea869cd944263c` |
| `owner-satellitescene-standard-shaders.json` | `389344fc34516a51e51a29abbbef3c832cc0f9b38c5a18bbc3b0f919ffe04b37` |
| `owner-satellitescene-postprocess.json` | `a1c4c9ede7fd719a0189418381a740faddcc1af561a339283f805572e072c07e` |
| `owner-limbo-standard-shaders.json` | `51cab1669445c77eb6e34af47d76e7ccc651b3fa574d6df20e29b0e7b89a867a` |
| `owner-limbo-postprocess.json` | `c6ac914674ec39c3bb9a60aabd24c1a1f711813494b784a8c34a0a012a29be05` |
| `owner-ironalluvium-standard-shaders.json` | `5389038e2f5d396d2388ae7eff4a433e6f196f249bacf24431742cbd81c34604` |
| `owner-ironalluvium2-standard-shaders.json` | `edc265021b929f0c8b84a57a23ffe61435f3bb94fb6892f4f5f11f35ea375e34` |
| `owner-lobby-standard-shaders.json` | `4890fc07442deef8af5cda6e534464c1447fa0045b6feb8249934106c55228ab` |
| `owner-lobby-postprocess.json` | `0fd3c91afc4c616711d2f643d0f075492f4d832fe5822dead6ad8fd931bba469` |
| `owner-lakesnight-standard-shaders.json` | `baa87545412df2669b7fb6b812a2d0e5ba681abba5ce707fffcf9d256811969c` |
| `owner-sulfurpools-standard-shaders.json` | `cb83bfa29b2db908dcbbe58190e8a5326cac8ea6cc6c5afdd292b236d9030ee2` |

Manual provenance, privacy, licensing and sensitive-content audit: these eleven
byte-unchanged qualified profiles contain only original source selectors, hashes,
SDK/public-template pins, authored compiler settings and destination identities.
The existing Shader record owner consumes them; no source text, serialized body,
program, target keyword table, private path or credential is included. Standard
material selection follows original scene renderer roots for spine scenes and
original recursive content closure for whole scenes. The two scopes preserve
the existing scene builders. Original/SDK inputs and generated packs remain
external and ignored; these recipes grant no redistribution or ownership right.
Phone execution and runtime qualification remain open.

## Eight complete scene object profiles (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-lakes-spine-objects.json` | `1b63b04f29691d6872d46167c3b57700ebf5238563ec15ee76806c6eb999e356` |
| `owner-satellitescene-objects.json` | `88badff0f98ba8809a13581b6883fc70f360ce5e6bfde17b9a902cc25994d4d2` |
| `owner-limbo-objects.json` | `35448d0f31ee8aaaa16d16c19a84e9a3ff5d31731f045c088d32296057c385e9` |
| `owner-ironalluvium-objects.json` | `2fa43d0a4c91c483320567db92b40641a477643a614981e59a11aae1c43aa96d` |
| `owner-ironalluvium2-objects.json` | `c9d2b7ee0e32723e8b6806b1a380985c60dbbfb14a1421bcf015a124a98a5a63` |
| `owner-lobby-objects.json` | `1c447dde4392ec2964bd5fe481006273506041305203b75b3f8596fbba314a43` |
| `owner-lakesnight-spine-objects.json` | `f2ed065a672383d9516c150e497719be84530f3d9aaf667f7d02a3dddb768d2a` |
| `owner-sulfurpools-spine-objects.json` | `53bdf1ed34a7582ac0ddb5b75127d9c502f4bf3c2d1a5d1020418b9da9570524` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain source selectors, hashes, checked pointer relationships and
authored import policies only. Compaction preserves every decoded selector.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Current legitimate PC files, SDK resources and checked
source-produced record packs remain required. Generated outputs and evidence
stay ignored. Existing redistribution and ownership boundaries apply; phone
execution and runtime qualification remain open.

## Produced catalog metadata adapter (2026-10-26)

Manual provenance, privacy, licensing and sensitive-content audit: the existing
whole-catalog owner now reads structural dependency records from locally produced
Android bundles, hashes their real bytes and completes a supplied source-declared
graph. The camera recipe source pin tracks that authored helper change only.
No accepted dependency table, object body, original source, private path or
credential is included. The bounded reader is unchanged; legitimate input and
source-produced bundles remain external and ignored. Host contracts preserve
cyclic references and refuse incomplete graphs. Full catalog production and phone
execution remain open; no redistribution or ownership right is granted.

## Loadingbasic scene object profile (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-loadingbasic-objects.json` | `3e46d0b7d2200ee8fa581328a6787d1687f2a66ea1f3bd7b15c3fa66cdb8de64` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains original selectors, hashes, checked pointer relationships and existing
authored import policies only. Compaction preserves every decoded selector.
The original SpriteNumberImage preload membership supplies its omitted local
GameObject dependency; existing component and global-owner policies preserve
the accepted startup layout. Source-produced texture, cubemap and Skybox packs
remain explicit pinned inputs to the existing object producer. No original body,
curve, scalar, pixel, program, copied source, private path or credential is
included. Current legitimate PC files and SDK resources remain required;
generated content and evidence stay ignored. Existing ownership and
redistribution boundaries apply. Phone and runtime qualification remain open.
## Conduit Canyon complete scene object profile (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-conduitcanyon-objects.json` | `28241c71cbe333cb25a2ac210c75cf10c91e92aab7887dec0179248e37827474` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains source selectors, hashes, checked pointer relationships and authored
import policies only. No original body, curve, scalar, pixel, program, copied
source, private path or credential is included. Source-qualified preload
relationships use original GameObject witnesses, pinned SDK dependencies and
the qualified imported-model exclusion. Current legitimate PC files, SDK
resources and independently source-produced Mesh, director and Shader record
packs remain required. Generated outputs and evidence stay ignored. Existing
redistribution and ownership boundaries apply; phone execution and runtime
qualification remain open.

## Fungal complete scene object profile (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-fungal-objects.json` | `217f1270df3fee57abaa3beffbc80aaeb41ef42f36c3c0523efa14d46dca246e` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains selectors, hashes, checked pointer relationships and authored import
policies only. It contains no original object bodies, curves, scalar data,
pixels, shader programs, copied source, private paths or credentials. Original
GameObject and typed reciprocal Rigidbody witnesses qualify preload membership;
the producer derives the preload from original dependencies. Current legitimate
PC files, the pinned SDK and independently source-produced media/Shader record
packs remain required. Generated outputs and raw evidence stay ignored.
Existing ownership and redistribution boundaries apply; phone production,
installation and runtime behavior remain open.
## Conduit and Fungal source Shader selections (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-conduitcanyon-standard-shaders.json` | `e8825d706eb5e6c234e536b7d05e9f36febbce5ec64dff90e89c3eac40c69f5c` |
| `owner-fungal-standard-shaders.json` | `8f51bfdf66770c08142bfd46b416fcc90f52f38623d4393137131aa6ebd3a63e` |
| `owner-fungal-postprocess-shaders.json` | `d91cb5e6ffbdd9e4a885ba93bdadab4aafe568071b4ddeba7f77f28a9fbf55d7` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles retain original material/scene selectors, source hashes, SDK/compiler
pins and authored output relationships only. Standard fog variants follow the
original RenderSettings mode; dummy Shader templates follow pinned AssetRipper
ParsedForm export rules. No original program, body, copied source, private path
or credential is included. Current legitimate PC files and separately acquired
SDK/public tools remain required. Generated records and evidence stay ignored;
Fungal complete-scene assembly and phone/runtime qualification remain open.
## Produced catalog metadata adapter (2026-10-26)

Manual provenance, privacy, licensing and sensitive-content audit: the existing
whole-catalog owner now reads structural dependency records from locally produced
Android bundles, hashes their real bytes and completes a supplied source-declared
graph. The camera recipe source pin tracks that authored helper change only.
No accepted dependency table, object body, original source, private path or
credential is included. The bounded reader is unchanged; legitimate input and
source-produced bundles remain external and ignored. Host contracts preserve
cyclic references and refuse incomplete graphs. Full catalog production and phone
execution remain open; no redistribution or ownership right is granted.


## Six whole-scene Shader producers (2026-10-26)

The existing `payload_shader_records.py` owner consumes these seven profiles
for 122 source-produced records. Pinned public AssetRipper ParsedForm template
selection and original resource fields determine post-processing exports;
original RenderSettings and material relationships select SDK Standard/skybox
variants. Independent comparisons pass for all records after guarded production
that refuses accepted outputs and retained packs as suppliers.

| Profile | SHA-256 |
| --- | --- |
| `owner-splash-postprocess-shaders.json` | `a8dab79b958798d951e7fc74425c6eb905de74eaf0b307e4eff4d0986d65c959` |
| `owner-splash-skybox-shaders.json` | `8e604923ca9bf2149ca42d9fb0c018fffb6e666b84a1ebf4d45ad08470c81322` |
| `owner-habitat-postprocess-shaders.json` | `611a10651c31861c40444d365613f30e95b88cdff0c4a4247efaf8b8901e9179` |
| `owner-helminthroost-postprocess-shaders.json` | `c701edee2c076c472d98d4d9ba9c91f46c8ef3600cb20b3d5479c37dfeffe00d` |
| `owner-artifactworld03-postprocess-shaders.json` | `ca7637756f3512e21bf40f5838e827082fd49fc5970cf8b75dbedae3d0e00043` |
| `owner-itgoolake-postprocess-shaders.json` | `690b6fc062494cde95c8e34271d787e352d0037be37c75b0025a42f8e8cf8808` |
| `owner-itgolemplains-standard-shaders.json` | `82643e59c40cd03766c16c023aeb844d604610ab9bb48778f8a886df2c2eafa9` |

Manual provenance, privacy, licensing and sensitive-content audit: profiles
contain original file/object selectors, source hashes, SDK/public-tool pins and
output relationships only. No original body, program, copied shader source,
private path or credential is included. Current legitimate PC input and the
separately acquired SDK remain required. Generated records and raw evidence stay
ignored. Full-bundle qualification is separate; phone/runtime gates remain open.


## Itmoon Shader producers (2026-10-26)

The existing record-pack owner consumes these two profiles for 24
post-processing records and one Standard record. Original resource fields,
export filename/GUID witnesses and recursive scene material relationships
select the inputs. Guarded actual CLI production persisted before independent
raw comparison; all 25 records match.

| Profile | SHA-256 |
| --- | --- |
| `owner-itmoon-postprocess-shaders.json` | `e0e4168ad9cb21c90ca2f17a6b6e20eb65e915d1c604228f1fa0574e0aad8182` |
| `owner-itmoon-standard-shaders.json` | `b55116099ac69aa181fb7478e1bba966608b626567da035dd14a52fc3925122e` |

Manual provenance, privacy, licensing and sensitive-content audit: only
source selectors, hashes, public-tool/SDK pins and destination relationships
are included. No game bodies, shader programs, copied source, private paths
or credentials are included. Legitimate PC input and separately acquired SDK
remain required; generated records stay ignored. Complete-scene, phone and
runtime qualification remain separate.

## Seven complete scene object profiles (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-splash-whole-objects.json` | `3b9366dbf00fbc4cd5733381557ff08f2ef8607ac7246bff01ffc0e77b7a2e9f` |
| `owner-habitat-whole-objects.json` | `b7bdedfe0acc7ea849ae8b3600fb1e8ed75ea32a536f4d7d06bfbc620b37e742` |
| `owner-helminthroost-whole-objects.json` | `3fbe8d7ac9ebec5cbda8220fcb174f91e0a694e69223de22407d8025740e66b1` |
| `owner-itgolemplains-whole-objects.json` | `798c87752dcda4b5b4fa5cc5754523483384475fba48fa1e5653b58b2cf7a947` |
| `owner-artifactworld03-whole-objects.json` | `ff50e0cc77b6f899c1efbf200c021ad1d2364f9140ba817f677fe79ae152de91` |
| `owner-itgoolake-whole-objects.json` | `0f94960f9e5427dcf0895a85e977233174f5a46e9a4890e76bd80cf30cefb6cd` |
| `owner-itmoon-whole-objects.json` | `b26b5e2c011ea6f20bbbd0886042506c63479854d011e0bd7b146afeb7d04cbd` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain source selectors, hashes, checked pointer relationships and
authored import policies only. Lossless compaction preserves decoded selectors.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Current legitimate PC files, SDK resources and checked
source-produced record packs remain required. Generated outputs and evidence
stay ignored. Existing redistribution and ownership boundaries apply; phone
production and runtime qualification remain open.


## Loadingbasic skybox Shader selection (2026-10-26)

The existing SDK skybox record owner follows original RenderSettings to the
Default-Skybox material and its built-in Shader pointer. Guarded actual CLI
production persisted before independent comparison; the single record matches.

| Profile | SHA-256 |
| --- | --- |
| `owner-loadingbasic-skybox-shaders.json` | `a6a45b569a9ff08e1f09ec2b2136729367b72c221387b95b5b3e6155c55d0235` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains only original file/object selectors, source hashes, SDK/public-tool
pins and output relationships. No original body, shader program, copied source,
private path or credential is included. Legitimate PC files and the separately
acquired SDK remain required. Generated records and evidence stay ignored;
complete-bundle, phone and runtime qualification remain separate.
## Loadingbasic scene object profile (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-loadingbasic-objects.json` | `3e46d0b7d2200ee8fa581328a6787d1687f2a66ea1f3bd7b15c3fa66cdb8de64` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains original selectors, hashes, checked pointer relationships and existing
authored import policies only. Compaction preserves every decoded selector.
The original SpriteNumberImage preload membership supplies its omitted local
GameObject dependency; existing component and global-owner policies preserve
the accepted startup layout. Source-produced texture, cubemap and Skybox packs
remain explicit pinned inputs to the existing object producer. No original body,
curve, scalar, pixel, program, copied source, private path or credential is
included. Current legitimate PC files and SDK resources remain required;
generated content and evidence stay ignored. Existing ownership and
redistribution boundaries apply. Phone and runtime qualification remain open.
## Fungal complete scene object profile (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-fungal-objects.json` | `217f1270df3fee57abaa3beffbc80aaeb41ef42f36c3c0523efa14d46dca246e` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains selectors, hashes, checked pointer relationships and authored import
policies only. It contains no original object bodies, curves, scalar data,
pixels, shader programs, copied source, private paths or credentials. Original
GameObject and typed reciprocal Rigidbody witnesses qualify preload membership;
the producer derives the preload from original dependencies. Current legitimate
PC files, the pinned SDK and independently source-produced media/Shader record
packs remain required. Generated outputs and raw evidence stay ignored.
Existing ownership and redistribution boundaries apply; phone production,
installation and runtime behavior remain open.

## Title Shader source selections (2026-10-26)

The existing Shader record owner produces 24 post-processing records, Standard
and the SDK terrain base generator. Original resource/material relationships
and SDK-declared pass metadata select the variants; guarded CLI production
persists before separate raw comparison of all 26 records.

| Profile | SHA-256 |
| --- | --- |
| `owner-title-postprocess-shaders.json` | `0eb16753bed7a2cae353db866db39dcd7ca4b80a028b4026ccb7a4e4a3ab6bbc` |
| `owner-title-standard-shaders.json` | `fd8ab6354a8cc0712ed3278d6785831497ec01fc5539152486c1a956039a597b` |
| `owner-title-terrain-shaders.json` | `9252627420b8def7f6e051317edbdd568b6e81e38a65e51811fa604aab753589` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, public SDK/tool pins and output
relationships only. No original bodies, shader programs, copied source, private
paths or credentials are included. Current legitimate PC files and separately
acquired SDK remain required. Generated records and evidence stay ignored;
complete Title assembly, phone production and runtime qualification remain open.
## Title and Satellite complete object selections (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-title-whole-objects.json` | `1f4ea96d713b60b159e5c1cd030bb5b49e7df1e387d9cbe10831290b033498ee` |
| `owner-satellitescene-whole-objects.json` | `a035d84e5f5e930eb24bf23bd3ef37bd400d34bce1b0a7d9f665c63a672cd911` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain source selectors, hashes, checked pointer relationships and
authored import policies only. Lossless compaction preserves decoded selectors.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Current legitimate PC files, SDK resources and checked
source-produced record packs remain required. Generated outputs and evidence
stay ignored. Existing redistribution and ownership boundaries apply; phone
production and runtime qualification remain open.

## Artifact World complete object selection (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-artifactworld01-whole-objects.json` | `f7b8b3e0d8728db50512201250c4d842bcd6e54705a69123a1b8e438017d3813` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain source selectors, hashes, checked pointer relationships and
authored import policies only. Lossless compaction preserves decoded selectors.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Current legitimate PC files, SDK resources and checked
source-produced record packs remain required. Generated outputs and evidence
stay ignored. Existing redistribution and ownership boundaries apply; phone
production and runtime qualification remain open.

## Satellite and Artifact World Shader selections (2026-10-26)

The existing Shader record owner consumes these source-qualified profiles for
48 post-processing records and one Standard record. Original resource fields,
export filename/GUID relationships and recursively reached materials determine
selection. Guarded actual CLI production persisted before independent raw comparison.

| Profile | SHA-256 |
| --- | --- |
| `owner-satellitescene-postprocess-shaders.json` | `a1c4c9ede7fd719a0189418381a740faddcc1af561a339283f805572e072c07e` |
| `owner-satellitescene-standard-shaders.json` | `389344fc34516a51e51a29abbbef3c832cc0f9b38c5a18bbc3b0f919ffe04b37` |
| `owner-artifactworld01-postprocess-shaders.json` | `b202cf2d9d3722e7febbadecb27c7337f879b85ab6af2d56c44feeb10f62637a` |

Manual provenance, privacy, licensing and sensitive-content audit: only source
selectors, hashes, public SDK/tool pins and destination relationships are included.
No original bodies, shader programs, copied source, private paths or credentials
are included. Legitimate PC files and separately acquired SDK remain required;
generated records stay ignored. Phone and runtime qualification remain open.


## Ten complete spine scene selections (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-golemplains2-spine-objects.json` | `fdbc8c2042ff83839ecf31359c6161cf583ac7304822d19fe8083e8c1b5e596b` |
| `owner-golemplains2-spine-lab-standard-shaders.json` | `f815eb48f56767b995df124f0cbf745d43927c1ba0f3318339682c926ee40deb` |
| `owner-dampcavesimple-spine-objects.json` | `9ac17ef9dbbd1c5bea99ca4b65a5431b7bbf2bcbf33a899e4acb6f9f5b2a9d46` |
| `owner-dampcavesimple-spine-lab-standard-shaders.json` | `fe93297b7d5332fd30be4482fc3913a07da34c4b9439ec2b9cbe913401c34d03` |
| `owner-blackbeach2-spine-objects.json` | `e4eb716afda5d23a505bb48728cffc6c10de43b3fabfb53fa38e1a78e58c26fa` |
| `owner-blackbeach2-spine-lab-standard-shaders.json` | `c5434c885801bf58b90157c7a32ee30093ab552d5f317cad59c877a0f1a2a406` |
| `owner-foggyswamp-spine-objects.json` | `74c27d2df8f6aba241ef8da26fe075590652699e65a2a39aac8339c0e6ce8418` |
| `owner-foggyswamp-spine-lab-standard-shaders.json` | `98699484ef630f10a3f1b46ae179882632222dcd1e7287628d4480a064ddd6b3` |
| `owner-ancientloft-spine-objects.json` | `9c0feb85d569b6762918d4d5fcfa2027979b52e141fdf5ce67437c32a2c50f44` |
| `owner-ancientloft-spine-lab-standard-shaders.json` | `c3bc501603146d9b536f1f6aa28533109971aa75eea16d2dca00ef4e5f0c13e3` |
| `owner-village-spine-objects.json` | `7dac53626b27ddb08e951d934015e237279b920f07ba5a2effcc569715e4cc49` |
| `owner-village-spine-lab-standard-shaders.json` | `fed66e3f3f11e27ce2f7d281ce2f1f0e26a19ccc1b9c59feb528aa4e51be7e47` |
| `owner-shipgraveyard-spine-objects.json` | `a62dd18b06ae62970984089ddd31fe11d26c4e2081432029a7e16ee0a4195b24` |
| `owner-shipgraveyard-spine-lab-standard-shaders.json` | `27c295f0fc7dfed9f6cb1009829f0698943ea3fde79096a235d1b4846e28d393` |
| `owner-golemplains-spine-objects.json` | `88350424b9e313ec47bacdf8210d962aa9cafeda2fc1610c01d4ce5a881382e0` |
| `owner-golemplains-spine-lab-standard-shaders.json` | `84cca571218bc56551f82813e3aeb01b45e27dc1b48441365181155849743665` |
| `owner-blackbeach-spine-objects.json` | `18adebc9c4b4dc9aaa8aa4ea1f54ea23b91d4787a8904801534035382d3f97a1` |
| `owner-blackbeach-spine-lab-standard-shaders.json` | `591baf62fe9b4b06c270b25bbe0f617b90583e21da174aed00b6d36c1d93ba42` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, checked pointer relationships,
SDK/public-tool pins and existing authored import policies only. Lossless JSON
compaction preserves all decoded object selections. Original scene renderer
and skybox material roots select the reduced-spine Standard variants. No original
body, curve, scalar payload, pixel, shader program, copied source, private path
or credential is included. Legitimate PC files, separately acquired SDK and
receipt-pinned source-produced media/Shader packs remain required. Generated
outputs and evidence stay ignored. Existing ownership and redistribution
boundaries apply; phone production, installation and runtime behavior remain open.

## Ultima source-derived Shader selections (2026-10-26)

The existing Shader owner selects 24 post-processing records from original
resource fields and Standard from recursively reached original materials.
The original Colossus item renderer and acquired export identify the SDK
default material; its explicit selector supplies pinned SDK features after
original material/body/shader validation. Other original emissive materials
retain their features. Source-only CLI output is persisted before comparison.

| Profile | SHA-256 |
| --- | --- |
| `owner-ultima-standard-shaders.json` | `3aa00bbca4a256991344d8228e59280b2e6e4ee81b22b979edfb7c1f27d923cd` |
| `owner-ultima-postprocess-shaders.json` | `d7a6ca82d474202320229d17d5e0d048d8476dc4d3f4de60b32f218de569be70` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain source selectors, hashes, source relationships and pinned
SDK/public-tool identities only. No original bodies, programs, copied source,
private paths or credentials are included. Legitimate PC input and separately
acquired SDK remain required; generated records and evidence stay ignored.
Phone production, installation and runtime qualification remain open.

## Four complete source-scene selections (2026-10-26)

Golemplains2, Ancientloft, Habitat and Blackbeach extend the existing object
and Shader owners. Their source-only CLI output persists before independent
comparison: all 60,493 objects, eight serialized members and four compressed
bundles are raw-exact to J850. Lossless JSON compaction preserves every
decoded object selection. The five Shader profiles are unchanged from their
separately qualified source-produced packs.

| Profile | SHA-256 |
| --- | --- |
| `owner-golemplains2-source-objects.json` | `31341ace31b15a939e2c05bd9cbe65da49fed2b5163b89e75e92faf35573c46b` |
| `owner-golemplains2-source-lab-standard-shaders.json` | `fff8d88f8d13bbb9f544bbafac5c0209bc63ddd3755786a36748b535311e81f1` |
| `owner-ancientloft-source-objects.json` | `30ee01b31ca59830c17d320b8df866b6e178bab502864ce5c2e95843354d0426` |
| `owner-ancientloft-source-lab-standard-shaders.json` | `d7db4c8699040dc7e4698aceaf13bac1ade720002347266b0642a12277617934` |
| `owner-ancientloft-source-lab-postprocess-shaders.json` | `eda9e4b0c2dccfdb6b0a15c6299deb4ec6c01a8f551d8f5b97254083ceaa7ec7` |
| `owner-habitat-source-objects.json` | `dce1bd3a7e624c3e320f86ad3f29f3dddfd20f7954ef514909bd6aa77b6f2316` |
| `owner-habitat-source-lab-postprocess-shaders.json` | `ef701e0931128d559ff0e6621d44ab56d5ca3d8def2b1ca22375dc8eff7f60df` |
| `owner-blackbeach-source-objects.json` | `20ce8f218ca27c732f2d486791c623031f0af7234bdd5b15b93ac11077964232` |
| `owner-blackbeach-source-lab-standard-shaders.json` | `ad46d5531f503361f8e9db24c2019d7979281ca22deb8052abb9d109190e06bb` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, checked pointer relationships,
SDK/public-tool pins and existing authored import policies only. No original
body, curve, scalar payload, pixel, shader program, copied source, private path
or credential is included. Legitimate PC files, separately acquired SDK and
receipt-pinned source-produced media/Shader packs remain required. Generated
outputs and evidence stay ignored. Existing ownership and redistribution
boundaries apply; phone production, installation and runtime behavior remain open.

## Ultima complete object selection (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-ultima-whole-objects.json` | `d7e0941ffd920f07f48cbf27e400ea9958551c8dc2713a127337c1c3e9661a36` |

Manual provenance, privacy, licensing and sensitive-content audit: this
profile contains source selectors, hashes, checked pointer relationships and
authored import policies only. Lossless compaction preserves decoded selectors.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Current legitimate PC files, SDK resources and checked
source-produced record packs remain required. Generated outputs and evidence
stay ignored. Existing redistribution and ownership boundaries apply; phone
production and runtime qualification remain open.

## Sulfurpools complete source-scene selections (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-sulfurpools-source-objects.json` | `4ad4cd14854456a66d4326d3f9d9aef783a65f8ede7778773c798d4f12204d72` |
| `owner-sulfurpools-source-lab-postprocess-shaders.json` | `8cae5e2fb635198d8b92df35c97bcbf1750059271be429c1e27ade4978b5ed4f` |
| `owner-sulfurpools-source-lab-standard-shaders.json` | `634ace2d8f1ea8e80bfc9dc2756c41acb25a8aa611c0fea3e213310e66516bd2` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, checked pointer relationships,
SDK/public-tool pins and existing authored import policies only. Lossless JSON
compaction preserves every decoded object selection; both Shader profiles are
unchanged from the separately qualified source-produced packs. No original
body, curve, scalar payload, pixel, shader program, copied source, private path
or credential is included. Legitimate PC files, separately acquired SDK and
receipt-pinned source-produced media/Shader packs remain required. Generated
outputs and evidence stay ignored. Existing ownership and redistribution
boundaries apply; phone production, installation and runtime behavior remain open.

## Habitatfall complete source-scene selections (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-habitatfall-source-objects.json` | `57dbaeb22a902e71d6178898b390ff0848bc6aa18ae6b9dae9b62396705b80e6` |
| `owner-habitatfall-source-lab-postprocess-shaders.json` | `6de150e41fed20628b0590fa5b3a4353df3e6d69bad01e2b3ccfcb9ffd8d276b` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, checked pointer relationships,
SDK/public-tool pins and existing authored import policies only. Lossless JSON
compaction preserves every decoded object selection; the Shader profile is
unchanged from the separately qualified source-produced packs. No original
body, curve, scalar payload, pixel, shader program, copied source, private path
or credential is included. Legitimate PC files, separately acquired SDK and
receipt-pinned source-produced media/Shader packs remain required. Generated
outputs and evidence stay ignored. Existing ownership and redistribution
boundaries apply; phone production, installation and runtime behavior remain open.

## Soul, Mire and Crystalworld Shader selections (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-crystalworld-postprocess-shaders.json` | `ea6966e5e5086b9547cfd83663198adce6c0125e6b1ff4e2beead7d8b2935fa8` |
| `owner-mire-postprocess-shaders.json` | `b91ed6fc82718236bc7445a65651f7c7a25dafacc2b74cdee76506fe15c2f693` |
| `owner-mire-standard-shaders.json` | `98d68b25432acfeb1771d54f7f2b8f60688b721e1e36e99657ce6e459ad12f26` |
| `owner-soul_perftest-postprocess-shaders.json` | `5d0daae7698d0344edc1ec7daedfc15fd5c8e536bb06e15cae8ff7c18fa9a289` |
| `owner-soul_perftest-standard-shaders.json` | `bfd878baca6e50ae5b74b4c3e7cfd73577d68e6702a70c9511c03e487996bf10` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, checked resource/material
relationships and SDK/public-tool pins only. Soul uses its own original
scene resource and acquired-export GUID relationships. No original body,
program, copied source, private path or credential is included. Legitimate
PC input and separately acquired SDK remain required; generated records
and evidence stay ignored. All 74 persisted Shader records are host
raw-exact against J850. Complete-scene readiness and phone qualification
remain separate gates.

## Dampcavesimple complete source-scene selections (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-dampcavesimple-source-objects.json` | `b9b63ecc12cb8357f5ce240441a10c8b340d8bb883e55f82c29857c8b4fd286c` |
| `owner-dampcavesimple-source-lab-postprocess-shaders.json` | `7a1e036001844e5f2ad527b130e5c0e66aa5d515686b825c5ee08e7026476476` |
| `owner-dampcavesimple-source-lab-standard-shaders.json` | `3313421454be04453770f570aa4e86893631e1c9136a6760f069cff4e18bc338` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, checked pointer relationships,
SDK/public-tool pins and existing authored import policies only. Lossless JSON
compaction preserves every decoded object selection; both Shader profiles are
unchanged from the separately qualified source-produced packs. No original
body, curve, scalar payload, pixel, shader program, copied source, private path
or credential is included. Legitimate PC files, separately acquired SDK and
receipt-pinned source-produced media/Shader packs remain required. Generated
outputs and evidence stay ignored. Existing ownership and redistribution
boundaries apply; phone production, installation and runtime behavior remain open.

## Soul, Mire and Crystalworld complete scene selections (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-soul_perftest-objects.json` | `7ff7efa24163a2268c978b6bd1bc8b89417d336e45e664105bce68ea13c0b371` |
| `owner-mire-objects.json` | `e177548f7fd8a1659427b5fea6eabfe644fb0ee55f054b44ddb5af47658d1ccb` |
| `owner-crystalworld-objects.json` | `3648a7e92bb91d626390761a799a9c10ae775c0f0bfb6f92b2ede1c1bb6de1d2` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain source selectors, hashes, checked pointer relationships and
authored import policies only. Compaction preserves every decoded selector.
No original body, curve, scalar data, pixel, shader program, copied source,
private path or credential is included. Current legitimate PC files, the pinned
SDK and independently source-produced media/Shader record packs remain required.
The existing object producer preserves source null-script type slots for Soul
and Mire. Generated outputs and raw comparison evidence stay ignored; ownership
and redistribution boundaries apply. Phone production and runtime remain open.

## ArtReview Shader selections (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-artreview-postprocess-shaders.json` | `6ea7d573778b2c400361d5473eb63c377c8320ba2c384afb1b285548872f8c66` |
| `owner-artreview-standard-shaders.json` | `031403f7e1e3aaddce1267716201c6702df12375fdddf3596dbfc304d5e87480` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, checked resource/material
relationships and SDK/public-tool pins only. Standard variant order comes
from original fragment feature declarations; post-processing uses the pinned
public exporter templates. No original body, program, copied source, private
path or credential is included. Legitimate PC input and separately acquired
SDK remain required; generated records and evidence stay ignored. All 25
persisted records are host raw-exact against J850. The matching complete object
selection below also passes the host complete-scene comparison; phone
qualification remains open.
## ArtReview complete object selection (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-artreview-whole-objects.json` | `e8911198ddd990b59debe714d500661f8a7a94e2be2f733ec4219b77cec5c7bd` |

Manual provenance, privacy, licensing and sensitive-content audit: this
profile contains source selectors, hashes, checked pointer relationships and
authored import policies only. Lossless compaction preserves decoded selectors.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Current legitimate PC files, SDK resources and checked
source-produced record packs remain required. Generated outputs and evidence
stay ignored. Existing redistribution and ownership boundaries apply; phone
production and runtime qualification remain open.

## Golemplains complete source-scene selections (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-golemplains-source-objects.json` | `3bc05216bfa7e6f5e0f364e7d422b1b710354af7e70fe3b5e9fbd0693a683232` |
| `owner-golemplains-source-lab-standard-shaders.json` | `96e031413ee2d338eb00e56302249674ae029d663daa2a42045f09e7ed6ce99d` |
| `owner-golemplains-source-lab-postprocess-shaders.json` | `fc9a9db1781e05cdb2de065893e5e742cafa248178ee81db6362d9b7c56e7485` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, checked pointer relationships,
SDK/public-tool pins and existing authored import policies only. Lossless JSON
compaction preserves every decoded object selection; both Shader profiles are
unchanged from the separately qualified source-produced packs. No original
body, curve, scalar payload, pixel, shader program, copied source, private path
or credential is included. Legitimate PC files, separately acquired SDK and
receipt-pinned source-produced media/Shader packs remain required. Generated
outputs and evidence stay ignored. Existing ownership and redistribution
boundaries apply; phone production, installation and runtime behavior remain open.

## Skymeadow source particle Shader selection (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-skymeadow-source-lab-particles-shaders.json` | `0f248eaf36b78b8025884d680e48946ea79d8a0a1fe30d452d69bde0050e90aa` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains original source/material selectors, body hashes and pinned public SDK
and tool identities only. No shader body, program, copied source, private path
or credential is included. Legitimate PC input and independently acquired SDK
remain required; generated records and evidence stay ignored. The persisted
30,516 B record is host raw-exact against J850; phone production and runtime
remain open.


## Skymeadow complete source-scene selection (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-skymeadow-source-objects.json` | `ed511391e2acb2779237fbda202050d17e7bc8e284257719a78e5adf934b51b5` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains original selectors, hashes, checked pointer relationships, SDK pins
and existing authored import policies only. Lossless JSON compaction preserves
every decoded selection; the separately qualified particle Shader profile above
is reused unchanged. No original body, curve, scalar payload, pixel, shader
program, copied source, private path or credential is included. Legitimate PC
files, separately acquired SDK and receipt-pinned source-produced media/Shader
packs remain required. Generated outputs and evidence stay ignored. Existing
ownership and redistribution boundaries apply; phone production, installation
and original scene behavior remain open.

J1282 refreshes the existing audio-owner manifest's authored `PortSession.cs`
source hash for the reviewed mapping-startup reader change. The merge retains
main's integrated-world pin and refreshes the dependent camera build-hook
identity. No original audio data, account input or proprietary content is added. Manual provenance/privacy/licensing review: 2026-10-26. Audio output
and device behavior gain no qualification from this pin refresh.

## Native graph detour owner repin (2026-10-26)

Refresh the authored integrated-world owner hash after preserving progressing
native graph detours, and refresh the producer/camera recipe pins together.
The prior recipe remains the parent hash. Reviewed changes contain only authored
source and hashes; no game content, middleware, private paths or identifiers.
This pin update does not qualify native encounter or audio behavior.

The same audit covers the camera build-hook hash following its refreshed
authored audio-producer recipe pin. This changes source validation metadata
only; no generated content or additional input identifiers are published.

## Meridian source particle Shader selection (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-meridian-source-lab-particles-shaders.json` | `f4790f6f732e987af47d3af7aeb1cfa156d398bcd0ac653336a31b1212b62d79` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains original source/material selectors, body hashes and pinned public SDK
and tool identities only. Recursive original scene dependencies select three
particle materials; the existing SDK 211 producer supplies programs and native
order. No shader body, program, copied source, private path or credential is
included. Legitimate PC input and independently acquired SDK remain required;
generated records and evidence stay ignored. The persisted 25,056 B record is
host raw-exact against J850; full-scene and phone gates remain separate.

## Frozenwall complete spine-scene selections (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-frozenwall-spine-objects.json` | `9cb32f87690d2b479eb778ec2e27b50d52249eff781affe93e7cee58bdc9200f` |
| `owner-frozenwall-spine-lab-standard-shaders.json` | `c7afd2cce11237e6db2131c5eddeb7037ca360866de80ecbe75825bc5fbe5829` |

Manual provenance, privacy, licensing and sensitive-content audit: these
profiles contain original selectors, hashes, checked pointer relationships,
SDK/public-tool pins and existing authored import policies only. Lossless JSON
compaction preserves every decoded object selection; the separately qualified
Standard profile is unchanged. Original renderer, skybox and local-material
roots select reduced-spine Standard variants using the J1183/J1192 policy.
No original body, curve, scalar payload, pixel, shader program, copied source,
private path or credential is included. Legitimate PC files, separately acquired
SDK and receipt-pinned source-produced media/Shader packs remain required.
Generated outputs and evidence stay ignored. Existing ownership and
redistribution boundaries apply; phone production and runtime remain open.

## Meridian complete object selection (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-meridian-whole-objects.json` | `bc6d4093b53ea0d345855e51360dd1983f43b35f947eb9ab491eb69555c60f9f` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains source selectors, hashes, checked pointer relationships and authored
import policies only. Lossless compaction preserves every decoded selection.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Legitimate PC files, SDK resources and receipt-pinned
source-produced record packs remain required. Generated outputs and evidence
stay ignored. Existing ownership and redistribution boundaries apply; phone
production, installation and original scene behavior remain open.

## Computational Exchange Standard selection (2026-10-26)

| Profile | SHA-256 |
| --- | --- |
| `owner-computationalexchange-whole-standard-shaders.json` | `74d83b24333b4d44ab832629953f3150fca8833088fcb9256993cbc72b401272` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains original scene/material selectors, body hashes, pinned public SDK/tool
identities and existing authored import settings only. Recursive original
dependencies select Standard features; the existing SDK compiler supplies
programs. No original body, program, copied source, private path or credential
is included. Legitimate PC input and independently acquired SDK remain required;
generated records and evidence stay ignored. The persisted 301,384 B record is
host raw-exact to J850; complete-scene and phone gates remain separate.

## Computational Exchange complete object selection (2026-10-26)

| Recipe | SHA-256 |
| --- | --- |
| `owner-computationalexchange-whole-objects.json` | `7f76a47065416c33a1606186da9c10e9bf6bdc22cea0aaecbb2611eb29433413` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains source selectors, hashes, checked pointer relationships and authored
import policies only. Lossless compaction preserves every decoded selection.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Legitimate PC files, SDK resources and receipt-pinned
source-produced record packs remain required. Generated outputs and evidence
stay ignored. Existing ownership and redistribution boundaries apply; phone
production, installation and original scene behavior remain open.

## Champrush source Shader selections (2026-10-27)

| Profile | SHA-256 |
| --- | --- |
| `owner-champrush-whole-postprocess-shaders.json` | `39d2fce2857346432b0a334c5d46e7e1ef174fc450bf95d364b05bb37a017444` |
| `owner-champrush-whole-standard-shaders.json` | `8dc74a60c9cb554ec5dca9d3fc13120b7037fc5ef1b2e3c74e76ff13a612c09d` |
| `owner-champrush-whole-particles-shaders.json` | `62f078d212e0bda8bf30b961cbfbfd3012db9770a75fa0923995d5c3e8595115` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles
contain original scene/material/Shader selectors, hashes, pinned public SDK/tool
identities and existing authored import settings only. Original dependency
relationships select post-processing, Standard and particle records; existing
exporter templates and SDK compilation supply programs. No original body,
program, copied source, private path or credential is included. Legitimate PC
input and independently acquired SDK remain required. Generated records and
evidence stay ignored. All 26 persisted records are host raw-exact to J850;
complete-scene readiness and phone qualification remain separate gates.

## Champrush complete object selection (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-champrush-whole-objects.json` | `1b2fbf67b368c857c30739458bf4b4ca95b76d0e4c7a182b844b0c222c608572` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains source selectors, hashes, checked pointer relationships and authored
import policies only. Lossless compaction preserves every decoded selection.
Eight original Timeline/Track managed roots are admitted only through pinned
class 114 bodies and their original PreloadData membership. No original body,
curve, scalar, pixel, program, copied source, private path or credential is
included. Legitimate PC files, SDK resources and receipt-pinned source-produced
record packs remain required. Generated outputs and evidence stay ignored.
Phone production, installation and original scene behavior remain open.

## Voidstage complete object selection (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-voidstage-whole-objects.json` | `1c45133b5df7083d5343beed4b79deeabd71b8b400b6762c31272302f5a78978` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile
contains source selectors, hashes, checked pointer relationships and authored
import policies only. Lossless compaction preserves every decoded selection.
The original Rigidbody is admitted through its reciprocal GameObject component
relationship and complete source body/type identity. No original body, scalar,
curve, pixel, program, copied source, private path or credential is included.
Legitimate PC files, SDK resources and receipt-pinned source-produced record
packs remain required; generated outputs and evidence stay ignored. Phone
production, installation and original scene behavior remain open.

## Bazaar complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-bazaar-whole-objects.json` | `e1a7f4be014786b9871446a64b8686bd01458be4ba4050856011ec21ee6615d1` |
| `owner-bazaar-whole-particles-shaders.json` | `33d92f822a2304108864bd07d4c91c1c2df4550898e2bcff0d71a9e68cb013d4` |
| `owner-bazaar-whole-postprocess-shaders.json` | `201ec49da0c3c758946200846089e3b508070d329437adf1111f8e9de00588a6` |
| `owner-bazaar-whole-standard-shaders.json` | `9f9fdd13a55e2a63eff8412af49922b7bc8c88f16bec5e6603fe91371bced7d1` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles
contain source selectors, hashes, checked pointer relationships and authored
import policies only. Lossless compaction preserves every decoded selection.
Seven original wind-disabled Bezier lines use the existing hierarchy evaluator;
four CharacterMaster bodies and their script use the qualified aligned Boolean
tail policy, complete schema and reciprocal component/body-prefab witnesses.
Original dependencies select 24 post-processing records; original recursive
materials select Standard and particles through the pinned SDK compiler.
No original body, curve, scalar, pixel, program, copied source, private path or
credential is included. Legitimate PC files, SDK resources and receipt-pinned
source-produced packs remain required; outputs and evidence stay ignored.
Phone production, installation and original scene behavior remain open.

## Voidstage source Shader selections (2026-10-27)

| Profile | SHA-256 |
| --- | --- |
| `owner-voidstage-whole-postprocess-shaders.json` | `5d34926684243892ae14bec7cb22e402fcfae94ef65dc09619a8107fc378c5df` |
| `owner-voidstage-whole-standard-shaders.json` | `7c40fe5f02ed72235f6f1e32deccf5ef2d7c98f9c8afe10e4c7e27180544adca` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles
contain original scene/material/Shader selectors, hashes, pinned public SDK/tool
identities and existing authored settings only. Original resource relationships
select 24 post-processing records; recursive original materials select Standard.
Programs come from the existing exporter-template and pinned SDK compiler owners.
No target bytes, copied game source, private paths or credentials are included.
Legitimate PC input and independently acquired SDK remain required. Generated
outputs and evidence stay ignored. All 25 persisted records are host raw-exact
to J850; complete-scene readiness and phone qualification remain separate.

The existing SDK 211 particle producer accepts optional `stripped_keywords` in
an audited profile. It removes source-derived variant rows containing a declared
keyword before native ordering; omission preserves all existing selections.
This policy records explicit build stripping, without supplying program bytes.

## Four scene source selections and Shader index reuse (2026-10-27)

| Profile | SHA-256 |
| --- | --- |
| `owner-frozenwall-source-objects.json` | `c14602ed5360bdf2bce5fbf1c5b283798ce1141c81cfdd049acd913564e6313e` |
| `owner-frozenwall-source-lab-shader-remap.json` | `7dfbdb627abd591fdb29b89135362be539efff15b5b854bbc7d680cc6fa59f3d` |
| `owner-villagenight-source-objects.json` | `f66f0fa9e4743dcd8094c9ae1be7b8bdd373d583133a5979c8075971e480c423` |
| `owner-villagenight-source-lab-shader-remap.json` | `99f4c31e05205ea7f7f63f9c19dd64c0f1b3ffd53099c05ff0a4cac72fc8d126` |
| `owner-foggyswamp-source-objects.json` | `c1c477f06c4a845cf947ab6a93229bfe8658b00440341090178916bcc2ae3129` |
| `owner-foggyswamp-source-lab-shader-remap.json` | `5ca166d5b4f672050fd12f72f5ae29f437e21cb8f89a0f96ac2d79e7144c2b49` |
| `owner-skymeadow-spine-objects.json` | `e650c9495f22ff2e7f74d60bf35d5e896cdf725a375a5fab0bfc45c293ab38cf` |
| `owner-skymeadow-spine-lab-particles-shaders.json` | `cfc075285f7edbed499356558389e2d94f04889f7c8280448a7a80980f995b76` |
| `owner-goldshores-standard-reuse-shaders.json` | `3f757ceb9f619881c1406b2f27284648c68857d780c6bcbdbf4e86452a84ad71` |

Manual provenance, privacy, licensing and sensitive-content audit: object
profiles contain original selectors, hashes, checked pointer relationships,
SDK pins and authored transformation policies. Forty-two animated wind lines
retain three build-state angles each; all evaluated positions and original
curve operands come from the legitimate input. Complete captured xyz arrays
remain private and are excluded. Lakes, Lakesnight and Village remain open; Goolake follows the scoped audit below.
Skymeadow's `_ALPHAMODULATE_ON` stripping keyword records our accepted build's
variant selection; programs still come from the pinned public SDK producer.
Shader remap recipes select independently source-produced bodies by profile,
identity, length and hash. `record_remap.py` changes destination index identities
only, retaining the source dependency rows and supplier receipt provenance;
none is claimed as compilation from its destination scene. No asset body,
program, pixel, copied source, private path, device identifier or credential
is included. Legitimate PC input and independently acquired SDK remain required.
Outputs and qualification evidence stay ignored; phone qualification remains open.

Skymeadow particle profile SHA-256: `cfc075285f7edbed499356558389e2d94f04889f7c8280448a7a80980f995b76`.

`owner-goldshores-standard-reuse-shaders.json` preserves the previously qualified
three-output Standard supplier profile, SHA-256
`3f757ceb9f619881c1406b2f27284648c68857d780c6bcbdbf4e86452a84ad71`.
It differs from the current Goldshores profile only by omitting the later fourth
output identity; its original material/scene selectors, SDK and compiler policy
are identical. This audited retained profile makes the Frozenwall remap's
supplier identity reproducible without relabelling it as Frozenwall compilation.

Retained J1192 Goolake spine selections (unchanged from PR 140):

| Profile | SHA-256 |
| --- | --- |
| `owner-goolake-spine-objects.json` | `396ec87613ecbc97e825f7680fa89800920239057a4436d6875c93cd000ad10a` |
| `owner-goolake-spine-lab-standard-shaders.json` | `485f9a4d3477285cf2c061245ffc7c74f91a3df83dab520a0279b500f94ac918` |

These retain the J1192 source-selection audit and existing original-input/SDK
requirements. This table restores audit indexing only; no profile content changes.

The original-audio owner manifest follows the authored native-waypoint progress
and neutral-terrain recovery changes in `IntegratedWorldBoundary.cs`. Reviewed
source hash pins only; no game-derived content, private paths or identifiers.

## Goolake source-scene build-rounding selections

The existing original-curve owner uses eighteen build-angle triplets and ten
sparse accepted-build Y words on two curves. The 2026-10-27 orchestrator decision
authorizes these lab build arithmetic values; each word pins the expected
evaluated bits before applying the captured final float32 bits. The other
coordinates and all curve operands still require the legitimate input. Complete
XYZ arrays remain excluded. No asset body, shader program, private path, device
identifier or credential is included. The shader index adapter retains the
source-produced Sulfurpools supplier identity and dependencies. Host qualification
is separate from phone production, installation and runtime.

| Profile | SHA-256 |
| --- | --- |
| `owner-goolake-source-objects.json` | `6193e1a8f15a8cac28be940941f7973b9cb25099261b3805d3c735862d868609` |
| `owner-goolake-source-lab-shader-remap.json` | `02fdd8eda8b9b3e1b20e7398c15aaf46d165852b1e7e8884430b2561d7c708a9` |

## Voidraid complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-voidraid-whole-objects.json` | `b417dc2dc65e32f4b80cee374b054ee5d4996d8d8dfd90ef95fa280955950af4` |
| `owner-voidraid-whole-postprocess-shaders.json` | `0e32bb35568d9913c8c3c85bcea8dc4416e3bc1697b39552acb1953768ffa6d6` |
| `owner-voidraid-whole-standard-shaders.json` | `5f6a306dfb6118d06fed41f78e59453e2af739f60a07c23e856f6fa322f79a00` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles
contain source selectors, hashes, checked pointer relationships and authored
import policies only. Lossless compaction preserves every decoded selection.
Original component/GameObject relationships and complete source bodies/types
admit Billboard and Rigidbody dependencies; retained original wind records
preserve their complete body/type identities. Original resource and
material relationships select 24 post-processing records and Standard through
the existing pinned SDK compiler owners. No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. Legitimate PC
files, SDK resources and receipt-pinned source-produced record packs remain
required. Generated outputs and evidence stay ignored. All 39,861 persisted
objects, two serialized members and the compressed bundle are host raw-exact
to J850; phone production, installation and original scene behavior remain open.

## Surv2 complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-surv2-whole-objects.json` | `1e9e78edbba4c72e4265119bd32bef9257d5369dd08e461d3731736cb1915292` |
| `owner-surv2-whole-standard-shaders.json` | `46994cb9bfd6c2361be78bb9fc3186db5320eb0400dcb8cf793097b7980c8c9f` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles
contain source selectors, hashes, checked pointer relationships, build-assigned
identity/order constants (IDs only) and authored import policies only. Three
SpeedTree wind records select byte-identical original Black Beach records; the
Rewired helper component whose script is absent from the build uses the new
`missing_script_base` policy (original component truncated to the base fields,
original base MonoBehaviour type); the AkInitializer instance reuses the shipped
script schema hash. Standard is selected through the existing pinned SDK compiler
owner. No original body, curve, scalar, pixel, program, copied source, private path
or credential is included. All 30,311 persisted objects, two serialized members and
the compressed bundle are host raw-exact to J850; phone production, installation
and original scene behavior remain open.

## nest complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-nest-whole-objects.json` | `88de6a4e782772ad993fcbaed674e1e1ac260ad69fb373fa91619d4afd94acf4` |
| `owner-nest-whole-standard-shaders.json` | `2bf9a8d7b3569a141729fda0c6777dabd29b729602fceb33f7363a0559e39e8e` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 33,275 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## golemplains2 complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-golemplains2-whole-objects.json` | `4170f596493029d58dec8dd4156c9464d438a58c25a3c162b62061ce72f02715` |
| `owner-golemplains2-whole-standard-shaders.json` | `2dd1f714cf9414c5ee0807f4b6fcacd952b5e1120a20c42f6630b53d62e75ee7` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 8,785 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## infinitetowerworld complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-infinitetowerworld-whole-objects.json` | `a8de58752f2aedb7002a5c6c4374d1571f2b3b550e938fcada8232d247276d07` |
| `owner-infinitetowerworld-whole-postprocess-shaders.json` | `09ba0ea50f22a4f11e1f71ed9c2a0f47a015beb3da3277d24197c985d848dfc7` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 1,750 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## lemuriantemple complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-lemuriantemple-whole-objects.json` | `79266e44ce1cfc9cbe121331cf9930997abeb70701134f745386f00b07e456b4` |
| `owner-lemuriantemple-whole-standard-shaders.json` | `f0cc93f619a2c154c8d2f2a3cefab1d5e12b23062342b0aafd9f27742921359a` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 10,928 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## artifactworld complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-artifactworld-whole-objects.json` | `4656205ad8a77ad07afe53e715a516767d7d2bc3da0c6ecfd7c231303ae1c5e9` |
| `owner-artifactworld-whole-postprocess-shaders.json` | `5b16a509c3c80f18b5519edf82440870a80aa7be1f37e1d2a68c4588d9a9bfc7` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 4,095 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## blackbeach complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-blackbeach-whole-objects.json` | `c2708a4bebe83c5e56a87762e0f2ab4793e89b7e144f58d23bcf65897f1c34e4` |
| `owner-blackbeach-whole-standard-shaders.json` | `46a25f83086a97208cddc989e0a3b41ad73bcb8027aa1a725f2940b1c9648889` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 19,098 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## blackbeach2 complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-blackbeach2-whole-objects.json` | `5dd9af8c497db3c77e3f2fa786f507a9cd2e1c88c8af5d63bf54ba373930e61e` |
| `owner-blackbeach2-whole-standard-shaders.json` | `130bf7ef5a8f58d4f006d111a0b36047f9283a26f40e2068dd882c1a73567145` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 18,363 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## ancientloft complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-ancientloft-whole-objects.json` | `c8eafdd4432409a1e504842c47a422c3dc07cec9bf09684de83fa87b485072fc` |
| `owner-ancientloft-whole-postprocess-shaders.json` | `32a3485299c8c3047294cf1de4d2b406226b43f424271362dbc83c77fcc3fc3d` |
| `owner-ancientloft-whole-standard-shaders.json` | `ef097dd4722843134f5cdf22971ac7061f57bd24d1a2897d294f5966ac161a5f` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 19,637 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## arena complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-arena-whole-objects.json` | `77fc2d740a4f7e034865472e0af57333f2ab351d39a94d69b64f6c6e5f905968` |
| `owner-arena-whole-postprocess-shaders.json` | `5b443240a415e018a88d54105bc2ee0992037c22dfdec1f67784d88e52582dcd` |
| `owner-arena-whole-standard-shaders.json` | `d69d7c952ad0e89f16db8cedf8f8eef1a6e704b6547a885932ac48573bd6aa19` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 4,777 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## villagenight complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-villagenight-whole-objects.json` | `44a8014cf5240cec0636e0437f4f1f80bfa837658df45fb79b524cc6b51f4402` |
| `owner-villagenight-whole-postprocess-shaders.json` | `1b255324e3fb5112e7928faf8814ca90be2b83b39e63b80fe1a19a801a9a46e5` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 14,033 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## lakes complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-lakes-whole-objects.json` | `7916752404e6c4395ae6730101b1ed1290b995f675d7129f6c57ef994ef13758` |
| `owner-lakes-whole-standard-shaders.json` | `d18b02e1cefc5667436a0ea7ba06a5977ca832b93712d30017244c3189dd274e` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 22,163 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## lakesnight complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-lakesnight-whole-objects.json` | `d99f7132bc86f8cfb0a2aa91aa1cc24a0120838989faddf3b66539366cb27c05` |
| `owner-lakesnight-whole-standard-shaders.json` | `efd2ca4d71f06b8bd226bc3e5d28dc10a1e86df0e4d5fea6ad894f0d358ef6ad` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 21,397 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## artifactworld02 complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-artifactworld02-whole-objects.json` | `d2d16e304c97c277030a20590277f7433d85a534468ad7adc35e01b2c69137b5` |
| `owner-artifactworld02-whole-postprocess-shaders.json` | `3944ced88ae1cb7b1016273a89813cb809cfbd3405afc85ec5eb373bd55a770f` |
| `owner-artifactworld02-whole-standard-shaders.json` | `ca901e27ae0730fa23f779e9c91ca1769524edf08bc8ef8338e37ef61f99e742` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 9,558 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## sanctum complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-sanctum-whole-objects.json` | `a7bc05d8521f836851d9ca4b716117f181bb04685abcab65ddca7edfe4eb5e2e` |
| `owner-sanctum-whole-standard-shaders.json` | `c49b3d36b1f96376233e5cfc94f769ffa10bc30551342cc30151f270bf5fdfdd` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 53,196 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## village complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-village-whole-objects.json` | `d04b581a8a982c151149618891dbcabe99b78c1431b2771604d28c9a126b9d78` |
| `owner-village-whole-postprocess-shaders.json` | `6acba1001463127e7ff4e6370bec0d831b264e18231448823b82d4db41a16fd2` |
| `owner-village-whole-standard-shaders.json` | `d42f0a98fe480671a06d4d2f32e989c32bc5483b34ac6debf7da36ad28a61533` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 15,130 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## habitatfall complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-habitatfall-whole-objects.json` | `88d76b380e653281c1931c90beb75e8ff5fdc62d7842c93b592a0e1faf493fa9` |
| `owner-habitatfall-whole-postprocess-shaders.json` | `9b29fa479de844429a1871f73a2a8c3c13f01812074d4bad29a0946b8d006dcb` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 13,909 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## sulfurpools complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-sulfurpools-whole-objects.json` | `2ddce4d098dc78a398af712f45965b4083b620325c82a68717f9b3c9c8ff0988` |
| `owner-sulfurpools-whole-postprocess-shaders.json` | `d7e3732878e026b42250b7dfad829ce1e78fbda754b29b7abcf0a2160fd92bb5` |
| `owner-sulfurpools-whole-standard-shaders.json` | `30df15708ee410e6331c033fa4f7efadd5414be18ad4c361bceb87c62dcd45ab` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 19,544 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## sad1 complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-sad1-whole-objects.json` | `f5f02d8c9daed39df7bc40c64936c26bb7e909da1a74c796604bdd67251dbc92` |
| `owner-sad1-whole-standard-shaders.json` | `9e8f88ff014b935b7ca0360bd666d1be7e5fedf7e960e0a0f9848dbe6ce87c5e` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 64,308 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## moon complete scene selections (2026-10-27)

| Recipe | SHA-256 |
| --- | --- |
| `owner-moon-whole-objects.json` | `b189deb255fddec61d5050d6ac46ce569c497b7e684d9170728cd3fe82e62548` |
| `owner-moon-whole-postprocess-shaders.json` | `0dea5e8f940a372425605b5873629e0c1be0cdbca17a293e0d18c0082b1f47e1` |
| `owner-moon-whole-standard-shaders.json` | `eda74a93c5df8e0632bf843b6288a43b916eab13a7848d9a7c44aeeaa910fe38` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain source
selectors, hashes, checked pointer relationships and authored import policies only. Records with no
same-scene source select byte-identical original records found by exact body hash, or original
records that differ only in object references (remapped). No original body, curve, scalar, pixel,
program, copied source, private path or credential is included. All 17,327 persisted
objects, two serialized members and the compressed bundle are host raw-exact to J850; phone
production, installation and original scene behavior remain open.

## ITDampcave complete scene selections (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-itdampcave-whole-objects.json` | `e3d76295e12d466ce3df0b14c1777bd3664138d1dd70bdd153550b29ca1eb01c` |
| `owner-itdampcave-whole-standard-shaders.json` | `635e5d70180edb9e26a94a2cd9e8de88b5d5b4137fce933fa87417890b73701e` |
| `owner-itdampcave-whole-postprocess-shaders.json` | `96b22c526b8f9e222e6efd88d18240f67e9ceca3853c28c9022c9a6513a478c4` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain
original-input selectors, hashes, checked pointer relationships and authored import policies.
Post-processing selections follow the original Dampcavesimple resource supplying these records;
Standard selections retain ITDampcave's recursive material dependencies. SDK and public-tool
pins supply compilation. No original body, scalar array, pixel, program, copied source,
private path or credential is included. All 18,225 persisted objects, both serialized members
and the compressed bundle are host raw-exact to J850. Phone production, installation and
original scene behavior remain open.

## itfrozenwall complete scene selections (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-itfrozenwall-whole-objects.json` | `029c4800ff7880eb1b42f279538625a150dd4f6280fa9ae11c7477156a7e2a22` |
| `owner-itfrozenwall-whole-postprocess-shaders.json` | `486f1393c2f9d9202b8bdd27a31f881a00ae49ecccc52f580e3c1347038825c3` |
| `owner-itfrozenwall-whole-standard-shaders.json` | `fc4e6333a0dcbccdad913325ffedb6c346421215a71d46de7cf3f486a5bb176d` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain
original-input selectors, hashes, checked pointer relationships and authored import policies.
Original material keywords use the existing dummy-shader demotion policy. Explicit preload
admissions retain original scene membership and source identity checks. No original object body,
scalar array, pixel, program, copied source, private path or credential is included. All
8,727 objects, both serialized members and the compressed bundle are host raw-exact
to J850. Phone production, installation and original scene behavior remain open.


## soul1 complete scene selections (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-soul1-whole-objects.json` | `704048d30efaa1838baa181cce3db709fa189f2afc4cd1602da49dac1dd65a04` |
| `owner-soul1-whole-postprocess-shaders.json` | `d8f7e95a047bee50d7e97d8e6bb106b58699f1c15ce425ce3ef25fba365e9200` |
| `owner-soul1-whole-standard-shaders.json` | `9797dd28c9122624409ba61fdec33c0c22a9ce69fcad7f46aefb49bc29ee9c70` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles contain
original-input selectors, hashes, checked pointer relationships and authored import policies.
Original material keywords use the existing dummy-shader demotion policy. Explicit preload
admissions retain original scene membership and source identity checks. No original object body,
scalar array, pixel, program, copied source, private path or credential is included. All
290,159 objects, both serialized members and the compressed bundle are host raw-exact
to J850. Phone production, installation and original scene behavior remain open.

## Solutionalhaunt complete scene selections (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-solutionalhaunt-whole-objects.json` | `d321ca690b8b4eacb28db58b468d5f3d8ffed4b030f8d74e94368ce25e98238e` |
| `owner-solutionalhaunt-whole-standard-shaders.json` | `cdf672c1eb408908a4dfe1fa58560fdaf4166fcd989e87e1dcbdc74df756391d` |
| `owner-solutionalhaunt-director-records.json` | `743873197658b5f034584dd5b5a8931c0b32fe8e56850cf35eb1d18c67308cc7` |

Manual provenance, privacy, licensing and sensitive-content audit: profiles contain original
input selectors, file/body hashes, checked references, source schema selectors and authored
import policies. Original PC player MonoScripts and pinned original CLR metadata supply
added trigger identity and fields; original native prototypes supply transfer flags. Original
preload roots retain direct membership or reciprocal Animator/GameObject ownership. The
Director profile uses the existing PropertyName importer. No original body, type-tree blob,
scalar array, program, copied source, private path or credential is included. All 31,264
objects, both serialized members and the compressed bundle are host raw-exact to J850.
Phone production, installation and original scene behavior remain open.

Shader profile publication preserves qualified file bytes because object selections refer
to their SHA-256 identities. The 37 existing whole-scene Shader audit rows above now retain
their qualified representations; structured profile contents and produced records are
unchanged. Their original provenance/privacy/licensing audits remain applicable.

## Intro, Outro, PromoRailgunner, Voidoutro and Goolake complete selections (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-intro-whole-objects.json` | `1b489277f5e0f1c36ed62ebd2d312be59b7227aaa18d840caf47b26c83d1bc30` |
| `owner-intro-whole-standard-shaders.json` | `8de2632786c035a1f4d14f17e7b1b791161a262a49a0cb79a28c1de0f6f76537` |
| `owner-intro-whole-postprocess-shaders.json` | `8bdbbacfabe38d510fe51281eb539ee090520b95815500268fce92fb88c2899b` |
| `owner-intro-director-records.json` | `48c603ad0fc7e48fd392b9a3ca98b7b1099c8fbc051d8dbee0e34410397a5caf` |
| `owner-outro-whole-objects.json` | `f7222172230ff961dcf9df9e01cfaf3c49c5cca77451cddec66a79d0754a6a86` |
| `owner-outro-whole-standard-shaders.json` | `071612d2d698a5a9a888e8011c2b9ba61c2e2849fca43be01fe990914b500586` |
| `owner-outro-whole-postprocess-shaders.json` | `ac901312c73648ff7a69474cd46cc96e9c1e5c8f156e3a0b17c58a3e6ded587e` |
| `owner-outro-director-records.json` | `c197ee4c189c077d4bed6f829ffec2f840e5390c55fc85f960907a49df5292f2` |
| `owner-promorailgunner-whole-objects.json` | `cd701336853ba2f7d6fbdc31993536aa8aa945322bd173da6c5d2bdb190d9717` |
| `owner-promorailgunner-whole-standard-shaders.json` | `83f35d4aa060d96397cb805364bf8ef8e8ff4bed36a89ebde6b960c7ac88ec0c` |
| `owner-promorailgunner-whole-postprocess-shaders.json` | `151995096acce879007a27a352a880c65c363d20a3b5b03552a6d9b5d9dddcbe` |
| `owner-promorailgunner-director-records.json` | `8650ff9af49eb78e9f742ee8ae64a9c2af36dad4334ef8b89d05c24ea700f216` |
| `owner-voidoutro-whole-objects.json` | `3214fac0283fc9d8b03ab9c43e0d2ffc19682e92b2b5dee7fa2945561befb4dd` |
| `owner-voidoutro-whole-standard-shaders.json` | `cc29702a3737f8da1448b653838914a9934f6f7b7bfdda69e5c6e929718a9aec` |
| `owner-voidoutro-whole-postprocess-shaders.json` | `a4f65b9fe72339efb40bda7db0fb422abd365aa6881c9f051ffc65051b6b37b3` |
| `owner-voidoutro-whole-particles-shaders.json` | `864c09f923538e53efb9a8223779f1804ca826122f184ea6c051d772d4dd918a` |
| `owner-voidoutro-director-records.json` | `68dcef75464391ddda32bd0a848ad8d99954d3a9e46377fc7073d33b545ee71e` |
| `owner-goolake-whole-objects.json` | `e6a07d5d74992bce4e5886bc5121db3d12374b86143a78b1c52f63cd2d11185d` |
| `owner-goolake-whole-standard-shaders.json` | `447916fb9ecf8b3cb4985f7f7cc6c28c80d4d937f0b7785f8c85b813c1ecf2ec` |

Manual provenance, privacy, licensing and sensitive-content audit: profiles contain original
input selectors, file/body hashes, checked pointer relationships and authored import policies.
The existing animation packs supply clips/controllers; original Timeline assets retain their
script identity and differ only through checked references and the shipped properties-hash
owner. Director profiles use the existing PropertyName importer. Goolake retains the original
Dampcave Rigidbody/GameObject preload witness. Voidoutro uses the existing explicit
`_ALPHAMODULATE_ON` stripping policy qualified for Skymeadow spine; original keyword order
and compiled programs remain source-derived. Shader and Director profile bytes preserve the
qualified digests used by the object selections. No original body, curve, scalar array, pixel,
program, copied source, private path or credential is included. Every object, all ten serialized
members and all five compressed bundles are host raw-exact to J850. Phone production,
installation and original scene behavior remain open.

## Lakes, Lakesnight and Village source-scene selections (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-lakes-source-objects.json` | `06038b6c2f1b2430468a34982217335895b20abb9ba56144eba52177cffcbfe0` |
| `owner-lakes-source-lab-standard-shaders.json` | `5c07fb48414eca3d3842b2c0e8a8a096345dc4e7b2ef994ee8f56dc9e230bb28` |
| `owner-lakesnight-source-objects.json` | `32be87ed851edb32a1deb0e59c92b287662a65a27e03657f4fdaab8022f97ffd` |
| `owner-lakesnight-source-lab-standard-shaders.json` | `5c3dc310f61866139b766abe07c4d796bd229673240b8c55d54fea5eefcdac60` |
| `owner-village-source-objects.json` | `8aa6fe590e0cf1d983f9538ca27077e193cd0ea77e44727b5ac4891773ee13de` |
| `owner-village-source-lab-standard-shaders.json` | `ae4698a1b89b659349a047b7262e944030fa47cabc3dafee68dd5a96f51cd24c` |
| `owner-village-source-lab-postprocess-shaders.json` | `8d75bbdda25d9975348060f716d92386d6b211e21aefe887f7c15523e607f5f5` |

Manual provenance, privacy, licensing and sensitive-content audit: profiles contain original
input selectors, file/body hashes, checked pointer relationships, SDK/tool pins and authored
import policies only. Retained source selections now use the shipped generic original-body,
component, properties-hash and animated-wind owners. Shader programs come from the existing
SDK/exporter owners. Qualified Shader profile bytes preserve object pack reference digests.
No original body, curve, scalar array, pixel, program, copied source, private path or credential
is included. All 58,555 objects, six serialized members and three compressed bundles are
host raw-exact to J850. Phone production, installation and original behavior remain open.

## Compressed tangent normalization selection (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-compressed-tangent-mesh.json` | `85902c2e2ab235eba9e7bcd46de5baf6957c862bc6126f9ed355dcb7c47bb7a9` |

Manual provenance, privacy, licensing and sensitive-content audit: this profile contains
one original file/body selector, hashes, a destination relationship and the authored
`repair_negative_z` policy. Original compressed XY fields reconstruct a negative Z-squared
case; float32 normalization derives the new packing bounds and integers. No target float,
geometry, byte patch, original body, private path or credential is included. The original
mesh cohort profile remains immutable. Consulted pinned AssetRipper `1ac666f`
`CompressedMeshExtensions.GetTangents` and `PackedFloatVectorExtensions.Unpack` for the
normalization observation; implementation is independently authored. Guarded tracked-CLI
production persists before comparison and matches the one 1,564 B MercSwordSwipe mesh.
This record does not close a file readiness entry; complete Commando assembly and phone
production remain open. Generated outputs and raw comparison evidence remain ignored.

## Objective native bundle selections (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-native-alias-records.json` | `4f041c4fdb4b9b928c1301fb8fa207e060ad94cc4b1e40ad8e1ef43c5b54aab2` |
| `owner-objective-reused-records.json` | `59af5ea81ad9473f39c27cbd88e9f34b5be866c49a915bf479de10cbff27ad29` |
| `owner-objective-legacy-particle-shader.json` | `0c8c53f8075478878bf812b6bb89df9a34b44bc034d09bc928cb813e2b008304` |
| `owner-objective-support-objects.json` | `2fdab523dc067eebf70709078ad08b6c854baf3a2fdbd86ee28ce5230f7774cc` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles
contain original source selectors, expected hashes, checked pointer/component
relationships and authored transformation policies. Native aliases retain the
original class, script, schema and all nonpointer bytes; duplicate source
fingerprints are permitted only when checked relocation reproduces the selected
record. The qualified alias cohort also supplies future Commando/Labgeometry
assembly; it does not close those complete bundles.

Reused records select receipt-pinned, source-produced player/Shader outputs;
no earlier producer was replayed. The object owner checks schema-declared
relocations and derives fieldless authored component metadata from a produced
MonoScript and the pinned SDK base. Default materials reuse SDK declarations and
original Shader properties. Sprite GUIDs name the local standalone import;
coordinates remain derived from original crop data. The Legacy particle Shader
uses the explicitly pinned SDK source and prefab/no-fog variant policy. Bundle
preload order records authored build relationships; an explicit 16-byte resource
alignment policy supplies only measured zero padding after the final extent. No original scalar/geometry
array, program, pixel, copied source, private path, device identifier or credential
is included. Original legitimate PC input and the acquired SDK remain required.

All 1,623 persisted objects, every member and the 543,216-byte
compressed Objective bundle are host raw-exact to J850. Evidence stays ignored
under `work/coordination/orchestrator/objective-native-final-v5/`. Phone production,
installation and original game behavior remain open.

## Presentation native bundle selections (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-presentation-reused-records.json` | `3ae4b2168323b26c4a8d5fe4f071a6301d4f0b0f6b4077fe043cef29d61aa3fe` |
| `owner-presentation-objects.json` | `035b43e697027df07c4dd0087cc4b6a32622e214daa62658767d690be15e0357` |

Manual provenance, privacy, licensing and sensitive-content audit: these profiles
contain original schema selectors, expected hashes, authored build relationships
and receipt-pinned source-produced record selections. All 358 Shader bodies and
two generated material manifests reuse qualified player outputs without byte
changes or recompilation. The manifests remain generated by the existing player
owner from original metadata and authored transformations. Two textures reuse
the qualified original-input RGB owner. Original PC types supply embedded schema;
no target type tree or body is a production supplier. Container preload order
records authored build relationships. No program, pixel, original scalar or
geometry array, copied source, private path, device identifier or credential is
included. Legitimate original PC input and the acquired SDK remain required.

All 363 persisted objects, both members and the 3,337,229-byte
compressed presentation bundle are host raw-exact to J850. Evidence stays ignored
under `work/coordination/orchestrator/presentation-native-final-v1/`. Phone
production, installation and original game behavior remain open.

## Root-motion float math provenance

The bounded `small_atan2f` projection in `record_produce.py` adapts the
positive-x, small-argument branches of FreeBSD msun's
[s_atanf.c](https://github.com/freebsd/freebsd-src/blob/389ae8e4fabeaf1c655f8116b1a1402e597fa515/lib/msun/src/s_atanf.c)
and
[e_atan2f.c](https://github.com/freebsd/freebsd-src/blob/389ae8e4fabeaf1c655f8116b1a1402e597fa515/lib/msun/src/e_atan2f.c).
The original Sun permission notice is retained beside the routine. Its five
polynomial coefficients are public numerical-library constants. Native host
`atan2f` served only as a local diagnostic reference; production uses portable
float32 operations and original clip samples. The explicit projection preserves
existing root-average arithmetic for other selections.

Provenance, privacy, licensing and sensitive-content review: 2026-10-28. No game
coefficient, pose, curve, program, pixel, private identifier or SDK binary is
included. Raw comparisons and native-reference diagnostics remain ignored.

## Shader context transformation provenance

`shader_context.py` reuses explicitly qualified source-produced Shader records
while deriving editor pass identities from original dummy properties or SDK
snippets, compiler capabilities, settings and common includes. It delegates the
existing public source generator and pass-key algorithm. Checked schema spans
limit changes to editor identities; compiled programs and unrelated data remain
source-produced. Profile/provider/input/extent hashes guard the resulting pack.
This accommodates the observed Gamma/SDK33 to Linear/SDK45 metadata-context
difference without recompiling identical programs or supplying accepted keys.

Provenance, privacy, licensing and sensitive-content review: 2026-10-28. No target
pass-key table, program, SDK include, copied source, private path, device identity
or game property values are included. Generated source, records and diagnostics
remain ignored; legitimate original input and acquired SDK remain required.

## Native Sprite transformation provenance

`sprite_produce.py` reconstructs native Sprite inputs from the user's original
Sprite/Texture2D records. It reuses the audited public block decoder and existing
source crop arithmetic. Its PNG writer only packages decoded source pixels;
`SpriteNativeFixture.cs` calls the exact SDK's runtime constructor to derive
mesh and fallback physics data. `sprite_native_record.py` retains original
serialization, zero-UV convention, references and unrelated fields, deriving
new stream allocations from native vertex/index counts. Importer GUIDs and
pointer mappings name only required source/build relationships. The native
provider and every resulting record are hash-checked; exported images and
accepted body/geometry tables are not production suppliers.

Provenance, privacy, licensing and sensitive-content review: 2026-10-28. These
authored transformations include no game pixel, geometry, physics polygon,
program, copied source, SDK binary, private path or device identifier. Generated
images, native outputs and device comparisons remain ignored. The original
legitimate input and acquired SDK remain required.

## Prefab Shader transformation provenance

`shader_prefab.py` composes existing source generation, standalone compilation
and SDK record serialization. It selects no-scene runtime axes from SDK
declarations, particle features from acquired default materials and native
particle order from original Shader metadata. Dummy forms use original
properties and pinned public exporter templates; inherited SDK snippet order
owns fallback keyword registration. SDK dependency traversal maps only named
destination relationships. Complete body pins verify results without supplying
programs or accepted keyword tables.

Provenance, privacy, licensing and sensitive-content review: 2026-10-28. Public
code contains no game properties, ShaderLab expressions, program bytes, SDK
binaries/includes, private paths or device identifiers. Generated source and
records stay ignored; legitimate original input and the acquired SDK remain
required. The compiler/codec owners retain their cleanup and failure evidence.

## Grouped prefab container transformation provenance

`bundle_preload.py` derives preload closure from typed source-produced objects.
Profiles name asset paths, original or authored importer GUIDs and imported
root identities; those relationships group subassets and determine Unity GUID
ordering. Original component selectors, whole/body pins, GameObject back-links
and membership validate external owner relationships. Resource identities and
serialized member names determine file order. Existing bundle framing writes
shared preload ranges and sorted container entries after producing all objects.
No accepted container/preload array or game content table is supplied.

Prior art: pinned AssetRipper `1ac666f` AssetBundleExtensions separates bundle
name from collection name, and Pass103 PPtrNodeHelper enumerates dependencies
with their field paths. Existing typed readers provide that boundary; current
source metadata and comparison evidence determine native grouping/order.
Provenance, privacy, licensing and sensitive-content review: 2026-10-28. Public
code contains format rules and identity relationships only, with no copied
upstream implementation, original bodies, private paths or device identifiers.

## Unchanged script metadata provenance

`object_produce.py` may retain the editor properties hash embedded in the
original MonoScript when its identity and runtime schema match the selected
MonoBehaviour exactly. Profiles select original records and the retention
policy; no accepted hashes or replacement schemas are inputs. Schema omission
policies still derive their own hashes. RunPresence's existing counter omission
now emits Unity common-string type labels, preserving its decoded field tree.

Reviewed pinned AssetRipper `1ac666f` MonoScriptExtensions identity comparison
and AnimationCurveExtensions' versioned curve boundary alongside the acquired
SDK and original metadata. Editor-only curve details need no new recovery when
the legitimate MonoScript already supplies their property identity. Provenance,
privacy, licensing and sensitive-content audit: 2026-10-28. No script-property hash literal,
curve value, node table, program, private path or device identifier is tracked.

## Complete Commando source selections (2026-10-28)

| Recipe | SHA-256 |
| --- | --- |
| `owner-commando-objects.json` | `84fc4e68b52ba80ca101333b0b9e4735b5f3dc96db468f73a7086cbcdd457605` |
| `owner-commando-reused-records.json` | `5440ce0007c9d69c6f5bd82f500a97caae8fffe1ed1b6dc7f76be96ad45ee37f` |
| `owner-commando-original-sprites-1.json` | `503c9feb21cf0865a6429c4a5d51f5b97ee2767b8235e9454635041bf1efb09f` |
| `owner-commando-sdk-shaders.json` | `9d109f1048dbc1bdddbae266dd4fee798be5328ef759226611262adbcf8e3ede` |
| `owner-commando-native-sprites-2.json` | `12f487a6c66e4645820a8a73b4e597fd9134b906ccf68bc7a323ae0bd2b9b594` |
| `owner-commando-original-sprites-2.json` | `d55cfe90cacd5f8b27924b2a7f6f790f2231bb81c2f0c22e7c31676ddb65fe16` |
| `owner-commando-shader-context.json` | `9aa18a1fc48f4bb406cb52b585aa4fa2f24956a5b8807c327ac5495ed30e8452` |
| `owner-commando-native-sprites-3.json` | `e42a307b1f0bf64785ccc9334f2ac765d4ae9308bb1dcf84ded24f4cae23a45c` |
| `owner-commando-animation-records.json` | `ca92c2afe7d58f52372fe036e7997c0edbe58d015e7deb25fad0880c348ad1d9` |
| `owner-commando-dummy-shaders-1.json` | `fe854ab6c532125f223378d66bfd7ec221d96b1067f2130009500407f1c520bc` |
| `owner-commando-native-sprites-1.json` | `2e60a186dce679c50288a4d09f57e77eb05ec2880060a0fd1902080a604e11ef` |
| `owner-commando-fallback-shaders.json` | `2104145b499f7e7cb6489d7589f19d29368f10415b6575e7dec832c73172300f` |
| `owner-commando-particle-shader.json` | `8dd5f5febaca10abdec83d1f0a5ef8bfedc8af0aa3a28e0121bb1532dfecc671` |
| `owner-commando-dummy-shaders-2.json` | `5863b4e8e6549a2ba3d23b4b45ce6b68b3e323b3fd55eb4d7f27813774896176` |
| `owner-commando-crosshair-sprite.json` | `b4a02c56fca0af8926914d20e9fee2a7f12ea59f4bb7a4fa2f4a76eee52eefe3` |
| `owner-commando-dummy-shaders-3.json` | `28f54e8e82c93611267028655bf5abdb838166ca154ef8af68c7eff32cb057a7` |

These profiles complete `commando-prefab-lab` through the existing original-object,
record, Sprite, SDK Shader, template Shader and record-remap owners. All 75,378
persisted objects, the serialized/resource members and the 87,954,431-byte bundle
are host raw-exact to J850 (`50a6af87…`). Profile bytes are preserved exactly so
explicit record-provider receipt hashes remain reproducible.

Production starts with original selectors and the acquired SDK. The animation,
original Sprite and crosshair profiles use `record_produce.py`; native Sprite
profiles use `sprite_produce.py` with its source-pixel request generator and the
repository's exact-SDK fixture. SDK/fallback/particle Shader profiles use
`shader_prefab.py`, dummy profiles use `payload_shader_records.py`, and the context
profile uses `shader_context.py` with the explicit existing Barrier source pack.
`record_remap.py` extracts the reused records from the already-qualified original/
SDK player and Objective providers. `object_produce.py` takes the full object
profile, these independently produced packs and the existing hierarchy, generic,
mesh, texture and avatar providers as explicit receipt-pinned CLI inputs. No
retained run directory is an implicit supplier; generators and required local
SDK/fixture inputs remain described in `docs/LOCAL_STATE.md`.

Manual provenance, privacy, licensing and sensitive-content audit: the profiles
contain original selectors, hashes, minimal GUID/root/pointer relationships and
authored transformation policies. Native Sprite geometry is generated locally
from original pixels; curves, poses, programs, textures and original bodies are
never embedded in recipes. Original script hashes retain their original identity
and unchanged schema; grouped preloads derive from the produced typed graph.
No original code, game-derived body, scalar/geometry/program table, private path,
device identifier, credential or redistribution payload is published. Phone
production of the complete bundle, installation and gameplay readiness remain
open; host byte equality is the only closure here.

## Labgeometry source selections (2026-10-29)

| Recipe | SHA-256 |
| --- | --- |
| `owner-labgeometry-meshes.json` | `6725e325f560e5ac2e75c39b8e0c06de72aaf9dbace3e7ac663180c74ad454da` |
| `owner-labgeometry-shaders.json` | `020afc23cb7a813b74a01d870f1f085d1d6c5c9e841f5acdfd512e03d36cd223` |
| `owner-labgeometry-objects.json` | `0c35f4a9c60b8bd0267300a35e850d6f3fffa33ff731dd7c03a8108c583e5825` |

All 10 objects, the serialized member and the 108,365-byte `labgeometry` bundle
are host raw-exact to J850 (`09ca79f4bd66…`). `mesh_produce.py` regenerates the
static OBJ mesh from original geometry through separately acquired pinned public
MikkTSpace and Apple BSD sort sources; `build_mesh_obj.py` builds that helper.
`shader_prefab.py` compiles the SDK Standard Shader with its explicitly selected
SDK material's instancing setting. `object_produce.py` consumes those packs and
`owner-native-alias-records.json`, constructs default OBJ hierarchy nodes, derives
the Lambert material from original/SDK metadata, and derives grouped preloads
from the produced graph. Pass all provider directories and receipts explicitly.
The model material reads the supplied SDK FBX library statically without loading
native SDK code. Generated outputs and comparison evidence remain ignored.

Manual provenance, privacy, licensing and sensitive-content audit: these profiles
contain minimum original asset/type identities, importer/root/PPtr relationships,
expected hashes and authored transformation policies. Source attributes and SDK
property declarations/defaults determine geometry, tangents, material values and
programs locally. No copied game/SDK source, native instruction sequence, protected
body, property-value table, vertex/program array, private path, device identifier,
credential or redistribution payload is published. Public helper dependencies
retain their notices; the separately acquired SDK and legitimate game remain
required. Evidence: `work/coordination/orchestrator/labgeometry-native-final-v2/`.
Phone production of the complete bundle, installation and game behavior remain open.

## Public startup metadata policy

`startup_metadata.py` derives app/build identifiers from complete source inventory,
public settings, toolchain and producer hashes. Its five boot options are authored
converter policy and public PlayerSettings, with no development connection fields.
Manual provenance/privacy/licensing review: no historical identifier, private
configuration, target byte span, game content, SDK implementation or credential
is embedded. No identity used for ownership, authentication, signing or saved-data
placement is replaced. Outputs/receipts remain ignored; host qualification is
recorded under `work/coordination/orchestrator/public-startup-metadata-v2/`.

## Source Menu profile

| Recipe | SHA-256 |
| --- | --- |
| `owner-player-menu.json` | `c4b96578385df9882b4253dd37f5eb50e5aadafef423205a358deff966a3361c` |

`owner-player-menu.json` selects minimum original UI/script/dependency members,
the original prefab root, public English tokens and authored hide/action policies.
It pins four separately supplied SDK UGUI source files and existing public texture
recipes. `player_ui.py` derives all component values, geometry, pixels, script
metadata and references locally; no saved prefab or historical ID map is supplied.
Manual provenance/privacy/licensing review: the profile contains identifiers,
source hashes and authored policy only, with no copied game/SDK code, asset body,
pixel/geometry table, private path, connection value or credential. Outputs and
receipts remain ignored. Genuine J850 field differences and phone/runtime
acceptance remain open; evidence: `work/coordination/orchestrator/menu-public-source-v1/`.

## Original-record stage contexts

| Recipe | SHA-256 |
| --- | --- |
| `owner-stage-contexts.json` | `e9098b415c66f74530b23aac1206443f0932daf7619b6c6ad192ef6e254ea807` |

The recipe selects 23 original scene members, population component IDs, original
catalog pool suppliers and TextAsset type metadata. Four required global roots
and an optional camera use the existing authored suppression policy. It contains
only minimum input identities/hashes and authored policy: no exported scene,
accepted context, game field-value table, protected implementation, SDK body,
private configuration, device identifier or credential. All policy values,
identity/toggle graphs and catalog keys are read from legitimate source records.
Manual provenance/privacy/licensing review: source selectors do not substitute
for owning the game; generated files and receipts remain ignored. Member and
canonical graph digests explicitly replace incidental exporter YAML hashes;
the complete public profile and producer hashes bind graph provenance.
Evidence: `work/coordination/orchestrator/stage-context-public-v2/`.
Complete phone production and runtime compatibility remain open.

## Original baked reflection retention audit (2026-10-29)

`owner-source-baked-reflections.json` selects two original BC6H Cubemaps from
the accepted legitimate installation using the existing texture profile shape.
`cube-preserve` verifies six complete face/mip chains and retains their bytes,
format, color space, usage and mip count. Output hashes describe independently
rewrapped source records, not captured J850 pixels. Native Android loading,
17,825,760 sampled float components across compressed/lossless controls and HDR
decode vectors pass (J1260); complete scene relationships and file admission
remain open. The qualified 110-record historical profile is unchanged.

Provenance, privacy, licensing and sensitive-content audit: selectors, extents,
hashes and minimum storage/identity relationships only. No pixel/block arrays,
serialized body/type templates, proprietary implementation, SDK bytes, private
settings/paths, device identifiers or credentials are published. Original input
hashes are rechecked before success. No game/SDK redistribution, ownership,
authentication or entitlement success is granted. Pinned AssetRipper
TextureConverter/ExrWriter informs face/chain ownership; its exporter does not
regenerate baked lighting. The operation consumes no codec or private fixture;
all generated packs, APKs and raw observations stay ignored. Native BC6H support
must be established before selecting this profile on another device.

## Complete original-lighting scene alternatives audit (2026-10-29)

| Recipe | Scope | Tracked information | Boundaries | Owner and evidence |
| --- | --- | --- | --- | --- |
| `owner-promovoidsurvivor-source-lighting-objects.json` | Complete source lighting scene | Original selectors, checked relationships, public policy and hashes. | No body/type/pixel/program literals or private inputs; audit below, 2026-10-29. | `object_produce.py`; J1261 host complete-file qualification, phone/runtime gate open. |
| `owner-promovoidsurvivor-source-lighting-textures.json` | Three original BC6H reflection chains | Original selectors, checked relationships, public policy and hashes. | No body/type/pixel/program literals or private inputs; audit below, 2026-10-29. | `texture_produce.py`; J1261 host complete-file qualification, phone/runtime gate open. |
| `owner-promovoidsurvivor-standard-shaders.json` | Original Standard Shader | Original selectors, checked relationships, public policy and hashes. | No body/type/pixel/program literals or private inputs; audit below, 2026-10-29. | `payload_shader_records.py`; J1261 host complete-file qualification, phone/runtime gate open. |
| `owner-promovoidsurvivor-postprocess-shaders.json` | Original post-processing Shaders | Original selectors, checked relationships, public policy and hashes. | No body/type/pixel/program literals or private inputs; audit below, 2026-10-29. | `payload_shader_records.py`; J1261 host complete-file qualification, phone/runtime gate open. |
| `owner-snowyforest-source-lighting-objects.json` | Complete source lighting scene | Original selectors, checked relationships, public policy and hashes. | No body/type/pixel/program literals or private inputs; audit below, 2026-10-29. | `object_produce.py`; J1261 host complete-file qualification, phone/runtime gate open. |
| `owner-snowyforest-source-lighting-textures.json` | Three original BC6H reflection chains | Original selectors, checked relationships, public policy and hashes. | No body/type/pixel/program literals or private inputs; audit below, 2026-10-29. | `texture_produce.py`; J1261 host complete-file qualification, phone/runtime gate open. |
| `owner-snowyforest-standard-shaders.json` | Original Standard Shader | Original selectors, checked relationships, public policy and hashes. | No body/type/pixel/program literals or private inputs; audit below, 2026-10-29. | `payload_shader_records.py`; J1261 host complete-file qualification, phone/runtime gate open. |
| `owner-snowyforest-postprocess-shaders.json` | Original post-processing Shaders | Original selectors, checked relationships, public policy and hashes. | No body/type/pixel/program literals or private inputs; audit below, 2026-10-29. | `payload_shader_records.py`; J1261 host complete-file qualification, phone/runtime gate open. |
| `owner-promovoidsurvivor-timeline-records.json` | Complete imported Director record | Original selectors, binding identities, authored null relationships and hashes. | No curve/pose/event/body literal or private inputs; audit below, 2026-10-29. | `record_produce.py`; J1261 full-file host qualification, phone/runtime gate open. |

J1261: `owner-promovoidsurvivor-source-lighting-objects.json` and
`owner-snowyforest-source-lighting-objects.json` select complete source records,
types, hash expectations and minimum relocated relationships. Their companion
`source-lighting-textures`, `standard-shaders` and `postprocess-shaders` profiles
select original reflections and existing source shader transformations. Promo's
`owner-promovoidsurvivor-timeline-records.json` additionally declares imported
unbound track relationships; null bindings introduce no animation/event data.
All other required packs use existing public mesh, texture and animation recipes;
producer/recipe closure is listed in the accepted-output README.

Provenance, privacy, licensing and sensitive-content audit: all nine new profiles
contain source selectors, identifiers, field extents, reconstruction policy and
hashes only. The complete object profiles contain no floating-point literals or
long encoded strings. They contain no pixels, geometry/curve/coefficient arrays,
serialized body/type templates, proprietary implementation, SDK bytes, private
paths/settings, device/account identifiers, credentials or signing material.
Original reflection and ambient data are read from legitimate game records.
All producer inputs are public recipes, the owner's installation, permitted SDK
and pinned public tooling; every required source-pack profile is published.
Guarded complete-file production denies target bundles, exports and preparation
captures. Independent comparison checks every object/type, all resource bytes
and native references. Native BC6H is an explicit device capability gate; full
game-runtime qualification and historical raw-exact admission remain open.
Existing source/tool licensing applies; no redistribution, ownership,
authentication or entitlement success is granted. Generated outputs stay ignored.

## Source HUD profile

| Recipe | Source | Audit | Consumer |
| --- | --- | --- | --- |
| `owner-player-hud.json` | Original UI/script/dependency selectors and existing texture recipes. | Identifiers, hashes and source relationships only; audit below, 2026-10-29. | `player_hud.py`; J1264 host-only, native runtime gate open. |

`owner-player-hud.json` SHA-256
`471b7f74f5e9143c0dfe7bba03c5138389a019d9f55b40fa581f881f75bd2241`
selects four original UI roots, original script/dependency members and five existing
public texture recipes. `player_hud.py` derives all hierarchy, fields, schemas,
geometry, pixels and relationships locally through the public HUD constructor.
Manual provenance/privacy/licensing/sensitive-content review: identifiers, hashes
and minimum source relationships only; no captured target IDs, prefab/body/field
value tables, protected implementation, SDK bytes, private settings or credentials.
Generated outputs and evidence stay ignored. Public-input evidence:
`work/coordination/orchestrator/hud-public-source-v1/`. Historical graph differences,
complete phone production and native runtime acceptance remain open.

## Source native manager profile

| Recipe | Source | Audit | Consumer |
| --- | --- | --- | --- |
| `owner-player-managers.json` | Original manager selection, public settings/source pins and authored startup/capability policy. | Identifiers, hashes and public policy only; audit below, 2026-10-29. | `player_managers.py`; J1265 host-only, native runtime gate open. |

Profile SHA-256: `0ec07f8658fb40f22cf3d8db4ea3e2878888d94aa9f184a756b9475626d24350`.
The recipe pins original manager metadata, public project/settings owners and
existing shader/context/copy recipes. It disables paid capability flags, retains
on-demand shader loading and selects the SDK's default dynamic batching for the
empty public platform override. This declares converter behavior; it grants no
SDK rights and asserts no ownership, authentication or entitlement success.

Manual provenance/privacy/licensing/sensitive-content review: source selectors,
hashes and authored configuration only. No captured manager body, target graph,
private connection/license value, game field table, SDK implementation/table,
credential or signing material is published. Original records, supplied SDK and
fresh source-phase outputs provide every serialized value and relationship.
PyYAML 6.0.3's pure Python SafeLoader reads public settings; digit-only encoded
arrays retain their lexical representation. Dependencies retain their licenses.
Evidence: `work/coordination/orchestrator/manager-public-source-v4/`.
Independent build identity, unused historical hash-cache entries and current UI
graph differences remain explicit; full phone/runtime acceptance remains open.

## Source default-scene profile

| Recipe | Source | Audit | Consumer |
| --- | --- | --- | --- |
| `owner-default-scene.json` | Original native record selectors, public Lab scene policy and exact SDK/source pins. | Identifiers, hashes and authored configuration only; audit below, 2026-10-29. | `player_scene.py`; native lighting/load qualification remains open. |

Profile SHA-256: `c02e13f130379c3d33eaf35260f28cc09173cd4e33179f6771013a0585c44a6d`.
This profile names the minimum original native suppliers and the public camera,
light and primitive policy. Built-in tag numbers and Cube identity are read from
the supplied SDK; local object IDs follow independent construction order. Native
schemas and fieldless diagnostics properties must match the source registry.

Manual provenance/privacy/licensing/sensitive-content review: no serialized game
body, native field dump, historical IDs, baked pixels/coefficients, SDK code or
registration table, private configuration, credential or signing input is stored.
The explicit environment inputs are generated phase outputs, with request,
material, face/mip and source-owner checks. The material is compared with the
legitimate default sky's parameters; no protected parameter table is published.
All output remains ignored. Host-built diagnostic inputs qualify the API only;
phone-built tool construction, native scene loading and lighting compatibility
remain open. Historical readiness is unchanged. Evidence:
`work/coordination/orchestrator/default-scene-public-v2/`.

## Moon2 source spine lighting

| Profile | Scope | Provenance and privacy audit | Owner/evidence |
| --- | --- | --- | --- |
| `owner-moon2-spine-source-lighting-objects.json` | Complete 30,450-record legacy Moon2 scene | Original selectors, relationships, named lab activation policy and hashes only. | `object_produce.py`; J1268, host source candidate; full phone/runtime gate open. |
| `owner-moon2-spine-source-lighting-textures.json` | Original baked reflection, complete face/mip chain | Original record/resource selectors, layout extents and hashes only. | `texture_produce.py`, `cube-preserve`; J1268. |

2026-10-29 provenance/privacy/licensing/sensitive-content audit: both profiles
contain no serialized bodies/types, pixels, protected implementation, numeric
lighting/material data, private paths/settings, account/device identifiers or
signing material. The object policy has no floating-point literals. Original
lighting and sky material relationships come from the legitimate input; all
required record-pack profiles are public and listed in the accepted-output README.
Native/script metadata and all 30,447 other bodies remain strict against J850.
The preload table preserves all historical dependencies and adds the original sky
material; source activation policy retains existing lab suppression. Guarded
production denies accepted bundles and preparation captures. SDK/tool licensing
and ownership/entitlement boundaries remain unchanged; no runtime distribution
or authentication success is granted. Generated outputs stay ignored. Complete
phone/game-runtime and install/update acceptance remain open.

## Snowy Forest source and spine lab lighting

| Profile | Scope | Provenance and privacy audit | Owner/evidence |
| --- | --- | --- | --- |
| `owner-snowyforest-source-lab-lighting-objects.json` | Complete 15,933-record source lab | Original selectors/relationships, existing lab policy and hashes only. | `object_produce.py`; J1269, phone/runtime gate open. |
| `owner-snowyforest-source-lab-lighting-textures.json` | Three original reflection chains | Original selectors, storage extents and hashes only. | `texture_produce.py`, `cube-preserve`; J1269. |
| `owner-snowyforest-spine-lab-lighting-objects.json` | Complete 14,001-record spine lab | Original selectors/relationships, existing lab policy and hashes only. | `object_produce.py`; J1269, phone/runtime gate open. |
| `owner-snowyforest-spine-lab-lighting-textures.json` | Three original reflection chains | Original selectors, storage extents and hashes only. | `texture_produce.py`, `cube-preserve`; J1269. |

2026-10-29 provenance/privacy/licensing/sensitive-content audit: all four profiles
contain no body/type templates, pixels, material/lighting coefficient literals,
protected implementation, private paths/configuration, account/device identifiers
or signing material. Object policies contain no floating-point literals. Source
lighting is read from the legitimate installation; every other record, native/
script identity, external identity and script table remains strict against J850.
The existing public pack owners and qualified Snowy Shader profiles supply all
other records; checked namespace aliases preserve each lab's local relationships.
No private generated artifact is required. Guarded production denies historical
bundles and preparation captures; independent full-file comparison verifies source
reflection faces/mips and native relationships. Existing tool/SDK licensing and
ownership/entitlement boundaries apply. No redistribution or authentication
success is granted. Full phone/game-runtime and install/update acceptance remain
open; generated outputs and raw evidence stay ignored.

### Whole-game native Sprite imports (J1272)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-native-sprites.json` | `100f834f8665f79b3075668d18e4b2f35866a6204753fddbad0125f95765d7d4` |

`owner-whole-game-native-sprites.json` (SHA-256
`100f834f8665f79b3075668d18e4b2f35866a6204753fddbad0125f95765d7d4`)
selects 757 original Sprite/Texture2D pairs and their minimum importer GUIDs,
output identities, pointer relationships and comparison hashes. It contains no
pixels, geometry, physics contours, native output or private configuration.
The existing public pixel decoder and exact SDK constructor generate those
outputs locally. The pinned AssetRipper `1ac666f` SpriteProcessor normalizes
crop/pivot/border before TextureExportCollection selects the importer mode.
The authored producer preserves that ordering and native pixel-pivot rounding.
Provenance/privacy review: original paths and GUIDs are reconstruction identities;
all game-derived PNGs, native geometry, records and device evidence stay ignored.
This adds no entitlement adapter, SDK redistribution or complete-game claim.

### Whole-game source records (J1273)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-source-records.json` | `56209ed460cf480fda51214d16a549e04223c19c89c9149c8b489ee908f925eb` |

Audit: minimum original bundle/member/object and MonoScript selectors, input and
output hashes, checked pointer relationships and native type identity hashes.
The 159 unchanged managed records use the existing SDK properties-hash rule;
39 native records retain their original type and nonpointer bytes. No game field
payload, type tree, source implementation, private configuration, SDK binary or
generated body is included. All 198 persisted bodies and native type identities
match J850; complete whole-game bundle and phone/runtime acceptance remain open.

### Whole-game material and compute records (J1274)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-material-compute-records.json` | `578cd86236afa06d1df29ad4ecba50e86e0e2487702bd2c65ceb057e3ae146a2` |

Audit: minimum original bundle/member/object selectors, hashes, checked pointer
relationships and existing named import policies only. The 130 materials retain
all original keyword strings and native values; the 24 compute records use the
existing checked DXBC-shell policy, retaining declarations and keywords. No game
field payload, type tree, shader program, SDK binary or private setting is
included. All 154 persisted bodies and native type identities match J850. These
compute shells supply no executable Android programs; complete bundle, phone
production and runtime acceptance remain open.

### Whole-game Shader records (J1275)

`S` uses `payload_shader_records.py`; `F` uses `shader_prefab.py`. Each row
pins a current original-input recipe.

| Recipe | Producer | SHA-256 |
| --- | --- | --- |
| `owner-whole-game-shader-02b1e6e9370c8791.json` | S | `8836fb1f617dffbe8d680d89b65f9f08f3eeeeb7d36165c6672715a560f1a6a7` |
| `owner-whole-game-shader-034fed06a241cf53.json` | S | `f62f49a8ff904e9b2d0d0bf2eca472979d816b55b6331125a36683fbeea7f419` |
| `owner-whole-game-shader-070de82e6cf2da18.json` | S | `c8a480b49bd0f9812bad3eec1aea092b6090de99ff3b41ed6f5505f6809e6303` |
| `owner-whole-game-shader-084c4240de06f760.json` | F | `4b0f783b9e833b1ce3b106748c2f93dc78b68a17a53e03347c51b86824360d28` |
| `owner-whole-game-shader-0df842e9796d40b4.json` | S | `3c34f73582757fa0f134d182758b868075672b318f585f66b7a1540e12f37655` |
| `owner-whole-game-shader-10f3b27d64b264f8.json` | F | `2d9cd4121d21a90c5cc48795ecf841218630a26520700c4272885339f3269d79` |
| `owner-whole-game-shader-10f74c3751e9b1f2.json` | F | `e0ebd197a4531f9d4097ad802418c1cd74abba4f50fd36685a0e484972a964af` |
| `owner-whole-game-shader-11736e6914b2b1ef.json` | F | `7dc4506be2f2869022f7c8a7f57c3688e3c2051a1e16fd0da5f0a00d24b036b2` |
| `owner-whole-game-shader-12652c99b63bc31d.json` | F | `abfbd18b76936902712ec7bb1fc289e1c2702c7255f37fef11dcc30b58bdfaaa` |
| `owner-whole-game-shader-126d20ddf6885aed.json` | S | `b5488e0638fe5606ba792583a88144f2b2a4eda80acf459b41ac709e5814f5df` |
| `owner-whole-game-shader-15d4d911b3052355.json` | S | `e8e440603607959e8839d9775e6df180f921722fc6dc6b908cd3c62e8b803e9b` |
| `owner-whole-game-shader-166772aece563fbc.json` | F | `c1d1350c6a239ec8786fd2c046d52fccdf19a42302da6f79c106d93a9b5d72b1` |
| `owner-whole-game-shader-1984988ea199266a.json` | S | `57b9c27e3e1e25633b75f7faa1d020312bfe9d98fde10a9252f8ba10bb5ba000` |
| `owner-whole-game-shader-1bd2823582554650.json` | F | `74dab9a770fd152fd52e0a35e0de7815884895a487801032138bfbf50d901bc5` |
| `owner-whole-game-shader-230d1be6fa62d96e.json` | S | `44b014060425d4d0af11aaf5775e34e523163df213bea6a345cfd2c04d388b27` |
| `owner-whole-game-shader-27d7abe9ab1b41d1.json` | F | `686b6c303fb2b6bc6a8a00e82e99137c8b2923cae7fbbe6652ff96cd47d24f0c` |
| `owner-whole-game-shader-2df5ef09fd9b26c1.json` | S | `9ffbfd92669c5fa28e9eb7fdedb4067bc21393764fab664d6e0a293573d2a8cf` |
| `owner-whole-game-shader-2f323612215e6871.json` | S | `749766d14872e0a0b1e6cf58b80a08640d7aa892622497c4bfdfbc2a5b69047e` |
| `owner-whole-game-shader-2fc6e0eb1fd573dd.json` | S | `f07df0521f86d0f0fbbdce4ff7a20afc507e970082599f615f7ebf91d0222ee8` |
| `owner-whole-game-shader-32f48bde88df56b8.json` | F | `a4d3f6af4b4ff6e1b84af01a49ce8747af733ae3045ccd374e7b802b231fd8b7` |
| `owner-whole-game-shader-3793415a1ec890af.json` | S | `ed25c5bc3e8730c3c6d36a73b3426aaf034a41ce568aebabb875c917bf0d2f25` |
| `owner-whole-game-shader-37eb61b60069d459.json` | S | `cb5e6313db4569720ab791844a409f92ad7bc222da9933c9e7e6636f4053dff1` |
| `owner-whole-game-shader-3aed6d462ae09235.json` | S | `9778f90ebb6e6ac5b80bfc5f312f645d406bac9f1f836315113644b99a0ef8f5` |
| `owner-whole-game-shader-3b722ab249c06fa5.json` | S | `bb2176e1c3e46163fdd6050f15dd6280f491bae6bb47e610477412ba9670810f` |
| `owner-whole-game-shader-3b7c0a2b60b39dda.json` | F | `1337459d0dfa3ee635efcd7058b856b339455b2484e6394fe638cdf77fc06e85` |
| `owner-whole-game-shader-3f03f5d706422ed7.json` | S | `dd8b96a606ff190116b828e62cfdb7a7d224e43bdde8c60124955bef5c8d973d` |
| `owner-whole-game-shader-42f9d38d37a8f1ec.json` | F | `022870c0efd48d1a432574e819205b4a8f9eec7bc8182309715264fc21035207` |
| `owner-whole-game-shader-449a91aa35081072.json` | F | `6487629edcf43d14de1f128bd13c465fde13e0102348e40eec3edb68bf27ad94` |
| `owner-whole-game-shader-44c69ea486cdbc3b.json` | S | `caf2b43ddf57b91b8fa1ddc1df64ef7997d2a1ca0a2b811b9b8d7097017d3c98` |
| `owner-whole-game-shader-46e4508af657c584.json` | S | `e3abab9523adea39a74937fd4337676cac1bcd48a6210e26b60740df8872b07a` |
| `owner-whole-game-shader-49a2f29f9f475e6b.json` | S | `55910b35c106656f779bbc0b21a2b5e145dceeca408ca169c4f2f3b8a2e1d429` |
| `owner-whole-game-shader-4e49d851def9ed88.json` | S | `8b929175cd9e7993bea09a6ea4f1c80639a072276ae109bbda8c89a39abb0766` |
| `owner-whole-game-shader-515983f7190a3b0b.json` | S | `1e26e58df3f8af6a0af8d467a888bbb0aa71997bd6f51851c3ad59421845d9b9` |
| `owner-whole-game-shader-532c55ed3d24cfac.json` | S | `75c47dbafe164e6c994765c7f5fafdfca09ee015fb7b676ddb099d7d69d5b444` |
| `owner-whole-game-shader-53780e664f859ed3.json` | F | `f1b2ecf574b7308c17849add035b90d1de4e0984468e2d992753729b9818fe68` |
| `owner-whole-game-shader-599a14580b0459cf.json` | F | `2cf40f6bcb29af0b96617a8c68027b0a7ad647ba08555d1aae02f0440778afa6` |
| `owner-whole-game-shader-5b0b82f27f82e1cc.json` | F | `85de14ec662ff04f2f719fefc7586fc4588165fd213694237ba101f7744274b8` |
| `owner-whole-game-shader-5bb1fd1123fbd18d.json` | S | `d868ada915a9b5298b2a537a240ba568886e61346144a3ff97619345e5d7e010` |
| `owner-whole-game-shader-5bce32ea30c543fc.json` | S | `087011fa075d7e8f33599d7358cd6d09674dd9e4dd87e9e1f4acfe020fcfb4cb` |
| `owner-whole-game-shader-5c02866f0f89ee19.json` | S | `e973dc0196c0511c7b0b9669de24749fb3eedb470181faf5e95bbc086d44573f` |
| `owner-whole-game-shader-5d2dbb5ed3989742.json` | S | `ec1d6b0e0a3180033d67a8df695557d9d6c3b9efddc1fbc650918cf38e3af628` |
| `owner-whole-game-shader-60a0ecc9c15294f6.json` | F | `6910ff79bd51333ba184f59e25811c722471a69ea76452f026f774a720d62e16` |
| `owner-whole-game-shader-61725b5f506b57f4.json` | S | `0ab6fe88a01ba25de793686f2adcf492a37da2cc706ce266034eb01b7a7d2862` |
| `owner-whole-game-shader-6175a41c51b80943.json` | F | `c51defb638df6e48b1aa9a2e002a3fc70cfb74fde98619d38ae8ef1a230c8649` |
| `owner-whole-game-shader-61ac51f1a6278c21.json` | S | `3554a7cd18def14f7b52888fb7b48da51edb8e87aad9866a90059fc35b8d7d4f` |
| `owner-whole-game-shader-647566a51860cd88.json` | S | `6875a4c6c8ee04b7e7144f7a347cb96bb2b23abf1c5c3b6e0f9047c30325cde2` |
| `owner-whole-game-shader-6533208cff9364ae.json` | F | `e412281d1c8a3aa59c0cc68d22736ee9dcb83e3c61db4741bb929df5940e9033` |
| `owner-whole-game-shader-65bc6451e47df640.json` | S | `e371df649843974d305c3cdccddb304b07c90046b5ebd465182ab43e2aaa2d08` |
| `owner-whole-game-shader-66151dfc1e50de53.json` | S | `2d84d58f7d47935778465e51e700624760655abba854ff45d565d24e6191cc31` |
| `owner-whole-game-shader-67be9f5752370119.json` | F | `5d3c4fe68faf768fb0e3f836b45f06aa8bb047e0c06f3cbda846ca655f2a85f6` |
| `owner-whole-game-shader-68f9cbdffccc4c63.json` | S | `a06fa73e159192f12252e06d708c60162df24aee63462e2b0f6ccc0f91e25bd6` |
| `owner-whole-game-shader-7824188d699af013.json` | S | `8f2ea997c8a74fe9805518cb903b52fcb45af25be87118248c470ba7105b7b06` |
| `owner-whole-game-shader-78a1f9d5c3679a16.json` | S | `16f699b51dd21ee56035e3fb3be212dbd6d4269e726895434e12a13e2b817c6b` |
| `owner-whole-game-shader-7972df511852774c.json` | F | `8f31da18f6f1f9e0de4c522c3f514a054294286bfdc64ef17b18ae33d17ce55c` |
| `owner-whole-game-shader-7c853f6e8c0bd51f.json` | S | `adf72ac044d178fdccc6bf3290d34978aa5c5ac1da0be44a7e35e0c6e8078a71` |
| `owner-whole-game-shader-7db3c9aecbd21e4b.json` | S | `0051ec36f18c04bb0911bf3847601a7d9fc35ba16d5b3f864269a539200a6bbf` |
| `owner-whole-game-shader-7e5cc8e11f2d0296.json` | S | `8c801a8b02d46838e1c36478ed0c041947ab155f181a2597ff96962e2ce10ae1` |
| `owner-whole-game-shader-7eb41628e2e25ec9.json` | S | `df63557b3756f601e5fa7a41f9c4040f05684f569ae24a321f0d7cb8f96ec0b5` |
| `owner-whole-game-shader-7f501270ae51a30e.json` | F | `7439b2746491e7d8c15ba180be3e59fbfc7126ff5f7c4d4a782ee5acf423686b` |
| `owner-whole-game-shader-81ed6ad28b4bac31.json` | S | `fa585c2aaa18000b55afbbeffb35410581498e0c4e467643485e7642298afab3` |
| `owner-whole-game-shader-86a15f60b1145c37.json` | S | `afa44a467fd0cce88273435b4d5f823e676a20e6605b0f70fd3e255133999c68` |
| `owner-whole-game-shader-87a2b9f5418f0dab.json` | S | `5a639d38e1b7d061ce92b1d1bb29e0443b205d5c73b8c3035a6c859f44ccc015` |
| `owner-whole-game-shader-883cabdb92759697.json` | F | `3bb8a9f77bb65c849481da320555075288c26611228376956fe7b5b077699e40` |
| `owner-whole-game-shader-89800c6dd864f5e9.json` | F | `9b317c0f7418ab90bd4f6a07da30867d2a8752a84ad3100b783e6ab1043beca7` |
| `owner-whole-game-shader-8be7ae4b8896070d.json` | S | `820449891b33e8a55a93acf4391781fcb09c10322b75f48713f8f809ee84e3b8` |
| `owner-whole-game-shader-8c4ce654e8d23f5a.json` | S | `ed3e44f9cdfbdce038de525d91a84ebfe13dc3a5b3e7746d667a7c0cbf6d873e` |
| `owner-whole-game-shader-8cb5d4399b6e0722.json` | S | `7838fb4f5e80a5698d29723034e6e329ce9ae67c0e871d9121385ce5cf0a24f0` |
| `owner-whole-game-shader-8e83f5a7d3e231ef.json` | S | `f5523849d3906eaa47d6e1fb6cc02974188b3edd4b3e0fe241a3b128359cc160` |
| `owner-whole-game-shader-912669ffb1c93663.json` | S | `81a699079fd1a0393b2862de219e2a990babef4cdb82951835cee53b9121bed6` |
| `owner-whole-game-shader-912e0b52dc8a3d2f.json` | F | `e6f89bbc05c6647a4e26f6f6003ce13ea1fed7b030c3e4db6790eaeb6745360b` |
| `owner-whole-game-shader-91f604b3530fd829.json` | S | `9b0e7bfdbe9a389c465d9de396595d5d9851bbd567776f7506f744b380dd58c2` |
| `owner-whole-game-shader-94add932987060ed.json` | F | `1485be301a50f119811fef8262c6bf920003130d11a8b560a27821d7858daf63` |
| `owner-whole-game-shader-959647ed2410089f.json` | S | `c7af35876140f4b5f8f1aef02f4aa42a37c4178e4918bd96fdec8ffa5a4c1de8` |
| `owner-whole-game-shader-9eccc184552cae8e.json` | S | `1bb137d2ec26900106b902be2c03a5847b6390e6bdde5582723a387faaf37d69` |
| `owner-whole-game-shader-a056d464c41f7d17.json` | F | `12a6d2b609bcb494e6a8984f35e96cf2efd3b7cee68009b1c8c92c3243f662d6` |
| `owner-whole-game-shader-a1fd6d502a9658bf.json` | S | `db7379bdaf304a499e71041b1b60b3754defd0a0c3b7246133c8689fe21952c7` |
| `owner-whole-game-shader-a4e447b7dfb74c41.json` | S | `175316b5e34ea3e87c8dd5c8289711c608ef60e18a303bef61dc9adc7d373bb6` |
| `owner-whole-game-shader-a52e461039bea821.json` | S | `57cc02d680d51a84da5c9f1466b4c61d43cc3eb978d2e59fe7aaac0a34bf7361` |
| `owner-whole-game-shader-a54e3b741e838107.json` | S | `af6411444d5a281f131b76c02364b99065a2576b6b21b8e4d9fba389fd31348d` |
| `owner-whole-game-shader-a806534dcc01a1a7.json` | S | `98260e278d094661fe5c31d4614aa5f28fe812b7d9c498c1d4cf2ed25b6c5eea` |
| `owner-whole-game-shader-a991b143408c77f2.json` | S | `6baab3633db358d559b5fd714432fd7f7248b67d7cb2173d919205218255a413` |
| `owner-whole-game-shader-abccadfad647c15c.json` | S | `31881d452b080037f1f159de6b96e89d6b69a5ad2c59ee429d24ae1443b5ca01` |
| `owner-whole-game-shader-ad2a3ce1f02f5aff.json` | S | `7a6c544676a44065e831b0252be49d8d8e22050ed4f011d647e9c60abd423248` |
| `owner-whole-game-shader-b0a7072e58e7bb60.json` | S | `5ce596f3513b6706061d09802a263999456519a907b8371246ef2b59c1081629` |
| `owner-whole-game-shader-bae2f7d5ab826699.json` | S | `bf31e263b7ad3845ad5899049aa671da35e174049dae6f47bff2f35f55f3ea6b` |
| `owner-whole-game-shader-bcdadc4fbcfeaebf.json` | F | `39f4c887d6e5e3b22c00ce8aa6b1fe2a55b72fac69922040a184c09714dc5ebe` |
| `owner-whole-game-shader-be20eb501f634e8e.json` | F | `67ad72e8ac19098fdadee189639091ca59f8b292c219dd1b953570acadd2e965` |
| `owner-whole-game-shader-be57447e98fc3b40.json` | S | `7e7a5cacf40033befe6b16702500e1468b2e62edde45c8b6aba718785cff5e69` |
| `owner-whole-game-shader-bfeb1f932a13aced.json` | F | `b196abe89141308011bb18a6ee526b0c5074d8a2db78c370994c6e5190f8f878` |
| `owner-whole-game-shader-c241bea3e672b193.json` | S | `157211392a7254863700cec25f3a642bd2ecd7e99654111b7388d6423c422dde` |
| `owner-whole-game-shader-c653b61cdd6dc6df.json` | S | `62cd44dffb53c8b2e22ed0e87f73bc00654dffcecf63054a7ef52b54d7340d84` |
| `owner-whole-game-shader-c904328f54247fc9.json` | F | `e7b1939cfea0a5d3b394cbc0ddc3afab2b442cbb4960cdbaffa3b0237c6518ea` |
| `owner-whole-game-shader-ca1c6d4095d4ad7c.json` | S | `5d822f76119459e41702fef923bc890b92c65d4ccf69e1a83d2e6fc25917baa3` |
| `owner-whole-game-shader-ca8387e579aae81f.json` | S | `cd09951bdcfaffbf9d442749ff2987fc292cbf037e9f033c939082a92a89b52b` |
| `owner-whole-game-shader-cf3f9db0e1a2625a.json` | F | `e8ea662985bbefbf9b41a13a7ba208d8c0f80bacf4bfa3b2c7940054caf4d182` |
| `owner-whole-game-shader-cfd807c65f3d3888.json` | F | `be016feb77d43ec03e55eca956f88d7673683dfa96eaa1e5a4b890f6879bbf9b` |
| `owner-whole-game-shader-d2733c05837824d2.json` | F | `2821e63904943a0510b5f1f1603098476686730a665fa641d5d7298292d3e638` |
| `owner-whole-game-shader-d3950d734eb81efc.json` | S | `c90ff2c9c26b11eed1acc81e8a54dd35026b3864fbc8c97c6c2e6cb774e94020` |
| `owner-whole-game-shader-d77ffe1926f7e966.json` | S | `eae26f7fd04f2fa3844c82473bdb9f50f44c7ae191093c5081ddc747b80f480a` |
| `owner-whole-game-shader-d99b3943ed2ab6cf.json` | S | `9528b8d6e5146636fa6809a23843462010c190b13bc68b0b18b862fe9999523d` |
| `owner-whole-game-shader-da8e7363437ccb77.json` | S | `e7bdd609152432e9dbbbad337dc9e8bb741e417bf3189b7ffd2637c2ee4e3dee` |
| `owner-whole-game-shader-db075d25d0d1688a.json` | S | `73eae1f4914f3c9a6810cfb0a4d2d5eed25ea49428167c706fcf51868d2aa205` |
| `owner-whole-game-shader-dbe1e9b11eb1e5b9.json` | S | `bfa575f6d3eaaa525e3330a8fa8fb2a8f093b9e9a3e3631ef03c2e90ddb99638` |
| `owner-whole-game-shader-e31bc85cbb80f18a.json` | F | `d00c55cdb8fbd4f85b39035983e2a3ef9bb2f91ccb05ac118d39a847b2d3248a` |
| `owner-whole-game-shader-e45cf7013b5e74de.json` | S | `2ca60fbb87b20a811c96e36748978f1be3db0838675ebcde96805a5f1e96c18f` |
| `owner-whole-game-shader-e52d452d03e22b87.json` | S | `4e49934feaf1cd7cde6e256a3500dc73f178a2d95fbebb8520f557251d068924` |
| `owner-whole-game-shader-e77d203538848225.json` | S | `6ac65d0b90f4a1b5db06775f2e82c386ca2a2e4264caa3c111bc70d9b153df13` |
| `owner-whole-game-shader-ec030340227418cb.json` | S | `f0ad144b328da31ab57f54fa04fade5db9f294311ba3854c7d0e03e3996be51d` |
| `owner-whole-game-shader-ec366ea0ed0b7448.json` | F | `c64bf3bb9d0b14e55299b3ac809878e614ffecb2cc14510945d1b98955c22673` |
| `owner-whole-game-shader-f175a9cf5b433cd2.json` | S | `e54faed8fb2dbf0d907a1b171d9258964fc1ab9c5b5e878b93f9c2ea504a975f` |
| `owner-whole-game-shader-f978fab9f2141531.json` | S | `1715c187362b9525667ffa6fd3990da69c8e7da6c7acca442efa4be431102f89` |
| `owner-whole-game-shader-f97c130db51c09fc.json` | S | `8ab987a48bbeecb882f02731cbb7e039159fe261ab3a2996cbcddec36a4eac84` |
| `owner-whole-game-shader-f9aad7ffaaec4f02.json` | S | `7cbfaa43683177149a67cda64df5ff103cb336d4a08249d2a18c5bddd3ecf4b8` |
| `owner-whole-game-shader-f9d89be4f62e7908.json` | F | `a96411a5a7c4140b5ec0ddb4b22deda1916eb07c5a378e24b74dd6ce01b0e190` |
| `owner-whole-game-shader-fa41fb006744e15d.json` | S | `be3cdb08776e57f4ed5186ed8af6175e10140d1d2125d187e5eb1b605709f46d` |
| `owner-whole-game-shader-facfd5c8e5f9eae1.json` | S | `85c7ac4e2e8ea815c908ab3bd94e9c3f1ded8f463971976cecf10c75d82fa41b` |
| `owner-whole-game-shader-fff9ac02cfd7c247.json` | S | `ba02c7fa98df94ca68a2410d729ee6071065e64bb2a1553b1a014479deba4e92` |

Audit: original bundle/member/Shader selectors and hashes, permitted SDK and
public-template pins, authored compiler settings, logical source filenames and
minimum output/PPtr relationships. No original property payload, program, type
tree, generated output or private setting is included. Original properties and
SDK fallback declarations supply keyword tables and dependencies. Stable logical
filenames may derive from original identities, without historical export files.
All 117 persisted records match J850; complete bundle, phone production and
original rendering/gameplay acceptance remain open. Template licenses stay with
local producer output; no third-party implementation is copied into these recipes.

### Whole-game hierarchy path records (J1276)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-hierarchy-path-records.json` | `dd7494d9c69e9da37fc5c6ce7da58a343213f685840942d1e1044fc3ebc83d41` |
| `owner-whole-game-path-managed-records.json` | `829c9316236c8b791a1eec0c08a607f3ea538af5befe93532b81b610da6292fe` |
| `owner-whole-game-path-original-hash-records.json` | `2b20c132dfdba8209757581a3a18ac6961d7fbaf7f0158e094f5f0593fe856eb` |

Audit: minimum original bundle/member/object/MonoScript selectors and hashes,
checked PPtr relationships, native type hashes and existing SDK/original-script
hash policies. Original roots and unique reciprocal child-name paths establish
identity; only exact native state is admitted. No pose, scalar, type tree, source
implementation, private setting or generated body is included. The 1,237 native
and 108 managed records match J850 after persisted extent checks. The original
script hash applies only to unchanged runtime identity/schema. Complete bundle,
phone production, gameplay and installation/update acceptance remain open.

### Whole-game prefab policies (J1277)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-prefab-policy-records.json` | `b8ddb04666bca02764ab2ea5ca46427d6e288e4db78c7f2444908036ca400992` |

Audit: minimum original bundle/member/object selectors, source/output hashes,
checked PPtr relationships and existing filename/component-append policies.
Actual MonoScript identities and reciprocal owners retain the complete ordered
original component sequence; five roots additionally list an already-produced
public SilentProjectileBoundary. No component is omitted. No original body,
scalar, type tree, source implementation or private setting is included. All
17 persisted records and native type hashes match J850. Complete bundle, phone
production, gameplay and data-preserving installation/update remain open.

### Whole-game existing presentation policies (J1278)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-existing-presentation-records.json` | `c488c434588e1cefe832e467141f8cf4e224edd89a2fd30520f2a6194a78a6df` |

Audit: minimum original bundle/member/object selectors, source/output hashes,
checked PPtr relationships and component omission indices/identities. Existing
`sanitize_optional_content` policy selects optional audio, decal and particle-tail
components by original MonoScript assembly/importer identity. Retained components
keep their original order and reciprocal owners; ambiguous duplicates are excluded.
Existing filename and public adapter-append policies also apply. No new omission
policy, original body/scalar/type tree, implementation or private setting is
included. All 38 persisted records and native type hashes match J850. Complete
bundle, phone production, gameplay and installation/update remain open.

### Whole-game source registry records (J1279)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-registry-records.json` | `70e07b47f45255014324c4b166e1f52edaa0263b770ea6cf9f6f63bea31c5955` |

Audit: existing public registry-profile hash, generated file/object selectors,
output identities, body hashes and native type hashes. `script_registry.py`
exposes the existing original/SDK/authored registry owner as a standalone phase;
`record_remap.py` consumes its fresh successful receipt. No historical player
file, private schema, generated body, original implementation or private setting
is included or required publicly. All six persisted MonoScripts match J850.
Generated registry IDs supply record selection, never original-asset identity
witnesses. Complete bundle, phone production and runtime acceptance remain open.

### Whole-game current script fields (J1280)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-current-script-fields.json` | `f38fbaede09af8041eb9e9678a7db03f1b2f0781e3be9fbb84d9502541ca095c` |

Audit: original bundle/member/object/MonoScript selectors and hashes, SDK/native
type pins, original managed-assembly hashes and checked PPtr relationships.
The generic projection omits only whole source fields absent from current CLR
declarations, inherited fields and serialized-name aliases. SDK native fields
remain protected; retained bytes/alignment and script identity stay checked.
No original implementation, field value, type tree, target template or private
setting is included. Five persisted RunPresence records match J850; their stale
counters are absent from the current original assembly. Complete bundle, phone
production, gameplay and installation/update acceptance remain open.

### Whole-game component edge records (J1281)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-component-edge-records.json` | `84413591dc94cd91944ccbbc526ae986f650ebaa3b452c10ed3021675e85d7d1` |

Audit: minimum original bundle/member/object selectors and hashes, output IDs,
checked PPtr relationships and native type hashes. Already-qualified original
GameObject recipes supply explicit component-pointer mappings after checked
omissions; append/reordering cases are excluded. Actual script names, native
identity and reciprocal ownership agree. No field value, original body/type
tree, implementation, private setting or generated prototype is published.
All 16 persisted records match J850. Complete bundle, phone production, gameplay
and data-preserving installation/update remain open.

### Whole-game remaining native Sprite imports (J1285)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-native-sprites-2.json` | `113d582c6e2cf7f70fa66be6a2a58e7bc8b9ab0e9377b3265005f6d44674342c` |

Audit: 65 minimum original Sprite/Texture2D selectors and hashes, importer GUIDs,
output identities and checked pointer relationships. Current export metadata
independently witnesses every importer GUID; 61 target texture edges select the
same original texture, and four aliases have identical compressed mip bytes,
dimensions and format. Production always decodes each Sprite's own original
texture. Pinned AssetRipper `1ac666f` SpriteProcessor/TextureExportCollection
normalization and EditorKit typed lookup guidance remain the prior art used by
the existing producer; target pixels or geometry never supply production input.
No pixels, contours, geometry, native output, original implementation or private
configuration is published. Exact-SDK host constructor output and every persisted
record extent match J850. Complete bundle and phone/install/update gates stay open.

### Whole-game selected controller relationships (J1286)

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `28724ccbb02362eb2f5814bc8d3718a3171e5ed6976fdbfe0eb16317a4fe1411` |

Audit: 2026-10-31. This extends the J1143 source-relationship policy with 24
whole-game controllers. Profiles select original objects, clip/state ordinals,
checked PPtr relationships and source TOS entries; the existing owner enforces
bijections and regenerates strings from the original source. Selected FullPathID
relationships qualify these records; they do not establish a generic state-order
inference algorithm. Pinned AssetRipper controller behaviour ranges, hierarchy
mask omissions and BlendTree leaf/child indices remain the prior art. No target
scalar, string, body, type template, original implementation or private setting
is included. All 358 persisted controller records match J850, including the
24 additions; existing 334 outputs are unchanged. Generated bodies remain local.
Complete bundle, phone production and install/update acceptance stay open.

### Whole-game duplicate behaviour relationships (J1287)

`owner-animator-controllers.json` SHA-256: `23a81b8615260e23de8d9ab985535bd8a96428e3e9a431e4dafc7aa992a2edac`.
Audit: 2026-10-31. The J1143/J1286 selection policy now includes Totem,
Bandit and LynxAmbusher. Original layer/state keys and range ordinals identify
otherwise identical behaviour bodies; script/body equality and original
PPtr edges are checked. Pinned AssetRipper `GetStateBehaviours` documents the
range-to-index relationship. The recipe adds source identities, ordinals,
operations and checked pointer remaps; no target scalar, string, native body,
type template, implementation or private setting. Three new persisted records
(40,044 bytes) are raw-exact J850; earlier selections are unchanged. Generated
bodies remain ignored. Complete bundle, phone and install/update gates stay open.

### Whole-game ordered behaviour ranges (J1288)

Audit: 2026-10-31. The existing source-relationship policy adds MimicLogbook and
four original state behaviours (two ClearLayerWeight, two SetRandomIntOnEnter).
Original layer/state keys, range membership and ordinal resolve their identities;
script identities, SDK-derived properties hashes, source schemas and full bodies
are checked. Pinned AssetRipper `GetStateBehaviours` traverses every range member.
Only original selectors/hashes, index permutations and checked pointer remaps
are published; no target scalar, string, body, type template or implementation.
New-only persisted production reproduces five records (16,252 bytes) raw-exact
J850. Previous outputs are unchanged; complete bundle and phone gates stay open.

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `df6381c71730c913a105808e25656b827f50c25af43fab2d2b3436ed1a6edd2f` |
| `owner-whole-game-path-managed-records.json` | `fe49a139288fb404846159f821cc149b71dab1beb5f1bfb8b35810a682ab7118` |

### Whole-game authored prefab activation (J1289)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-activation-records.json` | `720bb9f36bed638f194afb1a20d62f4d8691795e91568abf43f4ca440b423c6f` |

Audit: 2026-10-31. Existing `asset-transforms.json` policies deactivate the
original ItemIcon, HUDSimple and ClassicRunInfoHudPanel roots. Generic record
production delegates the same named-active-source check to the object owner.
Ordered component PPtrs, reciprocal ownership and 16 independently qualified
public component edges establish source identity. Three other native slots
(CanvasRenderer, Canvas, Rigidbody) have equal schemas, normalized bodies,
pointer fields and ordinals; those component records are not claimed produced.
Pinned AssetRipper GameObjectExtensions separates activation from ordered
component PPtrs. The profile contains only original selectors/hashes, authored
activation policy and checked pointer remaps, with no target body, type template,
implementation or private data. Three persisted records (317 bytes) match J850
raw-exact. Complete-file, phone production and install/update gates remain open.

### LightningStake late source witness (2026-10-31)

The default-off source observer continues checking scalar finiteness after its
eight-row cap, preserving the first later invalid call in the final row unless
an earlier invalid call is already retained. Its source hash and the shared
audio/camera owner-cohort pins are refreshed together. Review: authored observer
and metadata only; no game-derived content, private paths or identifiers. This
is diagnostic capture, with no projectile mutation or device-acceptance claim.

### Whole-game native HUD component slots (J1290)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-native-component-records.json` | `581a2f05b14d6ae18365386646a1e8b541cc33f2c0c26c7278f6e6913733d78f` |

Audit: 2026-10-31. Original HUDSimple Canvas/Rigidbody and ItemIcon
CanvasRenderer slots are identified by ordered component PPtrs, reciprocal
qualified GameObject ownership, equal complete schemas and equal normalized
bodies. Pinned AssetRipper GameObjectExtensions exposes ordered component
traversal; existing J1273 native record production relocates only the checked
GameObject pointer. No producer change or target scalar/body/template is added.
The profile contains original selectors/hashes, native type identities and
checked pointer remaps; generated bodies remain ignored. Three persisted records
(108 bytes) are raw-exact J850. Complete-file, phone and install/update gates
remain open.

### Whole-game Timeline relationships (J1291)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-timeline-records.json` | `30557118e6555f13c9ba3b50510e2cd0b986c4d7fe422fcb580906a8043e513e` |

Audit: 2026-10-31. Minimum original object selectors/hashes, output identities,
checked PPtr relationships and one named import operation select 20 unique
incoming tracks and their 23 ControlPlayableAsset children. An authored fixture
in the exact editor independently proves managed PropertyName mapping import
uses the default value. Original managed metadata establishes default integer
zero; pinned AssetRipper `813fed1597bac674def7256ce633a227e7b27497`
`YamlWalker`/`PropertyNameExtensions` establishes native decimal encoding.
No target scalar template, native body, type tree, game implementation or private
setting is published. All 43 persisted records match J850 raw-exact. Complete
bundle, phone production, gameplay and install/update acceptance remain open.

### Whole-game original prefab sources (J1292)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-prefab-source-records.json` | `fbc447822e5509b12a4ea6ca3c4f10d5a92b532609b44052d19bc627b5374cdb` |

Audit: 2026-10-31. Ordered equal component fingerprints, reciprocal ownership
and parent hierarchy select ten original SpeedTree GameObjects. Eight original
ItemInfection prefab roots use the existing exported-filename projection; native
components match, and managed components retain script identity, normalized body
and pointer schema despite imported native hash differences. BrotherSwing uses
the existing J288 detacher-removal policy after checking both original
DetachParticleOnDestroyAndEndEmission script identities and retained component
order. Pinned AssetRipper GameObjectExtensions establishes ordered component and
root-parent traversal. Existing generic record production supplies every body;
only original selectors/hashes, named policies, type identities and checked PPtr
remaps are published. No target body, scalar template or implementation is added.
All 19 persisted records (1,493 bytes) match J850 raw-exact; complete-file, phone
production and install/update gates remain open.

2026-10-31 authored owner pin refresh: `original-audio-owner-sources.json`
updates only the public `PortSession.cs` hash for the default-off settings
write observer startup request. Provenance, privacy, licensing and sensitive-content
audit: authored source hash only; no game content, private inputs or identifiers.

2026-10-31 camera build-hook pin refresh: `native-view-camera-transform.json`
tracks the authored hook hash after its owner-manifest pin update. Provenance,
privacy, licensing and sensitive-content audit: public authored hash only; no
game content, private inputs or identifiers. Runtime camera outputs are unchanged.

### Whole-game empty renderer membership (J1294)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-empty-renderer-records.json` | `6ea471b31c1f52acccf13a5679c7ce4dfa3ff5b450170aa831a7e5c4b9e5c07b` |
| `owner-whole-game-renderer-membership-records.json` | `f3114997dbf56ebb1a63730b62fccb2501ddaf3375752821da5e29a5c700367c` |

Audit: 2026-10-31. Existing J245 original AnimateShaderAlpha repair applies
when an original GameObject lacks a renderer and its decal reference is absent
or removed by the existing decal omission policy. Ordered original component
lists and reciprocal ownership establish all fourteen cases. The existing empty
MeshRenderer constructor preserves the original donor's native fields and type
identity while applying its three disabled flags. Generic record production
delegates that constructor, relocates checked owner PPtrs and uses existing
component append for GameObject membership. Pinned AssetRipper
GameObjectExtensions supplies ordered component traversal knowledge. Profiles
contain only original selectors/hashes, native identities, named operations and
checked relationships; no native body, scalar template, game implementation or
private input is published. All 28 persisted records (3,090 bytes) match J850
raw-exact. Complete-file, phone production and install/update gates remain open.

### Whole-game catalog-witnessed materials (J1293)

`owner-whole-game-material-compute-records.json` SHA-256:
`2a8face247ee9a9b5480de17751bd075e89541393eafaae83bc4ad3f741cb9f7`.

Audit: two original material selectors extend the existing record owner. Original
catalog-root relationships independently identify the Enforcer and LunarGolem
materials; original native schemas, pointer slots and all non-pointer fields match
under the existing named keyword import policies. The recipe retains source pins,
checked pointer mappings and output hashes only. No field payload, keyword string,
type tree, shader program, private path or generated game content is included.
J367/J371 and pinned EditorKit `HopooCloudRemapGUI` inform preservation of original
property/blend fields rather than exporter defaults; no upstream code is copied.
Both persisted records (2,856 bytes) match J850 raw-exact; 11 other witnessed
materials still differ after existing policies and are excluded. Complete bundle,
phone production, gameplay and install/update acceptance remain open.

### Whole-game original MeshFilter ownership (J1296)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-meshfilter-records.json` | `4518372445d82bbdfaabfe197fed2fed9f54155c22e0fe7cdbc0dd78d16871f9` |

Audit: 2026-10-31. Existing public GameObject source selections and the unique
original MeshFilter class slot identify fourteen records. Reciprocal component
ownership and both original pointer endpoints are checked against existing public
suppliers, resolving external mesh members explicitly. Pinned EditorKit
AddressablesPathDictionaryCache supplies GameObject/type component lookup
knowledge. The existing generic record owner preserves schemas and all nonpointer
bytes and relocates checked GameObject/mesh identities. This profile contains only
original selectors, input/output hashes, native type identities and pointer
relationships; no object bodies, scalar templates, game implementation or private
paths are published. All fourteen persisted records (336 bytes) match J850
raw-exact. Complete-file, phone production and install/update gates remain open.

### Whole-game reciprocal managed ownership (J1295)

`owner-whole-game-path-managed-records.json` SHA-256:
`a96162e8d171e9ad73fdfdd90878a9ad448cdadb4e424072dc3614121f4ddb50`.

Audit: ten original managed component selections extend the existing record owner:
eight ItemDisplay and two EffectManagerHelper records. Qualified original
GameObject component order and reciprocal owner links identify each component;
full assembly/namespace/class identity and source MonoScript hashes independently
check its type. The existing SDK properties-hash policy retains schema identity.
Pinned ThunderKit FileIdUtil and AssetRipper MonoScriptExtensions inform these
identity checks; no upstream implementation is copied. The additions contain
only source selectors/hashes, native identities, checked pointer mappings and
output hashes. No scalar template, original body, game implementation, private
path or generated content is included. All ten persisted records (880 bytes)
match J850 raw-exact. Complete bundle, phone and install/update gates remain open.

### Whole-game original MeshRenderer ownership (J1298)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-renderer-records.json` | `65810a7caa3fba3a55557c0044cf5bccbbf66a0082d0bed02a0dd96b4224d208` |

Audit: 2026-10-31. Existing public GameObject source selections and each unique
original MeshRenderer class slot identify twelve records. Reciprocal component
ownership and every original pointer endpoint, including unchanged and null
references, are checked against existing public suppliers. Two records with
unresolved material suppliers are excluded. Pinned EditorKit
AddressablesPathDictionaryCache informs GameObject/type component lookup.
The existing generic record owner preserves schemas and nonpointer bytes while
relocating checked references. This profile contains only source selectors,
input/output hashes, native type identities and pointer relationships; no object
bodies, scalar templates, game implementation or private paths are published.
All twelve persisted records (1,944 bytes) match J850 raw-exact. Complete-file,
phone production and install/update gates remain open.
| `owner-whole-game-shader-particle.json` | Original particle material and Shader pins, SDK declaration identity, dependency pointers and output hash; `shader_prefab.py`; J1297. |

### Whole-game original-material particle Shader (J1297)

`owner-whole-game-shader-particle.json` SHA-256:
`cb4108d7c0c3484f208d2f8b48057cf93786674f96a7cee9120512abf66c9a83`.

Audit: existing `shader_prefab.py` compiles acquired SDK 211 declarations using
original particle fragment order and an original UI material whose checked
external Shader pointer identifies the selected original shader. The existing
particle owner retains runtime feature alternatives and excludes scene fog;
no accepted keyword/pass/program table is an input. Pinned AssetRipper
`DummyShaderTextExporter` at `1ac666f47d8e9dedf96afb0b914c70d7656151ea`
continues to inform property/fallback contracts; it supplies no particle code.
The profile contains only input pins, source identities, dependency pointers and
output hashes. No source body, private path or generated content is published.
The persisted 25,056-byte record is independently raw-exact to J850. Complete
bundle, phone, gameplay and install/update gates remain open.

### Whole-game original Tree and WindAsset ownership (J1300)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-tree-records.json` | `751feacef112c6688858ab239c0206f57fa4759d72b489b6e6f741f25d578da0` |

Audit: 2026-10-31. Published original prefab GameObjects, unique Tree class
slots and reciprocal component ownership identify eight Trees. Their original
non-owner pointers identify two SpeedTreeWindAssets. Every pointer endpoint,
including null and unchanged references, resolves to a checked public supplier.
Pinned EditorKit AddressablesPathDictionaryCache informs component lookup through
GameObjects. The existing generic record owner preserves native schemas and all
nonpointer bytes; class 228 admission adds WindAssets to that owner. This profile
contains only original selectors, hashes, native type identities and pointer
relationships. No object bodies, scalar templates, game implementation or private
paths are published. All ten persisted records (2,952 bytes) match J850 raw-exact.
Complete-file, phone production and install/update gates remain open.

| `owner-whole-game-shader-calmwater.json` | Original CalmWater Shader pins, checked local fallback edge, public template identity and output hashes; `shader_prefab.py`; J1299. |

### Whole-game original CalmWater fallback graphs (J1299)

`owner-whole-game-shader-calmwater.json` SHA-256:
`2f272216acd8c3979f866937400ca0ee6b685aba9ae370a9a532af55530a61c1`.

Audit: existing `shader_prefab.py` combines original parsed properties with the
pinned public SingleColor exporter template and acquired SDK compiler. Original
local dependencies independently witness the DX11 fallback edge; DoubleSided
retains its original unresolved fallback literal without a dependency. Pinned
AssetRipper `DummyShaderTextExporter` at
`1ac666f47d8e9dedf96afb0b914c70d7656151ea` emits fallback literals independently
of resolution, informing this preservation policy. No original implementation,
accepted keyword table or shader program is a producer input. The recipe contains
only original/SDK/template pins, source identities, one pointer mapping and output
hashes; no protected body, private path or generated bytes are published. Both
persisted records (12,928 bytes) independently match J850 raw-exact. Complete
bundle, phone production, gameplay and install/update gates remain open.


| `owner-whole-game-transform-owner-records.json` | Original Transform selectors, checked component/owner relationships, native schemas and output hashes; `record_produce.py`; J1301. |

### Whole-game original Transform ownership (J1301)

`owner-whole-game-transform-owner-records.json` SHA-256:
`e02b80ee9fa096e2d497187ae5f1b9bc5ae0ff988747579f13265d9831a1e44e`.

Audit: qualified public GameObject recipes independently identify the original
Transform through its ordered component slot and reciprocal GameObject pointer.
Ten common-props and eight Brother records retain their original native type
hash, pointer shape and every nonpointer byte, including float bits. Only checked
references relocate through the unchanged generic record owner. J426's pinned
UnityPy `PPtr.deref` and `ObjectReader.peek_name` inform original member/path-ID
ownership; names alone do not select these records. Source parent/child edges
remain intact. The eight unresolved SolusWing records are excluded because their
original scale bits differ; no target scalar template or rounding policy is added.
The recipe contains only original selectors, hashes and relationship mappings;
no protected bodies, implementation, private paths or generated content. All
eighteen persisted records (1,320 bytes) match J850 raw-exact. Complete-bundle,
phone production and install/update acceptance remain open.


### Whole-game original Billboard ownership (J1302)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-billboard-records.json` | `fabfa2f7e4692c71063f3c723b6f585681ef291dd603b34f0bb5798446c4c79e` |

Audit: 2026-10-31. Qualified original GameObjects, unique BillboardRenderer
component slots and reciprocal ownership identify two renderers. Their original
Billboard pointers identify two BillboardAssets; original material endpoints
resolve to existing public suppliers. Pinned AssetRipper PPtrExtensions at
`813fed1597bac674def7256ce633a227e7b27497` informs local/dependency pointer
resolution. The existing generic owner admits native classes 226/227, preserving
native schemas and every nonpointer byte. This profile contains only original
selectors, hashes, native identities and checked pointer relationships. No object
body, scalar template, game implementation, private path or generated content is
published. All four persisted records (808 bytes) match J850 raw-exact. Three
remove saved census residuals; the fourth's overlap is unproven. Complete-file,
phone production and install/update gates remain open.


### Whole-game original LODGroup ownership (J1304)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-lodgroup-records.json` | `4b1fb0450355c9ce57b70bf223a2d73a0820703f8b081ebfb1d0bd9ea62b4e59` |

Audit: 2026-10-31. A unique original LODGroup component slot and reciprocal
qualified GameObject ownership select the source. Every original LOD renderer
endpoint resolves to an existing public supplier, including J1302's Billboard.
Pinned AssetRipper PPtrExtensions at `813fed1597bac674def7256ce633a227e7b27497`
informs local/dependency pointer resolution. The unchanged generic record owner
preserves native class 205, schema and every nonpointer byte, relocating only
checked references. The profile contains original selectors, hashes, native
identity and relationship mappings; no protected bodies, scalar templates,
implementation, private paths or generated content. The persisted record is
raw-exact to J850 (140 bytes). A second candidate remains excluded for missing
public renderer suppliers. Complete-file, phone production and install/update
acceptance remain open.


### Whole-game original PlayableDirector ownership (J1305)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-director-records.json` | `a76af2367dc096d0bf862455af699c4f817f6ec40bc9d848a0d5a7a03bec036f` |

Audit: 2026-10-31. Unique original Director component slots and reciprocal
qualified GameObject ownership select ConduitCanyon and SolusAmalgam sources.
All original pointer endpoints resolve through shipped selectors, including
compressed hierarchy suppliers and checked typed reference endpoints. Pinned
AssetRipper PropertyNameExtensions.GetIdString and YamlWalker explain signed
integer exposed-name export; the existing record owner reimports those names
and relocates checked references while preserving the native schema and fields.
The profile contains selectors, hashes, native identity and relationship mappings;
no protected bodies, target scalar templates, implementation or private paths.
All three persisted records (1,380 bytes) match J850 raw-exact (J1305/J1309).
Champrush endpoints follow 80 original Transform pairs rooted at a published
GameObject selection and seven connected Director suppliers, including the
reciprocal Animator component slot. Only identities and checked relationships
are published; original hierarchy/animation data stays local.
Complete-file, phone and install/update gates remain open.

### Whole-game Meridian material relationships (J1303)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-meridian-material-records.json` | `d6438f2ab2ddb8170bda115fba368259f2e9f0801fe0cbd83dcdaa9fcd8a307a` |

Audit: 2026-10-31. Four original Meridian Materials retain their complete
source bodies and keyword state; the existing `record_produce.py` owner changes
only schema-checked Shader/texture references. Original material identities and
public texture selections witness the endpoints; the shared original Shader
identity is retained as a dependency, without claiming its production is closed.
The profile contains only legitimate input selectors, hashes, pointer mappings
and output identities. No source body, generated program, private path or
protected implementation is published. Pinned community source/identity techniques
in `docs/community-prior-art.md` inform relationship inspection; current input
and persisted J850 byte comparison remain authoritative.

All four persisted records are raw-exact (1,184 bytes); one belongs to the saved
unresolved census, reducing 104 to 103. Other overlapping outputs are not counted
as new closures. Complete bundle, phone production and runtime gates stay open.

### Whole-game Standard fallback keyword registration (J1306)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-shader-standard-fallback.json` | `1b2b7eaad21fc49eb1eea48ed17484ad0709604a8247c4f16ed5d41bd8147668` |

Audit: 2026-10-31. The existing prefab Shader owner derives two original
Shader records from pinned legitimate input, public exporter templates and
acquired SDK fallback 46. Keyword registration traverses each snippet's stages,
then global/local declarations and builtin names, preserving first registration
and existing flags. No accepted keyword table is supplied to production.
Pinned AssetRipper `1ac666f47d8e9dedf96afb0b914c70d7656151ea`,
`DummyShaderTextExporter.cs:49-78`, informs property/template/fallback handling;
current SDK metadata and independently persisted J850 equality qualify ordering.
The profile contains only original selectors, hashes, authored filenames,
public template identities, SDK relationships and output pins. No protected
source body, program, generated data, private path or credential is published.
Both persisted records are raw-exact (12,004 bytes); complete-file, phone
production and runtime acceptance remain open.

### Whole-game inserted-component sequence ownership (J1308)

`owner-whole-game-path-managed-records.json` SHA-256:
`f60ed7b00484c57041745ef89a292dbfd0b84cfc3a9cff59b77466c8b489a4e8`.

Audit: 2026-10-31. Five original managed component selectors extend the existing
record owner: four ProjectileNetworkTransform records and one TeamFilter.
Already-qualified GameObject recipes declare source omissions and the appended
SilentProjectileBoundary identity. Filtering that insertion leaves the complete
original class and assembly/namespace/class sequence unchanged; ordered occurrence
and reciprocal GameObject owners uniquely identify duplicate components.
Pinned ThunderKit FileIdUtil and AssetRipper MonoScriptExtensions inform full
script identity, as in J1281/J1295. Native schema and all nonpointer bytes remain
original; only GameObject/MonoScript pointers relocate. The recipe contains input
selectors, hashes, native identities and checked relationship mappings, without
protected bodies, scalar templates, implementation, private paths or generated
content. All five persisted records match J850 raw-exact (360 bytes). Complete
bundle, phone production and install/update acceptance remain open.

### Whole-game original TerrainData Shader closure (J1310)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-terrain-shaders.json` | `f9611252293e4750fab696f851005b5ea5b907323de7fdad4ef7068c3d89b7bf` |

Audit: 2026-10-31. The shipped original Title TerrainData selection supplies
eleven explicit preload Shader relationships. Its checked external bundle
contains the actual original Shader records; names, properties and native schema
select acquired SDK Shader equivalents through the unchanged `shader_prefab.py`
owner. SDK native terrain preload collection corroborates inclusion but is not
a recipe input. Pinned AssetRipper `1ac666f47d8e9dedf96afb0b914c70d7656151ea`,
`DummyShaderTextExporter.cs:49-78`, informs source name/property preservation;
current original pointers and persisted J850 comparison remain authoritative.
The profile contains only source selectors, SDK identities/settings and hash pins;
no protected body, shader program, generated content or private path is published.
All eleven persisted records are raw-exact, 79,656 bytes; exact public coverage
reduces the saved residual from 93 to 82. Complete bundle, phone
production, installation and original runtime remain open.

### Whole-game empty TerrainData detail Shaders (J1312)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-terrain-detail-shaders.json` | `90928b2df1554a0e43c0ae93543a71b8be37e1da05baab917aa3108282f4b0ee` |

Audit: 2026-10-31. Original Title TerrainData's three indexed default Shader
pointers identify the original detail Shaders. Its empty detail prototype array
supplies the usage witness for the existing fresh-mono instancing stripping
policy; the acquired SDK DetailRenderer constructor corroborates that no
prototype instancing caches are created. Original Shader records retain their
instancing declarations and supply names, properties, native schema and fallback
identity. The existing `shader_prefab.py` owner checks the pinned TerrainData,
external member and default Shader identity before selecting variants.
Pinned AssetRipper `1ac666f47d8e9dedf96afb0b914c70d7656151ea`,
`DummyShaderTextExporter.cs:49-78`, informs property/fallback preservation.
Only input selectors, relationships, SDK settings and hashes are published;
no protected source/program body, generated content or private path is included.
All three persisted records are independently raw-exact to J850, 131,996 bytes;
public saved residual reduces from 82 to 79. Complete bundle, phone production,
installation and runtime gates remain open.

### Whole-game controller-owned managed record (J1314)

`owner-whole-game-path-managed-records.json` SHA-256:
`37c587c9c70e6027a7f876e455a7a4324e8da8d93fec3fcb2374c81837cffad1`.

Audit: 2026-10-31. The qualified original VoidRaidCrab AnimatorController's
indexed state-machine behaviour array identifies one original managed record.
The existing controller behaviour order supplies the output identity; original
native type/script schema and every nonpointer byte agree independently. Only
the MonoScript pointer relocates through the unchanged record producer.
Pinned ThunderKit FileIdUtil and AssetRipper MonoScriptExtensions full
assembly/namespace/class identity inform script checks, as in J1281/J1295.
Only source selectors, relationship mappings and hash pins are published; no
protected body, implementation, generated content or private path is included.
The persisted record is raw-exact to J850, 60 bytes. Saved public residual
79 to 78 excludes parallel controller closures; complete bundle, phone
production, installation/update and runtime acceptance remain open.

### Whole-game duplicate clip-name controllers (J1313)

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `c417169cfdd6dcc7255c475d94cbcbc23bfbbfaac333f8796962730a0b567abe` |

Audit: 2026-10-31. Existing J1143/J1286-J1288 relationship policies add
DroneTech, FalseSonNew and Drifter. Original clip identities, selected export-name
collision ordinals, state permutations and checked PPtr edges feed the unchanged
controller producer. Original layer/state keys, range indices and ordinal resolve
identical behaviour bodies; script/body equality remains checked. Pinned
AssetRipper ExportCollection.GetUniqueFileName and GetStateBehaviours document
the collision and range relationships. This is a selected reconstruction, not a
generic historical export-order inference. Only source selectors/hashes, ordinal
policies and checked pointer remaps ship; no target strings, scalar values, body,
type template, implementation or private settings. Three new persisted records
(107,980 bytes) match J850 raw-exact. Earlier outputs are unchanged; complete
bundle, phone production and install/update gates remain open.

### Whole-game controller state-range managed records (J1316)

`owner-whole-game-path-managed-records.json` SHA-256:
`46138646bcc4c0c6974638fdcf8b16a2fd47f9de0ae2a28d363aaf7a737b8dde`.

Audit: 2026-10-31. Twelve original managed records are selected by original
AnimatorController identity, matching layer/state dictionary keys, range count
and behaviour ordinal through the indexed behaviour array. Railgunner, FalseSon,
and Chef source controllers supply these relationships independently
of whether their complete controller records can already be reconstructed.
Original native/script schemas and all nonpointer bytes agree; the unchanged
record producer relocates only checked MonoScript pointers. Pinned AssetRipper
`1ac666f47d8e9dedf96afb0b914c70d7656151ea`,
`AnimatorControllerExtensions.cs:44-71`, documents the range/index indirection.
Only source selectors, relationship mappings and hashes are published; no
protected body, implementation, generated content or private path is included.
All twelve persisted records are raw-exact to J850, 716 bytes. Saved public
residual 75 to 63 includes the merged controller closures. Complete bundle,
phone production, installation/update and runtime gates remain open.


### Whole-game native component and Material suppliers (J1319)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-native-material-supplier-records.json` | `d7e1b7f4ec940109e3228445e42318154a368f8862710827c4131e7257d80d6e` |

Audit: 2026-10-31. Original GameObject component lists, reciprocal ownership and
unique native class slots select two Renderers and one LODGroup. Ordered
Renderer Material slots identify four Materials; every relocated pointer has an
original supplier witness. The shared Shader mapping comes from the public
Commando fallback recipe. The unchanged record producer preserves native schemas
and nonpointer bytes, using the existing dummy-Shader keyword demotion policy.
Pinned RoR2EditorKit AddressablesPathDictionaryCache.cs:203-214 and AssetRipper
GameObjectExtensions FetchComponents/GetComponentAccessList inform identity;
the pinned TransparentDiffuse template has no keyword variants. Only original
selectors, identity relationships, checked pointer remaps and hash pins ship;
no body, keyword string, material value, protected program or private path.
Seven persisted records are raw-exact to J850, 2,768 bytes. Complete bundle,
phone production, installation/update and runtime acceptance remain open.
### Whole-game shrine component relationships (J1318)

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-hierarchy-path-records.json` | `633ffe0b124232321bb76ee8a46f209c97481888fea4388dc9a014ce195125e7` |
| `owner-whole-game-path-managed-records.json` | `2a32cff26498ddef58c73f87f57daaa58e1e4c406ccb7948ac36d76977793d95` |

Audit: 2026-10-31. Original typed ShrineCombatPoison prefab path identifies
its GameObject. Its complete sixteen-component native/script sequence and
reciprocal owners identify both CombatDirector slots without name matching.
Existing source record production retains native schemas and nonpointer bytes
and relocates checked component, script and object references. Pinned R2API
DirectorAPIinternal.cs:22-28,75-78 describes per-instance Director state;
it supplies no shortcut for serialized duplicate identity. Original typed paths
and full sequences retain the J1276/J1281/J1308 policies. Only original selectors,
relationship mappings and hashes ship; no protected body, implementation,
generated content or private path is included. All three persisted records
are independently raw-exact to J850, 699 bytes. Saved public residual 63 to 60
excludes parallel closures; complete bundle and phone/runtime gates remain open.

### Whole-game build-missing script component

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-missing-script-records.json` | `36732035bfe1a3fecf454e024a740850e4c92faba98f295bbddf073a898ae571` |

Audit: 2026-10-31. The original Rewired GameObject's existing public selector,
component slot two and reciprocal owner select NintendoSwitchInputManager.
The existing J1225 `missing_script_base` policy retains its first 32 base bytes,
uses the pinned original Black Beach base MonoBehaviour type and relocates the
checked owner and absent-script pointers. The complete donor type agrees with
the accepted type. Pinned RoR2ImportExtensions `AssemblyBlacklist.Process`
illustrates platform/import-dependent assembly provision; it supplies no Android
script replacement. Existing Rewired runtime results remain untouched.
Only source selectors, hashes, extent and checked relationships ship; no body,
type template, decompiled implementation or private settings are published.
The persisted 32-byte record is raw-exact to J850. Saved residual 60 to 59
excludes parallel closures; complete bundle and phone/runtime gates remain open.

### Whole-game fallback Material keywords

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-fallback-material-records.json` | `715a6477f46159d5d85f8f4726713b6d14583d2b2c329ae39443936eccfd78c8` |

Audit: 2026-10-31. Existing catalog identities select eleven original Materials
whose Texture Scrolling Wireframe Shader uses the published Standard fallback.
The existing SDK Shader reader and keyword registry derive its declaration space
from pinned SDK object 46; original strings partition into valid/invalid arrays,
with invalid names sorted by the existing ordinal policy. All scalar/property
bytes remain original. Pinned AssetRipper 1ac666f DummyShaderTextExporter retains
fallback names; EditorKit metadata informs property boundaries, not scalar fitting.
The Gauntlet skybox Material uses its original catalog identity (comma-normalized
export path) and existing dummy sorting. Published Commando Shader and RGBA texture
recipes independently witness all five endpoints. Only selectors, hashes, named
policies and checked pointer relationships ship; no body, generated content or
private paths are included. Twelve persisted records are raw-exact to J850,
39,788 bytes. Saved public residual 57 to 45; final-file readiness remains
693/705 available, 685 raw-exact. Complete bundle and phone/runtime gates stay open.


### Whole-game synced motion and Mimic controllers

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `ff69865d77a5987188f2f230c57c597ed9fcd7b865313ef9c0bc4caca4d4a610` |

Audit: 2026-10-31. Original VoidSurvivor and Chef controller identities select
synced layers whose pinned AssetRipper 813fed15 processor omits motion overrides.
StateConstantExtensions.GetBlendTree selects the first source tree; the producer
retains that tree, remaps surviving clip occurrences and omits later overrides.
Only the observed empty single-leaf shape is admitted: 68 serialized bytes,
nine arrays, one node and no populated nested blend data. Source-only matching
across 479 controller pairs establishes a 152-byte blob-size marginal per tree;
this is empirical source evidence, not native deserializer heap allocation.
Mimic reuses existing collision-ordinal and source relationship policies.
Only source selectors, policies, pointer relationships and hashes ship; no
controller body, decompiled implementation or generated content is included.
Three persisted records are raw-exact to J850, 28,684 bytes. Saved residual
45 to 42; readiness stays 693/705 available, 685 raw-exact. Complete bundle,
phone production, installation/update and runtime gates remain open.

### Whole-game Scope Shader texture dimension

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-scope-shader.json` | `6f3c838d45980ceb52454834035df7b40000735a5193906b9844e78abe7f8948` |

Audit: 2026-10-31. The original Shader body/hash and existing authored export
path select the Scope record. Pinned AssetRipper 1ac666f
`DummyShaderTextExporter.cs` texture switch (lines 163–168) emits `any` for
native texture dimension one. The existing property owner now retains that
texture type/dimension instead of rejecting the declaration. Original property
metadata independently agrees; no integer-property change is included. The pinned
TransparentDiffuse template and existing producer supply the Android record.
Only original selectors, hashes, authored paths and public template pins ship;
no original property strings, shader programs, generated bytes or private paths.
The persisted record is independently raw-exact to J850, 4,940 bytes. Saved
public residual 45 to 44 excludes pending peer closures; readiness remains
693/705 available, 685 raw-exact. Complete bundle and phone/runtime gates stay open.

### Whole-game PowerOrb synced motion controller

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `ff672f2499ca6604fd3524f47adf8c8385c110c2c76f6ef2a5577a4f81dcf64d` |

Audit: 2026-10-31. Original PowerOrb controller identity selects the shared
state machine and synced layers. Pinned AssetRipper 813fed15
VirtualAnimationFactory.cs:215-223 and StateConstantExtensions.cs:18-20 select
the first source tree; AnimatorControllerProcessor.cs:93-139 leaves synced
overrides empty. The existing controller owner retains source clip occurrences,
clears skeleton masks and applies J1322's source-evidenced 152-byte marginal.
Only selectors, hashes, named policies and checked pointer relationships ship;
no controller body, generated content or private path is included. One persisted
record is independently raw-exact to J850, 1,256 bytes. Final-file readiness
stays 693/705 available, 685 raw-exact; complete bundle, phone production,
installation/update and runtime gates remain open.


### Whole-game Legacy Transparent Shader material selection

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-legacy-transparent-shader.json` | `c3889bebdd48bbbb8f26ee966f484e2e8b87c6920ab7cbad8e030310fd3f9e9d` |

Audit: 2026-10-31. A complete current-input census of 970 bundles and 9,080
Materials identifies six native-pointer users of Legacy Transparent/Diffuse.
All six original Materials disable instancing. Their pinned bodies and checked
Shader relationships select the existing SDK no-scene variant policy without
instancing; the particle-specific feature policy remains intact. Prior art:
EditorKit SerializableShaderWrapper preserves Shader name/GUID identity; pinned
AssetRipper 1ac666f exporter templates supply original declaration metadata.
Only source selectors, hashes, settings, relationships and SDK/template pins ship;
no original bodies, programs, keyword strings or generated content are included.
One persisted record is independently raw-exact to J850, 14,416 bytes. Combined
saved public residual 41 to 40; readiness stays 693/705 available, 685 raw-exact.
Complete bundle, phone production, installation/update and runtime remain open.

### Whole-game VoidWard synced motion controller

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `9254e6205034e97264824935588371a776032270b13eedd843bc2fb105d3dbef` |

Audit: 2026-10-31. Original animVoidWardCrab identity selects its source states,
first-tree motions and clip occurrences through the existing J1322 controller
owner. Pinned AssetRipper 813fed15 StateConstantExtensions.cs:18-20 selects
tree zero; AnimatorControllerProcessor.cs:108-138 recreates synced links without
motion overrides. The existing source-evidenced 152-byte marginal applies.
Only selectors, hashes, named policies and checked pointer relationships ship;
no controller body, generated content or private path is included. One persisted
record independently matches J850 raw-exact, 2,020 bytes. Final-file readiness
stays 693/705 available, 685 raw-exact. Complete bundle, phone production,
installation/update and runtime gates remain open.


### Whole-game False Son synchronized behaviour controller

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `6ca5a23b0f40b8067a3fa02a1d62c18ce0ea676484b724a913c05898535b509d` |

Audit: 2026-10-31. Original False Son layer/state keys select synchronized
behaviour overrides omitted by pinned AssetRipper 813fed15
AnimatorControllerProcessor.cs:93-138. The existing controller owner retains
source index order, compacts surviving ranges and preserves pointer identities;
its existing first-tree motion and clip policies apply. Only source selectors,
hashes, policies and checked pointer relationships ship; no controller body,
generated content, target byte patch or private path is included.
One persisted controller independently matches J850 raw-exact, 2,420 bytes.
Authored fixtures cover range compaction independently of game inputs.
Final-file readiness stays 693/705 available, 685 raw-exact. Complete bundle,
phone production, installation/update and runtime gates remain open.

### Whole-game UI and Railgunner display synchronized controllers

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `142d4b25e4566ddf4aa257f5e1fbc87b720346d0ed28556784b7e2181e38c9be` |

Audit: 2026-10-31. Original UI and Railgunner display layer/state identities
select the existing controller owner's first-tree motion, null-motion and
synchronized override policies. Pinned AssetRipper 813fed15
AnimatorControllerProcessor.cs:93-138 leaves synchronized overrides unset.
Only source selectors, hashes, policies and checked pointer relationships ship;
no controller body, generated content, target byte patch or private path is included.
Two persisted controllers independently match J850 raw-exact, 6,140 bytes.
Final-file readiness stays 693/705 available, 685 raw-exact. Complete bundle,
phone production, installation/update and runtime gates remain open.

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `88683044a35ff7884575ad4c9f05bc4128dfccbbee2e6e46be919e1392b48231` |

Audit: 2026-10-31. Original Seeker layer/state identities select the existing
controller owner's source ordering, null-motion and synchronized override policies.
Pinned AssetRipper 813fed15 AnimatorControllerProcessor.cs:93-138 omits synced
overrides. Only source selectors, hashes, policies and checked pointer relationships
ship; no controller body, generated content, target patch or private path.
One independently persisted controller matches J850 raw-exact, 24,584 bytes.
Final-file readiness stays 693/705 available, 685 raw-exact; complete bundle,
phone production, installation/update and runtime remain open.

### Whole-game remaining alpha renderer records

Audit: 2026-10-31. Four selectors extend the existing J1294 empty-renderer
profile and constructor; no new producer or payload template is introduced.
Original ordered component lists, retained sibling suppliers and reciprocal
GameObject ownership independently identify the Chef, BeetleQueen, DLC4 and
Croco alpha hosts. The J245 omitted-Decalicious repair explains renderer
insertion. Pinned AssetRipper GameObjectExtensions supplies ordered component
traversal knowledge. Published additions contain only original donor selectors,
checked owner PPtr relocations, type identities and output hashes; no game body,
private path, generated content or proprietary implementation is included.
Four persisted records, 576 bytes, match J850 raw-exact; GameObject membership
and complete-file, phone installation/update gates are separate and remain open.

### Whole-game False Son Boss controller

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `3481bfc27161bb1386a3072a574d7d091b455df70ce2b42620420e4d7836fc42` |

Audit: 2026-10-31. Original False Son Boss layer/state identities select the
existing controller owner, including duplicate clip-name collision ordinals.
Pinned AssetRipper 813fed15 ExportCollection.cs:70-91 derives unique exported
names after clone/instance cleanup. Only source selectors, hashes, policies and
checked pointer relationships ship; no controller body, generated content,
target byte patch or private path is included.
One independently persisted controller matches J850 raw-exact, 19,584 bytes.
Final-file readiness stays 693/705 available, 685 raw-exact; complete bundle,
phone production, installation/update and runtime remain open.

### Whole-game expanding-wave Transform callbacks

| Recipe | SHA-256 |
| --- | --- |
| `owner-whole-game-transform-owner-records.json` | `8de79965e62ba314f968dd1be244296c2f404ef3a9a6671c9fe94acb98470104` |

Audit: 2026-10-31. Eight original Transform selectors extend the existing record
owner with a source callback endpoint-distance projection. Pinned original
MonoScripts identify the two expanding-wave callback types; source radius, segment
count, curve endpoint and root position supply the float32 calculation. Reciprocal
Transform hierarchy and HitBoxGroup/ghost membership establish ownership.
Pinned AssetRipper 1ac666 TransformExtensions.cs:11 and YamlWalker.cs:430 preserve
floats unchanged; this is a callback-specific projection, not generic rounding.
Only selectors, hashes, checked pointer relationships and an authored calculation
ship. No original implementation, target-derived scalar, game body or private path
is included. Other native bytes remain intact before checked pointer relocation.
Eight persisted records match J850 raw-exact, 592 bytes. Complete-file readiness,
phone installation/update and runtime gates remain open.

### Whole-game VoidSurvivor synchronized layer chain

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `e84b83a4ce6b4ae8734c8d52a40f69410b45dccd867c2dc02e08d7f517370c9d` |

Audit: 2026-10-31. Original VoidSurvivor layers select the existing controller
owner's synchronized-link resolution. Inspected AssetRipper 1ac666f
AnimatorControllerProcessor.InitializeLayer exports machine indices as layer
links; resolving those original chains derives machine groups and ordinals.
Exact-editor allocation tracing establishes aligned source index-array sizes.
Only selectors, policies, hashes and checked pointer relationships ship; no
controller body, generated content, target byte patch or private path is included.
One independently persisted controller matches J850 raw-exact, 16,376 bytes.
Final-file readiness stays 693/705 available, 685 raw-exact; complete bundle,
phone production, installation/update and runtime remain open.

### Whole-game Reaper secondary-swing animation

| Recipe | SHA-256 |
| --- | --- |
| `owner-animation-clips.json` | `20b3c6bc413a89c082070597290a8181f0343ec5d324ff261eb731a2ad309031` |

Audit: 2026-10-31. One original AnimationClip selector uses the existing native
stream, reference-pose removal, quaternion normalization and atan2 root-average
policies. Original curve channels, orientation, loop and mirror fields supply
the calculation. J1143's pinned AssetRipper 1ac666 StreamedCurveKey and
CustomCurveResolver provide tangent/binding prior art; the existing synthetic
root-motion fixture checks atan2 projection. Only selectors, hashes and existing
policy flags ship; no curve, target scalar, generated body or private path is
included. Independently persisted output matches J850 raw-exact, 262,216 bytes.
Complete bundle, phone installation/update and original runtime remain open.

### Whole-game Heretic/Railgunner base-motion normalization

| Recipe | SHA-256 |
| --- | --- |
| `owner-animator-controllers.json` | `88f20d197bb515390ef1f68ac242b48823a16fd16e6b3096c27c3f470edff165` |

Audit: 2026-10-31. The existing controller owner follows pinned AssetRipper
813fed1597bac674def7256ce633a227e7b27497 StateConstantExtensions.GetBlendTree
and VirtualAnimationFactory: retained tree zero becomes base motion regardless
of its original synchronized slot. Override indices become unavailable.
Only original selectors, hashes, checked relationships and policies ship; no
controller body, target patch, generated data or private path is included.
Two independently persisted records match J850 raw-exact, 28,916 bytes.
Complete bundle, phone production, installation/update and runtime remain open.
