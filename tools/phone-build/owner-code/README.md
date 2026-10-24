# Editor-free owner code producer

Current experimental build support. The complete host chain is established in
[J1052–J1059](../../../docs/JOURNAL_INDEX.md); promotion into one public command
is in progress. This directory owns the native stage. No current game build
selects it. Architecture C and the desktop fallback remain unchanged.

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
including 687 independently restored source frames, exactly. It is not a new
native compiler execution: J1059 remains that evidence. Default complete native
execution through this controller, integration of upstream managed production,
full content/Burst/shaders, Android hosting/install/update and device behavior
remain open. The current game build consumes none of this state.
