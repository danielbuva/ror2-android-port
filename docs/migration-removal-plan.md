# Removing the composition migration chain

Phase 2 plan for the rebuild blockers in [LOCAL_STATE.md](LOCAL_STATE.md) (B1, B3–B8): build
the Unity project directly from the accepted input, the export and audited
[recipes](../recipe/README.md), instead of migrating a previous project. Analysis by Codex
(gpt-6.1-sol), line references checked by Claude, 2026-10-17. Status: commit 2's
source-membership half is done (`recipe/runtime-sources.json`, J509); its metadata and
package/settings half and commits 1 and 3–9 are open. Line numbers drift; re-check before
use.

Read-only analysis, 2026-10-17. Tracked source, policy, architecture, LOCAL_STATE,
ADR-001, and journal J430/J431/J508 were consulted. Shared local evidence was
inspected for schemas, counts and file presence only; no asset contents or values
are reproduced. No doctor, preflight, build, editor or device operation ran.
Python filenames below are under `scripts/lab/` unless qualified.

## 1. Present read/write sequence

| Order | Reads, meaning and writes |
| --- | --- |
| 1 | `composition_migration.py:181–193`: preflight; B1 selection supplies accepted input, evidence, rollback and shader locations. Read reconstruction's exported project, acceptance and existing `.port-input.json`; reject generation mismatch/self-rollback. This requires an initialized project already. |
| 2 | `composition_migration.py:194–220`: B3 semantic plan describes old/source/target files, expected hashes and conflicts. Read catalog GUID index, scan current metadata for unique owners, read audited UI remaps. B4 asset-analysis rows identify previous assets, source associations, kinds and GUIDs; B5 supplies old→current GUID substitutions. Conditional B6 associates removed bindings with absent current assembly types and checks assembly hash. |
| 3 | `composition_migration.py:226–277`: combine source overrides, GUID owners and analysis into asset-path mappings; select additions beneath the lab asset root, excluding scripts/editor/linker/bootstrap files. Recursively retarget B8 previous runtime config and existing `scene-probe-build.json`, dropping specified obsolete list bindings/prefabs. Check the exported cost prefab contract; write missing-binding diagnostics on failure. |
| 4 | `composition_migration.py:278–308`: verify B7 preview bytes, current export, previous adapted bytes and existing target hashes against B3. Copy selected previous additions plus metadata, normalizing YAML GUID/UI references; copy preview files and create missing metadata from export. These are project mutations. |
| 5 | `composition_migration.py:312–338`: shader directories contain recovered/generated source plus adjacent success/file-hash receipts. Copy every selected file; delete unselected native shader files/metadata. Native-global-texture rows select exported PNGs, resource aliases and hashes; compare importer metadata excluding GUID/time, replace bytes while retaining target metadata. Existing targets are required. |
| 6 | `composition_migration.py:339–350`: stage authored presentation C#; set attempt/pause options, write runtime config/build recipe, invoke dependencies below, refresh reduced-scene callback/mesh contracts from export (`:103–116`), rewrite config and emit scene-contract evidence. |
| 7 | `composition_migration.py:353–374`: validate original/transformed assembly placement; restore execution orders from legitimate native metadata (`:25–56`). Follow old runtime-attempt pointer to physical-input mapping and hash-check its observation. Write new mapping, assembly/config attribution, script-order and staging receipts; replace runtime current pointer. This extra historical chain is outside B1/B3–B8. |
| 8 | `stage_missing_sources`, `composition_migration.py:119–172`: preflight; read export/catalog pointers, GUID index, selection, generation, UI recipe and both configs. Collect missing asset roots; reject missing authored roots/DLL imports. Traverse exported YAML GUID references, reuse existing owners, copy missing asset/meta pairs and remap UI. Unknown external GUIDs are recorded, not automatically fatal. |
| 9 | `composition_migration.py:173–177`: qualify one recovered support-source alias (`whole_catalog.py:560`); sanitize optional presentation, modifying prefabs/assets **and build roots** (`integrated_objective.py:290–395`). Require root files to exist; write dependency receipt. Validation after earlier writes means staging is not transactional. |

## 2. Policy classification

Classes: **a** audited authored recipe; **b** generator from accepted input/export;
**c** ignored game-derived output; **d** unnecessary for direct composition.
Policy basis: `recipe/README.md:10–21`; prefer generators over published evidence.

| Input | Classification and evidence |
| --- | --- |
| B1 selection | **a** minimal semantic selections/options; **d** evidence/previous-project/shader-run pointers and migration-only renames. Private locations remain local. Fields are selectors, not asset contents (`composition_migration.py:184–187,211,312,330`). |
| B3 semantic plan | Existing report **d**; current-only transformation plan **b**. `serialization_rebase.py:230,289` nearly provides matching/merge semantics, but requires old base/adapted text; it cannot infer adaptations from current export alone. |
| B4 asset analysis | Historical old/current census **d**; replacement ownership/membership census **b**, outputs **c**. Reuse metadata enumeration and collision resolution in `whole_catalog.py:76,352–372`. Independently authored selections are **a**. |
| B5 rebase/GUID map | Historical GUID translation **d**; current GUID index/repairs **b/c** (`whole_catalog.py:76–101`). Keep public UI identity remaps **a**, already audited; do not publish full game maps. |
| B6 removed-state types | Current type-absence checking **b**, report **c**; old removal list **d** after current-only bindings. `tools/AssemblyProbe/Program.cs:25–49` enumerates metadata, but permits filtered results: hash plus omitted names alone does not prove exhaustive absence. |
| B7 preview tree | **c**, regenerated by current transformations; historical preview dependency **d**. Local schema shows 222 planned outputs, not a public recipe. |
| B8 previous project | Mixed **a/c/d**: extract independently authored policy; regenerate assets/config facts/metadata; eliminate tree inheritance. Selection currently includes 229 additions of mixed kinds. Neither file extension nor “generated” proves independent authorship. |
| Shader sources | Generated programs/ShaderLab **c**; selection/binding policy **a**; regeneration **b** via `shader_recovery.py`, `shader_source.py:110`, `shader_deferred.py:63`, `shader_materials.py:48`. Material census/analysis-selection producers remain missing (`LOCAL_STATE.md:151–155`). |
| Native global textures | Minimal role/resource selection **a**; source identity/importer derivation **b**; PNG/importer output **c**. Existing hash/importer checks establish identity, not distribution permission. |
| Other prerequisites | Acceptance/private configuration remain operator inputs. Export/catalog/index **b/c** (`recovery.py:35`, `whole_catalog.py:333`). Runtime/build configuration mixes **a/b/c**; old physical mapping is local operator evidence, never a public recipe. |

## 3. Nine separately verifiable commits

All checks below are proposed, not performed. Keep separate migration-stage and
current-build oracles: J431 reduced previews must not overwrite later source-scene
work (J459 onward). Hold attempt/time constant for comparisons. Compare complete
file membership and bytes, including metadata, Packages/ProjectSettings and external
recipe/manifest hashes (`build.py:107–121`); runtime attempt is itself hashed.

| Commit | Change | Equivalence proof | Risk |
| --- | --- | --- | --- |
| 1 | Add isolated manifest/diff harness and synthetic conflict/drift fixtures; retain local baseline receipts. | Untouched current input set; negative fixtures fail closed. | Low: incomplete oracle. |
| 2 | Add audited `recipe/project-layout.json`: explicit authored source membership, metadata identities, packages/settings; replace membership-by-existing-file (`build.py:78`, `whole_catalog.py:1090`). | Same staged source/meta set and bytes. | Medium: omitted serialized script identity. |
| 3 | Add `recipe/composition.json` and generators for runtime/build configs: authored options/selectors plus generated current bindings/contracts/report defaults. | Full generated JSON bytes match baseline; audit every omitted field's consumers. | High: settings/report ambiguity. |
| 4 | Add `recipe/asset-transforms.json`; re-express adaptations as current-source operations, using serialization helpers, sanitization and source-scene builders. No copied YAML patches. | Each adaptation and scene-contract output matches its appropriate oracle. | High: hierarchy/field ambiguity. |
| 5 | Generate every remaining addition and importer from authored constructors or accepted export; reuse tracked shader/include sources where applicable. | All selected asset/meta pairs match; every input has provenance. | High: undocumented hand edits. |
| 6 | Add `recipe/shader-selection.json`; generate material census, analysis selection and existing recovery/binding chain; derive texture importers without old targets. | Same generated files, variants, texture/importer bytes and pinned receipts. | High: external tool/fallback determinism. |
| 7 | Initialize clean project/generation maps; orchestrate existing AssemblyProbe guards from originals, preserving exact transform order, identity and script orders. `prepare.py:38` alone lacks assembly maps. | Same plugin bytes/importers, hashes and settings; synthetic transformation contracts. | High: hidden assembly initialization. |
| 8 | Compose in a separate destination from current export/recipes; parameterize dependency importer; generate current owners, closure and explicit absence proofs. Replace old-attempt lookup with named local mapping receipt, required only by its actual consumers. | Same complete build inputs with historical paths denied; repeat from empty destination. | High: closure/bootstrap cycles. |
| 9 | Switch `composition-update-stage` to direct producer; remove current B1/B3–B8 and `previous_project` reads; document ownership/setup/teardown. Keep historical receipts/rollbacks. | Denied-history test plus identical cache input set; later exact-editor/device baseline gates before acceptance. | Medium: orchestration/attribution. |

Each implementation commit records provenance/privacy review in recipe README and
runs staged public audit plus meaningful host fixtures. No authored-source text
replacement. Any mismatch blocks equivalence; compilation alone proves nothing.

## 4. Proposed recipe privacy/licensing audit

Every recipe needs `input_id` gating and relevant source/tool hashes. Hashes/GUIDs
may identify versions/content; retain only necessary audited identifiers, never
whole inventories. Hashes do not make protected content publishable.

| Proposed file | Strip/generalize before tracking |
| --- | --- |
| `project-layout.json` | Replace machine paths with repo-relative sources/toolchain roles; audit public package URLs/licenses and authored GUID provenance. Exclude copied proprietary importer bodies. |
| `composition.json` | Keep minimal asset selectors/catalog identifiers only where essential and audited; derive full catalog/path lists. Remove attempts, observations, captures, device/storage data, physical mappings, private paths and runtime telemetry. |
| `asset-transforms.json` | Keep independently authored operations and minimal identity preconditions. Exclude original field payloads, names/hierarchies beyond essential selectors, YAML blocks, game GUID maps and serialized content. |
| `shader-selection.json` | Keep audited logical families/features/tool pins; derive program inventories/material lists. Strip run/bottle/home paths, recovered expressions, layouts and program payloads. Catalog names/asset paths require individual necessity/provenance review. |

Reuse `hud-ui-remaps.json` unchanged under its existing audit; new game identities
would require a fresh audit.

## 5. Open user questions

- Which mixed runtime fields are intended settings versus historical observations?
- May minimal necessary game identifiers remain in audited recipes, or should
  selectors resolve entirely through generated local manifests?
- Which current project/config receipt is the final equivalence oracle, and which
  physical-input evidence must remain a separate run prerequisite?
- If exact bytes cannot be regenerated, which differences warrant a new measured
  contract instead of preserving the inherited behavior?
