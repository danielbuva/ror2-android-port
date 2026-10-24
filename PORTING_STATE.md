# Porting state

Updated 2026-10-24 UTC after **J1072**, **J1068**, **J1066** and **J1070**.
Main's R38 passes both standard controls, original audio Term/disarm, application-owned Quit and a
fresh-process audio restart. Exit still takes about 20 seconds; full audio and
source-view appearance remain open. Thor separately qualifies native settings
feedback and confirmed End Run/restart. Their combined runtime awaits the next
Main build. Timed C# APK iteration now passes normal/fast Thor controls; a normal
full build remains its acceptance gate. This laboratory is not a finished port.

Full results belong in the [journal](docs/PORTING_JOURNAL.md), searchable
through the [index](docs/JOURNAL_INDEX.md).

## Snapshot

| Item | Current fact |
| --- | --- |
| Accepted input | Steam 25475991; input `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88` |
| Toolchain | Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan; `environment/toolchain.json` |
| Latest Main diagnostic | J1068/R38 `ede957ee8faaa12106d7c36685625ed5459619452704a1c45517f5c65e6c2cba`, source `fad0247e`: both standard controls, original Term/disarm, application-owned Quit and fresh-process audio. Full mix and source-view parity remain open. |
| Latest UI feature | J1066 Thor `299445f72267f216b23c7c4c2610364329445625396d8cd536bab01c07747ead`, source `bf40428f`, qualifies application screen lifetime and strict native abandon/restart. Preceding modal-corrected `c17a0ccc2947ac4b7c02cf43c183170ff866f88b03e90629c70a96121c1d18bb`, source `e8600060`, qualifies native keyboard/preview/consent/copy/browser return and confirmation/cancel. Automatic gameplay diagnostics do not qualify complete physical/touch play. |
| Installed now | Main has R38 in adopted storage; independent final readback verifies its bytes, runtime backing, byte-identical 13-run profile, selector/process absence and sleeping display. J1072 restored Thor's 299445f7 in internal storage at handoff, with exact installed hash, runtime backing, selector/process absence and both panels OFF verified. Its shared lease was released; later owners may advance the receipts. Never infer installation from Git HEAD. |
| Runtime source since those APKs | R38 contains the bank-release resume hook and retains all 266 R37 payload hashes, including the Uber/skill-timed MainOutput selections. J1066's feedback/confirmation/screen-lifetime source is now on main but absent from Main's R38; the audio hook is absent from Thor's UI APK. Their combined Main device gate is open. J1072 adds the generic Unity-version snapshot field and host iteration tooling; its Thor APK predates R38 integration. Shared-editor builds can move the host pointer independently. |
| Developer iteration | J1072: current fresh-Data pre-Gradle splice and explicit ScriptsOnly actions; [operation](docs/fast-iteration.md). Normal verification APK `00b5813ce4faa860b3f2094a2daeab15849bcd181c5e120964c09a8d7b50b603`, source `0f0fab22`; fast verification APK `3375a6514e2092f5908f880e06675104bf6451a23ec9e52afb4982751a95fdf7`, source `20c3dbd7`. These are separate from the installed/accepted rollbacks. Streaming stays default after the matched transport check. |
| Accepted rollback | J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`, source `1780ea9`; scope in [BASELINE.md](docs/BASELINE.md). |
| Previous Main diagnostics | R37/J1067 `4e5f0feb79c5bc35b15518af39293779d5216f839cceb30103ceb8240f5fde5b`; R36/J1040 `bda30f33a62d62176cd45fd9cc0bd50ed5fe4e12d325ddc7ef19e948ec0fd3e7`; R35/J1034 `47d14cb855ce8fefdf2406d55591d13165665c4a160ab7d71f435c6469faba6e`. |
| Owner candidate installed now | J1065 owner version 2 `4960fba8ed5e727639c4f156e2f08cf92a6b6486790bb0ab295925e9bd212de0`, producer source `b9d74dd7`, remains on its assigned device, stopped/asleep. J850 code/content, private preparation, upgrade retention and assisted controls pass; current audio integration and a public phone converter remain open. |
| Phone-only production | J1063 completes source-input host game-code production; J1065 qualifies the private owner APK. J1070 produces 13,231 accepted mesh records exactly on Android from original PC bundles, with two tangent/importer cases excluded. Complete bundle assembly, other content/Burst/shader producers, licensed native input, full-player Android tools, owner signing/installer UX and matched performance remain open. Architecture C and desktop fallback stay fixed. |
| Historical executable rollbacks | J425 `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0`; paused J323 Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`. [Retention policy](docs/history-retention.md). |
| Retained old input | Steam 21587608 / Unity 2021.3.33f1 retained for old rollbacks only. |

## Capability and remaining gates

Original catalogs, recovered offline menus, profile-eligible survivor/loadout
selection, native world play, commerce, teleporter transport and multiple kits
have assisted device evidence. See [milestones](docs/milestones.md) and
[subsystem coverage](docs/subsystem-coverage.md) for their actual scopes.
Normal-difficulty full runs and complete kit semantics remain open.

R38's plain/fresh MainOutput windows and saved prefix contain nonzero data;
the stage window is silent. Complete mix/spatial behavior, event attribution
and speaker audibility remain open. Source camera/skin rendering remains
opt-in and visually unaccepted after J1067's almost-black world image.

The next gameplay work is:

1. Restore the source ScreenDamage pre-composite contract and localize the
   source-view output; compare appearance before claiming PC parity. The next
   full Main build also joins the separately qualified audio and UI changes.
2. Complete original audio mix/spatial behavior and reduce Quit latency while
   preserving the observed original Term/disarm path.
3. Finish the survivor-kit semantics, native Siren/egg boss mission, unassisted
   normal runs, sustained performance and thermal acceptance.

The alpha owner continues physical/touch controls, managed-growth and release
surface work, with separate evidence. [Public alpha](docs/public-alpha.md),
[execution backlog](docs/execution-backlog.md), [screen inventory](docs/SCREEN_COVERAGE.md)
and [policy](docs/ALPHA_POLICY.md) retain the remaining delivery gates. Identity,
online services, account downloads and Steam Cloud remain unavailable/deferred.
Moon/finale/escape remain manual only. Root owns Main gameplay/audio and the
shared editor; all editor mutations retain the host mutex. Pipeline and owner
boundaries live in [architecture](docs/ARCHITECTURE.md).
