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

`ContentFixtureLinkerCapture.cs` is a fixture-only editor observer for the next
stripping experiment. It snapshots the active public UnityLinker callback's
complete input directory into the explicitly owned build attempt, preserving
source/hash identity and rejecting links or concurrent drift. It returns only
an inert linker XML. The builder records its final BuildReport identity;
`phone_content.validate_linker_capture` requires matching build/commit/version,
required assembly/scene/editor-data inputs and every copied hash before accepting
a fixture build. This does not establish Android stripping or input consumption
by itself; the fresh graph and emitted outputs still need independent binding.
It is never staged into the game project.

`phone_linker.py` owns experimental stripping **support** for that captured
authored fixture. The current `phone-linker-fixture` action verifies the explicit
fixture/callback/final-build identities, maps only known linker flags/input roots,
and stages unchanged captured files plus supplied SDK descriptors/tool DLLs.
Its standalone Android driver verifies input hashes, uses the separate .NET
build-tool host, retains output/log/failure receipts and disables unnecessary
tool analytics. Desktop-generated scene/editor root production remains an input;
matching output hashes and fresh execution evidence are separate acceptance
checks. No whole-catalog build or game runtime calls it.

`tools/phone-build/host/` is separate experimental **support**. Its Android
driver owns compilation of authored C/Java/XML, DEX/APK production and disposable
signing from explicitly supplied local tools. `HostProbeActivity` owns one
background check of PackageManager-installed native execution and a writable
copy's refusal, then writes `files/host-report.json`. It uses no Unity/game
code, permissions or network. Setup and device cleanup are described in its
[README](../tools/phone-build/host/README.md); no game build calls it.
`phone_host_check.py` owns its explicit-device, hash-bound installation,
two launches, report/backing collection and ownership-checked teardown through
the current experimental `phone-host-check` action.

`phone_native.py` owns experimental **support** for replaying the authored
content fixture's native graph. `phone-native-fixture` verifies an explicit
project/APK request, copies supplied runtime/NDK and generated source inputs
unchanged, regenerates only include wrappers from their ordered dependency
descriptions, and records structured compile/link arguments plus input hashes.
Its standalone Android driver checks those hashes, builds into a new output
directory and retains each command/log and the first failure. Clang/LLD host
changes are explicit; desktop stripping/code generation and private Unity
inputs remain dependencies. No game build uses this path.
Relinks may reuse only a hash-bound complete object set with equal source/target
inputs, compile plan and actual compiler arguments. Link repair selects the
original NDK static C++/ABI/GCC libraries explicitly and preserves old attempts.

`phone_native_apk.py` is separate packaging **support** for the authored content
fixture only. It requires base APK, ARM64 shared-library and unchanged metadata
hashes, substitutes that one native entry plus the version integer, retains
other entry bytes/notices, and removes obsolete signatures. Its current
`phone-native-apk-fixture` host action and standalone Android CLI produce new
unsigned outputs; alignment, signing and device checks follow separately.
The device checker also hashes the actually mapped IL2CPP library inside the
observed installed code directory, independently of the APK's expected entry.

`phone_converter.py` owns separate experimental **support** for replaying the
authored player's complete recorded IL2CPP code-generation command. The current
`phone-converter-fixture` action shares the native fixture's project/APK/source
guard, requires the exact assembly closure and known options, copies supplied
stripped assemblies/tool DLLs/icalls unchanged, and records their hashes.
The standalone Android driver uses a separate .NET build-tool host, verifies
inputs before execution, relocates only output paths, disables unnecessary
tool analytics and retains fresh output/log/failure directories. An optional
`linker` selector in its request binds the actual Android stripping stage/result,
all emitted hashes and exact DLL/symbol closure against the same fixture. Only
the recorded editor-report module order may differ; complete entries/other fields
are checked in memory and the actual report bytes are copied unchanged.
An explicit
optional `converter` selector in a native-fixture request binds that converter's
stage/result/output hashes, original stripped input closure and byte-identical
data/metadata before choosing its emitted C++ for native compilation. The game
runtime is still IL2CPP; desktop scene/editor-root production and permitted
proprietary tool delivery remain gates. No whole-catalog game build calls this owner.

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
refuse.

The additional `--capture-il2cpp-invocation` opt-in requires
`--capture-player-linker-inputs` and is independently false by default. The
staged `Il2CppInvocationCapture.cs` subscribes only for that request, captures
Unity's pre-launch rendered IL2CPP command line and the one simple
`--directory=` input path, then snapshots the directory under request-owned
ignored storage. It records the project-relative input path and BuildReport
GUID; the UnityLinker receipt and final successful build result carry the same
GUID. `player_il2cpp_receipt.py` verifies the request/source/input/target/GUID
join and hashes before adding generic `il2cpp_snapshot_to_apk_build_binding`
evidence to the build receipt. This does not claim that the process consumed
those exact bytes, an exact argv vector, or equivalence with the composed-audio
transformed-input manifest; `stage_to_apk_binding` remains false. The native
`UnityLogWriter` to `Application.logMessageReceived` delivery is still
unverified until an owning editor build observes it. No runtime dispatch or
audio acceptance follows from this receipt.

`test_player_linker_receipt.py` covers the existing input capture and opt-in
forwarding. `test_player_il2cpp_receipt.py` covers the joined receipt contract;
`test_describe_runtime.py` and `test_il2cpp_invocation_capture_runtime.py`
execute the authored C# helpers against minimal host stubs and skip without the
pinned Mono compiler. Exact-editor compilation and later device acceptance
remain separate. This narrow build-receipt addition serves original audio;
alpha retains packaging ownership.

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
Shader replay initializes R1's generation marker, validates the public retained-input
recipe, runs existing generators into destination scratch, then places only
map-matching outputs through `StageIO`. Its per-file blocked/result receipt owns
completion state; composition requires it and rechecks generated source hashes.
No shared pointers or Wine bottles are written. Native recovery remains a pinned
local-input blocker. `shader_source.output_directory` shares unchanged real action
paths and isolated pointer-free setup across all three generators.
`inherited_rebuild.py` owns per-file R2 host candidates: minimal importers from
ledger identities, one hash-gated accepted-export texture importer and three
includes through the existing pinned Unity package reader. Destination-only setup
passes candidates to `inherited_state.prepare`; it retains original hash/GUID
checks and store fallback for unregenerated files. Per-file origins and reasons
live in `.rebuild/inherited-rebuild-result.json`; transient buffers disappear
on flush/failure. The real stage's store placement paths remain unchanged.

Project inputs own public smoke settings, Burst default JSON, J369 Android graphics
tiers, archived independently authored editor
versions, explicit Nova importer metadata, shared Nova-axis generation and the
original-identity OBJ export. All outputs are buffered and gated before flush;
the completion receipt lives under destination `.rebuild/`. No new runtime state
or teardown is introduced. Setup is the accepted installation and public recipes;
failed native scratch is retained and later operator reruns use a new attempt
folder. No local input is retired. Exact membership, explicit R9 PlayerSettings/linker
obligations, provenance corrections and pin counts are maintained once in
[rebuild-plan.md](rebuild-plan.md#shader-prerequisite-and-remaining-project-inputs).
Host contracts: `test_shader_rebuild.py`, `test_project_input_rebuild.py`.

`./dev prototype --action rebuild-step --step assemblies` reconstructs the assembly
cohort, then compares every selected map path with the current project's actual
bytes. The ordered `STEPS` table declares each step's producer categories, path
selection and builder; categories alone are too broad to select a subsystem.
The local `receipts/provenance-map.json` supplies comparison membership and output
hashes. `--work-dir PATH` selects read-only local inputs (including the legitimate
installation configuration); the destination remains in **this clone's**
`work/rebuild/<input_id>/lab-project`. `--dest DIR` may select another isolated
project strictly beneath that rebuild root. Live-project destinations, redirects,
nested symlinks and hard-linked output files are refused. No Unity or device
operation is involved.

After composition, `--step catalog-closure` uses `whole_catalog.prepare_integration`
through `StageIO` and `catalog_rebuild.CatalogIO`; `--step dependencies` uses
`composition_migration.stage_missing_sources`, the support alias repair and the
optional-content sanitizer through that same boundary. R3 selects 259 map files;
R4 selects 1,238. Membership uses the map's exact producer function evidence,
since the broad `repo-builder` category also includes later steps. Each cohort is
hash/size-gated before buffered project writes are flushed, then compared with
the current project. R3 requires R2's destination config; R4 requires R3's completion marker and R2's
destination build config. The real actions retain their original write paths.

`catalog_analysis.ensure` (J725) regenerates the catalog analysis once per destination
under `.rebuild/catalog-inputs/`, running the live pipeline's own `audit_into`,
`native_inventory_into` and `reconcile_into` (the source catalog through `catalog_reader.py`
and `AssemblyProbe --catalog-names`, J714). Only `recipe/catalog-typed-corrections.json`, three
measured identities, is not regenerated. No previous analysis or live pointer is read. Destination GUID ownership, catalog manifests/import receipts,
dependency receipts and optional-content receipts are regenerated. No current
project owner map or historical output body is used as source. R3 buffers the
closure import and UI remaps; R4 buffers dependency import, support repair and
sanitization. Auxiliary R4 writes remain under `.rebuild/composition/`, and reads
prefer R2's redirected config. Before R7 places its importer, sanitization obtains
SilentProjectileBoundary's identity directly from `project-layout.json`. These buffers have no state after flush or failure.
Synthetic contracts: `tests/test_catalog_rebuild.py`.

R5/R6 replay (`scripts/lab/scene_rebuild.py`, current): `--step stage-variants`
uses `stage_variants.stage`, the existing Nova geometry projection and
`scene_contract`; `--step source-scenes` uses `source_scene_candidate.prepare`
for all 23 scenes. R5 owns 18 map files (16 later reduced scenes and two final
contracts); R6 owns 46 bodies/importers. Completion markers enforce order after
R4, and both steps validate selected hashes/sizes before flushing `StageIO`,
then compare actual bytes. The real actions keep their original paths. R6
omits the separate audio action because R1 owns its DLL outputs.
R5 reads no retained analysis input (J597): `script_identity.py` derives the MapZone
script lookup from the installation's shipped MonoScripts with Unity's MD4 file-ID
rule, and `scene_rebuild.node_graphs` finds the stage graphs as the export's
`RoR2.Navigation.NodeGraph` assets, each of which must still be its export copy
before R9. Destination scene bytes
determine pending variants even when R2 already supplies their config rows.
R5 reuses R2/R3's imported closure, validates graph hashes/GUIDs, reads R3's
regenerated manifest, and regenerates navigation/config/context receipts.
Temporary projections remain buffered and are discarded after placement;
auxiliary outputs stay under `.rebuild/`. R6 derives source-scene GUIDs/importers
from input identity and source metadata. Buffers have no state after success or
failure. R4 still defers later scene paths until the final binding gate, which
remains disabled through R8. Host contracts: `tests/test_scene_rebuild.py`.

`recipe/original-assemblies.json` pins 49 Managed source identities and importer
parameters: 45 unchanged originals, installation-sourced SimpleJSON and three
originals transformed using J563. `recipe/templates/original-assembly.meta`
supplies the common importer schema; GUIDs, creation times and execution orders
reproduce the retained metadata without copying it from the project or export.
J563's shared `assembly_transforms.generate` builds an isolated tool copy and
replays the pinned transforms, with tool intermediates, CLI home, package cache
and temporary files beneath the destination. Scratch is removed on success or
failure. The full 98-file cohort is validated before project files are placed;
reruns overwrite only that cohort. R2 initializes a separate generation marker from these recipes after validating
R1 assembly placement.

Composition rebuild (`scripts/lab/composition_io.py`, current, R2):
`rebuild-step --step composition` runs `composition_migration.stage` through
`StageIO` against the isolated destination. Its selection comes from
`composition_rebuild.recipe_inputs` (J597): asset transforms, the addition ledger,
the public runtime/content recipes and `recipe/composition.json`, with source GUIDs
and catalog closure from the catalog analysis regenerated in the destination (J725). The rebuild reads no
migration evidence (B1, B3–B6, B8), previous project, live content selection or old
run attempt; the real action still takes them through `migration_inputs`. The same owner keeps real-stage writes
at their original paths when no destination is supplied. Export membership comes
from canonical catalog closure/resolved-mesh relocation plus the identifier-only residual
`recipe/composition-export-copies.json`; provenance gates each selected source's
size/hash before placement. The package manifest is rendered from the public
project-layout dependencies. Assembly identity comes from R1's public recipes,
never the working project's marker. Host/input preflight gates remain active;
device storage and preflight receipts belong to subsequent install/build work.

Stage transforms, additions, selected shader outputs, scene contracts, script
orders, runtime config and receipts use the same staging functions. Pending stage
bytes are visible to later stage reads and checked against provenance before
publication. Intermediate project products stay in the destination for subsequent
builders; auxiliary config/receipt outputs go under `.rebuild/composition/`, with
logical paths relative to the selected input work root. The comparison excludes
only that coordinator namespace and `.port-input.json` outside its three mapped
areas. Pending state is discarded on failure; copied exports and the generation
marker remain available for inspection. There is no Unity/device operation.

The dependency builder `stage_missing_sources` runs after complete catalog import
in the rebuild order; it is unchanged and still called inline by the real stage
action. Only the rebuild path defers J565's removed/unowned binding guard, retaining
the diagnostic and original unresolved identifiers for later builders. The final
`validate-bindings` step is registered last and refuses execution until R3–R8 are
implemented. No successful R2 comparison establishes that final gate. Host
contracts: `tests/test_composition_rebuild.py`, including the real-stage write path.

`--compare-only` requires an existing destination and performs no writes or tool
execution. Reports list identical, different, missing (which side), and extra
paths, with counts and a nonzero exit on differences. Files owned by other map
steps may coexist; files absent from the map are extra. Host contracts:
`tests/test_rebuild.py`; this is reconstruction tooling, not device acceptance.

Inherited-state store and ledger (`scripts/lab/inherited_state.py`, current):
`./dev prototype --action inherited-store-capture` validates and copies exactly the
189 inherited asset/meta pairs from the selected previous project into
`work/inherited-store/<input_id>/`, publishing only a complete hash/GUID-verified
store. An existing store must match exactly; capture never repairs drift.
`composition_migration.plan_additions` verifies that store and combines its pairs
with the 40 recipe-generated additions before any project writes, preserving
inherited YAML normalization. No addition is copied from the previous project by
current stage. `inherited-state-check` verifies the store and regenerates the
shader/export/package cohorts against ledger hashes in scratch, without historical
copies; `--work-dir PATH` selects read-only inputs. Store lifecycle and remaining
coordinator blockers are in [LOCAL_STATE.md](LOCAL_STATE.md#named-inherited-store-current).
Host contracts: `tests/test_inherited_state.py`. The full migration coordinator
still reads historical config/identity/provenance contracts listed there; addition
planner independence does not establish full direct composition.

Non-shader addition owners (`scripts/lab/export_additions.py` and
`scripts/lab/unity_package_additions.py`, current): composition prepares the full
asset/importer pairs before any staging writes, checking complete membership,
target identity and both ledger hashes. WarpRamp uses the accepted export's
hash-gated identity operation; its importer retains the export bytes except the
explicit inherited GUID and creation-time field. The used TMP properties include
comes from the hash-pinned TextMesh Pro 3.0.6 package bundled with the exact editor,
read in memory with no package installation or assembly-provider change. Its
importer uses `authored_additions.shader_importer` with the inherited GUID.
These owners have no runtime state or teardown; they return bytes and retain no
temporary output. Missing or drifting inputs fail before staging. Required local
inputs are the existing accepted export and documented Unity toolchain; neither
owner reads a timestamped run folder. Other non-shader additions remain inherited;
their individual blockers and third-party source requirements are audited in
`recipe/README.md`. Host contracts: `tests/test_nonshader_additions.py`.

Generator-owned shader additions (`scripts/lab/shader_additions.py`, current):
composition prepares all nine pairs before writing, using the existing deferred
and material generators with selected resources and temporary output directories.
The shared authored importer schema supplies each ledger GUID. Generator inputs,
selected pipeline receipts and final body/importer hashes are gated; staging does
not read the previous project for these pairs or overwrite them with selected
source copies. Temporary output is deleted on success or failure. DeferredLighting
reuses hash-verified, validated independent HLSL intermediates from the selected
pipeline receipt; it never invokes Wine in this isolated mode. The native DXBC,
HLSL and bound layout must agree with that receipt. The selected deferred pipeline's
`program-*-independent/program-*.hlsl` files remain required local inputs produced
by `shader_programs.NativePrograms.bound`; the composition selection locates them,
with no timestamped directory encoded in source. Other selected programs run
the pinned native decompiler and roundtrip check in scratch. No rendering or
input-bootstrap reproducibility follows from this host byte comparison.
Host contracts: `tests/test_shader_additions.py`,
`tests/test_shader_independent_reuse.py`.

Project equivalence harness (`scripts/lab/project_manifest.py`, current):
`./dev prototype --action project-manifest-capture` writes an ignored receipt of every file
under the generated project's `Assets/`, `Packages/` and `ProjectSettings/` (path, SHA-256,
size) plus the build cache's external inputs; `--action project-manifest-compare --compare A B`
reports added, removed and changed paths and exits non-zero on any difference. It never
writes to the project. Each step of the [migration removal plan](migration-removal-plan.md)
must compare equal against the previous receipt.

Pointer chain for the latest evidence: `experiments/whole-catalog/latest.json` →
`integration-latest.json` → build, device and composed receipts.
`checkpoints/LAST_OBSERVED_WHOLE_CATALOG.json` pins the accepted scope.

Asset transformations (`scripts/lab/asset_transforms.py`, current):
`recipe/asset-transforms.json` selects 222 accepted-export assets with source hashes:
28 SurfaceDefs, six identity copies, ten activation-only prefabs and all 178
structural prefabs/scenes. The generator returns bytes and export-derived metadata
without writes; `integrated_objective` shares the SurfaceDef field operation logic.

Identity copies preserve source bytes. General `set_field` operations select a
GameObject hierarchy path, native class or external script identity, zero-based
component occurrence and mapping field path. Duplicate hierarchy paths require an
explicit zero-based `hierarchy_occurrence` in source record order; otherwise they
fail. Consecutive non-identity field edits share a per-generation selector index;
renames, hierarchy/identity changes and structural operations flush it.
Four UI prefabs first apply the existing input-gated, hash-pinned uGUI mapping.

`remove_components` takes source fileIDs and an exact match count, preserving
surviving IDs and record order. Each deleted component must have one correct owner
membership. Explicit `retain_null_slots` identifiers replace selected memberships
with null slots instead of deleting them. `null_reference` and
`null_array_element` require an owner selector, a mapping/sequence field path,
exactly one match and the expected nonzero local reference. Array indices are
zero-based and retain entries; external references fail the nulling precondition.
`remove_scene_settings` separately deletes explicit ownerless class 29/104/157/196
records, with fileID/class/count checks. All deletion operations reject surviving
local references; hierarchy deletion remains unsupported.

`add_component` constructs the authored empty MeshRenderer and
SilentProjectileBoundary schemas from typed fields. It selects a surviving owner
by source fileID and allocates the sanitizer's SHA-256-derived IDs (renderer base
7,000,000,000,000,000; silent base 8,000,000,000,000,000), incrementing collisions.
The recipe's relative `id_seed_path` is an allocation namespace, never a path read
from disk. Explicit first/last membership placement preserves the migration's
ordering; records append in recipe order. Bodies are generated, never copied YAML.

`composition_migration.stage` prepares every recipe pair before project writes,
checks the existing provenance/output/conflict gates and metadata equality, then
writes those pairs instead of copying preview assets. `prepare_asset_transforms`
validates these rows using export bytes and the plan's hashes without opening
preview/previous asset files. The surrounding migration still reads historical
plans, mappings, configs and 200 additions; 15 use tracked sources and 14 use
export-based deck constructors.
There is no persistent generator state or teardown. The current read-only action
`./dev prototype --action asset-transforms-check` compares every recipe asset/meta
pair with the migration preview oracle (or project when no preview exists), checks
project metadata, lists differences and exits nonzero on drift. Exclusive
structural cohorts report equality separately; the removal cohort also counts
deleted components. Later project transformations are reported separately without
rewriting either side. Host contracts are in `tests/test_asset_transforms.py` and
`tests/test_asset_structural_operations.py`; device acceptance is a separate gate.

The same owner constructs the 14 director-deck additions selected by
`recipe/deck-transforms.json`. `generate_deck` selects category/card spans from
seven hash-pinned export decks, preserves retained fields and order, prefixes the
name, and omits default elite fields from the older serialization schema. Explicit
field/weight omissions preserve the inherited sparse Sky Meadow champion card;
they do not repair its gameplay. `generate_deck_asset` supplies a minimal native
importer with the stable lab GUID. `prepare_decks` requires complete composition
membership and matching identities before any writes; staging retains target
relocation and uses the existing addition writer. No persistent state or teardown
is needed. The current `asset-transforms-check` also reports `deck_cohort` against
the normalized previous-project addition oracle, compares metadata, fails on pair
drift and lists current-project changes separately. Host contracts live in
`tests/test_deck_transforms.py`; the recipe audit explains selections and prior art.

Authored additions (`scripts/lab/authored_additions.py`, current) owns
`recipe/authored-additions.json`: 14 tracked shader sources and one include, their
source hashes and stable lab GUIDs. Its pure generator returns source/importer
bytes; `composition_migration.stage` prepares the entire cohort before project
writes and retains ownership of writing/target relocation. There is no persistent
generator state or teardown. Missing membership, GUID mismatch and source drift
fail closed. Other additions still inherit the previous project. The current
`./dev prototype --action authored-additions-check` is a read-only comparison of
asset and metadata bytes against the migration copy rule. It does not compare
later shader replacements or run Unity. Host contracts are in
`tests/test_authored_additions.py`; provenance is in `recipe/README.md`.

## Android runtime

The shipped game runs inside the lab harness `PortSession`
(`tools/unity/runtime/session/PortSession.cs`, 70 `partial` files). The runtime configuration is the
untracked `Resources/MovementBatchProbe.json` (unchanged resource/file name) in the
generated project, parsed as the
184-field `SessionConfig`. `SessionReport` is the report written back as `movement-batch-*.json`
(and the `movement-batch-selection.json` override); config values the report shows are
copied into it explicitly (J517).

Start-up, in order:

1. `Init` (`PortSession.cs:402`, `RuntimeInitializeOnLoad` after scene load): if the
   `MovementBatchProbe` resource exists, create the harness object.
2. `Start` (`:407`): exits if `whole-catalog-selection.json` exists in persistent data (the
   separate catalog bootstrap owns that run), then **waits 8 s**.
3. Read the config. Without a `movement-batch-selection.json` override and with
   `launchPlayableSlice` set, wait for an attempt-bound `nova-input-mapping.json` in
   persistent data, then select case `body-state-spawn-state-auto-nova-spine`. Payload sync
   (`device.py`) does not push that mapping; only the historical `movement-batch-run`
   (`scene_runtime.py:629–631`) and some untracked runners do. The menu reads it too
   (`OfflineApplicationBoundary.cs:45`).
4. Begin presentation (`AndroidMaterialPresentation.Begin`), collect garbage left by a
   previous session, `Save()` phase `started`.
5. Catalog fixture: `RegisterBodyCatalog` (composed whole catalog), then
   `PrepareTeleportMaterial` and `PrepareBarrierEffect` when configured.
6. `AwaitOfflineRunStart` (`OfflineApplicationBoundary.cs:34`): offline settings, the
   recovered survivor/difficulty/loadout menu, and the wait for Start.
7. `RunSelectedProbe`: when `IsPlayableSpine()` (`PrimaryFireBoundary.cs:12`, a prefix
   match on `body-state-spawn-state-auto-nova-spine`) it runs `GameSession()`, which runs
   `BodyLifecycle()`; the same flag turns on the game path inside the boundaries it calls.
   Any other id goes to `LabExperiment()` (`LabExperiments.cs`), the 116-label switch of
   historical experiments. Both run inside the same `try`/`finally` (J513).

Teardown, in order, after `RunSelectedProbe` returns or throws:

1. `RunSelectedProbe`'s `finally`: `CleanupLanding`, destroy the obstacle, body host and
   staging roots, disconnect the recovered client and shut down the owned network server.
2. In `Start`: `VerifyEnemyCleanup` → `VerifyIntegratedWorldCleanup` (integrated world) →
   `VerifyAutomaticModelDestruction` → `CleanupEnemyRewards` → `CleanupPlayerDeathEffect`
   → `CleanupBodyCatalog` → `CleanupTeleportMaterial` → `CleanupBarrierEffect` →
   `CleanupSpawnConfig` → `CleanupStageGeometry` → `AndroidMaterialPresentation.Finish` →
   `ReclaimCompletedSessionResources` (only after a clean, successful integrated session) →
   `Save()` phase `complete` → `RestartWorldAfterCleanup`.

The enemy, world, model, teleport-material and barrier steps run through `RunGuarded`
(`PortSession.cs`), which records the failure and moves on. The reward,
death-effect, geometry and reclaim steps, and the synchronous cleanup calls outside the
`CleanupBodyCatalog` `try`, have no wrapper: an exception there stops the remaining
release steps. `Start` itself has no
enclosing `finally`, and `PortSession` has no `OnDestroy` or `OnApplicationQuit`:
an error during catalog preparation or the menu, or the app being killed, skips the
post-run release sequence. Per-boundary teardown inside the session (the 17-step call
order and each `finally`) is in
[architecture-file-map.md](architecture-file-map.md#d-playable-spine-runtime-sequence-and-ownership).

## Ownership

Each staged runtime file starts with a two-line header naming its subsystem, whether it is
on the game path, and its setup and teardown methods (J516).

Most `*Boundary.cs` files are `partial class PortSession`: their state is fields on
the coordinator, not a separate owner. Only the types marked **own type** keep their own
state. Host tests are in `tests/`; editor fixtures (`tools/catalog/*Host.cs`) run in the
exact editor. There is no per-subsystem device check yet: catalog registration is checked
by `whole-catalog-run`, and everything else by a gameplay runner's `movement-batch-*.json`
report, read against the journal entry that defines what it must show.

| Subsystem | Main files (`tools/unity/`) | State | Setup → teardown | Host test / editor fixture |
| --- | --- | --- | --- | --- |
| Session and entry | `PortSession`, `OfflineApplicationBoundary`, `SessionResourceBoundary`, `ActiveClientBoundary`, `OfflineRunSeedBoundary`, `SurvivorSelectionBoundary` | nested `OfflineRunSeedSession` (`IDisposable`) **own type** holds the cached seed, session id and source; nested `ActiveClientSession` (`IDisposable`) **own type** holds the owned body/master authority identities and client-scene ownership flag; `activeBodyClient`, `activeBodyOwner`, remaining state and `SessionReport r` (including `r.activeClient` and `r.rewards.seedSource`) stay on the coordinator; nested `OfflineApplicationSession` (`IDisposable`) **own types** hold their files' private state | `Start` → `AwaitOfflineRunStart` → `RunSelectedProbe`; `ConnectActiveBodyClient` → `CleanupActiveBodyClient` (calls `Dispose`: remove master then body authority, disconnect then shut down client) → coordinator server shutdown → `FinishActiveClientSceneCleanup`; active-client owner created on first use and retained after cleanup; `CollectPriorSessionGarbage` → `ReclaimCompletedSessionResources`; `SelectOwnedRunSeed` calls session `SelectOwnedRunSeed` (owner created on first use and retained; session id controls refresh; `Dispose` is a no-op with no teardown call) | `AndroidLifecycleHost.cs` |
| Catalog and resources | `BodyCatalogBoundary`, `WholeCatalogComposed`, `WholeCatalogLoader`, `SpawnStateBoundary`, `OriginalBodyVisualBoundary`, `OriginalGlobalCommonAssetsBoundary`, `TeleportMaterialBoundary`, `BarrierEffectBoundary` | `WholeCatalogComposed` **own type** (static); nested `TeleportMaterialSession` and `BarrierEffectSession` (`IDisposable`) **own types** hold the teleport material (locator, async handle, material, overlays) and the barrier effect (constants, locator, async handle, prefab, effect-slot snapshots, owned material copies); nested `OriginalBodyVisualSession` and `OriginalGlobalCommonAssetsSession` (`IDisposable`) **own types** each hold their native slot snapshots and async handle lists; nested `SpawnStateSession` (`IDisposable`) **own type** holds native state/preload snapshots and spawn delay/sound restoration; `ownsStateCatalog` stays shared on the coordinator; teleport, `r.barrier*` and `r.world` report fields remain coordinator observations; the rest coordinator fields; nested `BodyCatalogSession` (`IDisposable`) **own types** hold their files' private state | `RegisterBodyCatalog` (calls `WholeCatalogComposed.Prepare`) → `CleanupBodyCatalog` (calls `Release`); `PrepareBarrierEffect` → `ObserveBarrierEffect` / `ProbeBarrierEffectLifecycle` → `CleanupBarrierEffect` (awaited coroutine, preserving Start's setup and release order; `Dispose` is a no-op because release requires the coroutine's frame yields); `PrepareOriginalBodyVisualReferences` → `PrepareOriginalGlobalCommonAssets` → `CleanupOriginalGlobalCommonAssets` → `CleanupOriginalBodyVisualReferences` (each cleanup calls its owner's `Dispose`: restore slots, clear snapshots, release handles, clear handles, mark the coordinator report); `PrepareSpawnStateCatalog` forwards to `SpawnStateSession` without changing catalog/config/preload construction order; later `CleanupSpawnConfig` calls `Dispose` (objective, enemy and spine config cleanup, then spawn delay/sound restoration, then `RestoreWholeStateOwnership`); owners created on first use and retained after cleanup | `test_whole_catalog.py`, `test_composed_support.py`, `test_body_visual_map.py`, `test_common_assets_map.py`, `test_stage_variant_graph_roots.py`; `WholeCatalogHost.cs` |
| Manual Moon boundary (existing config) | `NovaInputBoundary`, `NovaInputBridge`, `IntegratedStageBoundary` | `ManualMoonBoundary` is a pure four-completed-transition gate shared by the automatic input loop and transport entry guard; `NovaInputBridge` applies its diagnostic-only hold at every fixed tick, preserving touch-equipment requests and the physical-controller route when diagnostic input is off. It refuses any subsequent or explicit `moon2` transport while `pauseBeforeMoon` is enabled. The ordinary path and default `false` remain unchanged; the report records stage/count and a fixed-tick witness only after the sink actually runs. | Input-loop gate before transport/producers; transport guard before destination resolution or stage mutation | `SurvivorSkillInputHost.cs` (exact-editor bridge sink contract; no Moon/runtime acceptance) |
| Input and camera | `NovaInputBoundary`, `NovaInputBridge`, `NovaThirdPersonView`, `AndroidPresentationCamera`, `NovaDiagnosticDisplay` | nested `NovaInputSession` (`IDisposable`) **own type** holds trace cursors and the input iterators with local mapping, landing, camera and loop state; `NovaThirdPersonView` keeps its own camera/orbit state; `worldView` and `worldEquipmentBridge` stay shared on the coordinator; `NovaInputBridge`, `AndroidPresentationCamera`, `NovaDiagnosticDisplay` and opt-in `AndroidNativeSourceSkinLifecycle` (with pure `AndroidNativeSkinActivationPolicy`) remain **own types**; the native-skin owner is attached to the selected source model, retains only its native skin subscription and Android material clones through body lifetime, and writes scalar evidence into `NovaReport`; the per-run `SessionReport` selector defaults false; reports remain coordinator observations | `NovaRawBoundary` / `NovaInputBoundary` forward to the session; input teardown stays in its iterator `finally` in the same order; `NovaInputBridge.OnDisable` neutralises input; owner created on first use and retained after its no-op `Dispose` so final `Save` can flush traces | `test_nova_input_presence.py`, `test_nova_bridge_evidence.py`, `test_input_migration.py` |
| Settings | `AndroidOfflineSettings`, `OfflineSettingsBoundary` | `AndroidOfflineSettings` **own type**, kept across sessions; nested `OfflineSettingsSession` (`IDisposable`) **own type** holds the saved pause time scale; store reference, visibility and pause flags stay on the coordinator for menu/Nova input | `PrepareOfflineSettings` (calls `OfflineSettingsSession.Prepare`) → `CleanupOfflineSettingsPause` (calls `Dispose`, releases an owned pause only) | — |
| Progression and profile | `AndroidProgressionBoundary`, `AndroidOfflineProfile`, `AndroidProfileBoundary`, `OfflineLoadoutBoundary` | `AndroidProgressionBoundary` (`IDisposable`), `AndroidOfflineProfile` and nested `AndroidProfileSession` (`IDisposable`) **own types**; session owns loadout preview, catalog snapshots, redirect lease and event/discovery listeners; progression reference, results/save-system state, world references and pending menu loadout stay shared on the coordinator | `ApplyAndroidProfileLoadoutBeforeSpawn` (calls `AndroidProfileSession.ApplyLoadoutBeforeSpawn`) → `PrepareAndroidProfile` (calls session `Prepare`, then `AndroidProgressionBoundary.Prepare`) → `CleanupAndroidProfile` (calls session `Dispose`, including progression `Dispose`); results installs the save system before profile setup and restores it after profile cleanup | `AndroidProgressionHost.cs`, `AndroidDiscoveryHost.cs`, `AndroidProfileHost.cs` |
| Results | `IntegratedResultsBoundary` (with `AndroidProfileSaveSystem` in `AndroidProfileBoundary`) | nested `IntegratedResultsSession` (`IDisposable`) **own type** holds ending templates/catalog restoration, statistics callbacks and event context, ledger directory, save-system swap/restore and result listeners; serializer guards remain static; `resultsSaveSystem`, `resultsLedger`, `resultsStats` and `resultsRunReport` stay shared on the coordinator; `r.results` remains the coordinator observation | `PrepareResultsKeyItems` may precede `PrepareIntegratedResults` (calls session `Prepare`) → `CleanupIntegratedResults` (calls `Dispose`: profile cleanup precedes save-system restore); owner created on first use and retained after `Dispose` | — |
| HUD and UI | `RecoveredHudBoundary`, `RecoveredHudPresentation`, `RecoveredHudFeedback`, `RecoveredPickupPresentation`, `MoonPillarPresentation` | nested `RecoveredHudSession` (`IDisposable`) **own type** holds menu events, reference-rendering restoration and text reflection/restoration state; `recoveredHud`, `recoveredMenu`, `recoveredTextSettings` and `ownsRecoveredText` stay shared on the coordinator; feedback/queue state and pickup bindings stay in the existing presentation component **own types**; `r.hud` remains the coordinator observation | Session startup prepares owned text after prior-session collection, before presentation/catalog and independent of menu bypass; separate `PrepareRecoveredText`/`Menu`/`Hud` → `CleanupRecoveredHud` (calls `Dispose`, HUD then menu only), `CleanupRecoveredMenu`, `CleanupRecoveredText` (later catalog teardown); owner created on first use and retained after `Dispose` | — |
| World, director and combat | `IntegratedWorldBoundary`, `AutomaticSpawnBoundary`, `AutomaticDirectorBoundary`, `EnemySpineBoundary`, `StagePopulationBoundary`, `WholeInteractableBoundary`, `RunClockBoundary`, `PlayerDefeatBoundary`, the `World*` item boundaries (27 files) | nested `RunClockSession` (`IDisposable`) **own type** holds original clock callbacks, async lifecycle, scene-catalog restoration and timestamps; `clockSceneDefs` and `priorClockScene` stay shared on the coordinator; nested `PlayerDefeatSession` (`IDisposable`) **own type** holds the death-effect locator, async handle, prefab, observed effects and defeat body; nested `WorldHealingItemsSession` and `WorldLegendaryItemsSession` (`IDisposable`) **own types** hold healing source names, Warbanner reflection/callback and observed instances, and legendary controller names, observed instances and remote-transform/host-authority snapshots, respectively (static fields remain static); `r.runClock`, `r.playerDefeat`, `r.procContent` and `r.itemBehaviors` remain coordinator observations; shared world registries and remaining boundaries use coordinator fields; nested `WorldItemDisplaySession`, `WorldDotSession`, `WorldItemBehaviorSession` (`IDisposable`) **own types** hold their files' private item-display, DOT and item-behaviour state (J534); for the opt-in selected-skin path, `AndroidNativeSourceSkinLifecycle` owns the native `CharacterModel` inventory callback and `WorldItemDisplaySession` observes it only for presentation; nested `CombatSpineSession`, `StageBossContentSession` (`IDisposable`) **own types** hold their files' private state; nested `PrimaryFireSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldProcContentSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldEquipmentSession`, `AutomaticDirectorSession` (`IDisposable`) **own types** hold their files' private state; nested `EnemyRewardSession` (`IDisposable`) **own types** hold their files' private state; nested `WholeInteractableSession` (`IDisposable`) **own type** holds owned templates/cards, player-spawn points and the native spawn-point prefab snapshot/lease; `wholeSceneDirector`, `wholeStageContext`, shared world/commerce collections and reports remain on the coordinator; nested `WholePopulationSession` (`IDisposable`) **own types** hold their files' private state; nested `EnemySpineSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldFlightEquipmentSession` (`IDisposable`) **own types** hold their files' private state; nested `IntegratedWorldSession` (`IDisposable`) **own types** hold their files' private state | `PrepareIntegratedWorld` → `CleanupIntegratedWorld` → `VerifyIntegratedWorldCleanup`; `PrepareEnemy` → `CleanupEnemy` → `VerifyEnemyCleanup`; `PrepareRunSceneContext` → `StartOriginalRunClock` → `CleanupRunClock` (calls `Dispose`) → later `ReleaseCompletedRunAsyncAssets` after Run teardown; `PreparePlayerDefeat` → `ObservePlayerDefeat` → `CleanupPlayerDeathEffect` (awaited coroutine: detach listener, destroy effects, release prefab references then handle, remove locator; `Dispose` detaches the listener only); `PrepareWorldHealingItemSource` / `ObserveWorldHealingItems` → `CleanupWorldHealingItems` (calls `Dispose`: final observation, level callback removal, instance destruction); `PrepareWorldLegendaryItemSource` / `ObserveWorldLegendaryItems` → `CleanupWorldLegendaryItems` (calls `Dispose`: final observation, instance destruction, remote-transform then host-authority restoration); all four owners created on first use and retained after cleanup; `PopulateWholeStage` → `CleanupWholeStageInteractables` (stage objects only) → `CleanupWholeInteractables` (calls `Dispose`: stage cleanup, spawn-point prefab restoration, lease release); interactable owner created on first use and retained across stage turnover and cleanup | `test_scene_acceptance.py` (acceptance helpers) |
| Position indicators | `TeamIndicatorQueueBoundary`, `AutomaticSpawnBoundary`, `SessionResourceBoundary` | nested `TeamIndicatorQueueSession` owns the cached original queue-processor delegate and first dispatch failure; the automatic body iterator temporarily owns only its captured source-enabled root `TeamComponent` references | capture before the existing disable loop; restore only in the integrated-world path and clear before activation yield; process the original queue from the port fixed tick only while `RoR2Application` is inactive; native component lifecycle plus J787 completed-session pruning remain teardown owners | `tests/test_team_indicator_helpers.py` (authored synthetic lifecycle contract; actual renderer remains an editor/device gate) |
| Equipment expansion availability | `runtime/world/EnemyRewardBoundary.cs`, existing `PortSession.OriginalStats` call site | `EnemyRewardSession` owns one `RewardEquipmentExpansionMaskLease`, retaining the exact native Run and rented mask before population | Integrated survivor state setup acquires before spawn; reward preparation reuses the exact lease; pre-rule refresh locks all required expansions and the later existing rule-ready refresh uses native availability. Partial setup and ordinary disposal return once before Run disable; foreign replacements survive and recovery retains ownership. Item-mask and RNG setup retain their existing phase. | `test_reward_equipment_mask_lease.py`, authored host doubles in `tests/fixtures/reward_equipment_mask_lease.cs` |
| Commerce and pickups | `WorldCommerceBoundary`, `ChestPurchaseBoundary`, `ChestEjectionBoundary`, `ItemPickupBoundary`, `GenericPickupBoundary`, `MoneyCostBoundary`, `PickupDropletFlightBoundary` (10 files) | nested `ChestEjectionSession` (`IDisposable`) **own type** holds chest animation snapshots, source effect pool/cache references, observed effects/returns, owned material copies and droplet/model references; `chestEjectionBegan` stays shared with ChestPurchase on the coordinator; `r.chestEjection` remains the coordinator observation; remaining boundaries use coordinator fields; nested `GenericPickupSession` (`IDisposable`) **own types** hold their files' private state; nested `WorldCommerceSession` (`IDisposable`) **own types** hold their files' private state | `PrepareWorldCommerce` → `CleanupWorldCommerce`; `OwnChestAnimationSources` / `PrepareChestEjection` → `ObserveChestEjection` / `FinishChestEjection` → `CleanupChestEjection` (calls `Dispose`: droplet destruction, source effect pools/cache cleanup, material destruction) → diagnostic `CheckChestEjectionCleanup` after chest/pickup cleanup; owner created on first use and retained after cleanup | — |
| Stage transport and teleporter | `TeleporterWorldBoundary`, `IntegratedStageBoundary`, `AndroidStageTransport`, `StageGeometryBoundary`, `GoldshoresBoundary`, `MoonMissionBoundary`, `MoonEscapeBoundary` | nested `StageGeometrySession` (`IDisposable`) **own type** holds owned billboard copies, Moon-volume mode, map-zone activation/source names and observation callbacks; geometry bundle, scene, materials, source-object/context roots, first-stage selection and `r.stage` stay shared on the coordinator; remaining boundaries use coordinator fields; nested `IntegratedStageSession` (`IDisposable`) **own types** hold their files' private state; nested `TeleporterWorldSession` (`IDisposable`) **own types** hold their files' private state | `PrepareTeleporterWorld` → `CleanupTeleporterWorld`; `PrepareStageTransport` → `CleanupStageTransport`; `PrepareStageGeometry` / `LoadStageGeometry` forward to the session; source-context deactivation stays separate; `CleanupStageGeometry` remains an awaited coroutine at the same call sites, including after `CleanupSpawnConfig` in `Start` (pause zones, detach observations, unload scene, destroy billboards then materials, unload bundle, mark coordinator report); owner created on first use and retained across stage handoffs; `Dispose` is a no-op | — |
| Combat-input first-failure witness | `TeleporterWorldSession.ObjectiveCombatInput`, `ObjectiveCombatInputFailureWitness`, existing `WorldReport` | Only explicit skill-coverage diagnostics allocate/reuse the witness; the ordinary path enters the same core directly. Read-group, row and CLR/Unity-null states describe already-read operands. The first NRE snapshot is copied to the report before bare rethrow; diagnostic failures cannot replace it. No operand becomes optional. | Per-call reset; no retained Unity references; the report survives existing cleanup, which remains authoritative | `test_objective_combat_input_failure_witness.py` executes the production wrapper, witness and report DTO against a synthetic core; runtime cause remains open (J811) |
| First-stage source lifecycle (diagnostic) | `runtime/stage/FirstStageDiagnosticGate.cs`, `FirstStageSourceOwners.cs`, `SourceStageIdentityLifecycle.cs`; existing stage/objective/population boundaries | `IntegratedStageSession` owns the exact source identity transaction and its Director bridge; `TeleporterWorldSession` owns the inactive prepared objective and exact native placement; `WholeStagePopulationObservation` owns pre-start listeners | Explicit per-attempt `SessionReport.nativeFirstStageLifecycleDiagnosticAttempt` defaults off, supports Golemplains/Lakes only and always marks assisted. Prepare native inputs → activate/spawn audited source cohort → genuine Run scene change and server Stage-begin → natural SceneDirector population/Teleporter Start. Retire owned actors/interactables → exact Stage → objective → source cohort → providers. Transport refuses before mutation. | `FirstStageDiagnosticGateFixture.cs` (pure production gates and an inactive native managed-field lease fixture; actual native lifecycle remains a separate device gate) |
| Siren encounter | `runtime/stage/SirenEncounterBoundary.cs` | `SirenEncounterSession` (`IDisposable`) **own type** holds the exact source encounter, its network-spawn lease, native BossGroup listener and observation clock; scalar reports remain in `r.stageProgress.sirenEncounters` | `IntegratedStageSession.BeginOriginalStage` after source population and native `Stage.Start` → bounded stage tick → `CleanupSirenEncounter` before transition/unload or transport disposal; detach listener, retire validated original squad members, unspawn the owned identity, restore source active state and clear engine references | `SirenEncounterHost.cs` (exact-editor selection/transaction fixture; native lifecycle unverified) |
| Siren source entry | `runtime/stage/SirenSourceEntrySession.cs` | `IntegratedStageSession` retains the `SirenSourceEntrySession` (`IDisposable`) and its exact source scene, ID-11 toggle target snapshots, source-spawner disable witnesses, egg identities/poses and per-row retirement progress; reports remain in `r.stageProgress.sirenSourceEntries` | With the exact temporary Stage current, preflight the inactive imported Ship Graveyard identities before the existing Director owner activates ID 2; retain the entry owner first and lease only that exact root/identity activation, requiring it to stay unregistered. Activate ID 11 under the same temporary Stage, then release that Stage. Native toggle `Awake` consumes destination RNG already generated by original Run advancement; perform the existing single Run stage callback then the complete native global callback; observe natural spawners and admit the existing ID-10 owner only after the exact cohort gate. Cleanup retries pending captured eggs, removes witnesses, restores toggle targets and retires/restores ID 11; moved, ambiguous or unknown rows retain recovery context; the first identity refusal reports its expected/actual match, name, active state and registration operands without mutation | `test_siren_source_entry_contract.py`, `test_siren_partial_retirement.py`, `test_siren_source_stage_handoff.py`, `test_siren_source_director_handoff.py` (host contract/retry/order fixtures; editor import and native device lifecycle remain gates) |
| Shaders and presentation | `AndroidMaterialPresentation`, `AndroidNativeDeferredPresentation`, `Android*Presentation.shader` (18 files) | **own types** (static) | `Begin` → `Finish` | `test_shader_bindings.py`, `test_shader_metadata.py`, `test_pc_draw_export.py` |
| Developer controls | `DebugAccelerationBoundary` ([debug-acceleration.md](debug-acceleration.md)) | nested `DebugAccelerationSession` (`IDisposable`) **own type** holds the body, saved god mode, ownership flag, charge scan/callback set and grant inventory; `debugPanel` stays shared with IntegratedWorld's graphics button; sticky "assisted" flags stay in the coordinator report | `PrepareDebugAcceleration` (calls `DebugAccelerationSession.Prepare`) → `CleanupDebugAcceleration` (calls `Dispose`; owner retained) | `test_debug_acceleration.py` |

`AutomaticSpawnBoundary` captures the owned body's live, source-enabled root
state machines before callback isolation. Only integrated-world startup restores
those machines after the existing selected-skill setup, counting newly enabled
callbacks in the strict existing check. Source-disabled machines and minimal
probe scheduling are preserved. The temporary snapshot is released before body
activation/yield; existing body/session teardown owns the components.
`test_automatic_spawn_state_machine_restore.py` executes the production restore
helper with fake-null, identity, source-disabled and nonintegrated cases.

The same automatic-spawn iterator captures source-enabled root Huntress trackers
before isolation and restores them only for integrated-world bodies, after
checking the owned root, serialized indicator prefab, input/team references and
finite positive update frequency. Unity retains ownership of the original
Awake/OnEnable/Start/FixedUpdate lifecycle; body/session teardown retires the
component. Disabled source components and other probe modes retain their prior
scheduling. `test_huntress_tracker_activation.py` executes the authored capture,
restore and target-read eligibility contracts. Native targeting still needs
device evidence; the original indicator's separate application-update callback
is not driven by this restoration. See J808.

The same boundary captures canonical skill-machine identities before yielding.
Cleanup merges entry and current canonical bindings, admits only machines on
the owned live body root, and keeps native remapping such as MUL-T's Weapon2.
Only recorded native body destruction permits already-destroyed child machines.
Each counter-only observer acquires a release lease before its event add;
independent releases run even when source recovery retains the native world.
Destructive teardown remains behind that recovery guard. Cleanup faults are
recorded without replacing a primary iterator exception.
`test_automatic_spawn_cleanup_lease.py` executes these production helpers with
synthetic lifetime, partial-subscription and remapping cases (J792).

`PrimaryFireSession` reuses one scalar operand snapshot during observation and
freezes a separate first-failure snapshot only on refusal or accessor exception.
It captures the live body, locator, primary slot, state machine and state in
order; healthy ticks add no snapshot allocation, identity query or diagnostic
string construction. No native slot, state, stock or readiness is repaired.
The coordinator's `RecordPrimarySessionFailure` preserves the first error;
`AutomaticSpawnBoundary` uses a non-reporting strict cleanup validator and
records secondary detail in `automaticSpawnCleanupError`. These diagnostics
share the existing session report lifetime and retain no Unity references.
`test_primary_operand_witness.py` executes the production observer and guarded
iterator with fake-null, single-read, thrown-accessor and cleanup-failure cases
(J796). J797 observes a CLR-null primary slot on a live MUL-T body/locator.
The input owner computes one `commandoPrimaryDiagnostic` gate from the native
Commando body catalog identity for each session. Only that gate enables the
Commando-specific primary observer, completion readiness read and Commando HUD.
General playable-spine setup and survivor skill coverage retain their existing
scope, as does strict canonical-machine cleanup. The identity policy executes
in `test_toolbot_commando_observer_scope.py`; consumer wiring is checked from
source, while the observer's strict missing-operand behavior is executed by the
existing operand test. J801 verifies the scope correction on device: both
Commando defaults retain the observer, while MUL-T bypasses it and then reaches
a separate shared combat-observer failure. Full-kit acceptance remains open.

CombatSpineSession samples primary and body-state operands independently. Its
single-read helpers record CLR-null/fake-null or missing-state samples without
writing native skills or state. An unavailable sample leaves the previous known
state identity intact; unobserved transitions remain unknown. Other combat
observations continue, and unexpected accessor failures still propagate. The
extracted production contract is tests/test_combat_observer_operands.py; strict
skill-machine cleanup and native ability acceptance remain separate (J804).

Only an explicit Siren source-entry diagnostic entering Ship Graveyard wraps
the existing population and original-stage iterators with
`SirenSourceEntryObservedRoutine` in the existing source-entry owner file.
`IntegratedStageSession` records entry, return and the original exception in
three scalar transport fields before outer cleanup can mask the failure.
The observer forwards yielded values and rethrows the same native exception;
reporting callback failures cannot replace it. It acquires no iterator or
scene cleanup ownership. `SirenSourceEntryFailureClassification` preserves an
earlier failure and distinguishes absent registration from failed cleanup.
`test_siren_source_transport_exception.py` executes these production helpers,
including throwing `Current`, `Reset` and reporting callbacks. Lifecycle,
identity, retirement, recovery and the manual Moon gate remain device gates.

Build, device and safety tooling has its own tests: `test_build_identity.py`,
`test_build_snapshots.py`, `test_apk_identity.py`, `test_adb_target.py`,
`test_lab_safety.py`, `test_public_privacy.py`.

Stage-context preparation seams (J639) remain inside those existing owners.
`EnemySpineSession.PrepareEnemy` forwards mandatory `PrepareEnemyContext` then
its actor fixture. `EnemySpineSession` owns idempotent damage/death event
subscriptions: the native first-stage context subscribes before source actor
activation, while the default fixture subscribes at its existing setup point.
Ownership begins before the first add, normal cleanup removes exact delegates
before actors, and source-stage recovery retains the owner and observations.
`test_enemy_actor_observation.py` executes the authored helpers/callbacks and
cleanup against host collaborators, including partial setup and unrelated
listeners. `EnemySpineSession.ObserveEnemy` samples each live target, state
machine, motor and health component independently, including bodies without a
CharacterMotor. Missing enemy reports skip only dependent reward/actor fields;
navigation and director observers keep their own lifetimes. Prior samples and
death facts survive unavailable components. `test_enemy_observer_lifetime.py`
executes that production method with live, missing and destroyed collaborators.
These host fixtures do not raise native gameplay events.

`IntegratedStageSession` retains an exact effect-pool map/pool/helper return
batch until native retirement is proven. It issues each original return once;
the existing transport and final reward-cleanup coroutines cross one actual
Unity frame only when loans remain, allowing native deferred destruction to
finish before the strict zero-loan and inactive-pool/destroyed witnesses.
Unknown, interrupted or failed ownership retains the batch and dependent
assets. The synchronous native scene-exit listener keeps its immediate guard
and ordering. `RunClockSession.ReleaseCompletedRunAsyncAssets` is now awaited
by `EnemyRewardSession.CleanupEnemyRewards` before forced asset release;
transport awaits the same fence before scene unload.
`test_effect_loan_return_lifecycle.py` executes the production owners/caller
seams with authored immediate, deferred, stuck and foreign-owner collaborators.
It does not identify the exact residual from J746 or qualify native loss.

`AutomaticDirectorSession`
separates native elite/catalog/
player initialization from the existing one-card director activation.
Its native first-stage path registers only the exact existing inactive player
controller before results prepare their statistics component. The later catalog
setup adopts that same registration without another Awake/OnEnable; the existing
director owner removes it even if results fail before a director report exists.
Native stage deck selection records the full deck but defers source director
property/enabled writes to FirstStageSourceOwners after its final cold preflight.
That owner binds both decks before genuine activation; default selection retains
its existing immediate writes. `NativeDirectorDeckSetterFixture.cs`, staged by
the same source producer, checks native setter effects on an inactive component
without a Run or network session.
`WholeInteractableSession` also owns the native first-stage borrowed drop-table
transaction. After exact source identities/toggle targets are captured, it
qualifies Lakes' Chest2 and Wake reward fields, clones four Basic tables through
`TeleporterWorldSession.ObjectiveDropTable`, verifies serialized configuration,
and regenerates choices from the current Run before activation. Positive-weight
categories require current lists; only the ordinary chest requires a nonempty
selector. Empty optional reward tiers remain empty. The known Scrapper exclusion
table and late-bound reward-creator slot are validated without replacement.
`NativeBorrowedFieldLease` records each binding before mutation and restores
only its exact owned/original values. Identity unspawn precedes reverse field
restoration, which precedes toggle restoration and objective resource release.
A foreign replacement retains recovery state and owned resources. Golemplains
has no known chest/Wake consumer. This qualifies accepted known component shapes;
it does not discover arbitrary future table consumers. The portable
`test_native_source_loot_contract.py` executes the extracted lease and checks
source ordering with authored fixtures. Native Run regeneration/roll remains a
device gate.
`TeleporterWorldSession.PrepareInactiveObjectiveTemplate` prepares its owned
clone before the existing direct spawn. `WholeInteractableSession` uses a
short-lived `WholeStagePopulationObservation` to store the exact selection/spawn
delegates and spawn-point baseline around its existing manual native `Start`.
Its `finally` retains sequential detach/collection behavior. These extractions
preserve the current public call order, setup fields and teardown owners; they
enable no native source-stage cohort, new selector or RNG-order claim.

The Siren encounter draft activates and network-spawns only the original inactive
`shipgraveyard` encounter identity. It preserves the source FSM, scripted boss
card, squad, rewards and separately expansion-gated portal callback. It never
calls global scene spawning, so the existing source-disabled MapZones retain
their own boundary. The report distinguishes a selected owner, live eggs, native
encounter start and the exact native BossGroup defeat event. Native squad-member
and summon callbacks identify the original boss and its probes without scanning
all masters. Cleanup validates the complete owned actor set before requesting
body/master destruction; changed identities or ownership refuse retirement.
It detaches its callbacks first, unspawns the source identity, restores its active
state and synchronously destroys only that owned scene instance while the server
is active. This runs the native squad's `OnDestroy` unsubscribe before the existing
session shutdown, which precedes deferred geometry unload. Actor destruction
requests are recorded as requests; `cleanupDisposed` must be read alongside
`cleanupError` and the individual cleanup flags. Egg placement, native spawn/unspawn,
rewards and teardown still need device acceptance. No separate probe switch case
implements this behavior.

Native teleporter retirement (`TeleporterWorldSession`, current source draft,
J600): this owner captures the exact instantiated host and network identity,
marks possible activation before detaching it from inactive staging, and keeps
ownership through partial setup. Final disposal unregisters the identity and
synchronously destroys only that host while the server remains active. This lets
the native `CombatSquad.OnDestroy` remove its server-gated static callbacks before
the outer session shuts down networking. A never-activated inactive host with no
network identity/listeners has a separate partial-setup cleanup path. Exact-target
death/summon callback counts before and after retirement remain as scalar fields
in `ObjectiveReport`; the read-only `NativeCombatSquadListenerEvidence` helper
preserves destroyed Unity wrappers and never restores or modifies event lists.
The existing stage-handoff destruction/two-yield path remains unchanged.
`TeleporterLifetimeHost.Run()` is a Play Mode native-callback fixture, staged by
`whole_catalog.stage_build_sources`; exact-editor execution and Android callback
retirement pass (J601/J609). Repeated-session memory attribution remains open.
No new probe switch case implements the cleanup.

Survivor ability observations (`SurvivorSkillObserver.cs`, current runtime source):
`IntegratedWorldSession` creates this independent `IDisposable` owner after local
player authority is connected. It holds only that body's four original skill slots,
definition snapshots and authority/server callback subscriptions. Native callbacks
use the original `SkillLocator.FindSkillSlot` at each event, preserving Toolbot's
component reassignment and the source precedence for aliased slots. They count
activation per slot; a once-per-second sample records active definitions,
stock and state-machine context. Definition names are cached until the original
definition changes. Removed native components clear live slot context while retaining
historical activation counters. Suppressed missing callbacks are a classified non-pass.
Cleanup detaches both managed callbacks, including after Unity
destroys the native body, then clears all body/skill/definition references before
world teardown. The report is `SessionReport.survivorSkills`; it proves callback
execution, not targeting, placement, effects or complete ability semantics.
The separate `components` report covers every GenericSkill on that body by exact
component identity, including Toolbot/Captain auxiliary loadout components that
native `FindSkillSlot` maps to None. It retains current component indices and
canonical mapping separately from the four slot counters. Bounded samples
reconcile components; a live same-body callback missing from the cache triggers
one immediate reconciliation so its first activation is retained. Removed/body-
destroyed components clear live state while scalar counts remain. Callback lookup
and canonical labels avoid per-activation LINQ closures and enum conversions.
This source draft passed its extended synthetic fixture (J602); auxiliary native
ability execution on Android remains pending. The four-slot device check keeps
its narrower canonical-slot criteria.
`SurvivorSkillHost.Run()` is the exact-editor synthetic ownership/override fixture.
It also checks that the loadout menu retains original component indices and uses
`hideInLoadoutSelect`, independently of character-select visibility. The existing
`OfflineLoadoutBoundary` owns that menu's scroll state, resets it at menu entry or
survivor change, and scrolls the source-selected rows above a fixed footer so
Toolbot's five and Captain's six loadout rows remain reachable.

`./dev prototype --action survivor-kit-check --target all` (current host action,
`scripts/lab/survivor_check.py`) runs the eleven base survivor catalog keys
sequentially in the integrated Lakes world. A comma-separated `--target` selects a
subset. Commando/Huntress use ordinary selection; locked base survivors use an
explicit diagnostic override and invincibility, never permanent profile awards or
expansion availability. Before launching, the runner verifies selected storage
policy against both the ownership receipt and live storage/package placement;
internal-storage reserve remains the install owner's gate. It does not infer
controller support from storage policy. A case needs 60 s of live world play and positive native
authority **and** server activations on all four slots; at 180 s it reports missing
activation evidence. Source-suppressed callbacks remain unproven. First failure,
first-stage departure or process exit ends the batch. Current-process errors are
polled every 10 s, stop the case even when report error fields are empty, and are
checked again in the final log; known handled Windows shader-target messages use
the existing filter. Results preserve the first failure and observed error list.
Each case preserves its first-world screenshot, frozen report, log and crash
evidence under `work/experiments/survivor-check/`. Cleanup removes the selector,
stops the owned app and sleeps the display. Every ADB command checks the parallel
session's coordination lock. Host contracts: `tests/test_survivor_check.py`.
This supplements both unchanged baseline modes; it does not replace them.

The current optional `--expected-apk-sha256` on survivor-kit-check and both
session cleanup actions binds a diagnostic to the selected device's matching
ownership receipt. `scripts/lab/installed_attempt.py` owns hash syntax and
receipt binding, then its existing reader verifies the receipt APK bytes and
extracts the unique embedded attempt before any selector push or launch.
Explicit binding never reads the mutable global current-build pointer, installs
an APK or claims the selected APK is current. Omission retains current-build
equality at check start. The survivor batch resolves this binding once before
its target loop, allowing host builds to finish during independent device runs.
Results record `apk_binding_mode`; default baseline acceptance remains separate.
Refusal/workflow contracts: `tests/test_owned_apk_diagnostic_binding.py` and the
existing installed-attempt, survivor and session cleanup tests.

`DeveloperSkillVariantSelection.cs` is the current, explicitly assisted per-run
loadout boundary owned by `AndroidProfileSession`. The optional
`survivor-kit-check --target <base-key> --skill-variants <ignored-json>` accepts
exactly one survivor. Its JSON object contains `survivor` and `entries`; each
entry contains `componentIndex`, `familyCatalogIndex`, `variantIndex` and
`skillCatalogIndex`. The runner refuses unknown/duplicate fields and duplicate
components before device access. The runtime independently validates the actual
body component order, native catalog identities, family bounds and expansion
requirements. Base-game locked variants remain diagnostic choices, never earned
profile choices or expansion access.

Before `SpawnBody`, the profile owner retains the unchanged profile/default
preview, copies the native master loadout, applies the requested indices through
native loadout APIs and calls `CharacterMaster.SetLoadoutServer`. It verifies
the resulting body against effective per-run variants while checking the saved
profile against its original preview. Diagnostic selections bypass menu-edited
loadout persistence. The master owns this temporary native loadout; profile
cleanup clears the preview/effective arrays, and existing body/master teardown
retires the run. No `SkillFamily`, unlock or persistent profile is edited.

`SessionReport.developerSkillVariantOverrideReport` records request/application
and refusal. A session-level assisted marker is saved before native mutation;
debug report initialization carries it forward, and permanent discovery,
achievement and result gates consult it directly. The launch file cannot supply
that trusted marker. Diagnostic `survivorSkills.skillVariantInventory` and the
override report expose bounded actual component/family/variant/SkillDef indices
for constructing a later explicit selector. Selected native loadout indices and
live runtime definitions are separate: prefab assets have no `GenericSkill.Awake`,
and a live skill can have a temporary override. Invalid or oversized inventories
refuse rather than truncate. This adds no ordinary menu eligibility.
A live inventory binds reciprocal native body/master ownership and exact server
mappings, with the catalog prefab's matching component/family order. Override
inventory takes precedence only for an explicitly requested override; Unity's
empty default inline reports do not displace the actual live observation.
The host result keeps that authoring inventory and labels pre-spawn and live
post-spawn inventories separately in both full-kit and isolated checks. A
requested alternate in the four-slot check must also match the final live
family, selected variant, selected SkillDef and runtime definition/index, with
the effective native loadout agreeing. Non-requested passive/auxiliary runtime
identities gain no invented activation requirement.

Host parser/assessment contracts are in `tests/test_survivor_check.py` and dispatch
contracts in `tests/test_cli_actions.py`. The existing fixture producer stages
`DeveloperSkillVariantSelectionFixture.cs` for exact-editor native API and strict
input checks. Its separate unawakened-prefab contract requires an already loaded
and registered native catalog prefab; idle API checks do not prove application
to that prefab. Source/host evidence and later device variant results stay
separate in the journal.

The checker also classifies J602's current component inventory independently
of the four-slot gate: four components for most base bodies, five for Toolbot
and Croco, six for Captain. Current indexes/instance identities must be unique
and complete; removed history is separate. Missing older instrumentation is
explicitly unavailable. Passive and auxiliary components need no invented
activation requirement; valid inventory is not complete ability acceptance.

`SurvivorSkillInputCoverage` (diagnostic input owner, default unconstructed)
is selected only by `SessionReport.diagnosticSkillCoverage`, which the skill
check explicitly enables. `IntegratedWorldSession` creates it after live
authority, bridge, assist tracking and skill observation exist; applies it
after the ordinary automatic producer; and disposes it before the observer
and body. It resolves current canonical components at each request, reads
native `CanExecute`, and overlays a single 0.25 s ordinary skill-button pulse.
Requests are bounded to 12 and 120 s, spaced by 6 s. Reports distinguish
eligibility, requests, later input-bank edges and native callback counts.
Manual/foreign input changes survive release. No cooldown, stock, skill state
or movement is written. `SurvivorSkillInputHost` tests synthetic routing,
dynamic slots, stale-edge refusal, ownership, bounds and disposal in the
exact editor. Real survivor behavior remains a device gate.

An optional `--skill-slot` on `survivor-kit-check` composes with the existing
strict per-run variant selector for one base survivor. The same owner enforces
one selected native skill request during each 0.25 s pulse and masks all other
skill requests at the input sink for the full 60 s observation interval, even
after the selected input edge and callback pair appear. It also blocks automatic
diagnostic equipment requests while preserving explicit touch input. The result
requires the exact live post-spawn component/family/variant identity, a later
input-bank edge, and fresh authority/server callbacks. It is assisted single-slot
input evidence, not a four-slot kit pass, slot-causality proof, or complete
ability-output acceptance. The special-slot request does not synthesize a
contextual primary input for Huntress Snipe. Omitting `--skill-slot` retains the
all-four behavior above.

The explicit `--toolbot-offhand` option requires one Toolbot target and the
exact native Buzzsaw/Dual Wield variant tuples. The same input owner validates
the live five-component loadout, requests special once, observes native Dual
Wield with its contextual secondary override and Weapon2, then requests
secondary once. It requires later input-bank edges, both native callback pairs
and FireBuzzsaw on Weapon2. The isolated input sink masks competing automatic
skill requests; manual input, identity loss, neutralization or the bounded
deadline stops the sequence. Disposal releases the owned input state before
the observer/body. The default selector remains false. Aggregate damage
counters provide context only; this mode establishes no slot-specific damage
or complete ability semantics. Host contracts extract the production phase
policy and check selector/refusal routing.

The same owner takes four one-shot readiness snapshots only in this Toolbot
mode: before special, after the native Dual Wield override, at the first
secondary-readiness refusal or sequence stop, and separately at the actual
terminal stop. The final snapshot retains its own phase, outcome, elapsed time,
frame count and fixed time without replacing the first refusal. They read stock, recharge,
enabled state, both native readiness predicates, the configured machine name,
the actual resolved machine reference, and the separately named Weapon/Weapon2
machines. Each machine also reports enabled/active state, update-transition
eligibility, pending-main status, configured main type and public networker/index/
authority values. An assigned index is not proof of private network-array
membership; the pending target type has no public API and stays unavailable.
Missing operands and exceptions have explicit status fields;
`captured` distinguishes a real snapshot from an empty serialized object.
A missing or destroyed resolved reference stays unavailable rather than
falling back to an empty-name lookup. No native readiness gate changes.
The report owns these values for the session; disposal releases input before
the observer/body. `test_toolbot_readiness_observation.py` exercises the
production resolver, including Unity-style fake-null references;
`test_toolbot_terminal_readiness_capture.py` executes distinct, idempotent
first-refusal/terminal headers and checks bounded public queries.

The default-off `--captain-supply-beacon` selector composes in this same owner
for one assisted Captain run with the exact native six-component identity and
no variant/slot/Toolbot selector. It snapshots the existing bridge's cumulative
real `InputBankTest.PushState` edge witness before each of two bounded pulses:
Captain special, then re-mapped native SupplyDrop1 on primary. It waits for the
original setup state, both original slot remaps, read-only valid-placement
observation, native authority/server callback deltas, the original healing call
state, an increased CaptainSupplyDrop count owned by the same `CharacterMaster`,
and return to ordinary body state with that deployable still present. Edge
counter reset/multiple increments, lost ownership, neutralization, changed
identity, timeout, or unresolved teardown stop/refuse without writing skill
state, stock, cooldown, placement, deployables, or profile values. The overlay
remains masked while an original native state is pending and disposes only its
owned bridge input/witness. This proves neither supply-drop damage/healing nor
presentation/full ability semantics; those remain separate device gates.
The auxiliary SupplyDrop1 uses native `CanExecute` without an extra Unity
component-enabled requirement, matching the original input dispatcher. A
primary pulse still requires the current setup state, exact slot remaps and
current valid native placement. The report separates current placement and
remap-gated native readiness from the historical positive placement witness;
bounded timeout labels identify the last failing operands.
`test_captain_supply_readiness.py` executes the extracted production phase and
readiness policies, including a disabled auxiliary component.
The setup identity requires the serialized Skillswap activation machine with
`EntityStates.Captain.Weapon.SetupSupplyDrop`; the state's namespace does not
name its machine. `test_captain_setup_identity.py` executes this production
predicate and rejects the former Weapon assumption, other states and missing
identity.
Family names use an explicit `ScriptableObject` base-object read: the accepted
native `SkillFamily` API hides the name property with an unavailable getter.
The same read supplies refusal details, separately from the serialized
`GenericSkill.skillName` label. `test_toolbot_family_name_shadow.py` executes
the production identity/refusal methods with that API shape and rejects
mutated family/catalog/variant/runtime identities.

Siren egg diagnostic input (`SirenEggDiagnosticInput.cs`, explicit default-off
per-attempt selection): `SessionReport.diagnosticSirenEggInput` constructs an
independent world-owned input lease only when selected. Jump snapshots carry a
write revision and fixed-consumption boundary so release preserves a later
producer write and cannot duplicate a consumed pulse. Before ordinary input
producers it releases its prior owned values; afterward it may navigate, aim
and request primary against the nearest currently visible original registered egg.
When all revalidated candidates are occluded, the nearest remains the navigation
target with primary released. Candidate caches above 12 refuse before physics
queries. A fixed scalar witness samples the real Huntress tracker target and
separates missing, disabled and inactive trackers before reading an active
tracker; target states distinguish destroyed, unidentified and known targets,
selected/native ID matches and requested primary. It records live tracker
settings and current geometry without refreshing native tracking or claiming its last LOS/range/cone
decision. Two optional, one-shot eligibility snapshots use the first visible
primary mismatch and a later null target with the same selected egg. They
record the held input aim before this frame's write, exact HurtBox registry
membership with a 4,096-entry cap, current body/team/layer/health/collider data,
and finite range/cone/LOS observations. Cached native target age remains
unknown; truncated absence and unavailable operands remain unknown. Optional
snapshot failures are reported separately, while the existing native target
getter still propagates its original exception before any input action.
Snapshot data survives the existing stop/disposal path; no engine reference
is retained by the report. `test_siren_target_eligibility_witness.py` executes
the authored membership, geometry-policy and getter-rethrow contracts.
`SirenNavigationObservation.cs` is the same world's bounded, read-only
approach recorder. After the same selected egg remains outside the active
native tracker range for 0.5 seconds, it pairs a previous owned
bridge request with a later bridge fixed tick. At most eight samples over eight
seconds record copied input-bank movement, motor/position, source path node and
real path-request identity; labels are capped at 64 characters. Objective stall
is recorded with an explicit availability flag at trigger and request time;
zero or unavailable stall does not prevent observation of a progressing route.
It closes on
manual/owner/bridge/egg change, unavailable operands, clock rollback, yield,
terminal stop or disposal. No normal run or inactive Siren selection starts it.
The context reads native state; route cadence, movement and gameplay remain
owned by the existing navigator/motor. Reports contain no Unity references.
`test_siren_navigation_observation.py` executes the production recorder with a
tracked synthetic reader/contract fixture; the original native-target test
includes the new report types without replacing its witness assertions.
The existing aim helper can issue at most 24 linecasts per active
sample for the inspected original egg shape; inactive selection does no witness
work. It yields to manual control and nearby hostile combat. Native encounter start, source/stage
loss, transport, first failure and the 180 s observation budget latch a stop.
No damage, egg counter, native registration, encounter state or spawn is written.

A separate default-false `sirenNativeEncounterContinuationRequested` selector
uses these same owners after exact source-entry registration. Its launch keeps
the legacy egg-input selector off, and it arms ordinary egg input only after
the live source owner and original Listening state are ready. Entry-only mode
retains its current canonical-registration guard. Continuation retains the
previous exact registration witness while original egg deaths change the list,
holds the next transport request and stops on native encounter start plus an
exact callback-captured boss master, positive network ID and local-object map.
The witness also requires the original catalog body, native monster squad,
active source scene, server identity and absence of player/foreign minion
ownership. The 180 s budget uses world elapsed minus the world-relative stage
entry offset; invalid clock operands refuse. Finalization disarms input and
retains the existing source/encounter retirement and recovery rules. The
continuation's completed flag means this bounded encounter-start observation,
not boss defeat or mission completion. The extracted production contract and
stateful identity witness run in
`test_siren_native_encounter_continuation.py`; device acceptance remains open
(J800).

`SirenEncounterEggTargets.cs` extends the existing source encounter owner. Its
0.5 s sample reads the exact current native Listening registration flag/list,
then caches only native registered eggs. Each input lookup revalidates source
body/catalog/asset identity, exact server object mapping, same active scene,
living health and the original main HurtBox relationship. A replaced native
Listening state cannot inherit the old list. A registered empty list yields no
target; runtime names alone never authorize input. Cleanup clears the cache and
all engine references before source encounter teardown. The editor fixture
checks the imported original asset and native field contracts, plus synthetic
input ownership/yield/stop cases; it does not certify actual mission completion.

Engineer shield compatibility (`EngiShieldHitGuard.cs`):
`IntegratedWorldSession` acquires `EngiShieldHitGuardTemplateLease` only for the
selected original Engi body, before automatic skill input. The caller loads the
exact owned catalog shield template and requires a non-scene asset. The lease
validates its native blocker/Collision references and adds only an authored
component to that in-memory template; native type, serialized fields, collider,
network identity and deployed state remain unchanged. Each Unity-created shield
runs the guard after native Awake, captures its exact native rejection delegate,
and handles only an actual-null world-hit HurtBox. Valid HurtBox targets use the
captured native filter. Processor identity, owner/collider liveness and callback
ownership are checked; missing or destroyed targets remain visible failures.
The first guarded world hit per instance emits a bounded lab log marker.

At host destruction, each instance withdraws only its still-owned callback via
the native HurtBox setter, including a destroyed managed wrapper whose inactive
Collision child never received OnDisable. Foreign replacements remain untouched.
Explicit live component detach restores the captured native callback first;
template release uses this separate path. Both paths clear owned references.
`VerifyIntegratedWorldCleanup`, after server shutdown and two frame
yields, requires scene guard clones to be gone before restoring/removing only
the template component. The existing catalog owner retains asset lifetime.
`r.world.engiShieldGuardPrepared/Released` records the lease boundaries.
`EngiShieldHitGuardHost` is a genuine Play Mode native-filter/clone fixture;
it manually activates the source Collision child and does not certify native
deployment timing or a bundle-template mutation on Android. J614 records its
evidence; J617 adds exact native rejector-list identity checks for inactive
destruction and explicit detach. Native skill/device acceptance remains separate.

LightningStake diagnostics (`LightningStakeDiagnosticObserver.cs`, current
read-only owner): the integrated world creates it after catalogs/report setup,
tracks at most three live exact catalog/server-mapped projectile identities,
releases their sampling slots when identities retire, and disposes with the
world. Its report counter retains cumulative admissions across turnover.
Registry discovery retains the six-frame cadence; only retained objects receive
per-frame finite/stuck checks. A shared policy caps each identity at 12 scalar
snapshots and all history at 36 rows. It reserves the last per-identity slot for
the first observed finite-to-nonfinite transition; at a full history that
transition can replace only the oldest ordinary row. A latched capped status
exposes refused/replaced history without a per-frame string allocation.
Transition-only history cannot grow, and between-scan short lifetimes remain
unobserved. Disposal releases live slots and makes the policy inert. The first
observation is explicitly not a known spawn position.

`r.world.lightningStakes` retains root/network/Rigidbody values, velocities,
owner attribution and native stick/victim/local-offset/ancestry observations.
Frame/fixed-time clocks accompany world seconds. No native fire/collision hook,
transform correction or error filter is added. Diagnostic read failures expose
an inert status separately from native runtime errors. The source-asset/policy
fixture checks minimum imported identity/geometry and actual sampling limits;
`test_lightning_stake_observer.py` executes the extracted policy and identity
retirement with authored host collaborators. Report replacement/status remain
source-inspected there. Only a device trace can identify a runtime transition,
and neither fixture nor
first sample proves native fire input. J623's intermittent corruption remains
unresolved until new evidence identifies its producer.

Engineer native outputs (`EngineerNativeOutputObserver.cs`, current authored source):
`IntegratedWorldSession` creates this read-only `IDisposable` owner for the exact
live original Engineer after local authority and skill observation exist. A
once-per-second sample reads only that master's native deployable list. Mines
and bubbles require their native slots, reciprocal owner and exact projectile
catalog identity with a server-local network mapping. Bubble deployment state
and ownership of the exact source Collision HurtBox guard filter are separate
counters. Turret masters require native deployable/minion ownership and the
original master index; live bodies additionally require reciprocal master/body
references, original body index and server mappings. The original summon event
records exact owner/current catalog master attribution independently of samples.
No skill, stock, damage, deployable, state or gameplay object is changed.
The native deployable wrapper may be uninitialized before first registration;
the observer uses its bool contract before Count/indexing and never initializes
the master's backing list. An idle exact-editor fixture covers that cold state.

The report is `r.world.engiNativeOutputs`. Unique observed counts and native
mine state names survive cleanup as scalars; they do not prove damage, turret
attacks, shield blocking, the guarded-null-hit branch, or every transient output
between samples. Disposal before skill/body teardown detaches the summon event
and clears retained engine references, sets and scratch storage. The source
asset fixture reads minimum GUID/relationship contracts without activation;
its separate Play Mode clone fixture checks real guard/HurtBox remapping and
retires only fixture-owned callbacks. The adapted-catalog fixture requires
initialized lab catalogs and has its own execution gate. These fixture contracts
do not substitute for actual server-created Android outputs.

Native objective exit telemetry (current authored source, J632):
`TeleporterWorldSession` owns scalar snapshots at activation edges, its existing
begin/finish subscriptions, and three bounded post-finish observations. Summary
state-change saves follow the complete observation. `ObjectiveExitTraceBuffer`
reserves initial/first-fault/terminal evidence within 16 entries; separate UTC,
frame, fixed, world, Run and Stage clocks avoid conflating time domains. Setup
resets controls per objective, teardown uses the existing exact subscriptions,
and read failures make only telemetry inert. No native method/input/state is
changed. `TeleporterExitTraceSourceContractFixture` checks the exact native API
and production buffer through the existing fixture producer. Android trace
acceptance remains pending; J641's APK contains this telemetry source.

`WorldCommerceSession` owns the typed ShrineUseEffect baseline and synchronous
native-purchase attribution counts from setup through final cleanup. Its inline
`NativeShrineEffectAttributionWitness` reports failure operands (baseline,
final, delta, aggregate and four concrete shrine callback counts). Those counts
share the existing session lifetime; they do not intercept native loads or claim
their caller. Cleanup still requires exact equality before releasing references;
a mismatch retains the existing recovery refusal.

For the explicit native-first-stage diagnostic only, this owner also owns an
inline `NativeShrineEffectOperationSnapshot`: one weak operation baseline before
the first boss-shrine observation, one post-purchase snapshot and one reserved
final-cleanup snapshot. Read-only locator/cache reflection records actual
operation/version/result identity and reference counts, current versus setup
legacy GUID, support-array index and native effect-catalog index. Locator/raw
location/cache/match/string limits and incomplete/error markers are explicit.
The report retains scalar strings only; the baseline retains weak references.
It adds no load, wait, acquire, release, profiler callback or per-frame polling.
Capture failures stay diagnostic and the strict refusal remains authoritative.
Post-event state is not proof of the native call's exact lookup or a rendered
effect. The existing `FirstStageDiagnosticGateFixture.cs` producer owns the
authored operation fixture: it runs twice, verifies shared-operation/count and
missing/error cases, then checks exact provider/locator/cache restoration.
The compiled formatter host contract preserves the ordinary failure prefix.

Native teardown restores the source cohort and borrowed tables before final
commerce reconciliation. `TeleporterWorldSession.Dispose` performs that
reconciliation while the baseline objective-support leases still exist, then
releases support. `IntegratedWorldSession` resumes its remaining cleanup afterward.
`test_native_commerce_release_order.py` compiles the actual two native branches
and support tail against the authored `native_commerce_release_order_host.cs`
ownership contracts, including refusal before baseline release.

Survivor combat output observation (authored source, J642):
`IntegratedWorldSession` owns a disposable `SurvivorCombatOutputObserver` beside
the skill observer; `r.world.survivorCombatOutputs` holds bounded scalar reports.
Setup requires the exact live server-mapped body/master and subscribes one stored
native damage delegate. Direct body damage, mapped projectile inflictors and
reciprocal owned summons remain separate attribution facts. A one-second sample
visits at most 4,096 server identities; scan truncation and sampled live counts
are explicit. Histories retain 32 damage facts and 64 distinct network IDs;
overflow observations and retained unique IDs are separate counts. Unity damage
time and world sampling time are separately labelled. Network-ID reuse and
short-lived outputs limit coverage; no skill slot is inferred from timing.
Each damage fact also records attacker/victim native catalog names from
`BodyCatalog.GetBodyName` at the event. These use the existing cached native
strings; missing bodies/indices remain explicit empty names. The unchanged
body/network indices and reciprocal ownership checks determine attribution.
Names help interpret a later exact index without reconstructing catalog order.
The exact-editor API/None fixture reports whether any positive native entry was
available; idle editor catalogs remain uninitialized. The existing first-stage
editor fixture source also owns `MageEarthShardsStaticConfigFixture`: exact
staged config/projectile GUID-path identity, native `ApplyStatic` after distinct
sentinels, and finally verified restoration of all captured mutable state fields.
It creates no Run/catalog/network and proves no device projectile output.
Portable tests execute
the authored helper against an authored catalog double.
Cleanup detaches before body/skill retirement and releases owner references.
An observer read failure records its first bounded error and makes only telemetry
inert. A pending unsubscribe retains its recovery handle for disposal/retry before
replacement; partial reports are never complete output evidence. The exact-editor
fixture checks native API, caps and fault/disposal contracts without native objects
or global event dispatch. This owner changes no gameplay, authority, stock or RNG.
For an explicit isolated-slot request only, the existing observer may arm up to
three one-second projectile-observation windows, with a 0.05-second cadence and
at most 60 extra scans per session. The inline pure
`TransientProjectileWindowSchedule` is owned/disposed with the observer;
`IntegratedWorldSession` resets its request cursor on setup/cleanup and arms a
window when its existing input owner issues a request. Normal runs retain the
one-second scan deadline. All scans reuse the same native server/owner/catalog
checks, 4,096-object bound and 64-record history. In-window baseline scans count
as observations without using the extra-scan budget. Reports separate request,
accepted/drop, scan/cap, expiry and maximum observed gap; these are partial after
an observer fault. A request window does not prove state entry, projectile
causality, complete transient coverage or per-slot damage. The extracted actual
timing policy has a compiled portable host contract.

`TeleportMaterialSession` also owns final overlay/material release.
`TeleportOverlayRegistryOwnership`, in the same authored file, reads the native
active registry prefix to resolve exact wrapper identity before public removal.
A remembered `managerIndex` alone cannot authorize removal. After tracked
overlays are retired and deferred destruction yields, the owner runs the public
native overlay update to prune destroyed-host entries, then requires the global
registry to be empty before releasing material resources. Live foreign overlays
remain intact and cause refusal. The owner neither clears nor replaces the
registry. `TeleportOverlayLifetimeHost` reproduces stale-index reuse and native
destroyed-host pruning in isolated exact-editor Play Mode; it restores only its
fixture-owned entries. Actual completed-session cleanup and restart pass in J609.

`./dev prototype --action session-cleanup-check` (current support action,
`scripts/lab/session_cleanup_check.py`) observes the existing first-stage loss
and restart flow with automatic diagnostic input and every gameplay debug
assist disabled. Optional `--target <base survivor>` selects the exact survivor;
the default remains Commando, and locked base choices are labelled diagnostic
overrides. Every current report must match that choice before any menu/restart
tap. It requires a genuine player death/result, native teleporter listener
retirement while the server is active, and live session 2 in the same process. It verifies the receipt-backed APK against its host artifact, freezes
profile counts, and refuses stale reports, runtime errors or departure from
Lakes. Setup preserves and removes only the owned report targets; teardown
preserves foreign selectors, verifies process termination and sleeps the display.
Raw evidence stays in validated `work/device/<serial>/experiments/session-cleanup/<attempt>/`.
UI-abandon startup waits at most 60 s from its first world-playing snapshot for
sampled positive health/maxHealth, ready/input evidence and the required guard.
Only then does its 60 s host interval start. Death/ending evidence stays fatal
through startup; any sampled interruption after the interval begins refuses.
The check cannot certify an unassisted run, permanent unlocks or a memory leak
fix. Host contracts live in `tests/test_session_cleanup_check.py`; J609 records
Android acceptance on the earlier J608 APK; the current candidate needs its own check.

`./dev prototype --action session-abandon-check` (current support action)
uses the same runner with an explicit separate ending contract. After at least
60 s of sampled ready, living first-stage play it taps only the reported
settings and end-run controls, requiring Unity/Android screen-grid agreement.
It observes the existing offline UI abandon flow, native listener/template
cleanup and a same-process restart. Explicit no-death/no-ending/no-result fields
and unchanged profile counts are required. Locked diagnostic targets may launch
directly; free targets require the ordinary menu. This action does not invoke
death, result or teardown methods and does not change difficulty/settings.
Free-target abandon also requires the returned session-2 menu and validates the
saved session-1 completion before tapping Start again. It requires the newly
reported settings screen dimensions in the installed APK;
older APKs refuse those taps. Genuine native loss remains the separate default
session-cleanup-check contract.

The host-only `HostMilestoneTiming` helper in the same runner records one-time
`time.monotonic()` offsets from `device.launch()` return. It marks observed
menu/world reports, returned UI commands, validated completed cleanup and the
existing healthy session-2 predicate. Missing milestones and out-of-order
interval endpoints remain null; abandon may observe the menu before validating
the completion report. `host_timing` is emitted in result/summary evidence only.
These measurements change no acceptance gate and are neither native CPU/FPS nor
proof that a warm batch executor exists.

Both cleanup actions accept the current optional `--skill-variants` JSON for
one base survivor, using the skill check's strict selector parser before device
access. The attempt-bound selector stays until runner finalization; a fresh
coordinator rereads it, so each session independently applies and verifies the
request. The runner distinguishes pre-mutation catalog metadata, effective
native loadout indices and the post-spawn setup snapshot, and requires the
sticky assisted marker. Setup snapshots are explicitly not continuous ability
observations. Original loss and UI-abandon remain separate contracts.

For APKs with combat-output instrumentation, the runner checks the first ready
healthy observer, completed-session detachment and fresh restarted attachment;
inert/error reports fail even after detachment. It waits for ready positive
health, diagnostic input and the Engineer guard before classifying startup.
Older absent instrumentation is explicitly unavailable, never a positive
observer lifecycle result. Host contracts remain in
`tests/test_session_cleanup_check.py`; this adds no runtime or profile writer.

`./dev prototype --action session-memory-check --expected-apk-sha256 <hash>`
(current support action, `scripts/lab/session_memory_check.py`) repeats the
ordinary Commando menu start, at least 60 s of ready Lakes play and the same UI
abandon five times in one process, then stops at the sixth menu. Each completed
`movement-completed-session-<k>.json` must pass `abandon_contract` (reused through
an index-checked session-1 view) before the next start, and profile counts must
stay frozen. It collects the existing `SessionResourceBoundary` samples plus host
`dumpsys meminfo` TOTAL PSS at every menu and reports per-session slopes from
session 2 onward. It is an observation runner: it attributes no retaining root
and certifies no leak fix. It binds only an explicit owned APK hash, refuses a
`--target`, and keeps evidence under `work/device/<serial>/experiments/session-memory/`.
Host contracts: `tests/test_session_memory_check.py`.

`session-memory-root-check` is the same runner with the launch selector's
`diagnosticCompletedRootWalkSession` set to the final menu's session index.
`SessionResourceBoundary` reads only that value (and the attempt) from the
selector itself. At that one `before-presentation` sample, after every measured
session and outside live gameplay, it runs the Unity-free
`CompletedSessionRootWalk` over static fields of every loaded type plus live
`MonoBehaviour`/`ScriptableObject` objects as named roots. The walk is a bounded
(1,000,000 objects) breadth-first, read-only field/array/delegate-target walk
that skips weak references and reflection metadata. It records up to 16
shortest paths to completed probes/reports, its node count, truncation and read
failures in the sample. Reading an uninitialized static field runs that type's
static constructor; J773 saw this register an original achievement callback
that the progression owner then refused. The walk therefore runs only at the
final menu and stays off by default. Host contract:
`tests/test_completed_session_root_walk.py` compiles the production block with
the pinned Mono/Roslyn.

`ReclaimCompletedSessionResources` also owns one adapted Android lifecycle
step (J775). Original `BaseAI.Awake` subscribes to the static
`GlobalEventManager.onCharacterDepossessed` and never unsubscribes, so every
spawned AI stays reachable. After the world is cleaned, with no Run or network,
the owner removes only entries whose `BaseAI` Unity has already destroyed,
through the Unity-free `CompletedSessionRootWalk.RemoveTargets`. It records the
count on the `completed-before-reclaim` sample. Live subscribers and accumulation
within one run are unchanged. J775 measured no managed-memory effect from it.
The same step (J787) removes Unity-destroyed entries from the original static
`ItemDisplayRuleSet.instancesList`, `PickupDropTable.instancesList` and
`TeamComponent.indicatorSetupQueue`. The first two keep assets from each
session's unloaded whole-catalog bundle. The named indicator owner now restores
source-enabled root components and services the original queue while the native
application dispatcher is inactive; native lifecycle owns initialization.
Completed-session pruning remains available for destroyed queue entries.
Per-registry removed/remaining counts are recorded; actual indicator rendering
remains a device gate (J804).
The final-menu walk also records a census: the 60 most frequent reachable
types with object counts and primitive-array bytes (`rootWalkCensus`).

`AndroidProfileSession` also owns the exact native timed-chest `Opening.onOpened`
subscription. That event has no sender or chest identity; it is recorded as a
global native observation for the sole owned offline profile. Setup captures
the exact Run/body/master and stable Android store/save-system owners. Each
callback resolves the current profile after prior transactions may replace its
object, validates the current owner/profile identities, then uses the existing
unassisted detached native achievement transaction. Teardown removes the exact
delegate and clears captures before releasing profile state. Assisted attempts
remain excluded; positive ordinary event delivery and saved awards are runtime
gates. `AndroidProgressionHost` exercises complete event metadata, detached
native grant/duplicate behavior and profile replacement in an isolated fixture,
without synthesizing the source event.

`scripts/lab/source_identity_metadata.py` owns the source identity/toggle
metadata read by `SourceStageIdentityLifecycle`. Existing
`whole_catalog.generate_build_maps` emits it into `WholeStageContexts.json`
from the exact staged `SourceScenes` bytes and their generated candidate
receipt; mismatched hashes refuse. It retains nonzero network scene IDs,
source component/object IDs, ordered group ranges, full slot widths and nulls.
Runtime bindings resolve exact object references through an ordered Transform
path under a uniquely named/shaped root, validating names, sibling counts and
child indices. Identical same-name/root-shape ambiguity refuses. Static
metadata for other Base scenes does not extend the runtime scene gate.

The early `original_stage_contexts` policy call remains independent of staged
source scenes and receipts. R5 policy paths explicitly omit identity metadata;
the nonempty post-R6 R7 map generation requires it, then R8 stages the consumer
and `SourceIdentityTransformParityFixture`. The fixture uses a disposable
inactive preview hierarchy, verifies Python/C# Unicode hashing and exact
ordered path resolution, and destroys/closes that hierarchy in `finally`.
No native Run, networking or real source scene is started by the fixture.
Host contracts: `test_source_identity_metadata.py`,
`test_source_identity_context_phase.py`, `test_source_identity_transform_parity.py`.

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
