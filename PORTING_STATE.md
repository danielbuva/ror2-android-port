# Porting state

Updated 2026-11-05 UTC. This laboratory is not a finished port. Results belong in the
[journal](docs/PORTING_JOURNAL.md) ([index](docs/JOURNAL_INDEX.md); J1–J1177 are
[frozen](docs/history/journal-J1-J1177/JOURNAL_INDEX.md)). Named APK hashes are
protected by the pruner; other old build outputs are disposable.

## Snapshot

| Item | Current fact |
| --- | --- |
| Accepted input | Steam 25475991; input `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88` |
| Toolchain | Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan; `environment/toolchain.json` |
| Compatibility reference (P1) | Latest lab APK `9f904392d02abc3854f9efc4b51cd03daec7afb6b7192a4c074f30fabc12fa22`, source `6c12b506`: device-verified playability with matching behaviour, content, visuals and performance. Structural/gameplay checks remain strict; J850 byte equality is diagnostic. |
| Latest device-verified APK | Audio-receipt APK `64b8741f45e5f94f54d95ca56b88040c72548795541c2daffc153e2fbca232e7`, source `80452b72`; ordinary Start reached stage/HUD with source audio ready 153/153. Install-bound full verification/cache and corruption refusal/restoration passed (J1384); sustained gameplay remains open. |
| Installed now (Main Nova) | Audio-receipt APK above on adopted storage; installed hash/backing verified in `work/coordination/alpha-loading-audio-receipt-integrity-start-20261105T020900Z/`. App stopped, display asleep, scratch removed and lease released. |
| Runtime source since that APK | Audio-receipt APK includes runtime through `80452b72`; subsequent source is not implied installed. Retained Siren candidate `4f2274d49ba10474299ffa7a58de5da49ffd70327897e532806a519d0ee24cea`, source `5dc99b6c`, remains an assisted failing candidate. |
| Retained gameplay baseline | J1121/R58 `4386916991386bdf5b747e69786be58fa72ccfb0d3fc0220f59061ede495d0f5`, source `55149b48`; Siren recovery/destination gates remain open. |
| Phone-only production | First produce a fully playable source-derived APK close to the latest lab build; then qualify import → convert → install → play → port-release update, retaining profiles/settings and rebuilding changed outputs. Check for updates and complete device acceptance remain open. Historical diagnostics: 693/705 files available, 685 raw-exact; not a playability gate. |
| Whole-game reconstruction | Three records remain in the separate whole-game record frontier, per current workstream handoff; this is not the 12-file final-output frontier. |
| Lighting tolerance | [ADR-003](docs/ADR-003-lighting-tolerance.md) scopes measured numerical and visual admission. Host validator/reporting shipped; no real record has completed both gates. |
| Historical executable rollbacks | J425 `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0`; paused J323 Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`. [Retention](docs/history-retention.md). |
| Old input | Steam 21587608 / Unity 2021.3.33f1 retained for historical rollbacks. |

The public converter uses legitimate game files, permitted SDK inputs and public
recipes. J850 artifacts, development settings and visual captures are private
qualification inputs only. Raw-exact, drift-explained, tolerance-accepted,
generated metadata and device acceptance remain separate facts.

## Remaining gates

1. Phone-only installation, in-place update and Check for updates, then the
   [public alpha checklist](docs/public-alpha.md).
2. Native Siren recovery/egg boss mission and unassisted normal runs.
3. Matched PC rendering parity and complete original audio mix/spatial/audibility.
4. Physical controls, bounded memory and sustained FPS/frame pacing/battery/heat
   profiling. Heat is a metric; safety admission/abort rules remain in force.

Current owners: [architecture](docs/ARCHITECTURE.md); work:
[backlog](docs/execution-backlog.md), [milestones](docs/milestones.md),
[coverage](docs/subsystem-coverage.md). Identity, online services and Steam Cloud
remain unavailable. No build or host test establishes game readiness.
