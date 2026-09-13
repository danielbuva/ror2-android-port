# Risk of Rain 2 Android porting laboratory

An evidence-driven local laboratory for investigating a native ARM64 Android port. **The game is not ported.** The current proof executes an original utility assembly through IL2CPP and renders a locally recovered mesh from an independently synced Android bundle on adopted storage, under GLES3 and Vulkan.

Start with [PORTING_STATE.md](PORTING_STATE.md), [ADR-001](docs/ADR-001-port-architecture.md), [journal](docs/PORTING_JOURNAL.md), then [milestones](docs/milestones.md). The bootstrap report remains under environment/.

## Local setup

The prepared environment already contains the exact Unity/Android toolchain and inspection tools. `./scripts/lab-setup.sh` restores the pinned Python laboratory dependencies if needed. Copy environment/lab-config.example.json to ignored work/config/local.json and supply the legitimate installation path and explicitly authorized device serial. Never copy the original installation into tracked directories.

`./dev inspect --full` creates a reviewed input identity. Initial/updated inputs must be reviewed before recording that ID in work/config/accepted-input.json. The current workstation already has this configuration and accepted baseline. No Steam authentication is needed to inspect the supplied installation.

## Command interface

| Command | Actual behavior |
| --- | --- |
| `./dev test` | Run isolated host safety guard tests. |
| `./dev doctor [--json]` | Bootstrap health plus local inventory, dependency pins and historical lab checkpoint. |
| `./dev inspect [--full]` | Hash files, identify build, scan managed metadata and native PE dependencies; update diff. |
| `./dev graphics` | Per-file cached Unity content/settings/shader/material/bundle inventory. |
| `./dev decompile [--assembly RoR2.dll]` | Local ilspycmd C#9 project export with per-assembly receipts. |
| `./dev export-project` | Cached AssetRipper local reconstruction with pinned settings; starts local service if needed. |
| `./dev prototype` | Stage source-owned harness, one original utility DLL and one converted mesh under work/. |
| `./dev prototype --action dependency-boundaries` | Attribute original/exported Rewired differences and record the bounded original-code probe. |
| `./dev prototype --action rewired-original` | Test the J09 virtual slots using original DLL inputs on ARM64; no controller initialization claim. |
| `./dev prototype --action collections-runtime` | Pinned native-list/job candidate on editor and Android; package resolution required before probing. |
| `./dev prototype --action ror2-slice` | Original trajectory/proc-mask IL with three cold-start assertion/survival runs; not full game closure. |
| `./dev prototype --action middleware` | Exact native Wwise version and bank metadata evidence. |
| `./dev prototype --action recompile` | Full recovered RoR2 source compile probes using modern and Unity compilers. |
| `./dev prototype --action reconstruction` | Export scene/shader/source summary. |
| `./dev prototype --action repair-reconstruction` | Apply only the recorded, input-gated ambiguous-type qualification patch. |
| `./dev prototype --action references` | External-GUID audit of generated Assets YAML, with explicit coverage limits. |
| `./dev prototype --action storage-lifecycle` | Disposable install, unchanged sync, update retention and cleanup test. |
| `./dev editor --target lab --action open` | Start isolated exact editor and connect pinned MCP. Use reconstruction or smoke for other known projects. |
| `./dev editor --target lab --action inspect` | Guarded MCP project/hierarchy/console inspection. |
| `./dev preflight` | Input acceptance/drift, tracked-file policy, toolchain pin, host/device storage checks. |
| `./dev build --target gles` | Instrumented IL2CPP ARM64 build through MCP; content-addressed APK receipt. Vulkan also supported. Editor must be connected. |
| `./dev install` | Install current build on live adopted volume; reject foreign pre-existing package; record placement. |
| `./dev run` | Launch lab, wait for checkpoint, collect runtime path/snapshot. |
| `./dev sync-data` | Hash-verified changed payload sync into the runtime-reported path. Run once before initial sync. |
| `./dev diagnostics --subtree NAME --fields` | Change runtime snapshot scope without rebuilding; `--disable` stops periodic snapshots. |
| `./dev logs / crash / screenshot / perf` | Timestamped local capture directory. |
| `./dev reset` | Uninstall only the locally receipted disposable lab package. |
| `./dev smoke --target gles` | Build/reuse, install, discover paths, sync, run, collect and clean up a fresh disposable install. |
| `./dev storage` | Live capacity/volume/backing report; no storage changes. |

Normal iteration with a connected editor: `./dev smoke --target vulkan`. For an installed development package: build → install → run → sync-data → run → capture; unchanged payload hashes are skipped. Keep one editor mutation active at a time. The full reconstructed project's Play Mode currently crashes; read the journal before repeating it.

Output roots: work/inventory, work/decompiled, work/assetripper, work/lab-project, work/build-cache, work/generated-android-data, work/runs, work/editor and work/experiments. `work/runs/latest.json` points to the latest attempt; each run result records its APK hash. No hidden manual APK copying is needed.

## Scope and distribution

Repository content is original tooling, small transformations and evidence summaries. User-supplied game data and generated proprietary content are Git-ignored. No DRM/ownership/authentication bypass is included. Middleware licensing/Android binaries remain unresolved. Do not redistribute raw work/ outputs.

The adopted-storage policy and limits are in [storage strategy](docs/storage-strategy.md). Diagnostics/acceptance limits are in [testing strategy](docs/testing-strategy.md); cache and update behavior are in [caching and updates](docs/caching-and-updates.md). Host safety checks: `.local/lab-venv/bin/python -m unittest discover -s tests -v`.
