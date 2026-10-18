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
and 204 inherited-store files (assembly paths remain R1). Canonical closure
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
unresolved identifiers are preserved. `validate-bindings` runs last, after R8. Synthetic host tests cover staging
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
the historical bootstrap attempt identity. Each is hash-pinned; none is claimed
regenerated. Together with R3/R4's ten and R5's two, there are **17** retained
local input records. `recipe/rebuild-binding-targets.json` is public identifier
membership, not a retained content input. See the provenance/privacy audit in
[recipe/README.md](../recipe/README.md#r7r8-host-replay-audit-2026-10-18).

Final validation requires the R8 completion marker, unique regenerated R2/R4
receipts, accepted input identities, all 104 J565 targets in the R2 receipt and
the destination, and every R4 `deferred_to_later_steps` target. Paths must be safe
and present in the provenance map. Missing targets fail the action; missing,
ambiguous or malformed receipts fail closed. R5's graph receipt is required;
`unity_import_deferred` entries must still exist and be `unity-generated`, but
are reported as R9 obligations without requiring their final imported hash.
This checks file placement, not GUID/fileID resolution or runtime readiness.

The original R1–R8 cohorts cover **86,433** files (J571: all identical from an empty
destination; final bindings pass). The new host cohorts below select **352 + 23**
additional paths, for **86,808** selected paths and **5,033** unselected paths:
5,028 `unity-generated` R9 obligations and five unresolved files. Selection describes
implemented coverage, not a completed operator replay. No new real-data harness
execution, Unity/device command, shared-work write, journal/state edit or Git
mutation was performed for this change.

## Shader prerequisite and remaining project inputs

The current host order is R1 `assemblies` → `shader-pipeline` → R2 `composition`
→ `project-inputs` → R3–R8 → `validate-bindings`. Use the existing rebuild-step
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
The real actions retain their selected output paths. The entire 23-file cohort
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
| ProjectSettings/BurstAotSettings_Android.json | **Unresolved:** package-generated v4 Burst settings; no complete tracked constructor or matching public template found. J430 local stage script only inherits the settings directory, without individual settings output hashes. Keep out of placement. |
| ProjectSettings/CommonBurstAotSettings.json | **Unresolved:** package-generated v4 warning settings; same inherited-directory limitation, no tracked complete producer. |
| ProjectSettings/GraphicsSettings.asset | **Unresolved:** smoke template plus three Android deferred/HDR tier overrides. No tracked tier-setting producer found. Runtime presentation requires linear/HDR but does not serialize these settings. |
| ProjectSettings/ProjectSettings.asset | **Unresolved:** `android/Assets/Editor/LabBuild.cs` sets player/backend/API values only partially. Current bytes also include newer editor schema and linear color space; no complete host constructor. |
| Assets/Editor/CatalogAddressProbe.cs | Exact public Git blob at `ad519fc534c71b78fd5634b9f214ddec102714d0:tools/unity/CatalogAddressProbe.cs`; J430 staging receipt `copied[8]` matches. Pinned authored template; project-inputs. |
| Assets/Editor/RecoveredHudBuilder.cs | Exact public blob at `df6df52b7187630d968389ac4c56aa73ea15bdaa:tools/unity/RecoveredHudBuilder.cs`; J430 receipt `copied[0]` matches. Pinned authored template; project-inputs. |
| Assets/Editor/WholeCatalogHost.cs | Exact public blob at `7e4f63b2a62c8f48bf00596f2df8ffe4a65f7e09:tools/catalog/WholeCatalogHost.cs`; current formatting differs. Pinned authored template; project-inputs. |
| Assets/LabLoadingScene/NovaInputBridge.cs.meta | J430 receipt `copied[57]` proves the current importer. `CharacterMotorOrderProbe` sets -20000; project-layout supplies its GUID. New public ordered-script template renders every field; full map hash gate, project-inputs. |
| Assets/Recovered/geometry.obj | `prepare.prepare` UnityPy Mesh.export, J08. `inventory/geometry-provenance.json` records the current accepted bundle hash, mesh path ID/name and exact output hash; project-inputs replays those identities. |
| Assets/LabLoadingScene/WholeCatalogPreservation/item-behaviors/link.xml | **Unresolved host replay:** `WholeItemBehaviorPreservation.OnPreprocessBuild` in `tools/catalog/WholeCatalogBuild.cs`, introduced at `be691df`, reflects association attributes and serializes XElement. J432 proves 84 association types but not this full file's output hash. Requires a host reflection/serialization replay or exact-editor fixture, not a copied type list/XML body. |

The five unresolved files are listed in coverage with their original evidence.
The smoke settings history is the public baseline at `da6d1e8`; no tracked later
settings constructor was found. J430's ignored `stage-project.py` lines 13–15
copy inherited ProjectSettings and replace ProjectVersion only. That directory
copy is historical evidence, not a fresh producer. No full private settings file
or reflected game type list is added to public templates.

**Provenance corrections to apply when its generator is available:** the three
editor sources and Nova importer can change `unknown` → `tool-owned`, with
`project_input_rebuild.project_inputs` and the public template/commit identities;
InputManager and geometry can change `unknown` → `repo-builder`, naming their
shared original generators and the new coordinator. The 17 settings and 352
shader attributions already name the correct original producers. No provenance-map
generator was found in tracked scripts or the searched local Python tools; the
local map is unchanged. Step membership supports both old and corrected categories.
These six corrections do not authorize reclassifying the five unresolved files.

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
   item-behavior linker file: its current complete output remains unknown below.
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

## Unknowns and limits

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
