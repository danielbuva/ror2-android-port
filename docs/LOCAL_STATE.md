# Local state dependency inventory

## Independent source audio prefab

`owner_audio_prefab.py` reads explicit owner work configuration, accepted input
and reviewed inventory plus the four original bundle paths named by the audited
`recipe/owner-audio-prefab.json`. No exported asset, lab project or historical
source catalog is a supplier. The tracked generator creates all new prefab and
terminal receipt files; the single export-GUID relationship is configuration,
not serialized data. [Setup](phone-owner-build.md#bounded-source-audio-prefab)
describes ownership/refusal/lifecycle. Current game builds select none of these
new outputs automatically.

`work/coordination/owner-wwise-prefab-v1/` retains original-input inspection,
lookup comparisons, complete private/public-source reconstruction attempts and
the first quoting/signed-zero difference. All original type trees and generated
prefab content stay private. No new source consumes a timestamped experiment.

## Independent source audio index

The current source bank owner entry reads explicitly supplied owner work state:
`config/local.json`, `config/accepted-input.json` and `inventory/files.json`.
It uses the original PC XML/banks from the configured installation, never a
captured Android output or `lab-project/.port-input.json`. An explicitly requested
metadata qualification additionally needs the owner's `vgmstream-cli` executable;
default source-only indexing does not run it. The tracked parser/entry produces
all new index/receipt files. [Setup](phone-owner-build.md#source-audio-inputs-without-a-project)
describes new-output ownership, inventory checks and optional tool execution.

`work/coordination/source-audio-inputs-v1/` retains the complete private source
case, metadata-only control on an owned bank copy, exact pinned-index comparison
and final public entry outputs. A byte-identical research copy of the historical
Init transformer remains under
`work/coordination/wwise-init-android-platform-metadata/transform_init.py`, source
SHA-256 `91c72d254ba9473d93ffb18c4be2233be1781b6072b08571aed7f607e76e9b37`.
It remains a private historical comparison artifact. The separately audited
readable template and full-inventory-gated `owner-code/legacy_init.py` now
reproduce that exact historical bank/receipt from public authored source; this
private source copy is no longer a required producer input. The public
`wwise_init_platform.py` remains the preferred generator for new bank/receipt
execution. All event/media names and generated index data stay ignored. The current game build reads none of this research state and no
existing runtime stage/request pin is changed.

## Retained package producer inputs

The experimental `tools/phone-build/package-assemblies/produce.py` reads an
explicit private request with `sdk_install`, `packages` and new `output` paths.
An owner may store that request under `work/config/`; it is not discovered
implicitly. The exact SDK and provider package sources/precompiled helpers are
required owner-supplied local state because they are not distributed in Git.
[Setup and pinned versions](../tools/phone-build/package-assemblies/README.md)
describe acquisition and layout. The tracked producer/profile generate every
compile response, the managed post-processor and all four output DLLs; they do
not require captured project responses or precompiled player outputs.

`work/coordination/package-assemblies-v1/` retains the complete private host case:
provider metadata/archives, extracted SDK/package inputs, initial attempts,
final public-source invocation, complete outputs and captured-player comparison.
The current game build reads none of this research state. No tool selects a
timestamped run or copies an output into the shared project automatically.

## Original game audio build selection (2026-10-20)

The current whole-catalog build reads the optional ignored
`work/config/original-game-audio/selection.json`. Absence means default off.
Schema `original-game-audio-build-selection-r1` has `requested` and, when true,
a 32-character request identity plus exactly ten `inputs` paths relative to
canonical `work/`: `android_source`, `android_os_string_source`,
`native_library`, `abi_native_plugin`, `stage_receipt`, `stage_root`, `prefab`,
`bank_index`, `adapted_init`, and `init_receipt`. No path may traverse a symlink.
The authorized Unity Integration Android declarations/OS-string helper and
Release ARM64 plugin come from the protected local `work/wwise/` extraction.
The separately built instrumented runtime is J794/J845's hash-pinned private
SDK product, not the Release ABI-inspection input. The prefab is supplied by
the accepted local AssetRipper export; `wwise_bank_index.py` produces the
explicitly selected bank index. The adapted Init and its transformation receipt
are J744's required private metadata adaptation inputs. Their current receipts
remain required local state until that separate generator is promoted.

`tools/unity/support/audio/generators/stage_original_game_banks.py` produces
the selected stage root/receipt from those explicit inputs and an explicit
`--soundbanks-info` path to the accepted installation's metadata. The current
R2 receipt contains 153 original banks, adapted Init and the complete 120-file
streamed-media closure with original bytes; all stay ignored. The pure
`original_media_plan.py` planner binds metadata and full-inventory hashes,
rejecting missing files, inconsistent modes, aliases and changed bytes.
The old bank-only R1 stage remains a historical rollback input, not a complete
current audio selection. Do not reuse its receipt for an R2 build. The build hook never searches an analysis
run for inputs. Its authored managed producer requires the locally supplied
.NET SDK (currently 10) and cached NETStandard.Library.Ref 2.1.0, plus the pinned
Unity Mono/Roslyn/Cecil and bundled Android NDK `llvm-nm`. Protected SDK source,
native libraries and generated game assemblies are never public dependencies.

`original_game_audio_produce.py` generates immutable source/tool/input-keyed
directories adjacent to the selected project under `original-game-audio-owner/`.
These contain compiler response files/logs, transformed assemblies, generated
request/contract/pins, artifact manifest and generation receipt. The project
ownership receipt records exactly staged files; Unity-created bank/media metadata
sidecars are preserved. Requested staging copies the selected bank-cohort receipt
to `Assets/StreamingAssets/stage-receipt.json` for the runtime payload copier;
the project ownership receipt under `StreamingAssets/Lab/` is a separate output.
Both files are generated locally and stay ignored. No build reads the host scratch roundtrip reports or
timestamped experiment outputs implicitly. Destination builds select their own
work root's configuration, keeping the current lab opt-in separate.

Schema `original-game-audio-build-selection-r2` retains those inputs and adds
the optional boolean `passive_pcm_capture_requested`, default false. R1 remains
accepted with capture disabled; it rejects the new field. The flag is included
in generation/cache identity and the generated process request. It selects a
bounded observation of ordinary gameplay output, with no test event. The V1
readback can persist a private raw prefix only after verified original shutdown. The optional R2 boolean `passive_pcm_capture_music_output_requested` defaults
false and requires passive capture. It selects the exact ready original music
output dynamically at gameplay admission; no output identity is configured on
the host. The optional R2 boolean
`passive_pcm_capture_after_authority_skill_requested` also defaults false;
omission is normalized to false. It requires passive MainOutput capture and
refuses the MusicController-output selector. It waits for the existing owned
authority-skill callback during playable-world time without issuing an audio
event. All three flags enter cache/request/staging identity. R1 rejects these
new fields. The current waveform-capable native library is an explicit licensed local input:
`work/coordination/original-game-audio-pcm-waveform/r26-native-build-draft-r3/`
`native-waveform-r26/libs/arm64-v8a/libAkSoundEngine.so`, SHA-256
`9075b5a4d3718a209eb244760d2b251a59ef2f5c486a2d2fc0e83b90240cbba3`.
Its adjacent `build-record.json` binds the authorized SDK sources/archives,
NDK r25c, exact isolated four-file extension and authored adapter; the matching
`source-waveform-r26-stage.json` binds the exact written record bytes. Required
private source is the sibling `source-waveform-r26/` tree, including the SDK-derived
bridge, Android build list and bounded V1 ring. Reproduce it through the retained
hash-bound build adapter/plan and explicit Root clearance in that R3 directory,
from the preserved R1 target-capture source and the reviewed private native delta.
Protected integration source, SDK archives and resulting native binaries cannot
be published; these remain required licensed local state. The static audit and
its raw/translated record bindings are under
`work/coordination/original-game-audio-pcm-waveform/r26-native-static-audit-root-r2/`;
it proves host ELF closure only, not Android loading or playback. Keep J918's
previous native 4f309b9d and its source/receipts under
`work/coordination/original-music-target-capture-native-build-root/r1/` for R25
and older rollback receipts. The selection must name an exact library explicitly;
no timestamped run or mutable current-build pointer is searched implicitly.

The private waveform transport is `lab-original-audio-pcm/` below the selected
app's actual Unity persistent-data root, never a configured SD path. Each raw
float/JSON pair is create-new, named with an opaque capture ID and native
generation, and written only after both original Terms plus verified monitor
disarm. Existing files are retained. Root copies the exact new closed pair into
an ignored evidence directory after shutdown; package ownership, process exit,
APK identity and actual data backing remain device-run gates. Raw audio and
exported WAVs stay ignored. The current host exporter is
`python3 scripts/lab/original_audio_pcm_waveform.py --help`; it consumes explicit
raw/metadata/output paths under `work/` and writes a separate hash-bound WAV
receipt. It does not read a timestamped run implicitly, post events or operate a
device. Public tests use authored synthetic float samples only.

The SoundEmitter restorer also reads the existing accepted-input,
reconstruction and project-input receipts and the accepted export's prefab/meta;
it pins the exact source bytes and changes only the owned project copy.

## Isolated phone build support (2026-10-20)

`native-flags-*` selectors, source-bound stages and the retained Android adapter
under `work/coordination/phone-proof/` select the independent native flag reader
probe. Sources come from the committed public readers; SDK bytes are selected
read-only through the existing owned SDK receipt. Fresh device/storage/reserve
and source/tool/input hashes are required. New reports and refusal controls are
outputs, never game or phone-build inputs; no timestamped directory is inferred.

`phone_wrapper_oracle.py` generates SDK-only projects under
`work/rebuild/phone-wrapper-oracle/<attempt>/project/` from its public C# source.
An explicit check request selects that project; each batch check creates a new
adjacent report/log/receipt directory. These private native metadata/wrapper
observations are desktop verification outputs, never game or phone-build inputs.
The generator and exact-editor runner preserve source, SDK and assembly hashes.

`work/rebuild/phone-content/<attempt>/project/` is generated by
`phone_content.stage` from public authored fixture sources using the Python
standard library. UnityPy independently checks the output on the host. Its bundle/source receipt, exact-editor reports and separate
APK are outputs, not inputs to the game build. Debug signing and Gradle state
are isolated under `.local/phone-build-*`.
Fresh fixture builds also generate `editor-build-<attempt>/linker-capture/`
through the authored `ContentFixtureLinkerCapture.cs` callback and
`player-build.json` through the builder. Their private input copies are bound
to the same BuildReport/commit by `phone_content.validate_linker_capture`.
These are experimental stripping inputs, not current game-build inputs.
The `strip-capture-stage-selection.json` and `strip-capture-build-selection.json`
receipts under the phone proof root select one fresh authored project/build and
its snapshot. The tracked `phone_linker.stage_action` produces
`work/rebuild/phone-linker/<attempt>/` from an explicit project/APK/capture request;
its SDK/tool/input copies stay private. This includes supplied
`il2cpp/LinkerDescriptors` under its original relative tool
root: command-line descriptors alone do not cover the linker's implicit defaults.
`strip-linker-stage-selection.json`
and `strip-linker-run-selection.json` select exact staged/owned Android attempts.
The private `strip-linker-on-android.py` adapter is required local replay support
for receipt-bound workspace/tool verification, fresh capacity, staging/execution
and output collection. No current game build reads these inputs.

The optional `native_registry` object contains an explicit absolute owner SDK
`binary` path and its pinned `sha256`. `phone_linker_roots.stage_support` produces
`project-root-data.json`, `registry/` with both authored readers and unchanged
SDK bytes, and the staged generation helper. The captured
`inputs/EditorToUnityLinkerData.json` is deliberately absent in this mode.
`phone_linker_roots.generate` produces `native-roots/sdk-registry.json`,
`EditorToUnityLinkerData.json` and `receipt.json` at the actual stripping output;
the linker command points there. Source/input/output hashes and a captured-
project flag preserve the distinction between SDK metadata and project roots.
The retained `native-root-linker-on-android.py` under the phone proof root is
local replay support for the same owned workspace, explicit device, fresh
capacity, exact staged inputs, tool verification and output collection. It
never overwrites the earlier stripping adapters, selectors or results.
The `native-root-linker-*` request/stage/run/boundary-check files under the phone
proof root select that explicit experiment. `native-root-converter-*` and the
retained `native-root-converter-on-android.py` select its downstream unchanged
converter action and owned Android execution. `native-root-native-selection.json`
and `native-root-native-handoff-check.json` bind the validated C++/metadata
boundary; no native compile or game build reads an unselected run directory.

The optional `module_policy` request selects the explicit
`builtin-modules-no-overrides-v1` fixture profile alongside `native_registry`.
`phone_module_policy.stage_support` copies unchanged pinned editor/target
`modules.asset`, project manifest and SDK builtin package JSON into private
`module-policy/`; the known fixture file set and builtin package lock are checked
for eligibility. No captured policy array is staged: `project-root-data.json`
contains only serializedTypes/typesInScenes. The authored policy reader generates
`native-roots/module-policy.json` at actual stripping invocation; input/source/
output hashes bind its generated arrays through the downstream handoff.
The `module-policy-*` selectors and retained `module-policy-linker-on-android.py`
under the proof root select new owned runs with the same device/tool/capacity
guards. Earlier adapters/selectors stay intact. No game build reads this state.

`work/coordination/phone-proof/nativeaot-tool-host-r1/` retains J1023's
versioned authored fixture publications, pinned upstream-source worktree,
failed stock-exporter publications, public dependency archives, local linker
adapter, exact input/output manifests and terminal phone reports. The public
fixture sources live in `tools/phone-build/tool-host-fixture/`; local
`build-fixture-v3.py`, `run-phone-fixture-v3.py` and `phone_fixture_v2.py` are
required replay support for the explicit owned Alpha shell workspace, fresh
capacity checks and hash-bound supplied tool/crypto support. Explicit versioned
selection JSON identifies each fresh attempt; no consumer infers a timestamped
path. Failed/earlier attempts stay preserved. These are tool-host observations,
not inputs to a game build or a complete installer. The process-local linker
adapter does not replace the Unity game NDK.
The same root retains J1025's self-test-only `assetripper-console-v1/`,
`assetripper-console-aot-v1/` and `assetripper-console-managed-v1/`, explicit
authored parser-input versions, `parser-proof-v1.json` and phone selection.
`build-assetripper-console-aot-v1.py`, its managed counterpart,
`run-phone-parser-v1.py` and `phone_parser_v1.py` are required local replay
support; the unchanged pinned upstream source supplies the importer library.
These experimental files remain outside every current game-build consumer.
J1027 adds private `assetripper-import-v2/` with explicit configuration, bounded
status/error observations and separate authored/configuration/import modes.
The versioned managed/native build adapters generate fresh publications; failed
compiler/source variants and moved partial native intermediates stay preserved.
`phone_import_refusals_v2.py` and `run-phone-import-refusals-v2.py` replay the
14 control cases through explicit owned selections. `configuration-proof-v1.json`
binds those controls. The source-bound `native-import-review-v3.json` selects
`run-native-import-v1.py` and `native_import_phone_v1.py` for the subsequently executed J1029
actual-input trial; v1/v2 are superseded. These local adapters are required replay
support, not a public installer or game-build input.
J1029 adds explicit `native-import-selection-v1.json` and malformed-control
selections with retained terminal result/events/stdout, actual input/tool
readbacks and `actual-import-proof-v1.json`. Failed scratch content remains in
its owned case. `lowmem-thresholds-v1.patch` and its source-binding receipt
select a separate pinned upstream source with only the prior temporary-stream
threshold changes; this candidate is not a current build input or native result.

`work/coordination/phone-proof/` retains J832's private execution adapters,
hash-bound tool/package manifests, original failed attempts and collected device
evidence. The `converter-host.py`, `converter-android.py`,
`converter-layout-retry.py`, `compile-android.py` and `content-device.py` adapters
are required local replay support, not a public installer or game-build input.
The supplied Unity converter/corelib/icall/header copies remain private;
Termux package archives are bound to their official HTTPS index hashes.
`device-owned-workspace.json` identifies the isolated shell workspace retained
on the alpha device for replay. It contains no installed game or package data.
The disposable content fixture package is removed after verification.

J833 adds private tool acquisition/staging and Android execution adapters under
that same evidence root: `fetch-python.py`, `fetch-packaging.py`,
`fetch-signer.py`, `generate-on-android.py`, `stage-packaging-tools.py`,
`package-on-android.py` and `android-packaging-driver.py`. They retain hash-bound
public package inputs and original failures; they are required local replay
support, not current game-build inputs. `phone-generation-package-receipt.json`
binds the successful outputs and device evidence. Its disposable signing key is
encrypted; the generated password exists only in the signing process environment
and is not retained. This identity is not a release or durable owner key.

`work/experiments/phone-packaging/<attempt>/` is generated by the tracked
`phone_package_check` owner, including failed attempts. Ignored local requests
select exact APK paths/hashes, a phone-generated bundle hash/path and the matching
shell-workspace ownership receipt. `phone-apk-fixture` generates separate new
unsigned outputs under `work/rebuild/phone-packaging/`; alignment/signing remain
separate explicit stages. No code selects a timestamped evidence directory as a
hidden build input.

J834 retains `review-package-on-android.py`, explicit review selectors and
`review-proof-receipt.json` under the same private proof root. These are local
replay/evidence support, not game-build inputs. Editor launches now keep fresh
per-operation report directories containing their actual version/content oracle.

The app-sandbox probe stages public `tools/phone-build/host/` sources with
explicit owner SDK API 30 `android.jar`, build-tools 34.0.0 `d8.jar` and the
separately pinned Termux signer. `stage-host.py` under the same private proof
root copies inputs unchanged, binds hashes and invokes the tracked Android
driver inside the existing receipt-owned shell workspace. Its per-attempt
build outputs, encrypted disposable key and reports remain ignored. This is
required local replay support; no game build reads it.
`phone_host_check` generates private device results under
`work/experiments/phone-host/`; its ignored request binds the exact APK path/hash
and optional target SDK (30 by default or the authored 33 variant). The private
`stage-host-target33-v1.py` adapter binds the same supplied tools and current
committed sources, verifies the explicitly configured device/owned workspace,
fresh capacity and unchanged stopped game, and invokes the tracked driver with
target 33. Its separate selector preserves the original J836 attempts.

The positive native build-tool fixture stages public
`tools/phone-build/native-host/` sources with the same supplied SDK jars and
the already verified .NET 8.0.32, Roslyn, reference and native-dependency
inputs described in its README. These are required local tools, not public
repository contents. Private `build_on_alpha.py` and `install_on_alpha.py`
under `work/coordination/phone-proof/native-tool-host-r1/` bind source/tool
hashes, explicit device/workspace ownership, fresh capacity and the stopped
game; their versioned selectors preserve each failed and successful attempt.
The tracked builder generates each new APK and data/native hash manifest.
Reports, raw mapping paths, source stages, disposable signing material and
`proof-receipt-v1.json` stay under that ignored evidence root. No game build
reads these private adapters, their timestamped outputs or the fixture APK.

The connected fixture's public `tools/phone-build/managed-host/stage.py` stages
the fixed source cohort, supplied SDK jars and audited native/link metadata.
Its optional public producer checkout and three verified archive files remain
explicit local tool inputs. Private `run_shell.py`, `build_app.py` and
`install_app.py` under
`work/coordination/phone-proof/native-python-host-r1/` own Alpha-only research
coordination and versioned source/build/install/refusal selectors. These
adapters hash accepted legitimate Managed files before copying them separately
into the owned fixture data area; no game build reads them. The tracked builder
and entry point generate the APK, link/data manifests and transform outputs.
Input archives, disposable keys, raw process/mapping evidence, output DLLs and
proof receipts stay ignored. Caller configuration and every device path remain
local; no public tool embeds a timestamped experiment path.

The current integration replay uses the public stage generator and explicit
caller-owned tool-root, SDK/material/archive selection receipts under
`work/coordination/app-host-integration/`. These selectors are required local
orchestration state locating already acquired tools, not opaque game-production
inputs. Its private adapters reuse the existing build/install contracts, select
the assigned device explicitly and retain failed attempts. The public stage,
builder and producer generate every consumed source/data artifact; original
Managed input comes directly from the accepted installation. No current game
build reads those selectors. The signed fixture APK is transferred once because
the guarded SDK inspector/install-capacity interface requires a local file;
other APK intermediates and disposable signing material stay on the phone.

`phone_native.stage_action` generates `work/rebuild/phone-native/<attempt>/`
from an explicit authored fixture project/APK/hash request. It copies supplied
SDK/runtime source, the NDK target headers/libraries, generated C++ and its build
graph; all remain private owner inputs. The tracked generator emits relative
include wrappers, a structured plan, source hashes and a stage receipt. The
private `native-on-android.py` replay adapter under the phone proof root binds
the existing device/workspace receipt, checks capacity and stages those inputs;
its Android driver creates new output/log directories without editor mutation.
This is required local experimental replay support, not a game-build input.
`native-relink-on-android.py` takes an explicit prior attempt and new stage,
binds the old result and every compiled object hash, and invokes the tracked
reuse checks for a separate link-only attempt. The original failed output and
its 264 objects remain retained; no timestamp search selects a build input.
`phone_native_apk.stage_action` generates separate unsigned outputs under
`work/rebuild/phone-native-packaging/`. Its ignored request pins the authored
base APK, matching metadata and native library. `native-package-on-android.py`
and `native-package-driver.py` under the proof root are required local replay
support for phone-side native substitution, alignment and disposable signing;
they preserve private inputs/outputs and never feed a current game build.
The proof root's `native-fixture-request.json` explicitly selects the authored
project/base APK. The `native-stage-selection.json`,
`native-relink-stage-selection.json`, `native-run-selection.json` and
`native-relink-run-selection.json` receipts select exact generated stages and
owned outputs; they are required local replay state, not a newest-run search.
`native-elf-comparison.json` is the required pre-packaging verification input,
produced by pinned NDK readelf/nm plus the retained `native-inspect-on-host.py`
adapter. It binds metadata/native/base hashes and observed ELF/API comparisons.
`native-package-selection.json` and `native-package-check-request.json` bind
the phone signing outputs and explicit device test. Raw evidence and the final
`native-proof-receipt.json` remain private; none is read by the game build.

`phone_converter.stage_action` generates `work/rebuild/phone-converter/<attempt>/`
from the same explicit authored project/APK request. Supplied stripped fixture
assemblies, converter/corelib DLLs and icall data remain private inputs. The
generator records the full closure/argument plan and input manifest; its Android
driver creates new output and first-failure receipts. The proof root's
`full-converter-observation.json` records the original graph and assembly hashes;
`full-converter-stage-selection.json` selects one exact generated stage.
`full-converter-on-android.py` is required local replay support: it binds the
existing device/workspace receipt, checks capacity and tool hashes, stages the
inputs and collects outputs into a new attempt. `full-converter-run-selection.json`
selects that explicit attempt for independent comparison. The private
`full-converter-native-request.json` binds that result/stage to the original
fixture for native recompilation; the emitted C++ is copied without editing.
`full-converter-output-comparison.json` and
`full-converter-comment-classification.json` retain the original byte comparison
and narrow missing-source-comment classification. The private
`full-converter-native-on-android.py`, `full-converter-inspect-on-host.py` and
`full-converter-package-on-android.py` adapters select the resulting native stage,
verify ELF/API/dependencies and package/sign fresh fixture versions using the
unchanged authored native APK driver. Their named stage/run/comparison/package
selectors bind exact outputs; old J839 selectors/evidence are not overwritten.
None is a game-build
input; the original smaller converter attempts remain retained.

The proof root's `strip-converter-request.json` optionally binds the actual
phone stripping stage/output/result into `phone_converter.stage_action`.
`strip-converter-stage-selection.json` and `strip-converter-run-selection.json`
select that exact new converter attempt; no older selector is overwritten.
`strip-converter-native-handoff.json` records its validated downstream selector;
the desktop and J842 boundary comparisons are review evidence, not rewritten
source inputs. The final `strip-converter-proof-receipt.json` binds those results.
`strip-converter-on-android.py` is required local replay support for tool/workspace
ownership, fresh capacity, isolated execution and collection. It does not read
or modify installed game data beyond read-only APK hash observations.

`phone_roots.inspect_action` generates `work/experiments/phone-roots/<attempt>/`
from the same explicit authored project/APK/capture request. The request binds
SDK metadata and an exact-editor root oracle; these are private observation
inputs, not a redistributable root table. The authored metadata tool, supplied
Cecil, isolated .NET 10 compilation, before/after SDK hashes and pure coverage
comparison produce raw private reports and failure evidence. No inspected DLL
is executed. No current game build or phone builder consumes those reports.
`root-contract-selection.json` under the phone proof root selects the original
inventory and an immutable updated coverage comparison. Raw editor symbol views,
SDK native record observations and their comparisons remain local research
evidence, not a qualified root generator or build input. Their supplied editor
binary and SDK-derived rows must not be copied into public tooling. A later
decoder needs its own generator/contract before consuming those observations.

`work/experiments/phone-managed-metadata/<attempt>/` retains J866's explicit
SDK-only input manifests, schema-2 metadata, supplied-Cecil tool builds and
receipts. `wrapper-scoped-*-selection.json` selects the separate SDK layouts;
they are observation inputs, not a redistributable type mapping. The isolated
`.local/phone-build-metadata-net8/` reference packs come from pinned official
NuGet packages with catalog-hash receipts; its host-reference links support
SDK package-pruning data without changing the global SDK. The final tool build
is selected by `wrapper-net8-build-v4-selection.json`; earlier setup failures
stay preserved. `wrapper-phone-stage-selection.json` binds the copied public
reader/resolver, supplied SDK assemblies, input manifest and expected host
reports. No current game build reads these files.

`wrapper-metadata-on-android-v2.py` is private local orchestration for the
explicit alpha device, owned workspace, fresh capacity, committed sources,
tool/input hashes, inspection, negative controls and unchanged game/idle state.
`wrapper-phone-run-v2-selection.json` selects its final fresh child; the first
failed checker/run and overwrite investigation remain immutable. The public
metadata reader and standalone `phone_managed_types.py` generate the reports.
The `wrapper-resolution-observation*` adapters/reports additionally retain
private SDK search-sequence/cache observations and bounded oracle comparisons.
Those observations are unqualified research, never build inputs or public
constants. A later SDK decoder needs its own version-bound producer/contract.

`phone_wrapper_search.inspect_action` generates
`work/experiments/phone-wrapper-search/<attempt>/` from an explicit pinned
owner-binary request. The unchanged private SDK, authored search/registry/
literal readers, input hashes, `search.json` and result/log files form the
attempt. This report reads SDK bytes directly; it consumes no earlier search
observation, captured root row or game file. The SDK and resulting literals
stay private. A phone replay may select an existing hash-verified owner-SDK
copy through its explicit owned-workspace receipt, stage fresh authored readers
and write new outputs; no timestamped SDK path is embedded in source. Complete
wrapper-cache and scene-root inputs remain unsupported.
`wrapper-search-on-android.py` and its explicit stage/run selectors retain J869's
fresh owned child, copied committed sources/controls, existing read-only SDK
receipt selection, fresh capacity, tool/input hashes and refusal results.
`wrapper-search-zero-register-*` preserves the first source's synthetic
origin-proof failure and corrected controls. The later
`wrapper-resolution-observation-v3*` uses the decoded phone search report with
explicit prior inventory/registry/oracle selectors for comparison only; cache
population remains unqualified. The versioned proof binds those prerequisite
inputs and retains the earlier core-only receipt.

Current population investigation retains explicit `wrapper-population-*`
observations under `work/coordination/phone-proof`: bounded owner-SDK inspection,
prototype output and first failures. These are private experiment evidence, not
build inputs. `phone_wrapper_population_oracle.py` generates fresh
`work/rebuild/phone-wrapper-oracle/population-<owned-attempt>/` SDK-only projects,
inputs, logs, reports and receipts from committed authored sources. The explicit
attempt receipt selects comparison data; no consumer embeds a timestamped path.
`wrapper-population-on-android.py` and explicit source-stage/run selections bind
committed readers and select existing J864 owner-SDK and J866 phone-generated
scoped inventory/assembly workspaces by receipt and hash. They are operator
qualification state, not inputs to a game build. Fresh child directories,
storage reserves, tool hashes, refusal controls and the unchanged APK receipt
remain local with their outputs; no SDK binary or assembly is republished.

The population oracle's optional `--reverse` mode generates its private
`layout.json` from the pinned SDK through `phone_wrapper_reverse.py` in the
same fresh attempt. No saved layout or mapping is a required local input.
The explicit attempt receipt selects native observations for comparison only;
the build reads no timestamped observation path. The supplied SDK's already
loaded native Mono library is hash-bound; it is not copied or redistributed.
Private `wrapper-reverse-*` selectors, SDK observations, controls and comparison
reports remain operator evidence under `work/coordination/phone-proof/`.
The root-inclusive replay uses a separate
`wrapper-population-root-on-android.py`, new source-stage/run selections and
fresh owned children, retaining J878's original source/results. It reuses only
the receipt-bound SDK and complete managed metadata inputs read-only. Neither
that adapter nor a native oracle report is a game-build input.

`phone_scene_usage_oracle.py ROOT WORK EXACT_EDITOR` generates fresh
`work/rebuild/phone-wrapper-oracle/scene-<owned-attempt>/` SDK-only projects,
`inputs.json`, player-script outputs, `oracle.json`, logs and a terminal receipt.
The authored scene and all compiled/type-database observations are local SDK
verification outputs. Sources and project configuration are generated by the
tracked runner and collector; no historical scene, captured linker input,
game file or saved dependency list is required. Select an attempt through its
explicit terminal receipt. These reports are comparison evidence only, with
root generation unqualified; no game or phone build reads them. Failed attempts
remain available, including a failing phase if the collector emitted a report.

`phone_manager_context.py OWNER_SDK_BINARY NEW_PRIVATE_REPORT` generates static
manager registration declarations directly from the pinned owner SDK. No saved
context-name table, native usage list, scene or oracle report is an input.
Private `manager-context-*` and `manager-family-*` selectors, comparisons and
qualification logs under `work/coordination/phone-proof/` are investigation
evidence only. They supply no game-build input. Context indices describe
declarations; live state and target/object retention remain separate gates.

`phone_manager_retention.py OWNER_SDK_BINARY NEW_PRIVATE_REPORT` generates
static write-method bindings from the same owner SDK and authored siblings.
It reads no captured vtable, disassembly, manager/scene list or oracle report.
Private `manager-retention-*` source stages, host observations and controls under
the same proof root are retained investigation evidence. The local
`stage-manager-retention-v1.py` and `manager-retention-on-android-v1.py` adapters
copy committed sources unchanged and reuse the receipt/hash-bound SDK/Python
workspace with explicit Alpha selection, fresh capacity and unchanged-game
guards. No SDK code, editor or player executes; no game-build input is generated.

`phone_platform_features.py OWNER_SDK NEW_PRIVATE_REPORT` generates the Android
declaration report directly from the same hash-pinned owner SDK. The private
`target-support-*` observations, source snapshots and failures under the phone
proof directory are research evidence, never captured inputs to this reader.
No SDK token table or disassembly is published. The separate
`phone_platform_feature_oracle.py ROOT WORK EXACT_EDITOR` generates
`work/rebuild/phone-wrapper-oracle/feature-<attempt>/` with its fresh project,
reader-derived query names, source/input receipts, SDK API observations and logs.
Its tracked generators own every staged input. The report is desktop comparison
evidence only; no phone or game build consumes it.
The local `stage-target-support-v1.py` and
`target-support-on-android-v1.py` adapters under the private proof root copy
committed reader/test sources unchanged into a fresh owned Alpha workspace.
They reuse receipt/hash-bound SDK and Python bytes, compare the independently
generated host report locally, and enforce explicit device selection, fresh
capacity and unchanged-game checks. Neither adapter accepts optimized Python;
SDK oracle answers are never staged to Android.

`phone_target_keys.py OWNER_SDK NEW_PRIVATE_REPORT` generates static target-key
input bindings from the pinned SDK and authored sibling readers. Its private
`target-discovery-*` prototypes, failed controls, source observations and reports
under the phone proof root are investigation evidence. The tracked reader does
not consume them. No SDK target table, instruction listing, generated game data
or private API observation is a production input; constructor results, map
population and target support remain unqualified.
`phone_target_records.py OWNER_SDK NEW_PRIVATE_REPORT` generates a separate
static record-copy/insertion/consumer alignment report from the pinned SDK.
Private `target-record-*` disassemblies, prototypes, source stages and mutation
controls under the phone proof root are investigation evidence only; the tracked
reader does not read them. Its positive field alignment is not node selection,
constructed strings, populated containers or target/module availability. Raw
SDK observations remain ignored and are never redistributed as phone inputs.
Private `stage-target-record-v1.py` and `target-record-on-android-v1.py` adapters
stage the committed sources in their repository layout, select Alpha explicitly,
revalidate the existing owned SDK/Python workspace, query fresh capacity/backing
and preserve game hashes/idle state. Both refuse optimized Python before device
access. The host report is comparison evidence only; the Android reader derives
its own report from the supplied SDK bytes.

`phone_target_key_oracle.py ROOT WORK EXACT_EDITOR` generates fresh
`work/rebuild/phone-wrapper-oracle/target-<attempt>/` projects and private
metadata/query/source receipts, SDK observations, exact comparisons and logs.
The tracked Python/C# generators own every staged input. Queries contain no
expected mapping; a completed observation is not necessarily an equivalent
mapping. These SDK answers remain comparison evidence only.
The private `stage-target-discovery-v1.py` and
`target-discovery-on-android-v1.py` adapters preserve the committed
`scripts/lab/` and `tests/` layout in a fresh owned Alpha workspace. They reuse
receipt/hash-bound SDK and Python bytes, refuse optimized Python before device
access, and enforce explicit device selection, fresh capacity and unchanged-game
guards. No SDK API observation is staged to the phone.

`phone_managed_compile.py stage ROOT OWNER_SDK_CONTENTS WORK` generates a fresh
`work/rebuild/phone-managed-compile/<owned-attempt>/` from the exact supplied SDK
and tracked arithmetic fixture. Its manifest binds the original compiler/config,
license, target core library, authored source and portable runner. The explicit
run uses the SDK's existing .NET 6.0.21 host or the separately qualified Android
.NET 8.0.32 tool host retained in the owned phone workspace. Compiler inputs,
DLL/PDB outputs and raw logs stay private; the SDK runtime configuration is not
rewritten. Failed stages are retained, and no game build reads an observation
or timestamped run path. This fixture does not supply general player compilation
or the SDK's native TypeDB.

`phone_unity_compile.py stage ROOT OWNER_SDK_CONTENTS WORK` generates a separate
`work/rebuild/phone-managed-compile/unity-<owned-attempt>/` with compiler inputs,
the public Unity fixture, builtin package/module metadata and the complete
hash-pinned SDK reference inventory. The phone derives its selected references;
no captured response or precompiled player is staged. The `sdk` or `android`
run creates one private `output/` with `references.json`, implementation and
reference assemblies, portable debug data and checked child/result logs.
The original compiler configuration remains unchanged. Explicit selections,
SDK-only inventory comparisons, failed attempts and device controls live under
`work/coordination/phone-proof/managed-unity-*`. They are investigation evidence,
never game-build inputs or redistribution permission for SDK reference bytes.

`phone_compiled_linker.py stage ROOT TEMPLATE COMPILER_STAGE COMPILER_OUTPUT WORK`
generates a fresh `work/rebuild/phone-managed-compile/linker-<owned-attempt>/`.
Its explicit template is the qualified authored SDK-root/module-policy stripping
stage, reproducible through the existing `phone_linker` fixture capture/staging
workflow; this restricted experiment refuses other template identities. The
compiler selections are generated by `phone_unity_compile.py` and checked
against the qualified fixed-source/profile fingerprints and Android outputs.
The generator copies the template unchanged except the new fixture DLL/PDB,
retains the original manifest and adds compiler/source/reference provenance.
`run STAGE OWNED_TOOL_ROOT NEW_SIBLING_OUTPUT` creates a uniquely prefixed sibling
output with the linker's original `result.json` and a separate checked
`handoff-result.json`. It never changes an accepted stage or replay receipt.
Explicit selections, source comparisons, controls and failed attempts live under
`work/coordination/phone-proof/compiled-linker-*`; these support the experiment,
not a game build. Desktop scene/editor roots remain private required inputs.

`phone_compiled_converter.py stage ROOT CONVERTER_TEMPLATE LINKER_STAGE
LINKER_OUTPUT WORK` generates a fresh
`work/rebuild/phone-managed-compile/converter-<owned-attempt>/`. The converter
template is the pinned authored module-policy converter stage from the existing
`phone_converter` workflow. The supplier stage/output are generated by
`phone_compiled_linker.py`, with every upstream input and raw result retained
and checked. Actual stripped bytes replace only the corresponding template
files; the original converter plan and SDK inputs stay unchanged. `run STAGE
OWNED_TOOL_ROOT NEW_SIBLING_OUTPUT` writes original converter outputs/result and
a separate checked handoff result. No game build consumes these files. Explicit
selections, controls, failures and comparisons remain investigation evidence
under `work/coordination/phone-proof/compiled-converter-*`; no runtime reads a
timestamped investigation directory.

`phone_compiled_native.py stage ROOT QUALIFIED_NATIVE_TEMPLATE FIXTURE_REQUEST
CONVERTER_STAGE CONVERTER_OUTPUT EDITOR ANDROID WORK` generates
`work/rebuild/phone-managed-compile/native-<owned-attempt>/`. The qualified
historical native template supplies only the SDK/target hash inventory; its
older fixture APK and graph are not substituted. The explicit authored fixture
request selects the same exact APK/project as the compiled converter profile.
The existing native stage builder captures its matching graph and copies actual
converter C++; generated metadata/resources must equal the selected APK entries.
The generator retains the original captured plan/manifest and annotates only
generated scope metadata. SDK/player/source copies, full upstream proof and raw
results stay ignored. `run STAGE OWNED_TOOL_ROOT NEW_SIBLING_OUTPUT
[REUSE_REQUEST]` runs the pinned native driver; an optional reuse request still
requires its existing complete object/source/argument checks. `library_input`
accepts explicit stage/output/handoff-result hash selections. No game build
reads these experiment files; explicit selections, SDK inventory comparisons,
failures and device controls live under
`work/coordination/phone-proof/compiled-native-*`.

`phone_registry.inspect_action` generates
`work/experiments/phone-registry/<attempt>/` from an explicit JSON request with
one absolute `binary` path. Only the pinned supplied Unity SDK executable is
accepted. `reader.py`, `phone_registry_literals.py`, the unchanged `owner-sdk`,
their `inputs.json` hashes,
`registry.json`, `host.log` and `result.json` form an isolated metadata attempt.
This SDK binary and its extracted records are protected local inputs/outputs;
they cannot be redistributed with the authored reader. The reader consumes no
earlier symbol dumps, captured native table, oracle or game file. A local device
replay may copy this explicit stage into a fresh owned workspace child, verify
all hashes, run the reader with supplied Android Python and collect its result.
The retained `native-registry-on-android.py` under the phone proof root is
required local orchestration for selected-device ownership, fresh capacity,
tool/input verification and read-only game hash observations. No current game
build consumes these records or receives independent project roots from them.
The later `native-registry-extra-on-android.py` retains those device boundaries
and additionally verifies the literal-helper source is committed/unchanged.
Earlier adapters and their hash-bound receipts remain immutable evidence.
`scene-root-ids-*` selects the later persistent-ID investigation, including its
preserved failed host stages and final source-bound stage/run selections.
`scene-root-ids-on-android.py` is local replay support with the same explicit
device/workspace, committed-source, fresh capacity, tool/input hash, refusal
control and idle-display boundaries. It generates no scene roots or game input.

The public scaffold and its generators are described in
[tools/phone-build](../tools/phone-build/README.md). No current game build reads
these support paths, and no compiler/editor redistribution grant is inferred.

Accepted-output replay requires explicit private state, not a captured timestamped
folder inferred by public code: an owner-input root and accepted input manifest;
a target manifest plus private compressed frames produced from that owner's
accepted APK/payload; permitted exact Unity SDK copy inputs; supplied Android
Python; and the source-built Zstandard codec. The public `tools/phone-build/accepted-output/package.py` reproduces a packet
from those explicit target/profile inputs and emits its verified wire stream.
The original local encoder/relay and hash-bound selections under
`work/coordination/accepted-build-reconstruction/` remain provenance and device
orchestration; profile selection/planning is still required private state. Their raw target information, original files, SDKs and outputs stay
ignored. The public receiver accepts explicit argument roots and a pinned stream,
never a timestamped run path. Process/result receipts and successful/failed
outputs are retained local evidence; no current game build reads them. See
[setup/lifecycle](../tools/phone-build/accepted-output/README.md) and J1042.

An owner-downloaded exact Unity Android support component is an alternative
explicit SDK-copy input source. Public `sdk_inputs.py` validates it and generates
a new SDK-root layout plus complete/failed receipt; original packages, outputs
and failed attempts remain private. This does not source the full compiler or
introduce a timestamped build dependency. See the
[acquisition lifecycle](../tools/phone-build/accepted-output/README.md#acquire-the-three-sdk-copy-inputs).

Independent mesh production instead reads only the original PC root and tracked
`recipe/owner-meshes.json`, through public `mesh_produce.py`; it requires no
private target/discovery snapshot. Private packs, complete/failed receipts and
raw verification evidence stay under explicitly selected ignored output roots.
The accepted target is an independent local verification oracle, not a producer
input. Android lab staging additionally requires the existing explicit-device
workspace ownership receipt and permitted Python interpreter. No timestamped
run path is embedded in the producer or a current build; see its
[setup/lifecycle](../tools/phone-build/accepted-output/README.md#produce-meshes-directly-from-original-pc-bundles).

The independent Avatar producer likewise reads only original PC files plus
tracked `recipe/owner-avatars.json`. Its private `objects.bin`, `index.jsonl`
and complete/failed receipt are generated by public `avatar_produce.py` in a
caller-selected new output root. No discovery snapshot, captured target body,
SDK or timestamped run is a producer/build input. The same explicit Android
workspace/interpreter ownership applies; see its
[setup/lifecycle](../tools/phone-build/accepted-output/README.md#produce-avatars-directly-from-original-pc-bundles).

The independent uncompressed texture entry reads only original PC files and
tracked `recipe/owner-uncompressed-textures.json`, through public
`texture_produce.py`. It generates private object/resource packs, index and
complete/failed receipt in a new caller-selected output root. No captured
pixel, discovery snapshot, Unity SDK or timestamped run is a producer input.
JPEG operations additionally require an explicit public native tool and its
SHA-256. `build_texture_jpeg.py` generates that tool in a new private output
from separately supplied pinned public IJG/stb source providers and an explicit
compiler, preserving source/notices/logs and a terminal build receipt. Its
Android Clang policy selects the existing owned public tool root; source
providers and tool outputs stay private local material, reproducible from the
documented public inputs. Explicit Android workspace/interpreter ownership remains required for
lab staging. See its
[setup/lifecycle](../tools/phone-build/accepted-output/README.md#produce-uncompressed-textures-directly-from-original-pc-bundles).

The experimental standalone SDK runner requires separately acquired, unchanged
public Box64 source and the owner's pinned SDK NDK, plus explicit host CMake/
LLVM archive tools. `build_sdk_runner.py` generates its private binary, license,
logs and receipt. Standalone Linux SDK libraries are required local providers,
not generated game data: select them from the hash-pinned official archive
listed in the [setup](../tools/phone-build/accepted-output/README.md#build-the-standalone-sdk-tool-runner).
The authored `sdk_texture_codec.c` adapter is built with the SDK's Android x86
compiler target. Its diagnostic additionally needs the public Debian libgcc
runtime listed there. Paths are explicit arguments; no build reads a timestamped
run folder. SDK binaries, original-source pixels, diagnostic output and device
receipts remain ignored. J1081 records the shell-only controls and remaining
RGBA equivalence failure.

The owner-APK bootstrap candidate consumes an explicit ignored request selecting
the accepted private packet manifest and verified reconstructed target root,
public frontend/wire-helper sources and supplied Java/Android/D8 tools.
Optional `version_code` is owner-selected revision configuration, not generated
game input; it selects an increasing package version while retaining the same
private signing identity. Omission retains the frozen input version.
`tools/phone-build/owner-apk/build_owner_apk.py` generates the authored DEX,
patched binary manifest, embedded payload index, unsigned owner APK and private
source/tool/hash result. These are reproducible post-reconstruction outputs,
not new original-game input producers. The device activity generates its own
private completion receipt and app-owned payload stage/backup directories;
failed stages remain evidence and no other app's files are used for output.
No current game build reads a timestamped owner-APK run directory. See the
[candidate lifecycle and gates](../tools/phone-build/owner-apk/README.md).

> **Dated snapshot.** This is a static audit taken on 2026-10-16. Line numbers drift as code
> changes; regenerate or re-audit it before relying on a specific `file:line`. The current
> map is [ARCHITECTURE.md](ARCHITECTURE.md).

Static audit of `scripts/`, `tools/` and `android/`, 2026-10-16. **Seven path families (eight before J508) with no snapshot/recipe producer are reached by the current workflow**, including one conditional proof. They are the first table. This is an inventory, not a fresh-build or game-readiness acceptance.

Only existence was checked in the workstation's `work/`; no file contents were read and nothing was modified. Paths below are logical `work/` paths, not private workstation locations. No builds, installs, runs or read traces were executed.

`<timestamp>` generalizes run timestamps; `<key>`, `<asset>`, `<attempt>`, `<composition-evidence>`, `<previous_project>` and other angle-bracket names denote path families or selector fields. Presence **yes** means the exact literal exists, or at least one matching family member exists; it does not validate contents, hashes, completeness or a pointer target. **†** means a matching candidate exists (or was searched for), but the actual selected target is **unclear** because opening the selector was prohibited. In particular, migration analysis/preview candidates were found under `work/experiments/input-migration/<composition>/`, and a prior project under `work/migrations/<input>/lab-project/`.

Readers are direct read/hash/enumeration sites, not every caller of a shared helper; counts deduplicate `file:line` sites. Output-only families say so. Producer references identify writes or the external tool invocation responsible for the output. A generic JSON writer, merge function or arbitrary editor-code executor is not a generator for an unrecorded recipe. “None found” is limited to the audited tracked source; it says nothing about ignored helper scripts.

Classes use the requested categories: **user input**, **generated by repo code**, **required local state with no producer**, **historical evidence/receipt**, and **cache**. A generated label establishes a write site, not an end-to-end reproducible current generation. Historical receipts retain their class even when used as provenance. Cache classification does not authorize deletion.

J659 extends the existing accepted `work/decompiled/RoR2/<cache-key>/**` reader:
whole-catalog audit, reconciliation and root repair inspect class-scoped field
types and inheritance to discover EntityStateGameObject dependencies. The same
recovery producer and input-hash selection supply this source; no additional
timestamped evidence folder becomes a build prerequisite. Generated edges live
in the existing closure receipt and feed ordinary integration staging.

## Inherited additions ledger (J558)

[recipe/inherited-state.json](../recipe/inherited-state.json) inventories the 229
composition additions: 192 shaders and 37 other files. It records previous-project
asset and importer hashes/GUIDs, current project paths/hashes, generator functions
and inputs, comparison basis, and current-use evidence. It contains identifiers
and hashes, never shader programs or serialized asset bodies.

Current status is **40 reproducible / 189 inherited / 0 retired** (J563).
`reproducible` means a host generator reproduces the complete pair under its
recorded comparison basis: 15 authored additions, 9 native shaders, 14 decks and
2 non-shader additions. Deck hashes use the normalized migration-stage basis;
the ledger's original inherited body hashes remain provenance. Among the 177
native generator-backed shaders, 9 pairs reproduce, 166 bodies differ and 2 have
no current selected output. Matching bodies alone do not change status. Retire
state only after device verification, per J558.

Usage is a static identity-level census: 224 used, 5 unused, 0 unclear (shaders:
190 used, 2 unused). `used` means reachable through the current content recipe's
bundle roots and serialized GUID closure, runtime resource/shader calls in the
staged source selection, native-manifest resource entries, or literal shader
includes. Each positive entry records a root/call site and reference chain.
This includes conditional/fallback calls; it does not assert a rendered draw.
`unused` means no reference in this scope, not permission to delete. Three unused
font includes and two absent older SpeedTree variants remain inherited.

The native manifests and shader bodies can differ from their inherited versions:
composition stages current selected outputs over inherited files. `current_sha256`
and `current_meta_sha256` record that distinction; null means absent. Thus use of
a shader name does not imply use of the inherited bytes. The snapshot uses current
project materials and manifests, not the previous project's reference graph.

Current read-only check: `./dev prototype --action inherited-state-check`.
A separate clone can select its authorized local tree with `--work-dir PATH`.
It gates acceptance, checks all 189 inherited pairs in the named store below,
and regenerates the shader/export/package cohorts in scratch against ledger
hashes. Missing files, hash drift or GUID mismatches fail; no project files,
selection, receipt or cache are written. Reproducible/retired entries do not
require historical copies. Status, usage and cross-tabulated counts are reported;
usage evidence remains a reviewed census, not recomputed by the integrity check.
Review it after changing content, manifests or runtime loads.

## Owner assembly prefix (current)

The separate current [owner assembly prefix](OWNER_ASSEMBLIES.md) needs only the
reviewed local input configuration, accepted-input receipt and inventory, plus
the documented toolchain. `owner_assemblies.py` generates its new
`work/rebuild/<chosen-prefix>/project/`, manifest and receipt;
`assembly_transforms.generate` generates the adjacent `attempt/` copies, tool
sources, restore configuration and transformed DLLs. These game-derived outputs
stay ignored. No existing build reads this prefix, and no private provenance map
or previous project is an input to this action.

The opt-in public profile additionally requires an explicit read-only archive
cache (`--tool-archives`) containing the three filenames/bytes pinned in
`recipe/owner-public-tools.json`. A stable ignored location is
`work/toolchains/owner-public-dotnet8/archives/`; it is required local state
because the command does not download tools or run a package manager. Download
the recipe's public URLs and retain exact versions; the generator validates
archive/member/source hashes and preserves notices. An existing native dotnet
launcher and Python environment are also required, not generated by this stage.
`public_transform_tools.generate` generates extracted materials, source copies,
compiled provider/tool, logs and its receipt under the new `attempt/`. No code
reads a historical run folder as a dependency. Public binary inputs and all
game-derived outputs remain ignored; only source/metadata/notices are tracked.

## Named inherited store (current)

`work/inherited-store/<input_id>/Assets/LabLoadingScene/**` is the **one required
local store for inherited addition bytes**. Its producer is the current
`./dev prototype --action inherited-store-capture` (`inherited_state.capture`).
Run it before the next composition stage. It reads the selected rollback only
for capture and copies exactly the ledger's 189 `inherited` asset/importer pairs
(378 files), with their original relative paths. The 40 reproducible entries are
excluded. Every body hash, importer hash and importer GUID must match the ledger;
all inputs are validated before publishing a temporary store by directory rename.
An existing store must have exactly the expected membership and matching bytes;
it is never repaired or overwritten on drift. A failed capture leaves no partial
published store. No private paths or game content are added to tracked files.
The ledger's `source` field remains capture provenance, not a staging location.

`inherited_state.prepare` reads and verifies that store before project writes.
`composition_migration.plan_additions` combines it with the five existing generator
owners, rejects omissions, duplicates and overlapping owners, and retains the
existing YAML GUID/UI normalization for inherited bodies. Importers are copied
byte for byte. Shader-source and native-texture replacement steps still run
later in their existing order. `inherited-state-check` checks store hashes/GUIDs
and compares regenerated shader/export/package pairs against the ledger, without
reading historical copies. Its `--work-dir` remains read-only. Capture intentionally
has no alternate-work-root option. Retain the store until device-verified
replacements justify changing the ledger; this change retires no entries.

### Composition read inventory and remaining blockers

Read-only re-audit against J563 and the locally selected inputs; no builds, device
commands or staging ran. This supersedes the B1/B3–B8 reachability claims below.
The store is the sole inherited-addition store, **not** the sole prerequisite for
the entire migration coordinator. Full denied-history staging remains blocked by
the reads explicitly retained here; substituting the current build recipes would
not establish identical migration-stage bytes.

| Read | Current classification / disposition |
| --- | --- |
| B1 `config/composition-migration.json` | Still read by both actions: accepted-input identity, evidence output location; stage also uses source-path overrides, removed-state selectors, shader-source selections and native textures. No byte-equivalent replacement for the entire selection contract. `previous_project` is now used only for the config below (and capture); the separate rollback safety check remains. |
| B3 `semantic-preview-result.json` | Retained: 222 rows provide source/output hashes, conflicts and allowed pre-stage target hashes. All 222 have recipe generators, but the recipe does not contain output or allowed prior-target hashes. Removing this validation would weaken drift refusal. |
| B4 `asset-analysis.json` | Retained: 33,016 identity rows, 32,626 with old-source associations, construct old-to-current path mappings, absent-input reporting, addition selection and GUID-owner placement. The ledger covers only the 229 additions, not this mapping census. |
| B5 `rebase-analysis.json` | Retained: 53,683 GUID translations normalize inherited YAML and construct current asset mappings. The asset analysis has only 33,016 distinct old GUIDs; it is not a complete replacement. No new GUID map is published or inferred. |
| B6 `removed-state-types.json` | Retained conditionally: the four selected removed bindings require exact original assembly hash and TypeDef-absence evidence. No equivalent current absence-proof producer is wired into composition. |
| B7 `preview/<asset>` | Removed from the current path: all 222 adaptation targets must have recipe owners before writes. There is no current preview-copy fallback. `prepare_asset_transforms` retains its historical fallback contract for independent callers, unreachable from current `stage`. |
| B8 previous adapted asset bodies | Unused by current stage: the same full-coverage guard makes the old adapted-hash fallback unreachable. Export hashes, plan output hashes and current-target checks remain. |
| B8 previous addition bodies/importers | Removed from current stage: 15 authored shader/include pairs, 9 generated shader pairs, 14 export-derived decks, WarpRamp and TMP properties include use generators; the other 189 pairs use the named store. Inherited kinds: 169 shaders, 7 materials, 3 prefabs, 1 texture, 1 ScriptableObject and 8 other files. No unclassified addition is allowed. |
| B8 previous `Resources/MovementBatchProbe.json` | **Retained blocker:** recursive retargeting reads all 366 old keys. The public runtime recipe has 183 keys, with 186 old-only keys and 109 unequal shared values before retargeting. It supersedes the config at the later whole-catalog build entry, not at this intermediate stage. No byte-equivalent intermediate constructor is available. |
| Evidence dependency subdirectory | `stage_missing_sources` only creates outputs here; it reads no B3–B8 content and no previous project. It still needs B1 for identity/output selection, current staged configs and the export/GUID index. |
| Other evidence access | Stage writes diagnostics, scene contracts, script orders, input mapping, attempt and staging receipts; its final `staging-result.json` read is readback of its own output, not inherited input. |

Outside B1/B3–B8, stage still reads the current project/generation marker and
metadata owners, acceptance, reconstruction/export, catalog GUID index, UI recipe,
existing content config, selected shader sources plus receipts, exported textures
and existing target importers, legitimate assembly/native metadata, and authored
presentation source. The old scene-runtime pointer → input mapping → hashed
observation chain also remains: it has no named replacement receipt yet.
`stage_missing_sources` reads current project metadata, both staged configs,
export closure and UI remaps, then runs support-source repair and optional-content
sanitization. None of those reads is an additional inherited addition.

The synthetic denied-history test covers the **addition planner**, store integrity
and normalized staged bytes. Existing transform fixtures cover adaptation generation
with absent history. It does not claim a successful full `stage` with B3–B6 or the
previous config absent. Those reads are intentionally stopped at their unresolved
contracts under the requested byte-preservation constraint. The older blocker table below remains historical audit context.

## Reachability and pointer chains

The current command set is the ten prototype actions in [Reusable fixes and commands](whole-catalog-integration.md#reusable-fixes-and-commands), plus `./dev preflight`, `build`, `install`, `run`, and `test`. “Yes” means a statically reachable read, existence/hash check, enumeration or output after earlier prerequisites pass; it does not claim successful execution on this clone. Conditional reads are marked. “No” means only another dispatched action or standalone utility uses it. Dynamic selection is called unclear where source cannot resolve it.

- `scripts/lab/main.py:28–33` dispatches composition stage/dependencies to `composition_migration.stage` / `stage_missing_sources`. Stage calls dependencies itself (`composition_migration.py:347`), but neither regenerates the initial rebase plan or selected rollback snapshot.
- `main.py:46–74` dispatches contracts/prepare/host/providers/repair/build/code-build/run directly to `whole_catalog.py`. The reusable list does **not** invoke `whole-catalog-audit`, `whole-catalog-native`, `whole-catalog-reconcile`, `inspect`, `decompile`, `export-project` or utility `prototype` preparation. Those producers exist but are separate prerequisites.
- `main.py:488–505` dispatches preflight/build/install/run to `build.py` / `Device`. Build calls preflight and the isolated editor, not composition migration. Install reads current-build; direct run calls `Device.launch`, not `scene_runtime.movement_batch_run`. `whole_catalog.run_integration` calls preflight/install/launch/sync and its catalog scan; it also does not call movement-batch-run.
- `main.py:11` runs host unittest discovery. Most state is mocked or temporary; the assembly fixture can create clone-local `work/tests` (`tests/test_assembly_slice.py:15`). No pre-existing game receipt is required by test dispatch. No source changes or optional trace were added here, so the suite was not run for this documentation-only change.
- `config/reconstruction.json → projects[0] → exported Assets/Packages/ProjectSettings`; `config/current-build.json → apk`; `whole-catalog-build.json → manifest`; `whole-catalog-code-base.json → frozen file/payload hashes`. These are dependencies, not self-bootstrapping recipes.
- `experiments/whole-catalog/latest.json → <timestamp>/`: `native-latest.json → native-<timestamp>`, `contracts-latest.json → runtime-contracts-<timestamp>`, and `integration-latest.json → integration-<timestamp>/{manifest,host-integration,host-provider-result,build}.json`. Integration `device-latest.json → device-<timestamp>` is written as evidence but not followed by the current commands. Optional `catalog-metadata.json → filename` changes the catalog read; otherwise `source-catalog.json` is used (`whole_catalog.py:33–41`).
- `config/composition-migration.json → evidence / previous_project / shader_sources`; stage also follows `experiments/scene-runtime/current.json → old attempt/nova-input-mapping.json → observation`, then replaces current.json with its new evidence path. Other `latest/current/active` chains are in the historical tables; their presence alone does not make them current inputs.

## Fresh-rebuild blockers reached by the current workflow

Since J597 these are reached only by the working project's own composition actions
(`composition_migration.migration_inputs`). The from-scratch rebuild's R2 takes the same
fields from public recipes (`composition_rebuild.recipe_inputs`) and reads none of them,
nor `work/scene-probe-build.json`, `experiments/scene-runtime/current.json` or the live
whole-catalog pointer. Commit 9 of the migration-removal plan retires them for the
working project too.

| Path / family | Readers (file:line) | Producer in repo | Class | Current workflow reaches it | Present |
| --- | --- | --- | --- | --- | --- |
| `B1: work/config/composition-migration.json` | `scripts/lab/composition_migration.py:129`; `scripts/lab/composition_migration.py:184` | none found | required local state with no producer | yes — both composition actions | yes |
| `B2: recipe/hud-ui-remaps.json` (was `work/config/`) | **Resolved 2026-10-17 (J508):** tracked as an audited recipe; see [recipe/README.md](../recipe/README.md) | — | tracked recipe | yes | yes |
| `B3: work/<composition-evidence>/semantic-preview-result.json` | `scripts/lab/composition_migration.py:194` | none found | required local state with no producer | yes — composition stage | yes † |
| `B4: work/<composition-evidence>/asset-analysis.json` | `scripts/lab/composition_migration.py:210` | none found | required local state with no producer | yes — composition stage | yes † |
| `B5: work/<composition-evidence>/rebase-analysis.json` | `scripts/lab/composition_migration.py:212` | none found | required local state with no producer | yes — composition stage | yes † |
| `B6: work/<composition-evidence>/removed-state-types.json` | `scripts/lab/composition_migration.py:215` | none found | required local state with no producer | yes — composition stage if `removed_state_configs` is nonempty | yes † |
| `B7: work/<composition-evidence>/preview/<asset>` | `scripts/lab/composition_migration.py:286`; `scripts/lab/composition_migration.py:303` | none found; `serialization_rebase.py` returns merged text but has no preview/plan writer | required local state with no producer | yes — composition stage | yes † |
| `B8: work/<previous_project>/Assets/** (especially LabLoadingScene/Resources/MovementBatchProbe.json and adapted asset/meta pairs)` | `scripts/lab/composition_migration.py:264`; `scripts/lab/composition_migration.py:286`; `scripts/lab/composition_migration.py:296`; `scripts/lab/composition_migration.py:298` | none found for the selected rollback snapshot; generic live config writes exist at `scripts/lab/scene_runtime.py:586` and `scripts/lab/nova_bridge.py:120` | required local state with no producer | yes — composition stage | yes † |

## Current configuration, project and catalog dependencies

| Path / family | Readers (file:line) | Producer in repo | Class | Current workflow reaches it | Present |
| --- | --- | --- | --- | --- | --- |
| `work/config/local.json` | `scripts/lab/common.py:10`; `scripts/doctor.py:32`; `tools/unity/runtime/presentation/RecoveredHudBuilder.cs:20` | none found; operator supplies `environment/lab-config.example.json` values | user input | yes — preflight/build/install/run and composition | yes |
| `work/config/accepted-input.json` | `scripts/lab/input_migration.py:68`; `scripts/lab/input_migration.py:104`; `scripts/lab/build.py:37`; `scripts/lab/shader_source.py:120`; +19 more | none found; explicit operator acceptance | user input | yes — preflight and catalog generation | yes |
| `work/config/reconstruction.json` | `scripts/lab/build.py:55`; `scripts/lab/integrated_moon.py:13`; `scripts/lab/recovery.py:71`; `scripts/lab/scene_closure.py:10`; +35 more | `scripts/lab/recovery.py:41`, `:65` | generated by repo code | yes — composition and catalog | yes |
| `work/inventory/files.json` | `scripts/lab/input_migration.py:69`; `scripts/lab/input_migration.py:71`; `scripts/lab/input_migration.py:104`; `scripts/lab/build.py:35`; +45 more | `scripts/lab/inventory.py:26` | generated by repo code | yes — preflight and catalog | yes |
| `work/inventory/{managed.json,managed-stamp.json,managed-previous.json,native.json,seams.json,summary.json,input-diff.json,surface-diff.json,history/<input-id>.json}` | `scripts/lab/inventory.py:30`; `scripts/lab/inventory.py:35`; `scripts/lab/health.py:13`; `scripts/lab/input_migration.py:94`; +3 more | `scripts/lab/inventory.py:25`, `:28`, `:35`, `:38`, `:51`, `:56`, `:58` | generated by repo code | no — inspect/doctor/migration/older actions only | yes |
| `work/lab-project/.port-input.json` | `scripts/lab/build.py:31`; `scripts/lab/composition_migration.py:28`; `scripts/lab/composition_migration.py:132`; `scripts/lab/composition_migration.py:190`; +5 more | `scripts/lab/prepare.py:38` (utility schema only); `scripts/lab/source_scene_candidate.py:73`, `:88` update existing metadata | generated by repo code | yes — preflight/composition; full `original_assemblies` / `transformed_assemblies` schema has no initializer found | yes |
| `work/lab-project/{Assets,Packages,ProjectSettings}/**` | `scripts/lab/build.py:82`; `scripts/lab/build.py:109`; `scripts/lab/whole_catalog.py:740`; `scripts/lab/animation_bindings.py:22`; +3 more | `scripts/lab/prepare.py:14`, `:16`, `:18`; `scripts/lab/whole_catalog.py:768`; source copy/retarget in `scripts/lab/composition_migration.py:297` | generated by repo code | yes — build/content import; this is incremental staging, not a complete current-project bootstrap | yes |
| `work/lab-project/Assets/LabLoadingScene/Resources/MovementBatchProbe.json` | `scripts/lab/composition_migration.py:146`; `scripts/lab/build.py:19`; `scripts/lab/whole_catalog.py:1050`; `android/Assets/Editor/LabBuild.cs:118`; +8 more | `scripts/lab/scene_runtime.py:586` (minimal); `scripts/lab/composition_migration.py:343`, `:349` rebase B8 | generated by repo code | yes — dependencies/full build; current data inherits B8 | yes |
| `work/scene-probe-build.json` | `scripts/lab/integrated_moon.py:234`; `scripts/lab/nova_bridge.py:109`; `scripts/lab/nova_bridge.py:198`; `scripts/lab/nova_bridge.py:329`; +21 more | `scripts/lab/scene_runtime.py:171`; `scripts/lab/composition_migration.py:344` | generated by repo code | yes — dependencies/build; stage reads existing recipe before rewriting it | yes |
| `work/lab-project/Assets/Recovered/geometry.obj` | `android/Assets/Editor/LabBuild.cs:194`; `scripts/lab/prepare.py:21` | `scripts/lab/prepare.py:28` | generated by repo code | yes — build always loads utility mesh | yes |
| `work/inventory/geometry-provenance.json` | `scripts/lab/prepare.py:21` | `scripts/lab/prepare.py:29` | generated by repo code | no — utility preparation | yes |
| `work/config/lab-project.json` | none found (output receipt) | `scripts/lab/prepare.py:31` | generated by repo code | no | yes |
| `work/lab-project/Assets/LabLoadingScene/Resources/{AndroidNative*.shader,AndroidNative*.json,AndroidNative*.png,AndroidIntersectionPresentation.shader}` | `android/Assets/Editor/LabBuild.cs:27`; `android/Assets/Editor/LabBuild.cs:33`; `android/Assets/Editor/LabBuild.cs:34`; `scripts/lab/build.py:109`; +1 more | `scripts/lab/composition_migration.py:322`, `:337` stage selected shader sources/textures; generators below | generated by repo code | yes — build/payload hashes | yes |
| `work/lab-project/Assets/LabLoadingScene/Resources/{WholeStageContexts.json,WholeCatalogBootstrap.json} and generated visual maps/link.xml` | `scripts/lab/build.py:109`; `tools/unity/runtime/catalog/OriginalBodyVisualBoundary.cs:18` | `scripts/lab/whole_catalog.py:1033`, `:1060`, `:1101`, `:1118` | generated by repo code | yes — whole-catalog builds; imported runtime resources | yes |
| `work/decompiled/<assembly>/<cache-key>/** (including RoR2.ContentManagement/AddressablesLoadHelper.cs, RoR2/{CharacterBody,HealthComponent,GlobalEventManager}.cs and result.json)` | `scripts/lab/whole_catalog.py:318`; `scripts/lab/whole_catalog.py:344`; `scripts/lab/whole_catalog.py:944`; `scripts/lab/body_visual_map.py:34`; +2 more | `scripts/lab/recovery.py:17` invokes ILSpy; `:27` writes result | generated by repo code | yes — repair-bindings and whole-catalog builds | yes |
| `work/inventory/decompilation.json` | `scripts/lab/experiments.py:5` | `scripts/lab/recovery.py:27`, `:29` | generated by repo code | no — recompile action | yes |
| `work/assetripper/<cache-key>/** (exported Unity project and result.json)` | `scripts/lab/composition_migration.py:107`; `scripts/lab/composition_migration.py:163`; `scripts/lab/whole_catalog.py:265`; `scripts/lab/whole_catalog.py:778`; +1 more | `scripts/lab/recovery.py:61` export request; `:67` result | generated by repo code | yes — reconstruction pointer resolves here in the usual layout; exact selected target unclear without opening config | yes † |
| `work/experiments/whole-catalog/latest.json` | `scripts/lab/nova_bridge.py:313`; `scripts/lab/composition_migration.py:127`; `scripts/lab/composition_migration.py:197`; `scripts/lab/whole_catalog.py:248`; +9 more | `scripts/lab/whole_catalog.py:373` (`whole-catalog-audit`, outside current list) | generated by repo code | yes — all catalog/composition actions need this existing audit | yes |
| `work/experiments/whole-catalog/<timestamp>/{source-catalog.json,original-catalog-contract.json}` | `scripts/lab/whole_catalog.py:25`; `scripts/lab/whole_catalog.py:318`; `scripts/lab/whole_catalog.py:363`; `scripts/lab/whole_catalog.py:941`; +1 more | `scripts/lab/whole_catalog.py` `export_source_catalog` (host `catalog_reader.py`, J714) | generated by repo code | yes — catalog and build | yes |
| `work/experiments/whole-catalog/<timestamp>/catalog-metadata.json → <filename>` | `scripts/lab/whole_catalog.py:37`; `scripts/lab/whole_catalog.py:40` | none found for optional metadata/alternate file; generated source-catalog.json is the fallback | historical evidence/receipt | yes if metadata receipt exists — prepare/repair; selected filename unclear | yes |
| `work/experiments/whole-catalog/<timestamp>/{host-closure.json,source-guid-index.json,source-guid-repairs.json}` | `scripts/lab/whole_catalog.py:250`; `scripts/lab/whole_catalog.py:500`; `scripts/lab/composition_migration.py:128`; `scripts/lab/whole_catalog.py:734`; +3 more | `scripts/lab/whole_catalog.py:362`, `:371`, `:372` | generated by repo code | yes — composition/catalog (repairs optional) | yes |
| `work/experiments/whole-catalog/<timestamp>/reconciled-closure.json` | `scripts/lab/whole_catalog.py:436`; `scripts/lab/whole_catalog.py:722`; `scripts/lab/whole_catalog.py:863`; `scripts/lab/whole_catalog.py:1113` | `scripts/lab/whole_catalog.py:329`, `:946` | generated by repo code | yes — prepare/contracts/repair/build | yes |
| `work/experiments/whole-catalog/<timestamp>/{native-latest.json,native-conversions.json} → native-<timestamp>/<bundle-id>.json` | `scripts/lab/whole_catalog.py:726`; `scripts/lab/whole_catalog.py:728`; `scripts/lab/whole_catalog.py:693`; `scripts/lab/whole_catalog.py:869`; +2 more | `scripts/lab/whole_catalog.py:308`, `:543`, `:554`; `:890` repairs a missing bundle receipt | generated by repo code | yes — prepare/repair; native inventory/reconcile producers are outside current list | yes |
| `work/experiments/whole-catalog/<timestamp>/typed-import-conversions.json` | `scripts/lab/whole_catalog.py:311`; `scripts/lab/whole_catalog.py:872`; `scripts/lab/whole_catalog.py:935` | `scripts/lab/whole_catalog.py:937` | generated by repo code | yes if present — repair (and prerequisite reconcile) | yes |
| `work/experiments/whole-catalog/<timestamp>/contracts-latest.json → runtime-contracts-<timestamp>/{runtime-contracts.json,result.json}` | `scripts/lab/whole_catalog.py:866`; `scripts/lab/whole_catalog.py:867`; `scripts/lab/whole_catalog.py:1084`; `scripts/lab/whole_catalog.py:1085` | `tools/catalog/ExportRuntimeContracts.cs.txt:17`; `scripts/lab/whole_catalog.py:466`, `:467` | generated by repo code | yes — repair/build; contracts refreshes pointer | yes |
| `work/experiments/whole-catalog/<timestamp>/integration-latest.json → integration-<timestamp>/manifest.json` | `scripts/lab/whole_catalog.py:828`; `scripts/lab/whole_catalog.py:839`; `scripts/lab/whole_catalog.py:860`; `scripts/lab/whole_catalog.py:1022`; +4 more | `scripts/lab/whole_catalog.py:812`, `:817` | generated by repo code | yes — host/repair/build/run; manifest also reached through whole-catalog-build.json | yes |
| `work/experiments/whole-catalog/<timestamp>/integration-<timestamp>/host-integration.json` | `scripts/lab/whole_catalog.py:830`; `scripts/lab/whole_catalog.py:861`; `scripts/lab/whole_catalog.py:1023` | `tools/catalog/ValidateWholeCatalog.cs.txt:25` via `scripts/lab/whole_catalog.py:829` | generated by repo code | yes — host/repair/build | yes |
| `work/experiments/whole-catalog/<timestamp>/integration-<timestamp>/host-provider-result.json` | `scripts/lab/whole_catalog.py:847` | `tools/catalog/WholeCatalogHost.cs:43` (Save) | generated by repo code | yes — host-providers | yes |
| `work/experiments/whole-catalog/<timestamp>/integration-<timestamp>/{build.json,build-previous-<timestamp>.json,device-latest.json,device-<timestamp>/**,import-receipt.json,mesh-subobjects.json,typed-import-repairs.json,support-source-alias.json,host-provider-dispatch.json,*-query*}` | none found (output evidence; query client reads its generated request sidecar at scripts/lab/whole_catalog.py:400) | `scripts/lab/whole_catalog.py:815`, `:934`, `:1133`, `:1204`, `:1205`; query/dispatch at `:408`, `:419` | historical evidence/receipt | yes — written/collected by catalog actions; mostly outputs, device-latest is not followed by those commands | yes |
| `work/whole-catalog-build.json → manifest` | `scripts/lab/build.py:116`; `tools/catalog/WholeCatalogBuild.cs:25`; `tools/catalog/AndroidProgressionHost.cs:66` | `scripts/lab/whole_catalog.py:1121` | generated by repo code | yes — direct build if present; whole-catalog build creates it | yes |
| `work/whole-catalog-code-base.json` | `scripts/lab/build.py:89`; `scripts/lab/stage_variants.py:87` | `scripts/lab/build.py:86`, `:98` | generated by repo code | yes — code-build validates reuse; full catalog build freezes receipt | yes |
| `work/{body-visual-map-latest.json,global-common-map-latest.json,animation-bindings-latest.json}` | none found (output receipts) | `scripts/lab/whole_catalog.py:1039`, `:1040`, `:1045` | historical evidence/receipt | yes — catalog-build outputs | yes |
| `work/experiments/scene-runtime/current.json → <attempt>/attempt.json` | `scripts/lab/nova_bridge.py:20`; `scripts/lab/nova_bridge.py:53`; `scripts/lab/nova_bridge.py:620`; `scripts/lab/nova_bridge.py:611`; +27 more | `scripts/lab/scene_runtime.py:69`, `:589`; `scripts/lab/composition_migration.py:362`, `:369` | generated by repo code | yes — composition stage reads old attempt; catalog-run does not call movement-batch-run | yes |
| `work/experiments/scene-runtime/<timestamp>/nova-input-mapping.json → <observation>` | `scripts/lab/composition_migration.py:356`; `scripts/lab/composition_migration.py:357`; `scripts/lab/scene_runtime.py:629`; `scripts/lab/scene_runtime.py:631` | `scripts/lab/nova_bridge.py:633`, `:161`; `scripts/lab/composition_migration.py:360` copies validated mapping | historical evidence/receipt | yes — composition reads mapping and hashes observation; actual selected observation unclear | yes † |
| `work/<composition-evidence>/{staging-result.json,attempt.json,nova-input-mapping.json,current-scene-contracts.json,current-original-script-orders.json,dependency-stage-<timestamp>/receipt.json,missing-runtime-bindings.json}` | `scripts/lab/composition_migration.py:375` | `scripts/lab/composition_migration.py:177`, `:278`, `:350`, `:354`, `:360`, `:362`, `:370` | historical evidence/receipt | yes — composition outputs; attempt/mapping subsequently read through current pointer | yes † |

## Build, install and runtime receipts

| Path / family | Readers (file:line) | Producer in repo | Class | Current workflow reaches it | Present |
| --- | --- | --- | --- | --- | --- |
| `work/build-request.json` | `android/Assets/Editor/LabBuild.cs:45`; `android/Assets/Editor/LabBuild.cs:197` | `scripts/lab/build.py:146` | generated by repo code | yes — build | yes |
| `work/graphics-api.txt` | `android/Assets/Editor/LabBuild.cs:108` | `scripts/lab/build.py:144` | generated by repo code | yes — build | yes |
| `work/lab-build/{started.json,result.json,previous-<timestamp>.json,*.apk}` | `scripts/lab/build.py:152`; `scripts/lab/build.py:154`; `scripts/lab/build.py:157`; `scripts/lab/scene_runtime.py:611`; +1 more | `android/Assets/Editor/LabBuild.cs:55`, `:213`, `:216`; `scripts/lab/build.py:145` archives result | generated by repo code | yes — build; result request identity is mandatory | yes |
| `work/lab-build/player-linker-inputs/{empty-linker.xml,<request>.json,<request>.il2cpp.json,<request>.il2cpp-incomplete.json,<request>/assemblies/**,<request>/poststrip/**}` | `scripts/lab/player_linker_receipt.py`, `player_il2cpp_receipt.py` and `build.py` | `android/Assets/Editor/PlayerLinkerInputCapture.cs` at UnityLinker; `Il2CppInvocationCapture.cs` at the optional pre-launch log callback | generated by repo code | yes — explicit capture flags; immutable snapshots and same BuildReport GUID bind request/source/input/APK; actual callback delivery and composed-audio stage equivalence remain unverified | yes |
| `work/build-cache/<key>/{result.json,*.apk,payload/*}` | `scripts/lab/build.py:137`; `scripts/lab/build.py:140`; `scripts/lab/build.py:138`; `scripts/compact-history.py:195` | `scripts/lab/build.py:161`, `:163`, `:165` | cache | yes — build cache hit; catalog builds force a fresh build | yes |
| `work/lab-build/symbols-<request>/{*.apk,*.zip}` and symbol-mode `work/build-cache/<key>/symbols.zip` | `scripts/lab/build.py` and `symbol_artifacts.py` | `android/Assets/Editor/LabBuild.cs` generates; `build.py` retains and hashes | generated optional output | yes — only explicit debugging-symbol builds; exact APK/ELF identity required | yes |
| `work/config/current-build.json → <apk>` | `scripts/lab/nova_bridge.py:66`; `scripts/lab/primary_fire.py:16`; `scripts/lab/presentation.py:10`; `scripts/lab/lifecycle.py:9`; +4 more | `scripts/lab/build.py:143`, `:165`; `scripts/lab/presentation.py:90` | generated by repo code | yes — install/catalog-run; build selects APK | yes |
| `work/generated-android-data/* (bundles, manifests, windows-shaders.bundle)` | `scripts/lab/build.py:96`; `scripts/lab/build.py:163`; `scripts/lab/device.py:108`; `scripts/lab/presentation.py:15`; +1 more | `android/Assets/Editor/LabBuild.cs:202`; `scripts/lab/prepare.py:36`; `scripts/lab/build.py:142` restores cache | generated by repo code | yes — code-build hashes; catalog-run syncs; direct run only launches | yes |
| `work/generated-android-data/whole-catalog.json` | `scripts/lab/whole_catalog.py:1160`; `scripts/lab/device.py:108` | `tools/catalog/WholeCatalogBuild.cs:46` | generated by repo code | yes — catalog-run hashes/pushes selector; sync transfers payload | yes |
| `work/device/installed.json` | `scripts/lab/device.py:35` | `scripts/lab/device.py:72` | historical evidence/receipt | yes — install update and run ownership gate; first install creates it | yes |
| `work/device-install-limits/<digest>.json` | `scripts/lab/device.py:54` | `scripts/lab/device.py:69` | historical evidence/receipt | yes — install (absent counter defaults to zero) | yes |
| `work/device/runtime.json` | `scripts/lab/boundaries.py:82`; `scripts/lab/boundaries.py:130`; `scripts/lab/boundaries.py:196`; `scripts/lab/device.py:102`; +9 more | `scripts/lab/device.py:96` from real launch diagnostics | historical evidence/receipt | yes — catalog-run sync; direct run rewrites runtime when reported | yes |
| `work/device/last-run.json` | `scripts/lab/rewired_trial.py:117` | `scripts/lab/device.py:98` | historical evidence/receipt | yes — run writes; current commands do not reread it | yes |
| `work/device/{storage.json,sync.json}` | none found (output receipts) | `scripts/lab/device.py:48`, `:123` | historical evidence/receipt | yes — preflight/install query live storage; catalog-run sync writes | yes |
| `work/device/diagnostics.json` | `scripts/lab/main.py:487` | `scripts/lab/main.py:486` | generated by repo code | no — diagnostics command | yes |
| `work/{preflight.json,doctor.json}` | none found (output receipts) | `scripts/lab/build.py:51`; `scripts/lab/health.py:21` | historical evidence/receipt | yes — preflight output; doctor is outside current list | yes |
| `work/editor/<timestamp>-<target>-<action>/** and <target>-process.json / editor logs` | `scripts/lab/boundaries.py:253`; `scripts/lab/boundaries.py:263` | `scripts/lab/editor.py:9`; `scripts/lab/build.py:61`, `:62` | historical evidence/receipt | yes — build records MCP dispatch; process/log rereads are older closure action | yes |
| `work/runs/latest.json → <timestamp>-<apk-hash>/result.json and captures/**` | `scripts/lab/health.py:19` | `scripts/lab/device.py:171`; `:136` collection | historical evidence/receipt | no — smoke/doctor/logs/crash/screenshot/perf; catalog-run collects into its own evidence tree | yes |
| `work/tests/<temporary-fixture>/**` | none in scripts/tools/android; test runner creates fixture | `tests/test_assembly_slice.py:15`, `:17`, `:19` | cache | yes — test when toolchain fixture enabled; no dependency on pre-existing game state | no |
| `work/backend-evidence.json` | none found (output evidence) | `android/Assets/Editor/LabBuild.cs:222` | historical evidence/receipt | no — explicit BackendEvidence menu/action | no |
| `work/experiments/whole-catalog/<timestamp>/integration-<timestamp>/{host-empty-catalog.json,host-settings.json}` | `tools/catalog/WholeCatalogHost.cs:37` | `tools/catalog/WholeCatalogHost.cs:35`, `:36` | generated by repo code | yes — host-providers creates a minimal Addressables startup catalog/settings | yes |
| `work/experiments/whole-catalog/gameplay/<host-fixture>/** (profile.json and recovery siblings)` | `tools/unity/runtime/progression/AndroidOfflineProfile.cs:65`; `tools/catalog/AndroidProfileHost.cs:42`; `tools/catalog/AndroidProgressionHost.cs:125`; `tools/catalog/AndroidDiscoveryHost.cs:42` | `tools/unity/runtime/progression/AndroidOfflineProfile.cs:66`; `tools/catalog/AndroidProfileHost.cs:17`, `:34` | generated by repo code | no — explicit host fixture methods; current catalog actions only stage these sources | yes † |

## Multi-device state (three configured; gameplay qualification remains per device)

The dated inventory above records the historical single-device receipt paths. The current
selector uses the ignored `work/config/local.json` fields `device_serials` (authorized allowlist),
`device_serial`, and `device_settings[serial]`. Device commands may select with
`--device SERIAL` or `LAB_DEVICE=SERIAL`. Multiple attached devices without an explicit
selection refuse; an explicit serial outside the allowlist refuses. Existing top-level
legacy configuration is fallback only for the default device. Device-specific settings
include `storage_mode`, `internal_reserve_mib`, `apk_install_limit`,
`sleep_display_when_idle`, `display_models`, and `display_count`.

Receipts live under `work/device/<serial>/`, including that device's installation,
storage, sync and runtime placement records after explicit `migrate-device-receipts`
activation. Legacy `work/device/` originals remain preserved. Migration retains the
original files and writes its activation marker last so an
incomplete migration cannot make an empty per-device receipt directory authoritative. No
receipt migration was performed before lock release. J595 then migrated the configured
Nova's verified receipts, preserving the flat originals and copying the counter, and passed
both baseline modes after an in-place adopted-storage install. An absent allowlist was
initialized only from the already configured default serial. J755 records the user's
authorization for Root to discover the other serials and configure all three explicitly.
The baseline Nova remains adopted-only; the second Nova and Thor use explicit internal
profiles, at least 1,024 MiB reserve, exact observed model lists and idle display control.
Thor has display_count=2 and both physical panels verify OFF.

The second Nova's pre-existing lab package is backed by the preserved
`work/device/installed-other-nova-backup.json`. Root verified its exact live APK bytes,
placement and signing identity before restoring that receipt through the canonical
scoped receipt API; the historical source stays intact. Ordinary installs then update
the owned package and record new per-device placement/runtime receipts. No receipt from
another device supplies ownership.

The game also needs its accepted attempt-bound Nova input mapping. Payload sync alone
does not supply it. The existing composition generator's
`work/experiments/input-migration/composed-25475991/nova-input-mapping.json` retains the
original measured observation/hash and supplies the current attempt; Root verifies that
observation and the exact installed APK attempt before copying it to the second Nova's
owned runtime path. This is existing measured Nova setup, not new physical-controller
acceptance. Thor has no such measured mapping; its game check is refused and its current
role is isolated audio/compatibility. Raw onboarding, historical-receipt verification,
mapping binding and role evidence stays under ignored `work/coordination/` and the
individual scoped device trees.

Current baseline, survivor and completed-session checks additionally read the
exact APK artifact named by the selected `installed.json` ownership receipt.
An isolated worktree needs its own selected-device installed/runtime/sync
receipts. An existing canonical receipt may be restored through the receipt API
only after checking the same authorized serial, package placement, retained and
live APK bytes and current runtime backing. Preserve the canonical originals and
the exact install-counter bytes; a missing local receipt is not permission to
adopt an unknown package. The restoration's private provenance record stays with
the check evidence. A baseline check needs no synthetic `current-build.json`:
without that local build pointer it records `is_current_build: false`.
Its `apk` path is written by `./dev install` from the generated/preserved lab
APK; `apk_sha256` binds its bytes. `installed_attempt.py` parses the embedded
authored config from that verified byte snapshot instead of the mutable project
config. Preserve that artifact under the existing rollback/retention rules;
missing or changed bytes refuse before selector writes. No new receipt field,
local configuration field or timestamped evidence input is introduced.

Receipt/counter JSON paths and directory components below the selected work root must be
ordinary files/directories, with no symlink redirects. The user-selected work root itself
may be a symlink. `Device.evidence_directory` produces validated per-device bootstrap and
other evidence directory paths; incomplete or redirected paths refuse before publication.

Build/editor operations use the global host lock `work/coordination/unity-build.lock`.
Device runs are outside that lock. `./dev preflight` is intended to combine host/input gates
with selected-device storage checks, while `./dev build` runs host preflight only.
`./dev preflight --host-only` explicitly omits device access.

CPU capture outputs are generated by `scripts/lab/performance_capture.py` through
the current `./dev perf --action cpu` action. Per-device
`performance/<attempt>/{simpleperf.data,record-output.txt,simpleperf-report.txt,receipt.json,failure.txt}`
are ignored evidence, never build inputs. The action reads the selected installed
ownership/runtime receipts and available live selection/report only; it does not read
a remembered timestamped run directory. It captures the existing foreground process
and preserves unsuccessful/partial attempts. A unique `/data/local/tmp/` output is
removed only after a verified nonempty host pull. No SDK, profiler binary or extra
required local content is added. Device permission and useful symbol attribution
remain unverified.

`session_cleanup_check.py` generates per-device evidence through
`Device.evidence_directory` under
`experiments/session-cleanup/<attempt>/`. It reads the current APK artifact,
owned install/runtime receipts and current launch configuration. Prior exact
diagnostic report targets are preserved there before clearing; full current
completion/restart reports, logs and display mapping remain ignored evidence,
never build inputs. No remembered run directory supplies runtime configuration.

## Other local inputs and historical workflows

| Path / family | Readers (file:line) | Producer in repo | Class | Current workflow reaches it | Present |
| --- | --- | --- | --- | --- | --- |
| `work/config/core-loot-support.json` | `scripts/lab/integrated_objective.py:121` | none found | required local state with no producer | no — objective support action, not called by current dispatch | yes |
| `work/config/world-commerce-support.json` | `scripts/lab/integrated_objective.py:134` | none found | required local state with no producer | no — objective commerce action, not called by current dispatch | yes |
| `work/config/default-pickup-catalog.json` | `scripts/lab/nova_bridge.py:115` | none found | required local state with no producer | no — default pickup action, not called by current dispatch | yes |
| `work/config/pickup-droplet-catalog.json` | `scripts/lab/nova_bridge.py:129` | none found | required local state with no producer | no — droplet action, not called by current dispatch | yes |
| `work/config/enemy-catalog.json` | `scripts/lab/nova_bridge.py:390` | none found | required local state with no producer | no — enemy staging action, not called by current dispatch | yes |
| `work/config/enemy-reward-catalog.json` | `scripts/lab/nova_bridge.py:425`; `scripts/lab/nova_bridge.py:130` | none found | required local state with no producer | no — enemy rewards action, not called by current dispatch | yes |
| `work/config/director-team-catalog.json` | `scripts/lab/nova_bridge.py:447` | none found | required local state with no producer | no — director staging action, not called by current dispatch | yes |
| `work/config/player-death-effect.json` | `scripts/lab/nova_bridge.py:421` | none found | required local state with no producer | no — player death action, not called by current dispatch | yes |
| `work/config/nova-input-mapping.json` | `scripts/lab/nova_bridge.py:621` | none found | required local state with no producer | no — physical mapping selection action, not called by current dispatch | yes |
| `work/objective-support-query.txt` | `scripts/lab/integrated_objective.py:112` | none found | required local state with no producer | no — objective/Moon/geometry preparation | yes |
| `work/loot-orb-query.txt` | `scripts/lab/integrated_objective.py:112` | none found | required local state with no producer | no — objective/Moon/geometry preparation | yes |
| `work/ward-catalog-query.txt` | `scripts/lab/integrated_objective.py:146` | none found | required local state with no producer | no — objective/Moon/geometry preparation | yes |
| `work/moon-script-identities.txt` | `scripts/lab/integrated_moon.py:18`; `scripts/lab/nova_bridge.py:239`; `scripts/lab/integrated_moon.py:99`; `scripts/lab/integrated_moon.py:100` | none found | required local state with no producer | no — objective/Moon/geometry preparation | yes |
| `work/moon-address-query.txt` | `scripts/lab/integrated_moon.py:120`; `scripts/lab/integrated_moon.py:196` | none found | required local state with no producer | no — objective/Moon/geometry preparation | yes |
| `work/<checkpoint-evidence>/next-objective-catalog-query.json` | `scripts/lab/integrated_objective.py:85` | none found | required local state with no producer | no — stage_objective | yes |
| `work/<hud-attempt>/hud-source-roots.json` | `tools/unity/runtime/presentation/RecoveredHudBuilder.cs:80` | `scripts/lab/integrated_objective.py:286` | generated by repo code | no — HUD builder is not invoked by current catalog build | yes † |
| `work/<hud-attempt>/native-crosshair-sprites.json` | `tools/unity/runtime/presentation/RecoveredHudBuilder.cs:135` | none found | required local state with no producer | no — HUD builder | yes † |
| `work/experiments/barrier-effect-source/current.json → <attempt>/{source.json,catalog-query.json}` | `scripts/lab/scene_runtime.py:889` | none found | required local state with no producer | no — barrier source preparation | yes |
| `work/experiments/rewired-trial/active.json → <attempt>/{attempt.json,original-contract.json,trial-public-api.json,serialization-comparison.json,trial-build-result.json,original-manager-parsed.json}` | `scripts/lab/rewired_trial.py:6`; `scripts/lab/rewired_trial.py:15`; `scripts/lab/rewired_trial.py:48`; `scripts/lab/rewired_trial.py:62`; +1 more | none found for activation/original/serialization seed receipts; `tools/unity/experiments/RewiredTrialInventory.cs:112` writes public API; `tools/unity/experiments/RewiredTrialBuild.cs:73` writes build result | historical evidence/receipt | no — rewired-trial actions | yes |
| `work/checkpoints/LAST_KNOWN_GOOD_*.json (prefab/controller/avatar/skin/state/startup/Nova/combat/director/loot/world receipts)` | `scripts/lab/nova_bridge.py:57`; `scripts/lab/primary_fire.py:9`; `scripts/lab/nova_bridge.py:141`; `scripts/lab/nova_bridge.py:66`; +27 more | none found | historical evidence/receipt | no — older experimental actions; neither current catalog-run nor direct run follows these | yes |
| `work/checkpoints/LAST_OBSERVED_WHOLE_CATALOG.json` | none found in scripts/tools/android; mentioned in workflow documentation | none found | historical evidence/receipt | no — documented acceptance pointer, not a dispatched read | yes |
| `work/inputs/latest-preserved.json → <baseline>/{receipt.json,metadata/files.json,metadata/native.json}` | `scripts/lab/input_migration.py:59`; `scripts/lab/input_migration.py:61`; `scripts/lab/input_migration.py:72`; `scripts/lab/input_migration.py:93` | none found | historical evidence/receipt | no — input-update-check | yes |
| `work/experiments/input-migration/<timestamp>/{inventory/**,baseline-surface.json,update-surface.json,managed-comparison.json,optional-guard-comparison.json,middleware-comparison.json,result.json} and latest.json` | `scripts/lab/input_migration.py:71`; `scripts/lab/input_migration.py:80` | `scripts/lab/input_migration.py:70`, `:79`, `:87`, `:92`, `:98`, `:119`, `:120` | historical evidence/receipt | no — input-update-check | yes |
| `work/experiments/scene-closure/latest.json → <timestamp>/{loadingbasic.json,CommandoBody.json,editor-identities.json}` | `scripts/lab/scene_runtime.py:25`; `scripts/lab/scene_runtime.py:26`; `scripts/lab/scene_runtime.py:29`; `scripts/lab/scene_runtime.py:152` | `scripts/lab/scene_closure.py:61`, `:67` write closure/latest; none found for editor-identities.json | historical evidence/receipt | no — scene_prepare/scene_arm | yes |
| `work/experiments/scene-runtime/<timestamp>/{attempt.json,stage/**,scene-probe-build.json,rollback.json,original-motor-order.json,*-identities.json,*-addresses.json,*-contract.json,*-result.json,<probe>/**}` | `scripts/lab/scene_runtime.py:231`; `scripts/lab/scene_runtime.py:275`; `scripts/lab/scene_runtime.py:345`; `scripts/lab/nova_bridge.py:612`; +4 more | `scripts/lab/scene_runtime.py:69`, `:589`, `:699`, `:737`, `:866` and `tools/unity/experiments/ReferenceIdentityProbe.cs:37`; some imported query receipts have no producer | historical evidence/receipt | no for residual historical family; current attempt/mapping are split out above | yes |
| `work/experiments/startup-boundary/{original-metadata.json,reflection-metadata.json}` | `scripts/lab/scene_runtime.py:437` | none found | historical evidence/receipt | no — startup_prepare | yes |
| `work/experiments/{dependency-boundaries,rewired-original,collections-runtime,ror2-slice,original-closure-runtime}/<timestamp>/** and latest.json` | `scripts/lab/scene_runtime.py:59`; `scripts/lab/boundaries.py:126` | `scripts/lab/boundaries.py:49`, `:101`, `:147`, `:176`, `:215` | historical evidence/receipt | no — historical experiments (fixed slice receipt also listed below) | yes |
| `work/experiments/original-closure/current.json → <timestamp>/attempt.json` | `scripts/lab/boundaries.py:160`; `scripts/lab/boundaries.py:249` | `scripts/lab/boundaries.py:244` | historical evidence/receipt | no — original closure actions | yes |
| `work/experiments/nova-input/current.json → <timestamp>/{result.json,events.txt,capabilities.txt,target.json,foreground.txt}` | none found for current pointer; mappings may select an observation | `scripts/lab/nova_input.py:21`, `:22`, `:32`, `:38`, `:42` | historical evidence/receipt | no — physical observation actions | yes |
| `work/experiments/{storage-lifecycle,recompile}/**` | none found (output evidence) | `scripts/lab/lifecycle.py:13`; `scripts/lab/experiments.py:11` | historical evidence/receipt | no | yes |
| `work/experiments/source-scenes/{candidate.json,*.receipt.json,audio-boundary*/receipt.json,*.dll,*.json}` | `scripts/lab/source_scene_candidate.py:45`; `scripts/lab/source_scene_candidate.py:62`; `scripts/lab/source_scene_candidate.py:183` | `scripts/lab/source_scene_candidate.py:90`, `:204` | historical evidence/receipt | no — source-scene-prepare; generated project scene assets can be build inputs | yes |
| `work/experiments/stage-variants/{latest.json,<timestamp>/**}` | none found for pointer; project/manifest are read instead | `scripts/lab/stage_variants.py:217`; `:131` writes compressed source originals | historical evidence/receipt | no — stage-variants | yes |
| `work/lab-project/Assets/{LabReferenceQuery.json,LabLoadingScene/Editor/character-motor-order*.json}` | `tools/unity/experiments/ReferenceIdentityProbe.cs:15`; `tools/unity/experiments/CharacterMotorOrderProbe.cs:13`; `scripts/lab/nova_bridge.py:45`; `scripts/lab/nova_bridge.py:612` | `scripts/lab/scene_runtime.py:216`, `:869`; `tools/unity/experiments/CharacterMotorOrderProbe.cs:34` | generated by repo code | no — editor identity/order experiments | no |
| `work/lab-project/Assets/LabCatalogQuery.json` | `tools/unity/runtime/catalog/CatalogAddressProbe.cs:17` | none found | required local state with no producer | no — catalog-addresses editor action | no |
| `work/lab-project/Library/** (including PackageCache/com.unity.ugui@1.0.0/Runtime/UI/Core/Layout/GridLayoutGroup.cs.meta)` | `scripts/lab/integrated_objective.py:231` | Unity import/package resolution; `scripts/lab/editor.py:39` requests refresh | cache | yes — editor build uses import cache; explicit GridLayoutGroup metadata read is older objective action | yes |

## Shader recovery, presentation and auxiliary storage

| Path / family | Readers (file:line) | Producer in repo | Class | Current workflow reaches it | Present |
| --- | --- | --- | --- | --- | --- |
| `work/config/shader-source-analysis.json` | `scripts/lab/shader_source.py:113` | none found | required local state with no producer | no — shader generation actions | yes |
| `work/config/shader-deferred-analysis.json` | `scripts/lab/shader_deferred.py:64` | none found | required local state with no producer | no — shader generation actions | yes |
| `work/config/shader-material-analysis.json` | `scripts/lab/shader_materials.py:49` | none found | required local state with no producer | no — shader generation actions | yes |
| `work/experiments/shader-recovery/<timestamp>/** (selected as <shader-analysis>; receipt.json, original-tree-base64.json, native-records.json, program/layout files)` | `scripts/lab/shader_deferred.py:14`; `scripts/lab/shader_deferred.py:25`; `scripts/lab/shader_source.py:116`; `scripts/lab/shader_source.py:130` | `scripts/lab/shader_recovery.py:127`, `:131`, `:137`, `:138`, `:212` | generated by repo code | no — shader generators; selected generated sources are read by composition | yes † |
| `work/<material_inventory> (shader selection field)` | `scripts/lab/shader_deferred.py:81`; `scripts/lab/shader_materials.py:67` | none found | required local state with no producer | no — shader generation | yes † |
| `work/{shader-recovery-current,shader-bindings-current,deferred-bindings-current,material-bindings-current}.json` | none found (published selection pointers) | `scripts/lab/shader_recovery.py:84`; `scripts/lab/shader_source.py:139`; `scripts/lab/shader_deferred.py:66`; `scripts/lab/shader_materials.py:50` | generated by repo code | no — generators write them; composition uses explicit shader_sources instead | yes |
| `work/experiments/{shader-bindings,deferred-bindings,material-bindings}/<timestamp>/{sources/*,receipt.json,unity-*,*-layout.json}` | `scripts/lab/composition_migration.py:314`; `scripts/lab/composition_migration.py:318`; `scripts/lab/presentation.py:20` | `scripts/lab/shader_source.py:175`, `:181`; `scripts/lab/shader_deferred.py:102`, `:109`, `:110`, `:113`; `scripts/lab/shader_materials.py:149`, `:152` | generated by repo code | yes — composition stages selected shader_sources; exact selected directories unclear | yes † |
| `work/generated-shader-candidates/outline-highlight-r4/<input_id>/**` (current two-pass ShaderLab, measured program/layout/pass evidence and manifest) | optional `whole_catalog.prepare_integration` shader override | `scripts/lab/shader_outline.py:generate` via `shader-outline-candidate` | generated by repo code from accepted local input and the fixed public recipe; prior R4, R3 and R2 outputs remain preserved in their versioned directories | only when explicitly activated — J965 bundle fixture passes; Android appearance remains separate | yes † |
| `work/generated-shader-candidates/ramp-fog-r5/<input_id>/**` (current candidate ShaderLab, exact native records/programs/layouts, pass state, and receipts) | optional `whole_catalog.prepare_integration` shader override | `scripts/lab/shader_ramp_fog.py:generate` via `shader-ramp-fog` | generated by repo code from the accepted local installation and public recipe; prior R4, R3 and R2 outputs remain preserved in their versioned directories | only when explicitly activated — J965 bundle fixture passes; Android appearance remains separate | yes † |
| `work/generated-shader-candidates/screen-damage-r1/<input_id>/**` (native ScreenDamage pass, programs/layouts, original state and receipts) | optional `whole_catalog.prepare_integration` shader override | `scripts/lab/shader_ramp_fog.py:generate(target="screen-damage")` via current `shader-screen-damage` | generated directly from the accepted original PC bundle and fixed public recipe; no retained analysis input | only when explicitly activated; editor/device appearance are separate gates | yes † |
| `work/generated-shader-candidates/{sobel-buffer,sobel-outline}-r1/<input_id>/**` | optional whole-catalog source Sobel shader override | `scripts/lab/shader_ramp_fog.py:generate` via current `shader-ramp-fog --target sobel-buffer` or `sobel-outline` | generated from the legitimate local bundle with fixed recipes, native topology, independent signatures and byte roundtrips; no retained evidence directory is an input | only when explicitly activated; host generation does not establish Android appearance | yes † |
| `work/generated-shader-candidates/translucent-camera-r2/<input_id>/**` (four candidate ShaderLab files, native program/interface evidence and manifests) | optional `whole_catalog.prepare_integration` nine-shader override | `scripts/lab/shader_translucent.py:main` via current `shader-translucent` | generated from the accepted configured installation and audited public recipe using the existing pinned shader tools | only when explicitly activated — J1009 isolated compile/cleanup passes; content integration, Android rendering and PC parity remain unqualified | yes † |
| `work/config/postprocessing-bloom.json` | optional whole-catalog Bloom staging | explicit operator selection with accepted `input_id` and `enabled` | required local state; keeps the public source replacement default off | only when enabled; source/import/device acceptance are separate | yes |
| `work/packages/com.unity.postprocessing-2.3.0.tgz` | `shader_postprocessing_bloom` | operator obtains the official archive from the URL pinned in `recipe/shader-postprocessing-bloom-candidate.json` | required local third-party input, exact archive/source/license hashes checked; source is never tracked or fetched implicitly | only for selected Bloom generation | yes |
| `work/generated-shader-candidates/postprocessing-bloom-r2/<input_id>/**` | optional whole-catalog Bloom/CopyStd staging and receipt validation | `scripts/lab/shader_postprocessing_bloom.py` from accepted export and pinned local archive | generated shader/include sources and input-bound manifest; no timestamped evidence folder is a build input | only when explicitly activated; no visual-parity claim | yes † |
| `work/config/postprocessing-uber.json` | optional whole-catalog exact Main Camera Uber shader staging | exactly `schema: whole-catalog-postprocessing-uber-activation-r1`, accepted `input_id`, and boolean `enabled` | required only when this batch is selected; public recipe and generator remain default off | selection is checked before catalog writes; rendering/parity are separate | yes |
| `work/packages/com.unity.postprocessing-2.3.0.tgz` | `shader_postprocessing_uber` | exact official archive pinned by `recipe/shader-postprocessing-uber-candidate.json` | required local input; archive, revision, license and Uber source hashes are checked; no download or package installation is automatic | only for selected Uber generation | yes † |
| `work/generated/shader-candidates/postprocessing-uber/<input_id>/**` | optional whole-catalog Main Camera Uber staging and receipt validation | `scripts/lab/shader_postprocessing_uber.py` from accepted export and pinned local archive | generated shader/include sources and input-bound manifest; no timestamped evidence folder is a build input | only when explicitly activated; no visual-parity claim | yes † |
| `work/reference-repos/{Abby1591__Unity_Shader_Decompiler,coconutbird__d3dasm,javelinlinV2__HLSLDecompiler,doitsujin__dxbc-spirv}/** and work/napbat/cfglib/**` | `scripts/lab/shader_recovery.py:99`; `scripts/lab/shader_source.py:125`; `scripts/lab/shader_deferred.py:72`; `scripts/lab/shader_materials.py:60`; +1 more | none found for fetching/building the pinned trees/binaries; `scripts/lab/shader_recovery.py:105` only records pins | required local state with no producer | no — shader recovery/generation; pins at shader_recovery.py:9 | yes |
| `work/toolchains/crossover-bottles/**` | `scripts/lab/shader_recovery.py:164`; `scripts/lab/shader_programs.py:36` | none found; shader_recovery.py:165 requires an already configured bottle | required local state with no producer | no — shader recovery/fallback requires configured bottle | yes |
| `work/experiments/android-presentation/<timestamp>/{bundle/**,sources/**,previous/**,selected-build.json,terminal.json}` | `scripts/lab/presentation.py:75`; `scripts/lab/presentation.py:77` | `scripts/lab/presentation.py:26`, `:90`; `android/Assets/Editor/LabBuild.cs:62`, `:76` | historical evidence/receipt | no — presentation payload actions | yes |
| `work/presentation-build-{request,result}.json` | `android/Assets/Editor/LabBuild.cs:45`; `scripts/lab/presentation.py:75` | `scripts/lab/presentation.py:68`; `android/Assets/Editor/LabBuild.cs:80` | generated by repo code | no — presentation payload actions | yes |
| `work/inventory/{graphics/<cache-key>.json,graphics.json,shader-manifest.json,shader-diff.json,graphics-summary.json,windows-shader-prototype.json}` | `scripts/lab/graphics.py:11`; `scripts/lab/graphics.py:37`; `scripts/lab/prepare.py:32`; `scripts/lab/source_reflections.py:11` | `scripts/lab/graphics.py:31`, `:33`, `:38`, `:39`, `:40`; `scripts/lab/prepare.py:37` | generated by repo code | no — graphics/utility/shader/presentation preparation | yes |
| `work/inventory/{middleware.json,middleware-reachability.json,reconstruction.json,serialized-references.json}` | none found (output evidence) | `scripts/lab/experiments.py:38`, `:39`, `:48`, `:65` | historical evidence/receipt | no — inventory experiment actions | yes |
| `work/experiments/audio-recovery/{current.json,<timestamp>/bank-index.json,decoder smoke files}` | none found (output evidence) | `scripts/lab/wwise_bank_index.py:130`, `:131` | historical evidence/receipt | no — audio-bank-index action | yes |
| `work/<pc-draw-output>/{draw.json,receipt.json,*.dxbc,*-cb-*.bin} and user-selected capture/unity/native-record paths` | `tools/shaders/export_pc_draw.py:126`; `tools/shaders/export_pc_draw.py:132`; `tools/shaders/export_pc_draw.py:133` | `tools/shaders/export_pc_draw.py:82`, `:90`, `:135`, `:144`; none found for user capture | historical evidence/receipt | no — standalone exporter; arbitrary selected capture existence unclear | yes † |
| `work/tools/assembly-probe/**` | `scripts/lab/boundaries.py:10` | `scripts/lab/boundaries.py:9` dotnet build | cache | yes — composition dependency support contract and contracts | yes |
| `work/assetripper-service/**` | none found (local service logs) | `scripts/lab/recovery.py:50`, `:51` | cache | no — export-project | yes |
| `work/retired-storage/{manifests/*.json.gz,blobs/**,operation.lock}, work/{experiments/scene-runtime,build-cache}/**.retired.json and operator-selected compaction plan` | `scripts/compact-history.py:114`; `scripts/compact-history.py:171`; `scripts/compact-history.py:195`; `scripts/compact-history.py:201`; +1 more | `scripts/compact-history.py:134`, `:165`, `:185`, `:188`, `:248`; no producer for operator plan | historical evidence/receipt | no — explicit compaction/restore only; never treated as disposable cache | yes |

The current generation marker deserves separate attention: `prepare.py:38` creates only the utility input marker, while composition requires assembly maps (`composition_migration.py:362–364`). No complete current assembly-map initializer was found. It is classified as generated because a write exists, but it remains an additional bootstrap/schema gap. Likewise, the live scene recipe/config have writers that consume their previous values; that is not proof that the present integrated composition can be reconstructed without B1–B8.

## Hard-coded timestamped run folders

These are all four timestamp literals found in filesystem paths in the audited source. The generic tables use `<timestamp>`; these exact public relative names identify the hard-coded references to replace. All four folders and their specifically read files exist on this workstation. None is called by the current command set; importing `scene_runtime` does not execute its preparation functions.

| Hard-coded folder / files | Reader | Producer | Class | Current workflow | Present |
| --- | --- | --- | --- | --- | --- |
| `work/experiments/original-closure-runtime/20260913T024051.910924Z/slice-provenance.json` | `scripts/lab/scene_runtime.py:59` | `scripts/lab/boundaries.py:176` writes the general `<timestamp>` family, not this fixed run | historical evidence/receipt | no — scene_prepare | yes |
| `work/experiments/audio-boundary/20260914T032612Z/{identities.json,serialized-closure.json}` | `scripts/lab/scene_runtime.py:515`; `:518` | none found | historical evidence/receipt | no — audio_assets_prepare | yes |
| `work/experiments/scene-runtime/20260930T202924.269738Z/teleport-catalog-query.json` | `scripts/lab/scene_runtime.py:883`; provenance string at `:887` | none found | historical evidence/receipt | no — body_start_loadout_prepare(teleport=True) | yes |
| `work/experiments/scene-runtime/20261008T163328.528634Z/optional-presentation-transformation.json` | `scripts/lab/input_migration.py:90–91` | none found | historical evidence/receipt | no — input-update-check | yes |

## How to remove each blocker

Keep all game-derived bytes, raw evidence and operator configuration ignored. Any tracked recipe must contain only reviewed authored transformations and public-safe selectors.

- B1 — Move the composition selection structure to a tracked recipe after privacy review, with operator-specific locations kept in local config.
- B2 — Done (J508): tracked as `recipe/hud-ui-remaps.json`.
- B3 — Check in a semantic-preview plan generator around `serialization_rebase.py`, including conflict and provenance validation.
- B4 — Check in the asset-analysis generator that enumerates old/current owners and authored additions.
- B5 — Check in the rebase-analysis/GUID-map generator and validate unique source owners.
- B6 — Check in a current-assembly type-absence proof generator for the conditional removed-state map.
- B7 — Check in the preview-tree writer driven by B3–B5, preserving hash checks and conflicts.
- B8 — Move the authored composition configuration/transforms to a tracked recipe after privacy review; replace selection of an anonymous prior tree with a named receipt for any unavoidable rollback input.
- Generation marker schema — Check in an initializer for accepted original/transformed assembly maps before composition staging.
- Older catalog/support/mapping JSON inputs and query TXT files — Check in generators for each listed required-input row; retain operator acceptance for physical mapping.
- Native crosshair query, editor LabCatalogQuery and barrier-source chain — Check in query/receipt generators with named receipts for their selected source generation.
- Shader selection/material census/pinned source trees and configured CrossOver bottle — Move reviewed selections to tracked recipes and check in census/fetch/build generators; shader outputs remain ignored.
- Fixed timestamp references, checkpoint/activation/preservation seeds and optional catalog metadata — Replace each with a named, input/hash-validated receipt and a documented producer; do not require an old run identifier.

Uncertainty is limited but material: selector contents, exact active pointer targets, retired-tree completeness and required conditional branches were not inspected. No runtime trace was taken. The inventory records source-level reachability and file-name existence, not the validity or rebuildability of the present workstation state. Device-side profile/result data uses `Application.persistentDataPath`; those are runtime stores, not host `work/` inputs. External installations, SDKs, `.local` tools and environment captures are outside this `work/` inventory.

### Receipt-bound source identity metadata

`WholeStageContexts.json` remains generated by the existing whole-catalog map
producer. Its source identity blocks require the staged
`Assets/LabLoadingScene/SourceScenes/<scene>/<scene>.unity` bytes and existing
`work/experiments/source-scenes/candidate.json` hashes, both produced by
`source_scene_candidate.prepare` (R6 for an isolated rebuild). The new authored
reader is `scripts/lab/source_identity_metadata.py`; no timestamped audit
folder is a build input. Early policy-only R5 generation reads neither later
source scenes nor that receipt. Post-R6 R7 and ordinary whole-catalog builds
verify exact source hashes before emission. All generated identity data stays
ignored under `work/`; it is not a new user-maintained configuration field.

Source-scene preparation also reads the existing validated
`work/config/original-game-audio/selection.json`. Requested audio retains
original Wwise/RTPC components; default off reproduces their omitted form.
The same generator updates `candidate.json` and its exact scene hashes before
current full-build stage maps are generated. Fast/code-only builds refuse a
mode change; isolated R6 uses its own work selection and R9 verifies the mode.
No timestamped run output or additional local selector is required.

### Mercenary editor-fixture initialization

`work/tests/merc-evis-impact-effect/addressables-init/{settings,catalog}.json`
are authored empty Addressables fixture inputs generated and validated by
`tools/catalog/MercEvisImpactEffectExactEditorFixture.cs`. They are retained for
the initialized content locator's lifetime and reused only with identical
contents. They are not user-supplied state or game content. The support fixture
is staged by `whole_catalog.stage_build_sources`; ordinary player behavior
never reads this test directory.

### Current gameplay qualification support

`work/coordination/codex-poststrip-build-root-r1/` and
`work/experiments/player-il2cpp-capture/candidate-20261020T221724.572459Z/`
retain J843’s build driver, actual request/source/APK/symbol outputs, incomplete
capture witness, bounded log segment and host first failure. They are required
private diagnostic/rollback support, not current player inputs. The collector
and normal receipt producers live in tracked source; no build reads this run
folder. The `audio-poststrip-owning-build-triage/` proposals remain host-only.


`work/coordination/codex-native-inventory-build-root-r{1..2}/`,
`work/coordination/codex-native-inventory-device-root-r1/` and
`work/experiments/native-skin-siren-next/candidate-20261020T214442.277797Z/`
retain J840’s serialized build producer, frozen source/APK/symbol/capture receipts,
selected-device qualification driver and both-default acceptance proof. They are
required private diagnostic/rollback support; the game reads tracked sources and
regenerated payloads, never these timestamped evidence directories.


`work/coordination/codex-skin-siren-*`,
`work/coordination/siren-navigation-new-player-guard/` and
`work/coordination/animation-native-skin-device-plan/` retain hash-bound source
snapshots, saved compiler references, rendered editor guards and selected-device
qualification inputs for J828/J835 and the next targeted runs. They are required local
diagnostic support; the game build reads the tracked fixture/runtime sources,
not these run directories. No game-derived material is public.

`work/coordination/codex-native-skin-device-root-r{1..3}/` and
`work/coordination/animation-native-skin-runtime-triage/` retain J835's bounded
runner, strict persisted-profile schema check, failed live attempt, J841’s
completed native teardown/host deadline and exclusive inventory-owner analysis.
They are required local diagnostic support and are not game build inputs.

The optional Bee execution capture writes request-owned
`work/lab-build/player-linker-inputs/<request>.bee-pre.json`,
`<request>.bee-post.json` and `<request>.bee-log-slice`, then the verified
snapshot under `<request>/bee/`. Producers are the tracked
`Il2CppInvocationCapture.cs`, finalized by `LabBuild.Build` from its returned
BuildReport, and `bee_codegen_capture.py`; the active
`work/editor/lab-process.json` binds the process/log owner. Captured graphs,
response files, SDK/game-derived assemblies and real traces stay ignored.
The tracked multiline trace test is independently authored synthetic data.
Old legacy invocation witnesses remain historical evidence.

`work/coordination/original-game-audio-r27-trace-preservation-root-r{1,2}/`
retains a reviewed, one-use experiment helper for preserving the exact prior
graph-declared CodeGen trace before a fresh capture attempt. Root's isolated
driver supplies its pinned helper and retained request-evidence hashes under
the host mutex after positive editor idle. This is required local diagnostic
support for that explicit trial, not a normal build dependency or a generic
cache-clear action. Preserve its plan, prior trace, receipt and any failure;
no game input, assembly or other cache is removed by the experiment.

## Isolated Wwise diagnostic inputs

The optional J740/J742 native fixtures and fresh Unity managed-readiness
fixture require the locally authorized Wwise 2023.1.8.8601 SDK and matching
Unity Integration 2023.1.8.3208. These are protected user-supplied dependencies,
separate from the current game's default no-audio build. They are not bundled
with the public repository. Preserve the following local inputs for replay:

| Local state | Reason and consumer |
| --- | --- |
| `work/wwise/` and `work/coordination/wwise-installed-sdk-audit/` | Authorized integration archive/extraction and exact native-library receipts; independent fixture staging reads the pinned ARM64 Profile library. |
| `work/coordination/wwise-original-bank-load-plan/bank-manifest.json` | Hash-bound accepted original bank/event inventory; fixture producers verify supplied game bytes against it. Banks remain in the legitimate external input. |
| `work/coordination/wwise-init-android-platform-metadata/` | Frozen historical generator, Root-generated bank and receipt for J740/J742. `scripts/lab/wwise_init_platform.py` plus `recipe/wwise-init-android.json` can reproduce the metadata variant from the accepted original into a new ignored output; existing fixture receipts still bind their original frozen generator. |
| `work/coordination/wwise-controller-bus-monitor-candidate/native-build-v1/` | Frozen bridge/JNI and actual compiler/source/input bindings reused by the separate native fixtures. |
| `work/coordination/wwise-init-metadata-fixture-draft/`, `work/coordination/wwise-init-metadata-runner-draft/`, `work/coordination/wwise-adapted-init-global-fixture-draft/` | Private authored producer/checker and native/Java host-contract drafts plus explicit signed fixture receipts. No current game build reads them. |
| `work/coordination/wwise-android-managed-compat-draft/`, `work/coordination/wwise-android-owner-draft/`, `work/coordination/wwise-unity-managed-fixture-generator/`, `work/coordination/wwise-managed-player-build-draft/`, `work/coordination/wwise-unity-managed-device-runner-draft/` | Private managed ABI candidate, owner, generator and fresh-player build/run drafts. They preserve source hashes and reference closure; they are not yet a supported public rebuild recipe. |
| `work/coordination/wwise-managed-failure-diagnostics-draft/`, `work/coordination/wwise-managed-retry-coordinator-draft/`, `work/coordination/wwise-managed-v4-retry-prep/`, `work/coordination/wwise-managed-v5-prep/`, `work/coordination/codex-wwise-*`, `work/coordination/codex-audio-*` | Root-reviewed diagnostic source revisions, compact report protocol, process-start identity, explicit retry input plans and orchestration. Isolated builds bind these exact source hashes and preserve older request/APK receipts. They remain private authored support drafts with no current game-build reader. |
| `work/coordination/wwise-managed-render-r5-draft/`, `work/coordination/wwise-managed-render-r5-coordinator-draft/`, `work/coordination/wwise-managed-event-coordinator-root-r5/` | Private authored per-frame render owner, bootstrap/fixture, strict monitor/WAV runner and hash-bound retry support for J786. Exact source/manifest/closure and all importer metadata are retained for the isolated player; no current game build reads them. The public ABI generator supplies the raw managed candidate, while the fixture producers remain required local support drafts. |
| `work/coordination/wwise-managed-capture-r6-owner-fix/`, `work/coordination/codex-audio-r6-stage-draft/` | Private authored finalization/unknown-outcome owner, bootstrap/fixture, strict PCM-container profile and reviewed Root-only stage/package/build support for the next isolated player. These preserve the exact raw API, managed closure, original bank/native/scene inputs and importer metadata. Effective precision remains unknown; no current game build reads these support drafts. |
| `work/coordination/wwise-managed-preinit-monitor-investigation/native-build-feasibility/` | Private authorized Integration-source inventory, authored same-library diagnostic extension, exact SDK/NDK/plugin bindings and Root source-staging/native-compile drafts. The bridge preserves monitor ownership through Term and leaves pre-Init coverage unknown until runtime controls pass. Generated native outputs remain ignored and outside the current game build. |
| `work/coordination/wwise-managed-native-monitor-r7-draft/`, `work/coordination/audio-r7-preinit-first-failure-native-triage/`, `work/coordination/audio-r7-preinit-first-failure-managed-triage/` | Frozen private authored NativeMonitorLease, managed owner/bootstrap/fixture/runner, production-extracted host contracts and source-based first-failure follow-up. The isolated player binds the native snapshot schema, full-width output identity, managed references and exact source hashes. J802 records its failed runtime gate; these inputs remain outside the current game build. |
| `work/coordination/audio-r9-native-root-build-plan-draft/`, `work/coordination/audio-r9-native-elf-audit-draft/`, `work/coordination/audio-r9-fixture-manifest-generator/`, `work/coordination/audio-r9-unity-root-plan-draft/`, `work/coordination/audio-r9-unity-root-plan-review/` | Private schema-3 native build/audit, immutable fixture manifest, exact-editor stage/package/build adapter and review. Root's process-local instance guard and receipts under `codex-audio-native-r9-root-r1/` bind the actual library, current managed R4 sources, historical manifest provenance, 46 importer metadata files and the terminal request. J810 records the failed exact-marker control and complete cleanup. These inputs are required to replay the isolated fixture, not the game build. |
| `work/coordination/audio-r9-postinit-service-candidate/`, `work/coordination/audio-r9-service-unity-plan-draft/`, `work/coordination/audio-r9-service-unity-plan-review/`, `work/coordination/audio-r5-root-runner-review/`, `work/coordination/audio-r5-actual-result-review/` | Private R5 managed serviced-wait sources, exact-editor adapter, preserved reload/frozen-input refusals, terminal build freeze and independent runner/result review. J816 binds the actual failed monitor control and complete owned fixture removal. Root's process-local adapter under `codex-audio-service-root-r1/` separates the current managed-source view from historical overlays without rewriting them. No game build reads these inputs. |
| `work/coordination/audio-r6-formatted-monitor-control/`, `work/coordination/audio-r6-formatted-monitor-control-review/` | Required private support for the next isolated native/managed control candidate: actual callback-envelope receipt, exact-format predicates, mismatch-mutant tests and authorized SDK-source binding. J824 supplies the original envelope evidence; J837 qualifies the rebuilt isolated negative/event cases. These are not current game inputs. |
| `work/coordination/audio-r5-native-message-triage/`, `work/coordination/audio-r6-message-review/`, `work/coordination/audio-r6-fixture-execution-plan/` | Private R6 first-message diagnostic owner/bootstrap, bounded UTF-16 helper, production-extracted host contracts and source review/staging drafts. The exact native marker remains required before bank/event work. These are required local support for an isolated candidate, with no runtime acceptance or current game-build reader. |
| `work/coordination/codex-audio-message-root-r1/`, `work/coordination/codex-audio-message-main-root-r{1..6}/`, `work/coordination/codex-main-overlay-root-r*/`, `work/coordination/audio-r6-execution-review/` | Required private support for the isolated R6 fixture: preserved partial-stage receipts, exact source/importer reconciliation, compiled-stage proof, fresh Main package-absence/resource claims and one-shot build selections. The build adapter reads the pinned reconciled proof; device dispatch requires its own fresh selected-device proof and exact completed APK. J821/J824 preserve missing-report/foreground captures, guarded ordinary modal cancellation, exact unlock-source amendment and fresh post-run verification. These do not enable game audio or change the game's accepted APK. |
| `work/coordination/audio-game-native-optin-real-input-triage/`, `work/coordination/audio-game-native-optin-full-closure-plan/`, `work/coordination/game-audio-api-origin/` | Private authored composed-audio candidates and host-only full-closure analysis support. Their compiler reads frozen copies of the accepted raw API and staged managed closure, with source-origin and strict dispatch classification evidence. They have no stage-to-APK binding, runtime acceptance or current game-build reader. Game-derived assemblies and inspection outputs remain ignored. |
| `work/coordination/run_game_audio_r7_root.py`, `work/coordination/codex-audio-full-closure-root-r7/` | Root's private host-analysis adapter and immutable input ledger. The adapter verifies the candidate sources, explicitly binds the copied runner's R7 analysis paths and records the completed J820 scan. It changes no historical input and supplies no game or device acceptance. |
| `work/coordination/audio-formatted-native-root-build-plan/`, `audio-formatted-fixture-root-plan/`, `audio-formatted-r6-device-plan/` and corresponding review directories | Required private producers/checkers for J837: exact authorized SDK overlay, native/static input ledger, descendant stage/build proof and two-scenario device adapter. Root producers in `codex-audio-formatted-*` bind them to actual build and selected-device receipts, preserving every failed attempt. No current game build reads these inputs. |
| `work/coordination/game-audio-original-api-fixture-plan/`, `named-pickup-fixture-root-plan/`, `named-pickup-compiled-il-triage/`, `named-pickup-terminal-reconciliation/`, `named-pickup-device-plan/` and corresponding review directories | Required private authored named-event owner/bootstrap/manifest producers, token-resolved compiled-method witness, descendant adapter and separate successful-build qualification for J845. Root `codex-named-pickup-*` producers bind exact raw/qualified receipts, current source/APK inputs and selected-device cleanup, preserving all failures. The same-byte host adapter support copy includes its required hash-bound manifest. No current game build reads these support inputs. |
| `work/coordination/audio-current-player-closure-consumer/`, `audio-current-player-closure-review/` | Required private host transform/scanner and immutable current 330-input analysis for J837. They consume J823/J828 capture snapshots and retain full source/API provenance; no post-strip/APK staging or runtime reader is supplied. |
| `work/toolchains/android-ndk-r25c*` | Official Google NDK r25c archive and isolated native-library toolchain, bound by download checksum and local revision/tool hashes. The supplied Wwise Android SDK requires r25; this optional diagnostic build dependency stays separate from Unity's pinned r21 SDK/NDK and does not change editor preferences or `scripts/env.sh`. |
| `work/coordination/wwise-unity-filename-io-triage/`, `work/coordination/wwise-managed-v5-independent-review/` | Local official-source/API evidence and independent review pins for J759's AddBasePath filename diagnostic. Its v8 source and v8-r2 package plan are frozen within the preceding row's directories; retry binds the terminal build request, exact package-only receipt and all 41 input hashes. These inputs do not enable composed audio. |
| `work/coordination/wwise-android-fixture-draft/fixture-signing.*` | Disposable locally generated signing identity used only for standalone fixtures; key/password bytes must remain private. |

The protected candidates in `work/coordination/audio-r6-formatted-monitor-control/`,
`audio-formatted-native-root-build-plan/`, `audio-formatted-fixture-root-plan/`
and Root's `codex-audio-formatted-*` support directories are required local state
for the authorized isolated native/managed fixture. They retain reviewed SDK
source overlays, exact native build inputs, static audits and selected stage/build
proofs until public authored generators replace that local dependency. No current
game build reads these protected overlays; they remain ignored and do not enable
game audio. The current pre-strip inventory/comparison is retained under
`work/coordination/audio-current-player-closure-consumer/`.

These fixtures select explicit hash-bound inputs, not a timestamped run as a
mutable source. Raw device output remains local evidence. Their authored
drafts are an explicit reproducibility gap until reviewed generators are
promoted into the repository; do not make them a current game dependency or
infer full audio readiness from an isolated result.

The current `tools/wwise-android-abi/generate.py` support tool reads the accepted
`AK.Wwise.Unity.API.dll`, authorized Wwise Unity Integration
2023.1.8.8601.3208 Android declarations, handwritten Android OS-string helper
source and ARM64 Release plugin from the local
`work/wwise/` extraction. It uses Unity-bundled Mono.Cecil 0.11.1, the documented
`dotnet` runtime and NDK `llvm-nm`. The protected Integration inputs remain
local; the public recipe contains hashes, identifiers and authored policy.
The exact accepted-input ID must match that policy even for plan-only output.
One declared managed helper call changes to the matching Android byte-string
decoder; all other method bodies remain unchanged.
The generator writes new plans/candidates under ignored `work/`; neither SDK
inputs nor generated candidates enter the default game build. Synthetic test
scratch stays under ignored `work/tests/wwise-android-abi/`.


## Native source view camera Cecil resolver

`work/generated/native-view-camera/resolver-sets/` is generated local state. The
tracked `scripts/lab/native_view_camera_resolver.py` snapshots the current project's
managed plugin DLLs and the exact pinned Unity engine-module/Mono mscorlib references
into a deterministic hash-bound set. The producer verifies source profile, hashes,
identities and copied bytes; the transform records this resolver inventory separately
from the current-player linker input inventory. Do not read Bee or timestamped linker
capture directories as a camera-transform input. This narrow Cecil resolver is not a
player linker or IL2CPP closure, APK binding, or runtime proof.


Destination R8/R9 builds preserve the existing destination-selected work root and
project route. They restore an old camera result only when an owned receipt exists,
then do not generate camera resolver/output state. The runtime owner resolves the
merged marker by exact name and signature at creation; if a destination assembly lacks
it, explicit camera creation refuses. The standard current-project whole-catalog build
continues to stage the marker transform.


## LightningStake source-call observation

The observer has no new game-derived local input. Its only selection is the
existing default-off `lightningStakeSourceCallDiagnosticRequested` session
boolean. The accepted-input Cecil producer adds the runtime owner path and its
source hash to `transformation_source_hashes`; both the baseline and native
view-camera runtime source selections include the owner and its authored `.meta`
GUID. The next build must derive fresh composed/prestrip/poststrip hashes from
the replayed producer receipt; old camera/audio hashes do not identify these
new bytes. No runtime result or Android qualification is implied by a host
replay.


J1014's equipment-highlight owner adds no manually authored private input. Its
three source-key/path relationships are authored runtime metadata, and both
runtime-source manifests stage the owner with the GUID in `project-layout.json`.
`importer-identities.json` regenerates that script's importer. The audio owner
cohort and camera hook bind the updated sources. Replaying runtime-source and
importer staging reconstructs this dependency; no timestamped diagnostic output
is read by the runtime or build.
J1015 supplies the matching authored `.cs.meta` sidecar so current-project
staging can seed its fixed identity before first import, as required by J973.


### Optional catalog shader activation (J966)

`work/config/shader-catalog-overrides.json` is optional required local state for
activating the six generated shader candidates (J1012); historical exact two-row
receipts remain supported. It contains exactly `schema`
(`whole-catalog-shader-overrides-activation-r1`), accepted `input_id`, and boolean
`enabled`. Absence means off. This user-selected input-bound configuration has no
generator; the public recipe defines the permitted identities. It contains no
private path or device data. Malformed, foreign-input or symlinked state refuses.

`whole_catalog.prepare_integration` generates the per-attempt `shader-overrides.json`
and the selected project's `.rebuild/catalog-shader-overrides-receipt.json` mirror
and `.rebuild/catalog-shader-overrides.json` marker. These bind the local selector
and generated candidates, and are read by catalog verification and rebuild
comparison. A prior marker prevents disabling in place; use a clean destination.
Stable generated candidate paths are listed above; no build reads a timestamped
experiment folder as shader source.

## Named historical optional-guard evidence

Historical `./dev input-update-check` resolves
`work/config/historical-receipts/input-migration-optional-guards.json` before
creating an experiment or inspecting the live game. This is a selection of
retained evidence, not input acceptance or a new transformation. Its source
receipt must retain the original optional-guard method list, original/output
assembly hashes and successful preservation contracts. The original hash must
match `RoR2.dll` in the preserved baseline inventory. The source is read once
and SHA-256 checked; the result records the selected name, path and hash.

To migrate the old implicit J425 dependency, independently review and hash the
retained `optional-presentation-transformation.json` beneath the J425 source
root documented in [historical retention](history-retention.md), then explicitly
register it (replace both placeholders):

```sh
python3 scripts/lab/historical_receipts.py input-migration-optional-guards \
  work/RETAINED_EVIDENCE/optional-presentation-transformation.json \
  --sha256 REVIEWED_RECEIPT_SHA256
```

The generator refuses existing selections, unknown names, invalid contracts,
hash mismatches, symlinks and paths outside ignored `work/`. It does not discover
or trust a "latest" candidate, copy game data, modify original evidence, restore
retired trees or replace rollbacks. If an intentional selection change is needed,
preserve the old selection separately before registering the reviewed replacement.
Missing source evidence must be restored specifically using the retention policy;
do not fabricate it. No selection is shipped in Git. Once preserved baseline metadata is available,
a missing selection fails with registration guidance rather than silently
picking historical input. A fully fresh clone must first supply that baseline.

## Standalone requested-audio support evidence (J1056)

Ignored `work/coordination/owner-audio-stage-v1/` retains explicit planning/staging
invocations, ordinary assembly-transform scratch, strict generated request/stage
pins, supplied-native provenance and fresh observer/core/bootstrap outputs.
Its input producers are J1052, J1054 and J1055; source tools are the existing
`stage_original_game_banks.py`, `original_game_audio_produce.py` lower-level
compiler functions and request/stage generators. All three plugin references
are explicit; no Unity project or current selection is created. The private
instrumented native input remains the licensed local product documented above.

Setup uses the accepted original inventory, generated prefab/index/Init inputs,
pinned SDK compiler/reference tools and an explicit new ignored output root.
Teardown changes no shared state. The reviewed 274 generated stage payload
copies were retired after full readback; `staged-v1.retired.json` binds their
complete ledger, exact public generator/invocation and retained receipt. Restage
into a new explicit root before any future use; this evidence path is not a
live build input. Failed attempts, compiled outputs and all receipts remain.

## Standalone gameplay source evidence (J1057)

Ignored `work/coordination/owner-player-assemblies-v1/` retains the complete PC
contract/catalog read, exact three generated maps, fourteen recovered support
sources, all 145-source/243-reference manifests, official Newtonsoft package
acquisition, compiler/processor runs and compressed comparison reports.
Setup uses the accepted inventory, J1052's independently regenerated source,
J1053/J1056's outputs, original plugin recipes and explicit pinned SDK tools.
All support membership is specified separately from source/binary providers.
No project, runtime selection or device is created; teardown changes no shared
state. Source/output/hash proof and failed attempts remain private evidence.

The named generators are existing `CatalogContract`, `catalog_reader`,
`body_visual_map`, `common_assets_map`, the current public runtime recipe and
the existing compiler/reference/package owners. The final matching-SDK output
and fresh-processor output are separate from the earlier Mono compiler result.
These are experimental host artifacts, not current game-build inputs or proof
of full player/native equivalence. No protected source or compiled output is
published.

## Whole-player fixed-root feasibility evidence (J1058)

Ignored `work/coordination/owner-player-roots-v1/` retains a current R36-era root
snapshot explicitly labeled as comparison/configuration evidence, not R27 roots.
The fixture does not provide those full-player root files. Setup uses the
accepted original inventory, J1052/J1053/J1056/J1057 independent providers and
the exact owner SDK. Existing registry/metadata readers validate the input
identities; `phone_linker_roots` composes supplied project configuration with
SDK-native metadata. The current TypesInScenes/SerializedTypes, authored
preservation/Burst descriptors and module policy remain explicit required local
configuration until a minimum-identity publication audit and reproducible
configuration owner are integrated. No protected root table is embedded in code.

The standalone whole-linker input/provider manifest records all 332 DLLs and the
MCP developer-runtime exclusion. Its 93 stripped DLLs are the sole game-code
inputs to the whole-converter run. Generated C++/metadata, full SDK tool hashes,
commands, failed validations, exact-consumer observations and raw comparisons
stay private. SDK-derived decompiler snippets are protected research inputs and
must not be published. Setup/teardown neither reads a mutable current build
pointer nor changes the shared project/editor/device. None of these experimental
output paths is a current whole-catalog build input. Preserve the complete case
and proof before any specifically scoped source compression/retirement.

## Whole native-player feasibility workspace

Ignored `work/coordination/owner-native-player-v1/` owns the next experimental
native build from J1058's actual generated source, with explicit frozen native
command policy and exact supplied SDK compiler. It is not a Unity project or a
current game-build input. The generated native plan and retained SDK-source
hashes bind all commands/providers; only owned output paths may be written.

J1058's reviewed C/C++ source is now individually compressed under this
workspace's `source-store/`. `source-store-manifest.json` preserves every original
path/hash/size/mode/mtime and each gzip hash. The adjacent J1058
`whole-converter-v1/cpp.retired.json` points to that restore ledger. All 687 source
frames were decompressed and hash-verified before expanded copies were retired;
metadata, failed cases and all historical receipts stay intact. The private
native replay adapter restores one exact translation unit at a time and retains
verified object receipts. These frames and their restore ledger are required
local source state until the candidate is promoted or specifically retired;
never treat them as disposable cache. SDK/runtime source is read from the
explicit owner install and remains unmodified. Failed compilation keeps its
source and logs; successful source expansion can be restored from the frames.


## Public native owner inputs

The current experimental `tools/phone-build/owner-code/native.py` reads only
explicit absolute paths from a private owner request; it does not discover an
experiment or timestamped build. Required local state is the reviewed owner
inventory/configuration, the exact owner-supplied SDK (including its full NDK),
a successful converter result and its hash, all matching source files or gzip
frames, and that same converter's metadata. These protected/generated inputs
remain private because they cannot be supplied by the public repository.
The upstream converter generates source and metadata; `native.py` generates
all wrappers, commands, expansions, logs, object receipts, libraries and
terminal results in a new owner-work output. [Setup and lifecycle](../tools/phone-build/owner-code/README.md)
name each request field and explicit teardown. The current game build consumes
none of this state.

`work/coordination/owner-code-producer-v1/` retains the private configuration
normalization audit and complete public-source native planning comparison.
Its requests explicitly select the J1058 converter and J1059 source frames as
qualification providers; no tracked tool names those research paths. The
initial plan and later complete-NDK/provider-drift revision remain separate.
This is planning/migration evidence, not another native compilation or a
public-input bootstrap claim.


## Combined owner code backend

`tools/phone-build/owner-code/produce.py` consumes explicit private owner work,
SDK and a complete 332-entry basename/provider-path/SHA-256 map. The independently
produced managed cohort remains required local state until upstream orchestration
is integrated. It is not supplied by a project/captured build, and the current
game build reads none of these outputs. The tracked producer/profile and SDK
registry reader generate every new managed copy, root file, stripping output,
C++/metadata file, retained source frame, native request and terminal result.
[Setup and lifecycle](../tools/phone-build/owner-code/README.md#combined-whole-player-backend)
describe all explicit providers and exclusive private outputs.

`work/coordination/owner-code-producer-v1/public-backend-v1/` retains the initial
complete public-source host execution. `public-backend-v2/` is the final same
case with explicit interstage input checks. Both retain all 687 generated sources
as hash-verified gzip frames plus ledgers and data/metadata; the expanded owned
C/C++ copies were removed only after complete restore/hash verification. No
failed case or required input was retired. The generator does not read these
research paths implicitly. The final sealed proof covers the current source,
configuration, actual outputs and comparison to J1058. Native execution remains
J1059; these new attempts stop after native planning, not native compilation.


## Historical Init source compatibility owner

`tools/phone-build/owner-code/legacy_init.py` reads this checkout's explicit
owner `work` root, accepted inventory/configuration and the configured original
Init bank. Its exact authored source supplier is the audited tracked readable
`tools/phone-build/legacy/transform_init.py.txt`; no private experiment supplies
code. The wrapper generates a byte-identical private tool under
`work/legacy-init-tools/<owned-run>/transform_init.py`, preserving the historical
source-root lookup depth, and owns bank/receipt/log/result generation under an
explicit new private output. The materialized source path is recorded in that
output's result. [Setup/refusal/teardown](../tools/phone-build/legacy/README.md)
cover the fixed layout and both private output locations; retain failed cases.

`work/coordination/owner-code-producer-v1/public-legacy-init-v1/` records actual
public-wrapper execution and exact legacy output/receipt comparisons. The old
private source remains historical evidence only. No current runtime build reads
this new state automatically, and no archived SDK/game body is added.


## Original-input player-code owner

The `source_inputs` request mode of `tools/phone-build/owner-code/produce.py`
uses this checkout's reviewed canonical `work` state and original installation,
plus explicitly supplied SDK, package/tool and authorized Wwise inputs. Its
[ten-field setup](../tools/phone-build/owner-code/README.md#original-input-command)
includes the complete NETStandard reference package; no ambient framework cache
is needed by this mode. The raw producer retains its prior default for existing
callers. The instrumented native SDK product is a required explicit local input
because independent public production is still open; it is not a captured game
binary or claimed distributable artifact.

The tracked managed owner and existing called generators produce every raw
transform, package DLL, bank index, prefab, adapted Init/receipt, staged payload,
audio contract/pin/assembly, original decompilation, visual map, gameplay assembly
and full provider manifest. The existing backend produces all further code and
metadata outputs. No input code is read from a historical run implicitly. All
source/frame/receipt/log outputs remain ignored, and current game builds consume
none of this state automatically. Remove only explicitly owned outputs after
preserving required evidence; failed cases stay retained.

`work/coordination/owner-full-code-v1/` retains the initial nine-input host case,
then the explicit NETStandard-package/accepted-catalog guard revision. Both are
complete source-driven runs through native planning; their actual DLL/metadata
bytes differ with generated request/path identities. All source providers and
commands are recorded rather than normalized to an old build. A separate detached
qualification checkout may use another host volume for the full default native
run; it uses the same committed source and newly generated owner work, never a
shared Unity project. Its private location and ownership are recorded locally;
no device or storage configuration is changed.
