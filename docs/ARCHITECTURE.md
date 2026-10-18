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
| 4 | Assembly transforms | `./dev prototype --action assembly-transforms-check` (verification only) | `scripts/lab/assembly_transforms.py` → `tools/assembly-transforms/` | none; verifies three transformed plugins in disposable `.local/` scratch |
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

Incremental project rebuild (`scripts/lab/rebuild.py`, current, R0–R8):
`build_entry_rebuild.py` owns host-only R7 `build-entries` and R8
`runtime-sources`, after `scene_rebuild.py` supplies R5/R6. It uses destination
`StageIO` buffers, explicit retained-input hash gates and completion markers;
`finish` verifies selected output hashes/sizes before flushing. It shares
`whole_catalog.generate_build_maps`, `stage_build_sources` and
`generate_build_bootstrap` with the real build. `build.stage_android_assets`
retains the real copytree and provides buffered destination placement. No Unity
import or build runs here. `validate-bindings` is the final read-only host gate;
its receipts, membership rules, remaining pins and uncovered provenance are in
[rebuild-plan.md](rebuild-plan.md#r7r8-host-build-entries-and-sources).

Host prerequisites (`shader_rebuild.py` and `project_input_rebuild.py`, current):
R1 → `shader-pipeline` → R2 → `project-inputs` → R3–R8 → final bindings.
Shader replay initializes R1's generation marker, validates the public retained-input
recipe, runs existing generators into destination scratch, then places only
map-matching outputs through `StageIO`. Its per-file blocked/result receipt owns
completion state; composition requires it and rechecks generated source hashes.
No shared pointers or Wine bottles are written. Native recovery remains a pinned
local-input blocker. `shader_source.output_directory` shares unchanged real action
paths and isolated pointer-free setup across all three generators.
Project inputs own public smoke settings, archived independently authored editor
versions, explicit Nova importer metadata, shared Nova-axis generation and the
original-identity OBJ export. All outputs are buffered and gated before flush;
the completion receipt lives under destination `.rebuild/`. No new runtime state
or teardown is introduced. Setup is the accepted installation and public recipes;
failed native scratch is retained and later operator reruns use a new attempt
folder. No local input is retired. Exact membership, unresolved settings/linker
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

`recipe/catalog-rebuild-inputs.json` pins ten retained local analysis inputs; they
are verified before being copied under `.rebuild/catalog-inputs/`. Catalog
metadata export currently needs Unity, so audit/native-inventory/reconcile are
**not regenerated** by this host-only replay. Regenerating these inputs is the
next blocker. Destination GUID ownership, catalog manifests/import receipts,
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
`scene-rebuild-inputs.json` pins the frozen graph baseline and MapZone script
identity list as two additional retained-input blockers. Destination scene bytes
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
`StageIO` against the isolated destination. The same owner keeps real-stage writes
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
plus `project-manifest-capture`, `project-manifest-compare`,
`asset-transforms-check` (owned by `asset_transforms`) and
`authored-additions-check` (owned by `authored_additions`), plus
`inherited-state-check` and `inherited-store-capture` (owned by `inherited_state`).

## Known structural debt

First verified against `af2e101`; status updated after J547. Each step was its own commit with
host tests, a zero-error exact-editor build and a device check.

Still open:

1. **No from-scratch build** (design: [rebuild-plan.md](rebuild-plan.md)). The project is still made by migrating a previous project
   (`composition_migration.stage`); seven path families it reads have no producer in the repo
   ([LOCAL_STATE.md](LOCAL_STATE.md#fresh-rebuild-blockers-reached-by-the-current-workflow)),
   and the generation marker still lacks a full assembly-map initializer. The three
   transformed plugins are now reproducible through `assembly-transforms-check`,
   but composition still carries them forward by hash. The removal plan is
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
