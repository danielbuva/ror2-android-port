# Architecture risk register

Likelihood is uncertainty, not a statistical estimate. Each risk is resolved by a bounded experiment, not optimistic inference. Follow DEVELOPMENT_PLAN.md and ADR-001.

| Risk | Uncertainty / impact | Early detection | Mitigation/fallback |
| --- | --- | --- | --- |
| Managed AOT/type identity | High / architecture-invalidating | T02–T07; required prefab contract | Selective boundary; same-probe bounded C#9 comparison |
| Entitlement/offline | High / gameplay-blocking | T02 startup reachability then observed initialization | Truthful mandatory checks; block dependent startup if no legitimate route |
| Middleware/native/legal distribution | High / capability-blocking | Exact authorized package/API/ELF access and load probe | User-supplied authorized package or bounded lawful alternative; tooling-only repo |
| Burst/Unity | High / editor or runtime-blocking | Separate direct-call package and Android probe | Compatible artifacts/valid fallback; exact editor stays pinned |
| Content/shaders | High / scene/readability-blocking | Required reference closure and one material family | Narrow repair; progressive replacement, parity later |
| Wwise banks/codecs | High / audio-blocking | Matching init bank/event probe; authoring inventory | Explicit no-audio where functional; no assumed regeneration |
| Input/local networking | Medium–high / simulation-blocking | L5.5 separates authority/ticking/scripted input/handheld | Retain local HLAPI and action contracts; remote transport separate |
| Android storage scale | Unmeasured / install/transfer loss | T10 before large content; every install live capacity/backing | Small APK, changed sync, staged dependent generations and host rollback |
| Memory/performance/thermal | Unmeasured / usability | Samples at gates, warmed stage/combat and transitions | Fix measured bottleneck; stable 30 FPS, avoid polish first |
| Input updates/toolchain drift | High / transforms fail | Accepted hashes, semantic match reports, second real build | Reject unknown input; explicit review; prior outputs retained |
| T30 custom driver | Unmeasured / optional graphics | Separate per-app loader/runtime identification | Passing Vulkan device driver first; no system-wide modification |

After two supported candidates at a boundary fail, reassess the hypothesis. Reconstruction cannot cure missing permissions, entitlement, authoring inputs or storage. Only real-device evidence advances capability gates.

L3 update (J11–J20): the Rewired AOT failure was induced by exported metadata; original slots and the full original RoR2 assembly pass on ARM64. Ten original game-method assertions repeat across three cold launches. Managed execution uncertainty is substantially reduced; serialized prefab identity and wider runtime/native contracts remain open. Pinned Collections/Burst representative jobs pass editor and device; full reconstructed Play Mode is still not established.
