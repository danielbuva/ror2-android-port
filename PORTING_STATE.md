# Porting state

Updated 2026-10-25 UTC after **J1120**, **J1119**, **J1118**, **J1117**, **J1116**, **J1115**, **J1114**, **J1113**, **J1112**, **J1110**, **J1109**, **J1107**, **J1103**, **J1102**, **J1100**, **J1098**, **J1095**, **J1094**, **J1093**, **J1092**, **J1091**, **J1088**, **J1086** and **J1084**.
Main's R44 preserves original stage audio clients through verified teardown and
restart, with confirmed End Run, original Term/disarm and application-owned Quits.
The alpha candidate adds device-verified software touch, native pause,
recoverable settings saves and fresh background return. Physical input, memory
bounds, ordinary full runs, PC appearance and full audio remain open. This
laboratory is not a finished port.

Full results belong in the [journal](docs/PORTING_JOURNAL.md), searchable
through the [index](docs/JOURNAL_INDEX.md).

## Snapshot

| Item | Current fact |
| --- | --- |
| Accepted input | Steam 25475991; input `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88` |
| Toolchain | Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan; `environment/toolchain.json` |
| Latest Main diagnostic | J1080/R44 `3d012ee9783e900117a10718d442582a3e6e6ecc1f444a48c316db7f043d4467`, build source `4c950513`: both standard controls, loaded source-audio clients on Lakes/Goolake, original Term/disarm, application-owned Quit and fresh-process restart. Full mix and PC appearance remain open. |
| Latest UI feature | J1071/J1091 `32c4742eba0bb61060f9e2a63441fdd0b961f5ada82e1f059101f1b75b7fd677`, build source `5f25a12d`: complete software-touch/native-consumer, cancellation, held-pause, save-failure/retry, fresh background return and confirmed same-process menu case. J1066 supplies reviewed native feedback and strict abandon/restart on `299445f72267f216b23c7c4c2610364329445625396d8cd536bab01c07747ead`. These do not qualify hardware controls or normal full play. |
| Installed now | Main's last J1080 readback is R44 in adopted storage. The shared internal Nova independently retains R55 `111b1facec5b021c87dce03be24c9b81e913160809e685dc94b23e161786917a`; J1107's source-only tool cases leave its bytes unchanged, the game stopped and OLED asleep. No game installation or launch occurs in those cases. Thor's last alpha handoff verifies `564d4573c764f69376cb07ee1834fc191db65055a335f68650a12ef9298531aa`, process/selector absent, both physical panels OFF and original vendor mode restored. Thor gameplay remains fail-closed until stable top-only physical-panel control exists. Shared handoffs may advance receipts; never infer installation from Git. |
| Runtime source since those APKs | Main R44 retains R43's source visibility and ready-source actor audio, adding requested-mode stage clients. Alpha `437caf70` includes the landed R44 readiness gate plus touch bank/GUI ownership and foreground-scoped SDK diagnostics; later P1-tool/source/doc integration does not prove another APK installation. Host build pointers can move independently. Source `5f25a12d` additionally separates touch pending jumps from physical latching and adds opt-in idle heap capture. Normal code build `32c4742e` succeeds with unchanged payload; its complete software-touch/native-pause and opt-in capture cases pass separately from `d211c7fa`. J1092's normal full build at `e27cffac` corrects periodic diagnostic logging and clears destroyed targets in returned pooled bullet hits after teardown. Its first device series fails on the known LightningStake error; J1100's retry completes 12 strict sessions and verifies the cleanup. Later host-only persistence diagnostics and documentation do not prove another APK installation. |
| Developer iteration | J1072: current fresh-Data pre-Gradle splice and explicit ScriptsOnly actions; [operation](docs/fast-iteration.md). Normal verification APK `00b5813ce4faa860b3f2094a2daeab15849bcd181c5e120964c09a8d7b50b603`, source `0f0fab22`; fast verification APK `3375a6514e2092f5908f880e06675104bf6451a23ec9e52afb4982751a95fdf7`, source `20c3dbd7`. These are separate from the installed/accepted rollbacks. Streaming stays default after the matched transport check. |
| Parallel build infrastructure | J1093 restages each lane's own authored sources at creation and before builds, with Git/receipt byte proof and unchanged generated-content checks. J1078: isolated APFS lanes pass concurrent code/full builds, private Gradle teardown and explicit iteration-only uncompressed reuse. [Commands](docs/build-lanes.md). Normal host control `1935024b8f290c456044c83cd1b6fb069a8179be40fedc3d6f5ba1367e1d0d94`, source `0b1e048c`, is retained for host comparison; it is not device-verified or installed. Acceptance compression stays LZ4. |
| Accepted rollback | J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`, source `1780ea9`; scope in [BASELINE.md](docs/BASELINE.md). |
| Previous Main diagnostic | R43/J1077 `206978b5e5d749ce11391bd68fe5689545b549abce414f2170aa7ad824589b02`, build source `2be4fa64`. Earlier diagnostic evidence remains in the journal. |
| Owner candidate / shared device | J1065 owner version 2 `4960fba8ed5e727639c4f156e2f08cf92a6b6486790bb0ab295925e9bd212de0`, source `b9d74dd7`, retains its preparation/upgrade and assisted-control qualification. It shares the lab namespace and is currently replaced by R55 `111b1fac` under the retained-data handoff. Prior differing owner runtime bytes remain hash-preserved device-locally; no uninstall/data clear occurs. J1107 independently verifies installed bytes unchanged through the bounded source-only tool cases. This diagnostic handoff does not qualify final alpha update policy. |
| Phone-only production | V1 targets exactly J850; promote only after complete phone build/run proof. J1098 closes the host native runtime-byte gap: metadata and all 23 runtime sections match with corrected object order. The original-input phone native job continues under its original plan and still needs explicit corrected relinking. J1103 qualifies public ordinary-app Burst (all 20 runtime sections and fresh linker roots exact) and durable app signing for authored APKs; tool APK `f740d20378e8971f5968aeef8e5bce3bcead8ad7b492153dc5f79178a4bae99f` is separate from the game. J1102's APK owner consumes all three produced code outputs without replay fallback. J1107 completes source-only host production of all 1,333 remaining single-mip RGBA texture records; full phone qualification remains open after thermal refusals and the interrupted guarded rerun. J1110 produces all 1,589 ETC1 mip-chain records exactly on the host; Android qualification remains open. J1119 supplies 5,531 byte-exact source-only animation/controller/material records on the host through the existing object-pack interface; these partial packs alone close no final-file readiness entry. J1120 extends J1113/J1115/J1117 to six complete source-derived host bundles, composed with J1118's 153 player-data files, including existing source-produced texture packs; 54 texture selections use J1107's public RGBA producer/profile. J1116 separately rewrites all 133 accepted UnityFS bundles byte-exact with bounded host memory; this accepted-record structural control produces no independent content. Phone replay and complete bundle/player-data/original shader gates remain open; partial producer qualification is documented in [public alpha](docs/public-alpha.md). J1109 reproduces all 13 generic Android SDK package entries raw-exact on the host. The guarded ordinary-app rerun succeeds in 37.938 seconds: 11 entries raw-exact; two DEX files differ only in compiler-class checksums and derived headers, with all remaining bytes exact. Peak CPU temperature is 79.2 C with 340 ms maximum sample gap, meeting the short-job protocol. Host fixtures compose all 16 produced SDK/gameplay outputs without replay files. J1112 adds an exhaustive final-file readiness check before compilation and passes full host composition/signing with explicit validation-only replay content; J1114 generates both generic Android build-metadata files without accepted-byte suppliers: fresh host SDK production yields all 15 entries raw-exact. Combined readiness now has 177 of 705 entries available: all 18 code/SDK entries and 159 source-produced content files, with 528 final content files missing (400 player-data and 128 payload). Ordinary-app qualification of the added metadata, final source content and corrected phone-native production remain open. Code retains final assembly/signing/installer. Full-player signing needs explicit compatible signer provisioning for the shared lab package. Complete source-derived installation, matched controls/performance and security qualification remain open; Architecture C and desktop fallback stay fixed. |
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
observed, but appearance remains flat/desaturated and PC parity is unaccepted.

The next gameplay work is:

1. Compare source-view output with a matched PC reference and resolve a measured
   remaining rendering difference without arbitrary lighting/exposure tuning.
2. Complete original audio mix/spatial/audibility and reduce Quit latency while
   preserving original Term/disarm ownership.
3. Finish survivor-kit semantics, the native Siren/egg boss mission, unassisted
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
smaller frontier is attributed. The original console itself must not be purged. [Public alpha](docs/public-alpha.md),
[execution backlog](docs/execution-backlog.md), [screen inventory](docs/SCREEN_COVERAGE.md)
and [policy](docs/ALPHA_POLICY.md) retain the remaining delivery gates. Identity,
online services, account downloads and Steam Cloud remain unavailable/deferred.
Moon/finale/escape remain manual only. Root owns Main gameplay/audio and the
shared editor; all editor mutations retain the host mutex. Pipeline and owner
boundaries live in [architecture](docs/ARCHITECTURE.md).
