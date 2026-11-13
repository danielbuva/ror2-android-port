# Porting state

Updated 2026-11-13 UTC. This laboratory is not a finished port. Evidence lives in
[the journal](docs/PORTING_JOURNAL.md) and [index](docs/JOURNAL_INDEX.md);
[J1–J1177 are frozen](docs/history/journal-J1-J1177/JOURNAL_INDEX.md).
Named APK hashes are protected by the pruner.

## Snapshot

| Item | Current fact |
| --- | --- |
| Input and toolchain | Accepted Steam 25475991; Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan. Pins: `environment/toolchain.json`. |
| Compatibility reference (P1) | Lab APK `9f904392d02abc3854f9efc4b51cd03daec7afb6b7192a4c074f30fabc12fa22`, source `6c12b506`. Match behaviour, content, visuals and performance as closely as possible; structural/gameplay checks stay strict, byte equality is diagnostic. |
| Latest device-verified APK | Bounded assisted-combat APK `0c440333e3906c483ad8280ab6287e299ca8f7e10238c696425f1e3423cde2ad`, source `4e12f51b`. Shared runner completed 30 minutes on source stage `lakes`, with 54 kills, 2–12 enemies and native teardown. Whole/tail means 59.800/59.749 FPS leave the strict 60 FPS gate open. |
| Installed now (last recorded) | Main Nova: the bounded-combat APK above, on adopted storage. Evidence: `work/coordination/alpha-shared-device-session-20261113T005754Z/terminal.done.json`. Profile/settings retention, package/runtime backing, stopped/asleep readback and lease release pass; no later device query in this refresh. |
| Runtime source since that APK | Installed runtime remains `4e12f51b`. Subsequent shared-runner/storage tooling and newer merged runtime changes have not been built into this APK. Ordinary-play and converted-device acceptance remain separate gates. |
| Converter | 79 source scenes staged (681-file inventory); whole-game closure inventory reports **0 catalog-missing**, 390,937 selected / 386,879 reachable records. These are staging/coverage facts: complete strict graph, current-CLR/script/reference checks, final typed load, APK assembly and converted-device play remain pending. |
| Installer | [#241 merged](https://github.com/danielbuva/ror2-android-port/pull/241): authorized synthetic prompts and readable live status. [#417 open](https://github.com/danielbuva/ror2-android-port/pull/417): visible unknown-app permission/consent qualification; exact-source build and seven-case device acceptance remain open. Check for updates, same-key update/rollback and real profile retention still need complete phone qualification. |

Converter receipts: `work/coordination/p1-scenes-w/scene-completion-audit-0722/`
and `work/coordination/p1-wholegame-1031/current-catalog-combined-repair-v2/`.
Zero catalog-missing does not imply graph admission or loadability. Public
production uses legitimate game files, permitted SDK inputs and public recipes;
game-derived outputs remain private. Raw-exact, drift-explained,
tolerance-accepted and device acceptance remain separate results.

## Alpha loading and stability since November 4

The shared device runner now has a real 30-minute qualification, retaining a
120 Hz request, reconciled raw frames and strict thermal coverage. It uses a
diagnostic-only monster cap and invincibility; ordinary sessions retain native
limits. See [the measured scope and open pacing gate](docs/performance-game.md#shared-runner-and-bounded-combat-qualification).
Retained ordinary-Start audio evidence remains APK
`1cee9b5ab9e7453f9ba76977e49f3b1208308be52c3d8ebe07dc7824e913b5a1`,
source `41c03a7a`; assisted combat does not replace that acceptance scope.

J1381–J1420 ship scoped structural checks, typed content discovery, install-bound
audio verification, shared provider manifests, native skin iterator execution and
snapshot indexes. Bounded Starts retain player/HUD, audio and profile/settings
contracts. Four traced index spans total 0.536 → 0.008 s (J1420); controlled
total-load improvement remains unqualified. Current audio callback attribution
([J1422](docs/PORTING_JOURNAL.md#j1422--attribute-original-audio-readiness-callback-waits))
identifies bank results as the final prerequisite, observed 16.1 ms after the last
bank callback; it preserves readiness and scheduling and makes no speedup claim.

J1407 completes a supervised 32-session UI-abandon diagnostic; J1408 reclaims
measured returned-pool storage. J1409 aligns matched-menu observations and retains
positive post-pool growth without a confirmed accumulating owner. Memory work is
parked at that checkpoint. Physical navigation, ordinary long-run dependency
retention, a memory plateau and sustained performance remain open.

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
