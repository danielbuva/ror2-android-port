# Whole-catalog integration — J426

Architecture C remains active. Replace the expansion of selected test content with the shipped content-provider seam: converted Android locations, original content providers, original ContentManager phases and original catalogs. Retain the accepted selected-content composition as rollback. Registration does not establish gameplay, rendering, unlocks or ownership.

## Measured source scope

The exact-editor locator decodes 62,243 keys and 37,673 resource locations from the accepted PC catalog. All six shipped providers are present: base, junk, DLC1, CU8, DLC2 and DLC3. Their original helper uses 29 content categories. Their intersections contain 6,025 typed locations, including 231 ItemDef locations, 59 EquipmentDef locations and 1,522 entity-state configurations. These are location counts, not a count of distinct supported gameplay behaviors.

All 6,025 roots map to exports after resolving punctuation, trailing whitespace and case differences. The serialized/runtime-reference closure contains 32,507 files and 6,242,096,750 source bytes. This includes scenes, models, textures, configurations, scripts and middleware references; it is not a proposed APK size.

The first YAML-only scan would miss runtime AssetReference edges. The broader scan records 1,761 of those edges. It retains the original keys, requested resource types, provider records, ordered dependencies, source GUID relationships and pack/category membership. No tested-content whitelist participates in root selection.

## Binary-backed conversion

Read-only inspection of 635 hash-verified original bundles yields 48,381 container object records with zero bundle/object read failures. Matching original address, object type, object name and exported owner resolves 2,799 additional typed locations. Each mapping retains its original serialized-file/path identity. Imported-model filenames alone are insufficient evidence for selecting a mesh or avatar.

4,942 location conversions remain unresolved. Common cases include multiple original meshes/clips under one imported-model address and nested GameObjects represented inside an exported prefab. The mapper retains the candidates and native identities; it does not choose an arbitrary object, remove the entry or label it incompatible. Explicit subobject requests and default imported-model loading need a shared conversion/provider contract.

436 runtime-reference conversion flags remain after this conservative scan. They count unresolved candidate location sets, not necessarily failed requests of the consumer's exact type. Two keys are absent from the shipped catalog, and three serialized GUID references are absent from the export index. Preserve those source inconsistencies and determine their actual consumers before quarantine.

**Quarantine remains empty.** Missing conversion, untested content and unresolved initialization are separate from demonstrated Android incompatibility.

## Shared binding and initialization boundaries

The imported script inventory matches 1,173 source script identities directly. Twenty additional UI identities map to already measured package remaps, with current input/export hashes and actual imported target types verified. Nine recovered-script identities remain unresolved: directional/contact NGSS, blurred background, Chef unlock effects, bead projectile sound, audio spline/follower, sound trigger and vertex instance streams. This is a binding gap, not evidence that every dependent asset must be excluded.

Reflection records 98 original system initializers and their declared dependencies without invoking them. The content provider's default-locator assumption is significant: original helpers select the first locator. A converted catalog must own that position and retain typed labels/aliases; the current empty diagnostic initialization must not accidentally remain first.

The measured original phases are LoadStaticContentAsync, GenerateContentPackAsync and FinalizeAsync, followed by ContentManager assignment. Use those original phases rather than cosmetic definition registration. SceneCatalog and the remaining catalog dependency graph follow. Do not invoke every initializer blindly: NetworkSoundEventCatalog calls the unavailable native Wwise ID API, and stock platform/profile startup retains the documented Steam boundary. Loading entitlement/expansion definitions never grants entitlement, enables an expansion or fabricates authentication.

## Cheap workflow and current exit

```bash
./dev prototype --action whole-catalog-audit
./dev prototype --action whole-catalog-native
./dev prototype --action whole-catalog-reconcile
./dev prototype --action whole-catalog-contracts
```

These actions emit ignored evidence. They discover and reconcile the complete source graph; they do not install content or pass full catalog registration. The only lookup narrowing is a concrete conversion identity constraint. Multiple candidates remain explicit.

The first expanded metadata representation redundantly emitted 32,353,309 dependency edges and occupied 447 MiB. The revised schema interns 1,471 ordered dependency sets, preserving those edges while reducing the report to about 54 MiB. Historical reports remain byte-identical through lossless filesystem compression. This change serves the immediate broad scan, not a general cache redesign.

Doctor passes. Host build preflight rejects less than ten GiB available space. Closed owned text compression retains exact hashes/paths and recovers some headroom, but the guard remains unsatisfied. No broad Unity import, ContentManager registration, APK build or Android integration run is accepted by J426. Do not lower the guard or delete unrelated files, accepted APKs, payloads or failed evidence. Budget import/cache/bundle space for this measured closure before dispatch.

Next: resolve shared typed subobject and recovered-script bindings; prepare a complete converted location catalog and closure; run original content providers/catalog phases; classify their first actual failure. Then validate one composed Android candidate using the same owned package. Quarantine only a demonstrated incompatible identity with evidence and affected consumers. Keep normal/Moon/manual/PC rollback pointers and platform ownership checks intact.

Prior art: pinned R2API.ContentManagement provider source explains the three original phases and ContentPack identity; pinned R2API.Addressables distinguishes typed keys and handle lifetimes. Local UnityPy ContainerHelper, PPtr dereferencing and ObjectReader.peek_name expose original container ownership without decompiling gameplay logic. The current shipped binaries/assets and exact-editor metadata override community assumptions. No upstream implementation or game-derived source is published.
