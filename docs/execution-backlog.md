# Execution backlog

Canonical policy: DEVELOPMENT_PLAN.md. Immediate order: T01 → T02 → T05 → T06 → T07. Conditional tooling needs a named triggering experiment. A completed experiment is not necessarily a passed capability gate.

Every record uses the required issue schema. All outputs containing game-derived data remain ignored. Future tasks must be split from the measured first failure, not speculative downstream fixes.

## T01 — Reproduce and preserve baseline
- **ID:** T01
- **TITLE:** Reproduce and preserve baseline
- **STATUS:** DONE
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Historical utility/G2 proof; fresh baseline required.
- **HYPOTHESIS:** Existing Vulkan proof remains reproducible.
- **TASK:** Run doctor, preflight, test and Vulkan smoke; verify ABI, placement, markers, visual geometry and cleanup; preserve rollback and approved documents.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing workflow, docs, ignored checkpoints.
- **TEST COMMAND:** ./dev doctor; ./dev preflight; ./dev test; ./dev smoke --target vulkan. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Fresh device G2 pass, recoverable known-good APK/payload.
- **FAILURE EVIDENCE TO CAPTURE:** First failed check, APK identity, run and live storage; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** None.

## T02 — Identify smallest meaningful RoR2 slice
- **ID:** T02
- **TITLE:** Identify smallest meaningful RoR2 slice
- **STATUS:** DONE
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** SimpleJSON does not prove RoR2; J09 identifies Rewired conflicts.
- **HYPOTHESIS:** A bounded dependency transformation enables actual original game code.
- **TASK:** Attribute conflicting metadata and consumers; select an independently checkable RoR2/EntityStates probe; record dependency/roots/contracts and early mandatory service risks.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Managed inventory, local recovered source, narrow analysis.
- **TEST COMMAND:** Existing reports; ./dev prototype --action dependency-boundaries if needed. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Exact original methods, assertions, required types/native references and first candidate recorded.
- **FAILURE EVIDENCE TO CAPTURE:** Unresolved signatures, conflicting definitions, access/native contracts; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** T01.

## T05 — Isolate Rewired boundary
- **ID:** T05
- **TITLE:** Isolate Rewired boundary
- **STATUS:** BOUNDED AOT PASS; controller/native integration OPEN
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Windows closure conflicts in Core/Windows.
- **HYPOTHESIS:** Android-capable integration retains required contract.
- **TASK:** Test authorized compatible package first; compare consumed API/serialized identity. If unavailable assess one bounded adapter, not a speculative replacement middleware.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Generated middleware, import config, transforms and probe.
- **TEST COMMAND:** Experiment-specific ./dev action and existing forced build/lifecycle. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Known conflicts removed with required types exercised, not stripped away.
- **FAILURE EVIDENCE TO CAPTURE:** VTable, API/type differences, native load and init; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** T02; minimum triggered support.

## T06 — Isolate Burst/Collections
- **ID:** T06
- **TITLE:** Isolate Burst/Collections
- **STATUS:** REPRESENTATIVE PACKAGE PASS; full game compatibility OPEN
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** J05 direct-call initialization crashes editor.
- **HYPOTHESIS:** Compatible artifacts or valid managed fallback preserve operations.
- **TASK:** Inspect fingerprints/direct calls; one justified package candidate then separate fallback if needed; allocation/disposal and job/hash probe.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Generated packages/imports and probe.
- **TEST COMMAND:** Experiment-specific ./dev action, guarded editor and Android probes. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Expected results without crashes; editor/device classified separately.
- **FAILURE EVIDENCE TO CAPTURE:** Package graph, API/layout/direct call and crash stack; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** T02; normally after T05.

## T07 — Execute meaningful original code on Android
- **ID:** T07
- **TITLE:** Execute meaningful original code on Android
- **STATUS:** BOUNDED SLICE PASS; full closure OPEN
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Utility execution does not prove game code.
- **HYPOTHESIS:** Selected boundary permits original slice AOT and execution.
- **TASK:** Stage slice in existing lab; root methods, forced build, guarded install and assert results; unchanged originals distinguished from transforms.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Lab probe, original assemblies, preservation and targeted transforms.
- **TEST COMMAND:** ./dev prototype --action ror2-slice (thin existing lifecycle; add when needed). Proposed actions must be added and documented before use.
- **PASS CONDITION:** Three cold launches ≥30 seconds each with correct original method results.
- **FAILURE EVIDENCE TO CAPTURE:** AOT, preservation/assembly hashes, assertions, crashes/exceptions; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** T05 and device-relevant T06 outcome.

## T03 — Build attribution and installation safety
- **ID:** T03
- **TITLE:** Build attribution and installation safety
- **STATUS:** CONDITIONAL
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Next experiment cannot identify completion or safe package identity.
- **HYPOTHESIS:** A narrow receipt/guard removes the concrete ambiguity.
- **TASK:** Add only needed attempt/terminal receipt or guard; keep separate reconstruction APK host-only.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Build/editor/device orchestration.
- **TEST COMMAND:** ./dev test and triggering experiment. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Stale output/failed dispatch/wrong-package cases rejected as applicable.
- **FAILURE EVIDENCE TO CAPTURE:** Attempt/progress and identity evidence; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** Trigger required; not wholesale prerequisite.

## T04 — Cache and independent data identities
- **ID:** T04
- **TITLE:** Cache and independent data identities
- **STATUS:** CONDITIONAL
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Scene cache uncertain or content edit rebuilds unchanged AOT.
- **HYPOTHESIS:** Affected recipe fix avoids stale reuse/unneeded builds.
- **TASK:** Force build initially; fix relevant recipe inputs or separate content receipt/build when needed.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Build/cache/content tooling.
- **TEST COMMAND:** Targeted scene/code/content change test. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Changed scenes invalidate; pure content avoids unnecessary AOT once supported.
- **FAILURE EVIDENCE TO CAPTURE:** Input/output hashes and cache decisions; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** Trigger from immediate experiment.

## T08 — Subsystem observability
- **ID:** T08
- **TITLE:** Subsystem observability
- **STATUS:** CONDITIONAL
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Next failure cannot be classified from current file diagnostics.
- **HYPOTHESIS:** One typed observation identifies first failure.
- **TASK:** Add only needed init/scene/reference/authority/input report; bind current launch.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Diagnostics and collector.
- **TEST COMMAND:** Triggering experiment plus stale/failure fixture where applicable. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Current attempt state distinguishes expected failure.
- **FAILURE EVIDENCE TO CAPTURE:** Event/state and launch correlation; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** Trigger from immediate experiment.

## T10 — Storage scale
- **ID:** T10
- **TITLE:** Storage scale
- **STATUS:** CONDITIONAL
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Tiny payload does not prove multi-GiB behavior.
- **HYPOTHESIS:** Adopted split supports realistic content size.
- **TASK:** Before large content use realistic synthetic payload; interrupt/retry/hash/update/unchanged sync/owned cleanup; stage dependent generations before activation.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Sync/lifecycle and synthetic fixture.
- **TEST COMMAND:** ./dev storage; experiment-specific scale action. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Verified hashes, no incomplete activation, unchanged transfer skipped, retention and owned cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** Capacity before/during/after, backing, partial state, transfer time; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** Immediately before large content.

## T01 evidence

Passed fresh doctor/preflight, six safety tests and Vulkan smoke. work/runs/20260913T020341.114229Z-46130c90d7a1; screenshot reviewed; package removed. Runtime pointer: work/checkpoints/LAST_KNOWN_GOOD_RUNTIME.json.

## Subsequent issue expansion

L4: required reference closure → animated prefab → loadingbasic device load. L5/L9: writable profile root → observed lawful startup boundary → menu. L5.5: master/body spawn/authority → deterministic original simulation → built-in input. L6: stage integration → camera/abilities. L7: enemy/damage → pickup/interactable → director → teleporter. L8: transitions/lifetime → finale → victory persistence. Expand each into this full schema only when its prerequisite evidence exists.

## T02 result / T05 candidate refinement

J11 attributes both conflicts to extra exported forwarding getters; original DLL bytes have one implementation per slot. Evidence: work/experiments/dependency-boundaries/20260913T021130.995984Z. T05 first tests original DLLs with the actual disputed types rooted/invoked. T07 selected Trajectory and ProcChainMask/ProcType; slice success is not full closure acceptance.

T05/J12: original Core/Windows bytes pass both explicitly rooted conflicting virtual slots on device, work/experiments/rewired-original/20260913T021247.788313Z. T06 next.

## Next gate refinement — T07b

T07 passes at work/experiments/ror2-slice/20260913T022358.230312Z. Before L4, AOT-build the full original managed set with compatible packages. This distinguishes actual assembly preservation from the export-modified J09 closure; do not infer full closure from a type-pruned slice.

## T07b — Full original managed-set AOT
- **ID:** T07b
- **TITLE:** Full original managed-set AOT
- **STATUS:** PASS — full AOT and additional baseline device smoke (J18)
- **CONTEXT:** J12 original Rewired slots and J14 package candidate pass; J16 type-pruned RoR2 slice passes.
- **OBSERVATION:** J09 tested export-modified DLLs; a type-pruned slice does not prove full closure.
- **HYPOTHESIS:** Original DLL bytes with the tested package providers can AOT-build the full RoR2 assembly.
- **TASK:** Stage original dependencies in existing lab, explicitly root full RoR2, resolve package modules, force build, attribute the first failure. No startup/auth adapters.
- **CONSTRAINTS:** Common plan; never substitute an export-only library without checking original consumers; preserve stage/input hashes and failed evidence. Wait for terminal build before any editor mutation.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Thin ./dev experiment runner, ignored lab stage, original dependency manifest and build receipts.
- **TEST COMMAND:** ./dev prototype --action original-closure-prepare; resolve pinned modules; ./dev prototype --action original-closure-build.
- **PASS CONDITION:** Terminal ARM64 IL2CPP APK build, staged input hashes retained and full RoR2 rooted. This is not device/startup acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** Original dependency hashes, package providers, first error, full relevant editor build output; no APK installed on build failure.
- **STATE/JOURNAL UPDATES REQUIRED:** State and J17 onward, backlog/milestone status; next runtime experiment only after measured build outcome.
- **DEPENDENCIES:** T05/T06/T07 bounded passes.

## T07c — Original method assertions with the full assembly
- **ID:** T07c
- **STATUS:** PASS — J20, three full-original launches
- **TITLE:** Repeat bounded game assertions without type pruning
- **CONTEXT:** J16 passes a type-pruned slice; J18 full original assembly builds and survives baseline smoke.
- **OBSERVATION:** Full assembly has not yet run the ten explicit trajectory/proc assertions.
- **HYPOTHESIS:** The full unchanged DLL produces the same results without extra runtime initialization failures.
- **TASK:** Reuse the existing authored assertion probe with the staged full assembly, record full-original identity, force build and run three cold launches.
- **CONSTRAINTS:** Common contract; only one RoR2.dll, no startup/auth patches; do not mistake LAB_READY for game readiness.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing probe and thin runner; ignored full assembly stage and receipts.
- **TEST COMMAND:** ./dev prototype --action original-closure-runtime; existing preflight/build/install/capture lifecycle.
- **PASS CONDITION:** Ten assertions on each of three distinct cold PIDs surviving ≥30 seconds, unchanged full DLL hash, no unexplained managed/native failures.
- **FAILURE EVIDENCE TO CAPTURE:** Current-launch assertion file, initialization errors, crash output, full assembly hashes and terminal build result.
- **STATE/JOURNAL UPDATES REQUIRED:** Record outcome and L3 scope; advance to L4 reference closure only after classification.
- **DEPENDENCIES:** T07b; no new broad infrastructure.

## L4a — Required recovered reference closure
- **ID:** L4a
- **STATUS:** COMPLETE — discriminating editor audit J21; device L4 remains OPEN
- **TITLE:** Audit loadingbasic and one dependency-rich prefab
- **CONTEXT:** L3 full-original method execution passes.
- **OBSERVATION:** G2 only renders a static recovered mesh; no original scene has loaded.
- **HYPOTHESIS:** A bounded recovered scene/prefab closure can retain required script and asset identities.
- **TASK:** Use existing reference reports and original/export metadata to identify required GUIDs, file IDs, script types, subassets, catalog locations, rig/animation and material dependencies; select the smallest closure and first repair.
- **CONSTRAINTS:** Common contract; no large transfers before T10; do not infer reference integrity from a loaded bundle container.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing reference tooling and ignored closure report; narrow transformation only if a concrete defect is found.
- **TEST COMMAND:** ./dev prototype --action references; inspect existing command scope before extending it; ./dev preflight before any build.
- **PASS CONDITION:** Exact required closure, unresolved references and next discriminating scene/prefab build are recorded. Device scene acceptance remains a separate L4 experiment.
- **FAILURE EVIDENCE TO CAPTURE:** First required missing/mismatched reference, source/export identities, catalog/provider dependencies and estimated payload size.
- **STATE/JOURNAL UPDATES REQUIRED:** Update L4 status and first experiment; preserve prior runtime receipt.
- **DEPENDENCIES:** T07c/L3.

## L4b — First loadingbasic Android scene bundle
- **ID:** L4b
- **STATUS:** BOUNDED DEVICE PASS — J23; complete L4 acceptance remains open
- **TITLE:** Import and load the measured loading scene closure
- **CONTEXT:** L4a/J21 yields a small closure and matching original DLL script IDs.
- **OBSERVATION:** 122 files, roughly 10 MiB source closure; dynamic fallback atlas missing; no Android scene proof.
- **HYPOTHESIS:** Original GUID/fileID preservation plus measured package UI remapping enables scene import and Android serialization.
- **TASK:** Stage only loadingbasic closure and original managed providers. Resolve each consumed UI type to its package MonoScript and rewrite only measured references. Validate missing scripts/references before building a separate Android scene bundle. Load through the existing lab, collect scene/error/capture evidence.
- **CONSTRAINTS:** Common contract; force builds for changed scenes; serialized editor operations must finish before another dispatch. Do not invoke RoR2Application or platform startup to repair an unmeasured scene error. Do not overwrite baseline APK/payload receipts.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Ignored closure/meta staging, narrow identity transform and scene probe; existing lab bundle/build lifecycle.
- **TEST COMMAND:** Add a thin scene-runtime prototype action when staging begins; ./dev preflight, forced Vulkan build, existing device lifecycle.
- **PASS CONDITION:** Real device loads original loadingbasic scene with resolved required scripts, traceable dependencies and visually reviewed capture. Record fallback font and placeholder material limitations; dependency-rich prefab remains a separate L4 subgate.
- **FAILURE EVIDENCE TO CAPTURE:** Import identity mismatch first, then bundle/build errors, scene activation exceptions, dynamic atlas behavior, current-launch screenshot.
- **STATE/JOURNAL UPDATES REQUIRED:** J22 onward; preserve L3 rollback; advance no scene pointer on failed import or mere bundle container success.
- **DEPENDENCIES:** L4a. T10 not yet triggered by measured small closure; check actual built size.

## L4c — Complete object audit and dependency-rich prefab content
- **ID:** L4c
- **STATUS:** BOUNDED DEVICE PASS — J24/J26; persistent objects and inactive prefab rig integrity proven
- **TITLE:** Extend the measured scene proof to persistent objects and prefab content
- **CONTEXT:** J23 loads the original loading scene with application startup inactive.
- **OBSERVATION:** Current count omits objects moved to DontDestroyOnLoad; Commando closure is measured but not instantiated.
- **HYPOTHESIS:** Original serialized identities remain valid across persistent objects and a recovered prefab dependency closure.
- **TASK:** Add the missing scene/persistent-object observation to the existing probe; inspect required font/render/animation references. Then introduce an inactive dependency-rich prefab for component/rig/material audit before any original character simulation. Split runtime animation into its own assertion if needed.
- **CONSTRAINTS:** Common contract; startup stays inactive, no authority/gameplay claim, no large unmeasured transfer. Fix first reference/import failure before later behavior.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing LoadingSceneProbe and narrowly staged content; no general observability framework.
- **TEST COMMAND:** Existing scene-prepare/identity/scene-arm/forced Vulkan build/scene-run flow, extended only for this probe.
- **PASS CONDITION:** Required components accounted for across loaded and persistent objects; prefab script/rig/animation/material references resolve on device and capture agrees. Complete L4 only when all its required assertions pass.
- **FAILURE EVIDENCE TO CAPTURE:** Persistent-object linkage, first missing required component/subasset, exceptions, actual font/animation observations and capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J23 receipt and L3 rollback; distinguish content, startup and simulation gates.
- **DEPENDENCIES:** L4b bounded result.

## L4d — Visible recovered Commando content
- **ID:** L4d
- **STATUS:** PASS — J28 paired visual poses and bone changes; L4 isolated content accepted
- **TITLE:** Validate visible pose and animation of recovered character content
- **CONTEXT:** J26 proves inactive prefab component/rig identities with six diagnostically bound default assets.
- **OBSERVATION:** The character is intentionally inactive and absent from captures; 35 clips and a valid avatar are present but not sampled.
- **HYPOTHESIS:** The validated skeleton/mesh/animation data can produce a recognizable pose and changing animation on device without activating gameplay scripts.
- **TASK:** Extend only the existing content probe to display the recovered model and sample a bounded animation. Keep original gameplay behaviours/startup isolated; explicitly distinguish diagnostic pose/rendering from original state-machine simulation. Inspect the first actual material/animation mismatch.
- **CONSTRAINTS:** Common contract; no direct-transform movement as simulation proof. Original asset-loader behavior remains a separate measured boundary; no wholesale Windows catalog transfer.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing LoadingSceneProbe, measured model/animation closure, one placeholder material family if needed.
- **TEST COMMAND:** Existing attributed prefab staging/build/device lifecycle, extended with a visible-pose assertion. Preflight and forced build; preserve prior receipts.
- **PASS CONDITION:** Device capture shows recognizable recovered Commando and a measured pose/animation change consistent with bone evidence, without activating startup/character simulation. Review remaining L4 gates explicitly.
- **FAILURE EVIDENCE TO CAPTURE:** First mesh/bind-pose/controller/material failure, sampled clip/time/bone transforms and matching capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Record bounded visual acceptance; replan before L5; retain runtime/prefab rollback.
- **DEPENDENCIES:** L4c/J26.


## L5a — Original asset-loading and startup boundary audit
- **ID:** L5a
- **TITLE:** Select the first truthful startup integration experiment
- **CONTEXT:** L4 content passes with diagnostic bindings; original startup remains inactive.
- **OBSERVATION:** Original skin content is deferred through AssetReference GUIDs; the current probe supplies six measured assets explicitly.
- **HYPOTHESIS:** A bounded local provider can satisfy measured content requests without platform initialization or altering original gameplay methods.
- **TASK:** Consult R2Wiki memory-update/skin/content guidance, RoR2EditorKit AddressablesPathDictionary/cache, R2API Addressables/content implementation, RoR2ImportExtensions/ThunderKit catalog import, and Starstorm2/MSU or RoRSkinBuilder real skin/content use before inventing a provider. Trace exact current-input requests, release/failure semantics, startup ordering, mandatory entitlement/native services and Android-only profile paths. Read the ranked experiment in community-prior-art.md.
- **CONSTRAINTS:** Common contract; original installation/profile untouched, no fabricated service success, no broad catalog transfer or speculative middleware rewrite.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Local recovered-source reports under work/, concise authored boundary analysis; thin provider probe only after measured contract.
- **TEST COMMAND:** Read existing local recovered code and catalog evidence; use existing ./dev preflight/build/scene-run lifecycle when a device test is justified.
- **PASS CONDITION:** Exact next original method/request, expected result, content identity, startup prerequisites and profile boundary recorded. Audit alone does not pass L5.
- **FAILURE EVIDENCE TO CAPTURE:** First unresolved API/native/ownership contract, source location, typed key, lifecycle and failure propagation.
- **STATE/JOURNAL UPDATES REQUIRED:** Record L4 replan and L5 first hypothesis; retain L3/runtime and L4 content checkpoints.
- **DEPENDENCIES:** L4d. T03/T04/T08/T10 remain conditional.

- **RESEARCH STATUS:** Audit complete; candidate A controller lifecycle passes in J33. Architecture and full capability gates unchanged.
- **CANDIDATE A (FIRST):** Small owned initialization/catalog recipe plus typed location using original AssetBundleProvider/BundledAssetProvider. Exercise original AssetOrDirectReference<RuntimeAnimatorController>.LoadAsync for GUID 48ef8327759dd43439416d4823124d9c, correct controller/35 clips, shared handles, Reset/delayed release/reload and missing/wrong-type controls. Original startup remains inactive; explicitly diagnose/tick original manager cleanup for this bounded probe. Locator registration alone does not complete Addressables initialization.
- **CANDIDATE B:** Same original caller with a narrow custom provider only if the built-in provider has a measured Android limitation. Wider Android catalog rebuilding is later, on measured content demand.
- **EXIT DISCIPLINE:** Existing pass condition above is unchanged. The research recommendation is EXPERIMENTAL and audit alone does not pass L5. Provider failure ordering and all required evidence are specified in community-prior-art.md.

## L5a-1 — Original controller request with existing providers
- **ID:** L5a-1
- **STATUS:** PASS — J33, 50.17-second device survival; no startup/simulation claim
- **TITLE:** Exercise original deferred controller load/shared ownership/release
- **CONTEXT:** L5a research recommends existing providers before a custom replacement.
- **OBSERVATION:** Original runtime libraries implement bundle providers and the game wrapper/manager; initialization autoreleases its handle and cleanup depends on an inactive application event.
- **HYPOTHESIS:** A valid local initialization catalog plus one typed Android location can serve the unchanged wrapper and preserve shared ownership, failure and release behavior.
- **TASK:** Initialize a real zero-entry bootstrap catalog, register the measured controller location with original bundle providers, request through AssetOrDirectReference twice, reset/release/reload and test invalid requests. Use explicit diagnostic calls to original cleanup Update; no fake initialized flags.
- **CONSTRAINTS:** Common contract; unchanged original DLLs, startup/profile/body inactive, existing owned package and storage guards; provider exclusively owns the prefab bundle. Diagnostic ticking does not prove the game loop.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored ControllerAddressProbe, thin existing scene runner additions, ignored restored content stage and receipts.
- **TEST COMMAND:** ./dev prototype --action controller-prepare; ./dev build --target vulkan --force; ./dev prototype --action controller-run; ./dev test.
- **PASS CONDITION:** Current-PID initialized state, correct controller/35 clips, shared/retained/released/reloaded handles and bundle, failed missing-key/wrong-type controls, 50-second survival, no unexpected startup/native failure and owned cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** First phase/status/exception, local catalog/settings, source and APK/payload hashes, logcat/crash/capture and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Classify first failure; update L5a status without passing L5; retain L3/L4 checkpoints.
- **DEPENDENCIES:** L5a prior-art audit; exact accepted J26 content recipe and current pinned runtime libraries.


## L5a-2 — Original avatar request and subobject identity
- **ID:** L5a-2
- **STATUS:** PASS — J34, valid original typed avatar request and 51.13-second device lifecycle
- **TITLE:** Resolve the original Commando avatar through the proven loader
- **CONTEXT:** L5a-1 controller lifecycle passes; FBX subobjects remain a distinct boundary.
- **OBSERVATION:** J26 explicitly bound an exported avatar, while J25 catalog reports describe its original typed subobject location. EditorKit subasset heuristics require current-input validation.
- **HYPOTHESIS:** The existing providers can resolve the measured Avatar subobject without a custom loader or full catalog transfer.
- **TASK:** Compare the pinned catalog key/type/subobject identity with actual exported bundle asset/subasset names. Extend only the accepted probe's typed location/request to the original avatar wrapper. Verify identity, validity and release/reload. Keep skin baking a separate subsequent task.
- **CONSTRAINTS:** Common contract; original application/body/profile inactive, unchanged original DLLs, diagnostic cleanup identified; no speculative FBX renaming or provider replacement.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow authored probe, ignored typed mapping/accepted content stage and evidence; existing provider orchestration.
- **TEST COMMAND:** Existing catalog-addresses inspection as needed, forced Vulkan build and controller-run lifecycle; name any new thin action with this experiment.
- **PASS CONDITION:** Current-PID successful original typed avatar request with independently matched subobject identity, valid avatar and balanced ownership/reload; at least 50 seconds alive and owned cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** Typed catalog and bundle names, first key/type/subobject/provider error, original wrapper results, source/APK/payload hashes and device evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failed candidates; record bounded result without passing full skin loading or L5. Keep accepted controller rollback.
- **DEPENDENCIES:** L5a-1/J33 and measured J25/J26 avatar identity; review community-prior-art.md before the subobject choice.


## L5a-3 — Original skin parameters and baking
- **ID:** L5a-3
- **STATUS:** PASS — J36, original baking/template identities/parameter release on Android; 70.92 seconds
- **TITLE:** Resolve default SkinDefParams and run original BakeAsync
- **CONTEXT:** Original controller and avatar deferred request lifecycles pass, with startup inactive.
- **OBSERVATION:** Original SkinDef.BakeAsync resolves deferred parameters and produces renderer/activation/mesh templates. Existing static content proof manually supplied defaults.
- **HYPOTHESIS:** Measured default-skin parameter and prefab references can support original template generation through the accepted provider path.
- **TASK:** Consult the pinned skin/community sources and current original implementation; measure the exact default SkinDef/params closure and expected template counts/identities before staging. Exercise parameter loading and original BakeAsync, stopping at the first unresolved dependency. Split skin application/material/mesh loading into later work if it adds a new boundary.
- **CONSTRAINTS:** Common contract; no original body/application/profile activation, no synthetic templates or rewritten game logic, unchanged original DLLs. Preserve diagnostic versus real game-loop scheduling distinction.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow skin probe and measured local location/content recipe, ignored original-source/identity reports and device receipts.
- **TEST COMMAND:** Existing preflight, forced Vulkan build and guarded device lifecycle; add a thin skin-specific action only with this probe.
- **PASS CONDITION:** Original parameter identity and BakeAsync completion, independently expected template counts/references, released temporary parameter ownership, stable device lifetime and owned cleanup. No full skin application or gameplay claim.
- **FAILURE EVIDENCE TO CAPTURE:** First unresolved key/reference/static initializer, nested coroutine exception, template/result identity, source/APK/payload hashes and current-PID device evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** Record outcome and any split task, preserve failed attempts and controller/avatar rollback; L5 remains open.
- **DEPENDENCIES:** L5a-2/J34, measured default skin/params and existing prior-art audit.


## L5a-4 — Original skin application to the inactive model
- **ID:** L5a-4
- **STATUS:** PASS — J38, original mesh assignments and material records on inactive model; 70.87 seconds
- **TITLE:** Load and apply the baked default material/mesh references
- **CONTEXT:** Original controller/avatar loading and default skin baking pass separately.
- **OBSERVATION:** Baked templates retain deferred material and mesh references; baking alone does not assign renderers or load those assets.
- **HYPOTHESIS:** Measured material and three mesh subobject mappings let original RuntimeSkin.ApplyAsync populate the inactive recovered model correctly.
- **TASK:** Inspect pinned skin/community implementations and current original ApplyAsync; measure exact deferred keys/provider mappings and resulting renderer assignments. Apply using the original method on an inactive model, assert mesh/material identities and reference counts, then release. Split at the first new loading/assignment boundary before adding activation or visuals.
- **CONSTRAINTS:** Common contract; original DLLs unchanged, no CharacterBody/application/profile activation, no diagnostic assignment substituted for original skin application. Diagnostic rendering can follow but does not imply gameplay or shader parity.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow existing probe extension, measured local material/mesh locations, ignored restored skin stage and evidence.
- **TEST COMMAND:** Existing preflight, forced Vulkan build and owned device lifecycle; add only the skin-application preparation needed for this task.
- **PASS CONDITION:** Original ApplyAsync completes; expected mesh components and CharacterModel material records receive the correct recovered identities; ownership/release assertions and stable device lifetime pass. No missing required references or new unexplained exceptions.
- **FAILURE EVIDENCE TO CAPTURE:** First typed key/provider/subobject/assignment failure, original coroutine results, current renderer identities and reference ownership, APK/payload hashes and device evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failed attempts, update bounded skin status without passing startup/simulation, retain J36 rollback.
- **DEPENDENCIES:** L5a-3/J36 and current-input material/mesh identity mappings; shared controller/avatar providers stay accepted.


## L5b-1 — First lawful startup segment and Android profile foundation
- **ID:** L5b-1
- **STATUS:** PASS — J39, first-yield/PreFrame and independent filesystem candidate; full startup remains open
- **TITLE:** Cross from isolated content into measured original startup
- **CONTEXT:** J33–J38 prove bounded original asset loading, baking and inactive model application. Original startup/menu and L5.5 simulation remain unexecuted.
- **OBSERVATION:** Static InitializeGameRoutine trace reaches Wwise, Addressables, a filesystem rooted at Application.dataPath, PlatformSystems.Init and a Steam-client delegate before profile loading. This order and native/service obligations need explicit device-relevant boundaries.
- **HYPOTHESIS:** An isolated first startup segment and separate Android-owned profile/content roots can expose the next real blocker without activating several unmeasured services at once.
- **TASK:** Reuse community-prior-art.md startup/profile findings; revalidate actual pinned assembly signatures/call order and mandatory checks. Select and record the smallest executable original startup segment, its stop boundary and truthful unavailable capabilities. Establish and test a fresh Android-only filesystem root before enabling profile writes. Implement only the necessary input-gated adapter/observation, then execute the selected segment on device; stop at its first failure.
- **CONSTRAINTS:** Common contract; no fabricated ownership/authentication/service success, no host Steam profile access or changes, no broad startup patching, no native middleware replacement without measured need. Wwise no-audio handling requires a valid lifecycle, not silent success.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow startup/path audit and probe, minimal profile/content path adapter if justified, ignored evidence and checkpoint receipts.
- **TEST COMMAND:** Existing doctor/preflight/forced build/owned device lifecycle; add only a thin startup-segment action with its exact assertions.
- **PASS CONDITION:** Fresh Android profile path isolation verified; the selected original segment reaches its declared boundary with attributable events, correct capability states and stable device lifetime. A discriminating failure completes the experiment but does not pass L5.
- **FAILURE EVIDENCE TO CAPTURE:** First initialization/native/path/entitlement failure, concrete call/signature and capabilities, profile backing/isolation evidence, source/APK/payload identities and device capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Record first blocker or passed segment; preserve J38 asset rollback and separate L5 startup from L5.5 simulation. Keep renderer material update unproven until exercised.
- **DEPENDENCIES:** L5a-4/J38; earlier startup/profile prior-art audit. Revisit audio access/platform requirements only where this segment needs them.

## L5b-2 — Original startup loading-scene handoff
- **ID:** L5b-2
- **STATUS:** PASS — J40, real loadingbasic/Canvas and two original frame yields; no component activation
- **TITLE:** Connect the proven first startup phase to recovered loadingbasic
- **CONTEXT:** J39 proves original PreFrame and an isolated Android filesystem candidate; L4 proves recovered loading scene content independently.
- **OBSERVATION:** The next original routine segment redirects console output, subscribes scene events, waits for loadingbasic, accesses LoadingScreenCanvas.Instance.percentage and yields two frames before enabling components.
- **HYPOTHESIS:** The recovered loading scene and persistent UI can satisfy these original startup references without prematurely activating audio/platform components.
- **TASK:** Inspect the exact recovered application/UI component identities and next coroutine yield boundaries. Restore J39, load the accepted recovered scene with application startup still controlled, resume only through the measured loading-UI frame yields, and stop before EnableBehaviours. Verify original loading scene/Canvas linkage and capture the first missing lifecycle/reference requirement. Audit the serialized enable list before any later activation.
- **CONSTRAINTS:** Common contract; no duplicate automatic application Awake or full startup, no fabricated scene readiness or service success, no profile-global reassignment. Do not skip a failing original reference by replacing it with a dummy. Preserve the J39 path and known-good content.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing narrow startup probe and preparation, recovered scene/component evidence under ignored work/, state and journal.
- **TEST COMMAND:** Existing startup preparation/run lifecycle with an explicit next-segment configuration; preflight, forced Vulkan build, current-attempt device report and screenshot.
- **PASS CONDITION:** Original routine recognizes actual recovered loadingbasic and real loading UI, reaches the declared yield stop before component enabling, with stable device lifetime and no new unexplained errors. This remains a segment proof, not L5 menu acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** First scene/singleton/component/reference failure, original yield position, current-PID exception/capture, preserved source/APK/payload identities.
- **STATE/JOURNAL UPDATES REQUIRED:** Record the exact reached boundary, retain J39 rollback, then select the measured component/audio boundary. Keep L5/L9/L5.5 open.
- **DEPENDENCIES:** L5b-1/J39 and accepted L4 recovered scene evidence.

## L5b-3 — Recovered application host and startup component lifecycle
- **ID:** L5b-3
- **STATUS:** SPLIT — L5b-3a real recovered application Awake, then individually measured component lifecycles
- **TITLE:** Measure the six startup components before crossing into audio
- **CONTEXT:** J40 proves loading-scene/UI handoff with the routine on an inactive diagnostic host.
- **OBSERVATION:** The recovered application's enable list has GlobalShaderTextures, two PostProcessVolume entries, InterpolationController, NGSS_Local and FPSQueue, all disabled/inactive. The diagnostic host's empty list cannot establish their lifecycle.
- **HYPOTHESIS:** Their measured initialization requirements can be isolated while retaining real serialized references and preventing automatic full application startup.
- **TASK:** Inspect original Awake/OnEnable/Start/update paths and native/shader requirements of these six components plus application Awake. Select the smallest real-host/component experiment, preserve references, and explicitly record inactive enable flags versus executed lifecycle. Stop before Wwise and split at the first component failure. Reuse prior-art audit where applicable.
- **CONSTRAINTS:** Common contract; no automatic full startup, empty-list success, speculative graphics rewrites, fake audio/services or saves. Keep user's owned app installed; update in place.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing narrow startup probe/preparation, ignored component metadata/serialized-contract reports, only a measured lifecycle adapter if needed.
- **TEST COMMAND:** Existing startup preparation, preflight, forced Vulkan build and current-attempt/PID device assertions; use a thin component action only if required.
- **PASS CONDITION:** Selected real component lifecycle and serialized references execute with correct assertions and stable device lifetime; report exactly which components ran. No L5 menu pass from toggled flags on inactive objects.
- **FAILURE EVIDENCE TO CAPTURE:** First component initialization/reference/shader/native failure, enabled/active states, actual lifecycle events, original method and source/APK/payload identities.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J40 rollback; select next component or Wwise boundary from evidence. Keep actual saves/menu/simulation open.
- **DEPENDENCIES:** L5b-2/J40 and measured original component/application lifecycle audit.

## L5b-3a — Original Awake on the recovered application component
- **ID:** L5b-3a
- **STATUS:** PASS — J41, explicitly invoked real recovered Awake; automatic lifecycle unproven
- **TITLE:** Establish the real application singleton without starting every component
- **CONTEXT:** J40 uses an inactive diagnostic host for the bounded startup coroutine.
- **OBSERVATION:** Original Awake assigns instance/build ID/assembly types and registers callbacks. It starts OnLoad only when isLoading is false; the tested original first yield has already set that flag true.
- **HYPOTHESIS:** Explicit original Awake invocation on the actual inactive recovered component can establish its identity while preserving the current bounded coroutine.
- **TASK:** Reuse J40, require the naturally established loading flag, invoke the original method unchanged, and verify singleton identity, Application.version build ID, expected assembly types, inactive object and disabled six-component list.
- **CONSTRAINTS:** Common contract; do not set loading/authentication flags manually, skip checks or activate the entire object. Event subscription is not entitlement success. Explicit method invocation does not establish automatic Unity Start/Update behavior. Keep app installed.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing startup probe/preparation and ignored component audit/evidence.
- **TEST COMMAND:** `./dev prototype --action startup-application-prepare`, forced Vulkan build and `./dev prototype --action startup-run`; existing preflight/install guards.
- **PASS CONDITION:** Real recovered singleton, correct build/type identities and bounded inactive state persist on the device; no extra startup coroutine, filesystem assignment or new unexplained exception.
- **FAILURE EVIDENCE TO CAPTURE:** First original Awake/static initializer error, current-PID singleton/loading/component state and source/APK/payload identities.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J40; record bounded method outcome, keep full component lifecycle/menu/simulation open, choose the first actual component method next.
- **DEPENDENCIES:** L5b-2/J40 and six-component/application source and pinned metadata audit.

## L5b-3b — Original global texture initialization
- **ID:** L5b-3b
- **STATUS:** PASS — J42, three original global bindings and previous-state restoration
- **TITLE:** Verify the first measured startup component method
- **CONTEXT:** J41 establishes the recovered application singleton without enabling its six-component list.
- **OBSERVATION:** GlobalShaderTextures.Start binds the serialized warp, elite and snow textures to three named shader globals.
- **HYPOTHESIS:** The recovered component retains valid texture identities and its unchanged original method can bind them on Android.
- **TASK:** Restore J41, independently record serialized texture GUID/imported identities and variable names, explicitly invoke original Start on the real component, then compare Shader.GetGlobalTexture results to each non-null source. Capture previous globals and restore after assertions where appropriate.
- **CONSTRAINTS:** Common contract; no authored replacement binding as proof, no full application activation, no automatic lifecycle or rendering-parity claim. Keep owned app installed.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow startup probe/preparation, ignored texture identity evidence, state/journal.
- **TEST COMMAND:** Existing forced Vulkan build and startup-run lifecycle with a thin measured component option.
- **PASS CONDITION:** All three original global assignments match independently verified recovered textures and stable device lifetime; no new exception.
- **FAILURE EVIDENCE TO CAPTURE:** First missing/wrong texture identity or global binding, method invocation, original DLL/APK/payload hashes and current-PID evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J41; record method proof separately from visual shaders/lifecycle, then select the next component from the stored audit.
- **DEPENDENCIES:** L5b-3a/J41, component-audit.json and current recovered serialized texture references.

## L5b-3c — Original interpolation timing
- **ID:** L5b-3c
- **STATUS:** PASS — J43, eight real timing comparisons and state restoration
- **TITLE:** Verify the recovered interpolation controller with real frame timing
- **CONTEXT:** J42 passes the first isolated startup component method; the application object remains inactive.
- **OBSERVATION:** InterpolationController.Start allocates a two-sample history, FixedUpdate records Time.fixedTime and Update derives the render interpolation factor. No application singleton or service initialization is required by these methods.
- **HYPOTHESIS:** Original methods preserve valid fixed-frame history and interpolation behavior under Android scheduling.
- **TASK:** Inspect pinned signatures, initialize the real recovered component, then call its original methods at measured fixed/frame boundaries. Record initial fallback and multiple distinct fixed-time samples, compare reported interpolation against an independently recorded timing oracle and restore temporary state where appropriate. Label diagnostic scheduling explicitly.
- **CONSTRAINTS:** Common contract; no fabricated timing results, no synthetic implementation replacing original methods, no full application/component activation or movement claim. Keep owned app installed.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow startup probe option and ignored timing/identity evidence, state/journal.
- **TEST COMMAND:** Existing forced Vulkan build/startup-run lifecycle; thin preparation option with current-attempt/PID assertions.
- **PASS CONDITION:** Original initialization and timing methods produce finite expected values across distinct real fixed ticks and stable device lifetime. Automatic lifecycle and character movement remain separate.
- **FAILURE EVIDENCE TO CAPTURE:** First initialization/history/nonfinite/timing mismatch, real timestamps and observed result, original DLL/APK/payload identity, current-PID logs/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J42 rollback and distinguish manual method scheduling from engine lifecycle; then select FPSQueue or the next measured component from J41 audit.
- **DEPENDENCIES:** L5b-3b/J42 and original InterpolationController source/metadata audit.

## L5b-3d — Original FPSQueue initialization and callback
- **ID:** L5b-3d
- **STATUS:** PASS — J45 fresh foreground verification; J44 rejected capture preserved
- **TITLE:** Verify original frame sampling without activating full application update
- **CONTEXT:** J43 proves original interpolation methods under diagnostic scheduling.
- **OBSERVATION:** FPSQueue.Start subscribes its callback to RoR2Application.onUpdate and allocates samples; the callback advances queue turns and computes sampled FPS.
- **HYPOTHESIS:** The original callback and sample queue can operate correctly with measured real frame deltas while the full application remains inactive.
- **TASK:** Revalidate exact callback/state signatures; capture prior subscription/static state, invoke original Start, identify only the newly registered original callback, exercise it across real frames, and verify frame sampling/queue wrap behavior. Restore state/subscription afterward. Never invoke unrelated onUpdate subscribers.
- **CONSTRAINTS:** Common contract; no fabricated frame metrics or rewritten queue, no whole application Update call, no gameplay-performance claim. Clean or in-place installation permitted under owned-package safeguards.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow startup probe/preparation and ignored timing/callback evidence, state/journal.
- **TEST COMMAND:** Existing preflight, forced Vulkan build and startup-run lifecycle; add only the needed option.
- **PASS CONDITION:** Original subscription and callback produce expected queue/sample behavior over real frames, restore ownership/state and survive on device. Automatic game-loop integration remains separate.
- **FAILURE EVIDENCE TO CAPTURE:** First missing callback/array/state/timing mismatch, real deltas, invocation identity, original DLL/APK/payload identity, current-PID report/log/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J43; distinguish callback proof from full frame loop; select postprocessing/NGSS next using the existing audit.
- **DEPENDENCIES:** L5b-3c/J43 and J41 component audit plus pinned FPSQueue signatures.

## T08-J44 — Foreground attribution for scene capture
- **ID:** T08-J44
- **TITLE:** Reject a screenshot belonging to another app
- **CONTEXT:** Supports immediate L5b-3d acceptance, not a general observability expansion.
- **OBSERVATION:** J44 method report passed while screenshot showed another foreground app.
- **HYPOTHESIS:** Checking resumed activity before capture prevents silently accepting this mismatch.
- **TASK:** Record current activity dump locally, require the lab resumed component, and reject unknown/other app identity. Review the resulting screenshot as before.
- **CONSTRAINTS:** Keep private activity details/captures ignored. Do not switch away from an actively used app without resolving device availability.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing scene runner and one regression test.
- **TEST COMMAND:** `./dev test`; next foreground device verification.
- **PASS CONDITION:** Host regression rejects a passing method marker with another app foreground; actual capture still requires visual review.
- **FAILURE EVIDENCE TO CAPTURE:** Current resumed activity, PID/report and image mismatch.
- **STATE/JOURNAL UPDATES REQUIRED:** J44 rejection remains immutable; only fresh verified capture can advance acceptance. Roll back this guard with its focused change if parsing is incompatible, after recording the exact failure.
- **DEPENDENCIES:** J44 observed capture mismatch.

## L5b-3e — Recovered postprocessing volume lifecycle
- **ID:** L5b-3e
- **STATUS:** PASS — J46, first volume registration/update/removal; both profiles audited
- **TITLE:** Verify original volume registration against recovered profiles
- **CONTEXT:** J45 passes isolated FPSQueue callbacks; two disabled PostProcessVolume entries remain in the recovered application enable list.
- **OBSERVATION:** Original OnEnable registers with PostProcessManager and initializes volume state; OnDisable unregisters. Two serialized profile references and their settings need inspection before execution.
- **HYPOTHESIS:** Real recovered profiles and unchanged original registration methods can satisfy the manager contract without enabling full postprocessing rendering.
- **TASK:** Resolve both profile identities/settings and inspect pinned manager initialization requirements. Select one volume first, record existing registration state, execute original OnEnable/Update/OnDisable where justified, and assert balanced registration plus required profile identities. Stop at the first manager/profile/resource failure before testing the second volume.
- **CONSTRAINTS:** Common contract; no synthetic profile or manager success, no final effect/shader parity claim, no full application activation. Explicit method invocation remains distinguished from automatic lifecycle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing startup probe/preparation and narrow ignored profile/manager evidence, state/journal.
- **TEST COMMAND:** Existing preflight, forced Vulkan build and startup-run with current-PID foreground capture; add only the needed volume option.
- **PASS CONDITION:** Selected original registration lifecycle balances and recovered references match; stable device lifetime and no new unexplained exception. Rendering and the second volume are separate until measured.
- **FAILURE EVIDENCE TO CAPTURE:** First profile/setting/manager/resource failure, actual registration state and lifecycle boundaries, source/APK/payload identities and current foreground capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J45 accepted verification; record bounded volume outcome and next volume or NGSS boundary.
- **DEPENDENCIES:** L5b-3d/J45 and J41 component audit with fresh profile/manager inspection.

## L5b-3f — Second volume and priority ordering
- **ID:** L5b-3f
- **STATUS:** PASS — J47, both lifecycles, original priority/layer query and balanced cleanup
- **TITLE:** Verify recovered override-volume registration and ordering
- **CONTEXT:** J46 passes ppApplication_opt lifecycle and audits ppDisabler_opt without invoking it.
- **OBSERVATION:** The second volume has priority 99999 and disabled effect settings; original manager sorts registered volumes by priority for eligible layers.
- **HYPOTHESIS:** Original registration/sorting preserves both recovered profile identities and removes them cleanly without rendering effects.
- **TASK:** Revalidate original manager query/sort contract; register the second volume and first in an order that discriminates priority sorting, inspect the original manager result for their actual layer, and unregister both with balanced cleanup. Preserve existing entries and exact recovered priority/profile values.
- **CONSTRAINTS:** Common contract; no authored sorting substituted for manager behavior, no rendering or visual-disable claim, no full application activation. Stop on first second-volume or manager-query failure.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small existing volume-probe extension, ignored manager/query evidence, state/journal.
- **TEST COMMAND:** Existing preflight, forced Vulkan build and startup-run with verified foreground capture.
- **PASS CONDITION:** Both real profiles register, original query orders them as specified, and registrations cleanly return to baseline; stable device lifetime without new exceptions.
- **FAILURE EVIDENCE TO CAPTURE:** First registration/profile/layer/query-order failure, before/during/after manager state, source/APK/payload identities and current-PID capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J46 rollback, distinguish manager ordering from rendered effects, then select NGSS from the existing audit.
- **DEPENDENCIES:** L5b-3e/J46 and pinned manager query/sort contract.

## L5b-3g — Recovered NGSS initialization
- **ID:** L5b-3g
- **STATUS:** PASS — J48, locally recompiled NGSS noise/global contract and restoration
- **TITLE:** Verify the remaining shadow component initialization contract
- **CONTEXT:** J47 passes both postprocessing volume lifecycles; NGSS_Local remains unexecuted in the measured enable list.
- **OBSERVATION:** Prior audit shows graphics support checking, shader-global initialization and a possible LegacyResourcesAPI noise fallback when the serialized texture is null. Its current compiled-code provenance must be explicit.
- **HYPOTHESIS:** The recovered component retains its required noise reference and can initialize the measured globals on Vulkan without a broad shadow implementation.
- **TASK:** Verify whether the staged NGSS type comes from preserved DLL or locally recovered source, record hashes and exact lifecycle signatures, resolve the serialized noise identity and expected globals, then execute the smallest initialization/update/disable probe with previous-state restoration. Split on missing native/resource/shader contract.
- **CONSTRAINTS:** Common contract; no recovered source committed, no original-DLL claim for recompiled code, no rendered-shadow parity claim, no full application activation.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow existing startup probe/preparation, ignored provenance/noise/shader-global evidence, state/journal.
- **TEST COMMAND:** Existing preflight, forced Vulkan build and foreground-verified startup-run; thin NGSS option only if needed.
- **PASS CONDITION:** Measured initialization and reference/global assertions pass and state restores on device, with truthful code provenance and no new unexplained exception.
- **FAILURE EVIDENCE TO CAPTURE:** First graphics-support/noise/resource/global mismatch, actual lifecycle state, source/assembly/APK/payload identities and current-PID capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J47, then review evidence for integrated startup rather than adding more speculative component probes. L5 menu remains open.
- **DEPENDENCIES:** L5b-3f/J47 and current staged NGSS provenance/serialized contract audit.

## L5b-4 — Controlled integrated startup
- **ID:** L5b-4
- **STATUS:** PASS — J49, controlled pre-audio segment only
- **TITLE:** Move from isolated method probes to actual application/component startup
- **CONTEXT:** J48 completes bounded method evidence for the six listed startup components. Application automatic lifecycle and full initialization remain unproven.
- **OBSERVATION:** Existing probes use inactive objects, explicit calls and a diagnostic coroutine host. Activating a host after manual Awake risks original singleton destruction; other attached components may have untested automatic callbacks.
- **HYPOTHESIS:** A fresh recovered application host with a reviewed callback closure can reach a bounded integrated startup state while preserving original ordering and truthful service state.
- **TASK:** Inventory all components and Awake/OnEnable/Start/Update obligations on the actual host, including those outside the six-item enable list. Trace exact original coroutine and singleton ordering. Choose the smallest integration experiment that executes actual callbacks without duplicate initialization, then stop before the first unreviewed audio/platform boundary. Split if required callbacks introduce a new subsystem.
- **CONSTRAINTS:** Common contract; no fake loading/entitlement/authentication flags, empty-list success or broad callback deletion, no vanilla profile writes before Android paths are established. Do not activate a previously manually awakened host. Any targeted adapter requires measured necessity and explicit provenance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing startup probe and generated scene configuration, narrow ignored callback/ordering evidence, state/journal.
- **TEST COMMAND:** Existing preflight, forced Vulkan build and foreground-verified device lifecycle; thin integration action when the exact boundary is recorded.
- **PASS CONDITION:** The selected actual callback/startup segment reaches its declared boundary with real host/component identities, stable device lifetime and no unexplained exception. Menu acceptance remains separate until reached and navigated.
- **FAILURE EVIDENCE TO CAPTURE:** First singleton/callback/reference/native/service failure, exact execution boundary and original component state, source/APK/payload identities, current-PID foreground capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J48 and earlier accepted checkpoints; review architecture evidence and select the next measured integration/audio boundary. Do not declare L5 from isolated tests.
- **DEPENDENCIES:** L5b-3a–g/J41–J48, existing startup/profile prior-art audit and complete attached callback inventory.

## L5b-5 — Wwise startup resource and native boundary
- **ID:** L5b-5
- **STATUS:** AUDITED — J50; resource identity closure remains open, next L5b-5a
- **TITLE:** Identify and test the next actual audio initialization dependency
- **CONTEXT:** J49 reaches the yield immediately before original WwiseIntegrationManager.Init.
- **OBSERVATION:** Init requests WwiseGlobal and AudioManager through LegacyResourcesAPI; compatible Android middleware/bank access remains unresolved.
- **HYPOTHESIS:** Existing resource and middleware evidence can identify a bounded legitimate next step without speculative replacement.
- **TASK:** Review prior audio research, exact resource closures and callback/native requirements; select the first discriminating resource or authorized native probe. Preserve separate missing-resource and middleware outcomes.
- **CONSTRAINTS:** Common contract; no fabricated audio/service success, no unreviewed startup continuation, no Steam profile writes. Reuse prior evidence before acquiring or rebuilding anything.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow ignored dependency audit, existing startup harness only if required, state/journal.
- **TEST COMMAND:** Existing dependency reports first; then preflight, forced Vulkan build and startup-run only for the selected device probe.
- **PASS CONDITION:** Exact next contract and access requirements are recorded; any executed probe satisfies independent assertions. Audio acceptance remains separate.
- **FAILURE EVIDENCE TO CAPTURE:** First missing resource, callback, API or native dependency; artifact provenance and current-launch diagnostics.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J49 rollback; record candidate and first failure, update audio risk and next action.
- **DEPENDENCIES:** L5b-4/J49 and existing audio/prior-art evidence.

## L5b-5a — Audio prefab identity and asynchronous asset loading
- **STATUS:** PASS — J52, original legacy-path loads on Android; no prefab activation or native audio.
- **ID:** L5b-5a
- **TITLE:** Resolve and load the two audio prefab assets without activating native callbacks
- **CONTEXT:** J50 identifies the resource/native split and absent separate native library in the accepted APK.
- **OBSERVATION:** Existing editor reports do not resolve most audio prefab script references; Init schedules callbacks rather than waiting for completion.
- **HYPOTHESIS:** The established small Android catalog can support original legacy-path loads independently of sound-engine instantiation.
- **TASK:** Resolve all prefab script and initialization-settings identities first. Stage only the measured closure; invoke original legacy-path loading with diagnostic callbacks that inspect assets without instantiation.
- **CONSTRAINTS:** Common contract; keep Wwise Init suspended, no native success substitution, preserve originals and J49 rollback.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing identity/catalog tooling, narrow startup probe and ignored audio closure.
- **TEST COMMAND:** Existing editor identity reports, then preflight, forced Vulkan build and foreground-verified startup-run.
- **PASS CONDITION:** Both original mappings resolve; asynchronous operations succeed with expected non-null prefab identities, balanced pending counts and released handles; no prefab activation or unexplained exception.
- **FAILURE EVIDENCE TO CAPTURE:** Unresolved script/settings reference, catalog/provider failure, result status, pending counts and current-launch diagnostics.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve separate resource/native outcomes and source hashes; do not advance L10 or claim sound.
- **DEPENDENCIES:** J49, J50, existing Addressables initialization and preservation evidence.

## L5b-5b — Native audio feasibility and bounded unavailable-audio alternative
- **ID:** L5b-5b
- **TITLE:** Select a lawful next audio lifecycle candidate
- **STATUS:** DISCRIMINATING PASS — J53 confirms absent native runtime; audio capability remains unavailable
- **CONTEXT:** J52 proves audio asset loading independently of activation.
- **OBSERVATION:** Preserved bindings import AkSoundEngine and default to Windows; accepted APK has no separate native engine. Activation also starts eight bank loaders.
- **HYPOTHESIS:** A compatible authorized runtime, or explicit unavailable-audio handling over a measured lifecycle, can support further startup.
- **TASK:** Check existing authorized middleware inputs and matching API/settings/native contract first. If unavailable, audit all immediate startup audio calls and define one bounded no-audio candidate without reporting engine/bank success.
- **CONSTRAINTS:** Common contract; no speculative SDK acquisition, fabricated AK success, entitlement bypass or broad gameplay rewriting. Preserve J52 and J49.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Local middleware inventory, narrow lifecycle audit and only the selected probe/adapter if justified.
- **TEST COMMAND:** Existing inventory/source reports; preflight and forced Android lifecycle only after selecting the candidate.
- **PASS CONDITION:** Exact candidate and access requirements recorded; execution must satisfy independent lifecycle assertions before advancing.
- **FAILURE EVIDENCE TO CAPTURE:** ABI/API mismatch, native resolution, bank/init errors or unhandled audio call; current-launch evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** Update audio risk and first failure; never advance audio/menu acceptance from asset loading.
- **DEPENDENCIES:** J50–J52, existing audio prior art.

## L5b-5c — Explicit unavailable-audio startup boundary
- **ID:** L5b-5c
- **TITLE:** Test one input-gated early audio guard
- **STATUS:** PASS — J55 early guard only; J54 preparation failure preserved
- **CONTEXT:** J53 confirms missing native runtime through original code on Android.
- **OBSERVATION:** Original early Init activates native-dependent prefabs; the following yields precede filesystem/platform setup.
- **HYPOTHESIS:** An explicit unavailable-audio guard can preserve original coroutine ordering through the next Addressables yield.
- **TASK:** Inspect original IL and exact call-site semantics; implement one narrowly gated candidate with authored unavailable capability evidence. Continue only through Addressables initialization, stopping before filesystem/platform code.
- **CONSTRAINTS:** No fabricated native success, no service/entitlement changes, no original installation edits. Distinguish transformed assembly hashes. Do not claim complete no-audio lifecycle; later queries/dialogs/bank waits remain open.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow local assembly transformation, provenance validation and existing startup probe.
- **TEST COMMAND:** Transformation contract assertions, preflight, forced Vulkan build and startup-run.
- **PASS CONDITION:** Explicit audio-unavailable observation, original coroutine reaches expected yield, real Addressables completion, unchanged filesystem globals and stable device lifetime.
- **FAILURE EVIDENCE TO CAPTURE:** IL mismatch, altered unexpected method, native call, initialization or preservation error; assembly/APK identities and current-launch capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J52/J53 and record exact altered method and limits; update next boundary.
- **DEPENDENCIES:** J49, J52, J53; minimum provenance tooling only.

## L5b-6 — Coupled profile and platform boundary
- **ID:** L5b-6
- **TITLE:** Isolate filesystem setup from mandatory platform startup
- **STATUS:** BOUNDED PASS — J57 temporary config bindings; original platform/filesystem continuation unproven; J56 preserved
- **CONTEXT:** J55 stops after the Addressables yield, before filesystem creation and PlatformSystems.Init.
- **OBSERVATION:** The next original coroutine step performs both without an intervening yield; Application.dataPath is not the Android writable profile root.
- **HYPOTHESIS:** A measured Android path policy and explicit platform boundary can preserve truthful startup semantics.
- **TASK:** Inspect exact filesystem/platform IL and concrete initialization calls, reusing prior startup research. Select a bounded filesystem-only proof before invoking platform services; identify mandatory ownership checks rather than bypassing them.
- **CONSTRAINTS:** Common contract; no Steam profile writes, fabricated authentication/ownership or successful service stubs. Preserve later no-audio obligations.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow ignored IL/source audit, Android path adapter and existing probe only when justified.
- **TEST COMMAND:** Existing metadata inspection first; preflight and forced device lifecycle for the chosen candidate.
- **PASS CONDITION:** Exact safe boundary and truthful contracts recorded; runtime proof must use owned writable paths and preserve required checks.
- **FAILURE EVIDENCE TO CAPTURE:** First path, constructor or service dependency; changed-method provenance and current-launch state.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J55 rollback; update profile/platform risks and next action without claiming menu readiness.
- **DEPENDENCIES:** J55, original startup/profile research, L9 foundation.

## L5b-7 — Concrete offline platform boundary
- **ID:** L5b-7
- **TITLE:** Classify original platform initialization and mandatory checks
- **STATUS:** DISCRIMINATING RESULT — J58 original load false; platform capability unproven
- **CONTEXT:** J57 proves temporary writable configuration bindings; original coroutine remains before PlatformSystems.Init.
- **OBSERVATION:** SteamworksClientManager starts before crossplay selection and can replace cloudStorage; concrete entitlement/save/achievement implementations follow.
- **HYPOTHESIS:** Exact consumer and initialization evidence can separate optional services from required checks without fabricating success.
- **TASK:** Inspect original SteamworksClientManager, save-system initialization and entitlement resolver call paths. Identify a bounded truthful candidate and required legitimate access; stop dependent startup if a mandatory check has no legitimate route.
- **CONSTRAINTS:** No fabricated ownership/authentication, no broad successful service stubs, no Steam profile access. Preserve original networking/authority semantics and later audio obligations.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing metadata/source audit and narrow adapter only after justified selection.
- **TEST COMMAND:** Existing inspection tools first; device probe only for a defined contract.
- **PASS CONDITION:** Required versus optional contracts and first candidate documented from exact input; actual execution needs independent assertions.
- **FAILURE EVIDENCE TO CAPTURE:** Mandatory access gap, native/API dependency, profile-root replacement or service failure.
- **STATE/JOURNAL UPDATES REQUIRED:** Update platform/profile risks and first failure; retain J57 rollback and explicit unproven gates.
- **DEPENDENCIES:** J55/J57 and existing prior-art startup audit.

## L5b-7a — Attribute the caught Steam failure
- **ID:** L5b-7a
- **TITLE:** Observe the first failure without changing platform outcome
- **STATUS:** ATTRIBUTED — J60 Windows native library missing; J59 contaminated second-call result rejected
- **CONTEXT:** J58 original load returns false, but its catch discards exception details.
- **OBSERVATION:** The result cannot distinguish native initialization, API validation or mandatory subscription paths.
- **HYPOTHESIS:** One input-gated diagnostic observation can identify the first failed prerequisite while preserving original checks and result.
- **TASK:** Inspect the exact catch/control flow; add minimal failure attribution or an equivalent isolated prerequisite probe. Preserve false and do not proceed into profile/gameplay startup.
- **CONSTRAINTS:** No replaced success, ownership/authentication bypass, or service emulation. Attribute any diagnostic assembly change separately.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow metadata/diagnostic transformation and existing startup harness.
- **TEST COMMAND:** Input/control-flow assertions, preflight, forced Vulkan build and startup-run.
- **PASS CONDITION:** First failure attributable to this launch; original false result and filesystem isolation preserved. A diagnostic pass does not pass platform acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** Exception type/stack or first prerequisite result, assembly/APK provenance and current-launch capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Record cause and legitimate next options, preserve J58; reassess architecture access risks.
- **DEPENDENCIES:** J58 and minimal T08 observation only.

## L5b-7b — Legitimate platform runtime feasibility
- **ID:** L5b-7b
- **TITLE:** Evaluate authorized runtime options against the measured Steam dependency
- **STATUS:** BLOCKED — J61 documented missing compatible Android ARM64 binding/runtime and absent publisher authorization
- **CONTEXT:** J60 fails in Win64 SteamAPI_Init on Android before ownership checks.
- **OBSERVATION:** The original managed binding selects a Windows DLL; no compatible authenticated Android route is established.
- **HYPOTHESIS:** Official runtime/platform documentation and existing authorized inputs can determine whether a legitimate bounded integration exists.
- **TASK:** Verify supported native targets and the exact binding contract, reuse prior research, and record feasible authorized options or an access blocker. Preserve mandatory ownership checks; separate optional services from the base client.
- **CONSTRAINTS:** No fake successful service/authentication/entitlement responses or arbitrary backend substitution. Do not acquire proprietary SDKs without appropriate access.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Source/runtime inventory and cited feasibility evidence; no speculative adapter.
- **TEST COMMAND:** Read-only source/runtime inspection and authoritative documentation; new device probe only for a justified candidate.
- **PASS CONDITION:** Concrete legitimate route or explicit prerequisite gap documented; this does not itself pass L5.
- **FAILURE EVIDENCE TO CAPTURE:** Unsupported ABI/platform, unavailable authorized runtime or unresolved mandatory checks.
- **STATE/JOURNAL UPDATES REQUIRED:** Reassess architecture/access risks; keep dependent startup stopped if no legitimate route exists and select useful independent work.
- **DEPENDENCIES:** J58–J60, existing platform prior art.

**J61 result:** Read-only exact-binding and authoritative-documentation review finds no lawful candidate on the authorized generic Android device. The preserved Facepunch source exposes only Windows, Linux x86/x64 and macOS implementations, and its fallback reaches the J60 Win64 `steam_api64.dll` import. Valve's current Android path requires rights-holder Steam Frame/Steamworks configuration of an Android depot, APK launch option and package access; the accepted desktop entitlement/input supplies none of those and no Android ARM64 runtime is present. See `docs/l5b-7b-platform-runtime-feasibility.md`. Do not run another constructor/load probe or add a stub. Reopen only with a rights-holder-provided compatible runtime and integration authority; L5, original profile startup and L5.5 remain blocked.


## L10-a — Remaining unavailable-audio lifecycle audit
- **ID:** L10-a
- **TITLE:** Attribute remaining no-audio obligations without crossing J61
- **STATUS:** COMPLETE — J63 source-only attribution; Astra must select any subsequent runtime candidate
- **CONTEXT:** L10 supporting work and unfinished L5b-5c/J55 obligations; C remains platform-deferred.
- **OBSERVATION:** J55 guards early initialization only; later query/dialog, bank waits and teardown are not covered by its device proof.
- **HYPOTHESIS:** Exact-input static tracing can separate suppressed, remaining and platform-coupled audio obligations without running startup.
- **TASK:** Execute the bounded matrix/evidence contract in architecture-review-j61.md. Reuse J50–J55 evidence and inspect pinned R2API.Sound prior art. Trace query/dialog, identified audio-prefab callbacks/bank producers/waits, shutdown registrations and cleanup; annotate unresolved indirect calls. Return results to Astra for runtime candidate selection.
- **CONSTRAINTS:** Read-only input/project/assembly/device/checkpoints; no Steam retry, stub, backend switch, middleware substitution, broad rewrite or weakened assertion. Preserve all accepted evidence and pins.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored audit summary/state/journal/backlog and ignored source-hashed evidence only.
- **TEST COMMAND:** ./dev doctor (record current attachment failure honestly); existing input/source/transform receipt verification; git diff --check; python3 scripts/audit-public.py after staging. No build/install/run is authorized by this issue.
- **PASS CONDITION:** Every scoped obligation traced or explicitly unresolved; first uncovered dependency and independence limits recorded. No runtime/no-audio/menu capability claim. Astra, not Terra, selects any next runtime candidate.
- **FAILURE EVIDENCE TO CAPTURE:** Input mismatch, unresolved callbacks/lifetime, missing producer, native dependency or platform coupling; distinguish inference from execution.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve local evidence, publish only authored conclusions, record limits, review status/privacy, commit/push coherent checkpoint and transfer sole control to Astra Low.
- **DEPENDENCIES:** J52/J53/J55 accepted evidence and J62 architecture decision; no requirement to cross blocked L5. Runtime prerequisites remain separate.

**J63 result:** The exact-input source-hashed matrix is recorded in `docs/l10-a-unavailable-audio-lifecycle-audit.md`. It attributes the first uncovered obligation to the later original native query and Windows-runtime dialog, downstream of J61's platform/Steam boundary. It also identifies that J55 suppresses the known bank-load producers, so a zero pending counter would not prove bank/callback lifecycle, and that whole-app teardown invokes platform shutdown callbacks. No isolated runtime candidate is specified; no capability advances. Current doctor additionally reports no authorized ADB device as well as no editor attachment, so both prerequisites must be restored before Astra selects or runs any runtime work.


## L11-a — Original skin material assignment and Vulkan rendering
- **ID:** L11-a
- **TITLE:** Turn J38 material records into a visible Android material result
- **STATUS:** PASS — J66, original assignments and Vulkan material/emission captures in two fresh processes; J65 inherited build failure preserved
- **CONTEXT:** Independent L11 work while J61 defers platform startup; J38 skin and J28 display evidence remain accepted.
- **OBSERVATION:** Original ApplyAsync fills mesh/material records, but original renderer slot assignment and converted material rendering are not yet proven together.
- **HYPOTHESIS:** Original material selection in a detached display context plus one authored Android albedo/emission shader can render the recovered three-mesh skin on Vulkan.
- **TASK:** Implement and execute docs/l11-commando-material-device-contract.md using existing skin/probe/display infrastructure. No standalone audit replacement.
- **CONSTRAINTS:** Original DLLs unchanged; inactive gameplay; explicit display-only body-null fixture; no platform/profile/audio/Run initialization, fake capability or original-installation changes. Preserve pins and accepted results.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing ControllerAddressProbe/LoadingSceneProbe, narrow shader/material conversion and scene_runtime preparation; ignored derived closure/evidence; concise state/journal.
- **TEST COMMAND:** ./dev doctor; ./dev preflight; relevant ./dev test checks; existing forced Vulkan build/install/run/capture with the new thin action documented before use.
- **PASS CONDITION:** Three original slot-identity assertions, two fresh device runs, Vulkan rendering and emission sensitivity captures, unchanged original assemblies and balanced owned cleanup. Display bridge is explicit; no gameplay or shader parity claim.
- **FAILURE EVIDENCE TO CAPTURE:** First closure/ApplyAsync/AOT/assignment/shader/device-output failure, APK/payload/material identities and current foreground evidence; no substituted success.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failures, record actual capability and limits, staged privacy review, coherent commit/push, hand evidence back to Astra.
- **DEPENDENCIES:** J38/J28, accepted input, restored editor/device and passing runtime prerequisites; L5 is not required for this independent fixture.

## S01 — Original state-machine scheduling precursor
- **ID:** S01
- **TITLE:** Original EntityStateMachine queue, tick and destruction behavior on Android
- **CONTEXT:** J66 content/material proof passes; platform-dependent L5 remains blocked. This independent precursor does not pass L5.5.
- **OBSERVATION:** Original scheduler separates fixed/update transitions; Idle inherits original age accumulation without character/native-service dependencies.
- **HYPOTHESIS:** The original component can initialize, transition, tick and clean up under Android IL2CPP without application startup.
- **TASK:** Extend accepted material fixture with an isolated original EntityStateMachine; assert deferred Idle transition, both scheduling branches, exact fixed-age accumulation, interrupt acceptance, Unity-driven ticks and destruction.
- **CONSTRAINTS:** No authority fabrication, body/master activation, game-assembly changes or catalog substitution. Idle only; this does not establish actual character-state behavior.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** One lab probe, thin prepare action, current-attempt runtime assertions.
- **TEST COMMAND:** `./dev prototype --action state-tick-prepare`; forced Vulkan build; `./dev prototype --action controller-run`.
- **PASS CONDITION:** Attributed device report passes all scheduler assertions and inherited content checks, with 70-second process survival and no unexplained failure.
- **FAILURE EVIDENCE TO CAPTURE:** First compiler/runtime exception, state/age observations, attempt/PID, unchanged original DLL hashes, current process logs.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failed attempts, record exact tested scope and next dependency; keep L5/L5.5 open.
- **DEPENDENCIES:** J66; original source and pinned Starstorm2 BarrageCharge inspected for queue/age/authority usage. No community code copied.
- **STATUS:** PASS — J68; original queue/timing/cleanup assertions and 70.54-second Android run. Character simulation remains separate.

## S02 — Original facing with local server authority
- **ID:** S02
- **TITLE:** CharacterDirection authority guard and deterministic turning
- **CONTEXT:** S01 scheduler passes; full body/master activation still needs measured dependencies.
- **OBSERVATION:** CharacterMotor/InputBank require CharacterBody; CharacterDirection independently consumes a direction vector and checks original effective authority.
- **HYPOTHESIS:** An actual local server-owned NetworkIdentity enables original direction simulation while the same fixture without authority cannot turn.
- **TASK:** Verify negative authority control, start a loopback-only HLAPI server, spawn the owned fixture, invoke original direction initialization/simulation, verify east-facing convergence and neutral-input hold, then destroy/shut down owned state.
- **CONSTRAINTS:** No authority/property patching, platform adapters, CharacterBody/master or walking claim. Refuse pre-existing network sessions. No remote client or matchmaking.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** One direction probe and thin existing prepare/run integration.
- **TEST COMMAND:** `./dev prototype --action direction-prepare`; forced Vulkan build; `./dev prototype --action controller-run`.
- **PASS CONDITION:** Current-attempt/PID assertions pass, real spawned identity/effective authority recorded, unauthorised turn blocked, original rotation converges, local server shuts down, inherited checks and 70-second survival pass.
- **FAILURE EVIDENCE TO CAPTURE:** Native transport errors, spawn/authority state, rotation, first exception, cleanup and current-process logs.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve build/run evidence and rollback; distinguish component ownership from full character authority and L5.5.
- **DEPENDENCIES:** S01; pinned DebugToolkit NetworkManager actual active-server/Spawn/Destroy usage and original CharacterDirection/Util/HLAPI source reviewed. No community code copied.
- **STATUS:** PASS — J69; unauthorised control, real server spawn/authority, east-facing convergence, neutral hold and owned shutdown all pass on Android.

## S03–S06 — Sequential isolated input/motor batch
Shared task contract:
- **CONTEXT:** User requests multiple independent experiments per pass, sequentially without subagents. S01/S02 pass; full movement remains unproven.
- **CONSTRAINTS:** One APK, separate fresh process per experiment. Separate durable started/terminal reports and captures; continue after independent failure. No original assembly changes, fabricated authority or gameplay startup. Inactive body fixtures only.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** MovementBatchProbe, thin prepare/run actions, existing device safeguards.
- **TEST COMMAND:** `./dev prototype --action movement-batch-prepare`; forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **FAILURE EVIDENCE TO CAPTURE:** Probe ID, current attempt/PID, started/terminal phase, first exception, survival, native/managed logs and cleanup. Never promote another probe's pass as a failed probe's result.
- **STATE/JOURNAL UPDATES REQUIRED:** Record each result separately; archive exact stage/build/input hashes and retain previous checkpoint. No L5.5 promotion.
- **DEPENDENCIES:** S02 closure; original InputBankTest/CharacterMotor/CharacterBody and pinned DebugToolkit network/motor references inspected.

| ID / TITLE | OBSERVATION | HYPOTHESIS | TASK / PASS CONDITION | STATUS |
| --- | --- | --- | --- | --- |
| S03 — Button edges | InputBank button state is a standalone original value type. | Press/hold/release and claim reset work under AOT. | Six exact edge/claim assertions plus attributed stable process. | PASS — J70 |
| S04 — Directional input and aim | InputBank requires a body but these methods do not run its lifecycle. | Inactive fixture supports original thresholds and normalization. | Verify press/hold/release hysteresis, opposite axes, normalized aim, zero fallback and button aggregation. | PASS — J70 |
| S05 — Motor output callbacks | UpdateVelocity/UpdateRotation have no simulation-side effects. | Original callbacks return configured velocity and upright rotation. | Verify velocity (2,3,-4), identity rotation and inactive body. | PASS — J70 |
| S06 — Motor acceleration/braking | PreMove requires authority, body stats and kinematic grounding context. | Real server identity plus inactive fixture can execute original velocity calculation. | With diagnostic speed 7, acceleration 10 and air control 1, verify first 0.1-second step yields 1, cap 7 and neutral braking 0; real authority and cleanup required. No translation claim. | PASS — J70 |

## S07–S11 — Sequential shipped-kinematic solver batch
- **CONTEXT:** Input and motor arithmetic pass J70; actual position integration and collision solving remain unproven.
- **OBSERVATION:** Shipped KinematicCharacterMotor exposes phases, collision/ground callbacks and computed transient position. Full CharacterMotor landing reaches GlobalEventManager/body dependencies.
- **HYPOTHESIS:** Original solver can integrate and resolve fixtures with an authored diagnostic velocity supplier, independently of those game-wide callbacks.
- **CONSTRAINTS:** Separate cold launches and results; no CharacterBody, gameplay controller replacement or character-simulation acceptance. Original solver performs movement; harness supplies velocities and publishes solver results via original API. Owned collision geometry only.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** KinematicBatchProbe and existing sequential batch selector.
- **TEST COMMAND:** `./dev prototype --action kinematic-batch-prepare`; successful forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **FAILURE EVIDENCE TO CAPTURE:** Started/terminal marker, original solver exception, position, grounding, hit callbacks, process crash and per-launch logs.
- **STATE/JOURNAL UPDATES REQUIRED:** Keep each pass/failure independent, retain stage/APK and accepted parent; do not advance L5.5.
- **DEPENDENCIES:** J70 batch runner; pinned DebugToolkit collision-layer prior art and exact-input KinematicCharacterMotor/System phases inspected.

| ID / TITLE | TASK / PASS CONDITION | STATUS |
| --- | --- | --- |
| S07 — Free integration | Original solver produces 2m displacement from 2m/s over 1s. | PASS — J71 |
| S08 — Wall stop | Capsule stops at expected wall boundary and original hit callback occurs. | PASS — J71 |
| S09 — Wall slide | Same normal boundary with continued tangent displacement. | PASS — J71 |
| S10 — Floor grounding | Solver reports stable floor and expected foot height. | PASS — J71 |
| S11 — Unground | After verified grounding, original ForceUnground plus upward velocity leaves floor. | PASS — J71 |

## S12–S15 — Original CharacterMotor plus solver
- **CONTEXT:** J70 original motor arithmetic and J71 shipped solver pass independently.
- **OBSERVATION:** CharacterMotor implements the solver callbacks; its landing callback additionally reaches global game-event state.
- **HYPOTHESIS:** Original motor can drive free motion/collision before those broader dependencies are initialized.
- **CONSTRAINTS:** Separate fresh launches, original callbacks unmodified, actual server-owned identity; body lifecycle inactive and diagnostic stats supplied explicitly. No gravity trajectory or full character acceptance claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing MovementBatchProbe and selector.
- **TEST COMMAND:** `./dev prototype --action motor-integration-prepare`; successful forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **FAILURE EVIDENCE TO CAPTURE:** First original exception/stack, phase, movement values, separate process report, shutdown and logs.
- **STATE/JOURNAL UPDATES REQUIRED:** Advance only individual passing checkpoints; record failed landing dependency without bypassing it.
- **DEPENDENCIES:** J70/J71; pinned DebugToolkit motor/network prior art and exact original callbacks inspected.

| ID / TITLE | TASK / PASS CONDITION | STATUS |
| --- | --- | --- |
| S12 — Original integrated motion | Original acceleration gives 4.62m in 1s at diagnostic acceleration10/speed 7, then brakes to zero. | PASS — J72 |
| S13 — Original wall callback | Original motor/solver stops at wall and clears disable-air-control collision flag. | PASS — J73, corrected initial-velocity fixture |
| S14 — Original Jump method | Diagnostic speed 7/power5 produces velocity(7,5,0), integrated for0.5s without gravity. | PASS — J72 |
| S15 — Original landing boundary | Execute original ground/landing callbacks; stable grounding without exceptions passes, otherwise classify first missing dependency. | FAILED — J72 original OnLanded null-reference; game-wide context unresolved |

## S16–S19 — Landing context batch
- **CONTEXT:** J72 landing failed in original OnLanded; free/wall/jump method paths pass.
- **OBSERVATION:** Original landing dereferences GlobalEventManager, then RunArtifactManager and the fall-damage artifact definition. Recovered artifact closure contains 17 files with no unresolved GUIDs.
- **HYPOTHESIS:** Original manager methods and a measured original artifact in a diagnostic catalog can supply this bounded landing context.
- **CONSTRAINTS:** Separate processes, original assemblies unchanged; one-entry diagnostic catalog is not full content initialization. Required Run remains inactive. Original artifact/serialized dependencies retained; no ownership/unlock or artifact availability claim. No callback suppression.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing batch probe/runner, narrow artifact closure staging into separate bundle, original content cache slots for the duration of the fixture.
- **TEST COMMAND:** `./dev prototype --action landing-batch-prepare`; forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **FAILURE EVIDENCE TO CAPTURE:** Original stack, artifact identity/reference checks, manager identity, catalog state, landing position, RPC/native errors, cleanup and per-process logs.
- **STATE/JOURNAL UPDATES REQUIRED:** Keep results independent, retain J72 failure, distinguish landing fixture from full body/master, effects/audio and actual game startup.
- **DEPENDENCIES:** J72/J73; pinned DebugToolkit CurrentRun artifact manager/catalog usage and exact original manager/landing source inspected.

| ID / TITLE | TASK / PASS CONDITION | STATUS |
| --- | --- | --- |
| S16 — Event manager lifecycle | Original OnEnable assigns singleton; OnDisable releases it. | PASS — J75 |
| S17 — Artifact catalog identity | Original recovered definition and references load; original one-entry catalog assigns/resolves its index. | PASS — J75 |
| S18 — Artifact manager initialization | Original pool initialization, Awake and OnEnable establish manager; recovered artifact correctly reports disabled. | PASS — J75 |
| S19 — Landing with measured context | Original motor landing reaches stable floor without exception or unexplained log error; managers/catalog restored afterward. | PASS — J77 after full measured layer-name repair |

## S20–S24 — Gravity and original movement-state batch
- **CONTEXT:** J77 bounded original landing passes; original movement-state input and gravity remain separate gates.
- **OBSERVATION:** CharacterGravityParameters has explicit precedence, original motor exposes the public gravity-parameter setter, and GenericCharacterMain gathers InputBank state and drives motor direction.
- **HYPOTHESIS:** These original paths can execute against the accepted inactive-body/landing context without broad character startup.
- **CONSTRAINTS:** Independent cold launches; no state/motor replacements. Original GenericCharacterMain entry, gathering, fixed ticks and exit where applicable. Diagnostic stats/catalog remain explicit; no sprint/skill/full-body or controller acceptance claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing movement batch probe and selector.
- **TEST COMMAND:** `./dev prototype --action gravity-state-prepare`; successful forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **FAILURE EVIDENCE TO CAPTURE:** Current attempt/PID, gravity and position, state-entry/gather exceptions, cleanup and per-launch logs.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve independent outcomes; retain landing rollback and classify first failure without broad initialization patches.
- **DEPENDENCIES:** J77; pinned Starstorm2 BorgMain uses original GenericCharacterMain base ticks and input; original gravity/state methods inspected. No mod hooks/code copied.

| ID / TITLE | TASK / PASS CONDITION | STATUS |
| --- | --- | --- |
| S20 — Gravity precedence | Original default/channeled/neutralizer/environmental precedence assertions. | PASS — J78 |
| S21 — Original falling | Original gravity setter and motor produce expected velocity/discrete displacement over 0.5 s. | PASS — J78 |
| S22 — Gravity jump/landing | Settle on floor, original Jump rises, then original gravity/landing returns to stable floor and resets jump count. | PASS — J78 |
| S23 — Original state input | Original state entry/GatherInputs reads direction/jump edge, consumes emote and rejects claimed press; exit cleans up. | PASS — J78 |
| S24 — Original state movement | Original state fixed ticks consume direction and drive motor/solver through acceleration and neutral stop. | PASS — J78 |

## S25–S28 — Grounded original state and source gravity
- **CONTEXT:** J78 proves gravity and original state movement separately.
- **OBSERVATION:** Exported gravity is -30; prior fixture used -9.81. Grounded state input/collision integration is untested.
- **HYPOTHESIS:** Original state and motor preserve grounding while moving, reversing and contacting a wall under the measured source gravity.
- **TASK:** Four independent cold launches; see individual assertions below.
- **CONSTRAINTS:** No original method changes; restore gravity; diagnostic inactive body/stats/catalog explicit. No full character or physical-controller claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing movement probe, thin preparation selector, physics-setting receipt.
- **TEST COMMAND:** `./dev prototype --action grounded-state-prepare`; completed forced Vulkan build; `./dev prototype --action movement-batch-run`. Transport-only S26 retry: `./dev prototype --action grounded-motion-retry`.
- **PASS CONDITION:** Original method results, grounding and cleanup match each row; current process survives and logs remain explained.
- **FAILURE EVIDENCE TO CAPTURE:** Separate report, current PID, connection/crash logs, gravity/positions and build identity.
- **STATE/JOURNAL UPDATES REQUIRED:** J79, physics receipt and distinct checkpoints; never overwrite rejected runs.
- **DEPENDENCIES:** J78, original exported gravity and pinned Starstorm2 BorgMain base-method observation.

| ID / TITLE | TASK / PASS CONDITION | STATUS |
| --- | --- | --- |
| S25 — Source gravity jump | Original jump rises and lands under measured -30 gravity; original landing resets jump count. | PASS — J79 |
| S26 — Grounded state movement | Original input/state drives expected 4.62 m acceleration and neutral stop while grounded. | PASS — J79 isolated retry; first transport failure retained |
| S27 — Grounded reversal | Opposite input reverses original velocity and moves back while grounded; neutral stop succeeds. | PASS — J79 |
| S28 — Grounded wall | Original state/motor respects measured wall boundary and retains grounding. | PASS — J79 |

### T03-J79 — Reject incomplete batch builds
- **CONTEXT / OBSERVATION:** A premature runner selected the old current-build receipt during an outstanding forced build.
- **HYPOTHESIS / TASK:** Requiring a newer successful terminal receipt and matching APK prevents this observed stale installation.
- **CONSTRAINTS:** Batch-only guard; no general locking or cache redesign. Reject rather than guess.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** movement_batch_run and host acceptance tests.
- **TEST COMMAND / PASS CONDITION:** `./dev test`; absent/stale/mismatched terminal records refuse before Device construction. PASS.
- **FAILURE EVIDENCE TO CAPTURE:** Rejected premature-run directory and assertion output.
- **STATE/JOURNAL UPDATES REQUIRED:** J79; failed records remain separate from successful same-build retries.
- **DEPENDENCIES / ROLLBACK:** Triggered by S25–S28; restore prior harness from the preceding commit if necessary, never accept its rejected launch.

## S29–S32 — Original jump-input dependencies
- **CONTEXT:** J79 original grounded movement passes; direct motor Jump does not prove the original jump-input path.
- **OBSERVATION:** ProcessJump queries an inventory and item definitions, then applies velocity and dispatches the body's jump event.
- **HYPOTHESIS:** A recovered two-item diagnostic catalog, empty original inventory and real server ownership can support a normal first jump press without method replacement.
- **TASK:** Separate item identity, inventory lifecycle, server-event and input-to-jump launches.
- **CONSTRAINTS:** No items granted, unlock/ownership changes, forced requirement bypass or replacement game methods. Inactive body/Run and supplied stats/jump capacity remain explicit. Server-only dispatch does not prove local-client delivery.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing closure preparation, movement probe, thin command selector; ignored item assets and receipts.
- **TEST COMMAND:** `./dev prototype --action jump-input-prepare`; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Per-row assertions, fresh process survival, clean owned cleanup and explained logs.
- **FAILURE EVIDENCE TO CAPTURE:** Preparation dependency chain, exact APK/payload, per-probe exception/logs and independent results.
- **STATE/JOURNAL UPDATES REQUIRED:** J80 preparation failure and subsequent device outcome; individual checkpoints only on accepted results.
- **DEPENDENCIES:** J79; pinned Starstorm2 BorgMain base ProcessJump; DebugToolkit inventory inspection and actual server Spawn; current original inventory/catalog/event implementations.

| ID / TITLE | TASK / PASS CONDITION | STATUS |
| --- | --- | --- |
| S29 — Recovered jump items | Original definitions retain references and receive distinct, resolvable original catalog indices. | PASS — J82 |
| S30 — Empty original inventory | Original allocation, zero-count queries and queued disposal succeed. | PASS — J82 |
| S31 — Server jump event | Real body server authority invokes one original jump callback and completes server dispatch without a client. | PASS — J81 |
| S32 — Original jump press | Original state handles press/release, produces one jump event, rises, lands and resets jump count. | PASS — J82 |

S29/S30/S32 first failed the shared null prior content-array precondition in J81; J82 preserves that failure and accepts the corrected diagnostic setup. S31 retains its independent earlier build. UI closure preparation failure is J80. No formal L5.5 advancement.

## S33–S36 — Recovered body and player-master setup
- **CONTEXT:** J82 original input-to-jump works in a diagnostic body; recovered prefab lifecycle is unproven.
- **OBSERVATION:** Awake and registration are separable from Start/stat/master/network initialization. Body Awake requires BuffCatalog buffers; player-master Awake requires its actual inventory.
- **HYPOTHESIS:** Selective original setup methods can establish recovered component relationships without broadly activating gameplay.
- **TASK:** Four fresh launches: buff allocation, recovered Commando Awake, body registration, recovered PlayerMaster Awake/registration.
- **CONSTRAINTS:** Inactive original roots; no original method changes or cached-reference assignments. Empty diagnostic buff catalog explicit and restored. No full Start, audio teardown, network spawn or body/master-link claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing closure preparation and movement probe; ignored PlayerMaster prefab root isolation.
- **TEST COMMAND:** `./dev prototype --action body-lifecycle-prepare`; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Original caches/events/registries match actual recovered components; each process survives and logs remain explained.
- **FAILURE EVIDENCE TO CAPTURE:** First setup exception, serialized references, exact input/build/payload and per-process diagnostics.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate outcomes and checkpoints; retain failed attempt stages.
- **DEPENDENCIES:** J82; current original lifecycle code; pinned Starstorm2 state-machine relationships and DebugToolkit server boundaries.

| ID / TITLE | TASK / PASS CONDITION | STATUS |
| --- | --- | --- |
| S33 — Buff storage | Original empty catalog and distinct zero-length body buffers, prior arrays restored. | PASS — J84 |
| S34 — Recovered Commando Awake | Original awake event, component caches, model/hurtbox/core references, capsule radius and state-machine identities agree. | PASS — J84 |
| S35 — Recovered body registration | Original OnEnable/OnDisable add and remove exactly this body while the root stays inactive. | PASS — J84 |
| S36 — Recovered player-master Awake | Actual inventory/identity/player-controller caches and master registration work; original bounded cleanup succeeds. | PASS — J84 |

J83 retains the authored compile failures; J84 accepts all four corrected lifecycle probes. These methods run selectively on inactive recovered roots. Body/master network linkage and complete Start/stat behavior remain separate; see character-lifecycle-boundary.md.

## S37–S40 — Recovered network identity prerequisites
- **CONTEXT:** J84 recovered body/master setup passes; actual network spawning and master-ID recording remain unproven.
- **OBSERVATION:** Original NetworkStateMachine.Awake wires sibling machines; NetworkServer.Spawn registers identities; the body's public masterObject setter records a network ID without invoking its inventory-adopting getter.
- **HYPOTHESIS:** These original paths work on the recovered inactive prefabs with actual loopback server ownership and no assigned authority flags.
- **TASK:** Four separate launches for state-machine binding, body spawn, master spawn and master-ID assignment/resolution.
- **CONSTRAINTS:** Original methods and prefab identities retained; roots inactive; no direct cache assignment. Getter/inventory adoption, reciprocal master body cache, full Start/stats and connected-client behavior remain excluded.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing movement probe and thin preparation selector; existing recovered body/master payload.
- **TEST COMMAND:** `./dev prototype --action body-network-prepare`; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Original network bindings, distinct registered IDs, effective authority, actual server lookup and owned unspawn assertions agree with each probe.
- **FAILURE EVIDENCE TO CAPTURE:** Per-process first exception, original spawn warnings, registry/authority failures and native crashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Individual accepted receipts and all failed reports; no full body/master-link milestone from an ID-only result.
- **DEPENDENCIES:** J84; pinned DebugToolkit actual server Spawn and Starstorm2 state-machine wiring; exact original NetworkIdentity/NetworkServer/Util/CharacterBody source.

| ID / TITLE | TASK / PASS CONDITION | STATUS |
| --- | --- | --- |
| S37 — State-machine networking setup | Original Awake assigns correct index, networker and identity to every recovered sibling machine. | PASS — J85 |
| S38 — Recovered body server spawn | Actual server registers recovered body and original authority query succeeds; owned unspawn removes it. | PASS — J85 |
| S39 — Recovered master server spawn | Actual server registers recovered player master and original authority query succeeds; owned unspawn removes it. | PASS — J85 |
| S40 — Body master-ID recording | Two distinct real IDs; original body setter records the master ID and actual server lookup resolves it. Inventory and reciprocal linkage remain unset. | PASS — J85 |

## S41–S42 — Original inventory adoption
- **CONTEXT:** J85 proves actual master IDs, but has not invoked the adopting getter.
- **OBSERVATION:** The original getter resolves the server object and invokes inventory callbacks. Four Lunar ItemDefs are directly dereferenced; absent quest equipment can incorrectly equal empty equipment.
- **HYPOTHESIS:** Five actual recovered definitions allow the original empty-inventory adoption path to complete without suppressing callbacks.
- **TASK:** Separate launches for typed definition/catalog identity and actual recovered body getter/adoption.
- **CONSTRAINTS:** Inactive roots, four-item/one-equipment diagnostic catalogs and empty buff storage. Other absent definitions retain original zero-count behavior. No direct cached relationship assignment, Start/stat or reciprocal-link claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing preparation traversal, movement probe and thin selector; ignored recovered closure.
- **TEST COMMAND:** `./dev prototype --action body-adoption-prepare`; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** S41 original catalog identity/name/index checks; S42 actual master/inventory identities, player-controller detection, one original inventory callback, stable repeated getter and no empty-equipment quest behavior. Owned cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** First content/compile/getter exception, callback count, current-process logs/crashes and immutable per-launch report.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate results/checkpoints; retain failures, no formal L5.5 advancement.
- **DEPENDENCIES:** J85; pinned DebugToolkit NetworkManager actual server spawning; current CharacterBody/ItemCatalog/EquipmentCatalog source.

| ID / TITLE | STATUS |
| --- | --- |
| S41 — Adoption definition identities | PASS — J87 |
| S42 — Original master getter and inventory adoption | PASS — J87 |

## S43–S46 — Original stat prerequisites and calculation
- **CONTEXT:** J87 establishes original empty-inventory adoption on recovered body/master.
- **OBSERVATION:** RecalculateStats returns immediately without Run; otherwise it reads team level, direct equipment definitions, Glass artifact state and health/skill callbacks.
- **HYPOTHESIS:** Selective original team/Run lifecycle and recovered content permit meaningful base-stat calculation without activating full startup.
- **TASK:** Four separate fresh launches: team experience/level initialization, recovered team/hurtbox membership, Run singleton enable/disable, original recovered-body stats.
- **CONSTRAINTS:** Original methods/assemblies unchanged; inactive roots; diagnostic catalogs and empty inventory. No fabricated player/auth state or reciprocal cache assignments; absent optional definitions retain original fallbacks.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing movement probe/preparation selector and narrow recovered Glass/Void equipment/Lunar Potion closure.
- **TEST COMMAND:** `./dev prototype --action body-stats-prepare`; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** S43 initial level one, threshold at 20 experience and reset; S44 original team membership/hurtbox propagation/removal; S45 original Run singleton lifecycle; S46 original completion event and level-one Commando health 110, speed 7, damage 12, jump 15.
- **FAILURE EVIDENCE TO CAPTURE:** Per-process first exception, observed stats/completion count, current-process errors/crashes and lifecycle cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Independent results and checkpoint receipts; preserve failures; no formal L5.5 advancement.
- **DEPENDENCIES:** J87; pinned DebugToolkit CurrentRun actual TeamComponent membership queries; current original TeamManager, TeamComponent, Run, CharacterBody and HealthComponent source.

| ID / TITLE | STATUS |
| --- | --- |
| S43 — Original team experience context | PASS — J88 |
| S44 — Recovered body team membership | PASS — J88 |
| S45 — Minimal original Run singleton lifecycle | PASS — J88 |
| S46 — Recovered original base stats | PASS — J92; earlier failed attempts preserved |

S47 — Recovered default skill setup inherits the S43–S46 contract and depends on J88's observed missing SkillDef. Hypothesis/task: original GenericSkill.Awake assigns the recovered family's default, original body and named state machine, with finite cooldown; original OnDestroy unassigns. No direct skill/cooldown substitution. Test `./dev prototype --action body-stats-retry-prepare`, completed forced Vulkan build, then existing batch runner: independent S47 followed by S46 retry. Preserve first assignment/cleanup exception and separate original-failure evidence. STATUS: PASS — J89.

S48 — Recovered motor capsule setup inherits the S43–S46 contract and depends on J89's observed missing capsule cache. Hypothesis/task: original CharacterMotor.Awake reads actual recovered collider dimensions, making original body effect-bound queries valid; original OnDestroy returns its pooled collection. Test `./dev prototype --action body-stats-motor-prepare`, completed forced Vulkan build, then batch runner: independent S48 and S46 retry. Preserve first exception and both earlier failed stat attempts. No solver movement/full motor Start claim. STATUS: PASS — J90.

## S49–S50 / S46 retry — Required knockback buff context
- **CONTEXT:** J90 stat calculation reaches a handler that directly dereferences two absent BuffDefs.
- **OBSERVATION:** Original BuffCatalog indexes definitions; CharacterBody.Awake allocates catalog-sized buffers. The empty-buff handler queries the motor's original non-authoritative netIsGrounded branch in this inactive fixture.
- **HYPOTHESIS:** Actual indexed definitions and correctly sized storage permit zero-buff handler execution and original stat completion.
- **TASK:** S49 typed definition/catalog/storage identity; S50 original parameterless handler; S46 original stats. Separate fresh launches.
- **CONSTRAINTS:** No method replacement, buff-count injection or suppressed effect handler. Diagnostic two-buff catalog, inactive roots; no authoritative motor/full simulation claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing closure preparation and movement probe; two ignored original BuffDefs and dependencies.
- **TEST COMMAND:** `./dev prototype --action body-stats-buffs-prepare`; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Original indexed identities, catalog-sized zero buffers, unchanged zero counts after handler; S46 original completion event and unchanged expected base stats. Catalog name mappings and prior arrays restore.
- **FAILURE EVIDENCE TO CAPTURE:** Per-process first exception, method phase, callback/results, current-process logs and crash capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate receipts and preserved failures; no formal L5.5 advancement.
- **DEPENDENCIES:** J90; pinned R2API ContentAddition.AddBuffDef pre-catalog content contract; current original BuffCatalog/CharacterBody/CharacterMotor.
- **STATUS:** S49/S50 and S46 retry PASS — J92; J91 import/reference failure preserved.

J91 supporting observation: `body-buffs-reference-prepare` adds one precise reference failure report and a buff-disabled Awake control alongside S49. After the controls pass, `body-buffs-methods-run` executes S50/S46 using the same APK and separate verification evidence. No generic cache redesign or original asset repair was added; the first malformed serialized payload remains rejected.

## S51–S52 — Level-derived stats and recovered motor binding
- **TITLE:** Original team-level stat changes; recovered motor uses computed stats.
- **CONTEXT / OBSERVATION:** J92 completes original level-one stats on recovered inactive Commando; earlier movement fixtures supplied stats.
- **HYPOTHESIS:** Original team membership propagates level changes, and the recovered motor can consume computed acceleration/speed without replacement values.
- **TASK:** Separate fresh launches: S51 raises the original team to level two, observes dirty/completion/level events and restores level one; S52 binds the recovered solver, obtains actual authority and checks acceleration, cap and braking through original PreMove.
- **CONSTRAINTS:** Inactive roots, subset catalogs, no direct stat assignment, no reciprocal cache injection. No solver translation/full Start/controller acceptance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing MovementBatchProbe, thin CLI selector, ignored stage/evidence.
- **TEST COMMAND:** `./dev prototype --action body-level-motor-prepare`; preflight and completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Level two health143/damage14.4 with one level-up event; reset110/12 with no extra level-up. Motor uses original acceleration and reaches speed 7 then stops, with actual recovered solver/authority.
- **FAILURE EVIDENCE TO CAPTURE:** First compilation/runtime exception, dirty flags/events/numeric results, current-process logs/crashes and capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate capability receipts, preserve failure, update state/milestones without formal L5.5 advancement.
- **DEPENDENCIES:** J92; pinned DebugToolkit CurrentRun actual TeamComponent membership observation, current original TeamManager/CharacterBody/CharacterMotor signatures and calculations.
- **STATUS:** S52 PASS — J93; S51 FAILED at original application/effect context. Retry only after measured TeamCatalog legacy loads and application/audio dependencies are addressed.

## S53–S55 — Recovered main-state input and solver movement
- **TITLE:** Existing Commando Body state machine consumes original input and computed stats.
- **CONTEXT / OBSERVATION:** J93 proves recovered motor binding and computed-stat acceleration; state motion previously used an assembled diagnostic body.
- **HYPOTHESIS:** The recovered named Body machine and input component can run their original main state with the established selective lifecycle.
- **TASK:** Three fresh processes: S53 entry/exit; S54 input gathering and claimed jump exclusion; S55 state-driven free displacement and braking.
- **CONSTRAINTS:** Inactive roots, diagnostic catalogs, no direct stat replacement or injected body caches. Free-space solver probe without gravity/collision; no full Start, client or controller claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** MovementBatchProbe, thin CLI selector, ignored stage/evidence.
- **TEST COMMAND:** `./dev prototype --action body-state-prepare`; preflight; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual named machine/input identity and authority; original state input assertions; original solver moves more than 5 and less than 7 units in one simulated second, reaches speed 7, then stops on neutral input; original state exit clears movement.
- **FAILURE EVIDENCE TO CAPTURE:** Per-case first state/cache/animation/input/motor exception, position/velocity, current-process logs and crash/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate receipts only for accepted cases; preserve first failures and formal L5.5 limits.
- **DEPENDENCIES:** J92/J93; pinned Starstorm2 SS2VanillaSurvivor named-machine and network relationships, current recovered mainStateType and original state/lifecycle source.
- **STATUS:** S53/S54/S55 PASS — J94.

## S56–S58 — Recovered motor startup, gravity and landing
- **TITLE:** Original motor Start and state-driven gravity/floor contact.
- **CONTEXT / OBSERVATION:** J94 passes recovered state motion without gravity/collision. Original Start configures gravity/solver and emits onMotorStart; landing calls the original event manager and fall-artifact query.
- **HYPOTHESIS:** Existing recovered components and measured landing context support original gravity and short-drop grounding with computed stats.
- **TASK:** Separate fresh launches: S56 original Start/event/authority; S57 source-gravity free fall; S58 short landing on a plain owned floor.
- **CONSTRAINTS:** No replacement stats, suppressed landing callbacks or fabricated ownership. Inactive roots, explicit stepping, subset catalogs; diagnostic floor without SurfaceDef. No full lifecycle/client/controller or audio claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing movement harness, source-gravity preparation and thin CLI selector; ignored stage/evidence.
- **TEST COMMAND:** `./dev prototype --action body-gravity-prepare`; preflight; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** One original motor-start event and real authority; free-fall velocity/displacement match measured gravity; one landing event, stable grounding, zero vertical speed and reset jump count; global gravity restores.
- **FAILURE EVIDENCE TO CAPTURE:** First lifecycle/solver/landing exception, event counts, grounding and position, current-process logs/crash/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Independent receipts for accepted capabilities; preserve failed attempts; retain formal L5.5 limits.
- **DEPENDENCIES:** J94; J75/J77 landing context; pinned Starstorm2 named-state relationships; current original motor Start/OnLanded and GlobalEventManager landing paths.
- **STATUS:** S56/S57 PASS — J95; S58 PASS — J96 after correcting overlapping initial placement. Failed landing retained. `body-landing-retry-prepare` reruns only that case.

## S59–S61 — Recovered grounded state motion
- **TITLE:** Grounded movement/stop, reversal and wall collision on recovered Commando.
- **CONTEXT / OBSERVATION:** J94 proves free state motion; J96 proves original startup/gravity/landing with correct capsule clearance.
- **HYPOTHESIS:** The same recovered state/motor consumes computed stats while grounded and respects a simple wall.
- **TASK:** Three fresh processes after measured landing: S59 movement and neutral stop; S60 reversal then stop; S61 wall contact then stop.
- **CONSTRAINTS:** Preserve recovered capsule, original stats/state/input/landing handlers and source gravity. Inactive roots, diagnostic floor/layer/subset catalogs; no controller, full lifecycle or visual acceptance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing movement probe and thin CLI selector; ignored build/run evidence.
- **TEST COMMAND:** `./dev prototype --action body-grounded-prepare`; preflight; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Grounded one-second displacement 6.76 and speed 7; neutral stop; reverse more than 10 units over two seconds at final speed -7; wall limits center to approximately 0.99; grounding retained throughout assertions.
- **FAILURE EVIDENCE TO CAPTURE:** First callback/movement assertion, positions, grounding, per-process logs/crash/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate accepted receipts and failures, state/milestones; no formal L5.5 advancement.
- **DEPENDENCIES:** J94/J96; pinned Starstorm2 BorgMain original base FixedUpdate and named-machine relationships; current original motor/solver/state methods.
- **STATUS:** S59/S60/S61 PASS — J97.

## S62 — Visual agreement with recovered grounded motion
- **TITLE:** Fixed-camera before/after captures follow actual original simulation positions.
- **CONTEXT / OBSERVATION:** J97 proves numeric movement; current screenshots show only the lab mesh. J66 already accepts diagnostic material rendering of recovered assets.
- **HYPOTHESIS:** Renderer-only copies at the actual body poses can visually corroborate original movement without activating broad gameplay.
- **TASK:** Reuse grounded movement/stop; capture before and after using three recovered meshes/textures, fixed camera and accepted shader.
- **CONSTRAINTS:** Direct diagnostic display binding only, no skin-loader or animation claim. No gameplay components on copies; simulation stats/caches unchanged. Raw captures remain ignored.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing material preview, movement probe, thin preparation and two-file capture collection.
- **TEST COMMAND:** `./dev prototype --action body-visual-prepare`; preflight; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Existing numeric grounded motion passes; actual stop position 7; both captures belong to this launch, visibly contain recovered character at distinct positions matching fixed-camera projection.
- **FAILURE EVIDENCE TO CAPTURE:** First binding/render/simulation exception, missing capture, current-process logs/crash and pixel evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** Distinguish diagnostic display from activated/animated character; preserve failures and accepted capture receipt.
- **DEPENDENCIES:** J66/J97; pinned Starstorm2 separates body/display skin controllers; accepted authored renderer-only preview. No new native shader/middleware route.
- **STATUS:** S62 PASS — J98. Exact projected displacement and reviewed recovered shape agree; three one-unit channel pixel differences prevent strict pixel equality.

## S63–S65 — Recovered normal jump
- **TITLE:** Recovered jump context, original event dispatch, input-driven jump and landing.
- **CONTEXT / OBSERVATION:** J97 proves grounded recovered motion; J98 finds original empty jumpSound but populated landing sound. J81/J82 used an assembled body with supplied jump stats.
- **HYPOTHESIS:** Actual recovered jump definitions, empty adopted inventory and computed jump power support a normal original jump without native audio changes.
- **TASK:** Fresh launches: S63 context; S64 original server jump event; S65 input press/release, rise and landing.
- **CONSTRAINTS:** No stat assignment, sound clearing, event suppression or fabricated authority. Six-item diagnostic catalog, inactive explicitly stepped roots, plain floor; no bonus-jump effects/audio or controller claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing probe/catalog setup and thin CLI selector; ignored recovered jump-item closure/evidence.
- **TEST COMMAND:** `./dev prototype --action body-jump-prepare`; preflight; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual empty jumpSound and populated landingSound; zero counts for recovered jump items; original jump power 15/count 1; event dispatch once; input jump rises 3–4 units, lands at prior ground height, resets jump count with one jump and two total landing events.
- **FAILURE EVIDENCE TO CAPTURE:** First content/input/native/event exception, computed values, event counts/peak, current-process logs/crash/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Independent accepted receipts; preserve failures and formal L5.5 limits.
- **DEPENDENCIES:** J81/J82/J96–J98; pinned Starstorm2 BorgMain original ProcessJump/FixedUpdate calls; current original GenericCharacterMain, CharacterBody and SfxLocator contract.
- **STATUS:** S63 PASS — J99. S64/S65 FAILED: zero observed local jump events. Measure hasAuthority versus effective authority and establish actual local client/ownership before retry; no flag injection or event suppression.

## S66–S68 — Local ownership distinction and original connection APIs
- **TITLE:** Observe recovered authority; isolate real local connection and client ownership.
- **CONTEXT / OBSERVATION:** J99 sees zero local jump events despite effective movement authority. Original local event delivery uses raw HLAPI ownership.
- **HYPOTHESIS:** Recovered server-only flags differ as predicted, and original local connection/authority messages can establish ownership on a minimal identity.
- **TASK:** Separate fresh launches: S66 recovered runtime flags; S67 original local connection/readiness/object mapping; S68 original authority assignment/message delivery/removal.
- **CONSTRAINTS:** Never change recovered authority flags. The minimal newly authored identity requests client ownership before spawn through its public configuration. No private authority writes or direct event invocation; no recovered client serialization/full player claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing probe and thin CLI; ignored build/run evidence.
- **TEST COMMAND:** `./dev prototype --action local-ownership-prepare`; preflight; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Recovered raw authority false/effective true/no owner/no client; actual local connected/ready endpoints and mapping; original assignment yields authority and matching owner after original message processing, then removal/cleanup succeeds.
- **FAILURE EVIDENCE TO CAPTURE:** Per-phase flags, connect event count, identity/owner assertions, current-process logs/crash/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate receipts and explicit minimal-versus-recovered limits; preserve failures and formal L5.5 status.
- **DEPENDENCIES:** J99; pinned DebugToolkit actual NetworkServer spawning; current original ClientScene/LocalClient/NetworkIdentity and RoR2 authority query.
- **STATUS:** S66 PASS — J100; S67/S68 PASS — J101. J100 teardown-error cases rejected and preserved. `local-ownership-retry-prepare` isolates the two minimal cases with corrected cleanup order.

## S69–S72 — Recovered local client and jump delivery
- **TITLE:** Recovered client initialization, ownership, jump event and input-driven landing.
- **CONTEXT / OBSERVATION:** J101 proves minimal local ownership; recovered callbacks remain untested and J99 lacks raw authority.
- **HYPOTHESIS:** Original local client APIs can initialize recovered objects and deliver ownership-dependent jump events.
- **TASK:** Four fresh launches: S69 client/readiness/mapping; S70 body ownership; S71 original jump event; S72 original input jump and landing.
- **CONSTRAINTS:** Preserve recovered flags and original methods. Read private cached authority only for observation; never assign it. Inactive roots and explicit stepping remain diagnostic, not a full player session.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing movement probe and thin CLI; ignored staged content and evidence.
- **TEST COMMAND:** `./dev prototype --action recovered-client-prepare`; preflight; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual recovered client mapping/readiness; matching owner and original authority callbacks; one jump event; computed impulse, rise, grounding and jump reset. Current-process logs must have no new unexplained errors.
- **FAILURE EVIDENCE TO CAPTURE:** First callback, ownership or jump assertion; process logs, crash, capture and unchanged assembly hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate outcomes and receipts; preserve failed attempts; formal L5.5 remains open.
- **DEPENDENCIES:** J99–J101; pinned DebugToolkit original NetworkServer spawning observation; current original SkillLocator Awake and authority callbacks, ClientScene and NetworkIdentity APIs.
- **STATUS:** S69–S72 acceptance FAILED — J102. All probe assertions pass, but original readiness serialization logs missing GenericCharacterMain catalog index and packet-handler failure. Preserve numeric jump observations without advancing capability receipts. Next isolate original entity-state catalog initialization and serialization.

## S73 — Original state catalog and serialization prerequisite
- **TITLE:** Initialize measured active state identity before recovered client readiness.
- **CONTEXT / OBSERVATION:** J102 lacks GenericCharacterMain index during original NetworkStateMachine serialization; handler failure may have further causes.
- **HYPOTHESIS:** Original catalog initialization resolves the first error and permits a clean state payload.
- **TASK:** Separate catalog/serialized-index/byte-consumption probe, then fresh S69–S72 retries with the same prerequisite.
- **CONSTRAINTS:** One measured active diagnostic type, empty configuration set; original SetElements coroutine assigns indices. Refuse existing catalog and clear owned diagnostic catalog after teardown. No full content-pack or remote peer claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing movement probe, thin CLI, ignored build/evidence.
- **TEST COMMAND:** `./dev prototype --action state-catalog-prepare`; preflight; forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Original type/index/instance round trip, serialized machine identities and full byte consumption; retries additionally require clean readiness/ownership/jump results and current-process log review.
- **FAILURE EVIDENCE TO CAPTURE:** First catalog/serialization exception, subsequent packet error, logs/crash and unchanged DLL hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve independent outcomes and failed attempts; advance no capability on logged errors.
- **DEPENDENCIES:** J102; pinned R2API.ContentManagement ContentAddition.AddEntityState checks registration before catalog initialization; original EntityStateCatalog.SetElements and NetworkStateMachine.OnSerialize.
- **STATUS:** S73 PASS — J103; S69–S72 remain rejected due separate packet-handler failure.

## S74–S75 — Recovered identity serializer attribution
- **TITLE:** Attribute the remaining readiness exception to original body/master serializers.
- **CONTEXT / OBSERVATION:** S73 removes missing state-index errors, but client readiness still logs only the original handler's generic failure.
- **HYPOTHESIS:** A recovered component's uninitialized serialization dependency throws inside the handler.
- **TASK:** Separate fresh body/master launches; invoke each original OnSerialize in original cached NetworkIdentity component order with a shared writer, saving component identity before invocation.
- **CONSTRAINTS:** No replacement serializer, suppressed failure, private gameplay assignment or network-compatibility claim. Preserve original exception as inner exception. This is direct serialization diagnosis, not a client connection.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing probe and CLI; ignored diagnostic evidence.
- **TEST COMMAND:** `./dev prototype --action recovered-serialization-prepare`; preflight; forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** All original serializers finish and produce a nonempty payload independently for each identity; runtime logs contain no new unexplained errors.
- **FAILURE EVIDENCE TO CAPTURE:** Exact component, original exception/stack, logs, crashes, DLL hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Record body/master outcomes independently; isolate first required lifecycle/catalog dependency before retrying readiness.
- **DEPENDENCIES:** S73/J103; pinned DebugToolkit original network spawning context, current original NetworkIdentity.UNetSerializeAllVars sequential dispatch and NetworkConnection.InvokeHandler catch behavior.
- **STATUS:** S74 PASS after parity correction — J105 (`recovered-body-serialization-retry-prepare`). J104 body mismatch preserved. S75 FAILED: original master entitlement tracker serializes uninitialized array; preserve entitlement checks and audit required allocation/catalog before extending.

## S76 — Original master tracker allocation without a network user
- **TITLE:** Original tracker lifecycle prerequisite and recovered client retries.
- **CONTEXT / OBSERVATION:** J104 master serialization throws on null entitlement storage. Original Awake allocates storage from the catalog; entitlement updates require a network user.
- **HYPOTHESIS:** Original Awake repairs storage while preserving the diagnostic's unavailable user/entitlement state.
- **TASK:** Verify original allocation and absent-user update, retry S75, then independently retry S69–S72.
- **CONSTRAINTS:** Keep existing empty diagnostic catalog unchanged and explicitly assert its scope. No ownership/authentication/entitlement success, content authorization, tracker removal or bypass. Empty storage is not entitlement-system acceptance; full catalog/user linkage remains untested.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing harness and CLI; ignored device evidence.
- **TEST COMMAND:** `./dev prototype --action master-tracker-prepare`; preflight; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Original allocation matches catalog, absent-user update preserves storage and no user; original master serialization completes. Client retries separately require clean readiness, actual ownership and original jump assertions.
- **FAILURE EVIDENCE TO CAPTURE:** Original allocation/serializer/callback exception, logs/crash, catalog/user observations and DLL hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate receipts and first failures; no platform or formal L5.5 advancement.
- **DEPENDENCIES:** J103–J105; community prior-art networking guidance and pinned DebugToolkit Code/Util.cs actual user/master queries; current EntitlementCatalog and PlayerCharacterMasterControllerEntitlementTracker original methods. Community entitlement alterations explicitly excluded.
- **STATUS:** S76 and S75 PASS — J106; S69–S72 clean retries PASS independently. Empty diagnostic entitlement catalog and absent network user only; no entitlement-service or formal L5.5 acceptance.

## S77–S78 — Original reciprocal spawn boundary
- **TITLE:** Untouched master loadout and original recovered SpawnBody entry.
- **CONTEXT / OBSERVATION:** J106 accepts local client/jump simulation, but the diagnostic still links body to master in one direction only.
- **HYPOTHESIS:** Default loadout remains serializable; original SpawnBody will either establish the reciprocal relationship or expose its first missing lifecycle dependency.
- **TASK:** Two fresh launches: S77 default loadout round trip; S78 original SpawnBody with the actual inactive recovered prefab, existing original team/stats/Run context and default master loadout.
- **CONSTRAINTS:** No private master body-reference writes, fake spawn, or substituted loadout logic. Inactive prefab intentionally retains the bounded lifecycle; success is not automatic active gameplay. Clean up only newly created body objects belonging to this isolated invocation, including partial failures.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing probe/CLI, ignored device evidence.
- **TEST COMMAND:** `./dev prototype --action reciprocal-spawn-prepare`; preflight; completed forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** S77 original default loadout serializes/deserializes with value equality and full byte consumption. S78 original spawn returns a distinct body with reciprocal master/body link and actual server object mapping, without new unexplained errors.
- **FAILURE EVIDENCE TO CAPTURE:** Original first exception, actual lifecycle phase, logs/crash and DLL hashes; do not infer reciprocal success from a partial clone.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate pass/failure receipts; preserve partial-spawn evidence and identify the next lifecycle dependency.
- **DEPENDENCIES:** J106; pinned DebugToolkit PlayerCommands calls original master.Respawn and queries actual body/master; current CharacterMaster.SpawnBody, CharacterBody.SetLoadoutServer, SkillLocator.ApplyLoadoutServer and Run notification.
- **STATUS:** S77 PASS — J107. S78 FAILED — J107–J109. Observation-only retries (`reciprocal-spawn-observe-prepare`) confirm missing clone Awake caches and no actual server registration; original body initialization lifecycle is the next prerequisite.

## S79 — Automatic recovered root initialization
- **TITLE:** Original automatic Awake/OnEnable and immediate root teardown.
- **CONTEXT / OBSERVATION:** J109 fresh inactive clone lacks required body caches. Recovered root includes network, input/state/physics, equipment and AkBank components; full child activation would mix rendering/animation dependencies.
- **HYPOTHESIS:** Root-only activation initializes original body caches, or reveals a specific automatic callback prerequisite before Start.
- **TASK:** Instantiate a fresh inactive recovered body; keep direct child objects inactive; activate/deactivate synchronously, observe original awake event/caches and registration, then destroy owned clone. Inspect all current-process errors including deferred destruction.
- **CONSTRAINTS:** No component removals, private cache injection, audio success fabrication or forced reciprocal reference. Child isolation is diagnostic; no full-prefab/lifecycle acceptance. No frame yield while active, so Start and ongoing simulation are out of scope.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing probe/CLI, ignored evidence.
- **TEST COMMAND:** `./dev prototype --action body-root-awake-prepare`; preflight; forced Vulkan build; `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** One original Awake event, matching required caches, registration/deregistration and cleanup, with no new unexplained log error or crash.
- **FAILURE EVIDENCE TO CAPTURE:** Callback/phase, logged Unity exceptions, teardown failures, current-process crash and DLL hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Classify first automatic callback failure; preserve original spawn and earlier client/jump receipts; no L5.5 advancement from caches alone.
- **DEPENDENCIES:** J109; pinned Starstorm2 SS2VanillaSurvivor named-state/network relationship and DebugToolkit actual master spawning; original CharacterBody Awake/OnEnable/Start, root script identity inventory and AkBank/ModelLocator callbacks.
- **STATUS:** S79 baseline rejected — J110 motor ordering exception; unchanged probe passes after measured restoration — J111.

## S80 — Restore measured CharacterMotor execution order
- **TITLE:** Preserve original lifecycle ordering metadata for the root activation retry.
- **CONTEXT / OBSERVATION:** J110 automatic body caches pass, but CharacterMotor OnEnable runs before solver binding. Original MonoScript order is 200; exported plugin metadata loses it.
- **HYPOTHESIS:** Restoring the exact input order lets original solver Awake bind the motor before OnEnable.
- **TASK:** Read exact original script metadata, apply only its order through MonoImporter, verify the editor receipt, force build and repeat S79.
- **CONSTRAINTS:** No original DLL changes, invented priority, manual cache assignment or broad order restoration. This small helper serves only the observed initialization failure. Preserve failed baseline and reject drift/ambiguous script identity.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow preparation/helper and pinned editor action, ignored plugin metadata/receipts.
- **TEST COMMAND:** `./dev prototype --action body-root-order-prepare`; editor refresh; `./dev editor --target lab --action character-motor-order`; inspect matching receipt; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** Applied order matches input; root activation/deactivation and teardown pass without the motor exception or another unexplained error.
- **FAILURE EVIDENCE TO CAPTURE:** Original/applicable order, editor receipt, first runtime callback/error/crash, DLL hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate measured metadata fix from full prefab/start/spawn capability; retain earlier failures.
- **DEPENDENCIES:** J110 source/input evidence, pinned community state/network relationships from S79; Unity importer API verified in exact local editor.
- **STATUS:** S80 PASS — J111. Applied original 0→200 order removes motor exception; automatic root lifecycle accepted separately from Start.

## S81 — Original spawn with automatic root initialization
- **TITLE:** Reciprocal master/body spawning before Start.
- **CONTEXT / OBSERVATION:** S79/S80 now pass root initialization after restoring original motor order; J109 inactive spawn lacked those caches.
- **HYPOTHESIS:** Original SpawnBody can complete its reciprocal link when Unity runs required root callbacks automatically.
- **TASK:** With measured order restored, temporarily enable the recovered prefab root and isolate direct children in memory; call original SpawnBody, deactivate returned body synchronously, check reciprocal link and actual server registration; restore prefab activation values and clean owned clone.
- **CONSTRAINTS:** Original spawn/loadout/network code retained. No Start, child rendering/animation, manual controller or populated BodyCatalog claim; default loadout only. No private link/cache assignments. Restore temporary asset activation values even on failure.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing probe and preparation; ignored receipts/evidence.
- **TEST COMMAND:** `./dev prototype --action automatic-spawn-prepare`; editor refresh/order action and receipt; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** Distinct returned body, actual master.GetBody/body.master reciprocal identity, server mapping and clean lifecycle logs.
- **FAILURE EVIDENCE TO CAPTURE:** Original exception/callback, partial clone observations, cleanup, current-process logs/crash and DLL hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate pre-Start reciprocal proof from full lifecycle; preserve earlier failures and next first dependency.
- **DEPENDENCIES:** J109/J111 and pinned DebugToolkit original spawning relationship; measured original motor metadata restoration.
- **STATUS:** S81 PASS — J112. Original reciprocal spawn/server mapping and clean teardown before Start; full lifecycle remains open.

## S82–S83 — Original master/body Start boundary
- **TITLE:** Master body-start callback and CharacterBody.Start on the original spawned body.
- **CONTEXT / OBSERVATION:** J112 establishes reciprocal spawning before Start. Original body Start invokes master.OnBodyStart before validating BodyCatalog identity; master callback directly dereferences GummyCloneIdentifier.
- **HYPOTHESIS:** Supplying that actual indexed definition with zero inventory count permits the master callback, allowing the next body Start failure to be classified independently.
- **TASK:** Add the measured original ItemDef to the bounded catalog before inventory allocation; two fresh launches invoke original master callback or original body Start on the original spawned body, checking completion events/health.
- **CONSTRAINTS:** No body-index injection, fake item counts, suppressed callbacks or full active-loop claim. Preserve original order and root-only spawn, keep children inactive, original DLLs unchanged. Empty/default loadout remains diagnostic.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing closure/catalog probe and thin CLI; ignored original item/evidence.
- **TEST COMMAND:** `./dev prototype --action body-start-boundary-prepare`; editor refresh/order action and matching receipt; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** S82 one master body-start event and original health initialization; S83 additionally original body-start completion. No new unexplained log errors or crashes.
- **FAILURE EVIDENCE TO CAPTURE:** Original first exception, callback counts, catalog context, current-process logs/crash and DLL hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate callback acceptance from full body Start; preserve failures and identify first catalog/content dependency.
- **DEPENDENCIES:** J112; pinned Starstorm2 state/network setup and DebugToolkit actual master/body queries; current original CharacterBody.Start/UpdateMasterLink, CharacterMaster.OnBodyStart/SetUpGummyClone and Inventory nullable-definition contract.
- **STATUS:** S82 PASS — J113; S83 FAILED at original UpdateMasterLink missing BodyCatalog index after master callback. Register original body catalog/content behavior before retry; no index injection.


## S84 — Original body catalog and portrait fallback
- **TITLE:** Register the original Commando prefab without inventing a portrait alias.
- **CONTEXT / OBSERVATION:** S83 stops at the original missing-body-index guard. Exact legitimate catalog decoding finds no `Textures/BodyIcons/CommandoBody` key; the serialized portrait resolves to the real Commando icon.
- **HYPOTHESIS:** Original SetBodyPrefabs assigns the index and retains the serialized portrait after the expected failed asynchronous lookup.
- **TASK:** Initialize real Addressables with the accepted empty-catalog recipe, verify the original legacy missing-key request fails, register the actual inactive prefab through original BodyCatalog, drain callbacks, verify index/name/prefab identity and portrait preservation.
- **CONSTRAINTS:** No direct index assignment, fake successful request, invented alias, body activation or Body.Start acceptance. Use a fresh process and wait for callbacks before owned catalog/bundle teardown.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow partial movement probe, existing preparation/CLI, ignored catalog query and device evidence.
- **TEST COMMAND:** `./dev prototype --action body-catalog-prepare`; editor refresh/order verification; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** Original index and lookup identities agree; missing request fails with InvalidKeyException; serialized portrait survives original callback; no unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** Current process, first request/callback/index error, pending request count, original assembly hashes, actual build and capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Record catalog-only result separately from S83 and formal L5.5; preserve failed preparations and source/query evidence.
- **DEPENDENCIES:** S81/S82; community-prior-art Addressables/catalog section, pinned R2API ContentAddition.AddBody registration timing and CharacterBody contract; exact original BodyCatalog/LegacyResourcesAPI and accepted controller initialization.
- **STATUS:** S84 PASS — J114. Fifteen assertions, 26.09 seconds, expected failed portrait request and original assigned identities/fallback; clean owned teardown, known shader messages only. S83 still awaits a fresh integrated retry.


## S85 / S83 retry — Catalog-aware loadout and original body Start
- **TITLE:** Carry accepted original body registration into fresh lifecycle experiments.
- **CONTEXT / OBSERVATION:** S84 proves original assigned identity and asynchronous portrait fallback; S83 previously fails before skin selection because no body catalog exists.
- **HYPOTHESIS:** The original default loadout can select the indexed Commando skin, and original body Start can advance past the missing-index guard.
- **TASK:** Two sequential fresh launches register the original prefab and drain portrait callbacks, then check catalog-aware default loadout or original reciprocal SpawnBody/Start. Record spawned index, skin, health and completion events.
- **CONSTRAINTS:** Shared prefab/bundle lifetime; no direct index/skin/cache writes, duplicate bundle loading, skipped original Start calls or altered audio fields. Keep children inactive and stop the spawned body before its automatic Start; the selected original body Start call is diagnostic. Destroy owned clones before catalog/bundle release.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing catalog and movement probes, thin CLI preparation, ignored build/device evidence.
- **TEST COMMAND:** `./dev prototype --action body-start-catalog-prepare`; editor refresh and original motor-order verification; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** S85 original default loadout round trip and catalog-aware skin selection agree; S83 actual original body Start returns, emits one completion event, preserves catalog identity and initializes health/skin as expected. Reject unexplained log errors/crashes independently.
- **FAILURE EVIDENCE TO CAPTURE:** First original exception, actual spawned identity and completion fields, current-process logs/crash, cleanup and original assembly hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate accepted loadout and body Start results; retain prior failures and formal L5.5 limits.
- **DEPENDENCIES:** S81/S82/S84; pinned R2API ContentAddition.AddBody registration timing, existing community Addressables callback/status knowledge; current original BodyCatalog, Loadout and CharacterBody.Start/UpdateMasterLink. Actual Commando alive-loop field is empty; retain its original PlaySound behavior.
- **STATUS:** J115 initial integrated cases FAILED; J116 corrected S85/S83 retry PASS with original table initialization: 395/402 assertions. Independent receipts retained; body Start is diagnostically invoked on an inactive original clone, not sustained automatic simulation.


## S86 — Original skill catalog and loadout defaults
- **TITLE:** Initialize original indexed Commando loadout dependencies.
- **CONTEXT / OBSERVATION:** J115 reveals null defaultBodyLoadouts during original skill/skin selection after real body registration.
- **HYPOTHESIS:** Registering actual prefab skill families/definitions and calling original BodyLoadoutManager.Init produces consistent original defaults.
- **TASK:** Assert empty diagnostic catalogs/tables, register actual bounded families and definitions through original setters, verify identities, invoke the complete original initializer, compare every default variant with its family and rerun S85/S83 independently.
- **CONSTRAINTS:** No fabricated skill definitions, private default-table values, profile/unlockable modifications or replacement initializer. Private writes are limited to restoring snapshotted table state after owned clone destruction. Preserve original viewable initialization; diagnostic SurvivorCatalog is empty, so its safe lookup skips survivor-specific viewables.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing catalog probe and thin preparation; ignored original closure/evidence.
- **TEST COMMAND:** `./dev prototype --action body-start-loadout-prepare`; editor refresh/original motor-order verification; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** Original indexed default skill and skin selections agree with actual families; original defaults enable the S85/S83 assertions without unexplained runtime errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** Catalog identities, first initializer/skill/start exception, callback/result counts, teardown and current-process diagnostics.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J115, distinguish loadout acceptance from body Start and full simulation, retain separate receipts only for accepted cases.
- **DEPENDENCIES:** S84 and J115 source audit; pinned DebugToolkit original Loadout/bodyLoadoutManager contract plus R2API registration timing. Exact original SkillCatalog and BodyLoadoutManager initializer are authoritative.
- **STATUS:** S86 PASS — J116. Original catalog/default initialization and S85/S83 assertions pass in separate fresh Android launches. Initial private-helper compile error retained; 45 unchanged DLLs, no new logged errors/crashes.


## S87–S90 — Original spawn state sequence
- **TITLE:** Original state configuration, Idle entry, spawn entry and timed transition.
- **CONTEXT / OBSERVATION:** J116 passes selected body Start; actual Commando Body initial/main types are SpawnTeleporterState/GenericCharacterMain, Weapon/Slide use Idle. Source configuration supplies the spawn delay and sound. Spawn entry applies HiddenInvincibility and model/camera state; the timed path reaches teleport material/content.
- **HYPOTHESIS:** Accepted catalogs/lifecycle plus the actual buff and configuration allow original entry; timed content requirements can be classified independently.
- **TASK:** Four sequential fresh launches: original catalog/configuration identity and static application; original Weapon/Slide Start; original Body Start into SpawnTeleporterState; original managed fixed ticks toward main. Capture actual states, effects and first exceptions.
- **CONSTRAINTS:** Preserve original state types, configuration and OnEnter/OnExit. No direct main-state replacement, fabricated delay, private state-cache writes or fake loaded resource. Children stay inactive; selected callbacks/ticks are diagnostic, not automatic sustained simulation. Original state destruction runs before actual buff/catalog teardown; static configuration values are restored afterward.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small partial probe, existing closure/preparation and thin CLI; ignored original configuration/buff/source receipt and device evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-state-prepare`; editor refresh/original motor order; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** S87 original type/index/instance and source-derived static values agree; S88 both original Idle entries; S89 original spawn entry with hidden buff and model invisibility; S90 original timed transition to GenericCharacterMain. Assess each independently against current-process errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First callback/resource/native exception, current state and buff effects, primary versus teardown errors, PID-scoped logs/crash, original DLL hashes and source/configuration receipt.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate accepted entry/configuration from timed transition and continuing simulation; preserve all failures and formal L5.5 limits.
- **DEPENDENCIES:** S83/S84/S85/S86; pinned Starstorm2 SS2VanillaSurvivor named state-machine/NetworkStateMachine contract, R2API content registration timing and community catalog readiness notes; exact original state/configuration/buff and teleport code govern the experiment.
- **STATUS:** S87/S88 PASS — J118 (404/420 assertions); S89 PASS — J119 (419 assertions) after complete removal contract. S90 initially failed at null original teleport material; J120/S94 passes the bounded timed-transition retry with the measured material provider. J117/J118 failures retained.


## S91 — Complete original spawn-buff exit contract
- **TITLE:** Original hidden-buff removal and timed restoration before spawn-state exit.
- **CONTEXT / OBSERVATION:** J118 entry reaches original removal, whose complete source unconditionally compares MedkitHeal, TonicBuff, SoulCost and KnockUpHitEnemies indices after OnBuffFinalStackLost needs Intangible.
- **HYPOTHESIS:** The actual indexed definitions at count zero allow original hidden-buff removal and timed grace behavior without rewriting the path.
- **TASK:** Complete the measured seven-definition diagnostic buff catalog; independently exercise original add/remove/timed-add/clear methods, then retry original spawn entry/exit in a fresh launch.
- **CONSTRAINTS:** No unrelated buff/item grants, skipped OnExit, direct buff counts or altered material loader. Keep the timed-transition material failure preserved and defer its unchanged retry.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing closure/buff bindings and narrow probe/preparation; ignored actual BuffDefs and evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-state-exit-prepare`; editor refresh/order verification; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** Original hidden-buff cycle completes, unrelated counts remain zero, original timed duration matches spawn exit; original spawn entry and destruction complete without unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First original removal/timed/exit exception, buff/state observations, teardown and current-process logs/crashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Retain J117/J118, distinguish entry/exit from original timed transition, preserve catalog/Idle checkpoints and formal L5.5 limits.
- **DEPENDENCIES:** J118 complete-method audit and reassessment; S87/S88 original state registration/machine knowledge; current legitimate buff assets and code outrank wider community assumptions.
- **STATUS:** S91 PASS — J119 (420 assertions); S89 entry/exit also passes separately (419). Known shader messages only; original definitions at zero unrelated counts, no DLL changes.


## S92–S94 — Original teleport material and overlay boundary
- **TITLE:** Separate typed material loading, original overlay lifecycle and timed spawn progression.
- **CONTEXT / OBSERVATION:** J119 passes original spawn entry/exit; S90 fails because original synchronous legacy teleport material resolves null. Exact catalog maps the legacy GUID to the recovered Material, with desktop dependencies unsuitable for Android. Exported asset GUID differs from the original catalog GUID.
- **HYPOTHESIS:** A bounded Android material bundle served by original providers resolves the original request without changing game code, allowing overlay setup and a discriminating transition retry.
- **TASK:** Three sequential fresh processes: S92 cold original synchronous load plus asynchronous identity/pending-count/release checks; S93 original AddTPOutEffect on the recovered model, diagnostic overlay update and original removal; S94/S90 original timed spawn progression after changing only material availability.
- **CONSTRAINTS:** Keep the prefab bundle with its current owner; use a separate material bundle and measured original GUID/type location. Retain exported shader as an explicit graphics limitation. No fake result, alias, direct main-state shortcut, altered configuration, effect bypass or original DLL patch. Capture the next effect/main-state failure independently. Track and release actual owned handles/material copies after original cleanup.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow partial probe, optional material bundle entry in existing build recipe, existing closure/preparation, thin CLI; ignored assets/receipts/evidence.
- **TEST COMMAND:** `./dev prototype --action teleport-material-prepare`; serial editor refresh/original motor order; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** S92 original sync/async Material identity agrees and pending count drains; S93 original copy/assignment/update/removal and bundle release; S94 original timed transition to main without unexplained errors/crashes. Component proofs do not pass graphics or formal L5.5 acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** Preparation identity mismatch, first provider/native/callback exception, typed material/shader/overlay observations, primary/cleanup errors, PID-scoped logs/crash, original DLL hashes, APK/payload identities.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve rejected attempts; separate material, overlay and transition receipts; keep L5/L5.5 limitations and next measured dependency current.
- **DEPENDENCIES:** S87–S91/J119; pinned R2API AddressReferencedAsset source for synchronous/async handle and release semantics; community-prior-art.md original-provider candidate and accepted controller/audio provider experiments. Exact current LegacyResourcesAPI/TeleportOutController/TemporaryOverlayManager code governs behavior.
- **STATUS:** S92/S93/S94 PASS — J120 (416/428/430 assertions). S90 timed state transition now passes as a bounded method proof; effect/audio remain unavailable and exported shader remains a dummy. Separate receipts retained.


## S95–S97 — Original spawned main-state scheduling and motion
- **TITLE:** Original motor Start, neutral state ticks and scripted main-state movement on the original spawned clone.
- **CONTEXT / OBSERVATION:** J120 passes original timed spawn progression into GenericCharacterMain; earlier movement proofs used an independently prepared body. Original CharacterBody.Start recalculates the actual spawned clone's stats.
- **HYPOTHESIS:** The accepted reciprocal spawn/Start/transition provides the original dependencies for motor Start and original main-state input/motion without replacing simulation.
- **TASK:** Three fresh processes through accepted spawn path: S95 original motor Start/event/parameters and measured server authority; S96 50 neutral original update/fixed callbacks; S97 one-second scripted input/motor/solver displacement and one-second braking.
- **CONSTRAINTS:** Actual clone and original computed stats; no direct state replacement or object translation. Keep body/children inactive, callbacks and solver stepping diagnostic. Movement fixture uses zero global gravity and no collisions/ground solving, restores those settings, and does not establish stage physics. Preserve original spawn delay/configuration/material path. Missing effect/audio and dummy shader remain explicit. Client/physical controls are separate.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing partial state probe and thin batch selector; ignored unchanged closure/build/runtime evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-main-prepare`; serial editor refresh/motor-order verification; preflight; forced Vulkan build; movement-batch-run.
- **PASS CONDITION:** Separate original motor completion/event/authority assertions; stable original neutral state with one-second fixed age and unchanged solver position; original input-driven displacement/speed/braking and unchanged main-state identity. Current-process errors/crashes must match accepted baseline only.
- **FAILURE EVIDENCE TO CAPTURE:** First lifecycle/input/motor/state exception, actual stats/authority/ages/displacement, primary and teardown errors, current-process log/crash, 45 assembly hashes and independent APK/payload identities.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate three component receipts from formal sustained/automatic simulation; preserve failures; next action addresses first new measured dependency.
- **DEPENDENCIES:** J120/S94; pinned Starstorm2 BorgMain original base FixedUpdate/ProcessJump and SS2VanillaSurvivor machine relationships; exact original CharacterBody.Start/CharacterMotor.Start/GenericCharacterMain and accepted solver-step probes govern behavior.
- **STATUS:** S95/S96/S97 PASS — J121 (434/435/437 assertions). Original spawned clone/motor/neutral ticks and scripted motion/braking accepted separately; inactive roots/explicit stepping and zero-gravity/no-collision movement limits retained.

## S98–S100 — Automatic original spawned state and motor scheduling
- **TITLE:** Replace explicit stepping with measured Unity callbacks, then add the shipped automatic motor/solver.
- **CONTEXT / OBSERVATION:** J121 passes original spawned main-state motion with inactive roots and explicit ticks. Its synchronous harness restores dependencies before a real-time probe could finish.
- **HYPOTHESIS:** Retaining the same measured catalogs/master/Run/material across frames allows automatic original FSM callbacks; enabling the original motor subsequently allows original KCC automatic simulation without a custom simulation loop.
- **TASK:** First rerun S94/S97 as regression controls, then S98 automatic Body machine Start/Update/FixedUpdate and 60-second neutral main hold. Only after accepting its current-process evidence run S99 automatic motor Start/registration/neutral hold, then S100 recorded right/neutral input with automatic state/motor/solver movement and braking. Each uses a fresh process and separate report.
- **CONSTRAINTS:** Preserve original DLLs and metadata. Enable only the selected root callbacks; keep body continuing callbacks and all children inactive. Diagnostic body Start remains explicit. No manual FSM ticks, motor Start, solver steps or transform translation in automatic probes. Zero gravity/no collisions isolate scheduling. Original overlay update remains an explicit diagnostic application callback. Original state exit is explicit while dependencies remain available. Formal L5/L5.5 does not advance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing partial probe and dependency scopes; thin CLI actions; per-case bounded capture duration needed to avoid stopping before the 60-second hold; ignored stage/build/device evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-automatic-prepare`; serial editor refresh/motor order; preflight; forced Vulkan build; movement-batch-run. After S98 evidence acceptance, `./dev prototype --action spawn-automatic-motor-run` reuses the build with separate evidence. `./dev prototype --action spawn-automatic-motion-prepare` selects a motion-only retry after a measured observer correction, followed by a completed forced build and movement-batch-run.
- **PASS CONDITION:** Accepted controls remain correct; automatic original timed transition and both state ages progress through at least 60 seconds; separately original motor event/authority/solver registration and actual motion/braking pass. No unexplained current-process error/warning/crash; owned state/solver/provider cleanup and unchanged DLL hashes.
- **FAILURE EVIDENCE TO CAPTURE:** Enabled-component list, phase, ages, frames, input/motion, motor event/registration, first callback/cleanup exception, PID-scoped logs/crash, APK/payload identities and actual survival.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failures; retain separate component receipts only after log review; distinguish automatic scheduling from full body/application lifecycle, gravity/collisions, visuals and controls.
- **DEPENDENCIES:** J120/J121; community-prior-art.md and pinned Starstorm2 BorgMain original base callbacks plus SS2VanillaSurvivor named-machine/network links. Current original FSM and KCC registration/AutoSimulation lifecycle govern the actual probe.
- **STATUS:** S98/S99 PASS — J123 (4039/4022 assertions). S100 PASS — J124 (3967 assertions); observe the overlay after transition as well as during it, then original automatic movement reaches 5.844 units and brakes at 7.14. Each new component probe holds for 60 seconds; rejected attempts remain preserved. Formal L5.5 remains open.

## S101–S104 — Automatic source gravity, landing and grounded movement
- **TITLE:** Add measured source gravity and owned collision geometry to the proven automatic spawned clone.
- **CONTEXT / OBSERVATION:** J124 passes automatic movement only with zero gravity/collisions. Earlier explicit-step J95–J97 pass original gravity, floor/event landing and grounded movement on a different recovered fixture.
- **HYPOTHESIS:** The unchanged original automatic motor/KCC path handles source gravity and the measured original landing contract when their existing dependencies are retained across real frames.
- **TASK:** S101 source-gravity pulse with no collision, comparing actual fixed age, velocity and displacement, then a zero-gravity neutral hold; S102 original short fall/landing/event and 60-second stable grounded hold. Accept those current-process results before separately running S103 grounded right/neutral stopping and S104 wall contact/braking in fresh processes.
- **CONSTRAINTS:** Original DLLs/pins remain unchanged. Diagnostic body Start, inactive children/body continuing callbacks, explicit original overlay update/state exit and server-only authority remain. Use actual source gravity, original fall-artifact/event context and only owned floor/wall. No manual simulation ticks, forced grounding, transform translation, entitlement changes or audio/effect success. End only the free-fall diagnostic pulse with zero gravity/velocity; landing/motion retain source gravity for their entire holds.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow automatic-ground partial probe, existing original landing-context predicate, thin CLI and helper staging; ignored attempt/build/device evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-automatic-gravity-prepare`; serial editor refresh/motor order; preflight; completed forced Vulkan build; movement-batch-run. After gravity/landing acceptance, `./dev prototype --action spawn-automatic-ground-run` reuses the build with independent verification evidence.
- **PASS CONDITION:** Source-gravity velocity/displacement agree with actual fixed age; landing emits one original authority event, grounds without health loss and holds 60 seconds. Separate movement/braking and wall-contact assertions pass with stable grounding. No unexplained current-process error/warning/crash; owned actor/collision/material cleanup and original hashes pass.
- **FAILURE EVIDENCE TO CAPTURE:** Gravity/source fingerprint, fixed interval/velocity/displacement, landing event/velocity/height, original authority, motion/contact/rest, current-process logs/crash, APK/payload/configuration and first exception.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failed attempts; advance separate component receipts only after runtime/log review. Keep gravity-pulse hold distinction and diagnostic lifecycle/clock/effect limitations explicit. Formal L5.5 does not advance.
- **DEPENDENCIES:** J123/J124 automatic FSM/motor/KCC; J95/J96 short recovered floor/event landing and J97 ground/wall contract. Consulted community-prior-art.md, pinned Starstorm2 BorgMain original base fixed callback, isGrounded/velocity/authority boundary. Current original CharacterMotor.OnLanded and GlobalEventManager server/SFX guards govern actual behavior; no community code copied.
- **STATUS:** S101–S104 PASS — J125 (4043/5849/5790/5790 assertions). Four independent 60-second holds; original gravity pulse, landing, grounded stopping and wall contact accepted separately. Body callbacks/clock/controls/visuals and formal L5.5 remain open.

## S105–S106 — Original automatic CharacterBody callbacks
- **TITLE:** Natural CharacterBody Start/Update/FixedUpdate, then grounded movement with those callbacks.
- **CONTEXT / OBSERVATION:** J125 passes automatic FSM/motor/KCC with diagnostic body Start and inactive body continuing callbacks. Spawn-exit timed buff therefore cannot decay; original stationary update remains unmeasured.
- **HYPOTHESIS:** The accepted measured empty-inventory/catalog/buff/Run context supports original body callbacks without gameplay rewrites.
- **TASK:** S105 enable CharacterBody alongside automatic FSM/motor only, skip diagnostic Start on the spawned clone, observe one original master/body Start event, actual stats/registration, natural timed spawn-buff expiry and stationary timer over 60 seconds. After accepting current-process evidence, S106 reuse the APK in a fresh launch with accepted source-gravity floor/grounded right-neutral input.
- **CONSTRAINTS:** No original DLL changes, private lifecycle flag writes, timer stepping, direct movement or fabricated platform/entitlement state. Other root callbacks/children stay inactive. HealthComponent/skill/animation lifetime and actual Run clock remain unproven. Original overlay application update and selected state exit stay explicit. Formal L5.5 remains open.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing automatic spawn/ground probe, skip-only manual Start branch, thin selectors and ignored evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-automatic-body-prepare`; serial editor refresh/motor-order; preflight; forced Vulkan build; movement-batch-run. Only after S105 acceptance, `./dev prototype --action spawn-automatic-body-ground-run`.
- **PASS CONDITION:** Original Start events each once, original stats callback and computed values, actual registration/deregistration, original timed buff disappears naturally, stationary timer exceeds 55 seconds and stable automatic hold exceeds 60 seconds. Grounded movement separately passes existing actual floor/motion/braking contract. No unexplained current-process error/warning/crash.
- **FAILURE EVIDENCE TO CAPTURE:** First callback/native/API exception, events/stats/buff duration/timer/registration, phase, current-process logs/crash, APK/payload/original hashes and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failures, separate body/grounded-body receipts only after review, update next measured dependency and retain formal gate limitations.
- **DEPENDENCIES:** J123–J125; community-prior-art.md character/network map and pinned Starstorm2 BorgMain original base callbacks/grounding/velocity boundaries. Exact CharacterBody.Start/Update/FixedUpdate, UpdateBuffs and UpdateNotMoving govern this experiment; inspected empty-inventory item branches and indexed knockback/removal definitions before enabling.
- **STATUS:** S105/S106 PASS — J126 (4043/5791 assertions). Actual Unity body Start/events/stats/registration, natural buff expiry and stationary update pass; source-gravity grounded motion passes separately. Full hierarchy/Run clock/controls/visuals and formal L5.5 remain open.

## S107–S108 — Original automatic health tick and barrier decay
- **TITLE:** Original HealthComponent fixed callbacks after accepted body Start.
- **CONTEXT / OBSERVATION:** J126 proves original automatic body callbacks with HealthComponent still disabled; a full-health result alone cannot establish its tick.
- **HYPOTHESIS:** Existing original empty-inventory/equipment/buff/Run context supports the unchanged no-damage health fixed path and independently measured barrier decay.
- **TASK:** S107 enable only original HealthComponent after body Start/transition, observe original regeneration accumulator over actual fixed age, then retain automatic body/health through a 60-second neutral hold. After accepting logs, S108 fresh launch adds 20 barrier using original public AddBarrier, compares one-second decay to the source-derived closed form, then verifies natural expiry and stable full health through 60 seconds.
- **CONSTRAINTS:** No manual health callbacks, private accumulator/health writes, damage or forced death. All DLLs unchanged; no item population/crit-heal, shield recharge, effects/audio or combat acceptance. Zero gravity/no collisions; other root/child callbacks inactive. Run clock zero and diagnostic overlay update/state exit remain.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow automatic health observer helper, existing callback selector/staging, thin CLI and ignored evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-automatic-health-prepare`; serial editor refresh/motor-order; preflight; forced Vulkan build; movement-batch-run. Only after S107 acceptance, `./dev prototype --action spawn-automatic-barrier-run`.
- **PASS CONDITION:** Actual original regeneration remainder agrees with rate times actual fixed interval, no health loss, stable 60-second body/health callbacks and owned cleanup. Separate barrier decay agrees within discrete-solver tolerance and naturally reaches zero. No unexplained current-process errors/warnings/crash.
- **FAILURE EVIDENCE TO CAPTURE:** First original fixed/heal/API/native exception, callback list, rate/accumulator/interval, barrier observed/expected, logs/crash/cleanup, APK/payload/original hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failures, separate health/barrier component receipts only after review, retain formal L5/L5.5 limits and next measured dependency.
- **DEPENDENCIES:** J126; community-prior-art.md items/damage boundary and pinned R2API DamageAPI source: hooks concern damage-type serialization/projectile contracts, not a replacement health loop or Android proof. Current exact HealthComponent.ManagedFixedUpdate/ServerFixedUpdate/Heal/AddBarrier and nullable buff/empty-equipment context govern this no-damage probe. No community code copied.
- **STATUS:** S107 PASS — J128 (4046 assertions). J129 rejected S108 and J127 observer failure preserved. S109/S112/S111 recover the measured original barrier asset/completion/lifecycle; S108 retry PASS — J133 (4118 assertions, natural expiry/effect lifecycle and clean 60-second automatic hold). Separate automatic-barrier receipt retained; formal gates remain open.


## S109–S111 — Original barrier prefab loading, initialization and lifecycle
- **TITLE:** Restore only J129's measured missing original BarrierEffect dependency.
- **CONTEXT / OBSERVATION:** S108 math/expiry assertions pass but three missing temporary-effect errors reject acceptance. Current legitimate legacy table and typed catalog resolve the exact prefab; original CharacterBody.Init populates the static slot asynchronously, independently of Awake.
- **HYPOTHESIS:** The recovered serialized closure and existing original providers support that slot and the original effect lifecycle without rewriting gameplay or suppressing failures.
- **TASK:** S109 cold original legacy sync/async GameObject loads, component/reference identity, callback drain and release. Accept before S110 original CharacterBody.Init with only the measured barrier location available; verify its actual completion/slot identity and restore owned static slots on teardown. Accept before S111 diagnostic original effect update on an inactive original spawned body; public AddBarrier controls enter/exit while original effect Unity callbacks follow/scale and destroy. Then retry S108 automatic original barrier decay in a fresh launch.
- **CONSTRAINTS:** Separate measured bundle/provider ownership; original DLLs unchanged. Missing other Init locations return original failure/null, never fabricated readiness. Partial Init is not complete startup. No explicit effect callback ticks, reference substitution, shader parity, platform/entitlement success or direct movement. S111's public barrier change is a controlled lifecycle stimulus, not natural decay proof. Existing Run clock/children/control limitations remain.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing closure recipe/build, one partial barrier observer, thin CLI selectors and ignored typed catalog/build/run records.
- **TEST COMMAND:** `./dev prototype --action barrier-effect-prepare`; serial editor refresh/motor-order; preflight; forced Vulkan build; movement-batch-run. Only after log acceptance run barrier-init-run, then barrier-lifecycle-run, then spawn-automatic-barrier-run separately.
- **PASS CONDITION:** Actual typed identity, one original Init slot completion, automatic Enter/follow/scale/Exit/timed destruction and balanced provider release; separately S108 natural decay/expiry plus observed effect lifecycle across its 60-second hold. No new unexplained PID errors/warnings/crash. Original hashes and owned cleanup pass.
- **FAILURE EVIDENCE TO CAPTURE:** First unresolved catalog/GUID/component/shader/native callback, Init pending count/slot identities, effect linkage/state/destruction, current-process logs/capture, build/payload/input identities and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve every attempt. Separate receipts only after real-device/log review; formal L5/L5.5 remain open.
- **DEPENDENCIES:** J128/J129. Consulted community-prior-art.md and pinned R2API AddressReferencedAsset handle completion/type/release contract; accepted original material/audio provider ownership. Exact current CharacterBody.Init/AssetReferences.Resolve, UpdateSingleTemporaryVisualEffect, TemporaryVisualEffect and VFXAttributes determine the probe; no community/game code copied.
- **STATUS:** S109 PASS — J131 (56 assertions). S110 clean Init acceptance FAILED on 21 missing unrelated direct requests. S112 original completion PASS — J132 (115 assertions). Corrected S111 lifecycle PASS — J133 (487 assertions); S108 automatic decay/effect/60-second hold PASS — J133 (4118 assertions). Separate receipts retained; full Init/formal gates remain open.


## S112 — Original successful barrier completion callback
- **TITLE:** Isolate the successful original Init callback from J131's unrelated missing requests.
- **CONTEXT / OBSERVATION:** S109 passes actual loading/release. S110's original barrier callback succeeds but the broad resolver logs 21 unrelated missing direct requests, rejecting clean Init acceptance.
- **HYPOTHESIS:** The exact original compiler callback can populate its measured slot from the actual successful legacy handle without running the unrelated resolver.
- **TASK:** Semantically attribute the one callback in the unchanged DLL with read-only Mono.Cecil; verify hash/declaring type/signature; invoke its original singleton delegate target against the successful original handle. Verify exactly one loaded slot, zero pending legacy calls, restoration and release. Accept before S111 and S108.
- **CONSTRAINTS:** Explicit diagnostic callback invocation, not full Init or automatic resolver acceptance. No harness writes to populate the slot, synthetic handles/results, error suppression, unrelated content or original assembly modification. Restore only owned slots on cleanup.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing barrier helper/configuration/selector and ignored IL attribution; existing original loaders unchanged.
- **TEST COMMAND:** `./dev prototype --action barrier-completion-prepare`; serial refresh/motor-order, preflight, forced Vulkan build, movement-batch-run. After acceptance, separate barrier-lifecycle-run and spawn-automatic-barrier-run.
- **PASS CONDITION:** Actual handle and original callback fill only the barrier slot; owned references release; no new current-process errors/warnings/crash. S110 remains rejected.
- **FAILURE EVIDENCE TO CAPTURE:** Source hash, semantic callback attribution, runtime type/signature/slot mismatch, pending callbacks, first exception, PID logs and cleanup/build/payload identities.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate completion receipt, explicit invocation limits and retained S110 rejection; then independently assess lifecycle/decay.
- **DEPENDENCIES:** J131/S109; the same pinned R2API AddressReferencedAsset actual successful-handle/completion ownership observation, exact original callback semantic attribution. No game/community implementation copied.
- **STATUS:** S112 PASS — J132 (115 assertions, explicit original completion only). J132 initial S111 observer lookup failure retained. J133 corrected S111 lifecycle/material-copy cleanup and S108 automatic decay pass with no new runtime errors; no full Init claim.


## S113–S116 — Original automatic recovered character direction
- **TITLE:** Add original CharacterDirection Start/Update to the proven original spawned body/health/FSM/motor/KCC callbacks.
- **CONTEXT / OBSERVATION:** J133 passes body/health and barrier callbacks; direction remains disabled. S02/J69 earlier tested original direction with explicit ticks on an artificial identity, not the original spawned body or natural Start.
- **HYPOTHESIS:** Recovered Commando's non-root-motion direction branch needs only its original authority/input/model-base links; original Start can cache the inactive original Animator without executing animation/audio branches.
- **TASK:** S113 automatic original direction Start/cache/authority and 60-second neutral facing. After accepting PID evidence, separately S114 original main-state east input/turning/motion/braking, S115 east-to-west reversal/turning/braking, and S116 public SetAimTimer with neutral motion/backward aim, actual original aim facing and natural timer expiry. Each holds for 60 seconds in a separate cold launch and reports its own failure.
- **CONSTRAINTS:** Preserve original DLLs/serialized turn settings/target links. No manual direction Start/Simulate, yaw/transform writes, replacement turning logic or fabricated authority. Only input and public aim-timer stimulus are authored. Source turn speed 720, driveFromRootRotation=false, shouldDirectPitch=false and direct AimAnimator mode are asserted. Model/child callbacks remain inactive; animation/rendering/root motion/audio/pitch/physical controls/client ownership/Run clock/formal L5.5 remain separate. Diagnostic overlay application update and selected state exit remain.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** One partial observer, existing automatic activation/health component identity checks, thin CLI/staging and ignored evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-automatic-direction-prepare`; serial refresh/motor-order; preflight; forced Vulkan build; movement-batch-run. After each acceptance, separate spawn-automatic-direction-motion-run, spawn-automatic-direction-reverse-run and spawn-automatic-direction-aim-run reuse that build.
- **PASS CONDITION:** Original natural Start caches the actual inactive Animator, real effective authority, original target/model-base identity and unchanged serialized settings. Facing converges to 90/270 degrees under original state input, neutral preserves facing/position; aim-only turns to 180 without translation, original timer expires and later neutral aim input cannot turn. Automatic holds and existing original body/health cleanup pass; no new unexplained current-process errors/warnings/crash.
- **FAILURE EVIDENCE TO CAPTURE:** Enabled-component identities, source settings/links, Start/cache/authority, input/state/yaw/target yaw/position/velocity/aim expiry, first exception, PID logs/crash/capture and APK/payload/hash/owned cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate direction/turn/reverse/aim component receipts only after review; preserve failures and full-character/formal gate limits. Do not repeat full Init or platform startup.
- **DEPENDENCIES:** J126/J128/J133; community-prior-art.md character/network map and pinned Starstorm2 BorgMain original base fixed callback/input/authority observations plus SS2VanillaSurvivor named-machine linkage. Current original CharacterDirection.Start/Update/Simulate, GenericCharacterMain.HandleMovements/GatherInputs, CharacterBody.shouldAim/SetAimTimer/Update and recovered prefab fields determine actual Android assertions. No community/game code copied.
- **STATUS:** PASS S113/S114/S115/S116 — J134/J135. Neutral 7653, motion 5792, reversal 5763, aim 7596 assertions; four separate 60-second holds/85-second process survival, 45 unchanged DLLs and 21 host tests. Stage/build/source/acceptance archived, four separate component receipts. No formal L5/L5.5 acceptance. Next source-audited ModelLocator lifecycle/follow/cleanup boundary.


## S117–S120 — Original automatic detached model following and destruction
- **TITLE:** Enable original ModelLocator beside the accepted automatic direction/body/health/FSM/motor/KCC callbacks.
- **CONTEXT:** J135 accepts neutral/motion/reversal/aim facing while ModelLocator and visual callbacks remain disabled.
- **OBSERVATION:** Current prefab autoUpdateModelTransform=true, dontDetatchFromParent=false, preserveModel=false, normalizeToFloor=false. Original Start caches ModelBase and detaches modelTransform; LateUpdate follows it; OnDestroy destroys the owned detached model.
- **HYPOTHESIS:** Keeping the original model inactive before detachment isolates natural model following and lifetime without activating the unproven visual hierarchy.
- **TASK:** S117 neutral natural Start/detachment/follow/cleanup, then separate S118 east motion, S119 reversal and S120 public aim-timer facing/natural expiry, each with 60-second hold and its own process/report. Observe pose after LateUpdate and assert original detached-model destruction before provider release.
- **CONSTRAINTS:** Original DLLs/serialized settings/links unchanged. No manual ModelLocator Awake/Start/LateUpdate/OnDestroy or model/root transform writes. The harness only keeps this owned model inactive, supplies existing input/aim stimulus and observes. Preserve earlier diagnostics, run-clock/zero-gravity/no-collision limitations and platform boundary. No animation/rendering/audio/death/corpse/physical controls/client-ownership/full Init/formal L5.5 claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** One partial model observer; existing activation/health identity/direction end-of-frame/cleanup observations; thin staging/CLI and ignored evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-automatic-model-prepare`; serial `./dev editor --target lab --action refresh`, `character-motor-order`; `./dev preflight`; `./dev build --target vulkan --force`; `./dev prototype --action movement-batch-run`. After each PID/log/cleanup acceptance, separate spawn-automatic-model-motion-run, spawn-automatic-model-reverse-run, spawn-automatic-model-aim-run reuse this terminal-completed build.
- **PASS CONDITION:** Original Start caches original ModelBase and detaches the exact model while inactive; after LateUpdate model pose matches original parent during accepted direction scenarios/60-second holds. Root destruction leads to original model destruction before provider release; no unexplained current-process errors/warnings/crash. Original body/health/authority/state/motor/solver assertions remain passing.
- **FAILURE EVIDENCE TO CAPTURE:** Source/prefab/DLL hashes; pre-Start parent-cache/isolation; detached-model/parent identity and activity; pose errors/sample count; input/yaw/motion/timer results; actual destruction; first exception/PID logs/crash/capture/build/payload/storage/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate accepted neutral/motion/reversal/aim model receipts; first-failure journal and no advance on failure; state/milestones/risk status with formal gate limits.
- **DEPENDENCIES:** S113–S116/J135, passed package pins/content. Prior art: docs/community-prior-art.md character map; pinned Starstorm2 SS2-Project/Assets/Starstorm2/ContentClasses/SS2VanillaSurvivor.cs AddToModelSkinControllers preserves body/display model identity, AddEntityStateMachine preserves named machine relationships; Modules/EntityStates/Cyborg/BorgMain.cs retains original base fixed callbacks/input/authority. These inform identity/scheduling observation, not Android detachment support. Exact legitimate ModelLocator Awake/Start/UpdateModelTransform/LateUpdate/OnDestroy and recovered Commando fields supply the unsolved Android lifetime assertions. No community/game implementation copied.
- **STATUS:** PASS S117–S120 — J137/J138, 13070/11208/11179/13012 assertions; four separate 60-second holds and 1803 zero-error model pose samples each; actual original destruction/owned cleanup pass, 45 originals unchanged, 21 host tests. J136 failed harness ordering attempt preserved; corrected retry accepted. Separate model receipts; formal L5/L5.5 unchanged. Next audit original GenericSkill/default SkillDef fixed timing before ability execution.


## T03-nova-target — Explicit target with multiple connected devices
- **TITLE:** Make bootstrap health checks select the authorized Nova explicitly.
- **CONTEXT:** User's Thor is connected and in use; Nova is the sole authorized test target.
- **OBSERVATION:** Initial doctor fails on two authorized devices despite valid Nova configuration; lab Device already uses an explicit serial.
- **HYPOTHESIS:** Exact configured-serial selection permits the Nova experiment without touching other devices.
- **TASK:** Select only the configured connected/authorized serial; reject missing/offline/unauthorized/no configuration and never infer a fallback.
- **CONSTRAINTS:** No commands to other devices, no serial publication, no ADB server restart or device configuration changes.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Bootstrap doctor selection, tiny selector and four safety tests; authored evidence summary.
- **TEST COMMAND:** `./dev doctor`; `./dev preflight`; `./dev test`.
- **PASS CONDITION:** Nova is selected with another device present; all rejection cases fail safely; health checks and tests pass.
- **FAILURE EVIDENCE TO CAPTURE:** First prerequisite result and configured-target model/selection receipt under ignored work; never publish identifiers.
- **STATE/JOURNAL UPDATES REQUIRED:** J139, state next action and Conventional Commit/privacy review.
- **DEPENDENCIES:** Immediate S121 original skill callback experiment; explicitly configured authorized Nova.
- **STATUS:** PASS — doctor/preflight and 25 host tests; no gameplay milestone advance.


## S121–S125 — Original automatic Commando skill stock and recharge
- **TITLE:** Prove original GenericSkill/SkillDef automatic timing on the actual spawned Commando.
- **CONTEXT:** J138 proves original body/health/direction/model/FSM/motor/KCC; skill callbacks remain disabled.
- **OBSERVATION:** Current original GenericSkill.FixedUpdate delegates to SkillDef.OnFixedUpdate. Default primary is SteppedSkillDef; other defaults are SkillDef. Original source assets specify one stock and recharge intervals 0/3/4/9 seconds. Original public RemoveAllStocks resets stock/stopwatch without ability execution. OnSkillCooldown's optional item lookup is null-safe and the accepted inventory is empty.
- **HYPOTHESIS:** Original fixed callbacks can preserve full stock and replenish the selected slot at measured source timing without ability-state/native-effect dependencies.
- **TASK:** S121 all-four neutral automatic full-stock hold; after PID/log acceptance S122 primary, S123 secondary, S124 utility, S125 special run separately, enabling only their selected skill beside accepted callbacks. Apply original public stock reset after initialization, record actual fixed elapsed refill and 60-second stable hold/model cleanup.
- **CONSTRAINTS:** Only configured Retroid Pocket Nova; never target the connected Thor. Preserve original DLLs/default definitions/stock settings/authority. No manual GenericSkill Start/FixedUpdate/ManagedFixedUpdate/SkillDef OnFixedUpdate, stopwatch/stock writes, callback interception or ability execution. Run clock, inactive visuals, zero-gravity/no-collision and diagnostic overlay/state teardown limits remain. No ability/projectile/audio/physical-input/formal gate claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** One partial observer, existing activation/identity/hold checks, thin CLI/staging and ignored attempt evidence.
- **TEST COMMAND:** `./dev prototype --action spawn-automatic-skill-prepare`; serial editor refresh/character-motor-order; preflight; forced Vulkan build; movement-batch-run. After each acceptance, separate spawn-automatic-skill-primary-run,secondary-run,utility-run,special-run reuse that terminal-completed APK.
- **PASS CONDITION:** Exact clone slot/body/family/default SkillDef/machine identities and source types/stock/timing settings remain; neutral stocks remain full. Original public reset produces zero, then natural fixed callbacks replenish at source interval within measured observation tolerance and maintain full stock through a 60-second hold. Original model destruction/owned cleanup pass, no new current-process errors/warnings/crash.
- **FAILURE EVIDENCE TO CAPTURE:** Exact source/prefab/asset/community/DLL hashes; callback identities; default definition type/stock/recharge; fixed-time observation and first failure; PID logs/crash/capture/build/payload/live backing/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate accepted skill receipts, reject/preserve first failures, journal/state/backlog/milestone/risk updates and Conventional Commit/public audit.
- **DEPENDENCIES:** J138 and J139 explicit Nova target. Prior art: community-prior-art.md character/EntityStates map; pinned Starstorm2 SS2VanillaSurvivor.AddSkill retains actual family/SkillDef links and AddEntityStateMachine links target machines; BorgMain retains base original fixed/input/authority scheduling. Exact legitimate GenericSkill,SkillDef,SteppedSkillDef,CharacterBody.OnSkillCooldown,Inventory.GetItemCountEffective and four original Commando defaults supply actual Android assertions. No implementation copied.
- **STATUS:** PASS S121–S125 — J141/J142. Five fresh Nova launches: 27509/16684/16693/16684/16684 assertions and separate 60-second holds. Original recharge observed 0.04/3.04/4.02/9.00 fixed seconds against source 0/3/4/9; original cleanup passes, 45 DLLs unchanged, 25 host tests. J140 observation failure preserved and corrected before retry. Five independent skill receipts; no ability or formal gate acceptance. Next S126 physical-control measurement requires the user.


## S126 — Nova physical gamepad observation
- **TITLE:** Measure built-in control events before binding the proven original input boundary.
- **CONTEXT:** Scripted original input/movement/jump and automatic model/skill precursors do not prove physical handheld controls.
- **OBSERVATION:** Read-only Nova getevent capabilities identify one gamepad with two-stick/trigger/D-pad/button labels. Unity lab input settings alone do not establish original ReInput initialization or actual physical mapping.
- **HYPOTHESIS:** A bounded gamepad-only event capture with human-labelled presses can establish the measured physical mapping needed by the next binding experiment.
- **TASK:** Requery configured Nova/model and one current gamepad; prepare the owned Lab screen and 60-second device-side-timeout capture. Ask user for physical control presses when ready, then compare actual events with their labelled sequence before selecting a binding candidate.
- **CONSTRAINTS:** Nova only; never query/operate Thor. Read-only input on the owned Lab screen, no injected events, no storage/settings changes, no touchscreen/keyboard capture, no raw identifiers/logs in Git. Do not claim ReInput, simulation control or formal gate acceptance from raw kernel events.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Thin experiment-specific CLI/helper, ignored capabilities/event/target records and authored summaries.
- **TEST COMMAND:** `./dev prototype --action nova-input-prepare`; when the user is ready, `./dev prototype --action nova-input-capture`.
- **PASS CONDITION:** Current unique gamepad and bounded capture transport validated; actual human-labelled sticks/buttons/triggers/D-pad agree with observed events. Game binding remains separate.
- **FAILURE EVIDENCE TO CAPTURE:** Exact current capabilities, selected event path/target model locally, timeout/transport status, event count/labels and mismatches; no synthetic passing input.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve raw records ignored; document preparation versus physical acceptance, user gate and next contract; Conventional Commit/privacy gate.
- **DEPENDENCIES:** Explicit Nova target J139; existing original input boundary; prior-art community input map plus exact original RewiredIntegrationManager controller/player/map initialization and pinned BorgMain inputBank consumption. These establish the distinction between raw device observation and actual original input integration; getevent is a read-only native observation, not a middleware replacement.
- **STATUS:** PASS raw physical observation — J144. Human 60-second Nova capture records 765 events, expected timeout, no stderr or dropped-sync marker, requested sticks/hats/triggers/shoulders/clicks and face controls. User confirms physical Xbox south/east/west/north order; captured west/north kernel names differ. M1/M2/Start/Select extras identified as a group; individually confirm Start/Select in the next Unity/Rewired exposure probe. Separate raw-observation receipt retained; original ReInput/game binding and formal gates remain unproven. Next inspect actual original integration before implementing any remap.


## S127 — Original Rewired platform contract on Nova
- **TITLE:** Measure the shipped Windows binding before initializing native input on Android.
- **CONTEXT:** S126 accepts raw physical controls; J11/J12 only proved original disputed AOT slots, not a ReInput backend.
- **OBSERVATION:** Exact original InputManager.DetectPlatform hardcodes Windows/Mono/NetStandard20; original ExternalTools.GetAndroidAPILevel returns -1. Original prefab declares Android settings but also references an unresolved optional Switch component. Settings do not establish Android runtime support.
- **HYPOTHESIS:** Actual original platform methods on ARM64 reproduce this mismatch, separating binding compatibility from Nova hardware/Unity input availability.
- **TASK:** In one inactive owned InputManager, invoke only original DetectPlatform and GetExternalTools/GetAndroidAPILevel, observe inherited platform/backend/API fields, actual Android SDK and Unity joystick enumeration; verify ReInput never initializes and owned cleanup completes. Do not instantiate the recovered manager prefab or call game integration.
- **CONSTRAINTS:** Only configured Nova, Thor untouched. Original DLLs unchanged; no field/config writes, fake readiness, platform services, native controller initialization, asset/security-resource extraction or license/authentication bypass. A diagnostic method observation is not middleware/controller acceptance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** One small partial probe, existing batch dispatch/result/staging, thin CLI and ignored evidence.
- **TEST COMMAND:** `./dev prototype --action rewired-platform-prepare`; serial editor refresh; preflight; forced Vulkan build; movement-batch-run; host tests and current-PID diagnostics.
- **PASS CONDITION:** Actual original detector/backend/API values and true Android SDK recorded with attempt/PID, stable process and unchanged originals. A reproduced Windows/Mono/-1 mismatch completes the discriminating experiment but fails Android binding capability. If mismatch reproduces, audit the exact backend-loading contract and choose only a lawful compatible integration or justified bounded adapter.
- **FAILURE EVIDENCE TO CAPTURE:** Source/DLL hashes, selected original method identities, platform/backend/API values, ReInput readiness before/after, Unity joystick availability, AOT/managed/native first failure, build/install/storage/PID/capture/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Record measured positive/negative result separately from game binding, journal first failures, preserve attempt, update state/backlog/milestones/risk and Conventional Commit/privacy gate. No formal controller or simulation pointer advance.
- **DEPENDENCIES:** S126/J144, accepted exact original input. Prior art: community-prior-art.md input/startup map distinguishes ReInput initialization from AOT slots; pinned Starstorm2 BorgMain preserves original inputBank/base state semantics without establishing Android backend support. Exact legitimate RewiredIntegrationManager and InputManager/InputManager_Base/ExternalTools govern this new contract. No implementation copied.
- **STATUS:** COMPLETE discriminator / Android binding NOT ACCEPTED — J145. Five assertions and 25.37-second Nova survival confirm original Windows/Mono/NetStandard20/-1 versus actual Android API33; Unity sees one joystick. ReInput never initializes, cleanup passes, 45 DLLs unchanged; known shader messages only. Ask compatible licensed Unity package availability before candidate selection; if unavailable evaluate a bounded documented Unity-input adapter. No formal input/simulation advance.


## T03-nova-display — Sleep the OLED when device work ends
- **TITLE:** Preserve Nova OLED during host-only work and after runtime operations.
- **CONTEXT:** User explicitly requests display sleep whenever the agent is not actively using Nova.
- **OBSERVATION:** The prepared Lab can remain foreground while host builds run; sleeping a runtime probe also pauses it, so wake/sleep must follow actual device use.
- **HYPOTHESIS:** Guarded system power keys around existing launch/capture and CLI completion provide the requested behavior without changing display/storage settings.
- **TASK:** Enable local Nova-only idle-display option; wake on launch/capture, sleep on command completion including failures, verify actual power states.
- **CONSTRAINTS:** Configured Nova only; refuse other models before emitting a key; never touch Thor, settings/storage or controller input. Keep original experiment failure visible.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing Device and CLI finally, Nova input capture, four meaningful safety cases, example/README/state.
- **TEST COMMAND:** `./dev test`; accepted S127 runtime; standalone `./dev run` and `./dev screenshot`; targeted read-only power-state verification.
- **PASS CONDITION:** Wake only during device use; verified sleep afterward; failure cleanup sleeps while preserving original failure, non-Nova and opt-out safeguards pass.
- **FAILURE EVIDENCE TO CAPTURE:** Power transition/model/CLI first failure locally, no identifiers published.
- **STATE/JOURNAL UPDATES REQUIRED:** J146 and durable user workflow; public staged audit and logical commit.
- **DEPENDENCIES:** User OLED request; immediate S127 runtime must wake after host work.
- **STATUS:** PASS — 29 host tests including four display safety cases, real runtime/run/capture wake and subsequent asleep verification. Current Nova asleep.


## S128 — Compare the official Rewired Unity-2021 trial in isolation
- **ID:** S128
- **TITLE:** Measure API, serialized contracts and installer changes before an Android SDK probe.
- **CONTEXT:** S127 finds a Windows binding on Android. User supplies official Unity-2021 trial and explicitly forbids replacing accepted originals.
- **OBSERVATION:** Actual trial 1.1.65.3 differs from shipped1.1.47; Unity-major compatibility does not prove binary or serialization compatibility.
- **HYPOTHESIS:** An ignored exact-editor reference can expose integration feasibility and concrete incompatibilities without altering accepted lab inputs.
- **TASK:** Inventory archive/assets/runtime/importers, public/protected APIs and original consumers, passive original input data import, controller registry and installer changes; preserve separate hashes and negative findings.
- **CONSTRAINTS:** No trial IL/resource/enforcement inspection or modifications, game installation or accepted lab changes. Trial evaluation only, five-minute restriction retained. Proprietary/raw material ignored; no distribution or formal controller acceptance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Original metadata observer, reference-only Unity observer, narrow comparison CLI, authored notes, ignored reference project and reports.
- **TEST COMMAND:** `./dev doctor`; `./dev prototype --action rewired-trial-inventory`; exact reference MCP observations; original DLL hash verification; `./dev test`.
- **PASS CONDITION:** Exact compared members/types, data identity/schema differences, runtime/installer inventory and first candidate decision recorded; a negative drop-in finding completes the experiment.
- **FAILURE EVIDENCE TO CAPTURE:** Missing signatures/accessibility/scopes/inheritance, dynamic reflection failure, optional missing script, before/after importer/settings hashes and unchanged originals.
- **STATE/JOURNAL UPDATES REQUIRED:** J147/J148, reference report, state/milestones/risk/backlog; staged public/IP review and Conventional Commit. Advance no game controller pointer.
- **DEPENDENCIES:** S127/J145 and user-supplied official archive. Prior art community input map and pinned BorgMain distinguish inputBank semantics from an Android backend; vendor installation/troubleshooting govern axes/order, controller assignment and maps.
- **STATUS:** COMPLETE / NOT DROP-IN — 170/172 signatures match, two missing/inaccessible, ten scope changes and a sealed inherited UI base. Passive input identities retained with documented schema differences. Accepted45 DLLs unchanged. One isolated SDK physical probe is justified; original integration needs a separately bounded compatible candidate.

## S129 — Official trial Android physical-controller observation
- **ID:** S129
- **TITLE:** Observe SDK readiness and copied original input maps on Nova without integrating RoR2.
- **CONTEXT:** S128 completes comparison before constructing a reference-only probe.
- **OBSERVATION:** Trial contains Android assembly/source, installer 512 axes and early manager order; neither import nor ARM64 compilation proves physical input.
- **HYPOTHESIS:** The official trial can initialize Android input and expose Nova physical controls through copied original action/player/map data, independently of original binary compatibility.
- **TASK:** Build one SDK-only scene, verify terminal build and package, preflight/install under existing owned lab safeguards, record90-second human-labelled raw/mapped input, collect current-PID evidence, restore prior APK and sleep Nova.
- **CONSTRAINTS:** Nova only, Thor untouched. No trial timeout bypass, original DLL replacement, platform/ownership services, game simulation or automatic human mapping acceptance. Definition IDs and runtime player IDs remain distinct. Preserve all failures and original APK/payload.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small reference scene builder/runtime observer, thin CLI, specific safety cases, ignored APK/device records; no accepted lab project edits.
- **TEST COMMAND:** Reference-only MCP refresh/guarded build; `./dev preflight`; `./dev prototype --action rewired-trial-run`; `./dev test`; visual/current-PID report review and human sequence confirmation.
- **PASS CONDITION:** ReInput initialized, exact44 action identities and measured original runtime player lookup retained, one joystick, gameplay/UI maps loaded, physically labelled axes/buttons and mapped outputs recorded without unexplained failures; previous APK restored and display asleep. SDK success cannot pass original game integration or L5.5.
- **FAILURE EVIDENCE TO CAPTURE:** Start/terminal build receipts, dispatch/signing/copy/compile/assertion failure, ABI/hash/storage/PID/current report/native/managed logs/screenshot, human ordering uncertainty and rollback/sleep failures.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J148 failed candidates and J149 outcome, scoped observation receipt, reference notes and durable state/backlog/milestones/risk. No original controller capability pointer advance.
- **DEPENDENCIES:** S128; existing Device ownership/adopted-storage/display safeguards. Exact original runtime player creation and game GetPlayer(0), official public controller/player APIs; no copied implementation.
- **STATUS:** COMPLETE / SDK OBSERVATION PASS — J149: 90.001-second Nova Vulkan ARM64 capture, 264 events, initialized SDK/one joystick, 44 retained action identities, runtime player0 lookup, gameplay/UI maps and standard physical controls observed. User confirms delayed L3/R3; reviewed capture/no new errors or matched crashes, prior APK restored and Nova asleep. M1/M2 have no distinct SDK events; original game controller/formal gates stay unaccepted. 35 host tests pass. Next measure authorized matching 1.1.47 integration, otherwise explicitly scoped newer-package compatibility candidate.


## S130 — Temporary Nova input producer and Unity exposure
- **ID:** S130
- **TITLE:** Measure Unity physical axes/buttons and stage an isolated Nova input producer.
- **CONTEXT:** User defers exact Rewired compatibility after S129 and requests direct physical Commando progress.
- **OBSERVATION:** Original InputBankTest is consumed by original GenericCharacterMain; SDK raw numbering does not establish Unity numbering.
- **HYPOTHESIS:** Existing Unity legacy controller APIs can supply the measured original input boundary without replacing middleware or gameplay.
- **TASK:** Append sixteen slot-1 diagnostic axes locally, capture labelled physical controls, validate an attempt-bound mapping, then stage only input-field writes before original fixed ticks.
- **CONSTRAINTS:** Nova only; ignore M1/M2; original45 DLLs and serialization unchanged. No new framework, original motion/state/skill logic replacement, entitlement/service claims or formal gate advance. Neutral on focus loss/disable; reject ambiguous controller or stale mapping. OLED asleep when idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** NovaInputBridge, small batch/helper staging, ignored InputManager backup/mapping/raw observation.
- **TEST COMMAND:** ./dev doctor; ./dev prototype --action nova-bridge-prepare; ./dev preflight; ./dev build --target vulkan --force; ./dev prototype --action nova-bridge-raw-run; ./dev test.
- **PASS CONDITION:** Labelled real Unity axes/buttons and removable, validated mapping recorded; originals unchanged, raw capture has current attempt/PID.
- **FAILURE EVIDENCE TO CAPTURE:** Compiler/build error, controller-slot ambiguity, raw axes/buttons and human order, hashes/current process logs/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Record results and failed attempts; keep scoped evidence separate from gameplay acceptance.
- **DEPENDENCIES:** S129; pinned Starstorm2 BorgMain consumes inputBank while retaining original GenericCharacterMain ProcessJump/FixedUpdate. Community source supplies no Android backend.
- **STATUS:** PASS — J150/J152: full120-second labelled Unity capture, measured sticks/buttons and attempt-bound mapping; original45 DLLs unchanged, stale/invalid mappings rejected. Rewired matching-package work deferred by user instruction.

## S131 — Physical Nova controls original spawned Commando
- **ID:** S131
- **TITLE:** Movement, aim, jump and landing through original automatically scheduled simulation.
- **CONTEXT:** S130 isolates the physical input producer; earlier automatic body/motor/model proofs already pass.
- **OBSERVATION:** Actual CharacterMaster.SpawnBody, authority, computed stats, original GenericCharacterMain and solver callbacks are separately proven.
- **HYPOTHESIS:** Physical input at InputBankTest drives the same original callbacks with the combined measured empty-inventory jump/start item subset.
- **TASK:** Run recovered spawned Commando on a small diagnostic floor; feed physical movement/aim/jump, record original state/motor positions and events, visually review renderer-only recovered model display.
- **CONSTRAINTS:** No scripted input or actor transform/velocity writes in physical phase. Original visual child behaviours stay inactive; bind-pose renderer copy and diagnostic camera/aim stance are explicit. Skills remain disabled pending their execution gate. Original network server semantics retained; L5 and formal L5.5 stay open.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** NovaInputBoundary, renderer-only NovaDiagnosticDisplay, measured combined item subset, existing original callback fixture and thin interactive observation.
- **TEST COMMAND:** ./dev prototype --action nova-bridge-commando-run after S130 mapping; current-PID logs and visual review; unchanged45 DLL hashes.
- **PASS CONDITION:** At least90 seconds real-device callbacks; physical movement over5m plus stop, right-stick aim consumed by original main state, original jump-count transition/rise/landing; exact spawned body/master linkage and authority stable, cleanup and mandatory captures pass.
- **FAILURE EVIDENCE TO CAPTURE:** First prefab/creation/authority/state/physics/input failure, attempt/PID, trajectory/raw input correlation, original jump events and native/managed errors.
- **STATE/JOURNAL UPDATES REQUIRED:** Scoped physical simulation precursor receipt only after reviewed acceptance; archive failures and state/backlog/milestone/risk updates; conventional commit/public audit/push.
- **DEPENDENCIES:** S130, accepted automatic original body/state/motor/model callback proofs; J64 allows independent simulation precursors before platform-blocked L5.
- **STATUS:** PASS — J152:90.03-second physical original Commando simulation,43.53m planar motion/stop, original aim consumption, one jump-count transition/3.6375m rise/landing/reset, user confirmation and reviewed captures.14019 assertions;45 unchanged DLLs,40 host tests, cleanup/OLED sleep pass. Scoped precursor only; formal gates remain open.

## S132 — Original Commando primary factory and activation
- **ID:** S132
- **TITLE:** Original primary state factory, stepping, stock and authority events.
- **CONTEXT:** S131 physical movement/aim/jump passes; skills remain unaccepted.
- **OBSERVATION:** Original primary uses SteppedSkillDef, Weapon Idle and FirePistol2; CharacterBody.OnSkillActivated consumes the empty IncreasePrimaryDamage item contract.
- **HYPOTHESIS:** Actual default primary can instantiate, schedule and consume stock with original step/event semantics before entering the native-consuming state.
- **TASK:** Derive one ignored stage from accepted Nova rollback; recover only two state configurations and the measured item closure; execute original factory/ExecuteIfReady and observe scheduling without entering FirePistol2.
- **CONSTRAINTS:** All45 original DLLs unchanged; no physical input claim, actor writes, audio/effect success, platform services or formal gate advancement. Diagnostic original scheduling is explicit. Keep Nova asleep when idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** PrimaryFireBoundary, thin primary CLI/staging, existing batch routing/catalog subset, ignored state/effect/item closure and receipts.
- **TEST COMMAND:** ./dev doctor; ./dev prototype --action primary-fire-prepare; pinned MCP refresh/console; ./dev preflight; ./dev build --target vulkan --force; ./dev prototype --action primary-fire-run; ./dev test.
- **PASS CONDITION:** Original factory binds actual slot/step0; original ExecuteIfReady queues FirePistol2, consumes1 stock, advances next step1, emits one server and authority event; pending/empty execution rejects; cleanup/current-PID evidence passes.
- **FAILURE EVIDENCE TO CAPTURE:** First state identity/configuration/item/activation exception, current attempt/PID, build/hash/original assembly receipts and screenshots.
- **STATE/JOURNAL UPDATES REQUIRED:** Scoped factory/activation result and provenance; preserve failed attempts, update concise state/backlog/milestones and commit/public audit.
- **DEPENDENCIES:** S131; prior-art map and pinned Starstorm2 a9a4badd Deadeye authority-gated original BulletAttack/effect contract; exact original source overrides assumptions.
- **STATUS:** PASS — J154: original factory/activation/step/stock/events and rejection assertions pass on device; scheduling only, no firing claim.

## S133 — Original primary first native consumer
- **ID:** S133
- **TITLE:** Attribute first unmodified FirePistol2.OnEnter failure.
- **CONTEXT:** S132 separates original skill scheduling from firing; J53 already records unavailable Wwise Android native query.
- **OBSERVATION:** Original FirePistol2 posts Play_commando_R before muzzle effects, recoil and BulletAttack.
- **HYPOTHESIS:** Original firing reaches the missing Wwise native leaf; this specific consumer must be observed before selecting no-audio handling.
- **TASK:** Separate cold launch repeats S132 then original Weapon.ManagedFixedUpdate enters the configured original state; record exact native exception and false firing/audio capability.
- **CONSTRAINTS:** No blanking sound/effects, native stub, DLL modification, suppressed unexpected exception, audio/service success or firing acceptance. Expected negative observation is distinct from capability success.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Same narrow probe; separate ignored device report and result.
- **TEST COMMAND:** Second individually reported primary-fire-run case; current-PID/capture/cleanup and original hashes.
- **PASS CONDITION:** Discriminating observation identifies original pistol native call and survives cleanly; does not pass primary-fire capability.
- **FAILURE EVIDENCE TO CAPTURE:** Earlier first failure, managed/native stack, state and stock/events, process survival/capture/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Append first-failure journal and next justified experiment; no gameplay pointer from native failure.
- **DEPENDENCIES:** S132; pinned R2API.Sound bank/native-result lifetime knowledge, J53/J63 audit; no Android SDK access follows from community code.
- **STATUS:** COMPLETE / NEGATIVE OBSERVATION — J154: original pistol enters and missing native Wwise IsInitialized fails before bullets/effects. No firing/audio capability advances.

S134 standalone silent-cycle proof is superseded by the user-directed integrated spine. Its zero-error host build and source patch are preserved locally; no device capability was claimed.

Current priority: integrated first-failure bring-up, one fresh run per ordinary iteration. J155 diagnostic bring-up and J156 human physical move/aim/jump/X-primary pass. Existing nova-bridge commands select the integrated stage; the first host dispatch NameError is fixed without rebuilding the accepted APK. Scoped physical spine checkpoint retains the90-second control/two-minute process evidence. Next integrate an original bullet-hit/damage path and visible target into this spine; inspect relevant pinned prior art and fix only the first observed device blocker. Audio/effects/menu/full run remain unaccepted; no new experiment action is required.


## S135 — Integrated default skills, damage target and direct app launch
- **ID:** S135
- **TITLE:** Bring original FMJ/roll/barrage and original damage into the physical Commando spine.
- **CONTEXT:** J156 accepts physical motion/aim/jump/primary; remaining skills and target damage are unproven.
- **OBSERVATION:** Exact original skills use existing GenericSkill/Body/Weapon state machines, FMJ projectile and HealthComponent; missing Android Wwise is an independent optional sound leaf.
- **HYPOTHESIS:** Owned sound/effect exclusions and the measured serialized closure preserve original default skill/damage behavior without changing gameplay assemblies.
- **TASK:** Add the three exact state configurations and projectile, original damage target and structured damage/state observation; reuse original inputBank boundary. Make the accepted installed slice start when opened directly and remain active beyond bounded captures.
- **CONSTRAINTS:**45 unchanged DLLs; original simulation/skill/stock/physics/damage code; no actor pose writes, native stubs, platform/authentication claims, original enemy/full-stage/game claim. Keep Nova asleep when idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing nova-bridge/MovementBatch helpers, narrow CombatSpineBoundary/instance sound guard; ignored25-asset closure/configuration/stage/build/payload/captures.
- **TEST COMMAND:** Existing nova-bridge-prepare; pinned MCP refresh/console; preflight; forced Vulkan build; movement-batch-run; local no-selector device capture;40 host tests. Physical all-skill capture after human readiness.
- **PASS CONDITION:** Actual original skill-state entries/projectile and DamageReport health loss, no current-process errors/crashes, original diagnostic fixture cleanup; separate no-selector current-attempt/PID freeplay survives beyond90 seconds with bounded observations. Manual new skill/damage acceptance requires actual physical capture.
- **FAILURE EVIDENCE TO CAPTURE:** First asset/GUID/state/native/observer failure, exact build/source/45 hashes, original damage events, current-PID logs/capture/cleanup. Keep each rejected attempt.
- **STATE/JOURNAL UPDATES REQUIRED:** J157/J158, concise state/milestone status, scoped diagnostic combat/freeplay receipts; public staged audit/manual review and Conventional Commit.
- **DEPENDENCIES:** Accepted J156; pinned Starstorm2 Deadeye/BorgMain and exact original source; authorized current Nova mapping.
- **STATUS:** Diagnostic skills/damage PASS J157; final-build diagnostic and default freeplay stability PASS J158. Physical Y/LB/RB and target aiming PENDING human readiness. No formal L5/L5.5/L6/L7 advance.


## S136 — Original Commando on recovered first-stage terrain
- **ID:** S136
- **TITLE:** Replace the diagnostic floor with recovered whole Titanic Plains static geometry/collision.
- **CONTEXT:** J157/J158 integrate default skills/damage/freeplay but use a synthetic floor.
- **OBSERVATION:** Exact source scene contains2250 objects and104 mesh colliders; static closure is52MB. Original stage lifecycle/director contracts are separate.
- **HYPOTHESIS:** Source transforms/active flags/mesh/LOD/collider data and original survivor spawn markers can support the same original character simulation without stage gameplay callbacks.
- **TASK:** Reuse existing serialized closure staging, build a separate scene bundle, source-world raycast before original SpawnBody, original terrain collision/gravity, owned material previews; verify skills/damage/cleanup and default-launch stability.
- **CONSTRAINTS:**45 original DLLs unchanged; source scene/assets/shaders immutable; preserve static batching/RectTransform hierarchy. No actor pose writes, synthetic floor, stage/director/authentication success or original shader parity. Keep Nova asleep when idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing nova-bridge staging, LabBuild scene bundle recipe, Movement/Nova spawn/display hooks, narrow StageGeometryBoundary and two authored preview shaders. Ignored source/converted geometry/receipts/captures only.
- **TEST COMMAND:** Existing nova-bridge-prepare; MCP refresh/console; preflight; forced Vulkan build; movement-batch-run; local no-selector capture; host safety tests.
- **PASS CONDITION:** Original source spawn marker/ground collision, zero missing render/collider meshes, stable original motion/jump/default skills and target damage, reviewed textured terrain/cutout screenshot, original fixture/scene cleanup; separate default launch survives beyond90 seconds.
- **FAILURE EVIDENCE TO CAPTURE:** Exact compile/runtime/mesh/collider/material first failure, source properties, native/current-PID logs, APK/payload hashes, rejected visual attempt and accepted retry separately.
- **STATE/JOURNAL UPDATES REQUIRED:** J159 and scoped terrain checkpoint, public source/privacy/IP review, Conventional Commit; keep formal gates open.
- **DEPENDENCIES:** S135; pinned Starstorm2 SlateMines, R2API.Director scene timing, R2Wiki HG terrain channels, MSU/EditorKit shader ownership knowledge; measured legitimate input and Nova evidence outrank assumptions.
- **STATUS:** PASS bounded geometry/collision/scripted skills/damage/default stability — J159. Physical all-skill/new-stage acceptance, original stage lifecycle/directors and complete stage remain OPEN. Next integrate original enemy behavior.

## S137 — Original Beetle behavior in the integrated terrain slice
- **ID:** S137
- **TITLE:** Original enemy master/body, navigation, targeting and melee in the accepted Commando spine.
- **CONTEXT:** S136 accepts static Titanic Plains terrain and original Commando skills/damage. Enemy simulation remains unproven.
- **OBSERVATION:** Original BaseAI adopts its master/body through OnBodyStart, selects targets and feeds original input/state consumers. Its navigation requires original SceneInfo and ground/air NodeGraphs. Beetle's optimized rig has no exposed bones; mesh/Avatar/controller identity must be measured rather than inferred from Commando.
- **HYPOTHESIS:** The exact enemy prefab/state/graph closure can execute original targeting and movement alongside the accepted player without gameplay DLL changes or actor motion writes.
- **TASK:** Resolve runtime GUID/subobject identities through the legitimate catalog; stage narrow serialized dependencies; instantiate original navigation context and master, then SpawnBody. Observe actual authority, target, AI/state transitions, trajectory, health and damage. Fix the first integrated device failure before widening scope.
- **CONSTRAINTS:**45 original DLLs unchanged; audio/effects explicitly excluded only on owned clones; no AI rewrite, fabricated service/entitlement state, synthetic enemy motion, director/progression/menu/victory claim. Keep accepted APK/payload receipts recoverable and Nova asleep when idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing nova-bridge staging, subset body/skill/state catalogs, narrow EnemySpineBoundary, integrated input/observation hooks; ignored source closure/catalog queries/builds/device evidence.
- **TEST COMMAND:** Existing nova-bridge-prepare; pinned MCP refresh/console; preflight and forced Vulkan build; movement-batch-run; review current-process errors and capture. Separate direct launch only after bounded bring-up passes; existing host safety tests.
- **PASS CONDITION:** Actual original master/body/authority and nonempty original graphs; original AI acquires player and drives movement; observe melee/damage/death separately without inferring them from targeting. Required captures, no unexpected current-process errors/crashes and owned cleanup pass. Physical combat remains separate.
- **FAILURE EVIDENCE TO CAPTURE:** Runtime/export GUID mismatch, exact first template/spawn/authority/state/navigation/native failure, original asset hashes, separate APK/payload/attempt/PID reports, screenshots and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Journal and concise next action after failures; scoped enemy capability receipt only after real device acceptance, milestone/risk status, staged public audit/manual IP review and Conventional Commit.
- **DEPENDENCIES:** S136; pinned Starstorm2 Runshroom monster/body/model/team collision knowledge, EditorKit runtime GUID/subobject identity distinction, exact original BaseAI/SceneInfo/Beetle state code and authorized Nova.
- **STATUS:** PASS bounded scripted enemy/navigation/melee/damage/death/cleanup — J161,3600 assertions/55.19-second process and45 unchanged DLLs. J160 setup/callback/ownership failures remain preserved. Physical combat, direct-launch enemy/player-death lifetime, rewards/director/stage progression stay OPEN.


## S138 — Original Commando defeat and direct-launch lifetime
- **ID:** S138
- **TITLE:** Handle original fatal NPC damage/death without continuing alive-body lab observations.
- **CONTEXT:** J161 accepts scripted enemy chase/melee/death; direct launch keeps original enemy active.
- **OBSERVATION:** J162 neutral direct launch receives144 damage, then original Commando.DeathState fails on missing PlayerDeathEffect; the lab observer unwinds through a destroyed body.
- **HYPOTHESIS:** The genuine effect/provider closure and original ragdoll callback satisfy death entry, while a death-aware lab hold allows original body lifetime to complete naturally.
- **TASK:** Add only the typed measured PlayerDeathEffect location and narrow serialized closure, original RagdollController Start, death-event/state/effect/ragdoll/body observation, and input-disabled defeat screen. Reprove the accepted scripted combat path, then fresh neutral direct-launch death/stable hold.
- **CONSTRAINTS:**45 original DLLs unchanged; original health/death/ragdoll/timers/authority; no artificial kill, resurrection, actor motion, profile/service/entitlement/victory or original-menu/game-over claim. Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing staging/build recipe, narrow PlayerDefeatBoundary and existing Nova input/main coroutine; ignored typed catalog receipt/closure/separate bundle/current-PID captures.
- **TEST COMMAND:** nova-bridge-prepare; pinned MCP compile/console; preflight; forced Vulkan build; movement-batch-run; local direct-launch defeat capture; existing host safety tests.
- **PASS CONDITION:** Accepted scripted skills/target/enemy path remains clean; original fatal NPC damage produces exactly one original player death event, original death/ragdoll and correctly targeted effect with natural effect/body destruction, followed by30 seconds of stable lab defeat display. No unexpected current-PID error/crash. Process-close cleanup distinct from managed scripted fixture cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** Exact provider/key/serialized/ragdoll/state/lifetime first failure; attempt/APK/payload/45 assembly hashes, original death/damage data and current-process logs/capture; retain accepted enemy rollback.
- **STATE/JOURNAL UPDATES REQUIRED:** J162/J163 and scoped defeat/direct-launch receipt after actual device acceptance; concise state/milestone/risk update, staged public audit/manual IP review and Conventional Commit.
- **DEPENDENCIES:** S137; original-provider prior art and pinned Starstorm2 Mimic observation knowledge; exact original game/type/catalog input and authorized Nova.
- **STATUS:** PASS bounded original defeat/state/ragdoll/effect/lifetime and30-second stable lab hold — J163. Scripted combat/managed cleanup5110 assertions; separate default launch66.59-second process,45 unchanged DLLs/40 host tests. J162 rejections preserved; original game-over/menu/progression and physical new combat remain OPEN.


## S139 — Original escape-pod preview deactivation
- **ID:** S139
- **TITLE:** Restore the original scene preview-disable callback to expose the integrated character.
- **CONTEXT:** S138 accepts original defeat, but gray EscapePodMesh objects obstruct the owned camera.
- **OBSERVATION:** Current device snapshot and source hierarchy identify23 EscapePodMesh children of SurvivorPodSpawnPoint. Exact original MonoScript/fileID resolves to DisableOnStart; its Start deactivates the object. Static extraction stripped that callback.
- **HYPOTHESIS:** Retaining only those measured original components restores natural preview deactivation without changing terrain, spawn markers, simulation, camera or source assets.
- **TASK:** Preserve only the exact input-gated callback references, supply the already accepted original RoR2.dll, wait for natural Start, assert23 inactive pod previews/no other scene scripts; reprove combat/death and review character visibility.
- **CONSTRAINTS:**45 original DLLs unchanged; no manual actor/scene-object motion, scene-root purge, fabricated service state or stage-lifecycle claim. Source flags/geometry untouched. Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing stage geometry transformation/StageGeometryBoundary only; ignored serialized scene/bundle/evidence.
- **TEST COMMAND:** Existing nova-bridge-prepare, pinned MCP compile/console, preflight/forced Vulkan build, movement-batch-run and separate no-selector defeat capture; existing host tests.
- **PASS CONDITION:** All23 original callbacks naturally deactivate only the measured previews, no other scene MonoBehaviours; original source collision/spawn/combat/managed cleanup and natural player defeat remain clean. Reviewed current-process capture shows the original character without those gray pods.
- **FAILURE EVIDENCE TO CAPTURE:** Exact source component identity/count, import/missing script/activation/geometry/rendering first failure, stage/APK/payload hashes, current-PID report/logs/screenshots and rollback.
- **STATE/JOURNAL UPDATES REQUIRED:** J164, concise state/milestone/risk and separate accepted view checkpoint; public audit/manual provenance review, Conventional Commit.
- **DEPENDENCIES:** S138; prior-art map and pinned EditorKit AddressablesPathDictionaryCache component inspection technique; exact current source/MonoScript evidence overrides assumptions. No community implementation copied.
- **STATUS:** PASS bounded original preview deactivation/clear actor view — J164;23 original callbacks,5090 scripted assertions/65.62-second process and separate clean default-launch defeat. Second defeat capture contains observed LB/aim input, so no neutral/confirmed physical-controls claim. Formal gates stay OPEN; next human all-skill/enemy capture after readiness.

## S140 — Original directed enemy spawn and gold/XP delivery
- **ID:** S140
- **TITLE:** Integrate original CombatDirector/CharacterSpawnCard/MasterSummon and DeathRewards into the terrain slice.
- **CONTEXT:** S137–S139 accept original combat/death but direct SpawnBody skips director reward initialization.
- **OBSERVATION:** Original cscBeetle retains cost8/empty loadout/equipment/items; original spawn gives UseAmbientLevel and original CombatDirector assigns reward values. Current fixture removes DeathRewards.
- **HYPOTHESIS:** Genuine reward-prefab providers, measured internal item definitions and original spawn callbacks enable gold/timed XP without gameplay DLL changes.
- **TASK:** Clone the exact spawn card with only its owned prepared master binding, call original director Spawn in Direct placement, retain original DeathRewards and automatic ExperienceManager; record original summon/spawn events, cost, inventory, money/XP timing and cleanup.
- **CONSTRAINTS:**45 original DLLs unchanged; no actor pose writes, manual gold/XP grants, fake services or platform startup. Server-only; automatic waves/placement, connected-client effects, level-up and optional logbook/profile drops deferred. Deterministic RNG configuration uses the measured original Run segment; no full Run lifecycle claim. Nova sleeps while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing staging/build recipe, narrow EnemyRewardBoundary and integrated actor/input/catalog hooks; ignored three original prefab providers, cscBeetle/internal items, receipts/build/device evidence.
- **TEST COMMAND:** nova-bridge-prepare; pinned MCP compilation/console; preflight; forced Vulkan build; movement-batch-run; host safety tests; current-process evidence/capture review.
- **PASS CONDITION:** Original summon/director events, source cost8/body cost8, original computed gold3/XP1 at explicit coefficient1/level1, original player money +3 and team XP +1 after the natural queued delay; preserved original enemy combat/death and owned cleanup, no unexpected current-process error/crash.
- **FAILURE EVIDENCE TO CAPTURE:** First asset/provider/import/spawn/inventory/reward/API/native failure; exact attempt/APK/payload/45 hashes, separate original event/payment/timing data and rejected evidence. Keep all accepted predecessors recoverable.
- **STATE/JOURNAL UPDATES REQUIRED:** J165 and concise state/milestone/risk update; scoped spawn/rewards pointer only after real device acceptance; staged public audit/manual provenance review and Conventional Commit.
- **DEPENDENCIES:** S139; pinned R2API.Director BaseSpawnCardClone/CharacterSpawnCardClone preserves cost/navigation/loadout/items; pinned Starstorm2 Chirr FriendRewards reveals money/effect/XP sequence. Use actual original implementations, not the community reward duplicate.
- **STATUS:** PASS bounded original directed spawn/gold/timed XP — J166,5151 assertions/65.98-second process, correct single gold3/XP1 after1.73seconds,45 originals unchanged/40 tests. J165 rejections preserved. Same-APK direct-launch defeat/stable hold passes under observed aim drift; no physical acceptance or formal gate advance. Other subset items stay locked; automatic waves, level-up, client visuals, logbook/profile/full Run remain OPEN.

## S141 — Original automatic director timing and placement
- **ID:** S141
- **TITLE:** Let the recovered fast director fund, select and place its first NPC automatically.
- **CONTEXT:** S140 accepts original direct placement/rewards; automatic FixedUpdate and navigation placement remain separate.
- **OBSERVATION:** Source Titanic Plains director9121 has one-second credit waves, multiplier0.75, reroll4.5–9, player targeting and original team-limit checks. The base deck contains a Beetle card with weight2/standard distance/no unlockable requirement. Before player registration the lab Run reports zero participants; its original getters count registered PCMCs and linked bodies, independently of connection status.
- **HYPOTHESIS:** Original player registration, master preload identity, disabled Honor artifact, genuine team effect providers and a source-derived one-card deck allow the enabled original director to schedule its first spawn without manually supplying credit, a target or a spawn position.
- **TASK:** Preserve source component settings in an isolated ignored prefab, keep only the measured base card in an owned deck, enable natural callbacks and record credit steps/conservation, target/preload identity and approximate placement. Stop after the first successful spawn, then reuse original combat/reward/cleanup assertions.
- **CONSTRAINTS:**45 original DLLs unchanged; no fabricated connected user/participant, manual credit/spawn call, motion/reward rewrite, ownership claim or full stage/elite/wave acceptance. Source director root is initially inactive; activation is an explicit lab boundary. Original optional/native exclusions remain. Nova sleeps while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing stage/recipe and actor hooks; narrow AutomaticDirectorBoundary; ignored source-derived director/deck, two team effects and Honor definition.
- **TEST COMMAND:** Existing nova-bridge-prepare, pinned MCP compile/console, preflight, forced Vulkan build, movement-batch-run, host tests and current-process capture review.
- **PASS CONDITION:** Natural enabled scheduling produces one original spawn using source timing/credits, correct actual player target/master preload and source navigation range; original combat/rewards and owned cleanup remain stable with no unexplained current-process failure.
- **FAILURE EVIDENCE TO CAPTURE:** First provider/catalog/registration/timing/placement/actor failure; immutable source/attempt/stage/APK/payload hashes, current-PID observations/logs/crashes/screenshots and prior rollback.
- **STATE/JOURNAL UPDATES REQUIRED:** J167+ failed attempts, concise state/milestone/risk exit and separate scheduling checkpoint only after device acceptance; public audit/manual provenance review and Conventional Commit.
- **DEPENDENCIES:** S140; pinned R2API.Director f539511e RunCombatDirectorsFixedUpdate separates Unity scheduling from explicit disabled-director calls, and DirectorAPI records Awake/ClassicStageInfo timing. Use original enabled callbacks; no mod hook/source copied.
- **STATUS:** PASS bounded original first automatic spawn with integrated navigation/combat/rewards — J168. J167 failures retained; source physics flag false, genuine participant/body counts1/1 without connected user, original8-credit/30.519m placement,11476 assertions/60.012-second simulation. No sustained-wave or formal gate advance.

## S142 — Original broad-navigation scheduling
- **ID:** S142
- **TITLE:** Tick the original far-route navigation system without activating platform-dependent application startup.
- **CONTEXT:** S141's Android director placement passes, but the automatically placed enemy cannot reach combat in the current integrated harness.
- **OBSERVATION:** Original AI enters Combat/finds actual player but stands1799 grounded frames. Original broad navigation subscribes StaticUpdate to inactive RoR2Application.onFixedUpdate; Combat requires its next-position output. Near direct-spawn pursuit did not prove this scheduler.
- **HYPOTHESIS:** A narrowly owned automatic lab FixedUpdate invoking only the original navigation StaticUpdate enables original route generation and pursuit.
- **TASK:** Guard the original application remains inactive, verify only the original BaseAI navigation system/no pre-existing agents, tick original navigation, observe real path/time/agent output and reprove director placement, original melee/skills/rewards and teardown.
- **CONSTRAINTS:** No full application event broadcast, original AI/path/motor rewrite, actor motion write, fake combat/user/service state or original DLL change. Preserve rejected attempts and prior rollbacks; Nova sleeps while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing narrow director/actor observations; ignored stage/APK/evidence. No new general scheduler framework.
- **TEST COMMAND:** Existing prepare, pinned MCP compile/console, preflight, forced Vulkan build, movement-batch-run and host tests.
- **PASS CONDITION:** Original broad output gains a real next position/path update, original enemy reaches melee and normal return combat/rewards pass; original agents returned, providers/context clean, no unexpected current-process failure.
- **FAILURE EVIDENCE TO CAPTURE:** First scheduler/AOT/path/physics/AI/skill/reward failure; original navigation output/time/agent counts, actual motion/authority, immutable attempt/stage/APK/payload/hash/current-PID evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** J167+ failed attempts, concise state/milestone/risk and joint scheduling/navigation checkpoint only after integrated Android acceptance; public audit/manual provenance review, Conventional Commit.
- **DEPENDENCIES:** S141 placement evidence; pinned Starstorm2 a9a4badd Fear reads broad-agent output/current/goal position and modules use RoR2Application.onFixedUpdate. Exact original source determines the Android scheduler boundary; no community implementation copied.
- **STATUS:** PASS original far-route scheduling/pursuit — J168;3447 original navigation ticks, real next position/reachability,35.95m pursuit before damage, original melee/return combat/gold/timed XP and zero agents after cleanup. Original application remains inactive; no full Run/stage or physical acceptance.

## S143 — Bounded original multi-actor director/combat
- **ID:** S143
- **TITLE:** Sustain the original fast director through three independently observed NPCs.
- **CONTEXT:** J168 accepts one natural source-timed spawn/navigation/combat/reward; the director stops after that first actor.
- **OBSERVATION:** Existing enemy fields hold a single master/body. Keeping the director enabled without per-actor ownership would overwrite evidence and lose cleanup. The original director subtracts source cost only after the spawn callback returns.
- **HYPOTHESIS:** Retaining the same source timing/deck, stopping after three natural successful spawns, and observing each original actor independently proves concurrent AI/navigation/combat/death and aggregate rewards without introducing new actor content.
- **TASK:** Add only a three-actor probe/registry; preserve the accepted first actor's references and observations. Track distinct network IDs, spawn timing/range, original Start/link/authority, real route/pursuit, damage/death, natural body/master/corpse lifetime and cleanup. Diagnostic input returns fire through original skills; verify source24-credit conservation and original gold9/queued XP3.
- **CONSTRAINTS:**45 original DLLs unchanged. No manual director credit/target/spawn, actor pose or reward writes, fake user/services, full deck/elite/wave/stage acceptance or physical acceptance. Same explicit silent/world-collision/application-inactive lab boundaries; three-spawn limit is diagnostic only. Nova sleeps when idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing director/reward/actor/input observations and thin dev action; narrow DirectorActorBoundary; ignored stage/build/payload/run receipts. No new content closure or general framework.
- **TEST COMMAND:** `./dev prototype --action nova-director-batch-prepare`; pinned MCP compile/console; preflight; forced Vulkan build; movement-batch-run; host safety tests and current-process capture review.
- **PASS CONDITION:** Three unique natural original spawns, at least two coexisting actors/navigation agents, source placement and original grounded pursuit for each, original death/kill/reward totals and natural actor lifetime;60-second original simulation, correct owned cleanup and no unexplained current-PID failure.
- **FAILURE EVIDENCE TO CAPTURE:** First import/AOT/director/actor/path/physics/input/damage/reward/lifetime failure, individual actor records, actual aggregate source timing/cost, immutable sources/settings/APK/payload/45 hashes/current-PID logs/crashes/screenshots. Failed attempts never advance rollback.
- **STATE/JOURNAL UPDATES REQUIRED:** Append failed experiments; concise state/milestone/risk at exit. Advance a scoped multi-actor checkpoint only after device acceptance; staged public audit/manual provenance review and Conventional Commit.
- **DEPENDENCIES:** S141/S142; pinned R2API.Director f539511e distinguishes natural enabled scheduling and catalog timing. Exact original OnSpawnedServer/MasterSummon events identify actors; CombatDirector cost accounting and TeamManager/ExperienceManager own rewards. No community/original implementation copied.
- **STATUS:** PASS bounded three-actor original simulation/combat/rewards — J170.11515 assertions/60.028seconds, distinct original identities/Starts/routes, two concurrent actors/agents, source24 credits, gold9/queued XP3 and owned cleanup. J169 withheld observation retained; paired solver/render data proves continuous physics and exposes an OPEN spawn-frame visual artifact.40 tests/45 unchanged original DLLs; neutral same-APK direct-launch defeat passes separately. Scoped MULTI_ACTOR_COMBAT checkpoint only; formal gates/full deck/waves/elites/physical/menu/progression remain OPEN.

## S144 — Original Run clock and source scene metadata
- **ID:** S144
- **TITLE:** Advance original Run clocks/difficulty before interaction and pickup timing.
- **CONTEXT:** S143 proves original multi-actor combat/rewards. Run remains inactive and its clocks stay zero.
- **OBSERVATION:** GenericPickupController's normal wait uses Run.FixedTimeStamp. Original Run.FixedUpdate advances the synchronized clock, updates its timestamp, derives stopwatch pause from living players/current SceneDef and recalculates difficulty; Update maintains its frame clock. SceneCatalog currently has no entries and geometry uses a lab scene name.
- **HYPOTHESIS:** Original source stage metadata/catalog and the recovered geometry's original name let original Run callbacks advance honest simulation time without platform-dependent Start.
- **TASK:** Preserve unchanged source SceneDef/static references, retain source scene name/GUID on the same geometry subset, initialize original SceneCatalog, schedule original Run Update/FixedUpdate on the owned inactive Run, and record stamps/stopwatch/difficulty. Reprove original three-actor combat/rewards and restore scene/catalog/static timestamp context.
- **CONSTRAINTS:** No manual clock/math, fake stage completion/user/service/entitlement, original DLL change or full Run/menu/stage-lifecycle claim. Original Run.Start remains stopped. Addressed scenes/dioramas/music/progression are not loaded; metadata is not full content acceptance. Preserve previous rollbacks; Nova sleeps while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Thin RunClockBoundary, existing stage preparation/scheduler/observations; ignored original metadata/static closure and source/settings/APK/device receipts. No general scene/content framework.
- **TEST COMMAND:** `./dev prototype --action nova-run-clock-prepare`; pinned MCP compile/console; preflight; forced Vulkan build; movement-batch-run; host tests and current-process/visual review.
- **PASS CONDITION:** Actual original catalog identity, clocks advance over60seconds through original methods, fixed/frame stamps agree with original intervals, stopwatch follows genuine live-player status and original elapsed-time difficulty changes; previous original combat/rewards and owned restoration pass without unexplained current-PID errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First metadata/import/catalog/AOT/clock/pause/difficulty/combat/restoration failure, exact closure/source/scene/APK/payload/45 hashes and current-process evidence. Keep failed attempts and previous APK/payload recoverable.
- **STATE/JOURNAL UPDATES REQUIRED:** Journal failed attempts and bounded exit; concise state/milestone/risk update; scoped clock checkpoint only after Android acceptance; staged public audit/manual provenance review and Conventional Commit.
- **DEPENDENCIES:** S143; pinned R2API.Director f539511e InitStageEnumToSceneDefs waits for original SceneCatalog.Init before using allStageSceneDefs. Exact original Run and GenericPickupController define the clock requirement. R2API.Items catalog timing and DebugToolkit original pickup factories inform the subsequent item boundary; no implementation copied.
- **STATUS:** PASS — J172. Actual original clock68.980s/3449 fixed/2069 frame callbacks, source catalog identity and difficulty1.1012/ambient1.3526;15128 assertions,80.536-second process, clean restoration and previous combat/rewards pass.40 tests/45 unchanged DLLs. Original Run inactive, lab-scheduled callbacks; no full startup/progression acceptance.

## S145 — Original cash-barrel interaction
- **ID:** S145
- **TITLE:** Query/open a recovered cash barrel through original server interaction and receive its natural rewards.
- **CONTEXT:** S144 establishes the original clock/catalog prerequisite; original three-enemy combat already supplies TeamManager/ExperienceManager.
- **OBSERVATION:** Source Barrel1 contains gold8/XP4, original Interactor querying/server dispatch and Opening→Opened state logic; native opening sound is unavailable.
- **HYPOTHESIS:** The preserved source prefab plus accepted original server/catalog/provider context can execute normal barrel interaction/rewards without implementing shop logic.
- **TASK:** Recover only static Barrel1 closure; instantiate an owned source clone, retain original collider/model/Animator/state/interaction code, explicitly omit the clone's audio component, query via original Interactor, dispatch original AttemptInteraction, observe original states/scaled rewards and reject repeated payment.
- **CONSTRAINTS:** No manual reward/clock, fake connection/entitlement, source DLL change or purchased-item/stage progression claim. Diagnostic placement/materials and server invocation are explicit; physical InteractionDriver/client acceptance remains separate. Preserve old rollbacks; Nova sleeps while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow barrel helper, existing preparation/state catalog/config/interface; ignored source closure/APK/payload/attempt/evidence.
- **TEST COMMAND:** `./dev prototype --action nova-barrel-prepare`; pinned MCP refresh/console/prefab inventory; preflight; forced Vulkan build; movement-batch-run; host tests and current-PID/visual review.
- **PASS CONDITION:** Actual original query selects source clone; one original interaction, natural Start scaling and Opening→Opened timing, correct single gold/queued XP award, no duplicate payment, owned cleanup and previous combat/clock assertions pass on Nova without new errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First closure/reference/import/AOT/query/state/native/reward/cleanup failure, source component/scene/build/mapping/payload/45 DLL hashes and current-process logs/captures. Archive each attempt.
- **STATE/JOURNAL UPDATES REQUIRED:** Journal failure/exit; concise state/milestones/risk; scoped barrel checkpoint only on actual Android pass; public staged audit/manual IP/provenance review and Conventional Commit.
- **DEPENDENCIES:** S143/S144; pinned R2API.Director f539511e InteractableSpawnCardClone distinguishes source placement/eligibility/stage caps from manually positioned interaction. Exact current-input Interactor/BarrelInteraction and Barrel states define query/reward/timing. No community/original implementation copied.
- **STATUS:** PASS — J175.15266 assertions/83.337-second Android process; original query/open/states/gold8/XP4 in four scheduled installments, repeated interaction rejected, measured original coin acquisition balanced and owned cleanup pass.45 original DLLs unchanged/40 tests. J173/J174 failures retained. Visible barrel, physical/full original interaction driver, purchases and item acquisition remain separate.

## S146 — Original item acquisition and stat effect
- **ID:** S146
- **TITLE:** Acquire a source-spawned original Syringe pickup through original game code.
- **CONTEXT:** S144 clock, S145 interaction/rewards and original automatic character stats are accepted; item acquisition is unproven.
- **OBSERVATION:** Original GenericPickup uses a half-second Run.FixedTimeStamp wait and original ItemDef.AttemptGrant; original Syringe adds15% attack speed. GetInteractability directly needs a valid internal Junk definition. Current camera excludes the original barrel's Default layer; enabling it reveals unrelated source objects and obscures the actor.
- **HYPOTHESIS:** Catalog original Syringe/Junk before inventory allocation, then original pickup factory/wait/permission/Interactor/grant/natural stats can execute without implementing inventory or bypassing source timing.
- **TASK:** Extend only the measured source closure; register original definitions before original inventory allocation, allow base Syringe in the scoped mask while keeping Junk locked/ungranted, create original pickup definitions/catalog and use original GenericPickupController.CreatePickup with an owned source-prefab override. Prove initial disabled/delayed available states, original grant/count/acquisition order/destruction and automatic attack speed change. Render an owned duplicate of the original animated barrel renderer on the accepted display layer, retaining original collider/query layers, and inspect barrel/source-icon captures. Snapshot clock fields/counters together before stopping callbacks.
- **CONSTRAINTS:** No direct inventory grant/manual clock/fake entitlement/client/profile or normal progression claim. Original PickupDisplay is explicitly omitted on owned clone; source icon is diagnostic, original pickup model remains open. Source DLLs/pins intact; previous rollback/evidence retained; Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small ItemPickupBoundary, existing source staging/catalog/mask/config/camera/clock observation; ignored closure/APK/payload/evidence.
- **TEST COMMAND:** `./dev prototype --action nova-pickup-prepare`; pinned MCP compile/prefab inventory; preflight; forced Vulkan build; movement-batch-run; current-process/visual/45-DLL verification and host tests.
- **PASS CONDITION:** Exact original item/pickup identities and original grant delegate, actual factory/network identity, unchanged half-second delay, original permission/server interaction grants exactly1 Syringe/0 Junk, natural source destruction and automatic attack speed1→1.15, old combat/barrel/clock checks and owned catalog/provider cleanup pass on Nova without unexplained errors/crashes. Review source barrel and icon capture separately; no model/physical acceptance inferred.
- **FAILURE EVIDENCE TO CAPTURE:** First closure/import/catalog/AOT/factory/timing/permission/grant/stats/view/cleanup failure, source/package/APK/payload/mapping/original hashes, current-process logs/captures. Archive each failed attempt.
- **STATE/JOURNAL UPDATES REQUIRED:** Journal failure/exit; state/milestone/risk update; scoped item checkpoint only after device acceptance; public staged audit/manual IP/provenance review and Conventional Commit.
- **DEPENDENCIES:** S144/S145 and original automatic stats. Pinned R2API.Items f539511e registers before ItemCatalog and queries FindItemIndex after initialization. Pinned DebugToolkit d1e2f0aa Items.CCCreatePickup uses UniquePickup and original pickup factory; diagnostic spawn is separate from natural acquisition/progression. Exact current-input GenericPickup/ItemDef/CharacterBody define delay/permission/grant/stat behavior; no implementation copied.
- **STATUS:** PASS — J178. Original factory/nonzero network identity, unchanged0.5-second delay observed0.540s, original grant/count/acquisition order/natural destruction and attack speed1→1.15; old combat/barrel/clock and owned catalog/provider cleanup pass.15350 assertions/86.126-second process,45 unchanged DLLs/40 tests, no new errors/crashes. Reviewed diagnostic barrel and source item icon visible; original pickup model/physical interaction/normal drops/progression remain separate. J176/J177 failures preserved.


## S147 — Original money affordability and payment
- **ID:** S147
- **TITLE:** Execute the original money-cost contract with the actual original player.
- **CONTEXT:** S146 grants an original item; source chest purchase callbacks/drop behavior remain separate.
- **OBSERVATION:** Original Chest1 has cost25/Money, no automatic cost scaling, unlockable or expansion requirement. Actual player has17 gold. Original Money delegates compare/deduct master.money and read original MultiShopCard equipment identity even for empty equipment. Chest PurchaseInteraction separately reads FreeUnlocks/SaleStar item definitions and invokes chest events/drop behavior.
- **HYPOTHESIS:** Original CostTypeCatalog.Init and Money delegates can prove insufficient/exact funds/payment without introducing chest/event/drop dependencies simultaneously.
- **TASK:** Receipt the immutable source chest cost on host and stage only original MultiShopCard definition, register equipment before original inventory allocation, verify host-receipted source cost, call original catalog initialization and affordability/payment methods with actual original player/master/Interactor/inventory. Add8 explicitly diagnostic gold through original GiveMoney; prove17 insufficient,25 sufficient, pay25→0, item/equipment conservation and catalog restoration.
- **CONSTRAINTS:** No custom money implementation, entitlement/unlock/profile or normal progression claim; no chest instance/callback/drop. Diagnostic funding is explicit and is not a reward proof. Original DLLs/pins unchanged; prior evidence recoverable, Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small MoneyCostBoundary, existing source closure/config/original equipment catalog/orchestration; ignored stage/APK/payload/evidence.
- **TEST COMMAND:** `./dev prototype --action nova-money-cost-prepare`; pinned MCP compile/source inventory; preflight; forced Vulkan build; movement-batch-run; current-PID/45-DLL checks and host tests.
- **PASS CONDITION:** Original source cost and original delegate identities,17 unaffordable/25 affordable/25 spent leaving0, Syringe1/equipmentNone conserved, exact catalog restoration and prior combat/barrel/pickup/clock/provider checks pass without unexplained device errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First source/catalog/equipment/AOT/affordability/payment/restoration failure; exact stage/settings/packages/mapping/assembly/APK/payload/terminal/run receipts and logs retained.
- **STATE/JOURNAL UPDATES REQUIRED:** Record first failure or exit, state/milestone/risk update, scoped money-cost checkpoint only after acceptance, staged public/manual review and Conventional Commit.
- **DEPENDENCIES:** S146. Consulted community subsystem map and pinned R2API.Director f539511e InteractableSpawnCardClone placement/eligibility/stage caps; these do not establish normal purchase/progression. Exact legitimate CostTypeCatalog/CostTypeDef/MultiShopCardUtils/Chest1 source determines the narrow API and next purchase dependencies. No implementation copied.
- **STATUS:** PASS — J183. Original Money delegates17 unaffordable/diagnostic8 funding→25 affordable/payment25→0, Syringe1/equipmentNone conservation and cost catalog restoration.15366 assertions/85.374-second process, prior item/barrel/combat/clock/provider checks,45 unchanged DLLs/40 tests, zero new errors/crashes. Only Money tested; source chest cost host-receipted. Original purchase callbacks/drops and other cost types remain open. J179–J182 host failures retained.


## S148 — Active original character local client ownership
- **ID:** S148
- **TITLE:** Connect an actual local client and own the active original Commando.
- **CONTEXT:** Server-only simulation/skills/combat/items/cost pass; InteractionDriver requires raw client authority. Historical J106 client/ownership proofs use explicitly stepped inactive roots.
- **OBSERVATION:** Original prefab retains localPlayerAuthority. Readiness serializes every server identity, requiring valid original state catalogs/caches and entitlement tracker storage. Original tracker allocation with absent user/catalog grants nothing. ClientScene.Shutdown resets shared transport, so it belongs after owned server shutdown.
- **HYPOTHESIS:** Accepted state/catalog/serializer prerequisites permit original active body/master readiness and actual local ownership callbacks without private authority flags or a platform/user session.
- **TASK:** Observe original cached initial serializers before readiness, initialize original tracker storage only where missing and require absent user/unchanged empty catalog. Connect original loopback ClientScene client, set ready/process original messages, verify actual body/master client mappings and assign body authority through original API. Hold60 seconds of original live neutral state/motor/clock/inventory, remove ownership/disconnect, then clear owned client scene after server teardown.
- **CONSTRAINTS:** No NetworkUser/LocalUser/platform authentication/entitlement success, new body/master/cache or authority assignment by fields, fake connection, remote peer or full startup claim. No movement/state/clock rewrite; all source DLLs/pins unchanged. Prior stage/APK/payload rollback retained; Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small ActiveClientBoundary and existing Result/config/CLI/capture/teardown; ignored source/settings/build/device evidence.
- **TEST COMMAND:** `./dev prototype --action nova-active-client-prepare`; pinned MCP compile; preflight; forced Vulkan build; movement-batch-run with180-second bounded deadline/stop on completion; current-PID/45-DLL/visual checks and host tests.
- **PASS CONDITION:** Actual local connection/ready/mappings, original raw/effective/skill authority/owner identity,60-second stable original main state/motor/clock/inventory, original authority removal/client disconnect/client-scene cleanup, old combat/barrel/pickup/cost/provider checks and no unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First serializer/readiness/mapping/authority/tick/native/teardown failure with exact original component, stage/settings/packages/APK/payload/current-process logs and capture. Preserve rejected attempts.
- **STATE/JOURNAL UPDATES REQUIRED:** Record exit/first failure; update state/milestones/risks/backlog; scoped active-client checkpoint only after device acceptance; public staged/manual review and Conventional Commit.
- **DEPENDENCIES:** S147/J106. Consulted community-prior-art networking/authority map and pinned DebugToolkit d1e2f0aa NetworkManager/Util original network/master observation. Inspected exact original HLAPI hash72784046 and CharacterBody/NetworkStateMachine/SkillLocator/tracker source; no implementation copied.
- **STATUS:** PASS — J187. Actual connection/readiness/body-master mapping/raw/effective/skill ownership,60.031-second original hold and original removal/disconnect/server preservation/client-scene cleanup.20803 assertions/146.293-second process, prior integrated checks,45 unchanged DLLs/40 tests, zero new errors/crashes. Explicit original cache/storage initialization; no platform/user/grant or InteractionDriver acceptance. J184–J186 failures retained.


## S149 — Original automatic interaction target selection
- **ID:** S149
- **TITLE:** Select an original barrel through the active character's original InteractionDriver.
- **CONTEXT:** S148 establishes real active-body client ownership; original interaction input/connected reward effects remain separate.
- **OBSERVATION:** Original InteractionDriver needs raw client authority, PauseStopController, original Recycle equipment identity and LowerPricedChests item identity even at zero count. Original Commando Interactor range is3. Recycle has an unlockable and LowerPricedChests requires an expansion; neither is granted.
- **HYPOTHESIS:** An original unpaused owned controller plus measured definitions let the source driver automatically select a source barrel without input, reward dispatch or middleware effects.
- **TASK:** Register original comparison definitions before inventory allocation, keep them ungranted/locked. Reuse owned original barrel setup, initialize the disabled original EquipmentSlot through its original Start/UpdateInventory and create original PauseStopController through its own lifecycle, enable actual source InteractionDriver after real client ownership and feed only diagnostic aim. Observe original automatic cooldown/selection with no target override/manual driver ticks; withdraw only owned colliders, observe natural selection release before destruction, and verify lifecycle/catalog/client/provider cleanup and conserved money/XP/inventory.
- **CONSTRAINTS:** No interaction press/purchase/drop/effect/audio/physical binding, stage progression/user/platform/entitlement grant or full startup claim. No source DLL/package changes, character translation, broad UI reconstruction or general framework. Keep accepted S148 and prior rollbacks; Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small InteractionSelectionBoundary, existing catalog/owned barrel/config/CLI/capture orchestration; ignored exact stage/settings/source/build/device records.
- **TEST COMMAND:** `./dev prototype --action nova-interaction-selection-prepare`; pinned MCP compile; preflight; forced Vulkan build; bounded180-second movement-batch-run; current-PID/45-DLL/visual checks and host tests.
- **PASS CONDITION:** Actual owned active body/client/unpaused original singleton, automatic driver cooldown and source barrel selection with source range3/no override/no input; no opening or funds/XP/item changes. Target/model/material/pause/outline registration restoration plus S14860-second hold/client and prior subsystem cleanup; no unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First source closure/definition/pause/authority/cache/range/selection/teardown failure, exact config/stage/settings/packages/mapping/APK/payload/current-PID evidence; failed attempts never advance pointers.
- **STATE/JOURNAL UPDATES REQUIRED:** First failure/exit, concise state/milestone/risk/backlog; scoped selection checkpoint only after acceptance; staged public/manual review and Conventional Commit.
- **DEPENDENCIES:** S148. Consulted community-prior-art networking/input/content map; pinned R2API.Items f539511e ItemAPI registers before catalog indices, R2API.Director InteractableSpawnCardClone separates source placement/eligibility from diagnostic placement. Exact current InteractionDriver/Interactor/PauseStopController/OutlineHighlight and prefab/definitions determine actual contracts. Connected reward effects remain independent per exact EffectManager source. No implementation copied.
- **STATUS:** PASS — J193. Automatic original source-barrel selection, original cache/ungranted prerequisites, natural release before owned destruction, conserved money/XP/Syringe and full original client/subsystem cleanup;20903 assertions/150.001-second process/60.018-second hold,45 unchanged DLLs/40 tests, no new errors/crashes. J188–J192 retained. Input dispatch/client effects/physical interaction remain separate.


## S150 — Original connected-client coin effect
- **ID:** S150
- **TITLE:** Prove original effect message decoding, coin tiers and natural pool return.
- **CONTEXT:** S149 passes automatic selection; interaction dispatch needs a measured connected-client effect boundary first.
- **OBSERVATION:** Existing original CoinEmitter has no sound event/native audio component, source pooling enabled, duration3 and tiers500/150/25/5/1. Original server message52 forwards to original client factory; source timer returns its original pool.
- **HYPOTHESIS:** Registering the genuine original client handler lets the existing unchanged source prefab execute on Nova without middleware adaptation.
- **TASK:** Retain S149; register one owned original message52 delegate with a narrow observation wrapper, transmit cosmetic diagnostic count683 and independently assert decoded identity/data, original CoinBehavior count and bursts1/1/1/1/3, natural3-second timer/pool return, money/XP/Syringe/budget conservation and exact owned handler/pool/cache/default-value cleanup. J196 requires prior0/declared200/original setter200/restored0; full Console stays unproven.
- **CONSTRAINTS:** No reward/funds grant, interaction input/physical binding/full startup/normal placement/audio or particle-material parity. Only measured skipped original medium-budget default initialization/restoration is allowed through its original setter; no custom thresholds/global pooling/VFX disabling/random changes; no DLL/package/new content/provider replacement. Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** ClientCoinBoundary plus existing lab config/CLI/capture orchestration; ignored source/stage/settings/receipts/device evidence.
- **TEST COMMAND:** nova-client-coin-prepare; pinned MCP compilation; preflight; forced Vulkan build; bounded movement-batch-run; current-PID/visual/45-DLL checks and host tests.
- **PASS CONDITION:** One original message/clone, exact decoded data/catalog/pool/tier bursts, original natural timer-return event with fixed-clock/tick agreement and owned restoration; prior selection/client60-second/subsystem checks, no new errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First message/AOT/VFX/factory/data/tier/timer/pool/cleanup failure, exact stage/settings/build/payload/current-PID records; no failed checkpoint advancement.
- **STATE/JOURNAL UPDATES REQUIRED:** First failure/exit; state/backlog/milestone/risk and scoped coin receipt on device acceptance; public/manual staged review, Conventional Commit.
- **DEPENDENCIES:** S149. Consulted community-prior-art network/content map and pinned R2API.ContentManagement f539511e R2APISerializableContentPack original EffectDef registration. Inspected exact current EffectManager/EffectData/CoinBehavior/DestroyOnTimer/EffectPool/Grumpy pool source and typed source prefab. J196 also inspects pinned R2API.CommandHelper ConsoleReady/default application and exact IntConVar/BaseConVar/Console source; initialization uses the original setter only. No original/community implementation copied.
- **STATUS:** PASS — J199. Original message/factory/count683/tier bursts/seven particles and natural3.020-second fixed/151-tick pool return; funds/XP/item/budget/owned cleanup, original60.010-second client hold and prior checks pass.20925 assertions/153.019-second process,45 unchanged DLLs/40 tests, no new errors/crashes. Explicit original medium-default setter200 restores0, read-only return clock witness; J194–J198 retained. Coin rendering/input/reward linkage/physical/full Console/startup remain unproven.


## S151 — Physical default Commando skill acceptance
- **ID:** S151
- **TITLE:** Capture manual Y/FMJ, LB/roll and RB/barrage through the existing Nova bridge.
- **CONTEXT:** J156 already records user-confirmed physical move/aim/A/X; J157 proves remaining original skills under diagnostic input.
- **OBSERVATION:** Existing mapping measures physical secondary3/utility4/special5; scripted counters do not establish human operation.
- **HYPOTHESIS:** The accepted unchanged original skill path responds to physical controls using the same measured input boundary.
- **TASK:** After explicit operator readiness, use the existing physical command and actual character-ready cue. Capture move/aim/A/X then Y, LB and RB with releases and state completion; review individual original skill/projectile/damage counters, raw button evidence, visual captures and user observations.
- **CONSTRAINTS:** No scripted input, pose/health/grant changes, new mapping/framework or DLL/package replacement. Server-local physical route only; connected physical-client/interaction, audio/graphics parity and formal startup/stage gates remain separate. Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing physical runner and ignored verification/operator records only; authored gate/state/journal summaries.
- **TEST COMMAND:** `./dev prototype --action nova-bridge-commando-run` using completed input-matched forced APK/payload; PID-scoped logs/crash/captures and original hashes.
- **PASS CONDITION:** Actual90-second physical phase, mapped controls and individual original secondary/utility/special entries plus existing move/aim/jump/primary/projectile/damage/actor cleanup checks, reviewed capture and human confirmation agree; no unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First physical input/state/target/authority/death/error, individual counters/raw controls/sequence, exact APK/payload/config/current-PID verification.
- **STATE/JOURNAL UPDATES REQUIRED:** Operator readiness/cue/outcome and first failure/exit; scoped physical receipt only after acceptance, maintain formal gates; public/manual review and Conventional Commit.
- **DEPENDENCIES:** J156/J157 and accepted current runtime. Reuse documented pinned Starstorm2 a9a4badd BorgMain original InputBank/base character-state contract and measured original skill configs/callbacks from J157. No new reconstruction/observer or community implementation.
- **STATUS:** WAITING FOR OPERATOR — readiness question pending; no fresh physical acceptance.


## S152 — Original input-driven barrel and connected reward linkage
- **ID:** S152
- **TITLE:** Press the original interaction input and observe source barrel rewards and client messages.
- **CONTEXT:** S149 establishes automatic original target selection and S150 establishes standalone original coin message/factory/lifetime; their linkage remains unproven.
- **OBSERVATION:** Original InteractionDriver reads InputBankTest.interact and dispatches through the original server Interactor. Original barrel sends effect52 and XP55. Genuine XP handler decodes before the original optional exp/money-effects setting; XP-orb arrival otherwise calls unavailable native sound. Uninitialized original BoolConVar records prior0/declared1, separately from full Console initialization.
- **HYPOTHESIS:** The accepted original local authority/selection/effect path can process one diagnostic interaction press, pay exact source-scaled gold/timed XP and decode both real messages without native XP cosmetics.
- **TASK:** Keep accepted S149/S150 results separate; create another owned original source barrel, let the automatic driver select it, push only original public interact press/release and observe original Opening/Opened, one interaction/gold event, exact wallet/XP deltas and genuine messages52/55. Observe source-count coin tiers and natural pool return, repeat input rejection, automatic selection release and owned cleanup. Register genuine XP handler and explicitly keep original optional cosmetics disabled through its original setter; record decoded target/origin/award and no orb, then restore option/handlers/references.
- **CONSTRAINTS:** No direct interaction/effect/reward calls for this input variant, custom dispatch, fake handler, native audio/physical interaction/normal placement/purchase/drop/profile/progression/full startup claim. Diagnostic source placement/input/materials remain explicit. Original DLLs/pins unchanged; no new content closure or general framework; previous APK/payload/receipts retained and Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small InputBarrelBoundary, one specific existing coin probe variant, existing config/CLI/capture and independent coin-reference baseline; ignored exact stage/settings/packages/build/device receipts.
- **TEST COMMAND:** `./dev prototype --action nova-input-barrel-prepare`; pinned MCP compile; preflight; forced Vulkan build; existing bounded180-second movement-batch-run; current-PID/45-DLL/visual/cleanup checks and host tests.
- **PASS CONDITION:** Original automatic selection/input/server dispatch and source state transition; one real effect52/XP55 with exact decoded data, original source gold/XP delivery, source-count coin tier/lifetime/pool return, no XP orb/native sound attempt, repeat rejected, restored owned options/handlers/target/outline/references. Prior S149/S150/client60-second/subsystem checks and no unexplained device errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First input/dispatch/message/XP/state/timer/reference/cleanup failure with exact stage/settings/config/APK/payload/terminal/current-PID logs/capture; preserve each rejected attempt.
- **STATE/JOURNAL UPDATES REQUIRED:** First failure or accepted exit; concise state/backlog/milestone/risk; scoped input-barrel rollback pointer only after device acceptance; public staged/manual IP review and Conventional Commit.
- **DEPENDENCIES:** S149/S150. Consulted community-prior-art map and pinned Starstorm2 a9a4badd BorgMain original inputBank/base-state boundary; R2API.CommandHelper f539511e ConsoleReady/default application; original EffectDef registration from R2API.ContentManagement. Inspected exact current InteractionDriver/Interactor/InputBankTest/BarrelInteraction/ExperienceManager/ExperienceOrbBehavior/SettingsConVars/CoinBehavior and source prefab. These source contracts govern the Android candidate; no original/community implementation copied.
- **STATUS:** PASS — J200. One original public input press/server barrel dispatch/source8 gold/4 timed XP, real messages52/55 decoding, source coin bursts1/3/four particles/natural3.020-fixed-second return and repeat rejection. Original XP option0/declared1/active0/restored0/no orb, owned selection/reference/handler/pool/default/client/provider cleanup;21048 assertions/156.187-second process/60.018-second hold,45 unchanged DLLs/40 tests, no new errors/crashes. Diagnostic input/manual placement only; S151 physical readiness pending.


## S153 — Original chest drop-table generation
- **ID:** S153
- **TITLE:** Execute the recovered source chest table before integrating purchase/drop physics.
- **CONTEXT:** S152 input barrel/rewards and S146 catalog/grant pass; normal chest purchase/drop remains separate.
- **OBSERVATION:** Source dtChest1 preserves weights0.8/0.2/0.01 and original replacement policy. BasicPickupDropTable consumes Run available-tier lists, which this inactive diagnostic Run has not populated. Original replacement path requires the RandomlyLunar definition even at zero stacks.
- **HYPOTHESIS:** The recovered unchanged table can produce reproducible, valid original UniquePickup choices from a bounded explicit base-item domain on Android without grants/native effects.
- **TASK:** Stage only source dtChest1 and the original locked/ungranted RandomlyLunar definition plus unlocked base ChainLightning; register before inventories. Temporarily initialize original pickup catalog and diagnostic Run tier1/tier2 lists with unlocked base Syringe/ChainLightning. Clone the original table, regenerate through its original method, verify unchanged source weights/replacement policy,64 valid choices with equal-seed reproduction/alternate-seed variation, original distinct/loop semantics and exact catalog/list/table restoration. Conserve inventory/wallet/XP.
- **CONSTRAINTS:** Tier3/other domains absent explicitly; no normal Run availability, chest/purchase/drop physics/item grant/progression/profile/replacement entitlement or full startup claim. No custom RNG/weighting or source DLL/package changes; keep S152 rollback and Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small ChestDropTableBoundary, existing source closure/catalog/config/CLI. Ignored source table/item/stage/build/device evidence.
- **TEST COMMAND:** `./dev prototype --action nova-chest-drop-table-prepare`; pinned MCP compile; preflight; forced Vulkan build; existing bounded movement-batch-run; current-PID/45-DLL/cleanup checks and host tests.
- **PASS CONDITION:** Original source policy/weights and effective0.8/0.2 choices, two allowed valid base choices, reproducible64 draws with both choices and alternate sequence, distinct2/loop5/nonloop2; no grant and original catalog/list/clone registration restoration. Prior S152/client60-second/subsystem checks, no unexplained device errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First source/catalog/replacement/AOT/RNG/unique/loop/cleanup failure with stage/settings/packages/config/APK/payload/build terminal/current-PID logs. Preserve failed attempts.
- **STATE/JOURNAL UPDATES REQUIRED:** First failure/exit, state/backlog/milestone/risk; scoped table checkpoint only after device acceptance; public/manual staged review and Conventional Commit.
- **DEPENDENCIES:** S152/S146. Consulted community map and pinned DebugToolkit d1e2f0aa Items.InitDroptableData/CollectItemTiers; table generation and Run tier lists are separate. Exact current BasicPickupDropTable/PickupDropTable/RandomlyLunarUtils/Xoroshiro/UniquePickup and source asset govern the candidate. No implementation copied.
- **STATUS:** PASS — J203. Exact recovered table/source policy, effective0.8/0.2 Syringe/ChainLightning choices, seeded64-draw reproduction/alternate sequence/histogram55/9, distinct2/loop5/no-loop2 and conserved inventory/wallet8/XP11. Original locked replacement0, clone registration/source/list/catalog restoration, prior S152 and60.029-second client hold;21239 assertions/156.542-second process,45 unchanged DLLs/40 tests, no new errors/crashes. J201/J202 prerequisite failures retained. Normal availability/chest/purchase/drop/grant/progression remain unproven; physical S151 pending.


## S154 — Original source chest input purchase and opening
- **ID:** S154
- **TITLE:** Connect the original source chest roll, callbacks and payment to the accepted input path.
- **CONTEXT:** S152 original input/server rewards and S153 loot-table generation pass separately; an actual source chest has not been purchased.
- **OBSERVATION:** Chest1 has original persistent SetAvailable(false)/ChestBehavior.Open callbacks, Money25, no expansion/unlock requirement, one drop and dtChest1. Null source dropTransform is the original Awake root fallback. Payment compares FreeUnlocks and LowerPricedChests/Consumed even at zero. Natural Delusion Start disables the secondary picker/prompt when the original artifact is disabled. Animator events eject loot, separately from Opening/Opened.
- **HYPOTHESIS:** Original natural chest lifecycle and automatic input/server interaction can perform exactly one original payment and source opening transition under the accepted local authority.
- **TASK:** Stage only measured Chest1/FreeUnlocks/Consumed/Delusion closure. Register original comparison definitions before body/inventory allocation, preserve locked/ungranted items/disabled artifact. Temporarily regenerate original source table against accepted two-item base lists. Instantiate owned source clone, preserve callback targets and methods, let original Awake/Start roll. Feed original interact press/release at wallet8 (no payment), explicitly GiveMoney17 then press again; observe exact detailed/global purchase,25→0, natural Opening→Opened, repeat rejection and list/catalog/target/model/material/pause restoration.
- **CONSTRAINTS:** Manual diagnostic placement/funding/input/materials. Disable owned Animator; omit only owned source SfxLocator; no ejection/physics/grant/visual opening/native audio/normal availability/profile/full startup acceptance. Preserve original DLLs/pins and accepted receipts; Nova asleep while idle. Keep actual original stats context, never fabricate profile initialization.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small ChestPurchaseBoundary; existing closure/config/catalog/CLI and one phase capture. Ignored exact source/stage/build/payload/device evidence.
- **TEST COMMAND:** `./dev prototype --action nova-chest-purchase-prepare`; pinned MCP compile; `./dev preflight`; forced Vulkan build; existing bounded movement-batch-run; current-PID/45-DLL/cleanup/capture verification and host tests.
- **PASS CONDITION:** Correct source policy/persistent callbacks, original natural roll and secondary unavailable, unaffordable input rejected, one original detailed/global/server interaction with actual cost25/wallet0, original Opening→Opened, repeat rejected, conserved inventory/XP and restored owned context. Prior S153/client60-second/subsystem checks pass, no unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First source/reference/lifecycle/callback/input/payment/state/native/cleanup failure with independent exact stage/settings/config/APK/payload/terminal/current-PID logs/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** First failure/exit, concise state/backlog/milestone/risk; scoped chest purchase pointer only after device acceptance; public staged/manual IP review and Conventional Commit.
- **DEPENDENCIES:** S152/S153. Consulted community-prior-art map, pinned R2API.Director f539511e InteractableSpawnCardClone (placement/eligibility/stage caps are separate) and DebugToolkit d1e2f0aa Items.CollectItemTiers (Run drop domains separate from table). Inspected exact current PurchaseInteraction/ChestBehavior/DelusionChestController/Picker/StatManager/Interactor and source prefab; no original/community implementation copied.
- **STATUS:** PASS — J206. Original source policy/natural roll/root fallback/persistent callbacks and inactive secondary path, unaffordable reject/funded25→0/exact original purchase contexts, Opening→Opened1.035s/repeat rejection, inventory/XP11 conservation and table0→2→0/full owned cleanup.21305 assertions/158.295-second process/60.021-second client hold,45 unchanged DLLs/40 tests, no new errors/crashes. No animator/drop/profile/full startup/physical purchase acceptance; S151 pending. J204/J205 compile dependencies retained separately.


## S155 — Original pickup-droplet loading and startup callback
- **ID:** S155
- **TITLE:** Resolve the original droplet prefab before chest ejection/physics.
- **CONTEXT:** S154 original chest purchase/opening passes with Animator disabled; ejection requires PickupDropletController's separately initialized source prefab.
- **OBSERVATION:** Exact original Init issues one LegacyResourcesAPI asynchronous callback for Prefabs/NetworkedObjects/PickupDroplet. Original legacy map and typed source catalog resolve the recovered base PickupDroplet. Source has seven components, mass1/drag0.1/angularDrag5/gravity/nonkinematic/radius0.5 and constant force(0,-15,0). Original factory also requires a Command artifact comparison and pickup-display/factory dependencies, deferred to a separate task.
- **HYPOTHESIS:** Accepted original providers/wrapper can load this untouched prefab and complete its genuine startup callback on Android without activating gameplay/native components.
- **TASK:** Reuse existing static closure for one root, add one conditional separate bundle to avoid reloading the already directly loaded character bundle. Register one owned original-provider location from measured legacy/catalog identity; check sync/async prefab identity, original Init callback assignment/pending balance/acquisition and source components/physics. Restore field/references/locator and prove bundle unload; conserve wallet/inventory/XP and retain prior S154/client hold.
- **CONSTRAINTS:** No instantiation/factory/Command grant/animation/drop physics/acquisition/native audio/full startup capability claim. Original DLLs/pins/source prefab untouched; generated content ignored. Only immediate bundle support needed; no new loader/framework. Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small PickupDropletLoadBoundary, existing closure/config/CLI and conditional LabBuild bundle. Ignored measured catalog/source/closure/build/device evidence.
- **TEST COMMAND:** `./dev prototype --action nova-pickup-droplet-load-prepare`; pinned MCP compile; preflight; forced Vulkan build; existing bounded movement-batch-run; current-PID/45-DLL/cleanup/capture/host tests.
- **PASS CONDITION:** Original typed sync/async and actual original Init callback resolve same non-scene source prefab with all seven source components/physics, no scene instance, exact acquired reference/pending/restoration/unloaded bundle, no gameplay state changes. Prior S154/60-second client hold and no unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First legacy/catalog/import/type/reference/callback/native/cleanup failure, exact source/stage/settings/config/APK/payload/build terminal/current-PID evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** First failure/exit, state/journal/backlog/milestone/risk; scoped droplet-load pointer only after device acceptance; staged public/manual review and Conventional Commit.
- **DEPENDENCIES:** S154; prior-art map, pinned R2API.Addressables f539511e AddressReferencedAsset handle/release semantics and DebugToolkit d1e2f0aa Items.CCCreatePickup using the original droplet factory. Exact current PickupDropletController Init/Start/CreatePickup and source/catalog govern the Android boundary; no original/community implementation copied.
- **STATUS:** PASS — J208. Original typed source sync/async/Init callback and7 component/physics identity, references2→3/pending0→0/no instance/wallet0/XP11 conservation, field/handles/locator5→5/bundle cleanup.21265 assertions/158.356-second process/60.027-second client hold, prior S154,45 unchanged DLLs/40 tests, no new errors/crashes. No instantiation/factory/animation/physics/grant/full startup acceptance. J207 authored compile correction retained; S151 pending.


## S156 — Original pickup-droplet factory and free-flight
- **ID:** S156
- **TITLE:** Spawn the source droplet through its original public factory and observe natural motion.
- **CONTEXT:** S155 original provider/Init callback passes; factory, authority and native Rigidbody motion are unproven.
- **OBSERVATION:** Original factory instantiates the unchanged source, retains CreatePickupInfo, sets UniquePickup/velocity/torque and calls NetworkServer.Spawn. It compares the original Command artifact. Natural ProjectileNetworkTransform caches Rigidbody and chooses server authority; native physics uses source gravity/drag/constant force. Collision reaches a separately uninitialized generic factory. Existing diagnostic ItemTierCatalog is empty, so original CreatePickupDef naturally has no droplet display.
- **HYPOTHESIS:** Original factory and automatic source callbacks can produce a correctly networked droplet and physically plausible free-flight on Android without entering the collision branch.
- **TASK:** Register only the genuine disabled source Command artifact before Run artifact storage allocation. Keep S155 load observations separate, retain its original prefab lease through an optional flight segment. Temporarily initialize the original pickup catalog, select unlocked base Syringe and call only original CreatePickupDroplet with diagnostic placement100 units above the player and velocity(0,20,2). Observe original info/state/network mapping/authority/cache and native free-flight for at least0.5 fixed seconds; compare motion with source gravity/force/drag and actual fixed ticks, observe original network updates and no collision/pickup instance/grant. Destroy only owned droplet before landing, then restore catalog and complete source lease/bundle cleanup.
- **CONSTRAINTS:** No manually instantiated droplet, velocity/pose writes after original factory, manual physics/network ticks, collider/force/gravity changes, Command activation, fabricated availability/ownership or audio success. Existing no-display diagnostic tier catalog explicit. No chest Animator/ejection/collision/acquisition/visual droplet/full startup claim. Preserve45 DLLs/pins/receipts, Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small PickupDropletFlightBoundary; existing optional loader segment, artifact/source closure/config/CLI. Ignored source/stage/build/payload/device evidence.
- **TEST COMMAND:** `./dev prototype --action nova-pickup-droplet-flight-prepare`; pinned MCP compile; preflight; forced Vulkan build; bounded movement-batch-run and current-PID/hash/cleanup/capture/host-test verification.
- **PASS CONDITION:** One original source factory object/info/UniquePickup/network mapping, genuine disabled Command/no user grant, natural original source Start/authority/fixed network position updates, observed native flight consistent with measured source/ticks and damping, no collision/generated pickup/inventory/wallet/XP change; owned object/client map removal/catalog restore and S155 bundle cleanup. Prior S154/client60-second hold and no unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First artifact/catalog/factory/source callback/authority/physics/network/collision/cleanup failure with phase/samples/source defaults, exact stage/settings/config/APK/payload/build terminal/current-PID evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** First failure/accepted exit; state/journal/backlog/milestone/risk and scoped flight receipt only after real device acceptance; public/manual staged review and Conventional Commit.
- **DEPENDENCIES:** S155. Consulted community-prior-art map, pinned DebugToolkit d1e2f0aa Items.CCCreatePickup original CreatePickupInfo/factory seam and R2API.Addressables f539511e handle/release ownership. Exact current PickupDropletController, ProjectileNetworkTransform, CommandArtifactManager, ItemDef.CreatePickupDef and recovered source govern the experiment; no original/community implementation copied.
- **STATUS:** PASS — J209, original factory/automatic native free-flight and owned cleanup pass on Nova. Collision/pickup creation/chest ejection remain separate; S151 physical readiness remains pending.


## S157 — Original native droplet collision and pickup creation
- **ID:** S157
- **TITLE:** Let native recovered-terrain collision invoke the original generic pickup factory.
- **CONTEXT:** S156 original factory/free-flight and S155 original prefab lease pass; collision/generic factory remain unproven.
- **OBSERVATION:** Original OnCollisionEnter calls InitializePickup once while alive, replaces CreatePickupInfo.position with actual transform, invokes original generic CreatePickup and destroys the droplet. Public prefabOverride supports the S146 owned original GenericPickup template. Original generic Start starts its unchanged0.5-second Run-clock delay. Normal chest drops have no override, so the default Init route remains separate.
- **HYPOTHESIS:** Native physics can reach the unchanged collision/factory/Start/delay path on Android with measured terrain and the already justified diagnostic template.
- **TASK:** After accepted free-flight cleanup, retain the original droplet source lease. Create the same owned original GenericPickup template as S146 with Ak components omitted and PickupDisplay disabled/null. Feed that public override and allowed base Syringe to original CreatePickupDroplet three units above a measured clear source terrain surface eight planar units from the actor, initial velocity(0,-2,0). Observe a real native collision, exactly one source pickup at collision position, natural droplet/map destruction, original Start/initial rejection/half-second availability, no grant and owned teardown/catalog/lease restoration.
- **CONSTRAINTS:** No direct collision/InitializePickup/ForcePickupInitialization/generic factory invocation, manual physics ticks, post-factory pose/velocity writes, physics/collider/layer-matrix changes or Command activation. Only read-only collision witness added to the owned droplet. Public diagnostic override/audio/display omissions explicit; no normal chest ejection/default Init/grant/model/audio/physical interaction/full startup claim. Preserve45 DLLs/pins; Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow PickupDropletCollisionBoundary, optional loader/config/CLI staging flag; existing original source closure remains unchanged. Ignored source/stage/build/payload/device evidence.
- **TEST COMMAND:** `./dev prototype --action nova-pickup-droplet-collision-prepare`; pinned MCP compile; preflight; forced Vulkan build; bounded movement-batch-run; current-PID/hash/cleanup/capture/host verification.
- **PASS CONDITION:** Real native terrain collision, exactly one original pickup with original identity/info/collision position and both network maps; natural droplet destruction/map release, unchanged0.5-second delay/permission, conserved wallet/XP/inventory and owned template/pickup/catalog/maps/loader release. Prior source purchase/free-flight and60-second client hold pass with no unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First terrain/layer/factory/collision/position/Start/delay/map/cleanup failure, source defaults, actual collision witness/ticks, exact stage/config/settings/APK/payload/build-terminal/current-PID logs.
- **STATE/JOURNAL UPDATES REQUIRED:** First failure/accepted exit and scoped collision checkpoint; state/journal/backlog/milestone/risk; public/manual staged review and Conventional Commit.
- **DEPENDENCIES:** S156/S146/S155. Consulted community-prior-art subsystem map and pinned DebugToolkit d1e2f0aa Items.CCCreatePickup public factory/CreatePickupInfo; R2API.Addressables f539511e lease ownership. Exact original PickupDropletController/GenericPickupController/native source collider/terrain/Run clock govern collision and delay. Existing authored OnDisable witness technique establishes a read-only callback clock seam. No original/community implementation copied.
- **STATUS:** PASS — J211, original native collision/one pickup, exact retained factory argument/current position, natural droplet/map destruction, original0.520-second availability and conservation/owned cleanup pass. J210 remains rejected; generic source Rigidbody is dynamic, so future position observers must distinguish native ticks. Normal chest default generic Init/ejection and original visuals/acquisition remain separate.


## S158 — Original default pickup factory and recovered item display
- **ID:** S158
- **TITLE:** Use original GenericPickup Init/default factory and natural Syringe display.
- **CONTEXT:** S157 collision uses public diagnostic prefabOverride/display omission. Normal chest drops require the real default prefab; original display remains unproven.
- **OBSERVATION:** Genuine GenericPickup Init is one original legacy async callback. Exact-editor source inventory resolves every component and contains no Ak scripts. Syringe has an empty model address and an existing direct PickupSyringeCluster reference with mesh/renderer; no new model loader is required. Original GenericPickup has a dynamic gravity Rigidbody and0.5-second delay. PickupDisplay creates/scales/spins its original direct model.
- **HYPOTHESIS:** Original default startup callback/factory/display can execute on Android with retained provider leases and a diagnostic material shader, no prefab override or display suppression.
- **TASK:** Build the unchanged generic source in a conditional separate bundle so the original provider need not duplicate-load the live character bundle. Load sync/async and invoke genuine Init before the existing item probe; preserve its source lease through subsequent tests. Existing S146/S157 read that same source when this flag is active. After source collision cleanup call original default CreatePickup with base Syringe/no override, far from the actor on measured terrain; observe natural model creation/mesh/scale/spin, original delay/network mappings and conservation. Use only owned material copies/view-layer changes for readability. Destroy owned pickup/model, restore catalog, then original field/all leases/locator/bundle before body/context teardown.
- **CONSTRAINTS:** Preserve source components/physics/display callbacks,45 DLLs/pins/ownership and entitlement boundaries. No new model loader, guessed GUID, source-prefab mutation, manual lifecycle/motion/physics ticks, item grant, native audio/service success or normal chest ejection/progression claim. Existing direct model reference stays original. Shared bundle dependencies must already be owned/live and recorded; reject unknown dependencies before device run. Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow GenericPickupBoundary; existing optional staging/CLI/config and one conditional build bundle, two source reads and lifecycle hooks. Ignored source/settings/build/manifest/device/capture evidence.
- **TEST COMMAND:** `./dev prototype --action nova-default-pickup-prepare`; pinned MCP compile; preflight; forced Vulkan build; dependency inspection; bounded movement-batch-run; current-PID/hash/cleanup/capture/host verification.
- **PASS CONDITION:** Original sync/async/Init identity/refcount/pending balance, original default factory/no override/state/network maps, natural original direct model creation/mesh/scale/spin and reviewed rendering, unchanged delay/permission and no grant/funds/XP changes, owned object/model/material/catalog/maps and source leases/field/locator/bundle restore; previous tests/client60-second hold and no unexplained errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First bundle/reference/callback/factory/display/material/lifecycle/delay/cleanup failure, actual defaults and original model references, precise phase, exact source/settings/config/APK/payload/dependencies/current-PID/build terminal/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** First failure/accepted exit with scoped default-pickup pointer; state/journal/backlog/milestones/risk; public/manual staged review and Conventional Commit.
- **DEPENDENCIES:** S157/S146/S155. Consulted community-prior-art Addressables/skin/network map, pinned R2API.Addressables f539511e AddressReferencedAsset handle ownership and DebugToolkit d1e2f0aa Items.CCCreatePickup original factory. Exact current GenericPickupController/PickupDisplay/ItemDef/AssetOrDirectReference and typed source/direct-model observations govern the candidate; no implementation copied.
- **STATUS:** PASS — J213, original default Init/source leases/no-override factory/active direct Syringe display/natural spin/delay/cleanup and reviewed real-device rendering pass. J212 authored compile rejected attempt retained. Source chest Animator/ejection, connected acquisition/effects/progression and formal gates remain separate.

## S159 — Original chest animation and default loot ejection
- **ID:** S159
- **TITLE:** Let source animation events complete the original chest-to-pickup chain.
- **CONTEXT:** S154 input purchase, S155–S157 droplet physics and S158 default pickup/display pass independently.
- **OBSERVATION:** The original chest Open clip has two ChestUnzip events, one Chest1Starburst and ItemDrop. Original AnimationEvents caches its ChildLocator/EntityLocator and calls IChestBehavior.ItemDrop. Both source effects use original pools/timers, empty sound names/noEffectData, and have no Ak components. Syringe and ChainLightning have direct original model references.
- **HYPOTHESIS:** Enabling the original chest Animator/AnimationEvents with accepted source leases permits one automatic ejection, native collision and default pickup/display, while preserving payment and source effects.
- **TASK:** Reuse the source purchase probe for one animated chest, with accepted pickup source leases initialized before it; retain the independent animator-disabled command. Keep source roll/two base domains and callbacks; observe original animation/effects/droplet info/network maps/collision/default display/availability. Walk the original actor away through its input boundary on measured terrain to prevent acquisition. Prove owned cleanup and the existing sixty-second client hold.
- **CONSTRAINTS:** No manual ItemDrop/collision/factory/lifecycle/physics calls, post-factory pose/velocity writes, effect suppression, forced loot selection or item grant. Existing diagnostic funding/placement/materials and silent owned SfxLocator omission explicit. Preserve original DLLs/pins and prior rollbacks; no normal placement/profile/startup/progression/controller-gate claim. Nova asleep while idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small ChestEjectionBoundary, conditional hooks in source purchase/droplet lease, existing config/prepare/CLI/capture; ignored exact stage/build/device evidence.
- **TEST COMMAND:** `./dev prototype --action nova-chest-ejection-prepare`; exact-editor compile; `./dev preflight`; forced Vulkan build; existing `movement-batch-run`; current-PID/hash/capture/cleanup review; `./dev test`.
- **PASS CONDITION:** One original payment/opening, animation-driven original droplet carrying exact chest/rolled identity/no override, natural terrain collision/default pickup/active direct model, original delay, unchanged inventory/XP, three natural effect instances/returns, complete owned cleanup and stable client hold; no new errors/crashes.
- **FAILURE EVIDENCE TO CAPTURE:** First animation/reference/pool/ejection/physics/model/authority/conservation/cleanup failure with current attempt, state, event targets, source hashes and logs; immutable rejected stage/receipt.
- **STATE/JOURNAL UPDATES REQUIRED:** Update state/journal/backlog/milestone/risk at exit; scoped checkpoint only after device acceptance; staged public audit/manual IP review and Conventional Commit.
- **DEPENDENCIES:** S154–S158. Consulted community-prior-art map, pinned R2API.ContentManagement f539511e original EffectDef registration and DebugToolkit d1e2f0aa original pickup factories. Exact current AnimationEvents/ChestBehavior/Opening/EffectPool/DestroyOnTimer and recovered source clip/prefabs determine callbacks and assertions; no original/community implementation copied.
- **STATUS:** PASS — J219. J219/S159 passes original source chest animation-to-loot chain on Nova: one original input/Money25 purchase (wallet8 + diagnostic17 →25→0), natural Opening/Opened1.080s and115.013-degree bone motion, original ItemDrop0.470s carrying exact rolled identity/chest/no override. Source droplet velocity observed(0,19.361,1.996), native terrain collision1.436s, one default GenericPickup/direct Syringe model655vertices/automatic152.314-degree spin; original delay0.520s. Original input moves actor5.917units away, inventory/XP11 conserved; three source effects return naturally. Pre-purchase Idle/zero effects, complete owned cleanup and60.006-second client hold/3001fixed ticks/1796frames pass.21459 assertions/165.538-second process,45 unchanged DLLs/40 tests, no new errors/crashes; existing missing-script warning count stays11→11. Scoped LAST_KNOWN_GOOD_CHEST_EJECTION retains S158 rollback. J214–J218 rejected attempts preserved; first-assertion/lease-cleanup and native-position witness corrections verified. Connected acquisition/feedback and physical all-skill S151 remain separate. L5 blocked and formal L5.5/L6/L7 open. APK installed/stopped, Nova asleep.


## S159-a — Preserve the first assertion across cleanup failures (conditional T08)
- **ID:** S159-a
- **TITLE:** Expose the actual prerequisite failure before debugging S159.
- **CONTEXT:** J217 never reaches default loading/collision/ejection; an unentered cleanup assertion masks an earlier actor failure.
- **OBSERVATION:** Deserialized empty reports exist even when their probes have not run; outer finally tests an uninitialized generic lease.
- **HYPOTHESIS:** A two-field first-assertion record plus a strict unentered-cleanup no-op preserves attribution and later cleanup.
- **TASK:** Persist only first predicate/phase before throwing; guard default cleanup on absent field/locator/acquisitions.
- **CONSTRAINTS:** No skipped checks after initialization, rewritten source gameplay or broad diagnostic framework. Original DLLs unchanged.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** MovementBatchProbe.Check/Result, GenericPickupBoundary cleanup, ignored failure records.
- **TEST COMMAND:** Same forced Vulkan S159 run and existing host tests.
- **PASS CONDITION:** A real earlier failure remains explicit through teardown, or the fresh run passes with original source lease cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** First predicate/phase plus later cleanup exceptions, exact build/stage/current PID.
- **STATE/JOURNAL UPDATES REQUIRED:** J217 and next result; no failed capability checkpoint.
- **DEPENDENCIES:** J217; prior-art diagnostic map and existing file-based lab observer; no original/community implementation copied.
- **STATUS:** PASS — J218 preserves the real first predicate/phase and outer cleanup; J219 normal source lease cleanup/full run passes. No separate capability gate claimed.


## I01 — Assemble persistent offline gameplay (whole-game integration)
- **ID:** I01
- **TITLE:** Keep recovered stage, original simulation/combat, local authority, rewards and loot active together.
- **CONTEXT:** User supersedes isolated-proof sequencing with whole-game integration; J219 is the retained rollback.
- **OBSERVATION:** Direct launch has original player/enemy combat, but source interactables/catalogs/client and loot are currently one-shot fixtures after combat. Stock startup remains blocked at J61.
- **HYPOTHESIS:** Existing accepted source/provider/authority routes can be composed into persistent local gameplay without rewriting original simulation or claiming platform success.
- **TASK:** Assemble continuous original director, source barrels/chests/purchases/animated ejection/default pickups/server grants, original reward/clock/stats, measured physical B interaction, HUD and explicit silent client presentation. Build the composition before device verification; iterate its first failures in this integrated path.
- **CONSTRAINTS:** Original installation/DLLs/pins unchanged; no authentication/entitlement/ownership/license success, NetworkUser/LocalUser/profile fabrication, forced progress/victory, original source copying or proprietary tracked inputs. Authored placement/material/HUD/input adapters explicit; default physical launch remains distinct from diagnostic validation. Retain rollback/evidence/storage ownership and idle OLED sleep.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** IntegratedWorldBoundary; conditional connection/director/input/combat hooks; thin existing prepare/runner action; ignored source closure/receipts/device evidence.
- **TEST COMMAND:** `./dev doctor`; `./dev prototype --action nova-whole-game-prepare`; exact-editor compile; `./dev preflight`; `./dev build --target vulkan --force`; `./dev prototype --action movement-batch-run`; actual current-PID/visual/hash/source review; `./dev test`.
- **PASS CONDITION:** Persistent source stage/player/skills/director/local authority and loot operate together on Nova, with original purchases and connected grants/rewards/stats, meaningful sustained combat and no new unexplained errors/crashes; retained playable direct-launch APK. Report limits separately from formal game gates.
- **FAILURE EVIDENCE TO CAPTURE:** Actual first integrated predicate/phase/native or managed error, source/context/network identity, current build/APK/payload/stage/mapping/PID/capture; preserve each rejected attempt.
- **STATE/JOURNAL UPDATES REQUIRED:** State/journal/backlog/milestones/risk and scoped integrated checkpoint only after acceptance; review staged provenance/privacy, Conventional Commit and push.
- **DEPENDENCIES:** J219 and accepted component routes. Consulted prior-art map, pinned R2API.Director f539511e SceneCatalog/director activity, R2API.ContentManagement EffectDef and DebugToolkit d1e2f0aa Run drop lists/original factories. Exact current source governs API/message/serialization; no implementations copied. Measured button1/B binding comes from accepted Nova full capture.
- **STATUS:** PASS — J223 persistent120-second composed gameplay and normal physical-input direct launch/death pass;45 unchanged DLLs/40 tests/no errors/crashes/owned cleanup. J220–J222 failures retained. Scoped integration rollback only; stock startup/profile/route/victory/formal gates remain unprovided. The observed stale defeat HUD is addressed by I02/J224.

## I02 — Broaden integrated loot and repair defeat presentation
- **ID:** I02
- **TITLE:** Extend the composed game's original chest pool and show actual fatal health.
- **CONTEXT:** I01/J223 is the accepted persistent combat/loot/authority rollback. Whole-game integration remains active.
- **OBSERVATION:** Normal direct launch reaches genuine original defeat, but the world HUD retains its last alive health sample. The current source chest domain contains only Syringe/ChainLightning. Recovered CritGlasses/HealWhileSafe are base tier1 definitions with no unlockable/expansion requirement and direct pickup models; original CharacterBody uses them for crit and safe regeneration.
- **HYPOTHESIS:** The existing source closure/catalog/Run-list/factory path can support these additional original items and repeated earned-money purchases without a new loader, gameplay rewrite or forced loot. Copying the measured fatal health into the composed report will expose its existing defeat UI.
- **TASK:** Stage the two measured definitions/models before original catalog/inventory allocation; preserve source identities and restrictions, add only these unlocked definitions to the scoped allowed domain and original tier1 list, retain original dtChest1 policy/RNG/grants. Continue combat to fund repeated natural purchases. Report actual inventory/crit/regen. Update HUD at original fatal damage and retain original death/ragdoll/body lifetime.
- **CONSTRAINTS:** Same I01 ownership/legal/storage/idle-OLED limits. No original DLL changes, unlock removal, granted locked items, synthetic funds/drops/inventory/progression, manual physics, platform/profile success or new physical-control acceptance. Hoof is excluded because its source is locked; ArmorPlate is excluded because its native sound contract is unresolved. Direct launches remain physical; validation automation is explicit.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing integrated boundary, catalog/mask/input hooks and closure recipe; player-defeat HUD observation; ignored stage/build/device receipts.
- **TEST COMMAND:** `./dev prototype --action nova-whole-game-prepare`; exact-editor refresh/console; `./dev preflight`; forced Vulkan build; existing movement-batch-run; normal direct launch with original defeat/capture; `./dev test`.
- **PASS CONDITION:** Composed Nova gameplay retains authority/combat/rewards/120-second stability and four valid original loot choices; at least two real purchases/connected acquisitions, actual stat/inventory evidence, no unexplained errors/crashes and owned cleanup. Normal launch shows fatal world health matching original death report and visually readable defeat/close UI. No guarantee every random item is acquired.
- **FAILURE EVIDENCE TO CAPTURE:** First integrated assertion/error, exact item/model/RNG/message/health identities, archived stage/config/terminal receipt/APK/payload/PID/current errors/capture; preserve rejected attempts separately.
- **STATE/JOURNAL UPDATES REQUIRED:** Update state/journal/backlog and integration summary; advance scoped rollback only on acceptance. Staged privacy/IP/manual provenance review and Conventional Commit/push.
- **DEPENDENCIES:** I01/J223. Consulted community-prior-art map, pinned R2API.Items f539511e registration before original catalogs and DebugToolkit d1e2f0aa CollectItemTiers/Run lists; current original ItemDef/CharacterBody and recovered source govern the contract. No source implementations copied; no new loader or diagnostic framework.
- **STATUS:** PASS — J224. Four original loot choices, three earned-money source chest purchases/connected grants (Glasses2/Syringe1), original crit21%/attack speed1.15/XP40/level2/max-health143/wallet21,16 kills,120.007 seconds/35979 assertions and owned cleanup.45 unchanged DLLs/40 tests/no new errors/crashes. Normal physical-input launch/original death and reviewed HP0/defeat/close UI pass, with report fatal health-4 preserved. Slug/Ukulele were not randomly acquired; no new human physical acceptance or formal gate advancement. Scoped integrated checkpoint retains I01/J223 rollback. APK installed/stopped, Nova asleep.

## I03 — Third-person view and death-to-restart in the composed game
- **ID:** I03
- **TITLE:** Replace the diagnostic view and restart a defeated session without closing the app.
- **CONTEXT:** I02/J224 remains the persistent integrated rollback; broad whole-loop integration is active.
- **OBSERVATION:** The world has real stage collision, original character/combat/loot and actual controller bindings, but uses an orthographic camera and requires closing after original death. Recovered Commando ccpStandard has pitch limits, pivot, camera offset and wall cushion; original CameraTargetParams provides overrides and recoil.
- **HYPOTHESIS:** A temporary perspective Android view/input adapter using those original parameters can provide camera-relative movement and reticle aiming. Fully tearing down the defeated owned world allows a fresh local session in the same process without rewriting death or inventing profiles/platform state.
- **TASK:** Integrate perspective orbit/terrain collision/camera-relative input/reticle directly into the world. Add physical A and UI restart after original death/body destruction, retain completed-session evidence, fully clean owned runtime/catalog/network/source resources, then instantiate a fresh session. Integrate the original lunar-coin definition/catalog exposed by the running combat build; preserve its original absent-NetworkUser grant refusal. Build/run the composed game and repair its first actual failure.
- **CONSTRAINTS:** I02 legal/privacy/storage boundaries remain. No direct movement/state/skill execution, synthetic resurrection, stock CameraRig/LocalUser/profile/authentication claim, progress or victory fabrication. Replay remains diagnostic; actual human controller acceptance is reported separately. Retain I02 rollback and idle OLED sleep.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** NovaThirdPersonView, existing display/input/world/death/spawn/clock lifecycle hooks and thin script-copy list; ignored full stage/build/device/capture/session receipts.
- **TEST COMMAND:** Doctor; existing nova-whole-game-prepare; pinned MCP compile; preflight; forced Vulkan build; movement-batch-run; normal direct launch through natural defeat and UI restart; current-PID/hash/capture/cleanup review; existing host tests.
- **PASS CONDITION:** Sustained composed combat/loot still passes with perspective source-parameter view. Normal physical-mode launch uses camera-relative/ray input. Actual original defeat followed by full owned teardown and a fresh healthy session in the same PID, with reset session inventory/clock and no new errors/crashes. New manual camera acceptance remains distinct from automated UI verification.
- **FAILURE EVIDENCE TO CAPTURE:** First actual camera/input/death/teardown/reinitialization failure and phase, completed/new session records, exact stage/settings/config/APK/payload/PID/current errors/captures. Preserve each rejected build/run.
- **STATE/JOURNAL UPDATES REQUIRED:** State/journal/backlog/milestones/risk at exit; advance only scoped accepted integration checkpoint. Staged public audit/manual provenance review and Conventional Commit/push.
- **DEPENDENCIES:** I02/J224. Consulted community-prior-art camera map and pinned Starstorm2 a9a4badd BossAttackCharge CameraTargetParams override ownership; exact current CameraTargetParams/CharacterCameraParamsData and recovered ccpStandard govern the view. Existing owned teardown supplies restart. No community/original implementation copied.
- **STATUS:** PASS — J228. Perspective composed gameplay120.021 seconds,15 kills/three purchases/two grants; two actual death/cleanup/UI restarts and fresh session3 in the same PID over109.024 seconds.45 unchanged DLLs/40 tests/no new errors/crashes. Source lunar definition and original unavailable grant retained. No new human orbit/A acceptance or formal gate advance; I02 rollback retained. J225–J227 failures preserved.

## I03-a — Preserve the queued composed build (conditional T03)
- **ID:** I03-a
- **TITLE:** Retain one editor build request across reload and attribute its completion.
- **CONTEXT:** J227 loses I03's queued delayCall before build entry.
- **OBSERVATION:** Dispatch succeeds but editor is idle and no terminal result exists.
- **HYPOTHESIS:** A SessionState request and ready-update dispatch survive reload; matching entry/terminal IDs prevent stale attribution.
- **TASK:** Persist only this existing lab request, refuse queued/active duplicates, record entry, check terminal ID and detect absent entry.
- **CONSTRAINTS:** No concurrent editor mutations, general queue/lock/cache redesign, stale APK installation or proprietary tracked material.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing LabBuild and build.py; ignored request/entry/terminal evidence.
- **TEST COMMAND:** Python compile; existing host safety tests; exact-editor forced I03 Vulkan build and request/terminal/APK verification.
- **PASS CONDITION:** Changed-source build actually enters/completes and all receipts match the current request before install.
- **FAILURE EVIDENCE TO CAPTURE:** Dispatch state, request/entry/terminal IDs and first editor error; preserve failed attempt.
- **STATE/JOURNAL UPDATES REQUIRED:** J227 and I03 exit; no capability advancement from dispatch alone; staged privacy/manual review and Conventional Commit.
- **DEPENDENCIES:** I03/J227; existing pinned Unity editor orchestration. Generic editor dispatch, no RoR2 subsystem reconstruction.
- **STATUS:** PASS — J228 changed-source build enters/completes with matching request/entry/terminal identities, zero build errors and accepted Nova execution;40 existing host tests pass.

## I04 — Compose original teleporter, boss, charging, rewards and exit

- **ID:** I04
- **TITLE:** Add the original stage objective directly to the persistent composed game.
- **CONTEXT:** I03/J228 retains camera, combat/loot and same-process restart as rollback. User requests broad whole-loop integration.
- **OBSERVATION:** Source Teleporter1 includes original boss/bonus directors, BossGroup/CombatSquad, holdout and SceneExit. Queen needs Guard, state configurations, source visuals and real projectile paths. Inactive Run lacks stage-selection rule context. Optional audio/profile presentation lacks its Android services.
- **HYPOTHESIS:** Original objective callbacks can operate in the composed local-authority world with source content/catalog/rules and explicit Android presentation boundaries.
- **TASK:** Assemble these dependencies together; build/run the complete candidate on Nova, classify/fix its first failure, then integrate actual stage continuity. Retain genuine boss death, natural charge and earned rewards; do not force completion.
- **CONSTRAINTS:** Shared contracts, legal/platform boundaries and privacy gate apply. Keep I03 recoverable. No package changes, middleware substitution, fake users/authentication/ownership, skipped combat or accelerated/forced charging. Input-gated optional presentation transformations must be identified separately from unchanged original assemblies.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing composed world/input/catalog/director recipe; authored objective adapter; ignored source closure/configuration/transformation/build/device evidence; existing AssemblyProbe and bundle recipe.
- **TEST COMMAND:** `./dev prototype --action nova-whole-game-prepare`; editor import/compile; `./dev preflight`; `./dev build --target vulkan --force`; `./dev prototype --action movement-batch-run`; `./dev test`.
- **PASS CONDITION:** Original teleporter interaction/state transitions, actual source boss spawning/combat/death, natural holdout charge, original rewards and exit execute in the composed Nova game without unexplained errors/crashes; source/candidate hashes and rollback retained. Scene continuity must be evidenced before claiming transition or complete-run progress.
- **FAILURE EVIDENCE TO CAPTURE:** First prepare/import/build/runtime error, exact source identities and transformed methods, current-PID report/log/crash/capture, terminal build/payload receipts and failed stage.
- **STATE/JOURNAL UPDATES REQUIRED:** I04 status and concise state, each rejected composed candidate in journal, accepted checkpoint only after actual device acceptance; scope/formal gates remain explicit.
- **DEPENDENCIES:** I03/J228; original provider/package pins and current accepted legitimate input. R2API.Director f539511e activity/catalog/stage seams and current original APIs consulted; no source implementation copied.
- **STATUS:** PASS — J252, work/experiments/scene-runtime/20261005T011620.982278Z.237.606 simulation seconds/55 genuine kills/four connected grants; real boss/natural charge/reward/exit/count1,28.8 seconds of recorded Wetland continuation with original inventory/XP/master/authority continuity. Zero current-PID errors/crashes and complete owned cleanup;44 unchanged original DLLs plus four documented presentation-method changes;40 tests. Separate objective checkpoint; I03 unchanged. Stock startup/profile, whole route/victory and new physical objective acceptance remain unproven.

## I05 — Continue complete Wetland objective into Rallypoint Delta
- **ID:** I05
- **TITLE:** Complete a second original objective and transport the same run into frozenwall.
- **CONTEXT:** I04/J252 accepts the first objective, actual Wetland entry/continuity and clean teardown; I03 remains the persistent-world rollback.
- **OBSERVATION:** Original Wetland selection requests frozenwall. J252's old30-second entry marker includes1.2 seconds of transport; observed new-stage gameplay is28.8 seconds.
- **HYPOTHESIS:** The accepted original combat/charge/reward/exit and owned transport can repeat with cumulative resources and original stage difficulty/count progression.
- **TASK:** Add actual recovered frozenwall geometry/graphs through the existing converter/builder. Complete both real boss/natural charge/reward/exit loops, preserve original Run/master/body/inventory/XP/authority across both transitions, then play30 seconds measured from completed Rallypoint entry. Use the integrated game to expose the first dependency failure.
- **CONSTRAINTS:** Common legal/device/privacy/preservation rules; I03 and separate I04 APK/payload/sources retained. No stock user/ownership/authentication/profile fabrication, accelerated charge, skipped combat, injected rewards or forced progression. Existing explicit continuous-body/layout/presentation adapters remain documented.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing stage converter/bundle recipe, integrated transport/input run limits, ignored content/attempts and concise state records. No general checkpoint/cache framework.
- **TEST COMMAND:** ./dev prototype --action nova-whole-game-prepare; ./dev preflight; exact-editor forced Vulkan build; ./dev prototype --action movement-batch-run; ./dev test.
- **PASS CONDITION:** Two genuine completed objectives and original stage count2, actual frozenwall geometry/graphs/landing, retained original run/master/net IDs/authority/items/XP,30 seconds of new-stage gameplay, clean current-PID runtime and complete owned teardown.
- **FAILURE EVIDENCE TO CAPTURE:** Attributed build, current-PID first error, per-stage objective/continuity records, source closure/hash receipts, playing capture, crash/exit data and rejected cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Record measured capability/first blocker and scope; preserve I04 and I03 pointers; accepted checkpoint only after device evidence, staged public audit/manual review and Conventional Commit.
- **DEPENDENCIES:** I04/J252; exact original input/pins. Pinned Starstorm2 a9a4badd SceneAssetCollection/SlateMines scene identities and R2API.Director f539511e catalog/stage activity consulted; current original Run selection and device observations govern the route. No implementation copied.
- **STATUS:** PASS — J255.492.433 simulation seconds/116 genuine kills/nine connected grants; two genuine completed objectives, original count2, actual Rallypoint entry/continuity and30.024 seconds of gameplay after loading. Full clean teardown, zero current-PID errors/crashes,44 unchanged DLLs plus the same four presentation-method changes,40 tests. Separate progress checkpoint; I04/I03 unchanged. Next actual destination dampcavesimple; full route/victory and formal prerequisites remain open.

## I06 — Integrate the route through Abyssal Depths and Sky Meadow
- **ID:** I06
- **TITLE:** Repeat four full original objective loops and enter the fifth-stage primordial teleporter context.
- **CONTEXT:** I05/J255 accepts two complete objectives and continuing Rallypoint play; I05/I04/I03 rollbacks remain separate.
- **OBSERVATION:** Original Rallypoint selection requests dampcavesimple. Current original primordial prefab references moon2; its original prong state determines the exit mode. Source preview callbacks are Abyssal HELPER LIGHT1 and Sky Meadow EscapePodMesh12.
- **HYPOTHESIS:** The accepted repeated original simulation/charge/reward/accounting and owned transport can support the remaining ordinary base-stage route while preserving original primordial destination behavior.
- **TASK:** Add actual dampcavesimple/skymeadow geometry/navigation and the original primordial teleporter/configurations/types. Run the full composed route through four genuine objectives and transitions, then30 seconds in Sky Meadow. Observe its actual exit mode/destination and classify the first real dependency failure before extending into moon2/finale.
- **CONSTRAINTS:** Shared preservation/legal/device/privacy rules; retain I05/I04/I03. No forced stage completion, accelerated charge, injected rewards, changed health/damage or forced moon destination. Limited deck/loot/layout/continuous-body adapters and unavailable stock platform/profile/audio remain explicit. No package changes or original input edits.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing source closure and stage converter/builder, composed original state registrations/teleporter selection and run deadlines, ignored outputs, state/backlog/journal.
- **TEST COMMAND:** Existing nova-whole-game-prepare, preflight, forced Vulkan build, movement-batch-run and dev test.
- **PASS CONDITION:** Four genuine boss/natural charge/reward/exit completions, original count4, actual five-stage route, original run/master/body/authority/inventory/XP continuity,30 seconds after completed final entry, original primordial context/destination observations, clean current-PID runtime and owned cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** Request-bound build/APK/payload/source hashes, per-stage objectives and continuity, first current-PID error, scene/prong state/mode/destination, playing capture, native crash/exit data and failed cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Capture each rejected combined candidate and actual capability; advance a separate rollback only after device acceptance, manual/public staged review and Conventional Commit. Complete route/victory remains unproven.
- **DEPENDENCIES:** I05/J255, pinned input/toolchain. R2API.Director f539511e catalog/stage seams and Starstorm2 a9a4badd SceneAssetCollection/SlateMines metadata consulted. Current original LunarTeleporter/SceneExitController/SceneDef source governs destination; no original/community implementation copied.
- **STATUS:** PASS — J256. Four genuine completed objectives and original count4; actual five-stage route, retained continuity and30.035 seconds of Sky Meadow play. Primordial destination moon2 observed; clean current-PID runtime/owned teardown,44 unchanged DLLs plus four presentation changes,40 tests. Separate route checkpoint; I05/I04/I03 retained. Finale remains subsequent.


## I07 — Continue the whole game into the original Moon mission
- **ID:** I07
- **TITLE:** Fifth original objective and recovered Moon mission composition.
- **CONTEXT:** I06/J256 accepts four genuine objective/exit loops and the actual five-stage route. Its primordial source reports moon2. I06/I05/I04/I03 remain separate immutable rollbacks.
- **OBSERVATION:** Original Moon source contains16 randomized batteries requiring4 completions, three elevators, four scripted boss encounters, an arena trigger and a180-second escape controller. Original phase transitions depend on genuine squad defeat; escape callbacks reference original ending definitions.
- **HYPOTHESIS:** Existing original simulation/catalogs/content conversion/local authority can support the original mission when its complete wiring and actors are composed into the continuing game.
- **TASK:** Integrate actual moon2 geometry/graphs, measured original mission scripts/trigger wiring, source batteries/elevators/Brother encounter/escape callbacks, original Brother/Hurt/Lunar actors/configurations/default visual bindings and source charging indicator. Complete Sky Meadow naturally and enter the mission with retained run/body/master/inventory. Build/run the whole route as the dependency scanner; repair first real failure, then continue natural batteries, encounters, escape and results.
- **CONSTRAINTS:** Shared legal/device/privacy/preservation rules. No forced charge, boss deaths, mission completion, game-over success, ownership/authentication/entitlement grants or platform availability. Source-native audio/presentation unavailable; declared activation/material/layout/continuous-body adapters remain explicit. Original installation untouched, generated scene/assets ignored.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing stage/objective converter/bundle recipe and source actor bindings; Moon-specific activation/observation boundary, bounded route run limits and durable state. No replacement global loader/framework/package.
- **TEST COMMAND:** Existing nova-whole-game-prepare, preflight, forced exact-editor Vulkan build, movement-batch-run and dev test.
- **PASS CONDITION:** Genuine fifth boss/natural-charge/original-exit and original count5, with optional loot outcome recorded separately, actual Moon entry/graphs/landing and run continuity, source mission context/current states recorded, clean current-PID runtime and owned cleanup. This entry checkpoint does not establish battery/boss/escape/victory acceptance; continue those through the same integrated game. Full route victory requires original normal completion and results, never an injected ending.
- **FAILURE EVIDENCE TO CAPTURE:** Original source/typed catalog/script identity and transformation receipts; request-bound APK/payload hashes, first actual runtime failure, source phase/battery/escape states, playing capture, crash/exit and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve each rejected combined attempt and first failure; separate accepted checkpoint only after device evidence, manual IP/privacy review, staged public scan and Conventional Commit. Formal stock-startup/profile gate remains J61 blocked.
- **DEPENDENCIES:** I06/J256. Pinned Starstorm2 a9a4badd SceneAssetCollection/SlateMines identity and R2API.Director f539511e stage/director seams inspected; original MoonBatteryMissionController, BrotherEncounter phases, ScriptedCombatEncounter, AllPlayersTrigger and EscapeSequenceController supply actual contracts. Original MonoScript metadata and typed catalog queried locally; no source implementation copied.
- **STATUS:** IN PROGRESS. Full Moon content/wiring and six actor templates assembled; J257–J263 repaired with failed evidence retained. J264 whole-game run reaches the second charged/defeated objective but stalls at replay pickup selection. J265 identifies upper-floor loot; J266 genuine death rejects the following route run. Complete Moon input loop is staged, and J267 restores original optional-loot exit semantics. Full-game capture continues beyond Moon entry; no Moon capability checkpoint.


### I07-S01 — Require the actual accepted runtime configuration

- **ID:** I07-S01 (conditional T03 support).
- **TITLE:** Reject build receipts used as gameplay configuration.
- **CONTEXT / OBSERVATION:** J261's integrated device run fails before gameplay because attributed recovery used a historically mislabeled build receipt instead of the archived runtime resource.
- **HYPOTHESIS:** Required body/master/display fields distinguish the accepted runtime configuration before staging mutations.
- **TASK:** Guard the existing preparation entry and restore/archive the actual stage resource.
- **CONSTRAINTS:** Common contract; no general receipt/cache/locking redesign or unknown input acceptance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing nova_bridge preparation, ignored snapshots, journal/state.
- **TEST COMMAND:** ./dev prototype --action nova-whole-game-prepare; exact-editor build and complete integrated device run.
- **PASS CONDITION:** Missing fields reject before mutations; the repaired actual resource passes body catalog registration on device.
- **FAILURE EVIDENCE TO CAPTURE:** Runtime resource/build receipt distinction and first source field failure.
- **STATE/JOURNAL UPDATES REQUIRED:** J261; I07 status remains separate from this support outcome.
- **DEPENDENCIES:** I07/J261.
- **STATUS:** DONE. Guard present; repaired device runs pass registration and reach gameplay. No new game milestone from the guard.

### I07-S02 — Classify the actual integrated pickup stall

- **ID:** I07-S02 (conditional T08 support).
- **TITLE:** Observe pickup distance, collider and original selection.
- **CONTEXT / OBSERVATION:** J264's second objective reaches genuine boss defeat/natural full charge, but replay selection/grant/exit stalls with two live pickups and no runtime exception.
- **HYPOTHESIS:** Current replay distance/pivot aiming prevents the original three-unit interaction path from selecting a pickup.
- **TASK:** Approach the closest eligible pickup more closely, aim at its interaction collider, and record actual distance/layer/availability/selection in the existing whole-game report.
- **CONSTRAINTS:** Common contract; preserve original range, physics, interaction, grants and progression. No direct inventory/charge/exit injection or global diagnostic framework.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing integrated/objective input replay and world report; ignored full-run evidence.
- **TEST COMMAND:** ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** The complete game continues through the stalled reward/exit boundary, or a specific observed first failure replaces the ambiguous stall.
- **FAILURE EVIDENCE TO CAPTURE:** Pickup identity/position/interaction collider/layer/distance/availability/selection, current-PID logs and capture.
- **STATE/JOURNAL UPDATES REQUIRED:** J264 and follow-up outcome; keep I06 and earlier rollbacks unchanged.
- **DEPENDENCIES:** I07/J264; pinned DebugToolkit d1e2f0aa pickup observation and original Interactor/InteractionDriver contracts inspected.
- **STATUS:** COMPLETE, discriminating failure J265. Actual available reward collider is16.236 units away on the upper floor; closer horizontal approach alone is insufficient. No capability advance.

## I07-S03 — Route the continuing game through recovered navigation

- **ID:** I07-S03.
- **TITLE:** Original graph path to normal movement/jump input.
- **CONTEXT / OBSERVATION:** J265 finds original Wetland reward on an upper floor; direct horizontal replay cannot reach it.
- **HYPOTHESIS:** Recovered original ground graph and original PathFollower can route the existing replay to another floor.
- **TASK:** Integrate original path queries and waypoint following into the continuing game for obstructed/distant interactables and objectives; build/run the full route toward Moon.
- **CONSTRAINTS:** Common contract; unchanged original item position, range, grant, graph gates, body hull/slope/jump/speed, physics and natural progression. Feed normal input, never pose writes.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing integrated world/objective replay, existing structured world report; ignored stage/build/run.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Full continuing game gets past the actual reward/exit and reaches its next original progression boundary. Unreachable-path observations classify failures, not acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** Graph reachability/waypoints/destination/jump, actual player/pickup positions, current-PID errors/capture and source identities.
- **STATE/JOURNAL UPDATES REQUIRED:** First actual result; preserve I06/I05/I04/I03 checkpoints.
- **DEPENDENCIES:** I07/J265; pinned Starstorm2 a9a4badd BorgMain inputBank/GenericCharacterMain delegation and exact original BroadNavigationSystem/NodeGraph/PathFollower API inspected; no implementation copied.
- **STATUS:** IN PROGRESS. J266 full-route run ends in original first-stage death before upper-floor navigation acceptance. Combat fallback is separated; J267 also removes the laboratory optional-loot exit overconstraint. Next full game includes Moon mission input and ending capture.

## I07-S04 — Continue original Moon mission input in the whole game

- **ID:** I07-S04.
- **TITLE:** Batteries, elevators, scripted arena combat and extraction in one continuing run.
- **CONTEXT / OBSERVATION:** Source mission wiring/actors are assembled; ending the earlier capture after30 seconds of Moon entry could not exercise its gameplay. Original charged teleporter does not require pickup collection.
- **HYPOTHESIS:** Existing original interaction/movement/holdout/director/mission callbacks can execute the complete source mission when replay navigates its actual targets.
- **TASK:** Feed the established input bridge toward available source batteries, hold their actual charge zones while fighting, enter active original JumpVolumes/AllPlayersTrigger, fight actual encounter members and navigate to active extraction. Continue beyond entry until original escape/ending or the first actual failure. Restore source optional-loot exit semantics; record missed loot instead of blocking progression on a lab-only condition.
- **CONSTRAINTS:** Common contract. Never set charge, kills, phases, pose, ending, ownership or account identity. Physical controls share the same original input boundary. Existing accepted rollbacks are immutable. Ending boolean alone does not establish valid results/profile persistence.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing Moon/world input and reports, objective transport assertions, full-run timeout configuration; ignored immutable builds/device evidence.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Actual whole-game execution reaches/completes source mission phases, with each outcome attributed. Full victory additionally requires original successful ending/results and persistence, not mere compilation or entry.
- **FAILURE EVIDENCE TO CAPTURE:** First actual failure, original source state/charge/encounter members, navigation/input target, ending/escape state, exact build/payload identities, logs/capture/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** I07 first-failure journal and concise state; separate accepted device checkpoint only after evidence.
- **DEPENDENCIES:** I07/I07-S03, source MoonBatteryMissionController/JumpVolume/AllPlayersTrigger/ScriptedCombatEncounter/EscapeSequenceExtractionZone and ChargedState reviewed; pinned Starstorm2 a9a4badd and R2API.Director f539511e. No source implementation copied.
- **STATUS:** IN PROGRESS. Both new contracts verified in the exact editor. Full71.312-second/zero-error Vulkan ARM64 build,39 payload hashes and40 host checks pass; J268 reaches the second genuine boss/charge and rejects a replay route blocked at root geometry. Normal-input obstacle recovery and removal of the lab-only per-stage pickup activation gate now feed the next complete game.

## I07-S05 — Recover ordinary input at an obstructed graph route

- **ID:** I07-S05.
- **TITLE:** Jump/sidestep/back-off in the continuing game.
- **CONTEXT / OBSERVATION:** J268 records an original reachable26-waypoint route, constant actual player position, grounded state/jumpCount0 and movement input at a visually reviewed source root/ledge obstruction. Both genuine boss/charge loops execute; no current-PID error.
- **HYPOTHESIS:** Normal jump and short alternate steering can clear this local obstruction; a source graph link alone does not guarantee present capsule clearance.
- **TASK:** Integrate bounded recovery into existing replay when actual position makes no progress; keep the whole five-objective/Moon run. Remove optional looting as a prerequisite for source teleporter activation or full-run victory acceptance.
- **CONSTRAINTS:** Common contract. Original state handles jump eligibility; original physics/collision/graphs and all genuine combat/progression remain. No actor relocation, forced state/charge/death/grant or changed movement limits. Earlier accepted proofs/rollbacks remain.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing integrated replay and final-run assertions/reports; ignored source/build/device evidence.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Whole running game gets past the actual obstruction and reaches its next source progression boundary. Only genuine successful original ending supports victory; optional loot counts are observations.
- **FAILURE EVIDENCE TO CAPTURE:** Actual position/input/jump/progress/recovery count/waypoint, source states, current-PID errors, capture/cleanup and exact build hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** First actual result and I07 status; no accepted pointer advance on failure.
- **DEPENDENCIES:** I07/J268; pinned Starstorm2 a9a4badd original input delegation and original navigation/idle-teleporter source reviewed; no implementation copied.
- **STATUS:** IN PROGRESS. Exact-editor compile, preflight,40 host checks,75.048-second/zero-error full build and39 payload/45 assembly hashes pass; complete route/mission device capture underway.


## I07-S06 — Complete original Run streams and notification context

- **ID / TITLE:** I07-S06 — Remove measured full-route context gaps.
- **CONTEXT / OBSERVATION:** J269 completes fifth original objective; AdvanceStage fails at GenerateLoopRNG. Earlier observer assertion rejects a source-permitted notification shape without decoded details.
- **HYPOTHESIS:** Exact original deterministic streams and tolerant notification observation unblock the same continuing game.
- **TASK:** Restore original RNG initialization/order, retain seed140 and stage-choice sequences, restore owned context on teardown; record decoded notifications and count positive resolved player messages only. Build/run the complete route and Moon mission.
- **CONSTRAINTS:** No game DLL/input/package change, forced progression, grants or authentication. Accepted persistent/route pointers stay immutable until acceptance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** EnemyRewardBoundary, TeleporterWorldBoundary, IntegratedWorldBoundary; ignored attributed build/run.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Fifth original AdvanceStage reaches actual Moon; decoded notification evidence explains non-counted packets; no new unexplained failure. Full I07 victory remains separate.
- **FAILURE EVIDENCE TO CAPTURE:** First current-process error, RNG/notification context, scene entry and actual Moon state, APK/payload receipts and teardown.
- **STATE/JOURNAL UPDATES REQUIRED:** First actual result and I07 status; failed attempts advance no checkpoint.
- **DEPENDENCIES:** I07/J269; pinned R2API.Director f539511e and DebugToolkit d1e2f0aa plus exact original Run/notification source.
- **STATUS:** J270 builds/runs with initialized streams; genuine first-stage death prevents transition acceptance. Continue the complete game with boss-aware ordinary input and ending context.


## I07-S07 — Carry the whole game through original ending/results

- **ID / TITLE:** I07-S07 — Integrate complete ending context and Android result persistence.
- **CONTEXT / OBSERVATION:** J270 genuine death; known original ending requires initialized statistics, GameOverController/report/catalog context. Moon source SceneDef exists but was omitted from registered metadata.
- **HYPOTHESIS:** Boss-aware replay and complete source ending context allow the assembled route/mission to progress into original report generation.
- **TASK:** Integrate original statistics/scheduling, genuine server/client ending and original report XML; provide an owned Android presentation template and separate local run ledger with checked reload/backup. Include exact Moon metadata.
- **CONSTRAINTS:** No fabricated victory, grants, login, NetworkUser, achievements or coins. Stock cutscene/Steam-backed UserProfile remain explicitly unavailable. Keep accepted rollback and original numerical code.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing world/input/prepare interface, authored IntegratedResultsBoundary and source-ending closure selection; ignored whole-game evidence.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Genuine original escape/ending, generated source report/client delivery, exact report XML reload and retained Android run result. Early game-over flag or compilation is insufficient.
- **FAILURE EVIDENCE TO CAPTURE:** First original stats/catalog/Moon/ending/native error, full current-process log, genuine report identity and result reload, owned teardown.
- **STATE/JOURNAL UPDATES REQUIRED:** Actual whole-game result; advance no failed checkpoint.
- **DEPENDENCIES:** I07/J269/J270; exact original report/ending/statistics source; pinned prior-art references above.
- **STATUS:** Host preparation/import repairs preserved as J271; expanded145.219-second/zero-error Vulkan build,39 payload/45 assembly hashes and40 tests pass. J272 device stops at original statistics XML-readiness write through the absent save system; subsequent model cleanup fails. Run-scoped unavailable-profile metadata boundary and first-error capture feed the next whole-game retry; ending/persistence acceptance remains open.

### I07-S08 — Complete composed application loop

- **CONTEXT / OBSERVATION:** J273 statistics execute in gameplay; actual first-stage defeat has clean teardown but no original ending report or app navigation. Boss-priority replay does not improve survival.
- **HYPOTHESIS:** Accepted add-first input and an owned application flow can retain original simulation/ending accounting without unavailable platform/profile initialization.
- **TASK:** Assemble Commando/Drizzle start, genuine defeat→original StandardLoss/report, restart, genuine victory results→menu, and the continuing Moon route.
- **CONSTRAINTS:** Existing shared safety/privacy/platform contract; no forced death/victory/charge or stock-menu/profile claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** OfflineApplicationBoundary, existing Start/input/death/results/teardown orchestration, nova_bridge staging.
- **TEST COMMAND:** preflight; test; forced Vulkan build; existing full movement-batch-run; manual app launch at capability exit.
- **PASS CONDITION:** Source ending/client/report persistence and completely cleaned fresh-session start actually run on Nova; full Moon route remains its own required acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** First source exception, decoded report, original death/Moon state, scoped cleanup and current launch logs/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Record each full-game exit; retain I06/I03 and advance no pointer on failure.
- **DEPENDENCIES:** Current integrated candidate and J273 metadata repair.
- **STATUS:** Imported/compiled candidate;73.138-second/zero-error Vulkan ARM64 build,39 payload/45 assembly hashes and40 tests pass. J274 original StandardLoss/server report/client notification pass; original XML save fails before persistence. Complete teardown passes. Original item-array XML registration compiles/builds in74.955 seconds with zero errors;40 tests pass. Full Nova retry running; app-loop acceptance pending.

**I07-S06/S08 continuation, J275:** Five original objective loops complete; current original RNG/loop generation works, but ClassicRun's serialized loop-reset name array is absent on the composed AddComponent Run. Recover the exact field/source hash, preserve/restore owned context, and retry the full game. Nearby post-boss combat remains ordinary input; original stats XML comparisons and a truthful defeated-boss HUD are included. All passes/acceptance still require the integrated Nova outcome.


**I07-S06/S08 continuation, J276:** Five genuine objectives reach source counter5 and load Moon geometry. Retain16 original required Highlights (244 total) before deferred mission activation; fix already-active persistent scene restoration on partial-load cleanup. Continue the full route, Moon mission and actual ending/persistence. Failed cleanup does not advance any checkpoint.

### I07-S09 — Broader earned items in the continuing run

- **CONTEXT:** Continuing Moon/application composition still uses three white items and one green item.
- **OBSERVATION:** Original SprintBonus and FlatHealth definitions are base-game items; unchanged CharacterBody recalculation consumes their inventory stacks for speed and health. ArmorPlate additionally requests a network sound asset and is not part of this chunk.
- **HYPOTHESIS:** Registering the two exact definitions before inventory/catalog allocation and admitting them to existing original drop lists extends real purchases/grants without a gameplay rewrite.
- **TASK:** Retain the original chest table and weights; expand its available domain with SprintBonus/FlatHealth. Record actual acquired stacks, movement speed and health. Show live Moon battery/encounter/input objectives in the same playing HUD.
- **CONSTRAINTS:** Current common platform/privacy/storage/ownership contract; only receipted original base definitions with no expansion/unlockable requirement; no granted items, synthetic stats or altered drop weights. Older accepted configurations retain their four-item domain. Do not alter an in-flight build/run.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing objective item closure, reward eligibility, original loot lists, world observations and HUD.
- **TEST COMMAND:** preflight; test; forced Vulkan ARM64 build; full movement-batch-run through ordinary source purchases and item grants.
- **PASS CONDITION:** Six-choice original chest domain, real acquired item/stack/stat evidence, no new source exception, readable playing HUD and owned teardown. Source inspection/compilation alone do not pass it.
- **FAILURE EVIDENCE TO CAPTURE:** Original item registration/type/asset error, actual drop domain and grants, stats/authority/ending errors, current-run logs/capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate build/run attribution; advance no pointer on failure.
- **DEPENDENCIES:** Current full-route attempt exit; pinned DebugToolkit d1e2f0aa Items original catalog/drop-list knowledge and exact original definitions/CharacterBody stat source inspected. No implementation copied.
- **STATUS:**21 source-closure files/323270 bytes staged after J277 exits; imported/compiled/preflight pass. 169.779-second/zero-error ARM64 Vulkan build and40 tests pass. Integrated device acceptance pending.


**I07-S06/S08 continuation, J277:** Moon geometry checks pass, then inactive serialized Toggle lacks original server scene-object activation/Awake. Use the original HLAPI SpawnObjects path after complete eligible-object ownership validation; preserve source randomization and capture the actual activation error before cleanup. Full-game retry retains I06/I03. The required diagnostic fix caps only the integrated input sample tail (900; cumulative counts/all actor records retained) and atomically publishes compact JSON, following an observed23 MB mid-write capture failure. This serves the next whole-game run, not a general observability framework.


**I07-S09 correction, J278:** Original Hoof has a real unlockable; eligibility guard rejects it before gameplay. Keep it locked and replace this candidate with original SprintBonus (Energy Drink), which has null expansion/unlockable, alongside FlatHealth. Full device cleanup passes. Source eligibility checks remain mandatory and now name the rejected item. Repeat the full game; no accepted pointer advances.


**I07 continuation, J279:** Corrected item eligibility and original first spawn target/preload/cost/placement pass. Fix only the legacy observer's wall-time comparison: source director credits accrue on fixedDeltaTime. Record reconstructed wave time and original Run.fixedTime elapsed, retain0.15 tolerance/all cost/credit assertions, and repeat the whole game. No gameplay numerics or source methods change.


**I07-S06/S08 continuation, J280:** Five genuine objectives complete. Original Moon server scene-object activation,30 identities, Toggle Awake/Generate/randomized selection and authority now pass before the first mission Start frame. Fix the adapter's redundant same-active-scene returnfalse, retain explicit active/catalog identity assertions, and continue the entire route/mission/ending. Full cleanup and long atomic report capture pass; no rollback advance. I07-S09 also corrects the observed HUD stack read from unpopulated report configuration; original earned inventory/stat behavior remains unchanged.


**I07-S07/S08 partial acceptance, J281/J282:** Original genuine loss/client/report/XML round trip and owned Android ledger now pass. Same integrated APK's actual GUI start, natural death, clean restart, return to menu and new run pass in three same-process sessions with prior results retained. No scripted gameplay input/forced death/stock profile or new physical-controller acceptance. MainEnding/Moon/full victory remain open; I06/I03 unchanged.

### I07-S10 — Original Moon natural-population context

- **CONTEXT:** Complete Moon/application composition is retained; stock platform startup stays unavailable.
- **OBSERVATION:** Retained Moon scene omits original ClassicStageInfo. Original CombatDirector uses its monsterSelection when its serialized deck is absent; most source Moon directors, including battery directors, use that fallback.
- **HYPOTHESIS:** Retaining the exact component/pool closure and original Start/RebuildCards supports actual source-weighted Moon population with the already composed Lunar actors.
- **TASK:** Retain original serialized ClassicStageInfo and DCCS dependencies; scope clones only to bind known original spawn cards to the existing Android actor templates. Preserve category weights/availability/expansion conditions, source randomization, original credit/timing/placement. Observe actual selected cards and native spawns in the continuing full game.
- **CONSTRAINTS:** Common contract; no forced selections/spawns/charge/kill/victory, unknown selected cards stop with a named failure; no middleware or platform capability claim.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing ignored Moon conversion/receipt; integrated_moon.py; MoonMissionBoundary.cs.
- **TEST COMMAND:** ./dev preflight; ./dev test; forced Vulkan build; existing movement-batch-run whole-game lifecycle.
- **PASS CONDITION:** Original ClassicStageInfo generates nonempty eligible selection, mapped source actors spawn under original directors, full mission continues with truthful evidence. Compilation alone is insufficient.
- **FAILURE EVIDENCE TO CAPTURE:** Source pool/card names and weights, actual current-launch first initialization/native/selection/spawn failure, original scene count and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Record source hashes/clones/selection scope, real full-game result, first failure and rollback; maintain open Moon/victory gates.
- **DEPENDENCIES:** J280 source activation; J281/J282 ending/application integration; immutable I06/I03.

**I07-S10 build preparation, J283:** Full source stage population context and245 mission behaviors retained;3813-file/297672309-byte source closure includes reuse. Known card bindings use scoped source-named clones with original weights/eligibility; every Moon director is observed. Import/compile/live preflight/40 checks and immutable archive pass. Forced full-game build running; no device or mission acceptance yet. I06/I03 unchanged.

**I07-S10 full build:**179.271-second/zero-error forced Vulkan build;39 payload/45 assembly identities, matching terminal attribution and APK hash verified. Full Nova route running; no new device capability claimed yet.

**I07-S10 device exit, J283:** Full first objective/transport and genuine loss/client/XML/ledger/cleanup pass; zero unexpected errors. The player dies during Wetland teleporter approach before Moon, so population/mission/victory remain unaccepted. Preserve evidence; repair the observed driver combat gap, then continue the entire route.

### I07-S11 — Self-defence during objective travel

- **ID:** I07-S11.
- **TITLE:** Self-defence during objective travel.
- **CONTEXT / OBSERVATION:** J283 reaches Wetland; idle teleporter approach resets all combat input while eight enemies close in. Kills stay59 until genuine death. Source runtime/results/cleanup pass.
- **HYPOTHESIS:** Ordinary firing/evasion when a close enemy interrupts travel lets the same composed game reach later mission dependencies.
- **TASK:** Keep original interaction priority once selected; otherwise use the accepted combat input path within20 units, without the charging-zone steering constraint. Retry the entire five-objective/Moon/ending route.
- **CONSTRAINTS:** Diagnostic replay only; physical direct-launch controls and original health/damage/difficulty/spawn/charge/progression remain. All common safety/platform/privacy/rollback rules apply.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** TeleporterWorldBoundary.cs, ignored full candidate/config/archive/run evidence.
- **TEST COMMAND:** preflight;40 host checks; forced Vulkan build; full movement-batch-run.
- **PASS CONDITION:** Actual travel threat combat/interaction and later whole-game progress occur without new source errors; no forced survival or claimed Moon/victory before execution.
- **FAILURE EVIDENCE TO CAPTURE:** First current-run error or genuine defeat, approach/combat input and enemy count, actual objectives/transports/mission/ending/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Each full-game exit with truthful gate status; no failed pointer advance.
- **DEPENDENCIES:** J283 full-game exit, pinned Starstorm2 a9a4badd original input-bank/state delegation, existing accepted combat boundary.

**I07-S11 preparation, J284:** Existing full Moon/application/world candidate retained; scoped approach-combat driver correction imports/compiles. Live preflight,40 tests and immutable archive pass. Forced full-game build next; no device acceptance yet.

**I07-S11 full build:**85.445-second/zero-error Vulkan ARM64 build and matching hashes/receipts pass. Full Nova route retry next; acceptance pending.


**I07-S10/S11 device exit, J284:** Five genuine objectives and original Moon scene/mission Start pass; the diagnostic approach-combat repair survives the whole route.429 kills/21 pickup notifications. Selected original Exploder is missing its owned actor; shared Moon Phase1 configuration and Lunar metadata also fail in actual logs. Population/mission/victory remain unaccepted; full cleanup passes, I06/I03 unchanged.

### I07-S12 — Complete measured original Moon dependency closure

- **ID:** I07-S12.
- **TITLE:** Original Exploder, shared Moon mission states and Lunar metadata/support in the full game.
- **CONTEXT:** J284 reaches original Moon Phase1 after five genuine teleporter loops.
- **OBSERVATION:** Selected Exploder lacks its owned template; original drop tables have seven unindexed definitions, Lunar elite equipment has no index, and Phase1's omitted shared config leaves its unconditional effect null.
- **HYPOTHESIS:** Exact original actor/config/catalog/support closure lets the mission run without filtering source population or replacing simulation.
- **TASK:** Add original Exploder/default animation/visual/state closure, shared Scenes/moon state configs, required metadata before body/catalog use, typed Lunar missile/Cripple support and source-elite-aware spawn observation. Build/run the whole route and fix its first actual blocker.
- **CONSTRAINTS:** Retain I06/I03; unchanged source weights/availability/unlock/expansion/numerics. Metadata registration grants no items or eligibility. No fabricated platform/ending or unrelated rewrites.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing integrated_moon staging and partial movement/objective/actor/Moon boundaries; ignored converted assets and evidence.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Matching build/assembly/payload receipts; the full Nova route continues the original Moon population/mission without the recorded catalog/availability/effect failures. Capability acceptance requires actual gameplay.
- **FAILURE EVIDENCE TO CAPTURE:** First named failure and preceding current-process logs, original selected cards/weights, mission/authority, captures, assembly/build/payload attribution and complete cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Record each integrated exit and next actual blocker; update milestones without inferring full-run success; privacy review and logical commit.
- **DEPENDENCIES:** J284 full route evidence; scoped source catalog and Android provider lifetime. Pinned R2API.Items/ContentManagement/Addressables f539511e and exact input inspected; no source implementation copied.


**I07-S12 J285/J286:** Complete original Exploder/shared mission/catalog/typed Lunar support closure imports/compiles,40 tests pass. Build rejects the old four/five support count before player build; failure preserved. Guard now also admits the measured seven supports with owned path/existence checks, and canonical staging carries their metadata. Fresh full candidate/build/run next; no device acceptance or pointer advance.

**I07-S12 full build, J286:**157.734 seconds/zero errors; matching receipts,45 assembly/39 payload identities and APK hash verified.40 tests pass. Whole Nova retry follows; no new capability acceptance.

**I07-S12 J286 exit/J287:** Actual integrated configuration omits optional Barrier initialization; Cripple ownership guard rejects its absent snapshot before gameplay. Full cleanup/zero unexpected process errors pass. Own/restore the exact Cripple field and real provider lease independently, then repeat the full composed game. No source gameplay change or new milestone/pointer acceptance.

**I07-S12 J287 full build:**84.092 seconds/zero errors,40 tests, matching39 payload/45 assembly/APK receipts. Launcher refuses an inherited batch receipt before device installation; retain it under the parent evidence and issue a fresh current run. Full-game retry running; no new capability acceptance.


**I07-S12 J287 exit / J288:** Five genuine loops and five actual transports reach original Moon population/Phase1; genuine defeat persists through original XML/ledger. Wrong upper-arena entry, missing Run equipment expansion mask, pooled optional particle-tail OnDisable and hidden handler exceptions are measured integrated issues. Correct those contexts/optional presentation and expose actual delegate exceptions, then run the full route. Source battery/elevator/boss/escape/victory remain open; I06/I03 unchanged. Exact command: `./dev prototype --action movement-batch-run` after fresh full forced Vulkan build and matching receipts.


**I07-S12 J288 build:**137.101 seconds/zero errors,40 tests,39 payload/45 assembly matching receipts; full Nova route running. Device entry/elite/message/mission assertions still pending.


**I07-S12 J288 exit / J289:** Five genuine loops/count5,385 kills/four transports; actual Moon context activates but source MapZone safe-teleport helper is unavailable and entry guard fails. Full teardown passes; no ending persistence or Moon acceptance. Supply original typed HelperPrefab, preserve source trigger layers, and record the exact existing grounding guard conditions in the full game. J289 whole build/route next; no accepted pointer advances.


**I07-S12 J289 build:**93.389 seconds/zero errors;40 tests/39 payload/45 assembly matching receipts. Full Nova retry starts with actual entry observations; no new device acceptance.


**I07-S12 J289 exit / J290:** Five genuine objectives/count5,386 kills/four transports; helper/trigger fixes remove the previous runtime exception. Moon landing still fails, with original physics advancing and full cleanup/zero unexpected process errors. Exact source SetPosition leaves queued motor moves; this is not yet a measured dirty target. Full J290 game uses original TeleportHelper entry and owned source message68, records actual queued/body/foot/core state, and retains the grounding guard. Build/run the entire route; no accepted pointer advances.


**I07-S12 J290 build:**81.089-second/zero-error Vulkan ARM64 build; matching request/start/terminal receipts,39 payload/45 assembly identities and APK SHA-256 `4a04e3bb19b2d04032acb99c0ed3bde8f2e0565c2cd66a9325bcf8b41e5e7e44`.40 tests pass. Full Nova route retry running; no new Moon or rollback acceptance.


**I07-S12 J290 exit:** Four genuine objectives/transports/421 kills; fifth-boss genuine player loss persists through original XML/ledger with full cleanup/zero unexpected errors. Original teleport works at four entries; Moon test remains unexecuted. Unreachable live actor beneath Sky Meadow reveals omitted original stage MapZone callbacks and diagnostic target starvation. No new accepted pointer.

### I07-S13 — Complete stage out-of-bounds simulation in the whole route

- **ID:** I07-S13.
- **TITLE:** Source out-of-bounds recovery/death and reachable diagnostic combat targets.
- **CONTEXT:** J290's whole game reaches the fifth objective but loses while an unreachable actor delays the driver.
- **OBSERVATION:** First-five generated scenes omit source MapZone scripts; a living actor persists hundreds of metres below the stage.
- **HYPOTHESIS:** Retaining source volumes/callbacks restores normal out-of-bounds lifetime; source-bound target choice prevents diagnostic aim starvation.
- **TASK:** Restore14 original components/shapes/destinations/layers; defer triggers until runtime/entry context and pause during continuous-body transport. Select validation combat targets with the source volume tests; run the complete game.
- **CONSTRAINTS:** No forced kill, altered source health/damage/difficulty/charge or platform success. Physical controls unchanged; retain accepted rollbacks/pins.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing nova_bridge stage transformation, stage/transport/objective boundaries and ignored generated scenes/evidence.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Matching receipts and clean actual source callbacks/entry/transport; whole run continues to Moon with ordinary source combat/progression. No unreachable aim starvation, unexplained new errors or incomplete cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** Actual source volume counts/layers/events, actor positions/health, original teleport queue/ground contacts, first failure/current-process errors, source ending/results and teardown.
- **STATE/JOURNAL UPDATES REQUIRED:** Record integrated exit and next real blocker; milestone/backlog update; privacy/IP review and Conventional Commit.
- **DEPENDENCIES:** J290 integrated evidence; original helper/provider/message context; pinned R2API.Director f539511e/Starstorm2 a9a4badd and exact MapZone source inspected, no implementation copied.


**I07-S13 J291 build:**115.678-second/zero-error Vulkan ARM64 build;40 tests, matching request/start/terminal receipts,39 payload/45 assembly identities and APK SHA-256 `940b384316690846412ca3588c18f203151eb9d651f6f31687bc8e6cba902af2` verified. Full Nova route retry running; source out-of-bounds/Moon/victory acceptance pending.


**I07-S13 J291 exit / J292:** Original enemy respawn fails before gameplay because registered MapZones have disabled colliders/empty bounds and request the unavailable early helper. Full stack/repeated exceptions/failed candidate retained; full cleanup passes. Defer source owner objects instead of colliders; restore only original active volumes, and retain Sky Meadow's two exact scene NetworkIdentity/TeamFilter pairs for original server activation. Build/run the whole game; no source numerical changes, accepted pointer or victory advance.


**J292 full build:**119.123-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities and APK SHA-256 `a4dc21bf35326158ba097d33733262c936491f02338607492527a0a0e65cea16`. Full Nova route retry running; original bounds/scene activation/Moon/victory acceptance pending. I06/I03 remain immutable.


**J292 device exit:**834.471 reported gameplay seconds, three genuine boss/natural-charge/exit loops and three completed recovered transports/count3,207 kills. Original source-enabled bounds and original active distinctions pass through Abyssal; Rallypoint water remains inactive. Genuine fatal combat health-36.56; no source MapZone exit/teleport at death and actual player near recovered ground. Original StandardLoss/server/client/RunReport/XML/ledger persist:357 fields,53711 dealt/1309 taken,847.204 original stopwatch seconds/five acquired item entries/priorRuns6. Full source/world/model/results cleanup and zero unexpected current-process runtime errors pass. Sky scene identities/Moon/victory unexecuted; I06/I03 remain unchanged, Nova stopped/asleep.

### I07-S14 — Keep the integrated validation player moving through real combat

- **ID:** I07-S14.
- **TITLE:** Source-grounded diagnostic combat navigation in the complete offline route.
- **CONTEXT:** J292 restores stage bounds and three source transports; actual Abyssal combat kills Commando before fourth completion.
- **OBSERVATION:**327/332 last40-second samples have zero input; two source guards each deal190.08 damage; no source bounds teleport or runtime exception.
- **HYPOTHESIS:** Ground-to-ground walkability and waiting-phase evasion avoid the driver's stationary combat while retaining original gameplay.
- **TASK:** Keep the whole composition, correct input-only terrain selection/nearby guard targeting, build/run the full Nova route and classify the next real failure.
- **CONSTRAINTS:** Inherited privacy/IP/platform/storage/ownership/pin rules; no health/damage/cooldown/progression writes, forced kill or physical input changes.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedWorld/TeleporterWorld partial boundaries, small current motion observations and ignored candidate/config/evidence.
- **TEST COMMAND:** Fresh `./dev preflight`, `./dev test`, forced Vulkan build and `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Matching build/assembly/payload receipts; actual driver moves with safe source ground while source combat/route continue without unexplained errors. Moon/victory need actual execution.
- **FAILURE EVIDENCE TO CAPTURE:** Actual current ground/destination/blocked input, actor damage/position/state, original results/cleanup, full exceptions and next original first failure.
- **STATE/JOURNAL UPDATES REQUIRED:** J293 build/device outcome, concise state and milestone/backlog; accepted pointers advance only at capability acceptance.
- **DEPENDENCIES:** J292 full-world archive; I06/I03 rollback unchanged.


**J293 full build:**146.005-second/zero-error Vulkan ARM64 build;40 tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `780f90f9ce51329a9f461ff146361646a24af9a7c04e07b488673b30016361df`. Full Nova route retry running; motion/guard targeting/Sky/Moon/victory require actual device outcomes. I06/I03 unchanged.


**J293 device exit / hypothesis revision:**782.032 reported gameplay seconds,192 kills/three genuine objectives and transports. Original StandardLoss/server/client/RunReport/XML/ledger persist:357 fields,49892 dealt/1016 taken,795.294 original stopwatch seconds/six acquired item entries/priorRuns7. Full cleanup/zero unexpected current-process errors pass. Ground-to-ground steering and actual Guard selection work through the first three stages, but Abyssal combat input stops immediately: motion/target remain stale from Rallypoint, nearby source Beetles each deal216 damage. Grounded entry is inside one original TriggerExit volume and outside the alternative above-cave volume. The adapter incorrectly requires all exit volumes; exact original Util accepts any. This supersedes terrain-only diagnosis for the Abyssal loss. Sky/Moon/victory remain unexecuted; I06/I03 unchanged, Nova stopped/asleep.

**I07-S13/S14 J294 continuation:** Exact original union semantics replace the failed all-volume test. Command remains forced full Vulkan build then `./dev prototype --action movement-batch-run`. Require actual Abyssal combat input and original grounded bounds; retain full route/Moon/result content, candidate rejection observations and failed J293 evidence. No source numerical change or accepted pointer advance.


**J294 full build:**82.371-second/zero-error Vulkan ARM64 build;40 tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `8b0772925ad7477c5667cabd4616d4aeb9fdfb2ecd700fafa021913bef439c5b`. Full Nova route retry running; actual original bounds/Abyssal combat/Sky/Moon/victory outcomes pending. I06/I03 unchanged.


**J294 device interruption:**1162.040 reported gameplay seconds/127 kills, one complete source boss/natural-charge/exit/transport. Wetland's second boss and natural charge finish, but return navigation remains blocked below the teleporter: original graph reports reachable/three nodes, repeated recovery, source exit Idle/unselected. No unexpected current-process exception detected before interruption. Owned host runner interrupted; final report/captures retained, app force-stopped/selection removed/Nova asleep. No source teardown, second exit, ending/persistence, Abyssal or later acceptance. I06/I03 unchanged.

### I07-S15 — Original local navigation in the complete offline route

- **ID:** I07-S15.
- **TITLE:** Reach original interaction and mission targets using original navigation output.
- **CONTEXT:** J294 completes first transport and defeats/charges Wetland, then stalls below its teleporter.
- **OBSERVATION:** Reachable three-node graph; repeated recovery, nonzero input but little velocity, no active enemy or runtime exception; source exit remains Idle/unselected.
- **HYPOTHESIS:** Exact AI foot-reference and original local avoidance/frustration satisfy the physical navigation contract omitted by straight waypoint input.
- **TASK:** Integrate original LocalNavigator input production into the full world, retain source limits, build/run the entire route and inspect its next actual blocker.
- **CONSTRAINTS:** Inherited pin/IP/privacy/legal/storage/ownership boundaries; no source movement/velocity/graph/collider edits, forced interaction/progression or physical mapping change.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedWorld/IntegratedStage boundaries, specific navigation observations and ignored full-game candidate/receipts.
- **TEST COMMAND:** Live `./dev preflight`, `./dev test`, forced full Vulkan build and `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual ordinary-input travel/selection/original exits continue across recovered terrain without unexplained runtime errors; original bounds/ground/continuity and full teardown agree. Later Moon/victory need execution.
- **FAILURE EVIDENCE TO CAPTURE:** Source foot reference/path nodes/minimum jumps/local avoidance/frustration, actual input/position/velocity/ground, interaction/exit/mission state and current exceptions.
- **STATE/JOURNAL UPDATES REQUIRED:** J295 build/device exit and next first failure; concise state/backlog/milestones; I06/I03 remain rollback until new capability acceptance.
- **DEPENDENCIES:** Preserved J294 full route and interrupted navigation evidence.


**J295 full build:**84.755-second/zero-error Vulkan ARM64 build;40 tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `898a6522164aa4706357819e34de22791b385a83fee00d65d2b70767e874a76f`. Whole Nova route retry running; original local navigation/exit/Abyssal/Sky/Moon/victory acceptance pending. I06/I03 unchanged.


**J295 device exit:**319.649 reported gameplay seconds,57 kills and one genuine objective/transport at original clear count1. Wetland ends in genuine StandardLoss while the diagnostic driver focuses on a naturally ejected pickup without return fire; nearby base Beetles deal115.2/144 damage. Original LocalNavigator runs without exceptions and reports obstruction/recovery output, but the second teleporter return is not reached. Original server/client/RunReport/XML/ledger persist:357 fields,11509 dealt/412 taken,332.696 original stopwatch seconds,three acquired item entries/priorRuns8. Full source/world/model/results cleanup passes with zero unexpected current-process errors. Failed assessment remains separate; I06/I03 unchanged, app stopped/Nova asleep. Next correct input-only self-defence during loot/objective travel in the entire composition.

### I07-S16 — Whole-game defence while approaching interactions

- **ID:** I07-S16.
- **TITLE:** Preserve ordinary self-defence during loot and objective travel.
- **CONTEXT:** J295 original local navigation executes cleanly, but Wetland pickup-focused input ends in genuine death.
- **OBSERVATION:** Nearby base Beetles deal115.2/144 damage while a pickup remains targeted; one source transport and original loss/results/cleanup pass.
- **HYPOTHESIS:** Input-only threat priority before travel prevents the driver's unopposed contact damage without changing source gameplay.
- **TASK:** Integrate defence across loot/reward/teleporter and Moon battery travel, then build/run the whole route and fix its next real blocker.
- **CONSTRAINTS:** Inherited privacy/IP/platform/storage/ownership/pin rules; preserve original selector priority, damage/health, progression, physics and physical controls.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedWorld/TeleporterWorld/MoonMission boundaries, narrow defence observations and ignored full candidate/evidence.
- **TEST COMMAND:** Live `./dev preflight`, `./dev test`, forced full Vulkan build and `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual travel defence and subsequent original interaction/route continue without unexplained runtime failures; Moon/victory require execution.
- **FAILURE EVIDENCE TO CAPTURE:** Travel/defence target, source threat/input/health, navigation/selector state, next actual runtime exception, ending/results/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J296 build and device exit, concise state/backlog/milestones; no acceptance from compilation/partial execution.
- **DEPENDENCIES:** J295 whole composition and actual loss; I06/I03 rollbacks retained.


**J296 full build:**91.921-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `dee903788a18b2ca38b2f1dd8c0725120fdf8198dd01b542e791aeb8905bddf6`. Complete Nova route retry running; travel defence/original interactions/Moon/victory require actual device outcomes. I06/I03 unchanged.


**J296 device interruption:**871.543 reported gameplay seconds/123 kills, first genuine source boss/charge/exit/transport plus Wetland boss defeat and natural full charge. Original graph/local navigation reaches the lower return area but circles the same waypoint near(31.80,-143.95,14.78) with no enemies and exit Idle/unselected. Movement-based progress continually resets; source local frustration/jumpSpeed remain zero despite no net waypoint progress. Reviewed capture and source PathFollower/LocalNavigator distinguish the input-driver omission; no unexplained current-process error. Current travel-defence counter remains zero, so this run does not independently establish that branch. Owned runner interrupted, report/captures retained, app stopped/selection removed/Nova asleep. No source teardown, second exit, ending/persistence or later gate acceptance; I06/I03 unchanged.

### I07-S17 — Recover whole-game travel from circling without progress

- **ID:** I07-S17.
- **TITLE:** Request ordinary player jumps when original local avoidance circles.
- **CONTEXT:** J296 defeats/charges Wetland but cannot return to its original exit.
- **OBSERVATION:** Same lower waypoint for over100 seconds, no enemies, source local jump output zero and movement-only progress repeatedly resets; no runtime errors.
- **HYPOTHESIS:** Waypoint-distance progress and ordinary recovery jump input let original physics traverse the measured obstacle.
- **TASK:** Correct integrated diagnostic travel progress, retain original navigation/input contracts, rebuild and run the full route.
- **CONSTRAINTS:** Inherited safety/privacy/IP/platform/pins; no direct movement/velocity, graph/collider/physics edits, forced interaction or progression.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedWorld input driver and narrow navigation observations, ignored full candidate/evidence.
- **TEST COMMAND:** `./dev preflight`, `./dev test`, forced full Vulkan build, `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual original input/physics reach the exit and continue route without unexplained failures; source ending/cleanup and later Moon/victory require execution.
- **FAILURE EVIDENCE TO CAPTURE:** Waypoint distance/progress/recovery jump, local navigation, source geometry/input/ground, selector/exit and actual next first failure.
- **STATE/JOURNAL UPDATES REQUIRED:** J297 build/device exit; concise state/backlog/milestones, no capability acceptance from compilation or partial route.
- **DEPENDENCIES:** Preserved J296 blocked full-world run and current I06/I03 rollbacks.


**J297 full build:**82.900-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `fd0cf2bd2a4f5a876d412335ca99d35358fd92c124c70ede16ed18a016be31c3`. Whole Nova route retry running; stalled-travel jump/second exit/later Moon/victory acceptance pending. I06/I03 unchanged.


**J297 device interruption:**973.601 reported gameplay seconds/126 kills, first genuine full objective/transport plus Wetland boss defeat and full charge. Pickup travel defence actually executes20 frames; progress-sensitive ordinary jump requests execute276 frames and advance the prior blocked waypoint. The next rising-floor waypoint still stalls with reversed local movement and no enemies. Read-only exact-editor geometry inspection finds the actual source floor at the waypoint with walkable normals and a clear approach; source jump pads are elsewhere. Exact original Walker.Combat ChaseMoveTarget sets allowWalkOffCliff=true and offsets foot target to body reference; adapter incorrectly fixed false. Source local cliff test casts down from current-height prediction and can reject rising terrain. Zero unexpected current-process errors; owned runner interrupted and app/selection stopped/removed, Nova asleep. No source teardown, second exit, ending/persistence or later acceptance. I06/I03 unchanged.

### I07-S18 — Original pursuit configuration through the complete game

- **ID:** I07-S18.
- **TITLE:** Use source chase navigation instead of a fixed circling guard.
- **CONTEXT:** J297 recovery jumps advance one Wetland waypoint, but the next rising-floor approach stalls.
- **OBSERVATION:** Original local output reverses the intended direction, no enemies/runtime errors; host source floor/approach are clear and source jump pads elsewhere. Exact Walker.Combat chase uses allowWalkOffCliff=true.
- **HYPOTHESIS:** Matching original chase target reference and policy preserves ordinary path traversal without changing physics.
- **TASK:** Correct the public navigator configuration, retain full route/Moon/results, build/run the complete Nova game and inspect its next real blocker.
- **CONSTRAINTS:** Inherited safety/privacy/IP/platform/pins; original path/physics/bounds/jump power/input/selector/exit rules unchanged.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedWorld navigation configuration/flag observation and ignored candidate/build/device evidence.
- **TEST COMMAND:** `./dev preflight`, `./dev test`, forced full Vulkan build, `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual original input/physics reach Wetland exit and continue the full route without unexplained failures; later Moon/victory need execution.
- **FAILURE EVIDENCE TO CAPTURE:** Actual chase flag/local direction/ground/path/position, source trigger/selector/exit, current exceptions and original ending/results/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J298 build/device exit, concise state/backlog/milestones; no acceptance from compilation or partial route.
- **DEPENDENCIES:** Preserved J297 full-world failure/source/geometry inspection; I06/I03 rollbacks unchanged.


**J298 full build:**83.200-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `7ab65850a0b7f0521821465162354976be37089fefa4d2012806702499f73145`. Complete Nova route retry running; original chase/second exit/Moon/victory need device execution. I06/I03 unchanged.


**J298 live integrated progress:** Wetland boss/charge/reward/exit and second actual source transport complete. Same original body/master/inventory reach Rallypoint Delta; current chase flagtrue and zero runtime errors. Prior uphill return blocker is cleared under original physics. Full-route/Moon/ending/cleanup acceptance remains pending; ignored current report and reviewed Rallypoint capture retained. I06/I03 unchanged.


**J298 device exit:**1516.3 reported gameplay seconds/412 kills, all five genuine source boss/charge/reward/exit objectives and original count5; four completed transports. Wetland traversal, Abyssal bounds/combat and Sky network MapZones pass in the full route. Actual Moon/catalog identity activates, but grounding fails before fifth transport/mission Start. Full source/world/model/results cleanup and zero unexpected current-process errors pass; no original ending/XML persistence or Moon/victory acceptance. Nova stopped/asleep; I06/I03 unchanged.

**Moon hypothesis revised:** After original teleport, the queued target matches the intended landing exactly; stale queue is rejected. The next sample is displaced below the platform and source MapZones recover six times. Read-only recovered-scene inspection at that point finds a source layer20 non-trigger ambient sphere. Actual Commando capsule penetration yields220.846 metres toward(0.3484,-0.9369,0.0286), projecting to(1181.459,-487.432,1186.782), matching device displacement. Runtime geometry had promoted this post-process collider to World. Original queue/teleport/physics are retained; correct Moon layer ownership rather than weakening the entry guard.

### I07-S19 — Correct complete Moon collision layer integration

- **ID:** I07-S19.
- **TITLE:** Retain original Moon physics/presentation/interaction layer roles.
- **CONTEXT:** J298 completes five genuine objectives, then Moon entry fails grounding.
- **OBSERVATION:** Correct queued teleport target; ambient sphere promoted from source PostProcess layer to World reproduces the device displacement by220.846 metres.
- **HYPOTHESIS:** Preserving source Moon layers removes the erroneous gameplay collision and permits original landing/mission execution.
- **TASK:** Preserve Moon object layers, retain full route/mission/results, rebuild/run and fix the next real integration blocker.
- **CONSTRAINTS:** Inherited privacy/IP/platform/storage/pins; keep original collider geometry/enabled state, physics, queue/teleport, entry guard and progression.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing StageGeometry layer adapter/count observations, ignored full candidate/evidence.
- **TEST COMMAND:** `./dev preflight`, `./dev test`, forced Vulkan build, `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual Moon landing and original mission run without unexplained failures; complete victory/ending/cleanup require execution.
- **FAILURE EVIDENCE TO CAPTURE:** Layer counts/entry queue/position/ground/bounds, source mission/actor/interaction state and first current exception.
- **STATE/JOURNAL UPDATES REQUIRED:** J299 build/device exit; concise state/backlog/milestones; no acceptance from compilation or partial route.
- **DEPENDENCIES:** Preserved J298 full route and matching host/device penetration evidence; I06/I03 immutable rollback.


**J299 full build:**81.268-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `43f3372608270898de2d8bbba519a11c497dee0db5812e1a5d8bb7d3d30f945d`. Complete Nova route retry running; Moon source layers/landing/mission/victory require device execution. I06/I03 unchanged.


**J299 live Moon progress:** All five genuine source objectives/count5 and five actual transports complete. Original teleport target settles on recovered Moon geometry at the intended landing; source bounds pass, queued move resolves, no map-zone recovery teleport.1548 world/49 non-world non-trigger colliders retain original Moon roles. Original population initializes with no unexpected current-process errors; battery travel runs. Mission completion/victory/ending/full cleanup acceptance remain pending; I06/I03 unchanged. Ignored current report and Moon capture preserved.


**J299 device interruption:**1997.889 reported gameplay seconds/411 kills, all five genuine source objectives/count5 and five transports. Actual original Moon landing, bounds, queued-move resolution and population initialization pass; four source batteries remain inactive. Human path to the selected Soul battery is unreachable/zero waypoints and direct fallback repeatedly enters terrain. Original Arena gate setter is present; no unexplained current-process runtime errors. Owned runner intentionally interrupted; reports/captures retained, app stopped/selection removed/Nova asleep. No source teardown, ending/persistence, battery completion or victory acceptance. I06/I03 unchanged.

### I07-S20 — Guide player travel where the Moon monster graph is incomplete

- **ID:** I07-S20.
- **TITLE:** Normal sprint and terrain steering in the complete Moon route.
- **CONTEXT:** J299 reaches actual Moon but cannot navigate to inactive batteries.
- **OBSERVATION:** Valid source endpoints; incomplete Human topology/path and direct travel repeatedly blocked by terrain. Original Arena gate setter exists; no runtime exception.
- **HYPOTHESIS:** Player input using ordinary sprint and recovered terrain can traverse beyond the incomplete monster route without changing source simulation.
- **TASK:** Integrate input-only terrain lookahead in the complete game, build/run Nova and fix its next real blocker.
- **CONSTRAINTS:** Inherited safety/privacy/IP/platform/pins; one original jump, source physics/stats/colliders/graphs/gates/mission/physical mapping preserved; no fabricated completion.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedWorld travel/observations and stage reset; ignored candidate/source analysis/build/device evidence.
- **TEST COMMAND:** `./dev preflight`, `./dev test`, forced Vulkan build, `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual battery approach/interaction/mission advances through original input and physics without unexplained failure; victory/ending/full cleanup require execution.
- **FAILURE EVIDENCE TO CAPTURE:** Source reachable flag, speed/terrain choices/position/ground, selector/battery state, first current exception and actual ending/results/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J300 build/device exit, concise state/backlog/milestones; no pointer from partial or interrupted route.
- **DEPENDENCIES:** Preserved J299 full-route failure, source topology/terrain/jump analysis; I06/I03 immutable rollback.


**J300 full build:**87.073-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `656970c2f8ab81d38e773cd5c25fc18535b3a7e85c11253f456b9237d91f35fc`. Entire Nova route retry running; ordinary sprint/terrain traversal/battery/mission/victory need device execution. I06/I03 immutable; no partial capability pointer.


**J300 device interruption:**870.776 reported gameplay seconds/137 kills/one genuine source transport. First objective and Wetland boss/natural charge complete; source return path is reachable but the player remains below a waypoint about six metres higher for over90 seconds. No unexplained current-process runtime errors. Moon terrain candidate is unexecuted. Owned runner interrupted, captures retained, app stopped/selection removed/Nova asleep; no source teardown, second exit, ending/persistence or later acceptance. I06/I03 remain immutable.

### I07-S21 — Recover stalled travel throughout the composed route

- **ID:** I07-S21.
- **TITLE:** Apply ground steering to a stalled original waypoint.
- **CONTEXT:** J300 full route ends at a different Wetland return approach before Moon.
- **OBSERVATION:** Source path reachable; original ordinary input remains below a higher waypoint for over90 seconds, no runtime error.
- **HYPOTHESIS:** Ground steering can find an alternate approach while original physics and graph intent remain authoritative.
- **TASK:** Extend existing input guidance to stalled travel, rebuild/run the entire route and classify its next real blocker.
- **CONSTRAINTS:** Inherited privacy/IP/platform/storage/pins; preserve source graph/gates/colliders/stats/jump/interaction/progression and physical mapping.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedWorld terrain trigger/goal/window and stage/cleanup reset, ignored full-game evidence.
- **TEST COMMAND:** `./dev preflight`, `./dev test`, forced Vulkan build, `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Real input/physics traverse the blocked return and continue toward batteries/mission; victory/results/full cleanup need execution.
- **FAILURE EVIDENCE TO CAPTURE:** Source waypoint/ground/position/reachability, terrain target/window/counts, selector/exit, first current error and original ending/results/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J301 build/device exit and concise state/backlog/milestones; no pointer advance from partial route.
- **DEPENDENCIES:** J300 full-route failure plus retained J299 original Moon landing; I06/I03 immutable rollback.


**J301 full build:**81.401-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `38a55a54f16867bce8b33f1dd3f4d0a08610537a586b53acb0cec03e90311cc0`. Complete Nova route retry running; stalled-travel recovery/Moon/battery/mission/victory require execution. I06/I03 remain immutable rollback.


**J301 live return progress:** Wetland boss/natural charge/reward/exit and second actual source transport complete.38 terrain-recovery frames/zero blocked terrain searches observed, followed by resumed source navigation; actual Rallypoint body/master/inventory and current source runtime remain stable. Integrated stalled-return correction has device evidence. Moon/battery/victory/ending/full cleanup acceptance remain pending; no new I07 pointer, I06/I03 immutable. Ignored current source report and reviewed Wetland capture retained.


**J301 device interruption:**1894.750 reported gameplay seconds/432 kills, all five genuine source objectives/count5 and five actual transports. Wetland terrain recovery clears the prior return; Moon landing/source population pass. Original four batteries remain inactive. Input repeatedly selects nearby higher ground while actual body remains near the entrance bridge; recovery jump requests do not resolve it. Source reachable flag remains false. Current-process errors zero, current Moon capture reviewed. Owned runner interrupted, evidence retained, app stopped/selection removed/Nova asleep. No source teardown, battery completion, ending/persistence or victory acceptance; I06/I03 unchanged.

### I07-S22 — Body-width terrain guidance and live integrated control

- **ID:** I07-S22.
- **TITLE:** Resolve the Moon bridge approach in the running complete game.
- **CONTEXT:** J301 passes five source stages/transports, then cannot reach batteries.
- **OBSERVATION:** Center-line ground choices stay above a stationary body; recovery requests fail, no current runtime error. Two approaches have failed at this boundary.
- **HYPOTHESIS:** Body-width clearance/rising-ground sampling improves guidance; source motor/state/button observations and physical takeover separate remaining input and physics failures.
- **TASK:** Integrate the correction/observations/takeover in the complete game, build/run the full route, inspect its next actual blocker and continue.
- **CONSTRAINTS:** Inherited privacy/IP/platform/storage/pins; original physics/jump/stats/graph/gates/colliders/interactions/progression authoritative, no forced ending; preserve completed live stages during takeover.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedWorld terrain/HUD/source observations; ignored full candidate/build/device evidence.
- **TEST COMMAND:** `./dev preflight`, `./dev test`, forced Vulkan build, `./dev prototype --action movement-batch-run`; physical takeover only at the actual integrated gate when needed.
- **PASS CONDITION:** Actual body/input traverses toward original batteries; original mission/boss/escape/ending/results/full cleanup require execution. Takeover needs same live world/master/inventory continuity.
- **FAILURE EVIDENCE TO CAPTURE:** Ground/state/velocity/jump/button/capsule/terrain observations, current visuals/errors, original mission/ending/results and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J302 host repair/build/device outcomes, concise state/backlog/milestones, no full-route pointer from partial or interrupted play.
- **DEPENDENCIES:** Preserved J301 full-route/Moon failure and reviewed capture; I06/I03 immutable rollback.


**J302 full build:**81.026-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `52f2275fd793e8ab4d9c4be7e0be1f29db41411ba6725ac8b0f04edd58a09fc3`. Complete Nova route retry running; terrain clearance/live motor/takeover/Moon/mission/victory outcomes pending. I06/I03 unchanged; no new capability pointer.


**J302 live takeover UI:** During the complete Wetland run, actual Nova taps switch to physical mode and back to automation. Current original body/master IDs and transport count stay unchanged; input neutralization and reported mode changes pass. Local before/active/resumed source records and active-button capture retained. This verifies mode switching/continuity, not human physical operation during takeover. Full route/terrain/Moon/mission/victory acceptance remain pending; I06/I03 unchanged.


**J302 live Moon / physical comparison pending:** All five genuine original objective/exit/transport loops pass again;429 kills, original Moon landing/population and four inactive batteries. Torso clearance moves beyond the previous wall contact, but input guidance then circles the bridge without reaching the first battery. Live original GenericCharacterMain/stable grounding/jump count0 and normal velocity distinguish navigation from a broken motor or missing state. Zero unexpected current-process errors. Physical takeover is active in the same live body/master/run; readiness requested for whole-Moon traversal. Nova display verified asleep while waiting, app process retained. No battery/Mithrix/escape/victory/ending/full cleanup acceptance; I06/I03 immutable, no new pointer. Ignored current reports/capture/pending-input record retained.


**J302 physical exit:** User confirms character movement during takeover but reports camera snapping to one direction. Live camera records879 nonzero physical look frames; replay still invokes DiagnosticDirection unconditionally after physical input, overwriting its orbit. Preserved same-process physical report/capture at2348.158 gameplay seconds,429 kills/five genuine objectives/transports. Current-process logs after physical travel additionally expose missing original EntityStates.FlyState registration and repeated AkSoundEngine StopPlayingID exceptions in LunarWisp.ChargeLunarGuns.OnExit; the earlier zero-error observation predates these failures. Four batteries remain inactive; no ending/persistence/full source teardown or new capability pointer. Owned runner interrupted, app stopped/selection removed/Nova asleep; I06/I03 immutable. Revisit after camera ownership, measured flight-state registration and silent native-stop correction.

### I07-S23 — Physical camera ownership and lunar silent exits

- **ID:** I07-S23.
- **TITLE:** Keep manual camera control and unblock actual Moon enemy transitions.
- **CONTEXT:** J302 passes five stages/transports; physical comparison exposes replay camera override and original lunar dependencies.
- **OBSERVATION:** User movement works/camera snaps;879 physical look frames, missing FlyState and repeated charge-exit native sound-stop exceptions.
- **HYPOTHESIS:** Correct input-mode ownership and measured catalog/silent-call contracts let the complete world continue naturally.
- **TASK:** Integrate camera guard, original FlyState identity and narrowly conditional lunar sound stops; build/run complete route, inspect next real failure, then physical Moon traversal.
- **CONSTRAINTS:** Inherited input/IP/privacy/storage/platform/pins; original simulation, attack/exit/cleanup/progression authoritative; no fabricated audio/native/ownership success; I06/I03 unchanged.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** NovaInputBoundary, TeleporterWorldBoundary, existing OptionalPresentationGuard and ignored full candidate/build/runtime evidence.
- **TEST COMMAND:** `./dev preflight`, `./dev test`, forced Vulkan build, `./dev prototype --action movement-batch-run`; same-world physical takeover when ready.
- **PASS CONDITION:** Physical camera retains right-stick orientation, original Moon flight/attack transitions run without unavailable native audio calls; original batteries/boss/escape/ending/persistence require execution.
- **FAILURE EVIDENCE TO CAPTURE:** Actual camera orbit/raw input/current source state and missing indexes; current-process native/managed failures, Moon progress and original cleanup/ending.
- **STATE/JOURNAL UPDATES REQUIRED:** J303 build/device/physical exit, concise state/milestones; no partial capability pointer.
- **DEPENDENCIES:** Preserved J302 physical report/errors, exact source/catalog and optional presentation contracts; immutable I06/I03.


**J303 full build:**85.741-second/zero-error Vulkan ARM64 build;40 tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `dfe88cffd56bf6a2ab644ed331068c5b9d97469a359a4a62e44c4732cdb82884`. Full Nova route/physical camera/original Moon flight and attack exits remain pending device execution; I06/I03 unchanged, no new capability pointer.


**J303 host dispatch correction:** The existing3600-second full-route host cap rejects the new4740-second bound before device construction; preserved rejection evidence. Raise only the composed teleporter-route cap to finite5400 seconds so physical Moon navigation fits after automatic travel. Shorter probe caps remain unchanged;40 safety tests pass again, existing APK/build identities unchanged. Full device acceptance pending.


**J303 physical camera acceptance:** In the running complete first stage, the user confirms right-stick camera turns freely in all directions and retains the chosen angle after release.172 nonzero physical look frames and changed yaw/pitch corroborate input. Same process and actual nonzero source body/master identities survive takeover/resume; zero current-process errors. Camera correction has real-device evidence. Full five-stage route/Moon flight/attack/mission/ending acceptance remains pending; no I07 pointer, I06/I03 immutable.


**J303 unattended exit:** Five genuine objectives/transports and383 kills complete; original Moon landing/population pass. Automatic guidance circles the temple floor for several minutes; current original main state, grounding and health remain stable, zero current-process errors. No original lunar actor attack executes in this observed Moon interval, so the new native-stop guards have no device execution acceptance yet. Physical camera acceptance remains valid. Read-only source walk/fall/capsule-jump analyses do not establish a complete route; a paired3416-ray inspection identifies519 locations where highest/nearest valid ground differ at the same height/window. Original elevator jump volumes are inactive until charging. Scene inspection emits dangling LOD references to intentionally omitted ParticleSystemRenderer components (class199), not C# compilation failures; source/destination IDs and observed logs retained locally. Owned runner interrupted at1710.314 seconds, app stopped/selector removed/Nova asleep; no ending/persistence/full source cleanup or new I07 pointer. I06/I03 immutable.

### I07-S24 — Nearest valid floor in full-world navigation

- **ID:** I07-S24.
- **TITLE:** Avoid selecting overlapping higher geometry as the walking floor.
- **CONTEXT:** J303 full five-stage route passes and physical camera works; unattended Moon navigation circles the temple.
- **OBSERVATION:** Paired3416 source rays have519 highest-versus-nearest differences; bounded ordinary movement searches do not prove a full route.
- **HYPOTHESIS:** Nearest valid foot-height selection improves the existing terrain guide without changing simulation.
- **TASK:** Integrate nearest-height ground selection and bounded-hit observations, build/run complete route, classify the next real Moon failure and continue unattended.
- **CONSTRAINTS:** Inherited public/IP/input/platform/storage/pins; original physics/geometry/stats/authority/interactions/progression unchanged; no forced scene or mission completion.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedWorld terrain sampler/report; ignored complete candidate/build/device evidence.
- **TEST COMMAND:** `./dev preflight`, `./dev test`, forced Vulkan build, `./dev prototype --action movement-batch-run`.
- **PASS CONDITION:** Actual source body progresses across the Moon approach with correct ground selection and no hit overflow/unknown error; original mission/ending/results/full cleanup need execution.
- **FAILURE EVIDENCE TO CAPTURE:** Nearest/lower selections, source floor/capsule/state/position and interaction target, overflow, actual lunar actors/native errors and ending/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J304 build/device exit, concise state/milestones; no new I07 pointer from partial or interrupted travel.
- **DEPENDENCIES:** J303 full route and physical camera evidence, paired source-height inspection; I06/I03 immutable.


**J304 full build:**79.831-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `759a7a11564d36658e1d2b2154ffafc4f11dfcae55698b082d11a96f21b0a300`. Complete unattended route/nearest-floor/Moon/ending acceptance pending; I06/I03 unchanged, no new capability pointer.


**J304 unattended exit:**1465.499 gameplay seconds,385 kills and five genuine objectives/transports; original Moon landing/population pass. Nearest-height selection executes2841 times, overflow0, but the last-minute battery distance remains991.616→989.491 metres (closest977.421), with four batteries inactive. Current-process errors zero; capture shows original character and temple geometry. No original lunar attack executes in this interval, so native-stop execution remains unproven. Read-only original ComputePath against active recovered collision finds a21-waypoint reachable bridge approach using the recorded original sprint11.9/jump3.75; full paths to all16 serialized battery candidates fail from the tested entrance points. These host observations do not prove device traversal. Current report/capture/errors and attempted analysis remain ignored locally. Owned runner interrupted, app stopped/selector removed/Nova asleep; no mission/ending/persistence/full source cleanup or I07 pointer. I06/I03 immutable. Revisit with partial original path guidance before terrain fallback.

### I07-S25 — Follow reachable original Moon approaches

- **ID:** I07-S25.
- **TITLE:** Original partial path guidance inside the complete run.
- **CONTEXT:** J304 completes five stages but greedy Moon steering circles the temple.
- **OBSERVATION:** Actual nearer-floor choices2841/overflow0; four batteries inactive, zero current-process errors. Original solver finds a closer reachable bridge node with unchanged recorded limits.
- **HYPOTHESIS:** Retaining the source-reachable path portion enables ordinary traversal before local terrain steering takes over.
- **TASK:** Integrate source approach selection into automatic Moon travel; force-build and execute the complete composed route on Nova.
- **CONSTRAINTS:** Normal original movement/input only; no source graph, physics/stats, mission/progression or platform identity edits. Accepted camera and I06/I03 immutable; user input unnecessary.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored IntegratedWorldBoundary, ignored full stage/config/recipe/archive/build/device evidence, state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Actual source partial path guides the continuing original body beyond the temple; complete mission/ending remains a distinct device gate. Inspect candidate count/query time, original movement, current-process errors and first blocker.
- **FAILURE EVIDENCE TO CAPTURE:** Full report, partial path/node/waypoints/timing, body/master/authority/grounding, current-process errors and screenshot; no pointer from interrupted travel.
- **STATE/JOURNAL UPDATES REQUIRED:** J305 build/device exit, concise state/milestones; preserve all failed evidence.
- **DEPENDENCIES:** J304 complete route and paired ground observations, active-collision original graph comparison; I06/I03 immutable.


**J305 full build:**111.655-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `39eb9224a2c21d19fc6de17a112a866440f25fc9323357bdfd8f873d4ebc3bf0`. Complete unattended route/original partial-path/Moon/ending acceptance pending; I06/I03 unchanged, no new capability pointer.


**J305 checkpoint feasibility, user-directed bounded review:** Prefer a small verified restore of genuine stage-entry state over repeated full-route replay. Exact original Run.OnSerialize only carries its declared network values; it omits run/stage RNG and the complete player simulation. Current live reports/ending XML do not provide a server restore. Pinned ProperSave d20c6c8e RunData/RunRngData/PlayerData/Saving/Loading demonstrates pre-stage RNG and additional run/rules/masks/master/inventory/stat/team lifecycle restoration through desktop hooks and NetworkUser loading. It is not an Android IL2CPP drop-in; no source copied or installed. A new equivalent server restore would exceed the requested small bounded effort. Retain the real route, without invented Moon progression, and revisit only with a concrete narrow restoration seam and genuine entry/equivalence validation. The current Nova run remains uninterrupted; no checkpoint capability claimed. Ignored stage-checkpoint-feasibility record retained.


**J305 device exit:** Original player death ends the unattended run on Sky Meadow at1867.985 gameplay seconds after four genuine teleporter/exit/transports and440 kills. Two source Queens remain, total health13366.714/16800; charge1 does not skip boss defeat. Ten live actors remain. No current-process errors or message failures. Original Commando death/ragdoll/body destruction, StandardLoss server/client ending, report generation/save/reload and source cleanup pass; persisted Android result retained. This is a combat defeat, not a native crash. The Moon partial-path candidate did not execute on device in this attempt and remains unaccepted. Nova asleep after completion; I06/I03 unchanged, no I07 pointer. Revisit unattended target visibility/approach before replaying the genuine route.

### I07-S26 — Visible combat targets in the complete run

- **ID:** I07-S26.
- **TITLE:** Unattended combat firing lines and original approach paths.
- **CONTEXT:** J305 ends through original defeat/results/cleanup after four genuine stage loops.
- **OBSERVATION:** Sky Meadow two original bosses survive while adds recur; driver does not measure firing lines and puts distant adds before bosses. Current-process errors zero; Moon change remains device-unexecuted.
- **HYPOTHESIS:** Visible hurtbox priority and source navigation approach improve genuine combat progress without altering simulation.
- **TASK:** Integrate target visibility/approach and its structured observations in the running whole game; force-build and replay the genuine route on Nova.
- **CONSTRAINTS:** Input only; preserve original damage/health/RNG/items/rules/directors/physics/authority/progression and physical camera. No forced combat outcome or stage skip; I06/I03 immutable.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored TeleporterWorldBoundary/IntegratedWorldBoundary; ignored stage/config/recipe/build/device evidence; concise state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Actual visible-target and original approach evidence; genuine combat/stage progress without new errors. Moon path and complete mission/ending remain separate device gates.
- **FAILURE EVIDENCE TO CAPTURE:** Aim endpoints/visibility/selected identity/distance, approach/grounding/movement, boss/add damage and first real failure, current-process logs/capture, ending/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J306 build/device exit and state/milestones; retain failed attempts and no pointer from incomplete play.
- **DEPENDENCIES:** J305 original defeat/report/cleanup, exact source/prior-art review, accepted physical camera and I06/I03.


**J306 full build:**89.601-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `2a13ed577c2892566d88d63c1e5241be7b9c18bfe9e6e1a8c53951690c29e1c1`. Complete unattended route/visible hurtbox/original combat approach/Moon partial-path/ending acceptance pending. I06/I03 unchanged, no new capability pointer.


**J306 device exit:**758.388 gameplay seconds,133 kills, one genuine teleporter reward/exit/transport. Actual visible boss targeting and original damage pass on device; Wetland Queen reaches89.589 health, then source level growth increases max health to3360. The last several minutes leave655.471 health unchanged. With only two live enemies, the driver selects an occluded Beetle rather than the unfinished Queen; source full path is reachable but target changes redirect it. Capture shows normal original character and recovered geometry; current-process errors/message failures zero. Source review additionally identifies flattened evasion distance and periodic combat jump overwriting approach requests; those are candidate corrections, not proven causes of every failed movement. Owned runner interrupted, app stopped/selector removed/Nova asleep; source teardown/ending did not run. Moon partial-path candidate remains device-unexecuted. I06/I03 immutable, no I07 pointer.

### I07-S27 — Keep original boss approach coherent

- **ID:** I07-S27.
- **TITLE:** Boss approach priority and full threat height.
- **CONTEXT:** J306 visible aiming passes, then stalls in the full Wetland encounter.
- **OBSERVATION:** Two living actors; occluded add chosen instead of unfinished Queen. Source path reachable; repeated redirection. Source input discards height for evasion and overwrites path jumps.
- **HYPOTHESIS:** Retain objective approach over occluded adds, restrict defence interruption to visible/contact threats and preserve source navigation jumps.
- **TASK:** Correct these related input decisions in the complete game; force-build and replay the genuine route on Nova.
- **CONSTRAINTS:** Input-only; original damage/health/RNG/rules/directors/loot/authority/collision/progression and physical input/camera unchanged. No forced boss defeat/charge/skip/save invention; I06/I03 immutable.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored TeleporterWorldBoundary, ignored full stage/config/build/device evidence and state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Device approach retains boss target and completes original combat/exit; inspect full route, then Moon partial path and mission/ending separately.
- **FAILURE EVIDENCE TO CAPTURE:** Actual target/LOS/endpoints, source path/jump/ground/3D range/motor progress, original damage/health/progression, current-process errors/capture and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J307 build/device exit; preserve failed candidates, no incomplete-run pointer.
- **DEPENDENCIES:** J306 exact two-actor stall/capture and source review; accepted camera/I06/I03.


**J307 pre-device caller correction:** Review finds the J306 combat approach call supplies stopDistance16, which NavigateWorldInput applies to every waypoint. Exact original PathFollower uses2-metre passage/height tolerance, so a16-metre movement stop can halt before the source follower advances. Correct only this call to1 metre; visible near-combat range logic still owns target approach/retreat. Preserve the first J307 archive/build (85.054seconds, zero errors, APK `8d65eab233f6a075847da5fec2316f76a4be33c64e5c3ccd09266056b4b5d7e8`) as rejected in host review, never installed. Corrected complete candidate work/experiments/scene-runtime/20261005T214936.976727Z retains a separate archive/parent record and refreshed compile/preflight;40 unchanged host safety tests remain passing. Full corrected build/device route pending. No stage edits occurred during the preceding outstanding build; no capability pointer advances.


**J307 corrected full build:**76.799-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `7ecb3ab672654e4a7a42e40a592f2d34f07e80f293b40b9e95a7ee7203ba8422`. Corrected waypoint tolerance is archived separately from the pre-device rejected parent. Complete unattended route/boss approach/Moon partial-path/mission/ending acceptance pending. I06/I03 unchanged; no new capability pointer.


**J307 live route progress:** Corrected full build executes on Nova. At567.5 gameplay seconds, three genuine source boss/charge/reward/exit/transports complete into Abyssal Depths,167 kills. Wetland no longer remains at the J306 approach blocker; visible boss damage and source path movement execute. No current-process errors/message failures. Different real-run RNG/loot prevents attributing all speed differences to the change. Same continuing original run/body/master; physical camera acceptance retained. Full fifth-stage/Moon partial-path/mission/ending/cleanup acceptance remains pending; I06/I03 unchanged, no I07 pointer.


**J307 complete route / Moon exit:**1533.244 gameplay seconds,325 kills, five genuine boss/charge/exit/transports and original Moon landing/population. Corrected combat approach passes Wetland/Rallypoint/Sky Meadow; all earlier source loops complete without current-process errors/message failures. Actual Moon partial path executes (observed2787 candidate requests/15 waypoints/about0.040seconds), then no closer candidate succeeds and terrain recovery circles the temple. Four batteries remain inactive. Last90seconds battery distance ranges977.209–1013.416 metres, ending1000.824; no meaningful traversal. Native lunar attack stops, mission/ending/full source teardown remain unaccepted. Matched-point read-only original solver against active collision reaches bridge node1890 with31/32/21 waypoints; raising start origin0/.05/.2/.92 does not change results. Source enter/exit bounds permit the inspected nodes at foot/body heights. These host results expose missing device request/filter evidence, not a justified physics/bounds workaround. Owned interruption preserved, app stopped/selector removed/Nova asleep; I06/I03 unchanged, no I07 pointer.

### I07-S28 — Actual integrated navigation request

- **ID:** I07-S28.
- **TITLE:** Resolve device/source Moon path contradiction.
- **CONTEXT:** J307 completes all five source loops; Moon partial paths stop short of the bridge.
- **OBSERVATION:** Device result conflicts with matched-point original host solver; exact device body/request/filter contract is absent. No runtime errors, no battery completion.
- **HYPOTHESIS:** Actual hull/jump/slope/gravity/start node or bounds/path rejection explains the contradiction.
- **TASK:** Add only that request snapshot to the existing composed game; force-build and run the genuine route on Nova.
- **CONSTRAINTS:** Read-only observations; original graph/physics/stats/authority/bounds/input/combat/mission/platform policy unchanged. No new standalone proof, save framework or fabricated skip; I06/I03 immutable.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored IntegratedWorldBoundary; ignored full archive/build/device comparisons; state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Exact current-launch original request/start/filter evidence classifies the first Moon failure; observation does not pass traversal or victory.
- **FAILURE EVIDENCE TO CAPTURE:** Full runtime inputs/start-node/graph and candidate counts, source movement/grounding/path, current-process logs/capture and live route identities.
- **STATE/JOURNAL UPDATES REQUIRED:** J308 build/device classification; preserve failed attempts and no incomplete-run pointer.
- **DEPENDENCIES:** J307 five-stage/Moon report and matched source/bounds comparisons; minimum conditional T08 triggered by actual ambiguity.


**J308 full build:**80.103-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `8eaeaa559c25b16da703fe8de1d9381902ab13e272af1715265e49542c54cc88`. Complete unattended route and exact device Moon request/start/filter classification pending; no new traversal or I07 pointer. I06/I03 unchanged.


**J308 first device attempt / same-APK retry:** Original first-stage defeat at115.2 gameplay seconds/18 kills, no completed transport, no runtime errors/message failures. Original StandardLoss report/save/reload and source cleanup complete; Android result remains retained. Human hull/maxJumpHeight3.75/slope70/gravity−30 and valid source start node are measured on the first stage; Moon request remains unobserved. Preserve this failed run; no source/physics/combat change or unchanged APK rebuild is justified. Expose existing movement_batch_run(retry=True) as thin ./dev prototype --action movement-batch-retry. Backend already creates immutable timestamped verification evidence and checks matching APK/terminal/assembly identities, current storage/device ownership and bounded durations. No new retry engine or cache mechanism. Initial CLI test run fails one of40 checks: an unnecessary retry=False keyword on the old action masks the intended first failure in its no-argument dispatch test. The initial passing-test statement was recorded prematurely and is corrected here. Restore the old no-argument call, keep retry=True on the new action only, then require all40 tests before device retry. Same-build genuine fresh run required, no forced seed/progression. Nova asleep before retry; I06/I03 unchanged, no I07 pointer.


**J308 retry dispatch repair:** Existing movement-batch-run retains its original no-argument call; only the new movement-batch-retry supplies retry=True. All40 safety tests now actually pass, including first-failure preservation and immutable retry attribution. Failed test log retained and earlier premature passing-test statement corrected. Same APK/recipe/Unity stage unchanged; actual immutable retry pending.


**J308 immutable retry exit:** Same APK verified, original first defeat remains preserved; fresh evidence at verification/20261005T223128.602430Z. One genuine original boss/reward/exit/transport, then Wetland reaches original charge1 while boss remains. At453.175seconds the original reachable boss path extends94.270 metres from the teleporter, but authored input interrupts approaches beyond50 metres even after charging finishes. This is a concrete input restriction, not a simulation/path solver failure. Current-process errors/message failures zero. Owned interruption at514.981seconds, app stopped/selector removed/Nova asleep; no source ending/teardown or Moon request observation. I06/I03 unchanged, no I07 pointer. Reassess prolonged combat as a post-charge approach restriction; preserve exact request observations for the subsequent Moon pass.

### I07-S29 — Boss approach after full charging

- **ID:** I07-S29.
- **TITLE:** Release diagnostic holdout constraint after original charge.
- **CONTEXT:** J308 same-APK retry reaches genuine charge1 but cannot complete a source boss detour.
- **OBSERVATION:** Original reachable path extends94.270m; own input stops approach beyond50m after charging is already complete. Runtime errors zero.
- **HYPOTHESIS:** Removing only the obsolete input constraint permits normal detour/combat.
- **TASK:** Integrate source charge-gated input constraint/observation in the whole game; full build and genuine Nova route.
- **CONSTRAINTS:** Preserve original charge duration, boss/health/damage/director/reward/exit, path/gates/physics/authority and physical controls; no forced outcome or skip. I06/I03 immutable.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored TeleporterWorldBoundary and one WorldReport flag; ignored complete archive/build/device evidence; state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run; same-APK movement-batch-retry only when a genuine defeat prevents the selected observation.
- **PASS CONDITION:** Actual constraint flag clears only after original charge1, normal detour/combat/exit completes; exact device Moon request remains subsequent required observation.
- **FAILURE EVIDENCE TO CAPTURE:** Original charge/boss/path radius/constraint flag, movement/grounding/target/LOS/damage, current-process errors/capture and first failure/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J309 build/device outcome, actual request classification, no incomplete-run pointer.
- **DEPENDENCIES:** J308 immutable retry path/charge blocker; retained camera/request trace/rollback.


**J309 full build:**78.655-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `f8243e02c3c7c556b97a8cf22432f2efecafd0dd6cb31e5ba8761abda0a4bc37`. Post-charge source detour and exact Moon request remain device-pending; original boss/charge/exit/physics unchanged. I06/I03 immutable; no I07 pointer.


**J309 device exit / J308 ambiguity resolved:**1202.661 gameplay seconds,341 kills, five genuine source boss/charge/reward/exit/transports and original Moon landing/population. Pre-charge constraint true and post-charge false measured; this RNG route does not reproduce the94m unfinished-boss detour. Moon actual request: Human, jump3.75, speed11.90000057, slope70, gravity−30,3960nodes, start1850;2782 nearer candidates rejected by original ComputePath, zero bounds/too-short rejections. Earlier editor comparisons omitted their actual−9.81 gravity. Matched request at−30 reproduces the source rejection to nodes1876/1890, whereas−9.81 reaches31/32waypoints. This corrects the prior assumed device/editor equivalence; no AOT defect or physics workaround is supported. Runtime/message errors zero, four batteries inactive. Capture reviewed; owned interruption/app stop/selector removal/Nova asleep, no source ending/teardown or I07 pointer. Preserve exact request and gravity comparison; next inspect the actual player-ground corridor at the original graph jump boundary. I06/I03 immutable.


### I07-S30 — Objective progress across terrain replanning

- **ID:** I07-S30.
- **TITLE:** Recover objective stalls hidden by changing local waypoints.
- **CONTEXT:** J309 full genuine run reaches Moon; exact source request now classified.
- **OBSERVATION:** Actual−30 source graph rejects raised-pillar route;4007 fallback frames/zero recovery jumps, repeated waypoint resets hide battery stall.
- **HYPOTHESIS:** Independent objective progress activates normal grounded recovery input at the physical obstruction.
- **TASK:** Integrate objective-progress tracking in the whole game and replay the genuine route; inspect actual recovery, grounding and first Moon failure.
- **CONSTRAINTS:** Original physics/jump/graph/gates/geometry/authority/mission/skills unchanged; no fabricated battery/ending/skip/restore; I06/I03 immutable. Keep16m avoidance horizon and source partial requests.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored IntegratedWorldBoundary; ignored complete archive/build/current-request/capture evidence; state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Actual objective stall survives local replan, existing grounded jump input executes with original limits, meaningful genuine Moon approach progress; no claim of mission victory from observation alone.
- **FAILURE EVIDENCE TO CAPTURE:** Objective versus waypoint times/distances, actual input/jump/motor/grounding, source path/filter/gravity, battery states, current-process errors/capture and first failure/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J310 actual build/device outcome; preserve failed attempts, no incomplete-run pointer.
- **DEPENDENCIES:** J309 exact Moon request/gravity classification and source pillar/ground audit; accepted camera/full route/J309 input boundary.


**J310 full build:**85.699-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `cc96b593b3da624a2e169f7d668df9693af46e54f269cc2785fe5202d8f41b42`. Actual objective-stall/recovery/jump/Moon traversal and mission/ending remain device-pending. Original physics/graph/mission and I06/I03 unchanged; no I07 pointer.


**J310 device exit:**912.248 gameplay seconds,241 kills, three genuine source boss/charge/reward/exit/transports into Abyssal Depths. The fourth boss is defeated/charge1 and original ChargedState.GetInteractability reports Available; nearby surviving adds trigger an authored35m unbounded defence veto before reward/exit, followed by a20m approach redirection. Selected add is world-occluded. No current-process/message errors. Objective-stall observation and31 recovery-input frames execute, but this attempt does not reach Moon; its Moon traversal hypothesis remains unaccepted. Owned interruption/capture/app stop/selector removal/Nova asleep, no source ending/teardown/pointer. Next remove the extra post-charge input gate while retaining defence during normal objective travel. I06/I03 immutable.

### I07-S31 — Source-available exit with travel defence

- **ID:** I07-S31.
- **TITLE:** Preserve objective travel after source teleporter becomes available.
- **CONTEXT:** J310 fourth stage boss/charge complete, original exit available, authored defence denies approach.
- **OBSERVATION:** Occluded nearby add triggers unbounded35m completion veto and20m movement redirection; runtime errors zero.
- **HYPOTHESIS:** Removing extra veto and firing while preserving navigation permits normal reward/exit.
- **TASK:** Integrate charged travel defence into complete game, forced build and genuine unattended Nova route.
- **CONSTRAINTS:** Pre-charge defence, original boss/charge/reward/exit, actors/health/damage/skills/physics/graph/authority/mission unchanged; interaction priority uses measured original range. I06/I03 immutable, no forced progression/checkpoint.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored TeleporterWorldBoundary; ignored full archive/build/device evidence; state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Original available teleporter/reward remains reachable under surviving adds; source transition completes, J310 Moon recovery then observed. Complete mission/ending remains separate.
- **FAILURE EVIDENCE TO CAPTURE:** Actual charge/boss/available/FSM, selected threat/range/LOS, normal target movement/selector/interaction, progression, current errors/capture/first failure/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J311 build/device outcome and J310 Moon acceptance; preserve all failed runs, no incomplete pointer.
- **DEPENDENCIES:** J310 actual charged-exit blocker and original ChargedState/Interactor contract; retained full run/J310 recovery/camera.


**J311 full build:**81.101-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `93c80d7b852d5bf502a90a502558d9848fd818894aa6db57d7474a278f5db490`. Actual available-exit travel/defence and retained J310 Moon objective recovery remain device-pending. Original boss/charge/exit/physics/graph/mission and I06/I03 unchanged; no I07 pointer.


**J311 first device exit:** Original first-stage boss/charge/reward/exit completes without the extra nearby-add veto;49 kills/184.3 last gameplay seconds. The next scene loads and original TeleportHelper/grounding/catalog checks pass, then strict continuity fails: Player XP112→113, inventory3→3 and money4→4. Full source cleanup succeeds; current-process/message errors zero, no Moon execution or capability pointer. Exact shipped ExperienceManager queues earned XP for0.5–2seconds and pays it in normal FixedUpdate, so the earlier quiet-combat snapshot omitted a legitimate pending award. Preserve the failed attempt/receipt/capture and stop/sleep Nova. Next observe and naturally settle that queue before the strict XP transport baseline; do not change XP values or relax equality. I06/I03 immutable.

### I07-S32 — Original queued XP and strict scene continuity

- **ID:** I07-S32.
- **TITLE:** Naturally settle earned XP before exact transport baseline.
- **CONTEXT:** J311 genuine available exit succeeds, then continuity rejects a delayed original XP award.
- **OBSERVATION:** XP112→113, items3→3/money4→4; source timed queue pays0.5–2seconds later.
- **HYPOTHESIS:** Bounded normal queue settlement retains exact earned XP and transport equality.
- **TASK:** Record original Player queued sum/count; wait original callbacks, assert conservation and unchanged post-settlement transport baseline; full integrated build/route.
- **CONSTRAINTS:** No forced XP, queue clearing, equality relaxation or time/stat/authority/mission changes. Full original run/master/body/inventory/money/count checks and I06/I03 retained.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored IntegratedStageBoundary; ignored complete archive/build/device queue/continuity records; state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Actual original queue settles within original maxOrbTravelTime+1sec, exact realized-plus-queued accounting holds and genuine scene transport completes; then continue full Moon route.
- **FAILURE EVIDENCE TO CAPTURE:** Actual realized/queued Player XP/count/time before/after, manager ownership, all identity/authority/inventory/money/count values, source exit/catalog/grounding, first failure/current errors/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J312 build/device outcome, preserve J311 failure, no incomplete capability pointer.
- **DEPENDENCIES:** J311 real exit/XP delta and exact original timed-award contract; existing preserved queue observer and full transport.


**J312 full build:**88.666-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `fd5fe8148a2557d83b9a719d855de3756399d3243539a24b71e461dbcb90feb6`. Actual original timed-XP settlement/conservation/strict transport and retained Moon recovery remain device-pending. Original earned XP/queue/physics/graph/mission and I06/I03 unchanged; no I07 pointer.


**J312 first device exit:** Original first-stage boss/charge/reward/exit completes;51 kills/211.6 last gameplay seconds. Before new-scene load, PendingStagePlayerExperience throws a null reference. Authored RewardField searches NonPublic|Static but pendingAwards is NonPublic|Instance; the failure belongs to the new observer, not original gameplay or settlement. Realized XP117, no queued amount yet observed. Full source cleanup passes; no message errors, no Moon execution or capability pointer. Preserve failed source/build/runtime/cleanup; Nova asleep. Explicit instance lookup and pre-read contract/phase checks are the next correction; original queue/values/conservation/equality remain unchanged.

### I07-S33 — Validated instance XP queue observation

- **ID:** I07-S33.
- **TITLE:** Correct static-versus-instance lookup before integrated XP settlement.
- **CONTEXT:** J312 original exit succeeds; new observer fails before next scene.
- **OBSERVATION:** RewardField only searches static fields; source pendingAwards is private instance. Exact editor reflection confirms all required fields.
- **HYPOTHESIS:** Explicit checked instance lookup allows original queue settlement/conservation to execute.
- **TASK:** Repair observer/phase attribution in full game, rebuild and replay real route.
- **CONSTRAINTS:** Queue/rewards/callbacks/bound/exact equality and original run/master/body/authority/mission unchanged; no force/grant/skip, I06/I03 immutable.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored IntegratedStageBoundary; ignored full archive/build/device reflection/settlement/failure records; state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Actual device instance/award fields resolve; original bounded settlement/conservation and strict transition checks pass, then continue whole Moon route.
- **FAILURE EVIDENCE TO CAPTURE:** Exact queue/type/field/owner failure, realized/queued XP/count/time/identity and continuity before/after, actual phase/runtime errors/source cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J313 actual build/device outcomes; preserve J312 failure, no incomplete pointer.
- **DEPENDENCIES:** J312 exact first observer failure, original field/source/linker and verified read-only reflection; J311 full-game route.


**J313 full build:**92.996-second/zero-error Vulkan ARM64 build;40 safety tests, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `9fd7ab7b009fd52c651040725776fb0660261603731ba1538c8b19fdc1690dc8`. Actual corrected instance queue observation/original settlement/conservation/strict transport and Moon recovery remain device-pending. I06/I03 unchanged; no I07 pointer.


**J313 live first transport:** Original boss/charge/reward/exit completes into Wetland Aspect while preserving same run/master/body/authority/inventory/money/count. Actual timed queue reports realized XP111 plus2 pending Player awards; original FixedUpdate settles to113 in0.224seconds, and strict post-transport XP remains113. This directly exercises corrected instance lookup and exact conservation without awarding/clearing/replacing XP. No runtime/message failure. Same original run continues; full later stages/Moon recovery/mission/ending remain pending, I06/I03 immutable, no I07 pointer.


**J313 live Moon recovery:** Five genuine source boss/charge/reward/exit/transports and309 kills reach original Moon population; all strict transport checks pass. Retained J310 objective stall survives terrain waypoint changes and normal grounded jump input executes. At1067.5seconds, actual body reaches bridge approach nearx479/z618 instead of the prior temple circle nearx700; original maxJumpHeight3.75/jumpCount1/unchanged gravity, battery-distance best721.6m. Current-process/message errors zero. Meaningful bridge approach progress is accepted as a live observation, not full battery/traversal/mission/victory/ending. Same genuine run continues; I06/I03 immutable, no I07 pointer.


**J313 device exit:** Five genuine original boss/charge/reward/exit/transports reach the Moon;324 kills at1418.402 gameplay seconds. Corrected queue lookup conserves actual earned XP111+2→113 through normal callbacks and strict transport. Objective-stall recovery now passes the temple and reaches original BridgeRamp ground; battery-distance best234.446m. Far-side approach then repeatedly falls: last90seconds distance233.779–499.916m and height−548.537..−181.550m,247 recovery-input frames and38 no-ground-candidate events. The authored terrain fallback returns the unchecked distant objective when all floor/torso/bounds candidates fail, while local navigation permits walking off cliffs. Four batteries remain inactive; no current-process runtime/message errors. Capture/first failure preserved; owned interruption, app stopped/selector removed/Nova asleep. Original ending and full source cleanup did not execute; no I07 pointer. Fix that input fallback before another genuine route; physics/mission/graph and I06/I03 remain unchanged.


### I07-S34 — Safe terrain rejection in the composed route

- **ID:** I07-S34.
- **TITLE:** Prevent unchecked distant-goal fallback and retain original cliff protection.
- **CONTEXT:** J313 five genuine exits and Moon bridge progress expose repeated far-side falls.
- **OBSERVATION:**38 no-candidate terrain events still return the objective; source local cliff guard disabled.
- **HYPOTHESIS:** Neutral rejected input and source cliff protection prevent unchecked departures while preserving valid traversal.
- **TASK:** Correct fallback input, build the complete game and replay the real route on Nova.
- **CONSTRAINTS:** Original physics/stats/graph/collision/gates, mission/battery/authority, camera and XP conservation unchanged; no skip/checkpoint framework. I06/I03 immutable.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored IntegratedWorldBoundary; ignored complete stage/build/input and device evidence; state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Integrated route remains coherent; actual fallback records neutral rejection/source cliff protection and advances safely beyond the bridge without changing source movement or objective requirements. Mission/ending remain separate actual outcomes.
- **FAILURE EVIDENCE TO CAPTURE:** First actual route failure, foot/body position, grounding/floor/waypoint/graph, rejected candidate/cliff flag, original input/jump/velocity, runtime/message errors and source versus owned cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J314 actual build/device outcomes; preserve J313 failed traversal and all rollbacks; no incomplete I07 pointer.
- **DEPENDENCIES:** J313 far-bridge capture and source-ground-input contract; pinned prior art and original LocalNavigator; existing full-game route/build/install safeguards.


**J314 full build:**86.094-second/zero-error Vulkan ARM64 build;40 safety tests, complete14397-file archive, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `11aa98a8dd955bf536e89b33f5f730ceea47634bfe47a354d64c34952ade0fe3`. Actual cliff-safe fallback/bridge/battery traversal remains device-pending. Original run/mission/physics/graph and I06/I03 unchanged; no I07 pointer.


**J314 first device exit:** Four genuine original boss/charge/reward/exit/transports and323 kills; normal player death in Sky Meadow at946.008 gameplay seconds. No current-process runtime/message errors. Original StandardLoss server/client report generates and persists to the retained Android ledger; original body destruction and full source/world cleanup pass. No Moon execution, so bridge hypothesis remains unaccepted.13 terrain rejections recorded; at defeat fallback is inactive/body grounded, which does not implicate the changed branch. Failed run/report/capture preserved and Nova verified asleep. Retry this exact verified APK with immutable evidence and a new genuine run; no rebuild, forced seed/stats or capability pointer. I06/I03 immutable.


**J314 immutable retry exit:** Same APK, separate verification/20261006T005020.484244Z. Five genuine exits and318 kills reach Moon; retained objective recovery passes temple. Source cliff guard observed during terrain fallback, then original partial path crosses bridge. Original player death at1109.993seconds/321 kills before the far-side lip; four batteries inactive. No runtime/message errors; StandardLoss persistence, natural body destruction and full source/world cleanup pass, Nova asleep. One source actor at physical contact contributes543.4damage; final actual aim points toward the distant battery. Existing Moon helper defends only when nearest core is within20m, and aims at core without visibility selection; first-stage helper already selects visible hurtboxes and uses physical contact for movement. Read-only exact source bounds permit the recorded contact positions, so no bounds workaround is justified. Original core-versus-physics discrepancy remains unmeasured. Next integrate that existing targeting/defence into Moon travel and observe actual positions; no actor/stat/attack nerf. Far-side guard hypothesis remains unaccepted because this attempt dies earlier. No I07 pointer, I06/I03 immutable.


### I07-S35 — Moon travel with visible combat and physical contact defence

- **ID:** I07-S35.
- **TITLE:** Reuse accepted targeting/checked combat movement in the full Moon route.
- **CONTEXT:** J314 five genuine exits and bridge traversal end in original player death.
- **OBSERVATION:** Contact actor543.4damage; final actual aim is battery. Moon helper uses nearest core/20m without visible-hurtbox selection. Bounds allow contact; actual core mismatch remains unmeasured.
- **HYPOTHESIS:** Visible targeting during travel plus checked physical-contact defence preserves both route progress and original combat survival.
- **TASK:** Integrate existing helpers into Moon input, record target core/physics/aim positions, rebuild full game and replay genuine route.
- **CONSTRAINTS:** Original combat damage/HP/director weights, abilities, mission/batteries/encounter, physics/graph/gates/bounds, camera and exact XP/transport unchanged; no direct damage/removal/skip or checkpoint side project. I06/I03 immutable.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored MoonMissionBoundary and WorldReport; ignored archive/input contract/build/device records; state/journal/milestones.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run.
- **PASS CONDITION:** Actual visible original targets receive ordinary ability attacks during Moon travel; physical contact evokes checked movement, genuine battery approach continues without changing source gameplay. Full mission/victory remains separate actual acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** Visibility/aim/target core/physics/contact distance, source actor damage/health/state, grounding/navigation/ability state, battery/encounter, first runtime/message failure and source versus owned cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J315 actual build/device outcomes; preserve J314 losses and unaccepted far-side hypothesis; no incomplete pointer.
- **DEPENDENCIES:** J314 exact bridge loss/capture and permitted source bounds; accepted visible-hurtbox and checked-combat helpers, original ability/physics contract and whole-game route.


**J315 full build:**86.047-second/zero-error Vulkan ARM64 build;40 safety tests, complete14397-file archive, matching request/start/terminal receipts,39 payload/45 assembly identities, APK SHA-256 `a5abbfffa983c4bb50702c540028ef1ed48c666a8c5978cec0d32e033ed1dd82`. Actual lunar visible targeting/contact defence/traversal/battery/ending remain device-pending. Original attacks/stats/director/mission/physics and I06/I03 unchanged; no I07 pointer.


**J315 device exit:** Unassisted genuine route ends in original Sky Meadow defeat at937.980seconds,4 exits/298 kills, after teleporter charge reaches1.0. Zero current-process errors/message failures; original StandardLoss generation/client report/XML reload/Android ledger persistence and full source/world cleanup pass. Nova verified asleep. Moon not reached, so visible lunar targeting and safe far-side traversal remain unaccepted; no I07 pointer. Evidence: `work/experiments/scene-runtime/20261006T011711.825389Z/device-exit-assessment.json`. I06/J256 and I03/J228 immutable. Next user-authorized iteration adds a small default-off, toggleable debug acceleration layer; assisted evidence never establishes normal combat/death/holdout/movement/full-run acceptance.


### I07-S36 — Isolated, toggleable debug acceleration for integrated iterations

- **ID:** I07-S36.
- **TITLE:** Shorten Moon/ending integration without claiming normal gameplay acceptance.
- **CONTEXT:** J315 unassisted route ends in Sky Meadow before Moon; user explicitly authorizes acceleration for subsequent runs.
- **OBSERVATION:** Original HealthComponent godMode, CharacterBody base/level stats and HoldoutZoneController.calcChargeRate provide small scoped boundaries. Pinned DebugToolkit god and charge_zone document player/holdout state relationships; direct charge mutation is unsuitable here.
- **HYPOTHESIS:** Independent reversible controls can accelerate genuine route progression while preserving attacks, occupancy, boss/mission gates and truthful evidence.
- **TASK:** Default-off panel/F1–F4 plus explicit per-launch CLI options; sticky assisted history, current effects and restoration; label results/ledger/receipts and fail closed on missing or contradictory debug evidence. Run integrated Android build with selected acceleration.
- **CONSTRAINTS:** All common boundaries; no assembly patch, direct kill, synthetic charge completion, state skip, route checkpoint framework, normal gate/pointer advancement from assisted evidence. Movement boost off for Moon navigation; combat/death/holdout acceptance excluded when affected.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Small authored debug boundary, existing Unity lab lifecycle/HUD/results, existing batch CLI and evidence tests, documentation; generated files ignored.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run --debug-options work/config/moon-debug-options.json.
- **PASS CONDITION:** Device executes selected controls, reversible toggles/callback removal observed, original progress continues; ever-assisted remains after controls off; labels and local result persistence agree. This is developer-control/integration acceptance only.
- **FAILURE EVIDENCE TO CAPTURE:** First host/build/runtime error, requested/current/history effects, source/derived stats, charge rates, restoration, matching APK/payload, actual mission state and result/cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** J316 actual device outcome and next first blocker, label assisted/unassisted explicitly; preserve J315 defeat and I06/I03.
- **DEPENDENCIES:** J315 iteration finished; existing integrated APK lifecycle and original APIs.


**J316 full build:** Full Vulkan ARM64 build passes in101.824seconds,zero errors,39 payload/45 assembly identities unchanged,complete14399-file archive; APK `48ec2c166415c97f7da07461693972c47191cbb2e271e95d35754eeda85ded8b`.45 safety/evidence tests and staged privacy scan pass. Actual device controls/restoration/assisted Moon route remain pending; no normal acceptance or I07 pointer.


**J316 device first failure:** Before gameplay, ownership guard rejects the empty inline debug report created by Unity JsonUtility. No effects applied/no stage progress; original source/world cleanup true,0 runtime errors, Nova asleep. Requested effects not observed: host receipt rejects normal eligibility and remains failed/unclassified. Exact-editor read-only FromJson confirms reportPresent=true/version1 despite omitted report. Evidence retained under `work/experiments/scene-runtime/20261006T014359.372445Z`. J317 replaces serialized-presence ownership with a live private ownership bit and preserves first runtime error when secondary acceptance checks fail. No original assembly/platform/gameplay change.


**J317 full build:** Live debug ownership guard passes45 safety/evidence tests and zero C# errors; full84.917second/zero-error Vulkan ARM64 build,39 payload/45 assembly identities unchanged,14399-file archive. APK `4fa70a01e2396fdb1f2c1ee2aa91707eb7f884dbedf02e196b4a13914e8e686d`. Device toggle/restoration and assisted route pending; no normal acceptance/I07 pointer.


**J317 device progress:** Current composed Android run executes requested invincibility/high damage/fast charge; original base damage12→12000, original movement7 unchanged, godMode observed true. Visually reviewed developer panel agrees with actual report. GUI clear restores original base/level damage, godMode false and charge callback count0; re-enable works, sticky ever-assisted/normal-eligibility false retained. Actual positive original charge rate0.011111111→0.088888891 over335 callbacks (x8). First source exit completes;0 current-process/message errors. Movement boost never enabled, optional device toggle remains pending. Assisted Moon route continues; this is developer-controls/integration evidence, no normal gameplay/full-route acceptance or I07 pointer. Evidence `work/experiments/scene-runtime/20261006T015220.202440Z/debug-toggle-device-assessment.json`.


## I07-J318 — High-jump assistance for Moon mission integration
- **ID:** I07-J318
- **TITLE:** Prepare independent high jump while preserving the human-controlled Moon attempt
- **STATUS:** HOST/FULL BUILD PASS; installation and jump device validation deferred by user
- **CONTEXT:** Aggressive whole-game I07; J317 same real five-exit run is under physical control.
- **OBSERVATION:** Manual input reaches BloodArena and charges two original batteries without new errors; normal base jump remains15/count1. Composed loot omits broader mobility items.
- **HYPOTHESIS:** Optional jump power x6 allows upper-terrain/pillar/elevator approach without forcing mission progress.
- **TASK:** Extend existing debug controls and evidence labels; build the complete integrated game, retain current manual run; enable/test in a subsequent assisted run. Inspect actual four-battery elevator/launch-volume behavior separately from boosted approach.
- **CONSTRAINTS:** Default off; no item unlock/grant, jump-count/position/velocity/mission edits; original gameplay consumer and DLLs preserved; no install/restart/control takeover until current user attempt finishes; exclude normal movement/navigation/full-run acceptance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing DebugAccelerationBoundary, debug option/evidence validation, focused evidence safety test, authored docs; ignored full build/receipt.
- **TEST COMMAND:** ./dev doctor; ./dev preflight; ./dev test; ./dev build --target vulkan --force; existing movement-batch run/retry with explicit ignored jumpBoost option when the live manual attempt is finished.
- **PASS CONDITION:** Full build attributed to candidate; subsequent device report shows original15→90→15, count1 unchanged, original physical jump/landing, sticky exclusions and zero new errors. No capability gate from host compilation.
- **FAILURE EVIDENCE TO CAPTURE:** Build errors/receipt; actual fields/count/toggles/physical motion/landing, source elevator and jump-volume state; preserve current J317 manual run and any first failure.
- **STATE/JOURNAL UPDATES REQUIRED:** J318 build/device status; report all cheats, preserve normal-run exclusions and I06/I03.
- **DEPENDENCIES:** J317 live debug controls; physical user's current attempt has priority over replacement.


**J318 full build:**46 host safety/evidence tests and zero C# errors; full83.456-second/zero-error Vulkan ARM64 build,39 payload/45 assembly identities retained. APK SHA-256 `9c8cc320ebe7057cf86d3c71032544f2fd80a6d23f18f983a31f5f6e64feb670`. Existing J317 live manual run remains installed; no device jump/restore claim. User explicitly requested to finish it. High-jump APK is prepared for subsequent assisted iteration, not installed. No normal acceptance or I07 pointer.


## I07-J319 — Moon wayfinding and elevator restoration
- **ID:** I07-J319
- **TITLE:** Restore original pillar beams and Moon gravity; continue the complete integrated mission
- **STATUS:** SOURCE/EDITOR/HOST/FULL BUILD PASS; integrated device run underway
- **CONTEXT:** J317 genuine five-exit assisted route and physical four-pillar completion; user remains in manual control.
- **OBSERVATION:** Two original elevator launches peak below arena; original SetGravity−20 was stripped, active game remains−30. Beam transforms also lack native particles/renderers, preventing wayfinding.
- **HYPOTHESIS:** Restoring original Moon gravity enables original elevator flight; restored source beams plus read-only markers make selected unfinished pillars visible.
- **TASK:** Integrate native scene restorations, Android beam shader/labels and exact gravity/launch observations, build full game, then run with jump assist off for elevator acceptance. Use high jump later only for mission iterations that explicitly exclude traversal/transport.
- **CONSTRAINTS:** Preserve original scene selection/state/charge/launch/physics/layers; no player translation, invented items or source assembly changes. Keep user's current run live until finished. Android visual shader is a replacement, not recovered shader parity. All active/ever-used cheats retain exclusions.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Moon scene transformation, existing stage material adapter, Moon mission/read-only presentation, camera projection, regeneration copier and docs; ignored scene/components/receipts/captures.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; existing movement-batch run/retry and configured Nova capture after current manual attempt finishes.
- **PASS CONDITION:** Full build attributed; actual Android original Moon gravity−20, visible selected inactive beams and current marker states, four source battery completions unlock Ready elevators, original unboosted jump volume reaches arena with no new first failure. Boss/escape/ending then remain the next integrated variables.
- **FAILURE EVIDENCE TO CAPTURE:** Native scene/source identities and counts, shader/build errors; current-launch beam/marker/charge/gravity/trajectory/physical motion/capture and original mission failures; preserve J317 four-pillar/failed-launch attempt.
- **STATE/JOURNAL UPDATES REQUIRED:** Build/device/first-failure status and active cheats; keep I06/I03 immutable; no normal gate from assisted route.
- **DEPENDENCIES:** J317 four-pillar/second-elevator evidence; J318 independent default-off jump toggle; user completes current attempt before replacement.


**J319 full build / previous-run exit:** Full125.301-second/zero-error Vulkan ARM64 build,46 host tests, complete14435-file source/settings/CLI archive and39 payload/45 assembly identities retained. APK SHA-256 `668a937cdbd5562206a81a0adf2648e7f350a515bcbde1311bd74ca3c7b1d31d`. User authorizes next run; preserve J317 four source completions/three Ready elevators/two low launch traces/capture, then owned interruption/app stop/selector removal/Nova sleep. Full source cleanup did not execute and no normal gate advances. Actual prior debug history shows user enabled movement x2 through developer panel at901.208seconds; observed speed14 at exit. Earlier movement-off descriptions apply to automatic route/Moon entry, but J318's description of the later live manual settings was stale. Four-pillar manual evidence therefore also excludes normal movement/navigation. New J319 launch requests invincibility/high damage/fast charge, movement/jump off; new beam/gravity/elevator runtime acceptance remains pending. I06/I03 unchanged; no I07 pointer.


**J319 live Android progress:** Five genuine exits reach Moon in the assisted integrated run. Original restored SetGravity executes with actual gravity−20; all three original serialized ten-second trajectories predict their target within0.0001m. Physical takeover confirmed, two source batteries complete, high jump/movement remain off, invincibility/high damage/fast charge on and zero current-process/message errors.48 restored native beam pairs/actual source activation and live particles are observed; labels visually reviewed. Entry/bridge screenshots do not establish visible sky beams, so that acceptance remains open. Native source renderers use thin Mesh/Local quads with random Z rotation and height300; material color/texture/particle alpha are nonzero. Camera far clip600 excludes distant effects. Preserve current manual session; actual four-pillar elevator flight/boss/escape/ending pending. No normal/I07 pointer.


## I07-J320 — Source-activated vertical Moon beacon fallback
- **ID:** I07-J320
- **TITLE:** Make original selected pillars readable in the composed Moon.
- **CONTEXT:** J319 live manual mission continues; do not replace it before the user's result.
- **OBSERVATION:** Native particles/activation pass, but reviewed entry/bridge captures do not visibly establish sky beams; thin Mesh/Local quads rotate and camera clips at600.
- **HYPOTHESIS:** View-facing vertical lines with measured source height and actual source activation provide reliable Android wayfinding.
- **TASK:** Add owned visual fallback and marker separation, compile/test, then build/run the next complete integrated candidate after current elevator/mission outcome.
- **CONSTRAINTS:** No mission/charge/pillar selection/interaction/physics/launch/authority/DLL rewrite; no source shader copying or parity claim. Preserve native particles, active manual session and I06/I03.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing Moon presentation/mission report, camera adapter, regeneration shader copier, authored beacon shader, state/journal; ignored archive/build/runtime captures.
- **TEST COMMAND:** ./dev preflight; ./dev test; forced full Vulkan build; existing whole-game run/capture.
- **PASS CONDITION:** Owned Android beacons visually agree with actual selected unfinished FX states; separate counts, no new first failure; owned resources and600-unit camera distance restore during cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** Actual source FX/particles/beacon states, stage-camera screenshot, shader/runtime errors, mission outcome and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Separate preparation/build/device status, explicit cheats/visual fallback scope, preserve J319 actual gravity/elevator evidence.
- **DEPENDENCIES:** J319 visual failure/source observations and current manual session exit;46 tests/zero C#/shader errors already pass. Full build/device pending.


**J319 physical mission/elevator/boss outcome:** User completes all four selected source batteries; all three original elevators Ready. At1209.782 gameplay seconds actual original unboosted elevator flight grounds Commando at y497.666 on the high arena, actual source Moon gravity−20, source launch fields unchanged. Capture visually confirms arena arrival. User debug history includes temporary high jump1027.573→1064.049 and movement1141.968→1189.427, both off before grounded elevator approach/launch; current fields return to power15/speed7. Invincibility/high damage/fast charge remain on. This establishes the restored elevator integration under those conditions, not normal traversal/combat/holdout/full-route acceptance.

Original arena trigger and four scripted encounter spawns progress PreEncounter→Phase1→Phase2→Phase3→Phase4→EncounterFinished; zero living members. Human reports final boss flies away in last animation. Actual final TrueDeath body position leaves arena to abouty582/x−342, so body motion is real; camera cause is not established. Current-process raw log reveals first mandatory failure: SpellBaseState.InitItemStealer instantiates null original Prefabs/NetworkedObjects/ItemStealController. Original escape remains Idle. Source audit finds stripped Phase4 CompletionEvents OnDisableEvent→DelayedEvent.CallDelayed10→BeginEscapeSequence/parent activation, and most source dropship holdout/state/trigger logic absent. Preserve failed encounter/runtime/capture and exact source audit; next repair original content and full escape lifecycle without forced progress. Native source CombatSquad also logs its member-zero fallback; do not discard those messages as a passed no-error run. J319 read-only marker incorrectly labels MoonBatteryDisabled as Ready; J320 now names that source state explicitly. I06/I03 immutable, no I07 pointer.


## I07-J321 — Original final phase → escape → dropship → ending
- **ID:** I07-J321
- **TITLE:** Restore the source lifecycle missing from the composed Moon.
- **CONTEXT:** J319 original elevator and encounter observations retained; user authorizes stop/sleep/update and is away.
- **OBSERVATION:** Missing item-stealer prefab throws; omitted Phase4/DelayedEvent and dropship logic leave escape Idle. Final-body motion unexplained.
- **HYPOTHESIS:** Original content/callback/timer contracts permit coherent source escape and ending.
- **TASK:** Integrate the whole final phase/escape/dropship loop, include J320 beacons, full build/run real route and fix first device blocker.
- **CONSTRAINTS:** Original source/read-only input, exact pins, explicit silent platform boundary; no forced mission or normal acceptance from assisted route. Preserve I06/I03/J319; Nova asleep when idle.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Moon restoration/regeneration and existing provider, timer/input/observation boundary, exact no-audio transformation; ignored stage/archive/build/device evidence.
- **TEST COMMAND:** ./dev preflight; ./dev test; ./dev build --target vulkan --force; ./dev prototype --action movement-batch-run --debug-options work/config/moon-debug-options.json.
- **PASS CONDITION:** Actual original item-steal states, source encounter completion/delayed escape/dropship holdout/ending and saved original result; visual beacons separately reviewed.
- **FAILURE EVIDENCE TO CAPTURE:** Current-PID exceptions/native/AOT errors, source states/charge/countdown/trigger data, actual boss motion, captures and build/content identities.
- **STATE/JOURNAL UPDATES REQUIRED:** Exact build/device/cleanup outcome, debug history, first failure/revisit condition; no partial/assisted full-route gate.
- **DEPENDENCIES:** J319 classified failure and explicit user stop; prior-art and exact source audit. Preparation passes46 tests/scene schema/compile; full build/device pending.


**J321 first build failure / J322 retry:** The terminal build rejects the new ten-asset support manifest at its existing count guard before bundle/AOT work (0.360seconds). No new APK or device attempt; preserve failed dispatch/request/start/terminal and full source archive separately. Extend only the measured ten-asset allowance, retaining generated-path/existence safeguards. Fork a fresh build attempt and archive it; full forced Vulkan retry pending. Existing preparation/assembly/schema outcomes remain scoped, no capability gate advances.


**J322 full build:** Forced Vulkan ARM64 IL2CPP build completes165.095seconds with zero errors. Request/start/terminal and actual APK hash match;39 payload hashes/45 assembly identities verify. APK SHA-256 `80f5fe289928c9c1079251ee5206362b09bf2400934a396cd74adc9165e3a81f`. New original final-phase support assets/source callbacks and J320 beacon presentation are compiled, not yet device-accepted. Launch the complete genuine route with invincibility/high damage/fast charge; movement/jump initially off. User away; automatic traversal assistance, if used, remains separately disclosed and excludes normal-run acceptance.


## J323 — Correct the source beam curve after integrated Moon-entry failure

**J322 device first failure:** Four genuine transports/85 kills precede fifth transport into Moon at482.673gameplay seconds (506.588-second host survival). Authored beacon Check rejects y.constantMax0 and aborts activation before original mission initialization; no navigation or final-phase/escape acceptance. This is a presentation regression, not a source gravity/networking failure. Complete owned cleanup passes, timer scheduler stops/zero pending callbacks, boosts restore, app stops and Nova sleeps. Failed APK/report/capture/console/source archive preserved; I06/I03 unchanged.

**Measured cause / repair:** Exact scene has48 native beam modules in Curve mode, constantMax0/curveMultiplier300; evaluation at0/0.5/1 is300 and startSizeY1. Previous preparation mistook the serialized curve scale for the constant accessor. Read actual curve values; preserve original particle modules. Missing height/shader now records an explicit optional presentation error and skips the owned line, rather than throwing through original mission activation. No visuals accepted on the failed run. A host-only read-only query initially fails on Vector3 JSON recursion; flattening scale to a number preserves the actual measurement. Fresh J323 attempt builds/replays the same composed genuine route; invincibility/high damage/fast charge, movement/jump initially off. User away; disclosed jump assistance may aid measured traversal, and unsupported navigation may require a user handoff. No normal/I07 pointer.


**J323 full build / replay:** First request never starts because MCP disconnects during compilation domain reload; editor reconnects with zero compiler errors. Preserve that failed dispatch separately, then retry the same archived candidate with a fresh request. Forced Vulkan ARM64 IL2CPP build passes89.648seconds/zero errors,39 payload/45 assembly identities and46 host tests. APK SHA-256 `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`. Owned in-place update passes live storage/placement checks; composed genuine route is running with invincibility/high damage/fast charge, movement/jump initially off. No new Moon visual/final-phase/escape acceptance; no normal/I07 pointer. Evidence `work/experiments/scene-runtime/20261006T034153.546343Z`.


**J323 device outcome / requested pause:** Five genuine source transports reach Moon at about475seconds. Original mission/population initializes,48 native beam renderers and four active authored Android beacons are observed, and reviewed607-second capture visibly shows vertical sky lines. Original particle modules retained; native shader parity remains unproven. Original fixed-time queue advances14,816ticks by770.731seconds without current-process errors. Four source batteries remain uncharged; final-phase/item-steal/escape/dropship device acceptance is still pending.

**Bounded navigation assistance:** User is away and authorizes6x jump or another route, with a stop if navigation needs manual input. Two separately recorded GUI toggle windows at660.953–663.666 and735.783–746.881seconds raise original computed power15→90 and restore15. The longer window confirms actual original path-request maxJumpHeight202.5, but zero reachable waypoints, terrain fallback has no candidate and requests no jump. Character position does not change; this proves the toggle/replanning outcome, not high-jump traversal or that6x cannot clear the cliff. Invincibility/damage x1000/charge x8 stay enabled, movement x2 never enabled; all observations exclude normal-game acceptance. No speculative navigation framework added.

**Handoff / rollback:** Preserve current report, navigation history, captures, current-process logs, exact APK/hash/payload receipts and complete source archive under `work/experiments/scene-runtime/20261006T034153.546343Z`. Stop the attributed route/observer and owned app, remove only its selector, verify Nova asleep; installed APK/payload/Android results retained. Source cleanup did not execute during this intentional interruption; no false restoration claim. I06/I03 and all accepted pointers remain unchanged. Pause at the user's conditional request, pending manual navigation. On return, use the already built candidate via `./dev prototype --action movement-batch-retry --debug-options work/config/moon-debug-options.json`, preserving this attempt and creating a fresh verification directory; follow the genuine route and hand over physical control for the Moon terrain. No normal/I07 gate advances.


## I08-J324 — Independent material families and base-stage stability

- **ID:** I08-J324
- **TITLE:** Independent material families and base-stage stability
- **CONTEXT:** User switches to explicitly authorized internal-only Nova, one APK, Moon paused. J323/I06/I03 retained.
- **OBSERVATION:** Legacy preview omits normal/emission/terrain/particle response; existing adopted-only placement rejects the new device.
- **HYPOTHESIS:** Owned material approximations and bounded five-stage window can exercise broad rendering/transition stability without Moon or user presence.
- **TASK:** Add only required internal placement/one-dispatch guard and five material-family shaders; run four genuine source transports.
- **CONSTRAINTS:** No original assets/source in Git, no original install change, no platform success, one device APK, idle OLED asleep, no Moon or normal assisted acceptance.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Device guards/example/docs/tests; owned renderer/camera/batch helpers and regeneration; ignored scene/build/run evidence.
- **TEST COMMAND:** ./dev doctor; ./dev preflight; ./dev test; forced Vulkan build; movement-batch-run with independent debug options.
- **PASS CONDITION:** Completed855.56-second window/four genuine transports/158kills/zero current-process errors, cleanup and internal backing;49 host tests. Does not pass parity or normal gameplay.
- **FAILURE EVIDENCE TO CAPTURE:** Preserve source/build/APK hashes, each stage capture, process errors/placement/memory/frame/thermal and debug history, first failed helper/toggle.
- **STATE/JOURNAL UPDATES REQUIRED:** J324 journal/state/milestone graphics/stability scope; archive installed APK and old Moon/device receipts, no normal/I07 pointer.
- **DEPENDENCIES:** Current integrated world and explicit new-device authorization.


## I08-J325 — Source-guided effect correction through shader payload

- **ID:** I08-J325
- **TITLE:** Source-guided effect correction through shader payload
- **CONTEXT:** Same installed J324 APK; original PC appearance is authority.
- **OBSERVATION:** Overbroad additive teleporter effect and invented grading are visible in reviewed legacy/approximation toggles.
- **HYPOTHESIS:** Original alpha/Fresnel parameters and neutral camera grade remove these unsupported aesthetic choices.
- **TASK:** Mask One-blend RGB with alpha, source rim/projection/snow controls; identity grade; build only fixed five-shader bundle, retry same APK.
- **CONSTRAINTS:** Preserve source activation/physics/assemblies/Moon; no PC parity claim; independent receipts, changed-file sync and one APK guard.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Five authored shaders; thin presentation action/editor dispatch; ignored payload variant/verification.
- **TEST COMMAND:** ./dev prototype --action presentation-payload; ./dev prototype --action movement-batch-retry --debug-options work/config/independent-debug-options.json.
- **PASS CONDITION:** Completed408.53-second/four-transition/63kill window, zero errors, restored debug/owned state, reviewed corrected rim. Matching PC parity remains open.
- **FAILURE EVIDENCE TO CAPTURE:** Bundle request/start/terminal and hashes, APK reuse, visual first mismatch and current-process crashes/errors.
- **STATE/JOURNAL UPDATES REQUIRED:** J325 and visual-restoration notes; bound assisted evidence and retain previous payload.
- **DEPENDENCIES:** I08-J324; source material blend metadata, pinned community graphics knowledge.


## I08-J326 — Original base-stage atmosphere and native lights

- **ID:** I08-J326
- **TITLE:** Original base-stage atmosphere and native lights
- **CONTEXT:** Broad integrated graphics continues on the one installed APK.
- **OBSERVATION:** Geometry conversion stripped native RenderSettings/light classes.
- **HYPOTHESIS:** Restoring exact original fog/ambient/sky/sun/light blocks can remove that reconstruction omission without new gameplay callbacks.
- **TASK:** Keep native104/108 and source closure in five base scenes; rebuild those existing bundles/manifests, run four genuine transports.
- **CONSTRAINTS:** Moon/assemblies/authority/physics callbacks unchanged; no invented scene settings, sky or PC parity; immutable previous sources/payload, idle OLED asleep.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing scene transformation; minimum stage-presentation bundle action; ignored native contracts/scene backups/receipts/captures.
- **TEST COMMAND:** ./dev prototype --action stage-presentation-payload; same-APK movement-batch-retry with independent debug options.
- **PASS CONDITION:** Completed host build38.84seconds/zero errors and same-APK508.13-second window/four transports/76kills/zero errors; captures reviewed, cleanup/sleep pass. Preserved source settings and derivative payload identities; no PC parity.
- **FAILURE EVIDENCE TO CAPTURE:** Exact native settings, imported references, each scene capture, first runtime failure and perf/memory deltas; capture helper relative-path rejection retained.
- **STATE/JOURNAL UPDATES REQUIRED:** Append J326 terminal outcome, concise state and graphics/stability scope; no parity/normal/Moon pointer.
- **DEPENDENCIES:** I08-J325; existing source scene closure and exact accepted input.


## I08-J327 — Recovered cubemap camera and source appearance observations

- **ID:** I08-J327
- **TITLE:** Recovered cubemap camera and source appearance observations
- **CONTEXT:** Installed J324 camera still clears sky to solid color; one APK dispatch consumed.
- **OBSERVATION:** Four exact source sky materials use built-in Skybox/Cubemap; one stage sky reference resolves to terrain.
- **HYPOTHESIS:** Source cubemap clear and removal of diagnostic directional light where source lights exist enable authored atmosphere without an invented sky.
- **TASK:** Prepare camera change/actual scene fog-light samples and approximation label; compile and build a reviewable host APK; clarify same-package replacement before installing.
- **CONSTRAINTS:** No inferred cubemap for dampcavesimple, no source grading/shader parity claim, no new license/platform access or Moon progression; preserve installed APK/payload.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Owned presentation camera/display/UI; ignored prebuild archive, compiler/sky query, full Vulkan candidate receipts.
- **TEST COMMAND:** Exact-editor refresh/console query; ./dev preflight; forced Vulkan build. Device retry only after replacement authorization.
- **PASS CONDITION:** Exact-editor preparation and full82.927-second/zero-error Vulkan build pass;14,478-file archive/41 payload/45 assembly identities verified. Host APK ready, replacement authorization/device sky acceptance pending.
- **FAILURE EVIDENCE TO CAPTURE:** Native sky shader support/texture/material identity and camera fields, full request/start/terminal/APK hash, first device sky/light/perf failure.
- **STATE/JOURNAL UPDATES REQUIRED:** J327 build/install outcomes and visual limits; state next action explicitly distinguishes installed code from host candidate.
- **DEPENDENCIES:** I08-J326 terminal; explicit user one-APK limit clarification for replacement.


**I08-J326 exit:**508.133gameplay/529.572host seconds,4 transports/76kills, zero actual-PID runtime/message failures, full cleanup/sleep. Mean33.517ms/0.80%>50ms, allocation141.99→225.44MiB across stages; no CPU/GPU thermal or leak claim. Matching PC parity and source cubemap camera remain open. Invincibility/high damage/fast charge on, movement/jump boost off; restored. Scoped observed presentation pointer only, I06/I03/J323 unchanged.


**I08-J327 build exit:** Host-only APK `464ab5dd2c22c1b2f6e3896338d81d7bb3f819dd68d0387f8384216b1d45712a`, source/full terminal receipts preserved. One-APK clarification pending; installed J324 hash unchanged, OLED asleep. No PC parity or device sky/camera acceptance from compilation.


## I08-J328 — Native stage lighting and source water inputs

- **ID:** I08-J328
- **TITLE:** Native stage lighting and source water inputs
- **CONTEXT:** Original scene atmosphere retained, same J324 APK remains installed.
- **OBSERVATION:** Replacement surfaces lacked native point/spot attenuation, additional passes and shadows; water used unsupported invented values.
- **HYPOTHESIS:** Native Unity lighting contracts plus original material inputs remove those omissions without replacing APK/gameplay.
- **TASK:** Add native surface/terrain lighting/shadow passes, remove ambient floor, retain original water inputs; rebuild fixed shader bundle and run integrated base-stage window.
- **CONSTRAINTS:** One installation dispatch consumed; same APK only. No source-shader/PC parity, normal gameplay or Moon claim. Preserve original assemblies, previous payloads and J327 host candidate.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Three authored shaders, ignored material queries/receipts/captures, concise state/journal/visual notes.
- **TEST COMMAND:** ./dev doctor; ./dev test; ./dev prototype --action presentation-payload; movement-batch-retry with independent debug options.
- **PASS CONDITION:**49 tests; final shader build4.631seconds/zero errors; same-APK437.770-second window/four transports/68kills/zero errors/cleanup. Chest/barrel shadows reviewed; source water inputs host-verified, water appearance unaccepted.
- **FAILURE EVIDENCE TO CAPTURE:** Shader import/pass/parameter evidence, request/start/terminal/hash, actual PID errors and capture context, frame/memory/debug history.
- **STATE/JOURNAL UPDATES REQUIRED:** J328, graphics/stability scope and observed-only presentation pointer; no normal/I07 advance.
- **DEPENDENCIES:** I08-J326; pinned graphics contracts and exact-editor native lighting definitions.

## I08-J329 — Compiled source-shader conversion prior art

- **ID:** I08-J329
- **TITLE:** Compiled source-shader conversion prior art
- **CONTEXT:** Source shader bundles use Windows programs; current replacements approximate behavior.
- **OBSERVATION:** Dummy exports provide no shader implementation; program conversion may omit Unity integration.
- **HYPOTHESIS:** Existing primary-source exporters/converters can delimit a future discriminating trial.
- **TASK:** Inspect pinned AssetRipper exporter/source paths and official shader converter interfaces; record applicable route or missing contracts without installing a framework.
- **CONSTRAINTS:** Read-only ignored source checkout, no original-install change, no copied proprietary/third-party implementation or inferred Android capability.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Ignored sparse reference checkout; authored prior-art/journal/visual-restoration notes.
- **TEST COMMAND:** Read-only pinned exporter/interface inspection; no runtime/build claim.
- **PASS CONDITION:** Bounded review completed: no direct usable Unity Android route found in inspected exporters; Unity pass/keyword/resource integration remains required. Research exit, not graphics parity.
- **FAILURE EVIDENCE TO CAPTURE:** Exact pin/files/interface boundaries and source-format mismatch; preserve future failed converter trial separately.
- **STATE/JOURNAL UPDATES REQUIRED:** J329 decision and source citations; retain dummy-source warning and PC parity gap.
- **DEPENDENCIES:** Existing community graphics map and original shader platform inventory.


## I08-J330 — Original lighting data and reflection component closure

- **ID:** I08-J330
- **TITLE:** Original lighting data and reflection component closure
- **CONTEXT:** Same installed J324 APK and original PC appearance authority.
- **OBSERVATION:** Converted geometry omits native lighting-data references and reflection components.
- **HYPOTHESIS:** Their exact retained closure can integrate without gameplay changes or speculative baking.
- **TASK:** Preserve classes157/215, validate same-scene back-reference without traversing discarded gameplay, build five stage bundles, run composed base-stage loop.
- **CONSTRAINTS:** No new callbacks/assembly/APK/MonoBehaviour/Moon changes; empty source lightmaps/probes remain empty; no reflection/PC parity claim from asset presence.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing scene transformation and ignored source/import/payload/device records.
- **TEST COMMAND:** ./dev preflight; ./dev test; stage-presentation-payload; same-APK movement-batch-retry with independent debug options.
- **PASS CONDITION:**49 tests;32.188-second/zero-error bundle build; five valid imported LightingData references/nine reflection components;412.196-second device window/four transports/65kills/zero errors/cleanup. Reflection textures remain unbound.
- **FAILURE EVIDENCE TO CAPTURE:** Native/source hashes and cycles, imported validity/textures, existing Billboard LOD pointers, actual-PID errors and capture/frame/memory/debug history.
- **STATE/JOURNAL UPDATES REQUIRED:** J330 and observed-only pointer; distinguish native retention from appearance; retain J327/J323/I06/I03.
- **DEPENDENCIES:** I08-J326/J328; current input/pinned graphics prior art and existing closure.

## I08-J331 — Native environment particles across the integrated base stages

- **ID:** I08-J331
- **TITLE:** Native environment particles across the integrated base stages
- **CONTEXT:** Large visual-restoration chunk through the installed APK's separate scene payloads.
- **OBSERVATION:**52/15/59/101/120 original particle-system/renderer pairs were stripped from five base scenes.
- **HYPOTHESIS:** Restoring original native modules/owner links/active flags can recover environmental effects while existing Android material binding handles their rendering.
- **TASK:** Retain native198/199 and measured texture/mesh/subemitter dependencies; build five scene bundles and run the same integrated stage window, fix the first actual failure.
- **CONSTRAINTS:** No new gameplay callbacks, invented activation, particles or brightness; preserve native modules, including two Sky Meadow collision modules, two Plains trigger modules and local subemitters. Source review finds no external emitter/light prefab references. Moon/assemblies/APK unchanged; shaders approximate.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing presentation scene closure; ignored module/renderer/import/source/payload/capture records.
- **TEST COMMAND:** stage-presentation-payload; same-APK movement-batch-retry with independent debug options; capture current stage/performance.
- **PASS CONDITION:** Host import/build35.338seconds/zero errors and439.071-second device window/four transports/70kills/zero errors/cleanup pass. Exact environmental effect appearance and PC parity remain unaccepted; source module/import identities retained.
- **FAILURE EVIDENCE TO CAPTURE:** Native references, actual shape/material/dependency failures, active/playing particle counts, current-process errors, effect readability and frame/memory samples.
- **STATE/JOURNAL UPDATES REQUIRED:** J331 first failure/exit and graphical limits; preserve J330 full rollback and all Moon/normal pointers.
- **DEPENDENCIES:** I08-J330 terminal; pinned EditorKit blend knowledge and original source/native settings.

## I08-J332 — Original baked reflection texture repair

- **ID:** I08-J332
- **TITLE:** Original baked reflection texture repair
- **CONTEXT:** J330 retains valid lighting data and nine native probes, but exported baked textures are unbound.
- **OBSERVATION:** Original PC native probes contain m_BakedTexture pointers omitted by export; default reflection cubemap is not always the probe's texture.
- **HYPOTHESIS:** Exact native external/container mapping can restore those authored Cubemaps through a small explicit Android scene-data adapter.
- **TASK:** Complete source mapping, restore only measured texture bindings in owned scenes with explicit mode adaptation if required, verify imported assignments, then run the integrated world.
- **CONSTRAINTS:** No guessed texture/lighting, new bake, broad serialization framework, source-install write, APK replacement or PC parity claim; preserve source parameters/identity and previous full payload.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing native scene transformation or a narrow helper; ignored source mapping/contract/scene/payload/device records.
- **TEST COMMAND:** Existing native/source inspection; stage-presentation-payload; same-APK movement-batch-retry after imported assignments verify.
- **PASS CONDITION:** All nine mappings/imported original Custom Cubemap bindings verify;37.126-second/zero-error stage build and49 host tests pass. Same-APK410.116gameplay/432.351host seconds, four transports/68kills, zero actual-PID runtime/message errors and cleanup/sleep pass. Reflection appearance/PC parity remain unaccepted.
- **FAILURE EVIDENCE TO CAPTURE:** Original pointer/external/container/export hashes, ambiguous match and first two failed host scripts/logs, import/binding/type mismatch and first runtime/appearance error.
- **STATE/JOURNAL UPDATES REQUIRED:** J332 preparation and actual repair/build/device exit separately; retain observed-only scope and J323/I06/I03.
- **DEPENDENCIES:** I08-J330/J331 terminal; existing pinned UnityPy/export input and current graphics prior art.

## I08-J333 — Original distant foliage and billboard LOD restoration

- **ID:** I08-J333
- **TITLE:** Original distant foliage and billboard LOD restoration
- **CONTEXT:** Five integrated base-stage scenes retain source LODGroups but omit native BillboardRenderer class227.
- **OBSERVATION:** Source scenes contain85/203/50/20/552 billboard renderers and793 LOD references to them. Eleven exact original billboard assets/materials retain atlas geometry, dimensions, texture slices and source properties; their SpeedTree Billboard shader exports are dummies.
- **HYPOTHESIS:** Retaining native components/assets and using the exact editor's billboard atlas/vertex path in an explicitly approximate material family can restore the missing distant foliage without altering gameplay.
- **TASK:** Prepare the five-stage native billboard closure and dedicated material selection in a coherent host APK alongside J327 sky and J332 lighting/reflections; verify asset/LOD/material contracts, build, then await the existing one-APK replacement clarification before device execution.
- **CONSTRAINTS:** Installed J324 APK/J332 payload and Moon candidate untouched; no guessed atlas or terrain, copied proprietary/community shader implementation, new wind animation, invented grade or PC parity claim. Native vertex/atlas support does not reproduce RoR2's lighting ramp.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing scene transformation/material selector/stage observation, one authored wrapper of bundled Unity includes, existing shader bundle recipe; ignored candidate/source/import/build receipts.
- **TEST COMMAND:** Existing exact-input source inspection, preflight, forced Vulkan host build and read-only editor contract review; same owned package device run only if replacement is authorized.
- **PASS CONDITION:** HOST PASS — all910 native renderers/eleven exact assets and793 billboard LOD references import; nonempty references retained and original explicit empty slots preserved. Dedicated owned shader/atlas/material/geometry contracts verify. Final91.012-second/zero-error Vulkan ARM64 build, matching request/start/terminal,41 payload and45 assembly identities;49 tests pass. Device rendering and matching PC appearance remain pending, no installation.
- **FAILURE EVIDENCE TO CAPTURE:** Source GUID/container/material/LOD mismatch, missing shader/atlas input, first compiler/AOT/runtime error and visually incorrect distant silhouettes; preserve failed helper logs.
- **STATE/JOURNAL UPDATES REQUIRED:** J333 preparation/build versus eventual device/PC outcomes separately; preserve J332 observed-only rollback and J323/I06/I03.
- **DEPENDENCIES:** J332 terminal; pinned scene/graphics prior art, exact-editor native billboard contracts; pending APK clarification for device.

## I08-J334 — Source reflection range and material response

- **ID:** I08-J334
- **TITLE:** Source reflection range and material response
- **CONTEXT:** The same installed J324 APK can accept shader and scene payload updates; J333 remains an immutable host candidate awaiting update clarification.
- **OBSERVATION:** Nine original BC6H reflection textures import as ETC RGB on Android. Terrain omits measured per-channel specular inputs; current surface/terrain shaders do not sample the retained probes. Texture format alone does not establish whether source brightness was lost.
- **HYPOTHESIS:** Measuring exact exported HDR inputs first can justify a narrow format repair; native Unity reflection sampling and source material inputs can address missing response while remaining explicitly approximate.
- **TASK:** Measure owned temporary imports and preserve source/import contracts. Repair only demonstrated format loss, then integrate source-driven material response into the existing composed world and inspect the first real device failure.
- **CONSTRAINTS:** No additional APK installation, source-install/export edits, invented lighting ramp, original shader or PC parity claim. Preserve J332/J333 and all Moon/normal rollbacks. Original PC appearance remains the authority; matching captures are still unavailable.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing source reflection/presentation payload tooling, authored surface/terrain shaders and bundled-Unity include calls; ignored texture measurements/import receipts/payload/device captures.
- **TEST COMMAND:** Exact-editor owned-copy range/format checks; preflight; shader/stage presentation payload builds; same-APK integrated stage window with recorded debug options.
- **PASS CONDITION:** Integration PASS — nine exact source-preserving RGBAHalf imports,225 material input checks,49 tests; shader/stage builds7.065/42.478seconds with zero errors. Same-APK427.648gameplay/450.230host seconds, four genuine transports/64kills, zero actual-PID runtime/message errors and cleanup/sleep. Reflection/PC appearance and normal gameplay remain unaccepted; opaque particle cards are a recorded visual failure.
- **FAILURE EVIDENCE TO CAPTURE:** First query/helper failure, HDR decoding/range/format difference, shader errors, actual-PID runtime errors, captures, memory/frame/debug history.
- **STATE/JOURNAL UPDATES REQUIRED:** J334 measurements, first failure, justified repair and actual device outcome; observed-only pointer advances only after accepted integration.
- **DEPENDENCIES:** I08-J332 terminal; pinned R2Wiki terrain material semantics and ImportExtensions custom deferred/reflection clues; exact SDK contracts.

## I08-J335 — Original particle families in the composed candidate

- **ID:** I08-J335
- **TITLE:** Original particle families in the composed candidate
- **CONTEXT:** J334 exposes opaque square cards; the installed selector routes non-Cloud particle families as surfaces and ignores the opaque cloud cutoff/state.
- **OBSERVATION:** Eight imported materials use four exact Unity builtin particle families. Across five stages,347 renderers expose141 opaque-cloud and29 distortion bindings;177 empty secondary/trail slots are original, with zero empty primary slots. Original opaque shader specifies alpha test2450, One/Zero, depth write and a shadow pass; distortion specifies a named grab, depth-write off and default queue5000. Exported defaults lose these states.
- **HYPOTHESIS:** Preserve builtin shaders and measured render contracts, with explicit bounded custom-family approximations, to remove routing failures without inventing another aesthetic.
- **TASK:** Retain the four native families; implement source cutoff/depth/shadows for opaque clouds and source-texture screen distortion/fades; assemble with J333 skies/billboards and J334 reflection data into one host candidate. Fix the first compiler/import failure; device verification awaits the existing APK clarification.
- **CONSTRAINTS:** No new install dispatch, original shader/IP copying, guessed colors, particle modules or gameplay changes. Custom lighting/cloud/extrusion/distortion formula and PC appearance remain approximate/unaccepted. Preserve installed J324/J334 and immutable J333/J323/normal rollbacks.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing material selector/camera, two authored shader wrappers and their existing bundle recipe; ignored original shader states/material contracts/source/payload/build archive.
- **TEST COMMAND:** Exact-editor source/copy/shader contract checks; preflight; forced Vulkan ARM64 host build;49 safety tests. Integrated Nova window only after APK replacement authorization.
- **PASS CONDITION:** Host candidate PASS —52 materials/709 supported-property checks, exact native families and source2450/5000/default-vs-explicit queue contracts; final Vulkan ARM64 build84.288seconds/zero errors,41 payload files/all45 accepted assembly identities,910 billboards/347 particle renderers/nine RGBAHalf probes.49 tests/doctor/preflight pass; complete candidate archived and installed J324/J334 selection restored with OLED asleep. No device or PC appearance claim from compilation; update clarification pending.
- **FAILURE EVIDENCE TO CAPTURE:** Initial trail-slot assertion, source/native default queue mismatch, unsupported shader/first compiler/build failure, later actual-PID errors and particle-card captures.
- **STATE/JOURNAL UPDATES REQUIRED:** J335 source decisions, host versus device outcomes and actual remaining gaps; no observed or normal pointer advance from host build.
- **DEPENDENCIES:** J334 device terminal; pinned EditorKit shader-registration/blend metadata, exact original shader forms and bundled Unity API; pending update clarification.

## I09-J336 — Broader original loot in the composed run

- **ID:** I09-J336
- **TITLE:** Earned mobility, defense, healing and rare items in the composed run
- **CONTEXT:** The persistent game has six chest items, one green item and no rare pool. Moon remains paused; source rendering candidate J335 is preserved and the installed J324/J334 combination stays selected.
- **OBSERVATION:** Ten additional original base items have no expansion/unlockable requirement. Their body/health/hit paths supply extra jumps, shields, proximity damage, healing, safe-travel speed, sprint armor and skill benefits. Shield break and sprint armor require two exact source effect prefabs/slots. Other proc/body-behavior families still need separate native context; arbitrary catalog registration does not make them work.
- **HYPOTHESIS:** Integrate this gameplay chunk with original catalog registration before inventory allocation, original Run.BuildDropTable and existing source purchases/grants/stats/skills, preserving each item's mechanics and chest weights.
- **TASK:** Stage ten source definitions and two effects; broaden the original availability domain to eight common/five uncommon/three rare items, retain truthful unavailable equipment/currency, bind only the measured effect slots and track ownership/cleanup. Compose with J335, build and preserve the first real failure. Device execution awaits the existing APK-update clarification.
- **CONSTRAINTS:** No item grants, forced pickups, altered drop weights/stat formulas, unlock/expansion/entitlement success or copied game implementation. Retain source prerequisites and labeled visual approximations, ignored assets, installed rollback and all Moon/normal checkpoints.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing objective staging, world/reward availability, support effects, observations and existing build recipe/count guard; ignored input/native API/closure/source/build records.
- **TEST COMMAND:** Source typed catalog and exact-editor original catalog/drop-table/support contracts; doctor/preflight;49 safety tests; forced Vulkan ARM64 host build. Whole integrated device run only after update authorization.
- **PASS CONDITION:** Host candidate PASS — all16 source requirements/identities and two lifecycle/slot/component contracts; original8/5/3 Run lists and4096 paired seeded pre-replacement draws agree, covering all16 items. Full Vulkan ARM64 build177.696seconds/zero errors,41 payload/all45 accepted assembly identities;49 tests/doctor/preflight pass. Complete candidate and failed preparations/build archived; installed J324/J334 selection restored, ownership verified and OLED asleep. Replacement gate, real acquisition/health/skills/jumps/death/restart/cleanup and PC appearance remain device gates.
- **FAILURE EVIDENCE TO CAPTURE:** Source identity/requirement mismatch, first import/compiler/AOT or original catalog/selector error, later missing effect/slot/handler or actual-PID gameplay failure; item counts, source stats/jumps/shield and assistance history.
- **STATE/JOURNAL UPDATES REQUIRED:** J336 source dependency decisions and host versus device outcomes; no observed/normal/Moon pointer advance from compilation.
- **DEPENDENCIES:** J335 coherent host candidate, J334 installed rollback; pinned R2API.Items catalog timing and DebugToolkit original drop-list/factory semantics; exact source mechanics and typed provider contracts.

## I09-J337 — Original multishop and shrine purchase loops

- **ID:** I09-J337
- **TITLE:** Original item multishops, chance shrines and blood shrines in the composed stages
- **CONTEXT:** J336 broadens the earned item domain; existing local start/death/restart/results flow is already tested. Moon remains paused and APK-update clarification remains pending.
- **OBSERVATION:** Original TripleShop/TripleShopLarge create three self-generating terminals using BasicPickupDropTable; source persistent callbacks pay/drop/close. Chance shrine retains failure0.4529, two successes and cost refresh; blood shrine uses native PercentHealth/gold. Its legacy ShrineUseEffect already exists in the inherited character recipe. Stock chat invokes the unavailable platform user manager.
- **HYPOTHESIS:** The existing original availability, purchase, droplet, local network and effect contexts can support this broad commerce chunk with owned templates/presentation/layout and truthful optional service boundaries.
- **TASK:** Stage four exact source prefabs and the typed shrine effect; preserve original terminal/shrine generation and callbacks, source tables/weights/costs/health rules. Introduce them at each recovered base-stage entry, observe source purchase/availability/network/item state and clean owned templates/listeners/leases. Compose with J336/J335, build and fix the first real failure.
- **CONSTRAINTS:** No synthetic funds/items/health costs/outcomes, forced success, hidden-item reveal, equipment/unlock/entitlement grant, platform chat/user initialization, source DLL rewrite or authored game-logic replacement. Near-entry placement and disabled stock presentation callbacks remain explicit adapters. Source materials are approximate; no PC parity. Invincibility invalidates blood-health-cost acceptance. Retain installed/Moon/normal rollbacks and idle OLED sleep.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing objective/recipe staging and stage/world lifecycle; one commerce boundary, report and source support hook; ignored typed-location, prefab/source contract, build and candidate receipts.
- **TEST COMMAND:** Doctor/preflight,49 safety tests, exact-editor read-only prefab/callback/type/cost contracts and forced Vulkan ARM64 host build. Integrated device run only after the existing update clarification resolves.
- **PASS CONDITION:** Host candidate PASS — exact four source prefab/component/persistent-callback/cost contracts, zero C# errors,49 tests/doctor/preflight; full Vulkan ARM64 build185.686seconds/zero errors,41 payload/all45 accepted assembly identities and all six scene hashes retained. Complete used candidate and failures archived; installed J324/J334 selection restored, ownership verified and OLED asleep. Native factory/choice/hiding/purchase/closure, chance success/failure/refresh/ejection, blood health/gold, stage lifetime/restart/cleanup and PC appearance require actual device evidence; compilation is insufficient.
- **FAILURE EVIDENCE TO CAPTURE:** First unresolved reference/import/compiler/bundle/AOT failure; actual-PID native factory/purchase/message/lease/cleanup errors when executable; source identity/cost, exact original paid context, health/money/item state, terminal availability and assistance history.
- **STATE/JOURNAL UPDATES REQUIRED:** J337 source versus device scope, first failures and rollback provenance; no observed/normal/Moon gate advance from host build.
- **DEPENDENCIES:** J336 full candidate/J334 installed selection; pinned R2API.Director interactable family/version clues and DebugToolkit original factories; exact original source contracts. T04 support is limited to correcting the measured duplicate explicit bundle owner.


## I09-J338 — Natural loss, restart and cold Android results

- **ID:** I09-J338
- **TITLE:** Exercise complete unassisted loss/restart/menu/local-result flow without another APK
- **CONTEXT:** J337 is host-only; the installed J324/J334 game already supports local application and original result paths. Moon remains paused.
- **OBSERVATION:** Prior stage windows use assistance and do not validate natural death. Local ledger validates primary then reads backup, with pending writes and native File.Replace.
- **HYPOTHESIS:** The same installed game can complete natural losses, fresh restart and cold owned result reload; real interrupted/damaged data can expose the first persistence flaw.
- **TASK:** Back up owned results, run two ordinary neutral-input enemy losses, restart/return menu, cold-load valid/partial-pending/invalid-primary generations and restore original data.
- **CONSTRAINTS:** One APK installation limit; no synthetic damage/ending/grants/debug acceleration, Steam profile/service success, Moon progression or source appearance claims. Inject faults only into backed-up owned Android ledger files; preserve all XML and failing attempts.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Ignored owned launch/result/evidence and file-generation records; state/journal/backlog/milestones summaries only.
- **TEST COMMAND:** Preflight; same-owned-APK launch/sync/capture with no install dispatch; exact current-PID observations, original death/report/cleanup, file hashes, cold reload and idle display check.
- **PASS CONDITION:** Scoped PASS: two natural StandardLoss reports, restart/menu/full completed-session cleanup, valid cold primary with two reports and ignored partial pending, zero actual-PID errors, original data/hash restoration and idle OLED sleep. Robust invalid-primary recovery FAIL: backup loads but diagnostics and later-save policy need J339 repair. No stock-profile or normal-victory acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** Real PID/phase/debug history, death/report/context/cleanup errors; primary/backup/pending/XML hashes and original versus injected generations; stale-PID and touch evidence separately.
- **STATE/JOURNAL UPDATES REQUIRED:** J338 scoped device successes and first failed recovery policy; private result-only observation pointer, no normal/visual/Moon advance.
- **DEPENDENCIES:** Installed J324/J334 owned combination; native RunReport/statistics, current Android ledger and pinned ProperSave filesystem policy boundary.


## I09-J339 — Safe recovery of the Android run ledger

- **ID:** I09-J339
- **TITLE:** Retain rejected data and valid backup before later result saves
- **CONTEXT:** J338 proves natural loss/restart/menu/cold valid results but rejects robust damaged-primary recovery; J337 is the coherent host gameplay/graphics candidate.
- **OBSERVATION:** Loaded backup leaves invalid primary in place, so later File.Replace can overwrite the valid backup with it; caught validation also marks terminal firstFailure.
- **HYPOTHESIS:** A validated recovered primary committed before later saves preserves usable generations without changing original report logic or stock profiles.
- **TASK:** Add only the measured recovery sequence and structured classification to the owned ledger; retain rejected bytes, validate before mutation, handle missing primary and reject both invalid. Compose and build over J337.
- **CONSTRAINTS:** Never change native report/statistics, Steam profiles, entitlement/identity, source assets, debug labels or Moon state. Do not accept pending data as committed. Original generations/failed evidence stay preserved; no additional APK installation pending clarification.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing IntegratedResultsBoundary owned ledger/report, ignored actual-report fixture replay/candidate/build archives and state summaries.
- **TEST COMMAND:** Exact-editor replay of genuine J338 file generations including next save/interruption/both-invalid; doctor/preflight,49 tests and forced Vulkan ARM64 build. Later device replay only after APK update authorization.
- **PASS CONDITION:** Host candidate PASS: all replayed file contracts,49 tests/doctor/preflight, zero editor errors and composed Vulkan ARM64 build182.556seconds/zero errors.41 payload files/all45 accepted assembly identities/all six scene hashes retained, complete candidate archived and installed J324/J334 restored/verified with OLED asleep. Device fault-recovery acceptance remains open; no stock-profile, normal victory or visual parity claim.
- **FAILURE EVIDENCE TO CAPTURE:** First file/validation/rename/build error; rejected/primary/backup/pending/XML bytes/hashes, restoration, recovery fields, APK/payload/assembly identities and actual-PID device outcome when permitted.
- **STATE/JOURNAL UPDATES REQUIRED:** J339 host versus device outcomes and inherited J337 content; retain J338's scoped results pointer and all observed/Moon/normal rollbacks.
- **DEPENDENCIES:** J338 real persistence failure/genuine reports, J337 composed host base; current owned ledger and pinned ProperSave policy boundary.


## I09-J340 — Unassisted original first-stage loop

- **ID:** I09-J340
- **TITLE:** Exercise original combat, earned loot, boss, normal charge and exit without another APK
- **CONTEXT:** J339 is a host candidate; J338 validates natural loss/restart/results. Moon remains paused and the one installed J324/J334 world is available.
- **OBSERVATION:** Previous recent route/presentation windows use invincibility/damage/charge assistance, excluding normal combat and holdout acceptance.
- **HYPOTHESIS:** Ordinary diagnostic inputs can complete one native objective/transition with all assistance off and expose visual/runtime dependencies.
- **TASK:** Run the composed first stage unassisted, capture original boss/holdout/reward/exit and authority/inventory/XP continuity into a ten-second Wetland window; preserve the first failure.
- **CONSTRAINTS:** No APK install, synthetic damage/items/charge/progression, Moon work, physical-input/stock-platform/normal-victory claim or graphics parity. Keep original Android results and all known-good snapshots intact; sleep OLED after stop.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Ignored existing-APK launch/observations/captures and scoped checkpoint; state/journal/backlog/milestone/visual summary only.
- **TEST COMMAND:** Preflight; same-owned-APK launch/sync with all debug options false; actual-PID original objective/stage observations/logs/captures/hash and idle power checks.
- **PASS CONDITION:** Scoped PASS: original2100-HP boss death/source90-second charge/reward/exit, original count1/Wetland entry,208.69seconds/50 kills, authority/inventory3/XP114 continuity, zero runtime errors and no installation. Boss opaque effect cards remain a visual failure; cold stop does not establish full harness teardown.
- **FAILURE EVIDENCE TO CAPTURE:** First game/native/authority/objective error or genuine loss; assistance history, source duration/FSM/boss/reward/exit and transition state; actual stage/object visual context and old result hashes.
- **STATE/JOURNAL UPDATES REQUIRED:** J340 actual scoped outcome/visual failure and unassisted-stage pointer; no normal-victory/Moon/formal/visual advancement.
- **DEPENDENCIES:** Installed J324/J334; current original director/teleporter/Run/authority contracts and pinned R2API.Director observation knowledge.
