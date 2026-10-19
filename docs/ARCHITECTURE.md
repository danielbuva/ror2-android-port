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
| 2 | Check before building | `./dev preflight` (host + selected storage); `--host-only` omits device access; builds run host gates | `scripts/lab/build.py` (`preflight_host`, `preflight`) | selected preflight receipt; refuses on drift |
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

### Device selection and storage receipts

Device selection uses an explicit allowlist/default model.
`work/config/local.json` accepts `device_serials`,
`device_serial`, and `device_settings[serial]`. Device actions accept `--device SERIAL`
or `LAB_DEVICE=SERIAL`; with multiple attached devices and no explicit selector, they
refuse to choose. An explicit serial outside the configured allowlist also refuses.
Top-level legacy settings are fallback values for the default device only. Per-device
overrides cover `storage_mode` (`adopted` or `internal`), `internal_reserve_mib`,
`apk_install_limit`, `sleep_display_when_idle`, `display_models`, and `display_count`.

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

`scripts/lab/build_lock.py` owns a persistent advisory kernel lock and owner diagnostics.
It is reentrant in one thread and hands its open descriptor to the editor client. Build
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

Current onboarding is Nova on adopted storage. Nova and Thor are not yet configured as
internal-storage devices; onboarding waits for configured serials, recorded live storage,
and a passing current Nova baseline. Thor's two-display sleep behavior also remains to be
verified. These are readiness conditions, not evidence that either device currently uses
the proposed settings.

CPU capture (`scripts/lab/performance_capture.py`, current host implementation):
`./dev perf --action cpu --target LABEL` takes a 15 s system simpleperf call graph
from the selected device's already running, owned foreground lab process. Setup
validates ownership, APK hash, one PID, foreground activity and the validated runtime
receipt. Before/after reports preserve available attempt/session/stage/frame context;
a changed process, APK or previously available session identity fails. It does not
launch gameplay or install a profiler. Live system-simpleperf permissions remain a
device gate. Raw profile, symbol report, receipt and failures stay in validated
`work/device/<serial>/performance/<attempt>/`. A symbol-report failure retains the
successful raw capture and explicitly records the report error. Teardown removes
only its unique remote profile after a verified nonempty pull; a failed pull or
timeout preserves the remote output without guessing a process to kill. The caller
retains ownership of the existing gameplay run and display. Host transport/refusal
contracts are in `test_performance_capture.py` and `test_performance_cli.py`.
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

Incremental project rebuild (`scripts/lab/rebuild.py`, current, R0–R9):
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
GUIDs and shared importer schemas from `recipe/importer-identities.json`, checks
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
and catalog closure from R3's hash-pinned analysis inputs. The rebuild reads no
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
| Siren encounter (host draft) | `runtime/stage/SirenEncounterBoundary.cs` | `SirenEncounterSession` (`IDisposable`) **own type** holds the exact source encounter, its network-spawn lease, native BossGroup listener and observation clock; scalar reports remain in `r.stageProgress.sirenEncounters` | `IntegratedStageSession.BeginOriginalStage` after source population and native `Stage.Start` → bounded stage tick → `CleanupSirenEncounter` before transition/unload or transport disposal; detach listener, retire validated original squad members, unspawn the owned identity, restore source active state and clear engine references | `SirenEncounterHost.cs` (exact-editor selection/transaction fixture; native lifecycle unverified) |
| Shaders and presentation | `AndroidMaterialPresentation`, `AndroidNativeDeferredPresentation`, `Android*Presentation.shader` (18 files) | **own types** (static) | `Begin` → `Finish` | `test_shader_bindings.py`, `test_shader_metadata.py`, `test_pc_draw_export.py` |
| Developer controls | `DebugAccelerationBoundary` ([debug-acceleration.md](debug-acceleration.md)) | nested `DebugAccelerationSession` (`IDisposable`) **own type** holds the body, saved god mode, ownership flag, charge scan/callback set and grant inventory; `debugPanel` stays shared with IntegratedWorld's graphics button; sticky "assisted" flags stay in the coordinator report | `PrepareDebugAcceleration` (calls `DebugAccelerationSession.Prepare`) → `CleanupDebugAcceleration` (calls `Dispose`; owner retained) | `test_debug_acceleration.py` |

Build, device and safety tooling has its own tests: `test_build_identity.py`,
`test_build_snapshots.py`, `test_apk_identity.py`, `test_adb_target.py`,
`test_lab_safety.py`, `test_public_privacy.py`.

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
`whole_catalog.stage_build_sources`; compiler checks pass, but fixture execution,
repeated device sessions and attribution of broader managed-memory growth remain
pending. No new probe switch case implements the cleanup.

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
expansion availability. A case needs 60 s of live world play and positive native
authority **and** server activations on all four slots; at 180 s it reports missing
activation evidence. Source-suppressed callbacks remain unproven. First failure,
first-stage departure or process exit ends the batch. Current-process errors fail
the check; known handled Windows shader-target messages use the existing filter.
Each case preserves its first-world screenshot, frozen report, log and crash
evidence under `work/experiments/survivor-check/`. Cleanup removes the selector,
stops the owned app and sleeps the display. Every ADB command checks the parallel
session's coordination lock. Host contracts: `tests/test_survivor_check.py`.
This supplements both unchanged baseline modes; it does not replace them.

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
fixture-owned entries. Actual completed-session cleanup remains a device gate.

`./dev prototype --action session-cleanup-check` (current support action,
`scripts/lab/session_cleanup_check.py`) observes the existing first-stage loss
and restart flow with automatic diagnostic input and every gameplay debug
assist disabled. It requires a genuine player death/result, native teleporter
listener retirement while the server is active, and live session 2 in the same
process. It verifies the receipt-backed APK against its host artifact, freezes
profile counts, and refuses stale reports, runtime errors or departure from
Lakes. Setup preserves and removes only the owned report targets; teardown
preserves foreign selectors, verifies process termination and sleeps the display.
Raw evidence stays in validated `work/device/<serial>/experiments/session-cleanup/<attempt>/`.
The check cannot certify an unassisted run, permanent unlocks or a memory leak
fix. Host contracts live in `tests/test_session_cleanup_check.py`; Android
acceptance remains a separate gate.

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

First verified against `af2e101`; status updated after J597. Each step was its own commit with
host tests, a zero-error exact-editor build and a device check.

Still open:

1. **The from-scratch rebuild is not yet equivalent or self-contained**
   ([rebuild-plan.md](rebuild-plan.md)). `./dev prototype --action rebuild-step` builds a
   separate destination in twelve host steps, each byte-identical to the working project
   (J567–J575). R9 builds it into an APK that passed both device checks (J582), but R9
   still reports it unequal. With the J584 Timeline pin and the J585 layered reimport, the J586
   rerun logs no new reimport error and passes both checks first time; its APK differs from the
   baseline only in `Hidden/Compositing` (open), the path-dependent Burst library and build
   metadata. The last differing gate file is `BlueNoise_R8_1.png.meta`, working-project drift (J592).
2. **The rebuild still has local inputs, and the working project is still migrated.** Since
   J597 the rebuild's R2 takes its selection from public recipes and reads no migration
   evidence (B1, B3–B6, B8), previous project or live pointer; R5 pins nothing and R7 pins one
   contract result. Left: 57 local analysis inputs read by recorded hash (R3/R4's ten catalog
   records, which need a host Addressables catalog reader; R7's runtime contracts; 46 shader
   recovery inputs), 14 inherited-store files (12 from the editor-side `RecoveredHudBuilder`,
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
