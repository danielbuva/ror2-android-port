# ADR-002 — Owner-built public alpha distribution

Status: **accepted for Route A by the user**, 2026-10-20. Amendment to
[ADR-001](ADR-001-port-architecture.md); Architecture C remains accepted.
Route A here means owner-side delivery, not ADR-001's source-reconstruction
architecture A. Runtime replacement and external publication are not approved.
Open work: [public-alpha.md](public-alpha.md).

## Decision

The user selects **A, owner-built IL2CPP**. Public users obtain their legitimate
PC game files, reconstruct Android content locally and build/install their own
APK with the pinned desktop editor. The project publishes reviewed tooling,
recipes and instructions. This preserves the existing device-tested runtime;
public-input bootstrap and ordinary gameplay acceptance remain open.
The B/C runtime investigations below remain unselected alternatives.

The repository distributes reviewed tooling and recipes; owners supply their
legitimate files and generate all game-derived outputs locally. The current
APK embeds original assembly code after AOT compilation and recovered data.
Its builder selects IL2CPP/ARM64 in `android/Assets/Editor/LabBuild.cs`.
[Unity documents IL-to-native conversion][unity-il2cpp]: moving bundles out of
the APK leaves compiled game code inside it. Encrypting, splitting or separately
downloading that code still distributes game-derived material. A content-free
installer does not itself solve execution or content conversion.

## Rimdroid findings

Inspected source: **5071c0ff8e52c3fda3b128aade7551b6ceaf0baa**. This is source
evidence, not a device test or an audit of a released APK.

- **Files:** [SteamDownloadSpike.java][rim-steam] authenticates through
  JavaSteam, supports mobile approval/email/authenticator codes, then uses
  license callbacks and depot downloads. Its reconnect token remains in memory
  with persistent sessions disabled, but account names are logged.
  [GogAuth.java][rim-gog] uses WebView authorization-code login; tokens stay in
  memory while cookies persist until sign-out. [GogLibrary.java][rim-library]
  queries the signed-in library. [The README][rim-readme] also supports an
  owner-supplied Linux game ZIP. These RimWorld-specific paths establish useful
  interaction patterns, not RoR2 ownership or storefront compatibility.
- **APK/runtime:** box64 runs the user's Linux x86-64 player with graphics/input
  compatibility libraries. The optional native route instead packages a Unity
  **2022.3.35f1** Android player and an ARM64 Mono-backed replacement
  `libil2cpp.so` ([il2mono build][rim-cmake]). [Preparation][rim-prepare] stages
  Unity engine libraries, Android UnityEngine assemblies, bootstrap resources
  and an authored bridge; [NativeEngine.java][rim-native] constructs the game
  data archive on-device from the imported instance. This is substantial engine
  integration. The tree also has an experimental RimWorld 1.7 .NET route;
  neither proves Unity 2021 compatibility. [CI][rim-ci] conditions native-engine
  inclusion, and [NOTICE][rim-notice] separates GPL/open/proprietary components.
  Its distribution choices grant this project no permissions.
- **Feedback:** the README directs users to GitHub Issues, but the pinned
  [LauncherActivity.java][rim-launcher] report button prepares an **email** via
  Android intents with an optional [LogExporter][rim-logs] ZIP. That exporter
  copies logs/configuration/crash information; it is not our required identifier
  redaction contract. Do not describe this as an in-app GitHub issue uploader.

## Options

Effort ranges below are low-confidence planning judgments for one experienced
engineer, excluding gameplay completion, external permissions and waiting time.

| Route | Owner workflow and public artifacts | Feasibility / effort |
| --- | --- | --- |
| **A — owner-built IL2CPP** | Obtain the game through the existing store client or local copy; run recipes with the pinned desktop editor; install the locally generated APK/payload. Publish source and recipes only. | Keeps the device-tested runtime. Roughly **2–6 engineer-weeks** for a supported bootstrap/build/install route; remaining local inputs may expand this. |
| **B — generic ARM64 player with interpreter** | Install an audited content-free player; import an owner-generated pack of transformed DLLs and Android bundles. Initially a computer still converts content. Publish no game DLL, compiled game implementation or derived content. | HybridCLR **8.x** is a credible Unity 2021.3 candidate. **1–2 weeks** for a go/no-go proof; **2–4+ engineer-months** for a supported route if viable. |
| **C — ARM64 Mono/native-engine bridge** | Install an audited engine/runtime shell; import owned files and any locally converted content. | Stock Unity has no ARM64 Mono player here. **2–4 weeks** to establish a narrow proof; a supported route is **months with no defensible upper bound**. Engine ABI, GC, objects, callbacks and licensing need independent qualification. |
| **D — desktop compatibility runtime** | Supply the desktop game to a Windows compatibility/emulation stack. | A different product path with no native-port acceptance. **1–2 weeks** could bound a device benchmark; middleware, controls and sustained play remain unknown. |

For A, R9's workstation reconstruction is not a public-input bootstrap. Remove
the local analysis/inherited-store/provenance dependencies documented in
[ARCHITECTURE](ARCHITECTURE.md#known-structural-debt), [LOCAL_STATE](LOCAL_STATE.md)
and [the structural backlog](execution-backlog.md#structural-cleanup); do not
ask owners to copy this workstation's `work/`. Authorized middleware inputs
and their build/distribution terms remain separate prerequisites.

For B, [HybridCLR 8.15 supports][hybrid-platforms] 2021.3 and Android ARM64;
[current guidance][hybrid-install] removes Unity 2021 support in 9.x. Its
[serialized-script requirements][hybrid-mono] include preloaded assemblies,
AssetBundles and a startup assembly list; [AOT generics][hybrid-generics] need
additional treatment. Our harness directly references game types, so removing
game DLLs from its AOT build is insufficient. Move game-dependent code behind
an explicit boundary and audit every generated bridge/metadata/stripping output
for game-derived content. No game implementation may remain embedded merely to
make a loading proof pass. Exact 2021.3.45f2, serialization, middleware and
performance compatibility remain unmeasured.

For C, read-only inspection of installed **2021.3.45f2** finds only
`mono/Release/Libs/armeabi-v7a`; IL2CPP includes `arm64-v8a`.
[Unity's backend documentation][unity-backends] likewise lists Android Mono
as Armv7. A 32-bit fallback loses the required ARM64 target and must requalify
memory/performance. Dropping another Mono library beside the player does not
provide Unity's scripting/object bridge. Rimdroid's version-specific native
engine work is evidence of a possible research direction, not a ready adapter.

Both B and C still need Android content. The original Windows shader sample
was rejected; current success uses local conversion
([architecture experiments](architecture-options.md)). The
[editor's supported hosts][unity-hosts] are desktop systems. A phone-only import
path needs a separate serialization/shader/content study; the present editor
pipeline cannot simply run in a launcher. A user-controlled remote builder
could relocate A's computer but adds private-input/signing custody. A public
build service is outside this proposal. Rights-holder-authorized binary
distribution is another route only if explicit authorization is obtained.

## Acquisition, cloud and feedback

Every route must validate the accepted build/hashes, preserve original files
and refuse unknown versions. Local import must say **files validated**, never
**Steam authenticated**. An owned-account download is acquisition; it does not
implement blocked original Steam startup, platform identity or DLC entitlement
([L5/L9](milestones.md), [ADR-001](ADR-001-port-architecture.md)). Latest store
downloads may differ from the accepted input. Steam/Guard needs separate
ownership, version and cancellation tests. No password/token/account identifier
belongs in logs; any retained credential needs an approved encrypted platform
store. Offline adapters must not fabricate service success.

**Propose deferring Steam Cloud from the first alpha.** Rimdroid has cloud
enumeration/download/upload tooling, but RoR2's Android profile and PC cloud
filesystem remain separate owners. First inspect RoR2's account-bound cloud
layout and prove compatibility, conflict detection, backups, interrupted writes
and rollback on disposable copies. Until then report cloud unavailable; a
consented manual backup/export is a smaller independent contract. Prior art:
[pinned profile/filesystem analysis](community-prior-art.md#startupplatform-graph-and-profile-boundary).

Proposed feedback: a short [prefilled GitHub new-issue URL][github-issues] in
the user's browser. They authenticate to GitHub and submit; no embedded APK
token or automatic sender. Exclude account/device/storage identifiers and logs
from query parameters. Offer a separate bounded, allowlisted, redacted report
preview/export only with consent; attachments are manual. No relay or public
issue-template change is authorized by this proposal.

## First proof and remaining approvals

Prove a clean checkout plus documented legitimate inputs can
rebuild/install on the assigned alpha device without workstation-only state.
After B/C approval, use a separate project for a bounded content-free-player
proof: import an owner's assembly and converted prefab, execute lifecycle
callbacks, retire/reload, and retain missing-input/type/version negative controls.
Audit the APK's actual contents. Synthetic callbacks or a loaded bundle alone
do not prove the original RoR2 contract or alpha readiness.

J818 assigns internal Nova exclusively to alpha; its configured serial is kept
in ignored local configuration and must be explicit on every device action.
Shared gameplay/editor state and the main device retain their existing owners.
Any B/C architecture experiment or external publication still needs separate
user approval. Device/build qualification is not implied by accepting Route A.

[unity-il2cpp]: https://docs.unity3d.com/2021.3/Documentation/Manual/IL2CPP.html
[unity-backends]: https://docs.unity3d.com/Manual/scripting-backends-intro.html
[unity-hosts]: https://docs.unity3d.com/2021.3/Documentation/Manual/system-requirements.html
[hybrid-platforms]: https://www.hybridclr.cn/en/docs/8.15.0/basic/supportedplatformanduniyversion
[hybrid-install]: https://www.hybridclr.cn/en/docs/basic/install
[hybrid-mono]: https://www.hybridclr.cn/en/docs/8.15.0/basic/monobehaviour
[hybrid-generics]: https://www.hybridclr.cn/en/docs/8.15.0/basic/aotgeneric
[github-issues]: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue#creating-an-issue-from-a-url-query
[rim-readme]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/README.md
[rim-steam]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/app/src/main/java/com/rimdroid/SteamDownloadSpike.java
[rim-gog]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/app/src/main/java/com/rimdroid/GogAuth.java
[rim-library]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/app/src/main/java/com/rimdroid/GogLibrary.java
[rim-cmake]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/unity/src/main/cpp/CMakeLists.txt
[rim-prepare]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/tools/unity-native/prepare_unity_module.sh
[rim-native]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/app/src/main/java/com/rimdroid/game/NativeEngine.java
[rim-ci]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/.github/workflows/build.yml
[rim-notice]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/NOTICE
[rim-launcher]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/app/src/main/java/com/rimdroid/LauncherActivity.java
[rim-logs]: https://github.com/udarmolota/RimDroid/blob/5071c0ff8e52c3fda3b128aade7551b6ceaf0baa/app/src/main/java/com/rimdroid/LogExporter.java
