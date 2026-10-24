# Editor-free owner code producer

Current experimental build support. The complete host chain is established in
[J1052–J1059](../../../docs/JOURNAL_INDEX.md); the source-input command below now composes the managed and native stages.
J1063 qualifies the complete default source-input host chain through native
linking. Full-player Android construction remains open. No current game build
selects it. Architecture C and the desktop fallback remain unchanged.

## Fixed accepted source target

An optional `target` selects an explicit public profile and its separate authored
source root: `{"profile": "ABSOLUTE_PROFILE_JSON", "source": "ABSOLUTE_SOURCE_ROOT"}`.
`recipe/owner-j850-code.json` pins 114 public inputs from commit
`1780ea9545f1597c033a8d32e08074b03c7f38c8`, including its 111 runtime sources.
Supply that public commit's files, for example with `git archive`; every selected
file is checked against the profile before and after production. No source is
read from the moving checkout in place of those target files.

In this pre-audio target mode, `source_inputs` has exactly five owner paths:
`packages`, `newtonsoft`, `dotnet`, `ilspy_dll` and `archives`. The first four
retain their meanings below; `archives` is the existing public transform tool
archive cache. The existing public producer compiles its Cecil/provider tools
and retains all three golden DLL gates. The package owner produces the four
package assemblies; the target's authored sources and fresh original-source
support/maps then produce the gameplay assembly. The complete 329-provider
cohort feeds the same backend. The developer-only MCP DLL is excluded.

The target profile reuses explicit fixed scene/module preservation configuration;
this is not independent scene inference or a claim of accepted byte parity.
Its actual converter outputs determine all generated native translation units,
while SDK compilation templates/lumps and link settings remain pinned. Native
planning/linking includes every source from that conversion. Raw target hashes,
types, behavior and performance remain comparison gates; differences stay visible.

The optional `android_tools` dictionary supplies canonical paths for `dotnet`,
`clang`, `linker`, `objcopy` and `resource_dir`. These replace host executables
only. .NET 8 runs the unchanged SDK linker/converter; Android Clang/LLD uses
the original NDK target headers/static C++/ABI/GCC archives. Clang 21/LLD is
explicitly different from the desktop Clang 9/BFD control. Tool/resource hashes,
original SDK and provider inputs are rechecked. Every attempt owns its output,
logs, exact commands and failed state; process-group cleanup remains active.

`run_android.py` connects this backend to the headless managed-host fixture.
It verifies the caller's private input manifest, checks every copied original
game hash, and records the copy's actual timestamps without changing its content
identity. Original/SDK/provider files stay outside the tool APK. Runtime tools
are PackageManager-installed read-only native files; framework/source/input data
remain private app data. The caller owns installation receipts, input transfer,
kernel thermal monitoring, independent output comparison and teardown. No game
launch, default build pointer or installer action is performed by this entry.
Its measurements distinguish backend wall time, Python/child peak RSS and live
free space. Copy/initial admission time and game performance are separate.

`native.py` replaces the private captured native DAG with the audited
`recipe/owner-native-arm64.json`. The profile contains six argument templates,
SDK-relative source/lump relationships, generated translation-unit names and
link ordering. It contains no SDK source, generated game C++, objects or library.
The fixed membership describes the qualified current player configuration;
new translation units require an explicit profile review, not silent omission.

Run with the repository Python environment:

```sh
python tools/phone-build/owner-code/native.py /absolute/owner/request.json --plan-only
python tools/phone-build/owner-code/native.py /absolute/owner/new-request.json
```

Each invocation needs a **different new output directory**. Requests have exactly
these fields (all filesystem paths are explicit absolute canonical paths):

| Field | Required input |
| --- | --- |
| `owner_work` | Private owner work root with reviewed `config/local.json`, `config/accepted-input.json` and `inventory/files.json`. |
| `sdk_install` | Owner's exact Unity 2021.3.45f2 macOS ARM64 installation, including original Android NDK 21.3.6528147. |
| `converter_receipt` | Successful complete converter result with `exit_code: 0`, `inputs_unchanged: true`, and a `files` map of relative paths to `bytes` and `sha256`. |
| `converter_receipt_sha256` | Explicit hash of that result. |
| `sources` | Directory containing the converter's 687 C/C++ files by basename, or individually compressed equivalents. |
| `sources_compressed` | Boolean: when true, each source filename has an additional `.gz` suffix. |
| `metadata` | The same converter's `data/Metadata/global-metadata.dat`. |
| `output` | New private directory inside `owner_work`, disjoint from every input and configuration directory. Its parent must exist. |

The owner checks the accepted installation inventory before/after, pins the
12,250 SDK/tool/source-file cohort through a portable aggregate hash, including the complete NDK tree (BFD, implicit
headers, CRT objects, libraries and compiler runtime), and binds
all source providers and metadata to one converter receipt. Planning writes the
complete commands and verifies provider hashes; execution additionally verifies
every expanded source against the converter's size and SHA-256 before compiling.
It never needs an Editor project, a captured DAG or an experiment directory.
The upstream producer must supply the actual fresh converter outputs explicitly;
this stage alone does not produce managed assemblies or content.

One compiler process runs at a time. Exact original SDK Clang 9/BFD, ARMv8-a,
Android API 22, Os/development and incremental-GC settings are retained. A new
output owns wrappers, temporary source expansions, commands, logs, object
receipts, the unstripped library, a separately stripped library and terminal
result. Successful generated-source expansions can be removed after their
object receipt; original providers stay untouched. Failure preserves the output,
active source and logs; automatic restart/reuse is not implemented. Interruption
kills and reaps the active tool process group. Compilation and linking enforce
separate capacity reserves. No installation, device, shared Editor mutation or
current-pointer update occurs. After review the owner can remove only its own
output directory; input archives, SDK and original installation remain required.

`--plan-only` makes no compilation/runtime claim. Public-source planning is
compared against all 825 proven compile commands, all link arguments and all
67 SDK-only lump cohorts after explicit output relocation. A new full compilation
through this public entry, Android tool hosting, Burst, content/shaders and
matched device behavior/performance remain separate acceptance gates. The
macOS compiler here is the original-policy control, not the final phone tool
host or distribution experience. Supplied SDK binaries are never published.

## Combined whole-player backend

`produce.py` joins fixed target roots, whole-player stripping, IL2CPP C++/metadata
conversion, exact source-frame preservation and the native owner above. It uses
`recipe/owner-player-code.json`, with no captured DAG, response file, generated
project root file or native registration table as an execution input.

```sh
python tools/phone-build/owner-code/produce.py /absolute/owner/backend-request.json
```

The request contains exactly `owner_work`, `sdk_install`, `managed`, and `output`.
The first two paths and new private output follow the native owner's path rules.
`managed` maps each of the 332 required DLL basenames to exactly `path` (canonical
absolute provider file) and `sha256`. Upstream producers must generate these
providers; this command does not yet invoke their managed-production stages.
Original PC/SDK files and freshly produced transforms/packages/gameplay/audio
assemblies are explicit providers, with hashes checked before copying and at
stage boundaries. The developer-only MCP runtime is excluded. No project oracle
or private provider lookup is used.

The audited target profile contains only scene/type identities, retention XML,
module policy, assembly membership/order and hashes of 309 SDK tool/config files.
It records current R36-era target configuration with original conservative
Android IL2CPP development policy, not independent scene inference or R27 roots.
The four observed Burst selectors remain literally configured; their presence
does not prove that each selector resolves. The existing static SDK reader
reconstructs the 318-entry native table from the owner's pinned Unity executable
without running the Editor. That generated table stays private.

The controller writes private `managed/`, `configuration/`, `stripped/`,
`converter/`, `sources/`, tool logs, exact commands, source-frame records and
terminal result. It checks source providers, staged DLLs, root configuration and
SDK inputs between expensive stages. Every generated C/C++ source is compressed
and fully restored/hash-verified before its owned expansion is removed; source
to source includes refuse pending qualification. The exact frames and same
converter metadata feed `native/`. All failure artifacts remain; there is no
implicit retry, restart, lab/current pointer update or installer. An owner may
remove only this explicit output after preserving any required evidence; original
providers, SDK, inputs and other outputs remain untouched.

`--stop-after-conversion` runs the complete stripping/conversion/preservation
stages and **only plans** the native stage. The recorded host case reproduces
all 94 prior stripped outputs and all 691 prior C++/metadata output records,
including 687 independently restored source frames, exactly. The later full default source-input run in J1063 executes the complete native
stage successfully. Full content/Burst/shaders, licensed native input production,
Android hosting/install/update and device behavior remain open. The current game
build consumes none of this state.


## Original-input command

The same `produce.py` entry also accepts `source_inputs` instead of `managed`.
It generates all 12 non-original managed providers and assembles the complete
332-provider cohort before running the backend above. No prebuilt game DLL,
decompiled source folder, exported asset, captured graph or historical run is
an input to this mode. The qualified target is the current diagnostic player
configuration; this is not accepted-APK byte parity or a new runtime selection.

The request has exactly `owner_work`, `sdk_install`, `source_inputs`, and new
private `output`. This mode currently requires this checkout's canonical `work`
root, because existing strict audio contracts and the archived Init tool use
that layout. Owner inventory/configuration and original game files must already
be reviewed. `source_inputs` has exactly these canonical absolute paths:

| Field | Owner-supplied input |
| --- | --- |
| `packages` | The pinned package source root described in the package producer README (including UI, Burst, Mathematics, Collections and their required helpers). |
| `netstandard_ref` | Complete NETStandard.Library.Ref 2.1.0 package directory; copied into an isolated offline cache. |
| `newtonsoft` | Official Newtonsoft package 3.2.1 AOT Newtonsoft.Json.dll, pinned by hash. |
| `dotnet` | The existing qualified .NET SDK host executable (current host control uses .NET 10). |
| `ilspy_dll` | ILSpy 11.0.0.9375 CLI assembly, executed only as a decompiler under that host. |
| `decoder` | The pinned vgmstream executable for required metadata qualification on a temporary bank copy. No audio playback occurs. |
| `wwise_android_source` | Owner's authorized Android PINVOKE declarations. |
| `wwise_os_string_source` | Matching authorized Android handwritten declarations. |
| `wwise_abi_native` | Matching generic Release ARM64 SDK library for static ABI inspection. |
| `wwise_native` | The explicitly supplied hash-bound instrumented SDK product required by existing audio contracts; independent production remains open. |

```sh
python tools/phone-build/owner-code/produce.py /absolute/owner/source-request.json
```

`--stop-after-conversion` runs all managed production, stripping, conversion and
source preservation, then only plans native compilation. Default execution
continues to the native library. Source mode first runs the existing raw managed
producer, package compiler and original-assembly transforms; reproduces the bank
index, prefab and exact historical Init receipt; stages all requested banks/media;
uses unchanged lower-level audio contract/pin generators and compilers; derives
maps from the actual original catalog/IL and freshly decompiles the selected 14
support sources; then compiles/post-processes all 145 gameplay sources. The three
runtime request/stage/project admissions remain intact. No fake project is used.

`recipe/owner-managed-code.json` contains only minimum provider paths/hashes and
support selection identities. At stage boundaries the owner rechecks original
state and bound source/tool inputs. It retains all new private outputs and the
complete provider manifest. Setup creates no shared Editor/device state; teardown
removes only the explicit owned output after preserving required evidence, plus
the recorded owned legacy tool materialization if no longer needed. No automatic
retry or current-build pointer change occurs.

The raw managed producer's optional `--netstandard-ref` accepts explicit package
input while preserving its existing host-cache default. Its actual source hash
pin is refreshed with that API change. Generic transform/decoder helpers likewise
accept explicit tools with their default callers unchanged. No network package
restore, installer, license acceptance or original input mutation is added.

[J1063](../../../docs/PORTING_JOURNAL.md#j1063--complete-the-source-input-host-native-owner-build)
executes this default source-input command through all 332 providers, 93 stripped
DLLs, 691 converter outputs, 687 checked frames and 825 actual native tasks plus
link and strip. Main independently verifies the sealed host evidence. Fresh
request/path identities change DLL/metadata bytes; bounded projections do not
establish native equivalence. Licensed native input production, Burst/content/
shaders, phone hosting, installation/update and matched game behavior/performance
remain gates. This host control does not commit the final installation experience
to a desktop.
