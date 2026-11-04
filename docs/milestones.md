# Capability gates

Gate status through PR #325 (2026-11-04 UTC). Host reconstruction, record coverage
and real-device acceptance are separate facts. Evidence lives in the
[journal](PORTING_JOURNAL.md); open actions live in the [backlog](execution-backlog.md).
[Policy](DEVELOPMENT_PLAN.md), [alpha checklist](public-alpha.md) and
[historical gate log](history/milestones-2026-10-16.md) retain detailed criteria.

| Gate | Status and remaining acceptance | Evidence |
| --- | --- | --- |
| P1 phone-only install/update | OPEN — 693/705 historical final files available, 685 raw-exact; complete phone production, fresh install, same-key in-place update, save retention and Check for updates remain open | [Reconstruction contract](accepted-build-reconstruction.md) |
| Whole-game record reconstruction | PARTIAL — unresolved selectors reduced from 345 to three: two Clips and one AssetBundle. Complete groups/bundle assembly and runtime qualification remain open | [J1347](PORTING_JOURNAL.md#j1347--reconstruct-whole-game-customrendertextures), [J1355](PORTING_JOURNAL.md#j1355--supply-source-derived-bundle-tree-providers) |
| Lighting reconstruction | POLICY DECIDED, ACCEPTANCE OPEN — GPU sampling/floating-point tolerance class permitted; measured numerical and visual bounds plus ADR required. Geometry-probe differences up to 134/255 remain unexplained | [Open qualification](execution-backlog.md#phone-only-installation-p1) |
| P2 public alpha | OPEN — memory plateau, physical controls, recovery, complete packaging and performance gates remain | [Alpha checklist](public-alpha.md) |
| L0–L2 baseline | PASS — accepted-input/toolchain and isolated ARM64/converted-content baseline; no game-readiness claim | [Historical gates](history/milestones-2026-10-16.md) |
| L3 managed execution | PASS — original assembly closure executes on ARM64; preserve API/type identity | J431; [historical gates](history/milestones-2026-10-16.md) |
| L4 recovered scene | PASS for isolated content — original content-loader integration remains distinct | J28; [historical gates](history/milestones-2026-10-16.md) |
| L5 lawful startup/menu | OPEN — native Android menu/session lifecycle exists; complete lawful original startup/navigation remains unqualified | [Startup/session owners](ARCHITECTURE.md#ownership) |
| L5.5 original simulation | OPEN as a formal gate dependent on L5; assisted original simulation runs | [Gameplay backlog](execution-backlog.md#gameplay-integration) |
| L6 controllable stage | OPEN — survivor coverage does not close physical controls, ability semantics, unlocks or visuals | [Gameplay backlog](execution-backlog.md#gameplay-integration) |
| L7 combat/complete stage | OPEN — native combat and assisted routes do not qualify a normal unassisted complete stage; Siren recovery and LightningStake remain open | [Gameplay backlog](execution-backlog.md#gameplay-integration) |
| L8 complete offline victory | OPEN — uninterrupted normal victory, finale/results/return and a second stable run required; Moon/finale manual only | [Gameplay backlog](execution-backlog.md#gameplay-integration) |
| L9 profile | PARTIAL — native save/reload/recovery and genuine-event achievements have evidence; full update retention and remaining recovery cases open; Steam/cloud unavailable | [Alpha checklist](public-alpha.md) |
| L10 audio | OPEN — source clients and bounded shutdown/restart qualified; complete original mix/spatial/audibility acceptance remains | J1080; [gameplay backlog](execution-backlog.md#gameplay-integration) |
| L11 graphics | PARTIAL — integrated source-informed rendering exists; matched PC parity and lighting qualification remain | [Lighting qualification](execution-backlog.md#phone-only-installation-p1) |
| L12 performance | OPEN — startup requests 300 FPS; startup request does not qualify sustained FPS. Managed growth reduced from about 680 to 219 KB/session, plateau open | [Startup fix #322](https://github.com/danielbuva/ror2-android-port/pull/322), [J1350](PORTING_JOURNAL.md#j1350--restore-original-console-retention-default-at-composed-startup) |
| L13 transformation | OPEN — substantial public host-producer coverage; complete clean phone reconstruction and install/update acceptance still required | [Reconstruction contract](accepted-build-reconstruction.md) |
| Performance release gate | OPEN — full converter per-stage time/memory/heat/storage and sustained game FPS/pacing/battery/thermal/fidelity qualification required before release | [Gate added in #273](https://github.com/danielbuva/ror2-android-port/pull/273), [acceptance](public-alpha.md#performance-release-gate) |

Heat is a metric, not a failure below the agreed safety limits. Runs still require
cool admission, battery/charging admission and valid thermal sampling. No gate
advances from a build, host test or assisted run alone.
