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
18-file shader closure (Uber plus 17 HLSL includes) and preserves each source
asset's `.meta`, resource, and camera bytes. The archive and generated source
remain local under the Unity Companion License. This package is a compatible
source reference, not a claim about the game's shipped package version. The
default-off activation and separate receipt are explicit; no Android or PC
visual parity is claimed. Manual provenance/privacy review: 2026-10-23.

| File | Replaces | Provenance | Privacy and licensing | Readers |
| --- | --- | --- | --- | --- |
| `owner-objective-ui-objects.json` | Private objective-UI bundle | Original object/type selectors, checked pointers, Sprite importer/crop relationships, produced texture profile and rooted container preloads. | No content body, type-tree/hash template, pixels, geometry or scalar override; audit below, 2026-10-25. | Existing `object_produce.py`; J1120 host qualification, phone gate open. |
| `owner-teleporter-indicator-objects.json` | Private teleporter-indicator bundle | Original selectors, Sprite relationships, produced RGBA/Alpha8 profiles, dummy-material keyword policy and rooted container preloads. | No content/type/pixel/keyword literals or scalar patches; audit below, 2026-10-25. | Existing `object_produce.py`; J1120 host qualification, phone gate open. |
| `owner-generic-pickup-objects.json` | Private generic-pickup bundle | Original rooted object/type selectors, checked PPtrs, one omitted component identity, Sprite/texture profiles and container relationships. | No content/type/pixel/template or scalar patches; audit below, 2026-10-25. | Existing `object_produce.py`; J1120 host qualification, phone gate open. |
| `owner-enemy-reward-objects.json` | Private enemy-reward bundle | Original object/script/behaviour selectors, pinned SDK base-schema selector, checked PPtrs, component omissions and rooted container relationships. | No body, type tree/hash or scalar template; audit below, 2026-10-25. | Existing `object_produce.py`; complete host and phone qualification tracked separately. |
| `owner-villagenight-objects.json` | Private Village Night streamed scene | Original object/type selectors, checked PPtr/component relationships, scene/member identities and source mesh profile. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1134 host exact, phone open. |
| `owner-helminthroost-objects.json` | Private Helminth Roost streamed scene | Original object/type selectors, checked PPtr/component relationships, scene/member identities and source mesh profile. | No body/tree/geometry/pixel/scalar template; provenance/privacy/licensing audit below, 2026-10-25. | Existing `object_produce.py`; J1135 host exact, phone open. |
| `owner-teleport-material-objects.json` | Private teleport-material bundle | Original material/type selectors, checked references, named dummy-shader keyword policy and container relationships. | No material/shader body, keyword literal, numeric override or target template; audit below, 2026-10-25. | Source-only `object_produce.py`; J1117 host qualification, phone gate open. |
| `owner-death-effect-objects.json` | Private replay player-death-effect bundle | Rooted original graph/script selectors, checked pointer extents, preload/dependency identities and hashes. | No body, type-tree snapshot, scalar/curve override or target delta; audit below, 2026-10-25. | Existing original-input-only `object_produce.py`; J1115 host qualification, phone gate open. |
| `owner-pickup-objects.json` | Private replay pickup bundle | Original selectors, hashes, checked pointer extents and destination relationships. | No bodies, type trees or target deltas; full audit below, 2026-10-25. | Original-input-only `object_produce.py`; J1113 host qualification, phone gate open. |
| `owner-bootstrap.json` | Authored bootstrap TextAsset | Existing public build-entry attempt identity/input ID and four original preload GUID relationships absent from the original catalog. | No object/body/type-tree/target template or protected text; audit below, 2026-10-25. | Existing `player_data.text_files`; J1118 host qualification, phone gate open. |
| `owner-player-data.json` | 153 private player files | Original object selectors, checked pointers/importer relationships, authored JSON/assembly order and existing texture-pack record identities. | No game bodies, pixels, text payloads, type-hash overrides or private identifiers; full audits below, 2026-10-25. | Explicit PC/SDK/fresh-converter and pinned source-produced texture packs; J1118 host qualification; landed PR75 provider, phone gate open. |
| `owner-uncompressed-textures.json` | Private replay uncompressed texture bodies/pixels | Original/destination selectors, source extents, generic import/placement metadata and hashes; copy, BC1, source-coordinate dilation and public JPEG policy. | No pixels, palettes, target literals/patches, native SDK implementation or image/library bytes; full audit above, 2026-10-24. All 399 records qualify on host/Android in J1079. | Explicit PC-input-only `texture_produce.py` and separately built public JPEG tool; no current game-build consumer. |
| `owner-alpha-textures.json` | Private replay source Alpha8/single-mip texture cohort (J1082) | Canonical original/destination selectors, source/field extents, import/storage settings and hashes. | No alpha samples, encoded blocks, target byte frames, protected source or private identifiers; full audit below, 2026-10-24. | Original-PC-input-only `texture_produce.py` plus separately built public codec; no game-build consumer. |
| `owner-rgb-textures.json` | Complete ETC1/single-mip target cohort | Original/destination selectors, field/pixel extents, hashes and source JPEG policy; composition aliases reuse original Warp/Elite ramps. | No colors, normal vectors, palettes, encoded blocks or target byte frames; audit below, 2026-10-24. | Original-input-only `texture_produce.py` and public ETC/JPEG tools; J1088 qualifies all 281 records on Android. |
| `owner-rgba-textures.json` | Complete non-Alpha8 ETC2 RGBA/single-mip target cohort | Original/destination selectors, byte/field extents, hashes and canonical source relationships. | No pixels, palettes, encoded blocks, SDK implementation, private paths or target byte frames; audit below, 2026-10-24. | Existing source-only texture owner plus separately supplied SDK codec and public BC7 decoder; full phone qualification pending. |
| `owner-generic-records.json` | Qualified remaining native/scripted object records | Original selectors/hashes, destination identities and checked PPtr relationships. | Every source field, script ID and native type hash is preserved; no state/property/particle value or target template. Audit below, 2026-10-25. | Source-only `record_produce.py`; host cohort and open phone/assembly gates recorded with the generic slice. |
| `owner-gameobjects.json` | Qualified private GameObject record cohort | Original source bundle/member/object selectors and hashes, destination identities and checked PPtrs. | No component value, body or target template; original fields and native type identity preserved. Audit below, 2026-10-25. | Source-only `record_produce.py`; host qualification and remaining gates recorded with the hierarchy slice. |
| `owner-transforms.json` | Qualified private Transform record cohort | Original source bundle/member/object selectors and hashes, destination identities and checked PPtrs. | No position, rotation, scale, hierarchy template or target scalar; source fields/native type identity preserved. Audit below, 2026-10-25. | Source-only `record_produce.py`; host qualification and remaining gates recorded with the hierarchy slice. |
| `owner-animation-clips.json` | Qualified private AnimationClip object cohort | Original selectors/hashes, destination relationships and named source-schema animation policies. | No curve, pose, event/string/body template, arbitrary patch or target scalar; audit below, 2026-10-25. | Source-only `record_produce.py`; J1119 host qualification, full cohort/phone gate open. |
| `owner-material-records.json` | Qualified private Material object cohort | Original selectors/hashes, checked PPtr relationships and existing dummy-shader keyword policy. | No material value, keyword string, shader program, body template or target scalar; audit below, 2026-10-25. | Source-only `record_produce.py`; J1119 host qualification, remaining materials/phone gate open. |
| `owner-animator-controllers.json` | Qualified private AnimatorController object cohort | Original selectors/hashes and checked PPtr relationships only. | No native controller body, TOS table, curve/state value or target template; audit below, 2026-10-25. | Source-only `record_produce.py`; J1119 host qualification, full cohort/phone gate open. |
| `owner-rgb-mip-textures.json` | Complete ETC1 mip-chain target cohort | Original/destination selectors, field/pixel extents, hashes, full mip counts and source JPEG/normal relationships. | No pixels, vectors, encoded blocks, SDK bytes or target frames; audit below, 2026-10-24. | Existing texture owner, native pixel/mip helper and public ETC/JPEG/Unity Crunch tools; J1110 qualifies the full host cohort, Android pending. |
| `owner-rgba-mip-textures.json` | Full RGBA mip-chain target cohort | Original/destination selectors, field/resource extents, source import relationships and hashes. | No pixels, block literals, serialized templates or SDK bytes; audit below, 2026-10-25. | Existing texture owner plus explicit SDK/public EAC tools; J1128 host qualification, Android open. |
| `owner-cubemap-textures.json` | 110 source-derived Cubemaps | Original face-chain selectors, field/resource extents, import relationships and hashes. | No pixels, encoded blocks, target body templates or native-probe fallback; audit below, 2026-10-25. | Existing texture owner and pinned public/SDK tools; J1128 host qualification, Android open. |
| `owner-avatars.json` | Private replay Avatar bodies (J1075) | Minimum original/destination identities, hashes, source extents and source-entry permutations. | No strings, poses, rig/geometry values, target literals or byte frames; full audit above, 2026-10-24. | Explicit PC-input-only `avatar_produce.py`; no current game-build consumer. |
| `owner-meshes.json` | Protected mesh bodies in the private replay packet, for the included cohort only (J1070) | Original bundle/object/resource selectors, destination identities/hashes and authored import/conversion settings. | No geometry arrays, collision data, target byte frames or float literals; full audit above, 2026-10-24. Two cases remain excluded. | Explicit original-input-only `mesh_produce.py`; no current game-build consumer. |
| `shader-postprocessing-bloom-candidate.json` | Exported one-pass Bloom and exact source-camera CopyStd placeholders | Accepted-input source/meta/resource identities, official Unity package/license hashes and pass contracts; authored camera staging pin refreshed without changing camera transforms. | Authored selection metadata only; upstream source and generated content stay local under Unity Companion License. Manual audit 2026-10-23 described above. | `shader_postprocessing_bloom`, whole-catalog preparation and catalog replay comparison; default off. |
| `shader-postprocessing-uber-candidate.json` | Exact source-camera `PostProcessResources.uber` one-pass constant-white placeholder | Accepted-input Main Camera/resource/shader/profile identities, official archive/license/source hashes, pass-0 call contract and 18-file include closure. | Reconstruction metadata only; official shader/includes and generated candidates stay ignored under Unity Companion License. Package 2.3.0 is a compatible reference, not a shipped-version claim. Audited 2026-10-23. | `shader_postprocessing_uber`, whole-catalog preparation and catalog replay comparison; independent default-off activation. |

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

Implementation/verification outcome: [J550](../docs/PORTING_JOURNAL.md#j550--track-the-content-recipe-as-a-public-recipe).

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
SDK APIs provide the observer/normal shell package stop; no Android source or
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
arbitrary scalar replacement is present. Controllers preserve all non-pointer
bytes. Materials reuse checked original fields and the existing named keyword
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
