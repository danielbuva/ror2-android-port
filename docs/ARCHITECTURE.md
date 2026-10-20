# Architecture

What runs today, how it is built, and who owns what. The ADRs explain *why*
([ADR-001](ADR-001-port-architecture.md)); this page is the current map. Update it when a
file, owner or pipeline step is added, moved or retired. Results and evidence live in the
[journal](PORTING_JOURNAL.md); the files the build expects under `work/` are listed in
[LOCAL_STATE.md](LOCAL_STATE.md).

Documentation entry points: [project home](../README.md) and
[player guide](PLAYER_GUIDE.md) explain availability for players.
[DEVELOPING.md](DEVELOPING.md) owns contributor setup, the repository map and
command reference, including the generated prototype-action table.

Public alpha delivery: [ADR-002](ADR-002-public-alpha-distribution.md) accepts
owner-built APKs and locally reconstructed content; [public-alpha.md](public-alpha.md)
holds open release work. ADR-001's architecture C and the runtime pipeline below
remain current. [phone-owner-build.md](phone-owner-build.md) assesses build stages
for phone-only delivery while retaining the desktop workflow as fallback; no
replacement game runtime or working build pipeline is selected. Public-input bootstrap,
performance equivalence and device acceptance remain open.

Phone build **support**: `scripts/lab/phone_bundle.py` writes the isolated authored
TextAsset bundle with only Python's standard library; its versioned native
schemas consume no class database or generated asset. `phone_content.py` owns
project staging and source/bundle hash checks for that fixture.
`tools/phone-build/ContentFixtureBuilder.cs` owns its exact-editor check and
separate player build; `ContentFixture.cs` loads either its embedded bundle or
a hash-bound candidate at a fixed path in its own data directory. It checks two
load/unload cycles and writes a private report. The three `phone-content-*` prototype
actions stage/check/build only this fixture under the primary checkout mutex.
See [probe setup and boundaries](../tools/phone-build/README.md). No game-runtime
owner or whole-catalog build calls this support path.

`scripts/lab/phone_apk.py` is separate packaging **support** for that authored
fixture only. Its standard-library parser increases a literal Android manifest
version code after checking the fixed package identity, substitutes the authored
bundle, preserves other entry bytes and removes obsolete signatures. It writes
new unsigned outputs; alignment and owner signing follow separately. The current
`phone-apk-fixture` action takes an ignored hash-bound request via `--target`;
the same file has a standalone Android CLI. It cannot repackage the game ID.

`phone_package_check.py` owns the separate fixture's device acceptance: require
explicit selection, local APK hashes, matching shell-workspace ownership and
fresh storage/capacity checks; exercise embedded input, refused hash drift,
phone-produced input, native reload/unload, a version-code upgrade and data
retention. Its `finally` removes only a package whose actual APK hash matches
the owned attempts and verifies display sleep. It records game APK hashes
read-only before/after. `phone-package-check` takes an ignored request and
writes private evidence under `work/experiments/phone-packaging/`.
The player publishes actual Android/Unity data paths in its private bootstrap
report; the runner binds canonical paths and their separate backing stores
before reading reports or copying candidates. Editor checks/builds each write
an isolated oracle report and require its pinned actual Unity version and
native content checks, independently of process exit status.

Status words used below: **current** (part of the shipped whole-catalog game or the
commands that build it), **support** (editor builders, host fixtures and tooling around the
current path) and **historical** (kept for evidence; not reached by current commands).

## Build pipeline

The user's legitimate PC installation goes in; an ARM64 IL2CPP APK plus an independently
synced content payload comes out. Everything game-derived stays under the ignored `work/`.

| # | Step | Command | Main code | Output under `work/` |
| --- | --- | --- | --- | --- |
| 1 | Accept input | `./dev inspect --full`, then record the ID in `config/accepted-input.json` by hand | `scripts/lab/inventory.py` | `inventory/` |
| 2 | Check before building | `./dev preflight` (host + selected storage); `--host-only` omits device access; builds run host gates | `scripts/lab/build.py` (`preflight_host`, `preflight`) | selected preflight receipt; refuses on drift |
| 3 | Decompile and export | `./dev decompile`, `./dev export-project` | `scripts/lab/recovery.py` | `config/reconstruction.json`, exported project |
| 4 | Assembly transforms | `./dev prototype --action assembly-transforms-check` (verification only) | `scripts/lab/assembly_transforms.py` → `tools/assembly-transforms/` | none; verifies three transformed plugins in disposable `.local/` scratch |
| 5 | Compose the project | `./dev prototype --action composition-update-stage`, then `composition-update-dependencies` | `scripts/lab/composition_migration.py` | `lab-project/` |
| 6 | Whole-catalog content | `whole-catalog-prepare` → `-host` → `-repair-bindings` (when recorded) → `-contracts` → `-host-providers` | `scripts/lab/whole_catalog.py`, `tools/catalog/` | `experiments/whole-catalog/<timestamp>/` |
| 7 | Bundles, payload, APK | `whole-catalog-build`, or `whole-catalog-code-build` for a code-only change | `whole_catalog.py` (writes the linker descriptor through `preservation_descriptor`, J506; refuses uncommitted `tools/unity`, `tools/catalog`, `android/Assets/Editor` sources, `build.build_source_identity`, J738) → `build.py` → exact editor via MCP | APK + payload receipts, with `source.commit` |
| 8 | Install and sync | done by `whole-catalog-run`; alone: `./dev install`, `./dev sync-data` | `scripts/lab/device.py` | placement receipt |
| 9a | Catalog registration scan | `whole-catalog-run` | `whole_catalog.run_integration` | `integration-<timestamp>/device-<timestamp>/` |
| 9b | Gameplay run | `./dev check-baseline` for the standard check ([BASELINE.md](BASELINE.md)); broader runs still use untracked runners in `work/experiments/whole-catalog/gameplay/` ([debt](#known-structural-debt) item 8); captures: `./dev logs`, `crash`, `screenshot`, `perf` | `scripts/lab/baseline.py` + `device.py` | `experiments/baseline/<timestamp>/`, `movement-batch-*.json` |
| 10 | Record | append a journal entry, `python3 scripts/journal-index.py`, replace `PORTING_STATE.md` | — | — |

Steps 6–9a are the `./dev prototype --action whole-catalog-*` actions listed in
[whole-catalog-integration.md](whole-catalog-integration.md#reusable-fixes-and-commands).
`whole-catalog-run` installs, syncs and launches, but it pushes `whole-catalog-selection.json`,
which makes `PortSession.Start` exit: it checks catalog registration
(`whole-catalog-result.json`), not gameplay. Gameplay is launched by a runner that pushes an
attempt-bound `movement-batch-selection.json` and then launches the app.
The exact editor is started with `./dev editor --target lab --action open`; send it one
mutation at a time. Device acceptance is always the real device, never the editor.

Current optional debugging symbols (`--debug-symbols` on `build` or
`whole-catalog-code-build`) flow through `main.py`/`actions.py` to
`whole_catalog.py` and `build.py`. `LabBuild.cs` requests
`AndroidCreateSymbols.Debugging` in a fresh request directory; ordinary requests
select `Disabled`. Its `finally` restores the prior editor setting.
`scripts/lab/symbol_artifacts.py` verifies the sole request-owned ZIP, mandatory
APK/ZIP/library hashes, matching ARM64 ELF GNU Build IDs, named symbols and
DWARF information. The symbol-mode cache includes the validator hash and retains
both artifacts; missing, ambiguous or altered artifacts refuse reuse. These
files are generated build outputs, not new required local input. Archive reads
are bounded separately: 512 MiB for the stripped APK library and 2 GiB for the
full debugging library. Host contracts: `test_symbol_artifacts.py` and
`test_symbol_build_mode.py`. J765 validates the first exact-editor ZIP and
matching ELF identities after correcting the debugging size bound; canonical
build publication and device qualification still require the retry. Retention
alone does not symbolicate the existing `performance_capture.py` report.

`--capture-player-linker-inputs` on `whole-catalog-code-build` is current,
opt-in build support for audio integration. `PlayerLinkerInputCapture.cs` in
`android/Assets/Editor` implements the pinned editor's `IUnityLinkerProcessor`;
the existing Android-asset staging owns its copy. The callback preserves an
inert linker descriptor on ordinary builds. Opted-in captures require the
active request ID, committed source ID, accepted input ID and Android target.
They inventory only Unity's supplied pre-strip `inputDirectory` and independently
copy every DLL to request-owned ignored storage, checking hashes before and
after the copy. No Library/Bee directory search supplies inputs.

`scripts/lab/player_linker_receipt.py` verifies saved path/hash/size identities
and seals that inventory with the successful request and APK hash. `build.py`
gives each capture a fresh request-specific output/cache namespace and refuses
reuse; default builds retain their existing invocation/cache behavior. Output
ancestry, stale identities, changed snapshots and missing callback evidence
refuse. This is a UnityLinker-input receipt: a same-request comparison with the
actual linker/IL2CPP invocation is still required before calling it the complete
player closure. `test_player_linker_receipt.py` covers identity/dispatch/refusal;
`test_describe_runtime.py` executes the actual C# copy/output helpers against
minimal host stubs and skips without the pinned Mono compiler. Exact-editor
compilation and later device acceptance remain separate. This narrow
build-receipt addition serves original audio; alpha retains packaging ownership.

`whole_catalog.analyze` owns the host dependency closure. Audit, reconciliation
and root-binding repair supply the accepted decompile root to
`entity_state_gameobject_fields`, a scoped field reader checked against the
accepted assembly metadata. `entity_state_reference_closure` follows serialized
string GUIDs only for native EntityStateGameObject fields, retaining inherited
field identity and nearer-field shadowing. It requires an exact unique original
GameObject catalog location and existing conversion; unresolved or ambiguous
edges remain explicit issues. Resolved files enter the existing closure walk
and manifest without becoming provider roots. No runtime loader alias or
gameplay-state replacement implements this repair. Host contracts live in
`tests/test_whole_catalog.py`; generated closure/manifest data remains ignored.

### Device selection and storage receipts

Device selection uses an explicit allowlist/default model.
`work/config/local.json` accepts `device_serials`,
`device_serial`, and `device_settings[serial]`. Device actions accept `--device SERIAL`
or `LAB_DEVICE=SERIAL`; with multiple attached devices and no explicit selector, they
refuse to choose. An explicit serial outside the configured allowlist also refuses.
Top-level legacy settings are fallback values for the default device only. Per-device
overrides cover `storage_mode` (`adopted` or `internal`), `internal_reserve_mib`,
`apk_install_limit`, `sleep_display_when_idle`, `display_models`, and `display_count`.

`scripts/lab/device_context.py` owns pure selection, storage policy and receipt namespace
resolution. Its explicit migration transaction requires verified ownership, preserves
source receipts/counters, and publishes `.device-context-active.json` last. Hashes in that
marker audit the original copy; ordinary receipt updates and reset keep the namespace
active. A malformed marker refuses selection. `Device` freezes the selected serial,
settings and receipt root. All current and
retained historical device callers use that instance's receipt API. CLI cleanup sleeps
only the exact instances it awakened, including on failure. Dual-panel profiles require
both physical internal panels to report OFF before sleep is accepted.

Receipt and evidence paths reject symlinks and non-directory components beneath the
chosen work root; an explicitly chosen work root may itself resolve through a symlink.
Every receipt lookup rechecks the active namespace and refuses a changed root. JSON
receipt/counter links also refuse, including dangling links during migration.
`Device.evidence_directory` validates new per-device evidence paths before creation.
Bootstrap smoke records install dispatch separately from success: an ambiguous failure
queries the selected package and cleans up only when it was absent before dispatch and
is now confirmed present. An unavailable follow-up query preserves the primary failure
and reports cleanup uncertainty.

`scripts/lab/installed_attempt.py` owns read-only diagnostic selector identity
for baseline, survivor and completed-session checks. After `Device.owned()`
validates selected-device ownership/placement, it reads the receipt's APK artifact
once, verifies that byte snapshot against the receipt hash, and parses the same
bytes with the existing UnityPy reader. Exactly one authored MovementBatchProbe
TextAsset must supply a nonempty attempt. No mutable project config, latest-build
attempt, cache search or timestamped run evidence supplies identity. The exact
owned artifact must remain available; missing/changed/ambiguous content refuses
before selector writes. This helper writes no receipts and changes no storage,
package or current-build gate. `test_installed_attempt.py` covers identity,
refusals and replacement during parsing; runner fixtures keep project and
installed attempts different.

`scripts/lab/build_lock.py` owns a persistent advisory kernel lock and owner diagnostics.
It is reentrant in one thread and hands its open descriptor to the editor client. Build
coordinators retain it through staging, Unity completion and result publication; editor
actions share it and refuse an outstanding player build. Bootstrap batch builds use the
same path. Device runs do not acquire it. Direct editor player-build dispatch requires
the receipt-polling coordinator. Protected R9 direct helper integration remains deferred
while the parallel session owns that file; its supported CLI enters through the shared
whole-catalog/build coordinator.

Session ownership and the host build mutex are separate. The incumbent session must
remain able to use the existing CLIs while it holds its coordination file. A waiting
orchestrator checks that file before every editor/device action and can additionally set
`LAB_COORDINATION_GUARD=1` for transport-level refusal. That opt-in is not ownership
authentication. Migration always refuses while the file exists, regardless of this
setting. The host Unity build mutex is mandatory for every caller.

`./dev preflight` combines host/input validation with selected-device live storage checks.
`./dev build` runs host preflight only and holds the global Unity build lock at
`work/coordination/unity-build.lock`; install, sync and gameplay actions do not take that
lock. Every install still queries live storage and free space and enforces the selected
device reserve. Scoped receipts live under `work/device/<serial>/`. The explicit
`migrate-device-receipts` command migrates legacy `work/device/` receipts after the
coordination lock clears, preserve the originals, and write its activation marker last.
J595 migrated the configured Nova's receipts and verified both baseline modes after an
in-place adopted-storage install. Legacy receipt bytes remain intact. Extra devices and
their storage/display contracts remain unvalidated until explicitly allowlisted.

J755 records the authorized three-device configuration: baseline Nova uses adopted
storage only, second Nova and Thor use internal storage with live reserve gates.
The second Nova passes both standard game checks after the current attempt-bound
measured Nova mapping is supplied. J762 qualifies Thor's explicit automatic
diagnostic path through both standard checks; physical input remains unavailable.
Its two physical panels both verify OFF. Under the J818 session split, this
gameplay session owns original gameplay, audio and animations on adopted Nova.
The separate public-alpha session owns launcher/packaging, controls, settings/UI,
end-run menus, feedback, stability/memory and playtest tooling on internal Nova.
Thor is an unassigned shared spare and needs explicit agreement before use.
Each device has one runner; the shared Unity build lock still serializes builds.
These roles do not imply generic-controller, normal-game or performance
acceptance on the additional devices. Installs select an explicit device and
the session's own frozen APK rather than a mutable current-build pointer.

`InputSessionPolicy` in `NovaInputBoundary.cs` owns the explicit game-input
choice. The exact Nova model retains measured, attempt-bound physical input.
Only the observed Thor model with the existing `-bringup` selector permits
automatic diagnostic input without a physical mapping. Ordinary Thor, missing
and unknown model identities refuse. `NovaInputBridge.automaticDiagnosticOnly`
defaults false, so legacy mapped and null-mapping behavior is retained.
The validated diagnostic path reports its source and unavailable physical
input, bypasses raw joystick/presence reads, and feeds the existing input bank.
The offline application/settings and integrated-world owners retain touch
menus, hide physical takeover and guard physical restart/settings consumers.
Their existing iterator cleanup and bridge disable neutralize input and
release session ownership. `test_portable_diagnostic_input.py` executes the
production policy/predicates and checks consumer guards; device acceptance is
separate (J762). Availability flags are authoritative: Unity's JSON serializer
can emit default inline mapping/raw placeholders for null runtime references;
those wire values are not measured input. This changes existing R8 sources
without adding a runtime file/GUID.

`NovaInputBridge` also owns an opt-in cumulative skill-edge witness at the
existing `PushState` sink. `SurvivorSkillInputCoverage` enables it only for the
bounded MUL-T diagnostic, snapshots each request, and requires one fresh edge
after a later physics tick alongside the native callbacks and stance. It refuses
missing/reset/ambiguous witnesses and disables observation on stop/dispose;
neutral cancellation precedes sampling. Ordinary input requests and other
coverage modes retain their existing paths. Host contracts execute the production
counter/classifier, including late sampling and a second edge across separate
samples (`test_toolbot_input_edge_witness.py`). J764 records the motivating
device failure; the durable witness still needs its own device build.

CPU capture (`scripts/lab/performance_capture.py`, current host implementation):
`./dev perf --action cpu --target LABEL` takes a 15 s system simpleperf call graph
from the selected device's already running, owned foreground lab process. Setup
validates ownership, APK hash, one PID, foreground activity and the validated runtime
receipt. Before/after reports preserve available attempt/session/stage/frame context;
a changed process, APK or previously available session identity fails. It does not
launch gameplay or install a profiler. J610's first current-Nova attempt is refused
by Android perf-event permissions; no call graph is available from that path.
Raw profile, symbol report, receipt and failures stay in validated
`work/device/<serial>/performance/<attempt>/`. A symbol-report failure retains the
successful raw capture and explicitly records the report error. Teardown removes
only its unique remote profile after a verified nonempty pull; a failed pull or
timeout preserves the remote output without guessing a process to kill. The caller
retains ownership of the existing gameplay run and display. Host transport/refusal
contracts are in `test_performance_capture.py` and `test_performance_cli.py`.
Typed survivor/diagnostic/assistance/profile metadata and runtime errors accompany
each available endpoint. `stable_stage_gameplay` qualifies the two sampled
endpoints separately from raw capture success; missing context, non-playing
phase, changed scene/transition count or runtime errors prevent that claim.
Matching survivor identity is reported separately. These endpoint comparisons
do not prove uninterrupted gameplay or complete ability behavior between samples.
Explicit `--profile-scope app` selects an independent software task-clock:u
hypothesis and requires live selected-package DEBUGGABLE metadata. It retains
all ownership/PID/foreground/runtime endpoint checks, but labels the raw profile
as the owned package process set with pid_attribution_exact=false. The system
simpleperf may internally use Android's app-UID helper; the wrapper requests no
root, launch, restart, profiler installation or settings change. Device syntax
and permission support remain measured gates. Any denial is preserved without
retry or fallback; default PID mode remains unchanged. This mode is not a
successful trace until the selected device produces one.
J761 records a selected internal-storage device's app-scope capture. Its
qualification includes stable run/stage endpoints; it supplies no exact-PID,
managed-caller, frame-window or sustained-frame-rate guarantee. Camera frame
counters are cumulative, while timing recorder averages reset on each sample;
compare their actual intervals rather than treating a cumulative maximum as a
new stall in every report.

Bare `./dev perf` retains the existing dumpsys capture behavior.

Assembly transform verification (`scripts/lab/assembly_transforms.py`, current):
`recipe/assembly-transforms.json` pins the accepted input, AssemblyProbe sources,
Mono.Cecil and ordered arguments/input/output hashes. The checker first applies
`--optional-presentation-guard` to original `RoR2.dll`, then independently applies
`--wwise-unavailable` to the original API/MonoBehaviour Wwise pair. `AudioGuard` is
historical; the optional presentation transform already includes its getter change.
The checker copies managed DLLs to scratch for resolution, builds the tool there,
and compares rebuilt hashes with the recipe, generation marker and uniquely placed
project plugins. Any drift fails. `--work-dir` selects read-only inputs in another
local work tree. Temporary tool/intermediate/plugin files are removed on success
or failure; there is no persistent state. This verifies plugin bytes only, not
importers, script orders or project initialization. Host contracts:
`tests/test_assembly_transforms.py`.

Audio remains unavailable in the composed game. Separate native diagnostics
use one disposable engine owner for exact bank buffers, listener/emitter,
event callback, bounded output capture and cumulative monitor; reverse cleanup
retains uncertain ownership. The private managed owner tests the retained
Wwise interface in fresh Unity players and is not the normal game controller.
Its Android filename resolver registers the verified app-private bank directory
with `AddBasePath` after `SetBasePath`, matching the official integration's
POSIX-storage seam. Each result has a separate diagnostic phase; refusal keeps
the first result through owned reverse cleanup. The private managed event owner
pumps RenderAudio with callback serialization each frame. Capture stop moves to
a bounded finalization state; the actual fixture caller keeps pumping while
healthy pending work waits for two consistent stable RIFF observations. Unknown
native outcomes retain ownership and prohibit unload/Term. The strict PCM
container profile preserves a zero valid-bits field as unknown precision;
container output, effective precision and physical audibility are separate facts. File loading, cumulative
middleware errors, event callbacks, PCM and composed gameplay have separate
acceptance gates; a successful bank result cannot qualify all of them.
Their setup/input boundaries are listed in
[LOCAL_STATE](LOCAL_STATE.md#isolated-wwise-diagnostic-inputs); experiment
acceptance and limits are recorded once in J740/J742 and J791. Neither diagnostic owner
changes the default assembly transforms or the current game build pipeline.

The ignored native-build-feasibility producer recompiles the authorized Android
bridge against its exact SDK with an isolated, process-local NDK r25c. Unity
keeps its pinned r21 toolchain. Its authored same-library diagnostic bridge and
serializer hook must keep the monitor armed through engine and callback-manager
Term; explicit return witnesses gate disarm, and bounded capture counters do
not acquire another engine owner. J794 qualifies only the static ELF's export,
import and dependency closure. J802 corrects the output-ID width and loads the
replacement, then refuses its pre-Init callback-observation assumption before
engine Init. Registration and delivered callback coverage are separate facts;
monitor continuity and capture callbacks remain runtime gates. The library is
outside the game. The private NativeMonitorLease owns diagnostic registration,
return witnesses and disarm state; its injected API is a host contract seam,
not native callback evidence. First failure and uncertain outcomes remain
visible through owner teardown.

The next private monitor protocol uses schema 3 with 24 snapshot slots. A
conservative latch precedes the actual engine Init attempt; pre-Init registration
does not imply callback coverage. An exact native control marker gates bank and
event work after Init. Both actual Term returns gate disarm; post-Term message
delivery is explicitly unsupported. J810 records the loaded candidate's missing
marker and completed cleanup. J816's serviced wait moves Init-bank loading and
the initialization delegate after the marker. It records successful callback
and RenderAudio service, but still times out before bank/event work. Neither
startup change is an established SDK requirement. The next bounded diagnostic
exposes the first any-level managed message while retaining the exact native
marker gate; generic message delivery cannot qualify that gate. The isolated
stage/build adapter pins the editor instance, current managed sources, historical
provenance and importer metadata separately; partial reload responses and terminal
build requests remain preserved. These private support producers are listed in
LOCAL_STATE and do not enable audio in the game.

J821's first-message player builds with the helper imported and its complete
source/metadata closure frozen. Its Main attempt produces no bootstrap report,
so neither monitor delivery nor runtime storage backing is established there.
Startup observation precedes any further engine change; owned package removal
is separate from unobserved native owner teardown.

The private composed-audio candidate has separate `GameAudioProcessHost` and
`GameWwiseRuntime` owners for opt-in startup, bounded native service and owned
teardown, with an identity-bound `GameAudioPostEventGate` around the recovered
offline pickup callback. J820 qualifies its full frozen host closure scan and
three disabled-profile assembly identities. It is not a current game owner:
current-player source/APK binding and native runtime acceptance remain closed.
Exact Timeline/diagnostic-event and Collections indirect-call classifications
belong to its transform, without changing the pinned package implementations.

`tools/wwise-android-abi/generate.py` is a current, explicitly invoked host
support tool with policy in `recipe/wwise-android-abi.json`. It reads the
exact policy-bound accepted managed API, authorized local Wwise Android
declarations, the pinned Android OS-string helper source and ARM64 Release
plugin, and uses Unity-bundled Cecil. The writer applies the reviewed P/Invoke
metadata and one exact-signature OS-string call-operand rewrite, refusing
body/signature/operand drift and verifying every other method and assembly
contract after reopen. It publishes only new plans and candidates under ignored
`work/`, refusing overwrite and symlink paths. It remains separate from the default
assembly-transform and game-build paths. Its incomplete Android ABI candidate
has 11 unavailable imports and does not enable production audio. The authored
tool and policy are audited in `recipe/README.md`; synthetic host contracts
are in `tools/wwise-android-abi/test_synthetic.py`.

`scripts/lab/wwise_init_platform.py` is a current, explicitly invoked support
tool for those isolated diagnostics, with its metadata contract in
`recipe/wwise-init-android.json`. It requires the configured legitimate source,
a full inventory matching the accepted input and an explicit source hash. It
hashes and transforms one byte snapshot, removes only the checked unsupported
Controller Speaker metadata and retargets the two checked root buses to the
existing System device. It creates a new bank and receipt exclusively under
ignored `work/`; original inputs and the default game payload are untouched.
There is no persistent engine state or `./dev` action. Synthetic structural,
input-binding and path/refusal contracts are in
`tests/test_wwise_init_platform.py`. Native acceptance remains scoped to
J740/J742; this generator does not establish full-bank or controller fidelity.

The updated-input transform also guards native `SkillResponseBehavior.OnDestroy`
when its skill array was never initialized by `Start` (J638). An absent array
returns without event work; an existing array executes the original cleanup IL.
The generator preserves assembly/MVID/type/field/method identity and audits all
other bodies. `SkillResponseCleanupExactEditorFixture` invokes the native base
lifecycle on isolated inactive fixture objects and verifies subscription removal
without claiming automatic Unity lifecycle or culprit-template attribution.
`assembly_transforms.generate` produces these plugin bytes from supplied originals;
working-project staging must hold the host editor lock and batch asset editing,
verify the prior plugin/generation hashes, and update the local generation marker.

Incremental project rebuild (`scripts/lab/rebuild.py`, current, R0–R9):
`unity_rebuild.py` owns R9 `unity-build` after `validate-bindings`: destination-only
host preflight, an exclusive operation lock, exact-editor batch invocation through
`whole_catalog.build_integration(destination=...)` → `build.build(destination=...)`
→ `LabBuild.BuildDestination` → the existing full `LabBuild.Build`. It runs two editor
sessions: `LabBuild.RepairDestinationPlugins` force-reimports the managed DLLs and exits,
so their recompilation settles; `BuildDestination` then reimports their asset dependents
in one batch per dependency layer (J585), runs the read-only script gate on the recovered
HUD/Menu components and TimerText targets, and enters the unchanged real build (J578–J581). Reimport errors that
pass 1's fresh import did not log are recorded and make R9 unequal after the build.
Per-asset missing-script counts and MonoScript identities live in the run's
`lab-build/script-audit.json` and successful destination receipt. `script_audit.py`
owns selection generation, working-editor MCP payload generation and comparison;
it never invokes an editor or stages working-project files. Scenes are audited from
their text, not opened; the destination error listener detaches before the real build
and on failure. Operator commands: [script gate](rebuild-plan.md#destination-script-import-gate).
The default project Library is destination-local. Per-attempt requests/logs/APKs/payload and
Android/Gradle homes stay under `.rebuild/unity/`; the summary and hash comparisons
are `.rebuild/unity-build.json`. Cleanup releases the R9 lock, preserving failed
runs; Unity locks are never removed. Both destination and working-project editors
must stay closed. The existing local debug signing key is copied read-only into
the destination to preserve in-place install compatibility. Real build cache keys,
paths, payload reuse and receipts keep their default behavior. `preflight --dest`
uses the same read-only host/input/binding gates without live preflight receipts.
`install --apk` and `sync-data --payload-dir` keep the existing `Device` safety
checks; explicit device-action `--work-dir` selects the existing device receipt
and config tree. Rebuild `--work-dir` is read-only. Comparison groups and exact
operator/restore commands: [R9](rebuild-plan.md#r9-isolated-unity-importbuild-current-not-yet-equivalent).
Host contracts: `tests/test_unity_rebuild.py`. The first R9 APK passed both device checks
but is not yet equivalent to the working project's (J582; causes in J583).

`build_entry_rebuild.py` owns host-only R7 `build-entries` and R8
`runtime-sources`, after `scene_rebuild.py` supplies R5/R6. It uses destination
`StageIO` buffers, explicit retained-input hash gates and completion markers. R7
regenerates its three decompiled map sources with the pinned decompiler
(`recovery.ilspy_project`) and reads the bootstrap attempt from the public recipe;
only the runtime-contract result remains a retained input (J597);
`finish` verifies selected output hashes/sizes before flushing. It shares
`whole_catalog.generate_build_maps`, `stage_build_sources` and
`generate_build_bootstrap` with the real build. `build.stage_android_assets`
retains the real copytree and provides buffered destination placement. No Unity
import or build runs here. `validate-bindings` is the final read-only host gate;
its receipts, membership rules, remaining pins and uncovered provenance are in
[rebuild-plan.md](rebuild-plan.md#r7r8-host-build-entries-and-sources).

`importer_rebuild.py` owns current host step `importer-identities`, after
`runtime-sources` and before `validate-bindings`/R9. It renders recorded public
GUIDs and shared importer schemas from `recipe/importer-identities.json`, checks
all selected hashes/sizes before placement and records
`.rebuild/importer-identities-result.json` plus its completion marker. Folder
importers are left to Unity at R9 (J575); R9 classifies them and rescans the
minted folder GUIDs for references. These receipts have
no process lifetime or cleanup requirement; reruns replace them only after the
cohort gates pass. `validate-bindings` requires the completion marker; R9 removes
this step's membership from its remaining `unity-generated` comparison. No local
provenance map is edited. Host contracts: `tests/test_importer_rebuild.py`;
[scope and operator usage](rebuild-plan.md#pre-import-importer-identities-current).

Host prerequisites (`shader_rebuild.py` and `project_input_rebuild.py`, current):
R1 → `shader-pipeline` → R2 → `project-inputs` → R3–R8 → `importer-identities` → final bindings.
Shader repla…26015 tokens truncated…ty_context_phase.py`, `test_source_identity_transform_parity.py`.

The first-stage source lifecycle diagnostic retains the full native stage deck,
source toggle references and original Run RNG. It omits the older temporary
Beetle/CombatDirector fixture, arms population observers before native Start,
and records only genuine native server Stage-begin. The offline path has no
local NetworkUser, so server-begin does not prove Stage.Start's client
continuation or `onStageStartGlobal`. Unknown/platform global scene-change
subscribers refuse; no event queue is cleared to force progress.

`WholeInteractableSession` captures each source table binding's exact component,
GameObject, scene, label and instance IDs before changing its borrowed field.
`NativeSourceBindingRestorePolicy` in the same owner file requires the bound,
valid, loaded, active scene. A live component must still reference the captured
live GameObject in that scene. For a destroyed component, the captured GameObject
must independently be Unity-fake-null with both managed references retained;
bind-time validation must identify one of the four exact mutable native public
PickupDropTable fields. The existing captured lease then restores that managed
field and still refuses foreign replacements. A component-only destruction with
a live GameObject/child consumer refuses. No field restoration is skipped and
providers remain held until all leases restore; failure retains recovery state.
`NativeSourceBindingWitnessFormatter` reports each predicate without dereferencing
dead wrappers. The portable policy/lease and formatting tests do not simulate
Unity destruction.

The existing editor fixture file also owns
`NativeSourceFieldFixture.WakeManagedFieldLeaseExactEditorFixture`: a disposable
inactive preview hierarchy exercises the production field schema and policy,
component-only destruction with a surviving child pickup consumer, full hierarchy
retirement, managed field restoration, idempotence and foreign replacement.
It restores before releasing temporary tables and closes the preview scene in
finally. It does not start gameplay or establish that native WakeSpawner ran.

Source identity retirement verifies the captured server mapping and current
ID mapping are absent after owned `UnSpawn`, then invokes native `Reset` for
the exact retained captured ID even when host-mode `OnNetworkDestroy` already
cleared `isServer`. Changed IDs/foreign remapping refuse; the postcondition
requires zero ID and cleared server/client flags before active-state restore.
No private identity state is assigned. `test_native_identity_reset.py` executes
the authored production rollback method against host-order HLAPI doubles;
actual native cleanup/restart remains a device gate.

`sourceStageLifecycleRecoveryRequired` keeps the exact nested iterator,
body/master, Run, server/client, scene and provider/catalog graph alive after
partial native acquisition or failed retirement. Destructive upstream finalizers
stop at that gate; an incomplete retained attempt is a failure. A narrow early
Director-prepare catch can conservatively retain recovery after restoring the
SceneDirector before observer disarm. Main-path safe abort disarms first; the
early edge is not represented as a successful safe abort. Native callback order,
placement, cleanup and failure recovery still require runtime evidence.

C# under `tools/` is formatted with `clang-format -i` using the repository's `.clang-format`
(J544). It never rewraps string literals or comments, so a correct reformat leaves each file
identical once whitespace is removed; check that before committing a reformat. CI does not
enforce it, because other clang-format versions format C# differently.

Host CI also runs Ruff (pinned in `tools/lab-requirements.txt`, configured in `ruff.toml`):
`ruff check` and `ruff format --check` on every Python file a change touches. `scripts/` and
`tests/` are ruff-formatted (J518); `ruff.toml` lists the rules still off and why.

`scripts/readme-actions.py` (support) generates the marked current-action table in
`docs/DEVELOPING.md` from `scripts/lab/actions.py`, preserving registry order and excluding
historical actions. Run it after changing registry names, status or help; host CI runs
`python scripts/readme-actions.py --check` beside the journal-index freshness check.
The script name stays stable after relocation from the player-facing README.
`tests/test_readme_actions.py` covers rendering, idempotence, freshness checks and
leaving the player landing page untouched.

## Source folders

`tools/unity/runtime/` groups authored sources by owner: `session` (including
`PortSession.cs`), `catalog`, `commerce`, `input`, `presentation`, `progression`,
`shaders`, `stage` and `world`. `tools/unity/experiments/` holds historical probes,
linker descriptors and `LabExperiments.cs` (still selected for the current player).
The detailed paths and status remain in [architecture-file-map.md](architecture-file-map.md).

`recipe/runtime-sources.json` contains paths relative to `tools/unity`. Every builder
stages sources by basename, preserving generated project paths and Unity-owned metadata.
The reader rejects duplicate basenames, including collisions with generated sources;
the strict staged C# membership and byte comparison checks remain in `build.py`.
`recipe/project-layout.json` owns those 92 authored script GUIDs and the 36 direct
package dependency pins, audited in `recipe/README.md`. `build.py` checks staged
`.meta` GUIDs and `Packages/manifest.json` dependencies after source validation on
the current whole-catalog build path, before cache lookup or editor invocation.
The check is read-only: it neither generates metadata nor installs packages;
existing staging retains ownership of those writes until the direct composer lands.
`recipe/runtime-config.json` records the 183 present public `SessionConfig` fields
(options and content identifiers; audit in `recipe/README.md`). `build.py` validates
them after layout validation, before cache lookup or editor invocation, without
writing the config. Extra staged keys remain allowed. The absent
`detailedVisualDiagnostics` field stays untracked until explicitly configured.
`recipe/content.json` records the 14 present public bundle-selection fields
(4,304 asset-path strings, including 4,184 `prefabAssets` entries; audit and complete
reader/writer inventory in `recipe/README.md`). `build.py` validates the work
`scene-probe-build.json` after runtime config with the same strict equality helper,
before cache lookup or editor invocation. Extra work keys remain allowed; the
validator never writes either input. At the start of both full and code-only
`whole_catalog.build_integration`, `build.generate_runtime_config(project)` and
`build.generate_content_recipe()` replace these files from the public recipes
before source validation or staging. They use sorted, two-space JSON plus a final
newline, preserve values/types/list order, and retain no extra keys. No later
current build step writes either file. Composition migration still writes its
intermediate configs before this entry point; those writes are superseded here.
The first build after this change must be a full `whole-catalog-build`: the runtime
resource is a payload input. See the [generation audit](../recipe/README.md#config-generation).

## File status

Every file in `tools/unity`, `tools/catalog` and `scripts/lab`, and every `prototype`
action, is classified with its staging site and a runtime call site in
[architecture-file-map.md](architecture-file-map.md). Totals:

| Area | Current | Support | Historical |
| --- | ---: | ---: | ---: |
| `tools/unity` + `tools/catalog` (135 files) | 94 | 26 | 15 |
| `scripts/lab` (43 modules) | 9 | 24 | 10 |
| Named `prototype` actions (177; default fallback excluded) | 12 | — | 165 |

Historical `tools/unity` files (not staged by any current builder; none exists in the
generated project): `AudioAssetProbe`, `CharacterMotorOrderProbe`,
`CollectionsRuntimeProbe`, `CommandoPosePreview`, `KinematicBatchProbe`,
`LoadingSceneProbe`, `MetadataDispatchProbe`, `ReferenceIdentityProbe`, `RoR2SliceProbe`,
`StartupSegmentProbe`, the three `RewiredTrial*` files, and `ControllerAddressLink.xml`
and `TeleporterTimelineLink.xml`. `ReconstructionProbe.cs` is support: `./dev
export-project` wires it into the exported project. Current whole-catalog C# source
membership is the audited `recipe/runtime-sources.json` selection, read by `build.py`
and staged by `whole_catalog.build_integration`. Existing Unity-owned `.meta` files
are retained; source and metadata paths remain player-only payload exceptions.
`build.py` declares the three generated visual maps separately and rejects missing
authored sources or unlisted staged C# files. `test_runtime_sources.py` checks the
selection and its independence from generated-project history.

The current `scripts/lab` modules are `build`, `composition_migration`, `device`,
`graphics`, `health`, `inventory`, `main`, `recovery` and `whole_catalog` (helpers such as
`common` count as support); the
current `prototype` actions are the ten in
[whole-catalog-integration.md](whole-catalog-integration.md#reusable-fixes-and-commands)
plus `project-manifest-capture`, `project-manifest-compare`,
`asset-transforms-check` (owned by `asset_transforms`) and
`authored-additions-check` (owned by `authored_additions`), plus
`inherited-state-check` and `inherited-store-capture` (owned by `inherited_state`).

### Mercenary impact-effect adapter

`BodyCatalogSession.MercEvisImpactEffectLease` in `BodyCatalogBoundary.cs`
owns the Evis-only compatibility adapter. `EnemyRewardSession` requests it
only for the selected Mercenary teleporter-loop session. Setup clones the
shared swing visual under an inactive owner, preserves its native one-second
timer, adds a nonpooled EffectComponent and a lifetime marker, appends one
native EffectCatalog entry, then redirects the registered Evis projectile's
impact field. The shared GroundLight2 visual and baked catalog indices remain
unchanged. No projectile catalog entry is added.

`RestoreComposedEffects` checks exact catalog/field ownership and refuses live
projectile or marked effect references before restoring the Evis field,
registered indices, sound metadata, prior catalog and availability. It removes
only the adapter's cache entry and destroys its owner after restoration. A
refusal retains the lease for diagnosis. Setup failures use the same ownership
checks for rollback, including the ordinary non-Merc path. Deferred teleporter
support uses `RegisterComposedEffects` after initial setup; it preflights the
whole request and records each field mutation before writes. Teardown restores
the accumulated stack in reverse so definitions sharing a prefab component
recover the original index. Initial setup uses its separately scoped registration
path and the same reverse restoration rule.

`MercEvisImpactEffectExactEditorFixture.cs` is support code staged by
`whole_catalog.stage_build_sources` into `Assets/Editor`. Its public `Run()`
requires the pinned, compiled, idle editor with no network session or populated
EffectCatalog. It initializes Addressables through the public API with generated
empty test settings/catalog, then exercises the actual owner and native
SetEntries in three restored generations. The fixture tests later-registration
failure, default-path rollback, live-projectile refusal, source immutability,
and provider/cache restoration. Generated initialization files remain under
`work/tests/merc-evis-impact-effect/addressables-init/` for the initialized
locator's lifetime. This fixture does not prove device effect presentation.

## Known structural debt

First verified against `af2e101`; status updated after J597. Each step was its own commit with
host tests, a zero-error exact-editor build and a device check.

Still open:

1. **The from-scratch rebuild is not yet equivalent or self-contained**
   ([rebuild-plan.md](rebuild-plan.md)). `./dev prototype --action rebuild-step` builds a
   separate destination in twelve host steps, each byte-identical to the working project
   (J567–J575); from a clean checkout of a gated build commit they reproduce 87,184 files
   (J750), and R9 there builds an APK that passed both device checks first time, with one
   differing gate file (BlueNoise drift) (J751); with that importer restored in the working
   project, R9 reports `equal: true` (J752). R9 builds it into an APK that passed both device checks (J582), but R9
   still reports it unequal. With the J584 Timeline pin and the J585 layered reimport, the J586
   rerun logs no new reimport error and passes both checks first time; its APK differs from the
   baseline only in `Hidden/Compositing` (open), the path-dependent Burst library and build
   metadata. The last differing gate file is `BlueNoise_R8_1.png.meta`, working-project drift (J592).
2. **The rebuild still has local inputs, and the working project is still migrated.** Since
   J597 the rebuild's R2 takes its selection from public recipes and reads no migration
   evidence (B1, B3–B6, B8), previous project or live pointer; R5 pins nothing and R7 pins one
   contract result. Since J725 R2–R4's catalog analysis is regenerated on the host in the
   destination. Left: 47 local analysis inputs read by recorded hash (R7's runtime contracts,
   still an editor export; 46 shader recovery inputs), 14 inherited-store files (12 from the editor-side `RecoveredHudBuilder`,
   FastDirector, the TMP mobile shader), and the local provenance map, which also selects
   membership (export copies, step cohorts), not only compares. The working project's own
   stage still runs the migration (`migration_inputs`); switching it is commit 9 of the
   [migration removal plan](migration-removal-plan.md).
3. **The session is still selected by id.** `Start` waits 8 s and picks the session from a
   string id; the playable spine runs `GameSession()` (J513) and the 116 historical cases live
   in `LabExperiments.cs`. Having `Start` call `GameSession` directly is the remaining step.
4. **Shared coordinator state.** 40 owners hold their subsystems' private state (J519–J540),
   but fields that several subsystems read (player, teleporter, results save system, HUD and
   menu roots, settings visibility and others) still live on `PortSession`. 23 boundary files
   have no private state worth an owner, and the three Moon files were deferred because
   neither standard check reaches them.
5. **Hard-coded run folders.** `scene_runtime.py:59`, `:515` and `:883`, and
   `input_migration.py:90` read fixed timestamped evidence folders (all in historical actions).
6. **Experiment drivers outside Git.** Broader gameplay runs still use about 89 untracked
   runner scripts in `work/experiments/whole-catalog/gameplay/`; the standard checks are
   tracked as `./dev check-baseline` and `--stage-exit` ([BASELINE.md](BASELINE.md)).
7. **Names.** Four staged diagnostic probes and six game-path shaders keep "Probe"/"Preview"
   names; renaming shaders changes names that code and materials look up, for no functional
   gain.

Resolved during the cleanup: dormant text patches on authored C# (J505/J506); build membership
by history (`recipe/runtime-sources.json`, J509, paths after the folder split J543); the 9
copies of the exception wrapper (`RunGuarded`, J511); config and report sharing one type
(`SessionConfig` J517, `SessionReport` J541); the coordinator name (`PortSession`, J542);
command sprawl (`scripts/lab/actions.py`, J512, README table generated J545); Python and C#
formatting (J518, J544); the flat `tools/unity` folder (J543).
