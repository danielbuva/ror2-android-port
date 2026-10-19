# Risk of Rain 2 Android porting laboratory

An evidence-driven laboratory that runs the original PC game's managed code and converted
content natively on ARM64 Android, using the user's own legitimate game installation.
**It is not a finished or distributable port.** The current APK reaches the original offline
menu, runs original survivors through several real stage transitions, and keeps an
Android-only profile, but only with diagnostic assists so far. Audio, stock platform
services, the Moon finale and PC visual parity are not done. See
[PORTING_STATE.md](PORTING_STATE.md) for the exact current snapshot.

## Read first

1. [PORTING_STATE.md](PORTING_STATE.md): what is installed, what runs, what is open.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the build pipeline, the Android runtime,
   who owns what, and the known structural debt.
3. [AGENTS.md](AGENTS.md): the safety, privacy and workflow rules. They apply to people too.
4. [docs/JOURNAL_INDEX.md](docs/JOURNAL_INDEX.md): search it before repeating an experiment,
   then read the matching entry in [docs/PORTING_JOURNAL.md](docs/PORTING_JOURNAL.md).

## Repository map

| Path | What it holds |
| --- | --- |
| `dev` | The command entry point; runs `scripts/lab/main.py` in the lab venv. |
| `scripts/lab/` | Host tooling: inventory, decompile/export, assembly and content transforms, project composition, build, install, device runs and evidence collection. |
| `tools/unity/` | Authored C# and shaders staged into the generated Unity project; most of the Android runtime lives here (see ARCHITECTURE). |
| `tools/catalog/` | Editor-side catalog build helpers and exact-editor host fixtures (`*Host.cs`). |
| `tools/assembly-transforms/` | .NET tool (assembly `AssemblyProbe`) that reads original assemblies and applies the bounded, input-gated transforms. |
| `android/`, `smoke/` | The lab player's build/diagnostic harness and the bootstrap smoke project. |
| `tests/` | Host tests (Python unittest). |
| `docs/` | Current references at the top level; superseded material under `docs/history/`. |
| `recipe/` | Audited, public build recipes: authored transformations and configuration the build reads ([recipe/README.md](recipe/README.md)). |
| `environment/` | Reviewed, public toolchain pins and examples; raw captures stay ignored. |
| `work/` (ignored) | All game-derived inputs, generated projects, builds, receipts and evidence. Never commit it. What the tooling expects to find there: [docs/LOCAL_STATE.md](docs/LOCAL_STATE.md). |

## Local setup

The prepared workstation already has the exact Unity/Android toolchain and inspection tools.
`./scripts/lab-setup.sh` restores the pinned Python dependencies (Python 3.11 or newer).
Copy `environment/lab-config.example.json` to the ignored `work/config/local.json` and set
the legitimate installation path. Never copy the original installation into tracked
directories. Configure authorized
serials in `device_serials` and choose the default in `device_serial`; each serial may have
its own `device_settings` entry. Device actions accept `--device SERIAL` or
`LAB_DEVICE=SERIAL`. If more than one attached device is available and neither selector is
given, the action refuses to guess. An explicit serial outside the configured allowlist
also refuses.

For example, device-specific settings can select `storage_mode` (`adopted` or `internal`),
`internal_reserve_mib`, `apk_install_limit`, `sleep_display_when_idle`,
`display_models`, and `display_count`. Existing top-level legacy settings are fallback values
for the configured default device only. Live checks must still confirm current storage and
free space before every install. Do not change storage configuration or move existing data.
Per-device receipts live under `work/device/<serial>/`. The explicit
`migrate-device-receipts` command verifies the configured default device's ownership,
retains original flat receipts and writes its activation marker last. The current Nova
has passed migration, an in-place install and both baseline modes (J595).

Current onboarding remains narrow: the current Nova uses adopted storage only. The second
Nova and Thor require explicit serial configuration, recorded live internal storage and
reserve checks before installation. Thor's two-display sleep behavior also needs
verification. Concurrent runs and extra-device compatibility remain unvalidated.

`./dev inspect --full` creates a reviewed input identity. New or updated inputs must be
reviewed before their ID is recorded in `work/config/accepted-input.json`. No Steam
authentication is needed to inspect the supplied installation.

## Everyday commands

| Command | What it does |
| --- | --- |
| `./dev test` | Host tests in the lab venv. |
| `./dev doctor [--json]` | Toolchain, inventory and dependency-pin health. |
| `./dev preflight [--device SERIAL] [--host-only]` | Current: host/input gates plus selected-device storage; `--host-only` omits device access. |
| `./dev check-baseline` | The standard device check on the installed APK: 35 s of assisted Lakes play, no report error, profile run count unchanged ([docs/BASELINE.md](docs/BASELINE.md)). |
| `./dev editor --target lab --action open` | Start the isolated exact editor and connect the pinned Unity MCP. One editor mutation at a time. |
| `./dev build [--target vulkan] [--force]` | Host preflight and instrumented IL2CPP ARM64 build through MCP with a content-addressed APK receipt. Rejects stale staged runtime sources. |
| `./dev install [--device SERIAL]` | Install on the selected device after live storage and reserve checks; rejects foreign pre-existing packages and records placement. |
| `./dev sync-data [--device SERIAL]` | Hash-verified sync of changed payload into the selected device's runtime-reported path. |
| `./dev run` | Launch the lab, wait for its checkpoint, collect the runtime snapshot. |
| `./dev logs` · `crash` · `screenshot` · `perf` | Timestamped local captures. |
| `./dev perf --action cpu [--target LABEL] [--device SERIAL]` | Current: 15 s system simpleperf call graph of the already running owned foreground lab process; no launch or install. Raw evidence stays per device; live profiling permissions remain unverified. |
| `./dev storage [--device SERIAL]` | Live capacity, volume and backing report; changes nothing. |
| `./dev reset [--device SERIAL]` | Uninstall only the selected device's locally receipted disposable lab package. |
| `./dev migrate-device-receipts [--device SERIAL]` | Current: migrate default-device receipts after live ownership verification, preserve originals, activate last. Blocked while the coordination lock exists. |
| `./dev inspect [--full]` · `decompile` · `export-project` · `graphics` | Input inventory and recovery stages (cached, receipted). |

`./dev prototype --action list` lists all actions with help, current first, including
historical actions and the historical default/unknown-name fallback. Historical
descriptions are also in
[docs/history/readme-commands-and-recipes.md](docs/history/readme-commands-and-recipes.md).

Current actions below are generated from `scripts/lab/actions.py`; do not edit the table
by hand. Regenerate with `python3 scripts/readme-actions.py`; CI checks freshness with
`python3 scripts/readme-actions.py --check`.

<!-- prototype-actions:start -->

| Command | What it does |
| --- | --- |
| `./dev prototype --action rebuild-step` | Rebuild --step assemblies\|shader-pipeline\|composition\|project-inputs\|catalog-closure\|dependencies\|stage-variants\|source-scenes\|build-entries\|runtime-sources\|importer-identities\|validate-bindings\|unity-build in order under work/rebuild/<input_id>/lab-project (--dest overrides); --compare-only reads an existing destination. |
| `./dev prototype --action assembly-transforms-check` | Rebuild the three transformed plugins from originals in disposable .local scratch and verify hashes; --work-dir selects read-only local inputs. |
| `./dev prototype --action inherited-store-capture` | Capture exactly the ledger's inherited asset/meta pairs into work/inherited-store/<input_id>; refuse hash or identity drift. |
| `./dev prototype --action inherited-state-check` | Verify inherited-store hashes and regenerate byte-proven pairs in scratch; work stays read-only (--work-dir selects local work). |
| `./dev prototype --action authored-additions-check` | Compare tracked shader addition and generated importer bytes with migration staging; read-only. |
| `./dev prototype --action asset-transforms-check` | Compare all recipe-generated asset/meta bytes with the project; read-only. |
| `./dev prototype --action project-manifest-capture` | Capture generated-project file hashes and external inputs. |
| `./dev prototype --action project-manifest-compare` | Compare two receipts with --compare A B; exit 1 on differences. |
| `./dev prototype --action composition-update-stage` | Stage the current project composition. |
| `./dev prototype --action composition-update-dependencies` | Stage missing source dependencies for the composition. |
| `./dev prototype --action whole-catalog-contracts` | Check whole-catalog resource and serialization contracts. |
| `./dev prototype --action whole-catalog-prepare` | Prepare the whole-catalog integration. |
| `./dev prototype --action whole-catalog-host` | Run the whole-catalog editor host fixture. |
| `./dev prototype --action survivor-kit-check` | Assisted world skill check: --target all or comma-separated base survivor keys; locked choices are diagnostic, no profile awards. |
| `./dev prototype --action session-cleanup-check` | Observe an original first-stage loss, native cleanup and same-process restart; diagnostic automatic input, gameplay debug assists off. Optional --target selects a base survivor (default Commando); locked choices are diagnostic overrides, no expansion. |
| `./dev prototype --action whole-catalog-host-providers` | Run the whole-catalog native-provider host fixture. |
| `./dev prototype --action whole-catalog-repair-bindings` | Repair recorded whole-catalog root bindings. |
| `./dev prototype --action whole-catalog-build` | Compose content and build the whole-catalog player. |
| `./dev prototype --action whole-catalog-code-build` | Build player code while verifying and reusing the frozen payload. |
| `./dev prototype --action whole-catalog-run` | Install, sync and run the catalog-registration check. |

<!-- prototype-actions:end -->

## Current integration loop

The active composition is the whole-catalog integration
([docs/whole-catalog-integration.md](docs/whole-catalog-integration.md) has the full
contract):

```sh
./dev preflight
# Authored C# change only (tools/unity, tools/catalog): restage sources, forced Vulkan
# build that reuses the frozen content payload
./dev prototype --action whole-catalog-code-build
# Content, scene or package change: full composition and forced Vulkan build
./dev prototype --action whole-catalog-build
# Install, sync and run the native catalog-registration check on the device
./dev prototype --action whole-catalog-run
```

Both build actions need the exact editor open and connected (`./dev editor --target lab --action open`).

`./dev build` refuses to package when authored runtime sources differ from the staged copies,
so a stale APK cannot pass as feature evidence. Gameplay runs on the device are currently
driven by runner scripts kept under the ignored `work/experiments/whole-catalog/gameplay/`;
they are not yet tracked (see [docs/LOCAL_STATE.md](docs/LOCAL_STATE.md)).

The selector, scoped receipts and receipt migration passed on the current Nova (J595).
Additional devices and concurrent device runs still need live acceptance.
Device operations do not take the global Unity build lock at
`work/coordination/unity-build.lock`; Unity build/editor work uses that shared host lock.

## Validation tiers

| Tier | Needs | Proves |
| --- | --- | --- |
| Host tests (`./dev test`, CI) | Python and `tools/lab-requirements.txt` | Tooling logic, transforms, safety guards. Runs on a fresh clone without `work/`. |
| Toolchain checks | Exact Unity editor, local .NET SDK, accepted input | Compilation, assembly and catalog contracts (`tools/catalog/*Host.cs`, assembly-slice tests). |
| Device acceptance | Accepted input, generated project, an explicitly configured and authorized device | Actual runtime behaviour. The only authority for gameplay claims. |

Passing an earlier tier never stands in for a later one. Acceptance limits:
[docs/testing-strategy.md](docs/testing-strategy.md); storage policy:
[docs/storage-strategy.md](docs/storage-strategy.md); caching and updates:
[docs/caching-and-updates.md](docs/caching-and-updates.md).

## Scope and distribution

Repository content is original tooling, small transformations and evidence summaries.
User-supplied game data and generated proprietary content are Git-ignored. No DRM,
ownership or authentication bypass is included. Middleware licensing and Android binaries
remain unresolved. Do not redistribute raw `work/` outputs. Before committing, run
`python3 scripts/audit-public.py` (CI runs it too); a passing scan does not replace manual
IP and secret review.
