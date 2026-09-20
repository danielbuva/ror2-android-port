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
| S12 — Original integrated motion | Original acceleration gives 4.62m in 1s at diagnostic acceleration10/speed7, then brakes to zero. | PASS — J72 |
| S13 — Original wall callback | Original motor/solver stops at wall and clears disable-air-control collision flag. | PASS — J73, corrected initial-velocity fixture |
| S14 — Original Jump method | Diagnostic speed7/power5 produces velocity(7,5,0), integrated for0.5s without gravity. | PASS — J72 |
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
