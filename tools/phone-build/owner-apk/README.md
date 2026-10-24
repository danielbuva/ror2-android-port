# Owner APK payload bootstrap candidate

Current experimental installation support after accepted-output reconstruction.
The private candidate's preparation, increasing-version upgrade, Unity lifecycle
and assisted standard controls are device-qualified in
[J1065](../../../docs/PORTING_JOURNAL.md#j1065--qualify-private-owner-apk-preparation-upgrade-and-unity-lifecycle).
[J1095](../../../docs/PORTING_JOURNAL.md#j1095--retain-one-on-device-owner-key-across-separate-apk-signing-builds)
qualifies durable phone signing on authored APKs. Ordinary app packaging-tool
hosting, installer UI and independent PC-input production remain open; this is not an adopted final distribution architecture.
Game-bearing packets, APKs, metadata and outputs remain private under
ignored `work/`; no key or game content belongs in Git.

Android 11 [restricts other apps' external app-specific directories](https://developer.android.com/about/versions/11/privacy/storage).
A separate launcher cannot simply reproduce the lab's ADB payload sync. This
candidate instead includes the owner's verified runtime payload in the owner's
APK. An authored Android entry activity prepares its own
`getExternalFilesDir(null)/payload`, matching the existing `Device.sync` and
`WholeCatalogComposed` contract, then starts the original Unity activity.
Android [provides this app-specific location without storage permission](https://developer.android.com/training/data-storage/app-specific).

The native IL2CPP libraries, original DEX files, game resources and all payload
contents retain their hashes. Binary manifest structure editing moves only the
original MAIN/LAUNCHER filter into the new authored activity and makes the
original Unity entry private to prevent bypassing preparation. Resource indices
and all other original activity/application attributes remain intact. No Unity
project, source text replacement, stripping, game compilation, runtime backend,
shader mechanism or replacement content loader is introduced.

## Owners and lifecycle

- `PayloadStore.java` owns bounded streaming, exact hashes, fresh storage
  admission, per-file staging/rename and retained backups. Unknown existing
  contents require an exact observed-hash review before replacement. It writes
  only named prepared files and its own stage/backup directories; saves and
  settings are outside its target set. Pause takes effect between files.
- `PayloadBootstrapActivity.java` owns the app entry, worker, private completion
  receipt, native update consent, launch verification and WebView lifecycle.
  A process restart rechecks actual files; a receipt alone never makes it ready.
  Completed files survive pause/restart, and failed stages/backups are retained.
  After Unity is requested, this process cannot prepare replacement data. The
  WebView is released before handing off to Unity. A same-process launcher
  re-entry resumes the already prepared Unity activity directly. The lab's old direct exported-Unity
  launch helper is not the candidate's public entry; exercise its bootstrap/Play
  path rather than changing the shared helper for this experiment.
- `owner-host.js` connects the approved frontend's adapter v1 to fixed native
  actions. It exposes no paths, account state, arbitrary JavaScript/shell or file
  access. Polling/subscription teardown does not cancel preparation. Only bundled
  allowlisted HTTPS-origin resources are served; navigation/network are blocked.
- `index.html` provides accurate owner-APK preparation copy while reusing the
  unchanged approved `launcher/{app.js,controller.js,style.css,background.png}`.
  The simulated demo is never included. There is no new tracked PNG exception.
- `binary_manifest.py` edits binary XML using the existing public `phone_apk.py`
  chunk/string reader. `build_owner_apk.py` compiles only the authored Java to a
  separate DEX, assembles the owner APK and independently hashes every entry.
  No current `./dev` game build consumes this path.

Preparation reserves 2 GiB plus all required new data and metadata margin.
Source and output stream in 64 KiB blocks; the largest bundle is not read into
one Java array. Backups and failed stages count against fresh capacity. This
approach stores payload in both the installed APK and prepared app files: its
size/space cost and actual installer behavior must be measured before adoption.
It never formats storage, relocates another app or clears user data to fit.

## Build the complete private candidate

Use the exact accepted profile supported by `accepted-output/`. An explicit
ignored request JSON contains these paths and the manifest SHA:

```json
{
  "manifest": "PRIVATE_PACKET_MANIFEST",
  "manifest_sha256": "93789f88d8fff178e31e1a4b78bc5cf735bb63f6e17d8bfd4518474dbff99d4a",
  "targets": "VERIFIED_RECONSTRUCTED_OUTPUT_ROOT",
  "frontend": "PUBLIC_REPOSITORY_LAUNCHER_DIRECTORY",
  "java": "SUPPLIED_JDK_BIN_JAVA",
  "android_jar": "SUPPLIED_ANDROID_API_30_JAR",
  "d8_jar": "SUPPLIED_BUILD_TOOLS_34_D8_JAR",
  "wire_helper": "PUBLIC_REPOSITORY_SCRIPTS_LAB_PHONE_APK_PY",
  "version_code": 2
}
```

```sh
python3 -I -S tools/phone-build/owner-apk/build_owner_apk.py \
  --request PRIVATE_REQUEST.json --output NEW_PRIVATE_OUTPUT_DIRECTORY
```

`version_code` is optional. Omission retains the frozen manifest version. An
explicit value must be a positive Android integer greater than the frozen
input version; select a value greater than every previously installed owner
version for an update. Only that typed manifest attribute changes in addition
to the launcher routing. Retain the same private signing key across updates.

Keep the public source tree's relative `owner-apk/` and `accepted-output/`
directories together when staging on Android. Supply the wire helper explicitly;
the builder never finds a timestamped analysis directory. SDK/tool acquisition
remains owner supplied; no redistribution permission is inferred by compilation.

The new unsigned ZIP uses deterministic entry metadata and aligned, uncompressed
`resources.arsc`. It uses ZIP32 and refuses unsupported archive size rather than
silently producing a ZIP64 APK. Canonically check alignment, owner-sign with a
persistent private key and verify signatures/alignment/content before installing.
Installation requires the explicit authorized device, fresh placement/capacity
and ownership receipts. Do not replace the working lab game while another chat
owns its device. Preserve the original input/accepted APK, failed runs and receipts.

## Prior art and acceptance boundaries

The pinned BepInEx.Android.Launcher `fd1a4023` README and Fusion exports were
inspected. They explicitly provide injection/runtime-container hooks; that
mechanism is excluded here. Existing source `WholeCatalogComposed` and the
accepted `payload/whole-catalog.json` supply the measured content contract.
No community implementation is copied. The existing framework, original loader,
serialization identities and gameplay remain authoritative.

J1065 qualifies the complete private candidate through authorized ADB installs,
fresh preparation/readback, pause/interruption/restart, update consent/backup,
unknown-file refusal, retained user data, live placement/backing, public
bootstrap/Play, warm re-entry and both assisted standard controls. Ordinary
Android installer UX, integration of J1095 signing into the ordinary app/full
player build, independent input-only production and matched performance remain
open.
Neither the frontend nor successful extraction claims account ownership,
authentication, DLC access or original-game readiness.


## Durable owner signing

The same owner accepts `--sign-request PRIVATE_SIGN_REQUEST.json --output
NEW_PRIVATE_OUTPUT` after unsigned APK assembly. The request fields are exactly
`unsigned`, `java`, `zipalign`, `apksigner_jar` and `key_directory`, all explicitly
supplied local paths. Tool acquisition remains owner supplied. Keep the durable
key directory separate from build outputs and preserve it across upgrades.

On first use the owner creates `owner.p12` (alias `owner`) and a random private
`password` file in that private directory. Later processes validate/reuse them;
missing or mismatched existing state fails without replacing a key. Back up that
owner key through an authorized private mechanism before removing its host data;
never include it in an APK, recipe, public report or Git. The laboratory fixture's
disposable signing identity is a separate mechanism.

The owner writes new aligned/signed APKs and command/result logs, verifies the
signature and 16 KiB alignment, and checks that every nonsignature APK content
entry and original input/key remain unchanged. It reserves room for two output
APKs plus 2 GiB. It never installs an APK. Failures and private keys remain; only
the explicit disposable output may be removed after retaining needed evidence.
J1095 qualifies two separate phone processes reusing a key for authored APKs;
ordinary app delivery and the complete independent game APK remain open.
