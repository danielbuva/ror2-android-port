# Capability gates

Re-audited 2026-11-11 UTC against merged evidence since #338, through
[#431](https://github.com/danielbuva/ror2-android-port/pull/431) and journal J1405.
No open gate closes. Host reconstruction, record coverage and real-device
acceptance are separate facts. Evidence lives in the
[journal](PORTING_JOURNAL.md); open actions live in the [backlog](execution-backlog.md).
[Policy](DEVELOPMENT_PLAN.md), [alpha checklist](public-alpha.md) and
[historical gate log](history/milestones-2026-10-16.md) retain detailed criteria.

| Gate | Status and remaining acceptance | Evidence |
| --- | --- | --- |
| P1 phone-only install/update | OPEN — first qualify a playable source-derived APK against the latest lab build; then complete phone production, fresh install, same-key port update, save retention and Check for updates. Historical byte counts are diagnostic | [Reconstruction contract](accepted-build-reconstruction.md), [host-only local assembly #408](https://github.com/danielbuva/ror2-android-port/pull/408) |
| Whole-game record reconstruction | PARTIAL — three selectors remain: two Clips and one AssetBundle. A partial native subset typed-loads; complete groups, managed/reference closure, bundles and runtime qualification remain open | [J1388](PORTING_JOURNAL.md#j1388--emit-and-typed-load-a-closed-source-native-bundle-subset), [camera suppliers #428](https://github.com/danielbuva/ror2-android-port/pull/428), [remaining selectors](execution-backlog.md#phone-only-installation-p1) |
| Lighting reconstruction | PARTIAL — source LightingSettings typed-load; native occlusion, complete source lighting and in-game visual qualification remain open. ADR/validator shipped; no real record has both numerical and visual tolerance admission | [J1378](PORTING_JOURNAL.md#j1378--source-release-lighting-records-and-typed-native-loading), [ADR-003](ADR-003-lighting-tolerance.md) |
| P2 public alpha | OPEN — memory plateau, physical controls, recovery, complete packaging and performance gates remain | [Alpha checklist](public-alpha.md) |
| L0–L2 baseline | PASS — accepted-input/toolchain and isolated ARM64/converted-content baseline; no game-readiness claim | [Historical gates](history/milestones-2026-10-16.md) |
| L3 managed execution | PASS — original assembly closure executes on ARM64; preserve API/type identity | J431; [historical gates](history/milestones-2026-10-16.md) |
| L4 recovered scene | PASS for isolated content — original content-loader integration remains distinct | J28; [historical gates](history/milestones-2026-10-16.md) |
| L5 lawful startup/menu | OPEN — bounded ordinary launcher Start reaches player/HUD on the lab APK; complete lawful original startup/navigation and converter-output qualification remain open | [J1401](PORTING_JOURNAL.md#j1401--load-typed-results-definitions-before-dependent-drop-tables), [startup/session owners](ARCHITECTURE.md#ownership) |
| L5.5 original simulation | OPEN as a formal gate dependent on L5; assisted original simulation runs | [Gameplay backlog](execution-backlog.md#gameplay-integration) |
| L6 controllable stage | OPEN — survivor coverage does not close physical controls, ability semantics, unlocks or visuals | [Gameplay backlog](execution-backlog.md#gameplay-integration) |
| L7 combat/complete stage | OPEN — native combat and assisted routes do not qualify a normal unassisted complete stage; Siren recovery and LightningStake remain open | [Gameplay backlog](execution-backlog.md#gameplay-integration) |
| L8 complete offline victory | OPEN — uninterrupted normal victory, finale/results/return and a second stable run required; Moon/finale manual only | [Gameplay backlog](execution-backlog.md#gameplay-integration) |
| L9 profile | PARTIAL — native save/reload/recovery, genuine-event achievements and lab update hash retention have evidence; final alpha update/rollback/backup/restore and remaining recovery cases open; Steam/cloud unavailable | [J1401](PORTING_JOURNAL.md#j1401--load-typed-results-definitions-before-dependent-drop-tables), [alpha checklist](public-alpha.md) |
| L10 audio | OPEN — source clients, bounded shutdown/restart and install-bound verification qualified; complete original mix/spatial/audibility acceptance remains | [J1386](PORTING_JOURNAL.md#j1386--reuse-install-bound-audio-verification-and-partition-loading-costs), [gameplay backlog](execution-backlog.md#gameplay-integration) |
| L11 graphics | PARTIAL — integrated source-informed rendering exists; matched PC parity and lighting qualification remain | [Lighting qualification](execution-backlog.md#phone-only-installation-p1) |
| L12 performance | OPEN — retained assisted final-ten-minute counters average 50.032 FPS; raw pacing, battery/throttling and ordinary sustained qualification remain open. Interrupted repeated-session series establishes no memory plateau | [J1389](PORTING_JOURNAL.md#j1389--report-final-ten-minute-sustained-frame-counters), [J1402](PORTING_JOURNAL.md#j1402--continue-memory-observations-through-native-loss-and-menu) |
| L13 transformation | OPEN — catalog/container and required-set host checks plus partial typed native loading shipped; complete clean phone reconstruction and install/update acceptance still required | [J1385](PORTING_JOURNAL.md#j1385--complete-catalogs-against-produced-serialized-containers), [J1394](PORTING_JOURNAL.md#j1394--exact-required-set-bundle-emission), [reconstruction contract](accepted-build-reconstruction.md) |
| Performance release gate | OPEN — full converter per-stage time/memory/heat/storage and sustained game FPS/pacing/battery/thermal/fidelity qualification required before release | [Gate added in #273](https://github.com/danielbuva/ror2-android-port/pull/273), [acceptance](public-alpha.md#performance-release-gate) |

Heat is a metric, not a failure below the agreed safety limits. Runs still require
cool admission, battery/charging admission and valid thermal sampling. No gate
advances from a build, host test or assisted run alone.
