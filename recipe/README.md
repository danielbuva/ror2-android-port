# Build recipes

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

| File | Replaces | Provenance | Privacy and licensing | Readers |
| --- | --- | --- | --- | --- |
| `asset-transforms.json` | Preview copies for 28 SurfaceDefs, six identity assets, ten field-only prefabs and all 178 structural prefabs/scenes (migration-removal commit 4 cohorts) | Accepted-export selectors/SHA-256; authored clearing, identity, typed field edits, explicit local-reference nulling, component/settings deletion and two typed adapter constructors. Four UI prefabs reuse the hash-pinned uGUI mapping. | J548 minimal source/output, hierarchy/script, removal/owner identifiers, field paths, reference preconditions, activation/reflection values and deterministic allocation namespaces only. No YAML blocks, original component bodies, importer bodies, private paths or historical asset reads. Constructor defaults are authored schemas matching the existing sanitizer; seed names preserve its IDs without reading the named location. Provenance/privacy/licensing audit extended 2026-10-17. | `asset_transforms.py` gates input/source hashes and returns asset/meta bytes; `composition_migration.stage` verifies them against the existing plan before writing. Current `asset-transforms-check` compares the migration-stage oracle, reports exclusive structural cohorts and lists later project changes separately, without writing. |
| `hud-ui-remaps.json` | `work/config/hud-ui-remaps.json` (LOCAL_STATE blocker B2) | 43 rows mapping Unity's own uGUI script identities: the precompiled `UnityEngine.UI.dll` reference in exported scenes (`from`) to the public `com.unity.ugui` package script GUID (`to`), with the type name and package path. Measured for input `6af7ed94…`; re-verified for the 2021.3.45f2 toolchain. | No game content, names or assets; identifiers and hashes only. One repo-relative evidence path. Audited 2026-10-17. | `composition_migration.py`, `whole_catalog.py`, `source_scene_candidate.py`, `integrated_objective.py`; each checks `input_id`, two also the `UnityEngine.UI.dll` hash |
| `runtime-sources.json` | Explicit and existing-file membership in `build.py` and the `whole_catalog.build_integration` copy loop | Authored file list: 92 sorted C# paths relative to `tools/unity`; coordinator entry renamed to `PortSession.cs` (source name only). Initial selection reproduces the old rules using generated-project filenames and existence only. | No game content, generated source, private paths or identifiers; repository-authored source names only. Audited 2026-10-17. | `build.py` derives player-only source and `.meta` inputs; `whole_catalog.py` stages the same selection. No game input dependency. |
| `project-layout.json` | Inherited authored script identities and package dependency selection | 92 GUID lines for authored sources in `runtime-sources.json`; 36 public direct dependency pins. | Identifiers and public package coordinates only; no importer bodies, game-derived content or private URLs. Per-package audit below, 2026-10-17. | `build.py` validates staged identities and manifest dependencies without writing them. No game input dependency. |
| `runtime-config.json` | Public selection in ignored `Resources/MovementBatchProbe.json`; generated at whole-catalog build entry | The lab's runtime selection for the accepted input `6af7ed94…` (Steam build 25475991); 183 present `SessionConfig` keys, preserving values and JSON types. | Authored options and necessary identifiers/relationships only; no protected content. 45 authored fields (44 present), 139 selector fields, 0 private/content fields. Excluded: `detailedVisualDiagnostics` is absent locally, so no value is invented. Audit details below, 2026-10-17. | `build.py` checks recipe keys against staged config after layout validation; extra local/obsolete keys remain allowed. Build-entry generation replaces the whole object before existing accepted-input-gated validation; no extra keys survive generation. |
| `content.json` | Public selection in ignored `work/scene-probe-build.json`; generated at whole-catalog build entry | Accepted input `6af7ed94…` (Steam build 25475991); 14 current build fields, 4,304 path strings, values and array order unchanged. | J548 permits these minimal selectors; no asset bodies, private paths or device/storage identities. Includes 61 Wwise asset UUID filenames, not middleware or banks. All fields retained; audit below, 2026-10-17. | `build.py` validates after runtime config on the accepted-input-gated whole-catalog path, before cache lookup/editor invocation. Build-entry generation replaces the work file from this recipe before validation. |

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

Implementation/verification outcome: [J550](../docs/PORTING_JOURNAL.md#j550--track-the-content-selection-as-a-public-recipe).

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
  are unchanged. It is not reached after generation in either current build path.

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
