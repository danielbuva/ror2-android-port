# Capability gates

Canonical policy: DEVELOPMENT_PLAN.md. Each gate requires stored real-device evidence, not compilation alone. Shared procedure: preflight → minimal change/build → install/runtime-path discovery/sync/run → structured logs/crash/state plus relevant visual capture → first-failure classification → state/journal/commit. Query live storage on each install/size increase and retain prior APK/payload; never change storage or unrelated data.

| Gate | Status | Objective, scope and acceptance | Dependencies / principal risk |
| --- | --- | --- | --- |
| L0–L2 baseline | PASS, T01 reproduced | Accepted input; exact toolchain; original utility AOT, converted mesh on adopted data; GLES/Vulkan historical proof, fresh Vulkan capture | T01; not game readiness |
| L3 managed execution | PASS — full original DLL, ten assertions × three cold launches | Original RoR2 slice expected results, three cold launches ≥30 s; preserve API/type identity | T02/T05/T06/T07; AOT/middleware |
| L4 recovered scene | PASS — isolated content J28; diagnostic binding/material, original loader deferred | loadingbasic plus dependency-rich animated prefab on device; required GUID/local fileID/script/subasset/catalog audit | L3; serialization; T10 before large data |
| L5 lawful startup/menu | OPEN — J55 reaches Addressables; J61 blocks the current original Steam/platform route before ownership checks | Observed initialization, truthful services, optional no-audio lifecycle, Android profile/content roots, original menu navigation | L4/L9 foundation; entitlement/native lifecycle; ADR-001 review |
| L5.5 original simulation | OPEN | Original Commando master/body/authority/state ticks; deterministic movement then built-in controls; three cold launches ≥60 s | L5; see detailed plan; no complete stage needed |
| L6 controllable stage | OPEN | Introduce whole original stage to proven simulation; handheld movement, camera, aim, default abilities, collision/animation | L5.5; catalog/stage integration |
| L7 combat/complete stage | OPEN | Enemy/damage → pickup/interactable → director → teleporter; normal complete stage, readable G4 gameplay | L6; authority/effects/simulation |
| L8 complete offline victory | OPEN | Route transitions/lifetime/finale/victory/results/return menu/profile; normal uninterrupted victory then second stable run | L7/L9; late dependencies/memory |
| L9 profile | OPEN — J39/J57 isolate roots/config; real original save/cold reload unproven and Steam-backed profile flow blocked by J61 | Fresh Android-only foundation before L5; cold reload, interrupted write, update retention, backup/restore by L8 | Path audit; host Steam profile immutable; lawful platform/profile boundary |
| L10 audio | OPEN | Early lawful engine/bank/codec access; later init bank, SFX/music/spatial events/callbacks/shutdown | Authorized compatible engine; banks/authoring |
| L11 graphics | L11-a PASS J66: original Commando material assignment and bounded Vulkan albedo/emission; broader families open | Minimum surface/terrain/character/UI/hazard families with L4–L7; G5/G6 parity later | Required scene families; shaders/dummy export |
| L12 performance | OPEN | Warm stage/combat, transitions, memory and thermals; optimize measured bottleneck, stable 30 FPS first | Meaningful gameplay; final after L8 |
| L13 transformation | OPEN | Clean ignored regeneration/provenance/cache checks; same accepted input; real second-build compatibility when available | Stable route; update/toolchain |

Replan at L3, L4, L5.5, L6, L7, L8. No gate advances from a stripped empty build or synthetic completion. Audio/visual parity, broader routes/devices, T30/60 FPS, distribution and remote services remain later unless a measured dependency requires them.

## Evidence

T01: work/runs/20260913T020341.114229Z-46130c90d7a1, visible Vulkan geometry, utility marker, ARM64 IL2CPP, adopted placement and cleanup. Doctor/preflight and six host tests passed. LAST_KNOWN_GOOD_RUNTIME under work/checkpoints binds baseline APK and payload; no scene/simulation/playable/run pointer exists yet.

J62 architecture review retains C as platform-deferred. J63 completes L10-a read-only lifecycle attribution: the later native query/dialog, bank producer/callback lifetime, and platform-coupled teardown remain unproven, and no runtime candidate is selected. No milestone advances; L5, Steam-backed profile startup and L5.5 remain blocked. See architecture-review-j61.md and l10-a-unavailable-audio-lifecycle-audit.md.

J64: L11-a is selected for constructive device execution. Independent simulation precursors may be scoped before L5, but cannot pass formal L5.5. No milestone advances from this selection; see l11-commando-material-device-contract.md.

S01 / J68 independently verifies original EntityStateMachine queue, update/fixed scheduling, automatic ticks and cleanup on Android. It does not advance formal L5.5: actual character states, movement and authority remain unproven.

S02 / J69 verifies original CharacterDirection facing and its authority guard using a real local server-owned identity. Original movement, full character authority and L5.5 remain unproven.

S03–S06 / J70 pass independent input-edge/normalization and inactive motor output/acceleration tests in four fresh Android processes. No translation, collisions, normal body stat calculation or L5.5 acceptance is implied.

S07–S11 / J71 pass shipped kinematic solver integration, wall stop/slide, stable grounding and ungrounding in five separate Android processes. An authored diagnostic velocity controller drives these probes; original CharacterMotor/body integration and L5.5 remain unproven.

S12/S14 (J72) and S13 (J73) pass original CharacterMotor-driven movement/braking, Jump-method impulse integration without gravity, and wall contact. S15 fails in original OnLanded with a null-reference exception; landing and full character simulation remain open.

S16–S19 / J75–J77 establish bounded original landing context and resolve the J72 null-reference for this fixture. Diagnostic artifact catalog and inactive body/Run remain; fall damage, effects/audio, normal character initialization and L5.5 are not accepted.

S20–S24 / J78 pass original gravity and GenericCharacterMain input-driven movement/stop in isolated diagnostic fixtures. This is original state-to-motor execution, while full Commando/master lifecycle, normal stats/catalogs, physical controls and formal L5.5 remain open.

S25–S28 / J79 pass source-gravity motor jumping and original grounded state movement, reversal, stopping and wall contact (101 assertions). S26 accepted only after isolated same-APK retry following device disconnection. Diagnostic fixture scope remains; input-driven jump inventory/networking and full L5.5 remain open.
