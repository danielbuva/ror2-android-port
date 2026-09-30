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
