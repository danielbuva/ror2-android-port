# Porting state

Updated 2026-11-11 UTC. This laboratory is not a finished port. Evidence lives in
[the journal](docs/PORTING_JOURNAL.md) and [index](docs/JOURNAL_INDEX.md);
[J1–J1177 are frozen](docs/history/journal-J1-J1177/JOURNAL_INDEX.md).
Named APK hashes are protected by the pruner.

## Snapshot

| Item | Current fact |
| --- | --- |
| Input and toolchain | Accepted Steam 25475991; Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan. Pins: `environment/toolchain.json`. |
| Compatibility reference (P1) | Lab APK `9f904392d02abc3854f9efc4b51cd03daec7afb6b7192a4c074f30fabc12fa22`, source `6c12b506`. Match behaviour, content, visuals and performance as closely as possible; structural/gameplay checks stay strict, byte equality is diagnostic. |
| Latest device-verified APK | Typed-results APK `04df664f66d5ebc32cbc477865e9bfb6a16bfdf1120603b0f2f2f99a310a680d`, source `2575892b` ([J1401](docs/PORTING_JOURNAL.md#j1401--load-typed-results-definitions-before-dependent-drop-tables)). Ordinary Start reached player/HUD; strict current-PID error scan empty; 21 survivors, 455 unlockables and 153 banks ready. Corrects J1400's premature CursedBook activation. Sustained play remains open. |
| Installed now (last recorded) | Main Nova: the J1401 APK above, on adopted storage; in-place update preserved profile/settings hashes. J1402 reused it for assisted sessions. Evidence: `work/coordination/alpha-item-group-device-20261111T023949Z/`. No fresh device query in this host-only refresh. |
| Runtime source since that APK | Installed runtime remains `2575892b`. Merged converter suppliers and host runner changes through J1405 do not establish a newer runtime APK or device qualification. |
| Converter | 79 source scenes staged (681-file inventory); whole-game closure inventory reports **0 catalog-missing**, 390,937 selected / 386,879 reachable records. These are staging/coverage facts: complete strict graph, current-CLR/script/reference checks, final typed load, APK assembly and converted-device play remain pending. |
| Installer | [#241 merged](https://github.com/danielbuva/ror2-android-port/pull/241): authorized synthetic prompts and readable live status. [#417 open](https://github.com/danielbuva/ror2-android-port/pull/417): visible unknown-app permission/consent qualification; exact-source build and seven-case device acceptance remain open. Check for updates, same-key update/rollback and real profile retention still need complete phone qualification. |

Converter receipts: `work/coordination/p1-scenes-w/scene-completion-audit-0722/`
and `work/coordination/p1-wholegame-1031/current-catalog-combined-repair-v2/`.
Zero catalog-missing does not imply graph admission or loadability. Public
production uses legitimate game files, permitted SDK inputs and public recipes;
game-derived outputs remain private. Raw-exact, drift-explained,
tolerance-accepted and device acceptance remain separate results.

## Alpha loading and stability since November 4

J1381–J1405 ship scoped pointer/script checks, typed buff/item/results discovery,
install-bound audio verification and shared startup manifests. Cached audio checks
changed from 274 full verifications to 274 cache hits: banks 3.765 → 0.044 s,
media 8.959 → 0.032 s (J1386). Artifacts/holders, drones/projectiles, profiles and
game modes reuse existing snapshots (J1393/J1396/J1397/J1399/J1400). Device starts
reached player/HUD and retained profiles/settings. Per-span timings are diagnostic;
controlled total-load improvement remains unqualified.

J1402 continued assisted loss → results → menu → Start in one process, reaching
ten completions before telemetry loss. J1403–J1405 improve transport reporting,
combined thermal/battery reads and between-session cooldown, with host tests only.
Repeated-session completion, memory plateau and physical navigation remain open.

## Remaining gates and retained rollbacks

1. Produce the first fully playable source-derived APK; then qualify phone-only
   import → convert → install → play → newer port-release update, preserving saves
   and rebuilding changed outputs. Follow the [alpha checklist](docs/public-alpha.md).
2. Siren recovery/egg boss mission, unassisted normal runs, physical controls,
   matched PC rendering and original audio mix/spatial/audibility.
3. Sustained FPS/frame pacing, bounded memory and battery/heat/storage profiling
   for the game and complete converter. Heat is a metric; safety limits remain.
   [Lighting tolerance](docs/ADR-003-lighting-tolerance.md) still needs numerical
   and visual admission of a real record.

Retained gameplay baseline: J1121/R58
`4386916991386bdf5b747e69786be58fa72ccfb0d3fc0220f59061ede495d0f5`;
Siren candidate (assisted, failing)
`4f2274d49ba10474299ffa7a58de5da49ffd70327897e532806a519d0ee24cea`.
Historical executable rollbacks: J425
`5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0`;
paused J323 Moon
`893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`.
Old Steam 21587608 / Unity 2021.3.33f1 is historical only; see
[retention](docs/history-retention.md).

Owners: [architecture](docs/ARCHITECTURE.md); open work:
[backlog](docs/execution-backlog.md), [milestones](docs/milestones.md).
Identity, online services and Steam Cloud remain unavailable. No build or host
test establishes game readiness.
