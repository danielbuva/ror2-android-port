# Rebuilding the generated project from scratch

Design for the last part of Phase 2: recreate `work/lab-project` from public source, public
recipes and the user's legitimate installation, without the previous project or private history.
Based on a provenance map of all 91,841 project files (Codex, 2026-10-18; the map itself is
local, since it lists every game asset path). Every step builds into a separate destination
project and is proven against the current project for exactly the files the map attributes to
it; the working `work/lab-project` is never written. Line numbers and counts are as of J565.

Steps:

- **R0:** destination project and a per-step comparison harness keyed by the provenance map.
- **R1:** original-assembly placement. 45 original DLLs and `SimpleJSON.dll` from the
  installation; no tracked producer today.
- **R2:** composition stage output (export copies, recipe transforms, generators, inherited
  store).
- **R3–R8:** the post-composition builders in the order below.
- **R9:** Unity import and build of the destination, then both device checks.

R0–R8 now have a current host-only coordinator in `scripts/lab/rebuild.py`:

```sh
./dev prototype --action rebuild-step --step assemblies
./dev prototype --action rebuild-step --step assemblies --compare-only
```

Use `--work-dir ../../../work` when this checkout reads the shared local inputs;
all outputs still go beneath this checkout's `work/rebuild/`. `--dest DIR` selects
another destination under that root. R1 owns 98 paths: 49 DLLs and 49 generated
importers, including installation-sourced SimpleJSON and the three J563 transforms.
The recipe retains only source identities, GUIDs and settings; the common tracked
template renders the importer bytes. The coordinator validates complete map
membership and generated hashes before placement, then compares actual project
bytes. `--compare-only` reads an existing destination. Synthetic host coverage is
in `tests/test_rebuild.py`; real-data step execution remains an operator check.
R2 is `--step composition`, after R1 and the shader prerequisite in the same destination. It owns 84,487
current map paths: 84,009 export copies, 264 recipe transforms, 10 generator outputs
and 204 store-attributed paths (assembly paths remain R1). The host replay now
regenerates 190 of those paths and retains 14 store bodies; see the per-file
accounting below. Canonical closure
relocation plus the existing resolved-mesh membership supplies 83,881 export
copies; the residual 128 are identifier-only
pairs in `recipe/composition-export-copies.json`, audited in `recipe/README.md`.
Composition uses the current stage with destination-backed `StageIO`, also
retaining intermediate runtime config/project products for later builders and
redirecting auxiliary outputs beneath `.rebuild/composition/`. It renders the
package manifest from project-layout dependencies and initializes assembly
generation identity from R1 recipes. Existing source/output/conflict gates remain.
Dependency staging follows catalog import in the order below, rather than running
inline during R2; the real stage action retains its inline dependency call.
The removed/unowned binding guard is deferred only in the rebuild path; its
unresolved identifiers are preserved. `validate-bindings` runs last, after R8 and `importer-identities`. Synthetic host tests cover staging
and comparison; the operator must still run R2 against real data.

R3 and R4 are now executable after R2 in that same destination:

```sh
./dev prototype --action rebuild-step --step catalog-closure --work-dir ../../../work
./dev prototype --action rebuild-step --step dependencies --work-dir ../../../work
```

R3 owns the 259 non-export files attributed to `prepare_integration`. R4 owns
1,237 sanitized bodies and the support source (1,238 files). The unchanged builders
share the destination-aware I/O boundary with their real actions. Each step checks
all selected output hashes/sizes before flushing project writes, then compares
actual bytes against the current project; `--compare-only` also works for both.
R3 validates the `bootstrap-identity.json` hash pin in `build-entry-inputs.json`
and uses its attempt for both the regenerated integration directory and manifest.
R7 requires that same identity and generates its bootstrap directly from R3's
manifest. Ordinary `whole-catalog-prepare` retains timestamp naming.
R4 requires R3's completion marker. The build selection names 23 generated source scenes
that R6 produces; in the rebuild path only, R4 defers required paths whose provenance names a
builder outside R3/R4 and lists them in its receipt (`deferred_to_later_steps`), and
`validate-bindings` must find them once R5–R8 exist. The dependency walk starts only from missing
`Assets/WholeGame/` roots, so the deferral cannot change a staged file. The real stage action
keeps the unconditional refusal. Real data (J569): R3 259/259 and R4 1,238/1,238 identical.

Regenerated: destination GUID owners, closure location manifest, import and
mesh-output receipts, dependency walk/receipt, optional-content receipt and its
updated build selection. R4 reads R2's destination build selection and staged
runtime config, rather than the live project/config. The UI mapping is the public
recipe; the public project-layout recipe also supplies SilentProjectileBoundary's
GUID before R7 places its importer. Support repair checks the installed original assembly hash and pinned field
contract. No probe-tool build or Unity process runs in the rebuild path.

Temporary explicit blocker: `recipe/catalog-rebuild-inputs.json` hash-pins ten
existing local analysis records: source catalog, original catalog contract,
host/reconciled closures, source GUID index/repairs, native conversions, typed
import corrections, resolved mesh records and support field-contract receipt.
They are copied to destination scratch only after the entire hash gate passes.
The host audit, native inventory and reconciliation outputs are retained inputs,
not claimed as freshly generated. Native container receipts are not read: the
recorded final mesh-resolution receipt supplies that boundary. Removing this debt
requires a host replacement for the Unity catalog/contract export followed by
native inventory/reconciliation replay. Source identities still come from the
export, and every selected project product must match the map and current project.

R5 and R6 are executable after R4, in the same destination:

```sh
./dev prototype --action rebuild-step --step stage-variants --work-dir ../../../work
./dev prototype --action rebuild-step --step source-scenes --work-dir ../../../work
```

`scene_rebuild.py` owns this host replay. R5 selects 18 provenance paths: the
16 later reduced scenes and the final Sky Meadow / Ship Graveyard contracts.
R6 selects 46: 23 source-scene bodies and 23 deterministic importers. Each cohort
is hash/size-gated before project writes flush, then compared to current-project
bytes; `--compare-only` works for both. Completion markers enforce R4 → R5 → R6.
R6 calls `prepare` for all scene names and leaves the two Wwise DLLs to R1.
The real actions retain their write paths and separate audio action.

R5 explicitly reads two more retained inputs by recorded hash in
`recipe/scene-rebuild-inputs.json`: the frozen `whole-catalog-code-base.json`
graph baseline and `moon-script-identities.txt` MapZone script identities.
Neither is regenerated, and removing these pins remains a fresh-rebuild blocker.
R3/R4's ten pinned analysis inputs remain unchanged. R5 regenerates projections,
scene contracts, navigation roots, contexts and receipts from accepted source,
destination configuration/imported graphs and R3's regenerated manifest. A config
row without its measured destination scene remains pending; no live-project
config or implicit baseline read supplies missing output. R6 regenerates full
scene bodies/importers and destination config/receipts from accepted source and
public UI remaps. R4 must still defer R5/R6 paths: they do not exist when it runs.
The receipt retains those paths for the final `validate-bindings` gate, which
runs after R8. Synthetic contracts: `tests/test_scene_rebuild.py`.
The 41 stage node graphs are `unity-generated`: the live project and the frozen baseline
hold the editor's re-serialized form, while a destination before R9 holds R2's export copy.
In the rebuild path R5 accepts such a graph only when the destination bytes equal its single
recorded export source, and lists it as `unity_import_deferred` in its result; R9 must then
reproduce the baseline hash. Only graph paths, never their bytes, feed R5's outputs.
Real data (J570): from an empty destination, R1–R6 give 98, 84,487, 259, 1,238, 18 and 46
identical files (28 graphs deferred to R9) with the working project unchanged.

## R7/R8 host build entries and sources

After R6, in the same destination:

```sh
./dev prototype --action rebuild-step --step build-entries --work-dir ../../../work
./dev prototype --action rebuild-step --step runtime-sources --work-dir ../../../work
./dev prototype --action rebuild-step --step importer-identities --work-dir ../../../work
./dev prototype --action rebuild-step --step validate-bindings --work-dir ../../../work
```

`build_entry_rebuild.py` owns these host steps. R7 selects **187** map paths:
one runtime config, three C# maps, 181 repaired animation clips, stage contexts
and bootstrap JSON. The content recipe is a regenerated build-external product.
R8 selects **100**: 92 declared runtime sources, four editor fixtures,
`WholeCatalogBuild.cs`, two `android/Assets` files and the preservation descriptor.
Both have preflight and predecessor gates, buffered destination writes, complete
output hash/size gates before flush, actual byte comparison and `--compare-only`.
The real build retains its config → membership → maps/animation/context →
sources/linker → bootstrap → build order. Its Android copy remains in `build`
after staged-source validation. No editor or build operation is extracted.

Regenerated inputs/products: public runtime/content recipes; visual maps using
accepted source/aliases and R3's regenerated manifest; clips from accepted export
and destination controller CRC names; original stage contexts from accepted
scene fields and destination pool GUIDs; bootstrap preload keys from the pinned
R3 closure; sources/fixtures and Android assets from public tracked files;
linker roots from regenerated locations, retained contracts and authored
progression roots. Existing importers are preserved, never allocated by R8.

Explicit added blockers in `recipe/build-entry-inputs.json`: three decompiled
source files, one imported-contract result and one manifest read **only** for
the historical R3/R7 attempt identity. Each is hash-pinned; none is claimed
regenerated. Together with R3/R4's ten and R5's two, there are **17** retained
local input records. `recipe/rebuild-binding-targets.json` is public identifier
membership, not a retained content input. See the provenance/privacy audit in
[recipe/README.md](../recipe/README.md#r7r8-host-replay-audit-2026-10-18).

Final validation requires the R8 and importer-identities completion markers, unique regenerated R2/R4
receipts, accepted input identities, all 104 J565 targets in the R2 receipt and
the destination, and every R4 `deferred_to_later_steps` target. Paths must be safe
and present in the provenance map. Missing targets fail the action; missing,
ambiguous or malformed receipts fail closed. R5's graph receipt is required;
`unity_import_deferred` entries must still exist and be `unity-generated`, but
are reported as R9 obligations without requiring their final imported hash.
This checks file placement, not GUID/fileID resolution or runtime readiness.

The original R1–R8 cohorts cover **86,433** files (J571: all identical from an empty
destination; final bindings pass). The new host cohorts below select **352 + 23**
additional paths at J572. The project-inputs extension below adds three more:
**86,811** selected paths and **5,030** R9 obligations (5,028 originally classified
`unity-generated` plus two now assigned explicit editor producers). Selection describes
implemented coverage, not a completed operator replay. No new real-data harness
execution, Unity/device command, shared-work write, journal/state edit or Git
mutation was performed for this change.

## Shader prerequisite and remaining project inputs

The current host order is R1 `assemblies` → `shader-pipeline` → R2 `composition`
→ `project-inputs` → R3–R8 → `importer-identities` → `validate-bindings`. Use the existing rebuild-step
command and `--work-dir`; only the operator runs the real destination replay.
`--compare-only` compares actual bytes for either new cohort without generation.

`shader_rebuild.py` runs the existing `shader_source.generate` (1 output),
`shader_deferred.generate` (129) and `shader_materials.generate` (222). It never
reads the retained final `sources/` bodies. Native program extraction, binding,
roundtrip checks, feature selection and water topology remain in their existing
owners. Scratch/native tool output stays beneath destination `.rebuild/`; final
project placement is buffered through `StageIO`, with per-file map hash/size gates.
Failures or different bytes are listed individually in
`.rebuild/shader-pipeline-result.json` and are **not placed**. A blocked result
fails the step even if an earlier destination happens to contain matching bytes.
Composition requires a complete result bound to the current recipe hash, rechecks
retained inputs and generated source/receipt hashes, then consumes those fresh
sources. Real stage actions still use their historical selections and write paths.
The shared `shader_source.output_directory` preserves all three real output/pointer
paths; isolated calls publish no shared pointers. Synthetic tests exercise both
modes and the refusal boundaries.

**Recovery is still a blocker:** `shader_recovery.recover` requires the pinned
native recovery tools and an already configured CrossOver bottle. It is not
replayed by this host-only step. `recipe/shader-rebuild-inputs.json` pins **46**
retained local files: 15 recovery receipts and 15 original-tree records, three
selected generator receipts, one material census and 12 validated independent
HLSL intermediates. The recipe records the selections, including original-vertex
water topology, instead of reading mutable analysis config pointers. These are
explicit retained inputs, not regenerated recovery evidence. All 46 hashes must
pass before any generator runs. The same five tool revisions in
`shader_recovery.PINS` remain; existing generators verify source pins and the
native d3dasm binary hash recorded by recovery. Isolated fallback uses only the
12 hash-pinned intermediates, never writes a Wine bottle, and refuses absent or
changed programs. A missing host tool blocks the affected outputs individually.
Removing these pins requires isolated recovery/toolchain/census producers.
No J558 inherited body is used as a fallback, ledger status is unchanged and no
inherited store file is retired. Device verification remains a later gate.

Prior-art review: `community-prior-art.md` J364–J371 and pinned d3dasm
`a292206a` `crates/d3dasm-cli/src/main.rs` were inspected. A successful process
can emit `not decompiled` as text; the existing NativePrograms roundtrip and
independently validated fallback contract must remain. EditorKit registration
and dummy shader export do not reconstruct D3D11 program math. No new shader
translation engine or community/game program text is published.

`project_input_rebuild.py` selects **23** files: 17 existing smoke settings
copies, three historical authored editor templates, the generated InputManager,
the explicit Nova importer and regenerated geometry. It uses the shared
`nova_bridge.nova_axes` / `insert_axes` and `prepare.export_geometry` serializers.
The real actions retain their selected output paths. The entire 26-file cohort
must pass map hash/size gates before any project file is flushed, followed by
actual current-project comparison. Geometry uses a public identity/hash recipe
and the legitimate installation, never the previous OBJ. The exact mesh must be
unique and have the recorded name, and both bundle and output hashes must match.
No retained geometry body or private receipt is a runtime input to this step.

The following accounts for **each of the 28** settings-template/unknown files.
Names in the first 18 rows are relative to `ProjectSettings/`.

| File | Producer and disposition |
| --- | --- |
| AudioManager.asset | `prepare.prepare`, exact public smoke template; project-inputs. |
| ClusterInputManager.asset | Same template copy owner; project-inputs. |
| DynamicsManager.asset | Same template copy owner; project-inputs. |
| EditorBuildSettings.asset | Same template copy owner; project-inputs. |
| EditorSettings.asset | Same template copy owner; project-inputs. |
| MemorySettings.asset | Same template copy owner; project-inputs. |
| NavMeshAreas.asset | Same template copy owner; project-inputs. |
| PackageManagerSettings.asset | Same template copy owner; project-inputs. |
| Physics2DSettings.asset | Same template copy owner; project-inputs. |
| PresetManager.asset | Same template copy owner; project-inputs. |
| ProjectVersion.txt | Smoke pin copy, also explicitly copied by J430 stage script; project-inputs. |
| QualitySettings.asset | `prepare.prepare`, exact smoke template; project-inputs. |
| SceneTemplateSettings.json | Same template copy owner; project-inputs. |
| TimeManager.asset | Same template copy owner; project-inputs. |
| UnityConnectSettings.asset | Same template copy owner; project-inputs. |
| VFXManager.asset | Same template copy owner; project-inputs. |
| VersionControlSettings.asset | Same template copy owner; project-inputs. |
| InputManager.asset | `nova_bridge.prepare`: 16 Nova slot-1 axes inserted into the smoke template. `work/experiments/scene-runtime/20261004T010614.329224Z/nova-contract.json` records the exact current hash; project-inputs shares that generator. |
| ProjectSettings/BurstAotSettings_Android.json | Burst 1.8.11 `Editor/BurstPlatformAotSettings.cs`: `InitialiseDefaults`, Android `ShouldSerialiseOut`, ordered `SerialiseOut` and `Save`. Host JSON from public default field settings in project-inputs; complete-byte gate. |
| ProjectSettings/CommonBurstAotSettings.json | Same Burst producer: common serialization selects Version and DisabledWarnings. Host JSON, complete-byte gate. |
| ProjectSettings/GraphicsSettings.asset | Public smoke baseline plus J369's Android tier settings: HDR, FP16 and DeferredShading for all three tiers. Host renderer with baseline SHA-256 and complete-byte gate. |
| ProjectSettings/ProjectSettings.asset | **R9:** Unity PlayerSettings serialization/schema migration plus `android/Assets/Editor/LabBuild.cs:Build`; J367 Linear setting is an explicit prerequisite. Exact-editor output must match the provenance hash; no private settings template. |
| Assets/Editor/CatalogAddressProbe.cs | Exact public Git blob at `ad519fc534c71b78fd5634b9f214ddec102714d0:tools/unity/CatalogAddressProbe.cs`; J430 staging receipt `copied[8]` matches. Pinned authored template; project-inputs. |
| Assets/Editor/RecoveredHudBuilder.cs | Exact public blob at `df6df52b7187630d968389ac4c56aa73ea15bdaa:tools/unity/RecoveredHudBuilder.cs`; J430 receipt `copied[0]` matches. Pinned authored template; project-inputs. |
| Assets/Editor/WholeCatalogHost.cs | Exact public blob at `7e4f63b2a62c8f48bf00596f2df8ffe4a65f7e09:tools/catalog/WholeCatalogHost.cs`; current formatting differs. Pinned authored template; project-inputs. |
| Assets/LabLoadingScene/NovaInputBridge.cs.meta | J430 receipt `copied[57]` proves the current importer. `CharacterMotorOrderProbe` sets -20000; project-layout supplies its GUID. New public ordered-script template renders every field; full map hash gate, project-inputs. |
| Assets/Recovered/geometry.obj | `prepare.prepare` UnityPy Mesh.export, J08. `inventory/geometry-provenance.json` records the current accepted bundle hash, mesh path ID/name and exact output hash; project-inputs replays those identities. |
| Assets/LabLoadingScene/WholeCatalogPreservation/item-behaviors/link.xml | **R9:** `WholeItemBehaviorPreservation.OnPreprocessBuild` in `tools/catalog/WholeCatalogBuild.cs`, introduced at `be691df`, reflects association attributes and serializes XElement. J432 observes associations; accepted-assembly reflection and exact output hash remain editor obligations, without a copied type list/XML body. |

The two explicit R9 obligations are in `recipe/rebuild-r9-obligations.json`.
`validate-bindings` reports each path, producer, setup and map SHA-256/size without
requiring it before import/build. Coverage reports them separately from unknowns;
the private provenance map remains unchanged. Neither classification is an R9 pass.
Burst's existing 1.8.11 package pin is retained; the host JSON fields are defaults,
not a copied private settings file. The package writer uses two-space indentation,
field declaration order and a final newline, so no Unity serializer is required.

Graphics producer evidence: J369 and ignored `work/j369-settings.py` call
`EditorGraphicsSettings.GetTierSettings` / `SetTierSettings` for Android Tier1–3,
setting HDR, FP16 and DeferredShading. Its readback is in
`work/experiments/scene-runtime/20261007T122200.963649Z/android-tier-settings.json`.
The host renderer retains public smoke settings outside that tier node and the
measured defaults within it (quality 0/1/1, GI usage 25, optional flags off).
It checks the smoke baseline hash and empty tier membership before rendering.
No authored C# source is edited by text substitution.

PlayerSettings producer evidence: `LabBuild.cs` lines 103–110 set identity,
IL2CPP/ARM64, SDK levels, automatic install location, keystore/stripping, graphics
API and timing. J367 supplies Linear color space. Compared with smoke, the current
file also adds newer-editor fields (`androidAutoRotationBehavior`,
`useCustomGradleSettingsTemplate`, `syncCapabilities`) and removes AndroidMinifyWithR8.
Those are native editor schema migration, not an authored host constructor.
R9 must import the public baseline, apply the stated settings and prove the full
hash; this host change does not promise that import alone supplies Linear.

**Provenance corrections to apply when its generator is available:** the three
editor sources and Nova importer can change `unknown` → `tool-owned`, with
`project_input_rebuild.project_inputs` and the public template/commit identities;
InputManager and geometry can change `unknown` → `repo-builder`, naming their
shared original generators and the new coordinator. The 17 settings and 352
shader attributions already name the correct original producers. No provenance-map
generator was found in tracked scripts or the searched local Python tools; the
local map is unchanged. Step membership supports both old and corrected categories.
The three newly host-owned settings and two explicit R9 producers supersede the
five earlier unresolved classifications without modifying the private map.

The audit below describes the J566 snapshot before this implementation.


Read-only audit of the shared lab project, accepted input and export, current repo recipes,
and experiment receipts. No builds, editor/device commands, doctor (which writes `work/`),
Git mutations, journal/state edits, or shared-work writes ran. Scratch generators wrote
only beneath the OS temporary directory; audit artifacts are local to this checkout.

The map covers **91,841 regular files, 9,371,820,635 bytes**, using
`project_manifest.AREAS`, `_files`, `_local_path` and the same SHA-256 implementation.
Final membership/sizes were checked again. `provenance-capture.json` additionally records
the two build-external hashes, outside the per-file totals. The accepted reconstruction
pointer selects `work/assetripper/3f02f15f5734bf59/export/ExportedProject`; its input ID agrees
with acceptance, the project generation marker and the inherited ledger.

Each map key has exactly one producer. Priority is exact export bytes (any export path),
then regenerated recipes/store/tool copies, then verified builder output receipts or
scratch regeneration, then positive Unity serialization signatures, otherwise unknown.
This is a reconstruction classification, not proof which historical process last touched
identical bytes. Export matches include metadata and relocated copies. Receipt input
hashes alone were never treated as generated-output proof.

| Producer | Files | Bytes |
| --- | ---: | ---: |
| export-copy | 84,051 | 6,817,648,206 |
| recipe-transform | 267 | 161,835,511 |
| generator | 10 | 4,913 |
| inherited-store | 204 | 2,542,874 |
| repo-builder | 2,107 | 2,305,423,939 |
| unity-generated | 5,028 | 71,808,205 |
| tool-owned | 117 | 2,291,946 |
| unknown | 57 | 10,265,041 |

Counts and bytes by first project folder; **each cell is files / bytes**.
Column abbreviations follow the producer table order.

| Folder | Export | Recipe | Generator | Store | Builder | Unity | Tool | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Assets (root files) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 11,834 | 1 / 6,928 | 0 / 0 |
| Assets/Editor | 1 / 432 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 10 / 2,430 | 6 / 90,032 | 3 / 28,875 |
| Assets/LabLoadingScene | 43 / 42,441 | 62 / 8,241,707 | 10 / 4,913 | 204 / 2,542,874 | 411 / 328,622,777 | 306 / 69,389 | 93 / 2,173,577 | 47 / 10,139,972 |
| Assets/Plugins | 1 / 620 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 1 / 25,088 |
| Assets/Recovered | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 1 / 2,766 | 0 / 0 | 1 / 36,019 |
| Assets/WholeGame | 84,004 / 6,817,603,761 | 204 / 153,592,142 | 0 / 0 | 0 / 0 | 1,696 / 1,976,801,162 | 4,702 / 71,712,796 | 0 / 0 | 0 / 0 |
| Packages | 0 / 0 | 1 / 1,662 | 0 / 0 | 0 / 0 | 0 / 0 | 1 / 8,990 | 0 / 0 | 0 / 0 |
| ProjectSettings | 2 / 952 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 17 / 21,409 | 5 / 35,087 |

## Rebuild order after composition

This is the required dependency order, **not an already executable fresh-project
coordinator**. Existing intermediate config, owner/GUID and frozen-payload dependencies
must become explicit inputs. J565's 104 unresolved bindings belong to the final `validate-bindings` gate.
Before composition, the missing original-assembly initializer is another prerequisite: J430's
ignored `stage-project.py` and `stage-project.json` prove 46 unchanged current DLL outputs,
but no current repo producer places that closure or initializes its generation maps. These
are unknown **producers**, with known legitimate source hashes. J563 covers the three transformed
DLLs separately; the old `scene_runtime.scene_prepare` cannot initialize this generation.

1. **Complete catalog analysis, then import its closure.** `whole_catalog.audit` →
   `native_inventory` → `reconcile` supply accepted catalog metadata, GUID index, native
   conversions and preload/legacy aliases; `prepare_integration`
   (`whole-catalog-prepare`) copies missing owners and remaps UI. Inputs: accepted export,
   original catalog/assembly contracts, current owner map, UI recipe, native mesh records.
   J430/J433/J435/J454/J458 establish expansions. Import receipts prove current outputs
   individually (259 non-export files here); GUID-repair/support-alias exceptions are explicit.
   Host/repair/contracts/provider actions validate readiness; they are not substitute producers.
2. **Apply dependency and optional-content adaptation.**
   `composition_migration.stage_missing_sources` (`composition-update-dependencies`) follows
   runtime/build roots and export GUIDs, calls `whole_catalog.repair_support_source` and
   `integrated_objective.sanitize_optional_content`. J431 receipts prove 1,237 current
   sanitized bodies plus the support source. Inputs include staged plugin/script identities.
   Re-check equivalence after any newly imported closure; blindly replaying the old order is
   insufficient. Earlier `nova_bridge`/`integrated_*` closure constructors are represented by
   export copies, recipes or the store; they are not additional current runtime owners.
3. **Finish reduced stage variants and navigation roots.** `stage_variants.stage`
   (`stage-variants`) calls `nova_bridge.stage_first_stage_geometry` and `scene_contract`.
   J441/J452/J484/J488 result receipts prove 16 later reduced scenes; the original seven are
   composition recipes, with two final J431 scene-contract repairs. Inputs: exact export
   scenes, imported graphs, manifest pool keys, intermediate configs and
   `whole-catalog-code-base.json`. That frozen baseline and pending-stage logic make this
   historical action unsuitable for direct empty-project replay without refactoring.
4. **Generate all 23 full source scenes.** `source_scene_candidate.prepare`
   (`source-scene-prepare --target all`), J459/J484/J488: accepted scene YAML, input ID and
   UI remaps produce 23 bodies and 23 importers, all scratch-compared equal. Candidate receipt
   proves the bodies. The action also calls `stage_unavailable_audio`; its two DLLs are already
   covered by J563's assembly recipe, so orchestrate that boundary once from originals.
5. **Generate build-entry inputs.** `whole_catalog.build_integration`
   (`whole-catalog-build`/`whole-catalog-code-build`, latest full execution J551):
   `build.generate_runtime_config`/`generate_content_recipe` use the public recipes;
   `body_visual_map.generate` (J475/J476) and `common_assets_map.generate` (J477) use accepted
   decompilation, aliases and manifest; `animation_bindings.repair` (J475) uses export clips
   and imported controller CRC names; `original_stage_contexts` uses export scene fields and
   manifest pool identities. Scratch equality proves three C# maps, 181 clips, stage contexts
   and bootstrap JSON; config bytes equal the recipe. No output-hash receipt proves all these
   products together, so retain the new per-file oracle.
6. **Stage sources and generate linker roots, then import/build.** The same owner copies the
   92 declared runtime sources and editor fixtures; `preservation_descriptor` (J506) uses
   manifest/contracts/progression roots, scratch-compared equal. `build.build` copies
   `android/Assets`. `WholeItemBehaviorPreservation.OnPreprocessBuild` derives the separate
   item-behavior linker file: its current complete output is an explicit R9 obligation above.
   `LabBuild.Build` serializes the scaffold scene/settings; Unity resolves packages/imports.
   Build/payload receipts prove builds, not deterministic reserialization of every input.

Shader recovery is a **composition prerequisite**, not an omitted post-stage builder:
`shader_recovery.recover` → `shader_source.generate` / `shader_deferred.generate` /
`shader_materials.generate` (`shader-source*`) consume native programs/layouts, material
census, selections and pinned tools. J431 selected receipts prove all **352 current shader
pipeline outputs**. Nine recipe-owned importers and the TMP include also compare equal.
`presentation.build_payload` stages presentation sources/reflection import settings for
historical payload variants; it is not a required second invocation after the full build.
The 204 store-attributed current files are hash-verified and normalized where necessary;
other retained store bodies are overwritten by selected current shader outputs.

## R2 inherited-file host replay

`inherited_rebuild.py` supplies per-file candidates only during destination replay.
`inherited_state.prepare` still requires the complete ledger selection and validates
every chosen byte stream against its original ledger hash and every importer GUID.
A generated matching file replaces only that file's store read; all remaining
files retain the existing store/path/hash/GUID gates. `read_pair`, capture and the
store integrity check are unchanged. The production stage keeps its original
store placement and later shader replacement order.

Of the **204 store-attributed current paths**, **187 are importers and 17 are
bodies**. In particular, the 166 used native shaders in J558 contribute importers
here; their current bodies are already among the 352 shader-pipeline outputs and
differ from the inherited ledger bodies. Regenerating importers does not establish
byte reproduction of those older shader bodies or satisfy J558's device gate.

| Group | Regenerated | Still inherited | Reason/owner |
| --- | ---: | ---: | --- |
| Shader importers | 167 | 0 | Existing `authored_additions.shader_importer`, original public ledger GUID/hash. Includes the recovered TMP mobile shader importer alongside the 166 used native shader importers. |
| TMP include importers | 3 | 0 | Same existing include-importer schema. |
| Text importers | 4 | 0 | Authored TextScriptImporter schema and ledger identity. |
| Material importers | 7 | 0 | Authored NativeFormatImporter schema, mainObjectFileID 2100000. |
| Prefab importers | 3 | 0 | Authored PrefabImporter schema; FastDirector retains its original empty-field whitespace. |
| Sprite/settings importers | 2 | 0 | Authored NativeFormatImporter schema, IDs 21300000 / 11400000. |
| Elite ramp importer | 1 | 0 | Accepted export texRampElites.png.meta, pinned source hash, inherited GUID and creation-time parameters only. |
| TMP include bodies | 3 | 0 | Existing hash-gated TMP 3.0.6 Essential Resources archive reader; no package content tracked. |
| FastDirector.prefab | 0 | 1 | Existing stage_enemy_spine rejects stale catalog/scene record identities; needs reviewed rebase (J562). |
| FontMaterial0–4.mat; NativeUiMaterial0–1.mat | 0 | 7 | RecoveredHudBuilder uses Unity material cloning/AssetDatabase serialization; exact-editor fixture needed. |
| Hud.prefab; Menu.prefab | 0 | 2 | Same builder, PrefabUtility serialization/local object IDs. |
| Owned full-rectangle texCrosshairNibBar.asset; TMP Settings.asset | 0 | 2 | Same builder, Sprite.Create / SerializedObject and AssetDatabase identities. |
| Strings.json | 0 | 1 | Current accepted English merge differs from inherited bytes (J562). |
| TMP_SDF-Mobile.shader | 0 | 1 | Pinned TMP package shader differs from inherited bytes (J562). |
| **Total** | **190** | **14** | No ledger entry retired or relabelled. |

The destination `.rebuild/inherited-rebuild-result.json` and composition replay
result list each regenerated path, each retained path/reason and both counts.
Candidates with different hashes remain inherited. The 352 shader outputs retain
their native-recovery/CrossOver limitation: shader recovery itself still requires
a native tool run and the existing 46 hash-pinned shader inputs. This extension
adds **zero retained local analysis records** (63 remain), one accepted-export
importer identity/hash, the public smoke GraphicsSettings baseline hash and three
TMP source selectors/hashes under the **existing** package/archive pins.
It does not run native recovery, Unity, devices or the real-data harness.

## Original provenance-map unknowns and limits

This table records the original J566 classification, not the current replay
coverage. The producer/disposition table above supersedes its settings/editor/OBJ
hypotheses; R1 supplies the original assemblies. The private map is unchanged.

| Folder | Files | Bytes | Files |
| --- | ---: | ---: | --- |
| Assets/LabLoadingScene | 47 | 10,139,972 | 45 original DLLs; NovaInputBridge.cs.meta; item-behaviors/link.xml |
| Assets/Recovered | 1 | 36,019 | geometry.obj |
| ProjectSettings | 5 | 35,087 | BurstAotSettings_Android.json; CommonBurstAotSettings.json; GraphicsSettings.asset; InputManager.asset; ProjectSettings.asset |
| Assets/Editor | 3 | 28,875 | CatalogAddressProbe.cs; RecoveredHudBuilder.cs; WholeCatalogHost.cs |
| Assets/Plugins | 1 | 25,088 | SimpleJSON.dll |

The largest unknown group is the original DLL closure placed by that local script.
The OBJ has a matching `inventory/geometry-provenance.json` output hash and a known
`prepare.prepare` exporter (J08), but no experiment output receipt or original-bundle replay
was established here. The five settings differ from repo templates: likely inherited
editor/Burst/InputManager settings plus partial `LabBuild` changes, without a complete
constructor. The three editor sources likely predate formatting/reorganization; basename
matches are insufficient. The Nova importer likely combines Unity allocation with
`CharacterMotorOrderProbe`'s -20000 order. The item-behavior XML likely comes from the
reflection callback above (J432), but its full current bytes lack the required proof.
Each unknown map entry contains its individual hypothesis.

**Unity-generated is origin evidence, not byte-equivalence proof:** 4,811 default/folder/
texture importers match concrete Unity schema signatures; 200 native assets have valid
SerializedFile v22 headers, exact editor version and preserved source GUIDs; 14 custom
render textures differ only by serializer field ordering. Scaffold, lockfile and OBJ importer
have explicit Unity ownership evidence. Their GUIDs/settings/allocated IDs still need retention
or isolated exact-editor fixtures. Likewise, recipe dependency bytes match the package manifest,
but J547 supplies a checker rather than a complete initializer. No game readiness is inferred.

## R9: isolated Unity import/build (current; not yet equivalent)

Status (J582, J583): from a fresh Library, R9 builds an APK that passed both device checks,
but reports it unequal. The extra `Unity.Timeline.dll` linker root matches the working
project's own full builds; the reimport errors come from batch import order; why
`Hidden/Compositing` drops out is still open. R2 still reads local migration evidence; see
[ARCHITECTURE.md](ARCHITECTURE.md#known-structural-debt).

`unity-build` runs only after a passing `validate-bindings` on the same destination.
Both R9 host preflight and the direct build entry refuse missing or mismatched
destination manifest/bootstrap input or attempt identities before invoking Unity.
Destinations generated before this check require R3 and R7 replay; changing only
the bootstrap would leave the payload inconsistent.
`scripts/lab/unity_rebuild.py` coordinates the read-only host preflight, exclusive R9
lock, batch invocation and comparisons. It calls the destination parameter of
`whole_catalog.build_integration` → `build.build` → `LabBuild.BuildDestination` →
the existing `LabBuild.Build`. R1–R8 already supply the host products; R9 does not
rerun those generators or follow live analysis pointers. `WholeCatalogBuild.Append`
and `Complete`, including the item-behaviour preprocessor, run unchanged. This is a
full bundle/content and IL2CPP player build; payload reuse is refused.

The exact editor uses the destination as `-projectPath`, with its own default
`Library/`. The batch entry checks the complete editor version/revision, applies
Linear colour space to the public smoke PlayerSettings baseline, and invokes the
normal build settings/serializer. It saves assets before exiting. The destination
gets refreshed authored Android editor sources; this can change their R8 byte
comparison relative to the older staged source, independently of R9's groups.

All requests, logs, APKs, generated payload, Android home, Gradle files and terminal
receipts go under `<destination>/.rebuild/unity/<attempt>/`. The comparison receipt
is `<destination>/.rebuild/unity-build.json`; failed attempts remain available.
The shared project's files/Library, current-build pointer, installed receipts,
payload/cache and rollback receipts are never written by R9. The ordinary build's
paths, cache-key formula, payload reuse and receipt publication stay the same
(the existing tool-source hash naturally changes when `build.py` changes).

R9 refuses a destination or working-project editor found in the process table or
by `Temp/UnityLockfile`; it never removes Unity's lock. Its own exclusive
`.rebuild/unity-build.lock` refuses overlapping R9 commands. Keep both editors
closed for the whole operation; do not open either while R9 runs. After an
interruption, inspect the process/log evidence before manually removing a stale
R9 lock. The live editor's cache is never cleared.

For an in-place update, R9 requires the existing debug signing key at the input
clone's `.local/android-user/.android/debug.keystore`. It copies that key into the
ignored destination Android home with mode 0600, without changing the original.
No new signing identity or custom keystore PlayerSetting is introduced. The key
copy is private local state generated by `unity_rebuild.execute_build`, never a
public recipe/output.

Comparisons retain actual SHA-256 values, with no normalization:

- `r9_obligations`: both paths from `rebuild-r9-obligations.json`.
- `unity_import_deferred`: every graph in the R5 receipt (28 at J573).
- `unity_generated`: every provenance row with that producer (5,028 at J573).
  Each group reports identical/different counts and per-path current/destination
  hashes, plus whether the destination also matches the recorded provenance hash.
  Missing files are different and retain null hashes. These cohorts overlap.
- `apk`: every entry name, uncompressed size and hash in the destination and the
  device-verified reference named by `BASELINE.md`, located through local receipts
  and independently hash-checked. Added/missing entries stay explicit. ZIP timestamps,
  compression, compressed sizes and extra-field hashes are reported separately.
  A changed `level0` is classified as script/type-hash-only **only** when the pinned
  UnityPy type reader identifies unique hash fields and every other byte is equal;
  offsets and both field values are retained. Other scene changes stay unexplained.
  Signing metadata, native binary changes, possible Unity build metadata and all
  other unexplained content changes receive separate classifications. Candidate
  metadata labels are observations requiring review, never equivalence assertions.

A project hash mismatch exits nonzero **after** saving the successful build and
comparison receipt; it does not delete the APK. APK byte differences are reported,
not treated as proof of a failed or successful runtime rebuild. Review them and
run both device checks. `--compare-only` recomputes comparisons without importing,
building or writing receipts. It verifies the destination APK's saved hash first.

### Exact operator sequence in this checkout

The destination must already contain the eleven host steps and their markers.
Use its actual path below if you selected a non-default `--dest`. These commands
are operator actions, not evidence that this implementation has run in Unity.
If this worktree lacks its interpreter link, create it once:

```sh
mkdir -p .local
ln -s "$(cd ../../lab-venv && pwd -P)" .local/lab-venv
```

Close both project editors, then run from this checkout:

```sh
LAB_INPUTS="$(cd ../../../work && pwd -P)"
LAB_PYTHON="$PWD/.local/lab-venv/bin/python"
LAB_INPUT_ID="$("$LAB_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["input_id"])' "$LAB_INPUTS/config/accepted-input.json")"
LAB_DEST="$PWD/work/rebuild/$LAB_INPUT_ID/lab-project"

./dev preflight --dest "$LAB_DEST" --work-dir "$LAB_INPUTS"
./dev prototype --action rebuild-step --step unity-build --dest "$LAB_DEST" --work-dir "$LAB_INPUTS"
```

Review `.rebuild/unity-build.json` even if the comparison exits nonzero. To repeat
only the comparison:

```sh
./dev prototype --action rebuild-step --step unity-build --dest "$LAB_DEST" --work-dir "$LAB_INPUTS" --compare-only
```

After reviewing the result, extract the exact APK/payload and rollback paths from
that destination receipt, then use the **existing** device installer/sync/checks:

```sh
LAB_RECEIPT="$LAB_DEST/.rebuild/unity-build.json"
LAB_APK="$("$LAB_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["build"]["apk"])' "$LAB_RECEIPT")"
LAB_PAYLOAD="$("$LAB_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["build"]["payload_directory"])' "$LAB_RECEIPT")"
LAB_GOOD_APK="$("$LAB_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["reference_apk"])' "$LAB_RECEIPT")"

./dev install --work-dir "$LAB_INPUTS" --apk "$LAB_APK"
./dev run --work-dir "$LAB_INPUTS"
./dev sync-data --work-dir "$LAB_INPUTS" --payload-dir "$LAB_PAYLOAD"
./dev check-baseline --work-dir "$LAB_INPUTS"
./dev check-baseline --work-dir "$LAB_INPUTS" --stage-exit
```

`run` discovers the installed player's runtime data path before sync. These explicit
**device actions** write the existing device/run evidence in the selected work tree;
rebuild/preflight `--work-dir` remains read-only. Installation still requires the
configured device and ownership receipt, queries current storage/free space, and
verifies APK identity, adopted placement and runtime backing through existing
`Device` methods. The current-build pointer remains the known-good build, so the
destination baseline reports `is_current_build: false` while recording its installed
APK hash. Its runtime selection is R8's public config, equal to the live config.

Restore the current device-verified APK **and original payload** afterwards:

```sh
./dev install --work-dir "$LAB_INPUTS" --apk "$LAB_GOOD_APK"
./dev run --work-dir "$LAB_INPUTS"
./dev sync-data --work-dir "$LAB_INPUTS"
./dev check-baseline --work-dir "$LAB_INPUTS"
./dev check-baseline --work-dir "$LAB_INPUTS" --stage-exit
```

No uninstall, storage changes or receipt swapping is needed. Device acceptance,
including restore validation, remains the operator's responsibility. Host tests
with mocked Unity/subprocess are in `tests/test_unity_rebuild.py`.


### Destination script import gate

`LabBuild.BuildDestination` alone owns the post-compilation plugin reimport.
All managed DLL assets are included, covering `Assets/Plugins`, the original
plugins under `Assets/LabLoadingScene/Plugins`, and alternate managed-plugin
locations. Native DLLs are excluded. Selected dependency consumers are imported
in dependency order after the DLLs; no Library reset or working-project mutation
is involved. An unsettled compilation/import refuses the build. This is the
narrow import-order hypothesis from J576/task-720; exact-editor verification
remains for the operator.

Before any call to the unchanged `LabBuild.Build`, the gate loads the recovered
HUD/Menu, including inactive children, and rejects missing scripts or a null
TimerText `targetLabel`. HUD must contain a TimerText. It also counts missing
scripts for every selected prefab/scene and their transitive dependencies;
non-UI counts remain comparison evidence rather than an assumed zero baseline.
Unreadable assets fail. Scenes use preview scenes and close even on failure;
prefabs are read as assets without instantiation or saving.

The destination run contains `build-selection.json`, `lab-build/script-imports.json`
and `lab-build/script-audit.json`. The audit includes zero-count rows, total
missing components, TimerText counts/targets, errors, and every imported
MonoScript's GUID/local ID and resolved assembly-qualified type (including
package scripts). The successful destination `result.json` includes this full
audit as `script_audit`. Failed attempts retain their available receipts. Error,
exception and assertion messages during repair/audit are counted without message
allowances; the real build retains its original report-error handling.

To compare the working editor without staging files there, generate MCP arguments
from the **same destination run selection**:

```sh
../../lab-venv/bin/python scripts/lab/script_audit.py --selection "$RUN/build-selection.json"
```

Pass that JSON object to the lab MCP editor's `execute_code` tool. It executes the
exact shared audit body in memory, without reimport, save, refresh, or file writes.
Save the raw JSON string returned as `data.result` to a local `working-script-audit.json`
outside the working project, then compare:

```sh
../../lab-venv/bin/python scripts/lab/script_audit.py --compare working-script-audit.json "$RUN/lab-build/script-audit.json"
```

`RUN` is the destination attempt directory beneath `.rebuild/unity/`. Comparison
requires identical selections, reports per-asset count differences even when
totals match, and fails for every resolved working MonoScript whose GUID/local ID
is absent, unresolved, or bound to a different type in the destination. The
working editor does not need an updated LabBuild source. Run the comparison after
R9 has exited; existing R9 editor-lock rules still apply.

Prior art consulted for this change: the pinned RoR2ImportExtensions
[`AssemblyBlacklist`](https://github.com/risk-of-thunder/RoR2ImportExtensions/blob/477ad9b52e66e59080049fc3a65645ddb4db2cef/Editor/AssemblyBlacklist.cs)
shows package-dependent exclusion of duplicate providers; retain our accepted
providers and import them after package compilation. The pinned EditorKit
[`AddressablesPathDictionaryCache`](https://github.com/risk-of-thunder/RoR2EditorKit/blob/4128710f74ffbd90bfebc523812e7155fa7bdee3/Editor/RoR2/AddressablePathDictionary/AddressablesPathDictionaryCache.cs)
uses loaded component inspection for typed queries. That supports checking actual
Unity objects rather than accepting serialized reference presence alone. Neither
source establishes that this reimport repairs Android reconstruction; the new
gate and operator comparison measure that contract. Host coverage:
`tests/test_script_audit.py`, its authored Unity doubles, and
`tests/test_unity_rebuild.py` (mocked subprocesses).

## Pre-import importer identities (current)

The first operator R9 attempt stopped before Unity at the missing
`Assets/LabLoadingScene/LabExperiments.cs.meta` layout check. The host order now
includes `--step importer-identities` after R8 `runtime-sources`, before
`validate-bindings` and `unity-build`. It requires R8's accepted-input completion
marker and existing script/shader bodies. Other lab asset metas may precede their
R9-generated bodies (Lab scene and item-behaviour XML). Folder importers are not
placed (J575): Unity mints them at import, and R9 classifies each folder meta as
`folder_guid_minted` (only its GUID line differs) or `empty_folder_absent` (the
working-project folder holds no files), and re-runs the folder-GUID reference
scan on the minted GUIDs; any reference fails R9.
The coordinator retains its byte comparison against the current project and
supports `--compare-only`; only the operator executes the real destination step.

Public `recipe/importer-identities.json` supplies complete cohort membership.
The 91 selected runtime script identities use project-layout GUIDs; 14 additional
script identities are recorded explicitly. All 105 selected scripts have order 0;
NovaInputBridge's already placed -20000 importer remains owned by project-inputs.
Six shared public schemas render all settings without reading the working project
as generator input. Provenance remains unchanged on disk: step membership assigns
these 286 originally `unity-generated` rows to host reconstruction, and R9's
remaining editor comparison subtracts exactly that selected membership.
The identity/privacy decision is audited in
[recipe/README.md](../recipe/README.md#pre-import-importer-identity-audit-2026-10-18).

Read-only real-data checks rendered 3,227 folder, 105 script, 175 shader and six
other asset importers (one scene, two JSON, two XML, one OBJ). All **3,513/3,513**
match the current project byte-for-byte and the local provenance SHA-256/size.
The folder group was then removed from the public recipe (J575, below), leaving 286.
A temporary host overlay of these importers, the destination's existing ordered
Nova importer and its manifest passes `build.validate_project_layout`. This is
not destination placement: the actual harness remains an operator action.

The read-only folder-GUID scan measured **zero referencing files** among 77,788
YAML/importer/JSON/XML or serialized files under destination `Assets/`, including
33,773 serialized assets and zero binary serialized assets. Importers' own
`guid:` declaration lines are excluded; external importer references are included.
Every selected body is scanned for text GUID tokens; binary serialized files, if
present on a later replay, also get conservative raw GUID byte/word-order scans.
The step regenerates this measurement in its destination result receipt. The
scan establishes the measured absence of references, rather than authorizing
new identities or dropping original GUIDs.

Host membership increases from 86,811 to **90,324** rows. R9 retains **1,515**
`unity-generated` rows: 1,299 other asset importers, 200 native `.asset` files,
14 custom render textures, `Assets/Lab.unity` and `Packages/packages-lock.json`.
The two explicit R9 obligations (`ProjectSettings.asset` and the item-behaviour
linker XML) remain separate, giving **1,517** total editor-owned rows. The 41
R5 graph reserializations remain inside that native-asset cohort. No Unity result,
APK, runtime readiness or device acceptance follows from these host checks.
The destination's absent Lab scene, item-behaviour XML and package lock are still
left to R9, rather than copied from the old project.
