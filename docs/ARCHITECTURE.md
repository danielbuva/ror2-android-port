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
| 4 | Assembly transforms | no current command; see [debt](#known-structural-debt) | `tools/AssemblyProbe/` (`OptionalPresentationGuard`, `WwiseUnavailable`, `AudioGuard`) | transformed `RoR2.dll`, recorded by hash |
| 5 | Compose the project | `./dev prototype --action composition-update-stage`, then `composition-update-dependencies` | `scripts/lab/composition_migration.py` | `lab-project/` |
| 6 | Whole-catalog content | `whole-catalog-prepare` → `-host` → `-repair-bindings` (when recorded) → `-contracts` → `-host-providers` | `scripts/lab/whole_catalog.py`, `tools/catalog/` | `experiments/whole-catalog/<timestamp>/` |
| 7 | Bundles, payload, APK | `whole-catalog-build`, or `whole-catalog-code-build` for a code-only change | `whole_catalog.py` (writes the linker descriptor through `preservation_descriptor`, J506) → `build.py` → exact editor via MCP | APK + payload receipts |
| 8 | Install and sync | done by `whole-catalog-run`; alone: `./dev install`, `./dev sync-data` | `scripts/lab/device.py` | placement receipt |
| 9a | Catalog registration scan | `whole-catalog-run` | `whole_catalog.run_integration` | `integration-<timestamp>/device-<timestamp>/` |
| 9b | Gameplay run | no tracked command: untracked runners in `work/experiments/whole-catalog/gameplay/` ([debt](#known-structural-debt) item 8); captures: `./dev logs`, `crash`, `screenshot`, `perf` | runner + `device.py` | `movement-batch-*.json` report, run folder |
| 10 | Record | append a journal entry, `python3 scripts/journal-index.py`, replace `PORTING_STATE.md` | — | — |

Steps 6–9a are the `./dev prototype --action whole-catalog-*` actions listed in
[whole-catalog-integration.md](whole-catalog-integration.md#reusable-fixes-and-commands).
`whole-catalog-run` installs, syncs and launches, but it pushes `whole-catalog-selection.json`,
which makes `MovementBatchProbe.Start` exit: it checks catalog registration
(`whole-catalog-result.json`), not gameplay. Gameplay is launched by a runner that pushes an
attempt-bound `movement-batch-selection.json` and then launches the app.
The exact editor is started with `./dev editor --target lab --action open`; send it one
mutation at a time. Device acceptance is always the real device, never the editor.

Pointer chain for the latest evidence: `experiments/whole-catalog/latest.json` →
`integration-latest.json` → build, device and composed receipts.
`checkpoints/LAST_OBSERVED_WHOLE_CATALOG.json` pins the accepted scope.

## Android runtime

The shipped game is one experiment case inside the lab harness `MovementBatchProbe`
(`tools/unity/MovementBatchProbe.cs`, 70 `partial` files). The runtime configuration is the
untracked `Resources/MovementBatchProbe.json` in the generated project; the same `Result`
type is both that configuration and the report written back as `movement-batch-*.json`.

Start-up, in order:

1. `Init` (`MovementBatchProbe.cs:47`, `RuntimeInitializeOnLoad` after scene load): if the
   `MovementBatchProbe` resource exists, create the harness object.
2. `Start` (`:48`): exits if `whole-catalog-selection.json` exists in persistent data (the
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
7. `RunSelectedProbe` (`:102`): a 118-label `switch` on the case id. The spine id shares a
   case group that runs `BodyLifecycle()` (`:310`); `IsPlayableSpine()`
   (`PrimaryFireBoundary.cs:12`, a prefix match) turns on the game path inside the
   boundaries it calls.

Teardown, in order, after `RunSelectedProbe` returns or throws:

1. `RunSelectedProbe`'s `finally`: `CleanupLanding`, destroy the obstacle, body host and
   staging roots, disconnect the recovered client and shut down the owned network server.
2. In `Start`: `VerifyEnemyCleanup` → `VerifyIntegratedWorldCleanup` (integrated world) →
   `VerifyAutomaticModelDestruction` → `CleanupEnemyRewards` → `CleanupPlayerDeathEffect`
   → `CleanupBodyCatalog` → `CleanupTeleportMaterial` → `CleanupBarrierEffect` →
   `CleanupSpawnConfig` → `CleanupStageGeometry` → `AndroidMaterialPresentation.Finish` →
   `ReclaimCompletedSessionResources` (only after a clean, successful integrated session) →
   `Save()` phase `complete` → `RestartWorldAfterCleanup`.

The enemy, world, model, teleport-material and barrier steps run inside copies of the same
`MoveNext` exception wrapper, which records the failure and moves on. The reward,
death-effect, geometry and reclaim steps, and the synchronous cleanup calls outside the
`CleanupBodyCatalog` `try`, have no wrapper: an exception there stops the remaining
release steps. `Start` itself has no
enclosing `finally`, and `MovementBatchProbe` has no `OnDestroy` or `OnApplicationQuit`:
an error during catalog preparation or the menu, or the app being killed, skips the
post-run release sequence. Per-boundary teardown inside the session (the 17-step call
order and each `finally`) is in
[architecture-file-map.md](architecture-file-map.md#d-playable-spine-runtime-sequence-and-ownership).

## Ownership

Most `*Boundary.cs` files are `partial class MovementBatchProbe`: their state is fields on
the coordinator, not a separate owner. Only the types marked **own type** keep their own
state. Host tests are in `tests/`; editor fixtures (`tools/catalog/*Host.cs`) run in the
exact editor. There is no per-subsystem device check yet: catalog registration is checked
by `whole-catalog-run`, and everything else by a gameplay runner's `movement-batch-*.json`
report, read against the journal entry that defines what it must show.

| Subsystem | Main files (`tools/unity/`) | State | Setup → teardown | Host test / editor fixture |
| --- | --- | --- | --- | --- |
| Session and entry | `MovementBatchProbe`, `OfflineApplicationBoundary`, `SessionResourceBoundary`, `ActiveClientBoundary`, `OfflineRunSeedBoundary`, `SurvivorSelectionBoundary` | coordinator fields; `Result r` | `Start` → `AwaitOfflineRunStart` → `RunSelectedProbe`; `ConnectActiveBodyClient` → `CleanupActiveBodyClient`; `CollectPriorSessionGarbage` → `ReclaimCompletedSessionResources` | `AndroidLifecycleHost.cs` |
| Catalog and resources | `BodyCatalogBoundary`, `WholeCatalogComposed`, `WholeCatalogLoader`, `SpawnStateBoundary`, `OriginalBodyVisualBoundary`, `OriginalGlobalCommonAssetsBoundary`, `TeleportMaterialBoundary`, `BarrierEffectBoundary` | `WholeCatalogComposed` **own type** (static); the rest coordinator fields | `RegisterBodyCatalog` (calls `WholeCatalogComposed.Prepare`) → `CleanupBodyCatalog` (calls `Release`) | `test_whole_catalog.py`, `test_composed_support.py`, `test_body_visual_map.py`, `test_common_assets_map.py`, `test_stage_variant_graph_roots.py`; `WholeCatalogHost.cs` |
| Input and camera | `NovaInputBoundary`, `NovaInputBridge`, `NovaThirdPersonView`, `AndroidPresentationCamera`, `NovaDiagnosticDisplay` | `NovaInputBridge`, `AndroidPresentationCamera` **own types** (components) | `NovaInputBoundary` → its `finally`; `NovaInputBridge.OnDisable` neutralises input | `test_nova_input_presence.py`, `test_nova_bridge_evidence.py`, `test_input_migration.py` |
| Settings | `AndroidOfflineSettings`, `OfflineSettingsBoundary` | `AndroidOfflineSettings` **own type**, kept across sessions | `PrepareOfflineSettings` → `CleanupOfflineSettingsPause` | — |
| Progression and profile | `AndroidProgressionBoundary`, `AndroidOfflineProfile`, `AndroidProfileBoundary`, `OfflineLoadoutBoundary` | `AndroidProgressionBoundary` (`IDisposable`) and `AndroidOfflineProfile` **own types** | `PrepareAndroidProfile` (calls `AndroidProgressionBoundary.Prepare`) → `CleanupAndroidProfile` (calls `Dispose`) | `AndroidProgressionHost.cs`, `AndroidDiscoveryHost.cs`, `AndroidProfileHost.cs` |
| Results | `IntegratedResultsBoundary` (with `AndroidProfileSaveSystem` in `AndroidProfileBoundary`) | coordinator fields; save system swapped into `PlatformSystems` | `PrepareIntegratedResults` → `CleanupIntegratedResults` (restores the previous save system) | — |
| HUD and UI | `RecoveredHudBoundary`, `RecoveredHudPresentation`, `RecoveredHudFeedback`, `RecoveredPickupPresentation`, `MoonPillarPresentation` | coordinator fields; `r.hud` observation | `PrepareRecoveredText`/`Menu`/`Hud` → `CleanupRecoveredHud`/`Menu`/`Text` | — |
| World, director and combat | `IntegratedWorldBoundary`, `AutomaticSpawnBoundary`, `AutomaticDirectorBoundary`, `EnemySpineBoundary`, `StagePopulationBoundary`, `RunClockBoundary`, `PlayerDefeatBoundary`, the `World*` item boundaries (27 files) | coordinator fields | `PrepareIntegratedWorld` → `CleanupIntegratedWorld` → `VerifyIntegratedWorldCleanup`; `PrepareEnemy` → `CleanupEnemy` → `VerifyEnemyCleanup` | `test_scene_acceptance.py` (acceptance helpers) |
| Commerce and pickups | `WorldCommerceBoundary`, `ChestPurchaseBoundary`, `ItemPickupBoundary`, `GenericPickupBoundary`, `MoneyCostBoundary`, `PickupDropletFlightBoundary` (10 files) | coordinator fields | `PrepareWorldCommerce` → `CleanupWorldCommerce` | — |
| Stage transport and teleporter | `TeleporterWorldBoundary`, `IntegratedStageBoundary`, `AndroidStageTransport`, `StageGeometryBoundary`, `GoldshoresBoundary`, `MoonMissionBoundary`, `MoonEscapeBoundary` | coordinator fields | `PrepareTeleporterWorld` → `CleanupTeleporterWorld`; `PrepareStageTransport` → `CleanupStageTransport` | — |
| Shaders and presentation | `AndroidMaterialPresentation`, `AndroidNativeDeferredPresentation`, `Android*Presentation.shader` (18 files) | **own types** (static) | `Begin` → `Finish` | `test_shader_bindings.py`, `test_shader_metadata.py`, `test_pc_draw_export.py` |
| Developer controls | `DebugAccelerationBoundary` ([debug-acceleration.md](debug-acceleration.md)) | coordinator fields; sticky "assisted" flags | `PrepareDebugAcceleration` → `CleanupDebugAcceleration` | `test_debug_acceleration.py` |

Build, device and safety tooling has its own tests: `test_build_identity.py`,
`test_build_snapshots.py`, `test_apk_identity.py`, `test_adb_target.py`,
`test_lab_safety.py`, `test_public_privacy.py`.

## File status

Every file in `tools/unity`, `tools/catalog` and `scripts/lab`, and every `prototype`
action, is classified with its staging site and a runtime call site in
[architecture-file-map.md](architecture-file-map.md). Totals:

| Area | Current | Support | Historical |
| --- | ---: | ---: | ---: |
| `tools/unity` + `tools/catalog` (135 files) | 94 | 26 | 15 |
| `scripts/lab` (43 modules) | 9 | 24 | 10 |
| `prototype` actions (175) | 10 | — | 165 |

Historical `tools/unity` files (not staged by any current builder; none exists in the
generated project): `AudioAssetProbe`, `CharacterMotorOrderProbe`,
`CollectionsRuntimeProbe`, `CommandoPosePreview`, `KinematicBatchProbe`,
`LoadingSceneProbe`, `MetadataDispatchProbe`, `ReferenceIdentityProbe`, `RoR2SliceProbe`,
`StartupSegmentProbe`, the three `RewiredTrial*` files, and `ControllerAddressLink.xml`
and `TeleporterTimelineLink.xml`. `ReconstructionProbe.cs` is support: `./dev
export-project` wires it into the exported project. Several current files are staged
only because a copy already exists in the generated project (see
[debt](#known-structural-debt) item 7).

The current `scripts/lab` modules are `build`, `composition_migration`, `device`,
`graphics`, `health`, `inventory`, `main`, `recovery` and `whole_catalog` (helpers such as
`common` count as support); the
current `prototype` actions are the ten in
[whole-catalog-integration.md](whole-catalog-integration.md#reusable-fixes-and-commands).

## Known structural debt

Verified against `af2e101`. The order at the end is the safe order to pay it down; each step
is its own commit with host tests, a zero-error exact-editor build and a device check.

1. **The shipped game is an experiment case.** `Start` waits 8 s, then `RunSelectedProbe`
   dispatches on a string id; the game is `body-state-spawn-state-auto-nova-spine`, one of
   118 case labels on a single 4,471-character line.
2. **One class holds everything.** 70 `tools/unity` files are `partial class
   MovementBatchProbe`; config and report share one `Result` type; the `MoveNext`
   exception wrapper is copied 9 times in `Start`.
3. **The recipe is untracked.** The runtime config (369 keys) and the content recipe
   `work/scene-probe-build.json` (4,184 prefabs) are not in Git.
4. **No from-scratch build.** The current project is made by migrating a previous project
   (`composition_migration.stage`). Eight path families it reads have no producer in the
   repo ([LOCAL_STATE.md](LOCAL_STATE.md#fresh-rebuild-blockers-reached-by-the-current-workflow)),
   and no current command applies the AssemblyProbe transforms: the transformed
   `RoR2.dll` was produced by historical actions (`scene_runtime.py:542`,
   `integrated_objective.py:56`) and is carried forward by hash.
5. **Hard-coded run folders.** `scene_runtime.py:59`, `:515` and `:883`, and
   `input_migration.py:90` read fixed timestamped evidence folders (all in historical
   actions).
6. **Text patches on authored C# — resolved.** The build used to inject code into
   `BodyCatalogBoundary.cs` and `MovementBatchProbe.Start` by exact-text `.replace()`. The
   patches were dormant and are deleted (J505, J506); the hooks are authored, and host tests
   check them without depending on whitespace. The remaining `.replace()` calls in
   `scripts/lab` remap GUIDs in generated Unity YAML or fill a Python-held editor template.
7. **Build membership depends on history.** A `tools/unity` file is staged if it already
   exists in the generated project (`build.py:78`, `whole_catalog.py:1090`); further file
   lists live in `build.py`, `nova_bridge.py:68` and `scene_runtime.py:584`.
8. **Experiment drivers outside Git.** Device gameplay runs are driven by about 89 untracked
   runner scripts in `work/experiments/whole-catalog/gameplay/`; `work/` also holds about 700
   loose one-off `.py` files.
9. **Command sprawl.** `scripts/lab/main.py` dispatches about 165 historical `prototype`
   actions from one `if/elif` chain next to the 10 current ones.

Safe order:

1. ~~Delete the dormant C# text patches~~ — done (J505, J506). C# formatting is no longer
   blocked by the build.
2. Split `Result` into `SessionConfig` and `SessionReport`, keeping both JSON shapes.
3. Give the game a `GameSession` entry point that `Start` calls directly; keep the old id as
   an alias for `nova_bridge.py`, `scene_runtime.py` and `IsPlayableSpine`.
4. Extract owners one at a time, least-coupled first, following
   `AndroidProgressionBoundary` (an `IDisposable` with explicit acquire/release and its own
   state).
5. Rename `MovementBatchProbe` last, keeping `Resources.Load("MovementBatchProbe")` and the
   on-device file names or aliasing them.

Recipe tracking (items 3–5) and a single runtime source manifest (item 7) can proceed in
parallel with steps 2–5; they change the build, not the runtime.
