# Architecture review — J61 decision (J62)

J61 satisfies ADR-001 revisit condition **(4)**: “a required middleware license/runtime cannot be obtained and no legitimate bounded replacement exists.” The required dependency is the original Steam client path reached by `PlatformSystems.Init`, not the desktop ownership record: the preserved Facepunch binding lacks an Android ARM64 implementation, and no rights-holder Android runtime/depot/launch integration is available.

## Reviewed question

Decide whether Architecture C remains the active but **platform-deferred** laboratory direction, or whether its controlled Architecture A fallback needs one discriminating trial. Neither choice authorizes a fake/offline Steam client, a changed backend string, copied desktop library, fabricated ownership, or relaxed entitlement/authentication checks.

Architecture A is not a solution to J61 by itself. A source-reconstruction trial is justified only if it discriminates an independent C limitation while preserving the lawful platform boundary; it cannot establish lawful startup/menu by replacing the unavailable Steam service.

## What J61 blocks

- Continuing the original coroutine through the coupled platform initialization and original Steam client load.
- Original Steam-backed cloud/profile flow, entitlement registration, achievements, and platform-dependent startup/menu proof.
- L5 acceptance and therefore L5.5 character simulation, L6–L8.

## Work that remains independently eligible, but is not selected here

- **L9 profile foundation:** J39/J57 only prove isolated owned writable roots and temporary config access. Actual original profile serialization/cold reload remains coupled to the Steam-backed save path and cannot be promoted from those proofs.
- **L10 no-audio lifecycle:** J52 asset loading, J53 native unavailability, and J55’s bounded early guard stand. Later query/dialog/bank-wait/shutdown obligations can be examined independently, but do not unlock platform startup.
- **L11 graphics/content:** original skin application remains bounded/inactive and Windows shader compatibility remains unresolved. Further independently scoped content/material evidence is permitted by the roadmap, not selected as a substitute for L5.
- **T10 storage scale:** remains conditional before multi-GiB content work.

These were eligible alternatives at J61. J62 selects only the read-only L10 continuation below; the others remain unselected.

## Guardrails for the reviewer

Read `PORTING_STATE.md`, ADR-001, `docs/DEVELOPMENT_PLAN.md`, `docs/l5b-7b-platform-runtime-feasibility.md`, `docs/PORTING_JOURNAL.md` J52–J61, and `docs/community-prior-art.md`. Preserve accepted L3/L4, Rewired, Burst, filesystem, audio-resource, and J55 results. Do not repeat J58/J60, alter the original installation, or infer ownership from the native-load failure. If proposing a new RoR2-specific mechanism, follow the prior-art-first rule and state the first failure it prevents.

## J62 decision — retain C; no Architecture A trial

Architecture C remains the active conditional laboratory direction, with its platform-dependent portion deferred. ADR-001 condition (4) requires reassessment, not replacement. J61 establishes an access/runtime boundary shared by A and C. Recompiling the same semantics cannot supply that dependency. No reviewed evidence establishes an independent C limitation for an A comparison: original managed execution/type preservation and bounded recovered content have passed; J11 attributed the Rewired failure to exporter metadata, and J14's package result remains accepted. Wider AOT/serialization compatibility is still unproven, not a measured failure. Consequently no source-reconstruction trial is authorized now.

An A trial would become justified only after a concrete independent C failure is isolated (for example, a required original method cannot AOT with retained semantics, or a required serialized identity cannot be preserved), with one same-input, same-assertion comparison that source reconstruction could actually discriminate. J61 alone does not meet that test. Platform startup/menu, Steam-backed profile flow, L5 acceptance and L5.5–L8 remain blocked.

Select **L10-a / L5b-5c follow-up: read-only unavailable-audio lifecycle audit**. This completes already-recorded J53/J55 obligations rather than inventing a new capability. L9's isolated config foundation already passes while original profile flow remains blocked; a further profile probe first needs its own independence contract. L11 is eligible but broadens content/material scope. T10 has no imminent multi-GiB payload trigger. Audio has a concrete outstanding query/dialog, pending-bank and teardown contract on the accepted candidate, so documenting it has the smallest scope and clearest evidence target. This is an investigation, not permission to advance startup or implement a guard.

### Small read-only inspection performed for this decision

Re-read J52–J61 and current roadmap, milestones, risks and prior art. In the recorded original RoR2 source receipt `work/decompiled/RoR2/0993a9f3fcd8540d/`, WwiseIntegrationManager.Init guards prefab requests with noAudio, while the later RoR2Application.InitializeGameRoutine calls AkSoundEngine.IsInitialized outside that guard and catches missing native code with a Windows-runtime error dialog. RoR2Application.OnApplicationQuit invokes shutdown subscribers and the Steam unload delegate; OnDestroy also references platform state. These are static observations, not new device outcomes or a complete reachability audit. They rule out casually resuming the coroutine or using whole-application teardown as an isolated audio probe.

Inspected the pinned R2API SoundAPI.cs at `f539511eabf87f02afddb5a83cafd2f4704c85ad` in `work/reference-repos/risk-of-thunder__R2API/`: bank loading is hooked after engine initialization, and bank load/unload retains native results and memory lifetime obligations. This is useful lifetime/API prior art, not an Android implementation or proof of behavior in the accepted game input. No community code was copied.

`./dev doctor` and the detailed bootstrap doctor were run. The sole reported failed bootstrap check is zero registered Unity MCP editor instances; input acceptance, tools and device checks passed. No editor was opened, no build/run attempted, and no capability/checkpoint advanced. Re-run health checks before runtime work; a missing editor does not invalidate this source/document review.

### Bounded investigation contract and transfer of control

- **Hypothesis:** the remaining unavailable-audio obligations can be attributed to exact current-input call sites and lifetimes, distinguishing obligations excluded by J55 from those still reachable or unresolved, without invoking platform startup. This does not hypothesize that a single new guard fixes them.
- **Scope:** the original startup status query/error-dialog path; the audio-prefab callbacks and bank loaders identified by J50–J53; pending-bank waits and their producers; audio shutdown registrations/cleanup reachable from those components. Trace only immediate dependencies needed to explain these paths. Do not perform a whole-game audio rewrite or exhaustive gameplay event audit.
- **Evidence:** revalidate accepted input/source receipts and J55 transformation identity; consult preserved J50–J55 artifacts before repeating analysis. Produce a source-hashed local call-site matrix with caller, condition, native boundary, pending-counter producer/consumer, callback registration/removal, teardown owner, platform/profile coupling and observed-versus-inferred status. Cite pinned R2API bank lifetime prior art and exact local methods; publish authored summaries only. Explicitly record unresolved indirect calls rather than claiming absence from a text search.
- **First-failure target:** the earliest uncovered native query, pending wait without an enabled producer, or cleanup/native call in this bounded unavailable-audio lifecycle. Order by the original call graph, not search-result order. If the path cannot be isolated from platform/profile state, report that dependency as the result; do not execute or skip it.
- **Truthful completion:** every scoped obligation is traced or explicitly unresolved with evidence and a reason. Record whether a single isolated runtime probe can be specified; any proposed probe must state real prerequisites, native-unavailable outcome, fresh-process requirements, unchanged platform semantics and assertions. A negative independence result is valid. Audit completion is not runtime safety, full no-audio, audio capability, L5 or menu acceptance.
- **Rollback:** read-only against input, generated projects, assemblies, device and checkpoints; only authored audit/state documents and ignored evidence may be added. Preserve J52 unmodified-assembly and J55/J57 accepted rollback receipts and all failures. No pointer advances, package changes, editor mutation or new transformation.
- **Owner:** Terra Medium executes this evidence-collection contract autonomously as sole driver, then stops. Astra Low selects any runtime candidate after reviewing the matrix; that architectural choice is not delegated. Terra must stop early on contradictory/stale evidence, ambiguous causal results, new subsystems, broader scope, changed platform/authentication/ownership, serialization or middleware semantics, any need to weaken assertions, or a second supported candidate failing the same boundary. Preserve evidence and commit/push a coherent checkpoint before returning control. No concurrent drivers.

## J64 continuation

J61–J63 remain accepted. The earlier read-only-only transfer is complete and superseded by the L11-a executable contract in l11-commando-material-device-contract.md. Gate dependencies govern acceptance; they do not prohibit a separately bounded independent simulation precursor. J64 compares that candidate with graphics/persistence and selects skin material assignment plus Vulkan rendering. Terra should construct and run it, not extend the earlier audits.
