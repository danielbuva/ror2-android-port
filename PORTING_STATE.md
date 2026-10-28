# Porting state

Updated 2026-10-28 UTC. This laboratory is not a finished port. Full results belong in the
[journal](docs/PORTING_JOURNAL.md) (index: [JOURNAL_INDEX](docs/JOURNAL_INDEX.md); J1–J1177 frozen in
[history](docs/history/journal-J1-J1177/JOURNAL_INDEX.md)).

APK hashes named here are the only builds the pruner protects through this file; every other old build
is disposable (user-approved cleanup, 2026-10-27).

## Snapshot

| Item | Current fact |
| --- | --- |
| Accepted input | Steam 25475991; input `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88` |
| Toolchain | Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan; `environment/toolchain.json` |
| Accepted build (P1 target) | J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`, source `1780ea9`; scope in [BASELINE.md](docs/BASELINE.md). Phone-only reconstruction must reproduce these bytes from the user's game files. |
| Latest device-verified APK | J1121/R58 `4386916991386bdf5b747e69786be58fa72ccfb0d3fc0220f59061ede495d0f5`, source `55149b48`; installed and verified on the shared Nova. Siren-route recovery and destination capture remain device gates. |
| Installed now (Main Nova) | `43a8c0ffd5e98fd7f04e7030df3c3e29e765ebfe06a50a647231c7d3103a8d7a`, source `70f44151`, adopted storage. Shared handoffs may advance receipts; never infer installation from Git. |
| Runtime source since that APK | Frozen Siren candidate `4f2274d49ba10474299ffa7a58de5da49ffd70327897e532806a519d0ee24cea`, source `5dc99b6c` (native navigation detours); its assisted Siren stage still fails in gameplay and is the current Main gate. |
| Phone-only production | Host readiness 678 of 705 final files (673 raw-exact), through J1247. Remaining: 27 scene/player/lab/catalog files, including native Cubemaps; complete phone production and install/update acceptance remain open. Details: [reconstruction](docs/accepted-build-reconstruction.md), [public alpha](docs/public-alpha.md). |
| Historical executable rollbacks | J425 `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0`; paused J323 Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`. [Retention policy](docs/history-retention.md). |
| Retained old input | Steam 21587608 / Unity 2021.3.33f1 retained for old rollbacks only. |

## Remaining gates

1. Siren: repair the native navigation/recovery failure, then the native Siren/egg boss mission and
   unassisted normal runs.
2. Rendering parity against a matched PC reference; complete original audio mix/spatial/audibility.
3. Physical controls, memory bound, sustained performance and thermal acceptance.
4. Phone-only installation, in-place update and Check for updates (P1), then the alpha checklist (P2).

Scopes and evidence: [milestones](docs/milestones.md), [subsystem coverage](docs/subsystem-coverage.md),
[execution backlog](docs/execution-backlog.md), [policy](docs/ALPHA_POLICY.md),
[architecture](docs/ARCHITECTURE.md). Identity, online services and Steam Cloud remain unavailable.
