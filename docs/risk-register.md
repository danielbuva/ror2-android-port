# Architecture risk register

Likelihood is uncertainty, not a statistical estimate. Each risk is resolved by a bounded experiment, not optimistic inference. Follow DEVELOPMENT_PLAN.md and ADR-001.

| Risk | Uncertainty / impact | Early detection | Mitigation/fallback | Status (2026-10-16) |
| --- | --- | --- | --- | --- |
| Managed AOT/type identity | High / architecture-invalidating | T02–T07; required prefab contract | Selective boundary; same-probe bounded C#9 comparison | Largely retired: the full original assembly closure runs on ARM64 (L3, J431) |
| Entitlement/offline | High / gameplay-blocking | T02 startup reachability then observed initialization | Truthful mandatory checks; block dependent startup if no legitimate route | Open by design: Steam startup unavailable; Android-only offline profile, nothing fabricated |
| Middleware/native/legal distribution | High / capability-blocking | Exact authorized package/API/ELF access and load probe | User-supplied authorized package or bounded lawful alternative; tooling-only repo | Local authorized SDK integration has bounded device output evidence ([J946](PORTING_JOURNAL.md#j946--pass-r25-controls-and-retain-the-recurring-lightningstake-defect)); full lifecycle/distribution scope remain open; tooling-only repository |
| Burst/Unity | High / editor or runtime-blocking | Separate direct-call package and Android probe | Compatible artifacts/valid fallback; exact editor stays pinned | Retired for current scope (J11–J20 boundary) |
| Content/shaders | High / scene/readability-blocking | Required reference closure and one material family | Narrow repair; progressive replacement, parity later | Reduced: source-informed approximations run; PC parity unproven |
| Wwise banks/codecs | High / audio-blocking | Isolated original pickup output passes J845; composed source music output has matching identity and bounded nonzero samples in [J946](PORTING_JOURNAL.md#j946--pass-r25-controls-and-retain-the-recurring-lightningstake-defect) | Measure track/state/native outcomes before changing source behavior; require composed playback and complete Android lifecycle evidence | Open: composed audio unqualified |
| Original projectile physics | Intermittent / combat correctness | Current-process collider errors and bounded native stake history | Preserve first invalid state; require causal spawn/hit/transform join before a behavior change | Open: LightningStake nonfinite transforms recur in both R25 controls ([J946](PORTING_JOURNAL.md#j946--pass-r25-controls-and-retain-the-recurring-lightningstake-defect)); producer remains unmeasured |
| Input/local networking | Medium–high / simulation-blocking | L5.5 separates authority/ticking/scripted input/handheld | Retain local HLAPI and action contracts; remote transport separate | Reduced: local HLAPI authority retained; Nova bridge adapted; Rewired licensing open |
| Android storage scale | Unmeasured / install/transfer loss | T10 before large content; every install live capacity/backing | Small APK, changed sync, staged dependent generations and host rollback | Managed: adopted storage, receipted retirement of superseded outputs |
| Memory/performance/thermal | Unmeasured / usability | Samples at gates, warmed stage/combat and transitions | Fix measured bottleneck; sustained 60 FPS is release acceptance | Open: crowded later stages below 60 FPS; managed growth across sessions; no thermal acceptance. System CPU capture refuses (J610); an internal-device app-scope trace is available, with managed attribution still open (J761). |
| Input updates/toolchain drift | High / transforms fail | Accepted hashes, semantic match reports, second real build | Reject unknown input; explicit review; prior outputs retained | Exercised: Steam 25475991 / 2021.3.45f2 migration passed with review (J430) |
| T30 custom driver | Unmeasured / optional graphics | Separate per-app loader/runtime identification | Passing Vulkan device driver first; no system-wide modification | Not pursued |

After two supported candidates at a boundary fail, reassess the hypothesis. Reconstruction cannot cure missing permissions, entitlement, authoring inputs or storage. Only real-device evidence advances capability gates.

Per-entry risk updates (L3/L4 updates, J39–J4xx sections) are archived in
[history/risk-register-2026-10-16.md](history/risk-register-2026-10-16.md); the full evidence is in
the [journal](PORTING_JOURNAL.md).
