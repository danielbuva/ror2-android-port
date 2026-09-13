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
| `./dev prototype --action original-closure-prepare` | Stage original full managed inputs and package providers; preserve provenance. |
| `./dev prototype --action original-closure-build` | Force full RoR2 AOT build with terminal evidence; no automatic game startup. |
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

Full original assembly assertion experiment: `./dev prototype --action original-closure-runtime` after original-closure-prepare/build. Reuses the ten game-method assertions on three cold launches and verifies unchanged input DLL hashes; does not initiate game startup. Passing stages are archived under ignored experiment evidence.

L4 scoped audit: `./dev prototype --action scene-closure` writes immutable loadingbasic/CommandoBody YAML closures under work/experiments/scene-closure. Imported subassets and runtime dependencies are explicitly unresolved by this text scan. The authored ReferenceIdentityProbe editor menu consumes an ignored Assets/LabReferenceQuery.json (attempt, output, path/fileID queries); after its import/refresh has completed, `./dev editor --target <lab|reconstruction> --action reference-identities` records imported identities without Play Mode or prefab instantiation. Keep each query configuration and result with its attempt.

Loading scene experiment: `./dev prototype --action scene-prepare`, then wait for `./dev editor --target lab --action refresh` to finish and run its `reference-identities` action. `./dev prototype --action scene-arm` validates the four UI identities and deactivates only the recorded RoR2Application object for a content-only probe. Run `./dev build --target vulkan --force`, then `./dev prototype --action scene-run`. This does not pass startup/authentication. Preserve the stage and work/scene-probe-build.json with the attempt; remove only those experiment-owned files after recording the result. Never run scene-arm on an already transformed stage.

Commando content audit starts with `./dev prototype --action prefab-prepare`. The prefab deliberately lacks its runtime-loaded mesh/material/animation data. `CatalogAddressProbe` reads an ignored Assets/LabCatalogQuery.json (catalog, output, attempt, keys) through `./dev editor --target lab --action catalog-addresses`; it decodes locations without loading providers or services. Preserve typed catalog results for the measured default-skin keys before `./dev prototype --action prefab-bind`; that action stages six default assets plus their static dependencies. Validate the resulting identity query, then scene-arm/build/scene-run. Binding is performed only on an inactive diagnostic clone and does not establish original skin-loader or character-simulation behavior.

L4 visible-content replay: `./dev prototype --action pose-prepare` restores the local accepted inactive-prefab checkpoint, followed by a forced Vulkan build and `./dev prototype --action scene-run`. The probe requires current-launch bone results and two valid pose captures. Original gameplay remains inactive. Preserve/classify each stage before a retry.

Original controller lifecycle: `./dev prototype --action controller-prepare` restores accepted content and stages one typed request with the original Addressables providers. Force a Vulkan build, then run `./dev prototype --action controller-run`. The current-PID report must pass real initialization, shared ownership, delayed release/reload and invalid-key/type checks over 50 seconds. Original application, profile and character startup remain inactive; cleanup ticking is explicitly diagnostic. Preserve/classify each attempt before preparing another. The experiment stages `ControllerAddressLink.xml` as `ControllerPreservation/link.xml` to retain measured reflection-created operations; input DLLs remain unchanged.

Public-repository hygiene: stage only authored tooling and reviewed summaries, then run `python3 scripts/audit-public.py`. Bootstrap captures remain ignored locally so existing health checks still work. See [privacy/IP audit](docs/public-repo-audit.md) for scope, removals and history limitations.

Avatar subobject lifecycle: `./dev prototype --action avatar-prepare` restores the accepted controller stage, validates original GUID/subobject and imported Avatar identity, and maps that compound key to the recovered standalone asset. Force a Vulkan build and use `./dev prototype --action controller-run` for the shared typed-request harness. Avatar name/validity, bundle asset identity, ownership/reload and missing-subobject/wrong-type checks must pass. Skin baking and application remain separate.
