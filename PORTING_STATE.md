# Porting state

Updated 2026-10-24 UTC after **J1079** (phone content), **J1078** (host infrastructure)
and **J1077** (Main device evidence).
Main's R43 restores visible source-camera terrain and original sound paths after
native audio readiness. Both standard controls pass with nonzero MainOutput,
including the previously silent stage-control window. Source-view color/lighting
parity and complete audio remain open. Confirmed End Run, original audio
Term/disarm, application-owned Quit and a fresh-process restart pass; observed
exits take about 16–21 seconds.
This laboratory is not a finished port.

Full results belong in the [journal](docs/PORTING_JOURNAL.md), searchable
through the [index](docs/JOURNAL_INDEX.md).

## Snapshot

| Item | Current fact |
| --- | --- |
| Accepted input | Steam 25475991; input `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88` |
| Toolchain | Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan; `environment/toolchain.json` |
| Latest Main diagnostic | J1077/R43 `206978b5e5d749ce11391bd68fe5689545b549abce414f2170aa7ad824589b02`, build source `2be4fa64`: both standard controls and visible source world; bounded MainOutput is nonzero in both controls. Full mix and PC appearance remain open. |
| Latest UI feature | J1066 Thor `299445f72267f216b23c7c4c2610364329445625396d8cd536bab01c07747ead`, source `bf40428f`, qualifies application screen lifetime and strict native abandon/restart. Preceding modal-corrected `c17a0ccc2947ac4b7c02cf43c183170ff866f88b03e90629c70a96121c1d18bb`, source `e8600060`, qualifies native keyboard/preview/consent/copy/browser return and confirmation/cancel. Automatic gameplay diagnostics do not qualify complete physical/touch play. |
| Installed now | Main has R43 in adopted storage; independent readback verifies installed bytes, runtime backing, unchanged 13-run profile, process/selector absence and sleeping display. J1072 restored Thor's 299445f7 in internal storage at handoff, with exact installed hash, runtime backing, selector/process absence and both panels OFF verified. Its shared lease was released; later owners may advance the receipts. Never infer installation from Git HEAD. |
| Runtime source since those APKs | R43 joins the bank-release resume hook, native feedback/confirmation, source ScreenDamage/camera World inclusion and readiness-scoped original sound preservation. Its 266 payload hashes equal the R39 rendering anchor. Source-stage audio preservation is host-qualified on `dani/source-stage-audio`; its full content build and Main device gates are pending. Later source/documentation/phone producer commits do not prove a different installation. Shared-editor builds can move the host pointer independently. |
| Developer iteration | J1072: current fresh-Data pre-Gradle splice and explicit ScriptsOnly actions; [operation](docs/fast-iteration.md). Normal verification APK `00b5813ce4faa860b3f2094a2daeab15849bcd181c5e120964c09a8d7b50b603`, source `0f0fab22`; fast verification APK `3375a6514e2092f5908f880e06675104bf6451a23ec9e52afb4982751a95fdf7`, source `20c3dbd7`. These are separate from the installed/accepted rollbacks. Streaming stays default after the matched transport check. |
| Parallel build infrastructure | J1078: isolated APFS lanes pass concurrent code/full builds, private Gradle teardown and explicit iteration-only uncompressed reuse. [Commands](docs/build-lanes.md). Normal host control `1935024b8f290c456044c83cd1b6fb069a8179be40fedc3d6f5ba1367e1d0d94`, source `0b1e048c`, is retained for host comparison; it is not device-verified or installed. Acceptance compression stays LZ4. |
| Accepted rollback | J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`, source `1780ea9`; scope in [BASELINE.md](docs/BASELINE.md). |
| Previous Main diagnostics | R38/J1068 `ede957ee8faaa12106d7c36685625ed5459619452704a1c45517f5c65e6c2cba`; R37/J1067 `4e5f0feb79c5bc35b15518af39293779d5216f839cceb30103ceb8240f5fde5b`; R36/J1040 `bda30f33a62d62176cd45fd9cc0bd50ed5fe4e12d325ddc7ef19e948ec0fd3e7`; R35/J1034 `47d14cb855ce8fefdf2406d55591d13165665c4a160ab7d71f435c6469faba6e`. |
| Owner candidate / shared device | J1065 owner version 2 `4960fba8ed5e727639c4f156e2f08cf92a6b6486790bb0ab295925e9bd212de0`, source `b9d74dd7`, retains its J850 preparation, upgrade and assisted-controls qualification. The shared device now has alpha APK `564d4573c764f69376cb07ee1834fc191db65055a335f68650a12ef9298531aa`: J1079 independently confirms its path/hash unchanged by content production, process absent and OLED asleep. Later owners may advance the install receipt; the owner APK is not currently installed. |
| Phone-only production | V1 targets exactly J850 through explicit target profiles; promotion follows a complete phone build/run. J1063 qualifies host game-code production; J1065 qualifies the private owner APK. J1073/J1074 qualify public-prefix tools and three-DLL app hosting. J1070 produces 13,231 mesh records exactly on Android, with two exclusions; J1075 produces all 228 Avatars; J1079 produces all 399 uncompressed textures and builds their public JPEG tool on Android. Complete bundle/player-data assembly and other content remain the content workstream's gates. The code workstream owns J850 managed/native/Burst/shader closure, final APK/signing/installer. Full phone installation and matched performance remain open; Architecture C and desktop fallback stay fixed. |
| Historical executable rollbacks | J425 `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0`; paused J323 Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`. [Retention policy](docs/history-retention.md). |
| Retained old input | Steam 21587608 / Unity 2021.3.33f1 retained for old rollbacks only. |

## Capability and remaining gates

Original catalogs, recovered offline menus, profile-eligible survivor/loadout
selection, native world play, commerce, teleporter transport and multiple kits
have assisted device evidence. See [milestones](docs/milestones.md) and
[subsystem coverage](docs/subsystem-coverage.md) for their actual scopes.
Normal-difficulty full runs and complete kit semantics remain open.

R43's plain and stage-control MainOutput windows contain nonzero finite samples.
Original source pistol identity is preserved; its first read-only playing-ID
sample is empty. Complete mix/spatial behavior, event attribution and speaker
audibility remain open. Source camera/skin rendering remains opt-in: terrain,
grass and survivor are visible after J1077, with Deferred Shading/HDR/Linear
observed, but appearance remains flat/desaturated and PC parity is unaccepted.

The next gameplay work is:

1. Compare source-view output with a matched PC reference and resolve a measured
   remaining rendering difference without arbitrary lighting/exposure tuning.
2. Complete original audio mix/spatial/audibility and reduce Quit latency while
   preserving original Term/disarm ownership.
3. Finish survivor-kit semantics, the native Siren/egg boss mission, unassisted
   normal runs, sustained performance and thermal acceptance.

The alpha owner continues physical/touch controls, managed-growth and release
surface work, with separate evidence. [Public alpha](docs/public-alpha.md),
[execution backlog](docs/execution-backlog.md), [screen inventory](docs/SCREEN_COVERAGE.md)
and [policy](docs/ALPHA_POLICY.md) retain the remaining delivery gates. Identity,
online services, account downloads and Steam Cloud remain unavailable/deferred.
Moon/finale/escape remain manual only. Root owns Main gameplay/audio and the
shared editor; all editor mutations retain the host mutex. Pipeline and owner
boundaries live in [architecture](docs/ARCHITECTURE.md).
