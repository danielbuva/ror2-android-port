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

Skin baking: `./dev prototype --action skin-prepare` measures default renderer/mesh paths from serialized prefab references and adds the deferred parameter asset to the accepted content. Force a Vulkan build and run `./dev prototype --action controller-run`. The shared probe checks original BakeAsync output and parameter release over 70 seconds; it does not apply the skin or activate gameplay.

Skin application: `./dev prototype --action skin-apply-prepare`, forced Vulkan build, then `./dev prototype --action controller-run` uses the existing 70-second lifecycle. Original ApplyAsync must populate initially empty mesh components and CharacterModel material records on an inactive model, then release acquired material/mesh handles. Live renderer material updates, startup and simulation are separate gates.

Startup segment: `./dev prototype --action startup-prepare`, forced Vulkan build, then `./dev prototype --action startup-run` restores the accepted skin stage and tests independent Android-owned Zio profile/content roots plus the original first startup yield and reviewed PreFrame phase over 50 seconds. It never resumes later audio/platform/save initialization or calls application Awake. Profile assertions use a disposable sentinel, not the game save format; filesystem reopen is not a cold-launch save test. Preserve the first exception and stage before changing a boundary.

Startup loading-scene handoff: `./dev prototype --action startup-scene-prepare`, forced Vulkan build, then `./dev prototype --action startup-run` tests the real recovered loadingbasic scene, Canvas/percentage references and two original frame yields. It stops before component enabling and audio.

Manual device use: the launcher name is **RoR2 Porting Lab**. In-place updates retain data and skip unchanged payload files. The user also permits clean installs/cleanup when they simplify an experiment; retaining the app is optional. Use the existing ownership/storage safeguards and preserve relevant profile/rollback evidence before resetting. The current app is a laboratory probe, not a playable game.

Recovered application initialization: `./dev prototype --action startup-application-prepare`, forced Vulkan build and `./dev prototype --action startup-run` extend the loading-scene proof with explicit original Awake on its inactive recovered component. Verify the loading flag was established by the original routine, singleton/build/type identities and disabled component list. This does not activate the application game loop or its startup components.

Global texture initialization: `./dev prototype --action startup-textures-prepare`, forced Vulkan build and `./dev prototype --action startup-run` measure three scene texture GUID/PNG identities, then call original GlobalShaderTextures.Start on its recovered inactive component. The probe clears only those globals to establish a before/after assertion, checks exact runtime bindings, and restores previous values. This is a method and reference proof, not final shader rendering or automatic lifecycle.

Interpolation timing: `./dev prototype --action startup-interpolation-prepare`, forced Vulkan build and `./dev prototype --action startup-run` invoke original Start/FixedUpdate/Update on the recovered inactive interpolation component. The probe records real fixed/render timestamps, checks eight interpolation results and two-sample history, then restores prior state. Diagnostic scheduling does not establish automatic Unity lifecycle or character movement.

Frame queue: `./dev prototype --action startup-fps-prepare`, forced Vulkan build and `./dev prototype --action startup-run` verify original FPSQueue.Start adds its expected callback, then invoke only that callback over 36 measured frames. Rolling average, sample/turn/slot wraparound and throttling decisions are checked; previous subscription/static state is restored. This is not a gameplay performance measurement or full application Update test.

Scene acceptance now checks that the lab is Android’s resumed activity before accepting a capture. A passing runtime marker paired with another foreground app fails acceptance; activity dumps and screenshots remain private local evidence.

Postprocessing volume: `./dev prototype --action startup-volume-prepare`, forced Vulkan build and `./dev prototype --action startup-run` audit both serialized profiles and their setting flags, then explicitly call the first original volume’s OnEnable/Update/OnDisable. Manager registration and component state must balance. This does not enable postprocessing rendering or establish the second volume’s lifecycle.

Volume ordering: `./dev prototype --action startup-volume-order-prepare`, forced Vulkan build and `./dev prototype --action startup-run` register both recovered volumes in descending priority order, then verify original GrabVolumes returns ascending priority for their actual layer and excludes them from a zero mask. Original unregistration must restore the prior registration/query lists; no rendering claim.

NGSS initialization: `./dev prototype --action startup-ngss-prepare`, forced Vulkan build and `./dev prototype --action startup-run` verify the staged recovered-source hash, serialized noise texture, and eight shader values across explicit OnEnable/Update/OnDisable. Previous globals restore. NGSS is locally recompiled recovered code, not a preserved original DLL; rendered shadows and the missing-noise fallback remain unproven.

Integrated pre-audio startup: `./dev prototype --action startup-integration-prepare`, forced Vulkan build and `./dev prototype --action startup-run` use a fresh recovered application to own the original routine. After its natural loading-state setup, Unity activates the host and executes automatic callbacks; the routine advances through the six-component enable step and stops before Wwise. Exact callback closure, real loop counters, active component states and late errors are checked. No menu or audio initialization claim.

Audio prefab loading: `./dev prototype --action audio-assets-prepare`, forced Vulkan build, then `./dev prototype --action startup-run` extends the controlled pre-audio segment with original legacy-path asset loads. It checks result status, prefab/component identity, pending counts and handle release without instantiating audio objects. Native audio and bank compatibility remain separate.

Native audio availability: `./dev prototype --action audio-native-prepare`, forced Vulkan build and `startup-run` add one original sound-engine status query after the asset-only checks. The current absent-runtime hypothesis requires an actual `DllNotFoundException`; other outcomes require reassessment. This reports audio unavailable and does not initialize audio or substitute native success.

Unavailable-audio continuation: `./dev prototype --action audio-guard-prepare` creates an input-gated local RoR2 assembly candidate whose optional no-audio getter reports true. After successful preparation only, force a Vulkan build and use `startup-run`. The probe resumes the original initializer and Addressables yields, stopping before filesystem/platform initialization. Original and transformed hashes remain separate; this is not complete no-audio or menu acceptance.

Profile binding: `./dev prototype --action profile-binding-prepare`, followed by a successful forced Vulkan build and `startup-run`, temporarily binds separate writable Android app-data/profile roots. It invokes the original private filesystem setter and configuration writer/reader, verifies isolation and restores globals. This is a sentinel/configuration probe, not profile serialization or platform startup. Read-only payload storage stays separate.

Steam failure boundary: `./dev prototype --action steam-boundary-prepare`, successful forced Vulkan build and `startup-run` exercise original callback registration/load/unload. The probe requires the observed false load result, untouched filesystem globals and restored callbacks. No ownership/authentication success is substituted; the original catch still hides the failure cause.

Steam first-failure attribution: `./dev prototype --action steam-exception-prepare`, successful forced Vulkan build and `startup-run` invoke the original private constructor through reflection before any normal load callback in that process. It requires a fresh Facepunch singleton and records the original inner exception. No additional game-assembly transformation is used. The callback result field is not exercised in this mode; use the explicit constructor exception and stop boundary.

Commando material rendering: `./dev prototype --action material-render-prepare`, successful forced Vulkan build, then `./dev prototype --action controller-run`. Original methods assign source slots; detached owned copies render the albedo control and recovered emission off/on. `./dev prototype --action material-render-verify` repeats the passing fixture in a fresh process with the same APK/payload and separate evidence. This is a fixed-pose diagnostic rendering proof, not gameplay or desktop shader parity.

Original state scheduler: `./dev prototype --action state-tick-prepare`, forced Vulkan build, then `./dev prototype --action controller-run` adds an isolated original EntityStateMachine to the accepted material fixture. It checks Idle queue/interrupt and frame/fixed scheduling, automatic ticks and destruction. This is a scheduler precursor, not character movement, authority or L5.5 acceptance.

Original direction/authority: `./dev prototype --action direction-prepare`, forced Vulkan build, then `./dev prototype --action controller-run`. The isolated fixture refuses existing network sessions, verifies no-authority behavior, starts a loopback-only server and spawns an owned identity, checks original turning/neutral hold and shuts down. No master/body, walking, remote client or platform integration is claimed.

Sequential movement batch: `./dev prototype --action movement-batch-prepare`, successful forced Vulkan build, then `./dev prototype --action movement-batch-run`. Four independent button/input/motor experiments use separate cold launches and reports. The runner continues after an individual failure and stops the owned app afterward. Inactive diagnostic bodies and supplied stat values do not establish walking, physics integration or normal stat initialization.

Shipped kinematic solver batch: `./dev prototype --action kinematic-batch-prepare`, successful forced Vulkan build, then `./dev prototype --action movement-batch-run`. Separate cold launches test free integration, wall stop/slide, floor grounding and ungrounding. An authored diagnostic controller supplies velocity; the unchanged shipped solver computes positions and contacts. This does not activate original character lifecycle or establish playable movement.

Original motor/solver integration: `./dev prototype --action motor-integration-prepare`, successful forced Vulkan build, then `./dev prototype --action movement-batch-run`. Four fresh processes test original acceleration/braking, wall callback, Jump impulse and landing. `motor-wall-prepare` selects only the corrected initial-velocity wall fixture. Landing may fail on missing game-wide context; inspect its own report rather than treating other passes as landing acceptance.

Landing context: `./dev prototype --action landing-batch-prepare`, forced Vulkan build, then `./dev prototype --action movement-batch-run` tests event lifecycle, recovered fall-artifact catalog, artifact manager and original landing in separate processes. `landing-context-prepare` selects only landing. Preparation copies the measured artifact closure into the separate content bundle and restores the original layer-name table without changing the physics collision matrix. The one-entry catalog and inactive body/Run are diagnostic only.

Gravity/state batch: `./dev prototype --action gravity-state-prepare`, forced Vulkan build, then `./dev prototype --action movement-batch-run`. Five independent launches exercise original gravity rules/falling, Jump plus gravity/landing, GenericCharacterMain input gathering and original state-driven acceleration/stop. Measured lab gravity and supplied body stats are diagnostic inputs; full character startup, input-triggered jump/skills and physical controls remain separate.

Grounded state batch: `./dev prototype --action grounded-state-prepare`, wait for a successful forced Vulkan build, then `./dev prototype --action movement-batch-run`. Tests measured source gravity, grounded original state movement/reversal/wall contact. A terminal-build receipt is required before installation. `grounded-motion-retry` reruns only movement into a separate verification directory using the same prepared attempt and APK. See docs/character-jump-input-boundary.md for the next inventory/networking boundary.

Jump-input batch: `./dev prototype --action jump-input-prepare`, completed forced Vulkan build, then `./dev prototype --action movement-batch-run`. Tests recovered item identity, empty original inventory lifecycle, server-only jump-event dispatch and the first press through original movement state. `jump-input-retry-prepare` selects the three catalog-dependent probes. Diagnostic catalogs/stats and inactive body remain; no complete Commando or controller claim.

Recovered lifecycle batch: `./dev prototype --action body-lifecycle-prepare`, completed forced Vulkan build, then `./dev prototype --action movement-batch-run`. Separately tests diagnostic buff storage, recovered Commando Awake/registration and recovered PlayerMaster setup. Roots remain inactive; full startup, stats, body-master networking and gameplay are not accepted by these probes.

Recovered networking batch: `./dev prototype --action body-network-prepare`, completed forced Vulkan build, then `./dev prototype --action movement-batch-run`. Tests original state-machine network wiring, actual recovered body/master server spawning and the body's original master-ID setter. Inventory adoption, reciprocal linkage and connected-client behavior remain separate.

Recovered inventory adoption: `./dev prototype --action body-adoption-prepare`, completed forced Vulkan build, then `./dev prototype --action movement-batch-run`. Separate launches check five recovered definitions and original master-getter inventory callbacks. Diagnostic subset catalogs and inactive roots remain; reciprocal linkage and normal stats/startup are separate.

Original stat batch: `./dev prototype --action body-stats-prepare`, completed forced Vulkan build, then `./dev prototype --action movement-batch-run`. Tests team experience, recovered team membership, minimal Run singleton lifecycle and concrete original Commando base stats separately. Inactive roots and diagnostic subset catalogs remain; this does not initialize a complete run or player session.

`body-stats-retry-prepare` selects the original recovered skill-initialization probe and stat retry after J88, retaining the three separate passing prerequisite receipts.

`body-stats-motor-prepare` selects recovered motor capsule initialization and stat retry after J89; earlier skill/team/Run results remain separately receipted.

`body-stats-buffs-prepare` selects separate recovered knockback-buff catalog/storage, original zero-buff handler and stat probes after J90. Populate the diagnostic catalog before original body allocation; preserve name-map cleanup and the non-authoritative motor-branch limitation.

After a recovered-reference regression, `body-buffs-reference-prepare` selects buff-disabled/enabled controls. Once both pass, `body-buffs-methods-run` runs the handler/stat assertions on the same APK with separate verification evidence.

Automatic spawned scheduling: `./dev prototype --action spawn-automatic-prepare`, completed forced Vulkan build, then `./dev prototype --action movement-batch-run`. Two accepted explicit-step controls precede a separate 60-second automatic original Body state-machine probe. Review current-process logs before `./dev prototype --action spawn-automatic-motor-run`, which reuses that build for automatic original motor/solver neutral hold and scripted movement/braking in separate launches. These probes retain diagnostic body Start, inactive children, zero gravity/no collisions and an explicit original overlay update; full character/application lifecycle, controls and L5.5 remain separate.

`spawn-automatic-motion-prepare` selects only the automatic-motion probe for a forced rebuild/retry after a measured observer correction. S98/S99/S100 component holds pass; source gravity/collisions, continuing body callbacks, character visuals and physical/client controls remain separate. The original timed spawn-exit buff remains unticked with CharacterBody callbacks inactive.


Barrier dependency probes: `./dev prototype --action barrier-effect-prepare` selects original typed prefab loading/release; `barrier-completion-prepare` selects the original successful-handle completion callback. Each preparation requires the locally preserved, input-matched legacy/catalog/callback attribution and a completed forced Vulkan build before `movement-batch-run`. Review current-process logs before `barrier-lifecycle-run`, then `spawn-automatic-barrier-run`, which reuse the APK with separate fresh-launch evidence. `barrier-lifecycle-prepare` selects a forced lifecycle-only retry after an attributed harness correction. These are diagnostic component proofs: the broad original Init attempt rejects on unavailable effect requests; full startup, graphics parity and formal L5.5 remain separate.


Automatic recovered direction: `./dev prototype --action spawn-automatic-direction-prepare`, serial refresh/motor-order, preflight, completed forced Vulkan build, then `movement-batch-run` selects the neutral Start/cache/facing gate. After its current-process acceptance, `spawn-automatic-direction-motion-run`, `spawn-automatic-direction-reverse-run` and `spawn-automatic-direction-aim-run` select independent fresh launches using the same APK. Original state input and public aim-timer stimulus drive original automatic facing; no manual turning/transform writes. Models/children/animation, physical controls and full character/formal acceptance remain separate.


Automatic model following: `./dev prototype --action spawn-automatic-model-prepare`, serial editor refresh/character-motor-order, preflight and a completed forced Vulkan build stage the neutral ModelLocator detachment/follow/cleanup probe for `movement-batch-run`. After accepting current-process evidence, `spawn-automatic-model-motion-run`, `spawn-automatic-model-reverse-run` and `spawn-automatic-model-aim-run` each run independently with the same APK. The exact original model remains inactive before natural detachment, and original LateUpdate owns all following; end-of-frame pose and original destruction are observed. Animation/rendering/death and formal L5.5 remain separate.


Automatic skill timing: `./dev prototype --action spawn-automatic-skill-prepare`, serial editor refresh/character-motor-order, preflight and a completed forced Vulkan build select the all-four neutral stock hold for `movement-batch-run`. After current-process acceptance, `spawn-automatic-skill-primary-run`, `spawn-automatic-skill-secondary-run`, `spawn-automatic-skill-utility-run` and `spawn-automatic-skill-special-run` each enable only the selected original slot in a fresh launch. Original public stock reset is the diagnostic stimulus; automatic original SkillDef callbacks replenish stock. Ability execution and physical input remain separate.

Nova control observation: `./dev prototype --action nova-input-prepare` measures the explicitly configured Nova's current gamepad and bounded capture support, then shows the owned Lab screen only after experiment selectors are cleared. When the user is ready to press physical controls, `nova-input-capture` records that gamepad alone for 60 seconds, without injecting controller input. Raw target/capability/event records stay ignored. Kernel events alone do not prove original ReInput initialization or game binding.


Original Rewired target contract: `./dev prototype --action rewired-platform-prepare`, serial editor refresh, preflight and a completed forced Vulkan build stage an inactive-manager detector probe for `movement-batch-run`. This observes original platform/backend/Android API methods and actual Unity joystick availability without initializing ReInput or touching services. A reproduced Windows/Mono result completes the diagnostic experiment and does not pass Android input integration.

Official Rewired trial evaluation: `./dev prototype --action rewired-trial-inventory` compares the ignored active reference attempt with the accepted input. `./dev prototype --action rewired-trial-run` observes its completed SDK-only Android build on Nova for 90 seconds, restores the previously owned APK and sleeps the display. Prepare/import/build only in `rewired-trial-reference`, never the accepted lab. See [measured compatibility and scope](docs/rewired-trial-reference.md); the current trial is not a drop-in game replacement.

Nova OLED protection: current ignored local configuration enables `sleep_display_when_idle`. Lab launch and screenshot/gamepad capture wake only a live verified Nova; CLI completion puts it asleep again, including failed runtime commands. Power keys do not simulate controller input. Host-only commands leave it asleep. Other device models are refused when this option is enabled.


Temporary Nova input producer: `./dev prototype --action nova-bridge-prepare`, restore measured motor/producer order, force Vulkan build, then `nova-bridge-raw-run`, `nova-bridge-bind` and `nova-bridge-commando-run`. This feeds original InputBankTest without replacing gameplay or Rewired; skill execution is disabled for the movement proof. See [scope, measured mappings and rollback](docs/nova-input-bridge.md). Exact Rewired compatibility is deferred by current user direction.

Original primary boundary: `./dev prototype --action primary-fire-prepare`, pinned editor refresh, preflight and forced Vulkan build, then `primary-fire-run` isolate original factory/activation and the first unmodified native firing consumer. The dependent firing case dispatches only after the contract passes. See [accepted scope and next probe](docs/commando-primary-boundary.md).

Integrated continuation: when the active stage already contains the measured primary configurations, `nova-bridge-prepare` carries the accepted Nova mapping forward and stages the combined spine. After forced Vulkan build, `movement-batch-run` performs a short scripted bring-up; `nova-bridge-commando-run` requires a ready human for physical move/aim/A-jump/X-primary. It renders the actual spawned model with recovered meshes/Animator and a diagnostic follow camera. Audio/firing effects remain explicitly unavailable.
