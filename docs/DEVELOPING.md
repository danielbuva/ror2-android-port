# Developer guide

[Project home](../README.md) · [Player guide](PLAYER_GUIDE.md)

This page preserves the laboratory setup and command reference. Run commands
from the repository root. It is for contributors, not a player installer.

Current independent prepared builds use [build lanes](build-lanes.md):
`./dev lane --action create --name NAME`, then `LAB_LANE=NAME ./dev …`.

An evidence-driven laboratory that runs the original PC game's managed code and converted
content natively on ARM64 Android, using the user's own legitimate game installation.
**It is not a finished or distributable port.** The current APK reaches the original offline
menu, runs original survivors through several real stage transitions, and keeps an
Android-only profile, but only with diagnostic assists so far. Audio, stock platform
services, the Moon finale and PC visual parity are not done. See
[PORTING_STATE.md](../PORTING_STATE.md) for the exact current snapshot.

## Getting involved

Start with the reading order below and the safety rules in [AGENTS.md](../AGENTS.md).
Check the [open backlog](execution-backlog.md) before choosing work, and use the
[journal index](JOURNAL_INDEX.md) to avoid repeating an experiment. Keep changes
focused and distinguish host-test results from device-verified gameplay.

For a reviewed report from an existing standard check, use the
[local baseline feedback preview](BASELINE_FEEDBACK.md). It selects fixed facts
and can include a manual issue-draft URL; settings integration remains open.

For an already prepared laboratory, the [owner-build playtest checklist](PLAYTESTING.md)
connects build identity, selected-device installation, assisted checks and reviewed
feedback. Fresh public-input setup and the final player installer remain open.

For tooling changes, use the [validation tiers](#validation-tiers) and
[testing strategy](testing-strategy.md). Review staged files and run the public
repository audit before committing; never include game-derived outputs or private
captures. Player-facing documentation starts at the [project home](../README.md)
and [player guide](PLAYER_GUIDE.md).

## Read first

1. [PORTING_STATE.md](../PORTING_STATE.md): what is installed, what runs, what is open.
2. [docs/ARCHITECTURE.md](ARCHITECTURE.md): the build pipeline, the Android runtime,
   who owns what, and the known structural debt.
3. [AGENTS.md](../AGENTS.md): the safety, privacy and workflow rules. They apply to people too.
4. [docs/JOURNAL_INDEX.md](JOURNAL_INDEX.md): search it before repeating an experiment,
   then read the matching entry in [docs/PORTING_JOURNAL.md](PORTING_JOURNAL.md).

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
| `recipe/` | Audited, public build recipes: authored transformations and configuration the build reads ([recipe/README.md](../recipe/README.md)). |
| `environment/` | Reviewed, public toolchain pins and examples; raw captures stay ignored. |
| `work/` (ignored) | All game-derived inputs, generated projects, builds, receipts and evidence. Never commit it. What the tooling expects to find there: [docs/LOCAL_STATE.md](LOCAL_STATE.md). |

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

J755 records three explicitly selected devices with separate receipts: the baseline
Nova uses adopted storage only; the second Nova and Thor use internal storage after
live reserve checks. Both standard checks pass on the second Nova. Thor passes
both checks through explicit automatic diagnostics (J762); physical input remains
unmeasured. Both Thor OLED panels sleep during cleanup.
Independent device runs have overlapped, while Unity builds remain serialized.

`./dev inspect --full` creates a reviewed input identity. New or updated inputs must be
reviewed before their ID is recorded in `work/config/accepted-input.json`. No Steam
authentication is needed to inspect the supplied installation.

## Everyday commands

| Command | What it does |
| --- | --- |
| `./dev test` | Host tests in the lab venv. |
| `./dev doctor [--json]` | Toolchain, inventory and dependency-pin health. |
| `./dev preflight [--device SERIAL] [--host-only]` | Current: host/input gates plus selected-device storage; `--host-only` omits device access. |
| `./dev check-baseline` | The standard device check on the installed APK: 35 s of assisted Lakes play, no report error, profile run count unchanged ([docs/BASELINE.md](BASELINE.md)). |
| `./dev editor --target lab --action open` | Start the isolated exact editor and connect the pinned Unity MCP. One editor mutation at a time. |
| `./dev editor --target lab --action siren-input-host` | Current: run the staged source-asset and range-aware Siren input fixture in the idle exact editor; no game/server or encounter acceptance. |
| `./dev editor --target lab --action source-camera-graphics-host` | Current: check real imported profile/resource clones and seven program bindings using inactive editor fixtures; no rendering acceptance. |
| `./dev build [--target vulkan] [--force]` | Host preflight and instrumented IL2CPP ARM64 build through MCP with a content-addressed APK receipt. Rejects stale staged runtime sources. |
| `./dev install [--device SERIAL]` | Install on the selected device after live storage and reserve checks; rejects foreign pre-existing packages and records placement. |
| `./dev sync-data [--device SERIAL]` | Hash-verified sync of changed payload into the selected device's runtime-reported path. |
| `./dev run` | Launch the lab, wait for its checkpoint, collect the runtime snapshot. |
| `./dev logs` · `crash` · `screenshot` · `perf` | Timestamped local captures. |
| `./dev perf --action cpu [--target LABEL] [--device SERIAL] [--profile-scope app]` | Current: 15 s system simpleperf capture of the owned foreground lab app. Default PID mode uses the original event; explicit app mode uses task-clock:u and requires live DEBUGGABLE metadata, with package scope rather than exact PID attribution. No launch or install; permission failures stay recorded per device. |
| `./dev storage [--device SERIAL]` | Live capacity, volume and backing report; changes nothing. |
| `./dev reset [--device SERIAL]` | Uninstall only the selected device's locally receipted disposable lab package. |
| `./dev migrate-device-receipts [--device SERIAL]` | Current: migrate default-device receipts after live ownership verification, preserve originals, activate last. Blocked while the coordination lock exists. |
| `./dev inspect [--full]` · `decompile` · `export-project` · `graphics` | Input inventory and recovery stages (cached, receipted). |

`./dev prototype --action list` lists all actions with help, current first, including
historical actions and the historical default/unknown-name fallback. Historical
descriptions are also in
[docs/history/readme-commands-and-recipes.md](history/readme-commands-and-recipes.md).

The command table moved here from the player-facing README. The existing
`scripts/readme-actions.py` entry point now targets `docs/DEVELOPING.md`, so the
same generation and CI check commands continue to work.

Current actions below are generated from `scripts/lab/actions.py`; do not edit the table
by hand. Regenerate with `python3 scripts/readme-actions.py`; CI checks freshness with
`python3 scripts/readme-actions.py --check`.

<!-- prototype-actions:start -->

| Command | What it does |
| --- | --- |
| `./dev prototype --action phone-wrapper-oracle` | Experimental desktop verification only: --target REQUEST.json selects stage or check for a fresh SDK-only project. The exact editor reports native metadata and concrete Object-descendant wrapper queries under the shared mutex. No game files, player build, installation or phone-build input; preserves existing editors and refuses lock contention. |
| `./dev prototype --action phone-wrapper-search` | Experimental read-only SDK support: --target REQUEST.json selects the pinned owner SDK binary and extracts normal-path assembly/namespace lookup order with argument, branch and return checks. Executes no SDK code and produces no scene roots, game build, install or editor mutation. |
| `./dev prototype --action phone-native-registry` | Experimental read-only metadata support: --target REQUEST.json selects the exact owner SDK binary, stages authored Python readers and reports native registration/module coverage and persistent class IDs. Executes no SDK code, generates no linker roots and changes no editor, package or runtime. |
| `./dev prototype --action phone-root-contract` | Experimental read-only host contract: --target REQUEST.json binds an authored fixture/capture and inventories SDK native-type metadata without executing inspected assemblies. Reports explicit matches separately from name guesses; produces no roots, game build, install or editor mutation. |
| `./dev prototype --action phone-linker-fixture` | Experimental: --target REQUEST.json binds the authored fixture APK/project and exact callback capture for Android UnityLinker replay. Optional native_registry selects a pinned owner SDK binary/hash. Optional module_policy selects builtin-modules-no-overrides-v1 with SDK/package-derived exclusions. Scene roots remain captured. No editor mutation, installation or game build. |
| `./dev prototype --action phone-converter-fixture` | Experimental: stage the authored player's hash-bound stripped closure and exact supplied Unity converter from --target REQUEST.json. An optional linker selector consumes verified phone stripping output; desktop editor roots remain inputs. Build-tool host only; no game, editor mutation or installation. |
| `./dev prototype --action phone-native-apk-fixture` | Experimental: --target REQUEST.json pins the authored fixture APK, matching metadata and ARM64 library hashes; writes a new unsigned native-swap fixture for separate alignment/signing and device checks. Never packages the game. |
| `./dev prototype --action phone-native-fixture` | Experimental: stage only the hash-bound authored content fixture's native graph from --target REQUEST.json, supplied Unity runtime and original NDK target inputs. An explicit converter selector may bind verified phone-generated C++; desktop stripping remains an input. No device or game build access. |
| `./dev prototype --action phone-host-check` | Experimental: explicit --device and hash-bound --target REQUEST.json install only the authored sandbox fixture, verify installed native execution and writable-code refusal twice, then remove the owned package and sleep the display. |
| `./dev prototype --action phone-package-check` | Experimental: explicit --device and hash-bound --target REQUEST.json check the separate phone content fixture, candidate refusal, two native reload cycles, increasing-version data retention and owned cleanup; never installs the game. |
| `./dev prototype --action phone-apk-fixture` | Experimental: repackage only the authored content fixture from hash-bound --target REQUEST.json; writes a new unsigned APK, requiring later alignment/signing. No device or game build access. |
| `./dev prototype --action phone-content-check` | Experimental: check generated --target PROJECT in the exact editor under the primary checkout build mutex; no game project or device access. |
| `./dev prototype --action phone-content-build` | Experimental: build committed authored --target PROJECT as a separate ARM64 IL2CPP/Vulkan fixture APK under the primary checkout build mutex; no install or game build changes. |
| `./dev prototype --action phone-content-fixture` | Experimental: generate an authored TextAsset bundle and isolated exact-editor fixture under work/rebuild/phone-content; no game input, build, install or runtime change. |
| `./dev prototype --action rebuild-step` | Rebuild --step assemblies\|shader-pipeline\|composition\|project-inputs\|catalog-closure\|dependencies\|stage-variants\|source-scenes\|build-entries\|runtime-sources\|importer-identities\|validate-bindings\|unity-build in order under work/rebuild/<input_id>/lab-project (--dest overrides); --compare-only reads an existing destination. |
| `./dev prototype --action owner-assembly-prefix` | Generate only the owner DLL/importer prefix from reviewed input and public recipes, without a project/provenance oracle. Requires a new --dest under this clone's work/rebuild/; --work-dir selects inputs. SDK default; opt-in --assembly-profile public-dotnet8 requires exact --tool-archives, --tool-launcher and --tool-host. No complete project or phone/game qualification. |
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
| `./dev prototype --action survivor-kit-check` | Assisted world skill check: --target all or comma-separated base survivor keys; optional --skill-variants supplies one strict per-run catalog selector; --skill-slot primary\|secondary\|utility\|special runs one bounded isolated native-input diagnostic; --toolbot-offhand runs the exact MUL-T Buzzsaw/Dual Wield sequence and requires --target Toolbot plus --skill-variants; --captain-supply-beacon runs native Captain PrepSupplyDrop, valid placement and owned deployable registration and requires exactly --target Captain with default loadout. Omit --expected-apk-sha256 to require current-build equality at check start; supplying it selects only a matching selected-device ownership receipt and its byte-verified APK, without calling it current. |
| `./dev prototype --action session-cleanup-check` | Observe an original first-stage loss, native cleanup and same-process restart; diagnostic automatic input, gameplay debug assists off. Optional --target selects one base survivor (default Commando); locked choices are diagnostic overrides, no expansion. Optional --skill-variants applies one strict per-run native catalog selector to both sessions. Omit --expected-apk-sha256 to require current-build equality at check start; supplying it binds this diagnostic to the selected device's matching ownership receipt and receipt APK bytes without calling that APK current. |
| `./dev prototype --action session-abandon-check` | After 60 s of ready first-stage play, observe original UI-driven end-run, native listener/template cleanup and same-process restart without an original loss/result; optional --target selects a base survivor (default Commando), locked choices are diagnostic overrides. Optional --skill-variants applies one strict per-run native catalog selector to both sessions. Omit --expected-apk-sha256 to require current-build equality at check start; supplying it binds this diagnostic to the selected device's matching ownership receipt and receipt APK bytes without calling that APK current. |
| `./dev prototype --action session-memory-check` | Repeat ordinary Commando menu-start, 60 s ready Lakes play and UI-abandon sessions in one process (five by default, --sessions 3 to 32); each completed session must pass the session-abandon contract. Reports existing runtime resource samples and per-menu PSS as observations, not a leak fix or normal-game acceptance. Requires --expected-apk-sha256 bound to the selected device's ownership receipt. |
| `./dev prototype --action session-memory-root-check` | session-memory-check plus the opt-in menu-only completed-session root walk: before each later menu, SessionResourceBoundary walks static fields of loaded types and live MonoBehaviour/ScriptableObject roots (bounded, read-only; may run unrelated static constructors) and names reference paths to retained completed sessions. Diagnostic only. Requires --expected-apk-sha256. |
| `./dev prototype --action whole-catalog-host-providers` | Run the whole-catalog native-provider host fixture. |
| `./dev prototype --action whole-catalog-repair-bindings` | Repair recorded whole-catalog root bindings. |
| `./dev prototype --action whole-catalog-build` | Compose content, stage explicit original-audio selection (default off), and build the player. Supports --debug-symbols, --capture-player-linker-inputs and --capture-il2cpp-invocation with the same contracts as whole-catalog-code-build. |
| `./dev prototype --action whole-catalog-code-build` | Build player code while verifying and reusing the frozen payload. Optional --debug-symbols retains matching Unity IL2CPP symbols for this exact APK. --capture-player-linker-inputs opts into the request/source/input-bound pre-strip UnityLinker inventory. Add --capture-il2cpp-invocation to capture the same request's pre-launch rendered IL2CPP line and input directory; it requires --capture-player-linker-inputs and does not claim exact argv or composed-audio stage equivalence. |
| `./dev prototype --action whole-catalog-fast-build` | Iteration only: verify frozen content, export fresh IL2CPP/player Data, splice the normal-build anchor APK, zipalign and sign with the existing lab key (v4 included), skipping Gradle and symbols. Requires a timed normal build anchor. A normal full build remains the acceptance gate. |
| `./dev prototype --action shared-catalog-code-build` | Build this clean committed worktree through the primary checkout/editor under the shared mutex, then restore its branch. Add --full for content/new script metadata. No project copies or device actions. Supports ordinary capture/symbol flags; refuses concurrent source edits. |
| `./dev prototype --action shared-catalog-fast-build` | Iteration only: run this worktree's whole-catalog-fast-build through the primary prepared editor under its mutex, then restore primary source. Same anchor/content/signature checks; no project copies or device deployment. |
| `./dev prototype --action shared-catalog-scripts-build` | Evaluation only: run this worktree's scripts-only/splice comparison through the primary prepared editor under its mutex, then restore primary source. Normal full acceptance remains required. |
| `./dev prototype --action whole-catalog-scripts-build` | Evaluation only: BuildScriptsOnly Development export plus APK splice. Reuses serialized player Data; compare with a normal build before trusting any change affecting serialized state. Requires a normal-build anchor; no automatic device deployment. |
| `./dev prototype --action apk-member-compare` | Host verification: --compare FIRST_RECEIPT SECOND_RECEIPT requires same source/input/API and verified APK hashes, then compares every unsigned APK member. Records all differences, including build GUIDs; does not install or promote acceptance. |
| `./dev prototype --action whole-catalog-run` | Install, sync and run the catalog-registration check. |
| `./dev prototype --action shader-outline-candidate` | Host-only: --target outline-highlight generates the original two-pass shader candidate at a stable ignored path; editor compilation and Android appearance remain unverified. |
| `./dev prototype --action shader-ramp-fog` | Current host-only native single-pass reconstruction: optional --target ramp-fog (default), sobel-buffer or sobel-outline. Refuses source/tool drift and existing output; editor compilation, Android execution and appearance remain separate gates. |
| `./dev prototype --action shader-screen-damage` | Host-only: reconstruct the accepted native ScreenDamage pass at a stable ignored path; refuses source/tool drift and overwrites. Editor compilation, Android execution and appearance are separate gates. |
| `./dev prototype --action shader-translucent` | Host-only: generate four source-bound camera blur/crop shader candidates under ignored work/. Refuses input, tool, helper or output drift. No catalog activation, Unity compilation, Android rendering or visual parity is implied. |

<!-- prototype-actions:end -->

The full build consumes the current prepared catalog. After changing catalog roots
or conversion membership, run `whole-catalog-prepare` and `whole-catalog-host`
before building; existing preparations remain available as evidence.


## Current integration loop

The active composition is the whole-catalog integration
([docs/whole-catalog-integration.md](whole-catalog-integration.md) has the full
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

For a current code build with matching IL2CPP debugging symbols, add
`--debug-symbols` to `whole-catalog-code-build`. This opt-in mode retains the
APK and symbols ZIP together, verifies their ARM64 library Build IDs and
debug information, and uses a separate cache. Ordinary builds request symbols
off. Retained symbols support later offline attribution; CPU capture does not
automatically use them.

`./dev build` refuses to package when authored runtime sources differ from the staged copies,
so a stale APK cannot pass as feature evidence. Gameplay runs on the device are currently
driven by runner scripts kept under the ignored `work/experiments/whole-catalog/gameplay/`;
they are not yet tracked (see [docs/LOCAL_STATE.md](LOCAL_STATE.md)).

The selector, scoped receipts and receipt migration passed on the current Nova (J595).
Additional devices and concurrent device runs still need live acceptance.
Device operations do not take the canonical Unity build lock at
`work/coordination/unity-build.lock`. Canonical build/editor work uses that lock;
[isolated lanes](build-lanes.md) each use their own persistent build lock and
editor. Device ownership stays global across all lanes.

## Validation tiers

| Tier | Needs | Proves |
| --- | --- | --- |
| Host tests (`./dev test`, CI) | Python and `tools/lab-requirements.txt` | Tooling logic, transforms, safety guards. Runs on a fresh clone without `work/`. |
| Toolchain checks | Exact Unity editor, local .NET SDK, accepted input | Compilation, assembly and catalog contracts (`tools/catalog/*Host.cs`, assembly-slice tests). |
| Device acceptance | Accepted input, generated project, an explicitly configured and authorized device | Actual runtime behaviour. The only authority for gameplay claims. |

Passing an earlier tier never stands in for a later one. Acceptance limits:
[docs/testing-strategy.md](testing-strategy.md); storage policy:
[docs/storage-strategy.md](storage-strategy.md); caching and updates:
[docs/caching-and-updates.md](caching-and-updates.md).

## Scope and distribution

Repository content is original tooling, small transformations and evidence summaries,
plus the two promotional graphics documented in [branding notes](assets/branding/README.md).
User-supplied game data and generated proprietary content are Git-ignored. No DRM,
ownership or authentication bypass is included. Middleware licensing and Android binaries
remain unresolved. Do not redistribute raw `work/` outputs. Before committing, run
`python3 scripts/audit-public.py` (CI runs it too); a passing scan does not replace manual
IP and secret review.
