# Porting state

Updated 2026-11-17 UTC. This laboratory is not a finished port. Evidence lives in
[the journal](docs/PORTING_JOURNAL.md) and [index](docs/JOURNAL_INDEX.md);
[J1–J1177 are frozen](docs/history/journal-J1-J1177/JOURNAL_INDEX.md).
Named APK hashes are protected by the pruner.

## Snapshot

| Item | Current fact |
| --- | --- |
| Input and toolchain | Accepted Steam 25475991; Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan. Pins: `environment/toolchain.json`. |
| Compatibility reference (P1) | Lab APK `9f904392d02abc3854f9efc4b51cd03daec7afb6b7192a4c074f30fabc12fa22`, source `6c12b506`. Match behaviour, content, visuals and performance as closely as possible; structural/gameplay checks stay strict, byte equality is diagnostic. |
| Latest device-verified APK | Lab APK `48b8a7f5ca26d15d53a6fb86bec9c5264e7419e4e5ab3cfe8a1b6c9b482192c1`, source `f94c0c30`, completed the J1477 stage-transition and passive-tail diagnostic. Converted APK `20726b61542cc5d08ece1b1030a7512a5b05fafd995f4baa7b364ac817ca608a`, source `538d1f1c`, reached the original-catalog survivor menu (J1476). Converted ordinary stage play and End Run remain open. |
| Installed now (last recorded) | Main Nova: the lab and converted packages above, on adopted storage. The J1477 and J1476 receipts record backing, stopped/asleep readback and lease release for their respective packages. |
| Runtime source since the converted APK | Subsequent merged runtime changes include native results cleanup, settings interaction and HUD presentation. The installed converted APK predates those changes. |
| Converter | Android emitted all 290,498 records of the strict whole-game bundle request. The output hash matches the host run (J1478). Unity typed load and playable APK integration of this specific bundle remain open. |
| Installer | [#241](https://github.com/danielbuva/ror2-android-port/pull/241) ships authorized synthetic prompts and readable live status. [#417](https://github.com/danielbuva/ror2-android-port/pull/417) qualifies visible installer permission and consent. Check for updates, same-key update/rollback and real profile retention still need complete phone qualification. |

The full source inventory has 79 staged scenes and zero catalog-missing entries
(`work/coordination/p1-wholegame-1031/current-catalog-combined-repair-v2/`).
Public production uses legitimate game files, permitted SDK inputs and public
recipes. Game-derived outputs remain private.

## Alpha loading and stability since November 4

The shared device runner now has a real 30-minute qualification, retaining a
120 Hz request, reconciled raw frames and strict thermal coverage. It uses a
diagnostic-only monster cap and invincibility; ordinary sessions retain native
limits. See [the measured scope and open pacing gate](docs/performance-game.md#shared-runner-and-bounded-combat-qualification).
Retained J1472 bounded-combat APK
`0c440333e3906c483ad8280ab6287e299ca8f7e10238c696425f1e3423cde2ad`,
source `4e12f51b`, recorded whole/tail means of 59.800/59.749 FPS.
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
