# Porting state

Updated 2026-10-24 UTC after
[J1066](docs/PORTING_JOURNAL.md#j1066--qualify-native-settings-feedback-and-two-step-end-run-controls).
Native settings feedback, confirmation/cancel and strict automatic-input
abandon/restart pass on Thor. The twelve-session memory series is running;
no memory bound, ordinary-controller or complete touch-gameplay claim follows.
Main's audio/rendering work remains separately owned by PR #58. This page is a
snapshot; experiment results belong in the [journal](docs/PORTING_JOURNAL.md)
and [index](docs/JOURNAL_INDEX.md).

## Snapshot

| Item | Current fact |
| --- | --- |
| Accepted input | Steam 25475991; input id `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88` |
| Toolchain | Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan; `environment/toolchain.json` |
| Latest device-verified feature APK | J1066 Thor `299445f72267f216b23c7c4c2610364329445625396d8cd536bab01c07747ead`, source bf40428f: application screen lifetime and strict native abandon/healthy same-process restart. The preceding modal-corrected `c17a0ccc2947ac4b7c02cf43c183170ff866f88b03e90629c70a96121c1d18bb`, source e8600060, qualifies native keyboard/preview/consent/copy/browser return and confirmation/cancel. Both use automatic gameplay diagnostics; this is UI/lifecycle acceptance. |
| Installed now | Thor has 299445f7 in internal storage and is leased for the twelve-session observation. Main's local receipt names R38 `ede957ee8faaa12106d7c36685625ed5459619452704a1c45517f5c65e6c2cba`, source fad0247e; main-port is qualifying that candidate independently. Its latest published Main baseline/lifecycle record remains J1040/J1045/J1046 until that owner's journal lands. Never infer installation from Git HEAD. |
| Runtime source since the feature APK | The feedback/modal/confirmation/screen-lifetime runtime is the bf40428f build cohort. Subsequent changes expose an explicit 3–32-session host observation count and update docs; they add no runtime behaviour. Main's original bank-release wakeup candidate is separate and absent from Thor's feature APK. |
| Accepted rollback | J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`, source 1780ea9. No newer diagnostic replaces this acceptance. |
| Retained diagnostic rollbacks | R36/J1040 `bda30f33a62d62176cd45fd9cc0bd50ed5fe4e12d325ddc7ef19e948ec0fd3e7`, source 1428fdf; R35/J1034 `47d14cb855ce8fefdf2406d55591d13165665c4a160ab7d71f435c6469faba6e`, source 919e72a. Visual parity/full audio/natural Quit remain separate gates. |
| Owner candidate installed now | J1065 owner version 2 `4960fba8ed5e727639c4f156e2f08cf92a6b6486790bb0ab295925e9bd212de0`, producer source b9d74dd7, remains in internal storage on the assigned owner device, stopped/asleep. Its J850 code/content, private preparation, upgrade retention and assisted controls pass; it has no current audio integration and is not a public phone converter. |
| Phone-only production | J1063 completes source-input host game-code production; J1065 qualifies the private owner APK. Independent content/Burst/shader producers, licensed native input, Android tool execution, phone signing/installer UX and matched performance remain open. Architecture C and desktop fallback stay fixed. |
| Historical executable rollbacks | J425 `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0`; paused J323 Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`. J1051 retired older rebuildable executables; keep source/findings/receipts. |
| Retained old input | Steam 21587608 / Unity 2021.3.33f1 under `work/migrations/steam-21587608`, old rollbacks only |

Retention: [history policy](docs/history-retention.md). The pruner protects APKs
named here, in `docs/BASELINE.md`, device receipts or the coordination lock.
Raw logs, captures, generated content and signing material remain private.

## Current capability and open gates

The offline composition loads original catalogs, recovered menu/survivor/loadout
choices, original combat/directors, purchases/items/equipment, staged worlds and
Android-local profile/results/settings. Native first-stage UI-abandon and genuine
defeat/restart pass on R36 with original audio ready. Assisted stage traversal and
survivor callbacks have bounded evidence, with ability/mission gaps retained in
[subsystem coverage](docs/subsystem-coverage.md) and [milestones](docs/milestones.md).
None establishes a normal-difficulty full run or PC appearance/audio parity.

- Qualify Thor's actual physical presses, mappings/rebinding and ordinary menu/
  game input. Existing Thor controls are automatic diagnostics (J762); full touch
  movement, camera, skills and interaction are absent. [Screen inventory](docs/SCREEN_COVERAGE.md).
- Attribute/bound managed growth, finish a long series, qualify crash/ANR,
  background/resume, interrupted writes, storage faults and sustained thermals.
  The older five-session APK still grows about 52 MB per session in J1066.
- Complete natural audio shutdown, continuous effects/spatial output and visual
  parity through the main-port gates. Original bank readiness and nonzero captured
  PCM alone do not qualify playback or a healthy Quit.
- Finish fresh public-input owner installation, increasing-version/signing custody
  and player update/rollback qualification. [Policy](docs/ALPHA_POLICY.md) chooses
  local files only and defers account downloads/Steam Cloud; identity and online
  service capabilities remain explicitly unavailable.
- Complete ordinary unassisted play and the [playtesting checklist](docs/PLAYTESTING.md).
  Moon/finale/escape remain manual only. Releases, outward announcements and issue
  templates need separate approval; workstream pushes and merges are authorized.

Open implementation work is in [execution backlog](docs/execution-backlog.md)
and [public alpha](docs/public-alpha.md); pipeline/debt ownership is in
[architecture](docs/ARCHITECTURE.md). No generated private input becomes a public
bootstrap merely because this laboratory builds.
