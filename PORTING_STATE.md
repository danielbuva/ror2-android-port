# Porting state

Updated 2026-10-25 UTC after **J1171**, **J1169**, **J1168**, **J1167**, **J1166**, **J1163**, **J1161** and the linked prior results.
Main's R44 preserves original stage audio clients through verified teardown and
restart, with confirmed End Run, original Term/disarm and application-owned Quits.
The alpha candidate adds device-verified software touch, native pause,
recoverable settings saves and fresh background return. Physical input, memory
bounds, ordinary full runs, PC appearance and full audio remain open. This
laboratory is not a finished port. J1156 host-qualifies the revised per-zone
gameplay thermal policy; it adds no installed-player or gameplay qualification.

Full results belong in the [journal](docs/PORTING_JOURNAL.md), searchable
through the [index](docs/JOURNAL_INDEX.md).

## Snapshot

| Item | Current fact |
| --- | --- |
| Accepted input | Steam 25475991; input `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88` |
| Toolchain | Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan; `environment/toolchain.json` |
| Latest Nova diagnostic | J1105/J1101/R55 `111b1facec5b021c87dce03be24c9b81e913160809e685dc94b23e161786917a`, source `eb2acf07`, normal full build, zero errors. Integrates current main touch/settings/idle heap/retention with the R48–R51 rendering/Siren work and original collision policy. All 267 references verified; actual packaged policy and heap identifiers checked. All four exact-editor fixtures and 48 focused host checks pass. Installed on Nova; both strict controls and source-view Sobel/AO/grading/resource teardown pass, with nonzero finite MainOutput and confirmed End Run/original Term/natural Quit. Six native elite stakes remain finite. The Siren route stops on a charged-teleporter navigation stall before arrival; rare-NaN causality, PC appearance and mission completion remain open. |
| Next normal route/audio candidate | J1121/R58 `4386916991386bdf5b747e69786be58fa72ccfb0d3fc0220f59061ede495d0f5`, build source `55149b48`: normal full content/player build, 185.312 s/zero errors; all 267 references independently rehashed. Includes the complete native Blink-tick correction and R57's destination-only MainOutput selection. Both exact-editor fixtures and 253 focused host tests pass (one expected skip). Installed in place with payload and profile checks; J1152 subsequently passes thermal admission and launches the plain control, but the thermal guard aborts at a CPU/all-zone peak of 81.6 C before any measured world play. No control is accepted; destination capture and Siren-route recovery remain device gates. R57/J1111 `e950fcb18ff8ed69c56b9399bd528657277af901525b6563cd4ed988c5a43f37` and R56 `39413fcf04d7d8da5c4eb56576b8facc3d3fd605ed8800503ef7daafe56094d2` remain frozen uninstalled predecessors. |
| Iteration comparison | J1097/R53 fast `8c53767a53f29e31b23f38b7ec9d0bc4b0d39340756351cc07f1544c2cc597d5` uses the same source and exact normal R52 payload; iteration-only. R52 normal `9ce08c18188fb5919cb278ebff793bfdfe9cbe30ad4eb626d0d10f50c74f175f` remains the collision-policy checkpoint. |
| Latest Main diagnostic | J1080/R44 `3d012ee9783e900117a10718d442582a3e6e6ecc1f444a48c316db7f043d4467`, build source `4c950513`: both standard controls, loaded source-audio clients on Lakes/Goolake, original Term/disarm, application-owned Quit and fresh-process restart. Full mix and PC appearance remain open. |
| Latest UI feature | J1071/J1091 `32c4742eba0bb61060f9e2a63441fdd0b961f5ada82e1f059101f1b75b7fd677`, build source `5f25a12d`: complete software-touch/native-consumer, cancellation, held-pause, save-failure/retry, fresh background return and confirmed same-process menu case. J1066 supplies reviewed native feedback and strict abandon/restart on `299445f72267f216b23c7c4c2610364329445625396d8cd536bab01c07747ead`. These do not qualify hardware controls or normal full play. |
| Installed now | Main's last journal-backed J1080 readback is R44 in adopted storage; it remains the latest qualified Main diagnostic. The shared Nova last verifies R58 `4386916991386bdf5b747e69786be58fa72ccfb0d3fc0220f59061ede495d0f5`. J1164 verifies unchanged APK bytes and native pending-write interruption/recovery, then deliberately stops session-memory under J1156 sustained CPU heat (84.8 C peak), before a completed session or fresh heap. Process/selector/pending absence, OLED sleep and lease release pass. J1166 subsequently verifies unchanged R58 bytes and completed cleanup after repaired source-only player assembly stops at 80.4 C, before complete comparison; no installation or game launch occurs. Thor's last handoff verifies `564d4573c764f69376cb07ee1834fc191db65055a335f68650a12ef9298531aa`, both panels off and original vendor mode restored; stable top-only physical-panel control remains required. Shared handoffs may advance receipts; never infer installation from Git. |
| Runtime source since those APKs | J1152 publication rebases onto current main and refreshes merged shader-helper validation pins; those host changes are not in frozen R58. R55 integrates current main’s touch/settings, idle heap capture and retention corrections with the R48–R51 rendering/Siren work and original collision policy. Original native callbacks remain authoritative. R54 is a frozen uninstalled predecessor lacking idle heap capture. The normal build, packaged policy, both Nova controls and source-view teardown/Quit pass; six finite native elite stakes exercise precise/world attachment. Authored source since R55 adds a conservative automatic Huntress mobility landing check, qualified by J1108’s normal build, production host tests and exact-editor configuration fixture, but awaiting device verification. Subsequent authored source also adds an explicit destination-only MainOutput arm/check, qualified by J1111’s normal player build and host checks, awaiting device verification. J1121 subsequently corrects automatic Blink prediction to include complete native fixed ticks and qualifies original Engineer charge/three-phase configuration and native phase construction in the exact editor; R58 now includes this source in a normal full player build; it remains device-unverified. A charged-teleporter navigation stall blocks Siren arrival; rare-NaN causality and full mission acceptance remain open. |
| Developer iteration | J1072: current fresh-Data pre-Gradle splice and explicit ScriptsOnly actions; [operation](docs/fast-iteration.md). Normal verification APK `00b5813ce4faa860b3f2094a2daeab15849bcd181c5e120964c09a8d7b50b603`, source `0f0fab22`; fast verification APK `3375a6514e2092f5908f880e06675104bf6451a23ec9e52afb4982751a95fdf7`, source `20c3dbd7`. These are separate from the installed/accepted rollbacks. Streaming stays default after the matched transport check. |
| Parallel build infrastructure | J1093 restages each lane's own authored sources at creation and before builds, with Git/receipt byte proof and unchanged generated-content checks. J1078: isolated APFS lanes pass concurrent code/full builds, private Gradle teardown and explicit iteration-only uncompressed reuse. [Commands](docs/build-lanes.md). Normal host control `1935024b8f290c456044c83cd1b6fb069a8179be40fedc3d6f5ba1367e1d0d94`, source `0b1e048c`, is retained for host comparison; it is not device-verified or installed. Acceptance compression stays LZ4. |
| Accepted rollback | J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`, source `1780ea9`; scope in [BASELINE.md](docs/BASELINE.md). |
| Previous Main diagnostic | R43/J1077 `206978b5e5d749ce11391bd68fe5689545b549abce414f2170aa7ad824589b02`, build source `2be4fa64`. Earlier diagnostic evidence remains in the journal. |
| Owner candidate / shared device | J1065 owner version 2 `4960fba8ed5e727639c4f156e2f08cf92a6b6486790bb0ab295925e9bd212de0`, source `b9d74dd7`, retains its preparation/upgrade and assisted-control qualification. It shares the lab namespace and its last verified replacement is R58 `43869169` under the retained-data handoff (J1140 tool-only readback). Prior differing owner runtime bytes remain hash-preserved device-locally; no uninstall/data clear occurs. J1107 independently verifies installed bytes unchanged through the bounded source-only tool cases. This diagnostic handoff does not qualify final alpha update policy. |
| Phone-only production | J1174 host-qualifies public release metadata, per-entry dependency/output reuse and retained-key update signing; installer trust provisioning, dispatch and installed-game update evidence remain open. J1167 completes three guarded ordinary-app native compiler measurements; a measured active-time budget supports checked continuation from 498 retained objects, while complete native production and gameplay qualification remain open. J1168 records continuation failing before compilation because Android Python lacks `os.link`; a checked object-copy fallback passes host contracts, with device retry still open. Current legitimate originals are the only reconstruction supplier; J850 remains the comparison target. J1157 reproduces all 414 APK Shader48 objects on the host: 369 complete files and two shared records, without an Editor or accepted-byte supplier. J1163 adds exact Barrier and all three Goldshores payload bundles, extending J1155's cohort to twenty-two complete payload bundles and preserving all three current-input drift cases. Readiness has 587 of 705 final files available: 582 raw-exact, two produced code outputs requiring separate comparisons and three drift-explained current content files; 118 remain missing (7 APK, 111 payload). Fresh final-player producer proofs preserve both current drift outputs. J1161 supplies the complete 177-file player cohort (175 raw-exact and two explained current-input differences), including the registry and default-scene shared file. J1169 preserves every output with peak host RSS 289,341,440 bytes, below 500 MiB; a fresh guarded phone replay of all 177 files remains open. J1171 confirms random external GUIDs in identical-input scene YAML exports; the WholeStageContexts historical digest gate remains open without a new readiness claim. The host shared Shader mixed-file assembly is qualified; Shader production on the phone remains unqualified. Historical originals qualify the same public producer only and are never assembly suppliers. J1165 excludes the historical Snowy triplet from drift qualification; all 13 native Cubemap records remain open. All 18 host code/SDK providers remain available; J1098/J1103 retain IL2CPP/Burst runtime-section parity, and J1114 retains all 15 raw-exact host SDK entries. J1109 qualifies the short guarded ordinary-app SDK cohort separately; metadata rerun and sustained thermal qualification remain open. J1154 collects the original phone native job's failed 3,600 s wall timeout at job 498, retaining its completed object prefix. Active-time accounting, selected-unit measurement and receipt-validated continuation pass host contracts; actual guarded measurement/continuation remain open. J1162 records a host ADB stream SIGKILL during tool-host compilation before any native measurement; its sender is unknown. Cleanup leaves tool apps stopped, both panels asleep and the lease released. J1143 qualifies expanded source-only host animation/controller and hierarchy packs, adding no complete final-file readiness entry or APK mapping. Content record packs still require complete final-file assembly and phone qualification. Full-player compatible signer provisioning, complete source-derived installation, controls, matched performance and security qualification remain open. Architecture C and the desktop fallback stay fixed. Details and evidence are linked from [public alpha](docs/public-alpha.md) and [reconstruction](docs/accepted-build-reconstruction.md). |
| Historical executable rollbacks | J425 `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0`; paused J323 Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`. [Retention policy](docs/history-retention.md). |
| Retained old input | Steam 21587608 / Unity 2021.3.33f1 retained for old rollbacks only. |

## Capability and remaining gates

Original catalogs, recovered offline menus, profile-eligible survivor/loadout
selection, native world play, commerce, teleporter transport and multiple kits
have assisted device evidence. See [milestones](docs/milestones.md) and
[subsystem coverage](docs/subsystem-coverage.md) for their actual scopes.
Normal-difficulty full runs and complete kit semantics remain open.

R44's plain and stage-control MainOutput windows contain nonzero finite samples.
Original source pistol identity is preserved; its first read-only playing-ID
sample is empty. Native stage clients retain their original lifecycles in the
tested scenes. Complete mix/spatial behavior, event attribution and speaker
audibility remain open. Source camera/skin rendering remains opt-in: terrain,
grass and survivor are visible after J1077, with Deferred Shading/HDR/Linear
observed, but appearance remains bright/flat and PC parity is unaccepted. J1105
additionally qualifies Nova’s live original Sobel/AO/grading resources and owned
teardown; it does not supply a matched PC reference.

The next gameplay work is:

1. Repair the measured Scorched Acres navigation/recovery stall before Siren
   (J1105), preserving native movement and out-of-bounds ownership.
2. Compare source-view output with a matched PC reference and resolve a measured
   remaining rendering difference without arbitrary lighting/exposure tuning.
3. Complete original audio mix/spatial/audibility and reduce Quit latency while
   preserving original Term/disarm ownership.
4. Finish survivor-kit semantics, the native Siren/egg boss mission, unassisted
   normal runs, sustained performance and thermal acceptance.

J1071 qualifies scoped software touch and bounded persistence/lifecycle recovery;
physical digitizer/controller/rebinding and genuine equipped/interaction effects
remain open. J1069 stops the prior extended memory series on the known native
LightningStake failure after three completed sessions; no managed-growth bound
is accepted. J1086 completes all 12 constrained-device native sessions with no
runtime errors, but observes 46.77 MiB managed growth per session after warmup.
J1091 names the dominant growth source: periodic full diagnostic JSON retained
by the original console. J1092 installs the producer/dead-target corrections;
J1100 completes all 12 strict Commando sessions without runtime errors. Matched
menu growth falls from 46.879 to 0.579 MiB/session, but remains positive. The
664.63 MiB post-collection spike is retained; a full bound is refused until the
smaller frontier is attributed. J1164 qualifies native interrupted pending-write recovery, but stage-start thermal refusal leaves fresh heaps and sustained qualification open. The original console itself must not be purged. [Public alpha](docs/public-alpha.md),
[execution backlog](docs/execution-backlog.md), [screen inventory](docs/SCREEN_COVERAGE.md)
and [policy](docs/ALPHA_POLICY.md) retain the remaining delivery gates. Identity,
online services, account downloads and Steam Cloud remain unavailable/deferred.
Moon/finale/escape remain manual only. Root owns Main gameplay/audio and the
shared editor; all editor mutations retain the host mutex. Pipeline and owner
boundaries live in [architecture](docs/ARCHITECTURE.md).
