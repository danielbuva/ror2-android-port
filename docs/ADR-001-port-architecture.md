# ADR-001 — Hybrid conversion and selective assembly preservation

Status: **accepted for laboratory direction; gameplay viability conditional**. Date: 2026-09-12 PDT.

Choose architecture C: a clean Android IL2CPP player, local content reconstruction/retargeting, explicit platform adapters, and selective preservation of original managed assemblies as build inputs. Keep architecture A (controlled source reconstruction) as fallback. Reject unchanged Windows Mono runtime/content surgery as primary.

Evidence: complete input inventory, 143 successful decompilations, a first full RoR2 recompile with 11 errors, a complete AssetRipper export with dummy shaders, and a real ARM64 device proof executing original SimpleJSON code and rendering a recovered game mesh from a separately synced Android bundle on adopted storage. The Windows shader sample fails to load in the Android player. See `architecture-options.md` and the run artifacts referenced there.

Consequences: source patches are targeted and input-version gated; extracted assets remain local; native services are isolated deliberately; Android content is built with exact Unity 2021.3.33f1. IL2CPP changes require APK builds even when DLLs are preserved. Pure asset changes can use separate payload sync. Small proof success must not be extrapolated to whole-game AOT/serialization compatibility.

Revisit when: (1) the original RoR2 dependency closure cannot AOT/link without pervasive semantic rewriting; (2) type/serialization identity cannot be retained through selective preservation; (3) reconstruction loses necessary assets/references; (4) a required middleware license/runtime cannot be obtained and no legitimate bounded replacement exists. Prefer a controlled source reconstruction trial before architecture replacement.

J61 invokes condition (4): the preserved Steam binding has no compatible Android ARM64 runtime path, and no rights-holder Android Steam integration is available. This requires an architecture review, not an automatic move to Architecture A. Any controlled reconstruction trial must discriminate an independent Architecture C limitation; reconstruction cannot lawfully replace ownership, authentication, entitlement, licensing, or the absent authorized platform runtime. Until review selects a bounded contract, retain Architecture C as platform-deferred and keep original platform-dependent startup stopped.

Follow-up evidence: the full exported closure fails IL2CPP VTable construction in Rewired_Core and Rewired_Windows, and editor Play Mode crashes through Burst/Collections. The next gate is a lawful Android-capable Rewired boundary plus compatible Burst/Collections handling, followed by a repeated minimal closure build. Preserve type identities and measure the next failure. Do not begin a broad game-source rewrite to solve an unmeasured hypothesis.
