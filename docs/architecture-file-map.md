# Architecture file map

> **Dated snapshot.** This is a static audit taken on 2026-10-16. Line numbers drift as code
> changes; regenerate or re-audit it before relying on a specific `file:line`. The current
> map is [ARCHITECTURE.md](ARCHITECTURE.md).

Per-file evidence behind [ARCHITECTURE.md](ARCHITECTURE.md): a static source audit,
2026-10-16, by Codex (gpt-6.1-sol), reviewed and corrected by Claude. No build,
editor, device run or readiness claim is made.

Only filenames/path existence were inspected in the authorized shared generated
project. No generated file contents, hashes or configuration were read or copied.
`work/lab-project/Assets` below is the logical project path. Presence proves neither matching contents nor
what is in the installed APK. J501 in `docs/PORTING_JOURNAL.md` explains why this
staging distinction matters; the current snapshot remains `PORTING_STATE.md`.

## A. Unity and catalog files

- **current**: staged/retained in the whole-catalog player and statically reachable
  from `body-state-spawn-state-auto-nova-spine`, including setup, predicates,
  cleanup, resource lookups and conditional stage/content branches.
- **support**: editor/host tooling or staged diagnostics outside that case. A
  diagnostic routine in a current partial file does not make that routine live.
- **historical**: no staging/use by the named current builder chain. Older
  experiment-only staging sites are shown where they exist.

`build.py` does not itself copy the listed Unity sources. Its explicit inputs at
`scripts/lab/build.py:67` and existing-file membership at `scripts/lab/build.py:78`
feed the copy loop at `scripts/lab/whole_catalog.py:1067`. That loop only checks
`Assets/LabLoadingScene`, not every file below `Assets`. C# retained only through
that rule is labelled **existing-file-only**. Nova/scene builders also stage
support experiments; those sites do not prove playable reachability.

The existence column is yes/no for the matching source destination under
`work/lab-project/Assets`, including renamed linker destinations. Templates
executed as MCP code need not exist as project files. Retained editor fixtures
with no tracked copy site have **unclear staging provenance**, stated explicitly.

### `tools/unity`

| File | Status | Subsystem | Exists | Staging/use evidence; current runtime call |
| --- | --- | --- | --- | --- |
| `runtime/session/ActiveClientBoundary.cs` | current | session | yes | `scripts/lab/nova_bridge.py:68`; `ConnectActiveBodyClient(player)` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:283` |
| `runtime/shaders/AndroidBillboardPresentation.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadShader` family selection at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:34` |
| `runtime/shaders/AndroidColorGrade.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadShader("AndroidColorGrade")` at `tools/unity/runtime/input/AndroidPresentationCamera.cs:14` |
| `runtime/shaders/AndroidDistortionPresentation.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadShader` family selection at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:34` |
| `runtime/shaders/AndroidIntersectionPresentation.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadShader` family selection at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:34` |
| `runtime/shaders/AndroidMaterialPresentation.cs` | current | shaders | yes | `scripts/lab/nova_bridge.py:69`; `AndroidMaterialPresentation.Begin` at `tools/unity/runtime/session/PortSession.cs:64` |
| `runtime/shaders/AndroidNativeDeferredPresentation.cs` | current | shaders | yes | `scripts/lab/composition_migration.py:340`; `AndroidNativeDeferredPresentation.Begin` at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:13` |
| `runtime/progression/AndroidOfflineProfile.cs` | current | progression | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `new AndroidOfflineProfile` at `tools/unity/runtime/progression/AndroidProfileBoundary.cs:111` |
| `runtime/input/AndroidOfflineSettings.cs` | current | input/camera | yes | Existing-file-only staging: `scripts/lab/build.py:78` (membership), `scripts/lab/whole_catalog.py:1067` (copy); `new AndroidOfflineSettings` at `tools/unity/runtime/input/OfflineSettingsBoundary.cs:13` |
| `runtime/shaders/AndroidOpaqueParticlePresentation.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadShader` family selection at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:34` |
| `runtime/shaders/AndroidParticlePresentation.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadShader` family selection at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:34` |
| `runtime/input/AndroidPresentationCamera.cs` | current | input/camera | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `AddComponent<AndroidPresentationCamera>` at `tools/unity/runtime/input/NovaDiagnosticDisplay.cs:71` |
| `runtime/progression/AndroidProfileBoundary.cs` | current | progression | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareAndroidProfile(player)` at `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:165` |
| `runtime/progression/AndroidProgressionBoundary.cs` | current | progression | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `androidProgression.Prepare` at `tools/unity/runtime/progression/AndroidProfileBoundary.cs:96` |
| `runtime/shaders/AndroidRecoveredReflections.cginc` | current | shaders | yes | `scripts/lab/nova_bridge.py:74`; Shader include at `tools/unity/runtime/shaders/AndroidSurfacePresentation.shader:17`; runtime shader load at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:34` |
| `runtime/stage/AndroidStageTransport.cs` | current | stage transport | yes | `scripts/lab/nova_bridge.py:68`; `AddComponent<AndroidStageTransport>` at `tools/unity/runtime/stage/IntegratedStageBoundary.cs:110` |
| `runtime/shaders/AndroidSurfacePresentation.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadShader` family selection at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:34` |
| `runtime/shaders/AndroidTerrainPresentation.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadShader` family selection at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:34` |
| `runtime/shaders/AndroidWaterPresentation.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadShader` family selection at `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:34` |
| `experiments/AudioAssetProbe.cs` | historical | diagnostics | no | `scripts/lab/scene_runtime.py:434` (historical preparation function; no current command reaches it) |
| `runtime/world/AutomaticDirectionBoundary.cs` | current | world/director | yes | `scripts/lab/scene_runtime.py:584`; `automaticDirection=IsAutomaticDirection()` at `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:16` (predicate reached; direction-only routine bypassed) |
| `runtime/world/AutomaticDirectorBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:74` → copy loop `scripts/lab/whole_catalog.py:1067`; `SpawnAutomaticEnemy(template` at `tools/unity/runtime/world/EnemyRewardBoundary.cs:83` |
| `runtime/world/AutomaticGroundBoundary.cs` | support | world/director | yes | `scripts/lab/scene_runtime.py:584` |
| `runtime/world/AutomaticHealthBoundary.cs` | support | world/director | yes | `scripts/lab/scene_runtime.py:584` |
| `runtime/world/AutomaticModelBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareAutomaticModel(body)` at `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:31` |
| `runtime/world/AutomaticSkillBoundary.cs` | current | world/director | yes | `scripts/lab/scene_runtime.py:584`; `if(IsAutomaticSkill())EnableAutomaticSkills` at `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:32` (predicate reached; isolated skill routine bypassed) |
| `runtime/world/AutomaticSpawnBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:74` → copy loop `scripts/lab/whole_catalog.py:1067`; `AutomaticSpawnBoundary(spawned,cfg)` at `tools/unity/runtime/session/PortSession.cs:541` |
| `runtime/commerce/BarrelInteractionBoundary.cs` | current | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68`; `CleanupOriginalBarrel()` at `tools/unity/runtime/input/NovaInputBoundary.cs:143` |
| `runtime/catalog/BarrierEffectBoundary.cs` | current | catalog/resources | yes | `scripts/lab/scene_runtime.py:584`; `PrepareBarrierEffect(config)` at `tools/unity/runtime/session/PortSession.cs:75` |
| `runtime/catalog/BodyCatalogBoundary.cs` | current | catalog/resources | yes | `scripts/lab/nova_bridge.py:68`; `RegisterBodyCatalog()` at `tools/unity/runtime/session/PortSession.cs:68` |
| `runtime/catalog/CatalogAddressProbe.cs` | support | catalog/resources | yes | Retained `Assets/Editor` file; no tracked copy site found; staging provenance unclear; editor menu use `scripts/lab/editor.py:36` |
| `runtime/session/CharacterDirectionProbe.cs` | support | diagnostics | yes | `scripts/lab/scene_runtime.py:416` |
| `experiments/CharacterMotorOrderProbe.cs` | historical | diagnostics | no | `scripts/lab/scene_runtime.py:868` (historical preparation function; no current command reaches it) |
| `runtime/commerce/ChestDropTableBoundary.cs` | support | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68` |
| `runtime/commerce/ChestEjectionBoundary.cs` | current | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68`; `OwnChestAnimationSources(` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:365` |
| `runtime/commerce/ChestPurchaseBoundary.cs` | current | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68`; `ChestPurchaseBuffs(cfg)` at `tools/unity/runtime/session/PortSession.cs:326` (buff/artifact helpers; purchase experiment bypassed) |
| `runtime/commerce/ClientCoinBoundary.cs` | support | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68` |
| `experiments/CollectionsRuntimeProbe.cs` | historical | diagnostics | no | No current staging site found; older isolated boundary experiment: `scripts/lab/boundaries.py:116` |
| `runtime/world/CombatSpineBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareCombatScene(body,cfg)` at `tools/unity/runtime/input/NovaInputBoundary.cs:63` |
| `runtime/session/CommandoMaterialPreview.cs` | support | diagnostics | yes | `scripts/lab/scene_runtime.py:257` |
| `runtime/shaders/CommandoMaterialPreview.shader` | current | shaders | yes | `scripts/lab/scene_runtime.py:377`; Runtime shader lookup at `tools/unity/runtime/input/NovaDiagnosticDisplay.cs:35` |
| `experiments/CommandoPosePreview.cs` | historical | diagnostics | no | `scripts/lab/scene_runtime.py:175` (historical preparation function; no current command reaches it) |
| `runtime/shaders/CommandoPreview.shader` | current | shaders | yes | `scripts/lab/scene_runtime.py:235`; Runtime shader lookup at `tools/unity/runtime/input/NovaDiagnosticDisplay.cs:35` |
| `experiments/ControllerAddressLink.xml` | historical | catalog/resources | no | `scripts/lab/scene_runtime.py:259` (historical preparation function; no current command reaches it) |
| `runtime/session/ControllerAddressProbe.cs` | support | diagnostics | yes | `scripts/lab/scene_runtime.py:257` |
| `runtime/session/DebugAccelerationBoundary.cs` | current | diagnostics | yes | `scripts/lab/nova_bridge.py:68`; `PrepareDebugAcceleration(body)` at `tools/unity/runtime/input/NovaInputBoundary.cs:72` |
| `runtime/world/DirectorActorBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `RecordDirectorActor` at `tools/unity/runtime/world/AutomaticDirectorBoundary.cs:40` |
| `runtime/world/EnemyRewardBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareEnemyRewards(player,cfg)` at `tools/unity/runtime/world/EnemySpineBoundary.cs:59` |
| `runtime/world/EnemySpineBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:75` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareEnemy(body,cfg)` at `tools/unity/runtime/input/NovaInputBoundary.cs:66` |
| `runtime/session/EntityStateTickProbe.cs` | support | diagnostics | yes | `scripts/lab/scene_runtime.py:397` |
| `runtime/commerce/GenericPickupBoundary.cs` | current | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68`; `CleanupOriginalDefaultPickup()` at `tools/unity/runtime/input/NovaInputBoundary.cs:143` |
| `runtime/stage/GoldshoresBoundary.cs` | current | stage transport | yes | `scripts/lab/whole_catalog.py:1065`; `IsGoldshoresEntryPortal(exit)` at `tools/unity/runtime/stage/TeleporterWorldBoundary.cs:376` |
| `runtime/commerce/InputBarrelBoundary.cs` | support | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68` |
| `runtime/progression/IntegratedResultsBoundary.cs` | current | session | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareIntegratedResults(player,cfg)` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:310` |
| `runtime/stage/IntegratedStageBoundary.cs` | current | stage transport | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `TransportIntegratedStage(bridge,began)` at `tools/unity/runtime/input/NovaInputBoundary.cs:84` |
| `runtime/world/IntegratedWorldBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareIntegratedWorld(body,cfg)` at `tools/unity/runtime/input/NovaInputBoundary.cs:67` |
| `runtime/commerce/InteractionSelectionBoundary.cs` | current | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68`; `DriverField(worldDriver,"networkIdentity")` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:363` (reflection/equipment helpers; selection experiment bypassed) |
| `runtime/commerce/ItemPickupBoundary.cs` | current | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68`; `CleanupOriginalItemPickup()` at `tools/unity/runtime/input/NovaInputBoundary.cs:143` |
| `experiments/KinematicBatchProbe.cs` | historical | diagnostics | no | `scripts/lab/scene_runtime.py:585` (probe selector), `scripts/lab/scene_runtime.py:586` (copy) (historical preparation function; no current command reaches it) |
| `experiments/LoadingSceneProbe.cs` | historical | diagnostics | no | `scripts/lab/scene_runtime.py:174` (historical preparation function; no current command reaches it) |
| `experiments/MetadataDispatchProbe.cs` | historical | diagnostics | no | No current staging site found; older isolated boundary experiment: `scripts/lab/boundaries.py:65` |
| `runtime/commerce/MoneyCostBoundary.cs` | current | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68`; `CleanupOriginalMoneyCost()` at `tools/unity/runtime/input/NovaInputBoundary.cs:143` |
| `runtime/stage/MoonEscapeBoundary.cs` | current | stage transport | yes | `scripts/lab/nova_bridge.py:68`; `TickMoonTimers()` at `tools/unity/runtime/world/RunClockBoundary.cs:67` |
| `runtime/stage/MoonMissionBoundary.cs` | current | stage transport | yes | Explicit player input at `scripts/lab/build.py:75` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareMoonSupport(cfg)` at `tools/unity/runtime/stage/TeleporterWorldBoundary.cs:127` |
| `runtime/shaders/MoonPillarBeaconPreview.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `ObserveMoonBeacons` lookup at `tools/unity/runtime/presentation/MoonPillarPresentation.cs:52` (Moon branch only) |
| `runtime/shaders/MoonPillarBeamPreview.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadStageGeometry` resource lookup at `tools/unity/runtime/stage/StageGeometryBoundary.cs:135` |
| `runtime/presentation/MoonPillarPresentation.cs` | current | HUD/UI | yes | `scripts/lab/nova_bridge.py:68`; `CleanupMoonPillarPresentation()` at `tools/unity/runtime/stage/MoonMissionBoundary.cs:256` |
| `runtime/session/PortSession.cs` | current | diagnostics | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `var selected=RunSelectedProbe(catalogFixture)` at `tools/unity/runtime/session/PortSession.cs:84` |
| `runtime/input/NovaDiagnosticDisplay.cs` | current | input/camera | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `new NovaDiagnosticDisplay` at `tools/unity/runtime/input/NovaInputBoundary.cs:61` |
| `runtime/input/NovaInputBoundary.cs` | current | input/camera | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `NovaInputBoundary(body,machine,cfg)` at `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:66` |
| `runtime/input/NovaInputBridge.cs` | current | input/camera | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `AddComponent<NovaInputBridge>` at `tools/unity/runtime/input/NovaInputBoundary.cs:71` |
| `runtime/input/NovaThirdPersonView.cs` | current | input/camera | yes | `scripts/lab/nova_bridge.py:68`; `new NovaThirdPersonView` at `tools/unity/runtime/input/NovaDiagnosticDisplay.cs:74` |
| `runtime/session/OfflineApplicationBoundary.cs` | current | session | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `AwaitOfflineRunStart(config)` at `tools/unity/runtime/session/PortSession.cs:83` |
| `runtime/progression/OfflineLoadoutBoundary.cs` | current | progression | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `DrawOfflineLoadout()` at `tools/unity/runtime/session/OfflineApplicationBoundary.cs:58` |
| `runtime/session/OfflineRunSeedBoundary.cs` | current | session | yes | Explicit player input at `scripts/lab/build.py:75` → copy loop `scripts/lab/whole_catalog.py:1067`; `SelectOwnedRunSeed(cfg)` at `tools/unity/runtime/world/EnemyRewardBoundary.cs:65` |
| `runtime/input/OfflineSettingsBoundary.cs` | current | input/camera | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareOfflineSettings()` at `tools/unity/runtime/session/OfflineApplicationBoundary.cs:35` |
| `runtime/catalog/OriginalBodyVisualBoundary.cs` | current | catalog/resources | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareOriginalBodyVisualReferences()` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:380` |
| `runtime/catalog/OriginalGlobalCommonAssetsBoundary.cs` | current | catalog/resources | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareOriginalGlobalCommonAssets()` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:380` |
| `runtime/commerce/PickupDropletCollisionBoundary.cs` | support | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68` |
| `runtime/commerce/PickupDropletFlightBoundary.cs` | current | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68`; `DropletFlightArtifacts(cfg)` at `tools/unity/runtime/session/PortSession.cs:445` (artifact helper; flight experiment bypassed) |
| `runtime/commerce/PickupDropletLoadBoundary.cs` | support | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68` |
| `runtime/world/PlayerDefeatBoundary.cs` | current | world/director | yes | `scripts/lab/nova_bridge.py:68`; `PreparePlayerDefeat(body,cfg)` at `tools/unity/runtime/input/NovaInputBoundary.cs:65` |
| `runtime/world/PrimaryFireBoundary.cs` | current | world/director | yes | `scripts/lab/nova_bridge.py:68`; `ObserveSpinePrimary(body)` at `tools/unity/runtime/input/NovaInputBoundary.cs:92` |
| `runtime/session/ReconstructionProbe.cs` | support | diagnostics | no | `scripts/lab/recovery.py:79` (export-project → wire_reconstruction) |
| `runtime/presentation/RecoveredHudBoundary.cs` | current | HUD/UI | yes | `scripts/lab/nova_bridge.py:70`; `PrepareRecoveredHud()` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:385` |
| `runtime/presentation/RecoveredHudBuilder.cs` | support | HUD/UI | yes | `scripts/lab/nova_bridge.py:71` |
| `runtime/presentation/RecoveredHudFeedback.cs` | current | HUD/UI | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `recoveredHud.QueuePickup` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:468` |
| `runtime/presentation/RecoveredHudPresentation.cs` | current | HUD/UI | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `recoveredHud.Present` at `tools/unity/runtime/presentation/RecoveredHudBoundary.cs:28` |
| `runtime/presentation/RecoveredPickupPresentation.cs` | current | HUD/UI | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `notificationView.Present(notice)` at `tools/unity/runtime/presentation/RecoveredHudFeedback.cs:57` |
| `experiments/ReferenceIdentityProbe.cs` | historical | diagnostics | no | `scripts/lab/scene_runtime.py:71` (historical preparation function; no current command reaches it) |
| `runtime/session/RewiredPlatformBoundary.cs` | support | diagnostics | yes | `scripts/lab/scene_runtime.py:584` |
| `experiments/RewiredTrialBuild.cs` | historical | diagnostics | no | No current staging site found; SDK experiment consumes externally prepared project, `scripts/lab/rewired_trial.py:14` / `scripts/lab/rewired_trial.py:57` |
| `experiments/RewiredTrialControllerProbe.cs` | historical | diagnostics | no | No current staging site found; SDK experiment consumes externally prepared project, `scripts/lab/rewired_trial.py:14` / `scripts/lab/rewired_trial.py:57` |
| `experiments/RewiredTrialInventory.cs` | historical | diagnostics | no | No current staging site found; SDK experiment consumes externally prepared project, `scripts/lab/rewired_trial.py:14` / `scripts/lab/rewired_trial.py:57` |
| `experiments/RoR2SliceProbe.cs` | historical | diagnostics | no | No current staging site found; older isolated boundary experiment: `scripts/lab/boundaries.py:178` |
| `runtime/world/RunClockBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareRunSceneContext(cfg)` at `tools/unity/runtime/input/NovaInputBoundary.cs:64` |
| `runtime/session/SessionResourceBoundary.cs` | current | session | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `CollectPriorSessionGarbage()` at `tools/unity/runtime/session/PortSession.cs:64` |
| `runtime/world/SilentProjectileBoundary.cs` | current | world/director | yes | `scripts/lab/nova_bridge.py:68`; `AddComponent<SilentProjectileBoundary>` at `tools/unity/runtime/world/CombatSpineBoundary.cs:42` |
| `runtime/catalog/SpawnStateBoundary.cs` | current | catalog/resources | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `if(r.id.StartsWith("body-state-spawn-state-auto-")){var preparation=PrepareSpawnStateCatalog(cfg)` at `tools/unity/runtime/session/PortSession.cs:533` |
| `runtime/world/StageBossContentBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareStageBossContent(cfg)` at `tools/unity/runtime/stage/TeleporterWorldBoundary.cs:127` |
| `runtime/world/StageCombatDeckBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:74` → copy loop `scripts/lab/whole_catalog.py:1067`; `SelectStageCombatDeck(cfg` at `tools/unity/runtime/stage/TeleporterWorldBoundary.cs:335` |
| `runtime/stage/StageGeometryBoundary.cs` | current | stage transport | yes | Explicit player input at `scripts/lab/build.py:75` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareStageGeometry(cfg)` at `tools/unity/runtime/session/PortSession.cs:531` |
| `runtime/world/StagePopulationBoundary.cs` | current | world/director | yes | `scripts/lab/nova_bridge.py:68`; `PrepareStagePopulationSupport(cfg)` at `tools/unity/runtime/stage/TeleporterWorldBoundary.cs:127` |
| `runtime/shaders/StageSurfacePreview.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadStageGeometry` resource lookup at `tools/unity/runtime/stage/StageGeometryBoundary.cs:115` |
| `runtime/shaders/StageTerrainPreview.shader` | current | shaders | yes | `scripts/lab/nova_bridge.py:73`; `LoadStageGeometry` resource lookup at `tools/unity/runtime/stage/StageGeometryBoundary.cs:115` |
| `experiments/StartupSegmentProbe.cs` | historical | diagnostics | no | `scripts/lab/scene_runtime.py:435` (historical preparation function; no current command reaches it) |
| `runtime/session/SurvivorSelectionBoundary.cs` | current | session | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `SelectedPlayerPrefab(cfg)` at `tools/unity/runtime/session/PortSession.cs:324` |
| `runtime/catalog/TeleportMaterialBoundary.cs` | current | catalog/resources | yes | `scripts/lab/scene_runtime.py:584`; `PrepareTeleportMaterial(config)` at `tools/unity/runtime/session/PortSession.cs:71` |
| `experiments/TeleporterTimelineLink.xml` | historical | stage transport | no | `scripts/lab/nova_bridge.py:72` (historical preparation function; no current command reaches it) |
| `runtime/stage/TeleporterWorldBoundary.cs` | current | stage transport | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareTeleporterWorld(cfg)` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:379` |
| `runtime/catalog/WholeCatalogBootstrap.cs` | support | catalog/resources | yes | `scripts/lab/whole_catalog.py:819`; selection-only boot, `tools/unity/runtime/catalog/WholeCatalogBootstrap.cs:23`; ordinary spine is gated separately at `tools/unity/runtime/session/PortSession.cs:49` |
| `runtime/catalog/WholeCatalogComposed.cs` | current | catalog/resources | yes | `scripts/lab/nova_bridge.py:68`; `WholeCatalogComposed.Prepare()` at `tools/unity/runtime/catalog/BodyCatalogBoundary.cs:96` |
| `runtime/catalog/WholeCatalogLoader.cs` | current | catalog/resources | yes | `scripts/lab/whole_catalog.py:818`; `WholeCatalogLoader.RegisterLocations` at `tools/unity/runtime/catalog/WholeCatalogComposed.cs:101` |
| `runtime/world/WholeInteractableBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PopulateWholeStage()` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:383` |
| `runtime/world/WholePopulationBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:75` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareWholeRunAvailability()` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:286` |
| `runtime/commerce/WorldChestBreadthBoundary.cs` | current | commerce/pickups | yes | `scripts/lab/nova_bridge.py:68`; `WorldChestTypes(cfg)` at `tools/unity/runtime/catalog/SpawnStateBoundary.cs:75` |
| `runtime/commerce/WorldCommerceBoundary.cs` | current | commerce/pickups | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareWorldCommerce(cfg` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:382` |
| `runtime/world/WorldDotBoundary.cs` | current | world/director | yes | Existing-file-only staging: `scripts/lab/build.py:78` (membership), `scripts/lab/whole_catalog.py:1067` (copy); `PrepareWorldDotSupport(cfg)` at `tools/unity/runtime/stage/TeleporterWorldBoundary.cs:130` |
| `runtime/world/WorldEquipmentBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareWorldEquipment(player,cfg)` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:362` |
| `runtime/world/WorldFlightEquipmentBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareFlightEquipmentSource(source` at `tools/unity/runtime/world/WorldEquipmentBoundary.cs:55` |
| `runtime/world/WorldHealingItemsBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareWorldHealingItemSource(path` at `tools/unity/runtime/world/WorldProcContentBoundary.cs:25` |
| `runtime/world/WorldItemBehaviorBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareWorldItemBehaviors(cfg)` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:382` |
| `runtime/world/WorldItemDisplayBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareWorldItemDisplays(player,cfg)` at `tools/unity/runtime/world/IntegratedWorldBoundary.cs:362` |
| `runtime/world/WorldLegendaryItemsBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareWorldLegendaryItemSource(path` at `tools/unity/runtime/world/WorldProcContentBoundary.cs:26` |
| `runtime/world/WorldProcContentBoundary.cs` | current | world/director | yes | Explicit player input at `scripts/lab/build.py:76` → copy loop `scripts/lab/whole_catalog.py:1067`; `PrepareWorldProcSupport(cfg)` at `tools/unity/runtime/stage/TeleporterWorldBoundary.cs:130` |

### `tools/catalog`

| File | Status | Subsystem | Exists | Staging/use evidence; current runtime call |
| --- | --- | --- | --- | --- |
| `AndroidDiscoveryHost.cs` | support | progression | yes | `scripts/lab/whole_catalog.py:1069` (list), `scripts/lab/whole_catalog.py:1070` (copy) |
| `AndroidLifecycleHost.cs` | support | session | yes | Retained `Assets/Editor` file; no tracked copy site found; staging provenance unclear; exact-editor `Run` fixture at `tools/catalog/AndroidLifecycleHost.cs:24` |
| `AndroidProfileHost.cs` | support | progression | yes | Retained `Assets/Editor` file; no tracked copy site found; staging provenance unclear; exact-editor `Run` fixture at `tools/catalog/AndroidProfileHost.cs:18` |
| `AndroidProgressionHost.cs` | support | progression | yes | `scripts/lab/whole_catalog.py:1069` (list), `scripts/lab/whole_catalog.py:1070` (copy) |
| `ExportCatalog.cs.txt` | support | catalog/resources | no | MCP code template at `scripts/lab/whole_catalog.py:377` via `scripts/lab/whole_catalog.py:380` (read), `scripts/lab/whole_catalog.py:410` (execute) |
| `ExportRuntimeContracts.cs.txt` | support | catalog/resources | no | MCP code template at `scripts/lab/whole_catalog.py:427` via `scripts/lab/whole_catalog.py:380` (read), `scripts/lab/whole_catalog.py:410` (execute) |
| `StartWholeCatalog.cs.txt` | support | catalog/resources | no | MCP code template at `scripts/lab/whole_catalog.py:843` via `scripts/lab/whole_catalog.py:380` (read), `scripts/lab/whole_catalog.py:410` (execute) |
| `ValidateWholeCatalog.cs.txt` | support | catalog/resources | no | MCP code template at `scripts/lab/whole_catalog.py:829` via `scripts/lab/whole_catalog.py:380` (read), `scripts/lab/whole_catalog.py:410` (execute) |
| `WholeCatalogBuild.cs` | support | catalog/resources | yes | `scripts/lab/whole_catalog.py:1102` |
| `WholeCatalogHost.cs` | support | catalog/resources | yes | `scripts/lab/whole_catalog.py:820` |

A counts: **current 94**, **support 26**, **historical 15**; **135 files**. Correction on review: nine files Codex first marked support are staged only by `scene_runtime.py`/`nova_bridge.py` preparation functions that no current command calls, so they are historical.

## B. `scripts/lab` modules

For host modules, **current** means a direct implementation/dispatcher of an
operation documented in `README.md` or the integration document's “Reusable fixes
and commands”. **support** means a transitive utility, constant provider, MCP
subprocess or host-test dependency of those routes. **historical** means neither
route; an old action can still be callable. `./dev test` is documented, so imports
from its test discovery (`scripts/lab/main.py:11`) count as support, even when the
module's prototype action is historical. Imported constants do not make every
function in the provider module current.

All filenames in this table are relative to `scripts/lab/`.

| Module | Status | One-line purpose | Route evidence |
| --- | --- | --- | --- |
| `animation_bindings.py` | support | Repair unique original animation curve bindings. | `scripts/lab/whole_catalog.py:1018` |
| `body_visual_map.py` | support | Generate body/health visual reference maps. | `scripts/lab/whole_catalog.py:1019` |
| `boundaries.py` | support | Assembly probe command helper; older dependency/closure experiments coexist. | `scripts/lab/whole_catalog.py:565` (`probe_tool` only) |
| `build.py` | current | Preflight, exact-editor dispatch, APK cache and staged-source identity guards. | `scripts/lab/main.py:488` / `scripts/lab/main.py:491` / `scripts/lab/main.py:494` |
| `common.py` | support | Repository/work paths, config, hashes, subprocess and JSON helpers. | `scripts/lab/main.py:2` |
| `common_assets_map.py` | support | Generate original global common-asset field map. | `scripts/lab/whole_catalog.py:1020` |
| `composition_migration.py` | current | Rebase composition assets and import missing current dependencies. | `scripts/lab/main.py:28` / `scripts/lab/main.py:31` |
| `debug_acceleration.py` | support | Validate explicit diagnostic assists and acceptance labels. | `test` discovery → `tests/test_debug_acceleration.py:6` |
| `device.py` | current | Owned-device storage, install, payload sync, launch and evidence collection. | `scripts/lab/main.py:497` |
| `editor.py` | support | Pinned MCP editor subprocess client. | `scripts/lab/build.py:65` |
| `experiments.py` | historical | Early recompile, middleware, references and reconstruction reports. | Undocumented action `recompile` at `scripts/lab/main.py:462` |
| `graphics.py` | current | Inventory original bundle graphics metadata. | `scripts/lab/main.py:21` |
| `health.py` | current | Toolchain/input/dependency health report. | `scripts/lab/main.py:12` |
| `input_migration.py` | support | Compare and gate updated input surfaces. | `test` discovery → `tests/test_input_migration.py:8` |
| `integrated_moon.py` | historical | Stage Moon actors, mission, pillars, escape and content. | `scripts/lab/nova_bridge.py:81` (undocumented Nova preparation) |
| `integrated_objective.py` | support | Stage teleporter support; current path uses optional-content sanitization. | `scripts/lab/composition_migration.py:174` (`sanitize_optional_content`) |
| `integrated_results.py` | historical | Stage original ending assets and result contracts. | `scripts/lab/nova_bridge.py:94` (undocumented Nova preparation) |
| `inventory.py` | current | Inventory legitimate input and drift. | `scripts/lab/main.py:15` |
| `lifecycle.py` | historical | Early storage/install/run lifecycle exercise. | Undocumented action `storage-lifecycle` at `scripts/lab/main.py:470` |
| `main.py` | current | Parse ./dev commands and dispatch module functions. | `dev:6` → `scripts/lab/main.py:3` |
| `moon_scene.py` | historical | Restore source Moon pillar, gravity and escape scene contracts. | `scripts/lab/integrated_moon.py:96` (undocumented Moon preparation) |
| `nova_bridge.py` | support | Prepare/run earlier integrated Nova spine; pure mapping/error helpers remain tested. | `test` discovery → `tests/test_nova_bridge_evidence.py:5` |
| `nova_input.py` | historical | Observe raw device input and capture mappings. | Undocumented action `nova-input-prepare` at `scripts/lab/main.py:198` |
| `prepare.py` | historical | Create the early SimpleJSON/mesh/Windows-shader lab project. | `scripts/lab/main.py:480` (undocumented fallback) |
| `presentation.py` | historical | Build and optionally sync separate presentation payloads. | Undocumented action `presentation-payload` at `scripts/lab/main.py:87` |
| `primary_fire.py` | historical | Prepare/run the bounded primary-fire experiment. | Undocumented action `primary-fire-prepare` at `scripts/lab/main.py:90` |
| `recovery.py` | current | Decompile accepted assemblies, export content and wire reconstruction editor. | `scripts/lab/main.py:18` |
| `rewired_trial.py` | support | Guarded licensed-SDK inventory/controller experiment helpers. | `test` discovery → `tests/test_rewired_trial_safety.py:15` |
| `scene_closure.py` | support | GUID dependency closure; current path imports REFERENCE regex. | `scripts/lab/whole_catalog.py:3` (`REFERENCE` only) |
| `scene_runtime.py` | support | Earlier scene/body/movement experiments; acceptance helpers remain tested. | `test` discovery → `tests/test_scene_acceptance.py:8` |
| `serialization_rebase.py` | support | Rebase serialized identities/hierarchies; current path uses scene contracts. | `scripts/lab/composition_migration.py:61` |
| `shader_deferred.py` | support | Generate deferred shaders and render state. | `test` discovery → `tests/test_shader_bindings.py:149` |
| `shader_materials.py` | support | Generate material-specific native shader variants. | `test` discovery → `tests/test_shader_metadata.py:8` |
| `shader_programs.py` | support | Select/translate native shader programs. | `test` discovery → `tests/test_shader_bindings.py:8` |
| `shader_recovery.py` | support | Pinned shader recovery metadata and early extraction. | `tests/test_shader_metadata.py:8` → `scripts/lab/shader_materials.py:7` (`PINS`) |
| `shader_segments.py` | support | Read native shader segments, variants and layouts. | `test` discovery → `tests/test_shader_bindings.py:7` |
| `shader_source.py` | support | Bind recovered HLSL and generate source. | `test` discovery → `tests/test_shader_bindings.py:6` |
| `shader_tessellation.py` | support | Translate measured hull/domain program paths. | `test` discovery → `tests/test_shader_bindings.py:211` |
| `source_reflections.py` | historical | Extract source reflection probe/texture mappings. | `scripts/lab/presentation.py:40` (undocumented presentation action) |
| `source_scene_candidate.py` | support | Scene identity table for current stage contexts; candidate staging action is historical. | `scripts/lab/whole_catalog.py:953` (`SCENES` only) |
| `stage_variants.py` | support | Stage variant scenes; graph-root helper remains tested. | `test` discovery → `tests/test_stage_variant_graph_roots.py:8` |
| `whole_catalog.py` | current | Whole-content prepare/host/contracts/build/device integration. | `scripts/lab/main.py:51` through `scripts/lab/main.py:74` |
| `wwise_bank_index.py` | support | Index accepted bank/media graph and optional decoder verification. | `test` discovery → `tests/test_wwise_bank_index.py:8` |

B counts: **current 9**, **support 24**, **historical 10**; **43 modules**.

## C. `prototype` actions

Only literal actions used in `README.md` or the integration document's “Reusable
fixes and commands” are **current**. This is documentation reachability, not a
judgment that an undocumented operation is obsolete or safe to delete. The
function column preserves shared dispatch; arguments differ between actions.

### Current

| Action | Module function | Dispatch site |
| --- | --- | --- |
| `composition-update-stage` | `composition_migration.stage` | `scripts/lab/main.py:28` |
| `composition-update-dependencies` | `composition_migration.stage_missing_sources` | `scripts/lab/main.py:31` |
| `whole-catalog-contracts` | `whole_catalog.contracts` | `scripts/lab/main.py:51` |
| `whole-catalog-prepare` | `whole_catalog.prepare_integration` | `scripts/lab/main.py:54` |
| `whole-catalog-host` | `whole_catalog.host_integration` | `scripts/lab/main.py:57` |
| `whole-catalog-host-providers` | `whole_catalog.host_providers` | `scripts/lab/main.py:60` |
| `whole-catalog-repair-bindings` | `whole_catalog.repair_root_bindings` | `scripts/lab/main.py:63` |
| `whole-catalog-build` | `whole_catalog.build_integration` | `scripts/lab/main.py:66` |
| `whole-catalog-code-build` | `whole_catalog.build_integration` (`code_only=True`) | `scripts/lab/main.py:69` |
| `whole-catalog-run` | `whole_catalog.run_integration` | `scripts/lab/main.py:72` |

### Historical

Every action in each row has status **historical**. Comma-separated action names
share the indicated module function, with action-specific flags/cases.

| Actions | Module function | Dispatch sites in `scripts/lab/main.py` |
| --- | --- | --- |
| `input-update-check` | `input_migration.check_update` | 25 |
| `stage-variants` | `stage_variants.stage` | 34 |
| `source-scene-prepare` | `source_scene_candidate.prepare + source_scene_candidate.stage_unavailable_audio` | 37 |
| `whole-catalog-audit` | `whole_catalog.audit` | 42 |
| `whole-catalog-native` | `whole_catalog.native_inventory` | 45 |
| `whole-catalog-reconcile` | `whole_catalog.reconcile` | 48 |
| `shader-recovery` | `shader_recovery.recover` | 75 |
| `shader-source` | `shader_source.generate` | 78 |
| `shader-source-deferred` | `shader_deferred.generate` | 81 |
| `shader-source-materials` | `shader_materials.generate` | 84 |
| `presentation-payload`, `stage-presentation-payload`, `recovered-presentation-payload` | `presentation.build_payload` | 87 |
| `primary-fire-prepare` | `primary_fire.prepare` | 90 |
| `primary-fire-run` | `primary_fire.run` | 93 |
| `steam-exception-prepare` | `scene_runtime.steam_exception_prepare` | 96 |
| `steam-boundary-prepare` | `scene_runtime.steam_boundary_prepare` | 99 |
| `profile-binding-prepare` | `scene_runtime.profile_binding_prepare` | 102 |
| `audio-guard-prepare` | `scene_runtime.audio_guard_prepare` | 105 |
| `audio-native-prepare`, `audio-assets-prepare` | `scene_runtime.audio_assets_prepare` | 108, 111 |
| `audio-bank-index` | `wwise_bank_index.index` | 114 |
| `startup-integration-prepare`, `startup-ngss-prepare`, `startup-volume-order-prepare`, `startup-volume-prepare`, `startup-fps-prepare`, `startup-interpolation-prepare`, `startup-textures-prepare`, `startup-application-prepare`, `startup-scene-prepare`, `startup-prepare` | `scene_runtime.startup_prepare` | 117, 120, 123, 126, 129, 132, 135, 138, 141, 144 |
| `startup-run`, `material-render-verify`, `controller-run`, `scene-run` | `scene_runtime.scene_run` | 147, 153, 417, 432 |
| `skin-apply-prepare` | `scene_runtime.skin_apply_prepare` | 150 |
| `grounded-motion-retry`, `barrier-init-run`, `barrier-lifecycle-run`, `spawn-automatic-skill-primary-run`, `spawn-automatic-skill-secondary-run`, `spawn-automatic-skill-utility-run`, `spawn-automatic-skill-special-run`, `spawn-automatic-model-motion-run`, `spawn-automatic-model-reverse-run`, `spawn-automatic-model-aim-run`, `spawn-automatic-direction-motion-run`, `spawn-automatic-direction-reverse-run`, `spawn-automatic-direction-aim-run`, `spawn-automatic-barrier-run`, `spawn-automatic-body-ground-run`, `spawn-automatic-ground-run`, `spawn-automatic-motor-run`, `body-buffs-methods-run`, `movement-batch-run`, `movement-batch-retry` | `scene_runtime.movement_batch_run` | 156, 167, 206, 214, 222, 230, 238, 246, 255, 339, 393, 396 |
| `jump-input-retry-prepare`, `body-root-awake-prepare`, `reciprocal-spawn-observe-prepare`, `reciprocal-spawn-prepare`, `master-tracker-prepare`, `recovered-body-serialization-retry-prepare`, `recovered-serialization-prepare`, `state-catalog-prepare`, `recovered-client-prepare`, `local-ownership-prepare`, `body-jump-prepare`, `body-grounded-prepare`, `body-landing-retry-prepare`, `body-gravity-prepare`, `jump-input-prepare`, `grounded-state-prepare` | `scene_runtime.grounded_state_prepare` | 159, 288, 291, 294, 297, 300, 303, 306, 309, 315, 318, 324, 327, 330, 366, 369 |
| `barrier-effect-prepare`, `barrier-completion-prepare`, `barrier-lifecycle-prepare`, `spawn-automatic-skill-prepare`, `spawn-automatic-model-prepare`, `spawn-automatic-direction-prepare`, `spawn-automatic-health-prepare`, `spawn-automatic-body-prepare`, `spawn-automatic-gravity-prepare`, `spawn-automatic-prepare`, `spawn-automatic-motion-prepare`, `spawn-main-prepare`, `teleport-material-prepare`, `spawn-state-exit-prepare`, `spawn-state-prepare`, `body-start-loadout-prepare` | `scene_runtime.body_start_loadout_prepare` | 162, 201, 209, 217, 225, 233, 241, 249, 258, 261, 264, 267, 270 |
| `rewired-trial-inventory` | `rewired_trial.inventory` | 170 |
| `rewired-trial-run` | `rewired_trial.controller_run` | 170 |
| `rewired-platform-prepare`, `local-ownership-retry-prepare`, `motor-wall-prepare`, `motor-integration-prepare`, `kinematic-batch-prepare`, `movement-batch-prepare` | `scene_runtime.movement_batch_prepare` | 173, 312, 381, 384, 387, 390 |
| `nova-whole-game-prepare`, `nova-director-batch-prepare`, `nova-run-clock-prepare`, `nova-barrel-prepare`, `nova-pickup-prepare`, `nova-money-cost-prepare`, `nova-active-client-prepare`, `nova-interaction-selection-prepare`, `nova-client-coin-prepare`, `nova-input-barrel-prepare`, `nova-chest-drop-table-prepare`, `nova-chest-purchase-prepare`, `nova-pickup-droplet-load-prepare`, `nova-pickup-droplet-flight-prepare`, `nova-pickup-droplet-collision-prepare`, `nova-default-pickup-prepare`, `nova-chest-ejection-prepare` | `nova_bridge.prepare_spine` | 176 |
| `nova-bridge-prepare` | `nova_bridge.prepare` | 176 |
| `nova-bridge-raw-run`, `nova-bridge-raw-retry`, `nova-bridge-commando-run` | `nova_bridge.run_probe` | 176 |
| `nova-bridge-bind` | `nova_bridge.bind` | 176 |
| `nova-input-prepare`, `nova-input-capture` | `nova_input.observe` | 198 |
| `body-start-catalog-prepare`, `body-catalog-prepare`, `body-start-boundary-prepare`, `automatic-spawn-prepare`, `body-root-order-prepare` | `scene_runtime.body_root_order_prepare` | 273, 276, 279, 282, 285 |
| `body-visual-prepare` | `scene_runtime.recovered_visual_prepare` | 321 |
| `body-state-prepare`, `body-level-motor-prepare`, `body-buffs-reference-prepare`, `body-stats-buffs-prepare`, `body-stats-motor-prepare`, `body-stats-retry-prepare`, `body-stats-prepare`, `body-adoption-prepare`, `body-network-prepare`, `body-lifecycle-prepare`, `gravity-state-prepare`, `landing-context-prepare`, `landing-batch-prepare` | `scene_runtime.landing_batch_prepare` | 333, 336, 342, 345, 348, 351, 354, 357, 360, 363, 372, 375, 378 |
| `direction-prepare` | `scene_runtime.direction_prepare` | 399 |
| `state-tick-prepare` | `scene_runtime.state_tick_prepare` | 402 |
| `material-render-prepare` | `scene_runtime.material_render_prepare` | 405 |
| `skin-prepare` | `scene_runtime.skin_prepare` | 408 |
| `avatar-prepare` | `scene_runtime.avatar_prepare` | 411 |
| `controller-prepare` | `scene_runtime.controller_prepare` | 414 |
| `pose-prepare` | `scene_runtime.pose_prepare` | 420 |
| `prefab-bind` | `scene_runtime.prefab_bind` | 423 |
| `prefab-prepare`, `scene-prepare` | `scene_runtime.scene_prepare` | 426, 435 |
| `scene-arm` | `scene_runtime.scene_arm` | 429 |
| `scene-closure` | `scene_closure.scene_closure` | 438 |
| `dependency-boundaries` | `boundaries.dependency_boundaries` | 441 |
| `rewired-original` | `boundaries.rewired_original` | 444 |
| `collections-runtime` | `boundaries.collections_runtime` | 447 |
| `ror2-slice`, `original-closure-runtime` | `boundaries.ror2_slice` | 450, 453 |
| `original-closure-prepare` | `boundaries.original_closure_prepare` | 456 |
| `original-closure-build` | `boundaries.original_closure_build` | 459 |
| `recompile` | `experiments.recompile` | 462 |
| `middleware` | `experiments.middleware` | 465 |
| `repair-reconstruction` | `subprocess.call → patches/reconstruction-ambiguities.py (no lab module function)` | 468 |
| `storage-lifecycle` | `lifecycle.lifecycle` | 470 |
| `references` | `experiments.references` | 473 |
| `reconstruction` | `experiments.reconstruction_report` | 476 |
| `inspect` (default), any unmatched action | `prepare.prepare` | 5, 479, 480, 481 |

C counts: **current 10**, **historical 165 explicit names**; **175 explicitly matched actions**. Including the named default `inspect`: **historical 166**, **176 named actions**. There is no `support` action status. Unknown strings also take the fallback; they are not an enumerable action set.

## D. Playable-spine runtime sequence and ownership

### Entry and dispatch

The source establishes the following order inside this component. Ordering against
unrelated Unity runtime initializers/components is **unclear**; no execution-order
attribute on `MovementBatchProbe` resolves it. It has **no `Awake`, `OnDestroy`, or
`OnApplicationQuit` method in any tracked partial**. Original game components do
have manually invoked callbacks as shown below.

| Order | Method/call | Source and conditions |
| --- | --- | --- |
| 1 | `Init` (`AfterSceneLoad`) → `AddComponent<PortSession>` | `tools/unity/runtime/session/PortSession.cs:47`; only if `Resources/MovementBatchProbe` exists. No probe `Awake` follows in tracked source. |
| 2 | Coroutine `Start` | `tools/unity/runtime/session/PortSession.cs:48`; a whole-catalog selection file causes immediate `yield break` at line 49. |
| 3 | Wait **8 s** | `tools/unity/runtime/session/PortSession.cs:50`; `WaitForSeconds`, hence scaled Unity time. Then load resource config and optional movement selection at lines 51–52; mismatched attempt exits. |
| 4 | Ordinary launch selection | `tools/unity/runtime/session/PortSession.cs:54`; require `launchPlayableSlice`, wait in 1 s intervals for an attempt-matching Nova mapping, then select `body-state-spawn-state-auto-nova-spine` with `freePlay=true` at line 58. Explicit movement selection skips this mapping wait. |
| 5 | Session/presentation setup | `CollectPriorSessionGarbage` → `ObserveSessionResources("before-presentation")` → `AndroidMaterialPresentation.Begin` (`tools/unity/runtime/session/PortSession.cs:64`), then save started report at line 65. |
| 6 | Catalog preparation | `RegisterBodyCatalog` (`tools/unity/runtime/session/PortSession.cs:68`) → optional `PrepareTeleportMaterial` (line 71) → optional `PrepareBarrierEffect` (line 75). The spine satisfies `catalogFixture` at line 66. These enumerators are driven with error capture. |
| 7 | Offline menu gate | `AwaitOfflineRunStart` (`tools/unity/runtime/session/PortSession.cs:83`), detailed below; this is **before** dispatch. |
| 8 | `RunSelectedProbe(catalogFixture)` → switch case → `BodyLifecycle` | `tools/unity/runtime/session/PortSession.cs:84`, `tools/unity/runtime/session/PortSession.cs:102`, `tools/unity/runtime/session/PortSession.cs:104`. The spine shares one large arm with older body experiments. The driver catches execution exceptions and records first failure at line 85. |

`RegisterBodyCatalog` initializes original handling presets (once) and calls
`WholeCatalogComposed.Prepare` before the empty Addressables bootstrap
(`tools/unity/runtime/catalog/BodyCatalogBoundary.cs:94`, `tools/unity/runtime/catalog/BodyCatalogBoundary.cs:96`).
It loads the character bundle and optional objective bundle preload at lines
121–122, sets body prefabs at line 133, then installs converted locations at line
144. This is distinct from the optional `WholeCatalogBootstrap` registration scan.

### `AwaitOfflineRunStart`

The implementation is `tools/unity/runtime/session/OfflineApplicationBoundary.cs:34`:

1. If integrated world and results are enabled, `PrepareOfflineSettings` (line 35).
2. Default survivor from pending selection (line 36). Skip the menu unless the
   session allows it and both integration flags are set; `skipOfflineMenu` and a
   developer survivor override also skip it (line 38).
3. Reset unlock preview, compute ordinary selectable survivors and visible roster
   (line 39), then read `AndroidOfflineProfile.PreviewLoadout` (line 42).
4. Validate mapping, `PrepareRecoveredMenu`, expose menu, save (lines 45–46).
5. Yield until `offlineStartSelected` (line 47). The existing Unity `Update` calls
   `ObserveOfflineApplicationInput` (`tools/unity/runtime/world/RunClockBoundary.cs:68`), while
   `OnGUI` calls `DrawOfflineStart` (`tools/unity/runtime/input/NovaInputBoundary.cs:33`).
6. `CleanupRecoveredMenu`, clear roster/menu state, persist pending survivor,
   `SelectedPlayerPrefab`, restore phase and save (line 48).

### Main calls after dispatch, in order

Flags below describe source branches, not inspected generated configuration.
The integrated composition is statically traceable; exact enabled branches in the
installed APK are **unclear** under the filename-only restriction.

| Order | Method/calls in execution order | Call-site evidence |
| --- | --- | --- |
| 1 | `BodyLifecycle`: empty buff catalog → `SelectedPlayerPrefab` → definition-family helpers → `PrepareAdoption` | `tools/unity/runtime/session/PortSession.cs:321`, `tools/unity/runtime/session/PortSession.cs:324`, `tools/unity/runtime/session/PortSession.cs:326`, `tools/unity/runtime/session/PortSession.cs:329` |
| 2 | Instantiate inactive selected body → original body `Awake` → original motor `Awake` | `tools/unity/runtime/session/PortSession.cs:330`, `tools/unity/runtime/session/PortSession.cs:331`, `tools/unity/runtime/session/PortSession.cs:338` |
| 3 | `SpawnRecovered` body → inventory/master `Awake` → `SpawnRecovered` master → bind body/master/inventory → `InitializeSkills` → `OriginalStats` | `tools/unity/runtime/session/PortSession.cs:349`, `tools/unity/runtime/session/PortSession.cs:351`, `tools/unity/runtime/session/PortSession.cs:356`, `tools/unity/runtime/session/PortSession.cs:358` |
| 4 | `OriginalStats`: equipment/artifact catalogs → landing event context → whole definition fields, `PrepareWholeDroneCatalog`, `PrepareProjectiles`, `RegisterOriginalSkins` | `tools/unity/runtime/session/PortSession.cs:443`, `tools/unity/runtime/session/PortSession.cs:445`, `tools/unity/runtime/session/PortSession.cs:447`, `tools/unity/runtime/session/PortSession.cs:453`, `tools/unity/runtime/session/PortSession.cs:454`, `tools/unity/runtime/session/PortSession.cs:455` |
| 5 | `CreateTeamContext` → instantiate original inactive `ClassicRun` → original Run `OnEnable`, artifact manager `Awake`/`OnEnable` → health `Awake` → `RecalculateStats` → `SpawnBoundary` | `tools/unity/runtime/session/PortSession.cs:458`, `tools/unity/runtime/session/PortSession.cs:460`, `tools/unity/runtime/session/PortSession.cs:470`, `tools/unity/runtime/session/PortSession.cs:471`, `tools/unity/runtime/session/PortSession.cs:483` |
| 6 | `SpawnBoundary` drives `SpawnBoundaryCore` → `PrepareStageGeometry` → `PrepareSpawnStateCatalog` → `ApplyAndroidProfileLoadoutBeforeSpawn` → original `master.SpawnBody` → `AutomaticSpawnBoundary` | `tools/unity/runtime/session/PortSession.cs:498`, `tools/unity/runtime/session/PortSession.cs:531`, `tools/unity/runtime/session/PortSession.cs:533`, `tools/unity/runtime/session/PortSession.cs:534`, `tools/unity/runtime/session/PortSession.cs:535`, `tools/unity/runtime/session/PortSession.cs:541` |
| 7 | `PrepareSpawnStateCatalog`: `CaptureWholeStateOwnership` → `PrepareSpineConfigs`, optional enemy/objective configs → `BuildStateCatalogRoutine` → apply selected configuration adaptations → `ApplySpineExclusions` / `EnemyExclusions` | `tools/unity/runtime/catalog/SpawnStateBoundary.cs:65`, `tools/unity/runtime/catalog/SpawnStateBoundary.cs:69`, `tools/unity/runtime/catalog/SpawnStateBoundary.cs:71`, `tools/unity/runtime/catalog/SpawnStateBoundary.cs:72`, `tools/unity/runtime/catalog/SpawnStateBoundary.cs:80`, `tools/unity/runtime/catalog/SpawnStateBoundary.cs:83`, `tools/unity/runtime/catalog/SpawnStateBoundary.cs:84` |
| 8 | `AutomaticSpawnBoundary`: disable root behaviours → `PrepareAutomaticModel` → enable original body/motor/state/direction/model/skill callbacks → activate body → yield one frame for original `Start` callbacks | `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:30`, `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:31`, `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:32`, `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:33`, `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:37`. Relative order of original component `Start` callbacks is **unclear** here. |
| 9 | Observe timed `SpawnTeleporterState` exit and overlays → enable original health → `NovaInputBoundary` | `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:48`, `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:62`, `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:66`. Spine bypasses isolated `AutomaticHealthBoundary`, `AutomaticDirectionBoundary` and `AutomaticGroundBoundary` routines. |
| 10 | `NovaInputBoundary`: validate physical mapping/authority → enable grounded solving/gravity → wait for landing → construct `NovaDiagnosticDisplay` | `tools/unity/runtime/input/NovaInputBoundary.cs:45`, `tools/unity/runtime/input/NovaInputBoundary.cs:47`, `tools/unity/runtime/input/NovaInputBoundary.cs:56`, `tools/unity/runtime/input/NovaInputBoundary.cs:57`, `tools/unity/runtime/input/NovaInputBoundary.cs:61` |
| 11 | `PrepareCombatScene` → `PrepareRunSceneContext` → `PreparePlayerDefeat` → `PrepareEnemy` → `PrepareIntegratedWorld` | `tools/unity/runtime/input/NovaInputBoundary.cs:63`, `tools/unity/runtime/input/NovaInputBoundary.cs:64`, `tools/unity/runtime/input/NovaInputBoundary.cs:65`, `tools/unity/runtime/input/NovaInputBoundary.cs:66`, `tools/unity/runtime/input/NovaInputBoundary.cs:67` (each conditional on its field) |
| 12 | `PrepareIntegratedWorld`: early hurt/presentation setup → `ConnectActiveBodyClient` → `PrepareWholeRunAvailability` → `PrepareWholeModelDisplayRules` → pickup/misc catalogs → `PrepareIntegratedResults` | `tools/unity/runtime/world/IntegratedWorldBoundary.cs:282`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:283`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:286`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:287`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:295`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:306`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:310` |
| 13 | Results: install `AndroidProfileSaveSystem` → statistics/ending/XML/ledger setup → `PrepareAndroidProfile` → rule metadata → ending template and listeners | `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:121`, `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:133`, `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:164`, `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:165`, `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:168`, `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:171` |
| 14 | Profile: survivor catalog → `AndroidProgressionBoundary.Prepare` → rule metadata → redirect lease → native default profile → `AndroidOfflineProfile` → reconcile/confirm loadout → event and discovery subscriptions | `tools/unity/runtime/progression/AndroidProfileBoundary.cs:93`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:95`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:103`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:106`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:110`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:111`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:113`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:117`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:131` |
| 15 | World continues: cost/droplet/messages → equipment/item displays → layout → `PrepareTeleporterWorld` → original visual/common references → transmutation → item behaviours/commerce → `PopulateWholeStage` → `BeginOriginalStage` → `PlaceGoldshoresDiagnosticShrine` → HUD | `tools/unity/runtime/world/IntegratedWorldBoundary.cs:337`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:348`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:355`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:362`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:379`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:380`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:381`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:382`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:383`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:384`, `tools/unity/runtime/world/IntegratedWorldBoundary.cs:385` |
| 16 | Third-person camera → add/configure `NovaInputBridge` → `PrepareDebugAcceleration` → set frame request/report → end-of-frame loop | `tools/unity/runtime/input/NovaInputBoundary.cs:70`, `tools/unity/runtime/input/NovaInputBoundary.cs:71`, `tools/unity/runtime/input/NovaInputBoundary.cs:72`, `tools/unity/runtime/input/NovaInputBoundary.cs:75`, `tools/unity/runtime/input/NovaInputBoundary.cs:77` |
| 17 | Each loop: results/abandon/death checks → optional `TransportIntegratedStage` → pause handling/model/aim/overlays → primary/combat/enemy/clock observers → integrated world/results → presentation/save | `tools/unity/runtime/input/NovaInputBoundary.cs:81`, `tools/unity/runtime/input/NovaInputBoundary.cs:82`, `tools/unity/runtime/input/NovaInputBoundary.cs:84`, `tools/unity/runtime/input/NovaInputBoundary.cs:85`, `tools/unity/runtime/input/NovaInputBoundary.cs:92`, `tools/unity/runtime/input/NovaInputBoundary.cs:96`, `tools/unity/runtime/input/NovaInputBoundary.cs:114`, `tools/unity/runtime/input/NovaInputBoundary.cs:120` |

Only IDs ending in `-bringup` enable the input stimulus branches at
`tools/unity/runtime/input/NovaInputBoundary.cs:96` and `tools/unity/runtime/input/NovaInputBoundary.cs:97`.
The exact requested spine ID does not. The component also owns Unity scheduling:
`Update` at `tools/unity/runtime/world/RunClockBoundary.cs:68` drives app input, stage and original
Run/async callbacks; `FixedUpdate` at `tools/unity/runtime/world/AutomaticDirectorBoundary.cs:59`
drives original Run clock, equipment, results and navigation callbacks. Original
body/state/motor/skill callbacks are enabled rather than reimplemented here.

### Normal teardown order

This order follows successful coroutine unwinding. It is **unclear** whether every
nested enumerator is disposed on exception, object destruction or application
quit: most callers manually use `MoveNext` without `using`/`Dispose`. `Start` has
no enclosing `finally`; catalog/menu errors or interrupted execution can skip its
post-run release sequence. Cleanup exceptions can also stop a chained cleanup.
The source therefore does not establish a universal quit-cleanup guarantee.

| Inner → outer | Cleanup order | Evidence |
| --- | --- | --- |
| `NovaInputBoundary` `finally` | `CleanupDebugAcceleration` → `CleanupIntegratedWorld` → `CleanupActiveBodyClient` → `CleanupOriginalMoneyCost` → `CleanupOriginalItemPickup` → conditional `CleanupOriginalDefaultPickup` → `CleanupOriginalBarrel` → `CleanupRunClock` → conditional `CleanupEnemy` → disable/destroy bridge → conditional `CleanupCombatScene` → display `Dispose` → remove jump/landing listeners → restore gravity/trigger/layer/solver state → clear view → restore frame request/sleep timeout | `tools/unity/runtime/input/NovaInputBoundary.cs:143` |
| `CleanupIntegratedWorld` expansion | HUD → results/profile → commerce → transmutation → teleporter/stage → global/body visual references; remove early hurt handler; reset observers/navigation; restore presentation callbacks; disable interaction; destroy pickups/droplets/layout/pause; chest ejection cleanup; coin pool/leases; handlers/options/loot/misc catalogs/droplet source; materials | `tools/unity/runtime/world/IntegratedWorldBoundary.cs:918` through `tools/unity/runtime/world/IntegratedWorldBoundary.cs:943` |
| Results/profile expansion | Results stage listeners → `CleanupAndroidProfile` (event/discovery listeners, pending save, progression `Dispose`, restore profile/redirect/viewable/survivor state) → restore save system → ending controllers/statistics/events/catalogs/relationships/groups/key items | `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:228`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:196`, `tools/unity/runtime/progression/AndroidProfileBoundary.cs:219` |
| Teleporter expansion | boss content → Moon mission/pillars/timers → stage transport → source event listeners → observe support → effect cleanup → support cleanup → objective objects → stage owner → resource/card clones → indicator/TMP leases → locator | `tools/unity/runtime/stage/TeleporterWorldBoundary.cs:588`. `CleanupObjectiveSupport` calls loot cleanup before Moon support and leases (`tools/unity/runtime/stage/TeleporterWorldBoundary.cs:161`); loot cleanup calls proc cleanup → pause cleanup → equipment/displays (`tools/unity/runtime/world/IntegratedWorldBoundary.cs:264`). |
| Enemy expansion | damage/death listeners → destroy enemy master/body/model → director actors → reward hosts/automatic director → restore catalog templates → scene/templates/material/surface | `tools/unity/runtime/world/EnemySpineBoundary.cs:114`, `tools/unity/runtime/world/EnemyRewardBoundary.cs:105` |
| `AutomaticSpawnBoundary` `finally` | deactivate spawned body → unsubscribe motor/body/master/stat observers → neutral input → original weapon state machines `OnDestroy` → body state machine `OnDestroy` → restore gravity/solver → destroy detached model for restart/death | `tools/unity/runtime/world/AutomaticSpawnBoundary.cs:118` |
| `SpawnBoundaryCore` `finally`, then wrapper | unspawn/destroy newly created scene bodies; restore master prefab and original prefab child activation states. Wrapper explicitly disposes core, yields up to 3 frames for deferred body/model destruction, checks release, then rethrows saved failure | `tools/unity/runtime/session/PortSession.cs:543`, `tools/unity/runtime/session/PortSession.cs:506`, `tools/unity/runtime/session/PortSession.cs:509` |
| `OriginalStats` `finally` | original skins → projectile catalog → definition fields → stats listener → original health/team `OnDestroy` → artifact manager `OnDisable`/`OnDestroy` → Run `OnDisable` → run/team hosts → restore artifact/equipment state | `tools/unity/runtime/session/PortSession.cs:490` |
| `BodyLifecycle` `finally` | model subscription → fixture motor/skills/team original `OnDestroy` → inventory listener → unspawn master, original master/inventory `OnDestroy`, inventory fixed disposal → unspawn fixture body → original `OnDisable` if registered → restore definition/buff arrays/maps → `RestoreAdoption` | `tools/unity/runtime/session/PortSession.cs:367` |
| `RunSelectedProbe` `finally` | `CleanupLanding` → destroy obstacle/fixture body/staging → recovered client disconnect/shutdown and server shutdown → client scene shutdown → active-client scene cleanup → reset state catalog if owned → cleanup status/report | `tools/unity/runtime/session/PortSession.cs:107` |
| `Start` post-dispatch | one frame → `VerifyEnemyCleanup` → conditional `VerifyIntegratedWorldCleanup` → `VerifyAutomaticModelDestruction` → `CleanupEnemyRewards` → `CleanupPlayerDeathEffect` → `CleanupBodyCatalog` → `CleanupTeleportMaterial` → `CleanupBarrierEffect` → `CleanupSpawnConfig` → `CleanupStageGeometry` → `AndroidMaterialPresentation.Finish` → successful integrated resource reclamation → complete/save → `RestartWorldAfterCleanup` | `tools/unity/runtime/session/PortSession.cs:87` through `tools/unity/runtime/session/PortSession.cs:99` |
| Reward/provider release | after original Run is gone, return owned effect loans and `AssetAsyncReleaseAllReferences(true)`; restore effect metadata/director assets; release reward assets/provider | `tools/unity/runtime/world/EnemyRewardBoundary.cs:106`, `tools/unity/runtime/world/RunClockBoundary.cs:69` |
| Body/provider release | skins/loadout/templates → body availability/catalog → character bundle unload → objective preload release/text cleanup → `WholeCatalogComposed.Release` (asset cache/locators/families/shared bundle) → Addressables transform restoration | `tools/unity/runtime/catalog/BodyCatalogBoundary.cs:221`, `tools/unity/runtime/catalog/WholeCatalogComposed.cs:103` |
| Optional restart | validate complete cleanup → write completed session → track weak references → add next `MovementBatchProbe` → assign session/menu flags → destroy old host | `tools/unity/runtime/world/IntegratedWorldBoundary.cs:913`; new component starts the same entry sequence, without a probe `Awake`. |

`AndroidPresentationCamera.OnDestroy` disposes profiler recorders and grade material
(`tools/unity/runtime/input/AndroidPresentationCamera.cs:51`) when the display's root destruction
completes. `NovaInputBridge.OnDisable` calls `Neutral`
(`tools/unity/runtime/input/NovaInputBridge.cs:112`). These are component callbacks, not probe
callbacks. Save/trace and catalog-driver `finally` blocks restore temporary report
state and dispose preload stacks (`tools/unity/runtime/session/PortSession.cs:44`,
`tools/unity/runtime/session/PortSession.cs:610`); they are not whole-session teardown.

### Boundary and owner inventory

Most files named `*Boundary.cs` are **partial `MovementBatchProbe`**, sharing its
fields and lifecycle; their filenames are not separate C# owner types. The table
covers every current C# file in A. Setup/teardown names are definition locations;
A supplies caller evidence. Predicate/cleanup-only files are labelled, so their
older experiment setup is not mistaken for playable setup. DTO/report types and
original RoR2/Unity classes are not additional authored owners.

| Actual owner type / partial file | Setup or entry | Teardown / lifetime |
| --- | --- | --- |
| `MovementBatchProbe` — `tools/unity/runtime/session/ActiveClientBoundary.cs` | `ConnectActiveBodyClient` (`tools/unity/runtime/session/ActiveClientBoundary.cs:32`) | `CleanupActiveBodyClient` (`tools/unity/runtime/session/ActiveClientBoundary.cs:68`), `FinishActiveClientSceneCleanup` (`tools/unity/runtime/session/ActiveClientBoundary.cs:73`) |
| `AndroidMaterialPresentation` — `tools/unity/runtime/shaders/AndroidMaterialPresentation.cs` | `Begin` (`tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:13`), `Apply` (`tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:17`) | `Finish` (`tools/unity/runtime/shaders/AndroidMaterialPresentation.cs:84`) |
| `AndroidNativeDeferredPresentation` — `tools/unity/runtime/shaders/AndroidNativeDeferredPresentation.cs` | `Begin` (`tools/unity/runtime/shaders/AndroidNativeDeferredPresentation.cs:21`), `Apply` (`tools/unity/runtime/shaders/AndroidNativeDeferredPresentation.cs:51`) | `Finish` (`tools/unity/runtime/shaders/AndroidNativeDeferredPresentation.cs:71`) |
| `AndroidOfflineProfile` — `tools/unity/runtime/progression/AndroidOfflineProfile.cs` | `AndroidOfflineProfile` (`tools/unity/runtime/progression/AndroidOfflineProfile.cs:24`), `Save` (`tools/unity/runtime/progression/AndroidOfflineProfile.cs:133`) | none; profile/save-system references released by CleanupAndroidProfile |
| `AndroidOfflineSettings` — `tools/unity/runtime/input/AndroidOfflineSettings.cs` | `AndroidOfflineSettings` (`tools/unity/runtime/input/AndroidOfflineSettings.cs:10`), `Save` (`tools/unity/runtime/input/AndroidOfflineSettings.cs:21`) | none; settings object/static values retained across sessions |
| `AndroidPresentationCamera` — `tools/unity/runtime/input/AndroidPresentationCamera.cs` | `Awake` (`tools/unity/runtime/input/AndroidPresentationCamera.cs:14`), `OnEnable` (`tools/unity/runtime/input/AndroidPresentationCamera.cs:15`) | `OnDestroy` (`tools/unity/runtime/input/AndroidPresentationCamera.cs:51`) |
| `MovementBatchProbe` — `tools/unity/runtime/progression/AndroidProfileBoundary.cs` | `PrepareAndroidProfile` (`tools/unity/runtime/progression/AndroidProfileBoundary.cs:82`), `ApplyAndroidProfileLoadoutBeforeSpawn` (`tools/unity/runtime/progression/AndroidProfileBoundary.cs:29`) | `CleanupAndroidProfile` (`tools/unity/runtime/progression/AndroidProfileBoundary.cs:196`) |
| `AndroidProgressionBoundary` — `tools/unity/runtime/progression/AndroidProgressionBoundary.cs` | `Prepare` (`tools/unity/runtime/progression/AndroidProgressionBoundary.cs:80`) | `Dispose` (`tools/unity/runtime/progression/AndroidProgressionBoundary.cs:333`) |
| `AndroidStageTransport` — `tools/unity/runtime/stage/AndroidStageTransport.cs` | `ServerChangeScene` (`tools/unity/runtime/stage/AndroidStageTransport.cs:39`) | external CleanupStageTransport destroys host and clears callback/singleton |
| `MovementBatchProbe` — `tools/unity/runtime/world/AutomaticDirectionBoundary.cs` | `IsAutomaticDirection` (`tools/unity/runtime/world/AutomaticDirectionBoundary.cs:9`) | none; predicate only on spine |
| `MovementBatchProbe` — `tools/unity/runtime/world/AutomaticDirectorBoundary.cs` | `PrepareDirectorAssets` (`tools/unity/runtime/world/AutomaticDirectorBoundary.cs:64`), `SpawnAutomaticEnemy` (`tools/unity/runtime/world/AutomaticDirectorBoundary.cs:81`), `StartOriginalNavigation` (`tools/unity/runtime/world/AutomaticDirectorBoundary.cs:53`) | `CleanupAutomaticDirector` (`tools/unity/runtime/world/AutomaticDirectorBoundary.cs:130`), `ReleaseDirectorAssets` (`tools/unity/runtime/world/AutomaticDirectorBoundary.cs:136`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/AutomaticModelBoundary.cs` | `PrepareAutomaticModel` (`tools/unity/runtime/world/AutomaticModelBoundary.cs:10`), `ObserveAutomaticModelFollow` (`tools/unity/runtime/world/AutomaticModelBoundary.cs:18`) | VerifyAutomaticModelDestruction (observes original ModelLocator destruction) |
| `MovementBatchProbe` — `tools/unity/runtime/world/AutomaticSkillBoundary.cs` | `IsAutomaticSkill` (`tools/unity/runtime/world/AutomaticSkillBoundary.cs:12`), `AutomaticSkillCount` (`tools/unity/runtime/world/AutomaticSkillBoundary.cs:13`) | none; predicates only on spine |
| `MovementBatchProbe` — `tools/unity/runtime/world/AutomaticSpawnBoundary.cs` | `AutomaticSpawnBoundary` (`tools/unity/runtime/world/AutomaticSpawnBoundary.cs:12`) | finally at line 118 |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/BarrelInteractionBoundary.cs` | none; playable path uses cleanup entry | `CleanupOriginalBarrel` (`tools/unity/runtime/commerce/BarrelInteractionBoundary.cs:84`) |
| `MovementBatchProbe` — `tools/unity/runtime/catalog/BarrierEffectBoundary.cs` | `PrepareBarrierEffect` (`tools/unity/runtime/catalog/BarrierEffectBoundary.cs:25`) | `CleanupBarrierEffect` (`tools/unity/runtime/catalog/BarrierEffectBoundary.cs:82`) |
| `MovementBatchProbe` — `tools/unity/runtime/catalog/BodyCatalogBoundary.cs` | `RegisterBodyCatalog` (`tools/unity/runtime/catalog/BodyCatalogBoundary.cs:91`), `RegisterOriginalSkins` (`tools/unity/runtime/catalog/BodyCatalogBoundary.cs:26`) | `CleanupBodyCatalog` (`tools/unity/runtime/catalog/BodyCatalogBoundary.cs:221`), `CleanupOriginalSkins` (`tools/unity/runtime/catalog/BodyCatalogBoundary.cs:41`) |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/ChestEjectionBoundary.cs` | `OwnChestAnimationSources` (`tools/unity/runtime/commerce/ChestEjectionBoundary.cs:25`), `EjectionPickups` (`tools/unity/runtime/commerce/ChestEjectionBoundary.cs:24`), `EjectionDroplets` (`tools/unity/runtime/commerce/ChestEjectionBoundary.cs:23`) | CleanupChestEjection (shared query/cleanup helpers) |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/ChestPurchaseBoundary.cs` | `ChestPurchaseBuffs` (`tools/unity/runtime/commerce/ChestPurchaseBoundary.cs:17`), `ChestPurchaseArtifacts` (`tools/unity/runtime/commerce/ChestPurchaseBoundary.cs:18`) | none; definition-array helpers only |
| `MovementBatchProbe` — `tools/unity/runtime/world/CombatSpineBoundary.cs` | `PrepareCombatConfigs` (`tools/unity/runtime/world/CombatSpineBoundary.cs:29`), `PrepareCombatScene` (`tools/unity/runtime/world/CombatSpineBoundary.cs:62`) | `CleanupCombatScene` (`tools/unity/runtime/world/CombatSpineBoundary.cs:121`), `CleanupCombatConfigs` (`tools/unity/runtime/world/CombatSpineBoundary.cs:127`) |
| `MovementBatchProbe` — `tools/unity/runtime/session/DebugAccelerationBoundary.cs` | `PrepareDebugAcceleration` (`tools/unity/runtime/session/DebugAccelerationBoundary.cs:35`) | `CleanupDebugAcceleration` (`tools/unity/runtime/session/DebugAccelerationBoundary.cs:140`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/DirectorActorBoundary.cs` | `RecordDirectorActor` (`tools/unity/runtime/world/DirectorActorBoundary.cs:29`), `ObserveDirectorActors` (`tools/unity/runtime/world/DirectorActorBoundary.cs:45`) | `CleanupDirectorActors` (`tools/unity/runtime/world/DirectorActorBoundary.cs:88`), `VerifyDirectorActorCleanup` (`tools/unity/runtime/world/DirectorActorBoundary.cs:89`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/EnemyRewardBoundary.cs` | `PrepareEnemyRewards` (`tools/unity/runtime/world/EnemyRewardBoundary.cs:29`), `InitializeRewardRunStreams` (`tools/unity/runtime/world/EnemyRewardBoundary.cs:59`) | `CleanupRewardHosts` (`tools/unity/runtime/world/EnemyRewardBoundary.cs:105`), `CleanupEnemyRewards` (`tools/unity/runtime/world/EnemyRewardBoundary.cs:106`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/EnemySpineBoundary.cs` | `PrepareEnemyConfigs` (`tools/unity/runtime/world/EnemySpineBoundary.cs:44`), `PrepareEnemy` (`tools/unity/runtime/world/EnemySpineBoundary.cs:58`) | `CleanupEnemy` (`tools/unity/runtime/world/EnemySpineBoundary.cs:114`), `CleanupEnemyConfigs` (`tools/unity/runtime/world/EnemySpineBoundary.cs:119`), `VerifyEnemyCleanup` (`tools/unity/runtime/world/EnemySpineBoundary.cs:118`) |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/GenericPickupBoundary.cs` | none; playable path uses cleanup entry | `CleanupOriginalDefaultPickup` (`tools/unity/runtime/commerce/GenericPickupBoundary.cs:42`) |
| `MovementBatchProbe` — `tools/unity/runtime/stage/GoldshoresBoundary.cs` | `IsGoldshoresEntryPortal` (`tools/unity/runtime/stage/GoldshoresBoundary.cs:35`), `PrepareGoldshoresStage` (`tools/unity/runtime/stage/GoldshoresBoundary.cs:42`) | none specific; shared stage/teleporter teardown |
| `MovementBatchProbe` — `tools/unity/runtime/progression/IntegratedResultsBoundary.cs` | `PrepareIntegratedResults` (`tools/unity/runtime/progression/IntegratedResultsBoundary.cs:117`) | `CleanupIntegratedResults` (`tools/unity/runtime/progression/IntegratedResultsBoundary.cs:228`) |
| `MovementBatchProbe` — `tools/unity/runtime/stage/IntegratedStageBoundary.cs` | `PrepareStageTransport` (`tools/unity/runtime/stage/IntegratedStageBoundary.cs:103`), `BeginOriginalStage` (`tools/unity/runtime/stage/IntegratedStageBoundary.cs:116`), `TransportIntegratedStage` (`tools/unity/runtime/stage/IntegratedStageBoundary.cs:156`) | `ReleaseObjectiveStage` (`tools/unity/runtime/stage/IntegratedStageBoundary.cs:138`), `CleanupStageTransport` (`tools/unity/runtime/stage/IntegratedStageBoundary.cs:265`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/IntegratedWorldBoundary.cs` | `PrepareIntegratedWorld` (`tools/unity/runtime/world/IntegratedWorldBoundary.cs:278`) | `CleanupIntegratedWorld` (`tools/unity/runtime/world/IntegratedWorldBoundary.cs:918`), `VerifyIntegratedWorldCleanup` (`tools/unity/runtime/world/IntegratedWorldBoundary.cs:880`) |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/InteractionSelectionBoundary.cs` | `DriverField` (`tools/unity/runtime/commerce/InteractionSelectionBoundary.cs:18`), `InteractionSelectionEquipment` (`tools/unity/runtime/commerce/InteractionSelectionBoundary.cs:17`) | none; reflection/equipment helpers only |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/ItemPickupBoundary.cs` | `DrawItemPickupObservation` (`tools/unity/runtime/commerce/ItemPickupBoundary.cs:19`) | CleanupOriginalItemPickup (shared cleanup entry) |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/MoneyCostBoundary.cs` | none; playable path uses cleanup entry | `CleanupOriginalMoneyCost` (`tools/unity/runtime/commerce/MoneyCostBoundary.cs:34`) |
| `MovementBatchProbe` — `tools/unity/runtime/stage/MoonEscapeBoundary.cs` | `PrepareMoonTimers` (`tools/unity/runtime/stage/MoonEscapeBoundary.cs:11`), `TickMoonTimers` (`tools/unity/runtime/stage/MoonEscapeBoundary.cs:19`) | `StopMoonTimers` (`tools/unity/runtime/stage/MoonEscapeBoundary.cs:24`), `CleanupMoonTimers` (`tools/unity/runtime/stage/MoonEscapeBoundary.cs:30`) |
| `MovementBatchProbe` — `tools/unity/runtime/stage/MoonMissionBoundary.cs` | `PrepareMoonSupport` (`tools/unity/runtime/stage/MoonMissionBoundary.cs:35`), `PrepareMoonWorld` (`tools/unity/runtime/stage/MoonMissionBoundary.cs:127`) | `CleanupMoonMission` (`tools/unity/runtime/stage/MoonMissionBoundary.cs:254`), `CleanupMoonSupport` (`tools/unity/runtime/stage/MoonMissionBoundary.cs:53`) |
| `MovementBatchProbe` — `tools/unity/runtime/presentation/MoonPillarPresentation.cs` | `ObserveMoonPillarMarkers` (`tools/unity/runtime/presentation/MoonPillarPresentation.cs:22`), `ObserveMoonBeacons` (`tools/unity/runtime/presentation/MoonPillarPresentation.cs:40`) | `CleanupMoonPillarPresentation` (`tools/unity/runtime/presentation/MoonPillarPresentation.cs:65`) |
| `PortSession` — `tools/unity/runtime/session/PortSession.cs` | `Init` (`tools/unity/runtime/session/PortSession.cs:47`), `Start` (`tools/unity/runtime/session/PortSession.cs:48`), `RunSelectedProbe` (`tools/unity/runtime/session/PortSession.cs:102`) | nested finally and Start post-dispatch sequence above; no OnDestroy/OnApplicationQuit |
| `NovaDiagnosticDisplay` — `tools/unity/runtime/input/NovaDiagnosticDisplay.cs` | `NovaDiagnosticDisplay` (`tools/unity/runtime/input/NovaDiagnosticDisplay.cs:21`), `ConfigureThirdPerson` (`tools/unity/runtime/input/NovaDiagnosticDisplay.cs:74`) | `Dispose` (`tools/unity/runtime/input/NovaDiagnosticDisplay.cs:76`) |
| `MovementBatchProbe` — `tools/unity/runtime/input/NovaInputBoundary.cs` | `NovaInputBoundary` (`tools/unity/runtime/input/NovaInputBoundary.cs:44`) | finally at line 143 |
| `NovaInputBridge` — `tools/unity/runtime/input/NovaInputBridge.cs` | `Update` (`tools/unity/runtime/input/NovaInputBridge.cs:75`), `FixedUpdate` (`tools/unity/runtime/input/NovaInputBridge.cs:96`) | Neutral,OnDisable; caller destroys component |
| `NovaThirdPersonView` — `tools/unity/runtime/input/NovaThirdPersonView.cs` | `NovaThirdPersonView` (`tools/unity/runtime/input/NovaThirdPersonView.cs:19`) | none; camera lifetime owned by NovaDiagnosticDisplay.Dispose |
| `MovementBatchProbe` — `tools/unity/runtime/session/OfflineApplicationBoundary.cs` | `AwaitOfflineRunStart` (`tools/unity/runtime/session/OfflineApplicationBoundary.cs:34`) | CleanupRecoveredMenu; restart flags consumed by RestartWorldAfterCleanup |
| `MovementBatchProbe` — `tools/unity/runtime/progression/OfflineLoadoutBoundary.cs` | `ResetOfflineLoadoutSelection` (`tools/unity/runtime/progression/OfflineLoadoutBoundary.cs:12`), `DrawOfflineLoadout` (`tools/unity/runtime/progression/OfflineLoadoutBoundary.cs:53`) | none; session/profile owner clears pending loadout state |
| `MovementBatchProbe` — `tools/unity/runtime/session/OfflineRunSeedBoundary.cs` | `SelectOwnedRunSeed` (`tools/unity/runtime/session/OfflineRunSeedBoundary.cs:7`) | none; reward owner restores Run RNG/seed |
| `MovementBatchProbe` — `tools/unity/runtime/input/OfflineSettingsBoundary.cs` | `PrepareOfflineSettings` (`tools/unity/runtime/input/OfflineSettingsBoundary.cs:11`), `ShowOfflineSettings` (`tools/unity/runtime/input/OfflineSettingsBoundary.cs:16`) | `CleanupOfflineSettingsPause` (`tools/unity/runtime/input/OfflineSettingsBoundary.cs:51`) |
| `MovementBatchProbe` — `tools/unity/runtime/catalog/OriginalBodyVisualBoundary.cs` | `PrepareOriginalBodyVisualReferences` (`tools/unity/runtime/catalog/OriginalBodyVisualBoundary.cs:17`) | `CleanupOriginalBodyVisualReferences` (`tools/unity/runtime/catalog/OriginalBodyVisualBoundary.cs:57`) |
| `MovementBatchProbe` — `tools/unity/runtime/catalog/OriginalGlobalCommonAssetsBoundary.cs` | `PrepareOriginalGlobalCommonAssets` (`tools/unity/runtime/catalog/OriginalGlobalCommonAssetsBoundary.cs:18`) | `CleanupOriginalGlobalCommonAssets` (`tools/unity/runtime/catalog/OriginalGlobalCommonAssetsBoundary.cs:55`) |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/PickupDropletFlightBoundary.cs` | `DropletFlightArtifacts` (`tools/unity/runtime/commerce/PickupDropletFlightBoundary.cs:19`) | none; artifact-array helper only |
| `MovementBatchProbe` — `tools/unity/runtime/world/PlayerDefeatBoundary.cs` | `PreparePlayerDefeat` (`tools/unity/runtime/world/PlayerDefeatBoundary.cs:20`), `ObservePlayerDefeat` (`tools/unity/runtime/world/PlayerDefeatBoundary.cs:34`) | `CleanupPlayerDeathEffect` (`tools/unity/runtime/world/PlayerDefeatBoundary.cs:55`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/PrimaryFireBoundary.cs` | `IsPlayableSpine` (`tools/unity/runtime/world/PrimaryFireBoundary.cs:12`), `PrepareSpineConfigs` (`tools/unity/runtime/world/PrimaryFireBoundary.cs:15`), `ObserveSpinePrimary` (`tools/unity/runtime/world/PrimaryFireBoundary.cs:30`) | `CleanupSpineConfig` (`tools/unity/runtime/world/PrimaryFireBoundary.cs:39`) |
| `MovementBatchProbe` — `tools/unity/runtime/presentation/RecoveredHudBoundary.cs` | `PrepareRecoveredText` (`tools/unity/runtime/presentation/RecoveredHudBoundary.cs:10`), `PrepareRecoveredMenu` (`tools/unity/runtime/presentation/RecoveredHudBoundary.cs:21`), `PrepareRecoveredHud` (`tools/unity/runtime/presentation/RecoveredHudBoundary.cs:16`) | `CleanupRecoveredHud` (`tools/unity/runtime/presentation/RecoveredHudBoundary.cs:30`), `CleanupRecoveredMenu` (`tools/unity/runtime/presentation/RecoveredHudBoundary.cs:29`), `CleanupRecoveredText` (`tools/unity/runtime/presentation/RecoveredHudBoundary.cs:15`) |
| `RecoveredHudPresentation` — `tools/unity/runtime/presentation/RecoveredHudFeedback.cs` | `QueuePickup` (`tools/unity/runtime/presentation/RecoveredHudFeedback.cs:21`), `PresentFeedback` (`tools/unity/runtime/presentation/RecoveredHudFeedback.cs:30`) | `CleanupFeedback` (`tools/unity/runtime/presentation/RecoveredHudFeedback.cs:61`) |
| `RecoveredHudPresentation` — `tools/unity/runtime/presentation/RecoveredHudPresentation.cs` | `Validate` (`tools/unity/runtime/presentation/RecoveredHudPresentation.cs:55`), `BindMenu` (`tools/unity/runtime/presentation/RecoveredHudPresentation.cs:62`), `Present` (`tools/unity/runtime/presentation/RecoveredHudPresentation.cs:63`) | external CleanupRecoveredHud/CleanupRecoveredMenu destroy roots |
| `RecoveredPickupPresentation` — `tools/unity/runtime/presentation/RecoveredPickupPresentation.cs` | `Present` (`tools/unity/runtime/presentation/RecoveredPickupPresentation.cs:13`) | external RecoveredHudPresentation.CleanupFeedback destroys notification |
| `MovementBatchProbe` — `tools/unity/runtime/world/RunClockBoundary.cs` | `PrepareRunSceneContext` (`tools/unity/runtime/world/RunClockBoundary.cs:20`), `StartOriginalRunClock` (`tools/unity/runtime/world/RunClockBoundary.cs:47`) | `CleanupRunClock` (`tools/unity/runtime/world/RunClockBoundary.cs:87`), `ReleaseCompletedRunAsyncAssets` (`tools/unity/runtime/world/RunClockBoundary.cs:69`) |
| `MovementBatchProbe` — `tools/unity/runtime/session/SessionResourceBoundary.cs` | `CollectPriorSessionGarbage` (`tools/unity/runtime/session/SessionResourceBoundary.cs:22`), `ObserveSessionResources` (`tools/unity/runtime/session/SessionResourceBoundary.cs:26`) | `TrackCompletedSessionReferences` (`tools/unity/runtime/session/SessionResourceBoundary.cs:21`), `ReclaimCompletedSessionResources` (`tools/unity/runtime/session/SessionResourceBoundary.cs:74`) |
| `SilentProjectileBoundary` — `tools/unity/runtime/world/SilentProjectileBoundary.cs` | `Awake` (`tools/unity/runtime/world/SilentProjectileBoundary.cs:8`) | none; projectile/template owner destroys GameObject |
| `MovementBatchProbe` — `tools/unity/runtime/catalog/SpawnStateBoundary.cs` | `PrepareSpawnStateCatalog` (`tools/unity/runtime/catalog/SpawnStateBoundary.cs:59`) | `CleanupSpawnConfig` (`tools/unity/runtime/catalog/SpawnStateBoundary.cs:90`), `RestoreWholeStateOwnership` (`tools/unity/runtime/catalog/SpawnStateBoundary.cs:53`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/StageBossContentBoundary.cs` | `PrepareStageBossContent` (`tools/unity/runtime/world/StageBossContentBoundary.cs:30`) | `CleanupStageBossInstances` (`tools/unity/runtime/world/StageBossContentBoundary.cs:82`), `CleanupStageBossContent` (`tools/unity/runtime/world/StageBossContentBoundary.cs:88`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/StageCombatDeckBoundary.cs` | `SelectStageCombatDeck` (`tools/unity/runtime/world/StageCombatDeckBoundary.cs:27`), `RecordStageCombatSpawn` (`tools/unity/runtime/world/StageCombatDeckBoundary.cs:53`) | `CleanupStageCombatDecks` (`tools/unity/runtime/world/StageCombatDeckBoundary.cs:74`) |
| `MovementBatchProbe` — `tools/unity/runtime/stage/StageGeometryBoundary.cs` | `PrepareStageGeometry` (`tools/unity/runtime/stage/StageGeometryBoundary.cs:55`), `LoadStageGeometry` (`tools/unity/runtime/stage/StageGeometryBoundary.cs:77`) | `DeactivateSourceGameManager` (`tools/unity/runtime/stage/StageGeometryBoundary.cs:36`), `DeactivateSourceSceneInfo` (`tools/unity/runtime/stage/StageGeometryBoundary.cs:52`), `CleanupStageGeometry` (`tools/unity/runtime/stage/StageGeometryBoundary.cs:241`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/StagePopulationBoundary.cs` | `PrepareStagePopulationSupport` (`tools/unity/runtime/world/StagePopulationBoundary.cs:38`), `PrepareStageBossDeck` (`tools/unity/runtime/world/StagePopulationBoundary.cs:22`) | shared objective support/boss deck teardown; no separate cleanup method |
| `MovementBatchProbe` — `tools/unity/runtime/session/SurvivorSelectionBoundary.cs` | `SelectedPlayerPrefab` (`tools/unity/runtime/session/SurvivorSelectionBoundary.cs:72`), `OrdinarySurvivorChoices` (`tools/unity/runtime/session/SurvivorSelectionBoundary.cs:28`) | none; selection staging root destroyed by RunSelectedProbe finally |
| `MovementBatchProbe` — `tools/unity/runtime/catalog/TeleportMaterialBoundary.cs` | `PrepareTeleportMaterial` (`tools/unity/runtime/catalog/TeleportMaterialBoundary.cs:24`), `ObserveTeleportOverlays` (`tools/unity/runtime/catalog/TeleportMaterialBoundary.cs:49`) | `CleanupTeleportMaterial` (`tools/unity/runtime/catalog/TeleportMaterialBoundary.cs:69`) |
| `MovementBatchProbe` — `tools/unity/runtime/stage/TeleporterWorldBoundary.cs` | `PreloadObjectiveBundle` (`tools/unity/runtime/stage/TeleporterWorldBoundary.cs:52`), `PrepareObjectiveSupport` (`tools/unity/runtime/stage/TeleporterWorldBoundary.cs:117`), `PrepareTeleporterWorld` (`tools/unity/runtime/stage/TeleporterWorldBoundary.cs:331`), `SpawnStageObjective` (`tools/unity/runtime/stage/TeleporterWorldBoundary.cs:349`) | `CleanupTeleporterWorld` (`tools/unity/runtime/stage/TeleporterWorldBoundary.cs:588`), `CleanupObjectiveSupport` (`tools/unity/runtime/stage/TeleporterWorldBoundary.cs:161`), `ReleaseObjectiveBundlePreload` (`tools/unity/runtime/stage/TeleporterWorldBoundary.cs:64`) |
| `WholeCatalogComposed` — `tools/unity/runtime/catalog/WholeCatalogComposed.cs` | `Prepare` (`tools/unity/runtime/catalog/WholeCatalogComposed.cs:81`), `ConfigureLocations` (`tools/unity/runtime/catalog/WholeCatalogComposed.cs:90`) | `Release` (`tools/unity/runtime/catalog/WholeCatalogComposed.cs:103`) |
| `WholeCatalogLoader` — `tools/unity/runtime/catalog/WholeCatalogLoader.cs` | `RegisterLocations` (`tools/unity/runtime/catalog/WholeCatalogLoader.cs:45`) | WholeCatalogComposed.Release removes locator; full Load is optional scan support |
| `MovementBatchProbe` — `tools/unity/runtime/world/WholeInteractableBoundary.cs` | `PopulateWholeStage` (`tools/unity/runtime/world/WholeInteractableBoundary.cs:71`) | `CleanupWholeStageInteractables` (`tools/unity/runtime/world/WholeInteractableBoundary.cs:122`), `CleanupWholeInteractables` (`tools/unity/runtime/world/WholeInteractableBoundary.cs:128`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/WholePopulationBoundary.cs` | `PrepareWholeDroneCatalog` (`tools/unity/runtime/world/WholePopulationBoundary.cs:40`), `PrepareWholeRunAvailability` (`tools/unity/runtime/world/WholePopulationBoundary.cs:51`), `PrepareWholeMasterTemplates` (`tools/unity/runtime/world/WholePopulationBoundary.cs:80`), `SelectWholeStagePool` (`tools/unity/runtime/world/WholePopulationBoundary.cs:146`) | `CleanupWholePopulation` (`tools/unity/runtime/world/WholePopulationBoundary.cs:203`), `CleanupWholeRunAvailability` (`tools/unity/runtime/world/WholePopulationBoundary.cs:73`), `CleanupWholeStagePool` (`tools/unity/runtime/world/WholePopulationBoundary.cs:192`), `CleanupWholePickups` (`tools/unity/runtime/world/WholePopulationBoundary.cs:33`) |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/WorldChestBreadthBoundary.cs` | `WorldChestTypes` (`tools/unity/runtime/commerce/WorldChestBreadthBoundary.cs:13`), `AddWorldChestBreadth` (`tools/unity/runtime/commerce/WorldChestBreadthBoundary.cs:17`) | shared world objects/materials teardown; no separate cleanup method |
| `MovementBatchProbe` — `tools/unity/runtime/commerce/WorldCommerceBoundary.cs` | `PrepareWorldCommerce` (`tools/unity/runtime/commerce/WorldCommerceBoundary.cs:93`) | `CleanupWorldCommerce` (`tools/unity/runtime/commerce/WorldCommerceBoundary.cs:135`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/WorldDotBoundary.cs` | `PrepareWorldDotSupport` (`tools/unity/runtime/world/WorldDotBoundary.cs:45`) | `CleanupWorldDots` (`tools/unity/runtime/world/WorldDotBoundary.cs:85`), `FinishWorldDotCleanup` (`tools/unity/runtime/world/WorldDotBoundary.cs:93`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/WorldEquipmentBoundary.cs` | `PrepareWorldEquipmentSupport` (`tools/unity/runtime/world/WorldEquipmentBoundary.cs:43`), `PrepareWorldEquipment` (`tools/unity/runtime/world/WorldEquipmentBoundary.cs:68`) | `CleanupWorldEquipment` (`tools/unity/runtime/world/WorldEquipmentBoundary.cs:93`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/WorldFlightEquipmentBoundary.cs` | `PrepareFlightEquipmentSource` (`tools/unity/runtime/world/WorldFlightEquipmentBoundary.cs:24`), `ObserveFlightEquipment` (`tools/unity/runtime/world/WorldFlightEquipmentBoundary.cs:36`) | `CleanupFlightEquipment` (`tools/unity/runtime/world/WorldFlightEquipmentBoundary.cs:71`), `VerifyFlightEquipmentCleanup` (`tools/unity/runtime/world/WorldFlightEquipmentBoundary.cs:80`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/WorldHealingItemsBoundary.cs` | `PrepareWorldHealingItemSource` (`tools/unity/runtime/world/WorldHealingItemsBoundary.cs:16`), `ObserveWorldHealingItems` (`tools/unity/runtime/world/WorldHealingItemsBoundary.cs:36`) | `CleanupWorldHealingItems` (`tools/unity/runtime/world/WorldHealingItemsBoundary.cs:57`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/WorldItemBehaviorBoundary.cs` | `PrepareWholeItemBehaviorSupport` (`tools/unity/runtime/world/WorldItemBehaviorBoundary.cs:54`), `PrepareWorldItemBehaviors` (`tools/unity/runtime/world/WorldItemBehaviorBoundary.cs:81`) | `CleanupWorldItemBehaviors` (`tools/unity/runtime/world/WorldItemBehaviorBoundary.cs:156`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/WorldItemDisplayBoundary.cs` | `PrepareWorldItemDisplays` (`tools/unity/runtime/world/WorldItemDisplayBoundary.cs:14`) | `CleanupWorldItemDisplays` (`tools/unity/runtime/world/WorldItemDisplayBoundary.cs:49`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/WorldLegendaryItemsBoundary.cs` | `PrepareWorldLegendaryItemSource` (`tools/unity/runtime/world/WorldLegendaryItemsBoundary.cs:19`), `ObserveWorldLegendaryItems` (`tools/unity/runtime/world/WorldLegendaryItemsBoundary.cs:39`) | `CleanupWorldLegendaryItems` (`tools/unity/runtime/world/WorldLegendaryItemsBoundary.cs:49`) |
| `MovementBatchProbe` — `tools/unity/runtime/world/WorldProcContentBoundary.cs` | `PrepareWorldProcSupport` (`tools/unity/runtime/world/WorldProcContentBoundary.cs:20`) | `CleanupWorldProcContent` (`tools/unity/runtime/world/WorldProcContentBoundary.cs:64`) |
| `MovementBatchProbe.AndroidProfileSaveSystem` — `tools/unity/runtime/progression/AndroidProfileBoundary.cs:14` | constructed/installed by `PrepareIntegratedResults` at `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:121`; native save calls delegate to local profile | `CleanupIntegratedResults` restores prior `PlatformSystems.saveSystem` at `tools/unity/runtime/progression/IntegratedResultsBoundary.cs:234`; no separate Dispose |
| `WholeCatalogComposed.BorrowedBundleProvider` / `BorrowedAssetProvider` — `tools/unity/runtime/catalog/WholeCatalogComposed.cs:42`, `tools/unity/runtime/catalog/WholeCatalogComposed.cs:51` | `ConfigureLocations` registers providers at `tools/unity/runtime/catalog/WholeCatalogComposed.cs:99`; `Provide` borrows existing bundle/asset ownership | provider `Release` at `tools/unity/runtime/catalog/WholeCatalogComposed.cs:49` / `tools/unity/runtime/catalog/WholeCatalogComposed.cs:79`; shared owner `Release` detaches cache/locator at `tools/unity/runtime/catalog/WholeCatalogComposed.cs:103` |
| `WholeCatalogComposed.BorrowedBundle` — `tools/unity/runtime/catalog/WholeCatalogComposed.cs:34` | constructed by provider `Provide` at `tools/unity/runtime/catalog/WholeCatalogComposed.cs:45`; `GetAssetBundle` validates the shared owner at `tools/unity/runtime/catalog/WholeCatalogComposed.cs:36` | no independent unload; shared composed owner releases bundle |
| `AndroidProgressionBoundary.UnavailableActivityDispatch` — `tools/unity/runtime/progression/AndroidProgressionBoundary.cs:46` | temporarily substitutes activity manager during local award evaluation, e.g. `tools/unity/runtime/progression/AndroidProgressionBoundary.cs:225` | `finally` restores prior manager at `tools/unity/runtime/progression/AndroidProgressionBoundary.cs:244`; no initialized service capability |
| `NovaInputBridge.ControllerPresence` — `tools/unity/runtime/input/NovaInputBridge.cs:25` | constructor/`Observe` at `tools/unity/runtime/input/NovaInputBridge.cs:32`, `tools/unity/runtime/input/NovaInputBridge.cs:38`; menu creates one at `tools/unity/runtime/session/OfflineApplicationBoundary.cs:26` | `Suspend` on focus/pause/disable; no external resource or Dispose |

Moon-specific setup/rendering is a reachable conditional branch, not proof that
Moon ran in this audit. Gold Shores and equipment/item families likewise depend
on scene/content selection. No generated configuration or device evidence was
read to resolve those conditions.

## Audit limits and findings

- Two current files have no explicit source-staging list or copy site beyond
  existing-file discovery: `AndroidOfflineSettings.cs` and `WorldDotBoundary.cs`;
  both destinations exist. The shared editor also retains `AndroidProfileHost.cs`,
  `AndroidLifecycleHost.cs`, and `CatalogAddressProbe.cs` without a tracked copy
  site; their initial staging provenance is **unclear**.
- Several files are current only through shared helpers or cleanup; their old
  probe routines are not on the exact spine case. Conversely,
  `WholeCatalogBootstrap.cs` is support: its optional scan excludes ordinary
  movement startup when selected.
- There are 175 explicit prototype action names, above the README's approximate
  160. Only 10 occur in the two specified current command references; the default
  `inspect`/unknown-action fallback still invokes `prepare.prepare`.
- The absent probe quit/destruction hooks and generated-project retention are
  ownership findings. Static
  reachability does not establish a passing build, installed source identity,
  enabled configuration branch or device readiness.

## Verification

Static coverage checks matched all 135 Unity/catalog files and all 43 lab modules;
the action inventory was extracted from the prototype dispatch AST and checked
against the documented commands. Every current C# file has an owner/lifecycle
row. Referenced source files and line bounds were checked. No build/test/editor
or device action ran.

The requested `git add docs/architecture-file-map.md && python3 scripts/audit-public.py`
stopped at Git's read-only index-lock failure. The exact
`violations(path, data)` checks from `scripts/audit-public.py` were then applied
directly to this file and passed. Manual review found authored source-analysis
summaries only, with repository-relative paths and no generated contents or raw
private evidence. Nothing was committed or pushed.
