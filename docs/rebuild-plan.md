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
must become explicit inputs. J565's 104 unresolved bindings remain a coordinator barrier.
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
