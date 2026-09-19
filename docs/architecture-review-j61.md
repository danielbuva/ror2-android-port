# Architecture review preparation — J61

J61 satisfies ADR-001 revisit condition **(4)**: “a required middleware license/runtime cannot be obtained and no legitimate bounded replacement exists.” The required dependency is the original Steam client path reached by `PlatformSystems.Init`, not the desktop ownership record: the preserved Facepunch binding lacks an Android ARM64 implementation, and no rights-holder Android runtime/depot/launch integration is available.

## Decision to make

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

No listed item is a replacement `NEXT` experiment. The next experiment requires the architecture-review decision and its own bounded contract.

## Guardrails for the reviewer

Read `PORTING_STATE.md`, ADR-001, `docs/DEVELOPMENT_PLAN.md`, `docs/l5b-7b-platform-runtime-feasibility.md`, `docs/PORTING_JOURNAL.md` J52–J61, and `docs/community-prior-art.md`. Preserve accepted L3/L4, Rewired, Burst, filesystem, audio-resource, and J55 results. Do not repeat J58/J60, alter the original installation, or infer ownership from the native-load failure. If proposing a new RoR2-specific mechanism, follow the prior-art-first rule and state the first failure it prevents.
