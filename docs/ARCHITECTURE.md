# Architecture

What runs today, how it is built, and who owns what. The ADRs explain *why*
([ADR-001](ADR-001-port-architecture.md)); this page is the current map. Update it when a
file, owner or pipeline step is added, moved or retired. Results and evidence live in the
[journal](PORTING_JOURNAL.md); the files the build expects under `work/` are listed in
[LOCAL_STATE.md](LOCAL_STATE.md).

Status words used below: **current** (part of the shipped whole-catalog game or the
commands that build it), **support** (editor builders, host fixtures and tooling around the
current path) and **historical** (kept for evidence; not reached by current commands).

## Build pipeline

The user's legitimate PC installation goes in; an ARM64 IL2CPP APK plus an independently
synced content payload comes out. Everything game-derived stays under the ignored `work/`.

| # | Step | Command | Main code | Output under `work/` |
| --- | --- | --- | --- | --- |
| 1 | Accept input | `./dev inspect --full`, then record the ID in `config/accepted-input.json` by hand | `scripts/lab/inventory.py` | `inventory/` |
| 2 | Check before building | `./dev preflight` (also run by `build`) | `scripts/lab/build.py` (`preflight`) | none (refuses on drift) |
| 3 | Decompile and export | `./dev decompile`, `./dev export-project` | `scripts/lab/recovery.py` | `config/reconstruction.json`, exported project |
| 4 | Assembly transforms | no current command; see [debt](#known-structural-debt) | `tools/assembly-transforms/` (`OptionalPresentationGuard`, `WwiseUnavailable`, `AudioGuard`) | transformed `RoR2.dll`, recorded by hash |
| 5 | Compose the project | `./dev prototype --action composition-update-stage`, then `composition-update-dependencies` | `scripts/lab/composition_migration.py` | `lab-project/` |
| 6 | Whole-catalog content | `whole-catalog-prepare` → `-host` → `-repair-bindings` (when recorded) → `-contracts` → `-host-providers` | `scripts/lab/whole_catalog.py`, `tools/catalog/` | `experiments/whole-catalog/<timestamp>/` |
| 7 | Bundles, payload, APK | `whole-catalog-build`, or `whole-catalog-code-build` for a code-only change | `whole_catalog.py` (writes the linker descriptor through `preservation_descriptor`, J506) → `build.py` → exact editor via MCP | APK + payload receipts |
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
The exact editor is started with `./dev editor --target lab --action open`; send it one
mutation at a time. Device acceptance is always the real device, never the editor.

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
| Session and entry | `PortSession`, `OfflineApplicationBoundary`, `SessionResourceBoundary`, `ActiveClientBoundary`, `OfflineRunSeedBoundary`, `SurvivorSelectionBoundary` | nested `OfflineRunSeedSession` (`IDisposable`) **own type** holds the cached seed, session id and source; nested `ActiveClientSession` (`IDisposable`) **own type** holds the owned body/master authority identities and client-scene ownership flag; `activeBodyClient`, `activeBodyOwner`, remaining state and `SessionReport r` (including `r.activeClient` and `r.rewards.seedSource`) stay on the coordinator; nested `OfflineApplicationSession` (`IDisposable`) **own types** hold their files' private state | `Start` → `AwaitOfflineRunStart` → `RunSelectedProbe`; `ConnectActiveBodyClient` → `CleanupActiveBodyClient` (calls `Dispose`: remove master then body authority, disconnect then shut down client) → coordinator server shutdown → `FinishActiveClientSceneCleanup`; active-client owner created on first use and retained after cleanup; `CollectPriorSessionGarbage` → `ReclaimCompletedSessionResources`; `SelectOwnedRunSeed` calls session `SelectOwnedRunSeed` (owner created on first use and retained; session id controls refresh; `Dispose` is a no-op with no teardown call) | `AndroidLifecycleHost.cs` |
| Catalog and resources | `BodyCatalogBoundary`, `WholeCatalogComposed`, `WholeCatalogLoader`, `SpawnStateBoundary`, `OriginalBodyVisualBoundary`, `OriginalGlobalCommonAssetsBoundary`, `TeleportMaterialBoundary`, `BarrierEffectBoundary` | `WholeCatalogComposed` **own type** (static); nested `TeleportMaterialSession` and `BarrierEffectSession` (`IDisposable`) **own types** hold the teleport material (locator, async handle, material, overlays) and the barrier effect (constants, locator, async handle, prefab, effect-slot snapshots, owned material copies); nested `OriginalBodyVisualSession` and `OriginalGlobalCommonAssetsSession` (`IDisposable`) **own types** each hold their native slot snapshots and async handle lists; nested `SpawnStateSession` (`IDisposable`) **own type** holds native state/preload snapshots and spawn delay/sound restoration; `ownsStateCatalog` stays shared on the coordinator; teleport, `r.barrier*` and `r.world` report fields remain coordinator observations; the rest coordinator fields; nested `BodyCatalogSession` (`IDisposable`) **own types** hold their files' private state | `RegisterBodyCatalog` (calls `WholeCatalogComposed.Prepare`) → `CleanupBodyCatalog` (calls `Release`); `PrepareBarrierEffect` → `ObserveBarrierEffect` / `ProbeBarrierEffectLifecycle` → `CleanupBarrierEffect` (awaited coroutine, preserving Start's setup and release order; `Dispose` is a no-op because release requires the coroutine's frame yields); `PrepareOriginalBodyVisualReferences` → `PrepareOriginalGlobalCommonAssets` → `CleanupOriginalGlobalCommonAssets` → `CleanupOriginalBodyVisualReferences` (each cleanup calls its owner's `Dispose`: restore slots, clear snapshots, release handles, clear handles, mark the coordinator report); `PrepareSpawnStateCatalog` forwards to `SpawnStateSession` without changing catalog/config/preload construction order; later `CleanupSpawnConfig` calls `Dispose` (objective, enemy and spine config cleanup, then spawn delay/sound restoration, then `RestoreWholeStateOwnership`); owners created on first use and retained after cleanup | `test_whole_catalog.py`, `test_composed_support.py`, `test_body_visual_map.py`, `test_common_assets_map.py`, `test_stage_variant_graph_roots.py`; `WholeCatalogHost.cs` |
| Input and camera | `NovaInputBoundary`, `NovaInputBridge`, `NovaThirdPersonView`, `AndroidPresentationCamera`, `NovaDiagnosticDisplay` | nested `NovaInputSession` (`IDisposable`) **own type** holds trace cursors and the input iterators with local mapping, landing, camera and loop state; `NovaThirdPersonView` keeps its own camera/orbit state; `worldView` and `worldEquipmentBridge` stay shared on the coordinator; `NovaInputBridge`, `AndroidPresentationCamera` and `NovaDiagnosticDisplay` remain **own types**; reports remain coordinator observations | `NovaRawBoundary` / `NovaInputBoundary` forward to the session; input teardown stays in its iterator `finally` in the same order; `NovaInputBridge.OnDisable` neutralises input; owner created on first use and retained after its no-op `Dispose` so final `Save` can flush traces | `test_nova_input_presence.py`, `test_nova_bridge_evidence.py`, `test_input_migration.py` |
| Settings | `AndroidOfflineSettings`, `OfflineSettingsBoundary` | `AndroidOfflineSettings` **own type**, kept across sessions; nested `OfflineSettingsSession` (`IDisposable`) **own type** holds the saved pause time scale; store reference, visibility and pause flags stay on the coordinator for menu/Nova input | `PrepareOfflineSettings` (calls `OfflineSettingsSession.Prepare`) → `CleanupOfflineSettingsPause` (calls `Dispose`, releases an owned pause only) | — |
| Progression and profile | `AndroidProgressionBoundary`, `AndroidOfflineProfile`, `AndroidProfileBoundary`, `OfflineLoadoutBoundary` | `AndroidProgressionBoundary` (`IDisposable`), `AndroidOfflineProfile` and nested `AndroidProfileSession` (`IDisposable`) **own types**; session owns loadout preview, catalog snapshots, redirect lease and event/discovery listeners; progression reference, results/save-system state, world references and pending menu loadout stay shared on the coordinator | `ApplyAndroidProfileLoadoutBeforeSpawn` (calls `AndroidProfileSession.ApplyLoadoutBeforeSpawn`) → `PrepareAndroidProfile` (calls session `Prepare`, then `AndroidProgressionBoundary.Prepare`) → `CleanupAndroidProfile` (calls session `Dispose`, including progression `Dispose`); results installs the save system before profile setup and restores it after profile cleanup | `AndroidProgressionHost.cs`, `AndroidDiscoveryHost.cs`, `AndroidProfileHost.cs` |
| Results | `IntegratedResultsBoundary` (with `AndroidProfileSaveSystem` in `AndroidProfileBoundary`) | nested `IntegratedResultsSession` (`IDisposable`) **own type** holds ending templates/catalog restoration, statistics callbacks and event context, ledger directory, save-system swap/restore and result listeners; serializer guards remain static; `resultsSaveSystem`, `resultsLedger`, `resultsStats` and `resultsRunReport` stay shared on the coordinator; `r.results` remains the coordinator observation | `PrepareResultsKeyItems` may precede `PrepareIntegratedResults` (calls session `Prepare`) → `CleanupIntegratedResults` (calls `Dispose`: profile cleanup precedes save-system restore); owner created on first use and retained after `Dispose` | — |
| HUD and UI | `RecoveredHudBoundary`, `RecoveredHudPresentation`, `RecoveredHudFeedback`, `RecoveredPickupPresentation`, `MoonPillarPresentation` | nested `RecoveredHudSession` (`IDisposable`) **own type** holds menu events, reference-rendering restoration and text reflection/restoration state; `recoveredHud`, `recoveredMenu`, `recoveredTextSettings` and `ownsRecoveredText` stay shared on the coordinator; feedback/queue state and pickup bindings stay in the existing presentation component **own types**; `r.hud` remains the coordinator observation | Separate `PrepareRecoveredText`/`Menu`/`Hud` → `CleanupRecoveredHud` (calls `Dispose`, HUD then menu only), `CleanupRecoveredMenu`, `CleanupRecoveredText` (later catalog teardown); owner created on first use and retained after `Dispose` | — |
| World, director and combat | `IntegratedWorldBoundary`, `AutomaticSpawnBoundary`, `AutomaticDirectorBoundary`, `EnemySpineBoundary`, `StagePopulationBoundary`, `WholeInteractableBoundary`, `RunClockBoundary`, `PlayerDefeatBoundary`, the `World*` item boundaries (27 files) | nested `RunClockSession` (`IDisposable`) **own type** holds original clock callbacks, async lifecycle, scene-catalog restoration and timestamps; `clockSceneDefs` and `priorClockScene` stay shared on the coordinator; nested `PlayerDefeatSession` (`IDisposable`) **own type** holds the death-effect locator, async handle, prefab, observed effects and defeat body; nested `WorldHealingItemsSession` and `WorldLegendaryItemsSession` (`IDisposable`) **own types** hold healing source names, Warbanner reflection/callback and observed instances, and legendary controller names, observed instances and remote-transform/host-authority snapshots, respectively (static fields remain static); `r.runClock`, `r.playerDefeat`, `r.procContent` and `r.itemBehaviors` remain coordinator observations; shared world registries and remaining boundaries use coordinator fields; nested `WorldItemDisplaySession`, `WorldDotSession`, `WorldItemBehaviorSession` (`IDisposable`) **own types** hold their files' private item-display, DOT and item-behaviour state (J534); nested `CombatSpineSession`, `StageBossContentSession` (`IDisposable`) **own types** hold their files' private state; nested `PrimaryFireSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldProcContentSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldEquipmentSession`, `AutomaticDirectorSession` (`IDisposable`) **own types** hold their files' private state; nested `EnemyRewardSession` (`IDisposable`) **own types** hold their files' private state; nested `WholeInteractableSession` (`IDisposable`) **own type** holds owned templates/cards, player-spawn points and the native spawn-point prefab snapshot/lease; `wholeSceneDirector`, `wholeStageContext`, shared world/commerce collections and reports remain on the coordinator; nested `WholePopulationSession` (`IDisposable`) **own types** hold their files' private state; nested `EnemySpineSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldFlightEquipmentSession` (`IDisposable`) **own types** hold their files' private state; nested `IntegratedWorldSession` (`IDisposable`) **own types** hold their files' private state | `PrepareIntegratedWorld` → `CleanupIntegratedWorld` → `VerifyIntegratedWorldCleanup`; `PrepareEnemy` → `CleanupEnemy` → `VerifyEnemyCleanup`; `PrepareRunSceneContext` → `StartOriginalRunClock` → `CleanupRunClock` (calls `Dispose`) → later `ReleaseCompletedRunAsyncAssets` after Run teardown; `PreparePlayerDefeat` → `ObservePlayerDefeat` → `CleanupPlayerDeathEffect` (awaited coroutine: detach listener, destroy effects, release prefab references then handle, remove locator; `Dispose` detaches the listener only); `PrepareWorldHealingItemSource` / `ObserveWorldHealingItems` → `CleanupWorldHealingItems` (calls `Dispose`: final observation, level callback removal, instance destruction); `PrepareWorldLegendaryItemSource` / `ObserveWorldLegendaryItems` → `CleanupWorldLegendaryItems` (calls `Dispose`: final observation, instance destruction, remote-transform then host-authority restoration); all four owners created on first use and retained after cleanup; `PopulateWholeStage` → `CleanupWholeStageInteractables` (stage objects only) → `CleanupWholeInteractables` (calls `Dispose`: stage cleanup, spawn-point prefab restoration, lease release); interactable owner created on first use and retained across stage turnover and cleanup | `test_scene_acceptance.py` (acceptance helpers) |
| Commerce and pickups | `WorldCommerceBoundary`, `ChestPurchaseBoundary`, `ChestEjectionBoundary`, `ItemPickupBoundary`, `GenericPickupBoundary`, `MoneyCostBoundary`, `PickupDropletFlightBoundary` (10 files) | nested `ChestEjectionSession` (`IDisposable`) **own type** holds chest animation snapshots, source effect pool/cache references, observed effects/returns, owned material copies and droplet/model references; `chestEjectionBegan` stays shared with ChestPurchase on the coordinator; `r.chestEjection` remains the coordinator observation; remaining boundaries use coordinator fields; nested `GenericPickupSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldCommerceSession` (`IDisposable`) **own types** hold their files' private state | `PrepareWorldCommerce` → `CleanupWorldCommerce`; `OwnChestAnimationSources` / `PrepareChestEjection` → `ObserveChestEjection` / `FinishChestEjection` → `CleanupChestEjection` (calls `Dispose`: droplet destruction, source effect pools/cache cleanup, material destruction) → diagnostic `CheckChestEjectionCleanup` after chest/pickup cleanup; owner created on first use and retained after cleanup | — |
| Stage transport and teleporter | `TeleporterWorldBoundary`, `IntegratedStageBoundary`, `AndroidStageTransport`, `StageGeometryBoundary`, `GoldshoresBoundary`, `MoonMissionBoundary`, `MoonEscapeBoundary` | nested `StageGeometrySession` (`IDisposable`) **own type** holds owned billboard copies, Moon-volume mode, map-zone activation/source names and observation callbacks; geometry bundle, scene, materials, source-object/context roots, first-stage selection and `r.stage` stay shared on the coordinator; remaining boundaries use coordinator fields; nested `IntegratedStageSession` (`IDisposable`) **own types** hold their files' private state; nested `TeleporterWorldSession` (`IDisposable`) **own types** hold their files' private state | `PrepareTeleporterWorld` → `CleanupTeleporterWorld`; `PrepareStageTransport` → `CleanupStageTransport`; `PrepareStageGeometry` / `LoadStageGeometry` forward to the session; source-context deactivation stays separate; `CleanupStageGeometry` remains an awaited coroutine at the same call sites, including after `CleanupSpawnConfig` in `Start` (pause zones, detach observations, unload scene, destroy billboards then materials, unload bundle, mark coordinator report); owner created on first use and retained across stage handoffs; `Dispose` is a no-op | — |
| Shaders and presentation | `AndroidMaterialPresentation`, `AndroidNativeDeferredPresentation`, `Android*Presentation.shader` (18 files) | **own types** (static) | `Begin` → `Finish` | `test_shader_bindings.py`, `test_shader_metadata.py`, `test_pc_draw_export.py` |
| Developer controls | `DebugAccelerationBoundary` ([debug-acceleration.md](debug-acceleration.md)) | nested `DebugAccelerationSession` (`IDisposable`) **own type** holds the body, saved god mode, ownership flag, charge scan/callback set and grant inventory; `debugPanel` stays shared with IntegratedWorld's graphics button; sticky "assisted" flags stay in the coordinator report | `PrepareDebugAcceleration` (calls `DebugAccelerationSession.Prepare`) → `CleanupDebugAcceleration` (calls `Dispose`; owner retained) | `test_debug_acceleration.py` |

Build, device and safety tooling has its own tests: `test_build_identity.py`,
`test_build_snapshots.py`, `test_apk_identity.py`, `test_adb_target.py`,
`test_lab_safety.py`, `test_public_privacy.py`.

C# under `tools/` is formatted with `clang-format -i` using the repository's `.clang-format`
(J544). It never rewraps string literals or comments, so a correct reformat leaves each file
identical once whitespace is removed; check that before committing a reformat. CI does not
enforce it, because other clang-format versions format C# differently.

Host CI also runs Ruff (pinned in `tools/lab-requirements.txt`, configured in `ruff.toml`):
`ruff check` and `ruff format --check` on every Python file a change touches. `scripts/` and
`tests/` are ruff-formatted (J518); `ruff.toml` lists the rules still off and why.

`scripts/readme-actions.py` (support) generates the marked current-action table in
`README.md` from `scripts/lab/actions.py`, preserving registry order and excluding
historical actions. Run it after changing registry names, status or help; host CI runs
`python scripts/readme-actions.py --check` beside the journal-index freshness check.
`tests/test_readme_actions.py` covers rendering, idempotence and freshness checks.

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
and staged by `whole_catalog.build_integration`. Existing Unity-owned `.meta` files
are retained; source and metadata paths remain player-only payload exceptions.
`build.py` declares the three generated visual maps separately and rejects missing
authored sources or unlisted staged C# files. `test_runtime_sources.py` checks the
selection and its independence from generated-project history.

The current `scripts/lab` modules are `build`, `composition_migration`, `device`,
`graphics`, `health`, `inventory`, `main`, `recovery` and `whole_catalog` (helpers such as
`common` count as support); the
current `prototype` actions are the ten in
[whole-catalog-integration.md](whole-catalog-integration.md#reusable-fixes-and-commands)
plus `project-manifest-capture` and `project-manifest-compare`.

## Known structural debt

First verified against `af2e101`; status updated after J547. Each step was its own commit with
host tests, a zero-error exact-editor build and a device check.

Still open:

1. **No from-scratch build.** The project is still made by migrating a previous project
   (`composition_migration.stage`); seven path families it reads have no producer in the repo
   ([LOCAL_STATE.md](LOCAL_STATE.md#fresh-rebuild-blockers-reached-by-the-current-workflow)),
   and the transformed `RoR2.dll` was produced by historical actions (`scene_runtime.py:542`,
   `integrated_objective.py:56`) and is carried forward by hash. The removal plan is
   [migration-removal-plan.md](migration-removal-plan.md); commits 1–2 are done (harness,
   source manifest, script GUIDs and packages), 3–9 are open.
2. **Direct composition remains unfinished.** The current build now generates both
   runtime and content configs from recipes, without inherited extra keys. The
   earlier composition migration still uses previous-project configs for its own
   staging/contracts; removing that chain belongs to later steps of the
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
