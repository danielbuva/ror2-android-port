# Capability gates

Canonical policy: DEVELOPMENT_PLAN.md. Each gate requires stored real-device evidence, not compilation alone. Shared procedure: preflight → minimal change/build → install/runtime-path discovery/sync/run → structured logs/crash/state plus relevant visual capture → first-failure classification → state/journal/commit. Query live storage on each install/size increase and retain prior APK/payload; never change storage or unrelated data.

| Gate | Status | Objective, scope and acceptance | Dependencies / principal risk |
| --- | --- | --- | --- |
| L0–L2 baseline | PASS, T01 reproduced | Accepted input; exact toolchain; original utility AOT, converted mesh on adopted data; GLES/Vulkan historical proof, fresh Vulkan capture | T01; not game readiness |
| L3 managed execution | PASS — full original DLL, ten assertions × three cold launches | Original RoR2 slice expected results, three cold launches ≥30 s; preserve API/type identity | T02/T05/T06/T07; AOT/middleware |
| L4 recovered scene | PASS — isolated content J28; diagnostic binding/material, original loader deferred | loadingbasic plus dependency-rich animated prefab on device; required GUID/local fileID/script/subasset/catalog audit | L3; serialization; T10 before large data |
| L5 lawful startup/menu | OPEN — isolated controller/avatar loaders pass J33–J34; startup unexecuted | Observed initialization, truthful services, optional no-audio lifecycle, Android profile/content roots, original menu navigation | L4/L9 foundation; entitlement/native lifecycle |
| L5.5 original simulation | OPEN | Original Commando master/body/authority/state ticks; deterministic movement then built-in controls; three cold launches ≥60 s | L5; see detailed plan; no complete stage needed |
| L6 controllable stage | OPEN | Introduce whole original stage to proven simulation; handheld movement, camera, aim, default abilities, collision/animation | L5.5; catalog/stage integration |
| L7 combat/complete stage | OPEN | Enemy/damage → pickup/interactable → director → teleporter; normal complete stage, readable G4 gameplay | L6; authority/effects/simulation |
| L8 complete offline victory | OPEN | Route transitions/lifetime/finale/victory/results/return menu/profile; normal uninterrupted victory then second stable run | L7/L9; late dependencies/memory |
| L9 profile | OPEN | Fresh Android-only foundation before L5; cold reload, interrupted write, update retention, backup/restore by L8 | Path audit; host Steam profile immutable |
| L10 audio | OPEN | Early lawful engine/bank/codec access; later init bank, SFX/music/spatial events/callbacks/shutdown | Authorized compatible engine; banks/authoring |
| L11 graphics | OPEN beyond G2 | Minimum surface/terrain/character/UI/hazard families with L4–L7; G5/G6 parity later | Required scene families; shaders/dummy export |
| L12 performance | OPEN | Warm stage/combat, transitions, memory and thermals; optimize measured bottleneck, stable 30 FPS first | Meaningful gameplay; final after L8 |
| L13 transformation | OPEN | Clean ignored regeneration/provenance/cache checks; same accepted input; real second-build compatibility when available | Stable route; update/toolchain |

Replan at L3, L4, L5.5, L6, L7, L8. No gate advances from a stripped empty build or synthetic completion. Audio/visual parity, broader routes/devices, T30/60 FPS, distribution and remote services remain later unless a measured dependency requires them.

## Evidence

T01: work/runs/20260913T020341.114229Z-46130c90d7a1, visible Vulkan geometry, utility marker, ARM64 IL2CPP, adopted placement and cleanup. Doctor/preflight and six host tests passed. LAST_KNOWN_GOOD_RUNTIME under work/checkpoints binds baseline APK and payload; no scene/simulation/playable/run pointer exists yet.
