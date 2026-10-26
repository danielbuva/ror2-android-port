# Capability gates

Gate definitions and current status only. Each gate needs stored real-device evidence, not
compilation alone; results are recorded in the [journal](PORTING_JOURNAL.md) and summarised in
[PORTING_STATE.md](../PORTING_STATE.md). Policy: [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md).
The previous version, with per-entry status reports and the evidence log, is archived in
[history/milestones-2026-10-16.md](history/milestones-2026-10-16.md).

Shared procedure: preflight → minimal change/build → install/runtime-path discovery/sync/run →
structured logs/crash/state plus relevant visual capture → first-failure classification →
journal/state/commit. Query live storage on each install or size increase and retain the prior
APK and payload; never change storage or unrelated data.

Status as of 2026-10-16 (J504). Status cells summarise; the journal entries they cite hold the evidence.

| Gate | Status | Objective, scope and acceptance | Dependencies / principal risk |
| --- | --- | --- | --- |
| L0–L2 baseline | PASS — T01 reproduced | Accepted input; exact toolchain; original utility AOT, converted mesh on adopted data; GLES/Vulkan historical proof, fresh Vulkan capture | T01; not game readiness |
| L3 managed execution | PASS — full original DLL, ten assertions × three cold launches | Original RoR2 slice expected results, three cold launches ≥30 s; preserve API/type identity | T02/T05/T06/T07; AOT/middleware |
| L4 recovered scene | PASS — isolated content (J28); original loader deferred | loadingbasic plus dependency-rich animated prefab on device; required GUID/local fileID/script/subasset/catalog audit | L3; serialization; T10 before large data |
| L5 lawful startup/menu | OPEN — original Steam/platform startup blocked; the recovered Android menu (J489) is not original menu navigation | Observed initialization, truthful services, optional no-audio lifecycle, Android profile/content roots, original menu navigation | L4/L9 foundation; entitlement/native lifecycle; ADR-001 review |
| L5.5 original simulation | OPEN as a formal gate (needs L5); original simulation runs in assisted integrated play | Original Commando master/body/authority/state ticks; deterministic movement then built-in controls; three cold launches ≥60 s | L5; see detailed plan; no complete stage needed |
| L6 controllable stage | OPEN — all 11 base survivors reach Lakes (J471, assisted); skills, unlocks, physical controls and visuals unproven | Introduce whole original stage to proven simulation; handheld movement, camera, aim, default abilities, collision/animation | L5.5; catalog/stage integration |
| L7 combat/complete stage | OPEN — original damage and default skills under diagnostic input (J157/J158); normal complete stage open | Enemy/damage → pickup/interactable → director → teleporter; normal complete stage, readable G4 gameplay | L6; authority/effects/simulation |
| L8 complete offline victory | OPEN | Route transitions/lifetime/finale/victory/results/return menu/profile; normal uninterrupted victory then second stable run | L7/L9; late dependencies/memory |
| L9 profile | PARTIAL — native Android save, reload and recovery (J436); persistent-stat and event achievements on genuine events (J437, J500–J503); Steam/cloud open | Fresh Android-only foundation before L5; cold reload, interrupted write, update retention, backup/restore by L8 | Path audit; host Steam profile immutable; lawful platform/profile boundary |
| L10 audio | OPEN — composed playback unqualified ([J919](history/journal-J1-J1177/PORTING_JOURNAL.md#j919--measure-the-selected-original-music-output-on-the-r20-player)) | Original SFX/music/spatial events, callbacks and complete shutdown/restart on Android | Authorized runtime and original bank/context compatibility |
| L11 graphics | PARTIAL — L11-a PASS (J66); integrated source-informed material approximations across stages (J324–J335); PC parity open | Minimum surface/terrain/character/UI/hazard families with L4–L7; G5/G6 parity later | Required scene families; shaders/dummy export |
| L12 performance | OPEN — 120 Hz, about 116 FPS first stage (J449–J451); crowded later stages below 60 FPS; memory growth and thermals open | Warm stage/combat, transitions, memory and thermals; optimize measured bottleneck, stable 30 FPS first | Meaningful gameplay; final after L8 |
| L13 transformation | OPEN | Clean ignored regeneration/provenance/cache checks; same accepted input; real second-build compatibility when available | Stable route; update/toolchain |

Replan at L3, L4, L5.5, L6, L7 and L8. No gate advances from a stripped empty build or synthetic
completion. Moon/finale waits for manual input; composed audio remains unqualified; sustained 60 FPS,
distribution and remote services come later.
