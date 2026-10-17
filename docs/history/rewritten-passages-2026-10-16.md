<!-- Archived verbatim on 2026-10-16: passages of af2e101 entry docs that the cleanup rewrote. Current versions are the files themselves. -->

# Rewritten passages (2026-10-16)

Each section quotes, unchanged, the paragraphs of one document at `af2e101` that no longer
appear anywhere else in the repository. Only link targets were adjusted so they resolve from
this folder.

## `README.md`

An evidence-driven local laboratory for investigating a native ARM64 Android port. **The game is not ported.** The current proof executes an original utility assembly through IL2CPP and renders a locally recovered mesh from an independently synced Android bundle on adopted storage, under GLES3 and Vulkan.

Start with [PORTING_STATE.md](../../PORTING_STATE.md), [ADR-001](../ADR-001-port-architecture.md), [journal](../PORTING_JOURNAL.md), then [milestones](../milestones.md). The bootstrap report remains under environment/.

The prepared environment already contains the exact Unity/Android toolchain and inspection tools. `./scripts/lab-setup.sh` restores the pinned Python laboratory dependencies if needed. Copy environment/lab-config.example.json to ignored work/config/local.json and supply the legitimate installation path and explicitly authorized device serial. Never copy the original installation into tracked directories.

Storage defaults to `"storage_mode": "adopted"`. An explicitly authorized internal-only device can use `"storage_mode": "internal"`; live checks reject an unexpected adopted volume and verify installation under internal app storage. Preserve the previous device's local configuration and ownership receipts before switching devices. Optional `"apk_install_limit": 1` counts installation dispatches for the selected device, including unknown outcomes. After that dispatch, only the identical receipted APK may be reused; replacing or uninstalling it does not reset the limit.

`./dev inspect --full` creates a reviewed input identity. Initial/updated inputs must be reviewed before recording that ID in work/config/accepted-input.json. The current workstation already has this configuration and accepted baseline. No Steam authentication is needed to inspect the supplied installation.

The adopted-storage policy and limits are in [storage strategy](../storage-strategy.md). Diagnostics/acceptance limits are in [testing strategy](../testing-strategy.md); cache and update behavior are in [caching and updates](../caching-and-updates.md). Host safety checks: `.local/lab-venv/bin/python -m unittest discover -s tests -v`.

Public-repository hygiene: stage only authored tooling and reviewed summaries, then run `python3 scripts/audit-public.py`. Bootstrap captures remain ignored locally so existing health checks still work. See [privacy/IP audit](../public-repo-audit.md) for scope, removals and history limitations.

Official Rewired trial evaluation: `./dev prototype --action rewired-trial-inventory` compares the ignored active reference attempt with the accepted input. `./dev prototype --action rewired-trial-run` observes its completed SDK-only Android build on Nova for 90 seconds, restores the previously owned APK and sleeps the display. Prepare/import/build only in `rewired-trial-reference`, never the accepted lab. See [measured compatibility and scope](../rewired-trial-reference.md); the current trial is not a drop-in game replacement.

Temporary Nova input producer: `./dev prototype --action nova-bridge-prepare`, restore measured motor/producer order, force Vulkan build, then `nova-bridge-raw-run`, `nova-bridge-bind` and `nova-bridge-commando-run`. This feeds original InputBankTest without replacing gameplay or Rewired; skill execution is disabled for the movement proof. See [scope, measured mappings and rollback](../nova-input-bridge.md). Exact Rewired compatibility is deferred by current user direction.

Original primary boundary: `./dev prototype --action primary-fire-prepare`, pinned editor refresh, preflight and forced Vulkan build, then `primary-fire-run` isolate original factory/activation and the first unmodified native firing consumer. The dependent firing case dispatches only after the contract passes. See [accepted scope and next probe](../commando-primary-boundary.md).

Persistent integration: `./dev prototype --action nova-whole-game-prepare` composes the recovered stage/player/combat/director/local authority/rewards/interactables/loot into one live session. Use the existing preflight, forced Vulkan build and movement-batch runner. See [integration scope and limitations](../whole-game-integration.md). This does not bypass the documented stock startup/platform gate.

Source-guided Android presentation: `./dev prototype --action presentation-payload` rebuilds only the fixed presentation shader families for the currently owned Vulkan APK. `./dev prototype --action stage-presentation-payload` restores original RenderSettings/lights and rebuilds the five existing base-stage bundles. Each keeps separate request/start/terminal and payload receipts; the next same-APK retry syncs only changed files. These actions require the installed APK to match the selected build, preserve unrelated payload hashes and leave Moon unchanged. Replacements are explicitly approximations: the original PC build is the visual authority. See [restoration evidence and remaining gaps](../visual-restoration.md).

Shipped shader recovery: `./dev prototype --action shader-recovery` reads the accepted original Cloud Intersection shader and runs the pinned Unity_Shader_Decompiler, d3dasm, HLSLDecompiler and dxbc-spirv on the same measured vertex/fragment pair. It requires the already built, ignored reference tools and isolated analysis bottle; it does not install dependencies or change the game, Unity project or device. Each attempt retains private input/output hashes, command results, DXBC roundtrip and HLSL compilation checks. Generated ShaderLab has known reconstruction errors; successful execution is not semantic equivalence or Android/PC parity. See [recovery findings and exact prerequisites](../shader-recovery.md).

`./dev prototype --action shader-source-deferred` generates a private Standard/custom-lighting candidate from an explicit `work/config/shader-deferred-analysis.json` selection: `standard` and `lighting` are repository-relative analysis directories; `material_inventory` and `material_inventory_sha256` identify the measured original material closure. It verifies accepted native trees/pins/roundtrips, retains measured feature combinations and independently compiled shadow fallback, and rejects unknown consumed contracts. Stage sources only into the ignored lab project. Original custom reflections require the separately receipted material-family selection; HDR/FP16/deferred settings and actual device target formats are part of this pipeline's contract. Full builds now reject nonzero shader/player errors even if Unity reports Succeeded. J369 runs the recovered candidate through the composed game; source semantics and PC appearance remain unproven. See [native pipeline findings](../shader-recovery.md).

Whole-catalog discovery uses `./dev prototype --action whole-catalog-audit`, followed by `whole-catalog-native`, `whole-catalog-reconcile` and `whole-catalog-contracts`. These read the complete shipped graph and emit ignored typed/provenance records. They do not load/register the complete game or install an APK. See [the current integration findings](../whole-catalog-integration.md); import/build remains gated by live headroom and original platform/ownership boundaries.

## `AGENTS.md`

Read `PORTING_STATE.md` first, then `environment/ENVIRONMENT_REPORT.md` and the relevant ADRs. Run `./dev doctor`. Read `docs/PORTING_JOURNAL.md` before repeating a failed experiment. This is a laboratory, not a working game port. Agent #3 should use the evidence to prepare a plan; do not infer game readiness from G2.

After meaningful progress update concise PORTING_STATE.md, append failed experiments with evidence/revisit conditions to docs/PORTING_JOURNAL.md, and maintain milestones/backlog. Commit small logical changes after checking staged files for proprietary material. Avoid unrelated rewrites. Read ADR-001 before changing architecture.

## `docs/ADR-001-port-architecture.md`

Consequences: source patches are targeted and input-version gated; extracted assets remain local; native services are isolated deliberately; Android content is built with exact Unity 2021.3.33f1. IL2CPP changes require APK builds even when DLLs are preserved. Pure asset changes can use separate payload sync. Small proof success must not be extrapolated to whole-game AOT/serialization compatibility.

## `docs/DEVELOPMENT_PLAN.md`

Each issue uses the full schema in execution-backlog.md. Preserve attempt evidence, update concise PORTING_STATE.md after meaningful progress, append failures and revisit conditions to PORTING_JOURNAL.md, update milestones/backlog at gates, review staged files and commit coherent changes. Split tasks that expand. A failed discriminating experiment can complete an issue without passing its milestone.
